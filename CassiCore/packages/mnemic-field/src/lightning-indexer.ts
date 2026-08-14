import type { ILogger } from '@cassicore/foundation'
import type { Cortex } from './cortex.js'
import { compressEmbedding } from './cortex.js'
import {
  LIGHTNING_INDEXER_VERSION,
  LIGHTNING_INDEXER_DEFAULTS,
  type LightningIndexerConfig,
  type LightningIndexerGlobal,
  type LightningCandidate,
  type LightningRanked,
} from './types.js'

interface PreparedQuery {
  qI: Float32Array
}

export class LightningIndexer {
  private readonly cortex: Cortex
  private readonly logger: ILogger
  private readonly config: LightningIndexerConfig
  private global: LightningIndexerGlobal | null = null
  /** Cached recency window IDs with short TTL to avoid per-retrieval DB queries. */
  private recencyCache: { ids: string[]; ts: number } | null = null
  private static readonly RECENCY_CACHE_TTL_MS = 30_000  // 30 seconds

  constructor(cortex: Cortex, logger: ILogger, config?: Partial<LightningIndexerConfig>) {
    this.cortex = cortex
    this.logger = logger.child ? logger.child('lightning-indexer') : logger
    this.config = { ...LIGHTNING_INDEXER_DEFAULTS, ...config }
  }

  ensureInit(): LightningIndexerGlobal {
    if (this.global) return this.global

    const existing = this.cortex.getLightningGlobal()
    if (existing && existing.dEmb === this.config.dEmb && existing.dC === this.config.dC
      && existing.nH === this.config.nH && existing.dIdx === this.config.dIdx) {
      this.global = existing
      return existing
    }

    if (existing) {
      this.logger.info('Lightning indexer dimensions changed; reinitializing', {
        from: { dEmb: existing.dEmb, dC: existing.dC, nH: existing.nH, dIdx: existing.dIdx },
        to: { dEmb: this.config.dEmb, dC: this.config.dC, nH: this.config.nH, dIdx: this.config.dIdx },
      })
    }

    const fresh = initializeGlobal(this.config)
    this.cortex.setLightningGlobal({
      wDq: fresh.wDq,
      wIuq: fresh.wIuq,
      wI: fresh.wI,
      dEmb: fresh.dEmb,
      dC: fresh.dC,
      nH: fresh.nH,
      dIdx: fresh.dIdx,
      version: fresh.version,
    })
    this.global = { ...fresh, updatedAt: new Date().toISOString() }
    this.logger.info('Lightning indexer initialized', {
      dEmb: fresh.dEmb, dC: fresh.dC, nH: fresh.nH, dIdx: fresh.dIdx, version: fresh.version,
    })
    return this.global
  }

  prepareQuery(queryEmbedding: Float32Array): PreparedQuery {
    const g = this.ensureInit()
    if (queryEmbedding.length !== g.dEmb) {
      throw new Error(`Query embedding dim ${queryEmbedding.length} != indexer dEmb ${g.dEmb}`)
    }
    const qI = projectToIndex(queryEmbedding, g)
    return { qI }
  }

  score(queryEmbedding: Float32Array, candidates: LightningCandidate[]): LightningRanked[] {
    const g = this.ensureInit()
    if (queryEmbedding.length !== g.dEmb) {
      throw new Error(`Query embedding dim ${queryEmbedding.length} != indexer dEmb ${g.dEmb}`)
    }
    if (candidates.length === 0) return []
    const { qI } = this.prepareQuery(queryEmbedding)

    const ids = candidates.map((c) => c.engramId)
    const existingKeys = this.cortex.getLightningKeys(ids)
    const toPersist: Array<{ engramId: string; keys: Float32Array | Buffer; version: number }> = []

    const ranked: LightningRanked[] = []
    for (const cand of candidates) {
      let keys = existingKeys.get(cand.engramId)
      if (!keys) {
        if (cand.embedding.length !== g.dEmb) {
          this.logger.warn('Skipping candidate with mismatched embedding dim', {
            engramId: cand.engramId, expected: g.dEmb, got: cand.embedding.length,
          })
          continue
        }
        keys = projectToIndex(cand.embedding, g)
        const storeKeys = this.config.compressKeys ? compressEmbedding(keys) : keys
        toPersist.push({ engramId: cand.engramId, keys: storeKeys!, version: g.version })
      }
      const score = scoreCandidate(qI, keys, g.wI, g.nH, g.dIdx)
      ranked.push({ engramId: cand.engramId, score })
    }

    if (toPersist.length > 0) {
      try {
        const written = this.cortex.bulkUpsertLightningKeys(toPersist)
        this.logger.debug('Bootstrapped lightning keys', { count: written })
      } catch (err) {
        this.logger.warn('Failed to persist bootstrapped lightning keys', { error: String(err) })
      }
    }

    ranked.sort((a, b) => b.score - a.score)
    return ranked
  }

  topK(queryEmbedding: Float32Array, candidates: LightningCandidate[], k: number): LightningRanked[] {
    return this.score(queryEmbedding, candidates).slice(0, k)
  }

  /**
   * Sparsification gate: score all candidates, keep top-k by indexer score
   * plus a recency window of the most recently stored engrams (by engram creation
   * order in the Cortex). Returns the filtered candidate IDs and the full ranked
   * results (so the caller doesn't need to re-score for logging).
   *
   * This is the DeepSeek V4-style sparse selection: top-k blocks + sliding window.
   */
  sparsify(
    queryEmbedding: Float32Array,
    candidates: LightningCandidate[],
    topK: number,
    recencyWindow: number,
  ): { keptIds: string[]; ranked: LightningRanked[] } {
    if (candidates.length === 0) return { keptIds: [], ranked: [] }

    const ranked = this.score(queryEmbedding, candidates)

    // Top-k by indexer score
    const topIds = new Set(ranked.slice(0, Math.min(topK, ranked.length)).map(r => r.engramId))

    // Always include the most recent N engrams (recency window), cached with short TTL
    if (recencyWindow > 0) {
      const now = Date.now()
      if (!this.recencyCache || (now - this.recencyCache.ts) > LightningIndexer.RECENCY_CACHE_TTL_MS) {
        this.recencyCache = { ids: this.cortex.getMostRecentEngramIds(recencyWindow), ts: now }
      }
      for (const id of this.recencyCache.ids) {
        topIds.add(id)
      }
    }

    // Preserve original order from candidates (only keep those selected)
    const keptIds = candidates
      .filter(c => topIds.has(c.engramId))
      .map(c => c.engramId)

    return { keptIds, ranked }
  }

  /**
   * Replace the in-memory weights with externally trained values.
   * Called by IndexerTrainer after a training step.
   */
  updateWeights(wDq: Float32Array, wIuq: Float32Array, wI: Float32Array, newVersion: number): void {
    const g = this.ensureInit()
    if (wDq.length !== g.wDq.length || wIuq.length !== g.wIuq.length || wI.length !== g.wI.length) {
      this.logger.warn('updateWeights: dimension mismatch, skipping', {
        expected: { wDq: g.wDq.length, wIuq: g.wIuq.length, wI: g.wI.length },
        got: { wDq: wDq.length, wIuq: wIuq.length, wI: wI.length },
      })
      return
    }
    g.wDq.set(wDq)
    g.wIuq.set(wIuq)
    g.wI.set(wI)
    g.version = newVersion
    g.updatedAt = new Date().toISOString()
  }

  stats(): { globalReady: boolean; keysCount: number; version: number; dims: { dEmb: number; dC: number; nH: number; dIdx: number } } {
    const g = this.global ?? this.cortex.getLightningGlobal()
    return {
      globalReady: g != null,
      keysCount: this.cortex.lightningKeysCount(),
      version: g?.version ?? -1,
      dims: {
        dEmb: g?.dEmb ?? this.config.dEmb,
        dC: g?.dC ?? this.config.dC,
        nH: g?.nH ?? this.config.nH,
        dIdx: g?.dIdx ?? this.config.dIdx,
      },
    }
  }
}

function initializeGlobal(cfg: LightningIndexerConfig): LightningIndexerGlobal {
  const rng = mulberry32(cfg.seed)
  const wDq = heInit(cfg.dC * cfg.dEmb, cfg.dEmb, rng)
  const wIuq = heInit(cfg.nH * cfg.dIdx * cfg.dC, cfg.dC, rng)
  const wI = new Float32Array(cfg.nH).fill(1 / cfg.nH)
  return {
    wDq,
    wIuq,
    wI,
    dEmb: cfg.dEmb,
    dC: cfg.dC,
    nH: cfg.nH,
    dIdx: cfg.dIdx,
    version: LIGHTNING_INDEXER_VERSION,
    updatedAt: new Date().toISOString(),
  }
}

function projectToIndex(input: Float32Array, g: LightningIndexerGlobal): Float32Array {
  const hidden = new Float32Array(g.dC)
  for (let i = 0; i < g.dC; i++) {
    let acc = 0
    const rowOffset = i * g.dEmb
    for (let j = 0; j < g.dEmb; j++) acc += g.wDq[rowOffset + j] * input[j]
    hidden[i] = acc > 0 ? acc : 0
  }
  const outDim = g.nH * g.dIdx
  const out = new Float32Array(outDim)
  for (let i = 0; i < outDim; i++) {
    let acc = 0
    const rowOffset = i * g.dC
    for (let j = 0; j < g.dC; j++) acc += g.wIuq[rowOffset + j] * hidden[j]
    out[i] = acc > 0 ? acc : 0
  }
  return out
}

function scoreCandidate(qI: Float32Array, keys: Float32Array, wI: Float32Array, nH: number, dIdx: number): number {
  let total = 0
  for (let h = 0; h < nH; h++) {
    const off = h * dIdx
    let dot = 0
    for (let d = 0; d < dIdx; d++) dot += qI[off + d] * keys[off + d]
    if (dot > 0) total += wI[h] * dot
  }
  return total
}

function heInit(count: number, fanIn: number, rng: () => number): Float32Array {
  const stddev = Math.sqrt(2 / fanIn)
  const out = new Float32Array(count)
  for (let i = 0; i < count; i++) {
    const u1 = Math.max(rng(), 1e-12)
    const u2 = rng()
    const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2)
    out[i] = z * stddev
  }
  return out
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return function () {
    a = (a + 0x6D2B79F5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
