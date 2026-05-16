/**
 * Reranker service — wraps zerank-server /v1/rerank or vLLM /v1/completions.
 * Uses Qwen3-based decoder (yes/no logit scoring) to precisely score
 * query–document pairs for the final stage of the retrieval pipeline.
 *
 * Supports two backends:
 *   1. zerank-server — POST /v1/rerank (GGUF or HF Transformers)
 *   2. vLLM — POST /v1/completions with logprobs (when /v1/rerank unavailable)
 *
 * Singleton: import { getRerankerService } from './reranker-service.js'
 */

import type { ILogger } from '../../../types/interfaces.js'

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
  /** Cached: true if backend is vLLM (not zerank-server) */
  private isVllm: boolean | null = null

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

    // Circuit breaker check
    if (this.cb.openUntil > Date.now()) {
      this.logger.debug('RerankerService: circuit breaker open, skipping', {
        reopensIn: `${Math.round((this.cb.openUntil - Date.now()) / 1000)}s`,
      })
      return []
    }

    // Detect backend type on first call (or after restart)
    if (this.isVllm === null) {
      this.isVllm = await this.probeVllm()
      this.logger.debug('RerankerService: backend probe', { isVllm: this.isVllm })
    }

    try {
      const results = this.isVllm
        ? await this.rerankVllm(query, documents)
        : await this.rerankZerank(query, documents, topN)

      if (results.length) {
        // Reset circuit breaker on success
        this.cb.failures = 0
        this.cb.trippedLogged = false
      }

      // Sort by relevance (highest first) and apply topN
      results.sort((a, b) => b.relevanceScore - a.relevanceScore)
      const limit = topN ?? documents.length
      return results.slice(0, limit)
    } catch (err) {
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

    return []  // Graceful degradation
  }

  /** Probe whether the backend is vLLM (returns 400 "does not support" for /v1/rerank). */
  private async probeVllm(): Promise<boolean> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 5000)
    try {
      const res = await fetch(`${this.serverUrl}/v1/rerank`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'probe', documents: ['probe'], top_n: 1 }),
        signal: controller.signal,
      })
      clearTimeout(timer)
      const body = await res.text()
      if (body.includes('does not support')) return true
      return false
    } catch {
      clearTimeout(timer)
      return false
    }
  }

  /** Use zerank-server /v1/rerank endpoint — cross-encoder (no Qwen3 templates needed). */
  private async rerankZerank(query: string, documents: string[], topN?: number): Promise<RerankResult[]> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this.timeoutMs)

    // Cross-encoder takes raw (query, doc) pairs — no LLM prompt formatting.
    // Our BGE bridge strips Qwen3 templates anyway, so sending raw text
    // avoids the instruction noise that dilutes cross-encoder signal.
    try {
      const res = await fetch(`${this.serverUrl}/v1/rerank`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim(),
          documents: documents.map(d => d.trim()),
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

      return data.results.map(r => ({
        index: r.index,
        relevanceScore: r.relevance_score ?? 0,
      }))
    } catch (err) {
      clearTimeout(timer)
      throw err
    }
  }

  /** Use vLLM /v1/completions endpoint with logprobs. */
  private async rerankVllm(query: string, documents: string[]): Promise<RerankResult[]> {
    const results: RerankResult[] = []
    const instruction = 'Given a search query, retrieve relevant passages that answer the query'

    for (let i = 0; i < documents.length; i++) {
      const doc = documents[i]
      const prompt = (
        '<|im_start|>system\n'
        + 'Judge whether the Document meets the requirements based on the Query '
        + 'and the Instruct provided. Note that the answer can only be "yes" or "no".'
        + '<|im_end|>\n<|im_start|>user\n'
        + `<Instruct>: ${instruction}\n`
        + `<Query>: ${query.trim()}\n`
        + `<Document>: ${doc.trim()}`
        + '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n'
      )

      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), this.timeoutMs)

      try {
        const res = await fetch(`${this.serverUrl}/v1/completions`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: 'Qwen/Qwen3-Reranker-0.6B',
            prompt,
            max_tokens: 1,
            temperature: 0,
            logprobs: 10,
          }),
          signal: controller.signal,
        })
        clearTimeout(timer)

        if (!res.ok) {
          this.logger.debug('RerankerService: vLLM non-OK response', { status: res.status, index: i })
          continue
        }

        const data = await res.json() as {
          choices?: Array<{
            logprobs?: {
              top_logprobs?: Array<Record<string, number>>
            }
          }>
        }

        const topLogprobs = data.choices?.[0]?.logprobs?.top_logprobs?.[0]
        if (!topLogprobs) {
          this.logger.debug('RerankerService: vLLM missing logprobs', { index: i })
          continue
        }

        // Find best logprob for yes/no variants (case-insensitive)
        let yesLogprob = -Infinity
        let noLogprob = -Infinity
        for (const [token, logprob] of Object.entries(topLogprobs)) {
          const lower = token.toLowerCase().trim()
          if (lower === 'yes' && logprob > yesLogprob) yesLogprob = logprob
          if (lower === 'no' && logprob > noLogprob) noLogprob = logprob
        }

        if (yesLogprob === -Infinity && noLogprob === -Infinity) {
          this.logger.debug('RerankerService: vLLM no yes/no in logprobs', { index: i, tokens: Object.keys(topLogprobs) })
          continue
        }

        // Default missing side to very low probability
        if (yesLogprob === -Infinity) yesLogprob = -20
        if (noLogprob === -Infinity) noLogprob = -20

        // sigmoid(yes - no) in log space = 1 / (1 + exp(no - yes))
        const score = 1.0 / (1.0 + Math.exp(noLogprob - yesLogprob))

        results.push({ index: i, relevanceScore: score })
      } catch (err) {
        clearTimeout(timer)
        this.logger.debug('RerankerService: vLLM request failed', { error: String(err), index: i })
      }
    }

    return results
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
