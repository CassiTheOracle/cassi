/**
 * B1.2 Aurora.evaluateAffectPredicates lifecycle tests.
 *
 * Covers edge transitions (false→true → activate, true→false → deactivate),
 * scaledModulated strength updates without re-invocation, and audit log
 * rows that capture the predicate-driven trigger.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'

import { Aurora } from '../index.js'
import type { AuroraConfig } from '../types.js'
import { AURORA_DEFAULTS } from '../types.js'
import type { Affect } from '@cassicore/mnemic-field'

function makeLogger() {
  const log: any = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {} }
  log.child = () => log
  return log
}

function makeCortex(): any {
  return { list: () => [], retrieve: async () => [], getAffectState: () => undefined }
}

function makeFakePersistence(dbPath: string): any {
  return {
    getDbPath: () => dbPath,
    beginSession: () => ({ sessionId: 'aur_test', inheritsFrom: null, createdAt: Date.now() }),
    hydrateClaustrum: () => ({ nodes: [], edges: [] }),
    hydrateReasoningLog: () => [],
    hydrateMomentum: () => null,
  }
}

function buildAurora(dbPath: string): Aurora {
  const cfg: Partial<AuroraConfig> = {
    ...AURORA_DEFAULTS,
    gapDetectionEnabled: false,
    meditationSeederEnabled: false,
    autoSchedulerEnabled: false,
    eventJournalEnabled: false,
    welfareAggregatorEnabled: false,
    refusalChannelEnabled: false,
    overlayLayerEnabled: false,
    cassiSpecChannelEnabled: false,
    modificationAuditEnabled: false,
    traceReplayEnabled: false,
    saturationDetectorEnabled: false,
    diversityFloorEnabled: false,
    counterfactualEngineEnabled: false,
    coherenceCheckEnabled: false,
    narrativeEnabled: false,
    compositionEnabled: true,
  }
  return new Aurora(makeCortex(), null, null, null, makeLogger(), cfg, makeFakePersistence(dbPath))
}

const calm: Affect = { valence: 0.3, arousal: 0.2 }
const frantic: Affect = { valence: -0.4, arousal: 0.85 }

describe('Aurora.evaluateAffectPredicates (B1.2)', () => {
  let dbPath: string
  let aurora: Aurora

  beforeEach(() => {
    dbPath = `/tmp/aurora-b12-test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`
    aurora = buildAurora(dbPath)
  })

  afterEach(() => {
    aurora.getCompositionStore()?.close()
    try { fs.unlinkSync(dbPath) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-wal`) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-shm`) } catch { /* ignore */ }
  })

  it('activates a predicate-modulated composition when the predicate becomes true', () => {
    aurora.defineComposition('careful = gate("rigor") + gate("clarity") - gate("haste") | when arousal < 0.4')
    expect(aurora.activeCompositions()).toHaveLength(0)

    const t1 = aurora.evaluateAffectPredicates(calm)
    expect(t1.activated).toEqual(['careful'])
    expect(aurora.activeCompositions().map(c => c.name)).toEqual(['careful'])
    expect(aurora.activeCompositions()[0].trigger).toBe('affect_predicate')
  })

  it('deactivates on the false transition', () => {
    aurora.defineComposition('careful = gate("rigor") | when arousal < 0.4')
    aurora.evaluateAffectPredicates(calm)
    const t2 = aurora.evaluateAffectPredicates(frantic)
    expect(t2.deactivated).toEqual(['careful'])
    expect(aurora.activeCompositions()).toHaveLength(0)
  })

  it('is idempotent on repeated calls with the same affect', () => {
    aurora.defineComposition('careful = gate("rigor") | when arousal < 0.4')
    aurora.evaluateAffectPredicates(calm)
    const t2 = aurora.evaluateAffectPredicates(calm)
    expect(t2.activated).toEqual([])
    expect(t2.deactivated).toEqual([])
    expect(aurora.activeCompositions()).toHaveLength(1)
  })

  it('does not interfere with manual invocations of the same composition', () => {
    aurora.defineComposition('careful = gate("rigor") | when arousal < 0.4')
    aurora.invokeComposition('careful', { ttlTurns: 5 }) // manual
    aurora.evaluateAffectPredicates(calm) // also adds an affect_predicate-triggered entry

    const active = aurora.activeCompositions()
    expect(active).toHaveLength(2)
    const triggers = active.map(c => c.trigger).sort()
    expect(triggers).toEqual(['affect_predicate', 'manual'])

    // Predicate flips false: only the affect_predicate entry leaves
    aurora.evaluateAffectPredicates(frantic)
    const after = aurora.activeCompositions()
    expect(after).toHaveLength(1)
    expect(after[0].trigger).toBe('manual')
  })

  it('scaledModulated activates with strength = expression value', () => {
    aurora.defineComposition('soft = gate("rigor") | scaled_by(1 - arousal)')
    aurora.evaluateAffectPredicates(calm) // arousal 0.2 → strength 0.8
    const active = aurora.activeCompositions()
    expect(active).toHaveLength(1)
    expect(active[0].magnitudeScale).toBeCloseTo(0.8)
  })

  it('scaledModulated updates magnitudeScale in place when strength changes', () => {
    aurora.defineComposition('soft = gate("rigor") | scaled_by(1 - arousal)')
    aurora.evaluateAffectPredicates(calm) // arousal 0.2 → strength 0.8
    const t2 = aurora.evaluateAffectPredicates({ valence: 0, arousal: 0.5 })
    expect(t2.activated).toEqual([])
    expect(t2.deactivated).toEqual([])
    expect(t2.updated).toEqual([{ name: 'soft', magnitudeScale: 0.5 }])
    expect(aurora.activeCompositions()[0].magnitudeScale).toBeCloseTo(0.5)
  })

  it('scaledModulated deactivates when strength clamps to 0', () => {
    aurora.defineComposition('soft = gate("rigor") | scaled_by(1 - arousal)')
    aurora.evaluateAffectPredicates(calm)
    const t2 = aurora.evaluateAffectPredicates({ valence: 0, arousal: 1 }) // 1 - 1 = 0
    expect(t2.deactivated).toEqual(['soft'])
    expect(aurora.activeCompositions()).toHaveLength(0)
  })

  it('does not touch non-modulated compositions', () => {
    aurora.defineComposition('plain = gate("warmth")')
    aurora.invokeComposition('plain')
    const t = aurora.evaluateAffectPredicates(calm)
    expect(t.activated).toEqual([])
    expect(t.deactivated).toEqual([])
    expect(aurora.activeCompositions().map(c => c.name)).toEqual(['plain'])
  })

  it('audit log records each predicate-driven activation', () => {
    aurora.defineComposition('careful = gate("rigor") | when arousal < 0.4')
    aurora.evaluateAffectPredicates(calm, undefined, { sessionId: 'sess-A' })
    aurora.evaluateAffectPredicates(frantic) // deactivates
    aurora.evaluateAffectPredicates(calm, undefined, { sessionId: 'sess-B' }) // re-activates
    const log = aurora.getCompositionStore()!.listInvocations({ limit: 10 })
    const triggers = log.map(l => l.trigger)
    expect(triggers).toEqual(['affect_predicate', 'affect_predicate'])
    expect(log[0].sessionId).toBe('sess-B')
    expect(log[1].sessionId).toBe('sess-A')
  })

  it('handles the label predicate when caller supplies the resolved label', () => {
    aurora.defineComposition('warm_focus = gate("focus") | when label == "calm"')
    const t1 = aurora.evaluateAffectPredicates(calm, 'calm')
    expect(t1.activated).toEqual(['warm_focus'])
    const t2 = aurora.evaluateAffectPredicates(calm, 'frustrated')
    expect(t2.deactivated).toEqual(['warm_focus'])
  })
})
