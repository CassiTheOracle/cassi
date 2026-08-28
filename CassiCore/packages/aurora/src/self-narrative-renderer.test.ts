import { describe, it, expect } from 'vitest'
import { SelfNarrativeRenderer } from './self-narrative-renderer.js'
import type { MentalState, AuroraConfig } from './types.js'
import { AURORA_DEFAULTS } from './types.js'

const stubLogger = { child: () => stubLogger, debug: () => {}, info: () => {}, warn: () => {}, error: () => {} } as any

function makeState(overrides: Partial<MentalState> = {}): MentalState {
  return {
    graph: { nodes: new Map(), edges: new Map(), reverseEdges: new Map(), sourceBreakdown: { model: 0, memory: 0, observer: 0, both: 0 }, edgeCount: 0, builtAt: Date.now() },
    resonanceHubs: [],
    gaps: [],
    recentDiscoveries: [],
    affect: null,
    foci: [],
    momentum: { trendingConcepts: [], acceleration: 0, dominantDirection: 'deepening', shifts: [] },
    coherence: 0.75,
    integration: 0.6,
    computedAt: Date.now(),
    durationMs: 10,
    ...overrides,
  }
}

describe('SelfNarrativeRenderer', () => {
  it('returns null when disabled', () => {
    const config = { ...AURORA_DEFAULTS, narrativeEnabled: false }
    const r = new SelfNarrativeRenderer(stubLogger, config)
    expect(r.render(makeState({ foci: ['auth'] }))).toBeNull()
  })

  it('renders focus clause', () => {
    const r = new SelfNarrativeRenderer(stubLogger, AURORA_DEFAULTS)
    const result = r.render(makeState({ foci: ['authentication', 'session-flow'] }))
    expect(result).not.toBeNull()
    expect(result!.text).toContain("I'm focused on authentication and session-flow")
    expect(result!.clauses.some(c => c.sourceFacts.includes('foci'))).toBe(true)
  })

  it('renders affect clause from valence/arousal', () => {
    const r = new SelfNarrativeRenderer(stubLogger, AURORA_DEFAULTS)
    const result = r.render(makeState({
      affect: { label: 'calm-engaged', affect: { valence: 0.6, arousal: 0.7 }, confidence: 0.9 },
    }))
    expect(result!.text).toContain('engaged')
  })

  it('renders momentum with trending concepts', () => {
    const r = new SelfNarrativeRenderer(stubLogger, AURORA_DEFAULTS)
    const result = r.render(makeState({
      momentum: { trendingConcepts: ['auth', 'session'], acceleration: 0.5, dominantDirection: 'deepening', shifts: [] },
    }))
    expect(result!.text).toContain('gravitating toward auth, session')
  })

  it('respects char budget', () => {
    const config = { ...AURORA_DEFAULTS, narrativeMaxChars: 60 }
    const r = new SelfNarrativeRenderer(stubLogger, config)
    const result = r.render(makeState({
      foci: ['one', 'two', 'three'],
      affect: { label: 'engaged', affect: { valence: 0.8, arousal: 0.9 }, confidence: 0.9 },
      momentum: { trendingConcepts: ['a', 'b', 'c'], acceleration: 0.5, dominantDirection: 'deepening', shifts: [] },
      gaps: [{ id: 'g1', modelNode: 'x', memoryNode: 'y', gapType: 'missing_edge' as any, severity: 0.5, detectedAt: Date.now() }],
      coherence: 0.2,
    }))
    expect(result).not.toBeNull()
    expect(result!.charCount).toBeLessThanOrEqual(80)
  })

  it('returns null for empty state with no renderable clauses', () => {
    const r = new SelfNarrativeRenderer(stubLogger, AURORA_DEFAULTS)
    const result = r.render(makeState())
    // coherence is 0.75 — within [0.4, 0.8] so no clause generated
    expect(result).toBeNull()
  })

  it('renders coherence clause for low coherence', () => {
    const r = new SelfNarrativeRenderer(stubLogger, AURORA_DEFAULTS)
    const result = r.render(makeState({ coherence: 0.25 }))
    expect(result!.text).toContain('fragmentation')
  })

  it('renders coherence clause for high coherence', () => {
    const r = new SelfNarrativeRenderer(stubLogger, AURORA_DEFAULTS)
    const result = r.render(makeState({ coherence: 0.95 }))
    expect(result!.text).toContain('coherent')
  })

  it('renders gaps clause', () => {
    const r = new SelfNarrativeRenderer(stubLogger, AURORA_DEFAULTS)
    const result = r.render(makeState({
      gaps: [
        { entity: 'x', knownBy: 'model' as const, knowledge: 'rel-y', strength: 0.5, gapType: 'missing' as const },
        { entity: 'a', knownBy: 'memory' as const, knowledge: 'rel-b', strength: 0.3, gapType: 'complementary' as const },
      ],
    }))
    expect(result!.text).toContain("gaps in what I know")
  })

  it('renders discoveries clause', () => {
    const r = new SelfNarrativeRenderer(stubLogger, AURORA_DEFAULTS)
    const result = r.render(makeState({
      recentDiscoveries: [{ sourceId: 'a', targetId: 'b', sharedFeatureCount: 5, jaccardSimilarity: 0.6, gateScoreCorrelation: 0.8, topOverlapLayers: [], combinedScore: 0.7 }],
    }))
    expect(result!.text).toContain('new connections')
  })

  it('truncates focus list for many foci', () => {
    const r = new SelfNarrativeRenderer(stubLogger, AURORA_DEFAULTS)
    const result = r.render(makeState({ foci: ['a', 'b', 'c', 'd', 'e'] }))
    expect(result!.text).toContain('a, b and 3 others')
  })
})
