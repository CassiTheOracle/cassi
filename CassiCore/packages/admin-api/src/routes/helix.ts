/**
 * Helix Admin API Routes
 *
 * Async job-based endpoints for Helix inverted-pyramid pattern.
 *
 * Routes:
 *   POST /helix             — Start a Helix session (returns jobId)
 *   POST /helix/project     — Alias for POST /helix
 *   POST /helix/:id/cancel  — Cancel a running Helix session
 *   GET  /helix/:id         — Get job result (poll until complete)
 *   GET  /helix/health      — Helix health check
 *   GET  /helix/jobs        — List recent Helix jobs (in-memory)
 *   GET  /helix/sessions    — List active sessions
 *   GET  /helix/:id/progress — Live progress report
 *   GET  /helix/:id/stream  — SSE event stream for a Helix session
 *   GET  /helix/:id/blackboard — Blackboard snapshot
 */

import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'
import type { HelixResult } from '../intelligence/helix/types.js'


interface HelixJob {
  id: string
  sessionId: string
  status: 'running' | 'completed' | 'failed'
  goal: string
  startedAt: number
  completedAt?: number
  result?: HelixResult
  error?: string
}

interface HelixDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}


const helixJobs = new Map<string, HelixJob>()
const JOB_TTL_MS = 60 * 60 * 1000 // 1 hour
const MAX_JOBS = 50

// SSE heartbeat interval for event streams
const SSE_HEARTBEAT_MS = 15_000

function generateJobId(): string {
  return `helix-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function pruneOldJobs(): void {
  const now = Date.now()
  for (const [id, job] of helixJobs) {
    if (now - job.startedAt > JOB_TTL_MS) {
      helixJobs.delete(id)
    }
  }
  if (helixJobs.size > MAX_JOBS) {
    const sorted = [...helixJobs.entries()].sort((a, b) => a[1].startedAt - b[1].startedAt)
    const toRemove = sorted.slice(0, sorted.length - MAX_JOBS)
    for (const [id] of toRemove) {
      helixJobs.delete(id)
    }
  }
}

function findHelixJob(idOrSessionId: string): HelixJob | undefined {
  return helixJobs.get(idOrSessionId) ?? [...helixJobs.values()].find(job => job.sessionId === idOrSessionId)
}


export function handleHelixRoutes(
  deps: HelixDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): boolean {
  const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`)
  const pathname = url.pathname
  const { daemon, logger, sendJSON, parseBody } = deps

  // Extract helix orchestrator
  const intelligence = daemon.intelligence
  const helix = intelligence?.helix

  // ── POST /helix OR POST /helix/project — Start a session ────────────
  if (method === 'POST' && (pathname === '/helix' || pathname === '/helix/project')) {
    if (!helix) {
      sendJSON(res, 503, { error: 'Helix not initialized' })
      return true
    }

    ;(async () => {
      try {
        pruneOldJobs()
        const body = (await parseBody(req)) as Record<string, unknown>
        const goal = body.goal as string
        if (!goal) {
          sendJSON(res, 400, { error: 'goal is required' })
          return
        }

        const sessionId = (body.sessionId as string) || `helix-${Date.now()}`
        const jobId = generateJobId()

        const job: HelixJob = {
          id: jobId,
          sessionId,
          status: 'running',
          goal,
          startedAt: Date.now(),
        }
        helixJobs.set(jobId, job)

        // Fire and forget — result tracked via job
        helix.project({
          goal,
          context: body.context as string | undefined,
          parentSessionId: body.parentSessionId as string | undefined,
          sessionId,
          jobId,
          taskType: body.taskType as string | undefined,
        }).then((result: HelixResult) => {
          job.status = 'completed'
          job.completedAt = Date.now()
          job.result = result
        }).catch((err: unknown) => {
          job.status = 'failed'
          job.completedAt = Date.now()
          job.error = err instanceof Error ? (err.stack ?? err.message) : String(err)
          logger.error('helix:project:failed', { error: err instanceof Error ? (err.stack ?? String(err)) : String(err), sessionId, jobId })
        })

        sendJSON(res, 200, { jobId, sessionId, status: 'running' })
      } catch (err) {
        logger.error('helix:project:request-error', { error: err instanceof Error ? (err.stack ?? String(err)) : String(err) })
        sendJSON(res, 500, { error: err instanceof Error ? (err.stack ?? String(err)) : String(err) })
      }
    })()
    return true
  }

  // ── GET /helix/health ───────────────────────────────────────────────
  if (method === 'GET' && pathname === '/helix/health') {
    if (!helix) {
      sendJSON(res, 503, { error: 'Helix not initialized' })
      return true
    }
    sendJSON(res, 200, helix.getHealth())
    return true
  }

  // ── GET /helix/jobs ─────────────────────────────────────────────────
  if (method === 'GET' && pathname === '/helix/jobs') {
    const jobs = [...helixJobs.values()]
      .sort((a, b) => b.startedAt - a.startedAt)
      .map(j => ({
        id: j.id,
        sessionId: j.sessionId,
        status: j.status,
        goal: j.goal.slice(0, 200),
        startedAt: j.startedAt,
        completedAt: j.completedAt,
        error: j.error,
      }))
    sendJSON(res, 200, { jobs })
    return true
  }

  // ── GET /helix/sessions ─────────────────────────────────────────────
  if (method === 'GET' && pathname === '/helix/sessions') {
    sendJSON(res, 200, { sessions: helix?.getActiveSessions() ?? [] })
    return true
  }

  // ── Routes with :id parameter ───────────────────────────────────────
  const helixRouteMatch = pathname.match(/^\/helix\/([^/]+)(?:\/(.+))?$/)
  if (!helixRouteMatch) return false

  const id = helixRouteMatch[1]
  const subRoute = helixRouteMatch[2]

  // Skip known top-level routes
  if (['health', 'jobs', 'sessions', 'project'].includes(id)) return false

  // ── POST /helix/:id/cancel ──────────────────────────────────────────
  if (method === 'POST' && subRoute === 'cancel') {
    if (!helix) {
      sendJSON(res, 503, { error: 'Helix not initialized' })
      return true
    }
    const job = findHelixJob(id)
    const sessionId = job?.sessionId ?? id
    const cancelled = helix.cancel(sessionId)
    if (job && cancelled) {
      job.status = 'failed'
      job.completedAt = Date.now()
      job.error = 'Cancelled by user'
    }
    sendJSON(res, 200, { cancelled, sessionId })

[output truncated: 1158 bytes]