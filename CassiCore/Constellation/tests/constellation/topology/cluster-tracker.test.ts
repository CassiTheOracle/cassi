import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ClusterTracker } from '../../../src/topology/cluster-tracker.js'
import type { ClusterTrackerDeps } from '../../../src/topology/cluster-tracker.js'
import type { LinkManager } from '../../../src/topology/link-manager.js'
import type { GravityEngine } from '../../../src/topology/gravity-engine.js'
import type { ILogger } from '../../../src/vendor/types/interfaces.js'
import type { TopologyLink, MergeDepth } from '../../../src/topology/topology-types.js'

function makeLogger(): ILogger {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn().mockReturnThis(),
  } as unknown as ILogger
}

function makeLink(
  idA: string,
  idB: string,
  overrides: Partial<TopologyLink> = {},
): TopologyLink {
  const a = idA < idB ? idA : idB
  const b = idA < idB ? idB : idA
  return {
    helixIdA: a,
    helixIdB: b,
    distance: 1.0,
    similarity: 0.8,
    createdAt: Date.now(),
    mergeDepth: 'shallow',
    stabilityTicks: 0,
    ...overrides,
  }
}

function makeLinkManager(links: TopologyLink[]): LinkManager {
  return {
    getAllLinks: vi.fn(() => links),
    getLinksFor: vi.fn(),
    areLinked: vi.fn(),
    getLink: vi.fn(),
    getNeighbors: vi.fn(),
  } as unknown as LinkManager
}

function makeGravityEngine(distances: Record<string, number> = {}): GravityEngine {
  return {
    getDistance: vi.fn((a: string, b: string) => {
      const key = a < b ? `${a}::${b}` : `${b}::${a}`
      return distances[key] ?? 1.0
    }),
  } as unknown as GravityEngine
}

function makeDeps(overrides: Partial<ClusterTrackerDeps> = {}): ClusterTrackerDeps {
  return {
    linkManager: makeLinkManager([]),
    gravityEngine: makeGravityEngine(),
    logger: makeLogger(),
    ...overrides,
  }
}

describe('ClusterTracker', () => {
  let tracker: ClusterTracker

  beforeEach(() => {
    tracker = new ClusterTracker(makeDeps())
  })

  describe('construction', () => {
    it('starts with no clusters', () => {
      expect(tracker.getAllClusters()).toEqual([])
      expect(tracker.getClusteredHelixIds()).toEqual([])
    })
  })

  describe('update — cluster detection', () => {
    it('forms a cluster from a pair of linked helixes', () => {
      const links = [makeLink('h1', 'h2')]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['h1', 'h2'])

      const clusters = tracker.getAllClusters()
      expect(clusters).toHaveLength(1)
      expect(clusters[0].members).toEqual(['h1', 'h2'])
    })

    it('ignores singletons (not clusters)', () => {
      const lm = makeLinkManager([])
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['h1', 'h2', 'h3'])
      expect(tracker.getAllClusters()).toHaveLength(0)
    })

    it('detects transitive clusters (A-B, B-C → cluster {A,B,C})', () => {
      const links = [makeLink('h1', 'h2'), makeLink('h2', 'h3')]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['h1', 'h2', 'h3'])

      const clusters = tracker.getAllClusters()
      expect(clusters).toHaveLength(1)
      expect(clusters[0].members).toEqual(['h1', 'h2', 'h3'])
    })

    it('detects multiple independent clusters', () => {
      const links = [
        makeLink('h1', 'h2'),
        makeLink('h3', 'h4'),
      ]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['h1', 'h2', 'h3', 'h4', 'h5'])

      const clusters = tracker.getAllClusters()
      expect(clusters).toHaveLength(2)

      const allMembers = clusters.flatMap(c => c.members).sort()
      expect(allMembers).toEqual(['h1', 'h2', 'h3', 'h4'])
    })

    it('sorts members alphabetically', () => {
      const links = [makeLink('z', 'a')]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['z', 'a'])

      expect(tracker.getAllClusters()[0].members).toEqual(['a', 'z'])
    })
  })

  describe('update — cluster stability', () => {
    it('preserves cluster ID when membership is unchanged', () => {
      const links = [makeLink('h1', 'h2')]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['h1', 'h2'])
      const id1 = tracker.getAllClusters()[0].clusterId

      tracker.update(['h1', 'h2'])
      const id2 = tracker.getAllClusters()[0].clusterId

      expect(id1).toBe(id2)
    })

    it('increments ticksStable on repeated update with same membership', () => {
      const links = [makeLink('h1', 'h2')]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['h1', 'h2'])
      expect(tracker.getAllClusters()[0].ticksStable).toBe(0)

      tracker.update(['h1', 'h2'])
      expect(tracker.getAllClusters()[0].ticksStable).toBe(1)

      tracker.update(['h1', 'h2'])
      expect(tracker.getAllClusters()[0].ticksStable).toBe(2)
    })

    it('starts a new cluster ID when membership changes', () => {
      // Initial: {h1, h2}
      let links = [makeLink('h1', 'h2')]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['h1', 'h2', 'h3'])
      const id1 = tracker.getAllClusters()[0].clusterId

      // Now h3 joins: {h1, h2, h3}
      links = [makeLink('h1', 'h2'), makeLink('h2', 'h3')]
      vi.mocked(lm.getAllLinks).mockReturnValue(links)

      tracker.update(['h1', 'h2', 'h3'])
      const id2 = tracker.getAllClusters()[0].clusterId

      expect(id1).not.toBe(id2) // Different membership = new cluster
    })

    it('stabilityScore approaches 1.0 asymptotically', () => {
      const links = [makeLink('h1', 'h2')]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['h1', 'h2'])
      expect(tracker.getAllClusters()[0].stabilityScore).toBe(0)

      for (let i = 0; i < 50; i++) {
        tracker.update(['h1', 'h2'])
      }
      const score = tracker.getAllClusters()[0].stabilityScore
      expect(score).toBeGreaterThan(0.4)
      expect(score).toBeLessThanOrEqual(1.0)
    })
  })

  describe('update — effective merge depth', () => {
    it('uses the shallowest link as the effective depth', () => {
      const links = [
        makeLink('h1', 'h2', { mergeDepth: 'deep' }),
        makeLink('h2', 'h3', { mergeDepth: 'shallow' }),
      ]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['h1', 'h2', 'h3'])
      expect(tracker.getAllClusters()[0].effectiveMergeDepth).toBe('shallow')
    })

    it('returns deep when all links are deep', () => {
      const links = [
        makeLink('h1', 'h2', { mergeDepth: 'deep' }),
        makeLink('h2', 'h3', { mergeDepth: 'deep' }),
      ]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['h1', 'h2', 'h3'])
      expect(tracker.getAllClusters()[0].effectiveMergeDepth).toBe('deep')
    })
  })

  describe('update — average distance', () => {
    it('computes average pairwise distance from gravity engine', () => {
      const links = [makeLink('h1', 'h2'), makeLink('h2', 'h3')]
      const lm = makeLinkManager(links)
      const ge = makeGravityEngine({
        'h1::h2': 1.0,
        'h1::h3': 2.0,
        'h2::h3': 1.5,
      })
      tracker = new ClusterTracker(makeDeps({ linkManager: lm, gravityEngine: ge }))

      tracker.update(['h1', 'h2', 'h3'])

      // Average of 1.0, 2.0, 1.5 = 1.5
      expect(tracker.getAllClusters()[0].averageInternalDistance).toBeCloseTo(1.5)
    })
  })

  describe('update — dissolution', () => {
    it('dissolves clusters when links disappear', () => {
      const links = [makeLink('h1', 'h2')]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))

      tracker.update(['h1', 'h2'])
      expect(tracker.getAllClusters()).toHaveLength(1)

      // No more links
      vi.mocked(lm.getAllLinks).mockReturnValue([])
      tracker.update(['h1', 'h2'])
      expect(tracker.getAllClusters()).toHaveLength(0)
    })
  })

  describe('query methods', () => {
    beforeEach(() => {
      const links = [
        makeLink('h1', 'h2'),
        makeLink('h2', 'h3'),
        makeLink('h4', 'h5'),
      ]
      const lm = makeLinkManager(links)
      tracker = new ClusterTracker(makeDeps({ linkManager: lm }))
      tracker.update(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    })

    it('getClusterFor returns the cluster containing a helix', () => {
      const cluster = tracker.getClusterFor('h1')
      expect(cluster).toBeDefined()
      expect(cluster!.members).toContain('h1')
      expect(cluster!.members).toContain('h2')
      expect(cluster!.members).toContain('h3')
    })

    it('getClusterFor returns undefined for unclustered helix', () => {
      expect(tracker.getClusterFor('h6')).toBeUndefined()
    })

    it('getClusteredHelixIds returns all helixes in clusters', () => {
      const ids = tracker.getClusteredHelixIds().sort()
      expect(ids).toEqual(['h1', 'h2', 'h3', 'h4', 'h5'])
    })

    it('areInSameCluster returns true for helixes in the same cluster', () => {
      expect(tracker.areInSameCluster('h1', 'h2')).toBe(true)
      expect(tracker.areInSameCluster('h1', 'h3')).toBe(true)
    })

    it('areInSameCluster returns false for helixes in different clusters', () => {
      expect(tracker.areInSameCluster('h1', 'h4')).toBe(false)
    })

    it('areInSameCluster returns false for unclustered helixes', () => {
      expect(tracker.areInSameCluster('h1', 'h6')).toBe(false)
      expect(tracker.areInSameCluster('h6', 'h99')).toBe(false)
    })

    it('getEffectiveMergeDepth returns depth for same-cluster pair', () => {
      const depth = tracker.getEffectiveMergeDepth('h1', 'h2')
      expect(depth).toBe('shallow')
    })

    it('getEffectiveMergeDepth returns undefined for different clusters', () => {
      expect(tracker.getEffectiveMergeDepth('h1', 'h4')).toBeUndefined()
    })

    it('getEffectiveMergeDepth returns undefined for unclustered helix', () => {
      expect(tracker.getEffectiveMergeDepth('h1', 'h6')).toBeUndefined()
    })
  })

  describe('cluster events logging', () => {
    it('logs cluster formation', () => {
      const links = [makeLink('h1', 'h2')]
      const lm = makeLinkManager(links)
      const logger = makeLogger()
      tracker = new ClusterTracker(makeDeps({ linkManager: lm, logger }))

      tracker.update(['h1', 'h2'])

      const childLogger = vi.mocked(logger.child!).mock.results[0]?.value ?? logger
      expect(childLogger.info).toHaveBeenCalledWith(
        'Cluster formed',
        expect.objectContaining({ members: ['h1', 'h2'] }),
      )
    })

    it('logs cluster dissolution', () => {
      const links = [makeLink('h1', 'h2')]
      const lm = makeLinkManager(links)
      const logger = makeLogger()
      tracker = new ClusterTracker(makeDeps({ linkManager: lm, logger }))

      tracker.update(['h1', 'h2'])

      vi.mocked(lm.getAllLinks).mockReturnValue([])
      tracker.update(['h1', 'h2'])

      const childLogger = vi.mocked(logger.child!).mock.results[0]?.value ?? logger
      expect(childLogger.info).toHaveBeenCalledWith(
        'Cluster dissolved',
        expect.objectContaining({ members: ['h1', 'h2'] }),
      )
    })
  })
})
