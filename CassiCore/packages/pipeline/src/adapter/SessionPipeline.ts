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
  };
  eventBus?: IEventBus;
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
    
    // 3. Create turn handler
    this.turnHandler = new TurnHandler({
      providers: this.options.providers,
      toolExecutor: this.options.toolExecutor as any,
      logger: this.logger.child('turn-handler'),
      maxToolRounds: this.options.config.get('pipeline.maxToolRounds', 8),
      contextWindowTokens: this.options.config.get('pipeline.contextWindowTokens', 200000),
      toolTimeoutMs: this.options.config.get('pipeline.toolTimeoutMs', 60000),
      toolSchemas: this.options.toolSchemas
    });
    
    // 4. Create intelligence layer
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
   * Process a message
   */
  async processMessage(
    channelId: string,
    senderId: string,
    content: string,
    options?: {
      attachments?: Array<{ mediaType: string; data: string }>;
      signal?: AbortSignal;
      stream?: boolean;                    // Enable SSE streaming events
      onStreamEvent?: StreamEventCallback; // Direct streaming callback (bypasses event bus routing)
      model?: string;                      // Override model for this turn
    }
  ): Promise<{ response: string; sessionId: string; model?: string; tokensUsed?: number; durationMs?: number }> {
    if (!this.initialized) {
      throw new Error('Session pipeline not initialized');
    }

    // 1. Get or create session
    const session = await this.sessionManager!.getOrCreate(channelId, senderId);
    const startedAt = Date.now();

    // Always set the current system prompt — existing sessions loaded from
    // SQLite may have a stale or empty prompt from an earlier daemon run.
    session.systemPrompt = this.systemPrompt;

    // Override session model if provided
    if (options?.model && options.model !== 'unknown') {
      session.model = options.model;
    }

    // 2. Create request
    const request: TurnRequest = {
      sessionId: session.id,
      channelId,
      senderId,
      content,
      attachments: options?.attachments as any,
      signal: options?.signal
    };

    // ── Pre-turn intelligence gathering ───────────────────────────────────────
    // Retrieve relevant memories and intelligence context BEFORE the LLM call
    // so that the MessageBuilder includes them in the prompt.
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
      // 3. Process turn with real-time streaming
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

      // 4. Update session
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

      // 5. Trigger background intelligence (post-processing: archiving, dialectic, etc.)
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
    }
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
  
  // ============================================================================
  // Private Methods
  // ============================================================================

  /**
   * Gather intelligence context BEFORE the LLM call so that the MessageBuilder
   * can include memory search results, thinker insights, and subconscious
   * observations in the prompt.
   *
   * This is the key piece that makes channels "first-class" — without it,
   * the LLM only sees raw conversation history and the system prompt.
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

    // Run retrieval operations concurrently with a timeout
    const results = await Promise.allSettled([
      // 1. Memory retrieval — search for relevant past context using the user's message
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

      // 2. Thinker insights — background reasoning that has accumulated
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

      // 3. Subconscious observations — patterns and background signals
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

    // Log any failures (non-fatal)
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
    // Use the workspace loader which reads IDENTITY.md, SOUL.md, USER.md,
    // MEMORY.md from ~/.cassi/ and builds the full Cassandra persona prompt.
    // This is the same system prompt used by the legacy turn pipeline.
    try {
      const prompt = buildSystemPrompt(this.logger);
      if (prompt?.trim()) return prompt;
    } catch (err) {
      this.logger.warn('Failed to build system prompt via workspace loader', {
        error: String(err),
      });
    }
    // Fallback — should never reach here if ~/.cassi/ files exist
    return `You are Cassandra — a personal AI assistant running on CassiCore.
Current date/time: ${new Date().toLocaleString('en-US', { timeZone: 'America/Los_Angeles', weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}
Be helpful, accurate, and concise. You have access to tools — use them freely.`;
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
