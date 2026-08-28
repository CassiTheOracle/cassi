/**
 * ModelDirective — Central model/provider routing directive for LLM operations.
 *
 * Replaces per-tool provider/model parameters with a single, layered routing
 * system. Scopes with strict priority, with optional slot-level granularity:
 *
 *   next:slot > next > job:slot > job > session:slot > session > default:slot > default > hardcoded
 *
 * Named tiers (minimax, qwenPlus, glm, kimi, qwenMax, sonnet, opus, background) provide
 * ergonomic aliases for common provider/model combos.
 *
 * Slot names use dotted hierarchy to avoid collisions:
 *   lumen.yang, lumen.yin, lumen.executive,
 *   dialectic.yang, dialectic.yin, dialectic.serenity,
 *   thinker, subconscious, memory, dreamer
 *
 * Complementary to the existing ModelRouter (budget-based routing):
 * - ModelDirective: "What provider+model should be used?" (scope overrides)
 * - ModelRouter: "Given budget, should I degrade or skip?" (cost awareness)
 */

import type { IConfig, IEventBus, ILogger } from '@cassicore/foundation'
import type {
  ModelConfig,
  RoutingScope,
  RoutingTier,
  IModelDirective,
  ModelDirectiveState,
} from '@cassicore/foundation'


const DEFAULT_TIERS: Record<RoutingTier, ModelConfig> = {
  minimax:    { provider: 'opencode-go', model: 'minimax-m2.5' },
  qwenPlus:   { provider: 'opencode-go', model: 'deepseek-v4-flash' },
  glm:        { provider: 'opencode-go', model: 'glm-5.1' },
  kimi:       { provider: 'opencode-go', model: 'kimi-k2.5' },
  qwenMax:    { provider: 'opencode-go', model: 'deepseek-v4-pro' },
  sonnet:     { provider: 'opencode-go', model: 'deepseek-v4-pro' },
  opus:       { provider: 'opencode-go', model: 'deepseek-v4-pro' },
  background: { provider: 'opencode-go', model: 'deepseek-v4-flash' },
}

/** Prefix patterns for auto-discovering models from the provider's model list.
 *  Each tier maps to a model-name prefix. When a tier's provider supports
 *  dynamic model discovery, the highest-version model matching the prefix
 *  is selected automatically — no manual model name configuration needed. */
const TIER_MODEL_PREFIXES: Record<RoutingTier, string> = {
  minimax:    'minimax-',
  qwenPlus:   'qwen',
  glm:        'glm-',
  kimi:       'kimi-',
  qwenMax:    'qwen',
  sonnet:     'claude-sonnet-',
  opus:       'claude-opus-',
  background: 'deepseek-v4-flash',
}

/** Hardcoded fallback when nothing else is configured */
const HARDCODED_FALLBACK: ModelConfig = {
  provider: 'opencode-go',
  model: 'deepseek-v4-pro',
}

/** All valid tier names for iteration. Single source of truth for the
 *  tier-name list — exported so MCP gateways and admin UIs can populate
 *  enums/dropdowns from the canonical list rather than duplicating it. */
export const ALL_TIER_NAMES: readonly RoutingTier[] = ['minimax', 'qwenPlus', 'glm', 'kimi', 'qwenMax', 'sonnet', 'opus', 'background']


export interface ModelDirectiveDeps {
  config: IConfig
  eventBus: IEventBus
  logger: ILogger
  /** Available provider IDs for validation (e.g. from providers Map) */
  availableProviders?: () => string[]
  /** Get available models for a given provider ID */
  getProviderModels?: (providerId: string) => string[] | null
  /** Persist a default config change to the daemon config file */
  persistDefault?: (config: ModelConfig, slot?: string) => void
}

export class ModelDirective implements IModelDirective {
  /**
   * Override storage uses composite keys for slot-specific overrides:
   *   - Shared key:     ""                  (applies to all slots)
   *   - Slot-specific:  "slot:lumen.yang"   (applies only to that slot)
   *   - Job shared:     "team-123"          (applies to all slots in that job)
   *   - Job+slot:       "team-123:lumen.yang" (applies to that slot in that job)
   */
  private nextOverrides = new Map<string, ModelConfig>()
  private nextJobOverrides = new Map<string, ModelConfig>()
  private sessionOverrides = new Map<string, ModelConfig>()
  private jobOverrides = new Map<string, ModelConfig>()
  private defaultOverrides = new Map<string, ModelConfig>()

  private tiers: Record<RoutingTier, ModelConfig>
  private readonly logger: ILogger
  private readonly eventBus: IEventBus
  private readonly config: IConfig
  private readonly getAvailableProviders: () => string[]
  private readonly getProviderModels: (providerId: string) => string[] | null
  private readonly persistDefaultFn?: (config: ModelConfig, slot?: string) => void

  constructor(deps: ModelDirectiveDeps) {
    this.logger = deps.logger.child('model-directive')
    this.eventBus = deps.eventBus
    this.config = deps.config
    this.getAvailableProviders = deps.availableProviders ?? (() => [])
    this.getProviderModels = deps.getProviderModels ?? ((_: string) => null)
    this.persistDefaultFn = deps.persistDefault

    // Load tiers from config, falling back to defaults
    this.tiers = this.loadTiers()

    // Load persisted default from config
    const cfgProvider = this.config.get<string>('intelligence.modelDirective.default.provider', '')
    const cfgModel = this.config.get<string>('intelligence.modelDirective.default.model', '')
    if (cfgProvider && cfgModel) {
      this.defaultOverrides.set('', { provider: cfgProvider, model: cfgModel })
    }
    const slotDefaults = this.config.get<Record<string, { provider?: string; model?: string }>>('intelligence.modelDirective.slots', {})
    if (slotDefaults && typeof slotDefaults === 'object') {
      for (const [slot, cfg] of Object.entries(slotDefaults)) {
        if (cfg?.provider && cfg?.model) {
          this.defaultOverrides.set(`slot:${slot}`, { provider: cfg.provider, model: cfg.model })
        }
      }
    }

    // Watch for config changes to tiers
    this.config.onChanged('intelligence.modelDirective.tiers', () => {
      this.tiers = this.loadTiers()
      this.logger.info('Tiers reloaded from config')
    })

    this.logger.info('ModelDirective initialized', {
      tiers: Object.keys(this.tiers),
      default: this.getDefaultConfig(),
    })
  }


  set(scope: RoutingScope, config: ModelConfig, jobId?: string, slot?: string): void {
    // Infer provider from model name if not provided
    if (!config.provider && config.model) {
      config = { ...config, provider: this.resolveProviderForModel(config.model) }
    }

    // Validate provider and model availability
    const validation = this.validateProviderAndModel(config.provider, config.model)
    if (!validation.valid) {
      throw new Error(validation.error!)
    }

    const meta = { scope, provider: config.provider, model: config.model, jobId, slot }

    switch (scope) {
      case 'next': {
        const key = slot ? `slot:${slot}` : ''
        this.nextOverrides.set(key, { ...config })
        this.logger.info('Next-call override set', meta)
        this.emitEvent('model-directive:set', meta)
        break
      }

      case 'next-job': {
        const key = slot ? `slot:${slot}` : ''
        this.nextJobOverrides.set(key, { ...config })
        this.logger.info('Next-job override set', meta)
        this.emitEvent('model-directive:set', meta)
        break
      }

      case 'session': {
        const key = slot ? `slot:${slot}` : ''
        this.sessionOverrides.set(key, { ...config })
        this.logger.info('Session override set (persists for all jobs in this session)', meta)
        this.emitEvent('model-directive:set', meta)
        break
      }

      case 'job': {
        if (!jobId) throw new Error('jobId is required for scope="job"')
        const key = slot ? `${jobId}:${slot}` : jobId
        this.jobOverrides.set(key, { ...config })
        this.logger.info('Job override set', meta)
        this.emitEvent('model-directive:set', meta)
        break
      }

      case 'default': {
        const key = slot ? `slot:${slot}` : ''
        this.defaultOverrides.set(key, { ...config })
        this.logger.info('Default override set', meta)
        this.emitEvent('model-directive:set', meta)
        if (this.persistDefaultFn) {
          try {
            this.persistDefaultFn(config, slot)
          } catch (err) {
            this.logger.warn('Failed to persist default', { error: String(err) })
          }
        }
        break
      }
    }
  }

  resolve(jobId?: string, slot?: string): ModelConfig {
    // Resolution priority: next:slot > next > job:slot > job > default:slot > default > hardcoded

    // 1. next:slot (consumed on use)
    if (slot) {
      const slotKey = `slot:${slot}`
      if (this.nextOverrides.has(slotKey)) {
        const override = { ...this.nextOverrides.get(slotKey)! }
        this.nextOverrides.delete(slotKey)
        this.logger.debug('Consumed next:slot override', { slot, provider: override.provider, model: override.model })
        this.emitEvent('model-directive:consumed-next', { slot, provider: override.provider, model: override.model })
        return override
      }
    }

    // 2. next (shared, consumed on use)
    if (this.nextOverrides.has('')) {
      const override = { ...this.nextOverrides.get('')! }
      this.nextOverrides.delete('')
      this.logger.debug('Consumed next override', { provider: override.provider, model: override.model })
      this.emitEvent('model-directive:consumed-next', { provider: override.provider, model: override.model })
      return override
    }

    // 3. job:slot
    if (jobId && slot) {
      const slotKey = `${jobId}:${slot}`
      if (this.jobOverrides.has(slotKey)) {
        const override = this.jobOverrides.get(slotKey)!
        return override
      }
    }

    // 4. job (shared)
    if (jobId && this.jobOverrides.has(jobId)) {
      return this.jobOverrides.get(jobId)!
    }

    // 5. session:slot (not consumed — persists for all jobs in the calling session)
    if (slot) {
      const slotKey = `slot:${slot}`
      if (this.sessionOverrides.has(slotKey)) {
        return this.sessionOverrides.get(slotKey)!
      }
    }

    // 6. session (shared)
    if (this.sessionOverrides.has('')) {
      return { ...this.sessionOverrides.get('')! }
    }

    // 7. default:slot
    if (slot) {
      const slotKey = `slot:${slot}`
      if (this.defaultOverrides.has(slotKey)) {
        return this.defaultOverrides.get(slotKey)!
      }
    }

    // 8. default (shared)
    if (this.defaultOverrides.has('')) {
      return { ...this.defaultOverrides.get('')! }
    }

    // 9. hardcoded fallback
    return { ...HARDCODED_FALLBACK }
  }

  getState(jobId?: string): ModelDirectiveState {
    const defaultConfig = this.getDefaultConfig()
    const jobConfig = jobId ? (this.jobOverrides.get(jobId) ?? null) : null
    const nextConfig = this.nextOverrides.get('') ?? null

    // Determine effective source (simplified — does not consider slots)
    let source: ModelDirectiveState['source'] = 'hardcoded'
    let effective: ModelConfig = { ...HARDCODED_FALLBACK }
    if (this.defaultOverrides.has('')) {
      source = 'default'
      effective = this.defaultOverrides.get('')!
    }
    if (this.sessionOverrides.has('')) {
      source = 'session'
      effective = this.sessionOverrides.get('')!
    }
    if (jobConfig) {
      source = 'job'
      effective = jobConfig
    }
    if (nextConfig) {
      source = 'next'
      effective = nextConfig
    }

    const activeJobs: Record<string, ModelConfig> = {}
    for (const [id, config] of this.jobOverrides) {
      activeJobs[id] = config
    }

    const nextJobEntries: Record<string, ModelConfig> = {}
    for (const [key, config] of this.nextJobOverrides) {
      nextJobEntries[key || '(all)'] = config
    }

    const sessionEntries: Record<string, ModelConfig> = {}
    for (const [key, config] of this.sessionOverrides) {
      sessionEntries[key || '(all)'] = config
    }

    return {
      effective,
      source,
      next: nextConfig ? { ...nextConfig } : null,
      nextJob: this.nextJobOverrides.size > 0 ? nextJobEntries : null,
      session: this.sessionOverrides.size > 0 ? sessionEntries : null,
      job: jobConfig,
      default: defaultConfig,
      activeJobs,
    }
  }

  clear(scope: RoutingScope, jobId?: string, slot?: string): void {
    switch (scope) {
      case 'next': {
        const key = slot ? `slot:${slot}` : ''
        this.nextOverrides.delete(key)
        this.logger.info('Next-call override cleared', { slot })
        break
      }

      case 'next-job': {
        if (slot) {
          this.nextJobOverrides.delete(`slot:${slot}`)
        } else {
          this.nextJobOverrides.clear()
        }
        this.logger.info('Next-job override cleared', { slot })
        break
      }

      case 'session': {
        if (slot) {
          this.sessionOverrides.delete(`slot:${slot}`)
        } else {
          this.sessionOverrides.clear()
        }
        this.logger.info('Session override cleared', { slot })
        break
      }

      case 'job': {
        if (!jobId) throw new Error('jobId is required for scope="job"')
        const key = slot ? `${jobId}:${slot}` : jobId
        this.jobOverrides.delete(key)
        this.logger.info('Job override cleared', { jobId, slot })
        break
      }

      case 'default': {
        const key = slot ? `slot:${slot}` : ''
        this.defaultOverrides.delete(key)
        this.logger.info('Default override cleared', { slot })
        if (this.persistDefaultFn) {
          try {
            this.persistDefaultFn({ provider: '', model: '' }, slot)
          } catch (err) {
            this.logger.warn('Failed to clear persisted default', { error: String(err) })
          }
        }
        break
      }
    }
    this.emitEvent('model-directive:cleared', { scope, jobId, slot })
  }

  clearJob(jobId: string): void {
    // Remove all overrides that start with this jobId (shared + slot-specific)
    const keysToDelete: string[] = []
    for (const key of this.jobOverrides.keys()) {
      if (key === jobId || key.startsWith(`${jobId}:`)) {
        keysToDelete.push(key)
      }
    }
    for (const key of keysToDelete) {
      this.jobOverrides.delete(key)
    }
    if (keysToDelete.length > 0) {
      this.logger.debug('Job overrides auto-cleared', { jobId, count: keysToDelete.length })
      this.emitEvent('model-directive:cleared', { scope: 'job', jobId })
    }
  }

  clearSession(): void {
    const count = this.sessionOverrides.size
    this.sessionOverrides.clear()
    if (count > 0) {
      this.logger.info('Session overrides cleared', { count })
      this.emitEvent('model-directive:cleared', { scope: 'session' })
    }
  }

  consumeNextJob(jobId: string): number {
    if (this.nextJobOverrides.size === 0) return 0

    let count = 0
    for (const [key, config] of this.nextJobOverrides.entries()) {
      // key is "" (no slot) or "slot:lumen.yang" etc.
      // Transfer to job overrides: "" → jobId, "slot:lumen.yang" → "jobId:lumen.yang"
      const slot = key.startsWith('slot:') ? key.slice(5) : undefined
      const jobKey = slot ? `${jobId}:${slot}` : jobId
      this.jobOverrides.set(jobKey, { ...config })
      count++
    }

    this.nextJobOverrides.clear()
    this.logger.info('Next-job overrides consumed', { jobId, count })
    this.emitEvent('model-directive:next-job-consumed', { jobId, count })
    return count
  }

  resolveTier(tier: RoutingTier): ModelConfig {
    const config = this.tiers[tier]
    if (!config) {
      throw new Error(`Unknown tier: "${tier}". Available: ${Object.keys(this.tiers).join(', ')}`)
    }
    return { ...config }
  }

  listTiers(): Record<RoutingTier, ModelConfig> {
    const result = {} as Record<RoutingTier, ModelConfig>
    for (const [tier, config] of Object.entries(this.tiers)) {
      result[tier as RoutingTier] = { ...config }
    }
    return result
  }

  validateProvider(provider: string): { valid: boolean; error?: string } {
    const available = this.getAvailableProviders()
    if (available.length === 0) {
      return { valid: true }
    }
    if (available.includes(provider)) {
      return { valid: true }
    }
    return {
      valid: false,
      error: `Provider "${provider}" is not available. Available providers: ${available.join(', ')}`,
    }
  }

  validateProviderAndModel(provider: string, model: string): { valid: boolean; error?: string } {
    // First validate provider
    const providerValidation = this.validateProvider(provider)
    if (!providerValidation.valid) {
      return providerValidation
    }

    // If no getProviderModels function, skip model validation
    if (!this.getProviderModels) {
      return { valid: true }
    }

    // Get available models for this provider
    const availableModels = this.getProviderModels(provider)
    if (!availableModels || availableModels.length === 0) {
      return { valid: true } // No model list available, skip validation
    }

    // Check if model exists
    if (availableModels.includes(model)) {
      return { valid: true }
    }
    
    return {
      valid: false,
      error: `Model "${model}" is not available for provider "${provider}". Available models: ${availableModels.join(', ')}`,
    }
  }


  private getDefaultConfig(): ModelConfig {
    if (this.defaultOverrides.has('')) {
      return { ...this.defaultOverrides.get('')! }
    }
    return { ...HARDCODED_FALLBACK }
  }

  /**
   * Resolve which provider serves a given model name.
   * Checks all available providers' model lists. Returns the first match.
   * Falls back to the default provider if no match found.
   */
  resolveProviderForModel(modelName: string): string {
    if (!this.getProviderModels) {
      return this.getDefaultConfig().provider
    }

    for (const provider of this.getAvailableProviders()) {
      const models = this.getProviderModels(provider)
      if (models && models.includes(modelName)) {
        return provider
      }
    }

    // No match — fall back to default provider
    return this.getDefaultConfig().provider
  }

  private loadTiers(): Record<RoutingTier, ModelConfig> {
    const result = {} as Record<RoutingTier, ModelConfig>
    const explicitModels = new Set<RoutingTier>()

    for (const tier of ALL_TIER_NAMES) {
      const cfgProvider = this.config.get<string>(`intelligence.modelDirective.tiers.${tier}.provider`, '')
      const cfgModel = this.config.get<string>(`intelligence.modelDirective.tiers.${tier}.model`, '')

      if (cfgProvider && cfgModel) {
        result[tier] = { provider: cfgProvider, model: cfgModel }
        explicitModels.add(tier)
      } else {
        result[tier] = { ...DEFAULT_TIERS[tier] }
      }
    }

    // Auto-discover models from the provider's model list for tiers
    // that were NOT explicitly configured in config.json
    for (const tier of ALL_TIER_NAMES) {
      if (explicitModels.has(tier)) continue
      const cfg = result[tier]
      if (cfg.provider !== 'opencode-go') continue

      const discovered = this.discoverModelForTier(tier)
      if (discovered) {
        result[tier] = { provider: cfg.provider, model: discovered }
      }
    }

    return result
  }

  /** Find the best model for a tier from the provider's dynamically-fetched
   *  model list. Uses TIER_MODEL_PREFIXES to match models by name, then picks
   *  the highest version. Returns null if no matching model is found. */
  private discoverModelForTier(tier: RoutingTier): string | null {
    const prefix = TIER_MODEL_PREFIXES[tier]
    if (!prefix) return null

    const models = this.getProviderModels('opencode-go')
    if (!models || models.length === 0) return null

    const matching = models.filter(m => m.startsWith(prefix))
    if (matching.length === 0) return null

    // Sort by version: extract the suffix after prefix and compare numerically
    matching.sort((a, b) => this.compareModelVersions(a, b, prefix))
    return matching[matching.length - 1]
  }

  /** Compare two model names by version number. Extracts the portion after
   *  the given prefix and compares numeric components. Falls back to
   *  lexicographic comparison for tie-breaking. */
  private compareModelVersions(a: string, b: string, prefix: string): number {
    const aVer = this.parseVersionParts(a.slice(prefix.length))
    const bVer = this.parseVersionParts(b.slice(prefix.length))

    const maxLen = Math.max(aVer.length, bVer.length)
    for (let i = 0; i < maxLen; i++) {
      const av = aVer[i] ?? 0
      const bv = bVer[i] ?? 0
      if (av !== bv) return av - bv
    }
    // Tie-break: prefer non-preview, non-nightly
    const aBad = a.includes('preview') || a.includes('nightly')
    const bBad = b.includes('preview') || b.includes('nightly')
    if (aBad !== bBad) return bBad ? 1 : -1
    return 0
  }

  /** Parse version numbers from a model suffix like "m2.7", "k2.6", "5.1",
   *  "3.6-plus". Returns an array of numeric components. */
  private parseVersionParts(suffix: string): number[] {
    const numeric = suffix.match(/[\d.]+/)
    if (!numeric) return [0]
    return numeric[0].split('.').map(Number)
  }

  private emitEvent(type: string, data: Record<string, unknown>): void {
    this.eventBus.emit({
      type: type as 'model-directive:set',
      sessionId: 'system',
      timestamp: Date.now(),
      data,
    } as any).catch(err => {
      this.logger.warn('Failed to emit directive event', { error: String(err) })
    })
  }
}
