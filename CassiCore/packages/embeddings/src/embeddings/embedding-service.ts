/**
 * Shared embedding service — wraps llama.cpp /v1/embeddings with caching,
 * circuit breaker, batching, and zembed-1 prompt formatting.
 *
 * Singleton: import { getEmbeddingService } from './embedding-service.js'
 */

import { createHash } from 'crypto'
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs'
import { join, dirname } from 'path'

import type { ILogger } from '../../../types/interfaces.js'
import { getInferenceStackLauncher, MANAGED_EMBEDDING } from './inference-stack-launcher.js'

// ── Configuration (env vars with sensible defaults) ──────────────────────────
const EMBEDDING_SERVER_URL = process.env.EMBEDDING_SERVER_URL || 'http://localhost:18820'
const EMBEDDING_MODEL_TAG = process.env.EMBEDDING_MODEL_TAG || 'zembed-1'
const EMB_TIMEOUT_MS = Number(process.env.EMBEDDING_TIMEOUT_MS || '5000')
const EMB_BATCH_SIZE = Number(process.env.EMBEDDING_BATCH_SIZE || '32')

// Cache tuning
const CACHE_MAX_ENTRIES = Number(process.env.EMB_CACHE_MAX_ENTRIES || '4000')
const CACHE_MAX_BYTES = Number(process.env.EMB_CACHE_MAX_BYTES || String(80 * 1024 * 1024))  // 80 MB
const CACHE_PERSIST_DEBOUNCE_MS = Number(process.env.EMB_PERSIST_DEBOUNCE_MS || '10000')

// Circuit breaker
const CB_MAX_FAILURES = 5
const CB_COOLDOWN_MS = 60_000

/** Embedding mode — determines the system prompt for asymmetric search */
export type EmbeddingMode = 'query' | 'document'

export interface EmbeddingServiceConfig {
  serverUrl?: string
  modelTag?: string
  timeoutMs?: number
  batchSize?: number
  cacheMaxEntries?: number
  cacheMaxBytes?: number
  cachePath?: string
  /** Disable file persistence (useful for tests) */
  noPersist?: boolean
}

export class EmbeddingService {
  private logger: ILogger
  private serverUrl: string
  private modelTag: string
  private timeoutMs: number
  private batchSize: number

  // ── LRU cache ──
  private cache = new Map<string, number[]>()
  private cacheOrder: string[] = []  // oldest → newest
  private cacheByteSize = 0
  private maxEntries: number
  private maxBytes: number

  // ── Persistence ──
  private persistPath: string
  private persistTimer: ReturnType<typeof setTimeout> | null = null
  private dirty = false
  private noPersist: boolean

  // ── Circuit breaker ──
  private cb = { failures: 0, openUntil: 0 }

  constructor(logger: ILogger, config?: EmbeddingServiceConfig) {
    this.logger = logger.child?.('embedding-service') ?? logger
    this.serverUrl = config?.serverUrl || EMBEDDING_SERVER_URL
    this.modelTag = config?.modelTag || EMBEDDING_MODEL_TAG
    this.timeoutMs = config?.timeoutMs || EMB_TIMEOUT_MS
    this.batchSize = config?.batchSize || EMB_BATCH_SIZE
    this.maxEntries = config?.cacheMaxEntries || CACHE_MAX_ENTRIES
    this.maxBytes = config?.cacheMaxBytes || CACHE_MAX_BYTES
    this.noPersist = config?.noPersist || false

    const home = process.env.HOME || require('os').homedir()
    this.persistPath = config?.cachePath || join(home, '.cassicore', 'data', 'embedding-cache.json')

    this.loadCache()
    this.logger.info('EmbeddingService initialized', {
      serverUrl: this.serverUrl,
      modelTag: this.modelTag,
      cachedEntries: this.cache.size,
    })
  }

  // ── Public API ───────────────────────────────────────────────────────────────

  /** Embed a single text. Returns null if server unavailable. */
  async embed(text: string, mode: EmbeddingMode = 'document'): Promise<number[] | null> {
    const key = this.cacheKey(text, mode)
    const cached = this.cache.get(key)
    if (cached) {
      this.touchLRU(key)
      return cached
    }

    const results = await this.fetchBatch([text], mode)
    const vec = results[0] ?? null
    if (vec) this.cacheSet(key, vec)
    return vec
  }

  /** Embed multiple texts in a single batch. Returns parallel array (null for failures). */
  async embedBatch(texts: string[], mode: EmbeddingMode = 'document'): Promise<Array<number[] | null>> {
    if (!texts.length) return []

    // Partition into cached vs uncached
    const results = new Array<number[] | null>(texts.length)
    const uncachedIndices: number[] = []
    const uncachedTexts: string[] = []

    for (let i = 0; i < texts.length; i++) {
      const key = this.cacheKey(texts[i], mode)
      const cached = this.cache.get(key)
      if (cached) {
        this.touchLRU(key)
        results[i] = cached
      } else {
        uncachedIndices.push(i)
        uncachedTexts.push(texts[i])
      }
    }

    // Fetch uncached in batches
    if (uncachedTexts.length > 0) {
      const fetched = await this.fetchBatch(uncachedTexts, mode)
      for (let j = 0; j < fetched.length; j++) {
        const vec = fetched[j]
        const origIdx = uncachedIndices[j]
        results[origIdx] = vec
        if (vec) {
          this.cacheSet(this.cacheKey(texts[origIdx], mode), vec)
        }
      }
    }

    return results
  }

  /** Cosine similarity between two vectors. Returns 0 on null/mismatched input. */
  cosineSimilarity(a: number[] | null, b: number[] | null): number {
    if (!a || !b || a.length !== b.length) return 0
    let dot = 0, ma = 0, mb = 0
    for (let i = 0; i < a.length; i++) {
      dot += a[i] * b[i]
      ma += a[i] * a[i]
      mb += b[i] * b[i]
    }
    if (ma === 0 || mb === 0) return 0
    return dot / (Math.sqrt(ma) * Math.sqrt(mb))
  }

  /** Compute similarity between two texts (embeds both, then cosine). */
  async textSimilarity(a: string, b: string, modeA: EmbeddingMode = 'document', modeB: EmbeddingMode = 'document'): Promise<number> {
    const [vecA, vecB] = await this.embedBatch([a, b], modeA === modeB ? modeA : 'document')
    // If modes differ, embed separately
    if (modeA !== modeB) {
      const va = await this.embed(a, modeA)
      const vb = await this.embed(b, modeB)
      return this.cosineSimilarity(va, vb)
    }
    return this.cosineSimilarity(vecA, vecB)
  }

  /** Check if the embedding server is available (circuit breaker not tripped). */
  get available(): boolean {
    return this.cb.openUntil <= Date.now()
  }

  /** Model tag used for cache key differentiation. */
  get model(): string {
    return this.modelTag
  }

  /** Number of cached embeddings. */
  get cacheSize(): number {
    return this.cache.size
  }

  /** Flush cache to disk immediately. */
  flushCache(): void {
    this.persistCache()
  }

  // ── HTTP layer ───────────────────────────────────────────────────────────────

  /**
   * Wrap text in zembed-1's chat template for asymmetric embedding.
   * Queries and documents get different system prompts for optimal retrieval.
   */
  private formatInput(text: string, mode: EmbeddingMode): string {
    const cleaned = (text || '').replace(/\n/g, ' ').trim()
    return `<|im_start|>system\n${mode}<|im_end|>\n<|im_start|>user\n${cleaned}<|im_end|>`
  }

  /** Fetch embeddings from the server, chunking if needed. */
  private async fetchBatch(texts: string[], mode: EmbeddingMode): Promise<Array<number[] | null>> {
    // Demand-load: restart the server if it was idle-unloaded
    const launcher = getInferenceStackLauncher()
    if (launcher) {
      const restarted = await launcher.ensureRunning(MANAGED_EMBEDDING)
      if (restarted) this.cb = { failures: 0, openUntil: 0 }
    }

    // Circuit breaker check
    if (this.cb.openUntil > Date.now()) {
      this.logger.debug('EmbeddingService: circuit breaker open, skipping', {
        reopensIn: `${Math.round((this.cb.openUntil - Date.now()) / 1000)  }s`,
      })
      return new Array(texts.length).fill(null)
    }

    // Chunk large batches
    if (texts.length > this.batchSize) {
      const out: Array<number[] | null> = []
      for (let i = 0; i < texts.length; i += this.batchSize) {
        const chunk = texts.slice(i, i + this.batchSize)
        const res = await this.fetchBatch(chunk, mode)
        out.push(...res)
      }
      return out
    }

    // Single HTTP request
    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), this.timeoutMs + Math.min(2000, texts.length * 60))
      const formatted = texts.map(t => this.formatInput(t, mode))

      const res = await fetch(`${this.serverUrl}/v1/embeddings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: formatted }),
        signal: controller.signal,
      })
      clearTimeout(timer)

      if (res.ok) {
        this.cb.failures = 0
        if (launcher) launcher.notifyActivity(MANAGED_EMBEDDING)
        const data = await res.json() as any
        if (Array.isArray(data?.data)) {
          const sorted = [...data.data].sort((a: any, b: any) => (a.index ?? 0) - (b.index ?? 0))
          return sorted.map((d: any) => Array.isArray(d?.embedding) ? d.embedding : null)
        }
      }
      // Non-200 response — log and fall through to sequential
      this.logger.warn('EmbeddingService: batch request returned non-OK', { status: res.status })
    } catch (err) {
      this.cb.failures++
      if (this.cb.failures >= CB_MAX_FAILURES) {
        this.cb.openUntil = Date.now() + CB_COOLDOWN_MS
        this.logger.warn('EmbeddingService: circuit breaker TRIPPED', {
          failures: this.cb.failures, cooldownMs: CB_COOLDOWN_MS,
        })
        this.cb.failures = 0
      }
      this.logger.debug('EmbeddingService: batch request failed', { error: String(err) })
    }

    // Fallback: sequential fetch
    const out: Array<number[] | null> = []
    for (const t of texts) {
      try {
        const controller = new AbortController()
        const timer = setTimeout(() => controller.abort(), this.timeoutMs)
        const formatted = this.formatInput(t, mode)
        const res = await fetch(`${this.serverUrl}/v1/embeddings`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ input: formatted }),
          signal: controller.signal,
        })
        clearTimeout(timer)
        if (res.ok) {
          this.cb.failures = 0
          if (launcher) launcher.notifyActivity(MANAGED_EMBEDDING)
          const data = await res.json() as any
          if (Array.isArray(data?.data) && data.data.length > 0) {
            out.push(Array.isArray(data.data[0]?.embedding) ? data.data[0].embedding : null)
            continue
          }
        }
        out.push(null)
      } catch {
        out.push(null)
      }
    }
    return out
  }

  // ── Cache management ─────────────────────────────────────────────────────────

  private cacheKey(text: string, mode: EmbeddingMode): string {
    return createHash('sha256').update(`${this.modelTag}:${mode}:${text}`).digest('hex')
  }

  private cacheSet(key: string, vec: number[]): void {
    const entryBytes = key.length + vec.length * 8  // rough estimate
    if (this.cache.has(key)) {
      this.touchLRU(key)
      return
    }
    // Evict if needed
    while (
      (this.cache.size >= this.maxEntries || this.cacheByteSize + entryBytes > this.maxBytes) &&
      this.cacheOrder.length > 0
    ) {
      this.evictOldest()
    }
    this.cache.set(key, vec)
    this.cacheOrder.push(key)
    this.cacheByteSize += entryBytes
    this.schedulePersist()
  }

  private touchLRU(key: string): void {
    const idx = this.cacheOrder.indexOf(key)
    if (idx >= 0) {
      this.cacheOrder.splice(idx, 1)
      this.cacheOrder.push(key)
    }
  }

  private evictOldest(): void {
    const oldest = this.cacheOrder.shift()
    if (oldest) {
      const vec = this.cache.get(oldest)
      if (vec) this.cacheByteSize -= oldest.length + vec.length * 8
      this.cache.delete(oldest)
    }
  }

  // ── File persistence ─────────────────────────────────────────────────────────

  private loadCache(): void {
    if (this.noPersist) return
    try {
      if (!existsSync(this.persistPath)) return
      const raw = readFileSync(this.persistPath, 'utf8')
      const entries = JSON.parse(raw) as Array<[string, number[]]>
      if (!Array.isArray(entries)) return
      let loaded = 0
      for (const [key, vec] of entries) {
        if (typeof key === 'string' && Array.isArray(vec)) {
          this.cache.set(key, vec)
          this.cacheOrder.push(key)
          this.cacheByteSize += key.length + vec.length * 8
          loaded++
          if (loaded >= this.maxEntries) break
        }
      }
      this.logger.debug('EmbeddingService: loaded cache', { entries: loaded })
    } catch (err) {
      this.logger.debug('EmbeddingService: cache load failed (starting fresh)', { error: String(err) })
    }
  }

  private persistCache(): void {
    if (this.noPersist || !this.dirty) return
    try {
      const dir = dirname(this.persistPath)
      if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
      const entries = Array.from(this.cache.entries())
      writeFileSync(this.persistPath, JSON.stringify(entries))
      this.dirty = false
    } catch (err) {
      this.logger.debug('EmbeddingService: cache persist failed', { error: String(err) })
    }
  }

  private schedulePersist(): void {
    this.dirty = true
    if (this.persistTimer) return
    this.persistTimer = setTimeout(() => {
      this.persistTimer = null
      this.persistCache()
    }, CACHE_PERSIST_DEBOUNCE_MS)
  }
}

// ── Singleton ────────────────────────────────────────────────────────────────
let _instance: EmbeddingService | null = null

/** Get the shared EmbeddingService singleton (auto-initializes on first call). */
export function getEmbeddingService(logger?: ILogger): EmbeddingService {
  if (!_instance) {
    const fallbackLogger: ILogger = {
      debug() {}, info() {}, warn() {}, error() {},
      child() { return this },
    }
    _instance = new EmbeddingService(logger || fallbackLogger)
  }
  return _instance
}

/** Reset the singleton (useful for tests). */
export function resetEmbeddingService(): void {
  if (_instance) _instance.flushCache()
  _instance = null
}
