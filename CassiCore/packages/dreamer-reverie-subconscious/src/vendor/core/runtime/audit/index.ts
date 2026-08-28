/**
 * Run/Step audit layer — public API (vendor stub).
 *
 * Faithful surface of `core/runtime/audit/index.ts`. The AsyncLocalStorage
 * helpers (`withStep` / `resolveProvenance` / `currentStep` / ...) are real
 * self-contained runtime copies (step-context.ts). `AuditStore` is carried as
 * a TYPE stub here: this package only receives an injected instance via
 * `setAudit(...)` and never constructs one, so the runtime SQLite implementation
 * is not reproduced in these stubs (it lives in Part B's vendored audit-store,
 * and ultimately re-points to @cassicore/events at P6).
 */

import { withStep, withStepAsync, currentStep, legacyProvenance, resolveProvenance } from './step-context.js'
import type { Run, Step, RunKind, Provenance, RunCreate, StepCreate } from './types.js'

export { withStep, withStepAsync, currentStep, legacyProvenance, resolveProvenance }
export type { Run, Step, RunKind, Provenance, RunCreate, StepCreate }

type MetricsSnapshot = { runs: number; openRuns: number; steps: number; avgStepMs: number | null }

/**
 * AuditStore — SQLite-backed run/step ledger. Type-only surface of the method
 * set this package touches on an injected instance (startRun / startStep /
 * finishRun / finishStep / queries). The faithful runtime impl is vendored in
 * @cassicore/lamina-locus-bridge (Part B) and ultimately lives in
 * @cassicore/events (P6).
 */
export interface AuditStore {
  startRun(input: RunCreate): Run
  finishRun(id: string, status?: 'completed' | 'failed' | 'aborted'): void
  getRun(id: string): Run | null
  listRuns(opts?: { sessionId?: string; agentId?: string; status?: Run['status']; limit?: number }): Run[]
  startStep(input: StepCreate): Step
  finishStep(id: string, opts?: { status?: 'completed' | 'failed'; toolCallCount?: number }): void
  getStep(id: string): Step | null
  listSteps(runId: string): Step[]
  metrics(): MetricsSnapshot
  setMnemicField(field: unknown): void
  close(): void
}
