/**
 * VENDORED — faithful type surface of `core/intelligence/memory-bridge/resonant-affect.ts`.
 * Consumed by @cassicore/aurora (index.ts, types.ts) as `ResonantAffectSignal` (type-only).
 *
 * `Affect`/`AffectLabel` are re-exported from `@cassicore/mnemic-field` (published
 * P4 package), mirroring the D: source. Re-point to `@cassicore/*-memory-bridge`
 * when that package lands (P5 repoint log).
 */
import type { Affect, AffectLabel } from '@cassicore/mnemic-field'

export type { Affect, AffectLabel }

/** Raw measurements from comparing model and memory activations. */
export interface ResonanceMeasurements {
  /** Portal resonance: average correlation across activated portal pairs. Range 0..1. */
  portalResonance: number
  /** Memory magnitude: how strongly the memory delta perturbs the residual. Range 0+. */
  memoryMagnitude: number
  /** Prediction agreement: cosine similarity between baseline and augmented predictions. */
  predictionAgreement: number | null
  /** Confidence shift: change in top prediction probability. */
  confidenceShift: number | null
  /** Prediction changed: did the top predicted token change? */
  topPredictionChanged: boolean | null
  /** Boundary correlation: cosine similarity between boundary residual and projected memory embedding. */
  boundaryCorrelation: number | null
  /** Contributing engram count: how many memories crossed the spark threshold. */
  contributingCount: number
  /** Activated portal count: how many portal pairs fired. */
  activatedPortals: number
}

/** A resonant affect signal — valence/arousal with dominance and label. */
export interface ResonantAffectSignal {
  affect: Affect
  dominance: number
  label: AffectLabel
  mode: 'full' | 'proxy' | 'boundary'
  measurements: ResonanceMeasurements
  computedAt: number
}
