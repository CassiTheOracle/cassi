import { describe, it, expect, vi, beforeEach } from 'vitest'
import { LinkManager } from '../../../src/topology/link-manager.js'
import type { LinkManagerDeps } from '../../../src/topology/link-manager.js'
import type { GravityEngine } from '../../../src/topology/gravity-engine.js'
import type { ILogger } from '../../../src/vendor/types/interfaces.js'
import type { LinkConfig } from '../../../src/topology/topology-types.js'

function makeLogger(): ILogger {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn().mockReturnThis(),
  } as unknown as ILogger
}

function makeConfig(overrides: Partial<LinkConfig> = {}): LinkConfig {
  return {
    linkThreshold: 1.5,
    unlinkThreshold: 2.5,
    minLinkSimilarity: 0.4,
    mediumMergeStabilityTicks: 3,
    deepMergeStabilityTicks: 8,
    ...overrides,
  }
}

function makeGravityEngine(
  distances: Record<string, number> = {},
  similarities: Record<string, number> = {},
): GravityEngine {
  return {
    getDistance: vi.fn((a: string, b: string) => {
      const key = a < b ? `${a}::${b}` : `${b}::${a}`
      return distances[key] ?? 5.0
    }),
    computeSimilarity: vi.fn((a: string, b: string) => {
      const key = a < b ? `${a}::${b}` : `${b}::${a}`
      return similarities[key] ?? 0.5
    }),
  } as unknown as GravityEngine
}

function makeDeps(overrides: Partial<LinkManagerDeps> = {}): LinkManagerDeps {
  return {
    gravityEngine: makeGravityEngine(),
    logger: makeLogger(),
    config: makeConfig(),
    ...overrides,
  }
}

describe('LinkManager', () => {
  let manager: LinkManager

  beforeEach(() => {
    manager = new LinkManager(makeDeps())
  })

  describe('construction', () => {
    it('starts with no links', () => {
      expect(manager.getAllLinks()).toEqual([])
    })
  })

  describe('evaluate — link formation', () => {
    it('creates a link when distance < linkThreshold and similarity >= minLinkSimilarity', () => {
      const ge = makeGravityEngine(
        { 'h1::h2': 1.0 },
        { 'h1::h2': 0.8 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge }))

      manager.evaluate(['h1', 'h2'])

      const links = manager.getAllLinks()
      expect(links).toHaveLength(1)
      expect(links[0].helixIdA).toBe('h1')
      expect(links[0].helixIdB).toBe('h2')
      expect(links[0].distance).toBe(1.0)
      expect(links[0].similarity).toBe(0.8)
      expect(links[0].mergeDepth).toBe('shallow')
      expect(links[0].stabilityTicks).toBe(0)
    })

    it('does NOT create a link when distance >= linkThreshold', () => {
      const ge = makeGravityEngine(
        { 'h1::h2': 2.0 },
        { 'h1::h2': 0.9 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge }))

      manager.evaluate(['h1', 'h2'])
      expect(manager.getAllLinks()).toHaveLength(0)
    })

    it('does NOT create a link when similarity < minLinkSimilarity', () => {
      const ge = makeGravityEngine(
        { 'h1::h2': 0.5 },
        { 'h1::h2': 0.1 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge }))

      manager.evaluate(['h1', 'h2'])
      expect(manager.getAllLinks()).toHaveLength(0)
    })

    it('alphabetically orders helixIdA < helixIdB regardless of input order', () => {
      const ge = makeGravityEngine(
        { 'alpha::zeta': 0.5 },
        { 'alpha::zeta': 0.9 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge }))

      // Pass in reverse order
      manager.evaluate(['zeta', 'alpha'])

      const links = manager.getAllLinks()
      expect(links).toHaveLength(1)
      expect(links[0].helixIdA).toBe('alpha')
      expect(links[0].helixIdB).toBe('zeta')
    })
  })

  describe('evaluate — link dissolution (hysteresis)', () => {
    it('dissolves a link when distance > unlinkThreshold', () => {
      // First: form a link at close distance
      const ge = makeGravityEngine(
        { 'h1::h2': 1.0 },
        { 'h1::h2': 0.8 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge }))
      manager.evaluate(['h1', 'h2'])
      expect(manager.getAllLinks()).toHaveLength(1)

      // Now: distance exceeds unlinkThreshold (2.5)
      vi.mocked(ge.getDistance).mockReturnValue(3.0)
      vi.mocked(ge.computeSimilarity).mockReturnValue(0.8)
      manager.evaluate(['h1', 'h2'])
      expect(manager.getAllLinks()).toHaveLength(0)
    })

    it('keeps a link alive within the hysteresis band (linkThreshold < dist < unlinkThreshold)', () => {
      const ge = makeGravityEngine(
        { 'h1::h2': 1.0 },
        { 'h1::h2': 0.8 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge }))
      manager.evaluate(['h1', 'h2'])
      expect(manager.getAllLinks()).toHaveLength(1)

      // Distance rises to 2.0 (within hysteresis band 1.5-2.5)
      vi.mocked(ge.getDistance).mockReturnValue(2.0)
      manager.evaluate(['h1', 'h2'])
      expect(manager.getAllLinks()).toHaveLength(1)
    })
  })

  describe('evaluate — stability and merge depth promotion', () => {
    it('increments stabilityTicks on each stable evaluate', () => {
      const ge = makeGravityEngine(
        { 'h1::h2': 1.0 },
        { 'h1::h2': 0.8 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge }))

      manager.evaluate(['h1', 'h2'])
      expect(manager.getAllLinks()[0].stabilityTicks).toBe(0)

      manager.evaluate(['h1', 'h2'])
      expect(manager.getAllLinks()[0].stabilityTicks).toBe(1)

      manager.evaluate(['h1', 'h2'])
      expect(manager.getAllLinks()[0].stabilityTicks).toBe(2)
    })

    it('promotes shallow → medium after mediumMergeStabilityTicks', () => {
      const config = makeConfig({ mediumMergeStabilityTicks: 2 })
      const ge = makeGravityEngine(
        { 'h1::h2': 1.0 },
        { 'h1::h2': 0.8 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge, config }))

      manager.evaluate(['h1', 'h2']) // creates link, stability=0
      manager.evaluate(['h1', 'h2']) // stability=1
      expect(manager.getAllLinks()[0].mergeDepth).toBe('shallow')

      manager.evaluate(['h1', 'h2']) // stability=2 → promote to medium
      expect(manager.getAllLinks()[0].mergeDepth).toBe('medium')
    })

    it('promotes medium → deep after deepMergeStabilityTicks', () => {
      const config = makeConfig({
        mediumMergeStabilityTicks: 1,
        deepMergeStabilityTicks: 3,
      })
      const ge = makeGravityEngine(
        { 'h1::h2': 1.0 },
        { 'h1::h2': 0.8 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge, config }))

      manager.evaluate(['h1', 'h2']) // creates, stability=0
      manager.evaluate(['h1', 'h2']) // stability=1 → medium
      expect(manager.getAllLinks()[0].mergeDepth).toBe('medium')

      manager.evaluate(['h1', 'h2']) // stability=2
      manager.evaluate(['h1', 'h2']) // stability=3 → deep
      expect(manager.getAllLinks()[0].mergeDepth).toBe('deep')
    })

    it('does not promote past deep', () => {
      const config = makeConfig({
        mediumMergeStabilityTicks: 1,
        deepMergeStabilityTicks: 2,
      })
      const ge = makeGravityEngine(
        { 'h1::h2': 1.0 },
        { 'h1::h2': 0.8 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge, config }))

      // Run enough ticks to hit deep, then keep going
      for (let i = 0; i < 10; i++) {
        manager.evaluate(['h1', 'h2'])
      }
      expect(manager.getAllLinks()[0].mergeDepth).toBe('deep')
    })
  })

  describe('evaluate — cleanup of deregistered helixes', () => {
    it('removes links where both ends are inactive', () => {
      const ge = makeGravityEngine(
        { 'h1::h2': 1.0 },
        { 'h1::h2': 0.8 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge }))
      manager.evaluate(['h1', 'h2'])
      expect(manager.getAllLinks()).toHaveLength(1)

      // Evaluate with neither h1 nor h2 in the active set
      manager.evaluate(['h3'])
      expect(manager.getAllLinks()).toHaveLength(0)
    })
  })

  describe('removeHelix', () => {
    it('removes all links involving a specific Helix', () => {
      const ge = makeGravityEngine(
        { 'h1::h2': 1.0, 'h1::h3': 1.0, 'h2::h3': 1.0 },
        { 'h1::h2': 0.8, 'h1::h3': 0.8, 'h2::h3': 0.8 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge }))
      manager.evaluate(['h1', 'h2', 'h3'])
      expect(manager.getAllLinks()).toHaveLength(3)

      manager.removeHelix('h1')
      const remaining = manager.getAllLinks()
      expect(remaining).toHaveLength(1)
      expect(remaining[0].helixIdA).toBe('h2')
      expect(remaining[0].helixIdB).toBe('h3')
    })
  })

  describe('query methods', () => {
    let ge: GravityEngine

    beforeEach(() => {
      ge = makeGravityEngine(
        { 'h1::h2': 1.0, 'h1::h3': 1.0, 'h2::h3': 5.0 },
        { 'h1::h2': 0.8, 'h1::h3': 0.7, 'h2::h3': 0.1 },
      )
      manager = new LinkManager(makeDeps({ gravityEngine: ge }))
      manager.evaluate(['h1', 'h2', 'h3'])
    })

    it('getLinksFor returns only links involving the given Helix', () => {
      // h1-h2 and h1-h3 are linked (close + similar), h2-h3 is not (far + low similarity)
      const h1Links = manager.getLinksFor('h1')
      expect(h1Links).toHaveLength(2)

      const h3Links = manager.getLinksFor('h3')
      expect(h3Links).toHaveLength(1)
    })

    it('areLinked returns true for linked pairs and false otherwise', () => {
      expect(manager.areLinked('h1', 'h2')).toBe(true)
      expect(manager.areLinked('h2', 'h1')).toBe(true) // order-independent
      expect(manager.areLinked('h2', 'h3')).toBe(false)
    })

    it('getLink returns the link object or undefined', () => {
      const link = manager.getLink('h1', 'h2')
      expect(link).toBeDefined()
      expect(link!.distance).toBe(1.0)

      expect(manager.getLink('h2', 'h3')).toBeUndefined()
    })

    it('getNeighbors returns all Helixes linked to the given one', () => {
      const neighbors = manager.getNeighbors('h1')
      expect(neighbors).toHaveLength(2)
      expect(neighbors).toContain('h2')
      expect(neighbors).toContain('h3')

      // h3 only linked to h1
      const h3neighbors = manager.getNeighbors('h3')
      expect(h3neighbors).toHaveLength(1)
      expect(h3neighbors).toContain('h1')
    })

    it('getNeighbors returns empty for an unlinked Helix', () => {
      expect(manager.getNeighbors('h99')).toEqual([])
    })
  })

  describe('multiple pairs', () => {
    it('handles many pairs independently', () => {
      const distances: Record<string, number> = {
        'a::b': 0.5,
        'a::c': 0.5,
        'b::c': 4.0,
        'a::d': 0.5,
        'b::d': 4.0,
        'c::d': 4.0,
      }
      const similarities: Record<string, number> = {
        'a::b': 0.9,
        'a::c': 0.9,
        'b::c': 0.1,
        'a::d': 0.9,
        'b::d': 0.1,
        'c::d': 0.1,
      }
      const ge = makeGravityEngine(distances, similarities)
      manager = new LinkManager(makeDeps({ gravityEngine: ge }))

      manager.evaluate(['a', 'b', 'c', 'd'])

      // Only 3 links should form: a-b, a-c, a-d (close + high sim)
      // b-c, b-d, c-d are far + low similarity
      const links = manager.getAllLinks()
      expect(links).toHaveLength(3)
      expect(manager.areLinked('a', 'b')).toBe(true)
      expect(manager.areLinked('a', 'c')).toBe(true)
      expect(manager.areLinked('a', 'd')).toBe(true)
      expect(manager.areLinked('b', 'c')).toBe(false)
    })
  })
})
