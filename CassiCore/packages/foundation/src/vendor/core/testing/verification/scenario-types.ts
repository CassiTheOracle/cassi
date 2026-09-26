/**
 * VENDOR TYPE STUB — `core/testing/verification/scenario-types.ts`
 *
 * Type-only placeholder for the workflow-verification scenario surface consumed by the P1
 * live-set (`types/replay.ts`): `ScenarioResult`, `WorkflowScenario`. Self-contained; builtin
 * types only; no runtime. Re-pointed to `@cassicore/testing` (or host-wired pkg) at P7/TBD.
 */

/** Event type string (minimal — scenario typing is not structural for P1 consumers). */
type EventType = string

/** Setup configuration for a workflow scenario. */
export interface ScenarioSetup {
  /** Intelligence modules to enable (names) */
  modules?: string[]
  /** Tools to make available */
  tools?: string[]
  /** Pre-seed memory entries */
  initialMemory?: Array<{ key: string; content: string }>
  /** Session configuration overrides */
  sessionConfig?: Record<string, unknown>
}

/** A single scenario step. */
export interface ScenarioStep {
  /** Human-readable label for this step */
  label?: string
  /** Action to perform */
  action: StepAction
  /** Assertions to verify after the action */
  assertions?: StepAssertion[]
}

/** Action a scenario step performs. */
export type StepAction =
  | { type: 'turn'; message: string }
  | { type: 'wait'; ms: number }
  | { type: 'inject-event'; event: { type: EventType; payload: Record<string, unknown> } }
  | { type: 'snapshot'; label: string }

/** Assertion verified after a scenario step. */
export type StepAssertion =
  | { type: 'event-emitted'; event: EventType; has?: Record<string, unknown> }
  | { type: 'event-sequence'; events: Array<EventType | { type: EventType; has?: Record<string, unknown> }> }
  | { type: 'no-event'; event: EventType }
  | { type: 'event-count'; event: EventType; min?: number; max?: number; exact?: number }
  | { type: 'session-state'; path: string; equals?: unknown; greaterThan?: number; lessThan?: number; contains?: string }
  | { type: 'snapshot-diff'; fromLabel: string; changed?: string[]; unchanged?: string[] }
  | { type: 'response-contains'; text: string }
  | { type: 'response-matches'; pattern: string }
  | { type: 'custom'; name: string; check: (context: AssertionContext) => void | Promise<void> }

/** Context passed to custom assertion functions. */
export interface AssertionContext {
  /** The traced events for this scenario run */
  trace: unknown
  /** State snapshots captured during the run */
  snapshots: Map<string, unknown>
  /** The most recent turn result, if applicable */
  lastTurnResult?: unknown
  /** The session ID used for this scenario run */
  sessionId: string
}

/** A workflow scenario: a named, ordered set of steps to verify. */
export interface WorkflowScenario {
  /** Unique scenario name (used as identifier in CLI/API) */
  name: string
  /** Human-readable description */
  description: string
  /** Setup configuration */
  setup?: ScenarioSetup
  /** Ordered steps to execute */
  steps: ScenarioStep[]
  /** Max time for the entire scenario (ms) */
  timeoutMs?: number
}

/** Result of a single scenario assertion. */
export interface AssertionResult {
  type: string
  passed: boolean
  detail?: string
}

/** Result of a single scenario step. */
export interface StepResult {
  index: number
  label?: string
  passed: boolean
  durationMs: number
  assertions: AssertionResult[]
}

/** Result of running a workflow scenario. */
export interface ScenarioResult {
  scenario: string
  passed: boolean
  durationMs: number
  sessionId: string
  steps: StepResult[]
  trace: {
    eventCount: number
    eventTypes: string[]
  }
}
