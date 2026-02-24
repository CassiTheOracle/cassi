import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import type { ILogger } from '../types/interfaces.js'
import type { DialecticStreamEvent } from '../types/dialectic.js'
import { createToolsApi } from './tools-api.js'
import { assembleContext } from './intelligence/context-assembler.js'

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
      const token = daemon.config.get('admin.token', undefined as string | undefined)
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

      // ── Pi Bridge endpoints ────────────────────────────────────────────────

<<<<<<< Updated upstream
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
            depth: depth || 'sonnet',
            yangBranches: result?.yang?.branches?.length ?? 0,
            yinCritiques: result?.yin?.critiques?.length ?? 0,
            synthesizer: result?.synthesizer?.synthesis ?? null,
            meta: { totalLatencyMs: result?.totalLatencyMs ?? null, totalCostUsd: result?.totalCostUsd ?? null },
          }
          if (include_raw) out['raw'] = result
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
          logger.info(`[admin-api] Processing chat message for session ${sessionId}`)

          // Process fires tokens onto the bus (picked up by SSE stream above)
          // then sends done event when complete
          daemon.pipeline.process(inbound).then((result: any) => {
            logger.info(`[admin-api] Turn complete for session ${sessionId}`)
            // Signal done to SSE subscriber
            daemon.bus.emit({
              type: 'worker:message',
              pluginId: `session:${sessionId}`,
              payload: { type: 'turn:done', sessionId, model: result.model, durationMs: result.durationMs, tokensUsed: result.tokensUsed },
            })
          }).catch((err: unknown) => {
            logger.error(`[admin-api] Pipeline error for session ${sessionId}: ${String(err)}`)
            daemon.bus.emit({
              type: 'worker:message',
              pluginId: `session:${sessionId}`,
              payload: { type: 'turn:error', sessionId, error: String(err) },
            })
          })

          return sendJSON(res, 200, { ok: true, sessionId })
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

      // Tools API endpoints
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
      
      // WebSocket upgrade handling
      unixServer.on('upgrade', (req, socket, head) => {
        void handleWebSocketUpgrade(req, socket, head)
      })
      
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
=======
    }
  } catch (err) {
    logger.error("[admin-api] request error: " + String(err))
    if (!res.headersSent) sendJSON(res, 500, { error: String(err) })
>>>>>>> Stashed changes
  }
}
