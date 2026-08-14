import { rootLogger, writeThoughtRequestLog, writeThoughtResultLog } from '../logger.js'
import { signalPromise } from '../utils/abort.js'
import { ActivityTimeout } from '../utils/activity-timeout.js'

import type { BudgetTracker } from './budget-tracker.js'
import type { RateLimitStore } from './rate-limit-store.js'
import type { ILogger, IEventBus, IConfig } from '../../types/interfaces.js'
import type { IProvider, Message, CompletionOpts, CompletionChunk, TurnResult } from '../../types/runtime.js'



const logger: ILogger = rootLogger.child('providers')

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
 * Provider configuration — only error cooldown.
 * Rate limits are learned adaptively from 429 responses, not pre-configured.
 */
interface ProviderConfig {
  errorCooldownMs: number
}

/**
 * Timescale windows for adaptive rate limit learning.
 * When a 429 is received, we snapshot the request count at all timescales.
 * Each timescale learns its limit independently — providers often enforce
 * different ceilings at different horizons (e.g., 60 RPM but 1000 RPH).
 */
const RATE_WINDOWS = [
  { label: '1m',  windowMs: 60_000 },
  { label: '10m', windowMs: 600_000 },
  { label: '1h',  windowMs: 3_600_000 },
] as const

type WindowLabel = typeof RATE_WINDOWS[number]['label']

/** Use 90% of the rate that triggered a 429 */
const SAFETY_MARGIN = 0.90

/** Probe upward by 5% after this many clean windows */
const PROBE_UP_CLEAN_WINDOWS = 5
const PROBE_UP_FACTOR = 1.05

/** Tighten by this factor when hit again at same timescale */
const TIGHTEN_FACTOR = 0.95

/** Max transparent retries when rate limited before surfacing error to caller */
const MAX_RATE_LIMIT_RETRIES = 5

/**
 * Sleep with abort support — rejects early with AbortError if `signal` fires.
 * Used by the rate-limit retry path so waits are cancellable.
 */
function sleepWithAbort(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'))
  if (ms <= 0) return Promise.resolve()
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    }, { once: true })
  })
}

/**
 * Learned rate limit state at a specific timescale for a specific model.
 */
interface LearnedLimit {
  observedCount: number
  safeCount: number
  lastHitAt: number
  hitCount: number
}

const DEFAULT_PROVIDER_CONFIGS: Record<string, ProviderConfig> = {
  'github-copilot': {
    errorCooldownMs: 15_000,
  },
  'kimi-coding': {
    errorCooldownMs: 5_000,
  },
  'default': {
    errorCooldownMs: 5_000,
  }
}


/**
 * Global provider config — shared across all CentralizedProvider instances.
 * Can be tuned via runtime config (preferred) or environment variables for quick experiments.
 */
const DEFAULT_PER_REQUEST_TIMEOUT_MS = parseInt(process.env.CASSI_PROVIDER_TIMEOUT_MS || '1200000', 10)
const DEFAULT_INACTIVITY_TIMEOUT_MS = parseInt(process.env.CASSI_PROVIDER_INACTIVITY_TIMEOUT_MS || '120000', 10)

logger.debug(`Default per-request timeout: ${DEFAULT_PER_REQUEST_TIMEOUT_MS / 1000}s`)

export const PROVIDER_RATE_LIMIT_DEFAULTS = DEFAULT_PROVIDER_CONFIGS
export const GLOBAL_PROVIDER_DEFAULTS = {
  timeoutMs: DEFAULT_PER_REQUEST_TIMEOUT_MS,
}

function getConfiguredProviderConfig(config: IConfig | undefined, providerId: string): Partial<ProviderConfig> {
  if (!config) return {}

  return {
    errorCooldownMs: config.get<number>(`providers.${providerId}.errorCooldownMs`, config.get<number>('providers.default.errorCooldownMs', DEFAULT_PROVIDER_CONFIGS.default.errorCooldownMs)),
  }
}

export function listProviderConfigKeys() {
  const globalKeys: Record<string, { default: number; description: string }> = {
    'providers.global.timeoutMs': { default: GLOBAL_PROVIDER_DEFAULTS.timeoutMs, description: 'Default per-request timeout in milliseconds' },
  }

  const providerSpecific: Record<string, Record<string, { default: number; description: string }>> = {}
  for (const [provId, cfg] of Object.entries(DEFAULT_PROVIDER_CONFIGS)) {
    providerSpecific[provId] = {
      [`providers.${provId}.errorCooldownMs`]: { default: cfg.errorCooldownMs, description: 'Cooldown after provider errors (ms)' },
    }
  }

  return { globalKeys, providerSpecific }
}

/**
 * CentralizedProvider — wraps any IProvider with request deduplication, per-provider
 * rate limiting, error tracking with cooldown, and timeout enforcement.
 *
 * WHY: prevents the "request burn" issue where a bug or loop could cause
 * hundreds of API calls in rapid succession.
 */
export class CentralizedProvider implements IProvider {
  readonly id: string
  readonly models: string[]

  /** Expose the inner provider for unwrapping (e.g. to call setBackgroundOnly on GitHubCopilotProvider) */
  readonly inner: IProvider
  private wrapped: IProvider
  private logger: ILogger
  private bus: IEventBus
  private config: ProviderConfig

  // In-flight request tracking: sessionId → RequestEntry
  private inFlight = new Map<string, RequestEntry>()

  // Per-model request history: model → array of timestamps
  // Used for both rate calculation and adaptive limit enforcement
  private modelHistory = new Map<string, number[]>()

  // Learned rate limits: `${model}:${windowLabel}` → LearnedLimit
  // Populated when 429 errors are detected; empty means no throttling
  private learnedLimits = new Map<string, LearnedLimit>()

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

  // Persistent store for learned rate limits — optional; in-memory is source-of-truth
  private rateLimitStore: RateLimitStore | undefined

  constructor(
    wrapped: IProvider,
    logger: ILogger,
    bus: IEventBus,
    providerConfig?: Partial<ProviderConfig>,
  ) {
    this.wrapped = wrapped
    this.inner = wrapped
    this.id = wrapped.id
    this.models = wrapped.models
    this.logger = logger.child(`provider:${wrapped.id}`)
    this.bus = bus

    const defaults = DEFAULT_PROVIDER_CONFIGS[wrapped.id] ?? {
      errorCooldownMs: DEFAULT_PROVIDER_CONFIGS.default.errorCooldownMs,
    }
    this.config = { ...defaults, ...providerConfig }
  }

  /**
   * Set the budget tracker for recording metered requests.
   * Allows deferred wiring after provider construction.
   */
  setBudgetTracker(tracker: BudgetTracker): void {
    this.budgetTracker = tracker
  }

  /**
   * Attach a persistent store and immediately warm up learnedLimits from it.
   * Call this right after construction, before the first request.
   */
  setRateLimitStore(store: RateLimitStore): void {
    this.rateLimitStore = store
    this.loadFromStore()
  }

  /**
   * Populate learnedLimits from the persistent store.
   * Existing in-memory entries are overwritten so the persisted values win on startup.
   */
  private loadFromStore(): void {
    if (!this.rateLimitStore) return
    const entries = this.rateLimitStore.loadForProvider(this.id)
    if (entries.length === 0) return

    for (const entry of entries) {
      const key = `${entry.model}:${entry.windowLabel}`
      this.learnedLimits.set(key, {
        observedCount: entry.observedCount,
        safeCount:     entry.safeCount,
        lastHitAt:     entry.lastHitAt,
        hitCount:      entry.hitCount,
      })
    }
    this.logger.info('Rate limits restored from store', {
      count: entries.length,
      models: [...new Set(entries.map(e => e.model))],
    })
  }

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

    const dedupeDisabled = opts.allowConcurrent === true || opts.dedupe === false
    if (!dedupeDisabled) {
      const existing = this.inFlight.get(sessionId)
      if (existing) {
        // If the existing request was already aborted (e.g., timed out),
        // clean up the stale entry and allow the new request to proceed.
        // This prevents dedup from permanently blocking a session when the
        // abort signal didn't propagate cleanly through the async iterator.
        if (existing.aborted) {
          this.logger.info(`[dedup] Clearing stale aborted request ${existing.id.slice(-8)} for session ${sessionId.slice(-8)}`)
          this.inFlight.delete(sessionId)
        } else {
          this.metrics.deduplicated++
          this.logger.warn(`[dedup] Session ${sessionId.slice(-8)} already has in-flight request ${existing.id.slice(-8)}`)
      this.bus.emit({
        type: 'provider:deduplicated',
        providerId: this.id,
        sessionId,
        existingRequestId: existing.id,
      })
          throw new Error(`Request already in progress for session ${sessionId.slice(-8)}`)
        }
      }
    } else {
      // Dedupe intentionally disabled for this call
      try { this.logger.debug(`[dedup] allowConcurrent set — skipping dedup for session ${sessionId.slice(-8)}`) } catch { }
    }

    const rawModel = opts.model || this.models[0]

    // Retry loop — transparent to callers. Retries on:
    //   1. Pre-check: learned limit not yet cleared (waits retryAfterMs, then re-checks)
    //   2. Live 429: provider returns 429 before any chunks yielded (waits, then retries)
    // After MAX_RATE_LIMIT_RETRIES retries the error is surfaced to the caller.
    for (let attempt = 0; ; attempt++) {

      // Pre-check: have we already learned this model's rate ceiling?
      const rateLimitResult = this.checkRateLimit(rawModel)
      if (!rateLimitResult.allowed) {
        this.metrics.rateLimited++
        this.logger.warn(`[ratelimit] ${this.id}/${rawModel} at learned limit (${rateLimitResult.windowLabel}), must wait ${rateLimitResult.retryAfterMs}ms`)
        this.bus.emit({
          type: 'provider:rate_limited',
          providerId: this.id,
          sessionId,
          retryAfterMs: rateLimitResult.retryAfterMs,
        })
        // Learned limit from 429 history: wait for the window to clear, then retry
        if (attempt >= MAX_RATE_LIMIT_RETRIES) {
          throw new Error(`Rate limited: gave up after ${attempt} retries, retry after ${rateLimitResult.retryAfterMs}ms`)
        }
        this.logger.info(`[ratelimit] waiting ${rateLimitResult.retryAfterMs}ms then retrying (attempt ${attempt + 1}/${MAX_RATE_LIMIT_RETRIES})`)
        await sleepWithAbort(rateLimitResult.retryAfterMs, signal)
        continue
      }

      // Pre-check: are we still in an error cooldown?
      // Error cooldown is a circuit breaker for non-429 failures — throw immediately.
      const cooldownRemaining = this.checkErrorCooldown()
      if (cooldownRemaining > 0) {
        throw new Error(`Provider cooling down after errors: retry after ${cooldownRemaining}ms`)
      }

      // === One attempt ===
      const requestId = `${this.id}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
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
      this.recordRequest(rawModel)

      // Normalize model reporting to include provider prefix when not already present
      let reportedModel = entry.model || ''
      try {
        if (reportedModel && !reportedModel.includes('/')) reportedModel = `${this.id}/${reportedModel}`
      } catch (err) { /* ignore */ }
      // Persist the normalized model for downstream diagnostics
      entry.model = reportedModel

      this.logger.info(`[request] ${requestId.slice(-12)} session=${sessionId.slice(-8)} model=${reportedModel}${attempt > 0 ? ` (retry ${attempt})` : ''}`)
      writeThoughtRequestLog({
        requestId,
        provider: this.id,
        model: reportedModel,
        sessionId,
        messages,
        systemPrompt: opts.systemPrompt,
        toolCount: opts.tools?.length ?? 0,
        attachmentCount: Array.isArray(attachments) ? attachments.length : 0,
        timeoutMs: (opts as { timeoutMs?: number }).timeoutMs ?? DEFAULT_PER_REQUEST_TIMEOUT_MS,
      })
      this.bus.emit({
        type: 'provider:request_start',
        providerId: this.id,
        requestId,
        sessionId,
        source: opts?.source ?? 'unknown',
        trigger: opts?.trigger,
        model: rawModel,
        messageCount: messages.length,
        timestamp: new Date(),
      })
      this.bus.emit({
        type: 'provider:request_prompt',
        providerId: this.id,
        requestId,
        sessionId,
        source: opts?.source ?? 'unknown',
        messages: messages.map(m => ({
          role: m.role,
          content: typeof m.content === 'string' ? m.content : JSON.stringify(m.content),
        })),
        systemPrompt: opts.systemPrompt,
        timestamp: new Date(),
      })

      let completed = false
      let inputTokens = 0
      let chunksYielded = 0
      let got429 = false

      // Activity-based timeout: resets on each streaming chunk, fires only on genuine stalls
      const inactivityTimeoutMs = (opts as { inactivityTimeoutMs?: number }).inactivityTimeoutMs ?? DEFAULT_INACTIVITY_TIMEOUT_MS
      const controller = new AbortController()
      const activityTimeout = new ActivityTimeout({
        inactivityMs: inactivityTimeoutMs,
        label: `provider:${this.id}/${reportedModel}`,
        parentSignal: signal,
      })

      try {
        try {
          inputTokens = await this.wrapped.countTokens(messages)
        } catch {
          // Best-effort estimate only; streaming providers may still report more
          // accurate structured usage that should override this fallback upstream.
        }

        signalPromise(activityTimeout.signal).then(() => {
          try {
            const reason = activityTimeout.reason
            entry.error = reason === 'inactivity'
              ? `stream stalled - no activity for ${activityTimeout.silentMs}ms`
              : `aborted by caller`
            entry.aborted = true
            this.metrics.totalErrors++
            this.consecutiveErrors++
            this.lastErrorAt = Date.now()
            this.bus.emit({ type: 'provider:request_timeout', providerId: this.id, requestId, sessionId, timeoutMs: inactivityTimeoutMs, reason: reason ?? undefined })
            this.logger.warn(`[timeout] ${requestId.slice(-12)} ${entry.error} - provider:${this.id}/${reportedModel}`)
            writeThoughtResultLog('● THOUGHT  timeout', {
              requestId,
              provider: this.id,
              model: reportedModel,
              sessionId,
              error: entry.error,
            })
            controller.abort()
          } catch { /* ignore errors in timeout handler */ }
        }).catch(() => { })
        // Use 'as any' to pass attachments (not in IProvider interface but supported by implementations)
        const stream = (this.wrapped as any).complete(messages, opts, attachments, controller.signal)
        for await (const chunk of stream) {
          // Track tokens from chunk
          if (chunk.tokensUsed) {
            entry.tokensUsed = chunk.tokensUsed
          } else if (chunk.type === 'token' && chunk.text) {
            entry.tokensUsed += Math.ceil(chunk.text.length / 4)
          }

          chunksYielded++
          activityTimeout.touch()

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
        if (err instanceof Error && err.name === 'AbortError' && entry.error && entry.error.startsWith('timeout')) {
          // keep entry.error
        } else {
          entry.error = err instanceof Error ? err.message : String(err)
        }

        // Only increment error metrics if we're not retrying (avoid double-counting)
        const isRetryable429 = entry.error && this.isRateLimitError(entry.error) && chunksYielded === 0 && attempt < MAX_RATE_LIMIT_RETRIES
        if (!isRetryable429) {
          this.metrics.totalErrors++
          this.consecutiveErrors++
          this.lastErrorAt = Date.now()
        }

        this.logger.error(`[error] ${requestId.slice(-12)}: ${entry.error}${isRetryable429 ? ' (will retry)' : ''}`)
        writeThoughtResultLog('● THOUGHT  error', {
          requestId,
          provider: this.id,
          model: reportedModel,
          sessionId,
          error: entry.error,
        })
        this.bus.emit({
          type: 'provider:request_error',
          providerId: this.id,
          requestId,
          sessionId,
          source: opts?.source ?? 'unknown',
          trigger: opts?.trigger,
          model: rawModel,
          error: entry.error,
          consecutiveErrors: this.consecutiveErrors,
          durationMs: Date.now() - entry.startedAt,
          timestamp: new Date(),
        })

        // Adaptive rate limit learning: if this looks like a rate limit error,
        // record the current request rate and learn the limit for this model.
        // Also set got429 to trigger a transparent retry if no chunks were yielded.
        if (entry.error && this.isRateLimitError(entry.error)) {
          this.onRateLimitHit(rawModel)
          if (chunksYielded === 0 && attempt < MAX_RATE_LIMIT_RETRIES) {
            got429 = true
          }
        }

        if (!got429) throw err

      } finally {
        activityTimeout.dispose()

        entry.completedAt = Date.now()
        this.inFlight.delete(sessionId)
        this.metrics.totalRequests++

        this.metrics.totalTokens += entry.tokensUsed

        const duration = entry.completedAt - entry.startedAt
        this.logger.info(
          `[complete] ${requestId.slice(-12)} ${completed ? 'OK' : got429 ? 'RETRY' : 'ERR'} ` +
          `tokens=${entry.tokensUsed} duration=${duration}ms`
        )
        writeThoughtResultLog('▸ THOUGHT  complete', {
          requestId,
          provider: this.id,
          model: reportedModel,
          sessionId,
          status: completed && !entry.error ? 'ok' : got429 ? 'retry' : 'error',
          tokensUsed: entry.tokensUsed,
          durationMs: duration,
          error: entry.error,
        })

        this.bus.emit({
          type: 'provider:request_end',
          providerId: this.id,
          requestId,
          sessionId,
          source: opts?.source ?? 'unknown',
          trigger: opts?.trigger,
          model: rawModel,
          tokensUsed: { input: inputTokens, output: entry.tokensUsed, thinking: 0 },
          durationMs: duration,
          error: entry.error,
          timestamp: new Date(),
        })

        // Record against budget tracker if wired (only counts metered models)
        if (this.budgetTracker && !entry.error) {
          const model = opts.model || 'unknown'
          this.budgetTracker.recordRequest(`${this.id}/${model}`)
        }
      }

      if (!got429) return  // success — exit retry loop

      // Live 429 retry: wait for the window to clear, then go around again
      const retryCheck = this.checkRateLimit(rawModel)
      const waitMs = retryCheck.retryAfterMs > 0 ? retryCheck.retryAfterMs : 5_000
      this.logger.info(`[ratelimit] live 429, waiting ${waitMs}ms before retry ${attempt + 1}/${MAX_RATE_LIMIT_RETRIES}`)
      await sleepWithAbort(waitMs, signal)
    }
  }

  async countTokens(messages: Message[]): Promise<number> {
    return this.wrapped.countTokens(messages)
  }

  async ping(_signal?: AbortSignal): Promise<boolean> {
    // Don't rate-limit pings — they're lightweight health checks
    return this.wrapped.ping()
  }
  // Public metrics API

  getMetrics() {
    return {
      ...this.metrics,
      inFlightCount: this.inFlight.size,
      consecutiveErrors: this.consecutiveErrors,
      currentRates: this.calculateCurrentRates(),
      learnedLimits: Object.fromEntries(this.learnedLimits),
      globalConfig: { ...this.config },
    }
  }

  getStats(): unknown {
    const wrapped = this.wrapped as unknown as { getStats?: () => unknown }
    if (typeof wrapped.getStats === 'function') {
      return wrapped.getStats()
    }
    return null
  }

  getActiveCount(): number {
    const wrapped = this.wrapped as unknown as { getActiveCount?: () => number }
    if (typeof wrapped.getActiveCount === 'function') {
      return wrapped.getActiveCount()
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
      this.logger.info('Error state cleared')
      this.bus.emit({
        type: 'provider:error_reset',
        providerId: this.id,
      })
    }
  }

  resetRateLimitHistory(): void {
    this.modelHistory.clear()
    this.learnedLimits.clear()
    this.rateLimitStore?.clearProvider(this.id)
    this.logger.info('Rate limit history and learned limits cleared')
  }

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
    this.logger.info('All state cleared')
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
      })
      return true
    }
    return false
  }

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

  /**
   * Check learned rate limits across all timescales.
   * Returns whether allowed and, if blocked, which window triggered it.
   */
  private checkRateLimit(model: string): { allowed: boolean; reason?: 'learned'; retryAfterMs: number; windowLabel?: WindowLabel } {
    // Check each timescale for learned limits
    const now = Date.now()
    const history = this.modelHistory.get(model) || []

    for (const { label, windowMs } of RATE_WINDOWS) {
      const key = `${model}:${label}`
      const limit = this.learnedLimits.get(key)
      if (!limit) continue

      // Count requests in this window
      const windowStart = now - windowMs
      const count = this.countInWindow(history, windowStart)

      // Probe-up: if we haven't been hit in 5× this window duration, relax slightly
      const timeSinceHit = now - limit.lastHitAt
      let effectiveSafeCount = limit.safeCount
      if (timeSinceHit > PROBE_UP_CLEAN_WINDOWS * windowMs) {
        effectiveSafeCount = Math.min(
          Math.ceil(limit.safeCount * PROBE_UP_FACTOR),
          limit.observedCount // Never exceed what originally triggered the 429
        )
      }

      if (count >= effectiveSafeCount) {
        // Estimate when the oldest relevant request will fall out of the window
        const oldestInWindow = this.findOldestInWindow(history, windowStart)
        const retryAfterMs = oldestInWindow
          ? Math.max(0, (oldestInWindow + windowMs) - now) + 100
          : 1000
        return { allowed: false, reason: 'learned', retryAfterMs, windowLabel: label }
      }
    }

    return { allowed: true, retryAfterMs: 0 }
  }

  private recordRequest(model: string): void {
    const now = Date.now()
    let history = this.modelHistory.get(model)
    if (!history) {
      history = []
      this.modelHistory.set(model, history)
    }
    history.push(now)

    // Prune timestamps older than the longest window (1 hour)
    const maxWindow = RATE_WINDOWS[RATE_WINDOWS.length - 1].windowMs
    const cutoff = now - maxWindow
    // Linear scan is fine for typical sizes
    while (history.length > 0 && history[0] < cutoff) {
      history.shift()
    }
  }

  /**
   * Detect rate limit errors from error strings.
   * Covers common patterns across providers.
   */
  private isRateLimitError(error: string): boolean {
    return /429|rate.?limit|rate_limit_exceeded|resource.?exhausted|quota.?exceeded|throttl/i.test(error)
  }

  /**
   * Called when a rate limit (429) is detected for a model.
   * Snapshots the current request count at all timescales and learns the limit.
   */
  private onRateLimitHit(model: string): void {
    const now = Date.now()
    const history = this.modelHistory.get(model) || []

    const learnedWindows: Array<{ label: WindowLabel; observedCount: number; safeCount: number }> = []

    for (const { label, windowMs } of RATE_WINDOWS) {
      const key = `${model}:${label}`
      const windowStart = now - windowMs
      const observedCount = this.countInWindow(history, windowStart)

      // Only learn if there were actually requests in this window
      if (observedCount <= 0) continue

      const newSafeCount = Math.max(1, Math.floor(observedCount * SAFETY_MARGIN))
      const existing = this.learnedLimits.get(key)

      if (existing) {
        // Tighten: take the minimum, then apply tighten factor
        existing.safeCount = Math.max(1, Math.min(
          existing.safeCount,
          Math.floor(newSafeCount * TIGHTEN_FACTOR)
        ))
        existing.observedCount = Math.min(existing.observedCount, observedCount)
        existing.lastHitAt = now
        existing.hitCount++
      } else {
        this.learnedLimits.set(key, {
          observedCount,
          safeCount: newSafeCount,
          lastHitAt: now,
          hitCount: 1,
        })
      }

      learnedWindows.push({ label, observedCount, safeCount: this.learnedLimits.get(key)!.safeCount })

      // Persist the updated entry immediately
      if (this.rateLimitStore) {
        const stored = this.learnedLimits.get(key)!
        this.rateLimitStore.save({
          providerId:    this.id,
          model,
          windowLabel:   label,
          observedCount: stored.observedCount,
          safeCount:     stored.safeCount,
          lastHitAt:     stored.lastHitAt,
          hitCount:      stored.hitCount,
          updatedAt:     now,
        })
      }
    }

    if (learnedWindows.length > 0) {
      this.logger.info(`[rate-learn] ${this.id}/${model} hit rate limit, learned limits:`, {
        windows: learnedWindows,
      })

      this.bus.emit({
        type: 'provider:rate_learned',
        providerId: this.id,
        model,
        learnedWindows,
        timestamp: new Date(),
      })
    }
  }

  private countInWindow(history: number[], windowStart: number): number {
    let count = 0
    for (let i = history.length - 1; i >= 0; i--) {
      if (history[i] >= windowStart) count++
      else break // history is sorted, no need to continue
    }
    return count
  }

  private findOldestInWindow(history: number[], windowStart: number): number | undefined {
    for (let i = 0; i < history.length; i++) {
      if (history[i] >= windowStart) return history[i]
    }
    return undefined
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

  private calculateCurrentRates(): Record<string, Record<string, number>> {
    const now = Date.now()
    const rates: Record<string, Record<string, number>> = {}

    for (const [model, history] of this.modelHistory) {
      rates[model] = {}
      for (const { label, windowMs } of RATE_WINDOWS) {
        const windowStart = now - windowMs
        rates[model][label] = this.countInWindow(history, windowStart)
      }
    }
    return rates
  }
}

/**
 * @dep callers: centralized-provider.test.ts (tests/centralized-provider.test.ts), createProviders (core/providers/index.ts)
 * @dep calls: getConfiguredProviderConfig, setBudgetTracker, setRateLimitStore
 * @dep module: Providers
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function wrapProvidersWithCentralized(
  providers: Map<string, IProvider>,
  logger: ILogger,
  bus: IEventBus,
  config?: IConfig,
  budgetTracker?: BudgetTracker,
  rateLimitStore?: RateLimitStore,
): Map<string, CentralizedProvider> {
  const wrapped = new Map<string, CentralizedProvider>()
  for (const [id, provider] of providers) {
    const cp = new CentralizedProvider(provider, logger, bus, getConfiguredProviderConfig(config, id))
    if (budgetTracker) cp.setBudgetTracker(budgetTracker)
    if (rateLimitStore) cp.setRateLimitStore(rateLimitStore)
    wrapped.set(id, cp)
  }
  logger.info('Providers wrapped with adaptive rate limiting', {
    providerCount: wrapped.size,
    defaults: DEFAULT_PROVIDER_CONFIGS,
    rateLimitStorePersisted: !!rateLimitStore,
  })
  return wrapped
}
