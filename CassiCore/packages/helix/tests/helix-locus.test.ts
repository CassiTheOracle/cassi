/**
 * HelixLocus tests — Spark → Kindle → Radiate at session granularity.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HelixLocus } from '../src/helix-locus.js'
import type { CognitiveSignal } from '../src/vendor/core/intelligence/workspace/index.js'
import type { ILogger } from '@cassicore/foundation'


function createMockLogger(): ILogger {
  const logger: ILogger = {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    child: () => logger,
  } as any
  return logger
}


function makeSignal(partial: Partial<CognitiveSignal> & Pick<CognitiveSignal, 'signalId'>): CognitiveSignal {
  return {
    source: partial.source ?? 'helix-yang-a',
    sessionId: partial.sessionId ?? 'session-a',
    type: partial.type ?? 'observation',
    content: partial.content ?? 'test',
    luminance: partial.luminance ?? { novelty: 0, urgency: 0, relevance: 0, sourceCredibility: 0, composite: 0 },
    createdAt: Date.now(),
    metadata: partial.metadata,
    urgencyHint: partial.urgencyHint,
    ...partial,
  }
}


describe('HelixLocus', () => {
  let logger: ILogger
  let locus: HelixLocus

  beforeEach(() => {
    logger = createMockLogger()
    locus = new HelixLocus({ sessionId: 'session-a', logger, ignitionThreshold: 0.45 })
  })

  afterEach(() => {
    locus.drain()
  })

  it('scores signals and emits a spark per observation', () => {
    const sparks: any[] = []
    locus.on({ kind: 'spark', handler: s => sparks.push(s) })

    locus.observe(makeSignal({
      signalId: 's1',
      type: 'tension',
      metadata: { kind: 'challenge', posture: 'yin' },
    }))

    expect(sparks.length).toBe(1)
    expect(sparks[0].role).toBe('yin')
    expect(sparks[0].kind).toBe('challenge')
    expect(sparks[0].score.composite).toBeGreaterThan(0)
    expect(sparks[0].score.composite).toBeLessThanOrEqual(1)
  })

  it('kindles signals above the ignition threshold', () => {
    const kindles: any[] = []
    locus.on({ kind: 'kindle', handler: k => kindles.push(k) })

    // A challenge carries high urgency + novelty; it should kindle easily.
    locus.observe(makeSignal({
      signalId: 's1',
      type: 'tension',
      metadata: { kind: 'challenge', posture: 'yin', correlation: 'f-1' },
    }))

    expect(kindles.length).toBe(1)
    expect(kindles[0].kind).toBe('challenge')
    expect(kindles[0].score.composite).toBeGreaterThanOrEqual(0.45)
  })

  it('skips kindling for signals below the threshold', () => {
    const tight = new HelixLocus({ sessionId: 'session-a', logger, ignitionThreshold: 0.95 })
    const kindles: any[] = []
    tight.on({ kind: 'kindle', handler: k => kindles.push(k) })

    tight.observe(makeSignal({
      signalId: 's1',
      type: 'observation',
      metadata: { kind: 'work-unit', posture: 'unity' },
    }))

    expect(kindles.length).toBe(0)
    tight.drain()
  })

  it('ignores signals from other sessions', () => {
    const sparks: any[] = []
    locus.on({ kind: 'spark', handler: s => sparks.push(s) })

    locus.observe(makeSignal({
      signalId: 's1',
      sessionId: 'different-session',
      metadata: { kind: 'finding', posture: 'yang' },
    }))

    expect(sparks.length).toBe(0)
  })

  it('author-diversity rewards multi-posture correlation threads', () => {
    const scores: number[] = []
    locus.on({ kind: 'spark', handler: s => scores.push(s.score.authorDiversity) })

    locus.observe(makeSignal({ signalId: 's1', metadata: { kind: 'finding', posture: 'yang', correlation: 'f-1' } }))
    locus.observe(makeSignal({ signalId: 's2', source: 'helix-yin-a', metadata: { kind: 'challenge', posture: 'yin', correlation: 'f-1' } }))
    locus.observe(makeSignal({ signalId: 's3', source: 'helix-unity-a', metadata: { kind: 'concession', posture: 'unity', correlation: 'f-1' } }))

    expect(scores[0]).toBeLessThanOrEqual(scores[1]!)
    expect(scores[1]).toBeLessThanOrEqual(scores[2]!)
  })

  it('novelty decays with repeated same-posture same-kind signals', () => {
    const nov: number[] = []
    locus.on({ kind: 'spark', handler: s => nov.push(s.score.novelty) })

    for (let i = 0; i < 5; i++) {
      locus.observe(makeSignal({
        signalId: `s${i}`,
        metadata: { kind: 'work-unit', posture: 'unity' },
        source: 'helix-unity-a',
      }))
    }

    expect(nov[0]).toBeGreaterThan(nov[4]!)
  })

  it('targeted signals lower cross-relevance', () => {
    const results: number[] = []
    locus.on({ kind: 'spark', handler: s => results.push(s.score.crossRelevance) })

    locus.observe(makeSignal({
      signalId: 'broadcast',
      metadata: { kind: 'finding', posture: 'yang' },
    }))
    locus.observe(makeSignal({
      signalId: 'targeted',
      metadata: { kind: 'nudge', posture: 'yang', recipient: 'unity' },
    }))

    expect(results[0]).toBeGreaterThan(results[1]!)
  })

  it('drain() emits session-end radiance for every live kindle', () => {
    const radiances: any[] = []
    locus.on({ kind: 'radiance', handler: r => radiances.push(r) })

    locus.observe(makeSignal({ signalId: 's1', type: 'tension', metadata: { kind: 'challenge', posture: 'yin', correlation: 'f-1' } }))
    locus.observe(makeSignal({ signalId: 's2', type: 'warning', metadata: { kind: 'mentor-flag', posture: 'yang', correlation: 'f-2' } }))

    locus.drain()
    expect(radiances.length).toBeGreaterThanOrEqual(2)
    expect(radiances.every(r => r.reason === 'session-end')).toBe(true)
  })

  it('stats report sparks / kindles / unique postures', () => {
    locus.observe(makeSignal({ signalId: 's1', source: 'helix-yang-a', metadata: { kind: 'finding', posture: 'yang' } }))
    locus.observe(makeSignal({ signalId: 's2', source: 'helix-yin-a', metadata: { kind: 'challenge', posture: 'yin' } }))

    const stats = locus.getStats()
    expect(stats.sparksObserved).toBe(2)
    expect(stats.uniquePostures).toBe(2)
    expect(stats.kindlesEmitted).toBeGreaterThanOrEqual(1)
  })
})
