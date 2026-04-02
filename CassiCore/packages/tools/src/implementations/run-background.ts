/**
 * run_background — Start a shell command in the background.
 *
 * Returns immediately with a job ID. The command runs asynchronously
 * in the daemon's JobManager. Use check_job or wait_job to get results.
 */

import type { ToolDefinition, ToolHandler } from '../types.js'

export const runBackgroundDefinition: ToolDefinition = {
  name: 'run_background',
  description:
    'Start a shell command in the background and return immediately with a job ID. ' +
    'The command runs asynchronously — use check_job to poll status or wait_job to block until completion. ' +
    'Useful for long-running operations like builds, test suites, benchmarks, or daemon restarts ' +
    'where you want to continue other work while waiting.',
  parameters: {
    type: 'object',
    properties: {
      command: {
        type: 'string',
        description: 'Shell command to execute (e.g., "npm run build", "npx vitest run tests/")',
      },
      label: {
        type: 'string',
        description: 'Human-readable label for this job (e.g., "Build project"). Used in notifications.',
      },
      timeout: {
        type: 'number',
        description: 'Maximum runtime in seconds (default: 300, max: 600).',
      },
      cwd: {
        type: 'string',
        description: 'Working directory (default: project root).',
      },
    },
    required: ['command'],
  },
  timeoutMs: 5_000, // Tool itself returns immediately
  requiredPermission: 'full-access',
}

/**
 * Factory: creates the handler with a reference to the daemon's JobManager.
 * The daemon wires this during startup.
 * @dep callers: registerCoreTools (core/tools/implementations/index.ts)
 * @dep calls: start
 * @dep flows: BootPipelineTools → MakeRunBackgroundHandler (4/4)
 * @dep module: Unknown
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
export function makeRunBackgroundHandler(
  getJobManager: () => import('../../jobs/job-manager.js').JobManager | undefined
): ToolHandler {
  return async (input, ctx) => {
    const jm = getJobManager()
    if (!jm) {
      return JSON.stringify({ error: 'JobManager not available' })
    }

    const command = input['command'] as string
    if (!command || typeof command !== 'string') {
      return JSON.stringify({ error: 'command is required' })
    }

    const label = (input['label'] as string) || undefined
    const timeoutSec = Math.min(Math.max((input['timeout'] as number) ?? 300, 5), 600)
    const cwd = (input['cwd'] as string) || ctx.workingDir

    try {
      const result = jm.start({
        command,
        label,
        timeoutMs: timeoutSec * 1000,
        cwd,
        notify: true,
        sessionId: ctx.sessionId,
      })

      return JSON.stringify({
        jobId: result.jobId,
        label: result.label,
        status: result.status,
        startedAt: result.startedAt,
        message: `Job started. Use check_job("${result.jobId}") to poll or wait_job("${result.jobId}") to block until done.`,
      }, null, 2)
    } catch (err) {
      return JSON.stringify({ error: String(err) })
    }
  }
}
