/**
 * Reverie types — ambient in-flight memory curator.
 */

import type { Provenance } from '../../runtime/audit/index.js'
import type { RetrievalLabelTriple } from './retrieval-labeler-types.js'

/** Trigger source classification. */
export type ReverieTriggerKind = 'step_count' | 'affect_spike' | 'ping_lamina' | 'manual' | 'idle'

export interface ReverieTrigger {
  kind: ReverieTriggerKind
  reason: string
  /** Reverie skips its own triggers — agentId guards against cascades. */
  agentId: string
  occurredAt: number
}

export interface ReverieEdit {
  action:
    | 'lamina.append'
    | 'lamina.replace'
    | 'lamina.rethink'
    | 'task-tree.rethink'
    | 'contradiction.flag'
    | 'loop.detect'
    | 'mnemic.promote'
    | 'mnemic.label_retrieval'
    | 'note'
  label?: string
  content: string
  reason: string
  /** Optional engram id for mnemic.promote */
  engramId?: string
  /** For replace — the contentHash the model believed it was overwriting */
  expectedHash?: string | null
  /** For mnemic.label_retrieval — structured training-request payload */
  labels?: RetrievalLabelTriple[]
}

export interface ReverieDecision {
  silence: boolean
  edits: ReverieEdit[]
  notes: string[]
}

export interface ReverieRecord {
  id: string
  sessionId: string
  trigger: ReverieTrigger
  decision: ReverieDecision
  durationMs: number
  budgetTokens: number
  startedAt: string
  finishedAt: string
  status: 'completed' | 'budget_exhausted' | 'failed' | 'suppressed'
  provenance: Provenance | null
}

export interface ReverieConfig {
  enabled: boolean
  /** Steps between scheduled ambient triggers — default 3 for responsiveness */
  stepInterval: number
  /** Hard token budget per session per day */
  sessionTokenBudget: number
  /** Latency above which subsequent triggers are skipped */
  slowThresholdMs: number
  /** Number of triggers to skip after a slow run */
  slowSkipCount: number
  /** Per-session minimum interval between Reverie runs (debounce) */
  minIntervalMs: number
  /** Inactivity window before generating a replay session summary. */
  summaryInactivityMs: number
  /** Max replay events included in a summary prompt. */
  summaryMaxEvents: number
}

export const DEFAULT_REVERIE_CONFIG: ReverieConfig = {
  enabled: true,
  stepInterval: 3,
  sessionTokenBudget: 50_000,
  slowThresholdMs: 5_000,
  slowSkipCount: 3,
  minIntervalMs: 2_000,
  summaryInactivityMs: 30 * 60 * 1000,
  summaryMaxEvents: 80,
}
