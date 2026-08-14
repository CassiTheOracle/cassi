import { describe, it, expect, vi, beforeEach } from 'vitest'
import { TopologyEmbeddingCache } from '../../../src/topology/embedding-cache.js'
import type { EmbeddingService } from '../../../src/vendor/embeddings/embedding-service.js'
import type { ILogger } from '../../../src/vendor/types/interfaces.js'

function makeLogger(): ILogger {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn().mockReturnThis(),
  } as unknown as ILogger
}

function makeEmbeddingService(overrides: Partial<EmbeddingService> = {}): EmbeddingService {
  return {
    embed: vi.fn(async (_text: string) => [0.1, 0.2, 0.3]),
    embedBatch: vi.fn(async (texts: string[]) => texts.map(() => [0.1, 0.2, 0.3])),
    cosineSimilarity: vi.fn((a: number[] | null, b: number[] | null) => {
      if (!a || !b) return 0
      return 0.95
    }),
    ...overrides,
  } as unknown as EmbeddingService
}

describe('TopologyEmbeddingCache', () => {
  let cache: TopologyEmbeddingCache
  let embeddingService: EmbeddingService
  let logger: ILogger

  beforeEach(() => {
    logger = makeLogger()
    embeddingService = makeEmbeddingService()
    cache = new TopologyEmbeddingCache(embeddingService, logger)
  })

  describe('construction', () => {
    it('starts with zero size and no metrics', () => {
      expect(cache.size).toBe(0)
      expect(cache.hitRate).toBe(0)
      const m = cache.getMetrics()
      expect(m.hits).toBe(0)
      expect(m.misses).toBe(0)
      expect(m.evictions).toBe(0)
      expect(m.totalCalls).toBe(0)
    })
  })

  describe('getEmbedding', () => {
    it('delegates to EmbeddingService on first call (cache miss)', async () => {
      const result = await cache.getEmbedding('h1', 'goal', 'some text')
      expect(result).toEqual([0.1, 0.2, 0.3])
      expect(embeddingService.embed).toHaveBeenCalledWith('some text', 'document')
      expect(cache.getMetrics().misses).toBe(1)
      expect(cache.getMetrics().hits).toBe(0)
    })

    it('returns cached vector on second call with same text (cache hit)', async () => {
      await cache.getEmbedding('h1', 'goal', 'same text')
      const result = await cache.getEmbedding('h1', 'goal', 'same text')

      expect(result).toEqual([0.1, 0.2, 0.3])
      expect(embeddingService.embed).toHaveBeenCalledTimes(1) // only first call
      expect(cache.getMetrics().hits).toBe(1)
      expect(cache.getMetrics().misses).toBe(1)
    })

    it('re-embeds when text changes', async () => {
      const vec1 = [1, 2, 3]
      const vec2 = [4, 5, 6]
      vi.mocked(embeddingService.embed)
        .mockResolvedValueOnce(vec1)
        .mockResolvedValueOnce(vec2)

      const r1 = await cache.getEmbedding('h1', 'goal', 'text v1')
      expect(r1).toEqual(vec1)

      const r2 = await cache.getEmbedding('h1', 'goal', 'text v2')
      expect(r2).toEqual(vec2)
      expect(embeddingService.embed).toHaveBeenCalledTimes(2)
      expect(cache.getMetrics().misses).toBe(2)
    })

    it('treats different fields independently', async () => {
      await cache.getEmbedding('h1', 'goal', 'goal text')
      await cache.getEmbedding('h1', 'findings', 'findings text')

      expect(embeddingService.embed).toHaveBeenCalledTimes(2)
      expect(cache.size).toBe(2)
    })

    it('treats different helixIds independently', async () => {
      await cache.getEmbedding('h1', 'goal', 'same text')
      await cache.getEmbedding('h2', 'goal', 'same text')

      // Both should miss because the cache key is (helixId, field)
      expect(embeddingService.embed).toHaveBeenCalledTimes(2)
      expect(cache.getMetrics().misses).toBe(2)
    })

    it('returns null and does not cache when embedding service returns null', async () => {
      vi.mocked(embeddingService.embed).mockResolvedValueOnce(null as unknown as number[])

      const result = await cache.getEmbedding('h1', 'goal', 'text')
      expect(result).toBeNull()
      expect(cache.size).toBe(0)
    })

    it('returns null when embedding service throws', async () => {
      vi.mocked(embeddingService.embed).mockRejectedValueOnce(new Error('API error'))

      const result = await cache.getEmbedding('h1', 'goal', 'text')
      expect(result).toBeNull()
      expect(cache.size).toBe(0)
    })

    it('increments totalCalls on every call', async () => {
      await cache.getEmbedding('h1', 'goal', 'text')
      await cache.getEmbedding('h1', 'goal', 'text') // hit
      await cache.getEmbedding('h2', 'goal', 'text') // miss
      expect(cache.getMetrics().totalCalls).toBe(3)
    })
  })

  describe('getEmbeddingBatch', () => {
    it('returns cached results for unchanged content and delegates the rest', async () => {
      // Prime the cache with h1:goal
      await cache.getEmbedding('h1', 'goal', 'text A')
      vi.mocked(embeddingService.embed).mockClear()

      const batchVec = [0.7, 0.8, 0.9]
      vi.mocked(embeddingService.embedBatch).mockResolvedValueOnce([batchVec])

      const results = await cache.getEmbeddingBatch([
        { helixId: 'h1', field: 'goal', text: 'text A' },   // cached hit
        { helixId: 'h2', field: 'goal', text: 'text B' },   // miss → batch
      ])

      expect(results).toHaveLength(2)
      expect(results[0]).toEqual([0.1, 0.2, 0.3]) // cached
      expect(results[1]).toEqual(batchVec)         // fresh from batch

      // embedBatch called with only the uncached text
      expect(embeddingService.embedBatch).toHaveBeenCalledWith(['text B'], 'document')
    })

    it('does not call embedBatch when all entries are cached', async () => {
      await cache.getEmbedding('h1', 'goal', 'text')
      vi.mocked(embeddingService.embedBatch).mockClear()

      const results = await cache.getEmbeddingBatch([
        { helixId: 'h1', field: 'goal', text: 'text' },
      ])

      expect(results).toHaveLength(1)
      expect(results[0]).toEqual([0.1, 0.2, 0.3])
      expect(embeddingService.embedBatch).not.toHaveBeenCalled()
    })

    it('returns null entries when batch embedding fails', async () => {
      vi.mocked(embeddingService.embedBatch).mockRejectedValueOnce(new Error('batch fail'))

      const results = await cache.getEmbeddingBatch([
        { helixId: 'h1', field: 'goal', text: 'text' },
      ])

      expect(results).toHaveLength(1)
      expect(results[0]).toBeUndefined() // stays null (unset position in array)
    })

    it('caches fresh vectors from batch response', async () => {
      const batchVec = [9, 8, 7]
      vi.mocked(embeddingService.embedBatch).mockResolvedValueOnce([batchVec])

      await cache.getEmbeddingBatch([
        { helixId: 'h1', field: 'goal', text: 'new text' },
      ])

      expect(cache.size).toBe(1)

      // Calling again with same text should be a hit
      vi.mocked(embeddingService.embedBatch).mockClear()
      const results = await cache.getEmbeddingBatch([
        { helixId: 'h1', field: 'goal', text: 'new text' },
      ])
      expect(results[0]).toEqual(batchVec)
      expect(embeddingService.embedBatch).not.toHaveBeenCalled()
    })
  })

  describe('removeHelix', () => {
    it('removes all cached entries for a helix', async () => {
      await cache.getEmbedding('h1', 'goal', 'g')
      await cache.getEmbedding('h1', 'findings', 'f')
      expect(cache.size).toBe(2)

      cache.removeHelix('h1')
      expect(cache.size).toBe(0)
      expect(cache.getMetrics().evictions).toBe(2)
    })

    it('does not affect other helixes', async () => {
      await cache.getEmbedding('h1', 'goal', 'g')
      await cache.getEmbedding('h2', 'goal', 'g')
      expect(cache.size).toBe(2)

      cache.removeHelix('h1')
      expect(cache.size).toBe(1)
    })

    it('is a no-op for unknown helixId', () => {
      cache.removeHelix('unknown')
      expect(cache.getMetrics().evictions).toBe(0)
    })

    it('forces re-embed after removal', async () => {
      await cache.getEmbedding('h1', 'goal', 'text')
      cache.removeHelix('h1')

      vi.mocked(embeddingService.embed).mockClear()
      await cache.getEmbedding('h1', 'goal', 'text')
      expect(embeddingService.embed).toHaveBeenCalledTimes(1) // miss, not hit
    })
  })

  describe('cosineSimilarity', () => {
    it('delegates to EmbeddingService.cosineSimilarity', () => {
      const result = cache.cosineSimilarity([1, 2], [3, 4])
      expect(embeddingService.cosineSimilarity).toHaveBeenCalledWith([1, 2], [3, 4])
      expect(result).toBe(0.95)
    })

    it('handles null inputs', () => {
      cache.cosineSimilarity(null, [1, 2])
      expect(embeddingService.cosineSimilarity).toHaveBeenCalledWith(null, [1, 2])
    })
  })

  describe('hitRate', () => {
    it('returns 0 when no calls have been made', () => {
      expect(cache.hitRate).toBe(0)
    })

    it('calculates correct hit rate', async () => {
      await cache.getEmbedding('h1', 'goal', 'text') // miss
      await cache.getEmbedding('h1', 'goal', 'text') // hit
      await cache.getEmbedding('h1', 'goal', 'text') // hit

      // 2 hits / (2 hits + 1 miss) = 0.667
      expect(cache.hitRate).toBeCloseTo(2 / 3)
    })
  })

  describe('clear', () => {
    it('resets all state and metrics', async () => {
      await cache.getEmbedding('h1', 'goal', 'text')
      await cache.getEmbedding('h1', 'goal', 'text')
      expect(cache.size).toBe(1)
      expect(cache.hitRate).toBeGreaterThan(0)

      cache.clear()
      expect(cache.size).toBe(0)
      expect(cache.hitRate).toBe(0)
      const m = cache.getMetrics()
      expect(m.hits).toBe(0)
      expect(m.misses).toBe(0)
      expect(m.evictions).toBe(0)
      expect(m.totalCalls).toBe(0)
    })
  })
})
