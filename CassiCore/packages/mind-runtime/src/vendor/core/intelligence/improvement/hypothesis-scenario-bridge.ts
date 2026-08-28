/**
 * Hypothesis Scenario Bridge — Translates AI Scientist hypotheses into
 * targeted verification scenarios.
 *
 * Unlike the template-based ScenarioGenerator, this bridge uses specific
 * hypothesis parameters (KV key, parameter name, metric, direction) to
 * create precise pre-experiment validation and post-experiment guard scenarios.
 */

import type { ILogger } from '@cassicore/foundation'
import type { ScenarioStore } from '../../testing/scenarios/scenario-store.js'
import type { WorkflowScenario, StepAssertion } from '../../testing/verification/scenario-types.js'

/** Hypothesis structure from AI Scientist */
export interface HypothesisInput {
  title: string
  hypothesis: string
  rationale: string
  track: string
  metric: string
  higherIsBetter: boolean
  treatment: {
    kvKey: string
    parameterName: string
    currentValue: unknown
    proposedValue: unknown
    reloadEvent?: string
  }
}

/** Experiment conclusion data */
export interface ExperimentConclusion {
  experimentId: string
  title: string
  track: string
  metric: string
  higherIsBetter: boolean
  outcome: 'improvement' | 'neutral' | 'regression' | 'insufficient_data'
  deltaPercent: number
  effectSize: number
  pValue: number
  treatment: {
    kvKey: string
    parameterName: string
    baselineValue: unknown
    treatmentValue: unknown
  }
}

/** Maps metrics to natural-language exercise messages */
const METRIC_EXERCISES: Record<string, string> = {
  'thinker_helpfulness': 'Analyze a complex technical problem that requires deep reasoning about architecture tradeoffs.',
  'thinker_insight_rate': 'Review recent session patterns and identify opportunities for cognitive improvement.',
  'turn_latency_ms': 'Quickly answer: what is the current system status and health?',
  'dialectic_signal_rate': 'Consider the pros and cons of restructuring the event bus to use priority queues.',
  'session_depth': 'Continue our discussion about optimizing the intelligence module pipeline.',
}

export class HypothesisScenarioBridge {
  private readonly logger: ILogger
  private readonly scenarioStore: ScenarioStore
  private generatedNames = new Set<string>()

  constructor(deps: {
    logger: ILogger
    scenarioStore: ScenarioStore
  }) {
    this.logger = deps.logger.child?.('hypothesis-bridge') ?? deps.logger
    this.scenarioStore = deps.scenarioStore
  }

  /**
   * Generate a pre-experiment validation scenario.
   * Tests that the baseline state is stable enough for experimentation.
   */
  fromHypothesisPreExperiment(hypothesis: HypothesisInput): WorkflowScenario | null {
    const safeName = this.sanitizeName(hypothesis.title)
    const name = `pre-exp-${hypothesis.track}-${safeName}-${Date.now()}`
    if (this.generatedNames.has(name)) return null
    this.generatedNames.add(name)

    const exerciseMessage = METRIC_EXERCISES[hypothesis.metric]
      ?? `Perform a task that exercises the ${hypothesis.metric} capability.`

    const scenario: WorkflowScenario = {
      name,
      description: `Pre-experiment baseline check: ${hypothesis.title}`,
      timeoutMs: 60_000,
      steps: [
        {
          label: 'Capture pre-experiment baseline',
          action: { type: 'snapshot', label: 'pre-experiment-baseline' },
        },
        {
          label: 'Exercise target capability at baseline',
          action: { type: 'turn', message: exerciseMessage },
          assertions: [
            { type: 'event-emitted', event: 'turn:end' as any },
            { type: 'no-event', event: 'plugin:crashed' as any },
            { type: 'no-event', event: 'intelligence:processor-error' as any },
          ],
        },
        {
          label: 'Confirm baseline stability',
          action: { type: 'snapshot', label: 'post-baseline-exercise' },
          assertions: [
            {
              type: 'snapshot-diff',
              fromLabel: 'pre-experiment-baseline',
              unchanged: ['session.status'],
            },
          ],
        },
      ],
    }

    this.scenarioStore.add(scenario, {
      triggerType: 'hypothesis',
      triggerId: `pre-${hypothesis.track}-${safeName}`,
      tags: ['generated', 'pre-experiment', hypothesis.track, hypothesis.metric],
    })

    this.logger.info('Created pre-experiment scenario', {
      name, track: hypothesis.track, metric: hypothesis.metric,
    })
    return scenario
  }

  /**
   * Generate a post-experiment regression guard.
   * More targeted than fromBreakthrough() — uses actual parameter values and metric-specific assertions.
   */
  fromExperimentConclusion(conclusion: ExperimentConclusion): WorkflowScenario | null {
    if (conclusion.outcome !== 'improvement') return null

    const safeName = this.sanitizeName(conclusion.title)
    const name = `guard-${conclusion.track}-${safeName}-${conclusion.experimentId}`
    if (this.generatedNames.has(name)) return null
    this.generatedNames.add(name)

    const exerciseMessage = METRIC_EXERCISES[conclusion.metric]
      ?? `Exercise the ${conclusion.metric} capability to verify the improvement persists.`

    const assertions: StepAssertion[] = [
      { type: 'event-emitted', event: 'turn:end' as any },
      { type: 'no-event', event: 'plugin:crashed' as any },
    ]

    // Add metric-specific assertions based on the improvement direction
    if (conclusion.metric === 'turn_latency_ms') {
      // For latency, we don't want huge regressions
      assertions.push({ type: 'no-event', event: 'intelligence:processor-error' as any })
    }

    const scenario: WorkflowScenario = {
      name,
      description: `Regression guard: ${conclusion.title} (${conclusion.metric} improved ${conclusion.deltaPercent.toFixed(1)}%, p=${conclusion.pValue.toFixed(3)})`,
      timeoutMs: 90_000,
      steps: [
        {
          label: 'Pre-guard snapshot',
          action: { type: 'snapshot', label: 'guard-baseline' },
        },
        {
          label: 'Exercise improved capability',
          action: { type: 'turn', message: exerciseMessage },
          assertions,
        },
        {
          label: 'Verify no degradation',
          action: { type: 'snapshot', label: 'guard-post' },
          assertions: [
            {
              type: 'snapshot-diff',
              fromLabel: 'guard-baseline',
              unchanged: ['session.status'],
            },
          ],
        },
      ],
    }

    this.scenarioStore.add(scenario, {
      triggerType: 'hypothesis',
      triggerId: `guard-${conclusion.experimentId}`,
      tags: ['generated', 'regression-guard', conclusion.track, conclusion.metric,
             `effect-${conclusion.effectSize > 0.5 ? 'large' : conclusion.effectSize > 0.2 ? 'medium' : 'small'}`],
    })

    this.logger.info('Created regression guard scenario', {
      name, track: conclusion.track, metric: conclusion.metric,
      deltaPercent: conclusion.deltaPercent, pValue: conclusion.pValue,
    })
    return scenario
  }

  /**
   * Generate a counter-hypothesis scenario (falsification check).
   * Tests the OPPOSITE of what the hypothesis predicts — if this passes
   * consistently, the hypothesis may be wrong.
   */
  fromCounterHypothesis(hypothesis: HypothesisInput): WorkflowScenario | null {
    const safeName = this.sanitizeName(hypothesis.title)
    const name = `counter-${hypothesis.track}-${safeName}-${Date.now()}`
    if (this.generatedNames.has(name)) return null
    this.generatedNames.add(name)

    // Build an exercise that specifically targets what the hypothesis claims to improve
    const exerciseMessage = METRIC_EXERCISES[hypothesis.metric]
      ?? `Perform a demanding task that stresses the ${hypothesis.metric} capability.`

    // Counter-hypothesis: if the metric is SUPPOSED to improve, check if it actually degrades
    const counterDescription = hypothesis.higherIsBetter
      ? `Counter-hypothesis: verify ${hypothesis.metric} doesn't degrade when ${hypothesis.treatment.parameterName} changes`
      : `Counter-hypothesis: verify ${hypothesis.metric} doesn't increase when ${hypothesis.treatment.parameterName} changes`

    const scenario: WorkflowScenario = {
      name,
      description: counterDescription,
      timeoutMs: 60_000,
      steps: [
        {
          label: 'Baseline snapshot',
          action: { type: 'snapshot', label: 'counter-baseline' },
        },
        {
          label: 'Stress-test target capability',
          action: { type: 'turn', message: `Stress test: ${exerciseMessage} Provide a thorough, detailed response.` },
          assertions: [
            { type: 'event-emitted', event: 'turn:end' as any },
            { type: 'no-event', event: 'plugin:crashed' as any },
          ],
        },
        {
          label: 'Second stress turn (detect latent issues)',
          action: { type: 'turn', message: 'Continue the previous analysis with additional depth. Focus on edge cases and potential failure modes.' },
          assertions: [
            { type: 'event-emitted', event: 'turn:end' as any },
          ],
        },
        {
          label: 'Verify system stability',
          action: { type: 'snapshot', label: 'counter-post' },
          assertions: [
            {
              type: 'snapshot-diff',
              fromLabel: 'counter-baseline',
              unchanged: ['session.status'],
            },
          ],
        },
      ],
    }

    this.scenarioStore.add(scenario, {
      triggerType: 'counter-hypothesis',
      triggerId: `counter-${hypothesis.track}-${safeName}`,
      tags: ['generated', 'counter-hypothesis', hypothesis.track, hypothesis.metric],
    })

    this.logger.info('Created counter-hypothesis scenario', {
      name, track: hypothesis.track, metric: hypothesis.metric,
    })
    return scenario
  }

  private sanitizeName(title: string): string {
    return title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40)
  }
}
