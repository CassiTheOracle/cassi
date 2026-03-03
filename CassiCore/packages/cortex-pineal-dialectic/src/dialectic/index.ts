/**
 * DialecticSystem — Consolidated Yang, Yin, Serenity
 *
 * The dialectic trio runs alongside the main agent using a single consolidated
 * LLM call that produces Yang, Yin, and Serenity analyses in one request.
 * This minimizes request count for request-based providers (e.g., GitHub Copilot).
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
} from '../../../types/dialectic.js';
import type { IProvider } from '../../../types/runtime.js';
import type { IMemory } from '../../../types/intelligence.js';
import { ConsolidatedDialecticProcessor } from './consolidated-processor.js';
import { PromptOptimizer, createPromptOptimizer } from './prompt-optimizer.js';
import type { PromptOptimizerConfig } from '../../../types/dialectic.js';
import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

export interface DialecticSystemConfig {
  enabled: boolean;
  yang?: { enabled?: boolean; model?: string; temperature?: number; maxBranches?: number };
  yin?: { enabled?: boolean; model?: string; temperature?: number };
  serenity?: { enabled?: boolean; model?: string; temperature?: number };
  parallel?: {
    maxWaitMs?: number;
    observerTimeoutMs?: number;
    partialResultsOnFailure?: boolean;
  };
  dataDir?: string;
  cache?: {
    enabled?: boolean;
    ttlMs?: number;
    similarityThreshold?: number;
  };
  taskGuide?: {
    enabled?: boolean;
    mode?: 'heuristic' | 'llm';
    timeoutMs?: number;
    model?: string;
  };
  promptOptimizer?: Partial<PromptOptimizerConfig>;
}

// ============================================================================
// Result Cache
// ============================================================================

interface CacheEntry {
  result: ParallelDialecticResult;
  timestamp: number;
}

class ResultCache {
  private cache = new Map<string, CacheEntry>();
  private readonly ttlMs: number;
  private readonly similarityThreshold: number;

  constructor(ttlMs = 30000, similarityThreshold = 0.85) {
    this.ttlMs = ttlMs;
    this.similarityThreshold = similarityThreshold;
  }

  get(userMessage: string): ParallelDialecticResult | undefined {
    const normalized = this.normalize(userMessage);
    const now = Date.now();

    for (const [key, entry] of this.cache) {
      if (now - entry.timestamp > this.ttlMs) {
        this.cache.delete(key);
        continue;
      }
      if (this.jaccardSimilarity(normalized, this.keyToSet(key)) >= this.similarityThreshold) {
        return entry.result;
      }
    }
    return undefined;
  }

  set(userMessage: string, result: ParallelDialecticResult): void {
    this.cache.set(this.normalizeToKey(userMessage), {
      result,
      timestamp: Date.now(),
    });
  }

  private normalize(text: string): Set<string> {
    const words = text.toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .split(/\s+/)
      .filter(w => w.length > 2);
    return new Set(words);
  }

  private normalizeToKey(text: string): string {
    return text.toLowerCase().replace(/[^\w]/g, '').slice(0, 200);
  }

  private keyToSet(key: string): Set<string> {
    const words = key.match(/.{1,4}/g) || [];
    return new Set(words);
  }

  private jaccardSimilarity(a: Set<string>, b: Set<string>): number {
    const intersection = [...a].filter(x => b.has(x)).length;
    const union = new Set([...a, ...b]).size;
    return union === 0 ? 0 : intersection / union;
  }
}

// ============================================================================
// DialecticSystem — Always Parallel
// ============================================================================

export class DialecticSystem implements IDialecticSystem {
  readonly name = 'dialectic';

  private logger: ILogger;
  private config: DialecticSystemConfig;
  private eventBus?: IEventBus;
  private memory?: IMemory;
  private provider?: IProvider;

  private consolidatedProcessor: ConsolidatedDialecticProcessor;
  private promptOptimizer?: PromptOptimizer;
  private db?: Database.Database;
  private streamCallbacks: Map<string, Set<(event: DialecticStreamEvent) => void>> = new Map();
  private resultCache?: ResultCache;

  // Subconscious context
  private subconsciousContext = new Map<string, {
    patterns: Array<{ type: string; confidence: number; evidence: string[] }>;
    intent?: { type: string; confidence: number };
    anomalies: Array<{ category: string; severity: string }>;
    lastUpdated: number;
  }>();

  constructor(logger: ILogger, config?: Partial<DialecticSystemConfig>) {
    this.logger = logger.child?.('dialectic') ?? logger;
    this.config = {
      enabled: config?.enabled ?? true,
      yang: config?.yang ?? {},
      yin: config?.yin ?? {},
      serenity: config?.serenity ?? {},
      dataDir: config?.dataDir ?? path.join(process.env.HOME || require('os').homedir(), '.cassicore', 'data'),
      cache: { enabled: true, ttlMs: 30000, similarityThreshold: 0.85, ...config?.cache },
      taskGuide: config?.taskGuide,
    };

    // Use consolidated processor (single LLM call for Yang+Yin+Serenity)
    this.consolidatedProcessor = new ConsolidatedDialecticProcessor(
      this.logger,
      {
        observerTimeoutMs: this.config.parallel?.observerTimeoutMs ?? 30_000,
        maxBranches: this.config.yang?.maxBranches ?? 3,
        temperature: this.config.yang?.temperature ?? 0.7,
        model: this.config.yang?.model ?? 'gpt-5-mini',
      },
    );

    // Create and wire prompt optimizer if enabled
    const optimizerConfig = this.config.promptOptimizer;
    if (optimizerConfig?.enabled !== false) {
      const persistPath = optimizerConfig?.persistPath ||
        path.join(this.config.dataDir!, 'prompt-optimizer.json');
      this.promptOptimizer = createPromptOptimizer(this.logger, {
        ...optimizerConfig,
        persistPath,
      });
      this.consolidatedProcessor.setPromptOptimizer(this.promptOptimizer);
    }

    if (this.config.cache?.enabled) {
      this.resultCache = new ResultCache(
        this.config.cache.ttlMs,
        this.config.cache.similarityThreshold
      );
    }

    if (this.config.enabled) {
      this.initPersistence();
      // Initialize prompt optimizer (loads persisted scores, starts auto-save)
      if (this.promptOptimizer) {
        this.promptOptimizer.init().catch(err => {
          this.logger.warn('DialecticSystem: prompt optimizer init failed', { error: String(err) });
        });
      }
      this.logger.info('DialecticSystem: enabled (parallel mode)');
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
    } catch (error) {
      this.logger.error('DialecticSystem: persistence init failed', { error: String(error) });
    }
  }

  setProvider(provider: IProvider): void {
    this.provider = provider;
    this.consolidatedProcessor.setProvider(provider);
    this.logger.info('DialecticSystem: provider wired');
  }

  setMemory(memory: IMemory): void {
    this.memory = memory;
    this.consolidatedProcessor.setMemory(memory);
    this.logger.info('DialecticSystem: memory wired');
  }

  /**
   * Stop the dialectic system — flush optimizer state and clean up timers.
   */
  async stop(): Promise<void> {
    if (this.promptOptimizer) {
      await this.promptOptimizer.stop();
      this.logger.info('DialecticSystem: prompt optimizer stopped');
    }
    if (this.db) {
      try { this.db.close(); } catch {}
      this.db = undefined;
    }
  }

  onEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    this.consolidatedProcessor.setEventBus(bus);
    this.setupSubconsciousListeners(bus);
    this.logger.info('DialecticSystem: event bus wired');
  }

  private setupSubconsciousListeners(bus: IEventBus): void {
    (bus as any).on?.('subconscious:pattern', (e: any) => {
      try {
        const { sessionId, pattern } = e;
        if (!sessionId || !pattern) return;
        let ctx = this.subconsciousContext.get(sessionId);
        if (!ctx) {
          ctx = { patterns: [], anomalies: [], lastUpdated: Date.now() };
          this.subconsciousContext.set(sessionId, ctx);
        }
        const existing = ctx.patterns.find(p => p.type === pattern.pattern);
        if (existing) {
          existing.confidence = Math.max(existing.confidence, pattern.confidence);
          existing.evidence.push(...pattern.evidence);
        } else {
          ctx.patterns.push({ type: pattern.pattern, confidence: pattern.confidence, evidence: pattern.evidence || [] });
        }
        ctx.lastUpdated = Date.now();
      } catch {}
    });

    (bus as any).on?.('subconscious:intent', (e: any) => {
      try {
        const { sessionId, intent } = e;
        if (!sessionId || !intent?.to) return;
        let ctx = this.subconsciousContext.get(sessionId);
        if (!ctx) {
          ctx = { patterns: [], anomalies: [], lastUpdated: Date.now() };
          this.subconsciousContext.set(sessionId, ctx);
        }
        ctx.intent = { type: intent.to.type, confidence: intent.to.confidence };
        ctx.lastUpdated = Date.now();
      } catch {}
    });

    (bus as any).on?.('subconscious:anomaly', (e: any) => {
      try {
        const { sessionId, anomaly } = e;
        if (!sessionId || !anomaly) return;
        let ctx = this.subconsciousContext.get(sessionId);
        if (!ctx) {
          ctx = { patterns: [], anomalies: [], lastUpdated: Date.now() };
          this.subconsciousContext.set(sessionId, ctx);
        }
        ctx.anomalies.push({ category: anomaly.category, severity: anomaly.severity });
        ctx.lastUpdated = Date.now();
      } catch {}
    });

    (bus as any).on?.('subconscious:session:ended', (e: any) => {
      try {
        const { sessionId } = e;
        if (sessionId) this.subconsciousContext.delete(sessionId);
      } catch {}
    });
  }

  subscribeToStream(sessionId: string, callback: (event: DialecticStreamEvent) => void): () => void {
    if (!this.streamCallbacks.has(sessionId)) {
      this.streamCallbacks.set(sessionId, new Set());
    }
    this.streamCallbacks.get(sessionId)!.add(callback);
    return () => { this.streamCallbacks.get(sessionId)?.delete(callback); };
  }

  private emitStreamEvent(sessionId: string, event: DialecticStreamEvent): void {
    this.streamCallbacks.get(sessionId)?.forEach(cb => { try { cb(event); } catch {} });
    (this.eventBus as any)?.emit?.({ type: 'dialectic:stream', sessionId, ...event });
  }

  async processTurn(
    sessionId: string,
    turnId: string,
    userMessage: string,
    context: YangContext,
    opts?: {
      providers?: Record<string, unknown>;
      signal?: AbortSignal;
      skipCache?: boolean;
    }
  ): Promise<ParallelDialecticResult> {
    const startTime = Date.now();

    // Check cache first (unless explicitly skipped for autonomous iterations)
    if (this.resultCache && !opts?.skipCache) {
      const cached = this.resultCache.get(userMessage);
      if (cached) {
        this.logger.info('DialecticSystem: cache hit', { sessionId, turnId });
        return { ...cached, sessionId, turnId, timestamp: startTime };
      }
    }

    if (!this.config.enabled) {
      return this.createEmptyResult(sessionId, turnId, startTime);
    }

    // Merge subconscious context
    const subCtx = this.subconsciousContext.get(sessionId);
    if (subCtx && Date.now() - subCtx.lastUpdated < 5 * 60 * 1000) {
      context = {
        ...context,
        subconsciousPatterns: subCtx.patterns,
        subconsciousIntent: subCtx.intent,
        subconsciousAnomalies: subCtx.anomalies,
      };
    }

    try {
      // Generate task guide if configured
      const taskGuideConfig = this.config.taskGuide;
      if (taskGuideConfig?.enabled && !context.taskGuide) {
        if (taskGuideConfig.mode === 'llm' && this.provider) {
          try {
            const guideText = await this.generateLlmTaskGuide(userMessage, taskGuideConfig.timeoutMs ?? 3000);
            if (guideText) {
              context = { ...context, taskGuide: guideText };
            }
          } catch (err) {
            this.logger.warn('DialecticSystem: LLM task guide generation failed, falling back to heuristic', { error: String(err) });
            context = { ...context, taskGuide: `TASK GUIDE: Address the user's request: "${userMessage.slice(0, 160)}" using the provided context.` };
          }
        } else {
          // Heuristic mode (default)
          context = { ...context, taskGuide: `TASK GUIDE: Address the user's request: "${userMessage.slice(0, 160)}" using the provided context.` };
        }
      }

      // Emit task guide in stream start event if generated
      if (context.taskGuide) {
        this.emitStreamEvent(sessionId, {
          timestamp: Date.now(),
          turnId,
          stage: 'start',
          data: { mode: 'parallel', taskGuide: context.taskGuide },
        });
      }

      // Use consolidated processor (single LLM call for Yang+Yin+Serenity)
      const result = await this.consolidatedProcessor.processTurn(
        sessionId,
        turnId,
        userMessage,
        context,
        (event: DialecticStreamEvent) => this.emitStreamEvent(sessionId, event),
        { signal: opts?.signal }
      );

      // Cache result
      if (this.resultCache) {
        this.resultCache.set(userMessage, result);
      }

      // Persist
      await this.persistResult(result);

      // Emit signal if urgent
      if (result.serenity.synthesis.hasSignal && result.serenity.synthesis.signal?.urgency === 'immediate') {
        this.emitSignal(sessionId, turnId, result.serenity.synthesis.signal);
      }

      return result;
    } catch (error) {
      this.logger.error('DialecticSystem: turn failed', { error: String(error) });
      this.emitStreamEvent(sessionId, { timestamp: Date.now(), turnId, stage: 'error', data: { error: String(error) } });
      throw error;
    }
  }

  /**
   * Generate a task guide using the LLM provider.
   * Returns the guide text or null if generation fails or times out.
   */
  private async generateLlmTaskGuide(userMessage: string, timeoutMs: number): Promise<string | null> {
    if (!this.provider) return null;

    const messages = [{
      role: 'system' as const,
      content: `You are a concise task summarizer. Given a user message, produce a brief TASK GUIDE (1-3 sentences) that helps an AI assistant understand what the user needs. Start your response with "TASK GUIDE:".`,
    }, {
      role: 'user' as const,
      content: userMessage,
    }];

    let guideText = '';

    const guidePromise = (async () => {
      for await (const chunk of this.provider!.complete(messages, {} as any)) {
        if (chunk.type === 'token' && chunk.text) {
          guideText += chunk.text;
        }
        if (chunk.type === 'done') break;
      }
      return guideText.trim() || null;
    })();

    const timeoutPromise = new Promise<null>((resolve) => setTimeout(() => resolve(null), timeoutMs));

    return Promise.race([guidePromise, timeoutPromise]);
  }

  private createEmptyResult(sessionId: string, turnId: string, timestamp: number): ParallelDialecticResult {
    return {
      sessionId,
      turnId,
      timestamp,
      yang: { branches: [], meta: { expansionTemperature: 0.9, generationTimeMs: 0, inputTokens: 0, outputTokens: 0 } },
      yin: { baselineBranches: [], selfCritiques: [], meta: { compressionRatio: 1.0, processingTimeMs: 0, inputTokens: 0, outputTokens: 0, relativeTiming: 'concurrent' } },
      serenity: {
        synthesis: { hasSignal: false, branchesConsidered: 0, branchesSurfaced: 0 },
        meta: { dialecticQuality: 0.5, processingTimeMs: 0, inputTokens: 0, outputTokens: 0 },
      },
      signalInjected: false,
      totalLatencyMs: 0,
      totalCostUsd: 0,
      level: 0,
      executionMode: 'parallel',
      timing: { yangDuration: 0, yinDuration: 0, serenityDuration: 0, totalParallelTime: 0, firstCompletion: 'yang' },
      quality: { yangYinAgreement: 0, dialecticTension: 0, synthesisConfidence: 0 },
    };
  }

  private async persistResult(result: ParallelDialecticResult): Promise<void> {
    if (!this.db) return;
    try {
      this.db.prepare(`INSERT INTO dialectic_turns
        (session_id, turn_id, timestamp, yang_output, yin_output, serenity_output, signal_injected, total_latency_ms, total_cost_usd)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`).run(
        result.sessionId,
        result.turnId,
        result.timestamp,
        JSON.stringify(result.yang),
        JSON.stringify(result.yin),
        JSON.stringify(result.serenity),
        result.signalInjected ? 1 : 0,
        result.totalLatencyMs,
        result.totalCostUsd
      );
    } catch (error) {
      this.logger.warn('DialecticSystem: persist failed', { error: String(error) });
    }
  }

  private emitSignal(sessionId: string, turnId: string, signal: DialecticSignal): void {
    (this.eventBus as any)?.emit?.({ type: 'dialectic:signal', sessionId, turnId, signal });
  }

  async getRecent(sessionId: string, limit = 10): Promise<DialecticResult[]> {
    if (!this.db) return [];
    try {
      const rows = this.db.prepare(`SELECT * FROM dialectic_turns WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?`).all(sessionId, limit) as any[];
      return rows.map(r => ({
        sessionId: r.session_id,
        turnId: r.turn_id,
        timestamp: r.timestamp,
        yang: JSON.parse(r.yang_output),
        yin: JSON.parse(r.yin_output),
        serenity: JSON.parse(r.serenity_output),
        signalInjected: Boolean(r.signal_injected),
        totalLatencyMs: r.total_latency_ms,
        totalCostUsd: r.total_cost_usd,
      }));
    } catch { return []; }
  }

  async getStats(sessionId: string) {
    if (!this.db) {
      return { totalTurns: 0, signalsGenerated: 0, signalsInjected: 0, avgLatencyMs: 0, totalCostUsd: 0 };
    }
    try {
      const row = this.db.prepare(`SELECT
        COUNT(*) as total_turns,
        SUM(CASE WHEN json_extract(serenity_output, '$.synthesis.hasSignal') = 1 THEN 1 ELSE 0 END) as signals_generated,
        SUM(CASE WHEN signal_injected = 1 THEN 1 ELSE 0 END) as signals_injected,
        AVG(total_latency_ms) as avg_latency_ms,
        SUM(total_cost_usd) as total_cost_usd
        FROM dialectic_turns WHERE session_id = ?`).get(sessionId) as any;
      return {
        totalTurns: row?.total_turns || 0,
        signalsGenerated: row?.signals_generated || 0,
        signalsInjected: row?.signals_injected || 0,
        avgLatencyMs: Math.round(row?.avg_latency_ms || 0),
        totalCostUsd: row?.total_cost_usd || 0,
      };
    } catch {
      return { totalTurns: 0, signalsGenerated: 0, signalsInjected: 0, avgLatencyMs: 0, totalCostUsd: 0 };
    }
  }
}

export const createDialecticSystem = (logger: ILogger, config?: Partial<DialecticSystemConfig>): DialecticSystem =>
  new DialecticSystem(logger, config);
