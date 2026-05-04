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

  if (!pathname.startsWith('/context/')) return false

  const thalamus = getThalamus(deps.daemon)
  if (!thalamus) {
    deps.sendJSON(res, 503, { error: 'Thalamus not available' })
    return true
  }

  // GET /context/audit?sessionId=X&window=5 — Recent drop history
  if (method === 'GET' && pathname === '/context/audit') {
    const sessionId = url.searchParams.get('sessionId')
    if (!sessionId) {
      deps.sendJSON(res, 400, { error: 'sessionId query param required' })
      return true
    }
    const window = parseInt(url.searchParams.get('window') ?? '5', 10)
    const records = thalamus.audit(sessionId, window)
    deps.sendJSON(res, 200, { sessionId, window, records })
    return true
  }

  // GET /context/why?sessionId=X&msgIndex=N — Luminance breakdown for one message
  if (method === 'GET' && pathname === '/context/why') {
    const sessionId = url.searchParams.get('sessionId')
    const msgIndex = parseInt(url.searchParams.get('msgIndex') ?? '', 10)
    if (!sessionId || isNaN(msgIndex)) {
      deps.sendJSON(res, 400, { error: 'sessionId and msgIndex query params required' })
      return true
    }
    const record = thalamus.why(sessionId, msgIndex)
    if (!record) {
      deps.sendJSON(res, 404, { error: 'No score record found for that message' })
      return true
    }
    deps.sendJSON(res, 200, record)
    return true
  }

  // GET /context/map?sessionId=X[&since=N&limit=K] — Per-message visibility roster
  if (method === 'GET' && pathname === '/context/map') {
    const sessionId = url.searchParams.get('sessionId')
    if (!sessionId) {
      deps.sendJSON(res, 400, { error: 'sessionId query param required' })
      return true
    }
    const sinceRaw = url.searchParams.get('since')
    const limitRaw = url.searchParams.get('limit')
    const since = sinceRaw === null ? undefined : parseInt(sinceRaw, 10)
    const limit = limitRaw === null ? undefined : parseInt(limitRaw, 10)
    const snapshot = thalamus.getContextMap(sessionId, {
      since: typeof since === 'number' && !isNaN(since) ? since : undefined,
      limit: typeof limit === 'number' && !isNaN(limit) && limit > 0 ? limit : undefined,
    })
    if (!snapshot) {
      deps.sendJSON(res, 404, { error: 'No curated state for that session yet' })
      return true
    }
    const rows = snapshot.rows
    deps.sendJSON(res, 200, {
      sessionId,
      pass: snapshot.pass,
      curatedAt: snapshot.curatedAt,
      charBudget: snapshot.charBudget,
      charsUsed: snapshot.charsUsed,
      annotatedCount: snapshot.annotatedCount,
      visibleCount: snapshot.visibleCount,
      rows,
    })
    return true
  }

  // POST /context/pin — Pin a message pattern
  if (method === 'POST' && pathname === '/context/pin') {
    const body = await deps.parseBody(req)
    const { sessionId, target, reason, pinClass } = body
    if (!sessionId || !target || !reason) {
      deps.sendJSON(res, 400, { error: 'sessionId, target, and reason are required' })
      return true
    }
    const pinId = thalamus.pin(sessionId, target, reason, pinClass)
    deps.sendJSON(res, 200, { pinId, sessionId, target })
    return true
  }

  // DELETE /context/pin?sessionId=X&pinId=Y — Remove a pin
  if (method === 'DELETE' && pathname === '/context/pin') {
    const sessionId = url.searchParams.get('sessionId')
    const pinId = url.searchParams.get('pinId')
    if (!sessionId || !pinId) {
      deps.sendJSON(res, 400, { error: 'sessionId and pinId query params required' })
      return true
    }
    const removed = thalamus.unpin(sessionId, pinId)
    deps.sendJSON(res, removed ? 200 : 404, { removed })
    return true
  }

  // GET /context/recall?sessionId=X&query=Y&limit=N — Search dropped messages
  if (method === 'GET' && pathname === '/context/recall') {
    const sessionId = url.searchParams.get('sessionId')
    const query = url.searchParams.get('query') ?? ''
    const limit = parseInt(url.searchParams.get('limit') ?? '5', 10)
    if (!sessionId) {
      deps.sendJSON(res, 400, { error: 'sessionId query param required' })
      return true
    }
    const results = thalamus.recall(sessionId, query, limit)
    deps.sendJSON(res, 200, { sessionId, query, results })
    return true
  }

  // POST /context/drop — mark indices to exclude on next curate
  if (method === 'POST' && pathname === '/context/drop') {
    const body = await deps.parseBody(req)
    const { sessionId, indices } = body
    if (!sessionId || !Array.isArray(indices)) {
      deps.sendJSON(res, 400, { error: 'sessionId and indices[] are required' })
      return true
    }
    const numeric = indices.filter((n: any) => Number.isInteger(n))
    const result = thalamus.markDrop(sessionId, numeric)
    deps.sendJSON(res, 200, { sessionId, ...result })
    return true
  }

  // POST /context/collapse — replace a message's content with a summary on next curate
  if (method === 'POST' && pathname === '/context/collapse') {
    const body = await deps.parseBody(req)
    const { sessionId, index, summary } = body
    if (!sessionId || !Number.isInteger(index) || typeof summary !== 'string') {
      deps.sendJSON(res, 400, { error: 'sessionId, integer index, and summary string required' })
      return true
    }
    const result = thalamus.markCollapse(sessionId, index, summary)
    deps.sendJSON(res, 200, { sessionId, index, ...result })
    return true
  }

  // DELETE /context/directives?sessionId=X — clear all drop+collapse directives
  if (method === 'DELETE' && pathname === '/context/directives') {
    const sessionId = url.searchParams.get('sessionId')
    if (!sessionId) {
      deps.sendJSON(res, 400, { error: 'sessionId query param required' })
      return true
    }
    thalamus.clearDirectives(sessionId)
    deps.sendJSON(res, 200, { cleared: true, sessionId })
    return true
  }

  // GET /context/active — most-recently-curated session id
  if (method === 'GET' && pathname === '/context/active') {
    const windowMs = parseInt(url.searchParams.get('windowMs') ?? '300000', 10)
    const sessionId = thalamus.getActiveSessionId(windowMs)
    deps.sendJSON(res, 200, { sessionId })
    return true
  }

  // POST /context/recall_inject — Queue content for re-injection on next curate
  if (method === 'POST' && pathname === '/context/recall_inject') {
    const body = await deps.parseBody(req)
    const { sessionId, content, role, label } = body
    if (!sessionId || !content) {
      deps.sendJSON(res, 400, { error: 'sessionId and content are required' })
      return true
    }
    thalamus.recallInject(sessionId, content, role ?? 'user', label ?? 'manual recall_inject')
    deps.sendJSON(res, 200, { queued: true, sessionId, label })
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
