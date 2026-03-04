import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'

export interface McpRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
}

export async function handleMcpRoutes(
  deps: McpRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string
): Promise<boolean> {
  const { daemon, sendJSON } = deps

  // GET /mcp
  if (method === 'GET' && pathname === '/mcp') {
    try {
      const mcpRef = (daemon.healthMonitor as any)?.mcp ?? (daemon.mcpRegistry as any) ?? undefined
      if (!mcpRef || typeof mcpRef.status !== 'function') {
        sendJSON(res, 200, { servers: [], message: 'No MCP servers configured' })
        return true
      }
      const servers = mcpRef.status()
      sendJSON(res, 200, servers)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
