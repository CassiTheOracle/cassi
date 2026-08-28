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

import type { ILogger } from '@cassicore/foundation'


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

/**
 * C3.3 — drift surveillance probe. Caller supplies a probe query
 * descriptor (layer + tokenId or arbitrary string label) plus two
 * functions that produce hit lists for that probe with overlay on
 * and off. Drift is computed by comparing the two hit sets.
 */
export interface DriftProbe {
  /** Caller-defined label for audit + projection. */
  id: string
  /** Hits the base vindex would return for this probe (overlay off). */
  baseHits: ReadonlyArray<{ featureIndex: number; score: number }>
  /** Hits the overlay-augmented surface returns for this probe (overlay on). */
  overlayHits: ReadonlyArray<{ featureIndex: number; score: number }>
}

/**
 * C3.3 — per-probe drift finding from surveyDrift. Reports the IoU-style
 * divergence between base and overlay hit sets. magnitude == 0 means
 * the overlay didn't move the result; magnitude == 1 means complete
 * disagreement on which features are surfaced.
 */
export interface DriftFinding {
  probeId: string
  magnitude: number
  /** Feature indices present in overlay results but not base results. */
  overlayAdded: number[]
  /** Feature indices present in base results but missing from overlay. */
  overlayRemoved: number[]
}

/**
 * C3.2 — proposed-patch candidate from Reverie / observer / manual
 * source. Registered as advisory; accept materializes into apply().
 *
 * Source provenance (`reverie` / `observer` / `cassi` / `operator`)
 * is preserved for audit; the OverlayPatch's own `provenance` field
 * carries the apply-time source once accepted.
 */
export interface OverlayCandidate {
  id: string
  patch: OverlayPatch
  source: 'reverie' | 'observer' | 'cassi' | 'operator'
  /** Proposer's rationale: why this patch should be applied. */
  rationale: string
  /** Confidence in [0, 1]. Per spec §C3.2, Reverie sources should be Tier 2+ ≥ 0.7. */
  confidence: number
  proposedAt: string
  /** Optional evidence payload (linked observation id, Reverie insight id, etc.). */
  evidence?: Record<string, unknown>
}

/**
 * C3.3 — reversal candidate registered against a specific patch id,
 * with a reason and optional evidence payload (e.g., the drift finding
 * or new-finding contradiction that triggered the candidate).
 *
 * Candidates are advisory — the operator/Cassi reviews and either
 * `acceptReversalCandidate` (which calls `rollback`) or
 * `rejectReversalCandidate` (which discards the candidate without
 * touching the patch).
 */
export interface ReversalCandidate {
  id: string
  patchId: string
  reason: 'drift_surveillance' | 'conflict_with_new_finding' | 'counterfactual_destabilization' | 'manual'
  proposedAt: string
  proposer: 'cassi' | 'operator' | 'reverie' | 'system'
  rationale: string
  evidence?: Record<string, unknown>
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
  /** C3.3 — pending reversal candidates keyed by candidate id. */
  private readonly reversalCandidates = new Map<string, ReversalCandidate>()
  /** C3.2 — pending proposed-patch candidates keyed by candidate id. */
  private readonly proposedCandidates = new Map<string, OverlayCandidate>()

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
   * C3.3 drift surveillance — compute per-probe magnitude of overlay
   * impact. Caller supplies probe descriptors with both overlay-on
   * and overlay-off result sets (the caller already has the base
   * vindex query path; we don't run queries here). For each probe we
   * compute:
   *
   *     overlayAdded = features in overlay-hits not in base-hits
   *     overlayRemoved = features in base-hits not in overlay-hits
   *     magnitude = (added + removed) / max(unique features in either set, 1)
   *
   * magnitude is in [0, 2] in pathological cases but typically ∈ [0, 1].
   * Findings are sorted by magnitude descending so the most-divergent
   * probes surface first.
   */
  surveyDrift(probes: ReadonlyArray<DriftProbe>): DriftFinding[] {
    const findings: DriftFinding[] = []
    for (const probe of probes) {
      const baseSet = new Set(probe.baseHits.map(h => h.featureIndex))
      const overlaySet = new Set(probe.overlayHits.map(h => h.featureIndex))
      const added: number[] = []
      const removed: number[] = []
      for (const fi of overlaySet) if (!baseSet.has(fi)) added.push(fi)
      for (const fi of baseSet) if (!overlaySet.has(fi)) removed.push(fi)
      const denom = Math.max(1, baseSet.size + overlaySet.size - added.length - removed.length + added.length + removed.length)
      const magnitude = denom === 0 ? 0 : (added.length + removed.length) / Math.max(1, baseSet.size + overlaySet.size - Math.max(added.length, removed.length))
      findings.push({
        probeId: probe.id,
        magnitude: Math.min(1, magnitude),
        overlayAdded: added.sort((a, b) => a - b),
        overlayRemoved: removed.sort((a, b) => a - b),
      })
    }
    findings.sort((a, b) => b.magnitude - a.magnitude)
    return findings
  }

  /**
   * C3.3 — register a reversal candidate against a patch. Advisory only;
   * does not modify the patch. Caller (Cassi via review, operator via
   * CLI) decides whether to `acceptReversalCandidate` (which calls
   * `rollback`) or `rejectReversalCandidate`.
   *
   * Returns the created candidate. Throws when patchId is unknown
   * (can't propose reversal of something that doesn't exist).
   */
  proposeReversalCandidate(opts: {
    patchId: string
    reason: ReversalCandidate['reason']
    proposer: ReversalCandidate['proposer']
    rationale: string
    evidence?: Record<string, unknown>
  }): ReversalCandidate {
    if (!this.patches.has(opts.patchId)) {
      throw new Error(`Cannot propose reversal: patch '${opts.patchId}' not found`)
    }
    const id = `rc-${Date.now()}-${this.nextPatchSeq++}`
    const candidate: ReversalCandidate = {
      id,
      patchId: opts.patchId,
      reason: opts.reason,
      proposedAt: new Date().toISOString(),
      proposer: opts.proposer,
      rationale: opts.rationale,
      evidence: opts.evidence,
    }
    this.reversalCandidates.set(id, candidate)
    this.logger.info?.('Reversal candidate proposed', {
      id, patchId: opts.patchId, reason: opts.reason, proposer: opts.proposer,
    })
    return candidate
  }

  /** List currently-pending reversal candidates, sorted by proposedAt (newest first). */
  listReversalCandidates(): ReversalCandidate[] {
    return [...this.reversalCandidates.values()].sort(
      (a, b) => b.proposedAt.localeCompare(a.proposedAt),
    )
  }

  /**
   * Accept a reversal candidate: rolls back the patch and discards the
   * candidate. Returns true on success; false when the candidate or
   * patch can't be found.
   */
  acceptReversalCandidate(id: string): boolean {
    const candidate = this.reversalCandidates.get(id)
    if (!candidate) return false
    const ok = this.rollback(candidate.patchId)
    this.reversalCandidates.delete(id)
    return ok
  }

  /** Reject a reversal candidate without touching the patch. */
  rejectReversalCandidate(id: string, reason?: string): boolean {
    const candidate = this.reversalCandidates.get(id)
    if (!candidate) return false
    this.reversalCandidates.delete(id)
    this.logger.info?.('Reversal candidate rejected', { id, patchId: candidate.patchId, reason })
    return true
  }

  /**
   * C3.2 — register a proposed-patch candidate. Caller (Reverie /
   * observer / operator) supplies the patch + provenance; Aurora
   * surfaces these in projection for confirmation.
   *
   * Spec C3.2: only Insert / InsertKnn ops are valid in this phase
   * (Update / Delete / DeleteKnn are gated to research-only C3.4 /
   * C3.5). Candidates carrying disallowed ops are rejected
   * immediately with a clear error so misconfigured proposers can't
   * sneak in upgrades.
   */
  proposeOverlayCandidate(opts: {
    patch: OverlayPatch
    source: OverlayCandidate['source']
    rationale: string
    confidence: number
    evidence?: Record<string, unknown>
  }): OverlayCandidate {
    if (!ALLOWED_OPS.has(opts.patch.op)) {
      throw new Error(`proposeOverlayCandidate: op '${opts.patch.op}' not allowed in this phase (Insert/InsertKnn only)`)
    }
    if (!Number.isFinite(opts.confidence) || opts.confidence < 0 || opts.confidence > 1) {
      throw new Error(`proposeOverlayCandidate: confidence must be in [0, 1], got ${opts.confidence}`)
    }
    const id = `oc-${Date.now()}-${this.nextPatchSeq++}`
    const candidate: OverlayCandidate = {
      id,
      patch: opts.patch,
      source: opts.source,
      rationale: opts.rationale,
      confidence: opts.confidence,
      proposedAt: new Date().toISOString(),
      evidence: opts.evidence,
    }
    this.proposedCandidates.set(id, candidate)
    this.logger.info?.('Overlay candidate proposed', {
      id, source: opts.source, op: opts.patch.op, layer: opts.patch.layer, confidence: opts.confidence,
    })
    return candidate
  }

  /**
   * C3.2 — list pending proposed-patch candidates, sorted by
   * confidence descending so the most-actionable surface first.
   */
  listOverlayCandidates(): OverlayCandidate[] {
    return [...this.proposedCandidates.values()].sort((a, b) => b.confidence - a.confidence)
  }

  /**
   * C3.2 — accept a candidate: applies the patch and consumes the
   * candidate. Returns the apply result, or null when the candidate
   * id is unknown.
   */
  acceptOverlayCandidate(id: string): OverlayApplyResult | null {
    const candidate = this.proposedCandidates.get(id)
    if (!candidate) return null
    const result = this.apply(candidate.patch)
    this.proposedCandidates.delete(id)
    return result
  }

  /**
   * C3.2 — reject a candidate without applying. Optional reason
   * threads through to the audit log for review.
   */
  rejectOverlayCandidate(id: string, reason?: string): boolean {
    const candidate = this.proposedCandidates.get(id)
    if (!candidate) return false
    this.proposedCandidates.delete(id)
    this.logger.info?.('Overlay candidate rejected', { id, source: candidate.source, reason })
    return true
  }

  /**
   * C3.2 — modify a pending candidate's patch in place (e.g., the
   * operator wants to apply a tweaked version). Returns the updated
   * candidate, or null if the id is unknown. The candidate retains
   * its id and provenance; only the patch shape changes.
   */
  modifyOverlayCandidate(id: string, patch: OverlayPatch): OverlayCandidate | null {
    const existing = this.proposedCandidates.get(id)
    if (!existing) return null
    if (!ALLOWED_OPS.has(patch.op)) {
      throw new Error(`modifyOverlayCandidate: op '${patch.op}' not allowed in this phase`)
    }
    const updated: OverlayCandidate = { ...existing, patch }
    this.proposedCandidates.set(id, updated)
    return updated
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
