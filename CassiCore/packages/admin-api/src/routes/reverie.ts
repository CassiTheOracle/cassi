import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'
import type { ReverieModule } from '../intelligence/reverie/index.js'

interface Deps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
}

function getReverie(daemon: any): ReverieModule | undefined {
  return daemon?.intelligence?.reverie
}

export async function handleReverieRoutes(
  deps: Deps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const url = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`)
  const pathname = url.pathname
  if (!pathname.startsWith('/reverie')) return false

  const reverie = getReverie(deps.daemon)
  if (!reverie) {
    deps.sendJSON(res, 503, { error: 'Reverie not available' })
    return true
  }

  if (method === 'GET' && pathname === '/reverie/recent') {
    const limit = url.searchParams.has('limit') ? Number(url.searchParams.get('limit')) : 20
    deps.sendJSON(res, 200, { records: reverie.getRecent(limit) })
    return true
  }

  if (method === 'GET' && pathname === '/reverie/metrics') {
    deps.sendJSON(res, 200, reverie.reverieMetrics())
    return true
  }

  if (method === 'POST' && pathname === '/reverie/ping') {
    const sessionId = url.searchParams.get('sessionId') ?? 'global'
    reverie.ping(sessionId, 'manual-admin')
    deps.sendJSON(res, 202, { ok: true, sessionId })
    return true
  }

  return false
}
