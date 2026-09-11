# GPU trajectory shell and ancestry probe

## Status: Frozen—September 10, 2026

## 1. Question

Does the CassiCosmos particle evolution produce measurable radial shell structure
and persistent merger ancestry under a fixed initial condition, and can those
claims be distinguished from a transient visual concentration?

This probe records particle trajectories and merge edges. It does not establish
that the simulated particles are physical elementary particles, that a shell is
bound, or that the Cassi field derives particle identity. The recorded events
are hops accepted by the existing particle-merge rule under its coherence gate.
The probe never dispatches the condensation scanner, spawns a black-hole
record, or transfers mass from the field to the particle population; it
measures the particle-merge path alone, and is not a test of the fluid-to-
matter collapse pathway.

## 2. Registered implementation

The physics engine receives a default-off passive trajectory recorder. The
recorder runs as GPU compute work in the same command list as the particle
integrator and reads the authoritative position and velocity buffers after each
accepted step. The merge-event pass runs after each accepted hop, reading the
post-hop centroid/momentum accumulators before merge finalization. It writes no
particle, field, merge, gravity, or render state.

A fixed set of particle indices is sampled. Each sample stores position and
mass in one `vec4`, velocity and radial velocity in another `vec4`, and the
accepted step in a ring-indexed step array. The merge pass separately records
each accepted sink-rule hop as `source → survivor` in an 80-byte record:
`uvec4` metadata plus pre-hop source position/mass and velocity/radial velocity,
and post-hop survivor position/mass and velocity/radial velocity. Particle
indices are the stable identity key; merge survivors retain the lowest index by
the existing merge contract.

Radial boundary crossings and turnarounds are derived from adjacent stored
samples. The registered sample stride is their temporal resolution. The
recorder is allocated and dispatched only when the explicit trajectory
configuration is enabled. The default configuration leaves the existing GPU
resource graph and dispatch sequence unchanged.


## 3. Frozen controls

The harness has two modes:

- `shell`: nested-shell initial geometry, inward initial motion, merge disabled;
- `ancestry`: the same deterministic geometry and seed, merge enabled, with a
  fixed coherent field plant (`E_Y = \varphi`, `E_I = 1`) so the existing
  coherence and mechanical binding gates are exercised without changing their
  thresholds.

Command-line inputs select the mode, seed, particle and tracer counts, step
count, sample stride, merge cadence, shell radii, and output directory. A
qualifying run must record the complete configuration and engine mode in its
receipt. The long-horizon target is
1,000,000 accepted steps, sampled every 4,096 steps, with 4,096 tracers and a
256-slot history ring; smaller runs are implementation checks only.

The default geometry is `initial_condition = Nested shells`,
`initial_arrangement = Ring`, and `initial_motion = Inward`. The harness uses a
fixed seed of `20260910`, `dt = 0.001`, `grid_N = 64`, and the explicit box and
cluster values written in its receipt. The shell boundaries are fixed at 25% and
75% of the recorded initial radial support unless command-line values override
them.

## 4. Measurements

The analysis script consumes only the raw receipt and binary arrays. It computes:

1. shell occupancy by radial bin at every stored history slot;
2. radial density contrast relative to the initial occupancy;
3. inward and outward crossing counts at both registered boundaries, with
   crossings resolved at the sample stride;
4. turnaround counts from sign changes in sampled radial velocity and the
   fraction of tracers remaining finite and alive;
5. the merge-edge count, unique source/survivor IDs, maximum ancestry depth, and
   connected-component size distribution;
6. mass closure from initial/final live-particle summaries and the source/survivor
   masses in the merge event ledger.

A shell candidate is reported when a radial bin has a local occupancy maximum
that persists for at least three consecutive stored history slots and its
contrast exceeds 1.5 relative to the initial occupancy. This is a descriptive
criterion, not a universal shell definition. A run with no candidate is a
negative result and remains a valid completed probe.

Contrast is the bin's share of live tracers at the stored slot divided by its
share at step zero. A bin that holds no tracers at step zero has no ratio, so
its baseline share is the one-tracer floor `1/N`: the smallest non-zero
occupancy the bin can hold. A candidate in such a bin therefore reports the
filling of an initially empty region, and its contrast scales with the tracer
count rather than with a measured ratio. Every candidate carries its step-zero
occupancy, so the stricter criterion—a local maximum in a bin that was already
occupied at step zero—can be read directly from the analysis output.

## 5. Decision rules

- Recorder allocation, shader import, command-list execution, readback, or
  artifact serialization failure: `FAIL`.
- Any nonfinite recorded value, counter overflow, truncated binary artifact, or
  merge mass ledger mismatch above `1e-4` relative: `FAIL`.
- A shell candidate satisfying the registered persistence and contrast rule:
  `SUPPORTS` transient shell formation for this configuration.
- No shell candidate: `DOES NOT EMERGE` for this configuration.
- A nonempty, internally consistent merge graph: `SUPPORTS` recorded ancestry
  formation for the observed merge events.
- No merge edges under the active gates: `DOES NOT EMERGE` for ancestry in that
  control; it is not evidence against particle formation in another regime.

No threshold, seed, boundary, initial condition, or stopping rule changes after
inspection of a qualifying receipt. A runtime failure is repaired and rerun
with the same frozen inputs; a scientific negative is not tuned through.

## 6. Evidence retention

Each run writes a JSON receipt and the following raw arrays under
`_diag/matter_formation/trajectory_<mode>/`:

- `tracer_ids.bin`—uint32 particle identities;
- `sample_steps.bin`—uint32 accepted step for each physical history-ring slot;
- `history_pos.bin` and `history_vel.bin`—sample-major float32 `vec4` records;
- `events.bin`—80-byte GPU event records (`uvec4` metadata plus four `vec4`
  pre-hop source and post-hop survivor state payloads);
- `initial_tracers.bin` and `final_tracers.bin`—selected tracer `vec4` states for
  mass and endpoint checks;
- `analysis.json`—derived measurements and the registered verdict.

The raw arrays and receipt are diagnostic artifacts. They are not copied into a
paper as physical evidence without an independent analysis and an explicit
scope statement.
