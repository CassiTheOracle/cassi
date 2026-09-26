/**
 * step-context.ts — AsyncLocalStorage-based attribution layer.
 * Faithful self-contained copy of `core/runtime/audit/step-context.ts`.
 *
 * Wrap any async work in `withStep({runId, stepId, agentId})` and downstream
 * memory writes can call `currentStep()` to discover their provenance without
 * threading it through every signature.
 *
 * Note: AsyncLocalStorage does NOT propagate across worker_threads — workers
 * accept explicit context params instead.
 */

import { AsyncLocalStorage } from 'node:async_hooks'

import type { Provenance } from './types.js'

const storage = new AsyncLocalStorage<Provenance>()

/** Run `fn` with the given step context. Nested calls override. */
export function withStep<T>(ctx: Provenance, fn: () => T): T {
  return storage.run(ctx, fn)
}

/** Run `fn` with the given step context (async variant — same impl, kept for clarity). */
export async function withStepAsync<T>(ctx: Provenance, fn: () => Promise<T>): Promise<T> {
  return storage.run(ctx, fn)
}

/** Get the current step context, or null if none is active. */
export function currentStep(): Provenance | null {
  return storage.getStore() ?? null
}

/** Convenience: build a legacy fallback when no context is set. */
export function legacyProvenance(agentId = 'legacy'): Provenance {
  return { runId: 'legacy', stepId: 'legacy', agentId }
}

/** Resolve provenance: the active step, or a legacy fallback. */
export function resolveProvenance(agentId = 'unknown'): Provenance {
  return currentStep() ?? legacyProvenance(agentId)
}
