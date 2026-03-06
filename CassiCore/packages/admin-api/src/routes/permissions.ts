/**
 * Admin API — Permission Oracle routes.
 *
 * Endpoints for the graduated autonomy system:
 *   GET  /permissions/pending    — list pending approval requests
 *   POST /permissions/:id/approve — approve a pending request
 *   POST /permissions/:id/reject  — reject a pending request
 *   GET  /permissions/stats      — permission decision statistics
 *   GET  /permissions/log        — recent decision audit trail
 *   GET  /trust                  — trust summary across all domains
 *   GET  /trust/:domain          — trust score for a specific domain
 *   GET  /consequences/stats     — consequence estimator statistics
 */

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface PermissionsRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  url: URL
  parts: string[]
}

export async function handlePermissionsRoutes(
  deps: PermissionsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string,
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, parts } = deps

  // ── Permission Oracle routes ──────────────────────────────────────────

  // GET /permissions/pending — list pending human approval requests
  if (parts[0] === 'permissions' && parts[1] === 'pending' && method === 'GET' && parts.length === 2) {
    const oracle = daemon.intelligence?.permissionOracle
    if (!oracle) {
      sendJSON(res, 503, { error: 'Permission Oracle not available' })
      return true
    }
    sendJSON(res, 200, {
      pending: oracle.listPending(),
      count: oracle.getPendingCount(),
    })
    return true
  }

  // POST /permissions/:id/approve — approve a pending escalation
  if (parts[0] === 'permissions' && parts[2] === 'approve' && method === 'POST' && parts.length === 3) {
    const oracle = daemon.intelligence?.permissionOracle
    if (!oracle) {
      sendJSON(res, 503, { error: 'Permission Oracle not available' })
      return true
    }

    const id = parts[1]
    const body = await parseBody(req).catch(() => ({}))
    const responder = body?.responder || 'admin-api'

    const resolved = oracle.resolveApproval(id, true, responder)
    if (!resolved) {
      sendJSON(res, 404, { error: `Pending approval '${id}' not found (may have timed out)` })
      return true
    }

    sendJSON(res, 200, { approved: true, id, responder })
    return true
  }

  // POST /permissions/:id/reject — reject a pending escalation
  if (parts[0] === 'permissions' && parts[2] === 'reject' && method === 'POST' && parts.length === 3) {
    const oracle = daemon.intelligence?.permissionOracle
    if (!oracle) {
      sendJSON(res, 503, { error: 'Permission Oracle not available' })
      return true
    }

    const id = parts[1]
    const body = await parseBody(req).catch(() => ({}))
    const responder = body?.responder || 'admin-api'

    const resolved = oracle.resolveApproval(id, false, responder)
    if (!resolved) {
      sendJSON(res, 404, { error: `Pending approval '${id}' not found (may have timed out)` })
      return true
    }

    sendJSON(res, 200, { approved: false, id, responder })
    return true
  }

  // GET /permissions/stats — permission decision statistics
  if (parts[0] === 'permissions' && parts[1] === 'stats' && method === 'GET' && parts.length === 2) {
    const oracle = daemon.intelligence?.permissionOracle
    if (!oracle) {
      sendJSON(res, 503, { error: 'Permission Oracle not available' })
      return true
    }
    sendJSON(res, 200, oracle.getStats())
    return true
  }

  // GET /permissions/log — recent decision audit trail
  if (parts[0] === 'permissions' && parts[1] === 'log' && method === 'GET' && parts.length === 2) {
    const oracle = daemon.intelligence?.permissionOracle
    if (!oracle) {
      sendJSON(res, 503, { error: 'Permission Oracle not available' })
      return true
    }
    const url = deps.url
    const limit = parseInt(url.searchParams.get('limit') ?? '20', 10)
    const log = oracle.getDecisionLog(limit).map((v: any) => ({
      toolName: v.toolName,
      decision: v.decision,
      riskScore: v.riskAssessment.riskScore,
      riskLevel: v.riskAssessment.riskLevel,
      trustScore: v.trustScore.score,
      autonomyLevel: v.autonomyLevel,
      reasoning: v.reasoning,
      hardGate: v.hardGate,
      sessionId: v.sessionId,
      decidedAt: v.decidedAt,
    }))
    sendJSON(res, 200, { decisions: log, count: log.length })
    return true
  }

  // ── Trust Ledger routes ───────────────────────────────────────────────

  // GET /trust — trust summary across all domains
  if (parts[0] === 'trust' && method === 'GET' && parts.length === 1) {
    const ledger = daemon.intelligence?.trustLedger
    if (!ledger) {
      sendJSON(res, 503, { error: 'Trust Ledger not available' })
      return true
    }
    const summary = ledger.getSummary()
    sendJSON(res, 200, {
      overallScore: summary.overallScore,
      autonomyLevel: summary.autonomyLevel,
      totalEvidence: summary.totalEvidence,
      strongestDomain: summary.strongestDomain,
      weakestDomain: summary.weakestDomain,
      domains: Object.fromEntries(summary.domains),
      stats: ledger.getStats(),
    })
    return true
  }

  // GET /trust/:domain — trust score for a specific domain
  if (parts[0] === 'trust' && method === 'GET' && parts.length === 2) {
    const ledger = daemon.intelligence?.trustLedger
    if (!ledger) {
      sendJSON(res, 503, { error: 'Trust Ledger not available' })
      return true
    }
    const domain = parts[1]
    const score = ledger.getDomainScore(domain)
    if (!score) {
      sendJSON(res, 404, { error: `Domain '${domain}' not found. Use GET /trust to see all domains.` })
      return true
    }
    sendJSON(res, 200, score)
    return true
  }

  // ── Consequence Estimator routes ──────────────────────────────────────

  // GET /consequences/stats — consequence estimator statistics
  if (parts[0] === 'consequences' && parts[1] === 'stats' && method === 'GET' && parts.length === 2) {
    const estimator = daemon.intelligence?.consequenceEstimator
    if (!estimator) {
      sendJSON(res, 503, { error: 'Consequence Estimator not available' })
      return true
    }
    sendJSON(res, 200, estimator.getStats())
    return true
  }

  return false
}
