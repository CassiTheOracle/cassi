/**
 * JobManager — Background shell command executor.
 *
 * Runs shell commands asynchronously, tracks their state, captures output
 * via ring buffers + file dumps, and emits events on completion.
 *
 * Designed to be safe: same sandbox as shell_exec, concurrency limits,
 * per-job timeouts, automatic cleanup of old jobs.
 */

import { spawn, spawnSync } from 'node:child_process'
import { createWriteStream, mkdirSync, existsSync, unlinkSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { homedir } from 'node:os'
import type { IEventBus } from '../../types/interfaces.js'
import type { ILogger } from '../../types/interfaces.js'
import { Job, JobConfig, JobResult, JobStatus, RingBuffer } from './types.js'

/** Max concurrent background jobs */
const MAX_CONCURRENT = 5
/** Max completed jobs to keep in history */
const MAX_HISTORY = 30
/** Default timeout: 5 minutes */
const DEFAULT_TIMEOUT_MS = 300_000
/** Max timeout: 10 minutes */
const MAX_TIMEOUT_MS = 600_000
/** Ring buffer size for stdout */
const STDOUT_BUFFER_SIZE = 50 * 1024 // 50KB
/** Ring buffer size for stderr */
const STDERR_BUFFER_SIZE = 10 * 1024 // 10KB
/** Auto-cleanup file age: 1 hour */
const FILE_CLEANUP_AGE_MS = 60 * 60 * 1000

export class JobManager {
  private readonly jobs = new Map<string, Job>()
  private jobCounter = 0
  private bus?: IEventBus
  private readonly logger: ILogger
  private readonly jobsDir: string
  private readonly workingDir: string
  private cleanupTimer?: ReturnType<typeof setInterval>
  private shell: string | null = null

  constructor(logger: ILogger, workingDir: string) {
    this.logger = logger.child('job-manager')
    this.workingDir = workingDir

    // Create jobs output directory
    this.jobsDir = join(homedir(), '.cassicore', 'jobs')
    if (!existsSync(this.jobsDir)) {
      mkdirSync(this.jobsDir, { recursive: true })
    }

    // Detect available shell
    const bashCheck = spawnSync('which', ['bash'], { encoding: 'utf-8', timeout: 5000 })
    this.shell = bashCheck.status === 0
      ? 'bash'
      : (spawnSync('which', ['sh'], { encoding: 'utf-8', timeout: 5000 }).status === 0 ? 'sh' : null)

    // Start periodic cleanup of old job files
    this.cleanupTimer = setInterval(() => this.cleanupOldFiles(), FILE_CLEANUP_AGE_MS)
    try { (this.cleanupTimer as any).unref?.() } catch { /* ok */ }
  }

  /** Wire the event bus for job completion notifications */
  setEventBus(bus: IEventBus): void {
    this.bus = bus
  }

  /** Start a background job. Returns immediately with the job ID. */
  start(config: JobConfig): JobResult {
    if (!this.shell) {
      throw new Error('No shell available (bash/sh not found)')
    }

    // Enforce concurrency limit
    const running = [...this.jobs.values()].filter(j => j.status === 'running').length
    if (running >= MAX_CONCURRENT) {
      throw new Error(`Max concurrent jobs reached (${MAX_CONCURRENT}). Cancel or wait for a job to finish.`)
    }

    const jobId = `job-${Date.now()}-${(++this.jobCounter).toString(36)}`
    const timeoutMs = Math.min(config.timeoutMs ?? DEFAULT_TIMEOUT_MS, MAX_TIMEOUT_MS)
    const cwd = config.cwd || this.workingDir
    const label = config.label || config.command.slice(0, 60)

    // Create file streams for full output capture
    const stdoutFile = join(this.jobsDir, `${jobId}.stdout`)
    const stderrFile = join(this.jobsDir, `${jobId}.stderr`)
    const stdoutStream = createWriteStream(stdoutFile)
    const stderrStream = createWriteStream(stderrFile)

    const job: Job = {
      id: jobId,
      config: { ...config, label, timeoutMs },
      status: 'running',
      stdoutBuffer: new RingBuffer(STDOUT_BUFFER_SIZE),
      stderrBuffer: new RingBuffer(STDERR_BUFFER_SIZE),
      stdoutFile,
      stderrFile,
      stdoutOverflowed: false,
      stderrOverflowed: false,
      startedAt: Date.now(),
    }

    // Spawn the process
    const proc = spawn(this.shell, ['-c', config.command], {
      cwd,
      env: { ...process.env, FORCE_COLOR: '0' },
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    job.process = proc

    // Track output sizes for overflow detection
    let stdoutTotal = 0
    let stderrTotal = 0

    proc.stdout?.on('data', (chunk: Buffer) => {
      const text = chunk.toString()
      stdoutTotal += text.length
      job.stdoutBuffer.append(text)
      stdoutStream.write(text)
      if (stdoutTotal > STDOUT_BUFFER_SIZE) {
        job.stdoutOverflowed = true
      }
    })

    proc.stderr?.on('data', (chunk: Buffer) => {
      const text = chunk.toString()
      stderrTotal += text.length
      job.stderrBuffer.append(text)
      stderrStream.write(text)
      if (stderrTotal > STDERR_BUFFER_SIZE) {
        job.stderrOverflowed = true
      }
    })

    // Set timeout
    job.timer = setTimeout(() => {
      if (job.status === 'running') {
        this.logger.warn('Job timeout, killing process', { jobId, timeoutMs })
        proc.kill('SIGTERM')
        setTimeout(() => {
          try { proc.kill('SIGKILL') } catch { /* already dead */ }
        }, 5000)
        this.finishJob(job, 'timeout')
      }
    }, timeoutMs)

    // Handle process exit
    proc.on('close', (code) => {
      if (job.status !== 'running') return // Already handled (timeout/cancel)
      job.exitCode = code ?? 1
      const status: JobStatus = code === 0 ? 'completed' : 'failed'
      this.finishJob(job, status)
    })

    proc.on('error', (err) => {
      if (job.status !== 'running') return
      job.stderrBuffer.append(`\nProcess error: ${String(err)}`)
      stderrStream.write(`\nProcess error: ${String(err)}`)
      this.finishJob(job, 'failed')
    })

    // Close file streams when process exits
    proc.on('close', () => {
      stdoutStream.end()
      stderrStream.end()
    })

    this.jobs.set(jobId, job)
    this.evictOldJobs()

    this.logger.info('Job started', { jobId, label, command: config.command.slice(0, 100), cwd })

    // Emit started event
    if (config.notify !== false && this.bus) {
      this.bus.emit({
        type: 'job:started',
        jobId,
        label,
        sessionId: config.sessionId,
        command: config.command.slice(0, 200),
      } as any)
    }

    return this.toResult(job)
  }

  /** Get current status and result of a job */
  get(jobId: string): JobResult | undefined {
    const job = this.jobs.get(jobId)
    if (!job) return undefined
    return this.toResult(job)
  }

  /** Wait for a job to complete (with timeout). Returns result or undefined on timeout. */
  async wait(jobId: string, timeoutMs: number = 120_000): Promise<JobResult | undefined> {
    const job = this.jobs.get(jobId)
    if (!job) return undefined
    if (job.status !== 'running') return this.toResult(job)

    return new Promise((resolve) => {
      const checkInterval = setInterval(() => {
        if (job.status !== 'running') {
          clearInterval(checkInterval)
          clearTimeout(timer)
          resolve(this.toResult(job))
        }
      }, 500)

      const timer = setTimeout(() => {
        clearInterval(checkInterval)
        resolve(this.toResult(job)) // Return current state even if still running
      }, timeoutMs)
    })
  }

  /** Cancel a running job */
  cancel(jobId: string): boolean {
    const job = this.jobs.get(jobId)
    if (!job || job.status !== 'running') return false

    job.process?.kill('SIGTERM')
    setTimeout(() => {
      try { job.process?.kill('SIGKILL') } catch { /* ok */ }
    }, 5000)
    this.finishJob(job, 'cancelled')
    return true
  }

  /** List all jobs (most recent first) */
  list(): JobResult[] {
    return [...this.jobs.values()]
      .sort((a, b) => b.startedAt - a.startedAt)
      .map(j => this.toResult(j))
  }

  /** Get running jobs summary for thinker/subconscious injection */
  getRunningJobsSummary(): string | undefined {
    const running = [...this.jobs.values()].filter(j => j.status === 'running')
    const recentCompleted = [...this.jobs.values()]
      .filter(j => j.status !== 'running' && j.completedAt && (Date.now() - j.completedAt) < 60_000)
      .sort((a, b) => (b.completedAt ?? 0) - (a.completedAt ?? 0))
      .slice(0, 3)

    if (running.length === 0 && recentCompleted.length === 0) return undefined

    const parts: string[] = []

    if (running.length > 0) {
      parts.push(`Running jobs (${running.length}):`)
      for (const j of running) {
        const elapsed = Math.round((Date.now() - j.startedAt) / 1000)
        parts.push(`  - "${j.config.label}" (${elapsed}s elapsed)`)
      }
    }

    if (recentCompleted.length > 0) {
      parts.push(`Recently completed:`)
      for (const j of recentCompleted) {
        const ago = Math.round((Date.now() - (j.completedAt ?? 0)) / 1000)
        const icon = j.status === 'completed' ? 'OK' : j.status === 'failed' ? 'FAILED' : j.status.toUpperCase()
        parts.push(`  - "${j.config.label}" [${icon}] (${ago}s ago)`)
      }
    }

    return parts.join('\n')
  }

  /** Shutdown: cancel all running jobs, stop cleanup timer */
  async shutdown(): Promise<void> {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer)
      this.cleanupTimer = undefined
    }

    for (const [jobId, job] of this.jobs) {
      if (job.status === 'running') {
        this.cancel(jobId)
      }
    }
  }

  // ─── Private ───────────────────────────────────────────────────────────

  private finishJob(job: Job, status: JobStatus): void {
    if (job.timer) {
      clearTimeout(job.timer)
      job.timer = undefined
    }
    job.status = status
    job.completedAt = Date.now()
    job.process = undefined // Release process reference

    const duration = job.completedAt - job.startedAt
    const label = job.config.label || job.id

    this.logger.info('Job finished', {
      jobId: job.id,
      label,
      status,
      exitCode: job.exitCode,
      duration,
    })

    // Emit completion event
    if (job.config.notify !== false && this.bus) {
      const summary = status === 'completed'
        ? job.stdoutBuffer.toString().trim().slice(-200)
        : job.stderrBuffer.toString().trim().slice(-200) || job.stdoutBuffer.toString().trim().slice(-200)

      this.bus.emit({
        type: status === 'completed'
          ? 'job:completed'
          : status === 'timeout'
            ? 'job:timeout'
            : status === 'cancelled'
              ? 'job:cancelled'
              : 'job:failed',
        jobId: job.id,
        label,
        exitCode: job.exitCode,
        duration,
        summary,
        sessionId: job.config.sessionId,
      } as any)
    }
  }

  private toResult(job: Job): JobResult {
    return {
      jobId: job.id,
      label: job.config.label || job.id,
      status: job.status,
      exitCode: job.exitCode,
      stdout: job.stdoutBuffer.toString(),
      stderr: job.stderrBuffer.toString(),
      duration: job.completedAt ? job.completedAt - job.startedAt : Date.now() - job.startedAt,
      startedAt: job.startedAt,
      completedAt: job.completedAt,
      stdoutFile: job.stdoutOverflowed ? job.stdoutFile : undefined,
      stderrFile: job.stderrOverflowed ? job.stderrFile : undefined,
    }
  }

  private evictOldJobs(): void {
    const completed = [...this.jobs.entries()]
      .filter(([, j]) => j.status !== 'running')
      .sort(([, a], [, b]) => (a.completedAt ?? 0) - (b.completedAt ?? 0))

    while (completed.length > MAX_HISTORY) {
      const [id, job] = completed.shift()!
      this.jobs.delete(id)
      // Clean up files
      this.safeUnlink(job.stdoutFile)
      this.safeUnlink(job.stderrFile)
    }
  }

  private cleanupOldFiles(): void {
    try {
      const files = readdirSync(this.jobsDir)
      const now = Date.now()
      for (const file of files) {
        const filePath = join(this.jobsDir, file)
        try {
          const stats = statSync(filePath)
          if (now - stats.mtimeMs > FILE_CLEANUP_AGE_MS) {
            unlinkSync(filePath)
          }
        } catch { /* file already gone or inaccessible */ }
      }
    } catch { /* dir doesn't exist or inaccessible */ }
  }

  private safeUnlink(path?: string): void {
    if (!path) return
    try { unlinkSync(path) } catch { /* ok */ }
  }
}
