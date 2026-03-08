import type { ScenarioResult, WorkflowScenario } from '../src/testing/verification/scenario-types.js'

export interface ReplayConfig {
  baseUrl?: string
  timeoutMs?: number
  config?: Record<string, unknown>
}

export interface ReplayComparisonReport {
  sessionId: string
  scenario: WorkflowScenario
  baseline: ScenarioResult
  treatment: ScenarioResult
  comparison: {
    baselinePassed: boolean
    treatmentPassed: boolean
    baselineDurationMs: number
    treatmentDurationMs: number
    baselineEventCount: number
    treatmentEventCount: number
  }
}
