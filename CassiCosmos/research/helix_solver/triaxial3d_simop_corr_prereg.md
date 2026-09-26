# Wave 8 — the sim-operator correction — PRE-REGISTRATION

## Status: Pre-registration — the frozen statistic; the decisive run used the same frozen
setup below (recorded here verbatim; the exploratory confirm that motivated this wave ran
the identical trace before this file was written — disclosed in the report).

**Date:** 2026-08-15 (follow-up to waves 6–7) · **Workstream:** 3D shape validation ·
**Pre-registered outcome:** whether the SIM's actual operator (cell sizes ∝ box extents
(φ,1,φ²), fully periodic) reproduces the doctrine's oblate z-bounded bubble, or whether
waves 6–7's "oblate direction confirmed" was an artifact of choosing the bubble-shaped
aspect (φ,1,φ⁻¹).

## 0. The correction being tested

Waves 6–7 used the φ-arm aspect h = (φ, 1, φ⁻¹) — the doctrine's *emergent bubble* shape —
and measured an oblate, z-bounded result (σ_x/σ_z 3.25 → relax → 4.44). But the sim's
shader computes cell sizes **h_i = extent_i/(N/2)** from the box *extents* (`cassi_two_fluid.glsl`
lines 92–95), and the default box is (φ, 1, φ²) — so the sim's actual operator is
**h = (φ, 1, φ²)**, fully periodic in all three axes (`% N` at lines 119–121). The
bubble-shaped aspect was a design choice that may have baked the oblate result in.

**Verification of the operator identity:** `lap_weights((φ,1,φ²))` returns
`ax=0.127, ay=0.731, az=-0.009, bxy=0.092, bxz=0.035, byz=0.042` — exactly the weights in
the shader's own comment ("a=(0.127,0.731,−0.009), b=(0.092,0.035,0.042)"). This pins
h=(φ,1,φ²) as the sim's operator.

## 1. Frozen setup

- The **physically-round** 3D Gaussian seed (the wave-6 correction), N=64, dt=0.02,
  two-fluid with the half-kick, ω₀²=20, 2400 steps, traced at t=200,600,1200,1800,2400.
- **Arm (a):** the SIM operator h=(φ,1,φ²) — the sim's real cell sizes, fully periodic.
- **Arm (b):** the BUBBLE aspect h=(φ,1,φ⁻¹) — the waves-6/7 operator (re-run for a clean,
  side-by-side live contrast).
- Statistic: σ_x/σ_y and σ_x/σ_z from the 3D second moments of |EY+EI|.

## 2. Decision (frozen)

| Verdict | Condition |
|---|---|
| **CONFIRMED correction** | the SIM operator (a) gives σ_x/σ_z < 1 at t=2400 (a Z-STRETCHED, prolate bubble — NOT the doctrine's oblate); then waves 6–7's oblate direction was aspect-circular, and the sim's recorded 2.510 requires a mechanism beyond the operator |
| **Refuted** | the SIM operator gives σ_x/σ_z ≥ 1 t=2400 (z-bounded even with the φ² z-box) — the operator does carry the oblate direction |

The doctrine anchors (φ, φ²) and the sim record (1.422, 2.510) are reference lines for
the reading, not gates.

## 3. Harness guards (unconditional)

- Free-case machinery conservation < 5e-3 (the uniform-grid property, already gated in
  wave-6; re-verified here).
- Determinism: the 2400-step (a) run re-run bitwise identical.
- Seed both physically round (σ ratios 1.000) and non-wrapping (z-boundary mass ≈ 0).

## 4. What does NOT count

- Post-hoc aspect, step, seed, threshold, or grid changes.
- Reading this operator-only result as the full sim (no source feed / gravity / cluster
  geometry here — those are exactly what the correction points to as the missing
  mechanism, and are out of scope for this operator probe).
- Treating waves 6–7's numbers as the sim's when they used the non-sim aspect.

## 5. Number provenance

- Sim operator + weights + `% N` periodicity: `CassiCosmos/compute/cassi_two_fluid.glsl`
  lines 53, 92–102, 119–121, 123–133.
- Box extents default (φ,1,φ²): the sim's `extent_x/y/z` (box aspect (1.618,1.0,2.618)).
- Waves 6–7 aspect (φ,1,φ⁻¹) and results: `triaxial3d_report.md`,
  `triaxial3d_relax_report.md`.
- Doctrine anchors + sim record: `bubble-edge-geometry.md` §2.3, `string_bubble_cascade.py`.
