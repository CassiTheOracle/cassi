import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface EventsRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  buildStateSnapshot: (sessionId: string, events: any[]) => any
  processHierarchyEvent: (event: any) => void
  onEventsIngested?: (events: any[], sessionId: string) => void
  url: URL
  pathname: string
  sseConnections: Map<string, { res: http.ServerResponse; sessionId: string; connectedAt: number }>
  sseConnectionId: { value: number }
}

export async function handleEventsRoutes(
  deps: EventsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, buildStateSnapshot, processHierarchyEvent, url, pathname, sseConnections, sseConnectionId } = deps

  // POST /events/ingest
  if (method === 'POST' && pathname === '/events/ingest') {
    try {
      const body = await parseBody(req)
      if (!body || typeof body !== 'object' || !body.sessionId || !Array.isArray(body.events)) {
        sendJSON(res, 400, { error: 'expected { sessionId, events: [...] }' })
        return true
      }

      const { getEventBus } = await import('../events/index.js')
      const eventBus = getEventBus()

      let ingested = 0
      const errors: string[] = []

      for (const event of body.events) {
        try {
          if (!event.eventId) {
            event.eventId = `evt_${Date.now()}_${Math.random().toString(36).slice(2)}`
          }
          if (!event.timestamp) {
            event.timestamp = Date.now()
          }
          if (!event.sessionId) {
            event.sessionId = body.sessionId
          }

          processHierarchyEvent(event)
          eventBus.emit(event)
          ingested++
        } catch (err) {
          errors.push(String(err))
        }
      }

      sendJSON(res, 200, { ingested, errors: errors.length > 0 ? errors : undefined })

      // Notify admin-api interceptor for OpenCode conversation tracking
      try { deps.onEventsIngested?.(body.events, body.sessionId) } catch {}

      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /events/history
  if (method === 'GET' && pathname === '/events/history') {
    const sessionId = url.searchParams.get('sessionId')
    if (!sessionId) {
      sendJSON(res, 400, { error: 'sessionId required' })
      return true
    }

    try {
      const { getEventBus } = await import('../events/index.js')
      const eventBus = getEventBus()

      const since = parseInt(url.searchParams.get('since') || '0', 10)
      const limit = parseInt(url.searchParams.get('limit') || '100', 10)
      const eventTypes = url.searchParams.get('eventTypes')?.split(',') || []

      let events = eventBus.getEventsSince(sessionId, since)
      if (eventTypes.length > 0) {
        events = events.filter(e => eventTypes.includes(e.type))
      }

      const total = events.length
      const hasMore = total > limit
      events = events.slice(0, limit)

      sendJSON(res, 200, { events, total, hasMore })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /state
  if (method === 'GET' && pathname === '/state') {
    const sessionId = url.searchParams.get('sessionId')
    if (!sessionId) {
      sendJSON(res, 400, { error: 'sessionId required' })
      return true
    }

    try {
      const { getEventBus } = await import('../events/index.js')
      const eventBus = getEventBus()

      const events = eventBus.getAllEvents(sessionId)
      const snapshot = buildStateSnapshot(sessionId, events)

      sendJSON(res, 200, snapshot)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /events/stream
  if (method === 'GET' && pathname === '/events/stream') {
    const sessionId = url.searchParams.get('sessionId') || null
    const globalStream = !sessionId || sessionId === '*'

    try {
      const { getEventBus } = await import('../events/index.js')
      const eventBus = getEventBus()

      const lastEventId = url.searchParams.get('lastEventId')
      let missedEvents: any[] = []
      if (lastEventId && !globalStream) {
        const match = lastEventId.match(/evt_(\d+)_/)
        if (match) {
          const since = parseInt(match[1], 10)
          missedEvents = eventBus.getEventsSince(sessionId!, since)
        }
      }

      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      })

      const connId = `sse_${++sseConnectionId.value}`
      const connSessionId = sessionId ?? '*'
      const conn = { res, sessionId: connSessionId, connectedAt: Date.now() }
      sseConnections.set(connId, conn)

      for (const event of missedEvents) {
        const data = JSON.stringify(event)
        res.write(`${[
          `id: ${event.eventId}`,
          `event: ${event.type}`,
          `data: ${data}`,
          '',
        ].join('\n')  }\n`)
      }

      const connectedEvent = {
        type: 'sse_connected',
        sessionId: connSessionId,
        timestamp: Date.now(),
        eventId: `evt_${Date.now()}`,
      }
      res.write(`${[
        `id: ${connectedEvent.eventId}`,
        `event: ${connectedEvent.type}`,
        `data: ${JSON.stringify(connectedEvent)}`,
        '',
      ].join('\n')  }\n`)

      const unsubscribe = eventBus.onAll((event: any) => {
        if (globalStream || event.sessionId === sessionId) {
          const data = JSON.stringify(event)
          const message = `${[
            `id: ${event.eventId || `evt_${Date.now()}`}`,
            `event: ${event.type}`,
            `data: ${data}`,
            '',
          ].join('\n')  }\n`

          try {
            conn.res.write(`${message  }\n`)
          } catch {
            sseConnections.delete(connId)
          }
        }
      })

      // Bridge internal daemon bus → SSE so cognitive/intelligence events
      // (thinker, dialectic, consciousness, turn, agent, team, drone, etc.)
      // are visible on the stream alongside Cassandra events.
      const COGNITIVE_PREFIXES = [
        'thinker:', 'dialectic:', 'consciousness:', 'subconscious:',
        'turn:', 'agent:', 'team:', 'drone:', 'reflect:', 'optimizer:',
        // autonomy: prefix covers confirmation_requested/approved/rejected — required by
        // external CLI clients (e.g. the Crush fork) to show approval dialogs
        'autonomy:', 'memory:',
        // scout: pre-turn search agent visibility
        'scout:',
      ]

      const forwardCognitive = (enriched: Record<string, unknown>): void => {
        const data = JSON.stringify(enriched)
        const message = `${[
          `id: ${enriched.eventId}`,
          `event: ${enriched.type}`,
          `data: ${data}`,
          '',
        ].join('\n')  }\n`
        try {
          conn.res.write(`${message  }\n`)
        } catch {
          sseConnections.delete(connId)
        }
      }

      const daemonBusUnsub: (() => void) | undefined =
        (daemon as any)?.bus?.onAll?.((event: any) => {
          const type = event?.type as string | undefined
          if (!type) return

          // thinker:insight is wrapped inside a worker:message envelope —
          // unwrap and forward as a direct thinker event
          if (type === 'worker:message' && event.pluginId === 'thinker') {
            const payload = event.payload as Record<string, unknown> | undefined
            const innerType = payload?.type as string | undefined
            if (innerType && innerType.startsWith('thinker:')) {
              const enriched = {
                ...payload,
                sessionId: event.sessionId ?? connSessionId,
                timestamp: event.timestamp ?? Date.now(),
                eventId: `evt_${Date.now()}_${Math.random().toString(36).slice(2)}`,
              }
              if (globalStream || enriched.sessionId === sessionId || event.sessionId == null) {
                forwardCognitive(enriched)
              }
            }
            return
          }

          if (!COGNITIVE_PREFIXES.some(p => type.startsWith(p))) return

          // Ensure every forwarded event has the required SSE fields
          const enriched = {
            ...event,
            sessionId: event.sessionId ?? connSessionId,
            timestamp: event.timestamp ?? Date.now(),
            eventId: event.eventId ?? `evt_${Date.now()}_${Math.random().toString(36).slice(2)}`,
          }

          // Session filter: global stream gets everything; per-session streams
          // get events that explicitly match OR that carry no session context.
          if (!globalStream && enriched.sessionId !== sessionId && event.sessionId != null) return

          forwardCognitive(enriched)
        })

      res.on('close', () => {
        sseConnections.delete(connId)
        unsubscribe.unsubscribe()
        daemonBusUnsub?.()
      })

      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
