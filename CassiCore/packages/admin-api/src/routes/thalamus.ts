import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'
import type { ThalamusModule } from '../intelligence/thalamus/index.js'

interface ThalamusDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

function getThalamus(daemon: any): ThalamusModule | undefined {
  return daemon?.intelligence?.registry?.get('thalamus') as ThalamusModule | undefined
}

export async function handleThalamusRoutes(
  deps: ThalamusDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const url = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`)
  const pathname = url.pathname

  if (!pathname.startsWith('/context/curate')) return false

  const thalamus = getThalamus(deps.daemon)
  if (!thalamus) {
    deps.sendJSON(res, 503, { error: 'Thalamus not available' })
    return true
  }

  if (method === 'POST' && pathname === '/context/curate') {
    const body = await deps.parseBody(req)
    const { sessionId, messages, config } = body
    if (!sessionId || !Array.isArray(messages)) {
      deps.sendJSON(res, 400, { error: 'sessionId and messages[] are required' })
      return true
    }
    const result = thalamus.curate(sessionId, messages, config)
    deps.sendJSON(res, 200, result)
    return true
  }

  if (method === 'GET' && pathname === '/context/curate/stats') {
    const stats = thalamus.getStats()
    deps.sendJSON(res, 200, stats)
    return true
  }

  return false
}
