import type { ILogger } from '../../types/interfaces.js'
import { MnemicField } from '../intelligence/mnemic-field/index.js'
import { migrateMemoryAndArchives, migrateMemoryOnly } from '../intelligence/mnemic-field/migrate-memory.js'
import { getEmbeddingService } from '../intelligence/embeddings/embedding-service.js'
import { getDataDir } from '../utils/paths.js'
import type { SelfModelField } from '../intelligence/mnemic-field/self-model/self-model-field.js'
import type { InterFieldBridge } from '../intelligence/mnemic-field/self-model/inter-field-bridge.js'
import {
  findNextUnannotated,
  findByName,
  annotateEngram,
  skipEngram,
  countUnannotated,
  buildInstruction,
  type AnnotationResponse,
  type AnnotationCandidate,
} from '../intelligence/mnemic-field/self-model/annotation.js'
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
  const daemonField = (daemon?.intelligence as any)?.__mnemicField as MnemicField | undefined
  if (daemonField) return daemonField
  if (mnemicField) return mnemicField
  const dbPath = path.join(getDataDir(), 'mnemic-field.db')
  mnemicField = new MnemicField(logger, dbPath)
  mnemicField.enableNeuralKindling()
  if (daemon) (daemon as any).__mnemicField = mnemicField
  return mnemicField
}


function getSelfModelField(daemon: any): SelfModelField | null {
  return (daemon as any).__selfModelField ?? (daemon?.intelligence as any)?.__selfModelField ?? null
}

function getKnowledgeField(daemon: any): any | null {
  return (daemon as any).__knowledgeField ?? (daemon?.intelligence as any)?.__knowledgeField ?? null
}

function requireKnowledgeField(
  daemon: any,
  res: http.ServerResponse,
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void,
): any | null {
  const kf = getKnowledgeField(daemon)
  if (!kf) sendJSON(res, 503, { error: 'Knowledge Field not available' })
  return kf
}

function getInterFieldBridge(daemon: any): InterFieldBridge | null {
  return (daemon as any).__interFieldBridge ?? (daemon?.intelligence as any)?.__interFieldBridge ?? null
}

/** Unwrap self-model or send 503; returns null if unavailable. */
function requireSelfModel(
  daemon: any,
  res: http.ServerResponse,
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void,
): SelfModelField | null {
  const smf = getSelfModelField(daemon)
  if (!smf) sendJSON(res, 503, { error: 'Self-Model Field not available' })
  return smf
}

/** Unwrap bridge or send 503; returns null if unavailable. */
function requireBridge(
  daemon: any,
  res: http.ServerResponse,
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void,
): InterFieldBridge | null {
  const bridge = getInterFieldBridge(daemon)
  if (!bridge) sendJSON(res, 503, { error: 'InterFieldBridge not available' })
  return bridge
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

  // GET /memory/stats — mnemic field statistics
  if (parts[1] === 'stats' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      sendJSON(res, 200, { ok: true, stats: field.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/by-type/:nodeType — list engrams by node type
  if (parts[1] === 'by-type' && parts[2] && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const limit = parseInt(url.searchParams.get('limit') ?? '50', 10)
      const engrams = field.listByType(parts[2], limit)
      sendJSON(res, 200, {
        ok: true,
        nodeType: parts[2],
        engrams: engrams.map(e => ({
          id: e.id, nodeType: e.nodeType, content: (e.content || '').slice(0, 500),
          potentiation: e.potentiation, tags: e.tags,
          provenance: e.provenance, createdAt: e.createdAt,
        })),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/popular — top engrams by potentiation
  if (parts[1] === 'popular' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const limit = parseInt(url.searchParams.get('limit') ?? '20', 10)
      const engrams = field.listPopular(limit)
      sendJSON(res, 200, {
        ok: true,
        engrams: engrams.map(e => ({
          id: e.id, nodeType: e.nodeType, content: (e.content || '').slice(0, 500),
          potentiation: e.potentiation, tags: e.tags,
          provenance: e.provenance, createdAt: e.createdAt,
        })),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }


  // GET /memory/nuclei — list nuclei
  if (parts[1] === 'nuclei' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      sendJSON(res, 200, { ok: true, nuclei: field.listNuclei() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/nucleus/:id/distinctiveness — per-member contrastive extraction results
  if (parts[1] === 'nucleus' && parts[3] === 'distinctiveness' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const nucleusId = parts[2]
      const nucleus = field.getNucleus(nucleusId)
      if (!nucleus) {
        sendJSON(res, 404, { error: 'Nucleus not found' })
        return true
      }
      const members = field.getEngramsByCluster(nucleusId)
      const membersOut = members.map(m => ({
        id: m.id,
        content: m.content?.slice(0, 200),
        distinctiveness: (m.metadata as Record<string, unknown> | undefined)?.distinctiveness ?? null,
      }))
      sendJSON(res, 200, {
        ok: true,
        nucleus,
        members: membersOut,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/abstractions — list abstractions
  if (parts[1] === 'abstractions' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      sendJSON(res, 200, { ok: true, abstractions: field.listAbstractions() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/tensions — tension report
  if (parts[1] === 'tensions' && method === 'GET') {
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

  // POST /memory/graph-search — typed graph traversal from startId
  if (parts[1] === 'graph-search' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const field = getMnemicField(logger, daemon)
      const startId = typeof body?.startId === 'string' ? body.startId : ''
      if (!startId) { sendJSON(res, 400, { error: 'startId required' }); return true }
      const maxDepth = Math.min(body?.maxDepth ?? 3, 5)
      const edgeTypes: string[] | undefined = Array.isArray(body?.edgeTypes) ? body.edgeTypes : undefined

      const visited = new Set<string>()
      const queue: Array<{ id: string; depth: number }> = [{ id: startId, depth: 0 }]
      const nodes: Array<{ id: string; depth: number; nodeType: string; content: string }> = []
      const edges: Array<{ sourceId: string; targetId: string; edgeType: string }> = []

      while (queue.length > 0) {
        const { id, depth } = queue.shift()!
        if (visited.has(id) || depth > maxDepth) continue
        visited.add(id)

        const engram = field.get(id)
        if (engram) {
          nodes.push({
            id: engram.id,
            depth,
            nodeType: engram.nodeType,
            content: (engram.content || '').slice(0, 300),
          })
        }

        if (depth < maxDepth) {
          const outSynapses = field.neighbors(id)?.synapses ?? []
          for (const s of outSynapses) {
            if (edgeTypes && !edgeTypes.includes(s.edgeType)) continue
            const neighborId = s.sourceId === id ? s.targetId : s.sourceId
            if (!visited.has(neighborId)) {
              edges.push({ sourceId: s.sourceId, targetId: s.targetId, edgeType: s.edgeType })
              queue.push({ id: neighborId, depth: depth + 1 })
            }
          }
        }
      }
      sendJSON(res, 200, { ok: true, startId, maxDepth, nodes, edges, totalVisited: visited.size })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/universal-search — combined text search (alias)
  if (parts[1] === 'universal-search' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const query = url.searchParams.get('q') ?? url.searchParams.get('query') ?? ''
      const limit = parseInt(url.searchParams.get('limit') ?? '10', 10)
      const nodeType = url.searchParams.get('node_type') || undefined

      if (!query) {
        if (nodeType) {
          const engrams = field.listByType(nodeType, limit)
          sendJSON(res, 200, {
            ok: true, source: 'browse',
            hits: engrams.map(e => ({
              id: e.id, score: e.potentiation, nodeType: e.nodeType,
              content: (e.content || '').slice(0, 300),
              potentiation: e.potentiation, tags: e.tags,
              provenance: e.provenance, createdAt: e.createdAt,
            })),
          })
          return true
        }
        sendJSON(res, 400, { error: 'query required' }); return true
      }

      let textHits = field.searchText(query, limit * 2)
        .filter(r => r.engram.nodeType !== 'bridge')
      if (nodeType) textHits = textHits.filter(r => r.engram.nodeType === nodeType)
      textHits = textHits.slice(0, limit)
      sendJSON(res, 200, {
        ok: true, source: 'text',
        hits: textHits.map(r => ({
          id: r.engram.id, score: r.score, nodeType: r.engram.nodeType,
          content: (r.engram.content || '').slice(0, 300),
          potentiation: r.engram.potentiation, tags: r.engram.tags,
          provenance: r.engram.provenance, createdAt: r.engram.createdAt,
          metadata: r.engram.metadata ?? {},
        })),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/search — text search (alias)
  if (parts[1] === 'search' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const query = url.searchParams.get('q') ?? url.searchParams.get('query') ?? ''
      if (!query) { sendJSON(res, 400, { error: 'query required' }); return true }
      const limit = parseInt(url.searchParams.get('limit') ?? '10', 10)
      const nodeType = url.searchParams.get('node_type') || undefined

      const results = field.searchText(query, limit)
      let filtered = results.filter(r => r.engram.nodeType !== 'bridge')
      if (nodeType) filtered = filtered.filter(r => r.engram.nodeType === nodeType)

      sendJSON(res, 200, {
        ok: true,
        hits: filtered.map(r => ({
          id: r.engram.id, score: r.score, nodeType: r.engram.nodeType,
          content: (r.engram.content || '').slice(0, 300),
          potentiation: r.engram.potentiation, tags: r.engram.tags,
          provenance: r.engram.provenance, createdAt: r.engram.createdAt,
        })),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/engram/:id/synapses — must precede GET /memory/engram/:id
  if (parts[1] === 'engram' && parts[3] === 'synapses' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const edgeType = url.searchParams.get('edge_type') || undefined
      const direction = (url.searchParams.get('direction') || 'both') as 'in' | 'out' | 'both'
      const limit = parseInt(url.searchParams.get('limit') ?? '20', 10)

      const result: Array<{ sourceId: string; targetId: string; edgeType: string; weight: number }> = []
      if (direction === 'out' || direction === 'both') {
        const out = edgeType
          ? field.getTypedSynapses(parts[2], edgeType, 'out')
          : (field.neighbors(parts[2])?.synapses ?? []).filter(s => s.sourceId === parts[2])
        result.push(...out.slice(0, limit))
      }
      if (direction === 'in' || direction === 'both') {
        const incoming = edgeType
          ? field.getTypedSynapses(parts[2], edgeType, 'in')
          : (field.neighbors(parts[2])?.synapses ?? []).filter(s => s.targetId === parts[2])
        result.push(...incoming.slice(0, limit))
      }
      sendJSON(res, 200, { ok: true, engramId: parts[2], synapses: result.slice(0, limit) })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/engram/:id (alias)
  if (parts[1] === 'engram' && parts[2] && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const engram = field.get(parts[2])
      if (!engram) { sendJSON(res, 404, { error: 'engram not found' }); return true }
      const includeContent = url.searchParams.get('content') !== 'false'
      sendJSON(res, 200, {
        id: engram.id, nodeType: engram.nodeType,
        potentiation: engram.potentiation,
        content: includeContent ? engram.content.slice(0, 4000) : undefined,
        provenance: engram.provenance, tags: engram.tags,
        createdAt: engram.createdAt, metadata: engram.metadata,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/retrieve — full retrieve (alias, cache + embedding + kindle + rerank)
  if (parts[1] === 'retrieve' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const field = getMnemicField(logger, daemon)
      const query = typeof body?.query === 'string' ? body.query : ''
      if (!query) { sendJSON(res, 400, { error: 'query required' }); return true }
      const hits = await field.retrieve(query, {
        limit: typeof body?.limit === 'number' ? body.limit : undefined,
        complexity: body?.complexity,
        sessionId: typeof body?.sessionId === 'string' ? body.sessionId : undefined,
      })
      sendJSON(res, 200, { ok: true, hits: hits.map(h => ({ id: h.id, score: h.score, nodeType: h.nodeType, content: h.content || '' })) })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
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

  // GET /memory/mnemic/ann/status (deprecated — ANN replaced by FeatureIndex)
  if (parts[1] === 'mnemic' && parts[2] === 'ann' && parts[3] === 'status' && method === 'GET') {
    sendJSON(res, 200, { ok: true, ready: false, deprecated: true, message: 'ANN removed — using FeatureIndex' })
    return true
  }

  // POST /memory/mnemic/ann/initialize (deprecated — ANN replaced by FeatureIndex)
  if (parts[1] === 'mnemic' && parts[2] === 'ann' && parts[3] === 'initialize' && method === 'POST') {
    sendJSON(res, 200, { ok: true, ready: false, deprecated: true, message: 'ANN removed — using FeatureIndex' })
    return true
  }

  // POST /memory/mnemic/detect-hubs
  if (parts[1] === 'mnemic' && parts[2] === 'detect-hubs' && method === 'POST') {
    try {
      const field = getMnemicField(logger, daemon)
      const hubs = field.detectHubs()
      sendJSON(res, 200, { ok: true, hubCount: hubs.length, hubs: hubs.slice(0, 20) })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/ann/rebuild (deprecated — ANN replaced by FeatureIndex)
  if (parts[1] === 'mnemic' && parts[2] === 'ann' && parts[3] === 'rebuild' && method === 'POST') {
    sendJSON(res, 200, { ok: true, ready: false, deprecated: true, message: 'ANN removed — using FeatureIndex' })
    return true
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
      const result = await field.consolidate({
        skipRadiance: !!body?.skipRadiance,
        skipDrift: !!body?.skipDrift,
        skipCentripetalDrift: !!body?.skipCentripetalDrift,
        skipAngularDrift: !!body?.skipAngularDrift,
        skipContrastiveFeedback: !!body?.skipContrastiveFeedback,
        skipNuclei: !!body?.skipNuclei,
        skipAbstractions: !!body?.skipAbstractions,
        skipPruning: !!body?.skipPruning,
        skipGradients: !!body?.skipGradients,
        skipForwardTracePrune: !!body?.skipForwardTracePrune,
        skipDistinctiveness: !!body?.skipDistinctiveness,
        skipOrphanAssignment: !!body?.skipOrphanAssignment,
        skipDreaming: !!body?.skipDreaming,
        // V-field active organization (Phases 0-2)
        skipMergeOnOverlap: !!body?.skipMergeOnOverlap,
        mergeOnOverlapMinPotentiation: typeof body?.mergeOnOverlapMinPotentiation === 'number' ? body.mergeOnOverlapMinPotentiation : undefined,
        skipQualityBasedPruning: !!body?.skipQualityBasedPruning,
        qualityPruningMinScore: typeof body?.qualityPruningMinScore === 'number' ? body.qualityPruningMinScore : undefined,
        skipFeatureOverlapNuclei: !!body?.skipFeatureOverlapNuclei,
        featureOverlapNucleiMinMembers: typeof body?.featureOverlapNucleiMinMembers === 'number' ? body.featureOverlapNucleiMinMembers : undefined,
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

  // POST /memory/mnemic/attention — update global attention from active sessions
  if (parts[1] === 'mnemic' && parts[2] === 'attention' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const raw = body?.sessionEmbeddings
      if (!Array.isArray(raw)) {
        sendJSON(res, 400, { error: 'sessionEmbeddings must be an array of number arrays' })
        return true
      }
      const field = getMnemicField(logger, daemon)
      const sessionEmbeddings = raw
        .filter((arr: unknown) => Array.isArray(arr) && arr.every((n: unknown) => typeof n === 'number'))
        .map((arr: number[]) => new Float32Array(arr))
      field.updateActiveAttentionEmbeddings(sessionEmbeddings)
      sendJSON(res, 200, { ok: true, sessionCount: sessionEmbeddings.length })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/mnemic/spatial-attention — sector attention weights
  if (parts[1] === 'mnemic' && parts[2] === 'spatial-attention' && method === 'GET') {
    const field = getMnemicField(logger, daemon)
    const engine = field.getConsolidationEngine()
    const sectors = engine?.getSectorAttention?.() ?? null
    const globalAttention = engine?.getGlobalAttention?.() ?? null

    const sectorLabels = [
      { index: 0, label: 'N', range: '0°–30°' },
      { index: 1, label: 'NNE', range: '30°–60°' },
      { index: 2, label: 'ENE', range: '60°–90°' },
      { index: 3, label: 'E', range: '90°–120°' },
      { index: 4, label: 'ESE', range: '120°–150°' },
      { index: 5, label: 'SSE', range: '150°–180°' },
      { index: 6, label: 'S', range: '180°–210°' },
      { index: 7, label: 'SSW', range: '210°–240°' },
      { index: 8, label: 'WSW', range: '240°–270°' },
      { index: 9, label: 'W', range: '270°–300°' },
      { index: 10, label: 'WNW', range: '300°–330°' },
      { index: 11, label: 'NNW', range: '330°–360°' },
    ]

    const response: Record<string, unknown> = {
      available: sectors !== null || globalAttention !== null,
      mode: sectors ? 'sector' : 'global',
    }

    if (sectors) {
      response.sectors = sectorLabels.map((sl, i) => ({
        ...sl,
        weight: sectors[i] ?? 0,
      }))
    }

    if (globalAttention) {
      response.globalAttentionNorm = Math.sqrt(
        [...globalAttention].reduce((s, v) => s + v * v, 0),
      ).toFixed(4)
    }

    sendJSON(res, 200, response)
    return true
  }


  // POST /memory/mnemic/ingest/spatial-grid — ingest 3D spatial positions as engrams
  if (parts[1] === 'mnemic' && parts[2] === 'ingest' && parts[3] === 'spatial-grid' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const field = getMnemicField(logger, daemon)
      const density = typeof body?.density === 'number' ? body.density : 2
      const limit = typeof body?.limit === 'number' ? body.limit : undefined
      const source = typeof body?.source === 'string' ? body.source : 'trellis2-4b'
      const tags = Array.isArray(body?.tags) ? body.tags : undefined

      const result = await field.ingestSpatialGrid(density, { source, limit, tags })
      sendJSON(res, 200, { ok: true, ...result, stats: field.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/mnemic/cross-modal-synapses — list cross-modal text↔3D connections
  if (parts[1] === 'mnemic' && parts[2] === 'cross-modal-synapses' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const cortex = field.getCortex()
      const limitParam = new URL(req.url ?? '/', 'http://localhost').searchParams.get('limit')
      const limit = limitParam ? parseInt(limitParam, 10) : 50

      const synapses = cortex.getSynapsesByType('cross_modal', limit)

      const enriched = synapses.map(s => {
        const sourceEngram = cortex.getEngram(s.sourceId)
        const targetEngram = cortex.getEngram(s.targetId)
        return {
          sourceId: s.sourceId.slice(0, 12),
          targetId: s.targetId.slice(0, 12),
          weight: s.weight,
          sharedFeatures: (s.metadata as Record<string, unknown>)?.sharedFeatures ?? 0,
          sourceContent: sourceEngram?.content?.slice(0, 60) ?? '(unknown)',
          targetNodeType: targetEngram?.nodeType ?? '(unknown)',
          sourceVindex: (s.metadata as Record<string, unknown>)?.sourceVindex ?? 'default',
          targetVindex: (s.metadata as Record<string, unknown>)?.targetVindex ?? 'unknown',
        }
      })

      sendJSON(res, 200, {
        ok: true,
        total: synapses.length,
        synapses: enriched,
        stats: field.stats(),
      })
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

  // POST /memory/mnemic/backfill-all
  if (parts[1] === 'mnemic' && parts[2] === 'backfill-all' && method === 'POST') {
    try {
      const field = getMnemicField(logger, daemon)
      const result = await field.backfillAllEmbeddings()
      sendJSON(res, 200, { ok: true, result, stats: field.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/reproject
  if (parts[1] === 'mnemic' && parts[2] === 'reproject' && method === 'POST') {
    const field = getMnemicField(deps.logger, daemon)
    const startMs = Date.now()
    try {
      const count = await field.reprojectAllAsync()
      sendJSON(res, 200, { ok: true, count, durationMs: Date.now() - startMs })
    } catch (err) {
      sendJSON(res, 500, { ok: false, error: String(err) })
    }
    return true
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

  // POST /memory/mnemic/classify — batch classify all unlabeled engrams
  if (parts[1] === 'mnemic' && parts[2] === 'classify' && method === 'POST' && !parts[3]) {
    try {
      const field = getMnemicField(logger, daemon)
      const result = await field.classifyAll()
      sendJSON(res, 200, { ok: true, ...result, stats: field.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/classify-edges — classify + generate type-based synapses
  if (parts[1] === 'mnemic' && parts[2] === 'classify-edges' && method === 'POST') {
    try {
      const field = getMnemicField(logger, daemon)
      const classify = await field.classifyAll()
      const edges = await field.generateTypeSynapses()
      sendJSON(res, 200, { ok: true, ...classify, edges, stats: field.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/thalamus-backfill — temporal relinking + metadata enrichment
  if (parts[1] === 'mnemic' && parts[2] === 'thalamus-backfill' && method === 'POST') {
    try {
      const field = getMnemicField(logger, daemon)
      const result = await field.thalamusBackfill()
      sendJSON(res, 200, { ok: true, ...result, stats: field.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/chains
  if (parts[1] === 'mnemic' && parts[2] === 'chains' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const field = getMnemicField(logger, daemon)
      const engramIds = Array.isArray(body?.engramIds) ? body.engramIds : undefined
      const chains = field.getChains(engramIds)
      sendJSON(res, 200, { ok: true, chains, count: chains.length })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/tier3
  if (parts[1] === 'mnemic' && parts[2] === 'tier3' && method === 'POST') {
    try {
      const field = getMnemicField(logger, daemon)
      const result = await field.runTier3Analysis()
      sendJSON(res, 200, { ok: true, result })
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

  // POST /memory/mnemic/retrieve — full retrieve path (cache + embedding + kindle + rerank).
  // Mirrors kindle's payload but exercises the public retrieve() API, including the
  // Foreshadow observation hook.
  if (parts[1] === 'mnemic' && parts[2] === 'retrieve' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const field = getMnemicField(logger, daemon)
      const query = typeof body?.query === 'string' ? body.query : ''
      if (!query) { sendJSON(res, 400, { error: 'query required' }); return true }
      const hits = await field.retrieve(query, {
        limit: typeof body?.limit === 'number' ? body.limit : undefined,
        complexity: body?.complexity,
        sessionId: typeof body?.sessionId === 'string' ? body.sessionId : undefined,
        shadow: body?.shadow === true,
      })
      sendJSON(res, 200, { ok: true, hits: hits.map(h => ({ id: h.id, score: h.score, nodeType: h.nodeType, content: h.content || '' })) })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/harmony — shadow observation + harmony metric (Phase 0-4)
  if (parts[1] === 'harmony' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const harmony = field.getHarmony()
      const shadowCtx = field.buildShadowContext()
      sendJSON(res, 200, {
        ok: true,
        harmony,
        harmonyLabel: harmony < 0.3 ? 'Yang-dominated' : harmony > 0.7 ? 'Yin-dominated' : 'balanced',
        shadowContext: shadowCtx,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/broadcast — global workspace broadcast state
  if (parts[1] === 'broadcast' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const primed = field.getPrimedNuclei()
      const allNuclei = field.listNuclei()
      const primedDetails = primed.map(p => {
        const nucleus = allNuclei.find(n => n.id === p.nucleusId)
        return {
          nucleusId: p.nucleusId,
          label: nucleus?.label ?? 'unknown',
          resonance: p.resonance,
          remainingRetrievals: p.remainingRetrievals,
        }
      })

      sendJSON(res, 200, {
        ok: true,
        primedNuclei: primedDetails,
        primedCount: primedDetails.length,
        totalNuclei: allNuclei.length,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/fractal — fractal dimension of cluster hierarchy
  if (parts[1] === 'fractal' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const nuclei = field.listNuclei()
      const depth0 = nuclei.filter(n => n.depth === 0).length
      const depth2 = nuclei.filter(n => n.depth === 2).length
      sendJSON(res, 200, {
        ok: true,
        fractalDimension: field.getFractalDimension(),
        depth0Nuclei: depth0,
        depth2SuperNuclei: depth2,
        totalNuclei: nuclei.length,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/hubs — field-level hub engrams
  if (parts[1] === 'hubs' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const limit = parseInt(url.searchParams.get('limit') ?? '20', 10)
      sendJSON(res, 200, { ok: true, hubs: field.getHubs(limit) })
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

  // GET /memory/mnemic/engram/:id/synapses — must precede generic engram GET
  if (parts[1] === 'mnemic' && parts[2] === 'engram' && parts[4] === 'synapses' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const edgeType = url.searchParams.get('edge_type') || undefined
      const direction = (url.searchParams.get('direction') || 'both') as 'in' | 'out' | 'both'
      const limit = parseInt(url.searchParams.get('limit') ?? '20', 10)

      const result: Array<{ sourceId: string; targetId: string; edgeType: string; weight: number }> = []
      if (direction === 'out' || direction === 'both') {
        const out = edgeType
          ? field.getTypedSynapses(parts[3], edgeType, 'out')
          : (field.neighbors(parts[3])?.synapses ?? []).filter(s => s.sourceId === parts[3])
        result.push(...out.slice(0, limit))
      }
      if (direction === 'in' || direction === 'both') {
        const incoming = edgeType
          ? field.getTypedSynapses(parts[3], edgeType, 'in')
          : (field.neighbors(parts[3])?.synapses ?? []).filter(s => s.targetId === parts[3])
        result.push(...incoming.slice(0, limit))
      }
      sendJSON(res, 200, { ok: true, engramId: parts[3], synapses: result.slice(0, limit) })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/mnemic/engram/:id
  if (parts[1] === 'mnemic' && parts[2] === 'engram' && parts[3] && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const engram = field.get(parts[3])
      if (!engram) { sendJSON(res, 404, { error: 'engram not found' }); return true }
      const includeContent = url.searchParams.get('content') !== 'false'
      sendJSON(res, 200, {
        id: engram.id,
        nodeType: engram.nodeType,
        potentiation: engram.potentiation,
        content: includeContent ? engram.content.slice(0, 4000) : undefined,
        provenance: engram.provenance,
        tags: engram.tags,
        createdAt: engram.createdAt,
        metadata: engram.metadata,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/mnemic/graph-search — typed graph traversal with depth limit
  if (parts[1] === 'mnemic' && parts[2] === 'graph-search' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const field = getMnemicField(logger, daemon)
      const startId = typeof body?.startId === 'string' ? body.startId : ''
      if (!startId) { sendJSON(res, 400, { error: 'startId required' }); return true }
      const maxDepth = Math.min(body?.maxDepth ?? 3, 5)
      const edgeTypes: string[] | undefined = Array.isArray(body?.edgeTypes) ? body.edgeTypes : undefined

      // BFS traversal
      const visited = new Set<string>()
      const queue: Array<{ id: string; depth: number }> = [{ id: startId, depth: 0 }]
      const nodes: Array<{ id: string; depth: number; nodeType: string; content: string }> = []
      const edges: Array<{ sourceId: string; targetId: string; edgeType: string }> = []

      while (queue.length > 0) {
        const { id, depth } = queue.shift()!
        if (visited.has(id) || depth > maxDepth) continue
        visited.add(id)

        const engram = field.get(id)
        if (engram) {
          nodes.push({
            id: engram.id,
            depth,
            nodeType: engram.nodeType,
            content: (engram.content || '').slice(0, 300),
          })
        }

        if (depth < maxDepth) {
          const outSynapses = field.neighbors(id)?.synapses ?? []
          for (const s of outSynapses) {
            if (edgeTypes && !edgeTypes.includes(s.edgeType)) continue
            const neighborId = s.sourceId === id ? s.targetId : s.sourceId
            if (!visited.has(neighborId)) {
              edges.push({ sourceId: s.sourceId, targetId: s.targetId, edgeType: s.edgeType })
              queue.push({ id: neighborId, depth: depth + 1 })
            }
          }
        }
      }
      sendJSON(res, 200, { ok: true, startId, maxDepth, nodes, edges, totalVisited: visited.size })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/mnemic/universal-search — combined text search with optional kindling
  if (parts[1] === 'mnemic' && parts[2] === 'universal-search' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const query = url.searchParams.get('q') ?? url.searchParams.get('query') ?? ''
      const limit = parseInt(url.searchParams.get('limit') ?? '10', 10)
      const nodeType = url.searchParams.get('node_type') || undefined

      // Allow empty query when node_type is set (browse by type)
      if (!query) {
        if (nodeType) {
          const engrams = field.listByType(nodeType, limit)
          sendJSON(res, 200, {
            ok: true,
            source: 'browse',
            hits: engrams.map(e => ({
              id: e.id, score: e.potentiation, nodeType: e.nodeType,
              content: (e.content || '').slice(0, 300),
              potentiation: e.potentiation, tags: e.tags,
              provenance: e.provenance, createdAt: e.createdAt,
            })),
          })
          return true
        }
        sendJSON(res, 400, { error: 'query required' }); return true
      }

      // Text search is fast and reliable; use it as the primary path.
      // Kindling is async and requires embedding service availability.
      let textHits = field.searchText(query, limit * 2)
        .filter(r => r.engram.nodeType !== 'bridge')
      if (nodeType) textHits = textHits.filter(r => r.engram.nodeType === nodeType)
      textHits = textHits.slice(0, limit)
      sendJSON(res, 200, {
        ok: true,
        source: 'text',
        hits: textHits.map(r => ({
          id: r.engram.id, score: r.score, nodeType: r.engram.nodeType,
          content: (r.engram.content || '').slice(0, 300),
          potentiation: r.engram.potentiation, tags: r.engram.tags,
          provenance: r.engram.provenance, createdAt: r.engram.createdAt,
          metadata: r.engram.metadata ?? {},
        })),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/mnemic/search — text-based search over engram content
  if (parts[1] === 'mnemic' && parts[2] === 'search' && method === 'GET') {
    try {
      const field = getMnemicField(logger, daemon)
      const query = url.searchParams.get('q') ?? url.searchParams.get('query') ?? ''
      if (!query) { sendJSON(res, 400, { error: 'query required' }); return true }
      const limit = parseInt(url.searchParams.get('limit') ?? '10', 10)
      const nodeType = url.searchParams.get('node_type') || undefined

      const results = field.searchText(query, limit)
      let filtered = results.filter(r => r.engram.nodeType !== 'bridge')
      if (nodeType) filtered = filtered.filter(r => r.engram.nodeType === nodeType)

      sendJSON(res, 200, {
        ok: true,
        hits: filtered.map(r => ({
          id: r.engram.id, score: r.score, nodeType: r.engram.nodeType,
          content: (r.engram.content || '').slice(0, 300),
          potentiation: r.engram.potentiation, tags: r.engram.tags,
          provenance: r.engram.provenance,
          createdAt: r.engram.createdAt,
        })),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // Self-Model Field routes
  // The self-model stores semantic understanding of the codebase architecture.

  // GET /memory/self-model/stats — self-model field statistics
  if (parts[1] === 'self-model' && parts[2] === 'stats' && !parts[3] && method === 'GET') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      sendJSON(res, 200, { ok: true, stats: smf.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/self-model/retrieve?query=...&limit=N — self-model retrieval via kindling
  if (parts[1] === 'self-model' && parts[2] === 'retrieve' && !parts[3] && method === 'GET') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const query = url.searchParams.get('query') ?? ''
      if (!query.trim()) {
        sendJSON(res, 400, { error: 'query parameter is required' })
        return true
      }
      const limit = parseInt(url.searchParams.get('limit') ?? '10', 10)
      const hits = await smf.retrieve(query, { limit })
      sendJSON(res, 200, { ok: true, hits: hits.map(h => ({
        id: h.id, nodeType: h.nodeType, content: h.content,
        score: h.score, charge: h.charge, tags: h.tags,
        metadata: h.metadata,
      }))})
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/self-model/modules?domain=...&limit=N — list module engrams
  if (parts[1] === 'self-model' && parts[2] === 'modules' && !parts[3] && method === 'GET') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const domain = url.searchParams.get('domain')
      const limit = parseInt(url.searchParams.get('limit') ?? '50', 10)
      const modules = domain
        ? smf.findModulesByDomain(domain, limit)
        : smf.list('module', limit)
      sendJSON(res, 200, { ok: true, modules })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/self-model/weaknesses?severity=...&limit=N — list weakness engrams
  if (parts[1] === 'self-model' && parts[2] === 'weaknesses' && !parts[3] && method === 'GET') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const severity = url.searchParams.get('severity') as 'low' | 'medium' | 'high' | 'critical' | null
      const limit = parseInt(url.searchParams.get('limit') ?? '50', 10)
      const weaknesses = smf.findWeaknesses(severity ?? undefined, limit)
      sendJSON(res, 200, { ok: true, weaknesses })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/self-model/dependency-graph — module dependency graph
  if (parts[1] === 'self-model' && parts[2] === 'dependency-graph' && !parts[3] && method === 'GET') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const graph = smf.getDependencyGraph()
      sendJSON(res, 200, { ok: true, graph: graph.map(g => ({
        module: { id: g.module.id, content: g.module.content, metadata: g.module.metadata },
        dependsOn: g.dependsOn.map(d => ({ id: d.id, content: d.content, metadata: d.metadata })),
      }))})
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/self-model/cross-retrieve?query=...&limit=N&prefer=... — cross-field retrieval
  if (parts[1] === 'self-model' && parts[2] === 'cross-retrieve' && !parts[3] && method === 'GET') {
    const bridge = requireBridge(daemon, res, sendJSON)
    if (!bridge) return true
    try {
      const query = url.searchParams.get('query') ?? ''
      if (!query.trim()) {
        sendJSON(res, 400, { error: 'query parameter is required' })
        return true
      }
      const limit = parseInt(url.searchParams.get('limit') ?? '12', 10)
      const prefer = url.searchParams.get('prefer') as 'episodic' | 'self-model' | null
      const result = await bridge.crossRetrieve(query, { limit, preferField: prefer ?? undefined })
      sendJSON(res, 200, { ok: true, ...result, hits: result.hits.map(h => ({
        id: h.id, nodeType: h.nodeType, content: h.content,
        score: h.score, charge: h.charge, tags: h.tags,
        sourceField: h.sourceField, crossFieldBoosted: h.crossFieldBoosted,
        metadata: h.metadata,
      }))})
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/self-model/ingest — trigger self-model ingestion from GitNexus
  if (parts[1] === 'self-model' && parts[2] === 'ingest' && !parts[3] && method === 'POST') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const bridge = getInterFieldBridge(daemon)
      const { SelfModelIngestor } = await import('../intelligence/mnemic-field/self-model/ingestor.js')
      const ingestor = new SelfModelIngestor(smf, logger, process.cwd(), bridge ?? undefined)
      const result = await ingestor.ingest({
        minCommunitySize: body?.minCommunitySize ?? 5,
        weaknessThreshold: body?.weaknessThreshold ?? 0.6,
        updateExisting: body?.updateExisting ?? true,
      })

      let seeded = 0
      if (bridge) {
        seeded = bridge.seedEpisodicLinks()
      }

      sendJSON(res, 200, { ok: true, ...result, episodicLinksSeeded: seeded })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/self-model/portals — portal pair statistics
  if (parts[1] === 'self-model' && parts[2] === 'portals' && !parts[3] && method === 'GET') {
    const bridge = requireBridge(daemon, res, sendJSON)
    if (!bridge) return true
    try {
      sendJSON(res, 200, { ok: true, portals: bridge.getPortalStats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/self-model/store — store a new self-model engram
  if (parts[1] === 'self-model' && parts[2] === 'store' && !parts[3] && method === 'POST') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const nodeType = body?.nodeType
      const name = body?.name
      const description = body?.description ?? ''
      const metadata = body?.metadata ?? {}
      const tags = body?.tags ?? []

      if (!nodeType || !name) {
        sendJSON(res, 400, { error: 'nodeType and name are required' })
        return true
      }

      const engram = smf.store(nodeType, name, description, metadata, { tags })
      sendJSON(res, 200, { ok: true, engram: { id: engram.id, content: engram.content, nodeType: engram.nodeType, tags: engram.tags } })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // PATCH /memory/self-model/update — update an existing self-model engram
  if (parts[1] === 'self-model' && parts[2] === 'update' && !parts[3] && method === 'PATCH') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const id = body?.id
      if (!id) {
        sendJSON(res, 400, { error: 'id is required' })
        return true
      }

      const patch: Record<string, unknown> = {}
      if (body.content !== undefined) patch.content = body.content
      if (body.metadata !== undefined) patch.metadata = body.metadata
      if (body.tags !== undefined) patch.tags = body.tags

      const updated = await smf.update(id, patch)
      if (!updated) {
        sendJSON(res, 404, { error: 'Engram not found' })
        return true
      }

      sendJSON(res, 200, { ok: true, engram: { id: updated.id, content: updated.content, nodeType: updated.nodeType, tags: updated.tags } })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/self-model/link — create synapse between self-model engrams
  if (parts[1] === 'self-model' && parts[2] === 'link' && !parts[3] && method === 'POST') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const sourceId = body?.sourceId as string | undefined
      const targetId = body?.targetId as string | undefined
      const edgeType = (body?.edgeType as string) || 'implements'
      const weight = typeof body?.edgeWeight === 'number' ? body.edgeWeight : 1.0

      if (!sourceId || !targetId) {
        sendJSON(res, 400, { error: 'sourceId and targetId are required' })
        return true
      }

      const synapse = smf.connect(sourceId, targetId, edgeType as any, weight)

      sendJSON(res, 200, { ok: true, synapse })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/self-model/purge-deprecated — remove deprecated team/feature engrams
  if (parts[1] === 'self-model' && parts[2] === 'purge-deprecated' && !parts[3] && method === 'POST') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const modules: string[] = Array.isArray(body?.modules) && body.modules.length > 0
        ? body.modules
        : ['flux-team', 'triad-team']
      const dryRun = body?.dryRun !== false

      const all = smf.list(undefined, 10000)
      const candidates = all.filter(e => {
        const lowerContent = (e.content || '').toLowerCase()
        const lowerTags = (e.tags || []).map((t: string) => t.toLowerCase())
        return modules.some(m =>
          lowerContent.includes(m.toLowerCase()) ||
          lowerTags.some(t => t.includes(m.toLowerCase()))
        )
      })

      let purged = 0
      if (!dryRun) {
        for (const e of candidates) {
          if (smf.delete(e.id)) purged++
        }
      }

      sendJSON(res, 200, {
        ok: true,
        dryRun,
        candidatesFound: candidates.length,
        purged,
        modules,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/self-model/annotate — iterative annotation workflow
  if (parts[1] === 'self-model' && parts[2] === 'annotate' && !parts[3] && method === 'POST') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const engramId = body?.engramId as string | undefined
      const summary = body?.summary as string | undefined
      const skip = body?.skip as boolean | undefined
      const target = body?.target as string | undefined
      const force = body?.force as boolean | undefined

      // Store annotation if provided
      if (engramId && summary && summary.trim()) {
        await annotateEngram(smf, engramId, summary.trim())
        logger.info('Stored self-model annotation', { engramId, summaryLength: summary.length, force })
      }

      // Skip if requested
      if (engramId && skip) {
        await skipEngram(smf, engramId)
        logger.info('Skipped self-model annotation', { engramId })
      }

      // Targeted lookup: if target name provided, find matching engram
      let next: AnnotationCandidate | null = null
      if (target && !engramId) {
        next = findByName(smf, target)
        if (!next) {
          sendJSON(res, 404, {
            status: 'error',
            error: `No unannotated engram matching "${target}" found`,
          } as AnnotationResponse)
          return true
        }
      }

      // Find next unannotated (unless target was used)
      if (!next) {
        next = findNextUnannotated(smf)
      }
      const progress = countUnannotated(smf)

      if (!next) {
        sendJSON(res, 200, {
          status: 'complete',
          instruction: 'All Self-Model engrams have been reviewed. No more unannotated entries.',
          complete: { message: 'Annotation finished' },
          progress,
        } as AnnotationResponse)
        return true
      }

      const previousAction = engramId
        ? { engramId, action: skip ? 'skipped' : 'annotated' }
        : undefined

      sendJSON(res, 200, {
        status: engramId ? (skip ? 'skipped' : 'stored') : 'pending',
        instruction: buildInstruction(next),
        engram: next,
        progress,
        previousAction,
      } as AnnotationResponse)
      return true
    } catch (err) {
      sendJSON(res, 500, { status: 'error', error: String(err) } as AnnotationResponse)
      return true
    }
  }

  // POST /memory/self-model/reclassify — reclassify "other" domain modules via neighbor-majority
  if (parts[1] === 'self-model' && parts[2] === 'reclassify' && !parts[3] && method === 'POST') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const fromDomain = (body?.domain as string) || 'other'
      const threshold = (body?.threshold as number) || 0.6
      const dryRun = body?.dryRun !== false  // default true for safety

      const all = smf.list('module', 5000)
      const targets = all.filter(e => (e.metadata?.domain as string) === fromDomain)

      const changes: Array<{ id: string; name: string; from: string; to: string; confidence: number }> = []

      for (const engram of targets) {
        const neighbors = smf.getField().neighbors(engram.id)
        const domainCounts = new Map<string, number>()

        for (const n of neighbors.engrams) {
          const d = n.metadata?.domain as string | undefined
          if (d && d !== fromDomain && d !== 'unknown') {
            domainCounts.set(d, (domainCounts.get(d) || 0) + 1)
          }
        }

        if (domainCounts.size === 0) continue

        let bestDomain = ''
        let bestCount = 0
        for (const [d, c] of domainCounts) {
          if (c > bestCount) { bestDomain = d; bestCount = c }
        }

        const total = [...domainCounts.values()].reduce((a, b) => a + b, 0)
        const confidence = total > 0 ? bestCount / total : 0

        if (confidence >= threshold && bestDomain) {
          changes.push({
            id: engram.id,
            name: engram.content.split(' — ')[0],
            from: fromDomain,
            to: bestDomain,
            confidence: Math.round(confidence * 100) / 100,
          })

          if (!dryRun) {
            const updatedMeta = { ...engram.metadata, domain: bestDomain }
            const updatedTags = engram.tags
              .filter(t => t !== `domain:${fromDomain}`)
              .concat(`domain:${bestDomain}`)
            await smf.update(engram.id, { metadata: updatedMeta, tags: updatedTags })
          }
        }
      }

      changes.sort((a, b) => b.confidence - a.confidence)

      sendJSON(res, 200, {
        ok: true,
        dryRun,
        fromDomain,
        threshold,
        candidatesFound: targets.length,
        reclassified: changes.length,
        changes,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/self-model/validate-annotations — find misannotated engrams
  if (parts[1] === 'self-model' && parts[2] === 'validate-annotations' && !parts[3] && method === 'GET') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const all = smf.list(undefined, 5000)
      const issues: Array<{ id: string; name: string; summaryStart: string; issue: string }> = []

      for (const engram of all) {
        const summary = engram.metadata?.llm_summary as string | undefined
        if (!summary || summary.trim().length === 0) continue

        const engramName = engram.content.split(' — ')[0].trim().toLowerCase()
        const summaryFirstWord = summary.trim().split(' ')[0].toLowerCase()

        if (!engramName || !summaryFirstWord) continue

        const commonModulePrefixes = ['the', 'this', 'a', 'an']
        if (commonModulePrefixes.includes(summaryFirstWord)) continue

        if (summaryFirstWord.length > 3 &&
            summaryFirstWord !== engramName &&
            !engramName.includes(summaryFirstWord) &&
            !summaryFirstWord.includes(engramName)) {
          issues.push({
            id: engram.id,
            name: engram.content.split(' — ')[0],
            summaryStart: summary.slice(0, 80),
            issue: `Summary starts with "${summaryFirstWord}" but engram is named "${engramName}" — possible misattribution`,
          })
        }
      }

      sendJSON(res, 200, {
        ok: true,
        annotatedCount: all.filter(e => {
          const s = e.metadata?.llm_summary as string | undefined
          return typeof s === 'string' && s.trim().length > 0
        }).length,
        issuesFound: issues.length,
        issues,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/self-model/audit-coverage — find known intelligence modules missing from self-model
  if (parts[1] === 'self-model' && parts[2] === 'audit-coverage' && !parts[3] && method === 'GET') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const knownModules = [
        'Thalamus', 'Cortex', 'Thinker', 'Dialectic', 'Subconscious',
        'Mnemic-field', 'Lamina', 'Workspace', 'Locus-bridge',
        'Pineal', 'Aurora', 'Dreamer', 'Reverie', 'Helix',
        'Constellation', 'Dmn', 'Heart', 'Meditation',
        'AI-engineer', 'AI-scientist', 'Error-learner',
        'Consequence-estimator', 'Trust-ledger', 'Permission-oracle',
        'Rule-enforcer', 'Context-window', 'Context-repo', 'Synapse',
        'Training', 'Reasoning-bank', 'Continuity',
        'Branching-conversation', 'Code-analysis', 'Code-vault',
        'Embeddings', 'Improvement', 'Execution-backends',
        'Cognitive-feed', 'Memory-bridge', 'Foreshadow',
        'Smart-rules', 'Self-healer', 'Reflex',
      ]

      const all = smf.list(undefined, 5000)
      const found = new Set<string>()

      for (const engram of all) {
        const content = engram.content.toLowerCase()
        for (const name of knownModules) {
          if (content.includes(name.toLowerCase())) {
            found.add(name)
          }
        }
      }

      const missing = knownModules.filter(n => !found.has(n))
      const present = knownModules.filter(n => found.has(n))

      sendJSON(res, 200, {
        ok: true,
        knownModules: knownModules.length,
        presentInSelfModel: present.length,
        missingFromSelfModel: missing.length,
        present,
        missing,
        coverage: `${Math.round((present.length / knownModules.length) * 100)}%`,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/self-model/wire-capabilities — create implements synapses
  if (parts[1] === 'self-model' && parts[2] === 'wire-capabilities' && !parts[3] && method === 'POST') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const dryRun = body?.dryRun !== false

      const capabilities = smf.list('capability', 500)
      const modules = smf.list('module', 5000)

      // Build community → module ID map
      const commToModule = new Map<string, string>()
      for (const mod of modules) {
        const cluster = mod.metadata?.cluster as string | undefined
        if (cluster && !commToModule.has(cluster)) {
          commToModule.set(cluster, mod.id)
        }
      }

      let created = 0, skipped = 0, noImpl = 0
      const createdPairs: Array<{ cap: string; mod: string; comm: string }> = []

      for (const cap of capabilities) {
        const implBy = (cap.metadata as any)?.implementedBy as string[] | undefined
        if (!implBy || implBy.length === 0) { noImpl++; continue }

        for (const comm of implBy) {
          const modId = commToModule.get(comm)
          if (!modId) { skipped++; continue }

          // Check if synapse already exists
          const existing = smf.getField().getTypedSynapses(cap.id, 'implements', 'out')
          if (existing.some(s => s.targetId === modId)) { skipped++; continue }

          if (!dryRun) {
            try {
              smf.connect(cap.id, modId, 'implements')
            } catch {
              skipped++
              continue
            }
          }
          created++
          if (createdPairs.length < 20) {
            createdPairs.push({
              cap: cap.content.split(' — ')[0],
              mod: modules.find(m => m.id === modId)?.content.split(' — ')[0] ?? modId,
              comm,
            })
          }
        }
      }

      sendJSON(res, 200, {
        ok: true,
        dryRun,
        capabilitiesFound: capabilities.length,
        capabilitiesWithoutImpl: noImpl,
        modulesFound: modules.length,
        communitiesMapped: commToModule.size,
        synapsesCreated: created,
        synapsesSkipped: skipped,
        samplePairs: createdPairs,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/self-model/embed-flows — embed execution flow descriptions into module engrams
  if (parts[1] === 'self-model' && parts[2] === 'embed-flows' && !parts[3] && method === 'POST') {
    const smf = requireSelfModel(daemon, res, sendJSON)
    if (!smf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const dryRun = body?.dryRun !== false

      // Get all capability engrams (they hold the flow descriptions)
      const capabilities = smf.list('capability', 500)
      const modules = smf.list('module', 5000)

      // Build community → module map
      const commToModule = new Map<string, { id: string; name: string }>()
      for (const mod of modules) {
        const cluster = mod.metadata?.cluster as string | undefined
        if (cluster && !commToModule.has(cluster)) {
          commToModule.set(cluster, { id: mod.id, name: mod.content.split(' — ')[0] })
        }
      }

      // Build module → flows map
      const moduleFlows = new Map<string, string[]>()
      for (const cap of capabilities) {
        const implBy = (cap.metadata as any)?.implementedBy as string[] | undefined
        if (!implBy || implBy.length === 0) continue

        const flowDesc = cap.content
        for (const comm of implBy) {
          const mod = commToModule.get(comm)
          if (!mod) continue
          const flows = moduleFlows.get(mod.id) || []
          if (!flows.includes(flowDesc)) {
            flows.push(flowDesc)
            moduleFlows.set(mod.id, flows)
          }
        }
      }

      let embedded = 0
      let skipped = 0
      const samples: Array<{ module: string; flowCount: number }> = []

      for (const [modId, flows] of moduleFlows) {
        if (flows.length === 0) { skipped++; continue }

        if (!dryRun) {
          const existing = modules.find(m => m.id === modId)
          if (!existing) { skipped++; continue }

          // Prepend flow descriptions to module content
          const flowSection = flows
            .map(f => `[flow] ${f}`)
            .join('\n')
          const newContent = existing.content + '\n\n' + flowSection

          await smf.update(modId, { content: newContent })
        }

        embedded++
        if (samples.length < 10) {
          const mod = modules.find(m => m.id === modId)
          samples.push({
            module: mod?.content.split(' — ')[0] ?? modId,
            flowCount: flows.length,
          })
        }
      }

      sendJSON(res, 200, {
        ok: true,
        dryRun,
        capabilitiesFound: capabilities.length,
        modulesWithFlows: embedded,
        modulesWithoutFlows: skipped,
        samples,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }


  // GET /memory/knowledge/stats
  if (parts[1] === 'knowledge' && parts[2] === 'stats' && !parts[3] && method === 'GET') {
    const kf = requireKnowledgeField(daemon, res, sendJSON)
    if (!kf) return true
    try {
      sendJSON(res, 200, { ok: true, stats: kf.stats() })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/knowledge/retrieve?query=...&limit=N
  if (parts[1] === 'knowledge' && parts[2] === 'retrieve' && !parts[3] && method === 'GET') {
    const kf = requireKnowledgeField(daemon, res, sendJSON)
    if (!kf) return true
    try {
      const query = url.searchParams.get('query') ?? ''
      if (!query.trim()) {
        sendJSON(res, 400, { error: 'query parameter is required' })
        return true
      }
      const limit = parseInt(url.searchParams.get('limit') ?? '10', 10)
      const hits = await kf.retrieve(query, { limit })
      sendJSON(res, 200, {
        ok: true,
        hits: hits.map((h: any) => ({
          id: h.id,
          nodeType: h.nodeType,
          content: h.content,
          score: h.score,
          charge: h.charge,
          tags: h.tags,
          metadata: h.metadata,
        })),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/knowledge/kindle
  if (parts[1] === 'knowledge' && parts[2] === 'kindle' && !parts[3] && method === 'POST') {
    const kf = requireKnowledgeField(daemon, res, sendJSON)
    if (!kf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const query = typeof body?.query === 'string' ? body.query : ''
      if (!query.trim()) {
        sendJSON(res, 400, { error: 'query is required' })
        return true
      }
      const result = kf.kindle(query, {
        complexity: body?.complexity,
        maxSeeds: typeof body?.maxSeeds === 'number' ? body.maxSeeds : undefined,
        maxLuminalSize: typeof body?.maxLuminalSize === 'number' ? body.maxLuminalSize : undefined,
      })
      sendJSON(res, 200, {
        ok: true,
        luminal: {
          ...result,
          engrams: result.engrams.map((e: any) => ({
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

  // GET /memory/knowledge/techniques?domain=...&limit=N
  if (parts[1] === 'knowledge' && parts[2] === 'techniques' && !parts[3] && method === 'GET') {
    const kf = requireKnowledgeField(daemon, res, sendJSON)
    if (!kf) return true
    try {
      const domain = url.searchParams.get('domain')
      const limit = parseInt(url.searchParams.get('limit') ?? '50', 10)
      const techniques = domain
        ? kf.findTechniquesByDomain(domain, limit)
        : kf.listByKnowledgeType('technique', limit)
      sendJSON(res, 200, { ok: true, techniques })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/knowledge/item/:id
  if (parts[1] === 'knowledge' && parts[2] === 'item' && parts[3] && method === 'GET') {
    const kf = requireKnowledgeField(daemon, res, sendJSON)
    if (!kf) return true
    try {
      const deepDive = kf.getDeepDive(parts[3])
      if (!deepDive) {
        sendJSON(res, 404, { error: 'knowledge item not found' })
        return true
      }
      sendJSON(res, 200, { ok: true, ...deepDive })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/knowledge/compare
  if (parts[1] === 'knowledge' && parts[2] === 'compare' && !parts[3] && method === 'POST') {
    const kf = requireKnowledgeField(daemon, res, sendJSON)
    if (!kf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const idA = body?.idA as string | undefined
      const idB = body?.idB as string | undefined
      if (!idA || !idB) {
        sendJSON(res, 400, { error: 'idA and idB are required' })
        return true
      }
      const comparison = kf.compareTechniques(idA, idB)
      if (!comparison) {
        sendJSON(res, 404, { error: 'one or both techniques not found' })
        return true
      }
      sendJSON(res, 200, { ok: true, comparison })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /memory/knowledge/ingest
  if (parts[1] === 'knowledge' && parts[2] === 'ingest' && !parts[3] && method === 'POST') {
    const kf = requireKnowledgeField(daemon, res, sendJSON)
    if (!kf) return true
    try {
      const body = await parseBody(req).catch(() => ({}))
      const dir = body?.dir as string | undefined
      if (!dir) {
        sendJSON(res, 400, { error: 'dir is required' })
        return true
      }
      const { KnowledgeIngestor } = await import('../intelligence/mnemic-field/knowledge/ingestor.js')
      const ingestor = new KnowledgeIngestor(kf, logger)
      const result = await ingestor.ingestFromDirectory(dir, {
        skipExisting: body?.skipExisting !== false,
        minYear: typeof body?.minYear === 'number' ? body.minYear : undefined,
        createSynapses: body?.createSynapses !== false,
      })
      sendJSON(res, 200, { ok: true, ...result })
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

      // Attempt cross-field retrieval (episodic + self-model) when available
      const bridge = getInterFieldBridge(daemon)
      let hits: BriefingHit[]
      let selfModelCount = 0
      let crossFieldBoosts = 0

      if (bridge) {
        try {
          const crossResult = await bridge.crossRetrieve(query, { complexity, limit })
          hits = crossResult.hits as BriefingHit[]
          selfModelCount = crossResult.selfModelCount
          crossFieldBoosts = crossResult.crossFieldBoosts
        } catch (crossErr) {
          logger.warn('Cross-field retrieval failed, falling back to episodic only', { error: String(crossErr) })
          hits = await field.retrieve(query, { complexity, limit })
        }
      } else {
        hits = await field.retrieve(query, { complexity, limit })
      }

      if (hits.length === 0) {
        sendJSON(res, 200, {
          ok: true,
          hasContext: false,
          markdown: `No relevant context found for: \`${query}\``,
        })
        return true
      }

      // Build first-person briefing from episodic hits
      const sections = buildEnrichmentBriefing(hits, query)

      // Append self-model section if cross-field produced self-model results
      if (selfModelCount > 0) {
        const smHits = hits.filter(h => (h as any).sourceField === 'self-model')
        if (smHits.length > 0) {
          const smLines = smHits.slice(0, 5).map(h => {
            const prefix = h.nodeType === 'module' ? '[Module]'
              : h.nodeType === 'capability' ? '[Capability]'
              : h.nodeType === 'weakness' ? '[Weakness]'
              : h.nodeType === 'pattern' ? '[Pattern]'
              : `[${h.nodeType}]`
            return `- ${prefix} ${h.content.slice(0, 300)}`
          })
          sections.push(`## Architectural self-knowledge\n\n${smLines.join('\n')}`)
        }
      }

      const affectState = field.getAffect()
      if (affectState.label !== 'neutral') {
        sections.unshift(`*Current affect: ${affectState.label} (v: ${affectState.valence.toFixed(2)}, a: ${affectState.arousal.toFixed(2)})*`)
      }

      sendJSON(res, 200, {
        ok: true,
        hasContext: true,
        markdown: sections.join('\n\n'),
        engramIds: hits.map(h => h.id),
        hitCount: hits.length,
        selfModelCount,
        crossFieldBoosts,
        affect: affectState,
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

      // Neural Kindling: also store a gradient request linking feedback to the last forward trace
      let gradientStored = false
      try {
        gradientStored = field.recordEnrichFeedback(feedback)
      } catch {
        // Non-critical — gradient storage failure shouldn't block feedback
      }

      sendJSON(res, 200, { ok: true, recorded, gradientStored })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /memory/lightning/status — Lightning Indexer mode, training stats, promotion readiness
  if (parts[1] === 'lightning' && parts[2] === 'status' && method === 'GET') {
    const field = getMnemicField(logger, daemon)
    sendJSON(res, 200, field.getLightningStatus())
    return true
  }

  // POST /memory/lightning/mode — Set Lightning Indexer mode
  if (parts[1] === 'lightning' && parts[2] === 'mode' && method === 'POST') {
    const body = await parseBody(req).catch(() => ({}))
    const mode = body?.mode as string | undefined
    if (mode !== 'shadow' && mode !== 'sparsify' && mode !== 'off') {
      sendJSON(res, 400, { error: 'mode must be shadow, sparsify, or off' })
      return true
    }
    const field = getMnemicField(logger, daemon)
    field.setLightningMode(mode as 'shadow' | 'sparsify' | 'off')
    sendJSON(res, 200, field.getLightningStatus())
    return true
  }

  // POST /memory/lightning/train — Force one training step
  if (parts[1] === 'lightning' && parts[2] === 'train' && method === 'POST') {
    const field = getMnemicField(logger, daemon)
    const result = await field.trainLightningIndexer()
    if (!result) {
      sendJSON(res, 503, { error: 'Lightning Indexer not initialized' })
      return true
    }
    sendJSON(res, 200, result)
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


  // POST /memory/universal-search — search memory + archive, return combined results
  if (parts[1] === 'universal-search' && method === 'POST') {
    if (!memory) return noMemory()
    const body = await parseBody(req)
    const query = body?.query ?? ''
    const limit = body?.limit ?? 10
    const includeMemories = body?.includeMemories !== false
    const includeArchives = body?.includeArchives !== false

    const hits: any[] = []

    // Search memory — uses MnemicField FTS5 (the MemoryShim is in-memory only, always empty)
    if (includeMemories && query.trim()) {
      try {
        const field = getMnemicField(logger, daemon)
        const textHits = field.searchText(query, limit * 2)
          .filter(r => r.engram.nodeType !== 'bridge')
        for (const r of textHits) {
          hits.push({
            id: r.engram.id,
            source: 'memory',
            type: r.engram.nodeType || 'fact',
            content: r.engram.content || '',
            score: r.score,
            metadata: r.engram.metadata ?? {},
          })
        }
      } catch (err: any) {
        logger.warn('universal-search memory query failed', { error: String(err), query })
      }
    }

    // Search archive (daemon.archive if available)
    const archive = (daemon as any)?.archive
    if (includeArchives && query.trim() && archive?.search) {
      try {
        const archResults = await archive.search(query, { limit: limit * 2 })
        for (const r of (archResults || [])) {
          hits.push({
            id: r.id,
            source: 'archive',
            type: r.type || r.entry?.type || 'turn',
            content: r.content || r.response || r.entry?.content || '',
            score: r.score ?? 0.5,
            metadata: r.metadata || r.entry?.metadata,
          })
        }
      } catch (err: any) {
        logger.warn('universal-search archive query failed', { error: String(err), query })
      }
    }

    // Deduplicate by content hash
    const seen = new Set<string>()
    const deduped = hits.filter(h => {
      const key = (h.content || '').slice(0, 200)
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })

    // Sort by score descending, apply limit
    deduped.sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    const results = deduped.slice(0, limit)

    sendJSON(res, 200, { ok: true, query, count: results.length, hits: results })
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

  function getVindexProvider(): any | null {
    return (daemon?.intelligence as any)?.aurora?.modelProvider ?? null
  }

  // POST /memory/vindex/forward — full forward pass, returns residuals + attention
  if (parts[1] === 'vindex' && parts[2] === 'forward' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const provider = getVindexProvider()
      if (!provider || !provider.forward) {
        sendJSON(res, 503, { error: 'vindex forward not available' }); return true
      }
      const text = typeof body?.text === 'string' ? body.text : ''
      const layers: number[] = Array.isArray(body?.layers) ? body.layers : [14, 20, 27]
      const captureAttention = body?.captureAttention === true
      if (!text) { sendJSON(res, 400, { error: 'text required' }); return true }
      const tokens = provider.tokenize(text)
      const result = provider.forward(tokens, layers, captureAttention)
      const residuals = result.residuals.map((r: any) => {
        const arr = new Float32Array(r.values.buffer, r.values.byteOffset, r.values.length)
        return { layer: r.layer, dims: arr.length, l2: Math.sqrt(arr.reduce((s: number, v: number) => s + v*v, 0)).toFixed(1) }
      })
      sendJSON(res, 200, { ok: true, tokens: tokens.length, residuals, attention: result.attention, durationMs: result.durationMs })
      return true
    } catch (err) { sendJSON(res, 500, { error: String(err) }); return true }
  }

  // POST /memory/vindex/generate — steered generation through the vindex model
  if (parts[1] === 'vindex' && parts[2] === 'generate' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const provider = getVindexProvider()
      if (!provider || !provider.generate) {
        sendJSON(res, 503, { error: 'vindex generation not available' }); return true
      }
      const prompt = typeof body?.prompt === 'string' ? body.prompt : ''
      const maxTokens = typeof body?.maxTokens === 'number' ? body.maxTokens : 50
      const steers = Array.isArray(body?.steers) ? body.steers : []
      if (!prompt) { sendJSON(res, 400, { error: 'prompt required' }); return true }
      const tokens = provider.tokenize(prompt)
      const gen = provider.generate(tokens, { maxTokens, steers })
      sendJSON(res, 200, { ok: true, text: gen.text, tokensGenerated: gen.tokens?.length ?? 0, durationMs: gen.durationMs })
      return true
    } catch (err) { sendJSON(res, 500, { error: String(err) }); return true }
  }

  // GET /memory/vindex/sources — list loaded vindex sources
  if (parts[1] === 'vindex' && parts[2] === 'sources' && method === 'GET') {
    try {
      const aurora = (daemon as any).intelligence?.aurora
      const provider = aurora?.modelProvider
      if (!provider?.getLoadedSources) {
        sendJSON(res, 503, { error: 'vindex provider not available' })
        return true
      }
      const sources = provider.getLoadedSources()
      const defaultSource = provider.getDefaultSource()
      const details = sources.map((s: string) => {
        const binding = provider.getBinding(s)
        return {
          source: s,
          config: binding?.config ?? null,
          isDefault: s === defaultSource,
        }
      })
      sendJSON(res, 200, { ok: true, sources: details, total: sources.length })
      return true
    } catch (err) { sendJSON(res, 500, { error: String(err) }); return true }
  }

  // GET /memory/vindex/vram — GPU VRAM usage telemetry
  if (parts[1] === 'vindex' && parts[2] === 'vram' && method === 'GET') {
    try {
      const fs = await import('node:fs/promises')
      const gpus: Array<{ id: number; vramTotalBytes: number; vramUsedBytes: number; vramFreeBytes: number }> = []
      for (let i = 0; i < 8; i++) {
        const totalPath = `/sys/class/drm/card${i}/device/mem_info_vram_total`
        const usedPath = `/sys/class/drm/card${i}/device/mem_info_vram_used`
        try {
          const [totalRaw, usedRaw] = await Promise.all([
            fs.readFile(totalPath, 'utf-8'),
            fs.readFile(usedPath, 'utf-8'),
          ])
          const total = parseInt(totalRaw.trim(), 10)
          const used = parseInt(usedRaw.trim(), 10)
          if (!isNaN(total) && total > 0) {
            gpus.push({ id: i, vramTotalBytes: total, vramUsedBytes: used, vramFreeBytes: total - used })
          }
        } catch { break }
      }

      const aurora = (daemon as any).intelligence?.aurora
      const provider = aurora?.modelProvider
      const sources = provider?.getLoadedSources?.() ?? []

      sendJSON(res, 200, {
        ok: true,
        gpus: gpus.map(g => ({
          id: g.id,
          vramTotalMB: Math.round(g.vramTotalBytes / 1024 / 1024),
          vramUsedMB: Math.round(g.vramUsedBytes / 1024 / 1024),
          vramFreeMB: Math.round(g.vramFreeBytes / 1024 / 1024),
          usedPct: g.vramTotalBytes > 0 ? parseFloat(((g.vramUsedBytes / g.vramTotalBytes) * 100).toFixed(1)) : 0,
        })),
        loadedSources: sources,
        note: 'Per-vindex VRAM breakdown requires Rust backend telemetry (future)',
      })
      return true
    } catch (err) { sendJSON(res, 500, { error: String(err) }); return true }
  }

  // GET /memory/vindex/quality?text=... — score content quality via attention Gini
  if (parts[1] === 'vindex' && parts[2] === 'quality' && method === 'GET') {
    try {
      const text = url.searchParams.get('text')
      const field = getMnemicField(logger, daemon)
      const scorer = (field as any).qualityScorer
      if (!text) { sendJSON(res, 400, { error: 'text query param required' }); return true }
      if (!scorer?.isReady()) { sendJSON(res, 503, { error: 'quality scorer not available' }); return true }
      const score = scorer.scoreContent(text)
      sendJSON(res, 200, { ok: true, ...score })
      return true
    } catch (err) { sendJSON(res, 500, { error: String(err) }); return true }
  }

  // POST /memory/vindex/quality-batch — batch quality scoring via attention Gini
  if (parts[1] === 'vindex' && parts[2] === 'quality-batch' && method === 'POST') {
    try {
      const body = await parseBody(req).catch(() => ({}))
      const texts: string[] = Array.isArray(body?.texts) ? body.texts : []
      const field = getMnemicField(logger, daemon)
      const scorer = (field as any).qualityScorer
      if (texts.length === 0) { sendJSON(res, 400, { error: 'texts array required' }); return true }
      if (texts.length > 50) { sendJSON(res, 400, { error: 'max 50 texts per batch' }); return true }
      if (!scorer?.isReady()) { sendJSON(res, 503, { error: 'quality scorer not available' }); return true }

      const results: Array<{ index: number; score: any; error?: string }> = []
      for (let i = 0; i < texts.length; i++) {
        try {
          const score = scorer.scoreContent(texts[i])
          results.push({ index: i, score })
        } catch (err) {
          results.push({ index: i, score: null, error: String(err) })
        }
      }

      const valid = results.filter(r => r.score).length
      const avgScore = valid > 0
        ? results.filter(r => r.score).reduce((s: number, r: any) => s + r.score.score, 0) / valid
        : 0

      sendJSON(res, 200, { ok: true, count: texts.length, scored: valid, avgScore, results })
      return true
    } catch (err) { sendJSON(res, 500, { error: String(err) }); return true }
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
