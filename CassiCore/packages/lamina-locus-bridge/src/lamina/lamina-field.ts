/**
 * LaminaField — public API for tool-edited memory blocks.
 *
 * This is the high-level facade most callers should use. It:
 *   - Resolves caller identity + provenance via AsyncLocalStorage
 *   - Seeds a baseline set of laminae at boot (active-task, user-model, …)
 *   - Provides convenience accessors that don't require the caller to know
 *     about scopes
 *
 * The underlying LaminaStore is exposed for advanced use.
 */

import { resolveProvenance } from '../../runtime/audit/index.js'

import { LaminaStore, type LaminaCaller } from './lamina-store.js'
import { DEFAULT_CHAR_LIMIT } from './types.js'

import type { ILogger } from '../../../types/interfaces.js'
import type {
  Lamina,
  LaminaAppend,
  LaminaCreate,
  LaminaQuery,
  LaminaReplace,
  LaminaRethink,
  LaminaScope,
} from './types.js'

const SEED_LAMINAE: LaminaCreate[] = [
  {
    label: 'active-task',
    description: 'Living task tree — what I am working on, with subtasks, progress, and blockers.',
    owner: 'reverie',
    charLimit: 4_000,
    pinned: true,
    ownerExclusive: true,
    content: '- [~] Initializing memory systems',
  },
  {
    label: 'user-model',
    description: 'My evolving understanding of the user, their goals, preferences, and current emotional context.',
    owner: 'reverie',
    charLimit: 4_000,
    pinned: true,
    ownerExclusive: true,
  },
  {
    label: 'open-hypotheses',
    description: 'Hypotheses I am currently testing or holding in mind.',
    owner: 'primary',
    charLimit: 4_000,
  },
  {
    label: 'session-decisions',
    description: 'Decisions I have made this session that should persist into next steps.',
    owner: 'primary',
    charLimit: 4_000,
  },
]

export class LaminaField {
  readonly store: LaminaStore

  constructor(private readonly logger: ILogger, store?: LaminaStore) {
    this.store = store ?? new LaminaStore(logger)
  }

  /** Build a caller from the current AsyncLocalStorage step context. */
  private callerFor(agentId: string): LaminaCaller {
    return { agentId, provenance: resolveProvenance(agentId) }
  }

  seedDefaults(): number {
    let created = 0
    for (const seed of SEED_LAMINAE) {
      const before = this.store.findByLabel(seed.label)
      const lamina = this.store.ensure(seed, this.callerFor('boot'))
      if (!before && lamina) created++
    }
    if (created > 0) this.logger.info('[lamina] Seeded default laminae', { created })
    return created
  }

  // High-level reads

  /** Read a lamina by label, optionally scoped. Returns null if missing. */
  read(label: string, scope: LaminaScope = { kind: 'global' }): Lamina | null {
    return this.store.findByLabel(label, scope)
  }

  list(query?: LaminaQuery): Lamina[] {
    return this.store.list(query)
  }

  // High-level mutations — agentId comes from caller; provenance auto-resolved

  create(input: LaminaCreate, agentId: string): Lamina {
    return this.store.create(input, this.callerFor(agentId))
  }

  ensure(input: LaminaCreate, agentId: string): Lamina {
    return this.store.ensure(input, this.callerFor(agentId))
  }

  replace(label: string, input: LaminaReplace, agentId: string, scope: LaminaScope = { kind: 'global' }): Lamina {
    return this.store.replace(label, scope, input, this.callerFor(agentId))
  }

  append(label: string, input: LaminaAppend, agentId: string, scope: LaminaScope = { kind: 'global' }): Lamina {
    return this.store.append(label, scope, input, this.callerFor(agentId))
  }

  rethink(label: string, input: LaminaRethink, agentId: string, scope: LaminaScope = { kind: 'global' }): Lamina {
    return this.store.rethink(label, scope, input, this.callerFor(agentId))
  }

  delete(id: string): boolean {
    return this.store.delete(id)
  }

  /**
   * Mirror an external piece of state (e.g., a Pineal facet) into a read-only lamina.
   * Idempotent: updates content if changed, creates if missing.
   * Skips Pineal/owner-exclusive guards by setting owner = mirroring agent.
   */
  mirrorReadOnly(opts: {
    label: string
    content: string
    owner: string
    description?: string
    tags?: string[]
    scope?: LaminaScope
    charLimit?: number
  }): Lamina {
    const scope = opts.scope ?? { kind: 'global' }
    const existing = this.store.findByLabel(opts.label, scope)
    const caller = this.callerFor(opts.owner)
    if (!existing) {
      return this.store.create({
        label: opts.label,
        content: opts.content,
        description: opts.description ?? null,
        owner: opts.owner,
        readOnly: true,
        ownerExclusive: true,
        scope,
        tags: opts.tags ?? ['mirror'],
        charLimit: opts.charLimit ?? Math.max(opts.content.length, DEFAULT_CHAR_LIMIT),
      }, caller)
    }
    if (existing.content === opts.content) return existing
    return this.store.rethink(opts.label, scope, { content: opts.content, reason: 'mirror-update' }, caller)
  }

  metrics() {
    return this.store.metrics()
  }
}
