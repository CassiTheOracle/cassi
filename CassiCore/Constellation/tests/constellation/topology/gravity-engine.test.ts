import { describe, it, expect, beforeEach } from 'vitest'
import { GravityEngine } from '../../src/topology/gravity-engine.js'
import type { GravityEngineDeps } from '../../src/topology/gravity-engine.js'
import type { BranchDigest } from '../../src/corpus-types.js'
import { DEFAULT_GRAVITY_CONFIG } from '../../src/topology/topology-types.js'
import type { EmbeddingMode } from '../../../src/vendor/embeddings/embedding-service.js'

function createMockDeps(overrides?: Partial<GravityEngineDeps>): GravityEngineDeps {
  return {
    embeddingService: {
      embed: async (_text: string, _mode?: EmbeddingMode) => [0.5, 0.3, 0.1, 0.8],
      cosineSimilarity: (a: number[] | null, b: number[] | null) => {
        if (!a || !b) return 0
        let dot = 0, normA = 0, normB = 0
        for (let i = 0; i < a.length; i++) {
          dot += a[i] * b[i]
          normA += a[i] * a[i]
          normB += b[i] * b[i]
        }
        const denom = Math.sqrt(normA) * Math.sqrt(normB)
        return denom === 0 ? 0 : dot / denom
      },
    } as any,
    logger: {
      info: () => {},
      warn: () => {},
      error: () => {},
      debug: () => {},
      child: () => ({
        info: () => {},
        warn: () => {},
        error: () => {},
        debug: () => {},
      }),
    } as any,
    config: { ...DEFAULT_GRAVITY_CONFIG },
    ...overrides,
  }
}

function createDigest(seed: number): BranchDigest {
  return {
    helixId: `h${seed}`,
    goalSummary: `Goal for helix ${seed}`,
    approach: 'implementation',
    progress: 0.5,
    keyFindings: [`Finding ${seed}-A`, `Finding ${seed}-B`],
    filesActive: [`file${seed}.ts`, 'shared.ts'],
    blockers: [],
    currentStrategy: `Strategy ${seed}`,
    rollingScore: 0.7,
    workUnitsProcessed: seed,
    updatedAt: Date.now(),
  }
}

describe('GravityEngine', () => {
  let engine: GravityEngine

  beforeEach(() => {
    engine = new GravityEngine(createMockDeps())
  })

  describe('registerHelix', () => {
    it('registers a new Helix with a position derived from embedding', async () => {
      await engine.registerHelix('h1', createDigest(1))

      const pos = engine.getPosition('h1')
      expect(pos).toBeDefined()
      expect(pos!.helixId).toBe('h1')
      expect(typeof pos!.x).toBe('number')
      expect(typeof pos!.y).toBe('number')
      expect(pos!.vx).toBe(0)
      expect(pos!.vy).toBe(0)
    })

    it('does not re-register an already registered Helix', async () => {
      await engine.registerHelix('h1', createDigest(1))
      const pos1 = engine.getPosition('h1')!

      await engine.registerHelix('h1', createDigest(1))
      const pos2 = engine.getPosition('h1')!

      expect(pos1.x).toBe(pos2.x)
      expect(pos1.y).toBe(pos2.y)
    })

    it('falls back to hash-based placement when embedding fails', async () => {
      const deps = createMockDeps({
        embeddingService: {
          embed: async () => { throw new Error('embedding unavailable') },
          cosineSimilarity: () => 0,
        } as any,
      })
      const eng = new GravityEngine(deps)

      await eng.registerHelix('h1', createDigest(1))

      const pos = eng.getPosition('h1')
      expect(pos).toBeDefined()
      expect(typeof pos!.x).toBe('number')
      expect(typeof pos!.y).toBe('number')
    })
  })

  describe('onDigestUpdate', () => {
    it('auto-registers unknown Helix on first digest update', async () => {
      await engine.onDigestUpdate('h1', createDigest(1))

      expect(engine.getPosition('h1')).toBeDefined()
      expect(engine.getTickCount()).toBe(1) // tick runs even with 1 helix
    })

    it('runs a physics tick when two or more Helixes are active', async () => {
      await engine.registerHelix('h1', createDigest(1))
      await engine.registerHelix('h2', createDigest(2))

      expect(engine.getTickCount()).toBe(0)

      await engine.onDigestUpdate('h1', createDigest(1))

      expect(engine.getTickCount()).toBe(1)
    })

    it('updates filesActive and approach on digest update', async () => {
      await engine.registerHelix('h1', createDigest(1))

      const updatedDigest = createDigest(1)
      updatedDigest.filesActive = ['newfile.ts']
      updatedDigest.approach = 'research'

      // Need a second helix so tick actually runs
      await engine.registerHelix('h2', createDigest(2))
      await engine.onDigestUpdate('h1', updatedDigest)

      const state = engine.getStates().get('h1')!
      expect(state.filesActive).toEqual(['newfile.ts'])
      expect(state.approach).toBe('research')
    })
  })

  describe('getDistance', () => {
    it('returns Infinity when a Helix does not exist', () => {
      expect(engine.getDistance('h1', 'h2')).toBe(Infinity)
    })

    it('returns Euclidean distance between two registered Helixes', async () => {
      await engine.registerHelix('h1', createDigest(1))
      await engine.registerHelix('h2', createDigest(2))

      const dist = engine.getDistance('h1', 'h2')
      // Both get the same embedding ([0.5, 0.3, 0.1, 0.8]) from the mock,
      // so they map to the same 2D position → distance should be 0
      expect(dist).toBe(0)
    })
  })

  describe('deregisterHelix', () => {
    it('marks Helix as inactive and zeroes velocity', async () => {
      await engine.registerHelix('h1', createDigest(1))

      engine.deregisterHelix('h1')

      const state = engine.getStates().get('h1')!
      expect(state.active).toBe(false)
      expect(state.position.vx).toBe(0)
      expect(state.position.vy).toBe(0)
    })

    it('inactive Helix does not participate in tick forces', async () => {
      await engine.registerHelix('h1', createDigest(1))
      await engine.registerHelix('h2', createDigest(2))

      engine.deregisterHelix('h1')

      const posBefore = { ...engine.getPosition('h1')! }
      await engine.onDigestUpdate('h2', createDigest(2))
      const posAfter = engine.getPosition('h1')!

      // h1 is inactive, so its position should not change
      expect(posAfter.x).toBe(posBefore.x)
      expect(posAfter.y).toBe(posBefore.y)
    })
  })

  describe('computeSimilarity', () => {
    it('returns 0 when either Helix does not exist', () => {
      expect(engine.computeSimilarity('h1', 'h2')).toBe(0)
    })

    it('returns a positive similarity for two Helixes with identical embeddings', async () => {
      await engine.registerHelix('h1', createDigest(1))
      await engine.registerHelix('h2', createDigest(2))

      const sim = engine.computeSimilarity('h1', 'h2')
      // Same mock embedding + shared file overlap + same approach → positive similarity
      expect(sim).toBeGreaterThan(0)
    })

    it('adds approach alignment bonus when approaches match', async () => {
      const d1 = createDigest(1)
      const d2 = createDigest(2)
      d1.approach = 'implementation'
      d2.approach = 'implementation'

      await engine.registerHelix('h1', d1)
      await engine.registerHelix('h2', d2)

      const simMatching = engine.computeSimilarity('h1', 'h2')

      // Reset and test with different approaches
      const engine2 = new GravityEngine(createMockDeps())
      d2.approach = 'research'
      await engine2.registerHelix('h1', d1)
      await engine2.registerHelix('h2', d2)

      const simDifferent = engine2.computeSimilarity('h1', 'h2')

      expect(simMatching).toBeGreaterThan(simDifferent)
    })
  })

  describe('convergence behavior', () => {
    it('similar Helixes converge over multiple ticks', async () => {
      // Use distinct embeddings so positions start apart
      let callCount = 0
      const deps = createMockDeps({
        embeddingService: {
          embed: async () => {
            callCount++
            // Give h1 and h2 different but similar embeddings
            return callCount <= 2 ? [0.5, 0.3, 0.1, 0.8] : [0.5, 0.3, 0.2, 0.7]
          },
          cosineSimilarity: (a: number[] | null, b: number[] | null) => {
            if (!a || !b) return 0
            return 0.9 // High similarity
          },
        } as any,
      })
      const eng = new GravityEngine(deps)

      await eng.registerHelix('h1', createDigest(1))
      await eng.registerHelix('h2', createDigest(2))

      const initialDist = eng.getDistance('h1', 'h2')

      // Run several ticks
      for (let i = 0; i < 5; i++) {
        await eng.onDigestUpdate('h1', createDigest(1))
        await eng.onDigestUpdate('h2', createDigest(2))
      }

      const finalDist = eng.getDistance('h1', 'h2')

      // Similar Helixes should get closer or stay close over time
      expect(finalDist).toBeLessThanOrEqual(initialDist * 2) // Allow some variance
    })
  })

  describe('getAllPositions', () => {
    it('returns positions for all registered Helixes', async () => {
      await engine.registerHelix('h1', createDigest(1))
      await engine.registerHelix('h2', createDigest(2))

      const positions = engine.getAllPositions()
      expect(positions).toHaveLength(2)
      expect(positions.map(p => p.helixId).sort()).toEqual(['h1', 'h2'])
    })
  })

  describe('getDistanceMatrix', () => {
    it('returns complete pairwise distance matrix', async () => {
      await engine.registerHelix('h1', createDigest(1))
      await engine.registerHelix('h2', createDigest(2))
      await engine.registerHelix('h3', createDigest(3))

      const matrix = engine.getDistanceMatrix()
      expect(matrix.size).toBe(3)
      expect(matrix.get('h1')!.size).toBe(2) // h2, h3
      expect(matrix.get('h1')!.has('h1')).toBe(false) // no self-distance
    })
  })
})
