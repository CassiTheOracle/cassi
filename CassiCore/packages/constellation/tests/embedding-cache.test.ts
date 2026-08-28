/**
 * Tests for TopologyEmbeddingCache — content-change detection layer
 * that sits between GravityEngine and EmbeddingService.
 *
 * Verifies:
 *   - Cache hit on unchanged text (skips embed call)
 *   - Cache miss on changed text (re-embeds)
 *   - Batch embedding (partitions cached vs uncached)
 *   - Helix cleanup on deregister
 *   - Metrics accuracy (hits, misses, evictions, hit rate)
 *   - cosineSimilarity delegation
 *   - Integration with TopologyGraph (cache wired automatically)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { TopologyEmbeddingCache } from '../src/topology/embedding-cache.js'
import { TopologyGraph } from '../src/topology/topology-graph.js'
import type { BranchDigest, BranchApproach } from '../src/corpus-types.js'

// --- Mock Factories ---

function createMockEmbeddingService() {
  const embedFn = vi.fn(async (text: string, _mode: string): Promise<number[]> => {
    // Deterministic embedding from text content
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

function createDigest(id: number, findings?: string[]): BranchDigest {
  const approaches: BranchApproach[] = ['implementation', 'research', 'testing', 'debugging']
  return {
    helixId: `helix-${id}`,
    goalSummary: `Goal for helix ${id}`,
    approach: approaches[id % approaches.length],
    progress: 0.5,
    filesActive: [`src/file-${id}.ts`],
    keyFindings: findings ?? [`Finding ${id}-A`, `Finding ${id}-B`],
    blockers: [],
    currentStrategy: `strategy-${id}`,
    rollingScore: 0.5,
    workUnitsProcessed: id,
    updatedAt: Date.now(),
  }
}


// --- TopologyEmbeddingCache Unit Tests ---

describe('TopologyEmbeddingCache', () => {
  let cache: TopologyEmbeddingCache
  let mockService: ReturnType<typeof createMockEmbeddingService>

  beforeEach(() => {
    mockService = createMockEmbeddingService()
    cache = new TopologyEmbeddingCache(mockService as any, createMockLogger() as any)
  })

  describe('getEmbedding', () => {
    it('calls embeddingService.embed on first request (cache miss)', async () => {
      const result = await cache.getEmbedding('h1', 'goal', 'implement auth system')

      expect(result).not.toBeNull()
      expect(result).toHaveLength(64)
      expect(mockService.embed).toHaveBeenCalledOnce()
      expect(mockService.embed).toHaveBeenCalledWith('implement auth system', 'document')
    })

    it('returns cached vector on identical text (cache hit)', async () => {
      const text = 'implement auth system'

      const first = await cache.getEmbedding('h1', 'goal', text)
      const second = await cache.getEmbedding('h1', 'goal', text)

      expect(first).toEqual(second)
      expect(mockService.embed).toHaveBeenCalledOnce()
    })

    it('re-embeds when text changes (cache miss)', async () => {
      await cache.getEmbedding('h1', 'findings', 'finding A')
      await cache.getEmbedding('h1', 'findings', 'finding A | finding B')

      expect(mockService.embed).toHaveBeenCalledTimes(2)
    })

    it('caches goal and findings independently', async () => {
      await cache.getEmbedding('h1', 'goal', 'shared text')
      await cache.getEmbedding('h1', 'findings', 'shared text')

      // Same text but different fields — both should call embed
      expect(mockService.embed).toHaveBeenCalledTimes(2)
    })

    it('caches different helixes independently', async () => {
      const text = 'same goal'

      await cache.getEmbedding('h1', 'goal', text)
      await cache.getEmbedding('h2', 'goal', text)

      // Same text but different helixes — both should call embed
      expect(mockService.embed).toHaveBeenCalledTimes(2)
    })

    it('returns null when embedding service fails', async () => {
      mockService.embed.mockRejectedValueOnce(new Error('network error'))

      const result = await cache.getEmbedding('h1', 'goal', 'some text')

      expect(result).toBeNull()
    })

    it('does not cache failed embeddings', async () => {
      mockService.embed.mockRejectedValueOnce(new Error('fail'))

      await cache.getEmbedding('h1', 'goal', 'retry text')
      const result = await cache.getEmbedding('h1', 'goal', 'retry text')

      // Should try again on second call (no cached null)
      expect(mockService.embed).toHaveBeenCalledTimes(2)
      expect(result).not.toBeNull()
    })
  })

  describe('getEmbeddingBatch', () => {
    it('batches uncached requests through embedBatch', async () => {
      const requests = [
        { helixId: 'h1', field: 'goal' as const, text: 'goal one' },
        { helixId: 'h2', field: 'goal' as const, text: 'goal two' },
        { helixId: 'h3', field: 'goal' as const, text: 'goal three' },
      ]

      const results = await cache.getEmbeddingBatch(requests)

      expect(results).toHaveLength(3)
      expect(results.every(r => r !== null)).toBe(true)
      expect(mockService.embedBatch).toHaveBeenCalledOnce()
      expect(mockService.embedBatch).toHaveBeenCalledWith(
        ['goal one', 'goal two', 'goal three'],
        'document',
      )
    })

    it('filters cached entries from batch request', async () => {
      // Pre-populate cache
      await cache.getEmbedding('h1', 'goal', 'goal one')
      mockService.embed.mockClear()

      const requests = [
        { helixId: 'h1', field: 'goal' as const, text: 'goal one' },     // cached
        { helixId: 'h2', field: 'goal' as const, text: 'goal two' },     // uncached
        { helixId: 'h3', field: 'goal' as const, text: 'goal three' },   // uncached
      ]

      const results = await cache.getEmbeddingBatch(requests)

      expect(results).toHaveLength(3)
      expect(results.every(r => r !== null)).toBe(true)
      // Only 2 uncached texts should be in the batch
      expect(mockService.embedBatch).toHaveBeenCalledWith(
        ['goal two', 'goal three'],
        'document',
      )
    })

    it('returns all cached when nothing changed', async () => {
      const requests = [
        { helixId: 'h1', field: 'goal' as const, text: 'goal one' },
        { helixId: 'h2', field: 'goal' as const, text: 'goal two' },
      ]

      // First call populates cache
      await cache.getEmbeddingBatch(requests)
      mockService.embedBatch.mockClear()

      // Second call should be fully cached
      const results = await cache.getEmbeddingBatch(requests)

      expect(results).toHaveLength(2)
      expect(results.every(r => r !== null)).toBe(true)
      expect(mockService.embedBatch).not.toHaveBeenCalled()
    })

    it('handles batch failure gracefully', async () => {
      mockService.embedBatch.mockRejectedValueOnce(new Error('batch failed'))

      const requests = [
        { helixId: 'h1', field: 'goal' as const, text: 'goal one' },
      ]

      const results = await cache.getEmbeddingBatch(requests)

      // Should return null for failed entries
      expect(results).toHaveLength(1)
      expect(results[0]).toBeUndefined() // never assigned
    })
  })

  describe('removeHelix', () => {
    it('removes cached goal and findings for a helix', async () => {
      await cache.getEmbedding('h1', 'goal', 'goal text')
      await cache.getEmbedding('h1', 'findings', 'findings text')
      expect(cache.size).toBe(2)

      cache.removeHelix('h1')

      expect(cache.size).toBe(0)
    })

    it('does not affect other helixes', async () => {
      await cache.getEmbedding('h1', 'goal', 'goal one')
      await cache.getEmbedding('h2', 'goal', 'goal two')

      cache.removeHelix('h1')

      expect(cache.size).toBe(1)
      // h2 should still be cached
      mockService.embed.mockClear()
      await cache.getEmbedding('h2', 'goal', 'goal two')
      expect(mockService.embed).not.toHaveBeenCalled()
    })

    it('re-embeds after removeHelix when same helix re-registers', async () => {
      await cache.getEmbedding('h1', 'goal', 'goal text')
      cache.removeHelix('h1')
      mockService.embed.mockClear()

      await cache.getEmbedding('h1', 'goal', 'goal text')

      expect(mockService.embed).toHaveBeenCalledOnce()
    })
  })

  describe('cosineSimilarity', () => {
    it('delegates to underlying embeddingService', () => {
      const a = [1, 0, 0]
      const b = [0, 1, 0]

      cache.cosineSimilarity(a, b)

      expect(mockService.cosineSimilarity).toHaveBeenCalledWith(a, b)
    })
  })

  describe('metrics', () => {
    it('tracks hits and misses accurately', async () => {
      await cache.getEmbedding('h1', 'goal', 'text A')       // miss
      await cache.getEmbedding('h1', 'goal', 'text A')       // hit
      await cache.getEmbedding('h1', 'goal', 'text A')       // hit
      await cache.getEmbedding('h1', 'findings', 'text B')   // miss

      const metrics = cache.getMetrics()
      expect(metrics.hits).toBe(2)
      expect(metrics.misses).toBe(2)
      expect(metrics.totalCalls).toBe(4)
    })

    it('tracks evictions', async () => {
      await cache.getEmbedding('h1', 'goal', 'text')
      await cache.getEmbedding('h1', 'findings', 'text')

      cache.removeHelix('h1')

      expect(cache.getMetrics().evictions).toBe(2)
    })

    it('computes hit rate correctly', async () => {
      expect(cache.hitRate).toBe(0) // no calls yet

      await cache.getEmbedding('h1', 'goal', 'text')   // miss
      await cache.getEmbedding('h1', 'goal', 'text')   // hit
      await cache.getEmbedding('h1', 'goal', 'text')   // hit
      await cache.getEmbedding('h1', 'goal', 'text')   // hit

      expect(cache.hitRate).toBe(0.75) // 3 hits / 4 total
    })
  })

  describe('clear', () => {
    it('clears all data and resets metrics', async () => {
      await cache.getEmbedding('h1', 'goal', 'text')
      await cache.getEmbedding('h1', 'goal', 'text')

      cache.clear()

      expect(cache.size).toBe(0)
      expect(cache.hitRate).toBe(0)
      expect(cache.getMetrics().hits).toBe(0)
      expect(cache.getMetrics().misses).toBe(0)
    })
  })

  describe('cache eviction under pressure', () => {
    it('handles many helixes without memory leak', async () => {
      // Simulate 100 helixes registering and deregistering
      for (let i = 0; i < 100; i++) {
        await cache.getEmbedding(`h${i}`, 'goal', `goal ${i}`)
        await cache.getEmbedding(`h${i}`, 'findings', `finding ${i}`)
      }

      const initialSize = cache.size
      expect(initialSize).toBe(200)

      // Deregister half of them
      for (let i = 0; i < 50; i++) {
        cache.removeHelix(`h${i}`)
      }

      expect(cache.size).toBe(100)
      expect(cache.getMetrics().evictions).toBe(100)
    })

    it('maintains cache integrity after repeated operations', async () => {
      const iterations = 50

      for (let i = 0; i < iterations; i++) {
        // Register
        await cache.getEmbedding('h1', 'goal', 'goal text')
        await cache.getEmbedding('h1', 'findings', 'finding text')

        // Deregister
        cache.removeHelix('h1')

        // Verify cache is empty after each cycle
        expect(cache.size).toBe(0)
      }

      // Final state should be clean
      expect(cache.size).toBe(0)
      expect(cache.getMetrics().evictions).toBe(iterations * 2)
    })
  })
})


// --- Integration: TopologyGraph + Cache ---

describe('TopologyGraph embedding cache integration', () => {
  let mockService: ReturnType<typeof createMockEmbeddingService>
  let topology: TopologyGraph

  beforeEach(() => {
    mockService = createMockEmbeddingService()
    topology = new TopologyGraph({
      embeddingService: mockService as any,
      logger: createMockLogger() as any,
      eventBus: {
        emit: () => {},
        on: () => () => {},
        off: () => {},
      } as any,
    })
  })

  it('wires embedding cache automatically', () => {
    expect(topology.cache).toBeDefined()
    expect(topology.cache.size).toBe(0)
  })

  it('caches embeddings across digest updates', async () => {
    const digest = createDigest(1)

    // First update: embeds goal + findings
    await topology.onDigestUpdate('h1', digest)
    const callsAfterFirst = mockService.embed.mock.calls.length

    // Second update with same digest: should hit cache for findings
    await topology.onDigestUpdate('h1', digest)
    const callsAfterSecond = mockService.embed.mock.calls.length

    // Second update should have fewer embed calls (findings cached)
    expect(callsAfterSecond).toBeLessThanOrEqual(callsAfterFirst)
    expect(topology.getCacheMetrics().hits).toBeGreaterThan(0)
  })

  it('re-embeds when findings change', async () => {
    await topology.onDigestUpdate('h1', createDigest(1, ['finding A']))
    mockService.embed.mockClear()

    await topology.onDigestUpdate('h1', createDigest(1, ['finding A', 'finding B']))

    // Should re-embed findings (text changed)
    const findingsCalls = mockService.embed.mock.calls.filter(
      ([text]) => text.includes('finding'),
    )
    expect(findingsCalls.length).toBeGreaterThan(0)
  })

  it('cleans up cache on deregister', async () => {
    await topology.onDigestUpdate('h1', createDigest(1))
    expect(topology.cache.size).toBeGreaterThan(0)

    topology.deregisterHelix('h1')

    expect(topology.cache.size).toBe(0)
    expect(topology.getCacheMetrics().evictions).toBeGreaterThan(0)
  })

  it('reports cache hit rate via accessor', async () => {
    const digest = createDigest(1)

    await topology.onDigestUpdate('h1', digest)
    await topology.onDigestUpdate('h1', digest)
    await topology.onDigestUpdate('h1', digest)

    // After multiple identical updates, hit rate should be positive
    expect(topology.cacheHitRate).toBeGreaterThan(0)
  })

  it('maintains independent cache per helix', async () => {
    await topology.onDigestUpdate('h1', createDigest(1))
    await topology.onDigestUpdate('h2', createDigest(2))

    topology.deregisterHelix('h1')

    // h2 cache entries should remain
    const metricsBeforeH2 = topology.cache.size
    expect(metricsBeforeH2).toBeGreaterThan(0)
  })

  it('prevents memory leak over many digest updates', async () => {
    // Simulate a helix updating 100 times
    for (let i = 0; i < 100; i++) {
      await topology.onDigestUpdate('h1', createDigest(1, [`finding ${i}`]))
    }

    // Cache should still only have entries for active helixes
    expect(topology.cache.size).toBeGreaterThan(0)
    expect(topology.cache.size).toBeLessThan(10) // Should not grow unbounded

    topology.deregisterHelix('h1')
    expect(topology.cache.size).toBe(0)
  })

  it('handles cache eviction under pressure with many helixes', async () => {
    const N = 50

    // Register many helixes
    for (let i = 0; i < N; i++) {
      await topology.onDigestUpdate(`h${i}`, createDigest(i))
    }

    const sizeAfterRegistration = topology.cache.size
    expect(sizeAfterRegistration).toBeGreaterThan(0)

    // Deregister half
    for (let i = 0; i < N / 2; i++) {
      topology.deregisterHelix(`h${i}`)
    }

    // Cache should have shrunk
    expect(topology.cache.size).toBeLessThan(sizeAfterRegistration)
    expect(topology.getCacheMetrics().evictions).toBeGreaterThan(0)
  })
})
