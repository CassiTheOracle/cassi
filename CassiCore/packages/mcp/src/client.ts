/**
 * MCPClient — manages a single MCP server subprocess.
 *
 * Lifecycle:
 *   new MCPClient(config, logger)
 *   await client.connect()       → spawns the process, does initialize handshake
 *   await client.listTools()     → returns available tools
 *   await client.callTool(...)   → executes a tool
 *   await client.disconnect()    → kills the process cleanly
 *
 * Transport: stdio (JSON-RPC 2.0 over stdin/stdout).
 * The MCP SDK's StdioClientTransport handles the wire format.
 */

import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'

import type { MCPServerConfig, MCPToolInfo } from './types.js'
import type { ILogger } from '../../types/interfaces.js'
import { CASSICORE_VERSION } from '../daemon.js'

const CLIENT_NAME = 'CassiCore'

export class MCPClient {
  private client: Client
  private transport?: StdioClientTransport
  private _connected = false
  private _tools: MCPToolInfo[] = []

  constructor(
    private config: MCPServerConfig,
    private logger: ILogger,
  ) {
    this.client = new Client({ name: CLIENT_NAME, version: CASSICORE_VERSION })
  }

  get id(): string { return this.config.id }
  get connected(): boolean { return this._connected }
  get tools(): MCPToolInfo[] { return [...this._tools] }

  /** Spawn the server process and complete the MCP initialize handshake */
  async connect(): Promise<void> {
    const timeoutMs = this.config.startupTimeoutMs ?? 15_000

    this.logger.info(`[mcp:${this.id}] Spawning: ${this.config.command} ${(this.config.args ?? []).join(' ')}`)

    this.transport = new StdioClientTransport({
      command: this.config.command,
      args:    this.config.args ?? [],
      env:     { ...process.env, ...(this.config.env ?? {}) } as Record<string, string>,
      stderr:  'pipe',
    })

    // Pipe subprocess stderr to debug-level logging instead of inheriting into daemon.log
    const stderrStream = this.transport.stderr
    if (stderrStream) {
      let buffer = ''
      stderrStream.on('data', (chunk: Buffer | string) => {
        buffer += String(chunk)
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line.trim()) this.logger.debug(`[mcp:${this.id}:stderr] ${line}`)
        }
      })
    }

    // Connect with a startup timeout
    await Promise.race([
      this.client.connect(this.transport),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error(`MCP server '${this.id}' startup timeout (${timeoutMs}ms)`)), timeoutMs)
      ),
    ])

    this._connected = true
    this.logger.info(`[mcp:${this.id}] Connected — MCP handshake complete`)
  }

  /** Fetch the tool list from the server */
  async listTools(): Promise<MCPToolInfo[]> {
    this.assertConnected()
    try {
      const resp = await this.client.listTools()
      this._tools = (resp.tools ?? []).map(t => ({
        name:        t.name,
        description: t.description ?? '',
        inputSchema: (t.inputSchema as Record<string, unknown>) ?? { type: 'object', properties: {} },
      }))
      this.logger.info(`[mcp:${this.id}] Discovered ${this._tools.length} tool(s): ${this._tools.map(t => t.name).join(', ')}`)
      return this._tools
    } catch (err) {
      this.logger.warn(`[mcp:${this.id}] listTools failed: ${String(err)}`)
      return []
    }
  }

  /** Call a tool on the server */
  async callTool(name: string, input: Record<string, unknown>): Promise<string> {
    this.assertConnected()

    const result = await this.client.callTool({ name, arguments: input })

    // MCP tool results are an array of content blocks
    const content = result.content as Array<{ type: string; text?: string }> | undefined
    if (!content || !Array.isArray(content) || content.length === 0) return ''

    // Join all text blocks
    return content
      .filter(c => c && c.type === 'text' && c.text)
      .map(c => c.text!)
      .join('\n')
  }

  /** Kill the server process */
  async disconnect(): Promise<void> {
    if (!this._connected) return
    try {
      await this.client.close()
      this._connected = false
      this.logger.info(`[mcp:${this.id}] Disconnected`)
    } catch (err) {
      this.logger.warn(`[mcp:${this.id}] Error during disconnect: ${String(err)}`)
    }
  }

  private assertConnected(): void {
    if (!this._connected) throw new Error(`MCP client '${this.id}' is not connected`)
  }
}
