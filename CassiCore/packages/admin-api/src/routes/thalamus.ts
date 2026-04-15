import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'
import type { ThalamusModule } from '../intelligence/thalamus/index.js'
import { ExternalClientCurator } from '../plugins/external-clients/index.js'
import type { ExternalCurateRequest } from '../plugins/external-clients/types.js'

// 2MB — generous for even the longest conversations (2000 digests ≈ 500KB)
const MAX_CURATION_BODY_BYTES = 2 * 1024 * 1024

interface ThalamusDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

function getThalamus(daemon: any): ThalamusModule | undefined {
  return daemon?.intelligence?.registry?.get('thalamus') as ThalamusModule | undefined
}

let curatorInstance: ExternalClientCurator | null = null

function getOrCreateCurator(deps: ThalamusDeps): ExternalClientCurator | null {
  if (curatorInstance) return curatorInstance

  const thalamus = getThalamus(deps.daemon)
  if (!thalamus) return null

  curatorInstance = new ExternalClientCurator({
    logger: deps.logger,
    getThalamus: () => getThalamus(deps.daemon),
    getSystemContext: async (sessionId: string) => {
      // Fetch cognitive context from the LocusBridge if available
      const locusBridge = deps.daemon?.intelligence?.locusBridge
      if (!locusBridge || typeof locusBridge.curate !== 'function') return []
      try {
        const curated = await locusBridge.curate()
        return curated?.systemContext ?? curated?.parts?.map((p: any) => p.content) ?? []
      } catch {
        return []
      }
    },
  })

  return curatorInstance
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

  // POST /context/curate — Direct thalamus curation (full message objects)
  if (method === 'POST' && pathname === '/context/curate') {
    const body = await deps.parseBody(req)
    const { sessionId, messages, config } = body
    if (!sessionId || !Array.isArray(messages)) {
      deps.sendJSON(res, 400, { error: 'sessionId and messages[] are required' })
      return true
    }
    const result = await thalamus.curate(sessionId, messages, config)
    deps.sendJSON(res, 200, result)
    return true
  }

  // POST /context/curate/external — Index-only curation for external editor clients.
  // Accepts lightweight message digests, returns kept indices + gap annotations.
  // This is the primary integration point for OpenCode, Claude Code, Cursor, etc.
  if (method === 'POST' && pathname === '/context/curate/external') {
    const contentLength = parseInt(req.headers['content-length'] ?? '0', 10)
    if (contentLength > MAX_CURATION_BODY_BYTES) {
      deps.sendJSON(res, 413, { error: `Request body too large (${contentLength} bytes, max ${MAX_CURATION_BODY_BYTES})` })
      return true
    }

    const curator = getOrCreateCurator(deps)
    if (!curator) {
      deps.sendJSON(res, 503, { error: 'External client curator not available' })
      return true
    }

    const body = await deps.parseBody(req) as ExternalCurateRequest
    if (!body?.sessionId || !Array.isArray(body?.digests)) {
      deps.sendJSON(res, 400, { error: 'sessionId and digests[] are required' })
      return true
    }

    try {
      const result = await curator.curate(body)
      deps.sendJSON(res, 200, result)
    } catch (err) {
      deps.logger.error('External curation failed', { error: String(err), sessionId: body.sessionId })
      deps.sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // GET /context/curate/stats — Thalamus curation statistics
  if (method === 'GET' && pathname === '/context/curate/stats') {
    const stats = thalamus.getStats()
    deps.sendJSON(res, 200, stats)
    return true
  }

  return false
}
