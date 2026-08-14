/**
 * Plugin API — Server-side request handler for the plugin protocol.
 *
 * Maps incoming PluginToCore messages to existing daemon services.
 * This is the single integration point — plugins don't call admin API
 * endpoints directly; they send typed messages and this handler routes
 * them to the appropriate service.
 *
 * Each handler method checks that the plugin has the required capability
 * before processing. Unauthorized requests get a clear error.
 */

import type { RuntimeEvent } from '@cassicore/foundation'
import type { Message } from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'
import type { PluginRegistry } from './plugin-registry.js'
import type { PluginRegistration, PluginToCore, PluginCapability } from '@cassicore/foundation'

/**
 * Dependencies injected from the daemon.
 * These are the existing services that the plugin API delegates to.
 * Typed loosely here to avoid circular imports with the daemon.
 */
export interface PluginAPIDeps {
  logger: ILogger
  registry: PluginRegistry

  /** Session manager — create, destroy, get sessions */
  sessions: {
    create(stableId: string, opts?: { channelId?: string; meta?: Record<string, unknown> }): { id: string }
    get(id: string): { id: string; status: string } | null
    destroy(id: string): void
    append?(id: string, message: Message): void
  }

  /** Context bridge — the same services that the OpenCode plugin uses */
  context: {
    fetchContext(): Promise<unknown>
    inject(sessionId: string): Promise<string[]>
    cognitiveStatus(): Promise<unknown>
    storeChunks(sessionId: string, chunks: unknown[]): Promise<{ stored: number }>
    expandChunks(sessionId: string, ids: string[]): Promise<unknown[]>
    archive(sessionId: string, messages: unknown[]): Promise<void>
    compact(sessionId: string, messages: unknown[]): Promise<unknown>
    index(sessionId: string, messages: unknown[]): void
    resolveRef(ref: string): Promise<unknown>
    searchIndex(query: string, sessionId?: string): Promise<unknown>
    ingestEvents(sessionId: string, events: unknown[]): Promise<void>
    forwardTurnStart(sessionId: string, trigger: string): void
    forwardTurnEnd(sessionId: string): void
    forwardToken(sessionId: string, delta: string, kind: string): void
    forwardToolCall(sessionId: string, toolName: string, meta?: Record<string, unknown>): void
    forwardToolResult(sessionId: string, callId: string, isError: boolean): void
  }

  /** Memory — search, store, KV operations */
  memory: {
    search(query: string, limit?: number): Promise<unknown[]>
    store(content: string, tags?: string[]): Promise<string>
    kvGet(key: string): Promise<unknown>
    kvSet(key: string, value: unknown, ttl?: number): Promise<void>
  }

  /** Intelligence layer — status, enrichment */
  intelligence: {
    status(): Promise<unknown>
    enrich(query: string): Promise<unknown>
  }

  /** Event bus — for forwarding daemon events to plugins */
  eventBus: {
    on(type: string, handler: (event: RuntimeEvent) => void): () => void
    emit(event: RuntimeEvent): Promise<void>
  }

  toolRegistry?: {
    register?(tool: { name: string; description: string; parameters: Record<string, unknown>; execute: (args: Record<string, unknown>, context?: unknown) => Promise<unknown> }): void
  }
}

export interface PluginAPIResult {
  ok: boolean
  data?: unknown
  error?: string
}

export class PluginAPI {
  private deps: PluginAPIDeps
  private logger: ILogger
  private pluginEventSubscribers = new Map<string, { filters: string[] }>()
  private pendingToolInvocations = new Map<string, {
    pluginId: string
    resolve: (result: string) => void
    reject: (err: Error) => void
    timer: ReturnType<typeof setTimeout>
  }>()

  constructor(deps: PluginAPIDeps) {
    this.deps = deps
    this.logger = deps.logger.child('plugin-api')
  }

  /**
   * Handle an incoming plugin protocol message.
   * Authenticates the plugin, checks capabilities, and routes to the handler.
   */
  async handle(
    registration: PluginRegistration,
    message: PluginToCore,
  ): Promise<PluginAPIResult> {
    const pluginId = registration.manifest.id

    try {
      switch (message.type) {
        // Layer 1: Session
        case 'session.create':
          return this.requireCapability(registration, 'session', () =>
            this.handleSessionCreate(pluginId, message))
        case 'session.destroy':
          return this.requireCapability(registration, 'session', () =>
            this.handleSessionDestroy(message))

        // Layer 1: Events (forwarding from client → CassiCore)
        case 'turn.complete':
          return this.requireCapability(registration, 'session', () =>
            this.handleTurnComplete(pluginId, message))
        case 'reasoning':
          return this.requireCapability(registration, 'session', () =>
            this.handleReasoning(message))
        case 'token.stream':
          return this.requireCapability(registration, 'session', () =>
            this.handleTokenStream(message))
        case 'tool.call':
        case 'tool.result':
          return this.requireCapability(registration, 'session', () =>
            this.handleToolEvent(message))
        case 'events.subscribe':
          return this.requireCapability(registration, 'events', () =>
            this.handleEventsSubscribe(registration.manifest.id, message))

        // Layer 2: Context
        case 'context.get':
          return this.requireCapability(registration, 'context', () =>
            this.handleContextGet(message))
        case 'pressure.report':
          return this.requireCapability(registration, 'pressure', () =>
            this.handlePressureReport(message))
        case 'directive.get':
          return this.requireCapability(registration, 'pressure', () =>
            this.handleDirectiveGet(message))

        // Layer 2: Memory / KV
        case 'kv.get':
          return this.requireCapability(registration, 'memory', () =>
            this.handleKVGet(message))
        case 'kv.set':
          return this.requireCapability(registration, 'memory', () =>
            this.handleKVSet(message))
        case 'memory.search':
          return this.requireCapability(registration, 'memory', () =>
            this.handleMemorySearch(message))
        case 'memory.store':
          return this.requireCapability(registration, 'memory', () =>
            this.handleMemoryStore(message))

        // Layer 2: Chunks
        case 'chunk.store':
          return this.requireCapability(registration, 'chunks', () =>
            this.handleChunkStore(message))
        case 'chunk.expand':
          return this.requireCapability(registration, 'chunks', () =>
            this.handleChunkExpand(message))

        // Layer 2: Archiving / Compaction / Indexing
        case 'session.archive':
          return this.requireCapability(registration, 'context', () =>
            this.handleArchive(message))
        case 'session.compact':
          return this.requireCapability(registration, 'context', () =>
            this.handleCompact(message))
        case 'session.index':
          return this.requireCapability(registration, 'context', () =>
            this.handleIndex(message))
        case 'session.index.search':
          return this.requireCapability(registration, 'context', () =>
            this.handleIndexSearch(message))
        case 'session.resolve_ref':
          return this.requireCapability(registration, 'context', () =>
            this.handleResolveRef(message))

        // Layer 3: Intelligence
        case 'intelligence.status':
          return this.requireCapability(registration, 'intelligence', () =>
            this.handleIntelligenceStatus())
        case 'intelligence.enrich':
          return this.requireCapability(registration, 'intelligence', () =>
            this.handleEnrich(message))
        case 'intelligence.ingest':
          return this.requireCapability(registration, 'intelligence', () =>
            this.handleIngest(message))
        case 'working-state.post':
          return this.requireCapability(registration, 'intelligence', () =>
            this.handleWorkingStatePost(message))

        // Layer 3: Tool registration
        case 'tool.register':
          return this.requireCapability(registration, 'tools', () =>
            this.handleToolRegister(pluginId, message))
        case 'tool.invoke.result':
          return this.requireCapability(registration, 'tools', () =>
            this.handleToolInvokeResult(message))

        default:
          return { ok: false, error: `Unknown message type: ${(message as { type: string }).type}` }
      }
    } catch (err) {
      this.logger.error('Plugin API handler error', {
        pluginId,
        type: message.type,
        error: String(err),
      })
      return { ok: false, error: String(err) }
    }
  }

  // Capability gate

  private async requireCapability(
    registration: PluginRegistration,
    capability: PluginCapability,
    handler: () => Promise<PluginAPIResult>,
  ): Promise<PluginAPIResult> {
    if (!registration.grantedCapabilities.includes(capability)) {
      return {
        ok: false,
        error: `Plugin "${registration.manifest.id}" does not have the "${capability}" capability`,
      }
    }
    return handler()
  }

  // Layer 1: Session handlers

  private async handleSessionCreate(
    pluginId: string,
    msg: Extract<PluginToCore, { type: 'session.create' }>,
  ): Promise<PluginAPIResult> {
    const prefix = this.deps.registry.get(pluginId)?.manifest.sessionPrefix ?? pluginId
    const sessionId = `${prefix}:${Math.random().toString(36).slice(2, 10)}`
    const result = this.deps.sessions.create(sessionId, {
      channelId: pluginId,
      meta: msg.meta,
    })
    return { ok: true, data: { sessionId: result.id, created: true } }
  }

  private async handleSessionDestroy(
    msg: Extract<PluginToCore, { type: 'session.destroy' }>,
  ): Promise<PluginAPIResult> {
    await this.deps.sessions.destroy(msg.sessionId)
    return { ok: true }
  }

  private async handleTurnComplete(
    pluginId: string,
    msg: Extract<PluginToCore, { type: 'turn.complete' }>,
  ): Promise<PluginAPIResult> {
    if (!this.deps.sessions.get(msg.sessionId)) {
      this.deps.sessions.create(msg.sessionId, { channelId: pluginId })
    }

    this.deps.sessions.append?.(msg.sessionId, { role: 'user', content: msg.userMessage })
    this.deps.sessions.append?.(msg.sessionId, { role: 'assistant', content: msg.assistantResponse })

    await this.deps.context.ingestEvents(msg.sessionId, [{
      type: 'turn:start',
      sessionId: msg.sessionId,
      message: msg.userMessage,
      timestamp: new Date(msg.timestamp),
    }, {
      type: 'turn:end',
      sessionId: msg.sessionId,
      response: msg.assistantResponse,
      durationMs: 0,
      model: msg.model,
      tokens: msg.tokens,
      timestamp: new Date(msg.timestamp),
    }])
    return { ok: true }
  }

  private async handleReasoning(
    msg: Extract<PluginToCore, { type: 'reasoning' }>,
  ): Promise<PluginAPIResult> {
    await this.deps.eventBus.emit({
      type: 'worker:message',
      pluginId: `session:${msg.sessionId}`,
      sessionId: msg.sessionId,
      payload: {
        type: 'turn:thinking',
        sessionId: msg.sessionId,
        token: msg.text,
        model: msg.model,
      },
    } as RuntimeEvent)
    return { ok: true }
  }

  private async handleTokenStream(
    msg: Extract<PluginToCore, { type: 'token.stream' }>,
  ): Promise<PluginAPIResult> {
    this.deps.context.forwardToken(msg.sessionId, msg.delta, msg.kind)
    return { ok: true }
  }

  private async handleToolEvent(
    msg: Extract<PluginToCore, { type: 'tool.call' | 'tool.result' }>,
  ): Promise<PluginAPIResult> {
    if (msg.type === 'tool.call') {
      this.deps.context.forwardToolCall(msg.sessionId, msg.toolName, msg.data)
    } else {
      const isError = (msg.data?.isError as boolean) ?? false
      const callId = (msg.data?.callId as string) ?? ''
      this.deps.context.forwardToolResult(msg.sessionId, callId, isError)
    }
    return { ok: true }
  }

  // Layer 2: Context handlers

  private async handleContextGet(
    msg: Extract<PluginToCore, { type: 'context.get' }>,
  ): Promise<PluginAPIResult> {
    const ctx = await this.deps.context.fetchContext()
    const cognitive = await this.deps.context.inject(msg.sessionId)
    const status = await this.deps.context.cognitiveStatus()

    return {
      ok: true,
      data: {
        context: ctx,
        cognitive,
        cognitiveStatus: status,
      },
    }
  }

  private async handlePressureReport(
    msg: Extract<PluginToCore, { type: 'pressure.report' }>,
  ): Promise<PluginAPIResult> {
    await this.deps.context.ingestEvents(msg.sessionId, [{
      type: 'opencode:context:pressure',
      sessionId: msg.sessionId,
      pressure: msg.pressure,
      contextLimit: msg.contextLimit,
      activeTokens: msg.activeTokens,
      timestamp: msg.timestamp,
    }])
    return { ok: true }
  }

  private async handleDirectiveGet(
    msg: Extract<PluginToCore, { type: 'directive.get' }>,
  ): Promise<PluginAPIResult> {
    const key = `context-directives:${msg.sessionId}`
    const directive = await this.deps.memory.kvGet(key)
    if (directive) {
      await this.deps.memory.kvSet(key, null)
    }
    return { ok: true, data: directive }
  }

  // Layer 2: Memory / KV handlers

  private async handleKVGet(
    msg: Extract<PluginToCore, { type: 'kv.get' }>,
  ): Promise<PluginAPIResult> {
    const value = await this.deps.memory.kvGet(msg.key)
    return { ok: true, data: value }
  }

  private async handleKVSet(
    msg: Extract<PluginToCore, { type: 'kv.set' }>,
  ): Promise<PluginAPIResult> {
    await this.deps.memory.kvSet(msg.key, msg.value, msg.ttl)
    return { ok: true }
  }

  private async handleMemorySearch(
    msg: Extract<PluginToCore, { type: 'memory.search' }>,
  ): Promise<PluginAPIResult> {
    const results = await this.deps.memory.search(msg.query, msg.limit)
    return { ok: true, data: results }
  }

  private async handleMemoryStore(
    msg: Extract<PluginToCore, { type: 'memory.store' }>,
  ): Promise<PluginAPIResult> {
    const id = await this.deps.memory.store(msg.content, msg.tags)
    return { ok: true, data: { id } }
  }

  // Layer 2: Chunk handlers

  private async handleChunkStore(
    msg: Extract<PluginToCore, { type: 'chunk.store' }>,
  ): Promise<PluginAPIResult> {
    const result = await this.deps.context.storeChunks(msg.sessionId, msg.chunks)
    return { ok: true, data: result }
  }

  private async handleChunkExpand(
    msg: Extract<PluginToCore, { type: 'chunk.expand' }>,
  ): Promise<PluginAPIResult> {
    const chunks = await this.deps.context.expandChunks(msg.sessionId, msg.chunkIds)
    return { ok: true, data: chunks }
  }

  // Layer 2: Archive / Compact / Index handlers

  private async handleArchive(
    msg: Extract<PluginToCore, { type: 'session.archive' }>,
  ): Promise<PluginAPIResult> {
    await this.deps.context.archive(msg.sessionId, msg.messages)
    return { ok: true }
  }

  private async handleCompact(
    msg: Extract<PluginToCore, { type: 'session.compact' }>,
  ): Promise<PluginAPIResult> {
    const result = await this.deps.context.compact(msg.sessionId, msg.messages)
    return { ok: true, data: result }
  }

  private async handleIndex(
    msg: Extract<PluginToCore, { type: 'session.index' }>,
  ): Promise<PluginAPIResult> {
    this.deps.context.index(msg.sessionId, msg.messages)
    return { ok: true }
  }

  private async handleIndexSearch(
    msg: Extract<PluginToCore, { type: 'session.index.search' }>,
  ): Promise<PluginAPIResult> {
    const result = await this.deps.context.searchIndex(msg.query)
    return { ok: true, data: result }
  }

  private async handleResolveRef(
    msg: Extract<PluginToCore, { type: 'session.resolve_ref' }>,
  ): Promise<PluginAPIResult> {
    const result = await this.deps.context.resolveRef(msg.ref)
    return { ok: true, data: result }
  }

  // Layer 3: Intelligence handlers

  private async handleIntelligenceStatus(): Promise<PluginAPIResult> {
    const status = await this.deps.intelligence.status()
    return { ok: true, data: status }
  }

  private async handleEnrich(
    msg: Extract<PluginToCore, { type: 'intelligence.enrich' }>,
  ): Promise<PluginAPIResult> {
    const result = await this.deps.intelligence.enrich(msg.query)
    return { ok: true, data: result }
  }

  private async handleIngest(
    msg: Extract<PluginToCore, { type: 'intelligence.ingest' }>,
  ): Promise<PluginAPIResult> {
    await this.deps.context.ingestEvents(msg.sessionId, msg.events)
    return { ok: true }
  }

  private async handleWorkingStatePost(
    msg: Extract<PluginToCore, { type: 'working-state.post' }>,
  ): Promise<PluginAPIResult> {
    await this.deps.memory.kvSet(`working-state:${msg.sessionId}`, {
      ...msg.state,
      timestamp: msg.timestamp,
    })
    return { ok: true }
  }

  // Layer 3: Tool handlers

  private async handleToolRegister(
    pluginId: string,
    msg: Extract<PluginToCore, { type: 'tool.register' }>,
  ): Promise<PluginAPIResult> {
    for (const tool of msg.tools) {
      this.deps.toolRegistry?.register?.({
        name: `${pluginId}.${tool.name}`,
        description: tool.description,
        parameters: tool.parameters,
        execute: async (args: Record<string, unknown>) => {
          const callId = `plugin-tool:${pluginId}:${tool.name}:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`

          return await new Promise<string>((resolve, reject) => {
            const timer = setTimeout(() => {
              this.pendingToolInvocations.delete(callId)
              reject(new Error(`Plugin tool timed out: ${tool.name}`))
            }, 30_000)

            this.pendingToolInvocations.set(callId, {
              pluginId,
              resolve,
              reject,
              timer,
            })

            void this.deps.eventBus.emit({
              type: 'worker:message',
              pluginId,
              payload: {
                type: 'plugin:tool_invoke',
                toolName: tool.name,
                callId,
                args,
              },
            } as RuntimeEvent).catch((err) => {
              const pending = this.pendingToolInvocations.get(callId)
              if (!pending) return
              clearTimeout(pending.timer)
              this.pendingToolInvocations.delete(callId)
              reject(new Error(String(err)))
            })
          })
        },
      })
    }

    this.logger.info('Plugin tools registered', {
      pluginId: msg.pluginId,
      tools: msg.tools.map(t => t.name),
    })
    return { ok: true, data: { registered: msg.tools.length } }
  }

  private async handleToolInvokeResult(
    msg: Extract<PluginToCore, { type: 'tool.invoke.result' }>,
  ): Promise<PluginAPIResult> {
    const pending = this.pendingToolInvocations.get(msg.callId)
    if (pending && pending.pluginId === msg.pluginId) {
      clearTimeout(pending.timer)
      this.pendingToolInvocations.delete(msg.callId)
      if (msg.isError) {
        pending.reject(new Error(typeof msg.result === 'string' ? msg.result : JSON.stringify(msg.result)))
      } else {
        pending.resolve(typeof msg.result === 'string' ? msg.result : JSON.stringify(msg.result))
      }
      return { ok: true }
    }

    await this.deps.eventBus.emit({
      type: 'worker:message',
      pluginId: msg.pluginId,
      payload: {
        type: 'plugin:tool_result',
        callId: msg.callId,
        result: msg.result,
        isError: msg.isError,
      },
    } as RuntimeEvent)
    return { ok: true }
  }

  private async handleEventsSubscribe(
    pluginId: string,
    msg: Extract<PluginToCore, { type: 'events.subscribe' }>,
  ): Promise<PluginAPIResult> {
    this.pluginEventSubscribers.set(pluginId, {
      filters: msg.filter && msg.filter.length > 0 ? msg.filter : ['*'],
    })
    return { ok: true, data: { subscribed: true, filters: this.pluginEventSubscribers.get(pluginId)?.filters ?? ['*'] } }
  }

  getEventFilters(pluginId: string): string[] {
    return this.pluginEventSubscribers.get(pluginId)?.filters ?? ['*']
  }
}
