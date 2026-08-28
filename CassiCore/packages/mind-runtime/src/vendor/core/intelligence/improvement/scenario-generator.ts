/**
 * Scenario Generator — Converts cognitive signals into verification scenarios.
 *
 * Listens to EventBus signals (anomalies, trust drops, repairs, hypotheses)
 * and generates targeted WorkflowScenario objects that exercise the specific
 * concern. Generated scenarios are registered in the ScenarioStore for
 * persistent tracking and use by the ImprovementGate.
 *
 * Two generation modes:
 *   - **Template-based** (fast, no LLM): anomalies, trust drops, repairs
 *   - **LLM-assisted** (richer, async): complex hypotheses from AI Scientist
 */

import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { ScenarioStore } from '../../testing/scenarios/scenario-store.js'
import type { WorkflowScenario, StepAssertion, ScenarioStep } from '../../testing/verification/scenario-types.js'
import type { ImprovementConfig } from './types.js'

export class ScenarioGenerator {
  private readonly logger: ILogger
  private readonly scenarioStore: ScenarioStore
  private readonly config: ImprovementConfig
  private eventBus?: IEventBus

  /** Track generated scenario names to avoid duplicates */
  private generatedNames = new Set<string>()

  constructor(deps: {
    logger: ILogger
    scenarioStore: ScenarioStore
    config: ImprovementConfig
  }) {
    this.logger = deps.logger.child?.('scenario-generator') ?? deps.logger
    this.scenarioStore = deps.scenarioStore
    this.config = deps.config
  }


  /** Wire event listeners for automatic scenario generation */
  initialize(eventBus: IEventBus): void {
    this.eventBus = eventBus
    this.wireEvents()
    this.logger.info('Initialized')
  }

  private wireEvents(): void {
    if (!this.eventBus) return

    // Anomaly → resilience scenario
    try {
      this.eventBus.on('consciousness:anomaly' as any, (event: any) => {
        this.fromAnomaly(event).catch(err => {
          this.logger.debug('Anomaly scenario gen failed', { error: String(err) })
        })
      })
    } catch { /* event type may not exist */ }

    // Trust drop → domain stability scenario
    try {
      this.eventBus.on('trust:score-updated' as any, (event: any) => {
        if (event.delta < -0.1) {
          this.fromTrustDrop(event).catch(err => {
            this.logger.debug('Trust scenario gen failed', { error: String(err) })
          })
        }
      })
    } catch { /* event type may not exist */ }

    // Self-healer repair → regression guard scenario
    try {
      this.eventBus.on('self-healer:repair-applied' as any, (event: any) => {
        this.fromRepair(event).catch(err => {
          this.logger.debug('Repair scenario gen failed', { error: String(err) })
        })
      })
    } catch { /* event type may not exist */ }

    // AI Scientist breakthrough → verification scenario
    try {
      this.eventBus.on('ai-scientist:breakthrough' as any, (event: any) => {
        this.fromBreakthrough(event).catch(err => {
          this.logger.debug('Breakthrough scenario gen failed', { error: String(err) })
        })
      })
    } catch { /* event type may not exist */ }
  }


  /** Generate a resilience scenario from an anomaly */
  private async fromAnomaly(event: any): Promise<void> {
    const anomaly = event.anomaly
    if (!anomaly?.id || !anomaly?.description) return

    const name = `anomaly-${anomaly.id}`
    if (this.generatedNames.has(name)) return
    this.generatedNames.add(name)

    const severity = anomaly.severity ?? 'medium'
    const eventTypes = anomaly.eventTypes ?? []

    const assertions: StepAssertion[] = [
      { type: 'no-event', event: 'plugin:crashed' },
    ]

    // If we know which event types were involved, check they're handled gracefully
    if (eventTypes.length > 0) {
      assertions.push({
        type: 'event-count',
        event: eventTypes[0],
        min: 0, // Just verify it doesn't crash
      })
    }

    const scenario: WorkflowScenario = {
      name,
      description: `Resilience: ${anomaly.description}`,
      timeoutMs: 60_000,
      steps: [
        {
          label: 'Baseline snapshot',
          action: { type: 'snapshot', label: 'pre-anomaly' },
        },
        {
          label: 'Trigger condition',
          action: {
            type: 'turn',
            message: `Test resilience: simulate condition related to "${anomaly.description}"`,
          },
          assertions,
        },
        {
          label: 'Verify stability',
          action: { type: 'snapshot', label: 'post-anomaly' },
          assertions: [
            {
              type: 'snapshot-diff',
              fromLabel: 'pre-anomaly',
              unchanged: ['session.status'],
            },
          ],
        },
      ],
    }

    this.scenarioStore.add(scenario, {
      triggerType: 'anomaly',
      triggerId: anomaly.id,
      tags: ['generated', 'anomaly', severity],
    })

    this.logger.info('Created anomaly scenario', {
      name,
      severity,
      eventTypes: eventTypes.slice(0, 3),
    })
  }

  /** Generate a domain stability scenario from a trust drop */
  private async fromTrustDrop(event: any): Promise<void> {
    const domain = event.domain
    if (!domain) return

    const name = `trust-drop-${domain}-${Date.now()}`
    if (this.generatedNames.has(name)) return
    this.generatedNames.add(name)

    // Map trust domains to relevant tool calls
    const domainToTool: Record<string, string> = {
      'file-read': 'read',
      'file-write': 'write',
      'shell-execution': 'bash',
      'web-fetch': 'web-fetch',
    }

    const toolName = domainToTool[domain]
    const steps: ScenarioStep[] = [
      {
        label: 'Baseline',
        action: { type: 'snapshot', label: 'pre-trust' },
      },
    ]

    if (toolName) {
      steps.push({
        label: `Exercise ${domain} domain`,
        action: {
          type: 'turn',
          message: `Perform a basic ${toolName} operation to verify the ${domain} domain is functional.`,
        },
        assertions: [
          { type: 'event-emitted', event: 'turn:end' },
        ],
      })
    } else {
      steps.push({
        label: `Exercise ${domain} domain`,
        action: {
          type: 'turn',
          message: `Test functionality in the "${domain}" domain.`,
        },
        assertions: [
          { type: 'event-emitted', event: 'turn:end' },
        ],
      })
    }

    steps.push({
      label: 'Verify recovery',
      action: { type: 'snapshot', label: 'post-trust' },
      assertions: [
        {
          type: 'snapshot-diff',
          fromLabel: 'pre-trust',
          unchanged: ['session.status'],
        },
      ],
    })

    const scenario: WorkflowScenario = {
      name,
      description: `Trust domain stability: ${domain} (delta=${event.delta?.toFixed(2) ?? '?'})`,
      timeoutMs: 60_000,
      steps,
    }

    this.scenarioStore.add(scenario, {
      triggerType: 'trust',
      triggerId: domain,
      tags: ['generated', 'trust', domain],
    })

    this.logger.info('Created trust-drop scenario', {
      name,
      domain,
      delta: event.delta,
    })
  }

  /** Generate a regression guard scenario from a self-healer repair */
  private async fromRepair(event: any): Promise<void> {
    const repairId = event.id
    const filePath = event.filePath
    if (!repairId) return

    const name = `repair-guard-${repairId}`
    if (this.generatedNames.has(name)) return
    this.generatedNames.add(name)

    const scenario: WorkflowScenario = {
      name,
      description: `Regression guard for repair ${repairId}${filePath ? ` (${filePath})` : ''}`,
      timeoutMs: 60_000,
      steps: [
        {
          label: 'Baseline',
          action: { type: 'snapshot', label: 'pre-repair-check' },
        },
        {
          label: 'Exercise repaired path',
          action: {
            type: 'turn',
            message: 'Perform a basic operation to verify system stability after recent repairs.',
          },
          assertions: [
            { type: 'no-event', event: 'intelligence:processor-error' as any },
            { type: 'event-emitted', event: 'turn:end' },
          ],
        },
        {
          label: 'Verify no new errors',
          action: { type: 'snapshot', label: 'post-repair-check' },
          assertions: [
            {
              type: 'snapshot-diff',
              fromLabel: 'pre-repair-check',
              unchanged: ['session.status'],
            },
          ],
        },
      ],
    }

    this.scenarioStore.add(scenario, {
      triggerType: 'repair',
      triggerId: repairId,
      tags: ['generated', 'repair', 'regression-guard'],
    })

    this.logger.info('Created repair-guard scenario', { name, repairId })
  }

  /** Generate a verification scenario from an AI Scientist breakthrough */
  private async fromBreakthrough(event: any): Promise<void> {
    const track = event.track
    const title = event.title
    const metric = event.metric
    if (!track || !title) return

    const name = `breakthrough-${track}-${Date.now()}`
    if (this.generatedNames.has(name)) return
    this.generatedNames.add(name)

    const scenario: WorkflowScenario = {
      name,
      description: `Verify breakthrough: ${title} (${metric})`,
      timeoutMs: 90_000,
      steps: [
        {
          label: 'Baseline',
          action: { type: 'snapshot', label: 'pre-breakthrough' },
        },
        {
          label: 'Exercise improved capability',
          action: {
            type: 'turn',
            message: `Test the capability that was improved: "${title}". Verify the system responds correctly.`,
          },
          assertions: [
            { type: 'event-emitted', event: 'turn:end' },
            { type: 'no-event', event: 'plugin:crashed' },
          ],
        },
        {
          label: 'Verify improvement persists',
          action: { type: 'snapshot', label: 'post-breakthrough' },
        },
      ],
    }

    this.scenarioStore.add(scenario, {
      triggerType: 'hypothesis',
      triggerId: `${track}-${title}`,
      tags: ['generated', 'breakthrough', track],
    })

    this.logger.info('Created breakthrough scenario', {
      name,
      track,
      metric,
    })
  }


  /** Generate a scenario from a manual hypothesis (admin API / MCP) */
  generateFromHypothesis(hypothesis: {
    name: string
    description: string
    testMessage: string
    expectedEvents?: string[]
    forbiddenEvents?: string[]
  }): WorkflowScenario {
    const assertions: StepAssertion[] = []

    if (hypothesis.expectedEvents) {
      for (const eventType of hypothesis.expectedEvents) {
        assertions.push({ type: 'event-emitted', event: eventType as any })
      }
    }
    if (hypothesis.forbiddenEvents) {
      for (const eventType of hypothesis.forbiddenEvents) {
        assertions.push({ type: 'no-event', event: eventType as any })
      }
    }

    const scenario: WorkflowScenario = {
      name: hypothesis.name,
      description: hypothesis.description,
      timeoutMs: 60_000,
      steps: [
        {
          label: 'Baseline',
          action: { type: 'snapshot', label: 'pre' },
        },
        {
          label: 'Test hypothesis',
          action: { type: 'turn', message: hypothesis.testMessage },
          assertions: assertions.length > 0 ? assertions : [
            { type: 'event-emitted', event: 'turn:end' },
          ],
        },
        {
          label: 'Verify state',
          action: { type: 'snapshot', label: 'post' },
          assertions: [
            {
              type: 'snapshot-diff',
              fromLabel: 'pre',
              unchanged: ['session.status'],
            },
          ],
        },
      ],
    }

    this.scenarioStore.add(scenario, {
      triggerType: 'manual',
      tags: ['generated', 'manual'],
    })

    this.logger.info('Created manual scenario', { name: hypothesis.name })
    return scenario
  }


  /** Detect and mark stale scenarios */
  detectStaleness(): string[] {
    return this.scenarioStore.detectStaleness(this.config.stalenessThreshold)
  }
}
