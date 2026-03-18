// ── Injection Tracking ─────────────────────────────────────────────────────

export interface TraceInjectionPart {
  source: string
  content: string
  charCount: number
  priority?: number
  reason?: string
  /** Whether this injection was truncated to fit within source caps */
  wasTruncated?: boolean
  /** Original character count before truncation (if truncated) */
  originalCharCount?: number
  /** Timestamp when this injection was collected (epoch ms) */
  collectedAtMs?: number
}

/** Records an injection that was dropped or timed out */
export interface TraceDroppedInjection {
  source: string
  reason: 'timeout' | 'cap_exceeded' | 'truncated' | 'error'
  originalCharCount?: number
  timeoutMs?: number
  timestamp?: number
}

// ── Tool Call Tracking ─────────────────────────────────────────────────────

export interface TraceToolCall {
  name: string
  durationMs?: number
  input?: unknown
  outputSummary?: string
  isError?: boolean
  permissionVerdict?: 'allow' | 'deny' | 'escalate' | 'unknown'
  riskScore?: number
}

// ── Cognitive Signal Tracking ──────────────────────────────────────────────

export interface TraceCognitiveSignal {
  source: string
  kind: string
  confidence: number
  text: string
}

// ── Context Mutation Tracking ──────────────────────────────────────────────

/** Records a destructive mutation to the context window (truncation, pruning, trimming) */
export interface TraceContextMutation {
  type: 'tool_result_truncated' | 'tool_result_summarized' | 'context_pruned'
       | 'section_dropped' | 'history_trimmed' | 'gap_annotation_inserted'
       | 'emergency_trim' | 'mid_loop_trim'
  messageIndex?: number
  originalChars: number
  afterChars: number
  reason: string
  timestamp?: number
}

// ── Team Context ───────────────────────────────────────────────────────────

/** Links a TurnTrace to its team cell — the join key for unified timelines */
export interface TraceTeamContext {
  teamId: string
  cellId: string
  cellRole: 'proposer' | 'critic' | 'executor'
  cellDepth: number
  parentCellId?: string
  phase: string
}

// ── Thinking Summary ───────────────────────────────────────────────────────

export interface TraceThinkingSummary {
  /** Total characters of thinking output */
  totalChars: number
  /** Number of cognitive signals extracted from thinking */
  signalsExtracted: number
  /** Whether thinking output was truncated before analysis */
  truncated: boolean
}

// ── TurnTrace (enhanced) ───────────────────────────────────────────────────

export interface TurnTrace {
  id: string
  turnId: string
  sessionId: string
  timestamp: number

  input: {
    message: string
    attachmentCount: number
  }

  contextSnapshot: {
    historyMessageCount: number
    injections: TraceInjectionPart[]
    retrievedMemories: Array<{ id?: string; type?: string; source?: string; summary: string }>
    /** Injections that were dropped due to timeout, cap, or error */
    droppedInjections?: TraceDroppedInjection[]
    /** Destructive mutations applied to the context before/during the turn */
    mutations?: TraceContextMutation[]
  }

  providerCall: {
    model: string
    tokensUsed: number
    durationMs: number
    toolCalls: TraceToolCall[]
  }

  /** Cognitive signals extracted from thinking output (was always [] before — now populated) */
  cognitiveSignals: TraceCognitiveSignal[]

  pendingInjections: TraceInjectionPart[]

  response: {
    text: string
  }

  /** Team context — present when this trace belongs to a team cell turn */
  teamContext?: TraceTeamContext

  /** Summary of thinking output captured during this turn */
  thinkingSummary?: TraceThinkingSummary

  /** IDs referencing full context window snapshots in the ContextSnapshotStore */
  contextSnapshotIds?: string[]
}
