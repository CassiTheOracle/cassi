/**
 * Hermes MCP Client — connects to the Hermes ACP server via MCP over stdio.
 *
 * Replaces the Python bridge (hermes-bridge.ts + bridge.py) with standard
 * MCP JSON-RPC 2.0 transport.  CassiCore spawns the Hermes ACP adapter as
 * a subprocess and discovers all Hermes tools dynamically — including
 * delegate_task, which was not available through the old bridge.
 *
 * Auto-reconnect: if the subprocess dies, the next callTool() will
 * transparently restart it.  Tool call results are always returned as
 * plain strings (callers call JSON.parse themselves if needed).
 */

import { spawn, type ChildProcess } from 'node:child_process'
import { resolve } from 'node:path'
import { rootLogger } from '../vendor/core/logger.js'
import { CASSICORE_VERSION } from '../vendor/core/version.js'
import type { ToolDefinition } from './types.js'
import type { ILogger } from "@cassicore/foundation"

const logger: ILogger = rootLogger.child('hermes-mcp-client')

const HERMES_PYTHON = resolve(
  process.env.HOME ?? '/home/valerie',
  '.hermes/hermes-agent/venv/bin/python3',
)

const HERMES_PROJECT = resolve(
  process.env.HOME ?? '/home/valerie',
  '.hermes/hermes-agent',
)

interface JsonRpcRequest {
  jsonrpc: '2.0'
  id: number
  method: string
  params?: Record<string, unknown>
}

interface JsonRpcResponse {
  jsonrpc: '2.0'
  id: number
  result?: unknown
  error?: { code: number; message: string; data?: unknown }
}

interface McpToolDef {
  name: string
  description?: string
  inputSchema: {
    type: 'object'
    properties?: Record<string, unknown>
    required?: string[]
  }
}

interface McpCallResult {
  content: Array<{ type: 'text'; text: string } | { type: 'image'; data: string; mimeType: string }>
  isError?: boolean
}

export class HermesMcpClient {
  private proc: ChildProcess | null = null
  private nextId = 1
  private pending = new Map<number, {
    resolve: (result: unknown) => void
    reject: (err: Error) => void
  }>()
  private buffer = ''
  private started = false
  private startPromise: Promise<void> | null = null
  private tools: ToolDefinition[] = []
  private serverCapabilities: Record<string, unknown> = {}

  async start(): Promise<void> {
    if (this.startPromise) return this.startPromise
    if (this.started) return

    this.startPromise = this.doStart()
    try {
      await this.startPromise
    } finally {
      this.startPromise = null
    }
  }

  getTools(): ToolDefinition[] {
    return this.tools
  }

  /**
   * Call a Hermes tool via MCP.  Auto-starts the client if not yet
   * connected.  Returns the raw result string on success; throws on
   * transport or tool-call error.
   */
  async callTool(name: string, args: Record<string, unknown>): Promise<string> {
    await this.ensureStarted()

    const result = await this.sendRequest('tools/call', { name, arguments: args })
    const callResult = result as McpCallResult | undefined

    if (callResult?.isError) {
      const errText = (callResult.content?.[0] as any)?.text ?? 'Tool call returned error'
      throw new Error(errText)
    }

    const textParts: string[] = []
    for (const c of (callResult?.content ?? [])) {
      if ('text' in c && typeof c.text === 'string') {
        textParts.push(c.text)
      }
    }
    return textParts.length > 0 ? textParts.join('\n') : JSON.stringify(result)
  }

  async stop(): Promise<void> {
    if (this.proc) {
      this.proc.stdin?.end()
      this.proc.kill()
      this.proc = null
    }
    this.started = false
    this.tools = []
    this.pending.clear()
    this.buffer = ''
  }

  private async ensureStarted(): Promise<void> {
    if (this.started && this.proc) return
    // Reset and reconnect
    if (this.proc) {
      this.proc.kill()
      this.proc = null
    }
    this.started = false
    this.pending.clear()
    this.buffer = ''
    await this.start()
  }

  private async doStart(): Promise<void> {
    logger.info('Starting Hermes MCP client', { python: HERMES_PYTHON })

    const proc = spawn(HERMES_PYTHON, ['-m', 'acp_adapter'], {
      cwd: HERMES_PROJECT,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {
        ...process.env,
        HOME: process.env.HOME ?? '/home/valerie',
        HERMES_HOME: resolve(process.env.HOME ?? '/home/valerie', '.hermes'),
      },
    })

    this.proc = proc
    this.buffer = ''

    proc.on('error', (err: Error) => {
      logger.error('Hermes MCP process error', { error: String(err) })
      this.started = false
      this.rejectAllPending(err)
    })

    proc.on('exit', (code, signal) => {
      logger.warn('Hermes MCP process exited', { code, signal })
      this.started = false
      this.proc = null
      this.rejectAllPending(new Error(`MCP process exited (code=${code})`))
    })

    proc.stdout!.on('data', (chunk: Buffer) => {
      this.buffer += chunk.toString()
      this.flushBuffer()
    })

    proc.stderr!.on('data', (chunk: Buffer) => {
      const text = chunk.toString().trim()
      if (text) logger.debug('[hermes-mcp stderr]', { text: text.slice(0, 500) })
    })

    const initResult = await this.sendRequest('initialize', {
      protocolVersion: '2024-11-05',
      capabilities: { tools: {} },
      clientInfo: { name: 'cassicore', version: CASSICORE_VERSION },
    })

    this.serverCapabilities = (initResult?.capabilities as Record<string, unknown>) ?? {}
    logger.info('Hermes MCP initialized', {
      serverName: initResult?.serverInfo?.name,
      serverVersion: initResult?.serverInfo?.version,
    })

    this.sendNotification('notifications/initialized', {})

    await this.discoverTools()
    this.started = true
    logger.info('Hermes MCP client ready', { toolCount: this.tools.length })
  }

  private async discoverTools(): Promise<void> {
    const result = await this.sendRequest('tools/list', {})
    const tools = (result?.tools as McpToolDef[]) ?? []
    this.tools = tools.map(t => this.convertToolDef(t))
    logger.info('Hermes MCP tools discovered', {
      count: this.tools.length,
      names: this.tools.map(t => t.name).slice(0, 20).join(', '),
    })
  }

  private convertToolDef(mcp: McpToolDef): ToolDefinition {
    return {
      name: mcp.name,
      description: mcp.description ?? '',
      parameters: {
        type: 'object',
        properties: (mcp.inputSchema?.properties ?? {}) as Record<string, any>,
        required: mcp.inputSchema?.required ?? [],
      },
      timeoutMs: 300_000,
      readOnly: false,
      category: 'core',
      requiredPermission: 'full-access',
    }
  }

  private sendRequest(method: string, params?: Record<string, unknown>): Promise<any> {
    const id = this.nextId++
    const request: JsonRpcRequest = { jsonrpc: '2.0', id, method, params }

    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      const line = JSON.stringify(request) + '\n'
      this.proc!.stdin!.write(line)
    })
  }

  private sendNotification(method: string, params?: Record<string, unknown>): void {
    const notification = { jsonrpc: '2.0', method, params }
    const line = JSON.stringify(notification) + '\n'
    this.proc?.stdin?.write(line)
  }

  private flushBuffer(): void {
    while (true) {
      const nl = this.buffer.indexOf('\n')
      if (nl === -1) break
      const line = this.buffer.slice(0, nl).trim()
      this.buffer = this.buffer.slice(nl + 1)
      if (!line) continue

      try {
        const parsed = JSON.parse(line)
        if (parsed && typeof parsed === 'object' && 'jsonrpc' in parsed && parsed.jsonrpc === '2.0' && 'id' in parsed) {
          const response = parsed as JsonRpcResponse
          const pending = this.pending.get(response.id)
          if (pending) {
            this.pending.delete(response.id)
            if (response.error) {
              pending.reject(new Error(response.error.message))
            } else {
              pending.resolve(response.result)
            }
          }
        }
      } catch {
        // Non-JSON line (log, notification, etc.) — ignore
      }
    }
  }

  private rejectAllPending(err: Error): void {
    this.pending.forEach((pending) => { pending.reject(err) })
    this.pending.clear()
  }
}

let _instance: HermesMcpClient | null = null

export function getHermesMcpClient(): HermesMcpClient {
  if (!_instance) {
    _instance = new HermesMcpClient()
  }
  return _instance
}

export async function shutdownHermesMcpClient(): Promise<void> {
  if (_instance) {
    await _instance.stop()
    _instance = null
  }
}
