import type { ToolCall, ToolResult, ToolExecutionContext } from './types.js'
import type { ToolRegistry } from './registry.js'

const MAX_CONCURRENT = 20

export class ToolExecutor {
  constructor(
    private registry: ToolRegistry,
    private defaultContext: Omit<ToolExecutionContext, 'sessionId'>,
  ) {}

  async execute(call: ToolCall, sessionId: string): Promise<ToolResult> {
    // Prefer serena (MCP) implementations for core file operations when available.
    // Strategy:
    // 1. Try exact tool name (as registered)
    // 2. Try preferred MCP servers (env PREFERRED_MCP_SERVERS, default 'serena') using serverId__toolName
    // 3. For common file ops, look for any registered serena__* tool that looks like a match

    let entry = this.registry.get(call.name)

    const preferredServers = (process.env.PREFERRED_MCP_SERVERS || 'serena').split(',').map(s => s.trim()).filter(Boolean)

    if (!entry) {
      for (const serverId of preferredServers) {
        const alt = `${serverId}__${call.name}`
        const e = this.registry.get(alt)
        if (e) { entry = e; break }
      }
    }

    // Heuristic fallback for common file operations
    if (!entry) {
      const fileOps = new Set(['read_file','write_file','read','write','exists','mkdir','delete','bash'])
      if (fileOps.has(call.name)) {
        const list = this.registry.list()

        // Try serena-prefixed tools first
        const serenaMatch = list.find(d => d.name.startsWith('serena__') && (
          (call.name.includes('read') && d.name.includes('read')) ||
          ((call.name.includes('write') || call.name.includes('create')) && (d.name.includes('write') || d.name.includes('create') || d.name.includes('replace') || d.name.includes('insert'))) ||
          (call.name.includes('exists') && d.name.includes('exists')) ||
          (call.name.includes('mkdir') && d.name.includes('mkdir')) ||
          (call.name === 'bash' && d.name.includes('shell'))
        ))
        if (serenaMatch) entry = this.registry.get(serenaMatch.name)

        // Otherwise, pick any tool with suffix __<toolName>
        if (!entry) {
          const suffixMatch = list.find(d => d.name.endsWith(`__${call.name}`))
          if (suffixMatch) entry = this.registry.get(suffixMatch.name)
        }
      }
    }

    if (!entry) {
      return { toolCallId: call.id, content: `Unknown tool: ${call.name}`, isError: true }
    }

    const timeout = entry.definition.timeoutMs ?? 30_000
    const ctx: ToolExecutionContext = { ...this.defaultContext, sessionId }

    try {
      const result = await Promise.race([
        entry.handler(call.input, ctx),
        new Promise<never>((_, reject) =>
          setTimeout(
            () => reject(new Error(`Tool '${call.name}' timed out after ${timeout}ms`)),
            timeout,
          )
        ),
      ])
      return { toolCallId: call.id, content: result, isError: false }
    } catch (err) {
      return { toolCallId: call.id, content: String(err), isError: true }
    }
  }

  /** Execute up to MAX_CONCURRENT tool calls concurrently */
  async executeAll(calls: ToolCall[], sessionId: string): Promise<ToolResult[]> {
    const results: ToolResult[] = []
    for (let i = 0; i < calls.length; i += MAX_CONCURRENT) {
      const batch = calls.slice(i, i + MAX_CONCURRENT)
      const batchResults = await Promise.all(batch.map(c => this.execute(c, sessionId)))
      results.push(...batchResults)
    }
    return results
  }
}
