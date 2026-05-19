/**
 * FeatureIndex — bidirectional map from vindex features → engrams.
 *
 * When an engram is stored, its content is run through gate KNN to find
 * the model features it activates. Those feature keys (e.g. "L16:F4521")
 * are stored in a Set<engramId> per feature. At retrieval time, the query's
 * gate KNN result directly points to engrams that activated the same
 * features — no ANN cosine scan needed for exact feature matches.
 *
 * This is the key that makes the vindex a substrate, not a bridge:
 * the model's internal activation pattern IS the retrieval index.
 *
 * Phase 8 integration: Built lazily from existing engrams and updated
 * during storeForSession when the vindex provider is available.
 */
import type { ILogger } from '../../../types/interfaces.js'
import type { Cortex } from './cortex.js'

/** Feature key format: "L{layer}:F{featureIndex}" */
function featureKey(layer: number, featureIndex: number): string {
  return `L${layer}:F${featureIndex}`
}

/** A vindex gate-KNN call: (text) => Array<{layer, featureIndex, score}> */
export type VindexGateKnnFn = (
  text: string,
  options?: { layers?: number[]; featuresPerLayer?: number; minScore?: number },
) => Array<{ layer: number; featureIndex: number; score: number }>

export interface FeatureIndexEntry {
  engramId: string
  /** Number of shared features — used for ordering direct-match hits. */
  sharedFeatureCount: number
}

export class FeatureIndex {
  /** feature key → Set of engram IDs that activated this feature */
  private featureToEngrams = new Map<string, Set<string>>()

  /** engram ID → feature keys (for removal on engram update) */
  private engramToFeatures = new Map<string, string[]>()

  private logger: ILogger
  private gateKnn: VindexGateKnnFn | null = null
  private ready = false

  constructor(logger: ILogger) {
    this.logger = logger.child ? logger.child('feature-index') : logger
  }

  /** Wire the gate-KNN function. Required before index(). */
  setGateKnn(fn: VindexGateKnnFn | null): void {
    this.gateKnn = fn
    this.ready = !!fn
    this.logger.info('FeatureIndex gateKnn set', { ready: this.ready })
  }

  /** Whether the index is ready for queries. */
  isReady(): boolean {
    return this.ready
  }

  /**
   * Index an engram from its content. Gate-KNNs the content and stores
   * the activated feature→engramId mapping.
   *
   * Call during storeForSession when vindex is available. Re-indexing
   * the same engramId with different content cleans up old mappings first.
   */
  indexEngram(
    engramId: string,
    content: string,
    options?: {
      layers?: number[]
      featuresPerLayer?: number
      minScore?: number
    },
  ): void {
    if (!this.ready || !this.gateKnn) return
    if (!content || content.length < 20) return

    // Clean up old feature mappings before re-indexing (content may have changed).
    this.removeEngram(engramId)

    try {
      const features = this.gateKnn(content, {
        layers: options?.layers,
        featuresPerLayer: options?.featuresPerLayer ?? 10,
        minScore: options?.minScore ?? 0.05,
      })

      if (features.length === 0) return

      const keys = features.map(f => featureKey(f.layer, f.featureIndex))

      // Store forward mapping: feature → engrams
      for (const key of keys) {
        let set = this.featureToEngrams.get(key)
        if (!set) {
          set = new Set()
          this.featureToEngrams.set(key, set)
        }
        set.add(engramId)
      }

      // Store reverse mapping: engram → features
      this.engramToFeatures.set(engramId, keys)
    } catch (err) {
      this.logger.debug?.('FeatureIndex.indexEngram failed', {
        engramId: engramId.slice(0, 12),
        error: String(err),
      })
    }
  }

  /**
   * Remove an engram from the index. Called when engram content changes
   * or the engram is deleted.
   */
  removeEngram(engramId: string): void {
    const keys = this.engramToFeatures.get(engramId)
    if (!keys) return

    for (const key of keys) {
      const set = this.featureToEngrams.get(key)
      if (set) {
        set.delete(engramId)
        if (set.size === 0) this.featureToEngrams.delete(key)
      }
    }
    this.engramToFeatures.delete(engramId)
  }

  /**
   * Find engrams that share features with the given text.
   * Returns engrams ranked by number of shared features (descending).
   *
   * This is the direct feature-indexed retrieval path — the model's
   * gate KNN activation pattern IS the query. No cosine scan needed.
   */
  lookup(
    text: string,
    options?: {
      layers?: number[]
      featuresPerLayer?: number
      minScore?: number
      limit?: number
    },
  ): FeatureIndexEntry[] {
    if (!this.ready || !this.gateKnn) return []
    if (!text) return []

    try {
      const features = this.gateKnn(text, {
        layers: options?.layers,
        featuresPerLayer: options?.featuresPerLayer ?? 10,
        minScore: options?.minScore ?? 0.05,
      })

      if (features.length === 0) return []

      const limit = options?.limit ?? 20
      const overlapCount = new Map<string, number>()

      for (const f of features) {
        const key = featureKey(f.layer, f.featureIndex)
        const engramIds = this.featureToEngrams.get(key)
        if (!engramIds) continue
        for (const id of engramIds) {
          overlapCount.set(id, (overlapCount.get(id) ?? 0) + 1)
        }
      }

      return [...overlapCount.entries()]
        .map(([engramId, count]) => ({ engramId, sharedFeatureCount: count }))
        .sort((a, b) => b.sharedFeatureCount - a.sharedFeatureCount)
        .slice(0, limit)
    } catch (err) {
      this.logger.debug?.('FeatureIndex.lookup failed', { error: String(err) })
      return []
    }
  }

  /**
   * Build the index from existing engrams in the Cortex.
   * Iterates engrams with content, runs gate KNN, populates the index.
   *
   * Best-effort and throttled — yields to event loop every 50 engrams.
   * Returns the number of engrams indexed.
   */
  async buildFromCortex(
    cortex: Cortex,
    options?: {
      limit?: number
      layers?: number[]
      featuresPerLayer?: number
      minScore?: number
    },
  ): Promise<number> {
    if (!this.ready || !this.gateKnn) return 0

    const limit = options?.limit ?? 10000
    const engrams = cortex.listEngrams(limit).filter(
      e => e.content && e.content.length > 20 && e.content.length < 50000,
    )

    let indexed = 0
    for (let i = 0; i < engrams.length; i++) {
      const e = engrams[i]
      this.indexEngram(e.id, e.content, options)
      indexed++

      // Yield to event loop every 50 engrams
      if (indexed % 50 === 0) {
        await new Promise(resolve => setImmediate(resolve))
      }
    }

    this.logger.info('FeatureIndex built from cortex', {
      scanned: engrams.length,
      indexed,
      featureKeys: this.featureToEngrams.size,
    })

    return indexed
  }

  /** Statistics about the index. */
  stats(): { engrams: number; featureKeys: number; ready: boolean } {
    return {
      engrams: this.engramToFeatures.size,
      featureKeys: this.featureToEngrams.size,
      ready: this.ready,
    }
  }

  /**
   * Find engrams that share vindex features with the given engram.
   *
   * Uses the stored feature→engram mapping to find engrams whose gate
   * activation patterns overlap. Returns engrams ranked by number of
   * shared features (descending). Excludes self.
   *
   * These correlations become `vindex_correlation` synapses — the bridge
   * between continuous ANN space and discrete model-feature space.
   */
  findCorrelated(
    engramId: string,
    options?: { minOverlap?: number; limit?: number },
  ): Array<{ engramId: string; sharedFeatureCount: number }> {
    const keys = this.engramToFeatures.get(engramId)
    if (!keys || keys.length === 0) return []

    const minOverlap = options?.minOverlap ?? 1
    const limit = options?.limit ?? 20
    const overlapCount = new Map<string, number>()

    for (const key of keys) {
      const engramIds = this.featureToEngrams.get(key)
      if (!engramIds) continue
      for (const id of engramIds) {
        if (id === engramId) continue
        overlapCount.set(id, (overlapCount.get(id) ?? 0) + 1)
      }
    }

    return [...overlapCount.entries()]
      .filter(([_, count]) => count >= minOverlap)
      .map(([id, count]) => ({ engramId: id, sharedFeatureCount: count }))
      .sort((a, b) => b.sharedFeatureCount - a.sharedFeatureCount)
      .slice(0, limit)
  }
}
