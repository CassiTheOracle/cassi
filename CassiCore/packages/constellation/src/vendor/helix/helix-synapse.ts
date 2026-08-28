/**
 * VENDORED TYPE STUB — mirrors `helix/helix-synapse.js` (CassiCore).
 * Surface used by constellation (cluster-observer-layer, corpus-observer-layer) and the
 * vendored runtime: SynapseBroadcast, SynapseRollingSlice, HelixSynapse + the method
 * surface the observer layers call. The full `HelixSynapse` runtime class lives in the daemon.
 */
export type HelixRole = 'unity' | 'yang' | 'yin' | string

export interface SynapseRollingSlice {
  posture: HelixRole | string
  fromSeq: number
  toSeq: number
  overlapFromSeq: number
  rendered: string
  tokenEstimate: number
  metadata: {
    eventCount: number
    latestToolNames: string[]
    hasRecentError: boolean
    lastAssistantTextPreview: string
  }
}

export interface SynapseBroadcast {
  id: string
  helixId: string
  source?: string
  content: string
  priority: 'ambient' | 'normal' | 'urgent'
  createdAt: number
  expiresAt: number
  targetPostures: Array<HelixRole | string>
  references: Array<{ posture: string; fromSeq: number; toSeq: number }>
}

export interface HelixSynapseConfig {
  /** Configure max events per slice (used by observers). */
  maxEventsPerSlice?: number
  overlapEvents?: number
  maxCharsPerPosture?: number
  [key: string]: unknown
}

export interface HelixSynapse {
  helixId: string
  goal: string
  renderSlicesForObserver(
    observerId: string,
    config?: Partial<Pick<HelixSynapseConfig, 'maxEventsPerSlice' | 'overlapEvents' | 'maxCharsPerPosture'>>,
  ): SynapseRollingSlice[]
  markObservedBy(observerId: string): void
  enqueueExternalBroadcast(input: {
    source: string
    content: string
    priority?: SynapseBroadcast['priority']
    targetPostures?: Array<HelixRole | string>
    ttlMs?: number
    references?: SynapseBroadcast['references']
  }): SynapseBroadcast
  [key: string]: unknown
}
