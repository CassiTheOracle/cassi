/**
 * @cassicore/model-pool — RETAINED TYPE SURFACE (CASSICORE-FOCUS §19 / §6 P4)
 *
 * CASSICORE-FOCUS P4 slimmed this module to the retained mind-cast types.
 * Budget / billing / fallback machinery types (BillingModel, BudgetScope,
 * FallbackChain, BudgetLimits, BudgetUsage, CircuitState, PoolEvent,
 * ModelSlotConfig, ModelPoolConfig, PoolStats, …) are DELEGATE surface and
 * were deleted with the pool machinery at P4 — see DELEGATE-SURFACE.md.
 *
 * What survives: the mind's cast over an ohmypi completion —
 * `ModelCapabilities`, `ModelCompletionOpts`, and `ModelHandle` (now without
 * the `budgetScope` field — ohmypi owns quota/budget).
 *
 * All imports use .js extensions (TypeScript ESM).
 */

import type { CompletionOpts, CompletionChunk, TurnResult, Message } from '@cassicore/foundation'

// Model Capabilities (aligned with the retained model-capabilities pattern).

/**
 * Model capabilities — retained with the handle; the retained runtime fills
 * them from the ohmypi provider resolution (or a sensible default when the
 * transport is not yet wired). Field names match
 * core/intelligence/triad-team/model-capabilities.ts exactly.
 */
export interface ModelCapabilities {
  /** Maximum input context window in tokens */
  contextWindow: number
  /** Maximum output tokens the model can generate */
  maxOutputTokens: number
  /** Whether the model supports tool/function calling */
  supportsTools: boolean
  /** Whether the model accepts image inputs */
  supportsImages: boolean
  /** Source of the capabilities data (for observability) */
  source: 'registry' | 'provider-calibration' | 'fallback'
  /** Cost tier for budget planning */
  costTier: 'free' | 'low' | 'medium' | 'high'
}

// Model Completion Options

/**
 * Options for completing a request with a model.
 */
export interface ModelCompletionOpts extends CompletionOpts {
  /** Optional timeout override */
  timeoutMs?: number
  /** Optional retry configuration */
  retryCount?: number
}

// Model Handle (mind's cast over an ohmypi completion)

/**
 * Lightweight handle to an acquired model from the retained acquire-shim.
 * Supports disposable pattern for cleanup.
 *
 * At P4 `complete()`/`stream()` route through the `mind_complete` transport
 * (an injected ohmypi-backed completion) instead of a CassiCore provider.
 * `budgetScope` was removed — ohmypi owns quota/budget.
 */
export interface ModelHandle {
  /** Provider ID */
  provider: string
  /** Model ID */
  model: string
  /** Model capabilities */
  capabilities: ModelCapabilities
  /** Execute a completion request (aggregated — waits for full response) */
  complete(messages: Message[], opts: ModelCompletionOpts): Promise<TurnResult>
  /** Stream a completion request (yields chunks for agentic tool loops) */
  stream(messages: Message[], opts: ModelCompletionOpts): AsyncIterable<CompletionChunk>
  /** Release the model back to the pool (explicit cleanup) */
  release(): void
  /** Symbol.dispose for automatic cleanup with using keyword */
  [Symbol.dispose](): void
}
