/**
 * AttractorManager — tracks the field's attentional focus in polar coordinates.
 *
 * Tonic center: fixed at (0,0) — the Pineal's identity facets.
 * Phasic attractor: shifts based on recent retrieval patterns.
 * Alpha: blend ratio (1.0 = pure tonic, 0.0 = pure phasic).
 * Sigma: attentional spread (small = tight focus, large = broad).
 */

export interface AttractorState {
  tonic: { r: number; theta: number }
  phasic: { r: number; theta: number }
  alpha: number
  sigma: number
}

const TONIC_HALF_LIFE_MS = 5 * 60 * 1000  // 5 minutes
const MAX_POSITION_HISTORY = 100          // ring buffer size
export const DEFAULT_SECTOR_COUNT = 12    // 30° each

export class AttractorManager {
  state: AttractorState = {
    tonic: { r: 0, theta: 0 },
    phasic: { r: 0, theta: 0 },
    alpha: 0.85,
    sigma: 0.3,
  }

  private lastUpdateMs = Date.now()

  // Position history ring buffer — tracks recent phasic attractor positions
  // for shadow observation (which sectors has the system been visiting?).
  private positionHistory: Array<{ r: number; theta: number; ts: number }> = []

  /** Record the current phasic position as a visit. Called after each retrieval. */
  recordVisit(r?: number, theta?: number): void {
    this.positionHistory.push({
      r: r ?? this.state.phasic.r,
      theta: theta ?? this.state.phasic.theta,
      ts: Date.now(),
    })
    if (this.positionHistory.length > MAX_POSITION_HISTORY) {
      this.positionHistory = this.positionHistory.slice(-MAX_POSITION_HISTORY)
    }
  }

  /** Return recent position history (newest last). */
  getPositionHistory(): Array<{ r: number; theta: number; ts: number }> {
    return this.positionHistory
  }

  /** Compute which angular sectors have been visited. 12 sectors at 30° each. */
  getSectorCoverage(sectorCount: number = DEFAULT_SECTOR_COUNT): Set<number> {
    const visited = new Set<number>()
    const secSize = (2 * Math.PI) / sectorCount
    for (const pos of this.positionHistory) {
      const sector = Math.floor(normalizeTheta(pos.theta) / secSize) % sectorCount
      visited.add(sector)
    }
    return visited
  }

  /** How many visits to a specific sector index? */
  getSectorVisitCount(sectorCount: number = DEFAULT_SECTOR_COUNT): Map<number, number> {
    const counts = new Map<number, number>()
    const secSize = (2 * Math.PI) / sectorCount
    for (const pos of this.positionHistory) {
      const sector = Math.floor(normalizeTheta(pos.theta) / secSize) % sectorCount
      counts.set(sector, (counts.get(sector) ?? 0) + 1)
    }
    return counts
  }

  /**
   * Yin phase (Phase 4): gently nudge the phasic attractor toward the
   * least-visited sector that has engrams in it. This is the system
   * "acknowledging" neglected regions of the field — not forcing retrieval,
   * just tilting attention slightly so shadows become visible.
   *
   * @param sectorDensity Map of sector index → engram count (from MnemicField)
   * @param sectorCount Number of sectors (default 12)
   * @returns The sector index nudged toward, or -1 if nothing to nudge
   */
  attractorYinPhase(
    sectorDensity: Map<number, number>,
    sectorCount: number = DEFAULT_SECTOR_COUNT,
  ): number {
    if (this.positionHistory.length === 0) return -1
    if (sectorDensity.size === 0) return -1

    const visitCounts = this.getSectorVisitCount(sectorCount)

    // Find the least-visited sector among those with engrams
    let leastVisited = -1
    let minVisits = Infinity
    for (const [sector, engramCount] of sectorDensity) {
      if (engramCount === 0) continue
      const visits = visitCounts.get(sector) ?? 0
      if (visits < minVisits) {
        minVisits = visits
        leastVisited = sector
      }
    }

    if (leastVisited < 0) return -1
    if (minVisits > 10) return -1  // all sectors well-visited, nothing to nudge

    // Nudge phasic attractor theta toward the neglected sector's center
    const targetTheta = normalizeTheta((leastVisited + 0.5) * SECTOR_SIZE)
    const nudgeRate = 0.05  // weak force — acknowledgment, not compulsion
    this.state.phasic.theta += nudgeRate * angularDelta(this.state.phasic.theta, targetTheta)

    // Also nudge r slightly outward to broaden attention scope
    this.state.phasic.r = Math.min(1.0, this.state.phasic.r + 0.01)

    // Update timestamp so decay doesn't immediately undo the nudge
    this.lastUpdateMs = Date.now()
    return leastVisited
  }

  /** Weighted distance from an engram to the combined attractor. */
  effectiveDistance(engramR: number, engramTheta: number): number {
    const dTonic = polarDistance(engramR, engramTheta, this.state.tonic.r, this.state.tonic.theta)
    const dPhasic = polarDistance(engramR, engramTheta, this.state.phasic.r, this.state.phasic.theta)
    return this.state.alpha * dTonic + (1 - this.state.alpha) * dPhasic
  }

  /** Radial boost factor: higher for engrams near the attractor. */
  radialBoost(engramR: number, engramTheta: number): number {
    const d = this.effectiveDistance(engramR, engramTheta)
    return Math.exp(-d / this.state.sigma)
  }

  /** Update phasic attractor toward the charge-weighted centroid of a luminal set. */
  updateFromLuminal(
    engrams: Array<{ r?: number; theta?: number; charge: number }>,
  ): void {
    if (engrams.length === 0) return

    let totalCharge = 0
    let weightedR = 0
    let sinSum = 0
    let cosSum = 0

    for (const e of engrams) {
      const r = e.r ?? 0.5
      const theta = e.theta ?? 0
      const w = e.charge
      weightedR += r * w
      sinSum += Math.sin(theta) * w
      cosSum += Math.cos(theta) * w
      totalCharge += w
    }

    if (totalCharge === 0) return

    const centroidR = weightedR / totalCharge
    const centroidTheta = Math.atan2(sinSum, cosSum)

    // Nudge phasic attractor toward centroid
    const nudgeRate = 0.3
    this.state.phasic.r += nudgeRate * (centroidR - this.state.phasic.r)
    this.state.phasic.theta += nudgeRate * angularDelta(this.state.phasic.theta, centroidTheta)

    // Lower alpha when phasic is far from tonic (system is focused on something specific)
    const dPhasic = polarDistance(
      this.state.phasic.r, this.state.phasic.theta,
      this.state.tonic.r, this.state.tonic.theta,
    )
    this.state.alpha = Math.max(0.3, 1.0 - dPhasic * 0.8)

    this.lastUpdateMs = Date.now()

    // Record this attractor position for shadow observation (Phase 0: Yin/Yang)
    this.recordVisit(this.state.phasic.r, this.state.phasic.theta)
  }

  /** Decay phasic attractor toward tonic center over time. */
  decay(nowMs: number = Date.now()): void {
    const dtMs = nowMs - this.lastUpdateMs
    if (dtMs <= 0) return

    const decayRate = 1 - Math.exp(-Math.LN2 * dtMs / TONIC_HALF_LIFE_MS)

    // Radial decay toward 0
    this.state.phasic.r *= (1 - decayRate)
    // Angular decay toward tonic theta (0)
    this.state.phasic.theta = this.state.phasic.theta * (1 - decayRate) + 0 * decayRate
    // Alpha returns toward 1.0 (pure tonic)
    this.state.alpha = Math.min(1.0, this.state.alpha + decayRate * 0.1)

    this.lastUpdateMs = nowMs
  }
}

/** Polar distance between two points. */
function polarDistance(r1: number, t1: number, r2: number, t2: number): number {
  const dx = r1 * Math.cos(t1) - r2 * Math.cos(t2)
  const dy = r1 * Math.sin(t1) - r2 * Math.sin(t2)
  return Math.sqrt(dx * dx + dy * dy)
}

/** Shortest angular difference in radians, wrapped to [-π, π]. */
export function angularDelta(a: number, b: number): number {
  let d = b - a
  while (d > Math.PI) d -= 2 * Math.PI
  while (d < -Math.PI) d += 2 * Math.PI
  return d
}

/** Normalize an angle to [0, 2π). */
export function normalizeTheta(theta: number): number {
  let t = theta
  while (t < 0) t += 2 * Math.PI
  while (t >= 2 * Math.PI) t -= 2 * Math.PI
  return t
}

/** 30° in radians (one 12-sector slice). */
export const SECTOR_SIZE = (2 * Math.PI) / DEFAULT_SECTOR_COUNT
