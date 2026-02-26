/**
 * get_subagent_result — Get the result of a completed subagent
 *
 * Retrieves the output from a subagent. Can optionally wait for completion.
 */

import type { ToolDefinition, ToolHandler, ToolContext } from '../types.js'

export const getSubagentResultDefinition: ToolDefinition = {
  name: 'get_subagent_result',
  description: 'Get the result of a completed subagent. Optionally block and wait for the subagent to finish. Use this to collect output from spawned subagents.',
  parameters: {
    type: 'object',
    properties: {
      runId: {
        type: 'string',
        description: 'The runId of the subagent (required)',
      },
      wait: {
        type: 'boolean',
        description: 'Block and wait for the subagent to complete (default: false)',
        default: false,
      },
      timeoutSeconds: {
        type: 'number',
        description: 'Maximum time to wait if wait=true (default: 60)',
        default: 60,
      },
      pollIntervalSeconds: {
        type: 'number',
        description: 'How often to check status when waiting (default: 2)',
        default: 2,
      },
    },
    required: ['runId'],
  },
}

export function makeGetSubagentResultHandler(
  tracker: {
    get(runId: string): any | undefined
    getResult(runId: string): { result?: string; error?: string; durationMs?: number } | undefined
  } | undefined,
): ToolHandler {
  return async (input, _ctx: ToolContext) => {
    if (!tracker) {
      return JSON.stringify({
        error: 'Subagent tracker not available. Subagent inspection is disabled.',
      })
    }

    const {
      runId,
      wait = false,
      timeoutSeconds = 60,
      pollIntervalSeconds = 2,
    } = input as {
      runId: string
      wait?: boolean
      timeoutSeconds?: number
      pollIntervalSeconds?: number
    }

    if (!runId || typeof runId !== 'string') {
      return JSON.stringify({
        error: 'Missing required parameter: runId',
      })
    }

    const startTime = Date.now()
    const maxWaitMs = timeoutSeconds * 1000

    try {
      // If wait=true, poll until complete or timeout
      if (wait) {
        while (true) {
          const info = tracker.get(runId)

          if (!info) {
            return JSON.stringify({
              status: 'not_found',
              error: `Subagent with runId "${runId}" not found.`,
              waitedMs: Date.now() - startTime,
            })
          }

          // Check if completed, failed, or timed out
          if (info.status === 'completed' || info.status === 'failed' || info.status === 'timeout') {
            const result = tracker.getResult(runId)
            return JSON.stringify({
              status: info.status,
              runId: info.runId,
              label: info.label,
              result: result?.result,
              error: result?.error || info.error,
              durationMs: result?.durationMs || info.durationMs,
              tokensUsed: info.tokensUsed,
              completedAt: info.completedAt,
              waitedMs: Date.now() - startTime,
            })
          }

          // Check timeout
          const elapsed = Date.now() - startTime
          if (elapsed >= maxWaitMs) {
            return JSON.stringify({
              status: 'wait_timeout',
              error: `Wait timeout exceeded after ${timeoutSeconds}s`,
              subagentStatus: info.status,
              waitedMs: elapsed,
              elapsedMs: info.startedAt ? Date.now() - new Date(info.startedAt).getTime() : undefined,
            })
          }

          // Wait before next poll
          await sleep(pollIntervalSeconds * 1000)
        }
      }

      // Non-blocking mode: return immediately
      const info = tracker.get(runId)

      if (!info) {
        return JSON.stringify({
          status: 'not_found',
          error: `Subagent with runId "${runId}" not found.`,
        })
      }

      // If still running, return status
      if (info.status === 'pending' || info.status === 'running') {
        const elapsed = info.startedAt
          ? Date.now() - new Date(info.startedAt).getTime()
          : Date.now() - new Date(info.createdAt).getTime()

        return JSON.stringify({
          status: info.status,
          runId: info.runId,
          label: info.label,
          message: `Subagent is ${info.status}. Use wait=true to block until completion, or poll again later.`,
          elapsedMs: elapsed,
          startedAt: info.startedAt,
          createdAt: info.createdAt,
        })
      }

      // Return result for completed/failed/timeout
      const result = tracker.getResult(runId)
      return JSON.stringify({
        status: info.status,
        runId: info.runId,
        label: info.label,
        result: result?.result,
        error: result?.error || info.error,
        durationMs: result?.durationMs || info.durationMs,
        tokensUsed: info.tokensUsed,
        completedAt: info.completedAt,
      })
    } catch (err) {
      return JSON.stringify({
        status: 'error',
        error: `Failed to get subagent result: ${String(err)}`,
        waitedMs: Date.now() - startTime,
      })
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}
