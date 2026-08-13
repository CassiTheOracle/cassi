/**
 * Corpus + CorpusTree Tests
 *
 * Tests the Constellation-level cognitive organizer and its shared reasoning tree.
 * Follows the same mock pattern as brainstem.test.ts.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { CorpusTree } from '../src/corpus-tree.js'
import { Corpus, createCorpus } from '../src/corpus.js'
import type { BrainstemAnnotation, WorkUnitAnnotation, DetectedPattern } from '../src/vendor/helix/brainstem-types.js'
import type { CorpusDeps, CorpusConfig, ICorpusTree, CorpusDirective } from '../src/corpus-types.js'
import type { SpawnRequest } from '../src/types.js'


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
    ...overrides,
  }
}

function makeLogger() {
  const log = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn(() => log),
  }
  return log
}

function makeSpawnRequest(overrides: Partial<SpawnRequest> = {}): SpawnRequest {
  return {
    requestId: `req-${Math.random().toString(36).slice(2, 8)}`,
    requestingHelixId: 'helix-0',
    requestingPosture: 'unity',
    targetDepth: 1,
    goal: 'Some work',
    status: 'pending',
    timestamp: Date.now(),
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
    logger: makeLogger() as any,
    goal: 'Implement feature X',
    constellationId: 'constellation-test-1',
    ...overrides,
  }
}

// CorpusTree Tests

describe('CorpusTree', () => {
  let tree: CorpusTree
  let logger: ReturnType<typeof makeLogger>

  beforeEach(() => {
    logger = makeLogger()
    tree = new CorpusTree(logger as any)
  })

  describe('registerBranch', () => {
    it('registers a new branch', () => {
      tree.registerBranch('helix-0', 'Build tests', 0)
      const branch = tree.getBranch('helix-0')

      expect(branch).toBeDefined()
      expect(branch!.helixId).toBe('helix-0')
      expect(branch!.goal).toBe('Build tests')
      expect(branch!.depth).toBe(0)
      expect(branch!.status).toBe('active')
      expect(branch!.steps).toHaveLength(0)
    })

    it('registers with parentId', () => {
      tree.registerBranch('helix-0', 'Root', 0)
      tree.registerBranch('helix-1', 'Child', 1, 'helix-0')

      const child = tree.getBranch('helix-1')
      expect(child!.parentId).toBe('helix-0')
      expect(child!.depth).toBe(1)
    })

    it('throws on duplicate helixId', () => {
      tree.registerBranch('helix-0', 'Root', 0)
      expect(() => tree.registerBranch('helix-0', 'Duplicate', 0)).toThrow(
        /already registered/,
      )
    })
  })

  describe('pushAnnotation', () => {
    it('pushes to existing branch', () => {
      tree.registerBranch('helix-0', 'Root', 0)
      const ann = makeAnnotation({ score: 0.8 })
      tree.pushAnnotation('helix-0', ann)

      const branch = tree.getBranch('helix-0')!
      expect(branch.steps).toHaveLength(1)
      expect(branch.steps[0].annotation.score).toBe(0.8)
      expect(branch.steps[0].pushedAt).toBeGreaterThan(0)
    })

    it('auto-registers branch if not registered', () => {
      tree.pushAnnotation('helix-unknown', makeAnnotation())

      const branch = tree.getBranch('helix-unknown')
      expect(branch).toBeDefined()
      expect(branch!.goal).toBe('unknown')
      expect(branch!.steps).toHaveLength(1)
    })

    it('accumulates steps', () => {
      tree.registerBranch('helix-0', 'Root', 0)
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.5 }))
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.7 }))
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.9 }))

      expect(tree.getBranch('helix-0')!.steps).toHaveLength(3)
    })
  })

  describe('closeBranch', () => {
    it('closes an existing branch', () => {
      tree.registerBranch('helix-0', 'Root', 0)
      tree.closeBranch('helix-0', 'completed')

      const branch = tree.getBranch('helix-0')!
      expect(branch.status).toBe('completed')
      expect(branch.closedAt).toBeGreaterThan(0)
    })

    it('is a no-op for non-existent branch', () => {
      tree.closeBranch('helix-nonexistent', 'failed')
      // No throw, just a log
      expect(tree.getBranch('helix-nonexistent')).toBeUndefined()
    })
  })

  describe('getAllBranches', () => {
    it('returns all branches', () => {
      tree.registerBranch('helix-0', 'A', 0)
      tree.registerBranch('helix-1', 'B', 0)
      tree.registerBranch('helix-2', 'C', 1, 'helix-0')

      expect(tree.getAllBranches()).toHaveLength(3)
    })
  })

  describe('pendingStepCount', () => {
    it('returns 0 when no steps', () => {
      tree.registerBranch('helix-0', 'Root', 0)
      expect(tree.pendingStepCount(new Map())).toBe(0)
    })

    it('counts all steps when no cursors', () => {
      tree.registerBranch('helix-0', 'A', 0)
      tree.registerBranch('helix-1', 'B', 0)
      tree.pushAnnotation('helix-0', makeAnnotation())
      tree.pushAnnotation('helix-0', makeAnnotation())
      tree.pushAnnotation('helix-1', makeAnnotation())

      expect(tree.pendingStepCount(new Map())).toBe(3)
    })

    it('subtracts cursor positions', () => {
      tree.registerBranch('helix-0', 'A', 0)
      tree.pushAnnotation('helix-0', makeAnnotation())
      tree.pushAnnotation('helix-0', makeAnnotation())
      tree.pushAnnotation('helix-0', makeAnnotation())

      const cursors = new Map([['helix-0', 2]])
      expect(tree.pendingStepCount(cursors)).toBe(1)
    })
  })

  describe('totalStepCount / activeBranchCount', () => {
    it('counts correctly', () => {
      tree.registerBranch('helix-0', 'A', 0)
      tree.registerBranch('helix-1', 'B', 0)
      tree.pushAnnotation('helix-0', makeAnnotation())
      tree.pushAnnotation('helix-0', makeAnnotation())
      tree.pushAnnotation('helix-1', makeAnnotation())
      tree.closeBranch('helix-1', 'completed')

      expect(tree.totalStepCount()).toBe(3)
      expect(tree.activeBranchCount()).toBe(1)
    })
  })

  describe('getSnapshot', () => {
    it('produces a full snapshot', () => {
      tree.registerBranch('helix-0', 'Root', 0)
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.6 }))
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.8 }))

      const snapshot = tree.getSnapshot()
      expect(snapshot.branches).toHaveLength(1)
      expect(snapshot.totalSteps).toBe(2)
      expect(snapshot.activeBranches).toBe(1)

      const branch = snapshot.branches[0]
      expect(branch.stepCount).toBe(2)
      expect(branch.latestScore).toBe(0.8)
      expect(branch.averageScore).toBe(0.7)
    })
  })
})


// Corpus Tests

describe('Corpus', () => {
  let tree: CorpusTree
  let deps: CorpusDeps
  let corpus: Corpus

  beforeEach(() => {
    tree = new CorpusTree(makeLogger() as any)
    deps = makeDeps()
    corpus = new Corpus(tree, deps, {
      idlePollMs: 10,             // Fast polling for tests
      llmAnalysisThreshold: 2,    // Low threshold for tests
    })
  })

  afterEach(async () => {
    if (corpus.isRunning()) {
      await corpus.stop()
    }
  })

  describe('lifecycle', () => {
    it('starts and stops', async () => {
      await corpus.start()
      expect(corpus.isRunning()).toBe(true)

      await corpus.stop()
      expect(corpus.isRunning()).toBe(false)
    })

    it('does nothing when disabled', async () => {
      const disabled = new Corpus(tree, deps, { enabled: false })
      await disabled.start()
      expect(disabled.isRunning()).toBe(false)
    })

    it('warns on double start', async () => {
      await corpus.start()
      await corpus.start()
      // Second start logs a warning, doesn't crash
      expect(corpus.isRunning()).toBe(true)
      await corpus.stop()
    })
  })

  describe('registerBrainstem', () => {
    it('registers a brainstem for directive delivery', () => {
      const mockBrainstem = { onCorpusDirective: vi.fn() }
      corpus.registerBrainstem('helix-0', mockBrainstem)
      // No error — stored internally
    })
  })

  describe('processNewSteps + branch assessments', () => {
    it('processes annotations and produces branch assessments', async () => {
      tree.registerBranch('helix-0', 'Test', 0)
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.8, annotation: 'implementation' as any }))
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.9, annotation: 'implementation' as any }))

      // Start corpus and let it process
      await corpus.start()
      await new Promise(r => setTimeout(r, 100))
      await corpus.stop()

      const result = corpus.getResult()
      expect(result.branchAssessments).toHaveLength(1)
      expect(result.branchAssessments[0].helixId).toBe('helix-0')
      expect(result.branchAssessments[0].status).toBe('productive')
      expect(result.branchAssessments[0].rollingScore).toBeGreaterThan(0.7)
    })

    it('flags struggling branches with low scores', async () => {
      tree.registerBranch('helix-0', 'Struggling', 0)
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.2 }))
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.3 }))

      await corpus.start()
      await new Promise(r => setTimeout(r, 100))
      await corpus.stop()

      const result = corpus.getResult()
      expect(result.branchAssessments[0].status).toBe('struggling')
    })

    it('flags drifting branches', async () => {
      tree.registerBranch('helix-0', 'Drifting', 0)
      // 5 consecutive drift annotations
      for (let i = 0; i < 5; i++) {
        tree.pushAnnotation('helix-0', makeAnnotation({
          score: 0.6,
          annotation: 'drift' as WorkUnitAnnotation,
        }))
      }

      await corpus.start()
      await new Promise(r => setTimeout(r, 100))
      await corpus.stop()

      const result = corpus.getResult()
      expect(result.branchAssessments[0].status).toBe('drifting')
    })
  })

  describe('cross-pattern detection', () => {
    it('detects asymmetric progress', async () => {
      tree.registerBranch('helix-0', 'Fast', 1, 'root')
      tree.registerBranch('helix-1', 'Slow', 1, 'root')

      // helix-0 has many steps, helix-1 has few with low scores
      for (let i = 0; i < 5; i++) {
        tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.8 }))
      }
      tree.pushAnnotation('helix-1', makeAnnotation({ score: 0.3 }))

      await corpus.start()
      await new Promise(r => setTimeout(r, 150))
      await corpus.stop()

      const result = corpus.getResult()
      const asymmetric = result.crossPatterns.find(p => p.type === 'asymmetric-progress')
      expect(asymmetric).toBeDefined()
      expect(asymmetric!.helixIds).toContain('helix-0')
      expect(asymmetric!.helixIds).toContain('helix-1')
    })

    it('detects convergence', async () => {
      tree.registerBranch('helix-0', 'A', 0)
      tree.registerBranch('helix-1', 'B', 0)

      // Both branches have high-scoring implementation steps
      for (let i = 0; i < 3; i++) {
        tree.pushAnnotation('helix-0', makeAnnotation({
          score: 0.85,
          annotation: 'implementation' as WorkUnitAnnotation,
        }))
        tree.pushAnnotation('helix-1', makeAnnotation({
          score: 0.9,
          annotation: 'implementation' as WorkUnitAnnotation,
        }))
      }

      await corpus.start()
      await new Promise(r => setTimeout(r, 150))
      await corpus.stop()

      const result = corpus.getResult()
      const conv = result.crossPatterns.find(p => p.type === 'convergence')
      expect(conv).toBeDefined()
    })

    it('de-duplicates patterns', async () => {
      tree.registerBranch('helix-0', 'A', 0)
      tree.registerBranch('helix-1', 'B', 0)

      // Push annotations that would trigger convergence multiple sweeps
      for (let i = 0; i < 6; i++) {
        tree.pushAnnotation('helix-0', makeAnnotation({
          score: 0.85,
          annotation: 'implementation' as WorkUnitAnnotation,
        }))
        tree.pushAnnotation('helix-1', makeAnnotation({
          score: 0.9,
          annotation: 'implementation' as WorkUnitAnnotation,
        }))
      }

      await corpus.start()
      await new Promise(r => setTimeout(r, 200))
      await corpus.stop()

      const result = corpus.getResult()
      const convergenceCount = result.crossPatterns.filter(p => p.type === 'convergence').length
      // Should be de-duplicated to 1 (within 60s window)
      expect(convergenceCount).toBe(1)
    })
  })

  describe('LLM analysis', () => {
    it('calls LLM when threshold reached', async () => {
      tree.registerBranch('helix-0', 'Test', 0)
      // Push enough for threshold (2)
      tree.pushAnnotation('helix-0', makeAnnotation())
      tree.pushAnnotation('helix-0', makeAnnotation())

      // Use 'active' cadence — safety-net mode doesn't trigger on simple step accumulation
      const activeDeps = makeDeps()
      const activeCorpus = new Corpus(tree, activeDeps, {
        idlePollMs: 10,
        llmAnalysisThreshold: 2,
        cadence: 'active',
      })

      await activeCorpus.start()
      await new Promise(r => setTimeout(r, 150))
      await activeCorpus.stop()

      expect(activeDeps.llm.complete).toHaveBeenCalled()
    })

    it('handles LLM failure gracefully', async () => {
      const failingDeps = makeDeps({
        llm: {
          complete: vi.fn().mockRejectedValue(new Error('LLM timeout')),
        },
      })
      const failCorpus = new Corpus(tree, failingDeps, {
        idlePollMs: 10,
        llmAnalysisThreshold: 1,
      })

      tree.registerBranch('helix-0', 'Test', 0)
      tree.pushAnnotation('helix-0', makeAnnotation())

      await failCorpus.start()
      await new Promise(r => setTimeout(r, 150))
      await failCorpus.stop()

      // Should not crash — loop continues
      expect(failCorpus.isRunning()).toBe(false)
    })

    it('parses INTERVENTION directives from LLM', async () => {
      const mockBrainstem = { onCorpusDirective: vi.fn() }
      corpus.registerBrainstem('helix-0', mockBrainstem)

      const interventionDeps = makeDeps({
        llm: {
          complete: vi.fn().mockResolvedValue({
            content: 'ASSESSMENT: helix-0 is struggling\nINTERVENTION[helix-0]: redirect:high:Focus on core implementation instead of exploration\nSYNTHESIS: NONE',
            truncated: false,
          }),
        },
      })
      const interventionCorpus = new Corpus(tree, interventionDeps, {
        idlePollMs: 10,
        llmAnalysisThreshold: 1,
        cadence: 'active',
        useToolBasedAnalysis: false,
      })
      interventionCorpus.registerBrainstem('helix-0', mockBrainstem)

      tree.registerBranch('helix-0', 'Test', 0)
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.3 }))

      await interventionCorpus.start()
      await new Promise(r => setTimeout(r, 200))
      await interventionCorpus.stop()

      expect(mockBrainstem.onCorpusDirective).toHaveBeenCalled()
      const directive: CorpusDirective = mockBrainstem.onCorpusDirective.mock.calls[0][0]
      expect(directive.targetHelixId).toBe('helix-0')
      expect(directive.type).toBe('redirect')
      expect(directive.urgency).toBe('high')
    })
  })

  describe('spawn evaluation', () => {
    it('approves a spawn request via LLM', async () => {
      const approvalDeps = makeDeps({
        llm: {
          complete: vi.fn().mockResolvedValue({
            content: 'DECISION: APPROVED\nREASON: Goal is clear and non-redundant\nSUGGESTED_TEMPLATE: NONE\nSUGGESTED_GOAL: NONE',
            truncated: false,
          }),
        },
      })
      const approvalCorpus = new Corpus(tree, approvalDeps)

      const decision = await approvalCorpus.evaluateSpawnRequest(makeSpawnRequest({
        requestId: 'req-1',
        goal: 'Write tests for module X',
      }))

      expect(decision.approved).toBe(true)
      expect(decision.reason).toContain('non-redundant')
    })

    it('rejects a spawn request via LLM', async () => {
      const rejectDeps = makeDeps({
        llm: {
          complete: vi.fn().mockResolvedValue({
            content: 'DECISION: REJECTED\nREASON: Too many active branches already\nSUGGESTED_TEMPLATE: NONE\nSUGGESTED_GOAL: NONE',
            truncated: false,
          }),
        },
      })
      const rejectCorpus = new Corpus(tree, rejectDeps)

      const decision = await rejectCorpus.evaluateSpawnRequest(makeSpawnRequest({
        requestId: 'req-2',
        targetDepth: 2,
        goal: 'Duplicate work',
      }))

      expect(decision.approved).toBe(false)
    })

    it('defaults to rejected on LLM failure', async () => {
      const failDeps = makeDeps({
        llm: {
          complete: vi.fn().mockRejectedValue(new Error('timeout')),
        },
      })
      const failCorpus = new Corpus(tree, failDeps)

      const decision = await failCorpus.evaluateSpawnRequest(makeSpawnRequest({
        requestId: 'req-3',
        goal: 'Something',
      }))

      expect(decision.approved).toBe(false)
      expect(decision.reason).toContain('failed')
    })
  })

  describe('getResult', () => {
    it('returns comprehensive result', async () => {
      tree.registerBranch('helix-0', 'A', 0)
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.8 }))
      tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.7 }))

      await corpus.start()
      await new Promise(r => setTimeout(r, 150))
      await corpus.stop()

      const result = corpus.getResult()
      expect(result.tree).toBeDefined()
      expect(result.tree.branches).toHaveLength(1)
      expect(result.branchAssessments).toHaveLength(1)
      expect(result.sweepCount).toBeGreaterThanOrEqual(1)
      expect(result.durationMs).toBeGreaterThan(0)
    })
  })

  describe('factory function', () => {
    it('createCorpus returns a Corpus', () => {
      const c = createCorpus(tree, deps)
      expect(c).toBeInstanceOf(Corpus)
    })
  })

  describe('event emission', () => {
    it('emits corpus:sweep events', async () => {
      const eventBus = { emit: vi.fn() }
      const eventDeps = makeDeps({ eventBus: eventBus as any })
      const eventCorpus = new Corpus(tree, eventDeps, { idlePollMs: 10, llmAnalysisThreshold: 100 })

      tree.registerBranch('helix-0', 'Test', 0)
      tree.pushAnnotation('helix-0', makeAnnotation())

      await eventCorpus.start()
      await new Promise(r => setTimeout(r, 100))
      await eventCorpus.stop()

      const sweepCalls = eventBus.emit.mock.calls.filter(
        (c: any) => c[0]?.type === 'corpus:sweep'
      )
      expect(sweepCalls.length).toBeGreaterThanOrEqual(1)
    })
  })
})


// Shared Thought Tree Tests

describe('Shared Thought Tree', () => {
  let tree: CorpusTree
  let logger: ReturnType<typeof makeLogger>

  beforeEach(() => {
    logger = makeLogger()
    tree = new CorpusTree(logger as any)
  })

  describe('Branch Digests', () => {
    it('stores and retrieves a digest', () => {
      tree.registerBranch('helix-0', 'Build auth', 0)
      tree.updateDigest('helix-0', {
        helixId: 'helix-0',
        goalSummary: 'Build auth',
        approach: 'implementation',
        progress: 0.5,
        filesActive: ['core/auth.ts'],
        keyFindings: ['Found middleware'],
        blockers: [],
        currentStrategy: 'Implementing auth flow',
        rollingScore: 0.8,
        workUnitsProcessed: 5,
        updatedAt: Date.now(),
      })

      const digests = tree.getDigestsExcluding('helix-1')
      expect(digests).toHaveLength(1)
      expect(digests[0].helixId).toBe('helix-0')
      expect(digests[0].approach).toBe('implementation')
    })

    it('excludes the requesting Helix from peer digests', () => {
      tree.registerBranch('helix-0', 'Auth', 0)
      tree.registerBranch('helix-1', 'Tests', 0)
      tree.updateDigest('helix-0', makeDigest('helix-0'))
      tree.updateDigest('helix-1', makeDigest('helix-1'))

      const digests = tree.getDigestsExcluding('helix-0')
      expect(digests).toHaveLength(1)
      expect(digests[0].helixId).toBe('helix-1')
    })

    it('returns relevant digests sorted by file overlap', () => {
      tree.registerBranch('helix-0', 'Auth', 0)
      tree.registerBranch('helix-1', 'Tests', 0)
      tree.registerBranch('helix-2', 'Auth middleware', 0)

      tree.updateDigest('helix-0', makeDigest('helix-0', { filesActive: ['core/auth.ts'] }))
      tree.updateDigest('helix-1', makeDigest('helix-1', { filesActive: ['tests/test.ts'] }))
      tree.updateDigest('helix-2', makeDigest('helix-2', { filesActive: ['core/auth.ts', 'core/middleware.ts'] }))

      const relevant = tree.getRelevantDigests('helix-0')
      // helix-2 should be first (shares core/auth.ts)
      expect(relevant[0].helixId).toBe('helix-2')
    })
  })

  describe('Topic Nodes', () => {
    it('creates a topic', () => {
      const topicId = tree.createTopic('auth middleware', 'helix-0', {
        helixId: 'helix-0',
        content: 'Found auth middleware at core/middleware/auth.ts',
        approach: 'exploration',
        files: ['core/middleware/auth.ts'],
        score: 0.8,
        timestamp: Date.now(),
      })

      expect(topicId).toMatch(/^topic-/)
      const topics = tree.getAllTopics()
      expect(topics).toHaveLength(1)
      expect(topics[0].name).toBe('auth middleware')
      expect(topics[0].createdBy).toBe('helix-0')
    })

    it('adds contributions and detects tension', () => {
      const topicId = tree.createTopic('error handling', 'helix-0', {
        helixId: 'helix-0',
        content: 'Using try-catch with typed errors',
        approach: 'implementation',
        files: ['core/errors.ts'],
        score: 0.7,
        timestamp: Date.now(),
      })

      // Different Helix with a different approach
      tree.contributeTopic(topicId, {
        helixId: 'helix-1',
        content: 'Using Result<T, E> pattern',
        approach: 'revision',
        files: ['core/errors.ts'],
        score: 0.7,
        timestamp: Date.now(),
      })

      const topics = tree.getAllTopics()
      expect(topics[0].contributions).toHaveLength(2)
      expect(topics[0].tensionFlag).toBe(true)
    })

    it('finds topics by file overlap', () => {
      tree.createTopic('auth', 'helix-0', {
        helixId: 'helix-0',
        content: 'Auth work',
        approach: 'implementation',
        files: ['core/auth.ts'],
        score: 0.7,
        timestamp: Date.now(),
      })

      tree.createTopic('tests', 'helix-1', {
        helixId: 'helix-1',
        content: 'Test work',
        approach: 'testing',
        files: ['tests/test.ts'],
        score: 0.7,
        timestamp: Date.now(),
      })

      const related = tree.findRelatedTopics(['core/auth.ts'], [])
      expect(related).toHaveLength(1)
      expect(related[0].name).toBe('auth')
    })
  })

  describe('Strategy Retrospectives', () => {
    it('records and retrieves retrospectives', () => {
      tree.recordRetrospective('helix-0', {
        helixId: 'helix-0',
        fromApproach: 'exploration',
        toApproach: 'implementation',
        reason: 'Score improved after finding the right approach',
        trigger: 'self-organization',
        scoreAtChange: 0.7,
        timestamp: Date.now(),
      })

      const retros = tree.getAllRetrospectives()
      expect(retros).toHaveLength(1)
      expect(retros[0].fromApproach).toBe('exploration')
      expect(retros[0].toApproach).toBe('implementation')
      expect(retros[0].trigger).toBe('self-organization')
    })
  })

  describe('Pattern Library', () => {
    it('elevates and retrieves patterns', () => {
      tree.elevatePattern({
        id: 'pattern-1',
        sourceHelixId: 'helix-0',
        approach: 'research',
        description: 'Deep investigation before implementation works well',
        applicableContext: 'Complex architecture tasks',
        achievedScore: 0.9,
        relevantFiles: ['core/architecture.ts'],
        supportingRetrospectives: ['exploration→research: found more context'],
        elevatedAt: Date.now(),
        referenceCount: 0,
      })

      const patterns = tree.getElevatedPatterns()
      expect(patterns).toHaveLength(1)
      expect(patterns[0].approach).toBe('research')
      expect(patterns[0].achievedScore).toBe(0.9)
    })

    it('auto-elevates patterns when a successful branch closes', () => {
      tree.registerBranch('helix-0', 'Auth work', 0)

      // Add annotations with good scores
      for (let i = 0; i < 5; i++) {
        tree.pushAnnotation('helix-0', makeAnnotation({ score: 0.85 }))
      }

      // Add a digest
      tree.updateDigest('helix-0', makeDigest('helix-0', {
        approach: 'implementation',
        keyFindings: ['Found auth pattern'],
      }))

      // Add a successful retrospective
      tree.recordRetrospective('helix-0', {
        helixId: 'helix-0',
        fromApproach: 'exploration',
        toApproach: 'implementation',
        reason: 'Found the right approach',
        trigger: 'self-organization',
        scoreAtChange: 0.6,
        wasEffective: true,
        timestamp: Date.now(),
      })

      // Close the branch successfully
      tree.closeBranch('helix-0', 'completed')

      const patterns = tree.getElevatedPatterns()
      expect(patterns.length).toBeGreaterThanOrEqual(1)
    })
  })

  describe('Effectiveness Tracking', () => {
    it('records and aggregates effectiveness', () => {
      tree.recordEffectiveness({
        adjustmentType: 'approach-redirect',
        helixId: 'helix-0',
        scoreBefore: 0.3,
        scoreAfter: 0.7,
        stepsDelta: 3,
        improvement: 0.4,
        effective: true,
        measuredAt: Date.now(),
      })

      tree.recordEffectiveness({
        adjustmentType: 'approach-redirect',
        helixId: 'helix-1',
        scoreBefore: 0.5,
        scoreAfter: 0.4,
        stepsDelta: 3,
        improvement: -0.1,
        effective: false,
        measuredAt: Date.now(),
      })

      const stats = tree.getEffectivenessStats()
      const redirectStats = stats.get('approach-redirect')
      expect(redirectStats).toBeDefined()
      expect(redirectStats!.total).toBe(2)
      expect(redirectStats!.effective).toBe(1)
      expect(redirectStats!.avgImprovement).toBeCloseTo(0.15)
    })
  })

  describe('Extended Snapshot', () => {
    it('includes all shared thought tree state', () => {
      tree.registerBranch('helix-0', 'Auth', 0)
      tree.pushAnnotation('helix-0', makeAnnotation())
      tree.updateDigest('helix-0', makeDigest('helix-0'))
      tree.createTopic('auth', 'helix-0', {
        helixId: 'helix-0',
        content: 'Found it',
        approach: 'exploration',
        files: ['core/auth.ts'],
        score: 0.8,
        timestamp: Date.now(),
      })
      tree.recordRetrospective('helix-0', {
        helixId: 'helix-0',
        fromApproach: 'exploration',
        toApproach: 'implementation',
        reason: 'Test',
        trigger: 'self-organization',
        scoreAtChange: 0.7,
        timestamp: Date.now(),
      })

      const snapshot = tree.getSnapshot()

      expect(snapshot.digests).toHaveLength(1)
      expect(snapshot.topics).toHaveLength(1)
      expect(snapshot.retrospectives).toHaveLength(1)
      expect(snapshot.branches[0].digest).toBeDefined()
    })
  })
})



function makeDigest(helixId: string, overrides: Partial<import('../src/corpus-types.js').BranchDigest> = {}): import('../src/corpus-types.js').BranchDigest {
  return {
    helixId,
    goalSummary: `Goal for ${helixId}`,
    approach: 'exploration',
    progress: 0.3,
    filesActive: [],
    keyFindings: [],
    blockers: [],
    currentStrategy: 'Exploring',
    rollingScore: 0.6,
    workUnitsProcessed: 3,
    updatedAt: Date.now(),
    ...overrides,
  }
}
