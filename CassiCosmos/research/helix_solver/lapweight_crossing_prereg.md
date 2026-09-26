# Lap-Weight Degeneracy Crossing Curve — PRE-REGISTRATION (U2)

**Status:** Pre-registration — written BEFORE any computation. Governs the probe
`lapweight_crossing_probe.py`.
**Date:** 2026-08-16 · **Workstream:** U2 — unification hypothesis
**Commit anchor:** wave-8 verified stencil weights `b62778d`; this line's
provenance work `oblate_provenance_audit.md` (27ad20f), `oblate_claim_map.md`
(15db3c8), provenance notes (0ff22d7).

---

## 0. Question

For the family of boxes `h = (φ, 1, s)` (the sim's cell sizes, one free
aspect-ratio parameter `s` along the z/string axis), does the axial Laplacian
coefficient `az(s)` cross zero near `s = φ² ≈ 2.618`? If `az` has **exactly one
sign change** and the root `s*` lies in `[φ²·0.9, φ²·1.1] = [2.356, 2.880]`, the
engine's default box aspect `(φ,1,φ²)` sits **at the operator's critical
manifold**: elliptic on the z-axis for `s < φ²`, anti-diffusive for `s > φ²`,
marginal exactly at `(φ,1,φ²)`.

This is a **pure analytic/coefficient scan** on the wave-8 `lap_weights` formula
— no PDE, no Godot, no engine run. It tests whether the default box aspect is a
**derived degeneracy** of the anisotropic Laplacian rather than an arbitrary
choice.

## 1. The exact formula (copied from source; upstream is unmodified)

The probe imports `lap_weights` from `research/helix_solver/triaxial3d.py`
(module-level, importable). The formula, verbatim from `triaxial3d.py:37-48`:

```python
def lap_weights(h):
    """The shader's per-axis and face-diagonal weights for cell sizes h=(hx,hy,hz).
    ...
    h02 = min(h)^2;  b_xy = (1/3) h02/(hx^2+hy^2);  ... ;  a_x = h02/hx^2 - 2(b_xy+b_xz).
    """
    hx, hy, hz = h
    h02 = min(h) ** 2
    bxy = (1.0 / 3.0) * h02 / (hx * hx + hy * hy)
    bxz = (1.0 / 3.0) * h02 / (hx * hx + hz * hz)
    byz = (1.0 / 3.0) * h02 / (hy * hy + hz * hz)
    ax = h02 / (hx * hx) - 2.0 * (bxy + bxz)
    ay = h02 / (hy * hy) - 2.0 * (bxy + byz)
    az = h02 / (hz * hz) - 2.0 * (bxz + byz)
    return ax, ay, az, bxy, bxz, byz
```

Return order `(ax, ay, az, bxy, bxz, byz)`; `h = (hx, hy, hz)` = per-axis cell
sizes = `2·extent_i/N` (wave-8 convention, `cassi_two_fluid.glsl`). Family under
test: `h = (φ, 1.0, s)`.

If the import is unavailable the probe falls back to an **identical local copy
of this exact function** (no behavior change); the prereg records this fallback
so the result is unambiguous either way.

## 2. Frozen setup

- **PHI** = `(1 + sqrt(5))/2` (from `phi_grid.PHI`, same source as wave-8).
- **Family:** `h(s) = (φ, 1.0, s)`.
- **Statistic:** `s*` = the `s` where `az(s) = 0`.
- **Method:**
  1. **Anchor gate first:** `lap_weights((φ, 1.0, φ²))` must reproduce the
     wave-8 tuple to the documented 3-decimal precision —
     `(ax, ay, az, bxy, bxz, byz)` round-matches
     `(0.127, 0.731, -0.009, 0.092, 0.035, 0.042)` for all six components
     (each `abs(diff) < 5e-4` → rounds to the same 3 dp). If the gate fails,
     print `PASS`/`FAIL` per component and bail with `ALL CHECKS FAILED`.
  2. **Scan:** evaluate `az(s)` on a fine uniform grid over `s ∈ [0.5, 2φ²+2]`
     (2φ²+2 = 7.2360679…) with a large step count; record every sign change of
     `az` (product of adjacent signs < 0, treating exact-zero as its own
     crossing sign edge).
  3. **Bisection:** for each detected crossing, refine to |az| < 1e-12 with
     bisection over the bracketing interval.
  4. **Supplementary (NO verdict):** also report `ax(s)` and `ay(s)` crossing
     locations and their sign structure — reference only, no verdict attached.

## 3. Decision tree (frozen)

| Verdict | Condition |
|---|---|
| **SUPPORTS** | `az` has **exactly one** sign change in `[0.5, 7.236]` AND the refined `s*` ∈ `[φ²·0.9, φ²·1.1] = [2.356, 2.880]` |
| **CONTRADICTS** | no sign change of `az` in the scan range, OR exactly one crossing whose `s*` lies outside `[2.356, 2.880]` |
| **INCONCLUSIVE** | more than one sign change of `az` in range, OR a near-zero plateau (`|az| < 1e-4` over a span ≥ 0.05 wide) touching the band edge `[2.356, 2.880]` such that `s*` becomes ambiguous |

No weaker/stronger gates are introduced post-freeze. Any change to a pin below
is a disclosed dated amendment.

## 4. What does NOT count

- Treating `ax`/`ay` crossings as verdicts (supplementary only).
- Claiming the engine *measured* the degenerate geometry — this probe derives a
  coefficient manifold from the wave-8 formula; it does not run the engine.
- Modifying `triaxial3d.py` or any existing file — the probe is new-files-only.

## 5. Reference

- Formula: `research/helix_solver/triaxial3d.py:37-48` (`lap_weights`).
- Wave-8 anchor tuple: `triaxial3d_simop_corr_prereg.md` and the dated
  correction in `triaxial3d_report.md` —
  `lap_weights((φ,1,φ²)) = (0.127, 0.731, −0.009, 0.092, 0.035, 0.042)`.
- Axes: `x` = Yang, `y` = Yin, `z` = String (the longest axis at `(φ,1,φ²)`).
