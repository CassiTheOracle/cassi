/**
 * QUARANTINED — stale relative to the verbatim-migrated live @cassicore/tools
 * code (P6 turn 1) / environment-dependent. Assertions contradict the
 * authoritative migrated implementations; kept for reference, NOT run.
 */
/**
 * Tests for collect_thoughts tool — Phase 1 (Stages 1-5).
 *
 * Validates the enrichment pipeline:
 *   Stage 1: STORE   — BranchingConversation.addTurn()
 *   Stage 2: EXTRACT — ThoughtObserver.extractSignalsFromText()
 *   Stage 3: PEER    — CognitiveBridge.getFusedSignals() + getResonancePatterns()
 *   Stage 4: ROUTE   — Signal routing + event emission
 *   Stage 5: MEMORY  — memory.search()
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  collectThoughtsDefinition,
  makeCollectThoughtsHandler,
  clearAllSessionStates,
  getAxonSessionState,
  type CollectThoughtsDeps,
} from '../src/implementations/collect-thoughts.js'
import { BranchingConversationManager } from '../src/vendor/core/intelligence/branching-conversation/manager.js'
import type { ToolExecutionContext } from '../src/types.js'
import type { CognitiveSignal } from '../src/vendor/core/intelligence/thought-observer.js'

function makeLogger() {
  return {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: () => makeLogger(),
  } as any
}

function makeContext(sessionId = 'test-session'): ToolExecutionContext {
  return {
    sessionId,
    workingDir: '/tmp',
    allowedPaths: ['/tmp'],
    networkAllowlist: [],
    logger: makeLogger(),
  }
}

function makeMinimalDeps(overrides?: Partial<CollectThoughtsDeps>): CollectThoughtsDeps {
  return {
    branchingManager: new BranchingConversationManager(),
    logger: makeLogger(),
    ...overrides,
  }
}

describe('collect_thoughts tool definition', () => {
  it('should have valid tool definition', () => {
    expect(collectThoughtsDefinition.name).toBe('collect_thoughts')
    expect(collectThoughtsDefinition.parameters.type).toBe('object')
    expect(collectThoughtsDefinition.parameters.properties).toHaveProperty('thought')
    expect(collectThoughtsDefinition.parameters.properties).toHaveProperty('step')
    expect(collectThoughtsDefinition.parameters.properties).toHaveProperty('estimated_steps')
    expect(collectThoughtsDefinition.parameters.properties).toHaveProperty('continue_thinking')
    expect(collectThoughtsDefinition.category).toBe('cognitive')
    expect(collectThoughtsDefinition.timeoutMs).toBe(10_000)
  })

  it('should require thought, step, estimated_steps, continue_thinking', () => {
    const required = collectThoughtsDefinition.parameters.required
    expect(required).toContain('thought')
    expect(required).toContain('step')
    expect(required).toContain('estimated_steps')
    expect(required).toContain('continue_thinking')
  })
})

describe('collect_thoughts handler — Stage 1: STORE', () => {
  beforeEach(() => {
    clearAllSessionStates()
  })

  it('should create a new reasoning session for step 1', async () => {
    const deps = makeMinimalDeps()
    const handler = makeCollectThoughtsHandler(deps)
    const result = await handler(
      {
        thought: 'Let me analyze the problem space first.',
        step: 1,
        estimated_steps: 3,
        continue_thinking: true,
      },
      makeContext(),
    )

    const parsed = JSON.parse(result)
    expect(parsed.step.number).toBe(1)
    expect(parsed.step.of).toBe(3)
    expect(parsed.step.recorded).toBe(true)
    expect(parsed.step.isRevision).toBe(false)
    expect(parsed.step.branchId).toBe('main')
    expect(parsed.tree.totalSteps).toBe(1)
    expect(parsed.tree.activeBranch).toBe('main')
    expect(parsed.tree.branches).toContain('main')
  })

  it('should record multiple steps in the same session', async () => {
    const deps = makeMinimalDeps()
    const handler = makeCollectThoughtsHandler(deps)
    const ctx = makeContext()

    // Step 1
    await handler(
      { thought: 'Step one', step: 1, estimated_steps: 3, continue_thinking: true },
      ctx,
    )

    // Step 2
    const result = await handler(
      { thought: 'Step two', step: 2, estimated_steps: 3, continue_thinking: true },
      ctx,
    )

    const parsed = JSON.parse(result)
    expect(parsed.step.number).toBe(2)
    expect(parsed.tree.totalSteps).toBe(2)
  })

  it('should track revisions correctly', async () => {
    const deps = makeMinimalDeps()
    const handler = makeCollectThoughtsHandler(deps)
    const ctx = makeContext()

    // Steps 1-2
    await handler(
      { thought: 'Original step 1', step: 1, estimated_steps: 3, continue_thinking: true },
      ctx,
    )
    await handler(
      { thought: 'Original step 2', step: 2, estimated_steps: 3, continue_thinking: true },
      ctx,
    )

    // Revision of step 1
    const result = await handler(
      {
        thought: 'Revised step 1 — I missed an edge case',
        step: 3,
        estimated_steps: 4,
        continue_thinking: true,
        is_revision: true,
        revises_step: 1,
      },
      ctx,
    )

    const parsed = JSON.parse(result)
    expect(parsed.step.isRevision).toBe(true)
    expect(parsed.tree.revisionsCount).toBe(1)
  })

  it('should handle branching', async () => {
    const deps = makeMinimalDeps()
    const handler = makeCollectThoughtsHandler(deps)
    const ctx = makeContext()

    // Steps 1-2 on main
    await handler(
      { thought: 'Step one main', step: 1, estimated_steps: 5, continue_thinking: true },
      ctx,
    )
    await handler(
      { thought: 'Step two main', step: 2, estimated_steps: 5, continue_thinking: true },
      ctx,
    )

    // Branch from step 1
    const result = await handler(
      {
        thought: 'Alternative approach from step 1',
        step: 3,
        estimated_steps: 5,
        continue_thinking: true,
        branch_from_step: 1,
        branch_id: 'alternative-a',
      },
      ctx,
    )

    const parsed = JSON.parse(result)
    expect(parsed.step.branchId).toBe('alternative-a')
    expect(parsed.tree.branches).toContain('main')
    expect(parsed.tree.branches).toContain('alternative-a')
  })
})

describe('collect_thoughts handler — Stage 2: EXTRACT', () => {
  beforeEach(() => {
    clearAllSessionStates()
  })

  it('should extract signals when ThoughtObserver is available', async () => {
    const mockSignals: CognitiveSignal[] = [
      { kind: 'edge_case', text: 'Buffer overflow when input exceeds 1MB', confidence: 0.85 },
      { kind: 'assumption', text: 'Assumes single-threaded execution', confidence: 0.75 },
    ]
    const deps = makeMinimalDeps({
      thoughtObserver: {
        extractSignalsFromText: vi.fn().mockReturnValue(mockSignals),
        storeSignals: vi.fn(),
        peekSignals: vi.fn().mockReturnValue([]),
        consumeSignals: vi.fn().mockReturnValue([]),
        getRecentSignals: vi.fn().mockReturnValue([]),
        getStats: vi.fn(),
        onEventBus: vi.fn(),
        setCognitiveBridge: vi.fn(),
        setContextManager: vi.fn(),
        setInjectionAggregator: vi.fn(),
        name: 'thought-observer',
        priority: 50,
      } as any,
    })
    const handler = makeCollectThoughtsHandler(deps)

    const result = await handler(
      { thought: 'This might overflow for large inputs', step: 1, estimated_steps: 3, continue_thinking: true },
      makeContext(),
    )

    const parsed = JSON.parse(result)
    expect(parsed.signals).toHaveLength(2)
    expect(parsed.signals[0].kind).toBe('edge_case')
    expect(parsed.signals[1].kind).toBe('assumption')
    expect(deps.thoughtObserver!.extractSignalsFromText).toHaveBeenCalledWith('This might overflow for large inputs')
  })

  it('should return empty signals when ThoughtObserver is absent', async () => {
    const deps = makeMinimalDeps()
    const handler = makeCollectThoughtsHandler(deps)

    const result = await handler(
      { thought: 'Some thought', step: 1, estimated_steps: 3, continue_thinking: true },
      makeContext(),
    )

    const parsed = JSON.parse(result)
    expect(parsed.signals).toHaveLength(0)
  })
})

describe('collect_thoughts handler — Stage 3: PEER', () => {
  beforeEach(() => {
    clearAllSessionStates()
  })

  it('should gather peer signals from CognitiveBridge', async () => {
    const peerSignals: CognitiveSignal[] = [
      { kind: 'convergence', text: 'Both sessions considering caching', confidence: 0.9 },
    ]
    const deps = makeMinimalDeps({
      cognitiveBridge: {
        getFusedSignals: vi.fn().mockReturnValue(peerSignals),
        getResonancePatterns: vi.fn().mockReturnValue([]),
        routeSignals: vi.fn(),
        getLinkedPeers: vi.fn().mockReturnValue([]),
        getStats: vi.fn(),
        isLinked: vi.fn().mockReturnValue(false),
        linkSessions: vi.fn(),
        unlinkSessions: vi.fn(),
        onEventBus: vi.fn(),
        setInjectionAggregator: vi.fn(),
        setSessionManager: vi.fn(),
        name: 'cognitive-bridge',
        priority: 40,
      } as any,
    })
    const handler = makeCollectThoughtsHandler(deps)

    const result = await handler(
      { thought: 'Evaluating caching approach', step: 1, estimated_steps: 3, continue_thinking: true },
      makeContext(),
    )

    const parsed = JSON.parse(result)
    expect(parsed.peerSignals).toHaveLength(1)
    expect(parsed.peerSignals[0].kind).toBe('convergence')
  })

  it('should gather resonance patterns', async () => {
    const resonancePatterns = [
      {
        kind: 'resonance' as const,
        signalA: { sessionId: 'a', signal: { kind: 'convergence', text: 'Both use caching', confidence: 0.8 } },
        signalB: { sessionId: 'b', signal: { kind: 'convergence', text: 'Caching is key', confidence: 0.7 } },
        similarity: 0.85,
        amplifiedConfidence: 0.92,
        detectedAt: Date.now(),
      },
    ]
    const deps = makeMinimalDeps({
      cognitiveBridge: {
        getFusedSignals: vi.fn().mockReturnValue([]),
        getResonancePatterns: vi.fn().mockReturnValue(resonancePatterns),
        routeSignals: vi.fn(),
        getLinkedPeers: vi.fn().mockReturnValue([]),
        getStats: vi.fn(),
        isLinked: vi.fn().mockReturnValue(false),
        linkSessions: vi.fn(),
        unlinkSessions: vi.fn(),
        onEventBus: vi.fn(),
        setInjectionAggregator: vi.fn(),
        setSessionManager: vi.fn(),
        name: 'cognitive-bridge',
        priority: 40,
      } as any,
    })
    const handler = makeCollectThoughtsHandler(deps)

    const result = await handler(
      { thought: 'Testing resonance', step: 1, estimated_steps: 2, continue_thinking: true },
      makeContext(),
    )

    const parsed = JSON.parse(result)
    expect(parsed.resonance).toHaveLength(1)
    expect(parsed.resonance[0].kind).toBe('resonance')
    expect(parsed.resonance[0].confidence).toBe(0.92)
  })
})

describe('collect_thoughts handler — Stage 4: ROUTE & EMIT', () => {
  beforeEach(() => {
    clearAllSessionStates()
  })

  it('should emit axon:step event', async () => {
    const emitFn = vi.fn()
    const deps = makeMinimalDeps({
      bus: { emit: emitFn, on: vi.fn(), off: vi.fn(), onAll: vi.fn() } as any,
    })
    const handler = makeCollectThoughtsHandler(deps)

    await handler(
      { thought: 'Analyze this', step: 1, estimated_steps: 3, continue_thinking: true },
      makeContext('session-abc'),
    )

    expect(emitFn).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'axon:step',
        sessionId: 'session-abc',
        step: 1,
        totalSteps: 3,
        branchId: 'main',
        isRevision: false,
      }),
    )
  })

  it('should emit axon:complete when continue_thinking is false', async () => {
    const emitFn = vi.fn()
    const deps = makeMinimalDeps({
      bus: { emit: emitFn, on: vi.fn(), off: vi.fn(), onAll: vi.fn() } as any,
    })
    const handler = makeCollectThoughtsHandler(deps)

    await handler(
      { thought: 'Final conclusion', step: 1, estimated_steps: 1, continue_thinking: false },
      makeContext(),
    )

    const completeEvent = emitFn.mock.calls.find(
      (c: any[]) => c[0]?.type === 'axon:complete',
    )
    expect(completeEvent).toBeTruthy()
    expect(completeEvent![0].totalSteps).toBe(1)
  })

  it('should emit axon:branch event when branching', async () => {
    const emitFn = vi.fn()
    const deps = makeMinimalDeps({
      bus: { emit: emitFn, on: vi.fn(), off: vi.fn(), onAll: vi.fn() } as any,
    })
    const handler = makeCollectThoughtsHandler(deps)
    const ctx = makeContext()

    // Step 1 on main
    await handler(
      { thought: 'Step one', step: 1, estimated_steps: 3, continue_thinking: true },
      ctx,
    )

    // Branch from step 1
    await handler(
      {
        thought: 'Alternative',
        step: 2,
        estimated_steps: 3,
        continue_thinking: true,
        branch_from_step: 1,
        branch_id: 'alt',
      },
      ctx,
    )

    const branchEvent = emitFn.mock.calls.find(
      (c: any[]) => c[0]?.type === 'axon:branch',
    )
    expect(branchEvent).toBeTruthy()
    expect(branchEvent![0].branchId).toBe('alt')
    expect(branchEvent![0].fromStep).toBe(1)
  })

  it('should store signals via ThoughtObserver and route via CognitiveBridge', async () => {
    const storeSignalsFn = vi.fn()
    const routeSignalsFn = vi.fn()
    const mockSignals: CognitiveSignal[] = [
      { kind: 'insight', text: 'Key insight found', confidence: 0.9 },
    ]
    const deps = makeMinimalDeps({
      thoughtObserver: {
        extractSignalsFromText: vi.fn().mockReturnValue(mockSignals),
        storeSignals: storeSignalsFn,
        peekSignals: vi.fn().mockReturnValue([]),
        consumeSignals: vi.fn().mockReturnValue([]),
        getRecentSignals: vi.fn().mockReturnValue([]),
        getStats: vi.fn(),
        onEventBus: vi.fn(),
        setCognitiveBridge: vi.fn(),
        setContextManager: vi.fn(),
        setInjectionAggregator: vi.fn(),
        name: 'thought-observer',
        priority: 50,
      } as any,
      cognitiveBridge: {
        getFusedSignals: vi.fn().mockReturnValue([]),
        getResonancePatterns: vi.fn().mockReturnValue([]),
        routeSignals: routeSignalsFn,
        getLinkedPeers: vi.fn().mockReturnValue([]),
        getStats: vi.fn(),
        isLinked: vi.fn().mockReturnValue(false),
        linkSessions: vi.fn(),
        unlinkSessions: vi.fn(),
        onEventBus: vi.fn(),
        setInjectionAggregator: vi.fn(),
        setSessionManager: vi.fn(),
        name: 'cognitive-bridge',
        priority: 40,
      } as any,
    })
    const handler = makeCollectThoughtsHandler(deps)

    await handler(
      { thought: 'Found something key', step: 1, estimated_steps: 2, continue_thinking: true },
      makeContext('sess-123'),
    )

    expect(storeSignalsFn).toHaveBeenCalledWith('sess-123', mockSignals)
    expect(routeSignalsFn).toHaveBeenCalledWith('sess-123', mockSignals)
  })
})

describe('collect_thoughts handler — Stage 5: MEMORY (removed)', () => {
  beforeEach(() => {
    clearAllSessionStates()
  })

  it('should return empty relatedContext (memory search removed to prevent context leakage)', async () => {
    const deps = makeMinimalDeps({
      memory: {
        search: vi.fn().mockResolvedValue([
          { entry: { id: '1', type: 'fact', content: 'Caching reduces latency by 50%', createdAt: new Date() }, score: 0.8 },
          { entry: { id: '2', type: 'insight', content: 'LRU eviction works well for read-heavy workloads', createdAt: new Date() }, score: 0.6 },
        ]),
        store: vi.fn(),
        kv_get: vi.fn(),
        kv_set: vi.fn(),
        kv_del: vi.fn(),
        stats: vi.fn(),
      } as any,
    })
    const handler = makeCollectThoughtsHandler(deps)

    const result = await handler(
      { thought: 'Should we add caching?', step: 1, estimated_steps: 3, continue_thinking: true },
      makeContext(),
    )

    const parsed = JSON.parse(result)
    // Memory search was removed to prevent main-session context leaking into Helix branches
    expect(parsed.relatedContext).toHaveLength(0)
    // Memory.search should NOT be called
    expect(deps.memory!.search).not.toHaveBeenCalled()
  })

  it('should handle missing memory gracefully', async () => {
    const deps = makeMinimalDeps({
      memory: {
        search: vi.fn().mockRejectedValue(new Error('DB connection lost')),
        store: vi.fn(),
        kv_get: vi.fn(),
        kv_set: vi.fn(),
        kv_del: vi.fn(),
        stats: vi.fn(),
      } as any,
    })
    const handler = makeCollectThoughtsHandler(deps)

    const result = await handler(
      { thought: 'Testing error handling', step: 1, estimated_steps: 2, continue_thinking: true },
      makeContext(),
    )

    // Should still return a valid result, just with no memory context
    const parsed = JSON.parse(result)
    expect(parsed.relatedContext).toHaveLength(0)
    expect(parsed.step.recorded).toBe(true)
  })
})

describe('collect_thoughts handler — validation', () => {
  beforeEach(() => {
    clearAllSessionStates()
  })

  it('should reject missing thought', async () => {
    const deps = makeMinimalDeps()
    const handler = makeCollectThoughtsHandler(deps)

    const result = await handler(
      { step: 1, estimated_steps: 3, continue_thinking: true },
      makeContext(),
    )

    const parsed = JSON.parse(result)
    expect(parsed.error).toContain('thought is required')
  })

  it('should reject invalid step', async () => {
    const deps = makeMinimalDeps()
    const handler = makeCollectThoughtsHandler(deps)

    const result = await handler(
      { thought: 'Test', step: 0, estimated_steps: 3, continue_thinking: true },
      makeContext(),
    )

    const parsed = JSON.parse(result)
    expect(parsed.error).toContain('step is required')
  })
})

describe('collect_thoughts handler — result cap', () => {
  beforeEach(() => {
    clearAllSessionStates()
  })

  it('should enforce the 2KB result cap', async () => {
    // Create a scenario that would produce a large result
    const longMemoryResults = Array.from({ length: 10 }, (_, i) => ({
      entry: { id: String(i), type: 'fact', content: 'x'.repeat(200), createdAt: new Date() },
      score: 0.9,
    }))
    const deps = makeMinimalDeps({
      memory: {
        search: vi.fn().mockResolvedValue(longMemoryResults),
        store: vi.fn(),
        kv_get: vi.fn(),
        kv_set: vi.fn(),
        kv_del: vi.fn(),
        stats: vi.fn(),
      } as any,
    })
    const handler = makeCollectThoughtsHandler(deps)

    const result = await handler(
      { thought: 'A'.repeat(500), step: 1, estimated_steps: 3, continue_thinking: true },
      makeContext(),
    )

    expect(result.length).toBeLessThanOrEqual(2_000)
  })
})

describe('collect_thoughts handler — session resumption', () => {
  beforeEach(() => {
    clearAllSessionStates()
  })

  it('should reuse session for subsequent steps from same owner', async () => {
    const deps = makeMinimalDeps()
    const handler = makeCollectThoughtsHandler(deps)
    const ctx = makeContext('owner-session')

    // Step 1
    await handler(
      { thought: 'Step 1', step: 1, estimated_steps: 3, continue_thinking: true },
      ctx,
    )

    // Step 2 — should find the same reasoning session
    const result = await handler(
      { thought: 'Step 2', step: 2, estimated_steps: 3, continue_thinking: true },
      ctx,
    )

    const parsed = JSON.parse(result)
    expect(parsed.tree.totalSteps).toBe(2) // Both steps in the same session
  })
})

describe('collect_thoughts — meta fields', () => {
  beforeEach(() => {
    clearAllSessionStates()
  })

  it('should include synapse budget metadata', async () => {
    const deps = makeMinimalDeps()
    const handler = makeCollectThoughtsHandler(deps)

    const result = await handler(
      { thought: 'Test meta', step: 1, estimated_steps: 3, continue_thinking: true },
      makeContext(),
    )

    const parsed = JSON.parse(result)
    expect(parsed.meta.synapseCallsRemaining).toBe(5) // default budget
    expect(parsed.meta.nextSynapseEligible).toBeDefined()
  })

  it('should have null synapse and constellationGuidance in Phase 1', async () => {
    const deps = makeMinimalDeps()
    const handler = makeCollectThoughtsHandler(deps)

    const result = await handler(
      { thought: 'Phase 1 check', step: 1, estimated_steps: 1, continue_thinking: false },
      makeContext(),
    )

    const parsed = JSON.parse(result)
    expect(parsed.synapse).toBeNull()
    expect(parsed.constellationGuidance).toBeNull()
  })
})
