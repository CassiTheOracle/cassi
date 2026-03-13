/**
 * Tool Loop
 * 
 * Explicit tool execution loop with retry and timeout handling
 */

import type { IProvider, CompletionChunk, Message as ProviderMessage, ContentBlock } from '../../../types/runtime.js';
import type {
  Message,
  ToolCall,
  ToolResult,
  ToolExecution,
  IToolExecutor,
  ToolContext,
  ILogger,
  StreamEventCallback
} from '../session/types.js';

export interface ToolLoopOptions {
  maxRounds: number;
  toolTimeoutMs: number;
  streamTimeoutMs: number;
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
  private toolSchemas?: Array<{ name: string; description: string; input_schema: Record<string, unknown> }>;
  
  constructor(
    toolExecutor: IToolExecutor,
    options: ToolLoopOptions,
    logger: ILogger,
    toolSchemas?: Array<{ name: string; description: string; input_schema: Record<string, unknown> }>
  ) {
    this.toolExecutor = toolExecutor;
    this.options = options;
    this.logger = logger;
    this.toolSchemas = toolSchemas;
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
    signal?: AbortSignal,
    onStreamEvent?: StreamEventCallback
  ): Promise<ToolLoopResult> {
    const executions: ToolExecution[] = [];
    let round = 0;
    let totalTokens = 0;
    let lastContent = '';
    const lastThinkingBlocks: string[] = [];
    
    while (round < this.options.maxRounds) {
      round++;
      
      this.logger.debug(`Tool loop round ${round}/${this.options.maxRounds}`, {
        messageCount: messages.length
      });
      
      // Stream completion from provider
      const streamResult = await this.streamWithTimeout(
        provider,
        messages,
        model,
        signal,
        onStreamEvent
      );
      
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
      
      // Add assistant message with tool calls
      messages.push({
        role: 'assistant',
        content: streamResult.content,
        timestamp: Date.now(),
        toolCalls: streamResult.toolCalls
      });
      
      // Add tool results as user message
      messages.push({
        role: 'user',
        content: '',
        timestamp: Date.now(),
        toolResults: results.map(r => ({
          toolCallId: r.toolCallId,
          content: r.content,
          isError: r.isError
        }))
      });
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
    signal?: AbortSignal,
    onStreamEvent?: StreamEventCallback
  ): Promise<StreamResult> {
    return this.withTimeout(
      this.doStream(provider, messages, model, signal, onStreamEvent),
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
    signal?: AbortSignal,
    onStreamEvent?: StreamEventCallback
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
        tools: this.toolSchemas,
      }
    );
    
    for await (const chunk of stream) {
      // Check cancellation
      if (signal?.aborted) {
        throw new Error('Stream cancelled');
      }
      
      switch (chunk.type) {
        case 'token':
          chunks.push(chunk.text ?? '');
          tokensUsed += chunk.tokensUsed ?? Math.ceil((chunk.text?.length ?? 0) / 4);
          onStreamEvent?.('token', { token: chunk.text ?? '' });
          break;
          
        case 'thinking':
          thinkingBlocks.push(chunk.text ?? '');
          tokensUsed += chunk.tokensUsed ?? Math.ceil((chunk.text?.length ?? 0) / 4);
          onStreamEvent?.('thinking', { token: chunk.text ?? '' });
          break;
          
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
          is_error: tr.isError
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
