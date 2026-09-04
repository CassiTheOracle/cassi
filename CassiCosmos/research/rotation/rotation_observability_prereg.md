# Production rotation observability — preregistration

Status: PRE-REGISTERED before implementation and the first GPU run — 2026-09-02

## Scope

Expose the accepted default-off rotation sector through the production decoupled publication path and a separate read-only orientation layer. The layer may read live particle positions and object quaternions, but it writes only its renderer-owned MultiMesh instance buffer. It cannot alter positions, velocities, merge spin, field displacement/momentum, heat, or engine orientation.

This campaign tests observability only. It does not change or re-open G75–G82, establish a physical scale law, or claim that visible rods are literal particle shapes.

## Frozen implementation contract

1. `rotation_stress_enabled=false` remains the default. The new orientation layer also defaults off and allocates no MultiMesh, uniform set, shader, or pipeline when the rotation sector is disabled at initialization.
2. The engine adds a compact publication readback containing its 16-float telemetry block and at most the first 16 particle quaternions. It must not read back displacement, momentum, spin/heat, matter aggregates, particle positions, or particle velocities.
3. The normal decoupled publish dictionary carries that compact state only on the existing accepted telemetry cadence. `CassiSim.rotation_snapshot()` returns a deep copy of the latest state; it never exposes mutable engine storage or RIDs.
4. The renderer obtains the orientation storage-buffer RID through a separate zero-readback resource view. The RID is never included in the CPU snapshot.
5. The orientation layer is a separate `MultiMeshInstance3D` named `RotationOrientationAxes`. Its compute pass reads interpolated render positions and normalized quaternions and writes one thin cyan axis transform per live particle. Dead particles receive zero transforms. Axis length is `2.5 * particle_size`, width is `0.12 * particle_size`, and the layer uses the same conservative particle culling bounds as the base renderer.
6. The layer is initialized only when both rotation and orientation-render toggles are enabled before `reinit()`. Turning its visual toggle off frees the MultiMesh and uniform set. The physics buffers remain authoritative.

## Focused scene

`verify_rotation_observability.tscn` uses the production `CassiSim` node with the decoupled global RenderingDevice, 64 particles, a 4-cubed rotation grid, two scale rungs, and the smallest existing stable field/site settings. It first boots with both rotation toggles off, records the disabled state, then enables both and calls the production `reinit()` path. It waits for an accepted publication and at least one rendered instance-buffer update. The scene is always run windowed.

## Registered gates

### G83 — default-off observability

PASS requires, before the enabled reinitialization:

- `rotation_snapshot().enabled == false`;
- no child named `RotationOrientationAxes`;
- no valid orientation-render MultiMesh RID, uniform set, shader, or pipeline; and
- production setup remains ready.

### G84 — bounded production publication

PASS requires after enabled reinitialization:

- snapshot `enabled == true`, `telemetry_count == 16`, and `orientation_sample_count == min(16, N_particles)`;
- exactly 16 telemetry floats and `4 * orientation_sample_count` quaternion floats;
- every sampled quaternion finite with norm error at most `1e-5` for a live initialized particle;
- no field, particle-position, particle-velocity, spin/heat, matter, buffer, or RID keys;
- serialized snapshot size below 4096 bytes; and
- two calls to `rotation_snapshot()` return distinct dictionaries so mutating a caller copy cannot mutate the stored publication.

### G85 — read-only orientation rendering

PASS requires:

- the enabled child exists, is visible, owns a MultiMesh with 64 instances, and exposes a valid renderer buffer RID;
- the GPU-written instance buffer has exactly `64 * 16` floats, all finite;
- at least one live record has nonzero basis length, opaque color, and a finite position;
- the corresponding sampled engine quaternion is unchanged across a renderer-only dispatch; and
- disabling only `rotation_orientation_render_enabled` removes the child and invalidates its renderer buffer/uniform-set handles while `rotation_snapshot().enabled` remains true.

## Decision tree and stopping rule

G83–G85 must all pass. Shader import/compile failure, missing global RenderingDevice, timeout, device loss, malformed receipt, or a failed invariant is `INCONCLUSIVE—IMPLEMENTATION` and stops acceptance until the defect is corrected without changing these values or tolerances. A scientific negative is not possible because this is an implementation-observability campaign.

The scene writes `_diag/rotation_observability.json` with gate details and exits 0 only on all three passes. After focused acceptance, the actual windowed surface must be inspected, and the full battery remains the regression contract.
