# Cassi Space Sim (Godot)

RealSim N-body + two-fluid visualization and verification. The production
site-native field/force engine and renderer share the renderer-owned
RenderingDevice. A worker prepares CPU initial conditions; GPU commands run
on the render thread. Standalone verification consumers can own a local RD.

## Run the production site-native universe

From the CassiCosmos directory, launch the tuned production scene with the
Godot 4.7.1 Mono console executable:

```powershell
& "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" `
  --path . res://scenes/main.tscn
```

For editor use, open the project in Godot and press **F6** with
`scenes/main.tscn` selected (or **F5** for the project main scene). Runtime
scenes must be windowed on this machine; `--headless` is not a GPU path. The
production scene uses the site-native field/force path
(`gridless_physics=true`, `physics_decoupled=true`, `boxless_field=true`) and
uses the source default of 2,500,000 particles unless a different preset is selected.
The production scene keeps the tracking envelope enabled: the finite
site window follows the compact particle envelope instead of becoming a fixed
wall that the cloud can pile into.

The site window is a finite open-boundary computation domain, not a periodic
render box: particles that leave it remain in world coordinates and stop
contributing to the local site field instead of reappearing on the opposite
wall. If you raise
`N_particles`, keep `particle_size` small and make sure the initial cluster
separation fits the site window; startup now auto-fits an invalid Gaussian or
Plummer support before GPU setup.

## Appearance and capture

Open **Visuals → Appearance** and select a view:

| View | Rendering |
|------|-----------|
| **Scientific** | Startup default; preserves the scientific palettes, legends, materials and field display. |
| **Observatory** | Warm point light, cooler diffuse material, depth-correct absorption, shadowed single scattering and shared HDR exposure. |
| **Cinematic** | Observatory with restrained additional bloom and a 20 ms shutter; camera direction remains an independent choice. |

Appearance and observation source are independent. **Simulation-unit optics**
retains the established renderer described below. **Prescribed spectral preview**
uses the immutable `prescribed-homogeneous-lte-continuum` reference: a 6500 K
LTE source, 16 visible groups, CIE 1931 2° observer data, explicit SI-to-simulation
unit maps, and a one-way homogeneous-sphere formal solution. It reads a frozen
geometry/time publication and never changes the solver. **Coupled physical
radiation** is visible but unavailable; selecting it fails closed and lists the
missing native material, thermal, exchange, transport, and checkpoint capabilities.

The optical views work in **Particles** and **Field** modes. They reconstruct
the live simulation without modifying its particles or solver. Their material
and colors use simulation units; coherence is not interpreted as temperature
or an astronomical spectrum. Brightness variation follows the source
distribution rather than added procedural foreground clouds.

Start with **Exposure (EV)**, **Optical thickness**, **Emission**, and
**Quality**. Exposure is locked by default. **Advanced scattering** contains
point/diffuse allocation, scattering, bloom, shutter, temporal reprojection,
optional slow auto exposure, the world-stable background and adaptive quality.
**Save appearance** / **Load appearance** persist settings locally; saving
does not silently enable the optical renderer on the next launch.

| Quality | Optical grid | Maximum optical image height |
|---------|--------------|------------------------------|
| Performance | 48³ | 270 px |
| Balanced | 64³ | 360 px |
| High | 96³ | 540 px |
| Capture | 128³ | 1080 px |

The optical image is aspect-correct and capped by the viewport. Particles and
the final composition retain viewport resolution. Adaptive quality responds
to total rendered-frame time, including physics, with hysteresis. It never
reduces particle count or changes solver settings. Capture quality is fixed;
other tiers can also be fixed by disabling adaptive quality.

**Visuals → Camera & capture** provides three saved camera views, PNG stills
at **1×** or **2×** viewport dimensions, a best-effort PNG sequence, and an
optional simulation-unit scale/time overlay. Uncheck **Interface** for an
unobstructed image; **F9** restores it. Supersampled stills restore the window
and playing state afterward. See [RECORDING.md](RECORDING.md) for fixed-rate
Movie Maker recordings and optical command-line controls.
Spectral stills also write a JSON provenance sidecar and a raw linear
`RGBA32F` XYZ file beside the PNG. PNG-sequence directories contain a
`sequence.json` sidecar with per-frame source, step/time, camera, exposure,
dimensions, and immutable model/snapshot identities.

### Measured Observatory render-boundary timing

The 2026-09-09 RX 7900 XTX comparison uses 2.5 million particles, a 1280×720
viewport, grid 64, seed 736241, uncapped rendering and a one-step-per-frame
physics cap. Each live row samples 90 wall-clock intervals between consecutive
`RenderingServer.frame_post_draw` boundaries in Particles mode after warmup.
These include CPU/GPU scheduling; they are not GPU-only timings or display
scan-out measurements.

| Camera path | Scientific median / p95 | Observatory Balanced median / p95 | Cinematic Balanced median / p95 | Observatory adaptive High median / p95 |
|-------------|-------------------------|----------------------------------|--------------------------------|---------------------------------------|
| Wide | 5.82 / 8.75 ms | 6.13 / 9.56 ms | 6.08 / 9.81 ms | 7.39 / 10.56 ms |
| Close core | 4.11 / 7.36 ms | 4.52 / 7.83 ms | 4.61 / 9.61 ms | 6.23 / 10.23 ms |
| Zoom | 5.44 / 11.09 ms | 5.75 / 13.65 ms | 5.70 / 12.65 ms | 7.21 / 10.97 ms |

Adaptive High retained its requested tier in these samples. Paused runs use
the same seed, 12-step stopping condition and camera paths. Live scheduling
advances 10–20 solver steps per 90 measured intervals, so live snapshots are
not bit-identical across runs. These short-path measurements do not guarantee
an arbitrary evolved scene's frame rate. Production-size captures separately
cover Scientific, Observatory and Cinematic in both Particles and Field modes;
the timing table does not benchmark Field mode. The coarse optical cache and
six-direction first-scatter model remain bounded approximations, particularly
in close, dense views. Raw intervals and screenshots are in
`_diag/observatory/render_boundary/`, indexed by
`_diag/observatory/release_receipt.json`.

The standalone `scenes/verify_observatory.tscn` checks optical transport,
mass/flux conservation and empty/boundary behavior.
`scenes/verify_observatory_integration.tscn` exercises real mode switches,
Scientific restoration, capture, history resets and adaptive quality.
The Observatory implementation design is
`research/presentation/observatory_design.md`; `scenes/verify_core.tscn` remains
the default-path contract.

The [physical-radiation design and staged implementation plan](research/presentation/physical_radiation_design.md)
uses the [completed conditional radiative closure](../CassiTheory/turbulence/cassi-radiative-material-closure.md)
to keep observation, supplied control physics and native material claims
separate. P0/P1 provides real grouped Planck emission/absorption, CIE colour
conversion, exact model/unit provenance, GPU formal-solution images and raw XYZ
capture without changing solver state.

The default-off `CassiRadiationEngine` additionally owns a hash-bound,
homogeneous supplied-material control: extensive mass/internal-energy/volume
and group-energy state, affine work and frequency transport, implicit LTE
matter/radiation exchange, accepted-step publication and complete checkpoints.
Its frozen CR-G0–CR-G8 gate passes 86/86 checks. This bounded receipt does **not** identify native Cosmos matter,
qualify spatial or general moving-medium radiation transport, supply a
plasma/atomic provider, or make physical point emitters available. Observatory
coupled-source readiness therefore remains fail-closed.

## Camera controls

Choose **Visuals → Camera direction → Follow structure** to keep the live
particle structure close and centered. The camera retains its current viewing
angle without orbiting and adjusts its distance to fit both window dimensions.
It frames the per-axis 2nd–98th percentile particle bounds, so isolated escaping
particles do not pull the view far away. Bounds refresh at up to twice a second;
the camera moves out immediately for expansion and eases inward for contraction.

WASD, mouse-look, or any other manual camera control immediately switches back
to **Manual**. Manual remains the startup default. **Wide envelope**, **Focus
core**, and **Record orbit** remain available as orbiting presets. Camera
following does not move the simulation's physics window.

## Particle initial conditions

In **Setup → Initial state**, choose a **Shape**, **Arrangement**, and
**Initial motion** independently. Changing an initialization control restarts
the particles; these controls are marked **REINIT**. The camera frames the
new support when startup framing is enabled.

Plummer, Gaussian, and Uniform remain available alongside nine designed
geometries:

| Shape | Shape-specific controls |
|---|---|
| Spiral disc | Arm count, pitch, width, and central core |
| Tilted encounter | Disc size, particle ratio, relative tilt, separation, and offset |
| Pearl ring | Ring radius, knot count, and vertical warp |
| Nested shells | Shell count, spacing, inner radius, ellipticity, and offset |
| Double helix | Strand count, turns, radius, and longitudinal pitch |
| Filament web | Junction count, connectivity, and curvature |
| Hierarchical cloud | Depth, branching, and scale separation |
| Folded sheet | Fold amplitude, wavelength, ripple count, and aspect |
| Trefoil cloud | Loop radius, loop proportion, and height |

**Shape settings** shows only the selected shape's controls, together with
shared thickness, clumpiness, asymmetry, and yaw/pitch/roll. **Support size**
sets the overall scale.

The production scene starts its 2.5 million-particle Double helix in a
20,000-world-unit support while retaining a 50-world-unit rendered particle
size. This is a physical initial-condition change, not a presentation-only
rescale: domain fitting and the characteristic evolution scale follow the
larger support. A fixed-seed full-population comparison against the former
1,000-unit support measured the median nearest-neighbor distance rising from
1.52 to 30.49 world units (20.000003×); masses were byte-identical, and the
GPU's 2.5 million position/mass records matched the generated layout
byte-for-byte. The raw QuadMesh width remains 50 world units against the
30.49-unit median spacing. Without the production scene's enabled
presentation profile and its bounded screen-space sizing, that ratio would
make the full population read as continuous luminous strands rather than
isolated grains. `scripts/main_recorder.gd` inherits the
same production-scene support for future recordings. The **Support size**,
**Component spacing**, and **Particle size** controls accept the production
values without clipping. Measurements are retained in
`_diag/spacing_measurement_receipt.json`,
`_diag/spacing_gpu_receipt.json`, and `_diag/spacing_live_receipt.json`;
the native view is `_diag/spacing_native_desktop.png`.

**Arrangement** places copies in a Ring, Sphere, Single, Pair, Chain,
Scatter, or Hierarchy. Single and Pair fix the copy count to one and two;
the Components control is disabled for those choices. Ring and Sphere are
explicit layouts, independent of component count.

**Initial motion** offers Profile, At rest, Spin, Counter-spin, Inward,
Outward, Along structure, and Opposed streams. Profile preserves the
spherical profiles' circular-support initialization and starts designed
shapes at rest. The other moving choices use **Motion speed**; they are
kinematic starting conditions, not equilibrium solutions.

**Total mass = 0** keeps the sampled Salpeter masses; a positive total
normalizes their sum. Shape, arrangement, and motion use separate random
streams from mass sampling. A nonzero **Seed** reproduces the initialization;
**Shuffle seed** selects a new nonzero seed and restarts it.

Both inline and decoupled initialization use
`scripts/cassi_particle_initial_conditions.gd` for the designed geometries,
which populate particle buffers directly. The three spherical profiles retain
their seeded initialization path when the shared geometry controls are at
their defaults and Ring or Sphere is selected. Recorder configuration carries
the same shape, arrangement, motion, mass, settings, and seed.

`scripts/workbench_initial_conditions.gd` remains a separate compiler of
normalized field recipes into deposit/align/impulse commands: its `shell`
primitive deposits a field profile, while Nested shells samples particle
positions.

Initialization verification on 2026-09-08 passed 1,606 geometry/invariant
checks, including 12 byte-identity comparisons against the seeded spherical
baseline at 4,096 and 40,000 particles. The native live-control smoke passed
878 checks across inline and decoupled runs, comparing GPU positions, masses,
and velocities to the requested initialization and exercising simulation
evolution. Raw receipts are `_diag/ic_geometry_receipt.json` and
`_diag/ic_live_receipt.json`; `_diag/ic_native_geometry_gallery.png` shows
all nine designed shapes rendered by the windowed simulation at 4,096
particles while paused.
The regression battery then in place passed **40/40** in 336 seconds
(exit code 0); its per-arm logs are in `_diag/battery_logs/`.

A CPU-only comparison against the pre-change engine also passed all 12
eight-chunk cases at 262,144 and 262,145 particles, covering all three
spherical profiles with one and ten components. Position/mass, velocity,
acceleration, and cluster-buffer bytes matched, as did total mass and
cluster-record count. The counts exercise both equal chunk sizes and the
uneven final chunk. Hashes and source identities are retained in
`_diag/ic_parallel_parity_receipt.json`.

## Performance paths

The site-native engine uses hierarchical momentum reduction, frontier-based
tree construction and complete stackless traversal. Exact nearest-site queries
retain original site IDs and are reused only while their particle and geometry
epochs match. Telemetry publishes once per accepted qualifying generation.
Renderer geometry, topology and field optics have separate update lifetimes.

`compact_render_data` is an optional billboard path using two RGBA32F texels
per particle instead of rewriting a full transform and color record. The
standard MultiMesh path remains available for compatibility and comparison.
`volume_dynamic_resolution` uses measured GPU dispatch time to select a bounded
volume-resolution tier; changing that tier is a quality/performance tradeoff.

Raster consumers use old-time field ping-pong and persistent FFT twiddles.
Field Particles evaluates the analytic derivative of its discrete Hamiltonian;
the finite-difference path remains available as an independent diagnostic.
Mind-engine projection uses typed top-k selection, ordered by descending q
and then ascending cell index.

### Measured production comparison

The 2026-09-07 RX 7900 XTX comparison uses 2,500,000 particles at 1287×720,
with matched camera, seed, particle size and simulation controls:

| Instrumented metric | Retained baseline | Current implementation |
|---|---:|---:|
| Live frame interval, median | 24.379 ms | 13.368 ms |
| Live frame interval, p95 | 67.528 ms | 35.797 ms |
| Site-step GPU interval, median | 12.962 ms | 2.854 ms |
| Paused full-size rendering, median | 14.776 ms | 14.065 ms |

The live median falls 45.2% and p95 falls 47.0%. Both runs reach step 538
with zero dropped steps; measured live cadence is 33.36 versus 33.21 steps/s.
This demonstrates lower frame latency and GPU cost, not increased
simulated-time throughput. GPU stage intervals are not additive.

The comparison keeps `compact_render_data=false`. The existing production
volume controller is enabled and the recorded volume resolution is 512×512.
Compact rendering has separate full-payload and rendered-image parity checks.

The battery then in place passed all 40 arms in 266 seconds; its separate G24
survey payload check also passed. The comparison, raw receipts, source hashes,
focused numerical/render checks and exact current-arm logs are retained in
`_diag/performance_implementation_20260907/`. The final comparison is
`comparison_receipt_2500000_implemented.json`; the first completed candidate is
preserved separately as `receipt_2500000_before_log_closure.json`.

## Field Particles

`Field Particles` is off by default. Turn it on in the **System** tab.

> Particles are simulated as moving patterns in the field instead of point objects.

When it is on, the simulation starts with two field particles moving toward
each other. The points on screen follow those field patterns; they do not
control them. Regular point-particle physics is turned off.

Gravity is not connected to field particles yet.

The pinned field data lives under `data/field_particles/`.
`tools/build_field_particle_seed.py` rebuilds the source particle and
`tools/build_field_particles_pair.py` rebuilds the moving pair.

Run the three field-particle checks windowed:

```powershell
& "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" `
  --path . res://scenes/verify_field_particles.tscn
& "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" `
  --path . res://scenes/verify_field_particle_integration.tscn
& "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" `
  --path . res://scenes/verify_field_particles_motion.tscn
```

The implementation and measured boundaries are recorded in
`research/field_particles/`.

## Box geometry: the φ-aspect box

The simulation box is **per-axis rectangular** (`box_aspect` export on
`cassi_sim.gd`): extent_i = aspect_i · 1.5 · cluster_radius with N³ cells
unchanged. The cube default `(1,1,1)` is the legacy box; the theory preset
`(φ, 1, φ²)` maps x = Yang (extended), y = Yin (contracted), z = String/P∥
(flow) and makes the box-mode lattice incommensurate — removing the cubic
image-lattice degeneracy that locked filaments into straight grid lines at
box scale in RealSim mode. See **GRID_LAYOUT.md** for the full design
(periods, de-resonance argument, anisotropic 19-point stencil, per-axis
k-space/samplers/deposit, expected effects and honest limits).

- Toggle in the UI: the "φ box" CheckButton (applies on reinit).
- Recording: `record.ps1 -Aspect 1.618,1,2.618` (see RECORDING.md).

## Verification

`scenes/verify_core.tscn` is the default-path contract. It boots the real
production scene, drives bounded explicit steps, and exits 0 only when every
check passes. GPU scenes are windowed on this machine because the headless
renderer has no usable RenderingDevice:

```powershell
& "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" `
  --path . res://scenes/verify_core.tscn
```

Exit code 0 means the production path passed. The receipt lands in
`_diag/core/core_receipt.json` with a captured frame beside it; `-- --fast` runs
the same checks on a 65,536-particle fixture (~4 s instead of ~30 s) and records
that reduced mode in the receipt.

Retained probes stay standalone — analytic identities, engine-branch fidelity,
the numpy-dump producers, and the radiation/observatory workstreams. Launch one
windowed when its subsystem is touched; `verify/README.md` lists them with their
numpy consumers.
