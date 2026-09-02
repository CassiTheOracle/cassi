# Unified Particle World Agent Pre-registration

## Status: Frozen—2026-09-01

This plan freezes the first player-visible integration of Cassi's persistent field-language runtime with the authoritative CassiCosmos particle state. It replaces the split between manual workbench editing and future agent actions with one typed, reversible `FieldWorkbench` command pipeline.

## Player-visible promise

In the ordinary `scenes/main.tscn` scene, the user can open Workbench, type a bounded natural-language particle request, receive a field-generated reply plus a canonical staged operation, preview it, press Apply while paused, step or resume the simulation, receive a measured result receipt, and undo to the exact pre-apply checkpoint.

The adoption phrase is:

> Arrange the selected particles into a ring around the orange cursor.

The adopted path must work with the shipped default `physics_decoupled = true`. A small inline configuration may be used only as a focused development control; disabling decoupled physics is not an acceptable product result.

## Existing authority and non-claims

The implementation starts from the code that exists:

- `CassiFI/cassi_field_language.py` and `cassi_persistent_provider.py` own the current persistent field-language session;
- `CassiCosmos/scripts/field_workbench.gd` owns paused mutation validation, command ordering, checkpoints, replay, and receipts;
- `CassiCosmos/scripts/cassi_physics_engine.gd` owns the authoritative particle and field buffers in decoupled mode;
- `CassiCosmos/scripts/cassi_sim.gd` owns inline buffers, render publication, and the Workbench host seam;
- `CassiCosmos/scripts/sim_ui.gd` owns the player-facing Workbench UI.

The absent `CassiQiFlowEngine`, port-8087 Godot adapter, and adapter brief are target designs rather than runtime dependencies. This slice uses the existing loopback HTTP provider at port 8086 and adds explicit world-turn/result routes. Port 7599 remains read-only field telemetry and is not used for particle actions.

The existing six-lobe `CassiFieldIntelligenceRuntime` remains a default-off embodied-learning laboratory. It is not enabled as a second adaptive policy in the player-facing path. The one persistent CassiFI field remains the agent's adaptive state; CassiCosmos Yang/Yin and particle buffers are world state.

## One editing pathway

Every manual or chat-originated mutation is normalized by `FieldWorkbench` into one canonical command before execution. The UI does not write GPU buffers, and chat does not have a second actuator.

Existing tools map into the same command grammar:

- `deposit` mutates the selected Yang/Yin field region;
- `align` mutates the selected field direction;
- `impulse` mutates selected particle velocity;
- `arrange` maps selected live particles to deterministic target positions or steering velocities.

The Workbench continues to require pause and explicit Apply. Chat stages a command and preview; it never applies on receipt.

## Canonical particle program

The schema is `cassi.particle-program.v1` with these top-level keys:

- `schema`;
- `operation`;
- `selection`;
- `target` when required;
- `motion`;
- `constraints`;
- `source`;
- `request_id`.

Supported selectors in this slice:

- `all`;
- `sphere {center, radius}`;
- `box {center, half_extents}`.

Supported targets in this slice:

- `line`;
- `ring`;
- `sphere`;
- `grid`;
- `helix`;
- `double_helix`;
- `point_cloud`;
- `translate`;
- `scale`;
- `rotate`.

Supported motion policies:

- `exact`, which writes target positions and applies the declared velocity policy;
- `steer`, which writes a bounded velocity toward each target and leaves positions unchanged until physics advances.

All values must be finite. Operations preserve particle count and `pos.w` mass. Delete, spawn, arbitrary code, arbitrary shaders, file-system paths, and model-generated executable expressions are outside this schema.

## Exact-count target rule

Let the selected live particle IDs, sorted ascending, be `S = [s_0, ..., s_(n-1)]`. Every accepted target resolves deterministically to exactly `n` target positions `T = [t_0, ..., t_(n-1)]`. Assignment is `s_j -> t_j` in this slice.

Procedural generators are indexed directly by `j` and `n`, so they always produce exactly `n` points. Their formulas use fixed axis-basis and tie-breaking rules.

A point cloud is canonicalized by rejecting non-finite points and sorting by `(x, y, z, original_index)`. For `m` canonical source points and `n` selected particles:

- `m = 0` rejects;
- `m = 1` repeats the sole point exactly `n` times;
- otherwise each target samples the canonical polyline at normalized arc-length `(j + 0.5) / n`, with deterministic linear interpolation.

This is the only up/down-sampling rule. It is deterministic, returns exactly `n` points, and is recorded in the receipt.

## Validation and limits

The validator rejects before mutation when any condition fails:

- the simulation is playing;
- the Workbench or authoritative buffers are unavailable;
- schema or operation is unknown;
- any number is non-finite;
- selector or target is outside the live world bounds after clamping policy;
- no live particles are selected;
- selected count exceeds `maximum_particles`;
- any exact displacement exceeds `maximum_displacement`;
- any steering speed exceeds `maximum_speed`;
- the command changes particle count or mass;
- the request ID is malformed or already applied with different content.

The initial defaults are conservative and explicit in the normalized command. Manual UI fields and chat programs pass through the same limits.

## Authoritative decoupled seam

`FieldWorkbench` continues to read and write through host callables. In inline mode the host accesses inline buffers. In decoupled mode the host delegates to new paused-only `CassiPhysicsEngine` Workbench methods that access the engine-owned buffers.

A successful decoupled write must:

- update engine position and velocity buffers;
- update field buffers for field operations;
- zero the cached acceleration buffer after a position change;
- set the engine gravity warm-up flag;
- refresh the simulation's previous/render position buffers;
- invalidate interpolation so stale positions are not rendered;
- preserve buffer sizes and mass values;
- leave the simulation paused until the user steps or resumes.

No chat or UI path accesses `_pos_buf` directly.

## Preview and undo

Before Apply, `FieldWorkbench.preview_command()` resolves the selection and target without mutation and returns a bounded sample of target positions plus count, bounds, maximum displacement, and normalized command digest. `cassi_sim.gd` displays those sample points as a ghost `MultiMesh`.

Apply captures an automatic exact checkpoint immediately before mutation. `undo_last()` restores that checkpoint, including field buffers, particle buffers, clock, and command lineage. A new successful Apply replaces the one-level automatic undo checkpoint; named/manual checkpoints remain available.

## Chat and provider contract

The existing port-8086 provider gains:

- `POST /v1/world/turn`;
- `POST /v1/world/result`.

A world turn contains only bounded JSON: `user`, `world_id`, `message`, current cursor/selection context, particle count, world bounds, and optional explicit particle program. The provider feeds the user message through the current persistent field-language completion path and compiles a candidate particle program with the deterministic bounded parser. It returns the field response, staged program or clarification, request ID, and field receipt.

The deterministic parser covers the registered selectors, targets, transforms, and numeric units. An optional stateless Qwen planner URL may provide a schema-constrained candidate program, but its result passes through the same local normalizer and validator; provider session memory remains in the field. Qwen unavailability falls back only to the deterministic parser, not to a second learned state.

A result contains the original request ID, normalized program digest, applied/rejected status, pre/post state digests, affected count, displacement/error metrics, and world step. The provider feeds a canonical result observation through the same field session exactly once and returns the grounded follow-up response. Duplicate identical results return the prior response; conflicting duplicates reject.

The Godot Workbench client binds only to `127.0.0.1`, uses a configured session ID, never executes a returned program automatically, and posts a result only after local Apply or rejection.

## Workbench UI

The existing Workbench page is updated rather than adding a second editor. It gains:

- chat transcript;
- message input and Send;
- field connection/session status;
- target-shape options for manual staging;
- Preview;
- Apply;
- Undo;
- the existing Pause/Resume and Step controls;
- affected count and result metrics.

Existing Deposit, Align, and Impulse controls remain and produce the same canonical command type. Text inputs consume keyboard focus only while editing so camera controls remain usable.

## Focused verification fixture

The focused scene uses a small deterministic particle count, default decoupled physics, periodic grid, fixed seed, merge off, black holes off, moving window off, and Workbench enabled. It starts paused.

The fixture stages a sphere selection and ring target, previews, applies, reads the authoritative engine buffers, steps once, undoes, and reads again. A local provider smoke sends the adoption phrase and verifies the staged program and result round trip.

## Gates

- **PWA0—Single command authority:** manual and chat commands both normalize through `FieldWorkbench`; no second particle mutation path exists.
- **PWA1—Schema and exact count:** every generator and point-cloud resampler returns exactly the selected live count; malformed, non-finite, empty, oversized, or out-of-budget programs reject before writes.
- **PWA2—Default-off identity:** with no staged command and chat disabled, the existing simulation path has no extra mutation dispatch or buffer write.
- **PWA3—Decoupled authority:** the ring operation works with `physics_decoupled = true` against engine-owned buffers; stale simulation mirrors are not mutated as authority.
- **PWA4—Mutation invariants:** selected count matches, target RMS error meets the frozen tolerance, mass/count are unchanged, all values are finite, and nonselected position/velocity bytes are unchanged.
- **PWA5—Cache and render coherence:** cached acceleration is invalidated, gravity warm-up runs before the next KDK step, rendered positions reflect the applied generation, and one post-apply step remains finite.
- **PWA6—Preview purity:** preview returns the same normalized digest and target sample as Apply but leaves every authoritative buffer and clock byte-identical.
- **PWA7—Exact undo:** automatic Undo restores supported buffers and clock byte-for-byte and restores the pre-apply digest.
- **PWA8—Chat staging:** the adoption phrase produces a canonical ring program and field response; no mutation occurs before Apply.
- **PWA9—Result grounding:** Apply/reject receipts round-trip to the same provider session exactly once; duplicate identical receipts are idempotent and conflicting duplicates reject.
- **PWA10—UI playability:** the ordinary Workbench page exposes Send, Preview, Apply, Undo, Pause/Resume, and status; focus does not consume camera input outside text editing.
- **PWA11—Performance:** focused and shipped particle counts record readback, normalization, write, preview, and post-step latency; no device loss or TDR occurs. The CPU paused-edit implementation is retained unless measurement requires a GPU compaction/generator path.
- **PWA12—Regression:** the focused verifier passes, then the complete CassiCosmos battery passes without modifying existing gate thresholds.

## Decision tree and stopping rule

PWA0 through PWA10 and PWA12 are hard correctness gates. Any failure blocks adoption. PWA11 records measured performance; device loss, TDR, or an operation exceeding the existing per-arm timeout blocks adoption, while a slow but bounded paused edit is reported as a measured limitation rather than silently replaced.

One implementation repair and one rerun are allowed under this frozen protocol. Gate thresholds and fixtures are not loosened after observing results. The final verdict is `ADOPT`, `REJECT`, or `INCONCLUSIVE`.
