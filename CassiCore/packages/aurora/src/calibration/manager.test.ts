/**
 * UCF CalibrationManager integration tests.
 *
 * The manager binds runtime measurement functions to persisted probe sets,
 * compares consecutive runs for drift, and surfaces drift to the event
 * journal when one is configured.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as fs from 'fs'

import { CalibrationManager } from './manager.js'
import { CalibrationStore } from './store.js'
import type { CalibrationProbeSet, MeasurementResult, Probe } from './types.js'

function makeLogger() {
  const log: any = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {} }
  log.child = () => log
  return log
}

interface JournalEvent {
  source: string
  category: string | undefined
  text: string
  tags?: string[]
  metadata?: Record<string, unknown>
}

function makeFakeJournal(): { emit: (e: any) => void; events: JournalEvent[] } {
  const events: JournalEvent[] = []
  return {
    events,
    emit(e: any) { events.push({ source: e.source, category: e.category, text: e.text, tags: e.tags, metadata: e.metadata }) },
  }
}

function probeSet(opts: {
  id: string
  measurement: (probe: Probe) => MeasurementResult
}): CalibrationProbeSet {
  return {
    id: opts.id,
    ownerSpec: 'TEST',
    description: 'synthetic',
    probes: [
      { id: 'p1', input: 'a' },
      { id: 'p2', input: 'b' },
    ],
    measurement: opts.measurement,
    schedule: { frequency: 'manual' },
  }
}

describe('CalibrationManager', () => {
  let dbPath: string
  let store: CalibrationStore
  let mgr: CalibrationManager

  beforeEach(() => {
    dbPath = `/tmp/aurora-ucf-test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`
    store = new CalibrationStore(dbPath, makeLogger())
    mgr = new CalibrationManager({ store, logger: makeLogger() })
  })

  afterEach(() => {
    store.close()
    try { fs.unlinkSync(dbPath) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-wal`) } catch { /* ignore */ }
    try { fs.unlinkSync(`${dbPath}-shm`) } catch { /* ignore */ }
  })

  it('registers and lists probe sets', () => {
    mgr.registerProbeSet(probeSet({ id: 'A', measurement: p => ({ probeId: p.id, values: { x: 1 } }) }))
    expect(mgr.listRegistered().map(s => s.id)).toEqual(['A'])
  })

  it('runs a probe set and stores the result', async () => {
    mgr.registerProbeSet(probeSet({
      id: 'A',
      measurement: p => ({ probeId: p.id, values: { x: p.id === 'p1' ? 1 : 2 } }),
    }))
    const result = await mgr.runCalibration('A', { skipDriftComparison: true })
    expect(result.results).toHaveLength(2)
    expect(result.drift).toBeNull()
    expect(mgr.history('A')).toHaveLength(1)
  })

  it('computes drift between consecutive runs', async () => {
    let run = 0
    mgr.registerProbeSet(probeSet({
      id: 'A',
      measurement: p => ({ probeId: p.id, values: { x: run === 0 ? 0 : 5 } }),
    }))
    await mgr.runCalibration('A', { skipDriftComparison: true }) // baseline
    run = 1
    const second = await mgr.runCalibration('A')
    expect(second.drift).not.toBeNull()
    expect(second.drift!.magnitude).toBeGreaterThan(0)
    expect(second.drift!.recommendation).not.toBe('no_action')
  })

  it('skips drift comparison on the first ever run automatically (no prior result)', async () => {
    mgr.registerProbeSet(probeSet({ id: 'A', measurement: p => ({ probeId: p.id, values: { x: 1 } }) }))
    const r = await mgr.runCalibration('A')
    expect(r.drift).toBeNull()
  })

  it('throws when running an unregistered probe set', async () => {
    await expect(mgr.runCalibration('does_not_exist')).rejects.toThrow(/not registered/)
  })

  it('honors a per-probe-set custom drift metric', async () => {
    let run = 0
    const ps: CalibrationProbeSet = {
      ...probeSet({ id: 'A', measurement: p => ({ probeId: p.id, values: { x: run === 0 ? 0 : 5 } }) }),
      driftMetric: (_prior, current) => ({
        magnitude: 0,
        affected: current.map(c => c.probeId),
        recommendation: 'no_action',
      }),
    }
    mgr.registerProbeSet(ps)
    await mgr.runCalibration('A', { skipDriftComparison: true })
    run = 1
    const r = await mgr.runCalibration('A')
    expect(r.drift?.magnitude).toBe(0)
    expect(r.drift?.affected).toEqual(['p1', 'p2'])
  })

  it('emits a drift event to the journal when magnitude is non-trivial', async () => {
    const journal = makeFakeJournal()
    const mgrWithJournal = new CalibrationManager({ store, logger: makeLogger(), eventJournal: journal as any })
    let run = 0
    mgrWithJournal.registerProbeSet(probeSet({
      id: 'A',
      measurement: p => ({ probeId: p.id, values: { x: run === 0 ? 0 : 10 } }),
    }))
    await mgrWithJournal.runCalibration('A', { skipDriftComparison: true })
    run = 1
    await mgrWithJournal.runCalibration('A')
    expect(journal.events).toHaveLength(1)
    expect(journal.events[0].source).toBe('UCF')
    expect(journal.events[0].category).toBe('calibration_drift')
    expect(journal.events[0].tags).toContain('drift')
  })

  it('does not emit drift events when no_action', async () => {
    const journal = makeFakeJournal()
    const mgrWithJournal = new CalibrationManager({ store, logger: makeLogger(), eventJournal: journal as any })
    mgrWithJournal.registerProbeSet(probeSet({
      id: 'A',
      measurement: p => ({ probeId: p.id, values: { x: 1 } }),
    }))
    await mgrWithJournal.runCalibration('A', { skipDriftComparison: true })
    await mgrWithJournal.runCalibration('A')
    expect(journal.events).toHaveLength(0)
  })

  it('surveillDrift inspects stored history without re-running measurements', async () => {
    let run = 0
    mgr.registerProbeSet(probeSet({
      id: 'A',
      measurement: p => ({ probeId: p.id, values: { x: run === 0 ? 0 : 5 } }),
    }))
    expect(mgr.surveillDrift('A')).toBeNull()
    await mgr.runCalibration('A', { skipDriftComparison: true })
    expect(mgr.surveillDrift('A')).toBeNull() // still only one run
    run = 1
    await mgr.runCalibration('A')
    const drift = mgr.surveillDrift('A')
    expect(drift).not.toBeNull()
    expect(drift!.magnitude).toBeGreaterThan(0)
  })

  it('runScheduled skips manual-only probe sets', async () => {
    mgr.registerProbeSet(probeSet({ id: 'manual', measurement: p => ({ probeId: p.id, values: { x: 1 } }) }))
    const ranked: CalibrationProbeSet = {
      ...probeSet({ id: 'startup-driven', measurement: p => ({ probeId: p.id, values: { x: 1 } }) }),
      schedule: { frequency: 'manual', triggeredBy: 'startup' },
    }
    mgr.registerProbeSet(ranked)
    const results = await mgr.runScheduled()
    expect(results.map(r => r.probeSetId)).toEqual(['startup-driven'])
  })

  it('unregister removes from registry and store', async () => {
    mgr.registerProbeSet(probeSet({ id: 'A', measurement: p => ({ probeId: p.id, values: { x: 1 } }) }))
    expect(mgr.unregisterProbeSet('A')).toBe(true)
    expect(mgr.listRegistered()).toHaveLength(0)
    await expect(mgr.runCalibration('A')).rejects.toThrow(/not registered/)
  })

  it('persists probe sets across manager instances', async () => {
    mgr.registerProbeSet(probeSet({ id: 'A', measurement: p => ({ probeId: p.id, values: { x: 1 } }) }))
    await mgr.runCalibration('A', { skipDriftComparison: true })
    const mgr2 = new CalibrationManager({ store, logger: makeLogger() })
    // History is in the store; manager2 can read it without re-registering
    expect(mgr2.history('A')).toHaveLength(1)
  })
})
