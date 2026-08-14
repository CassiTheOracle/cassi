/**
 * Scenario type definitions — the shared schema for workflow verification.
 *
 * Scenarios are backend-agnostic: the same definition runs against
 * the vitest harness (mocked) or the live daemon (via admin API).
 */

import type { EventType } from '@cassicore/foundation'


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


export interface ScenarioStep {
  /** Human-readable label for this step */
  label?: string

  /** Action to perform */
  action: StepAction

  /** Assertions to verify after the action */
  assertions?: StepAssertion[]
}

export type StepAction =
  | { type: 'turn'; message: string }
  | { type: 'wait'; ms: number }
  | { type: 'inject-event'; event: { type: EventType; payload: Record<string, unknown> } }
  | { type: 'snapshot'; label: string }


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

/** Context passed to custom assertion functions */
export interface AssertionContext {
  /** The traced events for this scenario run */
  trace: import('./event-trace.js').EventTraceCollector
  /** State snapshots captured during the run */
  snapshots: Map<string, import('./state-snapshot.js').StateSnapshot>
  /** The most recent turn result, if applicable */
  lastTurnResult?: TurnResult
  /** The session ID used for this scenario run */
  sessionId: string
}


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

export interface StepResult {
  index: number
  label?: string
  passed: boolean
  durationMs: number
  assertions: AssertionResult[]
}

export interface AssertionResult {
  type: string
  passed: boolean
  detail?: string
}

export interface TurnResult {
  response: string
  durationMs: number
  model?: string
  tokensUsed?: number
  toolCalls?: Array<{ name: string; args: unknown; result?: string }>
}


/**
 * WorkflowBackend — the execution interface that both the vitest harness
 * and the live HTTP harness implement.
 */
export interface WorkflowBackend {
  /** Create an isolated test session */
  createSession(config?: Record<string, unknown>): Promise<string>

  /** Execute a turn in the given session */
  executeTurn(sessionId: string, message: string): Promise<TurnResult>

  /** Capture current state as a snapshot */
  snapshot(sessionId?: string): Promise<import('./state-snapshot.js').StateSnapshot>

  /** Access the event trace collector */
  readonly trace: import('./event-trace.js').EventTraceCollector

  /** Clean up (delete test sessions, disconnect listeners) */
  teardown(): Promise<void>
}
