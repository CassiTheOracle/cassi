# Wave 6 — the full-3D oblate triaxial spheroid probe — PRE-REGISTRATION

## Status: Pre-registration — written BEFORE any run; governs the wave-6 arms

**Date:** 2026-08-15 (continuation of the ultimate-Cassi-solver program) ·
**Workstream:** the 3D transverse/axial composition ·
**Pre-registered outcomes:** whether the full-3D oblate-triaxial (φ-ellipsoid, string-bounded)
operator imprints the doctrine's emergent bubble shape in BOTH transverse and axial
dimensions (σ_x/σ_y → φ AND σ_x/σ_z → φ²), under the sim's two-fluid dynamics, with an
honest Reported Negative delivered if it does not.
**Implementing probes (numpy, new-files-only, under `CassiCosmos/research/helix_solver/`):**
`triaxial3d.py`, `verify_triaxial3d.py`, `triaxial3d_probe.py`.

---

## 0. The question and the prior record

### 0.1 The question

Wave 5a established that the **2D φ-ellipsoid transverse operator** imprints the
doctrine's in-plane anisotropy (σ_x/σ_y leaves the isotropic control 1.000 →
1.212, heading to φ; edge 1.70 measured on the analytic field at 1.707). The
5a-followup replaced the (withdrawn) arc-proxy with a validated bias-free proxy.
Wave 6 asks the 3D question: the theory's bubble is an **oblate triaxial spheroid —
extended in Yang, contracted in Yin, bounded along the string** (`bubble-edge-geometry.md`
§2.3). Does the **3D oblate-triaxial operator**, under the sim's two-fluid dynamics from a
symmetric seed, reproduce the doctrine's full emergent shape — σ_x/σ_y → φ AND
σ_x/σ_z → φ² (the latter never measured in the solver; the string axis is the axial
direction of waves 1–4)?

### 0.2 Why this is the honest continuation

- The **2D radial/transverse** plane (waves 5a–5a-followup) and the **1D axial cascade**
  (waves 1–4) are the two halves. Wave 6 composes them in 3D; σ_x/σ_z (the string/axial
  ratio, recorded 2.510 → φ² in `string_bubble_cascade.py`) has never been measured by
  a solver.
- The 5a-followup's dynamical leg was an honest **Reported Negative** (the 2D single-bubble
  does not form a sharp condensation boundary; the 1.70 is a field-shape property). Wave 6
  does NOT re-run that doomed absolute-edge measurement; it measures the **3D shape**
  (σ-ratios, second moments — robust) and reports the ring ladder as exploratory.
- The 3D solver uses a **uniform Cartesian grid with per-axis anisotropic weights**
  (the sim's exact 19-point `lap_ey_at` stencil reduced to matrix-free `np.roll`), NOT the
  φ-shell non-uniform grid whose FV leapfrog was shown (wave-5 close-out) to be
  non-conservative (secular drift ~2.5e-2). The uniform grid conserves cleanly (~3.6e-4).

### 0.3 The doctrine anchors (all from `bubble-edge-geometry.md` / `string_bubble_cascade.py`)

| Anchor | Doctrine | Recorded (sim, step 1100) |
|---|---|---|
| A1 transverse ratio σ_x/σ_y | → φ = 1.618 | 1.422 |
| A2 axial ratio σ_x/σ_z | → φ² = 2.618 | 2.510 |
| Edge ratio | 1.70130 (§2.2; exact 1.707 at θ=0.45) | — (grid-limited, reported) |
| Ring ladder (Prediction 51) | matter 0.618·R, void 0.786·R | — (exploratory) |

### 0.4 Frozen axes and aspect (grounded, §2.3)

- **x = Yang** (Λ_Y = φ·Λ_I, largest wavelength, "extended in Yang"); **y = Yin** (Λ_I);
  **z = string** ("bounded along the string", the cascade/axial direction).
- **φ-arm aspect:** physical cell sizes **h = (φ, 1, φ⁻¹)** — the operator weights encode
  the doctrine's oblate-triaxial shape (σ ∝ h ⇒ σ_x/σ_y = φ, σ_x/σ_z = φ², the
  emergent bubble is z-bounded).
- **Symmetric control:** h = (1, 1, 1) — must give all three σ ratios ≈ 1.0 (validates the
  3D operator + symmetric seed are unbiased).
- The sim's box default (φ, 1, φ²) is the **computational domain** (long z to fit
  dynamics); the *bubble it produces* is z-compressed (recorded σ_x/σ_z = 2.51). The
  solver's aspect is the operator's geometry (the bubble's own shape), which is the
  doctrine's oblate spheroid.

## 1. Frozen setup (verify *before* first probe run)

- **Operator:** the sim's exact 3D 19-point anisotropic periodic Laplacian
  (`cassi_two_fluid.glsl` `lap_ey_at`), matrix-free via `np.roll`. Weights (per axis):
  hx,hy,hz = h per axis; h0 = min; h02 = h0²; b_xy = (1/3)h02/(hx²+hy²);
  b_xz = (1/3)h02/(hx²+hz²); b_yz = (1/3)h02/(hy²+hz²); a_x = h02/hx² − 2(b_xy+b_xz);
  a_y = h02/hy² − 2(b_xy+b_yz); a_z = h02/hz² − 2(b_xz+b_yz). The discrete operator at
  (i,j,k) is a_x·(x-neighbours) + a_y·(y-neighbours) + a_z·(z-neighbours)
  + b_xy·(4 xy-face-diagonals) + b_xz·(4 xz) + b_yz·(4 yz) — exactly the shader.
- **Grid:** N = 64 per axis, periodic, uniform cells (physical extent ∝ aspect).
- **Two-fluid dynamics** (the sim's PDE, 3D): ∂²EY/∂t² = c²∇²EY − ω₀²(EY − φEI);
  ∂²EI/∂t² = c²∇²EI + ω₀²(EY − φEI); c=1.0, ω₀²=20.0, dt=0.02, leapfrog with the
  half-kick staggered start (the wave-1 lesson). 600 steps.
- **Seed:** a single radially-symmetric 3D Gaussian (σ_cell = 0.08·N per axis, co-located
  EY/EI with EI = φ⁻¹·EY), amplitude 0.3.
- **Measures:** second-moment σ_x, σ_y, σ_z of |ρ| = |EY+EI| (identical to wave-5a's
  `sigma_ratios`, extended to 3D, with physical scaling × h_per_axis).

## 2. The questions and decision trees

### Q1 (A1 + A2 — the core 3D shape gate)

**Statistic:** σ_x/σ_y and σ_x/σ_z on the φ-arm vs the symmetric control, after 600 steps.

| Verdict | Condition |
|---|---|
| **ACHIEVES** | φ-arm σ_x/σ_y ∈ [1.2, 1.9] (→ φ) AND σ_x/σ_z ∈ [1.8, 3.2] (→ φ²) AND symmetric control σ_x/σ_y, σ_x/σ_z ∈ [0.95, 1.05] |
| **CONTRADICTS** | the φ-arm ratios are flat/≈ uniform (e.g. σ_x/σ_z < 1.2) OR the control is biased (≠1.05) |
| **INCONCLUSIVE** | harness failure (operator wrong / explosion / non-determinism) |

The σ_short-run under-relaxation is expected (wave-5a: 1.212 → φ at 600 steps); the band
is the doctrine's recorded-adjacent range. A **Reported Negative** is a deliverable.

### Q2 (exploratory) — the 3D edge ratio

**REPORTED, not gated:** the absolute edge-steepness is a field-shape property whose sharp
measurement is grid-limited (5a-followup F2). In 3D we REPORT the φ-arm slice (peak-z,
Yang–Yin plane) edge ratio from the bias-free proxy applied to |ρ|, and the φ-vs-symmetric
**differential**. Given the 5a-followup dynamical Reported Negative (single bubble → no
sharp boundary), an absent/weak edge is expected and recorded; a clean differential would
be a positive.

### Q3 (exploratory) — the 3D ring ladder (Prediction 51)

**REPORTED, not gated:** the 3D radial profile of |ρ| from the bubble center. The doctrine
(Prediction 51) predicts a matter ridge at r/R = φ⁻¹ = 0.618 and a void at
r/R = φ⁻¹/² = 0.786. Report whether the 600-step 3D bubble shows structure at those radii
(peak-to-trough contrast ≥ 10%) or a flat profile (Reported Negative). A short linear run
may not quantize the doublet phase — that is a genuine negative, recorded.

## 3. Harness gates (verify_triaxial3d.py, unconditional, must ALL PASS)

1. **G-iso-control:** the symmetric operator (1,1,1) from a symmetric seed gives σ_x/σ_y,
   σ_x/σ_z ∈ [0.95, 1.05] after 600 steps (3D operator + seed unbiased).
2. **G-phi-shape:** the φ-arm gives σ_x/σ_y and σ_x/σ_z both > 1 clearly (anisotropic;
   the operator carries the shape).
3. **G-machinery-free:** the free (ω₀²=0) two-fluid energy drift < 5e-3 over 600 steps on
   the uniform 3D grid (the uniform-grid conservation holds, unlike the φ-shell).
4. **G-determinism:** two identical runs bitwise identical.
5. **Sanity:** no NaN, C_dyn = 2(EY²+EI²)−1 ∈ [-1.5, 1.5] (weak, since the small-amplitude
   bubble gives C≈−1 dense-void reading per 5a-followup).

## 4. Stopping rule

Fixed: one symmetric seed, N=64, 600 steps, two aspects (φ-arm, symmetric), one analysis,
deterministic. A CONTRADICTS is final for this wave. Only a new dated pre-registration
re-opens.

## 5. What does NOT count

- Post-hoc N, steps, dt, aspect, seed, or threshold changes.
- Reading the σ-shape (second moments) as the edge-steepness 1.70 (a different quantity —
  the edge needs the sharp-proxy follow-on).
- Claiming the 3D probe as the full sim engine (no shader/engine/Godot change here).

## 6. Honest tiers

- **T1 measured** — σ ratios, energy drifts, ring positions, determinism.
- **T2 inferred** — "the 3D oblate-triaxial operator imprints the doctrine's emergent
  bubble shape in both transverse and axial dimensions."
- **T3 out of scope** — the full sim engine, any Godot/shader/registry edit.

## 7. Number provenance

- PDE + 19-point stencil + weights: `CassiCosmos/compute/cassi_two_fluid.glsl`
  (`lap_ey_at`, `lap_ei_at`).
- Axes, aspect, anchors, ring ladder: `CassiTheory/foundations/bubble-edge-geometry.md`
  §2.2 (§2.3 B(x,y,z)=cosαx·cosβy·cosγz, "oblate triaxial spheroid—extended in Yang,
  contracted in Yin, bounded along the string"), §3.1 (ring ladder),
  `CassiTheory/predictions/falsifiable-predictions.md` (Prediction 51).
- Recorded σ ratios: `CassiTheory/visual-explainers/string_bubble_cascade.py`
  (σ_x/σ_y=1.422, σ_x/σ_z=2.510).
- 2D shape result (wave-5a): σ 1.000 → 1.212 heading to φ.
- Edge 1.70 / grid-limit / proxy validation: `edge_proxy_prereg.md` / `edge_proxy_report.md`
  (wave-5a-followup).
