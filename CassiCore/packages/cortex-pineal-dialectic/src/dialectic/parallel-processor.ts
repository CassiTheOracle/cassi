/**
 * ParallelDialecticProcessor — Runs Yang + Yin simultaneously
 * 
 * Key innovation: Instead of sequential (Yang → Yin → Serenity),
 * we run Yang (expansion) and Yin (baseline + self-critique) in parallel,
 * then have Serenity perform dual synthesis.
 * 
 * Expected speedup: ~1.7x (350ms vs 600ms typical)
 */

import type { ILogger } from '../../../types/interfaces.js';
import type { IEventBus } from '../../../types/interfaces.js';
import type { 
  YangOutput, 
  YinOutput, 
  YinBaselineOutput,
  YinBaselineBranch,
  YinCritique,
  SerenityOutput,
  DialecticResult,
  YangContext,
  DialecticStreamEvent,
  DualSynthesisInput,
  ParallelDialecticResult,
  ParallelConfig
} from '../../../types/dialectic.js';
import type { IProvider } from '../../../types/runtime.js';
import type { IMemory } from '../../../types/intelligence.js';
import type { PromptOptimizer } from './prompt-optimizer.js';
import { YangObserver, type YangConfig } from './yang.js';
import { YinObserver, type YinConfig } from './yin.js';
import { Serenity, type SerenityConfig } from './serenity.js';

export interface ParallelDialecticOptions {
  providers?: {
    yang?: IProvider | { model: string };
    yin?: IProvider | { model: string };
    serenity?: IProvider | { model: string };
  };
  mode?: 'parallel' | 'sequential' | 'adaptive';
  signal?: AbortSignal;
}

export class ParallelDialecticProcessor {
  private logger: ILogger;
  private config: ParallelConfig;
  private eventBus?: IEventBus;
  private memory?: IMemory;
  
  private yang: YangObserver;
  private yin: YinObserver;
  private serenity: Serenity;
  private promptOptimizer?: PromptOptimizer;

  constructor(
    logger: ILogger,
    config: ParallelConfig,
    yangConfig: Partial<YangConfig>,
    yinConfig: Partial<YinConfig>,
    serenityConfig: Partial<SerenityConfig>
  ) {
    this.logger = logger.child?.('parallel-dialectic') ?? logger;
    this.config = {
      maxWaitMs: config?.maxWaitMs ?? 8000,
      partialResultsOnFailure: config?.partialResultsOnFailure ?? true,
      observerTimeoutMs: config?.observerTimeoutMs ?? 6000,
      synchronization: config?.synchronization ?? 'best-effort',
    };
    
    // Initialize observers with specialized configs for parallel mode
    this.yang = new YangObserver(this.logger, {
      ...yangConfig,
      temperature: yangConfig.temperature ?? 0.9,  // High creativity
    });
    
    this.yin = new YinObserver(this.logger, {
      ...yinConfig,
      temperature: yinConfig.temperature ?? 0.3,  // High precision
    });
    
    this.serenity = new Serenity(this.logger, {
      ...serenityConfig,
      temperature: serenityConfig.temperature ?? 0.4,  // Balanced
    });
    
    this.logger.info('ParallelDialecticProcessor: initialized', {
      maxWaitMs: this.config.maxWaitMs,
      observerTimeoutMs: this.config.observerTimeoutMs,
      synchronization: this.config.synchronization,
    });
  }

  setEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    if (this.yang && typeof (this.yang as any).setEventBus === 'function') {
      (this.yang as any).setEventBus(bus);
    }
    if (this.yin && typeof (this.yin as any).setEventBus === 'function') {
      (this.yin as any).setEventBus(bus);
    }
    if (this.serenity && typeof (this.serenity as any).setEventBus === 'function') {
      (this.serenity as any).setEventBus(bus);
    }
    this.logger.info('ParallelDialecticProcessor: event bus wired');
  }

  setMemory(memory: IMemory): void {
    this.memory = memory;
    this.logger.info('ParallelDialecticProcessor: memory wired');
  }

  setPromptOptimizer(optimizer: PromptOptimizer): void {
    this.promptOptimizer = optimizer;
    this.yang.setPromptOptimizer(optimizer);
    this.yin.setPromptOptimizer(optimizer);
    this.serenity.setPromptOptimizer(optimizer);
    this.logger.info('ParallelDialecticProcessor: prompt optimizer wired to all observers');
  }

  setProvider(provider: IProvider): void {
    this.yang.setProvider(provider);
    this.yin.setProvider(provider);
    this.serenity.setProvider(provider);
    this.logger.info('ParallelDialecticProcessor: provider wired to all observers');
  }

  /**
   * Process a turn using parallel Yang + Yin execution
   */
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
    
    this.logger.info('ParallelDialecticProcessor: starting parallel turn', {
      sessionId,
      turnId,
      dialecticSessionId,
    });

    try {
      // Fetch relevant memories
      let relevantMemories: string[] = [];
      if (this.memory) {
        try {
          const results = await this.memory.search(userMessage, { limit: 5 });
          relevantMemories = results.map(r => r.entry.content.slice(0, 8000));
        } catch (error) {
          this.logger.warn('ParallelDialecticProcessor: failed to fetch memories', { error: String(error) });
        }
      }

      // Emit start event
      emitStreamEvent({
        timestamp: Date.now(),
        turnId,
        stage: 'start',
        data: { mode: 'parallel' },
      });

      // ─── PHASE 1: PARALLEL YANG + YIN ────────────────────────────────────
      
      // Yang: Generate expansive branches (standard mode)
      const yangPromise = this.executeYang(dialecticSessionId, userMessage, context, opts);
      
      // Yin: Generate baseline + self-critique (NEW parallel mode)
      const yinPromise = this.executeYinBaseline(dialecticSessionId, userMessage, context, opts);

      // Wait for both with timeout
      const [yangResult, yinResult] = await Promise.all([
        this.withTimeout(yangPromise, this.config.observerTimeoutMs, 'yang', turnId),
        this.withTimeout(yinPromise, this.config.observerTimeoutMs, 'yin', turnId),
      ]);

      // Emit Yang completion
      emitStreamEvent({
        timestamp: Date.now(),
        turnId,
        stage: 'yang',
        data: yangResult,
      });

      // Emit Yin completion
      emitStreamEvent({
        timestamp: Date.now(),
        turnId,
        stage: 'yin',
        data: yinResult,
      });

      // ─── PHASE 2: DUAL SYNTHESIS ─────────────────────────────────────────
      
      // Prepare dual synthesis input
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

      // Run Serenity dual synthesis
      const serenityOpts: any = {};
      if (opts?.providers?.serenity) {
        const hint = opts.providers.serenity;
        if (typeof hint === 'object' && 'complete' in hint) {
          serenityOpts.provider = hint;
        } else if (typeof hint === 'object' && 'model' in hint) {
          serenityOpts.model = hint.model;
        }
      }
      if (opts?.signal) serenityOpts.signal = opts.signal;
      serenityOpts.allowConcurrent = true;

      const serenityResult = await this.serenity.synthesizeDual(
        dialecticSessionId,
        serenityInput,
        relevantMemories,
        serenityOpts
      );

      // Emit Serenity completion
      emitStreamEvent({
        timestamp: Date.now(),
        turnId,
        stage: 'serenity',
        data: serenityResult,
      });

      // ─── BUILD RESULT ────────────────────────────────────────────────────
      
      const totalLatencyMs = Date.now() - startTime;
      const totalCostUsd = this.calculateCost(yangResult, yinResult, serenityResult);
      
      // Determine signal injection — threshold lowered from 0.7 to 0.6 to surface more quality signals
      const signalInjected = serenityResult.synthesis.hasSignal &&
        serenityResult.synthesis.signal?.urgency === 'immediate' &&
        (serenityResult.synthesis.signal?.confidence || 0) >= 0.6;

      const result: ParallelDialecticResult = {
        sessionId,
        turnId,
        timestamp: startTime,
        level: 0,
        executionMode: 'parallel',
        yang: yangResult,
        yin: yinResult,
        serenity: serenityResult,
        signalInjected,
        totalLatencyMs,
        totalCostUsd,
        timing: {
          yangDuration: yangResult.meta.generationTimeMs,
          yinDuration: yinResult.meta.processingTimeMs,
          serenityDuration: serenityResult.meta.processingTimeMs,
          totalParallelTime: totalLatencyMs,
          firstCompletion: yangResult.meta.generationTimeMs <= yinResult.meta.processingTimeMs ? 'yang' : 'yin',
        },
        quality: {
          yangYinAgreement: this.calculateAgreement(yangResult, yinResult),
          dialecticTension: this.calculateTension(yangResult, yinResult),
          synthesisConfidence: serenityResult.meta.dialecticQuality,
        },
      };

      // ─── PROMPT OPTIMIZER FEEDBACK ───────────────────────────────────────
      if (this.promptOptimizer?.enabled) {
        this.promptOptimizer.recordFeedback({
          quality: {
            yangYinAgreement: result.quality.yangYinAgreement,
            dialecticTension: result.quality.dialecticTension,
            synthesisConfidence: result.quality.synthesisConfidence,
            hasSignal: result.signalInjected,
          },
          selectedVariants: {
            yang: this.promptOptimizer.getLastSelected('yang') || 'yang-v1-structured',
            yin: this.promptOptimizer.getLastSelected('yin') || 'yin-v1-structured',
            serenity: this.promptOptimizer.getLastSelected('serenity') || 'serenity-v1-structured',
          },
        });
      }

      // Emit completion
      emitStreamEvent({
        timestamp: Date.now(),
        turnId,
        stage: 'complete',
      });

      this.logger.info('ParallelDialecticProcessor: turn complete', {
        sessionId,
        turnId,
        totalLatencyMs,
        branchesGenerated: yangResult.branches.length,
        baselineBranches: yinResult.baselineBranches.length,
        signalInjected,
        firstCompletion: result.timing.firstCompletion,
        speedupVsSequential: this.estimateSpeedup(result),
      });

      // Archive dialectic outputs to Archivist for comprehensive search
      if (this.memory && typeof (this.memory as any).archiveDialectic === 'function') {
        try {
          const memory = this.memory as any;
          // Archive Yang branches
          for (let i = 0; i < yangResult.branches.length; i++) {
            const branch = yangResult.branches[i];
            await memory.archiveDialectic(
              sessionId,
              'yang',
              branch.content,
              undefined,
              {
                turnId,
                branchIndex: i,
                confidence: branch.confidence,
                source: 'dialectic:parallel',
                tags: ['dialectic', 'yang', `turn:${turnId}`],
              }
            );
          }

          // Archive Yin critiques
          for (let i = 0; i < yinResult.selfCritiques.length; i++) {
            const critique = yinResult.selfCritiques[i];
            await memory.archiveDialectic(
              sessionId,
              'yin',
              critique.critique,
              undefined,
              {
                turnId,
                critiqueIndex: i,
                targetBranch: critique.yangBranchId,
                source: 'dialectic:parallel',
                tags: ['dialectic', 'yin', `turn:${turnId}`],
              }
            );
          }

          // Archive Serenity synthesis
          await memory.archiveDialectic(
            sessionId,
            'serenity',
            serenityResult.synthesis.signal?.content || `Synthesized ${serenityResult.synthesis.branchesConsidered} branches, surfaced ${serenityResult.synthesis.branchesSurfaced}`,
            undefined,
            {
              turnId,
              hasSignal: serenityResult.synthesis.hasSignal,
              signalType: serenityResult.synthesis.signal?.type,
              confidence: serenityResult.synthesis.signal?.confidence,
              source: 'dialectic:parallel',
              tags: ['dialectic', 'serenity', `turn:${turnId}`],
            }
          );
        } catch (err) {
          this.logger.warn('ParallelDialecticProcessor: failed to archive dialectic outputs', { error: String(err) });
        }
      }

      return result;
    } catch (error) {
      this.logger.error('ParallelDialecticProcessor: turn failed', {
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

    // Call Yin's new baseline mode (runs independently of Yang)
    return this.yin.observeWithBaseline(sessionId, userMessage, context, yinOpts);
  }

  private async withTimeout<T>(
    promise: Promise<T>,
    timeoutMs: number,
    stage: 'yang' | 'yin',
    turnId: string
  ): Promise<T> {
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        reject(new Error(`${stage} observer timed out after ${timeoutMs}ms`));
      }, timeoutMs);
    });

    return Promise.race([promise, timeoutPromise]).catch((error) => {
      this.logger.warn('ParallelDialecticProcessor: observer timeout', {
        stage,
        turnId,
        timeoutMs,
        error: String(error),
      });
      throw error;
    });
  }

  private calculateCost(
    yang: YangOutput,
    yin: YinBaselineOutput,
    serenity: SerenityOutput
  ): number {
    // GPT-5 Mini / k2p5 pricing (approximate)
    const inputCostPer1M = 0.15;
    const outputCostPer1M = 0.60;

    const totalInput = yang.meta.inputTokens + yin.meta.inputTokens + serenity.meta.inputTokens;
    const totalOutput = yang.meta.outputTokens + yin.meta.outputTokens + serenity.meta.outputTokens;

    return (totalInput / 1_000_000 * inputCostPer1M) + 
           (totalOutput / 1_000_000 * outputCostPer1M);
  }

  private calculateAgreement(yang: YangOutput, yin: YinBaselineOutput): number {
    // Measure how much Yin's baseline agrees with Yang's branches
    // Higher = more alignment, Lower = more tension (can be good for creativity)
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

  private calculateTension(yang: YangOutput, yin: YinBaselineOutput): number {
    // Dialectic tension = diversity of thought
    // Higher tension = more creative potential
    const agreement = this.calculateAgreement(yang, yin);
    return 1 - agreement;  // Inverse of agreement
  }

  private estimateSpeedup(result: ParallelDialecticResult): number {
    // Estimate speedup vs sequential execution
    // Sequential would be: yang + yin + serenity (sum of all)
    // Parallel is: max(yang, yin) + serenity
    const sequentialEstimate = result.timing.yangDuration + 
                               result.timing.yinDuration + 
                               result.timing.serenityDuration;
    const parallelActual = result.timing.totalParallelTime;
    
    return sequentialEstimate / parallelActual;
  }
}

export const createParallelDialecticProcessor = (
  logger: ILogger,
  config: ParallelConfig,
  yangConfig: Partial<YangConfig>,
  yinConfig: Partial<YinConfig>,
  serenityConfig: Partial<SerenityConfig>
): ParallelDialecticProcessor => {
  return new ParallelDialecticProcessor(logger, config, yangConfig, yinConfig, serenityConfig);
};
