# Verify battery — one-command runner

Runs the whole Cassi GPU-sim verify battery (43 arms) in sequence, captures each
arm's exit code, and exits 0 only when every arm passes.

## How to run

From the space-sim project directory (where `project.godot` lives), with the
Godot console exe:

```
"C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" --path . --headless -s res://verify/run_all.gd
```

- `--headless` on the **runner** is fine and recommended (the runner itself
  never touches a RenderingDevice).
- Every child scene arm runs **windowed**, sequentially, as
  `--path . res://scenes/<scene>.tscn`; child commands never receive
  `--headless`. Both the sim's global RenderingDevice and the arms' local
  RenderingDevices require a real window on this rig.
- Exit code: `0` = all 43 passed; `1` = at least one failed.
- The runner prints a progress line per arm and a summary table; failed arms
  get their last 15 stdout/stderr lines printed.
- Per-arm logs: `res://_diag/battery_logs/armNN_<name>.log` (gitignored).
- Per-arm timeout: `ARM_TIMEOUT_SEC` const at the top of `run_all.gd`
  (default 240 s). A hung arm is killed with `taskkill /T /F` and counted FAIL.
  (The console exe is a wrapper that spawns the real Godot process, so the
  process *tree* must be killed, or the orphan keeps the GPU and a window.)

## Standalone passive process-clock lab (not an ARMS battery member)

This is a separate CPU-only/default-off lab; it is **not** included in the
`ARMS` list or the one-command battery above. From `CassiCosmos/`, launch it
windowed with the console executable:

```
"C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" --path . res://scenes/verify_process_clock.tscn
```

The frozen preregistration is
[`research/process_time/common_lapse_prereg.md`](../research/process_time/common_lapse_prereg.md).
The raw receipt is written to
`res://_diag/process_time/common_lapse_receipt.json`. The scene has no
RenderingDevice/GPU/readback dependency, makes no production/default-path
common-lapse change, and reports implementation/reparameterization PASS/FAIL
only—not evidence for universal physical time.

## Standalone Field Particles verification (not ARMS members)

Field Particles has three separate windowed scenes. They remain outside `ARMS`
so the configured runner continues to prove default-off compatibility without
changing its established contract:

```
"C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" --path . res://scenes/verify_field_particles.tscn
"C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" --path . res://scenes/verify_field_particle_integration.tscn
"C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" --path . res://scenes/verify_field_particles_motion.tscn
```

`verify_field_particles` checks the pinned source field and its evolution.
`verify_field_particle_integration` checks the hidden single-particle control
through the real `CassiSim` renderer. `verify_field_particles_motion` checks
that the public setting displays two field particles, moves both in the
expected directions, preserves their field charge, keeps point-particle
physics off, and switches cleanly off and back on.

All three must exit 0 after a Field Particles change. Changes to
`cassi_physics_engine.gd`, `cassi_sim.gd`, or the field shader also require the
full configured battery before release. Frozen registrations and measured
results live in `research/field_particles/`.

## Standalone GPU trajectory probe (not an ARMS member)

`verify_trajectory_probe.tscn` is a windowed GPU probe that reads the passive
trajectory recorder — a default-off, read-only observation path inside
`cassi_physics_engine.gd`. It stays outside `ARMS` so the configured runner
continues to prove default-off compatibility without changing its contract.
Run it from `CassiCosmos/` with the console executable:

```
"<console exe>" --path . res://scenes/verify_trajectory_probe.tscn -- --mode=shell --recorder=on \
    --steps=1000000 --particles=8192 --tracers=4096 \
    --sample-stride=4096 --sample-capacity=256 --merge-cadence=64
```

`--mode=shell` runs the nested-shell initial condition with merging disabled;
`--mode=ancestry` repeats the same seeded geometry with the existing
particle-merge rule enabled under a fixed coherent field plant. `--recorder=off`
writes only the tracer endpoints and is the paired dynamics-neutrality control.
The frozen registration is
[`research/matter_formation/trajectory_shell_prereg.md`](../research/matter_formation/trajectory_shell_prereg.md);
runs shorter than the registered 1,000,000 accepted steps are reported with the
status `IMPLEMENTATION CHECK` and a verdict of `INCONCLUSIVE`, so they are never
read as evidence either way.

Every run writes `receipt.json`, the raw recorder arrays, and `analysis.json`
under `res://_diag/matter_formation/trajectory_<mode>/`. That output tree is
gitignored, so receipts and raw arrays stay out of commits; only the harness,
analyzer, and registration are tracked. Score a run with the standalone
analyzer, which consumes only the receipt and the binary payload:

```
python tools/analyze_trajectory_probe.py _diag/matter_formation/trajectory_shell
```

The probe measures radial shell occupancy and contrast, boundary crossings,
turnarounds, and the merge-edge ancestry graph. It does not dispatch the
condensation scanner, spawn black-hole records, or transfer field mass to the
particle population: recorded events are particle-merge hops only, and the
probe is not a test of the fluid-to-matter collapse pathway.

The recorder-off control compares the arrays the harness retains — the 4,096
sampled tracer identities and their initial and final states — and those arrays
match byte for byte across the on/off pair at matched configuration. Sampled
tracer motion therefore carries no recorder perturbation; the comparison does
not cover the unsampled particles or the field state, which rely on the
recorder's read-only dispatch contract rather than on this measurement.

## The arms

The authoritative arm list is the `ARMS` const in `verify/run_all.gd` (43 arms).
The table below documents each arm:

| # | Scene | What it verifies |
|---|-------|------------------|
| 1 | verify_fft | GPU FFT/Poisson round-trip identity (per-axis + full 3D) and point-mass / Gaussian solve checks at N=64 and N=256, including twiddle initialization for direct dispatches |
| 2 | verify_fmm | FMM/tree gravity: 8192-point octree build and complete stackless walk on a local RD, with a terminal root escape; dump for the numpy prototype (G16–G18 in research/meshless/stage5_verify.py) |
| 3 | verify_gravity_modes | 5-mode gravity selector, truncated-Plummer ICs, river calibration/attractor init, cached-acc KDK, BH toggle, RealSim dissipation |
| 4 | verify_merge | Particle-merge shader on a planted 8-particle input (local RD); dump for stage6_merge.py (G28/G29) |
| 5 | verify_meshless_sim | Meshless arm vs grid arm from the SAME initial condition — cross-solver agreement (G11/G12′ in stage4_verify.py) |
| 6 | verify_meshless_stability | Meshless arm under live-sim flat-noise conditions: 2000 steps, Voronoi site-spread and finiteness gates |
| 7 | verify_gridless_physics | Production site-native field, topology, tree-force, telemetry, snapshot and CSR contracts; exact original-ID nearest-site queries, sparse/window-edge/tie cases, and particle-query cache epochs |
| 8 | verify_phi_box | φ-aspect box battery: anisotropic 19-point stencil residuals, ellipsoid ring test, box-mode de-resonance |
| 9 | verify_ring | Wave-front ring roundness: 19-point stencil dispersion anisotropy, symbol[110]/symbol[100] ∈ [0.985, 1.015] |
| 10 | verify_river_law | River-law gravity upgrade: q→0 Newtonian limit, point-mass profile, mode toggle, no-NaN, reinit regression |
| 11 | validate_sim_ui | sim_ui.gd loads cleanly and the VFX controls exist (exit 0 = parse/load clean) |
| 12 | verify_particle_vfx | Instancer pipeline through each default-off visual feature, plus the shader-exact legacy size/color contract |
| 13 | verify_presentation_layers | Opt-in particle, macro-site, velocity-ribbon, camera-following sky, and site-volume-history rendering contracts |
| 14 | verify_survey | Survey exporter: frozen authoritative field and particle buffers, extent metadata, and byte-exact particle comparison; separate field/payload gate in survey_read.py |
| 15 | verify_synth | Audio-reduce cascade meter: φ-spaced plane-wave rung energies vs analytic references (G22/G23) |
| 16 | verify_volumetric | Volumetric ray-marched render of the analytic φ-attractor field (PNG + RGBAF pixel dump; G35) |
| 17 | verify_voronoi3d | GPU JFA Voronoi + per-cell two-fluid wave vs the numpy spectral reference (stage1_verify.py) |
| 18 | verify_voronoi3d_moving | Moving mesh: steering + periodic ALE remap + JFA refresh (stage2_verify.py) |
| 19 | verify_meshless_gravity | Meshless TREE gravity over the sim's real source buffers, rebuilt on a local RD (production G30/G31); also dumps rejected site-target G61/G62 and direct-refit G63 receipts plus hierarchical-refit G70/G71 receipts, which are evaluated by their numpy gates and do not control the arm exit |
| 20 | verify_river_isotropy | River azimuthal anisotropy: ring probes on N=64 and N=128, shader-vs-estimator identity, pinned trilinear baseline |
| 21 | verify_merge_sim | Particle merge wired into the LIVE sim: monotone merge count, mass conservation, dead-marking, φ⁻² gate (G52–G54) |
| 22 | verify_meshless_reconstruct | AREPO-style per-cell LINEAR reconstruction: linear exactness + interface-jump smoothness (R1/R2) |
| 23 | verify_meshless_sim_aniso | The verify_meshless_sim cross-solver battery at the φ-aspect box |
| 24 | verify_particle_vanish | "All particles vanish" diagnostic: direct + `_process` drive paths, full buffer readback timeline |
| 25 | verify_voronoi3d_aniso | The verify_voronoi3d battery at the φ-aspect box |
| 26 | verify_voronoi3d_moving_aniso | The verify_voronoi3d_moving battery at the φ-aspect box |
| 27 | verify_falsify | Falsification meter: w₀ estimator port vs falsify_wo.py references, meter wiring (F1–F3) |
| 28 | verify_mind_engine | Mind-engine no-op gate: attractor-ratio deposit stays at the fp32 floor; off-ratio evolution conserves charge; full-field seeding resets state with exact EY/EI readback and stable RIDs; canonical native Qi snapshots are hash-bound, monotonic, idempotent, projected deterministically, and isolated exactly from the PDE field |
| 29 | verify_field_intelligence | Default-off bit identity; fixed P/e and 128-byte header ABI; finite bounded learning; six-target learned-vs-clear controls; exact snapshot/restore; render purity; same-list visual receipt; reinitialization ownership (FI0–FI9) |
| 30 | verify_bh_accretion_engine | BH accretion in the standalone engine (local RD): exact mass conservation (G55), swallowed-dead/no-deposit (G56), toggle-off bit-identity (G57) |
| 31 | verify_merge_engine | Particle merge in the standalone engine: local-RD merge count + mass conservation (G52), dead-marking/no-deposit (G53), φ⁻² low-q no-merge (G54), global no-readback list conservation/cadence/query-readiness (G102), and two-cadence canonical motion preservation (G103) |
| 32 | verify_multigrid_engine | Cascade-multigrid engine: coarse Φ reference, near-field recovery, and placement-bias ring metric (G58–G60) |
| 33 | verify_rho_front | φ-locked density-front speed and radial-symmetry gates |
| 34 | verify_eps_gap | Pure-ε decoupling, gap frequency, and non-propagation gates |
| 35 | verify_subsonic_step | Exact particle-merge transverse-speed threshold gate |
| 36 | verify_omega_invariant | ω₀²-independent density-front speed and widened ε-gap gate |
| 37 | verify_tree_hier_refit_engine | Default-off retained-tree moment refit: 32 finite engine steps, forced-full force parity, pre-transition refits, and mandatory full rebuild on the first preparation after a site-topology generation change (G72) |
| 38 | verify_particle_world_agent | Canonical particle-program validation, pure preview, decoupled-engine authoritative Apply, cache/render publication, idempotency and conflict rejection, one explicit step, and byte-exact automatic Undo (PWA0–PWA8) |
| 39 | verify_rotation_stress | Default-off engine byte identity; conservative matter–Qi linear/angular exchange and heat ledger; φ⁻¹ interscale transfer/null controls; merge-spin quaternion orientation; 64-step finite stability; explicit conservative scale-boundary reservoirs with a byte-zero closed contract (G78–G82, G101) |
| 40 | verify_rotation_end_to_end | Repeatable live production regression: a real merge acquires canonical orbital angular momentum, persistent spin causally advances resolved orientation, bounded publication matches the GPU state, and particle/environment momentum ledgers close (G97–G100) |
| 41 | verify_physical_radiation | Immutable model/unit/snapshot rejection contracts; grouped Planck/CIE/slab references; real global-RD spectral formal solution against the independent CPU value; spatial/spectral convergence; one-way provenance; allocation reuse (PR-G1–G6, PR-G10, PR-G12 for the implemented P0/P1 scope) |
| 42 | verify_coupled_radiation_engine | Hash-bound supplied-material extensive-state solver; null/affine/frequency/LTE/thermal references; accepted-step batching; checkpoint identity; local-RD `CassiPhysicsEngine` scheduler integration; default-off core bit identity; fail-closed setup and resource lifecycle (CR-G0–CR-G8) |
| 43 | verify_observatory_integration | Production-scene Scientific/Observatory/Cinematic and independent source selection; prescribed spectral pixels; fail-closed coupled-source diagnostics; solver-byte preservation; still/raw-XYZ/sidecar capture; quality, history, camera, and lifecycle behavior (PR-G0, PR-G6, PR-G11 plus Observatory regressions) |

## Expected runtime

Measured 2026-09-09 on the RX 7900 XTX rig: **397 seconds (6m37s)** for a
fully passing 43-arm tree. Arms commonly take 1–60 seconds; the slowest in that
run were `verify_particle_vanish` (52 s), `verify_gravity_modes` (48 s) and
`verify_fft` (38 s). A prior full run with three arms hitting their 240-second
timeout took 17 minutes. Arms run strictly serially because they share the GPU.
The first run after a shader change can be slower while SPIR-V recompiles.

## Special launch conventions (read before touching the battery)

- **All arms windowed, never headless.** `run_all.gd` launches every child
  scene arm sequentially with `--path . res://scenes/<scene>.tscn`; both the
  sim's global RenderingDevice and the arms' local RenderingDevices require a
  real window on this rig.
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
