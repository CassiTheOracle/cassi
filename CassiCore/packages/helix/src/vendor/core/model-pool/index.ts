/**
 * VENDOR TYPE STUB — core/model-pool/index.ts
 * Faithful type surface for helix consumers (ModelPool class). No runtime.
 * Re-pointed to `@cassicore/model-pool` at P6; delete this stub then.
 * Only foundation + sibling model-pool/types + builtin types; self-contained.
 */
import type { ILogger, IEventBus, IProvider } from '@cassicore/foundation'
import type { ModelHandle, BudgetScope, BudgetLimits, BillingModel } from './types.js'

/** Pool statistics snapshot. */
export interface PoolStats {
  totalHandles: number
  activeHandles: number
  availableCount: number
  [key: string]: unknown
}

/** Configuration for a model pool. */
export interface ModelPoolConfig {
  logger: ILogger
  eventBus: IEventBus
  fallbackChains: unknown[]
  budgetScopes: BudgetScope[]
  circuitBreaker?: {
    failureThreshold: number
    resetTimeoutMs: number
    halfOpenMaxAttempts: number
  }
  defaultTimeoutMs: number
  auditEnabled: boolean
  blockedProviders?: string[]
  allowedModels?: Record<string, string[]>
}

/**
 * Capacity/fallback manager over the provider set. Helix acquires a
 * per-posture `ModelHandle` via `acquire(slotName, template, sessionId, override)`.
 */
export class ModelPool {
  constructor(config: ModelPoolConfig) {
    void config
  }

  setProviders(providers: Map<string, IProvider>): void {
    void providers
  }

  async acquire(
    slotName: string,
    template?: string,
    sessionId?: string,
    override?: { provider: string; model: string },
  ): Promise<ModelHandle> {
    void slotName
    void template
    void sessionId
    void override
    throw new Error('not connected (lands at P6 @cassicore/model-pool)')
  }

  release(handle: ModelHandle): void {
    void handle
  }

  createBudgetScope(
    id: string,
    name: string,
    type: 'team' | 'session' | 'slot' | 'provider',
    limits: BudgetLimits,
    billingModel: BillingModel,
    parentId?: string,
  ): BudgetScope {
    void id
    void name
    void type
    void limits
    void billingModel
    void parentId
    throw new Error('not connected (lands at P6 @cassicore/model-pool)')
  }

  getStats(): PoolStats {
    return {} as PoolStats
  }

  reportFailure(
    slotName: string,
    provider: string,
    model: string,
    trigger: 'rate_limit' | 'timeout' | 'model_unavailable' | 'budget_exceeded' | 'circuit_open' | 'error',
  ): void {
    void slotName
    void provider
    void model
    void trigger
  }

  dispose(): void {
    // no-op
  }
}
