/**
 * claude-memory-importer.ts — One-way bridge from Claude Code's per-project
 * memory at ~/.claude/projects/<projectHash>/memory/ into CassiCore's
 * Lamina + Mnemic + Pineal layers.
 *
 * See docs/CLAUDE_MEMORY_BRIDGE.md for the architectural rationale.
 */

import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { getDataDir } from '@cassicore/foundation'
import { withStep } from '../../vendor/core/runtime/audit/index.js'

import type { ILogger } from '@cassicore/foundation'
import type { AuditStore } from '../../vendor/core/runtime/audit/index.js'
import type { LaminaField } from './lamina-field.js'

export interface PinealLikeForImport {
  createFacet?: (input: {
    domain: 'identity' | 'wisdom' | 'philosophy' | 'praxis'
    category: string
    content: string
    conviction?: number
    provenance?: string
    tags?: string[]
  }) => unknown
}

export interface MnemicLikeForImport {
  /** Best-effort store. Returns engram id or null. */
  store?: (input: { type: string; content: string; metadata: Record<string, unknown> }) => Promise<string | undefined> | string | undefined
}

export interface ClaudeImportOptions {
  /** Override the discovery root (default ~/.claude/projects). */
  claudeProjectsDir?: string
  /** Override the digest path. */
  digestPath?: string
  /** Project working directory used to derive the per-project subdir name. */
  projectPath?: string
  /** Skip the digest cache — always re-import. */
  force?: boolean
}

interface ImportDigest {
  files: Record<string, { hash: string; importedAt: string }>
}

interface ParsedMemoryNote {
  filename: string
  frontmatter: Record<string, unknown>
  body: string
}

const FM_RE = /^---\n([\s\S]*?)\n---\n?/

function parseFrontmatter(raw: string): { fm: Record<string, unknown>; body: string } {
  const m = FM_RE.exec(raw)
  if (!m) return { fm: {}, body: raw }
  const fm: Record<string, unknown> = {}
  for (const line of m[1].split('\n')) {
    const idx = line.indexOf(':')
    if (idx === -1) continue
    const key = line.slice(0, idx).trim()
    let val: any = line.slice(idx + 1).trim()
    if (val === 'true') val = true
    else if (val === 'false') val = false
    else if (/^-?\d+(\.\d+)?$/.test(val)) val = Number(val)
    fm[key] = val
  }
  return { fm, body: raw.slice(m[0].length) }
}

function fileHash(p: string): string {
  const stat = fs.statSync(p)
  return crypto.createHash('sha256')
    .update(`${p}|${stat.size}|${stat.mtimeMs}`, 'utf8')
    .digest('hex').slice(0, 16)
}

function projectHashFor(projectPath: string): string {
  // Mirror Claude Code's directory naming: replace / with -, leading - included
  return projectPath.replace(/\//g, '-')
}

export class ClaudeMemoryImporter {
  private digestPath: string

  constructor(
    private readonly logger: ILogger,
    private readonly lamina: LaminaField,
    private readonly opts: ClaudeImportOptions = {},
    private readonly pineal?: PinealLikeForImport,
    private readonly mnemic?: MnemicLikeForImport,
    private readonly audit?: AuditStore,
  ) {
    this.digestPath = opts.digestPath ?? path.join(getDataDir(), 'claude-memory-import.json')
  }

  /** Walk the memory dir + run the bridge. Returns a summary. */
  async importAll(): Promise<{ files: number; laminae: number; engrams: number; facets: number; skipped: number }> {
    const root = this.opts.claudeProjectsDir ?? path.join(os.homedir(), '.claude', 'projects')
    if (!fs.existsSync(root)) {
      return { files: 0, laminae: 0, engrams: 0, facets: 0, skipped: 0 }
    }

    const projectPath = this.opts.projectPath ?? process.env.CASSICORE_PROJECT_PATH ?? process.cwd()
    const subdir = projectHashFor(projectPath)
    const memoryDir = path.join(root, subdir, 'memory')
    if (!fs.existsSync(memoryDir)) {
      this.logger.debug?.('[claude-import] no memory dir for project', { memoryDir })
      return { files: 0, laminae: 0, engrams: 0, facets: 0, skipped: 0 }
    }

    const digest = this.readDigest()
    let files = 0, laminae = 0, engrams = 0, facets = 0, skipped = 0

    // Audit run wraps the entire import for provenance
    const run = this.audit?.startRun({ kind: 'import', agentId: 'claude-import', goal: `import ${subdir}` })
    const step = run && this.audit ? this.audit.startStep({ runId: run.id, slot: 'claude-import' }) : null
    const provenance = step ? { runId: run!.id, stepId: step.id, agentId: 'claude-import', reason: 'boot-import' } : null

    try {
      for (const filename of fs.readdirSync(memoryDir)) {
        if (!filename.endsWith('.md')) continue
        const full = path.join(memoryDir, filename)
        files++

        const hash = fileHash(full)
        if (!this.opts.force && digest.files[full]?.hash === hash) {
          skipped++
          continue
        }

        const raw = fs.readFileSync(full, 'utf8')
        const { fm, body } = parseFrontmatter(raw)
        if (fm.private === true || filename.startsWith('secret/')) {
          skipped++
          continue
        }

        const note: ParsedMemoryNote = { filename, frontmatter: fm, body }
        const writes = provenance
          ? await withStep(provenance, () => this.dispatch(note))
          : await this.dispatch(note)
        laminae += writes.laminae
        engrams += writes.engrams
        facets += writes.facets

        digest.files[full] = { hash, importedAt: new Date().toISOString() }
      }
      this.writeDigest(digest)
    } finally {
      if (this.audit && step && run) {
        this.audit.finishStep(step.id, { status: 'completed', toolCallCount: laminae + engrams + facets })
        this.audit.finishRun(run.id, 'completed')
      }
    }

    if (laminae + engrams + facets > 0) {
      this.logger.info?.('[claude-import] imported memory notes', { files, laminae, engrams, facets, skipped })
    }
    return { files, laminae, engrams, facets, skipped }
  }

  private async dispatch(note: ParsedMemoryNote): Promise<{ laminae: number; engrams: number; facets: number }> {
    const out = { laminae: 0, engrams: 0, facets: 0 }
    const type = String(note.frontmatter.type ?? '').toLowerCase()
    const name = String(note.frontmatter.name ?? note.filename.replace(/\.md$/, ''))

    // MEMORY.md is just an index — keep it in lamina as a catalog
    if (note.filename === 'MEMORY.md') {
      try {
        this.lamina.mirrorReadOnly({
          label: 'claude:memory-catalog',
          content: note.body.slice(0, 8_000),
          owner: 'claude-import',
          description: 'Index of Claude Code per-project memory notes',
          tags: ['claude', 'imported', 'catalog'],
          charLimit: 9_000,
        })
        out.laminae++
      } catch (err) {
        this.logger.debug?.('[claude-import] catalog mirror failed', { error: String(err) })
      }
      return out
    }

    switch (type) {
      case 'project':
      case 'feedback': {
        try {
          this.lamina.mirrorReadOnly({
            label: `claude:${type}:${name.slice(0, 60)}`,
            content: note.body.slice(0, 8_000),
            owner: 'claude-import',
            description: String(note.frontmatter.description ?? ''),
            tags: ['claude', 'imported', type],
            charLimit: 9_000,
          })
          out.laminae++
        } catch (err) {
          this.logger.debug?.('[claude-import] lamina mirror failed', { file: note.filename, error: String(err) })
        }
        break
      }
      case 'user': {
        if (this.pineal?.createFacet) {
          try {
            this.pineal.createFacet({
              domain: 'identity',
              category: 'user-model',
              content: note.body.slice(0, 4_000),
              conviction: 0.7,
              provenance: 'user',
              tags: ['claude', 'imported', name],
            })
            out.facets++
          } catch (err) {
            this.logger.debug?.('[claude-import] pineal facet failed', { error: String(err) })
          }
        }
        break
      }
      default: {
        if (this.mnemic?.store) {
          try {
            const id = await this.mnemic.store({
              type: type || 'note',
              content: note.body,
              metadata: {
                source: 'claude-import',
                filename: note.filename,
                frontmatter: note.frontmatter,
                tags: ['claude', 'imported'],
              },
            })
            if (id) out.engrams++
          } catch (err) {
            this.logger.debug?.('[claude-import] mnemic store failed', { error: String(err) })
          }
        }
      }
    }
    return out
  }

  private readDigest(): ImportDigest {
    try {
      if (!fs.existsSync(this.digestPath)) return { files: {} }
      return JSON.parse(fs.readFileSync(this.digestPath, 'utf8'))
    } catch {
      return { files: {} }
    }
  }

  private writeDigest(d: ImportDigest): void {
    try {
      fs.mkdirSync(path.dirname(this.digestPath), { recursive: true })
      fs.writeFileSync(this.digestPath, JSON.stringify(d, null, 2), 'utf8')
    } catch (err) {
      this.logger.warn?.('[claude-import] failed to persist digest', { error: String(err) })
    }
  }
}
