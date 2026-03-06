/**
 * BaseCognitiveModule — Standardized abstract base for LLM-powered intelligence modules.
 *
 * Provides boilerplate for:
 *   - EventBus subscription (auto-wired via registry)
 *   - LLM inference routing through centralized providers
 *   - Context injection back into MentalModel / TurnPipeline
 *   - Subconscious signal subscription
 *   - Structured lifecycle (init → start → stop)
 *
 * New modules inherit from this instead of manually implementing IntelligenceModule
 * and wiring setter methods. The IntelligenceRegistry auto-discovers and wires
 * modules that extend this class.
 *
 * @example
 * ```typescript
 * export class ReflexModule extends BaseCognitiveModule {
 *   readonly name = 'reflex'
 *   readonly priority = 45
 *
 *   async onThinking(sessionId: string, thinking: string): Promise<void> {
 *     const toolCall = await this.infer(parsePrompt(thinking), ThinkingSchema)
 *     if (toolCall) await this.executeTool(toolCall)
 *   }
 * }
 * ```
 */

import { MODEL_DEFAULTS } from '../../config/system-settings.js'

import type { RuntimeEvent } from '../../../types/events.js'
import type { IMemory } from '../../../types/intelligence.js'
import type { ILogger, IEventBus, IntelligenceModule, IConfig } from '../../../types/interfaces.js'
import type { IProvider, Message, CompletionOpts, CompletionChunk } from '../../../types/runtime.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'

// ============================================================================
// Model Configuration for LLM-powered modules
// ============================================================================

export interface ModuleModelConfig {
  /** Provider ID (e.g., 'lmstudio', 'kimi-coding', 'github-copilot') */
  providerId: string
  /** Model name (e.g., 'lfm2.5-1.2b', 'k2p5') */
  model: string
  /** Temperature for inference (0-2) */
  temperature: number
  /** Max tokens for response */
  maxTokens: number
  /** Timeout for inference calls (ms) */
  timeoutMs: number
}

export const DEFAULT_MODULE_MODEL_CONFIG: ModuleModelConfig = {
  providerId: MODEL_DEFAULTS.fast.provider,
  model: MODEL_DEFAULTS.fast.model,
  temperature: 0.3,
  maxTokens: 1024,
  timeoutMs: 10_000,
}

// ============================================================================
// Module Lifecycle
// ============================================================================

export type ModuleStatus = 'created' | 'initializing' | 'running' | 'stopped' | 'error'

export interface CognitiveModuleMetrics {
  inferenceCalls: number
  inferenceErrors: number
  totalInferenceMs: number
  eventsProcessed: number
  lastActivityAt: number
}

// ============================================================================
// BaseCognitiveModule
// ============================================================================

export abstract class BaseCognitiveModule implements IntelligenceModule {
  /** Unique module identifier (e.g., 'reflex', 'guardian') */
  abstract readonly name: string

  /** Priority in execution order — higher = runs first */
  abstract readonly priority: number

  protected logger: ILogger
  protected config?: IConfig
  protected eventBus?: IEventBus
  protected memory?: IMemory
  protected provider?: IProvider
  protected toolRegistry?: ToolRegistry
  protected toolExecutor?: ToolExecutor
  protected modelConfig: ModuleModelConfig

  private _status: ModuleStatus = 'created'
  private _metrics: CognitiveModuleMetrics = {
    inferenceCalls: 0,
    inferenceErrors: 0,
    totalInferenceMs: 0,
    eventsProcessed: 0,
    lastActivityAt: 0,
  }
  private _unsubscribers: Array<() => void> = []

  constructor(logger: ILogger, modelConfig?: Partial<ModuleModelConfig>) {
    this.logger = logger
    // Store the constructor-provided config (env-var layer or explicit overrides).
    // config.json values are merged later in init() once setConfig() has been called.
    this.modelConfig = { ...DEFAULT_MODULE_MODEL_CONFIG, ...modelConfig }
  }

  // ==========================================================================
  // Lifecycle — called by IntelligenceRegistry
  // ==========================================================================

  /**
   * Initialize the module. Override for custom init logic (call super.init()).
   *
   * IMPORTANT: This is where config.json model settings are resolved. The
   * registry calls setConfig(iconfig) during wire(), which happens before init().
   * So by the time init() runs, this.config is available for reading config.json.
   *
   * Precedence (highest wins):
   *   1. config.json — `intelligence.<moduleName>.model`, `.provider`, `.temperature`, `.maxTokens`, `.timeoutMs`
   *   2. Constructor `modelConfig` parameter (e.g., from REFLEX_SETTINGS env vars)
   *   3. DEFAULT_MODULE_MODEL_CONFIG hardcoded fallback
   */
  async init(): Promise<void> {
    this._status = 'initializing'
    this.resolveModelConfigFromJson()
    this.wireConfigWatcher()
    this.logger.info(`[${this.name}] Initializing (priority=${this.priority})`, {
      model: this.modelConfig.model,
      provider: this.modelConfig.providerId,
      configSource: this.config ? 'config.json+defaults' : 'defaults-only',
    })
  }

  /** Start the module after all dependencies are wired. Override for background work. */
  async start(): Promise<void> {
    this._status = 'running'
    this.logger.info(`[${this.name}] Started`)
  }

  /** Stop the module. Cleans up subscriptions. Override for custom teardown. */
  async stop(): Promise<void> {
    this._status = 'stopped'
    for (const unsub of this._unsubscribers) {
      try { unsub() } catch { /* best-effort */ }
    }
    this._unsubscribers = []
    this.logger.info(`[${this.name}] Stopped`)
  }

  get status(): ModuleStatus { return this._status }
  get metrics(): Readonly<CognitiveModuleMetrics> { return this._metrics }

  // ==========================================================================
  // Dependency Injection — called by IntelligenceRegistry
  // ==========================================================================

  setEventBus(bus: IEventBus): void {
    this.eventBus = bus
  }

  setMemory(memory: IMemory): void {
    this.memory = memory
  }

  setProvider(provider: IProvider): void {
    this.provider = provider
  }

  setConfig(config: IConfig): void {
    this.config = config
  }

  /**
   * Update the model configuration at runtime.
   * Accepts partial overrides — unspecified fields retain their current values.
   * Supports the combined 'provider/model' format in the `model` field.
   */
  setModelConfig(overrides: Partial<ModuleModelConfig>): void {
    const prev = { ...this.modelConfig }

    // Handle combined 'provider/model' format
    if (overrides.model && overrides.model.includes('/') && !overrides.providerId) {
      const [provider, model] = overrides.model.split('/', 2)
      overrides = { ...overrides, providerId: provider, model }
    }

    Object.assign(this.modelConfig, overrides)

    this.logger.info(`[${this.name}] Model config updated`, {
      prev: { provider: prev.providerId, model: prev.model },
      now: { provider: this.modelConfig.providerId, model: this.modelConfig.model },
    })
  }

  /**
   * Re-read model configuration from config.json and apply it.
   * Called on config:changed events or explicit admin API requests.
   */
  reloadModelConfig(): void {
    this.resolveModelConfigFromJson()
    this.logger.info(`[${this.name}] Model config reloaded from config.json`, {
      provider: this.modelConfig.providerId,
      model: this.modelConfig.model,
    })
  }

  /** Get current model configuration (read-only snapshot). */
  getModelConfig(): Readonly<ModuleModelConfig> {
    return { ...this.modelConfig }
  }

  setToolRegistry(registry: ToolRegistry): void {
    this.toolRegistry = registry
  }

  setToolExecutor(executor: ToolExecutor): void {
    this.toolExecutor = executor
  }

  // ==========================================================================
  // Event Handling — subclasses override the hooks they need
  // ==========================================================================

  /**
   * Called by the EventBus for every RuntimeEvent.
   * Routes to specific hooks (onTurnStart, onTurnEnd, etc.)
   * Subclasses can override for custom routing.
   */
  async onEvent(event: RuntimeEvent): Promise<void> {
    this._metrics.eventsProcessed++
    this._metrics.lastActivityAt = Date.now()

    try {
      switch (event.type) {
        case 'turn:start':
          await this.onTurnStart?.(event.sessionId, event.message)
          break
        case 'turn:end':
          await this.onTurnEnd?.(event.sessionId, event.response, event.durationMs)
          break
        case 'daemon:ready':
          await this.onDaemonReady?.()
          break
        case 'daemon:shutdown':
          await this.onDaemonShutdown?.(event.reason)
          break
        case 'plugin:crashed':
          await this.onPluginCrashed?.(event.pluginId, event.error)
          break
      }
    } catch (err) {
      this.logger.error(`[${this.name}] Error in event handler`, {
        eventType: event.type,
        error: String(err),
      })
    }
  }

  /**
   * Wire this module to the EventBus for real-time events.
   * Called by IntelligenceRegistry after setEventBus().
   * Subclasses call this.subscribe() for custom event subscriptions.
   */
  onEventBus(bus: IEventBus): void {
    this.eventBus = bus
    this.wireEventSubscriptions()
  }

  // ── Optional event hooks for subclasses ──────────────────────────────────

  /** Called on turn:start */
  protected onTurnStart?(sessionId: string, message: string): Promise<void>

  /** Called on turn:end */
  protected onTurnEnd?(sessionId: string, response: string, durationMs: number): Promise<void>

  /** Called on daemon:ready */
  protected onDaemonReady?(): Promise<void>

  /** Called on daemon:shutdown */
  protected onDaemonShutdown?(reason: string): Promise<void>

  /** Called on plugin:crashed */
  protected onPluginCrashed?(pluginId: string, error: string): Promise<void>

  /**
   * Called when the Subconscious emits thinking tokens from the main agent's stream.
   * This is the primary hook for modules that react to the agent's reasoning.
   */
  protected onThinking?(sessionId: string, thinking: string): Promise<void>

  /**
   * Called when the Subconscious emits a signal (pattern, intent, anomaly, etc.)
   */
  protected onSignal?(sessionId: string, signal: unknown): Promise<void>

  /**
   * Called during wireEventSubscriptions so subclasses can add custom subscriptions.
   * Use this.subscribe() to register event handlers.
   */
  protected registerSubscriptions?(): void

  // ==========================================================================
  // LLM Inference — simplified interface for module authors
  // ==========================================================================

  /**
   * Run LLM inference using this module's configured provider/model.
   * Returns the raw text response. For structured output, use inferJSON().
   *
   * @param prompt - The prompt to send (system + user messages)
   * @param opts - Optional overrides for model, temperature, etc.
   */
  protected async infer(
    prompt: string | Message[],
    opts?: Partial<CompletionOpts>,
  ): Promise<string> {
    if (!this.provider) {
      throw new Error(`[${this.name}] No provider configured — cannot infer`)
    }

    const messages: Message[] = typeof prompt === 'string'
      ? [{ role: 'user', content: prompt }]
      : prompt

    const completionOpts: CompletionOpts = {
      model: this.modelConfig.model,
      temperature: this.modelConfig.temperature,
      maxTokens: this.modelConfig.maxTokens,
      thinking: 'none',
      allowConcurrent: true,  // Module inference should never block main agent
      dedupe: false,          // Each module call is unique
      ...opts,
    }

    const startMs = Date.now()
    this._metrics.inferenceCalls++

    try {
      let result = ''
      const stream = this.provider.complete(messages, completionOpts)
      for await (const chunk of stream) {
        if (chunk.type === 'token' && chunk.text) {
          result += chunk.text
        }
      }
      this._metrics.totalInferenceMs += Date.now() - startMs
      return result
    } catch (err) {
      this._metrics.inferenceErrors++
      this._metrics.totalInferenceMs += Date.now() - startMs
      this.logger.error(`[${this.name}] Inference failed`, { error: String(err) })
      throw err
    }
  }

  /**
   * Run LLM inference and parse the response as JSON.
   * Wraps the prompt with instructions to return valid JSON.
   *
   * @param prompt - The prompt to send
   * @param opts - Optional overrides
   * @returns Parsed JSON object, or null if parsing fails
   */
  protected async inferJSON<T = unknown>(
    prompt: string | Message[],
    opts?: Partial<CompletionOpts>,
  ): Promise<T | null> {
    const messages: Message[] = typeof prompt === 'string'
      ? [
          { role: 'system', content: 'You are a JSON-only responder. Return ONLY valid JSON, no markdown, no explanation.' },
          { role: 'user', content: prompt },
        ]
      : prompt

    const raw = await this.infer(messages, opts)

    try {
      // Extract JSON from possible markdown code block
      const jsonMatch = raw.match(/```(?:json)?\s*([\s\S]*?)```/) || [null, raw]
      const jsonStr = (jsonMatch[1] || raw).trim()
      return JSON.parse(jsonStr) as T
    } catch (err) {
      this.logger.warn(`[${this.name}] Failed to parse JSON from inference`, {
        rawLength: raw.length,
        error: String(err),
      })
      return null
    }
  }

  // ==========================================================================
  // Context Injection — push results back into the system
  // ==========================================================================

  /**
   * Store a memory entry via the Memory module.
   */
  protected async storeMemory(
    type: string,
    content: string,
    metadata?: Record<string, unknown>,
    sessionId?: string,
  ): Promise<string | undefined> {
    if (!this.memory) {
      this.logger.warn(`[${this.name}] No memory module — cannot store`)
      return undefined
    }

    return this.memory.store({
      type: type as any,
      content,
      metadata: { ...metadata, source: this.name },
      sessionId,
    })
  }

  /**
   * Emit a typed event on the EventBus.
   */
  protected emit(event: RuntimeEvent): void {
    if (!this.eventBus) {
      this.logger.warn(`[${this.name}] No event bus — cannot emit`)
      return
    }
    this.eventBus.emit(event)
  }

  // ==========================================================================
  // Subscription Helpers
  // ==========================================================================

  /**
   * Subscribe to an event type on the EventBus. Auto-cleaned on stop().
   */
  protected subscribe<T extends RuntimeEvent['type']>(
    type: T,
    handler: (event: Extract<RuntimeEvent, { type: T }>) => void,
  ): void {
    if (!this.eventBus) {
      this.logger.warn(`[${this.name}] No event bus — cannot subscribe to ${type}`)
      return
    }

    const unsub = this.eventBus.on(type as any, handler as any)
    this._unsubscribers.push(unsub)
  }

  // ==========================================================================
  // Private Wiring
  // ==========================================================================

  /**
   * Wire config.json watcher for live model config changes.
   *
   * Listens for changes to any `intelligence.<moduleName>.*` key.
   * On change, re-resolves the full model config from config.json so that
   * partial edits (e.g., changing only the model) are correctly merged.
   */
  private wireConfigWatcher(): void {
    if (!this.config) return

    const prefix = `intelligence.${this.name}`
    const keys = [`${prefix}.model`, `${prefix}.provider`, `${prefix}.temperature`, `${prefix}.maxTokens`, `${prefix}.timeoutMs`]

    for (const key of keys) {
      const unsub = this.config.onChanged(key, () => {
        this.logger.debug(`[${this.name}] Config key changed: ${key}`)
        this.reloadModelConfig()
      })
      this._unsubscribers.push(unsub)
    }
  }

  /**
   * Resolve model configuration from config.json.
   *
   * Reads `intelligence.<moduleName>.model`, `.provider`, `.temperature`,
   * `.maxTokens`, and `.timeoutMs` from config.json. Values found in config.json
   * override whatever was set by the constructor (env vars / defaults).
   *
   * This makes ~/.cassicore/config.json the single pane of glass for model selection:
   *   config.json → env vars / REFLEX_SETTINGS → DEFAULT_MODULE_MODEL_CONFIG
   *
   * Called during init() — setConfig() has already been called by the registry.
   */
  private resolveModelConfigFromJson(): void {
    if (!this.config) return

    const prefix = `intelligence.${this.name}`

    try {
      // Read model — supports both 'provider/model' combined format and separate fields
      const configModel = this.config.get<string | undefined>(`${prefix}.model`, undefined)
      const configProvider = this.config.get<string | undefined>(`${prefix}.provider`, undefined)
      const configTemperature = this.config.get<number | undefined>(`${prefix}.temperature`, undefined)
      const configMaxTokens = this.config.get<number | undefined>(`${prefix}.maxTokens`, undefined)
      const configTimeoutMs = this.config.get<number | undefined>(`${prefix}.timeoutMs`, undefined)

      let applied = false

      if (configModel !== undefined) {
        // Handle 'provider/model' combined format (e.g., 'lmstudio/lfm2.5-1.2b')
        if (configModel.includes('/')) {
          const [provider, model] = configModel.split('/', 2)
          this.modelConfig.providerId = provider
          this.modelConfig.model = model
        } else {
          this.modelConfig.model = configModel
        }
        applied = true
      }

      if (configProvider !== undefined) {
        this.modelConfig.providerId = configProvider
        applied = true
      }

      if (configTemperature !== undefined && typeof configTemperature === 'number') {
        this.modelConfig.temperature = configTemperature
        applied = true
      }

      if (configMaxTokens !== undefined && typeof configMaxTokens === 'number') {
        this.modelConfig.maxTokens = configMaxTokens
        applied = true
      }

      if (configTimeoutMs !== undefined && typeof configTimeoutMs === 'number') {
        this.modelConfig.timeoutMs = configTimeoutMs
        applied = true
      }

      if (applied) {
        this.logger.debug(`[${this.name}] Model config resolved from config.json`, {
          model: this.modelConfig.model,
          provider: this.modelConfig.providerId,
          temperature: this.modelConfig.temperature,
        })
      }
    } catch (err) {
      this.logger.debug(`[${this.name}] No config.json overrides (${String(err)})`)
    }
  }

  private wireEventSubscriptions(): void {
    if (!this.eventBus) return

    // Always wire thinking and signal events from subconscious
    if (this.onThinking) {
      this.subscribe('subconscious:thinking' as any, (e: any) => {
        this.onThinking!(e.sessionId, e.thinking).catch(err => {
          this.logger.error(`[${this.name}] Error in onThinking`, { error: String(err) })
        })
      })
    }

    if (this.onSignal) {
      this.subscribe('subconscious:signal' as any, (e: any) => {
        this.onSignal!(e.sessionId, e.signal).catch(err => {
          this.logger.error(`[${this.name}] Error in onSignal`, { error: String(err) })
        })
      })
    }

    // Let subclasses add their own subscriptions
    this.registerSubscriptions?.()
  }
}
