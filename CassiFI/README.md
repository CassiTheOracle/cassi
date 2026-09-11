# CassiFI

CassiFI develops field-owned intelligence: adaptive memory, inference,
deliberation, action, and learning remain explicit parts of persistent field
state. The canonical paths do not use a language model or a parallel learned
sidecar as a fallback.

## Active implementation

The canonical runtime uses a CPU/float64 resonant field, with a separately
identified GPU arithmetic path. This repository root contains:

| Path | Role |
|---|---|
| [`FIELD-INTELLIGENCE-DESIGN.md`](FIELD-INTELLIGENCE-DESIGN.md) | Mathematical and systems specification |
| [`cassi_field_atlas.py`](cassi_field_atlas.py) | Typed field atlas, evidence support, updates, inference, programs, and source retraction |
| [`cassi_field_cognition.py`](cassi_field_cognition.py) | Decision certificates, inquiry, structure selection, constructions, explanations, and plan repair |
| [`cassi_field_owner.py`](cassi_field_owner.py) | Single-owner persistence, immutable checkpoints, journals, authority, capacity, and exactly-once effects |
| [`cassi_variational_field.py`](cassi_variational_field.py) | Learned variational relation primitive and standalone numerical reference |
| [`cassi_resonant_field.py`](cassi_resonant_field.py) | Seven spatially resolved pools, two-strand transport, bounded heartbeat, breathing, numerical integration, dynamic reduction, energy-bounded temporal impulses, and read-only phase-space probe scoring |
| [`cassi_field_transceiver.py`](cassi_field_transceiver.py) | Field-derived temporal input/output realizations, compact linear execution, full nonlinear execution, and propagated error bounds |
| [`cassi_temporal_field.py`](cassi_temporal_field.py) | Bounded categorical predictive-state induction, carried temporal memory, prospective skill registration, evidence-triggered policy formation, safe-rank and admitted-episode pool projections, and multi-skill action records |
| [`cassi_temporal_inquiry.py`](cassi_temporal_inquiry.py) | Bounded observation-contingent inquiry over field-derived candidate states and supported outcomes |
| [`cassi_clause_field.py`](cassi_clause_field.py) | Uniform polynomial-space CNF, assignment trail, decision stack, unit propagation, resolution-derived conflict learning, proof-work counters, and chronological backtracking in one immutable nine-plane field tensor |
| [`runtime/cassi_cassipi_worker.py`](runtime/cassi_cassipi_worker.py) | Serialized owner operations, optional real-time scheduling, migration, and private HTTP transport |
| [`runtime/cassi_resonant_view.py`](runtime/cassi_resonant_view.py) | Read-only canonical field viewer and frozen-body response calibration |
| [`run_field_intelligence_scenario.py`](run_field_intelligence_scenario.py) | Controlled-world learning, recall, planning, action, restart, and forgetting scenario |
| [`run_variational_field_scenario.py`](run_variational_field_scenario.py) | Numerical learning, inference, revision, intervention, and restart scenario |
| [`run_resonant_field_scenario.py`](run_resonant_field_scenario.py) | Production owner, phase-learning controls, energy accounting, reduction, and CPU/GPU scenarios |
| [`run_field_transceiver_scenario.py`](run_field_transceiver_scenario.py) | Temporal transfer, compact/full comparison, sustained held-out learning, composition, revision, retention, restart, and revocation scenarios |
| [`run_temporal_field_scenario.py`](run_temporal_field_scenario.py) | Current-observation temporal learning, contextual distinctions, closed-loop skills, memory interventions, durable restart, and source revocation |
| [`run_temporal_learning_scenario.py`](run_temporal_learning_scenario.py) | Matched guided-use acquisition, retention, new-participant reuse, one-shot oracle, and frozen-memory counterfactual |
| [`run_autonomous_temporal_learning_scenario.py`](run_autonomous_temporal_learning_scenario.py) | Field-selected acquisition, episode-boundary retention, matched causal counterfactual, transfer, replay oracle, and frozen-memory control |
| [`run_autonomous_skill_formation_scenario.py`](run_autonomous_skill_formation_scenario.py) | Goal-only field-selected discovery, automatic prospective-skill formation, bounded seven-pool coupling, matched field controls, fresh-participant transfer, and exact restart reuse |
| [`verify_autonomous_skill_formation.py`](verify_autonomous_skill_formation.py) | Standard-library reconstruction of the skill-formation evidence, persisted wave page, work balance, propagation, and controls |
| [`run_online_resonant_learning_scenario.py`](run_online_resonant_learning_scenario.py) | Matched online-outcome learning, held-wave causal control, resonant action crossover, held-out execution, and exact restart |
| [`verify_online_resonant_learning.py`](verify_online_resonant_learning.py) | Production-independent reconstruction of retained sources, checkpoint lineage, raw resonant pages, candidate scores, causal comparisons, behavior traces, and restart |
| [`run_p_vs_np_clause_field_probe.py`](run_p_vs_np_clause_field_probe.py) | Exact three-variable corpus, structured SAT/UNSAT families, proof-carrying decisions, representation controls, resource ledger, and frozen receipt |
| [`verify_p_vs_np_clause_field_probe.py`](verify_p_vs_np_clause_field_probe.py) | Independent standard-library reconstruction of CNFs, truth-table decisions, SAT certificates, UNSAT resolution refutations, learned-clause soundness, storage bounds, proof/search scaling, and aggregates |
| [`cassi_hybrid_inference.py`](cassi_hybrid_inference.py) | Field-owned CNF proof state with cutting-plane arithmetic, GF(2) parity elimination, exact-cardinality bridges, acyclic named extensions, resolution, and fail-closed resource bounds |
| [`run_p_vs_np_hybrid_inference.py`](run_p_vs_np_hybrid_inference.py) | Counting, parity, connected matched exact-one, crossed-system, extension, satisfiable, incomplete-premise, representation, persistence, determinism, and scaling scenarios |
| [`verify_hybrid_inference.py`](verify_hybrid_inference.py) | Independent standard-library reconstruction of every serialized hybrid proof inference, syntax-only restricted-class recognition, exact bound checks, and receipt aggregates |
| [`cassi_mixed_exact_one_field.py`](cassi_mixed_exact_one_field.py) | Immutable field-owned total decision by constant-width dynamic programming for the canonical cycle-plus-adjacent-pair matched exact-one/parity class |
| [`run_mixed_exact_one_decision.py`](run_mixed_exact_one_decision.py) | Exhaustive small-label and linear-scaling SAT/UNSAT decisions, assignments, DP certificates, persistence, determinism, and exact resource receipts |
| [`verify_mixed_exact_one_decision.py`](verify_mixed_exact_one_decision.py) | Independent standard-library reconstruction of the canonical CNF, complete dynamic program, persisted tensor, certificates, truth-table controls, and aggregate evidence |
| [`cassi_general_matched_field.py`](cassi_general_matched_field.py) | Immutable field-owned total decision for every syntax-recognized connected matched exact-one/parity topology via deterministic Edmonds blossom search |
| [`run_general_matched_decision.py`](run_general_matched_decision.py) | Exhaustive edge-label, topology-diversity, scaling, persistence, public-step, and fail-closed matching scenarios |
| [`verify_general_matched_decision.py`](verify_general_matched_decision.py) | Independent standard-library reconstruction of source incidence, auxiliary graphs, perfect matchings, Tutte barriers, assignments, persisted tensors, digests, and aggregates |
| [`cassi_alias_exact_one_field.py`](cassi_alias_exact_one_field.py) | Immutable field-owned total decision for degree-two/degree-three monotone exact-one CNFs by branching on cubic variables and solving every residual by deterministic perfect matching |
| [`run_alias_exact_one_decision.py`](run_alias_exact_one_decision.py) | Exhaustive small truth tables, mixed-incidence stress, scaling, persistence, public-step replay, and fail-closed alias-boundary scenarios |
| [`verify_alias_exact_one_decision.py`](verify_alias_exact_one_decision.py) | Independent standard-library reconstruction of every cubic branch, matching or Tutte witness, SAT assignment, persisted tensor, digest, and receipt aggregate |
| [`run_alias_compression_analysis.py`](run_alias_compression_analysis.py) | Deterministic exact-cover state comparison, recurrence crossover accounting, and uniform-basis matchgate parity elimination for the alias boundary |
| [`verify_alias_compression_analysis.py`](verify_alias_compression_analysis.py) | Independent reconstruction of all cover searches, exhaustive small formulas, recurrence constants, receipt binding, and eight Gröbner ideal eliminations |
| [`cubic_kernel_decision.py`](cubic_kernel_decision.py) | Exact rational incidence-kernel analysis for cubic monotone one-in-three SAT, with rank/cardinality filters, caller-supplied basis coordinates, a bounded-support 2-SAT reduction, exact basis-width diagnostics, and an exact kernel-enumeration fallback |
| [`run_cubic_kernel_analysis.py`](run_cubic_kernel_analysis.py) | Cubic source cases, rank and alphabet obstructions, canonical and invariant support-three boundaries, exact basis censuses, connected linear-nullity families, certificates, and relation closures |
| [`verify_cubic_kernel_analysis.py`](verify_cubic_kernel_analysis.py) | Independent rational elimination, exhaustive basis-width reconstruction, kernel and 2-SAT certificate checking, relation closures, fixed-gauge formulas, and receipt verification |
| [`growing_nullity_schaefer_probe.py`](growing_nullity_schaefer_probe.py) | Exact direct-sum and connected-bridge census of growing-nullity cubic bases, pivot width, and arity-at-most-three Schaefer closures |
| [`verify_growing_nullity_schaefer_probe.py`](verify_growing_nullity_schaefer_probe.py) | Independent reconstruction of the growing-nullity formulas, rational basis censuses, product laws, connected bridge, and Schaefer relation profile |
| [`run_mixed_schaefer_frame_obstruction.py`](run_mixed_schaefer_frame_obstruction.py) | Exact mixed SAT+UNSAT direct-sum census with all 32,232 bases, the 1,620 connected cross-component 2-switches, canonical widths, an exhaustive bound-two width screen, and an exact width-three witness for every switch |
| [`verify_mixed_schaefer_frame_obstruction.py`](verify_mixed_schaefer_frame_obstruction.py) | Independent reconstruction of both component censuses, the mixed basis product, both switch screens and canonical widths, exact witness remeasurement, and full-enumeration brute-force controls at both bounds |
| [`run_yang_mills_gauge_fibre_probe.py`](run_yang_mills_gauge_fibre_probe.py) | Field-owned exact $SU(2)$ Gauss-constraint search for a fixed-boundary refined plaquette, with tensor-product multiplicity and cutoff controls |

Run the implemented paths from this directory:

```powershell
python run_field_intelligence_scenario.py --horizon-episodes 24
python -m unittest -v test_field_intelligence.py
python run_variational_field_scenario.py --output _diag/variational-field-math/scenario.json
python -m pytest test_variational_field.py -q
```

The scenarios are controlled reference environments. They do not establish
open-domain language acquisition, calibrated probability, causal
identifiability, GPU superiority, physical energy savings, or live
CassiCosmos operation.

## Resonant runtime

[`FIELD-INTELLIGENCE-DESIGN.md`, §26](FIELD-INTELLIGENCE-DESIGN.md#26-seven-pool-resonant-field-upgrade)
describes the implemented seven-pool body: four paired spatial ports per pool
in the default profile, directional two-strand exchange, a work-bounded
heartbeat, activity-modulated breathing, and persisted working phase/momentum.
Learned relations and provisional wave state share one canonical `AtlasState`.
An inference advance changes the working state and generation while preserving
learned chart bytes and evidence time.

`think` prepares and advances a bounded query; `query(query_id=...)` and
`explain_query(query_id=...)` read its persisted result. Action proposals freeze
the relevant readout and dependencies so unrelated heartbeats do not cancel
them. Source corrections still invalidate affected results and working state.

Exercise the live implementation and the separate mathematical reference:

```powershell
python run_resonant_field_design_math.py --output _diag/resonant-field-design/math.json
python run_resonant_field_scenario.py --output _diag/resonant-field-production/scenario.json
python -m pytest test_field_intelligence.py test_variational_field.py test_resonant_owner.py test_field_transceiver.py runtime/test_cassipi_worker.py runtime/test_cassipi_import.py runtime/test_cassipi_forget_generation.py runtime/test_cassipi_runtime_package.py -q
```

The production scenario measures seven localized transfer responses,
phase-conditioned held-out prediction, restart/revocation/effect behavior,
resolution error, and GPU agreement. These are controlled numerical and runtime
results. They establish neither biological chakras or consciousness nor a
seven-pool advantage over the comparison layouts. GPU correctness is measured;
a GPU speed or energy advantage is not established. Detailed measurements and
their limits are in [§26.24](FIELD-INTELLIGENCE-DESIGN.md#2624-implemented-runtime-and-measured-boundaries).

Build a private runtime into an unused output directory:

```powershell
python runtime/build_cassipi_runtime.py --output _diag/cassipi-resonant-runtime
python runtime/build_cassipi_runtime.py --output _diag/cassipi-resonant-runtime --verify-only
python -I _diag/cassipi-resonant-runtime/cassi_cassipi_worker.py --data-home _diag/resonant-owner
```

Logical mode advances only requested work. `--realtime` enables a bounded
0.25-second scheduler; achieved cadence and backlog are reported in the runtime
descriptor. A pause preserves the last committed wave. The last attached
client's detach stops the worker unless `--keep-alive` was explicitly supplied.
Shutdown joins the current bounded work and releases the owner lock.

An unmigrated v1 store is rejected by normal startup. With the owner stopped,
run the explicit `--migrate-v1` command against that store's `--data-home` before
starting the v2 owner. Migration validates the old head, source bytes, and
revocation fence; it preserves learned memory and starts an empty wave.

The worker serves `/view` and `/v1/view/snapshot` on its private loopback
endpoint. The viewer requires the worker's bearer authentication and exchanges
it for a read-only, HttpOnly, same-site cookie. Keep the runtime descriptor and
bearer secret private. Displayed colors come from a declared frozen-rest
transfer measurement; instantaneous local quadrature rates and spatial
pair-phase coherence are labeled separately. Filters, rendering, and bounded
snapshot polling do not advance the field or admit observations.

## Knowledge-bearing field transceivers

[§27 of the design](FIELD-INTELLIGENCE-DESIGN.md#27-knowledge-bearing-field-transceivers)
describes implemented condensation of supported relation charts into reusable
temporal input/output structures. Each retains its own working phase, explicit
ports, context, parent-chart versions, and source dependencies inside the same
canonical atlas. Derived numerical operators are not a second learned model.

`condense_transceiver` creates a realization; `advance_transceivers` supplies
bounded inputs and advances an assembly; `reset_transceiver` restarts its temporal
episode; `inspect_transceivers` reads without advancing. Connected outputs arrive
on the next local tick, carrying their uncertainty. These readouts are temporal
predictions, not newly observed evidence or permission to act.

The linear path can evolve fewer coordinates using a per-step residual bound.
It expands before a step that would exceed the allowance or declared compact
horizon. Nonlinear responses use the full canonical wave operator. Source or
parent changes remove affected derived realizations; old operation results cannot
be replayed across the checkpoint revocation fence.
On an ordinary retry, the owner recomputes the complete transceiver successor
and semantic receipt from its authenticated predecessor. Only measured elapsed
times are excluded; any other receipt or state disagreement is checkpoint
corruption rather than a reusable result.

```powershell
python run_field_transceiver_scenario.py --output _diag/field-transceivers/scenario.json
python run_field_transceiver_scenario.py --curriculum --seeds 101 202 303 --output _diag/field-curriculum/replay/report.json --data-home _diag/field-curriculum/replay/owners
python -m pytest test_field_transceiver.py -q
```

The controlled linear scenario uses 16 evolving coordinates instead of 112,
matches the full 32-step response within `3.56e-15`, and makes zero full
wave-operator applications during those steps. This measures temporal numerical
compression of a learned instrument relation. It does not establish nonlinear
compression, autonomous discovery of transceivers, biological neurons, general
reasoning, or an end-to-end scaling advantage.

The sustained curriculum requires an unused `--data-home`; it preserves each
trained owner and refuses to overwrite an existing one. It compares trained full
execution, trained transceivers, and a separately labeled unsupported numerical
prior against externally generated targets. Production condensation of an
untrained chart is refused.

The retained three-seed run admits 336 observations per owner. Pooled held-out
instrument RMSE falls from `1.95717` for the prior to `0.01619`; connected
composition reaches `0.02565` without observations of the new pairs. Raw one-tick
temporal prediction improves modestly, while supplied-history prediction is much
more accurate. The retained curriculum's compact closed-loop rollout returns only
half of the final predictions. The current uncertainty transport is evaluated
separately in the temporal-development comparison below.
These are distinct learning, temporal-representation, and numerical-certification
results. [§27.6](FIELD-INTELLIGENCE-DESIGN.md#276-sustained-held-out-learning-curriculum)
records the measurements, revision and retention behavior, full cost accounting,
and limits on scaling claims.

## Learned temporal memory and reusable skills

The categorical temporal path learns predictive states from ordered
`(action, observation)` episodes. At inference, the owner consumes only the
current event and carries numeric working state; it does not receive hidden
world state, supplied lag columns, or a remembered-history label. Compatible
observed continuations can share a state. Conflicting shared outcomes remain
distinct; stochastic continuations use evidence-based comparison rather than
requiring identical sample proportions.

An episode grows through a strict source-revision chain. Admission replaces its
earlier prefix instead of counting those observations again. Missing action
evidence carries an unknown successor and marks the working history uncovered;
it cannot eliminate an alternative or certify a prediction. Subsequent actual
observations continue narrowing the field's candidate states. Uncertainty
clears only when fully supported evidence leaves one candidate, never because
time passed or a reset selected the root. Admission can replay the same retained
history against newly learned relations.

Skill condensation stores a goal-directed policy in numeric field lanes.
Each proposed action is re-evaluated after its actual outcome, and completion
requires consumption of the goal observation. Participants share learned
relations but carry separate numeric histories and candidate states. Admission
replays those histories against the revised memory and recomputes existing
skill policies. After a support gap, a skill action also requires an action-
coverage certificate shared by every original prefix in the induced state;
pooled exposure from one context is insufficient. An already-issued task
proposal survives admission and restart. Its actual acknowledgment is consumed
once, and resetting its participant while the effect is outstanding is refused.
A proposal grants no permission to execute an external action.
If execution is durably journaled but the owner stops before admitting its
acknowledgment, retry resolves and admits that exact acknowledgment without
executing the effect or consuming authority a second time.

```powershell
python run_temporal_field_scenario.py --seeds 101 202 303 --output _diag/temporal-development/replay/report.json --data-home _diag/temporal-development/replay/owners
python -m pytest test_temporal_field.py -q
```

The data-home directory must be unused. This is bounded categorical
predictive-state induction, distinct from the continuous resonant dynamics.
The scenario supplies the vocabulary, training interventions, goals, and
forbidden outcomes. The owner rebuilds the temporal field from its active exact
source episodes on admission; inference does not replay that corpus.
Across three seeds, the controlled scenario answers all 81 final held-out
predictions correctly, compared with 63/81 for a current-observation-only
diagnostic, and completes all 12 observation-driven skill runs without a
forbidden outcome. Each seed preserves carried-state behavior over 4,096
numeric continuation steps. These are controlled-world results, not evidence
of open-vocabulary learning or broad autonomous skill acquisition.
[§28](FIELD-INTELLIGENCE-DESIGN.md#28-learned-temporal-state-and-observation-driven-skills)
describes the implementation, measured behavior, compact-feedback comparison,
and persistence costs.

### Active learning comparison

The inquiry selector derives alternatives from the learned temporal field and
searches bounded observation-contingent sequences. A carried support gap cannot
be declared resolved by the remaining known candidates alone. A supported
sequence may instead recover context when every branch reaches one universally
covered skill decision at a strictly lower field-derived remaining-step rank,
or when an actual observation distinguishes one candidate. This monotonic-rank
condition prevents a supported cycle from masquerading as restored progress.
If no such sequence is available, acquisition ranks permitted actions by field
support and outcome coverage rather than a fixed probe order. Every recovery
action remains `acquiring`, with the decision unresolved until its real outcome
is consumed. Only an explicitly authorized, feasible operation with
`acquisition_allowed=True` may acquire another observation; represented
forbidden outcomes still block it. Task composition binds one learned skill to
distinct participants, so one participant's acknowledgment cannot satisfy
another participant's goal.

```powershell
python run_temporal_learning_scenario.py --seeds 101 202 303 --budget 32 --output _diag/temporal-learning-corrected/completed/report.json --data-home _diag/temporal-learning-corrected/completed/owners
python verify_temporal_learning_scenario.py --report _diag/temporal-learning-corrected/completed/report.json --data-home _diag/temporal-learning-corrected/completed/owners --source run_temporal_learning_scenario.py --output _diag/temporal-learning-corrected/completed/verification.json
python -m pytest test_temporal_field.py test_temporal_inquiry.py test_temporal_tasks.py -q
```

The matched benchmark begins with six complete normal-mechanism episodes but no
jammed-mechanism trajectory. Each arm then receives three actual guided uses of
the same twelve-action jammed sequence. The online arm admits each growing
prefix after its real observation, the one-shot oracle admits only each
complete episode, and the frozen arm admits none. Transfer scoring uses fresh
participant identities, one jammed/jammed task and one jammed/normal task per
seed, with all admission disabled.

Across seeds 101, 202, and 303, online learning and the one-shot oracle each
complete 6/6 transfer tasks; frozen memory completes 0/6. Both learning arms
move from 36 to 43 induced states and finish with the same numeric learned-field
SHA-256 in every seed. Frozen memory remains at its initial 36-state digest.
Online learning makes 108 prefix revisions to nine retained source heads; the
oracle makes nine complete-episode revisions to the same number of heads.

Online and oracle scoring each consume 135 environment interactions, answer
75/123 predictions, get all 75 answered predictions correct, recover 12
participant contexts, and execute 36 supported recovery steps. Frozen scoring
consumes 204 interactions, answers 12/192 predictions, gets 6 correct, recovers
six contexts, and executes six recovery steps. No arm reaches a represented
forbidden simulator outcome. Learned memory is byte-stable throughout transfer
scoring, and an unrelated reference memory remains exact.

The independent standard-library verifier imports no CassiFI runtime module. It
replays all nine simulator runs, reconstructs guided and transfer observations,
checks incremental/oracle field equivalence and the frozen counterfactual,
walks 1,302 durable checkpoint manifests and their object hashes, validates
source-revision chains and blobs, and confirms exact restart identity and zero
live-model calls. The focused temporal regression suite passes 52 tests.

Complete arm times total 217.47 seconds for online learning, 179.99 seconds for
the oracle, and 147.42 seconds for frozen memory. The fixed temporal field is
3,234,816 bytes per owner. Active checkpoint closures are 4,350,789,
4,350,737, and 4,348,255 bytes per online, oracle, and frozen owner,
respectively; retained data homes are 469,882,713, 326,323,557, and
330,460,284 bytes per owner. These are end-to-end scenario costs on the shared
workstation, not isolated kernel benchmarks.

This establishes causal same-session learning, exact retention, and
new-participant reuse for the deliberately withheld relationship in this
closed-vocabulary simulator. The three seeds vary bootstrap ordering; they are
not independent physical environments. The benchmark supplies goals, safe
guided actions, mechanism vocabulary, and a reusable skill; every growing
prefix reaches a complete guided episode. Arbitrary abandoned or censored
streams remain outside this result. It does not
establish autonomous action discovery, broad order generalization, calibrated
uncertainty, or safety against unrepresented outcomes.
[§28.7–28.8](FIELD-INTELLIGENCE-DESIGN.md#287-inquiry-and-participant-bound-composition)
describe the mechanisms, full measurements, evidence checks, and limits.

### Field-selected acquisition comparison

The next controlled comparison relaxes guidance while retaining the supplied
action and observation vocabulary, goal, reusable skill, and explicit
acquisition permissions. Each arm starts with the same six normal-mechanism
episodes and no jammed-mechanism trajectory. After one supplied current
observation, the online arm selects every subsequent action through the
temporal inquiry and skill paths. Its authorized acquisition surface contains
`probe`, `read`, `inspect`, `idle`, `clear`, and `wait`; the scenario supplies
no acquisition sequence, demonstrated next action, predicted label, or hidden
mechanism state.

```powershell
python run_autonomous_temporal_learning_scenario.py --seeds 101 202 303 --budget 32 --output _diag/temporal-autonomous-learning/completed/report.json --data-home _diag/temporal-autonomous-learning/completed/owners
python verify_temporal_learning_scenario.py --report _diag/temporal-autonomous-learning/completed/report.json --data-home _diag/temporal-autonomous-learning/completed/owners --source run_autonomous_temporal_learning_scenario.py --output _diag/temporal-autonomous-learning/completed/verification.json
python -m pytest test_temporal_field.py test_temporal_inquiry.py test_temporal_tasks.py -q
```

The first field-selected acquisition segment remains unresolved at the
32-decision bound and is admitted once at that explicit segment endpoint. A
matched fresh-participant counterfactual is then run immediately. Online
learning and the replay oracle complete all 3/3 matched counterfactuals in 10
interactions each; frozen memory remains unresolved in all 3/3 and exhausts 34
interactions each. The two subsequent online acquisition segments complete
without guidance. For causal comparison, oracle and frozen arms replay the
online field's exact actions and observations; the oracle admits each bounded
segment and frozen memory admits none.

Transfer scoring then uses fresh participant identities, one jammed/jammed
task and one jammed/normal task per seed, with admission disabled. Online and
oracle fields complete 6/6 transfer tasks in 108 interactions; frozen memory
completes 0/6 in 204. Each learned arm answers 48/96 transfer predictions and
all 48 answered predictions are correct. Frozen memory answers 12/192 and gets
six correct. No arm reaches a represented forbidden outcome. Learned memory is
byte-stable during scoring, and unrelated retained memory remains exact.

Every arm starts from the same 36-state learned numeric digest. Online and
oracle acquisition each induce 39 states, retain nine bounded-segment source
revisions across nine heads, and finish at the same numeric learned-field
SHA-256:
`e4ef3b023b732d4ff810b88e158df0d57c2b2293005f5c23ef5fbf4532501e42`.
Frozen memory retains the initial digest
`d2ab20f5e3e1a9cd5b03043b35a4ac09f586a67c8ea084ae54f412f5ebfb4f94`
and no autonomous source heads.

The independent verifier reconstructs all nine simulator runs and every
field-selected or replayed observation, confirms that online records reproduce
their admitted segments, checks the permitted acquisition surface, verifies
the matched counterfactual and transfer outcomes, reconstructs field payload
hashes and source blobs, and walks 1,467 durable checkpoint manifests. It
reports `PASS`, exact restart identity, and zero live-model calls. The focused
temporal regression suite passes 52 tests in 83.53 seconds.

Complete arm timers total 200.35 seconds for online learning, 161.83 seconds
for the replay oracle, and 215.67 seconds for frozen memory. With eight bound
participants, the fixed temporal field is 4,852,224 bytes per owner. Active
checkpoint closures are 6,557,532, 6,553,818, and 6,552,152 bytes per online,
oracle, and frozen owner. Retained data homes are 688,213,602, 687,685,554,
and 1,034,471,242 bytes per owner, respectively. The nine homes total
7,231,111,194 bytes. These are end-to-end controlled-scenario costs, and the
large durable history remains a separate scaling concern from fixed field
capacity.

This establishes that admitted observations can change the field's own next
action selection, survive restart, and support new participants without a
demonstrated acquisition sequence. It establishes autonomous selection only
inside a supplied, closed, reversible action surface. The initial current
observation, vocabulary, goal, reusable skill, permissions, decision bound,
and segment endpoint remain supplied. The result does not establish discovery
of a new action, open-vocabulary acquisition, safe treatment of arbitrary
abandoned streams, broad operation-order generalization, calibrated
uncertainty, or safety against unrepresented outcomes.
[§28.9](FIELD-INTELLIGENCE-DESIGN.md#289-field-selected-acquisition-measurements)
records the protocol, measurements, evidence reconstruction, costs, and claim
boundary.

### Autonomous skill formation and resonant coupling comparison

The skill-formation benchmark begins with only two failed one-step
observations, `open -> blocked` and `align -> misaligned`. The host supplies
the three-action vocabulary `prime`, `align`, and `open`; the goal observation
`opened`; explicit forbidden observations; and authorization for each action.
It registers the prospective skill identity and goal before discovery, but
supplies no successful episode, demonstrated next action, action policy, or
goal observation during transfer.

```powershell
python run_autonomous_skill_formation_scenario.py --seeds 101 202 303 --output _diag/temporal-autonomous-skill-formation/coupled-field-v5/report.json --data-home _diag/temporal-autonomous-skill-formation/coupled-field-v5/owners
python verify_autonomous_skill_formation.py --report _diag/temporal-autonomous-skill-formation/coupled-field-v5/report.json --data-home _diag/temporal-autonomous-skill-formation/coupled-field-v5/owners --source run_autonomous_skill_formation_scenario.py --output _diag/temporal-autonomous-skill-formation/coupled-field-v5/verification.json
```

Registration writes the bounded goal and forbidden-observation binding into
the existing skill slot. Because no supported safe root path exists, its
policy and rank planes remain zero, the registration receipt is `pending`,
and readout exposes no action. Registration changes field-state identity but
does not change the learned-memory or transition digest or initialize a
resonant workspace.

For every seed, goal-directed temporal inquiry then selects
`prime -> align -> open` from real observations. Each observation is admitted
as one append-only revision of the growing discovery episode. Every
`learn_temporal` transition recomputes registered policies from the revised
numeric field. The skill remains pending after `primed` and `aligned`; the
admission containing `opened` returns the skill in `formed_skills` and makes
its root policy available. No post-experience condensation operation is
called.

The successful owner transition derives two nonzero signals from the same
learned temporal revision: a `goal-observation` event and the newly formed
skill's safe-reachability ranks. Both use the fixed, non-learned seven-pool
codec. For this three-step path each normalized signal is
`[1/sqrt(3), 0, 0, 1/sqrt(3), 0, 0, 1/sqrt(3)]`. The transition divides its
`1e-3` admission work budget equally between them, applies two common-mode
momentum impulses of `5e-4` each, and publishes the updated resonant workspace
and temporal field in one immutable atlas checkpoint. The two earlier
discovery revisions emit no work because their derived event signals are
zero. A safety-driven withdrawal uses the last supported-rank pattern with
opposite momentum orientation.

An otherwise identical unregistered `TemporalField` is reconstructed from the
same three episodes and source-revision identities. Its learned-memory and
transition SHA-256 values match the registered field exactly, while it
contains no skill. All three registered and control fields share the learned
transition SHA-256
`a0f8a607e078b2d2a7cadc36da83cd0a891144a3997d4b6d98722c9fa9decd60`.
This isolates policy formation from acquisition of the categorical
transition structure.

A second control starts from the same resonant profile and evidence clock but
receives no skill impulse. Both workspaces advance for eight ticks with their
ordinary sources disabled. The coupled field propagates nonzero power into
all seven pools and ends at field energy `9.88366652162665e-4`; the matched
control remains exactly quiescent. Exact restart preserves the coupled
workspace SHA-256
`8ac1425c79066dd0ac70a809197e7b79ba1a9f0c118a1f66d79d13feabf28a0d`.

A fresh participant completes the latch using only the formed skill readout
and actual observations. Exact restart preserves both learned closure and
wave page, and a second fresh participant completes the same sequence after
restart.

| Measurement across seeds 101, 202, and 303 | Observed result |
|---|---:|
| Field-selected discovery completions | 3/3 |
| Prospective skills initially pending | 3/3 |
| Skills formed at successful evidence admission | 3/3 |
| Premature formation events | 0 |
| Successful admissions with bound goal-outcome and formation events | 3/3 |
| Goal-outcome / formation work across all runs | `1.5e-3` / `1.5e-3` |
| Total requested/applied admission work | `3e-3` / `3e-3` |
| Coupled runs with nonzero power in all pools after 8 ticks | 3/3 |
| Matched no-impulse controls remaining quiescent | 3/3 |
| Matched unregistered transition and memory controls | 3/3 |
| Fresh-participant transfers completed | 3/3 |
| Post-restart fresh-participant transfers completed | 3/3 |
| Exact temporal and resonant restarts | 3/3 |
| Represented unsafe observations | 0 |
| Live language-model calls | 0 |
| Fixed temporal / resonant field allocation per owner | 51,840 B / 2,088 B |
| Complete end-to-end elapsed time | 26.47 s |

The independent verifier imports no CassiFI production module. It replays the
three-stage environment; reconstructs all 15 source revisions, their
content-addressed blobs, and source-bound evidence events; binds each
goal-outcome and formation event pair to the same evidence identity; checks both
`5e-4` impulse receipts, their ordered
energy states, and the `1e-3` admission total; validates the skill identity,
complete fixed resonant profile, and per-skill categorical-policy flag;
independently decodes the persisted resonant page and recomputes its energy,
pool powers, and SHA-256; reconstructs the matched no-impulse control from
verifier-owned canonical profile, layout, and zero-ledger constants and checks
its semantic advance-receipt fields, page, digest, and clocks; replays both
transfer passes; and walks 63 durable checkpoint manifests and every
referenced object. It reports `PASS`. The retained report SHA-256 is
`f6e3e8493cfec926ecc8888dfd882fedec9f0235705af70b7f74e411d59906ec`;
the verification receipt SHA-256 is
`4eb127b84987ee474277bb0f35b71129b0f6a01b35eb9b15808a8cf8a22dbd7c`.

This establishes field-selected action acquisition, automatic formation of a
registered prospective skill, direct energy-accounted coupling of its actual
goal outcome and formation into the continuous seven-pool field, source-free
propagation, exact retention, and reuse by new participants in one deterministic
environment. Re-learning also withdraws a formed skill when represented
evidence makes its policy unsafe. The three seeds permute operation
presentation but are reproducibility repeats, not independent worlds.

The per-skill categorical policy remains computed from the temporal field.
Selection among multiple admissible formed skills is now a separate read-only
resonant surface: categorical safety, authorization, feasibility, and
represented-forbidden checks run first, and the surviving distinct actions
are ranked by their compatibility with the current seven-pool phase-space
state. Each newly admitted episode can also contribute bounded outcome work
to that state. The result still does not establish autonomous skill naming or
goal invention, action invention, open-vocabulary acquisition, broad task
generalization, calibrated uncertainty, or safety against unrepresented
outcomes.

### Online outcome learning and resonant action crossover

[`run_online_resonant_learning_scenario.py`](run_online_resonant_learning_scenario.py)
tests whether experience admitted during use can change a later committed
action. It begins with two already formed, categorically safe skills in one
temporal memory:

- `fast-release`: one action, `short -> done-fast`;
- `staged-release`: two actions, `long -> stage -> continue -> done-staged`.

The initial formation impulses favor `fast-release`. The online condition then
admits four demonstrated successful `staged-release` episodes, one immutable
source revision at a time. Its matched held-wave control presents the same
current categorical candidate records to the same scorer but retains the
exact pre-feedback resonant workspace. The control is therefore not a second
adaptive owner and does not freeze or replace learned categorical memory.

For every newly admitted episode,
`TemporalField.episode_pool_signals` derives event directions from the learned
transition, safe-rank, goal, and forbidden coordinates. The atlas divides one
`1e-3` admission work budget equally among its nonzero event signals and
applies them through the same energy-accounted pool impulse as formation and
withdrawal. The successful two-step episode produces one reachable-context
event and one goal event, each receiving `5e-4` work. Replayed prefixes receive
no second impulse.

`FieldIntelligenceOwner.select_temporal_action` first excludes categorically
unsupported, unavailable, represented-forbidden, unauthorized, and infeasible
operations. A singleton or common action is resolved categorically. Otherwise
the fixed safe-rank signal for every surviving skill is lifted into the
seven-pool common-mode geometry and scored against the current position and
momentum at the persisted heartbeat phase. The highest score is selected only
when its margin is greater than the caller's nonnegative minimum. Selection
does not advance the field, change memory, or publish a checkpoint.

All three retained seeds produced the same measured score trajectory:

| Admitted successful staged episodes | Fast score | Staged score | Selected skill | Margin |
|---:|---:|---:|---|---:|
| 0 | 0.9915816022 | 0.9561326996 | `fast-release` | 0.0354489026 |
| 1 | 0.9828218265 | 0.9709753650 | `fast-release` | 0.0118464615 |
| 2 | 0.9762246300 | 0.9783122557 | `staged-release` | 0.0020876257 |
| 3 | 0.9711480871 | 0.9826880968 | `staged-release` | 0.0115400098 |
| 4 | 0.9671061425 | 0.9855945311 | `staged-release` | 0.0184883886 |

| Measurement across seeds 101, 202, and 303 | Observed result |
|---|---:|
| Online preference crossovers | 3/3 |
| Crossover round | 2, 2, 2 |
| Held-wave control crossovers | 0/3 |
| Online held-out completions | 3/3 |
| Online held-out action sequence | `long -> continue` |
| Online represented unsafe observations | 0 |
| Held-wave control completions | 0/3 |
| Held-wave control action / observation | `short` / `jammed` |
| Held-wave control represented unsafe observations | 3 |
| Field-only decision counterfactuals | 3/3 |
| Exact owner and resonant-workspace restarts | 3/3 |
| Reconstructed candidate score sets | 33 |
| Verified source records / checkpoint manifests | 18 / 45 |
| Total online outcome-feedback work | `0.011999999999999997` |
| Final formation / outcome / total field work per owner | `0.002` / `0.004` / `0.006` |
| Final stored field energy / balance defect per owner | `0.006` / `0.0` |
| Resonant field bytes per owner | 2,088 B |
| Complete retained owner evidence per seed | 532,935 B |
| Live language-model calls | 0 |
| Complete end-to-end elapsed time | 19.86 s |

The online and held-wave decisions have identical candidate semantics,
categorical state, operation constraints, and presentation-independent
candidate sets. Only the resonant workspace differs. The held-out world jams
the initially preferred shortcut and completes the staged sequence, so the
score crossover changes observable behavior rather than only an inspection
metric.

[`verify_online_resonant_learning.py`](verify_online_resonant_learning.py)
imports no CassiFI production module. It reconstructs the six independent
source chains per seed from their content-addressed bytes, walks 45 checkpoint
manifests, decodes raw float64 workspace pages, recomputes 33 complete score
sets from verifier-owned phase-space arithmetic, checks all causal held-wave
comparisons, replays online and control actions in its own simulator, and
confirms exact bundle and workspace identities across restart. A score-only
report tamper and a mismatched source-byte tamper were both rejected during
verification.

Run and independently verify the retained comparison with:

```powershell
python run_online_resonant_learning_scenario.py --seeds 101 202 303 --output _diag/temporal-online-resonant-learning/closed-loop-v1/report.json --data-home _diag/temporal-online-resonant-learning/closed-loop-v1
python verify_online_resonant_learning.py --report _diag/temporal-online-resonant-learning/closed-loop-v1/report.json --data-home _diag/temporal-online-resonant-learning/closed-loop-v1 --output _diag/temporal-online-resonant-learning/closed-loop-v1/verification.json
```

The retained scenario source SHA-256 is
`484e733aeefd15351e9b7aa8746331a28eed05aecb692173e2898a32a0463a0a`;
the report file SHA-256 is
`79e1547c9f012641abb2a48816dd31c1c8b728c10e4cbf32437dd31ffb690381`;
and the verification file SHA-256 is
`d0234f8cc0bb622c125bca488770fe9f5d9ae933ba4b76494fa7284cc2a353fd`.

This establishes a causal field-only preference crossover under repeated
represented outcomes, exact retention of the changed wave state, and safer
held-out action in this fixed two-skill controlled world. The successful
alternative is demonstrated during feedback; the benchmark does not establish
that the field invents or autonomously explores that alternative. It also does
not establish action invention, open-vocabulary learning, calibrated
uncertainty, safety under unrepresented outcomes, broad-world generalization,
or subjective experience.

## Uniform clause-field SAT research

[`cassi_clause_field.py`](cassi_clause_field.py) is a fixed, deterministic
polynomial-space chronological DPLL baseline. The CNF, assignment, implication
reasons, trail, decision stack, learned decision clauses, status, and resource
counters occupy one exact-integer float64 tensor with shape `[1, 9*M, 1]`. The
host repeatedly calls `step(state)`; it does not generate assignments or
schedule branches. This removes the exponential action-vocabulary and
chart-product costs of the earlier SAT crossover while leaving all search and
proof work explicit.

Every conflict now carries a linear resolution derivation from its conflicting
and reason clauses. A sound weakening yields the stored decision nogood.
Closed sibling branches are resolved on their decision pivot until an UNSAT
run derives the empty clause. Earlier learned nogoods may be reused as lemmas,
so the complete certificate is a resolution DAG rather than a trusted trace
label.

Run the 282-formula corpus, independent receipt verifier, and focused
contracts with:

```powershell
python run_p_vs_np_clause_field_probe.py
python verify_p_vs_np_clause_field_probe.py
python -m pytest test_clause_field.py -q
```

The measured receipt contains 275 SAT and 7 UNSAT decisions, 281 independent
truth-table checks, verified SAT certificates, seven independently verified
resolution refutations, exact checkpoint roundtrips, and 14 representation
controls. Across all cases, the proof checker validated 1,332 resolution or
weakening inferences; focused tamper tests reject altered conflict and
branch-closure resolvents.

This characterization settles the baseline's worst-case status. On the
standard `h+1`-pigeons/`h`-holes CNFs with `N=h(h+1)` variables, Haken's
unrestricted-resolution lower bound is `2^Omega(h)`, equivalently
`2^Omega(sqrt(N))`. A `T`-transition clause-field run translates to a
resolution refutation with `O(N*T)` inferences. The implemented transition law
therefore has superpolynomial worst-case transition count. This is a lower
bound for this resolution-bounded solver, not a proof that `P != NP` and not a
lower bound on all CassiFI algorithms.

## Beyond-resolution hybrid inference

[`cassi_hybrid_inference.py`](cassi_hybrid_inference.py) changes the deductions
the field can retain and derive, rather than only changing branch order. One
immutable float64 tensor with shape `[1, 9*M, 1]` stores the source clauses,
derived clauses, pseudo-Boolean inequalities, GF(2) equations, fresh-variable
definitions, premise pointers, rule identifiers, status, and resource counters.
Every stored coordinate is an exact integer of magnitude at most `2^53-1`;
capacity, coefficient, and transition limits return `exhausted`, never UNSAT.
The fixed controller keeps no adaptive proof database, formula-family label,
search schedule, or learned model outside the field.

The implemented rules are:

1. exact clause-to-inequality translation, nonnegative integer scaling,
   addition, and exact-coefficient division with floor-rounded right-hand side;
2. CNF-grounded recovery of complete bounded-width parity blocks and GF(2)
   addition;
3. a bridge from matching integer upper and lower bounds to a parity equation;
4. fresh acyclic disjunction abbreviations with their three defining clauses;
5. ordinary resolution over source, extension, and derived clauses.

The frozen 31-case receipt contains 25 checked UNSAT refutations and six
fail-closed controls. Standard `(h+1)`-into-`h` pigeonhole formulas through
`h=12` close by cutting planes, not resolution. Their construction has

```text
m = (h+1) + h * C(h+1, 2) input clauses
2m - 1 + 2h^2 - 3h derived proof lines,
```

so this particular obstruction has an explicit polynomial proof. The largest
run used 156 variables, 949 input clauses, 2,149 derived lines, maximum integer
magnitude 23, and 84,206,304 field bytes. Odd-charge degree-three prism
Tseitin formulas have `3r` variables and `20r-1` total proof lines:
`8r` inputs, `8r` clause conversions, `2r` imported equations, and `2r-1`
XOR additions. The largest run used 48 variables and 319 proof lines.

The crossed case is not a parallel portfolio of solvers. Cutting-plane steps
derive an exact-one equality, the bridge converts its parity, and GF(2)
cancellation with an independently recovered even-parity equation produces
the final contradiction. A separate case introduces a fresh disjunction and
uses its defining clauses in a complete resolution refutation. Satisfiable
even-parity and extension controls exhaust without contradiction; incomplete
parity and capacity premises are not imported as stronger facts; a deliberately
one-transition profile also exhausts without making a false UNSAT claim.

### Connected matched exact-one/parity class

The receipt now includes a syntax-defined infinite mixed class. Each instance
has an even number `b >= 4` of disjoint three-variable exact-one blocks. The
remaining clauses are complete two-clause parity encodings whose supports pair
every variable exactly once across blocks, and the matching quotient graph is
connected. The independent verifier discovers that partition from the raw CNF;
it receives no case name, generator metadata, or proof hint.

Over GF(2), every exact-one block contributes
`XOR_{x in B_i} x = 1`, and every matching pair contributes
`x_u XOR x_v = ell_e`. XORing all equations cancels every variable exactly
twice. Therefore the instance is UNSAT whenever

```text
(b mod 2) XOR XOR_e ell_e = 1.
```

This soundness statement covers the recognized class. For the implemented
canonical connected subfamily, the deterministic controller has exact bounds:

```text
variables                  3b
input clauses              7b
derived proof lines        18b
total proof lines          25b
maximum integer magnitude  b
field bytes                17928b^2 + 55296b.
```

The proof uses cutting-plane derivation of block cardinalities, the
cardinality-to-parity bridge, CNF-grounded pair parity, and GF(2)
cancellation. A source-loop audit bounds one bulk proof construction by
`O(b^3)` controller time and `O(b^2)` temporary space. Repeated public
single-transition stepping is `O(b^4)` because it reconstructs the same plan
for each of `18b` transitions.

The guarantee extends to every edge-label placement on the canonical topology
with odd total label parity. Complete matching equations and exact-one block
parities form an inconsistent GF(2) system, so deterministic elimination must
expose `0 = 1`. Deduplicating cardinality bridges by coefficient vector and
right-hand side gives the conservative bounds:

```text
proof lines                 <= 40b^2 + 32b + 256
maximum integer magnitude   <= 3b
field bytes                 216b(40b^2 + 32b + 256).
```

Bulk controller work and temporary space are `O(b^3)`; repeated
single-transition stepping is `O(b^5)`. Dense odd-label cases through `b=12`
are retained in the receipt. The behavioral suite exhaustively checks all 64
labelings at `b=4` and all 512 labelings at `b=6`: every globally inconsistent
case closes, and no globally consistent case produces a false contradiction.

The one-odd-edge sizes `b = 4, 6, 8, 12, 16, 24` match the exact formulas.
At `b=24`, the receipt has 72 variables, 168 input clauses, 432 derived lines,
600 total lines, integer magnitude 24, and 11,653,632 field bytes. A
consistent `b=4` control has a truth-table model and ends `exhausted` without
a contradiction. The hybrid proof field thereby proves soundness for the
syntax-recognized class and deterministic polynomial refutation discovery for
every globally inconsistent labeling on the canonical topology; it does not
itself decide consistent members or unrestricted CNF.

Run the scenario, independent checker, and behavioral contracts with:

```powershell
python run_p_vs_np_hybrid_inference.py
python verify_hybrid_inference.py
python -m pytest test_hybrid_inference.py -q
```

The receipt is `_diag/p_vs_np_hybrid_inference.json`. It stores every input
formula and proof line, state and proof digests, exact resource ledgers,
checkpoint and deterministic-replay results, representation controls, four
scaling tables, and the restricted-class theorem evidence. The verifier
imports neither the field nor the runner and reconstructs every inference
from serialized premises.

This hybrid-proof upgrade removes Haken's pigeonhole lower bound as a lower
bound on that transition law and proves polynomial deterministic refutation
discovery on the canonical connected mixed topology for every contradictory
edge labeling. The hybrid proof field by itself does not decide every
parity-consistent member, every connected matching topology, or unrestricted
CNF.

### Total decision on the canonical topology

`cassi_mixed_exact_one_field.py` closes the parity-consistent side for the
same canonical cycle-plus-adjacent-pair topology. Write a block's three
variables as `x[i,0]`, `x[i,1]`, and `x[i,2]`. If `c[i]` is the cycle-edge
label from `x[i,1]` to `x[i+1,0]`, then choosing the port-one values
`p[i] = x[i,1]` fixes

```text
x[i,0] = p[i-1] XOR c[i-1]
x[i,2] = 1 - x[i,0] - p[i].
```

The second equation is a valid bit exactly when the block has one true
variable. For adjacent blocks `2j` and `2j+1`, the remaining chord condition
is

```text
x[2j,2] XOR x[2j+1,2] = d[j].
```

The field tries both values of the single cycle boundary bit and carries only
the previous `p` bit. One transition processes one adjacent block pair by
checking all two-bit choices for its outgoing `p` values. After `b/2`
transitions, a path is accepting exactly when its final carry equals its
initial boundary. Every satisfying assignment induces such a path, and every
accepting path reconstructs an assignment satisfying all `7b` clauses.
Consequently, absence of an accepting path is a complete UNSAT certificate
for this topology, including parity-consistent instances that the global
XOR criterion cannot decide.

The exact resource formulas are:

```text
variables             3b
input clauses         7b
field transitions     b/2
candidate checks      8b
float64 field values  12 + 21b/2
field bytes           96 + 84b.
```

The fixed-width reachability table has four Boolean states per layer. Bulk
dynamic-program state construction, persistent field storage, and the abstract
certificate entry count are `O(b)`. Exact CNF canonicalization and certificate
digest serialization make the complete public solve `O(b log b)`. Replaying
the immutable one-transition `step` interface costs `O(b^2)`, because every
step validates, copies, and hashes an `O(b)` tensor. The one immutable field
contains the edge labels, every reachability layer, deterministic predecessors,
any final assignment, status, and work counters. It has no learned side table,
model fallback, family-name branch, or host-supplied proof plan.

The frozen receipt covers 600 cases. It exhausts all 64 labelings at `b=4`
and all 512 at `b=6`. Independent exact-one assignment enumeration gives
`31 SAT / 33 UNSAT` and `235 SAT / 277 UNSAT`, respectively; the field agrees
on every case. Of those 576 small cases, 22 are parity-consistent but UNSAT,
so the total procedure is strictly stronger than the global parity test.
Twenty-four scaling cases at `b = 8, 12, 24, 48, 96, 192, 384, 768` exercise
satisfiable, one-odd-edge, and dense-odd-edge paths. At `b=768`, the field
decides a 2,304-variable, 5,376-clause formula using 384 transitions, 6,144
candidate checks, and 64,608 bytes.

The independent verifier imports neither the field nor the runner. It rebuilds
all 600 canonical formulas, recomputes every dynamic-program layer and
deterministic predecessor, reconstructs or excludes an accepting path,
checks every SAT assignment, truth-tables all `b=4` cases, decodes every
persisted float64 tensor, verifies state and certificate digests, and rebuilds
the resource aggregates.

Run the scenario, verifier, and behavioral suite with:

```powershell
python run_mixed_exact_one_decision.py
python verify_mixed_exact_one_decision.py
python -m pytest test_mixed_exact_one_decision.py -q
```

The receipt is `_diag/mixed_exact_one_decision.json`. The recognizer requires
the exact `1..3b` variable-to-block/port numbering and complete canonical
clause set; permutations must be normalized before this path. Checkpoint
digests provide integrity, while the independent verifier supplies the
semantic check. This is a total polynomial-time theorem for one bounded-width
infinite CNF class. Its recurrence is topology-specific; the next section uses
a different perfect-matching reduction for arbitrary connected matched
topologies. Neither procedure decides unrestricted SAT or establishes
`P = NP`.

### Total decision on every connected matched topology

`cassi_general_matched_field.py` removes the bounded-width topology restriction
for the complete connected matched exact-one/parity class. The recognizer
requires:

1. an even number `b >= 4` of pairwise-disjoint three-variable exact-one
   blocks;
2. one complete binary parity equation incident to every variable exactly
   once;
3. parity edges joining distinct blocks; and
4. a connected quotient graph on the blocks.

It verifies those conditions from the complete CNF and receives no topology
name, family label, decomposition, proof plan, or model hint.

The source reduces exactly to a general-graph perfect-matching problem. Each
exact-one block becomes one auxiliary vertex. A parity-zero edge becomes a
direct edge between its blocks. A parity-one edge becomes a length-two path
through a fresh subdivision vertex. A satisfying assignment selects one
auxiliary incidence at every block and one side of every parity-one
subdivision. Conversely, a perfect matching sets the endpoint variables of a
selected direct edge to one, the endpoints of an unselected direct edge to
zero, and exactly the selected side of every subdivision to one. These maps
are inverse in the source-provenance multigraph.

The decision implementation retains every source and auxiliary edge. It uses
a simple adjacency projection for blossom search because parallel edges do
not change perfect-matching existence, then canonically lifts a selected
parallel block pair back to a source edge when constructing the SAT
assignment. Malformed source incidence, repeated variables, occurrence
aliases, same-block parity edges, and disconnected quotients fail closed
rather than being classified SAT or UNSAT.

For `m1` parity-one edges among the `3b/2` total parity edges:

```text
auxiliary vertices    N = b + m1        <= 5b/2
auxiliary edges       E = 3b/2 + m1     <= 3b
float64 field values      12 + 17b + 5m1
field bytes               96 + 136b + 40m1.
```

The deterministic Edmonds controller has a conservative `O(b^3)` matching
bound and `O(b)` live scratch space. Its root and adjacency order, queue,
blossom contractions, and matching updates are deterministic. Public
one-root stepping uses the same search schedule; immutable-field validation,
copying, and hashing add `O(b^2)` work without changing that bound.

The abstract algorithm uses `O(log b)`-bit integer identifiers. The concrete
float64 profile rejects any size whose conservative `N^3` work-counter range
would exceed exact integer representation, preventing silent numeric
rounding.

SAT certificates contain a perfect matching and a complete assignment checked
against every source clause. UNSAT certificates contain a Tutte barrier `S`
for which the number of odd connected components of `H-S` is greater than
`|S|`. That inequality directly excludes every perfect matching. The current
even-order barrier extractor uses at most `N` additional matching runs and
therefore has a conservative `O(b^4)` construction bound; the certificate
itself is independently checkable in `O(N+E)`.

The implemented total SAT path is therefore `O(b^3)`; the even-order UNSAT
path including proof-grade barrier extraction is `O(b^4)`.

Run the scenario, independent checker, and behavioral suite with:

```powershell
python run_general_matched_decision.py
python verify_general_matched_decision.py
python -m pytest test_general_matched_field.py -q
```

The receipt is `_diag/general_matched_decision.json`. It contains 672
decisions: all edge labelings of simple `K_4`, a connected four-block
multigraph, and the triangular prism, plus `K_3,3`, Petersen, and prism
scaling cases through `b=192`. The full outcomes are `324 SAT / 348 UNSAT`,
including 23 parity-consistent UNSAT cases. All 640 exhaustive-label cases
agree with independent exact-one assignment enumeration. Forty-five cases
replay through public immutable steps, and every checkpoint restores exactly.

`verify_general_matched_decision.py` imports neither field nor runner. It
recognizes every source CNF, reconstructs the source-provenance graph, checks
every perfect matching or Tutte obstruction, evaluates all SAT assignments,
decodes all tensor coordinates, verifies problem/state/certificate digests,
and rebuilds every aggregate. All 672 certificates and four fail-closed
controls pass.

This is a total polynomial-time theorem for every connected topology in the
recognized occurrence-matching class, including unbounded-width quotient
families. It identifies that class as a disguised perfect-matching problem
already in `P`; the next implementation below permits controlled occurrence
reuse. Neither result decides unrestricted SAT or establishes `P = NP`.

### Parameterized decision at the occurrence-alias boundary

[`cassi_alias_exact_one_field.py`](cassi_alias_exact_one_field.py) permits each
variable of a positive three-variable exact-one CNF to occur exactly two or
three times. If `c` is the clause count and `k` is the number of degree-three
variables, the field enumerates the `2^k` cubic assignments. Each assignment
either creates an immediate clause conflict or leaves a residual problem in
which every available degree-two variable joins its two unsatisfied clauses.
That branch is satisfiable exactly when the residual multigraph has a perfect
matching.

The reduction gives a total deterministic fixed-parameter algorithm:

```text
decision search                         O(2^k c^3)
complete UNSAT proof construction       O(2^k c^4) conservative
persistent field values                 13 + 6c
SAT certificate                         O(c)
complete UNSAT certificate              O(2^k c)
```

The abstract algorithm uses `O(log c)`-bit integers. The concrete float64
profile rejects identifiers or conservative work counters outside the exact
integer range, so rounding cannot silently become a branch decision.

One public immutable `step` evaluates one cubic assignment. The tensor owns
the canonical formula, degree table, cubic-variable indices, cursor, status,
exact work counters, and final assignment. A SAT certificate provides a
perfect matching and complete source assignment. A complete UNSAT certificate
provides an ordered conflict, odd-residual, or Tutte-barrier witness for every
cubic assignment.

This is also the first continuation whose full source class is NP-complete.
Cubic Planar Monotone 1-in-3 SAT is the special case in which every variable
has degree three, so `k=n`; Moore and Robson prove that subfamily NP-complete.
The field therefore reaches the bounded-occurrence hardness seam, but retains
an exponential dependence on the unbounded parameter. Replacing that
dependence by a polynomial for all recognized inputs would establish
`P = NP`.

Run the scenario, independent checker, and behavioral suite with:

```powershell
python run_alias_exact_one_decision.py
python verify_alias_exact_one_decision.py
python -m pytest test_alias_exact_one_field.py -q
```

The receipt is `_diag/alias_exact_one_decision.json`. It contains 65 complete
decisions: 56 small cases independently truth-tabled and nine scaling or
stress cases. The outcomes are `43 SAT / 22 UNSAT`; 29 cases replay through
public immutable steps. The largest case has 48 clauses, 65 variables, 14
cubic variables, 16,384 available branches, and 2,408 field bytes.

`verify_alias_exact_one_decision.py` imports neither field nor runner. It
reconstructs every residual graph, checks every branch conflict, perfect
matching, odd-order obstruction, or Tutte barrier, evaluates all SAT
assignments, truth-tables every enumerated input, decodes all tensor
coordinates, verifies digests and counters, and rebuilds every aggregate. All
65 certificates and four fail-closed controls pass.

### Exact-cover and uniform-matchgate compression results

[`run_alias_compression_analysis.py`](run_alias_compression_analysis.py) tests
two ways to compress the `2^k` family exposed by the alias field.

First, it views every clause as a vertex and every variable as a size-two or
size-three exact-cover edge. Branching on one uncovered clause gives the worst
local recurrence

```text
T(c) <= T(c-3) + 2 T(c-2),
```

with golden-ratio base `1.618033988749895`. This is a local relation, not a
global bound for the implemented search: a permitted degree-two-only clause
has three choices that each remove two clauses, yielding
`T(c) <= 3 T(c-2)`. On the 65-case receipt, the memoized cover search reduces
25,425 checked cubic assignments to 957 residual states; the largest
individual comparison is 16,384 assignments versus 395 states. It visits
fewer states on 31 cases, the same number on two, and more on 32 cases where
the binary schedule often encounters SAT immediately.

This search is retained only as an empirical analysis control. The
[`O*(1.0984^n)` monotone one-in-three SAT bound recorded in the exact-time
CSP literature](https://victorlagerkvist.github.io/assets/pdf/jcss2017.pdf)
remains the valid global benchmark; no asymptotic comparison follows from the
local golden-ratio relation. The independently proved matching-branch bound is
preferable to that generic bound only when

```text
k/c < 0.19022661804781446.
```

Second, the analyzer represents the cubic seam as a bipartite signature
problem with `EQ3 = [1,0,0,1]` at degree-three variables and
`EXACT1_3 = [0,1,0,0]` at clauses. [Planar matchgate
signatures](https://arxiv.org/abs/1303.6729) necessarily have only even-weight
or only odd-weight support. For every parity assignment
to the two signatures, the analyzer transforms them through a symbolic
invertible uniform `2x2` basis, adds `z det(A)-1=0`, and computes a Gröbner
basis. It repeats the calculation under both inverse/transpose tensor
conventions. All eight ideals reduce to `[1]`.

The result rules out one specific compression: no uniform invertible `2x2`
basis makes both local signatures satisfy even the necessary matchgate parity
condition. It does not rule out nonuniform gauges, larger gadgets,
higher-dimensional signatures, non-matchgate algebra, or unrelated
algorithms.

Run and independently reconstruct the analysis with:

```powershell
python run_alias_compression_analysis.py
python verify_alias_compression_analysis.py
```

The SHA-256-bound receipt is `_diag/alias_compression_analysis.json`. The
independent verifier rebuilds all 65 cover searches, truth-tables all 127
degree-two/degree-three formulas with four or five variables, recomputes the
crossover and recurrence roots, and independently reduces the eight matchgate
ideals. The exhaustive small set contains 94 SAT and 33 UNSAT formulas; every
decision agrees.

### Exact cubic incidence-kernel boundary

The degree-three-only subfamily of the occurrence-alias problem has an exact
linear-algebraic normal form. Let `M` be its clause-by-variable incidence
matrix. There are equally many variables and clauses, and every row and column
of `M` has three ones. A Boolean vector `x` is a satisfying assignment exactly
when

```text
M x = 1.
```

Set `z = 3x - 1`. Since `M 1 = 3 1`,

```text
M x = 1, x in {0,1}^n
    iff
M z = 0, z in {-1,2}^n.
```

This separates the linear and discrete parts of the problem exactly: SAT asks
whether the rational kernel of `M` intersects the two-point alphabet
`{-1,2}^n`. It immediately gives two polynomial UNSAT certificates. Full
column rank leaves only the zero kernel vector, which is outside the alphabet.
Also, summing `M x = 1` gives `3 sum(x) = n`, so `n` must be divisible by
three.

[`cubic_kernel_decision.py`](cubic_kernel_decision.py) computes an exact rational
RREF in either its deterministic canonical coordinates or coordinates selected
by a caller-supplied column basis. The complementary free coordinates must be
`-1` or `2`. When every pivot expression depends on at most two free
coordinates, its allowed alphabet values form a unary or binary Boolean
relation. Excluding each forbidden tuple produces 2-CNF, so one
implication-graph SCC pass decides the whole system in polynomial time. This
remains polynomial when nullity is linear in `n`; the sufficient condition is
basis width, not bounded nullity. The implementation records a checkable
implication certificate and reconstructs every SAT assignment against the
original clauses.

The basis condition has an exact matroid interpretation. Let `N` be the column
matroid of `M`, let `B` be a column basis, and let `F` be its complement. Then
`F` is a basis of the dual `N*`. The free-coordinate support of a pivot
`b in B` is its fundamental cocircuit in `N`, minus `b`; equivalently, it is
the fundamental circuit of `b` relative to `F` in `N*`, minus `b`. Thus a
maximum support of two says exactly that the ground-set basis `F` frames the
dual matroid.

There is also an exact semantic basis theorem. Call a complementary dual
ground-set basis `F` **zero-valid** when setting all of its Boolean free
coordinates to zero makes every induced pivot coordinate land in `{-1,2}`.
A cubic exact-one formula is SAT if and only if such a basis exists. Given a
satisfying assignment, its one-columns have pairwise disjoint nonempty row
supports and are independent. Projection of `ker(M)` onto the zero coordinates
is therefore injective, so Gaussian elimination selects a dual basis entirely
from those zero coordinates. Conversely, the all-zero free tuple of a
zero-valid basis reconstructs `z in ker(M) intersect {-1,2}^n`, hence the
satisfying assignment `x = (z+1)/3`.

This makes zero-valid internal-basis recognition NP-complete even for planar
square cubic incidence matrices: membership is checked by one elimination and
one tuple evaluation, while Cubic Planar Monotone 1-in-3 SAT maps to the same
matrix. [`cubic_kernel_zero_valid_basis`](cubic_kernel_decision.py) implements
the polynomial witness-to-basis direction. The result is a
certificate-preserving reformulation, not a polynomial SAT algorithm, and it
does not classify width-two frame-basis recognition.

This is a polynomial theorem when a width-two basis is supplied: exact
elimination verifies the basis and then 2-SAT decides the formula. It is
stronger than merely finding a row-equivalent external frame matrix, because
an external frame's coordinate axes need not be original variable columns.
The diagnostic `cubic_kernel_basis_width` finds the exact optimum by
enumerating every rank-sized column subset. Its work is
`binomial(n,rank) poly(n)`, so it is evidence and a certificate generator, not
a polynomial basis-finding algorithm.

The exact census corrects the canonical-coordinate interpretation:

|Control|Status|Subsets|Bases|Basis maximum-support histogram|Minimum|
|---|---:|---:|---:|---:|---:|
|canonical support-three, `n=9`|SAT|84|36|`2:24, 3:12`|2|
|canonical support-three, `n=15`|UNSAT|455|128|`2:60, 3:68`|2|
|greedy exchange trap, `n=9`|SAT|84|51|`2:8, 3:43`|2|
|all-bases-ternary, `n=12`|SAT|220|136|`3:136`|3|
|all-bases-ternary, `n=15`|UNSAT|455|237|`3:237`|3|

The two original canonical support-three formulas and a separate SAT control
therefore take the 2-SAT path under another basis and enumerate no alphabet
assignments. Separate SAT and UNSAT controls remain support three under every
column basis. Basis choice strictly enlarges the certificate-bearing 2-SAT
class, but unrestricted exact basis search does not enlarge the unassisted
polynomial-time class. Without a supplied width-two basis, the total decision
still uses canonical coordinates and falls back to `2^nullity` alphabet
assignments when support exceeds two.
 
Three restricted searches are polynomial:

1. for every fixed nullity `k`, enumerate the `binomial(n,k) = O(n^k)`
   complementary dual bases;
2. if the dual column matroid is graphic, the frame condition is exactly a
   tree 2-spanner in each component;
3. if the primal column matroid is graphic, the condition is exactly a
   spanning forest of congestion at most three.

Graphic-matroid recognition, tree-2-spanner construction, and
threshold-three spanning-tree-congestion are polynomial. These cases do not
classify cubic incidence matrices with growing nullity outside the graphic and
cographic classes.

Complete one-column basis-exchange graphs expose two further boundaries. All
five controls have every dual element in a loop, parallel pair, or triangle,
including both invariant-width-three cases, so local small-circuit coverage
does not imply one common frame basis. A connected SAT control has 51 bases,
eight of width two and 43 of width three. Nineteen width-three bases have no
exchange to a smaller-width neighbor; only 32 bases reach an optimum under
strict descent. Equal-width moves do connect all 51 to an optimum, so the
certificate rules out naive strict descent but not plateau-aware search.

### Growing-nullity Schaefer-basis census

[`growing_nullity_schaefer_probe.py`](growing_nullity_schaefer_probe.py)
separates three questions that canonical RREF coordinates conflate:

1. whether a supplied column basis has width at most two;
2. whether every induced arity-at-most-three pivot relation shares a
   Schaefer closure class; and
3. whether either property can be found without enumerating all bases.

The probe uses an all-bases SAT control with 12 variables and rank 9 and an
all-bases UNSAT control with 15 variables and rank 12. Every one of their 136
and 237 column bases, respectively, has maximum pivot-free support three:
there is no width-two basis. Among the SAT bases, 84 share a 0-valid class,
6 share a 1-valid class, and 46 share no listed class. Among the UNSAT bases,
6 share bijunctive, 2 share dual-Horn plus bijunctive, 53 share Horn plus
bijunctive, 6 share Horn plus dual-Horn plus bijunctive, 10 share Horn plus
dual-Horn plus bijunctive plus affine, and 160 share no listed class. Direct
sums preserve this exact width-three behavior while nullity grows linearly. At
16 blocks the SAT family has 192 variables and nullity 48; the UNSAT family has
240 variables and nullity 48. The receipt derives the basis and relation
histograms by exact product/intersection laws rather than by pretending the
disconnected sum is a connected theorem.

A degree-preserving incidence 2-switch joins two SAT copies into a connected
24-variable bridge. Its exact rank is 19 and nullity is 5; all 7,344 column
bases have width three, four, or five, with histogram `3:4,374`,
`4:1,944`, `5:1,026`. No width-two basis exists. The canonical residual has
support histogram `1:7, 2:6, 3:6` and is jointly 0-valid. This is evidence
that connectivity does not force a width-two frame, not a classification of
connected growing-nullity families.

Run the probe, independent receipt checker, and existing cubic behavior tests
with:

```powershell
python growing_nullity_schaefer_probe.py
python verify_growing_nullity_schaefer_probe.py
python -m pytest test_cubic_kernel_decision.py -q
```

The raw receipt is `_diag/growing_nullity_schaefer_probe.json`. Zero-valid
basis existence remains the NP-complete semantic problem described above;
this census does not provide a basis-finding algorithm or settle width-two
frame recognition.

Run the analysis, independent verifier, and behavioral tests with:

```powershell
python run_cubic_kernel_analysis.py
python verify_cubic_kernel_analysis.py
python -m pytest test_cubic_kernel_decision.py -q
```

The SHA-256-bound receipt is `_diag/cubic_kernel_analysis.json`. Its 34
canonical cases contain 15 SAT and 19 UNSAT decisions. Seven UNSAT cases are
full rank, nine fail the divisibility condition, 15 ordinary cases are decided
by 2-SAT, one additional empty pivot relation is rejected before SCC search,
and two canonical support-three cases use exact kernel enumeration. The basis
supplement checks 1,298 column subsets, 588 actual bases, 588 basis-exchange
nodes, 5,885 exchange edges, and 316 dual small circuits across five controls.
It independently records three canonical-to-binary transitions, one SAT plus
one UNSAT matrix whose every basis has maximum support three, the
19-local-minimum strict-descent trap, and three independently reconstructed
zero-valid basis certificates for the SAT controls.

The three singular, divisibility-compatible UNSAT obstructions remain
deliberately distinct:

1. a one-dimensional kernel forces a zero coordinate;
2. a one-dimensional full-support kernel still misses `{-1,2}^n`; and
3. a three-dimensional kernel induces a genuinely ternary residual in its
   canonical coordinates with no satisfying alphabet vector.

Twelve connected switched-block families independently establish that graph
connectivity does not bound nullity. The largest SAT member has 96 variables
and nullity 33; the largest UNSAT member has 100 variables and nullity 32.
Both are decided without enumerating those free-coordinate assignments.

The analyzer also classifies every canonical arity-at-most-three pivot relation
by the standard Schaefer closures. The canonical support-three SAT residual is
jointly 0-valid. The canonical support-three UNSAT residual has no one class
shared by all its relations among 0-valid, 1-valid, Horn, dual-Horn,
bijunctive, and affine. These classifications are exact for those coordinates
but are not basis-invariant: both formulas have alternative binary-support
bases.

The independent verifier imports neither implementation nor runner. It
recomputes all 34 rational RREFs and relation closures, all four complete basis
censuses and optimized decisions, validates every certificate, and
exhaustively checks all 574 fixed-gauge cubic formulas through six variables.
Those formulas contain 521 SAT and 53 UNSAT instances and require 35,928
pointwise Boolean assignment checks; every kernel result agrees.

### Mixed direct-sum frame obstruction

[`run_mixed_schaefer_frame_obstruction.py`](run_mixed_schaefer_frame_obstruction.py)
joins one all-bases SAT control to one all-bases UNSAT control and then cuts the
join open with every degree-preserving cross-component incidence 2-switch. The
mixed direct sum on 27 variables has rank 21, nullity 6, and
`136 * 237 = 32,232` column bases, every one of width three: its frame optimum
is `omega = 3`, and none of the 32,232 bases shares a listed Schaefer class
because the component class histograms intersect in the empty class.

Each of the 36 left incidence edges switched against each of the 45 right edges
gives 1,620 pairwise distinct connected formulas with rank 22, nullity 5, and
UNSAT status. None admits a width-two dual frame, so each has `omega >= 3`. The
screen decides this exhaustively rather than by basis enumeration: a free set
`F` frames the dual in width two exactly when every ground-set element lies in
the span of at most two elements of `F`, so intersecting the subset bitsets of
all element-pair spans leaves exactly the free subsets whose internal pairs
cover the ground set. For all 1,620 switches that intersection is empty over all
`C(27,5) = 80,730` five-subsets, before any independence test.

The same coverage test at bound three then carries each switch to an exact
optimum. The free sets that survive the triple-coverage filter include an
independent one, and in every switch the first surviving free set already is,
so the exact width is measured after 1,620 candidate tests in total, one per
formula. Width is then read off by Gauss-Jordan elimination on the augmented
kernel-coordinate system, which exhibits a width-three witness for each switch
and settles `omega = 3` exactly. The exact width primitive reproduces the
project's canonical pivot-support width on the canonical free set, and the
bound-two and bound-three screens reproduce the width-three invariant of the
all-bases controls under their full basis censuses as well as the known width-two
minimum of the canonical support-three controls. Canonical width is not the
optimum: the canonical basis attains width three on only 864 switches, with
canonical-width histogram `3: 864, 4: 540, 5: 216`, so the other 756 have
canonical width four or five while their frame optimum is still three. Applied
to the mixed sum, the same filters also return no covering pair and an exact
width-three witness, and the survivor count of the triple-coverage filter there
equals its basis count of 32,232, matching the width-three census exactly.

Run the census, its independent verifier, and the retained cubic tests with:

```powershell
python run_mixed_schaefer_frame_obstruction.py
python verify_mixed_schaefer_frame_obstruction.py
python -m pytest test_cubic_kernel_decision.py -q
```

The SHA-256-bound receipt is `_diag/mixed_schaefer_frame_obstruction.json`. The
verifier imports neither the runner, the growing-nullity probe, nor the
cubic-kernel implementation. It rebuilds every component basis and Schaefer
class row, all 32,232 direct-sum rows, all 1,620 switches with their canonical
widths and both screens, revalidates every positive witness with its own exact
rational elimination, and enumerates every free subset of seven sampled switches
at both bounds with no coverage prefilter. All seven brute-force controls agree
at both bounds, and the mixed-formula screen agrees with both the full
enumeration and the basis census. This is a finite-family measurement: it does
not decide width-two frame recognition or classify unbounded connected cubic
families.


## Gauge-compatible Yang–Mills block fibre

[`run_yang_mills_gauge_fibre_probe.py`](run_yang_mills_gauge_fibre_probe.py)
applies the clause field to the representation-support problem for an open
$2\times2$ plaquette refinement. All eight outer links are fixed at spin
$1/2$. The four internal spokes and one four-valent recoupling channel are
encoded as exact $n=2j$ labels. Boundary and central Gauss constraints become
CNF clauses; assignments, implications, conflicts, learned clauses, and work
counters remain in one immutable field tensor for each source-declared query.

Run the probe with:

```powershell
python run_yang_mills_gauge_fibre_probe.py
```

The 227 fixed candidate classifications match a left-associated recurrence
that accumulates the same $SU(2)$ fusion rule. The fibre saturates once
$n_{\max}=2$ ($j_{\max}=1$) is admitted and has 14 candidate basis states:
one with no active internal spoke, six with two, four with three, and three
with four. The corresponding full electric-Casimir values, including the
eight fixed boundary links, are $6$, $10$, $12$, and $14$. A dedicated field
query returns UNSAT for the one-spoke condition, while an adjacent two-spoke
query returns a verified satisfying assignment. Representative SAT and UNSAT
states round-trip exactly through the field descriptor.

This is useful computational infrastructure because it gives the first
gauge-admissibility layer of the refined block a 14-state fixed-boundary basis
audit. It is not a closed Hamiltonian sector: plaquette multiplication changes
the outer representation sector, so neighboring fibres remain necessary. The
receipt has no source-independent reconstruction or global UNSAT-proof audit
and does not provide the magnetic matrix elements or $6j$ amplitudes.
Volume-uniform resolvent estimates, the thermodynamic limit, and the continuum
mass gap remain open.

## Technical paper and reproducibility bundle

[`prototype/`](prototype/README.md) contains the versioned technical paper,
its self-contained Python reference implementation, exact configuration,
tests, and reproducibility evidence:

- [`prototype/cassi-technical-paper.md`](prototype/cassi-technical-paper.md)
- [`prototype/paper-version.json`](prototype/paper-version.json)
- [`prototype/public-release-policy.json`](prototype/public-release-policy.json)

Large corpus inputs, checkpoints, diagnostics, and retained run artifacts are
local and Git-ignored. The version manifest binds their identities; the
distributable bundle excludes private corpora, trained checkpoints, and raw
historical evidence.

[`legacy/prototype/`](legacy/prototype/README.md) contains reference-only
experiments outside the active import closure.

## Repository boundaries

- Root modules and `prototype/` are independent implementations; neither is a
  fallback for the other.
- CassiCore and CassiCosmos are external integrations, not hidden Python
  dependencies.
- Generated files belong under `_diag/` or the declared artifact directories,
  not beside source modules.

Source code is licensed under Apache-2.0. The technical paper and its original
figure are licensed under CC BY 4.0; see `prototype/LICENSE-PAPER`.
