/**
 * UCF (Universal Calibration Framework) — type surface.
 *
 * Probe sets are owned by a spec (A2, B2, C1, C3, B6, C2 — eventually). UCF
 * stores them, runs them on schedule, computes drift between consecutive
 * runs, and emits AEJ events when drift crosses a threshold. Per-spec
 * adapters supply the MeasurementFn (probe → result) and may override the
 * default DriftMetricFn.
 *
 * See: docs/design/aurora-universal-calibration-framework.md §2
 */

export type DriftRecommendation =
  | 'no_action'
  | 'investigate'
  | 'recalibrate'
  | 'serious_drift_review'

export interface MeasurementResult {
  probeId: string
  /** Numeric measurements produced by the spec adapter. The default drift
   * metric averages L1 differences across keys; per-spec adapters can
   * override with their own DriftMetricFn. */
  values: Record<string, number>
  /** Optional pass/fail flag for boolean probes. */
  pass?: boolean
  /** Free-form metadata the per-spec adapter wants preserved across runs. */
  metadata?: Record<string, unknown>
}

export interface DriftReport {
  magnitude: number             // 0..1
  affected: string[]            // probe ids with significant drift
  recommendation: DriftRecommendation
  perProbeMagnitude?: Record<string, number>
}

export interface Probe {
  id: string
  input: unknown
  expected?: unknown
  weight?: number
  metadata?: Record<string, unknown>
}

export type MeasurementFn = (probe: Probe) => Promise<MeasurementResult> | MeasurementResult
export type DriftMetricFn = (prior: MeasurementResult[], current: MeasurementResult[]) => DriftReport

export interface CalibrationSchedule {
  cron?: string
  triggeredBy?: 'startup' | 'on_drift_alert' | 'manual'
  frequency: 'daily' | 'weekly' | 'monthly' | 'manual'
}

export interface CalibrationProbeSet {
  id: string
  ownerSpec: string
  description: string
  probes: Probe[]
  measurement: MeasurementFn
  driftMetric?: DriftMetricFn   // omitted → default mean-L1 metric
  schedule: CalibrationSchedule
  metadata?: Record<string, unknown>
}

export interface CalibrationResult {
  id: string
  probeSetId: string
  ranAt: string
  results: MeasurementResult[]
  drift: DriftReport | null
  newParameters?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export interface RunOptions {
  /** Optional: caller can override the schedule's session id for the run. */
  sessionId?: string | null
  /** Skip drift comparison even if a prior run exists. Useful for first-run
   * baselines that should not emit a drift event. */
  skipDriftComparison?: boolean
}

/**
 * Default thresholds for the drift recommendation classifier (spec §4.3).
 * Magnitudes are normalized to [0, 1].
 */
export const DRIFT_TIERS = {
  low: 0.05,
  moderate: 0.15,
  high: 0.30,
} as const

export function classifyDrift(magnitude: number): DriftRecommendation {
  if (magnitude < DRIFT_TIERS.low) return 'no_action'
  if (magnitude < DRIFT_TIERS.moderate) return 'investigate'
  if (magnitude < DRIFT_TIERS.high) return 'recalibrate'
  return 'serious_drift_review'
}
