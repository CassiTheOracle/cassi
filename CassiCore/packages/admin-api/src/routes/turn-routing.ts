import { createHash, randomUUID } from 'node:crypto'

export type TurnEngine = 'session-pipeline' | 'legacy-pipeline'

type Attachment = { mediaType: string; data: string }
type StreamEventCallback = (type: string, data: Record<string, unknown>) => void

type ToolNameSource = { name: string }

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
      maxToolRounds?: number
    },
  ): Promise<SessionPipelineResult>

  /** Process a turn for an already-known session ID. */
  processTurn(
    sessionId: string,
    content: string,
    options?: {
      channelId?: string
      senderId?: string
      attachments?: Attachment[]
      signal?: AbortSignal
      stream?: boolean
      onStreamEvent?: StreamEventCallback
      model?: string
      maxToolRounds?: number
    },
  ): Promise<SessionPipelineResult>

  /** Cancel an active turn.  Returns true if a turn was aborted. */
  requestCancel(sessionId: string): boolean
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
    onStreamEvent?: StreamEventCallback
  }): Promise<LegacyPipelineResult>
  requestCancel?(sessionId: string): boolean
}

interface LegacySessionLike {
  id: string
  history: any[]
}

interface LegacySessionManagerLike {
  getOrCreateById(
    stableId: string,
    channelId: string,
    senderId: string,
    config?: Record<string, unknown>,
  ): LegacySessionLike
}

interface ConfigLike {
  get?<T>(key: string, fallback: T): T
}

interface ToolRegistryLike {
  list?(): ToolNameSource[]
  getAll?(): Record<string, unknown>
}

interface DialecticLike {
  processTurn(
    sessionId: string,
    turnId: string,
    content: string,
    context: Record<string, unknown>,
    options?: Record<string, unknown>,
  ): Promise<any>
}

export interface TurnRuntimeLike {
  sessionPipeline?: SessionPipelineLike
  pipeline?: LegacyPipelineLike
  sessions?: LegacySessionManagerLike
  config?: ConfigLike
  toolRegistry?: ToolRegistryLike
  intelligence?: {
    dialectic?: DialecticLike
  }
}

export interface TurnExecutionRequest {
  requestedSessionId: string
  channelId: string
  senderId: string
  content: string
  attachments?: Attachment[]
  model?: string
  maxToolRounds?: number
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

export interface TurnCancellationResult {
  engine: TurnEngine | null
  supported: boolean
  cancelled: boolean
  active: boolean
}

export interface LegacySessionPreparationRequest {
  sessionId: string
  channelId: string
  senderId: string
  model?: string
  thinking?: string
  systemPrompt?: string
}

export interface LegacyDialecticRequest {
  sessionId: string
  turnId: string
  content: string
  sessionHistory: any[]
  taskGuide?: string
  dialecticMode?: string
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

/**
 * @dep callers: start (core/daemon.ts), createAdminRuntimeFacade (core/admin-api/runtime.ts), cancelTurn (core/admin-api/turn-routing.ts)
 * @dep module: Admin-api
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

export function getPreferredTurnEngine(runtime: TurnRuntimeLike): TurnEngine | null {
  if (runtime.sessionPipeline) return 'session-pipeline'
  if (runtime.pipeline) return 'legacy-pipeline'
  return null
}

/**
 * @dep callers: admin-turn-routing.test.ts (tests/admin-turn-routing.test.ts), resolveStreamSessionId (core/admin-api/turn-routing.ts)
 * @dep flows: HandleSessionsRoutes → ResolveSessionPipelineSessionId (4/4)
 * @dep module: Admin-api
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */

export function resolveSessionPipelineSessionId(channelId: string, senderId: string): string {
  return createHash('sha256')
    .update(`${channelId}:${senderId}`)
    .digest('hex')
    .slice(0, 16)
}

/**
 * @dep callers: admin-turn-routing.test.ts (tests/admin-turn-routing.test.ts), handleChatRoutes (core/admin-api/chat.ts), createAdminRuntimeFacade (core/admin-api/runtime.ts), handleSseStream (core/admin-api/sessions.ts)
 * @dep calls: resolveSessionPipelineSessionId
 * @dep flows: HandleSessionsRoutes → ResolveSessionPipelineSessionId (3/4)
 * @dep module: Admin-api
 * @dep risk: MEDIUM | 4 callers, 1 flow, 1 module
 */

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

/**
 * @dep callers: admin-turn-routing.test.ts (tests/admin-turn-routing.test.ts), handleChatRoutes (core/admin-api/chat.ts), createAdminRuntimeFacade (core/admin-api/runtime.ts)
 * @dep calls: requestCancel, getPreferredTurnEngine, getActiveTurnEngine
 * @dep module: Admin-api
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */

export function cancelTurn(
  runtime: TurnRuntimeLike,
  sessionId: string,
): TurnCancellationResult {
  const activeEngine = getActiveTurnEngine(sessionId)

  if (activeEngine === 'session-pipeline') {
    if (runtime.sessionPipeline && typeof runtime.sessionPipeline.requestCancel === 'function') {
      return {
        engine: activeEngine,
        supported: true,
        cancelled: runtime.sessionPipeline.requestCancel(sessionId),
        active: true,
      }
    }
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

/**
 * @dep callers: createAdminRuntimeFacade (core/admin-api/runtime.ts), ensureLegacySession (core/admin-api/turn-routing.ts)
 * @dep calls: get
 * @dep module: Admin-api
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function buildLegacySessionConfig(
  runtime: TurnRuntimeLike,
  request: LegacySessionPreparationRequest,
): Record<string, unknown> {
  const modelFallback = runtime.config?.get?.('session.model', 'kimi-coding/k2p5') ?? 'kimi-coding/k2p5'
  const thinkingFallback = runtime.config?.get?.('session.thinking', 'high') ?? 'high'

  const sessionConfig: Record<string, unknown> = {
    model: request.model || modelFallback,
    thinking: request.thinking || thinkingFallback,
  }

  if (request.systemPrompt) {
    sessionConfig.systemPrompt = request.systemPrompt
  }

  return sessionConfig
}

export function ensureLegacySession(
  runtime: TurnRuntimeLike,
  request: LegacySessionPreparationRequest,
): LegacySessionLike {
  if (!runtime.sessions) {
    throw new Error('legacy session manager not available')
  }

  return runtime.sessions.getOrCreateById(
    request.sessionId,
    request.channelId,
    request.senderId,
    buildLegacySessionConfig(runtime, request),
  )
}

/**
 * @dep callers: createAdminRuntimeFacade (core/admin-api/runtime.ts), runLegacyDialectic (core/admin-api/turn-routing.ts)
 * @dep calls: getAll
 * @dep flows: HandleSessionsRoutes → GetAvailableToolNames (3/3)
 * @dep module: Admin-api
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */

export function getAvailableToolNames(runtime: TurnRuntimeLike): string[] {
  if (typeof runtime.toolRegistry?.list === 'function') {
    return runtime.toolRegistry.list().map(tool => tool.name)
  }

  if (typeof runtime.toolRegistry?.getAll === 'function') {
    return Object.keys(runtime.toolRegistry.getAll() || {})
  }

  return []
}

/**
 * @dep callers: createAdminRuntimeFacade (core/admin-api/runtime.ts), handleSessionsRoutes (core/admin-api/sessions.ts)
 * @dep calls: processTurn, getAvailableToolNames
 * @dep flows: HandleSessionsRoutes → GetAvailableToolNames (2/3)
 * @dep module: Admin-api
 * @dep risk: LOW | 2 callers, 1 flow, 1 module
 */

export async function runLegacyDialectic(
  runtime: TurnRuntimeLike,
  request: LegacyDialecticRequest,
): Promise<any | null> {
  const dialectic = runtime.intelligence?.dialectic
  if (!dialectic) return null

  return dialectic.processTurn(
    request.sessionId,
    request.turnId,
    request.content,
    {
      recentMemories: [],
      availableTools: getAvailableToolNames(runtime),
      sessionHistory: request.sessionHistory,
      taskGuide: request.taskGuide || `Process user message: ${request.content.slice(0, 100)}...`,
    },
    { mode: request.dialecticMode || 'parallel' },
  )
}

/**
 * @dep callers: admin-turn-routing.test.ts (tests/admin-turn-routing.test.ts), workflow-fault-injection.test.ts (tests/workflow-fault-injection.test.ts), workflow-verification.test.ts (tests/workflow-verification.test.ts), run (src/testing/verification/scenario-runner.ts), start (core/daemon.ts) [+4]
 * @dep calls: process, processMessage, markTurnStart, markTurnEnd
 * @dep module: Admin-api
 * @dep risk: HIGH | 9 callers, 0 flows, 1 module
 */

export async function executeTurn(
  runtime: TurnRuntimeLike,
  request: TurnExecutionRequest,
): Promise<TurnExecutionResult> {
  if (runtime.sessionPipeline) {
    markTurnStart(request.requestedSessionId, 'session-pipeline')
    try {
      const result = typeof runtime.sessionPipeline.processTurn === 'function'
        ? await runtime.sessionPipeline.processTurn(
            request.requestedSessionId,
            request.content,
            {
              channelId: request.channelId,
              senderId: request.senderId,
              attachments: request.attachments,
              signal: request.signal,
              stream: request.stream,
              onStreamEvent: request.onStreamEvent,
              model: request.model && request.model !== 'unknown' ? request.model : undefined,
              maxToolRounds: request.maxToolRounds,
            },
          )
        : await runtime.sessionPipeline.processMessage(
            request.channelId,
            request.senderId,
            request.content,
            {
              attachments: request.attachments,
              signal: request.signal,
              stream: request.stream,
              onStreamEvent: request.onStreamEvent,
              model: request.model && request.model !== 'unknown' ? request.model : undefined,
              maxToolRounds: request.maxToolRounds,
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
      onStreamEvent: request.onStreamEvent,
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
