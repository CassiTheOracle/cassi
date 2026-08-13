import { describe, expect, it, vi } from 'vitest'

import { DecompositionTracker, type TransitionHandler } from '../src/decomposition-tracker.js'

import type { GoalDecomposition } from '../src/corpus-types.js'
import type { ILogger } from '../src/vendor/types/interfaces.js'

function silentLogger(): ILogger {
  const make = () => () => undefined as unknown as void
  const l: ILogger = { debug: make(), info: make(), warn: make(), error: make(), child: () => l }
  return l
}

function makeDecomposition(taskCount: number = 1): GoalDecomposition {
  return {
    decomposed: true,
    originalGoal: 'test goal',
    subTasks: Array.from({ length: taskCount }, (_, i) => ({
      goal: `subtask-${i}`,
      priority: 1,
      relevantFiles: [`file-${i}.ts`],
    })),
    strategy: 'parallel',
    durationMs: 10,
  }
}

function newTracker(taskCount: number = 1): { tracker: DecompositionTracker; taskIds: string[] } {
  const tracker = new DecompositionTracker('c-test', makeDecomposition(taskCount), silentLogger())
  return { tracker, taskIds: tracker.getAllTaskIds() }
}

describe('DecompositionTracker — onTransition (PR-2 callback surface)', () => {
  it('fires on assignTask', () => {
    const { tracker, taskIds } = newTracker()
    const handler = vi.fn()
    tracker.onTransition(handler)
    tracker.assignTask(taskIds[0], 'helix-A')
    expect(handler).toHaveBeenCalledTimes(1)
    const event = handler.mock.calls[0][0]
    expect(event.from).toBe('planned')
    expect(event.to).toBe('assigned')
    expect(event.task.helixSessionId).toBe('helix-A')
  })

  it('fires on the full lifecycle (assign → start → complete)', () => {
    const { tracker, taskIds } = newTracker()
    const handler = vi.fn()
    tracker.onTransition(handler)
    tracker.assignTask(taskIds[0], 'helix-A')
    tracker.startTask(taskIds[0])
    tracker.completeTask(taskIds[0], 'shipped')
    expect(handler).toHaveBeenCalledTimes(3)
    expect(handler.mock.calls[0][0].to).toBe('assigned')
    expect(handler.mock.calls[1][0].to).toBe('in-progress')
    expect(handler.mock.calls[2][0].to).toBe('completed')
  })

  it('fires on failTask + cancelTask + splitTask', () => {
    const { tracker: t1, taskIds: ids1 } = newTracker()
    const failed = vi.fn()
    t1.onTransition(failed)
    t1.assignTask(ids1[0], 'helix-X')
    t1.startTask(ids1[0])
    t1.failTask(ids1[0], 'crash')
    expect(failed.mock.calls.some(c => c[0].to === 'failed')).toBe(true)

    const { tracker: t2, taskIds: ids2 } = newTracker()
    const cancelled = vi.fn()
    t2.onTransition(cancelled)
    t2.assignTask(ids2[0], 'helix-Y')
    t2.cancelTask(ids2[0])
    expect(cancelled.mock.calls.some(c => c[0].to === 'cancelled')).toBe(true)

    const { tracker: t3, taskIds: ids3 } = newTracker()
    const split = vi.fn()
    t3.onTransition(split)
    t3.splitTask(ids3[0], [{ goal: 'sub-a', priority: 1 }, { goal: 'sub-b', priority: 1 }])
    expect(split.mock.calls.some(c => c[0].to === 'split')).toBe(true)
  })

  it('fires a synthetic transition on recordDeviation with from === to', () => {
    const { tracker, taskIds } = newTracker()
    tracker.assignTask(taskIds[0], 'helix-A')
    tracker.startTask(taskIds[0])
    const handler = vi.fn()
    tracker.onTransition(handler)
    tracker.recordDeviation(taskIds[0], 'discovered the real fix is elsewhere')
    expect(handler).toHaveBeenCalledTimes(1)
    const event = handler.mock.calls[0][0]
    expect(event.from).toBe('in-progress')
    expect(event.to).toBe('in-progress')
    expect(event.reason).toContain('deviation:')
    expect(event.reason).toContain('discovered the real fix')
  })

  it('handler exceptions do not break tracker state', () => {
    const { tracker, taskIds } = newTracker()
    tracker.onTransition(() => { throw new Error('boom') })
    expect(() => tracker.assignTask(taskIds[0], 'helix-A')).not.toThrow()
    expect(tracker.getTask(taskIds[0])?.status).toBe('assigned')
    expect(() => tracker.startTask(taskIds[0])).not.toThrow()
    expect(tracker.getTask(taskIds[0])?.status).toBe('in-progress')
  })

  it('unsubscribe stops further events', () => {
    const { tracker, taskIds } = newTracker()
    const handler = vi.fn()
    const unsub = tracker.onTransition(handler)
    tracker.assignTask(taskIds[0], 'helix-A')
    expect(handler).toHaveBeenCalledTimes(1)
    unsub()
    tracker.startTask(taskIds[0])
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('most recent handler wins (single-subscriber semantics)', () => {
    const { tracker, taskIds } = newTracker()
    const first = vi.fn()
    const second = vi.fn()
    tracker.onTransition(first)
    tracker.onTransition(second)
    tracker.assignTask(taskIds[0], 'helix-A')
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledTimes(1)
  })

  it('handler sees post-transition task state', () => {
    const { tracker, taskIds } = newTracker()
    const handler: TransitionHandler = vi.fn()
    tracker.onTransition(handler)
    tracker.assignTask(taskIds[0], 'helix-Z')
    const event = (handler as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]
    expect(event.task.status).toBe('assigned')
    expect(event.task.helixSessionId).toBe('helix-Z')
  })
})
