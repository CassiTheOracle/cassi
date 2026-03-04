import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'

export interface SubagentsRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  parts: string[]
}

export async function handleSubagentsRoutes(
  deps: SubagentsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, sendJSON, parseBody, url, parts } = deps

  if (parts[0] !== 'subagents') return false

  // GET /subagents
  if (parts.length === 1 && method === 'GET') {
    try {
      const tracker = daemon.subagentTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'subagent tracker not initialised' })
        return true
      }
      const parentFilter = url.searchParams.get('parent')
      const statusFilter = url.searchParams.get('status')
      let list = tracker.list()
      if (parentFilter) {
        list = list.filter((s: any) => s.parentSessionId === parentFilter)
      }
      if (statusFilter) {
        list = list.filter((s: any) => s.status === statusFilter)
      }
      sendJSON(res, 200, {
        subagents: list.map((s: any) => ({
          runId: s.runId,
          label: s.label,
          status: s.status,
          parentSessionId: s.parentSessionId,
          sessionKey: s.sessionKey,
          model: s.model,
          createdAt: s.createdAt,
          startedAt: s.startedAt,
          completedAt: s.completedAt,
          durationMs: s.durationMs,
          tokensUsed: s.tokensUsed,
          hasResult: !!s.result || !!s.error,
        }))
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /subagents/:runId
  if (parts.length === 2 && method === 'GET') {
    try {
      const tracker = daemon.subagentTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'subagent tracker not initialised' })
        return true
      }
      const runId = parts[1]
      const info = tracker.get(runId)
      if (!info) {
        sendJSON(res, 404, { error: 'subagent not found' })
        return true
      }
      sendJSON(res, 200, {
        subagent: {
          runId: info.runId,
          label: info.label,
          status: info.status,
          task: info.task,
          parentSessionId: info.parentSessionId,
          sessionKey: info.sessionKey,
          model: info.model,
          timeoutSeconds: info.timeoutSeconds,
          createdAt: info.createdAt,
          startedAt: info.startedAt,
          completedAt: info.completedAt,
          durationMs: info.durationMs,
          tokensUsed: info.tokensUsed,
        }
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /subagents/:runId/result
  if (parts.length === 3 && parts[2] === 'result' && method === 'GET') {
    try {
      const tracker = daemon.subagentTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'subagent tracker not initialised' })
        return true
      }
      const runId = parts[1]
      const result = tracker.getResult(runId)
      if (!result) {
        const info = tracker.get(runId)
        if (!info) {
          sendJSON(res, 404, { error: 'subagent not found' })
          return true
        }
        sendJSON(res, 202, {
          status: info.status,
          message: 'Subagent still running or result not yet available'
        })
        return true
      }
      sendJSON(res, 200, {
        runId,
        result: result.result,
        error: result.error,
        durationMs: result.durationMs,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /subagents/prune
  if (parts.length === 2 && parts[1] === 'prune' && method === 'POST') {
    try {
      const tracker = daemon.subagentTracker
      if (!tracker) {
        sendJSON(res, 503, { error: 'subagent tracker not initialised' })
        return true
      }
      const body = await parseBody(req)
      const maxAgeMs = body?.maxAgeMs || 24 * 60 * 60 * 1000
      const maxEntries = body?.maxEntries
      const removed = tracker.prune(maxAgeMs, maxEntries)
      sendJSON(res, 200, { pruned: removed })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
