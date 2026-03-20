/**
 * Admin API routes for the ModelDirective subsystem.
 *
 * Endpoints:
 *   GET  /model-directive          — current state (effective routing, all scopes)
 *   GET  /model-directive/tiers    — list available tiers with their mappings
 *   POST /model-directive/set      — set routing at a given scope
 *   POST /model-directive/clear    — clear routing at a given scope
 */

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface ModelDirectiveRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  persistRuntimeOverrides?: () => Promise<void>
}

export async function handleModelDirectiveRoutes(
  deps: ModelDirectiveRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string,
): Promise<boolean> {
  const { daemon, sendJSON, parseBody, persistRuntimeOverrides } = deps

  const directive = daemon.modelDirective
  if (!directive) {
    if (pathname.startsWith('/model-directive')) {
      sendJSON(res, 503, { error: 'ModelDirective not initialized' })
      return true
    }
    return false
  }

  // GET /model-directive — current routing state
  if (method === 'GET' && pathname === '/model-directive') {
    try {
      const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`)
      const jobId = url.searchParams.get('jobId') ?? undefined
      const state = directive.getState(jobId)
      sendJSON(res, 200, { jobId, ...state })
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // GET /model-directive/tiers — list available tiers
  if (method === 'GET' && pathname === '/model-directive/tiers') {
    try {
      const tiers = directive.listTiers()
      sendJSON(res, 200, { tiers })
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
    }
    return true
  }

  // POST /model-directive/set — set routing at a scope
  if (method === 'POST' && pathname === '/model-directive/set') {
    try {
      const body = await parseBody(req)
      if (!body || typeof body !== 'object') {
        sendJSON(res, 400, { error: 'Missing request body' })
        return true
      }

      const { scope, tier, provider, model, jobId, slot } = body

      if (!scope || !['next', 'next-job', 'job', 'default'].includes(scope)) {
        sendJSON(res, 400, { error: 'scope must be "next", "next-job", "job", or "default"' })
        return true
      }

      // Resolve provider+model from either tier or raw values
      let resolvedProvider: string
      let resolvedModel: string

      if (tier) {
        const tierConfig = directive.resolveTier(tier)
        resolvedProvider = tierConfig.provider
        resolvedModel = tierConfig.model
      } else if (provider && model) {
        resolvedProvider = provider
        resolvedModel = model
      } else {
        sendJSON(res, 400, { error: 'Provide either "tier" or both "provider" and "model"' })
        return true
      }

      directive.set(scope, { provider: resolvedProvider, model: resolvedModel }, jobId, slot)
      if (scope === 'default' && persistRuntimeOverrides) {
        await persistRuntimeOverrides()
      }
      const state = directive.getState(jobId)
      sendJSON(res, 200, {
        ok: true,
        scope,
        provider: resolvedProvider,
        model: resolvedModel,
        jobId,
        slot,
        state,
      })
    } catch (err) {
      sendJSON(res, 400, { error: String(err) })
    }
    return true
  }

  // POST /model-directive/clear — clear routing at a scope
  if (method === 'POST' && pathname === '/model-directive/clear') {
    try {
      const body = await parseBody(req)
      if (!body || typeof body !== 'object') {
        sendJSON(res, 400, { error: 'Missing request body' })
        return true
      }

      const { scope, jobId, slot } = body

      if (!scope || !['next', 'next-job', 'job', 'default'].includes(scope)) {
        sendJSON(res, 400, { error: 'scope must be "next", "next-job", "job", or "default"' })
        return true
      }

      directive.clear(scope, jobId, slot)
      if (scope === 'default' && persistRuntimeOverrides) {
        await persistRuntimeOverrides()
      }
      const state = directive.getState(jobId)
      sendJSON(res, 200, { ok: true, scope, jobId, slot, state })
    } catch (err) {
      sendJSON(res, 400, { error: String(err) })
    }
    return true
  }

  return false
}
