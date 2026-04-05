/**
 * DreamerModule — Idle-time memory synthesis cognitive module.
 *
 * Activates when the daemon has been idle (no turns) for `idleThresholdMs`.
 * Samples the memory archive, runs a multi-phase dream cycle via LLM, stores
 * new semantic insights, retires distilled episodic memories to deep archive,
 * and surfaces the most recent dream insight into the turn context window.
 *
 * Priority: 15 (background — below AI Scientist, above Self Healer)
 */

import { MODEL_DEFAULTS } from '../../config/system-settings.js'
import { BaseCognitiveModule } from '../base/cognitive-module.js'
import type { MemoryModule } from '../memory/index.js'
import type { ReasoningBank } from '../reasoning-bank/index.js'
import type { InjectionAggregator, InjectionSource } from '../injection-aggregator.js'
import { DreamCycleEngine } from './dream-engine.js'
import type { DreamRecord, DreamerConfig } from './types.js'
import { DEFAULT_DREAMER_CONFIG } from './types.js'

import type { ILogger } from '../../../types/interfaces.js'


export type DreamerState =
  | 'idle'          // waiting for idle threshold
  | 'dreaming'      // dream cycle in progress
  | 'stopped'       // module stopped


export class DreamerModule extends BaseCognitiveModule {
  readonly name = 'dreamer'
  readonly priority = 15

  private dreamerConfig: DreamerConfig = { ...DEFAULT_DREAMER_CONFIG }
  private state: DreamerState = 'idle'

  /** Timestamp (ms) of the last completed turn. Updated by onTurnEnd. */
  private lastTurnAt = 0

  /** Timestamp (ms) of the last completed dream cycle. */
  private lastDreamAt = 0

  /** History of completed dream cycles (in-memory, last 20). */
  private dreamHistory: DreamRecord[] = []

  /** Latest dream insight text for context injection. */
  private latestInsightText: string | undefined

  private checkTimer?: NodeJS.Timeout

  /** Full MemoryModule reference (extends IMemory with dream-specific methods). */
  private fullMemory?: MemoryModule

  /** Reasoning Bank for cross-session reasoning synthesis. */
  private reasoningBank?: ReasoningBank

  constructor(logger: ILogger, config?: Partial<DreamerConfig>) {
    super(logger, {
      providerId: MODEL_DEFAULTS.reasoning.provider,
      model: MODEL_DEFAULTS.reasoning.model,
    })
    if (config) this.dreamerConfig = { ...DEFAULT_DREAMER_CONFIG, ...config }
  }


  override async start(): Promise<void> {
    await super.start()
    if (!this.dreamerConfig.enabled) {
      this.logger.info('[Dreamer] Disabled by config — not starting idle check loop')
      return
    }
    this.startIdleCheckLoop()
    this.logger.info('[Dreamer] Started idle-check loop', {
      checkIntervalMs: this.dreamerConfig.checkIntervalMs,
      idleThresholdMs: this.dreamerConfig.idleThresholdMs,
    })
  }

  override async stop(): Promise<void> {
    this.state = 'stopped'
    if (this.checkTimer) {
      clearInterval(this.checkTimer)
      this.checkTimer = undefined
    }
    await super.stop()
  }


  /**
   * Wire in the full MemoryModule (not just IMemory) for dream-specific methods.
   * Called by createIntelligence() after module instantiation.
   */
  setFullMemory(module: MemoryModule): void {
    this.fullMemory = module
    // Also set the base class IMemory reference
    this.setMemory(module)
  }

  /**
   * Wire in the ReasoningBank for reasoning trace synthesis during dream cycles.
   * Called by createIntelligence() after module instantiation.
   */
  setReasoningBank(bank: ReasoningBank): void {
    this.reasoningBank = bank
  }

  /**
   * Register this module as an InjectionSource so recent dream insights
   * are surfaced in the turn context window.
   */
  registerWithInjectionAggregator(aggregator: InjectionAggregator): void {
    const source: InjectionSource = {
      name: 'dreamer',
      priority: 20,
      getInjection: async (_sessionId: string) => this.getContextInjection(),
    }
    aggregator.register(source)
  }


  protected override async onTurnEnd(
    _sessionId: string,
    _response: string,
    _durationMs: number,
  ): Promise<void> {
    this.lastTurnAt = Date.now()
  }


  private startIdleCheckLoop(): void {
    this.checkTimer = setInterval(
      () => { void this.checkAndDream() },
      this.dreamerConfig.checkIntervalMs,
    )
    // Don't block process exit
    if (this.checkTimer.unref) this.checkTimer.unref()
  }

  private async checkAndDream(): Promise<void> {
    if (this.state !== 'idle') return
    if (!this.dreamerConfig.enabled) return

    const idleMs = Date.now() - this.lastTurnAt
    if (idleMs < this.dreamerConfig.idleThresholdMs) {
      this.emit({
        type: 'dreamer:dream-skipped',
        reason: 'not-idle',
        idleMs,
        thresholdMs: this.dreamerConfig.idleThresholdMs,
      } as any)
      return
    }

    if (!this.fullMemory) {
      this.emit({ type: 'dreamer:dream-skipped', reason: 'no-memory' } as any)
      return
    }

    if (!this.provider) {
      this.emit({ type: 'dreamer:dream-skipped', reason: 'provider-unavailable' } as any)
      return
    }

    await this.runDreamCycle()
  }


  /**
   * Trigger a dream cycle immediately.
   * Safe to call externally (e.g. from admin API).
   * Returns the resulting DreamRecord or null if skipped/failed.
   */
  async triggerDream(): Promise<DreamRecord | null> {
    if (this.state === 'dreaming') {
      this.logger.info('[Dreamer] Dream already in progress — ignoring trigger')
      return null
    }
    if (!this.fullMemory) {
      this.logger.warn('[Dreamer] No memory module — cannot dream')
      return null
    }
    return this.runDreamCycle()
  }

  private async runDreamCycle(): Promise<DreamRecord | null> {
    this.state = 'dreaming'

    const engine = new DreamCycleEngine(
      (prompt) => this.infer(prompt),
      <T>(prompt: string) => this.inferJSON<T>(prompt),
      this.fullMemory!,
      this.logger,
      this.reasoningBank,
    )

    try {
      this.emit({
        type: 'dreamer:dream-started',
        timestamp: Date.now(),
      } as any)

      const record = await engine.runCycle(this.dreamerConfig)
      this.lastDreamAt = Date.now()

      // Keep recent dream history
      this.dreamHistory.unshift(record)
      if (this.dreamHistory.length > 20) this.dreamHistory.pop()

      // Store dream record in archive
      const content = this.buildDreamSummary(record)
      this.fullMemory!.archiveDream(content, {
        insightsCreated: record.insightsCreated,
        episodicsRetired: record.episodicsRetired,
        linksCreated: record.linksCreated,
        archiveEntriesProcessed: record.archiveEntriesProcessed,
        durationMs: record.durationMs,
        startedAt: record.startedAt,
      })

      // Update latest insight for context injection
      if (record.topInsightContent) {
        this.latestInsightText = record.topInsightContent
      }

      this.emit({
        type: 'dreamer:dream-completed',
        dreamId: record.id,
        insightsCreated: record.insightsCreated.length,
        episodicsRetired: record.episodicsRetired.length,
        linksCreated: record.linksCreated,
        durationMs: record.durationMs,
        timestamp: Date.now(),
      } as any)

      return record
    } catch (err) {
      this.logger.error('[Dreamer] Dream cycle failed', { error: String(err) })
      return null
    } finally {
      this.state = 'idle'
    }
  }


  /** Returns the latest dream insight text if within the injection window. */
  private getContextInjection(): string | null {
    if (!this.dreamerConfig.injectContextEnabled) return null
    if (!this.latestInsightText) return null

    const windowMs = this.dreamerConfig.injectContextWindowHours * 3_600_000
    const lastDream = this.dreamHistory[0]
    if (!lastDream || Date.now() - lastDream.startedAt > windowMs) return null

    return `[Dream Insight] ${this.latestInsightText}`
  }


  /** Get current module state for the admin API. */
  getStatus(): {
    state: DreamerState
    enabled: boolean
    lastTurnAt: number
    lastDreamAt: number
    idleMs: number
    idleThresholdMs: number
    dreamsCompleted: number
    config: DreamerConfig
  } {
    return {
      state: this.state,
      enabled: this.dreamerConfig.enabled,
      lastTurnAt: this.lastTurnAt,
      lastDreamAt: this.lastDreamAt,
      idleMs: Date.now() - this.lastTurnAt,
      idleThresholdMs: this.dreamerConfig.idleThresholdMs,
      dreamsCompleted: this.dreamHistory.length,
      config: this.dreamerConfig,
    }
  }

  /** Get in-memory history of recent dream cycles. */
  getHistory(limit = 20): DreamRecord[] {
    return this.dreamHistory.slice(0, limit)
  }

  /** Update dreamer config at runtime. */
  updateConfig(updates: Partial<DreamerConfig>): void {
    this.dreamerConfig = { ...this.dreamerConfig, ...updates }
    this.logger.info('[Dreamer] Config updated', updates as Record<string, unknown>)
  }


  private buildDreamSummary(record: DreamRecord): string {
    const date = new Date(record.startedAt).toISOString()
    return [
      `Dream cycle — ${date}`,
      `Duration: ${(record.durationMs / 1000).toFixed(1)}s`,
      `Processed: ${record.archiveEntriesProcessed.length} archive entries`,
      `Created: ${record.insightsCreated.length} new insights`,
      `Retired: ${record.episodicsRetired.length} episodic memories to deep archive`,
      `Links: ${record.linksCreated} conceptual links created`,
      record.rawAnalysis ? `\nAnalysis:\n${record.rawAnalysis.slice(0, 800)}` : '',
    ].filter(Boolean).join('\n')
  }
}


/**
 * @dep callers: dreamer.test.ts (tests/dreamer.test.ts), createIntelligence (core/intelligence/index.ts)
 * @dep module: Intelligence
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function createDreamer(logger: ILogger, config?: Partial<DreamerConfig>): DreamerModule {
  return new DreamerModule(logger, config)
}
