/**
 * Blackboard Admin API Routes
 *
 * Routes for managing global Blackboards and reading session-scoped snapshots.
 *
 * Routes:
 *   GET    /blackboard/global            — List global blackboards
 *   POST   /blackboard/global            — Create named global blackboard
 *   GET    /blackboard/global/:name      — Get snapshot of a named board
 *   GET    /blackboard/global/:name/search — Search across all boards on a named board
 *   POST   /blackboard/global/:name/post — Post to a channel on a named board
 *   DELETE /blackboard/global/:name      — Delete a named board
 *   GET    /lumen/:sessionId/blackboard  — Get blackboard snapshot for a Lumen session
 *   GET    /lumen/:sessionId/blackboard/search — Search a Lumen session blackboard
 *   GET    /dyad/:sessionId/blackboard   — Get blackboard snapshot for a Dyad session
 *   GET    /dyad/:sessionId/blackboard/search — Search a Dyad session blackboard
 */

import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'
import type { GlobalBlackboardRegistry } from '../intelligence/flux-team/global-blackboard-registry.js'
import type { BlackboardChannel } from '../../types/flux-team.js'

const VALID_CHANNELS = new Set<BlackboardChannel>(['findings', 'concerns', 'decisions', 'artifacts', 'requests'])

interface BlackboardDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

/** Resolve the global blackboard registry from the daemon (lazy singleton). */
let cachedRegistry: GlobalBlackboardRegistry | undefined | null = undefined

async function getRegistry(daemon: any, logger: ILogger): Promise<GlobalBlackboardRegistry | undefined> {
  if (cachedRegistry !== undefined) return cachedRegistry ?? undefined
  try {
    const { GlobalBlackboardRegistry: RegistryClass } = await import('../intelligence/flux-team/global-blackboard-registry.js')
    cachedRegistry = new RegistryClass(logger.child('global-blackboard-registry'))
    await cachedRegistry.loadAll()
    return cachedRegistry
  } catch (err) {
    logger.warn('GlobalBlackboardRegistry not available', { error: String(err) })
    cachedRegistry = null
    return undefined
  }
}


export async function handleBlackboardRoutes(
  deps: BlackboardDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody } = deps
  const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`)
  const parts = url.pathname.replace(/^\//, '').split('/')


  if (parts[0] === 'blackboard' && parts[1] === 'global') {
    const registry = await getRegistry(daemon, logger)
    if (!registry) {
      return sendJSON(res, 503, { error: 'GlobalBlackboardRegistry not available' }), true
    }

    // GET /blackboard/global — list all boards
    if (method === 'GET' && !parts[2]) {
      return sendJSON(res, 200, { boards: registry.list() }), true
    }

    // POST /blackboard/global — create a named board
    if (method === 'POST' && !parts[2]) {
      const body = await parseBody(req)
      const name = body?.name
      if (!name || typeof name !== 'string') {
        return sendJSON(res, 400, { error: 'Missing required field: name (string)' }), true
      }
      const persist = body?.persist === true
      registry.getOrCreate(name, { persist })
      if (persist) {
        await registry.save(name)
      }
      return sendJSON(res, 201, { name, persist, message: `Blackboard '${name}' created.` }), true
    }

    // GET /blackboard/global/:name — get snapshot (supports ?summary=true, ?channel=X, ?limit=N)
    if (method === 'GET' && parts[2] && !parts[3]) {
      const name = decodeURIComponent(parts[2])
      const wantSummary = url.searchParams.get('summary') === 'true'
      const channelFilter = url.searchParams.get('channel') as BlackboardChannel | null
      const limitParam = url.searchParams.get('limit')
      const limit = limitParam ? parseInt(limitParam, 10) : undefined

      if (channelFilter && !VALID_CHANNELS.has(channelFilter)) {
        return sendJSON(res, 400, { error: `Invalid channel. Must be one of: ${[...VALID_CHANNELS].join(', ')}` }), true
      }

      if (channelFilter) {
        const entries = registry.getChannelEntries(name, channelFilter, limit)
        if (!entries) {
          await registry.load(name)
          const retryEntries = registry.getChannelEntries(name, channelFilter, limit)
          if (!retryEntries) return sendJSON(res, 404, { error: `Blackboard '${name}' not found.` }), true
          return sendJSON(res, 200, { channel: channelFilter, entries: retryEntries }), true
        }
        return sendJSON(res, 200, { channel: channelFilter, entries }), true
      }

      if (wantSummary) {
        let summary = registry.getSummary(name)
        if (!summary) {
          await registry.load(name)
          summary = registry.getSummary(name)
        }
        if (!summary) return sendJSON(res, 404, { error: `Blackboard '${name}' not found.` }), true
        return sendJSON(res, 200, summary), true
      }

      let snapshot = registry.getSnapshot(name)
      if (!snapshot) {
        await registry.load(name)
        snapshot = registry.getSnapshot(name)
      }
      if (!snapshot) {
        return sendJSON(res, 404, { error: `Blackboard '${name}' not found.` }), true
      }
      return sendJSON(res, 200, snapshot), true
    }

    // GET /blackboard/global/:name/search — search across all boards
    if (method === 'GET' && parts[2] && parts[3] === 'search') {
      const name = decodeURIComponent(parts[2])
      const pattern = url.searchParams.get('pattern') ?? ''
      if (!pattern) {
        return sendJSON(res, 400, { error: 'Missing required query param: pattern' }), true
      }
      const boardsParam = url.searchParams.get('boards')
      const boards = boardsParam ? boardsParam.split(',').map(b => b.trim()) as any[] : undefined
      const limitParam = url.searchParams.get('limit')
      const limitPerBoard = limitParam ? parseInt(limitParam, 10) : undefined
      const cursor = url.searchParams.get('cursor') ?? undefined
      const author = url.searchParams.get('author') ?? undefined
      const sinceParam = url.searchParams.get('since')
      const since = sinceParam ? parseInt(sinceParam, 10) : undefined
      const untilParam = url.searchParams.get('until')
      const until = untilParam ? parseInt(untilParam, 10) : undefined

      let result = registry.searchAll(name, { pattern, boards, limitPerBoard, cursor, author, since, until })
      if (!result) {
        await registry.load(name)
        result = registry.searchAll(name, { pattern, boards, limitPerBoard, cursor, author, since, until })
      }
      if (!result) {
        return sendJSON(res, 404, { error: `Blackboard '${name}' not found.` }), true
      }
      return sendJSON(res, 200, result), true
    }

    // POST /blackboard/global/:name/post — post to a channel
    if (method === 'POST' && parts[2] && parts[3] === 'post') {
      const name = decodeURIComponent(parts[2])
      let board = registry.get(name)
      if (!board) {
        await registry.load(name)
        board = registry.get(name)
      }
      if (!board) {
        return sendJSON(res, 404, { error: `Blackboard '${name}' not found.` }), true
      }
      const body = await parseBody(req)
      const channel = body?.channel
      const content = body?.content
      if (!channel || typeof channel !== 'string') {
        return sendJSON(res, 400, { error: 'Missing required field: channel (string)' }), true
      }
      if (!content || typeof content !== 'string') {
        return sendJSON(res, 400, { error: 'Missing required field: content (string)' }), true
      }

      if (!VALID_CHANNELS.has(channel as BlackboardChannel)) {
        return sendJSON(res, 400, { error: `Invalid channel. Must be one of: ${[...VALID_CHANNELS].join(', ')}` }), true
      }

      const priorityMap: Record<string, number> = { high: 2, medium: 1, low: 0 }
      const priority = priorityMap[body?.priority ?? 'medium'] ?? 1
      const tags = Array.isArray(body?.tags) ? body.tags.map(String) : []
      const author = body?.author ? String(body.author) : 'api'

      const entry = board.post(channel as any, { author, content, tags, priority })
      try {
        await registry.save(name)
      } catch {
        // Best-effort persistence; non-persisted boards or fs errors should not fail the request.
      }
      return sendJSON(res, 201, { id: entry.id, channel, message: `Posted to '${name}/${channel}'.` }), true
    }

    // DELETE /blackboard/global/:name — delete a board
    if (method === 'DELETE' && parts[2] && !parts[3]) {
      const name = decodeURIComponent(parts[2])
      const deleted = registry.delete(name)
      if (!deleted) {
        return sendJSON(res, 404, { error: `Blackboard '${name}' not found.` }), true
      }
      return sendJSON(res, 200, { name, deleted: true }), true
    }
  }


  if (parts[0] === 'lumen' && parts[1] && parts[2] === 'blackboard') {
    if (method !== 'GET') return false
    const sessionId = parts[1]

    // GET /lumen/:id/blackboard/search — search across all boards
    if (parts[3] === 'search') {
      const pattern = url.searchParams.get('pattern') ?? ''
      if (!pattern) {
        return sendJSON(res, 400, { error: 'Missing required query param: pattern' }), true
      }
      try {
        const lumen = daemon.intelligence?.lumen
        if (lumen?.getActiveBlackboardInstance) {
          const bb = lumen.getActiveBlackboardInstance(sessionId)
          if (bb) {
            const boardsParam = url.searchParams.get('boards')
            const boards = boardsParam ? boardsParam.split(',').map((b: string) => b.trim()) as any[] : undefined
            const limitParam = url.searchParams.get('limit')
            const limitPerBoard = limitParam ? parseInt(limitParam, 10) : undefined
            const cursor = url.searchParams.get('cursor') ?? undefined
            const author = url.searchParams.get('author') ?? undefined
            const sinceParam = url.searchParams.get('since')
            const since = sinceParam ? parseInt(sinceParam, 10) : undefined
            const result = bb.searchAll({ pattern, boards, limitPerBoard, cursor, author, since })
            return sendJSON(res, 200, result), true
          }
        }
        return sendJSON(res, 404, { error: `No active blackboard found for Lumen session '${sessionId}'. Search is only available on active sessions.` }), true
      } catch (err) {
        return sendJSON(res, 500, { error: String(err) }), true
      }
    }

    const wantSummary = url.searchParams.get('summary') === 'true'
    const channelFilter = url.searchParams.get('channel') as BlackboardChannel | null
    const limitParam = url.searchParams.get('limit')
    const limit = limitParam ? parseInt(limitParam, 10) : undefined

    if (channelFilter && !VALID_CHANNELS.has(channelFilter)) {
      return sendJSON(res, 400, { error: `Invalid channel. Must be one of: ${[...VALID_CHANNELS].join(', ')}` }), true
    }

    try {
      // Try in-memory active sessions first
      const lumen = daemon.intelligence?.lumen

      if (channelFilter && lumen?.getActiveChannel) {
        const entries = lumen.getActiveChannel(sessionId, channelFilter, limit)
        if (entries) return sendJSON(res, 200, { channel: channelFilter, entries }), true
      }

      if (wantSummary && lumen?.getActiveSummary) {
        const summary = lumen.getActiveSummary(sessionId)
        if (summary) return sendJSON(res, 200, summary), true
      }

      if (!channelFilter && !wantSummary && lumen?.getActiveBlackboard) {
        const snapshot = lumen.getActiveBlackboard(sessionId)
        if (snapshot) return sendJSON(res, 200, snapshot), true
      }

      // Fallback to persisted session
      const { LumenStore } = await import('../intelligence/lumen/lumen-store.js').catch(() => ({ LumenStore: null }))
      if (LumenStore) {
        const store = (LumenStore as any).open(logger.child('lumen-store-bb'))
        const session = store?.getSession?.(sessionId)
        if (session?.blackboard) {
          return sendJSON(res, 200, session.blackboard), true
        }
      }

      return sendJSON(res, 404, {
        error: `No blackboard found for Lumen session '${sessionId}'.`,
        note: 'Blackboard snapshots are currently available for active sessions or completed sessions persisted after Blackboard snapshot support was added.',
      }), true
    } catch (err) {
      return sendJSON(res, 500, { error: String(err) }), true
    }
  }


  if (parts[0] === 'dyad' && parts[1] && parts[2] === 'blackboard') {
    if (method !== 'GET') return false
    const sessionId = parts[1]

    // GET /dyad/:id/blackboard/search — search across all boards
    if (parts[3] === 'search') {
      const pattern = url.searchParams.get('pattern') ?? ''
      if (!pattern) {
        return sendJSON(res, 400, { error: 'Missing required query param: pattern' }), true
      }
      try {
        const dyad = daemon.intelligence?.dyad
        if (dyad?.getActiveBlackboardInstance) {
          const bb = dyad.getActiveBlackboardInstance(sessionId)
          if (bb) {
            const boardsParam = url.searchParams.get('boards')
            const boards = boardsParam ? boardsParam.split(',').map((b: string) => b.trim()) as any[] : undefined
            const limitParam = url.searchParams.get('limit')
            const limitPerBoard = limitParam ? parseInt(limitParam, 10) : undefined
            const cursor = url.searchParams.get('cursor') ?? undefined
            const author = url.searchParams.get('author') ?? undefined
            const sinceParam = url.searchParams.get('since')
            const since = sinceParam ? parseInt(sinceParam, 10) : undefined
            const result = bb.searchAll({ pattern, boards, limitPerBoard, cursor, author, since })
            return sendJSON(res, 200, result), true
          }
        }
        return sendJSON(res, 404, { error: `No active blackboard found for Dyad session '${sessionId}'. Search is only available on active sessions.` }), true
      } catch (err) {
        return sendJSON(res, 500, { error: String(err) }), true
      }
    }

    const wantSummary = url.searchParams.get('summary') === 'true'
    const channelFilter = url.searchParams.get('channel') as BlackboardChannel | null
    const limitParam = url.searchParams.get('limit')
    const limit = limitParam ? parseInt(limitParam, 10) : undefined

    if (channelFilter && !VALID_CHANNELS.has(channelFilter)) {
      return sendJSON(res, 400, { error: `Invalid channel. Must be one of: ${[...VALID_CHANNELS].join(', ')}` }), true
    }

    try {
      const dyad = daemon.intelligence?.dyad

      if (channelFilter && dyad?.getActiveChannel) {
        const entries = dyad.getActiveChannel(sessionId, channelFilter, limit)
        if (entries) return sendJSON(res, 200, { channel: channelFilter, entries }), true
      }

      if (wantSummary && dyad?.getActiveSummary) {
        const summary = dyad.getActiveSummary(sessionId)
        if (summary) return sendJSON(res, 200, summary), true
      }

      if (!channelFilter && !wantSummary && dyad?.getActiveBlackboard) {
        const snapshot = dyad.getActiveBlackboard(sessionId)
        if (snapshot) return sendJSON(res, 200, snapshot), true
      }

      // Fallback to persisted session
      const { DyadStore } = await import('../intelligence/dyad/dyad-store.js').catch(() => ({ DyadStore: null }))
      if (DyadStore) {
        const store = (DyadStore as any).open(logger.child('dyad-store-bb'))
        const session = store?.getSession?.(sessionId)
        if (session?.blackboard) {
          return sendJSON(res, 200, session.blackboard), true
        }
      }

      return sendJSON(res, 404, {
        error: `No blackboard found for Dyad session '${sessionId}'.`,
        note: 'Blackboard snapshots are currently available for active sessions or completed sessions persisted after Blackboard snapshot support was added.',
      }), true
    } catch (err) {
      return sendJSON(res, 500, { error: String(err) }), true
    }
  }

  return false
}
