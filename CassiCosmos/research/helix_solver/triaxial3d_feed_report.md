# Wave 9 — source-feed (Q1a/Q1b) and Poisson-gravity (Q2) on the sim's real (φ,1,φ²) operator — REPORT

**Date:** 2026-08-16 · **Pre-registration:** `triaxial3d_feed_prereg.md`. Every number came from
`triaxial3d_feed_probe.py` live output (re-run for the corrected verdict precedence, per the
prereg's dated amendment). Gates: `verify_triaxial3d_feed.py` prints `ALL CHECKS PASSED`.

## Verdict: all three mechanisms DO NOT EMERGE — none converts the prolate bubble toward the oblate reference

| arm | σ_x/σ_y @t=2400 | σ_x/σ_z @t=2400 | peak/peak0 | verdict (σ_x/σ_z primary) |
|---|---|---|---|---|
| **control** (pure wave-8) | 0.842 | **0.329** | 0.091 | — (prolate anchor reproduced) |
| **Q1a** TSC deposit feedback | 0.842 | **0.329** | 0.091 | CONTRADICTS / DOES NOT EMERGE |
| **Q1b** source field-gain | 1.285 | **0.528** | 0.343 | CONTRADICTS / DOES NOT EMERGE |
| **Q2** Poisson-gravity (g=1) | 0.767 | **0.304** | 0.057 | CONTRADICTS / DOES NOT EMERGE |

The frozen SUPPORTS condition (σ_x/σ_z rises from ≈0.33 toward ≥1, ideally into 1.8–3.2) is met
by **none** of the arms. Q1a is indistinguishable from the control; Q1b raises σ_x/σ_z to 0.528
(still prolate, ≤ 0.6) while raising σ_x/σ_y toward φ; Q2 makes σ_x/σ_z slightly **more** prolate
(0.304) with faster amplitude decay. The wave-8 correction stands: the doctrine's oblate reference
σ_x/σ_z = 2.510 does **not** arise from the deposit feedback, the source field-gain, or the field's
own (g=1) Poisson self-gravity on the sim's real operator.

## Trace tables (byte-for-byte from the probe)

```
  (control) pure wave-8 case (no feed, no gravity):
      t=  200: sigma_x/y=0.874  sigma_x/z=0.687  peak/p0=0.345
      t=  600: sigma_x/y=0.705  sigma_x/z=0.456  peak/p0=0.197
      t= 1200: sigma_x/y=0.625  sigma_x/z=0.371  peak/p0=0.115
      t= 1800: sigma_x/y=0.746  sigma_x/z=0.342  peak/p0=0.095
      t= 2400: sigma_x/y=0.842  sigma_x/z=0.329  peak/p0=0.091

  (Q1a) TSC mass-deposit feedback (0.001*rho_mass*dt^2 on EY, 0.000707*rho_mass*dt^2 on EI):
      t=  200: sigma_x/y=0.874  sigma_x/z=0.687  peak/p0=0.345
      t=  600: sigma_x/y=0.705  sigma_x/z=0.456  peak/p0=0.197
      t= 1200: sigma_x/y=0.625  sigma_x/z=0.371  peak/p0=0.115
      t= 1800: sigma_x/y=0.746  sigma_x/z=0.342  peak/p0=0.095
      t= 2400: sigma_x/y=0.842  sigma_x/z=0.329  peak/p0=0.091

  (Q1b) source_strength field-gain (0.5 centered EY, 0.707*0.5 offset EI):
      t=  200: sigma_x/y=1.688  sigma_x/z=0.642  peak/p0=0.444
      t=  600: sigma_x/y=1.515  sigma_x/z=0.618  peak/p0=0.415
      t= 1200: sigma_x/y=1.273  sigma_x/z=0.574  peak/p0=0.304
      t= 1800: sigma_x/y=1.207  sigma_x/z=0.541  peak/p0=0.356
      t= 2400: sigma_x/y=1.285  sigma_x/z=0.528  peak/p0=0.343

  (Q2) Poisson-gravity self-coupling (g=1, G_N=1.0):
      t=  200: sigma_x/y=0.890  sigma_x/z=0.706  peak/p0=0.606
      t=  600: sigma_x/y=0.693  sigma_x/z=0.442  peak/p0=0.210
      t= 1200: sigma_x/y=0.595  sigma_x/z=0.357  peak/p0=0.096
      t= 1800: sigma_x/y=0.676  sigma_x/z=0.325  peak/p0=0.064
      t= 2400: sigma_x/y=0.767  sigma_x/z=0.304  peak/p0=0.057
```

Frozen verdict lines:

```
  control sigma_x/z @2400 = 0.329 (wave-8 anchor ~0.329; prolate <= 0.6), peak/p0 = 0.091
  Q1a: ... -> CONTRADICTS / DOES NOT EMERGE  [amplitude-floor caveat: peak/peak0 < 0.10 (control 0.091)]
  Q1b: ... -> CONTRADICTS / DOES NOT EMERGE
  Q2:  ... -> CONTRADICTS / DOES NOT EMERGE  [amplitude-floor caveat: peak/peak0 < 0.10 (control 0.091)]
```

## Per-arm findings

### Q1a — sustained TSC mass-deposit feedback: zero measurable effect

The frozen Q1a arm re-seeds a physically-round Gaussian mass cloud (total mass M = 1.0) at the box
center each step, scattered through the engine's exact 27-cell TSC B-spline
(`cassi_mass_deposit.glsl`), and injects the shader's always-on field coupling
`EY += 0.001·ρ_mass·dt²`, `EI += 0.000707·ρ_mass·dt²`. The trace is **indistinguishable from the
control** (every entry matches to 3 decimals; the cumulative field difference is O(1e-6), below
display resolution). The `0.001·ρ_mass` coefficient couples the deposited mass into the field at
one part in a thousand of the mass density; at the probe's natural mass scale (M = 1.0 vs the field
seed amplitude 0.3) this is negligible. **Verdict: DOES NOT EMERGE** — the always-on mass feedback
does not scale the bubble. (At engine mass scales — ~1e7 total particle mass — the same coefficient
would be ~1e4× larger; this is the honest caveat, and a re-test at engine mass is a separate
pre-registration.)

### Q1b — source field-gain: transverse (x/y) imprint only, no axial z-compression

The Q1b arm injects the shader's `source_strength` field-gain at the live-sim value 0.5: a centered
Gaussian on EY plus an **offset** Gaussian on EI at `(0.7, 0.8, 0.6)·halfn` (the shader's Yin–Yang
separation). This is the **only** arm that moves the shape materially: σ_x/σ_y rises from 0.842 to
**1.285** (heading toward the doctrine's transverse φ = 1.618), while σ_x/σ_z rises only to
**0.528** — still prolate (≤ 0.6). The offset-EI source drives transverse (x/y) anisotropy, but it
does **not** compress the z-axis, so the oblate signature (σ_x/σ_z → 2.510) does not emerge.
**Verdict: DOES NOT EMERGE** on the primary σ_x/σ_z statistic (a Reported Negative); the transverse
σ_x/σ_y = 1.285 is REPORTED as the one positive partial signal (still below the 1.8–3.2 gate and
the φ reference).

### Q2 — field Poisson-gravity self-coupling (g=1): slightly more prolate, faster decay

The Q2 arm couples the field to its own Poisson potential through the engine's exact spectral solve
(`Φ̂ = −ρ̂/k²`, k=0 nulled, `L_i = 2·extent_i`) and 3-point central-difference gradient, using the
stated **g = 1** simplification of the river force, mapped to the scalar two-fluid through the
momentum–continuity divergence `S_grav = +G_N·∇·(m·∇Φ)`, `m = ρ·clamp((EY−EI)/ρ, 0, 0.72)`, with
G_N = 1.0. Gravity is attractive (verified: `S_grav > 0` at the seed peak), and it accelerates the
amplitude decay (peak/peak0 0.091 → 0.057) — but it does **not** compress z: σ_x/σ_z = **0.304**, a
hair **more** prolate than the control's 0.329. **Verdict: DOES NOT EMERGE** (more prolate, with the
amplitude-floor caveat). Self-gravity alone cannot produce the oblate record on this operator.

## Honest reframe

Wave 8 showed the sim's real operator is prolate (0.329), not oblate. Wave 9 rules out three
candidate mechanisms — the TSC mass-deposit feedback (negligible at probe mass), the source
field-gain (transverse-only, no z-compression), and the field's own (g=1) Poisson self-gravity
(more prolate). The doctrine's oblate reference σ_x/σ_z = 2.510 is, per the parallel provenance
audit, a **single-run Python-PDE output** with a seed-inherited transverse ratio and a mismatched
step label — **not an engine measurement**, and the engine has **no bubble-shape readout**. This
probe's verdicts therefore stand on their own physics: *on the sim's real operator, none of these
three mechanisms produces z-compression*. The oblate record — if it is real — must live in a sector
this scalar-field probe line cannot yet capture: the full river `g = 1+(φ⁶−1)q` chord factor, the
particle-nbody coupling (gravity acts on particles, not the field), the BH-accretion sector, the
dual (BCC) lattice / gradient-order-4 pass, or the RealSim dissipation. The operator is not the
carrier of the anisotropy; the source's Yin–Yang offset (Q1b) is the one lever that imprints
*transverse* shape — a pointer for any follow-up.

## Harness

- `verify_triaxial3d_feed.py` → `ALL CHECKS PASSED`:
  G1 seed-round (σ ratios 1.0000/1.0000, z-boundary mass 3.01e-23); G2 free 2400-step drift
  1.57e-04 (< 5e-3); G3a single-mode Poisson inversion 1.32e-15; G3b div(grad(u)) exact symbol
  8.09e-15; G3c gravity attractive (S_grav = 4.714e-02 at seed peak); G4 determinism bitwise for
  all four arms; G5a finite; G5b control σ_x/σ_z = 0.329 (wave-8 anchor reproduced exactly).

## The amplitude-floor calibration disclosure (per the prereg's dated amendment)

The pure control decays to peak/peak0 = **0.091** at t=2400 — the free dispersive wave's natural
end-state (the wave-8 anchor 0.329 *is* this 9.1% state). The frozen 10% amplitude-floor threshold
therefore sits *above* the baseline's own natural decay, so the floor is reported as a **caveat
flag** on the Q1a and Q2 verdicts rather than as an INCONCLUSIVE. A deterministic no-RNG σ_x/σ_z
≤ 0.6 is a definitive measured negative, not an unmeasurable one. No numeric pin was weakened; the
SUPPORTS (≥ 1.0) and DOES NOT EMERGE (≤ 0.6) thresholds are unchanged. Q1b (peak/peak0 = 0.343) is
cleanly above the floor.

## Traceability

- Re-run: `python research/helix_solver/triaxial3d_feed_probe.py` (~533 s; the owner's live Godot
  session competes for CPU, so wall time varies).
- Gates: `python research/helix_solver/verify_triaxial3d_feed.py` (~275 s) → `ALL CHECKS PASSED`.
- Files (new only): `triaxial3d_feed_prereg.md`, `triaxial3d_feed_probe.py`,
  `verify_triaxial3d_feed.py`, `triaxial3d_feed_report.md`. `triaxial3d.py` and every existing file
  are untouched.
- Ground truth: `cassi_two_fluid.glsl` (operator, source_ey/source_ei), `cassi_mass_deposit.glsl`
  (TSC deposit), `cassi_poisson.glsl` (spectral Poisson), `cassi_nbody_gravity.glsl` (river force),
  `cassi_physics_engine.gd` + `main.tscn` (source_strength/box params); wave-8
  `triaxial3d_simop_corr_report.md` (prolate anchor 0.329).
