import type { ToolCall, ToolResult, ToolExecutionContext } from './types.js'
import type { ToolRegistry } from './registry.js'

const MAX_CONCURRENT = 5

export class ToolExecutor {
  constructor(
    private registry: ToolRegistry,
    private defaultContext: Omit<ToolExecutionContext, 'sessionId'>,
  ) {}

  async execute(call: ToolCall, sessionId: string): Promise<ToolResult> {
    const entry = this.registry.get(call.name)
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
