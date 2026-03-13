/**
 * plugin-host.ts — Manages plugin worker processes.
 *
 * Each plugin runs in its own child process (fork()), providing full OS-level
 * isolation.  A native-module segfault in one worker cannot crash the daemon
 * or affect other workers.
 *
 * The IPC protocol (HostMessage / WorkerMessage) is identical to the previous
 * worker_threads implementation — workers just import `workerPort` from
 * `core/worker-ipc.ts` instead of `parentPort` from `node:worker_threads`.
 */

import { fork, type ChildProcess } from 'node:child_process'

import { bus } from '../core/event-bus.js'

import type { IPluginHost, PluginManifest, PluginStatus, ILogger } from '../types/interfaces.js'

// ── IPC Protocol ────────────────────────────────────────────────────────────

/** Messages sent from daemon to worker */
type HostMessage =
  | { type: 'init'; config: Record<string, unknown> }
  | { type: 'config:update'; config: Record<string, unknown> }
  | { type: 'message'; payload: unknown }
  | { type: 'health:ping'; ts: number }
  | { type: 'shutdown'; restart?: boolean }

/** Messages sent from worker to daemon */
type WorkerMessage =
  | { type: 'ready' }
  | { type: 'message'; payload: unknown }
  | { type: 'error'; message: string }
  | { type: 'log'; level: string; message: string }
  | { type: 'signal'; payload: Record<string, unknown> }
  | { type: 'health:pong'; ts: number; metrics?: { memoryMb: number } }

// ── Internal Record ─────────────────────────────────────────────────────────

interface InternalWorkerRecord {
  manifest: PluginManifest
  child?: ChildProcess
  status: PluginStatus
  restartTimer?: NodeJS.Timeout

  // Health probe state
  healthTimer?: ReturnType<typeof setInterval>
  lastPongTime: number

  // Circuit breaker state
  crashTimestamps: number[]
  circuitOpen: boolean

  // Race condition guards
  handlingCrash: boolean
  restarting: boolean
  spawning: boolean
}

// ── PluginHost ──────────────────────────────────────────────────────────────

/**
 * PluginHost manages the lifecycle of plugin workers (one child process per plugin).
 */
export class PluginHost implements IPluginHost {
  private workers: Map<string, InternalWorkerRecord> = new Map()

  constructor(private logger: ILogger) {}

  /**
   * Load and start a plugin worker
   */
  async load(manifest: PluginManifest): Promise<void> {
    if (this.workers.has(manifest.id)) {
      this.logger.warn(`plugin ${manifest.id} already loaded`)
      return
    }

    const status: PluginStatus = {
      id: manifest.id,
      status: 'starting',
      crashes: 0,
      startedAt: new Date(),
    }

    const record: InternalWorkerRecord = {
      manifest,
      status,
      lastPongTime: 0,
      crashTimestamps: [],
      circuitOpen: false,
      handlingCrash: false,
      restarting: false,
      spawning: false,
    }
    this.workers.set(manifest.id, record)

    await this.spawnWorker(record)
  }

  // ── Spawn ───────────────────────────────────────────────────────────────

  private spawnWorker(record: InternalWorkerRecord): Promise<void> {
    return new Promise((resolve, reject) => {
      // Guard against concurrent spawn attempts
      if (record.spawning) {
        reject(new Error('spawn already in progress'))
        return
      }
      record.spawning = true

      const { manifest } = record
      this.logger.info(`spawning worker process for ${manifest.id}`, { entry: manifest.entryPoint })

      const child = fork(manifest.entryPoint, [], {
        stdio: ['pipe', 'pipe', 'pipe', 'ipc'],
        env: {
          ...process.env,
          CASSICORE_WORKER_ID: manifest.id,
        },
        serialization: 'json',
      })

      record.child = child

      const initMsg: HostMessage = { type: 'init', config: manifest.config ?? {} }

      let ready = false
      const readyTimeout = setTimeout(() => {
        if (!ready) {
          this.logger.error(`plugin ${manifest.id} failed to become ready in time`)
          record.spawning = false
          reject(new Error('ready timeout'))
        }
      }, 5_000)

      // Forward child stdout/stderr to daemon log
      child.stdout?.on('data', (chunk: Buffer) => {
        const lines = chunk.toString().trim()
        if (lines) {
          for (const line of lines.split('\n')) {
            this.logger.debug(`[${manifest.id}:stdout] ${line}`)
          }
        }
      })
      child.stderr?.on('data', (chunk: Buffer) => {
        const lines = chunk.toString().trim()
        if (lines) {
          for (const line of lines.split('\n')) {
            this.logger.warn(`[${manifest.id}:stderr] ${line}`)
          }
        }
      })

      // Handle IPC messages from worker
      child.on('message', (m: WorkerMessage) => {
        if (m.type === 'ready') {
          ready = true
          clearTimeout(readyTimeout)
          record.status.status = 'healthy'
          record.status.startedAt = record.status.startedAt ?? new Date()
          this.logger.info(`plugin ${manifest.id} ready (pid ${child.pid})`)
          bus.emit({ type: 'plugin:loaded', pluginId: manifest.id })

          // Start health probes now that the worker is ready
          this.startHealthProbe(record)

          record.spawning = false
          resolve()
          return
        }

        if (m.type === 'message') {
          bus.emit({ type: 'worker:message', pluginId: manifest.id, payload: m.payload })
        }

        if (m.type === 'error') {
          const errorMsg = 'message' in m ? m.message : 'unknown error'
          this.logger.error(`worker ${manifest.id} error: ${errorMsg}`)
        }

        if (m.type === 'log') {
          bus.emit({ type: 'worker:message', pluginId: manifest.id, payload: m })
        }

        if (m.type === 'signal') {
          bus.emit({ type: 'worker:message', pluginId: manifest.id, payload: { type: 'signal', ...m.payload } })
        }

        if (m.type === 'health:pong') {
          record.lastPongTime = Date.now()
        }
      })

      child.on('error', (err) => {
        this.handleCrash(record, err instanceof Error ? err.message : String(err))
        // Fast-fail: if the worker hasn't signaled ready yet, reject immediately
        // instead of waiting for the full ready timeout to expire.
        if (!ready) {
          ready = true  // prevent timeout from also rejecting
          clearTimeout(readyTimeout)
          record.spawning = false
          reject(new Error(`worker crashed: ${err instanceof Error ? err.message : String(err)}`))
        }
      })

      child.on('exit', (code, signal) => {
        this.stopHealthProbe(record)

        if (code !== 0 && code !== null) {
          this.handleCrash(record, `exit code ${code}${signal ? ` (signal ${signal})` : ''}`)
        } else if (signal) {
          // Killed by signal (e.g. SIGKILL from us)
          if (!record.status.status.startsWith('stop')) {
            this.handleCrash(record, `killed by signal ${signal}`)
          }
        } else {
          // Graceful exit (code 0)
          record.status.status = 'stopped'
          this.logger.info(`worker ${manifest.id} exited gracefully`)
          bus.emit({ type: 'plugin:stopped', pluginId: manifest.id, reason: 'manual' })
        }

        // Fast-fail: if the worker exited before signaling ready, reject
        // immediately rather than waiting for the full timeout.
        if (!ready) {
          ready = true  // prevent timeout from also rejecting
          clearTimeout(readyTimeout)
          const reason = code !== 0
            ? `exit code ${code}${signal ? ` (signal ${signal})` : ''}`
            : signal ? `killed by ${signal}` : 'exited before ready'
          record.spawning = false
          reject(new Error(reason))
        }
      })

      // Send init message to start the worker
      try {
        child.send(initMsg)
      } catch (err) {
        clearTimeout(readyTimeout)
        record.spawning = false
        reject(err)
      }
    })
  }

  // ── Health Probes ─────────────────────────────────────────────────────

  private startHealthProbe(record: InternalWorkerRecord): void {
    const intervalMs = record.manifest.healthProbeIntervalMs ?? 10_000
    const timeoutMs = record.manifest.healthProbeTimeoutMs ?? 30_000

    record.lastPongTime = Date.now()

    record.healthTimer = setInterval(() => {
      if (!record.child || record.child.killed) return

      // Check for missed pongs
      const sincePong = Date.now() - record.lastPongTime
      if (sincePong > timeoutMs) {
        this.logger.error(
          `plugin ${record.manifest.id} health probe timeout (${sincePong}ms since last pong) — killing`
        )
        this.stopHealthProbe(record)
        record.child.kill('SIGKILL')
        return
      }

      // Send ping
      try {
        record.child.send({ type: 'health:ping', ts: Date.now() } as HostMessage)
      } catch {
        // IPC channel closed — worker is exiting
      }
    }, intervalMs)

    // Don't prevent the daemon from exiting
    record.healthTimer.unref()
  }

  private stopHealthProbe(record: InternalWorkerRecord): void {
    if (record.healthTimer) {
      clearInterval(record.healthTimer)
      record.healthTimer = undefined
    }
  }

  // ── Crash Handling & Circuit Breaker ──────────────────────────────────

  private handleCrash(record: InternalWorkerRecord, errorMsg: string): void {
    // Guard against double handleCrash() execution
    if (record.handlingCrash) {
      return
    }
    record.handlingCrash = true

    const { manifest } = record

    // Stop health probes for crashed worker
    this.stopHealthProbe(record)

    record.status.crashes += 1
    record.status.lastCrashAt = new Date()
    record.status.status = 'crashed'
    record.child = undefined

    this.logger.error(`plugin ${manifest.id} crashed: ${errorMsg}`, { crashes: record.status.crashes })
    bus.emit({
      type: 'plugin:crashed',
      pluginId: manifest.id,
      error: errorMsg,
      crashCount: record.status.crashes,
    })

    // Record crash timestamp for circuit breaker
    const now = Date.now()
    record.crashTimestamps.push(now)
    const windowMs = manifest.circuitBreakerWindowMs ?? 300_000 // 5 min default
    const maxInWindow = manifest.circuitBreakerMaxCrashes ?? 5
    record.crashTimestamps = record.crashTimestamps.filter(t => t >= now - windowMs)

    // Check circuit breaker
    if (record.crashTimestamps.length >= maxInWindow) {
      record.circuitOpen = true
      this.logger.error(
        `Circuit breaker OPEN for ${manifest.id} — ` +
        `${record.crashTimestamps.length} crashes in ${Math.round(windowMs / 1000)}s. Stopping restarts.`
      )
      record.status.status = 'stopped'
      record.handlingCrash = false
      bus.emit({
        type: 'plugin:circuit-open',
        pluginId: manifest.id,
        crashCount: record.crashTimestamps.length,
        windowMs,
      })
      bus.emit({ type: 'plugin:stopped', pluginId: manifest.id, reason: 'circuit-breaker' })
      return
    }

    // Attempt restart with exponential backoff
    const crashes = record.status.crashes
    if (manifest.restartOnCrash && crashes < manifest.maxRestarts) {
      const backoff = Math.min(1000 * Math.pow(2, crashes - 1), 30_000)
      this.logger.info(`scheduling restart for ${manifest.id} in ${backoff}ms`)
      
      // Clear any existing restart timer before scheduling a new one
      if (record.restartTimer) {
        clearTimeout(record.restartTimer)
        record.restartTimer = undefined
      }
      
      record.status.status = 'restarting'
      record.restarting = true
      record.restartTimer = setTimeout(() => {
        this.logger.info(`restarting plugin ${manifest.id} (attempt ${crashes + 1})`)
        record.restarting = false
        this.spawnWorker(record)
          .then(() => {
            bus.emit({ type: 'plugin:restarted', pluginId: manifest.id, attempt: crashes + 1 })
          })
          .catch((err) => {
            const errorInfo: Record<string, unknown> = {
            operation: 'plugin_restart',
            message: err instanceof Error ? err.message : String(err),
            pluginId: manifest.id,
          }
          if (err instanceof Error && err.stack) {
            errorInfo.stack = err.stack
          }
          this.logger.error(`failed to restart ${manifest.id}`, errorInfo)
            // Ensure status is consistent after failed restart
            if (record.status.status === 'restarting') {
              record.status.status = 'crashed'
            }
          })
          .finally(() => {
            record.handlingCrash = false
          })
      }, backoff)
    } else {
      this.logger.warn(`plugin ${manifest.id} reached max restarts or not configured to restart`)
      record.status.status = 'stopped'
      record.handlingCrash = false
      bus.emit({ type: 'plugin:stopped', pluginId: manifest.id, reason: 'max-restarts' })
    }
  }

  // ── Unload (graceful shutdown) ────────────────────────────────────────

  /**
   * Gracefully unload a plugin worker.
   * Sends shutdown message, waits for graceful exit, then escalates to SIGTERM/SIGKILL.
   * @param pluginId Worker plugin to unload
   * @param opts.restart If true, tells the worker this is a restart (not permanent shutdown)
   */
  async unload(pluginId: string, opts?: { restart?: boolean }): Promise<void> {
    const record = this.workers.get(pluginId)
    if (!record) return

    if (record.restartTimer) {
      clearTimeout(record.restartTimer)
      record.restartTimer = undefined
    }

    this.stopHealthProbe(record)

    if (!record.child) {
      this.workers.delete(pluginId)
      this.logger.info(`plugin ${pluginId} unloaded (was not active)`)
      return
    }

    const child = record.child
    record.child = undefined
    record.status.status = 'stopping'

    // Step 1: Send shutdown message over IPC (with optional restart hint)
    try {
      child.send({ type: 'shutdown', restart: opts?.restart } as HostMessage)
    } catch {
      this.logger.warn(`failed to send shutdown to ${pluginId}`)
    }

    // Step 2: Wait for graceful exit (5s)
    const exited = await Promise.race([
      new Promise<boolean>(res => child.once('exit', () => res(true))),
      new Promise<boolean>(res => setTimeout(() => res(false), 5000)),
    ])

    // Step 3: SIGTERM if still alive
    if (!exited && !child.killed) {
      this.logger.warn(`plugin ${pluginId} did not exit gracefully — sending SIGTERM`)
      child.kill('SIGTERM')

      await Promise.race([
        new Promise<void>(res => child.once('exit', () => res())),
        new Promise<void>(res => setTimeout(res, 3000)),
      ])
    }

    // Step 4: SIGKILL as last resort
    if (!child.killed) {
      this.logger.warn(`plugin ${pluginId} still alive — sending SIGKILL`)
      try { child.kill('SIGKILL') } catch { /* already dead */ }
    }

    this.workers.delete(pluginId)
    this.logger.info(`plugin ${pluginId} unloaded`)
  }

  // ── Restart ───────────────────────────────────────────────────────────

  /**
   * Restart a specific plugin
   */
  async restart(pluginId: string): Promise<void> {
    const record = this.workers.get(pluginId)
    if (!record) throw new Error('unknown plugin')

    await this.unload(pluginId)

    // Reset status
    record.status = {
      id: pluginId,
      status: 'starting',
      crashes: 0,
      startedAt: new Date(),
    }
    record.crashTimestamps = []
    record.circuitOpen = false
    record.handlingCrash = false
    record.restarting = false
    record.spawning = false
    this.workers.set(pluginId, record)

    await this.spawnWorker(record)
    bus.emit({ type: 'plugin:restarted', pluginId, attempt: 1 })
  }

  // ── Queries ───────────────────────────────────────────────────────────

  /** Get status for a specific plugin */
  status(pluginId: string) {
    const r = this.workers.get(pluginId)
    return r?.status
  }

  /** Get status for all loaded plugins */
  all() {
    return Array.from(this.workers.values()).map(r => r.status)
  }

  /**
   * Push a config update to a worker without restarting it
   */
  updateConfig(pluginId: string, config: Record<string, unknown>): void {
    const record = this.workers.get(pluginId)
    if (!record?.child || record.child.killed) {
      this.logger.warn(`cannot update config for ${pluginId}: worker not active`)
      return
    }

    try {
      record.child.send({ type: 'config:update', config } as HostMessage)
    } catch (e) {
      const errorInfo: Record<string, unknown> = {
      operation: 'config_update',
      message: e instanceof Error ? e.message : String(e),
      pluginId,
    }
    if (e instanceof Error && e.stack) {
      errorInfo.stack = e.stack
    }
    this.logger.error(`failed to send config update to ${pluginId}`, errorInfo)
    }
  }

  /**
   * Send a message to a specific plugin worker
   */
  send(pluginId: string, payload: unknown): void {
    const record = this.workers.get(pluginId)
    if (!record?.child || record.child.killed) {
      this.logger.warn(`cannot send to ${pluginId}: worker not active`)
      return
    }

    try {
      record.child.send({ type: 'message', payload } as HostMessage)
    } catch (e) {
      const errorInfo: Record<string, unknown> = {
      operation: 'send_message',
      message: e instanceof Error ? e.message : String(e),
      pluginId,
    }
    if (e instanceof Error && e.stack) {
      errorInfo.stack = e.stack
    }
    this.logger.error(`failed to send message to ${pluginId}`, errorInfo)
    }
  }

  /**
   * Gracefully shut down all workers.
   * @param opts.restart If true, workers are told this is a restart
   */
  async shutdown(opts?: { restart?: boolean }): Promise<void> {
    const ids = Array.from(this.workers.keys())
    await Promise.all(ids.map(id => this.unload(id, opts)))
  }
}
