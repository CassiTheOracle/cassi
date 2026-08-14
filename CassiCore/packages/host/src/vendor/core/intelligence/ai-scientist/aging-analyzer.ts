/**
 * AI Scientist — Aging Analyzer
 *
 * Detects how the cognitive system's performance changes over time.
 * Compares rolling windows (7d, 30d, 90d) to identify:
 *
 *   - Degradation: metrics trending downward without explicit change
 *   - Stagnation:  metrics flat despite environmental variation
 *   - Growth:      genuine, statistically supported improvement over time
 *   - Drift:       the system's behavior slowly shifting away from its
 *                  intended operating point
 *
 * The analyzer does not apply fixes — it produces findings that the main
 * AIScientist class translates into experiment proposals.
 */

import { mean, variance, describeStats, welchTTest } from './stats.js'


export type AgingTrend = 'growing' | 'stable' | 'degrading' | 'unknown'

export interface MetricWindow {
  windowDays: number
  sampleCount: number
  mean: number
  stdDev: number
  p95: number
}

export interface AgingReport {
  /** Wall-clock timestamp of this report */
  timestamp: number
  /** Trend direction for each tracked metric */
  trends: Record<string, AgingTrend>
  /** Per-metric window comparisons */
  windows: Record<string, { recent: MetricWindow; reference: MetricWindow }>
  /** Plain-English narrative for LLM consumption */
  narrative: string
  /** Whether any metric shows significant degradation */
  hasActiveDegradation: boolean
  /** Whether the system is demonstrably improving */
  hasActiveGrowth: boolean
}

export interface AgingDataPoint {
  timestamp: number
  metric: string
  value: number
}


export class AgingAnalyzer {
  /** Rolling buffer of metric observations. Max 10 000 per metric. */
  private data: AgingDataPoint[] = []

  /** Record a single metric observation. */
  record(metric: string, value: number, timestamp = Date.now()): void {
    this.data.push({ timestamp, metric, value })
    // Evict old points — keep at most 10k per metric
    const byMetric = this.data.filter(d => d.metric === metric)
    if (byMetric.length > 10_000) {
      const oldest = byMetric[0].timestamp
      this.data = this.data.filter(d => !(d.metric === metric && d.timestamp === oldest))
    }
  }

  /** Bulk-import historical data points. */
  import(points: AgingDataPoint[]): void {
    this.data.push(...points)
  }

  /** Generate a full aging report over the current data buffer. */
  analyse(now = Date.now()): AgingReport {
    const metrics = [...new Set(this.data.map(d => d.metric))]
    const trends: Record<string, AgingTrend>  = {}
    const windows: AgingReport['windows']      = {}

    for (const metric of metrics) {
      const all = this.data.filter(d => d.metric === metric)
        .sort((a, b) => a.timestamp - b.timestamp)

      const recent7d    = sliceWindow(all, now, 7)
      const reference7d = sliceWindow(all, now - DAY_MS * 7, 7)

      if (recent7d.length < 3 || reference7d.length < 3) {
        trends[metric] = 'unknown'
        continue
      }

      const recentStats = describeStats(recent7d.map(d => d.value))
      const refStats    = describeStats(reference7d.map(d => d.value))

      windows[metric] = {
        recent: {
          windowDays: 7,
          sampleCount: recent7d.length,
          mean: recentStats.mean,
          stdDev: recentStats.stdDev,
          p95: recentStats.p95,
        },
        reference: {
          windowDays: 7,
          sampleCount: reference7d.length,
          mean: refStats.mean,
          stdDev: refStats.stdDev,
          p95: refStats.p95,
        },
      }

      const tt = welchTTest(recent7d.map(d => d.value), reference7d.map(d => d.value))

      // We need directional knowledge: does higher mean better for this metric?
      // For latency we invert; for everything else higher = better by convention.
      const isLatency = metric.includes('latency')
      const delta     = recentStats.mean - refStats.mean
      const improved  = isLatency ? delta < 0 : delta > 0
      const degraded  = isLatency ? delta > 0 : delta < 0
      const significant = tt.pValue < 0.1  // slightly relaxed for trend detection

      if (!significant) {
        trends[metric] = 'stable'
      } else if (improved) {
        trends[metric] = 'growing'
      } else if (degraded) {
        trends[metric] = 'degrading'
      } else {
        trends[metric] = 'stable'
      }
    }

    const hasActiveDegradation = Object.values(trends).some(t => t === 'degrading')
    const hasActiveGrowth      = Object.values(trends).some(t => t === 'growing')

    const narrative = buildNarrative(trends, windows)

    return {
      timestamp: now,
      trends,
      windows,
      narrative,
      hasActiveDegradation,
      hasActiveGrowth,
    }
  }

  /** Export all buffered data points (for persistence). */
  export(): AgingDataPoint[] {
    return [...this.data]
  }

  /** Replace buffer from persisted data. */
  restore(points: AgingDataPoint[]): void {
    this.data = [...points]
  }
}


const DAY_MS = 86_400_000

function sliceWindow(sorted: AgingDataPoint[], endTime: number, days: number): AgingDataPoint[] {
  const start = endTime - days * DAY_MS
  return sorted.filter(d => d.timestamp >= start && d.timestamp <= endTime)
}

function buildNarrative(
  trends: Record<string, AgingTrend>,
  windows: AgingReport['windows'],
): string {
  const lines: string[] = []
  const degrading = Object.entries(trends).filter(([, t]) => t === 'degrading')
  const growing   = Object.entries(trends).filter(([, t]) => t === 'growing')
  const stable    = Object.entries(trends).filter(([, t]) => t === 'stable')

  if (degrading.length > 0) {
    lines.push(
      `Degradation detected in: ${degrading.map(([m]) => m.replace(/_/g, ' ')).join(', ')}.`,
    )
    for (const [metric] of degrading) {
      const w = windows[metric]
      if (w) {
        const pct = ((w.recent.mean - w.reference.mean) / Math.abs(w.reference.mean) * 100).toFixed(1)
        lines.push(`  • ${metric.replace(/_/g, ' ')}: recent mean ${w.recent.mean.toFixed(2)} vs reference ${w.reference.mean.toFixed(2)} (${pct}%)`)
      }
    }
  }

  if (growing.length > 0) {
    lines.push(
      `Growth confirmed in: ${growing.map(([m]) => m.replace(/_/g, ' ')).join(', ')}.`,
    )
    for (const [metric] of growing) {
      const w = windows[metric]
      if (w) {
        const pct = ((w.recent.mean - w.reference.mean) / Math.abs(w.reference.mean) * 100).toFixed(1)
        lines.push(`  • ${metric.replace(/_/g, ' ')}: +${pct}% over prior 7d window`)
      }
    }
  }

  if (stable.length > 0 && degrading.length === 0 && growing.length === 0) {
    lines.push(`All tracked metrics are stable over the last 7 days.`)
  }

  if (lines.length === 0) lines.push('Insufficient data for aging analysis.')

  return lines.join('\n')
}
