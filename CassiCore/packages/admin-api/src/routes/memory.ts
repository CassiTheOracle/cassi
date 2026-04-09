import type { ILogger } from '../../types/interfaces.js'
import { MnemicField } from '../intelligence/mnemic-field/index.js'
import { migrateMemoryAndArchives, migrateMemoryOnly } from '../intelligence/mnemic-field/migrate-memory.js'
import { getEmbeddingService } from '../intelligence/embeddings/embedding-service.js'
import { getDataDir } from '../utils/paths.js'
import fs from 'node:fs'
import path from 'node:path'
import type http from 'node:http'

export interface MemoryRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  parts: string[]
}

let mnemicField: MnemicField | undefined
const activeMigrationLoops = new Map<string, NodeJS.Timeout>()

function getMnemicField(logger: ILogger, daemon?: any): MnemicField {
  if (mnemicField) return mnemicField
  const dbPath = path.join(getDataDir(), 'mnemic-field.db')
  mnemicField = new MnemicField(logger, dbPath)
  if (daemon) (daemon as any).__mnemicField = mnemicField
  return mnemicField
}

function scheduleMigrationJob(jobId: string, useLocalEmbeddings: boolean, logger: ILogger, daemon?: any): void {
  if (activeMigrationLoops.has(jobId)) return
  const timer = setTimeout(async () => {
    activeMigrationLoops.delete(jobId)
    try {
      const field = getMnemicField(logger, daemon)
      const job = field.getMigrationJob(jobId)
      if (!job || job.status === 'completed' || job.status === 'failed') return
      const updated = await field.runMigrationJob(jobId, null, {
        embeddingProvider: useLocalEmbeddings ? async (text: string) => {
          const svc = getEmbeddingService(logger)
          return svc.available ? await svc.embed(text, 'document') : null
        } : undefined,
      })
      if (updated.status === 'paused') {
        scheduleMigrationJob(jobId, useLocalEmbeddings, logger, daemon)
      }
    } catch {
      // failure state recorded in job record
    }
  }, 50)
  activeMigrationLoops.set(jobId, timer)
}

export async function handleMemoryRoutes(
  deps: MemoryRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, url, parts } = deps

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

  // POST /memory/mnemic/migrate
  if (parts[1] === 'mnemic' && parts[2] === 'migrate' && !parts[3] && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const field = getMnemicField(logger, daemon)
      const sourceDbPath = path.join(getDataDir(), 'memory.db')
      const job = field.createMigrationJob({
        sourceDbPath,
        migrateArchives: !!body?.migrateArchives,
        includeArchived: !!body?.includeArchived,
        inferSynapses: body?.inferSynapses !== false,
        enableMicroChunking: body?.enableMicroChunking !== false,
        useLocalEmbeddings: !!body?.useLocalEmbeddings,
        memoryLimit: typeof body?.limit === 'number' ? body.limit : undefined,
        archiveLimit: typeof body?.archiveLimit === 'number' ? body.archiveLimit : undefined,
        archiveLinkLimit: typeof body?.archiveLinkLimit === 'number' ? body.archiveLinkLimit : undefined,
        microChunkTokenTarget: typeof body?.microChunkTokenTarget === 'number' ? body.microChunkTokenTarget : undefined,
      })

      scheduleMigrationJob(job.id, job.useLocalEmbeddings, logger, daemon)

      sendJSON(res, 202, { ok: true, job })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/migrate/resume/:jobId
  if (parts[1] === 'mnemic' && parts[2] === 'migrate' && parts[3] === 'resume' && parts[4] && method === 'POST') {
    try {
      const field = getMnemicField(logger, daemon)
      const job = field.getMigrationJob(parts[4])
      if (!job) {
        sendJSON(res, 404, { error: 'job not found' })
        return true
      }
      scheduleMigrationJob(job.id, job.useLocalEmbeddings, logger, daemon)
      sendJSON(res, 202, { ok: true, jobId: job.id })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/mnemic/migrate/jobs
  if (parts[1] === 'mnemic' && parts[2] === 'migrate' && parts[3] === 'jobs' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      sendJSON(res, 200, { ok: true, jobs: field.listMigrationJobs() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/mnemic/migrate/job/:jobId
  if (parts[1] === 'mnemic' && parts[2] === 'migrate' && parts[3] === 'job' && parts[4] && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const job = field.getMigrationJob(parts[4])
      if (!job) {
        sendJSON(res, 404, { error: 'job not found' })
        return true
      }
      sendJSON(res, 200, { ok: true, job })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/mnemic/nuclei
  if (parts[1] === 'mnemic' && parts[2] === 'nuclei' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      sendJSON(res, 200, { ok: true, nuclei: field.listNuclei() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/mnemic/abstractions
  if (parts[1] === 'mnemic' && parts[2] === 'abstractions' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      sendJSON(res, 200, { ok: true, abstractions: field.listAbstractions() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/mnemic/stats
  if (parts[1] === 'mnemic' && parts[2] === 'stats' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      sendJSON(res, 200, { ok: true, stats: field.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/reset
  if (parts[1] === 'mnemic' && parts[2] === 'reset' && method === 'POST') {
    try {
      const dbPath = path.join(getDataDir(), 'mnemic-field.db')
      if (mnemicField) {
        mnemicField.close()
        mnemicField = undefined
      }
      if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath)
      const field = getMnemicField(logger, daemon)
      sendJSON(res, 200, { ok: true, stats: field.stats(), path: dbPath })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/consolidate
  if (parts[1] === 'mnemic' && parts[2] === 'consolidate' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const field = getMnemicField(logger, daemon)
      const result = field.consolidate({
        skipRadiance: !!body?.skipRadiance,
        skipDrift: !!body?.skipDrift,
        skipNuclei: !!body?.skipNuclei,
        skipAbstractions: !!body?.skipAbstractions,
        skipPruning: !!body?.skipPruning,
        pruneKeepCount: typeof body?.pruneKeepCount === 'number' ? body.pruneKeepCount : undefined,
        nucleiMinClusterSize: typeof body?.nucleiMinClusterSize === 'number' ? body.nucleiMinClusterSize : undefined,
        nucleiEpsilon: typeof body?.nucleiEpsilon === 'number' ? body.nucleiEpsilon : undefined,
        abstractionMinMembers: typeof body?.abstractionMinMembers === 'number' ? body.abstractionMinMembers : undefined,
        abstractionMinPotentiation: typeof body?.abstractionMinPotentiation === 'number' ? body.abstractionMinPotentiation : undefined,
      })
      sendJSON(res, 200, { ok: true, result, stats: field.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/backfill
  if (parts[1] === 'mnemic' && parts[2] === 'backfill' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const field = getMnemicField(logger, daemon)
      const result = await field.backfillEmbeddings(typeof body?.limit === 'number' ? body.limit : 1000)
      sendJSON(res, 200, { ok: true, result, stats: field.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/backfill-filaments
  if (parts[1] === 'mnemic' && parts[2] === 'backfill-filaments' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const field = getMnemicField(logger, daemon)
      const result = await field.backfillFilaments(typeof body?.limit === 'number' ? body.limit : 100)
      sendJSON(res, 200, { ok: true, result, stats: field.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/mnemic/tensions
  if (parts[1] === 'mnemic' && parts[2] === 'tensions' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const minPotentiation = url.searchParams.get('minPotentiation')
      const limit = url.searchParams.get('limit')
      const report = field.tensionReport(
        minPotentiation ? Number(minPotentiation) : 0.3,
        limit ? Number(limit) : 10,
      )
      sendJSON(res, 200, { ok: true, report })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/kindle
  if (parts[1] === 'mnemic' && parts[2] === 'kindle' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const field = getMnemicField(logger, daemon)
      const result = field.kindle(null, typeof body?.query === 'string' ? body.query : null, {
        complexity: body?.complexity,
        maxSeeds: typeof body?.maxSeeds === 'number' ? body.maxSeeds : undefined,
        maxLuminalSize: typeof body?.maxLuminalSize === 'number' ? body.maxLuminalSize : undefined,
      })
      sendJSON(res, 200, {
        ok: true,
        luminal: {
          ...result,
          engrams: result.engrams.map(e => ({
            id: e.engram.id,
            nodeType: e.engram.nodeType,
            charge: e.charge,
            content: e.engram.content.slice(0, 180),
          })),
        },
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/enrich — Mnemic Field retrieval with first-person formatting
  if (parts[1] === 'enrich' && !parts[2] && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const query = typeof body?.query === 'string' ? body.query : ''
      if (!query.trim()) {
        sendJSON(res, 400, { error: 'query is required' })
        return true
      }

      const field = getMnemicField(logger, daemon)
      const complexity = body?.complexity ?? 'normal'
      const limit = typeof body?.limit === 'number' ? body.limit : 12

      const hits = field.retrieve(query, { complexity, limit })

      if (hits.length === 0) {
        sendJSON(res, 200, {
          ok: true,
          hasContext: false,
          markdown: `No relevant context found for: \`${query}\``,
        })
        return true
      }

      // Build first-person briefing
      const sections = buildEnrichmentBriefing(hits, query)

      sendJSON(res, 200, {
        ok: true,
        hasContext: true,
        markdown: sections.join('\n\n'),
        engramIds: hits.map(h => h.id),
        hitCount: hits.length,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/field/feedback — Record spikes for engram feedback
  if (parts[1] === 'field' && parts[2] === 'feedback' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const feedback = body?.feedback as Record<string, boolean> | undefined
      if (!feedback || typeof feedback !== 'object') {
        sendJSON(res, 400, { error: 'feedback map is required (engramId -> true/false)' })
        return true
      }

      const field = getMnemicField(logger, daemon)
      const taskContext = typeof body?.taskContext === 'string' ? body.taskContext : null
      let recorded = 0

      for (const [engramId, helpful] of Object.entries(feedback)) {
        try {
          field.spike({
            engramId,
            magnitude: helpful ? 1.0 : -0.3,
            outcome: helpful ? 'success' : 'failure',
            taskContext: taskContext || undefined,
          })
          recorded++
        } catch {
          // Engram may not exist — skip silently
        }
      }

      sendJSON(res, 200, { ok: true, recorded })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
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

// --- Enrichment Briefing Builder ---

/**
 * Build a first-person briefing from Mnemic Field retrieval hits.
 * Groups engrams by type and relevance, formats as natural language.
 */
interface BriefingHit {
  id: string
  content: string
  nodeType: string
  charge: number
  potentiation: number
  tags: string[]
  filamentExcerpt?: string
}

function excerpt(h: BriefingHit, maxLen: number): string {
  if (h.filamentExcerpt) return h.filamentExcerpt
  return h.content.length > maxLen ? h.content.slice(0, maxLen) + '...' : h.content
}

function buildEnrichmentBriefing(
  hits: BriefingHit[],
  query: string,
): string[] {
  const sections: string[] = []

  // Section 1: What I remember (facts, episodes, decisions, patterns)
  const memories = hits.filter(h =>
    ['fact', 'episode', 'decision', 'pattern', 'abstraction'].includes(h.nodeType),
  )
  if (memories.length > 0) {
    const lines = memories.map(h => `- ${excerpt(h, 400)}`)
    sections.push(`## What I remember\n\n${lines.join('\n\n')}`)
  }

  // Section 2: Decisions I've made
  const decisions = hits.filter(h => h.nodeType === 'decision')
  if (decisions.length > 0) {
    const lines = decisions.map(h => `- ${excerpt(h, 300)}`)
    sections.push(`## Decisions I've made\n\n${lines.join('\n')}`)
  }

  // Section 3: Watch out for (contradictions, outcomes, failures)
  const warnings = hits.filter(h =>
    ['outcome', 'pattern'].includes(h.nodeType) &&
    (h.content.toLowerCase().includes('fail') ||
     h.content.toLowerCase().includes('error') ||
     h.content.toLowerCase().includes('contradict') ||
     h.content.toLowerCase().includes('watch out')),
  )
  if (warnings.length > 0) {
    const lines = warnings.map(h => `- ${excerpt(h, 300)}`)
    sections.push(`## Things to watch out for\n\n${lines.join('\n')}`)
  }

  // Section 4: Connected work (files, tools, sessions)
  const connections = hits.filter(h =>
    ['file', 'tool', 'session', 'source_file', 'changeset'].includes(h.nodeType),
  )
  if (connections.length > 0) {
    const lines = connections.map(h => `- ${excerpt(h, 250)}`)
    sections.push(`## This connects to\n\n${lines.join('\n')}`)
  }

  // Fallback: if nothing categorized well, show everything
  if (sections.length === 0) {
    const lines = hits.slice(0, 8).map(h => `- ${excerpt(h, 300)}`)
    sections.push(`## Context for "${query}"\n\n${lines.join('\n\n')}`)
  }

  return sections
}
