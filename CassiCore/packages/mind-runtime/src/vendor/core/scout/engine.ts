/**
 * Scout Engine — Runs a fast/cheap model with read-only search tools to gather
 * context before the main model processes a turn.
 *
 * The engine performs a self-contained mini-agent loop:
 *   1. Build a scout prompt (system + conversation tail + user message)
 *   2. Call the fast model with search tool schemas
 *   3. If the model produces tool calls, execute them and feed results back
 *   4. Repeat up to maxToolRounds or until the model finishes
 *   5. Return the gathered context summary
 */

import { SCOUT_SYSTEM_PROMPT, SCOUT_CONTINUATION_PROMPT } from './prompts.js'

import type { ScoutConfig, ScoutResult, ScoutToolExecution } from './types.js'
import type { IEventBus, ILogger } from '@cassicore/foundation'
import type { IProvider, Message, CompletionOpts, CompletionChunk } from '@cassicore/foundation'
import type { ToolExecutor } from '@cassicore/tools'
import type { ToolRegistry } from '@cassicore/tools'
import type { ToolCall, ToolResult, ToolDefinition } from '@cassicore/tools'
import type { ModuleSessionRegistry } from '../intelligence/module-session-registry.js'


// Tool Whitelist

/**
 * Default set of allowed tool names for the scout.
 * Supports both direct names and MCP-prefixed variants (e.g., "serena__find_symbol").
 */
const DEFAULT_ALLOWED_TOOLS = new Set([
  // Codebase search
  'read_file',
  'search_for_pattern',
  'find_symbol',
  'get_symbols_overview',
  'find_file',
  'list_dir',
  'find_referencing_symbols',
  // Knowledge graph
  'gitnexus__query',
  'gitnexus__context',
  'gitnexus__cypher',
  // Memory / Archive
  'memory_search',
  'universal_search',
  'archive_search',
  'memory_search',
  // Web search
  'web_search',
  'web_fetch',
  'duckduckgo__search',
])

// ScoutEngine

export class ScoutEngine {
  private logger: ILogger
  private provider: IProvider
  private toolRegistry: ToolRegistry
  private toolExecutor: ToolExecutor
  private eventBus?: IEventBus
  private config: ScoutConfig
  private allowedTools: Set<string>
  private moduleRegistry?: ModuleSessionRegistry

  constructor(
    logger: ILogger,
    provider: IProvider,
    toolRegistry: ToolRegistry,
    toolExecutor: ToolExecutor,
    config: ScoutConfig,
    eventBus?: IEventBus,
  ) {
    this.logger = logger
    this.provider = provider
    this.toolRegistry = toolRegistry
    this.toolExecutor = toolExecutor
    this.config = config
    this.eventBus = eventBus

    // Build the allowed tool set from config or defaults
    this.allowedTools = config.allowedTools.length > 0
      ? new Set(config.allowedTools)
      : DEFAULT_ALLOWED_TOOLS
  }

  /** Wire the module session registry for persistent debug sessions. */
  setModuleRegistry(registry: ModuleSessionRegistry): void {
    this.moduleRegistry = registry
    registry.getOrCreate('scout')
  }

  /**
   * Run the scout for a given turn.
   *
   * @param sessionId — Session ID for tool execution context
   * @param userMessage — The user's current message
   * @param conversationTail — Recent messages for context
   * @returns ScoutResult with gathered context
   */
  async run(
    sessionId: string,
    userMessage: string,
    conversationTail: Message[],
  ): Promise<ScoutResult> {
    const startMs = Date.now()
    const toolExecutions: ScoutToolExecution[] = []
    let roundsUsed = 0
    let tokensUsed = 0

    // Build the messages for the scout model
    const isFirstMessage = conversationTail.length === 0
    const systemPrompt = isFirstMessage ? SCOUT_SYSTEM_PROMPT : SCOUT_CONTINUATION_PROMPT
    const scoutMessages = this.buildScoutMessages(systemPrompt, userMessage, conversationTail)
    const scoutTools = this.getScoutToolSchemas()

    if (scoutTools.length === 0) {
      this.logger.warn('No search tools available — skipping')
      return {
        status: 'skipped',
        context: '',
        toolExecutions: [],
        durationMs: Date.now() - startMs,
        skipReason: 'no search tools available',
        roundsUsed: 0,
        tokensUsed: 0,
      }
    }

    this.emitEvent('scout:started', { sessionId, message: userMessage.slice(0, 200) })

    // Mutable messages array for the tool loop
    const messages: Message[] = [...scoutMessages]

    try {
      // Mini-agent loop: call model → maybe get tool calls → execute → feed back → repeat
      for (let round = 0; round < this.config.maxToolRounds; round++) {
        roundsUsed++

        // Check timeout
        if (Date.now() - startMs > this.config.timeoutMs) {
          this.logger.warn('Timed out', {
            roundsUsed,
            durationMs: Date.now() - startMs,
          })
          return this.buildResult('timeout', messages, toolExecutions, startMs, roundsUsed, tokensUsed)
        }

        // Call the scout model
        const completionOpts: CompletionOpts = {
          model: this.config.model,
          maxTokens: this.config.maxTokens,
          temperature: this.config.temperature,
          thinking: 'none',
          tools: scoutTools,
          allowConcurrent: true,
          dedupe: false,
          // Bind to persistent module debug session for Telegram observability
          sessionId: this.moduleRegistry?.getSessionId('scout'),
        }

        let responseText = ''
        const toolCalls: ToolCall[] = []

        // Stream the response and collect text + tool calls
        const timeoutMs = Math.min(
          this.config.timeoutMs - (Date.now() - startMs),
          this.config.timeoutMs,
        )

        const stream = this.provider.complete(messages, completionOpts)
        const abortTimer = setTimeout(() => {
          // AbortController-style timeout — the for-await will throw on the next iteration
        }, timeoutMs)

        try {
          for await (const chunk of stream) {
            if (chunk.type === 'token' && chunk.text) {
              responseText += chunk.text
            } else if (chunk.type === 'tool_use' && chunk.toolCall) {
              toolCalls.push({
                id: chunk.toolCall.id,
                name: chunk.toolCall.name,
                input: chunk.toolCall.input,
              })
            } else if (chunk.type === 'done' && chunk.tokensUsed) {
              tokensUsed += chunk.tokensUsed
            }

            // Check timeout within the stream
            if (Date.now() - startMs > this.config.timeoutMs) break
          }
        } finally {
          clearTimeout(abortTimer)
        }

        // If no tool calls, the scout is done — responseText is the context summary
        if (toolCalls.length === 0) {
          // Add the response to messages for completeness
          if (responseText.trim()) {
            messages.push({ role: 'assistant', content: responseText })
          }
          break
        }

        // Build assistant message with tool_use blocks
        const assistantContent: Array<{ type: 'text'; text: string } | { type: 'tool_use'; id: string; name: string; input: Record<string, unknown> }> = []
        if (responseText.trim()) {
          assistantContent.push({ type: 'text', text: responseText })
        }
        for (const tc of toolCalls) {
          assistantContent.push({ type: 'tool_use', id: tc.id, name: tc.name, input: tc.input })
        }
        messages.push({ role: 'assistant', content: assistantContent })

        // Execute tool calls and collect results
        const toolResults: ToolResult[] = []
        for (const tc of toolCalls) {
          // Validate tool is allowed
          if (!this.isToolAllowed(tc.name)) {
            this.logger.warn('Tool not in whitelist, skipping', { tool: tc.name })
            toolResults.push({
              toolCallId: tc.id,
              toolName: tc.name,
              content: `Tool "${tc.name}" is not available to the scout agent.`,
              isError: true,
            })
            continue
          }

          this.emitEvent('scout:tool_call', { sessionId, tool: tc.name, input: tc.input })

          const toolStartMs = Date.now()
          const result = await this.toolExecutor.execute(tc, sessionId)
          const toolDurationMs = Date.now() - toolStartMs

          toolResults.push(result)
          toolExecutions.push({ call: tc, result, durationMs: toolDurationMs })

          this.emitEvent('scout:tool_result', {
            sessionId,
            tool: tc.name,
            resultLength: result.content.length,
            isError: result.isError,
            durationMs: toolDurationMs,
          })
        }

        // Add tool results as a user message with tool_result blocks
        const resultContent = toolResults.map(r => ({
          type: 'tool_result' as const,
          tool_use_id: r.toolCallId,
          content: this.truncateToolResult(r.content),
          is_error: r.isError,
        }))
        messages.push({ role: 'user', content: resultContent })
      }

      return this.buildResult('completed', messages, toolExecutions, startMs, roundsUsed, tokensUsed)
    } catch (err) {
      this.logger.error('Failed', { error: String(err) })
      this.emitEvent('scout:error', { sessionId, error: String(err) })
      return {
        status: 'error',
        context: '',
        toolExecutions,
        durationMs: Date.now() - startMs,
        error: String(err),
        roundsUsed,
        tokensUsed,
      }
    }
  }

  // Private Helpers

  /**
   * Build the initial messages for the scout model.
   * Includes system prompt + conversation tail (for continuity) + user message.
   */
  private buildScoutMessages(
    systemPrompt: string,
    userMessage: string,
    conversationTail: Message[],
  ): Message[] {
    const messages: Message[] = [
      { role: 'system', content: systemPrompt },
    ]

    // Include conversation tail for context (only last N messages)
    if (conversationTail.length > 0) {
      const tail = conversationTail.slice(-this.config.historyTailSize)
      // Summarize the tail as a system message rather than replaying the full history,
      // to save tokens while still giving the scout conversation context.
      const tailSummary = tail
        .filter(m => typeof m.content === 'string')
        .map(m => `[${m.role}]: ${(m.content as string).slice(0, 300)}`)
        .join('\n')

      if (tailSummary) {
        messages.push({
          role: 'system',
          content: `## Recent Conversation Context\n${tailSummary}`,
        })
      }
    }

    // The actual user message to scout for
    messages.push({ role: 'user', content: userMessage })

    return messages
  }

  /**
   * Get tool schemas for the scout model (only whitelisted tools).
   * Returns in Anthropic format since that's what CompletionOpts expects.
   */
  private getScoutToolSchemas(): Array<{ name: string; description: string; input_schema: Record<string, unknown> }> {
    const allTools = this.toolRegistry.list()
    const schemas: Array<{ name: string; description: string; input_schema: Record<string, unknown> }> = []

    for (const tool of allTools) {
      if (!this.isToolAllowed(tool.name)) continue

      schemas.push({
        name: tool.name,
        description: tool.description,
        input_schema: tool.parameters as unknown as Record<string, unknown>,
      })
    }

    return schemas
  }

  /**
   * Check if a tool is in the allowed whitelist.
   * Supports both exact match and MCP prefix match.
   */
  private isToolAllowed(toolName: string): boolean {
    if (this.allowedTools.has(toolName)) return true

    // Check MCP-prefixed variants (e.g., "serena__find_symbol" matches "find_symbol")
    for (const allowed of this.allowedTools) {
      if (toolName.endsWith(`__${allowed}`) || toolName.startsWith(`${allowed}__`)) return true
    }

    return false
  }

  /**
   * Truncate a tool result to avoid blowing the scout's context budget.
   * Individual tool results are capped; the total context injection is capped separately.
   */
  private truncateToolResult(content: string): string {
    const maxPerTool = Math.floor(this.config.maxContextChars / 2) // Leave room for summary
    if (content.length <= maxPerTool) return content
    return `${content.slice(0, maxPerTool)  }\n\n... [truncated]`
  }

  /**
   * Extract the final context summary from the scout's messages.
   * The last assistant text response is the summary.
   */
  private buildResult(
    status: 'completed' | 'timeout',
    messages: Message[],
    toolExecutions: ScoutToolExecution[],
    startMs: number,
    roundsUsed: number,
    tokensUsed: number,
  ): ScoutResult {
    // Find the last assistant response (text content, not tool_use)
    let context = ''
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      if (msg.role !== 'assistant') continue

      if (typeof msg.content === 'string') {
        context = msg.content.trim()
        break
      }

      // Content blocks — extract text blocks
      if (Array.isArray(msg.content)) {
        const textBlocks = msg.content
          .filter((b: any) => b.type === 'text')
          .map((b: any) => b.text)
        context = textBlocks.join('\n').trim()
        if (context) break
      }
    }

    // Enforce max context chars
    if (context.length > this.config.maxContextChars) {
      context = `${context.slice(0, this.config.maxContextChars)  }\n\n... [scout context truncated]`
    }

    const durationMs = Date.now() - startMs

    this.emitEvent('scout:completed', {
      sessionId: '',  // Will be set by caller
      contextLength: context.length,
      toolCalls: toolExecutions.length,
      durationMs,
      roundsUsed,
    })

    return {
      status,
      context,
      toolExecutions,
      durationMs,
      roundsUsed,
      tokensUsed,
    }
  }

  /**
   * Emit a scout event on the EventBus.
   */
  private emitEvent(type: string, data: Record<string, unknown>): void {
    if (!this.eventBus) return
    try {
      this.eventBus.emit({
        type,
        ...data,
        timestamp: new Date(),
      } as any)
    } catch {
      // Best-effort — don't crash the scout for event emission failures
    }
  }
}
