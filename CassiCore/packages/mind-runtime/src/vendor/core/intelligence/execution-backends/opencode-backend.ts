/**
 * OpenCodeExecutionBackend — Delegates agent execution to OpenCode via HTTP.
 *
 * CassiCore orchestrates (goal trees, checkpoints, delegation decisions),
 * while OpenCode executes (LLM calls, tool access, file operations).
 *
 * Architecture:
 *   - One OpenCode session per CassiCore agent
 *   - Iteration prompts sent as successive messages in the session
 *   - OpenCode maintains full conversation history and handles context management
 *   - Response mapped back to CassiCore's TurnResult format
 *   - Token usage reported back for budget tracking
 *
 * Port discovery order:
 *   1. Explicit config: teams.opencode.url
 *   2. server.json file: ~/.opencode/server.json (written by OpenCode fork U9)
 *   3. Default: http://localhost:4096
 */

import { readFileSync, existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { CachedValue } from '@cassicore/utils'



import type {
  IExecutionBackend,
  AgentSessionOpts,
  OpenCodeBackendConfig,
} from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'
import type { InboundMessage, TurnResult } from '@cassicore/foundation'


interface OpenCodeSessionInfo {
  id: string
  slug: string
  title: string
  parentID?: string
  directory: string
  time: { created: number; updated: number }
}

interface OpenCodeMessagePart {
  type: string
  text?: string
  tool?: string
  state?: {
    status?: string
    input?: Record<string, unknown>
    output?: string
    time?: { start?: number; end?: number }
  }
}

interface OpenCodeAssistantInfo {
  role: 'assistant'
  id: string
  sessionID: string
  modelID: string
  providerID: string
  agent: string
  cost: number
  tokens: {
    total?: number
    input: number
    output: number
    reasoning: number
    cache: { read: number; write: number }
  }
  time: { created: number; completed?: number }
  finish?: string
  error?: { name: string; message?: string }
}

interface OpenCodeMessageResponse {
  info: OpenCodeAssistantInfo
  parts: OpenCodeMessagePart[]
}


export class OpenCodeExecutionBackend implements IExecutionBackend {
  readonly name = 'opencode'
  private logger: ILogger
  private config: Required<OpenCodeBackendConfig>

  /** Maps CassiCore agentId → OpenCode sessionId */
  private agentSessions = new Map<string, string>()

  /** Pending context updates per agent — applied on next execute() */
  private pendingContextUpdates = new Map<string, { systemPrompt?: string }>()

  /** Cached base URL with TTL (5 minutes) */
  private urlCache = new CachedValue<string>({ ttlMs: 300_000 })

  /** Explicitly configured URL (never expires) */
  private explicitUrl: string | null = null

  /** Per-session provider settings for model/provider forwarding */
  private sessionProviders = new Map<string, { model?: string; provider?: string }>()

  constructor(logger: ILogger, config: OpenCodeBackendConfig = {}) {
    this.logger = logger.child?.('exec-backend:opencode') ?? logger
    this.config = {
      url: config.url ?? '',
      serverJsonPath: config.serverJsonPath ?? resolveDefaultServerJsonPath(),
      defaultAgent: config.defaultAgent ?? 'build',
      defaultModel: config.defaultModel ?? (undefined as any),
      requestTimeoutMs: config.requestTimeoutMs ?? 300_000,
      forwardHierarchyEvents: config.forwardHierarchyEvents ?? true,
    }
    // Store explicit URL if provided (trimming trailing slashes)
    if (config.url) {
      this.explicitUrl = config.url!.replace(/\/$/, '')
    }
  }


  async execute(inbound: InboundMessage): Promise<TurnResult> {
    const ocSessionId = this.agentSessions.get(inbound.metadata?.agentId as string)
    if (!ocSessionId) {
      throw new Error(
        `OpenCodeExecutionBackend: no OpenCode session for agent "${inbound.metadata?.agentId}". ` +
        `Call initAgentSession() first.`
      )
    }

    const baseUrl = await this.getBaseUrl()
    const startMs = Date.now()

    const agentId = inbound.metadata?.agentId as string | undefined

    // Build the request body for OpenCode's POST /session/:id/message
    const body: Record<string, unknown> = {
      parts: [{ type: 'text', text: inbound.content }],
    }

    // Apply pending context update if available, otherwise use metadata systemPrompt
    if (agentId) {
      const pendingUpdate = this.pendingContextUpdates.get(agentId)
      if (pendingUpdate?.systemPrompt) {
        body.system = pendingUpdate.systemPrompt
        this.pendingContextUpdates.delete(agentId)
        this.logger.debug('OpenCodeBackend: applied pending context update', {
          agentId,
          iteration: inbound.metadata?.iteration,
        })
      }
    }
    if (!body.system && inbound.metadata?.iteration === 1 && inbound.metadata?.systemPrompt) {
      body.system = inbound.metadata.systemPrompt
    }

    // Forward model/provider from per-session settings or config default
    // Fallback chain: session-specific → config.defaultModel → OpenCode defaults
    const sessionProvider = agentId ? this.sessionProviders.get(agentId) : undefined
    const model = sessionProvider?.model
    const provider = sessionProvider?.provider
    if (model) {
      body.model = model
      if (provider) {
        body.provider = provider
      }
    } else if (this.config.defaultModel) {
      body.model = this.config.defaultModel.modelID ?? ''
      body.provider = this.config.defaultModel.providerID
    }

    this.logger.debug('OpenCodeBackend: sending iteration', {
      agentId: inbound.metadata?.agentId,
      sessionId: ocSessionId,
      iteration: inbound.metadata?.iteration,
      promptLength: inbound.content.length,
    })

    try {
      // POST /session/:id/message — blocks until complete
      const response = await this.fetchWithTimeout(
        `${baseUrl}/session/${ocSessionId}/message`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
      )

      if (!response.ok) {
        const errorText = await response.text().catch(() => 'unknown')
        throw new Error(
          `OpenCodeBackend: message failed (${response.status}): ${errorText}`
        )
      }

      const result = (await response.json()) as OpenCodeMessageResponse
      const durationMs = Date.now() - startMs

      return this.mapToTurnResult(result, durationMs)
    } catch (err) {
      // Invalidate cache on connection errors so next call re-discovers URL
      const errorMsg = String(err)
      if (
        errorMsg.includes('ECONNREFUSED') ||
        errorMsg.includes('fetch failed') ||
        errorMsg.includes('ETIMEDOUT') ||
        errorMsg.includes('ENOTFOUND') ||
        errorMsg.includes('socket')
      ) {
        this.urlCache.invalidate()
        this.logger.debug('OpenCodeBackend: invalidated URL cache on connection error', {
          error: errorMsg,
        })
      }
      throw err
    }
  }

  async initAgentSession(
    agentId: string,
    _sessionId: string,
    opts: AgentSessionOpts,
  ): Promise<void> {
    const baseUrl = await this.getBaseUrl()

    // Create a new OpenCode session
    const createBody: Record<string, unknown> = {}
    if (opts.initialTask) {
      createBody.title = opts.initialTask.slice(0, 100)
    }
    // Forward model/provider from AgentSessionOpts for per-session configuration
    if (opts.provider?.model) {
      createBody.model = opts.provider.model
    }
    if (opts.provider?.providerId) {
      createBody.provider = opts.provider.providerId
    }
    createBody.agent = opts.openCodeAgent ?? this.config.defaultAgent

    const response = await this.fetchWithTimeout(`${baseUrl}/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(createBody),
    })

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'unknown')
      throw new Error(
        `OpenCodeBackend: session creation failed (${response.status}): ${errorText}`
      )
    }

    const session = (await response.json()) as OpenCodeSessionInfo
    this.agentSessions.set(agentId, session.id)

    // Store per-session provider settings for message execution
    this.sessionProviders.set(agentId, {
      model: opts.provider?.model,
      provider: opts.provider?.providerId,
    })

    this.logger.info('OpenCodeBackend: created session', {
      agentId,
      ocSessionId: session.id,
      slug: session.slug,
      title: session.title,
    })
  }

  async destroyAgentSession(agentId: string): Promise<void> {
    const ocSessionId = this.agentSessions.get(agentId)
    if (!ocSessionId) return

    // Try to abort any in-progress work
    try {
      const baseUrl = await this.getBaseUrl()
      await this.fetchWithTimeout(`${baseUrl}/session/${ocSessionId}/abort`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })
      this.logger.debug('OpenCodeBackend: aborted session', { agentId, ocSessionId })
    } catch {
      // Abort is best-effort — session may have already finished
    }

    this.agentSessions.delete(agentId)
    this.pendingContextUpdates.delete(agentId)
    this.sessionProviders.delete(agentId)
  }

  async isAvailable(): Promise<boolean> {
    try {
      const baseUrl = await this.getBaseUrl()
      const response = await this.fetchWithTimeout(`${baseUrl}/agent`, {
        method: 'GET',
      }, 5_000)
      return response.ok
    } catch {
      // Invalidate cache on failure so next check re-discovers URL
      this.urlCache.invalidate()
      return false
    }
  }

  /**
   * Update the execution context for an active agent session.
   * Stores the update to be applied on the next execute() call via the system field.
   */
  async updateContext(
    agentId: string,
    context: { systemPrompt?: string; recentMemories?: string[]; files?: string[] },
  ): Promise<void> {
    const ocSessionId = this.agentSessions.get(agentId)
    if (!ocSessionId) {
      this.logger.debug('OpenCodeBackend: updateContext called for unknown agent', { agentId })
      return
    }

    // Build a context-rich system prompt from the assembled context
    const contextParts: string[] = []

    if (context.systemPrompt) {
      contextParts.push(context.systemPrompt)
    }

    if (context.recentMemories?.length) {
      contextParts.push(`\n## Recent Context\n${context.recentMemories.join('\n')}`)
    }

    if (context.files?.length) {
      contextParts.push(`\n## Relevant Files\n${context.files.join('\n')}`)
    }

    const fullContext = contextParts.join('\n\n')

    if (!fullContext.trim()) {
      this.logger.debug('OpenCodeBackend: updateContext called with empty context', { agentId })
      return
    }

    // Store for application on next execute()
    this.pendingContextUpdates.set(agentId, { systemPrompt: fullContext })

    this.logger.debug('OpenCodeBackend: context update queued', {
      agentId,
      ocSessionId,
      contextLength: fullContext.length,
    })
  }


  private async getBaseUrl(): Promise<string> {
    // 1. Explicit config (never expires)
    if (this.explicitUrl) {
      return this.explicitUrl
    }

    // 2. Check cache (5 min TTL)
    const cached = this.urlCache.get()
    if (cached) return cached

    // 3. server.json discovery (U9)
    try {
      if (existsSync(this.config.serverJsonPath)) {
        const raw = readFileSync(this.config.serverJsonPath, 'utf-8')
        const data = JSON.parse(raw) as { url?: string; port?: number }
        if (data.url) {
          const url = data.url.replace(/\/$/, '')
          this.urlCache.set(url)
          this.logger.debug('OpenCodeBackend: discovered URL from server.json', {
            url,
            path: this.config.serverJsonPath,
          })
          return url
        }
        if (data.port) {
          const url = `http://127.0.0.1:${data.port}`
          this.urlCache.set(url)
          this.logger.debug('OpenCodeBackend: discovered port from server.json', {
            url,
            port: data.port,
          })
          return url
        }
      }
    } catch (err) {
      this.logger.debug('OpenCodeBackend: server.json read failed', { error: String(err) })
    }

    // 4. Default
    const url = 'http://127.0.0.1:4096'
    this.urlCache.set(url)
    this.logger.debug('OpenCodeBackend: using default URL', { url })
    return url
  }

  /** Reset cached URL (e.g., after OpenCode restart) */
  resetUrlCache(): void {
    this.urlCache.invalidate()
  }


  private mapToTurnResult(
    result: OpenCodeMessageResponse,
    durationMs: number,
  ): TurnResult {
    const info = result.info
    const parts = result.parts

    // Extract full response text from all text parts
    const textParts = parts.filter(p => p.type === 'text' && p.text)
    const response = textParts.map(p => p.text!).join('\n')

    // Calculate total tokens
    const tokens = info.tokens
    const tokensUsed = tokens.total ??
      (tokens.input + tokens.output + tokens.reasoning)

    // Extract tool calls
    const toolParts = parts.filter(p => p.type === 'tool' && p.tool)
    const toolCalls = toolParts.map(p => {
      const time = p.state?.time
      const toolDurationMs = (time?.end && time?.start) ? (time.end - time.start) : 0
      return { name: p.tool!, durationMs: toolDurationMs }
    })

    // Map tool outputs
    const tool_outputs = toolParts
      .filter(p => p.state?.status === 'completed' || p.state?.status === 'error')
      .map((p, i) => ({
        tool_name: p.tool!,
        tool_call_id: `oc-tool-${i}`,
        output: typeof p.state?.output === 'string'
          ? p.state.output
          : JSON.stringify(p.state?.output ?? ''),
        is_error: p.state?.status === 'error',
        timestamp: new Date(p.state?.time?.end ?? Date.now()),
      }))

    // Check for errors
    if (info.error) {
      this.logger.warn('OpenCodeBackend: assistant returned error', {
        error: info.error,
        model: info.modelID,
      })
    }

    return {
      response,
      tokensUsed,
      model: info.modelID || 'unknown',
      durationMs,
      toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
      tool_outputs: tool_outputs.length > 0 ? tool_outputs : undefined,
    }
  }


  private async fetchWithTimeout(
    url: string,
    init: RequestInit,
    timeoutMs?: number,
  ): Promise<Response> {
    const timeout = timeoutMs ?? this.config.requestTimeoutMs
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)

    try {
      return await fetch(url, {
        ...init,
        signal: controller.signal,
      })
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') {
        throw new Error(`OpenCodeBackend: request timed out after ${timeout}ms: ${url}`)
      }
      throw err
    } finally {
      clearTimeout(timer)
    }
  }


  /** Get info about current agent sessions */
  getSessionMap(): Record<string, string> {
    const map: Record<string, string> = {}
    for (const [agentId, sessionId] of this.agentSessions) {
      map[agentId] = sessionId
    }
    return map
  }

  /** Get the resolved URL (for diagnostics) */
  getResolvedUrl(): string | null {
    return this.explicitUrl ?? this.urlCache.value
  }
}


/**
 * Resolve the default server.json path following XDG conventions.
 * OpenCode writes to $XDG_STATE_HOME/opencode/server.json (typically ~/.local/state/opencode/).
 * Falls back to ~/.opencode/server.json for compatibility.
 */
function resolveDefaultServerJsonPath(): string {
  const xdgState = process.env.XDG_STATE_HOME ?? join(homedir(), '.local', 'state')
  const xdgPath = join(xdgState, 'opencode', 'server.json')
  // Prefer XDG path if the directory exists, otherwise fall back to legacy location
  if (existsSync(join(xdgState, 'opencode'))) {
    return xdgPath
  }
  return join(homedir(), '.opencode', 'server.json')
}
