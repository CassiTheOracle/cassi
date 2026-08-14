/**
 * VENDOR TYPE STUB — `core/intelligence/synapse/index.ts` (`Synapse`).
 *
 * Type-placeholder for the synapse guidance surface consumed by collect-thoughts.ts
 * (tools). Tools hold it as a typed dep (`deps.synapse?.shouldFire` /
 * `generateGuidance` / `getRemainingBudget`); not constructed by the tools or
 * their tests. Owned by the P5 brain package; re-pointed when it lands (Open-6).
 */

import type { CognitiveSignal, CognitiveSignalRef } from '../thought-observer.js'
import type { ResonancePattern } from '../cognitive-bridge.js'

/** Gating decision for whether Synapse should fire on a step. */
export interface SynapseGatingResult {
  shouldFire: boolean
  reason: string
}

/** Context provided to Synapse for guidance generation. */
export interface SynapseContext {
  tree: string
  currentStep: { number: number; content: string }
  signals: CognitiveSignal[]
  relatedMemory: string
  peerSignals: CognitiveSignalRef[]
  resonance: ResonancePattern[]
  energy?: string
  isRevision?: boolean
  revisesStep?: number
}

/** Guidance returned by Synapse for a reasoning step. */
export interface SynapseGuidance {
  content: string
  reason?: string
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
