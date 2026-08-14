/**
 * Admin API routes for the Dreamer cognitive module.
 *
 * GET  /dreamer/status      — current state, idle time, last dream, config
 * GET  /dreamer/history     — list of recent dream records
 * POST /dreamer/trigger     — manually trigger a dream cycle immediately
 * GET  /dreamer/insights    — all dream-generated insights from memory archive
 * GET  /memory/deep-archive — search deep-archived memories (retired by dreamer)
 */

import type http from 'node:http'
import type { ILogger } from '@cassicore/foundation'

export interface DreamerRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  pathname: string
}

export async function handleDreamerRoutes(
  deps: DreamerRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { daemon, sendJSON, parseBody, pathname, url } = deps

  // Route matching: dreamer routes and the deep-archive memory route
  const isDreamerRoute = pathname.startsWith('/dreamer')
  const isDeepArchiveRoute = pathname === '/memory/deep-archive'
  if (!isDreamerRoute && !isDeepArchiveRoute) return false

  const dreamer = daemon?.intelligence?.dreamer
  const memory = daemon?.intelligence?.memory

  if (method === 'GET' && pathname === '/dreamer/status') {
    if (!dreamer) {
      sendJSON(res, 503, { error: 'Dreamer module not available' })
      return true
    }
    try {
      sendJSON(res, 200, dreamer.getStatus())
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to get dreamer status', detail: String(err) })
    }
    return true
  }

  if (method === 'GET' && pathname === '/dreamer/history') {
    if (!dreamer) {
      sendJSON(res, 503, { error: 'Dreamer module not available' })
      return true
    }
    try {
      const limit = url.searchParams.get('limit') ? Number(url.searchParams.get('limit')) : 20
      const history = dreamer.getHistory(limit)
      sendJSON(res, 200, { history, count: history.length })
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to get dream history', detail: String(err) })
    }
    return true
  }

  if (method === 'POST' && pathname === '/dreamer/trigger') {
    if (!dreamer) {
      sendJSON(res, 503, { error: 'Dreamer module not available' })
      return true
    }
    try {
      // Non-blocking: start the dream cycle and respond immediately
      const record = await dreamer.triggerDream()
      if (record) {
        sendJSON(res, 200, {
          message: 'Dream cycle completed',
          dreamId: record.id,
          insightsCreated: record.insightsCreated.length,
          episodicsRetired: record.episodicsRetired.length,
          linksCreated: record.linksCreated,
          durationMs: record.durationMs,
        })
      } else {
        sendJSON(res, 409, { error: 'Dream cycle skipped (already in progress or no memory module available)' })
      }
    } catch (err) {
      sendJSON(res, 500, { error: 'Dream cycle failed', detail: String(err) })
    }
    return true
  }

  if (method === 'GET' && pathname === '/dreamer/insights') {
    if (!memory) {
      sendJSON(res, 503, { error: 'Memory module not available' })
      return true
    }
    try {
      const limit = url.searchParams.get('limit') ? Number(url.searchParams.get('limit')) : 20
      const query = url.searchParams.get('q') || ''
      // Search for memories with source='dreamer' in metadata
      const results = await memory.search(query || 'insight', { limit, type: 'insight' })
      const dreamInsights = results.filter((r: any) => r.entry?.metadata?.source === 'dreamer')
      sendJSON(res, 200, {
        insights: dreamInsights.map((r: any) => ({
          id: r.entry.id,
          content: r.entry.content,
          createdAt: r.entry.createdAt,
          confidence: r.entry.metadata?.confidence,
          title: r.entry.metadata?.title,
          topics: r.entry.metadata?.topics,
          dreamId: r.entry.metadata?.dreamId,
          score: r.score,
        })),
        count: dreamInsights.length,
      })
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to fetch dream insights', detail: String(err) })
    }
    return true
  }

  if (method === 'GET' && pathname === '/memory/deep-archive') {
    if (!memory) {
      sendJSON(res, 503, { error: 'Memory module not available' })
      return true
    }
    try {
      const query = url.searchParams.get('q') || ''
      const limit = url.searchParams.get('limit') ? Number(url.searchParams.get('limit')) : 20
      const type = url.searchParams.get('type') || undefined
      const results = await memory.searchDeepArchive(query, { limit, type })
      sendJSON(res, 200, {
        results: results.map((r: any) => ({
          id: r.entry.id,
          type: r.entry.type,
          content: r.entry.content,
          createdAt: r.entry.createdAt,
          metadata: r.entry.metadata,
          score: r.score,
        })),
        count: results.length,
        query,
      })
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to search deep archive', detail: String(err) })
    }
    return true
  }

  // Unmatched dreamer route
  if (isDreamerRoute) {
    sendJSON(res, 404, { error: `Unknown dreamer route: ${pathname}` })
    return true
  }

  return false
}
