/**
 * Admin API routes for the self-improvement loop.
 *
 * GET  /improvement/status     — orchestrator state, queue depth, gate mode, metrics
 * GET  /improvement/journal    — query improvement journal entries
 * GET  /improvement/scenarios  — list all scenarios (hardcoded + generated)
 * GET  /improvement/learnings  — recent learnings from the journal
 * POST /improvement/trigger    — manually trigger a cycle or submit a proposal
 * POST /improvement/scenario   — manually create a scenario from a hypothesis
 */

import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'

export interface ImprovementRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  pathname: string
}

export async function handleImprovementRoutes(
  deps: ImprovementRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { daemon, sendJSON, parseBody, pathname } = deps

  // Get the orchestrator from the intelligence layer
  const orchestrator = daemon?.intelligence?.improvementOrchestrator
  if (!orchestrator) {
    if (pathname.startsWith('/improvement')) {
      sendJSON(res, 503, { error: 'Improvement orchestrator not available' })
      return true
    }
    return false
  }

  // GET /improvement/status
  if (method === 'GET' && pathname === '/improvement/status') {
    try {
      const status = orchestrator.getStatus()
      sendJSON(res, 200, status)
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to get status', detail: String(err) })
    }
    return true
  }

  // GET /improvement/journal
  if (method === 'GET' && pathname === '/improvement/journal') {
    try {
      const { url } = deps
      const trigger = url.searchParams.get('trigger') ?? undefined
      const verdict = url.searchParams.get('verdict') ?? undefined
      const adaptation = url.searchParams.get('adaptation') ?? undefined
      const since = url.searchParams.get('since') ? Number(url.searchParams.get('since')) : undefined
      const limit = url.searchParams.get('limit') ? Number(url.searchParams.get('limit')) : 50

      const entries = orchestrator.queryJournal({ trigger, verdict, adaptation, since, limit })
      sendJSON(res, 200, { entries, count: entries.length })
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to query journal', detail: String(err) })
    }
    return true
  }

  // GET /improvement/scenarios
  if (method === 'GET' && pathname === '/improvement/scenarios') {
    try {
      const scenarios = orchestrator.getScenarios()
      sendJSON(res, 200, {
        scenarios: scenarios.map((s: any) => ({
          name: s.name,
          description: s.description,
          triggerType: s.triggerType,
          tags: s.tags,
          runCount: s.runCount,
          passCount: s.passCount,
          stale: s.stale,
          createdAt: s.createdAt,
        })),
        count: scenarios.length,
      })
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to list scenarios', detail: String(err) })
    }
    return true
  }

  // GET /improvement/learnings
  if (method === 'GET' && pathname === '/improvement/learnings') {
    try {
      const { url } = deps
      const limit = url.searchParams.get('limit') ? Number(url.searchParams.get('limit')) : 10
      const learnings = orchestrator.getRecentLearnings(limit)
      sendJSON(res, 200, { learnings, count: learnings.length })
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to get learnings', detail: String(err) })
    }
    return true
  }

  // POST /improvement/trigger
  if (method === 'POST' && pathname === '/improvement/trigger') {
    try {
      const body = await parseBody(req)

      if (body?.proposal) {
        // Submit a manual proposal
        const proposal = {
          id: `manual-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          trigger: 'manual' as const,
          source: body.proposal.source ?? 'admin-api',
          proposalClass: body.proposal.proposalClass ?? 'heuristic',
          hypothesis: body.proposal.hypothesis ?? 'Manual improvement proposal',
          adaptation: body.proposal.adaptation ?? 'parameter_tune',
          config: body.proposal.config ?? {},
          dedupeKey: body.proposal.dedupeKey,
          riskLevel: body.proposal.riskLevel ?? 'low',
          confidence: body.proposal.confidence ?? 0.8,
          evidence: body.proposal.evidence,
          verificationScenarios: body.proposal.verificationScenarios,
          timestamp: Date.now(),
        }
        orchestrator.propose(proposal)
        sendJSON(res, 200, { ok: true, proposalId: proposal.id, message: 'Proposal queued' })
      } else {
        // Trigger a manual cycle execution
        const result = await orchestrator.execute(0)
        sendJSON(res, 200, { ok: true, result: result ?? 'No actions taken' })
      }
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to trigger improvement', detail: String(err) })
    }
    return true
  }

  // POST /improvement/scenario
  if (method === 'POST' && pathname === '/improvement/scenario') {
    try {
      const body = await parseBody(req)

      if (!body?.name || !body?.description || !body?.testMessage) {
        sendJSON(res, 400, { error: 'Missing required fields: name, description, testMessage' })
        return true
      }

      const generator = orchestrator.getGenerator()
      const scenario = generator.generateFromHypothesis({
        name: body.name,
        description: body.description,
        testMessage: body.testMessage,
        expectedEvents: body.expectedEvents,
        forbiddenEvents: body.forbiddenEvents,
      })

      sendJSON(res, 200, { ok: true, scenario: { name: scenario.name, description: scenario.description, stepCount: scenario.steps.length } })
    } catch (err) {
      sendJSON(res, 500, { error: 'Failed to create scenario', detail: String(err) })
    }
    return true
  }

  return false
}
