/**
 * SpatialAttentionMapper — maps model attention patterns to field sectors.
 *
 * During a vindexForward pass with captureAttention=true, the model produces
 * per-head attention weight matrices. This class maps those attention weights
 * to feature activations, then to engram positions in the mnemic field,
 * accumulating into 12 angular sector buckets (30° each).
 *
 * The result is a sectorAttention[] array where each element [0,1] represents
 * the model's attention intensity in that angular sector. High values =
 * sectors the model is currently "looking at." Low values = neglected sectors.
 *
 * Also provides computeFromFeatureActivations() as a lighter alternative
 * when per-head attention data isn't available but feature activation
 * counts are.
 */

import type { ILogger } from '../../../types/interfaces.js'
import { DEFAULT_SECTOR_COUNT } from './attractor.js'

export interface SectorAttentionResult {
  /** 12-element array [0→1], index = sector 0-11. */
  sectors: number[]
  /** Total attention heads aggregated. */
  heads: number
  /** Total features mapped. */
  featuresMapped: number
  /** Total engrams looked up. */
  engramsLookedUp: number
  /** Duration in ms. */
  durationMs: number
  /** Layer used for attention capture. */
  layer: number
}

export class SpatialAttentionMapper {
  private logger: ILogger

  constructor(logger: ILogger) {
    this.logger = logger.child?.('spatial-attention') ?? logger
  }

  /**
   * Map attention patterns to sector weights.
   *
   * @param attention — Per-head attention weights from vindexForward
   * @param featureToEngrams — FeatureKey → engramId[] map (from LMDB FeatureIndex)
   * @param engramPositions — EngramId → { theta, r } map (from Cortex)
   * @param numHeads — Number of attention heads in the layer (unused, reserved)
   * @param layer — Layer used for capture
   */
  mapAttentionToSectors(
    attention: number[][],
    featureToEngrams: Map<string, string[]>,
    engramPositions: Map<string, { theta: number; r: number }>,
    _numHeads: number,
    layer: number,
  ): SectorAttentionResult | null {
    const start = performance.now()

    if (!attention || attention.length === 0) return null

    const buckets = new Array<number>(DEFAULT_SECTOR_COUNT).fill(0)
    let featuresMapped = 0
    let engramsLookedUp = 0

    // For each attention head, weight feature activations by attention
    // and accumulate into sector buckets via engram positions.
    for (const headAttn of attention) {
      const headSum = headAttn.reduce((s, v) => s + v, 0)
      if (headSum === 0) continue

      // For each token's attention, accumulate sector contributions
      for (const tokenWeight of headAttn) {
        const normalizedWeight = tokenWeight / headSum
        if (normalizedWeight < 0.01) continue

        featuresMapped++

        for (const [, engramIds] of featureToEngrams) {
          for (const eid of engramIds) {
            const pos = engramPositions.get(eid)
            if (!pos) continue
            engramsLookedUp++
            const sector = this.thetaToSector(pos.theta)
            buckets[sector] += normalizedWeight
          }
        }
      }
    }

    // Normalize
    const maxBucket = Math.max(...buckets, 0.001)
    const sectors = buckets.map(b => b / maxBucket)

    const durationMs = performance.now() - start

    this.logger.debug('Spatial attention mapped', {
      sectors: sectors.map(s => s.toFixed(3)),
      heads: attention.length,
      featuresMapped,
      engramsLookedUp,
      durationMs: Math.round(durationMs),
    })

    return {
      sectors,
      heads: attention.length,
      featuresMapped,
      engramsLookedUp,
      durationMs,
      layer,
    }
  }

  /** Map theta in radians to sector index 0-11. */
  thetaToSector(theta: number): number {
    let normalized = theta % (2 * Math.PI)
    if (normalized < 0) normalized += 2 * Math.PI
    const sectorSize = (2 * Math.PI) / DEFAULT_SECTOR_COUNT
    return Math.min(DEFAULT_SECTOR_COUNT - 1, Math.floor(normalized / sectorSize))
  }

  /**
   * Compute sector attention from pre-computed per-feature activation counts.
   *
   * Lighter alternative — use when per-head attention data isn't available.
   * Each featureKey maps to engramIds; activation counts aggregate per sector.
   */
  computeFromFeatureActivations(
    featureActivations: Map<string, number>,
    featureToEngrams: Map<string, string[]>,
    engramPositions: Map<string, { theta: number; r: number }>,
  ): number[] {
    const buckets = new Array<number>(DEFAULT_SECTOR_COUNT).fill(0)

    for (const [featureKey, activationCount] of featureActivations) {
      const engramIds = featureToEngrams.get(featureKey)
      if (!engramIds) continue

      for (const eid of engramIds) {
        const pos = engramPositions.get(eid)
        if (!pos) continue
        const sector = this.thetaToSector(pos.theta)
        buckets[sector] += activationCount
      }
    }

    const maxBucket = Math.max(...buckets, 0.001)
    return buckets.map(b => b / maxBucket)
  }
}
