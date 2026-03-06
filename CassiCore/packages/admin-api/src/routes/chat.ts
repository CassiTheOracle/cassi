import { getModelSpec } from '../config/system-settings.js'

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface ChatRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  parts: string[]
}

export async function handleChatRoutes(
  deps: ChatRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, parts } = deps

  if (parts[0] !== 'chat') return false

  // GET /chat/:sessionId/stream
  if (parts.length === 3 && parts[2] === 'stream' && method === 'GET') {
    const sessionId = parts[1]
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }

    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
    })
    res.write(': connected\n\n')

    const busHandler = (e: any) => {
      if (e.pluginId !== `session:${sessionId}`) return
      const payload = e.payload as Record<string, unknown>
      if (payload?.type === 'turn:token') {
        try {
          res.write(`data: ${JSON.stringify({ type: 'token', token: payload.token })}\n\n`)
        } catch {}
      } else if (payload?.type === 'turn:done') {
        try {
          res.write(`data: ${JSON.stringify({ type: 'done' })}\n\n`)
        } catch {}
      } else if (payload?.type === 'turn:tool_call') {
        try {
          res.write(`data: ${JSON.stringify({ type: 'tool_call', tool: payload.tool, input: payload.input })}\n\n`)
        } catch {}
      } else if (payload?.type === 'turn:error') {
        try {
          res.write(`data: ${JSON.stringify({ type: 'error', error: payload.error })}\n\n`)
        } catch {}
      }
    }

    daemon.bus.on('worker:message', busHandler)

    const ping = setInterval(() => {
      try { res.write(': ping\n\n') } catch { clearInterval(ping) }
    }, 15000)
    try { (ping as any).unref?.() } catch {}

    req.on('close', () => {
      clearInterval(ping)
      daemon.bus.off('worker:message', busHandler)
    })

    return true
  }

  // POST /chat/:sessionId/send
  if (parts.length === 3 && parts[2] === 'send' && method === 'POST') {
    const sessionId = parts[1]
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }

    if (!daemon.pipeline) {
      sendJSON(res, 503, { error: 'pipeline not ready' })
      return true
    }

    const body = await parseBody(req)
    const content: string = body?.content
    if (!content) {
      sendJSON(res, 400, { error: 'missing content' })
      return true
    }

    try {
      const { randomUUID } = await import('node:crypto')
      const inbound = {
        id: randomUUID(),
        sessionId,
        channelId: 'channel:cli',
        senderId: sessionId,
        content,
        timestamp: new Date(),
      }

      void daemon.pipeline.process(inbound).then((result: any) => {
        daemon.bus.emit({ type: 'turn:end', sessionId: inbound.sessionId, response: result.response, durationMs: result.durationMs })
      }).catch((err: any) => {
        daemon.logger?.error?.(`pipeline error: ${String(err)}`)
      })

      sendJSON(res, 200, { ok: true, sessionId })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /chat/:sessionId/cancel
  if (parts.length === 3 && parts[2] === 'cancel' && method === 'POST') {
    const sessionId = parts[1]
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }
    if (!daemon.pipeline) {
      sendJSON(res, 503, { error: 'pipeline not ready' })
      return true
    }
    try {
      const ok = typeof (daemon.pipeline as any).requestCancel === 'function'
        ? (daemon.pipeline as any).requestCancel(sessionId)
        : false
      if (ok) {
        sendJSON(res, 200, { ok: true, cancelled: true })
      } else {
        sendJSON(res, 404, { ok: false, error: 'no active turn or not cancellable' })
      }
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /chat
  if (parts.length === 1 && method === 'POST') {
    const body = await parseBody(req)
    const messages = body?.messages || []
    const model = body?.model || getModelSpec('main')

    try {
      const { randomUUID } = await import('node:crypto')
      const sessionId = `provider-${  randomUUID()}`
      const content = messages[messages.length - 1]?.content || ''

      const useSessionPipeline = !!(daemon as any).sessionPipeline

      if (useSessionPipeline) {
        logger.info(`Chat for session ${sessionId}`)
        const startTime = Date.now()
        const result = await (daemon as any).sessionPipeline.processMessage(
          'channel:cli',
          sessionId,
          content
        )
        const durationMs = Date.now() - startTime

        sendJSON(res, 200, {
          content: result.response,
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

      const inbound = {
        id: randomUUID(),
        sessionId,
        channelId: 'channel:cli',
        senderId: sessionId,
        content,
        timestamp: new Date(),
      }

      logger.info(`Processing provider chat for session ${sessionId}`)

      let responseContent = ''
      let responseModel = model
      let tokensUsed = 0
      let durationMs = 0

      const busHandler = (e: any) => {
        if (e.pluginId !== `session:${sessionId}`) return
        const payload = e.payload as Record<string, unknown>
        if (payload?.type === 'turn:token') {
          responseContent += String(payload.token || '')
        } else if (payload?.type === 'turn:done') {
          responseModel = String(payload.model || model)
          tokensUsed = Number(payload.tokensUsed || 0)
          durationMs = Number(payload.durationMs || 0)
        }
      }

      daemon.bus.on('worker:message', busHandler)

      try {
        await daemon.pipeline.process(inbound)
        await new Promise(resolve => setTimeout(resolve, 500))
      } finally {
        daemon.bus.off('worker:message', busHandler)
      }

      sendJSON(res, 200, {
        content: responseContent,
        model: responseModel,
        tokensUsed,
        durationMs
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
