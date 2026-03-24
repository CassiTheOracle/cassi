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
import type { BlackboardChannel } from '../../types/flux-team.js'

const VALID_CHANNELS = new Set<BlackboardChannel>(['findings', 'concerns', 'decisions', 'artifacts', 'requests'])


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
const HEARTBEAT_INTERVAL_MS = 15_000

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

/**
 * Load a persisted blackboard snapshot from HelixStore for completed sessions.
 * Returns undefined if the store is not available or session not found.
 */
function loadPersistedBlackboard(daemon: any, sessionId: string): unknown | undefined {
  try {
    // Access the HelixStore via the wired helix orchestrator's internal state
    // The daemon doesn't expose the store directly, so we try dynamic import + open
    const { HelixStore } = require('../intelligence/helix/helix-store.js')
    const store = HelixStore.open(daemon.logger.child('helix-store-reader'))
    const session = store.getSession(sessionId)
    store.close()
    return session?.blackboard ?? undefined
  } catch {
    return undefined
  }
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
          job.error = String(err)
          logger.error('helix:project:failed', { error: String(err), sessionId, jobId })
        })

        sendJSON(res, 200, { jobId, sessionId, status: 'running' })
      } catch (err) {
        logger.error('helix:project:request-error', { error: String(err) })
        sendJSON(res, 500, { error: String(err) })
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
    return true
  }

  // ── GET /helix/:id/progress ─────────────────────────────────────────
  if (method === 'GET' && subRoute === 'progress') {
    if (!helix) {
      sendJSON(res, 503, { error: 'Helix not initialized' })
      return true
    }
    const job = findHelixJob(id)
    const sessionId = job?.sessionId ?? id
    const progress = helix.getActiveProgress(sessionId)
    if (!progress) {
      sendJSON(res, 404, { error: 'Session not found or not active' })
      return true
    }
    sendJSON(res, 200, progress)
    return true
  }

  // ── GET /helix/:id/blackboard (supports ?summary=true, ?channel=X, ?limit=N)
  if (method === 'GET' && subRoute === 'blackboard') {
    if (!helix) {
      sendJSON(res, 503, { error: 'Helix not initialized' })
      return true
    }
    const job = findHelixJob(id)
    const sessionId = job?.sessionId ?? id
    const wantSummary = url.searchParams.get('summary') === 'true'
    const channelFilter = url.searchParams.get('channel') as BlackboardChannel | null
    const limitParam = url.searchParams.get('limit')
    const limit = limitParam ? parseInt(limitParam, 10) : undefined

    if (channelFilter && !VALID_CHANNELS.has(channelFilter)) {
      sendJSON(res, 400, { error: `Invalid channel. Must be one of: ${[...VALID_CHANNELS].join(', ')}` })
      return true
    }

    if (channelFilter) {
      const entries = helix.getActiveChannel(sessionId, channelFilter, limit)
      if (!entries) {
        const persisted = loadPersistedBlackboard(daemon, sessionId) as any
        if (persisted?.channels?.[channelFilter]) {
          const ch = persisted.channels[channelFilter]
          const sliced = limit ? ch.slice(-limit) : ch
          sendJSON(res, 200, { channel: channelFilter, entries: sliced })
          return true
        }
        sendJSON(res, 404, { error: 'Session not found or blackboard not active' })
        return true
      }
      sendJSON(res, 200, { channel: channelFilter, entries })
      return true
    }

    if (wantSummary) {
      const summary = helix.getActiveSummary(sessionId)
      if (!summary) {
        // Fallback: try loading from persisted HelixStore for completed sessions
        const persisted = loadPersistedBlackboard(daemon, sessionId)
        if (persisted) {
          sendJSON(res, 200, { sessionId, source: 'persisted', blackboard: persisted })
          return true
        }
        sendJSON(res, 404, { error: 'Session not found or blackboard not active' })
        return true
      }
      sendJSON(res, 200, summary)
      return true
    }

    const bb = helix.getActiveBlackboard(sessionId)
    if (!bb) {
      // Fallback: try loading from persisted HelixStore for completed sessions
      const persisted = loadPersistedBlackboard(daemon, sessionId)
      if (persisted) {
        sendJSON(res, 200, persisted)
        return true
      }
      sendJSON(res, 404, { error: 'Session not found or blackboard not active' })
      return true
    }
    sendJSON(res, 200, bb)
    return true
  }

  // ── GET /helix/:id/stream — SSE event stream ────────────────────────
  if (method === 'GET' && subRoute === 'stream') {
    const timeoutSecs = Math.min(parseInt(url.searchParams.get('timeout') || '300', 10), 600)

    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    })

    const job = findHelixJob(id)
    if (!job) {
      res.write(`data: ${JSON.stringify({ event: 'error', message: 'Job not found' })}\n\n`)
      res.end()
      return true
    }

    if (job.status !== 'running') {
      res.write(`data: ${JSON.stringify({ event: 'helix:completed', status: job.status, result: job.result, error: job.error })}\n\n`)
      res.end()
      return true
    }

    const heartbeat = setInterval(() => {
      if (!res.writableEnded) res.write(': heartbeat\n\n')
    }, HEARTBEAT_INTERVAL_MS)

    const poll = setInterval(() => {
      if (job.status !== 'running') {
        cleanup()
        res.write(`data: ${JSON.stringify({ event: 'helix:completed', status: job.status, result: job.result, error: job.error })}\n\n`)
        res.end()
      }
    }, 2000)

    const timeout = setTimeout(() => {
      cleanup()
      if (!res.writableEnded) {
        res.write(`data: ${JSON.stringify({ event: 'timeout' })}\n\n`)
        res.end()
      }
    }, timeoutSecs * 1000)

    function cleanup() {
      clearInterval(heartbeat)
      clearInterval(poll)
      clearTimeout(timeout)
    }

    req.on('close', cleanup)
    return true
  }

  // ── GET /helix/:id — Get job result ─────────────────────────────────
  if (method === 'GET' && !subRoute) {
    const job = findHelixJob(id)
    if (!job) {
      sendJSON(res, 404, { error: 'Job not found' })
      return true
    }
    sendJSON(res, 200, {
      id: job.id,
      sessionId: job.sessionId,
      status: job.status,
      goal: job.goal,
      startedAt: job.startedAt,
      completedAt: job.completedAt,
      result: job.result,
      error: job.error,
    })
    return true
  }

  return false
}
