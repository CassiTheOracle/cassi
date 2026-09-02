# CassiFI

CassiFI is Cassi's Field Intelligence working prototype. It owns sensing,
bounded Qi-field evolution, trajectory language, grounded actions, spatial
relations, references, temporal prediction, causal explanation, and persistent
sessions. The canonical `CassiFieldAgent` adaptive object is one
`QiFieldState.field` tensor with shape `[4,55296,1]`. Each live runtime has one
field-owned adaptive state. The persistent provider packs its fixed Phi and
counterflow geometries through a hash-bound `SharedFieldLayout`; other runtime
profiles keep their declared geometry rather than resizing it implicitly.
Model-integrated Field Intelligence experiments remain explicit measurement
surfaces alongside the live prototype.

Run commands from `Cassi/` (the workspace root):

```powershell
python CassiFI/training/train_cassi_field_language.py
python CassiFI/training/train_cassi_grounded_language.py
python CassiFI/training/train_cassi_spatial_language.py
python CassiFI/training/train_cassi_reference_language.py
python CassiFI/training/train_cassi_temporal_language.py
python CassiFI/verification/verify_cassi_corpus_language.py
python CassiFI/verification/verify_cassi_native_runtime.py
python CassiFI/runtime/run_cassi_field_agent.py `
  --predict "turn your gaze right" `
  --instruction "turn your gaze right" `
  --explain-last `
  --order-last before
python CassiFI/runtime/run_cassi_chromatic_recall.py 37 134
python CassiFI/run_grounded_counterflow_deliberation.py
python CassiFI/run_bilateral_counterflow_scenario.py
python CassiFI/run_learned_relational_basis.py
python CassiFI/run_relational_stress_tests.py
python CassiFI/run_generative_abstraction.py
python CassiFI/run_text_abstraction_comparison.py
python CassiFI/run_general_task_gauntlet.py
python CassiFI/run_general_task_gauntlet.py --phase controls `
  --output CassiFI/artifacts/general-task-gauntlet/controls.json
```

## Live provider composition

`PersistentFieldProvider` exposes two counterflow operations over one versioned,
atomic native `QiFieldState` checkpoint. `POST /v1/counterflow/commit` accepts
only an exact observed before/after transition plus execution acknowledgment,
stream sequence, event identity, and authorization path. The event identity
must be lowercase 64-hex and exactly equal the observation ID; CassiCore remains
responsible for deriving that ID from its canonical journal event. A sequence
is accepted when it is strictly greater than the stored sequence for that
stream—gaps are valid because journal events without an exact transition create
no counterflow commit. The endpoint validates idempotency and replaces only the
counterflow slice of the shared field while preserving the Phi slice exactly.
`SharedFieldSessionStore` writes one field payload; the frame checksum, shared
layout/state hashes, and component-specific hashes protect it.

`POST /v1/counterflow/plan` loads that persisted snapshot and binds request
descriptors against the learned counterflow component without training it. The
planner accepts only exact 16-byte Mnemic addresses plus revision, byte-span,
semantic, mask, and Thalamus policy metadata; it does not accept arbitrary
latent vectors or invent transition laws. Request observations may describe
counterfactual branches, but they are never promoted into the checkpoint.

A settled request returns the versioned
`cassi.counterflow.derived-runtime.v2` receipt (`schema_version: 2`), both
component identities, the whole symbolic trajectory, deterministic abstention
evidence, and—when exact evidence and policy agree—an inert typed action proposal
with its Mnemic revision effects. Thalamus eligibility, action kind, authority,
reversibility, and authorization path remain fixed constraints. No tool executes,
and planning asserts that both canonical component hashes remain unchanged.

The same provider now exposes exact nonadaptive data ingress through
`POST /v1/ingress/append`, `/v1/ingress/read`, and `/v1/ingress/replay`.
Append accepts one fixed lossless codec, acquisition identity, the expected
journal head, and canonical base64 payload bytes; it journals before adapter
selection and returns packet, journal, view, and Mnemic-compatible exact
references. The opaque codec accepts every byte value. Read and replay verify
the content-addressed payload and hash chain across restart. The HTTP body bound
is derived from the configured journal budget, and capacity rejection occurs
before journal objects are written. These operations never mutate
`QiFieldState`, infer arbitrary-byte semantics, or bypass Thalamus policy:
semantic status is `unsupported` with reason `no_semantic_task`, while malformed
typed input remains journaled evidence with adapter status `unsupported`.

`run_grounded_counterflow_deliberation.py` is the provider-bound exact-edge
composition smoke. It commits six independently executed one-action fragments,
with no source action history, then presents them out of trajectory order. The
unchanged counterflow field settles the unseen three-action paths `left → up →
left` and `right → down → right` to their exact held-out revisions. Removing
either path's required middle edge makes the planner exhaust its search and
return no proposal. This establishes composition of exact compatible
effect-to-precondition edges; it does not claim transfer to renamed or unseen
state relations.

`run_bilateral_counterflow_scenario.py` also emits the standalone
`grounded_relational_transfer` receipt. Four independent one-action physical
samples per gaze direction train operator basins over the fixed relation frame
`[x, y, 1, x*y]`; action labels never enter those field features. From a
different world and episode at a pose absent from training, the unchanged field
composes `right → up → right` and execution reaches the exact held-out world
revision. Clearing the required `up` basin forces exhaustion. This result is
limited to interior affine pose transfer: it does not cover boundary clamping,
and it does not alter the provider's exact-address law or silently convert live
requests to relational descriptors.

`run_learned_relational_basis.py` replaces the fixed-frame choice with
field-selected relational basis discovery over four explicit candidates:
target-minus-self, absolute self, absolute target, and an identity control.
The controller derives closure, inverse, multi-step composition, nuisance
invariance, collision, and boundary evidence from raw executions; their
sufficient statistics and the grouped action operators live only in the same
`QiFieldState`. Action IDs select operator groups but never enter field features,
and the selected basis survives an exact checkpoint restart.

Sixteen independent one-action training executions and a disjoint selection set
choose target-minus-self. The frozen field then binds the interventional self
role and settles 32/32 unseen three-action worlds to their exact revisions,
including renamed entities and 16 reversed entity orders. Clearing the selected
basis evidence forces abstention; clearing a required operator forces
exhaustion. Four boundary-clamping controls remain unsupported
(mean residual `0.0615025` against tolerance `0.04`), so this is a finite,
transparent candidate-library result rather than unrestricted representation
learning. Hash-bound `cassi.counterflow.relation-atoms.v1` payloads are exact;
the live provider still rejects them instead of falling back from its
exact-address law.

`run_relational_stress_tests.py` measures the selected field beyond the original
interior fixture. Moving targets reach 24/24 exact revisions when both
intermediate relations are supplied, while one-intermediate and endpoint-only
requests reach 0/24; the stationary endpoint control also reaches 0/24, showing
that hidden action order is underdetermined rather than specifically defeated by
motion. Coordinate noise remains 16/16 exact through amplitude `0.01`, then
declines to 13, 9, 4, 1, and 0 exact revisions at amplitudes `0.015`, `0.02`,
`0.025`, `0.03`, and `0.06`.

Dynamic consequences identify a relevant object among moving distractors in
24/24 cases. When relevance is absent from otherwise indistinguishable objects,
the current residual rule makes 10/16 false confident choices and never
abstains. Balanced passive role probes produce 8 correct, 8 wrong, and 16
abstentions; one intervention improves this to 24/32 but fails the unseen
southwest orientation. A boundary-inclusive three-candidate field narrowly
selects distance/bearing, yet all candidates reach 0/12 exact boundary
compositions and distance/bearing produces 12 false settlements.

`cassi_generative_abstraction.py` implements the bounded typed field-program
generator specified in
[`designs/GENERATIVE-ABSTRACTION-DESIGN.md`](designs/GENERATIVE-ABSTRACTION-DESIGN.md).
Its 12-program typed grammar generates and field-selects role-position
subtraction, target temporal delta, and a guarded clamped boundary update.
Canonical tokens, grouped operators, every ranking statistic, regime support,
and confirmation counts occupy one float64 `QiFieldState`; `EACH_OBJECT`
expands every visible entity into an explicit hypothesis and retains
observationally equivalent identities.

`run_generative_abstraction.py` measures renamed and translated holdouts,
stationary and moving endpoint completion, deterministic sensor intervals,
dynamic and indistinguishable distractors, passive and interventional roles,
and 12 boundary compositions. Its universal-data arm journals 32 paired
JSON/raster experience events, settles 32/32 mixed held-out consequences,
transfers source-only JSON experience to 16/16 raster queries and source-only
raster experience to 16/16 JSON queries, and returns `ambiguous` for both
unidentified-role controls. Shuffled pairing, missing event identity,
hashes-without-structure, program-evidence, and operator controls all remove
support. Checkpoint bytes, field state, journal replay, restarted outputs, and
read-only inference remain exact.

The same entry point exercises exact text, Python syntax, audio, scientific
tensor, and opaque adapters. Those adapters round-trip and retain provenance,
but their unmeasured semantic tasks remain `unsupported`. The live provider
routes the same exact boundary contract without participating in the relational
inference scenario; no teacher or model participates.

`run_text_abstraction_comparison.py` applies the same bounded typed-program,
upward-fit/downward-outcome selection discipline to whole byte spans from the
four-source text corpus. On the exact 40-training/16-heldout split, none of the
10 surface programs explains natural continuation, so the field abstains on all
16 holdouts with no false settlement. Even a target-aware grammar oracle reaches
only 13.72% positional byte accuracy and 0/16 exact continuations. The older
next-symbol trajectory scores 30.13% teacher-forced heldout events but falls to
7.47% positional accuracy, 0/16 exact, and 16 false settlements under
autoregressive generation; the exact-context Phi harmonic field abstains on all
16. Positive heldout controls for ASCII uppercase, four-byte periodic replay,
and word reversal each reach 16/16 exact, confirming that the field transfers a
supported symbolic law but correctly rejects this small surface grammar as an
explanation of prose. Program ablation and shuffled correspondence exhaust,
checkpoint bytes replay exactly, and inference leaves the field unchanged.

The same run now lifts the corpus through a lossless deterministic
word/whitespace/punctuation symbolizer (112/112 spans round-trip exactly) and a
12-program role grammar over two surface clauses. Natural continuation remains
unsupported: the role field abstains on all 16 holdouts, while its target-aware
oracle reaches 9.90% positional byte accuracy, 29.44% mean edit similarity, and
0/16 exact continuations. Raising the representation therefore does not by
itself supply a prose law. Entity swap, predicate rebinding, and reversed
`because` discourse controls each transfer 16/16 exactly, including a second
16/16 pass after every held-out word identity is deterministically renamed.
Role-program ablation and shuffled outcomes exhaust selection; framed restart
is byte-exact and read-only inference is frozen. The entity and predicate names
here denote surface-position hypotheses, not inferred semantic parses.

`run_general_task_gauntlet.py` is the CPU-only orchestrator for the bounded
training gauntlet. Its reproduction phase calls the existing text-abstraction,
generative-abstraction, and universal-data-field entrypoints; their receipts
retain explicit `bounded_*_grammar` candidate-space labels and do not describe a
task-independent learner or general semantic acquisition. The reproduction
diagnostic is derived from each entrypoint's exact documented success result
rather than being declared independently.

The mixed curriculum updates one `[1,6606,1]` float64 field sequentially. The
current leave-one-source-out run removes WikiText from training, uses 30
remaining training episodes, and evaluates four held-out WikiText episodes.
The receipt keeps the two provenance questions separate:
`raw_receipt_source_overlap` lists all four sources shared by the original
offset-based corpus receipts, while `selected_split_source_overlap` is empty
after the leave-one-source-out filter. The untrained baseline exhausts all 15
regimes; after 13 sequential family updates, every supported byte-span and
surface-role family reaches 4/4 exact on holdout, with 1.0 minimum retained
accuracy and no measured interference. Three bounded compositions that were
not trained directly each reach 4/4 exact.

Shuffled outcomes exhaust, an induced ambiguity remains `ambiguous`, natural
continuation exhausts, a targeted lesion removes only the selected family,
malformed UTF-8 remains `unsupported`, 256 repeated updates stay finite at the
same fixed point, and checkpoint reload, journal restart replay, and read-only
inference are exact. The execution wrapper requires CPU state and installs
fail-closed sentinels for Qwen-provider imports, subprocesses, sockets, and
Torch optimizers. The successful receipt records zero attempts on every
forbidden surface rather than relying on declared counters.

The JSON, tensor, opaque, and text results are 13/13 exact only after a fixed
lossless projection back to the same prompt bytes. They establish codec
invariance, not learned cross-view transfer. The receipt therefore separates
`diagnostic_checks_passed = true` from `readiness_validated = false` and reports
`readiness.status = "not_ready"` with `learned_cross_view_transfer` as the
remaining missing capability. `--require-ready` returns exit code 2 while that
condition remains. Reproduction, curriculum, holdouts, retention, persistence,
and controls can be requested independently with `--phase`; each invocation
writes one JSON receipt, defaulting to
`artifacts/general-task-gauntlet/receipt.json`.

CassiCore supplies both endpoints from its transactional Mnemic journal. It
first predicts the held-out event from the prior shared field snapshot, then
commits the ordinary field observation, then commits the exact observed
counterflow consequence, and only then advances the local journal
acknowledgment. Restart recovery replays observed commits idempotently without
replanning an event already accepted by the provider. Stores, feedback
snapshots, deletes, unresolved actions, and unrelated journal entries create no
counterflow commit.

Completed and error action outcomes enter the same counterflow field component;
an error-supported winning basin abstains instead of proposing. Default-off
action-role, semantic-lineage-role, and inert multi-action views rewrite no
journal facts and create no learned side state. The read-only status endpoint
reports residuals against identity, support buckets, proposal margin, latency,
classified failures, abstention evidence, explicit journal verification, and
unresolved action episodes; any configured support threshold is shadow
calibration only.

The 16-byte wire address is the first 16 bytes of SHA-256 over the UTF-8 JSON
array `["cassicore.mnemic.counterflow-address.v1", record_id, revision,
start_byte, end_byte, semantic_kind]`, in exactly that order. These source fields
remain authoritative in every receipt; the address is only their deterministic
transport codec. Empty content retains its exact `[0, 0]` byte span and remains a
valid transition endpoint.

## Layout

- Core modules live at this directory's root: `cassi_qi_field.py`,
  `cassi_field_language.py`, `cassi_grounded_language.py`,
  `cassi_temporal_language.py`, `cassi_field_agent.py`,
  `cassi_bilateral_counterflow.py`, `cassi_counterflow_reasoner.py`,
  `cassi_counterflow_runtime.py`, and the organism, consciousness, world-model,
  provider, and Field Intelligence modules.
- `designs/` contains the architecture plans, contracts, preregistrations,
  and milestone records.
- `configs/` contains hash-bound runtime and curriculum configuration.
- `schemas/` contains the field schema registry.
- `training/` contains curriculum builders and checkpoint writers.
- `verification/` contains corpus, native-runtime, dependence, and displacement
  measurements.
- `tests/` contains executable behavior and contract tests.
- `runtime/` contains the persistent field-agent and chat entrypoints plus the
  adopted two-symbol chromatic recall runtime.
- `artifacts/` contains the canonical local checkpoints and receipts; it is
  ignored by Git. `_diag/` contains retained experimental receipts and is also
  ignored.
- `legacy/flow/` and `legacy/tests/` retain the historical W-flow experiment
  surfaces. They are not imported by the live Field Intelligence runtime.
- `legacy/native/` retains native Qwen boundary experiments and their
  contract tests; their receipts live in `artifacts/native/`.

## Canonical checkpoints

The active checkpoint chain is:

```text
artifacts/cassi-qi-corpus-language/field-state.pt
  -> artifacts/cassi-qi-grounded-language/field-state.pt
  -> artifacts/cassi-qi-spatial-language/field-state.pt
  -> artifacts/cassi-qi-reference-language/field-state.pt
  -> artifacts/cassi-qi-temporal-language/field-state.pt
```

The temporal checkpoint is the default for `CassiFieldAgent`; predictions do
not advance the world, and executed transitions persist their exact
predecessor, successor, and action in the live field register. A second process
can reopen the session and recover the explanation and before/after ordering.

The milestone measurements and source-level design are in
`designs/GROUNDED-LANGUAGE-PLAN.md`.
