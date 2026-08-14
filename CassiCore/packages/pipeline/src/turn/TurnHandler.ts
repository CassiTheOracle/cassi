/**
 * Turn Handler
 * 
 * Main entry point for turn processing - integrates all components
 */

import { TurnProcessingError, ProviderNotFoundError } from '../session/types.js'

import { ContextWindow } from './ContextWindow.js'
import { MessageBuilder } from './MessageBuilder.js'
import { ToolLoop, createSafeToolLoop } from './ToolLoop.js'
import { CHARS_PER_TOKEN } from '../../intelligence/shared/token-estimation.js'

import type { IProvider } from '../../../types/runtime.js';
import type {
  SessionState,
  TurnRequest,
  TurnResult,
  TurnHandlerOptions,
  IToolExecutor,
  ILogger,
  StreamEventCallback,
  Message,
} from '../session/types.js';
import type { IEventBus } from '../../../types/interfaces.js';

/* ------------------------------------------------------------------ */
/*  Hook types                                                         */
/* ------------------------------------------------------------------ */

/**
 * Pipeline hook points for extensibility.
 * These replace the old middleware chain with targeted, composable callbacks.
 */
export interface PipelineHooks {
  /**
   * Called before each turn is processed.
   * Can modify the messages array or return early with a result.
   * Return undefined to continue normal processing.
   */
  onPreTurn?: (session: SessionState, messages: Message[]) => Promise<TurnResult | undefined>;

  /**
   * Called after each tool execution batch completes.
   * Can inspect results and optionally inject additional context.
   */
  onPostTool?: (session: SessionState, toolNames: string[], messages: Message[]) => Promise<void>;

  /**
   * Called before the final response is returned.
   * Can modify the response text.
   */
  onPreResponse?: (session: SessionState, result: TurnResult) => Promise<TurnResult>;
}

/**
 * Handles turn processing end-to-end
 */
export class TurnHandler {
  private providers: Map<string, IProvider>;
  private toolExecutor: IToolExecutor;
  private logger: ILogger;
  private bus?: IEventBus;
  private hooks: PipelineHooks;
  
  private messageBuilder: MessageBuilder;
  private contextWindow: ContextWindow;
  private toolLoop: ToolLoop;
  
  constructor(options: TurnHandlerOptions & { bus?: IEventBus; hooks?: PipelineHooks }) {
    this.providers = options.providers;
    this.toolExecutor = options.toolExecutor;
    this.logger = options.logger;
    this.bus = options.bus;
    this.hooks = options.hooks ?? {};
    
    // Initialize components
    this.messageBuilder = new MessageBuilder({
      logger: options.logger.child('message-builder'),
      includeSessionMarker: true
    });
    
    this.contextWindow = new ContextWindow({
      maxTokens: options.contextWindowTokens ?? 200000,
      charsPerToken: CHARS_PER_TOKEN,
      preserveSystemMessages: true,
      logger: options.logger.child('context-window'),
    })
    
    // Resolve tool schemas: accept either a static array or a getter function
    const rawSchemas = options.toolSchemas;
    const toolSchemasGetter: (() => Array<{ name: string; description: string; input_schema: Record<string, unknown> }> | undefined) = typeof rawSchemas === 'function'
      ? rawSchemas
      : () => rawSchemas;
    
    this.toolLoop = new ToolLoop(
      options.toolExecutor,
      {
        maxRounds: options.maxToolRounds ?? 8,
        toolTimeoutMs: options.toolTimeoutMs ?? 60000,
        streamTimeoutMs: 120000
      },
      options.logger.child('tool-loop'),
      toolSchemasGetter
    );
    
    // Resolve current count for init log
    const currentSchemas = toolSchemasGetter();
    this.logger.info('TurnHandler initialized', {
      providerCount: options.providers.size,
      maxToolRounds: options.maxToolRounds ?? 8,
      contextWindowTokens: options.contextWindowTokens ?? 200000,
      toolCount: currentSchemas?.length ?? 0
    });
  }
  
  /**
   * Process a turn
   */
  async process(
    session: SessionState,
    request: TurnRequest,
    onStreamEvent?: StreamEventCallback
  ): Promise<TurnResult> {
    const startTime = Date.now();
    const [providerId = 'unknown'] = session.model.split('/');
    
    // Emit turn:start event
    this.bus?.emit({ type: 'turn:start', sessionId: session.id, message: request.content, timestamp: new Date() } as any)
    
    try {
      // 1. Build messages
      const messages = this.messageBuilder.build(session, request);
      
      // 2. Apply context window
      const trimmed = this.contextWindow.trim(messages);
      const contextTokens = this.contextWindow.estimateTokens(trimmed);

      // Hook: onPreTurn — can short-circuit with an early result
      if (this.hooks.onPreTurn) {
        const earlyResult = await this.hooks.onPreTurn(session, trimmed)
        if (earlyResult) return earlyResult
      }
      
      // 3. Resolve provider
      const provider = this.resolveProvider(session.model);
      
      // 4. Run tool loop
      const loopResult = await this.toolLoop.run(
        provider,
        trimmed,
        session.model,
        request.attachments,
        request.signal,
        onStreamEvent,
        session.id,
      );
      
      const durationMs = Date.now() - startTime;
      
      this.logger.info('Turn processed', {
        sessionId: session.id,
        provider: providerId,
        model: session.model,
        durationMs,
        contextTokens: contextTokens >= 1000
          ? `${(contextTokens / 1000).toFixed(1)}k`
          : String(contextTokens),
        tokensUsed: loopResult.tokensUsed,
        toolRounds: loopResult.roundsUsed,
        toolCount: loopResult.toolExecutions.length
      });
      
      // 5. Format result
      const result: TurnResult = {
        response: loopResult.content,
        tokensUsed: loopResult.tokensUsed,
        model: session.model,
        durationMs,
        toolCalls: loopResult.toolExecutions.length > 0
          ? loopResult.toolExecutions
          : undefined
      };

      // Hook: onPreResponse — can modify the result before returning
      const finalResult = this.hooks.onPreResponse
        ? await this.hooks.onPreResponse(session, result)
        : result

      // Emit turn:end event
      this.bus?.emit({ type: 'turn:end', sessionId: session.id, response: finalResult.response, durationMs, timestamp: new Date() } as any)

      return finalResult;
      
    } catch (error) {
      const durationMs = Date.now() - startTime;
      
      this.logger.error('Turn processing failed', {
        sessionId: session.id,
        provider: providerId,
        model: session.model,
        durationMs,
        error: String(error)
      });
      
      throw new TurnProcessingError(
        `Failed to process turn: ${error}`,
        { cause: error }
      );
    }
  }
  
  /**
   * Process with custom options (for one-off changes)
   */
  async processWithOptions(
    session: SessionState,
    request: TurnRequest,
    overrides: {
      model?: string;
      systemPrompt?: string;
      maxToolRounds?: number;
    },
    onStreamEvent?: StreamEventCallback
  ): Promise<TurnResult> {
    // Create temporary session with overrides
    const tempSession: SessionState = {
      ...session,
      model: overrides.model ?? session.model,
      systemPrompt: overrides.systemPrompt ?? session.systemPrompt
    };
    
    // Temporarily modify tool loop max rounds if specified
    const originalMaxRounds = this.toolLoop.maxRounds;
    if (overrides.maxToolRounds !== undefined) {
      this.toolLoop.maxRounds = overrides.maxToolRounds;
    }
    
    try {
      return await this.process(tempSession, request, onStreamEvent);
    } finally {
      // Restore original max rounds
      this.toolLoop.maxRounds = originalMaxRounds;
    }
  }
  
  /**
   * Quick check if a provider is available
   */
  isProviderAvailable(modelSpec: string): boolean {
    try {
      const [providerId] = modelSpec.split('/');
      return this.providers.has(providerId);
    } catch {
      return false;
    }
  }
  
  /**
   * Get available providers
   */
  getAvailableProviders(): string[] {
    return Array.from(this.providers.keys());
  }
  
  /**
   * Get handler stats
   */
  getStats(): {
    providerCount: number;
    availableTools: string[];
  } {
    return {
      providerCount: this.providers.size,
      availableTools: []  // Would need to query tool executor
    };
  }

  /**
   * Queue content for injection on the next turn.
   * Delegates to the MessageBuilder's injection queue.
   */
  injectOnNextTurn(content: string): void {
    this.messageBuilder.injectOnNextTurn(content)
  }

  /** Hot-swap the context window (e.g., for changing token limits at runtime). */
  setContextWindow(contextWindow: ContextWindow): void {
    this.contextWindow = contextWindow
  }

  /** Set or update pipeline hooks at runtime. */
  setHooks(hooks: PipelineHooks): void {
    this.hooks = { ...this.hooks, ...hooks }
  }
  
  // Private Methods
  
  private resolveProvider(modelSpec: string): IProvider {
    const parts = modelSpec.split('/');
    const providerId = parts[0];
    
    // Direct lookup by provider ID (handles 'kimi-coding/k2p5' → 'kimi-coding')
    const provider = this.providers.get(providerId);
    if (provider) {
      return provider;
    }

    // Bare model name without provider prefix (e.g., 'k2p5' instead of 'kimi-coding/k2p5')
    // Search all registered providers for one that supports this model
    if (!modelSpec.includes('/')) {
      for (const [pid, prov] of this.providers) {
        const models = (prov as any).models || (prov as any).modelIds || [];
        if (Array.isArray(models) && models.some((m: any) =>
          (typeof m === 'string' ? m : m?.id) === modelSpec
        )) {
          this.logger.warn('resolveProvider: bare model name resolved', {
            model: modelSpec, resolvedProvider: pid,
            hint: 'Use fully-qualified "provider/model" format'
          });
          return prov;
        }
      }
      // Last resort: return the first registered provider
      const firstProvider = this.providers.values().next().value;
      if (firstProvider) {
        this.logger.warn('resolveProvider: bare model name, using first provider', {
          model: modelSpec, provider: this.providers.keys().next().value,
        });
        return firstProvider;
      }
    }
    
    throw new ProviderNotFoundError(providerId);
  }
}

/**
 * Factory function for creating TurnHandler
 */
export function createTurnHandler(
  options: TurnHandlerOptions
): TurnHandler {
  return new TurnHandler(options);
}

/**
 * Create handler with safe defaults
 */
export function createSafeTurnHandler(
  providers: Map<string, IProvider>,
  toolExecutor: IToolExecutor,
  logger: ILogger
): TurnHandler {
  return new TurnHandler({
    providers,
    toolExecutor,
    logger,
    maxToolRounds: 8,
    contextWindowTokens: 100000,  // Conservative default
    toolTimeoutMs: 60000
  });
}
