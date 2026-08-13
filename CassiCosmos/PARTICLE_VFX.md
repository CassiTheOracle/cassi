# Particle VFX modes (default-off) + deferred cassi_sim.gd integration

Status: implemented in `compute/cassi_instancer.glsl` + `scripts/sim_ui.gd`;
scene-based verification pending the FMM wave-3 `cassi_sim.gd` fix (it gates
every `cassi_sim.gd`-loading scene run).

## Feature encoding

`sim.particle_color_mode` carries the new visuals in its low nibble (base
mode) and high nibble (feature flags) — see the `cassi_instancer.glsl` header
for the full map:

| base mode | meaning                                          |
|-----------|--------------------------------------------------|
| 0         | Cassi mass gradient (legacy, bit-identical)      |
| 1         | Velocity rainbow                                 |
| 2 / 3     | Qi rainbow / Qi double                           |
| 4         | TWO-AXIS: hue = q (engine), lightness = ρ        |

| flag | meaning                     |
|------|-----------------------------|
| 0x10 | SIZE_BY_MASS (scale ∝ cbrt(m)) |
| 0x20 | ADDITIVE_GLOW (bright core + halo) |
| 0x40 | DEPTH_CUE (fade with camera distance) |

Example: `particle_color_mode = 2 | 0x10 | 0x20 = 50` → Qi rainbow +
size-by-mass + glow.

**Per-particle mass** lives in `pos[].w` (Salpeter draw in `_init_particles`,
preserved verbatim by the nbody KDK kick, `cassi_nbody_gravity.glsl`:
`pos[i] = vec4(p_new, pos[i].w)`). The size mode reads it from the existing
`Positions` binding — **no new MASS/COUNT buffer is needed**. When a future
merge pass writes varied masses into `pos.w`, the size mode lights up for
free.

## UI controls (scripts/sim_ui.gd)

A new "VFX:" row in the bottom control bar (after the cluster/color row)
exposes four default-off CheckButtons:

- **Size∝m¹ᐟ³** — sets the 0x10 flag (size ∝ cbrt(particle mass)).
- **Glow** — sets the 0x20 flag (additive bright-core + large-object halo).
- **Depth fade** — sets the 0x40 flag (alpha fades with camera distance).
- **2-axis q/ρ** — switches the base color mode to 4 (hue = q, lightness = ρ);
  requires the Rainbow toggle on.

All compose onto `particle_color_mode` via `_apply_particle_color_mode()` and
are live (no reinit). With every VFX toggle + Rainbow off, the composed value
is 0 — the legacy path, bit-identical.

## Depth cue camera source (deferred)

Until the host feeds the live camera, the depth probe uses the world-origin
distance (the auto-framed camera sits a fixed oblique distance from the
origin, so this is a faithful fallback). To use the TRUE camera position the
host must write the camera's world X/Y/Z into the three instancer-PC slots
the instancer never reads for their shared meaning, each fill:

| byte | slot | shared meaning      | repurposed as |
|------|------|---------------------|---------------|
| 32   | 8    | `source_strength`   | camera X |
| 36   | 9    | `num_clusters`      | camera Y |
| 40   | 10   | `gravity_mode`      | camera Z |

`sim_ui.gd` has the camera (sibling `Camera3D` of `CassiSim`; see the sim's
`_find_sibling_camera`). Then restore the shader's `cam` read (it is currently
hard-pinned to origin with a `// ← restore` marker).

## Two-axis ρ source (deferred)

Mode 4's lightness axis today uses q = EY²+EI² as a monotonic ρ proxy. To use
the TRUE ρ = EY+EI, add two bindings to `_us_inst_0` in
`cassi_sim.gd _cache_uniform_sets()` after binding 3:
`_uniform_storage(4, _field_ey)` and `_uniform_storage(5, _field_ei)`, then
enable the commented `tri_rho` sampler in the shader and flip `rho_proxy()`.

## Bloom (WorldEnvironment glow)

`scenes/vfx_glow_env.tscn` is a standalone `WorldEnvironment` with HDR/
additive glow enabled (threshold 0.35, additive blend). To use it, instance
that node into the scene (or add a `WorldEnvironment` node to any scene and
assign the included Environment resource). `main.tscn` is left untouched.

## Verification

`scenes/verify_particle_vfx.tscn` + `scripts/verify_particle_vfx.gd` drive
the real instancer and assert:
1. default (mode 0) matches the pinned legacy size + mass-temperature formula;
2. size flag matches `clamp(SIZE_K·cbrt(m), …)`;
3. two-axis lightness shift + nondegenerate hue;
4. glow alpha floor + activation;
5. depth alpha matches the linear fade.

`verify_river_isotropy.tscn` must stay 36/36 bit-identical (default path).
