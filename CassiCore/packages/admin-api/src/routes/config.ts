import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'

export interface ConfigRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  parseBody: (req: http.IncomingMessage) => Promise<any>
}

// Helper: shallow/object checks and deep merge for nested object merges
/**
 * @dep callers: handleConfigRoutes (core/admin-api/config.ts), mergeDeep (core/admin-api/config.ts)
 * @dep module: Admin-api
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/**
 * @dep callers: handleConfigRoutes (core/admin-api/config.ts), mergeDeep (core/admin-api/config.ts)
 * @dep calls: isObject, mergeDeep
 * @dep module: Admin-api
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function mergeDeep(target: any, src: any): any {
  if (!isObject(target) || !isObject(src)) return src
  const out: any = { ...target }
  for (const k of Object.keys(src)) {
    if (isObject(src[k])) {
      out[k] = mergeDeep(out[k] ?? {}, src[k])
    } else {
      out[k] = src[k]
    }
  }
  return out
}

export async function handleConfigRoutes(
  deps: ConfigRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string,
  parts: string[]
): Promise<boolean> {
  const { daemon, sendJSON, parseBody } = deps
  const layered = daemon.config as any

  // GET /config
  if (method === 'GET' && parts[0] === 'config' && parts.length === 1) {
    sendJSON(res, 200, daemon.config.toJSON())
    return true
  }

  // GET/POST/DELETE /config/:key
  if (parts[0] === 'config' && parts.length === 2) {
    const key = parts[1]
    if (method === 'GET') {
      const val = daemon.config.get(key as string, undefined)
      const source = val === undefined ? 'default' : 'file'
      sendJSON(res, 200, { key, value: val, source })
      return true
    }
    if (method === 'POST') {
      const body = await parseBody(req)
      if (!body || !('value' in body)) {
        sendJSON(res, 400, { error: 'missing value' })
        return true
      }
      if (typeof layered?.setOverride === 'function') {
        layered.setOverride(key, body.value, { reason: body.reason || 'admin' })
      }
      sendJSON(res, 200, { key, value: body.value })
      return true
    }
    if (method === 'DELETE') {
      if (typeof layered?.clearOverride === 'function') {
        layered.clearOverride(key)
      }
      sendJSON(res, 200, { key, removed: true })
      return true
    }
  }

  // POST /config/set
  if (method === 'POST' && pathname === '/config/set') {
    try {
      const body = await parseBody(req)
      if (!body || typeof body !== 'object') {
        sendJSON(res, 400, { error: 'missing body' })
        return true
      }
      const updated: string[] = []

      if (Array.isArray(body.updates)) {
        for (const u of body.updates) {
          if (!u || typeof u.key !== 'string' || !Object.prototype.hasOwnProperty.call(u, 'value')) continue
          const k = String(u.key)
          const v = u.value
          try {
            const existing = layered.get(k, undefined)
            const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
            layered.setOverride(k, newVal, { reason: u.reason || 'admin' })
            updated.push(k)
          } catch (err) { /* continue */ }
        }
      } else if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
        const k = String(body.key)
        const v = body.value
        try {
          const existing = layered.get(k, undefined)
          const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
          layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
          updated.push(k)
        } catch (err) {
          sendJSON(res, 500, { error: String(err) })
          return true
        }
      } else {
        sendJSON(res, 400, { error: 'expected { key, value } or { updates: [{ key, value }] }' })
        return true
      }

      try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch {}
      try { if (typeof daemon.reload === 'function') await daemon.reload(); else daemon.bus.emit({ type: 'config:reloaded' }) } catch {}

      sendJSON(res, 200, { ok: true, updated })
      return true
    } catch (err) {
      sendJSON(res, 500, { error: String(err) })
      return true
    }
  }

  return false
}
