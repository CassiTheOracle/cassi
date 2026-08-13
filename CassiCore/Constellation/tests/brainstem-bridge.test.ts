/**
 * Tests for BrainstemBridge — progressive context sharing between linked Helix sessions.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { BrainstemBridge } from '../src/topology/brainstem-bridge.js'
import type {
  BrainstemBridgeDeps,
  BrainstemStateAccessor,
} from '../src/topology/brainstem-bridge.js'
import type { BranchDigest, ICorpusTree } from '../src/corpus-types.js'
import type { CognitiveModel, BrainstemBlackboard } from '../src/vendor/helix/brainstem-types.js'


// --- Mock Helpers ---

function createMockLogger() {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: () => createMockLogger(),
  }
}

function createDigest(helixId: string, overrides: Partial<BranchDigest> = {}): BranchDigest {
  return {
    helixId,
    goalSummary: `Goal for ${helixId}`,
    approach: 'implement' as any,
    status: 'active',
    progress: 0.5,
    filesActive: ['src/main.ts', 'src/utils.ts'],
    keyFindings: ['Found pattern A', 'Found pattern B'],
    blockers: [],
    currentStrategy: 'incremental',
    rollingScore: 0.75,
    workUnitsProcessed: 10,
    updatedAt: Date.now(),
    recentDecisions: [],
    currentHypothesis: 'The auth module needs refactoring',
    allDiscoveries: ['Discovery 1', 'Discovery 2', 'Discovery 3'],
    allDecisions: ['Decision 1', 'Decision 2'],
    currentNextSteps: ['Step A', 'Step B'],
    confidence: 0.7,
    turnCount: 5,
    ...overrides,
  } as BranchDigest
}

function createMockTree(digests: Map<string, BranchDigest>): ICorpusTree {
  return {
    getDigestFor: (helixId: string) => digests.get(helixId) || undefined,
    getAllBranches: () => [],
    registerBranch: vi.fn(),
    getDigestsExcluding: vi.fn(() => []),
    getAllDigests: () => Array.from(digests.values()),
    updateDigest: vi.fn(),
  } as unknown as ICorpusTree
}

function createMockBrainstemAccessor(overrides: Partial<CognitiveModel> = {}): BrainstemStateAccessor {
  return {
    getCognitiveModel: () => ({
      currentHypothesis: 'Working hypothesis',
      allDiscoveries: ['Deep discovery 1', 'Deep discovery 2'],
      allDecisions: ['Deep decision 1'],
      pendingBlockers: ['Blocker X'],
      recentOutputs: ['Wrote file A', 'Ran test B', 'Fixed error C'],
      currentNextSteps: ['Next deep step'],
      hypothesisUpdatedAtStep: 5,
      ...overrides,
    }),
    getQualityTrajectory: () => [0.5, 0.6, 0.65, 0.7, 0.75],
    getBlackboard: () => ({
      post: vi.fn(),
      read: (channel: string, _limit?: number) => {
        if (channel === 'findings') return [{ id: '1', channel: 'findings', content: 'BB finding 1', author: 'h1', priority: 1, tags: [], timestamp: Date.now() }]
        if (channel === 'concerns') return [{ id: '2', channel: 'concerns', content: 'BB concern 1', author: 'h1', priority: 1, tags: [], timestamp: Date.now() }]
        if (channel === 'decisions') return [{ id: '3', channel: 'decisions', content: 'BB decision 1', author: 'h1', priority: 1, tags: [], timestamp: Date.now() }]
        return []
      },
    } as unknown as BrainstemBlackboard),
  }
}


// =============================================================
//  BrainstemBridge Tests
// =============================================================

describe('BrainstemBridge', () => {
  let bridge: BrainstemBridge
  let injectGuidance: ReturnType<typeof vi.fn<(helixId: string, content: string, urgency: 'low' | 'medium' | 'high' | 'critical') => void>>
  let digests: Map<string, BranchDigest>
  let tree: ICorpusTree
  let accessors: Map<string, BrainstemStateAccessor>

  beforeEach(() => {
    injectGuidance = vi.fn<(helixId: string, content: string, urgency: 'low' | 'medium' | 'high' | 'critical') => void>()
    digests = new Map()
    digests.set('h1', createDigest('h1', { goalSummary: 'Build auth module' }))
    digests.set('h2', createDigest('h2', { goalSummary: 'Build user module' }))
    digests.set('h3', createDigest('h3', { goalSummary: 'Write tests' }))

    tree = createMockTree(digests)
    accessors = new Map()
    accessors.set('h1', createMockBrainstemAccessor())
    accessors.set('h2', createMockBrainstemAccessor())

    bridge = new BrainstemBridge({
      tree,
      logger: createMockLogger() as any,
      injectGuidance,
      getBrainstemState: (id) => accessors.get(id),
    })
  })

  describe('activateLink / deactivateLink', () => {
    it('activates a bridge between two Helixes', () => {
      bridge.activateLink('h1', 'h2', 'shallow')
      expect(bridge.hasBridge('h1', 'h2')).toBe(true)
      expect(bridge.bridgeCount).toBe(1)
    })

    it('is idempotent — re-activating does not duplicate', () => {
      bridge.activateLink('h1', 'h2', 'shallow')
      bridge.activateLink('h1', 'h2', 'shallow')
      expect(bridge.bridgeCount).toBe(1)
    })

    it('deactivates a bridge', () => {
      bridge.activateLink('h1', 'h2', 'shallow')
      bridge.deactivateLink('h1', 'h2')
      expect(bridge.hasBridge('h1', 'h2')).toBe(false)
      expect(bridge.bridgeCount).toBe(0)
    })

    it('bridge key is symmetric', () => {
      bridge.activateLink('h2', 'h1', 'shallow')
      expect(bridge.hasBridge('h1', 'h2')).toBe(true)
      expect(bridge.hasBridge('h2', 'h1')).toBe(true)
    })
  })

  describe('updateDepth', () => {
    it('updates the merge depth of an active bridge', () => {
      bridge.activateLink('h1', 'h2', 'shallow')
      bridge.updateDepth('h1', 'h2', 'medium')

      const bridges = bridge.getActiveBridges()
      expect(bridges[0].depth).toBe('medium')
    })

    it('no-ops for non-existent bridge', () => {
      // Should not throw
      bridge.updateDepth('h1', 'h2', 'deep')
      expect(bridge.bridgeCount).toBe(0)
    })
  })

  describe('removeHelix', () => {
    it('removes all bridges involving a Helix', () => {
      bridge.activateLink('h1', 'h2', 'shallow')
      bridge.activateLink('h1', 'h3', 'shallow')
      bridge.activateLink('h2', 'h3', 'shallow')

      bridge.removeHelix('h1')
      expect(bridge.bridgeCount).toBe(1)
      expect(bridge.hasBridge('h2', 'h3')).toBe(true)
      expect(bridge.hasBridge('h1', 'h2')).toBe(false)
    })
  })

  describe('pushContext — shallow', () => {
    it('injects digest summaries in both directions', () => {
      bridge.activateLink('h1', 'h2', 'shallow')
      const injections = bridge.pushContext()

      // Should inject h1's context into h2, and h2's context into h1
      expect(injections).toHaveLength(2)
      expect(injectGuidance).toHaveBeenCalledTimes(2)
    })

    it('injection content contains goal summary', () => {
      bridge.activateLink('h1', 'h2', 'shallow')
      const injections = bridge.pushContext()

      const h1ToH2 = injections.find(i => i.targetHelixId === 'h2')!
      expect(h1ToH2.content).toContain('Build auth module')
      expect(h1ToH2.depth).toBe('shallow')

      const h2ToH1 = injections.find(i => i.targetHelixId === 'h1')!
      expect(h2ToH1.content).toContain('Build user module')
    })

    it('injection content contains active files and findings', () => {
      bridge.activateLink('h1', 'h2', 'shallow')
      const injections = bridge.pushContext()

      const h1ToH2 = injections.find(i => i.targetHelixId === 'h2')!
      expect(h1ToH2.content).toContain('src/main.ts')
      expect(h1ToH2.content).toContain('Found pattern A')
    })

    it('shallow injection does NOT contain cognitive model', () => {
      bridge.activateLink('h1', 'h2', 'shallow')
      const injections = bridge.pushContext()

      const h1ToH2 = injections.find(i => i.targetHelixId === 'h2')!
      expect(h1ToH2.content).not.toContain('Hypothesis')
      expect(h1ToH2.content).not.toContain('Recent decisions')
    })
  })

  describe('pushContext — medium', () => {
    it('includes cognitive model snippets', () => {
      bridge.activateLink('h1', 'h2', 'medium')
      const injections = bridge.pushContext()

      const h1ToH2 = injections.find(i => i.targetHelixId === 'h2')!
      expect(h1ToH2.content).toContain('Hypothesis')
      expect(h1ToH2.content).toContain('auth module needs refactoring')
      expect(h1ToH2.content).toContain('Decision 1')
      expect(h1ToH2.content).toContain('Discovery 1')
    })
  })

  describe('pushContext — deep', () => {
    it('includes blackboard and quality trajectory', () => {
      bridge.activateLink('h1', 'h2', 'deep')
      const injections = bridge.pushContext()

      const h1ToH2 = injections.find(i => i.targetHelixId === 'h2')!
      expect(h1ToH2.content).toContain('BB finding 1')
      expect(h1ToH2.content).toContain('BB concern 1')
      expect(h1ToH2.content).toContain('Quality trend')
    })
  })

  describe('pushContext — cooldown', () => {
    it('respects injection cooldown', () => {
      bridge.activateLink('h1', 'h2', 'shallow')

      // First push
      const first = bridge.pushContext()
      expect(first).toHaveLength(2)

      // Immediate second push — should be throttled
      const second = bridge.pushContext()
      expect(second).toHaveLength(0)
    })
  })

  describe('pushContext — missing digest', () => {
    it('skips injection when digest is missing for a Helix', () => {
      // h4 has no digest
      bridge.activateLink('h1', 'h4', 'shallow')
      const injections = bridge.pushContext()

      // h1→h4 should inject (h1 has digest), h4→h1 should not (h4 has no digest)
      expect(injections).toHaveLength(1)
      expect(injections[0].targetHelixId).toBe('h4')
      expect(injections[0].sourceHelixId).toBe('h1')
    })
  })

  describe('multiple bridges', () => {
    it('pushes context for all active bridges', () => {
      bridge.activateLink('h1', 'h2', 'shallow')
      bridge.activateLink('h2', 'h3', 'medium')

      const injections = bridge.pushContext()
      // 2 bridges × 2 directions = 4 injections
      expect(injections).toHaveLength(4)
      expect(injectGuidance).toHaveBeenCalledTimes(4)
    })
  })
})
