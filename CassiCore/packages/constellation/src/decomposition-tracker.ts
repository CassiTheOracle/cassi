/**
 * Decomposition Tracker — Task Lifecycle Management via Blackboard Pattern
 *
 * Tracks planned tasks from decomposition through execution, recording status,
 * timing, deviations, and outcomes. This gives the Corpus visibility into how
 * well decomposition matches reality.
 *
 * The tracker maintains a Map of TrackedTask entries, each representing a
 * sub-task from the original goal decomposition. As Helix sessions are assigned
 * and execute, their progress is recorded here for cross-branch analysis.
 */

import { randomBytes } from 'crypto'
import type { ILogger } from './vendor/types/interfaces.js'
import type { GoalDecomposition, GoalSubTask } from './corpus-types.js'
import { DEVIATION_REASON_PHRASES } from './vendor/phrase-prototypes.js'
import type { MnemicField } from '@cassicore/mnemic-field'

export type TaskStatus = 'planned' | 'assigned' | 'in-progress' | 'completed' | 'failed' | 'cancelled' | 'split'

export interface TrackedTask {
  id: string
  originalTask: GoalSubTask
  status: TaskStatus
  helixSessionId?: string
  startedAt?: number
  completedAt?: number
  /** Actual goal if it deviated from planned */
  actualGoal?: string
  deviationReason?: string
  deviationConfidence?: number
  /** Sub-tasks spawned from this task (for incremental re-decomposition) */
  childTaskIds?: string[]
  /** Parent task ID if this was spawned by re-decomposition */
  parentTaskId?: string
  /** Steps consumed by the assigned Helix */
  stepsConsumed?: number
  /** Outcome notes */
  outcome?: string
}

export interface DecompositionSnapshot {
  constellationId: string
  originalGoal: string
  strategy: 'sequential' | 'parallel' | 'tree'
  tasks: TrackedTask[]
  decompositionDurationMs: number
  /** Accuracy: how many tasks completed as planned vs deviated/split */
  accuracy: number
  createdAt: number
  lastUpdatedAt: number
}

interface TaskTransition {
  from: TaskStatus
  to: TaskStatus
  timestamp: number
  reason?: string
}

/**
 * Transition handler — invoked synchronously after each tracker mutation.
 * The handler sees the post-transition view of the task. Single-subscriber by
 * design (matches today's actual use); convert to Set<Handler> if a second
 * consumer ever needs in. Mirrors GlobalWorkspace.onBroadcast pattern.
 */
export type TransitionHandler = (event: {
  taskId: string
  task: TrackedTask
  from: TaskStatus
  to: TaskStatus
  reason?: string
}) => void

/**
 * Generates a short hash for task IDs
 */
function generateShortHash(): string {
  return randomBytes(4).toString('hex').slice(0, 8)
}

/**
 * DecompositionTracker — manages task lifecycle from planning through completion
 *
 * WHY: The Corpus needs visibility into whether decomposed tasks execute as planned.
 * This tracker records deviations, splits, and outcomes to improve future decomposition strategies.
 */
export class DecompositionTracker {
  private readonly tasks: Map<string, TrackedTask> = new Map()
  private readonly taskIndexByHelix: Map<string, string> = new Map()
  private readonly transitions: Map<string, TaskTransition[]> = new Map()
  private readonly createdAt: number
  private lastUpdatedAt: number
  private transitionHandler?: TransitionHandler
  private mnemicField?: MnemicField

  constructor(
    private readonly constellationId: string,
    private readonly decomposition: GoalDecomposition,
    private readonly log: ILogger,
  ) {
    this.createdAt = Date.now()
    this.lastUpdatedAt = this.createdAt
    this.initializeFromDecomposition()
  }

  setMnemicField(field: MnemicField): void {
    this.mnemicField = field
  }

  /**
   * Initialize tracked tasks from decomposition result
   * Creates a TrackedTask entry for each sub-task in 'planned' status
   */
  private initializeFromDecomposition(): void {
    const { subTasks } = this.decomposition
    
    subTasks.forEach((task, index) => {
      const taskId = `task-${index}-${generateShortHash()}`
      const trackedTask: TrackedTask = {
        id: taskId,
        originalTask: task,
        status: 'planned',
      }
      
      this.tasks.set(taskId, trackedTask)
      this.transitions.set(taskId, [])
      
      this.log.debug('[DecompositionTracker] Task initialized', {
        taskId,
        goal: task.goal,
        priority: task.priority,
      })
    })
    
    this.log.info('[DecompositionTracker] Initialized from decomposition', {
      constellationId: this.constellationId,
      taskCount: subTasks.length,
      strategy: this.decomposition.strategy,
    })
  }

  /**
   * Record a status transition for a task
   */
  private recordTransition(taskId: string, from: TaskStatus, to: TaskStatus, reason?: string): void {
    const transitions = this.transitions.get(taskId) || []
    transitions.push({
      from,
      to,
      timestamp: Date.now(),
      reason,
    })
    this.transitions.set(taskId, transitions)
    this.lastUpdatedAt = Date.now()
    this.emitTransition(taskId, from, to, reason)
  }

  /**
   * Subscribe to task lifecycle transitions. Single-subscriber — the most
   * recent handler wins. Returns an unsubscribe function. Handlers are invoked
   * synchronously after each transition is recorded; misbehaving handlers are
   * caught so they cannot break tracker state.
   */
  onTransition(handler: TransitionHandler): () => void {
    this.transitionHandler = handler
    return () => {
      if (this.transitionHandler === handler) this.transitionHandler = undefined
    }
  }

  private emitTransition(taskId: string, from: TaskStatus, to: TaskStatus, reason?: string): void {
    const handler = this.transitionHandler
    if (!handler) return
    const task = this.tasks.get(taskId)
    if (!task) return
    try {
      handler({ taskId, task, from, to, reason })
    } catch (err) {
      this.log.warn('[DecompositionTracker] Transition handler threw', {
        taskId,
        from,
        to,
        error: String(err),
      })
    }
  }

  /**
   * Assign a task to a Helix session
   * Transitions task from 'planned' to 'assigned'
   */
  assignTask(taskId: string, helixSessionId: string): void {
    const task = this.tasks.get(taskId)
    if (!task) {
      this.log.warn('[DecompositionTracker] Attempted to assign unknown task', { taskId })
      return
    }
    
    if (task.status !== 'planned') {
      this.log.warn('[DecompositionTracker] Cannot assign task in non-planned state', {
        taskId,
        currentStatus: task.status,
      })
      return
    }
    
    const previousStatus = task.status
    task.status = 'assigned'
    task.helixSessionId = helixSessionId
    
    this.taskIndexByHelix.set(helixSessionId, taskId)
    this.recordTransition(taskId, previousStatus, 'assigned', `Assigned to Helix ${helixSessionId}`)
    
    this.log.info('[DecompositionTracker] Task assigned', {
      taskId,
      helixSessionId,
      goal: task.originalTask.goal,
    })
  }

  /**
   * Mark a task as started
   * Transitions task from 'assigned' to 'in-progress'
   */
  startTask(taskId: string): void {
    const task = this.tasks.get(taskId)
    if (!task) {
      this.log.warn('[DecompositionTracker] Attempted to start unknown task', { taskId })
      return
    }
    
    if (task.status !== 'assigned') {
      this.log.warn('[DecompositionTracker] Cannot start task in non-assigned state', {
        taskId,
        currentStatus: task.status,
      })
      return
    }
    
    const previousStatus = task.status
    task.status = 'in-progress'
    task.startedAt = Date.now()
    
    this.recordTransition(taskId, previousStatus, 'in-progress')
    
    this.log.info('[DecompositionTracker] Task started', {
      taskId,
      helixSessionId: task.helixSessionId,
    })
  }

  /**
   * Mark a task as completed
   * Transitions task from 'in-progress' to 'completed'
   */
  completeTask(taskId: string, outcome?: string): void {
    const task = this.tasks.get(taskId)
    if (!task) {
      this.log.warn('[DecompositionTracker] Attempted to complete unknown task', { taskId })
      return
    }
    
    if (task.status !== 'in-progress') {
      this.log.warn('[DecompositionTracker] Cannot complete task in non-progress state', {
        taskId,
        currentStatus: task.status,
      })
      return
    }
    
    const previousStatus = task.status
    task.status = 'completed'
    task.completedAt = Date.now()
    task.outcome = outcome

    if (outcome && this.mnemicField && task.actualGoal) {
      const combined = `Original: ${task.originalTask.goal}\nActual: ${outcome}`
      this.mnemicField.classifyPhrase(combined, DEVIATION_REASON_PHRASES).then(result => {
        if (result?.label) {
          task.deviationReason = result.label
          task.deviationConfidence = result.score
        }
      }).catch(() => {})
    }

    this.recordTransition(taskId, previousStatus, 'completed', outcome)
    
    this.log.info('[DecompositionTracker] Task completed', {
      taskId,
      helixSessionId: task.helixSessionId,
      durationMs: task.completedAt - (task.startedAt || task.completedAt),
      hasOutcome: !!outcome,
    })
  }

  /**
   * Mark a task as failed
   * Transitions task from 'in-progress' (or 'assigned') to 'failed'
   */
  failTask(taskId: string, reason: string): void {
    const task = this.tasks.get(taskId)
    if (!task) {
      this.log.warn('[DecompositionTracker] Attempted to fail unknown task', { taskId })
      return
    }
    
    if (task.status !== 'in-progress' && task.status !== 'assigned') {
      this.log.warn('[DecompositionTracker] Cannot fail task in invalid state', {
        taskId,
        currentStatus: task.status,
      })
      return
    }
    
    const previousStatus = task.status
    task.status = 'failed'
    task.completedAt = Date.now()
    task.outcome = reason
    
    this.recordTransition(taskId, previousStatus, 'failed', reason)
    
    this.log.error('[DecompositionTracker] Task failed', {
      taskId,
      helixSessionId: task.helixSessionId,
      reason,
    })
  }

  /**
   * Mark a task as cancelled
   * Transitions task to 'cancelled' from any active state
   */
  cancelTask(taskId: string): void {
    const task = this.tasks.get(taskId)
    if (!task) {
      this.log.warn('[DecompositionTracker] Attempted to cancel unknown task', { taskId })
      return
    }
    
    if (['completed', 'failed', 'cancelled'].includes(task.status)) {
      this.log.warn('[DecompositionTracker] Cannot cancel task in terminal state', {
        taskId,
        currentStatus: task.status,
      })
      return
    }
    
    const previousStatus = task.status
    task.status = 'cancelled'
    task.completedAt = Date.now()
    
    this.recordTransition(taskId, previousStatus, 'cancelled')
    
    this.log.info('[DecompositionTracker] Task cancelled', {
      taskId,
      previousStatus,
    })
  }

  /**
   * Split a task into multiple sub-tasks (re-decomposition)
   * Marks original task as 'split' and creates new child tasks
   * 
   * @returns Array of new task IDs
   */
  splitTask(taskId: string, newSubTasks: GoalSubTask[]): string[] {
    const task = this.tasks.get(taskId)
    if (!task) {
      this.log.warn('[DecompositionTracker] Attempted to split unknown task', { taskId })
      return []
    }
    
    if (['completed', 'failed', 'cancelled', 'split'].includes(task.status)) {
      this.log.warn('[DecompositionTracker] Cannot split task in terminal/split state', {
        taskId,
        currentStatus: task.status,
      })
      return []
    }
    
    // HOW: Record the split and create child tasks
    const previousStatus = task.status
    task.status = 'split'
    task.childTaskIds = []
    task.completedAt = Date.now()
    
    this.recordTransition(taskId, previousStatus, 'split', `Split into ${newSubTasks.length} sub-tasks`)
    
    const newTaskIds: string[] = []
    const baseIndex = this.tasks.size
    
    newSubTasks.forEach((subTask, index) => {
      const newTaskId = `task-${baseIndex + index}-${generateShortHash()}`
      const newTask: TrackedTask = {
        id: newTaskId,
        originalTask: subTask,
        status: 'planned',
        parentTaskId: taskId,
      }
      
      this.tasks.set(newTaskId, newTask)
      this.transitions.set(newTaskId, [])
      task.childTaskIds!.push(newTaskId)
      newTaskIds.push(newTaskId)
      
      this.log.debug('[DecompositionTracker] Child task created from split', {
        newTaskId,
        parentTaskId: taskId,
        goal: subTask.goal,
      })
    })
    
    this.log.info('[DecompositionTracker] Task split', {
      taskId,
      childCount: newTaskIds.length,
      childTaskIds: newTaskIds,
    })
    
    return newTaskIds
  }

  /**
   * Add a new task (for Corpus-driven incremental additions)
   * 
   * @returns The new task ID
   */
  addTask(task: GoalSubTask, parentTaskId?: string): string {
    const taskId = `task-${this.tasks.size}-${generateShortHash()}`
    const trackedTask: TrackedTask = {
      id: taskId,
      originalTask: task,
      status: 'planned',
      parentTaskId,
    }
    
    this.tasks.set(taskId, trackedTask)
    this.transitions.set(taskId, [])
    
    // If this has a parent, link it
    if (parentTaskId) {
      const parent = this.tasks.get(parentTaskId)
      if (parent) {
        if (!parent.childTaskIds) {
          parent.childTaskIds = []
        }
        parent.childTaskIds.push(taskId)
      }
    }
    
    this.log.debug('[DecompositionTracker] Task added', {
      taskId,
      parentTaskId,
      goal: task.goal,
    })
    
    return taskId
  }

  /**
   * Get a task by its ID
   */
  getTask(taskId: string): TrackedTask | undefined {
    return this.tasks.get(taskId)
  }

  /**
   * Get a task by its assigned Helix session ID
   */
  getTaskByHelixId(helixSessionId: string): TrackedTask | undefined {
    const taskId = this.taskIndexByHelix.get(helixSessionId)
    return taskId ? this.tasks.get(taskId) : undefined
  }

  /**
   * Get all tasks that are not yet completed/failed/cancelled
   */
  getPendingTasks(): TrackedTask[] {
    return Array.from(this.tasks.values()).filter(
      task => !['completed', 'failed', 'cancelled'].includes(task.status)
    )
  }

  /**
   * Get all tasks currently in progress
   */
  getActiveTasks(): TrackedTask[] {
    return Array.from(this.tasks.values()).filter(
      task => task.status === 'in-progress'
    )
  }

  /**
   * Get a complete snapshot of the decomposition state
   */
  getSnapshot(): DecompositionSnapshot {
    const tasks = Array.from(this.tasks.values())
    const accuracy = this.calculateAccuracy()
    
    return {
      constellationId: this.constellationId,
      originalGoal: this.decomposition.originalGoal,
      strategy: this.decomposition.strategy,
      tasks,
      decompositionDurationMs: this.decomposition.durationMs,
      accuracy,
      createdAt: this.createdAt,
      lastUpdatedAt: this.lastUpdatedAt,
    }
  }

  /**
   * Calculate accuracy: ratio of tasks completed as originally planned
   * 
   * HOW: A task is "as-planned" if it completed without being split
   * and without deviating from its original goal.
   */
  getAccuracy(): number {
    return this.calculateAccuracy()
  }

  private calculateAccuracy(): number {
    const completedTasks = Array.from(this.tasks.values()).filter(
      task => task.status === 'completed' || task.status === 'failed'
    )
    
    if (completedTasks.length === 0) {
      return 1.0 // No completed tasks yet, assume perfect accuracy
    }
    
    const asPlanned = completedTasks.filter(task => {
      // Task must be completed (not failed)
      if (task.status !== 'completed') {
        return false
      }
      
      // Task must not have been split (check via childTaskIds presence)
      if (task.childTaskIds && task.childTaskIds.length > 0) {
        return false
      }
      
      // Task must not have deviated from original goal
      if (task.actualGoal && task.actualGoal !== task.originalTask.goal) {
        return false
      }
      
      return true
    }).length
    
    return asPlanned / completedTasks.length
  }

  /**
   * Get all tasks where the actual goal differs from planned
   */
  getDeviations(): Array<{ taskId: string; planned: string; actual: string }> {
    const deviations: Array<{ taskId: string; planned: string; actual: string }> = []
    
    for (const task of this.tasks.values()) {
      if (task.actualGoal && task.actualGoal !== task.originalTask.goal) {
        deviations.push({
          taskId: task.id,
          planned: task.originalTask.goal,
          actual: task.actualGoal,
        })
      }
    }
    
    return deviations
  }

  /**
   * Update the step count consumed by a task's Helix
   */
  updateSteps(taskId: string, steps: number): void {
    const task = this.tasks.get(taskId)
    if (!task) {
      this.log.warn('[DecompositionTracker] Attempted to update steps for unknown task', { taskId })
      return
    }
    
    task.stepsConsumed = steps
    
    this.log.debug('[DecompositionTracker] Steps updated', {
      taskId,
      steps,
    })
  }

  /**
   * Record a goal deviation for a task
   * Called when the actual goal differs from the planned goal
   */
  recordDeviation(taskId: string, actualGoal: string): void {
    const task = this.tasks.get(taskId)
    if (!task) {
      this.log.warn('[DecompositionTracker] Attempted to record deviation for unknown task', { taskId })
      return
    }

    task.actualGoal = actualGoal

    this.log.info('[DecompositionTracker] Goal deviation recorded', {
      taskId,
      planned: task.originalTask.goal,
      actual: actualGoal,
    })
    this.emitTransition(taskId, task.status, task.status, `deviation: ${actualGoal}`)
  }

  /**
   * Get transition history for a task
   */
  getTransitions(taskId: string): TaskTransition[] {
    return this.transitions.get(taskId) || []
  }

  /**
   * Get all task IDs
   */
  getAllTaskIds(): string[] {
    return Array.from(this.tasks.keys())
  }

  /**
   * Get task count by status
   */
  getStatusCounts(): Record<TaskStatus, number> {
    const counts: Record<TaskStatus, number> = {
      planned: 0,
      assigned: 0,
      'in-progress': 0,
      completed: 0,
      failed: 0,
      cancelled: 0,
      split: 0,
    }
    
    for (const task of this.tasks.values()) {
      counts[task.status]++
    }
    
    return counts
  }
}
