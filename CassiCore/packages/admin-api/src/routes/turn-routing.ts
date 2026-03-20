import { createHash, randomUUID } from 'node:crypto'

export type TurnEngine = 'session-pipeline' | 'legacy-pipeline'

type Attachment = { mediaType: string; data: string }
type StreamEventCallback = (type: string, data: Record<string, unknown>) => void

interface SessionPipelineResult {
  response: string
  sessionId: string
  model?: string
  tokensUsed?: number
  durationMs?: number
}

interface SessionPipelineLike {
  processMessage(
    channelId: string,
    senderId: string,
    content: string,
    options?: {
      attachments?: Attachment[]
      signal?: AbortSignal
      stream?: boolean
      onStreamEvent?: StreamEventCallback
      model?: string
    },
  ): Promise<SessionPipelineResult>
}

interface LegacyPipelineResult {
  response: string
  model?: string
  tokensUsed?: number
  durationMs?: number
  toolCalls?: unknown
  tool_outputs?: unknown
}

interface LegacyPipelineLike {
  process(inbound: {
    id: string
    sessionId: string
    channelId: string
    senderId: string
    content: string
    attachments?: Attachment[]
    timestamp: Date
  }): Promise<LegacyPipelineResult>
  requestCancel?(sessionId: string): boolean
}

export interface TurnRuntimeLike {
  sessionPipeline?: SessionPipelineLike
  pipeline?: LegacyPipelineLike
}

export interface TurnExecutionRequest {
  requestedSessionId: string
  channelId: string
  senderId: string
  content: string
  attachments?: Attachment[]
  model?: string
  signal?: AbortSignal
  stream?: boolean
  onStreamEvent?: StreamEventCallback
  timestamp?: Date
}

export interface TurnExecutionResult {
  engine: TurnEngine
  requestedSessionId: string
  sessionId: string
  response: string
  model?: string
  tokensUsed?: number
  durationMs?: number
  toolCalls?: unknown
  tool_outputs?: unknown
}

interface ActiveTurnState {
  engine: TurnEngine
  count: number
}

const activeTurns = new Map<string, ActiveTurnState>()

function markTurnStart(sessionId: string, engine: TurnEngine): void {
  const current = activeTurns.get(sessionId)
  if (current?.engine === engine) {
    current.count += 1
    return
  }

  activeTurns.set(sessionId, { engine, count: 1 })
}

function markTurnEnd(sessionId: string, engine: TurnEngine): void {
  const current = activeTurns.get(sessionId)
  if (!current || current.engine !== engine) return

  if (current.count <= 1) {
    activeTurns.delete(sessionId)
    return
  }

  current.count -= 1
}

export function getPreferredTurnEngine(runtime: TurnRuntimeLike): TurnEngine | null {
  if (runtime.sessionPipeline) return 'session-pipeline'
  if (runtime.pipeline) return 'legacy-pipeline'
  return null
}

export function resolveSessionPipelineSessionId(channelId: string, senderId: string): string {
  return createHash('sha256')
    .update(`${channelId}:${senderId}`)
    .digest('hex')
    .slice(0, 16)
}

export function resolveStreamSessionId(
  runtime: TurnRuntimeLike,
  requestedSessionId: string,
  channelId: string,
  senderId: string,
): string {
  if (runtime.sessionPipeline) {
    return resolveSessionPipelineSessionId(channelId, senderId)
  }

  return requestedSessionId
}

export function getActiveTurnEngine(sessionId: string): TurnEngine | null {
  return activeTurns.get(sessionId)?.engine ?? null
}

export function cancelTurn(
  runtime: TurnRuntimeLike,
  sessionId: string,
): { engine: TurnEngine | null; supported: boolean; cancelled: boolean; active: boolean } {
  const activeEngine = getActiveTurnEngine(sessionId)

  if (activeEngine === 'session-pipeline') {
    return {
      engine: activeEngine,
      supported: false,
      cancelled: false,
      active: true,
    }
  }

  if (runtime.pipeline && typeof runtime.pipeline.requestCancel === 'function') {
    return {
      engine: activeEngine ?? 'legacy-pipeline',
      supported: true,
      cancelled: runtime.pipeline.requestCancel(sessionId),
      active: activeEngine === 'legacy-pipeline',
    }
  }

  return {
    engine: activeEngine ?? getPreferredTurnEngine(runtime),
    supported: false,
    cancelled: false,
    active: activeEngine !== null,
  }
}

export async function executeTurn(
  runtime: TurnRuntimeLike,
  request: TurnExecutionRequest,
): Promise<TurnExecutionResult> {
  if (runtime.sessionPipeline) {
    markTurnStart(request.requestedSessionId, 'session-pipeline')
    try {
      const result = await runtime.sessionPipeline.processMessage(
        request.channelId,
        request.senderId,
        request.content,
        {
          attachments: request.attachments,
          signal: request.signal,
          stream: request.stream,
          onStreamEvent: request.onStreamEvent,
          model: request.model && request.model !== 'unknown' ? request.model : undefined,
        },
      )

      return {
        engine: 'session-pipeline',
        requestedSessionId: request.requestedSessionId,
        ...result,
      }
    } finally {
      markTurnEnd(request.requestedSessionId, 'session-pipeline')
    }
  }

  if (!runtime.pipeline) {
    throw new Error('pipeline not ready')
  }

  markTurnStart(request.requestedSessionId, 'legacy-pipeline')
  try {
    const result = await runtime.pipeline.process({
      id: randomUUID(),
      sessionId: request.requestedSessionId,
      channelId: request.channelId,
      senderId: request.senderId,
      content: request.content,
      attachments: request.attachments,
      timestamp: request.timestamp ?? new Date(),
    })

    return {
      engine: 'legacy-pipeline',
      requestedSessionId: request.requestedSessionId,
      sessionId: request.requestedSessionId,
      response: result.response,
      model: result.model,
      tokensUsed: result.tokensUsed,
      durationMs: result.durationMs,
      toolCalls: result.toolCalls,
      tool_outputs: result.tool_outputs,
    }
  } finally {
    markTurnEnd(request.requestedSessionId, 'legacy-pipeline')
  }
}
