/**
 * SoloRunner — Lightweight single-agent session for meditation explorers.
 *
 * Each explorer runs independently: one LLM handle, read-only tools,
 * no interaction with other explorers. The Corpus observes from outside.
 *
 * Replaces the full Helix pipeline for meditation, which created
 * unnecessary dialectic infrastructure (WorkStream, DialecticChannel,
 * Brainstem) even though meditation explorers should be solitary.
 */

import type { ILogger, IEventBus } from '../vendor/types/interfaces.js'
import type { Message, ContentBlock, CompletionChunk } from '../vendor/types/runtime.js'
import type { ModelHandle } from '@cassicore/model-pool/types'
import type { ToolExecutor } from '@cassicore/tools'
import type { ToolRegistry } from '@cassicore/tools'

import {
  getCodeConsolidatedToolSchema,
  getFilesystemConsolidatedToolSchema,
  WEB_CONSOLIDATED_TOOL,
  executeCodeConsolidatedTool,
  executeFilesystemConsolidatedTool,
  executeWebConsolidatedTool,
} from '../ports/mcp-consolidated-tools.js'


export interface SoloRunnerOpts {
  /** Unique session ID for this explorer */
  sessionId: string
  /** Explorer name (e.g., 'explorer-alpha') */
  name: string
  /** Opening prompt that sets the explorer's tone */
  instruction: string
  /** Acquired model handle for LLM calls */
  handle: ModelHandle
  /** Tool executor for running tools */
  toolExecutor: ToolExecutor
  /** Tool registry for tool schemas */
  toolRegistry: ToolRegistry
  /** Maximum iterations before stopping */
  maxIterations: number
  /** Logger instance */
  logger: ILogger
  /** Event bus for meditation events */
  eventBus: IEventBus
  /** Abort signal for cancellation */
  signal: AbortSignal
  /** Memory context to inject (from mnemic field) */
  memoryContext?: string
  /** Callback fired after each iteration for heartbeat/progress */
  onActivity?: (iteration: number, toolCalls: number) => void
  /** Custom tool handlers that override the default executor. Keyed by tool name. */
  customHandlers?: Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>>
  /** Custom tool schemas (replaces default consolidated + memory tools when provided) */
  customToolSchemas?: Array<{ name: string; description: string; input_schema: Record<string, unknown> }>
}

export interface ToolCallResult {
  content: string
  done?: boolean
}

export interface SoloRunnerResult {
  name: string
  sessionId: string
  iterations: number
  toolCalls: number
  tokensUsed: number
  stoppedBy: 'natural' | 'max-iterations' | 'cancelled' | 'error'
  error?: string
  /** The explorer's full text output — assistant messages only, for post-session synthesis */
  transcript: string
}

const CONSOLIDATED_TOOL_NAMES = new Set(['code', 'file', 'web'])

const MAX_TOOL_RESULT_LENGTH = 12_000


export async function runSoloExplorer(opts: SoloRunnerOpts): Promise<SoloRunnerResult> {
  const {
    sessionId, name, instruction, handle, toolExecutor, toolRegistry,
    maxIterations, logger, signal, memoryContext, onActivity,
    customHandlers, customToolSchemas,
  } = opts

  const log = logger.child(`solo:${name}`)
  let iterations = 0
  let totalToolCalls = 0
  let tokensUsed = 0
  const transcriptParts: string[] = []

  const tools = customToolSchemas ?? buildToolSchemas(toolRegistry)
  const messages: Message[] = buildInitialMessages(instruction, memoryContext, sessionId)

  log.info('Solo explorer starting', { name, maxIterations, model: `${handle.provider}/${handle.model}` })

  try {
    while (iterations < maxIterations) {
      if (signal.aborted) {
        log.info('Solo explorer cancelled', { name, iterations })
        return result('cancelled')
      }

      iterations++

      const inferenceMessages = messages

      // Stream inference to capture both text and tool_use chunks
      const { blocks, tokens } = await streamInference(handle, inferenceMessages, tools, signal, name)
      tokensUsed += tokens

      if (blocks.length === 0) {
        log.info('Solo explorer produced no output, stopping', { name, iterations })
        break
      }

      messages.push({ role: 'assistant', content: blocks })

      // Capture text output for post-session synthesis
      for (const block of blocks) {
        if (block.type === 'text') {
          const textBlock = block as { type: 'text'; text: string }
          if (textBlock.text) {
            transcriptParts.push(textBlock.text)
          }
        }
      }

      // Extract tool calls
      const toolUseBlocks = blocks.filter(
        (b): b is ContentBlock & { type: 'tool_use' } => b.type === 'tool_use',
      )

      if (toolUseBlocks.length === 0) {
        log.info('Solo explorer concluded (no tool calls)', { name, iterations })
        break
      }

      // Execute tools
      const { results, done } = await executeTools(toolUseBlocks, toolExecutor, toolRegistry, sessionId, log, customHandlers)
      totalToolCalls += toolUseBlocks.length

      messages.push({ role: 'user', content: results })

      onActivity?.(iterations, totalToolCalls)

      if (done) {
        log.info('Solo explorer concluded (done)', { name, iterations })
        break
      }
    }

    if (iterations >= maxIterations) {
      log.info('Solo explorer reached max iterations', { name, iterations })
      return result('max-iterations')
    }

    return result('natural')
  } catch (err) {
    if (signal.aborted) return result('cancelled')
    log.error('Solo explorer failed', { name, error: String(err), iterations })
    return result('error', String(err))
  } finally {
    handle.release()
    log.info('Solo explorer complete', { name, iterations, toolCalls: totalToolCalls, tokensUsed })
  }

  function result(stoppedBy: SoloRunnerResult['stoppedBy'], error?: string): SoloRunnerResult {
    // Truncate transcript to prevent memory bloat — keep the most recent ~8K chars
    const MAX_TRANSCRIPT = 8_000
    const fullTranscript = transcriptParts.join('\n\n')
    const transcript = fullTranscript.length > MAX_TRANSCRIPT
      ? fullTranscript.slice(-MAX_TRANSCRIPT)
      : fullTranscript
    return { name, sessionId, iterations, toolCalls: totalToolCalls, tokensUsed, stoppedBy, error, transcript }
  }
}


/** Collect streaming chunks into ContentBlock array + token count. */
async function streamInference(
  handle: ModelHandle,
  messages: Message[],
  tools: Array<{ name: string; description: string; input_schema: Record<string, unknown> }>,
  signal: AbortSignal,
  source: string,
): Promise<{ blocks: ContentBlock[]; tokens: number }> {
  const blocks: ContentBlock[] = []
  let currentText = ''
  let tokens = 0

  for await (const chunk of handle.stream(messages, {
    model: handle.model,
    tools,
    maxTokens: 16_000,
    temperature: 0.8,
    source: `meditation:${source}`,
    signal,
  })) {
    if (chunk.tokensUsed) tokens += chunk.tokensUsed

    if (chunk.type === 'token' || chunk.type === 'thinking') {
      currentText += chunk.text ?? ''
    } else if (chunk.type === 'tool_use' && chunk.toolCall) {
      // Flush accumulated text before tool_use
      if (currentText.length > 0) {
        blocks.push({ type: 'text', text: currentText })
        currentText = ''
      }
      blocks.push({
        type: 'tool_use',
        id: chunk.toolCall.id,
        name: chunk.toolCall.name,
        input: chunk.toolCall.input,
      })
    }
  }

  // Flush remaining text
  if (currentText.length > 0) {
    blocks.push({ type: 'text', text: currentText })
  }

  return { blocks, tokens }
}


function buildInitialMessages(instruction: string, memoryContext: string | undefined, sessionId: string): Message[] {
  const systemPrompt = [
    `[session:${sessionId}]`,
    '',
    'You are exploring. You have read-only tools to look around, read files, search code, and browse the web.',
    'There is no task. There is no deadline. Follow what interests you.',
    '',
    'You can read files, search code, and look through memory. You cannot modify anything.',
    'When you find something interesting, keep exploring. When you run out of curiosity, stop.',
  ].join('\n')

  const messages: Message[] = [
    { role: 'system', content: systemPrompt },
  ]

  let userContent = instruction
  if (memoryContext) {
    userContent += `\n\n## Memory\n\n${memoryContext}`
  }

  messages.push({ role: 'user', content: userContent })
  return messages
}


function buildToolSchemas(toolRegistry: ToolRegistry): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
  const tools: Array<{ name: string; description: string; input_schema: Record<string, unknown> }> = []

  // Read-only consolidated tools
  tools.push(getCodeConsolidatedToolSchema(true) as any)
  tools.push(getFilesystemConsolidatedToolSchema(true) as any)
  tools.push(WEB_CONSOLIDATED_TOOL as any)

  // Add memory-related tools from the registry (memory_search, memory_recent)
  const allSchemas = toolRegistry.toAnthropicSchema()
  for (const schema of allSchemas) {
    if (schema.name === 'memory_search' || schema.name === 'memory_recent') {
      tools.push(schema as any)
    }
  }

  return tools
}


interface ToolCallBlock {
  id: string
  name: string
  input: Record<string, unknown>
}

async function executeTools(
  toolCalls: ToolCallBlock[],
  toolExecutor: ToolExecutor,
  _toolRegistry: ToolRegistry,
  sessionId: string,
  log: ILogger,
  customHandlers?: Record<string, (input: Record<string, unknown>) => Promise<ToolCallResult>>,
): Promise<{ results: ContentBlock[]; done: boolean }> {
  const routeTool = async (toolName: string, toolArgs: unknown) => {
    const toolCall = {
      id: `solo-${Math.random().toString(36).slice(2)}`,
      name: toolName,
      input: (toolArgs ?? {}) as Record<string, unknown>,
    }
    const execResult = await toolExecutor.execute(toolCall, sessionId)
    return {
      content: [{ type: 'text' as const, text: execResult.content }],
      ...(execResult.isError ? { isError: true as const } : {}),
    }
  }

  let done = false

  const settled = await Promise.allSettled(
    toolCalls.map(async (tc): Promise<ContentBlock> => {
      try {
        // Check custom handler first
        if (customHandlers?.[tc.name]) {
          const handlerResult = await customHandlers[tc.name](tc.input)
          if (handlerResult.done) done = true
          return {
            type: 'tool_result' as const,
            tool_use_id: tc.id,
            content: handlerResult.content,
          }
        }

        let content = ''
        let isError = false

        if (CONSOLIDATED_TOOL_NAMES.has(tc.name)) {
          if (tc.name === 'code') {
            const r = await executeCodeConsolidatedTool(tc.input, log, routeTool)
            content = JSON.stringify(r)
            isError = !!r?.isError
          } else if (tc.name === 'file') {
            const r = await executeFilesystemConsolidatedTool(tc.input, log, routeTool)
            content = JSON.stringify(r)
            isError = !!r?.isError
          } else if (tc.name === 'web') {
            const r = await executeWebConsolidatedTool('http://localhost:7433', tc.input, log, routeTool)
            content = JSON.stringify(r)
            isError = !!r?.isError
          }
        } else {
          // Direct tool execution (memory_search, memory_recent)
          const execResult = await toolExecutor.execute(
            { id: tc.id, name: tc.name, input: tc.input },
            sessionId,
          )
          content = execResult.content
          isError = execResult.isError
        }

        // Truncate large results
        if (content.length > MAX_TOOL_RESULT_LENGTH) {
          content = content.slice(0, MAX_TOOL_RESULT_LENGTH) + '\n... (truncated)'
        }

        return {
          type: 'tool_result' as const,
          tool_use_id: tc.id,
          content,
          is_error: isError,
        }
      } catch (err) {
        log.warn('Tool execution failed', { tool: tc.name, error: String(err) })
        return {
          type: 'tool_result' as const,
          tool_use_id: tc.id,
          content: `Tool execution failed: ${String(err)}`,
          is_error: true,
        }
      }
    }),
  )

  return {
    results: settled
      .filter((r): r is PromiseFulfilledResult<ContentBlock> => r.status === 'fulfilled')
      .map(r => r.value),
    done,
  }
}
