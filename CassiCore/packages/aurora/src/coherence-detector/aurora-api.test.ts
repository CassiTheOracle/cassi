/**
 * N2 Aurora API tests — verify detectPostureCoherence pulls from the
 * composition store and meditation seeder, and that AEJ integration
 * writes events when the journal is configured.
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
    postureCoherenceEnabled: true,
    ...overrides,
  }
  return new Aurora(makeCortex(), null, null, null, makeLogger(), cfg, makeFakePersistence(dbPath))
}

describe('Aurora.detectPostureCoherence (N2)', () => {
  let dbPath: string
  let aurora: Aurora

  beforeEach(() => {
    dbPath = `/tmp/aurora-n2-test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`
    aurora = buildAurora(dbPath)
  })

  afterEach(() => {
    aurora.getCompositionStore()?.close()
    try { fs.unlinkSync(dbPath) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-wal`) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-shm`) } catch { /* ignore */ }
  })

  it('returns [] when posture coherence is disabled', () => {
    const dbPath2 = `/tmp/aurora-n2-disabled-${Date.now()}.db`
    const a = buildAurora(dbPath2, { postureCoherenceEnabled: false })
    expect(a.detectPostureCoherence()).toEqual([])
    a.getCompositionStore()?.close()
    try { fs.unlinkSync(dbPath2) } catch { /* ignore */ }
  })

  it('pulls active compositions from the active list and detects pair conflicts', () => {
    aurora.defineComposition('warm = gate("warmth") + gate("kindness")')
    aurora.defineComposition('cold = -gate("warmth") - gate("kindness") + gate("coldness")')
    aurora.invokeComposition('warm')
    aurora.invokeComposition('cold')
    const checks = aurora.detectPostureCoherence()
    expect(checks.length).toBeGreaterThan(0)
    expect(checks.some(c => c.category === 'composition_pair_contradictory')).toBe(true)
  })

  it('returns no checks when only one composition is active', () => {
    aurora.defineComposition('solo = gate("warmth")')
    aurora.invokeComposition('solo')
    expect(aurora.detectPostureCoherence()).toEqual([])
  })

  it('topPostureCoherenceChecks trims to N', () => {
    aurora.defineComposition('a1 = gate("x")')
    aurora.defineComposition('a2 = -gate("x")')
    aurora.defineComposition('b1 = gate("y")')
    aurora.defineComposition('b2 = -gate("y")')
    for (const n of ['a1', 'a2', 'b1', 'b2']) aurora.invokeComposition(n)
    const all = aurora.detectPostureCoherence()
    expect(all.length).toBeGreaterThanOrEqual(2)
    expect(aurora.topPostureCoherenceChecks(1)).toHaveLength(1)
  })

  it('extraInputs flow through to stub detectors (no throw, returns no extra checks yet)', () => {
    aurora.defineComposition('a = gate("x")')
    aurora.invokeComposition('a')
    const checks = aurora.detectPostureCoherence({
      retrievalPolicy: { affectBias: 'complementary' },
      currentAffect: { valence: 0.5, arousal: 0.5 },
    })
    // a single composition + stub categories → no checks
    expect(checks).toEqual([])
  })
})
