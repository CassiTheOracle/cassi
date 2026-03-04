import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'

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

export async function handleTeamsRoutes(
  deps: TeamsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, url, parts, sseConnections, sseConnectionId, resolveLatestTeamId, buildHandoffContext } = deps

  if (parts[0] !== 'teams') return false

  const to = daemon.intelligence?.teamOrchestrator as any

  // POST /teams
  if (parts.length === 1 && method === 'POST') {
    try {
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
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
          logger.debug('[admin-api] buildHandoffContext failed, using raw goal', { error: String(err) })
        }
      }

      const config = {
        goal: enrichedGoal,
        name: body.name || undefined,
        budget: {
          maxTokens: body.maxTokens || 500_000,
          maxAgents: body.maxAgents || 5,
          maxDepth: body.maxDepth || 4,
          maxDurationMs: body.maxDurationMs || 60 * 60_000,
        },
        checkpoint: {
          mode: body.checkpointMode || 'cassi',
          budgetThresholdPct: body.budgetThresholdPct || 50,
          completedGoalsInterval: body.completedGoalsInterval || 3,
          autoApproveTimeoutMs: body.autoApproveTimeoutMs || 5 * 60_000,
        },
        provider: body.provider || undefined,
        defaultProvider: body.provider
          ? { providerId: body.provider, model: body.model || undefined }
          : undefined,
        allowDestructive: body.allowDestructive || false,
        supervisorSessionId: body.sessionId || undefined,
      }

      const team = to.createTeam(config)
      sendJSON(res, 201, {
        teamId: team.id,
        status: team.status || 'created',
        coordinatorAgentId: team.coordinatorAgentId || null,
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
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const teams = to.listAllTeams().map((t: any) => ({
        id: t.id,
        status: t.status,
        goal: t.config?.goal,
        startedAt: t.startedAt,
        completedAt: t.completedAt,
        agentCount: t.agentIds?.length || 0,
        coordinatorAgentId: t.coordinatorAgentId,
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
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const teamId = url.searchParams.get('teamId') || undefined
      let resolvedTeamId = teamId
      if (!resolvedTeamId) {
        const all = to.listAllTeams()
        const active = all.find((t: any) => t.status === 'running' || t.status === 'paused')
        resolvedTeamId = active?.id || all[all.length - 1]?.id
      }
      if (!resolvedTeamId) {
        sendJSON(res, 404, { error: 'No teams found' })
        return true
      }

      const status = to.getTeamStatus(resolvedTeamId)
      if (!status) {
        sendJSON(res, 404, { error: `Team ${resolvedTeamId} not found` })
        return true
      }

      sendJSON(res, 200, status)
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /teams/tree
  if (parts.length === 2 && parts[1] === 'tree' && method === 'GET') {
    try {
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const teamId = url.searchParams.get('teamId') || undefined
      let resolvedTeamId = teamId
      if (!resolvedTeamId) {
        const all = to.listAllTeams()
        const active = all.find((t: any) => t.status === 'running' || t.status === 'paused')
        resolvedTeamId = active?.id || all[all.length - 1]?.id
      }
      if (!resolvedTeamId) {
        sendJSON(res, 404, { error: 'No teams found' })
        return true
      }

      const goalTree = to.getGoalTree(resolvedTeamId)
      if (!goalTree) {
        sendJSON(res, 404, { error: `Team ${resolvedTeamId} has no goal tree` })
        return true
      }

      sendJSON(res, 200, {
        teamId: resolvedTeamId,
        tree: goalTree.renderTree(),
        progress: goalTree.getProgressReport(),
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
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const body = await parseBody(req)
      const teamId = body?.teamId || resolveLatestTeamId(to)
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId is required (or no active teams found)' })
        return true
      }

      to.pauseTeam(teamId)
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
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const body = await parseBody(req)
      const teamId = body?.teamId || resolveLatestTeamId(to)
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId is required (or no active teams found)' })
        return true
      }

      to.resumeTeam(teamId)
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
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const body = await parseBody(req)
      const teamId = body?.teamId || resolveLatestTeamId(to)
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId is required (or no active teams found)' })
        return true
      }

      await to.cancelTeam(teamId, body?.reason || 'Cancelled by user')
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
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const teamId = url.searchParams.get('teamId') || undefined
      const checkpoints = to.listPendingCheckpoints(teamId)
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
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
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

      to.handleSupervisorResponse(checkpointId, {
        action: body.action,
        message: body.message || undefined,
      })
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
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }

      let teamId = url.searchParams.get('teamId') || ''
      if (!teamId) teamId = resolveLatestTeamId(to) || ''
      if (!teamId) {
        sendJSON(res, 404, { error: 'No active teams found' })
        return true
      }

      const team = to.getTeam(teamId)
      if (!team) {
        sendJSON(res, 404, { error: `Team ${teamId} not found` })
        return true
      }

      const limitParam = url.searchParams.get('limit')
      const limit = limitParam ? parseInt(limitParam, 10) : 50

      const eventLog = to.getTeamEventLog(teamId) || []
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
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }

      const teamId = url.searchParams.get('teamId') || ''
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId query parameter is required' })
        return true
      }

      const team = to.getTeam(teamId)
      if (!team) {
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
        } catch {}
      }

      const status = to.getTeamStatus(teamId)
      if (status) {
        sendSSE('snapshot', {
          teamId,
          team: status.team,
          goalTree: status.goalTree,
          progress: status.progress,
          activeAgents: status.activeAgents,
          pendingCheckpoints: status.pendingCheckpoints,
        })
      }

      res.write(': connected\n\n')

      const isTeamEvent = (event: any): boolean => {
        if (event.teamId === teamId) return true
        if (event.agentId && to.agentToTeam?.get(event.agentId) === teamId) return true
        return false
      }

      const teamEventTypes = [
        'team:started', 'team:completed', 'team:failed', 'team:cancelled',
        'team:paused', 'team:resumed', 'team:budget:warning', 'team:checkpoint',
        'agent:spawned', 'agent:completed', 'agent:error',
        'autonomy:loop_started', 'autonomy:loop_stopped',
        'autonomy:loop_paused', 'autonomy:loop_resumed',
        'autonomy:iteration', 'autonomy:iteration_error',
        'autonomy:delegation_requested', 'autonomy:blocked',
      ]

      const handlers: Array<{ type: string; handler: (e: any) => void }> = []
      for (const eventType of teamEventTypes) {
        const handler = (e: any) => {
          if (!isTeamEvent(e)) return
          sendSSE(e.type || eventType, e)
        }
        daemon.bus.on(eventType, handler)
        handlers.push({ type: eventType, handler })
      }

      const ping = setInterval(() => {
        try { res.write(': ping\n\n') } catch { clearInterval(ping) }
      }, 15_000)
      try { (ping as any).unref?.() } catch {}

      req.on('close', () => {
        clearInterval(ping)
        sseConnections.delete(connId)
        for (const { type, handler } of handlers) {
          try { daemon.bus.off(type, handler) } catch {}
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
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const teamId = parts[1]
      const team = to.getTeam(teamId)
      if (!team) {
        sendJSON(res, 404, { error: `Team ${teamId} not found` })
        return true
      }

      const goalTree = to.getGoalTree(teamId)
      sendJSON(res, 200, {
        team,
        goalTree: goalTree?.renderTree(),
        progress: goalTree?.getProgressReport(),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /teams/agent/message
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'message' && method === 'POST') {
    try {
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const ds = daemon.sessionDigestStore
      if (!ds) {
        sendJSON(res, 503, { error: 'SessionDigestStore not available' })
        return true
      }
      const body = await parseBody(req)
      if (!body?.toAgentId || !body?.message) {
        sendJSON(res, 400, { error: 'toAgentId and message are required' })
        return true
      }
      const fromSessionId = body.fromSessionId || body.agentId ? `agent:${body.agentId}` : 'external'
      const toSessionId = `agent:${body.toAgentId}`
      const msgId = ds.sendMessage(toSessionId, fromSessionId, body.message)
      sendJSON(res, 200, { messageId: msgId, toAgentId: body.toAgentId })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /teams/agent/result
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'result' && method === 'GET') {
    try {
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const agentId = url.searchParams.get('agentId')
      if (!agentId) {
        sendJSON(res, 400, { error: 'agentId query parameter is required' })
        return true
      }

      for (const team of to.listAllTeams()) {
        const goalId = team.agentGoalMap?.[agentId]
        if (!goalId) continue
        const goal = team.goals?.[goalId]
        if (!goal) {
          sendJSON(res, 404, { error: `Goal for agent ${agentId} not found` })
          return true
        }

        sendJSON(res, 200, {
          agentId,
          teamId: team.id,
          goalTitle: goal.title,
          status: goal.status,
          result: goal.result ?? null,
        })
        return true
      }
      sendJSON(res, 404, { error: `Agent ${agentId} not found in any team` })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /teams/agent/list
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'list' && method === 'GET') {
    try {
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const teamId = url.searchParams.get('teamId')
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId query parameter is required' })
        return true
      }
      const team = to.getTeam(teamId)
      if (!team) {
        sendJSON(res, 404, { error: `Team ${teamId} not found` })
        return true
      }

      const agents = (team.agentIds || []).map((aid: string) => {
        const goalId = team.agentGoalMap?.[aid]
        const goal = goalId ? team.goals?.[goalId] : undefined
        return {
          agentId: aid,
          isCoordinator: aid === team.coordinatorAgentId,
          goalId: goalId ?? null,
          goalTitle: goal?.title ?? null,
          goalStatus: goal?.status ?? 'unknown',
          roleHint: goal?.roleHint ?? (aid === team.coordinatorAgentId ? 'team-coordinator' : null),
        }
      })
      sendJSON(res, 200, { teamId, agents })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /teams/agent/update-plan
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'update-plan' && method === 'POST') {
    try {
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const body = await parseBody(req)
      if (!body?.teamId) {
        sendJSON(res, 400, { error: 'teamId is required' })
        return true
      }

      const goalTree = to.getGoalTree(body.teamId)
      if (!goalTree) {
        sendJSON(res, 404, { error: `Goal tree for team ${body.teamId} not found` })
        return true
      }

      const results: any[] = []
      if (body.addGoals && Array.isArray(body.addGoals)) {
        for (const g of body.addGoals) {
          if (!g.title || !g.parentGoalId) continue
          const newId = goalTree.addSubGoal(g.parentGoalId, {
            title: g.title,
            description: g.description || '',
            roleHint: g.roleHint || undefined,
          })
          results.push({ action: 'added', goalId: newId, title: g.title })
        }
      }
      if (body.updateGoals && Array.isArray(body.updateGoals)) {
        for (const g of body.updateGoals) {
          if (!g.goalId) continue
          if (g.status) goalTree.updateStatus(g.goalId, g.status, g.result || undefined)
          results.push({ action: 'updated', goalId: g.goalId, status: g.status })
        }
      }

      sendJSON(res, 200, { teamId: body.teamId, results })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /teams/agent/complete-goal
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'complete-goal' && method === 'POST') {
    try {
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const body = await parseBody(req)
      if (!body?.teamId || !body?.goalId) {
        sendJSON(res, 400, { error: 'teamId and goalId are required' })
        return true
      }

      const goalTree = to.getGoalTree(body.teamId)
      if (!goalTree) {
        sendJSON(res, 404, { error: `Goal tree for team ${body.teamId} not found` })
        return true
      }

      goalTree.updateStatus(body.goalId, body.success === false ? 'failed' : 'completed', {
        summary: body.summary || '',
        output: body.result || body.summary || '',
        tokensUsed: body.tokensUsed || 0,
        durationMs: body.durationMs || 0,
        error: body.error || undefined,
      })

      sendJSON(res, 200, { teamId: body.teamId, goalId: body.goalId, status: body.success === false ? 'failed' : 'completed' })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /teams/agent/goal-tree
  if (parts.length === 3 && parts[1] === 'agent' && parts[2] === 'goal-tree' && method === 'GET') {
    try {
      if (!to) {
        sendJSON(res, 503, { error: 'TeamOrchestrator not available' })
        return true
      }
      const teamId = url.searchParams.get('teamId')
      if (!teamId) {
        sendJSON(res, 400, { error: 'teamId query parameter is required' })
        return true
      }

      const goalTree = to.getGoalTree(teamId)
      if (!goalTree) {
        sendJSON(res, 404, { error: `Goal tree for team ${teamId} not found` })
        return true
      }

      sendJSON(res, 200, {
        teamId,
        tree: goalTree.renderTree(),
        progress: goalTree.getProgressReport(),
      })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
