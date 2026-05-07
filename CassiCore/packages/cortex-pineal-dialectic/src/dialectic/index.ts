/**
 * DialecticSystem — Consolidated Yang, Yin, Serenity
 *
 * The dialectic trio runs alongside the main agent using a single consolidated
 * LLM call that produces Yang, Yin, and Serenity analyses in one request.
 * This minimizes request count for request-based providers (e.g., GitHub Copilot).
 */

import fs from 'fs';
import path from 'path';

import Database from 'better-sqlite3';

import { ConsolidatedDialecticProcessor } from './consolidated-processor.js';
import { DialecticEngine } from './engine.js';
import { formatDialecticAsThoughts } from './thought-formatter.js';
import { getDataDir } from '../../utils/paths.js'

import type {
  IDialecticSystem,
  DialecticResult,
  ParallelDialecticResult,
  YangContext,
  DialecticStreamEvent,
  DialecticSignal,
} from '../../../types/dialectic.js';
import type { IMemory } from '../../../types/intelligence.js';
import type { ILogger , IEventBus } from '../../../types/interfaces.js';
import type { CorticalField } from '../cortex/index.js';
import type { IProvider } from '../../../types/runtime.js';
import type { ModuleSessionRegistry } from '../module-session-registry.js';
import type { GlobalBlackboardRegistry } from '../flux-team/global-blackboard-registry.js';
import type { BlackboardChannel } from '../../../types/flux-team.js';





// Re-export Yang, Yin, Serenity and their types from consolidated modules
export { YangObserver, type YangConfig, createYangObserver } from './yang.js';
export { YinObserver, type YinConfig, createYinObserver } from './yin.js';
export { Serenity, type SerenityConfig, createSerenity } from './serenity.js';

// Re-export the new DialecticEngine (string in → string out)
export { DialecticEngine, createDialecticEngine as createEngine } from './engine.js';
export { formatDialecticAsThoughts } from './thought-formatter.js';
export type {
  DialecticEngineConfig,
  ReasonOptions,
  DialecticStructuredResult,
  IDialecticEngine,
} from '../../../types/dialectic-engine.js';

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
  /**
   * When enabled, the dialectic engine runs synchronously on the user message
   * and injects its full reasoning as an assistant message — as if the model
   * thought through Yang/Yin/Unity before responding.
   *
   * This adds 2-5s of latency per turn but gives the model access to its own
   * dialectic reasoning about the current question.
   */
  injectAsThoughts?: {
    enabled?: boolean;
    /** Timeout for the synchronous dialectic call (default: 15000ms) */
    timeoutMs?: number;
    /** Use 'parallel' (3 calls, higher quality) or 'consolidated' (1 call, faster) */
    mode?: 'parallel' | 'consolidated';
  };
}

// Result Cache

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

// DialecticSystem — Always Parallel

export class DialecticSystem implements IDialecticSystem {
  readonly name = 'dialectic';

  private logger: ILogger;
  private config: DialecticSystemConfig;
  private eventBus?: IEventBus;
  private memory?: IMemory;
  private provider?: IProvider;
  private moduleRegistry?: ModuleSessionRegistry;
  private globalBlackboardRegistry?: GlobalBlackboardRegistry;
  private cortex?: CorticalField;

  private consolidatedProcessor: ConsolidatedDialecticProcessor;
  /** The new pure reasoning engine — string in → string out */
  readonly engine: DialecticEngine;
  private db?: Database.Database;
  private streamCallbacks: Map<string, Set<(event: DialecticStreamEvent) => void>> = new Map();
  private resultCache?: ResultCache;

  // Subconscious context
  /** Max patterns per session to prevent unbounded growth */
  private static readonly MAX_PATTERNS_PER_SESSION = 50;
  /** Max anomalies per session */
  private static readonly MAX_ANOMALIES_PER_SESSION = 50;
  /** Max evidence items per pattern */
  private static readonly MAX_EVIDENCE_PER_PATTERN = 20;
  /** TTL for stale session context (2 hours — safety net if session:ended never fires) */
  private static readonly SUBCONSCIOUS_TTL_MS = 2 * 60 * 60 * 1000;

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
      dataDir: config?.dataDir ?? getDataDir(),
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
        model: this.config.yang?.model ?? 'gpt-4o',
      },
    );

    // Initialize the pure reasoning engine (string in → string out)
    this.engine = new DialecticEngine(this.logger, {
      maxBranches: this.config.yang?.maxBranches ?? 3,
      yangTemperature: this.config.yang?.temperature ?? 0.8,
      yinTemperature: this.config.yin?.temperature ?? 0.3,
      unityTemperature: this.config.serenity?.temperature ?? 0.4,
      model: this.config.yang?.model ?? 'gpt-4o',
      maxTokens: 2000,
      postureTimeoutMs: this.config.parallel?.observerTimeoutMs ?? 30_000,
    });

    if (this.config.cache?.enabled) {
      this.resultCache = new ResultCache(
        this.config.cache.ttlMs,
        this.config.cache.similarityThreshold
      );
    }

    if (this.config.enabled) {
      this.initPersistence();
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
      this.db.pragma('busy_timeout = 5000');

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
    this.engine.setProvider(provider);
    this.logger.info('DialecticSystem: provider wired');
  }

  /** Wire the module session registry for persistent debug sessions. */
  setModuleRegistry(registry: ModuleSessionRegistry): void {
    this.moduleRegistry = registry;
    this.consolidatedProcessor.setModuleRegistry(registry);
    // Propagate registry to voice instances for consistent session tracking
    for (const key of ['yang', 'yin', 'serenity'] as const) {
      const voice = (this as any)[key];
      if (voice && typeof voice.setModuleRegistry === 'function') {
        voice.setModuleRegistry(registry);
      }
    }
    registry.getOrCreate('dialectic');
    registry.getOrCreate('dialectic.guide');
    this.logger.info('DialecticSystem: module registry wired');
  }

  setMemory(memory: IMemory): void {
    this.memory = memory;
    this.consolidatedProcessor.setMemory(memory);
    this.logger.info('DialecticSystem: memory wired');
  }

  /** Wire the GlobalBlackboardRegistry for posting to named global boards. */
  setGlobalBlackboardRegistry(registry: GlobalBlackboardRegistry): void {
    this.globalBlackboardRegistry = registry;
    this.logger.info('DialecticSystem: global blackboard registry wired');
  }

  setCortex(cortex: CorticalField): void {
    this.cortex = cortex
  }

  /** Post an entry to a named global board. Fire-and-forget — never throws. */
  private postToBoard(
    boardName: string,
    channel: BlackboardChannel,
    content: string,
    opts?: { author?: string; tags?: string[]; priority?: number },
  ): void {
    try {
      const board = this.globalBlackboardRegistry?.getOrCreate(boardName, { persist: true });
      board?.post(channel, {
        content,
        author: opts?.author ?? this.name,
        tags: opts?.tags ?? [],
        priority: opts?.priority ?? 0,
      });
    } catch (err) {
      this.logger.debug('DialecticSystem: blackboard post failed (non-fatal)', { error: String(err), boardName, channel });
    }
  }

  /**
   * Stop the dialectic system. Closes persistence; no-op when already stopped.
   */
  async stop(): Promise<void> {
    if (this.db) {
      try { this.db.close(); } catch {}
      this.db = undefined;
    }
  }

  /**
   * Run the dialectic engine on the user message and return the full reasoning
   * formatted as natural inner-monologue prose, suitable for injection as an
   * assistant message.
   *
   * Returns null if inject-as-thoughts is disabled, no provider is available,
   * or the dialectic fails/times out.
   */
  async reasonAsThoughts(
    userMessage: string,
    opts?: { signal?: AbortSignal; context?: string },
  ): Promise<string | null> {
    const thoughtConfig = this.config.injectAsThoughts;
    if (!thoughtConfig?.enabled) return null;
    if (!this.provider) {
      this.logger.debug('DialecticSystem.reasonAsThoughts: no provider, skipping');
      return null;
    }

    const timeoutMs = thoughtConfig.timeoutMs ?? 15_000;
    const mode = thoughtConfig.mode ?? 'consolidated';

    try {
      const result = await Promise.race([
        this.engine.reasonStructured(userMessage, {
          context: opts?.context,
          mode,
          signal: opts?.signal,
        }),
        new Promise<null>((resolve) => setTimeout(() => resolve(null), timeoutMs)),
      ]);

      if (!result) {
        this.logger.info('DialecticSystem.reasonAsThoughts: timed out');
        return null;
      }

      const thoughts = formatDialecticAsThoughts(result);
      this.logger.info('DialecticSystem.reasonAsThoughts: complete', {
        selected: result.unity.selected,
        tension: result.quality.tension.toFixed(2),
        confidence: result.quality.dialecticQuality.toFixed(2),
        thoughtChars: thoughts.length,
        latencyMs: result.meta.totalLatencyMs,
      });

      return thoughts;
    } catch (err) {
      this.logger.warn('DialecticSystem.reasonAsThoughts: failed', { error: String(err) });
      return null;
    }
  }

  /** Whether inject-as-thoughts mode is enabled. */
  get injectAsThoughtsEnabled(): boolean {
    return !!this.config.injectAsThoughts?.enabled;
  }

  /** Hot-update the injectAsThoughts config at runtime. */
  setInjectAsThoughts(opts: { enabled?: boolean; timeoutMs?: number; mode?: 'parallel' | 'consolidated' }): void {
    this.config = {
      ...this.config,
      injectAsThoughts: { ...this.config.injectAsThoughts, ...opts },
    };
    this.logger.info('DialecticSystem: injectAsThoughts updated', { ...this.config.injectAsThoughts });
  }

  onEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    this.consolidatedProcessor.setEventBus(bus);
    this.setupSubconsciousListeners(bus);
    this.logger.info('DialecticSystem: event bus wired');
  }

  private setupSubconsciousListeners(bus: IEventBus): void {
    // Accumulate subconscious patterns with confidence tracking and evidence capping
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
          const newEvidence = pattern.evidence || [];
          for (const ev of newEvidence) {
            if (existing.evidence.length >= DialecticSystem.MAX_EVIDENCE_PER_PATTERN) break;
            existing.evidence.push(ev);
          }
        } else if (ctx.patterns.length < DialecticSystem.MAX_PATTERNS_PER_SESSION) {
          const evidence = (pattern.evidence || []).slice(0, DialecticSystem.MAX_EVIDENCE_PER_PATTERN);
          ctx.patterns.push({ type: pattern.pattern, confidence: pattern.confidence, evidence });
        }
        ctx.lastUpdated = Date.now();
      } catch {}
    });

    // Track session intent direction for dialectic context enrichment
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

    // Accumulate anomaly signals for risk-aware dialectic analysis
    (bus as any).on?.('subconscious:anomaly', (e: any) => {
      try {
        const { sessionId, anomaly } = e;
        if (!sessionId || !anomaly) return;
        let ctx = this.subconsciousContext.get(sessionId);
        if (!ctx) {
          ctx = { patterns: [], anomalies: [], lastUpdated: Date.now() };
          this.subconsciousContext.set(sessionId, ctx);
        }
        if (ctx.anomalies.length < DialecticSystem.MAX_ANOMALIES_PER_SESSION) {
          ctx.anomalies.push({ category: anomaly.category, severity: anomaly.severity });
        }
        ctx.lastUpdated = Date.now();
      } catch {}
    });

    // Clean up on explicit session end — prevents memory leaks in long-running daemon
    (bus as any).on?.('subconscious:session:ended', (e: any) => {
      try {
        const { sessionId } = e;
        if (sessionId) {
          this.subconsciousContext.delete(sessionId);
          this.streamCallbacks.delete(sessionId);
        }
      } catch {}
    });

    // Fallback cleanup for sessions that don't emit subconscious:session:ended
    (bus as any).on?.('session:ended', (e: any) => {
      try {
        const { sessionId } = e;
        if (sessionId) {
          this.subconsciousContext.delete(sessionId);
          this.streamCallbacks.delete(sessionId);
        }
      } catch {}
    });
  }

  subscribeToStream(sessionId: string, callback: (event: DialecticStreamEvent) => void): () => void {
    if (!this.streamCallbacks.has(sessionId)) {
      this.streamCallbacks.set(sessionId, new Set());
    }
    this.streamCallbacks.get(sessionId)!.add(callback);
    return () => {
      const set = this.streamCallbacks.get(sessionId);
      if (set) {
        set.delete(callback);
        // Remove empty Sets to prevent Map entry leak
        if (set.size === 0) this.streamCallbacks.delete(sessionId);
      }
    };
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

    // Prune stale subconscious context to prevent unbounded memory growth
    if (this.subconsciousContext.size > 0) {
      const ttlCutoff = Date.now() - DialecticSystem.SUBCONSCIOUS_TTL_MS;
      for (const [sid, ctx] of this.subconsciousContext) {
        if (ctx.lastUpdated < ttlCutoff) {
          this.subconsciousContext.delete(sid);
        }
      }
    }

    // Skip cache when caller needs fresh results (autonomous iterations, testing)
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
      // Generate lightweight task framing to focus dialectic analysis
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

      // Stream task guide early so UI can show intent before dialectic completes
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

      // Cache result for semantic similarity matching on near-duplicate queries
      if (this.resultCache) {
        this.resultCache.set(userMessage, result);
      }

      // Persist to SQLite for analytics and debugging
      await this.persistResult(result);

      // Inject signal on every turn that produces one — dialectic enrichment is valuable even for non-urgent signals
      if (result.serenity.synthesis.hasSignal && result.serenity.synthesis.signal) {
        this.emitSignal(sessionId, turnId, result.serenity.synthesis.signal, result.requestId);
      }

      // Post to global blackboard so other agents/sessions see dialectic insights
      this.postToBoard('system:dialectic', 'findings', JSON.stringify({
        sessionId,
        turnId,
        synthesis: result.serenity.synthesis,
        hasSignal: result.serenity.synthesis.hasSignal,
        timestamp: result.timestamp,
      }), { tags: ['synthesis'] });

      // Post high-priority signals (tensions/gaps/edge cases) to concerns channel for review
      if (result.serenity.synthesis.hasSignal && result.serenity.synthesis.signal) {
        const signal = result.serenity.synthesis.signal;
        if (signal.type === 'tension' || signal.type === 'gap' || signal.type === 'edge_case') {
          this.postToBoard('system:dialectic', 'concerns', JSON.stringify({
            sessionId,
            turnId,
            signalType: signal.type,
            content: signal.content,
            confidence: signal.confidence,
            urgency: signal.urgency,
            timestamp: result.timestamp,
          }), { tags: ['tension', signal.type] });
        }
      }

      if (this.cortex) {
        const synthesis = result.serenity.synthesis
        if (synthesis.hasSignal && synthesis.signal) {
          const sig = synthesis.signal
          const isThreat = sig.type === 'tension' || sig.type === 'gap' || sig.type === 'edge_case'
          const urgencyBoost = sig.urgency === 'immediate' ? 1.0 : 0.7
          this.cortex.signal(isThreat ? 'limbic' : 'executive', {
            type: isThreat ? 'concern' : 'decision',
            content: sig.content,
            author: 'dialectic',
            sessionId,
            salience: Math.min(1.0, sig.confidence * urgencyBoost),
            valence: isThreat ? -0.3 : 0.2,
            confidence: sig.confidence,
            tags: [sig.type],
          })
        }
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
      for await (const chunk of this.provider!.complete(messages, {
        source: 'dialectic:guide',
        allowConcurrent: true,
        dedupe: false,
        // Bind to persistent module debug session for Telegram observability
        sessionId: this.moduleRegistry?.getSessionId('dialectic.guide'),
      } as any)) {
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

  private emitSignal(sessionId: string, turnId: string, signal: DialecticSignal, requestId?: string): void {
    (this.eventBus as any)?.emit?.({ type: 'dialectic:signal', sessionId, turnId, signal, requestId });
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

/**
 * @dep callers: main (scripts/test_persist.js), runMock (scripts/simulate-dialectic.js), runMockLoop (scripts/simulate-dialectic-multi.js), createIntelligence (core/intelligence/index.ts), dialectic-task-guide.test.ts (tests/dialectic-task-guide.test.ts) [+1]
 * @dep module: Unknown
 * @dep risk: MEDIUM | 6 callers, 0 flows, 1 module
 */

export const createDialecticSystem = (logger: ILogger, config?: Partial<DialecticSystemConfig>): DialecticSystem =>
  new DialecticSystem(logger, config);
