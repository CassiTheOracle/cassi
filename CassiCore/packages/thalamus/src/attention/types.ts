export type ThalamusMode = 'off' | 'observe' | 'inject'

export type AttentionKind =
  | 'goal'
  | 'constraint'
  | 'decision'
  | 'open_loop'
  | 'evidence'
  | 'artifact'
  | 'failure'
  | 'memory'

export type AttentionState = 'active' | 'resolved' | 'superseded' | 'stale'

export type AttentionAuthority =
  | 'direct_user'
  | 'agent'
  | 'tool'
  | 'memory'
  | 'external_data'

export interface AttentionObservation {
  type: 'user' | 'assistant' | 'tool_result' | 'compaction' | 'pin' | 'unpin' | 'invalidate'
  turnId: number
  sourceId: string
  text?: string
  timestamp?: number
  toolName?: string
  toolCallId?: string
  isError?: boolean
  unitId?: string
}
export interface ExactObservationReference {
  recordId: string
  revision: string
  packetSha256: string
  packetObjectSha256: string
  payloadManifestSha256: string
  journalHeadSha256: string
  viewSha256: string
  codecId: string
  sourceStreamId: string
  sourceSequence: number
  sourcePath?: readonly (string | number)[]
  sourceSpan?: readonly [number, number]
}


export interface ContextCandidate {
  id: string
  /** Exact Mnemic content revision used by the field's deletion path. */
  revision?: string
  /** Exact source record and UTF-8 byte range represented by this candidate. */
  recordId?: string
  startByte?: number
  endByte?: number
  source: 'mnemic' | 'aurora' | 'pineal' | 'field'
  text: string
  score: number
  sourceRefs?: string[]
  /** Semantic role for a field-owned active-development candidate. */
  workingKind?: 'goal' | 'artifact' | 'failure'
  metadata?: Record<string, unknown>
  /** Fixed upstream admission. False candidates are ineligible and never enter the plan. */
  eligible?: boolean
  /** Required records sort first but never grant authorization. */
  required?: boolean
  /** Fixed semantic class; candidates cannot claim user-goal or constraint authority. */
  kind?: 'evidence' | 'artifact' | 'failure' | 'memory'
  authority?: 'tool' | 'memory' | 'external_data'
  /** Hard per-candidate byte/token upper bound, including item overhead. */
  workBudget?: number
  /** Exact Mnemic → ingress-journal evidence identity; no payload copy. */
  observation?: ExactObservationReference
}

export interface ContextSourceStatus {
  source: 'local' | 'mnemic' | 'aurora' | 'pineal' | 'field'
  status: 'ready' | 'timeout' | 'offline' | 'error' | 'disabled'
  latencyMs?: number
  error?: string
}

export interface FieldAdvisory {
  mode: 'shadow'
  observedAt: number
  step: number | null
  time: number | null
  balance?: {
    meanRho: number
    meanEpsilon: number
    meanFieldPower: number
    meanCoherence: number
  }
  temporal?: {
    resultant: number
    weightedMeanAbsoluteIncrement: number
    samples: number
  }
  jProxy?: {
    rms: number
    samples: number
  }
  helical?: {
    canonicalSpiral: false
    bestValue: number
    bestAxis: 'x' | 'y' | 'z' | null
    bestMode: number
    modeZero: readonly [number, number, number]
    samples: number
  }
}

export interface ContextFrame {
  turnId: number
  query: string
  modelId?: string
  contextTokens?: number
  contextWindow?: number
  maxPacketTokens?: number
  sourceStatuses?: ContextSourceStatus[]
  fieldAdvisory?: FieldAdvisory
}

export interface PlannedAttentionItem {
  unitId: string
  kind: AttentionKind
  authority: AttentionAuthority
  text: string
  reason: string
  estimatedTokens: number
  sourceRefs: readonly string[]
}

export interface ContextPlan {
  schemaVersion: 1
  id: string
  sessionId: string
  turnId: number
  ledgerRevision: number
  budgetTokens: number
  estimatedTokens: number
  items: readonly PlannedAttentionItem[]
  omitted: number
  sourceStatuses: readonly ContextSourceStatus[]
  fieldAdvisory?: FieldAdvisory
}

export interface ContextPlanReceipt {
  schemaVersion: 1
  planId: string
  sessionId: string
  turnId: number
  ledgerRevision: number
  packetHash: string
  included: readonly {
    unitId: string
    reason: string
    estimatedTokens: number
    sourceRefs: readonly string[]
  }[]
  omitted: number
  sourceStatuses: readonly ContextSourceStatus[]
  fieldAdvisory?: FieldAdvisory
}

export interface AttentionStatus {
  sessionId: string
  revision: number
  turnId: number | null
  units: number
  active: number
  resolved: number
  pinned: number
  latestPlanId?: string
}

export interface ThalamusAttentionConfig {
  maxPacketTokens?: number
  minHeadroomTokens?: number
  recentGoalLimit?: number
  maxUnitChars?: number
  /** Hard bound on retained per-session semantic units. Default 256. */
  maxUnits?: number
}
