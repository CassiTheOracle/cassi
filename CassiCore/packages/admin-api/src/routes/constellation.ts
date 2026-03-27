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
      const { goal, context, template, postures, maxHelixes, maxDepth, timeoutMs } = body ?? {}

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
        timeoutMs,
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

  // GET /constellation/sessions — List active sessions
  if (method === 'GET' && parts.length === 2 && parts[1] === 'sessions') {
    const sessions = [...constellationJobs.values()]
      .filter(j => j.status === 'running')
      .map(j => j.sessionId)
    sendJSON(res, 200, { sessions })
    return true
  }

  // Routes with an ID: /constellation/:id/...
  if (parts.length >= 2 && parts[1] !== 'jobs' && parts[1] !== 'sessions') {
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

    // GET /constellation/:id/progress — Live progress report
    if (method === 'GET' && subAction === 'progress') {
      const job = findJob(id)
      if (!job) {
        sendJSON(res, 404, { error: 'Job not found' })
        return true
      }
      const orchestrator = daemon.intelligence?.constellation
      const progress = orchestrator?.getProgress?.(job.sessionId)
      sendJSON(res, 200, {
        sessionId: job.sessionId,
        status: job.status,
        goal: job.goal,
        startedAt: job.startedAt,
        durationMs: Date.now() - job.startedAt,
        progress: progress ?? null,
      })
      return true
    }

    // GET /constellation/:id/tree — Corpus reasoning tree snapshot
    if (method === 'GET' && subAction === 'tree') {
      const job = findJob(id)
      if (!job) {
        sendJSON(res, 404, { error: 'Job not found' })
        return true
      }
      const orchestrator = daemon.intelligence?.constellation
      const tree = orchestrator?.getTree?.(job.sessionId)
      if (!tree) {
        sendJSON(res, 200, { sessionId: job.sessionId, tree: null, message: 'Tree not available (session may have completed)' })
      } else {
        sendJSON(res, 200, { sessionId: job.sessionId, tree })
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
          result: job.result ?? undefined,
          error: job.error ?? undefined,
        })
      }
      return true
    }
  }

  return false
}
