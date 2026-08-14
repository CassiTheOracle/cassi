import { describe, it, expect, beforeEach } from 'vitest'
import { FieldHealthAnalyzer, type FieldHealthSnapshot } from '../src/meditation/field-health.js'
import { mockLogger } from './helpers.js'

const FIFTEEN_MIN_MS = 15 * 60 * 1000

class StubStore {
  private kv = new Map<string, string>()
  getMetaText(key: string): string | undefined { return this.kv.get(key) }
  setMetaText(key: string, value: string): void { this.kv.set(key, value) }
}

interface SessionRecord {
  timestamp: number
  before: { fragmentationScore: number }
  after: { fragmentationScore: number }
  regionsTouched?: string[]
  metrics?: Record<string, number>
}

function seedSessions(store: StubStore, sessions: SessionRecord[]): void {
  store.setMetaText('organizing_session_history', JSON.stringify(sessions))
}

function makeSnapshot(overrides: Partial<FieldHealthSnapshot> = {}): FieldHealthSnapshot {
  return {
    timestamp: Date.now(),
    engramCount: 200,
    synapseCount: 60,
    fragmentationScore: 0.7,
    connectionDensity: 0.3,
    abstractionCoverage: 0.5,
    potentiationSpread: 0.2,
    orphanRatio: 0.1,
    tensionLoad: 0,
    regions: [
      { id: 'r1', label: 'r1', memberCount: 10, avgPotentiation: 0.5, avgCharge: 1.2, hasAbstraction: true, neglectScore: 0.1 },
      { id: 'r2', label: 'r2', memberCount: 8, avgPotentiation: 0.4, avgCharge: 0.9, hasAbstraction: true, neglectScore: 0.1 },
    ],
    fieldGrowthRate: 0,
    ...overrides,
  } as FieldHealthSnapshot
}

function makeAnalyzer(store: StubStore, snapshot: FieldHealthSnapshot): FieldHealthAnalyzer {
  const mnemicStub = {
    stats: () => ({ totalEngrams: snapshot.engramCount, totalSynapses: snapshot.synapseCount, orphanedEngrams: 5 }),
    listNuclei: () => [],
    listAbstractions: () => [],
    tensions: () => [],
  } as any
  const a = new FieldHealthAnalyzer(mnemicStub, mockLogger(), store as any)
  ;(a as any).snapshot = () => snapshot
  return a
}

describe('FieldHealthAnalyzer.shouldOrganize cooldown', () => {
  let store: StubStore

  beforeEach(() => { store = new StubStore() })

  it('returns "field too small" when fewer than 10 engrams', () => {
    const a = makeAnalyzer(store, makeSnapshot({ engramCount: 5 }))
    const r = a.shouldOrganize()
    expect(r.trigger).toBe(false)
    expect(r.reason).toBe('field too small')
  })

  it('blocks organizing when last session is within 15-minute hard floor', () => {
    const now = Date.now()
    seedSessions(store, [
      { timestamp: now - 5 * 60_000, before: { fragmentationScore: 0.9 }, after: { fragmentationScore: 0.85 } },
    ])
    const a = makeAnalyzer(store, makeSnapshot({ fragmentationScore: 0.9 }))
    const r = a.shouldOrganize()
    expect(r.trigger).toBe(false)
    expect(r.reason).toMatch(/cooldown.*5m ago/)
  })

  it('allows organizing once the hard floor has passed and fragmentation is high', () => {
    const now = Date.now()
    seedSessions(store, [
      { timestamp: now - (FIFTEEN_MIN_MS + 60_000), before: { fragmentationScore: 0.9 }, after: { fragmentationScore: 0.85 } },
    ])
    const a = makeAnalyzer(store, makeSnapshot({ fragmentationScore: 0.7 }))
    const r = a.shouldOrganize()
    expect(r.trigger).toBe(true)
    expect(r.reason).toMatch(/high fragmentation/)
  })

  it('raises the fragmentation threshold after a streak of weak sessions', () => {
    // Two delta-weak sessions where regions WERE touched (so suppression
    // doesn't fire — only the threshold raise should activate).
    const now = Date.now()
    const oldEnough = (m: number) => now - (FIFTEEN_MIN_MS + m * 60_000)
    seedSessions(store, [
      { timestamp: oldEnough(60), before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.69 },  regionsOrganized: ['r1'] },
      { timestamp: oldEnough(30), before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.695 }, regionsOrganized: ['r1'] },
    ] as any)
    const a = makeAnalyzer(store, makeSnapshot({ fragmentationScore: 0.7 }))
    const r = a.shouldOrganize()
    expect(r.trigger).toBe(false)
    expect(r.reason).toMatch(/below threshold/)
  })

  it('resets the weak-streak counter after a strong session', () => {
    const now = Date.now()
    const oldEnough = (m: number) => now - (FIFTEEN_MIN_MS + m * 60_000)
    seedSessions(store, [
      { timestamp: oldEnough(120), before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.695 }, regionsOrganized: ['r1'] },
      { timestamp: oldEnough(90),  before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.69 },  regionsOrganized: ['r1'] },
      { timestamp: oldEnough(60),  before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.50 },  regionsOrganized: ['r1'] },
      { timestamp: oldEnough(30),  before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.69 },  regionsOrganized: ['r1'] },
    ] as any)
    const a = makeAnalyzer(store, makeSnapshot({ fragmentationScore: 0.7 }))
    const r = a.shouldOrganize()
    expect(r.reason).toMatch(/threshold raised to 0\.65 after 1 weak/)
  })

  // Note: a previous test exercising the +0.20 cap on threshold-raise was
  // removed when NOOP_SUPPRESSION_FLOOR (3) was added. With suppression in
  // place, the cap is unreachable through the public `shouldOrganize` API
  // — any sequence long enough to push the threshold past +0.20 hits
  // suppression first. The cap math survives in `computeOrganizingBackoff`
  // as a safety against future relaxations of the suppression floor.

  // Regression tests for the runaway pattern observed in the 2026-05-06
  // daemon log: the neglected-regions trigger path bypassed the
  // weak-streak threshold raise, so organizing kept firing every cooldown
  // window with `regionsOrganized=0` and no fragmentation movement,
  // chewing 85-300s of event-loop time per session.

  it('counts a session with regionsOrganized=[] as weak even if fragmentation moves slightly', () => {
    // A session that touched no regions cannot have moved fragmentation
    // legitimately. Treat it as weak regardless of the fragmentation
    // delta floor, so the streak counter tracks what's actually happening.
    const now = Date.now()
    const oldEnough = (m: number) => now - (FIFTEEN_MIN_MS + m * 60_000)
    seedSessions(store, [
      { timestamp: oldEnough(120), before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.695 }, regionsOrganized: [] },
      { timestamp: oldEnough(90),  before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.695 }, regionsOrganized: [] },
      { timestamp: oldEnough(60),  before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.695 }, regionsOrganized: [] },
    ] as any)
    const a = makeAnalyzer(store, makeSnapshot({ fragmentationScore: 0.7 }))
    const r = a.shouldOrganize()
    expect(r.trigger).toBe(false)
    expect(r.reason).toMatch(/suppressed.*3 consecutive weak/)
  })

  it('suppresses neglected-regions trigger after NOOP_SUPPRESSION_FLOOR weak sessions', () => {
    // Live daemon pattern: 3+ weak sessions in a row, fragmentation flat,
    // neglected-regions trigger keeps trying to fire every cooldown
    // window. Confirm suppression overrides the neglected-regions path
    // — the path that previously bypassed every backoff.
    const now = Date.now()
    const oldEnough = (m: number) => now - (FIFTEEN_MIN_MS + m * 60_000)
    seedSessions(store, [
      { timestamp: oldEnough(120), before: { fragmentationScore: 0.45 }, after: { fragmentationScore: 0.45 }, regionsOrganized: [] },
      { timestamp: oldEnough(90),  before: { fragmentationScore: 0.45 }, after: { fragmentationScore: 0.45 }, regionsOrganized: [] },
      { timestamp: oldEnough(60),  before: { fragmentationScore: 0.45 }, after: { fragmentationScore: 0.45 }, regionsOrganized: [] },
    ] as any)
    // Snapshot mimics live daemon: low fragmentation but ALL regions
    // marked severely neglected (which the path-4 trigger would normally
    // fire on).
    const allNeglected = makeSnapshot({
      fragmentationScore: 0.45,
      regions: [
        { id: 'r1', label: 'r1', memberCount: 10, avgPotentiation: 0.5, avgCharge: 1.2, hasAbstraction: true, neglectScore: 0.95 },
        { id: 'r2', label: 'r2', memberCount: 8,  avgPotentiation: 0.4, avgCharge: 0.9, hasAbstraction: true, neglectScore: 0.95 },
        { id: 'r3', label: 'r3', memberCount: 8,  avgPotentiation: 0.4, avgCharge: 0.9, hasAbstraction: true, neglectScore: 0.95 },
      ] as any,
    })
    const a = makeAnalyzer(store, allNeglected)
    const r = a.shouldOrganize()
    expect(r.trigger).toBe(false)
    expect(r.reason).toMatch(/suppressed/)
  })

  it('lifts noop suppression after a session with regionsOrganized > 0', () => {
    // A successful session (any region touched) breaks the streak and
    // re-enables organizing on subsequent triggers.
    const now = Date.now()
    const oldEnough = (m: number) => now - (FIFTEEN_MIN_MS + m * 60_000)
    seedSessions(store, [
      { timestamp: oldEnough(150), before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.695 }, regionsOrganized: [] },
      { timestamp: oldEnough(120), before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.695 }, regionsOrganized: [] },
      { timestamp: oldEnough(90),  before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.695 }, regionsOrganized: [] },
      // Strong recovery session: actually touched a region AND moved frag.
      { timestamp: oldEnough(60),  before: { fragmentationScore: 0.7 }, after: { fragmentationScore: 0.55 },  regionsOrganized: ['r1'] },
    ] as any)
    const a = makeAnalyzer(store, makeSnapshot({ fragmentationScore: 0.7 }))
    const r = a.shouldOrganize()
    expect(r.trigger).toBe(true)
    expect(r.reason).toMatch(/high fragmentation/)
  })
})
