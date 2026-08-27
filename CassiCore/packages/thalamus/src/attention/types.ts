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

export interface ContextCandidate {
  id: string
  source: 'mnemic' | 'aurora' | 'pineal'
  text: string
  score: number
  sourceRefs?: string[]
  metadata?: Record<string, unknown>
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
