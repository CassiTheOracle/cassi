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
 * Merge-on-overlap: when a new engram's gateKnn features overlap ≥95% with
 * an existing engram, the new engram is merged into the existing one rather
 * than indexed separately. Merges union the feature sets and the caller
 * boosts the anchor engram's potentiation.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { Cortex } from './cortex.js'
import type { VindexGateKnnFn, FeatureIndexEntry } from './feature-index.js'
import { open as lmdbOpen } from 'lmdb'

/** Return type for indexEngram — tells the caller whether to store or merge. */
export interface IndexResult {
  action: 'indexed' | 'merged'
  /** When merged: the engramId of the existing engram that absorbed this one. */
  mergedInto?: string
  /** Feature overlap ratio that triggered the merge. */
  overlapRatio?: number
  /** Number of features in the anchor engram (for weighted boost). */
  featureCount?: number
}

/** Feature overlap ratio ≥ this → merge instead of indexing. */
const MERGE_OVERLAP_THRESHOLD = 0.95

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
   * Before inserting, checks for near-complete feature overlap (≥95%)
   * with an existing engram. If found, merges the feature sets and
   * returns `{ action: 'merged' }` — the caller should boost the
   * anchor engram's potentiation instead of storing a new engram.
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
  ): IndexResult {
    if (!this.ready || !this.gateKnn) return { action: 'indexed' }
    if (!content || content.length < 20) return { action: 'indexed' }

    this.removeEngram(engramId)

    try {
      const features = this.gateKnn(content, {
        layers: options?.layers,
        featuresPerLayer: options?.featuresPerLayer ?? 10,
        minScore: options?.minScore ?? 0.05,
      })

      if (features.length === 0) return { action: 'indexed' }

      const featureKeys = features.map(f => `L${f.layer}:F${f.featureIndex}`)

      // Check for near-complete overlap with an existing engram.
      const overlapping = this.findOverlappingByKeys(featureKeys, { limit: 1 })
      if (overlapping.length > 0) {
        const top = overlapping[0]
        const overlapRatio = top.sharedFeatureCount / featureKeys.length
        if (overlapRatio >= MERGE_OVERLAP_THRESHOLD) {
          const anchorKeys = this.getFeatureKeys(top.engramId)
          const anchorFeatureCount = anchorKeys.length

          // Anchor quality check: if the newcomer has significantly more
          // features (1.5×), it's the richer engram — reverse the merge.
          // The old anchor is removed from the index; the newcomer absorbs it.
          if (featureKeys.length > anchorFeatureCount * 1.5) {
            this.removeEngram(top.engramId)
            // Union: newcomer's features + any anchor features it doesn't have.
            const anchorSet = new Set(anchorKeys)
            const union = featureKeys.filter(k => !anchorSet.has(k)).length > 0
              ? [...new Set([...featureKeys, ...anchorKeys])]
              : featureKeys
            this.env.transactionSync(() => {
              for (const key of union) {
                this.featureToEngrams.putSync(key, engramId)
                this.engramToFeatures.putSync(engramId, key)
              }
            })
            this.logger.debug?.('FeatureIndex reversed merge', {
              engramId: engramId.slice(0, 12),
              absorbed: top.engramId.slice(0, 12),
              newFeatures: featureKeys.length,
              anchorFeatures: anchorFeatureCount,
              ratio: (featureKeys.length / anchorFeatureCount).toFixed(2),
            })
            // Reversed: caller stores this engram normally; old anchor gone from index.
            return { action: 'indexed' }
          }

          // Normal merge: union the feature sets into the anchor engram.
          this.mergeFeatures(top.engramId, featureKeys)
          this.logger.debug?.('FeatureIndex merged engram', {
            engramId: engramId.slice(0, 12),
            into: top.engramId.slice(0, 12),
            overlapRatio: overlapRatio.toFixed(3),
          })
          return { action: 'merged', mergedInto: top.engramId, overlapRatio, featureCount: anchorFeatureCount }
        }
      }

      // No merge — store as new.
      this.env.transactionSync(() => {
        for (const key of featureKeys) {
          this.featureToEngrams.putSync(key, engramId)
          this.engramToFeatures.putSync(engramId, key)
        }
      })

      return { action: 'indexed' }
    } catch (err) {
      this.logger.debug?.('LmdbFeatureIndex.indexEngram failed', {
        engramId: engramId.slice(0, 12),
        error: String(err),
      })
      return { action: 'indexed' }
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

      const featureKeys = features.map(f => `L${f.layer}:F${f.featureIndex}`)
      return this.findOverlappingByKeys(featureKeys, { limit: options?.limit ?? 20 })
    } catch (err) {
      this.logger.debug?.('LmdbFeatureIndex.lookup failed', { error: String(err) })
      return []
    }
  }

  /**
   * Build the index from existing engrams in the Cortex.
   * Best-effort and throttled — yields every 10 newly-indexed engrams.
   * Merges count as skipped (the anchor engram already exists).
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
    let skipped = 0
    let merged = 0
    for (let i = 0; i < engrams.length; i++) {
      // Skip already-indexed engrams (persistent across boots).
      if (this.engramToFeatures.get(engrams[i].id) !== undefined) {
        skipped++
        continue
      }
      const result = this.indexEngram(engrams[i].id, engrams[i].content, options)
      if (result.action === 'merged') {
        merged++
      } else {
        indexed++
      }
      if ((indexed + merged) % 10 === 0) {
        await new Promise(resolve => setImmediate(resolve))
      }
    }

    const stats = this.stats()
    this.logger.info('LmdbFeatureIndex built from cortex', {
      scanned: engrams.length,
      indexed,
      merged,
      skipped,
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
    return this.findOverlappingByKeys(featureList, {
      excludeId: engramId,
      minOverlap,
      limit: options?.limit ?? 20,
    })
  }

  /**
   * Get all feature keys for an engram. Returns empty array if not indexed.
   */
  private getFeatureKeys(engramId: string): string[] {
    const features = this.engramToFeatures.getValues(engramId)
    return features ? Array.from(features) as string[] : []
  }

  /**
   * Find engrams that share the given feature keys.
   * Core overlap primitive used by lookup, findCorrelated, and merge check.
   */
  private findOverlappingByKeys(
    featureKeys: string[],
    opts?: { excludeId?: string; minOverlap?: number; limit?: number },
  ): Array<{ engramId: string; sharedFeatureCount: number }> {
    const excludeId = opts?.excludeId
    const minOverlap = opts?.minOverlap ?? 0
    const limit = opts?.limit ?? 20
    const overlapCount = new Map<string, number>()

    for (const key of featureKeys) {
      const engrams = this.featureToEngrams.getValues(key)
      if (!engrams) continue
      for (const id of engrams) {
        if (id === excludeId) continue
        overlapCount.set(id, (overlapCount.get(id) ?? 0) + 1)
      }
    }

    return [...overlapCount.entries()]
      .filter(([_, count]) => count >= minOverlap)
      .map(([id, count]) => ({ engramId: id, sharedFeatureCount: count }))
      .sort((a, b) => b.sharedFeatureCount - a.sharedFeatureCount)
      .slice(0, limit)
  }

  /**
   * Merge feature keys into an existing engram — union the feature sets.
   * Only adds features the anchor engram doesn't already have.
   */
  private mergeFeatures(engramId: string, newFeatureKeys: string[]): void {
    const existing = this.getFeatureKeys(engramId)
    const existingSet = new Set(existing)

    const toAdd = newFeatureKeys.filter(k => !existingSet.has(k))
    if (toAdd.length === 0) return

    this.env.transactionSync(() => {
      for (const key of toAdd) {
        this.featureToEngrams.putSync(key, engramId)
        this.engramToFeatures.putSync(engramId, key)
      }
    })
  }
}
