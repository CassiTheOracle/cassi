/**
 * Session Pipeline
 *
 * Integration point for session pipeline into the Daemon
 * with feature flag support
 */

import { homedir } from 'node:os';
import { join } from 'node:path';

import { buildSystemPrompt } from '../../workspace/loader.js';


import {
  SessionManager,
  SQLiteSessionStore,
  TurnHandler,
  IntelligenceLayer,
  type SessionState,
  type TurnRequest,
  type TurnResult,
  type TurnMetadata,
  type StreamEventCallback,
  type IntelligenceContext
} from '../index.js';
import { getModelSpec, MODEL_DEFAULTS } from '../../config/system-settings.js';

import type { IMemory } from '../../../types/intelligence.js';
import type { IConfig, ILogger, IEventBus } from '../../../types/interfaces.js';
import type { IProvider } from '../../../types/runtime.js';

// Intelligence module interfaces (from existing code)
interface DialecticSystem {
  processTurn: (...args: unknown[]) => Promise<unknown>;
}

interface ThinkerModule {
  getRecentInsights?(limit: number): Array<{ insight: string; level: string; timestamp: number }>;
  getContextInjection?(sessionId: string): string | undefined;
}

interface SubconsciousModule {
  getContextInjection?(sessionId: string): string | undefined;
}

export interface SessionPipelineOptions {
  config: IConfig;
  logger: ILogger;
  providers: Map<string, IProvider>;
  toolExecutor: {
    execute: (name: string, input: unknown, context: unknown) => Promise<{ content: string; isError: boolean }>;
    isAvailable: (name: string) => boolean;
  };
  /** Tool registry for passing tool schemas to LLM providers.
   *  Accepts a getter function for live registry updates, or a static array. */
  toolSchemas?: (() => Array<{ name: string; description: string; input_schema: Record<string, unknown> }>) | Array<{ name: string; description: string; input_schema: Record<string, unknown> }>;
  intelligence: {
    memory: IMemory;
    dialectic: DialecticSystem;
    thinker: ThinkerModule;
    subconscious: SubconsciousModule;
    locusBridge?: { sparkFromUserPrompt(sessionId: string, content: string, goal?: string): unknown };
  };
  eventBus?: IEventBus;
  /** Unified injection aggregator for Corpus, SessionDigest, Optimizer, Dreamer, etc. */
  injectionAggregator?: { aggregate(sessionId: string, turnContext?: unknown): Promise<Array<{ content: string; source: string }>> };
}

// Shared options for both processMessage and processTurn
interface TurnOptions {
  attachments?: Array<{ mediaType: string; data: string }>;
  signal?: AbortSignal;
  stream?: boolean;
  onStreamEvent?: StreamEventCallback;
  model?: string;
  timeoutMs?: number;
}

export interface TurnExecutionResult {
  response: string;
  sessionId: string;
  model?: string;
  tokensUsed?: number;
  durationMs?: number;
}

/**
 * Manages session pipeline components and provides integration with existing Daemon
 */
export class SessionPipeline {
  private options: SessionPipelineOptions;
  private logger: ILogger;
  private eventBus?: IEventBus;

  // Pipeline components
  private sessionManager?: SessionManager;
  private turnHandler?: TurnHandler;
  private intelligenceLayer?: IntelligenceLayer;
  private store?: SQLiteSessionStore;

  // State
  private initialized = false;
  private systemPrompt = '';

  // Active turn AbortControllers — keyed by sessionId
  private activeControllers = new Map<string, AbortController>();

  constructor(options: SessionPipelineOptions) {
    this.options = options;
    this.logger = options.logger.child('session-pipeline');
    this.eventBus = options.eventBus;
  }

  /**
   * Initialize pipeline components
   */
  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    this.logger.info('Initializing session pipeline');

    // 1. Create store
    const dbPath = join(homedir(), '.cassicore', 'sessions.db');
    this.store = new SQLiteSessionStore({
      dbPath,
      logger: this.logger.child('store'),
      walMode: true
    });
    await this.store.initialize();

    // 2. Resolve default model — prefer config, but validate against available providers
    const configuredProvider = this.options.config.get(
      'intelligence.defaultProvider',
      MODEL_DEFAULTS.main.provider,
    );
    const configuredModel = this.options.config.get(
      'intelligence.defaultModel',
      MODEL_DEFAULTS.main.model,
    );
    const candidateModel = configuredModel.includes('/')
      ? configuredModel
      : `${configuredProvider}/${configuredModel}`;

    // Verify the configured provider is actually available; if not,
    // pick the first registered provider so new sessions don't crash.
    const candidateProviderId = candidateModel.split('/')[0];
    let defaultModel = candidateModel;

    if (!this.options.providers.has(candidateProviderId)) {
      const firstAvailable = this.options.providers.keys().next().value;
      if (firstAvailable) {
        const modelName = candidateModel.split('/').slice(1).join('/') || candidateModel;
        defaultModel = `${firstAvailable}/${modelName}`;
        this.logger.warn('Configured default provider not available, falling back', {
          configured: candidateProviderId,
          fallback: firstAvailable,
          defaultModel,
        });
      }
    }

    // 3. Create session manager
    this.systemPrompt = this.loadSystemPrompt();
    this.sessionManager = new SessionManager({
      store: this.store,
      defaultModel,
      defaultSystemPrompt: this.systemPrompt,
      logger: this.logger.child('session-manager')
    });

    // 4. Create turn handler
    this.turnHandler = new TurnHandler({
      providers: this.options.providers,
      toolExecutor: this.options.toolExecutor as any,
      logger: this.logger.child('turn-handler'),
      maxToolRounds: this.options.config.get('pipeline.maxToolRounds', 8),
      contextWindowTokens: this.options.config.get('pipeline.contextWindowTokens', 200000),
      toolTimeoutMs: this.options.config.get('pipeline.toolTimeoutMs', 60000),
      toolSchemas: this.options.toolSchemas,
      bus: this.eventBus,
    });

    // 5. Create intelligence layer
    this.intelligenceLayer = new IntelligenceLayer({
      sessionManager: this.sessionManager,
      memory: this.options.intelligence.memory as any,
      dialectic: this.options.intelligence.dialectic as any,
      thinker: this.options.intelligence.thinker as any,
      subconscious: this.options.intelligence.subconscious as any,
      logger: this.logger.child('intelligence'),
      concurrency: this.options.config.get('pipeline.intelligenceConcurrency', 3)
    });

    this.initialized = true;

    this.logger.info('Session pipeline initialized', {
      dbPath,
      providerCount: this.options.providers.size
    });
  }

  /**
   * Process a message for a channel+sender pair.
   * Session is looked up or created via the (channelId, senderId) key.
   */
  async processMessage(
    channelId: string,
    senderId: string,
    content: string,
    options?: TurnOptions
  ): Promise<TurnExecutionResult> {
    this.assertInitialized();

    const session = await this.sessionManager!.getOrCreate(channelId, senderId);

    if (options?.model && options.model !== 'unknown') {
      session.model = options.model;
    }

    return this._executeTurn(session, content, options);
  }

  /**
   * Process a turn for a session identified by its ID directly.
   * If no session exists with that ID, one is created using the optional
   * channelId / senderId hints (defaulting to 'system' / 'system').
   *
   * This is the method used by HeartModule, ThinkerModule, subagent spawning,
   * and the CassiCoreExecutionBackend — all callers that already hold a
   * stable session ID rather than a channel+sender pair.
   */
  async processTurn(
    sessionId: string,
    content: string,
    options?: TurnOptions & { channelId?: string; senderId?: string }
  ): Promise<TurnExecutionResult> {
    this.assertInitialized();

    const session = await this.sessionManager!.getOrCreateById(
      sessionId,
      options?.channelId ?? 'system',
      options?.senderId ?? 'system',
      options?.model ? { model: options.model } : undefined
    );

    // Always refresh the system prompt on every turn
    session.systemPrompt = this.systemPrompt;

    if (options?.model && options.model !== 'unknown') {
      session.model = options.model;
    }

    return this._executeTurn(session, content, options);
  }

  /**
   * Cancel an active turn for a session.
   * Returns true if a turn was running and was aborted.
   */
  requestCancel(sessionId: string): boolean {
    const controller = this.activeControllers.get(sessionId);
    if (controller) {
      controller.abort();
      this.activeControllers.delete(sessionId);
      this.logger.info('Turn cancelled', { sessionId });
      return true;
    }
    return false;
  }

  /**
   * Get raw session manager
   */
  getSessionManager(): SessionManager | undefined {
    return this.sessionManager;
  }

  /**
   * Get intelligence layer for direct turn processing (e.g. captured external turns).
   */
  getIntelligenceLayer(): IntelligenceLayer | undefined {
    return this.intelligenceLayer;
  }

  /**
   * Get the TurnHandler for direct access (e.g. injection, context window swap).
   */
  getTurnHandler(): TurnHandler | undefined {
    return this.turnHandler;
  }

  /**
   * Queue content for injection on the next turn.
   * Delegates to TurnHandler → MessageBuilder.
   */
  injectOnNextTurn(content: string): void {
    this.turnHandler?.injectOnNextTurn(content)
  }

  /**
   * Hot-swap the context window at runtime (e.g., to change token limits).
   */
  setContextWindow(contextWindow: import('../turn/ContextWindow.js').ContextWindow): void {
    this.turnHandler?.setContextWindow(contextWindow)
  }

  /**
   * Get stats
   */
  getStats(): {
    initialized: boolean;
    intelligence: ReturnType<IntelligenceLayer['getStats']> | undefined;
  } {
    return {
      initialized: this.initialized,
      intelligence: this.intelligenceLayer?.getStats()
    };
  }

  /**
   * Shutdown pipeline components
   */
  async shutdown(): Promise<void> {
    this.logger.info('Shutting down session pipeline');

    this.intelligenceLayer?.stop();
    await this.store?.close?.();

    this.initialized = false;
  }

  // Private Methods

  /**
   * Core turn execution.  Both processMessage() and processTurn() delegate
   * here after resolving the session object.
   */
  private async _executeTurn(
    session: SessionState,
    content: string,
    options?: TurnOptions
  ): Promise<TurnExecutionResult> {
    const startedAt = Date.now();

    // Always set the current system prompt — existing sessions loaded from
    // SQLite may have a stale or empty prompt from an earlier daemon run.
    session.systemPrompt = this.systemPrompt;

    // Build an AbortController for this turn so that requestCancel() works.
    // If the caller also passed a signal, we chain them.
    const controller = new AbortController();
    if (options?.signal) {
      options.signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
    this.activeControllers.set(session.id, controller);

    // Create the turn request
    const request: TurnRequest = {
      sessionId: session.id,
      channelId: session.channelId,
      senderId: session.senderId,
      content,
      attachments: options?.attachments as any,
      signal: controller.signal
    };

    // Retrieve relevant memories and intelligence context BEFORE the LLM call
    try {
      const freshContext = await this.gatherPreTurnContext(session.id, content);
      if (freshContext) {
        session.context = {
          ...session.context,
          ...freshContext,
          updatedAt: Date.now(),
        };
      }
    } catch (err) {
      this.logger.debug('Pre-turn intelligence gathering failed (non-fatal)', {
        sessionId: session.id,
        error: String(err),
      });
    }

    // Submit user prompt spark to LocusBridge before injection aggregation
    // so the curated context includes the current turn's attentional focus
    try {
      const locusBridge = this.options.intelligence?.locusBridge;
      if (locusBridge && typeof locusBridge.sparkFromUserPrompt === 'function') {
        locusBridge.sparkFromUserPrompt(session.id, content);
      }
    } catch { /* non-blocking */ }

    // Apply InjectionAggregator injections (Corpus, SessionDigest, Optimizer, Dreamer, etc.)
    if (this.options.injectionAggregator) {
      try {
        const turnContext = { session, userMessage: content, timestamp: Date.now() };
        const injections = await this.options.injectionAggregator.aggregate(session.id, turnContext);
        if (injections.length > 0) {
          if (!session.context) {
            session.context = { updatedAt: Date.now() };
          }
          session.context.injections = injections.map(i => i.content);
          this.logger.debug('InjectionAggregator applied', {
            sessionId: session.id,
            sources: injections.map(i => i.source),
            totalChars: injections.reduce((s, i) => s + i.content.length, 0),
          });
        }
      } catch (err) {
        this.logger.debug('InjectionAggregator failed (non-fatal)', {
          sessionId: session.id,
          error: String(err),
        });
      }
    }

    // Emit stream start event if streaming is requested
    const shouldStream = !!(options?.stream || options?.onStreamEvent);
    if (shouldStream && this.eventBus) {
      this.eventBus.emit({
        type: 'worker:message' as any,
        pluginId: `session:${session.id}`,
        payload: {
          type: 'streaming_start',
          sessionId: session.id,
          timestamp: Date.now()
        }
      } as any);
    }

    // Build per-token streaming callback.
    // Priority: custom callback → event bus → none
    const onStreamEvent: StreamEventCallback | undefined =
      options?.onStreamEvent
      ?? ((options?.stream && this.eventBus)
        ? (type, data) => {
            const payload: Record<string, unknown> = {
              type: `turn:${type}`,
              sessionId: session.id,
              timestamp: Date.now()
            };

            switch (type) {
              case 'token':
                payload.token = data.token ?? '';
                break;
              case 'thinking':
                payload.token = data.token ?? '';
                payload.thinking = true;
                break;
              case 'tool_call':
                payload.tool = data.toolCall?.name;
                payload.toolCallId = data.toolCall?.id;
                payload.input = data.toolCall?.input;
                break;
              case 'tool_result':
                payload.tool = data.toolResult?.toolName;
                payload.toolCallId = data.toolResult?.toolCallId;
                payload.content = data.toolResult?.content;
                payload.isError = data.toolResult?.isError;
                payload.durationMs = data.toolResult?.durationMs;
                break;
            }

            this.eventBus!.emit({
              type: 'worker:message' as any,
              pluginId: `session:${session.id}`,
              payload
            } as any);
          }
        : undefined);

    if (this.eventBus) {
      this.eventBus.emit({
        type: 'turn:start' as any,
        sessionId: session.id,
        message: content,
        timestamp: new Date()
      } as any);
    }

    try {
      const result = await this.turnHandler!.process(session, request, onStreamEvent);

      // Emit done event (bookend) if streaming
      if (shouldStream && this.eventBus) {
        this.eventBus.emit({
          type: 'worker:message' as any,
          pluginId: `session:${session.id}`,
          payload: {
            type: 'turn:done',
            sessionId: session.id,
            model: result.model,
            tokensUsed: result.tokensUsed,
            durationMs: result.durationMs,
            timestamp: Date.now()
          }
        } as any);
      }

      // Update session
      await this.sessionManager!.addTurn(
        session.id,
        content,
        result.response,
        {
          tokensUsed: result.tokensUsed,
          toolCalls: result.toolCalls
        }
      );

      if (this.eventBus) {
        this.eventBus.emit({
          type: 'turn:end' as any,
          sessionId: session.id,
          response: result.response,
          durationMs: result.durationMs,
          timestamp: new Date()
        } as any);
      }

      // Trigger background intelligence (post-processing)
      this.intelligenceLayer!.process(session.id, {
        userMessage: content,
        assistantResponse: result.response,
        toolCalls: result.toolCalls,
        sessionHistory: session.messages,
        availableTools: [],
        timestamp: Date.now()
      });

      return {
        response: result.response,
        sessionId: session.id,
        model: session.model,
        tokensUsed: result.tokensUsed,
        durationMs: result.durationMs,
      };
    } catch (err) {
      if (this.eventBus) {
        this.eventBus.emit({
          type: 'turn:end' as any,
          sessionId: session.id,
          response: `Error processing request: ${String(err)}`,
          durationMs: Date.now() - startedAt,
          timestamp: new Date()
        } as any);
      }
      throw err;
    } finally {
      // Always clean up the controller
      this.activeControllers.delete(session.id);
    }
  }

  /**
   * Gather intelligence context BEFORE the LLM call so that the MessageBuilder
   * can include memory search results, thinker insights, and subconscious
   * observations in the prompt.
   */
  private async gatherPreTurnContext(
    sessionId: string,
    userMessage: string,
  ): Promise<Partial<IntelligenceContext> | null> {
    const intel = this.options.intelligence;
    if (!intel) return null;

    const memory = intel.memory as any;
    const thinker = intel.thinker as ThinkerModule | undefined;
    const subconscious = intel.subconscious as SubconsciousModule | undefined;

    const context: Partial<IntelligenceContext> = {};
    let hasContent = false;

    const results = await Promise.allSettled([
      // 1. Memory retrieval
      (async () => {
        if (memory?.retrieve) {
          const memories = await memory.retrieve(userMessage, { limit: 5 });
          if (memories?.length) {
            context.recentMemories = memories.map(
              (m: { content: string }) => m.content,
            );
            hasContent = true;
          }
        }
      })(),

      // 2. Thinker insights
      (async () => {
        if (thinker?.getContextInjection) {
          const injection = thinker.getContextInjection(sessionId);
          if (injection) {
            context.thinkerNotes = [injection];
            hasContent = true;
          }
        } else if (thinker?.getRecentInsights) {
          const insights = thinker.getRecentInsights(3) ?? [];
          if (insights.length) {
            context.thinkerNotes = insights.map(
              (i) => `[${i.level}] ${i.insight}`,
            );
            hasContent = true;
          }
        }
      })(),

      // 3. Subconscious observations
      (async () => {
        if (subconscious?.getContextInjection) {
          const injection = subconscious.getContextInjection(sessionId);
          if (injection) {
            context.subconsciousSignals = [injection];
            hasContent = true;
          }
        }
      })(),
    ]);

    for (const r of results) {
      if (r.status === 'rejected') {
        this.logger.debug('Pre-turn intelligence source failed', {
          sessionId,
          error: String(r.reason),
        });
      }
    }

    return hasContent ? context : null;
  }

  private loadSystemPrompt(): string {
    try {
      const prompt = buildSystemPrompt(this.logger);
      if (prompt?.trim()) return prompt;
    } catch (err) {
      this.logger.warn('Failed to build system prompt via workspace loader', {
        error: String(err),
      });
    }
    return `You are Cassandra — a personal AI assistant running on CassiCore.
Current date/time: ${new Date().toLocaleString('en-US', { timeZone: 'America/Los_Angeles', weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}
Be helpful, accurate, and concise. You have access to tools — use them freely.`;
  }

  private assertInitialized(): void {
    if (!this.initialized) {
      throw new Error('Session pipeline not initialized');
    }
  }
}

/**
 * Create and initialize a SessionPipeline
 */
export async function createSessionPipeline(
  options: SessionPipelineOptions
): Promise<SessionPipeline> {
  const pipeline = new SessionPipeline(options);
  await pipeline.initialize();
  return pipeline;
}
