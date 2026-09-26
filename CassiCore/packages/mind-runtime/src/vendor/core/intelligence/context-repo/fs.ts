/**
 * fs.ts — Phase 3.1: filesystem primitive + git wrapper.
 *
 * Owns the on-disk repo at ~/.cassicore/context-repos/<projectHash>/.
 * Exposes init / read / write / commit / log / diff / rebuild — the safety net
 * that every other phase relies on.
 *
 * git operations shell out to /usr/bin/git rather than using a JS impl, so
 * commits are visible to standard tooling (humans can `cd` in and inspect).
 */

import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { getCassiCoreHome } from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'
import type { ContextEntity, ContextFrontmatter, RepoIdentity, RepoStats } from './types.js'

const ROOT_SUBDIR = 'context-repos'

export function projectHashFor(projectPath: string): string {
  const norm = projectPath || 'global'
  return crypto.createHash('sha256').update(norm, 'utf8').digest('hex').slice(0, 16)
}

export function repoIdentity(projectPath: string, override?: string): RepoIdentity {
  const projectHash = projectHashFor(projectPath)
  const repoDir = override ?? path.join(getCassiCoreHome(), ROOT_SUBDIR, projectHash)
  return { projectPath, projectHash, repoDir }
}

function git(repoDir: string, args: string[], opts: { check?: boolean } = {}): string {
  try {
    return execFileSync('git', ['-C', repoDir, ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).toString()
  } catch (err: any) {
    if (opts.check === false) return ''
    throw new Error(`git ${args.join(' ')} failed: ${err?.stderr?.toString?.() ?? String(err)}`)
  }
}

function escapeYaml(s: string): string {
  if (s == null) return 'null'
  if (/[:\n#]/.test(s) || s.startsWith(' ') || s.endsWith(' ')) return JSON.stringify(s)
  return s
}

export function serializeFrontmatter(fm: ContextFrontmatter): string {
  const lines: string[] = ['---']
  lines.push(`id: ${escapeYaml(fm.id)}`)
  lines.push(`kind: ${fm.kind}`)
  lines.push(`source: ${escapeYaml(fm.source)}`)
  lines.push(`priority: ${fm.priority}`)
  lines.push(`pinned: ${fm.pinned}`)
  if (fm.potentiation !== undefined) lines.push(`potentiation: ${fm.potentiation}`)
  if (fm.tags && fm.tags.length > 0) lines.push(`tags: [${fm.tags.map(escapeYaml).join(', ')}]`)
  if (fm.sensitive) lines.push(`sensitive: true`)
  lines.push(`syncedAt: ${escapeYaml(fm.syncedAt)}`)
  lines.push('---')
  return lines.join('\n')
}

const FM_RE = /^---\n([\s\S]*?)\n---\n?/

export function parseEntity(relPath: string, raw: string): ContextEntity | null {
  const m = FM_RE.exec(raw)
  if (!m) return null
  const fmText = m[1]
  const fm: Record<string, unknown> = {}
  for (const line of fmText.split('\n')) {
    const idx = line.indexOf(':')
    if (idx === -1) continue
    const key = line.slice(0, idx).trim()
    let val: any = line.slice(idx + 1).trim()
    if (val === 'true') val = true
    else if (val === 'false') val = false
    else if (val === 'null') val = null
    else if (/^-?\d+(\.\d+)?$/.test(val)) val = Number(val)
    else if (val.startsWith('[') && val.endsWith(']')) {
      try { val = JSON.parse(val) } catch { val = val.slice(1, -1).split(',').map((s: string) => s.trim()).filter(Boolean) }
    } else if ((val.startsWith('"') && val.endsWith('"'))) {
      try { val = JSON.parse(val) } catch { /* keep raw */ }
    }
    fm[key] = val
  }
  const body = raw.slice(m[0].length)
  return { frontmatter: fm as unknown as ContextFrontmatter, body, relPath }
}

export class ContextRepoFs {
  readonly identity: RepoIdentity

  // In-memory guard: init is called defensively from many call sites (projector,
  // writeback, injection) but after the first successful run everything it does
  // is wasted I/O. The flag short-circuits subsequent calls.
  private initialized = false

  constructor(
    private readonly logger: ILogger,
    projectPath: string,
    rootOverride?: string,
  ) {
    this.identity = repoIdentity(projectPath, rootOverride)
  }

  /** Current HEAD sha of the repo, or null if uninitialized. Used as a cheap cache key. */
  headSha(): string | null {
    const dir = this.identity.repoDir
    if (!fs.existsSync(path.join(dir, '.git'))) return null
    try {
      return git(dir, ['rev-parse', 'HEAD'], { check: false }).trim() || null
    } catch {
      return null
    }
  }

  /** Initialize a fresh repo on disk if missing. Idempotent. */
  init(): void {
    if (this.initialized) return
    const dir = this.identity.repoDir
    fs.mkdirSync(dir, { recursive: true })
    if (!fs.existsSync(path.join(dir, '.git'))) {
      git(dir, ['init', '--initial-branch=main'])
      git(dir, ['config', 'user.email', 'cassi@local'])
      git(dir, ['config', 'user.name', 'Cassi'])
      // Seed structure
      for (const sub of ['system', 'laminae', 'entities', 'skills', 'sessions']) {
        const p = path.join(dir, sub)
        fs.mkdirSync(p, { recursive: true })
        const keep = path.join(p, '.gitkeep')
        if (!fs.existsSync(keep)) fs.writeFileSync(keep, '')
      }
      // Seed CONTEXT.md index placeholder
      const idx = path.join(dir, 'CONTEXT.md')
      if (!fs.existsSync(idx)) {
        fs.writeFileSync(idx, '# Context Repository\n\nCassi\'s working memory, mirrored as markdown.\n')
      }
      git(dir, ['add', '-A'])
      git(dir, ['commit', '-m', 'initial: seed context repo skeleton'], { check: false })
      this.logger.info('[context-repo] Initialized fresh repo', { dir })
    }
    this.initialized = true
  }

  /** Hard rebuild: nuke everything, re-init. Phase 3.1's safety net. */
  rebuild(): void {
    this.initialized = false
    const dir = this.identity.repoDir
    if (fs.existsSync(dir)) {
      // Preserve the dir itself but remove contents
      for (const entry of fs.readdirSync(dir)) {
        fs.rmSync(path.join(dir, entry), { recursive: true, force: true })
      }
    }
    this.init()
  }

  // Reads

  readEntity(relPath: string): ContextEntity | null {
    const p = path.join(this.identity.repoDir, relPath)
    if (!fs.existsSync(p)) return null
    return parseEntity(relPath, fs.readFileSync(p, 'utf8'))
  }

  listEntities(prefix: string): string[] {
    const root = path.join(this.identity.repoDir, prefix)
    if (!fs.existsSync(root)) return []
    return fs.readdirSync(root)
      .filter(n => n.endsWith('.md') && n !== '.gitkeep')
      .map(n => path.join(prefix, n))
  }

  // Writes

  writeEntity(entity: ContextEntity): void {
    const p = path.join(this.identity.repoDir, entity.relPath)
    fs.mkdirSync(path.dirname(p), { recursive: true })
    const out = `${serializeFrontmatter(entity.frontmatter)}\n${entity.body.startsWith('\n') ? entity.body.slice(1) : entity.body}`
    fs.writeFileSync(p, out, 'utf8')
  }

  removeEntity(relPath: string): void {
    const p = path.join(this.identity.repoDir, relPath)
    if (fs.existsSync(p)) fs.unlinkSync(p)
  }

  // Git ops

  /** Commit any pending changes; returns sha or null if nothing to commit. */
  commit(message: string): string | null {
    const dir = this.identity.repoDir
    git(dir, ['add', '-A'])
    const status = git(dir, ['status', '--porcelain'])
    if (status.trim().length === 0) return null
    git(dir, ['commit', '-m', message], { check: false })
    return git(dir, ['rev-parse', 'HEAD']).trim()
  }

  log(limit = 20): Array<{ sha: string; date: string; subject: string }> {
    const dir = this.identity.repoDir
    const out = git(dir, ['log', `-n${limit}`, '--pretty=format:%H%x09%aI%x09%s'], { check: false })
    if (!out.trim()) return []
    return out.split('\n').map(line => {
      const [sha, date, ...rest] = line.split('\t')
      return { sha, date, subject: rest.join('\t') }
    })
  }

  diff(args: string[] = []): string {
    return git(this.identity.repoDir, ['diff', ...args], { check: false })
  }

  status(): string {
    return git(this.identity.repoDir, ['status', '--short'], { check: false })
  }

  /** Run garbage collection — prune loose objects + worktrees. */
  gc(): void {
    git(this.identity.repoDir, ['gc', '--auto'], { check: false })
    git(this.identity.repoDir, ['worktree', 'prune'], { check: false })
  }

  stats(): RepoStats {
    const dir = this.identity.repoDir
    let totalFiles = 0
    let pinnedEntities = 0
    for (const sub of ['system', 'laminae', 'entities', 'skills']) {
      const p = path.join(dir, sub)
      if (!fs.existsSync(p)) continue
      for (const n of fs.readdirSync(p)) {
        if (!n.endsWith('.md')) continue
        totalFiles++
        try {
          const ent = parseEntity(path.join(sub, n), fs.readFileSync(path.join(p, n), 'utf8'))
          if (ent?.frontmatter?.pinned) pinnedEntities++
        } catch { /* ignore */ }
      }
    }
    const totalCommits = Number(git(dir, ['rev-list', '--count', 'HEAD'], { check: false }).trim() || '0')
    let worktrees = 0
    try {
      const wt = git(dir, ['worktree', 'list', '--porcelain'], { check: false })
      worktrees = (wt.match(/^worktree /gm) ?? []).length
    } catch { /* ignore */ }
    let diskBytes = 0
    try {
      const walk = (p: string) => {
        for (const e of fs.readdirSync(p, { withFileTypes: true })) {
          const c = path.join(p, e.name)
          if (e.isDirectory()) walk(c)
          else { try { diskBytes += fs.statSync(c).size } catch { /* ignore */ } }
        }
      }
      walk(dir)
    } catch { /* ignore */ }
    return { totalFiles, totalCommits, pinnedEntities, worktrees, diskBytes }
  }

  // Helpers used by phases 3.3+

  createWorktree(branch: string, subDir: string): string {
    const wtPath = path.join(this.identity.repoDir, '.worktrees', subDir)
    fs.mkdirSync(path.dirname(wtPath), { recursive: true })
    if (fs.existsSync(wtPath)) return wtPath
    git(this.identity.repoDir, ['worktree', 'add', '-b', branch, wtPath, 'main'], { check: false })
    return wtPath
  }

  removeWorktree(subDir: string): void {
    const wtPath = path.join(this.identity.repoDir, '.worktrees', subDir)
    git(this.identity.repoDir, ['worktree', 'remove', '--force', wtPath], { check: false })
  }

  mergeBranch(branch: string, message: string): { ok: boolean; conflicts: string[] } {
    const out = git(this.identity.repoDir, ['merge', '--no-ff', '-m', message, branch], { check: false })
    const conflicts = (out.match(/CONFLICT.*?in (\S+)/g) ?? []).map(s => s.replace(/^CONFLICT.*?in /, ''))
    if (conflicts.length > 0) {
      // Abort the merge to leave state clean — caller can re-run with conflict-resolution
      git(this.identity.repoDir, ['merge', '--abort'], { check: false })
      return { ok: false, conflicts }
    }
    return { ok: true, conflicts: [] }
  }
}

/** Make a temporary repo for tests. */
export function tempRepoIdentity(): RepoIdentity {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'context-repo-'))
  return { projectPath: 'test', projectHash: 'test', repoDir: dir }
}
