/**
 * TodoWrite Tool — Persistent structured task tracking.
 *
 * Provides a per-session todo list that agents can use to track
 * multi-step work. Todos persist to a JSON file so they survive
 * across turns and can be inspected by parent sessions.
 *
 * Features:
 * - States: pending, in_progress, completed
 * - Returns old + new state for visibility
 * - Verification nudge: when all items complete but none mention
 *   "verification", the output signals that verification was skipped
 *
 * Inspired by the Claude Code TodoWrite tool pattern.
 */

import { join } from 'node:path'
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs'

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'

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
    'Send the FULL todo list on every call (not just changes).',
  parameters: {
    type: 'object',
    properties: {
      todos: {
        type: 'array',
        description: 'The complete updated todo list',
        items: {
          type: 'object',
          enum: undefined,
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

  // Load existing todos
  const storePath = resolveStorePath(context)
  const oldTodos = loadTodos(storePath)

  // Check for verification nudge
  const allDone = parsed.todos.every(t => t.status === 'completed')
  const hasVerification = parsed.todos.some(t =>
    t.content.toLowerCase().includes('verif') ||
    t.content.toLowerCase().includes('test') ||
    t.content.toLowerCase().includes('build') ||
    t.content.toLowerCase().includes('check'),
  )
  const verificationNudgeNeeded = allDone && parsed.todos.length >= 3 && !hasVerification

  // Persist — if all done, clear the store
  const persisted = allDone ? [] : parsed.todos
  saveTodos(storePath, persisted)

  const output: TodoWriteOutput = {
    oldTodos,
    newTodos: parsed.todos,
    verificationNudgeNeeded,
  }

  let result = JSON.stringify(output, null, 2)

  if (verificationNudgeNeeded) {
    result += '\n\n[Note: All tasks are marked complete but none mention verification. ' +
      'Consider adding a verification step to confirm the changes work correctly.]'
  }

  return result
}

/* ------------------------------------------------------------------ */
/*  Persistence                                                        */
/* ------------------------------------------------------------------ */

function resolveStorePath(context: ToolExecutionContext): string {
  const dir = join(context.workingDir, '.cassicore')
  if (!existsSync(dir)) {
    try { mkdirSync(dir, { recursive: true }) } catch { /* ignore */ }
  }
  return join(dir, `todos-${context.sessionId || 'default'}.json`)
}

function loadTodos(path: string): TodoItem[] {
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
