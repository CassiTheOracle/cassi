# Wave 8 — the sim-operator correction — REPORT

**Date:** 2026-08-15 · **Pre-registration:** `triaxial3d_simop_corr_prereg.md`. Every number
came from `triaxial3d_simop_corr_probe.py` live output.

## Verdict: CONFIRMED correction — the sim's operator yields a Z-STRETCHED (prolate) bubble, not the doctrine's oblate

| arm | σ_x/σ_y @t=2400 | σ_x/σ_z @t=2400 | bubble sense | doctrine | sim record |
|---|---|---|---|---|---|
| **(a) SIM op** h=(φ,1,φ²) | 0.842 | **0.329** | **z-STRETCHED (prolate)** | φ=1.618 | — |
| **(b) BUBBLE** h=(φ,1,φ⁻¹) | 1.871 | 4.442 | z-bounded (oblate) | φ²=2.618 | σ_x/σ_z=2.510 |

The two operators, same round seed, same dynamics, diverge completely:
- **(b)** the waves-6/7 aspect (φ,1,φ⁻¹) gives σ_x/σ_z = 4.44 (strongly oblate);
- **(a)** the sim's actual aspect (φ,1,φ²) gives σ_x/σ_z = **0.329** (strongly prolate —
  the bubble is stretched along the φ²-long z-box, exactly what a z-lengthening operator
  should do).

## Why this is the decisive, honest correction

1. **The sim's operator is h=(φ,1,φ²), fully periodic.** The shader computes
   `h_i = extent_i/(N/2)` from the box extents (default (φ,1,φ²)) and wraps every axis
   with `% N`. My independent `lap_weights((φ,1,φ²))` returns `ax=0.127, ay=0.731,
   az=-0.009, bxy=0.092, bxz=0.035, byz=0.042` — **bit-identical to the weights in the
   shader's own comment**. There is no ambiguity about which operator the sim uses.

2. **The pure two-fluid anisotropic operator does NOT produce the doctrine's oblate
   z-bounded bubble.** On the sim's real operator it produces a *prolate*, z-stretched
   shape (0.329). So the sim's recorded σ_x/σ_z = 2.510 **cannot come from the
   operator/dynamics alone** — it must arise from the **source feed / cluster geometry /
   gravity sector** that this operator-only probe does not include.

3. **Waves 6–7's "oblate direction confirmed, magnitude over-shoots" was aspect-circular.**
   I chose the φ-arm aspect h=(φ,1,φ⁻¹) (the doctrine's *emergent bubble* shape) as the
   operator, which bakes the oblate result in. Measured against the sim's real (φ,1,φ²)
   operator, there is no oblate imprint at all — the opposite. The wave-6/7 shape results
   (2.227/3.251, relax to 1.87/4.44) described the chosen aspect, not the sim's operator.

4. **The wave-7 "bounded-z vs periodic-z" hypothesis was wrong.** The shader is `% N`
   periodic in z too; there is no boundary-mismatch gap. That explanation is withdrawn.

## What survives of waves 6–7 (and what does not)

- **Survives:** the matrix-free 3D machinery (exact sim stencil), the free-case
  conservation (7.9e-5), determinism, the physically-round-seed discipline, the bias-free
  edge proxy (5a-followup, independent of this aspect issue), and the 5a-followup
  result that the 2D in-plane operator gives no second-moment imprint on a round seed.
- **Superseded:** the "oblate triaxial operator imprints σ_x/σ_z→φ²" claims (wave-6 Q1,
  wave-7 relax) — they were tied to the (φ,1,φ⁻¹) aspect choice, not the sim's operator.

## The honest reframe for the program and the viability question

The doctrine's oblate record (σ_x/σ_z=2.510) is **not** a property of the anisotropic
Laplacian under two-fluid dynamics — the operator alone gives the opposite (prolate).
The compression must come from the sim's **source/feed, cluster geometry, or gravity/BH
sector**, none of which are in the pure two-fluid wave this probe line has been studying.
This is a *correction of scope*, not a dead end: it tells the program where the oblate
shape actually lives (the feed/sector, not the operator), which is exactly the
decision-relevant information needed before any engine upgrade is justified.

**Viability:** this further **confirms there is no engine upgrade yet**. The research has
now shown the operator (which is the engine's own stencil) does *not* carry the anisotropy
that the engine's own record shows — pointing the investigation at the feed/gravity
sector as the real mechanism. No bit-identity-critical engine change is warranted.

## Harness

- Free-case machinery conservation 7.9e-5 (uniform-grid property, re-verified).
- Determinism bitwise (2400-step (a) re-run).
- Seed physically round (1.000) and non-wrapping (z-boundary mass 0.0000).

## Traceability

- Re-run: `python research/helix_solver/triaxial3d_simop_corr_probe.py` (~206 s).
- Files: `triaxial3d_simop_corr_prereg.md`, `triaxial3d_simop_corr_probe.py`,
  `triaxial3d_simop_corr_report.md`; corrections appended to `triaxial3d_report.md`
  (wave 6) and `triaxial3d_relax_report.md` (wave 7).
- Ground truth: `cassi_two_fluid.glsl` lines 53, 92–102, 119–121, 123–133 (periodic
  stencil + extent-derived cell sizes + the exact weight tuple).
