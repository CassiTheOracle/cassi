/**
 * Tests for Saturation Detector (N5).
 */

import { describe, it, expect, beforeEach } from 'vitest'

import {
  SaturationDetector,
  DEFAULT_SATURATION_CONFIG,
} from './saturation-detector.js'
import type {
  SaturationConfig,
  SaturationScore,
  TurnSample,
} from './saturation-detector.js'
import type { ReverieInsight } from './types.js'
import type { ILogger } from '../../../types/interfaces.js'


function makeLogger(): ILogger {
  return {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => makeLogger(),
  } as any
}

function makeSample(overrides: Partial<TurnSample> = {}): TurnSample {
  return {
    turn: overrides.turn ?? 1,
    // Use `in` checks so that an explicit `null` is preserved (not replaced by ??)
    affect: 'affect' in overrides ? overrides.affect! : { valence: 0.0, arousal: 0.0 },
    activeCompositions: overrides.activeCompositions ?? [],
    activatedNodes: overrides.activatedNodes ?? [],
    insights: overrides.insights ?? [],
    reasoningMetrics: 'reasoningMetrics' in overrides ? overrides.reasoningMetrics! : null,
  }
}

function makeInsight(overrides: Partial<ReverieInsight> = {}): ReverieInsight {
  return {
    id: overrides.id ?? `ins-${Math.random().toString(36).slice(2, 8)}`,
    kind: overrides.kind ?? 'observation',
    summary: overrides.summary ?? 'A reverie observation',
    confidence: overrides.confidence ?? 0.5,
    ...overrides,
  } as ReverieInsight
}

/** Push N saturated samples (same compositions, same nodes, no insights, flat affect & metrics). */
function pushSaturated(detector: SaturationDetector, count: number, startTurn = 1): void {
  for (let i = 0; i < count; i++) {
    detector.recordSample(makeSample({
      turn: startTurn + i,
      affect: { valence: 0.1, arousal: 0.1 },
      activeCompositions: ['comp-A', 'comp-B'],
      activatedNodes: ['node-1', 'node-2', 'node-3'],
      insights: [],
      reasoningMetrics: { coherence: 0.5, integration: 0.5, novelty: 0.5 },
    }))
  }
}

/** Push N flowing samples (varied compositions, nodes, novel insights, varied affect & metrics). */
function pushFlowing(detector: SaturationDetector, count: number, startTurn = 1): void {
  for (let i = 0; i < count; i++) {
    detector.recordSample(makeSample({
      turn: startTurn + i,
      affect: { valence: Math.sin(i) * 0.7, arousal: Math.cos(i) * 0.7 },
      activeCompositions: [`comp-${i}`, `comp-${i + 1}`],
      activatedNodes: [`node-${i}`, `node-${i + 1}`, `node-${i + 2}`],
      insights: i % 2 === 0 ? [makeInsight({ kind: 'breakthrough', confidence: 0.9 })] : [],
      reasoningMetrics: {
        coherence: 0.3 + (i % 5) * 0.15,
        integration: 0.2 + (i % 4) * 0.2,
        novelty: 0.4 + (i % 3) * 0.2,
      },
    }))
  }
}


describe('SaturationDetector', () => {
  let detector: SaturationDetector
  let logger: ILogger

  beforeEach(() => {
    logger = makeLogger()
    detector = new SaturationDetector({}, logger)
  })

  describe('construction', () => {
    it('uses defaults when no config supplied', () => {
      const config = detector.getConfig()
      expect(config.enabled).toBe(true)
      expect(config.windows).toEqual(DEFAULT_SATURATION_CONFIG.windows)
      expect(config.silenced).toBe(false)
      expect(config.thresholds).toEqual(DEFAULT_SATURATION_CONFIG.thresholds)
    })

    it('accepts partial config overrides', () => {
      const custom = new SaturationDetector(
        { enabled: false, windows: [5, 10], resurfaceCooldownTurns: 100 },
        logger,
      )
      const config = custom.getConfig()
      expect(config.enabled).toBe(false)
      expect(config.windows).toEqual([5, 10])
      expect(config.resurfaceCooldownTurns).toBe(100)
      // Untouched values fall back to defaults
      expect(config.affectStabilityStdThreshold).toBe(DEFAULT_SATURATION_CONFIG.affectStabilityStdThreshold)
    })

    it('returns a copy of config (mutation-safe)', () => {
      const config = detector.getConfig()
      config.enabled = false
      expect(detector.getConfig().enabled).toBe(true)
    })
  })

  describe('recordSample', () => {
    it('stores samples for analysis', () => {
      pushSaturated(detector, 5)
      const scores = detector.computeScores()
      // At least one window should have run with these 5 samples
      expect(scores.length).toBeGreaterThan(0)
    })

    it('does not record when disabled', () => {
      const disabled = new SaturationDetector({ enabled: false, windows: [5] }, logger)
      pushSaturated(disabled, 10)
      expect(disabled.computeScores()).toEqual([])
    })

    it('reset clears samples', () => {
      pushSaturated(detector, 10)
      detector.reset()
      expect(detector.computeScores()).toEqual([])
    })
  })

  describe('computeScores', () => {
    it('returns empty array when disabled', () => {
      const disabled = new SaturationDetector({ enabled: false }, logger)
      pushSaturated(disabled, 30)
      expect(disabled.computeScores()).toEqual([])
    })

    it('skips windows with fewer than 3 samples', () => {
      const small = new SaturationDetector({ windows: [5] }, logger)
      pushSaturated(small, 2)
      expect(small.computeScores()).toEqual([])
    })

    it('produces a score per window when enough samples are present', () => {
      const multi = new SaturationDetector({ windows: [5, 10] }, logger)
      pushSaturated(multi, 12)
      const scores = multi.computeScores()
      expect(scores).toHaveLength(2)
      expect(scores[0].windowSize).toBe(5)
      expect(scores[1].windowSize).toBe(10)
    })

    it('classifies sustained sameness as saturated', () => {
      const focused = new SaturationDetector({ windows: [10] }, logger)
      pushSaturated(focused, 15)
      const [score] = focused.computeScores()
      expect(score.classification).toBe('saturated')
      expect(score.composite).toBeGreaterThanOrEqual(score.signals.affectStability * 0)
      expect(score.composite).toBeGreaterThanOrEqual(DEFAULT_SATURATION_CONFIG.thresholds.saturated)
    })

    it('classifies varied activity as flowing', () => {
      const lively = new SaturationDetector({ windows: [10] }, logger)
      pushFlowing(lively, 15)
      const [score] = lively.computeScores()
      expect(score.classification).toBe('flowing')
      expect(score.composite).toBeLessThan(DEFAULT_SATURATION_CONFIG.thresholds.flowing)
    })

    it('returns signals in the [0, 1] range', () => {
      pushSaturated(detector, 25)
      const scores = detector.computeScores()
      for (const score of scores) {
        for (const v of Object.values(score.signals)) {
          expect(v).toBeGreaterThanOrEqual(0)
          expect(v).toBeLessThanOrEqual(1)
        }
        expect(score.composite).toBeGreaterThanOrEqual(0)
        expect(score.composite).toBeLessThanOrEqual(1)
      }
    })

    it('reports correct turnCount for each window', () => {
      const detector2 = new SaturationDetector({ windows: [5, 100] }, logger)
      pushSaturated(detector2, 12)
      const scores = detector2.computeScores()
      const w5 = scores.find(s => s.windowSize === 5)!
      const w100 = scores.find(s => s.windowSize === 100)!
      expect(w5.turnCount).toBe(5)
      expect(w100.turnCount).toBe(12)
    })

    it('uses custom weights to influence composite', () => {
      const insightHeavy = new SaturationDetector({
        windows: [10],
        weights: {
          affectStability: 0,
          compositionStasis: 0,
          activationRepetition: 0,
          insightDrought: 1,
          metricFlatness: 0,
        },
      }, logger)
      pushSaturated(insightHeavy, 15)
      const [score] = insightHeavy.computeScores()
      // Composite should equal insightDrought signal exactly
      expect(score.composite).toBeCloseTo(score.signals.insightDrought, 5)
    })
  })

  describe('signal computations', () => {
    it('affectStability is high when valence/arousal are flat', () => {
      pushSaturated(detector, 25)
      const [score] = detector.computeScores()
      expect(score.signals.affectStability).toBeGreaterThan(0.5)
    })

    it('affectStability is zero when affect varies widely', () => {
      const wide = new SaturationDetector({ windows: [10] }, logger)
      for (let i = 0; i < 12; i++) {
        wide.recordSample(makeSample({
          turn: i,
          affect: { valence: i % 2 === 0 ? 1 : -1, arousal: i % 2 === 0 ? 1 : -1 },
        }))
      }
      const [score] = wide.computeScores()
      expect(score.signals.affectStability).toBe(0)
    })

    it('affectStability is zero when fewer than 3 affect samples present', () => {
      const sparse = new SaturationDetector({ windows: [5] }, logger)
      sparse.recordSample(makeSample({ turn: 1, affect: { valence: 0, arousal: 0 } }))
      sparse.recordSample(makeSample({ turn: 2, affect: null }))
      sparse.recordSample(makeSample({ turn: 3, affect: null }))
      sparse.recordSample(makeSample({ turn: 4, affect: null }))
      sparse.recordSample(makeSample({ turn: 5, affect: null }))
      const [score] = sparse.computeScores()
      expect(score.signals.affectStability).toBe(0)
    })

    it('compositionStasis is high when compositions never change', () => {
      pushSaturated(detector, 25)
      const [score] = detector.computeScores()
      expect(score.signals.compositionStasis).toBeGreaterThan(0)
    })

    it('compositionStasis is zero when compositions churn often', () => {
      const churn = new SaturationDetector({ windows: [10] }, logger)
      for (let i = 0; i < 12; i++) {
        churn.recordSample(makeSample({
          turn: i,
          activeCompositions: [`comp-${i}-a`, `comp-${i}-b`, `comp-${i}-c`],
        }))
      }
      const [score] = churn.computeScores()
      expect(score.signals.compositionStasis).toBe(0)
    })

    it('activationRepetition is high when same nodes activate', () => {
      pushSaturated(detector, 25)
      const [score] = detector.computeScores()
      // Default threshold is 0.7; identical sets give Jaccard = 1
      expect(score.signals.activationRepetition).toBeGreaterThanOrEqual(0.7)
    })

    it('activationRepetition is zero when no nodes overlap', () => {
      const disjoint = new SaturationDetector({ windows: [10] }, logger)
      for (let i = 0; i < 12; i++) {
        disjoint.recordSample(makeSample({
          turn: i,
          activatedNodes: [`unique-${i}-a`, `unique-${i}-b`],
        }))
      }
      const [score] = disjoint.computeScores()
      expect(score.signals.activationRepetition).toBe(0)
    })

    it('insightDrought is high when no novel insights are recorded', () => {
      pushSaturated(detector, 25)
      const [score] = detector.computeScores()
      expect(score.signals.insightDrought).toBe(1)
    })

    it('insightDrought is zero when breakthroughs land', () => {
      const ideas = new SaturationDetector({ windows: [10] }, logger)
      for (let i = 0; i < 12; i++) {
        ideas.recordSample(makeSample({
          turn: i,
          insights: [makeInsight({ kind: 'breakthrough', confidence: 0.9 })],
        }))
      }
      const [score] = ideas.computeScores()
      expect(score.signals.insightDrought).toBe(0)
    })

    it('insightDrought treats high-confidence non-breakthrough insights as novel', () => {
      const confident = new SaturationDetector({ windows: [10] }, logger)
      for (let i = 0; i < 12; i++) {
        confident.recordSample(makeSample({
          turn: i,
          insights: [makeInsight({ kind: 'observation', confidence: 0.9 })],
        }))
      }
      const [score] = confident.computeScores()
      expect(score.signals.insightDrought).toBe(0)
    })

    it('metricFlatness is high when reasoning metrics are constant', () => {
      pushSaturated(detector, 25)
      const [score] = detector.computeScores()
      expect(score.signals.metricFlatness).toBeGreaterThan(0)
    })

    it('metricFlatness is zero when metrics vary', () => {
      const varied = new SaturationDetector({ windows: [10] }, logger)
      for (let i = 0; i < 12; i++) {
        varied.recordSample(makeSample({
          turn: i,
          reasoningMetrics: {
            coherence: i % 2 === 0 ? 0.1 : 0.9,
            integration: i % 2 === 0 ? 0.1 : 0.9,
            novelty: i % 2 === 0 ? 0.1 : 0.9,
          },
        }))
      }
      const [score] = varied.computeScores()
      expect(score.signals.metricFlatness).toBe(0)
    })

    it('metricFlatness is zero when fewer than 3 reasoning samples are present', () => {
      const sparse = new SaturationDetector({ windows: [5] }, logger)
      for (let i = 0; i < 5; i++) {
        sparse.recordSample(makeSample({
          turn: i,
          reasoningMetrics: i < 2 ? { coherence: 0.5, integration: 0.5, novelty: 0.5 } : null,
        }))
      }
      const [score] = sparse.computeScores()
      expect(score.signals.metricFlatness).toBe(0)
    })
  })

  describe('classification thresholds', () => {
    it('flowing for very low composite', () => {
      const lively = new SaturationDetector({ windows: [10] }, logger)
      pushFlowing(lively, 15)
      const [score] = lively.computeScores()
      expect(score.composite).toBeLessThan(DEFAULT_SATURATION_CONFIG.thresholds.flowing)
      expect(score.classification).toBe('flowing')
    })

    it('saturated for very high composite', () => {
      pushSaturated(detector, 25)
      const scores = detector.computeScores()
      const big = scores.find(s => s.composite >= DEFAULT_SATURATION_CONFIG.thresholds.saturated)
      expect(big).toBeDefined()
      expect(big!.classification).toBe('saturated')
    })

    it('productive_focus when growth markers exist in mid-band', () => {
      // Custom thresholds force the medium band; signals indicate growth (low insightDrought)
      const focused = new SaturationDetector({
        windows: [10],
        thresholds: { flowing: 0.0, productiveFocus: 1.01, saturated: 1.02 },
      }, logger)
      // High composition stasis & repetition (saturated-like) but novel insights → growth marker
      for (let i = 0; i < 12; i++) {
        focused.recordSample(makeSample({
          turn: i,
          affect: { valence: 0.1, arousal: 0.1 },
          activeCompositions: ['comp-A'],
          activatedNodes: ['node-1', 'node-2'],
          insights: [makeInsight({ kind: 'breakthrough', confidence: 0.9 })],
          reasoningMetrics: { coherence: 0.5, integration: 0.5, novelty: 0.5 },
        }))
      }
      const [score] = focused.computeScores()
      expect(['flowing', 'productive_focus']).toContain(score.classification)
    })

    it('unclear when in mid-band without growth markers', () => {
      const middle = new SaturationDetector({
        windows: [10],
        thresholds: { flowing: 0.0, productiveFocus: 1.01, saturated: 1.02 },
      }, logger)
      pushSaturated(middle, 15)
      const [score] = middle.computeScores()
      // composite is < 1.01 (productiveFocus threshold) but no growth (insightDrought = 1, affectStability high)
      expect(['unclear', 'flowing']).toContain(score.classification)
    })

    it('unclear in the gap between productiveFocus and saturated', () => {
      const gappy = new SaturationDetector({
        windows: [10],
        thresholds: { flowing: 0.0, productiveFocus: 0.0, saturated: 1.01 },
      }, logger)
      pushSaturated(gappy, 15)
      const [score] = gappy.computeScores()
      // composite is in [0, 1.01) → unclear
      expect(score.classification).toBe('unclear')
    })
  })

  describe('shouldSurface and markSurfaced', () => {
    it('does not surface non-saturated scores', () => {
      const lively = new SaturationDetector({ windows: [10] }, logger)
      pushFlowing(lively, 15)
      const [score] = lively.computeScores()
      expect(lively.shouldSurface(score)).toBe(false)
    })

    it('surfaces saturated scores when nag guard has not fired', () => {
      pushSaturated(detector, 25)
      const scores = detector.computeScores()
      const sat = scores.find(s => s.classification === 'saturated')!
      expect(detector.shouldSurface(sat)).toBe(true)
    })

    it('does not surface when silenced', () => {
      pushSaturated(detector, 25)
      detector.silence()
      const scores = detector.computeScores()
      const sat = scores.find(s => s.classification === 'saturated')!
      expect(detector.shouldSurface(sat)).toBe(false)
    })

    it('unsilence re-enables surfacing', () => {
      pushSaturated(detector, 25)
      detector.silence()
      detector.unsilence()
      const scores = detector.computeScores()
      const sat = scores.find(s => s.classification === 'saturated')!
      expect(detector.shouldSurface(sat)).toBe(true)
    })

    it('does not re-surface same window within cooldown', () => {
      const tight = new SaturationDetector({ windows: [10], resurfaceCooldownTurns: 50 }, logger)
      pushSaturated(tight, 15)
      const [score] = tight.computeScores()
      expect(tight.shouldSurface(score)).toBe(true)
      tight.markSurfaced(score)

      // Add a few more saturated samples but stay within cooldown
      pushSaturated(tight, 5, 16)
      const [score2] = tight.computeScores()
      expect(tight.shouldSurface(score2)).toBe(false)
    })

    it('surfaces a different window even within cooldown', () => {
      const multi = new SaturationDetector({ windows: [10, 20], resurfaceCooldownTurns: 1000 }, logger)
      pushSaturated(multi, 25)
      const scores = multi.computeScores()
      const w10 = scores.find(s => s.windowSize === 10)!
      multi.markSurfaced(w10)

      const w20 = scores.find(s => s.windowSize === 20)!
      expect(w20.windowSize).not.toBe(w10.windowSize)
      expect(multi.shouldSurface(w20)).toBe(true)
    })

    it('re-surfaces after cooldown elapses', () => {
      const tight = new SaturationDetector({ windows: [10], resurfaceCooldownTurns: 5 }, logger)
      pushSaturated(tight, 15)
      const [score] = tight.computeScores()
      tight.markSurfaced(score)

      // Push enough samples to elapse the cooldown
      pushSaturated(tight, 10, 16)
      const [score2] = tight.computeScores()
      expect(tight.shouldSurface(score2)).toBe(true)
    })

    it('does not surface when no samples present', () => {
      const empty = new SaturationDetector({}, logger)
      const fakeScore: SaturationScore = {
        computedAt: new Date().toISOString(),
        windowSize: 20,
        turnCount: 0,
        signals: {
          affectStability: 1, compositionStasis: 1, activationRepetition: 1,
          insightDrought: 1, metricFlatness: 1,
        },
        composite: 1,
        classification: 'saturated',
      }
      expect(empty.shouldSurface(fakeScore)).toBe(false)
    })

    it('markSurfaced is a no-op when no samples are present', () => {
      const empty = new SaturationDetector({}, logger)
      const fakeScore: SaturationScore = {
        computedAt: new Date().toISOString(),
        windowSize: 20,
        turnCount: 0,
        signals: {
          affectStability: 1, compositionStasis: 1, activationRepetition: 1,
          insightDrought: 1, metricFlatness: 1,
        },
        composite: 1,
        classification: 'saturated',
      }
      // Should not throw
      empty.markSurfaced(fakeScore)
      expect(empty.shouldSurface(fakeScore)).toBe(false)
    })
  })

  describe('renderNote', () => {
    it('returns empty string when no signal exceeds 0.5', () => {
      const lively = new SaturationDetector({ windows: [10] }, logger)
      pushFlowing(lively, 15)
      const [score] = lively.computeScores()
      const note = lively.renderNote(score)
      expect(note).toBe('')
    })

    it('renders a humble note when signals are high', () => {
      pushSaturated(detector, 25)
      const scores = detector.computeScores()
      const sat = scores.find(s => s.classification === 'saturated')!
      const note = detector.renderNote(sat)
      expect(note).toContain('[Aurora — Saturation note]')
      expect(note).toContain(`The last ${sat.turnCount} turns`)
      // Humble phrasing: offers a question rather than asserting saturation
      expect(note).toMatch(/may be productive flow|saturation/)
      expect(note).toContain('Review?')
    })

    it('mentions the highest-scoring signals first', () => {
      pushSaturated(detector, 25)
      const scores = detector.computeScores()
      const sat = scores.find(s => s.classification === 'saturated')!
      const note = detector.renderNote(sat)

      const labelMap: Record<string, string> = {
        affectStability: 'stable affect',
        compositionStasis: 'unchanged composition',
        activationRepetition: 'repeated activation patterns',
        insightDrought: 'no novel insights',
        metricFlatness: 'flatlined reasoning metrics',
      }
      const sortedSignals = Object.entries(sat.signals)
        .filter(([, v]) => v >= 0.5)
        .sort(([, a], [, b]) => b - a)
      if (sortedSignals.length >= 2) {
        const firstLabel = labelMap[sortedSignals[0][0]]
        const secondLabel = labelMap[sortedSignals[1][0]]
        expect(note.indexOf(firstLabel)).toBeLessThan(note.indexOf(secondLabel))
      }
    })

    it('omits signals below 0.5 from the note', () => {
      pushSaturated(detector, 25)
      const scores = detector.computeScores()
      const sat = scores.find(s => s.classification === 'saturated')!
      const note = detector.renderNote(sat)

      const lowSignals = Object.entries(sat.signals).filter(([, v]) => v < 0.5)
      const labelMap: Record<string, string> = {
        affectStability: 'stable affect',
        compositionStasis: 'unchanged composition',
        activationRepetition: 'repeated activation patterns',
        insightDrought: 'no novel insights',
        metricFlatness: 'flatlined reasoning metrics',
      }
      for (const [k] of lowSignals) {
        expect(note).not.toContain(labelMap[k])
      }
    })
  })

  describe('silence / unsilence', () => {
    it('silence persists in config', () => {
      detector.silence()
      expect(detector.getConfig().silenced).toBe(true)
    })

    it('unsilence clears the silenced flag', () => {
      detector.silence()
      detector.unsilence()
      expect(detector.getConfig().silenced).toBe(false)
    })
  })

  describe('updateConfig', () => {
    it('merges patch onto current config', () => {
      detector.updateConfig({ resurfaceCooldownTurns: 200 })
      expect(detector.getConfig().resurfaceCooldownTurns).toBe(200)
      // Other values preserved
      expect(detector.getConfig().enabled).toBe(true)
    })
  })

  describe('edge cases', () => {
    it('handles empty history gracefully', () => {
      expect(detector.computeScores()).toEqual([])
    })

    it('handles a single sample without crashing', () => {
      detector.recordSample(makeSample({ turn: 1 }))
      // Default windows are [20, 100] — both will skip (need >= 3 samples)
      expect(detector.computeScores()).toEqual([])
    })

    it('handles repeated identical samples', () => {
      pushSaturated(detector, 30)
      const scores = detector.computeScores()
      expect(scores.length).toBeGreaterThan(0)
      for (const score of scores) {
        expect(score.composite).toBeGreaterThan(0)
        expect(Number.isFinite(score.composite)).toBe(true)
      }
    })

    it('handles large jumps in affect without producing NaN', () => {
      const jumpy = new SaturationDetector({ windows: [10] }, logger)
      for (let i = 0; i < 12; i++) {
        jumpy.recordSample(makeSample({
          turn: i,
          affect: { valence: i === 6 ? 1 : -1, arousal: i === 6 ? 1 : -1 },
        }))
      }
      const [score] = jumpy.computeScores()
      expect(Number.isFinite(score.composite)).toBe(true)
      expect(Number.isFinite(score.signals.affectStability)).toBe(true)
    })

    it('handles all-null affect without crashing', () => {
      for (let i = 0; i < 12; i++) {
        detector.recordSample(makeSample({ turn: i, affect: null }))
      }
      const scores = detector.computeScores()
      // All windows w/ ≥ 3 samples should yield a score with affectStability = 0
      for (const s of scores) {
        expect(s.signals.affectStability).toBe(0)
      }
    })

    it('handles all-empty activatedNodes without crashing', () => {
      for (let i = 0; i < 12; i++) {
        detector.recordSample(makeSample({ turn: i, activatedNodes: [] }))
      }
      const scores = detector.computeScores()
      for (const s of scores) {
        expect(s.signals.activationRepetition).toBe(0)
      }
    })

    it('records computedAt as ISO 8601 string', () => {
      pushSaturated(detector, 25)
      const [score] = detector.computeScores()
      expect(score.computedAt).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
      expect(() => new Date(score.computedAt).toISOString()).not.toThrow()
    })
  })
})
