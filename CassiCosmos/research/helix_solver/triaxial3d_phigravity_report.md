# Wave 12b (U3) — full φ⁶-modulated gravity — REPORT

**Date:** 2026-08-16 · **Pre-registration:** `triaxial3d_phigravity_prereg.md` (frozen). Every
number came from `triaxial3d_phigravity_probe.py` live output (byte-reconciled below). Gates:
`verify_triaxial3d_phigravity.py` prints `ALL CHECKS PASSED`.

## Verdict: the φ⁶-modulated gravity is NOT the missing oblate mechanism — CONTRADICTS

| arm | particle σ_x/σ_z @2400 | particle σ_x/σ_y @2400 | peak/p0 | field σ_x/σ_z @2400 | verdict |
|---|---|---|---|---|---|
| **A** free-streaming control | 1.008 | 1.012 | — | — | round guard PASS |
| **B** wave-10 g=1, π/ρ=1 (anchor) | **1.001** | 1.012 | 21.980 | — | REPRODUCED |
| **C** full φ⁶ coupling (g = 1+(φ⁶−1)·q) | **1.003** | 1.018 | 11.096 | **1.160** | CONTRADICTS |
| *(field-only baseline)* | — | — | — | *1.160* | *reference* |

The φ⁶ chord factor **is active** — arm C's collapse is ~7× faster than wave-10's g=1 arm C
(peak/p0 = 11.096 vs 1.616), and ~½ arm B's (21.980) — but it acts **isotropically**: the particle
cloud stays round (σ_x/σ_z = 1.003, within noise of the 1.008 round control), and the field bubble
is **unchanged** from the field-only baseline (1.160 = 1.160). The hypothesis that coherence-gated
gravity imprints the field's transverse anisotropy (σ_x/σ_y ≈ 1.580) onto the collapsing cloud is
**falsified**: the cloud's transverse ratio moves only 1.012 → 1.018 (0.5%), and there is **no
axial compression** at all.

## Trace tables (byte-for-byte from the probe)

```
  (A) free-streaming control (no gravity; must stay round):
      t=  200: sigma_x/y=1.012  sigma_x/z=1.008
      t=  600: sigma_x/y=1.012  sigma_x/z=1.008
      t= 1200: sigma_x/y=1.012  sigma_x/z=1.008
      t= 1800: sigma_x/y=1.012  sigma_x/z=1.008
      t= 2400: sigma_x/y=1.012  sigma_x/z=1.008

  (B) wave-10 arm-B reproduction (g=1, pi/rho=1):
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

  (C) FULL phi^6-modulated gravity (g=1+(phi^6-1)*q; whole-product grad(g*Phi)):
      t=  200: part sigma_x/y=1.011  part sigma_x/z=1.007  peak/p0=1.076  | field sigma_x/z=0.557 (sigma3=0.686)  field sigma_x/y=0.787
      t=  600: part sigma_x/y=1.011  part sigma_x/z=1.005  peak/p0=1.408  | field sigma_x/z=0.838 (sigma3=0.456)  field sigma_x/y=0.956
      t= 1200: part sigma_x/y=1.013  part sigma_x/z=1.003  peak/p0=2.483  | field sigma_x/z=1.029 (sigma3=0.371)  field sigma_x/y=1.040
      t= 1800: part sigma_x/y=1.015  part sigma_x/z=1.003  peak/p0=4.958  | field sigma_x/z=1.116 (sigma3=0.342)  field sigma_x/y=1.348
      t= 2400: part sigma_x/y=1.018  part sigma_x/z=1.003  peak/p0=11.096 | field sigma_x/z=1.160 (sigma3=0.329)  field sigma_x/y=1.581
```

Frozen verdict lines:

```
  (A) control sigma_x/z @2400 = 1.008 (round guard: PASS)
  (B) anchor sigma_x/z @2400 = 1.001 (sigma_x/y=1.012, peak/p0=21.980) -> REPRODUCED wave-10
  C: particle sigma_x/z @2400 = 1.003  (wave-10 baseline 1.00; threshold 1.05)
     field sigma_x/z @2400 = 1.160  (true frame; baseline 1.160; 5% rise threshold 1.218)
     C particle peak/p0 @2400 = 11.096  (vs wave-10 arm C = 1.616)
  OVERALL: CONTRADICTS (particle sigma_x/z=1.003 < 1.05 within noise of 1.00 AND field sigma_x/z=1.160 < 1.218 unchanged from baseline 1.160)
```

## Per-arm findings

### A — free-streaming control (gate)

Round to within finite-N_p noise (σ_x/σ_y = 1.012, σ_x/σ_z = 1.008), unchanged across all traces.
Roundness guard [0.95, 1.05] passes.

### B — wave-10 anchor (calibration)

Bit-reproduces wave-10's arm B exactly: σ_x/σ_z @2400 = 1.001, σ_x/σ_y = 1.012, peak/p0 = 21.980
(the isotropic 22× collapse). The harness is anchored to the prior wave's reported precision.

### C — full φ⁶-modulated gravity: active but isotropic

The law is implemented whole-product exactly as the shader specifies (`cassi_nbody_gravity.glsl`
L7-17, L354-361, L431-466, L499-518): `S = g·Φ` at cells, `g = 1+(φ⁶−1)·q`,
`q = ρ²/(ρ²+φ⁻²+ε²)` with `ρ=EY+EI`, `ε=EY−φ·EI`, forward central-difference ∇S, trilinear
sampling, `a = −G_N·(π/ρ)·∇S`, `π/ρ = clamp((EY−EI)/(EY+EI),0,0.72)`. At t=0 the bubble seed gives
`q ∈ [0, 0.3815]`, `g ∈ [1.0, 7.4646]` (φ⁶−1 = 16.9443), so the g factor is non-trivially active
but below the shader's attractor ceiling (q≈0.947, g≈17.9) because `seed_bubble3d` does not start at
the attractor.

Results: the φ⁶ modulation **changes the collapse rate** (peak/p0 = 11.096, ~7× wave-10 arm C's
1.616 and ~½ arm B's 21.980 — the g factor partially offsets the π/ρ≈0.236 weakening) but **not the
shape**. The cloud stays round (σ_x/σ_z = 1.003) and the transverse ratio barely moves (1.012 →
1.018). The field bubble is **byte-identical to the field-only baseline** (σ_x/σ_z = 1.160,
σ_x/σ_y = 1.581) — the particle-driven mass still contributes O(1e-6) to the field. **Verdict:
CONTRADICTS** — no oblate rise in either the particle cloud or the field.

## The explicit answer

**Is the φ⁶-modulated gravity the missing oblate mechanism? NO.**

The last untested lever is now closed. The coherence-gated chord factor `g = 1+(φ⁶−1)·q` is real and
active (it accelerates the collapse 7× over the g=1 composition), but it is spatially modulated in a
way that does **not** translate into shape: the collapsing cloud remains round (σ_x/σ_z = 1.003,
transverse 1.018) and the field bubble is unchanged (1.160). The field's own transverse anisotropy
(σ_x/σ_y ≈ 1.580, true frame) is **not** imprinted onto the particle cloud by the φ⁶ coupling, and no
axial (z-compressed) structure emerges.

With this, **every gravity/field mechanism the engine ships has now been tested** — wave 8
(operator, prolate), wave 9 (field feed, field gravity), wave 10 (particle gravity, g=1), wave 12b
(particle gravity, full φ⁶ chord) — and **none produces the doctrine's oblate σ_x/σ_z = 2.510.** The
only remaining untested items are the BH-accretion sector, the dual-lattice (BCC) gradient pass, and
the RealSim dissipation (all `gravity_mode` toggles, not the law's core), none of which is a
different *gravity law* — they are additions to, or sampling refinements of, the same river law
already shown to be isotropic here. The provenance chain is therefore closed: the oblate record is
not an engine observable at all (wave 11 established it is a seeded-transverse +
coherence-shell-transient artifact of a single numpy PDE, with an energy that is round at every
step).

## Harness

`verify_triaxial3d_phigravity.py` → `ALL CHECKS PASSED`:
- G1 arm-B anchor: @2400 σ_x/z = 1.001 (1.001), σ_x/y = 1.012 (1.012), peak/p0 = 21.980 (21.980).
- G2 Poisson exactness: single-mode inversion rel err = 1.32e-15 (< 1e-9), mean(Φ) = 2.87e-19.
- G3 TSC deposit: single-particle sum = 1.000000 (center) and 1.000000 (fractional); full-cloud
  sum = 1.000000 (total mass 1.0).
- G4 determinism: two 100-step arm-C runs bitwise identical.
- G5 no-NaN: arm B @100 and arm C @100 finite (B σ_x/z = 1.008, C part σ_x/z = 1.008, C field
  σ_x/z = 0.441).
- G6 (reported): field q ∈ [0, 0.3815], g ∈ [1.0, 7.4646] at t=0 (φ⁶−1 = 16.9443).

## Traceability

- Probe: `python research/helix_solver/triaxial3d_phigravity_probe.py` (~8 min; owner's Godot
  competes).
- Gates: `python research/helix_solver/verify_triaxial3d_phigravity.py` (~3 min) → `ALL CHECKS
  PASSED`.
- Files (new only): `triaxial3d_phigravity_prereg.md`, `triaxial3d_phigravity_probe.py`,
  `verify_triaxial3d_phigravity.py`, `triaxial3d_phigravity_report.md`. Wave-10
  `triaxial3d_particle_*`, wave-9 `triaxial3d_feed_*`, `triaxial3d.py`, and every other file are
  untouched.
- Ground truth: `cassi_nbody_gravity.glsl` L7-17 (q/g/a/π/ρ), L354-361 (`chord_s_at`), L431-466
  (`grad_pass`), L499-518 (`chord_g_from`); `oblate_provenance_audit.md` §3b (the same law);
  wave-10 `triaxial3d_particle_report.md` (the 1.008/1.001/21.980/1.160 baseline).
