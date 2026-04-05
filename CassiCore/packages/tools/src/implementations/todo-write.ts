/**
 * TodoWrite Tool — Persistent structured task tracking via Global Blackboard.
 *
 * Provides a per-session todo list that agents can use to track
 * multi-step work. Backed by the Global Blackboard system for
 * cross-session visibility — parent sessions (Constellation, Helix)
 * can read child session todos via the blackboard API.
 *
 * Features:
 * - Simple input: { todos: [...] } with content/status/priority
 * - Blackboard-backed: creates a `todos:{sessionId}` board
 * - Diff-based updates: computes changes between old and new states
 * - Activity log: posts change summaries to `findings` channel
 * - Verification nudge: posts to `concerns` when all done without verification
 * - Scratchpad: stores quick-access counts for parent session polling
 * - JSON file fallback: when blackboard is unavailable
 * - Event bus: emits `todo:updated` events
 *
 * Inspired by the Claude Code TodoWrite tool pattern,
 * upgraded to use CassiCore's Global Blackboard for cross-session sharing.
 */

import { join } from 'node:path'
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs'

import { bus } from '../../event-bus.js'
import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'
import type { GlobalBlackboardRegistry } from '../../intelligence/flux-team/global-blackboard-registry.js'
import type { Blackboard } from '../../intelligence/flux-team/blackboard.js'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface TodoItem {
  content: string
  status: 'pending' | 'in_progress' | 'completed'
  priority: 'high' | 'medium' | 'low'
}

interface TodoWriteInput {
  todos: TodoItem[]
}

interface TodoWriteOutput {
  oldTodos: TodoItem[]
  newTodos: TodoItem[]
  verificationNudgeNeeded: boolean
  blackboardBoard?: string
}

type PlanStepStatus = 'proposed' | 'approved' | 'in_progress' | 'completed' | 'rejected'

/* ------------------------------------------------------------------ */
/*  Status mapping                                                     */
/* ------------------------------------------------------------------ */

const TODO_TO_PLAN_STATUS: Record<string, PlanStepStatus> = {
  'pending': 'proposed',
  'in_progress': 'in_progress',
  'completed': 'completed',
}

const PLAN_TO_TODO_STATUS: Record<string, TodoItem['status']> = {
  'proposed': 'pending',
  'approved': 'pending',
  'in_progress': 'in_progress',
  'completed': 'completed',
  'rejected': 'completed',
}

/* ------------------------------------------------------------------ */
/*  Definition                                                         */
/* ------------------------------------------------------------------ */

export const todoWriteDefinition: ToolDefinition = {
  name: 'todo_write',
  description:
    'Update the structured task list for the current session. ' +
    'Use this to track multi-step work, plan complex tasks, and give ' +
    'visibility into progress. Each todo has content, status (pending | ' +
    'in_progress | completed), and priority (high | medium | low). ' +
    'Send the FULL todo list on every call (not just changes). ' +
    'Todos are shared via the global blackboard — parent sessions can ' +
    'monitor child task progress.',
  parameters: {
    type: 'object',
    properties: {
      todos: {
        type: 'array',
        description: 'The complete updated todo list',
        items: {
          type: 'object',
          properties: {
            content: { type: 'string', description: 'Brief description of the task' },
            status: { type: 'string', enum: ['pending', 'in_progress', 'completed'], description: 'Current status of the task' },
            priority: { type: 'string', enum: ['high', 'medium', 'low'], description: 'Priority level of the task' },
          },
          required: ['content', 'status', 'priority'],
        },
      },
    },
    required: ['todos'],
  },
  category: 'core',
  readOnly: false,
  requiredPermission: 'workspace-write',
}

/* ------------------------------------------------------------------ */
/*  Handler                                                            */
/* ------------------------------------------------------------------ */

export const todoWriteHandler: ToolHandler = async (
  input: Record<string, unknown>,
  context: ToolExecutionContext,
): Promise<string> => {
  const parsed = input as unknown as TodoWriteInput

  // Validate input
  if (!Array.isArray(parsed.todos)) {
    return JSON.stringify({ error: 'todos must be an array' })
  }
  if (parsed.todos.length === 0) {
    return JSON.stringify({ error: 'todos must not be empty' })
  }

  // Validate each todo
  for (const todo of parsed.todos) {
    if (!todo.content || typeof todo.content !== 'string' || !todo.content.trim()) {
      return JSON.stringify({ error: 'each todo must have non-empty content' })
    }
    if (!['pending', 'in_progress', 'completed'].includes(todo.status)) {
      return JSON.stringify({
        error: `invalid status "${todo.status}" — must be pending, in_progress, or completed`,
      })
    }
    if (!['high', 'medium', 'low'].includes(todo.priority ?? 'medium')) {
      return JSON.stringify({
        error: `invalid priority "${todo.priority}" — must be high, medium, or low`,
      })
    }
    // Default priority if not provided
    if (!todo.priority) todo.priority = 'medium'
  }

  const sessionId = context.sessionId || 'default'
  const boardName = `todos:${sessionId}`

  // Load existing state
  const oldTodos = loadOldTodos(context, boardName)

  // Compute diff
  const diff = computeDiff(oldTodos, parsed.todos)

  // Check verification nudge
  const allDone = parsed.todos.every(t => t.status === 'completed')
  const hasVerification = parsed.todos.some(t =>
    t.content.toLowerCase().includes('verif') ||
    t.content.toLowerCase().includes('test') ||
    t.content.toLowerCase().includes('build') ||
    t.content.toLowerCase().includes('check'),
  )
  const verificationNudgeNeeded = allDone && parsed.todos.length >= 3 && !hasVerification

  // Write to blackboard (primary) or fallback to JSON file
  const bbRegistry = context._globalBlackboardRegistry
  let blackboardWritten = false

  if (bbRegistry) {
    try {
      blackboardWritten = writeToBlackboard(
        bbRegistry, boardName, sessionId,
        parsed.todos, diff, verificationNudgeNeeded,
      )
    } catch {
      // Fall through to file fallback
    }
  }

  if (!blackboardWritten) {
    // File-based fallback
    const storePath = resolveStorePath(context)
    const persisted = allDone ? [] : parsed.todos
    saveTodos(storePath, persisted)
  }

  // Emit event for observability
  try {
    const pending = parsed.todos.filter(t => t.status === 'pending').length
    const inProgress = parsed.todos.filter(t => t.status === 'in_progress').length
    const completed = parsed.todos.filter(t => t.status === 'completed').length
    bus.emit({
      type: 'todo:updated' as any,
      sessionId,
      total: parsed.todos.length,
      pending,
      inProgress,
      completed,
      allDone,
      verificationNudgeNeeded,
      blackboardBoard: blackboardWritten ? boardName : undefined,
      timestamp: new Date(),
    })
  } catch { /* non-fatal */ }

  // Build output
  const output: TodoWriteOutput = {
    oldTodos,
    newTodos: parsed.todos,
    verificationNudgeNeeded,
    blackboardBoard: blackboardWritten ? boardName : undefined,
  }

  let result = JSON.stringify(output, null, 2)

  if (diff.summary) {
    result += `\n\n${diff.summary}`
  }

  if (verificationNudgeNeeded) {
    result += '\n\n[Note: All tasks are marked complete but none mention verification. ' +
      'Consider adding a verification step to confirm the changes work correctly.]'
  }

  return result
}

/* ------------------------------------------------------------------ */
/*  Blackboard integration                                             */
/* ------------------------------------------------------------------ */

function writeToBlackboard(
  registry: GlobalBlackboardRegistry,
  boardName: string,
  sessionId: string,
  todos: TodoItem[],
  diff: TodoDiff,
  verificationNudge: boolean,
): boolean {
  const board = registry.getOrCreate(boardName, {
    persist: true,
  })

  // Initialize plan if needed
  if (!board.getPlan()) {
    board.initPlan(`Tasks for session ${sessionId}`)
  }

  // Sync plan steps with current todo list.
  // Strategy: clear existing steps and recreate from current state.
  // This is simpler and safer than trying to match/merge individual steps.
  const existingPlan = board.getPlan()
  if (existingPlan) {
    // Mark all existing steps as rejected (cleared)
    for (const step of existingPlan.steps) {
      if (step.status !== 'completed' && step.status !== 'rejected') {
        board.updatePlanStep(step.id, { status: 'rejected' as any, rejectionReason: 'Plan replaced by new todo_write call' })
      }
    }
  }

  // Create fresh steps from current todos
  for (let i = 0; i < todos.length; i++) {
    const todo = todos[i]
    const step = board.submitPlanStep({
      title: todo.content,
      description: `Priority: ${todo.priority}`,
      order: i + 1,
      priority: todo.priority,
      tags: [todo.priority, todo.status],
      author: `todo_write:${sessionId}`,
      dependencies: [],
    })

    // Update status to match todo
    const targetStatus = TODO_TO_PLAN_STATUS[todo.status]
    if (targetStatus && targetStatus !== 'proposed') {
      board.updatePlanStep(step.id, { status: targetStatus as any })
    }
  }

  // Post activity summary to findings channel
  if (diff.summary) {
    board.post('findings', {
      author: `todo_write:${sessionId}`,
      content: diff.summary,
      priority: 0,
      tags: ['todo-update'],
    })
  }

  // Post verification nudge to concerns channel
  if (verificationNudge) {
    board.post('concerns', {
      author: `todo_write:${sessionId}`,
      content: 'All tasks are marked complete but none mention verification, testing, or build checks. Consider adding a verification step.',
      priority: 2,
      tags: ['verification-nudge'],
    })
  }

  // Update scratchpad with quick-access counts
  const pending = todos.filter(t => t.status === 'pending').length
  const inProgress = todos.filter(t => t.status === 'in_progress').length
  const completed = todos.filter(t => t.status === 'completed').length

  board.setScratchpad('todo:total', String(todos.length), `todo_write:${sessionId}`)
  board.setScratchpad('todo:pending', String(pending), `todo_write:${sessionId}`)
  board.setScratchpad('todo:in_progress', String(inProgress), `todo_write:${sessionId}`)
  board.setScratchpad('todo:completed', String(completed), `todo_write:${sessionId}`)
  board.setScratchpad('todo:all_done', String(todos.every(t => t.status === 'completed')), `todo_write:${sessionId}`)

  return true
}

function loadOldTodos(context: ToolExecutionContext, boardName: string): TodoItem[] {
  // Try blackboard first
  const bbRegistry = context._globalBlackboardRegistry
  if (bbRegistry) {
    try {
      const board = bbRegistry.get(boardName)
      if (board) {
        return loadTodosFromBlackboard(board)
      }
    } catch { /* fall through */ }
  }

  // File fallback
  const storePath = resolveStorePath(context)
  return loadTodosFromFile(storePath)
}

function loadTodosFromBlackboard(board: Blackboard): TodoItem[] {
  const plan = board.getPlan()
  if (!plan) return []

  return plan.steps
    .filter(s => s.status !== 'rejected')
    .sort((a, b) => a.order - b.order)
    .map(step => ({
      content: step.title,
      status: PLAN_TO_TODO_STATUS[step.status] ?? 'pending',
      priority: (step.priority as TodoItem['priority']) ?? 'medium',
    }))
}
/* ------------------------------------------------------------------ */
/*  Diff computation                                                   */
/* ------------------------------------------------------------------ */

interface TodoDiff {
  added: TodoItem[]
  removed: TodoItem[]
  statusChanged: Array<{ content: string; from: string; to: string }>
  summary: string
}

function computeDiff(oldTodos: TodoItem[], newTodos: TodoItem[]): TodoDiff {
  const oldMap = new Map(oldTodos.map(t => [t.content, t]))
  const newMap = new Map(newTodos.map(t => [t.content, t]))

  const added: TodoItem[] = []
  const removed: TodoItem[] = []
  const statusChanged: Array<{ content: string; from: string; to: string }> = []

  // New items not in old
  for (const t of newTodos) {
    if (!oldMap.has(t.content)) {
      added.push(t)
    }
  }

  // Old items not in new
  for (const t of oldTodos) {
    if (!newMap.has(t.content)) {
      removed.push(t)
    }
  }

  // Status changes
  for (const t of newTodos) {
    const old = oldMap.get(t.content)
    if (old && old.status !== t.status) {
      statusChanged.push({ content: t.content, from: old.status, to: t.status })
    }
  }

  // Build summary
  const parts: string[] = []
  if (added.length > 0) parts.push(`${added.length} added`)
  if (removed.length > 0) parts.push(`${removed.length} removed`)
  if (statusChanged.length > 0) {
    const completedCount = statusChanged.filter(c => c.to === 'completed').length
    const startedCount = statusChanged.filter(c => c.to === 'in_progress').length
    if (completedCount > 0) parts.push(`${completedCount} completed`)
    if (startedCount > 0) parts.push(`${startedCount} started`)
  }

  const summary = parts.length > 0
    ? `[Todo update: ${parts.join(', ')} — ${newTodos.length} total]`
    : ''

  return { added, removed, statusChanged, summary }
}

/* ------------------------------------------------------------------ */
/*  File-based fallback persistence                                    */
/* ------------------------------------------------------------------ */

function resolveStorePath(context: ToolExecutionContext): string {
  const dir = join(context.workingDir, '.cassicore')
  if (!existsSync(dir)) {
    try { mkdirSync(dir, { recursive: true }) } catch { /* ignore */ }
  }
  return join(dir, `todos-${context.sessionId || 'default'}.json`)
}

function loadTodosFromFile(path: string): TodoItem[] {
  try {
    if (!existsSync(path)) return []
    const raw = readFileSync(path, 'utf-8')
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveTodos(path: string, todos: TodoItem[]): void {
  try {
    writeFileSync(path, JSON.stringify(todos, null, 2), 'utf-8')
  } catch {
    // Silent fail — todo persistence is best-effort
  }
}
