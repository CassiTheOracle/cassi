/**
 * Replay System Types — A/B testing and scenario comparison framework.
 *
 * Enables comparing baseline vs treatment runs of the same scenario to
 * measure performance differences, regression detection, and improvement tracking.
 */

import type { ScenarioResult, WorkflowScenario } from '../core/testing/verification/scenario-types.js'

/** Configuration for replay execution */
export interface ReplayConfig {
  /** Base URL for the service under test */
  baseUrl?: string
  /** Request timeout in milliseconds */
  timeoutMs?: number
  /** Additional configuration parameters */
  config?: Record<string, unknown>
}

/** Comparison report between baseline and treatment runs */
export interface ReplayComparisonReport {
  /** Session ID for the replay run */
  sessionId: string
  /** The workflow scenario being tested */
  scenario: WorkflowScenario
  /** Baseline run results */
  baseline: ScenarioResult
  /** Treatment run results */
  treatment: ScenarioResult
  /** Comparison metrics */
  comparison: {
    /** Whether baseline passed validation */
    baselinePassed: boolean
    /** Whether treatment passed validation */
    treatmentPassed: boolean
    /** Baseline execution duration in ms */
    baselineDurationMs: number
    /** Treatment execution duration in ms */
    treatmentDurationMs: number
    /** Number of events in baseline run */
    baselineEventCount: number
    /** Number of events in treatment run */
    treatmentEventCount: number
  }
}
