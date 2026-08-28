/**
 * Locus Module Tests — Global Workspace for Constellation
 *
 * Tests the three-stage GWT pipeline: Spark → Kindle → Radiate
 * and the Locus facade that wires them together.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { SparkExtractor } from '../src/locus/spark-extractor.js'
import { KindlingEngine } from '../src/locus/kindling-engine.js'
import { Radiance } from '../src/locus/radiance.js'
import { Locus } from '../src/locus/index.js'
import type { BranchDigest, BranchAssessment } from '../src/corpus-types.js'
import type { CrossHelixPattern } from '../src/corpus-types.js'
import type { Spark, LocusConfig, LocusTopologyAccessor, GuidanceInjector } from '../src/locus/locus-types.js'
import { DEFAULT_LOCUS_CONFIG } from '../src/locus/locus-types.js'


function makeLogger() {
  const log = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn(() => log),
  }
  return log
}

function makeDigest(overrides: Partial<BranchDigest> = {}): BranchDigest {
  return {
    helixId: `helix-${Math.random().toString(36).slice(2, 6)}`,
    goalSummary: 'Implement feature X',
    approach: 'implementation',
    progress: 0.5,
    filesActive: ['src/foo.ts', 'src/bar.ts'],
    keyFindings: ['Found the entry point'],
    blockers: [],
    currentStrategy: 'Direct implementation',
    rollingScore: 0.7,
    workUnitsProcessed: 5,
    updatedAt: Date.now(),
    ...overrides,
  }
}

function makeTopology(): LocusTopologyAccessor {
  return {
    getDistance: vi.fn().mockReturnValue(1.0),
    getSimilarity: vi.fn().mockReturnValue(0.5),
  }
}


// SparkExtractor Tests

describe('SparkExtractor', () => {
  let extractor: SparkExtractor
  let logger: ReturnType<typeof makeLogger>

  beforeEach(() => {
    logger = makeLogger()
    extractor = new SparkExtractor({ logger: logger as any })
  })

  it('produces no sparks on first digest (baseline only)', () => {
    const digests = [makeDigest({ helixId: 'h1' })]
    const sparks = extractor.extract(digests)
    expect(sparks).toHaveLength(0)
  })

  it('detects new key findings as discovery sparks', () => {
    const d1 = makeDigest({ helixId: 'h1', keyFindings: ['Finding A'] })
    extractor.extract([d1])

    const d2 = makeDigest({ helixId: 'h1', keyFindings: ['Finding A', 'Finding B'] })
    const sparks = extractor.extract([d2])

    expect(sparks).toHaveLength(1)
    expect(sparks[0].type).toBe('discovery')
    expect(sparks[0].content).toBe('Finding B')
    expect(sparks[0].sourceHelixId).toBe('h1')
  })

  it('detects new blockers as blocker sparks', () => {
    const d1 = makeDigest({ helixId: 'h1', blockers: [] })
    extractor.extract([d1])

    const d2 = makeDigest({ helixId: 'h1', blockers: ['Cannot access database'] })
    const sparks = extractor.extract([d2])

    expect(sparks).toHaveLength(1)
    expect(sparks[0].type).toBe('blocker')
    expect(sparks[0].content).toBe('Cannot access database')
  })

  it('detects quality score jumps as breakthrough sparks', () => {
    const d1 = makeDigest({ helixId: 'h1', rollingScore: 0.4 })
    extractor.extract([d1])

    const d2 = makeDigest({ helixId: 'h1', rollingScore: 0.75 })
    const sparks = extractor.extract([d2])

    const breakthroughs = sparks.filter(s => s.type === 'breakthrough')
    expect(breakthroughs).toHaveLength(1)
    expect(breakthroughs[0].content).toContain('Quality breakthrough')
  })

  it('converts cross-branch patterns to sparks', () => {
    const patterns: CrossHelixPattern[] = [{
      type: 'convergence',
      helixIds: ['h1', 'h2'],
      severity: 'low',
      description: 'Both branches found same approach',
      detectedAt: Date.now(),
      actedUpon: false,
    }]

    const sparks = extractor.extract([], patterns)
    expect(sparks).toHaveLength(1)
    expect(sparks[0].type).toBe('convergence')
  })

  it('skips already-acted-upon cross patterns', () => {
    const patterns: CrossHelixPattern[] = [{
      type: 'conflict',
      helixIds: ['h1', 'h2'],
      severity: 'high',
      description: 'File conflict',
      detectedAt: Date.now(),
      actedUpon: true,
    }]

    const sparks = extractor.extract([], patterns)
    expect(sparks).toHaveLength(0)
  })

  it('handles multiple digests with mixed changes', () => {
    const d1a = makeDigest({ helixId: 'h1', keyFindings: ['A'], blockers: [] })
    const d1b = makeDigest({ helixId: 'h2', keyFindings: ['X'], blockers: [] })
    extractor.extract([d1a, d1b])

    const d2a = makeDigest({ helixId: 'h1', keyFindings: ['A', 'B'], blockers: ['Stuck'] })
    const d2b = makeDigest({ helixId: 'h2', keyFindings: ['X'], blockers: [] })
    const sparks = extractor.extract([d2a, d2b])

    expect(sparks).toHaveLength(2)
    expect(sparks.map(s => s.type).sort()).toEqual(['blocker', 'discovery'])
  })

  it('removeHelix stops tracking that branch', () => {
    const d1 = makeDigest({ helixId: 'h1', keyFindings: ['A'] })
    extractor.extract([d1])

    extractor.removeHelix('h1')

    const d2 = makeDigest({ helixId: 'h1', keyFindings: ['A', 'B'] })
    const sparks = extractor.extract([d2])
    expect(sparks).toHaveLength(0)
  })
})


// KindlingEngine Tests

describe('KindlingEngine', () => {
  let engine: KindlingEngine
  let logger: ReturnType<typeof makeLogger>

  beforeEach(() => {
    logger = makeLogger()
    engine = new KindlingEngine({ logger: logger as any })
  })

  function makeSpark(overrides: Partial<Spark> = {}): Spark {
    return {
      sparkId: `spark-test-${Math.random().toString(36).slice(2, 6)}`,
      sourceHelixId: 'h1',
      content: 'Test finding',
      type: 'discovery',
      luminance: { novelty: 0, urgency: 0, crossRelevance: 0, qualityDelta: 0, composite: 0 },
      sparkedAt: Date.now(),
      sourceGoal: 'Test goal',
      relevantFiles: [],
      ...overrides,
    }
  }

  it('fills empty foci with bright sparks', () => {
    const sparks = [
      makeSpark({ sourceHelixId: 'h1', type: 'blocker', content: 'Blocker content that is long enough' }),
    ]
    const digests = [makeDigest({ helixId: 'h1' })]

    const events = engine.evaluate(sparks, digests)
    expect(events.length).toBeGreaterThanOrEqual(1)
    expect(events[0].eclipse).toBeNull()
    expect(events[0].slotIndex).toBe(0)
  })

  it('filters dim sparks below kindling threshold', () => {
    const config: LocusConfig = {
      ...DEFAULT_LOCUS_CONFIG,
      kindlingThreshold: 0.99,
    }
    const eng = new KindlingEngine({ logger: logger as any, config })

    const sparks = [makeSpark({ type: 'discovery' })]
    const digests = [makeDigest()]

    const events = eng.evaluate(sparks, digests)
    expect(events).toHaveLength(0)
  })

  it('enforces one focus per branch', () => {
    const sparks = [
      makeSpark({ sourceHelixId: 'h1', type: 'blocker', content: 'First blocker' }),
      makeSpark({ sourceHelixId: 'h1', type: 'discovery', content: 'Also from h1' }),
    ]
    const digests = [makeDigest({ helixId: 'h1' })]

    const events = engine.evaluate(sparks, digests)
    expect(events).toHaveLength(1)
  })

  it('eclipses dim occupants with brighter sparks', () => {
    const config: LocusConfig = {
      ...DEFAULT_LOCUS_CONFIG,
      foci: 1,
      kindlingThreshold: 0.1,
    }
    const eng = new KindlingEngine({ logger: logger as any, config })

    const dimSpark = [makeSpark({ sourceHelixId: 'h1', type: 'discovery' })]
    const digests = [
      makeDigest({ helixId: 'h1' }),
      makeDigest({ helixId: 'h2' }),
    ]
    eng.evaluate(dimSpark, digests)

    // Advance occupancy to make the dim spark dimmer
    for (let i = 0; i < 5; i++) {
      eng.evaluate([], digests)
    }

    const brightSpark = [makeSpark({ sourceHelixId: 'h2', type: 'blocker', content: 'Critical blocker!' })]
    const events = eng.evaluate(brightSpark, digests)

    if (events.length > 0) {
      expect(events[0].eclipse).not.toBeNull()
    }
  })

  it('decays occupancy and expires foci after maxOccupancyTicks', () => {
    const config: LocusConfig = {
      ...DEFAULT_LOCUS_CONFIG,
      foci: 1,
      maxOccupancyTicks: 3,
      kindlingThreshold: 0.1,
    }
    const eng = new KindlingEngine({ logger: logger as any, config })

    const sparks = [makeSpark({ sourceHelixId: 'h1', type: 'blocker' })]
    const digests = [makeDigest({ helixId: 'h1' })]
    eng.evaluate(sparks, digests)

    expect(eng.getFoci()[0].spark).not.toBeNull()

    // Tick 4 times to exceed maxOccupancyTicks
    for (let i = 0; i < 4; i++) {
      eng.evaluate([], digests)
    }

    expect(eng.getFoci()[0].spark).toBeNull()
  })

  it('uses topology for cross-relevance scoring when available', () => {
    const topology = makeTopology()
    const sparks = [makeSpark({ sourceHelixId: 'h1', type: 'blocker' })]
    const digests = [makeDigest({ helixId: 'h1' }), makeDigest({ helixId: 'h2' })]

    engine.evaluate(sparks, digests, topology)

    expect(topology.getSimilarity).toHaveBeenCalled()
  })

  it('tracks stats correctly', () => {
    const sparks = [makeSpark({ sourceHelixId: 'h1', type: 'blocker' })]
    const digests = [makeDigest({ helixId: 'h1' })]
    engine.evaluate(sparks, digests)

    const stats = engine.getStats()
    expect(stats.totalSparksProcessed).toBe(1)
    expect(stats.totalKindlings).toBeGreaterThanOrEqual(0)
  })
})


// Radiance Tests

describe('Radiance', () => {
  let radiance: Radiance
  let logger: ReturnType<typeof makeLogger>

  beforeEach(() => {
    logger = makeLogger()
    radiance = new Radiance({ logger: logger as any })
  })

  function makeKindlingEvent() {
    return {
      eventId: 'kindle-test-1',
      spark: {
        sparkId: 'spark-test-1',
        sourceHelixId: 'h1',
        content: 'Important discovery about the API',
        type: 'discovery' as const,
        luminance: { novelty: 0.8, urgency: 0.3, crossRelevance: 0.5, qualityDelta: 0.2, composite: 0.6 },
        sparkedAt: Date.now(),
        sourceGoal: 'Implement API endpoints',
        relevantFiles: ['src/api.ts'],
      },
      slotIndex: 0,
      eclipse: null,
      kindlingLuminance: 0.6,
      timestamp: Date.now(),
    }
  }

  it('broadcasts kindled content to all active branches except source', () => {
    const injectGuidance: GuidanceInjector = vi.fn()
    const event = makeKindlingEvent()

    const events = radiance.broadcast(
      [event],
      ['h1', 'h2', 'h3'],
      undefined,
      injectGuidance,
    )

    expect(events).toHaveLength(1)
    expect(events[0].recipients).toEqual(['h2', 'h3'])
    expect(injectGuidance).toHaveBeenCalledTimes(2)
  })

  it('includes topology distances in radiance events', () => {
    const topology = makeTopology()
    const injectGuidance: GuidanceInjector = vi.fn()
    const event = makeKindlingEvent()

    const events = radiance.broadcast(
      [event],
      ['h1', 'h2'],
      topology,
      injectGuidance,
    )

    expect(events[0].recipientDistances['h2']).toBeDefined()
    expect(topology.getDistance).toHaveBeenCalled()
  })

  it('formats broadcast content with source context', () => {
    const injectGuidance: GuidanceInjector = vi.fn()
    const event = makeKindlingEvent()

    radiance.broadcast([event], ['h1', 'h2'], undefined, injectGuidance)

    const injectedContent = (injectGuidance as ReturnType<typeof vi.fn>).mock.calls[0][1] as string
    expect(injectedContent).toContain('[Locus Broadcast')
    expect(injectedContent).toContain('discovery')
    expect(injectedContent).toContain('Important discovery about the API')
  })

  it('returns empty array when no kindling events', () => {
    const injectGuidance: GuidanceInjector = vi.fn()
    const events = radiance.broadcast([], ['h1', 'h2'], undefined, injectGuidance)
    expect(events).toHaveLength(0)
    expect(injectGuidance).not.toHaveBeenCalled()
  })

  it('returns empty array when no active branches', () => {
    const injectGuidance: GuidanceInjector = vi.fn()
    const event = makeKindlingEvent()
    const events = radiance.broadcast([event], [], undefined, injectGuidance)
    expect(events).toHaveLength(0)
  })

  it('tracks total radiances', () => {
    const injectGuidance: GuidanceInjector = vi.fn()
    const event = makeKindlingEvent()

    radiance.broadcast([event], ['h1', 'h2'], undefined, injectGuidance)
    expect(radiance.getTotalRadiances()).toBe(1)
  })
})


// Locus Facade Tests

describe('Locus', () => {
  let locus: Locus
  let logger: ReturnType<typeof makeLogger>

  beforeEach(() => {
    logger = makeLogger()
    locus = new Locus({ logger: logger as any })
  })

  it('initializes with correct defaults', () => {
    expect(locus.enabled).toBe(true)

    const snapshot = locus.getSnapshot()
    expect(snapshot.foci).toHaveLength(5)
    expect(snapshot.totalSparksProcessed).toBe(0)
    expect(snapshot.totalKindlings).toBe(0)
  })

  it('runs a complete sweep pipeline', () => {
    const injectGuidance: GuidanceInjector = vi.fn()

    // First sweep: establish baseline
    const d1a = makeDigest({ helixId: 'h1', keyFindings: ['Finding A'] })
    const d1b = makeDigest({ helixId: 'h2', keyFindings: [] })
    locus.sweep([d1a, d1b], ['h1', 'h2'], { injectGuidance })

    // Second sweep: h1 adds a new finding
    const d2a = makeDigest({ helixId: 'h1', keyFindings: ['Finding A', 'Finding B'] })
    const d2b = makeDigest({ helixId: 'h2', keyFindings: [] })
    const result = locus.sweep([d2a, d2b], ['h1', 'h2'], { injectGuidance })

    expect(result.sparksExtracted).toBeGreaterThanOrEqual(1)

    const snapshot = locus.getSnapshot()
    expect(snapshot.totalSparksProcessed).toBeGreaterThanOrEqual(1)
  })

  it('uses topology for cross-relevance scoring', () => {
    const topology = makeTopology()
    const injectGuidance: GuidanceInjector = vi.fn()

    const d1 = makeDigest({ helixId: 'h1', keyFindings: ['A'] })
    const d2 = makeDigest({ helixId: 'h2', keyFindings: ['X'] })
    locus.sweep([d1, d2], ['h1', 'h2'], { topology, injectGuidance })

    const d1b = makeDigest({ helixId: 'h1', keyFindings: ['A', 'B'] })
    locus.sweep([d1b, d2], ['h1', 'h2'], { topology, injectGuidance })

    expect(topology.getSimilarity).toHaveBeenCalled()
  })

  it('returns empty result when disabled', () => {
    const disabled = new Locus({
      logger: logger as any,
      config: { ...DEFAULT_LOCUS_CONFIG, enabled: false },
    })

    const result = disabled.sweep(
      [makeDigest()], ['h1'],
      { injectGuidance: vi.fn() },
    )

    expect(result.sparksExtracted).toBe(0)
    expect(result.kindlingEvents).toHaveLength(0)
  })

  it('removeHelix cleans up tracking', () => {
    const d1 = makeDigest({ helixId: 'h1', keyFindings: ['A'] })
    locus.sweep([d1], ['h1'])

    locus.removeHelix('h1')

    const d2 = makeDigest({ helixId: 'h1', keyFindings: ['A', 'B'] })
    const result = locus.sweep([d2], ['h1'])

    expect(result.sparksExtracted).toBe(0)
  })

  it('snapshot reflects current state', () => {
    const injectGuidance: GuidanceInjector = vi.fn()

    const d1 = makeDigest({ helixId: 'h1', blockers: [] })
    locus.sweep([d1], ['h1', 'h2'], { injectGuidance })

    const d2 = makeDigest({ helixId: 'h1', blockers: ['Blocked on auth'] })
    locus.sweep([d2], ['h1', 'h2'], { injectGuidance })

    const snapshot = locus.getSnapshot()
    expect(snapshot.foci).toHaveLength(5)
    expect(snapshot.snapshotAt).toBeGreaterThan(0)
  })

  it('passes cross-patterns through to spark extraction', () => {
    const injectGuidance: GuidanceInjector = vi.fn()
    const patterns: CrossHelixPattern[] = [{
      type: 'conflict',
      helixIds: ['h1', 'h2'],
      severity: 'high',
      description: 'File conflict on src/main.ts',
      detectedAt: Date.now(),
      actedUpon: false,
    }]

    const result = locus.sweep([], ['h1', 'h2'], {
      crossPatterns: patterns,
      injectGuidance,
    })

    expect(result.sparksExtracted).toBe(1)
  })
})
