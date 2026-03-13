/**
 * Background Job System — Types
 *
 * Defines the shape of background jobs managed by JobManager.
 * Jobs run shell commands asynchronously, track output via ring buffers
 * + file dumps, and emit events on the EventBus when they complete.
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

export interface Job {
  id: string
  config: JobConfig
  status: JobStatus
  exitCode?: number
  /** Ring buffer for stdout (in-memory, capped) */
  stdoutBuffer: RingBuffer
  /** Ring buffer for stderr (in-memory, capped) */
  stderrBuffer: RingBuffer
  /** Full-output file paths */
  stdoutFile?: string
  stderrFile?: string
  /** Whether stdout exceeded the ring buffer */
  stdoutOverflowed: boolean
  /** Whether stderr exceeded the ring buffer */
  stderrOverflowed: boolean
  startedAt: number
  completedAt?: number
  /** The spawned child process (undefined after completion) */
  process?: import('node:child_process').ChildProcess
  /** Timeout timer handle */
  timer?: ReturnType<typeof setTimeout>
}

/**
 * Simple ring buffer that keeps the last N bytes of a stream.
 */
export class RingBuffer {
  private chunks: string[] = []
  private totalSize = 0
  private readonly maxSize: number

  constructor(maxSizeBytes: number) {
    this.maxSize = maxSizeBytes
  }

  append(data: string): void {
    this.chunks.push(data)
    this.totalSize += data.length

    // Trim from front when over budget
    while (this.totalSize > this.maxSize && this.chunks.length > 1) {
      const removed = this.chunks.shift()!
      this.totalSize -= removed.length
    }

    // If a single chunk exceeds max, truncate it
    if (this.totalSize > this.maxSize && this.chunks.length === 1) {
      this.chunks[0] = this.chunks[0].slice(-this.maxSize)
      this.totalSize = this.chunks[0].length
    }
  }

  toString(): string {
    return this.chunks.join('')
  }

  get size(): number {
    return this.totalSize
  }

  clear(): void {
    this.chunks = []
    this.totalSize = 0
  }
}
