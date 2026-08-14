// HOST-WIRED: requires CassiCore daemon runtime; excluded from default vitest run.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { MnemicField } from '../../core/intelligence/mnemic-field/index.js'
import type { PhrasePrototypeSet, ClassificationResult } from '../../core/intelligence/mnemic-field/edge-relators.js'
import { TERRITORY_RELATION_PHRASES, computeTerritorialOverlapSemantic, type SiblingGoalEntry } from '../../core/intelligence/constellation/territory-bridge.js'
import { SPAWN_EVALUATION_PHRASES } from '../../core/intelligence/phrase-prototypes.js'
import { DecompositionTracker, type TrackedTask } from '../../core/intelligence/constellation/decomposition-tracker.js'
import type { GoalDecomposition } from '../../core/intelligence/constellation/corpus-types.js'
import { MessageLuminanceScorer } from '../../core/intelligence/thalamus/scorer.js'

function mockLogger() {
  return { child: () => mockLogger(), info: vi.fn(), warn: vi.fn(), debug: vi.fn(), error: vi.fn() }
}

function makeMockField(fn: (text: string) => ClassificationResult): MnemicField {
  return {
    classifyPhrase: vi.fn(async (_text: string, _set?: PhrasePrototypeSet, _threshold?: number) => fn(_text)),
    ensurePhraseEmbeddingsForSet: vi.fn(),
  } as unknown as MnemicField
}

describe('TERRITORY_RELATION_PHRASES', () => {
  it('has all required labels', () => {
    expect(TERRITORY_RELATION_PHRASES.labels).toContain('same_domain')
    expect(TERRITORY_RELATION_PHRASES.labels).toContain('contradictory')
    expect(TERRITORY_RELATION_PHRASES.labels).toContain('enables_other')
    expect(TERRITORY_RELATION_PHRASES.labels).toContain('independent')
  })

  it('has phrases for every label', () => {
    for (const label of TERRITORY_RELATION_PHRASES.labels) {
      expect(TERRITORY_RELATION_PHRASES.phrases[label].length).toBeGreaterThan(0)
    }
  })
})

describe('SPAWN_EVALUATION_PHRASES', () => {
  it('has all required labels', () => {
    expect(SPAWN_EVALUATION_PHRASES.labels).toContain('duplicate_work')
    expect(SPAWN_EVALUATION_PHRASES.labels).toContain('natural_subtask')
    expect(SPAWN_EVALUATION_PHRASES.labels).toContain('out_of_scope')
    expect(SPAWN_EVALUATION_PHRASES.labels).toContain('high_dependency')
  })
})

describe('computeTerritorialOverlapSemantic', () => {
  const makeEntry = (helixId: string, goalText: string): SiblingGoalEntry => ({
    helixId, goalText, relevantFiles: [], keywords: new Set(), receivedAt: Date.now(),
  })

  it('detects same_domain overlap without file keywords', async () => {
    const mf = makeMockField(() => ({ label: 'same_domain', score: 0.55 }))
    const result = await computeTerritorialOverlapSemantic(makeEntry('a', 'auth refactor'), makeEntry('b', 'rbac rewrite'), mf)
    expect(result.hasOverlap).toBe(true)
  })

  it('returns no overlap for independent branches', async () => {
    const mf = makeMockField(() => ({ label: 'independent', score: 0.72 }))
    const result = await computeTerritorialOverlapSemantic(makeEntry('a', 'auth'), makeEntry('b', 'payment'), mf)
    expect(result.hasOverlap).toBe(false)
  })

  it('returns no overlap for null classification', async () => {
    const mf = makeMockField(() => ({ label: null, score: 0 }))
    const result = await computeTerritorialOverlapSemantic(makeEntry('a', 'x'), makeEntry('b', 'y'), mf)
    expect(result.hasOverlap).toBe(false)
  })
})

describe('DecompositionTracker deviation classification', () => {
  const makeDecomp = (): GoalDecomposition => ({
    goal: 'test', subTasks: [{ goal: 'subtask', priority: 'medium', acceptanceCriteria: [] }],
  })

  it('classifies under_scoped deviation', async () => {
    const mf = makeMockField(() => ({ label: 'under_scoped', score: 0.62 }))
    const tracker = new DecompositionTracker('c1', makeDecomp(), mockLogger() as any)
    tracker.setMnemicField(mf)

    const tasks = (tracker as any).tasks as Map<string, TrackedTask>
    const task = tasks.values().next().value
    task.status = 'in-progress'
    task.actualGoal = 'expanded scope'

    await tracker.completeTask(task.id, 'required three extra features beyond the estimate')
    await new Promise(r => setTimeout(r, 10))
    expect(task.deviationReason).toBe('under_scoped')
    expect(task.deviationConfidence).toBe(0.62)
  })

  it('classifies context_shift deviation', async () => {
    const mf = makeMockField(() => ({ label: 'context_shift', score: 0.58 }))
    const tracker = new DecompositionTracker('c1', makeDecomp(), mockLogger() as any)
    tracker.setMnemicField(mf)

    const tasks = (tracker as any).tasks as Map<string, TrackedTask>
    const task = tasks.values().next().value
    task.status = 'in-progress'
    task.actualGoal = 'new goal'

    await tracker.completeTask(task.id, 'stakeholder redirected priorities midway')
    await new Promise(r => setTimeout(r, 10))
    expect(task.deviationReason).toBe('context_shift')
    expect(task.deviationConfidence).toBe(0.58)
  })

  it('skips classification when no outcome provided', async () => {
    const mf = makeMockField(() => ({ label: 'under_scoped', score: 0.62 }))
    const tracker = new DecompositionTracker('c1', makeDecomp(), mockLogger() as any)
    tracker.setMnemicField(mf)

    const tasks = (tracker as any).tasks as Map<string, TrackedTask>
    const task = tasks.values().next().value
    task.status = 'in-progress'

    await tracker.completeTask(task.id)
    expect(task.deviationReason).toBeUndefined()
  })
})

describe('MessageLuminanceScorer.applyEpistemicBoosts', () => {
  it('boosts cognitiveResonance for reversal', async () => {
    const mf = makeMockField(() => ({ label: 'reversal', score: 0.8 }))
    const scorer = new MessageLuminanceScorer(mockLogger() as any)
    scorer.setMnemicField(mf)

    const scored = [{ messageIndex: 0, estimatedChars: 100, luminance: { novelty: 0.5, urgency: 0.5, relevance: 0.5, sourceCredibility: 0.5, cognitiveResonance: 0.3, strategicImportance: 0.5, composite: 0.3 } }]
    const messages = [{ content: 'I was wrong about the architecture' }]
    await scorer.applyEpistemicBoosts(scored, messages)

    expect(scored[0].luminance.cognitiveResonance).toBeGreaterThan(0.3)
    expect(scored[0].luminance.cognitiveResonance).toBeLessThanOrEqual(1)
  })

  it('gives mild boost for confirmation', async () => {
    const mf = makeMockField(() => ({ label: 'confirmation', score: 0.9 }))
    const scorer = new MessageLuminanceScorer(mockLogger() as any)
    scorer.setMnemicField(mf)

    const scored = [{ messageIndex: 0, estimatedChars: 100, luminance: { novelty: 0.5, urgency: 0.5, relevance: 0.5, sourceCredibility: 0.5, cognitiveResonance: 0.3, strategicImportance: 0.5, composite: 0.3 } }]
    await scorer.applyEpistemicBoosts(scored, [{ content: 'confirmed the suspicion' }])

    expect(scored[0].luminance.cognitiveResonance).toBe(0.3 + 0.08 * 0.9)
  })

  it('does not boost when no epistemic shift detected', async () => {
    const mf = makeMockField(() => ({ label: null, score: 0 }))
    const scorer = new MessageLuminanceScorer(mockLogger() as any)
    scorer.setMnemicField(mf)

    const scored = [{ messageIndex: 0, estimatedChars: 100, luminance: { novelty: 0.5, urgency: 0.5, relevance: 0.5, sourceCredibility: 0.5, cognitiveResonance: 0.3, strategicImportance: 0.5, composite: 0.3 } }]
    await scorer.applyEpistemicBoosts(scored, [{ content: 'routine message' }])

    expect(scored[0].luminance.cognitiveResonance).toBe(0.3)
  })

  it('skips messages already at max composite', async () => {
    const classifySpy = vi.fn()
    const mf = { classifyPhrase: classifySpy, ensurePhraseEmbeddingsForSet: vi.fn() } as unknown as MnemicField
    const scorer = new MessageLuminanceScorer(mockLogger() as any)
    scorer.setMnemicField(mf)

    const scored = [{ messageIndex: 0, estimatedChars: 100, luminance: { novelty: 1, urgency: 1, relevance: 1, sourceCredibility: 1, cognitiveResonance: 1, strategicImportance: 1, composite: 1 } }]
    await scorer.applyEpistemicBoosts(scored, [{ content: 'test' }])

    expect(classifySpy).not.toHaveBeenCalled()
  })
})

describe('phrase prototype import integrity', () => {
  it('all phrase sets have matching labels and phrase keys', async () => {
    const { default: _ } = await import('fs')
    const mod = await import('../../core/intelligence/phrase-prototypes.js')
    const exports = Object.entries(mod)
    for (const [name, set] of exports) {
      if (name.endsWith('_PHRASES') && typeof set === 'object' && 'labels' in set && 'phrases' in set) {
        const s = set as PhrasePrototypeSet
        for (const label of s.labels) {
          expect(s.phrases[label]).toBeDefined()
          expect(s.phrases[label].length).toBeGreaterThan(0)
        }
      }
    }
  })

  it('every phrase set has at least 3 phrases per label', async () => {
    const mod = await import('../../core/intelligence/phrase-prototypes.js')
    const exports = Object.entries(mod)
    for (const [name, set] of exports) {
      if (name.endsWith('_PHRASES') && typeof set === 'object' && 'labels' in set && 'phrases' in set) {
        const s = set as PhrasePrototypeSet
        for (const label of s.labels) {
          expect(s.phrases[label].length).toBeGreaterThanOrEqual(3)
        }
      }
    }
  })

  it('no phrase set is empty', async () => {
    const mod = await import('../../core/intelligence/phrase-prototypes.js')
    const exports = Object.entries(mod)
    for (const [name, set] of exports) {
      if (name.endsWith('_PHRASES') && typeof set === 'object' && 'labels' in set && 'phrases' in set) {
        const s = set as PhrasePrototypeSet
        expect(s.labels.length).toBeGreaterThan(0)
      }
    }
  })
})
