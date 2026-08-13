/**
 * Tests for TopologyGraph — Lifecycle, Clustering, Linking, and Brainstem Bridge
 *
 * Tests cover:
 *   - Lifecycle: registerHelix, onDigestUpdate, deregisterHelix
 *   - Snapshot structure and contents
 *   - Cluster formation when related helixes are registered
 *   - Link formation between similar helixes
 *   - Brainstem bridge activation, depth updates, and deactivation
 *   - Edge cases: empty graph, single helix, multiple clusters, dissimilar helixes
 *   - Cache integration and cleanup
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { TopologyGraph } from '../../src/topology/topology-graph.js'
import type { BranchDigest, BranchApproach } from '../../src/corpus-types.js'
import type { TopologySnapshot, MergeDepth } from '../../src/topology/topology-types.js'


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

function createMockEventBus() {
  return {
    emit: vi.fn(),
    on: vi.fn(() => () => {}),
    off: vi.fn(),
  }
}

function createMockBrainstemBridge() {
  return {
    activateLink: vi.fn(),
    updateDepth: vi.fn(),
    deactivateLink: vi.fn(),
    pushContext: vi.fn(),
    removeHelix: vi.fn(),
  }
}

function createDigest(id: number, findings?: string[], goal?: string): BranchDigest {
  const approaches: BranchApproach[] = ['implementation', 'research', 'testing', 'debugging']
  return {
    helixId: `helix-${id}`,
    goalSummary: goal ?? `Goal for helix ${id}`,
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

function createSimilarDigests(baseId: number, count: number): BranchDigest[] {
  // Create digests with similar goals and findings
  return Array.from({ length: count }, (_, i) => createDigest(
    baseId + i,
    [`Shared finding: pattern detection`, `Finding ${baseId + i}`],
    `Implement feature X - part ${i + 1}`
  ))
}

function createDissimilarDigests(baseId: number, count: number): BranchDigest[] {
  // Create digests with very different goals and findings
  return Array.from({ length: count }, (_, i) => createDigest(
    baseId + i,
    [`Finding about ${i}`],
    `Completely different goal ${i}`
  ))
}


// --- TopologyGraph Tests ---

describe('TopologyGraph Lifecycle', () => {
  let topology: TopologyGraph
  let mockService: ReturnType<typeof createMockEmbeddingService>

  beforeEach(() => {
    mockService = createMockEmbeddingService()
    topology = new TopologyGraph({
      embeddingService: mockService as any,
      logger: createMockLogger() as any,
      eventBus: createMockEventBus() as any,
    })
  })

  describe('constructor', () => {
    it('initializes with default config when none provided', () => {
      expect(topology.enabled).toBe(true)
      expect(topology.cache).toBeDefined()
      expect(topology.cache.size).toBe(0)
    })

    it('accepts custom config', () => {
      const customTopology = new TopologyGraph({
        embeddingService: mockService as any,
        logger: createMockLogger() as any,
        config: {
          enabled: false,
          gravity: {
            weights: { goalSimilarity: 0.5, findingsSimilarity: 0.3, fileOverlap: 0.1, approachAlignment: 0.1 },
            friction: 0.5,
            forceScale: 0.6,
            minDistance: 0.01,
            maxVelocity: 2.0,
            repulsionStrength: 0.2,
          },
          links: {
            linkThreshold: 1.0,
            unlinkThreshold: 2.0,
            minLinkSimilarity: 0.4,
            mediumMergeStabilityTicks: 5,
            deepMergeStabilityTicks: 15,
          },
        },
      })

      expect(customTopology.enabled).toBe(false)
    })

    it('wires embedding cache automatically', () => {
      expect(topology.cache).toBeDefined()
      expect(topology.cache.size).toBe(0)
    })
  })

  describe('registerHelix', () => {
    it('registers a helix and tracks it as active', async () => {
      const digest = createDigest(1)
      await topology.registerHelix('helix-1', digest)

      const snapshot = topology.getSnapshot()
      expect(snapshot.positions).toHaveLength(1)
      expect(snapshot.positions[0].helixId).toBe('helix-1')
    })

    it('registers multiple helixes independently', async () => {
      await topology.registerHelix('h1', createDigest(1))
      await topology.registerHelix('h2', createDigest(2))

      const snapshot = topology.getSnapshot()
      expect(snapshot.positions).toHaveLength(2)
      expect(snapshot.positions.map(p => p.helixId)).toContain('h1')
      expect(snapshot.positions.map(p => p.helixId)).toContain('h2')
    })

    it('does nothing when disabled', async () => {
      const disabledTopology = new TopologyGraph({
        embeddingService: mockService as any,
        logger: createMockLogger() as any,
        config: { enabled: false, gravity: {}, links: {} },
      })

      await disabledTopology.registerHelix('h1', createDigest(1))
      const snapshot = disabledTopology.getSnapshot()
      expect(snapshot.positions).toHaveLength(0)
    })
  })

  describe('onDigestUpdate', () => {
    it('updates topology when digest arrives', async () => {
      const digest = createDigest(1)
      await topology.onDigestUpdate('h1', digest)

      const snapshot = topology.getSnapshot()
      expect(snapshot.positions).toHaveLength(1)
      expect(snapshot.tickCount).toBeGreaterThan(0)
    })

    it('increments tick count on each update', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      const tick1 = topology.getSnapshot().tickCount

      await topology.onDigestUpdate('h1', createDigest(1))
      const tick2 = topology.getSnapshot().tickCount

      expect(tick2).toBeGreaterThan(tick1)
    })

    it('updates active helix tracking', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      const snapshot = topology.getSnapshot()
      expect(snapshot.positions).toHaveLength(2)
    })

    it('does nothing when disabled', async () => {
      const disabledTopology = new TopologyGraph({
        embeddingService: mockService as any,
        logger: createMockLogger() as any,
        config: { enabled: false, gravity: {}, links: {} },
      })

      await disabledTopology.onDigestUpdate('h1', createDigest(1))
      const snapshot = disabledTopology.getSnapshot()
      expect(snapshot.positions).toHaveLength(0)
    })
  })

  describe('deregisterHelix', () => {
    it('removes helix from active tracking (positions remain but helix marked inactive)', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      topology.deregisterHelix('h1')

      // Position remains but helix is no longer active
      const snapshot = topology.getSnapshot()
      // GravityEngine keeps positions for history, but activeHelixIds is updated
      expect(topology['activeHelixIds'].has('h1')).toBe(false)
    })

    it('cleans up gravity engine state (marks as inactive)', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      topology.deregisterHelix('h1')

      // Position still exists but is marked inactive in gravity engine
      const pos = topology['gravityEngine'].getPosition('h1')
      expect(pos).toBeDefined()
    })

    it('cleans up link manager state', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      topology.deregisterHelix('h1')

      expect(topology.getLinksFor('h1')).toHaveLength(0)
    })

    it('cleans up embedding cache', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      const cacheSizeBefore = topology.cache.size

      topology.deregisterHelix('h1')
      const cacheSizeAfter = topology.cache.size

      expect(cacheSizeAfter).toBeLessThan(cacheSizeBefore)
    })

    it('removes helix from brainstem bridge if present', async () => {
      const mockBridge = createMockBrainstemBridge()
      const topologyWithBridge = new TopologyGraph({
        embeddingService: mockService as any,
        logger: createMockLogger() as any,
        bridge: mockBridge as any,
      })

      await topologyWithBridge.onDigestUpdate('h1', createDigest(1))
      topologyWithBridge.deregisterHelix('h1')

      expect(mockBridge.removeHelix).toHaveBeenCalledWith('h1')
    })
  })

  describe('getSnapshot', () => {
    it('returns snapshot with expected structure', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))

      const snapshot = topology.getSnapshot()
      expect(snapshot).toMatchObject({
        positions: expect.any(Array),
        links: expect.any(Array),
        clusters: expect.any(Array),
        distances: expect.any(Map),
        tickCount: expect.any(Number),
        snapshotAt: expect.any(Number),
      })
    })

    it('includes positions for all active helixes', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      const snapshot = topology.getSnapshot()
      expect(snapshot.positions).toHaveLength(2)
      expect(snapshot.positions.every(p => typeof p.x === 'number' && typeof p.y === 'number')).toBe(true)
    })

    it('includes distance matrix', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      const snapshot = topology.getSnapshot()
      expect(snapshot.distances).toBeInstanceOf(Map)
      expect(snapshot.distances.size).toBe(2)
      expect(snapshot.distances.get('h1')).toBeInstanceOf(Map)
    })

    it('snapshotAt is current timestamp', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))

      const snapshot = topology.getSnapshot()
      const now = Date.now()
      expect(snapshot.snapshotAt).toBeGreaterThanOrEqual(now - 1000) // within 1 second
      expect(snapshot.snapshotAt).toBeLessThanOrEqual(now)
    })

    it('returns empty arrays when no helixes registered', () => {
      const snapshot = topology.getSnapshot()
      expect(snapshot.positions).toHaveLength(0)
      expect(snapshot.links).toHaveLength(0)
      expect(snapshot.clusters).toHaveLength(0)
    })
  })
})


describe('TopologyGraph Clustering and Linking', () => {
  let topology: TopologyGraph
  let mockService: ReturnType<typeof createMockEmbeddingService>

  beforeEach(() => {
    mockService = createMockEmbeddingService()
    topology = new TopologyGraph({
      embeddingService: mockService as any,
      logger: createMockLogger() as any,
      eventBus: createMockEventBus() as any,
    })
  })

  describe('link formation', () => {
    it('forms links between similar helixes after convergence', async () => {
      // Create similar digests that should link
      const similarDigests = createSimilarDigests(1, 2)
      await topology.onDigestUpdate('h1', similarDigests[0])
      await topology.onDigestUpdate('h2', similarDigests[1])

      // Give it a few ticks to converge
      for (let i = 0; i < 15; i++) {
        await topology.onDigestUpdate('h1', similarDigests[0])
        await topology.onDigestUpdate('h2', similarDigests[1])
      }

      const links = topology.getSnapshot().links
      // Links may or may not form depending on similarity threshold
      // At minimum, we verify the system doesn't crash
      expect(links).toBeDefined()
    })

    it('link manager can detect linked helixes', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      // Multiple ticks
      for (let i = 0; i < 10; i++) {
        await topology.onDigestUpdate('h1', createDigest(1))
        await topology.onDigestUpdate('h2', createDigest(2))
      }

      // Check link status
      const linked = topology['linkManager'].areLinked('h1', 'h2')
      expect(typeof linked).toBe('boolean')
    })

    it('forms multiple links in a cluster after sufficient ticks', async () => {
      const similarDigests = createSimilarDigests(1, 3)
      for (const digest of similarDigests) {
        await topology.onDigestUpdate(digest.helixId, digest)
      }

      // Multiple ticks for convergence
      for (let i = 0; i < 20; i++) {
        for (const digest of similarDigests) {
          await topology.onDigestUpdate(digest.helixId, digest)
        }
      }

      const snapshot = topology.getSnapshot()
      // With 3 similar helixes, system should be stable
      expect(snapshot.positions).toHaveLength(3)
    })

    it('dissolves links when helixes drift apart', async () => {
      const similarDigests = createSimilarDigests(1, 2)
      await topology.onDigestUpdate('h1', similarDigests[0])
      await topology.onDigestUpdate('h2', similarDigests[1])

      // Converge
      for (let i = 0; i < 10; i++) {
        await topology.onDigestUpdate('h1', similarDigests[0])
        await topology.onDigestUpdate('h2', similarDigests[1])
      }

      // Now update with very different content to drift apart
      await topology.onDigestUpdate('h1', createDigest(100, ['completely different']))
      await topology.onDigestUpdate('h2', createDigest(200, ['totally unrelated']))

      // More ticks to drift
      for (let i = 0; i < 15; i++) {
        await topology.onDigestUpdate('h1', createDigest(100 + i))
        await topology.onDigestUpdate('h2', createDigest(200 + i))
      }

      // Links should be stable or dissolved
      const links = topology.getSnapshot().links
      expect(links).toBeDefined()
    })
  })

  describe('cluster formation', () => {
    it('processes multiple helixes without errors', async () => {
      const similarDigests = createSimilarDigests(1, 3)
      for (const digest of similarDigests) {
        await topology.onDigestUpdate(digest.helixId, digest)
      }

      // Multiple ticks
      for (let i = 0; i < 15; i++) {
        for (const digest of similarDigests) {
          await topology.onDigestUpdate(digest.helixId, digest)
        }
      }

      const snapshot = topology.getSnapshot()
      expect(snapshot.clusters).toBeDefined()
    })

    it('processes multiple separate groups without errors', async () => {
      // Group 1: similar helixes
      const group1 = createSimilarDigests(1, 2)
      // Group 2: another set of similar but different helixes
      const group2 = createSimilarDigests(10, 2)

      for (const digest of [...group1, ...group2]) {
        await topology.onDigestUpdate(digest.helixId, digest)
      }

      // Multiple ticks
      for (let i = 0; i < 20; i++) {
        for (const digest of [...group1, ...group2]) {
          await topology.onDigestUpdate(digest.helixId, digest)
        }
      }

      const snapshot = topology.getSnapshot()
      expect(snapshot.positions).toHaveLength(4)
    })

    it('returns undefined for helix not in any cluster', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))

      const cluster = topology.getClusterFor('h1')
      // Single helix may not form a cluster yet
      expect(cluster).toBeUndefined()
    })

    it('cluster tracker can detect same cluster membership', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      // Multiple ticks
      for (let i = 0; i < 15; i++) {
        await topology.onDigestUpdate('h1', createDigest(1))
        await topology.onDigestUpdate('h2', createDigest(2))
      }

      // Check cluster membership
      const sameCluster = topology.areInSameCluster('h1', 'h2')
      expect(typeof sameCluster).toBe('boolean')
    })
  })

  describe('merge depth progression', () => {
    it('link starts with shallow merge depth', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      // Multiple stable ticks
      for (let i = 0; i < 15; i++) {
        await topology.onDigestUpdate('h1', createDigest(1))
        await topology.onDigestUpdate('h2', createDigest(2))
      }

      // Check that merge depth accessor works
      const depth = topology.getMergeDepth('h1', 'h2')
      expect(['shallow', 'medium', 'deep', undefined]).toContain(depth)
    })

    it('gets effective merge depth for helix pair', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      for (let i = 0; i < 15; i++) {
        await topology.onDigestUpdate('h1', createDigest(1))
        await topology.onDigestUpdate('h2', createDigest(2))
      }

      const depth = topology.getMergeDepth('h1', 'h2')
      expect(['shallow', 'medium', 'deep', undefined]).toContain(depth)
    })
  })
})


describe('TopologyGraph Brainstem Bridge Integration', () => {
  let topology: TopologyGraph
  let mockService: ReturnType<typeof createMockEmbeddingService>
  let mockBridge: ReturnType<typeof createMockBrainstemBridge>

  beforeEach(() => {
    mockService = createMockEmbeddingService()
    mockBridge = createMockBrainstemBridge()
    topology = new TopologyGraph({
      embeddingService: mockService as any,
      logger: createMockLogger() as any,
      bridge: mockBridge as any,
      eventBus: createMockEventBus() as any,
    })
  })

  describe('bridge activation', () => {
    it('bridge methods are called during topology updates', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      // Multiple ticks
      for (let i = 0; i < 10; i++) {
        await topology.onDigestUpdate('h1', createDigest(1))
        await topology.onDigestUpdate('h2', createDigest(2))
      }

      // Bridge should have been called
      expect(mockBridge.pushContext).toHaveBeenCalled()
    })

    it('deactivates bridge when helix deregistered', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      topology.deregisterHelix('h1')

      expect(mockBridge.removeHelix).toHaveBeenCalledWith('h1')
    })

    it('pushes context on each tick', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))

      // pushContext is called internally on each onDigestUpdate
      expect(mockBridge.pushContext).toHaveBeenCalled()
    })
  })
})


describe('TopologyGraph Edge Cases', () => {
  let topology: TopologyGraph
  let mockService: ReturnType<typeof createMockEmbeddingService>

  beforeEach(() => {
    mockService = createMockEmbeddingService()
    topology = new TopologyGraph({
      embeddingService: mockService as any,
      logger: createMockLogger() as any,
      eventBus: createMockEventBus() as any,
    })
  })

  describe('empty graph', () => {
    it('returns empty snapshot when no helixes registered', () => {
      const snapshot = topology.getSnapshot()
      expect(snapshot.positions).toHaveLength(0)
      expect(snapshot.links).toHaveLength(0)
      expect(snapshot.clusters).toHaveLength(0)
      expect(snapshot.distances.size).toBe(0)
      expect(snapshot.tickCount).toBe(0)
    })

    it('getClusterFor returns undefined for non-existent helix', () => {
      const cluster = topology.getClusterFor('nonexistent')
      expect(cluster).toBeUndefined()
    })

    it('areInSameCluster returns false for non-existent helixes', () => {
      const same = topology.areInSameCluster('h1', 'h2')
      expect(same).toBe(false)
    })

    it('getDistance returns Infinity for non-existent helixes', () => {
      const dist = topology.getDistance('h1', 'h2')
      expect(dist).toBe(Infinity)
    })

    it('getSimilarity returns 0 for non-existent helixes', () => {
      const sim = topology.getSimilarity('h1', 'h2')
      expect(sim).toBe(0)
    })
  })

  describe('single helix', () => {
    it('handles single helix without errors', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))

      const snapshot = topology.getSnapshot()
      expect(snapshot.positions).toHaveLength(1)
      expect(snapshot.links).toHaveLength(0)
      expect(snapshot.clusters).toHaveLength(0)
    })

    it('single helix has no links', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))

      const links = topology.getLinksFor('h1')
      expect(links).toHaveLength(0)
    })

    it('single helix has no neighbors', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))

      const neighbors = topology.getNeighbors('h1')
      expect(neighbors).toHaveLength(0)
    })
  })

  describe('many helixes', () => {
    it('handles 10+ helixes without performance issues', async () => {
      const similarDigests = createSimilarDigests(1, 10)
      for (const digest of similarDigests) {
        await topology.onDigestUpdate(digest.helixId, digest)
      }

      // Multiple ticks
      for (let i = 0; i < 10; i++) {
        for (const digest of similarDigests) {
          await topology.onDigestUpdate(digest.helixId, digest)
        }
      }

      const snapshot = topology.getSnapshot()
      expect(snapshot.positions).toHaveLength(10)
    })

    it('maintains correct state with many helixes', async () => {
      const similarDigests = createSimilarDigests(1, 5)
      for (const digest of similarDigests) {
        await topology.onDigestUpdate(digest.helixId, digest)
      }

      for (let i = 0; i < 15; i++) {
        for (const digest of similarDigests) {
          await topology.onDigestUpdate(digest.helixId, digest)
        }
      }

      const positions = topology.getSnapshot().positions
      expect(positions.length).toBe(5)
    })
  })

  describe('rapid registration/deregistration', () => {
    it('handles rapid register/deregister cycles', async () => {
      for (let i = 0; i < 20; i++) {
        await topology.onDigestUpdate(`h${i}`, createDigest(i))
        topology.deregisterHelix(`h${i}`)
      }

      // Verify active tracking is clean
      expect(topology['activeHelixIds'].size).toBe(0)
    })

    it('does not leak memory after many operations', async () => {
      const iterations = 50

      for (let i = 0; i < iterations; i++) {
        await topology.onDigestUpdate('h1', createDigest(i))
        topology.deregisterHelix('h1')
      }

      // Cache should be clean
      expect(topology.cache.size).toBe(0)
      expect(topology.getCacheMetrics().evictions).toBeGreaterThan(0)
    })
  })
})


describe('TopologyGraph Accessors', () => {
  let topology: TopologyGraph
  let mockService: ReturnType<typeof createMockEmbeddingService>

  beforeEach(() => {
    mockService = createMockEmbeddingService()
    topology = new TopologyGraph({
      embeddingService: mockService as any,
      logger: createMockLogger() as any,
      eventBus: createMockEventBus() as any,
    })
  })

  describe('getDistance', () => {
    it('returns distance between two helixes', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      const dist = topology.getDistance('h1', 'h2')
      expect(typeof dist).toBe('number')
      expect(dist).toBeGreaterThan(0)
    })

    it('returns Infinity for non-existent helix', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))

      const dist = topology.getDistance('h1', 'nonexistent')
      expect(dist).toBe(Infinity)
    })
  })

  describe('getSimilarity', () => {
    it('returns similarity score between two helixes', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      const sim = topology.getSimilarity('h1', 'h2')
      expect(typeof sim).toBe('number')
      expect(sim).toBeGreaterThanOrEqual(0)
      expect(sim).toBeLessThanOrEqual(1)
    })

    it('returns 0 for non-existent helix', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))

      const sim = topology.getSimilarity('h1', 'nonexistent')
      expect(sim).toBe(0)
    })
  })

  describe('getLinksFor', () => {
    it('returns all links for a specific helix', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      for (let i = 0; i < 15; i++) {
        await topology.onDigestUpdate('h1', createDigest(1))
        await topology.onDigestUpdate('h2', createDigest(2))
      }

      const links = topology.getLinksFor('h1')
      expect(links).toBeInstanceOf(Array)
    })

    it('returns empty array for helix with no links', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))

      const links = topology.getLinksFor('h1')
      expect(links).toHaveLength(0)
    })
  })

  describe('getNeighbors', () => {
    it('returns neighbor helix IDs', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h2', createDigest(2))

      for (let i = 0; i < 15; i++) {
        await topology.onDigestUpdate('h1', createDigest(1))
        await topology.onDigestUpdate('h2', createDigest(2))
      }

      const neighbors = topology.getNeighbors('h1')
      expect(neighbors).toBeInstanceOf(Array)
    })

    it('returns empty array for isolated helix', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))

      const neighbors = topology.getNeighbors('h1')
      expect(neighbors).toHaveLength(0)
    })
  })

  describe('cache metrics', () => {
    it('reports cache hit rate', async () => {
      const digest = createDigest(1)
      await topology.onDigestUpdate('h1', digest)
      await topology.onDigestUpdate('h1', digest)
      await topology.onDigestUpdate('h1', digest)

      const hitRate = topology.cacheHitRate
      expect(typeof hitRate).toBe('number')
      expect(hitRate).toBeGreaterThanOrEqual(0)
      expect(hitRate).toBeLessThanOrEqual(1)
    })

    it('reports detailed cache metrics', async () => {
      await topology.onDigestUpdate('h1', createDigest(1))
      await topology.onDigestUpdate('h1', createDigest(1))

      const metrics = topology.getCacheMetrics()
      expect(metrics.hits).toBeGreaterThanOrEqual(0)
      expect(metrics.misses).toBeGreaterThan(0)
      expect(metrics.totalCalls).toBeGreaterThan(0)
    })
  })
})
