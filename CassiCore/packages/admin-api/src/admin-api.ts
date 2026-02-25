import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import type { ILogger } from '../types/interfaces.js'
import type { DialecticStreamEvent } from '../types/dialectic.js'
import { createToolsApi } from './tools-api.js'
import { assembleContext } from './intelligence/context-assembler.js'
import { listProviderConfigKeys } from './providers/centralized.js'

// WebSocket state
interface WSConnection {
  socket: any
  sessionId: string
  subscribed: boolean
}

export function createAdminApi(daemon: any, logger: ILogger) {
  let unixPath = path.join(os.homedir(), '.cassicore', 'admin.sock')
  const tcpHost = (daemon?.config?.get?.('admin.host', '127.0.0.1')) ?? '127.0.0.1'
  const baseTcpPort = Number(daemon?.config?.get?.('admin.port', 7432)) || 7432
  let currentTcpPort = baseTcpPort

  // WebSocket connections store
  const wsConnections = new Map<string, WSConnection>()
  let wsConnectionId = 0

  function sendJSON(res: http.ServerResponse, code: number, obj: unknown) {
    const s = JSON.stringify(obj)
    res.writeHead(code, { 'Content-Type': 'application/json' })
    res.end(s)
  }

  function parseBody(req: http.IncomingMessage): Promise<any> {
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = []
      req.on('data', (c) => chunks.push(Buffer.from(c)))
      req.on('end', () => {
        if (chunks.length === 0) return resolve(undefined)
        try {
          const s = Buffer.concat(chunks).toString('utf8')
          resolve(JSON.parse(s))
        } catch (err) {
          reject(err)
        }
      })
      req.on('error', reject)
    })
  }

  function authOk(req: http.IncomingMessage) {
    try {
      const token = daemon.config?.get?.('admin.token', undefined as string | undefined)
      if (!token) return true
      const h = req.headers['authorization']
      if (!h || Array.isArray(h)) return false
      return h === `Bearer ${token}`
    } catch (err) {
      return true
    }
  }

  async function handlePiBridgeWebSocket(req: http.IncomingMessage, socket: any, head: Buffer) {
    // Accept WebSocket connection
    const key = req.headers['sec-websocket-key']
    if (!key) {
      socket.destroy()
      return
    }

    const crypto = await import('node:crypto')
    const acceptKey = crypto.createHash('sha1')
      .update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11')
      .digest('base64')

    socket.write(
      'HTTP/1.1 101 Switching Protocols\r\n' +
      'Upgrade: websocket\r\n' +
      'Connection: Upgrade\r\n' +
      `Sec-WebSocket-Accept: ${acceptKey}\r\n` +
      '\r\n'
    )

    const connId = `pi-bridge-${++wsConnectionId}`
    const conn: WSConnection = { socket, sessionId: 'pi-bridge', subscribed: true }
    wsConnections.set(connId, conn)

    logger.info(`[admin-api] Pi Bridge WebSocket connected: ${connId}`)

    // Listen for requests from the daemon to be sent to pi
    const requestHandler = (e: any) => {
      if (e.type === 'pi:completion:request') {
        sendWebSocketMessage(socket, JSON.stringify(e))
      }
    }
    daemon.bus.on('pi:completion:request', requestHandler)

    socket.on('close', () => {
      wsConnections.delete(connId)
      daemon.bus.off('pi:completion:request', requestHandler)
      logger.info(`[admin-api] Pi Bridge WebSocket disconnected: ${connId}`)
    })

    socket.on('error', (err: any) => {
      logger.warn(`[admin-api] Pi Bridge WebSocket error: ${String(err)}`)
      socket.destroy()
    })
  }

  /**
   * Set up WebSocket connection handling
   */
  async function handleWebSocketUpgrade(req: http.IncomingMessage, socket: any, head: Buffer) {
    const url = new URL(req.url || '', `http://${tcpHost}:${currentTcpPort}`)
    const parts = url.pathname.split('/').filter(Boolean)
    
    // Handle /pi-bridge WebSocket connections
    if (parts[0] === 'pi-bridge') {
      await handlePiBridgeWebSocket(req, socket, head)
      return
    }
    
    // Only handle /dialectic/:sessionId/stream WebSocket connections
    if (parts[0] !== 'dialectic' || parts.length !== 3 || parts[2] !== 'stream') {
      socket.destroy()
      return
    }
    
    const sessionId = parts[1]
    if (!sessionId) {
      socket.destroy()
      return
    }

    // Accept WebSocket connection (minimal implementation)
    const key = req.headers['sec-websocket-key']
    if (!key) {
      socket.destroy()
      return
    }

    // Generate accept key
    const crypto = await import('node:crypto')
    const acceptKey = crypto.createHash('sha1')
      .update(key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11')
      .digest('base64')

    // Send handshake response
    socket.write(
      'HTTP/1.1 101 Switching Protocols\r\n' +
      'Upgrade: websocket\r\n' +
      'Connection: Upgrade\r\n' +
      `Sec-WebSocket-Accept: ${acceptKey}\r\n` +
      '\r\n'
    )

    const connId = `ws-${++wsConnectionId}`
    const conn: WSConnection = { socket, sessionId, subscribed: true }
    wsConnections.set(connId, conn)

    logger.info(`[admin-api] WebSocket connected for dialectic stream: ${sessionId}`)

    // Subscribe to dialectic events for this session
    const unsubscribe = daemon.intelligence?.dialectic?.subscribeToStream?.(sessionId, (event: DialecticStreamEvent) => {
      if (!conn.subscribed || socket.destroyed) return
      try {
        const message = JSON.stringify(event)
        sendWebSocketMessage(socket, message)
      } catch (err) {
        logger.warn(`[admin-api] WebSocket send error: ${String(err)}`)
      }
    })

    // Handle close
    socket.on('close', () => {
      conn.subscribed = false
      wsConnections.delete(connId)
      unsubscribe?.()
      logger.info(`[admin-api] WebSocket disconnected: ${sessionId}`)
    })

    socket.on('error', (err: any) => {
      logger.warn(`[admin-api] WebSocket error: ${String(err)}`)
      socket.destroy()
    })
  }

  /**
   * Send a text message over WebSocket
   */
  function sendWebSocketMessage(socket: any, message: string) {
    // Minimal WebSocket text frame encoding (no fragmentation)
    const msgBuf = Buffer.from(message, 'utf8')
    const len = msgBuf.length
    
    let frame: Buffer
    if (len < 126) {
      frame = Buffer.allocUnsafe(2 + len)
      frame[0] = 0x81 // FIN=1, opcode=text
      frame[1] = len
      msgBuf.copy(frame, 2)
    } else if (len < 65536) {
      frame = Buffer.allocUnsafe(4 + len)
      frame[0] = 0x81
      frame[1] = 126
      frame.writeUInt16BE(len, 2)
      msgBuf.copy(frame, 4)
    } else {
      frame = Buffer.allocUnsafe(10 + len)
      frame[0] = 0x81
      frame[1] = 127
      frame.writeBigUInt64BE(BigInt(len), 2)
      msgBuf.copy(frame, 10)
    }
    
    socket.write(frame)
  }

  // Helper: shallow/object checks and deep merge for nested object merges
  function isObject(v: unknown): v is Record<string, unknown> {
    return typeof v === 'object' && v !== null && !Array.isArray(v)
  }

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

  async function handler(req: http.IncomingMessage, res: http.ServerResponse) {
    if (!authOk(req)) {
      sendJSON(res, 401, { error: 'unauthorized' })
      return
    }

    const url = new URL(req.url || '', `http://${tcpHost}:${currentTcpPort}`)
    const parts = url.pathname.split('/').filter(Boolean)

    try {
      // ── Health endpoints ───────────────────────────────────────────────────

      if (req.method === 'GET' && url.pathname === '/health') {
        // Try to pull the latest snapshot from the HealthMonitor
        const monitor = daemon.healthMonitor
        const snapshot = monitor?.latest?.()

        if (snapshot) {
          // Full rich response
          const httpCode = snapshot.overall === 'ok' ? 200
            : snapshot.overall === 'degraded' ? 200   // degraded still serves traffic
            : 503
          return sendJSON(res, httpCode, {
            status:         snapshot.overall,
            timestamp:      snapshot.timestamp,
            uptimeMs:       snapshot.uptimeMs,
            memoryMb:       snapshot.memoryMb,
            eventLoopLagMs: snapshot.eventLoopLagMs,
            version:        daemon.config?.get?.('daemon.version', '0.1.0') ?? '0.1.0',
            checks:         snapshot.checks,
          })
        }

        // Fallback: monitor not yet initialised — return minimal response
        return sendJSON(res, 200, {
          status:  'starting',
          uptime:  process.uptime(),
          version: daemon.config?.get?.('daemon.version', '0.1.0') ?? '0.1.0',
        })
      }

      // GET /health/history — rolling snapshot window
      if (req.method === 'GET' && url.pathname === '/health/history') {
        const monitor = daemon.healthMonitor
        const history = monitor?.getHistory?.() ?? []
        return sendJSON(res, 200, history)
      }

      // POST /health/check — trigger an immediate check and return the result
      if (req.method === 'POST' && url.pathname === '/health/check') {
        const monitor = daemon.healthMonitor
        if (!monitor) return sendJSON(res, 503, { error: 'health monitor not initialised' })
        const snapshot = await monitor.runChecks()
        return sendJSON(res, snapshot.overall === 'down' ? 503 : 200, snapshot)
      }

      if (req.method === 'GET' && parts[0] === 'config' && parts.length === 1) {
        return sendJSON(res, 200, daemon.config.toJSON())
      }

      if (parts[0] === 'config' && parts.length === 2) {
        const key = parts[1]
        if (req.method === 'GET') {
          const val = daemon.config.get(key as string, undefined)
          const source = val === undefined ? 'default' : 'file'
          return sendJSON(res, 200, { key, value: val, source })
        }
        if (req.method === 'POST') {
          const body = await parseBody(req)
          if (!body || !('value' in body)) return sendJSON(res, 400, { error: 'missing value' })
          daemon.__admin_overrides = daemon.__admin_overrides || {}
          daemon.__admin_overrides[key] = { value: body.value, reason: body.reason }
          return sendJSON(res, 200, { key, value: body.value })
        }
        if (req.method === 'DELETE') {
          daemon.__admin_overrides = daemon.__admin_overrides || {}
          delete daemon.__admin_overrides[key]
          return sendJSON(res, 200, { key, removed: true })
        }
      }

      // POST /config/set — set arbitrary config keys (set-and-persist) with nested merge support
      if (req.method === 'POST' && url.pathname === '/config/set') {
        try {
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'missing body' })
          const layered = (daemon.config as any)
          const updated: string[] = []

          if (Array.isArray(body.updates)) {
            for (const u of body.updates) {
              if (!u || typeof u.key !== 'string' || !Object.prototype.hasOwnProperty.call(u, 'value')) continue
              const k = String(u.key)
              const v = u.value
              try {
                if (typeof layered?.setOverride === 'function') {
                  const existing = layered.get(k, undefined)
                  const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
                  layered.setOverride(k, newVal, { reason: u.reason || 'admin' })
                } else {
                  daemon.__admin_overrides = daemon.__admin_overrides || {}
                  daemon.__admin_overrides[k] = { value: v, reason: u.reason || 'admin' }
                }
                updated.push(k)
              } catch (err) { /* continue */ }
            }
          } else if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
            const k = String(body.key)
            const v = body.value
            try {
              if (typeof layered?.setOverride === 'function') {
                const existing = layered.get(k, undefined)
                const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
                layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
              } else {
                daemon.__admin_overrides = daemon.__admin_overrides || {}
                daemon.__admin_overrides[k] = { value: v, reason: body.reason || 'admin' }
              }
              updated.push(k)
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          } else {
            return sendJSON(res, 400, { error: 'expected { key, value } or { updates: [{ key, value }] }' })
          }

          try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch {}
          try { if (typeof daemon.reload === 'function') await daemon.reload(); else daemon.bus.emit({ type: 'config:reloaded' }) } catch {}

          return sendJSON(res, 200, { ok: true, updated })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // orchestration endpoints
      if (parts[0] === 'orchestration') {
        if (req.method === 'GET' && parts.length === 1) {
          const list = daemon.pluginHost?.all?.() ?? []
          return sendJSON(res, 200, list)
        }
        if (req.method === 'GET' && parts[1] === 'stalled') {
          const all = daemon.pluginHost?.all?.() ?? []
          const stalled = (all as any[]).filter((p) => p.status === 'crashed' || p.status === 'restarting')
          return sendJSON(res, 200, stalled)
        }
        if (req.method === 'POST' && parts[1] === 'register') {
          const body = await parseBody(req)
          daemon.bus.emit({ type: 'orchestration:register', payload: body })
          return sendJSON(res, 200, { ok: true })
        }
        if (req.method === 'POST' && parts.length === 3 && parts[2] === 'update') {
          const id = parts[1]
          const body = await parseBody(req)
          daemon.bus.emit({ type: 'orchestration:update', id, payload: body })
          return sendJSON(res, 200, { ok: true })
        }
        if (req.method === 'POST' && parts.length === 3 && parts[2] === 'complete') {
          const id = parts[1]
          const body = await parseBody(req)
          daemon.bus.emit({ type: 'orchestration:complete', id, result: body })
          return sendJSON(res, 200, { ok: true })
        }
      }

      // plugins
      if (parts[0] === 'plugins' && req.method === 'GET') {
        const list = daemon.pluginHost?.all?.() ?? []
        return sendJSON(res, 200, list)
      }
      if (parts[0] === 'plugins' && parts.length === 2 && req.method === 'POST' && parts[1] && parts[1].endsWith('restart')) {
        // handled below
      }
      if (parts[0] === 'plugins' && parts.length === 3 && parts[2] === 'restart' && req.method === 'POST') {
        const id = parts[1]
        try {
          await daemon.pluginHost.restart(id)
          return sendJSON(res, 200, { ok: true })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // intelligence
      if (parts[0] === 'intelligence' && req.method === 'GET' && parts.length === 1) {
        const modules = (daemon.intelligence?.all ?? []).map((m: any) => ({ name: m.name, priority: m.priority, status: 'active' }))
        return sendJSON(res, 200, modules)
      }

      // GET/POST/DELETE => /intelligence/thinker/strategy
      if (url.pathname === '/intelligence/thinker/strategy') {
        try {
          const mem = daemon.intelligence?.memory
          if (!mem) return sendJSON(res, 503, { error: 'memory not initialised' })

          if (req.method === 'GET') {
            const strategy = await mem.kv_get('thinker:strategy')
            return sendJSON(res, 200, { strategy: strategy ?? null })
          }

          if (req.method === 'POST') {
            const body = await parseBody(req)
            if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'missing strategy body' })
            await mem.kv_set('thinker:strategy', body)
            // Emit bus event so Thinker picks it up
            daemon.bus.emit({ type: 'thinker:strategy-updated', strategy: body })
            return sendJSON(res, 200, { ok: true })
          }

          if (req.method === 'DELETE') {
            await mem.kv_del('thinker:strategy')
            daemon.bus.emit({ type: 'thinker:strategy-updated', strategy: null })
            return sendJSON(res, 200, { ok: true })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET/POST/DELETE => /intelligence/thinker/insight-history
      if (url.pathname === '/intelligence/thinker/insight-history') {
        try {
          const mem = daemon.intelligence?.memory
          if (!mem) return sendJSON(res, 503, { error: 'memory not initialised' })

          if (req.method === 'GET') {
            const history = await mem.kv_get('thinker:insight-history')
            return sendJSON(res, 200, { insightHistory: history ?? [] })
          }

          if (req.method === 'POST') {
            const body = await parseBody(req)
            if (!body || !Array.isArray(body)) return sendJSON(res, 400, { error: 'expected array body' })
            await mem.kv_set('thinker:insight-history', body)
            daemon.bus.emit({ type: 'thinker:insight-history-updated', history: body })
            return sendJSON(res, 200, { ok: true })
          }

          if (req.method === 'DELETE') {
            await mem.kv_del('thinker:insight-history')
            daemon.bus.emit({ type: 'thinker:insight-history-updated', history: [] })
            return sendJSON(res, 200, { ok: true })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/thinker/stats — return thinker runtime stats
      if (req.method === 'GET' && url.pathname === '/intelligence/thinker/stats') {
        try {
          const thinker = daemon.intelligence?.thinker
          if (!thinker) return sendJSON(res, 503, { error: 'thinker not initialised' })
          const stats = typeof thinker.stats === 'function' ? await Promise.resolve(thinker.stats()) : undefined
          return sendJSON(res, 200, { stats: stats ?? null })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET Subconscious learnings
      if (req.method === 'GET' && url.pathname === '/intelligence/subconscious/learnings') {
        try {
          const mem = daemon.intelligence?.memory
          let learnings: any[] | null = null
          if (mem) {
            try { learnings = await mem.kv_get('subconscious:learnings') || null } catch {}
          }
          if (!learnings) {
            // fallback: try reading persisted file
            const filePath = path.join(process.env.HOME || os.homedir(), '.cassicore', 'data', 'subconscious.json')
            try {
              if (fs.existsSync(filePath)) learnings = JSON.parse(fs.readFileSync(filePath, 'utf8') || '[]')
            } catch (err) { /* ignore */ }
          }
          return sendJSON(res, 200, { learnings: learnings ?? [] })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET Subconscious anomalies
      if (req.method === 'GET' && url.pathname === '/intelligence/subconscious/anomalies') {
        try {
          const mem = daemon.intelligence?.memory
          let anomalies: any[] | null = null
          if (mem) {
            try { anomalies = await mem.kv_get('subconscious:anomalies') || null } catch {}
          }
          return sendJSON(res, 200, { anomalies: anomalies ?? [] })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/thinker/think — manual Thinker trigger (supports context override)
      if (req.method === 'POST' && url.pathname === '/intelligence/thinker/think') {
        try {
          const body = await parseBody(req)
          const publicDepth = body?.depth === 'Think' ? 'Think' : 'Ponder'
          const context = body?.context
          const wait = body?.wait === false ? false : true
          const urgency = body?.urgency || 'medium'
          const trigger = body?.trigger || 'admin'
          const thinker = daemon.intelligence?.thinker
          if (!thinker) return sendJSON(res, 503, { error: 'thinker not available' })

          if (context) {
            // Use private Ponder/Think to pass explicit context
            const p = publicDepth === 'Think'
              ? (thinker as any).Think({ context, urgency, trigger })
              : (thinker as any).Ponder({ context, urgency, trigger })

            if (!wait) {
              p.catch((e: any) => daemon.logger?.warn?.('admin: thinker background failed', { error: String(e) }))
              return sendJSON(res, 200, { ok: true, message: 'Thinker triggered (async)' })
            }

            const result = await p
            return sendJSON(res, 200, { ok: true, result: result ?? null })
          } else {
            if (!wait) {
              (thinker as any).think(publicDepth).then(() => {}).catch((e: any) => daemon.logger?.warn?.('admin: thinker background failed', { error: String(e) }))
              return sendJSON(res, 200, { ok: true, message: 'Thinker triggered (async)' })
            }
            const insight = await (thinker as any).think(publicDepth)
            return sendJSON(res, 200, { ok: true, insight })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Multi-Agent endpoints (admin) ───────────────────────────────────────
      // GET /intelligence/multi-agent/metrics
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/metrics') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const metrics = typeof ma.getMetrics === 'function' ? ma.getMetrics() : undefined
          return sendJSON(res, 200, { metrics: metrics ?? null })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /providers/metrics — aggregated provider + global metrics
      if (req.method === 'GET' && url.pathname === '/providers/metrics') {
        try {
          // Prefer pipeline providers map, fall back to daemon-level providers (if any)
          const providersMap: Map<string, any> | undefined = (daemon.pipeline && (daemon.pipeline as any).providers) || (daemon.providers as any) || undefined
          if (!providersMap) return sendJSON(res, 503, { error: 'providers not initialised' })

          const providerMetrics: Array<{ id: string; metrics: any }> = []
          let globalConfig: any = null
          for (const [id, prov] of providersMap) {
            let metrics = null
            try { metrics = typeof prov.getMetrics === 'function' ? prov.getMetrics() : null } catch {}
            providerMetrics.push({ id, metrics })
            if (!globalConfig && metrics?.globalConfig) globalConfig = metrics.globalConfig
          }

          return sendJSON(res, 200, { global: globalConfig ?? null, providers: providerMetrics })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /providers/config — view effective provider global configuration and overrides
      if (req.method === 'GET' && url.pathname === '/providers/config') {
        try {
          const layered = (daemon.config as any)
          const getWithSource = typeof layered?.getWithSource === 'function'
            ? (k: string) => layered.getWithSource(k)
            : (k: string) => ({ value: layered?.get?.(k, undefined), source: undefined })

          const keys = [
            'providers.global.maxConcurrent',
            'providers.global.windowMs',
            'providers.global.maxRequestsPerWindow',
            'providers.global.timeoutMs',
          ]

          const configView: Record<string, unknown> = {}
          for (const k of keys) {
            try {
              configView[k] = getWithSource(k)
            } catch (err) {
              configView[k] = { value: daemon.config.get(k, undefined), source: undefined }
            }
          }

          const overrides = typeof layered?.getOverrides === 'function' ? layered.getOverrides() : (daemon.__admin_overrides || {})

          return sendJSON(res, 200, { config: configView, overrides })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /providers/config/keys — list provider-specific config keys and defaults
      if (req.method === 'GET' && url.pathname === '/providers/config/keys') {
        try {
          const keys = listProviderConfigKeys()
          return sendJSON(res, 200, { keys })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /providers/config — set provider global configuration overrides
      // Accepts either { key: 'providers.global.maxConcurrent', value: 16 } or
      // a body with friendly keys { maxConcurrent: 16, windowMs: 60000, ... }
      if (req.method === 'POST' && url.pathname === '/providers/config') {
        try {
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'missing body' })

          const layered = (daemon.config as any)
          const mapping: Record<string, string> = {
            maxConcurrent: 'providers.global.maxConcurrent',
            windowMs: 'providers.global.windowMs',
            maxRequestsPerWindow: 'providers.global.maxRequestsPerWindow',
            timeoutMs: 'providers.global.timeoutMs',
          }

          const updated: string[] = []

          if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
            const k = String(body.key)
            try {
              if (typeof layered?.setOverride === 'function') {
                // Merge nested objects where applicable
                const existing = layered.get(k, undefined)
                const newVal = isObject(existing) && isObject(body.value) ? mergeDeep(existing, body.value) : body.value
                layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
              } else {
                daemon.__admin_overrides = daemon.__admin_overrides || {}
                daemon.__admin_overrides[k] = { value: body.value, reason: body.reason }
              }
              updated.push(k)
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          } else {
            for (const friendly of Object.keys(mapping)) {
              if (Object.prototype.hasOwnProperty.call(body, friendly)) {
                const k = mapping[friendly]
                try {
                  if (typeof layered?.setOverride === 'function') {
                    const existing = layered.get(k, undefined)
                    const provided = (body as any)[friendly]
                    const newVal = isObject(existing) && isObject(provided) ? mergeDeep(existing, provided) : provided
                    layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
                  } else {
                    daemon.__admin_overrides = daemon.__admin_overrides || {}
                    daemon.__admin_overrides[k] = { value: (body as any)[friendly], reason: body.reason || 'admin' }
                  }
                  updated.push(k)
                } catch (err) {
                  return sendJSON(res, 500, { error: String(err) })
                }
              }
            }
          }

          // Persist and reload so listeners (e.g., CentralizedProvider) re-apply new limits
          try {
            if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides()
          } catch (err) { /* best-effort */ }

          try {
            if (typeof daemon.reload === 'function') await daemon.reload()
            else daemon.bus.emit({ type: 'config:reloaded' })
          } catch (err) { /* best-effort */ }

          return sendJSON(res, 200, { ok: true, updated })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // DELETE /providers/config — remove overrides for one or more keys
      // Body may be { keys: ['providers.global.maxConcurrent'] } or empty to remove all providers.global.* overrides
      if (req.method === 'DELETE' && url.pathname === '/providers/config') {
        try {
          const body = await parseBody(req)
          const layered = (daemon.config as any)
          const mapping: Record<string, string> = {
            maxConcurrent: 'providers.global.maxConcurrent',
            windowMs: 'providers.global.windowMs',
            maxRequestsPerWindow: 'providers.global.maxRequestsPerWindow',
            timeoutMs: 'providers.global.timeoutMs',
          }

          let toRemove: string[] = []
          if (body && Array.isArray(body.keys)) {
            toRemove = body.keys.map(String)
          } else if (body && typeof body.key === 'string') {
            toRemove = [String(body.key)]
          } else if (body && typeof body === 'object' && Object.keys(body).length > 0) {
            for (const friendly of Object.keys(mapping)) {
              if ((body as any)[friendly]) toRemove.push(mapping[friendly])
            }
          } else {
            // default: clear all known keys
            toRemove = Object.values(mapping)
          }

          const removed: string[] = []
          for (const k of toRemove) {
            try {
              if (typeof layered?.clearOverride === 'function') {
                layered.clearOverride(k)
                removed.push(k)
              } else {
                daemon.__admin_overrides = daemon.__admin_overrides || {}
                if (Object.prototype.hasOwnProperty.call(daemon.__admin_overrides, k)) {
                  delete daemon.__admin_overrides[k]
                  removed.push(k)
                }
              }
            } catch (err) {
              // continue
            }
          }

          try {
            if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides()
          } catch (err) { /* best-effort */ }

          try {
            if (typeof daemon.reload === 'function') await daemon.reload()
            else daemon.bus.emit({ type: 'config:reloaded' })
          } catch (err) { /* best-effort */ }

          return sendJSON(res, 200, { ok: true, removed })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /providers/config/set — set arbitrary provider config keys
      if (req.method === 'POST' && url.pathname === '/providers/config/set') {
        try {
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'missing body' })

          const layered = (daemon.config as any)
          const updated: string[] = []

          // Support batch updates: { updates: [{ key, value, reason }] }
          if (Array.isArray(body.updates)) {
            for (const u of body.updates) {
              if (!u || typeof u.key !== 'string' || !Object.prototype.hasOwnProperty.call(u, 'value')) continue
              const k = String(u.key)
              const v = (u as any).value
              try {
                if (typeof layered?.setOverride === 'function') {
                  const existing = layered.get(k, undefined)
                  const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
                  layered.setOverride(k, newVal, { reason: u.reason || 'admin' })
                } else {
                  daemon.__admin_overrides = daemon.__admin_overrides || {}
                  daemon.__admin_overrides[k] = { value: v, reason: u.reason || 'admin' }
                }
                updated.push(k)
              } catch (err) {
                // continue on per-item errors
              }
            }
          } else if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
            const k = String(body.key)
            const v = body.value
            try {
              if (typeof layered?.setOverride === 'function') {
                const existing = layered.get(k, undefined)
                const newVal = isObject(existing) && isObject(v) ? mergeDeep(existing, v) : v
                layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
              } else {
                daemon.__admin_overrides = daemon.__admin_overrides || {}
                daemon.__admin_overrides[k] = { value: v, reason: body.reason || 'admin' }
              }
              updated.push(k)
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          } else {
            return sendJSON(res, 400, { error: 'expected { key, value } or { updates: [{ key, value }] }' })
          }

          // Persist and reload
          try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch {}
          try { if (typeof daemon.reload === 'function') await daemon.reload(); else daemon.bus.emit({ type: 'config:reloaded' }) } catch {}

          return sendJSON(res, 200, { ok: true, updated })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /providers/config/apply — update overrides and return providers metrics snapshot
      if (req.method === 'POST' && url.pathname === '/providers/config/apply') {
        try {
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'missing body' })

          const layered = (daemon.config as any)
          const mapping: Record<string, string> = {
            maxConcurrent: 'providers.global.maxConcurrent',
            windowMs: 'providers.global.windowMs',
            maxRequestsPerWindow: 'providers.global.maxRequestsPerWindow',
            timeoutMs: 'providers.global.timeoutMs',
          }

          const updated: string[] = []

          // Accept same forms as /providers/config POST plus arbitrary updates
          if (typeof body.key === 'string' && Object.prototype.hasOwnProperty.call(body, 'value')) {
            const k = String(body.key)
            try {
              if (typeof layered?.setOverride === 'function') {
                const existing = layered.get(k, undefined)
                const newVal = isObject(existing) && isObject(body.value) ? mergeDeep(existing, body.value) : body.value
                layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
              } else {
                daemon.__admin_overrides = daemon.__admin_overrides || {}
                daemon.__admin_overrides[k] = { value: body.value, reason: body.reason || 'admin' }
              }
              updated.push(k)
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          } else if (Array.isArray(body.updates)) {
            for (const u of body.updates) {
              if (!u || typeof u.key !== 'string' || !Object.prototype.hasOwnProperty.call(u, 'value')) continue
              const k = String(u.key)
              try {
                if (typeof layered?.setOverride === 'function') {
                  const existing = layered.get(k, undefined)
                  const newVal = isObject(existing) && isObject(u.value) ? mergeDeep(existing, u.value) : u.value
                  layered.setOverride(k, newVal, { reason: u.reason || 'admin' })
                } else {
                  daemon.__admin_overrides = daemon.__admin_overrides || {}
                  daemon.__admin_overrides[k] = { value: u.value, reason: u.reason || 'admin' }
                }
                updated.push(k)
              } catch (err) { /* continue */ }
            }
          } else {
            // friendly mapping form
            for (const friendly of Object.keys(mapping)) {
              if (Object.prototype.hasOwnProperty.call(body, friendly)) {
                const k = mapping[friendly]
                try {
                  if (typeof layered?.setOverride === 'function') {
                    const existing = layered.get(k, undefined)
                    const provided = (body as any)[friendly]
                    const newVal = isObject(existing) && isObject(provided) ? mergeDeep(existing, provided) : provided
                    layered.setOverride(k, newVal, { reason: body.reason || 'admin' })
                  } else {
                    daemon.__admin_overrides = daemon.__admin_overrides || {}
                    daemon.__admin_overrides[k] = { value: (body as any)[friendly], reason: body.reason || 'admin' }
                  }
                  updated.push(k)
                } catch (err) {
                  return sendJSON(res, 500, { error: String(err) })
                }
              }
            }
          }

          // Persist and reload so listeners re-apply new limits
          try { if (typeof layered?.persistOverrides === 'function') await layered.persistOverrides() } catch {}
          try { if (typeof daemon.reload === 'function') await daemon.reload(); else daemon.bus.emit({ type: 'config:reloaded' }) } catch {}

          // Now return metrics snapshot
          try {
            const providersMap: Map<string, any> | undefined = (daemon.pipeline && (daemon.pipeline as any).providers) || (daemon.providers as any) || undefined
            if (!providersMap) return sendJSON(res, 503, { error: 'providers not initialised' })

            const providerMetrics: Array<{ id: string; metrics: any }> = []
            let globalConfig: any = null
            for (const [id, prov] of providersMap) {
              let metrics = null
              try { metrics = typeof prov.getMetrics === 'function' ? prov.getMetrics() : null } catch {}
              providerMetrics.push({ id, metrics })
              if (!globalConfig && metrics?.globalConfig) globalConfig = metrics.globalConfig
            }

            return sendJSON(res, 200, { ok: true, updated, metrics: { global: globalConfig ?? null, providers: providerMetrics } })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/stats
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/stats') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const stats = typeof ma.stats === 'function' ? await Promise.resolve(ma.stats()) : undefined
          return sendJSON(res, 200, { stats: stats ?? null })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/roles
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/roles') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const current = (ma as any).roleMap ?? {}
          const defaults = (ma.constructor as any)?.ROLES ?? {}
          return sendJSON(res, 200, { roles: { defaults, current } })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/roles
      if (req.method === 'POST' && url.pathname === '/intelligence/multi-agent/roles') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'expected roles object' })
          // Validate shape lightly
          const roles = body as Record<string, any>
          ma.updateRoles(roles)
          return sendJSON(res, 200, { ok: true, updated: Object.keys(roles) })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/templates
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/templates') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const templateMap = (ma as any).templateMap ?? {}
          const samples: Record<string, string> = {}
          for (const k of Object.keys(templateMap)) {
            try { samples[k] = templateMap[k]?.({}) ?? String(templateMap[k]) } catch { samples[k] = '[function]' }
          }
          return sendJSON(res, 200, { templates: samples })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/templates
      if (req.method === 'POST' && url.pathname === '/intelligence/multi-agent/templates') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'expected templates object' })
          const templatesIn = body as Record<string, string>
          // Convert string templates into simple functions
          const converted: Record<string, (args: any) => string> = {}
          for (const k of Object.keys(templatesIn)) {
            const v = templatesIn[k]
            converted[k] = () => String(v)
          }
          ma.updateTemplates(converted)
          return sendJSON(res, 200, { ok: true, updated: Object.keys(converted) })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/confirmations — list pending confirmations
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'confirmations') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })

          // GET list
          if (req.method === 'GET' && parts.length === 3) {
            const list = typeof ma.getConfirmations === 'function' ? ma.getConfirmations() : []
            return sendJSON(res, 200, { confirmations: list })
          }

          // POST /intelligence/multi-agent/confirmations/:id/approve
          if (req.method === 'POST' && parts.length === 5 && parts[4] === 'approve') {
            const id = parts[3]
            const body = await parseBody(req)
            try {
              const result = await ma.approveDestructiveConfirmation(id, body?.approver)
              return sendJSON(res, 200, { ok: true, result })
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          }

          // POST /intelligence/multi-agent/confirmations/:id/reject
          if (req.method === 'POST' && parts.length === 5 && parts[4] === 'reject') {
            const id = parts[3]
            const body = await parseBody(req)
            try {
              ma.rejectDestructiveConfirmation(id, body?.approver, body?.reason)
              return sendJSON(res, 200, { ok: true })
            } catch (err) {
              return sendJSON(res, 500, { error: String(err) })
            }
          }

          return sendJSON(res, 405, { error: 'method not allowed on confirmations endpoint' })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET/POST notification filter for multi-agent tool announcements
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/notification-filter') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const filter = typeof ma.getNotificationFilter === 'function' ? ma.getNotificationFilter() : null
          return sendJSON(res, 200, { filter })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      if (req.method === 'POST' && url.pathname === '/intelligence/multi-agent/notification-filter') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const body = await parseBody(req)
          if (!body || typeof body !== 'object') return sendJSON(res, 400, { error: 'expected notification filter object' })
          ma.updateNotificationFilter(body)
          return sendJSON(res, 200, { ok: true })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Multi-Agent Dialectic control endpoints (admin) ───────────────────────

      // POST /intelligence/multi-agent/dialectic/spawn - spawn a Yang/Yin/Serenity trio
      if (req.method === 'POST' && url.pathname === '/intelligence/multi-agent/dialectic/spawn') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const body = await parseBody(req)
          const opts: any = {}
          if (body?.name) opts.name = body.name
          if (body?.initialInput) opts.initialInput = body.initialInput
          if (typeof body?.maxIterations === 'number') opts.maxIterations = body.maxIterations
          if (typeof body?.intervalMs === 'number') opts.intervalMs = body.intervalMs
          if (typeof body?.allowDestructive === 'boolean') opts.allowDestructive = body.allowDestructive
          if (body?.providers && typeof body.providers === 'object') opts.providers = body.providers
          try {
            const r = await ma.spawnDialecticCassis(opts)
            // Retrieve instance metadata (if available)
            const inst = ma.getDialectic?.(r.dialecticId)
            const meta = inst ? {
              sessionId: inst.sessionId,
              createdAt: inst.createdAt,
              updatedAt: inst.updatedAt,
              initialInput: inst.initialInput,
              providers: inst.providers ?? { yang: inst.agents[0]?.provider, yin: inst.agents[1]?.provider, serenity: inst.agents[2]?.provider },
            } : undefined
            return sendJSON(res, 200, { ok: true, dialecticId: r.dialecticId, agents: r.agents.map((a: any) => ({ id: a.id, role: a.role.name, provider: a.provider || null })), meta })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/dialectic/:id/start - start loop
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'start' && req.method === 'POST') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          const body = await parseBody(req)
          try {
            ma.startDialecticCassisLoop(id, { intervalMs: body?.intervalMs, maxIterations: body?.maxIterations, timeoutMs: body?.timeoutMs, initialInput: body?.initialInput })
            return sendJSON(res, 200, { ok: true })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/dialectic/:id/stop - stop loop
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'stop' && req.method === 'POST') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          const body = await parseBody(req)
          try {
            ma.stopDialecticCassis(id, body?.reason || 'admin_stop')
            return sendJSON(res, 200, { ok: true })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/dialectic/:id/resume - resume a paused swarm (optionally update scheduling)
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'resume' && req.method === 'POST') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          const body = await parseBody(req)
          try {
            const ok = ma.resumeDialecticCassis(id, { intervalMs: body?.intervalMs, maxIterations: body?.maxIterations })
            return sendJSON(res, 200, { ok })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/dialectic/:id/schedule - update scheduling for a swarm
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'schedule' && req.method === 'POST') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          const body = await parseBody(req)
          try {
            ma.updateDialecticScheduling(id, { intervalMs: body?.intervalMs, maxIterations: body?.maxIterations, stopConfidenceThreshold: body?.stopConfidenceThreshold })
            return sendJSON(res, 200, { ok: true })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/multi-agent/dialectic/:id/trigger - request an immediate iteration without changing scheduling
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'trigger' && req.method === 'POST') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          try {
            const ok = ma.requestImmediateDialecticIteration(id)
            return sendJSON(res, 200, { ok })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/dialectic - list active dialectic swarms
      if (req.method === 'GET' && url.pathname === '/intelligence/multi-agent/dialectic') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const list = ma.listDialecticSwarms?.() || []
          return sendJSON(res, 200, { dialectics: list })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/dialectic/:id/history - get iteration history
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 4 && req.method === 'GET') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          try {
            // Prefer persisted KV history
            const mem = daemon.intelligence?.memory
            if (mem) {
              const history = await mem.kv_get(`dialectic:instance:${id}:history`) as any[] | undefined
              if (history) return sendJSON(res, 200, { dialecticId: id, history })
            }

            // Fallback to in-memory snapshot
            const inst = ma.getDialectic?.(id)
            if (!inst) return sendJSON(res, 404, { error: 'not found' })
            return sendJSON(res, 200, { dialecticId: id, history: inst.history || [] })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /intelligence/multi-agent/dialectic/:id/stats - aggregated statistics for a dialectic
      if (parts[0] === 'intelligence' && parts[1] === 'multi-agent' && parts[2] === 'dialectic' && parts.length === 5 && parts[4] === 'stats' && req.method === 'GET') {
        try {
          const ma = (daemon.intelligence as any)?.multiAgent
          if (!ma) return sendJSON(res, 503, { error: 'multi-agent coordinator not initialised' })
          const id = parts[3]
          try {
            const mem = daemon.intelligence?.memory
            const history = mem ? (await mem.kv_get(`dialectic:instance:${id}:history`) as any[] || []) : (ma.getDialectic?.(id)?.history || [])
            const total = history.length
            const totalLatency = history.reduce((s: number, it: any) => s + (Number(it.durationMs) || 0), 0)
            const totalCost = history.reduce((s: number, it: any) => s + (Number(it.costUsd) || 0), 0)
            const avgLatency = total > 0 ? Math.round(totalLatency / total) : 0
            return sendJSON(res, 200, { dialecticId: id, totalIterations: total, avgLatencyMs: avgLatency, totalCostUsd: totalCost })
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // ── Pi Bridge endpoints ────────────────────────────────────────────────

      // POST /pi/completion/:requestId/chunk
      if (parts[0] === 'pi' && parts[1] === 'completion' && parts[3] === 'chunk' && req.method === 'POST') {
        const requestId = parts[2]
        const body = await parseBody(req)
        if (!body || !body.chunk) return sendJSON(res, 400, { error: 'missing chunk' })
        
        daemon.bus.emit({
          type: 'pi:completion:chunk',
          requestId,
          chunk: body.chunk
        })
        return sendJSON(res, 200, { ok: true })
      }

      // ── Dialectic endpoints (C: Query API) ─────────────────────────────────

      // GET /dialectic/:sessionId/history — recent dialectic turns
      if (parts[0] === 'dialectic' && parts.length === 3 && parts[2] === 'history' && req.method === 'GET') {
        const sessionId = parts[1]
        const limit = parseInt(url.searchParams.get('limit') || '10', 10)
        try {
          const history = await daemon.intelligence?.dialectic?.getRecent?.(sessionId, limit) ?? []
          return sendJSON(res, 200, { sessionId, history })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /dialectic/:sessionId/stats — aggregated statistics
      if (parts[0] === 'dialectic' && parts.length === 3 && parts[2] === 'stats' && req.method === 'GET') {
        const sessionId = parts[1]
        try {
          const stats = await daemon.intelligence?.dialectic?.getStats?.(sessionId) ?? {
            totalTurns: 0, signalsGenerated: 0, signalsInjected: 0, avgLatencyMs: 0, totalCostUsd: 0
          }
          return sendJSON(res, 200, { sessionId, stats })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /dialectic/:sessionId/think — trigger dialectic for a session (admin)
      if (parts[0] === 'dialectic' && parts.length === 3 && parts[2] === 'think' && req.method === 'POST') {
        try {
          const sessionId = parts[1]
          const body = await parseBody(req)
          // Accept same params as the think tool
          const { query, depth, include_history, memory_limit, files, extra_context, wait, structured, include_raw } = body || {}

          const ctxObj = await assembleContext(
            {
              memory: daemon.intelligence?.memory,
              sessionManager: daemon.sessions,
              getPipeline: () => daemon.pipeline,
              logger: daemon.logger,
            },
            {
              sessionId,
              query: query || '',
              includeHistory: include_history !== undefined ? include_history : true,
              memoryLimit: memory_limit || 5,
              files: Array.isArray(files) ? files : (files ? [files] : []),
              extra: extra_context || '',
              workingDir: process.cwd(),
              allowedPaths: [],
            }
          )

          const turnId = `admin-think-${Date.now()}`
          const dialectic = daemon.intelligence?.dialectic
          if (!dialectic) return sendJSON(res, 503, { error: 'dialectic not available' })

          const promise = dialectic.processTurn(sessionId || `admin-session-${Date.now()}`, turnId, query || '', ctxObj)
          if (wait === false) {
            promise.catch((e: any) => daemon.logger?.warn?.('admin: background dialectic failed', { error: String(e) }))
            return sendJSON(res, 200, { ok: true, message: 'Dialectic triggered (async)' })
          }

          const result = await promise
          const out = {
            sessionId,
            turnId,
            depth: depth || 'Ponder',
            yangBranches: result?.yang?.branches?.length ?? 0,
            yinCritiques: result?.yin?.critiques?.length ?? 0,
            serenity: result?.serenity?.synthesis ?? null,
            meta: { totalLatencyMs: result?.totalLatencyMs ?? null, totalCostUsd: result?.totalCostUsd ?? null },
          }
          if (include_raw) (out as any)['raw'] = result
          return sendJSON(res, 200, out)
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /dialectic/:sessionId/stream — WebSocket upgrade handled separately
      if (parts[0] === 'dialectic' && parts.length === 3 && parts[2] === 'stream' && req.method === 'GET') {
        // Return HTML dashboard for browser requests
        const acceptHeader = req.headers['accept'] || '';
        if (acceptHeader.includes('text/html')) {
          try {
            const htmlPath = path.join(process.cwd(), 'public', 'dialectic-observatory.html');
            const html = fs.readFileSync(htmlPath, 'utf8');
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(html);
            return;
          } catch (err) {
            return sendJSON(res, 500, { error: 'Dashboard not found' });
          }
        }
        // Non-WebSocket request without upgrade
        return sendJSON(res, 426, { error: 'WebSocket upgrade required' });
      }

      // ── Chat endpoints (used by CLI) ───────────────────────────────────────

      // GET /observability/prompts/stream — SSE aggregated prompts & tokens
      if (req.method === 'GET' && url.pathname === '/observability/prompts/stream') {
        // Optional query filters: ?session=<id>&provider=<providerId>&includeTokens=true|false
        const sessionFilter = url.searchParams.get('session') || null
        const providerFilter = url.searchParams.get('provider') || null
        const includeTokens = (url.searchParams.get('includeTokens') || 'true') !== 'false'

        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache, no-transform',
          'Connection': 'keep-alive',
          'Access-Control-Allow-Origin': '*',
        })
        res.write(': connected\n\n')

        const sendEvent = (eventName: string, payload: unknown) => {
          try {
            // Normalize event name to avoid ':' in SSE event names
            const name = String(eventName).replace(/[:]/g, '.')
            res.write(`event: ${name}\n`)
            res.write(`data: ${JSON.stringify(payload)}\n\n`)
          } catch (err) {
            // Ignore write errors (client disconnected)
          }
        }

        // Named handlers so we can remove them on close
        // Helper to match both public session ids and centralized provider 'sess_' markers
        const matchesSessionFilter = (evSessionId: any) => {
          if (!sessionFilter) return true
          if (!evSessionId) return false
          const s = String(evSessionId)
          if (s === sessionFilter) return true
          if (s === `sess_${sessionFilter}`) return true
          if (s.startsWith(`sess_${sessionFilter}`)) return true
          if (s.includes(sessionFilter)) return true
          // Also check normalized form (strip leading 'sess_')
          if (s.startsWith('sess_') && s.slice(5) === sessionFilter) return true
          return false
        }

        const onProviderStart = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            if (!matchesSessionFilter(e.sessionId)) return
            sendEvent('provider:request_start', { providerId: e.providerId, requestId: e.requestId, sessionId: e.sessionId, model: e.model, messageCount: e.messageCount, timestamp: Date.now() })
          } catch {}
        }
        const onProviderEnd = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            if (!matchesSessionFilter(e.sessionId)) return
            sendEvent('provider:request_end', { providerId: e.providerId, requestId: e.requestId, sessionId: e.sessionId, tokensUsed: e.tokensUsed, durationMs: e.durationMs, error: e.error || null, timestamp: Date.now() })
          } catch {}
        }
        const onProviderError = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            if (!matchesSessionFilter(e.sessionId)) return
            sendEvent('provider:request_error', { providerId: e.providerId, requestId: e.requestId, sessionId: e.sessionId, error: e.error, consecutiveErrors: e.consecutiveErrors, timestamp: Date.now() })
          } catch {}
        }
        const onProviderDedup = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            if (!matchesSessionFilter(e.sessionId)) return
            sendEvent('provider:deduplicated', e)
          } catch {}
        }
        const onProviderRateLimited = (e: any) => {
          try {
            if (providerFilter && e.providerId !== providerFilter) return
            if (!matchesSessionFilter(e.sessionId)) return
            sendEvent('provider:rate_limited', e)
          } catch {}
        }

        const onWorkerMessage = (ev: any) => {
          try {
            const pluginId = ev.pluginId as string | undefined
            const payload = ev.payload as Record<string, any> | undefined
            const sid = payload?.sessionId || (typeof pluginId === 'string' && pluginId.startsWith('session:') ? pluginId.slice(8) : undefined)
            if (sessionFilter && sid && String(sid) !== sessionFilter) return

            if (payload?.type === 'turn:token') {
              if (!includeTokens) return
              sendEvent('turn.token', { sessionId: sid, token: payload.token, pluginId, timestamp: Date.now() })
            } else if (payload?.type === 'turn:thinking') {
              if (!includeTokens) return
              sendEvent('turn.thinking', { sessionId: sid, token: payload.token, pluginId, timestamp: Date.now() })
            } else if (payload?.type === 'turn:tool_call') {
              sendEvent('turn.tool_call', { sessionId: sid, tool: payload.tool, input: payload.input, timestamp: Date.now() })
            } else if (payload?.type === 'turn:done') {
              sendEvent('turn.done', { sessionId: sid, model: payload.model, tokensUsed: payload.tokensUsed, durationMs: payload.durationMs, timestamp: Date.now() })
            } else if (payload?.type === 'turn:error') {
              sendEvent('turn.error', { sessionId: sid, error: payload.error, timestamp: Date.now() })
            }
          } catch (err) { /* swallow */ }
        }

        const onTurnStart = (e: any) => {
          try {
            if (sessionFilter && String(e.sessionId) !== sessionFilter) return
            sendEvent('turn.start', { sessionId: e.sessionId, message: e.message, timestamp: e.timestamp || Date.now() })
          } catch {}
        }
        const onTurnEnd = (e: any) => {
          try {
            if (sessionFilter && String(e.sessionId) !== sessionFilter) return
            sendEvent('turn.end', { sessionId: e.sessionId, response: e.response, durationMs: e.durationMs, timestamp: Date.now() })
          } catch {}
        }
        const onDialecticStream = (e: any) => {
          try {
            if (sessionFilter && String(e.sessionId) !== sessionFilter) return
            sendEvent('dialectic.stream', e)
          } catch {}
        }

        // Register listeners
        daemon.bus.on('provider:request_start', onProviderStart)
        daemon.bus.on('provider:request_end', onProviderEnd)
        daemon.bus.on('provider:request_error', onProviderError)
        daemon.bus.on('provider:deduplicated', onProviderDedup)
        daemon.bus.on('provider:rate_limited', onProviderRateLimited)
        daemon.bus.on('worker:message', onWorkerMessage)
        daemon.bus.on('turn:start', onTurnStart)
        daemon.bus.on('turn:end', onTurnEnd)
        daemon.bus.on('dialectic:stream', onDialecticStream)

        // Keep-alive ping every 15s
        const ping = setInterval(() => {
          try { res.write(': ping\n\n') } catch { clearInterval(ping) }
        }, 15_000)
        try { (ping as any).unref?.() } catch {}

        req.on('close', () => {
          clearInterval(ping)
          try { daemon.bus.off('provider:request_start', onProviderStart) } catch {}
          try { daemon.bus.off('provider:request_end', onProviderEnd) } catch {}
          try { daemon.bus.off('provider:request_error', onProviderError) } catch {}
          try { daemon.bus.off('provider:deduplicated', onProviderDedup) } catch {}
          try { daemon.bus.off('provider:rate_limited', onProviderRateLimited) } catch {}
          try { daemon.bus.off('worker:message', onWorkerMessage) } catch {}
          try { daemon.bus.off('turn:start', onTurnStart) } catch {}
          try { daemon.bus.off('turn:end', onTurnEnd) } catch {}
          try { daemon.bus.off('dialectic:stream', onDialecticStream) } catch {}
        })

        return
      }

      // GET /chat/:sessionId/stream  — SSE token stream
      if (parts[0] === 'chat' && parts.length === 3 && parts[2] === 'stream' && req.method === 'GET') {
        const sessionId = parts[1]
        if (!sessionId) return sendJSON(res, 400, { error: 'missing sessionId' })

        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache, no-transform',
          'Connection': 'keep-alive',
          'Access-Control-Allow-Origin': '*',
        })
        res.write(': connected\n\n')

        // Subscribe to bus events for this session
        const busHandler = (e: any) => {
          if (e.pluginId !== `session:${sessionId}`) return
          const payload = e.payload as Record<string, unknown>
          if (payload?.type === 'turn:token') {
            try {
              res.write(`data: ${JSON.stringify({ type: 'token', token: payload.token })}\n\n`)
            } catch { /* client disconnected */ }
          } else if (payload?.type === 'turn:done') {
            try {
              res.write(`data: ${JSON.stringify({ type: 'done' })}\n\n`)
            } catch { /* client disconnected */ }
          } else if (payload?.type === 'turn:tool_call') {
            try {
              res.write(`data: ${JSON.stringify({ type: 'tool_call', tool: payload.tool, input: payload.input })}\n\n`)
            } catch { /* client disconnected */ }
          } else if (payload?.type === 'turn:error') {
            try {
              res.write(`data: ${JSON.stringify({ type: 'error', error: payload.error })}\n\n`)
            } catch { /* client disconnected */ }
          }
        }

        daemon.bus.on('worker:message', busHandler)

        // Keep-alive ping every 15s
        const ping = setInterval(() => {
          try { res.write(': ping\n\n') } catch { clearInterval(ping) }
        }, 15_000)
        try { (ping as any).unref?.() } catch {}

        req.on('close', () => {
          clearInterval(ping)
          daemon.bus.off('worker:message', busHandler)
        })

        return
      }

      // POST /chat/:sessionId/send  — send a message, returns { ok, model, durationMs, tokensUsed }
      if (parts[0] === 'chat' && parts.length === 3 && parts[2] === 'send' && req.method === 'POST') {
        const sessionId = parts[1]
        if (!sessionId) return sendJSON(res, 400, { error: 'missing sessionId' })

        if (!daemon.pipeline) return sendJSON(res, 503, { error: 'pipeline not ready' })

        const body = await parseBody(req)
        const content: string = body?.content
        if (!content) return sendJSON(res, 400, { error: 'missing content' })

        try {
          const { randomUUID } = await import('node:crypto')
          const inbound = {
            id: randomUUID(),
            sessionId,
            channelId: 'channel:cli',
            senderId: sessionId,
            content,
            timestamp: new Date(),
          }

          // process asynchronously (pipeline emits events onto bus for SSE clients)
          void daemon.pipeline.process(inbound).then((result: any) => {
            daemon.bus.emit({ type: 'turn:end', sessionId: inbound.sessionId, response: result.response, durationMs: result.durationMs })
          }).catch((err: any) => {
            daemon.logger?.error?.(`[admin-api] pipeline error: ${String(err)}`)
          })

          return sendJSON(res, 200, { ok: true, sessionId })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /chat/:sessionId/cancel — best-effort cancel of in-flight turn
      if (parts[0] === 'chat' && parts.length === 3 && parts[2] === 'cancel' && req.method === 'POST') {
        const sessionId = parts[1]
        if (!sessionId) return sendJSON(res, 400, { error: 'missing sessionId' })
        if (!daemon.pipeline) return sendJSON(res, 503, { error: 'pipeline not ready' })
        try {
          const ok = typeof (daemon.pipeline as any).requestCancel === 'function'
            ? (daemon.pipeline as any).requestCancel(sessionId)
            : false
          if (ok) return sendJSON(res, 200, { ok: true, cancelled: true })
          return sendJSON(res, 404, { ok: false, error: 'no active turn or not cancellable' })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /chat - Simple chat endpoint for provider integration
      if (parts[0] === "chat" && parts.length === 1 && req.method === "POST") {
        const body = await parseBody(req);
        const messages = body?.messages || [];
        const model = body?.model || "kimi-coding/k2p5";
        
        if (!daemon.pipeline) return sendJSON(res, 503, { error: "pipeline not ready" });
        
        try {
          const { randomUUID } = await import("node:crypto");
          const sessionId = "provider-" + randomUUID();
          const content = messages[messages.length - 1]?.content || "";
          
          const inbound = {
            id: randomUUID(),
            sessionId,
            channelId: "channel:cli",
            senderId: sessionId,
            content,
            timestamp: new Date(),
          };
          
          logger.info(`[admin-api] Processing provider chat for session ${sessionId}`);
          
          // Collect response content from bus events
          let responseContent = "";
          let responseModel = model;
          let tokensUsed = 0;
          let durationMs = 0;
          
          const busHandler = (e: any) => {
            if (e.pluginId !== `session:${sessionId}`) return;
            const payload = e.payload as Record<string, unknown>;
            if (payload?.type === "turn:token") {
              responseContent += String(payload.token || "");
            } else if (payload?.type === "turn:done") {
              responseModel = String(payload.model || model);
              tokensUsed = Number(payload.tokensUsed || 0);
              durationMs = Number(payload.durationMs || 0);
            }
          };
          
          daemon.bus.on("worker:message", busHandler);
          
          try {
            await daemon.pipeline.process(inbound);
            // Wait a bit for events to propagate
            await new Promise(resolve => setTimeout(resolve, 500));
          } finally {
            daemon.bus.off("worker:message", busHandler);
          }
          
          return sendJSON(res, 200, {
            content: responseContent,
            model: responseModel,
            tokensUsed,
            durationMs
          });
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) });
        }
      }

      // GET /models — list models exposed by the daemon (for external clients like CassiCore)
      if (req.method === 'GET' && url.pathname === '/models') {
        try {
          // Attempt to derive models from provider instances loaded into the pipeline.
          const providerMap = (daemon.pipeline as any)?.providers ?? new Map();
          const models: any[] = [];

          for (const [provId, prov] of providerMap.entries()) {
            try {
              const provModels = (prov as any)?.models ?? (prov as any)?.modelList ?? undefined;
              if (!provModels || !Array.isArray(provModels)) continue;

              for (const m of provModels) {
                const modelName = typeof m === 'string' ? m : String((m as any).id ?? m);
                const id = modelName.includes('/') ? modelName : `${provId}/${modelName}`;

                // Heuristics for sensible defaults
                let api = 'openai-completions';
                let reasoning = false;
                let input: string[] = ['text'];
                let contextWindow = 131072;
                let maxTokens = 8192;

                if (String(provId).toLowerCase().includes('kimi')) {
                  api = 'anthropic-messages';
                  reasoning = true;
                  input = ['text', 'image'];
                  contextWindow = 262144;
                  maxTokens = 32768;
                } else if (String(provId).toLowerCase().includes('copilot') || String(provId).toLowerCase().includes('github')) {
                  api = 'openai-completions';
                  reasoning = false;
                }

                // Base metadata
                const meta: any = {
                  id,
                  name: typeof m === 'string' ? id : ((m as any).name ?? id),
                  api,
                  reasoning,
                  input,
                  cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
                  contextWindow,
                  maxTokens,
                };

                // If provider exposes richer metadata via describeModel/getModelInfo, prefer it
                try {
                  if (typeof (prov as any).describeModel === 'function') {
                    const info = await (prov as any).describeModel(modelName)
                    if (info && typeof info === 'object') {
                      meta.name = info.name ?? meta.name
                      meta.api = info.api ?? meta.api
                      meta.reasoning = info.reasoning ?? meta.reasoning
                      meta.input = info.input ?? meta.input
                      meta.cost = info.cost ?? meta.cost
                      meta.contextWindow = info.contextWindow ?? meta.contextWindow
                      meta.maxTokens = info.maxTokens ?? meta.maxTokens
                    }
                  } else if (typeof (prov as any).getModelInfo === 'function') {
                    const info = (prov as any).getModelInfo(modelName)
                    if (info && typeof info === 'object') {
                      meta.name = info.name ?? meta.name
                      meta.api = info.api ?? meta.api
                      meta.reasoning = info.reasoning ?? meta.reasoning
                      meta.input = info.input ?? meta.input
                      meta.cost = info.cost ?? meta.cost
                      meta.contextWindow = info.contextWindow ?? meta.contextWindow
                      meta.maxTokens = info.maxTokens ?? meta.maxTokens
                    }
                  }
                } catch (err) {
                  // best-effort; swallow provider metadata errors
                }

                models.push(meta);
              }
            } catch { /* best-effort */ }
          }

          // Fallback to a small curated set if none discovered
          if (models.length === 0) {
            models.push(
              { id: 'kimi-coding/k2p5', name: 'Kimi K2.5 (CassiCore)', api: 'anthropic-messages', reasoning: true, input: ['text','image'], cost: { input:0,output:0,cacheRead:0,cacheWrite:0 }, contextWindow: 262144, maxTokens: 32768 },
              { id: 'github-copilot/gpt-5-mini', name: 'GitHub Copilot gpt-5-mini (via CassiCore)', api: 'openai-completions', reasoning: false, input: ['text'], cost: { input:0,output:0,cacheRead:0,cacheWrite:0 }, contextWindow: 131072, maxTokens: 8192 },
              { id: 'openrouter/auto', name: 'OpenRouter (via CassiCore)', api: 'openai-completions', reasoning: false, input: ['text'], cost: { input:0,output:0,cacheRead:0,cacheWrite:0 }, contextWindow: 131072, maxTokens: 8192 },
            );
          }

          return sendJSON(res, 200, { models });
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) });
        }
      }

      // GET /mcp — list configured MCP servers and status
      if (req.method === 'GET' && url.pathname === '/mcp') {
        try {
          // Prefer HealthMonitor's mcp reference (wired in daemon.start)
          const mcpRef = (daemon.healthMonitor as any)?.mcp ?? (daemon.mcpRegistry as any) ?? undefined
          if (!mcpRef || typeof mcpRef.status !== 'function') {
            return sendJSON(res, 200, { servers: [], message: 'No MCP servers configured' })
          }
          const servers = mcpRef.status()
          return sendJSON(res, 200, servers)
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /intelligence/thinker/feedback — record human feedback on an insight
      if (req.method === 'POST' && url.pathname === '/intelligence/thinker/feedback') {
        try {
          const body = await parseBody(req)
          const insight = body?.insight
          const helpful = body?.helpful
          const usedInResponse = body?.usedInResponse ?? false
          const sessionId = body?.sessionId
          if (!insight || typeof helpful !== 'boolean') return sendJSON(res, 400, { error: 'missing insight or helpful flag' })
          // Emit event on the bus for Thinker to consume
          daemon.bus.emit({ type: 'thinker:feedback', insight, helpful, usedInResponse, sessionId })
          return sendJSON(res, 200, { ok: true })
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // POST /tools/execute — execute a registered tool synchronously (admin)
      if (req.method === 'POST' && url.pathname === '/tools/execute') {
        try {
          const body = await parseBody(req)
          const toolName = body?.tool || body?.name
          const input = body?.input || {}
          const sessionId = body?.sessionId || null
          if (!toolName) return sendJSON(res, 400, { error: 'missing tool name (tool)' })
          const exec = (daemon as any).toolExecutor
          if (!exec || typeof exec.execute !== 'function') return sendJSON(res, 503, { error: 'toolExecutor not available' })
          const { randomUUID } = await import('node:crypto')
          const call = { id: randomUUID(), name: toolName, input }
          try {
            const result = await exec.execute(call, sessionId || `admin-${Date.now()}`)
            return sendJSON(res, 200, result)
          } catch (err) {
            return sendJSON(res, 500, { error: String(err) })
          }
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }

      // GET /tools/registry — list registered tools (name, description, parameters)
      if (req.method === 'GET' && url.pathname === '/tools/registry') {
        try {
          const toolRegistry = (daemon.pipeline as any)?.toolRegistry ?? (daemon.toolRegistry as any)
          if (!toolRegistry || typeof toolRegistry.list !== 'function') {
            return sendJSON(res, 503, { error: 'tool registry not initialised' })
          }
          const list = toolRegistry.list().map((t: any) => ({ name: t.name, description: t.description, parameters: t.parameters }))
          return sendJSON(res, 200, list)
        } catch (err) {
          return sendJSON(res, 500, { error: String(err) })
        }
      }
      if (parts[0] === "tools" || parts[0] === "fs") {
        const toolsApi = createToolsApi(logger);
        return toolsApi.handler(req, res);
      }
      sendJSON(res, 404, { error: 'not_found' })
    } catch (err) {
      logger.warn(`admin-api error: ${String(err)}`)
      sendJSON(res, 500, { error: String(err) })
    }
  }

  // Separate servers for Unix socket and TCP
  let unixServer: http.Server | null = null
  let tcpServer: http.Server | null = null

  return {
    async start() {
      if (unixServer || tcpServer) return { tcpPort: currentTcpPort, unixPath }

      // Remove existing socket if present
      try {
        if (fs.existsSync(unixPath)) fs.unlinkSync(unixPath)
      } catch {}

      // Start Unix socket server
      unixServer = http.createServer(handler)
      unixServer.on('upgrade', (req, socket, head) => { void handleWebSocketUpgrade(req, socket, head) })
      unixServer.on('error', (e) => logger.warn(`[admin-api] unix server error: ${String(e)}`))
      await new Promise<void>((resolve, reject) => {
        unixServer!.listen(unixPath, () => {
          try { fs.chmodSync(unixPath, 0o660) } catch {}
          logger.info(`[admin-api] listening on unix:${unixPath}`)
          resolve()
        })
        unixServer!.on('error', reject)
      })

      // Start TCP server (separate instance) — attempt base port then fallback
      let boundPort: number | null = null
      for (let i = 0; i < 10; i++) {
        const tryPort = baseTcpPort + i
        const s = http.createServer(handler)
        s.on('upgrade', (req, socket, head) => { void handleWebSocketUpgrade(req, socket, head) })

        try {
          await new Promise<void>((resolve, reject) => {
            s.listen(tryPort, tcpHost, () => resolve())
            s.once('error', (err) => reject(err))
          })
          tcpServer = s
          boundPort = tryPort
          currentTcpPort = tryPort
          logger.info(`[admin-api] listening on http://${tcpHost}:${tryPort}`)
          break
        } catch (err: any) {
          if (err && err.code === 'EADDRINUSE') {
            logger.warn(`[admin-api] port ${tryPort} in use; trying ${tryPort + 1}`)
            try { s.close?.(); } catch {}
            continue
          }
          try { s.close?.(); } catch {}
          throw err
        }
      }

      if (!boundPort) {
        logger.warn('[admin-api] failed to bind TCP admin port (no available port found)')
      }

      return { tcpPort: boundPort, unixPath }
    },
    async stop() {
      if (unixServer) {
        await new Promise<void>((resolve) => unixServer!.close(() => resolve()))
        unixServer = null
      }
      if (tcpServer) {
        await new Promise<void>((resolve) => tcpServer!.close(() => resolve()))
        tcpServer = null
      }
      try { if (fs.existsSync(unixPath)) fs.unlinkSync(unixPath) } catch {}
      logger.info('[admin-api] stopped')
    }
  }
}
