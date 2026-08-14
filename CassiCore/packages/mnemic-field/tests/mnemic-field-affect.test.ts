import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import Database from 'better-sqlite3'
import { MnemicField } from '../src/index.js'
import { attune, AffectRegister, resolveLabel, affectSimilarity, emotionalIntensity, computeDominance } from '../src/affect.js'
import type { Affect } from '../src/types.js'
import { mockLogger } from './helpers.js'

function makeInMemoryDb(): Database.Database {
  const db = new Database(':memory:')
  db.pragma('foreign_keys = ON')
  return db
}

describe('Attunement (Phase 1)', () => {
  it('detects positive valence from success markers', () => {
    const affect = attune('The deployment succeeded and all tests passed.')
    expect(affect.valence).toBeGreaterThan(0.2)
    expect(affect.arousal).toBeGreaterThan(0)
  })

  it('detects negative valence from failure markers', () => {
    const affect = attune('The build failed again with the same error.')
    expect(affect.valence).toBeLessThan(-0.2)
    expect(affect.arousal).toBeGreaterThan(0.2)
  })

  it('detects high arousal from urgency markers', () => {
    const affect = attune('This is critical and needs to be fixed immediately.')
    expect(affect.arousal).toBeGreaterThan(0.3)
  })

  it('detects curiosity from discovery markers', () => {
    const affect = attune('I discovered a surprising insight about the architecture.')
    expect(affect.valence).toBeGreaterThan(0.1)
    expect(affect.arousal).toBeGreaterThan(0.1)
  })

  it('returns neutral for emotionally flat content', () => {
    const affect = attune('The function takes two parameters and returns a boolean.')
    expect(affect.valence).toBe(0)
    expect(affect.arousal).toBe(0)
  })

  it('detects warmth from gratitude markers', () => {
    const affect = attune('Thank you for helping, I really appreciate it.')
    expect(affect.valence).toBeGreaterThan(0.2)
  })

  it('normalizes mixed signals', () => {
    const affect = attune('The test passed but the deployment failed and we need to fix it immediately.')
    expect(affect.valence).not.toBe(0)
    expect(affect.arousal).toBeGreaterThan(0)
    expect(Math.abs(affect.valence)).toBeLessThanOrEqual(1)
    expect(affect.arousal).toBeLessThanOrEqual(1)
  })
})

describe('AffectRegister (Phase 2)', () => {
  it('starts at baseline', () => {
    const register = new AffectRegister()
    const state = register.getState()
    expect(state.valence).toBeCloseTo(0.05, 1)
    expect(state.arousal).toBeCloseTo(0.2, 1)
    expect(state.label).toBe('neutral')
  })

  it('absorbs activation echoes', () => {
    const register = new AffectRegister()
    const batch = [
      { affect: { valence: 0.8, arousal: 0.6 } as Affect, charge: 1.0 },
      { affect: { valence: 0.6, arousal: 0.4 } as Affect, charge: 0.5 },
    ]
    for (let i = 0; i < 3; i++) register.absorbActivation(batch)
    const state = register.getState()
    expect(state.valence).toBeGreaterThan(0.1)
    expect(state.arousal).toBeGreaterThanOrEqual(0.25)
  })

  it('shifts negative on failure outcome', () => {
    const register = new AffectRegister()
    for (let i = 0; i < 3; i++) {
      register.absorbActivation(
        [{ affect: { valence: -0.3, arousal: 0.5 }, charge: 1.0 }],
        'failure',
      )
    }
    const state = register.getState()
    expect(state.valence).toBeLessThan(0)
  })

  it('shifts positive on success outcome', () => {
    const register = new AffectRegister()
    register.absorbActivation(
      [{ affect: { valence: 0.0, arousal: 0.3 }, charge: 0.5 }],
      'success',
    )
    const state = register.getState()
    expect(state.valence).toBeGreaterThan(0.05)
  })

  it('absorbs system signals', () => {
    const register = new AffectRegister()
    for (let i = 0; i < 3; i++) {
      register.absorbSignal({ valence: -0.8, arousal: 0.9 })
    }
    const state = register.getState()
    expect(state.valence).toBeLessThan(0)
    expect(state.arousal).toBeGreaterThan(0.25)
  })

  it('ignores null affect entries', () => {
    const register = new AffectRegister()
    register.absorbActivation([
      { affect: null, charge: 1.0 },
      { affect: null, charge: 0.5 },
    ])
    const state = register.getState()
    expect(state.valence).toBeCloseTo(0.05, 1)
  })
})

describe('Label Resolution (Phase 3)', () => {
  it('maps high-V high-A to excited', () => {
    expect(resolveLabel({ valence: 0.7, arousal: 0.7 })).toBe('excited')
  })

  it('maps high-V low-A to content', () => {
    expect(resolveLabel({ valence: 0.5, arousal: 0.15 })).toBe('content')
  })

  it('maps low-V high-A to alarmed', () => {
    expect(resolveLabel({ valence: -0.5, arousal: 0.7 })).toBe('alarmed')
  })

  it('maps low-V low-A to melancholy', () => {
    expect(resolveLabel({ valence: -0.5, arousal: 0.1 })).toBe('melancholy')
  })

  it('maps near-zero to neutral', () => {
    expect(resolveLabel({ valence: 0.05, arousal: 0.1 })).toBe('neutral')
  })

  it('maps moderate positive with moderate arousal to engaged', () => {
    expect(resolveLabel({ valence: 0.4, arousal: 0.4 })).toBe('engaged')
  })

  it('maps slight negative high arousal to frustrated', () => {
    expect(resolveLabel({ valence: -0.4, arousal: 0.4 })).toBe('frustrated')
  })
})

describe('Affect Utilities', () => {
  it('computes emotional intensity as max of |valence| and arousal', () => {
    expect(emotionalIntensity({ valence: -0.8, arousal: 0.3 })).toBe(0.8)
    expect(emotionalIntensity({ valence: 0.2, arousal: 0.9 })).toBe(0.9)
  })

  it('computes similarity between identical affects as 1', () => {
    const a: Affect = { valence: 0.5, arousal: 0.5 }
    expect(affectSimilarity(a, a)).toBeCloseTo(1.0, 5)
  })

  it('computes low similarity between opposite affects', () => {
    const a: Affect = { valence: 0.8, arousal: 0.8 }
    const b: Affect = { valence: -0.8, arousal: 0.1 }
    expect(affectSimilarity(a, b)).toBeLessThan(0.5)
  })
})

describe('MnemicField Integration', () => {
  let field: MnemicField

  beforeEach(() => {
    field = new MnemicField(mockLogger(), ':memory:')
  })

  afterEach(() => {
    field.close()
  })

  it('stores engrams with affect metadata', () => {
    const engram = field.store({
      content: 'The refactoring succeeded and the code is much cleaner now.',
      nodeType: 'episode',
    })
    const affect = engram.metadata?.affect as Affect | undefined
    expect(affect).toBeDefined()
    expect(affect!.valence).toBeGreaterThan(0)
  })

  it('stores neutral affect for flat content', () => {
    const engram = field.store({
      content: 'This module exports three functions.',
      nodeType: 'fact',
    })
    const affect = engram.metadata?.affect as Affect | undefined
    expect(affect).toBeDefined()
    expect(affect!.valence).toBe(0)
    expect(affect!.arousal).toBe(0)
  })

  it('exposes affect state via getAffect()', () => {
    const state = field.getAffect()
    expect(state).toHaveProperty('valence')
    expect(state).toHaveProperty('arousal')
    expect(state).toHaveProperty('label')
    expect(state.label).toBe('neutral')
  })

  it('affect register shifts after recordActivation with success', () => {
    const engram = field.store({
      content: 'The deployment succeeded and all tests passed perfectly.',
      nodeType: 'outcome',
      embedding: new Float32Array([0.1, 0.2, 0.3]),
      x: 0, y: 0,
    })

    const luminal = {
      engrams: [{ engram, charge: 0.8 }],
      totalCharge: 0.8,
      seedCount: 1,
      iterationsUsed: 0,
      sparkPoint: 0.5,
      taskComplexity: 'normal' as const,
      durationMs: 1,
    }

    field.recordActivation(luminal, 'test', 'success')
    const state = field.getAffect()
    expect(state.valence).toBeGreaterThan(0.05)
  })

  it('absorbs system signals', () => {
    field.absorbAffectSignal({ valence: -0.6, arousal: 0.8 })
    const state = field.getAffect()
    expect(state.valence).toBeLessThan(0.05)
    expect(state.arousal).toBeGreaterThan(0.2)
  })
})

describe('Wave 6: Affect Improvements', () => {
  describe('Dominance', () => {
    it('derives high dominance from positive valence + low arousal', () => {
      expect(computeDominance(0.8, 0.1)).toBeGreaterThan(0.8)
    })

    it('reaches 1.0 at max positive valence, zero arousal', () => {
      expect(computeDominance(1.0, 0.0)).toBe(1.0)
    })

    it('reaches 0.0 at max negative valence, max arousal', () => {
      expect(computeDominance(-1.0, 1.0)).toBe(0.0)
    })

    it('derives low dominance from negative valence + high arousal', () => {
      expect(computeDominance(-0.7, 0.8)).toBeLessThan(0.2)
    })

    it('derives neutral dominance from baseline', () => {
      const d = computeDominance(0.05, 0.2)
      expect(d).toBeGreaterThan(0.4)
      expect(d).toBeLessThan(0.6)
    })

    it('is included in AffectState', () => {
      const register = new AffectRegister()
      const state = register.getState()
      expect(state.dominance).toBeDefined()
      expect(typeof state.dominance).toBe('number')
    })
  })

  describe('Two-tier decay', () => {
    it('emotion decays faster than mood', () => {
      const register = new AffectRegister()
      for (let i = 0; i < 5; i++) register.absorbSignal({ valence: 0.8 })

      const before = register.getAffect()

      const emotionDecayRate = 0.05
      const moodDecayRate = 0.02
      const elapsed = 10
      const emotionFactor = Math.pow(1 - emotionDecayRate, elapsed)
      const moodFactor = Math.pow(1 - moodDecayRate, elapsed)

      expect(emotionFactor).toBeLessThan(moodFactor)
    })

    it('mood register creates sustained baseline shift', () => {
      const register = new AffectRegister()
      for (let i = 0; i < 10; i++) register.absorbSignal({ valence: 0.7 })

      const afterAbsorption = register.getAffect().valence

      register['lastDecay'] = Date.now() - 5 * 60_000
      register['decay']()
      const afterEmotionDecay = register.getAffect().valence

      expect(afterEmotionDecay).toBeGreaterThan(0.05)
      expect(afterEmotionDecay).toBeLessThan(afterAbsorption)
    })
  })

  describe('Valence-asymmetric decay', () => {
    it('negative valence decays slower than positive', () => {
      const negRegister = new AffectRegister()
      for (let i = 0; i < 5; i++) negRegister.absorbSignal({ valence: -0.8 })

      const posRegister = new AffectRegister()
      for (let i = 0; i < 5; i++) posRegister.absorbSignal({ valence: 0.8 })

      const elapsed = 5 * 60_000
      negRegister['lastDecay'] = Date.now() - elapsed
      posRegister['lastDecay'] = Date.now() - elapsed

      const negState = negRegister.getAffect()
      const posState = posRegister.getAffect()

      expect(Math.abs(negState.valence - 0.05)).toBeGreaterThan(
        Math.abs(posState.valence - 0.05)
      )
    })
  })

  describe('Lightweight appraisal', () => {
    it('goal-relevance markers boost arousal', () => {
      const goalRelevant = attune('We need to implement and ship this feature')
      const neutral = attune('The sky is blue today')
      expect(goalRelevant.arousal).toBeGreaterThan(neutral.arousal)
    })

    it('unexpected outcomes amplify arousal', () => {
      const unexpected = attune('This is unexpected behavior from the API')
      expect(unexpected.arousal).toBeGreaterThan(0)
    })
  })
})
