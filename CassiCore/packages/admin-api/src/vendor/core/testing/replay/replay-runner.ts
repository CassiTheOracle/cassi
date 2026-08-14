import { LiveWorkflowHarness } from '../live/live-harness.js'
import { ScenarioRunner } from '../verification/scenario-runner.js'

import type { ReplayComparisonReport, ReplayConfig } from '@cassicore/foundation'
import type { WorkflowScenario } from '../verification/scenario-types.js'

export class ReplayRunner {
  async run(
    sessionId: string,
    scenario: WorkflowScenario,
    baseline: ReplayConfig = {},
    treatment: ReplayConfig = {},
  ): Promise<ReplayComparisonReport> {
    const baselineHarness = new LiveWorkflowHarness({
      baseUrl: baseline.baseUrl,
      turnTimeoutMs: baseline.timeoutMs,
      autoPrune: true,
    })
    const treatmentHarness = new LiveWorkflowHarness({
      baseUrl: treatment.baseUrl,
      turnTimeoutMs: treatment.timeoutMs,
      autoPrune: true,
    })

    const baselineRunner = new ScenarioRunner(baselineHarness)
    const treatmentRunner = new ScenarioRunner(treatmentHarness)

    const baselineResult = await baselineRunner.run(scenario)
    const treatmentResult = await treatmentRunner.run(scenario)

    return {
      sessionId,
      scenario: scenario as ReplayComparisonReport['scenario'],
      baseline: baselineResult,
      treatment: treatmentResult,
      comparison: {
        baselinePassed: baselineResult.passed,
        treatmentPassed: treatmentResult.passed,
        baselineDurationMs: baselineResult.durationMs,
        treatmentDurationMs: treatmentResult.durationMs,
        baselineEventCount: baselineResult.trace.eventCount,
        treatmentEventCount: treatmentResult.trace.eventCount,
      },
    }
  }
}
