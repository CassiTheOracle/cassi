/**
 * Intelligence Layer
 * 
 * Coordinates background intelligence processing
 */

import {
  BackgroundProcessor,
  type IntelligenceProcessor,
  type OnCompleteCallback
} from './BackgroundProcessor.js';

import type { IMemory } from '../../../types/intelligence.js';
import type {
  SessionManager
} from '../session/SessionManager.js';
import type {
  TurnData,
  ProcessorResult,
  IntelligenceContext,
  ILogger
} from '../session/types.js';


// Intelligence module interfaces (simplified)
export interface DialecticSystem {
  processTurn(
    sessionId: string,
    turnId: string,
    userMessage: string,
    context: {
      recentMemories: unknown[];
      availableTools: string[];
      sessionHistory: unknown[];
    }
  ): Promise<{ signals?: Array<{ type: string; content: string }> }>;
}

/**
 * ThinkerModule — actual runtime API.
 * The Thinker operates autonomously via EventBus; per-turn data is read via
 * getRecentInsights() for context injection rather than a push-based reflect().
 */
export interface ThinkerModule {
  getRecentInsights?(limit: number): Array<{ insight: string; level: string; timestamp: number }>;
  getContextInjection?(sessionId: string): string | undefined;
}

/**
 * SubconsciousModule — actual runtime API.
 * The Subconscious taps the EventBus via onAll(); per-turn context is read
 * via getContextInjection() rather than a push-based ingest().
 */
export interface SubconsciousModule {
  getContextInjection?(sessionId: string): string | undefined;
  getSessionIds?(): string[];
}

export interface IntelligenceLayerOptions {
  sessionManager: SessionManager;
  memory: IMemory;
  dialectic: DialecticSystem;
  thinker: ThinkerModule;
  subconscious: SubconsciousModule;
  logger: ILogger;

  /** Optional EventBus for emitting processor-error events to the SelfHealingAgent */
  eventBus?: { emit(event: Record<string, unknown>): void };
  
  // Optional configuration
  enabledProcessors?: string[];
  concurrency?: number;
}

/**
 * Coordinates all intelligence background processing
 */
export class IntelligenceLayer {
  private sessionManager: SessionManager;
  private memory: IMemory;
  private dialectic: DialecticSystem;
  private thinker: ThinkerModule;
  private subconscious: SubconsciousModule;
  private logger: ILogger;
  private eventBus?: IntelligenceLayerOptions['eventBus'];
  
  private processor: BackgroundProcessor;
  private enabled: Set<string>;
  
  constructor(options: IntelligenceLayerOptions) {
    this.sessionManager = options.sessionManager;
    this.memory = options.memory;
    this.dialectic = options.dialectic;
    this.thinker = options.thinker;
    this.subconscious = options.subconscious;
    this.logger = options.logger;
    this.eventBus = options.eventBus;
    
    // Which processors to enable
    this.enabled = new Set(options.enabledProcessors ?? [
      'memory',
      'dialectic',
      'thinker',
      'subconscious'
    ]);
    
    // Create individual processors
    const processors: IntelligenceProcessor[] = [];
    
    if (this.enabled.has('memory')) {
      processors.push(new MemoryProcessor(this.memory, this.logger, this.eventBus));
    }
    
    if (this.enabled.has('dialectic')) {
      processors.push(new DialecticProcessor(this.dialectic, this.logger, this.eventBus));
    }
    
    if (this.enabled.has('thinker')) {
      processors.push(new ThinkerProcessor(this.thinker, this.logger, this.eventBus));
    }
    
    if (this.enabled.has('subconscious')) {
      processors.push(new SubconsciousProcessor(this.subconscious, this.logger, this.eventBus));
    }
    
    // Create background processor
    this.processor = new BackgroundProcessor(
      processors,
      {
        concurrency: options.concurrency ?? 3,
        intervalMs: 100,
        maxQueueSize: 1000,
        autoStart: true
      },
      this.logger.child('processor')
    );
    
    // Set completion handler
    this.processor.setOnComplete(this.updateContext.bind(this));
    
    this.logger.info('IntelligenceLayer initialized', {
      processors: processors.map(p => p.name),
      enabled: Array.from(this.enabled)
    });
  }
  
  /**
   * Process turn data (fire-and-forget)
   */
  async process(sessionId: string, turnData: TurnData): Promise<void> {
    // Just enqueue - don't wait
    this.processor.enqueue(sessionId, turnData).catch(err => {
      this.logger.error('Failed to enqueue intelligence job', {
        sessionId,
        error: String(err)
      });
    });
  }
  
  /**
   * Get processor stats
   */
  getStats(): ReturnType<BackgroundProcessor['getStats']> {
    return this.processor.getStats();
  }
  
  /**
   * Enable/disable processors dynamically
   */
  enableProcessor(name: string): void {
    this.enabled.add(name);
    this.logger.info(`Processor enabled: ${name}`);
  }
  
  disableProcessor(name: string): void {
    this.enabled.delete(name);
    this.logger.info(`Processor disabled: ${name}`);
  }
  
  /**
   * Stop the intelligence layer
   */
  stop(): void {
    this.processor.stop();
    this.logger.info('IntelligenceLayer stopped');
  }
  
  // ============================================================================
  // Private Methods
  // ============================================================================
  
  private async updateContext(
    sessionId: string,
    results: ProcessorResult[]
  ): Promise<void> {
    const context: Partial<IntelligenceContext> = {};
    
    for (const result of results) {
      switch (result.type) {
        case 'memories':
          context.recentMemories = result.data as string[];
          break;
          
        case 'dialecticInsights':
          context.dialecticInsights = result.data as string[];
          break;
          
        case 'thinkerNotes':
          context.thinkerNotes = result.data as string[];
          break;
          
        case 'subconsciousSignals':
          context.subconsciousSignals = result.data as string[];
          break;
      }
    }
    
    // Update session context
    try {
      await this.sessionManager.updateContext(sessionId, context);
      
      this.logger.debug('Session context updated', {
        sessionId,
        contextKeys: Object.keys(context)
      });
    } catch (error) {
      this.logger.error('Failed to update session context', {
        sessionId,
        error: String(error)
      });
    }
  }
}

// ============================================================================
// Individual Processors
// ============================================================================

/** Shared helper: emit an intelligence:processor-error event for the SelfHealingAgent. */
function emitProcessorError(
  eventBus: IntelligenceLayerOptions['eventBus'] | undefined,
  processorName: string,
  error: unknown
): void {
  try {
    const errStr = String(error)
    // Include stack trace so the SelfHealingAgent can extract file:line references
    const stack = (error instanceof Error && error.stack) ? error.stack : undefined
    eventBus?.emit({
      type: 'intelligence:processor-error',
      processorName,
      error: stack ? `${errStr}\n${stack}` : errStr,
      timestamp: Date.now(),
    });
  } catch { /* best-effort */ }
}

class MemoryProcessor implements IntelligenceProcessor {
  name = 'Memory';

  constructor(
    private memory: IMemory,
    private logger: ILogger,
    private eventBus?: IntelligenceLayerOptions['eventBus']
  ) {}

  async process(sessionId: string, turnData: TurnData): Promise<ProcessorResult | null> {
    try {
      // Archive the conversation (using any for flexibility)
      const memory = this.memory as any;
      if (memory.archiveConversation) {
        await memory.archiveConversation(
          sessionId,
          turnData.userMessage,
          turnData.assistantResponse,
          turnData.thinkingBlocks?.join('')
        );
      }

      // Retrieve relevant memories
      const memories = await memory.retrieve?.(
        turnData.userMessage,
        { limit: 5 }
      );

      return {
        type: 'memories',
        data: memories?.map((m: { content: string }) => m.content) ?? []
      };
    } catch (error) {
      this.logger.warn('Memory processor failed', { error: String(error) });
      emitProcessorError(this.eventBus, this.name, error);
      return null;
    }
  }
}

class DialecticProcessor implements IntelligenceProcessor {
  name = 'Dialectic';

  constructor(
    private dialectic: DialecticSystem,
    private logger: ILogger,
    private eventBus?: IntelligenceLayerOptions['eventBus']
  ) {}

  async process(sessionId: string, turnData: TurnData): Promise<ProcessorResult | null> {
    try {
      const result = await this.dialectic.processTurn(
        sessionId,
        `turn-${Date.now()}`,
        turnData.userMessage,
        {
          recentMemories: [],
          availableTools: turnData.availableTools,
          sessionHistory: turnData.sessionHistory
        }
      );

      const insights = result.signals?.map(s => s.content) ?? [];

      return {
        type: 'dialecticInsights',
        data: insights
      };
    } catch (error) {
      this.logger.warn('Dialectic processor failed', { error: String(error) });
      emitProcessorError(this.eventBus, this.name, error);
      return null;
    }
  }
}

class ThinkerProcessor implements IntelligenceProcessor {
  name = 'Thinker';

  constructor(
    private thinker: ThinkerModule,
    private logger: ILogger,
    private eventBus?: IntelligenceLayerOptions['eventBus']
  ) {}

  async process(sessionId: string, _turnData: TurnData): Promise<ProcessorResult | null> {
    try {
      // The Thinker operates autonomously via EventBus; it does not expose a
      // per-turn push API. Read recent insights for context injection instead.
      const recentInsights = this.thinker.getRecentInsights?.(3) ?? [];
      const contextInjection = this.thinker.getContextInjection?.(sessionId);

      const notes: string[] = [
        ...recentInsights.map(i => `[${i.level}] ${i.insight}`),
        ...(contextInjection ? [contextInjection] : []),
      ];

      return {
        type: 'thinkerNotes',
        data: notes
      };
    } catch (error) {
      this.logger.warn('Thinker processor failed', { error: String(error) });
      emitProcessorError(this.eventBus, this.name, error);
      return null;
    }
  }
}

class SubconsciousProcessor implements IntelligenceProcessor {
  name = 'Subconscious';

  constructor(
    private subconscious: SubconsciousModule,
    private logger: ILogger,
    private eventBus?: IntelligenceLayerOptions['eventBus']
  ) {}

  async process(sessionId: string, _turnData: TurnData): Promise<ProcessorResult | null> {
    try {
      // The Subconscious taps the EventBus via onAll(); it does not expose a
      // per-turn push API. Read the context injection it has built instead.
      const contextInjection = this.subconscious.getContextInjection?.(sessionId);

      const signals: string[] = contextInjection ? [contextInjection] : [];

      return {
        type: 'subconsciousSignals',
        data: signals
      };
    } catch (error) {
      this.logger.warn('Subconscious processor failed', { error: String(error) });
      emitProcessorError(this.eventBus, this.name, error);
      return null;
    }
  }
}

/**
 * Create intelligence layer with safe defaults
 */
export function createIntelligenceLayer(
  options: Omit<IntelligenceLayerOptions, 'logger'> & { logger?: ILogger }
): IntelligenceLayer {
  const logger = options.logger ?? createNoopLogger();
  
  return new IntelligenceLayer({
    ...options,
    logger
  });
}

// Helper
function createNoopLogger(): ILogger {
  return {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => createNoopLogger()
  };
}
