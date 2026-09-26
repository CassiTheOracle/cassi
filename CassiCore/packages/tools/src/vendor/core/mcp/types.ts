/**
 * VENDOR RUNTIME STUB — `core/mcp/types.ts`.
 *
 * Faithful type surface for the client-side MCP integration. Owned by
 * `@cassicore/mcp` (P6); re-pointed there. Consumed by vybit.ts (tools).
 */

/** Config entry for a single MCP server (stored in ~/.cassicore/config.json) */
export interface MCPServerConfig {
  /** Unique identifier — used as tool name prefix: `<id>__<tool>` */
  id: string
  /** Command to execute (e.g., "node" or "python") */
  command: string
  /** Human-readable description shown in logs */
  description?: string
  /** Arguments to pass to the command */
  args?: string[]
  /** Environment variables to set for the server process */
  env?: Record<string, string>
  /** Whether to auto-restart on crash. Default: true */
  restartOnCrash?: boolean
  /** Max restart attempts. Default: 3 */
  maxRestarts?: number
  /** Startup timeout in ms. Default: 15_000 */
  startupTimeoutMs?: number
}

/** Live connection state for a running MCP server */
export type MCPConnectionState =
  | 'starting'
  | 'ready'
  | 'degraded'   // connected but some tools failed to register
  | 'crashed'
  | 'stopped'

export interface MCPServerStatus {
  id: string
  state: MCPConnectionState
  toolCount: number
  restarts: number
  lastError?: string
  startedAt?: Date
}

/** A tool as reported by an MCP server's tools/list response */
export interface MCPToolInfo {
  name: string
  description: string
  inputSchema: Record<string, unknown>
}
