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

export class AttractorManager {
  state: AttractorState = {
    tonic: { r: 0, theta: 0 },
    phasic: { r: 0, theta: 0 },
    alpha: 0.85,
    sigma: 0.3,
  }

  private lastUpdateMs = Date.now()

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
function angularDelta(a: number, b: number): number {
  let d = b - a
  while (d > Math.PI) d -= 2 * Math.PI
  while (d < -Math.PI) d += 2 * Math.PI
  return d
}
