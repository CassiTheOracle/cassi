/**
 * Constellation Admin API Routes
 *
 * Async job-based endpoints for Constellation multi-Helix orchestration.
 *
 * Routes:
 *   POST /constellation             — Start a Constellation (returns jobId)
 *   POST /constellation/:id/cancel  — Cancel a running Constellation
 *   GET  /constellation/:id         — Get job result (poll until complete)
 *   GET  /constellation/jobs        — List recent Constellation jobs
 *   GET  /constellation/sessions    — List active sessions
 *   GET  /constellation/:id/progress — Live progress report
 *   GET  /constellation/:id/tree    — Corpus reasoning tree snapshot
 *   POST /constellation/:id/steer   — Send steering directive through Corpus
 *   GET  /constellation/:id/stream  — SSE event stream
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


// Archive Fallback Helpers

/**
 * Load a persisted tree snapshot from ConstellationStore for completed sessions.
 * Returns null if the store is not available or session not found.
 */
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

/**
 * Load a persisted progress snapshot from ConstellationStore for completed sessions.
 * Returns null if the store is not available or session not found.
 */
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

/**
 * Load a persisted session from ConstellationStore.
 * Returns undefined if the store is not available or session not found.
 */
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

/**
 * List sessions from ConstellationStore (includes archived).
 */
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

/**
 * Get session history from ConstellationStore.
 */
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

  // Must start with /constellation
  if (!pathname.startsWith('/constellation')) return false

  const parts = pathname.split('/').filter(Boolean)
  // parts[0] = 'constellation', parts[1] = id or action, parts[2] = sub-action

  // POST /constellation — Start a new Constellation
  if (method === 'POST' && parts.length === 1) {
    pruneOldJobs()
    try {
      const body = await parseBody(req)
      const { goal, context, template, postures, maxHelixes, maxDepth } = body ?? {}

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

      // Get the constellation orchestrator from the daemon
      const constellationOrchestrator = daemon.intelligence?.constellation
      if (!constellationOrchestrator) {
        sendJSON(res, 503, { error: 'Constellation orchestrator not available' })
        constellationJobs.delete(jobId)
        return true
      }

      // Launch constellation (non-blocking)
      constellationOrchestrator.project({
        goal,
        context,
        template: template ?? 'standard',
        postures,
        maxHelixes,
        maxDepth,
        sessionId,
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

  // GET /constellation/jobs — List recent jobs
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

  // GET /constellation/sessions — List sessions (includes archived by default)
  if (method === 'GET' && parts.length === 2 && parts[1] === 'sessions') {
    const includeArchived = url.searchParams.get('include_archived') !== 'false'
    const limit = parseInt(url.searchParams.get('limit') || '100', 10)
    const status = url.searchParams.get('status') || undefined

    // Get active sessions from in-memory jobs
    const activeSessions = [...constellationJobs.values()]
      .filter(j => j.status === 'running')
      .map(j => ({
        id: j.sessionId,
        goal: j.goal,
        status: j.status,
        startedAt: j.startedAt,
        source: 'live' as const,
      }))

    // Get archived sessions from store
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
        .filter(s => !activeSessions.some(a => a.id === s.id))  // Avoid duplicates
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

  // GET /constellation/history — Explicit archive query endpoint
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

  // Routes with an ID: /constellation/:id/...
  if (parts.length >= 2 && parts[1] !== 'jobs' && parts[1] !== 'sessions' && parts[1] !== 'history') {
    const id = parts[1]
    const subAction = parts[2]

    // POST /constellation/:id/cancel
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

    // POST /constellation/:id/steer — Send steering directive through Corpus
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

    // GET /constellation/:id/progress — Live progress report (with archive fallback)
    if (method === 'GET' && subAction === 'progress') {
      const job = findJob(id)

      // Try live state first
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

        // Fallback: try loading from persisted store for completed sessions
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

        // No progress available (but job exists)
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

      // Job not in memory — try loading directly from archive by session ID
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

    // GET /constellation/:id/tree — Corpus reasoning tree snapshot (with archive fallback)
    if (method === 'GET' && subAction === 'tree') {
      const job = findJob(id)

      // Try live state first
      if (job) {
        const orchestrator = daemon.intelligence?.constellation
        const tree = orchestrator?.getTree?.(job.sessionId)

        if (tree) {
          sendJSON(res, 200, { sessionId: job.sessionId, tree, source: 'live' })
          return true
        }

        // Fallback: try loading from persisted store for completed sessions
        const persisted = await loadPersistedTree(daemon, job.sessionId)
        if (persisted) {
          sendJSON(res, 200, { sessionId: job.sessionId, tree: persisted, source: 'archived' })
          return true
        }

        // No tree available (but job exists)
        sendJSON(res, 200, {
          sessionId: job.sessionId,
          tree: null,
          message: 'Tree not available (session may not have been archived)',
        })
        return true
      }

      // Job not in memory — try loading directly from archive by session ID
      const persisted = await loadPersistedTree(daemon, id)
      if (persisted) {
        sendJSON(res, 200, { sessionId: id, tree: persisted, source: 'archived' })
        return true
      }

      sendJSON(res, 404, { error: 'Session not found' })
      return true
    }

    // GET /constellation/:id/analyze — Deep post-mortem analysis
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

    // GET /constellation/:id/stream — SSE event stream
    if (method === 'GET' && subAction === 'stream') {
      const job = findJob(id)
      if (!job) {
        sendJSON(res, 404, { error: 'Job not found' })
        return true
      }

      // SSE headers
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      })
      res.write(`data: ${JSON.stringify({ type: 'connected', sessionId: job.sessionId })}\n\n`)

      // Poll for completion
      const interval = setInterval(() => {
        if (job.status !== 'running') {
          res.write(`data: ${JSON.stringify({ type: 'completed', status: job.status })}\n\n`)
          clearInterval(interval)
          res.end()
        } else {
          res.write(`data: ${JSON.stringify({ type: 'heartbeat', timestamp: Date.now() })}\n\n`)
        }
      }, 5000)

      req.on('close', () => {
        clearInterval(interval)
      })

      return true
    }

    // GET /constellation/:id — Job status/result
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
        sendJSON(res, 200, {
          jobId: job.id,
          sessionId: job.sessionId,
          status: job.status,
          goal: job.goal,
          startedAt: job.startedAt,
          completedAt: job.completedAt,
          durationMs: (job.completedAt ?? Date.now()) - job.startedAt,
          result: job.result ? serializeConstellationResult(job.result) : undefined,
          error: job.error ?? undefined,
        })
      }
      return true
    }
  }

  return false
}
