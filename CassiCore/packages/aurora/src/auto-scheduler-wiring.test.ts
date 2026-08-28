/**
 * Tests for C1.3 AutoScheduler end-to-end wiring.
 *
 * Verifies that Aurora.evaluateAutoScheduling() and
 * Aurora.collectAutoScheduledTopics() coordinate GapDetector,
 * MeditationSeeder, and AutoScheduler correctly.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import * as fs from 'fs'

import { Aurora } from './index.js'
import type { AuroraConfig } from './types.js'
import { AURORA_DEFAULTS } from './types.js'
import type { SchedulingResult } from './auto-scheduler.js'

function makeLogger() {
  const log: any = {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
  }
  log.child = () => log
  return log
}

function makeCortex(): any {
  return {
    list: () => [],
    retrieve: async () => [],
    getAffectState: () => undefined,
  }
}

function buildAurora(dbPath: string, overrides?: Partial<AuroraConfig>): Aurora {
  const cfg: Partial<AuroraConfig> = {
    ...AURORA_DEFAULTS,
    gapDetectionEnabled: true,
    meditationSeederEnabled: true,
    autoSchedulerEnabled: true,
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
    ...overrides,
  }
  // Stash dbPath via persistence-less construction by writing to a fixed temp path.
  // Aurora derives auroraDbPath from persistence?.getDbPath() ?? getDataDir(); we
  // override to a per-test dir by writing the env var equivalent at construction.
  // Simpler: rely on the system data dir but each test uses a unique suffix in the
  // submodule constructors. We pass dbPath through the persistence shim:
  const fakePersistence: any = {
    getDbPath: () => dbPath,
    beginSession: () => ({ sessionId: 'aur_sess_test', inheritsFrom: null, createdAt: Date.now() }),
    hydrateClaustrum: () => ({ nodes: [], edges: [] }),
    hydrateReasoningLog: () => [],
    hydrateMomentum: () => null,
  }
  return new Aurora(makeCortex(), null, null, null, makeLogger(), cfg, fakePersistence)
}

describe('Aurora.evaluateAutoScheduling', () => {
  let tempDbPath: string

  beforeEach(() => {
    tempDbPath = `/tmp/aurora-wiring-test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`
  })

  it('returns empty when modules disabled', () => {
    const aurora = buildAurora(tempDbPath, {
      gapDetectionEnabled: false,
      meditationSeederEnabled: false,
      autoSchedulerEnabled: false,
    })
    expect(aurora.evaluateAutoScheduling(100, 20)).toEqual([])
  })

  it('returns empty when no pending seeds', () => {
    const aurora = buildAurora(tempDbPath)
    expect(aurora.evaluateAutoScheduling(100, 20)).toEqual([])
  })

  it('does not throw on extreme meditation counts', () => {
    const aurora = buildAurora(tempDbPath)
    expect(() => aurora.evaluateAutoScheduling(0, 0)).not.toThrow()
    expect(() => aurora.evaluateAutoScheduling(1000, 500)).not.toThrow()
  })

  it('returns array shape regardless of seed state', () => {
    const aurora = buildAurora(tempDbPath)
    const results = aurora.evaluateAutoScheduling(100, 20)
    expect(Array.isArray(results)).toBe(true)
  })
})

describe('Aurora.collectAutoScheduledTopics', () => {
  let tempDbPath: string

  beforeEach(() => {
    tempDbPath = `/tmp/aurora-collect-topics-test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`
  })

  it('returns empty when meditation modules disabled', () => {
    const aurora = buildAurora(tempDbPath, {
      gapDetectionEnabled: false,
      meditationSeederEnabled: false,
      autoSchedulerEnabled: false,
    })
    expect(aurora.collectAutoScheduledTopics(100, 20)).toEqual([])
  })

  it('returns empty when no pending seeds', () => {
    const aurora = buildAurora(tempDbPath)
    expect(aurora.collectAutoScheduledTopics(100, 20)).toEqual([])
  })

  it('snapshots seed topics before evaluateAutoScheduling marks them scheduled', () => {
    const aurora = buildAurora(tempDbPath)

    const seeder = (aurora as any).meditationSeeder as { getPendingSeeds: () => any[] }
    expect(seeder).toBeDefined()

    const fakeSeeds = [
      { id: 'seed-A', topic: 'topic A', gapId: 'g1' },
      { id: 'seed-B', topic: 'topic B', gapId: 'g2' },
      { id: 'seed-C', topic: 'topic C', gapId: 'g3' },
    ]
    vi.spyOn(seeder, 'getPendingSeeds').mockReturnValue(fakeSeeds as any)
    vi.spyOn(aurora, 'evaluateAutoScheduling').mockReturnValue([
      { decision: 'auto_schedule', seedId: 'seed-A', gapId: 'g1', flags: [], reason: '', scheduledAt: null },
      { decision: 'flag_for_review', seedId: 'seed-B', gapId: 'g2', flags: [], reason: '', scheduledAt: null },
      { decision: 'auto_schedule', seedId: 'seed-C', gapId: 'g3', flags: [], reason: '', scheduledAt: null },
    ] as SchedulingResult[])

    const topics = aurora.collectAutoScheduledTopics(100, 20)
    expect(topics).toEqual(['topic A', 'topic C'])
  })

  it('skips topics for unknown seedIds (defensive)', () => {
    const aurora = buildAurora(tempDbPath)

    const seeder = (aurora as any).meditationSeeder as { getPendingSeeds: () => any[] }
    vi.spyOn(seeder, 'getPendingSeeds').mockReturnValue([
      { id: 'seed-A', topic: 'topic A', gapId: 'g1' },
    ] as any)
    vi.spyOn(aurora, 'evaluateAutoScheduling').mockReturnValue([
      { decision: 'auto_schedule', seedId: 'seed-A', gapId: 'g1', flags: [], reason: '', scheduledAt: null },
      { decision: 'auto_schedule', seedId: 'seed-MISSING', gapId: 'g99', flags: [], reason: '', scheduledAt: null },
    ] as SchedulingResult[])

    expect(aurora.collectAutoScheduledTopics(100, 20)).toEqual(['topic A'])
  })
})

afterAllCleanup()

function afterAllCleanup() {
  // Best-effort temp file cleanup so /tmp doesn't accumulate test DBs.
  // Each test uses a unique name; a sweep at module load is sufficient.
  try {
    const dir = '/tmp'
    for (const f of fs.readdirSync(dir)) {
      if (f.startsWith('aurora-wiring-test-') || f.startsWith('aurora-collect-topics-test-')) {
        try { fs.unlinkSync(`${dir}/${f}`) } catch { /* ignore */ }
      }
    }
  } catch { /* ignore */ }
}
