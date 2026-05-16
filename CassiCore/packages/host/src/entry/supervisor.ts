/**
 * supervisor.ts — Lightweight daemon supervisor.
 *
 * Spawns the actual daemon (daemon-main.ts) as a child process and monitors
 * it via IPC heartbeat.  Automatically restarts the daemon on crash with
 * exponential backoff, and opens a circuit breaker if crashes are too frequent.
 *
 * Hierarchy:
 *   supervisor (this process)
 *     └─ daemon-main (child, forked with IPC)
 *          └─ worker processes (forked by plugin-host)
 */

import { fork, spawn, type ChildProcess } from 'node:child_process'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import { fileURLToPath } from 'node:url'

import { rootLogger } from '../logger.js'
import { rotateLogByVersion } from '../logger.js'
import { checkForUpdates, extractAndBuild } from './code-extractor.js'
import { getBuildIdentifier, formatBuildId } from '../build-id.js'

process.title = 'cassi:supervisor'

const logger = rootLogger.child('supervisor')


interface SupervisorConfig {
  /** Heartbeat ping interval (ms). Default 5000. */
  heartbeatIntervalMs: number
  /** If no pong within this time, declare daemon dead. Default 15000. */
  heartbeatTimeoutMs: number
  /** Max crashes within crashWindowMs before circuit opens. Default 5. */
  maxCrashesPerWindow: number
  /** Rolling crash window. Default 300000 (5 min). */
  crashWindowMs: number
  /** Base restart delay (exponential backoff). Default 1000. */
  baseRestartDelayMs: number
  /** Max restart delay cap. Default 60000. */
  maxRestartDelayMs: number
  /** Graceful shutdown timeout before SIGKILL. Default 30000. */
  shutdownTimeoutMs: number
}

interface HealthSnapshot {
  memoryMb: number
  eventLoopLagMs: number
}

interface DaemonReadyMessage {
  type: 'ready'
  status: 'started'
  pid: number
  admin: { tcpPort: number; unixPath: string } | null
}

interface HeartbeatPongMessage {
  type: 'heartbeat:pong'
  ts: number
  health: HealthSnapshot
}

type DaemonMessage = DaemonReadyMessage | HeartbeatPongMessage


export class Supervisor {
  private child: ChildProcess | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private lastPongTime = 0
  private lastHealth: HealthSnapshot | null = null

  // Crash tracking
  private crashTimestamps: number[] = []
  private consecutiveCrashes = 0
  private circuitOpen = false
  private restartTimer: ReturnType<typeof setTimeout> | null = null

  // State
  private stopping = false
  private daemonReady = false

  private readonly config: SupervisorConfig
  private readonly daemonMainPath: string
  private readonly useTsxLauncher: boolean
  private readonly tsxBinPath: string
  private readonly repoRoot: string
  private readonly logFile: string

  constructor(config?: Partial<SupervisorConfig>) {
    this.config = {
      heartbeatIntervalMs: 5000,
      heartbeatTimeoutMs: 45000,
      maxCrashesPerWindow: 8,
      crashWindowMs: 300_000,
      baseRestartDelayMs: 2000,
      maxRestartDelayMs: 60_000,
      shutdownTimeoutMs: 30_000,
      ...config,
    }

    const here = path.dirname(fileURLToPath(import.meta.url))
    const isCompiled = path.basename(here) === 'entry' && path.basename(path.dirname(here)) === 'core'
    const repoRoot = isCompiled ? path.resolve(here, '../../..') : path.resolve(here, '../..')
    const tsxBinPath = path.join(repoRoot, 'node_modules', '.bin', 'tsx')
    const sourceDaemonMainPath = path.join(repoRoot, 'core', 'entry', 'daemon-main.ts')
    const compiledDaemonMainPath = path.join(here, 'daemon-main.js')

    this.repoRoot = repoRoot
    this.tsxBinPath = tsxBinPath
    this.useTsxLauncher = !isCompiled && fs.existsSync(tsxBinPath) && fs.existsSync(sourceDaemonMainPath)
    this.daemonMainPath = this.useTsxLauncher ? sourceDaemonMainPath : compiledDaemonMainPath
    this.logFile = path.join(os.homedir(), '.cassicore', 'daemon.log')
  }


  /**
   * Start the supervisor.  Spawns the daemon and begins monitoring.
   * Resolves when the daemon sends its `ready` message.
   * Rejects if the daemon fails to start.
   */
  async start(): Promise<void> {
    this.stopping = false

    // Self-update: check if code in mnemic-field.db is newer than on-disk
    this.tryCodeExtraction()

    await this.spawnDaemon()
  }

  /**
   * Check the mnemic-field database for committed changesets containing
   * source_file engrams. If newer code exists, extract it, build it,
   * and swap in the new dist/ before the daemon starts.
   *
   * On failure, falls back to existing on-disk code — never blocks startup.
   */
  private tryCodeExtraction(): void {
    try {
      const { needsExtraction, latestCommit } = checkForUpdates()
      if (!needsExtraction || !latestCommit) return

      this.log('info', `Code store has uncommitted changes (latest: ${latestCommit}), attempting extraction`)

      const result = extractAndBuild(this.repoRoot)

      if (result.success) {
        this.log('info', `Code extraction succeeded: ${result.filesExtracted} files extracted in ${result.durationMs}ms`)
      } else {
        this.log('warn', `Code extraction failed: ${result.error}`)
        if (result.buildOutput) {
          this.log('warn', `Build output: ${result.buildOutput.slice(0, 500)}`)
        }
        this.log('info', 'Falling back to existing on-disk code')
      }
    } catch (err) {
      this.log('warn', `Code extraction check failed: ${String(err)}`)
      this.log('info', 'Falling back to existing on-disk code')
    }
  }

  /**
   * Gracefully stop the supervisor and the daemon.
   */
  async stop(signal?: string): Promise<void> {
    if (this.stopping) return
    this.stopping = true

    this.log('info', `Supervisor shutting down${signal ? ` (${signal})` : ''}`)

    // Cancel any pending restart
    if (this.restartTimer) {
      clearTimeout(this.restartTimer)
      this.restartTimer = null
    }

    // Stop heartbeat
    this.stopHeartbeat()

      // Send shutdown to daemon
      if (this.child && !this.child.killed) {
        if (this.useTsxLauncher) {
          try {
            this.child.send({ type: 'shutdown', reason: signal || 'supervisor-stop' })
          } catch {
            // IPC channel may already be closed
          }
        } else {
          try {
            this.child.kill('SIGTERM')
          } catch {
            // process may already be gone
          }
        }

      // Wait for graceful exit
      const exited = await Promise.race([
        new Promise<boolean>(res => {
          this.child!.once('exit', () => res(true))
        }),
        new Promise<boolean>(res =>
          setTimeout(() => res(false), this.config.shutdownTimeoutMs)
        ),
      ])

      if (!exited && this.child && !this.child.killed) {
        this.log('warn', 'Daemon did not exit gracefully — sending SIGKILL')
        this.child.kill('SIGKILL')
      }
    }

    this.child = null
    this.cleanupPidFile()
    process.exit(0)
  }


  /**
   * Clean up stale resources from a previous daemon instance.
   * After a SIGKILL, the Unix socket and port may still be held briefly.
   */
  private cleanupStaleResources(): void {
    const sockPath = path.join(os.homedir(), '.cassicore', 'admin.sock')
    try {
      if (fs.existsSync(sockPath)) {
        fs.unlinkSync(sockPath)
        this.log('info', 'Cleaned up stale Unix socket')
      }
    } catch {
      // Ignore — socket may be in use by a different process
    }
  }

  private spawnDaemon(): Promise<void> {
    // Clean up stale resources from previous crashed instance
    this.cleanupStaleResources()

    return new Promise((resolve, reject) => {
      this.daemonReady = false

      // Forward all args except supervisor-specific ones to daemon-main
      const daemonArgs = process.argv.slice(2)

      this.log('info', `Spawning daemon: ${this.daemonMainPath}`)

      // Version-based log rotation: archive daemon.log if version changed
      const buildId = getBuildIdentifier()
      const version = formatBuildId(buildId)
      rotateLogByVersion(this.logFile, version)

      const logFd = fs.openSync(this.logFile, 'a')

      if (this.useTsxLauncher) {
        this.child = fork(this.daemonMainPath, daemonArgs, {
          cwd: this.repoRoot,
          stdio: ['ignore', logFd, logFd, 'ipc'],
          env: { ...process.env },
          detached: false,
          execArgv: process.execArgv,
        })
      } else {
        this.child = spawn(process.execPath, [this.daemonMainPath, '--supervisor', ...daemonArgs], {
          cwd: this.repoRoot,
          stdio: ['ignore', 'pipe', logFd],
          env: { ...process.env },
          detached: false,
        })
      }

      fs.closeSync(logFd)

      const readyTimeout = setTimeout(() => {
        if (!this.daemonReady) {
          this.log('error', 'Daemon failed to become ready within 60s')
          this.child?.kill('SIGKILL')
          reject(new Error('Daemon ready timeout'))
        }
      }, 60_000)

      if (this.useTsxLauncher) {
        this.child.on('message', (msg: DaemonMessage) => {
          if (msg.type === 'ready') {
            this.handleReady(msg.pid, msg.admin, readyTimeout, resolve)
          }

          if (msg.type === 'heartbeat:pong') {
            this.lastPongTime = Date.now()
            this.lastHealth = msg.health
          }
        })
      } else {
        let stdoutBuffer = ''
        // Keep a rolling tail of the child's stdout so we can dump it if the
        // daemon dies before reporting ready (otherwise the cause is invisible).
        let stdoutTail = ''
        const STDOUT_TAIL_LIMIT = 8192
        this.child.stdout?.on('data', chunk => {
          const text = String(chunk)
          stdoutBuffer += text
          stdoutTail = (stdoutTail + text).slice(-STDOUT_TAIL_LIMIT)
          const lines = stdoutBuffer.split('\n')
          stdoutBuffer = lines.pop() ?? ''

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed) continue
            try {
              const msg = JSON.parse(trimmed) as { status?: string; pid?: number; admin?: unknown }
              if (msg.status === 'started') {
                this.handleReady(msg.pid, msg.admin, readyTimeout, resolve)
                return
              }
            } catch {
              // ignore non-JSON daemon stdout lines
            }
          }
        })
        // Expose for use in exit handler below
        ;(this as any)._lastChildStdoutTail = () => stdoutTail
      }

      this.child.on('error', (err) => {
        this.log('error', `Daemon process error: ${err.message}`)
        if (!this.daemonReady) {
          clearTimeout(readyTimeout)
          reject(err)
        }
      })

      this.child.on('exit', (code, signal) => {
        this.stopHeartbeat()

        if (this.stopping) {
          this.log('info', `Daemon exited (code=${code}, signal=${signal}) — supervisor stopping`)
          return
        }

        this.log('warn', `Daemon exited unexpectedly (code=${code}, signal=${signal})`)

        if (!this.daemonReady) {
          clearTimeout(readyTimeout)
          // Dump the child's recent stdout so the failure is diagnosable.
          // Otherwise this exit looks identical for every cause (port collision,
          // bad import, missing dep, etc.) and you have to add console.logs.
          const tailGetter = (this as any)._lastChildStdoutTail
          const tail = typeof tailGetter === 'function' ? String(tailGetter()) : ''
          if (tail) {
            this.log('error', `Daemon stdout tail (last ${tail.length} chars):\n${tail}`)
          } else {
            this.log('error', 'Daemon produced no stdout before exit')
          }
          reject(new Error(`Daemon exited before ready (code=${code})`))
          return
        }

        this.recordCrash()
        this.scheduleRestart()
      })
    })
  }

  private handleReady(
    daemonPid: number | undefined,
    admin: unknown,
    readyTimeout: ReturnType<typeof setTimeout>,
    resolve: () => void,
  ): void {
    this.daemonReady = true
    clearTimeout(readyTimeout)

    this.writePidFile()

    logger.info('Daemon ready', { pid: process.pid, daemonPid, admin })

    if (this.useTsxLauncher) {
      this.startHeartbeat()
    }

    this.consecutiveCrashes = 0
    resolve()
  }


  private startHeartbeat(): void {
    this.lastPongTime = Date.now()

    this.heartbeatTimer = setInterval(() => {
      if (!this.child || this.child.killed || this.stopping) return

      // Check if we've missed too many pongs
      const sincePong = Date.now() - this.lastPongTime
      if (sincePong > this.config.heartbeatTimeoutMs) {
        this.log('error', `Daemon heartbeat timeout (${sincePong}ms since last pong) — killing`)
        this.stopHeartbeat()
        this.child.kill('SIGKILL')
        return
      }

      // Send ping
      try {
        this.child.send({ type: 'heartbeat:ping', ts: Date.now() })
      } catch {
        // IPC channel closed — daemon likely exiting
      }
    }, this.config.heartbeatIntervalMs)

    this.heartbeatTimer.unref()
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }


  private recordCrash(): void {
    const now = Date.now()
    this.crashTimestamps.push(now)
    this.consecutiveCrashes++

    // Prune timestamps outside the window
    const windowStart = now - this.config.crashWindowMs
    this.crashTimestamps = this.crashTimestamps.filter(t => t >= windowStart)

    if (this.crashTimestamps.length >= this.config.maxCrashesPerWindow) {
      this.circuitOpen = true
      this.log('error',
        `Circuit breaker OPEN — ${this.crashTimestamps.length} crashes in ` +
        `${Math.round(this.config.crashWindowMs / 1000)}s window. Stopping restarts.`
      )
    }
  }

  private scheduleRestart(): void {
    if (this.stopping) return

    if (this.circuitOpen) {
      this.log('error', 'Circuit breaker is open — not restarting. Supervisor exiting with code 2.')
      this.cleanupPidFile()
      process.exit(2)
    }

    const delay = Math.min(
      this.config.baseRestartDelayMs * Math.pow(2, this.consecutiveCrashes - 1),
      this.config.maxRestartDelayMs,
    )

    this.log('info', `Scheduling daemon restart in ${delay}ms (crash #${this.consecutiveCrashes})`)

    this.restartTimer = setTimeout(async () => {
      this.restartTimer = null
      try {
        await this.spawnDaemon()
      } catch (err) {
        const msg = String(err)
        this.log('error', `Failed to restart daemon: ${msg}`)
        this.recordCrash()

        // If daemon exited before ready, give extra time for resource cleanup
        // (stale ports, Unix sockets, DB locks from SIGKILL'd process)
        if (msg.includes('exited before ready')) {
          this.log('info', 'Adding 3s cleanup grace period before next restart attempt')
          await new Promise(resolve => setTimeout(resolve, 3000))
        }

        this.scheduleRestart()
      }
    }, delay)
  }


  private writePidFile(): void {
    const pidDir = path.join(os.homedir(), '.cassicore')
    fs.mkdirSync(pidDir, { recursive: true })
    fs.writeFileSync(path.join(pidDir, 'daemon.pid'), String(process.pid))
  }

  private cleanupPidFile(): void {
    try {
      fs.unlinkSync(path.join(os.homedir(), '.cassicore', 'daemon.pid'))
    } catch {
      // Already removed or never written
    }
  }


  private log(level: 'info' | 'warn' | 'error', message: string): void {
    const ts = new Date().toISOString()
    const prefix = level === 'error' ? '● ERROR' : level === 'warn' ? '▵ WARN ' : '▸ INFO '
    const line = `${ts} ${prefix} supervisor  ${message}\n`
    try {
      fs.appendFileSync(this.logFile, line)
    } catch {
      // Fallback to stderr if log file is inaccessible
      process.stderr.write(line)
    }
  }
}
