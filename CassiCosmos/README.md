# Cassi Space Sim (Godot)

RealSim N-body + two-fluid visualization and verification. The production
scene runs the site-native field/force engine on a worker-thread local RD;
legacy raster verification scenes retain the global-RD compatibility path.

## Run the production site-native universe

From the CassiCosmos directory, launch the tuned production scene with the
Godot 4.7.1 Mono console executable:

```powershell
& "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" `
  --path . res://scenes/main.tscn
```

For editor use, open the project in Godot and press **F6** with
`scenes/main.tscn` selected (or **F5** for the project main scene). Runtime
scenes must be windowed on this machine; `--headless` is for the battery runner
only. The production scene uses the site-native field/force path
(`gridless_physics=true`, `physics_decoupled=true`, `boxless_field=true`) and
starts with a 500,000-particle interactive preset.
The interactive preset also keeps the tracking envelope enabled: the finite
site window follows the compact particle envelope instead of becoming a fixed
wall that the cloud can pile into.

The site window is a finite open-boundary computation domain, not a periodic
render box: particles that leave it remain in world coordinates and stop
contributing to the local site field instead of reappearing on the opposite
wall. If you raise
`N_particles`, keep `particle_size` small and make sure the initial cluster
separation fits the site window; startup now auto-fits an invalid Gaussian or
Plummer support before GPU setup.

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

## Verification battery

Run the full runner headless only for orchestration; every GPU scene arm is
windowed on this machine because the headless renderer has no usable
RenderingDevice:

```powershell
& "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" `
  --path . --headless -s res://verify/run_all.gd
```

For a single arm, launch it windowed:

```powershell
& "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" `
  --path . res://scenes/verify_gridless_physics.tscn
```

Exit code 0 means the selected scene passed.

The first five run at the cube aspect (bit-untouched); the φ battery
validates the anisotropic physics against the analytic per-axis k-sum Green
and the anisotropic stencil symbol.
