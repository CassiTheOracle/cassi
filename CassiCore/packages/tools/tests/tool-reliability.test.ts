/**
 * Tests for Tool Reliability Tracker with Circuit Breaker Pattern
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { ToolReliabilityTracker, type ReliabilityConfig } from '../src/reliability.js'
import { rootLogger } from '../src/vendor/core/logger.js'

describe('ToolReliabilityTracker', () => {
  let tracker: ToolReliabilityTracker
  const testConfig: ReliabilityConfig = {
    failureThreshold: 3,
    cooldownMs: 1000,
    maxSamples: 50,
  }

  beforeEach(() => {
    tracker = new ToolReliabilityTracker(rootLogger.child('test'), testConfig)
  })

  describe('circuit breaker state machine', () => {
    it('starts in closed state', () => {
      expect(tracker.canExecute('test-tool')).toBe(true)
      const metrics = tracker.getMetrics('test-tool') as any
      expect(metrics.circuitState).toBe('closed')
    })

    it('transitions to open after consecutive failures', () => {
      // Record failures up to threshold
      for (let i = 0; i < testConfig.failureThreshold; i++) {
        tracker.recordFailure('test-tool', 100)
      }

      // Circuit should now be open
      expect(tracker.canExecute('test-tool')).toBe(false)
      const metrics = tracker.getMetrics('test-tool') as any
      expect(metrics.circuitState).toBe('open')
    })

    it('transitions to half-open after cooldown', async () => {
      // Open the circuit
      for (let i = 0; i < testConfig.failureThreshold; i++) {
        tracker.recordFailure('test-tool', 100)
      }

      // Wait for cooldown
      await new Promise(resolve => setTimeout(resolve, testConfig.cooldownMs + 50))

      // Should transition to half-open and allow execution
      expect(tracker.canExecute('test-tool')).toBe(true)
      const metrics = tracker.getMetrics('test-tool') as any
      expect(metrics.circuitState).toBe('half-open')
    })

    it('closes circuit on success in half-open state', async () => {
      // Open the circuit
      for (let i = 0; i < testConfig.failureThreshold; i++) {
        tracker.recordFailure('test-tool', 100)
      }

      // Wait for cooldown
      await new Promise(resolve => setTimeout(resolve, testConfig.cooldownMs + 50))

      // Trigger half-open state
      tracker.canExecute('test-tool')

      // Record success
      tracker.recordSuccess('test-tool', 50)

      // Circuit should be closed
      const metrics = tracker.getMetrics('test-tool') as any
      expect(metrics.circuitState).toBe('closed')
      expect(metrics.consecutiveFailures).toBe(0)
    })

    it('reopens circuit on failure in half-open state', async () => {
      // Open the circuit
      for (let i = 0; i < testConfig.failureThreshold; i++) {
        tracker.recordFailure('test-tool', 100)
      }

      // Wait for cooldown
      await new Promise(resolve => setTimeout(resolve, testConfig.cooldownMs + 50))

      // Trigger half-open state
      tracker.canExecute('test-tool')

      // Record failure
      tracker.recordFailure('test-tool', 100)

      // Circuit should be open again
      const metrics = tracker.getMetrics('test-tool') as any
      expect(metrics.circuitState).toBe('open')
    })
  })

  describe('metrics tracking', () => {
    it('tracks success and failure counts', () => {
      tracker.recordSuccess('tool-a', 100)
      tracker.recordSuccess('tool-a', 150)
      tracker.recordFailure('tool-a', 200)
      tracker.recordSuccess('tool-a', 120)

      const metrics = tracker.getMetrics('tool-a') as any
      expect(metrics.totalCalls).toBe(4)
      expect(metrics.successCount).toBe(3)
      expect(metrics.failureCount).toBe(1)
      expect(metrics.successRate).toBe(0.75)
    })

    it('tracks consecutive failures', () => {
      tracker.recordSuccess('tool-b', 100)
      tracker.recordFailure('tool-b', 150)
      tracker.recordFailure('tool-b', 200)

      const metrics = tracker.getMetrics('tool-b') as any
      expect(metrics.consecutiveFailures).toBe(2)

      // Success resets consecutive failures
      tracker.recordSuccess('tool-b', 100)
      const metrics2 = tracker.getMetrics('tool-b') as any
      expect(metrics2.consecutiveFailures).toBe(0)
    })

    it('calculates average duration', () => {
      tracker.recordSuccess('tool-c', 100)
      tracker.recordSuccess('tool-c', 200)
      tracker.recordSuccess('tool-c', 300)

      const metrics = tracker.getMetrics('tool-c') as any
      expect(metrics.avgDurationMs).toBe(200)
    })

    it('calculates p95 duration', () => {
      // Record 20 samples with varying durations
      for (let i = 1; i <= 20; i++) {
        tracker.recordSuccess('tool-d', i * 10)
      }

      const metrics = tracker.getMetrics('tool-d') as any
      // P95 of [10, 20, 30, ..., 200] should be around 190-200
      expect(metrics.p95DurationMs).toBeGreaterThanOrEqual(190)
    })

    it('maintains rolling window of duration samples', () => {
      // Record more samples than maxSamples
      for (let i = 0; i < 100; i++) {
        tracker.recordSuccess('tool-e', 100)
      }

      const metrics = tracker.getMetrics('tool-e') as any
      // Should still have reasonable metrics (not blown up)
      expect(metrics.totalCalls).toBe(100)
      expect(metrics.avgDurationMs).toBe(100)
    })
  })

  describe('reset functionality', () => {
    it('resets circuit state to closed', () => {
      // Open the circuit
      for (let i = 0; i < testConfig.failureThreshold; i++) {
        tracker.recordFailure('tool-f', 100)
      }

      expect(tracker.canExecute('tool-f')).toBe(false)

      // Reset
      tracker.reset('tool-f')

      // Should be closed now
      expect(tracker.canExecute('tool-f')).toBe(true)
      const metrics = tracker.getMetrics('tool-f') as any
      expect(metrics.circuitState).toBe('closed')
    })

    it('resets consecutive failures', () => {
      tracker.recordFailure('tool-g', 100)
      tracker.recordFailure('tool-g', 100)

      let metrics = tracker.getMetrics('tool-g') as any
      expect(metrics.consecutiveFailures).toBe(2)

      tracker.reset('tool-g')

      metrics = tracker.getMetrics('tool-g') as any
      expect(metrics.consecutiveFailures).toBe(0)
    })
  })

  describe('multiple tools', () => {
    it('tracks metrics independently for each tool', () => {
      tracker.recordFailure('tool-1', 100)
      tracker.recordFailure('tool-1', 100)
      tracker.recordSuccess('tool-2', 100)

      const metrics1 = tracker.getMetrics('tool-1') as any
      const metrics2 = tracker.getMetrics('tool-2') as any

      expect(metrics1.failureCount).toBe(2)
      expect(metrics1.successCount).toBe(0)
      expect(metrics2.successCount).toBe(1)
      expect(metrics2.failureCount).toBe(0)
    })

    it('returns metrics for all tools', () => {
      tracker.recordSuccess('tool-a', 100)
      tracker.recordSuccess('tool-b', 200)
      tracker.recordFailure('tool-c', 300)

      const allMetrics = tracker.getMetrics() as Map<string, any>
      expect(allMetrics.size).toBe(3)
      expect(allMetrics.has('tool-a')).toBe(true)
      expect(allMetrics.has('tool-b')).toBe(true)
      expect(allMetrics.has('tool-c')).toBe(true)
    })
  })

  describe('default configuration', () => {
    it('uses default config when not provided', () => {
      const defaultTracker = new ToolReliabilityTracker(rootLogger.child('test'))
      
      // Record 5 failures (default threshold)
      for (let i = 0; i < 5; i++) {
        defaultTracker.recordFailure('default-tool', 100)
      }

      // Should be open with default threshold
      expect(defaultTracker.canExecute('default-tool')).toBe(false)
    })
  })
})
