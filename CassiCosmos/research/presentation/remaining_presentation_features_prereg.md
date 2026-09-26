# Remaining CassiCosmos presentation features — preregistration

**Status:** FROZEN BEFORE IMPLEMENTATION OR PERFORMANCE RUNS  
**Date:** 2026-08-20  
**Scope:** presentation-only macro LOD, velocity ribbons, fused-volume temporal reprojection, and camera direction.  
**GPU target:** RX 7900 XTX / Godot 4.7.1 / windowed RenderingDevice scenes.

## 1. Evidence rule

This is a measurement contract, not a result. No feature is enabled in the
production presentation scenes until its focused arm, raw artifact, and gate
table exist. A screenshot alone cannot establish a buffer, parity, temporal,
or performance result.

Frozen verdict vocabulary:

- `PASS`: every applicable gate passes with complete evidence.
- `FAIL`: an applicable threshold is violated.
- `INVALID`: required identity, readiness, finite-state, or accounting evidence
  is missing.
- `REJECT`: a default-off/parity or correctness gate fails.
- `HOLD`: correctness passes but the declared performance/quality threshold does
  not; no downstream adoption is allowed.
- `ADOPT`: all mandatory gates pass and the feature may be enabled by a
  presentation scene.

Each claim is labeled `T1 measured`, `T2 inferred from T1`, or `T3 design
expectation`. A missing measurement remains `INVALID`.

## 2. Frozen arms

| Arm | Feature | Control | Counterfactual | Required artifact |
|---|---|---|---|---|
| P0 | Default-off parity | current profile-off scene/path | same seed, same frames, new feature resources absent/disabled | raw render/dispatch/buffer identity record |
| M1 | Macro-site LOD | presentation particles + macro layer off | same camera sweep with macro layer on | per-frame macro records, site generation, image metrics |
| T1 | Velocity ribbons | presentation particles + trail layer off | same state with bounded instantaneous ribbons on | trail instances, alignment/count stats, frame timings |
| V1 | Temporal volume | fused volume history off | same deterministic field/camera sequence with reprojection on | color/depth/history/reject stats and raw frames |
| D1 | Camera director | manual/free-camera or recorder control | one declared director preset at a time | pose timeline, ownership events, occupancy metrics |

Every arm uses a fresh windowed process, fixed seed/configuration, and an
explicit producer/resource identity. A new resolution, cap, threshold, seed,
producer, or camera path is a new preregistered arm.

## 3. Required diagnostic record

Every feature arm records JSON or equivalent machine-readable data containing:

1. scene/resource/shader paths and hashes where available;
2. fixed seed and all visual/physics configuration values;
3. profile flags and default-off state;
4. topology generation, render-query generation, site count, status, overflow,
   and readiness;
5. camera transform/FOV/viewport and current window center/extents;
6. MultiMesh RID, instance count, buffer byte size, and sampled finite records;
7. compute dispatch labels/order, host wall time, readbacks/uploads, and bytes;
8. frame index, simulation time, feature cap, selected/visible count;
9. raw output path and gate values, with `unknown` distinct from zero.

## 4. Common gates

### G0 — launch and finite state

The fresh windowed arm reaches its declared ready marker. All sampled positions,
velocities, transforms, custom data, topology fields, output pixels, counts, and
timings are finite. Any missing readiness/resource identity is `INVALID`.

### G1 — profile-off identity

P0 default-off output, instance bytes, dispatch order/count, push constants,
and resource bindings are byte-identical to the unchanged current path for the
short frozen run. A visual screenshot is not a substitute. Any difference is
`REJECT`.

### G2 — bounded resource lifecycle

Feature resources are allocated only when enabled, freed on reinit/shutdown,
and never resize an existing particle MultiMesh or its buffer. Every emitted
record is inside its declared capacity; no stale record survives a generation,
reinit, or disable transition.

### G3 — no simulation mutation

The feature arm and its control arm produce identical particle position, mass,
velocity, field, topology, and solver telemetry samples. Any difference is
`REJECT`, even if the image looks better.

### G4 — runtime safety

No invalid RID, shader binding error, device loss, TDR, unbounded backlog, or
non-finite output occurs. A timeout or device loss is `FAIL`, not a visual pass.

## 5. Macro-site LOD gates

### M1.1 — topology/index coherence

Macro rendering is enabled only with a valid, overflow-free topology generation
and exactly the published site count. The position/optical index mapping is
finite and one-to-one for all emitted sites. A generation change suppresses or
atomically replaces the macro output; mixed generations are `FAIL`.

### M1.2 — bounded output

The first implementation emits at most 8,192 macro records, uses a dedicated
16-float/64-B MultiMesh record, and never changes the particle MultiMesh count or
buffer. Capacity, count, AABB, and sampled records are reported.

### M1.3 — transition continuity

A deterministic wide-to-close camera sweep crosses both LOD thresholds. During
the crossfade, no frame may contain a non-finite record or a complete macro/near
blanking event. Relative luminance discontinuity in the transition band must be
`<= 0.20` at p99 against the same sweep with the transition sampled at twice the
frame rate. Any one-frame pop above `0.50` is `FAIL`.

### M1.4 — far-field visibility

At the frozen far camera pose, the macro arm must increase occupied foreground
coverage or cluster-silhouette contrast over the particle-only arm. If the
signal is absent under a valid arm, the result is `NULL`, not a forced `PASS`.

### M1.5 — cost

At the frozen 500k-particle presentation smoke configuration, macro dispatch and
raster overhead must remain within `+15%` of the particle-only presentation
frame-time median, with no unbounded per-frame CPU readback. A missing timing
record is `INVALID`.

## 6. Velocity-ribbon gates

### T1.1 — direction and stationary behavior

Stationary or below-threshold particles emit zero visible trail records. For
selected moving particles, the measured ribbon tangent must agree with the
signed velocity direction within 5 degrees after the declared world/window
transform.

### T1.2 — bounded selection and lifecycle

Trail count never exceeds the frozen cap, all records are finite, and a disable,
reinit, dead-mass mark, or world-window update leaves no stale record visible in
the next settled frame.

### T1.3 — visual motion signal

On the frozen moving-stream arm, trail-on must increase the predeclared
flow-direction coverage metric without increasing the stationary-particle
false-positive rate above 1%. If flow signal does not emerge, verdict `NULL`.

### T1.4 — cost and memory

The first arm uses instantaneous velocity glyphs only; no `N*K` history allocation
is permitted. Additional trail rendering must stay within `+20%` of the matching
particle-only frame-time median and its allocated bytes/cap are recorded.

## 7. Temporal-volume gates

### V1.1 — current output contract

RGB remains radiance and alpha remains Beer–Lambert opacity. Representative
ray-depth is written to its declared auxiliary depth image and never overwrites
alpha. All pixels and depth values are finite; opacity remains in `[0,1]` within
`1e-6`.

### V1.2 — stable acceptance

With unchanged field generation, render-query generation, geometry, camera, FOV,
resolution, and radiance-affecting controls, history is rejected on the first
frame, then may be accepted after the first settled history frame. Accepted
history must remain within p99 absolute color error `<= 0.10` against the
history-off reference, with p99 alpha error `<= 0.02`.

### V1.3 — first-frame rejection

The first affected frame rejects history on each injected event:

- topology generation or status change;
- render-query generation/window center/extents change;
- camera cut, FOV/viewport/resize change;
- mode/profile/radiance-control change;
- texture/resource rebuild, reinit, shader reload, or device recovery;
- invalid/out-of-bounds reprojection or depth disagreement.

A stale prior color contribution on the first affected frame is `FAIL`.

### V1.4 — bounded history

Ping-pong resources or an explicit copy pass prevent in-place image hazards. The
resolved Texture2DRD seam remains valid. History state, depth resources, reject
reasons, and accepted/rejected counters are reported; missing reasons are
`INVALID`.

### V1.5 — cost

At each frozen 256 and 512 output tier, temporal resolve overhead and memory are
reported separately from the existing dynamic-resolution controller. No arm may
silently increase the existing tier or alter physics/field resolution.

## 8. Director gates

### D1.1 — ownership

At every frame exactly one camera owner is recorded: `MANUAL`, `DIRECTED`, or
`RECORDER`. Manual input wins within one input frame. The director never writes
the Camera3D concurrently with `free_camera.gd` or `main_recorder.gd`.

### D1.2 — deterministic pose

For fixed seed, preset, camera start, and frame cadence, the pose timeline is
deterministic within `1e-4` position units and `1e-4` quaternion component error.
No roll exceeds 0.5 degrees unless a future preset explicitly declares roll.

### D1.3 — framing

Wide/focus/flow presets keep their declared target inside the camera frustum and
meet the frozen occupancy interval `[0.20, 0.80]` of the shorter viewport axis.
Invalid or stale targets fall back to a valid wide/manual state.

### D1.4 — recorder compatibility

Recorder frame count, FPS, Movie Maker lifecycle, output resolution, progress,
and quit behavior are unchanged. The director supplies only sampled camera pose.

## 9. Stopping rules and implementation order

1. Stop an arm at the first `INVALID`, `FAIL`, or `REJECT`; do not tune a later
   threshold in the same arm.
2. If G0–G4 fail, stop all downstream feature work until the resource/identity
   contract is repaired.
3. If a feature signal is absent under a valid control/counterfactual pair,
   record `NULL` and do not increase brightness, count, or trail cap to force a
   visual result.
4. Implement and gate in this order: M1, T1, V1, D1.
5. Run the complete 33-arm battery only after the relevant focused arm passes;
   never edit an existing verification asset to make it pass.
6. Production scenes remain unchanged until the verdict is `ADOPT`.
