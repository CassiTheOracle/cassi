/**
 * AutoScheduler tests — C1.3 auto-scheduling within budget.
 */

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import Database from 'better-sqlite3'
import { describe, it, expect, beforeEach, afterEach } from 'vitest'

import type { ILogger } from '../../../types/interfaces.js'
import type { GapCategory, GapCandidate, GapStatus } from './gap-detector.js'
import type { MeditationSeed } from './meditation-seeder.js'
import { AutoScheduler } from './auto-scheduler.js'


const TMP_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'auto-scheduler-test-'))

function makeLogger(): ILogger {
  return {
    info: () => {},
    warn: () => {},
    error: () => {},
    debug: () => {},
    child: () => makeLogger(),
  } as unknown as ILogger
}

function makeSeed(overrides: Partial<MeditationSeed> = {}): MeditationSeed {
  return {
    id: 'seed_test_1',
    gapId: 'gap_test_1',
    topic: 'Explore connections between related but poorly linked concepts',
    entryPoints: ['node_a', 'node_b'],
    expectedRefinement: 'At least 2 new edges',
    budget: { maxTurns: 15, maxCostUsd: 0.25 },
    proposedAt: new Date().toISOString(),
    proposedBy: 'curator',
    metadata: {},
    ...overrides,
  }
}

function makeGapMeta(
  category: GapCategory = 'underconnected',
  priority = 0.5,
  status: GapStatus = 'pending',
): { category: GapCategory; priority: number; status: GapStatus } {
  return { category, priority, status }
}

function makeScheduler(overrides: Record<string, unknown> = {}): AutoScheduler {
  const dbPath = path.join(TMP_DIR, `test-${Date.now()}-${Math.random().toString(36).slice(2)}.db`)
  return new AutoScheduler(dbPath, {
    enabled: true,
    maxDailyAutoScheduled: 6,
    totalDailyCostCapUsd: 1.0,
    maxConcurrentDirected: 1,
    maxRetriesPerGap: 3,
    cooldownHours: 24,
    categoryCaps: { underconnected: 2, fragmented: 2, missing_focus: 2, isolated_nucleus: 2 },
    highRiskPriorityThreshold: 0.8,
    anxiousLoopFraction: 0.6,
    anxiousLoopWindow: 10,
    ...overrides,
  }, makeLogger())
}


describe('AutoScheduler', () => {
  let scheduler: AutoScheduler

  beforeEach(() => {
    scheduler = makeScheduler()
  })

  afterEach(() => {
    scheduler.close()
  })


  describe('basic scheduling', () => {
    it('auto-schedules a seed that passes all checks', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta('underconnected', 0.5)]])

      const results = scheduler.evaluate([seed], gapMeta, 100, 5)

      expect(results).toHaveLength(1)
      expect(results[0].decision).toBe('auto_schedule')
      expect(results[0].flags).toHaveLength(0)
      expect(results[0].scheduledAt).toBeTruthy()
    })

    it('defers all seeds when auto-scheduling is disabled', () => {
      const disabled = makeScheduler({ enabled: false })
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta()]])

      const results = disabled.evaluate([seed], gapMeta, 100, 5)

      expect(results).toHaveLength(1)
      expect(results[0].decision).toBe('defer')
      expect(results[0].reason).toContain('disabled')
      disabled.close()
    })

    it('defers seeds with no gap metadata', () => {
      const seed = makeSeed()
      const emptyMeta = new Map()

      const results = scheduler.evaluate([seed], emptyMeta, 100, 5)

      expect(results).toHaveLength(1)
      expect(results[0].decision).toBe('defer')
      expect(results[0].reason).toContain('No gap metadata')
    })

    it('defers seeds for already-resolved gaps', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta('underconnected', 0.5, 'resolved')]])

      const results = scheduler.evaluate([seed], gapMeta, 100, 5)

      expect(results).toHaveLength(1)
      expect(results[0].decision).toBe('defer')
    })

    it('defers seeds for leave_open gaps', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta('underconnected', 0.5, 'leave_open')]])

      const results = scheduler.evaluate([seed], gapMeta, 100, 5)

      expect(results[0].decision).toBe('defer')
    })

    it('defers seeds for unresolvable gaps', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta('underconnected', 0.5, 'unresolvable')]])

      const results = scheduler.evaluate([seed], gapMeta, 100, 5)

      expect(results[0].decision).toBe('defer')
    })

    it('sorts seeds by gap priority (highest first)', () => {
      const low = makeSeed({ id: 'seed_low', gapId: 'gap_low' })
      const high = makeSeed({ id: 'seed_high', gapId: 'gap_high' })
      const gapMeta = new Map([
        ['gap_low', makeGapMeta('underconnected', 0.3)],
        ['gap_high', makeGapMeta('underconnected', 0.6)],
      ])

      const results = scheduler.evaluate([low, high], gapMeta, 100, 5)

      expect(results[0].seedId).toBe('seed_high')
      expect(results[1].seedId).toBe('seed_low')
    })
  })


  describe('daily budget cap', () => {
    it('stops auto-scheduling when daily cap is reached', () => {
      const seeds: MeditationSeed[] = []
      const gapMeta = new Map<string, ReturnType<typeof makeGapMeta>>()

      // Create more seeds than the daily cap
      for (let i = 0; i < 8; i++) {
        const id = `seed_${i}`
        const gapId = `gap_${i}`
        // Spread across categories to avoid per-category cap
        const categories: GapCategory[] = ['underconnected', 'fragmented', 'missing_focus', 'isolated_nucleus']
        seeds.push(makeSeed({ id, gapId, budget: { maxTurns: 10, maxCostUsd: 0.10 } }))
        gapMeta.set(gapId, makeGapMeta(categories[i % 4], 0.3))
      }

      const results = scheduler.evaluate(seeds, gapMeta, 100, 5)

      const autoScheduled = results.filter(r => r.decision === 'auto_schedule')
      const deferred = results.filter(r => r.decision === 'defer' && r.flags.includes('daily_cap_reached'))

      // maxDailyAutoScheduled is 6
      expect(autoScheduled).toHaveLength(6)
      expect(deferred.length).toBeGreaterThanOrEqual(1)
      expect(deferred[0].reason).toContain('Daily auto-schedule cap')
    })

    it('stops auto-scheduling when cost cap would be exceeded', () => {
      const tightBudget = makeScheduler({ totalDailyCostCapUsd: 0.30 })
      const seeds: MeditationSeed[] = []
      const gapMeta = new Map<string, ReturnType<typeof makeGapMeta>>()

      // Each seed costs $0.25, so only 1 fits in $0.30
      for (let i = 0; i < 3; i++) {
        const gapId = `gap_cost_${i}`
        seeds.push(makeSeed({ id: `seed_cost_${i}`, gapId, budget: { maxTurns: 10, maxCostUsd: 0.25 } }))
        gapMeta.set(gapId, makeGapMeta('underconnected', 0.3))
      }

      const results = tightBudget.evaluate(seeds, gapMeta, 100, 5)

      const autoScheduled = results.filter(r => r.decision === 'auto_schedule')
      const budgetExhausted = results.filter(r => r.flags.includes('budget_exhausted'))

      expect(autoScheduled).toHaveLength(1)
      expect(budgetExhausted).toHaveLength(2)
      tightBudget.close()
    })
  })


  describe('per-category caps', () => {
    it('respects per-category daily caps', () => {
      const seeds: MeditationSeed[] = []
      const gapMeta = new Map<string, ReturnType<typeof makeGapMeta>>()

      // All same category, cap is 2
      for (let i = 0; i < 4; i++) {
        const gapId = `gap_cat_${i}`
        seeds.push(makeSeed({ id: `seed_cat_${i}`, gapId, budget: { maxTurns: 10, maxCostUsd: 0.10 } }))
        gapMeta.set(gapId, makeGapMeta('underconnected', 0.3))
      }

      const results = scheduler.evaluate(seeds, gapMeta, 100, 5)

      const autoScheduled = results.filter(r => r.decision === 'auto_schedule')
      const categoryCapped = results.filter(r => r.flags.includes('category_cap_reached'))

      expect(autoScheduled).toHaveLength(2)
      expect(categoryCapped).toHaveLength(2)
    })
  })


  describe('retry and cooldown', () => {
    it('tracks retry counts per gap', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta()]])

      // First evaluation should succeed
      let results = scheduler.evaluate([seed], gapMeta, 100, 5)
      expect(results[0].decision).toBe('auto_schedule')

      // Check retry state
      const state = scheduler.getGapRetryState(seed.gapId)
      expect(state.retryCount).toBe(1)
    })

    it('defers when cooldown is active', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta()]])

      // Schedule once to set retry count and last_attempt_at
      scheduler.evaluate([seed], gapMeta, 100, 5)

      // Second evaluation should hit cooldown (24h default)
      const results = scheduler.evaluate([seed], gapMeta, 100, 5)
      expect(results[0].decision).toBe('defer')
      expect(results[0].flags).toContain('cooldown_active')
    })

    it('marks gap as unresolvable after max retries', () => {
      // Use a scheduler with no cooldown and high category cap so retries are immediate
      const noCooldown = makeScheduler({
        maxRetriesPerGap: 2,
        cooldownHours: 0,
        categoryCaps: { underconnected: 10, fragmented: 10, missing_focus: 10, isolated_nucleus: 10 },
        maxDailyAutoScheduled: 10,
        totalDailyCostCapUsd: 10,
      })

      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta()]])

      // First two should succeed
      noCooldown.evaluate([seed], gapMeta, 100, 5)
      noCooldown.evaluate([seed], gapMeta, 100, 5)

      // Third should hit max retries
      const results = noCooldown.evaluate([seed], gapMeta, 100, 5)
      expect(results[0].decision).toBe('defer')
      expect(results[0].flags).toContain('max_retries_reached')

      // Gap should now be marked unresolvable
      const state = noCooldown.getGapRetryState(seed.gapId)
      expect(state.unresolvable).toBe(true)

      // Further attempts should be deferred immediately
      const after = noCooldown.evaluate([seed], gapMeta, 100, 5)
      expect(after[0].decision).toBe('defer')
      expect(after[0].flags).toContain('max_retries_reached')
      expect(after[0].reason).toContain('unresolvable')

      noCooldown.close()
    })
  })


  describe('risk assessment', () => {
    it('flags high-priority gaps for human review', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta('underconnected', 0.9)]])

      const results = scheduler.evaluate([seed], gapMeta, 100, 5)

      expect(results[0].decision).toBe('flag_for_review')
      expect(results[0].flags).toContain('high_risk')
      expect(results[0].reason).toContain('High-priority')
    })

    it('auto-schedules gaps just below the threshold', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta('underconnected', 0.79)]])

      const results = scheduler.evaluate([seed], gapMeta, 100, 5)

      expect(results[0].decision).toBe('auto_schedule')
    })

    it('flags for review even when budget is available', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta('fragmented', 0.95)]])

      const results = scheduler.evaluate([seed], gapMeta, 100, 5)

      expect(results[0].decision).toBe('flag_for_review')
      expect(results[0].scheduledAt).toBeNull()
    })
  })


  describe('anxious-loop guard (C1.W5)', () => {
    it('triggers when directed fraction exceeds threshold', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta()]])

      // 7 out of 10 meditations are directed = 0.7 > 0.6 threshold
      const results = scheduler.evaluate([seed], gapMeta, 10, 7)

      expect(results[0].decision).toBe('defer')
      expect(results[0].flags).toContain('anxious_loop')
    })

    it('does not trigger when directed fraction is below threshold', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta()]])

      // 5 out of 10 = 0.5 < 0.6
      const results = scheduler.evaluate([seed], gapMeta, 10, 5)

      expect(results[0].decision).toBe('auto_schedule')
    })

    it('does not trigger when not enough data (window)', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta()]])

      // Only 5 meditations total, below window of 10
      const results = scheduler.evaluate([seed], gapMeta, 5, 5)

      // All 5 are directed, but not enough data — should still schedule
      expect(results[0].decision).toBe('auto_schedule')
    })

    it('defers all seeds when anxious-loop is active', () => {
      const seeds = [makeSeed({ id: 's1', gapId: 'g1' }), makeSeed({ id: 's2', gapId: 'g2' })]
      const gapMeta = new Map([
        ['g1', makeGapMeta('underconnected', 0.3)],
        ['g2', makeGapMeta('fragmented', 0.4)],
      ])

      const results = scheduler.evaluate(seeds, gapMeta, 10, 7)

      expect(results.every(r => r.decision === 'defer')).toBe(true)
      expect(results.every(r => r.flags.includes('anxious_loop'))).toBe(true)
    })

    it('exposes anxious-loop state via isAnxiousLoop', () => {
      expect(scheduler.isAnxiousLoop(10, 5)).toBe(false)
      expect(scheduler.isAnxiousLoop(10, 7)).toBe(true)
      expect(scheduler.isAnxiousLoop(5, 5)).toBe(false) // below window
    })
  })


  describe('runaway prevention', () => {
    it('a pile of pending gaps does NOT cause runaway scheduling', () => {
      const seeds: MeditationSeed[] = []
      const gapMeta = new Map<string, ReturnType<typeof makeGapMeta>>()

      // 50 pending gaps
      for (let i = 0; i < 50; i++) {
        const gapId = `gap_pile_${i}`
        const categories: GapCategory[] = ['underconnected', 'fragmented', 'missing_focus', 'isolated_nucleus']
        seeds.push(makeSeed({ id: `seed_pile_${i}`, gapId, budget: { maxTurns: 10, maxCostUsd: 0.10 } }))
        gapMeta.set(gapId, makeGapMeta(categories[i % 4], 0.3))
      }

      const results = scheduler.evaluate(seeds, gapMeta, 100, 5)

      const autoScheduled = results.filter(r => r.decision === 'auto_schedule')
      const deferred = results.filter(r => r.decision === 'defer')

      // Should be capped by daily budget (6) + category caps
      expect(autoScheduled.length).toBeLessThanOrEqual(6)
      expect(deferred.length).toBeGreaterThan(40)
    })
  })


  describe('status and reset', () => {
    it('returns correct status', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta()]])

      scheduler.evaluate([seed], gapMeta, 100, 5)

      const status = scheduler.getStatus(100, 5)
      expect(status.enabled).toBe(true)
      expect(status.dailyBudget.autoScheduled).toBe(1)
      expect(status.dailyBudget.costUsd).toBe(0.25)
    })

    it('resets daily budget', () => {
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta()]])

      scheduler.evaluate([seed], gapMeta, 100, 5)
      scheduler.resetDailyBudget()

      const status = scheduler.getStatus(100, 5)
      expect(status.dailyBudget.autoScheduled).toBe(0)
      expect(status.dailyBudget.costUsd).toBe(0)
    })
  })


  describe('database sharing', () => {
    it('works with an externally provided database', () => {
      const dbPath = path.join(TMP_DIR, `shared-${Date.now()}.db`)
      const db = new Database(dbPath)

      const s1 = new AutoScheduler(db, { enabled: true }, makeLogger())
      const seed = makeSeed()
      const gapMeta = new Map([[seed.gapId, makeGapMeta()]])

      const results = s1.evaluate([seed], gapMeta, 100, 5)
      expect(results[0].decision).toBe('auto_schedule')

      s1.close()
      db.close()
    })
  })
})
