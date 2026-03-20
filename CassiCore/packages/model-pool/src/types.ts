/**
 * ModelPool Type Definitions
 *
 * Core type system for the centralized model management system.
 * Integrates with existing BudgetTracker, CostClassifier, and ModelCapabilitiesFetcher.
 *
 * All imports use .js extensions (TypeScript ESM).
 */

import type { CompletionOpts, CompletionChunk, TurnResult, Message } from '../../types/runtime.js'
import type { ILogger, IEventBus } from '../../types/interfaces.js'

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

// Model Slot Configuration

/**
 * Configuration for a single model slot in the pool.
 * Each slot represents a role that can be filled by a specific provider+model.
 */
export interface ModelSlotConfig {
  /** Role this slot fulfills (e.g., "yang", "yin", "executive", "thinker") */
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

/**
 * Fallback chain configuration with trigger conditions.
 * Defines the order of models to try when the primary fails.
 */
export interface FallbackChain {
  /** Name of the slot this chain applies to */
  slotName: string
  /** Ordered list of model configurations to try */
  chain: ModelSlotConfig[]
  /** Events that trigger fallback to next model in chain */
  triggers: Array<
    | 'rate_limit'
    | 'timeout'
    | 'model_unavailable'
    | 'budget_exceeded'
    | 'circuit_open'
    | 'error'
  >
}

// Billing Models

/**
 * Billing model classification for provider+model combinations.
 * Different from CostClassifier ('free' | 'metered' | 'local') - this is more granular.
 */
export enum BillingModel {
  /** Request-based monthly quota (GitHub Copilot) */
  GITHUB_COPILOT = 'github-copilot',
  /** Request-based monthly quota (Alibaba Coding) */
  ALIBABA_CODING = 'alibaba-coding',
  /** Pay-per-token billing (OpenAI, Anthropic, etc.) */
  TOKEN_BASED = 'token-based',
  /** Local models with no billing */
  LOCAL = 'local',
}

// Budget Scopes (hierarchical limits for ModelPool)

/**
 * Budget limits for a scope.
 * Complements existing BudgetTracker (provider-level monthly limits) with
 * ModelPool-specific scoping (per-team, per-session, per-slot).
 */
export interface BudgetLimits {
  /** Maximum number of requests allowed */
  maxRequests?: number
  /** Maximum total tokens (input + output) */
  maxTokens?: number
  /** Maximum input tokens */
  maxInputTokens?: number
  /** Maximum output tokens */
  maxOutputTokens?: number
}

/**
 * Current budget usage within a scope.
 */
export interface BudgetUsage {
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
  limits: BudgetLimits
  /** Current usage */
  used: BudgetUsage
  /** Billing model for this scope */
  billingModel: BillingModel
}

/**
 * Budget tier indicating consumption level.
 */
export type BudgetTier = 'normal' | 'cautious' | 'frugal' | 'critical'

/**
 * Budget warning event data.
 */
export interface BudgetWarning {
  /** Scope that triggered the warning */
  scopeId: string
  /** Budget tier (cautious, frugal, critical) */
  tier: 'cautious' | 'frugal' | 'critical'
  /** Percentage of budget used (0-100) */
  percentUsed: number
  /** Projected exhaustion date based on current burn rate */
  projectedExhaustion?: Date
  /** Warning threshold that was crossed */
  threshold: number
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

// Circuit Breaker State (for PoolEvent integration)

/**
 * Circuit breaker state.
 * Matches the pattern from core/utils/circuit-breaker.ts
 */
export type CircuitState = 'closed' | 'open' | 'half-open'

// Pool Events (discriminated union for IEventBus)

/**
 * ModelPool events for observability and audit trail.
 * Integrates with existing IEventBus system.
 */
export type PoolEvent =
  | {
      /** Model acquired from pool */
      type: 'model:acquired'
      slotName: string
      provider: string
      model: string
      sessionId: string
      timestamp: Date
    }
  | {
      /** Model released back to pool */
      type: 'model:released'
      slotName: string
      provider: string
      model: string
      tokensUsed: number
      sessionId: string
      timestamp: Date
    }
  | {
      /** Budget warning threshold crossed */
      type: 'budget:warning'
      scopeId: string
      percentUsed: number
      projectedExhaustion?: Date
      threshold: number
      timestamp: Date
    }
  | {
      /** Budget limit exceeded */
      type: 'budget:exceeded'
      scopeId: string
      limitType: keyof BudgetLimits
      current: number
      limit: number
      timestamp: Date
    }
  | {
      /** Fallback triggered to next model in chain */
      type: 'fallback:triggered'
      slotName: string
      fromProvider: string
      fromModel: string
      toProvider: string
      toModel: string
      reason: string
      timestamp: Date
    }
  | {
      /** Circuit breaker state changed */
      type: 'circuit:stateChange'
      provider: string
      model?: string
      fromState: CircuitState
      toState: CircuitState
      failureCount?: number
      timestamp: Date
    }
  | {
      /** Rate limit detected */
      type: 'rate_limit:detected'
      provider: string
      model: string
      retryAfterMs?: number
      timestamp: Date
    }

// Pool Configuration

/**
 * Configuration for the ModelPool.
 */
export interface ModelPoolConfig {
  /** Logger instance */
  logger: ILogger
  /** Event bus for emitting pool events */
  eventBus: IEventBus
  /** Default fallback chains for each slot */
  fallbackChains: FallbackChain[]
  /** Budget scopes (hierarchical) */
  budgetScopes: BudgetScope[]
  /** Circuit breaker configuration */
  circuitBreaker?: {
    failureThreshold: number
    resetTimeoutMs: number
    halfOpenMaxAttempts: number
  }
  /** Default timeout for model requests (ms) */
  defaultTimeoutMs: number
  /** Enable detailed audit logging */
  auditEnabled: boolean
  /**
   * Provider IDs to block from registration.
   * Blocked providers are silently filtered out of setProviders() and fallback chains.
   * Use this to prevent expensive providers from being used in high-throughput contexts
   * (e.g., Teams, Lumen) where they would burn through rate limits.
   */
  blockedProviders?: string[]
}

/**
 * Pool statistics for monitoring.
 */
export interface PoolStats {
  /** Total models acquired */
  totalAcquired: number
  /** Total models released */
  totalReleased: number
  /** Total fallbacks triggered */
  totalFallbacks: number
  /** Current models in use */
  activeModels: number
  /** Budget usage by scope */
  budgetUsage: Record<string, BudgetUsage>
  /** Circuit breaker states by provider */
  circuitStates: Record<string, CircuitState>
}
