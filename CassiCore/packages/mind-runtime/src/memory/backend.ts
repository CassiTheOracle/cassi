/**
 * @cassicore/mind-runtime — MnemicField-backed memory adapter (plan §3).
 *
 * The ohmypi memory-backend contract, behaviorally, is `status / search / save`
 * (recon §1.5/§5.3). This adapter maps those three verbs onto the running
 * MnemicField (the mind runtime owns the field, plan §4.3):
 *   - save    → `field.store({ content, nodeType, metadata, provenance })`
 *   - search  → `field.retrieve(query, { limit, sessionId })` (kindling) with a
 *               `searchText` fallback when kindling yields nothing
 *   - status  → `field.stats()` (+ `getLightningStatus()` when relevant)
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

import type { MnemicField, MnemicRetrievalHit } from '@cassicore/mnemic-field'

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
      // fall through to searchText
    }
    // Kindling may be unavailable (no embeddings) — fall back to FTS searchText.
    try {
      const results = this.field.searchText(query, this.opts.searchTextLimit ?? limit * 2)
      return results.slice(0, limit).map(r => this.toView(r as unknown as MnemicRetrievalHit))
    } catch {
      return []
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
