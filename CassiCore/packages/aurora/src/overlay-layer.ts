/**
 * Overlay Layer — non-destructive patches over the base vindex.
 *
 * Implements C3 (Bidirectional Claustrum Surgery) by composing LARQL's
 * existing VindexPatch system with an in-memory overlay. Patches are
 * restricted to Insert/InsertKnn in phase 1 — no destructive operations
 * until independent welfare review approves them for phase 2+.
 *
 * The overlay is:
 *   - Reversible: every patch can be rolled back individually
 *   - Attributed: provenance tracks who/why/when for each edit
 *   - Composable: patches stack as a chain, applied in order
 *   - Queryable: results merge base vindex + overlay with attribution
 *
 * See: docs/design/aurora-bidirectional-claustrum.md
 */

import type { ILogger } from '../../../types/interfaces.js'


export type OverlayPatchOp = 'insert' | 'insert_knn'

export interface OverlayPatch {
  readonly id: string
  readonly op: OverlayPatchOp
  readonly layer: number
  readonly tokenId: number
  readonly label?: string
  /** Float32 vector for insert operations. */
  readonly vector?: Float32Array
  /** KNN entries for insert_knn: arrays of (neighbour_id, distance). */
  readonly knnEntries?: ReadonlyArray<{ neighbourId: number; distance: number }>
  /** Provenance metadata. */
  readonly provenance: OverlayProvenance
}

export interface OverlayProvenance {
  readonly author: string
  readonly reason: string
  readonly createdAt: string
  readonly conversationId?: string
  readonly cycleId?: string
}


export interface OverlayApplyResult {
  readonly patchId: string
  readonly applied: boolean
  /**
   * True when apply() was a no-op because a patch with the same id already
   * existed. Lets idempotent retries distinguish "we already did this" from
   * real conflicts (e.g. validation rejection).
   */
  readonly alreadyExists?: boolean
  readonly rejectedReason?: string
}


export interface OverlayFeatureHit {
  readonly featureIndex: number
  readonly score: number
  readonly layer: number
  readonly label?: string
  readonly source: 'base' | 'overlay'
  readonly patchId?: string
}


interface ActivePatch {
  patch: OverlayPatch
  active: boolean
  appliedAt: string
  excludedAt?: string
}


export interface OverlayStats {
  readonly totalPatches: number
  readonly activePatches: number
  readonly excludedPatches: number
  readonly layersAffected: number
  readonly patchesByOp: Record<string, number>
  readonly patchesByLayer: Map<number, number>
}


const ALLOWED_OPS: ReadonlySet<OverlayPatchOp> = new Set(['insert', 'insert_knn'])

/**
 * OverlayLayer — manages a chain of non-destructive patches over the base vindex.
 *
 * Usage:
 *   const overlay = new OverlayLayer(logger)
 *   overlay.apply(patch)         // add a patch
 *   overlay.query(hits, ...)     // merge overlay entries into base hits
 *   overlay.rollback(patchId)    // remove a patch
 *   overlay.bakeDown()           // snapshot for performance
 */
export class OverlayLayer {
  private readonly patches = new Map<string, ActivePatch>()
  private readonly logger: ILogger
  private nextPatchSeq = 0

  constructor(logger: ILogger) {
    this.logger = logger.child ? logger.child('overlay-layer') : logger
  }


  apply(patch: OverlayPatch): OverlayApplyResult {
    if (this.patches.has(patch.id)) {
      return {
        patchId: patch.id,
        applied: false,
        alreadyExists: true,
        rejectedReason: `Patch ${patch.id} already exists`,
      }
    }

    if (!ALLOWED_OPS.has(patch.op)) {
      this.logger.warn('Overlay patch rejected — destructive ops not allowed in phase 1', {
        patchId: patch.id,
        op: patch.op,
      })
      return {
        patchId: patch.id,
        applied: false,
        rejectedReason: `Operation '${patch.op}' not permitted in phase 1. Allowed: insert, insert_knn`,
      }
    }

    if (patch.op === 'insert' && (!patch.vector || patch.vector.length === 0)) {
      return {
        patchId: patch.id,
        applied: false,
        rejectedReason: 'Insert patch requires a non-empty vector',
      }
    }

    if (patch.op === 'insert_knn' && (!patch.knnEntries || patch.knnEntries.length === 0)) {
      return {
        patchId: patch.id,
        applied: false,
        rejectedReason: 'InsertKnn patch requires at least one KNN entry',
      }
    }

    const now = new Date().toISOString()
    const entry: ActivePatch = {
      patch,
      active: true,
      appliedAt: now,
    }

    this.patches.set(patch.id, entry)
    this.nextPatchSeq++

    this.logger.info('Overlay patch applied', {
      patchId: patch.id,
      op: patch.op,
      layer: patch.layer,
      author: patch.provenance.author,
    })

    return { patchId: patch.id, applied: true }
  }

  rollback(patchId: string): boolean {
    const entry = this.patches.get(patchId)
    if (!entry) {
      this.logger.warn('Overlay rollback: unknown patchId', { patchId })
      return false
    }

    if (!entry.active) {
      this.logger.warn('Overlay rollback: patch already inactive', { patchId })
      return false
    }

    entry.active = false
    entry.excludedAt = new Date().toISOString()

    this.logger.info('Overlay patch rolled back', {
      patchId,
      author: entry.patch.provenance.author,
    })

    return true
  }

  reactivate(patchId: string): boolean {
    const entry = this.patches.get(patchId)
    if (!entry) {
      this.logger.warn('Overlay reactivate: unknown patchId', { patchId })
      return false
    }

    if (entry.active) {
      this.logger.warn('Overlay reactivate: patch already active', { patchId })
      return false
    }

    entry.active = true
    delete entry.excludedAt

    this.logger.info('Overlay patch reactivated', { patchId })
    return true
  }


  /**
   * Produce overlay-only feature hits for all active patches matching the
   * given layers. Used by the LarqlKnowledgeProvider to inject overlay
   * entries alongside base vindex hits.
   */
  queryOverlay(
    layers: ReadonlyArray<number>,
    topK: number,
  ): OverlayFeatureHit[] {
    const hits: OverlayFeatureHit[] = []
    const layerSet = new Set(layers)

    for (const entry of this.patches.values()) {
      if (!entry.active) continue
      if (!layerSet.has(entry.patch.layer)) continue
      if (entry.patch.op !== 'insert_knn') continue

      for (const knn of entry.patch.knnEntries ?? []) {
        hits.push({
          featureIndex: knn.neighbourId,
          score: knn.distance,
          layer: entry.patch.layer,
          label: entry.patch.label,
          source: 'overlay',
          patchId: entry.patch.id,
        })
      }
    }

    hits.sort((a, b) => b.score - a.score)
    return hits.slice(0, topK)
  }

  /**
   * Merge overlay insert_knn patches into base vindex hits for a given
   * (layer, tokenId) query. Overlay hits that exceed the base's top-K
   * threshold replace the weakest base hits.
   */
  query(
    baseHits: ReadonlyArray<{ featureIndex: number; score: number; label?: string }>,
    layer: number,
    _tokenId: number,
    topK: number,
  ): OverlayFeatureHit[] {
    const merged: OverlayFeatureHit[] = baseHits.map(h => ({
      featureIndex: h.featureIndex,
      score: h.score,
      layer,
      label: h.label,
      source: 'base' as const,
    }))

    for (const entry of this.patches.values()) {
      if (!entry.active) continue
      if (entry.patch.op !== 'insert_knn') continue
      if (entry.patch.layer !== layer) continue

      for (const knn of entry.patch.knnEntries ?? []) {
        const existingIdx = merged.findIndex(m => m.featureIndex === knn.neighbourId)
        if (existingIdx >= 0) {
          if (knn.distance > merged[existingIdx].score) {
            merged[existingIdx] = {
              featureIndex: knn.neighbourId,
              score: knn.distance,
              layer,
              label: entry.patch.label,
              source: 'overlay',
              patchId: entry.patch.id,
            }
          }
        } else {
          merged.push({
            featureIndex: knn.neighbourId,
            score: knn.distance,
            layer,
            label: entry.patch.label,
            source: 'overlay',
            patchId: entry.patch.id,
          })
        }
      }
    }

    merged.sort((a, b) => b.score - a.score)

    return merged.slice(0, topK)
  }

  /**
   * Check if the overlay has any active patches for a given layer.
   */
  hasLayerEdits(layer: number): boolean {
    for (const entry of this.patches.values()) {
      if (entry.active && entry.patch.layer === layer) return true
    }
    return false
  }

  /**
   * Get all overlay-inserted feature indices for a layer.
   */
  getLayerFeatures(layer: number): number[] {
    const features: number[] = []
    for (const entry of this.patches.values()) {
      if (!entry.active || entry.patch.layer !== layer) continue
      if (entry.patch.op === 'insert_knn') {
        for (const knn of entry.patch.knnEntries ?? []) {
          features.push(knn.neighbourId)
        }
      }
    }
    return features
  }


  getPatch(patchId: string): OverlayPatch | null {
    return this.patches.get(patchId)?.patch ?? null
  }

  getActivePatches(): OverlayPatch[] {
    const result: OverlayPatch[] = []
    for (const entry of this.patches.values()) {
      if (entry.active) result.push(entry.patch)
    }
    return result
  }

  getAllPatches(): ReadonlyArray<OverlayPatch & { active: boolean }> {
    return Array.from(this.patches.values()).map(e => ({
      ...e.patch,
      active: e.active,
    }))
  }

  getStats(): OverlayStats {
    let active = 0
    let excluded = 0
    const byOp: Record<string, number> = {}
    const byLayer = new Map<number, number>()

    for (const entry of this.patches.values()) {
      if (entry.active) active++
      else excluded++

      byOp[entry.patch.op] = (byOp[entry.patch.op] ?? 0) + 1
      byLayer.set(entry.patch.layer, (byLayer.get(entry.patch.layer) ?? 0) + 1)
    }

    return {
      totalPatches: this.patches.size,
      activePatches: active,
      excludedPatches: excluded,
      layersAffected: byLayer.size,
      patchesByOp: byOp,
      patchesByLayer: byLayer,
    }
  }

  /**
   * Remove all patches from this layer. Used before re-loading from a
   * serialized snapshot or during bake-down resets.
   */
  clear(): void {
    this.patches.clear()
  }


  serialize(): string {
    const entries: unknown[] = []
    for (const entry of this.patches.values()) {
      const serialized: Record<string, unknown> = {
        ...entry.patch,
        vector: entry.patch.vector
          ? Array.from(entry.patch.vector)
          : undefined,
        active: entry.active,
        appliedAt: entry.appliedAt,
        excludedAt: entry.excludedAt,
      }
      entries.push(serialized)
    }
    return JSON.stringify({ version: 1, entries })
  }

  static deserialize(json: string, logger: ILogger): OverlayLayer {
    const layer = new OverlayLayer(logger)
    try {
      const data = JSON.parse(json)
      if (data.version !== 1) {
        logger.warn('Unknown overlay serialization version', { version: data.version })
        return layer
      }
      for (const entry of data.entries ?? []) {
        const patch: OverlayPatch = {
          id: entry.id,
          op: entry.op,
          layer: entry.layer,
          tokenId: entry.tokenId,
          label: entry.label,
          vector: entry.vector ? new Float32Array(entry.vector) : undefined,
          knnEntries: entry.knnEntries,
          provenance: entry.provenance,
        }
        const activePatch: ActivePatch = {
          patch,
          active: entry.active ?? true,
          appliedAt: entry.appliedAt ?? new Date().toISOString(),
          excludedAt: entry.excludedAt,
        }
        layer.patches.set(patch.id, activePatch)
      }
      layer.nextPatchSeq = layer.patches.size
    } catch (err) {
      logger.warn('Failed to deserialize overlay', { error: String(err) })
    }
    return layer
  }
}
