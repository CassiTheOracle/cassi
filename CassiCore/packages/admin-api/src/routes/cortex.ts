import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'
import type { CorticalField } from '../intelligence/cortex/index.js'
import type { SignalType, SignalState } from '../intelligence/cortex/types.js'
import { SIGNAL_TYPES } from '../intelligence/cortex/types.js'
import { computeActivation } from '../intelligence/cortex/signal.js'

interface CortexDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

function getCortex(daemon: any): CorticalField | undefined {
  return daemon?.intelligence?.cortex
}

function extractPathParam(pathname: string, prefix: string): string | undefined {
  if (!pathname.startsWith(prefix)) return undefined
  const param = pathname.slice(prefix.length)
  return param && !param.includes('/') ? decodeURIComponent(param) : undefined
}

export async function handleCortexRoutes(
  deps: CortexDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const url = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`)
  const pathname = url.pathname

  if (!pathname.startsWith('/cortex')) return false

  const cortex = getCortex(deps.daemon)
  if (!cortex) {
    deps.sendJSON(res, 503, { error: 'CorticalField not available' })
    return true
  }

  // --- Existing endpoints ---

  if (method === 'POST' && pathname === '/cortex/signal') {
    const body = await deps.parseBody(req)
    const { region, type, content, author, salience, valence, confidence, tags, sessionId } = body
    if (!region || !type || !content || !author) {
      deps.sendJSON(res, 400, { error: 'region, type, content, and author are required' })
      return true
    }
    if (!(SIGNAL_TYPES as readonly string[]).includes(type)) {
      deps.sendJSON(res, 400, { error: `Invalid signal type. Valid: ${SIGNAL_TYPES.join(', ')}` })
      return true
    }
    try {
      const signal = cortex.signal(region, {
        type: type as SignalType,
        content,
        author,
        salience,
        valence,
        confidence,
        tags,
        sessionId,
      })
      deps.sendJSON(res, 201, { id: signal.id, region: signal.region, activation: signal.activation })
    } catch (err) {
      deps.sendJSON(res, 400, { error: String(err) })
    }
    return true
  }

  if (method === 'GET' && pathname === '/cortex/active') {
    const regions = url.searchParams.get('regions')?.split(',')
    const rawTypes = url.searchParams.get('types')?.split(',')
    const types = rawTypes?.filter((t): t is SignalType =>
      (SIGNAL_TYPES as readonly string[]).includes(t)
    )
    const limit = url.searchParams.has('limit') ? Number(url.searchParams.get('limit')) : 20
    const sessionId = url.searchParams.get('sessionId') ?? undefined

    const signals = cortex.readActive({ regions, types, limit, sessionId })
    deps.sendJSON(res, 200, {
      count: signals.length,
      signals: signals.map(s => ({
        id: s.id,
        region: s.region,
        type: s.type,
        content: s.content,
        author: s.author,
        salience: s.salience,
        activation: s.activation,
        valence: s.valence,
        state: s.state,
        tags: s.tags,
        sessionId: s.sessionId,
        createdAt: s.createdAt,
      })),
    })
    return true
  }

  if (method === 'GET' && pathname === '/cortex/regions') {
    deps.sendJSON(res, 200, { regions: cortex.listRegions() })
    return true
  }

  if (method === 'GET' && pathname === '/cortex/tracts') {
    deps.sendJSON(res, 200, { tracts: cortex.listTracts() })
    return true
  }

  if (method === 'GET' && pathname === '/cortex/sessions') {
    deps.sendJSON(res, 200, { sessions: cortex.listSessions() })
    return true
  }

  if (method === 'POST' && pathname === '/cortex/tick') {
    const result = cortex.tick()
    deps.sendJSON(res, 200, result)
    return true
  }

  if (method === 'GET' && pathname === '/cortex/snapshot') {
    const regionInfos = cortex.listRegions()
    const totalSignals = regionInfos.reduce((sum, r) => sum + r.signalCount, 0)
    deps.sendJSON(res, 200, {
      timestamp: Date.now(),
      regionCount: regionInfos.length,
      tractCount: cortex.listTracts().length,
      totalSignals,
      sessions: cortex.listSessions().length,
      regions: regionInfos.map(r => ({
        name: r.name,
        isSystem: r.isSystem,
        signalCount: r.signalCount,
        activeCount: r.activeCount,
      })),
    })
    return true
  }

  if (method === 'POST' && pathname === '/cortex/attend') {
    const body = await deps.parseBody(req)
    if (!body.signalId) {
      deps.sendJSON(res, 400, { error: 'signalId required' })
      return true
    }
    const signal = cortex.attend(body.signalId)
    if (!signal) {
      deps.sendJSON(res, 404, { error: 'Signal not found' })
      return true
    }
    deps.sendJSON(res, 200, { id: signal.id, activation: signal.activation })
    return true
  }

  if (method === 'GET' && pathname === '/cortex/affect') {
    const affect = cortex.getAffectState()
    deps.sendJSON(res, 200, affect ?? { valence: 0, arousal: 0, dominance: 0.5, label: 'neutral' })
    return true
  }

  // --- Observability endpoints ---

  if (method === 'GET' && pathname === '/cortex/stats') {
    deps.sendJSON(res, 200, cortex.getStats())
    return true
  }

  if (method === 'GET' && pathname === '/cortex/oscillation/history') {
    const limit = url.searchParams.has('limit') ? Number(url.searchParams.get('limit')) : 50
    const history = cortex.getOscillationHistory(limit)
    deps.sendJSON(res, 200, {
      count: history.length,
      entries: history,
    })
    return true
  }

  // GET /cortex/region/:name — detailed view of a single region
  const regionParam = extractPathParam(pathname, '/cortex/region/')
  if (method === 'GET' && regionParam) {
    const detail = cortex.getRegionDetail(regionParam)
    if (!detail) {
      deps.sendJSON(res, 404, { error: `Region not found: ${regionParam}` })
      return true
    }
    deps.sendJSON(res, 200, detail)
    return true
  }

  // GET /cortex/signal/:id — detailed view of a single signal
  const signalParam = extractPathParam(pathname, '/cortex/signal/')
  if (method === 'GET' && signalParam) {
    const detail = cortex.getSignalDetail(signalParam)
    if (!detail) {
      deps.sendJSON(res, 404, { error: `Signal not found: ${signalParam}` })
      return true
    }
    deps.sendJSON(res, 200, detail)
    return true
  }

  if (method === 'GET' && pathname === '/cortex/signals/search') {
    const region = url.searchParams.get('region') ?? undefined
    const type = url.searchParams.get('type') as SignalType | undefined
    const state = url.searchParams.get('state') as SignalState | undefined
    const author = url.searchParams.get('author') ?? undefined
    const tagsRaw = url.searchParams.get('tags')
    const tags = tagsRaw ? tagsRaw.split(',') : undefined
    const sessionId = url.searchParams.get('sessionId') ?? undefined
    const content = url.searchParams.get('content') ?? undefined
    const limit = url.searchParams.has('limit') ? Number(url.searchParams.get('limit')) : 50

    const signals = cortex.searchSignals({ region, type, state, author, tags, sessionId, content, limit })
    const now = Date.now()
    deps.sendJSON(res, 200, {
      count: signals.length,
      signals: signals.map(s => ({
        id: s.id,
        region: s.region,
        type: s.type,
        content: s.content,
        author: s.author,
        salience: s.salience,
        activation: computeActivation(s, now),
        valence: s.valence,
        confidence: s.confidence,
        state: s.state,
        tags: s.tags,
        bindings: s.bindings.length,
        sessionId: s.sessionId,
        createdAt: s.createdAt,
      })),
    })
    return true
  }

  if (method === 'GET' && pathname === '/cortex/signals/consolidated') {
    const limit = url.searchParams.has('limit') ? Number(url.searchParams.get('limit')) : 20
    const signals = cortex.getConsolidated(limit)
    const now = Date.now()
    deps.sendJSON(res, 200, {
      count: signals.length,
      signals: signals.map(s => ({
        id: s.id,
        region: s.region,
        type: s.type,
        content: s.content,
        author: s.author,
        salience: s.salience,
        activation: computeActivation(s, now),
        tags: s.tags,
        bindings: s.bindings.length,
        consolidatedAt: s.consolidatedAt,
        createdAt: s.createdAt,
      })),
    })
    return true
  }

  if (method === 'GET' && pathname === '/cortex/signals/fading') {
    const limit = url.searchParams.has('limit') ? Number(url.searchParams.get('limit')) : 20
    const signals = cortex.getFading(limit)
    const now = Date.now()
    deps.sendJSON(res, 200, {
      count: signals.length,
      signals: signals.map(s => ({
        id: s.id,
        region: s.region,
        type: s.type,
        content: s.content,
        author: s.author,
        salience: s.salience,
        activation: computeActivation(s, now),
        tags: s.tags,
        bindings: s.bindings.length,
        createdAt: s.createdAt,
      })),
    })
    return true
  }

  // GET /cortex/session/:id — detailed view of a session's working memory
  const sessionParam = extractPathParam(pathname, '/cortex/session/')
  if (method === 'GET' && sessionParam) {
    const detail = cortex.getSessionDetail(sessionParam)
    if (!detail) {
      deps.sendJSON(res, 404, { error: `Session not found: ${sessionParam}` })
      return true
    }
    deps.sendJSON(res, 200, detail)
    return true
  }

  // GET /cortex/tract/:id — detailed view of a single tract
  const tractParam = extractPathParam(pathname, '/cortex/tract/')
  if (method === 'GET' && tractParam) {
    const tract = cortex.getTract(tractParam)
    if (!tract) {
      deps.sendJSON(res, 404, { error: `Tract not found: ${tractParam}` })
      return true
    }
    deps.sendJSON(res, 200, tract)
    return true
  }

  return false
}
