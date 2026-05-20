/**
 * LmdbFeatureIndex — LMDB-backed vindex feature → engram index.
 *
 * Replaces the SQLite-backed FeatureIndex with LMDB (Lightning Memory-Mapped
 * Database). Same interface, zero-copy mmap'd reads, MVCC (no WAL/checkpoint
 * blocking), sorted duplicate keys (MDB_DUPSORT).
 *
 * Data layout:
 *   feature_to_engrams  (dupSort):  feature_key → engram_id  (sorted)
 *   engram_to_features  (dupSort):  engram_id   → feature_key (sorted)
 *
 * This is Phase A of the V-Field substrate migration. Phase B moves the
 * engram data into the vindex binary format itself.
 */
import type { ILogger } from '../../../types/interfaces.js'
import type { Cortex } from './cortex.js'
import type { VindexGateKnnFn, FeatureIndexEntry } from './feature-index.js'
import { open as lmdbOpen } from 'lmdb'

export class LmdbFeatureIndex {
  private env: any              // lmdb RootDatabase
  private featureToEngrams: any // lmdb Database (dupSort)
  private engramToFeatures: any // lmdb Database (dupSort)
  private logger: ILogger
  private gateKnn: VindexGateKnnFn | null = null
  private ready = false

  constructor(envPath: string, logger: ILogger) {
    this.logger = logger.child?.('feature-index') ?? logger

    this.env = lmdbOpen(envPath, {
      noSync: true,              // fast writes — OS flushes pages
      mapSize: 2 * 1024 * 1024 * 1024, // 2GB virtual address space
    })

    this.featureToEngrams = this.env.openDB('feature_to_engrams', {
      dupSort: true,
      keyEncoding: 'ordered-binary',
      encoding: 'string',
    })

    this.engramToFeatures = this.env.openDB('engram_to_features', {
      dupSort: true,
      keyEncoding: 'ordered-binary',
      encoding: 'string',
    })

    this.logger.info('LmdbFeatureIndex opened', { envPath })
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
   * feature→engramId mappings in LMDB.
   *
   * Re-indexing the same engramId cleans up old mappings first.
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

    this.removeEngram(engramId)

    try {
      const features = this.gateKnn(content, {
        layers: options?.layers,
        featuresPerLayer: options?.featuresPerLayer ?? 10,
        minScore: options?.minScore ?? 0.05,
      })

      if (features.length === 0) return

      this.env.transactionSync(() => {
        for (const f of features) {
          const key = `L${f.layer}:F${f.featureIndex}`
          this.featureToEngrams.putSync(key, engramId)
          this.engramToFeatures.putSync(engramId, key)
        }
      })
    } catch (err) {
      this.logger.debug?.('LmdbFeatureIndex.indexEngram failed', {
        engramId: engramId.slice(0, 12),
        error: String(err),
      })
    }
  }

  /**
   * Remove an engram from the index.
   */
  removeEngram(engramId: string): void {
    const features = this.engramToFeatures.getValues(engramId)
    if (!features) return

    const featureList = Array.from(features) as string[]
    if (featureList.length === 0) return

    this.env.transactionSync(() => {
      for (const key of featureList) {
        this.featureToEngrams.removeSync(key, engramId)
      }
      this.engramToFeatures.removeSync(engramId)
    })
  }

  /**
   * Find engrams that share features with the given text.
   * Runs gateKnn on the text, looks up matching engrams via LMDB.
   *
   * Returns engrams ranked by number of shared features (descending).
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

      // For each query feature, iterate its engram set.
      for (const f of features) {
        const key = `L${f.layer}:F${f.featureIndex}`
        const engrams = this.featureToEngrams.getValues(key)
        if (!engrams) continue
        for (const id of engrams) {
          overlapCount.set(id, (overlapCount.get(id) ?? 0) + 1)
        }
      }

      if (overlapCount.size === 0) return []

      return [...overlapCount.entries()]
        .map(([engramId, count]) => ({ engramId, sharedFeatureCount: count }))
        .sort((a, b) => b.sharedFeatureCount - a.sharedFeatureCount)
        .slice(0, limit)
    } catch (err) {
      this.logger.debug?.('LmdbFeatureIndex.lookup failed', { error: String(err) })
      return []
    }
  }

  /**
   * Build the index from existing engrams in the Cortex.
   * Best-effort and throttled — yields every 50 engrams.
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
      this.indexEngram(engrams[i].id, engrams[i].content, options)
      indexed++
      if (indexed % 50 === 0) {
        await new Promise(resolve => setImmediate(resolve))
      }
    }

    const stats = this.stats()
    this.logger.info('LmdbFeatureIndex built from cortex', {
      scanned: engrams.length,
      indexed,
      featureKeys: stats.featureKeys,
    })

    return indexed
  }

  /** Statistics about the index. */
  stats(): { engrams: number; featureKeys: number; ready: boolean } {
    return {
      engrams: this.engramToFeatures.getKeysCount?.() ?? 0,
      featureKeys: this.featureToEngrams.getKeysCount?.() ?? 0,
      ready: this.ready,
    }
  }

  /**
   * Find engrams that share vindex features with the given engram.
   * Used for vindex_correlation synapse creation during store().
   */
  findCorrelated(
    engramId: string,
    options?: { minOverlap?: number; limit?: number },
  ): Array<{ engramId: string; sharedFeatureCount: number }> {
    const features = this.engramToFeatures.getValues(engramId)
    if (!features) return []

    const featureList = Array.from(features) as string[]
    if (featureList.length === 0) return []

    const minOverlap = options?.minOverlap ?? 2
    const limit = options?.limit ?? 20
    const overlapCount = new Map<string, number>()

    for (const key of featureList) {
      const engrams = this.featureToEngrams.getValues(key)
      if (!engrams) continue
      for (const id of engrams) {
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
