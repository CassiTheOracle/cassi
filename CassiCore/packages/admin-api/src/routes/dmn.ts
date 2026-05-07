/**
 * Admin API routes for the Default Mode Network (DMN).
 *
 * GET /dmn/sessions/:sessionId/digest
 *   Returns the cached `<observers>` block for a session, or empty string
 *   when no signal is cached or the session is not attached.
 *   Used by the Claude Code proxy at request-build time to inject the
 *   digest into the system prompt of the next main-session turn.
 *
 * GET /dmn/stats
 *   Telemetry: attached session count + per-session fire counts.
 */

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

import type { AdminRuntimeFacade } from './runtime.js'


export interface DmnRoutesDeps {
  runtime: AdminRuntimeFacade
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  url: URL
  parts: string[]
}


export async function handleDmnRoutes(
  deps: DmnRoutesDeps,
  _req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { runtime, sendJSON, parts } = deps

  if (parts[0] !== 'dmn') return false

  const dmn = runtime.getIntelligence()?.dmn

  // GET /dmn/stats
  if (parts.length === 2 && parts[1] === 'stats' && method === 'GET') {
    if (!dmn) {
      sendJSON(res, 503, { error: 'DMN not available (disabled or not initialised)' })
      return true
    }
    sendJSON(res, 200, dmn.stats())
    return true
  }

  // GET /dmn/sessions/:sessionId/digest
  if (parts.length === 4 && parts[1] === 'sessions' && parts[3] === 'digest' && method === 'GET') {
    const sessionId = decodeURIComponent(parts[2] ?? '')
    if (!sessionId) {
      sendJSON(res, 400, { error: 'missing sessionId' })
      return true
    }
    if (!dmn) {
      sendJSON(res, 200, { digest: '' })
      return true
    }
    const digest = dmn.getContextInjection(sessionId)
    sendJSON(res, 200, { digest })
    return true
  }

  return false
}
