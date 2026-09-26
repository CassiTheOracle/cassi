/**
 * VENDOR TYPE STUB — `core/jobs/job-manager.ts` (`JobManager`).
 *
 * Type-placeholder for the background JobManager surface consumed by the tools
 * via inline `import('...job-manager.js').JobManager` type refs (check-job,
 * run-background, registerCoreTools deps). Only `get`/`list`/`start`/`cancel`
 * are referenced by the tools. Owned by `@cassicore/jobs` (P6); re-pointed there.
 */
import type { JobConfig, JobResult } from './types.js'

/** Manages background OS processes with ring-buffer output tracking. */
export interface JobManager {
  start(config: JobConfig): JobResult
  get(jobId: string): JobResult | undefined
  list(): JobResult[]
  cancel(jobId: string): boolean
  wait(jobId: string, timeoutMs?: number): Promise<JobResult | undefined>
  getRunningJobsSummary(): string | undefined
}
