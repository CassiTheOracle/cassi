// Scenario registry — all available workflow scenarios
import { multiTurnContext } from './multi-turn-context.js'
import { thinkerInjection } from './thinker-injection.js'
import { providerFailure } from './provider-failure.js'
import { toolExecution } from './tool-execution.js'
import type { WorkflowScenario } from '../verification/scenario-types.js'

/** All registered scenarios, keyed by name */
export const scenarios: Record<string, WorkflowScenario> = {
  'multi-turn-context': multiTurnContext,
  'thinker-injection': thinkerInjection,
  'provider-failure': providerFailure,
  'tool-execution': toolExecution,
}

/** Get a scenario by name, or undefined if not found */
export function getScenario(name: string): WorkflowScenario | undefined {
  return scenarios[name]
}

/** List all available scenario names with descriptions */
export function listScenarios(): Array<{ name: string; description: string; stepCount: number }> {
  return Object.values(scenarios).map(s => ({
    name: s.name,
    description: s.description,
    stepCount: s.steps.length,
  }))
}
