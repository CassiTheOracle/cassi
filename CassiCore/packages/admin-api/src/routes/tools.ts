import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface ToolsRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  pathname: string
}

export async function handleToolsRoutes(
  deps: ToolsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, sendJSON, parseBody, pathname } = deps

  // POST /tools/execute
  if (method === 'POST' && pathname === '/tools/execute') {
    try {
      const body = await parseBody(req)
      const toolName = body?.tool || body?.name
      const input = body?.input || {}
      const sessionId = body?.sessionId || null
      if (!toolName) {
        sendJSON(res, 400, { error: 'missing tool name (tool)' })
        return true
      }
      const exec = (daemon as any).toolExecutor
      if (!exec || typeof exec.execute !== 'function') {
        sendJSON(res, 503, { error: 'toolExecutor not available' })
        return true
      }
      const { randomUUID } = await import('node:crypto')
      const call = { id: randomUUID(), name: toolName, input }
      try {
        const result = await exec.execute(call, sessionId || `admin-${Date.now()}`)
        sendJSON(res, 200, result)
      } catch (err) {
        sendJSON(res, 500, { error: String(err) })
      }
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /tools/registry
  if (method === 'GET' && pathname === '/tools/registry') {
    try {
      const toolRegistry = (daemon.pipeline as any)?.toolRegistry ?? (daemon.toolRegistry as any)
      if (!toolRegistry || typeof toolRegistry.list !== 'function') {
        sendJSON(res, 503, { error: 'tool registry not initialised' })
        return true
      }
      const list = toolRegistry.list().map((t: any) => ({ name: t.name, description: t.description, parameters: t.parameters }))
      sendJSON(res, 200, list)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
