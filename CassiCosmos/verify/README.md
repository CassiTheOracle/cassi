# Verify battery — one-command runner

Runs the whole Cassi GPU-sim verify battery (30 arms) in sequence, captures each
arm's exit code, and exits 0 only when every arm passes.

## How to run

From the space-sim project directory (where `project.godot` lives), with the
Godot console exe:

```
"C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" --path . --headless -s res://verify/run_all.gd
```

- `--headless` on the **runner** is fine and recommended (the runner itself
  never touches a RenderingDevice). Dropping it also works — only the runner's
  own window appears.
- The **arms always run windowed** (`--path . res://scenes/<scene>.tscn`):
  never `--headless` an arm — this rig's global RenderingDevice has no headless
  device.
- Exit code: `0` = all 30 passed; `1` = at least one failed.
- The runner prints a progress line per arm and a summary table; failed arms
  get their last 15 stdout/stderr lines printed.
- Per-arm logs: `res://_diag/battery_logs/armNN_<name>.log` (gitignored).
- Per-arm timeout: `ARM_TIMEOUT_SEC` const at the top of `run_all.gd`
  (default 240 s). A hung arm is killed with `taskkill /T /F` and counted FAIL.
  (The console exe is a wrapper that spawns the real Godot process, so the
  process *tree* must be killed, or the orphan keeps the GPU and a window.)

## The 27 arms

| # | Scene | What it verifies |
|---|-------|------------------|
| 1 | verify_fft | GPU FFT/Poisson round-trip identity (per-axis + full 3D) and point-mass / Gaussian solve checks, at N=64 and N=256 |
| 2 | verify_fmm | FMM/tree gravity: 8192-point octree build+walk on a local RD vs the numpy prototype (G16–G18 in research/meshless/stage5_verify.py) |
| 3 | verify_gravity_modes | 5-mode gravity selector, truncated-Plummer ICs, river calibration/attractor init, cached-acc KDK, BH toggle, RealSim dissipation |
| 4 | verify_merge | Particle-merge shader on a planted 8-particle input (local RD); dump for stage6_merge.py (G28/G29) |
| 5 | verify_meshless_sim | Meshless arm vs grid arm from the SAME initial condition — cross-solver agreement (G11/G12′ in stage4_verify.py) |
| 6 | verify_meshless_stability | Meshless arm under live-sim flat-noise conditions: 2000 steps, Voronoi site-spread and finiteness gates |
| 7 | verify_particle_vfx | Instancer pipeline through each default-off visual feature, plus the shader-exact legacy size/color contract |
| 8 | verify_phi_box | φ-aspect box battery: anisotropic 19-point stencil residuals, ellipsoid ring test, box-mode de-resonance |
| 9 | verify_ring | Wave-front ring roundness: 19-point stencil dispersion anisotropy, symbol[110]/symbol[100] ∈ [0.985, 1.015] |
| 10 | verify_river_law | River-law gravity upgrade: q→0 Newtonian limit, point-mass profile, mode toggle, no-NaN, reinit regression |
| 11 | validate_sim_ui | sim_ui.gd loads cleanly and the VFX controls exist (exit 0 = parse/load clean) |
| 12 | verify_survey | Survey exporter: programmatic snapshot vs a direct frozen-buffer reference read (byte-exact gate in survey_read.py) |
| 13 | verify_synth | Audio-reduce cascade meter: φ-spaced plane-wave rung energies vs analytic references (G22/G23) |
| 14 | verify_volumetric | Volumetric ray-marched render of the analytic φ-attractor field (PNG + RGBAF pixel dump; G35) |
| 15 | verify_voronoi3d | GPU JFA Voronoi + per-cell two-fluid wave vs the numpy spectral reference (stage1_verify.py) |
| 16 | verify_voronoi3d_moving | Moving mesh: steering + periodic ALE remap + JFA refresh (stage2_verify.py) |
| 17 | verify_meshless_gravity | Meshless TREE gravity over the sim's real source buffers, rebuilt on a local RD (G30/G31) |
| 18 | verify_river_isotropy | River azimuthal anisotropy: ring probes on N=64 and N=128, shader-vs-estimator identity, pinned trilinear baseline |
| 19 | verify_merge_sim | Particle merge wired into the LIVE sim: monotone merge count, mass conservation, dead-marking, φ⁻² gate (G52–G54) |
| 20 | verify_meshless_reconstruct | AREPO-style per-cell LINEAR reconstruction: linear exactness + interface-jump smoothness (R1/R2) |
| 21 | verify_meshless_sim_aniso | The verify_meshless_sim cross-solver battery at the φ-aspect box |
| 22 | verify_particle_vanish | "All particles vanish" diagnostic: direct + `_process` drive paths, full buffer readback timeline |
| 23 | verify_voronoi3d_aniso | The verify_voronoi3d battery at the φ-aspect box |
| 24 | verify_voronoi3d_moving_aniso | The verify_voronoi3d_moving battery at the φ-aspect box |
| 25 | verify_autotrack | Auto-track live-band tracker: robust-percentile match, min-span floor, damped glide (G49–G51) |
| 26 | verify_falsify | Falsification meter: w₀ estimator port vs falsify_wo.py references, meter wiring (F1–F3) |
| 27 | verify_mind_engine | Mind-engine no-op gate: attractor-ratio deposit stays at the fp32 floor; off-ratio evolution conserves charge |
| 28 | verify_bh_accretion_engine | BH accretion in the standalone engine (local RD): exact mass conservation (G55), swallowed-dead/no-deposit (G56), toggle-off bit-identity (G57) |
| 29 | verify_merge_engine | Particle merge in the standalone engine (local RD): merge count + mass conservation (G52), dead-marking/no-deposit (G53), φ⁻² low-q no-merge gate (G54) |
| 30 | verify_multigrid_engine | Cascade-multigrid arm in the standalone engine (local RD): coarse-level Φ vs direct reference (G58), fine-dominant near-field match (G59), honest placement-bias ring metric (G60) |

## Expected runtime

Measured 2026-08-14 on the RX 7900 XTX rig: **≈ 8–9 minutes** for a fully
passing tree (arms 1–60 s each; the slowest are verify_fft ~35 s,
verify_meshless_sim_aniso ~25 s, verify_particle_vanish ~60–100 s). The
same-day full 30-arm run with three arms hitting their 240 s timeout took
17 minutes. Arms run strictly serially because they share the GPU. First run
after a shader change can be slower (SPIR-V recompile).

## Special launch conventions (read before touching the battery)

- **All arms windowed, never headless.** The sim's global RD has no headless
  device on this rig. The local-RD arms (verify_fmm, verify_merge,
  verify_synth, verify_voronoi3d, verify_voronoi3d_moving,
  verify_meshless_reconstruct, verify_meshless_gravity, verify_mind_engine,
  verify_bh_accretion_engine, verify_merge_engine, verify_multigrid_engine —
  the last three instantiate the standalone physics engine on their own RD)
  create their own RenderingDevice and are display-independent
  (verify_voronoi3d's header even documents headless as acceptable), but the
  battery runs them windowed uniformly.
- **verify_particle_vanish is a diagnostic, not a gate**: it accepts an
  optional `-- --river` control arg (tree off, gravity_mode=0) and by design
  always exits 0. PASS means "the timeline completed"; failure findings
  (NaN/off-screen particles) appear in its printed timeline. The battery runs
  the default tree arm.
- **verify_autotrack / verify_falsify / verify_particle_vfx** headers show an
  `-e` editor-form variant; the plain `--path . res://scenes/<scene>.tscn`
  form is what the battery uses (it works for all three).
- **Stale shader artifacts**: if an arm fails with `No loader found for
  resource: res://compute/...` or `All the shader bindings ... not provided`,
  run `Godot_v4.7.1-stable_mono_win64_console.exe --headless --import` once
  (regenerates `.godot/imported/` after shader edits) and re-run.
- Each arm dumps its own JSON/raw artifacts to `res://_diag/` (gitignored)
  for the numpy gates; those gates are not re-run here — the arm's exit code
  is the battery contract.
