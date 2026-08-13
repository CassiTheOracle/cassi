import { describe, it, expect, beforeEach } from 'vitest'
import { MeditationFeedbackTracker } from '../src/meditation/meditation-feedback.js'
import { mockLogger } from './helpers.js'

describe('MeditationFeedbackTracker', () => {
  let tracker: MeditationFeedbackTracker

  beforeEach(() => {
    tracker = new MeditationFeedbackTracker(mockLogger(), 'test-session-001')
  })

  describe('recordRetrieved', () => {
    it('tracks retrieved engrams with context', () => {
      tracker.recordRetrieved(['e1', 'e2', 'e3'], 'organizing:kindle:test')

      const stats = tracker.getStats()
      expect(stats.retrievedCount).toBe(3)
    })

    it('does not duplicate engram tracking', () => {
      tracker.recordRetrieved(['e1', 'e2'], 'context1')
      tracker.recordRetrieved(['e2', 'e3'], 'context2')

      const stats = tracker.getStats()
      expect(stats.retrievedCount).toBe(3) // e1, e2, e3
    })
  })

  describe('recordUsed', () => {
    it('tracks used engrams that were retrieved', () => {
      tracker.recordRetrieved(['e1', 'e2', 'e3'], 'context')
      tracker.recordUsed(['e1', 'e2'])

      const stats = tracker.getStats()
      expect(stats.usedCount).toBe(2)
    })

    it('ignores engrams that were not retrieved', () => {
      tracker.recordRetrieved(['e1'], 'context')
      tracker.recordUsed(['e999'])

      const stats = tracker.getStats()
      expect(stats.usedCount).toBe(0)
    })
  })

  describe('recordProductive', () => {
    it('marks engrams as both used and productive', () => {
      tracker.recordRetrieved(['e1', 'e2'], 'context')
      tracker.recordProductive(['e1'])

      const stats = tracker.getStats()
      expect(stats.productiveCount).toBe(1)
      expect(stats.usedCount).toBe(1)
    })
  })

  describe('computeFeedback', () => {
    it('returns true for used engrams, false for unused', () => {
      tracker.recordRetrieved(['e1', 'e2', 'e3'], 'context')
      tracker.recordUsed(['e1', 'e2'])

      const feedback = tracker.computeFeedback()

      expect(feedback).toEqual({
        e1: true,
        e2: true,
        e3: false,
      })
    })

    it('returns true for productive engrams', () => {
      tracker.recordRetrieved(['e1', 'e2'], 'context')
      tracker.recordProductive(['e1'])

      const feedback = tracker.computeFeedback()

      expect(feedback).toEqual({
        e1: true,
        e2: false,
      })
    })

    it('returns empty object when no engrams tracked', () => {
      const feedback = tracker.computeFeedback()
      expect(feedback).toEqual({})
    })
  })

  describe('getStats', () => {
    it('computes helpful ratio correctly', () => {
      tracker.recordRetrieved(['e1', 'e2', 'e3', 'e4'], 'context')
      tracker.recordUsed(['e1', 'e2', 'e3'])

      const stats = tracker.getStats()

      expect(stats.helpfulCount).toBe(3)
      expect(stats.unhelpfulCount).toBe(1)
      expect(stats.helpfulRatio).toBeCloseTo(0.75)
    })

    it('returns zero ratio when no engrams tracked', () => {
      const stats = tracker.getStats()
      expect(stats.helpfulRatio).toBe(0)
    })
  })
})
