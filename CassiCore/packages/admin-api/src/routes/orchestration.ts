import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface OrchestrationRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  parts: string[]
}

export async function handleOrchestrationRoutes(
  deps: OrchestrationRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, sendJSON, parseBody, parts } = deps

  if (parts[0] !== 'orchestration') return false

  // GET /orchestration
  if (method === 'GET' && parts.length === 1) {
    const list = daemon.pluginHost?.all?.() ?? []
    sendJSON(res, 200, list)
    return true
  }

  // GET /orchestration/stalled
  if (method === 'GET' && parts[1] === 'stalled') {
    const all = daemon.pluginHost?.all?.() ?? []
    const stalled = (all as any[]).filter((p) => p.status === 'crashed' || p.status === 'restarting')
    sendJSON(res, 200, stalled)
    return true
  }

  // POST /orchestration/register
  if (method === 'POST' && parts[1] === 'register') {
    const body = await parseBody(req)
    daemon.bus.emit({ type: 'orchestration:register', payload: body })
    sendJSON(res, 200, { ok: true })
    return true
  }

  // POST /orchestration/:id/update
  if (method === 'POST' && parts.length === 3 && parts[2] === 'update') {
    const id = parts[1]
    const body = await parseBody(req)
    daemon.bus.emit({ type: 'orchestration:update', id, payload: body })
    sendJSON(res, 200, { ok: true })
    return true
  }

  // POST /orchestration/:id/complete
  if (method === 'POST' && parts.length === 3 && parts[2] === 'complete') {
    const id = parts[1]
    const body = await parseBody(req)
    daemon.bus.emit({ type: 'orchestration:complete', id, result: body })
    sendJSON(res, 200, { ok: true })
    return true
  }

  return false
}
