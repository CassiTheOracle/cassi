/**
 * Run/Step audit layer — public API.
 *
 * The AuditStore records every LLM call as a Step within a Run, providing
 * the provenance trail attached to memory writes (Lamina, Mnemic engrams).
 *
 * AsyncLocalStorage helpers (withStep / currentStep) make attribution
 * implicit within a single async context.
 */

export { AuditStore } from './audit-store.js'
export { withStep, withStepAsync, currentStep, legacyProvenance, resolveProvenance } from './step-context.js'
export type { Run, Step, RunKind, Provenance, RunCreate, StepCreate } from './types.js'
