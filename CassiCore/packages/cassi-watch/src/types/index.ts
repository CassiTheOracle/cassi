/**
 * Type definitions for cassi-watch — LLM call streaming viewer
 */

/** Represents a single LLM call/invocation */
export interface LLMCall {
  /** Unique identifier for this call */
  id: string
  /** Timestamp when the call started (Unix ms) */
  timestamp: number
  /** Provider name (e.g., "anthropic", "openai", "qwen") */
  provider: string
  /** Model name (e.g., "haiku", "gpt-4", "qwen-max") */
  model: string
  /** Session ID this call belongs to */
  sessionId: string
  /** Call status */
  status: LLMCallStatus
  /** Latency in milliseconds (null if pending) */
  latencyMs: number | null
  /** Token usage */
  tokens: TokenUsage | null
  /** Error message if failed */
  error: string | null
  /** Partial output preview (first 100 chars) */
  outputPreview: string | null
  /** Request ID from provider */
  requestId: string
}

export type LLMCallStatus = 'pending' | 'success' | 'error' | 'cancelled'

export interface TokenUsage {
  input: number
  output: number
  total: number
}

/** Filter configuration */
export interface WatchFilters {
  /** Filter by provider (exact match or substring) */
  provider: string | null
  /** Filter by model (exact match or substring) */
  model: string | null
  /** Filter by status */
  status: LLMCallStatus | null
  /** Filter by session ID (substring match) */
  sessionId: string | null
  /** Minimum latency threshold (ms) */
  minLatency: number | null
  /** Maximum latency threshold (ms) */
  maxLatency: number | null
  /** Only show calls with errors */
  errorsOnly: boolean
}

/** Summary statistics */
export interface WatchStats {
  /** Total calls in view */
  totalCalls: number
  /** Calls by status */
  byStatus: Record<LLMCallStatus, number>
  /** Calls by provider */
  byProvider: Record<string, number>
  /** Calls by model */
  byModel: Record<string, number>
  /** Average latency (ms) for completed calls */
  avgLatencyMs: number | null
  /** Error rate (0-1) */
  errorRate: number
  /** Total tokens used */
  totalTokens: number
  /** Calls per minute (estimated) */
  callsPerMinute: number
}

/** SSE event types from the daemon */
export interface ProviderStartEvent {
  providerId: string
  requestId: string
  sessionId: string
  model: string
  messageCount: number
  timestamp: number
}

export interface ProviderEndEvent {
  providerId: string
  requestId: string
  sessionId: string
  tokensUsed: number
  durationMs: number
  error: string | null
  timestamp: number
}

export interface ProviderErrorEvent {
  providerId: string
  requestId: string
  sessionId: string
  error: string
  consecutiveErrors: number
  timestamp: number
}

/** Union type for all SSE events */
export type WatchEvent =
  | { type: 'provider:request_start'; data: ProviderStartEvent }
  | { type: 'provider:request_end'; data: ProviderEndEvent }
  | { type: 'provider:request_error'; data: ProviderErrorEvent }
  | { type: 'provider:request_timeout'; data: ProviderEndEvent }
  | { type: 'connected'; data: { message: string } }
  | { type: 'ping'; data: { message: string } }

/** Display configuration */
export interface DisplayConfig {
  /** Number of calls to display in the main view */
  maxDisplayCalls: number
  /** Refresh rate for stats (ms) */
  statsRefreshMs: number
  /** Show output preview in call cards */
  showOutputPreview: boolean
  /** Show token details */
  showTokenDetails: boolean
}

export const DEFAULT_DISPLAY_CONFIG: DisplayConfig = {
  maxDisplayCalls: 50,
  statsRefreshMs: 1000,
  showOutputPreview: true,
  showTokenDetails: true,
}

export const DEFAULT_FILTERS: WatchFilters = {
  provider: null,
  model: null,
  status: null,
  sessionId: null,
  minLatency: null,
  maxLatency: null,
  errorsOnly: false,
}
