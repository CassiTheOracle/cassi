# Wave 6 — the full-3D oblate triaxial spheroid probe — REPORT

**Date:** 2026-08-15 · **Pre-registration:** `triaxial3d_prereg.md` (frozen before any run).
Every number below came from `verify_triaxial3d.py` / `triaxial3d_probe.py` live output.

## Verdict summary

| Gate / Question | Statistic | Measured | Target | Verdict |
|---|---|---|---|---|
| G1 | symmetric-op σ_x/y, σ_x/z, edge | **1.000, 1.000, 0.994** | ≈1.0 | **PASS** (3D op + round seed unbiased) |
| G2 | φ-arm σ_x/y, σ_x/z | **2.227, 3.251** | >1.15, >1.30 | **PASS** (round-seed discrimination holds) |
| G3 | free-case 3D machinery drift | **7.92e-5** | <5e-3 | **PASS** (uniform grid conserves cleanly) |
| G4 | determinism | bitwise identical | | **PASS** |
| sanity | C_dyn, no NaN | finite, [-1.0,-0.97] | | **PASS** |
| **Q1** | φ-arm σ_x/y vs φ, σ_x/z vs φ² | 2.227, 3.251 | in [1.2,1.9], [1.8,3.2] | **direction confirmed, magnitude OVER-SHOOTS** (not ACHIEVE as frozen) |
| Q2 | 3D edge (peak-z Yang-Yin slice) | φ 1.145 / ctl 0.994 | — | reported (weak; consistent with the 5a-followup Reported Negative) |
| Q3 | ring ladder (Prediction 51) | no bump (+1e-5) | — | **Reported Negative** (linear single bubble) |

## The headline finding

**The full-3D oblate-triaxial operator DOES imprint the doctrine's oblate shape on a
physically-round bubble — but over-drives the magnitude past φ.**

- **The physically-round seed is the honest discriminator.** The seed now has equal
  physical width on every axis (cell widths w/φ, w, w·φ cancel the aspect), verified:
  seed σ ratios = 1.0000/1.0009. Any emergent anisotropy is purely the operator's.
- **Control (isotropic op):** σ_x/y = σ_x/z = **1.000**, edge 0.994 — the 3D operator +
  round seed are unbiased.
- **φ-arm (oblate-triaxial op h=(φ,1,φ⁻¹)):** σ_x/y = **2.227**, σ_x/z = **3.251**,
  edge 1.145. The bubble is strongly oblate / **z-bounded** (σ_z smallest, 5.42 vs
  σ_x 17.62) — the doctrine's *direction* ("extended in Yang, contracted in Yin,
  bounded along the string", §2.3) is confirmed. But both ratios over-shoot the
  doctrine anchors (φ=1.618, φ²=2.618) at N=64, 600 steps.

**The over-shoot is the honest finding.** The pre-registered bands were [1.2,1.9] /
[1.8,3.2]; A1=2.227 exceeds 1.9 and A2=3.251 just exceeds 3.2, so Q1 **does not ACHIEVE
as frozen** — recorded with the over-shoot, not moved to pass. The 3D face-diagonal
couplings (bxy, bxz, byz in the sim's 19-point stencil) drive the anisotropy harder
than the 2D in-plane operator, producing the stronger-than-bubble shape at this short
run.

## The critical correction to wave 5a

**wave-5a's 2D result "σ_x/σ_y 1.000 → 1.212, heading to φ" was SEED-INHERITED, not a
second-moment imprint of the operator.** Re-tested with a physically-round 2D seed, the
(φ,1) in-plane operator gives σ_x/σ_y = **1.000** — NO anisotropy in the second moments.
The wave-5a seed used cell-width 0.08N on both axes, i.e. a *physical* extent (φ·?, 1),
so it baked the (φ,1) shape in; the operator added essentially nothing to σ. 

What survives wave-5a: the **edge-steepness** result (the bias-free proxy, validated in
the 5a-followup, that reproduces the analytic 1.707 exactly on the φ-checkerboard), and
the **control** validity. What was wrong: the *shape* claim that the 2D transverse
operator anisotropizes σ — in 2D it does not (only the 3D out-of-plane couplings do,
as wave-6 shows: 2.227/3.251).

This is a genuine correction to the program's record: the "φ-ellipsoid transverse
operator imprints the σ-anisotropy" headline is superseded by: **the φ-anisotropy in
the second-moment shape arises from the 3D face-diagonal couplings, not the 2D plane.**

## Q2 (edge) — reported

The φ-arm peak-z Yang-Yin slice edge = 1.145 vs control 0.994. Weak/shallow — the
small-amplitude single bubble does not form a sharp condensation boundary, consistent
with the 5a-followup dynamical **Reported Negative**. The absolute 1.70 remains a
field-shape property (measured exactly 1.707 on the analytic field in 5a-followup), not
realized by the minimal single-bubble dynamics. Reported, not gated.

## Q3 (ring ladder, Prediction 51) — Reported Negative

The 3D radial profile of |ρ| from the center shows **no local bump** at r/R=0.618
(+0.00001 vs its 5-bin neighbours, interior mean 0.015); the profile just decays. The
600-step linear single bubble does not quantize the doublet phase (the ring ladder needs
longer/nonlinear evolution to develop the φ-spaced matter/void rings). **Reported
Negative, as expected** — not claimed.

## Harness & machines

- The 3D solver is the sim's exact 19-point anisotropic periodic Laplacian
  (`cassi_two_fluid.glsl` `lap_ey_at`), matrix-free via `np.roll` (never a dense N³×N³
  operator — that would be ~68 GB at N=64). N=64, dt=0.02, two-fluid leapfrog with the
  half-kick. **Free-case drift 7.92e-5**, determinism bitwise — the uniform 3D grid
  conserves cleanly (unlike the φ-shell non-uniform grid, whose secular drift was the
  wave-5 close-out finding).
- All five gates PASS (`verify_triaxial3d.py` → `ALL CHECKS PASSED`).

## Honest amendments (disclosed, dated)

- **2026-08-15 (wave 6):** the 3D seed was corrected to be **physically round** (the
  initial version used equal cell-widths, which baked in the (φ,1,φ⁻¹) aspect — the same
  seed-inheritance bug that produced wave-5a's confounded 1.212). The physically-round
  seed is the honest discriminator and is what the pre-registration's "symmetric seed"
  was intended to mean; the correction was made before the probe verdict, and the
  wave-5a correction is recorded above. The Q3 ring statistic was corrected to a
  meaningful local-bump baseline (the initial far-field-floor ratio was degenerate at a
  ~0 baseline and the 266986x was an artifact — withdrawn).

## Traceability

- Re-run from `CassiCosmos/`: `python research/helix_solver/verify_triaxial3d.py`
  (~88 s, ALL CHECKS PASSED), `python research/helix_solver/triaxial3d_probe.py`
  (~120 s, deterministic).
- Files: `triaxial3d_prereg.md`, `triaxial3d.py`, `verify_triaxial3d.py`,
  `triaxial3d_probe.py` (all new, under `research/helix_solver/`).
- Doctrine: `bubble-edge-geometry.md` §2.3 (oblate triaxial spheroid, axes),
  §2.2 (the 1.70 edge, exact 1.707); §3.1 + `falsifiable-predictions.md` Prediction 51
  (ring ladder 0.618/0.786); `string_bubble_cascade.py` (σ 1.422, 2.510 record);
  the sim stencil `cassi_two_fluid.glsl` `lap_ey_at` / `lap_ei_at`.
- **Provenance note (2026-08-16):** the "record" 1.422/2.510 are single-run outputs of
  `CassiTheory/visual-explainers/string_bubble_cascade.py`, NOT engine measurements — see
  `research/helix_solver/oblate_provenance_audit.md` (commit 27ad20f) and `oblate_claim_map.md` (15db3c8).
- Prior waves: wave-5a (σ 1.212, seed-inherited — corrected here); the 5a-followup
  (bias-free edge proxy, the exact 1.707, the grid-limit); wave-5 close-out (φ-shell
  non-conservation); waves 1–4 (axial FV cascade).

## What this means for the ultimate Cassi solver

The 3D oblate-triaxial operator (the composition of axial + transverse) genuinely
produces the doctrine's *oblate, string-bounded* bubble topology on a round seed — the
direction is real and newly measured. But the magnitude over-shoots φ/φ² at this short
linear run, and the 2D planar operator alone does not anisotropize the shape (only the
3D couplings do). The natural wave-7 is a **longer/nonlinear or energy-fed run** to see
whether the over-shoot relaxes toward φ/φ² (the recorded 2.510/1.422 at sim step 1100
may reflect that relax) — and a proper ring-ladder candidate (Prediction 51, currently
Reported Negative). No registry entry is proposed (these are probe measurements).

---

## Dated correction (2026-08-15, wave 8)

**The "oblate direction confirmed, magnitude over-shoots" headline is SUPERSEDED.** Waves 6–7
chose the φ-arm operator aspect h=(φ,1,φ⁻¹) (the doctrine's *emergent bubble* shape), which
bakes the oblate result in. Measured against the **sim's actual operator**, whose cell sizes
are derived from the box extents (`cassi_two_fluid.glsl`: `h_i = extent_i/(N/2)`, default box
(φ,1,φ²), i.e. h=(φ,1,φ²), fully periodic via `% N`) — verified bit-identical (my
`lap_weights((φ,1,φ²))` = the shader's `a=(0.127,0.731,−0.009), b=(0.092,0.035,0.042)`) — the
pure two-fluid operator yields a **z-STRETCHED (prolate) bubble**: σ_x/σ_z = 0.329,
σ_x/σ_y = 0.842 at t=2400 (see `triaxial3d_simop_corr_probe.py`). The doctrine's oblate
record (σ_x/σ_z=2.510) therefore comes from the **source feed / cluster geometry / gravity
sector**, not the anisotropic Laplacian. The wave-6 Q1/Q2 shape numbers (2.227/3.251 and the
edge) describe the (φ,1,φ⁻¹) aspect, not the sim. The matrix-free machinery, free-case
conservation (7.9e-5), determinism, and the round-seed discipline stand. See
`triaxial3d_simop_corr_report.md` (wave 8).

**Provenance note (2026-08-16):** the oblate "record" σ_x/σ_z = 2.510 (and 1.422) are
single-run outputs of `CassiTheory/visual-explainers/string_bubble_cascade.py`, NOT engine
measurements — see `research/helix_solver/oblate_provenance_audit.md` (commit 27ad20f) and
`oblate_claim_map.md` (15db3c8). Per that audit the engine has no bubble-shape readout and
this SUPERSEDED section's PROLATE reading (0.329) is the operator's actual result.
