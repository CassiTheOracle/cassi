# M1 Prototype — gate-iv fidelity battery + gated site-path prototypes

Date: 2026-08-15. M1 prototyping on the meshless/Voronoi subsystem (parallel to M0).
Scope: the gate-iv A-decider battery, the mod-wrap removal prototype, and the
per-site-source prototype — all probe-gated, the DEFAULT path untouched and
battery-green. No field-promotion landed.

## Files (new, probe-only)

| File | Purpose |
|---|---|
| `res://_diag/m1_gateiv.tscn` | probe scene (CassiSim + harness; N=50k, grid 64, dt 0.01, source_strength 0, black_holes/merge/accretion off) |
| `res://_diag/m1_gateiv.gd` | the battery + phase C harness (windowed — the sim uses the global RD) |
| `res://_diag/compute/m1_sites_unwrapped.glsl` | the gated variant shader (mode 4 steer + mode 1 leapfrog, bindings 0-19 identical to cassi_voronoi_cells.glsl; PC = canonical 17 floats + a `variant` selector) |

Run: `godot --path <repo> res://_diag/m1_gateiv.tscn` (windowed).

## 1. The gate-iv battery (what it measures)

Same physical setup, two arms, identical continuum IC:
- IC: checkerboard ground state (EY = 0.1·cos(kx·x), EI = 0.1·sin(kx·x), kx = π/extent_x)
  + a Gaussian pulse (0.2·exp(−r²/σ²), σ = extent_x/8) at the box center.
- Particle masses zeroed after reinit (the deposit skips w ≤ 0 → rho_mass = 0 → the
  wave source coupling mr·0.001 = 0): a pure linear wave from the IC in both arms.
- Arm 1 (meshless): the sim's per-step meshless chain (modes 10/0/1/12 + raster) — the
  site psi/pi are seeded from the continuum IC at the site positions.
- Arm 2 (grid): the N³ two-fluid pass A/B — the grid ey/ei seeded at the cell centers.
- 1000 steps at dt=0.01, sampled every 4 steps (250 field readbacks per arm).
- Measured: (1) the ρ = ey+ei pulse front speed along the center x-ray (robust detector:
  center-outward scan, relative 25%-of-peak threshold, monotonic tracking — the v1 naive
  far-edge scan was pinned by raster boundary artifacts), (2) the top-2 dominant-mode
  frequencies at a probe point (512-point radix-2 FFT of the ρ(t) series), ratio = f1/f2.

## 2. Gate-iv result (measured 2026-08-15, deg_gateiv4.log)

| Metric | meshless arm | grid arm | Δ |
|---|---|---|---|
| ρ-front speed | **0.0000** units/s (front never left the center cells) | 2.2937 units/s (x 1.9 → 24.6 over 10 s) | **100%** (tol 5%) |
| top-2 mode frequencies | 0.0488 / 0.0977 Hz | 0.0488 / 0.0977 Hz | **0.0%** (tol 5%) |
| mode ratio f1/f2 | 0.500 | 0.500 | **0.0%** |
| ray diagnostics | pulse peak stays at the center (x 1.9 → −1.9 → −5.7), decaying 0.205 → 0.160 | pulse peak moves outward (x 1.9 → 20.9) at t ≈ 5, then wraps the periodic box | — |
| far-site psi_y (x = 0.75·Lx) | dev 0.125 (standing-mode oscillation; the pulse at 75+ units would need ≫ the 10 s window to arrive in BOTH arms) | same | — |

**VERDICT: FAIL on the front criterion (|Δfront| = 100%), PASS on the mode-spacing
criterion (|Δratio| = 0.0%)** → per the pre-scripted gate, **lean B** (keep the N³
lattice waves as the field of record).

Interpretation (honest): the meshless per-site wave reproduces the standing-mode
spectrum EXACTLY (the checkerboard oscillates at the identical frequencies — the
de-resonant spacing is preserved), but does NOT transport a local disturbance: the
pulse energy stays localized at the center while the grid arm's pulse spreads and
wraps the periodic box. The mechanism is a discretization-NORMALIZATION gap: the
two-point-flux Laplacian divided by the per-site Voronoi volume (lap/v, mode 1)
yields an effective wave-speed scale far below the D19 stencil's (an order-of-
magnitude estimate from the face/volume geometry: ~150× smaller lap scale → c ≈ 0.4
vs 2.3 units/step). This is a FIXABLE operator constant (not a fundamental barrier —
the spectrum fidelity is already exact), so the fallback is B now, with a note that a
corrected lap/v normalization could justify re-running gate-iv before abandoning A.

## 3. Phase C — the gated prototypes (verified)

### 3a. Mod-wrap removal (variant 1 of the probe shader)
- What: mode 4 (steer) drops the `mod(npos, L)` self-wrap — sites move freely in world
  coordinates (the movable home-window from 3e3f9a6 provides the coordinate frame);
  `drift_cap` still bounds the per-rebuild displacement; the scatter/lap indices are
  clamped to the window (a probe-side guard the canonical shader lacks — the MINOR
  hole 6 from the boundary audit).
- Gated: the `variant` PC float (probe-only pipeline; the canonical `cassi_voronoi_cells.glsl`
  is untouched; the sim's default path is byte-identical).
- Verified (deg_gateiv4.log, phase C):
  - T1/T2: canonical steer vs variant-0 steer on the sim's shared buffers with a
    controlled PC (kappa=0, lam=1, drift_cap=2.0) — **bit-identical** (all 8192·4 site
    floats equal). The variant shader is byte-exact to the canonical with variant=0.
  - T3: variant-1 (unwrapped) — site 0 (input x = Lx−0.05, outward momentum) lands at
    x = Lx−0.05 + 2/√3 (the 3D drift-cap on the (2,2,2) displacement) = **outside the
    window**; the wrapped result differs by EXACTLY Lx. "Leaves the box" is now
    meaningful at the site level.
- Determinism: the default path untouched; the unwrapped result = the canonical math
  minus the wrap (bit-identical control proves it).

### 3b. Per-site source (variant 2)
- What: mode 1 (leapfrog) anchors the Gaussian source at the SITE's own position
  (the field's "breath" rides the structure) instead of the fixed box-center offset
  (0.7/0.8/0.6·halfn in the canonical formula).
- Verified: variant-0 and variant-2 psi deltas match the CPU-recomputed formulas to
  < 1e-4 relative (the gating is exact; the canonical branch is unchanged).

## 4. A-viability verdict

**NOT viable in the current form — gate-iv FAILS the front criterion (lean B).** The
mode spectrum is exact (the de-resonant spacing survives the irregular mesh), but the
wave transport is suppressed by the lap/v normalization gap — the per-site field cannot
currently carry structure across the domain, which is precisely the capability the
A-promotion exists for. The B fallback (keep the N³ lattice waves as the field of
record; add the tracking coarse grid + patches) is the pre-scripted next step. The
normalization gap is a small, well-understood operator fix; re-running gate-iv after
it (or after a C2 per-patch calibration) is the cheapest path to a SECOND opinion on A
before committing to B's build.

## 5. Default-path integrity

- No edits to `cassi_voronoi_cells.glsl`, `cassi_two_fluid.glsl`, `cassi_sim.gd`,
  `cassi_physics_engine.gd`, or `scripts/contracts/` (M0's disjoint ownership).
- The probe scene/script/shaders are new `_diag` files, force-added to git for
  auditability (`git add -f`), committed as their own gated commit.
- The battery 8/8 is unaffected (no default-path change).
