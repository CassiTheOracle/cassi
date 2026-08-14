/**
 * Constellation Guidance Provider Tests
 *
 * Tests the guidance provider that bridges the Corpus tree and collect_thoughts,
 * and the ConstellationGuidanceRegistry that enables session-scoped lookup.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createConstellationGuidanceProvider, ConstellationGuidanceRegistry } from '../src/guidance-provider.js'
import type { CorpusTree } from '../src/corpus-tree.js'
import type { ILogger } from '../src/vendor/types/interfaces.js'

function makeLogger(): ILogger {
  const log: ILogger = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: () => log,
  }
  return log
}

function makeMockCorpusTree(opts?: {
  elevatedPatterns?: any[]
  branches?: any[]
}): CorpusTree {
  return {
    getElevatedPatterns: vi.fn().mockReturnValue(opts?.elevatedPatterns ?? []),
    getSnapshot: vi.fn().mockReturnValue({
      branches: opts?.branches ?? [],
      elevatedPatterns: opts?.elevatedPatterns ?? [],
    }),
    registerBranch: vi.fn(),
    pushAnnotation: vi.fn(),
    elevatePattern: vi.fn(),
    closeBranch: vi.fn(),
    updateDigest: vi.fn(),
    getBranch: vi.fn(),
    addRetrospective: vi.fn(),
    recordEffectiveness: vi.fn(),
  } as any
}

describe('ConstellationGuidanceProvider', () => {
  let logger: ILogger

  beforeEach(() => {
    logger = makeLogger()
  })

  it('returns null when no relevant patterns or branches', () => {
    const tree = makeMockCorpusTree()
    const provider = createConstellationGuidanceProvider({
      corpusTree: tree,
      helixId: 'helix-1',
      branchGoal: 'Implement rate limiting',
      logger,
    })

    const result = provider.getGuidanceForThought('Analyzing the code structure', 1, 'session-1')
    expect(result).toBeNull()
  })

  it('surfaces relevant elevated patterns', () => {
    const tree = makeMockCorpusTree({
      elevatedPatterns: [{
        id: 'p1',
        sourceHelixId: 'helix-other',
        approach: 'implementation',
        description: 'Used token bucket algorithm for rate limiting with per-IP tracking',
        applicableContext: 'Rate limiting implementation for API endpoints',
        achievedScore: 0.85,
        relevantFiles: ['core/middleware/rate-limiter.ts'],
        supportingRetrospectives: [],
        elevatedAt: Date.now(),
        referenceCount: 0,
      }],
    })

    const provider = createConstellationGuidanceProvider({
      corpusTree: tree,
      helixId: 'helix-1',
      branchGoal: 'Implement rate limiting for the admin API',
      logger,
    })

    const result = provider.getGuidanceForThought(
      'Thinking about how to implement rate limiting',
      1,
      'session-1',
    )
    expect(result).toBeTruthy()
    expect(result).toContain('Constellation knowledge')
    expect(result).toContain('token bucket')
  })

  it('does not repeat already-surfaced patterns', () => {
    const tree = makeMockCorpusTree({
      elevatedPatterns: [{
        id: 'p1',
        sourceHelixId: 'helix-other',
        approach: 'implementation',
        description: 'Token bucket for rate limiting',
        applicableContext: 'Rate limiting',
        achievedScore: 0.85,
        relevantFiles: [],
        supportingRetrospectives: [],
        elevatedAt: Date.now(),
        referenceCount: 0,
      }],
    })

    const provider = createConstellationGuidanceProvider({
      corpusTree: tree,
      helixId: 'helix-1',
      branchGoal: 'Implement rate limiting',
      logger,
    })

    // First call surfaces the pattern
    const first = provider.getGuidanceForThought('rate limiting approach', 1, 'session-1')
    expect(first).toBeTruthy()

    // Third call should not repeat (step 3 passes rate limit since MIN_STEP_INTERVAL=2)
    const second = provider.getGuidanceForThought('rate limiting implementation', 3, 'session-1')
    // Pattern was already surfaced, so no new patterns
    expect(second).toBeNull()
  })

  it('includes active peer branches on early steps', () => {
    const tree = makeMockCorpusTree({
      branches: [
        { helixId: 'helix-1', goal: 'My own branch goal', status: 'active', stepCount: 5, averageScore: 0.7, depth: 0, createdAt: Date.now() },
        { helixId: 'helix-peer1', goal: 'Implement database migrations', status: 'active', stepCount: 3, averageScore: 0.8, depth: 0, createdAt: Date.now() },
        { helixId: 'helix-peer2', goal: 'Add unit tests for auth module', status: 'active', stepCount: 2, averageScore: 0.6, depth: 0, createdAt: Date.now() },
      ],
    })

    const provider = createConstellationGuidanceProvider({
      corpusTree: tree,
      helixId: 'helix-1',
      branchGoal: 'Implement rate limiting',
      logger,
    })

    const result = provider.getGuidanceForThought('Starting work on rate limiting', 1, 'session-1')
    expect(result).toBeTruthy()
    expect(result).toContain('active branches')
    expect(result).toContain('database migrations')
    expect(result).toContain('unit tests')
    // Should not include own branch
    expect(result).not.toContain('My own branch goal')
  })

  it('does not include peer branches after step 3', () => {
    const tree = makeMockCorpusTree({
      branches: [
        { helixId: 'helix-peer', goal: 'Some peer work', status: 'active', stepCount: 3, averageScore: 0.7, depth: 0, createdAt: Date.now() },
      ],
    })

    const provider = createConstellationGuidanceProvider({
      corpusTree: tree,
      helixId: 'helix-1',
      branchGoal: 'Different goal',
      logger,
    })

    const result = provider.getGuidanceForThought('Working on step 5', 5, 'session-1')
    // No patterns, and step > 3 so no peer branches
    expect(result).toBeNull()
  })

  it('rate-limits guidance to every 2 steps', () => {
    const tree = makeMockCorpusTree({
      elevatedPatterns: [{
        id: 'p1',
        sourceHelixId: 'helix-other',
        approach: 'implementation',
        description: 'Token bucket for rate limiting',
        applicableContext: 'Rate limiting implementation',
        achievedScore: 0.85,
        relevantFiles: [],
        supportingRetrospectives: [],
        elevatedAt: Date.now(),
        referenceCount: 0,
      }],
    })

    const provider = createConstellationGuidanceProvider({
      corpusTree: tree,
      helixId: 'helix-1',
      branchGoal: 'Implement rate limiting',
      logger,
    })

    // Step 1: should provide guidance (first call)
    const step1 = provider.getGuidanceForThought('rate limiting', 1, 'session-1')
    expect(step1).toBeTruthy()

    // Step 2: should be rate-limited (only 1 step since last guidance)
    const step2 = provider.getGuidanceForThought('rate limiting details', 2, 'session-1')
    expect(step2).toBeNull()
  })
})


describe('ConstellationGuidanceRegistry', () => {
  it('registers and retrieves providers by session ID', () => {
    const registry = new ConstellationGuidanceRegistry()
    const provider = { getGuidanceForThought: vi.fn().mockReturnValue('guidance') }

    registry.register('session-1', provider)
    expect(registry.get('session-1')).toBe(provider)
    expect(registry.size).toBe(1)
  })

  it('returns undefined for unknown session IDs', () => {
    const registry = new ConstellationGuidanceRegistry()
    expect(registry.get('nonexistent')).toBeUndefined()
  })

  it('unregisters providers', () => {
    const registry = new ConstellationGuidanceRegistry()
    const provider = { getGuidanceForThought: vi.fn() }

    registry.register('session-1', provider)
    expect(registry.get('session-1')).toBe(provider)

    registry.unregister('session-1')
    expect(registry.get('session-1')).toBeUndefined()
    expect(registry.size).toBe(0)
  })

  it('supports multiple concurrent sessions', () => {
    const registry = new ConstellationGuidanceRegistry()
    const p1 = { getGuidanceForThought: vi.fn().mockReturnValue('guidance-1') }
    const p2 = { getGuidanceForThought: vi.fn().mockReturnValue('guidance-2') }

    registry.register('session-1', p1)
    registry.register('session-2', p2)

    expect(registry.get('session-1')).toBe(p1)
    expect(registry.get('session-2')).toBe(p2)
    expect(registry.size).toBe(2)

    registry.unregister('session-1')
    expect(registry.get('session-1')).toBeUndefined()
    expect(registry.get('session-2')).toBe(p2)
    expect(registry.size).toBe(1)
  })

  it('replaces provider when same session ID is re-registered', () => {
    const registry = new ConstellationGuidanceRegistry()
    const p1 = { getGuidanceForThought: vi.fn() }
    const p2 = { getGuidanceForThought: vi.fn() }

    registry.register('session-1', p1)
    registry.register('session-1', p2)

    expect(registry.get('session-1')).toBe(p2)
    expect(registry.size).toBe(1)
  })

  it('unregister is idempotent for unknown session IDs', () => {
    const registry = new ConstellationGuidanceRegistry()
    // Should not throw
    registry.unregister('nonexistent')
    expect(registry.size).toBe(0)
  })
})
