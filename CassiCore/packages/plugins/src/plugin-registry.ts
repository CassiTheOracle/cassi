/**
 * Plugin Registry — Server-side lifecycle management for CassiCore plugins.
 *
 * Handles plugin registration, capability negotiation, heartbeat monitoring,
 * and cleanup. Plugins register via the admin API and receive an API key
 * for authenticating subsequent requests.
 *
 * The registry is transport-agnostic — it doesn't care whether the plugin
 * connects via HTTP, WebSocket, Unix socket, or worker thread. Transport
 * adapters handle the wire protocol; the registry manages identity and state.
 */

import { randomUUID } from 'node:crypto'
import type { ILogger } from '../../types/interfaces.js'
import type {
  PluginManifest,
  PluginRegistration,
  PluginCapability,
  PluginStatus,
} from '../../types/plugin.js'

const HEARTBEAT_TIMEOUT_MS = 5 * 60_000
const CLEANUP_INTERVAL_MS = 60_000

/**
 * All capabilities that CassiCore currently supports.
 * Requested capabilities not in this set are silently dropped
 * during registration (forward-compatible).
 */
const SUPPORTED_CAPABILITIES = new Set<PluginCapability>([
  'session',
  'events',
  'context',
  'pressure',
  'chunks',
  'memory',
  'tools',
  'intelligence',
  'training',
])

export class PluginRegistry {
  private plugins = new Map<string, PluginRegistration>()
  private apiKeyIndex = new Map<string, string>()
  private cleanupTimer: ReturnType<typeof setInterval> | null = null
  private logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child('plugin-registry')
    this.cleanupTimer = setInterval(() => this.expireStale(), CLEANUP_INTERVAL_MS)
  }

  /**
   * Register a new plugin or re-register an existing one.
   * Returns the registration (including the API key for auth).
   */
  register(manifest: PluginManifest): PluginRegistration {
    const existing = this.plugins.get(manifest.id)
    if (existing) {
      this.logger.info('Re-registering plugin', { pluginId: manifest.id, version: manifest.version })
      if (existing.apiKey) {
        this.apiKeyIndex.delete(existing.apiKey)
      }
    }

    const granted = manifest.capabilities.filter(c => SUPPORTED_CAPABILITIES.has(c))
    const dropped = manifest.capabilities.filter(c => !SUPPORTED_CAPABILITIES.has(c))

    if (dropped.length > 0) {
      this.logger.info('Dropped unsupported capabilities', { pluginId: manifest.id, dropped })
    }

    const apiKey = `cpk_${randomUUID().replace(/-/g, '')}`

    const registration: PluginRegistration = {
      manifest,
      status: 'connected',
      connectedAt: Date.now(),
      lastHeartbeat: Date.now(),
      grantedCapabilities: granted,
      apiKey,
    }

    this.plugins.set(manifest.id, registration)
    this.apiKeyIndex.set(apiKey, manifest.id)

    this.logger.info('Plugin registered', {
      pluginId: manifest.id,
      name: manifest.name,
      version: manifest.version,
      transport: manifest.transport,
      capabilities: granted,
    })

    return registration
  }

  /** Unregister a plugin and invalidate its API key */
  unregister(pluginId: string): boolean {
    const reg = this.plugins.get(pluginId)
    if (!reg) return false

    this.apiKeyIndex.delete(reg.apiKey)
    this.plugins.delete(pluginId)

    this.logger.info('Plugin unregistered', { pluginId })
    return true
  }

  /** Look up a plugin by API key (for request authentication) */
  authenticate(apiKey: string): PluginRegistration | null {
    const pluginId = this.apiKeyIndex.get(apiKey)
    if (!pluginId) return null

    const reg = this.plugins.get(pluginId)
    if (!reg) {
      this.apiKeyIndex.delete(apiKey)
      return null
    }

    return reg
  }

  /** Check if a plugin has a specific capability */
  hasCapability(pluginId: string, capability: PluginCapability): boolean {
    const reg = this.plugins.get(pluginId)
    if (!reg) return false
    return reg.grantedCapabilities.includes(capability)
  }

  /** Record a heartbeat from a plugin */
  heartbeat(pluginId: string): void {
    const reg = this.plugins.get(pluginId)
    if (reg) {
      reg.lastHeartbeat = Date.now()
      if (reg.status === 'disconnected') {
        reg.status = 'connected'
        reg.connectedAt = Date.now()
        this.logger.info('Plugin reconnected', { pluginId })
      }
    }
  }

  /** Update a plugin's status */
  setStatus(pluginId: string, status: PluginStatus): void {
    const reg = this.plugins.get(pluginId)
    if (reg) {
      reg.status = status
    }
  }

  /** Get a single plugin registration */
  get(pluginId: string): PluginRegistration | null {
    return this.plugins.get(pluginId) ?? null
  }

  /** List all registered plugins */
  list(): PluginRegistration[] {
    return Array.from(this.plugins.values())
  }

  /** List plugins that have a specific capability */
  withCapability(capability: PluginCapability): PluginRegistration[] {
    return this.list().filter(p =>
      p.status === 'connected' && p.grantedCapabilities.includes(capability)
    )
  }

  /** Mark stale plugins as disconnected */
  private expireStale(): void {
    const now = Date.now()
    for (const [id, reg] of this.plugins) {
      if (
        reg.status === 'connected' &&
        reg.lastHeartbeat &&
        now - reg.lastHeartbeat > HEARTBEAT_TIMEOUT_MS
      ) {
        reg.status = 'disconnected'
        this.logger.info('Plugin heartbeat expired', {
          pluginId: id,
          lastHeartbeat: new Date(reg.lastHeartbeat).toISOString(),
        })
      }
    }
  }

  /** Shut down the registry and clean up timers */
  destroy(): void {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer)
      this.cleanupTimer = null
    }
    this.plugins.clear()
    this.apiKeyIndex.clear()
  }
}
