/**
 * Scout Module — Pre-turn Search Agent
 *
 * Intercepts every turn before the main model, runs a cheap/fast LLM with
 * read-only search tools to gather relevant context, then injects the findings
 * so the main model starts informed and doesn't waste expensive tokens exploring.
 *
 * Architecture:
 *   ScoutModule (BaseCognitiveModule) → installs scoutMiddleware into TurnPipeline
 *   scoutMiddleware → heuristic check → ScoutEngine (fast model + tool loop) → inject context
 *
 * Follows the same hybrid pattern as ContextManager: a cognitive module that
 * installs its own middleware into the pipeline.
 */

import { SCOUT_SETTINGS } from '@cassicore/foundation'
import { BaseCognitiveModule } from '../intelligence/base/cognitive-module.js'

import { ScoutEngine } from './engine.js'
import { shouldSkipScout } from './heuristics.js'

import type { ScoutConfig, ScoutResult, ScoutCacheEntry } from './types.js'
import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { Message, TurnContext } from '@cassicore/foundation'
import type { ModuleModelConfig } from '../intelligence/base/cognitive-module.js'
import type { ModuleSessionRegistry } from '../intelligence/module-session-registry.js'
import type { ToolExecutor } from '@cassicore/tools'
import type { ToolRegistry } from '@cassicore/tools'
import type { TurnPipeline } from '../turn-pipeline.js'  // DEPRECATED: middleware never runs with SessionPipeline


// Cache — avoid redundant scouting for similar messages

class ScoutCache {
  private entries = new Map<string, ScoutCacheEntry>()
  private maxSize: number
  private ttlMs: number

  constructor(maxSize = 50, ttlMs = 120_000) {
    this.maxSize = maxSize
    this.ttlMs = ttlMs
  }

  get(messageHash: string): ScoutResult | undefined {
    const entry = this.entries.get(messageHash)
    if (!entry) return undefined
    if (Date.now() - entry.cachedAt > entry.ttlMs) {
      this.entries.delete(messageHash)
      return undefined
    }
    return entry.result
  }

  set(messageHash: string, result: ScoutResult): void {
    // Evict oldest if at capacity
    if (this.entries.size >= this.maxSize) {
      const oldest = this.entries.keys().next().value
      if (oldest) this.entries.delete(oldest)
    }
    this.entries.set(messageHash, {
      messageHash,
      result,
      cachedAt: Date.now(),
      ttlMs: this.ttlMs,
    })
  }

  clear(): void {
    this.entries.clear()
  }
}

// Simple hash for cache keys

function hashMessage(content: string): string {
  let hash = 0
  for (let i = 0; i < content.length; i++) {
    const ch = content.charCodeAt(i)
    hash = ((hash << 5) - hash + ch) | 0
  }
  return hash.toString(36)
}

// Fingerprint for deduplication

function fingerprint(text: string): string {
  let h = 0
  const s = text.slice(0, 512)
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0
  }
  return (h >>> 0).toString(36)
}

// ScoutModule

export class ScoutModule extends BaseCognitiveModule {
  readonly name = 'scout'
  readonly priority = 88  // Between ContextManager (85) and Continuity (90)

  private pipeline?: TurnPipeline
  private scoutToolRegistry?: ToolRegistry
  private scoutToolExecutor?: ToolExecutor
  private scoutConfig: ScoutConfig
  private cache: ScoutCache

  constructor(logger: ILogger, scoutConfig?: Partial<ScoutConfig>) {
    // Build model config from scout settings
    const modelCfg: Partial<ModuleModelConfig> = {
      providerId: scoutConfig?.providerId ?? SCOUT_SETTINGS.providerId,
      model: scoutConfig?.model ?? SCOUT_SETTINGS.model,
      temperature: scoutConfig?.temperature ?? SCOUT_SETTINGS.temperature,
      maxTokens: scoutConfig?.maxTokens ?? SCOUT_SETTINGS.maxTokens,
      timeoutMs: scoutConfig?.timeoutMs ?? SCOUT_SETTINGS.timeoutMs,
    }

    super(logger, modelCfg)

    // Merge provided config with defaults
    this.scoutConfig = {
      enabled: scoutConfig?.enabled ?? SCOUT_SETTINGS.enabled,
      providerId: modelCfg.providerId!,
      model: modelCfg.model!,
      temperature: modelCfg.temperature!,
      maxTokens: modelCfg.maxTokens!,
      maxToolRounds: scoutConfig?.maxToolRounds ?? SCOUT_SETTINGS.maxToolRounds,
      timeoutMs: modelCfg.timeoutMs!,
      maxContextChars: scoutConfig?.maxContextChars ?? SCOUT_SETTINGS.maxContextChars,
      historyTailSize: scoutConfig?.historyTailSize ?? SCOUT_SETTINGS.historyTailSize,
      skipHeuristic: scoutConfig?.skipHeuristic ?? SCOUT_SETTINGS.skipHeuristic,
      toolTimeoutMs: scoutConfig?.toolTimeoutMs ?? SCOUT_SETTINGS.toolTimeoutMs,
      allowedTools: scoutConfig?.allowedTools ?? [],
      minResultLength: scoutConfig?.minResultLength ?? SCOUT_SETTINGS.minResultLength,
    }

    this.cache = new ScoutCache(
      SCOUT_SETTINGS.cacheMaxSize,
      SCOUT_SETTINGS.cacheTtlMs,
    )
  }

  // Lifecycle

  async init(): Promise<void> {
    await super.init()
    this.logger.info('Initialized', {
      model: this.scoutConfig.model,
      provider: this.scoutConfig.providerId,
      maxToolRounds: this.scoutConfig.maxToolRounds,
      timeoutMs: this.scoutConfig.timeoutMs,
      skipHeuristic: this.scoutConfig.skipHeuristic,
    })
  }

  async start(): Promise<void> {
    await super.start()
    this.logger.info('Started — will pre-search before each turn')
  }

  async stop(): Promise<void> {
    this.cache.clear()
    await super.stop()
    this.logger.info('Stopped')
  }

  // Dependency Injection

  setToolRegistry(registry: ToolRegistry): void {
    this.scoutToolRegistry = registry
  }

  setToolExecutor(executor: ToolExecutor): void {
    this.scoutToolExecutor = executor
  }

  override setModuleRegistry(registry: ModuleSessionRegistry): void {
    super.setModuleRegistry(registry)
  }

  /**
   * DEPRECATED: Scout middleware installation.
   * SessionPipeline uses hooks, not middleware. This method logs a warning and does nothing.
   * The ScoutEngine infrastructure remains available for future hook-based integration.
   */
  setPipeline(pipeline: TurnPipeline): void {
    this.pipeline = pipeline
    this.logger.warn('Scout: middleware installation disabled — SessionPipeline does not use middleware chain', {
      note: 'ScoutModule.start() still runs, but pre-turn search will not execute automatically',
    })
  }

  // REMOVED: createMiddleware() deleted — SessionPipeline doesn't use middleware
  // The ScoutEngine infrastructure remains available for future hook-based integration.

  // Helpers

  /**
   * Extract the user's current message from the turn context.
   */
  private extractUserMessage(ctx: TurnContext): string {
    // Prefer inbound.content (the raw user message)
    if (ctx.inbound?.content && typeof ctx.inbound.content === 'string') {
      return ctx.inbound.content
    }

    // Fallback: last user message in messages array
    for (let i = ctx.messages.length - 1; i >= 0; i--) {
      const msg = ctx.messages[i]
      if (msg.role === 'user' && typeof msg.content === 'string') {
        return msg.content
      }
    }

    return ''
  }

  /**
   * Extract recent conversation history as context for the scout.
   */
  private extractConversationTail(ctx: TurnContext): Message[] {
    const tail = ctx.session?.history || []
    return tail.slice(-this.scoutConfig.historyTailSize)
  }

  /**
   * Inject the scout's gathered context into the turn's message array.
   * Uses a fingerprint marker for deduplication.
   */
  private injectContext(ctx: TurnContext, context: string): void {
    const fp = fingerprint(context)
    const marker = `[SCOUT-FP:${fp}]`

    // Wrap context with markers
    const wrapped = `[Scout Pre-Search Context]\n${context}\n${marker}\n[/Scout Pre-Search Context]`

    // Check for duplicate injection
    const hasDuplicate = ctx.messages.some(
      (m: Message) =>
        m.role === 'system' &&
        typeof m.content === 'string' &&
        m.content.includes(marker),
    )

    if (hasDuplicate) {
      this.logger.debug('Duplicate context detected, skipping injection')
      return
    }

    // Insert after existing system messages (before user messages)
    const sysIdx = ctx.messages.findIndex((m: Message) => m.role === 'system')
    let insertAt: number
    if (sysIdx >= 0) {
      // Find the last consecutive system message
      let lastSysIdx = sysIdx
      while (
        lastSysIdx + 1 < ctx.messages.length &&
        ctx.messages[lastSysIdx + 1].role === 'system'
      ) {
        lastSysIdx++
      }
      insertAt = lastSysIdx + 1
    } else {
      insertAt = 0
    }

    ctx.messages = [
      ...ctx.messages.slice(0, insertAt),
      { role: 'system', content: wrapped },
      ...ctx.messages.slice(insertAt),
    ]
  }

  /**
   * Emit a typed scout event.
   */
  private emitScoutEvent(type: string, data: Record<string, unknown>): void {
    if (!this.eventBus) return
    try {
      this.eventBus.emit({ type, ...data, timestamp: new Date() } as any)
    } catch {
      // Best-effort
    }
  }
}
