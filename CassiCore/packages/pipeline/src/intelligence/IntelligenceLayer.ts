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

import type { IMemory } from '@cassicore/foundation';
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

export interface ThinkerModule {
  getRecentInsights?(limit: number): Array<{ insight: string; level: string; timestamp: number }>;
  getContextInjection?(sessionId: string): string | undefined;
}

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
  eventBus?: { emit(event: Record<string, unknown>): void };
  enabledProcessors?: string[];
  concurrency?: number;
}

// Processor Factory — replaces per-module classes with concise function calls

/**
 * Create an IntelligenceProcessor with built-in error handling and event emission.
 * Eliminates the boilerplate of per-module processor classes.
 */
function createProcessor(
  name: string,
  processFn: (sessionId: string, turnData: TurnData) => Promise<ProcessorResult | null>,
  logger: ILogger,
  eventBus?: { emit(event: Record<string, unknown>): void },
): IntelligenceProcessor {
  return {
    name,
    async process(sessionId: string, turnData: TurnData): Promise<ProcessorResult | null> {
      try {
        return await processFn(sessionId, turnData)
      } catch (error) {
        logger.warn(`${name} processor failed`, { error: String(error) })
        // Emit error event for SelfHealingAgent
        try {
          const errStr = String(error)
          const stack = (error instanceof Error && error.stack) ? error.stack : undefined
          eventBus?.emit({
            type: 'intelligence:processor-error',
            processorName: name,
            error: stack ? `${errStr}\n${stack}` : errStr,
            timestamp: Date.now(),
          })
        } catch { /* best-effort */ }
        return null
      }
    },
  }
}

// IntelligenceLayer

export class IntelligenceLayer {
  private sessionManager: SessionManager;
  private logger: ILogger;
  private processor: BackgroundProcessor;
  private enabled: Set<string>;
  
  constructor(options: IntelligenceLayerOptions) {
    this.sessionManager = options.sessionManager;
    this.logger = options.logger;
    
    this.enabled = new Set(options.enabledProcessors ?? [
      'memory', 'dialectic', 'thinker', 'subconscious'
    ]);
    
    // Build processors using factory — no per-module classes needed
    const processors: IntelligenceProcessor[] = [];
    const { memory, dialectic, thinker, subconscious, eventBus } = options;
    
    if (this.enabled.has('memory')) {
      processors.push(createProcessor('Memory', async (sessionId, turnData) => {
        const mem = memory as any;
        if (mem.archiveConversation) {
          await mem.archiveConversation(
            sessionId,
            turnData.userMessage,
            turnData.assistantResponse,
            turnData.thinkingBlocks?.join('')
          );
        }
        const memories = await mem.retrieve?.(turnData.userMessage, { limit: 5 });
        return {
          type: 'memories',
          data: memories?.map((m: { content: string }) => m.content) ?? [],
        };
      }, this.logger, eventBus));
    }
    
    if (this.enabled.has('dialectic')) {
      processors.push(createProcessor('Dialectic', async (sessionId, turnData) => {
        const result = await dialectic.processTurn(
          sessionId,
          `turn-${Date.now()}`,
          turnData.userMessage,
          {
            recentMemories: [],
            availableTools: turnData.availableTools,
            sessionHistory: turnData.sessionHistory,
          }
        );
        return {
          type: 'dialecticInsights',
          data: result.signals?.map(s => s.content) ?? [],
        };
      }, this.logger, eventBus));
    }
    
    if (this.enabled.has('thinker')) {
      processors.push(createProcessor('Thinker', async (sessionId, _turnData) => {
        const recentInsights = thinker.getRecentInsights?.(3) ?? [];
        const contextInjection = thinker.getContextInjection?.(sessionId);
        return {
          type: 'thinkerNotes',
          data: [
            ...recentInsights.map(i => `[${i.level}] ${i.insight}`),
            ...(contextInjection ? [contextInjection] : []),
          ],
        };
      }, this.logger, eventBus));
    }
    
    if (this.enabled.has('subconscious')) {
      processors.push(createProcessor('Subconscious', async (sessionId, _turnData) => {
        const contextInjection = subconscious.getContextInjection?.(sessionId);
        return {
          type: 'subconsciousSignals',
          data: contextInjection ? [contextInjection] : [],
        };
      }, this.logger, eventBus));
    }
    
    this.processor = new BackgroundProcessor(
      processors,
      {
        concurrency: options.concurrency ?? 3,
        intervalMs: 100,
        maxQueueSize: 1000,
        autoStart: true,
      },
      this.logger.child('processor'),
    );
    
    this.processor.setOnComplete(this.updateContext.bind(this));
    
    this.logger.info('IntelligenceLayer initialized', {
      processors: processors.map(p => p.name),
      enabled: Array.from(this.enabled),
    });
  }
  
  async process(sessionId: string, turnData: TurnData): Promise<void> {
    this.processor.enqueue(sessionId, turnData).catch(err => {
      this.logger.error('Failed to enqueue intelligence job', {
        sessionId,
        error: String(err),
      });
    });
  }
  
  getStats(): ReturnType<BackgroundProcessor['getStats']> {
    return this.processor.getStats();
  }
  
  enableProcessor(name: string): void {
    this.enabled.add(name);
    this.logger.info(`Processor enabled: ${name}`);
  }
  
  disableProcessor(name: string): void {
    this.enabled.delete(name);
    this.logger.info(`Processor disabled: ${name}`);
  }
  
  stop(): void {
    this.processor.stop();
    this.logger.info('IntelligenceLayer stopped');
  }
  
  private async updateContext(
    sessionId: string,
    results: ProcessorResult[],
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
    
    try {
      await this.sessionManager.updateContext(sessionId, context);
      this.logger.debug('Session context updated', {
        sessionId,
        contextKeys: Object.keys(context),
      });
    } catch (error) {
      this.logger.error('Failed to update session context', {
        sessionId,
        error: String(error),
      });
    }
  }
}

export function createIntelligenceLayer(
  options: Omit<IntelligenceLayerOptions, 'logger'> & { logger?: ILogger },
): IntelligenceLayer {
  const logger = options.logger ?? createNoopLogger();
  return new IntelligenceLayer({ ...options, logger });
}

/**
 * @dep callers: createNoopLogger (core/pipeline/intelligence/IntelligenceLayer.ts), createIntelligenceLayer (core/pipeline/intelligence/IntelligenceLayer.ts)
 * @dep calls: createNoopLogger
 * @dep module: Intelligence
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function createNoopLogger(): ILogger {
  return {
    debug: () => {},
    info: () => {},
    warn: () => {},
    error: () => {},
    child: () => createNoopLogger(),
  };
}
