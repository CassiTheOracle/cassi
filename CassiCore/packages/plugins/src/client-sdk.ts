/**
 * CassiCore Plugin Client SDK
 *
 * Lightweight client that connects to a running CassiCore daemon and
 * provides a typed API matching the plugin protocol. This is what a
 * new client integration would import to connect.
 *
 * Usage:
 *
 *   import { CassiCoreClient } from '@cassicore/plugin-sdk'
 *
 *   const client = new CassiCoreClient({
 *     socketPath: '~/.cassicore/admin.sock',  // or url: 'http://localhost:7433'
 *     manifest: {
 *       id: 'my-editor',
 *       name: 'My Editor Plugin',
 *       version: '1.0.0',
 *       capabilities: ['session', 'context', 'memory'],
 *       transport: 'unix-socket',
 *     },
 *   })
 *
 *   await client.connect()
 *   const ctx = await client.context.get('session-123', { contextLimit: 128000 })
 *   await client.session.turnComplete('session-123', userMsg, assistantResp, 'gpt-4')
 */

import http from 'node:http'
import { homedir } from 'node:os'
import { join } from 'node:path'
import type {
  CoreToPlugin,
  PluginManifest,
  PluginCapability,
  PluginToCore,
  ContextResponse,
  CompactResponse,
  DirectiveResponse,
  StoredChunk,
  TokenUsage,
  ToolDefinition,
  ToolInvokeRequest,
} from '../../types/plugin.js'

export interface CassiCoreClientConfig {
  /** Path to the CassiCore admin Unix socket */
  socketPath?: string
  /** HTTP URL if not using Unix socket */
  url?: string
  /** Plugin manifest — who this client is */
  manifest: PluginManifest
  /** Heartbeat interval in ms (default: 60000) */
  heartbeatIntervalMs?: number
}

export interface SendResult {
  ok: boolean
  data?: unknown
  error?: string
}

export interface PluginEvent {
  type: string
  data: unknown
}

type PluginToolHandler = (args: Record<string, unknown>, event: ToolInvokeRequest) => Promise<unknown>

export class CassiCoreClient {
  private config: CassiCoreClientConfig
  private apiKey: string | null = null
  private grantedCapabilities: PluginCapability[] = []
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private baseUrl?: string
  private socketPath?: string
  private eventReq: http.ClientRequest | null = null
  private eventBuffer = ''
  private eventListeners = new Set<(event: PluginEvent) => void>()
  private toolHandlers = new Map<string, PluginToolHandler>()

  readonly session: SessionAPI
  readonly context: ContextAPI
  readonly memory: MemoryAPI
  readonly chunks: ChunkAPI
  readonly intelligence: IntelligenceAPI
  readonly tools: ToolAPI

  constructor(config: CassiCoreClientConfig) {
    this.config = config
    this.baseUrl = config.url
    this.socketPath = config.url ? undefined : (config.socketPath ?? join(homedir(), '.cassicore', 'admin.sock'))

    this.session = new SessionAPI(this)
    this.context = new ContextAPI(this)
    this.memory = new MemoryAPI(this)
    this.chunks = new ChunkAPI(this)
    this.intelligence = new IntelligenceAPI(this)
    this.tools = new ToolAPI(this)
  }

  /** Connect to CassiCore and register as a plugin */
  async connect(): Promise<void> {
    this.eventBuffer = ''

    const res = await this.fetch('/plugin/register', {
      method: 'POST',
      body: this.config.manifest,
    })

    if (!res.ok) {
      throw new Error(`Plugin registration failed: ${res.error}`)
    }

    this.apiKey = res.apiKey as string
    this.grantedCapabilities = res.grantedCapabilities as PluginCapability[]

    // Start heartbeat
    const interval = this.config.heartbeatIntervalMs ?? 60_000
    this.heartbeatTimer = setInterval(() => {
      this.fetch('/plugin/heartbeat', { method: 'POST' }).catch(() => {})
    }, interval)
  }

  /** Disconnect from CassiCore */
  async disconnect(): Promise<void> {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }

    if (this.apiKey) {
      await this.fetch(`/plugin/${this.config.manifest.id}`, { method: 'DELETE' }).catch(() => {})
      this.apiKey = null
    }

    if (this.eventReq) {
      this.eventReq.destroy()
      this.eventReq = null
    }
    this.eventBuffer = ''
  }

  /** Check if a capability was granted */
  hasCapability(capability: PluginCapability): boolean {
    return this.grantedCapabilities.includes(capability)
  }

  /** Send a typed plugin protocol message to CassiCore */
  async send(message: Omit<PluginToCore, 'pluginId' | 'timestamp'>): Promise<SendResult> {
    const full = {
      ...message,
      pluginId: this.config.manifest.id,
      timestamp: Date.now(),
    }

    return this.fetch('/plugin/message', {
      method: 'POST',
      body: full,
    })
  }

  async subscribe(filters: string[] = ['*']): Promise<void> {
    if (this.eventReq) return
    if (!this.apiKey) throw new Error('Connect before subscribing to plugin events')

    await this.send({ type: 'events.subscribe', filter: filters } as PluginToCore)

    const headers: Record<string, string> = {
      Accept: 'text/event-stream',
      Authorization: `Bearer ${this.apiKey}`,
    }

    const requestOptions: http.RequestOptions = this.socketPath
      ? {
          socketPath: this.socketPath,
          path: '/plugin/events',
          method: 'GET',
          headers,
          timeout: 0,
        }
      : (() => {
          const url = new URL('/plugin/events', this.baseUrl ?? 'http://127.0.0.1:7433')
          return {
            hostname: url.hostname,
            port: url.port || 7433,
            path: url.pathname + url.search,
            method: 'GET',
            headers,
            timeout: 0,
          }
        })()

    this.eventReq = http.request(requestOptions, (res) => {
      res.setEncoding('utf8')
      res.on('data', (chunk: string) => {
        this.eventBuffer += chunk
        this.processEventBuffer()
      })
      res.on('close', () => {
        this.eventReq = null
      })
      res.on('end', () => {
        this.eventReq = null
      })
    })

    this.eventReq.on('error', () => {
      this.eventReq = null
    })
    this.eventReq.end()
  }

  onEvent(listener: (event: PluginEvent) => void): () => void {
    this.eventListeners.add(listener)
    return () => {
      this.eventListeners.delete(listener)
    }
  }

  registerToolHandler(name: string, handler: PluginToolHandler): void {
    this.toolHandlers.set(name, handler)
  }

  private processEventBuffer(): void {
    while (true) {
      const boundary = this.eventBuffer.indexOf('\n\n')
      if (boundary === -1) break

      const raw = this.eventBuffer.slice(0, boundary)
      this.eventBuffer = this.eventBuffer.slice(boundary + 2)
      if (!raw.trim() || raw.startsWith(':')) continue

      let eventType = 'message'
      let data = ''
      for (const line of raw.split('\n')) {
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          data += (data ? '\n' : '') + line.slice(5).trimStart()
        }
      }

      if (!data) continue

      try {
        const parsed = JSON.parse(data) as CoreToPlugin | Record<string, unknown>
        if (eventType === 'worker:message') {
          const payload = (parsed as { payload?: Record<string, unknown> }).payload
          if (payload?.type === 'plugin:tool_invoke') {
            void this.handleToolInvoke(payload as unknown as ToolInvokeRequest & { args: Record<string, unknown> })
          }
        }

        const pluginEvent: PluginEvent = {
          type: eventType,
          data: parsed,
        }
        for (const listener of this.eventListeners) {
          listener(pluginEvent)
        }
      } catch {
        // ignore malformed event payloads
      }
    }
  }

  private async handleToolInvoke(event: ToolInvokeRequest & { args: Record<string, unknown> }): Promise<void> {
    const toolName = event.toolName
    const handler = this.toolHandlers.get(toolName)
    if (!handler) {
      await this.send({
        type: 'tool.invoke.result',
        callId: event.callId,
        result: `No handler registered for plugin tool: ${toolName}`,
        isError: true,
      } as PluginToCore)
      return
    }

    try {
      const result = await handler(event.args, event)
      await this.send({
        type: 'tool.invoke.result',
        callId: event.callId,
        result,
        isError: false,
      } as PluginToCore)
    } catch (err) {
      await this.send({
        type: 'tool.invoke.result',
        callId: event.callId,
        result: String(err),
        isError: true,
      } as PluginToCore)
    }
  }

  /** Check if CassiCore is reachable */
  async available(): Promise<boolean> {
    try {
      const res = await this.fetch('/health', { method: 'GET' })
      return res.ok === true || (res as Record<string, unknown>).status === 'ok'
    } catch {
      return false
    }
  }

  /** Low-level HTTP fetch to the admin API */
  private async fetch(
    path: string,
    opts: { method: string; body?: unknown },
  ): Promise<SendResult & Record<string, unknown>> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`
    }

    const payload = opts.body ? JSON.stringify(opts.body) : undefined

    return new Promise((resolve, reject) => {
      const requestOptions: http.RequestOptions = this.socketPath
        ? {
            socketPath: this.socketPath,
            path,
            method: opts.method,
            headers: payload
              ? { ...headers, 'Content-Length': String(Buffer.byteLength(payload)) }
              : headers,
            timeout: 10_000,
          }
        : (() => {
            const url = new URL(path, this.baseUrl ?? 'http://127.0.0.1:7433')
            return {
              hostname: url.hostname,
              port: url.port || 7433,
              path: url.pathname + url.search,
              method: opts.method,
              headers: payload
                ? { ...headers, 'Content-Length': String(Buffer.byteLength(payload)) }
                : headers,
              timeout: 10_000,
            }
          })()

      const req = http.request(requestOptions, (res) => {
        const chunks: Buffer[] = []
        res.on('data', (chunk) => chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)))
        res.on('end', () => {
          try {
            const json = JSON.parse(Buffer.concat(chunks).toString('utf8')) as Record<string, unknown>
            resolve(json as SendResult & Record<string, unknown>)
          } catch (err) {
            reject(err)
          }
        })
      })

      req.on('error', reject)
      req.on('timeout', () => {
        req.destroy(new Error('Plugin SDK request timed out'))
      })

      if (payload) req.write(payload)
      req.end()
    })
  }
}
class SessionAPI {
  constructor(private client: CassiCoreClient) {}

  async create(parentSessionId?: string): Promise<{ sessionId: string }> {
    const res = await this.client.send({ type: 'session.create', parentSessionId } as PluginToCore)
    return res.data as { sessionId: string }
  }

  async destroy(sessionId: string): Promise<void> {
    await this.client.send({ type: 'session.destroy', sessionId } as PluginToCore)
  }

  async turnComplete(
    sessionId: string,
    userMessage: string,
    assistantResponse: string,
    model?: string,
    tokens?: TokenUsage,
  ): Promise<void> {
    await this.client.send({
      type: 'turn.complete',
      sessionId,
      userMessage,
      assistantResponse,
      model,
      tokens,
    } as PluginToCore)
  }

  async reasoning(sessionId: string, text: string, model?: string): Promise<void> {
    await this.client.send({
      type: 'reasoning',
      sessionId,
      text,
      model,
    } as PluginToCore)
  }

  async streamToken(sessionId: string, delta: string, kind: 'token' | 'thinking' = 'token'): Promise<void> {
    await this.client.send({
      type: 'token.stream',
      sessionId,
      delta,
      kind,
    } as PluginToCore)
  }
}

class ContextAPI {
  constructor(private client: CassiCoreClient) {}

  async get(
    sessionId: string,
    opts?: { contextLimit?: number; tokensUsed?: number; slim?: boolean },
  ): Promise<ContextResponse> {
    const res = await this.client.send({
      type: 'context.get',
      sessionId,
      ...opts,
    } as PluginToCore)
    return res.data as ContextResponse
  }

  async reportPressure(
    sessionId: string,
    pressure: number,
    contextLimit: number,
    activeTokens?: number,
  ): Promise<void> {
    await this.client.send({
      type: 'pressure.report',
      sessionId,
      pressure,
      contextLimit,
      activeTokens,
    } as PluginToCore)
  }

  async getDirective(sessionId: string): Promise<DirectiveResponse | null> {
    const res = await this.client.send({
      type: 'directive.get',
      sessionId,
    } as PluginToCore)
    return (res.data as DirectiveResponse) ?? null
  }

  async archive(sessionId: string, messages: Array<{ role: string; content: string }>): Promise<void> {
    await this.client.send({
      type: 'session.archive',
      sessionId,
      messages,
    } as PluginToCore)
  }

  async compact(
    sessionId: string,
    messages: Array<{ role: string; content: string }>,
  ): Promise<CompactResponse> {
    const res = await this.client.send({
      type: 'session.compact',
      sessionId,
      messages,
    } as PluginToCore)
    return res.data as CompactResponse
  }

  async index(
    sessionId: string,
    messages: Array<{ role: string; content: string }>,
  ): Promise<void> {
    await this.client.send({
      type: 'session.index',
      sessionId,
      messages,
    } as PluginToCore)
  }
}

class MemoryAPI {
  constructor(private client: CassiCoreClient) {}

  async kvGet(key: string): Promise<unknown> {
    const res = await this.client.send({ type: 'kv.get', key } as PluginToCore)
    return res.data
  }

  async kvSet(key: string, value: unknown, ttl?: number): Promise<void> {
    await this.client.send({ type: 'kv.set', key, value, ttl } as PluginToCore)
  }

  async search(query: string, limit?: number): Promise<unknown[]> {
    const res = await this.client.send({ type: 'memory.search', query, limit } as PluginToCore)
    return (res.data as unknown[]) ?? []
  }

  async store(content: string, tags?: string[]): Promise<string> {
    const res = await this.client.send({ type: 'memory.store', content, tags } as PluginToCore)
    return (res.data as { id: string }).id
  }
}

class ChunkAPI {
  constructor(private client: CassiCoreClient) {}

  async store(sessionId: string, chunks: StoredChunk[]): Promise<{ stored: number }> {
    const res = await this.client.send({
      type: 'chunk.store',
      sessionId,
      chunks,
    } as PluginToCore)
    return res.data as { stored: number }
  }

  async expand(sessionId: string, chunkIds: string[]): Promise<unknown[]> {
    const res = await this.client.send({
      type: 'chunk.expand',
      sessionId,
      chunkIds,
    } as PluginToCore)
    return (res.data as unknown[]) ?? []
  }
}

class IntelligenceAPI {
  constructor(private client: CassiCoreClient) {}

  async status(): Promise<unknown> {
    const res = await this.client.send({ type: 'intelligence.status' } as PluginToCore)
    return res.data
  }

  async enrich(query: string): Promise<unknown> {
    const res = await this.client.send({
      type: 'intelligence.enrich',
      query,
    } as PluginToCore)
    return res.data
  }

  async ingest(sessionId: string, events: Array<{ type: string; [key: string]: unknown }>): Promise<void> {
    await this.client.send({
      type: 'intelligence.ingest',
      sessionId,
      events: events.map(e => ({ ...e, timestamp: e.timestamp ?? Date.now() })),
    } as PluginToCore)
  }

  async postWorkingState(sessionId: string, state: Record<string, unknown>): Promise<void> {
    await this.client.send({
      type: 'working-state.post',
      sessionId,
      state,
    } as unknown as PluginToCore)
  }
}

class ToolAPI {
  constructor(private client: CassiCoreClient) {}

  async register(tools: ToolDefinition[]): Promise<void> {
    await this.client.send({
      type: 'tool.register',
      tools,
    } as PluginToCore)
  }
}
