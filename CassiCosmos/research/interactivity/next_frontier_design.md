# Interactive Field Workbench: Completion Design

## Status: Implementation design—2026-08-18

## Runtime layers

1. `CassiSim` owns RenderingDevice resources, authoritative buffers, simulation time, the camera ray, and the visible cursor marker.
2. `FieldWorkbench` owns command validation, the ordered ledger, CPU reference operations, checkpoint compatibility, branch summaries, scenario serialization, and observable names.
3. `sim_ui.gd` stages user intent. It arms viewport placement explicitly and never treats camera or lens changes as physics commands.
4. `cassi_workbench_field.glsl` and `cassi_workbench_particle.glsl` execute bounded align and impulse operations on the authoritative inline buffers. Optional workbench shaders do not participate in the core `_shaders_ready` gate.
5. The focused verifier creates a low-cost inline 64³ fixture and exercises coordinates, CPU/GPU parity, cursor mapping, checkpoints, branches, recipes, and the guided signature.

## Command queue

The queue is validated at insertion. `apply_queued` preserves insertion order and chooses a backend per operation:

- align and impulse: host GPU command callback when available;
- normalized deposit: CPU reference route until the deterministic reduction promotion passes;
- all commands: CPU route in the pure reference verifier.

The host callback returns the measured affected element count. The ledger records requested parameters, backend, applied step, and affected count. GPU commands are recorded into one compute list in queue order with a barrier between commands that may touch the same buffer. Global RenderingDevice rules apply: no manual `submit()` or `sync()`.

## Direct manipulation

The UI exposes a `Place in viewport` toggle. A left click projects a camera ray into the live field box. If the camera starts inside the box, the cursor lands on the camera-facing plane through the live window center and is clamped to the box. If outside, slab intersection selects the first positive box hit. The marker is a CassiSim child displayed at `cursor_world-window_center`, so tracking movement cannot create a world/local mismatch.

Numeric center controls and viewport placement call the same `workbench_set_cursor` API. The UI receives cursor updates through a signal and uses no-signal setters. Disarm conditions are tab exit and rail collapse.

## Checkpoints and branches

The controlled branch implementation deliberately rejects hidden state it cannot restore. Its compatibility signature freezes inline/grid ownership and disabled merge, black-hole, meshless, decoupled, and tracking features. The checkpoint carries the exact authoritative CPU-readable buffers, step count, time, extents, and window center. Restore writes all captured buffers and restores step/time.

A summary stores digest, mean field intensity, mean bounded coherence, mean absolute disequilibrium, live particle count, mean particle speed, step, and time. Difference view is a numeric dictionary with baseline/branch/delta values and one set of scales frozen from the checkpoint. This remains valid while the active field-slice renderer is incomplete.

## Procedural recipes

Recipes are data: `{kind, center_normalized, scale_normalized, amplitude, ...}`. The composer deterministically converts normalized coordinates to world-space operations for the current anisotropic box and window center. Recipes feed the same command API, avoiding a second mutation convention.

## Signature scenario

The signature is a measurement fixture rather than a cinematic claim. It constructs two equal-intensity regions with different channel directions and reports field intensity, bounded coherence, and disequilibrium separately. The result is suitable for the UI's guided-scenario card and the verifier because its expected inequality follows directly from the frozen definitions.
