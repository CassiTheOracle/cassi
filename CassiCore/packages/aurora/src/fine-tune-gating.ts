/**
 * Fine-Tune Gating — selects engrams that have earned a place in permanent model memory.
 *
 * Only engrams at r < 0.1 (near the tonic center) with high potentiation (> 0.7)
 * are candidates for fine-tuning back into the model. This ensures only well-reinforced,
 * high-confidence knowledge becomes part of the LLM's weight-space memory.
 */

import type { MnemicField } from '../mnemic-field/index.js'
import type { Engram } from '../mnemic-field/types.js'

export interface FineTuneCandidate {
  engram: Engram
  /** Radial distance from center — lower = more central, more trusted */
  r: number
  /** Angular position */
  theta: number
}

/**
 * Return engrams near the tonic center (r < 0.1) with high potentiation (> 0.7).
 * These are the engrams that have consistently been reinforced, drifted inward
 * through consolidation, and now represent well-earned knowledge.
 */
export function getFineTuningCandidates(
  field: MnemicField,
  limit: number = 100,
): FineTuneCandidate[] {
  const candidates: FineTuneCandidate[] = []

  // Query engrams with potentiation above threshold
  const highPotentiation = field.list(limit * 10).filter(
    e => e.potentiation >= 0.7
  )

  for (const engram of highPotentiation) {
    // Filter by radial distance: r < 0.1
    const r = computeR(engram)
    if (r >= 0.1) continue

    const theta = (engram.metadata as any)?.theta as number | undefined
      ?? Math.atan2(engram.y, engram.x)

    candidates.push({ engram, r, theta })
  }

  // Sort by r ascending (closest to center first), then potentiation descending
  candidates.sort((a, b) => {
    if (Math.abs(a.r - b.r) > 0.001) return a.r - b.r
    return b.engram.potentiation - a.engram.potentiation
  })

  return candidates.slice(0, limit)
}

/** Compute radial distance from x/y or metadata. */
function computeR(engram: Engram): number {
  const metaR = (engram.metadata as any)?.r as number | undefined
  if (metaR !== undefined) return metaR
  return Math.sqrt(engram.x * engram.x + engram.y * engram.y)
}
