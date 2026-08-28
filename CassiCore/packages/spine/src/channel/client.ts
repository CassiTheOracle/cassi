/**
 * @cassicore/spine — runtime channel HTTP client.
 *
 * Talks to the focused mind runtime's narrow 127.0.0.1 channel. The client is thin
 * and fetch-based (Node 20+ global fetch); it never imports mind internals — only the
 * channel contract types from `@cassicore/mind-runtime`.
 */

import { createCipheriv, createHash, createHmac, randomBytes, timingSafeEqual } from 'node:crypto'

import type {
  ContextCandidatesRequest,
  ContextCandidatesResponse,
  ContextFeedbackRequest,
  ContextFeedbackResponse,
  ExecuteToolRequest,
  HealthResponse,
  MemorySaveRequest,
  MemorySaveResponse,
  MemorySearchRequest,
  MemorySearchResponse,
  MemoryStatusResponse,
  MirrorSessionRequest,
  SnapshotResponse,
  ToolExecuteResponse,
} from '@cassicore/mind-runtime'

export interface ChannelClientOptions {
  baseUrl?: string
  token?: string
  timeoutMs?: number
}

/** Locate the runtime URL: env wins, else the default loopback (spawn fallback handled
 *  by the factory's spawn path — see index.ts). */
export function resolveChannelUrl(env: NodeJS.ProcessEnv = process.env): string {
  return env.CASSI_MIND_URL ?? (() => {
    const port = Number(env.CASSI_MIND_PORT ?? '7273')
    return `http://127.0.0.1:${port}`
  })()
}

export class NotFoundError extends Error {}
export class UnauthorizedError extends Error {}


function nonEmptyToken(value: string | undefined): string | undefined {
  const token = value?.trim()
  return token || undefined
}

function normalizeLoopbackUrl(value: string): string {
  const url = new URL(value)
  const loopback = url.hostname === '127.0.0.1' || url.hostname === '[::1]' || url.hostname === '::1'
  if (url.protocol !== 'http:' || !loopback || url.username || url.password) {
    throw new Error('Cassi mind channel must use an unauthenticated http loopback URL')
  }
  return url.toString().replace(/\/$/, '')
}

function validProof(actual: string, expected: string): boolean {
  const left = Buffer.from(actual, 'hex')
  const right = Buffer.from(expected, 'hex')
  return left.length === right.length && left.length > 0 && timingSafeEqual(left, right)
}

function channelKey(token: string): Buffer {
  return createHash('sha256').update(`cassi-mind-channel\u0000${token}`).digest()
}

function encryptBody(token: string, body: unknown): string {
  const iv = randomBytes(12)
  const cipher = createCipheriv('aes-256-gcm', channelKey(token), iv)
  const plaintext = Buffer.from(JSON.stringify(body), 'utf8')
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()])
  return JSON.stringify({
    v: 1,
    iv: iv.toString('base64'),
    ciphertext: ciphertext.toString('base64'),
    tag: cipher.getAuthTag().toString('base64'),
  })
}

/** Thin fetch client over the mind-runtime channel. */
export class ChannelClient {
  private readonly baseUrl: string
  private readonly token: string | undefined
  private readonly timeoutMs: number


  constructor(opts: ChannelClientOptions = {}) {
    this.baseUrl = normalizeLoopbackUrl(opts.baseUrl ?? resolveChannelUrl())
    this.token = nonEmptyToken(opts.token ?? process.env.CASSI_MIND_TOKEN)
    this.timeoutMs = opts.timeoutMs ?? 10_000
  }

  get url(): string { return this.baseUrl }

  /** Health probe; token-bearing clients also authenticate server identity. */
  async ping(): Promise<boolean> {
    try {
      if (this.token) return await this.verifyServer(this.timeoutMs)
      const res = await fetch(`${this.baseUrl}/v1/health`, {
        signal: AbortSignal.timeout(this.timeoutMs),
      })
      return res.status === 200
    } catch {
      return false
    }
  }

  async health(): Promise<HealthResponse> {
    return (await this.post('/v1/health', {})) as HealthResponse
  }

  /** Dispatch a retained mind tool to the runtime. Returns the retained string result. */
  async executeTool(tool: string, params: Record<string, unknown>, sessionId?: string): Promise<ToolExecuteResponse> {
    const body: ExecuteToolRequest = { tool, params, sessionId }
    return (await this.post('/v1/tools/execute', body)) as ToolExecuteResponse
  }

  /** Mirror a session lifecycle event into the runtime. */
  async mirrorSession(req: MirrorSessionRequest): Promise<void> {
    await this.post('/v1/session/mirror', req)
  }

  /** Fetch mind-state for the appendEntry episodic journal. */
  async getSnapshot(): Promise<SnapshotResponse> {
    return (await this.post('/v1/snapshot', {})) as SnapshotResponse
  }

  /** Push a harness event (mcp_notification, …) into the mind. */
  async postEvent(req: { type: string; payload: unknown; sessionId?: string }): Promise<unknown> {
    return this.post('/v1/events/push', req)
  }

  // ── memory backend (status/search/save over the shared MnemicField) ──────
  async memoryStatus(): Promise<MemoryStatusResponse> {
    return (await this.post('/v1/memory/status', {})) as MemoryStatusResponse
  }
  async memorySearch(req: MemorySearchRequest): Promise<MemorySearchResponse> {
    return (await this.post('/v1/memory/search', req)) as MemorySearchResponse
  }
  async memorySave(req: MemorySaveRequest): Promise<MemorySaveResponse> {
    return (await this.post('/v1/memory/save', req)) as MemorySaveResponse
  }

  // ── attention context channel (shared ThalamusAttention contract) ────────
  /**
   * Fetch typed Mnemic candidates + source statuses + a cached field advisory for a
   * turn's query. The runtime FAILS OPEN: a deadline overrun returns 200 with empty
   * candidates and `sources[0].status === 'timeout'`, never 5xx. A per-call timeout
   * (default: the client timeout) rejects the fetch — the controller treats that as
   * source-unavailable and still plans locally.
   */
  async contextCandidates(req: ContextCandidatesRequest, opts?: { timeoutMs?: number }): Promise<ContextCandidatesResponse> {
    return (await this.post('/v1/context/candidates', req, opts?.timeoutMs)) as ContextCandidatesResponse
  }

  /**
   * Send ID-only plan feedback (no raw text): which runtime candidate IDs the plan
   * included and the turn outcome. Fire-and-forget by callers — never turn-critical.
   */
  async contextFeedback(req: ContextFeedbackRequest, opts?: { timeoutMs?: number }): Promise<ContextFeedbackResponse> {
    return (await this.post('/v1/context/feedback', req, opts?.timeoutMs)) as ContextFeedbackResponse
  }

  private async post(path: string, body: unknown, timeoutMs?: number): Promise<unknown> {
    const t = timeoutMs ?? this.timeoutMs
    if (!(await this.verifyServer(t))) {
      throw new Error(`Mind runtime identity proof failed at ${this.baseUrl}`)
    }
    const encodedBody = this.token ? encryptBody(this.token, body) : JSON.stringify(body)
    let res: Response
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: encodedBody,
        signal: AbortSignal.timeout(t),
      })
    } catch (err) {
      throw new Error(`Mind runtime unreachable at ${this.baseUrl}${path}: ${String(err)}`)
    }
    if (res.status === 401) throw new UnauthorizedError(`unauthorized at ${path}`)
    if (res.status === 404) throw new NotFoundError(`not found: ${path}`)
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`mind runtime error ${res.status} at ${path}: ${text}`)
    }
    const text = await res.text()
    try { return JSON.parse(text) } catch { return text }
  }

  /**
   * Authenticate the loopback server immediately before EVERY protected request.
   * There is intentionally no positive cache: a replacement process cannot inherit
   * a proof from a prior runtime. Token-bearing bodies are AEAD-encrypted, so even a
   * narrow post-proof rebinding race cannot disclose raw extension context or the
   * bearer itself.
   */
  private async verifyServer(timeoutMs: number): Promise<boolean> {
    const token = this.token
    if (!token) return true
    const nonce = randomBytes(32).toString('hex')
    let response: Response
    try {
      response = await fetch(`${this.baseUrl}/v1/health?nonce=${nonce}`, {
        signal: AbortSignal.timeout(timeoutMs),
      })
    } catch {
      return false
    }
    if (!response.ok) return false
    let payload: unknown
    try {
      payload = await response.json()
    } catch {
      return false
    }
    const proof = typeof (payload as { proof?: unknown }).proof === 'string'
      ? (payload as { proof: string }).proof
      : ''
    const expected = createHmac('sha256', token).update(nonce).digest('hex')
    return validProof(proof, expected)
  }
}
