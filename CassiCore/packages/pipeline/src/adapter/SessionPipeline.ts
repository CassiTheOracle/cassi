/**
 * Session Pipeline
 * 
 * Integration point for session pipeline into the Daemon
 * with feature flag support
 */

import { homedir } from 'node:os';
import { join } from 'node:path';
import { readFileSync } from 'node:fs';


import {
  SessionManager,
  SQLiteSessionStore,
  TurnHandler,
  IntelligenceLayer,
  type SessionState,
  type TurnRequest,
  type TurnResult,
  type TurnMetadata,
  type StreamEventCallback
} from '../index.js';

import type { IMemory } from '../../../types/intelligence.js';
import type { IConfig, ILogger, IEventBus } from '../../../types/interfaces.js';
import type { IProvider } from '../../../types/runtime.js';

// Intelligence module interfaces (from existing code)
interface DialecticSystem {
  processTurn: (...args: unknown[]) => Promise<unknown>;
}

interface ThinkerModule {
  reflect: (...args: unknown[]) => Promise<string[]>;
}

interface SubconsciousModule {
  ingest: (...args: unknown[]) => Promise<unknown>;
}

export interface SessionPipelineOptions {
  config: IConfig;
  logger: ILogger;
  providers: Map<string, IProvider>;
  toolExecutor: {
    execute: (name: string, input: unknown, context: unknown) => Promise<{ content: string; isError: boolean }>;
    isAvailable: (name: string) => boolean;
  };
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
    
    // 2. Create session manager
    this.sessionManager = new SessionManager({
      store: this.store,
      defaultModel: this.options.config.get(
        'intelligence.defaultModel',
        'lmstudio/lfm2.5-1.2b'
      ),
      defaultSystemPrompt: this.loadSystemPrompt(),
      logger: this.logger.child('session-manager')
    });
    
    // 3. Create turn handler
    this.turnHandler = new TurnHandler({
      providers: this.options.providers,
      toolExecutor: this.options.toolExecutor as any,
      logger: this.logger.child('turn-handler'),
      maxToolRounds: this.options.config.get('pipeline.maxToolRounds', 8),
      contextWindowTokens: this.options.config.get('pipeline.contextWindowTokens', 200000),
      toolTimeoutMs: this.options.config.get('pipeline.toolTimeoutMs', 60000)
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
      stream?: boolean; // Enable SSE streaming events
    }
  ): Promise<{ response: string; sessionId: string }> {
    if (!this.initialized) {
      throw new Error('Session pipeline not initialized');
    }

    // 1. Get or create session
    const session = await this.sessionManager!.getOrCreate(channelId, senderId);

    // 2. Create request
    const request: TurnRequest = {
      sessionId: session.id,
      channelId,
      senderId,
      content,
      attachments: options?.attachments as any,
      signal: options?.signal
    };

    // Emit stream start event if streaming is requested
    if (options?.stream && this.eventBus) {
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

    // Build per-token streaming callback that emits to the event bus in real-time
    const onStreamEvent: StreamEventCallback | undefined =
      (options?.stream && this.eventBus)
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
        : undefined;

    // 3. Process turn with real-time streaming
    const result = await this.turnHandler!.process(session, request, onStreamEvent);

    // Emit done event (bookend) if streaming
    if (options?.stream && this.eventBus) {
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

    // 5. Trigger background intelligence
    this.intelligenceLayer!.process(session.id, {
      userMessage: content,
      assistantResponse: result.response,
      toolCalls: result.toolCalls,
      sessionHistory: session.messages,
      availableTools: [],  // Would need to get from tool executor
      timestamp: Date.now()
    });

    return {
      response: result.response,
      sessionId: session.id
    };
  }
  
  /**
   * Get raw session manager
   */
  getSessionManager(): SessionManager | undefined {
    return this.sessionManager;
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
  
  private loadSystemPrompt(): string {
    // Try to load from existing location
    try {
      const promptPath = join(
        process.cwd(),
        'core',
        'workspace',
        'system-prompt.md'
      );
      
      return readFileSync(promptPath, 'utf-8');
    } catch {
      // Return default
      return `You are CassiCore, an AI assistant. Be helpful, accurate, and concise.`;
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
