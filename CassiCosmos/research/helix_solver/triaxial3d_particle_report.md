# Wave 10 — particle-nbody gravity on the sim's periodic (φ,1,φ²) box — REPORT

**Date:** 2026-08-16 · **Pre-registration:** `triaxial3d_particle_prereg.md` (with the two dated
amendments). Every number came from `triaxial3d_particle_probe.py` live output. Gates:
`verify_triaxial3d_particle.py` prints `ALL CHECKS PASSED`.

## Verdict: the particle-nbody gravity sector does NOT produce oblate structure — CONTRADICTS

| arm | σ_x/σ_z @t=2400 | σ_x/σ_y @t=2400 | peak/peak0 | verdict |
|---|---|---|---|---|
| **A** free-streaming control | 1.008 | 1.012 | — (fixed) | round guard PASS |
| **B** particle self-gravity (g=1, π/ρ=1) | **1.001** | 1.012 | 21.980 | CONTRADICTS |
| **C** full composition (field π/ρ) — particle cloud | **1.007** | 1.012 | 1.616 | — (reported) |
| **C** full composition — field bubble (true frame) | **1.160** | 1.581 | — | CONTRADICTS |
| *(field-only baseline, true frame)* | *1.160* | *1.580* | — | *reference* |

Arm B (the pure particle-nbody test) **collapses** the round cloud — peak density grows **22×**
(peak/p0 = 21.980), confirming the attractive force is correct — but the collapse is **isotropic**:
σ_x/σ_z stays ~1.00 (1.008 → 1.001) throughout. The anisotropic (φ,1,φ²) Poisson box imprints **no
z-compression** at the cloud scale. Arm C's particle cloud also stays round (1.007; its collapse is
weakened ~4× by the field's π/ρ ≈ φ⁻³ = 0.236), and the field bubble is **unchanged** from the
field-only baseline (1.160 = 1.160) — the `0.001·ρ_mass` coupling is negligible, exactly as wave-9's
Q1a established. **The particle-gravity sector does not explain the (unverified) oblate record.**

## Trace tables (byte-for-byte from the probe)

```
  (A) free-streaming control (no gravity; must stay round):
      t=  200: sigma_x/y=1.012  sigma_x/z=1.008
      t=  600: sigma_x/y=1.012  sigma_x/z=1.008
      t= 1200: sigma_x/y=1.012  sigma_x/z=1.008
      t= 1800: sigma_x/y=1.012  sigma_x/z=1.008
      t= 2400: sigma_x/y=1.012  sigma_x/z=1.008

  (B) engine gravity g=1, pi/rho=1 (a = -G_N*grad(Phi)):
      t=  200: sigma_x/y=1.012  sigma_x/z=1.008  peak/p0=1.014
      t=  600: sigma_x/y=1.012  sigma_x/z=1.008  peak/p0=1.130
      t= 1200: sigma_x/y=1.012  sigma_x/z=1.007  peak/p0=1.674
      t= 1800: sigma_x/y=1.012  sigma_x/z=1.005  peak/p0=3.938
      t= 2400: sigma_x/y=1.012  sigma_x/z=1.001  peak/p0=21.980

  (field baseline) wave-9 field-only control (no particles):
      t=  200: true sigma_x/z=0.556  true sigma_x/y=0.786  sigma3_x/z=0.687
      t=  600: true sigma_x/z=0.838  true sigma_x/y=0.956  sigma3_x/z=0.456
      t= 1200: true sigma_x/z=1.029  true sigma_x/y=1.040  sigma3_x/z=0.371
      t= 1800: true sigma_x/z=1.116  true sigma_x/y=1.347  sigma3_x/z=0.342
      t= 2400: true sigma_x/z=1.160  true sigma_x/y=1.580  sigma3_x/z=0.329

  (C) full composition (pi/rho from the two-fluid field; field + 0.001*rho_mass):
      t=  200: part sigma_x/y=1.012  part sigma_x/z=1.008  peak/p0=1.003  | field sigma_x/z=0.557 (sigma3=0.686)  field sigma_x/y=0.787
      t=  600: part sigma_x/y=1.012  part sigma_x/z=1.008  peak/p0=1.027  | field sigma_x/z=0.838 (sigma3=0.456)  field sigma_x/y=0.956
      t= 1200: part sigma_x/y=1.012  part sigma_x/z=1.008  peak/p0=1.123  | field sigma_x/z=1.029 (sigma3=0.371)  field sigma_x/y=1.040
      t= 1800: part sigma_x/y=1.012  part sigma_x/z=1.008  peak/p0=1.298  | field sigma_x/z=1.116 (sigma3=0.342)  field sigma_x/y=1.348
      t= 2400: part sigma_x/y=1.012  part sigma_x/z=1.007  peak/p0=1.616  | field sigma_x/z=1.160 (sigma3=0.329)  field sigma_x/y=1.581
```

Frozen verdict lines:

```
  (A) control sigma_x/z @2400 = 1.008 (round guard: PASS)
  B: particle sigma_x/z @2400 = 1.001  (sigma_x/y=1.012, peak/p0=21.980)  ->  CONTRADICTS (no material oblate rise; sigma_x/z=1.001 vs round control 1.008)
  C: field sigma_x/z @2400 = 1.160 (true frame; sigma3=0.329; field-only baseline true=1.160)  ->  CONTRADICTS (no material rise; 1.160 vs field-only baseline 1.160)
     C particle cloud sigma_x/z @2400 = 1.007 (vs B = 1.001)
```

## Per-arm findings

### A — free-streaming control (gate)

A physically-round cloud (isotropic Gaussian, σ₀ = 5.12 physical, N_p = 32768, zero velocity) at
rest measures σ_x/σ_z = **1.008** and σ_x/σ_y = 1.012 — round to within sampling noise (the 0.8%
deviation from 1.000 is finite-N_p noise). The roundness guard [0.95, 1.05] passes. No force is
applied, so positions are fixed.

### B — particle self-gravity (g=1, π/ρ=1): isotropic collapse, no oblate

The pure particle-nbody arm applies `a = −G_N·∇Φ` (spectral Poisson on the TSC-deposited density,
3-point gradient, cached-acc KDK, G_N = 1). The cloud **collapses** — peak density rises
monotonically to **21.980×** its initial value — but the collapse is **isotropic**: σ_x/σ_z stays
1.008 → 1.001 (round, ending a hair *prolate*), σ_x/σ_y pinned at 1.012. The (φ,1,φ²) box's
anisotropic Poisson does **not** imprint z-compression at the cloud scale (σ₀ = 5.12 ≪ the box's
~64–167 physical units, so the periodic images are too distant to tidal-stretch the collapsing core
within the frozen 2400-step window). **Verdict: CONTRADICTS** — no material oblate rise.

### C — full composition: the particle-driven mass does NOT deform the field bubble

Arm C wires the engine's full loop: particles → TSC deposit → Poisson → two-fluid PDE (wave-8
machinery, source_strength = 0, with the always-on `0.001·ρ_mass` coupling) → particle force
`a = −G_N·(π/ρ)·∇Φ` with `π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72)` sampled from the *updated* field.
Two results:
- **Particle cloud:** σ_x/σ_z = 1.007 (round); its collapse is **~4× slower** than arm B
  (peak/p0 = 1.616 vs 21.980) because the field's π/ρ ≈ φ⁻³ = 0.236 at the attractor seed weakens
  the force. Still no oblate.
- **Field bubble:** σ_x/σ_z = **1.160** (true frame) — **identical to the field-only baseline
  1.160** to 3 decimals (σ_x/σ_y = 1.581 vs 1.580). The `0.001·ρ_mass` coupling contributes O(1e-6)
  to the field, so the particle-driven mass has **zero measurable effect** on the coherence bubble
  (confirming wave-9 Q1a). **Verdict: CONTRADICTS** — no material rise, no deformation.

## Honest reframe and the explicit answer

**Does the particle sector explain the (unverified) oblate record 2.510? NO.**

The provenance audit (`oblate_provenance_audit.md`, 27ad20f) established that 2.510 is a single-run
Python-PDE output (`string_bubble_cascade.py`), not an engine measurement, and the engine ships no
bubble-shape readout. Wave 8 showed the engine operator is *prolate* (σ_x/σ_z = 0.329 in the `sigma3`
frame); wave 9 ruled out the field-only mechanisms (deposit feedback, source field-gain, field
self-gravity); wave 10 now rules out the **particle-nbody gravity** sector: a round particle cloud
collapses isotropically (σ_x/σ_z ≈ 1.00), and the particle-driven mass does not deform the field
bubble (it stays at the field-only baseline). With all four sectors tested — operator, field feed,
field gravity, particle gravity — **none produces oblate z-compression on the sim's (φ,1,φ²) box.**
The 2.510 record remains an unverified single-run Python-PDE output with no identified mechanism in
the engine.

### Cross-frame note (a genuine positive, worth recording)

In the **true** engine frame (axis0 = x = φ-extent, axis2 = z = φ²-extent), the wave-8/9 field
machinery — with no particle or feed mechanism — *does* emerge a transverse ratio σ_x/σ_y = **1.580**
@2400, approaching the doctrine's φ = 1.618 (within ~2.3%), while its axial ratio σ_x/σ_z = 1.160 is
far from φ² = 2.618. This is the same field that reads σ_x/σ_z = 0.329 in the wave-9 `sigma3`
transposed labeling (σ_x/σ_z = 0.329 ↔ 1.160 are the SAME field under the axis-label swap). The
transverse φ-ratio is a real emergent property of the operator; the axial φ²-ratio is not. This is a
pointer for any future investigation: the operator carries the *transverse* anisotropy but nothing
in the sim so far carries the *axial* oblate compression.

### What remains untested (if the 2.510 record is ever to be explained)

- The **BH-accretion sector** (`cassi_bh_integrate.glsl`, `cassi_bh_accretion.glsl`).
- The **dual-lattice (BCC) gradient pass** (`gradient_order` 4, `dual_grid`).
- The **RealSim dissipation** (drag / viscosity / friction, `gravity_mode = 4`).
- The **full `g = 1 + (φ⁶−1)·q` chord factor** (this wave froze `g = 1`, per the audit's option).
- The **meshless / tree mode** (moving-Voronoi, open-boundary Barnes-Hut).
- The **actual mechanism of `string_bubble_cascade.py`** — the damped-wave RK4 numpy PDE that
  *did* produce 2.510; reproducing that script's IC (which seeds σ_x/σ_y = φ by construction and
  leaves z unseeded) is the most direct remaining path to understand the 2.510 provenance.

## Harness

`verify_triaxial3d_particle.py` → `ALL CHECKS PASSED`:
- G1 arm-A roundness: σ_x/σ_z = [1.0085, 1.0085, 1.0085, 1.0085, 1.0085] (all in [0.95, 1.05]).
- G2 Poisson exactness: single-mode inversion rel err = 1.32e-15 (< 1e-9), mean(Φ) = 2.87e-19.
- G3 TSC deposit: single-particle sum = 1.000000 (center) and 1.000000 (fractional); full-cloud
  sum = 1.000000 (total mass 1.0) — exact partition of unity.
- G4 determinism: two 100-step arm-B runs bitwise identical.
- G5 no-NaN: arm B @100 and arm C @100 finite.
- G6 mass conservation: deposit total mass = 1.000000000000 (exact).

## Traceability

- Re-run: `python research/helix_solver/triaxial3d_particle_probe.py` (~472 s; the owner's live
  Godot session competes for CPU, so wall time varies).
- Gates: `python research/helix_solver/verify_triaxial3d_particle.py` (~28 s) → `ALL CHECKS PASSED`.
- Files (new only): `triaxial3d_particle_prereg.md`, `triaxial3d_particle_probe.py`,
  `verify_triaxial3d_particle.py`, `triaxial3d_particle_report.md`. `triaxial3d.py`, the wave-9
  `triaxial3d_feed_*` files, and every other existing file are untouched.
- Ground truth: `cassi_mass_deposit.glsl` (TSC deposit), `cassi_poisson.glsl` (spectral Poisson),
  `cassi_nbody_gravity.glsl` (KDK, `a = −G_N·(π/ρ)·∇(g·Φ)`, π/ρ clamp), `cassi_physics_engine.gd`
  (box extents); provenance audit `oblate_provenance_audit.md`; wave-9 `triaxial3d_feed_report.md`.
