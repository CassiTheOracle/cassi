/**
 * Tests for the Self-Edit system — qualitative self-improvement through
 * corpus-level friction detection and edit request generation.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import Database from 'better-sqlite3'

import { SelfEditStore } from '../src/self-edit-store.js'
import { CorpusReflectionProcessor } from '../src/corpus-reflection-processor.js'
import {
  classifyEditAuthority,
  isBehaviorShapingFile,
} from '../src/self-edit-types.js'

import type {
  FrictionSignal,
  OutcomeSignal,
  ReflectionSignal,
  EditRequest,
  EditEvaluation,
  AppliedEdit,
} from '../src/self-edit-types.js'
import type { ILogger } from '../src/vendor/types/interfaces.js'



const noopLogger: ILogger = {
  info: () => {},
  warn: () => {},
  error: () => {},
  debug: () => {},
  child: () => noopLogger,
} as any

function createTestDb(): Database.Database {
  return new Database(':memory:')
}

function makeFriction(overrides: Partial<FrictionSignal> = {}): FrictionSignal {
  return {
    kind: 'repeated-work',
    whatHappened: 'Read the same file three times in one session',
    context: 'Working on feature implementation',
    involvedPaths: ['core/tools/implementations/foo.ts'],
    recurrence: 1,
    observedAt: Date.now(),
    sessionId: `session-${Math.random().toString(36).slice(2, 8)}`,
    ...overrides,
  }
}

function makeEditRequest(overrides: Partial<EditRequest> = {}): EditRequest {
  return {
    id: `req-${Math.random().toString(36).slice(2, 8)}`,
    sourceSessionId: 'session-1',
    editKind: 'skill-update',
    signals: {
      friction: [makeFriction()],
      outcomes: [],
      reflections: [],
    },
    suggestion: {
      targetFiles: ['AGENTS.md'],
      description: 'Update guidance for file reading patterns',
      currentProblem: 'Agents repeatedly re-read files they already have context on',
      proposedImprovement: 'Add explicit guidance to cache file context within a session',
    },
    crossSessionRecurrence: 3,
    createdAt: Date.now(),
    status: 'pending',
    authority: 'local',
    ...overrides,
  }
}


// SelfEditStore Tests

describe('SelfEditStore', () => {
  let db: Database.Database
  let store: SelfEditStore

  beforeEach(() => {
    db = createTestDb()
    store = new SelfEditStore(db, noopLogger)
  })

  afterEach(() => {
    db.close()
  })


  describe('friction signals', () => {
    it('records and retrieves friction signals', () => {
      const signal = makeFriction()
      store.recordFriction(signal)

      const results = store.findFriction({})
      expect(results).toHaveLength(1)
      expect(results[0].kind).toBe('repeated-work')
      expect(results[0].whatHappened).toBe(signal.whatHappened)
    })

    it('filters by friction kind', () => {
      store.recordFriction(makeFriction({ kind: 'repeated-work' }))
      store.recordFriction(makeFriction({ kind: 'wrong-path' }))
      store.recordFriction(makeFriction({ kind: 'repeated-work' }))

      const results = store.findFriction({ kind: 'repeated-work' })
      expect(results).toHaveLength(2)
    })

    it('counts cross-session recurrence', () => {
      store.recordFriction(makeFriction({ kind: 'wrong-path', sessionId: 'session-a' }))
      store.recordFriction(makeFriction({ kind: 'wrong-path', sessionId: 'session-b' }))
      store.recordFriction(makeFriction({ kind: 'wrong-path', sessionId: 'session-c' }))
      // Same session as 'a' — should not count as additional
      store.recordFriction(makeFriction({ kind: 'wrong-path', sessionId: 'session-a' }))

      const count = store.countCrossSessionFriction('wrong-path')
      expect(count).toBe(3) // 3 distinct sessions
    })

    it('filters friction by time window', () => {
      const oldTime = Date.now() - 30 * 24 * 60 * 60 * 1000 // 30 days ago
      store.recordFriction(makeFriction({ observedAt: oldTime }))
      store.recordFriction(makeFriction({ observedAt: Date.now() }))

      const since = Date.now() - 7 * 24 * 60 * 60 * 1000 // 7 days ago
      const results = store.findFriction({ since })
      expect(results).toHaveLength(1)
    })
  })


  describe('edit requests', () => {
    it('submits and retrieves pending requests', () => {
      const request = makeEditRequest()
      store.submitRequest(request)

      const pending = store.getPendingRequests()
      expect(pending).toHaveLength(1)
      expect(pending[0].id).toBe(request.id)
      expect(pending[0].status).toBe('pending')
    })

    it('orders pending requests by cross-session recurrence', () => {
      store.submitRequest(makeEditRequest({ id: 'low', crossSessionRecurrence: 2 }))
      store.submitRequest(makeEditRequest({ id: 'high', crossSessionRecurrence: 10 }))
      store.submitRequest(makeEditRequest({ id: 'mid', crossSessionRecurrence: 5 }))

      const pending = store.getPendingRequests()
      expect(pending[0].id).toBe('high')
      expect(pending[1].id).toBe('mid')
      expect(pending[2].id).toBe('low')
    })

    it('updates request status', () => {
      const request = makeEditRequest()
      store.submitRequest(request)

      store.updateRequestStatus(request.id, 'approved', 'Cross-session pattern confirmed')

      const updated = store.getRequest(request.id)
      expect(updated?.status).toBe('approved')
      expect(updated?.evaluationReason).toBe('Cross-session pattern confirmed')
    })

    it('excludes non-pending requests from pending list', () => {
      store.submitRequest(makeEditRequest({ id: 'a' }))
      store.submitRequest(makeEditRequest({ id: 'b' }))
      store.updateRequestStatus('a', 'approved')

      const pending = store.getPendingRequests()
      expect(pending).toHaveLength(1)
      expect(pending[0].id).toBe('b')
    })
  })


  describe('evaluations', () => {
    it('records and retrieves evaluations', () => {
      const request = makeEditRequest()
      store.submitRequest(request)

      const evaluation: EditEvaluation = {
        requestId: request.id,
        decision: 'approved',
        reasoning: 'This friction pattern has been observed across 5 sessions and the suggested improvement aligns with existing architectural intent.',
        consideredContext: {
          relatedSessionCount: 5,
          recentEditHistory: 'No recent edits to this file',
          touchesLoadBearing: false,
          subconsciousPatterns: ['repeated-work', 'paralysis'],
          priorAttempts: [],
        },
        evaluatedAt: Date.now(),
      }

      store.recordEvaluation(evaluation)

      const evals = store.getEvaluations(request.id)
      expect(evals).toHaveLength(1)
      expect(evals[0].decision).toBe('approved')
      expect(evals[0].reasoning).toContain('5 sessions')
    })
  })


  describe('applied edits', () => {
    it('records applied edits with audit trail', () => {
      const request = makeEditRequest()
      store.submitRequest(request)

      const applied: AppliedEdit = {
        requestId: request.id,
        evaluationId: 'eval-1',
        filesModified: ['AGENTS.md'],
        commitSha: 'abc123',
        beforeSnapshot: [{ file: 'AGENTS.md', contentHash: 'hash-before' }],
        appliedAt: Date.now(),
      }

      store.recordAppliedEdit(applied)

      const history = store.getFileEditHistory('AGENTS.md')
      expect(history).toHaveLength(1)
      expect(history[0].commitSha).toBe('abc123')
    })

    it('tracks reverted edits', () => {
      // Need parent request for foreign key
      store.submitRequest(makeEditRequest({ id: 'req-1' }))

      const applied: AppliedEdit = {
        requestId: 'req-1',
        evaluationId: 'eval-1',
        filesModified: ['AGENTS.md'],
        commitSha: 'abc123',
        beforeSnapshot: [{ file: 'AGENTS.md', contentHash: 'hash-before' }],
        appliedAt: Date.now() - 60000,
        revertedAt: Date.now(),
        revertReason: 'Subsequent sessions showed increased friction in this area',
        revertCommitSha: 'def456',
      }

      store.recordAppliedEdit(applied)

      const recent = store.getRecentEdits()
      expect(recent).toHaveLength(1)
      expect(recent[0].revertedAt).toBeDefined()
      expect(recent[0].revertReason).toContain('increased friction')
    })
  })


  describe('stats', () => {
    it('produces accurate aggregate statistics', () => {
      // Record some friction
      store.recordFriction(makeFriction({ kind: 'repeated-work' }))
      store.recordFriction(makeFriction({ kind: 'repeated-work' }))
      store.recordFriction(makeFriction({ kind: 'wrong-path' }))

      // Submit some requests
      store.submitRequest(makeEditRequest({ id: 'r1' }))
      store.submitRequest(makeEditRequest({ id: 'r2' }))
      store.updateRequestStatus('r1', 'approved')

      const stats = store.getStats()
      expect(stats.totalFrictionSignals).toBe(3)
      expect(stats.totalEditRequests).toBe(2)
      expect(stats.pendingRequests).toBe(1)
      expect(stats.approvedEdits).toBe(1)
      expect(stats.topFrictionKinds[0].kind).toBe('repeated-work')
      expect(stats.topFrictionKinds[0].count).toBe(2)
    })
  })
})


// CorpusReflectionProcessor Tests

describe('CorpusReflectionProcessor', () => {
  let db: Database.Database
  let store: SelfEditStore
  let processor: CorpusReflectionProcessor

  beforeEach(() => {
    db = createTestDb()
    store = new SelfEditStore(db, noopLogger)
    processor = new CorpusReflectionProcessor(store, noopLogger, {
      minCrossSessionRecurrence: 2, // Lower threshold for testing
      aggregationIntervalMs: 100_000, // Don't auto-aggregate in tests
    })
  })

  afterEach(() => {
    processor.stop()
    db.close()
  })


  it('records manually submitted friction', () => {
    const signal = makeFriction({ kind: 'misleading-guidance' })
    processor.submitFriction(signal)

    const found = store.findFriction({ kind: 'misleading-guidance' })
    expect(found).toHaveLength(1)
  })

  it('submits manual edit requests', () => {
    const request = makeEditRequest()
    processor.submitEditRequest(request)

    const pending = processor.getPendingRequests()
    expect(pending).toHaveLength(1)
  })

  it('returns empty stats for fresh system', () => {
    const stats = processor.getStats()
    expect(stats.totalFrictionSignals).toBe(0)
    expect(stats.totalEditRequests).toBe(0)
  })

  it('tracks stats across multiple operations', () => {
    // Simulate a session where friction is observed
    processor.submitFriction(makeFriction({ kind: 'wrong-path', sessionId: 'a' }))
    processor.submitFriction(makeFriction({ kind: 'wrong-path', sessionId: 'b' }))
    processor.submitFriction(makeFriction({ kind: 'wrong-path', sessionId: 'c' }))

    const stats = processor.getStats()
    expect(stats.totalFrictionSignals).toBe(3)
    expect(stats.topFrictionKinds.some(k => k.kind === 'wrong-path')).toBe(true)
  })

  it('enforces cassi-only authority for behavior-shaping edits', () => {
    const request = makeEditRequest({
      editKind: 'agents-update',
      authority: 'local', // Try to claim local authority
      suggestion: {
        targetFiles: ['AGENTS.md'],
        description: 'Update guidance',
        currentProblem: 'Guidance is misleading',
        proposedImprovement: 'Fix guidance',
      },
    })

    // Submit re-classifies authority — you can't spoof it
    processor.submitEditRequest(request)
    const pending = processor.getPendingRequests()
    expect(pending[0].authority).toBe('cassi-only')
  })

  it('allows local authority for operational config edits', () => {
    const request = makeEditRequest({
      editKind: 'config-update',
      suggestion: {
        targetFiles: ['core/config/defaults.ts'],
        description: 'Adjust timeout',
        currentProblem: 'Timeout too short',
        proposedImprovement: 'Increase timeout',
      },
    })

    expect(processor.canApplyLocally(request)).toBe(true)
  })

  it('blocks local application of behavior-shaping edits', () => {
    const request = makeEditRequest({
      editKind: 'skill-update',
      suggestion: {
        targetFiles: ['.opencode/skill/agent-dev-coder/SKILL.md'],
        description: 'Update skill',
        currentProblem: 'Skill is incomplete',
        proposedImprovement: 'Add more guidance',
      },
    })

    expect(processor.canApplyLocally(request)).toBe(false)
  })
})


// Authority Boundary Tests — The One Rule

describe('Edit Authority Boundary', () => {
  describe('isBehaviorShapingFile', () => {
    it('classifies AGENTS.md as behavior-shaping', () => {
      expect(isBehaviorShapingFile('AGENTS.md')).toBe(true)
      expect(isBehaviorShapingFile('/home/user/project/AGENTS.md')).toBe(true)
    })

    it('classifies skill files as behavior-shaping', () => {
      expect(isBehaviorShapingFile('.opencode/skill/agent-dev-coder/SKILL.md')).toBe(true)
      expect(isBehaviorShapingFile('.claude/skills/gitnexus/gitnexus-exploring/SKILL.md')).toBe(true)
    })

    it('classifies helix postures as behavior-shaping', () => {
      expect(isBehaviorShapingFile('core/intelligence/helix/helix-postures.ts')).toBe(true)
      expect(isBehaviorShapingFile('core/intelligence/helix/helix-posture-runner.ts')).toBe(true)
    })

    it('classifies constellation templates as behavior-shaping', () => {
      expect(isBehaviorShapingFile('core/intelligence/constellation/templates.ts')).toBe(true)
    })

    it('classifies flex posture as behavior-shaping', () => {
      expect(isBehaviorShapingFile('core/intelligence/constellation/flex-posture.ts')).toBe(true)
    })

    it('does NOT classify operational code as behavior-shaping', () => {
      expect(isBehaviorShapingFile('core/tools/implementations/bash.ts')).toBe(false)
      expect(isBehaviorShapingFile('core/config/defaults.ts')).toBe(false)
      expect(isBehaviorShapingFile('core/intelligence/budget-monitor.ts')).toBe(false)
      expect(isBehaviorShapingFile('core/intelligence/constellation/self-edit-store.ts')).toBe(false)
    })

    it('does NOT classify test files as behavior-shaping', () => {
      expect(isBehaviorShapingFile('tests/self-edit.test.ts')).toBe(false)
    })
  })

  describe('classifyEditAuthority', () => {
    it('always requires Cassi for skill/agents/prompt edit kinds', () => {
      expect(classifyEditAuthority('skill-update', ['anything.ts'])).toBe('cassi-only')
      expect(classifyEditAuthority('agents-update', ['anything.ts'])).toBe('cassi-only')
      expect(classifyEditAuthority('prompt-update', ['anything.ts'])).toBe('cassi-only')
    })

    it('requires Cassi for code-update targeting behavior files', () => {
      expect(classifyEditAuthority('code-update', ['core/intelligence/helix/helix-postures.ts'])).toBe('cassi-only')
    })

    it('allows local for config-update targeting operational files', () => {
      expect(classifyEditAuthority('config-update', ['core/config/defaults.ts'])).toBe('local')
    })

    it('allows local for tool-update targeting implementation files', () => {
      expect(classifyEditAuthority('tool-update', ['core/tools/implementations/bash.ts'])).toBe('local')
    })

    it('requires Cassi if ANY target file is behavior-shaping', () => {
      // Mix of operational and behavior-shaping
      expect(classifyEditAuthority('code-update', [
        'core/config/defaults.ts',
        'core/intelligence/helix/helix-postures.ts',
      ])).toBe('cassi-only')
    })
  })
})
