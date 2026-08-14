import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface ChannelsRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

export async function handleChannelsRoutes(
  deps: ChannelsRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string
): Promise<boolean> {
  const { daemon, sendJSON, parseBody } = deps
  const layered = daemon.config as any

  if (method === 'GET' && pathname === '/channels/telegram/config') {
    const tgCfg = daemon.config.get('channels.telegram', {})
    sendJSON(res, 200, tgCfg)
    return true
  }

  if (method === 'POST' && pathname === '/channels/telegram/config') {
    try {
      const body = await parseBody(req)
      if (!body || typeof body !== 'object') {
        sendJSON(res, 400, { error: 'missing body' })
        return true
      }
      const updated: string[] = []

      const mapping: Record<string, string> = {
        allowedChatIds: 'channels.telegram.allowedChatIds',
        enabled: 'channels.telegram.enabled',
        token: 'channels.telegram.token'
      }

      for (const key of Object.keys(mapping)) {
        if (Object.prototype.hasOwnProperty.call(body, key)) {
          const k = mapping[key]
          const v = body[key]
          try {
            layered.setOverride(k, v, { reason: 'admin' })
            updated.push(k)
          } catch (err) { /* continue */ }
        }
      }

      if (updated.length > 0) {
        try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch {}
        try { if (typeof daemon.reload === 'function') await daemon.reload() } catch {}
        sendJSON(res, 200, { ok: true, updated })
      } else {
        sendJSON(res, 400, { error: 'no valid fields to update' })
      }
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
