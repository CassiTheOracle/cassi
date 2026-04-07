/**
 * Constellation Admin API Routes
 *
 * Async job-based endpoints for Constellation multi-Helix orchestration.
 */

import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'
import type { ConstellationResult } from '../intelligence/constellation/types.js'
import { serializeConstellationResult } from '../intelligence/constellation/constellation-pipeline.js'
import type { CorpusTreeSnapshot } from '../intelligence/constellation/corpus-types.js'
import type { ConstellationSessionRow, ProgressSnapshot } from '../intelligence/constellation/constellation-store.js'


interface ConstellationJob {
  id: string
  sessionId: string
  status: 'running' | 'completed' | 'failed'
  goal: string
  startedAt: number
  completedAt?: number
  result?: ConstellationResult
  error?: string
}

interface ConstellationDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}


const constellationJobs = new Map<string, ConstellationJob>()
const JOB_TTL_MS = 60 * 60 * 1000 // 1 hour
const MAX_JOBS = 30

function generateJobId(): string {
  return `constellation-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function pruneOldJobs(): void {
  const now = Date.now()
  for (const [id, job] of constellationJobs) {
    if (now - job.startedAt > JOB_TTL_MS) {
      constellationJobs.delete(id)
    }
  }
  if (constellationJobs.size > MAX_JOBS) {
    const sorted = [...constellationJobs.entries()].sort((a, b) => a[1].startedAt - b[1].startedAt)
    const toRemove = sorted.slice(0, sorted.length - MAX_JOBS)
    for (const [id] of toRemove) {
      constellationJobs.delete(id)
    }
  }
}

function findJob(idOrSessionId: string): ConstellationJob | undefined {
  return constellationJobs.get(idOrSessionId) ??
    [...constellationJobs.values()].find(j => j.sessionId === idOrSessionId)
}


// WHY: Load a persisted tree snapshot from ConstellationStore for completed sessions.
async function loadPersistedTree(daemon: any, sessionId: string): Promise<CorpusTreeSnapshot | null> {
  try {
    const { ConstellationStore } = await import('../intelligence/constellation/constellation-store.js')
    const store = ConstellationStore.open(daemon.logger.child('constellation-store-reader'))
    const tree = store.getTree(sessionId)
    store.close()
    return tree
  } catch (err) {
    daemon.logger.warn('loadPersistedTree: error', { sessionId, error: String(err) })
    return null
  }
}

// WHY: Load a persisted progress snapshot from ConstellationStore for completed sessions.
async function loadPersistedProgress(daemon: any, sessionId: string): Promise<ProgressSnapshot | null> {
  try {
    const { ConstellationStore } = await import('../intelligence/constellation/constellation-store.js')
    const store = ConstellationStore.open(daemon.logger.child('constellation-store-reader'))
    const progress = store.getProgress(sessionId)
    store.close()
    return progress
  } catch {
    return null
  }
}

// WHY: Load a persisted session from ConstellationStore.
async function loadPersistedSession(daemon: any, sessionId: string): Promise<ConstellationSessionRow | undefined> {
  try {
    const { ConstellationStore } = await import('../intelligence/constellation/constellation-store.js')
    const store = ConstellationStore.open(daemon.logger.child('constellation-store-reader'))
    const session = store.getSession(sessionId)
    store.close()
    return session
  } catch {
    return undefined
  }
}

// WHY: List sessions from ConstellationStore (includes archived).
async function loadPersistedSessions(daemon: any, opts?: { limit?: number; status?: string; includeArchived?: boolean }): Promise<ConstellationSessionRow[]> {
  try {
    const { ConstellationStore } = await import('../intelligence/constellation/constellation-store.js')
    const store = ConstellationStore.open(daemon.logger.child('constellation-store-reader'))
    const sessions = store.listSessions(opts)
    store.close()
    return sessions
  } catch {
    return []
  }
}

// WHY: Get session history from ConstellationStore.
async function loadSessionHistory(daemon: any, opts?: { limit?: number; since?: number; until?: number; status?: string }): Promise<ConstellationSessionRow[]> {
  try {
    const { ConstellationStore } = await import('../intelligence/constellation/constellation-store.js')
    const store = ConstellationStore.open(daemon.logger.child('constellation-store-reader'))
    const history = store.getHistory(opts)
    store.close()
    return history
  } catch {
    return []
  }
}


export async function handleConstellationRoutes(
  deps: ConstellationDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody } = deps
  const url = new URL(req.url ?? '/', `http://${req.headers.host}`)
  const pathname = url.pathname

  if (!pathname.startsWith('/constellation')) return false

  const parts = pathname.split('/').filter(Boolean)

  if (method === 'POST' && parts.length === 1) {
    pruneOldJobs()
    try {
      const body = await parseBody(req)
      const { goal, context, template, postures, maxHelixes, maxDepth, costEffective } = body ?? {}

      if (!goal) {
        sendJSON(res, 400, { error: 'goal is required' })
        return true
      }

      const jobId = generateJobId()
      const sessionId = jobId

      const job: ConstellationJob = {
        id: jobId,
        sessionId,
        status: 'running',
        goal,
        startedAt: Date.now(),
      }
      constellationJobs.set(jobId, job)

      const constellationOrchestrator = daemon.intelligence?.constellation
      if (!constellationOrchestrator) {
        sendJSON(res, 503, { error: 'Constellation orchestrator not available' })
        constellationJobs.delete(jobId)
        return true
      }

      constellationOrchestrator.project({
        goal,
        context,
        template: template ?? 'standard',
        postures,
        maxHelixes,
        maxDepth,
        sessionId,
        costEffective: costEffective === true,
      }).then((result: ConstellationResult) => {
        job.status = 'completed'
        job.completedAt = Date.now()
        job.result = result
      }).catch((err: Error) => {
        job.status = 'failed'
        job.completedAt = Date.now()
        job.error = String(err)
        logger.error('Constellation job failed', { jobId, error: String(err) })
      })

      sendJSON(res, 200, {
        jobId,
        sessionId,
        status: 'running',
        message: `Constellation started. Poll GET /constellation/${jobId} for results.`,
      })
      return true
    } catch (err) {
      logger.error('constellation:project:request-error', { error: String(err) })
      sendJSON(res, 500, { error: 'Failed to start Constellation', detail: String(err) })
      return true
    }
  }

  if (method === 'GET' && parts.length === 2 && parts[1] === 'jobs') {
    pruneOldJobs()
    const jobs = [...constellationJobs.values()].map(j => ({
      id: j.id,
      sessionId: j.sessionId,
      status: j.status,
      goal: j.goal,
      startedAt: j.startedAt,
      completedAt: j.completedAt,
    }))
    sendJSON(res, 200, { jobs })
    return true
  }

  if (method === 'GET' && parts.length === 2 && parts[1] === 'sessions') {
    const includeArchived = url.searchParams.get('include_archived') !== 'false'
    const limit = parseInt(url.searchParams.get('limit') || '100', 10)
    const status = url.searchParams.get('status') || undefined

    const activeSessions = [...constellationJobs.values()]
      .filter(j => j.status === 'running')
      .map(j => ({
        id: j.sessionId,
        goal: j.goal,
        status: j.status,
        startedAt: j.startedAt,
        source: 'live' as const,
      }))

    let archivedSessions: Array<{
      id: string
      goal: string
      status: string
      startedAt: number
      completedAt?: number | null
      source: 'archived'
    }> = []

    if (includeArchived) {
      const persisted = await loadPersistedSessions(daemon, { limit, status, includeArchived: true })
      archivedSessions = persisted
        .filter(s => !activeSessions.some(a => a.id === s.id))
        .map(s => ({
          id: s.id,
          goal: s.goal,
          status: s.status,
          startedAt: s.createdAt,
          completedAt: s.completedAt,
          source: 'archived' as const,
        }))
    }

    const allSessions = [...activeSessions, ...archivedSessions].slice(0, limit)
    sendJSON(res, 200, {
      sessions: allSessions,
      count: allSessions.length,
      hasArchived: archivedSessions.length > 0,
    })
    return true
  }

  if (method === 'GET' && parts.length === 2 && parts[1] === 'history') {
    const limit = parseInt(url.searchParams.get('limit') || '100', 10)
    const since = url.searchParams.get('since')
      ? new Date(url.searchParams.get('since')!).getTime()
      : undefined
    const until = url.searchParams.get('until')
      ? new Date(url.searchParams.get('until')!).getTime()
      : undefined
    const status = url.searchParams.get('status') || undefined

    const history = await loadSessionHistory(daemon, { limit, since, until, status })
    sendJSON(res, 200, {
      history: history.map(s => ({
        id: s.id,
        goal: s.goal,
        status: s.status,
        template: s.template,
        totalBranches: s.totalBranches,
        completedBranches: s.completedBranches,
        failedBranches: s.failedBranches,
        tokensUsed: s.tokensUsed,
        durationMs: s.durationMs,
        createdAt: s.createdAt,
        completedAt: s.completedAt,
        error: s.error,
      })),
      count: history.length,
    })
    return true
  }

  if (parts.length >= 2 && parts[1] !== 'jobs' && parts[1] !== 'sessions' && parts[1] !== 'history') {
    const id = parts[1]
    const subAction = parts[2]

    if (method === 'POST' && subAction === 'cancel') {
      const job = findJob(id)
      if (!job) {
        sendJSON(res, 404, { error: 'Job not found' })
        return true
      }
      const orchestrator = daemon.intelligence?.constellation
      if (orchestrator?.cancel) {
        orchestrator.cancel(job.sessionId)
      }
      job.status = 'failed'
      job.completedAt = Date.now()
      job.error = 'Cancelled by user'
      sendJSON(res, 200, { sessionId: job.sessionId, status: 'cancelled' })
      return true
    }

    if (method === 'POST' && subAction === 'resume') {
      try {
        const orchestrator = daemon.intelligence?.constellation
        if (!orchestrator?.resumeConstellation) {
          sendJSON(res, 501, { error: 'Resume not available' })
          return true
        }

        const jobId = generateJobId()
        const job: ConstellationJob = {
          id: jobId,
          sessionId: id,
          status: 'running',
          goal: 'Resuming constellation',
          startedAt: Date.now(),
        }
        constellationJobs.set(jobId, job)

        orchestrator.resumeConstellation(id)
          .then((result: ConstellationResult) => {
            job.status = 'completed'
            job.completedAt = Date.now()
            job.result = result
          })
          .catch((err: Error) => {
            job.status = 'failed'
            job.completedAt = Date.now()
            job.error = String(err)
            logger.error('Constellation resume failed', { sessionId: id, error: String(err) })
          })

        sendJSON(res, 200, {
          jobId,
          sessionId: id,
          status: 'running',
          message: `Constellation resume started. Poll GET /constellation/${jobId} for results.`,
        })
      } catch (err) {
        logger.error('constellation:resume:request-error', { error: String(err) })
        sendJSON(res, 500, { error: 'Failed to resume Constellation', detail: String(err) })
      }
      return true
    }

    if (method === 'POST' && subAction === 'steer') {
      const job = findJob(id)
      if (!job || job.status !== 'running') {
        sendJSON(res, 404, { error: 'Running constellation not found' })
        return true
      }
      try {
        const body = await parseBody(req)
        const { message, targetHelixId, urgency } = body ?? {}
        if (!message) {
          sendJSON(res, 400, { error: 'message is required' })
          return true
        }
        const orchestrator = daemon.intelligence?.constellation
        if (orchestrator?.steer) {
          orchestrator.steer(job.sessionId, { message, targetHelixId, urgency: urgency ?? 'medium' })
        }
        sendJSON(res, 200, { status: 'steering directive sent', sessionId: job.sessionId })
      } catch (err) {
        sendJSON(res, 500, { error: 'Failed to send steering directive', detail: String(err) })
      }
      return true
    }

    if (method === 'POST' && subAction === 'corpus' && parts[3] === 'assume') {
      const job = findJob(id)
      if (!job || job.status !== 'running') {
        sendJSON(res, 404, { error: 'Running constellation not found' })
        return true
      }
      try {
        const body = await parseBody(req)
        const { agentId, heartbeatTimeoutMs } = body ?? {}
        if (!agentId) {
          sendJSON(res, 400, { error: 'agentId is required' })
          return true
        }
        const orchestrator = daemon.intelligence?.constellation
        if (!orchestrator?.assumeCorpus) {
          sendJSON(res, 501, { error: 'External Corpus Protocol not available' })
          return true
        }
        const result = orchestrator.assumeCorpus(job.sessionId, agentId, heartbeatTimeoutMs)
        sendJSON(res, result.assumed ? 200 : 409, result)
      } catch (err) {
        sendJSON(res, 500, { error: 'Failed to assume Corpus', detail: String(err) })
      }
      return true
    }

    if (method === 'POST' && subAction === 'corpus' && parts[3] === 'release') {
      const job = findJob(id)
      if (!job || job.status !== 'running') {
        sendJSON(res, 404, { error: 'Running constellation not found' })
        return true
      }
      try {
        const body = await parseBody(req)
        const { reason } = body ?? {}
        const orchestrator = daemon.intelligence?.constellation
        if (!orchestrator?.releaseCorpus) {
          sendJSON(res, 501, { error: 'External Corpus Protocol not available' })
          return true
        }
        const result = orchestrator.releaseCorpus(job.sessionId, reason)
        sendJSON(res, result.released ? 200 : 409, result)
      } catch (err) {
        sendJSON(res, 500, { error: 'Failed to release Corpus', detail: String(err) })
      }
      return true
    }

    if (method === 'GET' && subAction === 'corpus' && parts[3] === 'state') {
      const job = findJob(id)
      if (!job || job.status !== 'running') {
        sendJSON(res, 404, { error: 'Running constellation not found' })
        return true
      }
      const orchestrator = daemon.intelligence?.constellation
      const state = orchestrator?.getCorpusExternalState?.(job.sessionId)
      if (!state) {
        sendJSON(res, 404, { error: 'Corpus state not available' })
        return true
      }
      sendJSON(res, 200, state)
      return true
    }

    if (method === 'GET' && subAction === 'corpus' && parts[3] === 'snapshot') {
      const job = findJob(id)
      if (!job || job.status !== 'running') {
        sendJSON(res, 404, { error: 'Running constellation not found' })
        return true
      }
      const orchestrator = daemon.intelligence?.constellation
      const snapshot = orchestrator?.getCorpusSnapshot?.(job.sessionId)
      if (!snapshot) {
        sendJSON(res, 404, { error: 'Corpus snapshot not available' })
        return true
      }
      sendJSON(res, 200, snapshot)
      return true
    }

    if (method === 'POST' && subAction === 'corpus' && parts[3] === 'directive') {
      const job = findJob(id)
      if (!job || job.status !== 'running') {
        sendJSON(res, 404, { error: 'Running constellation not found' })
        return true
      }
      try {
        const body = await parseBody(req)
        const { targetHelixId, type, content, urgency } = body ?? {}
        if (!targetHelixId || !type || !content) {
          sendJSON(res, 400, { error: 'targetHelixId, type, and content are required' })
          return true
        }
        const orchestrator = daemon.intelligence?.constellation
        if (!orchestrator?.corpusDirective) {
          sendJSON(res, 501, { error: 'External Corpus Protocol not available' })
          return true
        }
        const result = orchestrator.corpusDirective(job.sessionId, {
          targetHelixId,
          type,
          text: content,
          reason: content,
          urgency: urgency ?? 'medium',
        })
        sendJSON(res, result.sent ? 200 : 409, result)
      } catch (err) {
        sendJSON(res, 500, { error: 'Failed to send directive', detail: String(err) })
      }
      return true
    }

    if (method === 'POST' && subAction === 'corpus' && parts[3] === 'spawn-decide') {
      const job = findJob(id)
      if (!job || job.status !== 'running') {
        sendJSON(res, 404, { error: 'Running constellation not found' })
        return true
      }
      try {
        const body = await parseBody(req)
        const { requestId, approved, reason, modifiedGoal } = body ?? {}
        if (!requestId || approved === undefined || !reason) {
          sendJSON(res, 400, { error: 'requestId, approved, and reason are required' })
          return true
        }
        const orchestrator = daemon.intelligence?.constellation
        if (!orchestrator?.corpusSpawnDecide) {
          sendJSON(res, 501, { error: 'External Corpus Protocol not available' })
          return true
        }
        const result = orchestrator.corpusSpawnDecide(job.sessionId, requestId, !!approved, reason, modifiedGoal)
        sendJSON(res, result.decided ? 200 : 409, result)
      } catch (err) {
        sendJSON(res, 500, { error: 'Failed to decide spawn request', detail: String(err) })
      }
      return true
    }

    if (method === 'POST' && subAction === 'corpus' && parts[3] === 'synthesis') {
      const job = findJob(id)
      if (!job || job.status !== 'running') {
        sendJSON(res, 404, { error: 'Running constellation not found' })
        return true
      }
      try {
        const body = await parseBody(req)
        const { content, priority, tags } = body ?? {}
        if (!content) {
          sendJSON(res, 400, { error: 'content is required' })
          return true
        }
        const orchestrator = daemon.intelligence?.constellation
        if (!orchestrator?.corpusSynthesis) {
          sendJSON(res, 501, { error: 'External Corpus Protocol not available' })
          return true
        }
        const result = orchestrator.corpusSynthesis(job.sessionId, content, priority, tags)
        sendJSON(res, result.posted ? 200 : 409, result)
      } catch (err) {
        sendJSON(res, 500, { error: 'Failed to post synthesis', detail: String(err) })
      }
      return true
    }

    if (method === 'GET' && subAction === 'progress') {
      const job = findJob(id)

      if (job) {
        const orchestrator = daemon.intelligence?.constellation
        const progress = orchestrator?.getProgress?.(job.sessionId)

        if (progress) {
          sendJSON(res, 200, {
            sessionId: job.sessionId,
            status: job.status,
            goal: job.goal,
            startedAt: job.startedAt,
            durationMs: Date.now() - job.startedAt,
            progress,
            source: 'live',
          })
          return true
        }

        const persisted = await loadPersistedProgress(daemon, job.sessionId)
        if (persisted) {
          sendJSON(res, 200, {
            sessionId: job.sessionId,
            status: job.status,
            goal: job.goal,
            startedAt: job.startedAt,
            durationMs: job.completedAt ? job.completedAt - job.startedAt : Date.now() - job.startedAt,
            progress: persisted,
            source: 'archived',
          })
          return true
        }

        sendJSON(res, 200, {
          sessionId: job.sessionId,
          status: job.status,
          goal: job.goal,
          startedAt: job.startedAt,
          durationMs: Date.now() - job.startedAt,
          progress: null,
          message: 'Progress not available',
        })
        return true
      }

      const persisted = await loadPersistedProgress(daemon, id)
      if (persisted) {
        const session = await loadPersistedSession(daemon, id)
        sendJSON(res, 200, {
          sessionId: id,
          status: session?.status ?? 'unknown',
          goal: session?.goal ?? 'unknown',
          startedAt: session?.createdAt,
          durationMs: session?.durationMs,
          progress: persisted,
          source: 'archived',
        })
        return true
      }

      sendJSON(res, 404, { error: 'Session not found' })
      return true
    }

    if (method === 'GET' && subAction === 'tree') {
      const job = findJob(id)

      if (job) {
        const orchestrator = daemon.intelligence?.constellation
        const tree = orchestrator?.getTree?.(job.sessionId)

        if (tree) {
          sendJSON(res, 200, { sessionId: job.sessionId, tree, source: 'live' })
          return true
        }

        const persisted = await loadPersistedTree(daemon, job.sessionId)
        if (persisted) {
          sendJSON(res, 200, { sessionId: job.sessionId, tree: persisted, source: 'archived' })
          return true
        }

        sendJSON(res, 200, {
          sessionId: job.sessionId,
          tree: null,
          message: 'Tree not available (session may not have been archived)',
        })
        return true
      }

      const persisted = await loadPersistedTree(daemon, id)
      if (persisted) {
        sendJSON(res, 200, { sessionId: id, tree: persisted, source: 'archived' })
        return true
      }

      sendJSON(res, 404, { error: 'Session not found' })
      return true
    }

    if (method === 'GET' && subAction === 'locus' && parts.length === 3) {
      const job = findJob(id)
      if (!job || job.status !== 'running') {
        sendJSON(res, 404, { error: 'Locus snapshot only available for running constellations' })
        return true
      }
      const orchestrator = daemon.intelligence?.constellation
      const snapshot = orchestrator?.getLocusSnapshot?.(job.sessionId)
      if (!snapshot) {
        sendJSON(res, 200, { sessionId: job.sessionId, snapshot: null, enabled: false })
        return true
      }
      sendJSON(res, 200, { sessionId: job.sessionId, snapshot, source: 'live' })
      return true
    }

    if (method === 'GET' && subAction === 'locus' && parts[3] === 'memories') {
      const job = findJob(id)
      if (!job || job.status !== 'running') {
        try {
          const { ConstellationStore } = await import('../intelligence/constellation/constellation-store.js')
          const store = ConstellationStore.open(daemon.logger.child('constellation-store-reader'))
          const persistence = store.getLocusMemoryPersistence()
          const memories = persistence.loadMemories()
          store.close()
          sendJSON(res, 200, {
            sessionId: job?.sessionId ?? id,
            memories,
            count: memories.length,
            source: 'archived',
          })
        } catch {
          sendJSON(res, 200, { sessionId: job?.sessionId ?? id, memories: [], count: 0, source: 'archived' })
        }
        return true
      }
      const orchestrator = daemon.intelligence?.constellation
      const memories = orchestrator?.getLocusMemories?.(job.sessionId)
      sendJSON(res, 200, {
        sessionId: job.sessionId,
        memories: memories ?? [],
        count: memories?.length ?? 0,
        source: 'live',
      })
      return true
    }

    if (method === 'GET' && subAction === 'topology') {
      const job = findJob(id)
      const orchestrator = daemon.intelligence?.constellation
      const sessionId = job?.sessionId ?? id

      const topology = orchestrator?.getTopology?.(sessionId)
      if (topology) {
        // WHY: distances is a nested Map — convert to plain object for JSON
        const distances: Record<string, Record<string, number>> = {}
        if (topology.distances instanceof Map) {
          for (const [fromId, toMap] of topology.distances) {
            distances[fromId] = {}
            for (const [toId, dist] of toMap) {
              distances[fromId][toId] = dist
            }
          }
        }
        sendJSON(res, 200, {
          sessionId,
          topology: { ...topology, distances },
          source: 'live',
        })
        return true
      }

      // Fallback: check completed job result
      if (job?.result?.topology) {
        try {
          const serialized = serializeConstellationResult(job.result)
          sendJSON(res, 200, {
            sessionId,
            topology: serialized.topology ?? null,
            source: 'result',
          })
        } catch (err) {
          // Defensive: serializeConstellationResult is non-throwing, but guard anyway
          logger.warn('Failed to serialize topology from job result', { sessionId, error: String(err) })
          sendJSON(res, 200, {
            sessionId,
            topology: null,
            source: 'result',
            error: 'Serialization failed',
          })
        }
        return true
      }

      // Fallback: for archived topology, use GET /constellation/:id/analyze
      // which reads from the ConstellationStore and includes topology spatial analysis

      sendJSON(res, 200, {
        sessionId,
        topology: null,
        message: 'Topology not available (session may not be running or topology is disabled)',
      })
      return true
    }

    if (method === 'GET' && subAction === 'audit-trail') {
      try {
        const auditTrail = daemon.intelligence?.constellationAuditTrail
        if (auditTrail) {
          const trail = auditTrail.readTrail(id)
          sendJSON(res, 200, { sessionId: id, ...trail, source: 'artifact-store' })
        } else {
          // Fallback: read events directly from ConstellationStore
          const { ConstellationStore } = await import('../intelligence/constellation/constellation-store.js')
          const store = ConstellationStore.open(daemon.logger.child('constellation-store-reader'))
          const events = store.getEvents(id)
          store.close()
          if (events.length > 0) {
            sendJSON(res, 200, { sessionId: id, events, source: 'constellation-store' })
          } else {
            sendJSON(res, 404, { error: 'No audit trail found for this session' })
          }
        }
      } catch (err) {
        logger.error('Failed to read audit trail', { sessionId: id, error: String(err) })
        sendJSON(res, 500, { error: `Audit trail read failed: ${String(err)}` })
      }
      return true
    }

    if (method === 'GET' && subAction === 'analyze') {
      const depth = (url.searchParams?.get?.('depth') ?? 'summary') as 'summary' | 'timeline' | 'full'
      try {
        const { analyzeConstellation } = await import('../intelligence/constellation/constellation-analyzer.js')
        const analysis = await analyzeConstellation(id, depth)
        sendJSON(res, 200, analysis)
      } catch (err) {
        logger.error('Failed to analyze constellation session', { sessionId: id, error: String(err) })
        sendJSON(res, 500, { error: `Analysis failed: ${String(err)}` })
      }
      return true
    }

    if (method === 'GET' && subAction === 'stream') {
      const job = findJob(id)
      if (!job) {
        sendJSON(res, 404, { error: 'Job not found' })
        return true
      }

      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      })
      res.write(`data: ${JSON.stringify({ type: 'connected', sessionId: job.sessionId })}\n\n`)

      if (job.status !== 'running') {
        res.write(`data: ${JSON.stringify({ type: 'constellation:completed', status: job.status })}\n\n`)
        res.end()
        return true
      }

      const HEARTBEAT_MS = 15_000
      const STATUS_POLL_MS = 2_000

      const heartbeat = setInterval(() => {
        if (!res.writableEnded) res.write(': heartbeat\n\n')
      }, HEARTBEAT_MS)

      const statusPoll = setInterval(() => {
        if (job.status !== 'running') {
          cleanup()
          if (!res.writableEnded) {
            res.write(`data: ${JSON.stringify({ type: 'constellation:completed', status: job.status })}\n\n`)
            res.end()
          }
        }
      }, STATUS_POLL_MS)

      // WHY: Forward EventBus events to SSE so watchViaSSE gets real-time corpus/topology events
      const CONSTELLATION_EVENT_TYPES = [
        'corpus:sweep', 'corpus:pattern', 'corpus:intervention',
        'corpus:spawn-evaluated', 'corpus:synthesis',
        'topology:updated', 'topology:link_formed', 'topology:link_dissolved',
        'topology:cluster_formed', 'topology:cluster_dissolved',
      ]
      const eventBus = daemon.eventBus
      const eventHandlers: Array<{ type: string; handler: (evt: any) => void }> = []

      if (eventBus?.on) {
        for (const evtType of CONSTELLATION_EVENT_TYPES) {
          const handler = (evt: any) => {
            // WHY: Only forward events for this specific constellation session
            if (evt.constellationId !== job.sessionId && evt.teamId !== job.sessionId) return
            if (res.writableEnded) return
            try {
              res.write(`data: ${JSON.stringify({ type: evtType, ...evt, timestamp: Date.now() })}\n\n`)
            } catch { /* ignore write errors on closed connections */ }
          }
          eventBus.on(evtType, handler)
          eventHandlers.push({ type: evtType, handler })
        }
      }

      const timeoutSecs = Math.min(parseInt(url.searchParams.get('timeout') || '600', 10), 600)
      const timeout = setTimeout(() => {
        cleanup()
        if (!res.writableEnded) {
          res.write(`data: ${JSON.stringify({ type: 'timeout' })}\n\n`)
          res.end()
        }
      }, timeoutSecs * 1000)

      function cleanup() {
        clearInterval(heartbeat)
        clearInterval(statusPoll)
        clearTimeout(timeout)
        for (const { type: evtType, handler } of eventHandlers) {
          eventBus?.off?.(evtType, handler)
        }
        eventHandlers.length = 0
      }

      req.on('close', cleanup)
      return true
    }

    if (method === 'GET' && !subAction) {
      const job = findJob(id)
      if (!job) {
        sendJSON(res, 404, { error: 'Job not found' })
        return true
      }
      if (job.status === 'running') {
        sendJSON(res, 200, {
          jobId: job.id,
          sessionId: job.sessionId,
          status: 'running',
          goal: job.goal,
          startedAt: job.startedAt,
          durationMs: Date.now() - job.startedAt,
        })
      } else {
        // Defensive wrapper around serialization
        let serializedResult: Record<string, unknown> | undefined
        try {
          serializedResult = job.result ? serializeConstellationResult(job.result) : undefined
        } catch (err) {
          // Defensive: serializeConstellationResult is non-throwing, but guard anyway
          logger.warn('Failed to serialize constellation result', { sessionId: job.sessionId, error: String(err) })
        }

        sendJSON(res, 200, {
          jobId: job.id,
          sessionId: job.sessionId,
          status: job.status,
          goal: job.goal,
          startedAt: job.startedAt,
          completedAt: job.completedAt,
          durationMs: (job.completedAt ?? Date.now()) - job.startedAt,
          result: serializedResult,
          error: job.error ?? undefined,
        })
      }
      return true
    }
  }

  return false
}
