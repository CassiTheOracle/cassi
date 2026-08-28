/**
 * wait_job — Block until a background job completes (with timeout).
 *
 * Returns the full result once the job finishes, or the current state
 * if the wait timeout is reached.
 */

import type { ToolDefinition, ToolHandler } from '../types.js'

export const waitJobDefinition: ToolDefinition = {
  name: 'wait_job',
  description:
    'Wait for a background job to complete. Blocks until the job finishes or the wait timeout is reached. ' +
    'Returns the full result including stdout, stderr, exit code, and duration. ' +
    'If the job is still running when the timeout expires, returns the current state.',
  parameters: {
    type: 'object',
    properties: {
      jobId: {
        type: 'string',
        description: 'The job ID returned by run_background.',
      },
      timeout: {
        type: 'number',
        description: 'Maximum time to wait in seconds (default: 120, max: 300).',
      },
    },
    required: ['jobId'],
  },
  timeoutMs: 310_000, // Slightly above max wait to avoid tool timeout before job timeout
  requiredPermission: 'read-only',
}

/**
 * @dep callers: registerCoreTools (core/tools/implementations/index.ts)
 * @dep calls: wait
 * @dep flows: BootPipelineTools → MakeWaitJobHandler (4/4)
 * @dep module: Unknown
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

export function makeWaitJobHandler(
  getJobManager: () => import('../vendor/core/jobs/job-manager.js').JobManager | undefined
): ToolHandler {
  return async (input) => {
    const jm = getJobManager()
    if (!jm) {
      return JSON.stringify({ error: 'JobManager not available' })
    }

    const jobId = input['jobId'] as string
    if (!jobId) {
      return JSON.stringify({ error: 'jobId is required' })
    }

    const timeoutSec = Math.min(Math.max((input['timeout'] as number) ?? 120, 5), 300)

    const result = await jm.wait(jobId, timeoutSec * 1000)
    if (!result) {
      return JSON.stringify({ error: `Job "${jobId}" not found` })
    }

    return JSON.stringify(result, null, 2)
  }
}
