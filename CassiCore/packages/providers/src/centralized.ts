import type { IProvider, Message, CompletionOpts, CompletionChunk, TurnResult } from '../../types/runtime.js'
import type { ILogger, IEventBus, IConfig } from '../../types/interfaces.js'
import { signalPromise } from '../utils/abort.js'
import type { BudgetTracker } from './budget-tracker.js'

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
 * Default rate limits — DISABLED (set to extremely high values to prevent any limiting).
 */
const DEFAULT_RATE_LIMITS: Record<string, RateLimitConfig> = {
  'github-copilot': {
    maxRequests: 999999,
    windowMs: 1000,
    maxConcurrent: 9999,
    errorCooldownMs: 0,
  },
  'kimi-coding': {
    maxRequests: 999999,
    windowMs: 1000,
    maxConcurrent: 9999,
    errorCooldownMs: 0,
  },
  // Default for any other provider
  'default': {
    maxRequests: 999999,
    windowMs: 1000,
    maxConcurrent: 9999,
    errorCooldownMs: 0,
  }
}


/**
 * Global provider limiter/config — shared across all CentralizedProvider instances.
 * Can be tuned via runtime config (preferred) or environment variables for quick experiments.
 */
// Global limits removed - each provider has its own independent rate limits
// Default 20 minute timeout for LLM requests, can be overridden via env
let DEFAULT_PER_REQUEST_TIMEOUT_MS = parseInt(process.env.CASSI_PROVIDER_TIMEOUT_MS || '1200000', 10)

// Log timeout configuration on startup
console.log(`[providers] Default per-request timeout: ${DEFAULT_PER_REQUEST_TIMEOUT_MS / 1000}s`)

// Exports for admin APIs to query provider-specific defaults
export const PROVIDER_RATE_LIMIT_DEFAULTS = DEFAULT_RATE_LIMITS
export const GLOBAL_PROVIDER_DEFAULTS = {
  timeoutMs: DEFAULT_PER_REQUEST_TIMEOUT_MS,
}

export function listProviderConfigKeys() {
  const globalKeys: Record<string, { default: number; description: string }> = {
    'providers.global.timeoutMs': { default: GLOBAL_PROVIDER_DEFAULTS.timeoutMs, description: 'Default per-request timeout in milliseconds' },
  }

  const providerSpecific: Record<string, Record<string, { default: number; description: string }>> = {}
  for (const [provId, cfg] of Object.entries(DEFAULT_RATE_LIMITS)) {
    providerSpecific[provId] = {
      [`providers.${provId}.maxRequests`]: { default: cfg.maxRequests, description: 'Max requests per provider per window' },
      [`providers.${provId}.windowMs`]: { default: cfg.windowMs, description: 'Window duration for provider rate limiting (ms)' },
      [`providers.${provId}.maxConcurrent`]: { default: cfg.maxConcurrent, description: 'Max concurrent requests to this provider' },
      [`providers.${provId}.errorCooldownMs`]: { default: cfg.errorCooldownMs, description: 'Cooldown after provider errors (ms)' },
    }
  }

  return { globalKeys, providerSpecific }
}

// Per-provider request tracking (removed global limits - each provider has its own limits)

/**
 * CentralizedProvider — wraps any IProvider with:
 *   - Request deduplication (same session can't have 2 simultaneous requests)
 *   - Per-provider rate limiting (each provider has independent limits)
 *   - Request metrics and logging
 *   - Error tracking with cooldown
 *   - Event emission for monitoring
 *   - Per-request timeout enforcement
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

  // Budget tracker — records metered requests for quota management
  private budgetTracker: BudgetTracker | undefined

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
      maxRequests: 6000,
      windowMs: 900_000,
      maxConcurrent: 100,
      errorCooldownMs: 500,
    }
    this.config = { ...defaults, ...rateLimits }
  }

  /**
   * Set the budget tracker for recording metered requests.
   * Allows deferred wiring after provider construction.
   */
  setBudgetTracker(tracker: BudgetTracker): void {
    this.budgetTracker = tracker
  }

  /**
   * Main completion method — wraps the provider with all protections.
   */
  async *complete(
    messages: Message[],
    opts: CompletionOpts,
    attachments?: any,
    signal?: AbortSignal,
  ): AsyncIterable<CompletionChunk> {
    // Options understood by CentralizedProvider (extensions to CompletionOpts):
    // - allowConcurrent (boolean): when true, skip per-session deduplication and
    //   allow multiple concurrent requests for the same logical session ID.
    // - dedupe (boolean): when false, equivalent to allowConcurrent=true (legacy)
    // - timeoutMs (number): optional per-request timeout in ms
    // Use these flags sparingly for internal analysis/backfills where parallelism
    // is desirable and callers are aware of provider rate limits.
    // Derive session ID from the last user message or use a fallback
    const sessionId = this.extractSessionId(messages) ?? 'unknown'

    // ── 0. Deduplication: prevent simultaneous requests from same session unless explicitly allowed ──
    const dedupeDisabled = (opts as any)?.allowConcurrent === true || (opts as any)?.dedupe === false
    if (!dedupeDisabled) {
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
    } else {
      // Dedupe intentionally disabled for this call
      if (typeof (this.logger as any).debug === 'function') {
        try { (this.logger as any).debug(`[dedup] allowConcurrent set — skipping dedup for session ${sessionId.slice(-8)}`) } catch { }
      }
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
    const rawModel = (opts as any)?.model || this.models[0]
    const entry: RequestEntry = {
      id: requestId,
      sessionId,
      providerId: this.id,
      model: rawModel,
      startedAt: Date.now(),
      tokensUsed: 0,
      aborted: false,
    }
    // Reserve slot atomically - this must happen immediately after check
    this.inFlight.set(sessionId, entry)
    this.recordRequest()

    // Normalize model reporting to include provider prefix when not already present
    let reportedModel = entry.model || ''
    try {
      if (reportedModel && !reportedModel.includes('/')) reportedModel = `${this.id}/${reportedModel}`
    } catch (err) { /* ignore */ }
    // Persist the normalized model for downstream diagnostics
    entry.model = reportedModel

    this.logger.info(`[request] ${requestId.slice(-12)} session=${sessionId.slice(-8)} model=${reportedModel}`)
    this.bus.emit({
      type: 'provider:request_start',
      providerId: this.id,
      requestId,
      sessionId,
      model: rawModel,
      messageCount: messages.length,
    } as any)

    // ── 5. Execute with error handling and per-request timeout ──
    let completed = false

    // Merge provided signal with our timeout controller
    const requestedTimeoutMs = (opts as any)?.timeoutMs ?? DEFAULT_PER_REQUEST_TIMEOUT_MS
    const controller = new AbortController()
    let timeoutHandle: ReturnType<typeof setTimeout> | undefined

    try {
      timeoutHandle = setTimeout(() => {
        try {
          entry.error = `timeout after ${requestedTimeoutMs}ms`
          entry.aborted = true
          this.metrics.totalErrors++
          this.consecutiveErrors++
          this.lastErrorAt = Date.now()
          this.bus.emit({ type: 'provider:request_timeout', providerId: this.id, requestId, sessionId, timeoutMs: requestedTimeoutMs } as any)
          this.logger.warn(`[timeout] ${requestId.slice(-12)} timed out after ${requestedTimeoutMs}ms - provider may be overloaded or model is too slow`)
        } catch (err) { /* best-effort */ }
        try { controller.abort() } catch (err) { /* best-effort */ }
      }, requestedTimeoutMs)

      // If caller provided a signal, wire it to our controller so caller aborts propagate
      if (signal) {
        if (signal.aborted) {
          try { controller.abort() } catch { }
        } else {
          // Use shared helper to avoid manual listener bookkeeping
          signalPromise(signal).then(() => { try { controller.abort() } catch { } }).catch(() => { })
        }
      }
      // Use 'as any' to pass attachments (not in IProvider interface but supported by implementations)
      const stream = (this.wrapped as any).complete(messages, opts, attachments, controller.signal)
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
      // If controller aborted due to timeout, prefer our entry.error message
      if ((err as any)?.name === 'AbortError' && entry.error && entry.error.startsWith('timeout')) {
        // keep entry.error
      } else {
        entry.error = err instanceof Error ? err.message : String(err)
      }
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
      if (timeoutHandle) clearTimeout(timeoutHandle)
      // No external listener removal required when using signalPromise

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

      // Record against budget tracker if wired (only counts metered models)
      if (this.budgetTracker && !entry.error) {
        const model = opts.model || 'unknown'
        this.budgetTracker.recordRequest(`${this.id}/${model}`)
      }
    }
  }

  async countTokens(messages: Message[]): Promise<number> {
    return this.wrapped.countTokens(messages)
  }

  async ping(signal?: AbortSignal): Promise<boolean> {
    // Don't rate-limit pings — they're lightweight health checks
    return (this.wrapped.ping as any)?.(signal) ?? this.wrapped.ping()
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

  /**
   * Pass-through for load balancer stats (if wrapped provider supports it)
   */
  getStats(): unknown {
    if (typeof (this.wrapped as any).getStats === 'function') {
      return (this.wrapped as any).getStats()
    }
    return null
  }

  /**
   * Get active count for load balancer compatibility
   */
  getActiveCount(): number {
    if (typeof (this.wrapped as any).getActiveCount === 'function') {
      return (this.wrapped as any).getActiveCount()
    }
    return 1
  }

  /**
   * Reset error state (consecutive errors and cooldown).
   * Useful when user manually switches models or after resolving provider issues.
   */
  resetErrorState(): void {
    const hadErrors = this.consecutiveErrors > 0
    this.consecutiveErrors = 0
    this.lastErrorAt = 0
    if (hadErrors) {
      this.logger.info('[reset] Error state cleared')
      this.bus.emit({
        type: 'provider:error_reset',
        providerId: this.id,
      } as any)
    }
  }

  /**
   * Reset rate limit history (for testing or manual intervention).
   */
  resetRateLimitHistory(): void {
    this.requestHistory = []
    this.logger.info('[reset] Rate limit history cleared')
  }

  /**
   * Full reset - clears all state including metrics.
   * Use with caution - mainly for testing.
   */
  resetAll(): void {
    this.resetErrorState()
    this.resetRateLimitHistory()
    this.metrics = {
      totalRequests: 0,
      totalTokens: 0,
      totalErrors: 0,
      deduplicated: 0,
      rateLimited: 0,
    }
    this.logger.info('[reset] All state cleared')
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
    // 1) Prefer system message marker if present (legacy behavior)
    for (const msg of messages) {
      if (msg.role === 'system' && typeof msg.content === 'string') {
        const markerMatch = msg.content.match(/\[session:([^\]]+)\]/i)
        if (markerMatch) return `sess_${markerMatch[1]}`
        const patterns = [/session-([a-zA-Z0-9_-]+)/i, /id[:\s]+([a-zA-Z0-9_-]{8,})/i]
        for (const pattern of patterns) {
          const match = msg.content.match(pattern)
          if (match) return `sess_${match[1]}`
        }
      }
    }

    // 2) If not found in system messages, scan ALL message contents for explicit [session:XXX] markers
    for (const msg of messages) {
      if (typeof msg.content === 'string') {
        const markerMatch = msg.content.match(/\[session:([^\]]+)\]/i)
        if (markerMatch) return `sess_${markerMatch[1]}`
      } else {
        try {
          const s = JSON.stringify(msg.content)
          const markerMatch = s.match(/\[session:([^\]]+)\]/i)
          if (markerMatch) return `sess_${markerMatch[1]}`
        } catch { /* ignore */ }
      }
    }

    // 3) Fall back to content-based hash of user messages
    const userContents = messages
      .filter(m => m.role === 'user')
      .map(m => typeof m.content === 'string' ? m.content : JSON.stringify(m.content))
      .join('\n')

    if (userContents) {
      return `sess_${this.hashString(userContents).slice(0, 16)}`
    }

    // 4) Final fallback: hash of all content
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
      hash = hash | 0 // Force 32-bit signed integer
    }
    return (hash >>> 0).toString(36) // Unsigned to avoid negative values
  }

  private checkRateLimit(): { allowed: boolean; retryAfterMs: number } {
    // Check concurrent limit
    if (this.inFlight.size >= this.config.maxConcurrent) {
      return { allowed: false, retryAfterMs: this.timeUntilNextSlot() || 1000 }
    }

    // Check window-based rate limit
    const now = Date.now()
    const windowStart = now - this.config.windowMs
    this.requestHistory = this.requestHistory.filter(t => t > windowStart)
    if (this.requestHistory.length >= this.config.maxRequests) {
      const retryAfterMs = this.timeUntilNextSlot()
      return { allowed: false, retryAfterMs }
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
    if (this.consecutiveErrors === 0 || this.config.errorCooldownMs <= 0) return 0
    // Exponential backoff: cooldown doubles with each consecutive error, capped at 5 minutes
    const MAX_COOLDOWN_MS = 300_000
    const cooldown = Math.min(
      this.config.errorCooldownMs * Math.pow(2, this.consecutiveErrors - 1),
      MAX_COOLDOWN_MS
    )
    const elapsed = Date.now() - this.lastErrorAt
    return Math.max(0, cooldown - elapsed)
  }

  private calculateCurrentRate(): number {
    const now = Date.now()
    const windowStart = now - this.config.windowMs
    return this.requestHistory.filter(t => t > windowStart).length
  }
}

/**
 * Wrap all providers in a map with CentralizedProvider.
 * Each provider has its own independent rate limits.
 */
export function wrapProvidersWithCentralized(
  providers: Map<string, IProvider>,
  logger: ILogger,
  bus: IEventBus,
  _config?: IConfig,
  budgetTracker?: BudgetTracker,
): Map<string, CentralizedProvider> {
  const wrapped = new Map<string, CentralizedProvider>()
  for (const [id, provider] of providers) {
    const cp = new CentralizedProvider(provider, logger, bus)
    if (budgetTracker) cp.setBudgetTracker(budgetTracker)
    wrapped.set(id, cp)
  }
  logger.info(`[providers] ${wrapped.size} providers wrapped with per-provider rate limiting (no global limits)`)
  return wrapped
}
