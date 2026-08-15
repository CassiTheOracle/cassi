/**
 * Stage-3-structural core of the Cassi Mind program: cascade-tier math.
 *
 * This module is PURE MATH ONLY — no I/O, no state, no logger calls, no
 * wiring into brain behavior. It exists so the "memory as field" layer
 * (cascade rung placement, winding arithmetic, coherence-budget capacity,
 * winding-based merge compatibility) can be pinned and tested in isolation
 * BEFORE any pre-registered A/B decides whether to adopt it.
 *
 * No-op-by-construction is the Stage-3 parity law: `cascadeRung`,
 * `windingDelta`, `windingParity`, `coherenceBudget`, and `mergeCompatible`
 * are NOT referenced by any production path. Wiring happens ONLY if the
 * pre-registered Stage 3-structural A/B (plan §20) adopts. These functions
 * are observable only to callers that import them explicitly.
 *
 * All formulas are pinned to the CassiTheory theory docs (READ-ONLY ground
 * truth). Every doc citation below is to `C:\Users\Carina\workspaces\Cassi\CassiTheory\foundations\...`; the section numbers are the docs' own headings.
 */

/** Golden ratio, the theory's one structural constant (φ = (1+√5)/2). */
export const PHI = 1.618033988749895;

/**
 * The integer/half parity tolerance, in rung units.
 *
 * Pinned from the relaxation-winding bound in
 * `CassiTheory/foundations/qi-flow-double-helix.md`, "The shared φ-powers"
 * table (Winding bounds row) and §2.6 of `cassi-first-principles.md` (via
 * the double-helix doc's "Deviations from φ-powers" section):
 *
 *   "|δn| ≤ atan(φ)/2π ≈ 0.162"
 *
 * A state relaxing toward the φ-line sweeps a bounded internal angle Δϑ and
 * can displace at most |δn| = |Δϑ|/(2π) rungs from its integer closure. That
 * 0.162 rung-window is the width of the "stable closure" (integer) parity
 * class AS GIVEN by the theory — we do NOT widen it, and we reuse the SAME
 * magnitude for the half-rung "crossing" tolerance (a symmetric application
 * of the theory's single symmetry-breaking bound; the two classes are
 * "separated by a factor of three in rung units" — 0.162 and 3·0.162 ≈ 0.5 —
 * so 0.162-wide windows around 0 and 0.5 never overlap, leaving a genuine
 * "unaligned" gap).
 */
export const PARITY_TOLERANCE = Math.atan(PHI) / (2 * Math.PI);

/** Parity classes: an integer rung is a stable closure; a half-rung is a crossing. */
export type RungParity = 'integer' | 'half' | 'unaligned';

/** `cascadeRung` result: the base-φ exponent and its fractional offset. */
export interface RungPlacement {
  /** n = log_φ(scale/anchor) — the (possibly fractional) cascade rung. */
  n: number;
  /** δn = n − ⌊n⌋, the doublet's phase-bookkeeping fractional offset. */
  deltaN: number;
  /** parity of the placement (integer = stable closure, half = crossing). */
  parity: RungParity;
}

/**
 * Assign a scale to a cascade rung relative to an anchor scale.
 *
 * Formula pinned from `CassiTheory/foundations/dimensionful-cascade.md` §2:
 *
 *   "n = ln(ℓ/ℓ_Pl)/ln φ = log_φ(ℓ/ℓ_Pl)"
 *
 * which generalizes to any anchor: n = log_φ(scale/anchor).
 *
 * δn follows the theory's OWN convention (NOT n − round(n)), from
 * `qi-flow-double-helix.md`, "Deviations from φ-powers":
 *
 *   "the fractional offsets δn = n − ⌊n⌋ are the doublet's phase bookkeeping"
 *
 * and the same doc's parity partition:
 *
 *   "A half-rung offset (δn ≈ 0.5) is one full π-advance of the density-plane
 *    angle ... the sine mode (crossing; antinode at the half-rung) seats
 *    sector edges, the cosine mode (bubble; antinode at the integer rungs)
 *    seats interior stable states."
 *
 * So the parity classes are:
 *   - `integer` (cosine/bubble, stable closure): δn within `PARITY_TOLERANCE`
 *     of an integer (0 or 1 — the fractional part wraps; a state at n=1.95 is
 *     relaxation-adjacent to the rung 2 closure, not to rung 1).
 *   - `half` (sine/crossing): δn within `PARITY_TOLERANCE` of 0.5.
 *   - `unaligned`: neither — a fractional offset in the gap between the two
 *     separation classes (relaxation winding can never reach a half-step).
 *
 * Domain: anchor must be a positive scale; scale must be positive. log_φ of a
 * non-positive argument is undefined → this returns NaN n / NaN δn / `unaligned`
 * for scale ≤ 0. anchor ≤ 0 likewise (NaN). This is explicit and documented;
 * no silent clamp.
 */
export function cascadeRung(scale: number, anchor: number): RungPlacement {
  if (!Number.isFinite(scale) || !Number.isFinite(anchor) || scale <= 0 || anchor <= 0) {
    return { n: NaN, deltaN: NaN, parity: 'unaligned' };
  }
  const n = Math.log(scale / anchor) / Math.log(PHI);
  const deltaN = n - Math.floor(n); // fractional part, per the doc convention
  return { n, deltaN, parity: classifyFractionalOffset(deltaN) };
}

/**
 * Map a fractional rung offset δn (the doc's n − ⌊n⌋, in [0,1)) to a parity.
 *
 * Centralizes the parity partition so `cascadeRung` and `windingParity` share
 * one convention. Classification rule (derivation in `PARITY_TOLERANCE`):
 * integer = within τ of 0 or 1 (the wraparound closure), half = within τ of
 * 0.5, else unaligned — τ = atan(φ)/2π, the theory's own |δn| ≤ 0.162 bound.
 */
export function classifyFractionalOffset(deltaN: number): RungParity {
  if (!Number.isFinite(deltaN)) return 'unaligned';
  const d = deltaN - Math.floor(deltaN);
  const tau = PARITY_TOLERANCE;
  if (d <= tau || d >= 1 - tau) return 'integer';
  if (Math.abs(d - 0.5) <= tau) return 'half';
  return 'unaligned';
}

/**
 * The relaxation-winding angle Δϑ for a field state.
 *
 * Formula pinned EXACTLY from `CassiTheory/foundations/qi-flow-double-helix.md`,
 * "Deviations from φ-powers" → "Relaxation winding" (boxed equation):
 *
 *   Δϑ = atan(1/φ) − atan((ρ − ε₀)/(ρφ + ε₀)),
 *
 * independent of λ and of the gate shape, "with ρ conserved the total
 * winding is a function of ε₀ alone". We compute atan((ρ−ε₀)/(ρφ+ε₀)) via
 * the two-argument form atan2(ρ−ε₀, ρφ+ε₀), which is equal to the one-form
 * for every denominator ≠ 0 and gives the honest limiting value ±π/2 when
 * the denominator is exactly 0 (see below) — no silent fudge.
 *
 * OPERAND MAP (OUR assignment — plan §7 Q2 "the ring algebra is invariant;
 * the assignment is ours"): for a field cell with Yang charge EY and Yin
 * charge EI,
 *   - ρ = EY + EI  (charge magnitude; qi-flow-double-helix.md §1: "ρ =
 *     Ψ₀²+Ψ₁² = R²"),
 *   - ε₀ = EY − φ·EI (closure residual).
 * This is EXACTLY the departure the field engine already computes: the
 * space-sim fork's `cassi_mind_engine.gd` `compute_state`/`compute_readout`
 * set `eps = ey[i] - PHI*ei[i]` with `PHI = 1.618033988749895` — the same φ
 * and the same residual. So ρ/ε₀ are the natural field-space operands and
 * need no remapping. At the φ-attractor EY = φ·EI (cascade-suppression-
 * formula.md §1.1 "Any departure from the φ-equilibrium (E_Y ≠ φ E_I)"),
 * ε₀ = 0 ⇒ (ρ−0)/(ρφ+0) = 1/φ ⇒ Δϑ = atan(1/φ) − atan(1/φ) = 0: a settled
 * state winds nothing, consistent with the doc's "the rate vanishes exactly
 * on the φ-line (ε = 0)".
 *
 * Domain (honestly documented, no silent sentinel fudge):
 *   - ρ > 0 required — ρ is a charge-density magnitude and the identity is
 *     derived under conserved positive ρ. ρ ≤ 0 (e.g. an empty cell) is a
 *     degenerate state where the winding identity does NOT apply → returns NaN.
 *   - ε₀ is any real.
 *   - ρφ + ε₀ = 0 (denominator zero): argument → ±∞, so atan → ∓π/2, a
 *     genuine limiting value; atan2 recovers it exactly. For example ρ=1,
 *     ε₀=−φ gives Δϑ = atan(1/φ) − π/2 = −atan(φ) ≈ −1.017 rad — precisely
 *     the theory's −atan(φ) extreme. This is the documented behavior, not a
 *     clamped value.
 *
 * The returned angle is the RAW formula value; we do not clamp. Its range over
 * the whole operand domain (rho > 0, eps0 any real) is
 * Δϑ ∈ [atan(1/φ)−3π/4, atan(1/φ)+π/4] ≈ [−1.803, +1.339] rad: eps0 → −∞ puts
 * (ρφ+ε₀, ρ−ε₀) in quadrant II (atan2 → +3π/4, the −1.803 end), eps0 → +∞ in
 * quadrant IV (atan2 → −π/4, the +1.339 end). The theory's own range
 * [−atan(φ), +atan(φ⁻¹)] ≈ [−1.017, +0.554] rad describes the PHYSICAL inputs
 * ε₀ ∝ EY−φEI with nonneg charges (EY,EI ≥ 0 ⇒ ε₀ ∈ [−ρφ, ρ]). A caller that
 * feeds operands outside the physical charge interval gets the honest formula
 * output (still bounded above at +1.339, never reaching the ±π half-rung
 * crossing) and can classify it independently.
 */
export function windingDelta(rho: number, eps0: number): number {
  if (!Number.isFinite(rho) || !Number.isFinite(eps0) || rho <= 0) return NaN;
  return Math.atan2(1, PHI) - Math.atan2(rho - eps0, rho * PHI + eps0);
}

/**
 * Parity of a relaxation-winding angle Δϑ.
 *
 * The theory maps winding angle to rung offset by dividing by 2π — one rung
 * of phase is 2π (qi-flow-double-helix.md "Matter as wound Qi": "with θ =
 * atan2(E_I, E_Y) the density-plane angle (one cascade rung advances θ by
 * 2π)"). So the implied rung offset of a winding angle Δϑ is Δϑ/(2π), and we
 * classify that offset with the SAME fractional-offset rule as `cascadeRung`
 * (see `classifyFractionalOffset` and `PARITY_TOLERANCE`):
 *
 *   - `integer` (stable closure): the winding keeps the state within
 *     atan(φ) rad of an integer-rung closure — this is the whole reachable
 *     relaxation range, since the doc states |δn| ≤ atan(φ)/2π and
 *     "relaxation winding can never produce a half-step".
 *   - `half` (crossing): |Δϑ − π| (or |Δϑ + π|) ≤ atan(φ) rad — a full half-
 *     rung phase advance, the sine/crossing class that "seats sector edges".
 *   - `unaligned`: anywhere between the two settled classes.
 *
 * Consistency with `cascadeRung`: both feed the same offset classifier, so a
 * winding angle that implies a half-rung offset is exactly the crossing
 * class, and a relaxation-compatible angle is the integer/stable class.
 */
export function windingParity(deltaTheta: number): RungParity {
  if (!Number.isFinite(deltaTheta)) return 'unaligned';
  const offset = deltaTheta / (2 * Math.PI);
  return classifyFractionalOffset(offset);
}

/** Result of the coherence-budget capacity check. */
export interface CoherenceBudget {
  /** Total coherence cost of the collection (see `coherenceBudget`). */
  cost: number;
  /** The unit coherence budget the collection is measured against. */
  capacity: number;
  /** True when cost ≤ capacity (the collection fits the field's budget). */
  withinBudget: boolean;
}

const COHERENCE_DELTA = 3; // δ = 3 from σ = ℓ_Pl/φ³ (cascade-suppression-formula.md §1.1)

/**
 * Per-engram coherence cost for a memory spanning/valued at rung depth n.
 *
 * Pinned from `CassiTheory/foundations/cascade-suppression-formula.md` §1.3
 * (Coherence maintenance), the boxed total-failure/suppression law:
 *
 *   D(0→n) = ∏_{i=0}^{n} (1−q_i) = φ^(−n(n+1)/2 − δ(n+1))
 *
 * with "δ = 3 (from σ = ℓ_Pl/φ³)". This is the fraction of the field's unit
 * coherence an engram at depth n must command to keep its whole span
 * simultaneously coherent. The plan §2 quotes the leading φ^(−N(N+1)/2)
 * term; the doc's exact law carries the −δ(n+1) refinement, and we use the
 * doc's exact exponent (δ = 3).
 */
export function coherenceCost(depth: number): number {
  if (!Number.isFinite(depth) || depth < 0) return NaN;
  const exponent = -(depth * (depth + 1)) / 2 - COHERENCE_DELTA * (depth + 1);
  return PHI ** exponent;
}

/**
 * Total coherence cost and capacity for a set of engrams indexed by rung.
 *
 * `rungCounts` is a histogram: rungCounts[i] = how many engrams sit at cascade
 * rung depth i (i ≥ 0). `cost` = Σ_i rungCounts[i] · coherenceCost(i) — each
 * engram draws its per-depth coherence fraction out of the field's budget.
 * `capacity` = 1 (the unit total-coherence budget: the field cannot hold more
 * than all of its coherence). `withinBudget` = cost ≤ capacity.
 *
 * This is the honest operationalization of the capacity law into a budget —
 * the plan's open-question precedent (plan §7 Q2) applies: the law is pinned
 * to the doc, the mapping (rung depth → per-engram coherence fraction, unit
 * capacity) is our assignment, documented here. Because every per-depth cost
 * is a deep suppression fraction (φ^−…≪1), real engram sets essentially never
 * exceed capacity — which is the theory's own statement that coherence
 * maintenance is astronomically cheap until depths get extreme, not a gate we
 * tuned.
 *
 * Edge cases (documented): a negative histogram entry is an invalid count →
 * the contribution is undefined → cost becomes NaN and withinBudget is false
 * (no silent pass); an empty array → cost 0, withinBudget true.
 */
export function coherenceBudget(rungCounts: number[]): CoherenceBudget {
  const capacity = 1;
  if (!Array.isArray(rungCounts) || rungCounts.length === 0) {
    return { cost: 0, capacity, withinBudget: true };
  }
  let cost = 0;
  for (let i = 0; i < rungCounts.length; i++) {
    const count = rungCounts[i];
    if (!Number.isFinite(count) || count < 0) return { cost: NaN, capacity, withinBudget: false };
    const per = coherenceCost(i);
    if (Number.isNaN(per)) return { cost: NaN, capacity, withinBudget: false };
    cost += count * per;
  }
  return { cost, capacity, withinBudget: cost <= capacity };
}

/**
 * Winding-parity merge compatibility for two field states.
 *
 * Operationalizes the theory's parity partition as a version-compatibility
 * gate: the field computes merge compatibility as PHASE BOOKKEEPING, no
 * diffing. A merge is allowed only between two states that are both in the
 * stable-closure (integer) parity — the cosine/bubble class that "seats
 * interior stable states". If either operand is in the crossing (half) class
 * — the sine mode that "seats sector edges", an inherently unstable position
 * — the pair never merges.
 *
 *   mergeCompatible(a, b) = windingParity(a) === 'integer'
 *                        && windingParity(b) === 'integer',
 *
 * where each operand's parity comes from its own winding angle
 * windingDelta(rho, eps0). Deterministic (pure function of the two operands),
 * symmetric (logical AND is order-independent), and reflexive on the natural
 * domain: an integer-parity state is compatible with itself.
 *
 * Reliability note (honest; the theory's own statement): the relaxation-winding
 * formula windingDelta is BOUNDED on the whole operand domain — for rho > 0 and
 * eps0 any real, as eps0 → −∞ the point (ρφ+ε₀, ρ−ε₀) → (−∞, +∞) so
 * atan2 → +3π/4 (Δϑ → atan(1/φ) − 3π/4 ≈ −1.803 rad), and as eps0 → +∞ the
 * point → (+∞, −∞) so atan2 → −π/4 (Δϑ → atan(1/φ) + π/4 ≈ +1.339 rad). Hence
 * Δϑ ∈ [atan(1/φ)−3π/4, atan(1/φ)+π/4] ≈ [−1.803, +1.339] rad, i.e. rung
 * offset ∈ [−0.287, +0.213], which NEVER reaches the half-rung crossing class
 * at Δϑ=π (qi-flow-double-helix.md: "relaxation winding can never produce a
 * half-step"). For the PHYSICAL operand domain (nonneg charges EY,EI ≥ 0 ⇒
 * eps0 = EY−φ·EI ∈ [−ρφ, ρ]) the range is the theory's own
 * [−atan(φ), +atan(1/φ)] ≈ [−1.017, +0.554] rad, offset [−0.162, +0.088] —
 * entirely within the 'integer' window. So a physically relaxed operand is
 * always 'integer' — a settled state is a stable closure and merges — and the
 * gate is match-permissive for settled states, exactly "stable closure →
 * compatible". The crossing (half) class is a POSITIONAL class realized by
 * half-rung placement (cascadeRung on scale=φ^(k+0.5)), not by relaxation. The
 * gate nevertheless rejects ANY operand whose winding parity is non-integer
 * (half or unaligned) by its strict conjunction; an operand with |eps0| ≫ ρ
 * (excess far outside the physical charge interval) winds into the unaligned
 * gap on either side (offset ≈ −0.287 or +0.213) and is rejected. This is the
 * honest operationalization of "the field computes version compatibility as
 * phase bookkeeping, no diffing": the gate is a phase check on each operand,
 * not a content diff.
 */
export function mergeCompatible(
  a: { rho: number; eps0: number },
  b: { rho: number; eps0: number },
): boolean {
  return windingParity(windingDelta(a.rho, a.eps0)) === 'integer' &&
    windingParity(windingDelta(b.rho, b.eps0)) === 'integer';
}
