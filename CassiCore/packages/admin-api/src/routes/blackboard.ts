/**
 * Blackboard Admin API Routes
 *
 * Routes for managing global Blackboards and reading session-scoped snapshots.
 *
 * Routes:
 *   GET    /blackboard/global            — List global blackboards
 *   POST   /blackboard/global            — Create named global blackboard
 *   GET    /blackboard/global/:name      — Get snapshot of a named board
 *   POST   /blackboard/global/:name/post — Post to a channel on a named board
 *   DELETE /blackboard/global/:name      — Delete a named board
 *   GET    /lumen/:sessionId/blackboard  — Get blackboard snapshot for a Lumen session
 *   GET    /dyad/:sessionId/blackboard   — Get blackboard snapshot for a Dyad session
 */

import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'
import type { GlobalBlackboardRegistry } from '../intelligence/flux-team/global-blackboard-registry.js'

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

    // GET /blackboard/global/:name — get snapshot
    if (method === 'GET' && parts[2] && !parts[3]) {
      const name = decodeURIComponent(parts[2])
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

      const validChannels = new Set(['findings', 'concerns', 'decisions', 'artifacts', 'requests'])
      if (!validChannels.has(channel)) {
        return sendJSON(res, 400, { error: `Invalid channel. Must be one of: ${[...validChannels].join(', ')}` }), true
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

    try {
      // Try in-memory active sessions first
      const lumen = daemon.intelligence?.lumen
      if (lumen?.getActiveBlackboard) {
        const snapshot = lumen.getActiveBlackboard(sessionId)
        if (snapshot) return sendJSON(res, 200, snapshot), true
      }

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

    try {
      const dyad = daemon.intelligence?.dyad
      if (dyad?.getActiveBlackboard) {
        const snapshot = dyad.getActiveBlackboard(sessionId)
        if (snapshot) return sendJSON(res, 200, snapshot), true
      }

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
