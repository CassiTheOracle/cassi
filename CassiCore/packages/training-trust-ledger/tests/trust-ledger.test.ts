import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  betaMean,
  betaVariance,
  betaConfidence,
  trustToAutonomyLevel,
  DEFAULT_TRUST_LEDGER_CONFIG,
  type TrustEvidence,
} from '../src/trust-ledger/types.js'
import { TrustLedger } from '../src/trust-ledger/index.js'


function createMockLogger() {
  return {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    child: vi.fn().mockReturnThis(),
  }
}

function createMockEventBus() {
  return {
    emit: vi.fn(),
    on: vi.fn(() => vi.fn()),
    onAll: vi.fn(() => vi.fn()),
    off: vi.fn(),
  }
}

// Type Helpers

describe('Trust Ledger Types', () => {
  describe('betaMean', () => {
    it('returns 0.5 for uninformative prior (1, 1)', () => {
      expect(betaMean(1, 1)).toBe(0.5)
    })

    it('returns higher for more successes', () => {
      expect(betaMean(10, 1)).toBeGreaterThan(0.5)
    })

    it('returns lower for more failures', () => {
      expect(betaMean(1, 10)).toBeLessThan(0.5)
    })

    it('converges to true rate with lots of evidence', () => {
      // 90 successes, 10 failures → should be ~0.9
      expect(betaMean(91, 11)).toBeCloseTo(0.891, 2)
    })
  })

  describe('betaVariance', () => {
    it('is highest for uninformative prior', () => {
      const uninformative = betaVariance(1, 1)
      const informed = betaVariance(10, 10)
      expect(uninformative).toBeGreaterThan(informed)
    })

    it('decreases with more evidence', () => {
      const v1 = betaVariance(5, 5)
      const v2 = betaVariance(50, 50)
      const v3 = betaVariance(500, 500)
      expect(v1).toBeGreaterThan(v2)
      expect(v2).toBeGreaterThan(v3)
    })
  })

  describe('betaConfidence', () => {
    it('is 0 for uninformative prior (1, 1)', () => {
      expect(betaConfidence(1, 1)).toBe(0)
    })

    it('increases with evidence', () => {
      const c1 = betaConfidence(5, 5)
      const c2 = betaConfidence(50, 50)
      expect(c2).toBeGreaterThan(c1)
    })

    it('is clamped to [0, 1]', () => {
      expect(betaConfidence(1000, 1000)).toBeLessThanOrEqual(1)
      expect(betaConfidence(1000, 1000)).toBeGreaterThanOrEqual(0)
    })
  })

  describe('trustToAutonomyLevel', () => {
    it('maps low trust to supervised', () => {
      expect(trustToAutonomyLevel(0.1)).toBe('supervised')
      expect(trustToAutonomyLevel(0.29)).toBe('supervised')
    })

    it('maps moderate trust to guided', () => {
      expect(trustToAutonomyLevel(0.3)).toBe('guided')
      expect(trustToAutonomyLevel(0.5)).toBe('guided')
    })

    it('maps good trust to autonomous', () => {
      expect(trustToAutonomyLevel(0.6)).toBe('autonomous')
      expect(trustToAutonomyLevel(0.8)).toBe('autonomous')
    })

    it('maps high trust to trusted', () => {
      expect(trustToAutonomyLevel(0.85)).toBe('trusted')
      expect(trustToAutonomyLevel(0.99)).toBe('trusted')
    })
  })
})

// Trust Ledger Module

describe('TrustLedger', () => {
  let ledger: TrustLedger
  let logger: ReturnType<typeof createMockLogger>
  let mockBus: ReturnType<typeof createMockEventBus>
  let emittedEvents: any[]

  beforeEach(() => {
    logger = createMockLogger()
    ledger = new TrustLedger(logger as any)
    emittedEvents = []
    mockBus = createMockEventBus()
    mockBus.emit.mockImplementation((event: any) => emittedEvents.push(event))
    ledger.onEventBus(mockBus as any)
  })

  describe('domain creation', () => {
    it('creates a new domain with prior score of 0.5', () => {
      const score = ledger.getOrCreateDomainScore('file-read')
      expect(score.domain).toBe('file-read')
      expect(score.score).toBeCloseTo(0.5, 5)
      expect(score.evidenceCount).toBe(0)
    })

    it('emits trust:domain-created event', () => {
      ledger.getOrCreateDomainScore('file-write')
      const event = emittedEvents.find(e => e.type === 'trust:domain-created')
      expect(event).toBeDefined()
      expect(event.domain).toBe('file-write')
    })

    it('returns existing domain without creating duplicate', () => {
      const first = ledger.getOrCreateDomainScore('shell-execution')
      const second = ledger.getOrCreateDomainScore('shell-execution')
      expect(first.score).toBe(second.score)
      // Only one domain-created event
      const createEvents = emittedEvents.filter(e => e.type === 'trust:domain-created')
      expect(createEvents.length).toBe(1)
    })
  })

  describe('evidence recording', () => {
    it('increases trust score on success', () => {
      ledger.getOrCreateDomainScore('file-read')
      const before = ledger.getDomainScore('file-read')!.score

      ledger.recordEvidence({
        domain: 'file-read',
        success: true,
        weight: 1.0,
        source: 'test',
        description: 'successful read',
        timestamp: Date.now(),
      })

      const after = ledger.getDomainScore('file-read')!.score
      expect(after).toBeGreaterThan(before)
    })

    it('decreases trust score on failure', () => {
      ledger.getOrCreateDomainScore('shell-execution')
      const before = ledger.getDomainScore('shell-execution')!.score

      ledger.recordEvidence({
        domain: 'shell-execution',
        success: false,
        weight: 1.0,
        source: 'test',
        description: 'command failed',
        timestamp: Date.now(),
      })

      const after = ledger.getDomainScore('shell-execution')!.score
      expect(after).toBeLessThan(before)
    })

    it('respects evidence weight — heavier evidence has more impact', () => {
      ledger.getOrCreateDomainScore('file-write')

      // Apply light positive evidence
      ledger.recordEvidence({
        domain: 'file-write',
        success: true,
        weight: 0.5,
        source: 'test',
        description: 'light success',
        timestamp: Date.now(),
      })
      const lightScore = ledger.getDomainScore('file-write')!.score

      // Reset by creating a new ledger
      const logger2 = createMockLogger()
      const ledger2 = new TrustLedger(logger2 as any)
      const mockBus2 = createMockEventBus()
      ledger2.onEventBus(mockBus2 as any)
      ledger2.getOrCreateDomainScore('file-write')

      // Apply heavy positive evidence
      ledger2.recordEvidence({
        domain: 'file-write',
        success: true,
        weight: 3.0,
        source: 'test',
        description: 'heavy success',
        timestamp: Date.now(),
      })
      const heavyScore = ledger2.getDomainScore('file-write')!.score

      expect(heavyScore).toBeGreaterThan(lightScore)
    })

    it('caps evidence weight at maxEvidenceWeight', () => {
      ledger.getOrCreateDomainScore('file-delete')

      // Try to apply excessively heavy evidence
      ledger.recordEvidence({
        domain: 'file-delete',
        success: true,
        weight: 100.0, // Way above max
        source: 'test',
        description: 'extreme evidence',
        timestamp: Date.now(),
      })

      const score = ledger.getDomainScore('file-delete')!
      // With max weight 3.0, alpha should be 1.0 + 3.0 = 4.0, not 101.0
      expect(score.alpha).toBeLessThanOrEqual(1.0 + DEFAULT_TRUST_LEDGER_CONFIG.maxEvidenceWeight + 1)
    })

    it('emits trust:score-updated and trust:outcome-recorded events', () => {
      ledger.getOrCreateDomainScore('git-operations')
      emittedEvents.length = 0 // Clear creation events

      ledger.recordEvidence({
        domain: 'git-operations',
        success: true,
        weight: 1.0,
        source: 'test',
        description: 'clean commit',
        timestamp: Date.now(),
      })

      expect(emittedEvents.some(e => e.type === 'trust:score-updated')).toBe(true)
      expect(emittedEvents.some(e => e.type === 'trust:outcome-recorded')).toBe(true)
    })

    it('auto-creates domain on first evidence', () => {
      expect(ledger.getDomainScore('network-fetch')).toBeUndefined()

      ledger.recordEvidence({
        domain: 'network-fetch',
        success: true,
        weight: 1.0,
        source: 'test',
        description: 'first fetch',
        timestamp: Date.now(),
      })

      expect(ledger.getDomainScore('network-fetch')).toBeDefined()
    })

    it('factors in consequence accuracy', () => {
      // High accuracy → bonus weight
      ledger.getOrCreateDomainScore('file-read')
      ledger.recordEvidence({
        domain: 'file-read',
        success: true,
        weight: 1.0,
        source: 'test',
        description: 'accurate prediction',
        consequenceAccuracy: 0.95,
        timestamp: Date.now(),
      })
      const highAccuracyScore = ledger.getDomainScore('file-read')!.score

      // Reset
      const ledger2 = new TrustLedger(createMockLogger() as any)
      const bus2 = createMockEventBus()
      ledger2.onEventBus(bus2 as any)
      ledger2.getOrCreateDomainScore('file-read')
      ledger2.recordEvidence({
        domain: 'file-read',
        success: true,
        weight: 1.0,
        source: 'test',
        description: 'inaccurate prediction',
        consequenceAccuracy: 0.1,
        timestamp: Date.now(),
      })
      const lowAccuracyScore = ledger2.getDomainScore('file-read')!.score

      // High accuracy should produce higher trust than low accuracy
      expect(highAccuracyScore).toBeGreaterThan(lowAccuracyScore)
    })
  })

  describe('Bayesian convergence', () => {
    it('converges toward true success rate with many observations', () => {
      ledger.getOrCreateDomainScore('file-read')

      // Simulate 90% success rate: 90 successes, 10 failures
      for (let i = 0; i < 90; i++) {
        ledger.recordEvidence({
          domain: 'file-read',
          success: true,
          weight: 1.0,
          source: 'test',
          description: 'success',
          timestamp: Date.now(),
        })
      }
      for (let i = 0; i < 10; i++) {
        ledger.recordEvidence({
          domain: 'file-read',
          success: false,
          weight: 1.0,
          source: 'test',
          description: 'failure',
          timestamp: Date.now(),
        })
      }

      const score = ledger.getDomainScore('file-read')!
      // Score should be approximately 0.9 (±0.05 accounting for prior)
      expect(score.score).toBeGreaterThan(0.85)
      expect(score.score).toBeLessThan(0.95)
      expect(score.confidence).toBeGreaterThan(0.8)
    })

    it('single failure after few successes drops trust significantly', () => {
      ledger.getOrCreateDomainScore('shell-execution')

      // 3 successes
      for (let i = 0; i < 3; i++) {
        ledger.recordEvidence({
          domain: 'shell-execution',
          success: true,
          weight: 1.0,
          source: 'test',
          description: 'success',
          timestamp: Date.now(),
        })
      }
      const beforeFailure = ledger.getDomainScore('shell-execution')!.score

      // 1 failure
      ledger.recordEvidence({
        domain: 'shell-execution',
        success: false,
        weight: 1.0,
        source: 'test',
        description: 'failure',
        timestamp: Date.now(),
      })
      const afterFailure = ledger.getDomainScore('shell-execution')!.score

      // Should drop noticeably (> 5%)
      expect(beforeFailure - afterFailure).toBeGreaterThan(0.05)
    })

    it('single failure after many successes barely dents trust', () => {
      ledger.getOrCreateDomainScore('file-read')

      // 100 successes
      for (let i = 0; i < 100; i++) {
        ledger.recordEvidence({
          domain: 'file-read',
          success: true,
          weight: 1.0,
          source: 'test',
          description: 'success',
          timestamp: Date.now(),
        })
      }
      const beforeFailure = ledger.getDomainScore('file-read')!.score

      // 1 failure
      ledger.recordEvidence({
        domain: 'file-read',
        success: false,
        weight: 1.0,
        source: 'test',
        description: 'failure',
        timestamp: Date.now(),
      })
      const afterFailure = ledger.getDomainScore('file-read')!.score

      // Drop should be tiny (< 2%)
      expect(beforeFailure - afterFailure).toBeLessThan(0.02)
    })
  })

  describe('getSummary()', () => {
    it('returns empty summary with no domains', () => {
      const summary = ledger.getSummary()
      expect(summary.domains.size).toBe(0)
      expect(summary.overallScore).toBe(0.5)
      expect(summary.autonomyLevel).toBe('guided')
    })

    it('computes weighted average across domains', () => {
      // Create two domains with different trust levels
      ledger.getOrCreateDomainScore('file-read')
      for (let i = 0; i < 10; i++) {
        ledger.recordEvidence({
          domain: 'file-read', success: true, weight: 1.0, source: 'test', description: 'ok', timestamp: Date.now(),
        })
      }

      ledger.getOrCreateDomainScore('shell-execution')
      for (let i = 0; i < 10; i++) {
        ledger.recordEvidence({
          domain: 'shell-execution', success: false, weight: 1.0, source: 'test', description: 'fail', timestamp: Date.now(),
        })
      }

      const summary = ledger.getSummary()
      expect(summary.domains.size).toBe(2)
      // Overall should be between the two extremes
      expect(summary.overallScore).toBeGreaterThan(0.2)
      expect(summary.overallScore).toBeLessThan(0.8)
      expect(summary.strongestDomain?.domain).toBe('file-read')
      expect(summary.weakestDomain?.domain).toBe('shell-execution')
    })
  })

  describe('getStats()', () => {
    it('tracks evidence and domain counts', () => {
      ledger.recordEvidence({
        domain: 'file-read', success: true, weight: 1.0, source: 'test', description: 'ok', timestamp: Date.now(),
      })
      ledger.recordEvidence({
        domain: 'file-write', success: false, weight: 1.0, source: 'test', description: 'fail', timestamp: Date.now(),
      })

      const stats = ledger.getStats()
      expect(stats.domainCount).toBe(2)
      expect(stats.totalEvidence).toBe(2)
    })
  })
})
