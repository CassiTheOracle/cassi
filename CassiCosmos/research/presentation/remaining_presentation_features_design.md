# Remaining CassiCosmos presentation features — architecture design

## Status: design frozen before implementation — 2026-08-20

## Scope

This document defines the next presentation-only renderer layers after the
landed particle presentation profile:

1. far-field macro-site LOD;
2. GPU velocity ribbons;
3. reprojected temporal site-volume rendering;
4. manual-first presentation direction and capture presets.

These layers improve visual legibility only. Particle/field physics, solver
cadence, position/mass/velocity buffer formats, and profile-off rendering stay
authoritative. Every new feature ships disabled and has a focused gate before it
can be enabled in `scenes/main.tscn` or `scenes/main_recorder.tscn`.

## Existing contracts that constrain every design

| Contract | Source | Consequence |
|---|---|---|
| Particle records are 16 floats / 64 B: three transform rows plus color or custom data. | `compute/cassi_instancer.glsl`, `scripts/cassi_sim.gd::_setup_multimesh()` | Do not resize, repurpose, or add payload to the particle MultiMesh. |
| LUT custom data is `(u, glow_boost, depth_fade, spare)`. | `compute/cassi_instancer.glsl` | Velocity direction does not fit safely in the live presentation material path. |
| Position and velocity are separate `vec4[N]` buffers. | `scripts/cassi_sim.gd`, `compute/cassi_nbody_gravity.glsl` | Visual motion layers read velocity directly; they do not infer it from a transformed billboard. |
| Instancer and fused-volume PCs are already exactly 32 floats / 128 B. | `scripts/contracts/layout.gd` | Every new compute pass owns a separate PC and binding map. |
| Site topology is coherent only after the render-topology worker publishes a valid generation. | `scripts/cassi_physics_engine.gd::topology_resources()` | Macro and history paths gate on ready/status/generation; no partial worker result is rendered. |
| The live optical payload is two `vec4`s per site: `(render_local_xyz, opacity)` and `(EY, EI, coherence, gradient)`. | `compute/cassi_voronoi_optical_payload.glsl` | A macro-site layer can use position, opacity, coherence, phase derivation, and gradient without CPU aggregation. It cannot claim mass, momentum, volume, or site velocity. |
| Fused-volume alpha is Beer–Lambert opacity, not depth. | `compute/cassi_voronoi_fused_volume.glsl` | Temporal reprojection needs a new auxiliary depth image; alpha remains opacity. |
| `free_camera.gd` and `main_recorder.gd` currently write camera transforms independently in their respective scenes. | `scripts/free_camera.gd`, `scripts/main_recorder.gd` | A director is a pose provider with explicit ownership, never a second concurrent camera writer. |
| Dynamic volume resolution already exists and is default-off in script defaults. | `scripts/cassi_sim.gd::_prepare_volume_resolution()` / `_note_volume_dispatch_frame()` | Do not introduce a competing quality governor in the first implementation. |

## Design decision A — macro-site far-field LOD

### Promise

At range, the field reads as coherent multi-scale structure while nearby
particles retain their individual identity. There is no particle-count or
physics approximation.

### Representation

Use one fixed-capacity visual instance per BCC site. At the present `ML_N1 =
16`, that is `2 * 16^3 = 8192` candidate instances.

A new `compute/cassi_presentation_macro_lod.glsl` owns this ABI:

| Binding | Resource | Purpose |
|---|---|---|
| 0 | readonly topology optical `vec4[2 * site_count]` | Render-local position, opacity, EY/EI, coherence, gradient. |
| 1 | readonly topology status `uint[4]` | Generation, required-edge count, overflow, site count validation. |
| 2 | writeonly macro instance `vec4[4 * max_sites]` | A dedicated 16-float MultiMesh record per site. |

The macro shader writes zero transforms for invalid, overflowed, or visually
insignificant sites. The first pass intentionally does **not** compact sites:
8,192 records are a bounded, stable output and avoid a new atomic/scan contract.

`shaders/presentation_macro_billboard.gdshader` uses a dedicated macro
MultiMesh/material. Its color is coherence/phase-derived, with opacity and
gradient only as bounded visual weights. It must not imply a physical site mass.

### Lifetime and dispatch

`CassiSim` gets a dedicated macro MultiMesh and a matching renderer-visible RD
instance buffer. It follows the existing `_setup_multimesh()` /
`_free_multimesh()` lifecycle, but never shares `_mmi` or `_mm_rd_rid`.

The pass is recorded only when all are true:

```text
topology_ready
AND topology status is finite and overflow-free
AND topology generation differs from last macro generation
AND presentation_macro_lod_enabled
```

It runs after topology publication and before the render consumes the dedicated
macro MultiMesh. In both inline and decoupled paths it consumes the global-RD
topology resources, never the local-RD worker resources.

### Crossfade

The individual presentation material and macro material each receive the same
camera-relative transition interval. They use complementary smooth weights:

```text
particle_weight = 1 - smoothstep(lod_enter, lod_exit, d)
macro_weight    =     smoothstep(lod_enter, lod_exit, d)
```

`d` is view distance after the current render-window transform. The first
prototype freezes thresholds relative to the live envelope diagonal and scales
them for FOV. A follow-up may replace this with a projected-footprint threshold
only after the deterministic camera sweep gate exists.

### Planned files

- `compute/cassi_presentation_macro_lod.glsl`
- `shaders/presentation_macro_billboard.gdshader`
- `scripts/cassi_sim.gd`
- `scripts/contracts/layout.gd`
- `scenes/verify_presentation_macro_lod.tscn`
- `scripts/verify_presentation_macro_lod.gd`
- `research/presentation/verify_macro_lod.py`

### Explicit non-goals

- No particle reduction, merge, or mutation.
- No CPU site aggregation/readback.
- No use of the particle instancer PC, particle instance buffer, shortlist
  semantics, or the merge-only exclusive scan.

## Design decision B — GPU velocity ribbons

### Promise

Fast, coherent flows become readable without turning static particles into
streaks or allocating an unbounded per-particle path history.

### First implementation: instantaneous velocity ribbons

The first trail layer is a bounded velocity glyph, not a persistent particle
path. For a particle at head `p` with velocity `v`, its visual segment is:

```text
head = p
length = clamp(|v| * shutter_seconds, min_length, max_length)
tail = p - normalize(v) * length
```

This avoids stale geometry on merges, changing home windows, and topology
rebuilds. A persistent history ring is explicitly deferred: at 2.5 million
particles, only eight `vec4` history samples already require roughly 320 MB
before any segment/output buffers.

### Bounded selection

`compute/cassi_presentation_trails.glsl` writes a **separate** trail MultiMesh
buffer. It uses a fixed visual cap rather than an all-particle trail draw.

The prototype uses a deterministic stride/permutation over the particle index
space. Each slot samples one particle and emits a zero transform unless it
passes the frozen eligibility rule:

```text
speed >= speed_threshold
AND projected ribbon length >= minimum_pixels
AND particle mass is positive
```

This bounds work and is reproducible for a fixed seed/frame. It does not claim
top-score selection. A compaction/sorting pass is a later decision only if the
coverage gate shows the bounded sampler misses relevant flow structure.

### Trail instance/material ABI

Each trail instance is a separate 16-float record. The compute transform carries
head/segment tangent; custom/color carries bounded hue key, speed, fade, and
validity. `shaders/presentation_trail.gdshader` reconstructs a camera-facing
ribbon from the transform tangent and camera direction. It tapers alpha toward
the tail and remains dimmer than a particle core.

The pass reads the final render position and live velocity only after the final
blend in both renderer paths. In decoupled mode it binds the engine-owned live
velocity RID through a dedicated decoupled uniform set. It never uses the
meshless topology worker, which has no particle velocity ownership.

### Planned files

- `compute/cassi_presentation_trails.glsl`
- `shaders/presentation_trail.gdshader`
- `scripts/cassi_sim.gd`
- `scripts/contracts/layout.gd`
- `scenes/verify_presentation_trails.tscn`
- `scripts/verify_presentation_trails.gd`
- `research/presentation/verify_trails.py`

### Explicit non-goals

- No mutation of `_pos_buf`, `_vel_buf`, `_pos_render_buf`, or `_mm_rd_rid`.
- No new fields in `cassi_instancer.glsl` or its 128-byte PC.
- No default allocation of a full `N * K` history ring.

## Design decision C — true temporal fused-volume reprojection

### Promise

Field mode gains stable accumulated quality when camera and topology remain
compatible, while cuts, window motion, topology changes, and invalid depth
reject history on the first affected frame.

### Why the current hook is insufficient

The current fused-volume shader reads an RGBA history image at the same pixel
and mixes it only if `history_weight > 0`. The host binds a cleared neutral
texture and sends weight zero. More importantly, the output alpha is opacity,
not geometry depth, so it cannot safely reproject a past image.

### Required resources

The temporal path remains opt-in and does not grow the fused-volume PC.

1. Fused volume gains a `r32f` current representative-depth output image.
   The value is the opacity-weighted ray-distance first moment; it is not
   stored in alpha.
2. A new `compute/cassi_volume_reproject.glsl` resolves current color/depth
   against history color/depth.
3. Two history color/depth pairs avoid in-place image read/write hazards.
4. A small global-RD camera/history-state storage buffer records previous
   render-local origin, right/up/forward basis, FOV, dimensions, topology
   generation, render-query generation, and geometry/radiance key.
5. The visible `Texture2DRD` remains backed by a stable resolved output RID;
   texture wrapper churn is not used as a history mechanism.

The reproject shader owns its own bindings and PC, registered in
`layout.gd`. The existing fused PC stays exactly 32 floats / 128 bytes.

### Depth and rejection contract

For each current pixel, reconstruct a representative world/render-local point:

```text
p = current_origin + current_ray(pixel) * current_opacity_weighted_depth
```

Project `p` through the prior camera basis/FOV into prior UV. History is
accepted only when all conditions are true:

```text
history_enabled
AND prior state valid
AND topology status valid and overflow-free
AND topology_generation matches
AND render_query_generation matches
AND geometry/radiance key matches
AND previous UV lies inside the image
AND current/history representative depths agree within frozen tolerance
AND no camera cut, resize, mode transition, reinit, or texture rebuild occurred
```

A rejection writes current color only and records a typed reject reason. A
stable field/camera can accept history. If live optical payload changes without
a topology generation change, the first implementation uses a bounded history
weight plus the moving-field gate; a future field-data generation is required
before increasing acceptance weight.

### Planned files

- `compute/cassi_voronoi_fused_volume.glsl`
- `compute/cassi_volume_reproject.glsl`
- `scripts/cassi_sim.gd`
- `scripts/contracts/layout.gd`
- `scenes/verify_presentation_volume_history.tscn`
- `scripts/verify_presentation_volume_history.gd`
- `research/presentation/verify_volume_history.py`

### Explicit non-goals

- No same-pixel blend presented as reprojection.
- No reuse of alpha as depth.
- No history acceptance through topology/window/resize/camera-cut changes.

## Design decision D — manual-first camera direction

### Ownership model

A director is a pose source, not an independent process that writes the camera
in parallel with `free_camera.gd` or `main_recorder.gd`.

```text
MANUAL       free camera is sole writer.
DIRECTED     director computes a target pose; a single owner applies it.
RECORDER     main_recorder remains sole camera writer and samples a director pose.
```

In the interactive scene, `free_camera.gd` emits a manual-takeover request for
WASD, Shift/Ctrl, Q/E, right/middle drag, wheel, Z/X, or Tab input. The director
switches to MANUAL before the next transform write. CassiSim's startup framing
and F recenter participate in the same owner handoff rather than silently
overriding an active directed pose.

In the recorder, `main_recorder.gd` retains frame count, FPS, Movie Maker
lifecycle, logging, and quit ownership. It invokes a director pose sampler in
place of its direct fixed-orbit pose calculation; the director never adds a
second `_process()` camera writer.

### Presets

- **Wide envelope:** camera frames the live envelope with a bounded screen
  occupancy target.
- **Focus site:** camera targets a valid coherent macro site.
- **Flow follow:** camera follows a stable velocity-ribbon cluster only when
  the target has valid visual state.
- **Record orbit:** deterministic orbit around a declared target; no roll.

All transitions use critically damped position/orientation interpolation. A
missing target degrades to WIDE or MANUAL, never extrapolates stale topology
coordinates.

### Quality integration

There is no new global adaptive-quality controller in the first wave. The
existing volume dynamic-resolution controller remains the sole adaptive
resolution controller. Macro LOD and trails expose explicit fixed caps/quality
presets; any later coordinating governor must report every visual change in
telemetry and may never alter simulation timestep, grid resolution, particle
count, or field state.

### Planned files

- `scripts/cassi_presentation_director.gd`
- `scripts/free_camera.gd`
- `scripts/main_recorder.gd`
- `scripts/cassi_sim.gd`
- `scripts/sim_ui.gd`
- `scenes/main.tscn`
- `scenes/main_recorder.tscn`
- `scenes/verify_presentation_director.tscn`
- `scripts/verify_presentation_director.gd`

## Implementation order

1. Macro LOD: fixed 8,192-site layer, separate MultiMesh, crossfade gate.
2. Velocity ribbons: bounded instantaneous glyphs, no history ring.
3. Volume reprojection: auxiliary depth plus resolve/history resources.
4. Director: consume accepted visual state, then optional recorder presets.
5. Only after all individual gates pass, consider a coordinated quality preset.

Every implementation step first updates `scripts/contracts/layout.gd`, the
matching shader header, host allocation, uniform-set lifecycle, and focused
verification artifact together. The full 33-arm battery runs only after an
implemented renderer wave, with no user-owned Godot process active.
