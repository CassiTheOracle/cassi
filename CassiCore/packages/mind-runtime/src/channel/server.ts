/**
 * @cassicore/mind-runtime — the narrow internal channel server.
 *
 * A thin localhost HTTP/1.1 JSON server bound to `127.0.0.1` only, on the brief's
 * channel endpoints (plan §1.2 loopback pattern, page 7273 distinct from the retired
 * 7433). Auth = loopback-bind + optional shared bearer token from `CASSI_MIND_TOKEN`
 * (spanning the spine via the same env var). One request–response per call; `requestId`
 * echoed verbatim for correlation.
 *
 * Explicitly NOT served here (plan §5 verdicts 22-31): providers, session infra, CLI,
 * ACP, admin-api, the 54-route admin surface. The retained mind-health read slice
 * folds into `/v1/health` + `/v1/snapshot`.
 *
 * Endpoints (all `POST /…` except `GET /v1/health`):
 *   POST /v1/tools/execute      { tool, params, sessionId } → { ok, result } | { ok:false, error }
 *   POST /v1/session/mirror     { event, sessionId, cwd?, branchFrom?, summary? } → { ack:true }
 *   POST /v1/events/push        { type, payload, sessionId } → { ack:true }
 *   POST /v1/snapshot           {} → { state }
 *   POST /v1/health             {} → { status, uptimeMs, fieldStats?, lightningStatus? }
 *   GET  /v1/health             → 200 "ok"
 *   POST /v1/memory/status      {} → { backend, stats }
 *   POST /v1/memory/search      { query, limit?, type? } → { results: [{id,content,score,metadata}] }
 *   POST /v1/memory/save        { content, type?, metadata?, sessionId? } → { id }
 *   POST /v1/shutdown           {} → { ok }
 */

import { createServer, type Server, type IncomingMessage, type ServerResponse } from 'node:http'

import type { ILogger } from '@cassicore/foundation'

import type { MindRuntime } from '../boot.js'
import { collectMindHealth } from '../health/index.js'
import type {
  ChannelRequest,
  ExecuteToolRequest,
  HealthResponse,
  MemorySaveRequest,
  MemorySaveResponse,
  MemorySearchRequest,
  MemorySearchResponse,
  MemoryStatusResponse,
  MirrorSessionRequest,
  MirrorSessionResponse,
  PushEventRequest,
  PushEventResponse,
  ShutdownRequest,
  ShutdownResponse,
  SnapshotResponse,
  ToolExecuteResponse,
} from './protocol.js'

export interface ChannelServerOptions {
  host?: string
  port?: number
  token?: string
  logger?: ILogger
  /** Called when `/v1/shutdown` fires (default: server.close()). */
  onShutdown?: () => Promise<void> | void
}

const JSON_HEADERS = { 'content-type': 'application/json' } as const

class HttpError extends Error {
  constructor(public readonly statusCode: number, message: string) { super(message) }
}

/** Plain HTTP channel server wrapping a `MindRuntime`. */
export class MindChannelServer {
  private server: Server
  private readonly host: string
  private readonly port: number
  private readonly token: string | undefined
  private readonly logger: ILogger
  private readonly onShutdown: (() => Promise<void> | void) | undefined
  private closeListeners: Array<() => void> = []

  constructor(
    private readonly runtime: MindRuntime,
    opts: ChannelServerOptions = {},
  ) {
    this.host = opts.host ?? '127.0.0.1'
    this.port = opts.port ?? runtime.config.port
    this.token = opts.token ?? runtime.config.token
    this.logger = opts.logger ?? runtime.logger
    this.onShutdown = opts.onShutdown
    this.server = createServer((req, res) => void this.handle(req, res))
    this.server.on('error', (err) => this.logger.error('channel server error', { error: String(err) }))
  }

  /** Register a callback fired once when the underlying server closes. */
  onClosed(cb: () => void): void {
    this.closeListeners.push(cb)
  }

  listen(): Promise<number> {
    return new Promise((resolve, reject) => {
      this.server.listen({ host: this.host, port: this.port }, () => {
        const addr = this.server.address()
        const actualPort = typeof addr === 'object' && addr ? addr.port : this.port
        this.logger.info('Mind channel listening', { host: this.host, port: actualPort })
        resolve(actualPort)
      })
      this.server.once('error', reject)
    })
  }

  address(): { host: string; port: number } {
    const addr = this.server.address()
    const port = typeof addr === 'object' && addr ? addr.port : this.port
    return { host: this.host, port }
  }

  async close(): Promise<void> {
    await new Promise<void>((resolve) => this.server.close(() => resolve()))
    const listeners = this.closeListeners
    this.closeListeners = []
    for (const cb of listeners) cb()
  }

  // ── internals ──────────────────────────────────────────────────────────────

  private async handle(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const started = Date.now()
    try {
      const url = new URL(req.url ?? '/', 'http://localhost')
      // Require auth for everything except plain GET /v1/health.
      if (!this.authorized(req)) throw new HttpError(401, 'unauthorized')

      if (req.method === 'GET' && url.pathname === '/v1/health') {
        res.writeHead(200, { 'content-type': 'text/plain' }).end('ok')
        return
      }

      if (req.method !== 'POST') throw new HttpError(405, 'method not allowed')

      const body = await readBody(req)
      const requestId = (body as ChannelRequest | undefined)?.requestId

      let payload: unknown
      switch (url.pathname) {
        case '/v1/tools/execute':
          payload = await this.executeTool(body as ExecuteToolRequest)
          break
        case '/v1/session/mirror':
          payload = await this.mirrorSession(body as MirrorSessionRequest)
          break
        case '/v1/events/push':
          payload = await this.pushEvent(body as PushEventRequest)
          break
        case '/v1/snapshot':
          payload = await this.snapshot()
          break
        case '/v1/health':
          payload = await this.health()
          break
        case '/v1/memory/status':
          payload = await this.memoryStatus()
          break
        case '/v1/memory/search':
          payload = await this.memorySearch(body as MemorySearchRequest)
          break
        case '/v1/memory/save':
          payload = await this.memorySave(body as MemorySaveRequest)
          break
        case '/v1/shutdown':
          payload = await this.shutdown(body as ShutdownRequest)
          break
        default:
          throw new HttpError(404, 'not found')
      }

      const echoed = typeof payload === 'object' && payload !== null
        ? { ...(payload as Record<string, unknown>), requestId }
        : payload
      res.writeHead(200, JSON_HEADERS)
      res.end(JSON.stringify(echoed))
      this.logger.debug('[channel]', { method: req.method, path: url.pathname, ms: Date.now() - started })
    } catch (err) {
      const http = err instanceof HttpError ? err : new HttpError(500, String(err))
      this.logger.error('channel request failed', { error: String(err), path: req.url })
      res.writeHead(http.statusCode, JSON_HEADERS)
      res.end(JSON.stringify({ error: http.message }))
    }
  }

  private authorized(req: IncomingMessage): boolean {
    if (!this.token) return true
    const auth = req.headers.authorization
    return auth === `Bearer ${this.token}`
  }

  private async executeTool(req: ExecuteToolRequest): Promise<ToolExecuteResponse> {
    if (!req.tool || typeof req.tool !== 'string') throw new HttpError(400, 'tool is required')
    try {
      const { result } = await this.runtime.executeTool(req.tool, req.params ?? {}, req.sessionId)
      return { ok: true, result }
    } catch (err) {
      return { ok: false, error: String(err) }
    }
  }

  private async mirrorSession(req: MirrorSessionRequest): Promise<MirrorSessionResponse> {
    if (!req.event || !req.sessionId) throw new HttpError(400, 'event + sessionId required')
    this.runtime.sessions.mirror(req)
    return { ack: true }
  }

  private async pushEvent(req: PushEventRequest): Promise<PushEventResponse> {
    if (!req.type || typeof req.type !== 'string') throw new HttpError(400, 'type required')
    // Push the harness event as a field/state event on the retained bus so mind
    // loops (mcp_notification consumers, etc.) observe it reactively.
    try {
      this.runtime.bus.emit({
        type: req.type,
        payload: req.payload,
        sessionId: req.sessionId,
        timestamp: new Date(),
      } as never)
    } catch (err) {
      this.logger.warn('event push emit failed (non-fatal)', { error: String(err), type: req.type })
    }
    return { ack: true }
  }

  private async snapshot(): Promise<SnapshotResponse> {
    const fieldStats = this.safeFieldStats()
    return {
      state: {
        memory: this.runtime.memory.status(),
        loops: { unifiedLoopRunning: true, cortexOscillation: !!this.runtime.intelligence.cortex },
        sessions: this.runtime.sessions.snapshotEntries(),
        uptimeMs: Date.now() - this.runtime.startedAt,
        health: 'ok',
      },
    }
  }

  private async health(): Promise<HealthResponse> {
    return {
      status: 'ok',
      uptimeMs: Date.now() - this.runtime.startedAt,
      fieldStats: this.safeFieldStats(),
      lightningStatus: this.safeLightningStatus(),
      retained: collectMindHealth(this.runtime),
    }
  }

  private safeFieldStats(): Record<string, unknown> | null {
    try {
      return this.runtime.memory.status().stats
    } catch {
      return null
    }
  }

  private safeLightningStatus(): Record<string, unknown> | null {
    try {
      return this.runtime.memory.status().lightning
    } catch {
      return null
    }
  }

  private async memoryStatus(): Promise<MemoryStatusResponse> {
    return { backend: 'mnemic-field', stats: this.safeFieldStats() }
  }

  private async memorySearch(req: MemorySearchRequest): Promise<MemorySearchResponse> {
    if (!req.query) return { results: [] }
    const limit = typeof req.limit === 'number' ? req.limit : 5
    const results = await this.runtime.memory.search(req.query, { limit, type: req.type, sessionId: req.sessionId })
    return { results }
  }

  private async memorySave(req: MemorySaveRequest): Promise<MemorySaveResponse> {
    if (!req.content || typeof req.content !== 'string') throw new HttpError(400, 'content required')
    const id = this.runtime.memory.save({
      content: req.content,
      type: req.type,
      metadata: req.metadata,
      sessionId: req.sessionId,
    })
    return { id }
  }

  private async shutdown(_req: ShutdownRequest): Promise<ShutdownResponse> {
    // Graceful stop: respond first, then close the server + release the field.
    setImmediate(() => {
      if (this.onShutdown) void Promise.resolve(this.onShutdown())
      void this.runtime.close()
      void this.close()
    })
    return { ok: true }
  }
}

function readBody(req: IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = []
    req.on('data', (c: Buffer) => chunks.push(c))
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8')
      if (!raw) return resolve({})
      try { resolve(JSON.parse(raw)) } catch (err) { reject(new HttpError(400, 'invalid JSON')) }
    })
    req.on('error', reject)
  })
}

/** Locate the runtime's channel URL (for the spine / supervisors). */
export function defaultChannelUrl(port: number, token?: string): string {
  return `http://127.0.0.1:${port}`
}
