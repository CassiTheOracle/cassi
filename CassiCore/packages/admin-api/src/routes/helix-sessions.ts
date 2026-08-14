/**
 * Helix Sessions Admin Routes — brain-integrated Helix session observability.
 *
 * Routes:
 *   GET  /helix-sessions                      — list journaled sessions (most-recent first)
 *   GET  /helix-sessions/:id/events           — latest N entries (?sinceSeq=N&limit=N)
 *   GET  /helix-sessions/:id/snapshot         — last snapshot, if any
 *   GET  /helix-sessions/:id/correlation/:cid — all entries sharing a correlation id
 *   GET  /helix-sessions/:id/stream           — SSE stream of new journal entries
 *
 * The journal and session store are process-wide singletons owned by the
 * daemon's intelligence layer (via getSharedHelixJournal / getSharedHelixSessionStore).
 * Reads are served directly from SQLite; streams attach an in-memory
 * subscriber and filter by session id.
 */

import type http from 'node:http'
import type { ILogger } from '@cassicore/foundation'
import {
  getSharedHelixJournal,
  type HelixJournal,
  type HelixJournalEntry,
  type HelixJournalEventType,
} from '@cassicore/helix'
import { getSharedHelixSessionStore, type HelixSessionStore } from '@cassicore/helix'


export interface HelixSessionsDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, body: unknown) => void
  parseBody?: (req: http.IncomingMessage) => Promise<unknown>
}


const HEARTBEAT_INTERVAL_MS = 15_000
const APPENDABLE_EVENT_TYPES: ReadonlySet<string> = new Set([
  'session.start',
  'session.terminate',
  'posture.lifecycle',
  'diagnostic',
])


export async function handleHelixSessionsRoutes(
  deps: HelixSessionsDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { logger, sendJSON } = deps
  const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`)
  const parts = url.pathname.split('/').filter(Boolean)

  if (parts[0] !== 'helix-sessions') return false

  const journal: HelixJournal = getSharedHelixJournal(logger)
  const sessionStore: HelixSessionStore = getSharedHelixSessionStore(logger)

  if (method === 'GET' && parts.length === 1) {
    const limit = Math.min(parseInt(url.searchParams.get('limit') ?? '50', 10), 500)
    try {
      const sessions = journal.listSessions(limit)
      sendJSON(res, 200, { sessions })
    } catch (err) {
      logger.error('helix-sessions list failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  const sessionId = parts[1]
  if (!sessionId) {
    sendJSON(res, 400, { error: 'Session id required' })
    return true
  }
  const subRoute = parts[2]

  if (method === 'GET' && subRoute === 'events') {
    const sinceSeq = parseInt(url.searchParams.get('sinceSeq') ?? '-1', 10)
    const limit = Math.min(parseInt(url.searchParams.get('limit') ?? '500', 10), 5000)
    try {
      const events = journal.readSession(sessionId, { sinceSeq, limit })
      sendJSON(res, 200, { sessionId, events, count: events.length })
    } catch (err) {
      logger.error('helix-sessions events failed', { sessionId, error: String(err) })
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  if (method === 'POST' && subRoute === 'events') {
    if (!deps.parseBody) {
      sendJSON(res, 503, { error: 'parseBody unavailable' })
      return true
    }
    try {
      const body = asRecord(await deps.parseBody(req))
      const eventType = APPENDABLE_EVENT_TYPES.has(String(body.eventType))
        ? String(body.eventType) as HelixJournalEventType
        : 'diagnostic'
      const payload = asRecord(body.payload)
      const entry = journal.append({
        sessionId,
        eventType,
        postureId: typeof body.postureId === 'string' ? body.postureId : undefined,
        correlationId: typeof body.correlationId === 'string' ? body.correlationId : undefined,
        payload,
      })
      sendJSON(res, 201, { sessionId, entry })
    } catch (err) {
      logger.error('helix-sessions append failed', { sessionId, error: String(err) })
      sendJSON(res, 400, { error: String(err) })
    }
    return true
  }

  if (method === 'GET' && subRoute === 'snapshot') {
    try {
      const snapshot = sessionStore.loadSnapshot(sessionId)
      if (!snapshot) {
        sendJSON(res, 404, { error: 'No snapshot for session', sessionId })
        return true
      }
      sendJSON(res, 200, snapshot)
    } catch (err) {
      logger.error('helix-sessions snapshot failed', { sessionId, error: String(err) })
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  if (method === 'GET' && subRoute === 'correlation' && parts[3]) {
    const correlationId = parts[3]
    const limit = Math.min(parseInt(url.searchParams.get('limit') ?? '500', 10), 5000)
    try {
      const events = journal.readByCorrelation(correlationId, limit)
        .filter(e => e.sessionId === sessionId)
      sendJSON(res, 200, { sessionId, correlationId, events })
    } catch (err) {
      logger.error('helix-sessions correlation failed', { sessionId, correlationId, error: String(err) })
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  if (method === 'GET' && subRoute === 'stream') {
    const timeoutSecs = Math.min(parseInt(url.searchParams.get('timeout') ?? '300', 10), 600)
    const sinceSeq = parseInt(url.searchParams.get('sinceSeq') ?? '-1', 10)

    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    })

    const write = (payload: unknown) => {
      if (res.writableEnded) return
      res.write(`data: ${JSON.stringify(payload)}\n\n`)
    }

    write({ type: 'connected', sessionId })

    try {
      const backfill = journal.readSession(sessionId, { sinceSeq, limit: 1000 })
      for (const entry of backfill) write({ type: 'journal.entry', entry })
    } catch (err) {
      write({ type: 'error', error: String(err) })
    }

    const unsub = journal.subscribe((entry: HelixJournalEntry) => {
      if (entry.sessionId !== sessionId) return
      write({ type: 'journal.entry', entry })
    })

    const heartbeat = setInterval(() => {
      if (!res.writableEnded) res.write(': heartbeat\n\n')
    }, HEARTBEAT_INTERVAL_MS)

    const timeout = setTimeout(() => {
      cleanup()
      if (!res.writableEnded) {
        write({ type: 'timeout' })
        res.end()
      }
    }, timeoutSecs * 1000)

    function cleanup() {
      try { unsub() } catch { /* best-effort */ }
      clearInterval(heartbeat)
      clearTimeout(timeout)
    }

    req.on('close', cleanup)
    return true
  }

  return false
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}
