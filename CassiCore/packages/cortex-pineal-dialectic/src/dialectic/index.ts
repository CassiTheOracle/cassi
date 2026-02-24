/**
 * DialecticSystem — Unified orchestration of Yang, Yin, and Synthesizer
 * 
 * Runs all three observers in parallel and coordinates their outputs.
 * Handles WebSocket streaming, persistence, and signal injection.
 */

import type { ILogger } from '../../../types/interfaces.js';
import type { IEventBus } from '../../../types/interfaces.js';
import type { 
  IDialecticSystem, 
  DialecticResult, 
  YangContext,
  DialecticStreamEvent,
  DialecticSignal 
} from '../../../types/dialectic.js';
import type { IProvider } from '../../../types/runtime.js';
import type { IMemory } from '../../../types/intelligence.js';
import { YangObserver, type YangConfig } from '../yang/index.js';
import { YinObserver, type YinConfig } from '../yin/index.js';
import { Synthesizer, type SynthesizerConfig } from '../synthesizer/index.js';
import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

export interface DialecticSystemConfig {
  enabled: boolean;
  yang?: Partial<YangConfig>;
  yin?: Partial<YinConfig>;
  synthesizer?: Partial<SynthesizerConfig>;
  dataDir?: string;
}

export class DialecticSystem implements IDialecticSystem {
  readonly name = 'dialectic';
  
  private logger: ILogger;
  private config: DialecticSystemConfig;
  private eventBus?: IEventBus;
  private memory?: IMemory;
  
  private yang: YangObserver;
  private yin: YinObserver;
  private synthesizer: Synthesizer;
  
  private db?: Database.Database;
  private streamCallbacks: Map<string, Set<(event: DialecticStreamEvent) => void>> = new Map();

  constructor(logger: ILogger, config?: Partial<DialecticSystemConfig>) {
    this.logger = logger.child?.('dialectic') ?? logger;
    this.config = {
      enabled: config?.enabled ?? true,
      yang: config?.yang ?? {},
      yin: config?.yin ?? {},
      synthesizer: config?.synthesizer ?? {},
      dataDir: config?.dataDir ?? path.join(process.env.HOME || require('os').homedir(), '.cassicore', 'data'),
    };
    
    // Initialize observers
    this.yang = new YangObserver(this.logger, this.config.yang);
    this.yin = new YinObserver(this.logger, this.config.yin);
    this.synthesizer = new Synthesizer(this.logger, this.config.synthesizer);
    
    if (this.config.enabled) {
      this.initPersistence();
      this.logger.info('DialecticSystem: enabled');
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
          synthesizer_output TEXT NOT NULL,
          signal_injected BOOLEAN NOT NULL,
          total_latency_ms INTEGER NOT NULL,
          total_cost_usd REAL NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_dialectic_session ON dialectic_turns(session_id);
        CREATE INDEX IF NOT EXISTS idx_dialectic_timestamp ON dialectic_turns(timestamp);
      `);
      
      this.logger.info('DialecticSystem: persistence initialized', { dbPath });
    } catch (error) {
      this.logger.error('DialecticSystem: failed to initialize persistence', { error: String(error) });
    }
  }

  setProvider(provider: IProvider): void {
    this.yang.setProvider(provider);
    this.yin.setProvider(provider);
    this.synthesizer.setProvider(provider);
    this.logger.info('DialecticSystem: provider wired to all observers');
  }

  setMemory(memory: IMemory): void {
    this.memory = memory;
    this.logger.info('DialecticSystem: memory wired');
  }

  onEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    this.logger.info('DialecticSystem: event bus wired');
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
    context: YangContext
  ): Promise<DialecticResult> {
    const startTime = Date.now();
    
    if (!this.config.enabled) {
      return {
        sessionId,
        turnId,
        timestamp: startTime,
        yang: { branches: [], meta: { expansionTemperature: 0.9, generationTimeMs: 0, inputTokens: 0, outputTokens: 0 } },
        yin: { critiques: [], meta: { compressionRatio: 1.0, processingTimeMs: 0, inputTokens: 0, outputTokens: 0 } },
        synthesizer: {
          synthesis: { hasSignal: false, branchesConsidered: 0, branchesSurfaced: 0 },
          meta: { dialecticQuality: 0.5, processingTimeMs: 0, inputTokens: 0, outputTokens: 0 },
        },
        signalInjected: false,
        totalLatencyMs: 0,
        totalCostUsd: 0,
      };
    }

    // Emit start event
    this.emitStreamEvent(sessionId, {
      timestamp: Date.now(),
      turnId,
      stage: 'start',
    });

    try {
      // Fetch relevant memories if memory is available
      let relevantMemories: string[] = [];
      if (this.memory) {
        try {
          const results = await this.memory.search(userMessage, { limit: 5 });
          relevantMemories = results.map(r => r.entry.content.slice(0, 200));
        } catch (error) {
          this.logger.warn('DialecticSystem: failed to fetch memories', { error: String(error) });
        }
      }

      // ORDER: Yang first (expansion), then Yin (refinement)
      // This allows maximum creativity before applying constraints
      
      // Run Yang first - generate expansive branches
      const yangOutput = await this.yang.observe(sessionId, userMessage, context);
      
      this.emitStreamEvent(sessionId, {
        timestamp: Date.now(),
        turnId,
        stage: 'yang',
        data: yangOutput,
      });

      // Run Yin (refinement) on Yang's output
      const yinOutput = await this.yin.observe(sessionId, userMessage, yangOutput);
      
      this.emitStreamEvent(sessionId, {
        timestamp: Date.now(),
        turnId,
        stage: 'yin',
        data: yinOutput,
      });

      // Run Synthesizer on the dialectic (Yang → Yin)
      const synthesizerOutput = await this.synthesizer.synthesize(
        sessionId,
        userMessage,
        yangOutput,
        yinOutput,
        relevantMemories
      );
      
      this.emitStreamEvent(sessionId, {
        timestamp: Date.now(),
        turnId,
        stage: 'synthesizer',
        data: synthesizerOutput,
      });

      // Calculate totals
      const totalLatencyMs = Date.now() - startTime;
      const totalCostUsd = this.calculateCost(yangOutput, yinOutput, synthesizerOutput);
      
      // Determine if signal should be injected
      const signalInjected = synthesizerOutput.synthesis.hasSignal && 
        synthesizerOutput.synthesis.signal?.urgency === 'immediate' &&
        (synthesizerOutput.synthesis.signal?.confidence || 0) >= 0.7;

      const result: DialecticResult = {
        sessionId,
        turnId,
        timestamp: startTime,
        yang: yangOutput,
        yin: yinOutput,
        synthesizer: synthesizerOutput,
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
      if (signalInjected && synthesizerOutput.synthesis.signal) {
        this.emitSignal(sessionId, turnId, synthesizerOutput.synthesis.signal);
      }

      this.logger.info('DialecticSystem: turn processed (Yang → Yin → Synthesizer)', {
        sessionId,
        turnId,
        critiquesCount: yinOutput.critiques.length,
        branchesGenerated: yangOutput.branches.length,
        signalGenerated: synthesizerOutput.synthesis.hasSignal,
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

  private calculateCost(
    yang: DialecticResult['yang'],
    yin: DialecticResult['yin'],
    synthesizer: DialecticResult['synthesizer']
  ): number {
    // GPT-5 Mini pricing (approximate)
    const inputCostPer1M = 0.15;  // $0.15 per 1M input tokens
    const outputCostPer1M = 0.60; // $0.60 per 1M output tokens
    
    const totalInput = yang.meta.inputTokens + yin.meta.inputTokens + synthesizer.meta.inputTokens;
    const totalOutput = yang.meta.outputTokens + yin.meta.outputTokens + synthesizer.meta.outputTokens;
    
    return (totalInput / 1_000_000 * inputCostPer1M) + (totalOutput / 1_000_000 * outputCostPer1M);
  }

  private async persistResult(result: DialecticResult): Promise<void> {
    if (!this.db) return;
    
    try {
      this.db.prepare(`
        INSERT INTO dialectic_turns (
          session_id, turn_id, timestamp,
          yang_output, yin_output, synthesizer_output,
          signal_injected, total_latency_ms, total_cost_usd
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      `).run(
        result.sessionId,
        result.turnId,
        result.timestamp,
        JSON.stringify(result.yang),
        JSON.stringify(result.yin),
        JSON.stringify(result.synthesizer),
        result.signalInjected ? 1 : 0,
        result.totalLatencyMs,
        result.totalCostUsd
      );
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
      signalContent: signal.content.slice(0, 100),
    });
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
        synthesizer: JSON.parse(r.synthesizer_output),
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
      const row = this.db.prepare(`
        SELECT 
          COUNT(*) as total_turns,
          SUM(CASE WHEN json_extract(synthesizer_output, '$.synthesis.hasSignal') = 1 THEN 1 ELSE 0 END) as signals_generated,
          SUM(CASE WHEN signal_injected = 1 THEN 1 ELSE 0 END) as signals_injected,
          AVG(total_latency_ms) as avg_latency_ms,
          SUM(total_cost_usd) as total_cost_usd
        FROM dialectic_turns
        WHERE session_id = ?
      `).get(sessionId) as any;
      
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
}

export const createDialecticSystem = (logger: ILogger, config?: Partial<DialecticSystemConfig>): DialecticSystem =>
  new DialecticSystem(logger, config);
