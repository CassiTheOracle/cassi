/**
 * SDK Tool Bridge — converts CassiCore tools to SDK Tool[] format,
 * annotating tool results with a compact status prefix.
 *
 * The Thalamus handles full annotation (_thalamus metadata) when messages
 * enter the conversation. This bridge adds a lightweight status prefix
 * so the LLM sees tool name, duration, output size, and status immediately.
 */
import type { Tool as SdkTool, ToolInvocation } from '@github/copilot-sdk'

import type { ToolRegistry } from '@cassicore/tools'
import type { ToolExecutor } from '@cassicore/tools'
import type { ToolDefinition } from '@cassicore/tools'
import type { ILogger, IEventBus } from '@cassicore/foundation'
import { buildToolResultPrefix } from '@cassicore/thalamus/classifier'

/** Admin API base URL for state-card fetching */
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

        // Execute with cassi_do augmentation (status bar + optional state card)
        const enrichedResult = await executeWithAugmentation(
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
 * Execute a tool and prepend a compact status prefix.
 *
 * Format: [tool_name · 342ms · 3.2KB · ✓]
 * <raw tool result>
 *
 * The Thalamus will attach full _thalamus annotation when the message
 * enters the conversation. This prefix gives the LLM immediate metadata.
 */
async function executeWithAugmentation(
  toolName: string,
  args: Record<string, unknown>,
  toolExecutor: ToolExecutor,
  sessionId: string,
  _adminBaseUrl: string,
  logger: ILogger,
): Promise<string> {
  const start = Date.now()

  // Execute tool through CassiCore's executor (preserves permissions, trust, safety)
  const toolResult = await toolExecutor.execute(
    { id: `sdk_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`, name: toolName, input: args },
    sessionId,
  )

  const durationMs = Date.now() - start
  const outputBytes = Buffer.byteLength(toolResult.content, 'utf8')

  const prefix = buildToolResultPrefix(toolName, durationMs, outputBytes, toolResult.isError)
  return `${prefix}\n${toolResult.content}`
}
