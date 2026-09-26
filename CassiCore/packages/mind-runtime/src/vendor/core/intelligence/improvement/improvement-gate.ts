/**
 * Improvement Gate — Configurable sync/async verification gate.
 *
 * Before any adaptation is applied, the gate captures baseline scenario results.
 * After the adaptation, it re-runs scenarios and compares. If regressions are
 * detected, the adaptation is automatically reverted.
 *
 * Supports two modes:
 *   - **sync** (default): Block → baseline → apply → verify → revert on fail
 *   - **async**: Apply → schedule background verify → revert on fail within window
 *
 * Low-risk proposals can opt into async even in sync-default mode via
 * `config.lowRiskAsyncAllowed`.
 */

import { ScenarioRunner } from '../../testing/verification/scenario-runner.js'
import type { ScenarioResult, WorkflowBackend } from '../../testing/verification/scenario-types.js'
import type { ScenarioStore } from '../../testing/scenarios/scenario-store.js'
import type { ILogger, IEventBus } from '@cassicore/foundation'
import type {
  ImprovementProposal,
  ImprovementConfig,
  GateMode,
  GateResult,
  GateVerdict,
} from './types.js'

export class ImprovementGate {
  private readonly logger: ILogger
  private readonly config: ImprovementConfig
  private readonly scenarioStore: ScenarioStore
  private eventBus?: IEventBus
  private backend?: WorkflowBackend
  private backendLabel?: string

  /** Track pending async reverts */
  private pendingAsyncReverts = new Map<string, NodeJS.Timeout>()

  constructor(deps: {
    logger: ILogger
    config: ImprovementConfig
    scenarioStore: ScenarioStore
    eventBus?: IEventBus
  }) {
    this.logger = deps.logger.child?.('improvement-gate') ?? deps.logger
    this.config = deps.config
    this.scenarioStore = deps.scenarioStore
    this.eventBus = deps.eventBus
  }

  /** Set the workflow backend (in-process or live) */
  setBackend(backend: WorkflowBackend, label?: string): void {
    this.backend = backend
    this.backendLabel = label
    this.logger.info('Verification backend wired', {
      backend: label ?? backend.constructor?.name ?? 'unknown',
    })
  }

  /** Set the event bus used for gate lifecycle events */
  setEventBus(eventBus: IEventBus): void {
    this.eventBus = eventBus
  }

  /** Whether a verification backend is currently available */
  hasBackend(): boolean {
    return !!this.backend
  }

  /** Human-readable backend label for diagnostics */
  getBackendLabel(): string | undefined {
    return this.backendLabel
  }


  /**
   * Evaluate a proposal through the verification gate.
   *
   * @param proposal - The improvement proposal to evaluate
   * @param applyFn - Callback that applies the adaptation
   * @param revertFn - Callback that reverts the adaptation
   * @returns Gate result with verdict and scenario comparisons
   */
  async evaluate(
    proposal: ImprovementProposal,
    applyFn: () => Promise<void>,
    revertFn: () => Promise<void>,
  ): Promise<GateResult> {
    const startMs = Date.now()
    const mode = this.resolveMode(proposal)

    this.logger.info('Evaluating proposal', {
      proposalId: proposal.id,
      mode,
      trigger: proposal.trigger,
      riskLevel: proposal.riskLevel,
    })

    this.emitEvent('improvement:gate-started', { proposalId: proposal.id, mode })

    // Get scenarios to run — skip if no backend or no scenarios
    const scenarios = this.scenarioStore.getForGate()
    if (!this.backend || scenarios.length === 0) {
      this.logger.info('Skipping gate — no backend or no scenarios', {
        hasBackend: !!this.backend,
        scenarioCount: scenarios.length,
      })

      // Apply directly
      await applyFn()

      const result: GateResult = {
        proposalId: proposal.id,
        mode,
        verdict: 'skipped',
        beforeResults: [],
        afterResults: [],
        regressions: [],
        improvements: [],
        durationMs: Date.now() - startMs,
      }
      this.emitEvent('improvement:gate-passed', { proposalId: proposal.id, improvements: [] })
      return result
    }

    if (mode === 'sync') {
      return this.evaluateSync(proposal, applyFn, revertFn, scenarios, startMs)
    } else {
      return this.evaluateAsync(proposal, applyFn, revertFn, scenarios, startMs)
    }
  }

  /** Cancel all pending async reverts (for shutdown) */
  cancelPending(): void {
    for (const timeout of this.pendingAsyncReverts.values()) {
      clearTimeout(timeout)
    }
    this.pendingAsyncReverts.clear()
  }


  private async evaluateSync(
    proposal: ImprovementProposal,
    applyFn: () => Promise<void>,
    revertFn: () => Promise<void>,
    scenarios: import('../../testing/verification/scenario-types.js').WorkflowScenario[],
    startMs: number,
  ): Promise<GateResult> {
    // 1. Run baseline scenarios
    const beforeResults = await this.runScenarios(scenarios)

    // 2. Apply the adaptation
    await applyFn()

    // 3. Run verification scenarios
    let afterResults: ScenarioResult[]
    try {
      afterResults = await this.runScenarios(scenarios)
    } catch (err) {
      // If verification crashes, revert and report failure
      this.logger.error('Verification crashed, reverting', { error: String(err) })
      await this.safeRevert(revertFn)

      return {
        proposalId: proposal.id,
        mode: 'sync',
        verdict: 'failed',
        beforeResults,
        afterResults: [],
        regressions: ['verification-crashed'],
        improvements: [],
        durationMs: Date.now() - startMs,
      }
    }

    // 4. Compare results
    const { regressions, improvements } = this.compareResults(beforeResults, afterResults)

    // 5. Record run stats
    this.recordRunStats(beforeResults, afterResults)

    // 6. If regressions detected, revert
    if (regressions.length > 0) {
      this.logger.warn('Regressions detected, reverting', {
        proposalId: proposal.id,
        regressions,
      })
      await this.safeRevert(revertFn)

      const result: GateResult = {
        proposalId: proposal.id,
        mode: 'sync',
        verdict: 'failed',
        beforeResults,
        afterResults,
        regressions,
        improvements,
        durationMs: Date.now() - startMs,
      }
      this.emitEvent('improvement:gate-failed', { proposalId: proposal.id, regressions })
      return result
    }

    // 7. Gate passed
    const result: GateResult = {
      proposalId: proposal.id,
      mode: 'sync',
      verdict: 'passed',
      beforeResults,
      afterResults,
      regressions,
      improvements,
      durationMs: Date.now() - startMs,
    }
    this.emitEvent('improvement:gate-passed', { proposalId: proposal.id, improvements })
    return result
  }


  private async evaluateAsync(
    proposal: ImprovementProposal,
    applyFn: () => Promise<void>,
    revertFn: () => Promise<void>,
    scenarios: import('../../testing/verification/scenario-types.js').WorkflowScenario[],
    startMs: number,
  ): Promise<GateResult> {
    // 1. Run baseline BEFORE applying (still sync for baseline)
    const beforeResults = await this.runScenarios(scenarios)

    // 2. Apply immediately
    await applyFn()

    // 3. Schedule background verification
    const timeout = setTimeout(async () => {
      this.pendingAsyncReverts.delete(proposal.id)

      try {
        const afterResults = await this.runScenarios(scenarios)
        const { regressions } = this.compareResults(beforeResults, afterResults)
        this.recordRunStats(beforeResults, afterResults)

        if (regressions.length > 0) {
          this.logger.warn('Async: regressions detected, reverting', {
            proposalId: proposal.id,
            regressions,
          })
          await this.safeRevert(revertFn)
          this.emitEvent('improvement:gate-failed', { proposalId: proposal.id, regressions })
          this.emitEvent('improvement:reverted', { proposalId: proposal.id, reason: `Regressions: ${regressions.join(', ')}` })
        } else {
          this.emitEvent('improvement:gate-passed', { proposalId: proposal.id, improvements: [] })
        }
      } catch (err) {
        this.logger.error('Async verification failed', { error: String(err) })
        // On error, revert to be safe
        await this.safeRevert(revertFn)
        this.emitEvent('improvement:gate-failed', { proposalId: proposal.id, regressions: ['async-verification-error'] })
      }
    }, this.config.asyncRevertWindowMs)

    this.pendingAsyncReverts.set(proposal.id, timeout)

    // Return immediately with "passed" (optimistic) — background verify may revert later
    return {
      proposalId: proposal.id,
      mode: 'async',
      verdict: 'passed',
      beforeResults,
      afterResults: [], // Not yet available
      regressions: [],
      improvements: [],
      durationMs: Date.now() - startMs,
    }
  }


  private async runScenarios(
    scenarios: import('../../testing/verification/scenario-types.js').WorkflowScenario[],
  ): Promise<ScenarioResult[]> {
    if (!this.backend) return []

    const runner = new ScenarioRunner(this.backend)
    const results: ScenarioResult[] = []

    for (const scenario of scenarios) {
      try {
        const result = await runner.run(scenario)
        results.push(result)
      } catch (err) {
        // Record a failed result instead of crashing the entire gate
        results.push({
          scenario: scenario.name,
          passed: false,
          durationMs: 0,
          sessionId: '',
          steps: [],
          trace: { eventCount: 0, eventTypes: [] },
        })
        this.logger.warn('Scenario execution failed', {
          scenario: scenario.name,
          error: String(err),
        })
      }
    }

    return results
  }


  /** Compare before/after results to detect regressions and improvements */
  private compareResults(
    before: ScenarioResult[],
    after: ScenarioResult[],
  ): { regressions: string[]; improvements: string[] } {
    const regressions: string[] = []
    const improvements: string[] = []

    const beforeMap = new Map<string, ScenarioResult>()
    for (const r of before) {
      beforeMap.set(r.scenario, r)
    }

    for (const afterResult of after) {
      const beforeResult = beforeMap.get(afterResult.scenario)
      if (!beforeResult) continue

      if (beforeResult.passed && !afterResult.passed) {
        regressions.push(afterResult.scenario)
      } else if (!beforeResult.passed && afterResult.passed) {
        improvements.push(afterResult.scenario)
      }
    }

    return { regressions, improvements }
  }


  /** Determine the effective gate mode for a proposal */
  private resolveMode(proposal: ImprovementProposal): GateMode {
    if (this.config.gateMode === 'async') return 'async'
    if (
      this.config.gateMode === 'sync' &&
      proposal.riskLevel === 'low' &&
      this.config.lowRiskAsyncAllowed
    ) {
      return 'async'
    }
    return 'sync'
  }

  /** Safely execute the revert function, catching errors */
  private async safeRevert(revertFn: () => Promise<void>): Promise<void> {
    try {
      await revertFn()
    } catch (err) {
      this.logger.error('Revert failed', { error: String(err) })
    }
  }

  /** Record run stats in the scenario store */
  private recordRunStats(before: ScenarioResult[], after: ScenarioResult[]): void {
    for (const result of [...before, ...after]) {
      this.scenarioStore.recordRun(result.scenario, result.passed)
    }
  }

  /** Emit an event if the event bus is available */
  private emitEvent(type: string, payload: Record<string, unknown>): void {
    if (!this.eventBus) return
    try {
      (this.eventBus as any).emit({ type, ...payload, timestamp: new Date() })
    } catch { /* best effort */ }
  }
}
