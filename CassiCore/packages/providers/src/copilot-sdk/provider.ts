/**
 * CopilotSDK Provider — IProvider wrapper that delegates entire turns
 * (including tool loops) to the Copilot SDK.
 *
 * When used with the SDK middleware, `executeSdkTurn()` handles the full
 * agentic loop as a single premium request. The `complete()` method is
 * a thin fallback for non-turn usage.
 */
import { approveAll } from '@github/copilot-sdk'
import type { CopilotSession, SessionEvent, Tool as SdkTool } from '@github/copilot-sdk'

import { BaseProvider } from '../base.js'
import { CopilotSdkManager } from './client-manager.js'
import { mapSdkEvent, createTurnState } from './event-mapper.js'

import type { Message, CompletionOpts, CompletionChunk, TurnResult, ImageAttachment } from '../../../types/runtime.js'
import type { ILogger, IEventBus } from '../../../types/interfaces.js'

/** Default sendAndWait timeout: 10 minutes (tool loops can be long). */
const SDK_TURN_TIMEOUT_MS = 600_000

export interface CopilotSdkProviderOptions {
  /** CopilotSdkManager instance (manages CLI lifecycle) */
  manager: CopilotSdkManager
  /** Pre-bridged SDK tools (from tool-bridge.ts) */
  tools: SdkTool[]
  /** Event bus for CassiCore events */
  bus: IEventBus
  /** Logger */
  logger: ILogger
  /** Default model */
  defaultModel?: string
  /** Working directory for sessions */
  workingDirectory?: string
}

export class CopilotSdkProvider extends BaseProvider {
  readonly id = 'copilot-sdk'
  models: string[] = []

  private manager: CopilotSdkManager
  private sdkTools: SdkTool[]
  private bus: IEventBus
  private logger: ILogger
  private defaultModel: string
  private workingDirectory: string

  /** Map CassiCore sessionId → SDK CopilotSession */
  private sessions = new Map<string, CopilotSession>()

  constructor(options: CopilotSdkProviderOptions) {
    super()
    this.manager = options.manager
    this.sdkTools = options.tools
    this.bus = options.bus
    this.logger = options.logger.child('copilot-sdk-provider')
    this.defaultModel = options.defaultModel ?? 'gpt-4o'
    this.workingDirectory = options.workingDirectory ?? process.cwd()
  }

  /**
   * Initialize models list from the SDK.
   * Called after the manager is started.
   */
  async initModels(): Promise<void> {
    try {
      const models = await this.manager.listModels()
      this.models = models.map(m => m.id)
      this.logger.info(`SDK provider models: ${this.models.join(', ')}`)
    } catch (err) {
      this.logger.warn(`Failed to list SDK models, using defaults: ${String(err)}`)
      this.models = ['gpt-4o', 'gpt-4.1', 'gpt-5-mini', 'claude-sonnet-4.5', 'claude-sonnet-4.6', 'claude-opus-4.6']
    }
  }

  // SDK Turn Execution (used by SDK middleware)

  /**
   * Execute a full turn via the SDK, including all tool loop iterations.
   * The entire turn counts as a single premium request.
   *
   * @param sessionId - CassiCore session ID
   * @param prompt - User message text
   * @param systemMessage - Assembled system prompt from intelligence modules
   * @param model - Model to use
   * @param onStream - Callback for streaming text chunks
   * @returns TurnResult with the final response
   */
  async executeSdkTurn(
    sessionId: string,
    prompt: string,
    systemMessage: string,
    model?: string,
    onStream?: (text: string) => void,
  ): Promise<TurnResult> {
    const session = await this.getOrCreateSession(sessionId, systemMessage, model)
    const state = createTurnState(sessionId)
    state.model = model || this.defaultModel

    // Subscribe to all events during this turn
    const unsubscribe = session.on((event: SessionEvent) => {
      mapSdkEvent(event, state, this.bus, onStream)
    })

    try {
      // Send prompt and wait for the full agentic loop to complete.
      // The SDK handles: prompt → LLM → tool calls → execute → re-prompt → ... → idle
      // All of this counts as a single premium request.
      const response = await session.sendAndWait(
        { prompt },
        SDK_TURN_TIMEOUT_MS,
      )

      // If response has content that wasn't streamed, use it
      if (response?.data.content && !state.text) {
        state.text = response.data.content
      }

      const durationMs = Date.now() - state.startedAt

      return {
        response: state.text,
        tokensUsed: state.tokensUsed,
        model: state.model,
        durationMs,
        toolCalls: state.toolCalls.length > 0 ? state.toolCalls : undefined,
        tool_outputs: state.toolOutputs.length > 0 ? state.toolOutputs : undefined,
      }
    } catch (err) {
      const durationMs = Date.now() - state.startedAt
      const errorMsg = err instanceof Error ? err.message : String(err)

      this.logger.error(`SDK turn failed for session ${sessionId}: ${errorMsg}`)

      // Return error as response text so the pipeline can handle it
      return {
        response: `Error: ${errorMsg}`,
        tokensUsed: state.tokensUsed,
        model: state.model,
        durationMs,
      }
    } finally {
      unsubscribe()
    }
  }

  // Session Management

  /**
   * Get or create an SDK session for a CassiCore session.
   */
  private async getOrCreateSession(
    sessionId: string,
    systemMessage: string,
    model?: string,
  ): Promise<CopilotSession> {
    const existing = this.sessions.get(sessionId)
    if (existing) {
      // Update model if changed
      if (model) {
        try {
          await existing.setModel(model)
        } catch { /* best effort — some models may not be switchable */ }
      }
      return existing
    }

    // Create new SDK session
    const client = this.manager.getClient()
    const session = await client.createSession({
      sessionId: `cassi_${sessionId}`,
      clientName: 'CassiCore',
      model: model || this.defaultModel,
      tools: this.sdkTools,
      systemMessage: {
        mode: 'replace',
        content: systemMessage,
      },
      onPermissionRequest: approveAll,
      workingDirectory: this.workingDirectory,
      streaming: true,
      infiniteSessions: {
        enabled: true,
        backgroundCompactionThreshold: 0.80,
        bufferExhaustionThreshold: 0.95,
      },
      // Disable built-in tools — CassiCore provides all tools
      availableTools: this.sdkTools.map(t => t.name),
    })

    this.sessions.set(sessionId, session)
    this.logger.info(`Created SDK session for CassiCore session ${sessionId.slice(-8)}`)
    return session
  }

  /**
   * Create a new SDK session with a custom tool list.
   * Used by complete() which merges CassiCore tools + caller meta-tools.
   */
  private async createSessionWithTools(
    sessionId: string,
    systemMessage: string,
    model: string,
    tools: SdkTool[],
  ): Promise<CopilotSession> {
    const client = this.manager.getClient()
    const session = await client.createSession({
      sessionId: `cassi_${sessionId}`,
      clientName: 'CassiCore',
      model,
      tools,
      systemMessage: {
        mode: 'replace',
        content: systemMessage,
      },
      onPermissionRequest: approveAll,
      workingDirectory: this.workingDirectory,
      streaming: true,
      infiniteSessions: {
        enabled: true,
        backgroundCompactionThreshold: 0.80,
        bufferExhaustionThreshold: 0.95,
      },
      availableTools: tools.map(t => t.name),
    })

    this.sessions.set(sessionId, session)
    return session
  }

  /**
   * Destroy an SDK session (called when CassiCore session ends).
   */
  async destroySession(sessionId: string): Promise<void> {
    const session = this.sessions.get(sessionId)
    if (!session) return

    try {
      await session.disconnect()
    } catch (err) {
      this.logger.warn(`Error disconnecting SDK session ${sessionId}: ${String(err)}`)
    }
    this.sessions.delete(sessionId)
  }

  /**
   * Destroy all SDK sessions (called on daemon shutdown).
   */
  async destroyAllSessions(): Promise<void> {
    const ids = Array.from(this.sessions.keys())
    await Promise.allSettled(ids.map(id => this.destroySession(id)))
    this.logger.info(`Destroyed ${ids.length} SDK session(s)`)
  }

  // IProvider interface (fallback — not the primary usage path)

  /**
   * Streaming completion — IProvider interface for Lumen/Dyad agent sessions.
   *
   * Architecture:
   *   - CassiCore tools (read, write, bash, etc.) are handled by the SDK's
   *     agentic loop via tool-bridge.ts. The SDK executes them and re-prompts.
   *   - Caller meta-tools (signal_conclusion, share_finding, etc.) are registered
   *     with relay handlers that push tool_use chunks into the stream. The SDK
   *     gets an acknowledgment; the caller handles the actual tool logic.
   *   - Text is streamed via assistant.message_delta events.
   *   - sendAndWait() handles completion detection (session.idle).
   */
  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    _attachments?: ImageAttachment[],
    _signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    const model = opts.model || this.defaultModel
    const sessionId = `sdk_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const log = this.logger.child('sdk-complete')

    // Build system prompt and user prompt
    const systemPrompt = opts.systemPrompt
      || messages.find(m => m.role === 'system')?.content as string
      || ''
    const prompt = this.formatMessagesAsPrompt(messages)

    const chunks: CompletionChunk[] = []
    let done = false
    let error: string | null = null
    let resolveWait: (() => void) | null = null
    let streamedTokens = 0
    let eventCount = 0
    let usageInput = 0
    let usageOutput = 0

    try {
      // Build meta-tool SDK definitions from opts.tools.
      // These are caller-managed tools (Lumen/Dyad meta-tools like signal_conclusion).
      // Their handlers push tool_use chunks and return acknowledgments to the SDK.
      const metaTools = this.buildMetaToolDefinitions(opts.tools || [], chunks, () => resolveWait?.(), log, sessionId)

      // Create session with BOTH CassiCore tools (from tool-bridge) and meta-tools
      const allTools = [...this.sdkTools, ...metaTools]
      const session = await this.createSessionWithTools(sessionId, systemPrompt, model, allTools)
      log.info('SDK session ready', {
        model, sessionId,
        promptLength: prompt.length,
        cassiTools: this.sdkTools.length,
        metaTools: metaTools.length,
        totalTools: allTools.length,
      })

      // 1. Subscribe streaming handler BEFORE sendAndWait
      const unsubscribe = session.on((event: SessionEvent) => {
        const t = event.type
        eventCount++

        // Stream text deltas — feeds the caller's inactivity watchdog
        if (t === 'assistant.message_delta') {
          const delta = (event as any).data?.deltaContent ?? ''
          if (delta) {
            streamedTokens += delta.length
            chunks.push({ type: 'token', text: delta })
            resolveWait?.()
          }
        }

        // Usage info — capture for done chunk
        else if (t === 'assistant.usage') {
          const d = (event as any).data
          usageInput += d?.inputTokens ?? 0
          usageOutput += d?.outputTokens ?? 0
          log.debug('SDK usage', { sessionId, inputTokens: d?.inputTokens, outputTokens: d?.outputTokens })
        }

        // Log session errors at INFO, everything else at DEBUG
        else if (t === 'session.error') {
          const dataSummary = (event as any).data
            ? JSON.stringify((event as any).data).slice(0, 300)
            : 'none'
          log.info('SDK session error', { type: t, sessionId, data: dataSummary })
        } else {
          log.debug('SDK event', { type: t, n: eventCount, sessionId })
        }
      })

      // 2. Use sendAndWait() in background for reliable completion detection
      log.info('Starting sendAndWait', { sessionId, promptLength: prompt.length })
      let sendAndWaitResult: { content?: string } | undefined

      session.sendAndWait(
        { prompt },
        SDK_TURN_TIMEOUT_MS,
      ).then((response: any) => {
        const content = response?.data?.content
        sendAndWaitResult = { content }
        log.info('sendAndWait resolved', {
          sessionId,
          hasContent: !!content,
          contentLength: content?.length ?? 0,
          streamedTokens,
          eventCount,
        })
        done = true
        resolveWait?.()
      }).catch((err: unknown) => {
        log.error('sendAndWait rejected', { error: String(err), sessionId, streamedTokens, eventCount })
        error = String(err)
        done = true
        resolveWait?.()
      })

      // Safety deadline
      const HARD_DEADLINE_MS = SDK_TURN_TIMEOUT_MS + 30_000
      const deadline = Date.now() + HARD_DEADLINE_MS

      // 3. Yield chunks as they arrive
      while (!done) {
        if (chunks.length > 0) {
          yield chunks.shift()!
        } else if (Date.now() > deadline) {
          log.error('Hard deadline exceeded', { sessionId, streamedTokens, eventCount })
          error = 'SDK completion hard deadline exceeded'
          break
        } else {
          await new Promise<void>(resolve => {
            resolveWait = resolve
            setTimeout(resolve, 10_000)
          })
        }
      }

      // 4. Drain remaining chunks
      while (chunks.length > 0) {
        yield chunks.shift()!
      }

      // 5. Fallback: if streaming produced nothing, yield sendAndWait content
      if (sendAndWaitResult?.content && streamedTokens === 0) {
        log.info('Using sendAndWait content as fallback', { sessionId, contentLength: sendAndWaitResult.content.length })
        yield { type: 'token', text: sendAndWaitResult.content }
      }

      unsubscribe()

      const totalTokens = usageInput + usageOutput
      log.info('SDK completion done', {
        sessionId, streamedTokens, eventCount,
        tokensUsed: totalTokens, usageInput, usageOutput,
        hadError: !!error,
      })

      if (error) {
        yield { type: 'error' as const, error }
      } else {
        yield {
          type: 'done' as const,
          tokensUsed: totalTokens || undefined,
          tokenBreakdown: totalTokens ? {
            input: usageInput,
            output: usageOutput,
            cacheRead: 0,
            cacheWrite: 0,
          } : undefined,
          model,
        }
      }

      await this.destroySession(sessionId)
    } catch (err) {
      log.error('SDK complete() exception', { error: String(err), sessionId })
      yield { type: 'error' as const, error: String(err) }
    }
  }

  /**
   * Build SDK tool definitions for caller-provided meta-tools (e.g. Lumen/Dyad tools).
   *
   * These handlers DON'T execute the tool — they push a tool_use chunk into the
   * streaming queue and return an acknowledgment to the SDK. The actual tool
   * logic is handled by the caller (Lumen's handleMetaTool, etc.) after it
   * sees the tool_use chunk in the completion stream.
   *
   * This allows the SDK's agentic loop to continue (it gets a result) while
   * the caller still sees and processes the tool call.
   */
  private buildMetaToolDefinitions(
    callerTools: Array<{ name: string; description: string; input_schema: Record<string, unknown> }>,
    chunkQueue: CompletionChunk[],
    wakeGenerator: () => void,
    log: ILogger,
    sessionId: string,
  ): SdkTool[] {
    // Skip tools that are already in the CassiCore tool-bridge (avoid duplicates)
    const bridgedNames = new Set(this.sdkTools.map(t => t.name))

    return callerTools
      .filter(t => !bridgedNames.has(t.name))
      .map(tool => ({
        name: tool.name,
        description: tool.description,
        parameters: tool.input_schema,
        // Override any CLI built-in with the same name (e.g. signal_conclusion)
        overridesBuiltInTool: true,
        handler: async (args: unknown) => {
          const toolCallId = `tc_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
          log.debug('Meta-tool called via SDK', { tool: tool.name, sessionId, toolCallId })

          // Push tool_use chunk — the caller will see and process it
          chunkQueue.push({
            type: 'tool_use',
            toolCall: {
              id: toolCallId,
              name: tool.name,
              input: (args ?? {}) as Record<string, unknown>,
            },
          })
          wakeGenerator()

          // Return acknowledgment to the SDK so it can continue the loop
          return {
            textResultForLlm: `Tool "${tool.name}" acknowledged. The system will process this action.`,
            resultType: 'success' as const,
          }
        },
      }))
  }

  /**
   * Format a Message[] array into a single prompt string.
   * The SDK session API is turn-based, so we concatenate multi-turn
   * history with role markers for context.
   */
  private formatMessagesAsPrompt(messages: Message[]): string {
    const parts: string[] = []
    for (const msg of messages) {
      if (msg.role === 'system') continue
      const content = typeof msg.content === 'string'
        ? msg.content
        : JSON.stringify(msg.content)
      if (!content.trim()) continue
      parts.push(`[${msg.role}]\n${content}`)
    }
    return parts.join('\n\n')
  }

  async countTokens(messages: Message[]): Promise<number> {
    return this.estimateTokens(messages)
  }

  async ping(): Promise<boolean> {
    return this.manager.ping()
  }
}
