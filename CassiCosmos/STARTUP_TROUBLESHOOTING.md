# Startup Troubleshooting — Godot Space Sim

Symptoms seen 2026-08-11: the sim appears to HANG at startup (black window,
no UI, no output for minutes) after several restarts with different settings.
Two independent causes were found and fixed:

## 1. Gaussian-ball IC init storm (CODE — fixed in `scripts/cassi_sim.gd`)

`scenes/main.tscn` pins `initial_condition = 1` (Gaussian ball). The Gaussian
arm of `_init_particles()` used REJECTION sampling: draw N(0, σ) positions and
keep only those with r ≤ r_max. The default single cluster sits at
(0 + cluster_separation, 0, 0) = (60, 0, 0), so

    r_max = fr·extent − |center|_∞ = 0.9·75 − 60 = 7.5

with σ = cluster_radius = 50 → acceptance P(χ₃ ≤ 0.15) ≈ 6e-4 → ~660 draws
per particle (40 % hit the 1000-draw cap) → **0.415 ms/particle → ~17 min for
2.5M particles**. Perceived as a hang, independent of UI settings (the scene
pins the profile).

Fix: the Gaussian arm now draws rejection-free via inverse CDF — the truncated
radial CDF `F(z) = erf(z) − (2/√π)·z·e^(−z²)`, `z = r/(√2σ)` (already used for
velocities) inverted by 24-step bisection; direction via the same uniform
th/ph draw as the Plummer arm. Exact same distribution, O(1) per particle.
Result: startup "Universe ready" at ~43–50 s (was never-finishing).

The other two IC profiles were already rejection-free (Plummer inverse-CDF,
uniform u^(1/3)).

## 2. Stale `.godot/shader_cache/` (ENVIRONMENT)

After many restarts + repeated runs, the cached shaders can go stale: the sim
starts, "shaders ready" prints, but forces read back as ZERO and verify
checks fail (e.g. `verify_river_law` 7/17 with acc = 0.0). Fix: delete the
cache and re-import (below). After that, `verify_river_law` is 17/17 again.

## Ordered recovery checklist

1. **Process check first** — ONE Godot at a time, always:
   `tasklist | findstr /i Godot`
   Kill only zombie console-exe game processes from crashed runs (they hold
   the GPU and the import locks). NEVER kill the mono editor; if it is open
   with this project, close it before running the sim (it locks `.godot/`
   and contends for the GPU).
2. **Delete the shader cache** (stale-cache symptom: zero forces / weird
   physics with "shaders ready"):
   `rm -rf godot/space-sim/.godot/shader_cache`
3. **Fresh import** (let it finish; it exits on its own):
   `"<Godot_v4.7-stable_win64_console.exe>" --path godot/space-sim --import`
4. **If still broken: nuke the whole cache and re-import** (slower, full
   reimport):
   `rm -rf godot/space-sim/.godot` then repeat step 3.
5. **Launch** the sim (or a verify scene) and wait for
   `[CassiSim] Universe ready` — with 2.5M particles a clean start takes
   ~45–60 s; it is NOT hung while the console shows init progress.

## Serial-Godot rule

NEVER run two Godot instances concurrently on this GPU — spurious failures
(shader import races, GPU contention, startup wedges). One instance at a
time; close the editor or quit the running sim before launching another.

## Notes

- `.glsl.import` files are rewritten by every Godot run — never stage/commit
  them. `comp.spv` and `.godot/` are likewise never committed.
- The Gaussian-IC fix lives in `scripts/cassi_sim.gd` (the Gaussian arm of
  `_init_particles()`); the verify scenes' tolerances were untouched.
- `verify_gravity_modes.tscn` requires the RealSim verify section in
  `scripts/verify_gravity_modes.gd` to parse (lines ~865-867 use `:=`
  inference from a `Node3D`-typed `sim` — type them explicitly, e.g.
  `var DEF_D: float = sim.realsim_drag`).
