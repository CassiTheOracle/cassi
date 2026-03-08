import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'
import type { TriadTeamOrchestrator } from '../intelligence/triad-team/index.js'
import type { TriadTeamSession, TriadTeamEventType } from '../../types/triad-team.js'

export interface TeamsRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  parts: string[]
  sseConnections: Map<string, { res: http.ServerResponse; sessionId: string; connectedAt: number }>
  sseConnectionId: { value: number }
  resolveLatestTeamId: (to: any) => string | undefined
  buildHandoffContext?: (sessionId: string) => Promise<string>
}

/**
 * Resolve the triad-team orchestrator from the daemon.
 * Falls back to legacy teamOrchestrator if triadTeam is not available.
 */
function getOrchestrator(daemon: any): TriadTeamOrchestrator | undefined {
  return daemon.intelligence?.triadTeam as TriadTeamOrchestrator | undefined
}

/**
 * Resolve a team ID, defaulting to the most recent active or last team.
 */
function resolveTeamId(tt: TriadTeamOrchestrator, teamId?: string): string | undefined {
  if (teamId) return teamId
  const teams = tt.listTeams()
  const active = teams.find(t => t.status === 'running' || t.status === 'paused' || t.status === 'planning')
  return active?.id ?? teams[teams.length - 1]?.id
}

/**
 * Serialize a TriadTeamSession for JSON transport.
 * Maps are not JSON-serializable, so we convert them.
 */
function serializeSession(session: TriadTeamSession): Record<string, unknown> {
  return {
    id: session.id,
    status: session.status,
    config: session.config,
    budget: session.budget,
    rootCellId: session.rootCellId,
    cells: Object.fromEntries(session.cells),
    cellGoalMap: Object.fromEntries(session.cellGoalMap),
    createdAt: session.createdAt,
    startedAt: session.startedAt,
    completedAt: session.completedAt,
    finalResult: session.finalResult,
    eventLog: session.eventLog,
  }
}

export async function handleTeamsRoutes(
  deps: TeamsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, url, parts, sseConnections, sseConnectionId, buildHandoffContext } = deps

  if (parts[0] !== 'teams') return false

  const tt = getOrchestrator(daemon)

  // POST /teams
  if (parts.length === 1 && method === 'POST') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const body = await parseBody(req)
      if (!body?.goal) {
        sendJSON(res, 400, { error: 'goal is required' })
        return true
      }

      let enrichedGoal = body.goal
      if (body.sessionId && buildHandoffContext) {
        try {
          const handoffCtx = await buildHandoffContext(body.sessionId)
          if (handoffCtx) {
            enrichedGoal = handoffCtx + body.goal
          }
        } catch (err) {
          logger.debug('buildHandoffContext failed, using raw goal', { error: String(err) })
        }
      }

      // Handle both nested provider object and flat provider/model fields
      let providerConfig: { providerId?: string; model?: string; temperature?: number; maxTokens?: number; thinking?: 'none' | 'low' | 'medium' | 'high' } | undefined
      if (body.provider && typeof body.provider === 'object') {
        // Nested: { provider: { providerId: "...", model: "..." } }
        providerConfig = {
          providerId: body.provider.providerId,
          model: body.provider.model || body.model || undefined,
          temperature: body.provider.temperature ?? body.temperature,
          maxTokens: body.provider.maxTokens ?? body.maxTokens,
          thinking: body.provider.thinking ?? body.thinking,
        }
      } else if (body.provider && typeof body.provider === 'string') {
        // Flat: { provider: "github-copilot", model: "gpt-5-mini" }
        providerConfig = {
          providerId: body.provider,
          model: body.model || undefined,
          temperature: body.temperature,
          maxTokens: body.maxTokens,
          thinking: body.thinking,
        }
      }

      // Also handle budget from nested body.budget or flat fields
      const budgetConfig = body.budget && typeof body.budget === 'object'
        ? {
            maxTokens: body.budget.maxTokens || body.maxTokens || 2_000_000,
            maxCells: body.budget.maxCells || body.maxCells || body.maxAgents || 20,
            maxDepth: body.budget.maxDepth || body.maxDepth || 3,
            maxDurationMs: body.budget.maxDurationMs || body.maxDurationMs || 4 * 60 * 60_000,
            maxToolIterationsPerMember: body.budget.maxToolIterationsPerMember || body.maxToolIterationsPerMember || 50,
          }
        : {
            maxTokens: body.maxTokens || 2_000_000,
            maxCells: body.maxCells || body.maxAgents || 20,
            maxDepth: body.maxDepth || 3,
            maxDurationMs: body.maxDurationMs || 4 * 60 * 60_000,
            maxToolIterationsPerMember: body.maxToolIterationsPerMember || 50,
          }

      // Handle checkpoint from nested or flat
      const checkpointConfig = body.checkpoint && typeof body.checkpoint === 'object'
        ? {
            mode: body.checkpoint.mode || 'none',
            supervisorSessionId: body.checkpoint.supervisorSessionId || body.sessionId || undefined,
            autoApproveTimeoutMs: body.checkpoint.autoApproveTimeoutMs || 5 * 60_000,
            budgetThresholds: body.checkpoint.budgetThresholds || [0.5, 0.75, 0.9],
            completedGoalsInterval: body.checkpoint.completedGoalsInterval,
          }
        : body.checkpointMode ? {
            mode: body.checkpointMode === 'cassi' ? 'cassi' : body.checkpointMode === 'human' ? 'human' : 'none',
            supervisorSessionId: body.sessionId || undefined,
            autoApproveTimeoutMs: body.autoApproveTimeoutMs || 5 * 60_000,
            budgetThresholds: body.budgetThresholds || [0.5, 0.75, 0.9],
            completedGoalsInterval: body.completedGoalsInterval,
          } : undefined

      const teamId = await tt.createTeam({
        goal: enrichedGoal,
        name: body.name || undefined,
        provider: providerConfig,
        budget: budgetConfig,
        checkpoint: checkpointConfig,
        maxDepth: budgetConfig.maxDepth,
        maxCells: budgetConfig.maxCells,
        maxDurationMs: body.maxDurationMs || 4 * 60 * 60_000,
        maxToolIterationsPerMember: body.maxToolIterationsPerMember || 50,
        metadata: { sessionId: body.sessionId },
      })

      sendJSON(res, 201, {
        teamId,
        status: 'initializing',
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /teams
  if (parts.length === 1 && method === 'GET') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const teams = tt.listTeams().map(t => ({
        id: t.id,
        status: t.status,
        name: t.name,
        cellCount: t.cellCount,
        tokensUsed: t.tokensUsed,
        createdAt: t.createdAt,
      }))
      sendJSON(res, 200, { teams })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /teams/status
  if (parts.length === 2 && parts[1] === 'status' && method === 'GET') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const teamId = url.searchParams.get('teamId') || undefined
      const resolvedTeamId = resolveTeamId(tt, teamId ?? undefined)
      if (!resolvedTeamId) {
        sendJSON(res, 404, { error: 'No teams found' })
        return true
      }

      const session = tt.getTeamStatus(resolvedTeamId)
      if (!session) {
        sendJSON(res, 404, { error: `Team ${resolvedTeamId} not found` })
        return true
      }

      sendJSON(res, 200, serializeSession(session))
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /teams/tree
  if (parts.length === 2 && parts[1] === 'tree' && method === 'GET') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const teamId = url.searchParams.get('teamId') || undefined
      const resolvedTeamId = resolveTeamId(tt, teamId ?? undefined)
      if (!resolvedTeamId) {
        sendJSON(res, 404, { error: 'No teams found' })
        return true
      }

      const session = tt.getTeamStatus(resolvedTeamId)
      if (!session) {
        sendJSON(res, 404, { error: `Team ${resolvedTeamId} not found` })
        return true
      }

      // Build a tree visualization from cell hierarchy
      const tree = buildCellTree(session)
      const progress = buildCellProgress(session)

      sendJSON(res, 200, {
        teamId: resolvedTeamId,
        tree,
        progress,
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /teams/pause
  if (parts.length === 2 && parts[1] === 'pause' && method === 'POST') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const body = await parseBody(req)
      const teamId = body?.teamId || resolveTeamId(tt)
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId is required (or no active teams found)' })
        return true
      }

      await tt.pauseTeam(teamId)
      sendJSON(res, 200, { teamId, status: 'paused' })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /teams/resume
  if (parts.length === 2 && parts[1] === 'resume' && method === 'POST') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const body = await parseBody(req)
      const teamId = body?.teamId || resolveTeamId(tt)
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId is required (or no active teams found)' })
        return true
      }

      await tt.resumeTeam(teamId)
      sendJSON(res, 200, { teamId, status: 'running' })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /teams/cancel
  if (parts.length === 2 && parts[1] === 'cancel' && method === 'POST') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const body = await parseBody(req)
      const teamId = body?.teamId || resolveTeamId(tt)
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId is required (or no active teams found)' })
        return true
      }

      await tt.cancelTeam(teamId)
      sendJSON(res, 200, { teamId, status: 'cancelled' })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /teams/checkpoints
  if (parts.length === 2 && parts[1] === 'checkpoints' && method === 'GET') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const teamId = url.searchParams.get('teamId') || undefined
      const checkpoints = tt.getPendingCheckpoints(teamId)
      sendJSON(res, 200, { checkpoints })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /teams/checkpoints/:checkpointId
  if (parts.length === 3 && parts[1] === 'checkpoints' && method === 'POST') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const checkpointId = parts[2]
      const body = await parseBody(req)
      if (!body?.action) {
        sendJSON(res, 400, { error: 'action is required (approve|reject|steer)' })
        return true
      }
      if (!['approve', 'reject', 'steer'].includes(body.action)) {
        sendJSON(res, 400, { error: 'action must be approve, reject, or steer' })
        return true
      }

      await tt.respondToCheckpoint(checkpointId, body.action, body.message || undefined)
      sendJSON(res, 200, { checkpointId, action: body.action })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /teams/events
  if (parts.length === 2 && parts[1] === 'events' && method === 'GET') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }

      let teamId = url.searchParams.get('teamId') || ''
      if (!teamId) teamId = resolveTeamId(tt) || ''
      if (!teamId) {
        sendJSON(res, 404, { error: 'No active teams found' })
        return true
      }

      const session = tt.getTeamStatus(teamId)
      if (!session) {
        sendJSON(res, 404, { error: `Team ${teamId} not found` })
        return true
      }

      const limitParam = url.searchParams.get('limit')
      const limit = limitParam ? parseInt(limitParam, 10) : 50

      const eventLog = session.eventLog || []
      const events = eventLog.slice(-limit)

      sendJSON(res, 200, { teamId, total: eventLog.length, events })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /teams/stream
  if (parts.length === 2 && parts[1] === 'stream' && method === 'GET') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }

      const teamId = url.searchParams.get('teamId') || ''
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId query parameter is required' })
        return true
      }

      const session = tt.getTeamStatus(teamId)
      if (!session) {
        sendJSON(res, 404, { error: `Team ${teamId} not found` })
        return true
      }

      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      })

      const connId = `team_sse_${++sseConnectionId.value}`
      sseConnections.set(connId, { res, sessionId: `team:${teamId}`, connectedAt: Date.now() })

      const sendSSE = (eventType: string, payload: unknown) => {
        try {
          res.write(`event: ${eventType}\n`)
          res.write(`data: ${JSON.stringify(payload)}\n\n`)
        } catch { /* SSE write failure */ }
      }

      // Send initial snapshot
      sendSSE('snapshot', serializeSession(session))
      res.write(': connected\n\n')

      // Subscribe to triad-team events
      const triadEventTypes: TriadTeamEventType[] = [
        'triad-team:created', 'triad-team:started', 'triad-team:planning',
        'triad-team:plan-complete', 'triad-team:cell-spawned', 'triad-team:cell-phase',
        'triad-team:cell-completed', 'triad-team:cell-failed', 'triad-team:cell-degraded',
        'triad-team:synthesis', 'triad-team:completed', 'triad-team:failed',
        'triad-team:cancelled', 'triad-team:paused', 'triad-team:resumed',
        'triad-team:checkpoint', 'triad-team:checkpoint:approved',
        'triad-team:checkpoint:rejected', 'triad-team:budget-warning',
      ]

      const handlers: Array<{ type: string; handler: (e: any) => void }> = []
      for (const eventType of triadEventTypes) {
        const handler = (e: any) => {
          if (e.teamId !== teamId) return
          sendSSE(e.type || eventType, e)
        }
        daemon.bus.on(eventType, handler)
        handlers.push({ type: eventType, handler })
      }

      const ping = setInterval(() => {
        try { res.write(': ping\n\n') } catch { clearInterval(ping) }
      }, 15_000)
      try { (ping as any).unref?.() } catch { /* unref not available */ }

      req.on('close', () => {
        clearInterval(ping)
        sseConnections.delete(connId)
        for (const { type, handler } of handlers) {
          try { daemon.bus.off(type, handler) } catch { /* cleanup failure */ }
        }
      })

      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /teams/:teamId
  if (parts.length === 2 && method === 'GET') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const teamId = parts[1]
      const session = tt.getTeamStatus(teamId)
      if (!session) {
        sendJSON(res, 404, { error: `Team ${teamId} not found` })
        return true
      }

      sendJSON(res, 200, serializeSession(session))
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // ── POST /teams/benchmark — Automated benchmark run with test verification ──
  if (parts.length === 2 && parts[1] === 'benchmark' && method === 'POST') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }

      const body = await parseBody(req)
      if (!body?.goal) {
        sendJSON(res, 400, { error: 'body.goal is required' })
        return true
      }

      // SSE response for long-running benchmark
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      })

      let ended = false
      const sendSSE = (eventType: string, payload: unknown) => {
        if (ended || !res.writable) return
        try {
          res.write(`event: ${eventType}\ndata: ${JSON.stringify(payload)}\n\n`)
        } catch { ended = true }
      }

      req.on('close', () => { ended = true })

      // Parse config — same logic as POST /teams
      let providerConfig: { providerId?: string; model?: string; temperature?: number; maxTokens?: number; thinking?: 'none' | 'low' | 'medium' | 'high' } | undefined
      if (body.provider && typeof body.provider === 'object') {
        providerConfig = {
          providerId: body.provider.providerId,
          model: body.provider.model || body.model || undefined,
        }
      } else if (body.provider && typeof body.provider === 'string') {
        providerConfig = { providerId: body.provider, model: body.model || undefined }
      }

      const budgetConfig = body.budget && typeof body.budget === 'object'
        ? { ...body.budget }
        : { maxTokens: body.maxTokens || 300_000, maxCells: 3, maxDepth: body.maxDepth || 1, maxDurationMs: 600_000, maxToolIterationsPerMember: 50 }

      sendSSE('benchmark:start', { goal: body.goal, provider: providerConfig })

      const benchStart = Date.now()

      // Create and start team
      const teamId = await tt.createTeam({
        goal: body.goal,
        name: body.name || 'Benchmark',
        provider: providerConfig,
        budget: budgetConfig,
        checkpoint: { mode: 'none' as const },
        maxDepth: budgetConfig.maxDepth || 1,
        maxCells: budgetConfig.maxCells || 3,
      })

      sendSSE('benchmark:team-created', { teamId })

      // Subscribe to team events and forward them
      const triadEventTypes = [
        'triad-team:started', 'triad-team:planning', 'triad-team:plan-complete',
        'triad-team:cell-spawned', 'triad-team:cell-phase', 'triad-team:cell-completed',
        'triad-team:cell-failed', 'triad-team:completed', 'triad-team:failed',
        'triad-team:cancelled',
      ]
      const handlers: Array<{ type: string; handler: (e: any) => void }> = []
      for (const eventType of triadEventTypes) {
        const handler = (e: any) => {
          if (e.teamId === teamId) {
            sendSSE('team-event', { type: eventType, ...e })
          }
        }
        daemon.bus.on(eventType as any, handler)
        handlers.push({ type: eventType, handler })
      }

      // Wait for team completion
      const teamResult = await new Promise<any>((resolve) => {
        const checkInterval = setInterval(() => {
          const status = tt.getTeamStatus(teamId)
          if (!status) {
            clearInterval(checkInterval)
            resolve({ status: 'error', error: 'Team not found' })
            return
          }
          if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
            clearInterval(checkInterval)
            resolve(serializeSession(status))
          }
        }, 2000)

        // Timeout safety
        setTimeout(() => {
          clearInterval(checkInterval)
          const status = tt.getTeamStatus(teamId)
          resolve(status ? serializeSession(status) : { status: 'timeout' })
        }, (budgetConfig.maxDurationMs || 600_000) + 30_000)
      })

      // Unsubscribe from events
      for (const { type, handler } of handlers) {
        daemon.bus.off(type as any, handler)
      }

      const teamDuration = Date.now() - benchStart

      sendSSE('benchmark:team-complete', {
        teamId,
        status: teamResult.status,
        duration: teamDuration,
        tokens: teamResult.budget?.tokensUsed || 0,
        cells: teamResult.budget?.cellsSpawned || 0,
        result: teamResult.finalResult?.slice(0, 500),
      })

      // Run tests if test paths specified
      let testResults: any = null
      const testPaths: string[] = body.testPaths || body.testPath ? [body.testPaths || body.testPath].flat() : []

      if (testPaths.length > 0) {
        sendSSE('benchmark:testing', { testPaths })

        const { spawn } = await import('node:child_process')
        for (const testPath of testPaths) {
          try {
            const testOutput = await new Promise<string>((resolve) => {
              let output = ''
              const proc = spawn('npx', ['vitest', 'run', testPath, '--reporter=verbose', '--no-color'], {
                cwd: process.cwd(),
                env: { ...process.env, FORCE_COLOR: '0' },
              })
              const timer = setTimeout(() => { proc.kill(); resolve(output + '\n(timeout)') }, 60_000)
              proc.stdout.on('data', (d: Buffer) => { output += d.toString() })
              proc.stderr.on('data', (d: Buffer) => { output += d.toString() })
              proc.on('close', () => { clearTimeout(timer); resolve(output) })
            })

            // Parse test output
            const passMatch = testOutput.match(/(\d+)\s+passed/)
            const failMatch = testOutput.match(/(\d+)\s+failed/)
            testResults = {
              testPath,
              passed: passMatch ? parseInt(passMatch[1]) : 0,
              failed: failMatch ? parseInt(failMatch[1]) : 0,
              output: testOutput.slice(0, 3000),
            }

            sendSSE('benchmark:test-result', testResults)
          } catch (err) {
            sendSSE('benchmark:test-error', { testPath, error: String(err) })
          }
        }
      }

      // Cleanup generated files if requested
      const generatedFiles: string[] = []
      if (body.cleanup) {
        const fs = await import('node:fs/promises')
        const path = await import('node:path')
        for (const testPath of testPaths) {
          // Find matching files using simple file existence checks
          // Handle both exact paths and basic glob patterns
          try {
            if (testPath.includes('*')) {
              // For glob patterns, list directory and match
              const dir = path.dirname(testPath)
              const pattern = path.basename(testPath).replace(/\*/g, '.*').replace(/\?/g, '.')
              const regex = new RegExp(`^${pattern}$`)
              const dirPath = path.join(process.cwd(), dir)
              const entries = await fs.readdir(dirPath).catch(() => [] as string[])
              for (const entry of entries) {
                if (regex.test(entry)) {
                  const relPath = path.join(dir, entry)
                  generatedFiles.push(relPath)
                  const implPath = relPath.replace('.test.ts', '.ts')
                  try { await fs.access(path.join(process.cwd(), implPath)); generatedFiles.push(implPath) } catch { }
                }
              }
            } else {
              // Exact path
              try { await fs.access(path.join(process.cwd(), testPath)); generatedFiles.push(testPath) } catch { }
              const implPath = testPath.replace('.test.ts', '.ts')
              try { await fs.access(path.join(process.cwd(), implPath)); generatedFiles.push(implPath) } catch { }
            }
          } catch { /* glob/list failed */ }
        }

        for (const file of generatedFiles) {
          try {
            await fs.unlink(path.join(process.cwd(), file))
          } catch { /* file already gone */ }
        }

        if (generatedFiles.length > 0) {
          sendSSE('benchmark:cleanup', { files: generatedFiles })
        }
      }

      // Final benchmark report
      const report = {
        teamId,
        status: teamResult.status,
        duration: teamDuration,
        tokens: teamResult.budget?.tokensUsed || 0,
        cells: teamResult.budget?.cellsSpawned || 0,
        phases: (teamResult.eventLog || [])
          .filter((e: any) => e.type === 'triad-team:cell-phase')
          .map((e: any) => e.data?.phase),
        testResults,
        generatedFiles,
        result: teamResult.finalResult?.slice(0, 1000),
      }

      sendSSE('benchmark:complete', report)

      if (!ended) {
        res.end()
      }
      return true
    } catch (err) {
      if (!res.headersSent) {
        sendJSON(res, 500, { error: String(err) })
      }
      return true
    }
  }

  // ── Legacy agent-based endpoints (stubs for backward compatibility) ────

  // POST /teams/agent/message
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'message' && method === 'POST') {
    sendJSON(res, 410, { error: 'Agent messaging is not supported in triad-team mode. Cells coordinate via shared workspace.' })
    return true
  }

  // GET /teams/agent/result
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'result' && method === 'GET') {
    sendJSON(res, 410, { error: 'Agent results are not supported in triad-team mode. Use GET /teams/status or GET /teams/:teamId instead.' })
    return true
  }

  // GET /teams/agent/list
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'list' && method === 'GET') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const teamId = url.searchParams.get('teamId')
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId query parameter is required' })
        return true
      }
      const session = tt.getTeamStatus(teamId)
      if (!session) {
        sendJSON(res, 404, { error: `Team ${teamId} not found` })
        return true
      }

      // Return cells as the "agent" equivalent
      const cells = [...session.cells.values()].map(c => ({
        cellId: c.cellId,
        goalId: c.goalId,
        goalTitle: c.goalTitle,
        parentCellId: c.parentCellId,
        childCellIds: c.childCellIds,
        depth: c.depth,
        status: c.status,
        phase: c.phase,
        tokensUsed: c.tokensUsed,
        createdAt: c.createdAt,
        completedAt: c.completedAt,
      }))
      sendJSON(res, 200, { teamId, cells })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /teams/agent/update-plan — not applicable in triad-team mode
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'update-plan' && method === 'POST') {
    sendJSON(res, 410, { error: 'Plan updates are managed internally by triad cells. Use checkpoints for steering.' })
    return true
  }

  // POST /teams/agent/complete-goal — not applicable in triad-team mode
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'complete-goal' && method === 'POST') {
    sendJSON(res, 410, { error: 'Goal completion is managed internally by triad cells.' })
    return true
  }

  // GET /teams/agent/goal-tree — redirect to /teams/tree
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'goal-tree' && method === 'GET') {
    try {
      if (!tt) {
        sendJSON(res, 503, { error: 'TriadTeamOrchestrator not available' })
        return true
      }
      const teamId = url.searchParams.get('teamId')
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId query parameter is required' })
        return true
      }

      const session = tt.getTeamStatus(teamId)
      if (!session) {
        sendJSON(res, 404, { error: `Team ${teamId} not found` })
        return true
      }

      sendJSON(res, 200, {
        teamId,
        tree: buildCellTree(session),
        progress: buildCellProgress(session),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}

// ── Helper functions ─────────────────────────────────────────────────────────

/**
 * Build a text tree visualization from cell hierarchy.
 */
function buildCellTree(session: TriadTeamSession): string {
  const lines: string[] = []
  const rootInfo = session.cells.get(session.rootCellId)
  if (!rootInfo) return '(no cells)'

  function renderCell(cellId: string, prefix: string, isLast: boolean): void {
    const info = session.cells.get(cellId)
    if (!info) return

    const connector = isLast ? '└── ' : '├── '
    const statusIcon = getStatusIcon(info.status)
    const phaseInfo = info.phase !== 'idle' ? ` [${info.phase}]` : ''
    lines.push(`${prefix}${connector}${statusIcon} ${info.goalTitle}${phaseInfo} (${info.tokensUsed} tokens)`)

    const childPrefix = prefix + (isLast ? '    ' : '│   ')
    for (let i = 0; i < info.childCellIds.length; i++) {
      renderCell(info.childCellIds[i], childPrefix, i === info.childCellIds.length - 1)
    }
  }

  const statusIcon = getStatusIcon(rootInfo.status)
  const phaseInfo = rootInfo.phase !== 'idle' ? ` [${rootInfo.phase}]` : ''
  lines.push(`${statusIcon} ${rootInfo.goalTitle}${phaseInfo} (${rootInfo.tokensUsed} tokens)`)

  for (let i = 0; i < rootInfo.childCellIds.length; i++) {
    renderCell(rootInfo.childCellIds[i], '', i === rootInfo.childCellIds.length - 1)
  }

  return lines.join('\n')
}

/**
 * Build a progress report from cell statuses.
 */
function buildCellProgress(session: TriadTeamSession): Record<string, unknown> {
  let total = 0
  let completed = 0
  let failed = 0
  let inProgress = 0
  let blocked = 0

  for (const cell of session.cells.values()) {
    total++
    switch (cell.status) {
      case 'completed': completed++; break
      case 'failed': failed++; break
      case 'executing': case 'planning': case 'synthesizing': inProgress++; break
      case 'waiting': blocked++; break
    }
  }

  const completionPct = total > 0 ? Math.round((completed / total) * 100) : 0

  return { total, completed, failed, inProgress, blocked, completionPct }
}

/**
 * Get a status icon for display.
 */
function getStatusIcon(status: string): string {
  switch (status) {
    case 'completed': return '[DONE]'
    case 'failed': return '[FAIL]'
    case 'executing': return '[EXEC]'
    case 'planning': return '[PLAN]'
    case 'synthesizing': return '[SYNTH]'
    case 'waiting': return '[WAIT]'
    case 'initializing': return '[INIT]'
    case 'degraded': return '[DEGR]'
    case 'cancelled': return '[CANCEL]'
    default: return '[?]'
  }
}
