/**
 * @cassicore/mind-runtime — MnemicField-backed memory adapter (plan §3).
 *
 * The ohmypi memory-backend contract, behaviorally, is `status / search / save`
 *   - save           → `field.store({ content, nodeType, metadata, provenance })`
 *   - search         → `field.retrieve(query, { limit, sessionId })` (kindling) with a
 *                      `searchText` fallback when kindling yields nothing
 *   - searchReadOnly → `field.searchTextStrict(query)` without retrieval-event
 *                      persistence, activation, broadcast, query logging, or
 *                      swallowed backend failures; used for attention candidates
 *   - status         → `field.stats()` (+ `getLightningStatus()` when relevant)
 *
 * Both ohmypi's built-ins (recall/retain/reflect/memory_edit) and the mind's own
 * memory ops hit the SAME field through this adapter (plan §3.2). The channel
 * memory endpoints (`/v1/memory/*`) are thin passthroughs into these methods.
 *
 * [VERIFY] Per plan §3.2 / brief Open Item 9: whether the ohmypi backend must
 * also expose a `memory://` URI resolver + an optional `learn` path is undecided
 * (local backends expose them; structured backends center on recall/retain/
 * reflect/memory_edit). This adapter implements `status/search/save` only; a
 * `memory://` read resolver would proxy `field.get`/`searchByProvenance` over a
 * future `/v1/memory/read` endpoint. Default (this phase): not wired.
 */

import { createHash } from 'node:crypto'

import type { MnemicField, MnemicRetrievalHit } from '@cassicore/mnemic-field'

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

/** Structural stop-words the kindling fallback uses when text search returns nothing. */
export interface MnemicMemoryAdapterOptions {
  /** Cap the `search` fallback's raw `searchText` result pool. */
  searchTextLimit?: number
}

/** The retained `save` entry shape (mapped onto EngramCreate). */
export interface MemorySaveEntry {
  content: string
  type?: string
  metadata?: Record<string, unknown>
  sessionId?: string
}

interface AttentionSearchField {
  searchTextStrictAsync?: (query: string, limit: number, timeoutMs: number) => Promise<Array<{
    engram: {
      id: string
      content: string
      nodeType?: string | null
      metadata?: Record<string, unknown>
    }
    score?: number
  }>>

}

/** A mapped retrieval hit exposed over the channel (`ids/content/score/metadata`). */
export interface MemoryHitView {
  id: string
  content: string
  score: number
  nodeType?: string | null
  metadata?: Record<string, unknown>
}

/**
 * Adapter implementing the ohmypi memory-backend surface (`status/search/save`)
 * over a live MnemicField. Instantiated by boot.ts and shared by the channel's
 * `/v1/memory/*` endpoints and (spine-side) `ctx.memory` wiring.
 */
export class MnemicMemoryAdapter {
  private activeReadOnlySearches = 0
  private static readonly MAX_CONCURRENT_READ_ONLY_SEARCHES = 2
  constructor(
    private readonly field: MnemicField,
    private readonly opts: MnemicMemoryAdapterOptions = {},
  ) { }

  /** status() — field stats (+ lightning when the indexer is active). */
  status(): { backend: 'mnemic-field'; stats: Record<string, unknown> | null; lightning: Record<string, unknown> | null } {
    let stats: Record<string, unknown> | null = null
    let lightning: Record<string, unknown> | null = null
    try {
      const s = this.field.stats()
      stats = (s as unknown as Record<string, unknown>) ?? {}
    } catch {
      stats = null
    }
    try {
      lightning = this.field.getLightningStatus() as unknown as Record<string, unknown>
    } catch {
      lightning = null
    }
    return { backend: 'mnemic-field', stats, lightning }
  }

  /** search(query, opts) — kindling retrieve with a searchText fallback. */
  async search(query: string, opts?: { limit?: number; type?: string; sessionId?: string }): Promise<MemoryHitView[]> {
    const limit = opts?.limit ?? 5
    if (!query || !query.trim()) return []
    try {
      const hits = await this.field.retrieve(query, { limit, sessionId: opts?.sessionId })
      const views = hits.map(hit => this.toView(hit))
      if (views.length > 0) return views
    } catch {
      // fall through to strict FTS
    }
    // Kindling may be unavailable (no embeddings) — fall back to bounded FTS.
    try {
      return await this.searchTextViews(query, limit)
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
        score: typeof engram.potentiation === 'number' ? engram.potentiation : 0,
        nodeType: (engram.nodeType as string | null | undefined) ?? null,
        metadata: (engram.metadata ?? {}) as Record<string, unknown>,
      }
    } catch {
      return null
    }
  }
  private async searchTextViews(query: string, limit: number, deadlineMs = 300): Promise<MemoryHitView[]> {
    const ftsQuery = literalFtsQuery(query)
    if (!ftsQuery) return []
    const resultLimit = Math.min(Math.max(1, this.opts.searchTextLimit ?? limit * 2), MAX_FTS_RESULTS)
    const strict = (this.field as MnemicField & AttentionSearchField).searchTextStrictAsync
    if (!strict) throw new Error('mnemic-strict-search-unavailable')
    const results = await strict.call(this.field, ftsQuery, resultLimit, deadlineMs)
    return results.slice(0, Math.min(limit, MAX_FTS_RESULTS)).map(result => ({
      id: safeOpaqueId(result.engram.id),
      content: result.engram.content.slice(0, MAX_CONTEXT_CONTENT_CHARS),
      score: typeof result.score === 'number' ? result.score : 0,
      nodeType: (result.engram.nodeType as string | null | undefined)?.slice(0, 64) ?? null,
      metadata: sessionMetadata(result.engram.metadata as Record<string, unknown> | undefined),
    }))
  }

  private toView(hit: MnemicRetrievalHit): MemoryHitView {
    return {
      id: hit.id,
      content: hit.content,
      score: typeof hit.score === 'number' ? hit.score : 0,
      nodeType: (hit as { nodeType?: string | null }).nodeType ?? null,
      metadata: ((hit as { metadata?: unknown }).metadata ?? {}) as Record<string, unknown>,
    }
  }
}
