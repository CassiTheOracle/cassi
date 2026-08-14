/**
 * VENDORED RUNTIME STUB — faithful `core/intelligence/constellation/meditation/
 * solo-runner.ts` surface consumed by the workspace package via a DYNAMIC
 * `import()` inside radiance-loop's `setHandleFactory` (observer path).
 *
 * `runSoloExplorer` is only ever reached when a host wires the observer handle
 * factory and a radiance cycle's surprise exceeds threshold — workspace tests
 * mock the observer runner and never hit this path. A `throw` would break the
 * runtime loop, so this is a genuine bounded inference-tool loop (not a throw),
 * with the model-pool / tool-executor / MCP-gateway deep deps reduced to minimal
 * structural types. Re-point to `@cassicore/constellation` at P7 when its barrel
 * expands to export `runSoloExplorer` (Open Flag 6).
 */

import type { ILogger, IEventBus, Message, ContentBlock, CompletionChunk } from '@cassicore/foundation'

/** Minimal structural ModelHandle surface used by the solo loop. */
export interface ModelHandle {
  provider: string
  model: string
  stream(
    messages: Message[],
    opts: {
      model: string
      tools?: Array<{ name: string; description: string; input_schema: Record<string, unknown> }>
      maxTokens?: number
      temperature?: number
      source?: string
      signal?: AbortSignal
    },
  ): AsyncIterable<CompletionChunk>
  release(): void
}

/** Minimal structural ToolExecutor surface used by the solo loop. */
export interface ToolExecutor {
  execute(call: { name: string; input: Record<string, unknown> }, sessionId: string): Promise<{ content: string; done?: boolean }>
}

/** Minimal structural ToolRegistry surface used by the solo loop. */
export interface ToolRegistry {
  toAnthropicSchema(): Array<{ name: string; description: string; input_schema: Record<string, unknown> }>
}

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
  /** Thalamus for context curation during long-running sessions (not exercised in this stub) */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  thalamus?: any
  /** Cross-session topic index (not exercised in this stub) */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  crossSessionIndex?: any
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

/** Build the initial message array from the instruction + optional memory context. */
function buildInitialMessages(
  instruction: string,
  memoryContext: string | undefined,
  _sessionId: string,
): Message[] {
  const messages: Message[] = []
  if (memoryContext) {
    messages.push({ role: 'user', content: memoryContext })
  }
  messages.push({ role: 'user', content: instruction })
  return messages
}

function isToolUse(block: ContentBlock): block is ContentBlock & { type: 'tool_use' } {
  return (block as { type?: string }).type === 'tool_use'
}

/**
 * Run a bounded model-tool observer loop. Iterates up to `maxIterations`,
 * streaming inference via the handle, extracting text output, and executing
 * tools (custom handlers, else the executor). Returns a valid SoloRunnerResult
 * on natural / max-iterations / cancellation / error — never throws.
 */
export async function runSoloExplorer(opts: SoloRunnerOpts): Promise<SoloRunnerResult> {
  const {
    sessionId, name, instruction, handle, toolExecutor, toolRegistry,
    maxIterations, logger, signal, memoryContext, onActivity, customHandlers,
  } = opts

  const log = logger.child ? logger.child(`solo:${name}`) : logger
  let iterations = 0
  let totalToolCalls = 0
  let tokensUsed = 0
  const transcriptParts: string[] = []
  const messages: Message[] = buildInitialMessages(instruction, memoryContext, sessionId)

  log.info('Solo explorer starting', {
    name,
    maxIterations,
    model: `${handle.provider}/${handle.model}`,
  })

  try {
    while (iterations < maxIterations) {
      if (signal.aborted) {
        log.info('Solo explorer cancelled', { name, iterations })
        return makeResult('cancelled')
      }

      iterations++

      const tools = opts.customToolSchemas ?? toolRegistry.toAnthropicSchema()
      const { blocks, tokens } = await streamInference(handle, messages, handle.model, tools, signal, name)
      tokensUsed += tokens

      if (blocks.length === 0) {
        log.info('Solo explorer produced no output, stopping', { name, iterations })
        break
      }

      messages.push({ role: 'assistant', content: blocks as ContentBlock[] })

      for (const block of blocks) {
        if (block.type === 'text' && (block as { text?: string }).text) {
          transcriptParts.push((block as { text: string }).text)
        }
      }

      const toolUseBlocks = blocks.filter(isToolUse)
      if (toolUseBlocks.length === 0) {
        log.info('Solo explorer concluded (no tool calls)', { name, iterations })
        break
      }

      // Execute tools — custom handlers override the executor per tool name.
      const results: Array<{ type: string; tool_call_id: string; content: string; done?: boolean }> = []
      let done = false
      for (const tc of toolUseBlocks) {
        const handler = customHandlers?.[tc.name]
        let content: string
        let toolDone: boolean | undefined
        if (handler) {
          const r = await handler(tc.input ?? {})
          content = r.content
          toolDone = r.done ?? undefined
        } else {
          const execResult = await toolExecutor.execute(
            { name: tc.name, input: tc.input ?? {} },
            sessionId,
          )
          content = execResult.content
          toolDone = execResult.done
        }
        totalToolCalls++
        if (toolDone) done = true
        results.push({ type: 'tool_result', tool_call_id: tc.id, content, done: toolDone ?? false })
      }

      messages.push({ role: 'user', content: results as unknown as ContentBlock[] })
      onActivity?.(iterations, totalToolCalls)

      if (done) {
        log.info('Solo explorer concluded (done)', { name, iterations })
        break
      }
    }

    if (iterations >= maxIterations) {
      log.info('Solo explorer reached max iterations', { name, iterations })
      return makeResult('max-iterations')
    }

    return makeResult('natural')
  } catch (err) {
    if (signal.aborted) return makeResult('cancelled')
    log.error('Solo explorer failed', { name, error: String(err), iterations })
    return makeResult('error', String(err))
  } finally {
    handle.release()
    log.info('Solo explorer complete', { name, iterations, toolCalls: totalToolCalls, tokensUsed })
  }

  function makeResult(stoppedBy: SoloRunnerResult['stoppedBy'], error?: string): SoloRunnerResult {
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
  model: string,
  tools: Array<{ name: string; description: string; input_schema: Record<string, unknown> }>,
  signal: AbortSignal,
  source: string,
): Promise<{ blocks: Array<ContentBlock & { text?: string }>; tokens: number }> {
  const blocks: Array<ContentBlock & { text?: string }> = []
  let currentText = ''
  let tokens = 0

  for await (const chunk of handle.stream(messages, {
    model,
    tools,
    maxTokens: 16_000,
    temperature: 0.8,
    source: `meditation:${source}`,
    signal,
  })) {
    if (chunk.type === 'token') {
      currentText += chunk.text
      tokens++
    } else if (chunk.type === 'tool_use') {
      if (currentText) {
        blocks.push({ type: 'text', text: currentText })
        currentText = ''
      }
      blocks.push(chunk as unknown as ContentBlock & { type: 'tool_use' })
    }
  }

  if (currentText) {
    blocks.push({ type: 'text', text: currentText })
  }

  return { blocks, tokens }
}
