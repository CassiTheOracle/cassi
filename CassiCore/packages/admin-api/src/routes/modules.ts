import type http from 'node:http'

import type { ILogger } from '../../types/interfaces.js'
import type { AdminRuntimeFacade } from './runtime.js'

export interface ModulesRoutesDeps {
  runtime: AdminRuntimeFacade
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

export async function handleModulesRoutes(
  deps: ModulesRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string,
  parts: string[],
): Promise<boolean> {
  const { runtime, sendJSON, parseBody } = deps
  if (parts[0] !== 'modules') return false

  const registry = runtime.getIntelligence()?.moduleRegistry as {
    listAll?: () => any[]
    getRegistration?: (key: string) => any
    compactNow?: (key: string) => Promise<boolean>
  } | undefined

  if (!registry) {
    sendJSON(res, 503, { error: 'module session registry not available' })
    return true
  }

  if (parts.length === 1 && method === 'GET') {
    sendJSON(res, 200, { modules: registry.listAll?.() ?? [] })
    return true
  }

  const moduleKey = parts[1]
  if (!moduleKey) {
    sendJSON(res, 400, { error: 'missing module key' })
    return true
  }

  if (parts.length === 2 && method === 'GET') {
    const registration = registry.getRegistration?.(moduleKey)
    if (!registration) {
      sendJSON(res, 404, { error: 'module not found' })
      return true
    }
    const session = runtime.getPrimarySessionStore()?.get?.(registration.sessionId)
    sendJSON(res, 200, {
      registration,
      session: session
        ? {
            id: session.id,
            channelId: session.channelId,
            senderId: session.senderId,
            createdAt: session.createdAt,
            lastActiveAt: session.lastActiveAt,
            tokenCount: session.tokenCount,
            historyLength: Array.isArray(session.history) ? session.history.length : 0,
          }
        : null,
    })
    return true
  }

  if (parts.length === 3 && parts[2] === 'compact' && method === 'POST') {
    const ok = await registry.compactNow?.(moduleKey)
    if (!ok) {
      sendJSON(res, 404, { error: 'module not found or compactor unavailable' })
      return true
    }
    sendJSON(res, 200, { ok: true, moduleKey })
    return true
  }

  if (parts.length === 3 && parts[2] === 'chat' && method === 'POST') {
    const registration = registry.getRegistration?.(moduleKey)
    if (!registration) {
      sendJSON(res, 404, { error: 'module not found' })
      return true
    }
    const body = await parseBody(req)
    const content = body?.content
    if (!content || typeof content !== 'string') {
      sendJSON(res, 400, { error: 'missing content' })
      return true
    }
    const result = await runtime.executeTurn({
      requestedSessionId: registration.sessionId,
      channelId: 'channel:module',
      senderId: body?.senderId || `module-api:${moduleKey}`,
      content,
      attachments: body?.attachments,
      model: body?.model,
    })
    sendJSON(res, 200, {
      ok: true,
      moduleKey,
      sessionId: result.sessionId,
      response: result.response,
      model: result.model ?? 'unknown',
      tokensUsed: result.tokensUsed ?? 0,
      engine: result.engine,
    })
    return true
  }

  return false
}
