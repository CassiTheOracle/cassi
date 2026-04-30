/**
 * ModelCapabilitiesFetcher — Dynamically fetch model context limits.
 *
 * Cascading fallback strategy:
 *   Tier 1: Check @cassicore/ai model registry (models.generated.ts)
 *   Tier 2: Query provider's countTokens() to calibrate
 *   Tier 3: Conservative hardcoded fallback per provider family
 *
 * Results are cached in a TTL map to avoid repeated lookups for the same
 * model across sessions.
 */

import type { ILogger } from '../../types/interfaces.js'
import type { IProvider } from '../../types/runtime.js'
import { TTLCache } from '../utils/ttl-cache.js'

// Types

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
}

// Provider-specific fallbacks
const FALLBACKS: Record<string, ModelCapabilities> = {
  // Anthropic
  'anthropic': { contextWindow: 200000, maxOutputTokens: 4096, supportsTools: true, supportsImages: true, source: 'fallback' },
  'claude': { contextWindow: 200000, maxOutputTokens: 4096, supportsTools: true, supportsImages: true, source: 'fallback' },
  // OpenAI
  'openai': { contextWindow: 128000, maxOutputTokens: 4096, supportsTools: true, supportsImages: true, source: 'fallback' },
  'gpt': { contextWindow: 128000, maxOutputTokens: 4096, supportsTools: true, supportsImages: true, source: 'fallback' },
  // Google
  'google': { contextWindow: 1000000, maxOutputTokens: 8192, supportsTools: true, supportsImages: true, source: 'fallback' },
  'gemini': { contextWindow: 1000000, maxOutputTokens: 8192, supportsTools: true, supportsImages: true, source: 'fallback' },
  // GitHub Copilot (via OpenAI)
  'github-copilot': { contextWindow: 128000, maxOutputTokens: 4096, supportsTools: true, supportsImages: false, source: 'fallback' },
  // Default
  'default': { contextWindow: 100000, maxOutputTokens: 4096, supportsTools: true, supportsImages: false, source: 'fallback' },
}

// ModelCapabilitiesFetcher

export class ModelCapabilitiesFetcher {
  private readonly logger: ILogger
  private readonly cache: TTLCache<string, ModelCapabilities>

  constructor(logger: ILogger) {
    this.logger = logger.child('model-capabilities')
    this.cache = new TTLCache<string, ModelCapabilities>({
      maxSize: 50,
      ttlMs: 10 * 60 * 1000, // 10 minutes — model caps don't change mid-run
    })
  }

  /**
   * Get capabilities for a provider+model combination.
   * Uses cascading fallback: registry → provider calibration → hardcoded defaults.
   */
  async getCapabilities(
    providerId: string,
    modelId: string,
    provider?: IProvider,
  ): Promise<ModelCapabilities> {
    const cacheKey = `${providerId}::${modelId}`
    const cached = this.cache.get(cacheKey)
    if (cached) return cached

    // Tier 1: Check the @cassicore/ai model registry
    const registryCaps = await this.fromRegistry(providerId, modelId)
    if (registryCaps) {
      this.cache.set(cacheKey, registryCaps)
      return registryCaps
    }

    // Tier 2: Provider calibration via countTokens()
    if (provider) {
      const calibrated = await this.fromProviderCalibration(provider, providerId, modelId)
      if (calibrated) {
        this.cache.set(cacheKey, calibrated)
        return calibrated
      }
    }

    // Tier 3: Hardcoded fallback
    const fallback = this.fromFallback(providerId, modelId)
    this.cache.set(cacheKey, fallback)
    this.logger.debug('Model capabilities from fallback', { providerId, modelId, contextWindow: fallback.contextWindow })
    return fallback
  }

  private async fromRegistry(providerId: string, modelId: string): Promise<ModelCapabilities | null> {
    try {
      // Try to import from @cassicore/ai if available
      const ai = await import('@cassicore/ai')
      // Check for MODELS or model registry
      const models = (ai as any).MODELS || (ai as any).models || (ai.default as any)?.MODELS
      const key = `${providerId}/${modelId}`
      const entry = models?.[key] || models?.[modelId]
      if (entry && entry.contextWindow) {
        return {
          contextWindow: entry.contextWindow,
          maxOutputTokens: entry.maxOutputTokens ?? 4096,
          supportsTools: entry.supportsTools ?? true,
          supportsImages: entry.supportsImages ?? false,
          source: 'registry',
        }
      }
    } catch {
      // @cassicore/ai not available — use fallback
    }
    return null
  }

  private async fromProviderCalibration(provider: IProvider, providerId: string, modelId: string): Promise<ModelCapabilities | null> {
    try {
      // Try to calibrate via provider's countTokens
      if ((provider as any).countTokens) {
        const testText = 'Test context calibration'
        const count = await (provider as any).countTokens(testText)
        // Estimate context window from token ratio (rough heuristic)
        const estimated = Math.min(count * 1000, 200000)
        return {
          contextWindow: estimated,
          maxOutputTokens: 4096,
          supportsTools: true,
          supportsImages: false,
          source: 'provider-calibration',
        }
      }
    } catch {
      // Provider calibration failed — use fallback
    }
    return null
  }

  private fromFallback(providerId: string, modelId: string): ModelCapabilities {
    // Match by provider ID prefix
    for (const [prefix, caps] of Object.entries(FALLBACKS)) {
      if (providerId.startsWith(prefix) || modelId.startsWith(prefix)) {
        return { ...caps }
      }
    }
    return { ...FALLBACKS['default'] }
  }

  /**
   * Clear the cache.
   */
  clearCache(): void {
    this.cache.clear()
  }
}