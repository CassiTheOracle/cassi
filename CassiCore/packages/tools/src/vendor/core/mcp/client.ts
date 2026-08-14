/**
 * VENDOR RUNTIME STUB — `core/mcp/client.ts` (`MCPClient`).
 *
 * Signature-faithful stub for the client-side MCP client consumed by vybit.ts
 * (tools instantiate `MCPClient` when the vybit tool runs). Owned by
 * `@cassicore/mcp` (P6); re-pointed there. No `@modelcontextprotocol/sdk`
 * dependency is pulled here (the mcp package carries it).
 */
import type { MCPToolInfo, MCPServerConfig } from './types.js'
import type { ILogger } from '@cassicore/foundation'

/** A client that speaks to an external MCP server over stdio. */
export class MCPClient {
  private config: MCPServerConfig
  private logger: ILogger
  private _connected = false
  private _tools: MCPToolInfo[] = []

  constructor(config: MCPServerConfig, logger: ILogger) {
    this.config = config
    this.logger = logger
  }

  get id(): string {
    return this.config.id
  }

  get connected(): boolean {
    return this._connected
  }

  /** Connect to the MCP server. */
  async connect(): Promise<void> {
    this._connected = true
  }

  /** Fetch the tool list from the server. */
  async listTools(): Promise<MCPToolInfo[]> {
    return this._tools
  }

  /** Invoke a tool on the server and return the joined text result. */
  async callTool(_name: string, _input: Record<string, unknown>): Promise<string> {
    return ''
  }

  /** Disconnect from the MCP server. */
  async disconnect(): Promise<void> {
    this._connected = false
  }

  private assertConnected(): void {
    if (!this._connected) throw new Error(`MCP server ${this.config.id} not connected`)
  }
}
