import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface DelegationRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
  delegationTracker: Map<string, any>
  subagentToTeamMap: Map<string, string>
}

export async function handleDelegationRoutes(
  deps: DelegationRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string
): Promise<boolean> {
  const { daemon, logger, sendJSON, parseBody, delegationTracker, subagentToTeamMap } = deps

  // POST /delegation/ack
  if (method === 'POST' && pathname === '/delegation/ack') {
    try {
      const body = await parseBody(req)
      const { delegationId, spawnedSessionId, status: ackStatus, error: ackError, result: ackResult } = body as any

      if (!delegationId) {
        sendJSON(res, 400, { error: 'Missing delegationId' })
        return true
      }

      const tracking = delegationTracker.get(delegationId)
      if (!tracking) {
        sendJSON(res, 404, { error: 'Delegation not found' })
        return true
      }

      if (ackStatus === 'executing' && spawnedSessionId) {
        tracking.status = 'executing'
        tracking.spawnedSessionId = spawnedSessionId
        tracking.acknowledgedAt = Date.now()

        const teamId = subagentToTeamMap.get(spawnedSessionId)
        if (teamId) tracking.teamId = teamId

        logger.info('Delegation acknowledged', { delegationId, spawnedSessionId })
      } else if (ackStatus === 'failed') {
        tracking.status = 'failed'
        tracking.result = ackError || 'Unknown error'
        logger.warn('Delegation failed', { delegationId, error: ackError })
      } else if (ackStatus === 'completed') {
        tracking.status = 'completed'
        tracking.completedAt = Date.now()
        tracking.result = ackResult
        logger.info('Delegation completed', { delegationId })
      }

      sendJSON(res, 200, { ok: true, status: tracking.status })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
