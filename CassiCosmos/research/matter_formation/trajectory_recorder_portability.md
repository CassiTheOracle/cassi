# Trajectory recorder portability

The passive trajectory recorder lives in the engine working tree that carries the
particle-initial-condition refactor. This note records what
`trajectory_engine_integration.patch` restores onto the committed engine, what it
cannot restore, and how the analyzer keeps the difference from reaching a verdict.

## What the patch restores

`trajectory_engine_integration.patch` extracts the recorder from the working-tree
engine and inserts it, by anchored insertion, into
`CassiCosmos/scripts/cassi_physics_engine.gd` as committed at `b118a038`. The
patch is additive: 233 lines across 24 blocks, no deletions.

Verified on a fresh worktree at that commit:

| Check | Result |
|---|---|
| GDScript parse (`--check-only --script`) | clean |
| Trajectory-bearing lines vs the working-tree engine | 166 / 166, identical multiset |
| Hook ordering (start, per-step, merge cycle, merge hop) | required statement subsequences match, including every `_barrier(cl)` — asserted by `research/matter_formation/verify_recorder_hooks.py` |
| Sample schedule after the ordering fix | same slots at the same steps (`0, 4096, … , 262144`) and the same tracer IDs as the working tree |
| Shell-mode run, 262144 steps, stride 4096 | receipt written, 65 samples, mass conserved |

The verifier asserts hook order and barriers rather than whole neighborhoods:
surrounding control flow differs between the two engines by design, because the
working tree ends a batch with `if not _step_dispatches(cl): break` where the
committed engine calls the same dispatch directly. The invariant that carries the
recorder is the ordering, and that is what the script checks.

Two ordering details are load-bearing and were caught by that comparison. The
per-step hook runs **after** `_step_dispatches(cl)`, not before it, and each hook
carries its `_barrier(cl)` so the recorder never observes a list that is still
being built. The first ordering error is visible in the receipt: a hook placed
before the step dispatch writes 64 samples where the working tree writes 65,
because the recorder shader derives its slot as `step / stride + 1`.

## What the patch does not restore

The registered experiment is not reproducible from the committed tree. The
working-tree engine resolves the configured initial condition into three nested
shells and reports `IC [Nested shells]: 8192 particles, 1 components,
mass=1000.0000`. At `b118a038` the same configuration falls through to the legacy
uniform cloud and reports `IC [Uniform] ... Particles initialized: 8192
(Σm=7639.9)`. The nested-shell initial condition and the associated arrangement
and motion enumerations are part of the uncommitted refactor.

Consequently a run from the committed engine is a different experiment: measured
initial mass 7639.913070 instead of 1000.000000, and a support radius of 24.999
instead of 27.624. Its receipt is an implementation check of the recorder path,
never probe evidence.

## The fail-closed check

The analyzer now compares the receipt's measured initial mass against the total
mass the harness requested, both of which the receipt carries, and fails a
receipt whose relative error exceeds $10^{-4}$. A committed-engine run fails with
relative error 6.64; the working-tree run agrees to $1.1 \times 10^{-9}$. The
check catches the divergence that exists today: an engine without the registered
geometry builds a different initial condition with a different total mass.

Its scope is the mass, not the shape. It detects the fallback divergence that
exists between these two engines: an engine without the registered geometry
builds a different initial condition and therefore a different total mass. An
engine that honored the requested total mass while resolving a different
geometry would pass this check, and the receipt still records the requested
`initial_condition`, `initial_arrangement`, and `initial_motion` for review. A
gate on the geometry itself needs the engine to report the condition it resolved,
or an invariant that does not move with the analyzer's bin count.

## Where the registered probe belongs

The registered probe belongs with the engine revision that implements its
contract: the revision that resolves the nested-shell geometry and carries the
recorder. This patch exists so the recorder is reviewable and recoverable from
committed history while that revision is prepared, and it holds only the
recorder. Transplanting further engine code by line-range extraction would carry
the same risk this port already surfaced twice — dropped barriers and a moved
hook — without the surrounding refactor that gives those lines their meaning.

Once the engine carrying the recorder is committed, the patch and this note are
obsolete: the recorder is part of `cassi_physics_engine.gd`, and nothing
downstream reads either file.
