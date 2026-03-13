import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface DebugRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  pathname: string
  sseConnections: Map<string, { res: http.ServerResponse; sessionId: string; connectedAt: number }>
  sseConnectionId: { value: number }
}

export async function handleDebugRoutes(
  deps: DebugRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, sendJSON, parseBody, url, pathname, sseConnections, sseConnectionId } = deps

  // GET /debug/context-window
  if (method === 'GET' && pathname === '/debug/context-window') {
    const sessionId = url.searchParams.get('sessionId')
    if (!sessionId) {
      sendJSON(res, 400, { error: 'sessionId required' })
      return true
    }

    try {
      const { getContextWindowDebugger } = await import('../events/index.js')
      const ctxDebugger = getContextWindowDebugger()

      if (!ctxDebugger) {
        sendJSON(res, 503, { error: 'Context window debugging not enabled' })
        return true
      }

      const snapshot = ctxDebugger.getLatestSnapshot(sessionId)
      if (!snapshot) {
        sendJSON(res, 404, { error: 'No context window snapshot found for this session' })
        return true
      }

      sendJSON(res, 200, { snapshot })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /debug/context-window/history
  if (method === 'GET' && pathname === '/debug/context-window/history') {
    const sessionId = url.searchParams.get('sessionId')
    if (!sessionId) {
      sendJSON(res, 400, { error: 'sessionId required' })
      return true
    }

    try {
      const { getContextWindowDebugger } = await import('../events/index.js')
      const ctxDebugger = getContextWindowDebugger()

      if (!ctxDebugger) {
        sendJSON(res, 503, { error: 'Context window debugging not enabled' })
        return true
      }

      const since = url.searchParams.get('since') ? parseInt(url.searchParams.get('since')!, 10) : 0
      const snapshots = since
        ? ctxDebugger.getSnapshotsSince(sessionId, since)
        : ctxDebugger.getSnapshots(sessionId)

      sendJSON(res, 200, {
        sessionId,
        snapshots,
        count: snapshots.length,
        stats: ctxDebugger.getStats(sessionId)
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /debug/context-window/stream
  if (method === 'GET' && pathname === '/debug/context-window/stream') {
    const sessionId = url.searchParams.get('sessionId')
    if (!sessionId) {
      sendJSON(res, 400, { error: 'sessionId required' })
      return true
    }

    try {
      const { getEventBus, getContextWindowDebugger } = await import('../events/index.js')
      const eventBus = getEventBus()
      const ctxDebugger = getContextWindowDebugger()

      if (!ctxDebugger) {
        sendJSON(res, 503, { error: 'Context window debugging not enabled' })
        return true
      }

      const latest = ctxDebugger.getLatestSnapshot(sessionId)

      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      })

      const connId = `ctx_sse_${++sseConnectionId.value}`
      const conn = { res, sessionId, connectedAt: Date.now() }
      sseConnections.set(connId, conn)

      if (latest) {
        res.write(`${[
          `id: ${latest.eventId}`,
          `event: context_window_snapshot`,
          `data: ${JSON.stringify(latest)}`,
          '',
        ].join('\n')  }\n`)
      }

      const unsubscribe = eventBus.onAll((event: any) => {
        if (event.sessionId === sessionId &&
            (event.type === 'context_window_snapshot' || event.type === 'context_window_diff')) {
          const data = JSON.stringify(event)
          try {
            res.write(`${[
              `id: ${event.eventId}`,
              `event: ${event.type}`,
              `data: ${data}`,
              '',
            ].join('\n')  }\n`)
          } catch {
            sseConnections.delete(connId)
            unsubscribe()
          }
        }
      })

      res.on('close', () => {
        sseConnections.delete(connId)
        unsubscribe()
      })

      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /debug/context-window/stats
  if (method === 'GET' && pathname === '/debug/context-window/stats') {
    const sessionId = url.searchParams.get('sessionId')
    if (!sessionId) {
      sendJSON(res, 400, { error: 'sessionId required' })
      return true
    }

    try {
      const { getContextWindowDebugger } = await import('../events/index.js')
      const ctxDebugger = getContextWindowDebugger()

      if (!ctxDebugger) {
        sendJSON(res, 503, { error: 'Context window debugging not enabled' })
        return true
      }

      const stats = ctxDebugger.getStats(sessionId)
      sendJSON(res, 200, { sessionId, stats })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /debug/context-window/clear
  if (method === 'POST' && pathname === '/debug/context-window/clear') {
    try {
      const body = await parseBody(req)
      const sessionId = body?.sessionId

      if (!sessionId) {
        sendJSON(res, 400, { error: 'sessionId required in body' })
        return true
      }

      const { getContextWindowDebugger } = await import('../events/index.js')
      const ctxDebugger = getContextWindowDebugger()

      if (!ctxDebugger) {
        sendJSON(res, 503, { error: 'Context window debugging not enabled' })
        return true
      }

      ctxDebugger.clearSession(sessionId)
      sendJSON(res, 200, { ok: true, message: `Context window history cleared for ${sessionId}` })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
