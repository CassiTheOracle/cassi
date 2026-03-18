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

  // ─────────────────────────────────────────────────────────────────────────
  // SDK Turn Execution (used by SDK middleware)
  // ─────────────────────────────────────────────────────────────────────────

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

  // ─────────────────────────────────────────────────────────────────────────
  // Session Management
  // ─────────────────────────────────────────────────────────────────────────

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

  // ─────────────────────────────────────────────────────────────────────────
  // IProvider interface (fallback — not the primary usage path)
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Streaming completion — used as fallback when the SDK middleware isn't active.
   * NOTE: This goes through the SDK as well but doesn't capture tool loop semantics.
   */
  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    _attachments?: ImageAttachment[],
    _signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    // Extract user message (last user message)
    const lastUser = [...messages].reverse().find(m => m.role === 'user')
    const prompt = typeof lastUser?.content === 'string'
      ? lastUser.content
      : JSON.stringify(lastUser?.content ?? '')

    // Extract system prompt
    const systemPrompt = opts.systemPrompt
      || messages.find(m => m.role === 'system')?.content as string
      || ''

    const model = opts.model || this.defaultModel
    const sessionId = `fallback_${Date.now()}`

    try {
      const session = await this.getOrCreateSession(sessionId, systemPrompt, model)

      // Collect response via events
      let responseText = ''
      const unsubscribe = session.on('assistant.message_delta', (event) => {
        responseText += event.data.deltaContent
      })

      const response = await session.sendAndWait({ prompt }, SDK_TURN_TIMEOUT_MS)
      unsubscribe()

      if (response?.data.content) {
        responseText = response.data.content
      }

      // Yield as single token chunk
      yield { type: 'token', text: responseText }
      yield { type: 'done' }

      // Clean up fallback session
      await this.destroySession(sessionId)
    } catch (err) {
      yield { type: 'error', error: String(err) }
    }
  }

  async countTokens(messages: Message[]): Promise<number> {
    return this.estimateTokens(messages)
  }

  async ping(): Promise<boolean> {
    return this.manager.ping()
  }
}
