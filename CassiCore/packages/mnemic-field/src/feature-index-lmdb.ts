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
 *   merge_tombstones    :           merged_engram_id → anchor_engram_id
 *
 * Merge-on-overlap: when a new engram's gateKnn features overlap ≥95% with
 * an existing engram, the new engram is merged into the existing one rather
 * than indexed separately. Merges union the feature sets and the caller
 * boosts the anchor engram's potentiation.
 *
 * Merge tombstones: after merging B into A, a tombstone `B → A` is written.
 * On subsequent boots, tombstones are checked BEFORE calling gateKnn, so
 * already-merged engrams are skipped instantly. This eliminates redundant
 * gateKnn calls that previously repeated every boot.
 */

import type { ILogger } from '../../../types/interfaces.js'
import type { Cortex } from './cortex.js'
import type { VindexGateKnnFn, FeatureIndexEntry } from './feature-index.js'
import { featureKey } from './feature-index.js'
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
  /** Slerped gate embedding: spherical interpolation of anchor + newcomer
   *  embeddings when both are available and a merge occurred. Null if
   *  embeddings unavailable or no merge. The caller should persist this
   *  as the anchor's new embedding via Cortex.bulkUpdateEmbeddings(). */
  slerpedEmbedding?: Float32Array | null
}

/** Feature overlap ratio ≥ this → merge instead of indexing. */
const MERGE_OVERLAP_THRESHOLD = 0.95

/** Minimum feature-count ratio (newcomer/ anchor) to reverse the merge.
 *  If the newcomer has ≥1.5× the anchor's features, it's the richer engram. */
const ANCHOR_REVERSAL_RATIO = 1.5

/** How often to yield the event loop during buildFromCortex (every N engrams). */
const BUILD_YIELD_INTERVAL = 1

/** How often to log progress during buildFromCortex (every N engrams). */
const BUILD_PROGRESS_INTERVAL = 100

export class LmdbFeatureIndex {
  private env: any              // lmdb RootDatabase
  private featureToEngrams: any // lmdb Database (dupSort)
  private engramToFeatures: any // lmdb Database (dupSort)
  private mergeTombstones: any  // lmdb Database (merged_engram_id → anchor_engram_id)
  private logger: ILogger
  private gateKnn: VindexGateKnnFn | null = null
  private ready = false
  /** Provider for gate embeddings, used by merge-on-overlap slerp. */
  private embeddingProvider: ((id: string) => Float32Array | null) | null = null

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

    this.mergeTombstones = this.env.openDB('merge_tombstones', {
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

  /** Wire the embedding provider for slerp computation during merges. */
  setEmbeddingProvider(fn: ((id: string) => Float32Array | null) | null): void {
    this.embeddingProvider = fn
  }

  /** Whether the index is ready for queries. */
  isReady(): boolean {
    return this.ready
  }

  /**
   * Check if an engram was already merged into another engram.
   * Returns the anchor engramId if a tombstone exists, null otherwise.
   */
  private getMergeTombstone(engramId: string): string | null {
    try {
      return this.mergeTombstones.get(engramId) ?? null
    } catch {
      return null
    }
  }

  /**
   * Record that an engram was merged into an anchor engram.
   * This tombstone prevents redundant gateKnn calls on subsequent boots.
   */
  private setMergeTombstone(mergedId: string, anchorId: string): void {
    try {
      this.mergeTombstones.putSync(mergedId, anchorId)
    } catch {
      // best-effort
    }
  }

  /**
   * Spherical linear interpolation between two unit-norm gate embeddings.
   * Both vectors live on S^{d-1}; slerp stays on the geodesic.
   * t ∈ [0,1]: 0 = pure a, 1 = pure b.
   */
  private slerpEmbeddings(a: Float32Array, b: Float32Array, t: number): Float32Array {
    const n = a.length
    let dot = 0
    for (let i = 0; i < n; i++) dot += a[i] * b[i]
    dot = Math.max(-1, Math.min(1, dot))
    const omega = Math.acos(dot)
    if (omega < 0.0001) return new Float32Array(a)
    const sinOmega = Math.sin(omega)
    const wA = Math.sin((1 - t) * omega) / sinOmega
    const wB = Math.sin(t * omega) / sinOmega
    const result = new Float32Array(n)
    for (let i = 0; i < n; i++) result[i] = wA * a[i] + wB * b[i]
    return result
  }

  /**
   * Index an engram from its content. Gate-KNNs the content and stores
   * feature→engramId mappings in LMDB.
   *
   * Before inserting, checks for a merge tombstone (already merged → skip)
   * and for near-complete feature overlap (≥95%) with an existing engram.
   * If overlap found, merges the feature sets and writes a tombstone so
   * future boots skip the gateKnn call entirely.
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
      /** New engram's gate embedding for slerp computation on merge. */
      embedding?: Float32Array
      /** Vindex source name — prefixed to feature keys for multi-vindex isolation. */
      source?: string
    },
  ): IndexResult {
    if (!this.ready || !this.gateKnn) return { action: 'indexed' }
    if (!content || content.length < 20) return { action: 'indexed' }

    // Check merge tombstone first — if this engram was already merged into
    // another, skip the expensive gateKnn call entirely. This tombstone
    // persists across boots, eliminating redundant warmup work.
    if (this.getMergeTombstone(engramId) !== null) {
      return { action: 'merged' }
    }

    try {
      const features = this.gateKnn(content, {
        layers: options?.layers,
        featuresPerLayer: options?.featuresPerLayer ?? 10,
        minScore: options?.minScore ?? 0.05,
      })

      if (features.length === 0) return { action: 'indexed' }

      const featureKeys = features.map(f => featureKey(f.layer, f.featureIndex, options?.source))

      // Check for near-complete overlap with an existing engram.
      const overlapping = this.findOverlappingByKeys(featureKeys, {
        limit: 1,
        minOverlapRatio: MERGE_OVERLAP_THRESHOLD,
      })
      if (overlapping.length > 0) {
        const top = overlapping[0]
        const overlapRatio = top.sharedFeatureCount / featureKeys.length
        if (overlapRatio >= MERGE_OVERLAP_THRESHOLD) {
          const anchorKeys = this.getFeatureKeys(top.engramId)
          const anchorFeatureCount = anchorKeys.length

          // Anchor quality check: if the newcomer has significantly more
          // features (1.5×), it's the richer engram — reverse the merge.
          // The old anchor is removed from the index; the newcomer absorbs it.
          if (featureKeys.length > anchorFeatureCount * ANCHOR_REVERSAL_RATIO) {
            this.removeEngram(top.engramId)
            // Union the feature sets — always merge, since the anchor may have
            // features the newcomer doesn't (even with the 1.5× ratio check).
            const allKeys = [...new Set([...featureKeys, ...anchorKeys])]
            this.insertFeatures(engramId, allKeys)
            // Move the tombstone: the old anchor is now merged into the newcomer.
            this.setMergeTombstone(top.engramId, engramId)
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
          // Record tombstone so this engram is skipped on future boots.
          this.setMergeTombstone(engramId, top.engramId)

          // Slerp gate embeddings: the anchor should reflect both engrams on the sphere.
          let slerpedEmbedding: Float32Array | undefined
          if (options?.embedding && this.embeddingProvider) {
            const anchorEmb = this.embeddingProvider(top.engramId)
            if (anchorEmb && anchorEmb.length === options.embedding.length) {
              const t = 0.3 + 0.4 * anchorFeatureCount / Math.max(anchorFeatureCount, featureKeys.length)
              slerpedEmbedding = this.slerpEmbeddings(anchorEmb, options.embedding, t)
            }
          }

          this.logger.debug?.('FeatureIndex merged engram', {
            engramId: engramId.slice(0, 12),
            into: top.engramId.slice(0, 12),
            overlapRatio: overlapRatio.toFixed(3),
            slerped: !!slerpedEmbedding,
          })
          return { action: 'merged', mergedInto: top.engramId, overlapRatio, featureCount: anchorFeatureCount, slerpedEmbedding }
        }
      }

      // No merge — store as new.
      this.removeEngram(engramId)
      this.insertFeatures(engramId, featureKeys)
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
   * Check if an already-indexed engram should be merged into another engram.
   *
   * Uses the STORED features from LMDB — no gateKnn recomputation needed.
   * Returns null if the engram isn't indexed or has no feature overlap above
   * the threshold. When a merge is triggered, union of the feature sets are
   * merged into the anchor engram, the merged engram is removed from the
   * index, and a tombstone is written. Anchor quality reversal still applies.
   *
   * This is the continuous merge-on-overlap primitive — called periodically
   * during consolidation to catch engrams that should have been merged but
   * weren't (because they were stored before their near-duplicate).
   */
  checkMergeFor(
    engramId: string,
    opts?: { minOverlapRatio?: number; embedding?: Float32Array },
  ): IndexResult | null {
    const features = this.engramToFeatures.getValues(engramId)
    if (!features) return null

    const featureList = Array.from(features) as string[]
    if (featureList.length === 0) return null

    const threshold = opts?.minOverlapRatio ?? MERGE_OVERLAP_THRESHOLD

    const overlapping = this.findOverlappingByKeys(featureList, {
      excludeId: engramId,
      limit: 1,
      minOverlapRatio: threshold,
    })

    if (overlapping.length === 0) return null

    const top = overlapping[0]
    const overlapRatio = top.sharedFeatureCount / featureList.length

    if (overlapRatio < threshold) return null

    const anchorKeys = this.getFeatureKeys(top.engramId)
    const anchorFeatureCount = anchorKeys.length

    // Anchor quality reversal: if the checked engram has ≥1.5× more
    // features than the anchor, the old anchor is removed and this
    // engram absorbs it.
    if (featureList.length > anchorFeatureCount * ANCHOR_REVERSAL_RATIO) {
      this.removeEngram(top.engramId)
      const allKeys = [...new Set([...featureList, ...anchorKeys])]
      // Re-index the richer engram with the union of both feature sets
      this.removeEngram(engramId)
      this.insertFeatures(engramId, allKeys)
      this.setMergeTombstone(top.engramId, engramId)
      this.logger.debug?.('FeatureIndex reversed merge (consolidation)', {
        engramId: engramId.slice(0, 12),
        absorbed: top.engramId.slice(0, 12),
        newFeatures: featureList.length,
        anchorFeatures: anchorFeatureCount,
        ratio: (featureList.length / anchorFeatureCount).toFixed(2),
      })
      // Return 'indexed' — caller should NOT delete this engram;
      // the old anchor should be retired instead.
      return { action: 'indexed', featureCount: featureList.length }
    }

    // Normal merge: union the feature sets into the anchor engram.
    this.mergeFeatures(top.engramId, featureList)
    this.removeEngram(engramId)
    this.setMergeTombstone(engramId, top.engramId)

    // Slerp gate embeddings: caller passes the merged engram's embedding;
    // we fetch the anchor's embedding via the getter.
    let slerpedEmbedding: Float32Array | undefined
    if (opts?.embedding && this.embeddingProvider) {
      const anchorEmb = this.embeddingProvider(top.engramId)
      if (anchorEmb && anchorEmb.length === opts.embedding.length) {
        const t = 0.3 + 0.4 * anchorFeatureCount / Math.max(anchorFeatureCount, featureList.length)
        slerpedEmbedding = this.slerpEmbeddings(anchorEmb, opts.embedding, t)
      }
    }

    this.logger.debug?.('FeatureIndex merged engram (consolidation)', {
      engramId: engramId.slice(0, 12),
      into: top.engramId.slice(0, 12),
      overlapRatio: overlapRatio.toFixed(3),
      slerped: !!slerpedEmbedding,
    })

    return {
      action: 'merged',
      mergedInto: top.engramId,
      overlapRatio,
      featureCount: anchorFeatureCount,
      slerpedEmbedding,
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
      /** Vindex source — prefixed to query keys for multi-vindex isolation. */
      source?: string
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

      const featureKeys = features.map(f => featureKey(f.layer, f.featureIndex, options?.source))
      return this.findOverlappingByKeys(featureKeys, { limit: options?.limit ?? 20 })
    } catch (err) {
      this.logger.debug?.('LmdbFeatureIndex.lookup failed', { error: String(err) })
      return []
    }
  }

  /**
   * Build the index from existing engrams in the Cortex.
   * Yields the event loop after every engram to keep the daemon responsive.
   * Logs progress periodically. Uses batched LMDB transactions for writes.
   * Skips engrams that are already indexed OR have a merge tombstone.
   */
  async buildFromCortex(
    cortex: Cortex,
    options?: {
      limit?: number
      layers?: number[]
      featuresPerLayer?: number
      minScore?: number
      /** Vindex source name — prefixed to all indexed feature keys. */
      source?: string
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
    let tombstoneSkipped = 0

    const total = engrams.length
    for (let i = 0; i < total; i++) {
      // Skip already-indexed engrams (persistent across boots via LMDB).
      if (this.engramToFeatures.get(engrams[i].id) !== undefined) {
        skipped++
        continue
      }

      // Skip engrams that were already merged into another (merge tombstone).
      if (this.getMergeTombstone(engrams[i].id) !== null) {
        tombstoneSkipped++
        continue
      }

      const result = this.indexEngram(engrams[i].id, engrams[i].content, options)
      if (result.action === 'merged') {
        merged++
      } else {
        indexed++
      }

      // Yield event loop after every engram for responsiveness
      if ((indexed + merged) % BUILD_YIELD_INTERVAL === 0) {
        await new Promise(resolve => setTimeout(resolve, 0))
      }

      // Progress logging
      if ((i + 1) % BUILD_PROGRESS_INTERVAL === 0 || i === total - 1) {
        this.logger.info('FeatureIndex warmup progress', {
          progress: `${i + 1}/${total}`,
          pct: Math.round((i + 1) / total * 100),
          indexed,
          merged,
          skipped,
          tombstoneSkipped,
        })
      }
    }

    const stats = this.stats()
    this.logger.info('LmdbFeatureIndex built from cortex', {
      scanned: total,
      indexed,
      merged,
      skipped,
      tombstoneSkipped,
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

  /** Strip a source prefix from a feature key. "gemma:L20:F6478" → "L20:F6478". */
  private stripSourcePrefix(key: string): string {
    const idx = key.indexOf(':L')
    return idx >= 0 ? key.slice(idx + 1) : key
  }

  /** Extract source prefix from a feature key. "gemma:L20:F6478" → "gemma". */
  private extractSource(key: string): string | null {
    const idx = key.indexOf(':L')
    return idx >= 0 ? key.slice(0, idx) : null
  }

  /**
   * Find engrams that share vindex features with the given engram.
   * Used for vindex_correlation synapse creation during store().
   *
   * sameSourceOnly=true (default): only matches within the same vindex source.
   *   Keys are queried as-is (prefixed), so cross-source false matches are impossible.
   * sameSourceOnly=false: for each prefixed key, queries both the prefixed key
   *   (same source) AND the bare key (any source). This discovers engrams from
   *   different vindexes that happen to share the same layer/feature indices.
   *   Use for cross-modal DreamEngine connections.
   */
  findCorrelated(
    engramId: string,
    options?: { minOverlap?: number; limit?: number; sameSourceOnly?: boolean },
  ): Array<{ engramId: string; sharedFeatureCount: number }> {
    const features = this.engramToFeatures.getValues(engramId)
    if (!features) return []

    const featureList = Array.from(features) as string[]
    if (featureList.length === 0) return []

    const minOverlap = options?.minOverlap ?? 2
    const sameSourceOnly = options?.sameSourceOnly ?? true

    // For cross-source matching, query both prefixed AND bare keys so we
    // find engrams from other sources that share the same layer/feature.
    // For same-source matching, use prefixed keys as-is.
    const queryKeys = sameSourceOnly
      ? featureList
      : [...featureList, ...featureList.map(k => this.stripSourcePrefix(k))]

    return this.findOverlappingByKeys(queryKeys, {
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
   *
   * Uses progressive early-exit: when minOverlapRatio is set (>0), tracks the
   * best overlap seen so far and short-circuits if the maximum possible overlap
   * for any engram can no longer reach the threshold. This avoids scanning all
   * feature keys when a merge is impossible — the common case for unique engrams.
   */
  private findOverlappingByKeys(
    featureKeys: string[],
    opts?: {
      excludeId?: string
      minOverlap?: number
      limit?: number
      /** If set, enables progressive early-exit with this ratio threshold. */
      minOverlapRatio?: number
    },
  ): Array<{ engramId: string; sharedFeatureCount: number }> {
    const excludeId = opts?.excludeId
    const minOverlap = opts?.minOverlap ?? 0
    const limit = opts?.limit ?? 20
    const minOverlapRatio = opts?.minOverlapRatio ?? 0

    const overlapCount = new Map<string, number>()
    let bestSeen = 0

    for (let ki = 0; ki < featureKeys.length; ki++) {
      const key = featureKeys[ki]
      const engrams = this.featureToEngrams.getValues(key)
      if (!engrams) continue
      for (const id of engrams) {
        if (id === excludeId) continue
        const count = (overlapCount.get(id) ?? 0) + 1
        overlapCount.set(id, count)
        if (count > bestSeen) bestSeen = count
      }

      // Progressive early-exit: if minOverlapRatio is set, check whether
      // any engram can still reach the threshold.  The maximum possible
      // overlap for ANY engram is bestSeen + (remaining feature keys).
      // If even that can't reach minOverlapRatio × total → no merge possible.
      if (minOverlapRatio > 0) {
        const remaining = featureKeys.length - ki - 1
        const maxPossibleRatio = (bestSeen + remaining) / featureKeys.length
        if (maxPossibleRatio < minOverlapRatio) {
          // Even the best engram can't reach the threshold — return early.
          // We already have the best candidates; filter/sort/slice what we have.
          if (minOverlap > 0 || limit < Infinity) {
            break
          }
          // If no minOverlap and no limit, we need all results — can't exit early.
          if (minOverlap === 0) continue
          break
        }
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

    this.insertFeatures(engramId, toAdd)
  }

  /**
   * Insert feature keys for an engram within a transaction.
   */
  private insertFeatures(engramId: string, featureKeys: string[]): void {
    this.env.transactionSync(() => {
      for (const key of featureKeys) {
        this.featureToEngrams.putSync(key, engramId)
        this.engramToFeatures.putSync(engramId, key)
      }
    })
  }
}
