/**
 * Tool Loop
 * 
 * Explicit tool execution loop with retry, timeout, overflow recovery,
 * mid-loop context trimming, and tool filler stripping.
 */

import type { IProvider, CompletionChunk, Message as ProviderMessage, ContentBlock, ImageAttachment } from '../../../types/runtime.js'
import type {
  Message,
  ToolCall,
  ToolResult,
  ToolExecution,
  IToolExecutor,
  ToolContext,
  ILogger,
  StreamEventCallback
} from '../session/types.js'

import { ContextOverflowError, isOverflowError, reclassifyAsOverflow, stripToolFiller, hasQuestionResult, buildToolUseMapFromMessages } from './overflow.js'
import { CHARS_PER_TOKEN } from '../../intelligence/shared/token-estimation.js'
import { isWriteTool, isReadTool, isShellTool, shortenPath } from '../../intelligence/thalamus/classifier.js'

export interface ToolLoopOptions {
  maxRounds: number;
  toolTimeoutMs: number;
  streamTimeoutMs: number;
  /** Maximum chars for the tool-loop message array before mid-loop trimming. Default 120_000. */
  midLoopMaxChars?: number;
}

export interface ToolLoopResult {
  content: string;
  tokensUsed: number;
  toolExecutions: ToolExecution[];
  roundsUsed: number;
}

export interface StreamResult {
  content: string;
  toolCalls?: ToolCall[];
  tokensUsed: number;
  thinkingBlocks?: string[];
}

/**
 * Executes the tool loop for provider completions
 */
export class ToolLoop {
  private options: ToolLoopOptions;
  private toolExecutor: IToolExecutor;
  private logger: ILogger;
  private toolSchemasGetter: () => Array<{ name: string; description: string; input_schema: Record<string, unknown> }> | undefined;
  
  constructor(
    toolExecutor: IToolExecutor,
    options: ToolLoopOptions,
    logger: ILogger,
    toolSchemas?: (() => Array<{ name: string; description: string; input_schema: Record<string, unknown> }> | undefined) | Array<{ name: string; description: string; input_schema: Record<string, unknown> }>
  ) {
    this.toolExecutor = toolExecutor;
    this.options = options;
    this.logger = logger;
    // Accept either a getter function or a static array
    this.toolSchemasGetter = typeof toolSchemas === 'function'
      ? toolSchemas
      : () => toolSchemas;
  }
  
  /** Get/set max tool loop rounds */
  get maxRounds(): number { return this.options.maxRounds; }
  set maxRounds(value: number) { this.options.maxRounds = value; }
  
  /**
   * Run the tool loop
   */
  async run(
    provider: IProvider,
    messages: Message[],
    model: string,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
    onStreamEvent?: StreamEventCallback,
    sessionId?: string,
  ): Promise<ToolLoopResult> {
    const executions: ToolExecution[] = [];
    let round = 0;
    let totalTokens = 0;
    let lastContent = '';
    let overflowRetried = false;
    const lastThinkingBlocks: string[] = [];
    
    while (round < this.options.maxRounds) {
      round++;
      
      this.logger.debug(`Tool loop round ${round}/${this.options.maxRounds}`, {
        messageCount: messages.length
      });
      
      // Stream completion from provider, with overflow recovery
      let streamResult: StreamResult;
      try {
        streamResult = await this.streamWithTimeout(
          provider,
          messages,
          model,
          attachments,
          signal,
          onStreamEvent,
          sessionId,
        );
      } catch (err) {
        // Reclassify generic errors that carry overflow messages
        const classified = reclassifyAsOverflow(err as Error)
        if (classified instanceof ContextOverflowError && !overflowRetried) {
          overflowRetried = true
          this.logger.warn('Context overflow detected — applying emergency trim and retrying', {
            round, messageCount: messages.length,
          })
          // Emergency trim: keep system msgs + first user + last 2 tool pairs
          this.emergencyTrim(messages)
          continue // Retry the round
        }
        throw classified
      }
      
      totalTokens += streamResult.tokensUsed;
      lastContent = streamResult.content;
      
      if (streamResult.thinkingBlocks) {
        lastThinkingBlocks.push(...streamResult.thinkingBlocks);
      }
      
      // Check for tool calls
      if (!streamResult.toolCalls || streamResult.toolCalls.length === 0) {
        // No tools - we're done
        this.logger.debug('Tool loop complete - no tools called', {
          roundsUsed: round,
          totalTokens
        });
        
        return {
          content: streamResult.content,
          tokensUsed: totalTokens,
          toolExecutions: executions,
          roundsUsed: round
        };
      }
      
      // Execute tools
      this.logger.debug('Executing tools', {
        toolCount: streamResult.toolCalls.length,
        toolNames: streamResult.toolCalls.map(t => t.name)
      });
      
      const results = await this.executeTools(
        streamResult.toolCalls,
        signal
      );
      
      executions.push(...results);
      
      // Emit tool_result events for each execution
      if (onStreamEvent) {
        for (const exec of results) {
          onStreamEvent('tool_result', { toolResult: exec });
        }
      }
      
      // Add assistant message with tool calls (strip filler text)
      const cleanedContent = stripToolFiller(streamResult.content || '')
      messages.push({
        role: 'assistant',
        content: cleanedContent,
        timestamp: Date.now(),
        toolCalls: streamResult.toolCalls
      });

      // Build reasoning prefix from accumulated thinking blocks for this round
      const reasoningPrefix = lastThinkingBlocks.length > 0
        ? `[Previous reasoning: ${lastThinkingBlocks.join('').trim()}]\n\n`
        : ''

      // Add tool results as user message
      messages.push({
        role: 'user',
        content: '',
        timestamp: Date.now(),
        toolResults: results.map((r, idx) => {
          const tc = streamResult.toolCalls![idx]
          const isQuestion = tc?.name === 'question' || tc?.name === 'AskUserQuestion'
          return {
            toolCallId: r.toolCallId,
            toolName: r.toolName,
            content: isQuestion && reasoningPrefix
              ? `${reasoningPrefix}${r.content}`
              : r.content,
            isError: r.isError
          }
        })
      });

      // Clear thinking blocks for this round so they don't accumulate into future rounds
      lastThinkingBlocks.length = 0

      // Mid-loop context trim: drop oldest tool pairs when over budget
      const midLoopMaxChars = this.options.midLoopMaxChars ?? 120_000
      this.midLoopTrim(messages, midLoopMaxChars)
    }
    
    // Max rounds reached
    this.logger.warn(`Tool loop reached max rounds (${this.options.maxRounds})`);
    
    return {
      content: `${lastContent  }\n\n[Note: Reached maximum tool execution rounds]`,
      tokensUsed: totalTokens,
      toolExecutions: executions,
      roundsUsed: round
    };
  }
  
  /**
   * Stream completion from provider with timeout
   */
  private async streamWithTimeout(
    provider: IProvider,
    messages: Message[],
    model: string,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
    onStreamEvent?: StreamEventCallback,
    sessionId?: string,
  ): Promise<StreamResult> {
    return this.withTimeout(
      this.doStream(provider, messages, model, attachments, signal, onStreamEvent, sessionId),
      this.options.streamTimeoutMs,
      'Provider stream timeout'
    );
  }
  
  /**
   * Actually stream from provider
   */
  private async doStream(
    provider: IProvider,
    messages: Message[],
    model: string,
    attachments?: ImageAttachment[],
    signal?: AbortSignal,
    onStreamEvent?: StreamEventCallback,
    sessionId?: string,
  ): Promise<StreamResult> {
    const chunks: string[] = [];
    const thinkingBlocks: string[] = [];
    const toolCalls: ToolCall[] = [];
    let tokensUsed = 0;
    
    const stream = provider.complete(
      this.toProviderMessages(messages),
      {
        model: model.split('/')[1] ?? model,
        stream: true,
        source: 'session-pipeline',
        tools: this.toolSchemasGetter(),
        sessionId,
      },
      attachments,
      signal,
    );
    
    for await (const chunk of stream) {
      // Check cancellation
      if (signal?.aborted) {
        throw new Error('Stream cancelled');
      }
      
      switch (chunk.type) {
        case 'token':
          chunks.push(chunk.text ?? '')
          tokensUsed += chunk.tokensUsed ?? Math.ceil((chunk.text?.length ?? 0) / CHARS_PER_TOKEN)
          onStreamEvent?.('token', { token: chunk.text ?? '' })
          break

        case 'thinking':
          thinkingBlocks.push(chunk.text ?? '')
          tokensUsed += chunk.tokensUsed ?? Math.ceil((chunk.text?.length ?? 0) / CHARS_PER_TOKEN)
          onStreamEvent?.('thinking', { token: chunk.text ?? '' })
          break
          
        case 'tool_use':
          if (chunk.toolCall) {
            toolCalls.push(chunk.toolCall);
            onStreamEvent?.('tool_call', { toolCall: chunk.toolCall });
          }
          break;
          
        case 'error':
          throw new Error(chunk.error ?? 'Provider error');
      }
    }
    
    return {
      content: chunks.join(''),
      toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
      tokensUsed,
      thinkingBlocks: thinkingBlocks.length > 0 ? thinkingBlocks : undefined
    };
  }
  
  /**
   * Execute all tool calls
   */
  private async executeTools(
    calls: ToolCall[],
    signal?: AbortSignal
  ): Promise<ToolExecution[]> {
    // Execute tools in parallel
    const results = await Promise.all(
      calls.map(call => this.executeTool(call, signal))
    );
    
    return results;
  }
  
  /**
   * Execute a single tool
   */
  private async executeTool(
    call: ToolCall,
    signal?: AbortSignal
  ): Promise<ToolExecution> {
    const start = Date.now();
    
    try {
      // Check if tool is available
      if (!this.toolExecutor.isAvailable(call.name)) {
        return {
          toolCallId: call.id,
          toolName: call.name,
          content: `Error: Tool '${call.name}' is not available`,
          isError: true,
          durationMs: Date.now() - start
        };
      }
      
      // Execute with timeout
      const result = await this.withTimeout(
        this.toolExecutor.execute(call.name, call.input, {
          toolCallId: call.id,
          sessionId: 'unknown',
          signal
        }),
        this.options.toolTimeoutMs,
        `Tool '${call.name}' timeout`
      );
      
      return {
        toolCallId: call.id,
        toolName: call.name,
        content: result.content,
        isError: result.isError,
        durationMs: Date.now() - start
      };
      
    } catch (error) {
      this.logger.error('Tool execution failed', {
        tool: call.name,
        error: String(error)
      });
      
      return {
        toolCallId: call.id,
        toolName: call.name,
        content: `Error: ${error}`,
        isError: true,
        durationMs: Date.now() - start
      };
    }
  }
  
  /**
   * Convert internal messages to provider Message format.
   * Tool call/result messages need ContentBlock[] content rather than plain strings.
   */
  private toProviderMessages(messages: Message[]): ProviderMessage[] {
    return messages.map(m => {
      // Assistant message with tool calls → use ContentBlock[] format
      if (m.role === 'assistant' && m.toolCalls && m.toolCalls.length > 0) {
        const blocks: ContentBlock[] = [];
        if (m.content) {
          if (typeof m.content === 'string') {
            blocks.push({ type: 'text', text: m.content });
          } else {
            blocks.push(...m.content);
          }
        }
        for (const tc of m.toolCalls) {
          blocks.push({
            type: 'tool_use',
            id: tc.id,
            name: tc.name,
            input: tc.input as Record<string, unknown>
          });
        }
        return { role: m.role, content: blocks };
      }

      // User message with tool results → use ContentBlock[] format
      if (m.role === 'user' && m.toolResults && m.toolResults.length > 0) {
        const blocks: ContentBlock[] = m.toolResults.map(tr => ({
          type: 'tool_result' as const,
          tool_use_id: tr.toolCallId,
          content: tr.content,
          is_error: tr.isError,
          tool_name: tr.toolName,
        }));
        return { role: m.role, content: blocks };
      }

      // Normal text message
      return {
        role: m.role,
        content: typeof m.content === 'string' ? m.content : m.content
      };
    });
  }

  /**
   * Promise with timeout wrapper
   */
  private withTimeout<T>(
    promise: Promise<T>,
    timeoutMs: number,
    message: string
  ): Promise<T> {
    let timer: ReturnType<typeof setTimeout>;
    return Promise.race([
      promise.finally(() => clearTimeout(timer)),
      new Promise<T>((_, reject) => {
        timer = setTimeout(() => reject(new Error(message)), timeoutMs);
      })
    ]);
  }

  /**
   * Emergency trim: aggressive context reduction after overflow error.
   * Keeps system messages + first user message + last 2 tool pairs.
   */
  private emergencyTrim(messages: Message[]): void {
    const systemMsgs = messages.filter(m => m.role === 'system')
    const firstUser = messages.find(m => m.role === 'user')
    const nonSystem = messages.filter(m => m.role !== 'system')

    // Keep last 4 non-system messages (2 tool pairs: assistant+user, assistant+user)
    const recentPairs = nonSystem.slice(-4)

    const kept: Message[] = [...systemMsgs]
    if (firstUser && !recentPairs.includes(firstUser)) {
      kept.push(firstUser)
    }
    kept.push(...recentPairs)

    messages.length = 0
    messages.push(...kept)

    this.logger.info('Emergency trim applied', {
      keptMessages: messages.length,
      keptSystem: systemMsgs.length,
    })
  }

  /**
    * Mid-loop context trim: drop oldest tool pairs when the message
    * array exceeds the character budget. Keeps at least 3 recent tool pairs.
    * Question tool results are treated as user messages and never trimmed.
    */
  private midLoopTrim(messages: Message[], maxChars: number): void {
    const chars = this.estimateChars(messages)
    if (chars <= maxChars) return

    // Count trimmable tool pairs (exclude pairs with question results)
    let toolPairCount = 0
    const systemEnd = messages.findIndex(m => m.role !== 'system')
    const preserveHead = Math.max(0, systemEnd)

    for (let i = preserveHead; i < messages.length; i++) {
      const m = messages[i]
      if (m.role === 'assistant' && m.toolCalls && m.toolCalls.length > 0) {
        // Skip if the following user message contains a question result
        if (i + 1 < messages.length && hasQuestionResult(messages[i + 1])) continue
        toolPairCount++
      }
    }

    const KEEP_PAIRS = 3
    if (toolPairCount <= KEEP_PAIRS) return

    let pairsToRemove = toolPairCount - KEEP_PAIRS
    const toRemove: number[] = []

    for (let i = preserveHead; i < messages.length - 1 && pairsToRemove > 0; i++) {
      const m = messages[i]
      if (m.role === 'assistant' && m.toolCalls && m.toolCalls.length > 0) {
        // Skip pairs containing question results — they're user messages
        if (i + 1 < messages.length && hasQuestionResult(messages[i + 1])) continue

        toRemove.push(i)
        // The next message should be the tool results
        if (i + 1 < messages.length - 1 && messages[i + 1].role === 'user') {
          toRemove.push(i + 1)
        }
        pairsToRemove--

        // Estimate new char count after removal
        const removedChars = toRemove.reduce((s, idx) => s + this.msgChars(messages[idx]), 0)
        if (chars - removedChars <= maxChars) break
      }
    }

    if (toRemove.length > 0) {
      // Generate a synthetic summary of the work being dropped so the model
      // retains context about what it already did. This prevents the agent
      // from re-reading files or re-running commands it already executed.
      const summary = this.buildMidLoopSummary(messages, toRemove)

      const removeSet = new Set(toRemove)
      const trimmed = messages.filter((_, idx) => !removeSet.has(idx))

      // Find a safe insertion point that preserves the user/assistant alternation.
      // Look for a user→assistant boundary and insert after the assistant message.
      let insertIdx = -1
      for (let i = 0; i < trimmed.length - 1; i++) {
        if (trimmed[i].role === 'user' && trimmed[i + 1].role === 'assistant') {
          // Insert after this assistant message
          insertIdx = i + 1
          break
        }
      }
      // Fallback: insert after the first non-system message
      if (insertIdx < 0) {
        insertIdx = trimmed.findIndex(m => m.role !== 'system')
        if (insertIdx < 0) insertIdx = trimmed.length - 1
      }

      const summaryMsg: Message = {
        role: 'user',
        content: summary,
        timestamp: Date.now(),
      }

      // Insert after the found boundary. If the boundary is an assistant message,
      // inserting a user message after it preserves alternation.
      // If the next message is also user, we merge or skip to avoid breaking alternation.
      const nextMsg = insertIdx + 1 < trimmed.length ? trimmed[insertIdx + 1] : null
      if (nextMsg && nextMsg.role === 'user') {
        // Can't insert a user message between user messages.
        // If the next message has toolResults, prepend as a synthetic system-style
        // note in the content string. If it's plain text, prepend directly.
        if (nextMsg.toolResults && nextMsg.toolResults.length > 0) {
          // Prepend to the first tool result's content
          nextMsg.toolResults[0].content = `${summary}\n\n${nextMsg.toolResults[0].content ?? ''}`
        } else if (typeof nextMsg.content === 'string') {
          nextMsg.content = `${summary}\n\n${nextMsg.content}`
        } else if (Array.isArray(nextMsg.content)) {
          // Insert a text block at the front
          nextMsg.content = [{ type: 'text' as const, text: summary }, ...nextMsg.content]
        }
      } else {
        // Safe to insert as a user message after the assistant boundary
        trimmed.splice(insertIdx + 1, 0, summaryMsg)
      }

      messages.length = 0
      messages.push(...trimmed)

      this.logger.debug('Mid-loop context trim: dropped tool pairs with summary injection', {
        removed: toRemove.length,
        summaryChars: summary.length,
        oldChars: chars,
        newChars: this.estimateChars(messages),
      })
    }
  }

  /**
   * Build a compact summary of tool pairs being dropped in mid-loop trim.
   * Extracts tool names, file paths, and key findings so the model has
   * enough context to continue without re-doing work.
   */
  private buildMidLoopSummary(messages: Message[], removedIndices: number[]): string {
    const tools = new Set<string>()
    const filesRead: string[] = []
    const filesWritten: string[] = []
    const errors: string[] = []
    const seenFilesRead = new Set<string>()
    const seenFilesWritten = new Set<string>()
    let pairCount = 0

    for (const idx of removedIndices) {
      const m = messages[idx]
      if (!m) continue

      // Extract from tool_call messages
      if (m.role === 'assistant' && m.toolCalls) {
        for (const tc of m.toolCalls) {
          const name = tc.name ?? ''
          if (name) tools.add(name)
          pairCount++

          // Extract file paths from tool input
          const input = tc.input
          if (input && typeof input === 'object') {
            const fp = (input as any).filePath ?? (input as any).path ?? (input as any).file_path ?? (input as any).relative_path ?? ''
            if (fp && typeof fp === 'string') {
              const short = shortenPath(fp)
              if (isWriteTool(name)) {
                if (!seenFilesWritten.has(fp)) { seenFilesWritten.add(fp); filesWritten.push(short) }
              } else if (isReadTool(name)) {
                if (!seenFilesRead.has(fp)) { seenFilesRead.add(fp); filesRead.push(short) }
              }
            }
            // Extract command
            if (isShellTool(name) && (input as any).command) {
              tools.add(`${name}: ${String((input as any).command).split('\n')[0]?.slice(0, 40)}`)
            }
          }
        }
      }

      // Extract from tool_result messages
      if (m.role === 'user' && m.toolResults) {
        for (const tr of m.toolResults) {
          if (tr.isError) {
            const firstLine = tr.content?.split('\n')[0]?.slice(0, 80) ?? ''
            if (firstLine && errors.length < 2) errors.push(firstLine)
          }
        }
      }
    }

    const parts: string[] = []
    const callCount = Math.ceil(pairCount / 2)
    if (filesRead.length > 0) parts.push(`read ${filesRead.slice(0, 5).join(', ')}`)
    if (filesWritten.length > 0) parts.push(`wrote ${filesWritten.slice(0, 3).join(', ')}`)
    if (errors.length > 0) parts.push(`errors: ${errors.join('; ')}`)

    const toolNames = Array.from(tools).slice(0, 5)
    if (toolNames.length > 0 && filesRead.length === 0 && filesWritten.length === 0) {
      parts.push(`tools used: ${toolNames.join(', ')}`)
    }

    if (parts.length === 0) {
      return `[Prior work: ${callCount} tool call${callCount !== 1 ? 's' : ''} completed. Do not repeat these operations unless the context has changed.]`
    }
    return `[Prior work: ${callCount} tool call${callCount !== 1 ? 's' : ''} — ${parts.join('. ')}. Do not repeat these operations unless the context has changed.]`
  }

  private estimateChars(messages: Message[]): number {
    return messages.reduce((s, m) => s + this.msgChars(m), 0)
  }

  private msgChars(msg: Message): number {
    if (typeof msg.content === 'string') return msg.content.length
    if (!Array.isArray(msg.content)) return 50
    return msg.content.reduce((s: number, b: any) => {
      if (b.type === 'text') return s + (b.text?.length ?? 0)
      return s + 100
    }, 0)
  }
}

/**
 * Create tool loop with safe defaults
 */
export function createSafeToolLoop(
  toolExecutor: IToolExecutor,
  logger: ILogger
): ToolLoop {
  return new ToolLoop(
    toolExecutor,
    {
      maxRounds: 8,
      toolTimeoutMs: 60000,
      streamTimeoutMs: 120000
    },
    logger
  );
}
