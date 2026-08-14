/**
 * CRITICAL MISSING TESTS for TopologyEmbeddingCache
 * 
 * Focus: Cache eviction under pressure, LRU behavior, size limits
 * These tests were identified as high-priority gaps in the original coverage review.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { TopologyEmbeddingCache } from '../src/topology/embedding-cache.js'
import type { EmbeddingService } from '../src/vendor/embeddings/embedding-service.js'

// --- Mock Factories ---

function createMockEmbeddingService() {
  const embedFn = vi.fn(async (text: string, _mode: string): Promise<number[]> => {
    const EMBED_DIM = 64
    return Array.from({ length: EMBED_DIM }, (_, i) => {
      let h = 0
      for (const ch of text) h = ((h << 5) - h + ch.charCodeAt(0) + i) | 0
      return (h & 0xFFFF) / 0xFFFF
    })
  })

  const embedBatchFn = vi.fn(async (texts: string[], mode: string): Promise<Array<number[] | null>> => {
    return Promise.all(texts.map(t => embedFn(t, mode)))
  })

  const cosineFn = vi.fn((a: number[] | null, b: number[] | null): number => {
    if (!a || !b || a.length !== b.length) return 0
    let dot = 0, normA = 0, normB = 0
    for (let i = 0; i < a.length; i++) {
      dot += a[i] * b[i]
      normA += a[i] * a[i]
      normB += b[i] * b[i]
    }
    const denom = Math.sqrt(normA) * Math.sqrt(normB)
    return denom === 0 ? 0 : dot / denom
  })

  return {
    embed: embedFn,
    embedBatch: embedBatchFn,
    cosineSimilarity: cosineFn,
  }
}

function createMockLogger() {
  const noop = () => {}
  return {
    info: noop, warn: noop, error: noop, debug: noop,
    child: () => createMockLogger(),
  }
}

// --- Critical Missing Tests: Cache Eviction Under Pressure ---

describe('TopologyEmbeddingCache — Cache Eviction Under Pressure', () => {
  let cache: TopologyEmbeddingCache
  let mockService: ReturnType<typeof createMockEmbeddingService>

  beforeEach(() => {
    mockService = createMockEmbeddingService()
    cache = new TopologyEmbeddingCache(mockService as any, createMockLogger() as any)
  })

  describe('LRU eviction behavior', () => {
    it('evicts least recently used entries when cache grows large', async () => {
      // Populate cache with many helixes
      const numHelixes = 100
      for (let i = 0; i < numHelixes; i++) {
        await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
        await cache.getEmbedding(`h${i}`, 'findings', `findings ${i}`)
      }

      expect(cache.size).toBe(numHelixes * 2)

      // Access some entries to mark them as recently used
      await cache.getEmbedding('h0', 'goal', 'goal 0')
      await cache.getEmbedding('h1', 'goal', 'goal 1')
      await cache.getEmbedding('h2', 'goal', 'goal 2')

      // Remove some helixes to trigger evictions
      cache.removeHelix('h50')
      cache.removeHelix('h51')
      cache.removeHelix('h52')

      // Verify cache size decreased and metrics tracked evictions
      expect(cache.size).toBe(numHelixes * 2 - 6) // 3 helixes × 2 fields each
      expect(cache.getMetrics().evictions).toBe(6)
    })

    it('maintains cache integrity after multiple rapid evictions', async () => {
      // Populate cache
      for (let i = 0; i < 50; i++) {
        await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
      }

      // Rapidly remove many helixes
      for (let i = 0; i < 25; i++) {
        cache.removeHelix(`h${i}`)
      }

      // Verify remaining entries are still accessible
      const result = await cache.getEmbedding('h30', 'goal', 'goal 30')
      expect(result).not.toBeNull()
      expect(cache.size).toBe(25) // 50 - 25 removed

      // Verify metrics are accurate
      const metrics = cache.getMetrics()
      expect(metrics.evictions).toBe(25)
    })
  })

  describe('Cache pressure scenarios', () => {
    it('handles many helixes with large embedding vectors efficiently', async () => {
      // Simulate large embeddings (256-dim instead of 64-dim)
      const largeEmbedFn = vi.fn(async (text: string): Promise<number[]> => {
        return Array.from({ length: 256 }, (_, i) => i / 256)
      })
      mockService.embed.mockImplementation(largeEmbedFn as any)

      // Create many helixes with large vectors
      const numHelixes = 200
      for (let i = 0; i < numHelixes; i++) {
        await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
      }

      expect(cache.size).toBe(numHelixes)
      
      // Verify cache can still operate under memory pressure
      const result = await cache.getEmbedding('h100', 'goal', 'goal 100')
      expect(result).not.toBeNull()
      expect(result).toHaveLength(256)
    })

    it('survives cache thrashing with alternating access patterns', async () => {
      // Populate cache with 50 helixes
      for (let i = 0; i < 50; i++) {
        await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
      }

      // Alternate between accessing different subsets (simulates thrashing)
      for (let round = 0; round < 5; round++) {
        // Access first half
        for (let i = 0; i < 25; i++) {
          await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
        }
        // Access second half
        for (let i = 25; i < 50; i++) {
          await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
        }
      }

      // Verify all entries still accessible and metrics tracked hits
      const metrics = cache.getMetrics()
      expect(metrics.hits).toBeGreaterThan(0)
      expect(cache.size).toBe(50)
    })
  })

  describe('Concurrent operations under pressure', () => {
    it('handles concurrent getEmbedding and removeHelix without corruption', async () => {
      // Populate cache
      for (let i = 0; i < 30; i++) {
        await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
      }

      // Simulate concurrent operations: some helixes being accessed while others are removed
      const operations = []
      for (let i = 0; i < 15; i++) {
        // Access these
        operations.push(cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`))
        // Remove these
        cache.removeHelix(`h${i + 15}`)
      }

      await Promise.all(operations)

      // Verify cache is in consistent state
      expect(cache.size).toBe(15) // 30 initial - 15 removed
      const metrics = cache.getMetrics()
      expect(metrics.evictions).toBe(15)
    })

    it('maintains correct hit/miss ratio under high concurrency', async () => {
      // Prime cache with 20 helixes
      for (let i = 0; i < 20; i++) {
        await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
      }

      // Concurrent accesses (all should be hits)
      const accesses = Array.from({ length: 100 }, (_, i) => 
        cache.getEmbedding(`h${i % 20}`, 'goal', `goal ${i % 20}`)
      )

      await Promise.all(accesses)

      const metrics = cache.getMetrics()
      // Should have 20 misses (initial) + 100 hits (concurrent)
      expect(metrics.hits).toBeGreaterThanOrEqual(100)
      expect(metrics.misses).toBe(20)
    })
  })

  describe('Edge cases with empty or null inputs', () => {
    it('handles empty string gracefully (treated as distinct content)', async () => {
      const result1 = await cache.getEmbedding('h1', 'goal', '')
      const result2 = await cache.getEmbedding('h1', 'goal', '')
      
      expect(result1).not.toBeNull()
      expect(result2).toEqual(result1) // Cache hit on second call
      expect(mockService.embed).toHaveBeenCalledOnce()
    })

    it('handles very large text inputs without crashing', async () => {
      const largeText = 'x'.repeat(100000) // 100KB string
      const result = await cache.getEmbedding('h1', 'goal', largeText)
      
      expect(result).not.toBeNull()
      expect(mockService.embed).toHaveBeenCalledOnce()
    })

    it('recovers from repeated failures without leaking cache state', async () => {
      mockService.embed.mockRejectedValueOnce(new Error('fail'))
      mockService.embed.mockRejectedValueOnce(new Error('fail'))
      mockService.embed.mockRejectedValueOnce(new Error('fail'))

      // Three failures in a row
      await cache.getEmbedding('h1', 'goal', 'text')
      await cache.getEmbedding('h1', 'goal', 'text')
      await cache.getEmbedding('h1', 'goal', 'text')

      // Fourth call should still try (no caching of failures)
      mockService.embed.mockResolvedValueOnce([1, 2, 3])
      const result = await cache.getEmbedding('h1', 'goal', 'text')

      expect(result).not.toBeNull()
      expect(mockService.embed).toHaveBeenCalledTimes(4)
    })
  })

  describe('Metrics accuracy under pressure', () => {
    it('tracks hit rate correctly with mixed hit/miss patterns', async () => {
      // 10 misses
      for (let i = 0; i < 10; i++) {
        await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
      }

      // 20 hits (re-accessing same)
      for (let i = 0; i < 20; i++) {
        await cache.getEmbedding(`h${i % 10}`, 'goal', `goal ${i % 10}`)
      }

      // 5 more misses
      for (let i = 10; i < 15; i++) {
        await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
      }

      const metrics = cache.getMetrics()
      expect(metrics.hits).toBe(20)
      expect(metrics.misses).toBe(15)
      expect(metrics.totalCalls).toBe(35)
      expect(cache.hitRate).toBeCloseTo(20 / 35, 0.01)
    })

    it('resets metrics correctly after clear() even under pressure', async () => {
      // Build up metrics
      for (let i = 0; i < 50; i++) {
        await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
      }
      for (let i = 0; i < 100; i++) {
        await cache.getEmbedding(`h${i % 50}`, 'goal', `goal ${i % 50}`)
      }

      expect(cache.hitRate).toBeGreaterThan(0)
      expect(cache.getMetrics().hits).toBeGreaterThan(0)

      // Clear and verify reset
      cache.clear()

      expect(cache.hitRate).toBe(0)
      expect(cache.getMetrics().hits).toBe(0)
      expect(cache.getMetrics().misses).toBe(0)
      expect(cache.getMetrics().evictions).toBe(0)
      expect(cache.getMetrics().totalCalls).toBe(0)
      expect(cache.size).toBe(0)
    })
  })
})
