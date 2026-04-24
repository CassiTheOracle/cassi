import { getModelSpec } from '../config/system-settings.js'

import type { AdminRuntimeFacade } from './runtime.js'

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface ChatRoutesDeps {
  runtime: AdminRuntimeFacade
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  parts: string[]
}

/**
 * @dep callers: admin-turn-routing.test.ts (tests/admin-turn-routing.test.ts), handler (core/admin-api.ts)
 * @dep calls: on, emit, off, sendJSON, parseBody [+4]
 * @dep module: Admin-api
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export async function handleChatRoutes(
  deps: ChatRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string
): Promise<boolean> {
  const { runtime, logger, sendJSON, parseBody, parts } = deps

  if (parts[0] !== 'chat') return false

  if (parts.length === 3 && parts[2] === 'stream' && method === 'GET') {
    const sessionId = parts[1]
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }

    const channelId = 'channel:cli'
    const senderId = sessionId
    const streamSessionId = runtime.resolveStreamSessionId(sessionId, channelId, senderId)

    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
    })
    res.write(': connected\n\n')

    const busHandler = (e: any) => {
      if (e.pluginId !== `session:${streamSessionId}`) return
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
          res.write(`data: ${JSON.stringify({ type: 'tool_call', toolCallId: payload.toolCallId, tool: payload.tool, input: payload.input })}\n\n`)
        } catch {}
      } else if (payload?.type === 'turn:tool_result') {
        try {
          res.write(`data: ${JSON.stringify({ type: 'tool_result', toolCallId: payload.toolCallId, tool: payload.tool, isError: payload.isError, content: payload.content })}\n\n`)
        } catch {}
      } else if (payload?.type === 'turn:error') {
        try {
          res.write(`data: ${JSON.stringify({ type: 'error', error: payload.error })}\n\n`)
        } catch {}
      }
    }

    runtime.bus.on('worker:message', busHandler)

    const ping = setInterval(() => {
      try { res.write(': ping\n\n') } catch { clearInterval(ping) }
    }, 15000)
    try { (ping as any).unref?.() } catch {}

    req.on('close', () => {
      clearInterval(ping)
      runtime.bus.off('worker:message', busHandler)
    })

    return true
  }

  if (parts.length === 3 && parts[2] === 'send' && method === 'POST') {
    const sessionId = parts[1]
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }

    const engine = runtime.preferredTurnEngine()
    if (!engine) {
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
      void runtime.executeTurn({
        requestedSessionId: sessionId,
        channelId: 'channel:cli',
        senderId: sessionId,
        content,
      }).then((result) => {
        runtime.bus.emit({ type: 'turn:end', sessionId: result.sessionId, response: result.response, durationMs: result.durationMs ?? 0 })
      }).catch((err: any) => {
        runtime.logger?.error?.(`pipeline error: ${String(err)}`)
      })

      sendJSON(res, 200, { ok: true, sessionId, engine })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  if (parts.length === 3 && parts[2] === 'cancel' && method === 'POST') {
    const sessionId = parts[1]
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }
    const engine = runtime.preferredTurnEngine()
    if (!engine) {
      sendJSON(res, 503, { error: 'pipeline not ready' })
      return true
    }

    try {
      const cancellation = runtime.cancelTurn(sessionId)
      if (!cancellation.supported) {
        const statusCode = cancellation.engine === 'session-pipeline' ? 409 : 503
        sendJSON(res, statusCode, {
          ok: false,
          cancelled: false,
          engine: cancellation.engine,
          error: cancellation.active
            ? 'active turn is running on the session pipeline and cannot be cancelled yet'
            : 'turn cancellation is not supported by the active engine',
        })
      } else if (cancellation.cancelled) {
        sendJSON(res, 200, { ok: true, cancelled: true, engine: cancellation.engine })
      } else {
        sendJSON(res, 404, {
          ok: false,
          cancelled: false,
          engine: cancellation.engine,
          error: 'no active turn or not cancellable',
        })
      }
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  if (parts.length === 1 && method === 'POST') {
    const body = await parseBody(req)
    const messages = body?.messages || []
    const model = body?.model || getModelSpec('main')

    try {
      const { randomUUID } = await import('node:crypto')
      const sessionId = `provider-${  randomUUID()}`
      const content = messages[messages.length - 1]?.content || ''

      if (!runtime.preferredTurnEngine()) {
        sendJSON(res, 503, { error: 'pipeline not ready' })
        return true
      }

      logger.info(`Processing provider chat for session ${sessionId}`)
      const result = await runtime.executeTurn({
        requestedSessionId: sessionId,
        channelId: 'channel:cli',
        senderId: sessionId,
        content,
        model,
      })

      sendJSON(res, 200, {
        sessionId: result.sessionId,
        requestedSessionId: sessionId,
        engine: result.engine,
        content: result.response,
        model: result.model ?? model,
        tokensUsed: result.tokensUsed ?? 0,
        durationMs: result.durationMs ?? 0,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
