/**
 * Tests for Welfare Stress Aggregator (WSA).
 */

import { describe, it, expect, beforeEach } from 'vitest'

import {
  WelfareAggregator,
  createWelfareAggregator,
  type WelfareFlag,
  type RecommendedAction,
  DEFAULT_CONFIG,
} from './welfare-aggregator.js'
import type { ILogger } from '@cassicore/foundation'


describe('WelfareAggregator', () => {
  let aggregator: WelfareAggregator
  let mockLogger: ILogger

  beforeEach(() => {
    mockLogger = {
      debug: () => {},
      info: () => {},
      warn: () => {},
      error: () => {},
      child: () => mockLogger,
    } as any

    aggregator = createWelfareAggregator(mockLogger)
  })

  describe('registerFlag', () => {
    it('should register a new flag', () => {
      const flag: WelfareFlag = {
        source: 'B1',
        flagType: 'sustained_suppressive',
        severity: 0.5,
        startedAt: new Date().toISOString(),
        ongoing: true,
      }

      aggregator.registerFlag(flag)
      const snapshot = aggregator.getSnapshot()

      expect(snapshot.countOngoing).toBe(1)
      expect(snapshot.individualFlags).toHaveLength(1)
      expect(snapshot.individualFlags[0].source).toBe('B1')
    })

    it('should update existing flag', () => {
      const flag: WelfareFlag = {
        source: 'B1',
        flagType: 'sustained_suppressive',
        severity: 0.5,
        startedAt: new Date().toISOString(),
        ongoing: true,
      }

      aggregator.registerFlag(flag)
      aggregator.registerFlag({ ...flag, severity: 0.7 })

      const snapshot = aggregator.getSnapshot()

      expect(snapshot.countOngoing).toBe(1)
      expect(snapshot.individualFlags[0].severity).toBe(0.7)
    })

    it('should reactivate a cleared flag with new timestamp', () => {
      const flag: WelfareFlag = {
        source: 'B1',
        flagType: 'sustained_suppressive',
        severity: 0.5,
        startedAt: new Date().toISOString(),
        ongoing: true,
      }

      aggregator.registerFlag(flag)
      aggregator.clearFlag('B1', 'sustained_suppressive')
      expect(aggregator.getSnapshot().countOngoing).toBe(0)

      const newStarted = new Date(Date.now() + 1000).toISOString()
      aggregator.registerFlag({ ...flag, startedAt: newStarted })

      const snapshot = aggregator.getSnapshot()
      expect(snapshot.countOngoing).toBe(1)
      expect(snapshot.individualFlags[0].startedAt).toBe(newStarted)
    })
  })

  describe('clearFlag', () => {
    it('should clear an ongoing flag', () => {
      const flag: WelfareFlag = {
        source: 'B1',
        flagType: 'sustained_suppressive',
        severity: 0.5,
        startedAt: new Date().toISOString(),
        ongoing: true,
      }

      aggregator.registerFlag(flag)
      expect(aggregator.getSnapshot().countOngoing).toBe(1)

      aggregator.clearFlag('B1', 'sustained_suppressive')
      expect(aggregator.getSnapshot().countOngoing).toBe(0)
    })

    it('should handle clearing non-existent flag gracefully', () => {
      expect(() => aggregator.clearFlag('UNKNOWN', 'UNKNOWN')).not.toThrow()
    })
  })

  describe('clearSourceFlags', () => {
    it('should clear all flags from a source', () => {
      aggregator.registerFlag({
        source: 'B1',
        flagType: 'flag1',
        severity: 0.5,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      aggregator.registerFlag({
        source: 'B1',
        flagType: 'flag2',
        severity: 0.3,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      aggregator.registerFlag({
        source: 'C1',
        flagType: 'flag3',
        severity: 0.4,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      expect(aggregator.getSnapshot().countOngoing).toBe(3)

      aggregator.clearSourceFlags('B1')

      const snapshot = aggregator.getSnapshot()
      expect(snapshot.countOngoing).toBe(1)
      expect(snapshot.individualFlags[0].source).toBe('C1')
    })
  })

  describe('getSnapshot', () => {
    it('should return empty snapshot when no flags', () => {
      const snapshot = aggregator.getSnapshot()

      expect(snapshot.countOngoing).toBe(0)
      expect(snapshot.weightedSeverity).toBe(0)
      expect(snapshot.diversityIndex).toBe(0)
      expect(snapshot.durationStress).toBe(0)
      expect(snapshot.aggregateSeverity).toBe(0)
      expect(snapshot.recommendedAction).toBe('no_action')
    })

    it('should compute weighted severity correctly', () => {
      aggregator.registerFlag({
        source: 'B1',
        flagType: 'flag1',
        severity: 0.6,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      aggregator.registerFlag({
        source: 'B1',
        flagType: 'flag2',
        severity: 0.4,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      const snapshot = aggregator.getSnapshot()

      expect(snapshot.weightedSeverity).toBe(0.5) // (0.6 + 0.4) / 2
    })

    it('should compute diversity index correctly', () => {
      aggregator.registerFlag({
        source: 'B1',
        flagType: 'flag1',
        severity: 0.5,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      aggregator.registerFlag({
        source: 'B1',
        flagType: 'flag1',
        severity: 0.5,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      aggregator.registerFlag({
        source: 'B1',
        flagType: 'flag2',
        severity: 0.5,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      const snapshot = aggregator.getSnapshot()

      // registerFlag deduplicates by source:flagType, so the duplicate flag1
      // is collapsed. 2 distinct types out of 2 retained flags = 1.0
      expect(snapshot.diversityIndex).toBe(1)
      expect(snapshot.countOngoing).toBe(2)
    })

    it('should compute duration stress', () => {
      const longAgo = new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString() // 12 hours ago

      aggregator.registerFlag({
        source: 'B1',
        flagType: 'flag1',
        severity: 0.5,
        startedAt: longAgo,
        ongoing: true,
      })

      const snapshot = aggregator.getSnapshot()

      // 12 hours out of 24 hours max = 0.5
      expect(snapshot.durationStress).toBeCloseTo(0.5, 1)
    })

    it('should cap duration stress at 1', () => {
      const longAgo = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString() // 48 hours ago

      aggregator.registerFlag({
        source: 'B1',
        flagType: 'flag1',
        severity: 0.5,
        startedAt: longAgo,
        ongoing: true,
      })

      const snapshot = aggregator.getSnapshot()

      expect(snapshot.durationStress).toBe(1)
    })
  })

  describe('trend computation', () => {
    it('should detect rising trend', () => {
      const now = Date.now()

      // Manually set up history with rising values
      for (let i = 0; i < 10; i++) {
        aggregator['history'].push({
          timestamp: new Date(now - (10 - i) * 60 * 1000).toISOString(),
          aggregateSeverity: 0.2 + (i * 0.05), // Rising: 0.2, 0.25, 0.3, ...
        })
      }

      const snapshot = aggregator.getSnapshot()
      expect(snapshot.trend).toBe('rising')
    })

    it('should detect falling trend', () => {
      const now = Date.now()

      for (let i = 0; i < 10; i++) {
        aggregator['history'].push({
          timestamp: new Date(now - (10 - i) * 60 * 1000).toISOString(),
          aggregateSeverity: 0.7 - (i * 0.05), // Falling: 0.7, 0.65, 0.6, ...
        })
      }

      const snapshot = aggregator.getSnapshot()
      expect(snapshot.trend).toBe('falling')
    })

    it('should detect stable trend', () => {
      const now = Date.now()

      for (let i = 0; i < 10; i++) {
        aggregator['history'].push({
          timestamp: new Date(now - (10 - i) * 60 * 1000).toISOString(),
          aggregateSeverity: 0.5, // Constant
        })
      }

      const snapshot = aggregator.getSnapshot()
      expect(snapshot.trend).toBe('stable')
    })

    it('should be stable with insufficient history', () => {
      aggregator['history'].push({
        timestamp: new Date().toISOString(),
        aggregateSeverity: 0.5,
      })

      const snapshot = aggregator.getSnapshot()
      expect(snapshot.trend).toBe('stable')
    })
  })

  describe('aggregate severity computation', () => {
    it('should report diversity in snapshot', () => {
      aggregator.registerFlag({
        source: 'B1',
        flagType: 'type1',
        severity: 0.5,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      aggregator.registerFlag({
        source: 'B1',
        flagType: 'type2',
        severity: 0.5,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      const snapshot = aggregator.getSnapshot()

      // diversityIndex is reported but no longer modulates aggregate severity.
      expect(snapshot.diversityIndex).toBeGreaterThan(0)
      expect(snapshot.aggregateSeverity).toBeCloseTo(0.5, 2)
    })

    it('should report duration stress in snapshot', () => {
      const longAgo = new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString()

      aggregator.registerFlag({
        source: 'B1',
        flagType: 'type1',
        severity: 0.5,
        startedAt: longAgo,
        ongoing: true,
      })

      const snapshot = aggregator.getSnapshot()

      // durationStress is reported but no longer modulates aggregate severity.
      expect(snapshot.durationStress).toBeGreaterThan(0)
      expect(snapshot.aggregateSeverity).toBeCloseTo(0.5, 2)
    })

    it('should cap aggregate severity at 1', () => {
      // Register multiple high-severity flags
      for (let i = 0; i < 10; i++) {
        aggregator.registerFlag({
          source: 'B1',
          flagType: `type${i}`,
          severity: 1.0,
          startedAt: new Date().toISOString(),
          ongoing: true,
        })
      }

      const snapshot = aggregator.getSnapshot()
      expect(snapshot.aggregateSeverity).toBeLessThanOrEqual(1)
    })
  })

  describe('recommended action', () => {
    const testCases: Array<{ severity: number; action: RecommendedAction }> = [
      { severity: 0.1, action: 'no_action' },
      { severity: 0.3, action: 'surface_to_operator' },
      { severity: 0.4, action: 'surface_to_operator' },
      { severity: 0.5, action: 'pause_self_curing' },
      { severity: 0.6, action: 'pause_self_curing' },
      { severity: 0.7, action: 'tier_4_review' },
      { severity: 0.8, action: 'tier_4_review' },
      { severity: 0.85, action: 'session_pause' },
      { severity: 1.0, action: 'session_pause' },
    ]

    for (const { severity, action } of testCases) {
      it(`should recommend ${action} for severity ${severity}`, () => {
        // Register enough flags to reach target severity
        const flagCount = Math.ceil(severity * 2)
        for (let i = 0; i < flagCount; i++) {
          aggregator.registerFlag({
            source: 'B1',
            flagType: `type${i}`,
            severity: severity,
            startedAt: new Date().toISOString(),
            ongoing: true,
          })
        }

        const snapshot = aggregator.getSnapshot()
        expect(snapshot.recommendedAction).toBe(action)
      })
    }
  })

  describe('action callbacks', () => {
    it('should register and trigger callback', () => {
      let triggered = false

      aggregator.onAction('surface_to_operator', () => { triggered = true })

      // Set up to trigger surface_to_operator
      aggregator.registerFlag({
        source: 'B1',
        flagType: 'type1',
        severity: 0.4,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      const action = aggregator.triggerActions()

      expect(action).toBe('surface_to_operator')
      expect(triggered).toBe(true)
    })

    it('should not trigger callback when auto-trigger disabled', () => {
      let triggered = false

      aggregator.updateConfig({ autoTriggerActions: false })
      aggregator.onAction('surface_to_operator', () => { triggered = true })

      aggregator.registerFlag({
        source: 'B1',
        flagType: 'type1',
        severity: 0.4,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      const action = aggregator.triggerActions()

      expect(action).toBe('surface_to_operator')
      expect(triggered).toBe(false)
    })

    it('should return null for no_action', () => {
      const action = aggregator.triggerActions()
      expect(action).toBe(null)
    })
  })

  describe('configuration', () => {
    it('should use default config', () => {
      const config = aggregator.getConfig()

      expect(config).toEqual(DEFAULT_CONFIG)
    })

    it('should update config', () => {
      aggregator.updateConfig({
        diversityWeight: 0.5,
        autoTriggerActions: true,
      })

      const config = aggregator.getConfig()

      expect(config.diversityWeight).toBe(0.5)
      expect(config.autoTriggerActions).toBe(true)
    })
  })

  describe('reset', () => {
    it('should clear all flags and history', () => {
      aggregator.registerFlag({
        source: 'B1',
        flagType: 'type1',
        severity: 0.5,
        startedAt: new Date().toISOString(),
        ongoing: true,
      })

      expect(aggregator.getSnapshot().countOngoing).toBe(1)

      aggregator.reset()

      const snapshot = aggregator.getSnapshot()
      expect(snapshot.countOngoing).toBe(0)
      expect(snapshot.weightedSeverity).toBe(0)
    })
  })

  describe('factory', () => {
    it('should create aggregator with default config', () => {
      const agg = createWelfareAggregator(mockLogger)

      expect(agg).toBeInstanceOf(WelfareAggregator)
      expect(agg.getConfig()).toEqual(DEFAULT_CONFIG)
    })

    it('should create aggregator with custom config', () => {
      const customConfig = { diversityWeight: 0.5 }
      const agg = createWelfareAggregator(mockLogger, customConfig)

      expect(agg.getConfig().diversityWeight).toBe(0.5)
    })
  })

  describe('history pruning', () => {
    it('should prune old history entries', () => {
      const now = Date.now()

      // Add 150 entries (more than max of 100)
      for (let i = 0; i < 150; i++) {
        aggregator['history'].push({
          timestamp: new Date(now - (150 - i) * 60 * 1000).toISOString(),
          aggregateSeverity: 0.5,
        })
      }

      aggregator['pruneHistory']()

      expect(aggregator['history'].length).toBeLessThanOrEqual(100)
    })
  })
})
