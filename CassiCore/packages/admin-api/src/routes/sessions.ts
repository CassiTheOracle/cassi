import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

import type { AdminRuntimeFacade } from './runtime.js'

export interface SessionsRoutesDeps {
  runtime: AdminRuntimeFacade
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  getFirstUserMessage: (history: any[]) => string
  getLastUserMessage: (history: any[]) => string
  tcpHost: string
  currentTcpPort: number
}

/**
 * @dep callers: admin-turn-routing.test.ts (tests/admin-turn-routing.test.ts), handler (core/admin-api.ts)
 * @dep calls: end, on, emit, off, get [+20]
 * @dep flows: HandleSessionsRoutes → Now (1/4), HandleSessionsRoutes → End (1/4), HandleSessionsRoutes → ResolveSessionPipelineSessionId (1/4) [+2]
 * @dep module: Admin-api
 * @dep risk: HIGH | 2 callers, 5 flows, 1 module
 */

export async function handleSessionsRoutes(
  deps: SessionsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string,
  parts: string[]
): Promise<boolean> {
  const { runtime, logger, sendJSON, parseBody, getFirstUserMessage, getLastUserMessage } = deps

  if (parts[0] !== 'sessions') return false

  // POST /sessions/:id/turn (non-streaming)
  if (parts.length === 3 && parts[2] === 'turn' && method === 'POST' && !(req.headers.accept || '').toLowerCase().includes('text/event-stream')) {
    const sessionId = parts[1]
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }

    const body = await parseBody(req)
    const content: string = body?.content
    if (!content) {
      sendJSON(res, 400, { error: 'missing content' })
      return true
    }

    try {
      const channelId = body?.channelId || 'channel:cli'
      const senderId = body?.senderId || sessionId

      if (runtime.preferredTurnEngine() === 'session-pipeline') {
        logger.info(`Processing turn`, { sessionId: sessionId.slice(0, 8) })
        const startTime = Date.now()
        const result = await runtime.executeTurn({
          requestedSessionId: sessionId,
          channelId,
          senderId,
          content,
          attachments: body?.attachments,
          model: body?.model,
        })
        const durationMs = Date.now() - startTime

        sendJSON(res, 200, {
          ok: true,
          sessionId: result.sessionId,
          requestedSessionId: sessionId,
          engine: result.engine,
          response: result.response,
          model: result.model ?? 'unknown',
          tokensUsed: result.tokensUsed ?? 0,
          durationMs,
        })
        return true
      }

      // Legacy pipeline path — only used when sessionPipeline is not available
      if (!runtime.getPipeline()) {
        sendJSON(res, 503, { error: 'pipeline not ready' })
        return true
      }

      const { randomUUID } = await import('node:crypto')
      const inbound = {
        id: randomUUID(),
        sessionId,
        channelId,
        senderId,
        content,
        timestamp: new Date(),
      }

      // Build session config — only include fields that are explicitly provided
      // so undefined values don't override SessionManager defaults (e.g. systemPrompt)
      const session = runtime.getLegacySession({
        sessionId,
        channelId: inbound.channelId,
        senderId: inbound.senderId,
        model: body?.model,
        thinking: body?.thinking,
        systemPrompt: body?.systemPrompt,
      })

      let dialecticResult: any = null
      const dialecticEnabled = body?.dialectic !== false && runtime.getIntelligence()?.dialectic

      if (dialecticEnabled) {
        try {
          dialecticResult = await runtime.runLegacyDialectic({
            sessionId,
            turnId: inbound.id,
            content,
            sessionHistory: session.history,
            taskGuide: body?.taskGuide,
            dialecticMode: body?.dialecticMode,
          })
        } catch (dialecticErr) {
          logger.warn(`dialectic error: ${String(dialecticErr)}`)
        }
      }

      let result: any
      try {
        result = await runtime.getPipeline().process(inbound)
      } catch (pipelineErr) {
        logger.error(`pipeline.process failed: ${String(pipelineErr)}`)
        throw pipelineErr
      }

      const response: any = {
        ok: true,
        engine: 'legacy-pipeline',
        sessionId,
        requestedSessionId: sessionId,
        response: result.response,
        model: result.model,
        tokensUsed: result.tokensUsed,
        durationMs: result.durationMs,
        toolCalls: result.toolCalls,
        tool_outputs: result.tool_outputs,
        dialectic: dialecticResult ? {
          signalInjected: dialecticResult.signalInjected,
          yangBranches: dialecticResult.yang?.branches?.length || 0,
          yinCritiques: dialecticResult.yin?.critiques?.length || 0,
          synthesis: dialecticResult.serenity?.synthesis?.hasSignal
            ? {
                type: dialecticResult.serenity.synthesis.signal?.type,
                content: dialecticResult.serenity.synthesis.signal?.content,
                confidence: dialecticResult.serenity.synthesis.signal?.confidence,
              }
            : null,
        } : null,
      }

      sendJSON(res, 200, response)
      return true
    } catch (err) {
      logger.error(`turn error: ${String(err)}`)
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /sessions/:id/turn/stream (SSE streaming)
  if (parts.length === 4 && parts[2] === 'turn' && parts[3] === 'stream' && method === 'POST' && (req.headers.accept || '').toLowerCase().includes('text/event-stream')) {
    const sessionId = parts[1]
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }

    // Session pipeline streaming path — per-token streaming supported for all channels
    const earlyBody = await parseBody(req)
    if (runtime.preferredTurnEngine() === 'session-pipeline') {
      return await handleSseStream(runtime, logger, sendJSON, res, req, sessionId, async () => earlyBody)
    }

    if (!runtime.getPipeline()) {
      logger.error('SSE stream rejected: pipeline not ready')
      sendJSON(res, 503, { error: 'pipeline not ready' })
      return true
    }

    logger.info(`SSE stream request START: session=${sessionId.slice(0,8)}`)

    const body = earlyBody
    const content: string = body?.content
    const model: string = body?.model || 'unknown'
    if (!content) {
      logger.error('SSE stream rejected: missing content')
      sendJSON(res, 400, { error: 'missing content' })
      return true
    }

    logger.info(`SSE stream request: session=${sessionId.slice(0,8)}, model=${model}, content_length=${content.length}`)

    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    })

    let responseEnded = false
    let streamCompleted = false

    let paused = false
    let pausedSince = 0
    const BACKPRESSURE_TIMEOUT_MS = 5_000

    const onDrain = () => { paused = false; pausedSince = 0 }
    res.on('drain', onDrain)

    const sendEvent = (type: string, data: any) => {
      if (responseEnded || !res.writable) return
      if (paused) {
        if (pausedSince > 0 && Date.now() - pausedSince > BACKPRESSURE_TIMEOUT_MS) {
          logger.warn(`SSE session stream too slow, closing`, { sessionId: sessionId.slice(0, 8) })
          responseEnded = true
          try { res.end() } catch { /* already gone */ }
        }
        return
      }
      try {
        const ok = res.write(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`)
        if (!ok) {
          paused = true
          pausedSince = Date.now()
          logger.debug(`SSE session backpressure on ${type} event`)
        }
      } catch (err) {
        logger.debug(`SSE write failed, client may have disconnected: ${String(err)}`)
        responseEnded = true
      }
    }

    req.socket.setTimeout(5 * 60 * 1000)
    req.socket.on('timeout', () => {
      logger.warn(`SSE socket timeout: session=${sessionId.slice(0,8)}`)
      if (!streamCompleted) {
        sendEvent('error', { error: 'Request timeout' })
        res.end()
      }
    })

    const pingInterval = setInterval(() => {
      if (!responseEnded && res.writable) {
        try { res.write(': ping\n\n') } catch { clearInterval(pingInterval) }
      } else {
        clearInterval(pingInterval)
      }
    }, 15000)
    try { (pingInterval as any).unref?.() } catch {}

    const cleanup = () => {
      if (streamCompleted) return
      clearInterval(pingInterval)
      responseEnded = true
      streamCompleted = true
      logger.info(`SSE stream closed: session=${sessionId.slice(0,8)}`)
    }
    req.on('close', cleanup)
    res.on('close', cleanup)
    res.on('finish', () => {
      streamCompleted = true
      cleanup()
    })
    res.on('error', (err) => {
      logger.error(`SSE stream error: ${String(err)}`)
      streamCompleted = true
      cleanup()
    })

    try {
      const { randomUUID } = await import('node:crypto')
      const inbound = {
        id: randomUUID(),
        sessionId,
        channelId: body?.channelId || 'channel:cli',
        senderId: body?.senderId || sessionId,
        content,
        timestamp: new Date(),
      }

      // Build session config — only include fields that are explicitly provided
      // so undefined values don't override SessionManager defaults (e.g. systemPrompt)
      const session = runtime.getLegacySession({
        sessionId,
        channelId: inbound.channelId,
        senderId: inbound.senderId,
        model: body?.model,
        thinking: body?.thinking,
        systemPrompt: body?.systemPrompt,
      })

      let dialecticResult: any = null
      const dialecticEnabled = body?.dialectic !== false && runtime.getIntelligence()?.dialectic

      if (dialecticEnabled) {
        try {
          dialecticResult = await runtime.runLegacyDialectic({
            sessionId,
            turnId: inbound.id,
            content,
            sessionHistory: session.history,
            taskGuide: body?.taskGuide,
            dialecticMode: body?.dialecticMode,
          })

          if (dialecticResult.yang?.branches?.length > 0) {
            for (const branch of dialecticResult.yang.branches) {
              sendEvent('dialectic', {
                stage: 'yang',
                label: 'Thesis - Exploring possibilities',
                content: branch.argument || branch.content,
                confidence: branch.confidence,
              })
            }
          }

          if (dialecticResult.yin?.critiques?.length > 0) {
            for (const critique of dialecticResult.yin.critiques) {
              sendEvent('dialectic', {
                stage: 'yin',
                label: 'Antithesis - Critical analysis',
                content: critique.critique || critique.content,
                confidence: critique.confidence,
              })
            }
          }

          if (dialecticResult.serenity?.synthesis?.hasSignal) {
            sendEvent('dialectic', {
              stage: 'serenity',
              label: 'Synthesis - Unified conclusion',
              type: dialecticResult.serenity.synthesis.signal?.type,
              content: dialecticResult.serenity.synthesis.signal?.content,
              confidence: dialecticResult.serenity.synthesis.signal?.confidence,
            })
          }
        } catch (dialecticErr) {
          logger.warn(`dialectic error: ${String(dialecticErr)}`)
        }
      }

      let tokenCount = 0
      const onWorkerMessage = (ev: any) => {
        const payload = ev?.payload
        if (!payload || payload.sessionId !== sessionId) return

        if (payload.type === 'turn:token') {
          tokenCount++
          sendEvent('token', { token: payload.token })
        } else if (payload.type === 'turn:tool_call') {
          sendEvent('tool_call', { toolCallId: payload.toolCallId, tool: payload.tool, input: payload.input })
        } else if (payload.type === 'turn:tool_result') {
          sendEvent('tool_result', { toolCallId: payload.toolCallId, isError: payload.isError, content: payload.content })
        }
      }

      runtime.bus.on('worker:message', onWorkerMessage)

      // STREAMING FIX: Also attach a direct callback to the inbound message
      // so the pipeline can push events without going through the event bus.
      // This works around an issue where bus.emit() inside the session-lock
      // .then() chain doesn't always reach the listener in time.
      ;(inbound as any).onStreamEvent = (type: string, data: any) => {
        if (type === 'token') {
          tokenCount++
          sendEvent('token', data)
        } else if (type === 'thinking') {
          sendEvent('thinking', data)
        } else if (type === 'tool_call') {
          sendEvent('tool_call', data)
        } else if (type === 'tool_result') {
          sendEvent('tool_result', data)
        }
      }

      logger.info(`Calling pipeline.process for session ${sessionId.slice(0,8)}...`)

      try {
        const result = await runtime.getPipeline().process(inbound)

        logger.info(`SSE stream completed: ${tokenCount} tokens sent, response=${result?.response?.slice(0, 50)}...`)

        sendEvent('done', {
          model: result?.model,
          tokensUsed: result?.tokensUsed,
          durationMs: result?.durationMs,
          response: result?.response,
          toolCalls: result?.toolCalls,
          tool_outputs: result?.tool_outputs,
          dialectic: dialecticResult ? {
            signalInjected: dialecticResult.signalInjected,
          } : null,
        })

        res.end()
        streamCompleted = true
      } catch (pipelineErr) {
        logger.error(`pipeline processing error: ${String(pipelineErr)}`)

        if (!streamCompleted && !responseEnded) {
          sendEvent('error', {
            error: String(pipelineErr),
            type: 'pipeline_error'
          })
          res.end()
          streamCompleted = true
        }
      } finally {
        runtime.bus.off('worker:message', onWorkerMessage)
      }
    } catch (err) {
      logger.error(`stream turn error: ${String(err)}`)
      if (!streamCompleted && !responseEnded) {
        sendEvent('error', { error: String(err) })
        res.end()
        streamCompleted = true
      }
    }
    return true
  }

  // DELETE /sessions/:id
  if (parts.length === 2 && method === 'DELETE') {
    const sessionId = parts[1]
    runtime.getLegacySessionStore().delete(sessionId)
    sendJSON(res, 200, { ok: true, deleted: 1 })
    return true
  }

  // POST /sessions/prune
  if (parts.length === 2 && parts[1] === 'prune' && method === 'POST') {
    const body = await parseBody(req) as {
      all?: boolean
      olderThanDays?: number
      channelId?: string
      emptyOnly?: boolean
    } | null

    let deleted = 0

    if (body?.all) {
      deleted = runtime.getLegacySessionStore().pruneAll()
    } else if (body?.channelId) {
      deleted = runtime.getLegacySessionStore().pruneByChannelId(body.channelId)
    } else if (body?.emptyOnly) {
      deleted = runtime.getLegacySessionStore().pruneEmpty()
    } else if (typeof body?.olderThanDays === 'number') {
      deleted = runtime.getLegacySessionStore().pruneOlderThan(body.olderThanDays)
    } else {
      sendJSON(res, 400, {
        error: 'Provide one of: all, olderThanDays, channelId, emptyOnly',
      })
      return true
    }

    sendJSON(res, 200, { ok: true, deleted })
    return true
  }

  // GET /sessions/:id/messages — returns paginated message history
  // Used by webui BFF to populate Agno-compatible session runs.
  if (parts.length === 3 && parts[2] === 'messages' && method === 'GET') {
    const sessionId = parts[1]
    const session = runtime.getLegacySessionStore().get(sessionId)
    if (!session) {
      sendJSON(res, 404, { error: 'session not found' })
      return true
    }
    const url = new URL(req.url ?? '/', `http://localhost`)
    const limit = Math.min(parseInt(url.searchParams.get('limit') ?? '100', 10), 500)
    const history: Array<{ role: string; content: unknown }> = session.history ?? []
    const messages = history
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .slice(-limit)
    sendJSON(res, 200, { messages, total: history.length })
    return true
  }

  // GET /sessions/:id
  if (parts.length === 2 && method === 'GET') {
    const sessionId = parts[1]
    const session = runtime.getLegacySessionStore().get(sessionId)
    if (!session) {
      sendJSON(res, 404, { error: 'session not found' })
      return true
    }

    sendJSON(res, 200, {
      id: session.id,
      channelId: session.channelId,
      senderId: session.senderId,
      createdAt: session.createdAt,
      lastActiveAt: session.lastActiveAt,
      historyLength: session.history.length,
      tokenCount: session.tokenCount,
      config: session.config,
    })
    return true
  }

  // GET /sessions
  // Supports optional ?projectPath= filter so CLI clients (e.g. the Crush fork)
  // can scope the session list to the current working directory.
  if (parts.length === 1 && method === 'GET') {
    const url = new URL(req.url ?? '/', `http://localhost`)
    const projectPathFilter = url.searchParams.get('projectPath') ?? null

    let sessions = runtime.getLegacySessionStore().list()
      .map((s: any) => ({
        id: s.id,
        channelId: s.channelId,
        senderId: s.senderId,
        createdAt: s.createdAt,
        lastActiveAt: s.lastActiveAt,
        historyLength: s.history.length,
        tokenCount: s.tokenCount,
        projectPath: (s.config as any)?.projectPath ?? null,
        title: (s.config as any)?.title ?? null,
        firstMessage: getFirstUserMessage(s.history || []),
        lastMessage: getLastUserMessage(s.history || []),
      }))

    if (projectPathFilter) {
      sessions = sessions.filter((s: any) => s.projectPath === projectPathFilter)
    }

    sendJSON(res, 200, { sessions })
    return true
  }

  // POST /sessions (create a new session)
  // Creates a session with optional custom name/title and a permanent flag.
  // Returns the session ID for the client to use in subsequent requests.
  //
  // Body:
  //   name?:      string  — custom session title (default: "Untitled")
  //   channelId?: string  — channel identifier (default: "channel:webui")
  //   senderId?:  string  — sender identifier (default: "webui-user")
  //   permanent?: boolean — marks the session as non-ephemeral (to-be-implemented)
  //   config?:    object  — optional session config overrides
  //
  // Response:
  //   { ok, sessionId, name, channelId, senderId, permanent, createdAt }
  if (parts.length === 1 && method === 'POST') {
    const body = await parseBody(req)
    const { randomUUID } = await import('node:crypto')

    const name: string = body?.name ?? 'Untitled'
    const channelId: string = body?.channelId ?? 'channel:webui'
    const senderId: string = body?.senderId ?? 'webui-user'
    const permanent: boolean = body?.permanent ?? false
    const configOverrides: Record<string, unknown> = body?.config ?? {}

    // Generate a stable session ID: use provided ID or create a new one
    const sessionId: string = body?.sessionId ?? `webui-${randomUUID()}`

    try {
      const session = runtime.getLegacySessionStore().getOrCreateById(
        sessionId,
        channelId,
        senderId,
        { ...configOverrides, title: name, permanent } as any
      )

      // Store the title in session config for later retrieval
      if (session.config) {
        ;(session.config as any).title = name
        ;(session.config as any).permanent = permanent
      }

      logger.info(`Session created via API: ${sessionId.slice(0, 12)}`, {
        name,
        channelId,
        senderId,
        permanent,
      })

      sendJSON(res, 201, {
        ok: true,
        sessionId: session.id,
        name,
        channelId,
        senderId,
        permanent,
        createdAt: session.createdAt,
      })
      return true
    } catch (err) {
      logger.error(`session create error: ${String(err)}`)
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /sessions/:id/think
  // Injects external agent thinking/reasoning into the cognitive pipeline.
  // This is the manual fallback for agents that don't use OpenCode (whose
  // reasoning is captured automatically via DB polling).
  //
  // The thinking text is:
  //   1. Emitted as a turn:thinking event on the event bus
  //   2. Processed by ThoughtObserver → extractSignals()
  //   3. Routed via CognitiveBridge to linked sessions
  //   4. Returned immediately with extracted signals
  //
  // This runs within the free tool loop — the external agent calls this
  // alongside its normal tools at zero additional cost.
  if (parts.length === 3 && parts[2] === 'think' && method === 'POST') {
    const sessionId = parts[1]
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }

    const body = await parseBody(req)
    const text: string = body?.text
    if (!text || typeof text !== 'string' || text.trim().length < 10) {
      sendJSON(res, 400, { error: 'missing or too short text (min 10 chars)' })
      return true
    }

    const projectPath: string | undefined = body?.projectPath

    try {
      // Emit thinking chunk on the event bus — ThoughtObserver will pick it up
      if (runtime.bus) {
        runtime.bus.emit({
          type: 'worker:message',
          pluginId: `session:${sessionId}`,
          payload: {
            type: 'turn:thinking',
            sessionId,
            token: text.trim(),
          },
        } as any)
      }

      // Extract signals synchronously for immediate return
      const thoughtObserver = runtime.getIntelligence()?.thoughtObserver
      const signals = thoughtObserver?.extractSignalsFromText?.(text.trim()) ?? []
      await thoughtObserver?.storeSignals?.(sessionId, signals)

      logger.info(`Think stream injected`, {
        sessionId: sessionId.slice(0, 12),
        textLength: text.length,
        signalsExtracted: signals.length,
        kinds: signals.map((s: any) => s.kind).join(', ') || '(none)',
      })

      sendJSON(res, 200, {
        ok: true,
        sessionId,
        signalsExtracted: signals.length,
        signals: signals.map((s: any) => ({
          kind: s.kind,
          text: s.text,
          confidence: s.confidence,
        })),
      })
      return true
    } catch (err) {
      logger.error('Think stream failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /sessions/:id/inject
  // Queues content for mid-loop injection into the active tool loop.
  // The content will appear as a <system-reminder> in the next tool result.
  // This is the HTTP entry point for any client (cassi-tui, web UI, external
  // agents) to send mid-turn messages or steering instructions.
  if (parts.length === 3 && parts[2] === 'inject' && method === 'POST') {
    const sessionId = parts[1]
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }

    const body = await parseBody(req)
    const content: string = body?.content
    if (!content || typeof content !== 'string') {
      sendJSON(res, 400, { error: 'content is required (string)' })
      return true
    }

    const source: string = body?.source || 'api'

    try {
      runtime.bus.emit({
        type: 'user:mid-turn-message',
        sessionId,
        content,
        source,
        timestamp: new Date(),
      })

      logger.info(`Mid-loop injection queued via API`, {
        sessionId: sessionId.slice(0, 12),
        source,
        chars: content.length,
      })

      sendJSON(res, 200, {
        ok: true,
        sessionId,
        queued: true,
        charCount: content.length,
      })
      return true
    } catch (err) {
      logger.error('Mid-loop injection failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /sessions/:id/command
  // Routes a slash command string (e.g. "/think about X") through CassiCore's
  // universal command processor. This is the HTTP entry point for external CLI
  // clients (e.g. the web UI, CassiTUI) that cannot send worker-thread messages directly.
  if (parts.length === 3 && parts[2] === 'command' && method === 'POST') {
    const sessionId = parts[1]
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }

    const body = await parseBody(req)
    const command: string = body?.command
    if (!command || typeof command !== 'string') {
      sendJSON(res, 400, { error: 'missing command string' })
      return true
    }

    try {
      // Import processor directly — CommandDispatcher.handle() sends via EventBus
      // which doesn't return the result. We need the return value for HTTP.
      const { processor } = await import('../../commands/universal-processor.js')
      if (!processor || typeof processor.process !== 'function') {
        sendJSON(res, 503, { error: 'command processor not available' })
        return true
      }

      const session = runtime.getLegacySessionStore().get(sessionId)
      const intelligence = runtime.getIntelligence()
      const ctx = {
        channel: 'api' as const,
        userId: session?.senderId ?? 'webui-user',
        sessionId,
        projectPath: (session?.config as any)?.projectPath ?? undefined,
        permissions: ['read', 'write', 'admin', 'intelligence', '*'],
        intelligence: intelligence ? {
          memory: intelligence.memory,
          thinker: intelligence.thinker,
          dialectic: intelligence.dialectic,
          contextManager: intelligence.contextManager,
        } : undefined,
      }

      const result = await processor.process(command, ctx)
      if (!result) {
        sendJSON(res, 404, { error: 'unknown command', command })
        return true
      }

      sendJSON(res, 200, { ok: true, text: result.text, actions: result.actions ?? null })
      return true
    } catch (err) {
      logger.error(`command error: ${String(err)}`, { sessionId, command })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}

/**
 * Handle SSE streaming for session pipeline
 * @dep callers: handleSessionsRoutes (core/admin-api/sessions.ts)
 * @dep calls: end, on, off, sendJSON, parseBody [+4]
 * @dep flows: HandleSessionsRoutes → Now (2/4), HandleSessionsRoutes → End (2/4), HandleSessionsRoutes → ResolveSessionPipelineSessionId (2/4) [+1]
 * @dep module: Admin-api
 * @dep risk: MEDIUM | 1 caller, 4 flows, 1 module
 */
async function handleSseStream(
  runtime: AdminRuntimeFacade,
  logger: ILogger,
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void,
  res: http.ServerResponse,
  req: http.IncomingMessage,
  sessionId: string,
  parseBody: (req: http.IncomingMessage) => Promise<any>
): Promise<boolean> {
  logger.info(`SSE stream request START: session=${sessionId.slice(0, 8)}`)

  const body = await parseBody(req)
  const content: string = body?.content
  const model: string = body?.model || 'unknown'
  if (!content) {
    logger.error('SSE stream rejected: missing content')
    sendJSON(res, 400, { error: 'missing content' })
    return true
  }

  logger.info(`SSE stream request: session=${sessionId.slice(0, 8)}, model=${model}, content_length=${content.length}`)

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'X-Accel-Buffering': 'no',
  })

  let responseEnded = false
  let streamCompleted = false

  let paused = false
  let pausedSince = 0
  const BACKPRESSURE_TIMEOUT_MS = 5_000

  const onDrain = () => { paused = false; pausedSince = 0 }
  res.on('drain', onDrain)

  const sendEvent = (type: string, data: any) => {
    if (responseEnded || !res.writable) return
    if (paused) {
      if (pausedSince > 0 && Date.now() - pausedSince > BACKPRESSURE_TIMEOUT_MS) {
        logger.warn(`SSE session stream too slow, closing`, { sessionId: sessionId.slice(0, 8) })
        responseEnded = true
        try { res.end() } catch { /* already gone */ }
      }
      return
    }
    try {
      const ok = res.write(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`)
      if (!ok) {
        paused = true
        pausedSince = Date.now()
        logger.debug(`SSE session backpressure on ${type} event`)
      }
    } catch (err) {
      logger.debug(`SSE write failed, client may have disconnected: ${String(err)}`)
      responseEnded = true
    }
  }

  req.socket.setTimeout(5 * 60 * 1000)
  req.socket.on('timeout', () => {
    logger.warn(`SSE socket timeout: session=${sessionId.slice(0, 8)}`)
    if (!streamCompleted) {
      sendEvent('error', { error: 'Request timeout' })
      res.end()
    }
  })

  const pingInterval = setInterval(() => {
    if (!responseEnded && res.writable) {
      try { res.write(': ping\n\n') } catch { clearInterval(pingInterval) }
    } else {
      clearInterval(pingInterval)
    }
  }, 15000)
  try { (pingInterval as any).unref?.() } catch { }

  const cleanup = () => {
    if (streamCompleted) return
    clearInterval(pingInterval)
    responseEnded = true
    streamCompleted = true
    logger.info(`SSE stream closed: session=${sessionId.slice(0, 8)}`)
  }
  req.on('close', cleanup)
  res.on('close', cleanup)
  res.on('finish', () => {
    streamCompleted = true
    cleanup()
  })
  res.on('error', (err) => {
    logger.error(`SSE stream error: ${String(err)}`)
    streamCompleted = true
    cleanup()
  })

  try {
    const channelId = body?.channelId || 'channel:cli'
    const senderId = body?.senderId || sessionId

    // The session pipeline generates internal IDs as a deterministic hash of
    // channelId:senderId. We need this to filter streaming events correctly,
    // since the URL sessionId parameter may differ from the internal ID.
    const internalSessionId = runtime.resolveStreamSessionId(sessionId, channelId, senderId)

    // Set up event listener BEFORE calling processMessage to avoid race conditions
    let tokenCount = 0
    let finalResponse = ''
    let tokensUsed = 0
    let durationMs = 0

    const onWorkerMessage = (ev: any) => {
      const payload = ev?.payload
      if (!payload || payload.sessionId !== internalSessionId) return

      if (payload.type === 'turn:token') {
        tokenCount++
        finalResponse += String(payload.token || '')
        sendEvent('token', { token: payload.token })
      } else if (payload.type === 'turn:thinking') {
        sendEvent('thinking', { token: payload.token })
      } else if (payload.type === 'turn:done') {
        tokensUsed = Number(payload.tokensUsed || 0)
        durationMs = Number(payload.durationMs || 0)
      } else if (payload.type === 'turn:tool_call') {
        sendEvent('tool_call', { toolCallId: payload.toolCallId, tool: payload.tool, input: payload.input })
      } else if (payload.type === 'turn:tool_result') {
        sendEvent('tool_result', { toolCallId: payload.toolCallId, isError: payload.isError, content: payload.content })
      }
    }

    runtime.bus.on('worker:message', onWorkerMessage)

    try {
      const result = await runtime.executeTurn({
        requestedSessionId: sessionId,
        channelId,
        senderId,
        content,
        attachments: body?.attachments,
        stream: true,
        model,
      })

      logger.info(`SSE stream completed: ${tokenCount} tokens, response=${result?.response?.slice(0, 50)}...`)

      sendEvent('done', {
        engine: result.engine,
        requestedSessionId: sessionId,
        sessionId: result.sessionId,
        model: result.model ?? model,
        tokensUsed: tokensUsed || result.tokensUsed || 0,
        durationMs: durationMs || result.durationMs || 0,
        response: result.response,
      })

      res.end()
      streamCompleted = true
    } catch (processErr) {
      logger.error(`processMessage error: ${String(processErr)}`)

      if (!streamCompleted && !responseEnded) {
        sendEvent('error', {
          error: String(processErr),
          type: 'processing_error'
        })
        res.end()
        streamCompleted = true
      }
    } finally {
      runtime.bus.off('worker:message', onWorkerMessage)
    }
  } catch (err) {
    logger.error(`Stream turn error: ${String(err)}`)
    if (!streamCompleted && !responseEnded) {
      sendEvent('error', { error: String(err) })
      res.end()
      streamCompleted = true
    }
  }

  return true
}
