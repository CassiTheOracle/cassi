/**
 * CassiCore daemon HTTP + SSE client.
 *
 * Connects via Unix socket (preferred) with HTTP fallback, matching the same
 * dual-transport strategy as the old Go client but with zero type duplication.
 */

import http from 'node:http'
import path from 'node:path'
import os from 'node:os'

import type {
  DaemonInfo,
  DaemonModel,
  DaemonSession,
  DaemonTeam,
  DaemonTeamCheckpoint,
  DaemonTeamStatus,
  DaemonImageAttachment,
  SessionMessage,
  TurnEvent,
  CognitiveEvent,
  CommandResponse,
  ProviderHealth,
} from '../types/index.js'

const DEFAULT_DAEMON_URL = 'http://localhost:7433'
const DEFAULT_SOCKET_PATH = path.join(os.homedir(), '.cassicore', 'admin.sock')
const CONNECT_TIMEOUT_MS = 5_000

// ── Transport helpers ───────────────────────────────────────────────────────

interface RequestOptions {
  method: string
  path: string
  body?: unknown
  headers?: Record<string, string>
  signal?: AbortSignal
}

function makeRequest(
  opts: RequestOptions,
  socketPath?: string,
): Promise<http.IncomingMessage> {
  return new Promise((resolve, reject) => {
    const isSocket = !!socketPath
    const bodyStr = opts.body != null ? JSON.stringify(opts.body) : undefined

    const reqOpts: http.RequestOptions = {
      method: opts.method,
      path: opts.path,
      headers: {
        ...opts.headers,
        ...(bodyStr ? { 'Content-Type': 'application/json' } : {}),
      },
      signal: opts.signal,
    }

    if (isSocket) {
      reqOpts.socketPath = socketPath
      reqOpts.hostname = 'localhost'
    } else {
      const url = new URL(opts.path, DEFAULT_DAEMON_URL)
      reqOpts.hostname = url.hostname
      reqOpts.port = Number(url.port) || 7433
      reqOpts.path = url.pathname + url.search
    }

    const req = http.request(reqOpts, resolve)
    req.on('error', reject)
    if (bodyStr) req.write(bodyStr)
    req.end()
  })
}

async function readJSON<T>(res: http.IncomingMessage): Promise<T> {
  const chunks: Buffer[] = []
  for await (const chunk of res) {
    chunks.push(chunk as Buffer)
  }
  return JSON.parse(Buffer.concat(chunks).toString('utf-8'))
}

// ── SSE parser ──────────────────────────────────────────────────────────────

function parseSSEStream(
  res: http.IncomingMessage,
  onEvent: (event: TurnEvent) => void,
  onEnd: () => void,
): void {
  let eventType = ''
  let dataBuf = ''
  let remainder = ''

  res.setEncoding('utf-8')

  res.on('data', (chunk: string) => {
    remainder += chunk
    const lines = remainder.split('\n')
    // Keep the last incomplete line
    remainder = lines.pop() ?? ''

    for (const line of lines) {
      if (line === '') {
        // Blank line → dispatch event
        if (dataBuf) {
          const type = eventType || 'message'
          try {
            const data = JSON.parse(dataBuf)
            onEvent({ type, data })
          } catch {
            // Non-JSON data payload, forward as string
            onEvent({ type, data: dataBuf })
          }
        }
        eventType = ''
        dataBuf = ''
      } else if (line.startsWith('event:')) {
        eventType = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        const payload = line.slice(5).replace(/^ /, '')
        if (dataBuf) dataBuf += '\n'
        dataBuf += payload
      }
      // id: and retry: lines are ignored
    }
  })

  res.on('end', () => {
    // Flush any remaining event
    if (dataBuf) {
      const type = eventType || 'message'
      try {
        const data = JSON.parse(dataBuf)
        onEvent({ type, data })
      } catch {
        onEvent({ type, data: dataBuf })
      }
    }
    onEnd()
  })

  res.on('error', () => {
    onEnd()
  })
}

// ── Client ──────────────────────────────────────────────────────────────────

export class DaemonClient {
  private socketPath: string | undefined
  private baseURL: string
  private preferSocket: boolean
  private connectedVia: 'unix' | 'http' = 'http'

  constructor(opts?: { socketPath?: string; baseURL?: string }) {
    this.baseURL = opts?.baseURL ?? DEFAULT_DAEMON_URL
    this.socketPath = opts?.socketPath ?? DEFAULT_SOCKET_PATH
    this.preferSocket = !!this.socketPath
  }

  /** The URL or socket the client is connected to. */
  get connectionString(): string {
    if (this.connectedVia === 'unix' && this.socketPath) {
      return `unix:${this.socketPath}`
    }
    return this.baseURL
  }

  // ── Low-level request with socket→HTTP fallback ─────────────────────────

  private async request(opts: RequestOptions): Promise<http.IncomingMessage> {
    if (this.preferSocket && this.socketPath) {
      try {
        const res = await makeRequest(opts, this.socketPath)
        this.connectedVia = 'unix'
        return res
      } catch {
        // Socket failed — fall through to HTTP
      }
    }

    try {
      const res = await makeRequest(opts)
      this.connectedVia = 'http'
      this.preferSocket = false
      return res
    } catch (err) {
      throw new Error(`Daemon unreachable at ${this.baseURL}: ${String(err)}`)
    }
  }

  private async getJSON<T>(urlPath: string): Promise<T> {
    const res = await this.request({ method: 'GET', path: urlPath })
    if (res.statusCode !== 200) {
      throw new Error(`Daemon returned HTTP ${res.statusCode} for ${urlPath}`)
    }
    return readJSON<T>(res)
  }

  private async postJSON<T>(urlPath: string, body?: unknown): Promise<T> {
    const res = await this.request({ method: 'POST', path: urlPath, body })
    if (res.statusCode !== 200) {
      const data = await readJSON<any>(res)
      throw new Error(data?.error ?? `HTTP ${res.statusCode} for POST ${urlPath}`)
    }
    return readJSON<T>(res)
  }

  // ── Public API ──────────────────────────────────────────────────────────

  /** Check daemon reachability. Returns the /cassicore/info payload. */
  async ping(): Promise<DaemonInfo> {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), CONNECT_TIMEOUT_MS)
    try {
      const res = await this.request({
        method: 'GET',
        path: '/cassicore/info',
        signal: controller.signal,
      })
      return readJSON<DaemonInfo>(res)
    } finally {
      clearTimeout(timeout)
    }
  }

  /** List available models. */
  async models(): Promise<DaemonModel[]> {
    const resp = await this.getJSON<{ models: DaemonModel[] }>('/models')
    return resp.models
  }

  /** Get provider health status. */
  async providerHealth(): Promise<ProviderHealth[]> {
    const resp = await this.getJSON<{ providers: ProviderHealth[] }>('/health/providers')
    return resp.providers
  }

  /** List sessions, optionally filtered by project path. */
  async sessions(projectPath?: string): Promise<DaemonSession[]> {
    const qs = projectPath ? `?projectPath=${encodeURIComponent(projectPath)}` : ''
    const resp = await this.getJSON<{ sessions: DaemonSession[] }>(`/sessions${qs}`)
    return resp.sessions
  }

  /** Get a single session. */
  async session(sessionId: string): Promise<DaemonSession> {
    return this.getJSON<DaemonSession>(`/sessions/${sessionId}`)
  }

  /** Get session message history. */
  async sessionMessages(sessionId: string, limit?: number): Promise<SessionMessage[]> {
    const qs = limit ? `?limit=${limit}` : ''
    const resp = await this.getJSON<{ messages: SessionMessage[] }>(
      `/sessions/${sessionId}/messages${qs}`,
    )
    return resp.messages
  }

  /** Dispatch a slash command. Returns the full response including action buttons. */
  async command(sessionId: string, command: string): Promise<CommandResponse> {
    const resp = await this.postJSON<CommandResponse>(
      `/sessions/${sessionId}/command`,
      { command },
    )
    return resp
  }

  /**
   * Fetch the list of available slash commands from the daemon.
   * Parses the /help output to extract command names.
   */
  async listCommands(sessionId: string): Promise<string[]> {
    try {
      const resp = await this.command(sessionId, '/help')
      // Parse command names from help text: lines matching /^\s+\/\w+/
      const names: string[] = []
      for (const line of resp.text.split('\n')) {
        const match = line.match(/^\s+(\/\S+)/)
        if (match) names.push(match[1]!)
      }
      return names
    } catch {
      return []
    }
  }

  /**
   * Generate a new session ID.
   *
   * Sessions are created implicitly by the daemon when the first turn is
   * sent — there is no explicit creation endpoint. The TUI generates IDs
   * client-side using the same format the daemon uses internally.
   */
  generateSessionId(): string {
    const ts = Date.now().toString(36)
    const rand = Math.random().toString(36).slice(2, 8)
    return `tui_${ts}_${rand}`
  }

  // ── Turn streaming (SSE) ────────────────────────────────────────────────

  /**
   * Stream a turn from the daemon. Returns an async iterable of TurnEvents.
   * The daemon runs the full intelligence stack internally.
   */
  async streamTurn(
    sessionId: string,
    content: string,
    model?: string,
    attachments?: DaemonImageAttachment[],
    signal?: AbortSignal,
  ): Promise<AsyncIterable<TurnEvent>> {
    const body: Record<string, unknown> = {
      content,
      channelId: 'channel:tui',
      senderId: `tui:${process.pid}`,
    }
    if (model) body.model = model
    if (attachments?.length) body.attachments = attachments

    const res = await this.request({
      method: 'POST',
      path: `/sessions/${sessionId}/turn/stream`,
      body,
      headers: { Accept: 'text/event-stream' },
      signal,
    })

    if (res.statusCode !== 200) {
      throw new Error(`Daemon returned HTTP ${res.statusCode} for turn stream`)
    }

    return {
      [Symbol.asyncIterator](): AsyncIterator<TurnEvent> {
        const buffer: TurnEvent[] = []
        let done = false
        let resolve: ((value: IteratorResult<TurnEvent>) => void) | null = null

        parseSSEStream(
          res,
          (event) => {
            if (resolve) {
              const r = resolve
              resolve = null
              r({ value: event, done: false })
            } else {
              buffer.push(event)
            }
          },
          () => {
            done = true
            if (resolve) {
              const r = resolve
              resolve = null
              r({ value: undefined as any, done: true })
            }
          },
        )

        return {
          next(): Promise<IteratorResult<TurnEvent>> {
            if (buffer.length > 0) {
              return Promise.resolve({ value: buffer.shift()!, done: false })
            }
            if (done) {
              return Promise.resolve({ value: undefined as any, done: true })
            }
            return new Promise((r) => {
              resolve = r
            })
          },
        }
      },
    }
  }

  // ── Cognitive event stream (SSE) ────────────────────────────────────────

  /**
   * Subscribe to the cognitive event stream. Returns an async iterable.
   * The stream includes thinker, dialectic, scout, autonomy, memory events.
   */
  async subscribeEvents(
    sessionId?: string,
    signal?: AbortSignal,
  ): Promise<AsyncIterable<CognitiveEvent>> {
    const qs = sessionId ? `?sessionId=${sessionId}` : ''
    const res = await this.request({
      method: 'GET',
      path: `/events/stream${qs}`,
      headers: { Accept: 'text/event-stream' },
      signal,
    })

    if (res.statusCode !== 200) {
      throw new Error(`Daemon returned HTTP ${res.statusCode} for events stream`)
    }

    return {
      [Symbol.asyncIterator](): AsyncIterator<CognitiveEvent> {
        const buffer: CognitiveEvent[] = []
        const MAX_BUFFER = 200  // Bound to prevent OOM from slow consumers
        let done = false
        let resolve: ((value: IteratorResult<CognitiveEvent>) => void) | null = null

        parseSSEStream(
          res,
          (event) => {
            const ce: CognitiveEvent = {
              ...(event.data as Record<string, unknown>),
              type: event.type,
              timestamp: (event.data as any)?.timestamp ?? Date.now(),
              eventId: (event.data as any)?.eventId ?? '',
            }
            if (resolve) {
              const r = resolve
              resolve = null
              r({ value: ce, done: false })
            } else {
              buffer.push(ce)
              // Drop oldest events if buffer exceeds max
              while (buffer.length > MAX_BUFFER) {
                buffer.shift()
              }
            }
          },
          () => {
            done = true
            if (resolve) {
              const r = resolve
              resolve = null
              r({ value: undefined as any, done: true })
            }
          },
        )

        // Also handle stream errors — without this, the iterator hangs
        // forever on half-open connections or unexpected stream termination.
        res.on('error', () => {
          done = true
          if (resolve) {
            const r = resolve
            resolve = null
            r({ value: undefined as any, done: true })
          }
        })

        return {
          next(): Promise<IteratorResult<CognitiveEvent>> {
            if (buffer.length > 0) {
              return Promise.resolve({ value: buffer.shift()!, done: false })
            }
            if (done) {
              return Promise.resolve({ value: undefined as any, done: true })
            }
            return new Promise((r) => {
              resolve = r
            })
          },
        }
      },
    }
  }

  // ── Teams ─────────────────────────────────────────────────────────────

  async teams(): Promise<DaemonTeam[]> {
    const resp = await this.getJSON<{ teams: DaemonTeam[] }>('/teams')
    return resp.teams
  }

  async teamStatus(teamId?: string): Promise<DaemonTeamStatus> {
    const qs = teamId ? `?teamId=${teamId}` : ''
    return this.getJSON<DaemonTeamStatus>(`/teams/status${qs}`)
  }

  async teamCheckpoints(teamId?: string): Promise<DaemonTeamCheckpoint[]> {
    const qs = teamId ? `?teamId=${teamId}` : ''
    const resp = await this.getJSON<{ checkpoints: DaemonTeamCheckpoint[] }>(
      `/teams/checkpoints${qs}`,
    )
    return resp.checkpoints
  }

  async teamAction(action: string, teamId?: string, message?: string): Promise<void> {
    const body: Record<string, string> = {}
    if (teamId) body.teamId = teamId
    if (message) body.reason = message
    await this.postJSON(`/teams/${action}`, body)
  }

  async teamCheckpointAction(
    checkpointId: string,
    action: 'approve' | 'reject',
    message?: string,
  ): Promise<void> {
    await this.postJSON(`/teams/checkpoints/${checkpointId}`, {
      action,
      message: message ?? '',
    })
  }

  // ── Autonomy confirmations ─────────────────────────────────────────────

  async approveConfirmation(id: string): Promise<void> {
    await this.request({
      method: 'POST',
      path: `/intelligence/multi-agent/confirmations/${id}/approve`,
    })
  }

  async rejectConfirmation(id: string): Promise<void> {
    await this.request({
      method: 'POST',
      path: `/intelligence/multi-agent/confirmations/${id}/reject`,
    })
  }

  // ── Session injection (mid-turn messages) ──────────────────────────────

  async inject(sessionId: string, content: string, source = 'tui'): Promise<void> {
    await this.postJSON(`/sessions/${sessionId}/inject`, { content, source })
  }
}
