import { describe, expect, it } from 'vitest'

import {
  PHI,
  PARITY_TOLERANCE,
  cascadeRung,
  windingDelta,
  windingParity,
  coherenceBudget,
  coherenceCost,
  mergeCompatible,
} from './index.js'

import type { RungParity } from './index.js'

/**
 * Stage-3-structural core — cascade-tier math (plan §20, pre-registered A/B,
 * NOT wired). These are pure-math invariants pinned to the cassi-toe theory
 * docs; every number below is hand-computed from the cited formulas (see the
 * doc comments in index.ts for the source sections). No production path calls
 * these functions; the tests pin the math so an adopted wiring cannot drift.
 */

/** Planted field states → (rho = EY+EI, eps0 = EY − φ·EI), the operand map. */
function state(ey: number, ei: number): { rho: number; eps0: number } {
  return { rho: ey + ei, eps0: ey - PHI * ei }
}

describe('cascadeRung — rung placement (dimensionful-cascade.md §2)', () => {
  it('assigns n = log_φ(scale/anchor) and the doc fractional-part δn', () => {
    // n = log_φ(scale/anchor)
    expect(cascadeRung(1, 1).n).toBeCloseTo(0, 12)
    expect(cascadeRung(PHI, 1).n).toBeCloseTo(1, 12)
    expect(cascadeRung(PHI ** 3.27, 1).n).toBeCloseTo(3.27, 12)
    // δn = n − ⌊n⌋ (qi-flow-double-helix.md, "Deviations from φ-powers")
    const r = cascadeRung(PHI ** 3.27, 1)
    expect(r.deltaN).toBeCloseTo(0.27, 12)
  })

  it('classifies parity exactly on planted integer / half / unaligned rungs', () => {
    expect(cascadeRung(1, 1).parity).toBe('integer') // n=0
    expect(cascadeRung(PHI, 1).parity).toBe('integer') // n=1
    expect(cascadeRung(PHI ** 1.9, 1).parity).toBe('integer') // n=1.9 → wraps to rung-2 closure
    expect(cascadeRung(Math.sqrt(PHI), 1).parity).toBe('half') // n=0.5 crossing
    expect(cascadeRung(PHI ** 3.27, 1).parity).toBe('unaligned') // δn=0.27 in the gap
    expect(cascadeRung(PHI ** 0.75, 1).parity).toBe('unaligned') // δn=0.75 in the gap
  })

  it('the tolerance is pinned to atan(φ)/2π and never silently widened', () => {
    // The tolerance constant is EXACTLY the theory's |δn| ≤ atan(φ)/2π bound.
    expect(PARITY_TOLERANCE).toBeCloseTo(Math.atan(PHI) / (2 * Math.PI), 12)
    // Classify with comfortable interiors, away from the float round-trip
    // n = log(φ^δn)/log(φ) reintroduces (~1e-16) noise ON the exact boundary,
    // so we assert margins, not the boundary point itself.
    for (const [deltaN, parity] of [
      [0.10, 'integer'], // 0.10 < τ → stable closure
      [0.20, 'unaligned'], // τ < 0.20 < 0.338 (the gap)
      [0.30, 'unaligned'], // gap interior (τ < 0.30 < 0.5−τ ≈ 0.338)
      [0.45, 'half'], // within [0.5−τ, 0.5+τ] → crossing
      [0.55, 'half'],
      [0.70, 'unaligned'], // 0.662 < 0.70 < 0.838 (the gap)
      [0.90, 'integer'], // 0.90 > 1−τ → wraps to the next rung closure
    ] as Array<[number, RungParity]>) {
      expect(cascadeRung(PHI ** deltaN, 1).parity).toBe(parity)
    }
  })

  it('documents degenerate scales honestly (NaN n/δn, unaligned)', () => {
    for (const bad of [0, -1, -PHI, NaN, Infinity]) {
      const r = cascadeRung(bad, 1)
      expect(Number.isNaN(r.n)).toBe(true)
      expect(Number.isNaN(r.deltaN)).toBe(true)
      expect(r.parity).toBe('unaligned')
    }
    for (const bad of [0, -1, NaN, Infinity]) {
      const r = cascadeRung(1, bad)
      expect(Number.isNaN(r.n)).toBe(true)
      expect(r.parity).toBe('unaligned')
    }
  })
})

describe('windingDelta — relaxation winding (qi-flow-double-helix.md)', () => {
  it('matches the hand-computed formula for planted (rho, eps0) values', () => {
    // The formula: Δϑ = atan(1/φ) − atan((ρ−ε₀)/(ρφ+ε₀)), computed via atan2.
    // Values hand-computed in double precision.
    const cases: Array<[number, number, number]> = [
      // ρ, ε₀, expected Δϑ (rad)
      [1 + 1 / PHI, 0, 0], // attractor EY=1,EI=1/φ → ε₀=0 → winds nothing
      [2, 1 - PHI, -0.231823805], // symmetric EY=EI=1 → e0=1−φ<0
      [1.5, 0.5 - PHI, -0.553574359], // yin-heavy EY=0.5,EI=1 → the theory's −atan(1/φ)
      [1.5, 1.5, 0.553574359], // ε₀=ρ → numerator 0 → the theory's +atan(1/φ)
    ]
    for (const [rho, e0, expected] of cases) {
      expect(windingDelta(rho, e0)).toBeCloseTo(expected, 6)
    }
  })

  it('recovers the theory extremes at the physical bounds', () => {
    // +atan(φ⁻¹) ≈ +0.5536 and −atan(φ) ≈ −1.0172 (qi-flow table, Winding bounds)
    expect(windingDelta(1.5, 1.5)).toBeCloseTo(Math.atan(1 / PHI), 9)
    expect(windingDelta(1, -PHI)).toBeCloseTo(-Math.atan(PHI), 9) // denominator-zero limit
  })

  it('documents degenerate domain honestly (ρ ≤ 0 → NaN; denominator zero is a limit)', () => {
    expect(Number.isNaN(windingDelta(0, 1))).toBe(true) // ρ=0: no charge magnitude
    expect(Number.isNaN(windingDelta(-1, 1))).toBe(true)
    expect(Number.isNaN(windingDelta(NaN, 1))).toBe(true)
    expect(Number.isNaN(windingDelta(1, NaN))).toBe(true)
    // ρφ+ε₀ = 0 is a genuine limiting value (atan2 → ∓π/2), not a NaN fudge:
    expect(Number.isNaN(windingDelta(2, -2 * PHI))).toBe(false)
  })

  it('consistency: the operable map (EY,EI)→(ρ,ε₀) matches the field engine eps', () => {
    // engine: eps = ey - PHI*ei (cassi_mind_engine.gd compute_state). At the
    // φ-attractor EY=φ·EI the state winds nothing (ε₀=0, Δϑ=0).
    const a = state(1.0, 1 / PHI)
    expect(a.eps0).toBeCloseTo(0, 9)
    expect(windingDelta(a.rho, a.eps0)).toBeCloseTo(0, 9)
  })
})

describe('windingParity — parity of the winding angle', () => {
  it('classifies planted angles at integer / half / unaligned offsets', () => {
    expect(windingParity(0)).toBe('integer') // settled at a closure
    expect(windingParity(Math.atan(1 / PHI))).toBe('integer') // max relaxation, still stable
    expect(windingParity(Math.PI)).toBe('half') // full half-rung advance → crossing
    expect(windingParity(-Math.PI)).toBe('half')
    // halfway in rung terms between 0 and 0.5 → unaligned (e.g. offset 0.25 → π/2 rad)
    expect(windingParity(Math.PI / 2)).toBe('unaligned')
  })

  it('is consistent with cascadeRung on the same fractional offset', () => {
    const offsetToTheta = (deltaN: number) => deltaN * 2 * Math.PI
    for (const deltaN of [0, 0.5, 0.9, 0.27]) {
      const viaWinding = windingParity(offsetToTheta(deltaN))
      const viaRung = cascadeRung(PHI ** deltaN, 1).parity
      expect(viaWinding).toBe(viaRung as RungParity)
    }
  })

  it('documents degenerate input as unaligned (NaN)', () => {
    expect(windingParity(NaN)).toBe('unaligned')
    expect(windingParity(Infinity)).toBe('unaligned')
  })
})

describe('coherenceBudget — capacity law (cascade-suppression-formula.md §1.3)', () => {
  it('matches the doc law φ^(−n(n+1)/2 − δ(n+1)), δ=3, on hand-computed examples', () => {
    // Hand-computed: exponent = −(n(n+1)/2 + 3(n+1)):
    //   n=0 → φ^−3 ≈ 0.236068;  n=1 → φ^−7 ≈ 0.034442;  n=2 → φ^−12 ≈ 0.003106
    expect(coherenceCost(0)).toBeCloseTo(PHI ** -3, 9)
    expect(coherenceCost(1)).toBeCloseTo(PHI ** -7, 9)
    expect(coherenceCost(2)).toBeCloseTo(PHI ** -12, 9)
    // One engram at depth 0 and one at depth 2 → φ^−3 + φ^−12 (the doc's law summed).
    const b = coherenceBudget([1, 0, 1])
    expect(b.cost).toBeCloseTo(PHI ** -3 + PHI ** -12, 9)
    expect(b.capacity).toBe(1)
    expect(b.withinBudget).toBe(true)
  })

  it('is monotone in occupancy (same-rung histogram growth raises cost)', () => {
    // Monotone in OCCUPANCY: more engrams at the same rung depth → higher cost.
    // Note the capacity law is NOT monotone across DEPTHS: a shallow (rung-0)
    // engram costs φ^−3 ≈ 0.24, while a deep (rung-2) engram costs only
    // 2·φ^−12 ≈ 0.006 — rungs near Planck are far more coherent (φ^−i−δ ≪ φ^−1),
    // so deeper engrams are CHEAPER. We assert same-rung growth only.
    const empty = coherenceBudget([])
    const one = coherenceBudget([1])
    const two = coherenceBudget([2])
    const plus = coherenceBudget([1, 1]) // two engrams, both at rung 0
    expect(one.cost).toBeGreaterThan(empty.cost)
    expect(two.cost).toBeGreaterThan(one.cost) // same rung 0: 2× φ^−3 > 1× φ^−3
    expect(plus.cost).toBeGreaterThan(one.cost) // rung 0 and rung 1 both occupied
    expect(two.cost).toBeCloseTo(2 * coherenceCost(0), 9)
    expect(plus.cost).toBeCloseTo(coherenceCost(0) + coherenceCost(1), 9)
  })

  it('handles documented degenerate inputs (negative/NaN counts → NaN cost, not within budget)', () => {
    expect(coherenceBudget([]).withinBudget).toBe(true)
    expect(coherenceBudget([1, -1]).cost).toBeNaN()
    expect(coherenceBudget([1, -1]).withinBudget).toBe(false)
    expect(coherenceBudget([1, NaN]).withinBudget).toBe(false)
  })
})

describe('mergeCompatible — winding-based merge gate (no diffing)', () => {
  const closed = state(1.0, 1 / PHI) // ε₀=0 → Δϑ=0 → integer (stable closure)
  const open_ = state(1.0, 1.0) // small relaxation winding, still integer
  // An over-excess operand (very positive ε₀ > ρ) winds to the +π/4 asymptote:
  // Δϑ→atan(1/φ)+π/4≈1.339 rad ⇒ offset ≈0.213 rungs (τ=0.162). Valid (ρ>0)
  // but not a stable closure → gate must reject.
  const unsettled = { rho: 1.0, eps0: 1e12 }
  expect(windingParity(windingDelta(unsettled.rho, unsettled.eps0))).toBe('unaligned')

  it('is deterministic, symmetric, and reflexive on stable states', () => {
    expect(mergeCompatible(closed, open_)).toBe(mergeCompatible(open_, closed)) // symmetric
    expect(windingParity(windingDelta(closed.rho, closed.eps0))).toBe('integer')
    expect(mergeCompatible(closed, closed)).toBe(true) // reflexive (integer × integer)
    expect(mergeCompatible(open_, open_)).toBe(true)
  })

  it('merges only integer-parity (stable-closure) pairs', () => {
    expect(mergeCompatible(closed, open_)).toBe(true)
  })

  it('the parity map pins the half (crossing) class, which the gate rejects', () => {
    // Reliability note (honest, theory-grounded): the relaxation-winding
    // formula Δϑ = atan(1/φ) − atan((ρ−ε₀)/(ρφ+ε₀)) is bounded on the whole
    // operand domain — for ρ>0 and ε₀ any real, Δϑ ∈ [atan(1/φ)−3π/4,
    // atan(1/φ)+π/4] ≈ [−1.803, 1.339] rad ⇒ rung offset ∈ [−0.287, 0.213],
    // which NEVER reaches the half-rung crossing at Δϑ=π. (For the physical
    // nonneg-charge domain ε₀∈[−ρφ,ρ] the range is the theory's own
    // [−atan(φ), atan(1/φ)] ≈ [−1.017, 0.554] rad ⇒ offset [−0.162, 0.088].)
    // This is the theory's own statement ("relaxation winding can never
    // produce a half-step"; qi-flow-double-helix.md). So a HALF-parity operand
    // is unreachable through windingDelta. The gate's rejection of the
    // crossing class is nevertheless pinned two ways:
    //  (a) the parity MAP itself classifies the nominal crossing angle π as
    //      'half' (the sine/crossing class "seats sector edges");
    //  (b) mergeCompatible is a strict conjunction of integer-parity checks,
    //      so any non-integer parity (half or unaligned) blocks the merge —
    //      exercised concretely with the reachable unaligned over-excess case.
    expect(windingParity(Math.PI)).toBe('half') // the nominal half-rung crossing
    expect(windingParity(-Math.PI)).toBe('half')
    expect(mergeCompatible(unsettled, closed)).toBe(false) // unaligned blocks
    expect(mergeCompatible(closed, unsettled)).toBe(false)
    expect(mergeCompatible(unsettled, unsettled)).toBe(false)
    expect(mergeCompatible(unsettled, unsettled)).toBe(mergeCompatible(unsettled, closed)) // both reject
  })

  it('is a pure function of the two operands (no state, no I/O)', () => {
    const ab = mergeCompatible(closed, open_)
    const ba = mergeCompatible(open_, closed)
    const again = mergeCompatible(closed, open_)
    expect(ab).toBe(again) // deterministic across calls
    expect(ab).toBe(ba) // order-invariant
  })
})
