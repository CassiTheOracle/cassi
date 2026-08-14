/**
 * VENDOR TYPE STUB — `core/jobs/types.ts`.
 *
 * Faithful type surface for the background job system (JobConfig/JobResult).
 * Owned by `@cassicore/jobs` (P6); re-pointed there. Consumed via
 * `import('...job-manager.js').JobManager` inline type refs in the tools.
 */

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'timeout' | 'cancelled'

export interface JobConfig {
  /** Shell command to execute */
  command: string
  /** Human-readable label (e.g., "Build project") */
  label?: string
  /** Maximum runtime in ms (default: 300_000 = 5 min) */
  timeoutMs?: number
  /** Working directory (default: project root) */
  cwd?: string
  /** Whether to emit events on completion (default: true) */
  notify?: boolean
  /** Session ID that created this job (for context injection) */
  sessionId?: string
}

export interface JobResult {
  jobId: string
  label: string
  status: JobStatus
  exitCode?: number
  /** Last ~50KB of stdout (ring buffer) */
  stdout: string
  /** Last ~5KB of stderr (ring buffer) */
  stderr: string
  /** Execution duration in ms */
  duration?: number
  startedAt: number
  completedAt?: number
  /** Path to full stdout file (if output exceeded buffer) */
  stdoutFile?: string
  /** Path to full stderr file (if output exceeded buffer) */
  stderrFile?: string
}
