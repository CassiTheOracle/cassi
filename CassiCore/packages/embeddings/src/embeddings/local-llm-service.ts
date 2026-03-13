/**
 * LocalLLMService — thin OpenAI-compatible client for the local generative
 * model (llama.cpp server running Qwen3.5-0.8B or similar).
 *
 * Singleton pattern matching EmbeddingService / RerankerService.
 *
 * Uses the OpenAI-compatible /v1/chat/completions endpoint provided natively
 * by llama-server (no adapter needed).
 *
 * Default sampling params follow Qwen3.5 best practices for non-thinking
 * (concise extraction) tasks.
 */

import type { ILogger } from '../../../types/interfaces.js'
import { getInferenceStackLauncher, MANAGED_GENERATIVE } from './inference-stack-launcher.js'

// ── Configuration ───────────────────────────────────────────────────────────
const DEFAULT_SERVER_URL = 'http://127.0.0.1:18822'
const DEFAULT_TIMEOUT_MS = 5000
const DEFAULT_MAX_TOKENS = 512
const DEFAULT_TEMPERATURE = 0

// Circuit breaker — avoid hammering a dead server
const CB_MAX_FAILURES = 5
const CB_COOLDOWN_MS = 30_000

// Health check cache — avoid flooding /health
const HEALTH_CACHE_TTL_MS = 10_000

// ── Types ───────────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface LocalLLMGenerateOpts {
  /** Max tokens to generate. Default: 256 */
  maxTokens?: number
  /** Sampling temperature. Default: 0.7 */
  temperature?: number
  /** Top-p nucleus sampling. Default: 0.8 */
  topP?: number
  /** Top-k sampling. Default: 20 */
  topK?: number
  /** Presence penalty. Default: 1.5 */
  presencePenalty?: number
  /** Request timeout in ms. Default: 3000 */
  timeoutMs?: number
  /** Abort signal for cancellation */
  signal?: AbortSignal
}

export interface LocalLLMServiceConfig {
  serverUrl?: string
  timeoutMs?: number
  maxTokens?: number
  temperature?: number
}

// ── Service ─────────────────────────────────────────────────────────────────

export class LocalLLMService {
  private logger: ILogger
  private serverUrl: string
  private defaultTimeoutMs: number
  private defaultMaxTokens: number
  private defaultTemperature: number

  // Circuit breaker state
  private cbFailures = 0
  private cbOpenUntil = 0

  // Cached health check
  private healthCacheValue = false
  private healthCacheExpiry = 0

  constructor(logger: ILogger, config?: LocalLLMServiceConfig) {
    this.logger = logger.child?.('local-llm') ?? logger
    this.serverUrl = config?.serverUrl
      ?? process.env.LOCAL_LLM_URL
      ?? DEFAULT_SERVER_URL
    this.defaultTimeoutMs = config?.timeoutMs ?? DEFAULT_TIMEOUT_MS
    this.defaultMaxTokens = config?.maxTokens ?? DEFAULT_MAX_TOKENS
    this.defaultTemperature = config?.temperature ?? DEFAULT_TEMPERATURE
  }

  /**
   * Whether the local LLM server is believed to be available.
   * Uses a cached health check to avoid excessive polling.
   * Returns false when the circuit breaker is open.
   */
  get available(): boolean {
    // Circuit breaker check
    if (this.cbOpenUntil > Date.now()) return false

    // Return cached value if fresh
    if (Date.now() < this.healthCacheExpiry) return this.healthCacheValue

    // Trigger async health probe (returns stale value this call)
    this.probeHealth().catch(() => {})
    return this.healthCacheValue
  }

  /**
   * Generate text from the local model using OpenAI-compatible chat completions.
   *
   * @returns Generated text, or null if the server is unavailable / times out.
   */
  async generate(messages: ChatMessage[], opts?: LocalLLMGenerateOpts): Promise<string | null> {
    // Demand-load: restart the server if it was idle-unloaded
    const launcher = getInferenceStackLauncher()
    if (launcher) {
      const restarted = await launcher.ensureRunning(MANAGED_GENERATIVE)
      if (restarted) {
        this.cbFailures = 0
        this.cbOpenUntil = 0
      }
    }

    // Circuit breaker gate
    if (this.cbOpenUntil > Date.now()) {
      this.logger.debug('LocalLLMService: circuit breaker open, skipping')
      return null
    }

    const timeoutMs = opts?.timeoutMs ?? this.defaultTimeoutMs
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)

    // Chain external abort signal
    if (opts?.signal) {
      if (opts.signal.aborted) {
        clearTimeout(timer)
        return null
      }
      opts.signal.addEventListener('abort', () => controller.abort(), { once: true })
    }

    try {
      const body = {
        messages,
        max_tokens: opts?.maxTokens ?? this.defaultMaxTokens,
        temperature: opts?.temperature ?? this.defaultTemperature,
        top_p: opts?.topP ?? 0.8,
        top_k: opts?.topK ?? 20,
        presence_penalty: opts?.presencePenalty ?? 1.5,
        stream: false,
      }

      const startTime = Date.now()
      const res = await fetch(`${this.serverUrl}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
      clearTimeout(timer)

      if (!res.ok) {
        this.recordFailure()
        this.logger.warn('LocalLLMService: non-OK response', { status: res.status })
        return null
      }

      const data = await res.json() as any
      const text = data?.choices?.[0]?.message?.content ?? null

      // Reset circuit breaker on success
      this.cbFailures = 0
      this.cbOpenUntil = 0
      this.healthCacheValue = true
      this.healthCacheExpiry = Date.now() + HEALTH_CACHE_TTL_MS
      if (launcher) launcher.notifyActivity(MANAGED_GENERATIVE)

      const elapsed = Date.now() - startTime
      this.logger.debug('LocalLLMService: generation complete', {
        elapsed,
        tokens: data?.usage?.completion_tokens,
      })

      return typeof text === 'string' ? text.trim() : null
    } catch (err) {
      clearTimeout(timer)
      this.recordFailure()
      const isTimeout = String(err).includes('abort')
      this.logger.debug('LocalLLMService: generation failed', {
        error: isTimeout ? 'timeout' : String(err),
      })
      return null
    }
  }

  /**
   * Convenience: generate from a single user prompt with an optional system message.
   */
  async prompt(userPrompt: string, opts?: LocalLLMGenerateOpts & { system?: string }): Promise<string | null> {
    const messages: ChatMessage[] = []
    if (opts?.system) messages.push({ role: 'system', content: opts.system })
    messages.push({ role: 'user', content: userPrompt })
    return this.generate(messages, opts)
  }

  // ── Internal ────────────────────────────────────────────────────────────

  private recordFailure(): void {
    this.cbFailures++
    if (this.cbFailures >= CB_MAX_FAILURES) {
      this.cbOpenUntil = Date.now() + CB_COOLDOWN_MS
      this.healthCacheValue = false
      this.healthCacheExpiry = Date.now() + CB_COOLDOWN_MS
      this.logger.warn('LocalLLMService: circuit breaker opened', {
        failures: this.cbFailures,
        cooldownMs: CB_COOLDOWN_MS,
      })
    }
  }

  private async probeHealth(): Promise<void> {
    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 2000)
      const res = await fetch(`${this.serverUrl}/health`, {
        signal: controller.signal,
      })
      clearTimeout(timer)
      this.healthCacheValue = res.ok
      this.healthCacheExpiry = Date.now() + HEALTH_CACHE_TTL_MS
      if (res.ok) {
        this.cbFailures = 0
        this.cbOpenUntil = 0
      }
    } catch {
      this.healthCacheValue = false
      this.healthCacheExpiry = Date.now() + HEALTH_CACHE_TTL_MS
    }
  }
}

// ── Singleton ────────────────────────────────────────────────────────────────
let _instance: LocalLLMService | null = null

/** Get the shared LocalLLMService singleton. */
export function getLocalLLMService(logger?: ILogger): LocalLLMService {
  if (!_instance) {
    const fallbackLogger: ILogger = {
      debug() {}, info() {}, warn() {}, error() {},
      child() { return this },
    }
    _instance = new LocalLLMService(logger || fallbackLogger)
  }
  return _instance
}

/** Reset the singleton (useful for tests). */
export function resetLocalLLMService(): void {
  _instance = null
}
