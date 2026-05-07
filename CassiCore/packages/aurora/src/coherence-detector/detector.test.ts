/**
 * N2 PostureCoherenceDetector tests — the three live categories
 * (composition_pair_cancelling, composition_pair_contradictory,
 * composition_meditation_suppression) with the four stub categories
 * verified to return [] until their inputs land.
 */

import { describe, it, expect } from 'vitest'

import { PostureCoherenceDetector } from './index.js'
import { parseComposition } from '../composition/parser.js'
import type { CompositionRecord, ActiveComposition } from '../composition/types.js'

function makeLogger() {
  const log: any = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {} }
  log.child = () => log
  return log
}

function rec(name: string, dsl: string, suppressive = false): CompositionRecord {
  const parsed = parseComposition(dsl)
  return {
    name,
    dsl,
    ast: parsed.ast,
    layerPolicy: 'all',
    affectModulated: parsed.ast.kind === 'modulated' || parsed.ast.kind === 'scaledModulated',
    suppressive,
    vindexId: 'default',
    description: null,
    createdAt: '2026-05-06T00:00:00Z',
    updatedAt: '2026-05-06T00:00:00Z',
    metadata: {},
  }
}

function active(name: string, scale = 1): ActiveComposition {
  return {
    name,
    ast: { kind: 'gate', label: 'unused' },
    invokedAt: '2026-05-06T00:00:00Z',
    ttlTurns: 5,
    remainingTurns: 5,
    magnitudeScale: scale,
    trigger: 'manual',
  }
}

describe('PostureCoherenceDetector', () => {
  const detector = new PostureCoherenceDetector(makeLogger())

  it('returns no checks when fewer than 2 compositions are active', () => {
    expect(detector.detect({ active: [], records: [], pendingSeeds: [] })).toEqual([])
    expect(detector.detect({
      active: [active('solo')],
      records: [rec('solo', 'solo = gate("a")')],
      pendingSeeds: [],
    })).toEqual([])
  })

  it('flags composition_pair_cancelling when two compositions partly oppose', () => {
    const checks = detector.detect({
      active: [active('a'), active('b')],
      records: [
        rec('a', 'a = gate("warmth") + gate("rigor") - gate("haste")'),
        rec('b', 'b = gate("haste") - gate("warmth") * 0.5'),
      ],
      pendingSeeds: [],
    })
    const c = checks.find(x => x.category === 'composition_pair_cancelling' || x.category === 'composition_pair_contradictory')
    expect(c).toBeDefined()
    expect(c!.involvedElements.map(e => e.id).sort()).toEqual(['a', 'b'])
  })

  it('flags composition_pair_contradictory when overlap dominates one composition', () => {
    const checks = detector.detect({
      active: [active('warm'), active('cold')],
      records: [
        rec('warm', 'warm = gate("warmth") + gate("kindness")'),
        rec('cold', 'cold = gate("coldness") - gate("warmth") - gate("kindness")'),
      ],
      pendingSeeds: [],
    })
    const c = checks.find(x => x.category === 'composition_pair_contradictory')
    expect(c).toBeDefined()
    expect(c!.severity).toBe('warning')
    expect(c!.recommendation).toBeTruthy()
  })

  it('does not flag pairs that share gates with the same sign', () => {
    const checks = detector.detect({
      active: [active('a'), active('b')],
      records: [
        rec('a', 'a = gate("x") + gate("y")'),
        rec('b', 'b = gate("x") + gate("z")'),
      ],
      pendingSeeds: [],
    })
    expect(checks.filter(c => c.category.startsWith('composition_pair'))).toHaveLength(0)
  })

  it('respects cancellingThreshold (small overlap is suppressed)', () => {
    const tightDetector = new PostureCoherenceDetector(makeLogger(), { cancellingThreshold: 1.0 })
    const checks = tightDetector.detect({
      active: [active('a'), active('b')],
      records: [
        rec('a', 'a = gate("x") * 0.2'),
        rec('b', 'b = -gate("x") * 0.1'),
      ],
      pendingSeeds: [],
    })
    expect(checks.filter(c => c.category.startsWith('composition_pair'))).toHaveLength(0)
  })

  it('flags composition_meditation_suppression when seed targets suppressed label', () => {
    const checks = detector.detect({
      active: [active('quiet')],
      records: [
        rec('quiet', 'quiet = gate("calm") - affect("frustrated")', true),
      ],
      pendingSeeds: [
        { id: 'seed-A', gapId: 'g1', topic: 'Investigate sources of frustrated reasoning', entryPoints: [], expectedRefinement: '', proposedAt: '', proposedBy: 'curator', status: 'pending', budget: { maxTurns: 10, maxCostUsd: 0.25 }, metadata: {} } as any,
      ],
    })
    const c = checks.find(x => x.category === 'composition_meditation_suppression')
    expect(c).toBeDefined()
    expect(c!.severity).toBe('serious')
    expect(c!.involvedElements.some(e => e.kind === 'meditation_seed' && e.id === 'seed-A')).toBe(true)
  })

  it('does not flag suppression when no suppressive composition is active', () => {
    const checks = detector.detect({
      active: [active('plain')],
      records: [
        rec('plain', 'plain = gate("focus")', false),
      ],
      pendingSeeds: [
        { id: 'seed-A', gapId: 'g1', topic: 'frustrated reasoning', entryPoints: [], expectedRefinement: '', proposedAt: '', proposedBy: 'curator', status: 'pending', budget: { maxTurns: 10, maxCostUsd: 0.25 }, metadata: {} } as any,
      ],
    })
    expect(checks.filter(c => c.category === 'composition_meditation_suppression')).toHaveLength(0)
  })

  it('does not fire any of the optional-input categories when inputs are absent', () => {
    const checks = detector.detect({
      active: [active('a')],
      records: [rec('a', 'a = gate("x")')],
      pendingSeeds: [],
    })
    const optionalCategories = ['composition_retrieval_mismatch', 'replay_affect_mismatch', 'meditation_entrypoint_cold', 'composition_meditation_cold_topic']
    for (const cat of optionalCategories) {
      expect(checks.filter(c => c.category === cat)).toHaveLength(0)
    }
  })
})

describe('PostureCoherenceDetector — composition × retrieval policy', () => {
  const detector = new PostureCoherenceDetector(makeLogger())

  it('flags composition_retrieval_mismatch when suppressive composition meets non-neutral policy', () => {
    const checks = detector.detect({
      active: [active('quiet')],
      records: [rec('quiet', 'quiet = gate("calm") - gate("loud") - gate("frenetic")', true)],
      pendingSeeds: [],
      retrievalPolicy: { affectBias: 'complementary' },
    })
    const c = checks.find(x => x.category === 'composition_retrieval_mismatch')
    expect(c).toBeDefined()
    expect(c!.severity).toBe('warning')
    expect(c!.message).toContain('complementary')
    expect(c!.involvedElements.some(e => e.kind === 'retrieval_policy')).toBe(true)
  })

  it('does not flag when policy is neutral', () => {
    const checks = detector.detect({
      active: [active('quiet')],
      records: [rec('quiet', 'quiet = gate("calm") - gate("loud")', true)],
      pendingSeeds: [],
      retrievalPolicy: { affectBias: 'neutral' },
    })
    expect(checks.filter(c => c.category === 'composition_retrieval_mismatch')).toHaveLength(0)
  })

  it('does not flag when no composition is suppressive', () => {
    const checks = detector.detect({
      active: [active('plain')],
      records: [rec('plain', 'plain = gate("focus")', false)],
      pendingSeeds: [],
      retrievalPolicy: { affectBias: 'similar' },
    })
    expect(checks.filter(c => c.category === 'composition_retrieval_mismatch')).toHaveLength(0)
  })
})

describe('PostureCoherenceDetector — replay × affect', () => {
  const detector = new PostureCoherenceDetector(makeLogger())

  it('flags replay_affect_mismatch when distance exceeds threshold', () => {
    const checks = detector.detect({
      active: [],
      records: [],
      pendingSeeds: [],
      currentAffect: { valence: -0.5, arousal: 0.8 },
      scheduledReplays: [{ id: 'r1', sourceAffect: { valence: 0.5, arousal: 0.2 } }],
    })
    const c = checks.find(x => x.category === 'replay_affect_mismatch')
    expect(c).toBeDefined()
    expect(c!.severity).toBe('warning')
    expect(c!.involvedElements.some(e => e.kind === 'replay' && e.id === 'r1')).toBe(true)
  })

  it('does not flag when affect distance is below threshold', () => {
    const checks = detector.detect({
      active: [],
      records: [],
      pendingSeeds: [],
      currentAffect: { valence: 0.4, arousal: 0.3 },
      scheduledReplays: [{ id: 'r1', sourceAffect: { valence: 0.5, arousal: 0.2 } }],
    })
    expect(checks.filter(c => c.category === 'replay_affect_mismatch')).toHaveLength(0)
  })

  it('does not flag when sourceAffect is absent', () => {
    const checks = detector.detect({
      active: [],
      records: [],
      pendingSeeds: [],
      currentAffect: { valence: 0, arousal: 0 },
      scheduledReplays: [{ id: 'r1' }],
    })
    expect(checks.filter(c => c.category === 'replay_affect_mismatch')).toHaveLength(0)
  })

  it('honors a custom replayAffectMismatchThreshold', () => {
    const tightDetector = new PostureCoherenceDetector(makeLogger(), { replayAffectMismatchThreshold: 2.0 })
    const checks = tightDetector.detect({
      active: [],
      records: [],
      pendingSeeds: [],
      currentAffect: { valence: -0.5, arousal: 0.8 },
      scheduledReplays: [{ id: 'r1', sourceAffect: { valence: 0.5, arousal: 0.2 } }],
    })
    expect(checks.filter(c => c.category === 'replay_affect_mismatch')).toHaveLength(0)
  })
})

describe('PostureCoherenceDetector — meditation entry-points cold', () => {
  const detector = new PostureCoherenceDetector(makeLogger())

  function seed(id: string, topic: string): any {
    return {
      id, gapId: 'g1', topic, entryPoints: [], expectedRefinement: '',
      proposedAt: '', proposedBy: 'curator', status: 'pending',
      budget: { maxTurns: 10, maxCostUsd: 0.25 }, metadata: {},
    }
  }

  it('flags meditation_entrypoint_cold when topic mentions only cold nodes', () => {
    const checks = detector.detect({
      active: [],
      records: [],
      pendingSeeds: [seed('s1', 'Investigate frustrated reasoning patterns')],
      claustrumActivations: new Map([['frustrated', 0.05], ['reasoning', 0.08]]),
    })
    const c = checks.find(x => x.category === 'meditation_entrypoint_cold')
    expect(c).toBeDefined()
    expect(c!.severity).toBe('warning')
    expect(c!.involvedElements.some(e => e.kind === 'meditation_seed')).toBe(true)
  })

  it('does not flag when topic has at least one warm node', () => {
    const checks = detector.detect({
      active: [],
      records: [],
      pendingSeeds: [seed('s1', 'frustrated reasoning')],
      claustrumActivations: new Map([['frustrated', 0.05], ['reasoning', 0.6]]),
    })
    expect(checks.filter(c => c.category === 'meditation_entrypoint_cold')).toHaveLength(0)
  })

  it('flags when topic has no matching claustrum nodes at all', () => {
    const checks = detector.detect({
      active: [],
      records: [],
      pendingSeeds: [seed('s1', 'completely unrelated topic')],
      claustrumActivations: new Map([['warmth', 0.9], ['rigor', 0.5]]),
    })
    const c = checks.find(x => x.category === 'meditation_entrypoint_cold')
    expect(c).toBeDefined()
    expect(c!.message).toContain('no claustrum nodes in topic')
  })
})

describe('PostureCoherenceDetector — composition vs meditation cold-topic', () => {
  const detector = new PostureCoherenceDetector(makeLogger())

  function seed(id: string, topic: string): any {
    return {
      id, gapId: 'g1', topic, entryPoints: [], expectedRefinement: '',
      proposedAt: '', proposedBy: 'curator', status: 'pending',
      budget: { maxTurns: 10, maxCostUsd: 0.25 }, metadata: {},
    }
  }

  it('flags composition_meditation_cold_topic when boost lands on cold concept', () => {
    const checks = detector.detect({
      active: [active('booster')],
      records: [rec('booster', 'booster = gate("frustrated") + gate("doubt")', false)],
      pendingSeeds: [seed('s1', 'frustrated reasoning')],
      claustrumActivations: new Map([['frustrated', 0.05], ['doubt', 0.0]]),
    })
    const c = checks.find(x => x.category === 'composition_meditation_cold_topic')
    expect(c).toBeDefined()
    expect(c!.severity).toBe('info')
    expect(c!.message).toContain('frustrated')
  })

  it('does not flag when boosted label is warm in claustrum', () => {
    const checks = detector.detect({
      active: [active('booster')],
      records: [rec('booster', 'booster = gate("frustrated")', false)],
      pendingSeeds: [seed('s1', 'frustrated reasoning')],
      claustrumActivations: new Map([['frustrated', 0.6]]),
    })
    expect(checks.filter(c => c.category === 'composition_meditation_cold_topic')).toHaveLength(0)
  })

  it('does not flag when boost label not in topic', () => {
    const checks = detector.detect({
      active: [active('booster')],
      records: [rec('booster', 'booster = gate("warmth")', false)],
      pendingSeeds: [seed('s1', 'rigor focus')],
      claustrumActivations: new Map([['warmth', 0.0]]),
    })
    expect(checks.filter(c => c.category === 'composition_meditation_cold_topic')).toHaveLength(0)
  })

  it('only counts positive (boosting) contributions, not suppressive ones', () => {
    const checks = detector.detect({
      active: [active('quiet')],
      records: [rec('quiet', 'quiet = -gate("frustrated")', true)],
      pendingSeeds: [seed('s1', 'frustrated reasoning')],
      claustrumActivations: new Map([['frustrated', 0.0]]),
    })
    expect(checks.filter(c => c.category === 'composition_meditation_cold_topic')).toHaveLength(0)
  })

  it('rankChecks orders serious > warning > info', () => {
    const checks = detector.detect({
      active: [active('warm'), active('cold'), active('quiet')],
      records: [
        rec('warm', 'warm = gate("warmth")'),
        rec('cold', 'cold = -gate("warmth")'),
        rec('quiet', 'quiet = gate("calm") - affect("frustrated")', true),
      ],
      pendingSeeds: [
        { id: 'seed-A', gapId: 'g1', topic: 'frustrated', entryPoints: [], expectedRefinement: '', proposedAt: '', proposedBy: 'curator', status: 'pending', budget: { maxTurns: 10, maxCostUsd: 0.25 }, metadata: {} } as any,
      ],
    })
    const ranked = detector.rankChecks(checks)
    expect(ranked[0].severity).toBe('serious')
    const orderIdx = (s: string) => ({ serious: 0, warning: 1, info: 2 } as Record<string, number>)[s]
    for (let i = 1; i < ranked.length; i++) {
      expect(orderIdx(ranked[i].severity)).toBeGreaterThanOrEqual(orderIdx(ranked[i - 1].severity))
    }
  })

  it('topN trims to the configured projection size', () => {
    const checks = detector.detect({
      active: [active('a1'), active('a2'), active('b1'), active('b2')],
      records: [
        rec('a1', 'a1 = gate("x")'),
        rec('a2', 'a2 = -gate("x")'),
        rec('b1', 'b1 = gate("y")'),
        rec('b2', 'b2 = -gate("y")'),
      ],
      pendingSeeds: [],
    })
    expect(detector.topN(checks, 2)).toHaveLength(2)
  })
})
