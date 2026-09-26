/**
 * B1 Aurora API tests — define/invoke/active/deactivate lifecycle.
 *
 * Mirrors the constructor pattern from auto-scheduler-wiring.test.ts since
 * Aurora has positional args.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'

import { Aurora } from '../index.js'
import type { AuroraConfig } from '../types.js'
import { AURORA_DEFAULTS } from '../types.js'

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

function buildAurora(dbPath: string, overrides?: Partial<AuroraConfig>): Aurora {
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
    ...overrides,
  }
  return new Aurora(makeCortex(), null, null, null, makeLogger(), cfg, makeFakePersistence(dbPath))
}

describe('Aurora composition API (B1.1a)', () => {
  let dbPath: string
  let aurora: Aurora

  beforeEach(() => {
    dbPath = `/tmp/aurora-comp-api-test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`
    aurora = buildAurora(dbPath)
  })

  afterEach(() => {
    aurora.getCompositionStore()?.close()
    try { fs.unlinkSync(dbPath) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-wal`) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-shm`) } catch { /* ignore */ }
  })

  it('throws when compositionEnabled is false', () => {
    const dbPath2 = `/tmp/aurora-comp-disabled-${Date.now()}.db`
    const a = buildAurora(dbPath2, { compositionEnabled: false })
    expect(() => a.defineComposition('p = gate("x")')).toThrow(/compositionStore disabled/)
    try { fs.unlinkSync(dbPath2) } catch { /* ignore */ }
  })

  it('refuses bare expressions (require named definition)', () => {
    expect(() => aurora.defineComposition('gate("x") + gate("y")')).toThrow(/named definition/)
  })

  it('defines, invokes, and lists active compositions', () => {
    aurora.defineComposition('calm_focus = gate("calm") + gate("focus") - gate("reactivity")')
    const inv = aurora.invokeComposition('calm_focus', { ttlTurns: 3 })
    expect(inv.name).toBe('calm_focus')
    expect(inv.trigger).toBe('manual')

    const active = aurora.activeCompositions()
    expect(active).toHaveLength(1)
    expect(active[0].name).toBe('calm_focus')
    expect(active[0].remainingTurns).toBe(3)
    expect(active[0].magnitudeScale).toBe(1)
  })

  it('refuses suppressive composition without opt-in', () => {
    expect(() =>
      aurora.defineComposition('quiet = gate("calm") - affect("frustrated")'),
    ).toThrow(/suppressive/)
  })

  it('accepts suppressive composition with allowSuppressive: true', () => {
    const rec = aurora.defineComposition(
      'quiet = gate("calm") - affect("frustrated")',
      { allowSuppressive: true },
    )
    expect(rec.suppressive).toBe(true)
  })

  it('throws when invoking unknown composition', () => {
    expect(() => aurora.invokeComposition('does_not_exist')).toThrow(/not found/)
  })

  it('multiple compositions stack in active list', () => {
    aurora.defineComposition('a = gate("x")')
    aurora.defineComposition('b = gate("y")')
    aurora.invokeComposition('a')
    aurora.invokeComposition('b')
    expect(aurora.activeCompositions().map(c => c.name).sort()).toEqual(['a', 'b'])
  })

  it('deactivates a composition before TTL expires', () => {
    aurora.defineComposition('p = gate("x")')
    aurora.invokeComposition('p', { ttlTurns: 100 })
    expect(aurora.deactivateComposition('p')).toBe(true)
    expect(aurora.activeCompositions()).toHaveLength(0)
    expect(aurora.deactivateComposition('p')).toBe(false)
  })

  it('tickCompositions decrements remainingTurns and expires at zero', () => {
    aurora.defineComposition('p = gate("x")')
    aurora.invokeComposition('p', { ttlTurns: 2 })
    expect(aurora.tickCompositions()).toEqual({ active: 1, expired: [] })
    expect(aurora.activeCompositions()[0].remainingTurns).toBe(1)
    expect(aurora.tickCompositions()).toEqual({ active: 0, expired: ['p'] })
    expect(aurora.activeCompositions()).toHaveLength(0)
  })

  it('affect_predicate-triggered compositions are exempt from TTL countdown', () => {
    aurora.defineComposition('p = gate("x")')
    aurora.invokeComposition('p', { ttlTurns: 1, trigger: 'affect_predicate' })
    aurora.tickCompositions()
    aurora.tickCompositions()
    aurora.tickCompositions()
    const active = aurora.activeCompositions()
    expect(active).toHaveLength(1)
    expect(active[0].remainingTurns).toBe(1)
  })

  it('records each invocation in the audit log', () => {
    aurora.defineComposition('p = gate("x")')
    aurora.invokeComposition('p', { sessionId: 's1' })
    aurora.invokeComposition('p', { sessionId: 's2' })
    const log = aurora.getCompositionStore()!.listInvocations({ limit: 10 })
    expect(log.map(l => l.sessionId)).toEqual(['s2', 's1'])
  })

  it('upserts on redefinition (does not duplicate)', () => {
    aurora.defineComposition('p = gate("x")')
    aurora.defineComposition('p = gate("x") + gate("y")')
    const list = aurora.getCompositionStore()!.listCompositions()
    expect(list).toHaveLength(1)
    expect(list[0].dsl).toContain('+ gate("y")')
  })
})
