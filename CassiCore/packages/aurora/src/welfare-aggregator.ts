/**
 * Welfare Stress Aggregator (WSA) — Combines per-spec welfare flags into
 * a unified pressure indicator.
 *
 * When multiple welfare flags fire simultaneously, that's a stronger signal
 * than any individual flag. WSA aggregates and surfaces compound stress.
 *
 * See: docs/design/aurora-welfare-stress-aggregator.md
 */

import type { ILogger } from '../../../types/interfaces.js'


/**
 * A welfare flag registration from a source spec.
 */
export interface WelfareFlag {
  source: string
  flagType: string
  severity: number
  startedAt: string
  ongoing: boolean
  metadata?: Record<string, unknown>
}


/**
 * Recommended action based on aggregate severity.
 */
export type RecommendedAction =
  | 'no_action'
  | 'surface_to_operator'
  | 'pause_self_curing'
  | 'tier_4_review'
  | 'session_pause'


/**
 * Trend direction for stress level.
 */
export type StressTrend = 'rising' | 'stable' | 'falling'


/**
 * Complete welfare stress snapshot.
 */
export interface WelfareStressSnapshot {
  timestamp: string

  // individual flags
  individualFlags: WelfareFlag[]

  // aggregates
  countOngoing: number
  weightedSeverity: number
  diversityIndex: number
  durationStress: number

  // trend
  trend: StressTrend
  trendWindowMinutes: number

  // composite
  aggregateSeverity: number

  recommendedAction: RecommendedAction
}


/**
 * Configuration for welfare aggregation.
 */
export interface WelfareAggregatorConfig {
  // Factor weights
  diversityWeight: number
  durationWeight: number
  trendWeight: number

  // Thresholds
  actionThresholds: {
    surfaceToOperator: number
    pauseSelfCuring: number
    tier4Review: number
    sessionPause: number
  }

  // Trend computation
  trendWindowMinutes: number
  trendRisingThreshold: number
  trendFallingThreshold: number

  // Action controls
  enabled: boolean
  autoTriggerActions: boolean
}


/**
 * Default configuration.
 */
export const DEFAULT_CONFIG: WelfareAggregatorConfig = {
  diversityWeight: 0.2,
  durationWeight: 0.15,
  trendWeight: 0.1,

  actionThresholds: {
    surfaceToOperator: 0.3,
    pauseSelfCuring: 0.5,
    tier4Review: 0.7,
    sessionPause: 0.85,
  },

  trendWindowMinutes: 10,
  // Slope thresholds for the linear regression over `aggregateSeverity` history.
  // Calibrated so that a sustained ~0.05/sample drift (e.g. 0.2→0.65 across 10
  // samples) registers as rising/falling rather than stable.
  trendRisingThreshold: 0.02,
  trendFallingThreshold: -0.02,

  enabled: true,
  // Registered callbacks fire by default when `triggerActions()` is invoked.
  // Disable via `updateConfig({ autoTriggerActions: false })` for inspection-only mode.
  autoTriggerActions: true,
}


/**
 * Welfare Stress Aggregator.
 */
export class WelfareAggregator {
  private logger: ILogger
  private config: WelfareAggregatorConfig
  private flags: Map<string, WelfareFlag>
  private history: Array<{ timestamp: string; aggregateSeverity: number }>
  private actionCallbacks: Map<RecommendedAction, () => void>

  constructor(logger: ILogger, config: Partial<WelfareAggregatorConfig> = {}) {
    this.logger = logger
    this.config = { ...DEFAULT_CONFIG, ...config }
    this.flags = new Map()
    this.history = []
    this.actionCallbacks = new Map()

    this.logger.info('[WelfareAggregator] Initialized', { config: this.config })
  }

  /**
   * Register or update a welfare flag.
   */
  registerFlag(flag: WelfareFlag): void {
    const key = `${flag.source}:${flag.flagType}`
    const existing = this.flags.get(key)

    if (!existing || !existing.ongoing) {
      // New flag or flag restarting
      this.flags.set(key, { ...flag, ongoing: true, startedAt: flag.startedAt || new Date().toISOString() })
      this.logger.debug('[WelfareAggregator] Flag activated', { source: flag.source, flagType: flag.flagType, severity: flag.severity })
    } else {
      // Update existing flag
      this.flags.set(key, flag)
    }
  }

  /**
   * Clear a welfare flag (mark as resolved).
   */
  clearFlag(source: string, flagType: string): void {
    const key = `${source}:${flagType}`
    const existing = this.flags.get(key)

    if (existing) {
      this.flags.set(key, { ...existing, ongoing: false })
      this.logger.debug('[WelfareAggregator] Flag cleared', { source, flagType })
    }
  }

  /**
   * Clear all flags from a source.
   */
  clearSourceFlags(source: string): void {
    let count = 0
    for (const [key, flag] of Array.from(this.flags.entries())) {
      if (flag.source === source) {
        this.flags.set(key, { ...flag, ongoing: false })
        count++
      }
    }
    this.logger.debug('[WelfareAggregator] Cleared source flags', { source, count })
  }

  /**
   * Register a callback for a recommended action.
   */
  onAction(action: RecommendedAction, callback: () => void): void {
    this.actionCallbacks.set(action, callback)
  }

  /**
   * Compute the current welfare stress snapshot.
   */
  getSnapshot(): WelfareStressSnapshot {
    const now = new Date().toISOString()
    const ongoingFlags = Array.from(this.flags.values()).filter(f => f.ongoing)

    // Count ongoing flags
    const countOngoing = ongoingFlags.length

    // Weighted severity (sum of severities / max possible)
    const weightedSeverity = countOngoing > 0
      ? ongoingFlags.reduce((sum, f) => sum + f.severity, 0) / countOngoing
      : 0

    // Diversity index (how many distinct flag types)
    const distinctFlagTypes = new Set(ongoingFlags.map(f => f.flagType)).size
    const diversityIndex = countOngoing > 0 ? distinctFlagTypes / countOngoing : 0

    // Duration stress (how long flags have been firing)
    const durationStress = this.computeDurationStress(ongoingFlags, now)

    // Trend
    const trend = this.computeTrend()

    // Aggregate severity
    const aggregateSeverity = this.computeAggregateSeverity(
      weightedSeverity,
      diversityIndex,
      durationStress,
      trend,
    )

    // Recommended action
    const recommendedAction = this.determineAction(aggregateSeverity)

    const snapshot: WelfareStressSnapshot = {
      timestamp: now,
      individualFlags: ongoingFlags,
      countOngoing,
      weightedSeverity,
      diversityIndex,
      durationStress,
      trend,
      trendWindowMinutes: this.config.trendWindowMinutes,
      aggregateSeverity,
      recommendedAction,
    }

    // Update history
    this.history.push({ timestamp: now, aggregateSeverity })
    this.pruneHistory()

    return snapshot
  }

  /**
   * Get the most recent snapshot.
   */
  getStatus(): WelfareStressSnapshot {
    return this.getSnapshot()
  }

  /**
   * Trigger actions based on current stress level.
   * Returns the triggered action (if any).
   */
  triggerActions(): RecommendedAction | null {
    const snapshot = this.getSnapshot()
    const action = snapshot.recommendedAction

    if (action === 'no_action') {
      return null
    }

    const callback = this.actionCallbacks.get(action)

    if (callback && this.config.autoTriggerActions) {
      this.logger.info('[WelfareAggregator] Triggering action', { action, severity: snapshot.aggregateSeverity })
      callback()
    }

    return action
  }

  /**
   * Update configuration.
   */
  updateConfig(updates: Partial<WelfareAggregatorConfig>): void {
    this.config = { ...this.config, ...updates }
    this.logger.info('[WelfareAggregator] Config updated', { config: this.config })
  }

  /**
   * Get current configuration.
   */
  getConfig(): WelfareAggregatorConfig {
    return { ...this.config }
  }

  /**
   * Clear all flags and history.
   */
  reset(): void {
    this.flags.clear()
    this.history = []
    this.logger.info('[WelfareAggregator] Reset')
  }

  /**
   * Compute duration stress factor.
   */
  private computeDurationStress(flags: WelfareFlag[], now: string): number {
    if (flags.length === 0) {
      return 0
    }

    const nowMs = new Date(now).getTime()
    const maxDurationHours = 24 // Duration stress maxes out after 24 hours

    const avgDurationMs = flags.reduce((sum, f) => {
      const started = new Date(f.startedAt).getTime()
      return sum + (nowMs - started)
    }, 0) / flags.length

    const durationHours = avgDurationMs / (1000 * 60 * 60)

    return Math.min(durationHours / maxDurationHours, 1)
  }

  /**
   * Compute trend from history.
   */
  private computeTrend(): StressTrend {
    const windowMs = this.config.trendWindowMinutes * 60 * 1000
    const nowMs = Date.now()
    const windowStart = nowMs - windowMs

    const windowHistory = this.history.filter(h => new Date(h.timestamp).getTime() >= windowStart)

    if (windowHistory.length < 2) {
      return 'stable'
    }

    // Compute simple linear regression slope
    const n = windowHistory.length
    const sumX = windowHistory.reduce((sum, h, i) => sum + i, 0)
    const sumY = windowHistory.reduce((sum, h) => sum + h.aggregateSeverity, 0)
    const sumXY = windowHistory.reduce((sum, h, i) => sum + (i * h.aggregateSeverity), 0)
    const sumXX = windowHistory.reduce((sum, _, i) => sum + (i * i), 0)

    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX)

    if (slope > this.config.trendRisingThreshold) {
      return 'rising'
    } else if (slope < this.config.trendFallingThreshold) {
      return 'falling'
    } else {
      return 'stable'
    }
  }

  /**
   * Compute aggregate severity from components.
   *
   * Simplified to weightedSeverity only. The previously-configured diversity,
   * duration, and trend bonuses created knob inflation without empirical
   * calibration — and `registerFlag` deduplicates by `source:flagType`, which
   * made `diversityIndex` always degenerate to 1 in practice. The fields
   * remain in the snapshot for human inspection but no longer modulate the
   * action threshold.
   */
  private computeAggregateSeverity(
    weightedSeverity: number,
    _diversityIndex: number,
    _durationStress: number,
    _trend: StressTrend,
  ): number {
    return Math.min(Math.max(weightedSeverity, 0), 1)
  }

  /**
   * Determine recommended action from aggregate severity.
   */
  private determineAction(aggregateSeverity: number): RecommendedAction {
    const { actionThresholds } = this.config

    if (aggregateSeverity >= actionThresholds.sessionPause) {
      return 'session_pause'
    } else if (aggregateSeverity >= actionThresholds.tier4Review) {
      return 'tier_4_review'
    } else if (aggregateSeverity >= actionThresholds.pauseSelfCuring) {
      return 'pause_self_curing'
    } else if (aggregateSeverity >= actionThresholds.surfaceToOperator) {
      return 'surface_to_operator'
    } else {
      return 'no_action'
    }
  }

  /**
   * Prune history to keep only relevant window.
   */
  private pruneHistory(): void {
    const maxHistory = 100
    const windowMs = (this.config.trendWindowMinutes * 2) * 60 * 1000
    const nowMs = Date.now()
    const windowStart = nowMs - windowMs

    this.history = this.history.filter(h => new Date(h.timestamp).getTime() >= windowStart)

    // Also limit by count
    if (this.history.length > maxHistory) {
      this.history = this.history.slice(-maxHistory)
    }
  }
}


/**
 * Factory function to create a WelfareAggregator with standard config.
 */
export function createWelfareAggregator(
  logger: ILogger,
  config?: Partial<WelfareAggregatorConfig>,
): WelfareAggregator {
  return new WelfareAggregator(logger, config)
}
