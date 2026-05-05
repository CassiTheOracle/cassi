/**
 * Reranker service — wraps zerank-server /v1/rerank endpoint.
 * Uses zerank-2 (Qwen3-based decoder, yes/no logit scoring via
 * sigmoid(logit_Yes / 5.0)) to precisely score query–document pairs
 * for the final stage of the retrieval pipeline.
 *
 * The zerank-server backend supports two modes:
 *   1. GGUF via llama-cpp-python (default) — zerank-server --gguf <path>
 *   2. HuggingFace Transformers (legacy) — zerank-server --model zerank-2
 *
 * Both backends expose the same /v1/rerank HTTP API, so this client
 * works with either backend transparently.
 *
 * See bin/zerank-server for the server implementation.
 *
 * Singleton: import { getRerankerService } from './reranker-service.js'
 */

import type { ILogger } from '../../../types/interfaces.js'
import { getInferenceStackLauncher, MANAGED_RERANKER } from './inference-stack-launcher.js'

const RERANKER_SERVER_URL = process.env.RERANKER_SERVER_URL || 'http://127.0.0.1:18821'
// zerank-2 with GGUF on GPU: typically <50ms/doc; 30s covers worst-case batches.
// Override with RERANKER_TIMEOUT_MS.
const RERANKER_TIMEOUT_MS = Number(process.env.RERANKER_TIMEOUT_MS || '30000')

// Circuit breaker
const CB_MAX_FAILURES = 3
const CB_COOLDOWN_MS = 60_000

export interface RerankResult {
  /** Original index in the documents array */
  index: number
  /** Relevance score — sigmoid(Yes_logit / 5.0), range [0, 1] */
  relevanceScore: number
}

export class RerankerService {
  private logger: ILogger
  private serverUrl: string
  private timeoutMs: number
  private cb = { failures: 0, openUntil: 0, trippedLogged: false }

  constructor(logger: ILogger) {
    this.logger = logger.child?.('reranker-service') ?? logger
    this.serverUrl = RERANKER_SERVER_URL
    this.timeoutMs = RERANKER_TIMEOUT_MS
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

    // Demand-load: restart the server if it was idle-unloaded
    const launcher = getInferenceStackLauncher()
    if (launcher) {
      const restarted = await launcher.ensureRunning(MANAGED_RERANKER)
      if (restarted) this.cb = { failures: 0, openUntil: 0, trippedLogged: false }
    }

    // Circuit breaker check
    if (this.cb.openUntil > Date.now()) {
      this.logger.debug('RerankerService: circuit breaker open, skipping', {
        reopensIn: `${Math.round((this.cb.openUntil - Date.now()) / 1000)}s`,
      })
      return []
    }

    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this.timeoutMs)

    // Qwen3-Reranker prompt formatting for vLLM
    const prefix = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
    const suffix = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n'
    const instruction = 'Given a search query, retrieve relevant passages that answer the query'

    const formattedQuery = `${prefix}<Instruct>: ${instruction}\n<Query>: ${query.trim()}\n`
    const formattedDocs = documents.map(doc => `<Document>: ${doc.trim()}${suffix}`)

    try {
      const res = await fetch(`${this.serverUrl}/v1/rerank`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: formattedQuery,
          documents: formattedDocs,
          top_n: topN ?? documents.length,
        }),
        signal: controller.signal,
      })
      clearTimeout(timer)

      if (!res.ok) {
        this.logger.debug('RerankerService: non-OK response', { status: res.status })
        return []
      }

      const data = await res.json() as {
        results?: Array<{ index: number; relevance_score: number }>
      }

      if (!data.results?.length) return []

      // Reset circuit breaker on success
      this.cb.failures = 0
      this.cb.trippedLogged = false
      if (launcher) launcher.notifyActivity(MANAGED_RERANKER)

      return data.results.map(r => ({
        index: r.index,
        relevanceScore: r.relevance_score ?? 0,
      }))
    } catch (err) {
      clearTimeout(timer)
      this.cb.failures++
      if (this.cb.failures >= CB_MAX_FAILURES) {
        this.cb.openUntil = Date.now() + CB_COOLDOWN_MS
        if (!this.cb.trippedLogged) {
          this.logger.warn('RerankerService: circuit breaker TRIPPED', {
            failures: this.cb.failures, cooldownMs: CB_COOLDOWN_MS,
          })
          this.cb.trippedLogged = true
        }
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

let _instance: RerankerService | null = null

/** Get the shared RerankerService singleton. */
/**
 * @dep callers: scoreForOpenCode (core/intelligence/context-window/index.ts), build (core/intelligence/context-window/index.ts), search (core/intelligence/memory/archive-reader.ts), smartRecall (core/intelligence/memory/index.ts), search (core/intelligence/memory/index.ts) [+1]
 * @dep module: Memory
 * @dep risk: MEDIUM | 6 callers, 0 flows, 1 module
 */

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
