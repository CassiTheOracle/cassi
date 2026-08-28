/**
 * @cassicore/model-pool — RETAINED PORT SURFACE (CASSICORE-FOCUS §19 / §6 P4)
 *
 * The mind-facing seam that survives P4. In the focused shape, ohmypi owns
 * providers + routing; the retained `ModelHandle` is the *mind's cast* over
 * an ohmypi completion (via `mind_complete` / task-agent subagents). This
 * ports/ module is the canonical retained surface; the pool machinery it
 * does NOT re-export (FallbackManager, BudgetManager, CapabilityCache,
 * billing-models, rate-limit/blocked/allowlist wiring, the provider-map
 * pool, ModelPoolConfig/PoolStats) was DELETED at P4 — see DELEGATE-SURFACE.md.
 *
 * Mind consumers (helix, constellation, mini-helix, host radiance-loop)
 * import ONLY what is re-exported here: `ModelHandle`, `ModelCompletionOpts`,
 * `ModelCapabilities`, `ModelHandleImpl`, and the acquire-shim factory type
 * `ModelPool` (the retained `acquire/release` contract the mind drives via
 * `setModelPool`). The P4 host builds the acquirer with
 * `createMindCompleteAcquirer({ transport, logger })`.
 */

// ── Retained handle types ──────────────────────────────────────────────────
// Only the retained subset of ../types.js is re-exported. Budget/billing/
// fallback machinery types were deleted at P4 with the delegate pool.
export type {
  ModelHandle,
  ModelCompletionOpts,
  ModelCapabilities,
} from '../types.js'

// ── Retained handle runtime ────────────────────────────────────────────────
// ModelHandleImpl is the retained completion runtime, now retargeted to an
// injected `mind_complete` transport (ohmypi owns providers/routing). Budget
// and fallback tie-ins were stripped at P4.
export { ModelHandleImpl } from '../model-handle.js'

// ── Retained acquire-shim factory ──────────────────────────────────────────
// The mind injects an acquirer via setModelPool() and calls
//   pool.acquire(slot, template, sessionId, override?) -> Promise<ModelHandle>
// At P4 the delegate `ModelPool` class was replaced by `createMindCompleteAcquirer`
// (an ohmypi-backed shim satisfying this same acquire/release shape). The
// retained surface treats `ModelPool` as a type-only acquire-shim contract.
export type { ModelPool } from '../index.js'
