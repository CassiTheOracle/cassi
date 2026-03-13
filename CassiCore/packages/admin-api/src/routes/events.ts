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
    const all = url.searchParams.get('all') === 'true' || sessionId === '*'
    if (!sessionId && !all) {
      sendJSON(res, 400, { error: 'sessionId required unless all=true' })
      return true
    }

    try {
      const { getEventBus } = await import('../events/index.js')
      const eventBus = getEventBus()

      const sinceParam = url.searchParams.get('since') ?? '0'
      const limit = parseInt(url.searchParams.get('limit') || '100', 10)
      const tail = parseInt(url.searchParams.get('tail') || '0', 10)
      const eventTypes = url.searchParams.get('eventTypes')?.split(',') || []

      let since = 0
      if (sinceParam.endsWith('m')) {
        since = Date.now() - parseInt(sinceParam, 10) * 60_000
      } else if (sinceParam.endsWith('h')) {
        since = Date.now() - parseInt(sinceParam, 10) * 3_600_000
      } else if (sinceParam.endsWith('d')) {
        since = Date.now() - parseInt(sinceParam, 10) * 86_400_000
      } else if (sinceParam.includes('T') || sinceParam.includes('-')) {
        since = new Date(sinceParam).getTime()
      } else {
        since = parseInt(sinceParam, 10)
      }

      let events = all
        ? eventBus.getGlobalEventsSince(since)
        : eventBus.getEventsSince(sessionId!, since)
      if (eventTypes.length > 0) {
        events = events.filter(e => eventTypes.includes(e.type))
      }

      const totalBeforeTail = events.length
      if (tail > 0) {
        events = events.slice(-tail)
      }

      const total = events.length
      const hasMore = tail > 0 ? totalBeforeTail > tail : total > limit
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

      // ── Backpressure state ────────────────────────────────────────────
      // When res.write() returns false, the kernel buffer is full and we
      // must pause writes until 'drain' fires. If a connection stays
      // paused for >5 seconds it is considered too slow and is closed to
      // prevent unbounded buffer growth.
      let paused = false
      let pausedSince = 0
      const BACKPRESSURE_TIMEOUT_MS = 5_000

      const onDrain = () => {
        paused = false
        pausedSince = 0
      }
      res.on('drain', onDrain)

      /** Write an SSE frame with backpressure awareness. */
      const sseWrite = (message: string): void => {
        if (paused) {
          // Check if the connection has been paused too long
          if (pausedSince > 0 && Date.now() - pausedSince > BACKPRESSURE_TIMEOUT_MS) {
            logger.warn('SSE connection too slow, closing', { connId })
            sseConnections.delete(connId)
            try { res.end() } catch { /* already gone */ }
          }
          // Drop this frame — client is not keeping up
          return
        }
        try {
          const ok = res.write(message)
          if (!ok) {
            paused = true
            pausedSince = Date.now()
            logger.debug('SSE backpressure engaged', { connId })
          }
        } catch {
          sseConnections.delete(connId)
        }
      }

      for (const event of missedEvents) {
        const data = JSON.stringify(event)
        sseWrite(`${[
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
      sseWrite(`${[
        `id: ${connectedEvent.eventId}`,
        `event: ${connectedEvent.type}`,
        `data: ${JSON.stringify(connectedEvent)}`,
        '',
      ].join('\n')  }\n`)

      // Cognitive events are forwarded exclusively by the daemon bus listener below.
      // This listener must skip them to avoid duplicates on the SSE stream.
      const COGNITIVE_PREFIXES = [
        'thinker:', 'dialectic:', 'consciousness:', 'subconscious:',
        'turn:', 'agent:', 'team:', 'drone:', 'reflect:', 'optimizer:',
        'autonomy:', 'memory:',
        'scout:',
        'provider:',
        'macro-dialectic:',
        'daemon:',  // daemon:restarting, daemon:resumed — restart lifecycle
      ]

      const unsubscribe = eventBus.onAll((event: any) => {
        // Skip cognitive events — handled by the daemon bus listener below.
        const type = event?.type as string | undefined
        if (type && COGNITIVE_PREFIXES.some(p => type.startsWith(p))) return

        if (globalStream || event.sessionId === sessionId) {
          const data = JSON.stringify(event)
          const message = `${[
            `id: ${event.eventId || `evt_${Date.now()}`}`,
            `event: ${event.type}`,
            `data: ${data}`,
            '',
          ].join('\n')  }\n`

          try {
            sseWrite(`${message  }\n`)
          } catch {
            sseConnections.delete(connId)
          }
        }
      })

      // Bridge internal daemon bus → SSE so cognitive/intelligence events
      // (thinker, dialectic, consciousness, turn, agent, team, drone, etc.)
      // are visible on the stream alongside Cassandra events.
      // COGNITIVE_PREFIXES is declared above — shared between both listeners.

      const forwardCognitive = (enriched: Record<string, unknown>): void => {
        const data = JSON.stringify(enriched)
        const message = `${[
          `id: ${enriched.eventId}`,
          `event: ${enriched.type}`,
          `data: ${data}`,
          '',
        ].join('\n')  }\n`
        sseWrite(`${message  }\n`)
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
        unsubscribe()
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
