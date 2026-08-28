/**
 * check_job — Get the current status and result of a background job.
 */

import type { ToolDefinition, ToolHandler } from '../types.js'

export const checkJobDefinition: ToolDefinition = {
  name: 'check_job',
  description:
    'Check the status and output of a background job started with run_background. ' +
    'Returns the current status (running/completed/failed/timeout/cancelled), ' +
    'exit code, stdout/stderr output, and duration.',
  parameters: {
    type: 'object',
    properties: {
      jobId: {
        type: 'string',
        description: 'The job ID returned by run_background.',
      },
    },
    required: ['jobId'],
  },
  timeoutMs: 5_000,
  requiredPermission: 'read-only',
}

/**
 * @dep callers: registerCoreTools (core/tools/implementations/index.ts)
 * @dep flows: BootPipelineTools → MakeCheckJobHandler (4/4)
 * @dep module: Unknown
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

export function makeCheckJobHandler(
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

    const result = jm.get(jobId)
    if (!result) {
      // Maybe list available jobs to help
      const jobs = jm.list()
      return JSON.stringify({
        error: `Job "${jobId}" not found`,
        availableJobs: jobs.slice(0, 5).map(j => ({ jobId: j.jobId, label: j.label, status: j.status })),
      })
    }

    return JSON.stringify(result, null, 2)
  }
}
