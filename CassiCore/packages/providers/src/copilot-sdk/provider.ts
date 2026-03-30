/**
 * CopilotSDK Provider — IProvider wrapper that delegates entire turns
 * (including tool loops) to the Copilot SDK.
 *
 * When used with the SDK middleware, `executeSdkTurn()` handles the full
 * agentic loop as a single premium request. The `complete()` method is
 * the primary path for Lumen/Dyad/Helix agent sessions.
 *
 * Warm Session Pattern:
 *   When `opts.warmSessionKey` is set, the provider keeps SDK sessions alive
 *   across successive `complete()` calls by blocking a `finished()` tool
 *   handler between iterations. All iterations within the same warm session
 *   collapse into a single premium request (single `sendAndWait()` call).
 *   This provides both billing efficiency and context warmth.
 */
import { approveAll } from '@github/copilot-sdk'
import type { CopilotSession, SessionEvent, Tool as SdkTool } from '@github/copilot-sdk'

import { BaseProvider } from '../base.js'
import { CopilotSdkManager } from './client-manager.js'
import { mapSdkEvent, createTurnState } from './event-mapper.js'
import { WarmSessionState, buildFinishedSdkTool } from './finished-tool.js'
import type { IterationResult } from './finished-tool.js'

import type { Message, CompletionOpts, CompletionChunk, TurnResult, ImageAttachment } from '../../../types/runtime.js'
import type { ILogger, IEventBus } from '../../../types/interfaces.js'

/** Default sendAndWait timeout: 10 minutes (tool loops can be long). */
const SDK_TURN_TIMEOUT_MS = 600_000

/**
 * Warm sendAndWait timeout: 24 hours.
 * Warm sessions stay alive across many iterations, so we need a very long
 * timeout. The wall-clock timer is the only risk — if it fires, the
 * sendAndWait Promise rejects but the session stays alive.
 */
const WARM_SESSION_TIMEOUT_MS = 24 * 60 * 60 * 1000

/** Stale session eviction: destroy warm sessions idle for > 10 minutes */
const WARM_SESSION_MAX_IDLE_MS = 10 * 60 * 1000

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

/** Warm session entry — tracks a kept-alive SDK session */
interface WarmSession {
  session: CopilotSession
  state: WarmSessionState
  /** Background sendAndWait() Promise — stays alive across iterations */
  sendAndWaitPromise: Promise<unknown>
  /** Unsubscribe from session events (set per-iteration) */
  unsubscribe: (() => void) | null
  model: string
  createdAt: number
  lastActivity: number
  /** Logging identity for diagnostics */
  warmKey: string
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

  /** Map CassiCore sessionId → SDK CopilotSession (for executeSdkTurn) */
  private sessions = new Map<string, CopilotSession>()

  /** Map warmSessionKey → WarmSession (for complete() warm sessions) */
  private warmSessions = new Map<string, WarmSession>()

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
    // Destroy warm sessions first (abort blocked handlers)
    const warmKeys = Array.from(this.warmSessions.keys())
    for (const key of warmKeys) {
      await this.destroyWarmSession(key, 'daemon shutdown')
    }
    if (warmKeys.length > 0) {
      this.logger.info(`Destroyed ${warmKeys.length} warm session(s)`)
    }

    const ids = Array.from(this.sessions.keys())
    await Promise.allSettled(ids.map(id => this.destroySession(id)))
    this.logger.info(`Destroyed ${ids.length} SDK session(s)`)
  }

  /**
   * Destroy a warm session — abort the blocked finished() handler and disconnect.
   */
  async destroyWarmSession(warmKey: string, reason = 'session destroyed'): Promise<void> {
    const warm = this.warmSessions.get(warmKey)
    if (!warm) return

    warm.state.abort(reason)
    warm.unsubscribe?.()
    this.warmSessions.delete(warmKey)

    try {
      await warm.session.disconnect()
    } catch (err) {
      this.logger.warn(`Error disconnecting warm session ${warmKey}: ${String(err)}`)
    }

    this.logger.info('Warm session destroyed', {
      warmKey,
      reason,
      iterations: warm.state.iterationCount,
      aliveMs: Date.now() - warm.createdAt,
    })
  }

  /**
   * Evict stale warm sessions that have been idle too long.
   */
  private evictStaleWarmSessions(): void {
    const now = Date.now()
    for (const [key, warm] of this.warmSessions) {
      if (now - warm.lastActivity > WARM_SESSION_MAX_IDLE_MS) {
        this.logger.info('Evicting stale warm session', {
          warmKey: key,
          idleMs: now - warm.lastActivity,
          iterations: warm.state.iterationCount,
        })
        this.destroyWarmSession(key, 'idle timeout').catch(() => {})
      }
    }
  }

  // IProvider interface — primary completion path

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
   *
   * Warm Session Pattern (when opts.warmSessionKey is set):
   *   All iterations within the same warmSessionKey share one sendAndWait() call.
   *   The `finished()` tool handler blocks between iterations, keeping the session
   *   alive and collapsing all iterations into a single premium request.
   *
   *   Cold start: create session → sendAndWait() → yield until finished() → leave warm
   *   Resume:     registerTools() → resume finished() → yield until finished() → leave warm
   */
  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    _attachments?: ImageAttachment[],
    _signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    const warmKey = opts.warmSessionKey
    if (warmKey) {
      yield* this.completeWithWarmSession(warmKey, messages, opts)
    } else {
      yield* this.completeCold(messages, opts)
    }
  }

  /**
   * Cold completion — original behavior. Creates a session, runs one turn, destroys it.
   */
  private async *completeCold(
    messages: Message[],
    opts: CompletionOpts,
  ): AsyncIterable<CompletionChunk> {
    const model = opts.model || this.defaultModel
    const sessionId = `sdk_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const log = this.logger.child('sdk-complete')

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
      const metaTools = this.buildMetaToolDefinitions(opts.tools || [], chunks, () => resolveWait?.(), log, sessionId)
      const allTools = [...this.sdkTools, ...metaTools]
      const session = await this.createSessionWithTools(sessionId, systemPrompt, model, allTools)
      log.info('SDK session ready (cold)', {
        model, sessionId,
        promptLength: prompt.length,
        cassiTools: this.sdkTools.length,
        metaTools: metaTools.length,
        totalTools: allTools.length,
      })

      const unsubscribe = session.on((event: SessionEvent) => {
        const t = event.type
        eventCount++
        if (t === 'assistant.message_delta') {
          const delta = (event as any).data?.deltaContent ?? ''
          if (delta) {
            streamedTokens += delta.length
            chunks.push({ type: 'token', text: delta })
            resolveWait?.()
          }
        } else if (t === 'assistant.usage') {
          const d = (event as any).data
          usageInput += d?.inputTokens ?? 0
          usageOutput += d?.outputTokens ?? 0
        } else if (t === 'session.error') {
          const dataSummary = (event as any).data ? JSON.stringify((event as any).data).slice(0, 300) : 'none'
          log.info('SDK session error', { type: t, sessionId, data: dataSummary })
        }
      })

      log.info('Starting sendAndWait (cold)', { sessionId, promptLength: prompt.length })
      let sendAndWaitResult: { content?: string } | undefined

      session.sendAndWait(
        { prompt },
        SDK_TURN_TIMEOUT_MS,
      ).then((response: any) => {
        sendAndWaitResult = { content: response?.data?.content }
        done = true
        resolveWait?.()
      }).catch((err: unknown) => {
        log.error('sendAndWait rejected', { error: String(err), sessionId })
        error = String(err)
        done = true
        resolveWait?.()
      })

      const HARD_DEADLINE_MS = SDK_TURN_TIMEOUT_MS + 30_000
      const deadline = Date.now() + HARD_DEADLINE_MS

      while (!done) {
        if (chunks.length > 0) {
          yield chunks.shift()!
        } else if (Date.now() > deadline) {
          error = 'SDK completion hard deadline exceeded'
          break
        } else {
          await new Promise<void>(resolve => {
            resolveWait = resolve
            setTimeout(resolve, 10_000)
          })
        }
      }

      while (chunks.length > 0) yield chunks.shift()!

      if (sendAndWaitResult?.content && streamedTokens === 0) {
        yield { type: 'token', text: sendAndWaitResult.content }
      }

      unsubscribe()

      const totalTokens = usageInput + usageOutput
      log.info('SDK completion done (cold)', {
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
            input: usageInput, output: usageOutput,
            cacheRead: 0, cacheWrite: 0,
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
   * Warm completion — keeps the SDK session alive across iterations.
   *
   * On cold start (no existing warm session):
   *   1. Creates session with CassiCore tools + meta-tools + finished() tool
   *   2. Starts sendAndWait() in background (with 24h timeout)
   *   3. Yields streaming chunks until the agent calls finished()
   *   4. Leaves the session warm (finished() handler blocked)
   *
   * On resume (existing warm session blocked in finished()):
   *   1. Updates meta-tools via registerTools()
   *   2. Subscribes new event handler for this iteration's chunk queue
   *   3. Resumes the blocked finished() handler with the new prompt
   *   4. Yields streaming chunks until the agent calls finished() again
   *   5. Leaves the session warm
   */
  private async *completeWithWarmSession(
    warmKey: string,
    messages: Message[],
    opts: CompletionOpts,
  ): AsyncIterable<CompletionChunk> {
    const model = opts.model || this.defaultModel
    const log = this.logger.child('sdk-warm')
    const systemPrompt = opts.systemPrompt
      || messages.find(m => m.role === 'system')?.content as string
      || ''
    const prompt = this.formatMessagesAsPrompt(messages)

    // Evict stale sessions opportunistically
    this.evictStaleWarmSessions()

    const chunks: CompletionChunk[] = []
    let resolveWait: (() => void) | null = null
    const wakeGenerator = () => resolveWait?.()

    let usageInput = 0
    let usageOutput = 0
    let streamedTokens = 0
    let error: string | null = null

    const warm = this.warmSessions.get(warmKey)
    const isResume = warm?.state.isBlocked === true

    try {
      if (isResume) {
        // ── RESUME WARM SESSION ──
        log.info('Resuming warm session', {
          warmKey,
          iteration: warm!.state.iterationCount + 1,
          model,
          blockedMs: Date.now() - warm!.state.lastFinishedAt,
        })

        // Unsubscribe previous event handler (from prior iteration)
        warm!.unsubscribe?.()

        // Update meta-tools — registerTools replaces tools with the same name
        const metaTools = this.buildMetaToolDefinitions(
          opts.tools || [], chunks, wakeGenerator, log, warmKey, warm!.state,
        )
        if (metaTools.length > 0) {
          await warm!.session.registerTools(metaTools)
        }

        // Subscribe new event handler for this iteration
        warm!.unsubscribe = warm!.session.on((event: SessionEvent) => {
          this.handleWarmEvent(event, chunks, wakeGenerator, log, warmKey, (input, output) => {
            usageInput += input
            usageOutput += output
          })
        })

        // Prepare to wait for the next finished() call
        warm!.state.prepareForIteration()
        const finishedPromise = warm!.state.waitForFinished()

        // Resume the blocked handler — the agent gets our prompt as the tool result
        warm!.state.resume(prompt)
        warm!.lastActivity = Date.now()

        // Yield chunks until finished() is called
        yield* this.yieldUntilFinished(chunks, finishedPromise, wakeGenerator, (rw) => { resolveWait = rw })

        // Drain remaining chunks
        while (chunks.length > 0) yield chunks.shift()!

        warm!.lastActivity = Date.now()
      } else {
        // ── COLD START WARM SESSION ──
        if (warm) {
          // Stale warm session (not blocked) — destroy and recreate
          log.info('Destroying stale warm session', { warmKey })
          await this.destroyWarmSession(warmKey, 'stale (not blocked)')
        }

        const sessionId = `warm_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
        const state = new WarmSessionState()

        // Build all tools: CassiCore + meta-tools (with warm blocking on signal_conclusion)
        const metaTools = this.buildMetaToolDefinitions(
          opts.tools || [], chunks, wakeGenerator, log, warmKey, state,
        )
        // Also include standalone finished() tool as fallback
        // (in case caller has no signal_conclusion tool)
        const finishedSdkTool = buildFinishedSdkTool(state, log)
        const allTools = [...this.sdkTools, ...metaTools, finishedSdkTool]

        const session = await this.createSessionWithTools(sessionId, systemPrompt, model, allTools)
        log.info('SDK warm session created', {
          warmKey, sessionId, model,
          promptLength: prompt.length,
          cassiTools: this.sdkTools.length,
          metaTools: metaTools.length,
          totalTools: allTools.length,
        })

        // Subscribe event handler
        const unsubscribe = session.on((event: SessionEvent) => {
          this.handleWarmEvent(event, chunks, wakeGenerator, log, warmKey, (input, output) => {
            usageInput += input
            usageOutput += output
          })
        })

        // Store warm session entry
        const warmEntry: WarmSession = {
          session,
          state,
          sendAndWaitPromise: null!,
          unsubscribe,
          model,
          createdAt: Date.now(),
          lastActivity: Date.now(),
          warmKey,
        }

        // Prepare to wait for the first finished() call
        state.prepareForIteration()
        const finishedPromise = state.waitForFinished()

        // Start sendAndWait in background — this stays alive across ALL iterations
        warmEntry.sendAndWaitPromise = session.sendAndWait(
          { prompt },
          WARM_SESSION_TIMEOUT_MS,
        ).then((response: any) => {
          log.info('Warm sendAndWait resolved (session ended)', {
            warmKey,
            iterations: state.iterationCount,
            hasContent: !!response?.data?.content,
          })
          // Unblock yieldUntilFinished if the model never called finished().
          // Without this, the agent hangs for 24h waiting for a tool call
          // that will never come (e.g., model returned text-only response).
          state.sessionEnded(response?.data?.content)
          // Session is dead — remove from warm pool so next iteration cold-starts
          this.warmSessions.delete(warmKey)
        }).catch((err: unknown) => {
          log.warn('Warm sendAndWait rejected', {
            warmKey,
            error: String(err),
            iterations: state.iterationCount,
          })
          // Push error chunk so the model handle can detect the failure and
          // trigger provider fallback on the next acquire() call.
          chunks.push({ type: 'error' as const, error: String(err) })
          wakeGenerator()
          // Also unblock on rejection to prevent hanging
          state.sessionEnded()
          this.warmSessions.delete(warmKey)
        })

        this.warmSessions.set(warmKey, warmEntry)

        // Yield chunks until finished() is called
        yield* this.yieldUntilFinished(chunks, finishedPromise, wakeGenerator, (rw) => { resolveWait = rw })

        // Drain remaining chunks
        while (chunks.length > 0) yield chunks.shift()!

        warmEntry.lastActivity = Date.now()
      }

      // Yield done chunk — iteration complete, session stays warm
      const totalTokens = usageInput + usageOutput
      log.info('Warm iteration complete', {
        warmKey, streamedTokens,
        tokensUsed: totalTokens, usageInput, usageOutput,
        iteration: this.warmSessions.get(warmKey)?.state.iterationCount ?? 0,
        isBlocked: this.warmSessions.get(warmKey)?.state.isBlocked ?? false,
      })

      yield {
        type: 'done' as const,
        tokensUsed: totalTokens || undefined,
        tokenBreakdown: totalTokens ? {
          input: usageInput, output: usageOutput,
          cacheRead: 0, cacheWrite: 0,
        } : undefined,
        model,
      }

    } catch (err) {
      log.error('Warm complete() exception', { error: String(err), warmKey })

      // On error, destroy the warm session to avoid stuck state
      await this.destroyWarmSession(warmKey, `error: ${String(err)}`)

      yield { type: 'error' as const, error: String(err) }
    }
  }

  /**
   * Yield chunks from the queue until the finishedPromise resolves.
   * Shared by both cold-start and resume paths.
   */
  private async *yieldUntilFinished(
    chunks: CompletionChunk[],
    finishedPromise: Promise<IterationResult>,
    _wakeGenerator: () => void,
    setResolveWait: (rw: (() => void) | null) => void,
  ): AsyncIterable<CompletionChunk> {
    let iterationDone = false

    // Race: finishedPromise will resolve when the agent calls finished()
    finishedPromise.then(() => {
      iterationDone = true
      // Wake the generator so it can exit
      setResolveWait(null)
    }).catch(() => {
      iterationDone = true
      setResolveWait(null)
    })

    const deadline = Date.now() + WARM_SESSION_TIMEOUT_MS + 30_000

    while (!iterationDone) {
      if (chunks.length > 0) {
        yield chunks.shift()!
      } else if (Date.now() > deadline) {
        throw new Error('Warm session iteration hard deadline exceeded')
      } else {
        await new Promise<void>(resolve => {
          setResolveWait(resolve)
          // Check frequently for new chunks
          setTimeout(resolve, 5_000)
        })
      }
    }
  }

  /**
   * Shared event handler for warm session events.
   * Pushes streaming chunks and tracks usage.
   */
  private handleWarmEvent(
    event: SessionEvent,
    chunks: CompletionChunk[],
    wakeGenerator: () => void,
    log: ILogger,
    warmKey: string,
    onUsage: (input: number, output: number) => void,
  ): void {
    const t = event.type

    if (t === 'assistant.message_delta') {
      const delta = (event as any).data?.deltaContent ?? ''
      if (delta) {
        chunks.push({ type: 'token', text: delta })
        wakeGenerator()
      }
    } else if (t === 'assistant.reasoning_delta') {
      // Extended thinking / reasoning tokens — stream them as 'thinking' chunks
      const delta = (event as any).data?.deltaContent ?? ''
      if (delta) {
        chunks.push({ type: 'thinking', text: delta })
        wakeGenerator()
      }
    } else if (t === 'assistant.usage') {
      const d = (event as any).data
      onUsage(d?.inputTokens ?? 0, d?.outputTokens ?? 0)
      log.debug('SDK usage (warm)', { warmKey, inputTokens: d?.inputTokens, outputTokens: d?.outputTokens })
    } else if (t === 'session.error') {
      const dataSummary = (event as any).data ? JSON.stringify((event as any).data).slice(0, 300) : 'none'
      log.info('SDK session error (warm)', { warmKey, data: dataSummary })
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
   *
   * Warm Session Integration:
   *   When `warmState` is provided, the `signal_conclusion` meta-tool handler
   *   doubles as the warm session's blocking point. After pushing the tool_use
   *   chunk, it calls `warmState.onFinishedCalled()` which:
   *     1. Signals the generator that this iteration is done
   *     2. Blocks the handler until the next complete() call resumes it
   *     3. Returns the new prompt as the tool result to the SDK
   *   This keeps the entire multi-iteration workflow in a single sendAndWait().
   */
  private buildMetaToolDefinitions(
    callerTools: Array<{ name: string; description: string; input_schema: Record<string, unknown> }>,
    chunkQueue: CompletionChunk[],
    wakeGenerator: () => void,
    log: ILogger,
    sessionId: string,
    warmState?: WarmSessionState,
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

          // Warm session: signal_conclusion doubles as the blocking point.
          // When the agent calls signal_conclusion, we block the handler
          // to keep the sendAndWait() alive across iterations.
          if (warmState && tool.name === 'signal_conclusion') {
            const conclusion = (args as any)?.conclusion ?? ''
            log.info('signal_conclusion triggering warm session block', {
              sessionId,
              iteration: warmState.iterationCount + 1,
              conclusionPreview: String(conclusion).slice(0, 100),
            })

            try {
              const newPrompt = await warmState.onFinishedCalled(String(conclusion))
              log.info('Warm session resumed via signal_conclusion', {
                sessionId,
                iteration: warmState.iterationCount,
                promptLength: newPrompt.length,
              })
              return {
                textResultForLlm: newPrompt,
                resultType: 'success' as const,
              }
            } catch (err) {
              log.info('Warm session terminated during signal_conclusion block', {
                sessionId,
                error: String(err),
              })
              return {
                textResultForLlm: `Session ended: ${String(err)}. You may stop now — do not call any tools.`,
                resultType: 'success' as const,
              }
            }
          }

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
