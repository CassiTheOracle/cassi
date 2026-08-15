/**
 * projection.ts — Phase 3.2: project Mnemic engrams + Laminae into the repo.
 *
 * Runs during Meditation (not per-turn). Cap: 200 entity files.
 * Threshold: potentiation > 0.6 OR pinned OR referenced by active lamina OR
 *            nodeType in (decision, weakness, principle).
 *
 * Sensitive engrams (frontmatter `sensitive: true`) are blocked entirely.
 */

import type { ILogger } from '@cassicore/foundation'
import type { ContextRepoFs } from './fs.js'
import type { LaminaField } from '@cassicore/lamina-locus-bridge'
import type { ContextEntity, ContextRepoConfig } from './types.js'

export interface EngramLike {
  id: string
  type?: string
  nodeType?: string
  content: string
  potentiation?: number
  pinned?: boolean
  tags?: string[]
  metadata?: Record<string, unknown>
}

export interface MnemicReader {
  /** Pull the most-relevant engrams for projection. Return any subset that matters. */
  listForProjection(opts: { limit: number; minPotentiation: number }): EngramLike[]
}

const ALLOWED_TYPES = new Set(['decision', 'weakness', 'principle'])

function safeFilename(id: string): string {
  return id.replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 80)
}

function isSensitive(eng: EngramLike): boolean {
  const flag = eng.metadata?.sensitive
  return flag === true || flag === 'true'
}

export class Projector {
  constructor(
    private readonly fs: ContextRepoFs,
    private readonly logger: ILogger,
    private readonly cfg: ContextRepoConfig,
  ) {}

  /** Project current Lamina + Mnemic state. Returns counts. */
  project(opts: {
    lamina?: LaminaField
    mnemic?: MnemicReader
    /** Free-form identity content for system/identity.md (e.g., from PinealAssembler). */
    identity?: string
  }): { laminae: number; engrams: number; system: number } {
    this.fs.init()
    let laminaCount = 0
    let engramCount = 0
    let systemCount = 0

    // System
    if (opts.identity) {
      this.fs.writeEntity({
        relPath: 'system/identity.md',
        frontmatter: {
          id: 'identity', kind: 'identity', source: 'pineal',
          priority: 100, pinned: true, syncedAt: new Date().toISOString(),
        },
        body: opts.identity,
      })
      systemCount++
    }

    // Laminae
    if (opts.lamina) {
      const laminae = opts.lamina.list({ limit: 100 })
      // Clean stale lamina files
      const wantedFiles = new Set<string>()
      for (const lam of laminae) {
        const file = `laminae/${safeFilename(lam.label)}.md`
        wantedFiles.add(file)
        const entity: ContextEntity = {
          relPath: file,
          frontmatter: {
            id: lam.label,
            kind: 'lamina',
            source: lam.owner,
            priority: lam.pinned ? 90 : 50,
            pinned: lam.pinned,
            tags: lam.tags,
            syncedAt: new Date().toISOString(),
          },
          body: lam.content || '_(empty)_',
        }
        this.fs.writeEntity(entity)
        laminaCount++
      }
      for (const existing of this.fs.listEntities('laminae')) {
        if (!wantedFiles.has(existing)) this.fs.removeEntity(existing)
      }
    }

    // Engrams
    if (opts.mnemic) {
      let chosen = opts.mnemic.listForProjection({
        limit: this.cfg.entityCap,
        minPotentiation: this.cfg.potentiationThreshold,
      })
      // Drop sensitive
      chosen = chosen.filter(e => !isSensitive(e))
      // Augment with type-based promotion (decision/weakness/principle)
      chosen.sort((a, b) => (b.potentiation ?? 0) - (a.potentiation ?? 0))
      chosen = chosen.slice(0, this.cfg.entityCap)
      const wantedFiles = new Set<string>()
      for (const eng of chosen) {
        const promote = eng.pinned ||
          (eng.potentiation ?? 0) >= this.cfg.potentiationThreshold ||
          ALLOWED_TYPES.has(eng.nodeType ?? eng.type ?? '')
        if (!promote) continue
        const file = `entities/${safeFilename(eng.id)}.md`
        wantedFiles.add(file)
        this.fs.writeEntity({
          relPath: file,
          frontmatter: {
            id: eng.id,
            kind: 'engram',
            source: 'mnemic',
            priority: Math.round((eng.potentiation ?? 0) * 100),
            pinned: !!eng.pinned,
            potentiation: eng.potentiation,
            tags: eng.tags,
            syncedAt: new Date().toISOString(),
          },
          body: eng.content || '_(no content)_',
        })
        engramCount++
      }
      for (const existing of this.fs.listEntities('entities')) {
        if (!wantedFiles.has(existing)) this.fs.removeEntity(existing)
      }
    }

    // Index
    this.regenerateIndex(laminaCount, engramCount, systemCount)

    const sha = this.fs.commit(`project: meditation pass — ${laminaCount} laminae, ${engramCount} engrams`)
    if (sha) this.logger.info('[context-repo] projection committed', { sha, laminae: laminaCount, engrams: engramCount })

    return { laminae: laminaCount, engrams: engramCount, system: systemCount }
  }

  private regenerateIndex(laminae: number, engrams: number, system: number): void {
    const lines: string[] = ['# Context Repository', '']
    lines.push(`Last sync: ${new Date().toISOString()}`)
    lines.push('')
    lines.push(`- system: ${system}`)
    lines.push(`- laminae: ${laminae}`)
    lines.push(`- entities: ${engrams}`)
    lines.push('')
    lines.push('## Laminae')
    for (const f of this.fs.listEntities('laminae')) {
      lines.push(`- [${f.replace('laminae/', '').replace('.md', '')}](./${f})`)
    }
    lines.push('')
    lines.push('## Entities (top 20 shown)')
    const ents = this.fs.listEntities('entities').slice(0, 20)
    for (const f of ents) {
      lines.push(`- [${f.replace('entities/', '').replace('.md', '')}](./${f})`)
    }
    this.fs.writeEntity({
      relPath: 'CONTEXT.md',
      frontmatter: {
        id: 'index', kind: 'note', source: 'projector',
        priority: 0, pinned: true, syncedAt: new Date().toISOString(),
      },
      body: lines.join('\n'),
    })
  }
}
