// Verification framework — shared core
export { EventTraceCollector, TraceAssertionError } from './event-trace.js'
export type { TracedEvent, EventMatcher } from './event-trace.js'

export { StateSnapshot, SnapshotAssertionError } from './state-snapshot.js'
export type { SnapshotData, SessionState, ModuleState, SnapshotDiff, DiffEntry } from './state-snapshot.js'

export { ScenarioRunner } from './scenario-runner.js'
export type {
  WorkflowScenario,
  WorkflowBackend,
  ScenarioSetup,
  ScenarioStep,
  StepAction,
  StepAssertion,
  AssertionContext,
  ScenarioResult,
  StepResult,
  AssertionResult,
  TurnResult,
} from './scenario-types.js'
