/**
 * @cassicore/mind-runtime — the narrow internal channel server.
 *
 * A thin localhost HTTP/1.1 JSON server bound to `127.0.0.1` only, on the brief's
 * channel endpoints (plan §1.2 loopback pattern, port 7273 distinct from retired 7433).
 * Auth = loopback bind plus optional `CASSI_MIND_TOKEN` bearer shared with the spine.
 * POST requests additionally require `application/json`, reject browser `Origin`
 * requests, and enforce a bounded body; this keeps an unauthenticated loopback
 * deployment outside the browser-CSRF surface.
 * One request–response per call; `requestId` is echoed verbatim for correlation.
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
 *   POST /v1/context/candidates { sessionId, turnId, query, limit?, deadlineMs?, includeFieldShadow? }
 *                              → { candidates, sources, fieldAdvisory }   (shared context seam; deadline fails open)
 *   POST /v1/context/feedback   { sessionId, turnId, planId, includedCandidateIds, outcome } → { ack:true }
 *   POST /v1/context/action     exact text-free tool start/outcome → { ack:true }
 *   POST /v1/context/status     {} → read-only candidate/counterflow/journal recovery status
 *   POST /v1/shutdown           {} → { ok }
 */

import { createServer, type Server, type IncomingMessage, type ServerResponse } from 'node:http'
import { createDecipheriv, createHash, createHmac } from 'node:crypto'

import type { ILogger } from '@cassicore/foundation'

import type { MindRuntime } from '../boot.js'
import { collectMindHealth } from '../health/index.js'
import { ContextRequestError } from '../context/candidates.js'
import type {
  ChannelRequest,
  ContextCandidatesRequest,
  ContextActionRequest,
  ContextActionResponse,
  ContextCandidatesResponse,
  ContextFeedbackRequest,
  ContextFeedbackResponse,
  ContextStatusResponse,
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
const MAX_BODY_BYTES = 1024 * 1024
const MAX_BODY_CHUNKS = 1_024
const BODY_READ_TIMEOUT_MS = 10_000

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
    this.token = (opts.token ?? runtime.config.token)?.trim() || undefined
    this.logger = opts.logger ?? runtime.logger
    this.onShutdown = opts.onShutdown
    this.server = createServer((req, res) => void this.handle(req, res))
    // Bound slow/unread request bodies even when routing rejects before `readBody`.
    this.server.requestTimeout = BODY_READ_TIMEOUT_MS
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
    // A keep-alive loopback client must not make runtime shutdown wait for the
    // server's default idle timeout (which is minutes on recent Node releases).
    this.server.closeIdleConnections?.()
    this.server.closeAllConnections?.()
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
      if (req.method === 'GET' && url.pathname === '/v1/health') {
        this.respondHealthProbe(req, res, url)
        return
      }

      if (req.method !== 'POST') throw new HttpError(405, 'method not allowed')
      // This is an internal process-to-process channel, never a browser API.
      // Rejecting every browser Origin plus non-JSON simple request prevents a
      // malicious page from driving loopback endpoints when no bearer is configured.
      if (req.headers.origin !== undefined) throw new HttpError(403, 'browser origins are not allowed')
      const contentType = req.headers['content-type']
      if (typeof contentType !== 'string' || !/^application\/json(?:\s*;|$)/i.test(contentType)) {
        throw new HttpError(415, 'content-type must be application/json')
      }

      const wireBody = await readBody(req, MAX_BODY_BYTES)
      const body = this.decodeAuthorizedBody(req, wireBody)
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
        case '/v1/context/status':
          payload = this.contextStatus()
          break
        case '/v1/context/candidates':
          payload = await this.contextCandidates(body as ContextCandidatesRequest)
          break
        case '/v1/context/feedback':
          payload = await this.contextFeedback(body as ContextFeedbackRequest)
          break
        case '/v1/context/action':
          payload = await this.contextAction(body as ContextActionRequest)
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

  private decodeAuthorizedBody(req: IncomingMessage, wireBody: unknown): unknown {
    if (this.authorized(req)) return wireBody
    if (!this.token || !isEncryptedEnvelope(wireBody)) throw new HttpError(401, 'unauthorized')
    try {
      const iv = Buffer.from(wireBody.iv, 'base64')
      const ciphertext = Buffer.from(wireBody.ciphertext, 'base64')
      const tag = Buffer.from(wireBody.tag, 'base64')
      if (iv.length !== 12 || tag.length !== 16 || ciphertext.length === 0) {
        throw new Error('invalid encrypted envelope')
      }
      const key = createHash('sha256').update(`cassi-mind-channel\u0000${this.token}`).digest()
      const decipher = createDecipheriv('aes-256-gcm', key, iv)
      decipher.setAuthTag(tag)
      const plaintext = Buffer.concat([decipher.update(ciphertext), decipher.final()]).toString('utf8')
      return JSON.parse(plaintext) as unknown
    } catch {
      // Do not leak crypto/parser detail from a channel boundary.
      throw new HttpError(401, 'unauthorized')
    }
  }

  /**
   * Proves server possession of the bearer without exposing it to a potentially
   * pre-bound loopback listener. Spine verifies this HMAC before sending raw
   * provider-context data or an Authorization header.
   */
  private respondHealthProbe(req: IncomingMessage, res: ServerResponse, url: URL): void {
    if (!this.token) {
      res.writeHead(200, { 'content-type': 'text/plain' }).end('ok')
      return
    }
    const nonce = url.searchParams.get('nonce')
    if (!nonce || !/^[a-f0-9]{32,128}$/i.test(nonce)) {
      if (!this.authorized(req)) throw new HttpError(401, 'unauthorized')
      res.writeHead(200, { 'content-type': 'text/plain' }).end('ok')
      return
    }
    const proof = createHmac('sha256', this.token).update(nonce).digest('hex')
    res.writeHead(200, JSON_HEADERS).end(JSON.stringify({ ok: true, proof }))
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
      tags: req.tags,
      provenance: req.provenance,
      sessionId: req.sessionId,
    })
    return { id }
  }

  private contextStatus(): ContextStatusResponse {
    return {
      schemaVersion: 1,
      candidates: this.runtime.context.status(),
      journal: {
        stream: this.runtime.field.fieldStreamStatus(),
        verification: this.runtime.field.fieldJournalVerificationStatus(),
        unresolvedActions: this.runtime.field.unresolvedActionEpisodes(),
      },
    }
  }

  private async contextCandidates(req: ContextCandidatesRequest): Promise<ContextCandidatesResponse> {
    try {
      return await this.runtime.context.candidates(req)
    } catch (err) {
      if (err instanceof ContextRequestError) throw new HttpError(err.statusCode, err.message)
      throw err
    }
  }

  private async contextFeedback(req: ContextFeedbackRequest): Promise<ContextFeedbackResponse> {
    try {
      return await this.runtime.context.feedback(req)
    } catch (err) {
      if (err instanceof ContextRequestError) throw new HttpError(err.statusCode, err.message)
      throw err
    }
  }

  private async contextAction(req: ContextActionRequest): Promise<ContextActionResponse> {
    try {
      return await this.runtime.context.action(req)
    } catch (err) {
      if (err instanceof ContextRequestError) throw new HttpError(err.statusCode, err.message)
      throw err
    }
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
async function readBody(req: IncomingMessage, maxBytes: number): Promise<unknown> {
  const declaredLength = Number(req.headers['content-length'])
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    req.destroy()
  }, BODY_READ_TIMEOUT_MS)
  if (Number.isFinite(declaredLength) && declaredLength > maxBytes) {
    // Return a normal 413 promptly, but keep a deadline while Node drains an
    // oversized declared body so a slow sender cannot hold the socket forever.
    req.once('end', () => clearTimeout(timer))
    req.resume()
    throw new HttpError(413, `request body exceeds ${maxBytes} bytes`)
  }

  const chunks: Buffer[] = []
  let bytes = 0
  let chunkCount = 0
  try {
    for await (const rawChunk of req) {
      if (timedOut) throw new HttpError(408, 'request body timed out')
      const chunk = Buffer.isBuffer(rawChunk) ? rawChunk : Buffer.from(rawChunk)
      bytes += chunk.length
      chunkCount += 1
      if (bytes > maxBytes || chunkCount > MAX_BODY_CHUNKS) {
        req.destroy()
        throw new HttpError(413, `request body exceeds ${maxBytes} bytes`)
      }
      chunks.push(chunk)
    }
  } catch (error) {
    if (timedOut) throw new HttpError(408, 'request body timed out')
    throw error
  } finally {
    clearTimeout(timer)
  }

  const raw = Buffer.concat(chunks, bytes).toString('utf8')
  if (!raw) return {}
  try {
    return JSON.parse(raw)
  } catch {
    throw new HttpError(400, 'invalid JSON')
  }
}

interface EncryptedEnvelope {
  v: 1
  iv: string
  ciphertext: string
  tag: string
}

function isEncryptedEnvelope(value: unknown): value is EncryptedEnvelope {
  if (!value || typeof value !== 'object') return false
  const envelope = value as Record<string, unknown>
  return envelope.v === 1
    && typeof envelope.iv === 'string'
    && typeof envelope.ciphertext === 'string'
    && typeof envelope.tag === 'string'
}

/** Locate the runtime's channel URL (for the spine / supervisors). */
export function defaultChannelUrl(port: number, token?: string): string {
  return `http://127.0.0.1:${port}`
}
