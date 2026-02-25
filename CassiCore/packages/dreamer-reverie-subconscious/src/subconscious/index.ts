/**
 * Subconscious — Background consolidation of dialectic signals (v2)
 *
 * Features:
 * - Semantic clustering using embeddings ( Ollama / configured embedding service )
 * - Optional LLM summarization for cluster labels and summaries (uses wired provider)
 * - Rich anomaly scoring combining count, confidence, recency, similarity and spike detection
 * - Persists learnings to IMemory (preferred) or a fallback JSON file
 * - Emits events: 'subconscious:learning' and 'subconscious:anomaly'
 *
 * Usage notes:
 * - Configure via runtime config path: intelligence.subconscious
 * - You may configure a dedicated provider ID via intelligence.subconscious.provider
 *   — daemon wires that provider (if present) into the Subconscious via setProvider().
 * - Embedding service defaults to Ollama (process.env.OLLAMA_URL and model snowflake-arctic-embed2)
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

  // Embedding / clustering
  embeddingService?: 'ollama' | 'none';
  embeddingModel?: string;          // default snowflake-arctic-embed2
  embeddingTimeoutMs?: number;
  embeddingBatchSize?: number;
  maxSignalsPerCycle?: number;      // cap how many signals to embed per consolidation
  clusterSimilarityThreshold?: number; // 0-1, similarity threshold to join a cluster
  maxClustersPerBatch?: number;

  // Summarization via LLM
  summarizerEnabled?: boolean;
  summarizerModel?: string;
  summarizerMaxTokens?: number;
  summarizerTemperature?: number;
  summarizerTimeoutMs?: number;

  // Anomaly parameters
  recencyWindowMs?: number;         // recency decay horizon
}

export class Subconscious {
  readonly name = 'subconscious' as const;
  readonly priority: number;

  private logger: ILogger;
  private config: Required<SubconsciousConfig>;
  private memory?: IMemory;
  private eventBus?: IEventBus;
  private provider?: IProvider; // optional: wired provider for summaries
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

      // Embedding defaults
      embeddingService: config?.embeddingService ?? 'ollama',
      embeddingModel: config?.embeddingModel ?? process.env.OLLAMA_EMBEDDING_MODEL ?? 'snowflake-arctic-embed2',
      embeddingTimeoutMs: config?.embeddingTimeoutMs ?? 3000,
      embeddingBatchSize: config?.embeddingBatchSize ?? 32,
      maxSignalsPerCycle: config?.maxSignalsPerCycle ?? 200,
      clusterSimilarityThreshold: config?.clusterSimilarityThreshold ?? 0.80,
      maxClustersPerBatch: config?.maxClustersPerBatch ?? 8,

      // Summarizer defaults
      summarizerEnabled: config?.summarizerEnabled ?? true,
      summarizerModel: config?.summarizerModel ?? process.env.OLLAMA_SUMMARIZER_MODEL ?? 'gpt-5-mini',
      summarizerMaxTokens: config?.summarizerMaxTokens ?? 160,
      summarizerTemperature: config?.summarizerTemperature ?? 0.12,
      summarizerTimeoutMs: config?.summarizerTimeoutMs ?? 8000,

      // anomaly
      recencyWindowMs: config?.recencyWindowMs ?? (24 * 60 * 60 * 1000),
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
    try { (this.timer as any).unref?.() } catch {}

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

    // Work on a recent slice to bound cost
    const all = this.buffer.splice(0, this.buffer.length);
    this.logger.debug('Subconscious: consolidating batch', { batchSize: all.length });

    // Sort by recency (most recent first) and trim to maxSignalsPerCycle
    const sorted = all.sort((a, b) => b.ts - a.ts).slice(0, this.config.maxSignalsPerCycle);

    // Build texts for embedding: use signal.content; include type as prefix for small disambiguation
    const texts = sorted.map(s => `${s.signal.type}: ${s.signal.content}`);

    // Fetch embeddings for the batch (best-effort)
    let embeddings: Array<number[] | null> = [];
    try {
      if (this.config.embeddingService === 'ollama') {
        embeddings = await this.fetchEmbeddingsBatch(texts, this.config.embeddingTimeoutMs, this.config.embeddingBatchSize);
      } else {
        embeddings = texts.map(() => null);
      }
    } catch (err) {
      this.logger.warn('Subconscious: failed to fetch embeddings', { error: String(err) });
      embeddings = texts.map(() => null);
    }

    // If no embeddings available, fall back to naive grouping by normalized prefix (cheap)
    let clusters: Array<{ indices: number[]; centroid?: number[] }> = [];
    if (embeddings.every(e => e === null)) {
      // cheap prefix grouping
      const groups = new Map<string, number[]>();
      for (let i = 0; i < texts.length; i++) {
        const key = texts[i].replace(/\s+/g, ' ').trim().toLowerCase().slice(0, 80);
        const arr = groups.get(key) ?? [];
        arr.push(i);
        groups.set(key, arr);
      }
      clusters = Array.from(groups.values()).map(indices => ({ indices }));
    } else {
      // Greedy clustering by centroid similarity
      const threshold = this.config.clusterSimilarityThreshold;

      for (let i = 0; i < embeddings.length; i++) {
        const emb = embeddings[i];
        if (!emb) continue; // skip missing

        let placed = false;
        for (const c of clusters) {
          if (!c.centroid) continue;
          const sim = this.cosineSimilarity(emb, c.centroid);
          if (sim >= threshold) {
            c.indices.push(i);
            // incremental centroid update: newCentroid = (centroid * n + emb) / (n+1)
            const n = c.indices.length;
            const newCentroid = c.centroid.map((v, k) => ((v * (n - 1)) + (emb[k] || 0)) / n);
            c.centroid = newCentroid;
            placed = true;
            break;
          }
        }
        if (!placed) {
          clusters.push({ indices: [i], centroid: emb.slice() });
        }
      }
    }

    // Limit the number of clusters we analyze further
    clusters = clusters.sort((a, b) => b.indices.length - a.indices.length).slice(0, this.config.maxClustersPerBatch);

    const learnings: Array<any> = [];

    const now = Date.now();

    for (const cluster of clusters) {
      const items = cluster.indices.map(idx => sorted[idx]).filter(Boolean);
      const count = items.length;
      const avgConfidence = items.reduce((s, it) => s + (it.signal.confidence || 0), 0) / Math.max(1, count);
      const samples = items.slice(0, 6).map(i => i.signal.content).filter(Boolean);
      const type = items[0].signal.type;
      const firstSeen = items[items.length - 1].ts; // oldest in cluster
      const lastSeen = items[0].ts; // most recent

      // baseline from avgCounts (per type or coarse key)
      const baselineKey = `${type}`;
      const prevAvg = this.avgCounts[baselineKey] || 0;

      // similarity metric: average cosine similarity of each member to centroid (if available)
      let simAvg = 1;
      if (cluster.centroid) {
        let ssum = 0;
        let sct = 0;
        for (const idx of cluster.indices) {
          const vec = embeddings[idx];
          if (!vec) continue;
          ssum += this.cosineSimilarity(vec, cluster.centroid);
          sct++;
        }
        simAvg = sct > 0 ? (ssum / sct) : 1;
      } else {
        // fallback: compute text similarity heuristics
        simAvg = 0.5;
      }

      // recency score (1 = very recent, 0 = stale beyond recencyWindow)
      const recencyWindow = this.config.recencyWindowMs;
      const recencyScore = Math.max(0, 1 - ((now - lastSeen) / recencyWindow));

      // spike factor relative to baseline
      let spikeFactor = 0;
      if (prevAvg <= 0) {
        spikeFactor = Math.min(1, count / Math.max(3, this.config.minSignals));
      } else {
        const ratio = count / prevAvg;
        spikeFactor = Math.min(1, Math.max(0, (ratio - 1) / 4)); // ratio 5 -> spikeFactor ~1
      }

      // countScore normalized
      const countScore = Math.min(1, count / Math.max(5, prevAvg || 5));

      // Compose anomaly score (weighted)
      const w_count = 0.25;
      const w_conf = 0.15;
      const w_recency = 0.2;
      const w_similarity = 0.25;
      const w_spike = 0.15;

      const anomalyScore = Math.max(0, Math.min(1,
        (w_count * countScore) + (w_conf * avgConfidence) + (w_recency * recencyScore) + (w_similarity * simAvg) + (w_spike * spikeFactor)
      ));

      const anomalyReasonParts: string[] = [];
      if (spikeFactor > 0.5) anomalyReasonParts.push(`spike: count=${count} prevAvg=${prevAvg.toFixed(2)}`);
      if (simAvg > 0.9 && count >= this.config.minSignals) anomalyReasonParts.push('repeated identical signals');
      if (avgConfidence >= this.config.persistConfidenceThreshold) anomalyReasonParts.push('high confidence signals');
      if (recencyScore > 0.8) anomalyReasonParts.push('recent activity');

      const anomalyReason = anomalyReasonParts.join('; ');

      // Decide whether to persist the learning (LLM advice optional)
      let persistAdvice: boolean | null = null;
      let clusterLabel = `${type}`;
      let summaryText = `Detected ${count} ${type} signal(s). Samples: ${samples.slice(0,3).join(' | ')}`;

      // Optionally call summarizer LLM for rich label/summary (best-effort)
      if (this.config.summarizerEnabled && this.provider) {
        try {
          const prompt = this.buildClusterSummarizerPrompt({ type, count, avgConfidence, samples, firstSeen, lastSeen, simAvg, anomalyScore });

          const messages = [{ role: 'user' as const, content: prompt }];
          const modelSpec = this.config.summarizerModel || '';
          const slashIdx = modelSpec.indexOf('/');
          const modelName = slashIdx >= 0 ? modelSpec.slice(slashIdx + 1) : modelSpec;
          const opts = {
            model: modelName || this.config.summarizerModel,
            stream: true as const,
            maxTokens: this.config.summarizerMaxTokens,
            temperature: this.config.summarizerTemperature,
            thinking: 'none' as const,
          } as any;

          let text = '';
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), this.config.summarizerTimeoutMs);
          try {
            const stream = (this.provider as any).complete(messages as any, opts as any, undefined, controller.signal) as AsyncIterable<any>;
            for await (const chunk of stream) {
              if (chunk.type === 'token' && chunk.text) text += chunk.text;
              if (chunk.type === 'error') throw new Error(chunk.error || 'provider error');
              if (chunk.type === 'done') break;
            }
          } finally {
            clearTimeout(timer);
          }

          // Try to parse JSON first
          const jsonMatch = (text || '').match(/\{[\s\S]*\}/);
          let parsed: any = null;
          if (jsonMatch) {
            try { parsed = JSON.parse(jsonMatch[0]); } catch { parsed = null; }
          }

          if (parsed) {
            if (parsed.clusterLabel) clusterLabel = parsed.clusterLabel;
            if (parsed.summary) summaryText = parsed.summary;
            if (typeof parsed.persist === 'boolean') persistAdvice = parsed.persist;
            if (typeof parsed.confidence === 'number') {
              // blend with avgConfidence
            }
          } else {
            // Soft parse heuristics
            const soft = this.fallbackParseFreeform(text);
            if (soft.clusterLabel) clusterLabel = soft.clusterLabel;
            if (soft.summary) summaryText = soft.summary;
            if (typeof soft.persist === 'boolean') persistAdvice = soft.persist;
          }
        } catch (err) {
          this.logger.debug('Subconscious: summarizer failed', { error: String(err) });
        }
      }

      // Final persist decision
      const shouldPersist = (persistAdvice !== null)
        ? persistAdvice
        : ((count >= this.config.minSignals) || (avgConfidence >= this.config.persistConfidenceThreshold) || (anomalyScore >= 0.75));

      const learning: any = {
        summary: summaryText,
        clusterLabel,
        confidence: avgConfidence,
        anomalyScore,
        anomalyReason,
        meta: { type, count, avgConfidence, samples, firstSeen, lastSeen, simAvg },
        persisted: false,
        persistedId: null,
        timestamp: Date.now(),
      };

      if (shouldPersist) {
        try {
          if (this.memory && this.config.persistMemory) {
            const id = await this.memory.store({ type: 'insight', content: learning.summary, metadata: { clusterLabel, meta: learning.meta, anomalyScore, anomalyReason } });
            learning.persisted = true;
            learning.persistedId = id;
            this.logger.info('Subconscious: persisted learning to memory', { id, clusterLabel, count });
          } else if (this.config.persistToFile) {
            let existing: any[] = [];
            try { if (fs.existsSync(this.filePath)) existing = JSON.parse(fs.readFileSync(this.filePath, 'utf8') || '[]') as any[]; } catch {}
            const id = `sublearn_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
            const entry = { id, summary: learning.summary, clusterLabel, meta: learning.meta, anomalyScore, anomalyReason, timestamp: Date.now() };
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

      // Update moving average baseline for this type
      try {
        const prev = this.avgCounts[baselineKey] || 0;
        const updated = (prev * 0.9) + (count * 0.1);
        this.avgCounts[baselineKey] = updated;
        if (this.memory) await this.memory.kv_set('subconscious:avgCounts', this.avgCounts);
      } catch (err) {
        this.logger.debug('Subconscious: failed to update avgCounts', { error: String(err) });
      }

      // Emit learning event
      try { (this.eventBus as any)?.emit?.({ type: 'subconscious:learning', learning, sessionId: null }); } catch {}

      // If anomaly score is high or heuristics triggered, emit anomaly event and persist
      const anomalyThreshold = 0.72;
      if (learning.anomalyScore >= anomalyThreshold) {
        try {
          const anomaly = { summary: learning.summary, clusterLabel: learning.clusterLabel, reason: learning.anomalyReason || '', evidence: learning.meta.samples, confidence: learning.confidence, anomalyScore: learning.anomalyScore, timestamp: Date.now() };
          (this.eventBus as any)?.emit?.({ type: 'subconscious:anomaly', anomaly, sessionId: null });
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

  // ---------------------- Helpers ----------------------

  private async fetchEmbeddingsBatch(texts: string[], timeoutMs = 3000, chunkSize = 32): Promise<Array<number[] | null>> {
    if (!texts || texts.length === 0) return [];

    const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
    const model = this.config.embeddingModel;

    // If chunking is required, process in chunks
    if (texts.length > chunkSize) {
      const out: Array<number[] | null> = [];
      for (let i = 0; i < texts.length; i += chunkSize) {
        const chunk = texts.slice(i, i + chunkSize);
        const res = await this.fetchEmbeddingsBatch(chunk, timeoutMs, chunkSize);
        out.push(...res);
      }
      return out;
    }

    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs + Math.min(2000, texts.length * 60));
      const body = { model, input: texts.map(t => (t || '').replace(/\n/g, ' ')) };
      const res = await fetch(`${OLLAMA_URL}/api/embeddings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (res.ok) {
        const data = await res.json() as any;
        if (Array.isArray(data?.embeddings) && data.embeddings.length === texts.length) {
          return data.embeddings.map((e: any) => Array.isArray(e) ? e : null);
        }
        if (Array.isArray(data?.results) && data.results.length === texts.length) {
          return data.results.map((r: any) => Array.isArray(r?.embedding) ? r.embedding : null);
        }
        if (Array.isArray(data?.embedding) && texts.length === 1) return [data.embedding];
      }
    } catch (err) {
      this.logger.debug('Subconscious: batch embeddings request failed', { error: String(err), chunkSize });
    }

    // fallback to sequential single calls
    const out: Array<number[] | null> = [];
    for (const t of texts) {
      try {
        const vec = await this.fetchSingleEmbedding(t, timeoutMs);
        out.push(vec);
      } catch {
        out.push(null);
      }
    }
    return out;
  }

  private async fetchSingleEmbedding(text: string, timeoutMs = 3000): Promise<number[] | null> {
    const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
    const model = this.config.embeddingModel;
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      const res = await fetch(`${OLLAMA_URL}/api/embeddings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, prompt: (text || '').replace(/\n/g, ' ') }),
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (!res.ok) return null;
      const data = await res.json() as any;
      if (Array.isArray(data?.embedding)) return data.embedding as number[];
      if (Array.isArray(data?.embeddings) && data.embeddings.length === 1) return data.embeddings[0];
      if (Array.isArray(data?.results) && data.results.length === 1) return data.results[0]?.embedding ?? null;
      return null;
    } catch {
      return null;
    }
  }

  private cosineSimilarity(a: number[] | null, b: number[] | null): number {
    if (!a || !b || a.length !== b.length) return 0;
    let dot = 0, ma = 0, mb = 0;
    for (let i = 0; i < a.length; i++) {
      dot += (a[i] || 0) * (b[i] || 0);
      ma += (a[i] || 0) * (a[i] || 0);
      mb += (b[i] || 0) * (b[i] || 0);
    }
    if (ma === 0 || mb === 0) return 0;
    return dot / (Math.sqrt(ma) * Math.sqrt(mb));
  }

  private buildClusterSummarizerPrompt(meta: { type: string; count: number; avgConfidence: number; samples: string[]; firstSeen: number; lastSeen: number; simAvg: number; anomalyScore: number }) {
    const samplesText = meta.samples.slice(0, 6).map((s, i) => `(${i+1}) ${s}`).join('\n');
    return `You are a concise background analyst. Given the cluster metadata below, respond with a JSON object containing:\n- clusterLabel: short label (1-5 words)\n- summary: 1-2 sentence summary of the core insight or issue\n- persist: true|false\n- confidence: 0.0-1.0\n- anomalyScore: 0.0-1.0\n\nCluster metadata:\n- type: ${meta.type}\n- count: ${meta.count}\n- avgConfidence: ${meta.avgConfidence.toFixed(2)}\n- simAvg: ${meta.simAvg.toFixed(2)}\n- anomalyScore: ${meta.anomalyScore.toFixed(2)}\n\nSamples:\n${samplesText}\n\nRespond ONLY with valid JSON.`;
  }

  private fallbackParseFreeform(text: string): any {
    const lines = (text || '').split('\n').map(l => l.trim()).filter(Boolean);
    const res: any = {};
    for (const l of lines.slice(0, 12)) {
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
    // Quick heuristic: if no clusterLabel but first line short, use that
    if (!res.clusterLabel && lines.length > 0) {
      const first = lines[0];
      if (first.length < 60) res.clusterLabel = first.slice(0, 60);
    }
    if (!res.summary && lines.length > 1) res.summary = lines.slice(0, 2).join(' ');
    return res;
  }
}

export const createSubconscious = (logger: ILogger, config?: Partial<SubconsciousConfig>): Subconscious =>
  new Subconscious(logger, config);
