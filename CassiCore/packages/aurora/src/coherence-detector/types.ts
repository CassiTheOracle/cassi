/**
 * N2 Posture Coherence Detector — type surface.
 *
 * The detector is a pure consumer of state; it reads active compositions,
 * pending meditation seeds, scheduled replays, and retrieval policies, and
 * surfaces incoherences as `CoherenceCheck` records.
 *
 * Categories without supporting subsystems (B2 retrieval, B3 replay scheduling
 * with affect tags, claustrum activation timelines) ship as defined types
 * with stub detectors that return [] until those inputs land. The architecture
 * is the same; the gap is just empty.
 *
 * See: docs/design/aurora-posture-coherence-detector.md §3
 */

export type CoherenceCategory =
  | 'composition_pair_cancelling'
  | 'composition_pair_contradictory'
  | 'composition_meditation_suppression'
  | 'composition_retrieval_mismatch'
  | 'replay_affect_mismatch'
  | 'meditation_entrypoint_cold'
  | 'composition_meditation_cold_topic'

export type CoherenceSeverity = 'info' | 'warning' | 'serious'

export interface InvolvedElement {
  kind: 'composition' | 'meditation_seed' | 'replay' | 'retrieval_policy' | 'claustrum_node'
  id: string
  label: string
}

export interface CoherenceCheck {
  id: string
  detectedAt: string
  category: CoherenceCategory
  severity: CoherenceSeverity
  message: string
  involvedElements: InvolvedElement[]
  recommendation?: string
  ignored?: { reason: string; ignoredAt: string; ignoredBy: 'cassi' | 'operator' }
}

export interface CoherenceDetectorConfig {
  /** Minimum cancellation weight (L1 of overlap) below which `cancelling` is suppressed. */
  cancellingThreshold: number
  /** Fraction of a composition's L1 norm captured by overlap above which it's flagged `contradictory`. */
  contradictoryFraction: number
  /** Maximum top-N coherence checks to render in projection. */
  projectionTopN: number
  /**
   * Euclidean distance on (valence, arousal) above which a scheduled
   * replay's source-affect is flagged as mismatched with current affect.
   * Default 0.7: mild drift (≤ 0.5 in either dim) ignored; strong drift
   * flagged. Range is approximately 0–√(4+1) ≈ 2.24 with valence ∈ [-1,1]
   * and arousal ∈ [0,1].
   */
  replayAffectMismatchThreshold: number
  /**
   * Claustrum activation level at or below which a node is considered
   * "cold" — too inactive to anchor a meditation entry-point or to
   * ground a composition's amplification. Default 0.1.
   */
  coldActivationThreshold: number
}

export const COHERENCE_DEFAULTS: CoherenceDetectorConfig = {
  cancellingThreshold: 0.3,
  contradictoryFraction: 0.5,
  projectionTopN: 3,
  replayAffectMismatchThreshold: 0.7,
  coldActivationThreshold: 0.1,
}
