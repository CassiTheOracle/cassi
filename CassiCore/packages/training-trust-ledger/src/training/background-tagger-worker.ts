/**
 * BackgroundTaggerWorker — autonomous LLM-powered annotation for the training warehouse.
 *
 * Runs on a configurable interval, selecting untagged objects and annotating them
 * through the Copilot SDK tool loop. Each tick processes one batch via the SdkTagger,
 * which gives the model tools (get_batch, submit_annotations) and runs them in a
 * single premium request.
 *
 * Lifecycle: instantiate once, call start(), call stop() on shutdown.
 *
 * Configuration via environment variables:
 *   TAGGER_BG_INTERVAL_MS  - Tick interval (default: 120000 = 2 min)
 *   TAGGER_BG_BATCH_SIZE   - Objects per SDK batch (default: 20)
 *   TAGGER_BG_MODEL        - Model to use (default: claude-opus-4.6)
 *   TAGGER_BG_SCOPE        - Scope to tag (default: cycles through message, chunk, turn)
 *
 * @dep callers: boot-pipeline-tools.ts, admin-api/training.ts
 * @dep module: Training
 */

import type { ILogger } from '../../../types/interfaces.js'
import { SdkTagger } from './sdk-tagger.js'
import type { SdkTaggerResult } from './sdk-tagger.js'
import { TrainingStore } from './training-store.js'

const TICK_INTERVAL_MS = Number(process.env.TAGGER_BG_INTERVAL_MS || '120000') // 2 min
const BATCH_SIZE = Number(process.env.TAGGER_BG_BATCH_SIZE || '20')
const MODEL = process.env.TAGGER_BG_MODEL || 'claude-opus-4.6'

// WHY: Cycle through scopes so all object types get tagged, not just one scope.
const SCOPE_CYCLE: Array<'message' | 'chunk'> = ['message', 'chunk']

export interface BackgroundTaggerStats {
  isRunning: boolean
  totalTagged: number
  totalSkipped: number
  totalFailed: number
  totalLabels: number
  totalMetrics: number
  totalTokens: number
  totalTicks: number
  lastTickAt: number | null
  lastTickDurationMs: number
  lastTickTagged: number
  lastTickScope: string | null
  model: string
  scopeIndex: number
  errors: string[]
}

export class BackgroundTaggerWorker {
  private logger: ILogger
  private store: TrainingStore
  private sdkProvider: any // CopilotSdkProvider — typed loosely to avoid circular deps
  private timer: NodeJS.Timeout | null = null
  private running = false
  private ticking = false
  private scopeIdx = 0

  private stats: BackgroundTaggerStats = {
    isRunning: false,
    totalTagged: 0,
    totalSkipped: 0,
    totalFailed: 0,
    totalLabels: 0,
    totalMetrics: 0,
    totalTokens: 0,
    totalTicks: 0,
    lastTickAt: null,
    lastTickDurationMs: 0,
    lastTickTagged: 0,
    lastTickScope: null,
    model: MODEL,
    scopeIndex: 0,
    errors: [],
  }

  constructor(store: TrainingStore, sdkProvider: any, logger: ILogger) {
    this.store = store
    this.sdkProvider = sdkProvider
    this.logger = logger.child?.('bg-tagger-worker') ?? logger
  }

  // LIFECYCLE

  start(): void {
    if (this.running) return
    this.running = true
    this.stats.isRunning = true

    this.logger.info('BackgroundTaggerWorker: started', {
      intervalMs: TICK_INTERVAL_MS,
      batchSize: BATCH_SIZE,
      model: MODEL,
      scopes: SCOPE_CYCLE,
    })

    // WHY: Delay first tick to let the daemon fully initialize
    setTimeout(() => this.tick(), 30_000)

    // Schedule recurring ticks
    this.timer = setInterval(() => this.tick(), TICK_INTERVAL_MS)
  }

  stop(): void {
    this.running = false
    this.stats.isRunning = false
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
    this.logger.info('BackgroundTaggerWorker: stopped', {
      totalTagged: this.stats.totalTagged,
      totalFailed: this.stats.totalFailed,
    })
  }

  getStats(): BackgroundTaggerStats {
    return { ...this.stats, errors: [...this.stats.errors.slice(-10)] }
  }

  /** Manually trigger a tick (for admin API). */
  async triggerTick(opts?: { scope?: string; batchSize?: number; model?: string }): Promise<SdkTaggerResult | null> {
    return this.tick(opts?.scope as any, opts?.batchSize, opts?.model)
  }

  // TICK — main processing loop

  private async tick(
    overrideScope?: 'message' | 'chunk',
    overrideBatchSize?: number,
    overrideModel?: string,
  ): Promise<SdkTaggerResult | null> {
    if (this.ticking || !this.running) return null
    if (!this.sdkProvider) {
      this.logger.debug('BackgroundTaggerWorker: SDK provider not available, skipping tick')
      return null
    }

    this.ticking = true
    const tickStart = Date.now()
    const scope = overrideScope ?? SCOPE_CYCLE[this.scopeIdx % SCOPE_CYCLE.length]
    const batchSize = overrideBatchSize ?? BATCH_SIZE
    const model = overrideModel ?? MODEL

    this.stats.lastTickScope = scope

    try {
      // Check if there are untagged objects for this scope
      const remaining = this.countUntagged(scope)
      if (remaining === 0) {
        // Advance scope and check the next one
        this.scopeIdx++
        const nextScope = SCOPE_CYCLE[this.scopeIdx % SCOPE_CYCLE.length]
        const nextRemaining = this.countUntagged(nextScope)

        if (nextRemaining === 0) {
          this.logger.info('BackgroundTaggerWorker: all objects tagged across all scopes')
          return null
        }

        // Recurse with the next scope
        this.ticking = false
        return this.tick(nextScope, batchSize, model)
      }

      this.logger.info('BackgroundTaggerWorker: starting tick', {
        scope,
        batchSize,
        model,
        remaining,
      })

      const sdkTagger = new SdkTagger(this.store, this.logger)
      sdkTagger.setProvenance(model, 'copilot-sdk')

      const tools = sdkTagger.buildTools({ batchSize, scope, minContentLength: 20 })
      const systemPrompt = sdkTagger.getSystemPrompt()
      const userPrompt = sdkTagger.getUserPrompt({ batchSize, scope })
      const sessionId = `bg_tagger_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

      const turnResult = await this.sdkProvider.executeStandaloneTurn(
        sessionId,
        userPrompt,
        systemPrompt,
        model,
        tools,
      )

      const result = sdkTagger.getResult()
      result.totalTokens = turnResult.tokensUsed || 0
      result.durationMs = Date.now() - tickStart

      // Update stats
      this.stats.totalTagged += result.tagged
      this.stats.totalSkipped += result.skipped
      this.stats.totalFailed += result.failed
      this.stats.totalLabels += result.labelsCreated
      this.stats.totalMetrics += result.metricsSet
      this.stats.totalTokens += result.totalTokens
      this.stats.totalTicks++
      this.stats.lastTickAt = tickStart
      this.stats.lastTickDurationMs = result.durationMs
      this.stats.lastTickTagged = result.tagged
      this.stats.scopeIndex = this.scopeIdx

      if (result.errors.length) {
        this.stats.errors.push(...result.errors)
        // Keep only last 50 errors
        if (this.stats.errors.length > 50) {
          this.stats.errors = this.stats.errors.slice(-50)
        }
      }

      this.logger.info('BackgroundTaggerWorker: tick completed', {
        scope,
        tagged: result.tagged,
        failed: result.failed,
        labels: result.labelsCreated,
        tokens: result.totalTokens,
        durationMs: result.durationMs,
        totalTaggedSoFar: this.stats.totalTagged,
      })

      // Advance scope for next tick
      this.scopeIdx++

      return result
    } catch (err) {
      const errMsg = String(err)
      this.stats.totalFailed++
      this.stats.errors.push(`tick_error: ${errMsg}`)
      this.logger.error('BackgroundTaggerWorker: tick failed', {
        scope,
        error: errMsg,
      })
      // Advance scope to avoid getting stuck on one that always fails
      this.scopeIdx++
      return null
    } finally {
      this.ticking = false
    }
  }

  // HELPERS

  private countUntagged(scope: string): number {
    const types = scope === 'message' ? ['message']
      : scope === 'chunk' ? ['message', 'reasoning_step', 'event', 'artifact', 'memory', 'insight', 'pattern']
      : scope === 'turn' ? ['turn']
      : scope === 'session' ? ['session']
      : []

    if (!types.length) return 0

    const placeholders = types.map(() => '?').join(',')
    const row = this.store.db.prepare(`
      SELECT COUNT(*) as cnt FROM objects o
      WHERE o.object_type IN (${placeholders})
        AND NOT EXISTS (
          SELECT 1 FROM object_labels ol
          WHERE ol.object_id = o.object_id AND ol.source = 'llm'
        )
    `).get(...types) as { cnt: number }

    return row?.cnt ?? 0
  }
}
