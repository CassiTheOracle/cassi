/**
 * Saturation Detector (N5) — Detects sustained sameness without growth.
 *
 * When Aurora's cognitive state has been roughly the same posture for many turns
 * without novel insight, fresh activation, or affect change, N5 surfaces a signal.
 * The detector is informational only (N5.W1) — no auto-corrective actions.
 *
 * Five signals feed a composite saturation score:
 *   1. Affect stability — narrow valence/arousal band
 *   2. Composition stasis — same active compositions across turns
 *   3. Activation repetition — same claustrum nodes activating
 *   4. Insight drought — no novel Reverie insights
 *   5. Metric flatness — reasoning coherence/integration/novelty flatlined
 *
 * See: docs/design/aurora-saturation-detector.md
 */

import type { ILogger } from '@cassicore/foundation'
import type { ReverieInsight, ReasoningRecord } from './types.js'



export interface SaturationSignals {
  affectStability: number
  compositionStasis: number
  activationRepetition: number
  insightDrought: number
  metricFlatness: number
}

export type SaturationClassification = 'flowing' | 'productive_focus' | 'saturated' | 'unclear'

export interface SaturationScore {
  computedAt: string
  windowSize: number
  turnCount: number
  signals: SaturationSignals
  composite: number
  classification: SaturationClassification
}

export interface SaturationConfig {
  enabled: boolean
  /** Turn windows to evaluate. Default: [20, 100] */
  windows: number[]
  /** Weights for each signal axis (must sum to ~1). */
  weights: SaturationSignals
  /** Composite thresholds for classification. */
  thresholds: { flowing: number; productiveFocus: number; saturated: number }
  /** Affect: std-dev below this counts as stable. Default: 0.05 */
  affectStabilityStdThreshold: number
  /** Composition: fewer than this many activation events = stasis. Default: 2 */
  compositionEventFloor: number
  /** Activation: Jaccard above this = repetition. Default: 0.7 */
  activationRepetitionThreshold: number
  /** Insight: fewer than this many novel insights = drought. Default: 1 */
  insightNoveltyFloor: number
  /** Metric: variance below this = flatline. Default: 0.01 */
  metricVarianceFloor: number
  /** Cooldown turns before re-surfacing same pattern. Default: 50 */
  resurfaceCooldownTurns: number
  /** Per-session silence flag. Re-enables on new session. */
  silenced: boolean
}

export const DEFAULT_SATURATION_CONFIG: SaturationConfig = {
  enabled: true,
  windows: [20, 100],
  weights: {
    affectStability: 0.2,
    compositionStasis: 0.2,
    activationRepetition: 0.2,
    insightDrought: 0.2,
    metricFlatness: 0.2,
  },
  thresholds: { flowing: 0.3, productiveFocus: 0.5, saturated: 0.7 },
  affectStabilityStdThreshold: 0.05,
  compositionEventFloor: 2,
  activationRepetitionThreshold: 0.7,
  insightNoveltyFloor: 1,
  metricVarianceFloor: 0.01,
  resurfaceCooldownTurns: 50,
  silenced: false,
}



export interface TurnSample {
  turn: number
  affect: { valence: number; arousal: number } | null
  activeCompositions: string[]
  activatedNodes: string[]
  insights: ReverieInsight[]
  reasoningMetrics: { coherence: number; integration: number; novelty: number } | null
}



export class SaturationDetector {
  private config: SaturationConfig
  private logger: ILogger
  private samples: TurnSample[] = []
  private lastSurfacedTurn: number = -Infinity
  private lastSurfaceWindow: number = 0

  constructor(config: Partial<SaturationConfig>, logger: ILogger) {
    this.config = { ...DEFAULT_SATURATION_CONFIG, ...config }
    this.logger = logger
  }

  /**
   * Record a turn sample for saturation analysis.
   */
  recordSample(sample: TurnSample): void {
    if (!this.config.enabled) return
    this.samples.push(sample)
  }

  /**
   * Compute saturation scores across all configured windows.
   */
  computeScores(): SaturationScore[] {
    if (!this.config.enabled) return []

    const results: SaturationScore[] = []
    const now = new Date().toISOString()

    for (const windowSize of this.config.windows) {
      const windowSamples = this.samples.slice(-windowSize)
      if (windowSamples.length < 3) continue

      const signals = this.computeSignals(windowSamples)
      const composite = this.weightedComposite(signals)
      const classification = this.classify(composite, signals)

      results.push({
        computedAt: now,
        windowSize,
        turnCount: windowSamples.length,
        signals,
        composite,
        classification,
      })
    }

    return results
  }

  /**
   * Should this saturation result be surfaced? Implements N5.W4 (nag guard)
   * and N5.W5 (per-session silence).
   */
  shouldSurface(score: SaturationScore): boolean {
    if (!this.config.enabled || this.config.silenced) return false
    if (score.classification !== 'saturated') return false

    const lastSample = this.samples[this.samples.length - 1]
    if (!lastSample) return false

    const turnsSinceLastSurface = lastSample.turn - this.lastSurfacedTurn
    const windowChanged = score.windowSize !== this.lastSurfaceWindow

    return turnsSinceLastSurface >= this.config.resurfaceCooldownTurns || windowChanged
  }

  /**
   * Mark a score as surfaced. Updates nag guard state.
   */
  markSurfaced(score: SaturationScore): void {
    const lastSample = this.samples[this.samples.length - 1]
    if (lastSample) {
      this.lastSurfacedTurn = lastSample.turn
      this.lastSurfaceWindow = score.windowSize
    }
  }

  /**
   * Render a human-readable saturation note. Implements humble phrasing (N5.W2).
   */
  renderNote(score: SaturationScore): string {
    const parts: string[] = []

    const topSignals = Object.entries(score.signals)
      .filter(([, v]) => v >= 0.5)
      .sort(([, a], [, b]) => b - a)

    if (topSignals.length === 0) return ''

    const signalNames: Record<string, string> = {
      affectStability: 'stable affect',
      compositionStasis: 'unchanged composition',
      activationRepetition: 'repeated activation patterns',
      insightDrought: 'no novel insights',
      metricFlatness: 'flatlined reasoning metrics',
    }

    parts.push(`The last ${score.turnCount} turns have shown ${topSignals.map(([k]) => signalNames[k] ?? k).join(', ')}.`)
    parts.push('This may be productive flow on a focused task — or it may be saturation. Review?')

    return `[Aurora — Saturation note]\n${parts.join(' ')}`
  }

  /**
   * Silence N5 for the current session (N5.W5).
   */
  silence(): void { this.config.silenced = true }

  /**
   * Un-silence N5 (re-enables surfacing).
   */
  unsilence(): void { this.config.silenced = false }

  getConfig(): SaturationConfig { return { ...this.config } }

  updateConfig(patch: Partial<SaturationConfig>): void {
    this.config = { ...this.config, ...patch }
  }

  reset(): void {
    this.samples = []
    this.lastSurfacedTurn = -Infinity
    this.lastSurfaceWindow = 0
  }


  private computeSignals(samples: TurnSample[]): SaturationSignals {
    return {
      affectStability: this.computeAffectStability(samples),
      compositionStasis: this.computeCompositionStasis(samples),
      activationRepetition: this.computeActivationRepetition(samples),
      insightDrought: this.computeInsightDrought(samples),
      metricFlatness: this.computeMetricFlatness(samples),
    }
  }

  private computeAffectStability(samples: TurnSample[]): number {
    const affects = samples
      .map(s => s.affect)
      .filter((a): a is NonNullable<typeof a> => a !== null)

    if (affects.length < 3) return 0

    const valences = affects.map(a => a.valence)
    const arousals = affects.map(a => a.arousal)
    const valenceStd = standardDeviation(valences)
    const arousalStd = standardDeviation(arousals)
    const avgStd = (valenceStd + arousalStd) / 2

    // Map: low std-dev → high stability score
    if (avgStd < this.config.affectStabilityStdThreshold) {
      return 1 - (avgStd / this.config.affectStabilityStdThreshold)
    }
    return 0
  }

  private computeCompositionStasis(samples: TurnSample[]): number {
    const eventCount = samples.reduce((count, sample, i) => {
      if (i === 0) return count
      const prev = new Set(samples[i - 1].activeCompositions)
      const curr = new Set(sample.activeCompositions)
      // Count compositions that changed (added or removed)
      const added = [...curr].filter(c => !prev.has(c)).length
      const removed = [...prev].filter(c => !curr.has(c)).length
      return count + added + removed
    }, 0)

    if (eventCount < this.config.compositionEventFloor) {
      return 1 - (eventCount / this.config.compositionEventFloor)
    }
    return 0
  }

  private computeActivationRepetition(samples: TurnSample[]): number {
    if (samples.length < 2) return 0

    // Average pairwise Jaccard of consecutive activation sets
    let totalJaccard = 0
    let pairs = 0

    for (let i = 1; i < samples.length; i++) {
      const prev = new Set(samples[i - 1].activatedNodes)
      const curr = new Set(samples[i].activatedNodes)
      if (prev.size === 0 && curr.size === 0) continue

      const intersection = [...prev].filter(n => curr.has(n)).length
      const union = new Set([...prev, ...curr]).size
      if (union === 0) continue

      totalJaccard += intersection / union
      pairs++
    }

    if (pairs === 0) return 0
    const avgJaccard = totalJaccard / pairs

    // Map: high Jaccard → high repetition score
    if (avgJaccard >= this.config.activationRepetitionThreshold) {
      return avgJaccard
    }
    return 0
  }

  private computeInsightDrought(samples: TurnSample[]): number {
    const novelCount = samples.reduce((count, sample) => {
      return count + sample.insights.filter(i => i.kind === 'breakthrough' || (i.confidence ?? 0) > 0.7).length
    }, 0)

    if (novelCount < this.config.insightNoveltyFloor) {
      return 1 - (novelCount / this.config.insightNoveltyFloor)
    }
    return 0
  }

  private computeMetricFlatness(samples: TurnSample[]): number {
    const metrics = samples
      .map(s => s.reasoningMetrics)
      .filter((m): m is NonNullable<typeof m> => m !== null)

    if (metrics.length < 3) return 0

    const coherences = metrics.map(m => m.coherence)
    const integrations = metrics.map(m => m.integration)
    const novelties = metrics.map(m => m.novelty)

    const coherenceVar = variance(coherences)
    const integrationVar = variance(integrations)
    const noveltyVar = variance(novelties)

    const avgVar = (coherenceVar + integrationVar + noveltyVar) / 3

    if (avgVar < this.config.metricVarianceFloor) {
      return 1 - (avgVar / this.config.metricVarianceFloor)
    }
    return 0
  }

  private weightedComposite(signals: SaturationSignals): number {
    const w = this.config.weights
    return (
      w.affectStability * signals.affectStability +
      w.compositionStasis * signals.compositionStasis +
      w.activationRepetition * signals.activationRepetition +
      w.insightDrought * signals.insightDrought +
      w.metricFlatness * signals.metricFlatness
    )
  }

  private classify(composite: number, signals: SaturationSignals): SaturationClassification {
    const t = this.config.thresholds
    if (composite < t.flowing) return 'flowing'
    if (composite < t.productiveFocus) {
      // Medium composite: check for growth markers (some novelty or affect movement)
      const hasGrowth = signals.insightDrought < 0.5 || signals.affectStability < 0.5
      return hasGrowth ? 'productive_focus' : 'unclear'
    }
    if (composite >= t.saturated) return 'saturated'
    // Between productiveFocus and saturated
    return 'unclear'
  }
}



function standardDeviation(values: number[]): number {
  if (values.length < 2) return 0
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  const sqDiffs = values.map(v => (v - mean) ** 2)
  return Math.sqrt(sqDiffs.reduce((a, b) => a + b, 0) / values.length)
}

function variance(values: number[]): number {
  if (values.length < 2) return 0
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  return values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / values.length
}
