/**
 * DialecticSystem — Unified orchestration of Yang, Yin, and Serenity
 * 
 * Runs all three observers in parallel and coordinates their outputs.
 * Handles WebSocket streaming, persistence, and signal injection.
 */

import type { ILogger } from '../../../types/interfaces.js';
import type { IEventBus } from '../../../types/interfaces.js';
import type {
  IDialecticSystem,
  DialecticResult,
  ParallelDialecticResult,
  YangContext,
  DialecticStreamEvent,
  DialecticSignal,
  DialecticMode
} from '../../../types/dialectic.js';
import type { IProvider, Message } from '../../../types/runtime.js';
import type { IMemory } from '../../../types/intelligence.js';
import { YangObserver, type YangConfig } from '../yang/index.js';
import { YinObserver, type YinConfig } from '../yin/index.js';
import { Serenity, type SerenityConfig } from '../serenity/index.js';
import { ParallelDialecticProcessor, type ParallelDialecticOptions } from './parallel-processor.js';
import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

export interface DialecticSystemConfig {
  enabled: boolean;
  mode?: DialecticMode;  // 'sequential' | 'parallel' | 'adaptive'
  yang?: Partial<YangConfig>;
  yin?: Partial<YinConfig>;
  serenity?: Partial<SerenityConfig>;
  parallel?: {
    maxWaitMs?: number;
    observerTimeoutMs?: number;
    partialResultsOnFailure?: boolean;
    synchronization?: 'wait-for-both' | 'best-effort';
  };
  adaptive?: {
    complexityThreshold?: number;
    qualityThreshold?: number;
    historyWindowSize?: number;
  };
  dataDir?: string;
  taskGuide?: {
    enabled?: boolean;
    mode?: 'llm' | 'heuristic' | 'disabled';
    model?: string;
    maxTokens?: number;
    temperature?: number;
    timeoutMs?: number;
  };
}

export class DialecticSystem implements IDialecticSystem {
  readonly name = 'dialectic';
  
  private logger: ILogger;
  private config: DialecticSystemConfig;
  private eventBus?: IEventBus;
  private memory?: IMemory;
  private provider?: IProvider;
  private taskGuideGenerator?: (userMessage: string, context: YangContext, relevantMemories: string[]) => Promise<string> | string;
  // Track recent taskGuide LLM failures per session to avoid thundering LLM calls
  private taskGuideFailures: Map<string, { count: number; lastFailAt: number }> = new Map();
  
  private yang: YangObserver;
  private yin: YinObserver;
  private serenity: Serenity;
  private parallelProcessor?: ParallelDialecticProcessor;
  
  private db?: Database.Database;
  private streamCallbacks: Map<string, Set<(event: DialecticStreamEvent) => void>> = new Map();

  constructor(logger: ILogger, config?: Partial<DialecticSystemConfig>) {
    this.logger = logger.child?.('dialectic') ?? logger;
    this.config = {
      enabled: config?.enabled ?? true,
      yang: config?.yang ?? {},
      yin: config?.yin ?? {},
      serenity: config?.serenity ?? {},
      dataDir: config?.dataDir ?? path.join(process.env.HOME || require('os').homedir(), '.cassicore', 'data'),
      taskGuide: config?.taskGuide ?? { enabled: true, mode: 'heuristic', model: 'gpt-5-mini', maxTokens: 256, temperature: 0.2, timeoutMs: 5000 },
    };
    
    // Initialize observers
    this.yang = new YangObserver(this.logger, this.config.yang);
    this.yin = new YinObserver(this.logger, this.config.yin);
    this.serenity = new Serenity(this.logger, this.config.serenity);
    
    // Initialize parallel processor if needed
    if (this.config.mode === 'parallel' || this.config.mode === 'adaptive') {
      this.parallelProcessor = new ParallelDialecticProcessor(
        this.logger,
        {
          maxWaitMs: this.config.parallel?.maxWaitMs ?? 8000,
          observerTimeoutMs: this.config.parallel?.observerTimeoutMs ?? 6000,
          partialResultsOnFailure: this.config.parallel?.partialResultsOnFailure ?? true,
          synchronization: this.config.parallel?.synchronization ?? 'best-effort',
        },
        this.config.yang ?? {},
        this.config.yin ?? {},
        this.config.serenity ?? {}
      );
      this.logger.info('DialecticSystem: parallel processor initialized', { mode: this.config.mode });
    }
    
    if (this.config.enabled) {
      this.initPersistence();
      this.logger.info('DialecticSystem: enabled', { mode: this.config.mode || 'sequential' });
    } else {
      this.logger.info('DialecticSystem: disabled');
    }
  }

  private initPersistence(): void {
    try {
      if (!fs.existsSync(this.config.dataDir!)) {
        fs.mkdirSync(this.config.dataDir!, { recursive: true });
      }
      
      const dbPath = path.join(this.config.dataDir!, 'dialectic.db');
      this.db = new Database(dbPath);
      
      this.db.exec(`
        PRAGMA journal_mode=WAL;
        
        CREATE TABLE IF NOT EXISTS dialectic_turns (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id TEXT NOT NULL,
          turn_id TEXT NOT NULL,
          timestamp INTEGER NOT NULL,
          yang_output TEXT NOT NULL,
          yin_output TEXT NOT NULL,
          serenity_output TEXT NOT NULL,
          signal_injected BOOLEAN NOT NULL,
          total_latency_ms INTEGER NOT NULL,
          total_cost_usd REAL NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_dialectic_session ON dialectic_turns(session_id);
        CREATE INDEX IF NOT EXISTS idx_dialectic_timestamp ON dialectic_turns(timestamp);
      `);
      
      this.logger.info('DialecticSystem: persistence initialized', { dbPath });

      // Backwards-compatibility: detect older schemas that used `synthesizer_output` and copy
      try {
        const cols = (this.db.prepare("PRAGMA table_info(dialectic_turns)").all() as any[]).map((c: any) => c.name);
        const hasSynth = cols.includes('synthesizer_output') || cols.includes('synthesizer');
        const hasSerenity = cols.includes('serenity_output');
        if (hasSynth && !hasSerenity) {
          try {
            this.db.prepare(`ALTER TABLE dialectic_turns ADD COLUMN serenity_output TEXT`).run();
            // Copy existing synthesizer_output into serenity_output when present
            try {
              this.db.prepare(`UPDATE dialectic_turns SET serenity_output = synthesizer_output WHERE serenity_output IS NULL`).run();
            } catch (err) {
              // Some older DBs may have different column naming; attempt generic copy
              try { this.db.prepare(`UPDATE dialectic_turns SET serenity_output = synthesizer WHERE serenity_output IS NULL`).run() } catch {}
            }
            this.logger.info('DialecticSystem: migrated synthesizer_output -> serenity_output for backward compatibility');
          } catch (err) {
            this.logger.warn('DialecticSystem: failed to add serenity_output column during migration', { error: String(err) });
          }
        }
      } catch (err) {
        this.logger.debug('DialecticSystem: migration check failed', { error: String(err) });
      }

    } catch (error) {
      this.logger.error('DialecticSystem: failed to initialize persistence', { error: String(error) });
    }
  }

  setProvider(provider: IProvider): void {
    this.provider = provider;
    this.yang.setProvider(provider);
    this.yin.setProvider(provider);
    this.serenity.setProvider(provider);
    if (this.parallelProcessor) {
      this.parallelProcessor.setProvider(provider);
    }
    this.logger.info('DialecticSystem: provider wired to all observers');
  }

  setMemory(memory: IMemory): void {
    this.memory = memory;
    if (this.parallelProcessor) {
      this.parallelProcessor.setMemory(memory);
    }
    this.logger.info('DialecticSystem: memory wired');
  }

  /**
   * Allow injecting a custom task guide generator (pluggable).
   * The generator may return a string or a Promise<string>.
   */
  setTaskGuideGenerator(generator: (userMessage: string, context: YangContext, relevantMemories: string[]) => Promise<string> | string): void {
    this.taskGuideGenerator = generator;
    this.logger.info('DialecticSystem: custom taskGuide generator configured');
  }

  // Subconscious integration: store pre-detected patterns and context
  private subconsciousContext = new Map<string, {
    patterns: Array<{ type: string; confidence: number; evidence: string[] }>;
    intent?: { type: string; confidence: number };
    anomalies: Array<{ category: string; severity: string }>;
    lastUpdated: number;
  }>();

  onEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    try {
      if (this.yang && typeof (this.yang as any).setEventBus === 'function') (this.yang as any).setEventBus(bus);
      if (this.yin && typeof (this.yin as any).setEventBus === 'function') (this.yin as any).setEventBus(bus);
      if (this.serenity && typeof (this.serenity as any).setEventBus === 'function') (this.serenity as any).setEventBus(bus);
      if (this.parallelProcessor) this.parallelProcessor.setEventBus(bus);
    } catch (err) {
      // best-effort — do not fail wiring if observers don't support event bus
    }

    // Wire Subconscious signals for enhanced context
    this.setupSubconsciousListeners(bus);

    this.logger.info('DialecticSystem: event bus wired');
  }

  /**
   * Listen to Subconscious signals for pattern/intent context
   */
  private setupSubconsciousListeners(bus: IEventBus): void {
    // Listen for pattern signals from Subconscious
    (bus as any).on?.('subconscious:pattern', (e: any) => {
      try {
        const { sessionId, pattern } = e;
        if (!sessionId || !pattern) return;

        let ctx = this.subconsciousContext.get(sessionId);
        if (!ctx) {
          ctx = { patterns: [], anomalies: [], lastUpdated: Date.now() };
          this.subconsciousContext.set(sessionId, ctx);
        }

        // Add or update pattern
        const existing = ctx.patterns.find(p => p.type === pattern.pattern);
        if (existing) {
          existing.confidence = Math.max(existing.confidence, pattern.confidence);
          existing.evidence.push(...pattern.evidence);
        } else {
          ctx.patterns.push({
            type: pattern.pattern,
            confidence: pattern.confidence,
            evidence: pattern.evidence || [],
          });
        }

        ctx.lastUpdated = Date.now();
        this.logger.debug('DialecticSystem: received subconscious pattern', {
          sessionId: sessionId.slice(-8),
          pattern: pattern.pattern,
          confidence: pattern.confidence,
        });
      } catch (err) {
        this.logger.debug('DialecticSystem: failed to process subconscious:pattern', { error: String(err) });
      }
    });

    // Listen for intent signals
    (bus as any).on?.('subconscious:intent', (e: any) => {
      try {
        const { sessionId, intent } = e;
        if (!sessionId || !intent?.to) return;

        let ctx = this.subconsciousContext.get(sessionId);
        if (!ctx) {
          ctx = { patterns: [], anomalies: [], lastUpdated: Date.now() };
          this.subconsciousContext.set(sessionId, ctx);
        }

        ctx.intent = {
          type: intent.to.type,
          confidence: intent.to.confidence,
        };
        ctx.lastUpdated = Date.now();

        this.logger.debug('DialecticSystem: received subconscious intent', {
          sessionId: sessionId.slice(-8),
          intent: intent.to.type,
          confidence: intent.to.confidence,
        });
      } catch (err) {
        this.logger.debug('DialecticSystem: failed to process subconscious:intent', { error: String(err) });
      }
    });

    // Listen for anomaly signals
    (bus as any).on?.('subconscious:anomaly', (e: any) => {
      try {
        const { sessionId, anomaly } = e;
        if (!sessionId || !anomaly) return;

        let ctx = this.subconsciousContext.get(sessionId);
        if (!ctx) {
          ctx = { patterns: [], anomalies: [], lastUpdated: Date.now() };
          this.subconsciousContext.set(sessionId, ctx);
        }

        ctx.anomalies.push({
          category: anomaly.category,
          severity: anomaly.severity,
        });
        ctx.lastUpdated = Date.now();

        this.logger.debug('DialecticSystem: received subconscious anomaly', {
          sessionId: sessionId.slice(-8),
          category: anomaly.category,
          severity: anomaly.severity,
        });
      } catch (err) {
        this.logger.debug('DialecticSystem: failed to process subconscious:anomaly', { error: String(err) });
      }
    });

    // Clean up on session end
    (bus as any).on?.('subconscious:session:ended', (e: any) => {
      try {
        const { sessionId } = e;
        if (sessionId) {
          this.subconsciousContext.delete(sessionId);
          this.logger.debug('DialecticSystem: cleaned up subconscious context', { sessionId: sessionId.slice(-8) });
        }
      } catch (err) {
        this.logger.debug('DialecticSystem: failed to cleanup subconscious context', { error: String(err) });
      }
    });

    this.logger.info('DialecticSystem: Subconscious listeners wired');
  }

  /**
   * Get Subconscious-derived context for a session
   */
  getSubconsciousContext(sessionId: string): {
    patterns: Array<{ type: string; confidence: number; evidence: string[] }>;
    intent?: { type: string; confidence: number };
    anomalies: Array<{ category: string; severity: string }>;
  } | undefined {
    const ctx = this.subconsciousContext.get(sessionId);
    if (!ctx) return undefined;

    // Only return if recent (within 5 minutes)
    if (Date.now() - ctx.lastUpdated > 5 * 60 * 1000) {
      return undefined;
    }

    return {
      patterns: ctx.patterns,
      intent: ctx.intent,
      anomalies: ctx.anomalies,
    };
  }

  subscribeToStream(sessionId: string, callback: (event: DialecticStreamEvent) => void): () => void {
    if (!this.streamCallbacks.has(sessionId)) {
      this.streamCallbacks.set(sessionId, new Set());
    }
    this.streamCallbacks.get(sessionId)!.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.streamCallbacks.get(sessionId)?.delete(callback);
    };
  }

  private emitStreamEvent(sessionId: string, event: DialecticStreamEvent): void {
    const callbacks = this.streamCallbacks.get(sessionId);
    if (callbacks) {
      callbacks.forEach(cb => {
        try {
          cb(event);
        } catch (error) {
          this.logger.warn('DialecticSystem: stream callback error', { error: String(error) });
        }
      });
    }
    
    // Also emit on event bus for other components
    if (this.eventBus) {
      (this.eventBus as any).emit?.({
        type: 'dialectic:stream',
        sessionId,
        ...event,
      });
    }
  }

  async processTurn(
    sessionId: string,
    turnId: string,
    userMessage: string,
    context: YangContext,
    opts?: { 
      providers?: { yang?: any; yin?: any; serenity?: any }; 
      signal?: AbortSignal;
      mode?: 'sequential' | 'parallel' | 'adaptive';
    }
  ): Promise<DialecticResult | ParallelDialecticResult> {
    // Determine execution mode
    const mode = opts?.mode || this.config.mode || 'sequential';
    
    // Route to parallel processor if mode is parallel or adaptive
    if ((mode === 'parallel' || mode === 'adaptive') && this.parallelProcessor) {
      // For adaptive mode, check if we should use parallel
      if (mode === 'adaptive' && !this.shouldUseParallel(userMessage, context)) {
        this.logger.info('DialecticSystem: adaptive mode selected sequential', { sessionId, turnId });
      } else {
        this.logger.info('DialecticSystem: using parallel processor', { mode, sessionId, turnId });
        return this.parallelProcessor.processTurn(
          sessionId,
          turnId,
          userMessage,
          context,
          (event) => this.emitStreamEvent(sessionId, event),
          { providers: opts?.providers, mode, signal: opts?.signal }
        );
      }
    }
    
    const startTime = Date.now();
    // Use a per-invocation dialectic session id so concurrent background
    // dialectic runs for the same user session don't collide with Centralized
    // provider deduplication. This avoids rejecting parallel analysis tasks.
    const dialecticSessionId = `${sessionId}:dialectic:${Date.now()}:${Math.random().toString(36).slice(2,6)}`;
    
    if (!this.config.enabled) {
      return {
        sessionId,
        turnId,
        timestamp: startTime,
        yang: { branches: [], meta: { expansionTemperature: 0.9, generationTimeMs: 0, inputTokens: 0, outputTokens: 0 } },
        yin: { critiques: [], meta: { compressionRatio: 1.0, processingTimeMs: 0, inputTokens: 0, outputTokens: 0 } },
        serenity: {
          synthesis: { hasSignal: false, branchesConsidered: 0, branchesSurfaced: 0 },
          meta: { dialecticQuality: 0.5, processingTimeMs: 0, inputTokens: 0, outputTokens: 0 },
        },
        signalInjected: false,
        totalLatencyMs: 0,
        totalCostUsd: 0,
      };
    }

    try {
      // Fetch relevant memories if memory is available
      let relevantMemories: string[] = [];
      if (this.memory) {
        try {
          const results = await this.memory.search(userMessage, { limit: 5 });
          relevantMemories = results.map(r => r.entry.content.slice(0, 8000));
        } catch (error) {
          this.logger.warn('DialecticSystem: failed to fetch memories', { error: String(error) });
        }
      }

      // Build a short task guide and attach to the context so both observers
      // see the same brief instruction at the top of their context.
      // Allow per-turn provider/model hints (prefer serenity hint, then yang, then yin) to be used by the taskGuide summarizer.
      const preferredProviderHint = opts?.providers?.serenity ?? opts?.providers?.yang ?? opts?.providers?.yin;
      const taskGuide = await this.buildTaskGuide(dialecticSessionId, userMessage, context, relevantMemories, preferredProviderHint, { signal: opts?.signal });
      
      // Incorporate Subconscious context (patterns, intent, anomalies)
      const subCtx = this.getSubconsciousContext(sessionId);
      const ctxWithSubconscious = subCtx ? {
        ...context,
        subconsciousPatterns: subCtx.patterns,
        subconsciousIntent: subCtx.intent,
        subconsciousAnomalies: subCtx.anomalies,
      } : context;
      
      const ctxWithGuide = { ...ctxWithSubconscious, taskGuide };

      // Log subconscious context if present
      if (subCtx && (subCtx.patterns.length > 0 || subCtx.anomalies.length > 0)) {
        this.logger.info('DialecticSystem: using subconscious context', {
          sessionId,
          patterns: subCtx.patterns.map(p => p.type),
          intent: subCtx.intent?.type,
          anomalies: subCtx.anomalies.map(a => a.category),
        });
      }

      // Emit start event with the generated task guide for observability
      this.emitStreamEvent(sessionId, {
        timestamp: Date.now(),
        turnId,
        stage: 'start',
        data: { taskGuide }
      });

      // ORDER: Yang first (expansion), then Yin (refinement)
      // This allows maximum creativity before applying constraints
      
      // Run Yang first - generate expansive branches
      const yangHints = opts?.providers?.yang;
      const yangOpts: any = {};
      if (yangHints) {
        if (typeof yangHints === 'object' && typeof (yangHints as any).complete === 'function') yangOpts.provider = yangHints as any;
        else if (typeof yangHints === 'object' && yangHints.model) yangOpts.model = yangHints.model;
        if (typeof yangHints === 'object' && typeof (yangHints as any).allowConcurrent === 'boolean') yangOpts.allowConcurrent = (yangHints as any).allowConcurrent;
        if (typeof yangHints === 'object' && typeof (yangHints as any).dedupe === 'boolean') yangOpts.dedupe = (yangHints as any).dedupe;
      }
      // Default: allow concurrent dialectic observer calls to avoid false dedup while
      // the pipeline triggers background dialectic runs for the same session.
      if (typeof yangOpts.allowConcurrent === 'undefined') yangOpts.allowConcurrent = true;

      if (opts?.signal) yangOpts.signal = opts.signal;
      const yangOutput = await this.yang.observe(dialecticSessionId, userMessage, ctxWithGuide, yangOpts);
      
      this.emitStreamEvent(sessionId, {
        timestamp: Date.now(),
        turnId,
        stage: 'yang',
        data: yangOutput,
      });

      // Run Yin (refinement) on Yang's output
      const yinHints = opts?.providers?.yin;
      const yinOpts: any = {};
      if (yinHints) {
        if (typeof yinHints === 'object' && typeof (yinHints as any).complete === 'function') yinOpts.provider = yinHints as any;
        else if (typeof yinHints === 'object' && yinHints.model) yinOpts.model = yinHints.model;
        if (typeof yinHints === 'object' && typeof (yinHints as any).allowConcurrent === 'boolean') yinOpts.allowConcurrent = (yinHints as any).allowConcurrent;
        if (typeof yinHints === 'object' && typeof (yinHints as any).dedupe === 'boolean') yinOpts.dedupe = (yinHints as any).dedupe;
      }
      if (typeof yinOpts.allowConcurrent === 'undefined') yinOpts.allowConcurrent = true;

      if (opts?.signal) yinOpts.signal = opts.signal;
      const yinOutput = await this.yin.observe(dialecticSessionId, userMessage, yangOutput, ctxWithGuide, yinOpts);
      
      this.emitStreamEvent(sessionId, {
        timestamp: Date.now(),
        turnId,
        stage: 'yin',
        data: yinOutput,
      });

      // Run Serenity on the dialectic (Yang → Yin)
      const serenityHints = opts?.providers?.serenity;
      const serenityOpts: any = {};
      if (serenityHints) {
        if (typeof serenityHints === 'object' && typeof (serenityHints as any).complete === 'function') serenityOpts.provider = serenityHints as any;
        else if (typeof serenityHints === 'object' && serenityHints.model) serenityOpts.model = serenityHints.model;
        if (typeof serenityHints === 'object' && typeof (serenityHints as any).allowConcurrent === 'boolean') serenityOpts.allowConcurrent = (serenityHints as any).allowConcurrent;
        if (typeof serenityHints === 'object' && typeof (serenityHints as any).dedupe === 'boolean') serenityOpts.dedupe = (serenityHints as any).dedupe;
      }
      if (typeof serenityOpts.allowConcurrent === 'undefined') serenityOpts.allowConcurrent = true;

      if (opts?.signal) serenityOpts.signal = opts.signal;
      const serenityOutput = await this.serenity.synchronize(
        dialecticSessionId,
        userMessage,
        yangOutput,
        yinOutput,
        relevantMemories,
        serenityOpts
      );
      
      this.emitStreamEvent(sessionId, {
        timestamp: Date.now(),
        turnId,
        stage: 'serenity',
        data: serenityOutput,
      });

      // Calculate totals
      const totalLatencyMs = Date.now() - startTime;
      const totalCostUsd = this.calculateCost(yangOutput, yinOutput, serenityOutput);
      
      // Determine if signal should be injected
      const signalInjected = serenityOutput.synthesis.hasSignal && 
        serenityOutput.synthesis.signal?.urgency === 'immediate' &&
        (serenityOutput.synthesis.signal?.confidence || 0) >= 0.7;

      const result: DialecticResult = {
        sessionId,
        turnId,
        timestamp: startTime,
        yang: yangOutput,
        yin: yinOutput,
        serenity: serenityOutput,
        signalInjected,
        totalLatencyMs,
        totalCostUsd,
      };

      // Persist result
      await this.persistResult(result);

      // Emit completion event
      this.emitStreamEvent(sessionId, {
        timestamp: Date.now(),
        turnId,
        stage: 'complete',
      });

      // If signal should be injected, emit signal event
      if (signalInjected && serenityOutput.synthesis.signal) {
        this.emitSignal(sessionId, turnId, serenityOutput.synthesis.signal);
      }

      this.logger.info('DialecticSystem: turn processed (Yang → Yin → Serenity)', {
        sessionId,
        turnId,
        critiquesCount: yinOutput.critiques.length,
        branchesGenerated: yangOutput.branches.length,
        signalGenerated: serenityOutput.synthesis.hasSignal,
        signalInjected,
        totalLatencyMs,
        totalCostUsd: totalCostUsd.toFixed(6),
      });

      return result;
    } catch (error) {
      this.logger.error('DialecticSystem: turn processing failed', {
        sessionId,
        turnId,
        error: String(error),
      });
      
      this.emitStreamEvent(sessionId, {
        timestamp: Date.now(),
        turnId,
        stage: 'error',
        data: { error: String(error) },
      });
      
      throw error;
    }
  }

  /**
   * shouldUseParallel — Adaptive mode decision
   * 
   * Returns true if parallel mode should be used based on message complexity
   * and quality history.
   */
  private shouldUseParallel(userMessage: string, context: YangContext): boolean {
    const config = this.config.adaptive;
    
    // Simple complexity estimation
    const complexity = this.estimateComplexity(userMessage);
    
    // For now, use parallel for most messages except very complex ones
    // where sequential quality is more important than speed
    if (config?.complexityThreshold && complexity > config.complexityThreshold) {
      this.logger.debug('DialecticSystem: high complexity, using sequential', { complexity });
      return false;
    }
    
    // Default to parallel for speed
    return true;
  }

  private estimateComplexity(userMessage: string): number {
    // Simple heuristic: longer messages with more concepts are more complex
    const length = userMessage.length;
    const words = userMessage.split(/\s+/).length;
    const sentences = userMessage.split(/[.!?]+/).length;
    
    // Keywords that indicate complexity
    const complexKeywords = [
      'architecture', 'design', 'implement', 'refactor', 'optimize',
      'debug', 'analyze', 'compare', 'evaluate', 'synthesize',
      'complex', 'complicated', 'sophisticated', 'intricate'
    ];
    const keywordMatches = complexKeywords.filter(kw => 
      userMessage.toLowerCase().includes(kw)
    ).length;
    
    // Score 0-10
    let score = 0;
    if (length > 500) score += 2;
    if (length > 1000) score += 2;
    if (words > 100) score += 2;
    if (sentences > 10) score += 1;
    score += keywordMatches;
    
    return Math.min(10, score);
  }

  private calculateCost(
    yang: DialecticResult['yang'],
    yin: DialecticResult['yin'],
    serenity: DialecticResult['serenity']
  ): number {
    // GPT-5 Mini pricing (approximate)
    const inputCostPer1M = 0.15;  // $0.15 per 1M input tokens
    const outputCostPer1M = 0.60; // $0.60 per 1M output tokens
    
    const totalInput = yang.meta.inputTokens + yin.meta.inputTokens + serenity.meta.inputTokens;
    const totalOutput = yang.meta.outputTokens + yin.meta.outputTokens + serenity.meta.outputTokens;
    
    return (totalInput / 1_000_000 * inputCostPer1M) + (totalOutput / 1_000_000 * outputCostPer1M);
  }


  /**
   * Build a short task guide string to place at the top of Yang/Yin context.
   * By default this uses an LLM-based summarizer if enabled; falls back to
   * a lightweight heuristic when LLM is disabled or fails.
   */
  private async buildTaskGuide(
    sessionIdOrUserMessage: string,
    maybeUserMessageOrContext?: any,
    maybeContextOrMemories?: any,
    maybeRelevantMemories?: any,
    maybeProviderHint?: any,
    maybeOpts?: { signal?: AbortSignal }
  ): Promise<string> {
    // Support both new and legacy signatures:
    // New:   buildTaskGuide(sessionId, userMessage, context, relevantMemories, providerHint)
    // Legacy: buildTaskGuide(userMessage, context, relevantMemories)

    let sessionId: string
    let userMessage: string
    let context: YangContext | undefined
    let relevantMemories: string[] = []
    let providerHint: any = maybeProviderHint

    // Detect new signature: second arg is a string (userMessage)
    if (typeof maybeUserMessageOrContext === 'string') {
      sessionId = sessionIdOrUserMessage
      userMessage = maybeUserMessageOrContext
      context = maybeContextOrMemories as YangContext
      relevantMemories = maybeRelevantMemories ?? []
      providerHint = maybeProviderHint
    } else {
      // Legacy call: first arg is userMessage, second is context object
      userMessage = sessionIdOrUserMessage || ''
      context = maybeUserMessageOrContext as YangContext
      relevantMemories = maybeContextOrMemories ?? []
      // Synthesize a per-call session marker to avoid dedup collisions (use local hash to be robust)
      const localHash = (s: string) => {
        let h = 0
        for (let i = 0; i < s.length; i++) {
          const c = s.charCodeAt(i)
          h = ((h << 5) - h) + c
          h |= 0
        }
        return Math.abs(h).toString(36)
      }
      sessionId = `legacy:${localHash(String(userMessage)).slice(0, 12)}`
      providerHint = maybeRelevantMemories ?? undefined
    }

    const tgCfg = this.config.taskGuide ?? { enabled: true, mode: 'llm' };
    if (!tgCfg.enabled || tgCfg.mode === 'disabled') return '';

    // If a custom generator has been set, use it (pluggable)
    if (this.taskGuideGenerator) {
      try {
        const r = await this.taskGuideGenerator(userMessage, context as YangContext, relevantMemories);
        return r || '';
      } catch (err) {
        this.logger.warn('DialecticSystem: custom taskGuide generator failed', { error: String(err) });
        // fall through to heuristic
      }
    }

    // If we've seen repeated failures for this session recently, avoid thundering LLM calls.
    const failEntry = this.taskGuideFailures.get(sessionId) ?? { count: 0, lastFailAt: 0 };
    const FAIL_THRESHOLD = 3;
    const FAIL_COOLDOWN_MS = 60_000; // 1 minute
    if (failEntry.count >= FAIL_THRESHOLD && (Date.now() - failEntry.lastFailAt) < FAIL_COOLDOWN_MS) {
      this.logger.warn('DialecticSystem: skipping taskGuide LLM due to recent failures', { sessionId, failures: failEntry.count });
      return this.buildHeuristicTaskGuide(userMessage, relevantMemories);
    }

    // Heuristic mode (fast, no LLM cost) or no provider available
    if (tgCfg.mode === 'heuristic' || (!this.provider && !providerHint)) {
      return this.buildHeuristicTaskGuide(userMessage, relevantMemories);
    }

    // Determine effective provider + model to use
    let effectiveProvider: any = undefined;
    let model = tgCfg.model || 'gpt-5-mini';

    if (providerHint) {
      if (typeof providerHint === 'object' && typeof (providerHint as any).complete === 'function') {
        effectiveProvider = providerHint;
      } else if (typeof providerHint === 'object' && providerHint.model) {
        model = providerHint.model;
        effectiveProvider = this.provider;
      } else if (typeof providerHint === 'string') {
        // string may encode a model name
        model = providerHint;
        effectiveProvider = this.provider;
      }
    } else {
      effectiveProvider = this.provider;
    }

    if (!effectiveProvider) return this.buildHeuristicTaskGuide(userMessage, relevantMemories);

    const memoryHint = (relevantMemories && relevantMemories.length > 0)
      ? `Context: ${relevantMemories.length} recent relevant memory snippets available.`
      : '';

    const short = (userMessage || '').toString().replace(/\s+/g, ' ').trim().slice(0, 240);

    const prompt = `You are a concise task summarizer for an AI dialectic system.\n\n` +
      `Produce a short TASK GUIDE (1-2 sentences) that should be prepended to downstream observers' prompts to orient their work.\n` +
      `Output only the guide text — do NOT include analysis or explanation.\n\n` +
      `USER MESSAGE:\n"""${userMessage}"""\n\n` +
      `${memoryHint}\n\n` +
      `GUIDELINES:\n- Keep it extremely short and focused (1-2 sentences).\n- Mention if code examples or debugging steps are preferred based on the user's intent.\n- Use plain language starting with 'TASK GUIDE:'.\n\n` +
      `[session:${sessionId}]`; // Explicit session marker for centralized provider

    const maxTokens = tgCfg.maxTokens ?? 64;
    const timeoutMs = tgCfg.timeoutMs ?? 5000;

    const messages = [{ role: 'user' as const, content: prompt }];
    // Allow concurrent summarizer calls so taskGuide generation doesn't collide with other dialectic requests
    const opts = { model, stream: true as const, maxTokens, allowConcurrent: true }; // removed temperature and thinking

    try {
      const stream = (effectiveProvider as any).complete(messages, opts, undefined, maybeOpts?.signal) as AsyncIterable<any>;
      const iterator = (stream as any)[Symbol.asyncIterator]() as AsyncIterator<any>;

      let collected = '';

      const start = Date.now();
      while (true) {
        const timeLeft = Math.max(0, timeoutMs - (Date.now() - start));
        if (timeLeft <= 0) {
          // timeout
          try { await iterator.return?.(); } catch {}
          this.logger.warn('DialecticSystem: taskGuide summarizer timed out');
          // record failure
          this.taskGuideFailures.set(sessionId, { count: (failEntry.count || 0) + 1, lastFailAt: Date.now() });
          break;
        }

        const nextPromise = iterator.next();
        const timeoutPromise = new Promise<never>((_, rej) => setTimeout(() => rej(new Error('timeout')), timeLeft));

        try {
          const res = await Promise.race([nextPromise, timeoutPromise]) as IteratorResult<any>;
          if (res.done) break;
          const ch = res.value;
          // Accept both token and thinking chunks as textual output
          if ((ch.type === 'token' || ch.type === 'thinking') && ch.text) collected += ch.text;
          if (ch.type === 'done') break;
          if (ch.type === 'error') {
            this.logger.warn('DialecticSystem: taskGuide summarizer error', { error: String(ch.error) });
            // record failure
            this.taskGuideFailures.set(sessionId, { count: (failEntry.count || 0) + 1, lastFailAt: Date.now() });
            break;
          }
        } catch (err) {
          // timeout or other error
          if ((err as Error).message === 'timeout') {
            try { await iterator.return?.(); } catch {}
            this.logger.warn('DialecticSystem: taskGuide summarizer timed out (race)');
            this.taskGuideFailures.set(sessionId, { count: (failEntry.count || 0) + 1, lastFailAt: Date.now() });
            break;
          }
          this.logger.warn('DialecticSystem: taskGuide summarizer failed', { error: String(err) });
          this.taskGuideFailures.set(sessionId, { count: (failEntry.count || 0) + 1, lastFailAt: Date.now() });
          break;
        }
      }

      const guideText = (collected || '').trim();
      if (guideText) {
        // Success — reset failure tracker
        this.taskGuideFailures.delete(sessionId);
        // Ensure it starts with 'TASK GUIDE' for consistency
        if (!/TASK GUIDE/i.test(guideText)) return `TASK GUIDE: ${guideText}`;
        return guideText.split('\n')[0];
      }

      // fallback
      return this.buildHeuristicTaskGuide(userMessage, relevantMemories);
    } catch (err) {
      this.logger.warn('DialecticSystem: failed to run taskGuide summarizer', { error: String(err) });
      this.taskGuideFailures.set(sessionId, { count: (failEntry.count || 0) + 1, lastFailAt: Date.now() });
      return this.buildHeuristicTaskGuide(userMessage, relevantMemories);
    }
  }

  private buildHeuristicTaskGuide(userMessage: string, relevantMemories: string[]): string {
    const short = String(userMessage || '').replace(/\s+/g, ' ').trim().slice(0, 200);
    const lc = String(userMessage || '').toLowerCase();

    let hint = 'Prioritize clarity, relevance, and actionable suggestions.';
    if (/\b(code|function|script|implement|example|snippet|program)\b/.test(lc)) {
      hint = 'Provide concise, runnable code examples where applicable.';
    } else if (/\b(error|bug|fix|debug|traceback)\b/.test(lc)) {
      hint = 'Focus on debugging steps, root causes, and reproducible fixes.';
    } else if (/\b(opinion|recommend|advice|should|best practice)\b/.test(lc)) {
      hint = 'Provide balanced recommendations with pros/cons and next steps.';
    } else if (/\b(explain|define|what is|how does)\b/.test(lc)) {
      hint = 'Provide a clear explanation and simple illustrative examples.';
    }

    const memoryHint = (relevantMemories && relevantMemories.length > 0)
      ? `Context: ${relevantMemories.length} recent relevant memory snippets available.`
      : '';

    const guide = [`TASK GUIDE: ${short}`];
    if (memoryHint) guide.push(memoryHint);
    guide.push(hint);
    return guide.join(' ');
  }

  private async persistResult(result: DialecticResult): Promise<void> {
    if (!this.db) return;
    
    try {
      // Backwards-compatible insert: some older DBs used `synthesizer_output`
      // while newer schemas use `serenity_output`. Detect which column exists
      // and insert to that column to avoid NOT NULL constraint failures.
      const cols = (this.db.prepare("PRAGMA table_info(dialectic_turns)").all() as any[]).map((c: any) => c.name);
      const hasSynth = cols.includes('synthesizer_output');
      const hasSer = cols.includes('serenity_output');

      // If the DB has both old & new columns, write to both to keep them in sync.
      const outputCols = hasSynth && hasSer ? ['synthesizer_output', 'serenity_output']
        : hasSer ? ['serenity_output']
        : hasSynth ? ['synthesizer_output']
        : ['serenity_output'];

      const insertCols = [
        'session_id', 'turn_id', 'timestamp',
        'yang_output', 'yin_output', ...outputCols,
        'signal_injected', 'total_latency_ms', 'total_cost_usd'
      ];

      const placeholders = insertCols.map(() => '?').join(', ');
      const stmt = this.db.prepare(`INSERT INTO dialectic_turns (${insertCols.join(',')}) VALUES (${placeholders})`);

      const outputJson = JSON.stringify(result.serenity || {});
      const args: any[] = [
        result.sessionId,
        result.turnId,
        result.timestamp,
        JSON.stringify(result.yang),
        JSON.stringify(result.yin),
      ];
      for (const _ of outputCols) args.push(outputJson);
      args.push(result.signalInjected ? 1 : 0, result.totalLatencyMs, result.totalCostUsd);

      try {
        this.logger.info?.('DialecticSystem: persisting result', { sessionId: result.sessionId, turnId: result.turnId, outputCols, outputJsonLength: (outputJson || '').length, argsCount: args.length });
      } catch {}

      stmt.run(...args);
    } catch (error) {
      this.logger.warn('DialecticSystem: failed to persist result', { error: String(error) });
    }
  }

  private emitSignal(sessionId: string, turnId: string, signal: DialecticSignal): void {
    if (this.eventBus) {
      (this.eventBus as any).emit?.({
        type: 'dialectic:signal',
        sessionId,
        turnId,
        signal,
      });
    }
    
    this.logger.info('DialecticSystem: signal emitted', {
      sessionId,
      turnId,
      signalType: signal.type,
      signalContent: signal.content.slice(0, 4000),
    });
  }

  // Lightweight string hashing used for legacy session markers
  private hashString(str: string): string {
    let hash = 0
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      // Convert to 32-bit integer
      hash |= 0
    }
    return Math.abs(hash).toString(36)
  }

  // ─── Query Methods ─────────────────────────────────────────────────────────

  async getRecent(sessionId: string, limit = 10): Promise<DialecticResult[]> {
    if (!this.db) return [];
    
    try {
      const rows = this.db.prepare(`
        SELECT * FROM dialectic_turns
        WHERE session_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
      `).all(sessionId, limit) as any[];
      
      return rows.map(r => ({
        sessionId: r.session_id,
        turnId: r.turn_id,
        timestamp: r.timestamp,
        yang: JSON.parse(r.yang_output),
        yin: JSON.parse(r.yin_output),
        serenity: JSON.parse(r.serenity_output ?? r.synthesizer_output ?? '{}'),
        signalInjected: Boolean(r.signal_injected),
        totalLatencyMs: r.total_latency_ms,
        totalCostUsd: r.total_cost_usd,
      }));
    } catch (error) {
      this.logger.warn('DialecticSystem: failed to get recent', { error: String(error) });
      return [];
    }
  }

  async getStats(sessionId: string): Promise<{
    totalTurns: number;
    signalsGenerated: number;
    signalsInjected: number;
    avgLatencyMs: number;
    totalCostUsd: number;
  }> {
    if (!this.db) {
      return { totalTurns: 0, signalsGenerated: 0, signalsInjected: 0, avgLatencyMs: 0, totalCostUsd: 0 };
    }

    try {
      // Determine which column to use for serenity/synthesizer output (backwards compatible)
      const cols = (this.db.prepare("PRAGMA table_info(dialectic_turns)").all() as any[]).map((c: any) => c.name);
      const serenityCol = cols.includes('serenity_output') ? 'serenity_output' : (cols.includes('synthesizer_output') ? 'synthesizer_output' : 'serenity_output');

      const sql = `
        SELECT
          COUNT(*) as total_turns,
          SUM(CASE WHEN json_extract(${serenityCol}, '$.synthesis.hasSignal') = 1 THEN 1 ELSE 0 END) as signals_generated,
          SUM(CASE WHEN signal_injected = 1 THEN 1 ELSE 0 END) as signals_injected,
          AVG(total_latency_ms) as avg_latency_ms,
          SUM(total_cost_usd) as total_cost_usd
        FROM dialectic_turns
        WHERE session_id = ?
      `;

      const row = this.db.prepare(sql).get(sessionId) as any;

      return {
        totalTurns: row?.total_turns || 0,
        signalsGenerated: row?.signals_generated || 0,
        signalsInjected: row?.signals_injected || 0,
        avgLatencyMs: Math.round(row?.avg_latency_ms || 0),
        totalCostUsd: row?.total_cost_usd || 0,
      };
    } catch (error) {
      this.logger.warn('DialecticSystem: failed to get stats', { error: String(error) });
      return { totalTurns: 0, signalsGenerated: 0, signalsInjected: 0, avgLatencyMs: 0, totalCostUsd: 0 };
    }
  }

  // NOTE: quickAnalyzeSession, quickPatternAnalysis, and fullAnalysis methods
  // temporarily disabled due to TypeScript inference issues with YangContext.
  // These methods are for the unified intelligence loop feature.
  /*
  async quickAnalyzeSession(session: any): Promise<void> {
    if (!this.config.enabled) return;

    this.logger.debug(`[Dialectic] Quick analysis for session ${session.id}`);

    // Run lightweight dialectic (yang only for speed)
    try {
      await this.processTurn(
        session.sessionId || session.id,
        `quick-${Date.now()}`,
        session.content || 'Quick analysis',
        {
          recentMemories: [],
          availableTools: [],
          sessionHistory: [],
          taskGuide: session.content || session.trigger || 'Quick analysis',
        } as any
      );
    } catch (err) {
      this.logger.warn('[Dialectic] Quick analysis error:', err);
    }
  }

  async quickPatternAnalysis(pattern: any): Promise<void> {
    if (!this.config.enabled) return;

    this.logger.debug(`[Dialectic] Quick pattern analysis: ${pattern.type}`);

    // Emit pattern as dialectic signal
    this.eventBus?.emit({
      type: 'dialectic:signal',
      signalType: 'pattern_analysis',
      content: pattern.content || pattern.type,
      confidence: pattern.confidence || 0.5,
      novelty: pattern.novelty || 0.5,
      sessionId: pattern.sessionId,
    } as any);
  }

  async fullAnalysis(options: { sessionId: string; state?: any; trigger?: string }): Promise<any> {
    if (!this.config.enabled) return null;

    this.logger.debug(`[Dialectic] Full analysis for session ${options.sessionId}`);

    try {
      return await this.processTurn(
        options.sessionId,
        `full-${Date.now()}`,
        options.state?.content || 'Deep analysis',
        {
          recentMemories: [],
          availableTools: [],
          sessionHistory: options.state?.history || [],
          taskGuide: options.trigger || 'Deep analysis',
        } as any
      );
    } catch (err) {
      this.logger.warn('[Dialectic] Full analysis error:', err);
      return null;
    }
  }
  */
}

export const createDialecticSystem = (logger: ILogger, config?: Partial<DialecticSystemConfig>): DialecticSystem =>
  new DialecticSystem(logger, config);
