import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'

export interface PluginsRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parts: string[]
}

export async function handlePluginsRoutes(
  deps: PluginsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, sendJSON, parts } = deps

  if (parts[0] !== 'plugins') return false

  // GET /plugins
  if (parts.length === 1 && method === 'GET') {
    const list = daemon.pluginHost?.all?.() ?? []
    sendJSON(res, 200, list)
    return true
  }

  // POST /plugins/:id/restart
  if (parts.length === 3 && parts[2] === 'restart' && method === 'POST') {
    const id = parts[1]
    try {
      await daemon.pluginHost.restart(id)
      sendJSON(res, 200, { ok: true })
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  return false
}
