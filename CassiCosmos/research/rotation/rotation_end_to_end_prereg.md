# Live merge-to-orientation production scenario — preregistration

Status: PRE-REGISTERED before implementation and first run — 2026-09-02

## Question and boundary

Can the production physics-engine sequence acquire angular momentum from a real particle merger, store it in the canonical merge-spin buffer, advance the surviving object's quaternion on subsequent production steps, and publish that quaternion through the bounded production API without planting merge spin or orientation?

This scenario tests live acquisition-to-observation wiring. It does not add or claim a spin-dependent force, quadrupole, rigid-body surface velocity, or cloud circulation. Those require a nonspherical matter action that is not derived in this campaign. The result therefore establishes a rotating resolved orientation, not a proton model or a stellar/proton identity.

## Frozen fixture

A windowed local RenderingDevice runs one `CassiPhysicsEngine` with four particles. The canonical field is reset uniformly to `EY=phi`, `EI=1`, `q=phi^2+1`, and `FieldVel=0` so the established merge coherence gate is deterministic.

- Pair indices 0 and 1: masses 10, positions `(5,0,0)` and `(5.4,0,0)`, velocities `(0,3,0)` and `(0,-5,0)`.
- Environment indices 2 and 3: masses 5 at `(-15,0,0)` and `(15,0,0)`, zero velocity.
- Pair internal angular momentum is exactly `(0,0,-16)` in simulation units.
- Canonical grid 64, `dt=1e-6`, cluster radius 25, gravity mode 2, source strength 0, frozen two-fluid field, merge cadence 1, virial merge gate off.
- Rotation stress enabled with grid 32, three rungs, field inertia 2, `c_T=c_L=0`, scale frequency 0, exchange rate 0, reservoir inertia 3, and both explicit reservoir couplings 0. The harness advances 16 post-merge production steps: the declared solid-sphere inertia at this resolution predicts a quaternion displacement above `1e-6` while the total physical interval remains only `1.6e-5`.

No call to `rotation_write_state` is allowed. Engine setup must supply identity quaternions and zero merge spin. Particle and canonical-field buffers are the only planted state.

The harness records three states:

1. `before`: setup state before a production step;
2. `post_merge`: after `engine.step(1)`, whose local-RD merge pass runs after the rotation pass;
3. `post_orientation`: after 16 additional calls to `engine.step(1)`, each of whose rotation passes sees the live merge spin.

It then calls `rotation_publish_state(4)` and records the bounded snapshot. Full arrays are verifier-only. Raw output is `_diag/rotation_end_to_end_gpu.json`; the independent verifier writes `_diag/rotation_end_to_end_verify.json`. Both receipts bind complete configuration, producer source, verifier source, preregistration, and raw content by SHA-256.

## Registered gates

### G97 — live angular-momentum acquisition

The initial merge-spin bytes must be zero. The first production step must leave exactly three live particles, exactly one of pair 0/1 alive, and both environment particles alive. The surviving pair spin must match `(0,0,-16)` to relative `1e-3`.

### G98 — causal orientation advance

The survivor quaternion must be identity to absolute `1e-7` before and immediately after the merge step. After 16 post-merge production steps it must differ from identity by more than `1e-6`, have norm error no greater than `1e-5`, and have a quaternion-vector component aligned in sign with the acquired spin axis. Every orientation value must be finite.

### G99 — bounded production publication

`rotation_publish_state(4)` must report enabled, four samples, 16 telemetry floats, both closed reservoir couplings, and the configured reservoir inertia. Its survivor quaternion must match the full verifier readback to absolute `1e-7`. Invalid telemetry must be zero, and both reservoir momentum arrays must remain byte-zero because the boundaries are closed.

### G100 — merge ledger closure

Across `before` to `post_merge`, total particle linear momentum must close to relative `1e-3`. Particle orbital angular momentum about the live center of mass plus live merge spin must close to relative `1e-3`. Environment position/velocity/mass state change must remain no greater than `1e-5` relative.

## Decision and stopping rule

G97–G100 all PASS: `PASS_LIVE_MERGE_TO_ORIENTATION`.

Any source/configuration/hash/shape/nonfinite/acquisition defect: `INCONCLUSIVE—IMPLEMENTATION`.

Any valid failed gate: `FAIL_LIVE_MERGE_TO_ORIENTATION`.

Run the windowed scene once and the independent verifier once. Retain all outcomes; do not tune the pair, thresholds, timestep, sequence, or field and rerun under this preregistration.
