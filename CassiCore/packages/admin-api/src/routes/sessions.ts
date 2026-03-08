import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface SessionsRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  getFirstUserMessage: (history: any[]) => string
  getLastUserMessage: (history: any[]) => string
  tcpHost: string
  currentTcpPort: number
}

export async function handleSessionsRoutes(
  deps: SessionsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string,
  parts: string[]
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, getFirstUserMessage, getLastUserMessage } = deps

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

      if ((daemon as any).sessionPipeline) {
        logger.info(`Processing turn`, { sessionId: sessionId.slice(0, 8) })
        const startTime = Date.now()
        const result = await (daemon as any).sessionPipeline.processMessage(channelId, senderId, content)
        const durationMs = Date.now() - startTime

        sendJSON(res, 200, {
          ok: true,
          sessionId: result.sessionId,
          response: result.response,
          model: result.model ?? 'unknown',
          tokensUsed: result.tokensUsed ?? 0,
          durationMs,
        })
        return true
      }

      if (!daemon.pipeline) {
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
      const sessionCfg: Record<string, unknown> = {
        model: body?.model || daemon.config?.get?.('session.model', 'kimi-coding/k2p5'),
        thinking: body?.thinking || daemon.config?.get?.('session.thinking', 'high'),
      }
      if (body?.systemPrompt) sessionCfg.systemPrompt = body.systemPrompt

      const session = daemon.sessions.getOrCreateById(
        sessionId,
        inbound.channelId,
        inbound.senderId,
        sessionCfg as any,
      )

      let dialecticResult: any = null
      const dialecticEnabled = body?.dialectic !== false && daemon.intelligence?.dialectic

      if (dialecticEnabled) {
        try {
          const dialectic = daemon.intelligence.dialectic
          const context = {
            recentMemories: [],
            availableTools: Object.keys(daemon.toolRegistry?.getAll?.() || {}),
            sessionHistory: session.history,
            taskGuide: body?.taskGuide || `Process user message: ${content.slice(0, 100)}...`,
          }

          dialecticResult = await dialectic.processTurn(
            sessionId,
            inbound.id,
            content,
            context,
            { mode: body?.dialecticMode || 'parallel' }
          )
        } catch (dialecticErr) {
          logger.warn(`dialectic error: ${String(dialecticErr)}`)
        }
      }

      let result: any
      try {
        result = await daemon.pipeline.process(inbound)
      } catch (pipelineErr) {
        logger.error(`pipeline.process failed: ${String(pipelineErr)}`)
        throw pipelineErr
      }

      const response: any = {
        ok: true,
        sessionId,
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
    const hasPipeline = !!(daemon as any).sessionPipeline
    if (hasPipeline) {
      return await handleSseStream(daemon, logger, sendJSON, res, req, sessionId, async () => earlyBody)
    }

    if (!daemon.pipeline) {
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

    // ── Backpressure state ──────────────────────────────────────────────
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
      const sessionCfg: Record<string, unknown> = {
        model: body?.model || daemon.config?.get?.('session.model', 'kimi-coding/k2p5'),
        thinking: body?.thinking || daemon.config?.get?.('session.thinking', 'high'),
      }
      if (body?.systemPrompt) sessionCfg.systemPrompt = body.systemPrompt

      const session = daemon.sessions.getOrCreateById(
        sessionId,
        inbound.channelId,
        inbound.senderId,
        sessionCfg as any,
      )

      let dialecticResult: any = null
      const dialecticEnabled = body?.dialectic !== false && daemon.intelligence?.dialectic

      if (dialecticEnabled) {
        try {
          const dialectic = daemon.intelligence.dialectic
          const context = {
            recentMemories: [],
            availableTools: Object.keys(daemon.toolRegistry?.getAll?.() || {}),
            sessionHistory: session.history,
            taskGuide: body?.taskGuide || `Process user message: ${content.slice(0, 100)}...`,
          }

          dialecticResult = await dialectic.processTurn(
            sessionId,
            inbound.id,
            content,
            context,
            { mode: body?.dialecticMode || 'parallel' }
          )

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

      daemon.bus.on('worker:message', onWorkerMessage)

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
        const result = await daemon.pipeline.process(inbound)

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
        daemon.bus.off('worker:message', onWorkerMessage)
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
    daemon.sessions.delete(sessionId)
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
      deleted = daemon.sessions.pruneAll()
    } else if (body?.channelId) {
      deleted = daemon.sessions.pruneByChannelId(body.channelId)
    } else if (body?.emptyOnly) {
      deleted = daemon.sessions.pruneEmpty()
    } else if (typeof body?.olderThanDays === 'number') {
      deleted = daemon.sessions.pruneOlderThan(body.olderThanDays)
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
    const session = daemon.sessions.get(sessionId)
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
    const session = daemon.sessions.get(sessionId)
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

    let sessions = daemon.sessions.list()
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
      if (daemon.bus) {
        daemon.bus.emit({
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
      const thoughtObserver = daemon.intelligence?.thoughtObserver
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

  // POST /sessions/:id/command
  // Routes a slash command string (e.g. "/think about X") through CassiCore's
  // universal command processor. This is the HTTP entry point for external CLI
  // clients (e.g. the Crush fork) that cannot send worker-thread messages directly.
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
      const commandProcessor = (daemon as any).commandProcessor
      if (!commandProcessor || typeof commandProcessor.process !== 'function') {
        sendJSON(res, 503, { error: 'command processor not available' })
        return true
      }

      const session = daemon.sessions.get(sessionId)
      const ctx = {
        channel: 'api' as const,
        userId: session?.senderId ?? sessionId,
        sessionId,
        projectPath: (session?.config as any)?.projectPath ?? undefined,
        permissions: ['*'],
        intelligence: daemon.intelligence ?? undefined,
      }

      const result = await commandProcessor.process(command, ctx)
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
 */
async function handleSseStream(
  daemon: any,
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

  // ── Backpressure state ────────────────────────────────────────────────
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

    // Set up event listener BEFORE calling processMessage to avoid race conditions
    let tokenCount = 0
    let finalResponse = ''
    let tokensUsed = 0
    let durationMs = 0

    const onWorkerMessage = (ev: any) => {
      const payload = ev?.payload
      if (!payload || payload.sessionId !== sessionId) return

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

    daemon.bus.on('worker:message', onWorkerMessage)

    try {
      const result = await daemon.sessionPipeline.processMessage(channelId, senderId, content, {
        attachments: body?.attachments,
        stream: true,
        model: model !== 'unknown' ? model : undefined,
      })

      logger.info(`SSE stream completed: ${tokenCount} tokens, response=${result?.response?.slice(0, 50)}...`)

      sendEvent('done', {
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
      daemon.bus.off('worker:message', onWorkerMessage)
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
