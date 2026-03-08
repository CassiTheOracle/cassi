export interface TraceInjectionPart {
  source: string
  content: string
  charCount: number
  priority?: number
  reason?: string
}

export interface TraceToolCall {
  name: string
  durationMs?: number
  input?: unknown
  outputSummary?: string
  isError?: boolean
  permissionVerdict?: 'allow' | 'deny' | 'escalate' | 'unknown'
  riskScore?: number
}

export interface TraceCognitiveSignal {
  source: string
  kind: string
  confidence: number
  text: string
}

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
  }
  providerCall: {
    model: string
    tokensUsed: number
    durationMs: number
    toolCalls: TraceToolCall[]
  }
  cognitiveSignals: TraceCognitiveSignal[]
  pendingInjections: TraceInjectionPart[]
  response: {
    text: string
  }
}
