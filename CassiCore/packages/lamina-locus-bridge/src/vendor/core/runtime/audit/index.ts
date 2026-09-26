/**
 * Run/Step audit layer — public API (vendor stub).
 *
 * Faithful barrel of `core/runtime/audit/index.ts`. `AuditStore` is a real
 * self-contained RUNTIME copy (audit-store.ts, better-sqlite3-backed); the
 * AsyncLocalStorage helpers (`withStep` / `resolveProvenance` / ...) are real
 * runtime copies (step-context.ts). Re-point to `@cassicore/events` at P6.
 */

export { AuditStore } from './audit-store.js'
export { withStep, withStepAsync, currentStep, legacyProvenance, resolveProvenance } from './step-context.js'
export type { Run, Step, RunKind, Provenance, RunCreate, StepCreate } from './types.js'
