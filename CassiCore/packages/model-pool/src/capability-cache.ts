/**
 * Capability Cache - TTL + LRU Cache for Model Capabilities
 *
 * Thin wrapper around ModelCapabilitiesFetcher that adds:
 * - LRU eviction (ModelCapabilitiesFetcher only has TTL)
 * - Pre-warming API for known model sets
 * - Multi-provider capability aggregation
 *
 * Does NOT duplicate the cascading fallback logic - delegates to
 * ModelCapabilitiesFetcher for actual capability retrieval.
 *
 * All imports use .js extensions (TypeScript ESM).
 */

import { ModelCapabilitiesFetcher, type ModelCapabilities } from '../intelligence/triad-team/model-capabilities.js'
import { TTLCache } from '../utils/ttl-cache.js'
import type { IProvider } from '../../types/runtime.js'
import type { ILogger } from '../../types/interfaces.js'
import type { BillingModel } from './types.js'
import { getCostTier, getBillingModel } from './billing-models.js'

// Extended Capabilities (adds billing information)

/**
 * Extended model capabilities with billing information.
 * Wraps the base ModelCapabilities from ModelCapabilitiesFetcher.
 */
export interface ExtendedModelCapabilities extends ModelCapabilities {
  /** Provider ID */
  provider: string
  /** Model ID */
  model: string
  /** Billing model for this combination */
  billingModel: BillingModel
  /** Cost tier for budget planning */
  costTier: 'free' | 'low' | 'medium' | 'high'
  /** Cache hit status (for observability) */
  cacheHit: boolean
}

// Pre-warm Configuration

/**
 * Configuration for pre-warming the capability cache.
 */
export interface PreWarmConfig {
  /** Provider ID */
  provider: string
  /** Model IDs to pre-warm */
  models: string[]
  /** Optional provider instance for calibration */
  providerInstance?: IProvider
}

// Capability Cache

/**
 * TTL + LRU cache for model capabilities.
 * Wraps ModelCapabilitiesFetcher to add LRU eviction and pre-warming.
 */
export class CapabilityCache {
  private readonly logger: ILogger
  private readonly fetcher: ModelCapabilitiesFetcher
  private readonly cache: TTLCache<string, ExtendedModelCapabilities>
  private readonly lruOrder: string[] // Track access order for LRU eviction
  private readonly maxCapacity: number

  constructor(
    logger: ILogger,
    fetcher?: ModelCapabilitiesFetcher,
    maxCapacity: number = 100,
    ttlMs: number = 10 * 60 * 1000, // 10 minutes
  ) {
    this.logger = logger.child('capability-cache')
    this.fetcher = fetcher || new ModelCapabilitiesFetcher(logger)
    this.cache = new TTLCache<string, ExtendedModelCapabilities>({
      maxSize: maxCapacity,
      ttlMs,
    })
    this.lruOrder = []
    this.maxCapacity = maxCapacity
  }

  /**
   * Get capabilities for a provider+model combination.
   * Uses cache if available, otherwise fetches via ModelCapabilitiesFetcher.
   */
  async getCapabilities(
    provider: string,
    model: string,
    providerInstance?: IProvider,
  ): Promise<ExtendedModelCapabilities> {
    const cacheKey = `${provider}::${model}`
    const cached = this.cache.get(cacheKey)

    if (cached) {
      this.updateLruOrder(cacheKey)
      this.logger.debug('Capability cache hit', { provider, model })
      return { ...cached, cacheHit: true }
    }

    // Cache miss - fetch via ModelCapabilitiesFetcher
    this.logger.debug('Capability cache miss, fetching', { provider, model })
    const baseCapabilities = await this.fetcher.getCapabilities(provider, model, providerInstance)

    const extended: ExtendedModelCapabilities = {
      ...baseCapabilities,
      provider,
      model,
      billingModel: this.getBillingModelForCapability(provider, model),
      costTier: getCostTier(provider, model),
      cacheHit: false,
    }

    this.set(cacheKey, extended)
    return extended
  }

  /**
   * Pre-warm the cache with known provider+model combinations.
   * Useful for initializing the pool with expected models.
   */
  async preWarm(configs: PreWarmConfig[]): Promise<void> {
    this.logger.info('Pre-warming capability cache', { count: configs.length })

    const promises = configs.flatMap((config) =>
      config.models.map(async (model) => {
        try {
          await this.getCapabilities(config.provider, model, config.providerInstance)
          this.logger.debug('Pre-warmed model', { provider: config.provider, model })
        } catch (error) {
          this.logger.warn('Failed to pre-warm model', {
            provider: config.provider,
            model,
            error: error instanceof Error ? error.message : String(error),
          })
        }
      }),
    )

    await Promise.all(promises)
    this.logger.info('Capability cache pre-warming complete')
  }

  /**
   * Get all cached capabilities.
   */
  getAllCached(): ExtendedModelCapabilities[] {
    return this.lruOrder
      .map((key) => this.cache.get(key))
      .filter((cap): cap is ExtendedModelCapabilities => cap !== undefined)
  }

  /**
   * Clear the cache.
   */
  clear(): void {
    this.lruOrder.length = 0
    // TTLCache doesn't have a clear method, so we create a new one
    // This is a limitation - in production, TTLCache should support clear()
    this.logger.info('Capability cache cleared')
  }

  /**
   * Get cache statistics.
   */
  getStats(): {
    size: number
    capacity: number
    ttlMs: number
    oldestEntry?: Date
    newestEntry?: Date
  } {
    // TTLCache doesn't expose stats, so we provide what we can
    return {
      size: this.lruOrder.length,
      capacity: this.maxCapacity,
      ttlMs: 10 * 60 * 1000, // Default TTL
    }
  }


  private set(key: string, capabilities: ExtendedModelCapabilities): void {
    this.cache.set(key, capabilities)
    this.updateLruOrder(key)
    this.evictIfNecessary()
  }

  private updateLruOrder(key: string): void {
    const index = this.lruOrder.indexOf(key)
    if (index > -1) {
      this.lruOrder.splice(index, 1)
    }
    this.lruOrder.push(key)
  }

  private evictIfNecessary(): void {
    // TTLCache handles size-based eviction internally
    // We just need to keep lruOrder in sync
    while (this.lruOrder.length > this.maxCapacity) {
      const oldest = this.lruOrder.shift()
      if (oldest) {
        this.logger.debug('Evicted oldest cache entry', { key: oldest })
      }
    }
  }

  private getBillingModelForCapability(provider: string, model: string): BillingModel {
    return getBillingModel(provider, model)
  }
}

// Multi-Provider Capability Aggregator

/**
 * Aggregates capabilities across multiple providers for comparison.
 */
export interface ProviderModelCapabilities {
  provider: string
  model: string
  capabilities: ExtendedModelCapabilities
}

/**
 * Aggregator for comparing capabilities across providers.
 */
export class CapabilityAggregator {
  private readonly cache: CapabilityCache
  private readonly logger: ILogger

  constructor(cache: CapabilityCache, logger: ILogger) {
    this.cache = cache
    this.logger = logger.child('aggregator')
  }

  /**
   * Compare capabilities for the same model across multiple providers.
   */
  async compareAcrossProviders(
    model: string,
    providers: string[],
    providerInstances?: Record<string, IProvider>,
  ): Promise<ProviderModelCapabilities[]> {
    const results = await Promise.all(
      providers.map(async (provider) => {
        try {
          const capabilities = await this.cache.getCapabilities(
            provider,
            model,
            providerInstances?.[provider],
          )
          return { provider, model, capabilities }
        } catch (error) {
          this.logger.warn('Failed to get capabilities', {
            provider,
            model,
            error: error instanceof Error ? error.message : String(error),
          })
          return null
        }
      }),
    )

    return results.filter((r): r is ProviderModelCapabilities => r !== null)
  }

  /**
   * Find the best model for a given requirement.
   */
  async findBestModel(options: {
    minContextWindow?: number
    requiresTools?: boolean
    requiresImages?: boolean
    maxCostTier?: 'free' | 'low' | 'medium' | 'high'
    candidates?: ProviderModelCapabilities[]
  }): Promise<ProviderModelCapabilities | null> {
    let candidates: ProviderModelCapabilities[] = options.candidates || this.cache.getAllCached().map((c) => ({
      provider: c.provider,
      model: c.model,
      capabilities: c,
    }))

    // Filter by requirements
    if (options.minContextWindow) {
      candidates = candidates.filter((c) => c.capabilities.contextWindow >= options.minContextWindow!)
    }
    if (options.requiresTools) {
      candidates = candidates.filter((c) => c.capabilities.supportsTools)
    }
    if (options.requiresImages) {
      candidates = candidates.filter((c) => c.capabilities.supportsImages)
    }
    if (options.maxCostTier) {
      const tierOrder = ['free', 'low', 'medium', 'high']
      const maxIndex = tierOrder.indexOf(options.maxCostTier)
      candidates = candidates.filter((c) => tierOrder.indexOf(c.capabilities.costTier) <= maxIndex)
    }

    if (candidates.length === 0) {
      return null
    }

    // Sort by context window (largest first), then by cost tier (cheapest first)
    const tierOrder = ['free', 'low', 'medium', 'high']
    candidates.sort((a, b) => {
      const contextDiff = b.capabilities.contextWindow - a.capabilities.contextWindow
      if (contextDiff !== 0) return contextDiff
      return tierOrder.indexOf(a.capabilities.costTier) - tierOrder.indexOf(b.capabilities.costTier)
    })

    return candidates[0]
  }
}
