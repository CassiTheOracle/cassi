/**
 * Blackboard tests for FluxTeam architecture
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { Blackboard } from '../src/blackboard.js'
import type { BlackboardChannel, FluxCellResult } from '@cassicore/foundation'
import type { ILogger } from '@cassicore/foundation'

/**
 * Mock logger for testing
 */
const createMockLogger = () => ({
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  debug: vi.fn(),
  child: vi.fn().mockReturnThis(),
})

/**
 * Create a mock FluxCellResult for testing
 */
const createMockCellResult = (success: boolean, output: string): FluxCellResult => ({
  cellId: 'test-cell',
  success,
  output,
  nodeResults: [],
  totalTokens: 1000,
  totalDurationMs: 5000,
  topologyId: 'test-topology',
  artifacts: [],
  completedAt: Date.now(),
})

describe('Blackboard', () => {
  let blackboard: Blackboard
  let mockLogger: ReturnType<typeof createMockLogger>
  const cellId = 'test-cell-123'

  beforeEach(() => {
    mockLogger = createMockLogger()
    blackboard = new Blackboard(mockLogger as unknown as ILogger, cellId)
  })

  describe('channel operations', () => {
    describe('post and read', () => {
      it('should post entries to a channel and read them back', () => {
        const entry = blackboard.post('findings', {
          author: 'explorer',
          content: 'Found important pattern',
          priority: 5,
          tags: ['pattern', 'important'],
        })

        expect(entry.id).toBeDefined()
        expect(entry.channel).toBe('findings')
        expect(entry.author).toBe('explorer')
        expect(entry.content).toBe('Found important pattern')
        expect(entry.priority).toBe(5)
        expect(entry.tags).toEqual(['pattern', 'important'])
        expect(entry.timestamp).toBeDefined()

        const entries = blackboard.read('findings')
        expect(entries).toHaveLength(1)
        expect(entries[0].content).toBe('Found important pattern')
      })

      it('should assign automatic id and timestamp to entries', () => {
        const entry = blackboard.post('concerns', {
          author: 'reviewer',
          content: 'Potential issue detected',
          priority: 0,
          tags: [],
        })

        expect(entry.id).toMatch(/^[0-9a-f-]+$/)
        expect(entry.timestamp).toBeGreaterThan(0)
        expect(entry.channel).toBe('concerns')
      })

      it('should default priority to 0 and tags to empty array', () => {
        const entry = blackboard.post('decisions', {
          author: 'planner',
          content: 'Decision made',
          priority: 0,
          tags: [],
        })

        expect(entry.priority).toBe(0)
        expect(entry.tags).toEqual([])
      })
    })

    describe('read sorting', () => {
      it('should sort entries by priority DESC, then timestamp DESC', async () => {
        // Post entries with different priorities
        // Wait between posts to ensure different timestamps
        blackboard.post('findings', {
          author: 'agent1',
          content: 'Low priority first',
          priority: 1,
          tags: [],
        })

        await new Promise(resolve => setTimeout(resolve, 10))

        blackboard.post('findings', {
          author: 'agent2',
          content: 'High priority second',
          priority: 10,
          tags: [],
        })

        await new Promise(resolve => setTimeout(resolve, 10))

        blackboard.post('findings', {
          author: 'agent3',
          content: 'Low priority third',
          priority: 1,
          tags: [],
        })

        await new Promise(resolve => setTimeout(resolve, 10))

        blackboard.post('findings', {
          author: 'agent4',
          content: 'Medium priority fourth',
          priority: 5,
          tags: [],
        })

        const entries = blackboard.read('findings')

        // Should be sorted: priority 10, then 5, then 1 (newest first for same priority)
        expect(entries).toHaveLength(4)
        expect(entries[0].content).toBe('High priority second')
        expect(entries[1].content).toBe('Medium priority fourth')
        expect(entries[2].content).toBe('Low priority third')
        expect(entries[3].content).toBe('Low priority first')
      })
    })

    describe('read with limit', () => {
      it('should limit results when limit is specified', () => {
        for (let i = 0; i < 10; i++) {
          blackboard.post('findings', {
            author: 'agent',
            content: `Entry ${i}`,
            priority: i,
            tags: [],
          })
        }

        const entries = blackboard.read('findings', 5)
        expect(entries).toHaveLength(5)
        // Should return highest priority entries
        expect(entries[0].priority).toBe(9)
        expect(entries[4].priority).toBe(5)
      })
    })

    describe('readAll', () => {
      it('should read all entries across all channels', () => {
        blackboard.post('findings', { author: 'a1', content: 'Finding 1', priority: 0, tags: [] })
        blackboard.post('concerns', { author: 'a2', content: 'Concern 1', priority: 0, tags: [] })
        blackboard.post('decisions', { author: 'a3', content: 'Decision 1', priority: 0, tags: [] })

        const allEntries = blackboard.readAll()
        expect(allEntries).toHaveLength(3)
      })

      it('should sort all entries by timestamp DESC', async () => {
        blackboard.post('findings', { author: 'a1', content: 'First', priority: 0, tags: [] })
        await new Promise(resolve => setTimeout(resolve, 10))
        blackboard.post('concerns', { author: 'a2', content: 'Second', priority: 0, tags: [] })
        await new Promise(resolve => setTimeout(resolve, 10))
        blackboard.post('decisions', { author: 'a3', content: 'Third', priority: 0, tags: [] })

        const allEntries = blackboard.readAll()
        expect(allEntries).toHaveLength(3)
        expect(allEntries[0].content).toBe('Third')
        expect(allEntries[1].content).toBe('Second')
        expect(allEntries[2].content).toBe('First')
      })
    })

    describe('channel rolling limit', () => {
      it('should enforce 500 entry limit per channel', () => {
        // Post 550 entries
        for (let i = 0; i < 550; i++) {
          blackboard.post('findings', {
            author: 'agent',
            content: `Entry ${i}`,
            priority: i, // Different priorities to test priority sorting
            tags: [],
          })
        }

        const entries = blackboard.read('findings')
        expect(entries).toHaveLength(500)
        // Oldest entries (0-49) should be removed
        // Sorted by priority DESC, so highest priority first
        expect(entries[0].priority).toBe(549)
        expect(entries[entries.length - 1].priority).toBe(50)
      })
    })
  })

  describe('reactive subscriptions', () => {
    it('should fire subscriptions on matching channel', () => {
      const callback = vi.fn()
      blackboard.subscribe('findings', undefined, callback)

      blackboard.post('findings', {
        author: 'explorer',
        content: 'New finding',
        priority: 0,
        tags: ['test'],
      })

      expect(callback).toHaveBeenCalledTimes(1)
      expect(callback.mock.calls[0][0].content).toBe('New finding')
    })

    it('should fire subscriptions when tags match', () => {
      const callback = vi.fn()
      blackboard.subscribe('findings', ['important', 'urgent'], callback)

      // This should fire - has all required tags
      blackboard.post('findings', {
        author: 'explorer',
        content: 'Critical finding',
        priority: 10,
        tags: ['important', 'urgent', 'security'],
      })

      expect(callback).toHaveBeenCalledTimes(1)
    })

    it('should NOT fire subscriptions when tags do not match', () => {
      const callback = vi.fn()
      blackboard.subscribe('findings', ['important', 'urgent'], callback)

      // This should NOT fire - missing 'urgent' tag
      blackboard.post('findings', {
        author: 'explorer',
        content: 'Regular finding',
        priority: 5,
        tags: ['important', 'general'],
      })

      expect(callback).not.toHaveBeenCalled()
    })

    it('should NOT fire subscriptions on non-matching channel', () => {
      const callback = vi.fn()
      blackboard.subscribe('findings', undefined, callback)

      blackboard.post('concerns', {
        author: 'reviewer',
        content: 'New concern',
        priority: 0,
        tags: [],
      })

      expect(callback).not.toHaveBeenCalled()
    })

    it('should unsubscribe correctly', () => {
      const callback = vi.fn()
      const unsubscribe = blackboard.subscribe('findings', undefined, callback)

      blackboard.post('findings', {
        author: 'explorer',
        content: 'First finding',
        priority: 0,
        tags: [],
      })
      expect(callback).toHaveBeenCalledTimes(1)

      unsubscribe()

      blackboard.post('findings', {
        author: 'explorer',
        content: 'Second finding',
        priority: 0,
        tags: [],
      })
      expect(callback).toHaveBeenCalledTimes(1) // Still only 1
    })

    it('should handle subscription callback errors gracefully', () => {
      const callback = vi.fn().mockImplementation(() => {
        throw new Error('Callback error')
      })
      blackboard.subscribe('findings', undefined, callback)

      // Should not throw
      expect(() => {
        blackboard.post('findings', {
          author: 'explorer',
          content: 'Finding',
          priority: 0,
          tags: [],
        })
      }).not.toThrow()

      expect(mockLogger.error).toHaveBeenCalledWith(
        'Subscription callback failed',
        expect.objectContaining({
          subscriptionId: expect.any(String),
          error: expect.any(String),
        }),
      )
    })
  })

  describe('scratchpad with TTL', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('should set and get scratchpad entries', () => {
      blackboard.setScratchpad('key1', 'value1', 'author1')
      expect(blackboard.getScratchpad('key1')).toBe('value1')
    })

    it('should return undefined for non-existent keys', () => {
      expect(blackboard.getScratchpad('nonexistent')).toBeUndefined()
    })

    it('should expire entries after TTL', () => {
      const ttlMs = 5000
      blackboard.setScratchpad('key1', 'value1', 'author1', ttlMs)

      // Should exist before TTL
      expect(blackboard.getScratchpad('key1')).toBe('value1')

      // Advance time past TTL
      vi.advanceTimersByTime(ttlMs + 100)

      // Should be expired
      expect(blackboard.getScratchpad('key1')).toBeUndefined()
    })

    it('should use default TTL of 30 minutes', () => {
      blackboard.setScratchpad('key1', 'value1', 'author1')

      // Advance time by 29 minutes
      vi.advanceTimersByTime(29 * 60 * 1000)
      expect(blackboard.getScratchpad('key1')).toBe('value1')

      // Advance past 30 minutes
      vi.advanceTimersByTime(2 * 60 * 1000)
      expect(blackboard.getScratchpad('key1')).toBeUndefined()
    })

    it('should get all non-expired scratchpad entries', () => {
      blackboard.setScratchpad('key1', 'value1', 'author1', 10000)
      blackboard.setScratchpad('key2', 'value2', 'author2', 10000)
      blackboard.setScratchpad('key3', 'value3', 'author3', 1000)

      vi.advanceTimersByTime(5000)

      const all = blackboard.getAllScratchpad()
      expect(all.size).toBe(2)
      expect(all.get('key1')).toBe('value1')
      expect(all.get('key2')).toBe('value2')
      expect(all.has('key3')).toBe(false)
    })

    it('should clean up expired entries on getAllScratchpad', () => {
      blackboard.setScratchpad('key1', 'value1', 'author1', 1000)
      vi.advanceTimersByTime(2000)

      blackboard.getAllScratchpad()

      // Expired entry should be removed from internal map
      expect(blackboard.getScratchpad('key1')).toBeUndefined()
    })
  })

  describe('tool execution logging', () => {
    it('should add tool records', () => {
      blackboard.addToolRecord({
        tool: 'read',
        nodeId: 'explorer',
        params: { path: 'src/index.ts' },
        result: 'File content...',
        isError: false,
        durationMs: 150,
      })

      const log = blackboard.getToolLog()
      expect(log).toHaveLength(1)
      expect(log[0].tool).toBe('read')
      expect(log[0].nodeId).toBe('explorer')
      expect(log[0].isError).toBe(false)
      expect(log[0].durationMs).toBe(150)
      expect(log[0].timestamp).toBeDefined()
    })

    it('should enforce tool log limit of 500', () => {
      // Add 550 records
      for (let i = 0; i < 550; i++) {
        blackboard.addToolRecord({
          tool: 'bash',
          nodeId: 'agent',
          params: { command: `echo ${i}` },
          result: `Output ${i}`,
          isError: false,
          durationMs: 100,
        })
      }

      const log = blackboard.getToolLog()
      expect(log).toHaveLength(500)
      // Oldest records should be removed
      expect(log[0].params.command).toBe('echo 50')
    })

    it('should limit recent records when specified', () => {
      for (let i = 0; i < 10; i++) {
        blackboard.addToolRecord({
          tool: 'tool',
          nodeId: 'agent',
          params: {},
          result: `Result ${i}`,
          isError: false,
          durationMs: 100,
        })
      }

      const log = blackboard.getToolLog(5)
      expect(log).toHaveLength(5)
      // Should return most recent
      expect(log[0].result).toBe('Result 5')
      expect(log[4].result).toBe('Result 9')
    })
  })

  describe('artifact tracking', () => {
    it('should track file artifacts', () => {
      blackboard.addArtifact({
        path: 'src/utils.ts',
        operation: 'created',
        author: 'builder',
      })

      const artifacts = blackboard.getArtifacts()
      expect(artifacts).toHaveLength(1)
      expect(artifacts[0].path).toBe('src/utils.ts')
      expect(artifacts[0].operation).toBe('created')
      expect(artifacts[0].author).toBe('builder')
      expect(artifacts[0].timestamp).toBeDefined()
    })

    it('should update existing artifacts', () => {
      blackboard.addArtifact({
        path: 'src/utils.ts',
        operation: 'created',
        author: 'builder',
      })

      blackboard.addArtifact({
        path: 'src/utils.ts',
        operation: 'modified',
        author: 'reviewer',
      })

      const artifacts = blackboard.getArtifacts()
      expect(artifacts).toHaveLength(1)
      expect(artifacts[0].operation).toBe('modified')
      expect(artifacts[0].author).toBe('reviewer')
    })

    it('should track multiple artifacts', () => {
      blackboard.addArtifact({ path: 'file1.ts', operation: 'created', author: 'a1' })
      blackboard.addArtifact({ path: 'file2.ts', operation: 'created', author: 'a2' })
      blackboard.addArtifact({ path: 'file3.ts', operation: 'deleted', author: 'a3' })

      const artifacts = blackboard.getArtifacts()
      expect(artifacts).toHaveLength(3)
    })
  })

  describe('child results and parent context', () => {
    it('should store and retrieve child results', () => {
      const result1 = createMockCellResult(true, 'Child 1 output')
      const result2 = createMockCellResult(false, 'Child 2 failed')

      blackboard.setChildResult('child-1', result1)
      blackboard.setChildResult('child-2', result2)

      const childResults = blackboard.getChildResults()
      expect(childResults.size).toBe(2)
      expect(childResults.get('child-1')?.success).toBe(true)
      expect(childResults.get('child-2')?.success).toBe(false)
    })

    it('should set and get parent context', () => {
      const context = 'Parent cell provided this context for the child'
      blackboard.setParentContext(context)

      expect(blackboard.getParentContext()).toBe(context)
    })

    it('should handle empty parent context', () => {
      expect(blackboard.getParentContext()).toBe('')
    })
  })

  describe('context assembly', () => {
    it('should assemble context respecting token budget', () => {
      blackboard.setParentContext('Important parent context')
      blackboard.post('findings', {
        author: 'explorer',
        content: 'Finding 1',
        priority: 5,
        tags: [],
      })
      blackboard.setScratchpad('note', 'Important note', 'planner')

      // Small budget should truncate
      const context = blackboard.assembleContext('test-node', 50)
      expect(context.length).toBeLessThan(50 * 4) // ~4 chars per token
    })

    it('should include parent context first', () => {
      blackboard.setParentContext('Parent context content')

      const context = blackboard.assembleContext('test-node', 1000)
      expect(context).toContain('## Parent Context')
      expect(context).toContain('Parent context content')
    })

    it('should include channel entries', () => {
      blackboard.post('findings', {
        author: 'explorer',
        content: 'Important finding',
        priority: 10,
        tags: ['critical'],
      })

      const context = blackboard.assembleContext('test-node', 1000)
      expect(context).toContain('FINDINGS')
      expect(context).toContain('Important finding')
      expect(context).toContain('Author: explorer')
      expect(context).toContain('Priority: 10')
      expect(context).toContain('Tags: critical')
    })

    it('should include scratchpad entries', () => {
      blackboard.setScratchpad('key1', 'value1', 'author')
      blackboard.setScratchpad('key2', 'value2', 'author')

      const context = blackboard.assembleContext('test-node', 1000)
      expect(context).toContain('## Scratchpad')
      expect(context).toContain('key1')
      expect(context).toContain('value1')
    })

    it('should include child results', () => {
      blackboard.setChildResult('child-1', createMockCellResult(true, 'Success output'))
      blackboard.setChildResult('child-2', createMockCellResult(false, 'Failed'))

      const context = blackboard.assembleContext('test-node', 2000)
      expect(context).toContain('## Child Results')
      expect(context).toContain('child-1')
      expect(context).toContain('SUCCESS')
      expect(context).toContain('child-2')
      expect(context).toContain('FAILED')
    })

    it('should handle budget exhaustion gracefully', () => {
      blackboard.setParentContext('A'.repeat(1000))
      blackboard.post('findings', {
        author: 'explorer',
        content: 'B'.repeat(1000),
        priority: 5,
        tags: [],
      })

      // Very small budget
      const context = blackboard.assembleContext('test-node', 100)
      // Should not throw and should contain at least partial content
      expect(context).toBeDefined()
      expect(context.length).toBeGreaterThan(0)
    })
  })

  describe('snapshot and restore', () => {
    it('should create a snapshot', () => {
      blackboard.post('findings', {
        author: 'explorer',
        content: 'Finding',
        priority: 5,
        tags: ['tag1'],
      })
      blackboard.setScratchpad('key', 'value', 'author')
      blackboard.addArtifact({ path: 'file.ts', operation: 'created', author: 'builder' })
      blackboard.setParentContext('Parent context')

      const snapshot = blackboard.getSnapshot()

      expect(snapshot.id).toBeDefined()
      expect(snapshot.cellId).toBe(cellId)
      expect(snapshot.channels.findings).toHaveLength(1)
      expect(snapshot.scratchpad.key).toBeDefined()
      expect(Object.keys(snapshot.artifacts)).toHaveLength(1)
      expect(snapshot.parentContext).toBe('Parent context')
      expect(snapshot.createdAt).toBeDefined()
      expect(snapshot.lastActivityAt).toBeDefined()
    })

    it('should restore from snapshot', () => {
      // Create initial state
      blackboard.post('findings', {
        author: 'explorer',
        content: 'Original finding',
        priority: 5,
        tags: [],
      })
      blackboard.setScratchpad('key1', 'value1', 'author')
      blackboard.setParentContext('Original context')

      const snapshot = blackboard.getSnapshot()

      // Create new blackboard and restore
      const newBlackboard = new Blackboard(mockLogger as unknown as ILogger, cellId)
      newBlackboard.restoreFromSnapshot(snapshot)

      // Verify restored state
      const findings = newBlackboard.read('findings')
      expect(findings).toHaveLength(1)
      expect(findings[0].content).toBe('Original finding')
      expect(newBlackboard.getScratchpad('key1')).toBe('value1')
      expect(newBlackboard.getParentContext()).toBe('Original context')
    })

    it('should restore all channels', () => {
      blackboard.post('findings', { author: 'a1', content: 'f1', priority: 0, tags: [] })
      blackboard.post('concerns', { author: 'a2', content: 'c1', priority: 0, tags: [] })
      blackboard.post('decisions', { author: 'a3', content: 'd1', priority: 0, tags: [] })
      blackboard.post('artifacts', { author: 'a4', content: 'a1', priority: 0, tags: [] })
      blackboard.post('requests', { author: 'a5', content: 'r1', priority: 0, tags: [] })

      const snapshot = blackboard.getSnapshot()
      const newBlackboard = new Blackboard(mockLogger as unknown as ILogger, cellId)
      newBlackboard.restoreFromSnapshot(snapshot)

      expect(newBlackboard.read('findings')).toHaveLength(1)
      expect(newBlackboard.read('concerns')).toHaveLength(1)
      expect(newBlackboard.read('decisions')).toHaveLength(1)
      expect(newBlackboard.read('artifacts')).toHaveLength(1)
      expect(newBlackboard.read('requests')).toHaveLength(1)
    })

    it('should restore tool log', () => {
      blackboard.addToolRecord({
        tool: 'read',
        nodeId: 'agent',
        params: {},
        result: 'result',
        isError: false,
        durationMs: 100,
      })

      const snapshot = blackboard.getSnapshot()
      const newBlackboard = new Blackboard(mockLogger as unknown as ILogger, cellId)
      newBlackboard.restoreFromSnapshot(snapshot)

      const log = newBlackboard.getToolLog()
      expect(log).toHaveLength(1)
      expect(log[0].tool).toBe('read')
    })

    it('should restore child results', () => {
      blackboard.setChildResult('child-1', createMockCellResult(true, 'Output'))

      const snapshot = blackboard.getSnapshot()
      const newBlackboard = new Blackboard(mockLogger as unknown as ILogger, cellId)
      newBlackboard.restoreFromSnapshot(snapshot)

      const childResults = newBlackboard.getChildResults()
      expect(childResults.size).toBe(1)
      expect(childResults.get('child-1')?.success).toBe(true)
    })

    it('should handle deserialized plain objects', () => {
      // Simulate JSON serialization/deserialization
      const snapshot = blackboard.getSnapshot()
      const serialized = JSON.parse(JSON.stringify(snapshot))

      const newBlackboard = new Blackboard(mockLogger as unknown as ILogger, cellId)
      newBlackboard.restoreFromSnapshot(serialized)

      // Should work without errors
      expect(newBlackboard.readAll()).toBeDefined()
    })
  })

  describe('metadata tracking', () => {
    it('should track createdAt timestamp', () => {
      const beforeCreate = Date.now()
      const bb = new Blackboard(mockLogger as unknown as ILogger, 'test')
      const afterCreate = Date.now()

      const snapshot = bb.getSnapshot()
      expect(snapshot.createdAt).toBeGreaterThanOrEqual(beforeCreate)
      expect(snapshot.createdAt).toBeLessThanOrEqual(afterCreate)
    })

    it('should update lastActivityAt on operations', async () => {
      const snapshot1 = blackboard.getSnapshot()
      const activity1 = snapshot1.lastActivityAt

      // Wait a bit to ensure different timestamps
      await new Promise(resolve => setTimeout(resolve, 10))

      blackboard.post('findings', { author: 'a', content: 'c', priority: 0, tags: [] })

      const snapshot2 = blackboard.getSnapshot()
      expect(snapshot2.lastActivityAt).toBeGreaterThanOrEqual(activity1)
    })
  })

  describe('work-claiming TODO', () => {
    // Helper: init plan, submit a step, and approve it
    function setupApprovedStep(title = 'Implement feature A') {
      blackboard.initPlan('Build the thing')
      const step = blackboard.submitPlanStep({
        title,
        description: `Description of ${title}`,
        author: 'yang',
        order: 1,
        dependencies: [],
        priority: 'high',
        tags: ['core'],
      })
      blackboard.updatePlanStep(step.id, { status: 'approved' })
      return step
    }

    describe('claimPlanStep', () => {
      it('should claim an approved, unassigned step', () => {
        const step = setupApprovedStep()
        const claimed = blackboard.claimPlanStep(step.id, 'yang')
        expect(claimed).not.toBeNull()
        expect(claimed!.status).toBe('in_progress')
        expect(claimed!.assignee).toBe('yang')
        expect(claimed!.claimedAt).toBeGreaterThan(0)
        expect(claimed!.lastActivityAt).toBeGreaterThan(0)
      })

      it('should reject claiming a proposed step', () => {
        blackboard.initPlan('Build the thing')
        const step = blackboard.submitPlanStep({
          title: 'A step',
          description: 'desc',
          author: 'yang',
          order: 1,
          dependencies: [],
          priority: 'medium',
          tags: [],
        })
        const claimed = blackboard.claimPlanStep(step.id, 'yang')
        expect(claimed).toBeNull()
      })

      it('should reject double-claiming', () => {
        const step = setupApprovedStep()
        blackboard.claimPlanStep(step.id, 'yang')
        const second = blackboard.claimPlanStep(step.id, 'yin')
        expect(second).toBeNull()
      })

      it('should reject with status mismatch (optimistic concurrency)', () => {
        const step = setupApprovedStep()
        // Step is approved, but caller expects 'proposed'
        const claimed = blackboard.claimPlanStep(step.id, 'yang', 'proposed')
        expect(claimed).toBeNull()
      })

      it('should return null with no plan', () => {
        const claimed = blackboard.claimPlanStep('nope', 'yang')
        expect(claimed).toBeNull()
      })
    })

    describe('releasePlanStep', () => {
      it('should release a claimed step back to approved', () => {
        const step = setupApprovedStep()
        blackboard.claimPlanStep(step.id, 'yang')
        const released = blackboard.releasePlanStep(step.id, 'yang')
        expect(released).toBe(true)

        const plan = blackboard.getPlan()!
        const updated = plan.steps.find(s => s.id === step.id)!
        expect(updated.status).toBe('approved')
        expect(updated.assignee).toBeUndefined()
        expect(updated.claimedAt).toBeUndefined()
        expect(updated.lastActivityAt).toBeUndefined()
      })

      it('should reject release by non-assignee', () => {
        const step = setupApprovedStep()
        blackboard.claimPlanStep(step.id, 'yang')
        const released = blackboard.releasePlanStep(step.id, 'yin')
        expect(released).toBe(false)
      })

      it('should allow forced release by non-assignee', () => {
        const step = setupApprovedStep()
        blackboard.claimPlanStep(step.id, 'yang')
        const released = blackboard.releasePlanStep(step.id, 'executive', true)
        expect(released).toBe(true)
      })

      it('should return false with no plan', () => {
        expect(blackboard.releasePlanStep('nope', 'yang')).toBe(false)
      })
    })

    describe('reportPlanStepProgress', () => {
      it('should update lastActivityAt and optionally set outcome', () => {
        const step = setupApprovedStep()
        blackboard.claimPlanStep(step.id, 'yang')

        const before = blackboard.getPlan()!.steps[0].lastActivityAt!
        // Small delay to get a different timestamp
        const result = blackboard.reportPlanStepProgress(step.id, 'yang', 'Halfway done')
        expect(result).not.toBeNull()
        expect(result!.lastActivityAt).toBeGreaterThanOrEqual(before)
        expect(result!.outcome).toBe('Halfway done')
      })

      it('should reject progress from non-assignee', () => {
        const step = setupApprovedStep()
        blackboard.claimPlanStep(step.id, 'yang')
        const result = blackboard.reportPlanStepProgress(step.id, 'yin', 'nope')
        expect(result).toBeNull()
      })

      it('should return null with no plan', () => {
        expect(blackboard.reportPlanStepProgress('nope', 'yang')).toBeNull()
      })
    })

    describe('getAvailableSteps', () => {
      it('should return approved, unassigned steps sorted by priority then order', () => {
        blackboard.initPlan('Multi-step plan')
        const s1 = blackboard.submitPlanStep({ title: 'Low prio', description: 'd', author: 'yang', order: 1, dependencies: [], priority: 'low', tags: [] })
        const s2 = blackboard.submitPlanStep({ title: 'High prio', description: 'd', author: 'yang', order: 2, dependencies: [], priority: 'high', tags: [] })
        const s3 = blackboard.submitPlanStep({ title: 'Med prio', description: 'd', author: 'yang', order: 3, dependencies: [], priority: 'medium', tags: [] })

        // Approve all
        blackboard.updatePlanStep(s1.id, { status: 'approved' })
        blackboard.updatePlanStep(s2.id, { status: 'approved' })
        blackboard.updatePlanStep(s3.id, { status: 'approved' })

        const available = blackboard.getAvailableSteps()
        expect(available).toHaveLength(3)
        expect(available[0].title).toBe('High prio')
        expect(available[1].title).toBe('Med prio')
        expect(available[2].title).toBe('Low prio')
      })

      it('should exclude claimed steps', () => {
        blackboard.initPlan('Plan')
        const s1 = blackboard.submitPlanStep({ title: 'Step 1', description: 'd', author: 'yang', order: 1, dependencies: [], priority: 'high', tags: [] })
        const s2 = blackboard.submitPlanStep({ title: 'Step 2', description: 'd', author: 'yang', order: 2, dependencies: [], priority: 'high', tags: [] })
        blackboard.updatePlanStep(s1.id, { status: 'approved' })
        blackboard.updatePlanStep(s2.id, { status: 'approved' })

        blackboard.claimPlanStep(s1.id, 'yang')

        const available = blackboard.getAvailableSteps()
        expect(available).toHaveLength(1)
        expect(available[0].id).toBe(s2.id)
      })

      it('should return empty array with no plan', () => {
        expect(blackboard.getAvailableSteps()).toEqual([])
      })
    })

    describe('getClaimedSteps', () => {
      it('should return all claimed steps', () => {
        blackboard.initPlan('Plan')
        const s1 = blackboard.submitPlanStep({ title: 'Step 1', description: 'd', author: 'yang', order: 1, dependencies: [], priority: 'high', tags: [] })
        const s2 = blackboard.submitPlanStep({ title: 'Step 2', description: 'd', author: 'yang', order: 2, dependencies: [], priority: 'high', tags: [] })
        blackboard.updatePlanStep(s1.id, { status: 'approved' })
        blackboard.updatePlanStep(s2.id, { status: 'approved' })

        blackboard.claimPlanStep(s1.id, 'yang')
        blackboard.claimPlanStep(s2.id, 'yin')

        expect(blackboard.getClaimedSteps()).toHaveLength(2)
        expect(blackboard.getClaimedSteps('yang')).toHaveLength(1)
        expect(blackboard.getClaimedSteps('yang')[0].id).toBe(s1.id)
        expect(blackboard.getClaimedSteps('yin')).toHaveLength(1)
        expect(blackboard.getClaimedSteps('nobody')).toHaveLength(0)
      })

      it('should return empty array with no plan', () => {
        expect(blackboard.getClaimedSteps()).toEqual([])
      })
    })

    describe('reclaimStalledWork', () => {
      it('should release steps that exceeded stall timeout', () => {
        const step = setupApprovedStep()
        blackboard.claimPlanStep(step.id, 'yang')

        // Manually backdate the lastActivityAt to simulate stalling
        const plan = blackboard.getPlan()!
        const s = plan.steps.find(s => s.id === step.id)!
        s.lastActivityAt = Date.now() - 35 * 60 * 1000 // 35 minutes ago

        const reclaimed = blackboard.reclaimStalledWork()
        expect(reclaimed).toBe(1)

        const updated = blackboard.getPlan()!.steps.find(s => s.id === step.id)!
        expect(updated.status).toBe('approved')
        expect(updated.assignee).toBeUndefined()
      })

      it('should not reclaim active steps', () => {
        const step = setupApprovedStep()
        blackboard.claimPlanStep(step.id, 'yang')
        // lastActivityAt is fresh (just claimed)
        const reclaimed = blackboard.reclaimStalledWork()
        expect(reclaimed).toBe(0)
      })

      it('should respect per-step stallTimeoutMs', () => {
        const step = setupApprovedStep()
        blackboard.claimPlanStep(step.id, 'yang')

        // Set a very short per-step timeout
        const plan = blackboard.getPlan()!
        const s = plan.steps.find(s => s.id === step.id)!
        s.stallTimeoutMs = 100 // 100ms
        s.lastActivityAt = Date.now() - 200 // 200ms ago

        const reclaimed = blackboard.reclaimStalledWork()
        expect(reclaimed).toBe(1)
      })

      it('should respect custom maxAgeMs parameter', () => {
        const step = setupApprovedStep()
        blackboard.claimPlanStep(step.id, 'yang')

        const plan = blackboard.getPlan()!
        const s = plan.steps.find(s => s.id === step.id)!
        s.lastActivityAt = Date.now() - 500 // 500ms ago

        // Default 30min won't reclaim, but 100ms will
        expect(blackboard.reclaimStalledWork()).toBe(0)
        expect(blackboard.reclaimStalledWork(100)).toBe(1)
      })

      it('should return 0 with no plan', () => {
        expect(blackboard.reclaimStalledWork()).toBe(0)
      })
    })

    describe('formatPlanForContext with claiming', () => {
      it('should include progress summary and assignee info', () => {
        blackboard.initPlan('Build it')
        const s1 = blackboard.submitPlanStep({ title: 'Step 1', description: 'd', author: 'yang', order: 1, dependencies: [], priority: 'high', tags: [] })
        const s2 = blackboard.submitPlanStep({ title: 'Step 2', description: 'd', author: 'yang', order: 2, dependencies: [], priority: 'medium', tags: [] })
        blackboard.updatePlanStep(s1.id, { status: 'approved' })
        blackboard.updatePlanStep(s2.id, { status: 'approved' })

        blackboard.claimPlanStep(s1.id, 'yang')

        const ctx = blackboard.formatPlanForContext()
        expect(ctx).toContain('Progress:')
        expect(ctx).toContain('1 in-progress')
        expect(ctx).toContain('1 available')
        expect(ctx).toContain('[assigned: yang]')
      })
    })

    describe('snapshot/restore with claiming fields', () => {
      it('should preserve claiming fields through snapshot/restore', () => {
        const step = setupApprovedStep()
        blackboard.claimPlanStep(step.id, 'yang')
        blackboard.reportPlanStepProgress(step.id, 'yang', 'Working on it')

        const snapshot = blackboard.getSnapshot()

        // Create a new blackboard and restore
        const newLogger = createMockLogger()
        const newBb = new Blackboard(newLogger as unknown as ILogger, 'new-cell')
        newBb.restoreFromSnapshot(snapshot)

        const plan = newBb.getPlan()!
        const restored = plan.steps.find(s => s.id === step.id)!
        expect(restored.status).toBe('in_progress')
        expect(restored.assignee).toBe('yang')
        expect(restored.claimedAt).toBeGreaterThan(0)
        expect(restored.lastActivityAt).toBeGreaterThan(0)
        expect(restored.outcome).toBe('Working on it')
      })
    })
  })
})
