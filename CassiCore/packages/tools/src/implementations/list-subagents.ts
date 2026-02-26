/**
 * list_subagents — List tracked subagents with optional filtering
 * 
 * Allows agents to inspect their spawned subagents and monitor progress.
 */

import type { ToolDefinition, ToolHandler, ToolExecutionContext } from '../types.js'

export const listSubagentsDefinition: ToolDefinition = {
  name: 'list_subagents',
  description: 'List all tracked subagents with optional filtering by status or parent session. Use this to monitor progress of async tasks and find completed results.',
  parameters: {
    type: 'object',
    properties: {
      status: {
        type: 'string',
        enum: ['pending', 'running', 'completed', 'failed', 'timeout', 'all'],
        description: 'Filter by subagent status. Default: "all"',
        default: 'all',
      },
      parentSessionId: {
        type: 'string',
        description: 'Filter by parent session ID (default: current session)',
      },
      limit: {
        type: 'number',
        description: 'Maximum number of results to return (default: 50)',
        default: 50,
      },
      includeTask: {
        type: 'boolean',
        description: 'Include task description in results (default: false)',
        default: false,
      },
    },
  },
}

export function makeListSubagentsHandler(
  tracker: { list(): Array<any>; getByParent(parentId: string): Array<any> } | undefined,
): ToolHandler {
  return async (input, ctx: ToolExecutionContext) => {
    if (!tracker) {
      return JSON.stringify({
        error: 'Subagent tracker not available. Subagent inspection is disabled.',
      })
    }

    const { 
      status = 'all', 
      parentSessionId = ctx.sessionId,
      limit = 50,
      includeTask = false,
    } = input as {
      status?: string
      parentSessionId?: string
      limit?: number
      includeTask?: boolean
    }

    try {
      // Get subagents - either by parent or all
      let subagents = parentSessionId 
        ? tracker.getByParent(parentSessionId)
        : tracker.list()

      // Filter by status if specified
      if (status !== 'all') {
        subagents = subagents.filter(s => s.status === status)
      }

      // Sort by createdAt (newest first) and limit
      subagents = subagents
        .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
        .slice(0, limit)

      // Format response
      const formatted = subagents.map(s => {
        const base: Record<string, unknown> = {
          runId: s.runId,
          label: s.label,
          status: s.status,
          model: s.model,
          createdAt: s.createdAt,
        }

        // Add optional fields
        if (s.startedAt) base.startedAt = s.startedAt
        if (s.completedAt) base.completedAt = s.completedAt
        if (s.durationMs !== undefined) base.durationMs = s.durationMs
        if (s.tokensUsed !== undefined) base.tokensUsed = s.tokensUsed
        if (s.timeoutSeconds !== undefined) base.timeoutSeconds = s.timeoutSeconds
        if (includeTask && s.task) base.task = s.task.substring(0, 200)

        // Add progress indicator for running subagents
        if (s.status === 'running' && s.startedAt) {
          const elapsed = Date.now() - new Date(s.startedAt).getTime()
          base.elapsedMs = elapsed
          base.progress = `Running for ${Math.round(elapsed / 1000)}s`
        }

        // Add result preview for completed
        if (s.status === 'completed') {
          base.hasResult = !!s.result
          base.resultPreview = s.result ? s.result.substring(0, 100) + '...' : undefined
        }

        // Add error preview for failed
        if (s.status === 'failed' || s.status === 'timeout') {
          base.error = s.error ? s.error.substring(0, 200) : 'Unknown error'
        }

        return base
      })

      return JSON.stringify({
        count: formatted.length,
        total: parentSessionId ? tracker.getByParent(parentSessionId).length : tracker.list().length,
        filter: { status, parentSessionId },
        subagents: formatted,
      })
    } catch (err) {
      return JSON.stringify({
        error: `Failed to list subagents: ${String(err)}`,
      })
    }
  }
}
