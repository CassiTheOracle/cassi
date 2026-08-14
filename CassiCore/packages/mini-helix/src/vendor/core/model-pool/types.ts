/**
 * VENDORED TYPE STUB — mirrors `model-pool/types.js`. Surface: `ModelHandle`,
 * `ModelCompletionOpts` (both TYPE-ONLY for the mini-helix package; mini-helix
 * acquires handles via `handleFactory` and uses `stream`/`release`/reads
 * `provider`/`model`). Self-contained: supporting ModelCapabilities/BudgetScope
 * types inlined locally (faithful to the D: originals); foundation types
 * (`CompletionOpts`, `Message`, `TurnResult`, `CompletionChunk`) come from
 * `@cassicore/foundation`. Re-point to `@cassicore/model-pool` at P6.
 */
import type { CompletionOpts, CompletionChunk, TurnResult, Message } from '@cassicore/foundation'

// Model Capabilities (aligned with existing ModelCapabilitiesFetcher)

/**
 * Model capabilities - extends existing pattern with cost tier information.
 * Field names match core/intelligence/triad-team/model-capabilities.ts exactly.
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

// Budget Scopes (hierarchical limits for ModelPool)

/**
 * Hierarchical budget scope for ModelPool.
 * Scopes can be nested (team → session → slot) with inherited limits.
 */
export interface BudgetScope {
  /** Unique identifier for this scope */
  id: string
  /** Parent scope ID (for hierarchical limits) */
  parentId?: string
  /** Human-readable name */
  name: string
  /** Scope type */
  type: 'team' | 'session' | 'slot' | 'provider'
  /** Budget limits for this scope */
  limits: {
    /** Maximum number of requests allowed */
    maxRequests?: number
    /** Maximum total tokens (input + output) */
    maxTokens?: number
    /** Maximum input tokens */
    maxInputTokens?: number
    /** Maximum output tokens */
    maxOutputTokens?: number
  }
  /** Current usage */
  used: {
    /** Number of requests made */
    requests: number
    /** Total tokens consumed */
    tokens: number
    /** Input tokens consumed */
    inputTokens: number
    /** Output tokens consumed */
    outputTokens: number
    /** When the budget resets (for monthly/periodic budgets) */
    resetAt?: Date
    /** When this usage snapshot was taken */
    lastUpdated: Date
  }
  /** Billing model for this scope */
  billingModel: 'github-copilot' | 'alibaba-coding' | 'token-based' | 'local'
}

// Model Handle (lightweight model reference with lifecycle)

/**
 * Options for completing a request with a model.
 */
export interface ModelCompletionOpts extends CompletionOpts {
  /** Optional timeout override */
  timeoutMs?: number
  /** Optional retry configuration */
  retryCount?: number
}

/**
 * Lightweight handle to an acquired model from the pool.
 * Supports disposable pattern for cleanup.
 */
export interface ModelHandle {
  /** Provider ID */
  provider: string
  /** Model ID */
  model: string
  /** Model capabilities */
  capabilities: ModelCapabilities
  /** Optional budget scope for tracking usage */
  budgetScope?: BudgetScope
  /** Execute a completion request (aggregated — waits for full response) */
  complete(messages: Message[], opts: ModelCompletionOpts): Promise<TurnResult>
  /** Stream a completion request (yields chunks for agentic tool loops) */
  stream(messages: Message[], opts: ModelCompletionOpts): AsyncIterable<CompletionChunk>
  /** Release the model back to the pool (explicit cleanup) */
  release(): void
  /** Symbol.dispose for automatic cleanup with using keyword */
  [Symbol.dispose](): void
}
