/**
 * Topology Embedding Cache — Content-change detection layer for the
 * GravityEngine's embedding calls.
 *
 * WHY: The global EmbeddingService has its own LRU cache keyed by
 * SHA-256(text), but the GravityEngine re-embeds findings text on
 * every digest update — even when findings haven't changed. This
 * cache adds a fast content-change detection layer:
 *
 *   1. Tracks a lightweight FNV-1a hash of the last-embedded text
 *      per (helix, field) pair
 *   2. Returns the cached vector immediately when text is unchanged
 *      (no SHA-256, no Map lookup in EmbeddingService)
 *   3. Falls through to EmbeddingService on cache miss
 *   4. Supports batch embedding via embedBatch() for concurrent updates
 *   5. Provides topology-specific metrics (hit rate, API calls saved)
 *
 * Lifecycle: one per TopologyGraph, destroyed when constellation completes.
 */

import type { ILogger } from '../../../../types/interfaces.js'
import type { EmbeddingService } from '../../embeddings/embedding-service.js'

export interface TopologyEmbeddingCacheMetrics {
  /** Number of times a cached vector was returned (text unchanged) */
  hits: number
  /** Number of times a fresh embed was required (text changed or new) */
  misses: number
  /** Number of entries removed via removeHelix() */
  evictions: number
  /** Total getEmbedding()/getEmbeddingBatch() calls */
  totalCalls: number
}

export type EmbeddingField = 'goal' | 'findings'

export class TopologyEmbeddingCache {
  /** FNV-1a hash of the last-embedded text per cache key */
  private contentHashes = new Map<string, number>()
  /** Cached embedding vectors per cache key */
  private vectors = new Map<string, number[]>()
  private metrics: TopologyEmbeddingCacheMetrics = {
    hits: 0,
    misses: 0,
    evictions: 0,
    totalCalls: 0,
  }
  private embeddingService: EmbeddingService
  private logger: ILogger

  constructor(embeddingService: EmbeddingService, logger: ILogger) {
    this.embeddingService = embeddingService
    this.logger = logger.child?.('embedding-cache') ?? logger
  }

  /**
   * Get or compute embedding for a helix field.
   * Returns cached vector if content hasn't changed; otherwise embeds fresh.
   */
  async getEmbedding(
    helixId: string,
    field: EmbeddingField,
    text: string,
  ): Promise<number[] | null> {
    this.metrics.totalCalls++
    const key = `${helixId}:${field}`
    const hash = fnv1a(text)

    // Fast path: content unchanged — return cached vector
    if (this.contentHashes.get(key) === hash) {
      const cached = this.vectors.get(key)
      if (cached) {
        this.metrics.hits++
        return cached
      }
    }

    // Slow path: content changed or new — delegate to EmbeddingService
    this.metrics.misses++
    try {
      const vec = await this.embeddingService.embed(text, 'document')
      if (vec) {
        this.contentHashes.set(key, hash)
        this.vectors.set(key, vec)
      }
      return vec
    } catch {
      return null
    }
  }

  /**
   * Batch embed multiple (helix, field, text) tuples.
   * Filters out unchanged content first, then batches the rest via
   * EmbeddingService.embedBatch() for a single network round-trip.
   */
  async getEmbeddingBatch(
    requests: Array<{ helixId: string; field: EmbeddingField; text: string }>,
  ): Promise<Array<number[] | null>> {
    const results = new Array<number[] | null>(requests.length)
    const uncachedIndices: number[] = []
    const uncachedTexts: string[] = []

    // Partition: cached vs uncached
    for (let i = 0; i < requests.length; i++) {
      const { helixId, field, text } = requests[i]
      this.metrics.totalCalls++
      const key = `${helixId}:${field}`
      const hash = fnv1a(text)

      if (this.contentHashes.get(key) === hash) {
        const cached = this.vectors.get(key)
        if (cached) {
          this.metrics.hits++
          results[i] = cached
          continue
        }
      }

      this.metrics.misses++
      uncachedIndices.push(i)
      uncachedTexts.push(text)
    }

    // Batch-embed uncached via EmbeddingService
    if (uncachedTexts.length > 0) {
      try {
        const vecs = await this.embeddingService.embedBatch(uncachedTexts, 'document')
        for (let j = 0; j < vecs.length; j++) {
          const origIdx = uncachedIndices[j]
          const vec = vecs[j]
          results[origIdx] = vec
          if (vec) {
            const { helixId, field, text } = requests[origIdx]
            const key = `${helixId}:${field}`
            this.contentHashes.set(key, fnv1a(text))
            this.vectors.set(key, vec)
          }
        }
      } catch {
        // Batch failed — results stay null for uncached entries
      }
    }

    return results
  }

  /**
   * Remove all cached data for a helix.
   * Called when a helix deregisters (completed/failed/cancelled).
   */
  removeHelix(helixId: string): void {
    for (const field of ['goal', 'findings'] as const) {
      const key = `${helixId}:${field}`
      if (this.vectors.has(key)) {
        this.vectors.delete(key)
        this.contentHashes.delete(key)
        this.metrics.evictions++
      }
    }
  }

  /**
   * Delegate cosineSimilarity to the underlying EmbeddingService.
   * HOW: Pure computation (no API call), but centralizes the dependency
   * so GravityEngine only needs the cache, not the raw service.
   */
  cosineSimilarity(a: number[] | null, b: number[] | null): number {
    return this.embeddingService.cosineSimilarity(a, b)
  }

  /**
   * Get cache metrics snapshot.
   */
  getMetrics(): TopologyEmbeddingCacheMetrics {
    return { ...this.metrics }
  }

  /**
   * Cache hit rate (0-1). Returns 0 if no calls have been made.
   */
  get hitRate(): number {
    const total = this.metrics.hits + this.metrics.misses
    return total === 0 ? 0 : this.metrics.hits / total
  }

  /**
   * Number of cached embedding vectors.
   */
  get size(): number {
    return this.vectors.size
  }

  /**
   * Clear all cached data and reset metrics.
   */
  clear(): void {
    this.contentHashes.clear()
    this.vectors.clear()
    this.metrics = { hits: 0, misses: 0, evictions: 0, totalCalls: 0 }
  }
}

/**
 * FNV-1a hash for fast content-change detection.
 *
 * WHY: Not cryptographic — only used to detect if text changed since
 * last embed. FNV-1a is ~100x faster than SHA-256 for short strings
 * and has excellent distribution for change detection.
 */
function fnv1a(str: string): number {
  let hash = 0x811c9dc5
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i)
    hash = (hash * 0x01000193) | 0
  }
  return hash >>> 0
}
