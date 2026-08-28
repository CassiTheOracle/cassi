/**
 * VENDOR TYPE STUB — `core/intelligence/synapse/index.ts` (`Synapse`).
 *
 * Type-placeholder for the synapse guidance surface consumed by collect-thoughts.ts
 * (tools). Tools hold it as a typed dep (`deps.synapse?.shouldFire` /
 * `generateGuidance` / `getRemainingBudget`); not constructed by the tools or
 * their tests. `SynapseContext`/`SynapseGuidance` come from `@cassicore/foundation`
 * (canonical shapes) so the generateGuidance return matches collect-thoughts'
 * use. Owned by the P5 brain package; re-pointed when it lands (Open-6).
 */

import type { SynapseContext, SynapseGuidance } from '@cassicore/foundation'

/** Gating decision for whether Synapse should fire on a step. */
export interface SynapseGatingResult {
  shouldFire: boolean
  reason: string
}

/** Guidance-firing cost-cohort controller. */
export interface Synapse {
  shouldFire(
    thoughtNumber: number,
    sessionId: string,
    signals: Array<{ confidence: number }>,
    isRevision: boolean,
    branchFromThought: number | undefined,
  ): SynapseGatingResult
  generateGuidance(context: SynapseContext, sessionId: string): Promise<SynapseGuidance | null>
  getRemainingBudget(sessionId: string): number
}
