/**
 * Event Accumulator — Rate-limits high-volume events for the cognitive feed.
 *
 * Sits between the event bus and the topic posting layer. Batchable events
 * (dialectic messages, iteration progress, work stream items) are accumulated
 * per (sessionId, eventPrefix) and flushed as digest messages every N seconds.
 *
 * Non-batchable events (completions, errors, high-priority items) pass through
 * immediately.
 */

import type { ILogger } from '@cassicore/foundation'


/** An event payload as seen by the cognitive feed layer */
export interface AccumulatorEvent {
  type: string
  sessionId?: string
  [key: string]: unknown
}

/** Callback invoked when events should be posted to a topic */
export type FlushCallback = (events: AccumulatorEvent[]) => void

/**
 * Prefixes that are batchable — accumulated and flushed periodically.
 * All other events pass through immediately.
 */
const BATCHABLE_PREFIXES = [
  'lumen:dialectic:',
  'lumen:posture:iteration',
  'lumen:posture:progress',
  'dyad:work-unit',
  'dyad:refinement',
  'dyad:nudge',
  'dyad:research',
  'dyad:guidance',
  'dyad:posture:iteration',
  'provider:request_chunk',
  'tool:executed',
  'turn:start',
  'turn:end',
]

/**
 * Event types that always pass through immediately regardless of batching,
 * even if they match a batchable prefix.
 */
const PASSTHROUGH_TYPES = new Set([
  'lumen:dialectic:executive-injection',
  'lumen:dialectic:executive-steering',
  'dyad:quality-assessment',
])

/**
 * Completion events that trigger an immediate flush of all pending batches
 * for that session, then pass through themselves.
 */
const FLUSH_TRIGGERS = new Set([
  'lumen:completed',
  'lumen:persisted',
  'dyad:completed',
  'dyad:failed',
  'team:completed',
  'team:failed',
])

interface BatchBucket {
  events: AccumulatorEvent[]
  lastFlush: number
}


export class EventAccumulator {
  /** Buckets keyed by `${sessionId}::${prefix}` */
  private readonly buckets = new Map<string, BatchBucket>()

  /** Flush interval handle */
  private timer: ReturnType<typeof setInterval> | null = null

  /** Flush interval in ms */
  private readonly flushIntervalMs: number

  /** Maximum events to hold in a single bucket before forcing a flush */
  private readonly maxBucketSize: number

  private readonly logger: ILogger
  private readonly onFlush: FlushCallback

  constructor(opts: {
    logger: ILogger
    onFlush: FlushCallback
    flushIntervalMs?: number
    maxBucketSize?: number
  }) {
    this.logger = opts.logger.child('event-accumulator')
    this.onFlush = opts.onFlush
    this.flushIntervalMs = opts.flushIntervalMs ?? 15_000
    this.maxBucketSize = opts.maxBucketSize ?? 20
  }

  /** Start the periodic flush timer */
  start(): void {
    if (this.timer) return
    this.timer = setInterval(() => this.flushAll(), this.flushIntervalMs)
    // Allow the process to exit even if this timer is running
    if (this.timer && typeof this.timer === 'object' && 'unref' in this.timer) {
      this.timer.unref()
    }
  }

  /** Stop the periodic flush timer and flush all remaining events */
  stop(): void {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
    this.flushAll()
  }

  /**
   * Process an event. Returns true if the event was accumulated (caller
   * should NOT post it). Returns false if the event should pass through
   * (caller should post it immediately).
   */
  accumulate(event: AccumulatorEvent): boolean {
    const type = event.type

    // Flush triggers: flush all pending for this session, then pass through
    if (FLUSH_TRIGGERS.has(type)) {
      this.flushSession(event.sessionId)
      return false // pass through
    }

    // Always-passthrough types bypass batching
    if (PASSTHROUGH_TYPES.has(type)) {
      return false // pass through
    }

    // Check if this event type is batchable
    const matchedPrefix = BATCHABLE_PREFIXES.find(p => type.startsWith(p))
    if (!matchedPrefix) {
      return false // not batchable, pass through
    }

    // Accumulate into the appropriate bucket
    const sessionKey = event.sessionId ?? '_global'
    const bucketKey = `${sessionKey}::${matchedPrefix}`

    let bucket = this.buckets.get(bucketKey)
    if (!bucket) {
      bucket = { events: [], lastFlush: Date.now() }
      this.buckets.set(bucketKey, bucket)
    }

    bucket.events.push(event)

    // Force flush if bucket is too large
    if (bucket.events.length >= this.maxBucketSize) {
      this.flushBucket(bucketKey, bucket)
    }

    return true // accumulated, don't pass through
  }

  /** Flush all buckets */
  private flushAll(): void {
    for (const [key, bucket] of this.buckets) {
      if (bucket.events.length > 0) {
        this.flushBucket(key, bucket)
      }
    }
  }

  /** Flush all buckets for a specific session */
  private flushSession(sessionId?: string): void {
    const prefix = `${sessionId ?? '_global'}::`
    for (const [key, bucket] of this.buckets) {
      if (key.startsWith(prefix) && bucket.events.length > 0) {
        this.flushBucket(key, bucket)
      }
    }
  }

  /** Flush a single bucket — creates a digest event from accumulated events */
  private flushBucket(key: string, bucket: BatchBucket): void {
    const events = bucket.events.splice(0)
    bucket.lastFlush = Date.now()

    if (events.length === 0) return

    // Clean up empty buckets
    if (bucket.events.length === 0) {
      this.buckets.delete(key)
    }

    // Determine the digest type based on the event types
    const firstType = events[0].type
    const digestType = this.getDigestType(firstType)
    const sessionId = events[0].sessionId

    // Create a digest event that summarizes the batch
    const digest: AccumulatorEvent = {
      type: digestType,
      sessionId,
      batchSize: events.length,
      events,
      summary: this.buildDigestSummary(events),
      timestamp: Date.now(),
    }

    try {
      this.onFlush([digest])
    } catch (err) {
      this.logger.warn('Failed to flush event batch', {
        key,
        batchSize: events.length,
        error: String(err),
      })
    }
  }

  /** Map an event type to its digest type */
  private getDigestType(type: string): string {
    if (type.startsWith('lumen:dialectic:')) return 'lumen:dialectic:digest'
    if (type.startsWith('lumen:posture:iteration')) return 'lumen:iteration:digest'
    if (type.startsWith('lumen:posture:progress')) return 'lumen:progress:digest'
    if (type.startsWith('dyad:work-unit')) return 'dyad:work-stream:digest'
    if (type.startsWith('dyad:refinement')) return 'dyad:work-stream:digest'
    if (type.startsWith('dyad:nudge')) return 'dyad:work-stream:digest'
    if (type.startsWith('dyad:research')) return 'dyad:work-stream:digest'
    if (type.startsWith('dyad:guidance')) return 'dyad:work-stream:digest'
    if (type.startsWith('dyad:posture:iteration')) return 'dyad:iteration:digest'
    if (type.startsWith('provider:request_chunk')) return 'provider:stream:digest'
    if (type.startsWith('tool:executed')) return 'tool:execution:digest'
    if (type.startsWith('turn:')) return 'session:turn:digest'
    return `${type}:digest`
  }

  /** Build a human-readable summary of the batch */
  private buildDigestSummary(events: AccumulatorEvent[]): string {
    // Count by sub-type
    const counts = new Map<string, number>()
    for (const e of events) {
      const shortType = e.type.split(':').pop() ?? e.type
      counts.set(shortType, (counts.get(shortType) ?? 0) + 1)
    }

    const parts: string[] = []
    for (const [key, count] of counts) {
      parts.push(`${count} ${key}${count > 1 ? 's' : ''}`)
    }

    return parts.join(', ')
  }

  /** Get the current number of pending events across all buckets */
  getPendingCount(): number {
    let count = 0
    for (const bucket of this.buckets.values()) {
      count += bucket.events.length
    }
    return count
  }

  /** Get the number of active buckets */
  getBucketCount(): number {
    return this.buckets.size
  }
}
