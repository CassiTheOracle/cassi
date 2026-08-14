import type http from 'node:http'

import type { ILogger } from '@cassicore/foundation'
import type { MnemicField } from '@cassicore/mnemic-field'
import type { AdminRuntimeFacade } from './runtime.js'

export interface ReplayRoutesDeps {
  daemon: any
  runtime: AdminRuntimeFacade
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
}

export async function handleReplayRoutes(
  deps: ReplayRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string,
): Promise<boolean> {
  const parts = pathname.split('/').filter(Boolean)
  if (parts[0] !== 'replay' && parts[0] !== 'session-summary' && parts[0] !== 'legacy-sessions') return false

  const field = getMnemicField(deps.daemon)

  if (method === 'GET' && parts[0] === 'replay' && parts[1] === 'session' && parts[2]) {
    if (!field) return unavailable(deps, res)
    const sessionId = decodeURIComponent(parts[2])
    const events = field.replaySession(sessionId)
    deps.sendJSON(res, 200, { sessionId, events, count: events.length })
    return true
  }

  if (method === 'GET' && parts[0] === 'replay' && parts[1] === 'run' && parts[2]) {
    if (!field) return unavailable(deps, res)
    const runId = decodeURIComponent(parts[2])
    const events = field.replayRun(runId)
    deps.sendJSON(res, 200, { runId, events, count: events.length })
    return true
  }

  if (method === 'GET' && parts[0] === 'session-summary' && parts[1]) {
    if (!field) return unavailable(deps, res)
    const sessionId = decodeURIComponent(parts[1])
    const summaryId = `session_summary:${sessionId.startsWith('session:') ? sessionId.slice('session:'.length) : sessionId}`
    const summary = field.get(summaryId)
    if (!summary) {
      deps.sendJSON(res, 404, { error: 'summary_not_found', sessionId })
      return true
    }
    deps.sendJSON(res, 200, { sessionId, summary })
    return true
  }

  if (method === 'GET' && parts[0] === 'legacy-sessions' && parts.length === 1) {
    const sessions = legacyStore(deps).list().map(legacySummary)
    deps.sendJSON(res, 200, { sessions, count: sessions.length })
    return true
  }

  if (method === 'GET' && parts[0] === 'legacy-sessions' && parts[1]) {
    const sessionId = decodeURIComponent(parts[1])
    const session = legacyStore(deps).get(sessionId)
    if (!session) {
      deps.sendJSON(res, 404, { error: 'session_not_found', sessionId })
      return true
    }
    deps.sendJSON(res, 200, { session })
    return true
  }

  return false
}

function getMnemicField(daemon: any): MnemicField | null {
  return (daemon as any).__mnemicFieldForCode ?? (daemon as any).__mnemicField ?? (daemon as any).intelligence?.__mnemicField ?? null
}

function unavailable(deps: ReplayRoutesDeps, res: http.ServerResponse): true {
  deps.sendJSON(res, 503, { error: 'MnemicField not available' })
  return true
}

function legacyStore(deps: ReplayRoutesDeps): any {
  return deps.runtime.getLegacySessionStore()
}

function legacySummary(session: any): Record<string, unknown> {
  return {
    id: session.id,
    channelId: session.channelId,
    senderId: session.senderId,
    createdAt: session.createdAt,
    lastActiveAt: session.lastActiveAt,
    historyLength: Array.isArray(session.history) ? session.history.length : 0,
    tokenCount: session.tokenCount,
    title: session.config?.title ?? null,
  }
}
