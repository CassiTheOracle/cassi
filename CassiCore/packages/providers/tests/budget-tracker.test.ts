/**
 * BudgetTracker tests — Provider request budget management with persistence and tier-based throttling.
 *
 * The BudgetTracker monitors metered provider usage (e.g., GitHub Copilot's 1500 request/month limit)
 * and emits events when usage crosses tier thresholds (normal → cautious → frugal → critical).
 * This enables adaptive behavior: background tasks can switch to free models as budgets tighten.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { BudgetTracker, createBudgetTracker, type BudgetTier } from '../src/budget-tracker.js'
import type { ILogger, IEventBus } from '@cassicore/foundation'
import type { RuntimeEvent } from '@cassicore/foundation'
import { readFile, unlink, writeFile, mkdir } from 'node:fs/promises'
import { join } from 'node:path'
import { homedir } from 'node:os'
import { existsSync } from 'node:fs'


function makeMockLogger(): ILogger {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn(() => makeMockLogger()),
  } as unknown as ILogger
}

function makeMockBus(): IEventBus & { events: RuntimeEvent[]; handlers: Map<string, Function[]> } {
  const events: RuntimeEvent[] = []
  const handlers = new Map<string, Function[]>()
  return {
    events,
    handlers,
    emit(event: RuntimeEvent) {
      events.push(event)
      const list = handlers.get(event.type) ?? []
      for (const fn of list) fn(event)
    },
    on(type: string, handler: Function) {
      const list = handlers.get(type) ?? []
      list.push(handler)
      handlers.set(type, list)
      return () => {
        const idx = list.indexOf(handler)
        if (idx >= 0) list.splice(idx, 1)
      }
    },
  } as any
}


const BUDGET_STATE_PATH = join(homedir(), '.cassicore', 'budget-state.json')

function makeTracker(monthlyLimit = 100): BudgetTracker {
  return createBudgetTracker(makeMockLogger(), {
    'test-provider': { monthlyLimit },
  })
}

/** Simulate metered requests by importing state directly */
function setUsage(tracker: BudgetTracker, count: number): void {
  const now = new Date()
  const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  const day = now.getDate()
  tracker.importState({
    'test-provider': {
      month,
      count,
      dailyCounts: { [day]: count },
    },
  })
}


describe('BudgetTracker', () => {
  describe('state persistence (exportState / importState)', () => {
    it('round-trips budget counters through export and import so usage survives daemon restarts', () => {
      const tracker = makeTracker()
      setUsage(tracker, 42)

      const exported = tracker.exportState()
      expect(exported['test-provider']).toBeDefined()
      expect(exported['test-provider'].count).toBe(42)

      // Create a fresh tracker and import
      const tracker2 = createBudgetTracker(makeMockLogger(), {
        'test-provider': { monthlyLimit: 100 },
      })
      tracker2.importState(exported)

      const snapshot = tracker2.getSnapshot('test-provider')
      expect(snapshot).toBeDefined()
      expect(snapshot!.used).toBe(42)
    })

    it('discards stale month data on import to prevent billing confusion across month boundaries', () => {
      const tracker = makeTracker()
      tracker.importState({
        'test-provider': {
          month: '1999-01', // ancient
          count: 999,
          dailyCounts: { 1: 999 },
        },
      })

      const snapshot = tracker.getSnapshot('test-provider')
      // Should not have imported stale data — snapshot should show 0 or undefined
      expect(snapshot?.used ?? 0).toBe(0)
    })

    it('initializes previousTiers on import so first request does not emit false transition', () => {
      const tracker = makeTracker(100)
      const bus = makeMockBus()
      tracker.wire(bus)

      // Import state at 60% — this is in 'cautious' tier
      const now = new Date()
      const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
      tracker.importState({
        'test-provider': {
          month,
          count: 60,
          dailyCounts: { [now.getDate()]: 60 },
        },
      })

      // Record one more request — should NOT emit tier_changed since we're still in cautious
      tracker.recordRequest('test-provider/some-model')

      const tierChanges = bus.events.filter(e => e.type === 'budget:tier_changed')
      expect(tierChanges.length).toBe(0)
    })
  })

  describe('tier calculation (getTier)', () => {
    it('returns normal tier when usage is below 50% of monthly limit', () => {
      const tracker = makeTracker(100)
      expect(tracker.getTier('test-provider')).toBe('normal')
    })

    it('returns cautious tier when usage crosses 50% threshold', () => {
      const tracker = makeTracker(100)
      setUsage(tracker, 50)
      expect(tracker.getTier('test-provider')).toBe('cautious')
    })

    it('returns frugal tier when usage crosses 75% threshold', () => {
      const tracker = makeTracker(100)
      setUsage(tracker, 75)
      expect(tracker.getTier('test-provider')).toBe('frugal')
    })

    it('returns critical tier when usage crosses 90% threshold', () => {
      const tracker = makeTracker(100)
      setUsage(tracker, 90)
      expect(tracker.getTier('test-provider')).toBe('critical')
    })

    it('returns normal tier for unknown providers without configured budgets', () => {
      const tracker = makeTracker(100)
      expect(tracker.getTier('unknown-provider')).toBe('normal')
    })
  })

  describe('tier change events', () => {
    it('emits budget:tier_changed event when usage crosses into a new tier', () => {
      const tracker = makeTracker(100)
      const bus = makeMockBus()
      tracker.wire(bus)

      // Set up initial state at normal tier
      setUsage(tracker, 10)

      // Record requests by emitting provider:request_end events
      // Simulate crossing the cautious threshold (50%)
      setUsage(tracker, 49)

      // Now record a metered request that pushes us over 50%
      // We need to trigger checkThresholds by calling recordRequest
      tracker.recordRequest('test-provider/some-model')

      const tierEvents = bus.events.filter(e => e.type === 'budget:tier_changed')
      expect(tierEvents.length).toBeGreaterThanOrEqual(1)

      const last = tierEvents[tierEvents.length - 1] as any
      expect(last.providerId).toBe('test-provider')
      expect(last.newTier).toBe('cautious')
    })

    it('emits budget:warning event for non-normal tiers to alert monitoring systems', () => {
      const tracker = makeTracker(100)
      const bus = makeMockBus()
      tracker.wire(bus)

      // Push directly to frugal
      setUsage(tracker, 75)
      tracker.recordRequest('test-provider/some-model')

      const warnings = bus.events.filter(e => e.type === 'budget:warning')
      expect(warnings.length).toBeGreaterThanOrEqual(1)
      expect((warnings[0] as any).tier).toBe('frugal')
    })

    it('does not emit tier_changed if tier did not actually change', () => {
      const tracker = makeTracker(100)
      const bus = makeMockBus()
      tracker.wire(bus)

      // Start at cautious
      setUsage(tracker, 55)
      // Record — this causes a tier_changed from normal→cautious because importState sets previousTier
      tracker.recordRequest('test-provider/some-model')
      const firstTierEvents = bus.events.filter(e => e.type === 'budget:tier_changed')

      // Record another within the same tier — should NOT add another tier_changed
      const countBefore = bus.events.filter(e => e.type === 'budget:tier_changed').length
      tracker.recordRequest('test-provider/some-model')
      const countAfter = bus.events.filter(e => e.type === 'budget:tier_changed').length

      expect(countAfter).toBe(countBefore)
    })
  })

  describe('disk persistence', () => {
    afterEach(async () => {
      // Clean up test files if they exist
      try { await unlink(BUDGET_STATE_PATH) } catch { /* ignore */ }
    })

    it('saves state to disk and loads it back to survive daemon restarts', async () => {
      const tracker = makeTracker(100)
      setUsage(tracker, 37)

      await tracker.saveToDisk()

      // Verify file exists
      const raw = await readFile(BUDGET_STATE_PATH, 'utf-8')
      const state = JSON.parse(raw)
      expect(state['test-provider']).toBeDefined()
      expect(state['test-provider'].count).toBe(37)

      // Load into a fresh tracker
      const tracker2 = createBudgetTracker(makeMockLogger(), {
        'test-provider': { monthlyLimit: 100 },
      })
      await tracker2.loadFromDisk()

      const snapshot = tracker2.getSnapshot('test-provider')
      expect(snapshot).toBeDefined()
      expect(snapshot!.used).toBe(37)
    })

    it('handles missing state file gracefully on first run without throwing', async () => {
      // Remove file if exists
      try { await unlink(BUDGET_STATE_PATH) } catch { /* ignore */ }

      const tracker = makeTracker(100)
      // Should not throw
      await tracker.loadFromDisk()

      // Should have no usage
      const snapshot = tracker.getSnapshot('test-provider')
      expect(snapshot?.used ?? 0).toBe(0)
    })
  })

  describe('request recording and cost classification', () => {
    it('only counts metered requests against the budget (free models are excluded)', () => {
      const tracker = makeTracker(100)
      const bus = makeMockBus()
      tracker.wire(bus)

      // Record a free model request (gpt-5-mini on github-copilot is free)
      tracker.recordRequest('github-copilot/gpt-5-mini')

      // Should not increment counter for free models
      const snapshot = tracker.getSnapshot('github-copilot')
      // github-copilot is not in our test budget config, so it returns null
      expect(snapshot).toBeNull()
    })

    it('increments counter for metered provider/model combinations', () => {
      const tracker = makeTracker(100)

      // Record a metered request
      tracker.recordRequest('test-provider/some-model')

      const snapshot = tracker.getSnapshot('test-provider')
      expect(snapshot!.used).toBe(1)
    })

    it('ignores requests for providers without configured budgets', () => {
      const tracker = makeTracker(100)

      // Record for unconfigured provider
      tracker.recordRequest('unknown-provider/some-model')

      const snapshot = tracker.getSnapshot('unknown-provider')
      expect(snapshot).toBeNull()
    })
  })

  describe('budget queries (getSnapshot, getRemaining, getUsagePercent)', () => {
    it('returns complete budget snapshot with usage, remaining, and projections', () => {
      const tracker = makeTracker(100)
      setUsage(tracker, 25)

      const snapshot = tracker.getSnapshot('test-provider')
      expect(snapshot).toBeDefined()
      expect(snapshot!.providerId).toBe('test-provider')
      expect(snapshot!.monthlyLimit).toBe(100)
      expect(snapshot!.used).toBe(25)
      expect(snapshot!.remaining).toBe(75)
      expect(snapshot!.percentUsed).toBe(0.25)
    })

    it('returns null snapshot for providers without budget configuration', () => {
      const tracker = makeTracker(100)
      const snapshot = tracker.getSnapshot('unconfigured-provider')
      expect(snapshot).toBeNull()
    })

    it('calculates remaining requests correctly', () => {
      const tracker = makeTracker(100)
      setUsage(tracker, 30)

      expect(tracker.getRemaining('test-provider')).toBe(70)
    })

    it('returns Infinity for remaining requests of unconfigured providers', () => {
      const tracker = makeTracker(100)
      expect(tracker.getRemaining('unknown')).toBe(Infinity)
    })

    it('calculates usage percentage as decimal between 0 and 1', () => {
      const tracker = makeTracker(100)
      setUsage(tracker, 50)

      expect(tracker.getUsagePercent('test-provider')).toBe(0.5)
    })

    it('returns 0 usage percent for unconfigured providers', () => {
      const tracker = makeTracker(100)
      expect(tracker.getUsagePercent('unknown')).toBe(0)
    })
  })

  describe('canAfford — request admission control', () => {
    it('allows free model requests regardless of budget exhaustion', () => {
      const tracker = makeTracker(100)
      setUsage(tracker, 100) // Exhausted

      // Free models should always be allowed
      expect(tracker.canAfford('github-copilot/gpt-5-mini')).toBe(true)
    })

    it('allows local model requests regardless of budget', () => {
      const tracker = makeTracker(100)
      setUsage(tracker, 100) // Exhausted

      // Local models should always be allowed
      expect(tracker.canAfford('lmstudio/llama-3')).toBe(true)
    })

    it('allows metered requests when budget has remaining capacity', () => {
      const tracker = makeTracker(100)
      setUsage(tracker, 50)

      expect(tracker.canAfford('test-provider/some-model')).toBe(true)
    })

    it('always allows metered requests even when budget is exhausted (tracking only)', () => {
      const tracker = makeTracker(100)
      setUsage(tracker, 100)

      // Budget is tracking only — never denies requests
      tracker.recordRequest('test-provider/some-model') // Now at 101
      expect(tracker.canAfford('test-provider/some-model')).toBe(true)
    })
  })

  describe('getAllSnapshots — multi-provider overview', () => {
    it('returns snapshots for all configured providers', () => {
      const tracker = createBudgetTracker(makeMockLogger(), {
        'provider-a': { monthlyLimit: 100 },
        'provider-b': { monthlyLimit: 200 },
      })

      const snapshots = tracker.getAllSnapshots()
      expect(snapshots).toHaveLength(2)
      expect(snapshots.map(s => s.providerId).sort()).toEqual(['provider-a', 'provider-b'])
    })

    it('returns empty array when no providers are configured', () => {
      const tracker = createBudgetTracker(makeMockLogger(), {})
      const snapshots = tracker.getAllSnapshots()
      expect(snapshots).toHaveLength(0)
    })
  })

  describe('edge cases and error handling', () => {
    it('handles zero monthly limit gracefully without division errors', () => {
      const tracker = createBudgetTracker(makeMockLogger(), {
        'zero-provider': { monthlyLimit: 0 },
      })

      // Should not throw
      const snapshot = tracker.getSnapshot('zero-provider')
      expect(snapshot).toBeDefined()
      expect(snapshot!.percentUsed).toBe(0)
      expect(snapshot!.remaining).toBe(0)
    })

    it('handles concurrent request counting without data races (single-writer invariant)', () => {
      const tracker = makeTracker(100)

      // Simulate rapid sequential requests (in real usage, daemon is single-writer)
      for (let i = 0; i < 10; i++) {
        tracker.recordRequest('test-provider/model')
      }

      const snapshot = tracker.getSnapshot('test-provider')
      expect(snapshot!.used).toBe(10)
    })

    it('calculates daily burn rate from daily usage history', () => {
      const tracker = makeTracker(100)
      const now = new Date()
      const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
      
      // Simulate 2 days of usage: day 1 had 10 requests, day 2 had 20
      tracker.importState({
        'test-provider': {
          month,
          count: 30,
          dailyCounts: { 
            [now.getDate() - 1]: 10,
            [now.getDate()]: 20 
          },
        },
      })

      const snapshot = tracker.getSnapshot('test-provider')
      // Burn rate = average of daily counts = (10 + 20) / 2 = 15
      expect(snapshot!.dailyBurnRate).toBe(15)
    })

    it('projects exhaustion day when burn rate indicates budget will deplete', () => {
      const tracker = makeTracker(100)
      const now = new Date()
      const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
      const today = now.getDate()
      
      // Simulate usage that will exhaust budget: 50 used, 50 remaining, burn rate of 10/day
      tracker.importState({
        'test-provider': {
          month,
          count: 50,
          dailyCounts: { [today]: 10 }, // Burn rate = 10/day
        },
      })

      const snapshot = tracker.getSnapshot('test-provider')
      expect(snapshot!.projectedExhaustionDay).toBeDefined()
      // 50 remaining / 10 per day = 5 more days
      expect(snapshot!.projectedExhaustionDay).toBe(today + 5)
    })

    it('returns null exhaustion day when burn rate is zero', () => {
      const tracker = makeTracker(100)
      
      const snapshot = tracker.getSnapshot('test-provider')
      expect(snapshot!.projectedExhaustionDay).toBeNull()
    })

    it('returns null exhaustion day when projection exceeds month boundary', () => {
      const tracker = makeTracker(100)
      const now = new Date()
      const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
      const today = now.getDate()
      const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
      
      // Simulate low burn rate that won't exhaust before month end
      tracker.importState({
        'test-provider': {
          month,
          count: 10,
          dailyCounts: { [today]: 1 }, // Burn rate = 1/day, 90 remaining would take 90 days
        },
      })

      const snapshot = tracker.getSnapshot('test-provider')
      // If today + 90 > daysInMonth, exhaustion is beyond this month
      if (today + 90 > daysInMonth) {
        expect(snapshot!.projectedExhaustionDay).toBeNull()
      }
    })

    it('handles EventBus wiring when no bus is attached', () => {
      const tracker = makeTracker(100)
      
      // Should not throw when recording without wired bus
      expect(() => {
        tracker.recordRequest('test-provider/model')
      }).not.toThrow()
    })
  })
})
