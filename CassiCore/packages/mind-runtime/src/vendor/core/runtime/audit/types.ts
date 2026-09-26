/**
 * Run/Step audit types.
 *
 * Run = a single high-level activity (turn, meditation pass, helix branch run, etc.)
 * Step = a single LLM call within that run, including the tool calls it produced
 *
 * Together they form the provenance trail attached to every memory write.
 */

export type RunKind =
  | 'turn'
  | 'reverie'
  | 'meditation'
  | 'helix'
  | 'constellation'
  | 'pineal'
  | 'background'
  | 'import'
  | 'unknown'

export interface Run {
  id: string
  kind: RunKind
  /** Session this run belongs to (when applicable) */
  sessionId: string | null
  /** Agent name responsible (e.g. 'primary', 'reverie', 'unity', 'meditation') */
  agentId: string
  /** Optional parent run for nested activity */
  parentRunId: string | null
  /** Free-form goal/description */
  goal: string | null
  startedAt: string
  finishedAt: string | null
  status: 'open' | 'completed' | 'failed' | 'aborted'
}

export interface Step {
  id: string
  runId: string
  /** Monotonic 1-based step number within the run */
  stepNumber: number
  /** Provider call requestId, if known */
  requestId: string | null
  /** Slot/module name making the call (e.g. 'thinker', 'reverie', 'primary') */
  slot: string
  /** Optional model identifier */
  model: string | null
  /** Optional reason describing why this step ran */
  reason: string | null
  startedAt: string
  finishedAt: string | null
  durationMs: number | null
  status: 'open' | 'completed' | 'failed'
  /** Optional structured tool-call summary (best-effort, not authoritative) */
  toolCallCount: number
}

/** Provenance pointer attached to memory writes. */
export interface Provenance {
  runId: string
  stepId: string
  toolCallId?: string
  agentId: string
  reason?: string
}

export interface RunCreate {
  kind: RunKind
  sessionId?: string | null
  agentId: string
  parentRunId?: string | null
  goal?: string | null
}

export interface StepCreate {
  runId: string
  slot: string
  model?: string | null
  requestId?: string | null
  reason?: string | null
}
