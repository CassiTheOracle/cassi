/** Exact Mnemic record adapter for the mind runtime memory surface. */

import { createHash } from 'node:crypto'

import {
  mnemicRecordRevision,
  type MnemicActionFinish,
  type MnemicActionStart,
  type MnemicExactStore,
  type MnemicFeedbackOutcome,
  type MnemicFieldCandidate,
  type MnemicFieldToolResult,
} from '@cassicore/mnemic-field'

const MAX_FTS_INPUT_CHARS = 1024
const MAX_FTS_TERMS = 12
const MAX_FTS_TERM_CHARS = 48
const MAX_FTS_RESULTS = 32
const MAX_CONTEXT_CONTENT_CHARS = 2048
const FTS_TERM = new RegExp(`[\\p{L}\\p{N}][\\p{L}\\p{N}_-]{0,${MAX_FTS_TERM_CHARS - 1}}`, 'gu')

/**
 * Convert arbitrary provider text into a bounded FTS5 literal query. This
 * removes operators/parentheses/wildcards, caps parser work, and prevents a
 * malformed prompt from reaching the raw FTS grammar.
 */
function literalFtsQuery(query: string): string {
  const terms: string[] = []
  const seen = new Set<string>()
  for (const match of query.slice(0, MAX_FTS_INPUT_CHARS).normalize('NFKC').matchAll(FTS_TERM)) {
    const term = match[0]
    const key = term.toLocaleLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    terms.push(`"${term}"`)
    if (terms.length >= MAX_FTS_TERMS) break
  }
  return terms.join(' OR ')
}

function safeOpaqueId(value: string): string {
  if (/^[A-Za-z0-9._:-]{1,128}$/.test(value)) return value
  return `sha256:${createHash('sha256').update(value).digest('hex').slice(0, 32)}`
}

function sessionMetadata(metadata: Record<string, unknown> | undefined): Record<string, unknown> {
  const sessionId = metadata?.sessionId
  return typeof sessionId === 'string' ? { sessionId: sessionId.slice(0, 128) } : {}
}
export interface MnemicMemoryAdapterOptions {
  searchTextLimit?: number
}


/** The retained `save` entry shape (mapped onto EngramCreate). */
export interface MemorySaveEntry {
  content: string
  type?: string
  metadata?: Record<string, unknown>
  tags?: string[]
  provenance?: string
  sessionId?: string
}


/** A mapped retrieval hit exposed over the channel (`ids/content/score/metadata`). */
export interface MemoryHitView {
  id: string
  content: string
  revision?: string
  score: number
  nodeType?: string | null
  metadata?: Record<string, unknown>
}

/** Runtime memory surface over exact SQLite records; adaptive ranking lives in CassiFI. */
export class MnemicMemoryAdapter {
  private activeReadOnlySearches = 0
  private static readonly MAX_CONCURRENT_READ_ONLY_SEARCHES = 2
  constructor(
    private readonly field: MnemicExactStore,
    private readonly opts: MnemicMemoryAdapterOptions = {},
  ) { }

  status(): { backend: 'mnemic-field'; stats: Record<string, unknown> | null } {
    let stats: Record<string, unknown> | null = null
    try {
      stats = this.field.stats() as unknown as Record<string, unknown>
    } catch {
      stats = null
    }
    return { backend: 'mnemic-field', stats }
  }

  /** Deterministic exact-text lookup; no second learned retrieval path. */
  async search(query: string, opts?: { limit?: number; type?: string; sessionId?: string }): Promise<MemoryHitView[]> {
    if (!query || !query.trim()) return []
    try {
      return await this.searchTextViews(query, opts?.limit ?? 5)
    } catch {
      return []
    }
  }

  /**
   * Strict, side-effect-free lookup for provider-context candidates.
   *
   * `MnemicField.retrieve()` records `queryText` plus retrieval telemetry and
   * activates/broadcasts hits. Attention prefetches must not persist a raw user
   * prompt merely because the provider is about to run, so this path uses only
   * the no-log strict FTS reader. A small literalized term/query/result budget
   * bounds synchronous SQLite work before the channel deadline. Errors propagate,
   * allowing the caller to report an accurate source status.
   */
  async searchReadOnly(
    query: string,
    opts?: { limit?: number; type?: string; sessionId?: string; deadlineMs?: number },
  ): Promise<MemoryHitView[]> {
    if (!query || !query.trim()) return []
    if (this.activeReadOnlySearches >= MnemicMemoryAdapter.MAX_CONCURRENT_READ_ONLY_SEARCHES) {
      throw new Error('mnemic-search-busy')
    }
    this.activeReadOnlySearches += 1
    try {
      return await this.searchTextViews(query, opts?.limit ?? 5, opts?.deadlineMs)
    } finally {
      this.activeReadOnlySearches -= 1
    }
  }

  /** save(entry) — store an engram and return its id. */
  save(entry: MemorySaveEntry): string {
    const engram = this.field.store({
      content: entry.content,
      // EngramCreate.nodeType is a rich enum union; the adapter's `type` string is
      // validated by the caller (ohmypi memory backend) and defaults to 'fact'.
      nodeType: (entry.type ?? 'fact') as unknown as never,
      tags: entry.tags,
      provenance: entry.provenance,
      metadata: { ...(entry.metadata ?? {}), ...(entry.sessionId ? { sessionId: entry.sessionId } : {}) },
    })
    return engram.id
  }

  /** Narrow read (used by `memory://`/read path when wired — [VERIFY] plan §3.2). */
  get(id: string): MemoryHitView | null {
    try {
      const engram = this.field.get(id)
      if (!engram) return null
      return {
        id: engram.id,
        content: engram.content,
        revision: mnemicRecordRevision(engram),
        score: typeof engram.potentiation === 'number' ? engram.potentiation : 0,
        nodeType: (engram.nodeType as string | null | undefined) ?? null,
        metadata: (engram.metadata ?? {}) as Record<string, unknown>,
      }
    } catch {
      return null
    }
  }

  getMany(ids: readonly string[]): MemoryHitView[] {
    return this.field.getMany(ids).map(engram => ({
      id: safeOpaqueId(engram.id),
      revision: mnemicRecordRevision(engram),
      content: engram.content.slice(0, MAX_CONTEXT_CONTENT_CHARS),
      score: 0,
      nodeType: engram.nodeType,
      metadata: sessionMetadata(engram.metadata),
    }))
  }

  rememberContextTurn(
    sessionId: string,
    turnId: number,
    query: string,
    candidates: readonly MnemicFieldCandidate[],
  ): void {
    this.field.rememberContextTurn(sessionId, turnId, query, candidates)
  }

  consumeContextFeedback(
    sessionId: string,
    turnId: number,
    includedCandidateIds: readonly string[],
    outcome: MnemicFeedbackOutcome,
    toolResult?: MnemicFieldToolResult,
  ): void {
    this.field.consumeContextFeedback(sessionId, turnId, includedCandidateIds, outcome, toolResult)
  }

  startActionEpisode(input: MnemicActionStart): void {
    this.field.startActionEpisode(input)
  }

  finishActionEpisode(input: MnemicActionFinish): void {
    this.field.finishActionEpisode(input)
  }

  latestCompactionCandidateIds(sessionId: string): string[] {
    return this.field.latestCompactionCandidateIds(sessionId)
  }
  private async searchTextViews(query: string, limit: number, deadlineMs = 300): Promise<MemoryHitView[]> {
    const ftsQuery = literalFtsQuery(query)
    if (!ftsQuery) return []
    const resultLimit = Math.min(Math.max(1, this.opts.searchTextLimit ?? limit * 2), MAX_FTS_RESULTS)
    const results = await this.field.searchTextStrictAsync(ftsQuery, resultLimit, deadlineMs)
    return results.slice(0, Math.min(limit, MAX_FTS_RESULTS)).map(result => ({
      id: safeOpaqueId(result.engram.id),
      revision: mnemicRecordRevision(result.engram),
      content: result.engram.content.slice(0, MAX_CONTEXT_CONTENT_CHARS),
      score: typeof result.score === 'number' ? result.score : 0,
      nodeType: (result.engram.nodeType as string | null | undefined)?.slice(0, 64) ?? null,
      metadata: sessionMetadata(result.engram.metadata as Record<string, unknown> | undefined),
    }))
  }
}
