/**
 * VENDOR TYPE STUB — core/model-pool/types.ts
 * Faithful type surface for helix consumers (ModelHandle). No runtime.
 * Re-pointed to `@cassicore/model-pool` at P6; delete this stub then.
 * Only foundation + builtin types; self-contained.
 */
import type { Message, CompletionOpts, CompletionChunk, TurnResult } from '@cassicore/foundation'

/** Model capabilities exposed by a pooled model handle. */
export interface ModelCapabilities {
  contextWindow: number
  maxOutputTokens: number
  supportsStreaming: boolean
  supportsToolUse: boolean
  supportsStructuredOutput?: boolean
  modalities?: Array<'text' | 'image' | 'audio'>
  /** Extra capability flags the pool may carry. */
  [key: string]: unknown
}

/** Financial/budget limits for a hierarchical budget scope. */
export interface BudgetLimits {
  maxCost: number
  maxTokens: number
  periodMs?: number
}

/** Encapsulates usage totals for a budget scope. */
export interface BudgetUsage {
  cost: number
  tokens: number
}

/** A named budget scope tracking usage hierarchical against limits. */
export interface BudgetScope {
  id: string
  name: string
  type: 'team' | 'session' | 'slot' | 'provider'
  parentId?: string
  limits: BudgetLimits
  usage: BudgetUsage
  consume(cost: number, tokens: number): void
  remaining(): { cost: number; tokens: number }
}

/** Billing model classification. */
export enum BillingModel {
  METERED = 'metered',
  SUBSCRIPTION = 'subscription',
  BYOK = 'byok',
}

/** Completion options for a pooled model handle. */
export interface ModelCompletionOpts extends CompletionOpts {
  /** Optional timeout override. */
  timeoutMs?: number
  /** Optional retry configuration. */
  retryCount?: number
}

/**
 * A model handle leased from the pool. Helix obtains these via
 * `ModelPool.acquire(...)` and drives them with complete/stream.
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
  /** Execute a completion request (aggregated — waits for full response). */
  complete(messages: Message[], opts: ModelCompletionOpts): Promise<TurnResult>
  /** Stream a completion request (yields chunks for agentic tool loops). */
  stream(messages: Message[], opts: ModelCompletionOpts): AsyncIterable<CompletionChunk>
  /** Release the model back to the pool (explicit cleanup). */
  release(): void
  /** Symbol.dispose for automatic cleanup with `using` keyword. */
  [Symbol.dispose](): void
}
