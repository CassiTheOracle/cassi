import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import type { ILogger } from '../types/interfaces.js'

export function createAdminApi(daemon: any, logger: ILogger) {
  const HOME = os.homedir()
  const unixPath = path.join(HOME, '.cassicore', 'admin.sock')
  const tcpHost = (daemon?.config?.get?.('admin.host', '127.0.0.1')) ?? '127.0.0.1'
  const baseTcpPort = Number(daemon?.config?.get?.('admin.port', 7432)) || 7432
  let currentTcpPort = baseTcpPort

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

  async function handler(req: http.IncomingMessage, res: http.ServerResponse) {
    if (!authOk(req)) {
      sendJSON(res, 401, { error: 'unauthorized' })
      return
    }

    const url = new URL(req.url || '', `http://${tcpHost}:${currentTcpPort}`)
    const parts = url.pathname.split('/').filter(Boolean)

    try {
      // health
      if (req.method === 'GET' && url.pathname === '/health') {
        const snapshot = daemon?.healthMonitor?.latest?.() ?? null
        if (snapshot) {
          const httpCode = snapshot.overall === 'ok' ? 200 : snapshot.overall === 'degraded' ? 200 : 503
          return sendJSON(res, httpCode, { status: snapshot.overall, timestamp: snapshot.timestamp, uptimeMs: snapshot.uptimeMs, checks: snapshot.checks, version: daemon.config?.get?.('daemon.version', '0.1.0') })
        }
        return sendJSON(res, 200, { status: 'starting', uptime: process.uptime(), version: daemon.config?.get?.('daemon.version', '0.1.0') })
      }

      // simple tools registry
      if (req.method === 'GET' && url.pathname === '/tools/registry') {
        const toolRegistry = (daemon.pipeline as any)?.toolRegistry ?? (daemon.toolRegistry as any)
        if (!toolRegistry || typeof toolRegistry.list !== 'function') return sendJSON(res, 503, { error: 'tool registry not initialised' })
        const list = toolRegistry.list().map((t: any) => ({ name: t.name, description: t.description, parameters: t.parameters }))
        return sendJSON(res, 200, list)
      }

      // chat send endpoint used by CLI
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

      // SSE stream for chat tokens
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

        const busHandler = (e: any) => {
          if (e.pluginId !== `session:${sessionId}`) return
          const payload = e.payload as any
          try {
            if (payload?.type === 'turn:token') res.write(`data: ${JSON.stringify({ type: 'token', token: payload.token })}\n\n`)
            else if (payload?.type === 'turn:done') res.write(`data: ${JSON.stringify({ type: 'done' })}\n\n`)
            else if (payload?.type === 'turn:tool_call') res.write(`data: ${JSON.stringify({ type: 'tool_call', tool: payload.tool, input: payload.input })}\n\n`)
            else if (payload?.type === 'turn:error') res.write(`data: ${JSON.stringify({ type: 'error', error: payload.error })}\n\n`)
          } catch { /* ignore */ }
        }

        daemon.bus.on('worker:message', busHandler)
        const ping = setInterval(() => { try { res.write(': ping\n\n') } catch { clearInterval(ping) } }, 15_000)
        req.on('close', () => { clearInterval(ping); daemon.bus.off('worker:message', busHandler) })
        return
      }

      // not found
      sendJSON(res, 404, { error: 'not_found' })
    } catch (err) {
      logger.warn(`admin-api error: ${String(err)}`)
      if (!res.headersSent) sendJSON(res, 500, { error: String(err) })
    }
  }

  let unixServer: http.Server | null = null
  let tcpServer: http.Server | null = null

  return {
    async start() {
      if (unixServer || tcpServer) return { tcpPort: currentTcpPort, unixPath }

      try { if (fs.existsSync(unixPath)) fs.unlinkSync(unixPath) } catch {}

      unixServer = http.createServer(handler)
      unixServer.on('error', (e) => logger.warn(`[admin-api] unix server error: ${String(e)}`))
      unixServer.listen(unixPath, () => {
        try { fs.chmodSync(unixPath, 0o660) } catch {}
        logger.info(`[admin-api] listening on unix:${unixPath}`)
      })

      // Start TCP server, attempt base port and increment if in use
      let boundPort: number | null = null
      for (let i = 0; i < 10; i++) {
        const tryPort = baseTcpPort + i
        const s = http.createServer(handler)
        s.on('error', () => {})
        try {
          await new Promise<void>((resolve, reject) => { s.listen(tryPort, tcpHost, () => resolve()); s.once('error', (err) => reject(err)) })
          tcpServer = s
          boundPort = tryPort
          currentTcpPort = tryPort
          logger.info(`[admin-api] listening on http://${tcpHost}:${tryPort}`)
          break
        } catch (err: any) {
          try { s.close?.() } catch {}
          if (err && err.code === 'EADDRINUSE') continue
          throw err
        }
      }

      return { tcpPort: boundPort, unixPath }
    },
    async stop() {
      if (unixServer) await new Promise<void>((resolve) => unixServer!.close(() => resolve()))
      if (tcpServer) await new Promise<void>((resolve) => tcpServer!.close(() => resolve()))
      try { if (fs.existsSync(unixPath)) fs.unlinkSync(unixPath) } catch {}
      logger.info('[admin-api] stopped')
    }
  }
}
