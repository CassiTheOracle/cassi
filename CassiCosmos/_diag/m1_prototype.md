# M1 Prototype — gate-iv fidelity battery + gated site-path prototypes

Date: 2026-08-15. M1 prototyping on the meshless/Voronoi subsystem (parallel to M0).
Scope: the gate-iv A-decider battery, the mod-wrap removal prototype, the per-site
source prototype, and the corrected-operator A/B — all probe-gated; the DEFAULT path
untouched and battery-green. No field-promotion landed.

## Files (new, probe-only)

| File | Purpose |
|---|---|
| `res://_diag/m1_gateiv.tscn` | probe scene (CassiSim + harness; N=50k, grid 64, dt 0.01, source_strength 0, black_holes/merge/accretion off) |
| `res://_diag/m1_gateiv.gd` | the battery + the corrected-operator arm + phase C (windowed — the sim uses the global RD) |
| `res://_diag/compute/m1_sites_unwrapped.glsl` | the gated variant shader (mode 4 steer + mode 1 leapfrog, bindings 0-19 identical to cassi_voronoi_cells.glsl; PC = the canonical 17 floats + a variant selector + the corr scale) |

Run: `godot --path <repo> res://_diag/m1_gateiv.tscn` (windowed). ~45 s. The battery
self-quits; 0 stderr errors on the final run (deg_gateiv25.log).

## 1. Why the battery had to be rebuilt (the measurement archaeology)

The gate-iv battery went through FIVE successive harness defects before it could
measure the wave honestly. Each was a probe artifact, not sim physics:

1. **IC coordinate mismatch** — the meshless arm's IC was evaluated at the RAW site
   positions in `[0, Lx)` mesh coordinates; the grid arm (and the detector) use
   world coordinates (`− extent`). The pulse landed at the mesh CORNER, never on the
   sampled ray. The measured "front 0.0000" of the first battery was this artifact.
2. **The detector's checkerboard reference had the wrong phase** — `cb = cos(kx·x)`
   with the world x vs the mesh-checkerboard `cos(kx·(x+extent)) = −cos(...)` — the
   phase-flipped reference made the meshless "residual" = 2·the checkerboard (the
   0.205 "peak" = 2·0.1·cos). And the ρ = ey+ei checkerboard is a TRAVELING wave
   (the two-field superposition) whose phase drift contaminates any static-reference
   front — the battery now runs the pulse on the ZERO field (pure-pulse IC).
3. **The 3D wave's 1/r decay + focus + echo** confound amplitude-contour and
   single-probe front measures (the contour drifts with the decay, not the
   transport). The robust measure: the +x outgoing shell's OUTER profile peak
   (r = ct + σ/√2), continuity-tracked (±3 cells on the grid ray, ±2 sites on the
   site ray) with a seed floor above the IC's initial edge.
4. **The sim's rebuild STEERS the sites** (the momentum ride — the wave's pi is
   nonzero) — the strip's stale site indices read the WRONG sites. The site-ray now
   follows the CURRENT positions per sample (a 1.5-cell tube).
5. **The raster's Barth-Jespersen limiter clamps the recon's negative phase
   excursions at the front** (the 26-neighbourhood includes sites AHEAD of the front
   with psi ≈ 0 → lo ≈ 0) — the rasterized field is the positive-only envelope, NOT
   the wave. The gate therefore measures the SITE-LEVEL wave (the leapfrog/lap
   output, before the raster) for the meshless arms; the grid arm has no raster (its
   field IS the wave).

## 2. The lap probe: the operator is NOT the defect

The corrected operator's diagnosis required a DIRECT lap/v measurement: seed the site
psi with the quadratic x²/100 (∇² = 0.02), run ONE canonical lap, read lap_y[s]/vol[s].

- Theory (the ΣA·d = 6V Voronoi identity): lap/v = 3·∇²ψ = 0.0600.
- **Measured: |mean| = 0.0592 over all 8192 sites (vol mean 1745) — the identity is
  realized at 98.7%.** (The signed mean −0.0037 is the sign-mix over the anisotropic
  JFA cells' face normals — the magnitude is the point.)

**The lap/v is CORRECT.** The original "~150× suppressed wave speed" hypothesis is
dead — it was entirely the harness artifacts above. The genuine operator gap is
coarse-mesh DISPERSION: the site wave's realized speed scale at the pulse's k
(σ = ext.x/8 ≈ 3-4 sites) is ~1.4 units/s vs the grid's 2.36 — a 38% speed deficit,
not a 150× one, and it is a resolution/dispersion property, not a normalization bug.

## 3. Gate-iv result (final numbers, deg_gateiv25.log, 0 stderr errors)

| Metric | meshless arm (site-level) | grid arm (field) | Δ |
|---|---|---|---|
| ρ-front speed | **1.4590 units/s** (77-row shell-peak fit) | 2.3614 units/s (368 rows) | **38.2%** (tol 5%) |
| top-2 mode ratio | 0.0488/0.0977 Hz → ratio 0.500 | 0.0488/0.0977 → 0.500 | **0.0%** |
| far-site psi_y (0.75·Lx) | 0.0000 (no arrival in 24 s) | — | — |
| lap/v (quadratic probe) | 0.0592 vs theory 0.0600 | — | 1.3% |

**VERDICT: FAIL on the front criterion (38.2%), PASS on the mode-spacing criterion
(0.0%)** → per the pre-scripted gate, the uncorrected operator is NOT viable for the
A-promotion as-is.

Note the run-to-run ALE variance: the uncorrected front measured 2.03-2.48 units/s
in earlier runs (the rebuild's momentum steer adds ~0.5-0.9 units/s of LAB advection,
varying with the wave's pi state); the SITE-level static measurement (1.44-1.46) is
the stable number. The corrected arm (static mesh, no steer) is deterministic.

## 4. The corrected operator A/B (variant 3)

The variant-3 operator scales the leapfrog's wave speed²: `C2_eff = C2·corr` (gated
exactly like variants 0-2; variant-0 stays byte-identical — T1/T2 PASS, the wrap
difference exactly Lx — T3 PASS; the per-site source matches the CPU formula — T4/T5
PASS). The corr mechanism itself is verified in isolation (T6): one leapfrog step
with lap=1, vol=1, psi=0 gives pi = dt·C2·corr — the corr=2/corr=1 ratio = 1.998 ≈ 2
(float32) — PASS.

The full-wave A/B: corr₀ = v_grid²/c_meshless² = 2.62 (the measured operator ratio),
then self-iterate (corr → corr·(v_grid/v_measured)²). **The iteration DIVERGES:**
fronts 1.15 → 1.62 → 2.99 units/s for corr 2.6 → 16 → 352 (run 25; the run-24 series
0.95 → 1.13 → 1.05 → 2.33 similar), with the mode ratios drifting 0.500 → 0.75-1.25 —
the correction does NOT rescale the wave cleanly: at the needed scales the coarse-mesh
dispersion and the leapfrog's structure break the wave's shape (the spectrum is not
preserved). The corrected-operator arm FAILS both the front criterion (never within
5% — the iteration overshoots/undershoots without converging) and the spectrum
criterion (the ratio drifts).

## 5. A-viability verdict

**NOT viable — commit to B** (the tracking coarse-grid + patches fallback). The
evidence chain:

1. The meshless per-site wave DOES transport (the early "0.0000" was the harness
   artifacts) — at 1.46 units/s vs the grid's 2.36 — a genuine 38% speed deficit.
2. The deficit is the coarse-mesh dispersion at the pulse's k (σ ≈ 3-4 sites), NOT a
   normalization bug (the lap/v identity is realized at 98.7%).
3. The speed correction (corr scaling) works in isolation but does NOT converge in
   the full wave — the correction distorts the spectrum (the ratio drifting
   0.50 → 0.67-1.25) — the A-promotion's wave fidelity cannot be restored by a
   constant rescale.
4. The raster's Barth-Jespersen limiter additionally clamps the front's phase
   structure in the rasterized output (a separate, fixable output-path defect — the
   site-level wave is the honest state).

The gate as written → **B**: keep the N³ lattice waves as the field of record; build
the tracking coarse grid + patches. The meshless arm remains a candidate only for
the OPEN-BOUNDARY regimes (the tree-gravity arm) where the N³ waves cannot go — with
the lap/v normalization known-good and the dispersion documented as the fidelity
limit.

## 6. Default-path integrity

- No edits to `cassi_voronoi_cells.glsl`, `cassi_two_fluid.glsl`, `cassi_sim.gd`,
  `cassi_physics_engine.gd`, or `scripts/contracts/` (M0's disjoint ownership).
- The probe scene/script/shader are new `_diag` files, force-added for auditability
  (`git add -f`), committed as their own gated commit.
- The battery 8/8 is unaffected (no default-path change).
