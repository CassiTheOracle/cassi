import type { ToolDefinition, ToolHandler } from '../types.js'
import type { IMemory } from "@cassicore/foundation"
import type { ISessionManager } from "@cassicore/foundation"

export interface SystemHealthDeps {
  daemon?: any
  sessionManager?: ISessionManager
  memory?: IMemory
}

export const systemHealthDefinition: ToolDefinition = {
  name: 'system_health',
  description: 'Get comprehensive system health status including daemon health, provider status, active sessions, and team orchestrator status. Aggregates data from health monitor, provider registry, session manager, and team orchestrator.',
  parameters: {
    type: 'object',
    properties: {
      includeProviders: {
        type: 'boolean',
        default: true,
        description: 'Enhance health monitoring, extended-data with account-level details.',
      },
      includeSessions: {
        type: 'boolean',
        default: true,
        description: 'Include active session count and recent session details.',
      },
      includeTeams: {
        type: 'boolean',
        default: true,
        description: 'Include team orchestrator status and active team count.',
      },
      includeMemory: {
        type: 'boolean',
        default: true,
        description: 'Include memory module status and statistics.',
      },
      includePlugins: {
        type: 'boolean',
        default: true,
        description: 'Include plugin health status (circuit breakers, crashed plugins).',
      },
      sessionLimit: {
        type: 'number',
        default: 10,
        description: 'Maximum number of recent sessions to return (max: 50).',
      },
    },
    required: [],
  },
  timeoutMs: 20000,
  requiredPermission: 'read-only',
}

export function makeSystemHealthHandler(deps: SystemHealthDeps): ToolHandler {
  return async (input: any, _ctx: any) => {
    const params = input as {
      includeProviders?: boolean
      includeSessions?: boolean
      includeTeams?: boolean
      includeMemory?: boolean
      includePlugins?: boolean
      sessionLimit?: number
    }

    const response: any = {
      timestamp: new Date().toISOString(),
    }

    const daemon = deps.daemon

    // Daemon health
    if (daemon) {
      try {
        const healthMonitor = daemon.healthMonitor
        if (healthMonitor) {
          const health = await healthMonitor.getHealth()
          response.daemon = {
            status: health.status || 'unknown',
            version: health.version || 'unknown',
            pid: process.pid,
            uptimeMs: process.uptime() * 1000,
            memoryMb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024 * 100) / 100,
            eventLoopLagMs: health.eventLoopLagMs || 0,
          }
        } else {
          response.daemon = {
            status: 'unknown',
            version: 'unknown',
            pid: process.pid,
            uptimeMs: process.uptime() * 1000,
            memoryMb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024 * 100) / 100,
          }
        }
      } catch (err) {
        response.daemon = {
          status: 'error',
          error: 'Failed to get daemon health',
        }
      }
    } else {
      response.daemon = {
        status: 'unavailable',
        error: 'Daemon reference not available',
      }
    }

    // Provider health
    if (params.includeProviders !== false && daemon) {
      try {
        const providerRegistry = daemon.providerRegistry
        if (providerRegistry) {
          const providers = providerRegistry.listProviders()
          response.providers = providers.map((p: any) => {
            const providerHealth = providerRegistry.getProviderHealth?.(p.id)
            return {
              id: p.id,
              status: providerHealth?.status || p.status || 'unknown',
              models: p.models || [],
              accounts: providerHealth?.accounts || [],
            }
          })
        }
      } catch (err) {
        response.providers = { error: 'Failed to get provider health' }
      }
    }

    // Sessions
    if (params.includeSessions !== false) {
      try {
        const sessionManager = deps.sessionManager
        if (sessionManager) {
          const sessions = sessionManager.list()
          const limit = Math.min(params.sessionLimit || 10, 50)
          const recent = sessions
            .sort((a: any, b: any) => new Date(b.lastActiveAt).getTime() - new Date(a.lastActiveAt).getTime())
            .slice(0, limit)
            .map((s: any) => ({
              id: s.id,
              channelId: s.channelId,
              lastActiveAt: s.lastActiveAt.toISOString(),
              historyLength: s.history?.length || 0,
              tokenCount: s.tokenCount || 0,
            }))

          response.sessions = {
            total: sessions.length,
            active: sessions.filter((s: any) => s.status === 'active').length,
            recent,
          }
        } else {
          response.sessions = { error: 'Session manager not available' }
        }
      } catch (err) {
        response.sessions = { error: 'Failed to get sessions' }
      }
    }

    // REMOVED: Teams section — deprecated TriadTeam orchestrator deleted
    // Constellation/Helix orchestration status is available via their own APIs
    response.teams = { total: 0, active: 0, running: 0, completed: 0, failed: 0, recent: [], note: 'TriadTeam deprecated - use constellation status' }

    // Memory
    if (params.includeMemory !== false) {
      try {
        const memory = deps.memory
        if (memory) {
          // Try to get memory stats - method name may vary
          const stats = (memory as any).getStats?.() || (memory as any).stats || {}
          response.memory = {
            totalEntries: stats.totalEntries || 0,
            entriesByType: stats.entriesByType || {},
            oldestEntry: stats.oldestEntry,
            newestEntry: stats.newestEntry,
          }
        } else {
          response.memory = { error: 'Memory module not available' }
        }
      } catch (err) {
        response.memory = { error: 'Failed to get memory stats' }
      }
    }

    // Plugins
    if (params.includePlugins !== false && daemon) {
      try {
        const pluginManager = daemon.pluginManager
        if (pluginManager) {
          const plugins = pluginManager.listPlugins?.() || []
          const healthy = plugins.filter((p: any) => p.status === 'healthy').length
          const crashed = plugins.filter((p: any) => p.status === 'crashed').length
          const stopped = plugins.filter((p: any) => p.status === 'stopped').length
          const circuitOpen = plugins.filter((p: any) => p.circuitOpen).length

          response.plugins = {
            total: plugins.length,
            healthy,
            crashed,
            stopped,
            circuitOpen,
            degraded: plugins.filter((p: any) => p.status !== 'healthy' && p.status !== 'crashed').map((p: any) => p.id),
            details: plugins.map((p: any) => ({
              id: p.id,
              status: p.status,
              circuitOpen: p.circuitOpen || false,
              lastError: p.lastError,
            })),
          }
        } else {
          response.plugins = { error: 'Plugin manager not available' }
        }
      } catch (err) {
        response.plugins = { error: 'Failed to get plugin status' }
      }
    }

    // Overall status
    const daemonStatus = response.daemon?.status
    const hasDegradedProviders = Array.isArray(response.providers) && response.providers.some((p: any) => p.status === 'degraded' || p.status === 'down')
    const hasCrashedPlugins = response.plugins?.crashed > 0

    if (daemonStatus === 'error' || daemonStatus === 'unavailable') {
      response.overall = 'critical'
    } else if (hasCrashedPlugins || hasDegradedProviders || daemonStatus === 'degraded') {
      response.overall = 'degraded'
    } else {
      response.overall = 'healthy'
    }

    return JSON.stringify(response, null, 2)
  }
}
