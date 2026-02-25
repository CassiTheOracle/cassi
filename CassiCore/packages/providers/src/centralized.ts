import type { IProvider, Message, CompletionOpts, CompletionChunk, TurnResult } from '../../types/runtime.js'
import type { ILogger, IEventBus, IConfig } from '../../types/interfaces.js'

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
    maxRequests: 600,      // 60 requests per minute
    windowMs: 60_000,
    maxConcurrent: 20,
    errorCooldownMs: 5_000,
  },
  'kimi-coding': {
    maxRequests: 1200,
    windowMs: 60_000,
    maxConcurrent: 40,
    errorCooldownMs: 2_000,
  },
  'pi-bridge': {
    maxRequests: 1200,
    windowMs: 60_000,
    maxConcurrent: 40,
    errorCooldownMs: 2_000,
  }
}

// Export provider defaults so the Admin API can expose provider-specific config keys and defaults
export const PROVIDER_RATE_LIMIT_DEFAULTS = DEFAULT_RATE_LIMITS

// Export global defaults (derived from env fallbacks present at module initialization)
export const GLOBAL_PROVIDER_DEFAULTS = {
  maxConcurrent: GLOBAL_MAX_CONCURRENT,
  windowMs: GLOBAL_WINDOW_MS,
  maxRequestsPerWindow: GLOBAL_MAX_REQUESTS_PER_WINDOW,
  timeoutMs: DEFAULT_PER_REQUEST_TIMEOUT_MS,
}

export function listProviderConfigKeys() {
  const globalKeys: Record<string, { default: number; description: string }> = {
    'providers.global.maxConcurrent': { default: GLOBAL_PROVIDER_DEFAULTS.maxConcurrent, description: 'Maximum global concurrent in-flight provider requests across all providers' },
    'providers.global.windowMs': { default: GLOBAL_PROVIDER_DEFAULTS.windowMs, description: 'Window duration in milliseconds for global rate calculations' },
    'providers.global.maxRequestsPerWindow': { default: GLOBAL_PROVIDER_DEFAULTS.maxRequestsPerWindow, description: 'Maximum global requests allowed within the windowMs window' },
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

/**
 * Global provider limiter/config — shared across all CentralizedProvider instances.
 * Can be tuned via runtime config (preferred) or environment variables for quick experiments.
 */
let GLOBAL_MAX_CONCURRENT = parseInt(process.env.CASSI_GLOBAL_PROVIDER_MAX_CONCURRENT || '32', 10)
let GLOBAL_WINDOW_MS = parseInt(process.env.CASSI_GLOBAL_PROVIDER_WINDOW_MS || '60000', 10)
let GLOBAL_MAX_REQUESTS_PER_WINDOW = parseInt(process.env.CASSI_GLOBAL_PROVIDER_MAX_REQUESTS || '1000', 10)
let DEFAULT_PER_REQUEST_TIMEOUT_MS = parseInt(process.env.CASSI_PROVIDER_TIMEOUT_MS || '20000', 10)

let globalInFlightCount = 0
let globalRequestHistory: number[] = []

/**
 * CentralizedProvider — wraps any IProvider with:
 *   - Request deduplication (same session can't have 2 simultaneous requests)
 *   - Rate limiting (token bucket per provider + global limit)
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

    // ── 0. Global limiter: prevent too many concurrent requests across providers ──
    if (globalInFlightCount >= GLOBAL_MAX_CONCURRENT) {
      this.metrics.rateLimited++
      const retryAfter = 10000
      this.logger.warn(`[global-ratelimit] global in-flight limit reached (${globalInFlightCount}/${GLOBAL_MAX_CONCURRENT})`)
      this.bus.emit({ type: 'provider:global_rate_limited', providerId: this.id, sessionId, retryAfterMs: retryAfter } as any)
      throw new Error(`Global provider capacity reached: retry after ${retryAfter}ms`)
    }

    // Also check global requests per window
    const now = Date.now()
    const globalWindowStart = now - GLOBAL_WINDOW_MS
    globalRequestHistory = globalRequestHistory.filter(t => t > globalWindowStart)
    if (globalRequestHistory.length >= GLOBAL_MAX_REQUESTS_PER_WINDOW) {
      const oldest = globalRequestHistory[0]
      const expiresAt = oldest + GLOBAL_WINDOW_MS
      const retryAfterMs = Math.max(0, expiresAt - now)
      this.metrics.rateLimited++
      this.logger.warn(`[global-ratelimit] global request rate exceeded (${globalRequestHistory.length}/${GLOBAL_MAX_REQUESTS_PER_WINDOW})`)
      this.bus.emit({ type: 'provider:global_rate_limited', providerId: this.id, sessionId, retryAfterMs } as any)
      throw new Error(`Global rate limited: retry after ${retryAfterMs}ms`)
    }

    // ── 1. Deduplication: prevent simultaneous requests from same session unless explicitly allowed ──
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
        try { (this.logger as any).debug(`[dedup] allowConcurrent set — skipping dedup for session ${sessionId.slice(-8)}`) } catch {}
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
    globalInFlightCount++
    globalRequestHistory.push(Date.now())

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
    const timeoutHandle = setTimeout(() => {
      try {
        entry.error = `timeout after ${requestedTimeoutMs}ms`
        entry.aborted = true
        this.metrics.totalErrors++
        this.consecutiveErrors++
        this.lastErrorAt = Date.now()
        this.bus.emit({ type: 'provider:request_timeout', providerId: this.id, requestId, sessionId, timeoutMs: requestedTimeoutMs } as any)
        this.logger.warn(`[timeout] ${requestId.slice(-12)} timed out after ${requestedTimeoutMs}ms`)
      } catch (err) { /* best-effort */ }
      try { controller.abort() } catch (err) { /* best-effort */ }
    }, requestedTimeoutMs)

    // If caller provided a signal, wire it to our controller so caller aborts propagate
    const onCallerAbort = () => { try { controller.abort() } catch { } }
    if (signal) {
      if (signal.aborted) onCallerAbort()
      else signal.addEventListener('abort', onCallerAbort)
    }

    try {
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
      clearTimeout(timeoutHandle)
      if (signal) {
        try { signal.removeEventListener('abort', onCallerAbort) } catch { }
      }

      entry.completedAt = Date.now()
      this.inFlight.delete(sessionId)
      if (globalInFlightCount > 0) globalInFlightCount--
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
      globalInFlightCount,
      globalCurrentRate: this.calculateGlobalRate(),
      globalConfig: {
        maxConcurrent: GLOBAL_MAX_CONCURRENT,
        windowMs: GLOBAL_WINDOW_MS,
        maxRequestsPerWindow: GLOBAL_MAX_REQUESTS_PER_WINDOW,
        defaultTimeoutMs: DEFAULT_PER_REQUEST_TIMEOUT_MS,
      }
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
      if (globalInFlightCount > 0) globalInFlightCount--
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

  private calculateGlobalRate(): number {
    const now = Date.now()
    const windowStart = now - GLOBAL_WINDOW_MS
    return globalRequestHistory.filter(t => t > windowStart).length
  }
}

/**
 * Wrap all providers in a map with CentralizedProvider.
 * Optionally accepts a runtime config so global limits can be loaded from
 * the daemon configuration (preferred over env vars).
 */
export function wrapProvidersWithCentralized(
  providers: Map<string, IProvider>,
  logger: ILogger,
  bus: IEventBus,
  config?: IConfig,
): Map<string, CentralizedProvider> {
  // Apply runtime configuration to global limits if provided
  try {
    if (config) {
      const gc = config.get<number>('providers.global.maxConcurrent', GLOBAL_MAX_CONCURRENT)
      GLOBAL_MAX_CONCURRENT = Number(gc) || GLOBAL_MAX_CONCURRENT
      const gw = config.get<number>('providers.global.windowMs', GLOBAL_WINDOW_MS)
      GLOBAL_WINDOW_MS = Number(gw) || GLOBAL_WINDOW_MS
      const gmr = config.get<number>('providers.global.maxRequestsPerWindow', GLOBAL_MAX_REQUESTS_PER_WINDOW)
      GLOBAL_MAX_REQUESTS_PER_WINDOW = Number(gmr) || GLOBAL_MAX_REQUESTS_PER_WINDOW
      const tms = config.get<number>('providers.global.timeoutMs', DEFAULT_PER_REQUEST_TIMEOUT_MS)
      DEFAULT_PER_REQUEST_TIMEOUT_MS = Number(tms) || DEFAULT_PER_REQUEST_TIMEOUT_MS
      logger.info(`[providers] Global provider limits applied from config`, {
        GLOBAL_MAX_CONCURRENT,
        GLOBAL_WINDOW_MS,
        GLOBAL_MAX_REQUESTS_PER_WINDOW,
        DEFAULT_PER_REQUEST_TIMEOUT_MS,
      })

      // Re-apply on config reloads
      try {
        bus.on('config:reloaded', () => {
          try {
            const gc2 = config.get<number>('providers.global.maxConcurrent', GLOBAL_MAX_CONCURRENT)
            GLOBAL_MAX_CONCURRENT = Number(gc2) || GLOBAL_MAX_CONCURRENT
            const gw2 = config.get<number>('providers.global.windowMs', GLOBAL_WINDOW_MS)
            GLOBAL_WINDOW_MS = Number(gw2) || GLOBAL_WINDOW_MS
            const gmr2 = config.get<number>('providers.global.maxRequestsPerWindow', GLOBAL_MAX_REQUESTS_PER_WINDOW)
            GLOBAL_MAX_REQUESTS_PER_WINDOW = Number(gmr2) || GLOBAL_MAX_REQUESTS_PER_WINDOW
            const tms2 = config.get<number>('providers.global.timeoutMs', DEFAULT_PER_REQUEST_TIMEOUT_MS)
            DEFAULT_PER_REQUEST_TIMEOUT_MS = Number(tms2) || DEFAULT_PER_REQUEST_TIMEOUT_MS
            logger.info('[providers] Global provider limits re-applied from config:config:reloaded')
          } catch (err) {
            logger.warn('[providers] failed to re-apply global provider limits on config:reloaded', { error: String(err) })
          }
        })
      } catch (err) {
        // best-effort
      }
    }
  } catch (err) {
    // best-effort — leave env/defaults in place
  }

  const wrapped = new Map<string, CentralizedProvider>()
  for (const [id, provider] of providers) {
    wrapped.set(id, new CentralizedProvider(provider, logger, bus))
  }
  return wrapped
}
