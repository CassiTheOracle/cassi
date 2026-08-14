/**
 * @cassicore/model-pool — RETAINED PORT SURFACE (CASSICORE-FOCUS §19 / §6 P2)
 *
 * The mind-facing seam that survives P4. In the focused shape, ohmypi owns
 * providers + routing; the retained `ModelHandle` is the *mind's cast* over
 * an ohmypi completion (via `mind_complete` / task-agent subagents). This
 * ports/ module is the canonical retained surface; the pool machinery it
 * does NOT re-export (FallbackManager, BudgetManager, CapabilityCache,
 * billing-models, rate-limit/blocked/allowlist wiring, the provider-map
 * pool) is DELEGATE and deleted at P4 — see DELEGATE-SURFACE.md.
 *
 * Mind consumers (helix, constellation, mini-helix, host radiance-loop)
 * import ONLY what is re-exported here: `ModelHandle`, `ModelCompletionOpts`,
 * `ModelCapabilities`, `ModelHandleImpl`, and the acquire-shim factory
 * `ModelPool` (the retained `acquire/release` contract the mind drives via
 * `setModelPool`).
 */

// ── Retained handle types ──────────────────────────────────────────────────
// Only the retained subset of ../types.js is re-exported. Budget/billing/
// fallback machinery types (BillingModel, BudgetScope, FallbackChain, PoolEvent,
// ModelSlotConfig, ModelPoolConfig, PoolStats, …) are intentionally NOT part of
// the retained surface — they die with the delegate pool at P4.
export type {
  ModelHandle,
  ModelCompletionOpts,
  ModelCapabilities,
} from '../types.js'

// ── Retained handle runtime ────────────────────────────────────────────────
// ModelHandleImpl is the retained completion runtime. Today it calls
// providerInstance.complete() and tracks budget via BudgetManager; at P4 its
// provider calls are retargeted to `mind_complete` / task-agents and the
// budget/fallback tie-ins are stripped. Kept exported here as the retained
// handle impl the retained factory returns.
export { ModelHandleImpl } from '../model-handle.js'

// ── Retained acquire-shim factory ──────────────────────────────────────────
// The mind injects an acquirer via setModelPool() and calls
//   pool.acquire(slot, template, sessionId, override?) -> Promise<ModelHandle>
// Today the injected value is the delegate `ModelPool` class (exported from the
// barrel for the host to construct). The retained surface treats `ModelPool` as
// a type-only acquire-shim contract; at P4 the class is replaced by an
// ohmypi-backed shim satisfying this same acquire/release shape.
export type { ModelPool } from '../index.js'
