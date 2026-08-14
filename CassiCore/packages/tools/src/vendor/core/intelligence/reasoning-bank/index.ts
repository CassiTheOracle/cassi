/**
 * VENDOR TYPE STUB — `core/intelligence/reasoning-bank/index.ts` (`ReasoningBank`).
 *
 * Type-placeholder for the reasoning-bank surface consumed by collect-thoughts.ts
 * (tools) via `deps.reasoningBank?.search(...)`. Only the search surface is
 * referenced. Owned by the P5 brain package; re-pointed when it lands (Open-6).
 */

/** Search options for the reasoning bank. */
export interface SearchTracesOpts {
  query: string
  taskType?: string
  minQuality?: number
  successOnly?: boolean
  limit?: number
}

/** A single stored reasoning trace. */
export interface ReasoningTrace {
  id: string
  approach: string
  content: string
  taskType?: string
  quality?: number
  succeeded?: boolean
}

/** A search hit against the reasoning bank. */
export interface SearchResult {
  trace: ReasoningTrace
  score: number
}

/** Cross-session store of successful reasoning traces, searchable by query. */
export interface ReasoningBank {
  search(opts: SearchTracesOpts): SearchResult[]
  store(opts: { trace: unknown; sessionId?: string }): string | null
  getStats(): unknown
  prune(): number
}
