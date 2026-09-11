# Verification

Two tiers: **one production smoke gate** — the default-path contract — and
**standalone probes** that are launched by hand when their subsystem is touched.
The retired battery of 27 arms is gone from the tree; its coverage lives in git
history (see *Retired arms* below for the names and what each covered).

## The gate — `scenes/verify_core.tscn` + `scripts/verify_core.gd`

Boots the real production scene (`res://scenes/main.tscn`), drives bounded
explicit steps, and exits 0 only when every check passes. Run it windowed — the
global RenderingDevice needs a real window on this rig:

```powershell
& "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" `
  --path . res://scenes/verify_core.tscn
```

Named fast fixture (~4 s instead of ~30 s; reduced particle count, so NOT exact
production coverage — the receipt records which mode ran):

```powershell
& "<console exe>" --path . res://scenes/verify_core.tscn -- --fast
```

Checks, in order — each row groups the `_check()` calls it covers (the gate
prints one line per call: 16 lines on a green production run, since the window
rows repeat per window):

| # | Check | Notes |
|---|-------|-------|
| 1 | production scene loads | `CassiSim` + `Camera3D` + `SimUI` present with scripts attached |
| 2 | scene declares the pinned contract | 22 `main.tscn` overrides + 11 inherited defaults, read **before** the scene enters the tree |
| 3 | simulation reaches setup ready | shaders ready, engine `setup_ready()`, no fail-closed state |
| 4 | decoupled bootstrap completes | first publish lands; the `playing=true` warm-up window and its step count are recorded |
| 5 | frame pacing is frozen | with `playing=false` the executed-step counter must not move over 3 frames |
| 6 | UI builds with default-off controls | VFX check buttons, presentation-profile and field-particles toggles exist and default off |
| 7 | capture helper wired | the production `CassiPresentationCapture` is present on the UI |
| 8 | renderer draws a visible frame | viewport grab saved to `_diag/core/core_frame.png` with a lit-pixel floor |
| 9 | explicit windows execute exactly | two 8-step windows driven via `_run_physics_steps`, each counted exactly |
| 10 | sampled state is finite | positions, velocities, and field roles (when the grid path exposes them) |
| 11 | particles stay alive and move | alive fraction, moving fraction, bounded mean displacement |
| 12 | forces act | mean \|Δv\| over a window inside a bounded envelope (the velocity buffer is the authoritative site state) |
| 13 | particle mass is conserved | sampled-chunk mass across the run |
| 14 | field telemetry matches the mode contract | see below |
| 15 | site-native field telemetry | the engine's own `readback_telemetry()` gridless branch: weighted \|q_mean\| and the site q range finite and nonzero and bounded, recorded per sample; the field-particle catalog branch reports zeros by design, so it is rejected as a source rather than read as a healthy field |

Receipt: `res://_diag/core/core_receipt.json` (gitignored) with every check,
its measured detail, the warm-up boundary, per-window sample statistics, the
runtime configuration, and the frame path.

### Two things the gate deliberately does not pretend

- **Field telemetry.** On the shipped configuration (`gridless_physics=true`)
  the engine allocates its grid-field buffers at **1 cell by design**
  (`cassi_physics_engine.gd`: `nc := 1 if gridless_physics else N*N*N`) — the
  site buffer is authoritative. The gate therefore asserts the *mode contract*
  and reports the EY/EI/q aggregates **unavailable**, rather than passing a
  vacuous band check. The site path is judged where it can actually fail:
  check 15 reads the engine's own `readback_telemetry()` gridless branch (the
  site-stats buffer when published, otherwise the volume-weighted meshless site
  rows) and requires the weighted `q_mean` and the site q range to be finite and
  bounded, per sample, in the receipt — so the shipped path keeps a field
  blow-up invariant instead of only a mode contract. When the grid path is
  actually present, the EY/EI drift band and the max-\|q\| blow-up guard run
  instead.
- **Configuration fingerprint.** It is read *before* `add_child`: several
  exports (the qi colour bands among them) are re-resolved at boot from a
  machine-local `user://` config, so the post-boot values are runtime state and
  are recorded in the receipt unjudged.

The gate does not re-derive physics. Analytic identities, engine-branch
fidelity (FFT/FMM/merge/BH/radiation/multigrid), the 7599 mind engine, and the
audit-grade export contracts are probe territory.

## Retained probes

Launched one at a time, windowed, when the subsystem is touched:

```powershell
& "<console exe>" --path . res://scenes/<probe>.tscn
```

Exit code 0 is the probe's contract; most also dump JSON/raw artifacts to
`res://_diag/` for the numpy gates under `research/`, which are run separately.

| Scene | What it carries | Numpy consumer |
|-------|-----------------|----------------|
| verify_fmm | FMM/tree gravity: 8192-point octree build + full stackless walk on a local RD | `research/meshless/stage5_verify.py` (G16–G18) |
| verify_merge | Merge shader on a planted 8-particle input (local RD) | `research/meshless/stage6_merge.py` (G28/G29) |
| verify_meshless_sim | Meshless vs grid arm from the SAME initial condition | `research/meshless/stage4_verify.py` (G11/G12′) |
| verify_meshless_sim_aniso | The same cross-solver battery at the φ-aspect box | `research/meshless/stage1b_aniso.py` |
| verify_voronoi3d | GPU JFA Voronoi + per-cell two-fluid wave vs the numpy spectral reference | `research/meshless/stage1_verify.py`, `stage2_verify.py` |
| verify_voronoi3d_moving | Moving mesh: steering + periodic ALE remap + JFA refresh | `research/meshless/stage2_verify.py` |
| verify_voronoi3d_aniso | The Voronoi battery at the φ-aspect box | `research/meshless/stage1b_aniso.py` |
| verify_meshless_gravity | Meshless TREE gravity over the sim's real source buffers (production G30/G31); also dumps G61–G63 and G70/G71 receipts | `research/meshless/stage5b_verify.py` |
| verify_river_isotropy | River azimuthal anisotropy: ring probes at N=64/N=128, shader-vs-estimator identity, pinned trilinear baseline | `research/cascade_multigrid/stage7_multigrid.py` |
| verify_survey | Survey exporter: frozen authoritative field/particle buffers, extent metadata, byte-exact particle comparison | `research/meshless/survey_read.py` |
| verify_synth | Audio-reduce cascade meter: φ-spaced plane-wave rung energies vs analytic references | `research/meshless/synth_verify.py` (G22/G23) |
| verify_volumetric | Volumetric ray-marched render of the analytic φ-attractor field (PNG + RGBAF pixel dump) | `research/volumetric/volumetric_verify.py` (G35) |
| verify_rotation_end_to_end | Repeatable live production regression: merge → canonical orbital angular momentum, spin → resolved orientation, ledger closure | `research/rotation/rotation_end_to_end_verify.py` (G97–G100; reads this script) |
| verify_physical_radiation | Immutable model/unit/snapshot rejection contracts, grouped Planck/CIE references, real spectral formal solution vs the independent CPU value | — (in-flight workstream) |
| verify_coupled_radiation_engine | Hash-bound supplied-material extensive-state solver, LTE/affine/frequency references, scheduler integration, fail-closed lifecycle | — (in-flight workstream) |
| verify_observatory_integration | Production-scene mode switches, prescribed spectral pixels, capture + sidecar contracts | — (in-flight workstream) |

`scripts/verify_river_isotropy.gd` pins the default CUBE grid-river chain
bit-identical with fixed numeric anchors — those anchors are load-bearing.

## Standalone labs (not part of the gate)

### Passive process-clock lab

CPU-only and default-off; frozen preregistration in
[`research/process_time/common_lapse_prereg.md`](../research/process_time/common_lapse_prereg.md).

```powershell
& "<console exe>" --path . res://scenes/verify_process_clock.tscn
```

Raw receipt: `res://_diag/process_time/common_lapse_receipt.json`. The scene has
no RenderingDevice/GPU/readback dependency, makes no production/default-path
common-lapse change, and reports implementation/reparameterization PASS/FAIL
only — not evidence for universal physical time.

### Field Particles (three scenes)

```powershell
& "<console exe>" --path . res://scenes/verify_field_particles.tscn
& "<console exe>" --path . res://scenes/verify_field_particle_integration.tscn
& "<console exe>" --path . res://scenes/verify_field_particles_motion.tscn
```

`verify_field_particles` checks the pinned source field and its evolution;
`verify_field_particle_integration` checks the hidden single-particle control
through the real `CassiSim` renderer; `verify_field_particles_motion` checks
that the public setting displays two field particles, moves both in the
expected directions, preserves their field charge, keeps point-particle physics
off, and switches cleanly off and back on. All three must exit 0 after a Field
Particles change. Frozen registrations and measured results live in
`research/field_particles/`.

### GPU trajectory probe

Reads the passive trajectory recorder — a default-off, read-only observation
path inside `cassi_physics_engine.gd`:

```powershell
& "<console exe>" --path . res://scenes/verify_trajectory_probe.tscn -- --mode=shell --recorder=on \
    --steps=1000000 --particles=8192 --tracers=4096 \
    --sample-stride=4096 --sample-capacity=256 --merge-cadence=64
```

`--mode=shell` runs the nested-shell initial condition with merging disabled;
`--mode=ancestry` repeats the same seeded geometry with the merge rule enabled
under a fixed coherent field plant. `--recorder=off` writes only the tracer
endpoints and is the paired dynamics-neutrality control. The frozen
registration is
[`research/matter_formation/trajectory_shell_prereg.md`](../research/matter_formation/trajectory_shell_prereg.md);
runs shorter than the registered 1,000,000 accepted steps are reported with the
status `IMPLEMENTATION CHECK` and a verdict of `INCONCLUSIVE`, so they are never
read as evidence either way.

Every run writes `receipt.json`, the raw recorder arrays, and `analysis.json`
under `res://_diag/matter_formation/trajectory_<mode>/` (gitignored). Score a run
with the standalone analyzer:

```powershell
python tools/analyze_trajectory_probe.py _diag/matter_formation/trajectory_shell
```

The probe measures radial shell occupancy and contrast, boundary crossings,
turnarounds, and the merge-edge ancestry graph. It does not dispatch the
condensation scanner, spawn black-hole records, or transfer field mass to the
particle population: recorded events are particle-merge hops only, and the probe
is not a test of the fluid-to-matter collapse pathway. The recorder-off control
compares the arrays the harness retains — the 4,096 sampled tracer identities
and their initial and final states — and those arrays match byte for byte across
the on/off pair at matched configuration; sampled tracer motion therefore
carries no recorder perturbation. That comparison does not cover the
unsampled particles or the field state, which rely on the recorder's
read-only dispatch contract rather than on this measurement.

## Launch conventions

- **Every GPU scene is windowed, never headless.** The headless renderer on this
  rig has no usable RenderingDevice; `--headless` is only for orchestration and
  for `--import`.
- **Stale shader artifacts**: if a scene fails with `No loader found for
  resource: res://compute/...` or `All the shader bindings ... not provided`,
  run the console exe once with `--headless --import` (regenerates
  `.godot/imported/` after shader edits) and re-run. The first run after a
  shader change can be slower while SPIR-V recompiles.
- **Orphan hygiene**: one Godot instance at a time
  (`tasklist | findstr /i Godot`); a scene launched through a wrapper may leave
  a child process holding the GPU — kill the process *tree*.
- Receipts, logs, and dumps go under `res://_diag/` (gitignored).

## Retired arms

The following 27 arms were retired from the tree; their coverage lives in git
history (search the scene name) and, where it remains load-bearing, in the gate:

`verify_fft`, `verify_gravity_modes`, `verify_meshless_stability`,
`verify_gridless_physics`, `verify_phi_box`, `verify_ring`, `verify_river_law`,
`validate_sim_ui`, `verify_particle_vfx`, `verify_presentation_layers`,
`verify_merge_sim`, `verify_meshless_reconstruct`, `verify_particle_vanish`,
`verify_voronoi3d_moving_aniso`, `verify_falsify`, `verify_mind_engine`,
`verify_field_intelligence`, `verify_bh_accretion_engine`,
`verify_merge_engine`, `verify_multigrid_engine`, `verify_rho_front`,
`verify_eps_gap`, `verify_subsonic_step`, `verify_omega_invariant`,
`verify_tree_hier_refit_engine`, `verify_particle_world_agent`,
`verify_rotation_stress`.

Two notes for anyone digging in history:

- `verify_particle_vanish` was a diagnostic, not a gate (it always exited 0).
- The FFT barrier pattern — direct FFT consumers must call
  `_ensure_poisson_twiddle(cl)` after `compute_list_begin()` and before binding
  the Poisson pipeline — was introduced in the retired `verify_fft`. No retained
  probe dispatches the Poisson FFT directly; the live callers are
  `cassi_sim.gd:_dispatch_poisson` and the engine's own Poisson and cascade
  paths.

`scripts/verify_sim_ui.gd` remains in the tree: the retired `validate_sim_ui`
scene was its only launcher, and the UI defaults it checked are now covered by
check 6 of the gate.
