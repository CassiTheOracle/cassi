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
  totalLifetimeRestarts: number  // Global restart count (never resets)

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
      totalLifetimeRestarts: 0,
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
        execArgv: ['--max-old-space-size=256'],
        stdio: ['pipe', 'pipe', 'pipe', 'ipc'],
        env: {
          ...process.env,
          CASSICORE_WORKER_ID: manifest.id,
        },
        serialization: 'json',
      })

      record.child = child

      const initMsg: HostMessage = { type: 'init', config: manifest.config ?? {} }

      // Send init message so the worker knows it's time to start.
      // Workers wait for this before sending 'ready' back.
      child.send(initMsg)

      let ready = false
      const readyTimeout = setTimeout(() => {
        if (!ready) {
          ready = true
          this.logger.error(`plugin ${manifest.id} failed to become ready in time (5000ms)`)
          record.spawning = false
          reject(new Error(`Timed out waiting for worker "${manifest.id}" to be ready (5000ms)`))
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
          // Fast-fail: if the worker sends an error before ready, reject immediately
          if (!ready) {
            ready = true  // prevent timeout from also rejecting
            clearTimeout(readyTimeout)
            record.spawning = false
            reject(new Error(`Worker "${manifest.id}" reported error: ${errorMsg}`))
            return
          }
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
          reject(err)
          return
        }
      })

      child.on('exit', (code, signal) => {
        const reason = code !== null ? `code ${code}` : `signal ${signal}`
        this.logger.warn(`worker ${manifest.id} exited (${reason})`)

        // Fast-fail: if the worker exits before signaling ready, reject immediately
        // instead of waiting for the full ready timeout to expire.
        if (!ready) {
          ready = true  // prevent timeout from also rejecting
          clearTimeout(readyTimeout)
          record.spawning = false
          reject(new Error(`Worker "${manifest.id}" exited unexpectedly with ${reason}`))
          return
        }

        // Only handle as a crash if the worker was healthy (not during intentional restart)
        if (record.status.status === 'healthy' && !record.restarting) {
          this.handleCrash(record, `exited with ${reason}`)
        }
      })
    })
  }

  // ── Health Probes ─────────────────────────────────────────────────────────

  private startHealthProbe(record: InternalWorkerRecord): void {
    if (record.healthTimer) {
      clearInterval(record.healthTimer)
    }

    record.healthTimer = setInterval(() => {
      if (!record.child || !record.child.connected) {
        this.logger.warn(`health probe: worker ${record.manifest.id} not connected`)
        return
      }

      // Send ping
      const pingMsg: HostMessage = { type: 'health:ping', ts: Date.now() }
      record.child.send(pingMsg)

      // Check for timeout (no pong within 10 seconds)
      const lastPongAgo = Date.now() - record.lastPongTime
      if (record.lastPongTime > 0 && lastPongAgo > 10_000) {
        this.logger.warn(`health probe: worker ${record.manifest.id} unresponsive (${Math.round(lastPongAgo / 1000)}s)`)
        // Optionally trigger restart here if needed
      }
    }, 5_000)
  }

  private stopHealthProbe(record: InternalWorkerRecord): void {
    if (record.healthTimer) {
      clearInterval(record.healthTimer)
      record.healthTimer = undefined
    }
  }

  // ── Crash Handling & Circuit Breaker ─────────────────────────────────────

  /** Maximum total restarts across the entire daemon lifetime per worker */
  private static readonly MAX_LIFETIME_RESTARTS = 20

  private handleCrash(record: InternalWorkerRecord, reason: string): void {
    // Guard against concurrent crash handling
    if (record.handlingCrash) {
      return
    }
    record.handlingCrash = true

    const now = Date.now()
    record.status.crashes = (record.status.crashes ?? 0) + 1
    record.crashTimestamps.push(now)
    record.totalLifetimeRestarts++

    // Keep only crashes from the last 5 minutes
    const windowMs = record.manifest.circuitBreakerWindowMs ?? 5 * 60 * 1000
    record.crashTimestamps = record.crashTimestamps.filter((ts) => now - ts < windowMs)

    this.logger.error(`plugin ${record.manifest.id} crashed: ${reason}`, {
      crashes: record.status.crashes,
      recentCrashes: record.crashTimestamps.length,
      totalLifetimeRestarts: record.totalLifetimeRestarts,
    })

    // Emit plugin:crashed on every crash
    bus.emit({
      type: 'plugin:crashed',
      pluginId: record.manifest.id,
      error: reason,
      crashCount: record.status.crashes,
    })

    // Check manifest maxRestarts limit (0 = no restarts allowed)
    const maxRestarts = record.manifest.maxRestarts ?? Infinity
    if (!record.manifest.restartOnCrash || record.status.crashes > maxRestarts) {
      record.status.status = 'stopped'
      record.handlingCrash = false
      bus.emit({ type: 'plugin:stopped', pluginId: record.manifest.id, reason: 'max-restarts' })
      return
    }

    // Global lifetime restart limit: stop restarting workers that keep dying
    if (record.totalLifetimeRestarts >= PluginHost.MAX_LIFETIME_RESTARTS) {
      record.circuitOpen = true
      this.logger.error(
        `circuit breaker OPEN for ${record.manifest.id}: exceeded lifetime restart limit (${record.totalLifetimeRestarts}/${PluginHost.MAX_LIFETIME_RESTARTS})`,
      )
      record.status.status = 'crashed'
      record.handlingCrash = false
      bus.emit({ type: 'plugin:circuit-open', pluginId: record.manifest.id, crashCount: record.totalLifetimeRestarts, windowMs: 0 })
      bus.emit({ type: 'plugin:stopped', pluginId: record.manifest.id, reason: 'circuit-breaker' })
      return
    }

    // Circuit breaker: open if too many crashes within window
    const maxCrashes = record.manifest.circuitBreakerMaxCrashes ?? 3
    if (record.crashTimestamps.length >= maxCrashes) {
      record.circuitOpen = true
      this.logger.error(`circuit breaker OPEN for ${record.manifest.id}`)
      record.status.status = 'crashed'
      record.handlingCrash = false
      bus.emit({ type: 'plugin:circuit-open', pluginId: record.manifest.id, crashCount: record.crashTimestamps.length, windowMs })
      bus.emit({ type: 'plugin:stopped', pluginId: record.manifest.id, reason: 'circuit-breaker' })
      return
    }

    // Schedule restart with exponential backoff
    const delay = Math.min(1000 * Math.pow(2, record.crashTimestamps.length - 1), 30_000)
    this.logger.info(`scheduling restart in ${delay}ms`)

    // Set status eagerly so callers can observe restart state
    record.status.status = 'restarting'
    record.restarting = true

    record.restartTimer = setTimeout(() => {
      if (record.circuitOpen) {
        this.logger.warn(`restart cancelled: circuit breaker open`)
        record.restarting = false
        record.handlingCrash = false
        return
      }

      this.logger.info(`restarting worker ${record.manifest.id}`)
      record.status.status = 'starting'

      // Clean up old child process references
      if (record.child) {
        record.child.removeAllListeners()
        record.child = undefined
      }

      this.spawnWorker(record)
        .then(() => {
          record.restarting = false
          record.handlingCrash = false
        })
        .catch((err) => {
          this.logger.error(`restart failed: ${err.message}`)
          record.restarting = false
          record.handlingCrash = false
          // Re-trigger crash handling if restart spawn fails
          if (!record.circuitOpen) {
            this.handleCrash(record, 'restart failed: ' + err.message)
          }
        })
    }, delay)

    // handlingCrash stays true until restart completes (prevents double-crash counting)
  }

  // ── Message Passing ───────────────────────────────────────────────────────

  sendMessage(pluginId: string, payload: unknown): void {
    const record = this.workers.get(pluginId)
    if (!record || !record.child || !record.child.connected) {
      this.logger.warn(`cannot send message to ${pluginId}: not connected`)
      return
    }

    const msg: HostMessage = { type: 'message', payload }
    record.child.send(msg)
  }

  updateConfig(pluginId: string, config: Record<string, unknown>): void {
    const record = this.workers.get(pluginId)
    if (!record || !record.child || !record.child.connected) {
      this.logger.warn(`cannot update config for ${pluginId}: not connected`)
      return
    }

    const msg: HostMessage = { type: 'config:update', config }
    record.child.send(msg)
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  async unload(pluginId: string): Promise<void> {
    const record = this.workers.get(pluginId)
    if (!record) {
      this.logger.warn(`plugin ${pluginId} not loaded`)
      return
    }

    this.logger.info(`unloading plugin ${pluginId}`)

    // Stop health probes
    this.stopHealthProbe(record)

    // Cancel any pending restart
    if (record.restartTimer) {
      clearTimeout(record.restartTimer)
      record.restartTimer = undefined
    }

    // Send shutdown message
    if (record.child && record.child.connected) {
      const shutdownMsg: HostMessage = { type: 'shutdown' }
      record.child.send(shutdownMsg)

      // Give worker 5 seconds to shut down gracefully
      await new Promise<void>((resolve) => {
        const timeout = setTimeout(() => {
          this.logger.warn(`worker ${pluginId} did not shut down gracefully, killing`)
          resolve()
        }, 5_000)

        record.child!.once('exit', () => {
          clearTimeout(timeout)
          resolve()
        })
      })

      // Force kill if still running
      if (record.child && record.child.pid) {
        try {
          process.kill(record.child.pid, 'SIGKILL')
        } catch (err) {
          // Already dead
        }
      }
    }

    // Clean up
    record.child?.removeAllListeners()
    this.workers.delete(pluginId)

    bus.emit({ type: 'plugin:stopped', pluginId, reason: 'manual' })
  }

  async shutdown(): Promise<void> {
    this.logger.info('shutting down plugin host...')

    const unloadPromises = Array.from(this.workers.keys()).map((id) => this.unload(id))
    await Promise.all(unloadPromises)

    this.logger.info('plugin host shut down complete')
  }

  getPluginStatus(pluginId: string): PluginStatus | undefined {
    return this.workers.get(pluginId)?.status
  }

  getAllPluginStatuses(): PluginStatus[] {
    return Array.from(this.workers.values()).map((r) => r.status)
  }

  // IPluginHost interface aliases (kept for backward compatibility)
  /** @see getPluginStatus */
  status(pluginId: string): PluginStatus | undefined { return this.getPluginStatus(pluginId) }
  /** @see getAllPluginStatuses */
  all(): PluginStatus[] { return this.getAllPluginStatuses() }
  /** @see sendMessage */
  send(pluginId: string, payload: unknown): void { this.sendMessage(pluginId, payload) }

  /**
   * Restart a specific plugin
   */
  async restart(pluginId: string): Promise<void> {
    const record = this.workers.get(pluginId)
    if (!record) throw new Error(`unknown plugin: ${pluginId}`)

    await this.unload(pluginId)

    // Reset state
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
}
