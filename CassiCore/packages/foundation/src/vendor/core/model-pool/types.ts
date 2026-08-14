/**
 * VENDOR TYPE STUB — `core/model-pool/types.ts`
 *
 * Type-only placeholder for the ModelPool type surface consumed by the P1 live-set
 * (`types/cassi-agent.ts`). Self-contained; builtin types only; no runtime. Re-pointed to
 * `@cassicore/model-pool` at P6, then deleted.
 */

/** Lightweight handle to an acquired model from the pool (type surface only). */
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

/** A model configuration as referenced through the pool. */
export interface ModelConfig {
  /** Role this configuration fills */
  role: string
  /** Provider ID (e.g., "github-copilot", "openai") */
  provider: string
  /** Model ID (e.g., "gpt-4o", "gpt-5-mini") */
  model: string
  /** Priority within fallback chain (higher = preferred) */
  priority: number
  /** Optional budget scope ID for this slot */
  budgetScopeId?: string
}

/** Model capabilities (type surface). */
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

/** Hierarchical budget scope (type surface). */
export interface BudgetScope {
  /** Unique identifier for this scope */
  id: string
  /** Parent scope ID (for hierarchical limits) */
  parentId?: string
  /** Human-readable name */
  name: string
  /** Scope type */
  type: 'team' | 'session' | 'slot' | 'provider'
}

/** A single message in a completion exchange. */
export interface Message {
  role: 'system' | 'user' | 'assistant'
  content: string
}

/** Options for completing a request with a model. */
export interface CompletionOpts {
  /** Maximum tokens the model may output */
  maxTokens?: number
  /** Temperature override */
  temperature?: number
}

/** Options for completing a request with a model, plus pool overrides. */
export interface ModelCompletionOpts extends CompletionOpts {
  /** Optional timeout override */
  timeoutMs?: number
  /** Optional retry configuration */
  retryCount?: number
}

/** A full turn result. */
export interface TurnResult {
  content: string
  usage?: { inputTokens: number; outputTokens: number }
  sessionId?: string
}

/** A streaming completion chunk. */
export interface CompletionChunk {
  type: 'content' | 'tool_use' | 'done'
  text?: string
  toolCall?: { id: string; name: string; input: Record<string, unknown> }
}
