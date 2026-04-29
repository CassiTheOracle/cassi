/**
 * Teams Admin API Routes — DEPRECATED
 *
 * REMOVED: TriadTeam and FluxTeam orchestrators are deleted.
 * All orchestration now uses Helix (single-session) and Constellation (multi-Helix tree).
 *
 * This route handler returns deprecation messages for legacy team endpoints.
 * Future constellation/helix route handlers will replace this.
 *
 * @module admin-api/teams
 */

import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

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
  teamStore?: any
  contextSnapshotStore?: any
}

/**
 * Handle teams admin API routes.
 *
 * DEPRECATED: All endpoints return 410 Gone with migration guidance.
 */
export async function handleTeamsRoutes(
  deps: TeamsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
): Promise<boolean> {
  const { sendJSON, parts } = deps

  // Route pattern: /api/teams/* or /api/team/*
  if (parts.length < 2 || (parts[0] !== 'teams' && parts[0] !== 'team')) {
    return false
  }

  const endpoint = parts[1] || ''

  const deprecationResponse = {
    error: 'Deprecated endpoint',
    message: 'TriadTeam and FluxTeam orchestrators are removed.',
    migration: 'Use /api/constellation/* for multi-Helix orchestration or /api/helix/* for single-session.',
    endpoint: `/api/${parts.join('/')}`,
  }

  // Return 410 Gone for all legacy team endpoints
  sendJSON(res, 410, deprecationResponse)
  return true
}

// REMOVED: All legacy team route handlers deleted with TriadTeam/FluxTeam
// - getOrchestrator, getFluxOrchestrator, resolveTeamId
// - loadPersistedFluxTeam, loadPersistedFluxCells
// - buildCellTree, buildFluxCellTree, buildFluxCellTreeFromPersisted
// - timeline aggregation, metrics, cell context replay
// - SSE team streaming
// All will be replaced by constellation/helix route handlers in future phases.