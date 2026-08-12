# Cassi Space Sim (Godot)

RealSim N-body + two-fluid visualization and verification, running the
river-law gravity in Godot compute shaders (global RenderingDevice).

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

Run each scene headless; exit code 0 = all checks passed:

```
godot --path . res://scenes/verify_fft.tscn            # FFT roundtrip + Poisson solves
godot --path . res://scenes/verify_ring.tscn           # 19-point dispersion isotropy
godot --path . res://scenes/verify_river_law.tscn      # river/heuristic force laws
godot --path . res://scenes/verify_river_isotropy.tscn # ring anisotropy anchors (r/h)
godot --path . res://scenes/verify_gravity_modes.tscn  # 5-mode gravity selector battery
godot --path . res://scenes/verify_phi_box.tscn        # φ-aspect battery (a–e, GRID_LAYOUT.md §5)
```

The first five run at the cube aspect (bit-untouched); the φ battery
validates the anisotropic physics against the analytic per-axis k-sum Green
and the anisotropic stencil symbol.
