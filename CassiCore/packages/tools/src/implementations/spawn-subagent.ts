import type { ToolDefinition, ToolHandler } from '../types.js'
import type { ISessionManager } from '../../../types/runtime.js'

export const spawnSubagentDefinition: ToolDefinition = {
  name: 'spawn_subagent',
  description: 'Spawn a background subagent to complete a task asynchronously. The subagent runs independently and reports back when complete.',
  parameters: {
    type: 'object',
    properties: {
      task: {
        type: 'string',
        description: 'Detailed description of what the subagent should do. Be specific about expected outputs.',
      },
      label: {
        type: 'string',
        description: 'Short label for tracking (e.g., "analyze-code", "research-topic").',
      },
      model: {
        type: 'string',
        description: 'Model to use for the subagent. Defaults to gpt-5-mini for cost efficiency.',
        default: 'github-copilot/gpt-5-mini',
      },
      timeoutSeconds: {
        type: 'number',
        description: 'Maximum time in seconds before the subagent is terminated. Default 300 (5 minutes).',
        default: 300,
      },
    },
    required: ['task', 'label'],
  },
  timeoutMs: 10_000, // Just for the spawn operation itself
}

export function makeSpawnSubagentHandler(
  sessionManager: ISessionManager,
  spawnFn?: (params: {
    task: string
    label: string
    model: string
    timeoutSeconds: number
    parentSessionId: string
  }) => Promise<{ runId: string; sessionKey: string }>,
): ToolHandler {
  return async (input, ctx) => {
    const { task, label, model = 'github-copilot/gpt-5-mini', timeoutSeconds = 300 } = input as {
      task: string
      label: string
      model?: string
      timeoutSeconds?: number
    }

    if (!task || typeof task !== 'string') {
      return JSON.stringify({ error: 'Missing required parameter: task' })
    }
    if (!label || typeof label !== 'string') {
      return JSON.stringify({ error: 'Missing required parameter: label' })
    }

    // If no spawn function provided, return a simulated response
    // In production, this would integrate with the actual subagent spawning system
    if (!spawnFn) {
      return JSON.stringify({
        status: 'spawned',
        runId: `simulated-${Date.now()}`,
        label,
        model,
        timeoutSeconds,
        message: 'Subagent spawn requested. (Subagent system not fully wired yet - this is a stub)',
      })
    }

    try {
      const result = await spawnFn({
        task,
        label,
        model,
        timeoutSeconds,
        parentSessionId: ctx.sessionId,
      })

      return JSON.stringify({
        status: 'spawned',
        runId: result.runId,
        sessionKey: result.sessionKey,
        label,
        model,
        timeoutSeconds,
      })
    } catch (err) {
      return JSON.stringify({
        error: `Failed to spawn subagent: ${String(err)}`,
      })
    }
  }
}
