/**
 * Heart Module — Periodic Autonomous Agent Heartbeats
 *
 * Performs periodic autonomous agent turns that read HEARTBEAT.md,
 * follow its checklist, and route actionable results to channels.
 *
 * Inspired by OpenClaw's heartbeat pattern but built natively on
 * CassiCore infrastructure (TurnPipeline, EventBus, PluginHost).
 */

import { BaseCognitiveModule } from '../base/cognitive-module.js'
import type { ModuleModelConfig } from '../base/cognitive-module.js'
import { readHeartbeatFile, type HeartbeatFileResult } from './heartbeat-reader.js'
import { parseHeartbeatResponse } from './response-parser.js'
import { DEFAULT_HEART_CONFIG, type HeartConfig, type HeartbeatResult, type HeartState } from './types.js'

import type { ILogger, IEventBus, IConfig, WiringDependencies } from '@cassicore/foundation'
import type { IMemory } from '@cassicore/foundation'
// REMOVED: TurnPipeline import deleted — SessionPipeline is always wired
import type { InboundMessage, ISessionManager, SessionConfig } from '@cassicore/foundation'
import type { IPluginHost } from '@cassicore/foundation'

/** Minimal duck-type for the new SessionPipeline — no circular dep needed. */
interface SessionPipelineLike {
  processTurn(
    sessionId: string,
    content: string,
    options?: { channelId?: string; senderId?: string; signal?: AbortSignal },
  ): Promise<{ response: string; sessionId: string; tokensUsed?: number }>
}

// Extended Wiring Dependencies for Heart Module

export interface HeartWiringDependencies extends Partial<WiringDependencies> {
  // REMOVED: pipeline deleted — SessionPipeline is always wired at boot
  /** SessionPipeline — required for heartbeat execution. */
  sessionPipeline?: SessionPipelineLike
  sessionManager?: ISessionManager
  pluginHost?: IPluginHost
  workspaceRoot?: string
}

// Heart Module Implementation

export class HeartModule extends BaseCognitiveModule {
  readonly name = 'heart'
  readonly priority = 85

  private heartConfig: HeartConfig = { ...DEFAULT_HEART_CONFIG }
  // REMOVED: pipeline property deleted — SessionPipeline is always used
  private sessionPipeline?: SessionPipelineLike
  private sessionManager?: ISessionManager
  private pluginHost?: IPluginHost
  private workspaceRoot = process.cwd()

  // State
  private timer?: ReturnType<typeof setTimeout>
  private running = false
  private busy = false
  private cycleNumber = 0
  private startedAt = 0
  private lastBeatAt = 0
  private nextBeatAt = 0
  private consecutiveErrors = 0
  private readonly MAX_CONSECUTIVE_ERRORS = 5

  // State persistence key
  private readonly STATE_KEY = 'heart:state'

  constructor(logger: ILogger, modelConfig?: Partial<ModuleModelConfig>) {
    super(logger, modelConfig)
  }

  // Lifecycle

  override async init(): Promise<void> {
    await super.init()

    // Load config from config.json if available
    const jsonConfig = (this.config as any).get?.('intelligence.heart')
    if (jsonConfig) {
      this.heartConfig = { ...this.heartConfig, ...jsonConfig }
    }

    // Load persisted state
    await this.loadState()

    this.logger.info('[Heart] Initialized', {
      enabled: this.heartConfig.enabled,
      intervalMs: this.heartConfig.intervalMs,
      target: this.heartConfig.target,
    })
  }

  override async start(): Promise<void> {
    await super.start()

    if (!this.heartConfig.enabled) {
      this.logger.info('[Heart] Disabled in config — not starting')
      return
    }

    this.running = true
    this.startedAt = Date.now()

    // Schedule first beat with small random jitter (0-5s) to avoid thundering herd
    const jitter = Math.random() * 5000
    this.scheduleNextBeat(jitter)

    this.logger.info('[Heart] Started', {
      firstBeatIn: jitter + this.heartConfig.intervalMs,
      nextBeatAt: new Date(this.nextBeatAt).toISOString(),
    })
  }

  override async stop(): Promise<void> {
    this.running = false

    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = undefined
    }

    // Persist state
    await this.saveState()

    await super.stop()

    this.logger.info('[Heart] Stopped', {
      cyclesCompleted: this.cycleNumber,
      uptimeMs: Date.now() - this.startedAt,
    })
  }

  // Wiring

  override wire(deps: Partial<HeartWiringDependencies>): void {
    super.wire(deps)

    if (deps.memory) this.memory = deps.memory as IMemory
    // REMOVED: pipeline wiring deleted — SessionPipeline is always used
    if (deps.sessionPipeline) this.sessionPipeline = deps.sessionPipeline as SessionPipelineLike
    if (deps.sessionManager) this.sessionManager = deps.sessionManager as ISessionManager
    if (deps.pluginHost) this.pluginHost = deps.pluginHost as IPluginHost
    if (deps.workspaceRoot) this.workspaceRoot = deps.workspaceRoot
  }

  // Timer Management

  private scheduleNextBeat(jitter = 0): void {
    if (!this.running || this.busy) return

    const delay = this.heartConfig.intervalMs + jitter
    this.nextBeatAt = Date.now() + delay

    this.timer = setTimeout(() => {
      if (this.running && !this.busy) {
        void this.performHeartbeat()
      }
    }, delay)

    // Unref so the timer doesn't prevent process exit
    try { (this.timer as any).unref?.() } catch {}
  }

  // Heartbeat Execution

  private async performHeartbeat(): Promise<void> {
    if (this.busy) {
      this.logger.debug('[Heart] Skipping beat — busy')
      this.scheduleNextBeat()
      return
    }

    this.busy = true
    this.cycleNumber++
    const cycleStart = Date.now()

    try {
      this.logger.debug('[Heart] Performing heartbeat', { cycle: this.cycleNumber })

      // 1. Check active hours
      if (!this.isWithinActiveHours()) {
        this.logger.debug('[Heart] Skipping beat — outside active hours')
        this.emitSkippedEvent('outside_active_hours')
        this.scheduleNextBeat()
        return
      }

      // 2. Read HEARTBEAT.md
      const heartbeatFile = await readHeartbeatFile(this.workspaceRoot, this.heartConfig.heartbeatFilePath)

      // 3. Check if file is empty (only headers/whitespace)
      if (heartbeatFile.exists && heartbeatFile.isEmpty) {
        this.logger.debug('[Heart] Skipping beat — HEARTBEAT.md is empty')
        this.emitSkippedEvent('heartbeat_file_empty')
        this.scheduleNextBeat()
        return
      }

      // 4. Create or get dedicated session
      const sessionId = 'heart:beat'
      // REMOVED: legacy ensureSession() path deleted — SessionPipeline handles session creation

      // 5. Build heartbeat prompt
      const prompt = this.buildHeartbeatPrompt(heartbeatFile)

      // 6. Execute turn via pipeline
      const result = await this.executeTurn(sessionId, prompt)

      // 7. Parse response
      const parseResult = parseHeartbeatResponse(result.response, this.heartConfig.ackMaxChars)

      // 8. Build result object
      const beatResult: HeartbeatResult = {
        cycleNumber: this.cycleNumber,
        response: result.response,
        isOk: parseResult.isOk,
        alertContent: parseResult.alertContent,
        reasoning: parseResult.reasoning,
        durationMs: Date.now() - cycleStart,
        tokensUsed: result.tokensUsed,
      }

      // 9. Emit beat event
      this.emitBeatEvent(beatResult)

      // 10. Deliver to channel if not suppressed
      if (!parseResult.shouldSuppress && parseResult.alertContent) {
        await this.deliverToChannel(sessionId, parseResult.alertContent, parseResult.reasoning)
      }

      // Update state
      this.lastBeatAt = Date.now()
      this.consecutiveErrors = 0

      this.logger.info('[Heart] Beat completed', {
        cycle: this.cycleNumber,
        isOk: beatResult.isOk,
        delivered: !parseResult.shouldSuppress,
        durationMs: beatResult.durationMs,
        tokensUsed: beatResult.tokensUsed,
      })

    } catch (err) {
      this.consecutiveErrors++
      this.logger.error('[Heart] Heartbeat failed', {
        cycle: this.cycleNumber,
        error: String(err),
        consecutiveErrors: this.consecutiveErrors,
      })

      // Circuit breaker
      if (this.consecutiveErrors >= this.MAX_CONSECUTIVE_ERRORS) {
        this.logger.error('[Heart] Too many consecutive errors — backing off', {
          errors: this.consecutiveErrors,
          newIntervalMs: this.heartConfig.intervalMs * 2,
        })
        // Double interval (capped at 2 hours)
        const newInterval = Math.min(this.heartConfig.intervalMs * 2, 2 * 60 * 60 * 1000)
        this.heartConfig = { ...this.heartConfig, intervalMs: newInterval }
        this.consecutiveErrors = 0
      }

      this.emitBeatEvent({
        cycleNumber: this.cycleNumber,
        response: '',
        isOk: false,
        durationMs: Date.now() - cycleStart,
        tokensUsed: { input: 0, output: 0 },
        skippedReason: `error: ${String(err)}`,
      })

    } finally {
      this.busy = false
      this.scheduleNextBeat()
      await this.saveState()
    }
  }

  // Helper Methods

  private isWithinActiveHours(): boolean {
    const activeHours = this.heartConfig.activeHours
    if (!activeHours) return true

    const now = new Date()
    const [startHour, startMin] = activeHours.start.split(':').map(Number)
    const [endHour, endMin] = activeHours.end.split(':').map(Number)

    const currentTime = now.getHours() * 60 + now.getMinutes()
    const startTime = startHour * 60 + startMin
    const endTime = endHour * 60 + endMin

    // Handle overnight windows (e.g., 22:00 - 06:00)
    if (endTime < startTime) {
      return currentTime >= startTime || currentTime < endTime
    }

    return currentTime >= startTime && currentTime < endTime
  }

  private ensureSession(sessionId: string): { id: string; channelId: string } {
    if (!this.sessionManager) {
      throw new Error('[Heart] SessionManager not wired')
    }

    // Get or create session with stable ID
    const session = this.sessionManager.getOrCreateById(
      sessionId,
      'system',
      'heartbeat',
      { projectPath: this.workspaceRoot } as any,
    )

    return { id: session.id, channelId: session.channelId }
  }

  private buildHeartbeatPrompt(heartbeatFile: HeartbeatFileResult): string {
    let prompt = this.heartConfig.prompt

    if (heartbeatFile.exists && heartbeatFile.content) {
      prompt += `\n\n--- HEARTBEAT.md ---\n${heartbeatFile.content}\n--- END HEARTBEAT.md ---`
    }

    return prompt
  }

  private async executeTurn(
    sessionId: string,
    prompt: string,
  ): Promise<{ response: string; tokensUsed: { input: number; output: number } }> {
    // SessionPipeline is required — removed TurnPipeline fallback
    if (!this.sessionPipeline) {
      throw new Error('[Heart] SessionPipeline not wired — heartbeat cannot execute')
    }

    const result = await this.sessionPipeline.processTurn(sessionId, prompt, {
      channelId: 'system',
      senderId: 'heartbeat',
    })
    return {
      response: result.response,
      tokensUsed: {
        input: (result.tokensUsed as any)?.input ?? result.tokensUsed ?? 0,
        output: (result.tokensUsed as any)?.output ?? 0,
      },
    }
  }

  private async deliverToChannel(
    sessionId: string,
    content: string,
    reasoning?: string,
  ): Promise<void> {
    if (!this.pluginHost) {
      this.logger.debug('[Heart] PluginHost not wired — skipping delivery')
      return
    }

    const target = this.resolveDeliveryTarget()
    if (!target || target === 'none') {
      this.logger.debug('[Heart] Delivery target is "none" — skipping delivery')
      return
    }

    try {
      // Build delivery payload
      const payload = {
        sessionId,
        content: this.heartConfig.includeReasoning && reasoning
          ? `${reasoning}\n\n---\n\n${content}`
          : content,
        done: true,
        from: 'heartbeat',
      }

      this.pluginHost.send(target, payload)

      this.logger.info('[Heart] Delivered to channel', {
        target,
        contentLength: content.length,
      })

      // Emit delivered event
      try {
        (this.eventBus as any).emit({
          type: 'heart:delivered',
          cycleNumber: this.cycleNumber,
          target,
          contentLength: content.length,
          timestamp: new Date(),
        })
      } catch { /* ignore */ }

    } catch (err) {
      this.logger.error('[Heart] Delivery failed', {
        target,
        error: String(err),
      })
    }
  }

  private resolveDeliveryTarget(): string | null {
    const target = this.heartConfig.target

    if (target === 'none') {
      return 'none'
    }

    if (target === 'last') {
      // Find last external channel from recent sessions
      return this.findLastExternalChannel()
    }

    // Specific channel ID
    return target
  }

  private findLastExternalChannel(): string | null {
    if (!this.sessionManager) return null

    // Walk recent sessions to find last non-internal channel
    // This is a simplified implementation — in production you'd want
    // to track this more efficiently
    const sessionManager = this.sessionManager as any
    const sessions = sessionManager.sessions
    if (!sessions) return null

    // Get all sessions, sort by lastActiveAt, find first with external channel
    const sessionList = Array.from(sessions.values()) as Array<{ channelId: string; lastActiveAt?: number }>
    sessionList.sort((a, b) => (b.lastActiveAt || 0) - (a.lastActiveAt || 0))

    for (const session of sessionList) {
      const channelId = session.channelId
      if (channelId && !channelId.startsWith('heart:') && channelId !== 'system') {
        return channelId
      }
    }

    return null
  }

  // Event Emission

  private emitBeatEvent(result: HeartbeatResult): void {
    try {
      (this.eventBus as any).emit({
        type: 'heart:beat',
        cycleNumber: result.cycleNumber,
        isOk: result.isOk,
        durationMs: result.durationMs,
        tokensUsed: result.tokensUsed,
        timestamp: new Date(),
      })
    } catch { /* ignore */ }
  }

  private emitSkippedEvent(reason: string): void {
    try {
      (this.eventBus as any).emit({
        type: 'heart:skipped',
        cycleNumber: this.cycleNumber,
        reason,
        timestamp: new Date(),
      })
    } catch { /* ignore */ }
  }

  // State Persistence

  private async loadState(): Promise<void> {
    if (!this.memory) return

    try {
      const state = await this.memory.kv_get<HeartState>(this.STATE_KEY)
      if (state) {
        this.cycleNumber = state.cycleNumber || 0
        this.lastBeatAt = state.lastBeatAt || 0
        this.nextBeatAt = state.nextBeatAt || 0
      }
    } catch (err) {
      this.logger.debug('[Heart] Failed to load state', { error: String(err) })
    }
  }

  private async saveState(): Promise<void> {
    if (!this.memory) return

    try {
      const state: HeartState = {
        cycleNumber: this.cycleNumber,
        lastBeatAt: this.lastBeatAt,
        nextBeatAt: this.nextBeatAt,
        totalDeliveries: 0, // Would track this if needed
        totalSkips: 0,
      }
      await this.memory.kv_set(this.STATE_KEY, state)
    } catch (err) {
      this.logger.debug('[Heart] Failed to save state', { error: String(err) })
    }
  }

  // Public API for Monitoring

  getStatus(): {
    running: boolean
    busy: boolean
    cycleNumber: number
    lastBeatAt?: number
    nextBeatAt?: number
    consecutiveErrors: number
    config: HeartConfig
  } {
    return {
      running: this.running,
      busy: this.busy,
      cycleNumber: this.cycleNumber,
      lastBeatAt: this.lastBeatAt,
      nextBeatAt: this.nextBeatAt,
      consecutiveErrors: this.consecutiveErrors,
      config: { ...this.heartConfig },
    }
  }

  /** Trigger an immediate heartbeat (for testing/admin API) */
  async triggerNow(): Promise<void> {
    if (this.busy) {
      this.logger.debug('[Heart] Skipping manual trigger — busy')
      return
    }

    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = undefined
    }

    await this.performHeartbeat()
  }
}

// Factory Export

export default function createHeartModule(
  logger: ILogger,
  modelConfig?: Partial<ModuleModelConfig>,
): HeartModule {
  return new HeartModule(logger, modelConfig)
}
