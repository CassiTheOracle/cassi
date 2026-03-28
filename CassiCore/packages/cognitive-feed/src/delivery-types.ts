/**
 * Delivery system types for the cognitive feed batching pipeline.
 *
 * Controls how events flow from curation to Telegram delivery, with
 * load-aware batching, per-lane freeze semantics, and emergency bypass
 * for critical messages.
 *
 * Design invariants:
 *  - Under normal load, all events are delivered immediately (current behavior)
 *  - Batching only activates when load increases (busy/congested/rate-limited)
 *  - Critical lane is never frozen — errors always get through
 *  - Emergency token bucket allows high-priority events to bypass frozen lanes
 *  - Hysteresis prevents load tier oscillation (separate up/down thresholds + dwell time)
 */

// ── Delivery mode ──

/** How an individual message should be delivered */
export type DeliveryMode = 'immediate' | 'batched' | 'digest' | 'drop'

// ── Load state machine ──

/** System-wide load tiers — determines batching aggressiveness */
export type LoadState = 'normal' | 'busy' | 'congested' | 'rate-limited'

// ── Delivery lanes ──

/**
 * Delivery lane — groups messages for per-lane freeze/batch control.
 *
 *  critical:       Errors, budget exhausted, self-healer — always delivered
 *  highlight:      Main chat highlights — batched under load but never frozen
 *  orchestration:  Lumen/Dyad/Team topic messages — frozen under congestion
 *  intelligence:   Thinker/Dialectic — frozen under congestion
 *  constellation:  Constellation & Consciousness — immediate delivery, never frozen
 *  routine:        Memory, heart, LLM calls, routine updates — frozen under congestion
 */
export type DeliveryLane =
  | 'critical'
  | 'highlight'
  | 'orchestration'
  | 'intelligence'
  | 'constellation'
  | 'routine'

// ── Batch policy ──

/** Policy for a specific delivery lane */
export interface BatchPolicy {
  /** Lane identifier */
  lane: DeliveryLane
  /** Base batch window in ms (only applies when load > normal) */
  batchWindowMs: number
  /** Multiplier applied per load tier */
  loadMultipliers: Record<LoadState, number>
  /** Max events before forced flush */
  maxBatchSize: number
  /** Whether this lane can be frozen under congestion/rate-limited */
  freezable: boolean
  /** Whether events in this lane can be coalesced into edits (future) */
  coalescible: boolean
}

// ── Load thresholds ──

/** Load tier transition thresholds with hysteresis */
export interface LoadThresholds {
  /** Queue depth to enter 'busy' (up transition) */
  busyUp: number
  /** Queue depth to leave 'busy' (down transition — must be < busyUp) */
  busyDown: number
  /** Queue depth to enter 'congested' (up transition) */
  congestedUp: number
  /** Queue depth to leave 'congested' (down transition — must be < congestedUp) */
  congestedDown: number
  /** Minimum dwell time before tier transitions (ms) */
  dwellTimeMs: number
}

// ── Delivery config ──

/** Configuration for the delivery system */
export interface DeliveryConfig {
  /** Load tier thresholds with hysteresis */
  loadThresholds: LoadThresholds
  /** Emergency token bucket: max tokens available */
  emergencyBucketCapacity: number
  /** Emergency token bucket: refill rate (tokens per second) */
  emergencyBucketRefillRate: number
  /** Emergency token bucket: token TTL — decay if unused (ms) */
  emergencyBucketTtlMs: number
  /** Per-lane batch policies */
  policies: BatchPolicy[]
}

// ── Defaults ──

/** Default batch policies per lane */
export const DEFAULT_POLICIES: BatchPolicy[] = [
  {
    lane: 'critical',
    batchWindowMs: 0,
    loadMultipliers: { normal: 1, busy: 1, congested: 1, 'rate-limited': 1 },
    maxBatchSize: 1,
    freezable: false,
    coalescible: false,
  },
  {
    lane: 'highlight',
    batchWindowMs: 2_000,
    loadMultipliers: { normal: 1, busy: 2, congested: 5, 'rate-limited': 10 },
    maxBatchSize: 10,
    freezable: false,
    coalescible: true,
  },
  {
    lane: 'orchestration',
    batchWindowMs: 5_000,
    loadMultipliers: { normal: 1, busy: 2, congested: 4, 'rate-limited': 8 },
    maxBatchSize: 15,
    freezable: true,
    coalescible: true,
  },
  {
    lane: 'intelligence',
    batchWindowMs: 10_000,
    loadMultipliers: { normal: 1, busy: 3, congested: 6, 'rate-limited': 12 },
    maxBatchSize: 20,
    freezable: true,
    coalescible: true,
  },
  {
    lane: 'constellation',
    batchWindowMs: 0,
    loadMultipliers: { normal: 1, busy: 1, congested: 1, 'rate-limited': 1 },
    maxBatchSize: 1,
    freezable: false,
    coalescible: false,
  },
  {
    lane: 'routine',
    batchWindowMs: 15_000,
    loadMultipliers: { normal: 1, busy: 4, congested: 8, 'rate-limited': 15 },
    maxBatchSize: 30,
    freezable: true,
    coalescible: true,
  },
]

/** Default load thresholds with hysteresis gap */
export const DEFAULT_LOAD_THRESHOLDS: LoadThresholds = {
  busyUp: 20,
  busyDown: 10,
  congestedUp: 50,
  congestedDown: 30,
  dwellTimeMs: 30_000,
}

/** Default delivery config */
export const DEFAULT_DELIVERY_CONFIG: DeliveryConfig = {
  loadThresholds: DEFAULT_LOAD_THRESHOLDS,
  emergencyBucketCapacity: 10,
  emergencyBucketRefillRate: 0.2, // 1 token every 5 seconds
  emergencyBucketTtlMs: 60_000,
  policies: DEFAULT_POLICIES,
}
