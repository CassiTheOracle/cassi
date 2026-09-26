/**
 * PlanHandler tests for FluxTeam planning system
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { Blackboard } from '../src/blackboard.js'
import { PlanHandler } from '../src/plan-handler.js'
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

describe('PlanHandler', () => {
  let blackboard: Blackboard
  let handler: PlanHandler
  let mockLogger: ReturnType<typeof createMockLogger>
  const cellId = 'test-cell-123'

  beforeEach(() => {
    mockLogger = createMockLogger()
    blackboard = new Blackboard(mockLogger as unknown as ILogger, cellId)
    blackboard.initPlan('Optimize HTTP API startup')
    handler = new PlanHandler(blackboard, mockLogger as unknown as ILogger)
  })


  describe('static helpers', () => {
    it('should identify plan meta-tools', () => {
      expect(PlanHandler.isPlanMetaTool('plan_submit_step')).toBe(true)
      expect(PlanHandler.isPlanMetaTool('plan_view')).toBe(true)
      expect(PlanHandler.isPlanMetaTool('plan_approve_step')).toBe(true)
      expect(PlanHandler.isPlanMetaTool('plan_reject_step')).toBe(true)
      expect(PlanHandler.isPlanMetaTool('plan_update_step')).toBe(true)
      expect(PlanHandler.isPlanMetaTool('plan_finalize')).toBe(true)
    })

    it('should not identify non-plan tools as plan meta-tools', () => {
      expect(PlanHandler.isPlanMetaTool('share_finding')).toBe(false)
      expect(PlanHandler.isPlanMetaTool('read')).toBe(false)
      expect(PlanHandler.isPlanMetaTool('bash')).toBe(false)
      expect(PlanHandler.isPlanMetaTool('')).toBe(false)
    })
  })


  describe('plan_submit_step', () => {
    it('should submit a step as proposed', () => {
      const result = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Parallelize intelligence init',
        description: 'Use Promise.all for independent modules after memory is created.',
      }, 'yang'))

      expect(result.success).toBe(true)
      expect(result.step.title).toBe('Parallelize intelligence init')
      expect(result.step.status).toBe('proposed')
      expect(result.step.author).toBe('yang')
      expect(result.step.id).toMatch(/^step-/)
    })

    it('should allow yin to submit steps', () => {
      const result = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Add error handling to SessionStore',
        description: 'Wrap open() in try/catch to prevent startup crashes.',
        priority: 'high',
        order: 1,
      }, 'yin'))

      expect(result.success).toBe(true)
      expect(result.step.author).toBe('yin')
      expect(result.step.priority).toBe('high')
      expect(result.step.order).toBe(1)
    })

    it('should allow executive to submit steps', () => {
      const result = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Early HTTP server start',
        description: 'Start server immediately, add 503 readiness gate.',
      }, 'executive'))

      expect(result.success).toBe(true)
      expect(result.step.author).toBe('executive')
    })

    it('should require title and description', () => {
      const result = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Missing description',
      }, 'yang'))

      expect(result.error).toBeDefined()
      expect(result.error).toContain('required')
    })

    it('should auto-assign order when not provided', () => {
      const r1 = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Step 1',
        description: 'First step',
      }, 'yang'))

      const r2 = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Step 2',
        description: 'Second step',
      }, 'yin'))

      expect(r2.step.order).toBeGreaterThan(r1.step.order)
    })

    it('should support dependencies and tags', () => {
      const r1 = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Step 1',
        description: 'First step',
      }, 'yang'))

      const result = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Step 2',
        description: 'Depends on step 1',
        dependencies: [r1.step.id],
        tags: ['optimization', 'parallelization'],
      }, 'yang'))

      expect(result.step.dependencies).toEqual([r1.step.id])
      expect(result.step.tags).toEqual(['optimization', 'parallelization'])
    })
  })


  describe('plan_view', () => {
    it('should return the plan with all steps', () => {
      handler.handleToolCall('plan_submit_step', {
        title: 'Step 1',
        description: 'First step',
        order: 1,
      }, 'yang')

      handler.handleToolCall('plan_submit_step', {
        title: 'Step 2',
        description: 'Second step',
        order: 2,
      }, 'yin')

      const result = JSON.parse(handler.handleToolCall('plan_view', {}, 'yang'))

      expect(result.plan).toBeDefined()
      expect(result.plan.goal).toBe('Optimize HTTP API startup')
      expect(result.plan.status).toBe('drafting')
      expect(result.plan.stepCount).toBe(2)
      expect(result.plan.steps).toHaveLength(2)
      // Steps should be sorted by order
      expect(result.plan.steps[0].title).toBe('Step 1')
      expect(result.plan.steps[1].title).toBe('Step 2')
    })

    it('should include status breakdown', () => {
      handler.handleToolCall('plan_submit_step', {
        title: 'Step A',
        description: 'A',
      }, 'yang')

      handler.handleToolCall('plan_submit_step', {
        title: 'Step B',
        description: 'B',
      }, 'yin')

      const result = JSON.parse(handler.handleToolCall('plan_view', {}, 'executive'))

      expect(result.plan.statusBreakdown.proposed).toBe(2)
      expect(result.plan.statusBreakdown.approved).toBe(0)
    })

    it('should be accessible to all postures', () => {
      for (const posture of ['yang', 'yin', 'executive'] as const) {
        const result = JSON.parse(handler.handleToolCall('plan_view', {}, posture))
        expect(result.plan).toBeDefined()
      }
    })
  })


  describe('plan_approve_step', () => {
    it('should approve a proposed step', () => {
      const step = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Good step',
        description: 'This is valid',
      }, 'yang')).step

      const result = JSON.parse(handler.handleToolCall('plan_approve_step', {
        step_id: step.id,
      }, 'executive'))

      expect(result.success).toBe(true)
      expect(result.step.status).toBe('approved')
    })

    it('should reject access from yang', () => {
      const step = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Step',
        description: 'Test',
      }, 'yang')).step

      const result = JSON.parse(handler.handleToolCall('plan_approve_step', {
        step_id: step.id,
      }, 'yang'))

      expect(result.error).toBeDefined()
      expect(result.error).toContain('restricted to the Executive')
    })

    it('should reject access from yin', () => {
      const step = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Step',
        description: 'Test',
      }, 'yang')).step

      const result = JSON.parse(handler.handleToolCall('plan_approve_step', {
        step_id: step.id,
      }, 'yin'))

      expect(result.error).toBeDefined()
      expect(result.error).toContain('restricted to the Executive')
    })

    it('should return error for missing step_id', () => {
      const result = JSON.parse(handler.handleToolCall('plan_approve_step', {}, 'executive'))
      expect(result.error).toContain('step_id is required')
    })

    it('should return error for non-existent step', () => {
      const result = JSON.parse(handler.handleToolCall('plan_approve_step', {
        step_id: 'step-nonexistent',
      }, 'executive'))

      expect(result.error).toContain('Step not found')
    })
  })


  describe('plan_reject_step', () => {
    it('should reject a step with a reason', () => {
      const step = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Risky step',
        description: 'This could break things',
      }, 'yang')).step

      const result = JSON.parse(handler.handleToolCall('plan_reject_step', {
        step_id: step.id,
        reason: 'Too risky without test coverage.',
      }, 'executive'))

      expect(result.success).toBe(true)
      expect(result.step.status).toBe('rejected')
      expect(result.step.rejectionReason).toBe('Too risky without test coverage.')
    })

    it('should require a reason', () => {
      const step = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Step',
        description: 'Test',
      }, 'yang')).step

      const result = JSON.parse(handler.handleToolCall('plan_reject_step', {
        step_id: step.id,
      }, 'executive'))

      expect(result.error).toContain('reason is required')
    })

    it('should restrict to executive only', () => {
      const result = JSON.parse(handler.handleToolCall('plan_reject_step', {
        step_id: 'step-123',
        reason: 'Bad idea',
      }, 'yang'))

      expect(result.error).toContain('restricted to the Executive')
    })
  })


  describe('plan_update_step', () => {
    it('should update step fields', () => {
      const step = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Original title',
        description: 'Original description',
        priority: 'low',
        order: 5,
      }, 'yang')).step

      const result = JSON.parse(handler.handleToolCall('plan_update_step', {
        step_id: step.id,
        title: 'Updated title',
        priority: 'high',
        order: 1,
      }, 'executive'))

      expect(result.success).toBe(true)
      expect(result.step.title).toBe('Updated title')
      expect(result.step.priority).toBe('high')
      expect(result.step.order).toBe(1)
      // Unchanged fields remain
      expect(result.step.description).toBe('Original description')
    })

    it('should update step status', () => {
      const step = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Step',
        description: 'Test',
      }, 'yang')).step

      const result = JSON.parse(handler.handleToolCall('plan_update_step', {
        step_id: step.id,
        status: 'in_progress',
      }, 'executive'))

      expect(result.step.status).toBe('in_progress')
    })

    it('should require at least one field to update', () => {
      const step = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Step',
        description: 'Test',
      }, 'yang')).step

      const result = JSON.parse(handler.handleToolCall('plan_update_step', {
        step_id: step.id,
      }, 'executive'))

      expect(result.error).toContain('No fields to update')
    })

    it('should restrict to executive only', () => {
      const result = JSON.parse(handler.handleToolCall('plan_update_step', {
        step_id: 'step-123',
        title: 'New title',
      }, 'yin'))

      expect(result.error).toContain('restricted to the Executive')
    })
  })


  describe('plan_finalize', () => {
    it('should finalize plan as approved', () => {
      handler.handleToolCall('plan_submit_step', {
        title: 'Step 1',
        description: 'First step',
      }, 'yang')

      const result = JSON.parse(handler.handleToolCall('plan_finalize', {
        status: 'approved',
        summary: 'Plan ready for implementation.',
      }, 'executive'))

      expect(result.success).toBe(true)
      expect(result.plan.status).toBe('approved')
      expect(result.plan.summary).toBe('Plan ready for implementation.')
      expect(result.plan.approvedBy).toBe('executive')
    })

    it('should finalize plan as completed', () => {
      const result = JSON.parse(handler.handleToolCall('plan_finalize', {
        status: 'completed',
        summary: 'All steps done.',
      }, 'executive'))

      expect(result.success).toBe(true)
      expect(result.plan.status).toBe('completed')
    })

    it('should finalize plan as abandoned', () => {
      const result = JSON.parse(handler.handleToolCall('plan_finalize', {
        status: 'abandoned',
        summary: 'Goal changed, plan no longer relevant.',
      }, 'executive'))

      expect(result.success).toBe(true)
      expect(result.plan.status).toBe('abandoned')
    })

    it('should reject invalid status', () => {
      const result = JSON.parse(handler.handleToolCall('plan_finalize', {
        status: 'invalid',
      }, 'executive'))

      expect(result.error).toContain('Invalid status')
    })

    it('should restrict to executive only', () => {
      const result = JSON.parse(handler.handleToolCall('plan_finalize', {
        status: 'approved',
      }, 'yang'))

      expect(result.error).toContain('restricted to the Executive')
    })
  })


  describe('Blackboard plan integration', () => {
    it('should initialize plan on the blackboard', () => {
      const freshBlackboard = new Blackboard(mockLogger as unknown as ILogger, 'fresh-cell')
      const plan = freshBlackboard.initPlan('Test goal')

      expect(plan.id).toMatch(/^plan-/)
      expect(plan.goal).toBe('Test goal')
      expect(plan.status).toBe('drafting')
      expect(plan.steps).toEqual([])
    })

    it('should return existing plan on duplicate init', () => {
      const freshBlackboard = new Blackboard(mockLogger as unknown as ILogger, 'fresh-cell')
      const plan1 = freshBlackboard.initPlan('Goal 1')
      const plan2 = freshBlackboard.initPlan('Goal 2')

      expect(plan1.id).toBe(plan2.id)
      expect(plan2.goal).toBe('Goal 1') // First goal preserved
    })

    it('should include plan in context assembly', () => {
      handler.handleToolCall('plan_submit_step', {
        title: 'Test step',
        description: 'A test step for context assembly',
        order: 1,
      }, 'yang')

      const context = blackboard.assembleContext('test-node', 10000)

      expect(context).toContain('Current Plan')
      expect(context).toContain('Test step')
    })

    it('should include plan in snapshot', () => {
      handler.handleToolCall('plan_submit_step', {
        title: 'Snapshot step',
        description: 'This should persist in snapshots',
      }, 'yang')

      const snapshot = blackboard.getSnapshot()

      expect(snapshot.plan).toBeDefined()
      expect(snapshot.plan!.steps).toHaveLength(1)
      expect(snapshot.plan!.steps[0].title).toBe('Snapshot step')
    })

    it('should restore plan from snapshot', () => {
      handler.handleToolCall('plan_submit_step', {
        title: 'Persistent step',
        description: 'Should survive restore',
      }, 'yang')

      const snapshot = blackboard.getSnapshot()

      // Create new blackboard and restore
      const restoredBlackboard = new Blackboard(mockLogger as unknown as ILogger, 'restored-cell')
      restoredBlackboard.restoreFromSnapshot(snapshot)

      const restoredPlan = restoredBlackboard.getPlan()
      expect(restoredPlan).toBeDefined()
      expect(restoredPlan!.steps).toHaveLength(1)
      expect(restoredPlan!.steps[0].title).toBe('Persistent step')
    })

    it('should format plan for context injection', () => {
      handler.handleToolCall('plan_submit_step', {
        title: 'Step A',
        description: 'Do A first',
        order: 1,
        priority: 'high',
      }, 'yang')

      handler.handleToolCall('plan_submit_step', {
        title: 'Step B',
        description: 'Then do B',
        order: 2,
        priority: 'medium',
        dependencies: ['step-placeholder'],
      }, 'yin')

      const text = blackboard.formatPlanForContext()

      expect(text).toContain('Optimize HTTP API startup')
      expect(text).toContain('drafting')
      expect(text).toContain('[PROPOSED] Step A (high)')
      expect(text).toContain('[PROPOSED] Step B (medium)')
      expect(text).toContain('Do A first')
      expect(text).toContain('Then do B')
    })
  })


  describe('end-to-end planning workflow', () => {
    it('should support a full submit → review → approve → finalize cycle', () => {
      // Yang submits steps
      const s1 = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Parallelize plugin loading',
        description: 'Load channel workers in parallel using Promise.all.',
        order: 1,
        priority: 'high',
      }, 'yang')).step

      const s2 = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Early HTTP server start',
        description: 'Start HTTP server before intelligence modules, add 503 gate.',
        order: 2,
        priority: 'high',
      }, 'yang')).step

      // Yin submits a concern as a step
      const s3 = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Add error handling to SessionStore',
        description: 'Wrap open() in try/catch — currently crashes daemon if DB is locked.',
        order: 0,
        priority: 'high',
        tags: ['safety', 'prerequisite'],
      }, 'yin')).step

      // Executive reviews
      const plan = JSON.parse(handler.handleToolCall('plan_view', {}, 'executive')).plan
      expect(plan.stepCount).toBe(3)

      // Executive approves safety step and reorders
      handler.handleToolCall('plan_approve_step', { step_id: s3.id }, 'executive')
      handler.handleToolCall('plan_approve_step', { step_id: s1.id }, 'executive')
      handler.handleToolCall('plan_approve_step', { step_id: s2.id }, 'executive')

      // Executive finalizes
      const finalResult = JSON.parse(handler.handleToolCall('plan_finalize', {
        status: 'approved',
        summary: 'Safety-first approach: error handling → parallel loading → early HTTP.',
      }, 'executive'))

      expect(finalResult.success).toBe(true)
      expect(finalResult.plan.status).toBe('approved')
      expect(finalResult.plan.statusBreakdown.approved).toBe(3)
      expect(finalResult.plan.summary).toContain('Safety-first')
    })

    it('should support reject and resubmit cycle', () => {
      // Yang submits a risky step
      const s1 = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Remove all sync DB calls',
        description: 'Replace every synchronous better-sqlite3 call.',
        priority: 'high',
      }, 'yang')).step

      // Executive rejects
      handler.handleToolCall('plan_reject_step', {
        step_id: s1.id,
        reason: 'Too broad. Focus on startup-path sync calls only.',
      }, 'executive')

      // Yang resubmits with narrower scope
      const s2 = JSON.parse(handler.handleToolCall('plan_submit_step', {
        title: 'Defer SessionStore.prune() to background',
        description: 'Move the startup prune() call to a setTimeout after init completes.',
        priority: 'medium',
      }, 'yang')).step

      // Executive approves refined step
      const result = JSON.parse(handler.handleToolCall('plan_approve_step', {
        step_id: s2.id,
      }, 'executive'))

      expect(result.step.status).toBe('approved')

      // Verify rejected step is still visible
      const plan = JSON.parse(handler.handleToolCall('plan_view', {}, 'executive')).plan
      expect(plan.statusBreakdown.rejected).toBe(1)
      expect(plan.statusBreakdown.approved).toBe(1)
    })
  })


  describe('error handling', () => {
    it('should handle unknown tool names', () => {
      const result = JSON.parse(handler.handleToolCall('plan_unknown', {}, 'executive'))
      expect(result.error).toContain('Unknown plan tool')
    })

    it('should handle submission when no plan exists', () => {
      const emptyBlackboard = new Blackboard(mockLogger as unknown as ILogger, 'empty-cell')
      const emptyHandler = new PlanHandler(emptyBlackboard, mockLogger as unknown as ILogger)

      const result = JSON.parse(emptyHandler.handleToolCall('plan_submit_step', {
        title: 'Step',
        description: 'No plan initialized',
      }, 'yang'))

      expect(result.error).toBeDefined()
    })
  })
})
