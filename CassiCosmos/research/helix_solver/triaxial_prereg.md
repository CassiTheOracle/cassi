# Triaxial-Transverse Wave 5a — the φ-ellipsoid probe — PRE-REGISTRATION

## Status: Pre-registration — written BEFORE any run; governs the wave-5a arms

**Date:** 2026-08-15 · **Workstream:** the ultimate Cassi solver (transverse geometry)
**Pre-registered outcomes:** the φ-ellipsoid vs spherical-transverse probe below.
**Implementing probes (numpy, new-files-only, under `CassiCosmos/research/helix_solver/`):** `triaxial_laplacian.py`, `verify_triaxial.py`, `triaxial_probe.py`.

---

## 0. The question and the doctrine anchors

### 0.1 The question

The "ultimate Cassi solver" should solve on the theory's OWN transverse geometry, not a sphere. The doctrine pins that geometry as the **oblate triaxial spheroid** (`bubble-edge-geometry.md` §2.3): the level set of $B(x,y,z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z)$, extended in Yang, contracted in Yin, bounded along the string. This probe asks the narrowest measurable question: **does the φ-ellipsoidal transverse Laplacian (vs a spherically-symmetric one) produce the doctrine's recorded anisotropic signatures?**

### 0.2 The doctrine anchors (each a pre-registered statistic)

| Anchor | Doctrine value | Source |
|---|---|---|
| **A1 — transverse axis ratio** | $\sigma_x/\sigma_y \to \varphi \approx 1.618$ | `bubble-edge-geometry.md` §2.1 ($a_X/a_Y = \beta/\alpha = \varphi$); measured 1.42 (87%) in `visual-explainers/string_bubble_cascade.py` |
| **A2 — axial ratio** | $\sigma_x/\sigma_z \to \varphi^2 \approx 2.618$ | `bubble-lattice-fabric.md:65` (oblate triaxial, bounded along the string); measured 2.51 (96%) in `string_bubble_cascade.py` |
| **A3 — edge-steepness anisotropy** | $\dfrac{|\nabla C|_{\text{axial}}}{|\nabla C|_{\text{diag}}} = \sqrt{\dfrac{4\varphi^2}{1+\varphi^2}} \approx 1.70$ (zero-parameter) | `bubble-edge-geometry.md` §2.2 |
| **A4 — radial ring ladder** | matter rings at $r_k = \ell_n\varphi^{-k}$ (ratio $\varphi^{-1} = 0.618$), voids at $\varphi^{-1/2} = 0.786$ | `bubble-edge-geometry.md` §3.1 (Derived-conditional; Prediction 51) |

### 0.3 Why this is falsifiable and not tautological

The φ-ellipsoid operator is the φ-aspect box's anisotropic 19-point FV stencil (weights $a_i, b_{ij}$ from the per-axis extents — already in `cassi_two_fluid.glsl` `lap_ey_at/lap_ei_at`). The spherically-symmetric control uses uniform weights. A symmetric operator CANNOT produce A1/A2/A3 (anisotropy is structurally impossible); the φ-ellipsoid MUST if it carries the theory. The question is whether the measured values *match the anchors' magnitudes*, not merely whether they are non-zero.

---

## 1. The frozen setup

### 1.1 The two transverse operators (2D, the Yang-Yin plane)

- **φ-ellipsoid arm:** the anisotropic 19-point FV Laplacian with the sim's per-axis weights: $b_{ij} = \tfrac13 h_0^2/(h_i^2+h_j^2)$, $a_i = h_0^2/h_i^2 - 2(b_{ij}+b_{ik})$, with $h_x : h_y : h_z = \varphi : 1 : \varphi^2$ (the box aspect = the triaxial semi-axis set). Reduced to 2D (the Yang-Yin plane) with the axial term held at the φ-apart set.
- **symmetric control:** the same stencil with $h_x = h_y = h_z$ (uniform weights) — the sphere's degenerate case.
- Grid: $N_x = N_y = 96$ (or the anisotropic extent-compatible sizes), periodic contact.

### 1.2 The wave

A single Gaussian bubble seeded on the φ-relaxed ground state (EY/EI at the φ-attractor), evolved by the two-fluid nonlinearity (the conversion/driving $g(q)$ and $(1-q)$ terms from `bubble-edge-geometry.md` §1.2, $\omega_0 = 0.1$, $D_{\text{eff}}$ as calibrated) OR, minimally, the linear two-fluid wave — the probe tests the OPERATOR's anisotropy imprint, so the linear two-fluid wave suffices for the shape signatures (A1–A3). The ring ladder (A4) needs the nonlinear condensation; measured in the same run if it forms.

### 1.3 Statistics

- **A1/A2:** the Gaussian-fitted widths σ_x, σ_y, σ_z of the emergent $\rho$ field; report the ratios vs φ, φ².
- **A3:** the edge gradient of the condensation field $C$ along the axial (Yin) vs diagonal (neighbor-ward) direction at the $C = \theta_{\text{cond}}$ contour; the ratio vs 1.70.
- **A4:** radial profile's local extrema → the matter/void ring radii; the consecutive ratios vs 0.618, 0.786.

### 1.4 Harness gates (verify_triaxial.py, unconditional)

1. **Symmetric control sanity:** the symmetric arm gives σ_x/σ_y ≈ σ_x/σ_z ≈ 1 (anisotropy requires the asymmetric operator — the control must be isotropic).
2. **Conservation:** the two-fluid energy conserved on the φ-ellipsoid arm over $10^3$ steps.
3. **φ-attractor:** the seeded ground state stays at EY/EI ≈ φ (the relaxation baseline).
4. **Determinism:** two runs bit-identical.

## Q1 — the φ-ellipsoid arm reproduces the doctrine anchors

### Decision tree

1. **EMERGES / ADOPTS-the-anisotropy**: the φ-arm's $\sigma_x/\sigma_y \in [1.3, 1.9]$, $\sigma_x/\sigma_z \in [2.0, 3.2]$ (bracketing the doctrine aims $\varphi$, $\varphi^2$ and the recorded measurements 1.42/2.51), and the edge ratio $\in [1.4, 2.0]$ (bracketing 1.70) — while the symmetric arm sits near 1.0 for both ratios. The φ-ellipsoid is the geometry that carries the theory's anisotropy.
2. **DOES NOT EMERGE**: the φ-arm is isotropic (ratios ≈ 1) or grossly off the anchors.
3. **INCONCLUSIVE**: harness failure (control not isotropic, no conservation).

## Q2 — the ring ladder (A4) under the φ-ellipsoid

EMERGES iff the radial profile shows distinct matter/void extrema with consecutive ratios within 30% of 0.618 and 0.786 (the doctrine aims), on the φ-arm; the symmetric arm shows no such ladder. A Reported Negative is stated if it does not form in the linear probe (the nonlinear condensation is then flagged as the follow-on).

---

## Stopping rule

Fixed: one seed, $10^3$ steps, one analysis per arm, deterministic. A CONTRADICTS/DOES-NOT-EMERGE is a finding, not a re-frame; only a new dated pre-registration re-opens.

## What does NOT count

- Post-hoc extents, $\omega_0$, seed, or step-count changes.
- Reading the 2D-Yang-Yin result as the 3D sim verdict — this is the transverse-plane signature probe, the axial/full-3D is future work.
- The ring ladder being absent from the LINEAR probe being read as doctrine-failure (it is a nonlinear phenomenon; reported, flagged).

## Honest tiers

- **T1 measured** — σ ratios, edge gradients, ring radii, energy drifts.
- **T2 inferred** — "the φ-ellipsoidal transverse Laplacian is the geometry that carries the theory's anisotropy" (Q1 EMERGES).
- **T3 out of scope** — the full 3D engine, the axial coupling (waves 1–4 cover the axial line), any registry edit.

## Number provenance

- The stencil weights: `cassi_two_fluid.glsl` `lap_ey_at/lap_ei_at` (the anisotropic 19-point FV, φ-aspect per-axis).
- The doctrine anchors: `bubble-edge-geometry.md` §2.1 (φ ratio, recorded 1.42), §2.2 (1.70 zero-parameter), §2.3 (the B(x,y,z) field, recorded 2.51), §3.1 (ring ladder 0.618/0.786); `bubble-lattice-fabric.md:65` (oblate triaxial); `predictions/falsifiable-predictions.md` Prediction 51.
- The recorded measurements: `visual-explainers/string_bubble_cascade.py` (σ_x/σ_z = 2.510 vs φ², σ_x/σ_y = 1.422 vs φ at step 1100).
- **Provenance note (2026-08-16):** the 1.422/2.510 values are single-run outputs of `CassiTheory/visual-explainers/string_bubble_cascade.py`, NOT engine measurements — see `research/helix_solver/oblate_provenance_audit.md` (commit 27ad20f) and `oblate_claim_map.md` (15db3c8).
