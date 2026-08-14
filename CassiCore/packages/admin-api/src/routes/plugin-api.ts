/**
 * Plugin HTTP Routes — Admin API endpoints for the plugin protocol.
 *
 * Exposes the plugin system over HTTP for out-of-process clients.
 * In-process plugins (worker threads) can use the PluginAPI directly.
 *
 * Routes:
 *   POST   /plugin/register        — Register a plugin (returns API key)
 *   DELETE /plugin/:id             — Unregister a plugin
 *   POST   /plugin/heartbeat       — Plugin heartbeat
 *   POST   /plugin/message         — Send a protocol message
 *   GET    /plugin/events          — SSE event stream
 *   GET    /plugin/list            — List registered plugins
 *
 * Authentication: Bearer token in Authorization header (the API key
 * returned from /plugin/register). Registration itself is unauthenticated
 * but restricted to local connections (Unix socket).
 */

import type http from 'node:http'
import type { ILogger } from '../../types/interfaces.js'
import type { PluginRegistry } from '../plugins/plugin-registry.js'
import type { PluginAPI } from '../plugins/plugin-api.js'
import type { PluginManifest, PluginToCore } from '../../types/plugin.js'

export interface PluginAPIRoutesDeps {
  logger: ILogger
  registry: PluginRegistry
  pluginAPI: PluginAPI
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
  readBody: (req: http.IncomingMessage) => Promise<unknown>
  parts: string[]
  attachEventStream?: (pluginId: string, res: http.ServerResponse, req: http.IncomingMessage) => void
}

export async function handlePluginAPIRoutes(
  deps: PluginAPIRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string
): Promise<boolean> {
  const { registry, pluginAPI, sendJSON, readBody, parts, attachEventStream } = deps

  if (parts[0] !== 'plugin') return false

  // POST /plugin/register — Register a new plugin
  if (parts.length === 2 && parts[1] === 'register' && method === 'POST') {
    try {
      if (!isLocalRequest(req)) {
        sendJSON(res, 403, { ok: false, error: 'Plugin registration is restricted to local connections' })
        return true
      }

      const body = await readBody(req) as PluginManifest
      if (!body.id || !body.name || !body.version) {
        sendJSON(res, 400, { ok: false, error: 'Missing required fields: id, name, version' })
        return true
      }

      const registration = registry.register(body)
      sendJSON(res, 200, {
        ok: true,
        apiKey: registration.apiKey,
        grantedCapabilities: registration.grantedCapabilities,
        pluginId: registration.manifest.id,
      })
    } catch (err) {
      sendJSON(res, 500, { ok: false, error: String(err) })
    }
    return true
  }

  // DELETE /plugin/:id — Unregister a plugin
  if (parts.length === 2 && method === 'DELETE') {
    const pluginId = parts[1]
    const reg = authenticate(req, registry)
    if (!reg || reg.manifest.id !== pluginId) {
      sendJSON(res, 401, { ok: false, error: 'Invalid or missing API key' })
      return true
    }
    const success = registry.unregister(pluginId)
    sendJSON(res, success ? 200 : 404, { ok: success })
    return true
  }

  // POST /plugin/heartbeat — Plugin heartbeat
  if (parts.length === 2 && parts[1] === 'heartbeat' && method === 'POST') {
    const reg = authenticate(req, registry)
    if (!reg) {
      sendJSON(res, 401, { ok: false, error: 'Invalid or missing API key' })
      return true
    }
    registry.heartbeat(reg.manifest.id)
    sendJSON(res, 200, { ok: true })
    return true
  }

  // POST /plugin/message — Send a protocol message
  if (parts.length === 2 && parts[1] === 'message' && method === 'POST') {
    const reg = authenticate(req, registry)
    if (!reg) {
      sendJSON(res, 401, { ok: false, error: 'Invalid or missing API key' })
      return true
    }

    try {
      const body = await readBody(req) as PluginToCore
      if (!body.type) {
        sendJSON(res, 400, { ok: false, error: 'Missing message type' })
        return true
      }

      // Inject pluginId from the authenticated registration
      body.pluginId = reg.manifest.id
      body.timestamp = body.timestamp || Date.now()

      const result = await pluginAPI.handle(reg, body)
      sendJSON(res, result.ok ? 200 : 400, result)
    } catch (err) {
      sendJSON(res, 500, { ok: false, error: String(err) })
    }
    return true
  }

  // GET /plugin/events — SSE event stream for a plugin
  if (parts.length === 2 && parts[1] === 'events' && method === 'GET') {
    const reg = authenticate(req, registry)
    if (!reg) {
      sendJSON(res, 401, { ok: false, error: 'Invalid or missing API key' })
      return true
    }

    if (attachEventStream) {
      attachEventStream(reg.manifest.id, res, req)
    } else {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
      })
      res.write(': connected\n\n')

      const heartbeatTimer = setInterval(() => {
        if (res.destroyed || res.writableEnded) {
          clearInterval(heartbeatTimer)
          return
        }
        try {
          res.write(': heartbeat\n\n')
          registry.heartbeat(reg.manifest.id)
        } catch {
          clearInterval(heartbeatTimer)
        }
      }, 15_000)

      req.on('close', () => {
        clearInterval(heartbeatTimer)
        registry.setStatus(reg.manifest.id, 'disconnected')
      })
    }

    return true
  }

  // GET /plugin/list — List registered plugins
  if (parts.length === 2 && parts[1] === 'list' && method === 'GET') {
    const plugins = registry.list().map(p => ({
      id: p.manifest.id,
      name: p.manifest.name,
      version: p.manifest.version,
      status: p.status,
      transport: p.manifest.transport,
      capabilities: p.grantedCapabilities,
      connectedAt: p.connectedAt ? new Date(p.connectedAt).toISOString() : null,
      lastHeartbeat: p.lastHeartbeat ? new Date(p.lastHeartbeat).toISOString() : null,
    }))
    sendJSON(res, 200, { ok: true, plugins })
    return true
  }

  return false
}

/**
 * Extract and validate the API key from the Authorization header.
 * Returns the plugin registration if valid, null otherwise.
 */
function authenticate(
  req: http.IncomingMessage,
  registry: PluginRegistry,
) {
  const authHeader = req.headers.authorization
  if (!authHeader) return null

  const match = authHeader.match(/^Bearer\s+(.+)$/i)
  if (!match) return null

  return registry.authenticate(match[1])
}

function isLocalRequest(req: http.IncomingMessage): boolean {
  if (!req.socket.remoteAddress) return true
  const addr = req.socket.remoteAddress
  return addr === '127.0.0.1' || addr === '::1' || addr === '::ffff:127.0.0.1'
}
