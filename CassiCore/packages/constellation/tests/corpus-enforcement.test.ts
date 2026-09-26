/**
 * Corpus Enforcement Tests
 *
 * Tests the enforcement mechanisms in the Corpus intervention system:
 *   - evaluateEscalation: level transitions based on ignored directives and low progress
 *   - evaluateAllEscalations: enforcement fields on directives per level
 *   - sendDirective: actedUpon flag, DirectiveRecord creation
 *   - checkInterventionEffectiveness: outcome transition from pending to effective/ignored
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createCorpus } from '../src/corpus.js'
import { CorpusTree } from '../src/corpus-tree.js'
import type {
  CorpusDeps,
  CorpusDirective,
  BranchAssessment,
  DirectiveRecord,
  EscalationLevel,
} from '../src/corpus-types.js'
import type {
  BrainstemAnnotation,
  WorkUnitAnnotation,
  DetectedPattern,
} from '../src/vendor/helix/brainstem-types.js'

function makeLogger(): any {
  const log: any = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn(() => log),
  }
  return log
}

function makeAnnotation(overrides: Partial<BrainstemAnnotation> = {}): BrainstemAnnotation {
  return {
    workUnitId: `wu-${Math.random().toString(36).slice(2, 8)}`,
    axonStep: 1,
    score: 0.7,
    annotation: 'implementation' as WorkUnitAnnotation,
    pattern: 'none' as DetectedPattern,
    synthesis: 'Yang and Yin agree on approach',
    guidance: null,
    guidanceUrgency: 'low' as any,
    trainingNote: 'Good progress',
    timestamp: Date.now(),
    goalAlignment: 0.7,
    novelty: 0.5,
    progress: 0.6,
    discoveries: [],
    decisions: [],
    hypothesis: '',
    outputs: [],
    blockers: [],
    nextSteps: [],
    knowledgeDelta: '',
    ...overrides,
  }
}

function makeDeps(overrides: Partial<CorpusDeps> = {}): CorpusDeps {
  return {
    llm: {
      complete: vi.fn().mockResolvedValue({
        content: 'ASSESSMENT: All branches healthy\nSYNTHESIS: NONE',
        truncated: false,
      }),
    },
    logger: makeLogger(),
    goal: 'Implement feature X',
    constellationId: 'constellation-test-1',
    ...overrides,
  }
}

function makeBranchAssessment(helixId: string, overrides: Partial<BranchAssessment> = {}): BranchAssessment {
  return {
    helixId,
    status: 'productive',
    rollingScore: 0.5,
    scoreTrajectory: [0.5],
    dominantPattern: 'none',
    filesModified: new Set<string>(),
    decliningScoreStreak: 0,
    lastActivityAt: Date.now(),
    avgGoalAlignment: 0.5,
    avgNovelty: 0.5,
    avgProgress: 0.5,
    directiveHistory: [],
    escalationLevel: 0 as EscalationLevel,
    ignoredDirectiveStreak: 0,
    lowProgressStreak: 0,
    discoveries: [],
    contextInjectionsReceived: 0,
    researchDigestBuilt: false,
    ...overrides,
  }
}

describe('Corpus Enforcement', () => {
  let tree: CorpusTree
  let logger: any

  beforeEach(() => {
    logger = makeLogger()
    tree = new CorpusTree(logger)
  })

  describe('evaluateEscalation', () => {
    it('should escalate from level 0 to 1 on directive failures', () => {
      const corpus = createCorpus(tree, makeDeps())

      const assessment = makeBranchAssessment('helix-1', {
        // HOW: standard template: directiveFailuresForEscalation = 3
        ignoredDirectiveStreak: 3,
        lowProgressStreak: 0,
      })

      const newLevel = corpus.evaluateEscalation(assessment)
      expect(newLevel).toBe(1)
      expect(assessment.escalationLevel).toBe(1)
    })

    it('should escalate from level 0 to 1 on low progress streak', () => {
      const corpus = createCorpus(tree, makeDeps())

      const assessment = makeBranchAssessment('helix-1', {
        // HOW: standard template: lowProgressStepsForEscalation = 12
        lowProgressStreak: 12,
        ignoredDirectiveStreak: 0,
      })

      const newLevel = corpus.evaluateEscalation(assessment)
      expect(newLevel).toBe(1)
    })

    it('should escalate by 2 levels when both signals fire', () => {
      const corpus = createCorpus(tree, makeDeps())

      const assessment = makeBranchAssessment('helix-1', {
        ignoredDirectiveStreak: 3,
        lowProgressStreak: 12,
      })

      const newLevel = corpus.evaluateEscalation(assessment)
      expect(newLevel).toBe(2)
      expect(assessment.escalationLevel).toBe(2)
    })

    it('should not exceed level 4', () => {
      const corpus = createCorpus(tree, makeDeps())

      const assessment = makeBranchAssessment('helix-1', {
        escalationLevel: 3 as EscalationLevel,
        ignoredDirectiveStreak: 3,
        lowProgressStreak: 12,
      })

      const newLevel = corpus.evaluateEscalation(assessment)
      expect(newLevel).toBe(4)
      expect(assessment.escalationLevel).toBe(4)
    })

    it('should return null when no escalation is needed', () => {
      const corpus = createCorpus(tree, makeDeps())

      const assessment = makeBranchAssessment('helix-1', {
        ignoredDirectiveStreak: 0,
        lowProgressStreak: 0,
      })

      const newLevel = corpus.evaluateEscalation(assessment)
      expect(newLevel).toBeNull()
    })

    it('should escalate on low rolling score with enough history', () => {
      const corpus = createCorpus(tree, makeDeps())

      // HOW: standard template: lowScoreThreshold=0.3, lowScoreStepsForEscalation=10
      const assessment = makeBranchAssessment('helix-1', {
        rollingScore: 0.2,
        scoreTrajectory: new Array(10).fill(0.2),
        ignoredDirectiveStreak: 0,
        lowProgressStreak: 0,
      })

      const newLevel = corpus.evaluateEscalation(assessment)
      expect(newLevel).toBe(1)
    })

    it('should de-escalate when improvement detected', () => {
      const corpus = createCorpus(tree, makeDeps())

      // WHY: When no signals fire and the branch is above level 0, the
      // evaluateEscalation code returns null (no change), so de-escalation
      // happens through a separate path. This test verifies no false escalation.
      const assessment = makeBranchAssessment('helix-1', {
        escalationLevel: 2 as EscalationLevel,
        ignoredDirectiveStreak: 0,
        lowProgressStreak: 0,
        rollingScore: 0.8,
        scoreTrajectory: [0.8],
      })

      const newLevel = corpus.evaluateEscalation(assessment)
      expect(newLevel).toBeNull()
      expect(assessment.escalationLevel).toBe(2) // Level unchanged (de-escalation is separate)
    })
  })

  describe('evaluateAllEscalations — enforcement fields', () => {
    it('should send level 1 directive with maxIterationsRemaining=20 and narrow_scope', () => {
      const corpus = createCorpus(tree, makeDeps())
      const mockBrainstem = { onCorpusDirective: vi.fn() }

      tree.registerBranch('helix-1', 'Test branch', 0)
      corpus.registerBrainstem('helix-1', mockBrainstem)

      const assessment = makeBranchAssessment('helix-1', {
        ignoredDirectiveStreak: 3,
      })
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).evaluateAllEscalations()

      expect(mockBrainstem.onCorpusDirective).toHaveBeenCalled()
      const directive: CorpusDirective = mockBrainstem.onCorpusDirective.mock.calls[0][0]
      expect(directive.maxIterationsRemaining).toBe(20)
      expect(directive.requiredAction).toBe('narrow_scope')
      expect(directive.urgency).toBe('medium')
      expect(directive.type).toBe('guidance')
    })

    it('should send level 2 directive with maxIterationsRemaining=10 and produce_output', () => {
      const corpus = createCorpus(tree, makeDeps())
      const mockBrainstem = { onCorpusDirective: vi.fn() }

      tree.registerBranch('helix-1', 'Test branch', 0)
      corpus.registerBrainstem('helix-1', mockBrainstem)

      const assessment = makeBranchAssessment('helix-1', {
        escalationLevel: 1 as EscalationLevel,
        ignoredDirectiveStreak: 3,
      })
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).evaluateAllEscalations()

      const directive: CorpusDirective = mockBrainstem.onCorpusDirective.mock.calls[0][0]
      expect(directive.maxIterationsRemaining).toBe(10)
      expect(directive.requiredAction).toBe('produce_output')
      expect(directive.urgency).toBe('critical')
      expect(directive.type).toBe('redirect')
    })

    it('should send level 3 directive with maxIterationsRemaining=5 and conclude', () => {
      const corpus = createCorpus(tree, makeDeps())
      const mockBrainstem = { onCorpusDirective: vi.fn() }

      tree.registerBranch('helix-1', 'Test branch', 0)
      corpus.registerBrainstem('helix-1', mockBrainstem)

      const assessment = makeBranchAssessment('helix-1', {
        escalationLevel: 2 as EscalationLevel,
        ignoredDirectiveStreak: 3,
      })
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).evaluateAllEscalations()

      const directive: CorpusDirective = mockBrainstem.onCorpusDirective.mock.calls[0][0]
      expect(directive.maxIterationsRemaining).toBe(5)
      expect(directive.requiredAction).toBe('conclude')
      expect(directive.urgency).toBe('critical')
      expect(directive.type).toBe('cancel')
    })

    it('should skip completed branches', () => {
      const corpus = createCorpus(tree, makeDeps())
      const mockBrainstem = { onCorpusDirective: vi.fn() }

      tree.registerBranch('helix-1', 'Test branch', 0)
      corpus.registerBrainstem('helix-1', mockBrainstem)

      const assessment = makeBranchAssessment('helix-1', {
        status: 'completed',
        ignoredDirectiveStreak: 10,
      })
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).evaluateAllEscalations()
      expect(mockBrainstem.onCorpusDirective).not.toHaveBeenCalled()
    })

    it('should skip failed branches', () => {
      const corpus = createCorpus(tree, makeDeps())
      const mockBrainstem = { onCorpusDirective: vi.fn() }

      tree.registerBranch('helix-1', 'Test branch', 0)
      corpus.registerBrainstem('helix-1', mockBrainstem)

      const assessment = makeBranchAssessment('helix-1', {
        status: 'failed',
        ignoredDirectiveStreak: 10,
      })
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).evaluateAllEscalations()
      expect(mockBrainstem.onCorpusDirective).not.toHaveBeenCalled()
    })
  })

  describe('sendDirective — actedUpon flag', () => {
    it('should set actedUpon=true on matching source pattern', () => {
      const corpus = createCorpus(tree, makeDeps())
      const mockBrainstem = { onCorpusDirective: vi.fn() }

      tree.registerBranch('helix-1', 'Test branch', 0)
      corpus.registerBrainstem('helix-1', mockBrainstem)

      ;(corpus as any).state.crossPatterns.push({
        type: 'asymmetric-progress',
        helixIds: ['helix-1', 'helix-2'],
        severity: 'critical',
        detectedAt: Date.now(),
        actedUpon: false,
      })

      ;(corpus as any).sendDirective({
        targetHelixId: 'helix-1',
        type: 'guidance',
        urgency: 'medium',
        text: 'Test directive',
        reason: 'test',
        timestamp: Date.now(),
        fromPattern: 'asymmetric-progress',
      })

      expect((corpus as any).state.crossPatterns[0].actedUpon).toBe(true)
    })

    it('should not set actedUpon on unrelated patterns', () => {
      const corpus = createCorpus(tree, makeDeps())
      const mockBrainstem = { onCorpusDirective: vi.fn() }

      tree.registerBranch('helix-1', 'Test branch', 0)
      corpus.registerBrainstem('helix-1', mockBrainstem)

      ;(corpus as any).state.crossPatterns.push({
        type: 'cascade-failure',
        helixIds: ['helix-3'],
        severity: 'critical',
        detectedAt: Date.now(),
        actedUpon: false,
      })

      ;(corpus as any).sendDirective({
        targetHelixId: 'helix-1',
        type: 'guidance',
        urgency: 'medium',
        text: 'Test directive',
        reason: 'test',
        timestamp: Date.now(),
        fromPattern: 'asymmetric-progress',
      })

      expect((corpus as any).state.crossPatterns[0].actedUpon).toBe(false)
    })
  })

  describe('sendDirective — DirectiveRecord creation', () => {
    it('should create DirectiveRecord with outcome=pending', () => {
      const corpus = createCorpus(tree, makeDeps())
      const mockBrainstem = { onCorpusDirective: vi.fn() }

      tree.registerBranch('helix-1', 'Test branch', 0)
      corpus.registerBrainstem('helix-1', mockBrainstem)

      const assessment = makeBranchAssessment('helix-1')
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).sendDirective({
        targetHelixId: 'helix-1',
        type: 'guidance',
        urgency: 'medium',
        text: 'Refocus',
        reason: 'test',
        timestamp: Date.now(),
      })

      expect(assessment.directiveHistory).toHaveLength(1)
      const record: DirectiveRecord = assessment.directiveHistory[0]
      expect(record.outcome).toBe('pending')
      expect(record.directive.text).toBe('Refocus')
      expect(record.postDirectiveScores).toEqual([])
    })

    it('should set intervention baseline for effectiveness tracking', () => {
      const corpus = createCorpus(tree, makeDeps())
      const mockBrainstem = { onCorpusDirective: vi.fn() }

      tree.registerBranch('helix-1', 'Test branch', 0)
      corpus.registerBrainstem('helix-1', mockBrainstem)

      const assessment = makeBranchAssessment('helix-1', { rollingScore: 0.45 })
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).sendDirective({
        targetHelixId: 'helix-1',
        type: 'guidance',
        urgency: 'medium',
        text: 'Refocus',
        reason: 'test',
        timestamp: Date.now(),
      })

      const baseline = (corpus as any).interventionBaselines.get('helix-1')
      expect(baseline).toBeDefined()
      expect(baseline.score).toBe(0.45)
      expect(baseline.type).toBe('guidance')
    })
  })

  describe('checkInterventionEffectiveness', () => {
    it('should mark directive as effective when score improves >5%', () => {
      const corpus = createCorpus(tree, makeDeps())

      tree.registerBranch('helix-1', 'Test', 0)
      // Add steps via pushAnnotation so branch.steps.length > 2
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 1 }))
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 2 }))
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 3 }))

      const assessment = makeBranchAssessment('helix-1', {
        rollingScore: 0.65, // improved from 0.5 baseline
        directiveHistory: [{
          directive: {
            targetHelixId: 'helix-1',
            type: 'guidance',
            urgency: 'medium',
            reason: 'test',
            text: 'Refocus',
            timestamp: Date.now(),
          },
          sentAtStep: 0,
          scoreAtSend: { goalAlignment: 0.5, novelty: 0.5, progress: 0.3 },
          postDirectiveScores: [],
          outcome: 'pending',
        }],
      })
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).interventionBaselines.set('helix-1', {
        score: 0.5,
        type: 'guidance',
        timestamp: Date.now() - 5000,
        step: 0,
      })

      ;(corpus as any).checkInterventionEffectiveness()

      // improvement = 0.65 - 0.5 = 0.15 > 0.05 threshold
      expect(assessment.directiveHistory[0].outcome).toBe('effective')
      expect(assessment.directiveHistory[0].evaluatedAt).toBeDefined()
    })

    it('should mark directive as ignored when score improvement <=5%', () => {
      const corpus = createCorpus(tree, makeDeps())

      tree.registerBranch('helix-1', 'Test', 0)
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 1 }))
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 2 }))
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 3 }))

      const assessment = makeBranchAssessment('helix-1', {
        rollingScore: 0.52,
        directiveHistory: [{
          directive: {
            targetHelixId: 'helix-1',
            type: 'guidance',
            urgency: 'medium',
            reason: 'test',
            text: 'Refocus',
            timestamp: Date.now(),
          },
          sentAtStep: 0,
          scoreAtSend: { goalAlignment: 0.5, novelty: 0.5, progress: 0.3 },
          postDirectiveScores: [],
          outcome: 'pending',
        }],
      })
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).interventionBaselines.set('helix-1', {
        score: 0.5,
        type: 'guidance',
        timestamp: Date.now() - 5000,
        step: 0,
      })

      ;(corpus as any).checkInterventionEffectiveness()

      // improvement = 0.52 - 0.5 = 0.02 <= 0.05
      expect(assessment.directiveHistory[0].outcome).toBe('ignored')
    })

    it('should skip evaluation when fewer than 2 steps since baseline', () => {
      const corpus = createCorpus(tree, makeDeps())

      tree.registerBranch('helix-1', 'Test', 0)
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 1 }))

      const assessment = makeBranchAssessment('helix-1', {
        rollingScore: 0.8,
        directiveHistory: [{
          directive: {
            targetHelixId: 'helix-1',
            type: 'guidance',
            urgency: 'medium',
            reason: 'test',
            text: 'Refocus',
            timestamp: Date.now(),
          },
          sentAtStep: 0,
          scoreAtSend: { goalAlignment: 0.5, novelty: 0.5, progress: 0.3 },
          postDirectiveScores: [],
          outcome: 'pending',
        }],
      })
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).interventionBaselines.set('helix-1', {
        score: 0.5,
        type: 'guidance',
        timestamp: Date.now() - 5000,
        step: 0,
      })

      ;(corpus as any).checkInterventionEffectiveness()

      // Only 1 step since baseline — not enough
      expect(assessment.directiveHistory[0].outcome).toBe('pending')
    })

    it('should clear baseline after one-shot measurement', () => {
      const corpus = createCorpus(tree, makeDeps())

      tree.registerBranch('helix-1', 'Test', 0)
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 1 }))
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 2 }))
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 3 }))

      const assessment = makeBranchAssessment('helix-1', {
        rollingScore: 0.7,
        directiveHistory: [{
          directive: {
            targetHelixId: 'helix-1',
            type: 'guidance',
            urgency: 'medium',
            reason: 'test',
            text: 'Refocus',
            timestamp: Date.now(),
          },
          sentAtStep: 0,
          scoreAtSend: { goalAlignment: 0.5, novelty: 0.5, progress: 0.3 },
          postDirectiveScores: [],
          outcome: 'pending',
        }],
      })
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).interventionBaselines.set('helix-1', {
        score: 0.5,
        type: 'guidance',
        timestamp: Date.now() - 5000,
        step: 0,
      })

      ;(corpus as any).checkInterventionEffectiveness()

      expect((corpus as any).interventionBaselines.has('helix-1')).toBe(false)
    })

    it('should only update the first pending directive', () => {
      const corpus = createCorpus(tree, makeDeps())

      tree.registerBranch('helix-1', 'Test', 0)
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 1 }))
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 2 }))
      tree.pushAnnotation('helix-1', makeAnnotation({ axonStep: 3 }))

      const makeRecord = (text: string): DirectiveRecord => ({
        directive: {
          targetHelixId: 'helix-1',
          type: 'guidance',
          urgency: 'medium',
          reason: 'test',
          text,
          timestamp: Date.now(),
        },
        sentAtStep: 0,
        scoreAtSend: { goalAlignment: 0.5, novelty: 0.5, progress: 0.3 },
        postDirectiveScores: [],
        outcome: 'pending',
      })

      const assessment = makeBranchAssessment('helix-1', {
        rollingScore: 0.7,
        directiveHistory: [makeRecord('First'), makeRecord('Second')],
      })
      ;(corpus as any).state.branchAssessments.set('helix-1', assessment)

      ;(corpus as any).interventionBaselines.set('helix-1', {
        score: 0.5,
        type: 'guidance',
        timestamp: Date.now() - 5000,
        step: 0,
      })

      ;(corpus as any).checkInterventionEffectiveness()

      // Only the first pending record should be updated
      expect(assessment.directiveHistory[0].outcome).toBe('effective')
      expect(assessment.directiveHistory[1].outcome).toBe('pending')
    })
  })
})
