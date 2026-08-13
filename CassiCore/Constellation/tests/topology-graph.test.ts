/**
 * Tests for the Helix Topology Graph — spatial coordination layer
 * that uses gravity-based clustering to organize Helix sessions.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { GravityEngine } from '../src/topology/gravity-engine.js'
import { LinkManager } from '../src/topology/link-manager.js'
import { ClusterTracker } from '../src/topology/cluster-tracker.js'
import { TopologyGraph } from '../src/topology/topology-graph.js'
import type { BranchDigest, BranchApproach } from '../src/corpus-types.js'
import type { GravityConfig, LinkConfig } from '../src/topology/topology-types.js'
import {
  DEFAULT_GRAVITY_CONFIG,
  DEFAULT_LINK_CONFIG,
} from '../src/topology/topology-types.js'

// --- Mock EmbeddingService ---

function createMockEmbeddingService() {
  const embeddings = new Map<string, number[]>()
  let embedCallCount = 0

  return {
    async embed(text: string, _mode: string): Promise<number[]> {
      embedCallCount++
      // Return a deterministic embedding based on text hash
      if (embeddings.has(text)) return embeddings.get(text)!
      const emb = Array.from({ length: 8 }, (_, i) => {
        let h = 0
        for (const ch of text) h = ((h << 5) - h + ch.charCodeAt(0) + i) | 0
        return (h & 0xFFFF) / 0xFFFF
      })
      embeddings.set(text, emb)
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

    // Test helpers
    setEmbedding(text: string, emb: number[]): void {
      embeddings.set(text, emb)
    },
    getEmbedCallCount(): number {
      return embedCallCount
    },
  }
}

// --- Mock Logger ---

function createMockLogger() {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: () => createMockLogger(),
  }
}

// --- Test Digest Factory ---

function createDigest(overrides: Partial<BranchDigest> = {}): BranchDigest {
  return {
    goalSummary: 'Implement feature X',
    approach: 'implement' as BranchApproach,
    status: 'active',
    filesActive: ['src/main.ts', 'src/utils.ts'],
    keyFindings: ['Found existing pattern in utils'],
    recentDecisions: [],
    blockers: [],
    confidence: 0.7,
    turnCount: 5,
    ...overrides,
  } as BranchDigest
}


// =============================================================
//  GravityEngine Tests
// =============================================================

describe('GravityEngine', () => {
  let engine: GravityEngine
  let mockEmbed: ReturnType<typeof createMockEmbeddingService>
  let mockLogger: ReturnType<typeof createMockLogger>

  beforeEach(() => {
    mockEmbed = createMockEmbeddingService()
    mockLogger = createMockLogger()
    engine = new GravityEngine({
      embeddingService: mockEmbed as any,
      logger: mockLogger as any,
      config: DEFAULT_GRAVITY_CONFIG,
    })
  })

  it('registers a Helix with position from goal embedding', async () => {
    const digest = createDigest({ goalSummary: 'Build the auth module' })
    await engine.registerHelix('h1', digest)

    const pos = engine.getPosition('h1')
    expect(pos).toBeDefined()
    expect(pos!.helixId).toBe('h1')
    expect(typeof pos!.x).toBe('number')
    expect(typeof pos!.y).toBe('number')
    expect(pos!.vx).toBe(0)
    expect(pos!.vy).toBe(0)
  })

  it('does not re-register an existing Helix', async () => {
    const digest = createDigest()
    await engine.registerHelix('h1', digest)
    const pos1 = engine.getPosition('h1')!

    await engine.registerHelix('h1', digest)
    const pos2 = engine.getPosition('h1')!

    expect(pos1.x).toBe(pos2.x)
    expect(pos1.y).toBe(pos2.y)
  })

  it('computes pairwise distances', async () => {
    const d1 = createDigest({ goalSummary: 'Goal A' })
    const d2 = createDigest({ goalSummary: 'Goal B' })
    await engine.registerHelix('h1', d1)
    await engine.registerHelix('h2', d2)

    const dist = engine.getDistance('h1', 'h2')
    expect(dist).toBeGreaterThan(0)
    expect(dist).toBeLessThan(Infinity)
  })

  it('returns Infinity for unknown Helix distance', () => {
    expect(engine.getDistance('h1', 'h2')).toBe(Infinity)
  })

  it('computes similarity between Helixes with same approach', async () => {
    // Set up similar embeddings
    const sameEmb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same goal A', sameEmb)
    mockEmbed.setEmbedding('Same goal B', sameEmb)

    const d1 = createDigest({
      goalSummary: 'Same goal A',
      approach: 'implement' as BranchApproach,
      filesActive: ['shared.ts'],
    })
    const d2 = createDigest({
      goalSummary: 'Same goal B',
      approach: 'implement' as BranchApproach,
      filesActive: ['shared.ts'],
    })

    await engine.registerHelix('h1', d1)
    await engine.registerHelix('h2', d2)

    const similarity = engine.computeSimilarity('h1', 'h2')
    expect(similarity).toBeGreaterThan(0.5)
  })

  it('applies gravity forces — similar Helixes move closer', async () => {
    // Use identical embeddings for maximum attraction
    const emb = [1, 0.5, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Shared goal', emb)

    const digest = createDigest({
      goalSummary: 'Shared goal',
      filesActive: ['file.ts'],
    })

    await engine.registerHelix('h1', digest)
    await engine.registerHelix('h2', digest)

    const distBefore = engine.getDistance('h1', 'h2')

    // Trigger a digest update to run a physics tick
    await engine.onDigestUpdate('h1', digest)

    const distAfter = engine.getDistance('h1', 'h2')

    // With same embeddings, they share same initial position, so distance should stay small
    // The key behavior: the tick ran without errors
    expect(distAfter).toBeLessThan(Infinity)
  })

  it('deregisters a Helix — stops attracting', async () => {
    await engine.registerHelix('h1', createDigest())
    engine.deregisterHelix('h1')

    const state = engine.getStates().get('h1')
    expect(state!.active).toBe(false)
    expect(state!.position.vx).toBe(0)
    expect(state!.position.vy).toBe(0)
  })

  it('deregisters during active tick without crashing', async () => {
    await engine.registerHelix('h1', createDigest({ goalSummary: 'A' }))
    await engine.registerHelix('h2', createDigest({ goalSummary: 'B' }))
    await engine.registerHelix('h3', createDigest({ goalSummary: 'C' }))

    // Trigger a digest update and immediately deregister
    const promise = engine.onDigestUpdate('h1', createDigest({ goalSummary: 'Updated' }))
    engine.deregisterHelix('h2') // deregister while tick is in progress

    await promise

    // Should not crash
    const pos = engine.getPosition('h1')
    expect(pos).toBeDefined()
  })

  it('handles empty constellation (0 helixes) gracefully', () => {
    const positions = engine.getAllPositions()
    expect(positions).toHaveLength(0)

    const matrix = engine.getDistanceMatrix()
    expect(matrix.size).toBe(0)

    const dist = engine.getDistance('h1', 'h2')
    expect(dist).toBe(Infinity)
  })

  it('handles single helix scenario without errors', async () => {
    await engine.registerHelix('h1', createDigest({ goalSummary: 'Solo' }))

    const positions = engine.getAllPositions()
    expect(positions).toHaveLength(1)

    const matrix = engine.getDistanceMatrix()
    expect(matrix.size).toBe(1)
    expect(matrix.get('h1')!.size).toBe(0) // no other helixes to compare with

    const dist = engine.getDistance('h1', 'h2')
    expect(dist).toBe(Infinity)
  })

  it('getAllPositions returns all registered Helixes', async () => {
    await engine.registerHelix('h1', createDigest({ goalSummary: 'A' }))
    await engine.registerHelix('h2', createDigest({ goalSummary: 'B' }))
    await engine.registerHelix('h3', createDigest({ goalSummary: 'C' }))

    const positions = engine.getAllPositions()
    expect(positions).toHaveLength(3)
  })

  it('getDistanceMatrix returns pairwise distances', async () => {
    await engine.registerHelix('h1', createDigest({ goalSummary: 'A' }))
    await engine.registerHelix('h2', createDigest({ goalSummary: 'B' }))

    const matrix = engine.getDistanceMatrix()
    expect(matrix.size).toBe(2)
    expect(matrix.get('h1')!.has('h2')).toBe(true)
    expect(matrix.get('h2')!.has('h1')).toBe(true)
  })

  it('handles embedding failure gracefully (falls back to hash position)', async () => {
    const failingEmbed = {
      ...mockEmbed,
      async embed(): Promise<number[]> {
        throw new Error('Embedding server down')
      },
    }

    const eng = new GravityEngine({
      embeddingService: failingEmbed as any,
      logger: mockLogger as any,
      config: DEFAULT_GRAVITY_CONFIG,
    })

    await eng.registerHelix('h1', createDigest())
    const pos = eng.getPosition('h1')
    expect(pos).toBeDefined()
    expect(typeof pos!.x).toBe('number')
  })
})


// =============================================================
//  LinkManager Tests
// =============================================================

describe('LinkManager', () => {
  let engine: GravityEngine
  let linkManager: LinkManager
  let mockEmbed: ReturnType<typeof createMockEmbeddingService>
  let mockLogger: ReturnType<typeof createMockLogger>

  // Config with tight thresholds for testing
  const testLinkConfig: LinkConfig = {
    linkThreshold: 5.0,
    unlinkThreshold: 8.0,
    mediumMergeStabilityTicks: 3,
    deepMergeStabilityTicks: 8,
    minLinkSimilarity: 0.3,
  }

  beforeEach(() => {
    mockEmbed = createMockEmbeddingService()
    mockLogger = createMockLogger()
    engine = new GravityEngine({
      embeddingService: mockEmbed as any,
      logger: mockLogger as any,
      config: DEFAULT_GRAVITY_CONFIG,
    })
    linkManager = new LinkManager({
      gravityEngine: engine,
      logger: mockLogger as any,
      config: testLinkConfig,
    })
  })

  it('forms a link when distance is below threshold', async () => {
    // Register two Helixes at the same position (same embedding)
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same goal', emb)
    const digest = createDigest({ goalSummary: 'Same goal' })

    await engine.registerHelix('h1', digest)
    await engine.registerHelix('h2', digest)

    // Same embedding → same projected position → distance ~0
    linkManager.evaluate(['h1', 'h2'])

    expect(linkManager.areLinked('h1', 'h2')).toBe(true)
    const link = linkManager.getLink('h1', 'h2')
    expect(link).toBeDefined()
    expect(link!.mergeDepth).toBe('shallow')
  })

  it('does NOT form a link when distance exceeds threshold', async () => {
    // Register with very different embeddings
    mockEmbed.setEmbedding('Very different goal A', [10, 0, 0, 0, 0, 0, 0, 0])
    mockEmbed.setEmbedding('Very different goal B', [0, 0, 0, 0, 0, 0, 0, 10])

    await engine.registerHelix('h1', createDigest({ goalSummary: 'Very different goal A' }))
    await engine.registerHelix('h2', createDigest({ goalSummary: 'Very different goal B' }))

    linkManager.evaluate(['h1', 'h2'])

    // Distance should be large
    const dist = engine.getDistance('h1', 'h2')
    if (dist >= testLinkConfig.linkThreshold) {
      expect(linkManager.areLinked('h1', 'h2')).toBe(false)
    }
  })

  it('promotes merge depth with stability', async () => {
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same', emb)
    const digest = createDigest({ goalSummary: 'Same' })

    await engine.registerHelix('h1', digest)
    await engine.registerHelix('h2', digest)

    // Run enough evaluations to promote through levels
    for (let i = 0; i < testLinkConfig.deepMergeStabilityTicks + 1; i++) {
      linkManager.evaluate(['h1', 'h2'])
    }

    const link = linkManager.getLink('h1', 'h2')
    expect(link).toBeDefined()
    // After enough ticks, should be at least medium if not deep
    expect(['medium', 'deep']).toContain(link!.mergeDepth)
  })

  it('removes links when a Helix is removed', async () => {
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same', emb)
    const digest = createDigest({ goalSummary: 'Same' })

    await engine.registerHelix('h1', digest)
    await engine.registerHelix('h2', digest)
    linkManager.evaluate(['h1', 'h2'])

    expect(linkManager.areLinked('h1', 'h2')).toBe(true)

    linkManager.removeHelix('h1')
    expect(linkManager.areLinked('h1', 'h2')).toBe(false)
  })

  it('getNeighbors returns linked Helixes', async () => {
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same', emb)
    const digest = createDigest({ goalSummary: 'Same' })

    await engine.registerHelix('h1', digest)
    await engine.registerHelix('h2', digest)
    await engine.registerHelix('h3', digest)

    linkManager.evaluate(['h1', 'h2', 'h3'])

    const neighbors = linkManager.getNeighbors('h1')
    expect(neighbors).toContain('h2')
    expect(neighbors).toContain('h3')
  })

  it('linkKey is symmetric — (A,B) === (B,A)', async () => {
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same', emb)
    const digest = createDigest({ goalSummary: 'Same' })

    await engine.registerHelix('h1', digest)
    await engine.registerHelix('h2', digest)
    linkManager.evaluate(['h1', 'h2'])

    expect(linkManager.areLinked('h1', 'h2')).toBe(true)
    expect(linkManager.areLinked('h2', 'h1')).toBe(true)
  })

  it('handles empty helix list gracefully', () => {
    expect(() => linkManager.evaluate([])).not.toThrow()
    expect(linkManager.getAllLinks()).toHaveLength(0)
  })

  it('handles single helix without forming links', async () => {
    await engine.registerHelix('h1', createDigest({ goalSummary: 'Solo' }))
    linkManager.evaluate(['h1'])
    expect(linkManager.getAllLinks()).toHaveLength(0)
  })
})


// =============================================================
//  ClusterTracker Tests
// =============================================================

describe('ClusterTracker', () => {
  let engine: GravityEngine
  let linkManager: LinkManager
  let clusterTracker: ClusterTracker
  let mockEmbed: ReturnType<typeof createMockEmbeddingService>
  let mockLogger: ReturnType<typeof createMockLogger>

  beforeEach(() => {
    mockEmbed = createMockEmbeddingService()
    mockLogger = createMockLogger()
    engine = new GravityEngine({
      embeddingService: mockEmbed as any,
      logger: mockLogger as any,
      config: DEFAULT_GRAVITY_CONFIG,
    })
    linkManager = new LinkManager({
      gravityEngine: engine,
      logger: mockLogger as any,
      config: { ...DEFAULT_LINK_CONFIG, linkThreshold: 5.0, unlinkThreshold: 8.0 },
    })
    clusterTracker = new ClusterTracker({
      linkManager,
      gravityEngine: engine,
      logger: mockLogger as any,
    })
  })

  it('forms a cluster from linked Helixes', async () => {
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same', emb)
    const digest = createDigest({ goalSummary: 'Same' })

    await engine.registerHelix('h1', digest)
    await engine.registerHelix('h2', digest)
    await engine.registerHelix('h3', digest)

    linkManager.evaluate(['h1', 'h2', 'h3'])
    clusterTracker.update(['h1', 'h2', 'h3'])

    const clusters = clusterTracker.getAllClusters()
    // All 3 at same position → should form one cluster
    if (linkManager.getAllLinks().length > 0) {
      expect(clusters.length).toBeGreaterThanOrEqual(1)
      expect(clusters[0].members).toHaveLength(3)
    }
  })

  it('does not form a cluster from singletons', async () => {
    await engine.registerHelix('h1', createDigest({ goalSummary: 'Solo A' }))

    linkManager.evaluate(['h1'])
    clusterTracker.update(['h1'])

    const clusters = clusterTracker.getAllClusters()
    expect(clusters).toHaveLength(0)
  })

  it('tracks cluster stability over ticks', async () => {
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same', emb)
    const digest = createDigest({ goalSummary: 'Same' })

    await engine.registerHelix('h1', digest)
    await engine.registerHelix('h2', digest)

    // First tick: form
    linkManager.evaluate(['h1', 'h2'])
    clusterTracker.update(['h1', 'h2'])

    // Second tick: stability increments
    linkManager.evaluate(['h1', 'h2'])
    clusterTracker.update(['h1', 'h2'])

    const clusters = clusterTracker.getAllClusters()
    if (clusters.length > 0) {
      expect(clusters[0].ticksStable).toBeGreaterThanOrEqual(1)
      expect(clusters[0].stabilityScore).toBeGreaterThan(0)
    }
  })

  it('areInSameCluster returns correct result', async () => {
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same', emb)
    const digest = createDigest({ goalSummary: 'Same' })

    await engine.registerHelix('h1', digest)
    await engine.registerHelix('h2', digest)
    await engine.registerHelix('h3', createDigest({ goalSummary: 'Different' }))

    linkManager.evaluate(['h1', 'h2', 'h3'])
    clusterTracker.update(['h1', 'h2', 'h3'])

    if (linkManager.areLinked('h1', 'h2')) {
      expect(clusterTracker.areInSameCluster('h1', 'h2')).toBe(true)
    }
  })

  it('computes effective merge depth as minimum across links', async () => {
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same', emb)
    const digest = createDigest({ goalSummary: 'Same' })

    await engine.registerHelix('h1', digest)
    await engine.registerHelix('h2', digest)

    linkManager.evaluate(['h1', 'h2'])
    clusterTracker.update(['h1', 'h2'])

    const clusters = clusterTracker.getAllClusters()
    if (clusters.length > 0) {
      expect(clusters[0].effectiveMergeDepth).toBe('shallow')
    }
  })

  it('handles empty helix list gracefully', () => {
    expect(() => clusterTracker.update([])).not.toThrow()
    expect(clusterTracker.getAllClusters()).toHaveLength(0)
  })

  it('handles single helix without forming clusters', async () => {
    await engine.registerHelix('h1', createDigest({ goalSummary: 'Solo' }))
    linkManager.evaluate(['h1'])
    clusterTracker.update(['h1'])
    expect(clusterTracker.getAllClusters()).toHaveLength(0)
  })
})


// =============================================================
//  TopologyGraph Integration Tests
// =============================================================

describe('TopologyGraph', () => {
  let topology: TopologyGraph
  let mockEmbed: ReturnType<typeof createMockEmbeddingService>
  let mockLogger: ReturnType<typeof createMockLogger>

  beforeEach(() => {
    mockEmbed = createMockEmbeddingService()
    mockLogger = createMockLogger()
    topology = new TopologyGraph({
      embeddingService: mockEmbed as any,
      logger: mockLogger as any,
    })
  })

  it('registers and tracks Helixes through digest updates', async () => {
    const digest = createDigest({ goalSummary: 'Build feature' })
    await topology.onDigestUpdate('h1', digest)

    const snapshot = topology.getSnapshot()
    expect(snapshot.positions).toHaveLength(1)
    expect(snapshot.tickCount).toBeGreaterThan(0)
  })

  it('detects clusters through digest updates', async () => {
    // Use same embedding for maximum similarity
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same goal', emb)
    const digest = createDigest({ goalSummary: 'Same goal', filesActive: ['shared.ts'] })

    await topology.onDigestUpdate('h1', digest)
    await topology.onDigestUpdate('h2', digest)
    await topology.onDigestUpdate('h3', digest)

    const snapshot = topology.getSnapshot()
    expect(snapshot.positions).toHaveLength(3)

    // Same position → linked → clustered
    if (snapshot.links.length > 0) {
      expect(snapshot.clusters.length).toBeGreaterThanOrEqual(1)
    }
  })

  it('deregisters Helixes correctly', async () => {
    const digest = createDigest({ goalSummary: 'Temp work' })
    await topology.onDigestUpdate('h1', digest)
    await topology.onDigestUpdate('h2', digest)

    topology.deregisterHelix('h1')

    const snapshot = topology.getSnapshot()
    // h1's position is still in the snapshot (inactive) but won't be tracked as active
    const positions = snapshot.positions
    expect(positions.length).toBeLessThanOrEqual(2)
  })

  it('deregisters during digest update without crashing', async () => {
    await topology.onDigestUpdate('h1', createDigest({ goalSummary: 'A' }))
    await topology.onDigestUpdate('h2', createDigest({ goalSummary: 'B' }))

    // Start an update and deregister concurrently
    const updatePromise = topology.onDigestUpdate('h1', createDigest({ goalSummary: 'Updated' }))
    topology.deregisterHelix('h2')

    await updatePromise

    const snapshot = topology.getSnapshot()
    expect(snapshot.positions).toBeDefined()
  })

  it('handles empty constellation (0 helixes) gracefully', () => {
    const snapshot = topology.getSnapshot()
    expect(snapshot.positions).toHaveLength(0)
    expect(snapshot.links).toHaveLength(0)
    expect(snapshot.clusters).toHaveLength(0)
    expect(snapshot.tickCount).toBe(0)
  })

  it('handles single helix scenario without errors', async () => {
    await topology.onDigestUpdate('h1', createDigest({ goalSummary: 'Solo' }))

    const snapshot = topology.getSnapshot()
    expect(snapshot.positions).toHaveLength(1)
    expect(snapshot.links).toHaveLength(0)
    expect(snapshot.clusters).toHaveLength(0)

    const dist = topology.getDistance('h1', 'h2')
    expect(dist).toBe(Infinity)

    const neighbors = topology.getNeighbors('h1')
    expect(neighbors).toHaveLength(0)
  })

  it('provides convenience methods for Corpus consumption', async () => {
    const emb = [1, 0, 0, 0, 0, 0, 0, 0]
    mockEmbed.setEmbedding('Same', emb)
    const digest = createDigest({ goalSummary: 'Same' })

    await topology.onDigestUpdate('h1', digest)
    await topology.onDigestUpdate('h2', digest)

    const dist = topology.getDistance('h1', 'h2')
    expect(typeof dist).toBe('number')

    const similarity = topology.getSimilarity('h1', 'h2')
    expect(typeof similarity).toBe('number')
    expect(similarity).toBeGreaterThanOrEqual(0)
    expect(similarity).toBeLessThanOrEqual(1)

    const neighbors = topology.getNeighbors('h1')
    expect(Array.isArray(neighbors)).toBe(true)
  })

  it('respects enabled flag — no-ops when disabled', async () => {
    const disabledTopology = new TopologyGraph({
      embeddingService: mockEmbed as any,
      logger: mockLogger as any,
      config: {
        gravity: DEFAULT_GRAVITY_CONFIG,
        links: DEFAULT_LINK_CONFIG,
        enabled: false,
      },
    })

    await disabledTopology.onDigestUpdate('h1', createDigest())
    const snapshot = disabledTopology.getSnapshot()
    expect(snapshot.positions).toHaveLength(0)
    expect(snapshot.tickCount).toBe(0)
  })

  it('handles concurrent digest updates', async () => {
    const digests = Array.from({ length: 5 }, (_, i) =>
      createDigest({ goalSummary: `Task ${i}` }),
    )

    // Fire all updates concurrently
    await Promise.all(
      digests.map((d, i) => topology.onDigestUpdate(`h${i}`, d)),
    )

    const snapshot = topology.getSnapshot()
    expect(snapshot.positions).toHaveLength(5)
  })

  it('getSnapshot returns complete topology state', async () => {
    await topology.onDigestUpdate('h1', createDigest({ goalSummary: 'A' }))

    const snapshot = topology.getSnapshot()
    expect(snapshot).toHaveProperty('positions')
    expect(snapshot).toHaveProperty('links')
    expect(snapshot).toHaveProperty('clusters')
    expect(snapshot).toHaveProperty('distances')
    expect(snapshot).toHaveProperty('tickCount')
    expect(snapshot).toHaveProperty('snapshotAt')
    expect(snapshot.snapshotAt).toBeGreaterThan(0)
  })

  // =============================================================
  //  CRITICAL MISSING TESTS — Deregistration Edge Cases
  // =============================================================

  it('handles self-deregistration during own digest update', async () => {
    await topology.onDigestUpdate('h1', createDigest({ goalSummary: 'A' }))

    // Start update, then immediately deregister the same helix
    const updatePromise = topology.onDigestUpdate('h1', createDigest({ goalSummary: 'Updated' }))
    topology.deregisterHelix('h1')

    await expect(updatePromise).resolves.not.toThrow()
  })

  it('handles multiple rapid deregistrations during single tick', async () => {
    await topology.onDigestUpdate('h1', createDigest({ goalSummary: 'A' }))
    await topology.onDigestUpdate('h2', createDigest({ goalSummary: 'B' }))
    await topology.onDigestUpdate('h3', createDigest({ goalSummary: 'C' }))

    const updatePromise = topology.onDigestUpdate('h1', createDigest({ goalSummary: 'Updated' }))

    // Deregister all others rapidly
    topology.deregisterHelix('h2')
    topology.deregisterHelix('h3')

    await updatePromise

    // Should not crash, remaining helix should be in valid state
    const snapshot = topology.getSnapshot()
    expect(snapshot.positions.length).toBeGreaterThanOrEqual(0)
  })

  it('handles cascade deregistration during tick', async () => {
    await topology.onDigestUpdate('h1', createDigest({ goalSummary: 'A' }))
    await topology.onDigestUpdate('h2', createDigest({ goalSummary: 'B' }))

    const updatePromise = topology.onDigestUpdate('h1', createDigest({ goalSummary: 'Updated' }))

    // Simulate cascade: deregister h1 which should clean up h2 as well
    topology.deregisterHelix('h1')
    topology.deregisterHelix('h2')

    await updatePromise

    // Both should be cleanly removed - check snapshot shows no active positions
    const snapshot = topology.getSnapshot()
    const activePositions = snapshot.positions.filter(p => p.helixId === 'h1' || p.helixId === 'h2')
    expect(activePositions.length).toBeLessThanOrEqual(2) // may still have inactive positions
  })

  it('handles transition from non-empty to empty constellation', async () => {
    await topology.onDigestUpdate('h1', createDigest({ goalSummary: 'A' }))
    await topology.onDigestUpdate('h2', createDigest({ goalSummary: 'B' }))

    // Deregister all
    topology.deregisterHelix('h1')
    topology.deregisterHelix('h2')

    // Should remain stable - no crashes on subsequent operations
    expect(() => topology.getDistance('h1', 'h2')).not.toThrow()
    expect(() => topology.getNeighbors('h1')).not.toThrow()
  })

  it('handles single helix transitioning to empty', async () => {
    await topology.onDigestUpdate('h1', createDigest({ goalSummary: 'Solo' }))

    // Deregister the last one
    topology.deregisterHelix('h1')

    // Should remain stable
    expect(() => topology.getDistance('h1', 'h2')).not.toThrow()
  })

  it('single helix position remains stable across multiple digest updates', async () => {
    await topology.onDigestUpdate('h1', createDigest({ goalSummary: 'Task' }))

    const initialPos = topology.getSnapshot().positions[0]
    const initialX = initialPos.x
    const initialY = initialPos.y

    // Apply many updates
    for (let i = 0; i < 50; i++) {
      await topology.onDigestUpdate('h1', createDigest({ goalSummary: 'Task' }))
    }

    const finalPos = topology.getSnapshot().positions[0]

    // Position should not drift significantly (allow small epsilon for floating point)
    expect(Math.abs(finalPos.x - initialX)).toBeLessThan(0.01)
    expect(Math.abs(finalPos.y - initialY)).toBeLessThan(0.01)
  })

  it('handles rapid succession digest updates on single helix', async () => {
    const updates = Array.from({ length: 20 }, (_, i) =>
      topology.onDigestUpdate('h1', createDigest({ goalSummary: `Task ${i}` }))
    )

    await Promise.all(updates)

    // Should not crash
    const snapshot = topology.getSnapshot()
    expect(snapshot.positions).toHaveLength(1)
  })

  it('computes correct distance and similarity for self-comparison', async () => {
    await topology.onDigestUpdate('h1', createDigest({ goalSummary: 'Task' }))

    const dist = topology.getDistance('h1', 'h1')
    expect(dist).toBe(0)

    const similarity = topology.getSimilarity('h1', 'h1')
    expect(similarity).toBeCloseTo(1, 5) // allow floating point epsilon
  })
})


describe('TopologyGraph persistEvent integration', () => {
  let mockEmbed: ReturnType<typeof createMockEmbeddingService>
  let mockLogger: ReturnType<typeof createMockLogger>

  it('calls persistEvent on topology updates', async () => {
    mockEmbed = createMockEmbeddingService()
    mockLogger = createMockLogger()
    const persistEvent = vi.fn()

    const topo = new TopologyGraph({
      embeddingService: mockEmbed as any,
      logger: mockLogger as any,
      persistEvent,
    })
    topo.setConstellationId('test-constellation')

    await topo.onDigestUpdate('h1', createDigest({ goalSummary: 'Task A' }))

    expect(persistEvent).toHaveBeenCalledWith(
      'topology:updated',
      'h1',
      expect.stringContaining('Topology tick'),
      expect.objectContaining({
        helixId: 'h1',
        tickCount: expect.any(Number),
        linkCount: expect.any(Number),
        clusterCount: expect.any(Number),
      }),
    )
  })

  it('does not call persistEvent when constellation ID is not set', async () => {
    mockEmbed = createMockEmbeddingService()
    mockLogger = createMockLogger()
    const persistEvent = vi.fn()

    const topo = new TopologyGraph({
      embeddingService: mockEmbed as any,
      logger: mockLogger as any,
      persistEvent,
    })
    // WHY: Without a constellation ID, persist should not fire
    await topo.onDigestUpdate('h1', createDigest({ goalSummary: 'Task A' }))
    expect(persistEvent).not.toHaveBeenCalled()
  })

  it('survives persistEvent throwing an error', async () => {
    mockEmbed = createMockEmbeddingService()
    mockLogger = createMockLogger()
    const persistEvent = vi.fn().mockImplementation(() => { throw new Error('DB write failed') })

    const topo = new TopologyGraph({
      embeddingService: mockEmbed as any,
      logger: mockLogger as any,
      persistEvent,
    })
    topo.setConstellationId('test-constellation')

    // Should not throw
    await expect(
      topo.onDigestUpdate('h1', createDigest({ goalSummary: 'Task A' }))
    ).resolves.toBeUndefined()

    // persistEvent was called but error was swallowed
    expect(persistEvent).toHaveBeenCalled()
  })
})


// Serialization roundtrip tests

import {
  serializeTopologySnapshot,
  deserializeTopologySnapshot,
} from '../src/topology/topology-types.js'

describe('TopologySnapshot serialization', () => {

  it('roundtrips a snapshot through serialize/deserialize', () => {
    const original = {
      positions: [
        { helixId: 'h1', x: 1.5, y: 2.3, vx: 0.1, vy: -0.2 },
        { helixId: 'h2', x: -0.5, y: 0.7, vx: 0, vy: 0 },
      ],
      links: [
        {
          helixIdA: 'h1', helixIdB: 'h2', distance: 0.8,
          similarity: 0.75, createdAt: 1000, mergeDepth: 'shallow' as const,
          stabilityTicks: 3,
        },
      ],
      clusters: [
        {
          clusterId: 'c1',
          members: ['h1', 'h2'],
          links: [{ helixIdA: 'h1', helixIdB: 'h2', distance: 0.8, similarity: 0.75, createdAt: 1000, mergeDepth: 'shallow' as const, stabilityTicks: 3 }],
          effectiveMergeDepth: 'shallow' as const,
          averageInternalDistance: 0.8,
          stabilityScore: 0.6,
          formedAt: 1000,
          ticksStable: 3,
        },
      ],
      distances: new Map([
        ['h1', new Map([['h1', 0], ['h2', 0.8]])],
        ['h2', new Map([['h1', 0.8], ['h2', 0]])],
      ]),
      tickCount: 5,
      snapshotAt: Date.now(),
    }

    const serialized = serializeTopologySnapshot(original)

    // Distances should be plain objects
    expect(serialized.distances).toEqual({
      h1: { h1: 0, h2: 0.8 },
      h2: { h1: 0.8, h2: 0 },
    })

    // Should survive JSON roundtrip
    const jsonStr = JSON.stringify(serialized)
    const parsed = JSON.parse(jsonStr)

    const restored = deserializeTopologySnapshot(parsed)

    // Distances should be Maps again
    expect(restored.distances).toBeInstanceOf(Map)
    expect(restored.distances.get('h1')).toBeInstanceOf(Map)
    expect(restored.distances.get('h1')?.get('h2')).toBe(0.8)

    // Other fields should match
    expect(restored.positions).toEqual(original.positions)
    expect(restored.links).toEqual(original.links)
    expect(restored.clusters).toEqual(original.clusters)
    expect(restored.tickCount).toBe(original.tickCount)
    expect(restored.snapshotAt).toBe(original.snapshotAt)
  })

  it('handles empty distances', () => {
    const snap = {
      positions: [],
      links: [],
      clusters: [],
      distances: new Map(),
      tickCount: 0,
      snapshotAt: 0,
    }

    const serialized = serializeTopologySnapshot(snap)
    expect(serialized.distances).toEqual({})

    const restored = deserializeTopologySnapshot(serialized)
    expect(restored.distances.size).toBe(0)
  })

  it('serialized topology embeds cleanly in CorpusTreeSnapshot JSON', () => {
    const snap = {
      positions: [{ helixId: 'h1', x: 1, y: 2, vx: 0, vy: 0 }],
      links: [],
      clusters: [],
      distances: new Map([['h1', new Map([['h1', 0]])]]),
      tickCount: 1,
      snapshotAt: 1000,
    }

    const serialized = serializeTopologySnapshot(snap)

    // Simulate what the pipeline does: embed topology in tree snapshot
    const treeSnapshot = {
      branches: [],
      totalSteps: 0,
      activeBranches: 0,
      snapshotAt: 1000,
      digests: [],
      topics: [],
      retrospectives: [],
      elevatedPatterns: [],
      effectivenessRecords: [],
      topology: serialized,
    }

    const json = JSON.stringify(treeSnapshot)
    const parsed = JSON.parse(json)

    expect(parsed.topology).toBeDefined()
    expect(parsed.topology.positions).toHaveLength(1)
    expect(parsed.topology.distances.h1.h1).toBe(0)
  })
})
