/**
 * Resonant Affect — derives emotional affect from the resonance between
 * model knowledge (LARQL vindex) and personal memory (Mnemic Field).
 *
 * Instead of regex sentiment detection, this measures what actually happens
 * when memories meet model weights:
 *
 *   - Memories CONFIRM model knowledge  → positive valence (agreement)
 *   - Memories CONTRADICT model          → negative valence (conflict)
 *   - Memories SHIFT the prediction      → high arousal (surprise)
 *   - Memories have NO effect            → low arousal (irrelevance)
 *
 * Three operating modes:
 *   1. Full:  Compare walkInfer (baseline) vs injectWithForwardPass (augmented)
 *   2. Proxy: Use portal resonance + memory magnitude (no forward pass needed)
 *   3. Boundary: Use boundary residual correlation (mid-forward-pass, cheap)
 *
 * The affect signal feeds into the existing AffectRegister via absorbSignal(),
 * blending with the regex-based attune() signal rather than replacing it.
 */

import type { ILogger } from '@cassicore/foundation'
import type { Affect, AffectLabel } from '@cassicore/mnemic-field'
import type {
  MemoryKindlingResult,
  MemoryDelta,
  BoundaryResidual,
  FeatureEngramPortal,
} from './types.js'
import type { PortalBridge } from './portal-bridge.js'
import type { LuminalProjectionEngine } from './luminal-projection.js'

/**
 * Result of a resonant affect computation.
 * Carries both the core affect signal and the measurements that produced it.
 */
export interface ResonantAffectSignal {
  /** Core affect: valence (-1..1) and arousal (0..1). */
  affect: Affect

  /** Computed dominance: who's driving — model (0) or memory (1). */
  dominance: number

  /** Resolved label from the affect coordinates. */
  label: AffectLabel

  /** Which mode produced this signal. */
  mode: 'full' | 'proxy' | 'boundary'

  /** Measurements that produced this signal (for introspection). */
  measurements: ResonanceMeasurements

  /** Timestamp. */
  computedAt: number
}

/**
 * Raw measurements from comparing model and memory activations.
 * These are the "instruments" — the affect is the interpretation.
 */
export interface ResonanceMeasurements {
  /**
   * Portal resonance: average correlation across activated portal pairs.
   * High = model features and engrams agree. Low = they diverge.
   * Range: 0 to 1.
   */
  portalResonance: number

  /**
   * Memory magnitude: how strongly the memory delta perturbs the residual.
   * High = memories are loudly present. Low = memories are quiet.
   * Range: 0+.
   */
  memoryMagnitude: number

  /**
   * Prediction agreement: cosine similarity between baseline and augmented
   * prediction distributions. 1.0 = identical predictions, 0.0 = completely different.
   * Only available in 'full' mode.
   */
  predictionAgreement: number | null

  /**
   * Confidence shift: change in top prediction probability.
   * Positive = memory makes model more confident. Negative = less confident.
   * Only available in 'full' mode.
   */
  confidenceShift: number | null

  /**
   * Prediction changed: did the top predicted token change?
   * Only available in 'full' mode.
   */
  topPredictionChanged: boolean | null

  /**
   * Boundary correlation: cosine similarity between boundary residual
   * and projected memory embedding. Measures alignment at L22.
   * Available in 'boundary' and 'full' modes.
   */
  boundaryCorrelation: number | null

  /**
   * Contributing engram count: how many memories crossed the spark threshold.
   */
  contributingCount: number

  /**
   * Activated portal count: how many portal pairs fired.
   */
  activatedPortals: number
}

/**
 * Configuration for resonant affect computation.
 */
export interface ResonantAffectConfig {
  /**
   * Weight of portal resonance in valence computation.
   * Portal resonance directly measures agreement between model and memory.
   */
  portalResonanceWeight: number

  /**
   * Weight of prediction agreement in valence computation (full mode only).
   * Prediction agreement measures whether memory changed the actual output.
   */
  predictionAgreementWeight: number

  /**
   * Weight of confidence shift in valence computation (full mode only).
   */
  confidenceShiftWeight: number

  /**
   * Scale factor for memory magnitude → arousal mapping.
   * Larger = more sensitive to memory perturbation.
   */
  magnitudeArousalScale: number

  /**
   * Arousal contribution from prediction change (full mode only).
   * If the top prediction actually changed, add this much arousal.
   */
  predictionChangeArousalBoost: number

  /**
   * Minimum portal resonance to count as "agreement."
   * Below this, resonance is treated as neutral rather than positive.
   */
  resonanceFloor: number

  /**
   * Blend factor when combining resonant affect with text-based attune().
   * 0.0 = only attune(), 1.0 = only resonant.
   */
  resonantBlendFactor: number
}

export const RESONANT_AFFECT_DEFAULTS: ResonantAffectConfig = {
  portalResonanceWeight: 0.6,
  predictionAgreementWeight: 0.25,
  confidenceShiftWeight: 0.15,
  magnitudeArousalScale: 0.02,     // 50.0 magnitude → 1.0 arousal (matches maxContribution)
  predictionChangeArousalBoost: 0.4,
  resonanceFloor: 0.3,
  resonantBlendFactor: 0.5,
}

/**
 * Token prediction from LARQL inference.
 */
interface TokenPrediction {
  token: string
  prob: number
}

/**
 * ResonantAffectEngine — computes affect from the interaction
 * between model knowledge and personal memory.
 */
export class ResonantAffectEngine {
  private config: ResonantAffectConfig
  private logger: ILogger
  private history: ResonantAffectSignal[] = []

  constructor(
    private portalBridge: PortalBridge | null,
    private projectionEngine: LuminalProjectionEngine | null,
    logger: ILogger,
    config?: Partial<ResonantAffectConfig>,
  ) {
    this.logger = logger.child ? logger.child('resonant-affect') : logger
    this.config = { ...RESONANT_AFFECT_DEFAULTS, ...config }
  }

  /**
   * Full mode: compare baseline predictions (walk, no memory) against
   * augmented predictions (forward pass with memory injection).
   *
   * This is the gold standard — it measures what memory actually DID
   * to the model's output. Expensive (requires two inference passes).
   */
  computeFromPredictionDelta(
    baselinePredictions: TokenPrediction[],
    augmentedPredictions: TokenPrediction[],
    memoryResult: MemoryKindlingResult,
    boundary?: BoundaryResidual,
  ): ResonantAffectSignal {
    const measurements = this.measure(memoryResult, boundary)

    // Prediction agreement: cosine similarity of probability distributions
    measurements.predictionAgreement = this.predictionCosineSim(
      baselinePredictions,
      augmentedPredictions,
    )

    // Confidence shift: did memory make the model more or less sure?
    const baselineTop = baselinePredictions[0]?.prob ?? 0
    const augmentedTop = augmentedPredictions[0]?.prob ?? 0
    measurements.confidenceShift = augmentedTop - baselineTop

    // Did the actual prediction change?
    measurements.topPredictionChanged =
      (baselinePredictions[0]?.token ?? '') !== (augmentedPredictions[0]?.token ?? '')

    // Compute affect from measurements
    const affect = this.measurementsToAffect(measurements, 'full')

    const signal: ResonantAffectSignal = {
      affect,
      dominance: this.computeDominance(measurements),
      label: this.resolveLabel(affect),
      mode: 'full',
      measurements,
      computedAt: Date.now(),
    }

    this.recordSignal(signal)
    return signal
  }

  /**
   * Proxy mode: derive affect from portal resonance and memory magnitude alone.
   * No forward pass needed — uses only data available after kindling.
   *
   * Less precise than full mode, but essentially free.
   */
  computeFromKindling(
    memoryResult: MemoryKindlingResult,
  ): ResonantAffectSignal {
    const measurements = this.measure(memoryResult, memoryResult.boundary)
    const affect = this.measurementsToAffect(measurements, 'proxy')

    const signal: ResonantAffectSignal = {
      affect,
      dominance: this.computeDominance(measurements),
      label: this.resolveLabel(affect),
      mode: 'proxy',
      measurements,
      computedAt: Date.now(),
    }

    this.recordSignal(signal)
    return signal
  }

  /**
   * Boundary mode: use boundary residual correlation (available mid-forward-pass).
   * Cheaper than full mode, richer than proxy.
   */
  computeFromBoundary(
    memoryResult: MemoryKindlingResult,
    boundary: BoundaryResidual,
  ): ResonantAffectSignal {
    const measurements = this.measure(memoryResult, boundary)

    // Boundary correlation: how aligned is memory with model state at L22
    if (this.projectionEngine) {
      measurements.boundaryCorrelation =
        this.projectionEngine.computeMemoryBoundaryCorrelation(
          boundary,
          memoryResult.luminalSet,
        )
    }

    const affect = this.measurementsToAffect(measurements, 'boundary')

    const signal: ResonantAffectSignal = {
      affect,
      dominance: this.computeDominance(measurements),
      label: this.resolveLabel(affect),
      mode: 'boundary',
      measurements,
      computedAt: Date.now(),
    }

    this.recordSignal(signal)
    return signal
  }

  /**
   * Core measurement: gather portal resonance and memory magnitude
   * from a kindling result. Available in all modes.
   */
  private measure(
    memoryResult: MemoryKindlingResult,
    boundary?: BoundaryResidual,
  ): ResonanceMeasurements {
    // Portal resonance: average strength of activated portal pairs
    let portalResonance = 0
    let activatedPortals = 0
    if (this.portalBridge) {
      const portalStats = this.portalBridge.getStats()
      portalResonance = portalStats.avgStrength
      activatedPortals = portalStats.totalPortals
    }

    // Memory magnitude: max delta magnitude across injection layers
    let memoryMagnitude = 0
    for (const delta of memoryResult.deltas.values()) {
      if (delta.magnitude > memoryMagnitude) {
        memoryMagnitude = delta.magnitude
      }
    }

    // Boundary correlation
    let boundaryCorrelation: number | null = null
    if (boundary && this.projectionEngine) {
      boundaryCorrelation =
        this.projectionEngine.computeMemoryBoundaryCorrelation(
          boundary,
          memoryResult.luminalSet,
        )
    }

    // Contributing count
    const contributingCount = memoryResult.luminalSet.engrams.length

    return {
      portalResonance,
      memoryMagnitude,
      predictionAgreement: null,     // only in full mode
      confidenceShift: null,         // only in full mode
      topPredictionChanged: null,    // only in full mode
      boundaryCorrelation,
      contributingCount,
      activatedPortals,
    }
  }

  /**
   * Convert raw measurements into an affect signal.
   *
   * The interpretation depends on the mode — full mode has richer signals.
   */
  private measurementsToAffect(
    m: ResonanceMeasurements,
    mode: 'full' | 'proxy' | 'boundary',
  ): Affect {
    let valence = 0
    let arousal = 0

    // === VALENCE: agreement vs disagreement between model and memory ===

    if (mode === 'full' && m.predictionAgreement !== null && m.confidenceShift !== null) {
      // Full mode: rich valence from actual prediction comparison
      //
      // predictionAgreement high + confidenceShift positive
      //   → model and memory agree, memory helps → strong positive
      //
      // predictionAgreement low + confidenceShift negative
      //   → model and memory conflict, memory confuses → strong negative
      //
      // predictionAgreement high + confidenceShift negative
      //   → same prediction but less sure → mild negative (undermining)
      //
      // predictionAgreement low + confidenceShift positive
      //   → different prediction but model is confident → arousing (novel path)

      const agreementValence = (m.predictionAgreement - 0.5) * 2  // map 0..1 to -1..1
      const confidenceValence = clamp(m.confidenceShift * 2, -1, 1)  // scale up

      valence = (
        this.config.predictionAgreementWeight * agreementValence +
        this.config.confidenceShiftWeight * confidenceValence +
        this.config.portalResonanceWeight * this.portalToValence(m.portalResonance)
      )
    } else if (mode === 'boundary' && m.boundaryCorrelation !== null) {
      // Boundary mode: valence from alignment of memory with model state at L22
      const correlationValence = (m.boundaryCorrelation - 0.5) * 2  // center at 0.5
      valence = (
        0.4 * correlationValence +
        0.6 * this.portalToValence(m.portalResonance)
      )
    } else {
      // Proxy mode: valence primarily from portal resonance
      valence = this.portalToValence(m.portalResonance)
    }

    // === AROUSAL: how much is happening? ===

    // Memory magnitude → arousal (louder memory = more activation)
    const magnitudeArousal = clamp(
      m.memoryMagnitude * this.config.magnitudeArousalScale,
      0,
      0.8,  // leave room for prediction-change boost
    )

    // Contributing count → arousal modifier (more memories = more active)
    const countModifier = Math.min(m.contributingCount / 20, 1.0) * 0.2

    arousal = magnitudeArousal + countModifier

    // Full mode bonus: prediction change is a big arousal event
    if (mode === 'full' && m.topPredictionChanged) {
      arousal += this.config.predictionChangeArousalBoost
    }

    // Boundary mode: high correlation variance from typical = arousing
    if (mode === 'boundary' && m.boundaryCorrelation !== null) {
      const deviation = Math.abs(m.boundaryCorrelation - 0.5) * 2
      arousal = Math.max(arousal, deviation * 0.6)
    }

    return {
      valence: clamp(valence, -1, 1),
      arousal: clamp(arousal, 0, 1),
    }
  }

  /**
   * Map portal resonance (0..1) to valence (-1..1).
   *
   * Above the resonance floor → positive valence (agreement).
   * Below the floor → slightly negative (divergence).
   * No portals → neutral.
   */
  private portalToValence(resonance: number): number {
    if (resonance <= 0) return 0  // no portals = no signal

    const floor = this.config.resonanceFloor
    if (resonance >= floor) {
      // Above floor: positive, scaled 0 to 1
      return (resonance - floor) / (1 - floor)
    }
    // Below floor: slightly negative
    return -(floor - resonance) / floor * 0.5
  }

  /**
   * Compute dominance: is the model or memory driving the output?
   *
   * 0 = model completely dominates (memories had no effect)
   * 0.5 = balanced
   * 1 = memory completely dominates (memories overrode the model)
   */
  private computeDominance(m: ResonanceMeasurements): number {
    if (m.predictionAgreement !== null && m.topPredictionChanged !== null) {
      // Full mode: if prediction changed, memory is dominant
      if (m.topPredictionChanged) {
        // Memory shifted the answer — high dominance
        return 0.5 + (1 - (m.predictionAgreement ?? 0.5)) * 0.5
      }
      // Prediction unchanged — model dominates
      return 0.5 - (m.predictionAgreement ?? 0.5) * 0.3
    }

    // Proxy/boundary mode: use magnitude relative to max contribution
    const magnitudeRatio = clamp(m.memoryMagnitude / 50, 0, 1)  // 50 = maxContribution default
    return magnitudeRatio * 0.5 + 0.25  // range 0.25 to 0.75
  }

  /**
   * Resolve affect coordinates to a label.
   * Uses the same labels as the existing system for compatibility.
   */
  private resolveLabel(affect: Affect): AffectLabel {
    const { valence: v, arousal: a } = affect

    if (Math.abs(v) < 0.15 && a < 0.3) return 'neutral'

    if (v > 0.3) {
      if (a > 0.5) return 'excited'
      if (a > 0.3) return 'engaged'
      if (v > 0.5) return 'delighted'
      return 'content'
    }

    if (v > 0) {
      if (a < 0.2) return 'calm'
      return 'warm'
    }

    if (v < -0.3) {
      if (a > 0.5) return 'alarmed'
      if (a > 0.3) return 'frustrated'
      return 'melancholy'
    }

    if (a > 0.4) return 'uneasy'
    if (a < 0.2) return 'fatigued'
    return 'neutral'
  }

  /**
   * Cosine similarity between two prediction distributions.
   * Predictions are sparse (top-K tokens), so we compute over the union.
   */
  private predictionCosineSim(
    a: TokenPrediction[],
    b: TokenPrediction[],
  ): number {
    if (a.length === 0 || b.length === 0) return 0

    // Build probability maps
    const mapA = new Map<string, number>()
    const mapB = new Map<string, number>()
    for (const p of a) mapA.set(p.token, p.prob)
    for (const p of b) mapB.set(p.token, p.prob)

    // Union of all tokens
    const allTokens = new Set([...mapA.keys(), ...mapB.keys()])

    // Cosine similarity over the union
    let dotProduct = 0
    let normA = 0
    let normB = 0

    for (const token of allTokens) {
      const va = mapA.get(token) ?? 0
      const vb = mapB.get(token) ?? 0
      dotProduct += va * vb
      normA += va * va
      normB += vb * vb
    }

    if (normA === 0 || normB === 0) return 0
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB))
  }

  /**
   * Record a signal for history tracking.
   * History enables trend detection (are we getting more/less resonant over time).
   */
  private recordSignal(signal: ResonantAffectSignal): void {
    this.history.push(signal)
    if (this.history.length > 100) {
      this.history.shift()
    }

    this.logger.debug('Resonant affect computed', {
      mode: signal.mode,
      valence: signal.affect.valence.toFixed(3),
      arousal: signal.affect.arousal.toFixed(3),
      label: signal.label,
      dominance: signal.dominance.toFixed(3),
      portalResonance: signal.measurements.portalResonance.toFixed(3),
      memoryMagnitude: signal.measurements.memoryMagnitude.toFixed(1),
      contributingCount: signal.measurements.contributingCount,
    })
  }

  /**
   * Get the trend: is resonance increasing or decreasing?
   * Positive = warming up (more agreement). Negative = cooling (more conflict).
   */
  getResonanceTrend(windowSize: number = 10): number {
    if (this.history.length < 2) return 0

    const recent = this.history.slice(-windowSize)
    if (recent.length < 2) return 0

    const firstHalf = recent.slice(0, Math.floor(recent.length / 2))
    const secondHalf = recent.slice(Math.floor(recent.length / 2))

    const avgFirst = firstHalf.reduce((s, h) => s + h.affect.valence, 0) / firstHalf.length
    const avgSecond = secondHalf.reduce((s, h) => s + h.affect.valence, 0) / secondHalf.length

    return avgSecond - avgFirst
  }

  /**
   * Get average arousal over recent history.
   * High sustained arousal = active, engaged session.
   * Low sustained arousal = routine, background work.
   */
  getAverageArousal(windowSize: number = 10): number {
    if (this.history.length === 0) return 0
    const recent = this.history.slice(-windowSize)
    return recent.reduce((s, h) => s + h.affect.arousal, 0) / recent.length
  }

  /**
   * Get recent signal history for introspection.
   */
  getHistory(limit: number = 20): ResonantAffectSignal[] {
    return this.history.slice(-limit)
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}
