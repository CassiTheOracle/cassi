/**
 * Subconscious — Background consolidation of dialectic signals
 *
 * Listens for `dialectic:signal` events, aggregates them over time, and
 * persists low-signal / repeated patterns as background "learnings".
 *
 * The Subconscious intentionally operates at low priority and runs
 * periodically to avoid impacting turn latency.
 */

import type { ILogger, IEventBus } from '../../../types/interfaces.js';
import type { IMemory } from '../../../types/intelligence.js';
import type { DialecticSignal } from '../../../types/dialectic.js';
import fs from 'fs';
import path from 'path';

export interface SubconsciousConfig {
  enabled?: boolean;
  consolidationIntervalMs?: number; // how often to consolidate buffer
  minSignals?: number;              // minimum occurrences to persist
  persistMemory?: boolean;          // whether to write learnings to IMemory
  persistToFile?: boolean;          // fallback: write learnings to disk
  dataDir?: string;                 // where to write fallback file
  persistConfidenceThreshold?: number; // persist if avg confidence >= this
  priority?: number;
}

export class Subconscious {
  readonly name = 'subconscious' as const;
  readonly priority: number;

  private logger: ILogger;
  private config: Required<SubconsciousConfig>;
  private memory?: IMemory;
  private eventBus?: IEventBus;
  private buffer: Array<{ sessionId?: string; turnId?: string; signal: DialecticSignal; ts: number }> = [];
  private timer?: NodeJS.Timeout;
  private filePath: string;

  constructor(logger: ILogger, config?: Partial<SubconsciousConfig>) {
    this.logger = logger.child?.('subconscious') ?? logger;
    this.config = {
      enabled: config?.enabled ?? true,
      consolidationIntervalMs: config?.consolidationIntervalMs ?? 60_000,
      minSignals: config?.minSignals ?? 3,
      persistMemory: config?.persistMemory ?? true,
      persistToFile: config?.persistToFile ?? true,
      dataDir: config?.dataDir ?? path.join(process.env.HOME || require('os').homedir(), '.cassicore', 'data'),
      persistConfidenceThreshold: config?.persistConfidenceThreshold ?? 0.85,
      priority: config?.priority ?? 40,
    };

    this.priority = this.config.priority;

    // Ensure data dir exists for file persistence
    try {
      if (this.config.persistToFile && !fs.existsSync(this.config.dataDir)) {
        fs.mkdirSync(this.config.dataDir, { recursive: true });
      }
    } catch (err) {
      this.logger.warn('Subconscious: failed to ensure data dir', { error: String(err) });
    }

    this.filePath = path.join(this.config.dataDir, 'subconscious.json');

    if (this.config.enabled) this.logger.info('Subconscious: enabled', { consolidationIntervalMs: this.config.consolidationIntervalMs });
    else this.logger.info('Subconscious: disabled');
  }

  setMemory(memory: IMemory): void {
    this.memory = memory;
    this.logger.info('Subconscious: memory wired');
  }

  onEventBus(bus: IEventBus): void {
    this.eventBus = bus;
    this.logger.info('Subconscious: event bus wired');

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

    // Optionally start background consolidation immediately when wired
    if (this.config.enabled) this.start();
  }

  start(): void {
    if (!this.config.enabled) return;
    if (this.timer) return;

    this.timer = setInterval(() => {
      void this.consolidate();
    }, this.config.consolidationIntervalMs);

    this.logger.info('Subconscious: started', { intervalMs: this.config.consolidationIntervalMs });
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = undefined;
      this.logger.info('Subconscious: stopped');
    }
  }

  async cleanup(): Promise<void> {
    this.stop();
  }

  private handleSignal(entry: { sessionId?: string; turnId?: string; signal: DialecticSignal; ts: number }): void {
    // Capture to buffer for later consolidation
    try {
      this.buffer.push(entry);
      this.logger.debug('Subconscious: captured signal', { type: entry.signal.type, confidence: entry.signal.confidence });
    } catch (err) {
      this.logger.warn('Subconscious: failed to capture signal', { error: String(err) });
    }
  }

  private async consolidate(): Promise<void> {
    if (this.buffer.length === 0) return;

    const batch = this.buffer.splice(0, this.buffer.length);
    this.logger.debug('Subconscious: consolidating batch', { batchSize: batch.length });

    // Group by rough key: type + normalized prefix of content
    const groups = new Map<string, Array<typeof batch[0]>>();

    for (const item of batch) {
      try {
        const normalized = ((item.signal.content || '') as string).replace(/\s+/g, ' ').trim().toLowerCase().slice(0, 120);
        const key = `${item.signal.type}::${normalized.slice(0, Math.min(80, normalized.length))}` || `${item.signal.type}::`; 
        const arr = groups.get(key) ?? [];
        arr.push(item);
        groups.set(key, arr);
      } catch (err) {
        // skip problematic item
      }
    }

    const learnings: Array<any> = [];

    for (const [key, items] of groups.entries()) {
      const count = items.length;
      const avgConfidence = items.reduce((s, it) => s + (it.signal.confidence || 0), 0) / Math.max(1, count);
      const samples = items.slice(0, 3).map(i => i.signal.content).filter(Boolean);
      const type = items[0].signal.type;

      const shouldPersist = (count >= this.config.minSignals) || (avgConfidence >= this.config.persistConfidenceThreshold);

      const summary = `Detected ${count} ${type} signal(s) — avg confidence=${avgConfidence.toFixed(2)}. Samples: ${samples.join(' | ')}`;

      const meta = {
        key,
        type,
        count,
        avgConfidence,
        samples,
        firstSeen: items[0].ts,
        lastSeen: items[items.length - 1].ts,
      };

      const learning: any = { summary, meta, persisted: false, persistedId: null, timestamp: Date.now() };

      if (shouldPersist) {
        // Persist either to memory or to file
        try {
          if (this.memory && this.config.persistMemory) {
            const id = await this.memory.store({ type: 'insight', content: summary, metadata: meta });
            learning.persisted = true;
            learning.persistedId = id;
            this.logger.info('Subconscious: persisted learning to memory', { id, type, count });
          } else if (this.config.persistToFile) {
            // persist to local JSON file
            try {
              let existing: any[] = [];
              if (fs.existsSync(this.filePath)) {
                try { existing = JSON.parse(fs.readFileSync(this.filePath, 'utf8') || '[]') as any[] } catch { existing = [] }
              }
              const id = `sublearn_${Date.now()}_${Math.floor(Math.random()*1000)}`;
              const entry = { id, summary, meta, timestamp: Date.now() };
              existing.push(entry);
              fs.writeFileSync(this.filePath, JSON.stringify(existing, null, 2), 'utf8');
              learning.persisted = true;
              learning.persistedId = id;
              this.logger.info('Subconscious: persisted learning to file', { id, file: this.filePath });
            } catch (err) {
              this.logger.warn('Subconscious: failed to write learning to file', { error: String(err) });
            }
          }
        } catch (err) {
          this.logger.warn('Subconscious: failed to persist learning', { error: String(err) });
        }
      } else {
        this.logger.debug('Subconscious: aggregated learning (not persisted)', { type, count, avgConfidence });
      }

      learnings.push(learning);

      // Emit event for downstream consumers
      try {
        (this.eventBus as any)?.emit?.({ type: 'subconscious:learning', learning, sessionId: null });
      } catch (err) {
        // non-fatal
      }
    }

    if (learnings.length > 0) {
      this.logger.info('Subconscious: consolidation complete', { learnings: learnings.length });
    }
  }
}

export const createSubconscious = (logger: ILogger, config?: Partial<SubconsciousConfig>): Subconscious =>
  new Subconscious(logger, config);
