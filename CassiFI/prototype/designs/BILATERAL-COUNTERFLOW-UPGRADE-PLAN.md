# Bilateral Counterflow Composition Implementation Roadmap and Results

**Status:** Implemented and measured — 2026-08-31

## Implemented Scope

The explicit bilateral counterflow field now provides a bounded field-owned
composition surface that can:

- recover trajectories across active lengths 2–8;
- use endpoint, partial, noisy, ambiguous, and contradictory constraints;
- preserve alternatives without exhaustive `K^(L-1)` search;
- represent forward and backward transition laws without assuming invertibility;
- consolidate successful trajectories as reusable macro-operators in the field;
- accept exact Mnemic addresses and Thalamus authority as fixed constraints;
- induce shared transition basins from equal observed outcomes;
- settle an entire symbolic trajectory before rendering it;
- plan typed actions without executing them;
- replay exactly from the serialized `QiFieldState.field` state.

The surface is exposed through the live Phi harmonic provider as a derived,
nonpersistent planner. Each request builds its bilateral companion only from
explicit observed transitions and binds the receipt to the selected provider
field hash. It does not overlay the bilateral profile onto the populated Phi
harmonic checkpoint or modify the production field-agent geometry. A persistent
cutover still requires a native shared geometry and a separately measured
migration.

## Implemented State

`cassi_bilateral_counterflow.py` stores learned transition moments, active
trajectories, constraints, thought metadata, and settlement state in one
`QiFieldState.field` tensor.

The six-slot synthetic composition `B → C → A → D → B` settles from two partial
landmarks and a partial goal. Adaptive search evaluates 348 extensions rather
than 1,024 complete plans. The width-1 control evaluates 44 extensions and
settles the same plan through backward-anchor ranking. Exact restart,
inactive-slot zeroing, hidden-value non-leakage, and CPU/ROCm discrete parity
are covered by `tests/test_cassi_bilateral_counterflow.py`.

This surface demonstrates bounded state-owned composition over synthetic
operator families. It does not establish semantic understanding or general
planning.

## Invariants

1. `QiFieldState.field` is the only adaptive persistent state.
2. Learned forward maps, backward maps, macros, supports, and semantic outcome
   equivalence live in field coordinates.
3. Exact address catalogs, action schemas, authority rules, and codecs are fixed
   deterministic boundary data, not learned side state.
4. Planning does not mutate learned basin memory.
5. Outcome consolidation is explicit and occurs only after a closed thought.
6. Inactive slots remain exactly zero.
7. Checkpoints reject incompatible configuration or field layout.
8. Invalid, ambiguous, contradictory, and unauthorized requests fail closed.
9. Typed action planning returns a proposal; it never performs an external action.
10. No model, embedding service, optimizer, replay table, learned reranker, or
    fallback policy participates in the live path.

## Implementation Surface

The implementation reuses the existing field and provider surfaces:

- `cassi_bilateral_counterflow.py` owns field layout, transition learning,
  bidirectional search, adaptive beam behavior, macro memory, and settlement.
- `cassi_counterflow_reasoner.py` owns fixed exact-address encoding, Thalamus
  constraint conversion, symbolic trajectory rendering, and typed action plans.
- `cassi_counterflow_runtime.py` validates observed transitions, derives one
  ephemeral companion, and returns the consolidated plan receipt.
- `cassi_persistent_provider.py` exposes `POST /v1/counterflow/plan`, binds the
  derived receipt to the selected primary field, and verifies that planning did
  not mutate or persist the provider session.
- `run_bilateral_counterflow_scenario.py` exercises the complete path and emits
  measured JSON receipts.
- `tests/test_cassi_bilateral_counterflow.py`,
  `tests/test_cassi_counterflow_reasoner.py`, and
  `tests/test_cassi_counterflow_runtime.py` cover the solver and consolidated
  boundary; `tests/test_cassi_persistent_provider.py` covers the live seam.

No new dependency is required.

## Implemented Solver

### Bidirectional anchor completion

Each constrained slot is an anchor. Candidate trajectories propagate forward
from the preceding anchor and backward from the following anchor. Candidate
cost combines every observed component reached so far with forward/backward
meeting disagreement. Small search spaces are enumerated exactly; larger spaces
use a stable bounded beam.

The backward set is a Cartesian relaxation over the enumerated legal suffixes.
Enumeration is exhaustive up to `bidirectional_lookahead_limit` and
deterministically truncated above it. The API contains no prefix-dependent
suffix constraint, so path labels are unnecessary. The minimum meeting residual
ranks beam prefixes, while accumulated observed-constraint path cost determines
terminal validity.

Recorded telemetry and coverage:

- evaluated extension count;
- surviving path count;
- exact-versus-beam mode;
- forward/backward meeting residual;
- winning plan, runner-up margin, and entropy.

Executable coverage compares tractable cases with exhaustive enumeration,
preserves the unique endpoint-only plan and deterministic tie resolution, and
checks the configured work bound.

### Adaptive beam allocation

Search begins at the configured minimum width and expands deterministically when
the retained path distribution remains ambiguous. The maximum configured width
is a hard bound. No width history persists outside the field.

Recorded telemetry and coverage:

- widths used by depth;
- evaluated extensions;
- result equality with the fixed maximum-width reference;
- expansion reduction on easy cases.

Coverage preserves the fixed-width valid decision, recovers the same plan, and
measures reduced work on the low-ambiguity fixture.

### Ambiguity and abstention

Settlement requires a valid trajectory, constraint residual below tolerance,
adequate plan margin, and sufficiently low normalized beam entropy. Multiple
materially distinct valid plans return `ambiguous`; contradictory or unsupported
constraints return `exhausted`.

Coverage distinguishes multiple valid trajectories as `ambiguous` and closes
null or contradictory fixtures as `exhausted`.

## Transition Law

Each basin stores separate forward and backward sufficient statistics. The
backward map is learned from reversed observations rather than computed as an
exact inverse. Cycle disagreement measures information loss.

This supports rank-deficient and many-to-one transitions while retaining the
existing full-rank invertible cases.

Recorded telemetry and coverage:

- forward residual;
- backward residual;
- cycle residual;
- exact plan on a mixed invertible/noninvertible fixture;
- calibrated abstention when backward information is insufficient.

Coverage accepts rank-deficient observations without manufacturing an inverse
and preserves the established invertible results.

## Field-Resident Abstractions

### Macro-operators

A settled plan can be consolidated into one field basin whose forward and
backward maps are the ordered compositions of its constituent basins. The basin
stores its macro marker, span, and constituent basin IDs in field metadata.
Re-consolidating the same macro reinforces it. A macro can later solve a direct
abstract transition in one edge.

Field-only coverage verifies ordered composition, exact constituent identity,
restart, reinforcement, and transitive invalidation after a required
constituent is removed.

### Outcome-induced equivalence

Different deterministic surface addresses that produce the same observed
transition are deposited through the same basin-learning law. Equivalence is
accepted only when the learned field assigns the same basin and held-out outcome
composition succeeds. Text similarity is not used.

Coverage requires a shared observed transition before equivalence and confirms
that equivalent outcomes merge under the configured residual.

### Compact exact addresses

A fixed codec splits one caller-supplied 16-byte Mnemic address into eight
big-endian unsigned 16-bit words. The words occupy the real and imaginary lanes
of four complex field components as exact multiples of `2^-15` shifted into
`[-1, 1)`. Every 16-bit word is exactly representable in float32 and float64;
the codec never packs 128 bits into one floating-point scalar.

Decoding rejects nonfinite lanes, negative zero, off-grid values, out-of-range
words, and malformed byte lengths. Coverage includes arbitrary 128-bit values,
all-zero and all-one addresses, dtype parity, restart, and distinct addresses for
revision changes. Mnemic allocates and collision-checks the exact 16-byte address;
the adapter never truncates a hash. The field learns relationships involving the
address; the codec learns nothing.

Coverage confirms exact round trips, dtype-independent decoding, invalid-lane
rejection, collision and truncation checks, and restart-stable addresses.

## Mnemic and Thalamus Boundary

`cassi_counterflow_reasoner.py` accepts exact candidates containing:

- a collision-checked 16-byte Mnemic address;
- record revision and exact byte span metadata;
- a latent constraint value;
- a per-component observation mask;
- Thalamus authority, requirement, and semantic kind.

Required candidates become hard constraints. Optional candidates become bounded
soft masks scaled only by deterministic authority. Ineligible candidates never
enter the field. Conflicting required candidates fail before planning.

The adapter contains no relevance model and stores no adaptive candidate state.

The live `DerivedCounterflowRuntime` does not accept a caller-supplied latent
constraint value. It deterministically encodes each exact Mnemic address into
four complex field components and learns only the supplied before/after address
transitions. This prevents temporal coordinates, action kinds, or host heuristics
from becoming invented field laws.

## Whole-Trajectory Symbolic Generation

Generation is constraint completion, not next-symbol sampling:

1. clamp known exact addresses and required latent values;
2. leave unknown slots unresolved;
3. run bilateral continuous relaxation and discrete adaptive search;
4. require settlement or return ambiguity/exhaustion;
5. render the settled basin sequence through the supplied fixed symbol catalog.

A generated symbol is therefore downstream of a settled field trajectory. No
language model, tokenizer probability, or host continuation table participates.

## Typed Action Planning

A fixed action catalog maps eligible basin IDs to typed action descriptors with
kind, authority requirement, reversibility, and declared precondition/effect
addresses. The field selects a trajectory; the boundary validates every selected
action against Thalamus eligibility and returns a read-only proposal.

No tool is executed. Consequential execution remains outside this measurement
surface and requires the existing explicit authorization path.

Coverage rejects ineligible and untyped actions, disconnected precondition
chains, and every path that would perform an external side effect.

## Measured Coverage

| Area | Executable evidence | Covered behavior |
|---|---|---|
| Held-out starts | exact plans over independent starts | result does not depend on the original start vector |
| Held-out operator families | exact plans over separately trained families | behavior extends beyond the original four matrices |
| Length 2–8 | exact plan, inactive zeros, bounded work | supported lengths close with inactive state exactly zero |
| Endpoint-only | exact plans without landmarks | future-anchor ranking retains the correct prefix |
| Noisy constraints | accuracy and residual by noise level | small bounded noise retains the calibrated plan |
| Ambiguous constraints | `ambiguous` plus multiple survivors | no arbitrary unique settlement |
| Contradictory/null | exhaustion and residual separation | no false settlement |
| Noninvertible transitions | forward accuracy and cycle residual | rank deficiency is accepted and information loss remains visible |
| Adaptive beam | work versus fixed-width reference | same valid result with easy-case work savings |
| ROCm | discrete parity and wall time by `K,L,W` | device-independent discrete plan and finite field |
| Restart | exact next step and serialized bytes | exact replay |
| Field counterfactual | changed basin memory changes plan | committed result causally depends on the learned field |

## Performance

Profiling measured actual wall time before the implementation changed. The
largest component, repeated per-scale operator completion, was vectorized.
Candidate construction, sorting, host/device synchronization, field cloning,
validation, and serialization were measured separately where possible.

The retained optimization preserves discrete decisions, restart, and field
invariants while producing the repeatable wall-time reduction recorded below.

## Present State

The current implementation has:

1. a complete integrated scenario that exits successfully and emits all receipts;
2. executable coverage for every area in the measured-coverage table;
3. exact CPU restart;
4. ROCm discrete parity with bounded numeric tolerance;
5. unchanged trained basin memory during inference;
6. a field-only counterfactual that changes a committed symbolic or typed-action
   plan;
7. a passing maintained CassiFI suite;
8. recorded measurements bounded to the synthetic composition surface rather
   than a general cognition claim;
9. a live provider endpoint that derives its companion from explicit observations
   and leaves the selected primary field unchanged; and
10. advisory `no_transition_data` behavior when no transition evidence exists.

## Built and Measured

### Delivered surface

- `cassi_bilateral_counterflow.py` now owns two-to-eight-slot thoughts,
  bidirectional anchor completion, adaptive beam allocation, calibrated
  ambiguity/exhaustion, independently learned forward and backward moment
  laws, field-resident macros with generation tombstones, and policy-frozen
  eligible basin subsets.
- `cassi_counterflow_reasoner.py` supplies the exact 128-bit Mnemic address
  codec, Mnemic/Thalamus constraint translation, whole-trajectory symbolic
  rendering, outcome-induced equivalence consolidation, and inert typed-action
  proposals.
- `cassi_counterflow_runtime.py` supplies the strict observed-transition request
  boundary, nonpersistent companion lifecycle, primary-field hash binding,
  symbolic/action consolidation, and ephemeral macro receipt.
- `cassi_persistent_provider.py` serves that path at
  `POST /v1/counterflow/plan` without writing a session checkpoint.
- `run_bilateral_counterflow_scenario.py` exercises training, refinement,
  ablations, adaptive search, macro consolidation, consolidated runtime
  settlement, the no-transition advisory, typed-action planning, and
  required-basin invalidation.
- The established strict residual tolerances remain unchanged:
  `action_residual_tolerance = 0.16` and
  `constraint_tolerance = 0.12`. No projection law or learned side state was
  added.

### Search and settlement result

The integrated six-slot thought settled in 16 refinement steps on the unique
expected basin path `(1, 2, 0, 3, 1)`. Adaptive search evaluated 348 extensions
instead of 1,024 complete plans, using widths `(4, 16, 64, 2, 8)`. The final
best-plan residual was `0.004399119184560205`, the valid-plan count was one,
and the normalized beam entropy was `1.57840981308439e-05`. The learned basin
region hash remained unchanged throughout inference.

The same settled path consolidated as macro basin 4 and then solved the direct
two-slot thought as plan `(4,)`. Symbolic rendering produced
`op-1 op-2 op-0 op-3 op-1` only after settlement. The corresponding typed
action proposal remained inert. Clearing required constituent basin 1
transitively invalidated the macro and changed the required-basin control to
`exhausted`.

Ambiguous partial constraints close as `ambiguous`; contradictory, null, and
unsupported constraints close as `exhausted`. Rank-deficient observations are
accepted without inventing an inverse, while their backward/cycle uncertainty
remains visible in telemetry.

### CPU and ROCm wall time

Timings below are synchronized medians after two warmups, with five CPU
repetitions and three ROCm repetitions. `K` is the eligible basin count, `L`
is the active slot count, and `W` is the actual adaptive survivor width at
each search depth. Values are milliseconds for one `refine_once` call.

| K | L | W | Extensions | CPU before → after | ROCm before → after |
|---:|---:|---|---:|---:|---:|
| 2 | 2 | `2` | 2 | 5.733 → 4.780 | 33.154 → 29.397 |
| 2 | 4 | `2,4,8` | 14 | 12.022 → 7.002 | 45.065 → 28.287 |
| 2 | 6 | `2,4,8,16,16` | 62 | 16.769 → 6.773 | 54.826 → 36.863 |
| 2 | 8 | `2,4,8,16,32,64,16` | 254 | 19.300 → 9.372 | 64.928 → 41.526 |
| 4 | 2 | `4` | 4 | 7.565 → 6.266 | 31.455 → 33.330 |
| 4 | 4 | `4,16,16` | 84 | 12.681 → 7.080 | 47.132 → 34.841 |
| 4 | 6 | `4,16,64,16,16` | 404 | 15.997 → 8.113 | 54.635 → 39.136 |
| 4 | 8 | `4,16,64,16,16,16,16` | 532 | 21.497 → 10.780 | 67.922 → 43.551 |
| 8 | 2 | `8` | 8 | 6.932 → 7.186 | 37.059 → 35.531 |
| 8 | 4 | `8,64,16` | 584 | 13.860 → 8.518 | 50.749 → 40.398 |
| 8 | 6 | `8,64,16,16,16` | 840 | 19.303 → 11.448 | 59.973 → 43.994 |
| 8 | 8 | `8,64,16,16,16,16,16` | 1,096 | 54.493 → 43.706 | 70.557 → 47.234 |

For the complete representative 16-step thought, CPU median latency fell from
204.930 ms to 113.843 ms, a 44.4% reduction. ROCm median latency fell from
860.579 ms to 571.721 ms, a 33.6% reduction. ROCm is slower at these small
tensor sizes because the implementation intentionally performs host-visible
validation and decision checks; it retains the same discrete plan and bounded
numeric parity.

The measured hotspot was `_operator_completion`: the profiled representative
run called it 224 times for 0.138 s cumulative. Batching all seven scale
trajectories reduced that to 32 calls and 0.009 s cumulative. Profiled
`refine_once` time fell from 0.250 s to 0.127 s. Checkpoint serialization was
not the hotspot: the 139,886-byte state measured 1.032 ms to dump and 1.374 ms
to load on CPU.

### Verification receipts

- Integrated scenario: exit 0; settled expected plan; all training,
  refinement, control, macro, consolidated-runtime, no-transition, action, and
  invalidation receipts emitted.
- Solver coverage after optimization: `27 passed`, including CPU/ROCm
  discrete parity, restart, field counterfactuals, active lengths 2–8,
  held-out starts, multiple operator families, noisy/ambiguous/null
  constraints, noninvertible laws, adaptive-beam equivalence, and macro
  invalidation.
- Integrated boundary coverage: `7 passed` for exact address behavior,
  Mnemic/Thalamus constraints, eligibility, semantic equivalence, symbolic
  settlement, and inert typed actions.
- Consolidated runtime and provider coverage: `18 passed`, including strict
  exact-address inputs, authority rejection, ephemeral macro behavior,
  transport-key filtering, primary-field identity, and absence of a persisted
  planner checkpoint.
- Live HTTP smoke: `POST /v1/counterflow/plan` returned HTTP 200 with
  `settled`, symbol `advance`, inert action `advance-field`, the selected primary
  field hash, and frozen inference memory. Nonfinite internal first-observation
  residuals are rendered as JSON `null`.
- Maintained CassiFI suite: `429 passed, 2 xfailed, 150 subtests passed` in
  432.97 seconds on the final code tree.

These measurements establish the bounded synthetic composition surface
described in this plan. They do not establish general semantic understanding,
open-domain language generation, autonomous action execution, or a production
CassiCore cutover.
