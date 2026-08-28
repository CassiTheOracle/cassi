/**
 * Tests for Trace Replay Engine (B3).
 */

import { describe, it, expect, beforeEach } from 'vitest'

import { TraceReplayEngine } from './trace-replay.js'
import type {
  TraceRetrievalQuery,
  RankedTrace,
  TraceReplayConfig,
} from './trace-replay-types.js'
import { DEFAULT_TRACE_REPLAY_CONFIG } from './trace-replay-types.js'
import type { ReasoningRecord, ReasoningMomentum } from './types.js'
import type { ILogger } from '@cassicore/foundation'


function makeLogger(): ILogger {
  return {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => makeLogger(),
  } as any
}

function makeRecord(overrides: Partial<ReasoningRecord> & { id?: string; text?: string; concepts?: string[] } = {}): ReasoningRecord {
  return {
    id: overrides.id ?? `rec-${Math.random().toString(36).slice(2, 8)}`,
    turn: overrides.turn ?? 1,
    text: overrides.text ?? 'Default reasoning text for testing purposes.',
    concepts: overrides.concepts ?? ['default-concept'],
    recordedAt: overrides.recordedAt ?? new Date().toISOString(),
    momentum: overrides.momentum ?? {
      confidence: 0.7,
      novelty: 0.3,
      turnsInDirection: 3,
    } as ReasoningMomentum,
    ...overrides,
  } as ReasoningRecord
}

function makeQuery(overrides: Partial<TraceRetrievalQuery> = {}): TraceRetrievalQuery {
  return {
    current: {
      text: 'Test query about authentication patterns',
      conceptsExtracted: ['auth', 'token', 'validation'],
      affect: { valence: 0.3, arousal: 0.4 },
      activeCompositions: [],
    },
    topK: 5,
    ...overrides,
  }
}


describe('TraceReplayEngine', () => {
  let engine: TraceReplayEngine
  let logger: ILogger

  beforeEach(() => {
    logger = makeLogger()
    engine = new TraceReplayEngine({}, logger)
  })

  describe('retrieveSimilarTraces', () => {
    it('returns empty when disabled', () => {
      const disabled = new TraceReplayEngine({ enabled: false }, logger)
      const log = [makeRecord({ text: 'auth token validation' })]
      const results = disabled.retrieveSimilarTraces(makeQuery(), log)
      expect(results).toHaveLength(0)
    })

    it('finds concept-overlapping traces', () => {
      const log = [
        makeRecord({ text: 'Auth token validation logic', concepts: ['auth', 'token', 'validation', 'jwt'] }),
        makeRecord({ text: 'Database migration schema changes', concepts: ['database', 'schema', 'migration'] }),
      ]
      const results = engine.retrieveSimilarTraces(makeQuery(), log)
      expect(results.length).toBeGreaterThanOrEqual(1)
      expect(results[0].record.concepts).toContain('auth')
      expect(results[0].similarity).toBeGreaterThan(0)
    })

    it('ranks by similarity descending', () => {
      const log = [
        makeRecord({ text: 'Auth token validation with JWT', concepts: ['auth', 'token', 'validation'] }),
        makeRecord({ text: 'Database schema', concepts: ['database'] }),
        makeRecord({ text: 'Authentication patterns in microservices', concepts: ['auth', 'token'] }),
      ]
      const results = engine.retrieveSimilarTraces(makeQuery(), log)
      for (let i = 1; i < results.length; i++) {
        expect(results[i - 1].similarity).toBeGreaterThanOrEqual(results[i].similarity)
      }
    })

    it('respects topK limit', () => {
      const log = Array.from({ length: 20 }, (_, i) =>
        makeRecord({ text: `Auth record ${i}`, concepts: ['auth', 'token'] }),
      )
      const results = engine.retrieveSimilarTraces(makeQuery({ topK: 3 }), log)
      expect(results.length).toBeLessThanOrEqual(3)
    })

    it('applies quality floor filter', () => {
      // Pre-score one record with low quality
      const log = [
        makeRecord({ text: 'Auth token validation with JWT', concepts: ['auth', 'token', 'validation'] }),
      ]
      // Run quality pass so records get scored
      engine.runQualityScoringPass(log)
      // With a very high quality floor, no results should pass
      const results = engine.retrieveSimilarTraces(
        makeQuery({ qualityFloor: 0.99 }),
        log,
      )
      // All records should be filtered out (quality composite < 0.99)
      expect(results.every(r => (r.quality?.composite ?? 0.5) >= 0.99)).toBe(true)
    })

    it('filters records with empty text', () => {
      const log = [
        makeRecord({ text: '', concepts: ['auth'] }),
        makeRecord({ text: 'Auth token validation', concepts: ['auth', 'token'] }),
      ]
      const results = engine.retrieveSimilarTraces(makeQuery(), log)
      expect(results.every(r => r.record.text.length >= 10)).toBe(true)
    })

    it('filters distressed records (B3.W1)', () => {
      const log = [
        makeRecord({
          text: 'Auth token validation failed catastrophically',
          concepts: ['auth', 'token'],
          affectSnapshot: { valence: -0.8, arousal: 0.9 },
        } as any),
        makeRecord({
          text: 'Auth token validation works well',
          concepts: ['auth', 'token'],
          affectSnapshot: { valence: 0.5, arousal: 0.3 },
        } as any),
      ]
      const results = engine.retrieveSimilarTraces(makeQuery(), log)
      // Distressed record should be filtered
      expect(results.every(r => {
        const aff = (r.record as any).affectSnapshot
        return !aff || !(aff.valence < -0.5 && aff.arousal > 0.7)
      })).toBe(true)
    })

    it('returns signal breakdown in results', () => {
      const log = [makeRecord({ text: 'Auth token validation', concepts: ['auth', 'token'] })]
      const results = engine.retrieveSimilarTraces(makeQuery(), log)
      if (results.length > 0) {
        expect(results[0].signalBreakdown).toHaveProperty('conceptOverlap')
        expect(results[0].signalBreakdown).toHaveProperty('textSimilarity')
        expect(results[0].signalBreakdown).toHaveProperty('affectProximity')
        expect(results[0].signalBreakdown).toHaveProperty('compositionOverlap')
      }
    })
  })

  describe('quality scoring', () => {
    it('scores records with enough subsequent context', () => {
      const log = Array.from({ length: 10 }, (_, i) =>
        makeRecord({ text: `Reasoning step ${i}`, concepts: [`concept-${i}`] }),
      )
      const scored = engine.runQualityScoringPass(log)
      // With minAge=5, only the first 5 records should be scored
      expect(scored).toBeGreaterThan(0)
    })

    it('does not re-score already-scored records', () => {
      const log = Array.from({ length: 10 }, (_, i) =>
        makeRecord({ text: `Reasoning step ${i}`, concepts: [`concept-${i}`] }),
      )
      engine.runQualityScoringPass(log)
      const secondPass = engine.runQualityScoringPass(log)
      expect(secondPass).toBe(0)
    })

    it('quality scores are in valid range', () => {
      const log = Array.from({ length: 10 }, (_, i) =>
        makeRecord({ text: `Reasoning step ${i}`, concepts: [`concept-${i}`] }),
      )
      engine.runQualityScoringPass(log)
      for (const record of log) {
        const quality = engine.getQuality(record)
        if (quality) {
          expect(quality.composite).toBeGreaterThanOrEqual(0)
          expect(quality.composite).toBeLessThanOrEqual(1)
          expect(quality.internal).toBeGreaterThanOrEqual(0)
          expect(quality.internal).toBeLessThanOrEqual(1)
          expect(quality.affectTrajectory).toBeGreaterThanOrEqual(0)
          expect(quality.affectTrajectory).toBeLessThanOrEqual(1)
        }
      }
    })
  })

  describe('replay scheduling', () => {
    function makeRankedTrace(overrides: Partial<RankedTrace> = {}): RankedTrace {
      return {
        record: makeRecord({ text: 'Auth token validation', concepts: ['auth'] }),
        similarity: 0.8,
        signalBreakdown: {
          conceptOverlap: 0.7,
          textSimilarity: 0.8,
          affectProximity: 0.9,
          compositionOverlap: 0.5,
        },
        quality: null,
        ...overrides,
      }
    }

    it('schedules context replay', () => {
      const trace = makeRankedTrace()
      engine.scheduleContextReplay(trace)
      const replay = engine.consumeScheduledReplay()
      expect(replay).not.toBeNull()
      expect(replay!.mode).toBe('context')
      expect(replay!.trace).toBe(trace)
    })

    it('schedules state replay', () => {
      const trace = makeRankedTrace()
      engine.scheduleStateReplay(trace)
      const replay = engine.consumeScheduledReplay()
      expect(replay).not.toBeNull()
      expect(replay!.mode).toBe('state')
    })

    it('consumes scheduled replay (single-use)', () => {
      engine.scheduleContextReplay(makeRankedTrace())
      const first = engine.consumeScheduledReplay()
      const second = engine.consumeScheduledReplay()
      expect(first).not.toBeNull()
      expect(second).toBeNull()
    })

    it('cancels scheduled replay', () => {
      engine.scheduleContextReplay(makeRankedTrace())
      engine.cancelScheduledReplay()
      expect(engine.consumeScheduledReplay()).toBeNull()
    })

    it('shouldAutoReplay respects thresholds', () => {
      const goodTrace = makeRankedTrace({
        similarity: 0.8,
        quality: { internal: 0.7, affectTrajectory: 0.8, externalFeedback: 0.6, composite: 0.75, computedAt: 'now' },
      })
      const badTrace = makeRankedTrace({
        similarity: 0.3,
        quality: { internal: 0.3, affectTrajectory: 0.3, externalFeedback: 0.3, composite: 0.3, computedAt: 'now' },
      })

      // Default: auto-replay disabled
      expect(engine.shouldAutoReplay(goodTrace)).toBe(false)

      const autoEngine = new TraceReplayEngine({ autoReplayEnabled: true }, logger)
      expect(autoEngine.shouldAutoReplay(goodTrace)).toBe(true)
      expect(autoEngine.shouldAutoReplay(badTrace)).toBe(false)
      expect(autoEngine.shouldAutoReplay(undefined)).toBe(false)
    })
  })

  describe('renderReplayContext', () => {
    it('renders context-mode replay with metadata', () => {
      const trace: RankedTrace = {
        record: makeRecord({ text: 'Authentication middleware handles JWT validation' }),
        similarity: 0.85,
        signalBreakdown: { conceptOverlap: 0.7, textSimilarity: 0.8, affectProximity: 0.9, compositionOverlap: 0.5 },
        quality: null,
      }
      engine.scheduleContextReplay(trace)
      const replay = engine.consumeScheduledReplay()!
      const rendered = engine.renderReplayContext(replay, 600)
      expect(rendered).toContain('Replayed trace')
      expect(rendered).toContain('0.85')
    })

    it('renders state-mode replay as empty string', () => {
      const trace: RankedTrace = {
        record: makeRecord(),
        similarity: 0.7,
        signalBreakdown: { conceptOverlap: 0.5, textSimilarity: 0.5, affectProximity: 0.5, compositionOverlap: 0.5 },
        quality: null,
      }
      engine.scheduleStateReplay(trace)
      const replay = engine.consumeScheduledReplay()!
      const rendered = engine.renderReplayContext(replay, 600)
      expect(rendered).toBe('')
    })

    it('truncates to budget', () => {
      const trace: RankedTrace = {
        record: makeRecord({ text: 'A'.repeat(500) }),
        similarity: 0.7,
        signalBreakdown: { conceptOverlap: 0.5, textSimilarity: 0.5, affectProximity: 0.5, compositionOverlap: 0.5 },
        quality: null,
      }
      engine.scheduleContextReplay(trace, { budgetChars: 50 })
      const replay = engine.consumeScheduledReplay()!
      const rendered = engine.renderReplayContext(replay, 50)
      expect(rendered.length).toBeLessThanOrEqual(50)
    })
  })

  describe('config', () => {
    it('returns current config', () => {
      const config = engine.getConfig()
      expect(config.enabled).toBe(true)
      expect(config.autoReplayEnabled).toBe(false)
    })

    it('updates config', () => {
      engine.updateConfig({ autoReplayEnabled: true })
      expect(engine.getConfig().autoReplayEnabled).toBe(true)
    })
  })
})
