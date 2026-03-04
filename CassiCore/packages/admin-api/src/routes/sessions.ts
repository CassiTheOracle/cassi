import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'

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

      const useV2 = (daemon as any).useV2 && (daemon as any).v2

      if (useV2) {
        logger.info(`[admin-api] Using V2 for turn`, { sessionId: sessionId.slice(0, 8) })
        const startTime = Date.now()
        const result = await (daemon as any).v2.processMessage(channelId, senderId, content)
        const durationMs = Date.now() - startTime

        sendJSON(res, 200, {
          ok: true,
          sessionId: result.sessionId,
          response: result.response,
          model: 'v2',
          tokensUsed: 0,
          durationMs,
          v2: true,
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

      const session = daemon.sessions.getOrCreateById(
        sessionId,
        inbound.channelId,
        inbound.senderId,
        {
          model: body?.model || daemon.config?.get?.('session.model', 'kimi-coding/k2p5'),
          thinking: body?.thinking || daemon.config?.get?.('session.thinking', 'high'),
          systemPrompt: body?.systemPrompt,
        }
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
          logger.warn(`[admin-api] dialectic error: ${String(dialecticErr)}`)
        }
      }

      let result: any
      try {
        result = await daemon.pipeline.process(inbound)
      } catch (pipelineErr) {
        logger.error(`[admin-api] pipeline.process failed: ${String(pipelineErr)}`)
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
      logger.error(`[admin-api] turn error: ${String(err)}`)
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

    const useV2 = (daemon as any).useV2 && (daemon as any).v2
    if (useV2) {
      // V2 SSE streaming path
      return await handleV2SseStream(daemon, logger, sendJSON, res, req, sessionId, parseBody)
    }

    if (!daemon.pipeline) {
      logger.error('[admin-api] SSE stream rejected: pipeline not ready')
      sendJSON(res, 503, { error: 'pipeline not ready' })
      return true
    }

    logger.info(`[admin-api] SSE stream request START: session=${sessionId.slice(0,8)}`)

    const body = await parseBody(req)
    const content: string = body?.content
    const model: string = body?.model || 'unknown'
    if (!content) {
      logger.error('[admin-api] SSE stream rejected: missing content')
      sendJSON(res, 400, { error: 'missing content' })
      return true
    }

    logger.info(`[admin-api] SSE stream request: session=${sessionId.slice(0,8)}, model=${model}, content_length=${content.length}`)

    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    })

    let responseEnded = false
    let streamCompleted = false

    const sendEvent = (type: string, data: any) => {
      if (responseEnded || !res.writable) return
      try {
        const written = res.write(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`)
        if (!written) {
          logger.debug(`[admin-api] SSE backpressure on ${type} event`)
        }
      } catch (err) {
        logger.debug(`[admin-api] SSE write failed, client may have disconnected: ${String(err)}`)
        responseEnded = true
      }
    }

    req.socket.setTimeout(5 * 60 * 1000)
    req.socket.on('timeout', () => {
      logger.warn(`[admin-api] SSE socket timeout: session=${sessionId.slice(0,8)}`)
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
      logger.info(`[admin-api] SSE stream closed: session=${sessionId.slice(0,8)}`)
    }
    req.on('close', cleanup)
    res.on('close', cleanup)
    res.on('finish', () => {
      streamCompleted = true
      cleanup()
    })
    res.on('error', (err) => {
      logger.error(`[admin-api] SSE stream error: ${String(err)}`)
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

      const session = daemon.sessions.getOrCreateById(
        sessionId,
        inbound.channelId,
        inbound.senderId,
        {
          model: body?.model || daemon.config?.get?.('session.model', 'kimi-coding/k2p5'),
          thinking: body?.thinking || daemon.config?.get?.('session.thinking', 'high'),
          systemPrompt: body?.systemPrompt,
        }
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
          logger.warn(`[admin-api] dialectic error: ${String(dialecticErr)}`)
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
          sendEvent('tool_call', { tool: payload.tool, input: payload.input })
        } else if (payload.type === 'turn:tool_result') {
          sendEvent('tool_result', { toolCallId: payload.toolCallId, isError: payload.isError })
        }
      }

      daemon.bus.on('worker:message', onWorkerMessage)

      logger.info(`[admin-api] Calling pipeline.process for session ${sessionId.slice(0,8)}...`)

      try {
        const result = await daemon.pipeline.process(inbound)

        logger.info(`[admin-api] SSE stream completed: ${tokenCount} tokens sent, response=${result?.response?.slice(0, 50)}...`)

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
        logger.error(`[admin-api] pipeline processing error: ${String(pipelineErr)}`)

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
      logger.error(`[admin-api] stream turn error: ${String(err)}`)
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
      logger.error(`[admin-api] command error: ${String(err)}`, { sessionId, command })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}

/**
 * Handle SSE streaming for V2 session flow
 */
async function handleV2SseStream(
  daemon: any,
  logger: ILogger,
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void,
  res: http.ServerResponse,
  req: http.IncomingMessage,
  sessionId: string,
  parseBody: (req: http.IncomingMessage) => Promise<any>
): Promise<boolean> {
  logger.info(`[admin-api] V2 SSE stream request START: session=${sessionId.slice(0, 8)}`)

  const body = await parseBody(req)
  const content: string = body?.content
  const model: string = body?.model || 'unknown'
  if (!content) {
    logger.error('[admin-api] V2 SSE stream rejected: missing content')
    sendJSON(res, 400, { error: 'missing content' })
    return true
  }

  logger.info(`[admin-api] V2 SSE stream request: session=${sessionId.slice(0, 8)}, model=${model}, content_length=${content.length}`)

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'X-Accel-Buffering': 'no',
  })

  let responseEnded = false
  let streamCompleted = false

  const sendEvent = (type: string, data: any) => {
    if (responseEnded || !res.writable) return
    try {
      const written = res.write(`event: ${type}\ndata: ${JSON.stringify(data)}\n\n`)
      if (!written) {
        logger.debug(`[admin-api] V2 SSE backpressure on ${type} event`)
      }
    } catch (err) {
      logger.debug(`[admin-api] V2 SSE write failed, client may have disconnected: ${String(err)}`)
      responseEnded = true
    }
  }

  req.socket.setTimeout(5 * 60 * 1000)
  req.socket.on('timeout', () => {
    logger.warn(`[admin-api] V2 SSE socket timeout: session=${sessionId.slice(0, 8)}`)
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
    logger.info(`[admin-api] V2 SSE stream closed: session=${sessionId.slice(0, 8)}`)
  }
  req.on('close', cleanup)
  res.on('close', cleanup)
  res.on('finish', () => {
    streamCompleted = true
    cleanup()
  })
  res.on('error', (err) => {
    logger.error(`[admin-api] V2 SSE stream error: ${String(err)}`)
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
      } else if (payload.type === 'turn:done') {
        tokensUsed = Number(payload.tokensUsed || 0)
        durationMs = Number(payload.durationMs || 0)
      } else if (payload.type === 'turn:tool_call') {
        sendEvent('tool_call', { tool: payload.tool, input: payload.input })
      } else if (payload.type === 'turn:tool_result') {
        sendEvent('tool_result', { toolCallId: payload.toolCallId, isError: payload.isError })
      }
    }

    daemon.bus.on('worker:message', onWorkerMessage)

    try {
      // Call V2 processMessage with streaming enabled
      const result = await daemon.v2.processMessage(channelId, senderId, content, {
        attachments: body?.attachments,
        stream: true
      })

      logger.info(`[admin-api] V2 SSE stream completed: ${tokenCount} tokens, response=${result?.response?.slice(0, 50)}...`)

      sendEvent('done', {
        model: 'v2',
        tokensUsed: tokensUsed || result.tokensUsed || 0,
        durationMs: durationMs || result.durationMs || 0,
        response: result.response,
        v2: true
      })

      res.end()
      streamCompleted = true
    } catch (processErr) {
      logger.error(`[admin-api] V2 processMessage error: ${String(processErr)}`)

      if (!streamCompleted && !responseEnded) {
        sendEvent('error', {
          error: String(processErr),
          type: 'v2_processing_error'
        })
        res.end()
        streamCompleted = true
      }
    } finally {
      daemon.bus.off('worker:message', onWorkerMessage)
    }
  } catch (err) {
    logger.error(`[admin-api] V2 stream turn error: ${String(err)}`)
    if (!streamCompleted && !responseEnded) {
      sendEvent('error', { error: String(err) })
      res.end()
      streamCompleted = true
    }
  }

  return true
}
