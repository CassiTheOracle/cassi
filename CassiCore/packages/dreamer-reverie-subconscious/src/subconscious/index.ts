/**
 * Subconscious — Real-time stream interlay with ContextManager integration (v4)
 *
 * The Subconscious serves as the interlay between the main agent's thought
 * stream and the rest of the CassiCore intelligence layer.
 *
 * v4 Features:
 * - Real-time stream processing via StreamIngestor
 * - MentalModel for evolving conversation understanding
 * - SignalGenerator for structured intelligence signals
 * - ContextManager integration for enriched context
 * - Backward compatible with v3 (60s consolidation)
 *
 * Integration points:
 * - Stream events: turn:token, turn:thinking, turn:tool_call
 * - Context enrichment: Periodic refresh from ContextManager
 * - Signal emission: Real-time events for Dialectic, Thinker, Optimizer
 * - Background consolidation: Learnings persistence (60s interval)
 *
 * Emits events:
 * - subconscious:token, subconscious:thinking, subconscious:tool
 * - subconscious:state:updated, subconscious:context:enriched
 * - subconscious:signal, subconscious:pattern, subconscious:intent
 * - subconscious:anomaly, subconscious:opportunity
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js';
import type { IMemory } from '../../../types/intelligence.js';
import type { DialecticSignal } from '../../../types/dialectic.js';
import type { IProvider, Message, CompletionChunk } from '../../../types/runtime.js';
import type { RuntimeEvent } from '../../../types/events.js';
import fs from 'fs';
import path from 'path';

// v2 Components
import {
  SubconsciousConfigV2,
  DEFAULT_SUBCONSCIOUS_CONFIG_V2,
  MentalModelSnapshot,
  ModelDelta,
  EnrichedContext,
} from './types.js';
import { StreamIngestorImpl, createStreamIngestor } from './stream-ingestor.js';
import { MentalModelImpl, createMentalModel, calculateModelDelta } from './mental-model.js';
import { SignalGeneratorImpl, createSignalGenerator } from './signal-generator.js';

// Legacy v3 Components
import { SubconsciousSearch, SearchConfig } from './enhanced-search.js';

// Legacy v3 Config (for backward compatibility)
export interface SubconsciousConfig {
  enabled?: boolean;
  consolidationIntervalMs?: number;
  minSignals?: number;
  persistMemory?: boolean;
  persistToFile?: boolean;
  dataDir?: string;
  persistConfidenceThreshold?: number;
  priority?: number;

  // Proactive mode settings
  proactiveMode?: boolean;
  readAlongEnabled?: boolean;
  memoryQueryOnTurn?: boolean;
  actionThreshold?: number;
  proactiveActionCooldownMs?: number;

  // Embedding / clustering
  embeddingService?: 'ollama' | 'none';
  embeddingModel?: string;
  embeddingTimeoutMs?: number;
  embeddingBatchSize?: number;
  maxSignalsPerCycle?: number;
  clusterSimilarityThreshold?: number;
  maxClustersPerBatch?: number;

  // Summarization via LLM
  summarizerEnabled?: boolean;
  summarizerModel?: string;
  summarizerMaxTokens?: number;
  summarizerTemperature?: number;
  summarizerTimeoutMs?: number;

  // Anomaly parameters
  recencyWindowMs?: number;

  // v2 Feature Flag
  v2?: boolean;

  // v2 Configuration
  stream?: SubconsciousConfigV2['stream'];
  context?: SubconsciousConfigV2['context'];
  signals?: SubconsciousConfigV2['signals'];
  mentalModel?: SubconsciousConfigV2['mentalModel'];
  consolidation?: SubconsciousConfigV2['consolidation'];
}

// Legacy types
interface TurnObservation {
  sessionId: string;
  turnId: string;
  userMessage: string;
  assistantResponse: string;
  tokens: string[];
  startTime: number;
  endTime?: number;
  memoryContext?: Array<{ content: string; score: number }>;
  patternsDetected: string[];
  actionsTaken: string[];
}

interface ProactiveAction {
  type: 'suggest_context' | 'surface_memory' | 'flag_pattern' | 'trigger_workflow';
  confidence: number;
  payload: any;
  timestamp: number;
}

export class Subconscious {
  readonly name = 'subconscious' as const;
  readonly priority: number;

  private logger: ILogger;
  private config: Required<SubconsciousConfig>;
  private memory?: IMemory;
  private eventBus?: IEventBus;
  private provider?: IProvider;

  // v2 Components
  private streamIngestor?: StreamIngestorImpl;
  private mentalModels = new Map<string, MentalModelImpl>();
  private signalGenerator?: SignalGeneratorImpl;
  private v2Config: SubconsciousConfigV2;

  // Legacy v3 Components
  private turnObservations = new Map<string, TurnObservation>();
  private signalBuffer: Array<{ sessionId?: string; turnId?: string; signal: DialecticSignal; ts: number }> = [];
  private recentActions: ProactiveAction[] = [];
  private timer?: NodeJS.Timeout;
  private filePath: string;
  private avgCounts: Record<string, number> = {};
  private recentLearnings: Array<{ summary: string; timestamp: number; confidence?: number }> = [];
  private activeTurns = new Map<string, {
    messages: Message[];
    tokens: string[];
    patterns: Set<string>;
    memoryQueried: boolean;
    startTime: number;
  }>();
  private enhancedSearch: SubconsciousSearch;

  // ContextManager reference (for v2 enrichment)
  private contextManager?: any;
  private contextRefreshTimers = new Map<string, NodeJS.Timeout>();

  constructor(logger: ILogger, config?: Partial<SubconsciousConfig>) {
    this.logger = logger.child?.('subconscious') ?? logger;

    // Merge legacy and v2 configs
    this.config = {
      enabled: config?.enabled ?? true,
      consolidationIntervalMs: config?.consolidationIntervalMs ?? 60_000,
      minSignals: config?.minSignals ?? 3,
      persistMemory: config?.persistMemory ?? true,
      persistToFile: config?.persistToFile ?? true,
      dataDir: config?.dataDir ?? path.join(process.env.HOME || require('os').homedir(), '.cassicore', 'data'),
      persistConfidenceThreshold: config?.persistConfidenceThreshold ?? 0.85,
      priority: config?.priority ?? 40,
      proactiveMode: config?.proactiveMode ?? true,
      readAlongEnabled: config?.readAlongEnabled ?? true,
      memoryQueryOnTurn: config?.memoryQueryOnTurn ?? true,
      actionThreshold: config?.actionThreshold ?? 0.7,
      proactiveActionCooldownMs: config?.proactiveActionCooldownMs ?? 5000,
      embeddingService: config?.embeddingService ?? 'ollama',
      embeddingModel: config?.embeddingModel ?? process.env.OLLAMA_EMBEDDING_MODEL ?? 'snowflake-arctic-embed2',
      embeddingTimeoutMs: config?.embeddingTimeoutMs ?? 3000,
      embeddingBatchSize: config?.embeddingBatchSize ?? 32,
      maxSignalsPerCycle: config?.maxSignalsPerCycle ?? 200,
      clusterSimilarityThreshold: config?.clusterSimilarityThreshold ?? 0.80,
      maxClustersPerBatch: config?.maxClustersPerBatch ?? 8,
      summarizerEnabled: config?.summarizerEnabled ?? true,
      summarizerModel: config?.summarizerModel ?? process.env.OLLAMA_SUMMARIZER_MODEL ?? 'gpt-5-mini',
      summarizerMaxTokens: config?.summarizerMaxTokens ?? 160,
      summarizerTemperature: config?.summarizerTemperature ?? 0.12,
      summarizerTimeoutMs: config?.summarizerTimeoutMs ?? 8000,
      recencyWindowMs: config?.recencyWindowMs ?? (24 * 60 * 60 * 1000),
      v2: config?.v2 ?? true, // Default to v2
      stream: config?.stream ?? DEFAULT_SUBCONSCIOUS_CONFIG_V2.stream,
      context: config?.context ?? DEFAULT_SUBCONSCIOUS_CONFIG_V2.context,
      signals: config?.signals ?? DEFAULT_SUBCONSCIOUS_CONFIG_V2.signals,
      mentalModel: config?.mentalModel ?? DEFAULT_SUBCONSCIOUS_CONFIG_V2.mentalModel,
      consolidation: config?.consolidation ?? DEFAULT_SUBCONSCIOUS_CONFIG_V2.consolidation,
    };

    this.priority = this.config.priority;
    this.v2Config = {
      enabled: this.config.enabled,
      v2: this.config.v2,
      stream: this.config.stream,
      context: this.config.context,
      signals: this.config.signals,
      mentalModel: this.config.mentalModel,
      consolidation: this.config.consolidation,
    };

    // Ensure data dir exists
    try {
      if (this.config.persistToFile && !fs.existsSync(this.config.dataDir)) {
        fs.mkdirSync(this.config.dataDir, { recursive: true });
      }
    } catch (err) {
      this.logger.warn('Subconscious: failed to ensure data dir', { error: String(err) });
    }

    this.filePath = path.join(this.config.dataDir, 'subconscious.json');

    // Initialize v2 components if enabled
    if (this.config.v2) {
      this.signalGenerator = createSignalGenerator(this.v2Config.signals, this.logger);
      this.logger.info('Subconscious: v2 components initialized');
    }

    // Initialize enhanced search (used by both v2 and legacy)
    this.enhancedSearch = new SubconsciousSearch(this.logger, {
      enabled: true,
      maxTokensToAnalyze: 100,
      searchCooldownMs: 5000,
      minRelevanceToInject: 0.75,
      maxContextToInject: 3,
      maxRetrievedCache: 20,
      enableMemorySearch: true,
      enableFileSearch: true,
      enableWebSearch: false,
    });

    if (this.config.enabled) {
      this.logger.info('Subconscious: enabled', {
        v2: this.config.v2,
        proactiveMode: this.config.proactiveMode,
        readAlongEnabled: this.config.readAlongEnabled,
        memoryQueryOnTurn: this.config.memoryQueryOnTurn,
      });
    } else {
      this.logger.info('Subconscious: disabled');
    }
  }

  setMemory(memory: IMemory): void {
    this.memory = memory;
    this.enhancedSearch.setMemory(memory);
    this.logger.info('Subconscious: memory wired');

    // Hydrate persisted state
    void (async () => {
      try {
        const existing = await this.memory!.kv_get<any>('subconscious:avgCounts');
        if (existing && typeof existing === 'object') this.avgCounts = existing;
        const learnings = await this.memory!.kv_get<any[]>('subconscious:learnings');
        if (Array.isArray(learnings)) this.recentLearnings = learnings.slice(-50);

        // Hydrate v2 mental models if available
        if (this.config.v2) {
          const mentalModels = await this.memory!.kv_get<Record<string, MentalModelSnapshot>>('subconscious:v2:mentalModels');
          if (mentalModels) {
            for (const [sessionId, snapshot] of Object.entries(mentalModels)) {
              const model = createMentalModel(sessionId, this.logger);
              model.fromJSON(snapshot);
              this.mentalModels.set(sessionId, model);
            }
            this.logger.info('Subconscious: v2 mental models hydrated', { count: this.mentalModels.size });
          }
        }
      } catch (err) {
        this.logger.debug('Subconscious: failed to hydrate kv state', { error: String(err) });
      }
    })();
  }

  setProvider(provider: IProvider): void {
    this.provider = provider;
    this.enhancedSearch.setProvider(provider);
    this.logger.info('Subconscious: provider wired', { provider: provider.id });
  }

  setContextManager(contextManager: any): void {
    this.contextManager = contextManager;
    this.logger.info('Subconscious: ContextManager wired');
  }

  onEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    this.logger.info('Subconscious: event bus wired');

    // Initialize v2 stream ingestor with event bus
    if (this.config.v2) {
      this.streamIngestor = createStreamIngestor(this.v2Config.stream, this.logger, bus);
    }

    // Listen for turn lifecycle events
    if (this.config.readAlongEnabled) {
      this.setupTurnListeners(bus);
    }

    // Listen for dialectic signals
    (bus as any).on?.('dialectic:signal', (e: any) => {
      try {
        const sig: DialecticSignal | undefined = e?.signal;
        if (!sig) return;
        this.handleSignal({ sessionId: e.sessionId, turnId: e.turnId, signal: sig, ts: Date.now() });
      } catch (err) {
        this.logger.warn('Subconscious: dialectic:signal handler error', { error: String(err) });
      }
    });

    if (this.config.enabled) this.start();
  }

  /**
   * Setup listeners for turn events to enable read-along mode
   */
  private setupTurnListeners(bus: IEventBus): void {
    // Turn start - begin tracking
    (bus as any).on?.('turn:start', (e: any) => {
      const { sessionId, message } = e;
      if (!sessionId) return;

      this.logger.debug('Subconscious: turn:start', { sessionId });

      // Legacy tracking
      this.activeTurns.set(sessionId, {
        messages: [message],
        tokens: [],
        patterns: new Set(),
        memoryQueried: false,
        startTime: Date.now(),
      });

      // v2: Initialize mental model and stream ingestor
      if (this.config.v2 && this.streamIngestor) {
        // Create or get mental model for this session
        let mentalModel = this.mentalModels.get(sessionId);
        if (!mentalModel) {
          mentalModel = createMentalModel(sessionId, this.logger);
          this.mentalModels.set(sessionId, mentalModel);

          // Emit session started event
          this.emitEvent('subconscious:session:started', {
            sessionId,
            timestamp: Date.now(),
          });
        }

        // Start context refresh timer for this session
        this.startContextRefresh(sessionId);
      }

      // Initialize enhanced search context
      this.enhancedSearch.initTurn(sessionId, `${sessionId}_${Date.now()}`, message.content);

      // Query memory for context if enabled
      if (this.config.memoryQueryOnTurn && this.memory) {
        void this.queryMemoryForContext(sessionId, message.content);
      }

      // v2: Initial context enrichment
      if (this.config.v2 && this.contextManager) {
        void this.enrichContext(sessionId);
      }
    });

    // Token streaming - read along
    (bus as any).on?.('turn:token', (e: any) => {
      const { sessionId, token } = e;
      if (!sessionId || !token) return;

      const turn = this.activeTurns.get(sessionId);
      if (!turn) return;

      turn.tokens.push(token);

      // Legacy: Pattern detection on streaming tokens
      this.detectPatternsInStream(sessionId, turn);

      // Legacy: Enhanced search token analysis
      void this.enhancedSearch.streamToken(sessionId, token);

      // v2: Stream ingestor
      if (this.config.v2 && this.streamIngestor) {
        this.streamIngestor.onToken(sessionId, token, { timestamp: Date.now() });

        // v2: Update mental model incrementally
        const mentalModel = this.mentalModels.get(sessionId);
        if (mentalModel) {
          mentalModel.updateFromTokens([token]);
        }
      }
    });

    // Thinking streaming
    (bus as any).on?.('turn:thinking', (e: any) => {
      const { sessionId, token } = e;
      if (!sessionId || !token) return;

      // v2: Stream thinking to ingestor and mental model
      if (this.config.v2) {
        this.streamIngestor?.onThinking(sessionId, token);
        this.mentalModels.get(sessionId)?.updateFromThinking(token);
      }
    });

    // Turn end - consolidate
    (bus as any).on?.('turn:end', (e: any) => {
      const { sessionId, response, tokensUsed } = e;
      if (!sessionId) return;

      const turn = this.activeTurns.get(sessionId);

      this.logger.debug('Subconscious: turn:end', { sessionId, tokensUsed });

      // v2: Final mental model update and signal generation
      if (this.config.v2) {
        this.processTurnEndV2(sessionId, response);
      }

      if (turn) {
        // Legacy: Consolidate observation
        const observation: TurnObservation = {
          sessionId,
          turnId: `${sessionId}_${turn.startTime}`,
          userMessage: turn.messages[0]?.content as string || '',
          assistantResponse: response || '',
          tokens: turn.tokens,
          startTime: turn.startTime,
          endTime: Date.now(),
          patternsDetected: Array.from(turn.patterns),
          actionsTaken: [],
        };

        // Legacy: Take proactive actions
        if (this.config.proactiveMode) {
          void this.takeProactiveActions(sessionId, observation, turn);
        }

        this.turnObservations.set(observation.turnId, observation);

        // Legacy: Get retrieved context
        const retrievedContext = this.enhancedSearch.getContextToInject(sessionId);
        if (retrievedContext.length > 0) {
          this.emitAction('surface_retrieved_context', {
            sessionId,
            items: retrievedContext.map(item => ({
              source: item.source,
              content: item.content.slice(0, 500),
              relevance: item.relevance,
              query: item.query,
            })),
            summary: this.enhancedSearch.getSearchSummary(sessionId),
          });
        }

        this.activeTurns.delete(sessionId);

        // Legacy: Emit insight event
        this.emitEvent('subconscious:insight', {
          insight: {
            type: 'turn_observation',
            sessionId,
            patterns: observation.patternsDetected,
            duration: observation.endTime ? observation.endTime - observation.startTime : 0,
            retrievedItems: retrievedContext.length,
          },
        });
      }
    });

    // Tool calls - track for pattern analysis
    (bus as any).on?.('turn:tool_call', (e: any) => {
      const { sessionId, tool, input } = e;
      if (!sessionId) return;

      // Legacy tracking
      const turn = this.activeTurns.get(sessionId);
      if (turn) {
        turn.patterns.add(`tool:${tool}`);
      }

      // v2: Stream ingestor and mental model
      if (this.config.v2) {
        this.streamIngestor?.onToolCall(sessionId, tool, input);
        this.mentalModels.get(sessionId)?.updateFromToolCall(tool, input);
      }
    });

    // Tool results
    (bus as any).on?.('turn:tool_result', (e: any) => {
      const { sessionId, tool, result, callId } = e;
      if (!sessionId) return;

      // v2: Stream ingestor and mental model
      if (this.config.v2) {
        this.streamIngestor?.onToolResult(sessionId, tool, result, callId);
        this.mentalModels.get(sessionId)?.updateFromToolResult(tool, result);
      }
    });
  }

  /**
   * v2: Process turn end - generate signals from mental model changes
   */
  private async processTurnEndV2(sessionId: string, response: string): Promise<void> {
    const mentalModel = this.mentalModels.get(sessionId);
    if (!mentalModel || !this.signalGenerator) return;

    // Get previous snapshot
    const previousSnapshot = mentalModel.toJSON();

    // Final update from response
    mentalModel.updateFromTokens(response.split(' '));

    // Get current snapshot
    const currentSnapshot = mentalModel.toJSON();

    // Calculate delta
    const delta = calculateModelDelta(previousSnapshot, currentSnapshot);

    // Generate signals
    const signals = this.signalGenerator.generateSignals(delta);

    // Emit signals
    for (const signal of signals) {
      this.emitEvent('subconscious:signal', { sessionId, signal });

      // Emit specific signal types
      switch (signal.type) {
        case 'pattern:detected':
          this.emitEvent('subconscious:pattern', { sessionId, pattern: signal });
          break;
        case 'intent:shift':
          this.emitEvent('subconscious:intent', { sessionId, intent: signal });
          break;
        case 'anomaly:detected':
          this.emitEvent('subconscious:anomaly', { sessionId, anomaly: signal });
          break;
        case 'opportunity:present':
          this.emitEvent('subconscious:opportunity', { sessionId, opportunity: signal });
          break;
      }
    }

    // Emit state updated event
    this.emitEvent('subconscious:state:updated', {
      sessionId,
      state: currentSnapshot.state,
      delta,
    });
  }

  /**
   * v2: Enrich context from ContextManager
   */
  private async enrichContext(sessionId: string): Promise<void> {
    if (!this.contextManager || !this.mentalModels.has(sessionId)) return;

    try {
      const context = await this.contextManager.getEffectiveContext(sessionId, {
        query: this.mentalModels.get(sessionId)?.state.topic,
        includeHistory: this.v2Config.context.includeHistory,
        charBudget: this.v2Config.context.charBudget,
      });

      const mentalModel = this.mentalModels.get(sessionId);
      if (mentalModel) {
        const enrichedContext: EnrichedContext = {
          loadedFiles: context.assembled.files?.map((f: any) => ({
            path: f.path,
            content: f.content,
            loadedAt: Date.now(),
            lastAccessed: Date.now(),
          })) || [],
          relevantMemories: context.assembled.recentMemories?.map((m: string, i: number) => ({
            id: `mem_${i}`,
            content: m,
            type: 'memory',
            score: 0.8,
            accessedAt: Date.now(),
          })) || [],
          recentHistory: context.assembled.sessionHistory || [],
          availableTools: context.assembled.availableTools || [],
          sessionSummary: context.assembled.sessionSummary,
        };

        mentalModel.updateFromContext(enrichedContext);

        this.emitEvent('subconscious:context:enriched', {
          sessionId,
          context: enrichedContext,
        });
      }
    } catch (err) {
      this.logger.debug('Subconscious: context enrichment failed', { sessionId: sessionId.slice(-8), error: String(err) });
    }
  }

  /**
   * v2: Start periodic context refresh for a session
   */
  private startContextRefresh(sessionId: string): void {
    if (!this.config.v2 || !this.contextManager) return;

    // Clear existing timer if any
    this.stopContextRefresh(sessionId);

    const timer = setInterval(() => {
      void this.enrichContext(sessionId);
    }, this.v2Config.context.refreshIntervalMs);

    this.contextRefreshTimers.set(sessionId, timer);
  }

  /**
   * v2: Stop context refresh for a session
   */
  private stopContextRefresh(sessionId: string): void {
    const timer = this.contextRefreshTimers.get(sessionId);
    if (timer) {
      clearInterval(timer);
      this.contextRefreshTimers.delete(sessionId);
    }
  }

  /**
   * Emit event helper
   */
  private emitEvent(type: string, payload: any): void {
    try {
      (this.eventBus as any)?.emit?.({ type, ...payload });
    } catch (err) {
      this.logger.debug('Subconscious: failed to emit event', { type, error: String(err) });
    }
  }

  /**
   * Legacy: Query memory for relevant context
   */
  private async queryMemoryForContext(sessionId: string, query: string): Promise<void> {
    if (!this.memory) return;

    try {
      const results = await this.memory.search(query, { limit: 5 });

      const turn = this.activeTurns.get(sessionId);
      if (turn) {
        turn.memoryQueried = true;
      }

      if (results.length > 0) {
        this.logger.debug('Subconscious: memory context found', {
          sessionId,
          results: results.length,
          topScore: results[0]?.score,
        });

        const highConfidenceMemories = results.filter(r => r.score > 0.85);
        if (highConfidenceMemories.length > 0 && this.shouldTakeAction('surface_memory')) {
          this.emitAction('surface_memory', {
            sessionId,
            memories: highConfidenceMemories.map(r => ({
              content: r.entry.content,
              type: r.entry.type,
            })),
            trigger: query.slice(0, 100),
          });
        }
      }
    } catch (err) {
      this.logger.debug('Subconscious: memory query failed', { error: String(err) });
    }
  }

  /**
   * Legacy: Detect patterns in streaming tokens
   */
  private detectPatternsInStream(sessionId: string, turn: { tokens: string[]; patterns: Set<string> }): void {
    const text = turn.tokens.join('').toLowerCase();

    const patterns = [
      { id: 'code_block', keywords: ['```'] },
      { id: 'error_discussion', keywords: ['error', 'exception', 'failed'] },
      { id: 'architecture', keywords: ['architecture', 'design pattern', 'refactor'] },
      { id: 'debugging', keywords: ['debug', 'investigate', 'trace'] },
      { id: 'testing', keywords: ['test', 'spec', 'assert'] },
    ];

    for (const pattern of patterns) {
      if (!turn.patterns.has(pattern.id) && pattern.keywords.some(kw => text.includes(kw))) {
        turn.patterns.add(pattern.id);
        this.logger.debug('Subconscious: detected pattern', { sessionId, pattern: pattern.id });
      }
    }
  }

  /**
   * Legacy: Take proactive actions
   */
  private async takeProactiveActions(
    sessionId: string,
    observation: TurnObservation,
    turn: { patterns: Set<string>; memoryQueried: boolean }
  ): Promise<void> {
    const actions: ProactiveAction[] = [];

    if (turn.patterns.has('debugging') && turn.patterns.has('error_discussion')) {
      if (this.shouldTakeAction('trigger_workflow')) {
        actions.push({
          type: 'trigger_workflow',
          confidence: 0.8,
          payload: { workflow: 'systematic_debugging', sessionId },
          timestamp: Date.now(),
        });
      }
    }

    if (turn.patterns.has('architecture') && observation.tokens.length > 500) {
      if (this.shouldTakeAction('flag_pattern')) {
        actions.push({
          type: 'flag_pattern',
          confidence: 0.85,
          payload: { pattern: 'architecture_discussion', importance: 'high', sessionId },
          timestamp: Date.now(),
        });
      }
    }

    for (const action of actions) {
      this.recentActions.push(action);
      this.emitAction(action.type, action.payload);
      observation.actionsTaken.push(action.type);
    }

    if (this.recentActions.length > 100) {
      this.recentActions = this.recentActions.slice(-50);
    }
  }

  private shouldTakeAction(actionType: string): boolean {
    const now = Date.now();
    const recent = this.recentActions.filter(
      a => a.type === actionType && now - a.timestamp < this.config.proactiveActionCooldownMs
    );
    return recent.length === 0;
  }

  private emitAction(type: string, payload: any): void {
    this.logger.info('Subconscious: proactive action', { type });
    this.emitEvent('subconscious:action', { action: { type, payload, timestamp: Date.now() } });
  }

  private handleSignal(entry: { sessionId?: string; turnId?: string; signal: DialecticSignal; ts: number }): void {
    try {
      this.signalBuffer.push(entry);
      this.logger.debug('Subconscious: captured signal', { type: entry.signal.type, confidence: entry.signal.confidence });
    } catch (err) {
      this.logger.warn('Subconscious: failed to capture signal', { error: String(err) });
    }
  }

  start(): void {
    if (!this.config.enabled) return;
    if (this.timer) return;

    this.timer = setInterval(() => {
      void this.consolidate();
    }, this.config.consolidationIntervalMs);
    try { (this.timer as any).unref?.(); } catch {}

    this.logger.info('Subconscious: started', {
      v2: this.config.v2,
      intervalMs: this.config.consolidationIntervalMs,
    });
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
    }

    // Stop all context refresh timers
    for (const [sessionId, timer] of this.contextRefreshTimers) {
      clearInterval(timer);
    }
    this.contextRefreshTimers.clear();

    this.logger.info('Subconscious: stopped');
  }

  async cleanup(): Promise<void> {
    this.stop();

    // Persist v2 mental models
    if (this.config.v2 && this.memory) {
      try {
        const mentalModels: Record<string, MentalModelSnapshot> = {};
        for (const [sessionId, model] of this.mentalModels) {
          mentalModels[sessionId] = model.toJSON();
        }
        await this.memory.kv_set('subconscious:v2:mentalModels', mentalModels);
        this.logger.info('Subconscious: v2 mental models persisted');
      } catch (err) {
        this.logger.warn('Subconscious: failed to persist mental models', { error: String(err) });
      }
    }
  }

  private async consolidate(): Promise<void> {
    if (this.signalBuffer.length > 0) {
      await this.consolidateSignals();
    }
    if (this.turnObservations.size > 10) {
      await this.consolidateObservations();
    }
    // Periodic persistence of mental models
    if (this.config.v2 && this.memory) {
      await this.persistMentalModels();
    }
  }

  async persistMentalModels(): Promise<void> {
    if (!this.config.v2 || !this.memory) return;
    try {
      const mentalModels: Record<string, MentalModelSnapshot> = {};
      for (const [sessionId, model] of this.mentalModels) {
        mentalModels[sessionId] = model.toJSON();
      }
      await this.memory.kv_set('subconscious:v2:mentalModels', mentalModels);
      this.logger.debug('Subconscious: v2 mental models persisted', { count: this.mentalModels.size });
    } catch (err) {
      this.logger.debug('Subconscious: failed to persist mental models', { error: String(err) });
    }
  }

  private async consolidateSignals(): Promise<void> {
    // ... (existing implementation preserved)
    if (this.signalBuffer.length === 0) return;

    const all = this.signalBuffer.splice(0, this.signalBuffer.length);
    this.logger.debug('Subconscious: consolidating signals', { batchSize: all.length });

    const byType = new Map<string, typeof all>();
    for (const entry of all) {
      const arr = byType.get(entry.signal.type) || [];
      arr.push(entry);
      byType.set(entry.signal.type, arr);
    }

    let learnings: any[] = [];
    if (this.memory && this.config.persistMemory) {
      try { learnings = await this.memory.kv_get('subconscious:learnings') || [] } catch {}
    }

    for (const [type, entries] of byType) {
      if (entries.length >= this.config.minSignals) {
        const avgConfidence = entries.reduce((s, e) => s + (e.signal.confidence || 0), 0) / entries.length;

        const learning = {
          id: `learning_${Date.now()}_${type}`,
          summary: `${type} signals: ${entries.length} occurrences`,
          clusterLabel: type,
          confidence: avgConfidence,
          occurrences: entries.length,
          firstSeen: entries[0]?.ts || Date.now(),
          lastSeen: entries[entries.length - 1]?.ts || Date.now(),
          examples: entries.slice(0, 5).map(e => e.signal.content.slice(0, 200)),
          timestamp: Date.now(),
        };

        learnings.push(learning);
        if (learnings.length > 1000) learnings = learnings.slice(-1000);

        try {
          if (this.memory && this.config.persistMemory) {
            await this.memory.kv_set('subconscious:learnings', learnings);
            // Also store as insight entry for memory system
            await this.memory.store({
              type: 'insight',
              content: `${type} signals: ${entries.length} occurrences`,
              metadata: {
                clusterLabel: type,
                confidence: avgConfidence,
                occurrences: entries.length,
                examples: learning.examples,
                source: 'subconscious:consolidation',
              },
            });
          }
          this.emitEvent('subconscious:learning', { learning });
        } catch (err) {
          this.logger.debug('Subconscious: failed to persist learning', { error: String(err) });
        }
      }
    }
  }

  private async consolidateObservations(): Promise<void> {
    const observations = Array.from(this.turnObservations.values());
    if (observations.length < 10) return;

    this.logger.debug('Subconscious: consolidating observations', { count: observations.length });

    // Store observations to memory before clearing
    if (this.memory && this.config.persistMemory) {
      for (const obs of observations) {
        try {
          await this.memory.store({
            type: 'insight',
            content: `Turn observation: ${obs.userMessage?.slice(0, 100) || 'unknown'}`,
            metadata: {
              sessionId: obs.sessionId,
              patterns: obs.patternsDetected,
              tokenCount: obs.tokens?.length || 0,
              duration: obs.endTime ? obs.endTime - obs.startTime : 0,
              source: 'subconscious:observation',
            },
          });
        } catch (err) {
          this.logger.debug('Subconscious: failed to store observation', { error: String(err) });
        }
      }
    }

    this.turnObservations.clear();
  }

  // ===========================================================================
  // Public API
  // ===========================================================================

  getRetrievedContext(sessionId: string) {
    return this.enhancedSearch.getContextToInject(sessionId);
  }

  getSearchSummary(sessionId: string) {
    return this.enhancedSearch.getSearchSummary(sessionId);
  }

  getEnhancedSearchStats() {
    return this.enhancedSearch.getStats();
  }

  getMentalModel(sessionId: string): MentalModelImpl | undefined {
    return this.mentalModels.get(sessionId);
  }

  getRecentSignals(sessionId: string, count = 10) {
    return this.signalGenerator?.getRecentSignals(sessionId, count) || [];
  }

  cleanupSession(sessionId: string): void {
    this.enhancedSearch.cleanupSession(sessionId);
    this.activeTurns.delete(sessionId);
    this.mentalModels.delete(sessionId);
    this.stopContextRefresh(sessionId);
    this.streamIngestor?.cleanupSession(sessionId);

    this.emitEvent('subconscious:session:ended', {
      sessionId,
      timestamp: Date.now(),
    });
  }

  /**
   * Incorporate dialectic signal into mental model
   * Called by UnifiedIntelligenceLoop for cross-module feedback
   */
  async incorporateDialecticSignal(signal: any): Promise<void> {
    if (!signal?.sessionId) return;

    const mentalModel = this.mentalModels.get(signal.sessionId);
    if (mentalModel) {
      // Call the prototype method that was added to MentalModelImpl
      const incorporateMethod = (mentalModel as any).incorporateDialecticSignal;
      if (incorporateMethod && typeof incorporateMethod === 'function') {
        await incorporateMethod.call(mentalModel, signal);
      }
      this.logger.debug(`[Subconscious] Incorporated dialectic signal for session ${signal.sessionId}`);
    }
  }
}

export const createSubconscious = (logger: ILogger, config?: Partial<SubconsciousConfig>): Subconscious =>
  new Subconscious(logger, config);
