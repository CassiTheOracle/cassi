/**
 * VENDORED TYPE STUB — mirrors `reasoning-bank/index.js` `ReasoningBank` surface.
 *
 * Dreamer consumes `ReasoningBank` as an injected type (`setReasoningBank`) and
 * calls `.search()` / `.store()` on it. The runtime SQLite-backed implementation
 * is owned by a later auxiliary/coalesced package (re-point per the P5b Group B
 * table §A3.2). Type-only — no runtime impl reproduced here.
 */

import type {
  ReasoningBankStats,
  SearchResult,
  SearchTracesOpts,
  StoreTraceOpts,
  ReasoningBankOpts,
} from './types.js'

/**
 * Faithful `ReasoningBank` surface — the methods dreamer invokes on an injected
 * instance (`search`, `store`) plus the broader public method set for type
 * compatibility.
 */
export interface ReasoningBank {
  store(opts: StoreTraceOpts): string | null
  search(opts: SearchTracesOpts): SearchResult[]
  retrieveForBranch(goal: string, taskType?: string): string | null
  getStats(): ReasoningBankStats
  prune(): number
  close(): void
}

export type { ReasoningBankOpts, SearchResult, SearchTracesOpts, StoreTraceOpts, ReasoningBankStats, ReasoningTrace } from './types.js'
