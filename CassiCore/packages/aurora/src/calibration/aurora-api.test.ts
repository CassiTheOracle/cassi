/**
 * UCF Aurora API tests — verify the four public methods and AEJ side-effects.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'

import { Aurora } from '../index.js'
import type { AuroraConfig } from '../types.js'
import { AURORA_DEFAULTS } from '../types.js'
import type { CalibrationProbeSet } from './types.js'

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
    compositionEnabled: false,
    postureCoherenceEnabled: false,
    calibrationEnabled: true,
    ...overrides,
  }
  return new Aurora(makeCortex(), null, null, null, makeLogger(), cfg, makeFakePersistence(dbPath))
}

function syntheticProbeSet(id: string, run: { current: number }): CalibrationProbeSet {
  return {
    id,
    ownerSpec: 'TEST',
    description: 'synthetic for Aurora API test',
    probes: [
      { id: 'p1', input: 'a' },
      { id: 'p2', input: 'b' },
    ],
    measurement: probe => ({
      probeId: probe.id,
      values: { x: run.current },
    }),
    schedule: { frequency: 'manual' },
  }
}

describe('Aurora calibration API (UCF)', () => {
  let dbPath: string
  let aurora: Aurora

  beforeEach(() => {
    dbPath = `/tmp/aurora-ucf-api-${Date.now()}-${Math.random().toString(36).slice(2)}.db`
    aurora = buildAurora(dbPath)
  })

  afterEach(() => {
    aurora.getCalibrationManager()?.['store']?.close?.()
    try { fs.unlinkSync(dbPath) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-wal`) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-shm`) } catch { /* ignore */ }
  })

  it('throws when calibrationEnabled is false', () => {
    const dbPath2 = `/tmp/aurora-ucf-disabled-${Date.now()}.db`
    const a = buildAurora(dbPath2, { calibrationEnabled: false })
    expect(() => a.registerCalibrationProbeSet(syntheticProbeSet('A', { current: 0 }))).toThrow(/calibrationManager disabled/)
    try { fs.unlinkSync(dbPath2) } catch { /* ignore */ }
  })

  it('register, run, history end-to-end', async () => {
    const run = { current: 0 }
    aurora.registerCalibrationProbeSet(syntheticProbeSet('A', run))
    const baseline = await aurora.runCalibration('A', { skipDriftComparison: true })
    expect(baseline.drift).toBeNull()
    run.current = 5
    const second = await aurora.runCalibration('A')
    expect(second.drift).not.toBeNull()
    expect(second.drift!.magnitude).toBeGreaterThan(0)
    expect(aurora.calibrationHistory('A')).toHaveLength(2)
  })

  it('surveillCalibrationDrift returns null when fewer than 2 runs', async () => {
    const run = { current: 0 }
    aurora.registerCalibrationProbeSet(syntheticProbeSet('A', run))
    expect(aurora.surveillCalibrationDrift('A')).toBeNull()
    await aurora.runCalibration('A', { skipDriftComparison: true })
    expect(aurora.surveillCalibrationDrift('A')).toBeNull()
    run.current = 5
    await aurora.runCalibration('A')
    expect(aurora.surveillCalibrationDrift('A')).not.toBeNull()
  })

  it('runScheduledCalibrations returns [] when no probe sets are auto-scheduled', async () => {
    const run = { current: 0 }
    aurora.registerCalibrationProbeSet(syntheticProbeSet('A', run)) // manual
    const results = await aurora.runScheduledCalibrations()
    expect(results).toEqual([])
  })

  it('emits AEJ event on drift when journal is enabled', async () => {
    // Build with the journal turned on so Aurora wires it into the manager.
    const dbPath2 = `/tmp/aurora-ucf-journal-${Date.now()}.db`
    const aJ = buildAurora(dbPath2, { eventJournalEnabled: true })
    const run = { current: 0 }
    aJ.registerCalibrationProbeSet(syntheticProbeSet('A', run))
    await aJ.runCalibration('A', { skipDriftComparison: true })
    run.current = 10
    await aJ.runCalibration('A')
    const events = aJ.getEventJournal()!.query({ sources: ['UCF'], limit: 10 })
    expect(events.length).toBeGreaterThan(0)
    expect(events[0].category).toBe('calibration_drift')
    aJ.getCalibrationManager()?.['store']?.close?.()
    try { fs.unlinkSync(dbPath2) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath2}-wal`) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath2}-shm`) } catch { /* ignore */ }
  })
})
