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
}

export const COHERENCE_DEFAULTS: CoherenceDetectorConfig = {
  cancellingThreshold: 0.3,
  contradictoryFraction: 0.5,
  projectionTopN: 3,
}
