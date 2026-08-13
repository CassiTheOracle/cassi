# Particle VFX modes (default-off) + cassi_sim.gd integration

Status: implemented in `compute/cassi_instancer.glsl` + `scripts/sim_ui.gd`,
with the two `scripts/cassi_sim.gd` hooks LANDED (green-lit after the FMM
wave): TRUE ρ = EY+EI for two-axis and the live camera position for depth.
Verification: `verify_river_isotropy` 36/36 bit-identical, `verify_particle_vfx`
smoke 5/5, `validate_sim_ui` 9/9.

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

## Depth cue camera source (landed)

`_fill_instancer_pc()` writes the live camera world X/Y/Z into the three
instancer-PC slots the instancer never reads for their shared meaning each
fill (from `_sim_cam`, the sibling `Camera3D`; headless scenes leave them 0):

| byte | slot | shared meaning      | repurposed as |
|------|------|---------------------|---------------|
| 32   | 8    | `source_strength`   | camera X |
| 36   | 9    | `num_clusters`      | camera Y |
| 40   | 10   | `gravity_mode`      | camera Z |

The shader's depth path reads those slots as the camera position.

## Two-axis ρ source (landed)

Mode 4's lightness axis reads TRUE ρ = EY+EI via bindings 4/5 of
`_us_inst_0` (`_field_ey` + `_field_ei`), trilinear-sampled at the particle
with the same periodic convention as q.

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
