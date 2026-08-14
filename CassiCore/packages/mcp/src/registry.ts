/**
 * MCPRegistry — manages the pool of MCP server connections.
 *
 * Responsibilities:
 *   - Spawn and connect all configured MCP servers at startup
 *   - Register each server's tools into CassiCore's ToolRegistry
 *   - Monitor for crashes and restart (with backoff)
 *   - Expose status for the health monitor
 *
 * Tool naming convention:
 *   <serverId>__<toolName>
 *   e.g. serena__find_symbol, gitnexus__query
 *
 * This prefix scheme avoids collisions and makes it obvious in logs
 * which MCP server handled a given tool call.
 */

import { MCPClient } from './client.js'

import type { MCPServerConfig, MCPServerStatus, MCPConnectionState } from './types.js'
import type { ILogger } from '@cassicore/foundation'
import type { ToolRegistry } from '@cassicore/tools'
import type { ToolDefinition, ToolParamSchema } from '@cassicore/tools'

interface ServerEntry {
  config:    MCPServerConfig
  client:    MCPClient
  state:     MCPConnectionState
  restarts:  number
  lastError?: string
  startedAt?: Date
  retryTimer?: ReturnType<typeof setTimeout>
}

export class MCPRegistry {
  private servers = new Map<string, ServerEntry>()

  constructor(
    private toolRegistry: ToolRegistry,
    private logger: ILogger,
  ) {}

  /** Connect all configured servers and register their tools */
  async start(configs: MCPServerConfig[]): Promise<void> {
    if (configs.length === 0) {
      this.logger.info('No MCP servers configured — skipping')
      return
    }

    this.logger.info(`Starting ${configs.length} MCP server(s)`)

    await Promise.allSettled(configs.map(cfg => this.startServer(cfg)))

    const ready   = [...this.servers.values()].filter(e => e.state === 'ready' || e.state === 'degraded').length
    const crashed = [...this.servers.values()].filter(e => e.state === 'crashed').length
    this.logger.info(`Startup complete — ${ready} ready, ${crashed} failed`)
  }

  /** Gracefully disconnect all servers */
  async stop(): Promise<void> {
    for (const entry of this.servers.values()) {
      if (entry.retryTimer) clearTimeout(entry.retryTimer)
      await entry.client.disconnect().catch(() => {})
      entry.state = 'stopped'
    }
    this.logger.info('All MCP servers stopped')
  }

  /** Status snapshot for the health monitor */
  status(): MCPServerStatus[] {
    return [...this.servers.values()].map(e => ({
      id:        e.config.id,
      state:     e.state,
      toolCount: e.client.tools.length,
      restarts:  e.restarts,
      lastError: e.lastError,
      startedAt: e.startedAt,
    }))
  }


  private async startServer(config: MCPServerConfig): Promise<void> {
    const client = new MCPClient(config, this.logger)

    const entry: ServerEntry = {
      config,
      client,
      state:    'starting',
      restarts: 0,
    }
    this.servers.set(config.id, entry)

    try {
      await client.connect()
      entry.state    = 'ready'
      entry.startedAt = new Date()

      // Discover tools and bridge into ToolRegistry
      const tools = await client.listTools()
      let registered = 0
      for (const t of tools) {
        try {
          this.registerToolBridge(config.id, client, t)
          registered++
        } catch (err) {
          this.logger.warn(`[mcp:${config.id}] Failed to register tool '${t.name}': ${String(err)}`)
          entry.state = 'degraded'
        }
      }

      if (registered < tools.length) {
        this.logger.warn(`[mcp:${config.id}] ${registered}/${tools.length} tools registered`)
      } else {
        this.logger.info(`[mcp:${config.id}] ${registered} tool(s) registered — state: ready`)
      }

    } catch (err) {
      entry.state     = 'crashed'
      entry.lastError = String(err)
      this.logger.warn(`[mcp:${config.id}] Failed to start: ${String(err)}`)
      this.scheduleRestart(entry)
    }
  }

  private registerToolBridge(serverId: string, client: MCPClient, tool: { name: string; description: string; inputSchema: Record<string, unknown> }): void {
    // Prefix tool name to avoid collisions
    const prefixedName = `${serverId}__${tool.name}`

    // Coerce the MCP input schema into our ToolParamSchema shape
    const schema = tool.inputSchema as Record<string, unknown>
    const params: ToolParamSchema = {
      type:       'object',
      properties: (schema.properties as ToolParamSchema['properties']) ?? {},
      required:   (schema.required as string[]) ?? [],
    }

    const definition: ToolDefinition = {
      name:        prefixedName,
      description: `[${serverId}] ${tool.description}`,
      parameters:  params,
      timeoutMs:   60_000,  // MCP tools can be slow (LSP startup, graph queries)
    }

    this.toolRegistry.register(definition, async (input, _ctx) => {
      // Check client is still connected
      if (!client.connected) {
        throw new Error(`MCP server '${serverId}' is not connected`)
      }
      this.logger.debug(`[mcp:${serverId}] Calling tool '${tool.name}'`)
      return client.callTool(tool.name, input)
    })
  }

  private scheduleRestart(entry: ServerEntry): void {
    const maxRestarts = entry.config.maxRestarts ?? 3
    if (!entry.config.restartOnCrash && entry.config.restartOnCrash !== undefined) return
    if (entry.restarts >= maxRestarts) {
      this.logger.warn(`[mcp:${entry.config.id}] Max restarts (${maxRestarts}) reached — giving up`)
      return
    }

    // Exponential backoff: 2s, 4s, 8s, ...
    const delayMs = Math.min(2_000 * Math.pow(2, entry.restarts), 30_000)
    entry.restarts++
    this.logger.info(`[mcp:${entry.config.id}] Scheduling restart #${entry.restarts} in ${delayMs}ms`)

    entry.retryTimer = setTimeout(async () => {
      this.logger.info(`[mcp:${entry.config.id}] Restarting...`)
      entry.state = 'starting'

      // Disconnect old client (best-effort) and create a fresh one
      await entry.client.disconnect().catch(() => {})
      entry.client = new MCPClient(entry.config, this.logger)

      try {
        await entry.client.connect()
        entry.state     = 'ready'
        entry.startedAt = new Date()
        entry.lastError = undefined

        const tools = await entry.client.listTools()
        for (const t of tools) {
          try { this.registerToolBridge(entry.config.id, entry.client, t) } catch { /* ignore dup */ }
        }
        this.logger.info(`[mcp:${entry.config.id}] Restarted successfully`)
      } catch (err) {
        entry.state     = 'crashed'
        entry.lastError = String(err)
        this.logger.warn(`[mcp:${entry.config.id}] Restart failed: ${String(err)}`)
        this.scheduleRestart(entry)
      }
    }, delayMs)
  }
}
