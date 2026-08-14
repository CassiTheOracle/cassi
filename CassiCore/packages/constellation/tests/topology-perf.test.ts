/**
 * Performance Benchmarks for the Helix Topology Graph.
 *
 * Measures wall-clock time for core topology operations at various scales:
 *   - GravityEngine: registration, digest update (embedding + physics tick)
 *   - LinkManager: pairwise evaluation
 *   - ClusterTracker: connected-component detection
 *   - TopologyGraph: full orchestrated cycle
 *
 * Target: sub-10ms per tick at 100 Helixes, sub-100ms at 500 Helixes.
 * These are well above typical Constellation sizes (2-16) but validate
 * the O(n^2) physics loop doesn't become a bottleneck at scale.
 */

import { describe, it, expect, vi } from 'vitest'
import { GravityEngine } from '../src/topology/gravity-engine.js'
import { LinkManager } from '../src/topology/link-manager.js'
import { ClusterTracker } from '../src/topology/cluster-tracker.js'
import { TopologyGraph } from '../src/topology/topology-graph.js'
import type { BranchDigest, BranchApproach } from '../src/corpus-types.js'
import {
  DEFAULT_GRAVITY_CONFIG,
  DEFAULT_LINK_CONFIG,
} from '../src/topology/topology-types.js'


// --- Helpers ---

function createMockEmbeddingService() {
  const cache = new Map<string, number[]>()
  const EMBED_DIM = 64

  return {
    async embed(text: string, _mode: string): Promise<number[]> {
      if (cache.has(text)) return cache.get(text)!
      const emb = Array.from({ length: EMBED_DIM }, (_, i) => {
        let h = 0
        for (const ch of text) h = ((h << 5) - h + ch.charCodeAt(0) + i) | 0
        return (h & 0xFFFF) / 0xFFFF
      })
      cache.set(text, emb)
      return emb
    },

    cosineSimilarity(a: number[] | null, b: number[] | null): number {
      if (!a || !b || a.length !== b.length) return 0
      let dot = 0, normA = 0, normB = 0
      for (let i = 0; i < a.length; i++) {
        dot += a[i] * b[i]
        normA += a[i] * a[i]
        normB += b[i] * b[i]
      }
      const denom = Math.sqrt(normA) * Math.sqrt(normB)
      return denom === 0 ? 0 : dot / denom
    },
  }
}

function createMockLogger() {
  const noop = () => {}
  return {
    info: noop,
    warn: noop,
    error: noop,
    debug: noop,
    child: () => createMockLogger(),
  }
}

function createDigest(id: number): BranchDigest {
  const approaches: BranchApproach[] = ['implementation', 'research', 'testing', 'debugging']
  return {
    helixId: `helix-${id}`,
    goalSummary: `Goal for helix ${id}: ${id % 5 === 0 ? 'shared objective' : `unique task ${id}`}`,
    approach: approaches[id % approaches.length],
    progress: 0.5,
    filesActive: Array.from({ length: 3 + (id % 5) }, (_, i) =>
      `src/module-${(id + i) % 20}/file-${i}.ts`,
    ),
    keyFindings: [`Finding ${id}-A`, `Finding ${id}-B`],
    blockers: [],
    currentStrategy: `strategy-${id}`,
    rollingScore: 0.5 + (id % 50) / 100,
    workUnitsProcessed: id,
    updatedAt: Date.now(),
  }
}

function median(arr: number[]): number {
  const sorted = [...arr].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid]
}

function p95(arr: number[]): number {
  const sorted = [...arr].sort((a, b) => a - b)
  return sorted[Math.floor(sorted.length * 0.95)]
}

function formatBench(label: string, times: number[]): string {
  return `${label}: median=${median(times).toFixed(2)}ms  p95=${p95(times).toFixed(2)}ms  min=${Math.min(...times).toFixed(2)}ms  max=${Math.max(...times).toFixed(2)}ms`
}

// --- Benchmarks ---

describe('Topology Performance Benchmarks', () => {

  describe('GravityEngine — Registration', () => {
    const scales = [10, 50, 100, 200] as const

    for (const n of scales) {
      it(`registers ${n} Helixes`, async () => {
        const engine = new GravityEngine({
          embeddingService: createMockEmbeddingService() as any,
          logger: createMockLogger() as any,
          config: DEFAULT_GRAVITY_CONFIG,
        })

        const start = performance.now()
        for (let i = 0; i < n; i++) {
          await engine.registerHelix(`helix-${i}`, createDigest(i))
        }
        const elapsed = performance.now() - start

        const positions = engine.getAllPositions()
        expect(positions).toHaveLength(n)

        // Registration at 200 should complete in under 500ms (mock embeddings are fast)
        expect(elapsed).toBeLessThan(500)
        console.log(`  Registration(${n}): ${elapsed.toFixed(2)}ms (${(elapsed / n).toFixed(3)}ms/helix)`)
      })
    }
  })

  describe('GravityEngine — Physics Tick', () => {
    const scales = [10, 50, 100, 200, 500] as const

    for (const n of scales) {
      it(`ticks with ${n} active Helixes`, async () => {
        const engine = new GravityEngine({
          embeddingService: createMockEmbeddingService() as any,
          logger: createMockLogger() as any,
          config: DEFAULT_GRAVITY_CONFIG,
        })

        // Register all Helixes
        for (let i = 0; i < n; i++) {
          await engine.registerHelix(`helix-${i}`, createDigest(i))
        }

        // Warm up: run a few ticks to stabilize positions
        for (let i = 0; i < 3; i++) {
          await engine.onDigestUpdate(`helix-${i % n}`, createDigest(i % n))
        }

        // Benchmark: 10 ticks
        const tickTimes: number[] = []
        for (let t = 0; t < 10; t++) {
          const helixIdx = t % n
          const start = performance.now()
          await engine.onDigestUpdate(`helix-${helixIdx}`, createDigest(helixIdx))
          tickTimes.push(performance.now() - start)
        }

        console.log(`  ${formatBench(`Tick(${n})`, tickTimes)}`)

        // Performance targets:
        //   n=100: median < 10ms per tick
        //   n=500: median < 100ms per tick
        if (n <= 100) {
          expect(median(tickTimes)).toBeLessThan(10)
        }
        if (n <= 500) {
          expect(median(tickTimes)).toBeLessThan(100)
        }
      })
    }
  })

  describe('LinkManager — Pairwise Evaluation', () => {
    const scales = [10, 50, 100, 200] as const

    for (const n of scales) {
      it(`evaluates ${n} Helixes (${n * (n - 1) / 2} pairs)`, async () => {
        const engine = new GravityEngine({
          embeddingService: createMockEmbeddingService() as any,
          logger: createMockLogger() as any,
          config: DEFAULT_GRAVITY_CONFIG,
        })

        for (let i = 0; i < n; i++) {
          await engine.registerHelix(`helix-${i}`, createDigest(i))
        }

        const linkManager = new LinkManager({
          gravityEngine: engine,
          logger: createMockLogger() as any,
          config: DEFAULT_LINK_CONFIG,
        })

        const activeIds = Array.from({ length: n }, (_, i) => `helix-${i}`)

        // Benchmark: 10 evaluations
        const evalTimes: number[] = []
        for (let t = 0; t < 10; t++) {
          const start = performance.now()
          linkManager.evaluate(activeIds)
          evalTimes.push(performance.now() - start)
        }

        console.log(`  ${formatBench(`LinkEval(${n}, ${n * (n - 1) / 2} pairs)`, evalTimes)}`)

        // n=100: 4,950 pairs — median < 20ms
        // n=200: 19,900 pairs — median < 100ms
        if (n <= 100) {
          expect(median(evalTimes)).toBeLessThan(20)
        }
        if (n <= 200) {
          expect(median(evalTimes)).toBeLessThan(100)
        }
      })
    }
  })

  describe('ClusterTracker — Connected Components', () => {
    const scales = [10, 50, 100, 200] as const

    for (const n of scales) {
      it(`detects clusters in ${n} Helixes`, async () => {
        const engine = new GravityEngine({
          embeddingService: createMockEmbeddingService() as any,
          logger: createMockLogger() as any,
          config: DEFAULT_GRAVITY_CONFIG,
        })

        for (let i = 0; i < n; i++) {
          await engine.registerHelix(`helix-${i}`, createDigest(i))
        }

        const linkManager = new LinkManager({
          gravityEngine: engine,
          logger: createMockLogger() as any,
          config: {
            ...DEFAULT_LINK_CONFIG,
            linkThreshold: 100, // Very permissive — creates many links for stress testing
            unlinkThreshold: 200,
          },
        })

        const activeIds = Array.from({ length: n }, (_, i) => `helix-${i}`)
        linkManager.evaluate(activeIds)

        const clusterTracker = new ClusterTracker({
          linkManager,
          gravityEngine: engine,
          logger: createMockLogger() as any,
        })

        // Benchmark: 10 cluster updates
        const updateTimes: number[] = []
        for (let t = 0; t < 10; t++) {
          const start = performance.now()
          clusterTracker.update(activeIds)
          updateTimes.push(performance.now() - start)
        }

        const clusters = clusterTracker.getAllClusters()
        console.log(`  ${formatBench(`ClusterUpdate(${n})`, updateTimes)} — ${clusters.length} clusters found`)

        // Cluster detection is O(n+e), should be very fast even at scale
        if (n <= 200) {
          expect(median(updateTimes)).toBeLessThan(50)
        }
      })
    }
  })

  describe('Full TopologyGraph — Orchestrated Cycle', () => {
    const scales = [10, 50, 100, 200] as const

    for (const n of scales) {
      it(`full cycle with ${n} Helixes`, async () => {
        const topology = new TopologyGraph({
          embeddingService: createMockEmbeddingService() as any,
          logger: createMockLogger() as any,
          eventBus: {
            emit: () => {},
            on: () => () => {},
            off: () => {},
          } as any,
        })

        // Register all Helixes
        for (let i = 0; i < n; i++) {
          await topology.onDigestUpdate(`helix-${i}`, createDigest(i))
        }

        // Benchmark: 10 full update cycles
        const cycleTimes: number[] = []
        for (let t = 0; t < 10; t++) {
          const helixIdx = t % n
          const start = performance.now()
          await topology.onDigestUpdate(`helix-${helixIdx}`, createDigest(helixIdx))
          cycleTimes.push(performance.now() - start)
        }

        const snapshot = topology.getSnapshot()
        console.log(`  ${formatBench(`FullCycle(${n})`, cycleTimes)} — ${snapshot.links.length} links, ${snapshot.clusters.length} clusters`)

        // Full cycle targets:
        //   n=100: median < 15ms
        //   n=200: median < 100ms
        if (n <= 100) {
          expect(median(cycleTimes)).toBeLessThan(15)
        }
        if (n <= 200) {
          expect(median(cycleTimes)).toBeLessThan(100)
        }
      })
    }
  })

  describe('Snapshot Generation', () => {
    it('snapshot generation at 200 Helixes', async () => {
      const topology = new TopologyGraph({
        embeddingService: createMockEmbeddingService() as any,
        logger: createMockLogger() as any,
        eventBus: {
          emit: () => {},
          on: () => () => {},
          off: () => {},
        } as any,
      })

      for (let i = 0; i < 200; i++) {
        await topology.onDigestUpdate(`helix-${i}`, createDigest(i))
      }

      // Benchmark: 100 snapshot reads
      const snapshotTimes: number[] = []
      for (let t = 0; t < 100; t++) {
        const start = performance.now()
        topology.getSnapshot()
        snapshotTimes.push(performance.now() - start)
      }

      console.log(`  ${formatBench('Snapshot(200)', snapshotTimes)}`)

      // Snapshot should be essentially instant — just reading state
      expect(median(snapshotTimes)).toBeLessThan(5)
    })
  })

  describe('Distance Matrix', () => {
    it('builds distance matrix at 200 Helixes (39,800 pairs)', async () => {
      const engine = new GravityEngine({
        embeddingService: createMockEmbeddingService() as any,
        logger: createMockLogger() as any,
        config: DEFAULT_GRAVITY_CONFIG,
      })

      for (let i = 0; i < 200; i++) {
        await engine.registerHelix(`helix-${i}`, createDigest(i))
      }

      // Benchmark: 10 matrix builds
      const matrixTimes: number[] = []
      for (let t = 0; t < 10; t++) {
        const start = performance.now()
        engine.getDistanceMatrix()
        matrixTimes.push(performance.now() - start)
      }

      console.log(`  ${formatBench('DistanceMatrix(200, 39800 pairs)', matrixTimes)}`)

      // Pure arithmetic — should be fast
      expect(median(matrixTimes)).toBeLessThan(50)
    })
  })

  describe('Scaling Analysis', () => {
    it('measures O(n^2) scaling factor', async () => {
      const measurements: Array<{ n: number; tickMs: number }> = []

      for (const n of [10, 25, 50, 100]) {
        const engine = new GravityEngine({
          embeddingService: createMockEmbeddingService() as any,
          logger: createMockLogger() as any,
          config: DEFAULT_GRAVITY_CONFIG,
        })

        for (let i = 0; i < n; i++) {
          await engine.registerHelix(`helix-${i}`, createDigest(i))
        }

        // Warm up
        await engine.onDigestUpdate('helix-0', createDigest(0))

        // Measure
        const times: number[] = []
        for (let t = 0; t < 5; t++) {
          const start = performance.now()
          await engine.onDigestUpdate(`helix-${t % n}`, createDigest(t % n))
          times.push(performance.now() - start)
        }

        measurements.push({ n, tickMs: median(times) })
      }

      console.log('\n  Scaling analysis (should show ~4x increase per 2x n if O(n^2)):')
      for (let i = 0; i < measurements.length; i++) {
        const m = measurements[i]
        const ratio = i > 0 ? (m.tickMs / measurements[i - 1].tickMs).toFixed(2) : '-'
        const nRatio = i > 0 ? (m.n / measurements[i - 1].n).toFixed(2) : '-'
        console.log(`    n=${m.n.toString().padStart(4)}: ${m.tickMs.toFixed(3)}ms  (n-ratio: ${nRatio}, time-ratio: ${ratio})`)
      }

      // Verify the largest scale is still fast
      const largest = measurements[measurements.length - 1]
      expect(largest.tickMs).toBeLessThan(10)
    })
  })

  describe('Embedding Cache — Repeated Digest Updates', () => {
    const N = 50

    it(`measures cache hit speedup with ${N} Helixes and repeated digests`, async () => {
      const topology = new TopologyGraph({
        embeddingService: createMockEmbeddingService() as any,
        logger: createMockLogger() as any,
        eventBus: {
          emit: () => {},
          on: () => () => {},
          off: () => {},
        } as any,
      })

      // Initial registration — all cache misses
      for (let i = 0; i < N; i++) {
        await topology.onDigestUpdate(`helix-${i}`, createDigest(i))
      }

      // Round 1: Same digests again — should hit cache for all embeddings
      const cachedTimes: number[] = []
      for (let t = 0; t < 10; t++) {
        const helixIdx = t % N
        const start = performance.now()
        await topology.onDigestUpdate(`helix-${helixIdx}`, createDigest(helixIdx))
        cachedTimes.push(performance.now() - start)
      }

      const metrics = topology.getCacheMetrics()
      console.log(`  EmbeddingCache(${N}): hitRate=${(topology.cacheHitRate * 100).toFixed(1)}%  hits=${metrics.hits}  misses=${metrics.misses}`)
      console.log(`  ${formatBench(`CachedCycle(${N})`, cachedTimes)}`)

      // WHY: Overall hit rate includes cold-start misses from initial registration.
      // The cache's value is that repeated identical digests produce hits (> 0),
      // not that the overall rate exceeds a threshold.
      expect(metrics.hits).toBeGreaterThan(0)
      // Cached cycles should be fast
      expect(median(cachedTimes)).toBeLessThan(10)
    })

    it('cache misses on changed findings', async () => {
      const topology = new TopologyGraph({
        embeddingService: createMockEmbeddingService() as any,
        logger: createMockLogger() as any,
        eventBus: {
          emit: () => {},
          on: () => () => {},
          off: () => {},
        } as any,
      })

      // Register with initial findings
      for (let i = 0; i < 10; i++) {
        await topology.onDigestUpdate(`helix-${i}`, createDigest(i))
      }
      const metricsAfterInit = topology.getCacheMetrics()

      // Update with changed findings — should be cache misses
      for (let i = 0; i < 10; i++) {
        const digest = createDigest(i)
        digest.keyFindings = [`New finding ${i}-${Date.now()}`]
        await topology.onDigestUpdate(`helix-${i}`, digest)
      }

      const metricsAfterChange = topology.getCacheMetrics()
      // New misses should have been recorded
      expect(metricsAfterChange.misses).toBeGreaterThan(metricsAfterInit.misses)
    })
  })
})
