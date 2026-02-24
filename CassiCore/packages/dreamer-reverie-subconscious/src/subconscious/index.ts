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
import type { IProvider } from '../../../types/runtime.js';
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
  llmModel?: string;                // fallback model name when calling provider
  maxGroupsPerBatch?: number;       // limit LLM calls
}

export class Subconscious {
  readonly name = 'subconscious' as const;
  readonly priority: number;

  private logger: ILogger;
  private config: Required<SubconsciousConfig>;
  private memory?: IMemory;
  private eventBus?: IEventBus;
  private provider?: IProvider;
  private buffer: Array<{ sessionId?: string; turnId?: string; signal: DialecticSignal; ts: number }> = [];
  private timer?: NodeJS.Timeout;
  private filePath: string;

  // Runtime stats for anomaly detection
  private avgCounts: Record<string, number> = {};
  private recentSubconsciousLearnings: Array<{ summary: string; timestamp: number; confidence?: number }> = [];

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
      llmModel: config?.llmModel ?? 'gpt-5-mini',
      maxGroupsPerBatch: config?.maxGroupsPerBatch ?? 6,
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

    // hydrate persisted averages and learnings in background (best-effort)
    void (async () => {
      try {
        const existing = await this.memory!.kv_get<any>('subconscious:avgCounts');
        if (existing && typeof existing === 'object') this.avgCounts = existing;
        const learnings = await this.memory!.kv_get<any[]>('subconscious:learnings');
        if (Array.isArray(learnings)) this.recentSubconsciousLearnings = learnings.slice(-50);
      } catch (err) {
        this.logger.debug('Subconscious: failed to hydrate kv state', { error: String(err) });
      }
    })();
  }

  setProvider(provider: IProvider): void {
    this.provider = provider;
    this.logger.info('Subconscious: provider wired', { provider: provider.id });
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

    // Sort groups by size and limit how many we analyze via LLM
    const sortedGroups = Array.from(groups.entries()).sort((a, b) => b[1].length - a[1].length);
    const topGroups = sortedGroups.slice(0, this.config.maxGroupsPerBatch);

    for (const [key, items] of topGroups) {
      const count = items.length;
      const avgConfidence = items.reduce((s, it) => s + (it.signal.confidence || 0), 0) / Math.max(1, count);
      const samples = items.slice(0, 6).map(i => i.signal.content).filter(Boolean);
      const type = items[0].signal.type;

      const meta = {
        key,
        type,
        count,
        avgConfidence,
        samples,
        firstSeen: items[0].ts,
        lastSeen: items[items.length - 1].ts,
      };

      // Use LLM to summarize & classify this cluster (best-effort)
      let llmResult: any = null;
      try {
        if (this.provider) {
          const model = (this.provider.models && this.provider.models.length > 0) ? this.provider.models[0] : this.config.llmModel;
          const prompt = this.buildClusterPrompt(meta);
          const messages = [{ role: 'user' as const, content: prompt }];
          const opts = { model, stream: true as const, maxTokens: 300, temperature: 0.2 };

          let collected = '';
          const stream = this.provider.complete(messages as any, opts as any) as AsyncIterable<any>;
          for await (const chunk of stream) {
            if (chunk.type === 'token' && chunk.text) collected += chunk.text;
            if (chunk.type === 'done') break;
            if (chunk.type === 'error') throw new Error(chunk.error || 'provider error');
          }

          // Attempt to extract JSON
          const jsonMatch = collected.match(/\{[\s\S]*\}/);
          if (jsonMatch) {
            try {
              llmResult = JSON.parse(jsonMatch[0]);
            } catch (err) {
              this.logger.debug('Subconscious: failed to parse LLM JSON, falling back to heuristics', { error: String(err) });
            }
          }

          // If no parse, try a soft parse: look for lines like 'label:' 'summary:'
          if (!llmResult) {
            llmResult = this.fallbackParseFreeform(collected);
          }
        }
      } catch (err) {
        this.logger.warn('Subconscious: LLM summarization failed', { error: String(err) });
        llmResult = null;
      }

      // Decide whether to persist based on LLM advice or heuristics
      const shouldPersist = (llmResult && typeof llmResult.persist === 'boolean')
        ? llmResult.persist
        : (count >= this.config.minSignals) || (meta.avgConfidence >= this.config.persistConfidenceThreshold);

      const summaryText = (llmResult && llmResult.summary) ? llmResult.summary : `Detected ${count} ${type} signal(s). Samples: ${meta.samples.slice(0,3).join(' | ')}`;
      const clusterLabel = (llmResult && llmResult.clusterLabel) ? llmResult.clusterLabel : `${type}`;
      const confidence = (llmResult && typeof llmResult.confidence === 'number') ? Math.max(0, Math.min(1, llmResult.confidence)) : Math.min(1, Math.max(0, meta.avgConfidence));
      const anomalyScore = (llmResult && typeof llmResult.anomalyScore === 'number') ? llmResult.anomalyScore : 0;
      const anomalyReason = (llmResult && llmResult.anomalyReason) ? llmResult.anomalyReason : '';

      const learning: any = {
        summary: summaryText,
        clusterLabel,
        confidence,
        anomalyScore,
        anomalyReason,
        meta,
        persisted: false,
        persistedId: null,
        timestamp: Date.now(),
      };

      if (shouldPersist) {
        try {
          if (this.memory && this.config.persistMemory) {
            const id = await this.memory.store({ type: 'insight', content: summaryText, metadata: { clusterLabel, meta, anomalyScore, anomalyReason } });
            learning.persisted = true;
            learning.persistedId = id;
            this.logger.info('Subconscious: persisted learning to memory', { id, clusterLabel, count });
          } else if (this.config.persistToFile) {
            let existing: any[] = [];
            try {
              if (fs.existsSync(this.filePath)) {
                existing = JSON.parse(fs.readFileSync(this.filePath, 'utf8') || '[]') as any[];
              }
            } catch {}
            const id = `sublearn_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
            const entry = { id, summary: summaryText, clusterLabel, meta, anomalyScore, anomalyReason, timestamp: Date.now() };
            existing.push(entry);
            try { fs.writeFileSync(this.filePath, JSON.stringify(existing, null, 2), 'utf8'); } catch (err) { this.logger.warn('Subconscious: failed to write file', { error: String(err) }); }
            learning.persisted = true;
            learning.persistedId = id;
            this.logger.info('Subconscious: persisted learning to file', { id, file: this.filePath });
          }

          // Update stored learnings list
          try {
            this.recentSubconsciousLearnings.push({ summary: learning.summary, timestamp: learning.timestamp, confidence: learning.confidence });
            if (this.recentSubconsciousLearnings.length > 100) this.recentSubconsciousLearnings.shift();
            if (this.memory) await this.memory.kv_set('subconscious:learnings', this.recentSubconsciousLearnings.slice(-50));
          } catch (err) {
            this.logger.debug('Subconscious: failed to update kv list', { error: String(err) });
          }
        } catch (err) {
          this.logger.warn('Subconscious: failed to persist learning', { error: String(err) });
        }
      }

      // Anomaly detection heuristics
      let isAnomaly = false;
      const anomalyThreshold = 0.7;
      if ((learning.anomalyScore || 0) >= anomalyThreshold) isAnomaly = true;
      if (/error|exception|crash|data loss|security|vulnerability|corrupt/i.test(summaryText)) isAnomaly = true;

      // Sliding average baseline update
      try {
        const prev = this.avgCounts[key] || 0;
        const updated = (prev * 0.9) + (count * 0.1);
        this.avgCounts[key] = updated;
        if (this.memory) await this.memory.kv_set('subconscious:avgCounts', this.avgCounts);

        // detect spikes relative to baseline
        if (prev > 0 && count > Math.max(3, prev * 3)) {
          isAnomaly = true;
          learning.anomalyReason = learning.anomalyReason || `Spike: count=${count} prevAvg=${prev.toFixed(2)}`;
        }
      } catch (err) {
        this.logger.debug('Subconscious: failed to update avgCounts', { error: String(err) });
      }

      // Record learning metrics to event bus and ai-scientist
      try {
        (this.eventBus as any)?.emit?.({ type: 'subconscious:learning', learning, sessionId: null });
      } catch (err) {}

      if (isAnomaly) {
        try {
          const anomaly = { summary: learning.summary, clusterLabel: learning.clusterLabel, reason: learning.anomalyReason || '', evidence: learning.meta.samples, confidence: learning.confidence, timestamp: Date.now() };
          (this.eventBus as any)?.emit?.({ type: 'subconscious:anomaly', anomaly, sessionId: null });
          // also persist anomaly history
          try {
            if (this.memory) {
              const existing = await this.memory.kv_get<any[]>('subconscious:anomalies') || [];
              existing.push(anomaly);
              await this.memory.kv_set('subconscious:anomalies', existing.slice(-100));
            }
          } catch {}
        } catch (err) {
          this.logger.warn('Subconscious: failed to emit anomaly', { error: String(err) });
        }
      }

      learnings.push(learning);
    }

    if (learnings.length > 0) {
      this.logger.info('Subconscious: consolidation complete', { learnings: learnings.length });
    }
  }

  private buildClusterPrompt(meta: { key: string; type: string; count: number; avgConfidence: number; samples: string[]; firstSeen: number; lastSeen: number }): string {
    const samplesText = meta.samples.slice(0, 6).map((s, i) => `(${i+1}) ${s}`).join('\n');
    return `You are a background analyst for an AI system. Given the following cluster of signals, produce a JSON object with the fields:\n- clusterLabel: short label (1-5 words)\n- summary: 1-2 sentence summary of the core insight or issue\n- persist: true|false // whether this should be saved as a persistent learning\n- confidence: 0.0-1.0 // how useful/important this is\n- anomalyScore: 0.0-1.0 // how anomalous or urgent this cluster appears\n- anomalyReason: optional string explaining anomaly detection\n\nCluster metadata:\n- type: ${meta.type}\n- count: ${meta.count}\n- avgConfidence: ${meta.avgConfidence.toFixed(2)}\n\nSamples:\n${samplesText}\n\nRespond only with a JSON object.`;
  }

  private fallbackParseFreeform(text: string): any {
    // Simple heuristics to extract label/summary lines
    const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
    const res: any = {};
    for (const l of lines.slice(0, 8)) {
      const m = l.match(/clusterLabel[:\-]\s*(.+)/i) || l.match(/label[:\-]\s*(.+)/i);
      if (m) res.clusterLabel = m[1].trim();
      const s = l.match(/summary[:\-]\s*(.+)/i);
      if (s) res.summary = s[1].trim();
      const p = l.match(/persist[:\-]\s*(true|false)/i);
      if (p) res.persist = p[1].toLowerCase() === 'true';
      const c = l.match(/confidence[:\-]\s*([0-9.]+)/i);
      if (c) res.confidence = parseFloat(c[1]);
      const a = l.match(/anomalyScore[:\-]\s*([0-9.]+)/i);
      if (a) res.anomalyScore = parseFloat(a[1]);
      const ar = l.match(/anomalyReason[:\-]\s*(.+)/i);
      if (ar) res.anomalyReason = ar[1].trim();
    }
    return res;
  }
}

export const createSubconscious = (logger: ILogger, config?: Partial<SubconsciousConfig>): Subconscious =>
  new Subconscious(logger, config);
