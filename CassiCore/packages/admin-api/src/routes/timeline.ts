/**
 * Admin API routes for the Timeline Store.
 *
 * Provides a unified, chronological view of all system data with
 * cursor-based pagination for efficient scrolling.
 *
 * Routes:
 *   GET  /timeline            — Query timeline with filters + cursor pagination
 *   GET  /timeline/types      — List distinct event types
 *   GET  /timeline/sources    — List distinct source modules
 *   GET  /timeline/stats      — Storage statistics
 *   GET  /timeline/stream     — SSE live tail
 *   GET  /timeline/:id        — Get single entry by ID
 *   POST /timeline/retention  — Update retention config
 *   GET  /timeline/retention  — Get retention config
 */

import type { ILogger } from '@cassicore/foundation'
import type http from 'node:http'
import type { TimelineStore, TimelineQueryOptions } from '../vendor/core/timeline-store.js'

export interface TimelineRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  pathname: string
  sseConnections: Map<string, { res: http.ServerResponse; sessionId: string; connectedAt: number }>
  sseConnectionId: { value: number }
}

export async function handleTimelineRoutes(
  deps: TimelineRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, url, pathname, sseConnections, sseConnectionId } = deps

  // Only handle /timeline* paths
  if (!pathname.startsWith('/timeline')) return false

  const store: TimelineStore | undefined = daemon.timelineStore
  if (!store) {
    sendJSON(res, 503, { error: 'Timeline store not initialized' })
    return true
  }

  // GET /timeline/types — list distinct event types
  if (method === 'GET' && pathname === '/timeline/types') {
    try {
      const types = store.getEventTypes()
      sendJSON(res, 200, { types, count: types.length })
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // GET /timeline/sources — list distinct source modules
  if (method === 'GET' && pathname === '/timeline/sources') {
    try {
      const sources = store.getSources()
      sendJSON(res, 200, { sources, count: sources.length })
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // GET /timeline/stats — storage statistics
  if (method === 'GET' && pathname === '/timeline/stats') {
    try {
      const stats = store.getStats()
      sendJSON(res, 200, stats)
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // GET /timeline/retention — get retention config
  if (method === 'GET' && pathname === '/timeline/retention') {
    try {
      const retention = store.getRetention()
      sendJSON(res, 200, retention)
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // POST /timeline/retention — update retention config
  if (method === 'POST' && pathname === '/timeline/retention') {
    try {
      const body = await parseBody(req)
      if (!body || typeof body !== 'object') {
        sendJSON(res, 400, { error: 'Expected JSON body with { defaultDays?, perType? }' })
        return true
      }
      store.setRetention(body)
      sendJSON(res, 200, { ok: true, retention: store.getRetention() })
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // GET /timeline/stream — SSE live tail
  if (method === 'GET' && pathname === '/timeline/stream') {
    try {
      const filterTypes = url.searchParams.get('types')?.split(',').filter(Boolean) || []
      const filterSource = url.searchParams.get('source') || null
      const filterSessionId = url.searchParams.get('sessionId') || null
      const filterSeverity = url.searchParams.get('severity') || null

      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      })

      const connId = `tl_sse_${++sseConnectionId.value}`
      sseConnections.set(connId, { res, sessionId: '*', connectedAt: Date.now() })

      let eventSeq = 0
      let connectionClosed = false

      const nextEventId = () => `tl_${Date.now()}_${++eventSeq}`

      // Heartbeat
      const heartbeatTimer = setInterval(() => {
        if (connectionClosed) {
          clearInterval(heartbeatTimer)
          return
        }
        try { res.write(`: ping ${Date.now()}\n\n`) } catch { connectionClosed = true }
      }, 15_000)
      heartbeatTimer.unref()

      // Send connected event
      const connectedData = JSON.stringify({ type: 'timeline_connected', timestamp: Date.now() })
      try {
        res.write(`id: ${nextEventId()}\nevent: connected\ndata: ${connectedData}\n\n`)
      } catch { connectionClosed = true }

      // Subscribe to live entries
      const unsub = store.subscribe((entry) => {
        if (connectionClosed) return

        // Apply filters
        if (filterTypes.length > 0 && !filterTypes.includes(entry.type)) return
        if (filterSource && entry.source !== filterSource) return
        if (filterSessionId && entry.session_id !== filterSessionId) return
        if (filterSeverity && entry.severity !== filterSeverity) return

        const data = JSON.stringify(entry)
        try {
          res.write(`id: ${nextEventId()}\nevent: timeline\ndata: ${data}\n\n`)
        } catch {
          connectionClosed = true
        }
      })

      res.on('close', () => {
        connectionClosed = true
        clearInterval(heartbeatTimer)
        sseConnections.delete(connId)
        unsub()
      })

      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /timeline/:id — get single entry by ID
  const idMatch = pathname.match(/^\/timeline\/(\d+)$/)
  if (method === 'GET' && idMatch) {
    try {
      const id = parseInt(idMatch[1], 10)
      const entry = store.getById(id)
      if (!entry) {
        sendJSON(res, 404, { error: `Timeline entry not found: ${id}` })
        return true
      }
      sendJSON(res, 200, { entry })
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // GET /timeline — query with filters and cursor pagination
  if (method === 'GET' && pathname === '/timeline') {
    try {
      const opts: TimelineQueryOptions = {}

      // Parse time range
      const startParam = url.searchParams.get('start')
      const endParam = url.searchParams.get('end')

      if (startParam) {
        opts.start = parseTimeParam(startParam)
      }
      if (endParam) {
        opts.end = parseTimeParam(endParam)
      }

      // Parse filters
      const types = url.searchParams.get('types')
      if (types) opts.types = types.split(',').filter(Boolean)

      const source = url.searchParams.get('source')
      if (source) opts.source = source

      const sessionId = url.searchParams.get('sessionId')
      if (sessionId) opts.sessionId = sessionId

      const provider = url.searchParams.get('provider')
      if (provider) opts.provider = provider

      const severity = url.searchParams.get('severity')
      if (severity) opts.severity = severity

      const search = url.searchParams.get('search')
      if (search) opts.search = search

      const limit = url.searchParams.get('limit')
      if (limit) opts.limit = parseInt(limit, 10)

      const cursor = url.searchParams.get('cursor')
      if (cursor) opts.cursor = cursor

      const order = url.searchParams.get('order')
      if (order === 'asc' || order === 'desc') opts.order = order

      const result = store.query(opts)
      sendJSON(res, 200, result)
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  return false
}


/**
 * Parse flexible time parameters.
 * Supports:
 *   - epoch ms (numeric)
 *   - ISO 8601 strings
 *   - relative shorthand: "5m" (minutes), "2h" (hours), "7d" (days)
 */
function parseTimeParam(value: string): number {
  // Relative time shorthand
  if (/^\d+m$/.test(value)) {
    return Date.now() - parseInt(value, 10) * 60_000
  }
  if (/^\d+h$/.test(value)) {
    return Date.now() - parseInt(value, 10) * 3_600_000
  }
  if (/^\d+d$/.test(value)) {
    return Date.now() - parseInt(value, 10) * 86_400_000
  }
  // ISO 8601
  if (value.includes('T') || value.includes('-')) {
    return new Date(value).getTime()
  }
  // Epoch ms
  return parseInt(value, 10)
}
