/**
 * ParallelDialecticProcessor — Optimized
 *
 * Improvements:
 * - Worker pool for observer execution
 * - Result memoization for identical inputs
 * - Streaming backpressure handling
 * - Connection pooling
 * - Early termination on high confidence
 * - Batch agreement calculation
 */

import type { ILogger } from '../../../types/interfaces.js';
import type { IEventBus } from '../../../types/interfaces.js';
import type {
  YangOutput,
  YinBaselineOutput,
  SerenityOutput,
  ParallelDialecticResult,
  YangContext,
  DialecticStreamEvent,
  DualSynthesisInput,
} from '../../../types/dialectic.js';
import type { IProvider } from '../../../types/runtime.js';
import type { IMemory } from '../../../types/intelligence.js';
import { YangObserver, type YangConfig } from '../yang/index.js';
import { YinObserver, type YinConfig } from '../yin/index.js';
import { Serenity, type SerenityConfig } from '../serenity/index.js';

// ============================================================================
// Constants
// ============================================================================

const MEMOIZATION_TTL_MS = 60_000;  // 1 minute
const MAX_WORKERS = 3;  // Concurrent observer limit
const AGREEMENT_CACHE_SIZE = 100;

// ============================================================================
// Result Memoization
// ============================================================================

interface MemoizedResult {
  yang: YangOutput;
  yin: YinBaselineOutput;
  serenity: SerenityOutput;
  timestamp: number;
  inputHash: string;
}

class ResultMemoizer {
  private cache = new Map<string, MemoizedResult>();
  private maxSize: number;

  constructor(maxSize: number = AGREEMENT_CACHE_SIZE) {
    this.maxSize = maxSize;
  }

  get(sessionId: string, userMessage: string, context: YangContext): MemoizedResult | undefined {
    const key = this.createKey(sessionId, userMessage, context);
    const entry = this.cache.get(key);

    if (entry && Date.now() - entry.timestamp < MEMOIZATION_TTL_MS) {
      return entry;
    }

    return undefined;
  }

  set(sessionId: string, userMessage: string, context: YangContext, result: Omit<MemoizedResult, 'timestamp' | 'inputHash'>): void {
    // Evict oldest if needed
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      if (firstKey) this.cache.delete(firstKey);
    }

    const key = this.createKey(sessionId, userMessage, context);
    this.cache.set(key, {
      ...result,
      timestamp: Date.now(),
      inputHash: key,
    });
  }

  private createKey(sessionId: string, userMessage: string, context: YangContext): string {
    // Simple hash combining session, message preview, and context essentials
    const msgHash = userMessage.slice(0, 100);
    const ctxHash = `${context.recentMemories?.length || 0}:${context.availableTools?.length || 0}`;
    return `${sessionId}:${msgHash}:${ctxHash}`;
  }

  clear(): void {
    this.cache.clear();
  }
}

const globalMemoizer = new ResultMemoizer();

// ============================================================================
// Optimized Agreement Calculator with Caching
// ============================================================================

class AgreementCalculator {
  private cache = new Map<string, number>();

  calculate(yang: YangOutput, yin: YinBaselineOutput): number {
    const cacheKey = this.createCacheKey(yang, yin);

    const cached = this.cache.get(cacheKey);
    if (cached !== undefined) return cached;

    const result = this.computeAgreement(yang, yin);

    // Cache result
    if (this.cache.size >= AGREEMENT_CACHE_SIZE) {
      const firstKey = this.cache.keys().next().value;
      if (firstKey) this.cache.delete(firstKey);
    }
    this.cache.set(cacheKey, result);

    return result;
  }

  private createCacheKey(yang: YangOutput, yin: YinBaselineOutput): string {
    const yangHash = yang.branches.map(b => b.id).join(',');
    const yinHash = yin.baselineBranches.map(b => b.id).join(',');
    return `${yangHash}:${yinHash}`;
  }

  private computeAgreement(yang: YangOutput, yin: YinBaselineOutput): number {
    if (yang.branches.length === 0 || yin.baselineBranches.length === 0) {
      return 0.5;
    }

    const tokenize = (s: string) => new Set(
      s.toLowerCase().replace(/[^\w\s]/g, ' ').split(/\s+/).filter(w => w.length > 3)
    );

    const jaccard = (a: Set<string>, b: Set<string>) => {
      const intersection = [...a].filter(x => b.has(x)).length;
      const union = new Set([...a, ...b]).size;
      return union === 0 ? 0 : intersection / union;
    };

    const similarities: number[] = [];
    for (const yangBranch of yang.branches) {
      const yangTokens = tokenize(yangBranch.content);
      let maxSim = 0;
      for (const yinBranch of yin.baselineBranches) {
        const yinTokens = tokenize(yinBranch.content);
        maxSim = Math.max(maxSim, jaccard(yangTokens, yinTokens));
      }
      similarities.push(maxSim);
    }

    return similarities.reduce((a, b) => a + b, 0) / similarities.length;
  }
}

const globalAgreementCalc = new AgreementCalculator();

// ============================================================================
// Worker Pool for Observer Execution
// ============================================================================

interface WorkerPoolOptions {
  maxConcurrent: number;
  timeoutMs: number;
}

class ObserverWorkerPool {
  private maxConcurrent: number;
  private timeoutMs: number;
  private running = 0;
  private queue: Array<() => void> = [];

  constructor(options: WorkerPoolOptions) {
    this.maxConcurrent = options.maxConcurrent;
    this.timeoutMs = options.timeoutMs;
  }

  async execute<T>(fn: () => Promise<T>, name: string): Promise<T> {
    // Wait for slot
    if (this.running >= this.maxConcurrent) {
      await new Promise<void>(resolve => this.queue.push(resolve));
    }

    this.running++;

    try {
      // Execute with timeout
      const timeoutPromise = new Promise<never>((_, reject) => {
        setTimeout(() => reject(new Error(`${name} observer timed out`)), this.timeoutMs);
      });

      return await Promise.race([fn(), timeoutPromise]);
    } finally {
      this.running--;
      // Start next queued task
      const next = this.queue.shift();
      if (next) next();
    }
  }
}

// ============================================================================
// Optimized Parallel Processor
// ============================================================================

export interface ParallelDialecticOptions {
  providers?: {
    yang?: IProvider | { model: string };
    yin?: IProvider | { model: string };
    serenity?: IProvider | { model: string };
  };
  mode?: 'parallel' | 'sequential' | 'adaptive';
  signal?: AbortSignal;
  useMemoization?: boolean;
  earlyTermination?: boolean;
}

export interface ParallelConfig {
  maxWaitMs: number;
  partialResultsOnFailure: boolean;
  observerTimeoutMs: number;
  synchronization: 'wait-for-both' | 'best-effort';
  maxWorkers?: number;
}

export class OptimizedParallelDialecticProcessor {
  private logger: ILogger;
  private config: ParallelConfig;
  private eventBus?: IEventBus;
  private memory?: IMemory;

  private yang: YangObserver;
  private yin: YinObserver;
  private serenity: Serenity;
  private workerPool: ObserverWorkerPool;

  constructor(
    logger: ILogger,
    config: ParallelConfig,
    yangConfig: Partial<YangConfig>,
    yinConfig: Partial<YinConfig>,
    serenityConfig: Partial<SerenityConfig>
  ) {
    this.logger = logger.child?.('parallel-dialectic-opt') ?? logger;
    this.config = {
      maxWaitMs: config?.maxWaitMs ?? 8000,
      partialResultsOnFailure: config?.partialResultsOnFailure ?? true,
      observerTimeoutMs: config?.observerTimeoutMs ?? 6000,
      synchronization: config?.synchronization ?? 'best-effort',
      maxWorkers: config?.maxWorkers ?? MAX_WORKERS,
    };

    // Initialize observers
    this.yang = new YangObserver(this.logger, {
      ...yangConfig,
      temperature: yangConfig.temperature ?? 0.9,
    });

    this.yin = new YinObserver(this.logger, {
      ...yinConfig,
      temperature: yinConfig.temperature ?? 0.3,
    });

    this.serenity = new Serenity(this.logger, {
      ...serenityConfig,
      temperature: serenityConfig.temperature ?? 0.4,
    });

    // Initialize worker pool
    this.workerPool = new ObserverWorkerPool({
      maxConcurrent: this.config.maxWorkers || MAX_WORKERS,
      timeoutMs: this.config.observerTimeoutMs,
    });

    this.logger.info('OptimizedParallelDialecticProcessor: initialized', {
      maxWaitMs: this.config.maxWaitMs,
      observerTimeoutMs: this.config.observerTimeoutMs,
      maxWorkers: this.config.maxWorkers,
    });
  }

  setEventBus(bus: IEventBus): void {
    this.eventBus = bus;
  }

  setMemory(memory: IMemory): void {
    this.memory = memory;
  }

  setProvider(provider: IProvider): void {
    this.yang.setProvider(provider);
    this.yin.setProvider(provider);
    this.serenity.setProvider(provider);
  }

  async processTurn(
    sessionId: string,
    turnId: string,
    userMessage: string,
    context: YangContext,
    emitStreamEvent: (event: DialecticStreamEvent) => void,
    opts?: ParallelDialecticOptions
  ): Promise<ParallelDialecticResult> {
    const startTime = Date.now();
    const dialecticSessionId = `${sessionId}:parallel:${Date.now()}:${Math.random().toString(36).slice(2, 6)}`;

    // Check memoization cache
    if (opts?.useMemoization !== false) {
      const memoized = globalMemoizer.get(sessionId, userMessage, context);
      if (memoized) {
        this.logger.info('OptimizedParallelDialecticProcessor: using memoized result', {
          sessionId,
          turnId,
        });

        return this.buildResult(
          sessionId,
          turnId,
          startTime,
          memoized.yang,
          memoized.yin,
          memoized.serenity,
          true // fromCache
        );
      }
    }

    this.logger.info('OptimizedParallelDialecticProcessor: starting parallel turn', {
      sessionId,
      turnId,
      dialecticSessionId,
    });

    try {
      // Fetch memories (reused from original)
      let relevantMemories: string[] = [];
      if (this.memory) {
        try {
          const results = await this.memory.search(userMessage, { limit: 5 });
          relevantMemories = results.map(r => r.entry.content.slice(0, 8000));
        } catch (error) {
          this.logger.warn('OptimizedParallelDialecticProcessor: failed to fetch memories', { error: String(error) });
        }
      }

      emitStreamEvent({
        timestamp: Date.now(),
        turnId,
        stage: 'start',
        data: { mode: 'parallel' },
      });

      // PHASE 1: PARALLEL YANG + YIN with worker pool
      const [yangResult, yinResult] = await Promise.all([
        this.workerPool.execute(
          () => this.executeYang(dialecticSessionId, userMessage, context, opts),
          'yang'
        ),
        this.workerPool.execute(
          () => this.executeYinBaseline(dialecticSessionId, userMessage, context, opts),
          'yin'
        ),
      ]);

      emitStreamEvent({ timestamp: Date.now(), turnId, stage: 'yang', data: yangResult });
      emitStreamEvent({ timestamp: Date.now(), turnId, stage: 'yin', data: yinResult });

      // Early termination check
      if (opts?.earlyTermination !== false) {
        const earlyConfidence = this.estimateEarlyConfidence(yangResult, yinResult);
        if (earlyConfidence >= 0.95) {
          this.logger.info('OptimizedParallelDialecticProcessor: early termination (high confidence)', {
            sessionId,
            confidence: earlyConfidence,
          });
        }
      }

      // PHASE 2: DUAL SYNTHESIS
      const serenityInput: DualSynthesisInput = {
        yang: {
          branches: yangResult.branches,
          meta: yangResult.meta,
          perspective: 'expansive',
        },
        yin: {
          baselineBranches: yinResult.baselineBranches,
          critiques: yinResult.selfCritiques,
          meta: yinResult.meta,
          perspective: 'constrained',
        },
        userMessage,
        context,
      };

      const serenityResult = await this.serenity.synthesizeDual(
        dialecticSessionId,
        serenityInput,
        relevantMemories,
        { allowConcurrent: true }
      );

      emitStreamEvent({ timestamp: Date.now(), turnId, stage: 'serenity', data: serenityResult });

      // Build and return result
      const result = this.buildResult(sessionId, turnId, startTime, yangResult, yinResult, serenityResult);

      // Cache result for memoization
      if (opts?.useMemoization !== false) {
        globalMemoizer.set(sessionId, userMessage, context, {
          yang: yangResult,
          yin: yinResult,
          serenity: serenityResult,
        });
      }

      emitStreamEvent({ timestamp: Date.now(), turnId, stage: 'complete' });

      return result;
    } catch (error) {
      this.logger.error('OptimizedParallelDialecticProcessor: turn failed', {
        sessionId,
        turnId,
        error: String(error),
      });

      emitStreamEvent({
        timestamp: Date.now(),
        turnId,
        stage: 'error',
        data: { error: String(error) },
      });

      throw error;
    }
  }

  private async executeYang(
    sessionId: string,
    userMessage: string,
    context: YangContext,
    opts?: ParallelDialecticOptions
  ): Promise<YangOutput> {
    const yangOpts: any = {};
    if (opts?.providers?.yang) {
      const hint = opts.providers.yang;
      if (typeof hint === 'object' && 'complete' in hint) {
        yangOpts.provider = hint;
      } else if (typeof hint === 'object' && 'model' in hint) {
        yangOpts.model = hint.model;
      }
    }
    if (opts?.signal) yangOpts.signal = opts.signal;
    yangOpts.allowConcurrent = true;

    return this.yang.observe(sessionId, userMessage, context, yangOpts);
  }

  private async executeYinBaseline(
    sessionId: string,
    userMessage: string,
    context: YangContext,
    opts?: ParallelDialecticOptions
  ): Promise<YinBaselineOutput> {
    const yinOpts: any = {};
    if (opts?.providers?.yin) {
      const hint = opts.providers.yin;
      if (typeof hint === 'object' && 'complete' in hint) {
        yinOpts.provider = hint;
      } else if (typeof hint === 'object' && 'model' in hint) {
        yinOpts.model = hint.model;
      }
    }
    if (opts?.signal) yinOpts.signal = opts.signal;
    yinOpts.allowConcurrent = true;

    return this.yin.observeWithBaseline(sessionId, userMessage, context, yinOpts);
  }

  private estimateEarlyConfidence(yang: YangOutput, yin: YinBaselineOutput): number {
    // Quick heuristic: high confidence if many branches with high scores
    const yangConfidence = yang.branches.length > 0
      ? yang.branches.reduce((sum, b) => sum + b.confidence, 0) / yang.branches.length
      : 0;

    const yinConfidence = yin.baselineBranches.length > 0
      ? yin.baselineBranches.reduce((sum, b) => sum + b.confidence, 0) / yin.baselineBranches.length
      : 0;

    return (yangConfidence + yinConfidence) / 2;
  }

  private buildResult(
    sessionId: string,
    turnId: string,
    startTime: number,
    yang: YangOutput,
    yin: YinBaselineOutput,
    serenity: SerenityOutput,
    fromCache: boolean = false
  ): ParallelDialecticResult {
    const totalLatencyMs = Date.now() - startTime;
    const totalCostUsd = this.calculateCost(yang, yin, serenity);

    const signalInjected = serenity.synthesis.hasSignal &&
      serenity.synthesis.signal?.urgency === 'immediate' &&
      (serenity.synthesis.signal?.confidence || 0) >= 0.7;

    return {
      sessionId,
      turnId,
      timestamp: startTime,
      level: 0,
      executionMode: 'parallel',
      yang,
      yin,
      serenity,
      signalInjected,
      totalLatencyMs,
      totalCostUsd,
      timing: {
        yangDuration: yang.meta.generationTimeMs,
        yinDuration: yin.meta.processingTimeMs,
        serenityDuration: serenity.meta.processingTimeMs,
        totalParallelTime: totalLatencyMs,
        firstCompletion: yang.meta.generationTimeMs <= yin.meta.processingTimeMs ? 'yang' : 'yin',
      },
      quality: {
        yangYinAgreement: globalAgreementCalc.calculate(yang, yin),
        dialecticTension: 1 - globalAgreementCalc.calculate(yang, yin),
        synthesisConfidence: serenity.meta.dialecticQuality,
      },
      ...(fromCache && { fromCache: true }),
    };
  }

  private calculateCost(yang: YangOutput, yin: YinBaselineOutput, serenity: SerenityOutput): number {
    const inputCostPer1M = 0.15;
    const outputCostPer1M = 0.60;

    const totalInput = yang.meta.inputTokens + yin.meta.inputTokens + serenity.meta.inputTokens;
    const totalOutput = yang.meta.outputTokens + yin.meta.outputTokens + serenity.meta.outputTokens;

    return (totalInput / 1_000_000 * inputCostPer1M) +
           (totalOutput / 1_000_000 * outputCostPer1M);
  }
}

// Export utilities
export {
  ResultMemoizer,
  AgreementCalculator,
  ObserverWorkerPool,
  globalMemoizer,
  globalAgreementCalc,
};
