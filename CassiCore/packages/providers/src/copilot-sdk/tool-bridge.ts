/**
 * SDK Tool Bridge — converts CassiCore tools to SDK Tool[] format,
 * routing all execution through the cassi_do enrichment pipeline.
 *
 * Every tool result the LLM sees includes relevant context from
 * memory, archive, and session history — no explicit injection needed.
 */
import type { Tool as SdkTool, ToolInvocation } from '@github/copilot-sdk'

import type { ToolRegistry } from '../../tools/registry.js'
import type { ToolExecutor } from '../../tools/executor.js'
import type { ToolDefinition } from '../../tools/types.js'
import type { ILogger, IEventBus } from '../../../types/interfaces.js'

/** Admin API base URL for context fetching (memory/archive/index search) */
const DEFAULT_ADMIN_URL = 'http://127.0.0.1:7433'

/**
 * Bridge CassiCore tools to SDK Tool[] format with cassi_do enrichment.
 *
 * Each tool is exposed to the SDK with its proper typed schema.
 * Under the hood, every tool handler routes through the cassi_do
 * enrichment pipeline for automatic context injection.
 */
export function bridgeToolsToSdk(
  toolRegistry: ToolRegistry,
  toolExecutor: ToolExecutor,
  bus: IEventBus,
  logger: ILogger,
  adminBaseUrl: string = DEFAULT_ADMIN_URL,
): SdkTool[] {
  const definitions = toolRegistry.list()
  const bridgedTools: SdkTool[] = []

  for (const def of definitions) {
    const sdkTool = createSdkTool(def, toolExecutor, bus, logger, adminBaseUrl)
    bridgedTools.push(sdkTool)
  }

  logger.info(`Bridged ${bridgedTools.length} CassiCore tools to SDK format`)
  return bridgedTools
}

/** Emit a worker:message event (CassiCore convention for turn-level events). */
function emitWorkerMessage(bus: IEventBus, sessionId: string, payload: Record<string, unknown>): void {
  bus.emit({
    type: 'worker:message',
    pluginId: `session:${sessionId}`,
    payload,
  })
}

/**
 * Create a single SDK tool from a CassiCore ToolDefinition.
 */
function createSdkTool(
  def: ToolDefinition,
  toolExecutor: ToolExecutor,
  bus: IEventBus,
  logger: ILogger,
  adminBaseUrl: string,
): SdkTool {
  return {
    name: def.name,
    description: def.description,
    // Convert CassiCore ToolParamSchema to the generic JSON schema the SDK expects
    parameters: def.parameters as unknown as Record<string, unknown>,
    // Ensure our tool takes precedence over any Copilot built-in with the same name
    // (e.g. web_fetch, read_file, write_file all have Copilot equivalents).
    // Without this flag the Copilot API returns a 400 for conflicting tool names.
    overridesBuiltInTool: true,
    handler: async (args: unknown, invocation: ToolInvocation) => {
      const toolLogger = logger.child(`sdk-tool:${def.name}`)
      const start = Date.now()
      const sessionId = invocation.sessionId

      try {
        // Emit CassiCore event for tool start
        emitWorkerMessage(bus, sessionId, {
          type: 'turn:tool_call',
          sessionId,
          toolCallId: invocation.toolCallId,
          tool: def.name,
          input: args,
        })

        // Execute through cassi_do enrichment pipeline
        const enrichedResult = await executeWithEnrichment(
          def.name,
          args as Record<string, unknown>,
          toolExecutor,
          sessionId,
          adminBaseUrl,
          toolLogger,
        )

        const durationMs = Date.now() - start

        // Emit CassiCore event for tool completion
        emitWorkerMessage(bus, sessionId, {
          type: 'turn:tool_result',
          sessionId,
          toolCallId: invocation.toolCallId,
          isError: false,
          content: enrichedResult.slice(0, 200),
        })

        toolLogger.debug(`${def.name} completed in ${durationMs}ms`)

        return {
          textResultForLlm: enrichedResult,
          resultType: 'success' as const,
        }
      } catch (err) {
        const durationMs = Date.now() - start
        const errorMsg = err instanceof Error ? err.message : String(err)

        emitWorkerMessage(bus, sessionId, {
          type: 'turn:tool_result',
          sessionId,
          toolCallId: invocation.toolCallId,
          isError: true,
          content: `Error: ${errorMsg}`.slice(0, 200),
        })

        toolLogger.error(`${def.name} failed in ${durationMs}ms: ${errorMsg}`)

        return {
          textResultForLlm: `Error: ${errorMsg}`,
          resultType: 'failure' as const,
          error: errorMsg,
        }
      }
    },
  }
}

/**
 * Execute a tool with cassi_do-style context enrichment.
 *
 * Fetches memory/archive/index context in parallel with tool execution,
 * then prepends the context to the tool result.
 */
async function executeWithEnrichment(
  toolName: string,
  args: Record<string, unknown>,
  toolExecutor: ToolExecutor,
  sessionId: string,
  adminBaseUrl: string,
  logger: ILogger,
): Promise<string> {
  // Derive context query from tool name + first meaningful input field
  const contextQuery = deriveContextQuery(toolName, args)

  // Execute tool + fetch context in parallel
  const [toolResult, contextBlock] = await Promise.all([
    // Tool execution via CassiCore's ToolExecutor (preserves permissions, trust, etc.)
    toolExecutor.execute(
      { id: `sdk_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`, name: toolName, input: args },
      sessionId,
    ),
    // Context enrichment (memory + archive + session index)
    fetchContextBlock(adminBaseUrl, contextQuery, logger).catch(err => {
      logger.debug(`Context fetch failed (non-fatal): ${String(err)}`)
      return '' // Graceful degradation — tool result still returned
    }),
  ])

  // Assemble enriched result
  const parts: string[] = []
  if (contextBlock) {
    parts.push(contextBlock)
    parts.push('---')
  }
  parts.push(`## Tool Result: \`${toolName}\``)
  if (toolResult.isError) {
    parts.push(`**Error:** ${toolResult.content}`)
  } else {
    parts.push(toolResult.content)
  }

  return parts.join('\n')
}

/**
 * Derive context search query from tool name and input arguments.
 * Matches the logic in mcp/gateway/do-tool.ts deriveContextQuery().
 */
function deriveContextQuery(toolName: string, args: Record<string, unknown>): string {
  const priorityFields = ['query', 'goal', 'command', 'message', 'content', 'path', 'target', 'prompt', 'text']
  for (const field of priorityFields) {
    const val = args[field]
    if (typeof val === 'string' && val.trim()) {
      return `${toolName} ${val.trim().slice(0, 200)}`
    }
  }
  return toolName
}

/**
 * Fetch context from memory, archive, and session index via the admin API.
 * Returns a formatted markdown block, or empty string if no results.
 */
async function fetchContextBlock(
  baseUrl: string,
  query: string,
  _logger: ILogger,
  memoryLimit = 3,
  archiveLimit = 3,
  indexLimit = 5,
): Promise<string> {
  const sections: string[] = []

  // Fetch all three sources in parallel
  const [memories, archives, indexResults] = await Promise.all([
    memoryLimit > 0 ? fetchJson(`${baseUrl}/memory/search?query=${encodeURIComponent(query)}&limit=${memoryLimit}`) : [],
    archiveLimit > 0 ? fetchJson(`${baseUrl}/memory/archives/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: archiveLimit }),
    }) : [],
    indexLimit > 0 ? fetchJson(`${baseUrl}/memory/index/search?query=${encodeURIComponent(query)}&limit=${indexLimit}`) : [],
  ])

  if (memories.length > 0) {
    sections.push(`### From Memory (${memories.length} results)`)
    for (const m of memories) {
      const mem = m as Record<string, unknown>
      sections.push(`- ${String(mem.key ?? mem.id ?? 'memory')}: ${String(mem.content ?? '').slice(0, 300)}`)
    }
  }

  if (archives.length > 0) {
    sections.push(`### From Archive (${archives.length} results)`)
    for (const a of archives) {
      const arc = a as Record<string, unknown>
      sections.push(`- [${String(arc.type ?? 'entry')}] ${String(arc.content ?? arc.summary ?? '').slice(0, 300)}`)
    }
  }

  if (indexResults.length > 0) {
    sections.push(`### From Session History (${indexResults.length} results)`)
    for (const r of indexResults) {
      const idx = r as Record<string, unknown>
      sections.push(`- ${String(idx.text ?? idx.content ?? '').slice(0, 200)}`)
    }
  }

  if (sections.length === 0) return ''

  return `## Cassi Context\n> Auto-enriched for: \`${query.slice(0, 80)}\`\n\n${sections.join('\n')}`
}

/** Fetch JSON from admin API with timeout. */
async function fetchJson(url: string, init?: RequestInit): Promise<unknown[]> {
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    const res = await fetch(url, { ...init, signal: controller.signal })
    clearTimeout(timeout)
    if (!res.ok) return []
    const data = await res.json() as unknown
    // Handle various response shapes
    if (Array.isArray(data)) return data
    if (data && typeof data === 'object' && 'results' in data) return (data as { results: unknown[] }).results ?? []
    if (data && typeof data === 'object' && 'entries' in data) return (data as { entries: unknown[] }).entries ?? []
    return []
  } catch {
    return []
  }
}
