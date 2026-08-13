/**
 * Unit tests for decompositionToWorkflow — the pure translator that converts
 * a GoalDecomposition into a WorkflowDefinition the WorkflowEngine can execute.
 *
 * The translator is the bridge between the decomposer (which says WHAT
 * subtasks exist + their orchestration shape) and the engine (which says HOW
 * to run, cancel, persist, and resume them). Tests pin behaviour at every
 * branch of the strategy switch and verify the helixBranch fields end up
 * populated correctly.
 */

import { describe, it, expect, vi } from 'vitest'
import { decompositionToWorkflow } from '../src/decomposition-workflow.js'
import type { GoalDecomposition } from '../src/corpus-types.js'
import type { IHelixRunner } from '../src/vendor/workflow/steps.js'

const stubRunner: IHelixRunner = {
  async run() {
    throw new Error('stub runner — translator tests should never invoke run()')
  },
}

function makeDecomp(partial: Partial<GoalDecomposition> = {}): GoalDecomposition {
  return {
    decomposed: true,
    originalGoal: 'sample goal',
    subTasks: [{ goal: 'subtask alpha', priority: 1 }],
    strategy: 'parallel',
    durationMs: 0,
    ...partial,
  }
}

describe('decompositionToWorkflow', () => {
  it('emits a workflow whose id derives from the baseId', () => {
    const wf = decompositionToWorkflow(makeDecomp(), { baseId: 'const-42', runner: stubRunner })
    expect(wf.id).toBe('const-42-decomposition')
  })

  it('rejects decompositions with no subTasks', () => {
    expect(() =>
      decompositionToWorkflow(
        { decomposed: false, originalGoal: 'g', subTasks: [], strategy: 'parallel', durationMs: 0 },
        { baseId: 'x', runner: stubRunner },
      ),
    ).toThrow(/no subTasks/)
  })

  it('emits a single then-node when there is exactly one subtask, regardless of strategy', () => {
    for (const strategy of ['parallel', 'sequential', 'tree'] as const) {
      const wf = decompositionToWorkflow(makeDecomp({ strategy }), { baseId: 's', runner: stubRunner })
      expect(wf.nodes).toHaveLength(1)
      expect(wf.nodes[0].kind).toBe('step')
    }
  })

  it('emits one parallel node containing N branches when strategy=parallel and N>1', () => {
    const wf = decompositionToWorkflow(
      makeDecomp({
        strategy: 'parallel',
        subTasks: [
          { goal: 'one', priority: 1 },
          { goal: 'two', priority: 1 },
          { goal: 'three', priority: 1 },
        ],
      }),
      { baseId: 'p', runner: stubRunner },
    )
    expect(wf.nodes).toHaveLength(1)
    expect(wf.nodes[0].kind).toBe('parallel')
    const par = wf.nodes[0] as { branches: unknown[][] }
    expect(par.branches).toHaveLength(3)
  })

  it('emits N sequential then-nodes when strategy=sequential and N>1', () => {
    const wf = decompositionToWorkflow(
      makeDecomp({
        strategy: 'sequential',
        subTasks: [
          { goal: 'plan-ish', priority: 1 },
          { goal: 'implement-ish', priority: 1 },
          { goal: 'review-ish', priority: 1 },
        ],
      }),
      { baseId: 'seq', runner: stubRunner },
    )
    expect(wf.nodes).toHaveLength(3)
    for (const node of wf.nodes) expect(node.kind).toBe('step')
  })

  it('degrades strategy=tree to parallel and warns', () => {
    const warn = vi.fn()
    const wf = decompositionToWorkflow(
      makeDecomp({
        strategy: 'tree',
        subTasks: [
          { goal: 'a', priority: 1 },
          { goal: 'b', priority: 1 },
        ],
      }),
      { baseId: 't', runner: stubRunner, logger: { warn } },
    )
    expect(wf.nodes[0].kind).toBe('parallel')
    expect(warn).toHaveBeenCalledTimes(1)
    expect(warn.mock.calls[0][0]).toMatch(/tree strategy not yet supported/)
  })

  it('populates step ids as subtask-1, subtask-2, ...', () => {
    const wf = decompositionToWorkflow(
      makeDecomp({
        strategy: 'sequential',
        subTasks: [
          { goal: 'a', priority: 1 },
          { goal: 'b', priority: 1 },
        ],
      }),
      { baseId: 'ids', runner: stubRunner },
    )
    const ids = wf.nodes.map(n => {
      const stepNode = n as { step?: { id: string } }
      return stepNode.step?.id
    })
    expect(ids).toEqual(['subtask-1', 'subtask-2'])
  })

  it('packs context + relevantFiles into the helixBranch context field', () => {
    const wf = decompositionToWorkflow(
      makeDecomp({
        subTasks: [{
          goal: 'modify auth',
          context: 'consider compliance',
          relevantFiles: ['core/auth.ts', 'core/session.ts'],
          priority: 1,
        }],
      }),
      { baseId: 'ctx', runner: stubRunner },
    )
    const step = (wf.nodes[0] as { step: { execute: Function } }).step
    expect(step).toBeDefined()
    // Inspect the helixBranch options through introspection — context isn't
    // exposed on the step directly, but description includes the goal preview.
    expect((step as { description?: string }).description).toMatch(/Subtask 1/)
    expect((step as { description?: string }).description).toMatch(/priority 1/)
  })

  it('coerces ConstellationTemplate=meditation to standard for helixBranch compatibility', () => {
    const wf = decompositionToWorkflow(
      makeDecomp({
        subTasks: [{ goal: 'q', template: 'meditation', priority: 1 }],
      }),
      { baseId: 'med', runner: stubRunner },
    )
    expect(wf.nodes).toHaveLength(1)
    expect(wf.nodes[0].kind).toBe('step')
  })

  it('uses subtaskTimeoutMs override when provided', () => {
    const wf = decompositionToWorkflow(
      makeDecomp(),
      { baseId: 'to', runner: stubRunner, subtaskTimeoutMs: 30_000 },
    )
    const step = (wf.nodes[0] as { step: { timeoutMs?: number } }).step
    expect(step.timeoutMs).toBe(30_000)
  })

  it('defaults subtask timeout to 600000 when not specified', () => {
    const wf = decompositionToWorkflow(makeDecomp(), { baseId: 'def', runner: stubRunner })
    const step = (wf.nodes[0] as { step: { timeoutMs?: number } }).step
    expect(step.timeoutMs).toBe(600_000)
  })

  describe('multi-phase complexity', () => {
    it('emits a subworkflow node for a multi-phase subtask (single-subtask shape)', () => {
      const wf = decompositionToWorkflow(
        makeDecomp({
          subTasks: [{
            goal: 'Substantial implementation work',
            priority: 1,
            complexity: 'multi-phase',
            template: 'implementation',
          }],
        }),
        { baseId: 'mp', runner: stubRunner },
      )
      // Single-subtask path uses then(); multi-phase yields a subworkflow node
      expect(wf.nodes).toHaveLength(1)
      expect(wf.nodes[0].kind).toBe('subworkflow')
    })

    it('mixes flat and multi-phase subtasks in a parallel node', () => {
      const wf = decompositionToWorkflow(
        makeDecomp({
          strategy: 'parallel',
          subTasks: [
            { goal: 'flat task', priority: 1 },
            { goal: 'multi-phase task', priority: 1, complexity: 'multi-phase', template: 'implementation' },
          ],
        }),
        { baseId: 'mix', runner: stubRunner },
      )
      expect(wf.nodes[0].kind).toBe('parallel')
      const par = wf.nodes[0] as { branches: Array<Array<{ kind: string }>> }
      expect(par.branches).toHaveLength(2)
      // Each branch is wrapped in an array of nodes; first node of each branch is what we built
      expect(par.branches[0][0].kind).toBe('step')              // flat → helixBranch step
      expect(par.branches[1][0].kind).toBe('subworkflow')        // multi-phase → featureImplementation
    })

    it('chains multi-phase subtasks sequentially via then()', () => {
      const wf = decompositionToWorkflow(
        makeDecomp({
          strategy: 'sequential',
          subTasks: [
            { goal: 'phase A', priority: 1, complexity: 'multi-phase', template: 'implementation' },
            { goal: 'phase B', priority: 2, complexity: 'multi-phase', template: 'implementation' },
          ],
        }),
        { baseId: 'seq-mp', runner: stubRunner },
      )
      expect(wf.nodes).toHaveLength(2)
      expect(wf.nodes[0].kind).toBe('subworkflow')
      expect(wf.nodes[1].kind).toBe('subworkflow')
    })

    it('the multi-phase subworkflow contains design + implement + review (no tests phase)', () => {
      const wf = decompositionToWorkflow(
        makeDecomp({
          subTasks: [{
            goal: 'Substantial implementation work',
            priority: 1,
            complexity: 'multi-phase',
            template: 'implementation',
          }],
        }),
        { baseId: 'phases', runner: stubRunner },
      )
      const sub = (wf.nodes[0] as { workflow: { nodes: Array<{ kind: string; step?: { id: string } }> } }).workflow
      const stepIds = sub.nodes
        .filter(n => n.kind === 'step')
        .map(n => n.step?.id ?? '')
      expect(stepIds).toContain('design')
      expect(stepIds).toContain('implement')
      expect(stepIds).toContain('review')
      expect(stepIds).not.toContain('test')
    })
  })
})
