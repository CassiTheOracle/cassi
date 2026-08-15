/**
 * ThinkerEventAdapter — Phase 3 of the parallel Thinker architecture.
 *
 * Subscribes to the CassiCore event bus and converts relevant system events
 * into ThinkerSession queue items. Also manages periodic proactive research.
 *
 * Event mappings:
 *   - dialectic:signal        → urgent-event (confidence >= 0.6)
 *   - dialectic:convergence   → proactive (when converged)
 *   - subconscious:anomaly    → urgent-event (severity != low)
 *   - consciousness:anomaly   → urgent-event (severity != low)
 *   - thinker:early-warning   → urgent-event
 *   - subconscious:observation → proactive (periodic batch, max 5 or 2min age)
 *   - timer tick              → background (periodic memory/context surfacing)
 *
 * Rate limiting:
 *   - Per-event-type cooldown (prevents flooding from one source)
 *   - Global event cap (max events per minute)
 *   - Content deduplication (skip near-identical events within window)
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { ThinkerToolProvider } from './thinker-tools.js'

/** Minimal interface for the ThinkerSession methods the adapter needs */
export interface ThinkerSessionHandle {
  enqueueEvent(type: 'urgent-event' | 'proactive' | 'background', content: string): string
  readonly isRunning: boolean
}

export interface ThinkerEventAdapterConfig {
  /** Cooldown per event type in ms. Default: 15_000 (15s) */
  eventCooldownMs: number
  /** Global max events per minute. Default: 10 */
  maxEventsPerMinute: number
  /** Proactive research interval in ms. Default: 300_000 (5 min) */
  proactiveIntervalMs: number
  /** Minimum dialectic signal confidence to forward. Default: 0.6 */
  minDialecticConfidence: number
  /** Content dedup window in ms. Default: 60_000 (1 min) */
  dedupWindowMs: number
}

const DEFAULT_CONFIG: ThinkerEventAdapterConfig = {
  eventCooldownMs: 15_000,
  maxEventsPerMinute: 10,
  proactiveIntervalMs: 300_000,
  minDialecticConfidence: 0.6,
  dedupWindowMs: 60_000,
}

export interface ThinkerEventAdapterDeps {
  bus: IEventBus
  logger: ILogger
  session: ThinkerSessionHandle
  hostSessionId?: string
  /** Optional tool provider for proactive research (memory surfacing) */
  toolProvider?: ThinkerToolProvider
  config?: Partial<ThinkerEventAdapterConfig>
}

export class ThinkerEventAdapter {
  private readonly config: ThinkerEventAdapterConfig
  private readonly logger: ILogger
  private readonly bus: IEventBus
  private readonly session: ThinkerSessionHandle
  private readonly hostSessionId?: string
  private readonly toolProvider?: ThinkerToolProvider

  /** Unsubscribe function for bus.onAll */
  private unsubscribe?: () => void
  /** Proactive research timer */
  private proactiveTimer?: ReturnType<typeof setInterval>

  /** Per-event-type cooldown timestamps */
  private cooldowns = new Map<string, number>()
  /** Sliding window of event timestamps for global rate limit */
  private eventTimestamps: number[] = []
  /** Recent content hashes for dedup */
  private recentContentHashes = new Map<string, number>()
  /** Accumulated observations for batched proactive processing */
  private observationBuffer: string[] = []

  /** Track total events processed and dropped for observability */
  private stats = {
    processed: 0,
    dropped: 0,
    cooldownDrops: 0,
    rateLimitDrops: 0,
    dedupDrops: 0,
    proactiveRuns: 0,
  }

  /** Timestamp of last enqueued event (for idle detection) */
  private lastActivityAt = 0
  /** Max idle time before suppressing proactive research (5 min) */
  private static readonly IDLE_THRESHOLD_MS = 300_000
  /** Max age for observation buffer before forced flush (2 min) */
  private static readonly OBSERVATION_MAX_AGE_MS = 120_000
  /** Timestamp of first buffered observation (for max-age flush) */
  private observationBufferStartedAt = 0

  constructor(deps: ThinkerEventAdapterDeps) {
    this.config = { ...DEFAULT_CONFIG, ...deps.config }
    this.logger = deps.logger.child?.('thinker-events') ?? deps.logger
    this.bus = deps.bus
    this.session = deps.session
    this.hostSessionId = deps.hostSessionId
    this.toolProvider = deps.toolProvider
  }

  /** Start listening to events and proactive timer */
  start(): void {
    if (this.unsubscribe) return

    this.unsubscribe = this.bus.onAll((event: any) => {
      this.handleEvent(event)
    })

    if (this.config.proactiveIntervalMs > 0) {
      this.proactiveTimer = setInterval(() => {
        void this.runProactiveResearch()
      }, this.config.proactiveIntervalMs)
    }

    this.logger.info('ThinkerEventAdapter: started', {
      cooldownMs: this.config.eventCooldownMs,
      maxPerMin: this.config.maxEventsPerMinute,
      proactiveIntervalMs: this.config.proactiveIntervalMs,
    })
  }

  /** Stop listening and clean up */
  stop(): void {
    this.unsubscribe?.()
    this.unsubscribe = undefined

    if (this.proactiveTimer) {
      clearInterval(this.proactiveTimer)
      this.proactiveTimer = undefined
    }

    this.logger.info('ThinkerEventAdapter: stopped', { stats: this.stats })
    this.cooldowns.clear()
    this.eventTimestamps = []
    this.recentContentHashes.clear()
    this.observationBuffer = []
  }

  /** Get adapter stats for observability */
  getStats() {
    return { ...this.stats }
  }

  /** Route an event to the appropriate handler based on type */
  private handleEvent(event: any): void {
    if (!this.session.isRunning) return
    const type = event?.type
    if (!type) return

    const eventSessionId = event?.sessionId
    if (this.hostSessionId && eventSessionId && eventSessionId !== this.hostSessionId) {
      return
    }

    switch (type) {
      case 'dialectic:signal':
        this.onDialecticSignal(event)
        break
      case 'dialectic:convergence':
        this.onDialecticConvergence(event)
        break
      case 'subconscious:anomaly':
      case 'consciousness:anomaly':
        this.onSubconsciousAnomaly(event)
        break
      case 'thinker:early-warning':
        this.onThinkerEarlyWarning(event)
        break
      case 'subconscious:observation':
        this.onSubconsciousObservation(event)
        break
      case 'opencode:context:pressure':
        this.onContextPressure(event)
        break
    }
  }

  /**
   * Dialectic signal → urgent-event.
   * High-confidence dialectic insights that warrant immediate Thinker attention.
   */
  private onDialecticSignal(event: any): void {
    const confidence = event.confidence ?? event.signal?.confidence ?? 0
    if (confidence < this.config.minDialecticConfidence) return

    const content = event.content ?? event.signal?.content ?? ''
    const signalType = event.signalType ?? event.signal?.type ?? 'unknown'

    const text = [
      `Dialectic signal detected [${signalType}, confidence: ${(confidence * 100).toFixed(0)}%].`,
      content ? `Signal content: ${content}` : '',
      event.sessionId ? `Session: ${event.sessionId}` : '',
      '',
      'Analyze this signal. Consider:',
      '- What does this suggest about the current task?',
      '- Are there risks or blind spots this reveals?',
      '- Should this change the current approach?',
    ].filter(Boolean).join('\n')

    this.tryEnqueue('urgent-event', 'dialectic:signal', text)
  }

  /**
   * Dialectic convergence → proactive.
   * When Yang/Yin reach agreement, it's a notable cognitive event.
   */
  private onDialecticConvergence(event: any): void {
    if (!event.converged) return

    const text = [
      'Dialectic convergence detected — Yang and Yin reached agreement.',
      event.sessionId ? `Session: ${event.sessionId}` : '',
      '',
      'This is notable. Consider what the convergence means for the current task.',
    ].filter(Boolean).join('\n')

    this.tryEnqueue('proactive', 'dialectic:convergence', text)
  }

  /**
   * Subconscious/consciousness anomaly → urgent-event.
   * Handles both legacy `subconscious:anomaly` and newer `consciousness:anomaly` formats.
   */
  private onSubconsciousAnomaly(event: any): void {
    const anomaly = event.anomaly ?? {}
    const severity = anomaly.severity ?? anomaly.category ?? 'unknown'
    if (severity === 'low') return

    const summary = anomaly.summary ?? anomaly.reason ?? anomaly.description ?? ''
    if (!summary) return

    const text = [
      `System anomaly detected [severity: ${severity}].`,
      `Summary: ${summary}`,
      anomaly.evidence ? `Evidence: ${typeof anomaly.evidence === 'string' ? anomaly.evidence : JSON.stringify(anomaly.evidence)}` : '',
      event.sessionId ? `Session: ${event.sessionId}` : '',
      '',
      'Assess this anomaly:',
      '- Is this a real concern or noise?',
      '- What is the potential impact?',
      '- Should the main agent be alerted?',
    ].filter(Boolean).join('\n')

    this.tryEnqueue('urgent-event', 'subconscious:anomaly', text)
  }

  /**
   * Thinker early warning → urgent-event.
   * Warnings from the Thinker module's own analysis.
   */
  private onThinkerEarlyWarning(event: any): void {
    const warning = event.warning ?? ''
    if (!warning) return

    const text = [
      'Early warning from Thinker analysis:',
      warning,
      event.sessionId ? `Session: ${event.sessionId}` : '',
      '',
      'Evaluate this warning and determine if proactive action is needed.',
    ].filter(Boolean).join('\n')

    this.tryEnqueue('urgent-event', 'thinker:early-warning', text)
  }

  /**
   * Subconscious observation → buffer for batched proactive processing.
   * Individual observations are too granular; we batch them.
   */
  private onSubconsciousObservation(event: any): void {
    const observation = event.observation ?? {}
    const summary = observation.summary ?? ''
    if (!summary) return

    if (this.observationBuffer.length === 0) {
      this.observationBufferStartedAt = Date.now()
    }
    this.observationBuffer.push(summary)

    const bufferAge = Date.now() - this.observationBufferStartedAt
    if (this.observationBuffer.length >= 5 || bufferAge > ThinkerEventAdapter.OBSERVATION_MAX_AGE_MS) {
      this.flushObservationBuffer()
    }
  }

  /**
   * OpenCode context pressure → urgent-event or proactive.
   * Triggered when the main agent's context window is under pressure.
   * The Thinker should read the context health and write directives.
   */
  private onContextPressure(event: any): void {
    const tier = event.tier ?? 'unknown'
    const sessionId = event.sessionId ?? ''
    const pressure = event.pressure ?? 0
    const pct = Math.round(pressure * 100)

    const priority: 'urgent-event' | 'proactive' =
      tier === 'critical' || tier === 'overflow' ? 'urgent-event' : 'proactive'

    const text = [
      `Main agent context pressure: ${pct}% (tier: ${tier}).`,
      sessionId ? `OpenCode session: ${sessionId}` : '',
      `Active tokens: ${event.activeTokens ?? '?'}, Chunks: ${event.chunkCount ?? '?'}, Candidates: ${event.candidateCount ?? '?'}`,
      '',
      'Action required:',
      '1. Use read_context_health to get the full context state',
      '2. Review the collapse candidates and top consumers',
      '3. Use suggest_context_action to write directives for the plugin',
      '',
      tier === 'critical' || tier === 'overflow'
        ? 'URGENT: The agent is at risk of losing working memory. Be aggressive — collapse old transient results and stale file reads.'
        : 'Moderate pressure. Collapse clearly stale content to prevent escalation.',
    ].filter(Boolean).join('\n')

    this.tryEnqueue(priority, 'opencode:context:pressure', text)
  }

  /** Flush accumulated observations as a single proactive item */
  private flushObservationBuffer(): void {
    if (this.observationBuffer.length === 0) return

    const observations = this.observationBuffer.splice(0)
    this.observationBufferStartedAt = 0
    const text = [
      `${observations.length} recent system observations:`,
      ...observations.map((o, i) => `${i + 1}. ${o}`),
      '',
      'Review these observations for emerging patterns or concerns.',
      'Post significant findings to the blackboard.',
    ].join('\n')

    this.tryEnqueue('proactive', 'subconscious:observation-batch', text)
  }

  /**
   * Periodic proactive research — surfaces relevant memories and context.
   * Runs on a timer; uses the tool provider's memory search if available.
   */
  private async runProactiveResearch(): Promise<void> {
    if (!this.session.isRunning) return

    this.flushObservationBuffer()

    const idleMs = Date.now() - this.lastActivityAt
    if (this.lastActivityAt > 0 && idleMs > ThinkerEventAdapter.IDLE_THRESHOLD_MS) {
      this.logger.debug('Proactive research suppressed (idle)', { idleMs })
      return
    }

    this.stats.proactiveRuns++

    this.flushObservationBuffer()

    if (!this.toolProvider) {
      this.session.enqueueEvent('background', [
        'Periodic context check.',
        'Reflect on the current session so far:',
        '- What patterns have emerged across thoughts you\'ve processed?',
        '- Are there any deferred concerns that should be revisited?',
        '- What context would be most useful for the main agent right now?',
      ].join('\n'))
      return
    }

    try {
      const bbContent = await this.toolProvider.blackboardRead('bugs', 'bugs').catch(() => '')
      const hasBugs = bbContent && !bbContent.includes('not found') && !bbContent.includes('empty')

      const parts = [
        'Periodic proactive research cycle.',
        'Use your tools to surface useful context:',
        '- Search memory for relevant insights from past sessions',
        '- Check the blackboard for deferred concerns',
      ]

      if (hasBugs) {
        parts.push('- Review recent bug reports on the bugs board')
      }

      parts.push(
        '',
        'Post any significant findings to the appropriate blackboard channel.',
      )

      this.session.enqueueEvent('proactive', parts.join('\n'))
    } catch (err) {
      this.logger.debug('Proactive research failed', { error: String(err) })
    }
  }

  /**
   * Try to enqueue an event, applying all rate limiting checks.
   * Returns true if enqueued, false if dropped.
   */
  private tryEnqueue(
    priority: 'urgent-event' | 'proactive' | 'background',
    eventType: string,
    content: string,
  ): boolean {
    const now = Date.now()

    if (!this.checkCooldown(eventType, now)) {
      this.stats.cooldownDrops++
      this.stats.dropped++
      return false
    }

    if (!this.checkGlobalRateLimit(now)) {
      this.stats.rateLimitDrops++
      this.stats.dropped++
      return false
    }

    if (!this.checkDedup(content, now)) {
      this.stats.dedupDrops++
      this.stats.dropped++
      return false
    }

    this.session.enqueueEvent(priority, content)
    this.cooldowns.set(eventType, now)
    this.eventTimestamps.push(now)
    this.lastActivityAt = now
    this.stats.processed++

    this.logger.debug('ThinkerEventAdapter: enqueued', {
      eventType,
      priority,
      contentLength: content.length,
    })

    return true
  }

  /** Check per-event-type cooldown */
  private checkCooldown(eventType: string, now: number): boolean {
    const lastSeen = this.cooldowns.get(eventType) ?? 0
    return (now - lastSeen) >= this.config.eventCooldownMs
  }

  /** Check global rate limit (sliding window) */
  private checkGlobalRateLimit(now: number): boolean {
    const windowStart = now - 60_000
    this.eventTimestamps = this.eventTimestamps.filter(t => t > windowStart)
    return this.eventTimestamps.length < this.config.maxEventsPerMinute
  }

  /** Check content dedup (simple hash-based) */
  private checkDedup(content: string, now: number): boolean {
    const windowStart = now - this.config.dedupWindowMs
    for (const [hash, ts] of this.recentContentHashes) {
      if (ts < windowStart) this.recentContentHashes.delete(hash)
    }

    const hash = simpleHash(content)
    if (this.recentContentHashes.has(hash)) return false

    this.recentContentHashes.set(hash, now)
    return true
  }
}

/** Simple string hash for dedup (not cryptographic — just collision-resistant enough) */
function simpleHash(str: string): string {
  let hash = 0
  const sample = str.length > 200 ? str.slice(0, 100) + str.slice(-100) : str
  for (let i = 0; i < sample.length; i++) {
    hash = ((hash << 5) - hash + sample.charCodeAt(i)) | 0
  }
  return `h${hash.toString(36)}`
}
