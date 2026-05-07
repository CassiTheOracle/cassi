/**
 * MeditationSeeder tests — C1.2 directed meditation seeding.
 */

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { describe, it, expect, beforeEach, afterEach, afterAll } from 'vitest'

import type { ILogger } from '../../../types/interfaces.js'
import { GapDetector, type GapCandidate } from './gap-detector.js'
import { MeditationSeeder } from './meditation-seeder.js'


const TMP_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'meditation-seeder-test-'))

function makeLogger(): ILogger {
  return {
    info: () => {},
    warn: () => {},
    error: () => {},
    debug: () => {},
    child: () => makeLogger(),
  } as unknown as ILogger
}

function makeGap(overrides: Partial<GapCandidate> = {}): GapCandidate {
  return {
    id: 'gap_test_1',
    category: 'underconnected',
    scope: {
      nodeIds: ['node_a', 'node_b', 'node_c'],
      affectedModules: ['brain/cortex'],
    },
    signals: [
      { type: 'low_edge_density', strength: 0.6, provenance: 'detector' },
    ],
    priority: 0.7,
    status: 'pending',
    observedSince: new Date().toISOString(),
    lastObserved: new Date().toISOString(),
    detectionCount: 3,
    metadata: {},
    ...overrides,
  }
}


describe('MeditationSeeder', () => {
  let dbPath: string
  let seeder: MeditationSeeder
  const logger = makeLogger()

  beforeEach(() => {
    dbPath = path.join(TMP_DIR, `test-seeds-${Date.now()}.db`)
    seeder = new MeditationSeeder(dbPath, logger)
  })

  afterEach(() => {
    seeder.close()
  })

  afterAll(() => {
    fs.rmSync(TMP_DIR, { recursive: true, force: true })
  })


  describe('initialization', () => {
    it('creates database and schema on first run', () => {
      expect(fs.existsSync(dbPath)).toBe(true)
      const pending = seeder.getPendingSeeds()
      expect(pending).toEqual([])
    })

    it('idempotent schema creation on repeated init', () => {
      seeder.close()
      const seeder2 = new MeditationSeeder(dbPath, logger)
      expect(seeder2.getPendingSeeds()).toEqual([])
      seeder2.close()
    })
  })


  describe('seedFromGaps', () => {
    it('creates seeds from gap candidates', () => {
      const gap = makeGap()
      const result = seeder.seedFromGaps([gap])

      expect(result.seeds).toHaveLength(1)
      expect(result.seeds[0].gapId).toBe('gap_test_1')
      expect(result.seeds[0].entryPoints).toEqual(['node_a', 'node_b', 'node_c'])
      expect(result.seeds[0].proposedBy).toBe('curator')
      expect(result.seeds[0].budget.maxTurns).toBeGreaterThan(0)
      expect(result.seeds[0].budget.maxCostUsd).toBeGreaterThan(0)
    })

    it('skips gaps that already have active seeds', () => {
      const gap = makeGap()
      const first = seeder.seedFromGaps([gap])
      expect(first.seeds).toHaveLength(1)

      const second = seeder.seedFromGaps([gap])
      expect(second.seeds).toHaveLength(0)
      expect(second.skipped).toHaveLength(1)
      expect(second.skipped[0].reason).toBe('already has active seed')
    })

    it('respects the pending seed budget', () => {
      const budgetSeeder = new MeditationSeeder(
        path.join(TMP_DIR, `budget-${Date.now()}.db`),
        logger,
        { maxPendingSeeds: 3 },
      )
      const gaps = Array.from({ length: 10 }, (_, i) =>
        makeGap({ id: `gap_budget_${i}`, scope: { nodeIds: [`n${i}`] } }),
      )

      const result = budgetSeeder.seedFromGaps(gaps)
      expect(result.seeds).toHaveLength(3)
      expect(result.skipped.length).toBeGreaterThanOrEqual(7)
      budgetSeeder.close()
    })

    it('sorts gaps by priority (highest first)', () => {
      const budgetSeeder = new MeditationSeeder(
        path.join(TMP_DIR, `sort-${Date.now()}.db`),
        logger,
        { maxPendingSeeds: 2 },
      )
      const gaps = [
        makeGap({ id: 'gap_low', priority: 0.3, scope: { nodeIds: ['low_a'] } }),
        makeGap({ id: 'gap_high', priority: 0.9, scope: { nodeIds: ['high_a'] } }),
        makeGap({ id: 'gap_mid', priority: 0.6, scope: { nodeIds: ['mid_a'] } }),
      ]

      const result = budgetSeeder.seedFromGaps(gaps)
      expect(result.seeds).toHaveLength(2)
      expect(result.seeds[0].gapId).toBe('gap_high')
      expect(result.seeds[1].gapId).toBe('gap_mid')
      budgetSeeder.close()
    })

    it('enforces cooldown for recently-seeded gaps', () => {
      const gap = makeGap()
      seeder.seedFromGaps([gap])

      // Mark the seed as expired so it's no longer active
      const seeds = seeder.getPendingSeeds()
      seeder.markExpired(seeds[0].id)

      // Try seeding again immediately — should hit cooldown
      const result = seeder.seedFromGaps([gap])
      expect(result.seeds).toHaveLength(0)
      expect(result.skipped[0]?.reason).toContain('cooldown')
    })

    it('produces category-appropriate topic templates', () => {
      for (const category of ['underconnected', 'fragmented', 'missing_focus', 'isolated_nucleus'] as const) {
        const gap = makeGap({
          id: `gap_${category}_0`,
          category,
          scope: { nodeIds: ['x', 'y'] },
        })
        const result = seeder.seedFromGaps([gap])
        expect(result.seeds).toHaveLength(1)
        expect(result.seeds[0].expectedRefinement).toBeTruthy()
      }
    })
  })


  describe('status transitions', () => {
    it('marks seeds through the lifecycle', () => {
      const gap = makeGap()
      seeder.seedFromGaps([gap])
      const [seed] = seeder.getPendingSeeds()

      seeder.markScheduled(seed.id)
      seeder.markRunning(seed.id)
      seeder.markResolved(seed.id, 'Added 3 new connections')

      // No longer pending
      expect(seeder.getPendingSeeds()).toHaveLength(0)
    })

    it('marks seeds as abandoned', () => {
      const gap = makeGap()
      seeder.seedFromGaps([gap])
      const [seed] = seeder.getPendingSeeds()

      seeder.markAbandoned(seed.id)
      expect(seeder.getPendingSeeds()).toHaveLength(0)
    })

    it('C1.4 — markLeftOpen moves seed out of pending and stores rationale', () => {
      const gap = makeGap()
      seeder.seedFromGaps([gap])
      const [seed] = seeder.getPendingSeeds()

      seeder.markLeftOpen(seed.id, 'Productive uncertainty — keep exploring without resolving')
      expect(seeder.getPendingSeeds()).toHaveLength(0)
    })

    it('C1.4 — getOpenQuestions returns only left_open seeds with their rationale', () => {
      const gap1 = makeGap({ id: 'gap-1' })
      const gap2 = makeGap({ id: 'gap-2' })
      seeder.seedFromGaps([gap1, gap2])
      const seeds = seeder.getPendingSeeds()

      seeder.markLeftOpen(seeds[0].id, 'rationale-A')
      seeder.markAbandoned(seeds[1].id)

      const open = seeder.getOpenQuestions()
      expect(open).toHaveLength(1)
      expect(open[0].id).toBe(seeds[0].id)
      expect(open[0].rationale).toBe('rationale-A')
    })

    it('C1.4 — getOpenQuestions returns empty list when none left_open', () => {
      const gap = makeGap()
      seeder.seedFromGaps([gap])
      expect(seeder.getOpenQuestions()).toHaveLength(0)
    })
  })


  describe('database sharing with GapDetector', () => {
    it('seeder and detector can coexist with separate DBs', () => {
      const gapDbPath = path.join(TMP_DIR, `gap-${Date.now()}.db`)
      const seedDbPath = path.join(TMP_DIR, `seed-${Date.now()}.db`)

      const detector = new GapDetector(gapDbPath, logger)
      const seedDb = new MeditationSeeder(seedDbPath, logger)

      const gap = makeGap()
      detector.persistGaps([gap])

      const result = seedDb.seedFromGaps([gap])
      expect(result.seeds).toHaveLength(1)

      detector.close()
      seedDb.close()
    })
  })
})
