/**
 * Meditation Admin API Routes
 *
 * Endpoints for controlling and observing the meditation system.
 *
 *   GET  /meditation/status       — current meditation state and session info
 *   GET  /meditation/live         — compact live observability: last 3 steps per explorer, self-awareness, insights
 *   GET  /meditation/live/full   — untruncated full stream of every explorer step
 *   GET  /meditation/insights     — meditation insights stored in memory (most recent first)
 *   GET  /meditation/self-awareness — all self-awareness detections with full context
 *   GET  /meditation/prompts      — all prompts with Thompson params and scores
 *   GET  /meditation/leaderboard  — prompts ranked by avg score + category stats
 *   GET  /meditation/scores       — recent evaluation scores
 *   GET  /meditation/evolution    — mutation temperature, Cassi vs library performance
 *   GET  /meditation/search?q=    — full-text search on evaluation narratives
 *   POST /meditation/start        — force-start a meditation session (accepts style param)
 *   POST /meditation/stop         — force-stop a running meditation session
 */

import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'


interface MeditationDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, status: number, data: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}


export async function handleMeditationRoutes(
  deps: MeditationDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { daemon, logger, sendJSON } = deps
  const url = new URL(req.url ?? '/', `http://${req.headers.host}`)
  const pathname = url.pathname

  if (!pathname.startsWith('/meditation')) return false

  const parts = pathname.split('/').filter(Boolean)
  const meditation = daemon.intelligence?.meditation

  if (!meditation) {
    sendJSON(res, 503, { error: 'Meditation controller not available' })
    return true
  }

  // GET /meditation/status
  if (method === 'GET' && parts.length === 2 && parts[1] === 'status') {
    try {
      const state = meditation.getState()
      const session = meditation.getSession()

      const selfAwareness = meditation.getSelfAwarenessDetections()

      sendJSON(res, 200, {
        state,
        selfAwarenessDetections: selfAwareness.length,
        session: session ? {
          constellationId: session.constellationId,
          style: session.style,
          startedAt: new Date(session.startedAt).toISOString(),
          durationMs: Date.now() - session.startedAt,
          engrams: session.engrams,
          consolidations: session.consolidations,
          prompts: session.prompts,
        } : null,
      })
      return true
    } catch (err) {
      logger.warn('Meditation status failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /meditation/start
  if (method === 'POST' && parts.length === 2 && parts[1] === 'start') {
    try {
      const body = await deps.parseBody(req)
      const style = body?.style as string | undefined
      const session = await meditation.triggerMeditation(style as any)
      if (session) {
        sendJSON(res, 200, {
          started: true,
          constellationId: session.constellationId,
          style: session.style,
          startedAt: new Date(session.startedAt).toISOString(),
        })
      } else {
        sendJSON(res, 200, {
          started: false,
          reason: meditation.getState() === 'meditating' ? 'already meditating' : 'controller not ready',
        })
      }
      return true
    } catch (err) {
      logger.warn('Meditation start failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // POST /meditation/stop
  if (method === 'POST' && parts.length === 2 && parts[1] === 'stop') {
    try {
      await meditation.forceStop()
      sendJSON(res, 200, { stopped: true })
      return true
    } catch (err) {
      logger.warn('Meditation stop failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /meditation/self-awareness — all self-awareness detections from the current session
  if (method === 'GET' && parts.length === 2 && parts[1] === 'self-awareness') {
    try {
      const detections = meditation.getSelfAwarenessDetections()
      sendJSON(res, 200, {
        count: detections.length,
        detections: detections.map((d: any) => ({
          timestamp: new Date(d.timestamp).toISOString(),
          helixId: d.helixId,
          step: d.stepIndex,
          confidence: d.confidence,
          fileTrigger: d.fileTrigger ?? null,
          reasoningMatch: d.reasoningMatch ?? null,
          reasoning: d.fullReasoning,
          toolCalls: d.toolCalls,
          knowledgeDelta: d.knowledgeDelta,
        })),
      })
      return true
    } catch (err) {
      logger.warn('Meditation self-awareness endpoint failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /meditation/insights — meditation insights from memory (most recent first)
  if (method === 'GET' && parts.length === 2 && parts[1] === 'insights') {
    try {
      const mem = daemon.intelligence?.memory
      if (!mem) {
        sendJSON(res, 503, { error: 'Memory system not available' })
        return true
      }
      const limitParam = url.searchParams.get('limit')
      const limit = limitParam ? parseInt(limitParam, 10) : 20
      // Fetch a generous window of recent entries then filter to meditation insights
      const recent = await mem.getRecent(200)
      const insights = recent
        .filter((e: any) => e.metadata?.source === 'meditation' && e.type === 'insight')
        .slice(0, limit)
        .map((e: any) => ({
          id: e.id,
          content: e.content,
          tags: e.metadata?.tags?.filter((t: string) => t !== 'meditation' && t !== 'insight') ?? [],
          importance: e.metadata?.importance ?? 5,
          createdAt: e.createdAt,
        }))
      sendJSON(res, 200, {
        count: insights.length,
        insights,
      })
      return true
    } catch (err) {
      logger.warn('Meditation insights endpoint failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /meditation/live/full — untruncated full stream of every explorer step
  if (method === 'GET' && parts.length === 3 && parts[1] === 'live' && parts[2] === 'full') {
    try {
      const state = meditation.getState()
      const session = meditation.getSession()
      if (state !== 'meditating' || !session) {
        sendJSON(res, 200, { state, full: null })
        return true
      }

      const orchestrator = daemon.intelligence?.constellation
      const tree = orchestrator?.getLiveTree?.(session.constellationId)
      if (!tree) {
        sendJSON(res, 200, { state, full: { error: 'CorpusTree not available' } })
        return true
      }

      const branches = tree.getAllBranches()
      const explorers = branches.map((b: any) => {
        const steps = (b.steps ?? []).map((s: any, i: number) => {
          const a = s.annotation ?? {}
          return {
            step: i + 1,
            timestamp: a.timestamp ?? s.pushedAt,
            reasoning: a.discoveries ?? [],
            decisions: a.decisions ?? [],
            hypothesis: a.hypothesis ?? null,
            toolCalls: (s.toolCalls ?? []).map((tc: any) => ({
              name: tc.name,
              args: tc.args,
            })),
            toolSummary: a.outputs ?? [],
            knowledgeDelta: a.knowledgeDelta ?? null,
            nextSteps: a.nextSteps ?? [],
          }
        })

        return {
          helixId: b.helixId,
          goal: b.goal,
          status: b.status,
          steps,
        }
      })

      sendJSON(res, 200, {
        state,
        full: {
          constellationId: session.constellationId,
          style: session.style,
          durationMs: Date.now() - session.startedAt,
          prompts: session.prompts,
          explorers,
          totalSteps: tree.totalStepCount?.() ?? 0,
        },
      })
      return true
    } catch (err) {
      logger.warn('Meditation live/full failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /meditation/live — rich live observability during meditation (compact, last 3 steps)
  if (method === 'GET' && parts.length === 2 && parts[1] === 'live') {
    try {
      const state = meditation.getState()
      const session = meditation.getSession()
      if (state !== 'meditating' || !session) {
        sendJSON(res, 200, { state, live: null })
        return true
      }

      const constellationId = session.constellationId
      const orchestrator = daemon.intelligence?.constellation
      const tree = orchestrator?.getLiveTree?.(constellationId)

      const live: Record<string, unknown> = {
        constellationId,
        style: session.style,
        durationMs: Date.now() - session.startedAt,
        prompts: session.prompts,
        engrams: session.engrams,
        consolidations: session.consolidations,
      }

      // CorpusTree data — what the explorers are doing
      if (tree) {
        const branches = tree.getAllBranches()
        live.explorers = branches.map((b: any) => {
          const steps = b.steps ?? []
          const recentSteps = steps.slice(-3)
          return {
            helixId: b.helixId,
            goal: b.goal,
            status: b.status,
            totalSteps: steps.length,
            recentActivity: recentSteps.map((s: any) => {
              const a = s.annotation ?? {}
              return {
                discoveries: a.discoveries?.slice(0, 3) ?? [],
                toolCalls: (s.toolCalls ?? []).map((tc: any) => `${tc.name}(${(tc.args ?? '').slice(0, 80)})`),
                knowledgeDelta: (a.knowledgeDelta ?? '').slice(0, 200),
              }
            }),
          }
        })

        // Digests
        const digests = tree.getAllDigests?.() ?? []
        if (digests.length > 0) {
          live.digests = digests.map((d: any) => ({
            helixId: d.helixId,
            approach: d.approach,
            progress: d.progress,
            keyFindings: d.keyFindings?.slice(0, 5),
            filesActive: d.filesActive?.slice(0, 10),
            score: d.rollingScore ?? d.score,
          }))
        }

        live.totalSteps = tree.totalStepCount?.() ?? 0
        live.activeBranches = tree.activeBranchCount?.() ?? 0
      }

      // Self-awareness detections
      const detections = meditation.getSelfAwarenessDetections()
      if (detections.length > 0) {
        live.selfAwareness = detections.map((d: any) => ({
          timestamp: new Date(d.timestamp).toISOString(),
          helixId: d.helixId,
          step: d.stepIndex,
          confidence: d.confidence,
          fileTrigger: d.fileTrigger?.category ?? null,
          reasoningMatch: d.reasoningMatch?.label ?? null,
          excerpt: d.reasoningMatch?.excerpt ?? d.fullReasoning.slice(0, 200),
        }))
      }

      // Meditation insights from memory
      const mem = daemon.intelligence?.memory
      if (mem) {
        try {
          const recent = await mem.getRecent(100)
          const insights = recent
            .filter((e: any) => e.metadata?.source === 'meditation' && e.type === 'insight')
            .slice(0, 5)
            .map((e: any) => ({
              content: e.content,
              tags: e.metadata?.tags?.filter((t: string) => t !== 'meditation' && t !== 'insight') ?? [],
              createdAt: e.createdAt,
            }))
          if (insights.length > 0) live.insights = insights
        } catch {
          // best-effort — don't fail the live endpoint if memory search fails
        }
      }

      sendJSON(res, 200, { state, live })
      return true
    } catch (err) {
      logger.warn('Meditation live failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /meditation/prompts
  if (method === 'GET' && parts.length === 2 && parts[1] === 'prompts') {
    const store = meditation.getStore()
    if (!store) {
      sendJSON(res, 503, { error: 'Meditation store not available' })
      return true
    }
    try {
      sendJSON(res, 200, { prompts: store.getAllPrompts() })
      return true
    } catch (err) {
      logger.warn('Meditation prompts failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /meditation/leaderboard
  if (method === 'GET' && parts.length === 2 && parts[1] === 'leaderboard') {
    const store = meditation.getStore()
    if (!store) {
      sendJSON(res, 503, { error: 'Meditation store not available' })
      return true
    }
    try {
      sendJSON(res, 200, {
        leaderboard: store.getPromptLeaderboard(),
        categories: store.getCategoryStats(),
        stats: store.getOverallStats(),
      })
      return true
    } catch (err) {
      logger.warn('Meditation leaderboard failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /meditation/evolution
  if (method === 'GET' && parts.length === 2 && parts[1] === 'evolution') {
    const store = meditation.getStore()
    if (!store) {
      sendJSON(res, 503, { error: 'Meditation store not available' })
      return true
    }
    try {
      sendJSON(res, 200, {
        mutationTemperature: store.getMutationTemperature(),
        mutationPerformance: store.getMutationPerformance(),
        cassiPromptCount: store.getCassiPromptCount(),
        stats: store.getOverallStats(),
      })
      return true
    } catch (err) {
      logger.warn('Meditation evolution failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /meditation/scores
  if (method === 'GET' && parts.length === 2 && parts[1] === 'scores') {
    const store = meditation.getStore()
    if (!store) {
      sendJSON(res, 503, { error: 'Meditation store not available' })
      return true
    }
    try {
      const limitParam = url.searchParams.get('limit')
      const limit = limitParam ? parseInt(limitParam, 10) : 20
      sendJSON(res, 200, { scores: store.getRecentScores(limit) })
      return true
    } catch (err) {
      logger.warn('Meditation scores failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  // GET /meditation/search?q=...
  if (method === 'GET' && parts.length === 2 && parts[1] === 'search') {
    const store = meditation.getStore()
    if (!store) {
      sendJSON(res, 503, { error: 'Meditation store not available' })
      return true
    }
    try {
      const q = url.searchParams.get('q') ?? ''
      if (!q) {
        sendJSON(res, 400, { error: 'Missing query parameter: q' })
        return true
      }
      const limitParam = url.searchParams.get('limit')
      const limit = limitParam ? parseInt(limitParam, 10) : 20
      sendJSON(res, 200, { results: store.searchEvaluations(q, limit) })
      return true
    } catch (err) {
      logger.warn('Meditation search failed', { error: String(err) })
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  sendJSON(res, 404, { error: `Unknown meditation route: ${pathname}` })
  return true
}
