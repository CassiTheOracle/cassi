import type { IProvider, Message, CompletionOpts, CompletionChunk, TurnResult } from '../../types/runtime.js'
import type { ILogger, IEventBus } from '../../types/interfaces.js'

/**
 * Request tracking entry for a single in-flight or completed request.
 */
interface RequestEntry {
  id: string
  sessionId: string
  providerId: string
  model: string
  startedAt: number
  completedAt?: number
  tokensUsed: number
  error?: string
  aborted: boolean
}

/**
 * Rate limit configuration per provider.
 */
interface RateLimitConfig {
  /** Maximum requests per window */
  maxRequests: number
  /** Window size in milliseconds */
  windowMs: number
  /** Max concurrent requests to this provider */
  maxConcurrent: number
  /** Cooldown after errors (ms) */
  errorCooldownMs: number
}

/**
 * Default rate limits — conservative to prevent runaway requests.
 */
const DEFAULT_RATE_LIMITS: Record<string, RateLimitConfig> = {
  'github-copilot': {
    maxRequests: 60,      // 60 requests per minute
    windowMs: 60_000,
    maxConcurrent: 5,
    errorCooldownMs: 5_000,
  },
  'anthropic': {
    maxRequests: 40,
    windowMs: 60_000,
    maxConcurrent: 3,
    errorCooldownMs: 10_000,
  },
  'kimi': {
    maxRequests: 30,
    windowMs: 60_000,
    maxConcurrent: 3,
    errorCooldownMs: 5_000,
  },
  'kimi-coding': {
    maxRequests: 30,
    windowMs: 60_000,
    maxConcurrent: 3,
    errorCooldownMs: 5_000,
  },
}

/**
 * CentralizedProvider — wraps any IProvider with:
 *   - Request deduplication (same session can't have 2 simultaneous requests)
 *   - Rate limiting (token bucket per provider)
 *   - Request metrics and logging
 *   - Error tracking with cooldown
 *   - Event emission for monitoring
 *
 * This prevents the "request burn" issue where a bug or loop could cause
 * hundreds of API calls in rapid succession.
 */
export class CentralizedProvider implements IProvider {
  readonly id: string
  readonly models: string[]

  private wrapped: IProvider
  private logger: ILogger
  private bus: IEventBus
  private config: RateLimitConfig

  // In-flight request tracking: sessionId → RequestEntry
  private inFlight = new Map<string, RequestEntry>()

  // Recent request history for rate limiting: providerId[]
  private requestHistory: number[] = []

  // Error tracking for cooldown
  private lastErrorAt = 0
  private consecutiveErrors = 0

  // Metrics
  private metrics = {
    totalRequests: 0,
    totalTokens: 0,
    totalErrors: 0,
    deduplicated: 0,
    rateLimited: 0,
  }

  constructor(
    wrapped: IProvider,
    logger: ILogger,
    bus: IEventBus,
    rateLimits?: Partial<RateLimitConfig>,
  ) {
    this.wrapped = wrapped
    this.id = wrapped.id
    this.models = wrapped.models
    this.logger = logger.child(`provider:${wrapped.id}`)
    this.bus = bus

    const defaults = DEFAULT_RATE_LIMITS[wrapped.id] ?? {
      maxRequests: 30,
      windowMs: 60_000,
      maxConcurrent: 3,
      errorCooldownMs: 5_000,
    }
    this.config = { ...defaults, ...rateLimits }
  }

  /**
   * Main completion method — wraps the provider with all protections.
   */
  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: any,
  ): AsyncIterable<CompletionChunk> {
    // Derive session ID from the last user message or use a fallback
    const sessionId = this.extractSessionId(messages) ?? 'unknown'

    // ── 1. Deduplication: prevent simultaneous requests from same session ──
    const existing = this.inFlight.get(sessionId)
    if (existing) {
      this.metrics.deduplicated++
      this.logger.warn(`[dedup] Session ${sessionId.slice(-8)} already has in-flight request ${existing.id.slice(-8)}`)
      this.bus.emit({
        type: 'provider:deduplicated',
        providerId: this.id,
        sessionId,
        existingRequestId: existing.id,
      } as any)
      throw new Error(`Request already in progress for session ${sessionId.slice(-8)}`)
    }

    // ── 2. Rate limiting check (includes concurrent limit) ──
    const rateLimitResult = this.checkRateLimit()
    if (!rateLimitResult.allowed) {
      this.metrics.rateLimited++
      this.logger.warn(`[ratelimit] Provider ${this.id} at capacity, must wait ${rateLimitResult.retryAfterMs}ms`)
      this.bus.emit({
        type: 'provider:rate_limited',
        providerId: this.id,
        sessionId,
        retryAfterMs: rateLimitResult.retryAfterMs,
      } as any)
      throw new Error(`Rate limited: retry after ${rateLimitResult.retryAfterMs}ms`)
    }

    // ── 3. Error cooldown check ──
    const cooldownRemaining = this.checkErrorCooldown()
    if (cooldownRemaining > 0) {
      this.logger.warn(`[cooldown] Provider ${this.id} in error cooldown for ${cooldownRemaining}ms`)
      throw new Error(`Provider cooling down after errors: retry after ${cooldownRemaining}ms`)
    }

    // ── 4. Atomically reserve slot and track the request ──
    const requestId = `${this.id}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
    const entry: RequestEntry = {
      id: requestId,
      sessionId,
      providerId: this.id,
      model: opts.model || this.models[0],
      startedAt: Date.now(),
      tokensUsed: 0,
      aborted: false,
    }
    // Reserve slot atomically - this must happen immediately after check
    this.inFlight.set(sessionId, entry)
    this.recordRequest()

    this.logger.info(`[request] ${requestId.slice(-12)} session=${sessionId.slice(-8)} model=${entry.model}`)
    this.bus.emit({
      type: 'provider:request_start',
      providerId: this.id,
      requestId,
      sessionId,
      model: entry.model,
      messageCount: messages.length,
    } as any)

    // ── 5. Execute with error handling ──
    let completed = false
    try {
      // Use 'as any' to pass attachments (not in IProvider interface but supported by implementations)
      const stream = (this.wrapped as any).complete(messages, opts, attachments)
      for await (const chunk of stream) {
        // Track tokens from chunk
        if (chunk.tokensUsed) {
          entry.tokensUsed = chunk.tokensUsed
        } else if (chunk.type === 'token' && chunk.text) {
          entry.tokensUsed += Math.ceil(chunk.text.length / 4)
        }

        // Pass through to caller
        yield chunk

        // Check if this chunk signals completion
        if (chunk.type === 'done') {
          completed = true
        }
      }

      // Mark success
      this.consecutiveErrors = 0

    } catch (err) {
      entry.error = err instanceof Error ? err.message : String(err)
      this.metrics.totalErrors++
      this.consecutiveErrors++
      this.lastErrorAt = Date.now()

      this.logger.error(`[error] ${requestId.slice(-12)}: ${entry.error}`)
      this.bus.emit({
        type: 'provider:request_error',
        providerId: this.id,
        requestId,
        sessionId,
        error: entry.error,
        consecutiveErrors: this.consecutiveErrors,
      } as any)

      throw err
    } finally {
      // ── 6. Cleanup tracking ──
      entry.completedAt = Date.now()
      this.inFlight.delete(sessionId)
      this.metrics.totalRequests++
      this.metrics.totalTokens += entry.tokensUsed

      const duration = entry.completedAt - entry.startedAt
      this.logger.info(
        `[complete] ${requestId.slice(-12)} ${completed ? 'OK' : 'ERR'} ` +
        `tokens=${entry.tokensUsed} duration=${duration}ms`
      )

      this.bus.emit({
        type: 'provider:request_end',
        providerId: this.id,
        requestId,
        sessionId,
        tokensUsed: entry.tokensUsed,
        durationMs: duration,
        error: entry.error,
      } as any)
    }
  }

  async countTokens(messages: Message[]): Promise<number> {
    return this.wrapped.countTokens(messages)
  }

  async ping(): Promise<boolean> {
    // Don't rate-limit pings — they're lightweight health checks
    return this.wrapped.ping()
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Public metrics API
  // ─────────────────────────────────────────────────────────────────────────

  getMetrics() {
    return {
      ...this.metrics,
      inFlightCount: this.inFlight.size,
      consecutiveErrors: this.consecutiveErrors,
      currentRate: this.calculateCurrentRate(),
    }
  }

  getInFlight(): ReadonlyArray<RequestEntry> {
    return Array.from(this.inFlight.values())
  }

  /**
   * Force-abort a request for a specific session (used by optimizer kill).
   */
  abortSession(sessionId: string): boolean {
    const entry = this.inFlight.get(sessionId)
    if (entry) {
      entry.aborted = true
      this.inFlight.delete(sessionId)
      this.logger.info(`[abort] Session ${sessionId.slice(-8)} request ${entry.id.slice(-8)}`)
      this.bus.emit({
        type: 'provider:request_aborted',
        providerId: this.id,
        requestId: entry.id,
        sessionId,
      } as any)
      return true
    }
    return false
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Private helpers
  // ─────────────────────────────────────────────────────────────────────────

  private extractSessionId(messages: Message[]): string | undefined {
    // Try to find an explicit session identifier in system messages
    for (const msg of messages) {
      if (msg.role === 'system' && typeof msg.content === 'string') {
        // Look for explicit session patterns
        const patterns = [
          /session[:\s]+([a-zA-Z0-9_-]+)/i,
          /session-([a-zA-Z0-9_-]+)/i,
          /id[:\s]+([a-zA-Z0-9_-]{8,})/i,
        ]
        for (const pattern of patterns) {
          const match = msg.content.match(pattern)
          if (match) return `sess_${match[1]}`
        }
      }
    }

    // Fall back to content-based hash of user messages
    const userContents = messages
      .filter(m => m.role === 'user')
      .map(m => typeof m.content === 'string' ? m.content : JSON.stringify(m.content))
      .join('\n')

    if (userContents) {
      return `sess_${this.hashString(userContents).slice(0, 16)}`
    }

    // Final fallback: hash of all content
    const allContent = messages
      .map(m => typeof m.content === 'string' ? m.content : JSON.stringify(m.content))
      .join('\n')

    return allContent ? `sess_${this.hashString(allContent).slice(0, 16)}` : undefined
  }

  private hashString(str: string): string {
    let hash = 0
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash = hash & hash // Convert to 32bit integer
    }
    return Math.abs(hash).toString(36)
  }

  private checkRateLimit(): { allowed: boolean; retryAfterMs: number } {
    const now = Date.now()
    const windowStart = now - this.config.windowMs

    // Clean old entries
    this.requestHistory = this.requestHistory.filter(t => t > windowStart)

    // Check concurrent limit
    if (this.inFlight.size >= this.config.maxConcurrent) {
      return { allowed: false, retryAfterMs: 10_000 } // Estimate 10s for slot
    }

    // Check rate limit
    if (this.requestHistory.length >= this.config.maxRequests) {
      const oldest = this.requestHistory[0]
      const expiresAt = oldest + this.config.windowMs
      return { allowed: false, retryAfterMs: Math.max(0, expiresAt - now) }
    }

    return { allowed: true, retryAfterMs: 0 }
  }

  private recordRequest(): void {
    this.requestHistory.push(Date.now())
  }

  private timeUntilNextSlot(): number {
    if (this.requestHistory.length === 0) return 0
    if (this.inFlight.size >= this.config.maxConcurrent) {
      // Estimate based on average request duration (conservative 10s)
      return 10_000
    }
    // Time until oldest request falls out of window
    const oldest = this.requestHistory[0]
    const expiresAt = oldest + this.config.windowMs
    return Math.max(0, expiresAt - Date.now())
  }

  private checkErrorCooldown(): number {
    if (this.consecutiveErrors === 0) return 0

    // Exponential backoff: 5s, 10s, 20s, 30s cap
    const backoff = Math.min(
      this.config.errorCooldownMs * Math.pow(2, this.consecutiveErrors - 1),
      30_000
    )
    const elapsed = Date.now() - this.lastErrorAt
    return Math.max(0, backoff - elapsed)
  }

  private calculateCurrentRate(): number {
    const now = Date.now()
    const windowStart = now - this.config.windowMs
    return this.requestHistory.filter(t => t > windowStart).length
  }
}

/**
 * Wrap all providers in a map with CentralizedProvider.
 */
export function wrapProvidersWithCentralized(
  providers: Map<string, IProvider>,
  logger: ILogger,
  bus: IEventBus,
): Map<string, CentralizedProvider> {
  const wrapped = new Map<string, CentralizedProvider>()
  for (const [id, provider] of providers) {
    wrapped.set(id, new CentralizedProvider(provider, logger, bus))
  }
  return wrapped
}
