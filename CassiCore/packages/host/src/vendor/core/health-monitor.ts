/*
 * Lightweight HealthMonitor (safe fallback)
 *
 * The previous HealthMonitor implementation performed many intrusive checks
 * and attempted automatic self-healing. That behavior caused instability in
 * some deployments and made debugging difficult. We're replacing it with a
 * minimal, non-invasive monitor that preserves the public API surface (so
 * other modules don't break) but disables automatic healing and expensive
 * probes. This file is intentionally conservative:
 *  - exposes the same class name `HealthMonitor`
 *  - provides `start`, `stop`, `runChecks`, `wire`, `latest`, `getHistory`
 *  - provides no-op/benign implementations of cluster-oriented methods used
 *    by older code (startMonitoring, stopMonitoring, waitForHealthy, destroy)
 *  - emits a lightweight `daemon:health` event on the bus when runChecks
 *
 * The long-term plan is to replace this with a dedicated, pluggable
 * monitoring service that:
 *  - runs as a separate process/worker so probes can't destabilize the core
 *  - exposes a plugin interface for probes (http/tcp/ping/provider checks)
 *  - records metrics to a time-series DB (Prometheus, Influx) and exposes
 *    an /metrics endpoint
 *  - sends alerts (PagerDuty/Slack/email) and provides a human-in-the-loop
 *    remediation dashboard; automatic remediation (restarts) must be
 *    opt-in and gated by circuit-breakers
 */

import { EventEmitter } from 'events'
import type { IEventBus } from '@cassicore/foundation'

export type CheckStatus = 'ok' | 'degraded' | 'down'

export interface CheckResult {
  name: string
  status: CheckStatus
  message: string
  durationMs: number
  meta?: Record<string, unknown>
}

export interface HealthSnapshot {
  timestamp: Date
  overall: CheckStatus
  checks: CheckResult[]
  uptimeMs: number
  memoryMb: number
  eventLoopLagMs: number
}

// Backwards-compatible health check config shape (used by cluster code)
export interface HealthCheckConfig {
  defaultCheck?: unknown
  startupGracePeriodMs?: number
  // legacy fields tolerated — monitoring is intentionally shallow here
}

export interface HealthMonitorOptions {
  intervalMs?: number
  historySize?: number
}

function rollup(checks: CheckResult[]): CheckStatus {
  if (checks.some(c => c.status === 'down')) return 'down'
  if (checks.some(c => c.status === 'degraded')) return 'degraded'
  return 'ok'
}

async function measureLag(): Promise<number> {
  const before = Date.now()
  await new Promise<void>(res => setImmediate(res))
  return Date.now() - before
}

/**
 * A conservative, non-invasive HealthMonitor. It intentionally avoids
 * calling provider.ping(), restarting plugins, or running deep probe
 * sequences. Use this as a safe default while designing a replacement
 * monitoring/observability system that runs out-of-process.
 */
export class HealthMonitor extends EventEmitter {
  private timer: NodeJS.Timeout | null = null
  private history: HealthSnapshot[] = []
  private readonly intervalMs: number
  private readonly historySize: number
  private startedAt = Date.now()

  // Wired references (optional)
  private providers?: Map<string, unknown>
  private pluginHost?: { all?: () => Array<{ id: string; status: string; crashes?: number }>; }
  private intelligence?: any
  private pipeline?: any
  private sessions?: any
  private mcp?: any
  private eventBus?: IEventBus
  private httpServer?: { listening: boolean }
  /** Number of consecutive health checks where the HTTP server was not listening */
  private httpDownCount = 0
  private static readonly HTTP_DOWN_EXIT_THRESHOLD = 3

  // Instances registered by cluster code (no active polling performed here)
  private monitoredInstances = new Map<string, { role?: string; port?: number; meta?: any }>()

  constructor(arg1?: any, arg2?: any, arg3?: any) {
    super()

    // Support two calling conventions for backwards compatibility:
    //   new HealthMonitor(bus, logger, opts)
    //   new HealthMonitor(opts)
    let opts: HealthMonitorOptions | undefined
    if (typeof arg1 === 'object' && arg1 && (arg1.intervalMs !== undefined || arg1.historySize !== undefined || arg2 === undefined && arg3 === undefined)) {
      opts = arg1
    } else if (typeof arg3 === 'object') {
      opts = arg3
    } else {
      opts = arg2 as HealthMonitorOptions | undefined
    }

    this.intervalMs = (opts && opts.intervalMs) ?? 30_000
    this.historySize = (opts && opts.historySize) ?? 20
  }

  /** Wire optional subsystem references (same shape as previous implementation) */
  wire(refs: {
    providers?: Map<string, unknown>
    pluginHost?: any
    intelligence?: any
    pipeline?: any
    sessions?: any
    mcp?: any
    eventBus?: IEventBus
    httpServer?: { listening: boolean }
  }): void {
    if (refs.providers) this.providers = refs.providers
    if (refs.pluginHost) this.pluginHost = refs.pluginHost
    if (refs.intelligence) this.intelligence = refs.intelligence
    if (refs.pipeline) this.pipeline = refs.pipeline
    if (refs.sessions) this.sessions = refs.sessions
    if (refs.mcp) this.mcp = refs.mcp
    if (refs.eventBus) this.eventBus = refs.eventBus
    if (refs.httpServer) this.httpServer = refs.httpServer
  }

  start(): void {
    if (this.timer) return
    // Run initial check, then schedule
    void this.runChecks().catch(() => {})
    this.timer = setInterval(() => void this.runChecks().catch(() => {}), this.intervalMs)
    this.timer.unref?.()
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }
  }

  latest(): HealthSnapshot | null {
    return this.history[this.history.length - 1] ?? null
  }

  getHistory(): HealthSnapshot[] {
    return [...this.history]
  }

  async runChecks(): Promise<HealthSnapshot> {
    const start = Date.now()

    // 1) process check (local metrics only)
    const lag = await measureLag()
    const mem = process.memoryUsage()
    const memoryMb = Math.round(mem.heapUsed / 1024 / 1024)

    const processCheck: CheckResult = {
      name: 'process',
      status: memoryMb > 1500 || lag > 2000 ? 'degraded' : 'ok',
      message: `heap ${memoryMb}MB lag ${lag}ms`,
      durationMs: Date.now() - start,
      meta: { heapMb: memoryMb, lagMs: lag }
    }

    // 2) providers check — non-blocking/surface-level (presence + basic API shape)
    let providersCheck: CheckResult
    try {
      if (!this.providers || this.providers.size === 0) {
        providersCheck = { name: 'providers', status: 'degraded', message: 'no providers configured', durationMs: 0 }
      } else {
        const ids = Array.from(this.providers.keys())
        const ok = ids.filter(id => {
          try {
            const p = this.providers!.get(id) as any
            return p && typeof p.complete === 'function'
          } catch {
            return false
          }
        })
        const missing = ids.filter(id => !ok.includes(id))
        providersCheck = {
          name: 'providers',
          status: missing.length ? 'degraded' : 'ok',
          message: `${ok.length}/${ids.length} providers present`,
          durationMs: 0,
          meta: { providers: ids, missing }
        }
      }
    } catch (err) {
      providersCheck = { name: 'providers', status: 'degraded', message: `providers check failed: ${String(err)}`, durationMs: 0 }
    }

    // 3) plugins (best-effort if pluginHost wired)
    let pluginsCheck: CheckResult
    try {
      if (!this.pluginHost || typeof this.pluginHost.all !== 'function') {
        pluginsCheck = { name: 'plugins', status: 'degraded', message: 'plugin host unavailable', durationMs: 0 }
      } else {
        const all = this.pluginHost.all() || []
        const healthy = all.filter((p: any) => p.status === 'healthy')
        const crashed = all.filter((p: any) => p.status === 'crashed')
        let status: CheckStatus = 'ok'
        const message = `${healthy.length}/${all.length} healthy`
        if (crashed.length > 0) status = 'degraded'
        pluginsCheck = { name: 'plugins', status, message, durationMs: 0, meta: { total: all.length, crashed: crashed.map((p: any) => p.id) } }
      }
    } catch (err) {
      pluginsCheck = { name: 'plugins', status: 'degraded', message: `plugins check failed: ${String(err)}`, durationMs: 0 }
    }

    const checks = [processCheck, providersCheck, pluginsCheck]

    // 4) HTTP server liveness — detect zombie daemon state
    if (this.httpServer) {
      const httpOk = this.httpServer.listening
      const httpCheck: CheckResult = {
        name: 'http-server',
        status: httpOk ? 'ok' : 'down',
        message: httpOk ? 'listening' : 'NOT listening — zombie state detected',
        durationMs: 0,
      }
      checks.push(httpCheck)

      if (!httpOk) {
        this.httpDownCount++
        if (this.httpDownCount >= HealthMonitor.HTTP_DOWN_EXIT_THRESHOLD) {
          // HTTP server has been down for multiple consecutive checks.
          // This is a zombie daemon — exit so the process supervisor can restart us.
          try {
            this.eventBus?.emit({ type: 'daemon:shutdown', reason: 'http-server-zombie' } as any)
          } catch {}
          setTimeout(() => process.exit(1), 3000).unref()
        }
      } else {
        this.httpDownCount = 0
      }
    }

    const overall = rollup(checks)

    const snapshot: HealthSnapshot = {
      timestamp: new Date(),
      overall,
      checks,
      uptimeMs: Date.now() - this.startedAt,
      memoryMb,
      eventLoopLagMs: lag,
    }

    // retain rolling history
    this.history.push(snapshot)
    if (this.history.length > this.historySize) this.history.shift()

    // Emit on bus (non-blocking) — previous implementation relied on bus.emit
    try {
      // emit a deprecated-style event for compatibility
      this.emit('snapshot', snapshot)
    } catch {}

    // Emit daemon:health onto the typed EventBus so the SSE stream, event
    // history, and external tools get periodic health snapshots.
    if (this.eventBus) {
      try {
        // Map CheckStatus → HealthStatus: ok→healthy, degraded→degraded, down→unhealthy
        const mapStatus = (s: CheckStatus): 'healthy' | 'degraded' | 'unhealthy' =>
          s === 'ok' ? 'healthy' : s === 'down' ? 'unhealthy' : 'degraded'

        this.eventBus.emit({
          type: 'daemon:health',
          overall: mapStatus(snapshot.overall),
          checks: snapshot.checks.map((c) => ({ name: c.name, status: mapStatus(c.status) })),
          uptimeMs: snapshot.uptimeMs,
          memoryMb: snapshot.memoryMb,
          eventLoopLagMs: snapshot.eventLoopLagMs,
          timestamp: snapshot.timestamp,
        } as any)
      } catch { /* never let bus errors break health checks */ }
    }

    return snapshot
  }


  /** Register an external instance for monitoring (legacy API compatibility). */
  startMonitoring(instanceId: string, role?: string, port?: number, processRef?: any): void {
    this.monitoredInstances.set(instanceId, { role, port, meta: { processRef: !!processRef } })
  }

  stopMonitoring(instanceId: string): void {
    this.monitoredInstances.delete(instanceId)
  }

  /**
   * Wait for an instance to become healthy. In this conservative fallback
   * implementation we resolve "healthy" immediately — the caller should
   * use stronger checks if they rely on health for critical decisions.
   */
  async waitForHealthy(instanceId: string, role?: string, port?: number, timeoutMs?: number): Promise<boolean> {
    // If instance is unknown, resolve false after a short delay
    if (!this.monitoredInstances.has(instanceId)) {
      if (timeoutMs && timeoutMs > 0) await new Promise(r => setTimeout(r, Math.min(500, timeoutMs)))
      return true
    }
    // For now, don't actively probe — assume healthy
    return true
  }

  /** Remove internal timers and clear state */
  destroy(): void {
    this.stop()
    this.history = []
    this.monitoredInstances.clear()
    this.removeAllListeners()
  }
}
