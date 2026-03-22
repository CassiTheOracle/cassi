/**
 * ModelPool - Centralized Model Management
 *
 * Main orchestrator for the ModelPool system.
 */

import type { IProvider, TurnResult } from '../../types/runtime.js'
import type { ILogger, IEventBus } from '../../types/interfaces.js'
import type {
  FallbackChain,
  BudgetLimits,
  BudgetScope,
  ModelCapabilities,
  ModelHandle,
  PoolStats,
  ModelPoolConfig,
  BudgetUsage,
  CircuitState,
} from './types.js'
import { BillingModel } from './types.js'
import { FallbackManager } from './fallback-manager.js'
import { BudgetManager } from './budget-manager.js'
import { CapabilityCache } from './capability-cache.js'
import { ModelHandleImpl } from './model-handle.js'
import { ModelCapabilitiesFetcher } from '../intelligence/triad-team/model-capabilities.js'

/**
 * ModelPool - Central orchestrator for model management.
 */
export class ModelPool {
  private readonly fallbackManager: FallbackManager
  private readonly budgetManager: BudgetManager
  private readonly capabilityCache: CapabilityCache
  private readonly logger: ILogger
  private readonly eventBus: IEventBus
  private readonly config: ModelPoolConfig
  private readonly activeHandles: Map<string, ModelHandleImpl>
  private readonly providers: Map<string, IProvider>
  private totalAcquiredCount = 0
  private totalReleasedCount = 0
  private totalFallbackCount = 0
  private handleSeq = 0
  private disposed = false

  constructor(config: ModelPoolConfig) {
    this.logger = config.logger.child('ModelPool')
    this.eventBus = config.eventBus
    this.config = config
    this.activeHandles = new Map()
    this.providers = new Map()

    // Initialize FallbackManager
    this.fallbackManager = new FallbackManager({
      chains: config.fallbackChains,
      circuitBreakerConfig: config.circuitBreaker,
      successResetThreshold: 3,
      logger: this.logger.child('FallbackManager'),
      eventBus: this.eventBus,
    })

    // Initialize BudgetManager
    this.budgetManager = new BudgetManager(this.eventBus, this.logger)

    // Initialize CapabilityCache
    const fetcher = new ModelCapabilitiesFetcher(this.logger)
    this.capabilityCache = new CapabilityCache(
      this.logger.child('CapabilityCache'),
      fetcher,
      100,
      10 * 60 * 1000,
    )

    // Pre-load budget scopes
    for (const scope of config.budgetScopes) {
      this.budgetManager.createScope(
        scope.id,
        scope.name,
        scope.type,
        scope.limits,
        scope.billingModel,
        scope.parentId,
      )
    }

    this.logger.info('ModelPool initialized', {
      fallbackChainCount: config.fallbackChains.length,
      budgetScopeCount: config.budgetScopes.length,
      slots: config.fallbackChains.map((c) => c.slotName),
    })
  }

  /**
   * Set provider instances.
   * Blocked providers (from config.blockedProviders) are silently filtered out.
   */
  setProviders(providers: Map<string, IProvider>): void {
    this.providers.clear()
    const blocked = this.config.blockedProviders ?? []
    for (const [id, provider] of providers.entries()) {
      if (blocked.includes(id)) {
        this.logger.warn('Provider blocked by ModelPool config', { providerId: id })
        continue
      }
      this.providers.set(id, provider)
    }
    this.logger.info('Providers set', { count: this.providers.size, blocked: blocked.length > 0 ? blocked : undefined })
  }

  /**
   * Acquire a model handle for a given slot.
   * Tries models in the fallback chain until a working one is found.
   * If `override` is provided, bypasses the fallback chain entirely and
   * goes directly to the specified provider+model.
   */
  async acquire(
    slotName: string,
    template?: string,
    sessionId?: string,
    override?: { provider: string; model: string },
  ): Promise<ModelHandle> {
    if (this.disposed) {
      this.logger.warn('acquire() called on disposed ModelPool')
      throw new Error('ModelPool has been disposed')
    }

    this.logger.debug('Acquiring model', { slotName, template, sessionId, override: override ? `${override.provider}/${override.model}` : undefined })

    if (override) {
      const providerInstance = this.providers.get(override.provider)
      if (!providerInstance) {
        throw new Error(
          `ModelDirective override failed: provider "${override.provider}" not found. ` +
          `Available: ${Array.from(this.providers.keys()).join(', ')}`,
        )
      }

      // Check per-provider model allowlist
      const allowlist = this.config.allowedModels?.[override.provider]
      if (allowlist && !allowlist.includes(override.model)) {
        throw new Error(
          `ModelDirective override failed: model "${override.model}" is not in the allowlist for provider "${override.provider}". ` +
          `Allowed models: ${allowlist.join(', ')}`,
        )
      }

      // Validate model is available for this provider
      if (providerInstance.models && providerInstance.models.length > 0 && !providerInstance.models.includes(override.model)) {
        throw new Error(
          `ModelDirective override failed: model "${override.model}" not available for provider "${override.provider}". ` +
          `Available models: ${providerInstance.models.join(', ')}`,
        )
      }

      const capabilities = await this.capabilityCache.getCapabilities(
        override.provider,
        override.model,
        providerInstance,
      )

      let budgetScopeId: string | undefined
      if (sessionId) {
        budgetScopeId = `session:${sessionId}:${slotName}`
      }

      const handle = new ModelHandleImpl(
        override.provider,
        override.model,
        capabilities,
        providerInstance,
        this.budgetManager,
        budgetScopeId,
        this.logger,
        slotName,
        (h) => this.release(h),
        this.fallbackManager,
      )

      const handleId = `${slotName}:${override.provider}:${override.model}:${++this.handleSeq}`
      this.activeHandles.set(handleId, handle)
      this.totalAcquiredCount++

      this.logger.info('Model acquired via directive override', {
        handleId,
        slotName,
        provider: override.provider,
        model: override.model,
      })

      return handle
    }


    // Try models in the fallback chain until we find a working one
    let slotConfig = this.fallbackManager.getNextAvailable(slotName)
    let attempts = 0
    const maxAttempts = 10 // Prevent infinite loops

    while (slotConfig && attempts < maxAttempts) {
      attempts++

      // Get provider instance
      const providerInstance = this.providers.get(slotConfig.provider)
      if (!providerInstance) {
        this.logger.warn('Provider not found, trying next in chain', { provider: slotConfig.provider })
        this.fallbackManager.reportFailure(
          slotName,
          slotConfig.provider,
          slotConfig.model,
          'model_unavailable',
        )
        slotConfig = this.fallbackManager.getNextAvailable(slotName)
        continue
      }

      // Check per-provider model allowlist
      const chainAllowlist = this.config.allowedModels?.[slotConfig.provider]
      if (chainAllowlist && !chainAllowlist.includes(slotConfig.model)) {
        this.logger.warn('Model not in allowlist for provider, trying next in chain', {
          provider: slotConfig.provider,
          model: slotConfig.model,
          allowed: chainAllowlist,
        })
        this.fallbackManager.reportFailure(
          slotName,
          slotConfig.provider,
          slotConfig.model,
          'model_unavailable',
        )
        slotConfig = this.fallbackManager.getNextAvailable(slotName)
        continue
      }

      // Soft ping — log on failure but don't fail acquisition.
      // Many providers (Alibaba, Kimi) don't expose /models endpoint,
      // so a failed ping doesn't mean the provider can't serve completions.
      try {
        const pingResult = await providerInstance.ping()
        if (!pingResult) {
          this.logger.debug('Provider ping returned false (may not support /models endpoint)', { provider: slotConfig.provider })
        }
      } catch (pingError) {
        this.logger.debug('Provider ping error (non-fatal, continuing)', { 
          provider: slotConfig?.provider,
          error: pingError instanceof Error ? pingError.message : String(pingError)
        })
      }

      if (!slotConfig) {
        throw new Error(`No available model for slot "${slotName}" - all providers in chain failed`)
      }

      // Provider is working, proceed with acquisition
      break
    }

    if (!slotConfig) {
      const error = new Error(`No available models in fallback chain for slot: ${slotName}`)
      this.logger.error('Fallback chain exhausted', { slotName })
      throw error
    }

    // Get provider instance (we already verified it exists)
    const providerInstance = this.providers.get(slotConfig.provider)!

    // Get model capabilities
    const capabilities = await this.capabilityCache.getCapabilities(
      slotConfig.provider,
      slotConfig.model,
      providerInstance,
    )

    // Determine budget scope
    let budgetScopeId = slotConfig.budgetScopeId
    if (!budgetScopeId && sessionId) {
      budgetScopeId = `session:${sessionId}:${slotName}`
    }

    // Check budget if scope exists (warnings only — never block requests)
    if (budgetScopeId) {
      const status = this.budgetManager.checkBudget(budgetScopeId)

      if (!status.allowed) {
        this.logger.warn('Budget exceeded — continuing execution (tracking only)', {
          scopeId: budgetScopeId,
          reason: status.reason,
        })
      }

      // Emit warnings
      for (const warning of status.warnings) {
        this.logger.warn('Budget warning', {
          scopeId: warning.scopeId,
          percentUsed: warning.percentUsed,
          threshold: warning.threshold,
        })
      }
    }

    // Track if we had to fallback
    if (attempts > 1) {
      this.totalFallbackCount++
      this.logger.info('Fallback triggered', {
        slotName,
        attempts,
        finalProvider: slotConfig.provider,
        finalModel: slotConfig.model,
      })

      // Emit fallback event
      this.eventBus.emit({
        type: 'fallback:triggered',
        slotName,
        fromProvider: null,
        fromModel: null,
        toProvider: slotConfig.provider,
        toModel: slotConfig.model,
        reason: 'provider_failed',
        chainExhausted: attempts >= maxAttempts,
        timestamp: new Date(),
      })
    }

    // Create model handle
    const handle = new ModelHandleImpl(
      slotConfig.provider,
      slotConfig.model,
      capabilities,
      providerInstance,
      this.budgetManager,
      budgetScopeId,
      this.logger,
      slotName,
      (h) => this.release(h),
      this.fallbackManager, // Pass fallback manager for auto-reporting failures
    )

    // Track active handle
    const handleId = `${slotName}:${slotConfig.provider}:${slotConfig.model}:${++this.handleSeq}`
    this.activeHandles.set(handleId, handle)
    this.totalAcquiredCount++

    this.logger.info('Model acquired', {
      handleId,
      slotName,
      provider: slotConfig.provider,
      model: slotConfig.model,
    })

    // Emit acquisition event
    this.eventBus.emit({
      type: 'model:acquired',
      slotName,
      provider: slotConfig.provider,
      model: slotConfig.model,
      sessionId: sessionId ?? '',
      timestamp: new Date(),
    })

    return handle
  }

  /**
   * Release a model handle back to the pool.
   */
  release(handle: ModelHandleImpl): void {
    if (this.disposed) {
      this.logger.warn('release() called on disposed ModelPool')
      return
    }

    // Find and remove from active handles
    let handleId: string | undefined
    for (const [id, h] of this.activeHandles.entries()) {
      if (h === handle) {
        handleId = id
        break
      }
    }

    if (handleId) {
      this.activeHandles.delete(handleId)
    }

    // Get stats before release
    const stats = handle.getStats()
    this.totalReleasedCount++

    this.logger.info('Model released', {
      handleId,
      provider: handle.provider,
      model: handle.model,
      totalTokens: stats.totalTokens,
      requestCount: stats.requestCount,
    })

    // Report success to fallback manager
    this.fallbackManager.reportSuccess(handle.slotName, handle.provider, handle.model)

    // Emit release event
    this.eventBus.emit({
      type: 'model:released',
      slotName: handle.slotName,
      provider: handle.provider,
      model: handle.model,
      tokensUsed: stats.totalTokens,
      sessionId: '',
      timestamp: new Date(),
    })
  }

  /**
   * Create a budget scope.
   */
  createBudgetScope(
    id: string,
    name: string,
    type: 'team' | 'session' | 'slot' | 'provider',
    limits: BudgetLimits,
    billingModel: BillingModel,
    parentId?: string,
  ): BudgetScope {
    if (this.disposed) {
      this.logger.warn('createBudgetScope() called on disposed ModelPool')
      throw new Error('ModelPool has been disposed')
    }

    return this.budgetManager.createScope(id, name, type, limits, billingModel, parentId)
  }

  /**
   * Get statistics about the pool.
   */
  getStats(): PoolStats {
    const budgetUsage: Record<string, BudgetUsage> = {}
    const circuitStates: Record<string, CircuitState> = {}
    const activeHandleCount = this.activeHandles.size

    return {
      totalAcquired: this.totalAcquiredCount,
      totalReleased: this.totalReleasedCount,
      totalFallbacks: this.totalFallbackCount,
      activeModels: activeHandleCount,
      budgetUsage,
      circuitStates,
    }
  }

  /**
   * Manually report a failure for a specific slot/provider/model combination.
   * Triggers fallback chains so the next acquire() skips the failed provider.
   */
  reportFailure(slotName: string, provider: string, model: string, trigger: 'rate_limit' | 'timeout' | 'model_unavailable' | 'budget_exceeded' | 'circuit_open' | 'error'): void {
    this.fallbackManager.reportFailure(slotName, provider, model, trigger)
  }

  /**
   * Dispose of the ModelPool and clean up resources.
   */
  dispose(): void {
    if (this.disposed) {
      return
    }

    this.disposed = true
    this.logger.info('ModelPool disposed', {
      activeHandles: this.activeHandles.size,
    })

    // Release all active handles
    for (const handle of this.activeHandles.values()) {
      handle.release()
    }

    this.activeHandles.clear()
  }
}
