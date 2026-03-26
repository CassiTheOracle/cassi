/**
 * Warm Provider Manager — bridges CassiCore's warm session pattern
 * to an OpenAI-compatible API for external clients (e.g. OpenCode).
 *
 * Each conversation (identified by a session key) maps to a single warm
 * SDK session. Multiple user messages within the same conversation reuse
 * the same `sendAndWait()` call, collapsing all turns into one premium
 * request on the GitHub Copilot billing model.
 *
 * The manager:
 *   - Accepts user messages and routes them to warm SDK sessions
 *   - Creates new sessions on first contact, resumes on subsequent messages
 *   - Yields streaming CompletionChunks that callers convert to SSE
 *   - Manages session lifecycle (idle eviction, explicit destroy)
 */
import type { CopilotSdkProvider } from './provider.js'
import type { ILogger, IEventBus } from '../../../types/interfaces.js'
import type { CompletionChunk, CompletionOpts, Message } from '../../../types/runtime.js'

/** Default idle timeout: 8 hours (work-day sessions) */
const DEFAULT_IDLE_TIMEOUT_MS = 8 * 60 * 60 * 1000

/** Eviction check interval: every 5 minutes */
const EVICTION_INTERVAL_MS = 5 * 60 * 1000

export interface WarmProviderManagerOptions {
  provider: CopilotSdkProvider
  bus: IEventBus
  logger: ILogger
  /** Max idle time before eviction (ms). Default: 8 hours */
  idleTimeoutMs?: number
  /** Default system prompt (injected from AGENTS.md + CassiCore context) */
  defaultSystemPrompt?: string
}

interface ManagedSession {
  /** The warm session key used with the provider */
  warmKey: string
  /** Model used for this session */
  model: string
  /** Creation timestamp */
  createdAt: number
  /** Last activity timestamp */
  lastActivity: number
  /** Number of turns processed */
  turnCount: number
}

export class WarmProviderManager {
  private provider: CopilotSdkProvider
  private bus: IEventBus
  private logger: ILogger
  private idleTimeoutMs: number
  private defaultSystemPrompt: string

  /** Map conversationId → managed session metadata */
  private sessions = new Map<string, ManagedSession>()

  /** Periodic eviction timer */
  private evictionTimer: ReturnType<typeof setInterval> | null = null

  constructor(opts: WarmProviderManagerOptions) {
    this.provider = opts.provider
    this.bus = opts.bus
    this.logger = opts.logger.child('warm-provider-mgr')
    this.idleTimeoutMs = opts.idleTimeoutMs ?? DEFAULT_IDLE_TIMEOUT_MS
    this.defaultSystemPrompt = opts.defaultSystemPrompt ?? ''

    // Start periodic eviction
    this.evictionTimer = setInterval(() => this.evictIdleSessions(), EVICTION_INTERVAL_MS)
    // Don't block process exit
    if (this.evictionTimer.unref) this.evictionTimer.unref()
  }

  /**
   * Process a user message within a conversation.
   *
   * On first call for a conversationId: creates a warm session.
   * On subsequent calls: resumes the existing warm session.
   *
   * Yields CompletionChunks that the caller converts to OpenAI SSE format.
   */
  async *processMessage(
    conversationId: string,
    userMessage: string,
    opts: {
      model?: string
      systemPrompt?: string
    } = {},
  ): AsyncIterable<CompletionChunk> {
    const warmKey = `opencode:${conversationId}`
    const model = opts.model || 'claude-sonnet-4.6'
    const systemPrompt = opts.systemPrompt || this.defaultSystemPrompt

    const existing = this.sessions.get(conversationId)
    const isResume = !!existing

    if (isResume) {
      existing.lastActivity = Date.now()
      existing.turnCount++
      this.logger.info('Warm provider: resuming conversation', {
        conversationId,
        warmKey,
        turn: existing.turnCount,
        idleMs: Date.now() - existing.lastActivity,
      })
    } else {
      this.sessions.set(conversationId, {
        warmKey,
        model,
        createdAt: Date.now(),
        lastActivity: Date.now(),
        turnCount: 1,
      })
      this.logger.info('Warm provider: starting new conversation', {
        conversationId,
        warmKey,
        model,
      })
    }

    // Emit turn:start for intelligence modules
    const turnId = `warm-${conversationId}-${Date.now()}`
    this.bus.emit({
      type: 'turn:start',
      sessionId: conversationId,
      turnId,
      message: userMessage.slice(0, 200),
      timestamp: new Date(),
    })

    // Build the messages array for the provider.
    // For the warm session pattern, the provider extracts the latest user
    // message and uses it as the resume prompt. We include the system
    // prompt in the message list so it's available on cold start.
    const messages: Message[] = [
      { role: 'system' as const, content: systemPrompt },
      { role: 'user' as const, content: userMessage },
    ]

    const completionOpts: CompletionOpts = {
      model,
      systemPrompt,
      warmSessionKey: warmKey,
      // No caller meta-tools — the warm session uses its own finished() tool
      tools: [],
    }

    let lastError: string | undefined

    try {
      for await (const chunk of this.provider.complete(messages, completionOpts)) {
        if (chunk.type === 'error') {
          lastError = chunk.error
          // Still yield it so the caller can see the error
        }
        yield chunk
      }
    } catch (err) {
      this.logger.error('Warm provider: completion error', {
        conversationId,
        warmKey,
        error: String(err),
      })
      // Remove the session so next message creates a fresh one
      this.sessions.delete(conversationId)
      yield { type: 'error' as const, error: String(err) }
    }

    // Update last activity
    const session = this.sessions.get(conversationId)
    if (session) {
      session.lastActivity = Date.now()
    }

    // Emit turn:end for intelligence modules
    this.bus.emit({
      type: 'turn:end',
      sessionId: conversationId,
      response: lastError ? `Error: ${lastError}` : '(warm session turn complete)',
      durationMs: Date.now() - (session?.lastActivity ?? Date.now()),
      traceId: turnId,
    })
  }

  /**
   * Destroy a specific conversation's warm session.
   */
  async destroySession(conversationId: string, reason = 'manual destroy'): Promise<boolean> {
    const session = this.sessions.get(conversationId)
    if (!session) return false

    this.sessions.delete(conversationId)
    try {
      await this.provider.destroyWarmSession(session.warmKey, reason)
      this.logger.info('Warm provider: session destroyed', {
        conversationId,
        warmKey: session.warmKey,
        turns: session.turnCount,
        reason,
      })
      return true
    } catch (err) {
      this.logger.warn('Warm provider: error destroying session', {
        conversationId,
        error: String(err),
      })
      return false
    }
  }

  /**
   * List all active managed sessions.
   */
  listSessions(): Array<ManagedSession & { conversationId: string }> {
    return Array.from(this.sessions.entries()).map(([id, s]) => ({
      conversationId: id,
      ...s,
    }))
  }

  /**
   * Evict sessions that have been idle longer than the configured timeout.
   */
  private evictIdleSessions(): void {
    const now = Date.now()
    for (const [id, session] of this.sessions) {
      if (now - session.lastActivity > this.idleTimeoutMs) {
        this.logger.info('Warm provider: evicting idle session', {
          conversationId: id,
          warmKey: session.warmKey,
          idleMs: now - session.lastActivity,
          turns: session.turnCount,
        })
        this.destroySession(id, 'idle timeout').catch(() => {})
      }
    }
  }

  /**
   * Shut down the manager — destroy all sessions and stop eviction timer.
   */
  async shutdown(): Promise<void> {
    if (this.evictionTimer) {
      clearInterval(this.evictionTimer)
      this.evictionTimer = null
    }

    const ids = Array.from(this.sessions.keys())
    for (const id of ids) {
      await this.destroySession(id, 'manager shutdown')
    }
    this.logger.info(`Warm provider manager shut down (${ids.length} sessions destroyed)`)
  }
}
