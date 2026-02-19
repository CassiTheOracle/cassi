import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import type { ILogger } from '../types/interfaces.js'

export function createAdminApi(daemon: any, logger: ILogger) {
  let server: http.Server | null = null
  let unixPath = path.join(os.homedir(), '.claracore', 'admin.sock')
  let tcpHost = '127.0.0.1'
  let tcpPort = 7432

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

  async function handler(req: http.IncomingMessage, res: http.ServerResponse) {
    if (!authOk(req)) {
      sendJSON(res, 401, { error: 'unauthorized' })
      return
    }

    const url = new URL(req.url || '', `http://${tcpHost}:${tcpPort}`)
    const parts = url.pathname.split('/').filter(Boolean)

    try {
      if (req.method === 'GET' && url.pathname === '/health') {
        const uptime = process.uptime()
        const version = daemon.config.get('daemon.version', '0.1.0')
        return sendJSON(res, 200, { status: 'ok', uptime, version })
      }

      if (req.method === 'GET' && parts[0] === 'config' && parts.length === 1) {
        return sendJSON(res, 200, daemon.config.toJSON())
      }

      if (parts[0] === 'config' && parts.length === 2) {
        const key = parts[1]
        if (req.method === 'GET') {
          const val = daemon.config.get(key as string, undefined)
          // source detection: simple heuristic
          const source = val === undefined ? 'default' : 'file'
          return sendJSON(res, 200, { key, value: val, source })
        }
        if (req.method === 'POST') {
          const body = await parseBody(req)
          if (!body || !('value' in body)) return sendJSON(res, 400, { error: 'missing value' })
          // set runtime override on daemon — store in-memory overrides map
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
          // naive register — emit event
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
        // allow POST /plugins/:id/restart — parts would be ['plugins', ':id', 'restart'] but our split differs
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
      if (parts[0] === 'intelligence' && req.method === 'GET') {
        const modules = (daemon.intelligence?.all ?? []).map((m: any) => ({ name: m.name, priority: m.priority, status: 'active' }))
        return sendJSON(res, 200, modules)
      }

      // not found
      sendJSON(res, 404, { error: 'not_found' })
    } catch (err) {
      logger.warn(`admin-api error: ${String(err)}`)
      sendJSON(res, 500, { error: String(err) })
    }
  }

  return {
    async start() {
      if (server) return
      server = http.createServer(handler)

      // Remove existing socket if present
      try {
        if (fs.existsSync(unixPath)) fs.unlinkSync(unixPath)
      } catch {}

      await new Promise<void>((resolve, reject) => {
        server!.listen(unixPath, () => {
          try { fs.chmodSync(unixPath, 0o660) } catch {}
          logger.info(`[admin-api] listening on unix:${unixPath}`)
          resolve()
        })
        server!.on('error', reject)
      })

      await new Promise<void>((resolve, reject) => {
        server!.listen(tcpPort, tcpHost, () => {
          logger.info(`[admin-api] listening on http://${tcpHost}:${tcpPort}`)
          resolve()
        })
        server!.on('error', reject)
      })
    },
    async stop() {
      if (!server) return
      await new Promise<void>((resolve) => server!.close(() => resolve()))
      server = null
      try { if (fs.existsSync(unixPath)) fs.unlinkSync(unixPath) } catch {}
      logger.info('[admin-api] stopped')
    }
  }
}
