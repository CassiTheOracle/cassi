/**
 * DeliveryBatcher — Load-aware batching layer for the cognitive feed.
 *
 * Sits between the EventCurator and the RateLimiter. Under normal load,
 * all events are delivered immediately (preserving current behavior).
 * When load increases, events are batched per-lane with increasing
 * windows to reduce Telegram API pressure.
 *
 * Key features:
 *  - Load state machine with hysteresis (normal → busy → congested → rate-limited)
 *  - Per-lane batch policies with configurable windows and freeze semantics
 *  - Emergency token bucket for high-priority events in frozen lanes
 *  - Stats and observability for /status reporting
 *
 * Design constraints from Lumen review:
 *  - Per-lane freeze, NOT global freeze — critical/highlight lanes never frozen
 *  - Emergency token bucket with TTL-based decay
 *  - Hysteresis with minimum 30s dwell time and separate up/down thresholds
 *  - RateLimiter observability hooks for load state decisions
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { CuratedEvent } from './event-curator.js'
import type {
  DeliveryConfig,
  DeliveryLane,
  LoadState,
  BatchPolicy,
} from './delivery-types.js'
import { DEFAULT_DELIVERY_CONFIG } from './delivery-types.js'


/**
 * Read-only view of the RateLimiter's state, consumed by the DeliveryBatcher
 * for load state decisions. The RateLimiter implements this implicitly via
 * its public getters.
 */
export interface RateLimiterObservability {
  readonly queueDepth: number
  readonly isBackingOff: boolean
  readonly recent429Count: number
}


/**
 * Called by the DeliveryBatcher when events should be sent to Telegram.
 *
 * @param events  The curated events to deliver
 * @param mode    'single' = deliver each individually (normal formatting),
 *                'digest' = combine into a batch digest message
 */
export type DeliverCallback = (events: CuratedEvent[], mode: 'single' | 'digest') => void


/**
 * Leaky token bucket for emergency bypass of frozen lanes.
 * Tokens refill at a steady rate and decay if unused for TTL.
 */
class EmergencyTokenBucket {
  private tokens: number
  private lastRefillTime: number
  private lastUsedTime: number
  private readonly capacity: number
  private readonly refillRate: number  // tokens per second
  private readonly ttlMs: number

  constructor(capacity: number, refillRate: number, ttlMs: number) {
    this.capacity = capacity
    this.tokens = capacity // start full
    this.refillRate = refillRate
    this.ttlMs = ttlMs
    this.lastRefillTime = Date.now()
    this.lastUsedTime = Date.now()
  }

  /** Try to consume one token. Returns true if consumed. */
  tryConsume(): boolean {
    this.refill()
    if (this.tokens >= 1) {
      this.tokens -= 1
      this.lastUsedTime = Date.now()
      return true
    }
    return false
  }

  /** Current available tokens (after refill). */
  get available(): number {
    this.refill()
    return Math.floor(this.tokens)
  }

  private refill(): void {
    const now = Date.now()
    const elapsed = (now - this.lastRefillTime) / 1000
    this.tokens = Math.min(this.capacity, this.tokens + elapsed * this.refillRate)
    this.lastRefillTime = now

    /**
     * Decay tokens if unused for longer than TTL.
     * Purpose: Prevent emergency tokens from accumulating indefinitely during idle periods.
     * When a bucket sits unused (no successful consumptions), tokens decay to 50% capacity.
     * This prevents a scenario where old emergency reserves can be consumed long after
     * the urgent event that justified them has passed.
     * The 50% cap ensures some emergency capacity remains available for the next urgent event.
     */
    if (now - this.lastUsedTime > this.ttlMs) {
      this.tokens = Math.min(this.tokens, this.capacity * 0.5)
    }
  }
}


interface LaneBucket {
  events: CuratedEvent[]
  lastFlush: number
}


const TOPIC_TO_LANE: Record<string, DeliveryLane> = {
  // Constellation War Room — real-time visibility, dedicated lane
  constellation: 'constellation',

  // Intelligence — reasoning and awareness
  intelligence:  'intelligence',

  // Memory — dreams, archive, heart
  memory:        'routine',

  // System — operational health
  system:        'routine',

  // Sessions — user lifecycle
  sessions:      'routine',
}

/** Event types that are always on the critical lane regardless of topic */
const CRITICAL_EVENT_TYPES = new Set([
  'provider:request_error',
  'provider:request_timeout',
  'provider:rate_limited',
  'self-healer:repair',
  'budget:warning',
  'budget:exhausted',
  'team:failed',
  'dyad:failed',
  'lumen:posture:error',
  'triad-team:failed',
  'multi-agent:spawn-failed',
  'agent:error',
])


export interface DeliveryStats {
  eventsReceived: number
  eventsDelivered: number
  eventsDropped: number
  batchesDelivered: number
  emergencyTokensUsed: number
  loadTransitions: number
  loadState: LoadState
  emergencyTokensAvailable: number
  pendingByLane: Record<string, number>
}


export class DeliveryBatcher {
  private readonly config: DeliveryConfig
  private readonly logger: ILogger
  private readonly onDeliver: DeliverCallback
  private readonly lanes = new Map<DeliveryLane, LaneBucket>()
  private readonly policyMap = new Map<DeliveryLane, BatchPolicy>()
  private readonly emergencyBucket: EmergencyTokenBucket

  private loadState: LoadState = 'normal'
  private lastTransitionTime = Date.now()
  private rateLimiterObs: RateLimiterObservability | null = null
  private timer: ReturnType<typeof setInterval> | null = null

  // Counters
  private _eventsReceived = 0
  private _eventsDelivered = 0
  private _eventsDropped = 0
  private _batchesDelivered = 0
  private _emergencyTokensUsed = 0
  private _loadTransitions = 0

  constructor(
    config: Partial<DeliveryConfig>,
    onDeliver: DeliverCallback,
    logger: ILogger,
  ) {
    this.config = { ...DEFAULT_DELIVERY_CONFIG, ...config }
    this.onDeliver = onDeliver
    this.logger = logger.child('delivery-batcher')

    // Build policy lookup and initialize lane buckets
    for (const policy of this.config.policies) {
      this.policyMap.set(policy.lane, policy)
      this.lanes.set(policy.lane, { events: [], lastFlush: Date.now() })
    }

    // Initialize emergency bucket with TTL
    this.emergencyBucket = new EmergencyTokenBucket(
      this.config.emergencyBucketCapacity,
      this.config.emergencyBucketRefillRate,
      this.config.emergencyBucketTtlMs,
    )
  }


  /** Connect to the RateLimiter for load-state observability. */
  setRateLimiterObservability(obs: RateLimiterObservability): void {
    this.rateLimiterObs = obs
  }

  /** Start the periodic flush timer. */
  start(): void {
    if (this.timer) return
    // Check every second for flushable batches and load-state changes
    this.timer = setInterval(() => this.tick(), 1_000)
    if (this.timer && typeof this.timer === 'object' && 'unref' in this.timer) {
      this.timer.unref()
    }
    this.logger.debug('[delivery-batcher] Started')
  }

  /** Stop and flush all remaining batched events. */
  stop(): void {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
    // Flush all remaining events before shutdown
    for (const lane of this.lanes.keys()) {
      this.flushLane(lane)
    }
    this.logger.debug('[delivery-batcher] Stopped', { ...this.getStats() })
  }


  /**
   * Accept a curated event for delivery.
   *
   * Under normal load, events are delivered immediately.
   * Under elevated load, events are batched per-lane.
   * Critical events always bypass batching.
   */
  accept(curated: CuratedEvent): void {
    this._eventsReceived++

    const lane = this.assignLane(curated)
    const policy = this.policyMap.get(lane)

    // Critical events or unknown lanes → deliver immediately
    if (lane === 'critical' || !policy) {
      this.deliverImmediate([curated])
      return
    }

    // Under normal load, deliver immediately (preserves current behavior)
    if (this.loadState === 'normal') {
      this.deliverImmediate([curated])
      return
    }

    // Check if lane is frozen (freezable lanes in congested/rate-limited state)
    const isFrozen = policy.freezable &&
      (this.loadState === 'congested' || this.loadState === 'rate-limited')

    if (isFrozen && curated.priority === 'high') {
      // High-priority events in frozen lanes can consume an emergency token
      if (this.emergencyBucket.tryConsume()) {
        this._emergencyTokensUsed++
        this.logger.debug('[delivery-batcher] Emergency bypass', {
          lane, eventType: (curated.event as any).type,
        })
        this.deliverImmediate([curated])
        return
      }
      // No tokens available — fall through to batch
    }

    // Add to lane batch
    const bucket = this.lanes.get(lane)!
    bucket.events.push(curated)

    // Force flush if batch is full
    if (bucket.events.length >= policy.maxBatchSize) {
      this.flushLane(lane)
    }
  }


  /** Get the current load state. */
  getLoadState(): LoadState {
    return this.loadState
  }

  /** Get delivery statistics for /status reporting. */
  getStats(): DeliveryStats {
    const pendingByLane: Record<string, number> = {}
    for (const [lane, bucket] of this.lanes) {
      if (bucket.events.length > 0) {
        pendingByLane[lane] = bucket.events.length
      }
    }
    return {
      eventsReceived: this._eventsReceived,
      eventsDelivered: this._eventsDelivered,
      eventsDropped: this._eventsDropped,
      batchesDelivered: this._batchesDelivered,
      emergencyTokensUsed: this._emergencyTokensUsed,
      loadTransitions: this._loadTransitions,
      loadState: this.loadState,
      emergencyTokensAvailable: this.emergencyBucket.available,
      pendingByLane,
    }
  }


  private assignLane(curated: CuratedEvent): DeliveryLane {
    const eventType = (curated.event as any).type as string

    // Critical events override everything
    if (CRITICAL_EVENT_TYPES.has(eventType)) return 'critical'

    // Constellation and all consciousness-related events use dedicated lane for real-time visibility
    if (eventType.startsWith('constellation:')) return 'constellation'
    if (eventType.startsWith('consciousness:')) return 'constellation'
    if (eventType.startsWith('subconscious:')) return 'constellation'
    if (eventType.startsWith('axon:')) return 'constellation'
    if (eventType.startsWith('synapse:')) return 'constellation'
    if (eventType.startsWith('brainstem:')) return 'constellation'
    if (eventType.startsWith('corpus:')) return 'constellation'

    // Highlights without a topic go to highlight lane (main chat)
    if (curated.isHighlight && curated.topicKey === null) return 'highlight'

    // Route by topic
    if (curated.topicKey) {
      return TOPIC_TO_LANE[curated.topicKey] ?? 'routine'
    }

    // Highlights with a topic go to highlight lane for the main chat copy
    if (curated.isHighlight) return 'highlight'

    return 'routine'
  }


  private tick(): void {
    this.updateLoadState()

    const now = Date.now()
    for (const [lane, bucket] of this.lanes) {
      if (bucket.events.length === 0) continue

      const policy = this.policyMap.get(lane)
      if (!policy) continue

      // Don't flush frozen lanes
      const isFrozen = policy.freezable &&
        (this.loadState === 'congested' || this.loadState === 'rate-limited')
      if (isFrozen) continue

      // Calculate effective batch window with load multiplier
      const multiplier = policy.loadMultipliers[this.loadState] ?? 1
      const effectiveWindow = policy.batchWindowMs * multiplier

      const elapsed = now - bucket.lastFlush
      if (elapsed >= effectiveWindow) {
        this.flushLane(lane)
      }
    }
  }


  /**
   * Update the load state based on RateLimiter observability.
   *
   * Hysteresis rules:
   *  - Separate up/down thresholds prevent oscillation
   *  - Minimum dwell time (default 30s) before any transition
   *  - 429 backoff immediately escalates to rate-limited (ignores dwell)
   */
  private updateLoadState(): void {
    const now = Date.now()
    const queueDepth = this.rateLimiterObs?.queueDepth ?? 0
    const is429 = this.rateLimiterObs?.isBackingOff ?? false
    const thresholds = this.config.loadThresholds
    const dwellElapsed = now - this.lastTransitionTime

    // 429 backoff → immediate escalation to rate-limited (ignores dwell)
    if (is429 && this.loadState !== 'rate-limited') {
      this.transitionTo('rate-limited', queueDepth, is429)
      return
    }

    // Must dwell for minimum time before transitioning
    if (dwellElapsed < thresholds.dwellTimeMs) return

    let newState = this.loadState

    switch (this.loadState) {
      case 'normal':
        if (queueDepth >= thresholds.congestedUp) newState = 'congested'
        else if (queueDepth >= thresholds.busyUp) newState = 'busy'
        break
      case 'busy':
        if (queueDepth >= thresholds.congestedUp) newState = 'congested'
        else if (queueDepth < thresholds.busyDown) newState = 'normal'
        break
      case 'congested':
        if (queueDepth < thresholds.busyDown) newState = 'normal'
        else if (queueDepth < thresholds.congestedDown) newState = 'busy'
        break
      case 'rate-limited':
        if (!is429) {
          if (queueDepth < thresholds.busyDown) newState = 'normal'
          else if (queueDepth < thresholds.congestedDown) newState = 'busy'
          else newState = 'congested'
        }
        break
    }

    if (newState !== this.loadState) {
      this.transitionTo(newState, queueDepth, is429)
    }
  }

  private transitionTo(newState: LoadState, queueDepth: number, is429: boolean): void {
    const oldState = this.loadState
    this.loadState = newState
    this.lastTransitionTime = Date.now()
    this._loadTransitions++

    this.logger.info('[delivery-batcher] Load state transition', {
      from: oldState,
      to: newState,
      queueDepth,
      is429,
    })

    // When transitioning DOWN from a frozen state, flush all previously-frozen lanes
    if (this.isLowerState(newState, oldState)) {
      this.flushUnfrozenLanes()
    }
  }

  /** Returns true if `a` is a lower (less severe) state than `b`. */
  private isLowerState(a: LoadState, b: LoadState): boolean {
    const order: Record<LoadState, number> = {
      'normal': 0, 'busy': 1, 'congested': 2, 'rate-limited': 3,
    }
    return order[a] < order[b]
  }

  /** Flush all lanes that were frozen but are now unfrozen. */
  private flushUnfrozenLanes(): void {
    for (const [lane, bucket] of this.lanes) {
      if (bucket.events.length === 0) continue
      const policy = this.policyMap.get(lane)
      if (!policy?.freezable) continue

      // If the lane is no longer frozen at the current load state, flush it
      const stillFrozen = policy.freezable &&
        (this.loadState === 'congested' || this.loadState === 'rate-limited')
      if (!stillFrozen) {
        this.flushLane(lane)
      }
    }
  }


  private flushLane(lane: DeliveryLane): void {
    const bucket = this.lanes.get(lane)
    if (!bucket || bucket.events.length === 0) return

    const events = bucket.events.splice(0)
    bucket.lastFlush = Date.now()

    if (events.length === 1) {
      this.deliverImmediate(events)
    } else {
      this.deliverBatch(events)
    }
  }

  private deliverImmediate(events: CuratedEvent[]): void {
    try {
      this.onDeliver(events, 'single')
      this._eventsDelivered += events.length
    } catch (err) {
      this.logger.warn('[delivery-batcher] Delivery failed', {
        count: events.length, error: String(err),
      })
    }
  }

  private deliverBatch(events: CuratedEvent[]): void {
    try {
      this.onDeliver(events, 'digest')
      this._eventsDelivered += events.length
      this._batchesDelivered++
    } catch (err) {
      this.logger.warn('[delivery-batcher] Batch delivery failed', {
        count: events.length, error: String(err),
      })
    }
  }
}
