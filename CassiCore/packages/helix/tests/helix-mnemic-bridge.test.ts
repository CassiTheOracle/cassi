/**
 * HelixMnemicBridge tests — milestone engrams for brain-integrated sessions.
 *
 * Uses a mock MnemicField that records store() + connect() calls so we can
 * assert the bridge writes the right engram types and synapses in response
 * to lifecycle + kindle events.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { HelixMnemicBridge } from '../src/helix-mnemic-bridge.js'
import { HelixJournal } from '../src/helix-journal.js'
import { HelixLocus } from '../src/helix-locus.js'
import type { ILogger } from '@cassicore/foundation'
import type { CognitiveSignal } from '../src/vendor/core/intelligence/workspace/index.js'


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


interface StoredEngram {
  id: string
  nodeType: string
  content: string
  tags: string[]
  metadata: Record<string, unknown>
}

interface StoredSynapse {
  sourceId: string
  targetId: string
  edgeType: string
  metadata?: Record<string, unknown>
}

function createMockMnemicField() {
  const engrams: StoredEngram[] = []
  const synapses: StoredSynapse[] = []
  let id = 0
  const mf: any = {
    store: vi.fn((input: any) => {
      const engramId = `eng-${++id}`
      const entry: StoredEngram = {
        id: engramId,
        nodeType: input.nodeType,
        content: input.content,
        tags: input.tags ?? [],
        metadata: input.metadata ?? {},
      }
      engrams.push(entry)
      return { id: engramId, ...entry }
    }),
    connect: vi.fn((input: any) => {
      const syn: StoredSynapse = {
        sourceId: input.sourceId,
        targetId: input.targetId,
        edgeType: input.edgeType,
        metadata: input.metadata,
      }
      synapses.push(syn)
      return syn
    }),
  }
  return { mf, engrams, synapses }
}


function makeSignal(metadata: Record<string, unknown>): CognitiveSignal {
  return {
    signalId: `sig-${Math.random()}`,
    source: 'helix-yang-x',
    sessionId: 'session-a',
    type: 'observation',
    content: 'test content',
    luminance: { novelty: 0.5, urgency: 0.5, relevance: 0.5, sourceCredibility: 0.5, composite: 0.9 },
    createdAt: Date.now(),
    metadata,
  }
}


describe('HelixMnemicBridge', () => {
  let logger: ILogger
  let journal: HelixJournal

  beforeEach(() => {
    logger = createMockLogger()
    journal = new HelixJournal({ logger, inMemory: true })
  })

  afterEach(() => {
    journal.close()
  })

  it('writes a `session` engram on start, closes with one on stop', async () => {
    const { mf, engrams } = createMockMnemicField()
    const bridge = new HelixMnemicBridge({
      sessionId: 'session-a',
      goal: 'test goal',
      logger,
      mnemicField: mf,
      journal,
    })

    await bridge.start()
    expect(engrams.length).toBe(1)
    expect(engrams[0]!.nodeType).toBe('session')
    expect(engrams[0]!.tags).toContain('session:session-a')

    await bridge.stop('ok')
    expect(engrams.length).toBe(2)
    expect(engrams[1]!.metadata).toMatchObject({ outcome: 'ok', written: 1 })
  })

  it('maps kindle kinds to the right engram types', async () => {
    const { mf, engrams } = createMockMnemicField()
    const locus = new HelixLocus({ sessionId: 'session-a', logger, ignitionThreshold: 0 })
    const bridge = new HelixMnemicBridge({
      sessionId: 'session-a',
      goal: 'g',
      logger,
      mnemicField: mf,
      journal,
      locus,
    })
    await bridge.start()

    locus.observe(makeSignal({ kind: 'work-unit', posture: 'unity' }))
    locus.observe(makeSignal({ kind: 'finding', posture: 'yang', correlation: 'f-1' }))
    locus.observe(makeSignal({ kind: 'challenge', posture: 'yin', correlation: 'f-1' }))
    locus.observe(makeSignal({ kind: 'concession', posture: 'unity', correlation: 'f-1' }))
    locus.observe(makeSignal({ kind: 'mentor-flag', posture: 'yang' }))

    const byType = engrams.reduce<Record<string, number>>((acc, e) => {
      acc[e.nodeType] = (acc[e.nodeType] ?? 0) + 1
      return acc
    }, {})
    expect(byType['session']).toBe(1)
    expect(byType['outcome']).toBe(1)   // work-unit
    expect(byType['abstraction']).toBe(1) // finding
    expect(byType['concern']).toBe(1)   // challenge
    expect(byType['decision']).toBe(1)  // concession
    expect(byType['anomaly']).toBe(1)   // mentor-flag

    await bridge.stop()
  })

  it('wires concessions back to the matching concern via synapse', async () => {
    const { mf, engrams, synapses } = createMockMnemicField()
    const locus = new HelixLocus({ sessionId: 'session-a', logger, ignitionThreshold: 0 })
    const bridge = new HelixMnemicBridge({
      sessionId: 'session-a',
      goal: 'g',
      logger,
      mnemicField: mf,
      locus,
    })
    await bridge.start()

    locus.observe(makeSignal({ kind: 'challenge', posture: 'yin', correlation: 'f-1' }))
    locus.observe(makeSignal({ kind: 'concession', posture: 'unity', correlation: 'f-1' }))

    const challengeEngram = engrams.find(e => e.nodeType === 'concern')
    const concessionEngram = engrams.find(e => e.nodeType === 'decision')
    expect(challengeEngram).toBeTruthy()
    expect(concessionEngram).toBeTruthy()

    const mitigatesSynapse = synapses.find(s => s.edgeType === 'mitigates')
    expect(mitigatesSynapse).toBeTruthy()
    expect(mitigatesSynapse!.sourceId).toBe(concessionEngram!.id)
    expect(mitigatesSynapse!.targetId).toBe(challengeEngram!.id)

    await bridge.stop()
  })

  it('journals engram.write entries when a journal is attached', async () => {
    const { mf } = createMockMnemicField()
    const locus = new HelixLocus({ sessionId: 'session-a', logger, ignitionThreshold: 0 })
    const bridge = new HelixMnemicBridge({
      sessionId: 'session-a',
      goal: 'g',
      logger,
      mnemicField: mf,
      journal,
      locus,
    })
    await bridge.start()

    locus.observe(makeSignal({ kind: 'challenge', posture: 'yin', correlation: 'f-1' }))

    const writes = journal.readSession('session-a').filter(e => e.eventType === 'engram.write')
    expect(writes.length).toBeGreaterThanOrEqual(2) // session + challenge
    expect(writes.some(e => (e.payload as any).nodeType === 'concern')).toBe(true)

    await bridge.stop()
  })

  it('is resilient when Mnemic Field throws', async () => {
    const { mf } = createMockMnemicField()
    const errorMf = { ...mf, store: vi.fn(() => { throw new Error('disk full') }), connect: vi.fn() }
    const bridge = new HelixMnemicBridge({
      sessionId: 'session-a',
      goal: 'g',
      logger,
      mnemicField: errorMf as any,
      journal,
    })
    await expect(bridge.start()).resolves.toBeUndefined()
    expect(bridge.getStats().failed).toBeGreaterThanOrEqual(1)
    await bridge.stop()
  })
})
