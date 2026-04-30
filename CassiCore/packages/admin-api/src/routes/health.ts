import type { ILogger } from '../../types/interfaces.js'
import type http from 'node:http'
import { CASSICORE_VERSION, CASSICORE_BUILD, CASSICORE_BUILD_STRING } from '../daemon.js'

export interface HealthRoutesDeps {
  daemon: any
  logger: ILogger
  sendJSON: (res: http.ServerResponse, code: number, obj: unknown) => void
}

export async function handleHealthRoutes(
  deps: HealthRoutesDeps,
  req: http.IncomingMessage,
  res: http.ServerResponse,
  method: string,
  pathname: string
): Promise<boolean> {
  const { daemon, sendJSON } = deps

  // GET /health
  if (method === 'GET' && pathname === '/health') {
    const monitor = daemon.healthMonitor
    const snapshot = monitor?.latest?.()

    // Check plugin health for degradation
    const pluginStatuses = daemon.pluginHost?.all?.() ?? []
    const criticalDown = pluginStatuses.some(
      (p: any) => p.circuitOpen && daemon.pluginHost?.status?.(p.id)
    )
    // Detect if any critical plugin is stopped or has circuit open
    const degradedPlugins = pluginStatuses.filter((p: any) =>
      (p.status === 'stopped' || p.status === 'crashed' || p.circuitOpen) &&
      p.id // Any stopped plugin indicates potential degradation
    )

    const pluginHealth = {
      total: pluginStatuses.length,
      healthy: pluginStatuses.filter((p: any) => p.status === 'healthy').length,
      crashed: pluginStatuses.filter((p: any) => p.status === 'crashed').length,
      stopped: pluginStatuses.filter((p: any) => p.status === 'stopped').length,
      circuitOpen: pluginStatuses.filter((p: any) => p.circuitOpen).length,
      degraded: degradedPlugins.map((p: any) => p.id),
    }

    if (snapshot) {
      // Override status to degraded if critical plugins are down
      const overall = degradedPlugins.length > 0 ? 'degraded' : snapshot.overall
      // Degraded means reduced functionality - clients should treat as unavailable (503)
      const httpCode = overall === 'ok' ? 200
        : overall === 'degraded' ? 503
        : 503
      sendJSON(res, httpCode, {
        status: overall,
        timestamp: snapshot.timestamp,
        uptimeMs: snapshot.uptimeMs,
        memoryMb: snapshot.memoryMb,
        eventLoopLagMs: snapshot.eventLoopLagMs,
        version: CASSICORE_VERSION,
        build: CASSICORE_BUILD_STRING,
        buildDetails: {
          version: CASSICORE_BUILD.version,
          gitRef: CASSICORE_BUILD.gitRef,
        },
        checks: snapshot.checks,
        plugins: pluginHealth,
      })
      return true
    }

    sendJSON(res, 200, {
      status: degradedPlugins.length > 0 ? 'degraded' : 'starting',
      uptime: process.uptime(),
      version: CASSICORE_VERSION,
      build: CASSICORE_BUILD_STRING,
      buildDetails: {
        version: CASSICORE_BUILD.version,
        gitRef: CASSICORE_BUILD.gitRef,
      },
      plugins: pluginHealth,
    })
    return true
  }

  // GET /health/history
  if (method === 'GET' && pathname === '/health/history') {
    const monitor = daemon.healthMonitor
    const history = monitor?.getHistory?.() ?? []
    sendJSON(res, 200, history)
    return true
  }

  // POST /health/check
  if (method === 'POST' && pathname === '/health/check') {
    const monitor = daemon.healthMonitor
    if (!monitor) {
      sendJSON(res, 503, { error: 'health monitor not initialised' })
      return true
    }
    const snapshot = await monitor.runChecks()
    sendJSON(res, snapshot.overall === 'down' ? 503 : 200, snapshot)
    return true
  }

  // GET /cassicore/info
  // Capability discovery endpoint for external CLI clients (e.g. the Crush fork).
  // Returns the daemon version, active intelligence modules, available tools, and
  // whether the bridge / turn-stream API is available.  Crush uses this on startup
  // to decide which UI panels to enable and which API surface to use.
  if (method === 'GET' && pathname === '/cassicore/info') {
    const intel = (daemon as any).intelligence ?? {}
    const tools = (daemon as any).toolRegistry ?? (daemon as any).tools ?? null
    const availableTools: string[] = []
    try {
      if (tools && typeof tools.list === 'function') {
        for (const t of tools.list()) availableTools.push(t.name ?? String(t))
      } else if (tools && typeof tools.getAll === 'function') {
        for (const t of tools.getAll()) availableTools.push(t.name ?? String(t))
      }
    } catch { /* best-effort */ }

    const modules: Record<string, boolean> = {
      memory: !!(intel.memory),
      continuity: !!(intel.continuity),
      recover: !!(intel.recover),
      reflect: !!(intel.reflect),
      thinker: !!(intel.thinker),
      // REMOVED: optimizer — OptimizerModule deleted
      dialectic: !!(intel.dialectic),
      multiAgent: false,
      ruleEnforcer: !!(intel.ruleEnforcer),
      subconscious: !!(intel.subconscious),
    }

    sendJSON(res, 200, {
      name: 'CassiCore',
      version: CASSICORE_VERSION,
      build: CASSICORE_BUILD_STRING,
      buildDetails: {
        version: CASSICORE_BUILD.version,
        gitRef: CASSICORE_BUILD.gitRef,
      },
      pid: process.pid,
      uptimeMs: Math.floor(process.uptime() * 1000),
      // API surface available for the Crush fork
      api: {
        turnStream: true,   // POST /sessions/:id/turn/stream (SSE, full intelligence)
        events: true,       // GET /events/stream (cognitive event bus over SSE)
        command: true,      // POST /sessions/:id/command (slash command routing)
        models: true,       // GET /models (CassiCore model routing)
        confirmations: false,
        bridge: false,      // bridge.ts is a raw provider passthrough — does NOT run intelligence
      },
      // Active intelligence modules — Crush uses this to decide which panels to show
      intelligence: modules,
      // Tools the daemon can execute
      tools: availableTools,
    })
    return true
  }

  // GET /health/providers
  if (method === 'GET' && pathname === '/health/providers') {
    const providerHealth: Array<{
      id: string
      status: 'ok' | 'degraded' | 'down'
      models: string[]
      accounts?: Array<{
        profileId: string
        status: 'ok' | 'degraded' | 'down'
        quotaStatus?: 'healthy' | 'low' | 'exhausted'
        tokenExpiry?: number
        tokenExpiresIn?: number
        error?: string
      }>
    }> = []

    const providers = (daemon as any).providers || new Map<string, any>()

    function unwrapProvider(p: any): any {
      return p?.wrapped || p
    }

    for (const [id, provider] of providers) {
      const health: any = {
        id,
        status: 'ok' as const,
        models: (provider as any).models || [],
      }

      const unwrapped = unwrapProvider(provider)
      if (id === 'qwen' && (unwrapped as any).accounts) {
        const lb = unwrapped as any
        health.accounts = []

        for (let i = 0; i < lb.accounts.length; i++) {
          const acc = lb.accounts[i]
          const stats = lb.stats?.[i]
          const accountHealth: any = {
            profileId: acc.profileId,
            status: stats?.cooldownUntil && Date.now() < stats.cooldownUntil ? 'degraded' : 'ok',
            tokenExpiry: acc.credentials?.expires,
            tokenExpiresIn: acc.credentials?.expires ? acc.credentials.expires - Date.now() : undefined,
          }

          if (acc.credentials?.expires && acc.credentials.expires < Date.now()) {
            accountHealth.status = 'down'
            accountHealth.error = 'Token expired'
          }

          try {
            const testProvider = lb.providers?.[i]
            if (testProvider) {
              const pingResult = await testProvider.ping()
              if (!pingResult) {
                accountHealth.status = 'degraded'
                accountHealth.quotaStatus = 'exhausted'
                accountHealth.error = 'Quota exceeded or service unavailable'
              } else {
                accountHealth.quotaStatus = 'healthy'
              }
            }
          } catch (err: any) {
            const errMsg = String(err?.message || err)
            if (errMsg.includes('quota') || errMsg.includes('429')) {
              accountHealth.quotaStatus = 'exhausted'
              accountHealth.status = 'degraded'
            } else if (errMsg.includes('auth') || errMsg.includes('token')) {
              accountHealth.status = 'down'
            }
            accountHealth.error = errMsg
          }

          health.accounts.push(accountHealth)
        }

        const allDown = health.accounts.every((a: any) => a.status === 'down')
        const anyOk = health.accounts.some((a: any) => a.status === 'ok')
        health.status = allDown ? 'down' : (anyOk ? 'ok' : 'degraded')
      }

      providerHealth.push(health)
    }

    sendJSON(res, 200, {
      timestamp: new Date().toISOString(),
      providers: providerHealth,
    })
    return true
  }

  // POST /restart — trigger a partial daemon restart
  if (method === 'POST' && pathname === '/restart') {
    const reason = (req as any).body?.reason ?? 'admin-api'

    // Start the restart asynchronously — we send the response before teardown
    sendJSON(res, 202, {
      status: 'restarting',
      reason,
      message: 'Daemon restart initiated. Subscribe to SSE /events/stream to monitor.',
    })

    // Allow the response to flush before tearing down subsystems
    setImmediate(() => {
      daemon.restart(reason).catch((err: unknown) => {
        deps.logger.error(`Restart failed: ${String(err)}`)
      })
    })
    return true
  }

  return false
}
