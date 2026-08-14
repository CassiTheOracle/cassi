/**
 * TodoWrite Tool — Brain-native structured task tracking.
 *
 * Tasks live as executive cortex signals in working memory.
 * State transitions produce cortical signals that the thalamus
 * uses for context scoring, and the affect register absorbs
 * for emotional state tracking. Completed sessions persist
 * to episodic memory.
 *
 * Replaces the blackboard-backed implementation with direct
 * brain integration:
 * - Cortex executive signals for active tasks (working memory)
 * - Cortex motor signals for completed tasks (action log)
 * - Cortex limbic signals for blocking/all-fail states
 * - Memory persistence on session completion
 * - Thalamus picks up task terms via buildBrainContext()
 */

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'
import type { CorticalField } from '../../intelligence/cortex/index.js'

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

interface TodoDiff {
  added: TodoItem[]
  completed: TodoItem[]
  changed: TodoItem[]
  removed: TodoItem[]
  summary: string
}

/* ------------------------------------------------------------------ */
/*  In-memory state per session                                        */
/* ------------------------------------------------------------------ */

const sessionTodos = new Map<string, TodoItem[]>()

/* ------------------------------------------------------------------ */
/*  Priority → salience mapping                                        */
/* ------------------------------------------------------------------ */

const PRIORITY_SALIENCE: Record<string, number> = {
  high: 0.9,
  medium: 0.6,
  low: 0.4,
}

/* ------------------------------------------------------------------ */
/*  Tool definition                                                    */
/* ------------------------------------------------------------------ */

export const todoWriteDefinition: ToolDefinition = {
  name: 'todo_write',
  description: 'Update the structured task list. Send the FULL todo list on every call.',
  category: 'core',
  parameters: {
    type: 'object',
    properties: {
      todos: {
        type: 'array',
        description: 'The complete updated todo list.',
        items: {
          type: 'object',
          properties: {
            content: { type: 'string', description: 'Brief description of the task' },
            status: { type: 'string', description: 'pending | in_progress | completed', enum: ['pending', 'in_progress', 'completed'] },
            priority: { type: 'string', description: 'high | medium | low', enum: ['high', 'medium', 'low'] },
          },
          required: ['content', 'status', 'priority'],
        },
      },
    },
    required: ['todos'],
  },
}

/* ------------------------------------------------------------------ */
/*  Tool handler                                                       */
/* ------------------------------------------------------------------ */

export const todoWriteHandler: ToolHandler = async (
  input: Record<string, unknown>,
  context: ToolExecutionContext,
): Promise<string> => {
  const parsed: TodoWriteInput = input as any

  // Validate
  if (!Array.isArray(parsed.todos)) {
    return JSON.stringify({ error: 'todos must be an array' })
  }
  for (const todo of parsed.todos) {
    if (!todo.content?.trim()) {
      return JSON.stringify({ error: 'each todo must have non-empty content' })
    }
    if (!['pending', 'in_progress', 'completed'].includes(todo.status)) {
      return JSON.stringify({ error: `invalid status "${todo.status}"` })
    }
    todo.priority ??= 'medium' as any
  }

  const sessionId = context.sessionId || 'default'
  const oldTodos = sessionTodos.get(sessionId) ?? []
  const newTodos = parsed.todos

  // Compute diff
  const diff = computeDiff(oldTodos, newTodos)

  // Store new state
  sessionTodos.set(sessionId, newTodos)

  const cortex = context._cortex as CorticalField | undefined
  if (cortex) {
    postCortexSignals(cortex, sessionId, diff, newTodos)
  }

  if (newTodos.length > 0 && newTodos.every(t => t.status === 'completed')) {
    persistToMemory(context, newTodos, sessionId)
  }

  // Build output
  const summary = diff.summary || `[Todo update: ${diff.added.length} added — ${newTodos.length} total]`

  return JSON.stringify({
    oldTodos,
    newTodos,
    diff: {
      added: diff.added.length,
      completed: diff.completed.length,
      changed: diff.changed.length,
      removed: diff.removed.length,
    },
  }) + '\n\n' + summary
}

/* ------------------------------------------------------------------ */
/*  Diff computation                                                   */
/* ------------------------------------------------------------------ */

function computeDiff(oldTodos: TodoItem[], newTodos: TodoItem[]): TodoDiff {
  const oldByContent = new Map(oldTodos.map(t => [t.content, t]))

  const added: TodoItem[] = []
  const completed: TodoItem[] = []
  const changed: TodoItem[] = []

  for (const todo of newTodos) {
    const old = oldByContent.get(todo.content)
    if (!old) {
      added.push(todo)
    } else if (old.status !== todo.status) {
      if (todo.status === 'completed') {
        completed.push(todo)
      } else {
        changed.push(todo)
      }
      oldByContent.delete(todo.content)
    } else {
      oldByContent.delete(todo.content)
    }
  }

  const newContentSet = new Set(newTodos.map(t => t.content))
  const removed = oldTodos.filter(t => !newContentSet.has(t.content))

  const parts: string[] = []
  if (added.length) parts.push(`${added.length} added`)
  if (completed.length) parts.push(`${completed.length} completed`)
  if (changed.length) parts.push(`${changed.length} changed`)
  if (removed.length) parts.push(`${removed.length} removed`)

  return {
    added, completed, changed, removed,
    summary: parts.length > 0
      ? `[Todo update: ${parts.join(', ')} — ${newTodos.length} total]`
      : `[Todo update: no changes — ${newTodos.length} total]`,
  }
}

/* ------------------------------------------------------------------ */
/*  Cortex signal integration                                          */
/* ------------------------------------------------------------------ */

function postCortexSignals(
  cortex: CorticalField,
  sessionId: string,
  diff: TodoDiff,
  allTodos: TodoItem[],
): void {
  try {
    // New tasks → executive decision signals
    for (const todo of diff.added) {
      cortex.signal('executive', {
        type: 'decision',
        content: `[task:new] ${todo.content}`,
        author: 'todo',
        sessionId,
        salience: PRIORITY_SALIENCE[todo.priority] ?? 0.6,
        confidence: 0.9,
        valence: 0.1,
        tags: ['task', 'new', todo.priority],
      })
    }

    // Completed tasks → motor action signals with positive valence
    for (const todo of diff.completed) {
      cortex.signal('motor', {
        type: 'action',
        content: `[task:done] ${todo.content}`,
        author: 'todo',
        sessionId,
        salience: 0.5,
        confidence: 1.0,
        valence: 0.4,
        tags: ['task', 'completed'],
      })
    }

    // Status changes → executive action signals
    for (const todo of diff.changed) {
      if (todo.status === 'in_progress') {
        cortex.signal('executive', {
          type: 'action',
          content: `[task:active] ${todo.content}`,
          author: 'todo',
          sessionId,
          salience: 0.8,
          confidence: 0.9,
          valence: 0.2,
          tags: ['task', 'in_progress', todo.priority],
        })
      }
    }

    // All tasks complete → session completion insight
    if (allTodos.length > 0 && allTodos.every(t => t.status === 'completed')) {
      cortex.signal('executive', {
        type: 'insight',
        content: `[task:session-complete] All ${allTodos.length} tasks completed`,
        author: 'todo',
        sessionId,
        salience: 0.7,
        confidence: 1.0,
        valence: 0.6,
        tags: ['task', 'session-complete'],
      })
    }

    // Many pending with no in_progress → potential blocking concern
    const pending = allTodos.filter(t => t.status === 'pending')
    const inProgress = allTodos.filter(t => t.status === 'in_progress')
    if (pending.length >= 3 && inProgress.length === 0 && diff.completed.length === 0) {
      cortex.signal('limbic', {
        type: 'concern',
        content: `[task:stalled] ${pending.length} tasks pending, none in progress`,
        author: 'todo',
        sessionId,
        salience: 0.7,
        confidence: 0.6,
        valence: -0.3,
        tags: ['task', 'stalled'],
      })
    }
  } catch {
    // Cortex signals are best-effort — never fail the tool
  }
}

/* ------------------------------------------------------------------ */
/*  Memory persistence                                                 */
/* ------------------------------------------------------------------ */

function persistToMemory(
  context: ToolExecutionContext,
  todos: TodoItem[],
  sessionId: string,
): void {
  const memory = context._memory as any
  if (!memory || typeof memory.store !== 'function') return

  try {
    const topics = todos.map(t => t.content).join('; ')
    const highCount = todos.filter(t => t.priority === 'high').length
    memory.store(
      `task-session:${sessionId}`,
      `Task session completed (${todos.length} tasks, ${highCount} high priority). Tasks: ${topics}`,
      ['task-session', 'completed'],
    )
  } catch {
    // Memory persistence is best-effort
  }
}
