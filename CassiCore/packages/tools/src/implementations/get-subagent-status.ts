/**
 * get_subagent_status — Get detailed status of a specific subagent
 * 
 * Provides comprehensive information about a subagent's current state,
 * including timing, progress, and result availability.
 */

import type { ToolDefinition, ToolHandler, ToolContext } from '../types.js'

export const getSubagentStatusDefinition: ToolDefinition = {
  name: 'get_subagent_status',
  description: 'Get detailed status of a specific subagent by its runId. Use this to check progress, timing, and whether results are available.',
  parameters: {
    type: 'object',
    properties: {
      runId: {
        type: 'string',
        description: 'The runId of the subagent to inspect (required)',
      },
    },
    required: ['runId'],
  },
}

export function makeGetSubagentStatusHandler(
  tracker: { get(runId: string): any | undefined } | undefined,
): ToolHandler {
  return async (input, _ctx: ToolContext) => {
    if (!tracker) {
      return JSON.stringify({
        error: 'Subagent tracker not available. Subagent inspection is disabled.',
      })
    }

    const { runId } = input as { runId: string }

    if (!runId || typeof runId !== 'string') {
      return JSON.stringify({
        error: 'Missing required parameter: runId',
      })
    }

    try {
      const info = tracker.get(runId)

      if (!info) {
        return JSON.stringify({
          found: false,
          error: `Subagent with runId "${runId}" not found. It may have been pruned or never existed.`,
        })
      }

      // Build comprehensive status response
      const response: Record<string, unknown> = {
        found: true,
        subagent: {
          runId: info.runId,
          sessionKey: info.sessionKey,
          parentSessionId: info.parentSessionId,
          label: info.label,
          model: info.model,
          status: info.status,
          task: info.task ? info.task.substring(0, 500) : undefined,
          createdAt: info.createdAt,
          timeoutSeconds: info.timeoutSeconds,
        },
      }

      // Add timing information
      const subagent = response.subagent as Record<string, unknown>

      if (info.startedAt) {
        subagent.startedAt = info.startedAt
      }

      if (info.completedAt) {
        subagent.completedAt = info.completedAt
      }

      if (info.durationMs !== undefined) {
        subagent.durationMs = info.durationMs
      }

      if (info.tokensUsed !== undefined) {
        subagent.tokensUsed = info.tokensUsed
      }

      // Calculate elapsed time for running subagents
      if (info.status === 'running' && info.startedAt) {
        const elapsed = Date.now() - new Date(info.startedAt).getTime()
        subagent.elapsedMs = elapsed
        subagent.elapsedFormatted = formatDuration(elapsed)

        // Calculate remaining time
        if (info.timeoutSeconds) {
          const remaining = info.timeoutSeconds * 1000 - elapsed
          subagent.remainingMs = Math.max(0, remaining)
          subagent.remainingFormatted = formatDuration(Math.max(0, remaining))
        }
      }

      // Add queue time for pending subagents
      if (info.status === 'pending') {
        const queued = Date.now() - new Date(info.createdAt).getTime()
        subagent.queuedMs = queued
        subagent.queuedFormatted = formatDuration(queued)
      }

      // Add result/error information
      if (info.status === 'completed') {
        subagent.hasResult = !!info.result
        subagent.resultLength = info.result?.length || 0
        subagent.resultPreview = info.result 
          ? info.result.substring(0, 300) + (info.result.length > 300 ? '...' : '')
          : undefined
      }

      if (info.status === 'failed' || info.status === 'timeout') {
        subagent.error = info.error
        subagent.errorType = info.status === 'timeout' ? 'timeout' : 'execution_error'
      }

      // Add next steps hint
      response.nextSteps = getNextSteps(info.status)

      return JSON.stringify(response)
    } catch (err) {
      return JSON.stringify({
        found: false,
        error: `Failed to get subagent status: ${String(err)}`,
      })
    }
  }
}

function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m ${seconds % 60}s`
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`
  }
  return `${seconds}s`
}

function getNextSteps(status: string): string {
  switch (status) {
    case 'pending':
      return 'Subagent is queued and waiting to start. Check again soon.'
    case 'running':
      return 'Subagent is actively working. Use get_subagent_result with wait=true to block until completion, or poll get_subagent_status periodically.'
    case 'completed':
      return 'Subagent has completed. Use get_subagent_result to retrieve the full output.'
    case 'failed':
      return 'Subagent failed. Check the error field for details. You may want to retry with modified parameters.'
    case 'timeout':
      return 'Subagent timed out. Consider increasing timeoutSeconds or breaking the task into smaller chunks.'
    default:
      return 'Unknown status. Please report this issue.'
  }
}
