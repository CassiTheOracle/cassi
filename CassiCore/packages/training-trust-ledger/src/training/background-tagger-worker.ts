/**
 * BackgroundTaggerWorker — autonomous LLM-powered annotation for the training warehouse.
 *
 * Runs as a continuous loop rather than a timer-based tick system. Each session is a
 * single long-lived SDK turn that keeps calling get_batch → submit_annotations until
 * get_batch returns empty. When the session terminates (model finished, timeout, or
 * API limit), the loop immediately starts a new session for the remaining objects.
 * This minimises the number of SDK requests — ideally one session per full scope pass.
 *
 * WHY continuous loop over setInterval: each setInterval tick was a new SDK request
 * even if the previous one finished early. The loop chains sessions with zero idle
 * time and stops cleanly when nothing is left to tag.
 *
 * Lifecycle: instantiate once, call start(), call stop() on shutdown.
 *
 * Configuration via environment variables:
 *   TAGGER_BG_BATCH_SIZE      - Objects per SDK batch (default: 20)
 *   TAGGER_BG_MODEL           - Model to use (default: claude-opus-4.6)
 *   TAGGER_BG_SESSION_TIMEOUT - Per-session timeout in ms (default: 3600000 = 1h)
 *   TAGGER_BG_INITIAL_DELAY   - Delay before first session (default: 30000 = 30s)
 *
 * @dep callers: boot-pipeline-tools.ts, admin-api/training.ts
 * @dep module: Training
 */

import type { ILogger } from '../../../types/interfaces.js'
import { SdkTagger } from './sdk-tagger.js'
import type { SdkTaggerResult } from './sdk-tagger.js'
import { TrainingStore } from './training-store.js'

const BATCH_SIZE = Number(process.env.TAGGER_BG_BATCH_SIZE || '20')
const MODEL = process.env.TAGGER_BG_MODEL || 'claude-opus-4.6'
const SESSION_TIMEOUT_MS = Number(process.env.TAGGER_BG_SESSION_TIMEOUT || '3600000') // 1h
const INITIAL_DELAY_MS = Number(process.env.TAGGER_BG_INITIAL_DELAY || '30000') // 30s

// WHY: Cycle through scopes so all object types get tagged, not just one scope.
const SCOPE_CYCLE: Array<'message' | 'chunk'> = ['message', 'chunk']

// WHY: If this many consecutive sessions tag 0 objects, stop — either done or broken.
const MAX_ZERO_STREAK = SCOPE_CYCLE.length

export interface BackgroundTaggerStats {
  isRunning: boolean
  totalTagged: number
  totalSkipped: number
  totalFailed: number
  totalLabels: number
  totalMetrics: number
  totalTokens: number
  totalSessions: number
  lastSessionAt: number | null
  lastSessionDurationMs: number
  lastSessionTagged: number
  lastSessionScope: string | null
  model: string
  scopeIndex: number
  errors: string[]
}

export class BackgroundTaggerWorker {
  private logger: ILogger
  private store: TrainingStore
  private sdkProvider: any // CopilotSdkProvider — typed loosely to avoid circular deps
  private running = false
  private sessionActive = false
  private scopeIdx = 0

  private stats: BackgroundTaggerStats = {
    isRunning: false,
    totalTagged: 0,
    totalSkipped: 0,
    totalFailed: 0,
    totalLabels: 0,
    totalMetrics: 0,
    totalTokens: 0,
    totalSessions: 0,
    lastSessionAt: null,
    lastSessionDurationMs: 0,
    lastSessionTagged: 0,
    lastSessionScope: null,
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
      batchSize: BATCH_SIZE,
      model: MODEL,
      sessionTimeoutMs: SESSION_TIMEOUT_MS,
      scopes: SCOPE_CYCLE,
    })

    // WHY: Delay first session to let the daemon fully initialize before heavy SDK work.
    setTimeout(() => this.runLoop(), INITIAL_DELAY_MS)
  }

  stop(): void {
    this.running = false
    this.stats.isRunning = false
    this.logger.info('BackgroundTaggerWorker: stopped', {
      totalTagged: this.stats.totalTagged,
      totalFailed: this.stats.totalFailed,
    })
  }

  getStats(): BackgroundTaggerStats {
    return { ...this.stats, errors: [...this.stats.errors.slice(-10)] }
  }

  /** Manually trigger one session (for admin API). Blocks until the session ends. */
  async triggerSession(opts?: { scope?: string; batchSize?: number; model?: string }): Promise<SdkTaggerResult | null> {
    if (this.sessionActive) {
      this.logger.warn('BackgroundTaggerWorker: session already active, ignoring triggerSession')
      return null
    }
    return this.runSession(
      (opts?.scope as 'message' | 'chunk') ?? SCOPE_CYCLE[this.scopeIdx % SCOPE_CYCLE.length],
      opts?.batchSize ?? BATCH_SIZE,
      opts?.model ?? MODEL,
    )
  }

  // LOOP — replaces the old setInterval tick system

  private async runLoop(): Promise<void> {
    let zeroStreak = 0

    while (this.running) {
      if (!this.sdkProvider) {
        this.logger.debug('BackgroundTaggerWorker: SDK provider not available, waiting 30s')
        await sleep(30_000)
        continue
      }

      const scope = SCOPE_CYCLE[this.scopeIdx % SCOPE_CYCLE.length]
      const remaining = this.countUntagged(scope)

      if (remaining === 0) {
        // Advance to the next scope
        this.scopeIdx++
        zeroStreak++

        if (zeroStreak >= MAX_ZERO_STREAK) {
          this.logger.info('BackgroundTaggerWorker: all taggable objects annotated — loop complete')
          this.running = false
          this.stats.isRunning = false
          return
        }
        continue
      }

      zeroStreak = 0

      const result = await this.runSession(scope, BATCH_SIZE, MODEL)
      if (!result) {
        // Session failed — advance scope to avoid retrying the same failing scope
        this.scopeIdx++
      } else if (result.tagged === 0) {
        // Session ran but tagged nothing (unexpected — countUntagged said > 0)
        // Advance scope to break potential infinite loop
        this.scopeIdx++
        zeroStreak++
      }
      // If result.tagged > 0, stay on same scope — there may be more to tag
    }
  }

  // SESSION — one SDK turn that runs until the model calls get_batch and gets empty

  private async runSession(
    scope: 'message' | 'chunk',
    batchSize: number,
    model: string,
  ): Promise<SdkTaggerResult | null> {
    if (this.sessionActive) return null

    this.sessionActive = true
    const sessionStart = Date.now()
    this.stats.lastSessionScope = scope

    try {
      const remaining = this.countUntagged(scope)
      this.logger.info('BackgroundTaggerWorker: starting session', {
        scope,
        batchSize,
        model,
        remaining,
        sessionTimeoutMs: SESSION_TIMEOUT_MS,
      })

      const sdkTagger = new SdkTagger(this.store, this.logger)
      sdkTagger.setProvenance(model, 'copilot-sdk')

      const tools = sdkTagger.buildTools({ batchSize, scope, minContentLength: BackgroundTaggerWorker.MIN_CONTENT_LENGTH })
      const systemPrompt = sdkTagger.getSystemPrompt()
      const userPrompt = sdkTagger.getUserPrompt({ batchSize, scope })
      const sessionId = `bg_tagger_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

      const turnResult = await this.sdkProvider.executeStandaloneTurn(
        sessionId,
        userPrompt,
        systemPrompt,
        model,
        tools,
        undefined, // onStream
        SESSION_TIMEOUT_MS,
      )

      const result = sdkTagger.getResult()
      result.totalTokens = turnResult.tokensUsed || 0
      result.durationMs = Date.now() - sessionStart

      // Update stats
      this.stats.totalTagged += result.tagged
      this.stats.totalSkipped += result.skipped
      this.stats.totalFailed += result.failed
      this.stats.totalLabels += result.labelsCreated
      this.stats.totalMetrics += result.metricsSet
      this.stats.totalTokens += result.totalTokens
      this.stats.totalSessions++
      this.stats.lastSessionAt = sessionStart
      this.stats.lastSessionDurationMs = result.durationMs
      this.stats.lastSessionTagged = result.tagged
      this.stats.scopeIndex = this.scopeIdx

      if (result.errors.length) {
        this.stats.errors.push(...result.errors)
        if (this.stats.errors.length > 50) {
          this.stats.errors = this.stats.errors.slice(-50)
        }
      }

      this.logger.info('BackgroundTaggerWorker: session completed', {
        scope,
        tagged: result.tagged,
        failed: result.failed,
        labels: result.labelsCreated,
        tokens: result.totalTokens,
        durationMs: result.durationMs,
        totalTaggedSoFar: this.stats.totalTagged,
      })

      return result
    } catch (err) {
      const errMsg = String(err)
      this.stats.totalFailed++
      this.stats.errors.push(`session_error: ${errMsg}`)
      this.logger.error('BackgroundTaggerWorker: session failed', {
        scope,
        error: errMsg,
      })
      return null
    } finally {
      this.sessionActive = false
    }
  }

  // HELPERS

  private static readonly MIN_CONTENT_LENGTH = 20

  private countUntagged(scope: string): number {
    const types = scope === 'message' ? ['message']
      : scope === 'chunk' ? ['message', 'reasoning_step', 'event', 'artifact', 'memory', 'insight', 'pattern']
      : scope === 'turn' ? ['turn']
      : scope === 'session' ? ['session']
      : []

    if (!types.length) return 0

    const placeholders = types.map(() => '?').join(',')
    const minLen = BackgroundTaggerWorker.MIN_CONTENT_LENGTH

    // WHY: Count only objects that have extractable content meeting the minimum length.
    // This matches the SQL filter in SdkTagger.selectAndExtractBatch so the loop
    // guard accurately reflects what the tagger can actually tag.
    const row = this.store.db.prepare(`
      SELECT COUNT(*) as cnt FROM objects o
      WHERE o.object_type IN (${placeholders})
        AND NOT EXISTS (
          SELECT 1 FROM object_labels ol
          WHERE ol.object_id = o.object_id AND ol.source = 'llm'
        )
        AND (
          EXISTS (SELECT 1 FROM messages m WHERE m.object_id = o.object_id AND length(m.content_text) >= ${minLen})
          OR EXISTS (SELECT 1 FROM chunks c WHERE c.object_id = o.object_id AND length(c.text) >= ${minLen})
          OR EXISTS (SELECT 1 FROM reasoning_steps rs WHERE rs.object_id = o.object_id AND length(rs.content) >= ${minLen})
          OR EXISTS (SELECT 1 FROM reasoning_traces rt WHERE rt.object_id = o.object_id AND (length(rt.synthesis) >= ${minLen} OR length(rt.decision) >= ${minLen}))
          OR EXISTS (SELECT 1 FROM events e WHERE e.object_id = o.object_id)
        )
    `).get(...types) as { cnt: number }

    return row?.cnt ?? 0
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}
