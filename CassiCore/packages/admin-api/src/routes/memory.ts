import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface MemoryRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  parts: string[]
}

export async function handleMemoryRoutes(
  deps: MemoryRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, sendJSON, parseBody, url, parts } = deps

  if (parts[0] !== 'memory') return false

  const memory = daemon.intelligence?.memory

  function noMemory(): true {
    sendJSON(res, 503, { error: 'memory not available' })
    return true
  }

  if (parts[1] === 'stats' && method === 'GET') {
    if (!memory) return noMemory()
    const memStats = await memory.stats()
    const archiveStats = memory.getArchiveStats?.() ?? null
    const queueStats = memory.getArchiveQueueStats?.() ?? null
    sendJSON(res, 200, { memory: memStats, archives: archiveStats, queue: queueStats })
    return true
  }


  // POST /memory/archives/search
  if (parts[1] === 'archives' && parts[2] === 'search' && method === 'POST') {
    if (!memory) return noMemory()
    if (!memory.searchArchives) {
      sendJSON(res, 501, { error: 'archive search not available' })
      return true
    }
    const body = await parseBody(req)
    const results = await memory.searchArchives(body?.query ?? '', {
      filters: body?.filters,
      limit: body?.limit ?? 20,
      sortBy: body?.sortBy,
    })
    sendJSON(res, 200, results)
    return true
  }

  // GET /memory/archives/recent
  if (parts[1] === 'archives' && parts[2] === 'recent' && method === 'GET') {
    if (!memory) return noMemory()
    if (!memory.getRecentArchiveEntries) {
      sendJSON(res, 501, { error: 'archive not available' })
      return true
    }
    const limit = parseInt(url.searchParams.get('limit') ?? '10', 10)
    sendJSON(res, 200, memory.getRecentArchiveEntries(limit))
    return true
  }

  // GET /memory/archives/browse?category=tags|entities|topics&minCount=N
  if (parts[1] === 'archives' && parts[2] === 'browse' && method === 'GET') {
    if (!memory) return noMemory()
    const category = url.searchParams.get('category') as 'tags' | 'entities' | 'topics' | null
    const minCount = parseInt(url.searchParams.get('minCount') ?? '1', 10)
    if (!category || !['tags', 'entities', 'topics'].includes(category)) {
      sendJSON(res, 400, { error: 'category must be tags, entities, or topics' })
      return true
    }
    let items: { name: string; count: number }[] = []
    if (category === 'tags' && memory.getAllTags) {
      items = memory.getAllTags(minCount).map((r: { tag: string; count: number }) => ({ name: r.tag, count: r.count }))
    } else if (category === 'entities' && memory.getAllEntities) {
      items = memory.getAllEntities(minCount).map((r: { entity: string; count: number }) => ({ name: r.entity, count: r.count }))
    } else if (category === 'topics' && memory.getAllTopics) {
      items = memory.getAllTopics(minCount).map((r: { topic: string; count: number }) => ({ name: r.topic, count: r.count }))
    } else {
      sendJSON(res, 501, { error: `${category} browse not available` })
      return true
    }
    sendJSON(res, 200, { category, items })
    return true
  }

  // GET /memory/archives/:id/related
  if (parts[1] === 'archives' && parts[3] === 'related' && method === 'GET') {
    if (!memory) return noMemory()
    if (!memory.getRelatedArchives) {
      sendJSON(res, 501, { error: 'archive not available' })
      return true
    }
    const limit = parseInt(url.searchParams.get('limit') ?? '10', 10)
    sendJSON(res, 200, memory.getRelatedArchives(parts[2], limit))
    return true
  }

  // GET /memory/archives/:id
  if (parts[1] === 'archives' && parts[2] && parts.length === 3 && method === 'GET') {
    if (!memory) return noMemory()
    if (!memory.getArchiveById) {
      sendJSON(res, 501, { error: 'archive not available' })
      return true
    }
    const entry = memory.getArchiveById(parts[2])
    if (!entry) {
      sendJSON(res, 404, { error: 'not_found' })
      return true
    }
    sendJSON(res, 200, entry)
    return true
  }


  // GET /memory/kv/:key
  if (parts[1] === 'kv' && parts[2] && method === 'GET') {
    if (!memory) return noMemory()
    const key = decodeURIComponent(parts[2])
    const value = await memory.kv_get(key)
    sendJSON(res, 200, { key, value: value ?? null })
    return true
  }

  // POST /memory/kv
  if (parts[1] === 'kv' && !parts[2] && method === 'POST') {
    if (!memory) return noMemory()
    const body = await parseBody(req)
    if (!body?.key) {
      sendJSON(res, 400, { error: 'key is required' })
      return true
    }
    await memory.kv_set(body.key, body.value)
    sendJSON(res, 200, { ok: true })
    return true
  }

  // DELETE /memory/kv/:key
  if (parts[1] === 'kv' && parts[2] && method === 'DELETE') {
    if (!memory) return noMemory()
    await memory.kv_del(decodeURIComponent(parts[2]))
    sendJSON(res, 200, { ok: true })
    return true
  }


  // GET /memory/session/:id/conversation
  if (parts[1] === 'session' && parts[3] === 'conversation' && method === 'GET') {
    if (!memory) return noMemory()
    if (!memory.getConversationWithThinking) {
      sendJSON(res, 501, { error: 'archive not available' })
      return true
    }
    const limit = parseInt(url.searchParams.get('limit') ?? '50', 10)
    sendJSON(res, 200, memory.getConversationWithThinking(parts[2], limit))
    return true
  }

  // GET /memory/session/:id/export
  if (parts[1] === 'session' && parts[3] === 'export' && method === 'GET') {
    if (!memory) return noMemory()
    if (!memory.exportSession) {
      sendJSON(res, 501, { error: 'archive not available' })
      return true
    }
    const exported = memory.exportSession(parts[2])
    sendJSON(res, 200, JSON.parse(exported))
    return true
  }


  // GET /memory/ref/:refString  — resolve a compact ref like S0#M1.B0.P2
  if (parts[1] === 'ref' && parts[2] && method === 'GET') {
    if (!memory) return noMemory()
    if (!memory.resolveRef) {
      sendJSON(res, 501, { error: 'session index not available' })
      return true
    }
    try {
      const refStr = decodeURIComponent(parts[2])
      const entries = memory.resolveRef(refStr)
      if (entries.length === 0) {
        sendJSON(res, 404, { error: 'ref not found', ref: refStr })
        return true
      }
      sendJSON(res, 200, { ref: refStr, entries })
    } catch (err) {
      sendJSON(res, 400, { error: String(err) })
    }
    return true
  }

  // GET /memory/index/search?q=...&limit=N  — global cross-session FTS search
  if (parts[1] === 'index' && parts[2] === 'search' && !parts[3] && method === 'GET') {
    if (!memory) return noMemory()
    if (!memory.searchIndex) {
      sendJSON(res, 501, { error: 'session index not available' })
      return true
    }
    const q = url.searchParams.get('q') ?? url.searchParams.get('query') ?? ''
    const limit = parseInt(url.searchParams.get('limit') ?? '10', 10)
    sendJSON(res, 200, memory.searchIndex(q, { limit }))
    return true
  }

  // GET /memory/index/:labelOrSessionId/search?q=...&limit=20
  if (parts[1] === 'index' && parts[3] === 'search' && method === 'GET') {
    if (!memory) return noMemory()
    if (!memory.searchIndex) {
      sendJSON(res, 501, { error: 'session index not available' })
      return true
    }
    const q = url.searchParams.get('q') || url.searchParams.get('query') || ''
    const limit = parseInt(url.searchParams.get('limit') ?? '20', 10)
    const labelOrId = parts[2]
    const opts = labelOrId.startsWith('S')
      ? { label: labelOrId, limit }
      : { sessionId: labelOrId, limit }
    sendJSON(res, 200, memory.searchIndex(q, opts))
    return true
  }

  // GET /memory/index/:labelOrSessionId/stats
  if (parts[1] === 'index' && parts[3] === 'stats' && method === 'GET') {
    if (!memory) return noMemory()
    if (!memory.indexStats) {
      sendJSON(res, 501, { error: 'session index not available' })
      return true
    }
    const stats = memory.indexStats(parts[2])
    if (!stats) {
      sendJSON(res, 404, { error: 'session not indexed' })
      return true
    }
    sendJSON(res, 200, stats)
    return true
  }

  // POST /memory/index/:sessionId  — trigger on-demand full index
  if (parts[1] === 'index' && parts[2] && !parts[3] && method === 'POST') {
    if (!memory) return noMemory()
    if (!memory.indexSession) {
      sendJSON(res, 501, { error: 'session index not available' })
      return true
    }
    // Get the session history from the session manager
    const session = daemon.sessions?.get(parts[2])
    if (!session) {
      sendJSON(res, 404, { error: 'session not found' })
      return true
    }
    const label = memory.indexSession(parts[2], session.history)
    const stats = memory.indexStats?.(label)
    sendJSON(res, 200, { ok: true, label, stats })
    return true
  }


  // POST /memory/universal-search
  if (parts[1] === 'universal-search' && method === 'POST') {
    if (!memory) return noMemory()
    const body = await parseBody(req)
    const results = await memory.universalSearch(body?.query ?? '', {
      includeMemories: body?.includeMemories,
      includeArchives: body?.includeArchives,
      limit: body?.limit,
    })
    sendJSON(res, 200, results)
    return true
  }


  // DELETE /memory/:id
  if (parts[1] && !parts[2] && method === 'DELETE') {
    if (!memory) return noMemory()
    if (!memory.delete) {
      sendJSON(res, 501, { error: 'delete not available' })
      return true
    }
    const deleted = await memory.delete(parts[1])
    if (!deleted) {
      sendJSON(res, 404, { error: 'not_found' })
      return true
    }
    sendJSON(res, 200, { ok: true })
    return true
  }


  // POST /memory/store
  if (parts[1] === 'store' && method === 'POST') {
    const body = await parseBody(req)
    if (!memory) return noMemory()
    // Merge user-supplied tags + key from top-level fields (MCP gateway sends them
    // as top-level, not nested under metadata). Preserve any existing metadata fields
    // but never silently discard caller-specified tags.
    const userTags: string[] = body?.tags || body?.metadata?.tags || ['cli']
    const metadata: Record<string, unknown> = {
      ...(body?.metadata || {}),
      tags: userTags,
      ...(body?.key ? { key: body.key } : {}),
    }
    const storeEntry: Record<string, unknown> = {
      type: body?.type || 'fact',
      content: body?.content || body?.note || '',
      metadata,
      sessionId: body?.metadata?.sessionId || body?.sessionId,
    }
    // Optional importance (0-10) and pinned flag
    if (body?.importance !== undefined) storeEntry.importance = Number(body.importance)
    if (body?.pinned !== undefined) storeEntry.pinned = Boolean(body.pinned)
    const id = await memory.store(storeEntry as any)
    sendJSON(res, 200, { ok: true, id })
    return true
  }

  // POST /memory/:id/pin
  if (parts[2] === 'pin' && method === 'POST') {
    if (!memory) return noMemory()
    if (!memory.pin) {
      sendJSON(res, 501, { error: 'pin not available' })
      return true
    }
    const pinned = await memory.pin(parts[1])
    if (!pinned) {
      sendJSON(res, 404, { error: 'not_found' })
      return true
    }
    sendJSON(res, 200, { ok: true, pinned: true })
    return true
  }

  // POST /memory/:id/unpin
  if (parts[2] === 'unpin' && method === 'POST') {
    if (!memory) return noMemory()
    if (!memory.unpin) {
      sendJSON(res, 501, { error: 'unpin not available' })
      return true
    }
    const unpinned = await memory.unpin(parts[1])
    if (!unpinned) {
      sendJSON(res, 404, { error: 'not_found' })
      return true
    }
    sendJSON(res, 200, { ok: true, pinned: false })
    return true
  }

  // POST /memory/:id/invalidate
  if (parts[2] === 'invalidate' && method === 'POST') {
    if (!memory) return noMemory()
    if (!memory.invalidate) {
      sendJSON(res, 501, { error: 'invalidate not available' })
      return true
    }
    const body = await parseBody(req)
    const ok = await memory.invalidate(parts[1], body?.reason)
    if (!ok) {
      sendJSON(res, 404, { error: 'not_found' })
      return true
    }
    sendJSON(res, 200, { ok: true, invalidated: true })
    return true
  }

  // POST /memory/:id/supersede
  if (parts[2] === 'supersede' && method === 'POST') {
    if (!memory) return noMemory()
    if (!memory.supersede) {
      sendJSON(res, 501, { error: 'supersede not available' })
      return true
    }
    const body = await parseBody(req)
    if (!body?.content) {
      sendJSON(res, 400, { error: 'content is required' })
      return true
    }
    const newId = await memory.supersede(parts[1], body.content, body.metadata)
    sendJSON(res, 200, { ok: true, oldId: parts[1], newId })
    return true
  }

  // GET /memory/search
  if (parts[1] === 'search' && method === 'GET') {
    const query = url.searchParams.get('q') || url.searchParams.get('query') || ''
    const limit = parseInt(url.searchParams.get('limit') || '5', 10)
    if (!memory) return noMemory()

    // Build search opts from query params
    const searchOpts: Record<string, unknown> = { limit }
    const timeAfter = url.searchParams.get('time_after')
    const timeBefore = url.searchParams.get('time_before')
    const minImportance = url.searchParams.get('min_importance')
    const pinnedOnly = url.searchParams.get('pinned_only')
    const validOnly = url.searchParams.get('valid_only')
    if (timeAfter) searchOpts.timeAfter = new Date(timeAfter)
    if (timeBefore) searchOpts.timeBefore = new Date(timeBefore)
    if (minImportance) searchOpts.minImportance = parseFloat(minImportance)
    if (pinnedOnly === 'true') searchOpts.pinnedOnly = true
    if (validOnly !== null) searchOpts.validOnly = validOnly !== 'false'

    const results = await memory.search(query, searchOpts as any)
    sendJSON(res, 200, results.map((r: { entry: any, score: number, confidence?: string }) => ({
      entry: r.entry,
      score: r.score,
      confidence: r.confidence,
    })))
    return true
  }

  // GET /memory/recent
  if (parts[1] === 'recent' && method === 'GET') {
    const limit = parseInt(url.searchParams.get('limit') || '10', 10)
    if (!memory) return noMemory()
    const entries = await memory.getRecent(limit)
    sendJSON(res, 200, entries)
    return true
  }

  return false
}
