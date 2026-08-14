/**
 * Admin API routes for the Prompt Log.
 *
 * Provides structured access to every prompt sent to any provider,
 * stored in SQLite with zero truncation.
 *
 * Routes:
 *   GET  /prompt-log            — List entries (filtered)
 *   GET  /prompt-log/:id        — Get single entry with full messages
 *   GET  /prompt-log/sessions   — List sessions with prompt log counts
 *   GET  /prompt-log/stats      — Storage statistics
 */

import type { ILogger } from '@cassicore/foundation'
import type http from 'node:http'

export interface PromptLogRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  url: URL
  pathname: string
}

export async function handlePromptLogRoutes(
  deps: PromptLogRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { daemon, sendJSON, url, pathname } = deps

  // Only handle /prompt-log* paths
  if (!pathname.startsWith('/prompt-log')) return false

  const store = daemon.promptLogStore
  if (!store) {
    sendJSON(res, 503, { error: 'Prompt log store not initialized' })
    return true
  }

  // GET /prompt-log/sessions — list sessions with prompt log counts
  if (method === 'GET' && pathname === '/prompt-log/sessions') {
    try {
      const limit = parseInt(url.searchParams.get('limit') ?? '50', 10)
      const sessions = store.listSessions(Math.min(limit, 200))
      sendJSON(res, 200, { sessions, count: sessions.length })
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // GET /prompt-log/stats — storage statistics
  if (method === 'GET' && pathname === '/prompt-log/stats') {
    try {
      const stats = store.getStats()
      sendJSON(res, 200, stats)
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // GET /prompt-log/:id — get single entry with full messages
  if (method === 'GET' && pathname.startsWith('/prompt-log/pl_')) {
    try {
      const id = pathname.slice('/prompt-log/'.length)
      const entry = store.getById(id)
      if (!entry) {
        sendJSON(res, 404, { error: `Prompt log entry not found: ${id}` })
        return true
      }
      sendJSON(res, 200, { entry })
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // GET /prompt-log — list entries with filtering
  if (method === 'GET' && pathname === '/prompt-log') {
    try {
      const filters: Record<string, unknown> = {}

      const sessionId = url.searchParams.get('sessionId')
      if (sessionId) filters.sessionId = sessionId

      const source = url.searchParams.get('source')
      if (source) filters.source = source

      const providerId = url.searchParams.get('providerId')
      if (providerId) filters.providerId = providerId

      const model = url.searchParams.get('model')
      if (model) filters.model = model

      const since = url.searchParams.get('since')
      if (since) filters.since = parseInt(since, 10)

      const until = url.searchParams.get('until')
      if (until) filters.until = parseInt(until, 10)

      const limit = parseInt(url.searchParams.get('limit') ?? '50', 10)
      filters.limit = Math.min(limit, 200)

      const entries = store.list(filters)
      sendJSON(res, 200, { entries, count: entries.length })
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  return false
}
