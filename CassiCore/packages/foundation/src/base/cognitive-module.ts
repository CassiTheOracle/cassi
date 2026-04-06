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
 * export class GuardianModule extends BaseCognitiveModule {
 *   readonly name = 'guardian'
 *   readonly priority = 45
 *
 *   async onTurnEnd(sessionId: string, response: string): Promise<void> {
 *     const assessment = await this.infer(analyzePrompt(response), AssessmentSchema)
 *     if (assessment.risk > 0.8) this.inject(sessionId, 'warning', assessment.reason)
 *   }
 * }
 * ```
 */

import {
  resolveModelConfigFromJson,
  wireModelConfigWatcher,
  applyModelConfigOverrides,
  DEFAULT_MODULE_MODEL_CONFIG,
} from './model-config.js'
import type { ModuleModelConfig } from './model-config.js'
import { infer as inferHelper, inferJSON as inferJSONHelper } from './inference.js'
import type { InferenceMetrics } from './inference.js'

import type { RuntimeEvent } from '../../../types/events.js'
import type { IMemory } from '../../../types/intelligence.js'
import type { IModelDirective } from '../../../types/model-routing.js'
import type { ILogger, IEventBus, IntelligenceModule, IConfig, WiringDependencies } from '../../../types/interfaces.js'
import type { IProvider, Message, CompletionOpts } from '../../../types/runtime.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolRegistry } from '../../tools/registry.js'
import type { ModuleSessionRegistry } from '../module-session-registry.js'
import type { GlobalBlackboardRegistry } from '../flux-team/global-blackboard-registry.js'

// Re-export types for backward compatibility
export type { ModuleModelConfig } from './model-config.js'
export { DEFAULT_MODULE_MODEL_CONFIG } from './model-config.js'

// Module Lifecycle

export type ModuleStatus = 'created' | 'initializing' | 'running' | 'stopped' | 'error'

export interface CognitiveModuleMetrics {
  inferenceCalls: number
  inferenceErrors: number
  totalInferenceMs: number
  eventsProcessed: number
  lastActivityAt: number
}

// BaseCognitiveModule

export abstract class BaseCognitiveModule implements IntelligenceModule {
  /** Unique module identifier (e.g., 'guardian', 'error-learner') */
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
  protected modelDirective?: IModelDirective
  protected providerResolver?: (providerId: string) => IProvider | undefined
  protected moduleRegistry?: ModuleSessionRegistry
  protected globalBlackboardRegistry?: GlobalBlackboardRegistry

  private _status: ModuleStatus = 'created'
  private _metrics: CognitiveModuleMetrics = {
    inferenceCalls: 0,
    inferenceErrors: 0,
    totalInferenceMs: 0,
    eventsProcessed: 0,
    lastActivityAt: 0,
  }
  private _inferenceMetrics: InferenceMetrics = { calls: 0, errors: 0, totalMs: 0 }
  private _unsubscribers: Array<() => void> = []

  /**
   * The requestId from the most recent provider call made via infer()/inferJSON().
   * Set by the onMeta callback before infer() resolves. Modules can include this
   * in their outcome events to enable end-to-end tracing in `cassicore llm stream`.
   */
  protected _lastRequestId?: string

  constructor(logger: ILogger, modelConfig?: Partial<ModuleModelConfig>) {
    this.logger = logger
    this.modelConfig = { ...DEFAULT_MODULE_MODEL_CONFIG, ...modelConfig }
  }

  // Lifecycle — called by IntelligenceRegistry

  async init(): Promise<void> {
    this._status = 'initializing'

    // Resolve config.json model settings
    if (this.config) {
      resolveModelConfigFromJson(this.config, this.name, this.modelConfig)

      // Watch for live config changes
      const unsubs = wireModelConfigWatcher(this.config, this.name, () => {
        this.logger.debug(`[${this.name}] Config key changed — reloading model config`)
        this.reloadModelConfig()
      })
      this._unsubscribers.push(...unsubs)
    }

    this.logger.info(`[${this.name}] Initializing (priority=${this.priority})`, {
      model: this.modelConfig.model,
      provider: this.modelConfig.providerId,
      configSource: this.config ? 'config.json+defaults' : 'defaults-only',
    })
  }

  async start(): Promise<void> {
    this._status = 'running'
    this.logger.info(`[${this.name}] Started`)
  }

  async stop(): Promise<void> {
    this._status = 'stopped'
    for (const unsub of this._unsubscribers) {
      try { unsub() } catch { /* best-effort */ }
    }
    this._unsubscribers = []
    this.logger.info(`[${this.name}] Stopped`)
  }

  get status(): ModuleStatus { return this._status }
  get metrics(): Readonly<CognitiveModuleMetrics> {
    // Sync inference metrics into the module-level metrics
    this._metrics.inferenceCalls = this._inferenceMetrics.calls
    this._metrics.inferenceErrors = this._inferenceMetrics.errors
    this._metrics.totalInferenceMs = this._inferenceMetrics.totalMs
    return this._metrics
  }

  // Dependency Injection

  setEventBus(bus: IEventBus): void { this.eventBus = bus }
  setMemory(memory: IMemory): void { this.memory = memory }
  setProvider(provider: IProvider): void { this.provider = provider }
  setConfig(config: IConfig): void { this.config = config }
  setToolRegistry(registry: ToolRegistry): void { this.toolRegistry = registry }
  setToolExecutor(executor: ToolExecutor): void { this.toolExecutor = executor }

  /**
   * Wire the module session registry so this module records its LLM turns
   * to a persistent debug session (accessible via Telegram topics).
   */
  setModuleRegistry(registry: ModuleSessionRegistry): void {
    this.moduleRegistry = registry
    // Ensure the session is created/loaded from disk immediately
    registry.getOrCreate(this.name)
  }

  /**
   * Wire the ModelDirective for centralized model selection.
   * When set, infer()/inferJSON() calls consult the directive to resolve
   * the provider+model for this module's slot (using `this.name` as the slot).
   * Only `default` and `job` scopes are meaningful for background modules.
   */
  setModelDirective(directive: IModelDirective): void { this.modelDirective = directive }

  /**
   * Wire a provider resolver function for directive-driven provider switching.
   * Allows infer() to look up a different provider instance when the directive
   * resolves to a provider other than the one wired via setProvider().
   */
  setProviderResolver(resolver: (providerId: string) => IProvider | undefined): void {
    this.providerResolver = resolver
  }

  /**
   * Wire the GlobalBlackboardRegistry for posting to named global boards.
   * Used by modules to publish findings, decisions, and artifacts.
   */
  setGlobalBlackboardRegistry(registry: GlobalBlackboardRegistry): void {
    this.globalBlackboardRegistry = registry
  }

  /**
   * Wire multiple dependencies in one call.
   * Preferred over individual setX() methods.
   */
  wire(deps: Partial<WiringDependencies>): void {
    if (deps.eventBus) this.setEventBus(deps.eventBus)
    if (deps.memory) this.setMemory(deps.memory as IMemory)
    if (deps.provider) this.setProvider(deps.provider as IProvider)
    if (deps.config) this.setConfig(deps.config)
    if (deps.toolRegistry) this.setToolRegistry(deps.toolRegistry as ToolRegistry)
    if (deps.toolExecutor) this.setToolExecutor(deps.toolExecutor as ToolExecutor)
    if (deps.globalBlackboardRegistry) this.setGlobalBlackboardRegistry(deps.globalBlackboardRegistry as GlobalBlackboardRegistry)
  }

  /**
   * Update the model configuration at runtime.
   * Supports combined 'provider/model' format.
   */
  setModelConfig(overrides: Partial<ModuleModelConfig>): void {
    const prev = { provider: this.modelConfig.providerId, model: this.modelConfig.model }
    applyModelConfigOverrides(this.modelConfig, overrides)
    this.logger.info(`[${this.name}] Model config updated`, {
      prev,
      now: { provider: this.modelConfig.providerId, model: this.modelConfig.model },
    })
  }

  reloadModelConfig(): void {
    if (this.config) {
      resolveModelConfigFromJson(this.config, this.name, this.modelConfig)
    }
    this.logger.info(`[${this.name}] Model config reloaded`, {
      provider: this.modelConfig.providerId,
      model: this.modelConfig.model,
    })
  }

  getModelConfig(): Readonly<ModuleModelConfig> {
    return { ...this.modelConfig }
  }

  // Event Handling — subclasses override the hooks they need

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
        case 'daemon:restarting':
          await this.onDaemonRestarting?.(event.reason)
          break
        case 'plugin:crashed':
          await this.onPluginCrashed?.(event.pluginId, event.error)
          break
        case 'tool:round-complete':
          await this.onToolRound?.(
            (event as any).sessionId,
            (event as any).round,
            (event as any).toolCalls,
            (event as any).results,
          )
          break
      }
    } catch (err) {
      this.logger.error(`[${this.name}] Error in event handler`, {
        eventType: event.type,
        error: String(err),
      })
    }
  }

  onEventBus(bus: IEventBus): void {
    if (this.eventBus === bus) return
    this.eventBus = bus
    this.wireEventSubscriptions()
  }


  protected onTurnStart?(sessionId: string, message: string): Promise<void>
  protected onTurnEnd?(sessionId: string, response: string, durationMs: number): Promise<void>
  protected onDaemonReady?(): Promise<void>
  protected onDaemonShutdown?(reason: string): Promise<void>
  protected onDaemonRestarting?(reason: string): Promise<void>
  protected onPluginCrashed?(pluginId: string, error: string): Promise<void>
  protected onThinking?(sessionId: string, thinking: string): Promise<void>
  protected onSignal?(sessionId: string, signal: unknown): Promise<void>
  protected onToolRound?(
    sessionId: string,
    round: number,
    toolCalls: Array<{ name: string; id: string }>,
    results: Array<{ toolCallId: string; isError: boolean; contentPreview: string }>,
  ): Promise<void>
  protected registerSubscriptions?(): void

  // LLM Inference — delegates to standalone inference helpers

  /**
   * Run LLM inference using this module's configured provider/model.
   * If a ModelDirective is wired, consults it for a slot-specific override
   * (using `this.name` as the slot name in the dotted hierarchy).
   * Returns the raw text response. For structured output, use inferJSON().
   */
  protected async infer(
    prompt: string | Message[],
    opts?: Partial<CompletionOpts>,
  ): Promise<string> {
    if (!this.provider) {
      throw new Error(`[${this.name}] No provider configured — cannot infer`)
    }

    // Resolve directive override if available
    const { provider: effectiveProvider, modelConfig: effectiveModelConfig } = this.resolveEffectiveModel()

    this._lastRequestId = undefined
    return inferHelper(effectiveProvider, effectiveModelConfig, prompt, {
      source: this.name,
      onMeta: (meta) => { this._lastRequestId = meta.requestId },
      // Bind to persistent module debug session when registry is wired
      sessionId: this.moduleRegistry?.getSessionId(this.name),
      ...opts,
    }, this._inferenceMetrics)
  }

  /**
   * Run LLM inference and parse the response as JSON.
   * Wraps the prompt with instructions to return valid JSON.
   */
  protected async inferJSON<T = unknown>(
    prompt: string | Message[],
    opts?: Partial<CompletionOpts>,
  ): Promise<T | null> {
    if (!this.provider) {
      throw new Error(`[${this.name}] No provider configured — cannot infer`)
    }

    // Resolve directive override if available
    const { provider: effectiveProvider, modelConfig: effectiveModelConfig } = this.resolveEffectiveModel()

    this._lastRequestId = undefined
    return inferJSONHelper<T>(effectiveProvider, effectiveModelConfig, prompt, this.logger, {
      source: this.name,
      onMeta: (meta) => { this._lastRequestId = meta.requestId },
      // Bind to persistent module debug session when registry is wired
      sessionId: this.moduleRegistry?.getSessionId(this.name),
      ...opts,
    }, this._inferenceMetrics)
  }

  /**
   * Resolve the effective provider and model config for an inference call.
   * Checks the ModelDirective for a slot-specific override (using this.name),
   * falling back to the module's configured provider/model.
   */
  private resolveEffectiveModel(): { provider: IProvider; modelConfig: ModuleModelConfig } {
    if (this.modelDirective) {
      // Resolve without consuming 'next' scope (background modules shouldn't consume one-shot overrides).
      // We pass undefined for jobId since background modules aren't scoped to a specific job.
      const override = this.modelDirective.resolve(undefined, this.name)

      // Check if the directive returned something different from the hardcoded fallback
      if (override.provider !== this.modelConfig.providerId || override.model !== this.modelConfig.model) {
        // Try to resolve the provider instance
        const resolvedProvider = this.providerResolver?.(override.provider) ?? this.provider
        if (resolvedProvider) {
          return {
            provider: resolvedProvider,
            modelConfig: { ...this.modelConfig, providerId: override.provider, model: override.model },
          }
        }
      }
    }

    return { provider: this.provider!, modelConfig: this.modelConfig }
  }

  // Context Injection

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

  protected emit(event: RuntimeEvent): void {
    if (!this.eventBus) {
      this.logger.warn(`[${this.name}] No event bus — cannot emit`)
      return
    }
    this.eventBus.emit(event)
  }

  /**
   * Post an entry to a named global board. Fire-and-forget — never throws.
   * Modules use this to make their LLM outputs visible on the blackboard.
   */
  protected postToBoard(
    boardName: string,
    channel: 'findings' | 'concerns' | 'decisions' | 'artifacts' | 'requests' | 'bugs',
    content: string,
    opts?: { author?: string; tags?: string[]; priority?: number },
  ): void {
    try {
      const board = this.globalBlackboardRegistry?.getOrCreate(boardName, { persist: true })
      board?.post(channel, {
        content,
        author: opts?.author ?? this.name,
        tags: opts?.tags ?? [],
        priority: opts?.priority ?? 0,
      })
    } catch (err) {
      this.logger.debug(`[${this.name}] Blackboard post failed (non-fatal)`, { error: String(err), boardName, channel })
    }
  }

  // Subscription Helpers

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

  // Private Wiring

  private wireEventSubscriptions(): void {
    if (!this.eventBus) return

    if (this.onTurnStart) {
      this.subscribe('turn:start' as any, (e: any) => {
        this.onTurnStart!(e.sessionId, e.message).catch((err: unknown) => {
          this.logger.error(`[${this.name}] Error in onTurnStart`, { error: String(err) })
        })
      })
    }

    if (this.onTurnEnd) {
      this.subscribe('turn:end' as any, (e: any) => {
        this.onTurnEnd!(e.sessionId, e.response, e.durationMs).catch((err: unknown) => {
          this.logger.error(`[${this.name}] Error in onTurnEnd`, { error: String(err) })
        })
      })
    }

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

    if (this.onToolRound) {
      this.subscribe('tool:round-complete' as any, (e: any) => {
        this.onToolRound!(e.sessionId, e.round, e.toolCalls, e.results).catch(err => {
          this.logger.error(`[${this.name}] Error in onToolRound`, { error: String(err) })
        })
      })
    }

    this.registerSubscriptions?.()
  }
}
