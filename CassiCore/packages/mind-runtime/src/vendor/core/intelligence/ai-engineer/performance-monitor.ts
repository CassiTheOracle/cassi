/**
 * AI Engineer — Performance Monitor
 *
 * Captures health signals from the EventBus for every intelligence module
 * that has at least one UpgradeTarget.  Provides:
 *   - Per-module rolling metric buffers (last 200 values per metric)
 *   - Composite health scores (0 = worst, 1 = best)
 *   - Trend classification (improving / stable / degrading / unknown)
 *   - Baseline and trial window snapshots for A/B comparison
 */

import type { HealthSignal, ModuleHealth } from './upgrade-types.js'


/** Maximum data points kept per metric per module. */
const MAX_SIGNAL_BUFFER = 200

/** Minimum signals required before computing a health score. */
const MIN_SIGNALS_FOR_SCORE = 5

/**
 * Module IDs that the Performance Monitor tracks.
 * Any module that has at least one catalog entry appears here.
 */
const TRACKED_MODULES = ['thinker', 'dialectic', 'subconscious', 'rule-enforcer'] as const


interface SignalBuffer {
  signals: HealthSignal[]
  lastSignalAt: number
}


export class PerformanceMonitor {
  /** module id → metric name → rolling buffer */
  private readonly buffers = new Map<string, Map<string, SignalBuffer>>()

  /** metadata: how many upgrade attempts each module has seen */
  private readonly upgradeCounts = new Map<string, number>()
  private readonly lastUpgradeAttemptAt = new Map<string, number>()

  constructor() {
    for (const m of TRACKED_MODULES) {
      this.buffers.set(m, new Map())
      this.upgradeCounts.set(m, 0)
    }
  }


  /**
   * Record a health signal for a module/metric.
   * Called by the AIEngineer EventBus listeners on relevant events.
   */
  record(moduleId: string, metricName: string, value: number, eventSource: string): void {
    if (!this.buffers.has(moduleId)) {
      this.buffers.set(moduleId, new Map())
    }
    const moduleBuffers = this.buffers.get(moduleId)!

    if (!moduleBuffers.has(metricName)) {
      moduleBuffers.set(metricName, { signals: [], lastSignalAt: 0 })
    }
    const buf = moduleBuffers.get(metricName)!
    const now = Date.now()

    const signal: HealthSignal = {
      metricName,
      value,
      timestamp: now,
      moduleId,
      eventSource,
    }

    buf.signals.push(signal)
    if (buf.signals.length > MAX_SIGNAL_BUFFER) {
      buf.signals.shift()
    }
    buf.lastSignalAt = now
  }

  /** Notify the monitor that an upgrade attempt was made for a module. */
  recordUpgradeAttempt(moduleId: string): void {
    this.upgradeCounts.set(moduleId, (this.upgradeCounts.get(moduleId) ?? 0) + 1)
    this.lastUpgradeAttemptAt.set(moduleId, Date.now())
  }


  /**
   * Compute average metric values over the last `windowSize` signals.
   * Returns a Record mapping metric name → average value.
   * Metrics with no data are omitted.
   */
  snapshot(moduleId: string, windowSize: number = 30): Record<string, number> {
    const moduleBuffers = this.buffers.get(moduleId)
    if (!moduleBuffers) return {}

    const result: Record<string, number> = {}
    for (const [metricName, buf] of moduleBuffers) {
      const recent = buf.signals.slice(-windowSize)
      if (recent.length === 0) continue
      const avg = recent.reduce((s, sig) => s + sig.value, 0) / recent.length
      result[metricName] = avg
    }
    return result
  }

  /**
   * Compute average metric values for a set of specific metric names.
   * Used to capture the baseline snapshot just before a trial starts.
   */
  snapshotMetrics(
    moduleId: string,
    metricNames: string[],
    windowSize: number = 30,
  ): Record<string, number> {
    const full = this.snapshot(moduleId, windowSize)
    const result: Record<string, number> = {}
    for (const name of metricNames) {
      if (Object.prototype.hasOwnProperty.call(full, name)) {
        result[name] = full[name]!
      }
    }
    return result
  }


  /**
   * Compute a composite health score (0–1) for a module.
   *
   * Scoring is based on the last MAX_WINDOW signals per metric.
   * Each metric is normalised to [0, 1] based on its known range,
   * then averaged.  Modules with too few signals receive score = 0.5.
   */
  healthScore(moduleId: string): number {
    const moduleBuffers = this.buffers.get(moduleId)
    if (!moduleBuffers || moduleBuffers.size === 0) return 0.5

    const scores: number[] = []

    for (const [metricName, buf] of moduleBuffers) {
      if (buf.signals.length < MIN_SIGNALS_FOR_SCORE) continue
      const recent = buf.signals.slice(-50)
      const avg = recent.reduce((s, sig) => s + sig.value, 0) / recent.length

      // Normalise each known metric into [0, 1] where 1 = best.
      const score = normaliseMetric(metricName, avg)
      scores.push(score)
    }

    if (scores.length === 0) return 0.5
    return scores.reduce((a, b) => a + b, 0) / scores.length
  }

  /**
   * Classify the trend of a module's health over the last two windows.
   * Compares older half vs newer half of the signal buffer.
   */
  trend(moduleId: string): ModuleHealth['trend'] {
    const moduleBuffers = this.buffers.get(moduleId)
    if (!moduleBuffers || moduleBuffers.size === 0) return 'unknown'

    const allSignals: HealthSignal[] = []
    for (const buf of moduleBuffers.values()) {
      allSignals.push(...buf.signals)
    }
    allSignals.sort((a, b) => a.timestamp - b.timestamp)

    if (allSignals.length < MIN_SIGNALS_FOR_SCORE * 2) return 'unknown'

    const half = Math.floor(allSignals.length / 2)
    const older = allSignals.slice(0, half)
    const newer = allSignals.slice(half)

    const olderAvg = older.reduce((s, sig) => s + normaliseMetric(sig.metricName, sig.value), 0) / older.length
    const newerAvg = newer.reduce((s, sig) => s + normaliseMetric(sig.metricName, sig.value), 0) / newer.length

    const delta = newerAvg - olderAvg
    if (delta > 0.05) return 'improving'
    if (delta < -0.05) return 'degrading'
    return 'stable'
  }

  /** Return a full ModuleHealth summary for a module. */
  moduleHealth(moduleId: string): ModuleHealth {
    const moduleBuffers = this.buffers.get(moduleId)

    let signalCount = 0
    let lastSignalAt: number | undefined
    if (moduleBuffers) {
      for (const buf of moduleBuffers.values()) {
        signalCount += buf.signals.length
        if (!lastSignalAt || buf.lastSignalAt > lastSignalAt) {
          lastSignalAt = buf.lastSignalAt
        }
      }
    }

    return {
      moduleId,
      healthScore: this.healthScore(moduleId),
      trend: this.trend(moduleId),
      signalCount,
      lastSignalAt,
      lastUpgradeAttemptAt: this.lastUpgradeAttemptAt.get(moduleId),
      upgradeCount: this.upgradeCounts.get(moduleId) ?? 0,
    }
  }

  /** Return health summaries for all tracked modules. */
  allHealth(): ModuleHealth[] {
    return Array.from(this.buffers.keys()).map(mid => this.moduleHealth(mid))
  }

  /**
   * Find the module that most needs an upgrade attempt — the one with the
   * lowest health score that isn't excluded by the caller (e.g. on cooldown).
   */
  weakestModule(excludeModules: string[] = []): string | null {
    let worst: string | null = null
    let worstScore = Infinity

    for (const moduleId of this.buffers.keys()) {
      if (excludeModules.includes(moduleId)) continue
      const score = this.healthScore(moduleId)
      if (score < worstScore) {
        worstScore = score
        worst = moduleId
      }
    }

    return worst
  }
}


/**
 * Convert a raw metric value into a [0, 1] score where 1.0 = best possible.
 * Ranges are approximate; they will naturally compress as the system matures.
 * @dep callers: trend (core/intelligence/ai-engineer/performance-monitor.ts), healthScore (core/intelligence/ai-engineer/performance-monitor.ts)
 * @dep calls: clamp, linearMap
 * @dep module: Branching-conversation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
function normaliseMetric(name: string, value: number): number {
  switch (name) {
    // Thinker
    case 'thinker_helpfulness':
      // Fraction 0–1 where 1 = always helpful. Direct mapping.
      return clamp(value, 0, 1)

    case 'thinker_insight_rate':
      // Insights per turn. Optimal ~0.3–0.7. Too low = useless; too high = noise.
      // Map 0.3–0.7 → 0.7–1.0, outside that range degrades gracefully.
      if (value <= 0) return 0.1
      if (value >= 1) return 0.3 // too many insights is noise
      if (value >= 0.3 && value <= 0.7) return linearMap(value, 0.3, 0.7, 0.7, 1.0)
      if (value < 0.3) return linearMap(value, 0, 0.3, 0.1, 0.7)
      return linearMap(value, 0.7, 1.0, 1.0, 0.3) // above 0.7, too noisy

    // Dialectic
    case 'dialectic_signal_confidence':
      // Average confidence 0–1. Higher is better. Map directly.
      return clamp(value, 0, 1)

    case 'dialectic_signal_rate':
      // Signals per turn. Optimal ~0.4–0.8.
      if (value <= 0) return 0.1
      if (value >= 0.4 && value <= 0.8) return 1.0
      if (value < 0.4) return linearMap(value, 0, 0.4, 0.2, 1.0)
      return linearMap(value, 0.8, 2.0, 1.0, 0.3)

    case 'dialectic_convergence_rate':
      // Fraction of dialectic cycles that produce a convergent signal 0–1.
      return clamp(value, 0, 1)

    // Subconscious
    case 'subconscious_observation_rate':
      // Observations per turn. Optimal ~0.2–0.5.
      if (value <= 0) return 0.1
      if (value >= 0.2 && value <= 0.5) return 1.0
      if (value < 0.2) return linearMap(value, 0, 0.2, 0.2, 1.0)
      return linearMap(value, 0.5, 2.0, 1.0, 0.3)

    case 'subconscious_anomaly_rate':
      // Anomalies detected per observation. Optimal ~0.1–0.3 (detects real ones).
      if (value <= 0) return 0.5 // no anomalies is neutral, not bad
      if (value >= 0.1 && value <= 0.3) return 1.0
      if (value < 0.1) return linearMap(value, 0, 0.1, 0.5, 1.0)
      return linearMap(value, 0.3, 1.0, 1.0, 0.3) // too many anomalies = noise

    default:
      // Unknown metric: treat as-is (assume 0–1 range)
      return clamp(value, 0, 1)
  }
}

/**
 * @dep callers: linearMap (core/intelligence/ai-engineer/performance-monitor.ts), normaliseMetric (core/intelligence/ai-engineer/performance-monitor.ts)
 * @dep module: Branching-conversation
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

function linearMap(v: number, inLo: number, inHi: number, outLo: number, outHi: number): number {
  if (inHi === inLo) return outLo
  const t = (v - inLo) / (inHi - inLo)
  return clamp(outLo + t * (outHi - outLo), Math.min(outLo, outHi), Math.max(outLo, outHi))
}
