/**
 * Tests for the Corpus-Workflow strategy integration:
 *   - CorpusStrategyRegistry (registration, matching, run tracking)
 *   - corpusDirectiveStep and corpusAssessStep (new workflow step types)
 *   - Conflict resolution strategy (end-to-end workflow execution)
 *   - Cascade recovery strategy
 *   - Convergence synthesis strategy
 *   - Stuck redecomposition strategy
 *   - Redundancy strategy
 *   - Divergence strategy
 *   - Resource imbalance strategy
 *   - Full registry integration (all 7 pattern types covered)
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { CorpusStrategyRegistry } from '../src/corpus-strategy-registry.js'
import { createConflictResolutionStrategy } from '../src/strategies/conflict-resolution.js'
import { createCascadeRecoveryStrategy } from '../src/strategies/cascade-recovery.js'
import { createConvergenceSynthesisStrategy } from '../src/strategies/convergence-synthesis.js'
import { createStuckRedecompositionStrategy } from '../src/strategies/stuck-redecomposition.js'
import { createRedundancyStrategy } from '../src/strategies/redundancy.js'
import { createDivergenceStrategy } from '../src/strategies/divergence.js'
import { createResourceImbalanceStrategy } from '../src/strategies/resource-imbalance.js'
import {
  WorkflowEngine,
  corpusDirectiveStep,
  corpusAssessStep,
  _resetNodeCounter,
} from '../src/vendor/workflow/index.js'
import type {
  ICorpusDirectiveSender,
  ICorpusStateReader,
} from '../src/vendor/workflow/steps.js'
import type {
  CorpusStrategy,
  CrossHelixPattern,
  CorpusProcessedState,
  StrategyContext,
  ActiveStrategyRun,
} from '../src/corpus-types.js'
import { createInitialProcessedState } from '../src/corpus-types.js'
import type { WorkflowDefinition } from '../src/vendor/types/workflow.js'
import { createWorkflow } from '../src/vendor/workflow/builder.js'
import type { ILogger, IEventBus } from '../src/vendor/types/interfaces.js'
import type { RuntimeEvent } from '../src/vendor/types/events.js'

// Helpers

function createMockLogger(): ILogger {
  const log: ILogger = {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    child: vi.fn(() => log),
  }
  return log
}

function createMockEventBus(): IEventBus {
  return {
    emit: vi.fn(async () => {}),
    on: vi.fn(() => () => {}),
    once: vi.fn(),
    off: vi.fn(),
    listenerCount: vi.fn(() => 0),
    onAll: vi.fn(() => () => {}),
  }
}

function createMockSender(): ICorpusDirectiveSender & { calls: unknown[] } {
  const calls: unknown[] = []
  return {
    calls,
    sendDirective: vi.fn(async (directive) => { calls.push(directive) }),
  }
}

function createMockReader(overrides?: {
  assessments?: Map<string, { status: string; rollingScore: number; filesModified: Set<string> }>
  patterns?: Array<{ type: string; helixIds: string[]; severity: string; description: string }>
  budgets?: Map<string, { consumedSteps: number; maxSteps: number }>
  branches?: Array<{ helixId: string; goal: string; status: string; steps?: unknown[] }>
}): ICorpusStateReader {
  const assessments = overrides?.assessments ?? new Map()
  const patterns = overrides?.patterns ?? []
  const budgets = overrides?.budgets ?? new Map()
  const branches = overrides?.branches ?? []

  return {
    getProcessedState: () => ({
      branchAssessments: assessments,
      crossPatterns: patterns,
      budgets,
    }),
    getTree: () => ({
      getBranch: (id: string) => branches.find(b => b.helixId === id) as any,
      getAllBranches: () => branches as any,
    }),
  }
}

function createPattern(overrides?: Partial<CrossHelixPattern>): CrossHelixPattern {
  return {
    type: 'conflict',
    helixIds: ['helix-a', 'helix-b'],
    severity: 'high',
    description: 'File conflict between helix-a and helix-b',
    detectedAt: Date.now(),
    actedUpon: false,
    ...overrides,
  }
}

function createState(overrides?: Partial<CorpusProcessedState>): CorpusProcessedState {
  return {
    ...createInitialProcessedState(),
    ...overrides,
  }
}

function createEngine() {
  const logger = createMockLogger()
  const eventBus = createMockEventBus()
  const engine = new WorkflowEngine({ logger, eventBus, defaultStepTimeoutMs: 10000 })
  return { engine, logger, eventBus }
}


// Tests

describe('CorpusStrategyRegistry', () => {
  let registry: CorpusStrategyRegistry
  let logger: ILogger

  beforeEach(() => {
    logger = createMockLogger()
    registry = new CorpusStrategyRegistry(logger)
  })

  describe('register / unregister', () => {
    it('registers a strategy and indexes it by pattern type', () => {
      const strategy: CorpusStrategy = {
        id: 'test-strategy',
        description: 'Test',
        patternTypes: ['conflict'],
        priority: 5,
        matches: () => true,
        createWorkflow: () => createWorkflow({ id: 'test' }).commit(),
      }

      registry.register(strategy)

      expect(registry.size).toBe(1)
      expect(registry.get('test-strategy')).toBe(strategy)
    })

    it('replaces existing strategy with same id', () => {
      const v1: CorpusStrategy = {
        id: 'strat',
        description: 'v1',
        patternTypes: ['conflict'],
        priority: 1,
        matches: () => true,
        createWorkflow: () => createWorkflow({ id: 'v1' }).commit(),
      }
      const v2: CorpusStrategy = {
        id: 'strat',
        description: 'v2',
        patternTypes: ['conflict'],
        priority: 10,
        matches: () => true,
        createWorkflow: () => createWorkflow({ id: 'v2' }).commit(),
      }

      registry.register(v1)
      registry.register(v2)

      expect(registry.size).toBe(1)
      expect(registry.get('strat')!.description).toBe('v2')
    })

    it('unregisters a strategy', () => {
      const strategy: CorpusStrategy = {
        id: 'to-remove',
        description: 'Will be removed',
        patternTypes: ['redundancy'],
        priority: 0,
        matches: () => true,
        createWorkflow: () => createWorkflow({ id: 'x' }).commit(),
      }

      registry.register(strategy)
      expect(registry.size).toBe(1)

      const removed = registry.unregister('to-remove')
      expect(removed).toBe(true)
      expect(registry.size).toBe(0)
      expect(registry.get('to-remove')).toBeUndefined()
    })

    it('returns false when unregistering non-existent strategy', () => {
      expect(registry.unregister('nope')).toBe(false)
    })
  })

  describe('match', () => {
    it('returns the highest-priority matching strategy', () => {
      const low: CorpusStrategy = {
        id: 'low',
        description: 'Low priority',
        patternTypes: ['conflict'],
        priority: 1,
        matches: () => true,
        createWorkflow: () => createWorkflow({ id: 'low' }).commit(),
      }
      const high: CorpusStrategy = {
        id: 'high',
        description: 'High priority',
        patternTypes: ['conflict'],
        priority: 10,
        matches: () => true,
        createWorkflow: () => createWorkflow({ id: 'high' }).commit(),
      }

      registry.register(low)
      registry.register(high)

      const pattern = createPattern()
      const state = createState()
      const matched = registry.match(pattern, state)

      expect(matched).not.toBeNull()
      expect(matched!.id).toBe('high')
    })

    it('returns null when no strategy matches', () => {
      const strategy: CorpusStrategy = {
        id: 'picky',
        description: 'Only matches specific conditions',
        patternTypes: ['conflict'],
        priority: 5,
        matches: () => false,
        createWorkflow: () => createWorkflow({ id: 'x' }).commit(),
      }

      registry.register(strategy)

      const pattern = createPattern()
      const state = createState()
      expect(registry.match(pattern, state)).toBeNull()
    })

    it('returns null for unregistered pattern types', () => {
      const strategy: CorpusStrategy = {
        id: 'conflict-only',
        description: 'Only conflict',
        patternTypes: ['conflict'],
        priority: 5,
        matches: () => true,
        createWorkflow: () => createWorkflow({ id: 'x' }).commit(),
      }

      registry.register(strategy)

      const pattern = createPattern({ type: 'redundancy' })
      const state = createState()
      expect(registry.match(pattern, state)).toBeNull()
    })

    it('skips strategies where matches() throws', () => {
      const bad: CorpusStrategy = {
        id: 'bad',
        description: 'Throws',
        patternTypes: ['conflict'],
        priority: 10,
        matches: () => { throw new Error('boom') },
        createWorkflow: () => createWorkflow({ id: 'x' }).commit(),
      }
      const good: CorpusStrategy = {
        id: 'good',
        description: 'Works',
        patternTypes: ['conflict'],
        priority: 5,
        matches: () => true,
        createWorkflow: () => createWorkflow({ id: 'good' }).commit(),
      }

      registry.register(bad)
      registry.register(good)

      const pattern = createPattern()
      const state = createState()
      const matched = registry.match(pattern, state)

      expect(matched!.id).toBe('good')
    })
  })

  describe('run tracking', () => {
    it('tracks an active run', () => {
      const run: ActiveStrategyRun = {
        runId: 'run-1',
        strategyId: 'test',
        pattern: createPattern(),
        startedAt: Date.now(),
      }

      registry.trackRun(run)
      expect(registry.getActiveRuns()).toHaveLength(1)
      expect(registry.getAllRuns()).toHaveLength(1)
    })

    it('marks run as completed', () => {
      const run: ActiveStrategyRun = {
        runId: 'run-1',
        strategyId: 'test',
        pattern: createPattern(),
        startedAt: Date.now(),
      }

      registry.trackRun(run)
      registry.completeRun('run-1', { status: 'completed' } as any)

      expect(registry.getActiveRuns()).toHaveLength(0)
      expect(registry.getAllRuns()).toHaveLength(1)
    })

    it('removes a run', () => {
      const run: ActiveStrategyRun = {
        runId: 'run-1',
        strategyId: 'test',
        pattern: createPattern(),
        startedAt: Date.now(),
      }

      registry.trackRun(run)
      registry.removeRun('run-1')

      expect(registry.getAllRuns()).toHaveLength(0)
    })

    it('detects duplicate pattern runs', () => {
      const pattern = createPattern({ helixIds: ['a', 'b'] })
      const run: ActiveStrategyRun = {
        runId: 'run-1',
        strategyId: 'test',
        pattern,
        startedAt: Date.now(),
      }

      registry.trackRun(run)

      expect(registry.isRunningForPattern(createPattern({ helixIds: ['a', 'b'] }))).toBe(true)
      expect(registry.isRunningForPattern(createPattern({ helixIds: ['c', 'd'] }))).toBe(false)
    })

    it('ignores completed runs in duplicate check', () => {
      const pattern = createPattern({ helixIds: ['a', 'b'] })
      const run: ActiveStrategyRun = {
        runId: 'run-1',
        strategyId: 'test',
        pattern,
        startedAt: Date.now(),
        result: { status: 'completed' } as any,
      }

      registry.trackRun(run)
      expect(registry.isRunningForPattern(createPattern({ helixIds: ['a', 'b'] }))).toBe(false)
    })
  })
})


describe('corpusDirectiveStep', () => {
  beforeEach(() => {
    _resetNodeCounter()
  })

  it('sends a directive with static parameters', async () => {
    const sender = createMockSender()
    const { engine } = createEngine()

    const step = corpusDirectiveStep({
      id: 'test-directive',
      sender,
      targetHelixId: 'helix-1',
      directiveType: 'redirect',
      urgency: 'high',
      text: 'Stop editing file X',
      reason: 'Conflict with peer',
    })

    const wf = createWorkflow({ id: 'test' }).then(step).commit()
    const run = await engine.execute(wf, {})

    expect(run.status).toBe('completed')
    expect(sender.sendDirective).toHaveBeenCalledOnce()
    expect(sender.calls[0]).toMatchObject({
      targetHelixId: 'helix-1',
      type: 'redirect',
      urgency: 'high',
      text: 'Stop editing file X',
      reason: 'Conflict with peer',
    })
  })

  it('resolves dynamic parameters from input', async () => {
    const sender = createMockSender()
    const { engine } = createEngine()

    const step = corpusDirectiveStep({
      id: 'dynamic-directive',
      sender,
      targetHelixId: (input) => (input as any).targetId,
      directiveType: 'guidance',
      urgency: 'medium',
      text: (input) => `Message: ${(input as any).msg}`,
      reason: (input) => `Because: ${(input as any).why}`,
    })

    const wf = createWorkflow({ id: 'test' }).then(step).commit()
    const run = await engine.execute(wf, { targetId: 'helix-99', msg: 'hello', why: 'testing' })

    expect(run.status).toBe('completed')
    expect(sender.calls[0]).toMatchObject({
      targetHelixId: 'helix-99',
      text: 'Message: hello',
      reason: 'Because: testing',
    })
  })

  it('uses default reason when not provided', async () => {
    const sender = createMockSender()
    const { engine } = createEngine()

    const step = corpusDirectiveStep({
      id: 'no-reason',
      sender,
      targetHelixId: 'helix-1',
      directiveType: 'redirect',
      urgency: 'low',
      text: 'Do something',
    })

    const wf = createWorkflow({ id: 'test' }).then(step).commit()
    await engine.execute(wf, {})

    expect(sender.calls[0]).toMatchObject({
      reason: 'Strategy step: no-reason',
    })
  })

  it('passes optional fields through', async () => {
    const sender = createMockSender()
    const { engine } = createEngine()

    const step = corpusDirectiveStep({
      id: 'full',
      sender,
      targetHelixId: 'helix-1',
      directiveType: 'throttle',
      urgency: 'critical',
      text: 'Slow down',
      fromPattern: 'conflict',
      maxIterationsRemaining: 5,
      requiredAction: 'narrow_scope',
    })

    const wf = createWorkflow({ id: 'test' }).then(step).commit()
    await engine.execute(wf, {})

    expect(sender.calls[0]).toMatchObject({
      fromPattern: 'conflict',
      maxIterationsRemaining: 5,
      requiredAction: 'narrow_scope',
    })
  })
})


describe('corpusAssessStep', () => {
  beforeEach(() => {
    _resetNodeCounter()
  })

  it('runs assessment function and passes result downstream', async () => {
    const reader = createMockReader({
      assessments: new Map([
        ['h1', { status: 'productive', rollingScore: 0.8, filesModified: new Set(['a.ts']) }],
      ]),
    })
    const { engine } = createEngine()

    const assess = corpusAssessStep<{ total: number }>({
      id: 'count-branches',
      reader,
      assess: (r) => {
        const state = r.getProcessedState()
        return { total: state.branchAssessments.size }
      },
    })

    const verify = {
      id: 'verify',
      execute: async (ctx: any) => {
        expect(ctx.input).toEqual({ total: 1 })
        return 'ok'
      },
    }

    const wf = createWorkflow({ id: 'test' }).then(assess).then(verify).commit()
    const run = await engine.execute(wf, {})

    expect(run.status).toBe('completed')
  })

  it('receives the workflow input in the assess function', async () => {
    const reader = createMockReader()
    const { engine } = createEngine()

    let receivedInput: unknown
    const assess = corpusAssessStep({
      id: 'check-input',
      reader,
      assess: (_r, input) => {
        receivedInput = input
        return 'done'
      },
    })

    const wf = createWorkflow({ id: 'test' }).then(assess).commit()
    await engine.execute(wf, { foo: 'bar' })

    expect(receivedInput).toEqual({ foo: 'bar' })
  })
})


describe('Conflict Resolution Strategy', () => {
  beforeEach(() => {
    _resetNodeCounter()
  })

  it('matches conflict patterns with 2+ branches', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const strategy = createConflictResolutionStrategy(sender, reader)

    expect(strategy.id).toBe('conflict-resolution')
    expect(strategy.patternTypes).toEqual(['conflict'])

    const pattern = createPattern({ helixIds: ['a', 'b'] })
    expect(strategy.matches(pattern, createState())).toBe(true)
  })

  it('does not match already-acted-upon patterns', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const strategy = createConflictResolutionStrategy(sender, reader)

    const pattern = createPattern({ actedUpon: true })
    expect(strategy.matches(pattern, createState())).toBe(false)
  })

  it('does not match patterns with fewer than 2 branches', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const strategy = createConflictResolutionStrategy(sender, reader)

    const pattern = createPattern({ helixIds: ['a'] })
    expect(strategy.matches(pattern, createState())).toBe(false)
  })

  it('executes end-to-end: assess, then send parallel directives', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['helix-a', { status: 'productive', rollingScore: 0.9, filesModified: new Set(['core/x.ts', 'core/y.ts']) }],
        ['helix-b', { status: 'active', rollingScore: 0.5, filesModified: new Set(['core/x.ts', 'mcp/z.ts']) }],
      ]),
      branches: [
        { helixId: 'helix-a', goal: 'Implement feature A', status: 'active' },
        { helixId: 'helix-b', goal: 'Implement feature B', status: 'active' },
      ],
    })

    const strategy = createConflictResolutionStrategy(sender, reader)
    const logger = createMockLogger()

    const context: StrategyContext = {
      pattern: createPattern({ helixIds: ['helix-a', 'helix-b'], severity: 'high' }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger,
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    const run = await engine.execute(wf, { pattern: context.pattern })

    expect(run.status).toBe('completed')
    // Two directives sent: one to yielding, one to primary
    expect(sender.sendDirective).toHaveBeenCalledTimes(2)

    // helix-b yields (lower score), helix-a is primary
    const calls = sender.calls as any[]
    const redirectCall = calls.find((c: any) => c.type === 'redirect')
    const guidanceCall = calls.find((c: any) => c.type === 'guidance')

    expect(redirectCall).toBeDefined()
    expect(redirectCall.targetHelixId).toBe('helix-b')
    expect(redirectCall.urgency).toBe('high')
    expect(redirectCall.requiredAction).toBe('narrow_scope')

    expect(guidanceCall).toBeDefined()
    expect(guidanceCall.targetHelixId).toBe('helix-a')
    expect(guidanceCall.text).toContain('CONFLICT RESOLVED')
  })

  it('identifies conflicting files from modified file intersection', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['helix-a', { status: 'productive', rollingScore: 0.7, filesModified: new Set(['shared.ts', 'a-only.ts']) }],
        ['helix-b', { status: 'active', rollingScore: 0.6, filesModified: new Set(['shared.ts', 'b-only.ts']) }],
      ]),
      branches: [
        { helixId: 'helix-a', goal: 'Task A', status: 'active' },
        { helixId: 'helix-b', goal: 'Task B', status: 'active' },
      ],
    })

    const strategy = createConflictResolutionStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({ helixIds: ['helix-a', 'helix-b'] }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    await engine.execute(wf, { pattern: context.pattern })

    // The redirect directive should mention the conflicting file
    const redirectCall = (sender.calls as any[]).find((c: any) => c.type === 'redirect')
    expect(redirectCall.text).toContain('shared.ts')
  })

  it('works with equal-scored branches (tie-breaking by file count)', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['helix-a', { status: 'active', rollingScore: 0.5, filesModified: new Set(['a.ts', 'b.ts', 'c.ts']) }],
        ['helix-b', { status: 'active', rollingScore: 0.5, filesModified: new Set(['a.ts']) }],
      ]),
      branches: [
        { helixId: 'helix-a', goal: 'A', status: 'active' },
        { helixId: 'helix-b', goal: 'B', status: 'active' },
      ],
    })

    const strategy = createConflictResolutionStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({ helixIds: ['helix-a', 'helix-b'] }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    await engine.execute(wf, { pattern: context.pattern })

    // helix-a has more files, so it wins the tie
    const redirectCall = (sender.calls as any[]).find((c: any) => c.type === 'redirect')
    expect(redirectCall.targetHelixId).toBe('helix-b')
  })

  it('integrates with the registry: match → createWorkflow → execute', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['h1', { status: 'productive', rollingScore: 0.8, filesModified: new Set(['f.ts']) }],
        ['h2', { status: 'struggling', rollingScore: 0.3, filesModified: new Set(['f.ts']) }],
      ]),
      branches: [
        { helixId: 'h1', goal: 'Goal 1', status: 'active' },
        { helixId: 'h2', goal: 'Goal 2', status: 'active' },
      ],
    })

    const strategy = createConflictResolutionStrategy(sender, reader)
    const logger = createMockLogger()
    const registry = new CorpusStrategyRegistry(logger)
    registry.register(strategy)

    const pattern = createPattern({ helixIds: ['h1', 'h2'] })
    const state = createState()

    // Registry matches the strategy
    const matched = registry.match(pattern, state)
    expect(matched).not.toBeNull()
    expect(matched!.id).toBe('conflict-resolution')

    // Build and execute workflow
    const context: StrategyContext = {
      pattern,
      state,
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger,
    }

    const wf = matched!.createWorkflow(context)
    const { engine } = createEngine()
    const run = await engine.execute(wf, { pattern })

    expect(run.status).toBe('completed')
    expect(sender.sendDirective).toHaveBeenCalledTimes(2)

    // Track the run
    registry.trackRun({
      runId: run.runId,
      strategyId: matched!.id,
      pattern,
      startedAt: Date.now(),
      result: run,
    })

    expect(registry.getAllRuns()).toHaveLength(1)
  })
})


describe('Cascade Recovery Strategy', () => {
  beforeEach(() => {
    _resetNodeCounter()
  })

  it('matches cascade-failure patterns with 2+ branches', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const strategy = createCascadeRecoveryStrategy(sender, reader)

    expect(strategy.id).toBe('cascade-recovery')
    expect(strategy.patternTypes).toEqual(['cascade-failure'])
    expect(strategy.priority).toBe(20)

    const pattern = createPattern({ type: 'cascade-failure', helixIds: ['a', 'b'] })
    expect(strategy.matches(pattern, createState())).toBe(true)
  })

  it('does not match already-acted-upon patterns', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const strategy = createCascadeRecoveryStrategy(sender, reader)

    const pattern = createPattern({ type: 'cascade-failure', actedUpon: true })
    expect(strategy.matches(pattern, createState())).toBe(false)
  })

  it('throttles healthy branches and redirects struggling ones', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['h1', { status: 'productive', rollingScore: 0.8, filesModified: new Set(['a.ts']) }],
        ['h2', { status: 'struggling', rollingScore: 0.3, filesModified: new Set(['b.ts']) }],
        ['h3', { status: 'productive', rollingScore: 0.7, filesModified: new Set(['c.ts']) }],
      ]),
      branches: [
        { helixId: 'h1', goal: 'Goal 1', status: 'active' },
        { helixId: 'h2', goal: 'Goal 2', status: 'active' },
        { helixId: 'h3', goal: 'Goal 3', status: 'active' },
        { helixId: 'h4', goal: 'Goal 4', status: 'failed' },
      ],
    })

    const strategy = createCascadeRecoveryStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({ type: 'cascade-failure', helixIds: ['h1', 'h2', 'h3', 'h4'] }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    const run = await engine.execute(wf, { pattern: context.pattern })

    expect(run.status).toBe('completed')

    // Should have directives for h1 (throttle), h2 (redirect), h3 (throttle)
    // h4 is failed/skipped
    const calls = sender.calls as any[]
    expect(calls.length).toBe(3)

    const throttleCalls = calls.filter(c => c.type === 'throttle')
    const redirectCalls = calls.filter(c => c.type === 'redirect')

    expect(throttleCalls).toHaveLength(2)
    expect(redirectCalls).toHaveLength(1)

    // Struggling branch gets critical redirect
    expect(redirectCalls[0].targetHelixId).toBe('h2')
    expect(redirectCalls[0].urgency).toBe('critical')
    expect(redirectCalls[0].requiredAction).toBe('produce_output')

    // Healthy branches get throttle
    const throttleIds = throttleCalls.map((c: any) => c.targetHelixId).sort()
    expect(throttleIds).toEqual(['h1', 'h3'])
  })

  it('skips failed branches entirely', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['alive', { status: 'productive', rollingScore: 0.7, filesModified: new Set() }],
      ]),
      branches: [
        { helixId: 'alive', goal: 'Active', status: 'active' },
        { helixId: 'dead1', goal: 'Dead 1', status: 'failed' },
        { helixId: 'dead2', goal: 'Dead 2', status: 'completed' },
      ],
    })

    const strategy = createCascadeRecoveryStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({ type: 'cascade-failure', helixIds: ['alive', 'dead1', 'dead2'] }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    await engine.execute(wf, { pattern: context.pattern })

    // Only 'alive' should receive a directive
    expect(sender.calls).toHaveLength(1)
    expect((sender.calls[0] as any).targetHelixId).toBe('alive')
  })
})


describe('Convergence Synthesis Strategy', () => {
  beforeEach(() => {
    _resetNodeCounter()
  })

  it('matches convergence patterns with 2+ branches', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const strategy = createConvergenceSynthesisStrategy(sender, reader)

    expect(strategy.id).toBe('convergence-synthesis')
    expect(strategy.patternTypes).toEqual(['convergence'])
    expect(strategy.priority).toBe(5)

    const pattern = createPattern({ type: 'convergence', helixIds: ['a', 'b'] })
    expect(strategy.matches(pattern, createState())).toBe(true)
  })

  it('injects peer context into each converging branch', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['h1', { status: 'productive', rollingScore: 0.9, filesModified: new Set(['core/a.ts', 'core/b.ts']) }],
        ['h2', { status: 'productive', rollingScore: 0.85, filesModified: new Set(['mcp/c.ts']) }],
        ['h3', { status: 'productive', rollingScore: 0.8, filesModified: new Set(['types/d.ts', 'types/e.ts']) }],
      ]),
      branches: [
        { helixId: 'h1', goal: 'Implement auth layer', status: 'active' },
        { helixId: 'h2', goal: 'Add MCP endpoint', status: 'active' },
        { helixId: 'h3', goal: 'Update type definitions', status: 'active' },
      ],
    })

    const strategy = createConvergenceSynthesisStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({ type: 'convergence', helixIds: ['h1', 'h2', 'h3'] }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    const run = await engine.execute(wf, { pattern: context.pattern })

    expect(run.status).toBe('completed')

    // Each branch should receive a context-inject directive
    const calls = sender.calls as any[]
    expect(calls).toHaveLength(3)

    // All should be context-inject type
    for (const call of calls) {
      expect(call.type).toBe('context-inject')
      expect(call.urgency).toBe('medium')
      expect(call.fromPattern).toBe('convergence')
      expect(call.text).toContain('CONVERGENCE UPDATE')
    }

    // Each branch's directive should mention its peers
    const h1Call = calls.find((c: any) => c.targetHelixId === 'h1')
    expect(h1Call.text).toContain('Add MCP endpoint')
    expect(h1Call.text).toContain('Update type definitions')
    expect(h1Call.text).not.toContain('Implement auth layer')

    const h2Call = calls.find((c: any) => c.targetHelixId === 'h2')
    expect(h2Call.text).toContain('Implement auth layer')
    expect(h2Call.text).toContain('Update type definitions')
  })

  it('includes file information in peer summaries', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['h1', { status: 'productive', rollingScore: 0.9, filesModified: new Set(['core/a.ts']) }],
        ['h2', { status: 'productive', rollingScore: 0.85, filesModified: new Set(['mcp/c.ts', 'mcp/d.ts']) }],
      ]),
      branches: [
        { helixId: 'h1', goal: 'Task A', status: 'active' },
        { helixId: 'h2', goal: 'Task B', status: 'active' },
      ],
    })

    const strategy = createConvergenceSynthesisStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({ type: 'convergence', helixIds: ['h1', 'h2'] }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    await engine.execute(wf, { pattern: context.pattern })

    const h1Call = (sender.calls as any[]).find(c => c.targetHelixId === 'h1')
    expect(h1Call.text).toContain('mcp/c.ts')
  })
})


describe('Stuck Redecomposition Strategy', () => {
  beforeEach(() => {
    _resetNodeCounter()
  })

  it('matches asymmetric-progress patterns', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const strategy = createStuckRedecompositionStrategy(sender, reader)

    expect(strategy.id).toBe('stuck-redecomposition')
    expect(strategy.patternTypes).toEqual(['asymmetric-progress'])
    expect(strategy.priority).toBe(10)

    const pattern = createPattern({ type: 'asymmetric-progress', helixIds: ['stuck', 'ok'] })
    expect(strategy.matches(pattern, createState())).toBe(true)
  })

  it('narrows scope when budget is low and score is moderate', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['stuck', { status: 'active', rollingScore: 0.4, filesModified: new Set(['a.ts']) }],
        ['fast', { status: 'productive', rollingScore: 0.9, filesModified: new Set(['b.ts', 'c.ts', 'd.ts']) }],
      ]),
      branches: [
        { helixId: 'stuck', goal: 'Implement complex feature', status: 'active' },
        { helixId: 'fast', goal: 'Simple task', status: 'active' },
      ],
      budgets: new Map([
        ['stuck', { consumedSteps: 8, maxSteps: 40 }],
        ['fast', { consumedSteps: 15, maxSteps: 40 }],
      ]),
    })

    const strategy = createStuckRedecompositionStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({ type: 'asymmetric-progress', helixIds: ['stuck', 'fast'] }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    const run = await engine.execute(wf, { pattern: context.pattern })

    expect(run.status).toBe('completed')

    const calls = sender.calls as any[]
    expect(calls).toHaveLength(1)
    expect(calls[0].targetHelixId).toBe('stuck')
    expect(calls[0].type).toBe('redirect')
    expect(calls[0].urgency).toBe('high')
    expect(calls[0].requiredAction).toBe('narrow_scope')
    expect(calls[0].text).toContain('PROGRESS ALERT')
  })

  it('requests redecomposition when budget is high and score is low', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['stuck', { status: 'struggling', rollingScore: 0.2, filesModified: new Set() }],
        ['fast', { status: 'productive', rollingScore: 0.9, filesModified: new Set(['a.ts', 'b.ts']) }],
      ]),
      branches: [
        { helixId: 'stuck', goal: 'Refactor entire module', status: 'active' },
        { helixId: 'fast', goal: 'Fix bug', status: 'active' },
      ],
      budgets: new Map([
        ['stuck', { consumedSteps: 25, maxSteps: 40 }],
        ['fast', { consumedSteps: 10, maxSteps: 40 }],
      ]),
    })

    const strategy = createStuckRedecompositionStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({ type: 'asymmetric-progress', helixIds: ['stuck', 'fast'] }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    const run = await engine.execute(wf, { pattern: context.pattern })

    expect(run.status).toBe('completed')

    const calls = sender.calls as any[]
    expect(calls).toHaveLength(1)
    expect(calls[0].targetHelixId).toBe('stuck')
    expect(calls[0].urgency).toBe('critical')
    expect(calls[0].requiredAction).toBe('conclude')
    expect(calls[0].maxIterationsRemaining).toBe(3)
    expect(calls[0].text).toContain('REDECOMPOSITION')

    // Workflow output should contain the redecomposition result
    expect(run.output).toMatchObject({
      type: 'redecompose',
      stuckHelixId: 'stuck',
    })
  })

  it('correctly identifies the worst-scoring branch as stuck', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['a', { status: 'active', rollingScore: 0.6, filesModified: new Set(['x.ts']) }],
        ['b', { status: 'active', rollingScore: 0.2, filesModified: new Set() }],
        ['c', { status: 'productive', rollingScore: 0.9, filesModified: new Set(['y.ts']) }],
      ]),
      branches: [
        { helixId: 'a', goal: 'Task A', status: 'active' },
        { helixId: 'b', goal: 'Task B', status: 'active' },
        { helixId: 'c', goal: 'Task C', status: 'active' },
      ],
      budgets: new Map([
        ['b', { consumedSteps: 30, maxSteps: 40 }],
      ]),
    })

    const strategy = createStuckRedecompositionStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({ type: 'asymmetric-progress', helixIds: ['a', 'b', 'c'] }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    await engine.execute(wf, { pattern: context.pattern })

    // 'b' has the lowest score (0.2) — it should be the target
    const calls = sender.calls as any[]
    expect(calls).toHaveLength(1)
    expect(calls[0].targetHelixId).toBe('b')
  })

  it('includes peer performance info in narrow-scope directives', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['slow', { status: 'active', rollingScore: 0.4, filesModified: new Set() }],
        ['fast', { status: 'productive', rollingScore: 0.95, filesModified: new Set(['a.ts', 'b.ts', 'c.ts']) }],
      ]),
      branches: [
        { helixId: 'slow', goal: 'Slow task', status: 'active' },
        { helixId: 'fast', goal: 'Fast task', status: 'active' },
      ],
      budgets: new Map([
        ['slow', { consumedSteps: 5, maxSteps: 40 }],
      ]),
    })

    const strategy = createStuckRedecompositionStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({ type: 'asymmetric-progress', helixIds: ['slow', 'fast'] }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    await engine.execute(wf, { pattern: context.pattern })

    const call = (sender.calls as any[])[0]
    expect(call.text).toContain('0.95')
    expect(call.text).toContain('3 files')
  })
})


describe('Strategy Registry Integration', () => {
  beforeEach(() => {
    _resetNodeCounter()
  })

  it('registers all seven strategies with correct priorities', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const logger = createMockLogger()
    const registry = new CorpusStrategyRegistry(logger)

    registry.register(createConflictResolutionStrategy(sender, reader))
    registry.register(createCascadeRecoveryStrategy(sender, reader))
    registry.register(createConvergenceSynthesisStrategy(sender, reader))
    registry.register(createStuckRedecompositionStrategy(sender, reader))
    registry.register(createRedundancyStrategy(sender, reader))
    registry.register(createDivergenceStrategy(sender, reader))
    registry.register(createResourceImbalanceStrategy(sender, reader))

    expect(registry.size).toBe(7)

    // cascade-recovery has highest priority (20)
    const cascadeMatch = registry.match(
      createPattern({ type: 'cascade-failure', helixIds: ['a', 'b'] }),
      createState(),
    )
    expect(cascadeMatch!.id).toBe('cascade-recovery')

    // conflict-resolution matches conflict
    const conflictMatch = registry.match(
      createPattern({ type: 'conflict', helixIds: ['a', 'b'] }),
      createState(),
    )
    expect(conflictMatch!.id).toBe('conflict-resolution')

    // convergence-synthesis matches convergence
    const convergenceMatch = registry.match(
      createPattern({ type: 'convergence', helixIds: ['a', 'b'] }),
      createState(),
    )
    expect(convergenceMatch!.id).toBe('convergence-synthesis')

    // stuck-redecomposition matches asymmetric-progress
    const stuckMatch = registry.match(
      createPattern({ type: 'asymmetric-progress', helixIds: ['a', 'b'] }),
      createState(),
    )
    expect(stuckMatch!.id).toBe('stuck-redecomposition')

    // redundancy matches redundancy
    const redundancyMatch = registry.match(
      createPattern({ type: 'redundancy', helixIds: ['a', 'b'] }),
      createState(),
    )
    expect(redundancyMatch!.id).toBe('redundancy')

    // divergence matches divergence
    const divergenceMatch = registry.match(
      createPattern({ type: 'divergence', helixIds: ['a', 'b'] }),
      createState(),
    )
    expect(divergenceMatch!.id).toBe('divergence')

    // resource-imbalance matches resource-imbalance
    const imbalanceMatch = registry.match(
      createPattern({ type: 'resource-imbalance', helixIds: ['a', 'b'] }),
      createState(),
    )
    expect(imbalanceMatch!.id).toBe('resource-imbalance')
  })

  it('all pattern types are covered', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const logger = createMockLogger()
    const registry = new CorpusStrategyRegistry(logger)

    registry.register(createConflictResolutionStrategy(sender, reader))
    registry.register(createCascadeRecoveryStrategy(sender, reader))
    registry.register(createConvergenceSynthesisStrategy(sender, reader))
    registry.register(createStuckRedecompositionStrategy(sender, reader))
    registry.register(createRedundancyStrategy(sender, reader))
    registry.register(createDivergenceStrategy(sender, reader))
    registry.register(createResourceImbalanceStrategy(sender, reader))

    const patternTypes = [
      'conflict', 'cascade-failure', 'convergence',
      'asymmetric-progress', 'redundancy', 'divergence',
      'resource-imbalance',
    ] as const

    for (const type of patternTypes) {
      const match = registry.match(
        createPattern({ type, helixIds: ['a', 'b'] }),
        createState(),
      )
      expect(match, `Expected strategy for pattern type '${type}'`).not.toBeNull()
    }
  })
})


describe('Redundancy Strategy', () => {
  beforeEach(() => {
    _resetNodeCounter()
  })

  it('matches redundancy patterns with 2+ branches', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const strategy = createRedundancyStrategy(sender, reader)

    expect(strategy.id).toBe('redundancy')
    expect(strategy.patternTypes).toEqual(['redundancy'])
    expect(strategy.priority).toBe(8)

    const pattern = createPattern({ type: 'redundancy', helixIds: ['a', 'b'] })
    expect(strategy.matches(pattern, createState())).toBe(true)
  })

  it('redirects lower-scorer to unique work', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['h1', { status: 'productive', rollingScore: 0.8, filesModified: new Set(['shared.ts', 'only-h1.ts']) }],
        ['h2', { status: 'active', rollingScore: 0.5, filesModified: new Set(['shared.ts', 'only-h2.ts']) }],
      ]),
      branches: [
        { helixId: 'h1', goal: 'Implement feature A', status: 'active' },
        { helixId: 'h2', goal: 'Implement feature B', status: 'active' },
      ],
    })

    const strategy = createRedundancyStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({
        type: 'redundancy',
        helixIds: ['h1', 'h2'],
        description: 'Branches h1 and h2 doing redundant implementation work (60% file overlap)',
      }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    const run = await engine.execute(wf, { pattern: context.pattern })

    expect(run.status).toBe('completed')

    const calls = sender.calls as any[]
    expect(calls).toHaveLength(1)
    expect(calls[0].targetHelixId).toBe('h2')
    expect(calls[0].type).toBe('redirect')
    expect(calls[0].requiredAction).toBe('switch_strategy')
    expect(calls[0].text).toContain('REDUNDANCY DETECTED')
    expect(calls[0].text).toContain('shared.ts')
    expect(calls[0].text).toContain('only-h2.ts')
  })

  it('extracts work pattern from detection description', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['a', { status: 'active', rollingScore: 0.7, filesModified: new Set(['x.ts']) }],
        ['b', { status: 'active', rollingScore: 0.5, filesModified: new Set(['x.ts']) }],
      ]),
      branches: [
        { helixId: 'a', goal: 'A', status: 'active' },
        { helixId: 'b', goal: 'B', status: 'active' },
      ],
    })

    const strategy = createRedundancyStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({
        type: 'redundancy',
        helixIds: ['a', 'b'],
        description: 'Branches a and b doing redundant analysis work (80% file overlap)',
      }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    await engine.execute(wf, { pattern: context.pattern })

    const call = (sender.calls as any[])[0]
    expect(call.text).toContain('analysis')
  })
})


describe('Divergence Strategy', () => {
  beforeEach(() => {
    _resetNodeCounter()
  })

  it('matches divergence patterns with 2+ branches', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const strategy = createDivergenceStrategy(sender, reader)

    expect(strategy.id).toBe('divergence')
    expect(strategy.patternTypes).toEqual(['divergence'])
    expect(strategy.priority).toBe(7)

    const pattern = createPattern({ type: 'divergence', helixIds: ['a', 'b'] })
    expect(strategy.matches(pattern, createState())).toBe(true)
  })

  it('sends realignment directive to divergent branch', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['divergent', { status: 'active', rollingScore: 0.35, filesModified: new Set() }],
        ['sibling', { status: 'productive', rollingScore: 0.8, filesModified: new Set(['a.ts']) }],
      ]),
      branches: [
        { helixId: 'divergent', goal: 'Explore architecture', status: 'active' },
        { helixId: 'sibling', goal: 'Implement feature', status: 'active' },
      ],
    })

    const strategy = createDivergenceStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({
        type: 'divergence',
        helixIds: ['divergent', 'sibling'],
        description: 'divergent is doing analysis while siblings do implementation (declining score streak: 3)',
      }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    const run = await engine.execute(wf, { pattern: context.pattern })

    expect(run.status).toBe('completed')

    const calls = sender.calls as any[]
    expect(calls).toHaveLength(1)
    expect(calls[0].targetHelixId).toBe('divergent')
    expect(calls[0].type).toBe('redirect')
    expect(calls[0].urgency).toBe('high')
    expect(calls[0].requiredAction).toBe('switch_strategy')
    expect(calls[0].text).toContain('DIVERGENCE DETECTED')
    expect(calls[0].text).toContain('analysis')
    expect(calls[0].text).toContain('implementation')
  })
})


describe('Resource Imbalance Strategy', () => {
  beforeEach(() => {
    _resetNodeCounter()
  })

  it('matches resource-imbalance patterns with 2+ branches', () => {
    const sender = createMockSender()
    const reader = createMockReader()
    const strategy = createResourceImbalanceStrategy(sender, reader)

    expect(strategy.id).toBe('resource-imbalance')
    expect(strategy.patternTypes).toEqual(['resource-imbalance'])
    expect(strategy.priority).toBe(6)

    const pattern = createPattern({ type: 'resource-imbalance', helixIds: ['a', 'b'] })
    expect(strategy.matches(pattern, createState())).toBe(true)
  })

  it('throttles overconsumer and encourages underconsumer', async () => {
    const sender = createMockSender()
    const reader = createMockReader({
      assessments: new Map([
        ['over', { status: 'active', rollingScore: 0.5, filesModified: new Set(['a.ts', 'b.ts']) }],
        ['under', { status: 'active', rollingScore: 0.6, filesModified: new Set(['c.ts']) }],
      ]),
      branches: [
        { helixId: 'over', goal: 'Heavy task', status: 'active' },
        { helixId: 'under', goal: 'Light task', status: 'active' },
      ],
    })

    const strategy = createResourceImbalanceStrategy(sender, reader)
    const context: StrategyContext = {
      pattern: createPattern({
        type: 'resource-imbalance',
        helixIds: ['over', 'under'],
        description: 'over has consumed 85% budget while under only 20%',
      }),
      state: createState(),
      tree: reader.getTree() as any,
      constellationId: 'const-1',
      logger: createMockLogger(),
    }

    const wf = strategy.createWorkflow(context)
    const { engine } = createEngine()
    const run = await engine.execute(wf, { pattern: context.pattern })

    expect(run.status).toBe('completed')

    const calls = sender.calls as any[]
    expect(calls).toHaveLength(2)

    // First call: throttle the overconsumer
    const throttleCall = calls.find((c: any) => c.type === 'throttle')
    expect(throttleCall).toBeDefined()
    expect(throttleCall.targetHelixId).toBe('over')
    expect(throttleCall.urgency).toBe('high')
    expect(throttleCall.text).toContain('85%')
    expect(throttleCall.maxIterationsRemaining).toBe(10)

    // Second call: encourage the underconsumer
    const guidanceCall = calls.find((c: any) => c.type === 'guidance')
    expect(guidanceCall).toBeDefined()
    expect(guidanceCall.targetHelixId).toBe('under')
    expect(guidanceCall.urgency).toBe('medium')
    expect(guidanceCall.text).toContain('PACE CHECK')
    expect(guidanceCall.text).toContain('20%')
  })
})
