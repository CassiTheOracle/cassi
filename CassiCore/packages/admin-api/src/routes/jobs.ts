/**
 * Admin API routes for the Background Job Manager.
 *
 * Endpoints:
 *   GET  /jobs          — List all jobs
 *   POST /jobs          — Create and start a job
 *   GET  /jobs/:id      — Get job status and result
 *   DELETE /jobs/:id    — Cancel a running job
 *   GET  /jobs/:id/output — Get full stdout/stderr (from file dump)
 */

import type http from 'node:http'
import type { ILogger } from '@cassicore/foundation'
import type { JobManager } from '@cassicore/jobs'

interface JobsRouteContext {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  parts: string[]
}

export async function handleJobsRoutes(
  ctx: JobsRouteContext,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string,
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, parts } = ctx

  if (parts[0] !== 'jobs') return false

  const jm: JobManager | undefined = daemon.jobManager
  if (!jm) {
    sendJSON(res, 503, { error: 'JobManager not available' })
    return true
  }

  // GET /jobs — list all jobs
  if (parts.length === 1 && method === 'GET') {
    const jobs = jm.list()
    sendJSON(res, 200, { jobs: jobs.map(j => ({
      jobId: j.jobId,
      label: j.label,
      status: j.status,
      exitCode: j.exitCode,
      duration: j.duration,
      startedAt: j.startedAt,
      completedAt: j.completedAt,
    }))})
    return true
  }

  // POST /jobs — create and start a job
  if (parts.length === 1 && method === 'POST') {
    try {
      const body = await parseBody(req)
      if (!body?.command) {
        sendJSON(res, 400, { error: 'body.command is required' })
        return true
      }

      const result = jm.start({
        command: body.command,
        label: body.label,
        timeoutMs: body.timeout ? body.timeout * 1000 : undefined,
        cwd: body.cwd,
        notify: body.notify !== false,
        sessionId: body.sessionId,
      })

      sendJSON(res, 201, result)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /jobs/:id — get job status
  if (parts.length === 2 && method === 'GET') {
    const jobId = parts[1]
    const result = jm.get(jobId)
    if (!result) {
      sendJSON(res, 404, { error: `Job ${jobId} not found` })
      return true
    }
    sendJSON(res, 200, result)
    return true
  }

  // DELETE /jobs/:id — cancel a running job
  if (parts.length === 2 && method === 'DELETE') {
    const jobId = parts[1]
    const cancelled = jm.cancel(jobId)
    if (!cancelled) {
      sendJSON(res, 404, { error: `Job ${jobId} not found or not running` })
      return true
    }
    sendJSON(res, 200, { jobId, status: 'cancelled' })
    return true
  }

  // GET /jobs/:id/output — get full output from file dump
  if (parts.length === 3 && parts[2] === 'output' && method === 'GET') {
    const jobId = parts[1]
    const result = jm.get(jobId)
    if (!result) {
      sendJSON(res, 404, { error: `Job ${jobId} not found` })
      return true
    }

    const output: Record<string, string> = {
      stdout: result.stdout,
      stderr: result.stderr,
    }

    // If there are file dumps with more content, read those
    const fs = await import('node:fs/promises')
    if (result.stdoutFile) {
      try {
        output.stdoutFull = await fs.readFile(result.stdoutFile, 'utf-8')
      } catch { /* file gone */ }
    }
    if (result.stderrFile) {
      try {
        output.stderrFull = await fs.readFile(result.stderrFile, 'utf-8')
      } catch { /* file gone */ }
    }

    sendJSON(res, 200, { jobId, ...output })
    return true
  }

  return false
}
