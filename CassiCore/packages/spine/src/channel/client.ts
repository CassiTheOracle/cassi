/**
 * @cassicore/spine — runtime channel HTTP client.
 *
 * Talks to the focused mind runtime's narrow 127.0.0.1 channel. The client is thin
 * and fetch-based (Node 20+ global fetch); it never imports mind internals — only the
 * channel contract types from `@cassicore/mind-runtime`.
 */

import type {
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

/** Thin fetch client over the mind-runtime channel. */
export class ChannelClient {
  private readonly baseUrl: string
  private readonly token: string | undefined
  private readonly timeoutMs: number

  constructor(opts: ChannelClientOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? resolveChannelUrl()).replace(/\/$/, '')
    this.token = opts.token ?? process.env.CASSI_MIND_TOKEN
    this.timeoutMs = opts.timeoutMs ?? 10_000
  }

  get url(): string { return this.baseUrl }

  /** Health probe (plain GET). Returns true when the runtime answers 200. */
  async ping(): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/v1/health`, { signal: AbortSignal.timeout(this.timeoutMs) })
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

  private async post(path: string, body: unknown): Promise<unknown> {
    let res: Response
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          ...(this.token ? { authorization: `Bearer ${this.token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(this.timeoutMs),
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
}
