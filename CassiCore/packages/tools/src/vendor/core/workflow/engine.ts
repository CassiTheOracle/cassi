/**
 * VENDOR TYPE STUB — `core/workflow/engine.ts` (`WorkflowEngine`).
 *
 * Type placeholder for the workflow engine surface consumed by tools workflow.ts
 * (`getEngine: () => WorkflowEngine | null` + engine methods execute/getRun/
 * resume/cancel/listRuns). Mirrors the source signatures. Owned by
 * `@cassicore/workflow` (P6); re-pointed there.
 */
import type { WorkflowDefinition, WorkflowRun, WorkflowState } from '@cassicore/foundation'

/** Error raised when a workflow suspends for external input. */
export class SuspendSignal extends Error {
  runId: string
  state?: WorkflowState
  constructor(runId: string, message: string, state?: WorkflowState) {
    super(message)
    this.name = 'SuspendSignal'
    this.runId = runId
    this.state = state
  }
}

/** Engine that executes, manages, and stores workflow runs. */
export interface WorkflowEngine {
  execute(
    definition: WorkflowDefinition,
    input?: unknown,
    opts?: { runId?: string; initialState?: WorkflowState },
  ): Promise<WorkflowRun>
  resume(
    definition: WorkflowDefinition,
    runId: string,
    resumeInput?: unknown,
  ): Promise<WorkflowRun>
  cancel(runId: string, reason: string): Promise<void>
  getRun(runId: string): WorkflowRun | undefined
  listRuns(): WorkflowRun[]
}
