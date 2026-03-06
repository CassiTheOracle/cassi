/**
 * Reranker service — wraps zerank-server /v1/rerank endpoint.
 * Uses zerank-2 (Qwen3-based decoder, HF Transformers yes/no logit scoring)
 * to precisely score query–document pairs for the final stage of the
 * retrieval pipeline. See bin/zerank-server for the server implementation.
 *
 * Singleton: import { getRerankerService } from './reranker-service.js'
 */

import type { ILogger } from '../../../types/interfaces.js'

// ── Configuration ──────────────────────────────────────────────────────────
const RERANKER_SERVER_URL = process.env.RERANKER_SERVER_URL || 'http://localhost:18821'
// zerank-2 on CPU: ~100–500ms/doc; 30s covers a batch of 50 docs at worst-case CPU speeds.
// On GPU (ROCm/CUDA) this is typically <1s total. Override with RERANKER_TIMEOUT_MS.
const RERANKER_TIMEOUT_MS = Number(process.env.RERANKER_TIMEOUT_MS || '30000')

// Circuit breaker
const CB_MAX_FAILURES = 3
const CB_COOLDOWN_MS = 60_000

export interface RerankResult {
  /** Original index in the documents array */
  index: number
  /** Relevance score (higher = more relevant; may be negative) */
  relevanceScore: number
}

export interface RerankerServiceConfig {
  serverUrl?: string
  timeoutMs?: number
}

export class RerankerService {
  private logger: ILogger
  private serverUrl: string
  private timeoutMs: number
  private cb = { failures: 0, openUntil: 0 }

  constructor(logger: ILogger, config?: RerankerServiceConfig) {
    this.logger = logger.child?.('reranker-service') ?? logger
    this.serverUrl = config?.serverUrl || RERANKER_SERVER_URL
    this.timeoutMs = config?.timeoutMs || RERANKER_TIMEOUT_MS
    this.logger.info('RerankerService initialized', { serverUrl: this.serverUrl })
  }

  /**
   * Rerank documents by relevance to a query.
   * Returns results sorted by relevance (highest first).
   * Returns empty array if server is unavailable (graceful degradation).
   *
   * @param query  - The search query
   * @param documents - Candidate document texts
   * @param topN - Max results to return (default: all)
   */
  async rerank(query: string, documents: string[], topN?: number): Promise<RerankResult[]> {
    if (!documents.length || !query.trim()) return []

    // Circuit breaker check
    if (this.cb.openUntil > Date.now()) {
      this.logger.debug('RerankerService: circuit breaker open, skipping', {
        reopensIn: `${Math.round((this.cb.openUntil - Date.now()) / 1000)  }s`,
      })
      return []
    }

    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), this.timeoutMs)

      const res = await fetch(`${this.serverUrl}/v1/rerank`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          documents,
          top_n: topN ?? documents.length,
        }),
        signal: controller.signal,
      })
      clearTimeout(timer)

      if (res.ok) {
        this.cb.failures = 0
        const data = await res.json() as any
        if (Array.isArray(data?.results)) {
          return data.results
            .map((r: any) => ({
              index: r.index ?? 0,
              relevanceScore: r.relevance_score ?? 0,
            }))
            .sort((a: RerankResult, b: RerankResult) => b.relevanceScore - a.relevanceScore)
        }
      }
      this.logger.warn('RerankerService: non-OK response', { status: res.status })
    } catch (err) {
      this.cb.failures++
      if (this.cb.failures >= CB_MAX_FAILURES) {
        this.cb.openUntil = Date.now() + CB_COOLDOWN_MS
        this.logger.warn('RerankerService: circuit breaker TRIPPED', {
          failures: this.cb.failures, cooldownMs: CB_COOLDOWN_MS,
        })
        this.cb.failures = 0
      }
      this.logger.debug('RerankerService: request failed', { error: String(err) })
    }

    return []  // Graceful degradation — caller uses embedding scores alone
  }

  /** Check if the reranker server is available (circuit breaker not tripped). */
  get available(): boolean {
    return this.cb.openUntil <= Date.now()
  }
}

// ── Singleton ────────────────────────────────────────────────────────────────
let _instance: RerankerService | null = null

/** Get the shared RerankerService singleton. */
export function getRerankerService(logger?: ILogger): RerankerService {
  if (!_instance) {
    const fallbackLogger: ILogger = {
      debug() {}, info() {}, warn() {}, error() {},
      child() { return this },
    }
    _instance = new RerankerService(logger || fallbackLogger)
  }
  return _instance
}

/** Reset the singleton (useful for tests). */
export function resetRerankerService(): void {
  _instance = null
}
