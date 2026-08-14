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
import { assignCell, globalCellKey } from './healpix.js'
import { open as lmdbOpen } from 'lmdb'

/** Return type for indexEngram — tells the caller whether to store or merge. */
export interface IndexResult {
  action: 'indexed' | 'merged' | 'skipped'
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
  /** Reason for skip — e.g. 'not_ready', 'content_too_short', 'gateknn_error'. */
  skipReason?: string
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
  private engramsByCell: any    // lmdb Database (dupSort): cell_key → engram_id
  private engramsByPosition: any // lmdb Database: engram_id → position BLOB
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

    // Position-index databases for spherical spatial queries (V1).
    this.engramsByCell = this.env.openDB('engrams_by_cell', {
      dupSort: true,
      keyEncoding: 'ordered-binary',
      encoding: 'string',
    })

    this.engramsByPosition = this.env.openDB('engrams_by_position', {
      keyEncoding: 'ordered-binary',
      encoding: 'binary',
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
   * Core merge execution — shared by indexEngram and checkMergeFor.
   *
   * Handles anchor quality reversal, feature-set union, tombstone write,
   * and slerp computation. Callers provide the newcomer's feature keys and
   * the anchor engram's ID + feature count.
   */
  private executeMerge(
    newcomerId: string,
    newcomerFeatureKeys: string[],
    anchorId: string,
    anchorFeatureCount: number,
    opts: {
      /** If true, also removes the anchor from the index (reversal case). */
      reverseAnchor?: boolean
      /** If true, removes the newcomer from the index (consolidation case). */
      removeNewcomer?: boolean
      /** Gate embedding for slerp. */
      embedding?: Float32Array
      /** Label for debug log context. */
      debugLabel?: string
    } = {},
  ): IndexResult {
    const anchorKeys = this.getFeatureKeys(anchorId)

    if (opts.reverseAnchor) {
      // Anchor quality reversal: newcomer has ≥1.5× the features.
      // The old anchor is removed; the newcomer absorbs its features.
      this.removeEngram(anchorId)
      const allKeys = [...new Set([...newcomerFeatureKeys, ...anchorKeys])]
      if (opts.removeNewcomer) this.removeEngram(newcomerId)
      this.insertFeatures(newcomerId, allKeys)
      this.setMergeTombstone(anchorId, newcomerId)
      this.logger.debug?.(`FeatureIndex reversed merge${opts.debugLabel ? ` (${opts.debugLabel})` : ''}`, {
        engramId: newcomerId.slice(0, 12),
        absorbed: anchorId.slice(0, 12),
        newFeatures: newcomerFeatureKeys.length,
        anchorFeatures: anchorFeatureCount,
        ratio: (newcomerFeatureKeys.length / anchorFeatureCount).toFixed(2),
      })
      return { action: 'indexed' }
    }

    // Normal merge: union the feature sets into the anchor engram.
    this.mergeFeatures(anchorId, newcomerFeatureKeys)
    if (opts.removeNewcomer) this.removeEngram(newcomerId)
    this.setMergeTombstone(newcomerId, anchorId)

    // Slerp gate embeddings: the anchor should reflect both engrams on the sphere.
    let slerpedEmbedding: Float32Array | undefined
    if (opts.embedding && this.embeddingProvider) {
      const anchorEmb = this.embeddingProvider(anchorId)
      if (anchorEmb && anchorEmb.length === opts.embedding.length) {
        const t = 0.3 + 0.4 * anchorFeatureCount / Math.max(anchorFeatureCount, newcomerFeatureKeys.length)
        slerpedEmbedding = this.slerpEmbeddings(anchorEmb, opts.embedding, t)
      }
    }

    this.logger.debug?.(`FeatureIndex merged engram${opts.debugLabel ? ` (${opts.debugLabel})` : ''}`, {
      engramId: newcomerId.slice(0, 12),
      into: anchorId.slice(0, 12),
      slerped: !!slerpedEmbedding,
    })

    return {
      action: 'merged',
      mergedInto: anchorId,
      featureCount: anchorFeatureCount,
      slerpedEmbedding,
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
    if (!this.ready || !this.gateKnn) return { action: 'skipped', skipReason: 'not_ready' }
    if (!content || content.length < 20) return { action: 'skipped', skipReason: 'content_too_short' }

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

      if (features.length === 0) return { action: 'skipped', skipReason: 'no_features' }

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
          const reverseAnchor = featureKeys.length > anchorFeatureCount * ANCHOR_REVERSAL_RATIO

          return this.executeMerge(engramId, featureKeys, top.engramId, anchorFeatureCount, {
            reverseAnchor,
            embedding: options?.embedding,
          })
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
      return { action: 'skipped', skipReason: 'gateknn_error' }
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
    const reverseAnchor = featureList.length > anchorFeatureCount * ANCHOR_REVERSAL_RATIO

    return this.executeMerge(engramId, featureList, top.engramId, anchorFeatureCount, {
      reverseAnchor,
      removeNewcomer: true,
      embedding: opts?.embedding,
      debugLabel: 'consolidation',
    })
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
   * Logs progress periodically. Skips engrams that are already indexed OR
   * have a merge tombstone.
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
    let errorSkipped = 0

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
      } else if (result.action === 'skipped') {
        errorSkipped++
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
          errorSkipped,
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
      errorSkipped,
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
   * Progressive early-exit: when minOverlapRatio is set (>0), tracks the
   * best overlap seen so far and short-circuits if the maximum possible
   * overlap for any engram can no longer reach the threshold. Additionally,
   * when limit=1 and a qualifying engram is already found, exits early
   * since the caller only needs one merge candidate.
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

      // Progressive early-exit when a merge threshold is configured.
      if (minOverlapRatio > 0) {
        const remaining = featureKeys.length - ki - 1
        const maxPossibleRatio = (bestSeen + remaining) / featureKeys.length

        // Short-circuit: even the best engram can't reach the threshold.
        if (maxPossibleRatio < minOverlapRatio) break

        // Short-circuit: caller only needs one result, and we already have
        // a qualifying engram (≥ threshold). No need to find a better one.
        if (limit === 1 && bestSeen / featureKeys.length >= minOverlapRatio) break
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

  // Position-index (V1: Spherical Coordinate System)

  /** Write an engram's spherical position and cell membership. */
  writePosition(
    engramId: string,
    r: number,
    theta: number,
    phi: number,
    embedding?: Float32Array | null,
  ): void {
    // Remove old cell mapping if this engram already had a position.
    const oldPos = this.getPosition(engramId)
    if (oldPos && (Math.abs(oldPos.r - r) > 0.01 || Math.abs(oldPos.theta - theta) > 0.01 || Math.abs(oldPos.phi - phi) > 0.01)) {
      const oldCell = assignCell(oldPos.r, oldPos.theta, oldPos.phi)
      const oldKey = globalCellKey(oldCell.shell, oldCell.cell)
      this.engramsByCell.remove(oldKey, engramId)
    }

    const cell = assignCell(r, theta, phi)
    const cellKey = globalCellKey(cell.shell, cell.cell)
    this.engramsByCell.put(cellKey, engramId)

    const hasEmb = embedding && embedding.length > 0 ? 1 : 0
    const blobSize = 12 + 1 + (hasEmb ? embedding!.length * 4 : 0)
    const blob = Buffer.alloc(blobSize)
    blob.writeFloatLE(r, 0)
    blob.writeFloatLE(theta, 4)
    blob.writeFloatLE(phi, 8)
    blob.writeUInt8(hasEmb, 12)
    if (hasEmb && embedding) {
      for (let i = 0; i < embedding.length; i++) {
        blob.writeFloatLE(embedding[i]!, 13 + i * 4)
      }
    }
    this.engramsByPosition.put(engramId, blob)
  }

  /** Read an engram's spherical position. */
  getPosition(engramId: string): { r: number; theta: number; phi: number; embedding?: Float32Array } | null {
    const blob = this.engramsByPosition.get(engramId) as Buffer | undefined
    if (!blob || blob.length < 12) return null
    const r = blob.readFloatLE(0)
    const theta = blob.readFloatLE(4)
    const phi = blob.readFloatLE(8)
    const hasEmb = blob.length > 12 ? blob.readUInt8(12) : 0
    let embedding: Float32Array | undefined
    if (hasEmb && blob.length >= 13) {
      const dim = (blob.length - 13) / 4
      if (dim > 0 && Number.isInteger(dim)) {
        embedding = new Float32Array(dim)
        for (let i = 0; i < dim; i++) {
          embedding[i] = blob.readFloatLE(13 + i * 4)
        }
      }
    }
    return { r, theta, phi, embedding }
  }

  /** Fast path: read only spherical coordinates, skip embedding parse. */
  private getPositionCoords(engramId: string): { r: number; theta: number; phi: number } | null {
    const blob = this.engramsByPosition.get(engramId) as Buffer | undefined
    if (!blob || blob.length < 12) return null
    return {
      r: blob.readFloatLE(0),
      theta: blob.readFloatLE(4),
      phi: blob.readFloatLE(8),
    }
  }

  /** Get engram IDs in a cell. */
  engramsInCell(shell: number, cell: number): string[] {
    const cellKey = String.fromCharCode(shell) +
      String.fromCharCode((cell >> 24) & 0xFF) +
      String.fromCharCode((cell >> 16) & 0xFF) +
      String.fromCharCode((cell >> 8) & 0xFF) +
      String.fromCharCode(cell & 0xFF)
    const ids: string[] = []
    for (const id of this.engramsByCell.getValues(cellKey) ?? []) {
      ids.push(id as string)
    }
    return ids
  }

  /** Batch lookup: engrams in multiple cells. */
  engramsInCells(cellKeys: string[]): string[] {
    const ids: string[] = []
    for (const key of cellKeys) {
      for (const id of this.engramsByCell.getValues(key) ?? []) {
        ids.push(id as string)
      }
    }
    return ids
  }

  /** Nearest engrams by spherical position using cell-based bucketing. */
  nearestByPosition(
    r: number, theta: number, phi: number,
    maxResults: number = 20, radius: number = 0.3,
  ): Array<{ engramId: string; distance: number }> {
    const shell = r < 0.1 ? 0 : r < 0.3 ? 1 : r < 0.6 ? 2 : 3
    const nside = [1, 2, 4, 8][shell]!
    const candidateIds = new Set<string>()
    for (const ds of [-1, 0, 1]) {
      const s = shell + ds
      if (s < 0 || s > 3) continue
      const ns = [1, 2, 4, 8][s]!
      const dPhi = (radius * Math.PI) / ns
      const dTheta = (radius * 2 * Math.PI) / ns
      const ringMin = Math.max(0, Math.floor((phi - dPhi) / Math.PI * 4 * ns))
      const ringMax = Math.min(4 * ns - 1, Math.ceil((phi + dPhi) / Math.PI * 4 * ns))
      for (let ri = ringMin; ri <= ringMax; ri++) {
        const midR = (4 * ns) >> 1
        const cellsInRing = ri <= midR
          ? Math.max(4, 4 * (ri + 1))
          : Math.max(4, 4 * (4 * ns - ri))
        const cellMin = Math.floor(((theta - dTheta) % (2 * Math.PI) + 2 * Math.PI) / (2 * Math.PI) * cellsInRing)
        const cellMax = Math.ceil(((theta + dTheta) % (2 * Math.PI) + 2 * Math.PI) / (2 * Math.PI) * cellsInRing)
        let baseCell = 0
        for (let rj = 0; rj < ri; rj++) {
          const count = rj <= midR
            ? Math.max(4, 4 * (rj + 1))
            : Math.max(4, 4 * (4 * ns - rj))
          baseCell += count
        }
        for (let ci = cellMin; ci <= cellMax; ci++) {
          const ck = String.fromCharCode(s) +
            String.fromCharCode((baseCell + (ci % cellsInRing) >> 24) & 0xFF) +
            String.fromCharCode((baseCell + (ci % cellsInRing) >> 16) & 0xFF) +
            String.fromCharCode((baseCell + (ci % cellsInRing) >> 8) & 0xFF) +
            String.fromCharCode((baseCell + (ci % cellsInRing)) & 0xFF)
          candidateIds.add(ck)
        }
      }
    }

    const results: Array<{ engramId: string; distance: number }> = []
    for (const ck of candidateIds) {
      for (const id of this.engramsByCell.getValues(ck) ?? []) {
        const pos = this.getPositionCoords(id as string)
        if (!pos) continue
        const dr = r - pos.r
        const dTheta = Math.abs(theta - pos.theta)
        const minDTheta = Math.min(dTheta, 2 * Math.PI - dTheta)
        const arcDist = (r + pos.r) * 0.5 * minDTheta
        const dPhi = phi - pos.phi
        const dz = (r + pos.r) * 0.5 * dPhi
        const distance = Math.sqrt(dr * dr + arcDist * arcDist + dz * dz)
        if (distance <= radius) results.push({ engramId: id as string, distance })
      }
    }
    results.sort((a, b) => a.distance - b.distance)
    return results.slice(0, maxResults)
  }

  /** Remove position data for an engram. */
  removePosition(engramId: string): void {
    this.engramsByPosition.remove(engramId)
  }

  /** Position-index stats. */
  positionStats(): { cellCount: number; positionCount: number } {
    let cellCount = 0, positionCount = 0
    for (const _ of this.engramsByCell.getKeys() ?? []) cellCount++
    for (const _ of this.engramsByPosition.getKeys() ?? []) positionCount++
    return { cellCount, positionCount }
  }
}
