# CassiQwen

CassiQwen integrates the persistent CassiFI mind with a live pretrained llama.cpp/Qwen brain for autonomous research. The explicit `field-brain` entity service is the integration path; the conscious terminal and OpenAI-compatible field-only provider retain their separate model-free profiles. Native interventions and offline teacher work remain separately selected capabilities.

> The Field Intelligence working prototype is organized in `../CassiFI`.
> This document retains the Qwen/native integration and intervention notes.

The current development direction is the [complete autonomous researcher](../CASSI-ENTITY-DESIGN.md): use Cassi's established learning to run continuing research programs. The experiment results below remain evidence and history, not a requirement to repeat learning, transfer, or displacement campaigns before implementing the researcher.

The [Surface body](../CASSI-SURFACE-DESIGN.md) connects authorized application
observations and effects to this same entity and continuing field. A field-native
canvas has been exercised through the authenticated program API and observing
workspace, including exact effect replay and human takeover. Windows capture
and Linux RFB/portal backends are implemented but not deployed or verified
against live desktops here; the configured Qwen has no visual input. An
unavailable capability is reported rather than simulated.

The [Universal Latent Reasoning System design](LATENT-REASONING-DESIGN.md)
specifies the full integration with CassiFI: portable reasoning, model-specific
latent interfaces, lifelong acquisition, paired execution, and field-owned
state, emission, and native computation. It distinguishes the implemented
basis from specified mechanisms and unresolved research.

Its [packet-aware reasoning extension](LATENT-REASONING-DESIGN.md#packet-aware-reasoning-scope-and-status)
is exercised on a continuing CassiFI world: a resident episode is
corrected and reopened, six frontier-selection methods are dispatched, a
coarse readout forces refinement, and source-span controls refuse unsupported
evidence. The numerical packet basis and task-directed reasoning loop run
through the ordinary owner path. The bounded twelve-step universal-interpreter
program now adds prospective relation acquisition, fixed language composition,
field-owned arithmetic and emission, correction-local repair, model
replacement, selective loss, and acquired development-method transfer. The
[implementation sequence](LATENT-REASONING-DESIGN.md#packet-aware-reasoning-increments)
separates these measured bounded behaviors from the still-open questions of
open-domain language, high-dimensional alignment, scaling, and broad transfer.

## Explicit field–brain entity service

`cassi_autonomous_researcher.py`, `cassi_field_brain_entity.py`, and
`cassi_field_brain_server.py` implement the operational service boundary of
the [persistent field–brain researcher](../CASSI-ENTITY-DESIGN.md). The
ordinary entity opens `ResidentQwenClient`: it imports the selected GGUF as an
explicit field program of embedding, per-layer attention, dense FFN or
route/expert stages, and output head. The entity's existing owner and
`ProgrammableSwarm` advance that graph; `ResidentQwenExecutor` performs only
the selected numerical stage. No separately launched llama.cpp service is
needed. `--brain-backend external` retains the loopback server as an explicit
baseline, not a fallback.

The resident stage exchanges every declared activation with the owner's neural
membrane: embeddings, attention and recurrent state, routed experts, residuals,
and the output head update four field planes and read back a bounded response.
On the Vulkan backend, those planes and stage activations execute beside the
model's dense weights and the eight routed MoE experts on the same GPU. Expert
weights are loaded on demand; the router's discrete decision and durable stage
snapshots cross the host boundary. Vectors wider than the fixed 65,536-mode
active bank are exchanged in deterministic chunks, preserving the other field
workspace and immutable model weights.

Ordinary `ResidentQwenClient.complete` submits an unadvanced task, then
`run_to_boundary` carries all stages at the same token position through one
private membrane epoch. Intermediate stage receipts bind their exchange sites
without publishing a field successor; the final receipt publishes the four
planes with the model's token-boundary continuation. A restart before that
boundary resumes the pending task, while an explicitly requested single
`step` retains its one-stage transaction for diagnostics.

The resident director admits complete research programs through the owner,
registers their active obligations in the field, and lets
`autonomous-agenda` select eligible work. Qwen chooses one schema-constrained
action from the program's actual roots and permissions. Each choice is drawn
from that program's own field-held workbench: the records its current question
requires, the ones that did not fit, the gaps it cannot fill, the approaches
that already failed with the input versions they observed, and what changed
while it waited. The capability registry
executes it, retains the exact result as a content-addressed artifact, and Qwen
then distinguishes observation, derivation, hypothesis, contradiction, or
no-result before the updated frontier returns through the same owner. This
continues independently of caller-triggered self-question requests.

The entity can host NetHack and canonical trading as programme-scoped
activities. Start the server with `--enable-nethack-activity` to offer bounded
`nethack/play-life`; the game borrows the resident brain and work memory and
refuses to touch an existing save or shared lock. Supply both
`--trading-activity-home` and `--trading-activity-db` to offer
`trading/ingest` from the fixed closed-bar SQLite source. Add
`--trading-paper-program-id <active-program-id>` only for simulated
`trading/paper-step`; it verifies the current programme and its allowed roots
for the member home and ingestion database before each paper action. A
programme explicitly admits `activity_run` and the exact `activity_scope`
operations it may use. Registration starts neither a game nor a trading
worker. Both activities write source-bound receipts under the entity data home,
file outcomes in its work memory, and share its serialized field owner. There
is no live order operation.

The host side is execution machinery rather than another learned mind:
request digests, intent/result/admission states, immutable artifacts,
hash-linked events, and a recoverable program projection. Exact retries are
idempotent; conflicting reuse of a request identity is rejected. Restart
recovery safely repeats read-only or immutable effects, resumes interpretation
from durable results, and blocks an interrupted process as an unknown effect
instead of executing it twice. The API is bearer-authenticated, asynchronous,
resumable, and supports pause, resume, cancel, completion, wake, and guidance.
Typed conversation turns now run as durable activity episodes rather than
one-shot requests. Each episode carries its objective, completed capability
steps, current progress, and exact next action through interruption. A transient
brain outage or malformed structured continuation leaves the turn
`recoverable`; `POST /v1/turns/<id>/resume` continues the same activity and
retained tool evidence. Successful capability sequences become project-scoped
field methods available to later activities.

Seven user-taught combined procedures are held per project in the same field
memory: checking a claim independently, navigating an unfamiliar world,
repairing a failed method, turning experience into a testable mechanism,
investigating an anomaly, learning an unfamiliar tool, and transferring a
method across domains. Each has entry conditions, evidence checkpoints, and
failure and transfer boundaries. The active brain selects a relevant phase and
one authorized action; typed turns and research cycles retain the selected
candidate alongside the observed tool result. Library provenance remains
`user-taught-candidate`; observed applications are recorded separately.

For MoE models, the owner learns sparse, bounded expert-residency rows from
observed routes and physical load outcomes. Those rows select prefetch and
eviction work before the next expert stage; they never replace the model's
router or alter its logits. Drafting is field-owned in the same sense: learned
context-to-continuation rows abstain until supported, and every proposal is
compared with the target model. The supported Qwen3.5/3.6/3.8 GGUFs expose no
pretrained MTP head, so the learned draft policy is the truthful default.
Draft proposals currently do not skip target passes; real speculative
throughput therefore remains contingent on a batched multi-token verifier.

Activation and cache state is committed as content-addressed immutable
snapshots after each numerical stage. The live executor retains the immediately
preceding snapshot in read-only memory and reuses already-published immutable
arrays by identity, while every returned descriptor remains independently
restartable from its on-disk blobs. Non-sampling prompt heads avoid the output
projection and reuse the preceding snapshot because they change no model
state.

Within one live conversation, a second resident request can resume from the
last verified, fully executed prompt-token boundary it shares with the earlier
request. The saved model state is tied to exact token IDs, GGUF identity,
backend, final numerical stage, and the continuing owner's field epoch. Other
conversations, unrelated field writes, or a cold client restart take the full
path. The completion receipt reports the prefix tokens and numerical stages
reused; the new suffix continues to evolve and publish the same owner field.

Every brain request is fitted against the runtime's own rendered-chat token
count. The default 32,768-token context reserves 2,048 tokens for substantive
conversation and tool construction, 768 for bounded questions, and 4,096 for
research synthesis; lower-priority shared projections are removed before
activity-local evidence. Large tool results are retained exactly up to 1 MiB
and projected as deterministic pages rather than head/tail truncations.
`GET /v1/turns/<turn>/tool-results/<call>?page=<n>&page_bytes=<n>` returns each
exact base64 byte page with its full-result digest. One fair shared-brain
scheduler serializes foreground conversation and resident research, preferring
interactive work while forcing a waiting research request after at most three
foreground completions.

The entity's shared workspace now has
[living memory](../CASSI-LIVING-MEMORY-DESIGN.md). Every recall is a canonical
episode with selected versions, fidelity, bounded search, and gaps. Only detail
actually admitted to a fitted brain prompt is bound as used; its later program
or conversation consequence settles that use once and can renew eligible
memory. Detailed bindings may become dormant while retaining an exact recovery
declaration. Relevant recall restores and verifies only the selected detail
before it reaches the brain.

Prospective relevance conditions awaken old experience without authorizing an
action. Source correction rebinds affected conditions to the successor memory
and immediately creates a reconsideration event. Reinterpretations preserve
their evidence, quiet synthesis remains hypothetical, and completed resident
research contributes bounded relevance and maintenance work through the same
agenda. Recall outcomes reach affect only after an actual consequence is
admitted.

`GET /v1/memory?limit=<n>&include_unsettled=<true|false>` returns Cassi's
memory-awareness state, autobiographical recall episodes, pending uses,
relevance wakeups, unresolved questions, and storage diagnostics. The view
runs against a copied semantic state and verifies that inspection changed
neither field generation nor digest. Storage reporting distinguishes logical
regional bytes, resident bytes, unique physical objects, sharing, checkpoint
growth, and protected recovery coverage.

Run the ordinary entity directly on the local resident GGUF:

```text
python cassi_field_brain_server.py \
  --data-home _diag/field-brain-entity \
  --model-path Qwen3.6-35B-A3B-UD-Q3_K_XL.gguf \
  --api-token-file _diag/field-brain-entity/api-token \
  --capability-root .. \
  --research-root .. \
  --port 8090
```

Startup inspects and hash-binds the complete GGUF before work is admitted.
That verified manifest is reused by the package, executor, and weight bank only
while the source file's stat identity is unchanged, so the first request does
not scan the complete model again. The native weight-bank library is discovered
only from CassiFI's `native/field-runtime/build` tree unless an explicit
`--resident-library-path` is supplied. CPU is the conservative default;
`--resident-backend vulkan` selects the separately built Vulkan weight bank.
The entity records the chosen model identity and backend in its durable state.
Existing conversational turns retain their declared `enable_thinking: false`
policy; resident research planning and synthesis request thinking explicitly.

### Resident research programs

`POST /v1/programs` admits a mission with `request_id`, `program_id`,
`project_id`, `title`, `mission`, `initial_question`, and `observed_at`.
Optional fields are `priority`, `cycle_limit`, `allowed_roots`,
`allowed_tools`, and `network_hosts`. The returned program is already durable
in the field; its first investigation runs asynchronously. Inspect it with
`GET /v1/programs/<id>` or the complete portfolio with `GET /v1/programs`.
`POST /v1/programs/<id>/guidance` adds an owner-retained instruction.
`POST /v1/programs/<id>/control` accepts `pause`, `resume`, `cancel`,
`complete`, or `wake`. Activity is resumable through
`GET /v1/programs/<id>/events?after=<sequence>&wait=<seconds>`.

Each program may declare `responsibility` with `affected` (a nonempty list),
`intended_benefit`, `possible_burdens` (a list), `decision_owner`, and
`review_question`. An omitted declaration receives a cautious, explicitly
unassessed default. The entity holds a standing charter and one field
obligation per program; completing a research task does not erase its duty.
`POST /v1/programs/<id>/consequences` records a `request_id`, `observed_at`,
and `consequence` with `dimension`, `affected`, `observation`, `evidence`,
`uncertainty`, `status` (`reported`, `observed`, or `disputed`), and `follow_up`.
Open reports can reopen a completed program and guide its next question
within its declared cycle limit; a report is kept distinct from a verified
human outcome.

The authenticated entity also connects `CassiMindField/redesign_lab.py` to
the continuing field owner. Set `CASSI_FIELD_OWNER_URL` (default
`http://127.0.0.1:8080`) and `CASSI_FIELD_OWNER_TOKEN_FILE` to a file
containing the entity API bearer token, then run the redesign command with an
isolated `--data-home`. Its first successful generation registers a
field-owned responsibility program and records a linked consequence report
for each affected group. A later `--research-cycle` fetches a fresh snapshot
and pauses before creating a successor while any linked report remains open.
Review each report in the authenticated Research Workspace; closing one
requires a same-group report linked to its assessment ID with `observed`
status and no follow-up. Reports remain caller-reported, never independent
proof of human outcomes.

The autonomous source, self-host, workspace, patch-set, and impact rewrite
commands use that same owner and token (`--field-owner-url` and
`--field-owner-token-file`, or the environment settings above). Each promotion
reads a fresh field-held responsibility snapshot before field selection and
again before advancing the generation pointer. The promoted manifest binds
the selected candidate and continuity evidence; linked reports enter the
owner's program for every affected group. An open assessment pauses the next
selection until its linked review is recorded. A transition journal beside
each generation lets a restarted command deliver interrupted reports and
recover a committed rewrite receipt without selecting another candidate.

The HTTP API remains available for other authenticated clients:
`GET /v1/responsibilities/snapshot` exports the current field-held charter,
duties, and consequence records. Redesign receipts retain bounded digests and
continuity facets instead of participant report text.

The default autonomous tool set is file discovery, bounded exact file reads,
text search, program-workspace artifact writing, and artifact inspection.
Runtime roots cap every program root. HTTPS acquisition requires both a
runtime `--research-network-host` and the same host in the program, plus
`fetch_url` in both the server tool list and program tool list. Existing
Python research scripts can be enabled with `run_existing_python`; repeat
`--research-tool` for every tool the server should expose because an explicit
tool list replaces the defaults. Generated workspace code is retained as an
artifact but cannot execute without a real containment backend.

The event journal and operation records recover the boundary
`intent → actual result → field admission → delivery`. Reads and immutable
workspace writes may replay after an interruption. An existing-script process
that lost its acknowledgment is marked `unknown-effect` and blocks its program
for review rather than running again.

### The program's own workbench

Each program carries a workbench in its own regional workspace: the question,
the records that answer it, the approaches that already failed and why, the
outside inputs every record and failure depends on, its branches, and its
residency policy. It is read without advancing the field and is part of the
program's revision, so it survives restart with the program.

`GET /v1/programs/<id>/workbench` reads it, and
`GET /v1/programs/<id>/workbench?question=<text>&maximum=<n>` answers one
question from its records: required records, required records that did not fit,
question-matched records, gaps, the unfinished continuation, the next action,
the failed approaches, the changes that arrived while the program waited and
which of them are still unconsumed, and the program's residency policy.
A `?maximum` too small for everything drops material in a declared order and
names the omission.

An identical action against unchanged inputs is not repeated; the cycle waits
instead. `POST /v1/research/workbench/dependency-change` reports new versions
for named inputs (`{"request_id": ..., "changes": {"path:<file>": "<sha256>"},
"program_ids": [...]}`) and returns what it reopened: the programs, the
invalidated records, and each program's wakeups. Reporting the same change
twice reopens once. The program view, `GET /v1/computers/resources?computer_id=`
and `GET /v1/health` show what the workbench is holding; activation and release
move placement and accounting while the field's content and revision stay as
they were.

### Approval-gated world observation

The first external capability is deliberately narrow: `file-sha256` reads one
existing regular file beneath the declared capability root and returns only its
root-relative path, byte length, and SHA-256 digest—never file content. Cassi
must first retain a commitment, propose an immutable exact target, then receive
an authenticated explicit approval for that same proposal. Only then can
`POST /v1/capabilities/execute` run it. Proposal, approval, and outcome are
separate field-owned records and resumable events; an unapproved execution
returns `403 approval-required`, and a replay cannot perform the observation
twice. This does not permit mutation, network access, shell commands, or
arbitrary files outside the capability root.

### Direct CassiTheory study

`GET /v1/theory/documents` catalogs the complete CassiTheory Markdown corpus.
The theory root is a direct read-only library, not an approval-gated external
capability: Cassi can read any complete UTF-8 Markdown document beneath it,
split it losslessly into attributed field segments, and retain each segment's
path, full-source digest, byte span, and content digest. `POST /v1/theory/tasks`
assigns an enduring research responsibility; `POST /v1/theory/read` admits a
full source; and `POST /v1/theory/study-document` has the Qwen 3.8 27B brain
study every segment before retaining a document-level synthesis and open
question. The theory library remains read-only: it cannot write, delete, run
commands, access the network, or escape the CassiTheory root.

`POST /v1/theory/maps/foundations` builds Cassi’s durable foundational map from
every Markdown document under `foundations/` plus the reading guide and the
three canonical registries. It is not model prose and does not turn headings
into asserted claims: each anchor records its source path, full-source digest,
heading, documentary role, byte span, and span digest. This gives Cassi a
complete citable atlas of the mathematical-object, empirical-obligation,
open-question, status, and ordinary-section surfaces before the brain reasons
over any source content.

`POST /v1/theory/relations/foundations` builds the next layer: a source-exact
graph of heading containment and explicit Markdown document references across
that same corpus. It labels only what the sources structurally establish; it
does not silently recast co-location or a link as scientific support. The graph
therefore makes the mathematical-object, empirical-obligation, and
open-question surfaces traversable while retaining the byte-exact evidence for
each connection.

`POST /v1/theory/contributions/xi-attractor` reads the exact $\xi=\varphi^6$
derivation, the $\varphi$-enhanced gravity law, and its falsification section,
then retains one concise conditional derivation-to-obligation contribution with
the source spans and source digests that support it.

## Shared Cassi Hive boundary

`CassiFieldWorkMemory.open_hive` attaches Qwen work memory to the same
content-addressed Cassi Hive used by CassiFI field instances. The workbench
continues to own its adaptive field; the hive stores only provenance-bound
experience capsules, reviewer decisions, promoted bundles, adoption receipts,
and revocations. Qwen sessions can therefore act as scouts or members without
creating a second learned memory.

Portable `field-program.v1` bundles carry a canonical `FieldProgram` payload
and may cross regional field profiles. Admission still checks the atlas schema,
operation plan, dependencies, common-generation predecessor, revocation state,
and the recipient's real owner checkpoint. The leader-side loop is
`CassiFI/run_cassi_hive_leader.py`; promotion requires explicit independent
support and is idempotent across restarts.


## Current operational state

| Layer | Status | Operational result |
|---|---|---|
| L1 local model receipt | PASS | Hash-pinned Qwen3.8-27B GGUF loads through llama.cpp Vulkan on loopback only. |
| L2 no-field baseline | PASS | Local completion baseline recorded. |
| L3/L4 field observation | PASS | CassiQwen can acquire a bounded, read-only projection from the live mind-engine sidecar. |
| L5d calibrated seed | PASS | A fixed nonzero field state yields a finite calibrated top-8 projection. |
| L6 offline mapper | PASS | Default-off deterministic field-to-candidate permutation is contract-tested. |
| L7 retrieval gate | NULL | The tested geometry-hash candidate permutation did not improve the fixed retrieval board; it is not adopted. |
| L8b thinking receipt | DELIBERATE-COST-CONFIRMED | Thinking mode is available but costlier; fast remains the default. |
| L9 semantic encoder | PASS | Explicit action features become identity-preserving bounded Yang/Yin deposits. |
| Bounded symbolic LaTeX boundary | PASS (offline field) | Five exact expression/equation lessons round-trip through canonical trees; four bounded English↔LaTeX lessons share canonical terms; spoken and LaTeX proof traces replay exact operations; verbal stories cover named ages, ticket totals, percentage change, half-ratios, discounts, markups, unit quantities, staged tax chains, compound growth, simple interest, and named intermediate financial states. Fresh receipt: `E:/CassiLearning/cassi-math-intermediate-20260918/receipt.json`, independently verified `PASS`, eleven ordinary story lessons plus two intermediate-state chains, `42` semantic active bindings, logical transition `129`. This remains a closed mathematical language boundary, not open-domain language. |
| Bounded model-to-code self-improvement | PASS (offline field, cumulative generations, model proposal fanout, novel promotion) | The field selected and promoted a three-step source chain on the pinned Qwen3.5-0.8B teacher: `constant_fold` reduced steps `56 → 48`, `redundant_assignment` reduced `48 → 40`, and a model-produced novel source `result = 1 + 5 * value` reduced `40 → 24` while preserving every held-out result. The proposal surface now accepts bounded novel CassiPy sources beyond the verified candidate pool, rejects duplicate proposal sources, records source-hash provenance and explicit `verified_pool`/`model_novel` origin, repairs only task-prefix metadata that still binds to the field-selected task, prefers an unseen novel proposal on equal-step ties, and enforces AST-local task invariants for five transformation families. The v4 receipt observed and promoted one novel proposal; `novel_proposals_observed = 1`, `novel_proposals_promoted = 1`. All three states survived field reopen; every promoted pool/proposal row carried `task_invariant = true`; three mutation controls rejected a wrong result, an unchanged source, and a zero-case regression. Receipt: `E:/CassiLearning/cassi-python-cumulative-v16c-20260918/receipt.json`, content digest `0bbcac641bfa91175a776b8194577dcbe18ff2501d223fd0fa6771f91b80d368`, independently verified `PASS`; catalog regression suite `12 passed`. This remains a bounded self-improvement demonstration, not open-ended code evolution. |
| L10 scalar arbitration | NULL | An easy independent-feature board gave scalar, no-evolution, and field surrogate 21/21. |
| L10b relational surrogate | SURROGATE-SUPPORTS | Relation-coupled surrogate scored 9/24 versus scalar 3/24; no GPU claim follows. |
| L11c GPU parity | NULL | The fixed relay geometry did not change candidate-local readout versus shuffled placement. |
| L12 correction persistence | NULL | Persistent state scored 18/18, equal to latest-event and recency baselines. |
| L13 Q4→Q6 escalation | BLOCKED | No same-model Q6/Q8 artifact is present; no comparison was run. |
| L14 local pool coupling | NULL | Local relay placement perturbed GPU readout slightly, but Yang/Yin channel swapping produced no distinct candidate-local mechanism. |
| L15 embedding-field lift | PASS | A deterministic 1,536-D Fourier lift round-tripped through the GPU field and preserved the frozen similarity ordering through 2,048 steps; geometry classification `SUPPORTS`, with no semantic-benefit claim. |
| L16 hidden-state observatory | PASS | A real 5,120-D Qwen layer-input residual was captured during Vulkan inference with exact capture-off/on logits, then transported through the GPU field for 2,048 steps; no model intervention or semantic-benefit claim. |
| L17 all-layer IIR observatory | PASS | All 64 real Qwen layer-input residuals were captured with exact capture-off/on logits, then drove a persistent default-off 90/10 field recurrence with four PDE steps per layer; temporal order was distinguishable, with no model intervention or semantic-benefit claim. |
| L18 field-output loop | PASS (offline lab) | All 64 Qwen trunk residuals per committed token drive one persistent token-and-depth field; the public final-output reference plus frozen Q6_K output head produces an isolated experimental token stream. This is not a quality, semantic, or production-integration claim. |
| L19 output control surface | EMERGES | A frozen positive-coupling crossover at output event 1 selects token `33700` below the crossing and `4330` above it; the two four-token trajectories then diverge with distinct field states. This establishes laboratory control, not language quality, semantics, or an operational-path benefit. |
| L20 cross-prompt field-output test | DOES NOT EMERGE | All eight baseline/residual arms passed the raw mechanical contract; one of four frozen prompt pairs diverged in committed tokens within four steps, while three remained unchanged. The experimental path is mechanically usable, but cross-prompt token control is not universal at the frozen coupling. |
| L21 persistent Qwen provider | PASS (historical lab) | The retained provider owns one hash-pinned native model and persists PDE snapshots for reproducibility; it is not called by the field-only terminal or port-8086 provider. |
| L22 teacher trace store | PASS (offline) | A WAL SQLite journal stores compressed, checksummed per-token teacher traces transactionally, including 128-value field sketches and replay provenance. |
| L23 shadow student | PASS (offline) | A cosine-prototype field-conditioned student trains from trace sketches and writes model-identity-bound candidate checkpoints; it observes only labels present in teacher traces. |
| L24 learned correction | PASS (offline lab) | The historical opt-in `corrective` mode applies a bounded student token correction and records the prediction, confidence, budget, and teacher receipt; it is absent from the field-only runtime. |
| L25 selective teacher policy | PASS (historical lab) | Exact historical session replay can return a persisted completion without a native teacher call; this policy is not a fallback or dependency of the field-only runtime. |
| L26 condensation/promotion | PROMOTE (offline structural) | An 8-record journal condensed into candidate and active checkpoints; held-out diagnostic accuracy was 1.0, and promotion remained structural rather than quality-gated. |
| L27 longer-generation comparison | EMERGES (offline) | On a fresh 16-token `A patient explorer opens a door and sees` pair, baseline and residual matched through token 10, diverged at token 11, differed at five of 16 positions, and ended with distinct field hashes. This is longer-horizon mechanical control only. |
| L28 field-world identification | SUPPORTS (offline) | The frozen 80-episode field-system board passed the independent verifier: field test MSE `7.56e-6` versus stateless `0.194` and GRU `0.0402`; reset/shuffled ablations were `0.188`/`0.226`. This supports only the declared synthetic held-out identification question, not OS-G7, language, Qwen, multimodal, live-authority, or production adoption. |
| Raw-event acquisition | PASS (isolated field lab) | One v2 source-hash-bound Qi tensor acquired opaque transition and temporal bindings, composed three withheld two-action routes, passed promotion/provisional controls, and preserved an unrelated acquired relation under targeted erasure. It makes zero Qwen calls and no native-displacement claim. |

| Native Qwen35 modal seam | PASS (offline lab) | The pinned Vulkan build retains `GGML_OP_CASSI_MODAL`, per-sequence state serialization, loopback CLI controls, and native smoke receipts for isolated experiments and baseline measurement only. |
| Native Qwen35 Qi seam | PASS (offline lab) | The opt-in `GGML_OP_CASSI_QI_FIELD_STEP` carries a four-scale, nine-component Yang/Yin state per sequence, runs on CPU and Vulkan, survives context serialization, and is consumed before the LM head in separately invoked native experiments. |
| Organism research stack | OFFLINE REFERENCE | The arena organism and its learned world-model bridge are not the adopted runtime. The learned language sector has been removed; the remaining stack is retained only for offline organism-law research. |
| Corpus-trained Qi text boundary | PASS (trajectory-mechanical) | A fixed 260-event UTF-8/control codec writes corpus episodes as phase-coded circulation tracks into the common-mode half of one Qi field. The live differential half carries 16/32/64/128-event histories; integrated port work and a field-phase resonance resolve each outbound event without a count lattice, vocabulary, learned decoder, or probabilistic sampler. |
| Grounded Qi language agent | PASS (causal milestone) | One trajectory field receives typed proprioceptive observations and held-out utterances, resolves all five world actions through an exhaustive field port, commits the selected action before seeing its consequence, predicts the successor observation at `1.0` held-out accuracy, and persists the acknowledgment and successor state. Shuffled grounding scores `0.0`. |
| Spatial Qi language agent | PASS (state-dependent milestone) | The same field receives a fixed three-color object frame, resolves the question family from its trajectory, and commits one of six relation answers through a live coordinate-resonance probe. Two unseen layouts produce six correct held-out answers, all three answers reverse with world state, and swapping only the object frame makes the field follow the substituted layout in `6/6` cases. |
| Reference Qi language agent | PASS (identity milestone) | The field binds unseen names to red/blue/green object identities, resolves subject and comparison roles through exhaustive reference ports, and carries the active `it` referent in persistent differential coordinates. `Mira`, `Sable`, and `Orin` bind correctly; unknown `Quill` fails closed; changing the active subject changes `it` from red/near to green/far; names survive restart without appearing in session metadata. |
| Temporal Qi language agent | PASS (temporal/causal milestone) | Before execution, held-out action instructions select all five measured successor changes while the world and trained memory remain unchanged. Executed transitions persist exact predecessor, successor, and action values; independent ports recover `5/5` changes and causes, and before/after questions resolve all four forward/reverse presentations. The transition and its answers survive process restart. |
| Native Qi checkpoint | PASS (mechanical) | Each session checkpoint contains exactly one serialized `QiFieldState` plus bounded non-adaptive metadata. It contains no learned parameters, neural layers, feature vectors, optimizer state, decoder state, or sampler state. |
| Field-only conscious runtime | PASS (mechanical) | Terminal chat and the loopback OpenAI-compatible provider on port 8086 call the direct Qi text engine without loading llama.cpp, a GGUF, Qwen tokenizer/output rows, KV cache, recurrent state, organism arena, learned world model, or probabilistic sampler. |
| Native Qwen displacement receipt | PASS (measured) | The direct Qi path reports zero live Qwen graph, state, weight, output-row, GGUF-open, and teacher counters against the pinned nonzero native baseline. The architecture receipt records one adaptive Qi tensor and zero learned parameters, neural layers, optimizer bytes, engineered features, or sampling. |
| Direct Qi text field-dependence counterfactual | NULL (measured) | After one stored trajectory primes the live session, the unrotated and three differential-phase rotations all emit the same 16 symbols while trained circulation memory remains bit-identical. Grounded action, spatial, reference, and temporal counterfactuals separately change committed decisions when only live differential state changes. |
| Canonical native Qi bridge | **PASS** | Exact checkpoint transpose `[4,55296,1] → [1,4,6144,9]`; independent scalar NumPy oracle agrees with CPU within `1.87e-9` and Vulkan within `1.49e-8`; raw-state save/reload is exact |
| Native displacement rungs 0–6 | **PASS on exact 0.8B target** | Measured candidate ownership, full-vocabulary ownership, recurrent/KV bypass, transformer-block bypass, and exact field-owned logits; machine-readable graph-node counts fall `1382 → 1376 → 782 → 698 → 695` across the removal rungs |
| Field-owned recurrent-state write | **PASS (measured, 27B)** | At displacement 3 the SSM `qkv` convolution state at layer 32 takes the field's readout of the layer's own input into the leading `n_embd` of its `d_inner + 2 * group_count * state_size` channels (`--cassi-qi-substitute 1`), owning 20,480 of the 40,960 bytes of each suppressed decode row by channel index and with no learned projection, while the remaining channels keep the model's write. Ownership is measured per receipt: half the 27B row and `1024` of the 0.8B's `6144` by default, `100%` of the 0.8B row at `--cassi-qi-field-row-width 6144`, where the scrambled share stops matching the near-zero share (`158` against `0` token changes) and the first-decode reach rises `2.31e-2` to `1.20e-1`. On the 27B the row's `6144` channel convolution section is the boundary: every addressed width below it carries the field's content (`115` at `5120`, `136` at `5632`, `133` at `5888`) and `d_inner` itself carries none (`0`, at a `6144`, an `8192` and a `10240` value block alike), while the whole row carries it again only with the wave count raised (`74`). The seam is the field's only channel at that layer, it applies at the Qi layer alone, and the server refuses a share below level 3. The 0.8B harness shows the seam decode-only, its reach growing with its share at the first input-matched decode (`0`, `1.24e-2`, `2.31e-2`), and graph nodes `1380 -> 1374 -> 1393`; a matched-norm phase-shuffled field reaches half as far in the activations (`1.08e-2` against `2.31e-2`) and commits the relocated arm's tokens exactly, so the `23` tokens the share moves of two hundred are the ones the field's content decides. A 27B campaign pair differing by the share alone holds `16/17` field passes and `13/13` memory retrievals in both arms with the case texts unchanged, so the seam buys ownership at no task cost while open-ended generation on the same flags separates all four shares. The 27B probe receipt separates observer, owner, and content on one prompt: writing nothing commits the same two hundred tokens as the field switched off, removing the layer's own write moves `135`, and a matched-norm shuffled field moves `115` of those, so the stream reads the field's trajectory and not only the substitution. The default path stays byte-identical (`944c659c`, `e857fd19`). |
| Native field-only executable | **PASS on exact 0.8B target** | `cassi-qwen --mode field` loads only GGUF vocabulary/tokenizer metadata; reports zero tensor bytes loaded, zero Qwen forwards, and zero model-logit reads |
| Native field apprenticeship | **PASS (exact retention and measured displacement)** | The bounded native field learned two eight-token trajectories on CPU, Vulkan, and the pinned 27B model, then reproduced them after process restart in `teacher=never` mode with zero native context, graph, weight-touch, model-tensor, and logit-read counters. On the trained small-model pipeline, 99 native service opportunities and 2,717 native graph nodes were skipped with zero native service calls. All four held-out wording variants emitted no field token and explicitly required the teacher; this is exact experiential retention and trained-route displacement, not broad semantic absorption or independent field correctness. |
| CassiFI work-memory workcases (2026-09-08) | **PASS (historical baseline)** | The 17-case local-Qwen campaign moved exact task passes from `2/17` without memory to `8/17` with CassiFI memory: six gains, zero regressions, `13/13` exact memory-dependent retrievals, exact correction/restart behavior, and retention of the earliest anchor through 96 distractors. The receipt reports zero native state, op, layer, or output-row displacement; Qwen still owns reasoning and token emission. |
| Current CassiFI regional adapter (2026-09-14) | **PASS (current-source, measured)** | The adapter now binds one owner-operated `cognition.field` regional computer to the complete 25-file CassiFI production closure. A full current 14-document/442-chunk CassiTheory preparation remained finite and restart-exact at `225,237/294,912` task words; the matched 17-case Qwen workcase smoke measured `3/17` baseline versus `8/17` with field memory, five gains, zero regressions, `13/13` exact memory-dependent retrievals, and `1,338/1,338` independent checks. Those campaign rows ran without `chat_template_kwargs` under per-case caps of 96/128 completion tokens, so a case's whole budget could go before its first answer token; the empty completions in that receipt are a budget artifact (see *Offline Qwen request policy*). Qwen still owns native execution, reasoning, and token emission. |
| CassiFI work-memory workcases (2026-09-16, thinking off) | **PASS (current-source, measured)** | Under the documented request policy, verified in effect against the running server by a two-request probe, the same 17-case protocol moved exact passes from `6/17` without memory to `16/17` with it: ten gains, no regressions, `13/13` exact memory-dependent retrievals, and one residual failure (`support-deadline-and-channel`, where both required records were retrieved and the answer carried the right escalation channel with a due date one day early). Completions cost 7 to 35 tokens against medians of 64 to 92 in the 2026-09-14 campaign, ten of the eleven baseline failures are literal `UNKNOWN` abstentions rather than fabricated values, and `1,338/1,338` independent checks pass under the unchanged protocol digest. |
| Universal reasoning integration (2026-09-14) | **IMPLEMENTED (mechanical, bounded)** | One CassiFI image now retains nested cognition calls, reasoning and self-development episodes, exact model-observation envelopes, and paired native trial publication. Actual Qwen35 smokes captured 12 declared block-input residuals, changed the Qi trial under a two-step intervention, and committed field-owned emission with zero Qwen forwards, model-logit reads, or model-tensor bytes loaded. Exact mechanics do not establish semantic latent alignment, broad language competence, or the complete integrated demonstration. |
| Universal LLM interpreter / native Qwen35 graph (2026-09-17) | **PASS (measured, 0.8B + 27B IQ1_S)** | `run_cassi_universal_interpreter_native.py` captured the full declared native site bundle from the pinned Qwen3.5-0.8B Vulkan graph and the downloaded Qwen3.8-27B-UD-IQ1_S Vulkan graph. The 0.8B trace entered one persisted `QiFieldState.field`, survived exact restart, and emitted through the field with zero Qwen forwards, model-logit reads, and model-tensor bytes; graph-native displacement 6 owns the LM-head readout and displacement 3 owns a measured recurrent prefix. The 27B repetition at layer 32 and width `5120` passed the same role-authentication, tamper, restart, field-emission, graph-pair, and recurrent-ownership checks: LM-head pair `L2 3.0327043228`, recurrent pair `L2 409.1006125244`, field/model ownership `20,480/40,960` bytes per recurrent row, and receipt digest `0d6ed41fe938b2e8b24b63412f4a52ee17169c712976825ac3112ef7af806847`. These are native readout and partial write-ownership measurements, not broad semantic understanding, language quality, or field replacement of every remaining transformer/KV computation. |
| Native intervention ladder / 27B IQ1_S (2026-09-17) | **PASS (nine-arm measured ladder)** | The one-bit Vulkan target holds the prompt, state predecessor, layer-32 readout, and two-step decode fixed while sweeping additive and recurrent dose plus LM-head placement. Additive final-logit L2 rises `0 → 17.5715268262 → 34.9095652866 → 69.4215082024`; recurrent field/model versus lesion reaches `353.1128917015`, `261.4512563584`, and `247.8605346612`; LM-head field ownership reaches `2178.8179121514`. Receipt `cdd47732771b7679f8920f69177a37b6d878760dfdc048925c2f19034f4b6fcc` passes the independent verifier and raw-byte mutation control. |
| Native semantic atlas (2026-09-17) | **PASS (bounded, measured)** | A separately authored eight-axis family (`agency`, `certainty`, `inclusion`, `exploration`, `cooperation`, `priority`, `attention`, `openness`) classified all eight held-out pairs from 64 layer-12 residual captures on the exact 0.8B Vulkan runtime and repeated them on the downloaded 27B IQ1_S Vulkan target. The 0.8B identity screen reached rank 16, the duplicate control rank 15, and an exact-repeat source control had zero residual difference; the 27B repetition passed all eight axes with the same rank/control pattern. This is measured geometry in two pinned runtimes, not model-independent semantic understanding or field transport. |
| Universal interpreter / continuing-world composition (2026-09-17) | **PASS (bounded, measured)** | `run_cassi_universal_interpreter_program.py` links the packet-aware CassiFI episode to the fixed interpreter boundary: premise `2.0 → 5.0`, resident reopen, six selection methods, forced refinement, source controls, and a nonzero packet successor row. One learned meaning is field-owned on a held-out trace, a distinct model identity, and exact restart through the same adapter coordinate; the interpreter ledger has one row and no native fallback. Receipt `3c7c696bac8e75eed694ab6bf087a69801927d041fc5f323d88230731d2727cc` passes the independent verifier. The packet regional workspace and interpreter `QiFieldState.field` remain explicit separate adaptive owners; this is composition evidence, not a shared-tensor, semantic-alignment, or broad-language claim. |
| Universal interpreter / full twelve-step program (2026-09-17) | **PASS (bounded, independently verified)** | `run_cassi_universal_interpreter_full_program.py` and `verify_cassi_universal_interpreter_full_program.py` pass on a persistent field: prospective relation acquisition, new-participant composition through a fixed bounded language boundary, field-owned calculation/emission, correction-local repair, actual pause/reopen with one effect, replacement-model transfer, isolated selective relation loss, held-out emission, a genuine cap-regime gap, and matched fixed-versus-acquired method transfer. The fixed second-family method returns `17` for truth `9`; the acquired guard returns `9` after interruption/reopen while preserving corrected result `11`. Structured execution makes zero model calls. Shared-task native receipt `3b2e8b67a1ca96cc77a327c34ac5fe94917275f0b1fe491450059d549371e832` supplies matching task ID/question/source identity and passes the native verifier; full receipt digest is `4e4a634f0b68d2db7e893d5193e23f3e4c527e386cac668481ed73bc03e821e5`. Scope remains bounded: fixed parser, evaluator-owned outcomes, small field, and no open-domain semantic claim. |
| SQLite capability apprenticeship (2026-09-17) | **PASS (bounded field-owned vertical slice)** | `run_sqlite_apprenticeship.py` acquires the nullable-table `sequence` program from three typed teacher proposals, chooses separating tables before oracle access, executes the candidate only through the field-owned bounded interpreter, and reproduces two held-out order/NULL cases with new input values after persistence. The held-out field calls receive no teacher text, SQL, oracle receipt, or expected result; SQLite runs only afterward for scoring. The receipt records three exactly-once training observations, explicit unsupported statuses, and exact reopen equality; `verify_sqlite_apprenticeship.py` independently accepts the receipt. This is the typed text route, not a native-model or open-language result. |
| SQLite reusable-component apprenticeship (2026-09-18) | **PASS (bounded, independently verified)** | v12 deepens the native field-owned slice with a three-level nested arrangement, four held-out stage routes, and sequential loss of two different components. The nested route returns `[8, 7, 6, 3]` against an independently executed SQLite oracle; revoking and reacquiring `order_limit`, then revoking and reacquiring `stage_order`, preserves the unrelated recovered component and restores the final construction after reopen. Receipt `eb93ac355a3e523222485526feba9b40c9317b2596346670c143d8983018e4f7` passes the independent verifier and native-binding mutation control. This remains bounded typed composition, not open-domain SQL competence. |
| SQLite recursive-depth apprenticeship (2026-09-18) | **PASS (bounded, independently verified)** | v13 transfers the same five native-rooted components into six held-out arrangements, including recursive depth-3 and depth-4 routes absent from the lesson. The field returns `[9, 8, 7]` and `[10, 9, 8, 6]` on those recursive cases, matching independent SQLite oracles; sequential `order_limit` and `stage_order` loss/reacquisition still preserves the unrelated component and final reopen identity. Receipt `15f81eb320578b3d5ac8482e3409f13b860486dcde9370420ec11a60e74d42d4` passes the independent verifier and mutation control. The recursive pipeline is an explicit bounded compiler capability, not open-domain SQL recursion. |
| SQLite declarative-recipe apprenticeship (2026-09-18) | **PASS (bounded, independently verified)** | v14 transfers five typed components acquired from the coupled native teacher plus eight separately admitted, recipe-only field constructions rooted to the same native identity through `cassi.language-stage-recipe-catalog.v1`: seven held-out arrangements overall, including recursive depth-3, depth-4, and branchless `weave`. The live recipe entry is resolved through a second field interpretation before compilation; `weave` returns `[3, 6, 7]`, while `recursive-3` and `recursive-4` return `[9, 8, 7]` and `[10, 9, 8, 6]`, all matching independent SQLite oracles. Revoking `weave` yields a recipe-only support gap while `recursive-3` and `stage_order` remain usable; reacquisition creates a new recipe version and restores `weave`. Receipt `41cea47486a71cc17794da0d9fd9edd1cdbfe006c3948383e56fcf553ce3e906` passes the independent verifier; native-binding and live-recipe mutation controls both reject. This remains bounded typed composition, not open-domain SQL competence.`
| SQLite native-taught parametric apprenticeship (2026-09-18) | **PASS (bounded, independently verified)** | v15 admits a bounded eight-line native lesson: two component examples plus repeated recursive depth-2/3 recipe examples from the captured teacher output, not a declared runner fixture. The field acquires the `recursive` recipe family with a typed repeat-count role and generalizes it to held-out depth 5, returning `[12, 11, 10, 8, 6]` against an independent SQLite oracle; all eight held-out arrangements match. Revoking the parametric recipe creates a recipe-only support gap while `recursive-3` survives, and native-rooted reacquisition restores the depth-5 route with a new construction version. Receipt `6a3e2c911b270fa37cb825d797a701f5084c676f638736ed455b6446ff71b8fd` passes the independent verifier plus native-binding and parametric-recipe mutation controls. This is bounded parametric recipe acquisition, not open-domain SQL recursion. |

| CassiTheory field-memory stress (2026-09-09) | **PASS for exact storage/restart; NULL for semantic selection and answer quality** | The 14-document, 352-chunk campaign returned 60/60 Qwen-requested payloads byte-exact and round-tripped the field state before and after six difficult questions. All source-chart numeric fields were identical, Qwen selected every document/chunk ID, and a literal-text placebo received byte-identical answer prompts. Same-process shared-parameter replay produced five distinct answers for one identical prompt, so no answer-quality delta is attributable to the field. |
| Live-order text counterfactual | **FIELD_DEPENDENT (exploratory)** | Reversing only bounded live-event order changes committed field-owned symbols while trained circulation stays bit-identical. This is separate from the unavailable frozen `qi-field-dependence.v2` receipt and from the null phase-rotation probe above |
| CassiCosmos canonical Qi mirror | **PASS** | Hash-bound monotonic `qi_snapshot` handoff, deterministic top-mode projection, idempotent replay, stale/conflicting revision rejection, and exact PDE isolation |

## The Shifting Laboratory

A course that measures a reader's behavior against a declared physical
instrument. Every station ships a brief, an evidence schema, and a judge that
runs the world; the agent never sees the judge. `laboratory/oracle.py` is an
independent CPU implementation of the qualified two-fluid equations, so the
course can hand an agent a brief and still check its answer against the same
equations, executed separately.

| Level | Question | Stations |
|---|---|---|
| Physics | Which mechanism ran this observed window? | `discrimination`, `representation`, `explanation`, `inverse-design`, `workshop` |
| Hidden worlds | Which of four candidate laws is running, how far is it from the runner-up, what do the held-out steps hold, and how long do four written patterns live? | `identification`, `retention` |
| Shift | A world whose law changes at a declared round: when does the reader notice, and how long does it keep carrying a stale answer? | per-round courses, then a shift receipt |
| Authoring | The agent builds a station of its own; the judge builds that world, runs the real course on it, and accepts it only when an honest reader passes while a wrong one and an idle one are refused. | `authoring` |

Hidden worlds declare four laws over the same chain (native/equal Yin gain at
`omega2 = 0.25` or `0.49` or `0.81`), four observation recipes, and a menu of
four writes whose lifetimes the declared procedure measures. The reader that
cannot be caught is the interesting one: `misattributing` identifies honestly
and then names the runner-up law, so its measurement is real, its separation is
real, and its forecast is a real forecast of the wrong law.

```powershell
python run_shifting_laboratory.py self-check
python run_shifting_laboratory.py canary
python run_shifting_laboratory.py discover --law L3-native-w49
python run_shifting_laboratory.py discover-canary
python run_shifting_laboratory.py shift --reader scripted:tracking
python run_shifting_laboratory.py shift-canary
python run_shifting_laboratory.py author --reference good
python run_shifting_laboratory.py author-canary
python -m pytest tests/test_cassi_shifting_laboratory.py
```

`discover`, `shift` and `author` take `--agent entity` against a running entity;
`discover-run` and `author-run` boot a disposable one in a run directory, as
`entity-run` does for the physics course. An entity program answering these
stations is granted `write_artifact, run_existing_python, read_file,
list_files`: the hidden-world stations ask for a frequency fit and a forecast,
so the reader has to be able to compute and run what it wrote, not only to
write prose. `interpret_python` is deliberately not part of that grant — it
reads source and never executes it, so it cannot produce station evidence.

Receipts land in `_diag/laboratory/`. The instrument is measured, not asserted:
on all four hidden laws the honest reader passes both stations while the
one-model reader, the runner-up reader and the unexecuted reader are refused;
across a six-round shift with the law changing at round 3 the tracking reader
reports the new law in the switch round itself and predicts the next round's
measurement to `1e-7` relative, while a reader that freezes its first answer
stays at the switch's `0.527` error for every later round; a proposal that
observes only the `eps = 0` counterflow packet is rejected because its
observations cannot separate any two candidates. A shift refuses to resume
under a different plan or a different reader, and its receipt digest is stable
across independent sessions and receipt locations.

These are statements about reader behavior on a declared instrument. They make
no claim about the field, the brain, or acquired capability.

## Cassi plays NetHack (the watched-world seam)

Cassi can now live in a game outside the workbench: it reads the game's own
screen, chooses from the game's own verbs, and is watched while it plays. The
first world is NetHack 5.0 (console build) under a Windows pseudoconsole, played
as Cassi the lawful dwarven Valkyrie; the live loopback brain decides one action
at a time.

```powershell
python run_cassi_game.py probe --turns 6                      # the world alone: does a life start, read, and step
python run_cassi_game.py play --player scripted --turns 30    # the walker: the loop and the page
python run_cassi_game.py play --player brain --turns 40       # the live 27B decides
python -m pytest tests/test_cassi_games.py
```

`play` serves a watch page on `http://127.0.0.1:8099/`: the game's screen with
its colours, the numbers the game reports, the last decision with the reason the
player gave, and the journal of the life so far. Every life writes
`games/runs/<stamp>/receipt.json` — player identity and model, and one journal
row per turn with the action, the reason, who chose it, whether it moved, the
game's message, and the state — plus the final screen.

The seam is one game wide and one game deep:

| Module | Owns |
|---|---|
| `games/terminal.py` | the terminal: spawn a program on a pseudoconsole, decode the screen, type, and know when it has settled |
| `games/screen.py` | everything a text game shares: handshake, settle, act, the message diff, and whether the last action moved the player |
| `games/nethack.py` | NetHack's perception and vocabulary: message line, map, status lines, menus, prompts, death, and the game's own keys |
| `games/player.py` | who decides: the loopback brain, or the scripted walker (which also answers mechanical prompts and takes a turn when the brain will not move) |
| `games/fieldmemory.py` | the level memory: the two-fluid field on the level's grid, its readout, and what the player is told of it |
| `games/livingmemory.py` | the memory of playing: lessons the brain writes after a life, the situations that wake them, the use of a recollection and the outcome that settles it |
| `games/view.py` | the watch surface: screen, panel, journal, and no game knowledge at all |

A game is a module and one registration: it declares what to run, how to get
past the title screens, how to read the screen, what the player may do, and
which rows are its own prose. Nothing above the seam knows which game it is
driving. `tests/test_cassi_games.py` carries the proof: a twenty-line toy game
registers on the same seam, is played the same way, and its screen is rendered
by the same watch page.

The player gives the brain what a person at the keyboard has: the screen, the
message line, the state, the actions available, its recent turns with what they
did, and one line saying whether it is against something. When it chooses a move
that just failed, it is told so once in words; if it insists, the walker takes
that turn so the life keeps moving, and the receipt records that it did.

A sixty-decision life on the loopback brain (`Qwen3.8-27B-UD-Q2_K_XL` at
`127.0.0.1:8085`, thinking off) ran 454 s, 7.6 s per decision: 59 decisions from
the brain, one turn where the reply was not JSON (the walker took it), one
blocked-move correction, and one failed call out of sixty-one. The life read the
level, walked corridors, tried doors, was corrected once in words ("Move south to
explore the corridor and find the stairs down." after being told that way was
blocked), and ended alive at `HP 18/18` on the first level, still looking for the
stairs down. The reasons are about the map it can see. This is one bounded life
in one world, not a claim about play strength.

The asking was measured on the loopback brain, and the first measurement is why
it is bounded. Thirty decisions with the question invited in the answer shape
(`Qwen3.8-27B-UD-Q2_K_XL` at `127.0.0.1:8085`): the brain asked on twenty-three
of the thirty turns, thirteen of them in a row, in eight different wordings --
"anything about the stairs", then "anything about the down stairs", then
"location of the down stairs". Each wording was a fresh look for the field:
twenty-three recollections the life then had to settle, of which it had acted on
one. The bound is what followed. In the next thirty-decision life the brain asked
twenty times and the field answered three -- "anything about the door", "anything
about the scroll", "anything about the area to the east" -- refused nine new
questions with the reason recorded, and served the repeats of the three it had
answered from the reading it already held: seven recollections in the whole life
against twenty-seven. Both lessons the field carried into that life were cited by
decisions the life made after asking, both earned 0.25 and were filed back at
priority 0.3, the life ended alive at `HP 17/18`, and it left nothing
unresolved. What the mind asks for, it acts on from; what it asks for twice, it
gets for free.

### A life after a life

One run is one bounded life. A **campaign** plays lives back to back into the
same memory until it is stopped, which is the only shape in which "does it get
better at this" is a question with an answer:

```
python run_cassi_game.py campaign --player brain --turns 600 --lives 0 \
    --memory-home games/field-home-3 --campaign games/runs/campaign-1
```

`--lives 0` means keep going; the field home is opened once for the whole
campaign and every life writes into it, so what a life learns is what the next
life opens with. The watch page keeps running across lives (`life 3 · …` in its
status line), each death is held on the page a few seconds, and Ctrl-C stops
between lives with the current life closed out first -- its recollection bound
and settled, its lesson filed, so stopping never costs the life that was
playing. A campaign can also be stopped from anywhere -- another terminal, tomorrow, a
script -- by creating a file named `STOP` in its directory. The life being
played notices it between turns and finishes first, and the campaign ends behind
it; nothing about the process has to be reachable for this to work, which is
what makes a run that outlives its console safe to leave alone.

Pointing `--campaign` at an existing directory continues it: the log is
read back, the lives carry on from where they were, and the memory does the rest.

The campaign keeps its own account in `campaign.json`, a row per life:

```
life <n>  deepest <level>  died|stopped|WON  turns <n>  <mins> min  HP <h>/<max>
          lessons <n>  earning <n>  stall <n>  home <mb> MB  -- <the game's last words>
```

Deepest level reached, how the life ended (`died`, `stopped`, or `WON` when the
endgame text says the Amulet made it back up), turns played, how long it took,
where it stood, the lessons it wrote, how many memories now carry a verdict, the
longest run of turns in which it did not move, and how heavy the mind's home has
become. That last number is the one to watch over days: an indefinite loop is
only honest if the memory it accumulates stays usable.

### The level memory is a field

The brain carries nothing between decisions, so the seam gives it a memory that
is a field rather than a dictionary: `games/fieldmemory.py` runs the canonical
Cassi two-fluid scalar sector (`CassiTheory/two-fluid/cassi_two_fluid_3d_gpu.py`)
on the level's own grid, 21 rows by 80 columns, one Yang/Yin pair per channel,
stepped once per game turn.

- Four channels: `terrain` (open or solid), `goal` (a way down or a way up),
  `blocked` (a door that would not open, a way that refused the player), and
  `trail` (where the player has been).
- Looking at the level writes a cell: `ey = +1, ei = 0` for open floor, stairs
  down, a door, a trail step; the Yin cells for solid rock, stairs up, a refusal.
  Re-looking at a cell refreshes it, so decay is exactly one law.
- The step is conversion only (`conv = -lam*(ey - PHI*ei)`, `d(ey)/dt = conv`,
  `d(ei)/dt = -conv`, RK2, `dt` = one turn). The sum `ey + ei` is conserved, so
  what fades is the content, with half-life `ln2/(lam*(1+PHI))` turns — 40 by
  default, from `--memory-half-life`. No flow term: a memory of a place does not
  drift.
- Everything the player is told is read back out of the field, above a `0.25`
  threshold: the remembered map, the count of known and solid cells, the ways
  down and up, the refusals, the player's own cell (the strongest trail cell —
  the most recent write, since every trail write is equally strong), and the
  bearing from that cell to a goal. There is no side table of places.

```powershell
python run_cassi_game.py play --player brain --turns 80                    # the field remembers
python run_cassi_game.py play --player brain --turns 80 --memory none      # the control
```

What the brain reads is that readout: the remembered map with a column ruler,
its legend, and one summary line. At decision 68 of the field life the line was
`you have walked 38 cells and know 161 of the level's cells (66 solid); you are
at column 51, row 7; you found a way down at column 51, row 8 (1 row south of
you); a way up at column 17, row 8 (1 row south and 34 columns west of you).` The
receipt carries the memory's parameters, its per-turn counts and goals, and a
digest of both fluid fields.

Two eighty-decision lives on the same brain and model, thinking off:

| life | depth | distinct cells stood on | cells the field still held at the end | blocked-move corrections | descent |
|---|---|---|---|---|---|
| `--memory none` | 1 | 6 | — | 4 | none |
| `--memory field` | 2 | 48 | 37 of the level's cells | 10 | turn 70, at `(8, 51)` |

The field life stood on 48 distinct cells but its trail held 37 by the end: the
other eleven had faded below the readout threshold, which is the memory working
as declared rather than a bookkeeping error.

In the field life the model explored for 58 decisions; at decision 59 the field
first held a way down at column 51, row 8, and from decision 60 to 68 it walked
straight there — distance 10, 9, 8, … 0, one step per decision, every reason
naming the coordinates the field held ("Move east toward the stairs down at
column 51, row 8"). At decision 70 it stood on the stairs and took them. In the
no-memory life the same brain spent all eighty decisions inside a six-cell pocket
choosing "move east" into a wall, with no way to know it had been there.

The lives are different random levels, so the two arms are not level-matched:
this NetHack build ignores `OPTIONS=seed`, and the same seed produces different
dungeons. What the field life shows is within one life, on one level: the model
changed what it did exactly when the field's content changed, and acted on the
coordinates it was given. The memory is one level's map, not a plan; the decision
stays with the brain.

### The memory of playing is the field's own

Two memories carry a life. `games/fieldmemory.py` is where the player *is*: one
level's map, held in the two-fluid field. `games/livingmemory.py` is what the
player has *learned about playing*, held in Cassi's living memory
(`CassiFI/cassi_field_cognition.py` through `CassiQwen/cassi_field_qwen_workbench.py`)
in a field home of its own (`--memory-home`, default `games/field-home`), so the
experience of one life is available to the next.

The loop is the design's, not an imitation of it:

- **When a decision is needed**, the player reports what is true of it -- a way
  refused, a monster beside it, health below its best, a known way onward being
  followed, a level just arrived on -- and the field wakes lessons filed for
  those moments (`register_relevance`/`match_relevance`). The first decision
  reads these situations directly, without a workspace-wide opening recall or
  briefing. The brain is shown at most four woken lessons, most earned first.
  A lesson written in an earlier life is recovered from its field binding and
  exact source revision when it wakes, including after reopening the field home.
  A lesson set aside for not earning its place returns as a marked cue.
- **The mind can ask for a memory.** A decision may put a question of its own in
  `"want"` -- *"anything about doors"* -- and the field looks it up; the answer
  leads the next decision, marked as the answer to that question, because a
  question the mind asked itself is the most specific thing it knows about what
  it needs. When the field knows nothing about it, it says so rather than leaving
  the question hanging. The asking is bounded, because the mind has no restraint
  about it: a question is looked up once per life however often it is asked, and a
  life may ask three different things -- past that the field says so and the
  decision stands on what the life already has. The answer is a reading like any
  other, so it earns its own verdict: a lesson the life acted on after asking is
  credited, and one the life asked for and then ignored is settled as unused
  rather than left open.
- **At the end of the life**, memories the brain cited are bound to the outcome.
  If the field woke a cited lesson, one recollection episode is created for
  those woken lessons, used (`use_recall`), and settled (`assess_recall`).
  Lessons returned to a question the mind asked keep their own episode and
  settlement. Usefulness is `1.0` for a life that went down a level, `0.25` for
  one that moved and saw new ground, `0.0` for one that got nowhere. The use
  carries every lesson the life acted on, so one verdict credits each of them.
  A life that cited nothing creates no situational recall episode.
- **A memory is as loud as the lives that leaned on it.** Every verdict the field
  recorded for a lesson is read back and averaged, and that standing -- the
  middle when a lesson has never been acted on, toward `0.9` for one that keeps
  serving, toward `0.1` for one that keeps leading nowhere -- is the priority its
  moment is filed at. What worked is heard first, and a lesson that stopped
  earning its place sinks without being hidden.
- **Then the brain looks back** (`reflect`): one sentence on the life and one to
  three lessons, each with the moment it applies to. A lesson that only sharpens
  one the brain already knew is filed as a sharper *reading* of that memory
  (`reinterpret_memory`) -- the evidence stays as it was learned -- and no second
  lesson is kept. A lesson acted on in lives that got nowhere, twice, is set
  aside with its words kept (`demote_memory`); a set-aside memory is expanded
  again whenever its own context is recalled, so setting one aside marks it as
  not earning its place rather than hiding it.
- **After the run**, the field assesses its own memory work (`maintain_memory`)
  and reports whether exact detail is still recoverable (`memory_awareness`);
  both land in the receipt beside the autobiography.

```powershell
python run_cassi_game.py play --player brain --turns 90                    # plays, remembers, settles
python run_cassi_game.py play --player brain --turns 90 --no-living        # the same, remembering nothing
python run_cassi_game.py play --player brain --turns 90 --memory-home X    # a different field home
```

What the first lives wrote, in the field's words: *"Repeatedly moving into a
solid object teaches me nothing; I should change direction after the first
blocked attempt"* and *"A kitten can block your path just as firmly as a wall, so
I must plan a detour rather than bumping into it repeatedly."* A later life
recalled four lessons, cited them on 32 of its 60 decisions, bound the use of one
and settled it at `0.25` -- it moved and saw ground but never found the stairs.
Its own reflection then sharpened the blocked-move lesson into *"If I am blocked
by a solid object, I must not just keep trying to move into it; I need to rotate
my direction to find a path around it"*, filed for the moment a way is refused,
and wrote no duplicate. The receipt carries the whole exchange: the recall with
its episode identity, the citations, the use, the outcome, the reflection, the
conditions registered, what was sharpened or set aside, the autobiography, the
maintenance assessment, and the awareness reading.

The next life opened on *"This is your life number 2. You have played 1 before;
your deepest was level 1, and you hold 2 lessons about playing"*, was woken by
its situations 26 times across 60 decisions, and cited both lessons it was shown.
One use carried both; the field credited each of them at `1.0` -- the life went
down a level -- so both were filed for their moments at priority `0.9` rather
than the middle. The brain then sharpened the blocked-move lesson into its own
words and wrote no duplicate. The life after that one opened on *"This is your
life number 3 ... your deepest was level 2"*, was woken 15 times in 14 decisions,
and cited both lessons again; it got nowhere, so the two `1.0` verdicts became an
average of `0.625`, their standing fell from `0.9` to `0.6`, and their moments
were filed at that instead of at what they had been. Those earlier receipts
record opening briefings; current lives wake relevant lessons directly at the
first decision. The receipt records the woken memories, citations, any earned
use and verdict, the conditions filed, the reflection, and the autobiography.

After a run the page holds the last screen for five minutes (`--linger`), so the
end of a life is watchable too. A run refuses a port another run is still holding
rather than sharing it silently.

## 2026-09-18 bounded teacher proposal and Cassi Mind Field design

The cumulative Python teacher boundary now has five bounded task families:
`constant_fold`, `redundant_assignment`, `identical_branch`,
`redundant_add_zero`, and `redundant_multiply_one`. Eligibility and promotion
use the canonical CassiPy AST rather than source-text markers. Every static or
model-produced candidate must satisfy a task-local structural obligation
(remove the selected AST pattern), preserve all held-out results, pass the
independent CPython differential oracle, and reduce measured execution steps.
This prevents a behavior-preserving edit from quietly performing a different
task. The receipt schema is now `v5` and records `task_invariant` on candidate
pool rows, proposal outcomes, retained field experiences, and teacher-control
mode.

The next teacher integration is deliberately a new control boundary rather
than a reinterpretation of the existing selector. The current
`field_select_edit` remains an explicit host comparator; it is not yet claimed
as a field-owned decision. The implementable first slice is a
`TeacherFieldController` around the existing `CassiFieldWorkMemory`:

1. Before each offline teacher call, submit a bounded observation and current
   candidate descriptors to one field operation with an expected predecessor
   state hash.
2. The field returns a fixed action: candidate/task ID or abstention, a
   bounded proposal budget, and a bounded thinking control
   (`enabled`, `max_tokens`, `effort_code`). The teacher receives the action's
   fixed control frame, never raw field checkpoint bytes.
3. Call the explicitly loopback-only Qwen teacher, then admit the outcome
   observation against the action's successor state. Carry that state hash
   into the next generation.
4. Record prompt, response, reasoning, model identity, actual request policy,
   candidate provenance, field predecessor/successor hashes, and operation
   IDs in the receipt. A field-off matched run supplies the comparator.

The runnable first slice is exposed by
`run_cassi_python_cumulative_improvement.py --teacher-control field` with
`--teacher-control field-off` as the matched comparator. The controller now
calibrates the actual server policy before the field acts: it sends identical
thinking-off/thinking-on probes, separates flag operativeness from answer-channel
viability, and feeds the bounded capability result into the named
`teacher-control` operation. On the pinned 0.8B teacher the flag is effective
(`reasoning_content` changes), but the thinking-on answer channel is not viable
within the probe budget. The field therefore emits a visible
`capability-floor-off` action rather than silently falling back.

The calibrated three-generation field-owned campaign passed and independently
verified at
`E:/CassiLearning/cassi-python-teacher-field-calibrated-20260918/receipt.json`:
the field selected `constant_fold:canonical`, `redundant_assignment:canonical`,
and `identical_branch:parenthesized`, while every teacher action carried the
capability-floor thinking policy and every outcome returned to the field.
The matched three-generation field-off campaign also passed at
`E:/CassiLearning/cassi-python-teacher-field-off-calibrated-20260918/receipt.json`;
its teacher-control receipts contain no field-state mutations. A raw
thinking-on campaign remains fail-closed when the model cannot produce its
answer channel, preserving the distinction between reasoning tokens and a
usable teacher decision.

The action must be produced by a named `teacher-control` semantic operation
before it can be called field-owned. The field may select among fixed
candidate descriptors or abstain; it may not emit arbitrary source text,
temperature, top-k/top-p policy, embeddings, a learned side table, or a Qwen
fallback. Teacher thinking is measured through the server policy probe and
actual reasoning-content/token evidence, not the requested flag alone.

The existing CassiCore 7273 and CassiCosmos 7599 paths are not this control
boundary: 7599 is a shadow field bridge and the current 7273 context client is
advisory/fail-open. A future split deployment therefore needs a new explicit
loopback-only teacher-control endpoint with request identity, predecessor
state checks, replay protection, and fail-closed behavior. Native Qwen
displacement remains zero for the Python first slice; a native claim requires
the returned field action to enter the live decode graph and a separate
identity/control receipt.

## 2026-09-14 current CassiFI regional adapter upgrade

`cassi_field_qwen_workbench.py` now uses the current CassiFI owner and its
`cognition.field` semantic kernel rather than the retired adapter-side
adaptive-memory assumptions. The source identity is hash-bound to the complete
28-file CassiFI production closure, and the owner is reopened through one
regional `LearningComputer` with a fixed profile.
The current closure includes the affect, open-vocabulary, and mathematical-language
modules; older measured receipts retain their original source identities.

The profile is `mode_count=196,608`, producing a `14,155,776`-byte field image
and a `294,912`-word semantic task region. The adapter exposes task occupancy
in its state receipt and drains every bounded semantic continuation through
deterministic owner operations; it does not silently fall back to an
unbounded loop or a second adaptive store.

The current verification evidence is split into two bounded exercises:

- The CassiTheory preparation loaded 14 documents and 442 chunks
  (`2,213,803` source bytes), admitted 442 current source revisions, remained
  finite, and reopened with an exact state receipt. It ended at
  `225,237/294,912` task words under the current regional profile.
- The matched 17-case local-Qwen workcase smoke measured `3/17` exact baseline
  passes and `8/17` field-memory passes, with five gains, zero regressions,
  `13/13` exact memory-dependent retrievals, and `4/4` exact empty
  memory-independent selections. The independent verifier recomputed 1,338
  checks with zero failures.

  The campaign ran before the harness sent `chat_template_kwargs`, so the
  model's template opened a reasoning block inside those same `96/128`-token
  caps. All 13 empty baseline completions and all 7 empty field completions
  ended at exactly their case cap, and the receipt records no trace; `content`
  holds only the answer, and two field longitudinal rows are JSON prefixes cut
  mid-value. The field retrieved exactly on all 17 rows of all four campaign
  receipts, and the baseline arm records retrieval as `null` throughout, since
  it has no field agent. `8/17` therefore counts the cases where exact
  retrieval and a completion that reached an answer coincided, and all five
  `reasoned_memory` cases are empty in both arms.

  The per-case token counts fix the failure mode exactly. Every empty completion
  consumed precisely its case cap, 96 or 128, and every successful one consumed
  64 to 92, with `content` carrying the answer in both cases. So the campaigns
  filtered on deliberation length rather than on knowledge: the same cases that
  exhausted 96 tokens without the field's facts finished in 73 to 90 with them,
  and the five `reasoned_memory` cases ran past 128 in both arms. No row of any
  of the four receipts contains a complete but incorrect answer.

  With the policy in effect the same protocol measures knowledge rather than
  budget: `6/17` without memory and `16/17` with it, ten gains, no regressions,
  and completions of 7 to 35 tokens. The model abstains rather than invents when
  it cannot ground a field, since ten of the eleven baseline failures are the
  literal string `UNKNOWN` and the exception answered a tax computation it had
  no figures for. The field arm's single failure returned the correct escalation
  channel with a due date one day early, which is an arithmetic slip on the case
  that also drew its longest completion.

This is an exact-storage, source-exposure, persistence, and ownership-boundary
result. CassiFI owns durable regional memory and exact source selection; Qwen
still owns native execution, natural-language reasoning, and emitted tokens.
The result does not claim semantic absorption, model-weight displacement, or
general language improvement.

Machine-readable upgrade evidence is under
`_diag/upgrade-workcases-final-v2-20260914/` and
`_diag/upgrade-theory-final-v2-20260914/`. Both receipts bind to the same
25-file CassiFI source identity aggregate
`7bf5592f35fcec539af835f30b4fcd56bcdb6aedf4151fd0204b8a8ff2ce2603`.



## 2026-09-14 universal reasoning integration

The current regional computer now retains nested calls in a protected field
region rather than replacing cognition or restoring it from a host dictionary.
Reasoning and self-development episodes use the same `cognition.field` state,
semantic records, owner journal, bounded work allowance, and restart boundary.
The initial development selector is the disclosed fixed
`supplied-balanced-v1` strategy; acquiring a better strategy on unfamiliar
capability targets remains an empirical objective.

`cassi_model_instrument.py` is the fixed model boundary. It binds model,
runtime, hook, tokenizer, arithmetic, context, and backend identity; declares
capabilities; validates bounded numeric observation envelopes; and refuses
unsupported sites or continuation classes explicitly. Its coupled journal
contains reservation, trial, work, publication, delivery, and recovery
control, not learned state. `cassi_field_qwen_workbench.py` admits those
observations and native results through the existing CassiFI owner.

The exercised native paths were:

- `test-cassi-qi-latent` captured 12 Qwen35 block-input residuals from layers
  12 through 23 as finite, hashed float32 envelopes. A separate two-step,
  `alpha=0.1` Qi intervention changed the trial state. The adapter reports
  `native-continuation-unavailable` because the harness does not serialize a
  resumable model/KV context.
- `cassi-qwen --mode field` emitted an 11-byte two-token result while its
  native receipt reported zero Qwen forward passes, zero model-logit reads,
  and zero model-tensor bytes loaded. The GGUF vocabulary/tokenizer dependency
  remains declared.
- The workbench staged that field-owned route, admitted its exact result into
  the regional field, sealed one field/native successor pair, committed it,
  closed, reopened, and recovered `exact-pair` with the same zero-use
  displacement counters.

Focused behavioral checks passed for interruption-safe caller restoration,
typed returns, bounded reasoning and development, envelope tamper rejection,
unsupported partial acceptance, duplicate observation admission, transaction
crash windows, correction locality, and restart.

The continuing-world run at
`../CassiFI/_diag/universal-design-demo.json` used one seed, one acquisition
block, two roots, and two decisions per root. Its final frozen trained
checkpoint scored `4/4` in each of measurement, temporal, inventory, and
software. Across all 72 cold, trained, structural, irrelevant, and
intervention rows it retained 52 failures, and the shared-belief challenge
passed `7/9` checks. The independent verifier accepted receipt
`0dce255667830b6f7a48fc1e468c12ba61033e4366c31d0160194f20b510e2a7`.
Those results establish bounded mechanics and selective learned capability;
they do not establish the complete twelve-part composition in
`LATENT-REASONING-DESIGN.md`, useful semantic alignment of the captured
residuals, acquired improvement-method superiority, open-domain language, or
general intelligence.

## 2026-09-17 universal interpreter role-authenticated coordinate seam

`ActivationTrace` can now carry a declared `native_role` and deterministic
`role_attestation`. Passing a `role_registry` to `UniversalLLMInterpreter`
authenticates the coordinate's semantic role and model fingerprint before the
interpreter admits a reset or observation event. Registry descriptors retain
the task/source coordinate fields used by the semantic bridge. With the
default `role_registry=None`, existing traces retain their legacy digest
identity and behavior.

The canonical seam rejects an unregistered coordinate, a native-role/
coordinate mismatch, an altered capture digest, or a cross-model trace before
field access. The focused suite
`python -m unittest -v test_cassi_universal_interpreter` passes. The native
paraphrase smoke covers correction and delay roles, and the independent
tamper receipt is
`_diag/universal-interpreter-core-role-authentication-20260917-r3/`
with content digest
`0bd8395c76ee179cef0d480a3c4b855d4134a47141349b5a7394d5d53bd862b2`.
The gate authenticates declared capture provenance; it does not infer a role
from native hidden-state content.

The role seam now supports an independent native-semantic manifest. Pass
`native_role_manifest` alongside `role_registry` to
`UniversalLLMInterpreter`; each manifest row binds a
`model_fingerprint`, `prompt_sha256`, and `capture_sha256` to the role derived
from the native task semantics. The gate checks that binding after the
coordinate, model, and deterministic attestation checks, so a trace can no
longer reuse a valid correction coordinate and attestation for capture
evidence whose native task means delay. Supplying a manifest without a role
registry fails closed.

`NativeLlamaSession.capture(..., native_role=...)` persists the role and
attestation in the capture receipt, and `load_capture_receipt` reloads both.
The native vertical slice derives `correction` from the closed native task
grammar, records the resulting manifest digest in the field state receipt,
and runs semantic-misbinding and unregistered-evidence controls before any
field event is admitted. The independent native verifier recomputes the same
grammar independently, then checks the prompt-derived role, manifest key,
manifest digest, capture attestation, and both tamper controls. This validates
the native task-to-role binding at the capture boundary; it does not infer a
role from hidden-state values.

The measured adversarial role-semantics smoke is retained at
`_diag/universal-interpreter-native-role-semantics-20260917-r6/`. Its native
program receipt is `PASS` with content digest
`17b379915febd8d369e8c296912b51ce8bab2a9fc9b694da0b283fefc65936ed`; the
independent verifier is also `PASS`. The separately authored manifest is
source-bound with digest
`cde1cf0f8a236a0d2a0cdd071946fdf90a3a4628743b583c1f72d8a3f5c9fa7a`, and
the probe matrix digest is
`a448221a37af9395a8d028e8b9b75ff46a672dea2158483ba30699f2198b55c3`.
The correction probe containing delay cues still favored `correction`
(margin `1.9545354843139648`); the delay probe containing correction cues
favored `delay` (margin `4.940971374511719`); and the deliberately losing
correction control produced a negative `delay` margin of
`-8.577526092529297`. All three raw logits artifacts are independently
re-read, and the losing control is explicitly required to lose.

## 2026-09-17 four-axis native semantic atlas

The first held-out semantic atlas captures 32 field-off native residuals from
the exact Qwen3.5-0.8B Vulkan runtime at layer 12 with width 1,024: three
training paraphrase pairs and one held-out pair for each of `timing`,
`revision`, `epistemic`, and `commitment`. Each axis classifies its held-out
pair by the sign of the direction learned from the three training pairs.
All four held-out pairs recover the declared pole, with scores
`0.5282542706` (timing), `0.6996461749` (revision), `0.5933966637`
(epistemic), and `0.3908973336` (commitment); swapping the held-out pair
reverses every score.

The identity-row rank screen returns rank `8` for eight distinct held-out
semantic rows, rank `7` after one exact duplicate, and rank `1` for both the
shared-identity and scalar-multiple controls. The distinct-row smallest
singular value is `0.5799684163`. These measurements establish a
four-dimensional held-out residual geometry in this exact capture setting;
they do not yet establish model-independent semantics or field transport.

The receipt is
`_diag/native-semantic-atlas-20260917-r3/semantic-atlas-receipt.json` with
content digest
`29ee95938d0edf46f64bdd1bd700572eff1c7c1001099119c9ddf1c595160dfc`.
Its separately authored manifest digest is
`1187763b6c001ef04a864d2becc2dab591bc12e1a535604c5752f5ab75e81111`;
`verify_native_semantic_atlas.py` independently re-reads all 32 capture
receipts and raw residuals, recomputes the holdout directions, derived
artifacts, singular spectra, and controls, and returns `PASS`.

The atlas can be reproduced with:

```powershell
python run_native_semantic_atlas.py --root _diag/native-semantic-atlas-20260917-r3
python verify_native_semantic_atlas.py --root _diag/native-semantic-atlas-20260917-r3
python -m unittest -v test_native_semantic_atlas.py
```

## 2026-09-17 eight-axis native semantic atlas

The broader source-authored atlas extends the same held-out direction test
from four to eight semantic families: `agency`, `certainty`, `inclusion`,
`exploration`, `cooperation`, `priority`, `attention`, and `openness`. It
captures 64 field-off residuals at layer 12 of the exact Qwen3.5-0.8B Vulkan
runtime: three training paraphrase pairs and one held-out pair per family.
All eight held-out pairs recover their declared pole; the smallest positive
held-out score is `0.0504483171` (`priority`), and the next smallest is
`0.1147610843` (`cooperation`). The 16-row held-out identity screen reaches
rank `16` with smallest singular value `0.4123026827`; the exact duplicate
control reaches rank `15`, while the shared-identity and scalar controls
remain rank `1`.

The manifest also contains a source-authored exact-repeat negative control.
Its two independently captured copies have residual difference norm `0.0`;
the independent verifier requires this control to pass, re-reads all 66 raw
capture artifacts, recomputes every held-out direction and rank spectrum,
and checks the receipt content digest. A mutation control that changed one
float32 residual was rejected with `artifact digest mismatch`. This is
broader measured geometry in one exact runtime, not a model-independent
semantic benchmark, cross-runtime invariance result, or field-transport
result.

The receipt is
`_diag/native-semantic-atlas-broad-20260917-r1/semantic-atlas-receipt.json`
with content digest
`aaae09a48b68b5979dceef5fc78b9f2fb02bd2e2248eaa29d760a36d33c1157a`;
the separately authored broad-manifest digest is
`16ba74bbd7cf2ae324aaf553bde903e3bc856e9fa9bcafd6b7b7cff4d301af8c`.
Reproduce it with:

```powershell
python run_native_semantic_atlas.py --manifest semantic-atlas-broad-manifest.json --root _diag/native-semantic-atlas-broad-20260917-r1
python verify_native_semantic_atlas.py --manifest semantic-atlas-broad-manifest.json --root _diag/native-semantic-atlas-broad-20260917-r1
python -m unittest -v test_native_semantic_atlas.py
```

## 2026-09-17 cross-runtime and one-bit 27B atlas

The same eight-axis manifest now has a CPU/Vulkan repetition on the exact
Qwen3.5-0.8B Q4_0 model. Both runs use runtime build
`llama.cpp:0.1.1-dev` with runtime digest
`a6d36f1a5d6d02568283850cc8c0ecd4acc5b138e794d1ad47163a3907fa0afa`;
the model digest is
`57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf`.
The Vulkan run is at layer 12 with 99 GPU layers; the CPU run is at the same
layer with zero GPU layers. The independent cross-runtime comparison reports
`PASS`: all eight held-out score signs agree, all rank controls agree, both
exact-repeat controls have difference norm `0.0`, and every prompt hash and
capture layer matches. The eight axis-direction cosines range from
`0.9928399324` to `0.9982677698`.

The source receipt digests are
`aaae09a48b68b5979dceef5fc78b9f2fb02bd2e2248eaa29d760a36d33c1157a` for
Vulkan and
`a3119234b482304fe767dc7bafaa441837cbbdfe490a8f174025e750231e671c` for
CPU. The comparison receipt is
`_diag/native-semantic-atlas-cross-runtime-20260917/comparison.json`; it
checks the two raw receipt trees rather than comparing only their summaries.

The downloaded one-bit target is pinned as a separate manifest:
`Qwen3.8-27B-UD-IQ1_S.gguf`, quantization `IQ1_S`, Vulkan with 99 GPU layers,
model digest
`3895b6eaa91e705c06ad1938d16c22e86f073c6a67df86260a1da79be3d1f887`.
The 27B run captures the same 66 raw residuals at layer 32 in width `5120`.
All eight held-out axes pass; the smallest held-out score is `6.1663727760`
(`priority`), the identity screen reaches rank `16` with smallest singular
value `29.7492500750`, the duplicate control reaches rank `15`, and the
shared-identity and scalar controls remain rank `1`. Its exact-repeat
negative control has difference norm `0.0`.

The 27B receipt is
`_diag/native-semantic-atlas-27b-iq1s-20260917-r1/semantic-atlas-receipt.json`
with content digest
`705bbe87529ba64fbcc252d39947ab560e58dcc59d1a8bfb7b9f9a591452b49d`.
The pinned manifest digest is
`5e9139dbeae67b9e3179196dfc02196325bf1fc7dd3e0ab09c5e1ca0952655ee`.
Reproduce and verify it with:

```powershell
python run_native_semantic_atlas.py --manifest semantic-atlas-27b-iq1s-manifest.json --model Qwen3.8-27B-UD-IQ1_S.gguf --gpu-layers 99 --quantization IQ1_S --root _diag/native-semantic-atlas-27b-iq1s-20260917-r1
python verify_native_semantic_atlas.py --manifest semantic-atlas-27b-iq1s-manifest.json --model Qwen3.8-27B-UD-IQ1_S.gguf --root _diag/native-semantic-atlas-27b-iq1s-20260917-r1
python compare_native_semantic_atlas.py --manifest semantic-atlas-broad-manifest.json --left-root _diag/native-semantic-atlas-broad-20260917-r1 --right-root _diag/native-semantic-atlas-broad-cpu-20260917-r1 --out _diag/native-semantic-atlas-cross-runtime-20260917/comparison.json
python -m unittest -v test_native_semantic_atlas.py
```

This establishes reproducible eight-axis geometry on the new 27B IQ1_S
runtime and backend-stable direction signs on the smaller cross-runtime pair.
It does not turn prompt-defined axes into a model-independent semantic
benchmark or establish field transport.

## 2026-09-17 universal LLM interpreter native vertical slice

The universal interpreter now has a complete measured native boundary for the
declared exact `Qwen3.5-0.8B-Q4_0.gguf` target: a running Qwen graph is
observed, the observation enters one persistent Cassi field, the field emits
without Qwen, and the same field state is exercised in graph-native output and
recurrent-state interventions. The program is
`run_cassi_universal_interpreter_native.py`; its independent receipt verifier is
`verify_cassi_universal_interpreter_native.py`. Fresh evidence is under
`_diag/universal-interpreter-native-program-v2-20260917/` and its compact
summary is `_diag/universal-interpreter-native-program-v2-20260917-summary.json`.
The top-level receipt digest is
`1d6539189d1a89caf7a4b7349461731c6abba5e2f7b55b35dc02e010c676cec6`.

The native observatory used the pinned Qwen3.5-0.8B Q4_0 model and the Vulkan
llama.cpp build. Its capture bundle covers every declared model layer for the
non-optional sites (`embedding`, `layer_input`, `attention_output`,
`ffn_input`, `ffn_output`) and records the optional attention-probability
layers explicitly. The selected real `layer_input` trace at layer 12 contains
1,024 finite float32 values; the corresponding public head readout contains
248,320 logits. Capture-off and capture-on logits are byte-identical (`0.0`
maximum difference), with top token `561`. The trace, model, prompt, hook,
per-site raw files, and adapter coordinate
`qwen35-0.8b/layer-input-mid-v1` are hash-bound. The GGUF observatory also read
a bounded `2x2` slice from tied `token_embd.weight` Q8_0, touching 2,176
quantized bytes. This is a real model read; the file omits a separate
`output.weight` tensor because the embedding tensor is tied to the output
projection.

That immutable trace entered `UniversalLLMInterpreter` without copying model
state into a second adaptive system. The interpreter admitted the native
meaning through one `RawEventStore` and one `QiFieldState.field`, answered
field-owned on the same trace, closed, reopened, and answered again with the
same field fingerprint. Inspection did not mutate the field, the answer
matched native top token `561`, and neither query used a native fallback.

The field-only executable then ran two explicit routes. A one-token seed
produced `环保`; a four-token continuation produced
`uage-handle-handle-handle`. Both are fixed field-boundary outputs rather than
quality claims. Their receipts report field ownership of logits and sampling,
zero Qwen forwards, zero model-logit reads, zero Qwen tensor bytes, and no
silent fallback. This demonstrates a live field-owned emission boundary; it
does not establish open-domain language competence.

The graph-native route ran matched trials with the same model, prompt, layer,
and sequence coordinates:

- At displacement 6 the field-owned LM-head route bypassed the native output
  row and read one field-owned logits vector per decode. The paired field-state
  lesion changed the logits with `L2=1.7039947433` and maximum absolute delta
  `0.0237564482`; a zero-state donor restored the baseline decision. The graph
  executed two trunk forwards per trial and loaded `552,074,496` Qwen tensor
  bytes. The output row was skipped; this is measured output ownership, not an
  offline counterfactual.
- At displacement 3 the field-owned state route replaced the selected layer's
  suppressed recurrent write. The SSM `qkv` convolution row has 6,144
  channels: the field supplied the leading 1,024 channels (`4,096` bytes per
  decode) and the model retained the remaining 5,120 channels (`20,480`
  bytes). The field/model pair changed the committed graph readout
  (`L2=56.6301024695`, maximum absolute delta `0.5508885384`). The independent
  suppressed-model control also changed the readout
  (`L2=29.2941717326`, maximum absolute delta `0.3507469893`), so the
  measurement separates a field write from a generic recurrent-write lesion.
  The receipt names the three owners directly: `model`, `suppressed-model`,
  and `field`.

The recurrent route removes no bytes from the native allocation because it
shares the row: `native_dynamic_state_bytes_removed` is `0`, while the field
owns `4,096` bytes of each write and the model retains `20,480`. This is a
partial native replacement with causal field ownership, not a claim that the
whole recurrent or attention state has disappeared. The existing displacement
4/5 ladder remains useful as an ablation of attention or whole blocks; it is
not described as field-owned replacement.

The independent verifier does not launch the model or trust the runner's
derived pair results. It validates the capture contract and every linked site
descriptor, rehashes every capture/logits/state float32 file, checks the
head-output and selected-layer identities, reconstructs all graph snapshots,
reruns the LM-head and recurrent causal comparisons, checks the three
state-write owners and byte counts, verifies interpreter restart identity, and
recomputes the top-level digest. All 17 program checks and all 12 independent
verification checks passed.

This completes the declared universal interpreter R&D program on the exact
0.8B target: real native observation, fixed-coordinate field ingestion,
persistent field-owned meaning, field-only emission, graph-native LM-head
ownership, and graph-native recurrent-state ownership with interpretable
lesion controls. It establishes causal ownership and measured native
displacement, not semantic alignment, broad language quality, or a
model-independent replacement of every transformer/KV computation.

## 2026-09-17 universal interpreter native 27B IQ1_S boundary

The same native interpreter boundary now runs on the downloaded
`Qwen3.8-27B-UD-IQ1_S.gguf` one-bit target beside the smaller reference model.
The run used the Vulkan `llama.cpp:0.1.1-dev` build with 99 GPU layers, all 64
model layers available, width `5120`, and the real `layer_input` trace at layer
32. The model SHA-256 is
`3895b6eaa91e705c06ad1938d16c22e86f073c6a67df86260a1da79be3d1f887`; the
runtime SHA-256 is
`a6d36f1a5d6d02568283850cc8c0ecd4acc5b138e794d1ad47163a3907fa0afa`.

The separately authored native task manifest identifies the captured role as
`correction`. Both directional behavior probes passed, the
`correction-losing-control` negative control failed as intended, and both
semantic-misbinding and unregistered-evidence tamper controls were rejected
without changing state. This prevents the adapter coordinate from being
treated as meaningful merely because a field-to-logit path is live.

The 27B trace entered the same single `QiFieldState.field` interpreter path:
the field learned from the native capture, delivered a field-owned prediction
with target token `271`, survived exact close/reopen with the same state
fingerprint, and used no native fallback. The field-only emission route made
four selections with zero Qwen forwards, zero model-logit reads, and zero
Qwen tensor bytes.

The graph-native readout is also live on this larger model:

- At displacement 6 the field-owned LM-head route changed the native logits
  by `L2=3.0327043228` with maximum absolute delta `0.0645719953`. The
  zero-state donor restored the baseline decision. This is a real graph route,
  not an offline replay.
- At displacement 3 the field supplied `5,120` of the `10,240` recurrent-row
  width (`20,480` bytes), while the model retained the other `5,120`
  coordinates (`20,480` bytes). The field/model pair changed the committed
  readout by `L2=409.1006125244` with maximum absolute delta `7.4153305292`.
  The independent suppressed-model control also fired
  (`L2=208.5842882946`, maximum absolute delta `3.8626477718`), separating
  field ownership from a generic recurrent-write lesion.

The independent verifier recomputed the capture parity, every linked native
site, role probes and tamper controls, interpreter restart identity, field
emission ownership, graph donor/control pairs, recurrent byte ownership, and
the top-level digest. The verification status is `PASS`.

The retained receipt is
`_diag/universal-interpreter-native-program-27b-iq1s-20260917-r2/native-program-receipt.json`
with content digest
`0d6ed41fe938b2e8b24b63412f4a52ee17169c712976825ac3112ef7af806847`.
Reproduce and verify it with:

```powershell
python run_cassi_universal_interpreter_native.py --root _diag/universal-interpreter-native-program-27b-iq1s-20260917-r2 --model Qwen3.8-27B-UD-IQ1_S.gguf --gpu-layers 99 --quantization IQ1_S --adapter-key qwen38-27b-iq1s/layer-input-mid-v1 --expected-model-sha256 3895b6eaa91e705c06ad1938d16c22e86f073c6a67df86260a1da79be3d1f887 --output _diag/universal-interpreter-native-program-27b-iq1s-20260917-r2/compact-receipt.json
python verify_cassi_universal_interpreter_native.py --run-dir _diag/universal-interpreter-native-program-27b-iq1s-20260917-r2
python -m unittest -v test_cassi_universal_interpreter_native_roles.py
```

This extends the measured native ownership result from the 0.8B reference
model to the new 27B IQ1_S model. It establishes reach into the declared native
readout and partial recurrent write ownership; it is not a claim of open-domain
language quality or replacement of the full transformer state.

## 2026-09-17 native intervention ladder on 27B IQ1_S

The downloaded one-bit target now has a matched native intervention ladder, not
only a single displacement demonstration. Every arm uses the same 20-token
prompt, the same 221,184-float predecessor field state, the same layer-32
`layer_input` readout, and a two-step decode. The nine arms sweep additive
output-norm dose (`0`, `0.25`, `0.5`, `1.0`), recurrent state-row dose
(`0`, `0.25`, `0.5`, `1.0` with the zero arm as the suppressed-model lesion),
and the field-owned LM-head placement. The model SHA-256 is
`3895b6eaa91e705c06ad1938d16c22e86f073c6a67df86260a1da79be3d1f887`; the
runtime SHA-256 is
`a6d36f1a5d6d02568283850cc8c0ecd4acc5b138e794d1ad47163a3907fa0afa`.

The additive route is live and dose-ordered. Relative to the zero-dose
identity arm, final-logit L2 is `0`, `17.5715268262`, `34.9095652866`, and
`69.4215082024` at doses `0`, `0.25`, `0.5`, and `1.0`. The model remains the
logit and state owner on this placement; the top token remains `271` while
the decision gap rises from `1.4112300873` to `1.7718887329`.

The recurrent route separates the lesion from field ownership. The
suppressed-model lesion owns zero field coordinates; each positive substitute
owns `5,120` of the `10,240` recurrent-row coordinates (`20,480` field bytes
and `20,480` model bytes) and names `field` as the state-write owner. Relative
to the lesion, the final-logit L2 values are `353.1128917015`, `261.4512563584`,
and `247.8605346612` for substitute doses `0.25`, `0.5`, and `1.0`. The
response decreases across this recurrent dose ladder; all three positive
arms are live and keep the model as the output owner.

The LM-head placement is the strongest displacement arm: the field owns both
the output and logits, the model reads zero logits, and two field-logit vectors
are read. Its final-logit L2 against the additive identity is
`2178.8179121514`; the field-selected top token is `109110` with a gap of
`0.00004312396`. This is a placement result and an ownership result, not a
language-quality claim.

The ladder runner is `run_cassi_native_intervention_ladder.py`; its defaults
select `Qwen3.8-27B-UD-IQ1_S.gguf`, the b8 Vulkan runtime, and the retained
27B source state. The independent verifier is
`verify_cassi_native_intervention_ladder.py`. The retained receipt is
`_diag/native-intervention-ladder-27b-iq1s-20260917/intervention-ladder-receipt.json`
with content digest
`cdd47732771b7679f8920f69177a37b6d878760dfdc048925c2f19034f4b6fcc`.
The verifier reports `PASS`, and a mutation control changed one logits byte
and was rejected by the linked-artifact digest check.

Reproduce the ladder and verify it with:

```powershell
python run_cassi_native_intervention_ladder.py
python verify_cassi_native_intervention_ladder.py --run-dir _diag/native-intervention-ladder-27b-iq1s-20260917
```

This extends the 27B result from a single native reach demonstration to a
measured placement-and-dose surface: additive steering scales with dose,
recurrent state ownership is partial and causal, and LM-head ownership is
field-complete at the declared output boundary.



## 2026-09-17 universal interpreter continuing-world composition

The packet-aware CassiFI work loop is now connected to the universal interpreter
through one bounded task and evidence handoff. The program is
`run_cassi_universal_interpreter_program.py`; its independent receipt verifier
is `verify_cassi_universal_interpreter_program.py`. The retained receipt is
`_diag/universal-interpreter-program-20260917.json` with content digest
`3c7c696bac8e75eed694ab6bf087a69801927d041fc5f323d88230731d2727cc`.

The continuing workshop episode starts from premise `2.0`, pauses after a
resident child return, corrects the premise to `5.0`, repairs and reopens the
episode, dispatches baseline/hierarchy/static/live/shuffled/acquired selection
methods, forces one coarse-to-fine refinement, and exercises admitted,
out-of-span, and unknown-source controls. A nonzero successor row from the
retained packet continuation is hash-bound into the next boundary rather than
reconstructed from a diagnostic hash.

The fixed adapter coordinate carries that row into one
`UniversalLLMInterpreter` `QiFieldState.field`. A meaning for the corrected task
is learned once, read on a held-out trace, read again through a distinct model
identity using the same declared adapter coordinate, and recovered after exact
restart. All three deliveries are field-owned, the meaning ledger contains one
entry, and no native fallback is used.

The receipt names the ownership boundary directly: the packet world retains
its regional workspace, while the interpreter retains its own single adaptive
`QiFieldState.field`; the bridge carries task, source, and bounded trace
metadata only. This is the completed composition increment, not a claim that
the two adaptive surfaces are one tensor or that the fixture adapters establish
semantic alignment. The dedicated native Qwen receipt remains the evidence for
the graph-native displacement routes.

The verifier does not rerun the scenario or import the runner. It recomputes
the content digest and activation identities, checks the packet-to-interpreter
trace and source handoff, and checks the persisted packet head, two-model
registry, current interpreter generation, and exactly-once meaning ledger. The
program and independent verification both pass.

## 2026-09-17 universal interpreter full twelve-step program

The complete bounded universal-interpreter episode is retained under
`_diag/universal-interpreter-full-program-native-shared-strict-20260917/`.
The runner is `run_cassi_universal_interpreter_full_program.py`; the
independent verifier is `verify_cassi_universal_interpreter_full_program.py`.
The strict full receipt digest is
`dfa05a3505d7effec22a5bd15a6055ea813be7890e1a157751c6c9dc175afe52`, and the
verifier reports `PASS` with six immutable field branches and no errors.

One persistent structured field acquires an affine base-plus-delay relation
from two prospective calibration predictions, applies it to new participant
`beta`, parses a fixed bounded language request, and performs the arithmetic
and numeric emission without model calls. A correction changes the delay
coefficient from `3` to `2`; the dependent beta prediction and plan repair
from `13` to `11`, while an unrelated safety meaning remains field-owned.
Actual unfinished work is journaled as pending, the process closes and
reopens, and exactly one simulation effect is published.

The same field meaning transfers to a replacement model identity on held-out
participant `gamma`. An isolated branch revokes only the corrected relation:
the relation query loses support while the unrelated safety meaning remains.
The held-out field emission is numerically adequate on the corrected route.
The program then exposes a cap-regime gap (`17` predicted versus `9`
observed), acquires a bounded guard method, and compares it with the fixed
method under the same source, permissions, work, evidence-read, and
model-call allocation. The fixed method remains at `17`; the acquired guard
returns `9` after another interruption/reopen and preserves beta's `11`.

The strict native sibling
`_diag/universal-interpreter-native-shared-task-strict-20260917.json` is a
separate Qwen3.5-0.8B Vulkan measurement arm. It uses the same task ID,
question, and source revision, and was launched with
`--without-answer-bearing-target`. Its native receipt digest is
`f8f63ec7399e1c8fab20fcf20106b4f7658101545d4cfc9e9850a563ab6b9e5a`; the
independent native verifier passes. The native logits remain measurement
evidence and are not supplied as the structured field's semantic target. The
strict full-program receipt is
`_diag/universal-interpreter-full-program-native-shared-strict-20260917.json`
with digest
`dfa05a3505d7effec22a5bd15a6055ea813be7890e1a157751c6c9dc175afe52`; its
independent verifier also passes. This closes the twelve-step bounded
integration without claiming open-domain language, architecture-wide semantic
alignment, or unrestricted general intelligence.



## Executable capability apprenticeship design

The [apprenticeship design](LATENT-REASONING-DESIGN.md#executable-capability-apprenticeship)
specifies the next increment: learn restricted SQLite transformations from
documentation, attributed model proposals, and actual local execution, then
apply the retained rules to unfamiliar inputs without a model or SQLite
executing the learner's answer. All acquired rules, request constructions,
native mappings, and unfinished work belong to the existing regional owner.

The design separates typed computation, learned language, model-assisted
interpretation, active study, and actual model replacement. Text-only and
native-observation teaching receive matched exposure, with shuffled-trace and
selective-knowledge-loss controls. Generic sequence execution and prospective
acquisition are implementation work; current exact transition lookup is not
SQL competence.

SQLite subject feasibility is exercised in
[`_diag/sqlite-apprenticeship-design-20260917/semantics.json`](_diag/sqlite-apprenticeship-design-20260917/semantics.json):
eleven illustrative cases and 1,364 tiny-domain oracle/reference comparisons
with zero mismatches.

The current executable apprenticeship receipt is
[`_diag/sqlite-apprenticeship-native-components-20260918-v14e/sqlite-apprenticeship.json`](_diag/sqlite-apprenticeship-native-components-20260918-v14e/sqlite-apprenticeship.json),
SHA-256
`41cea47486a71cc17794da0d9fd9edd1cdbfe006c3948383e56fcf553ce3e906`.
It acquires five reusable typed components from the coupled native teacher and
admits eight guarded recipe constructions rooted to the same native identity.
It transfers seven held-out arrangements and matches an independently executed
SQLite oracle on every route. Before compilation, the field resolves the
selected live recipe through a recipe-only interpretation; `weave`,
`recursive-3`, and `recursive-4` return `[3, 6, 7]`, `[9, 8, 7]`, and
`[10, 9, 8, 6]`. Revoking `weave` produces a recipe-only support gap while
`recursive-3` and the underlying `stage_order` component remain usable;
reacquisition returns a new recipe version and restores the route. The
independent verifier rejects both native binding and live-recipe mutations.
This is a bounded typed-composition result, not open-domain SQL synthesis.

The v12 extension is retained at
[`_diag/sqlite-apprenticeship-native-components-20260918-v12b/sqlite-apprenticeship.json`](_diag/sqlite-apprenticeship-native-components-20260918-v12b/sqlite-apprenticeship.json),
SHA-256
`eb93ac355a3e523222485526feba9b40c9317b2596346670c143d8983018e4f7`.
It preserves the five separately acquired component references while adding a
three-level nested arrangement (`nested-reapply`) and a fourth held-out
SQLite/oracle comparison. The field returns `[8, 7, 6, 3]` on the nested
case. Sequentially revoking `order_limit` and then `stage_order` produces two
distinct support gaps; each component is reacquired under a new version, the
unrelated component remains supported after the first repair, and the final
construction remains identical after reopening. Native teacher counters and
the independent mutation control remain unchanged from the measured v11
boundary. This is a depth-and-recovery increment within the declared typed
language boundary, not an open-domain SQL result.

The v13 depth-transfer extension is retained at
[`_diag/sqlite-apprenticeship-native-components-20260918-v13c/sqlite-apprenticeship.json`](_diag/sqlite-apprenticeship-native-components-20260918-v13c/sqlite-apprenticeship.json),
SHA-256
`15f81eb320578b3d5ac8482e3409f13b860486dcde9370420ec11a60e74d42d4`.
It keeps the same five separately acquired component references and
five-role construction, then transfers two unseen arrangement values:
`recursive-3` builds three nested
`filter → project → order → limit` reapplications, while `recursive-4`
builds four. The field returns `[9, 8, 7]` and `[10, 9, 8, 6]`, matching
independent SQLite oracles; the four earlier held-out routes continue to
match. The independent verifier checks the recursive AST chain itself.
Sequential loss and versioned reacquisition of `order_limit` and then
`stage_order` still preserves component-only support and exact final reopen
identity. This is a depth-transfer increment inside the declared typed
language boundary, not an open-domain SQL result.

## CassiFI work-memory evaluation (2026-09-08)

The 2026-09-08 campaign exercises the current CassiFI owner as an explicitly
off-graph work-memory boundary around separately restarted copies of the same
hash-pinned local Qwen server. The two arms share one frozen 17-case protocol:
direct recall, multi-record calculations and policy application, an early and
late longitudinal anchor, a same-domain interference control, a corrected
fact, memory-independent controls, an unknown-fact control, and reuse of a
result learned during the evaluation.

Before inference, the field admitted 117 source revisions, including 96
distractors and two corrections. It retained 115 active revisions, returned
the early anchor correctly at every 16-record checkpoint through all 96
distractors, excluded both superseded revisions, and reproduced its complete
state receipt exactly after preparation, after evaluation, and after learning
the in-session result. The final state remained finite; its largest workspace
coordinate was `4.713629385640803` and its largest relation-chart coordinate
was `0.4471991360905908`, below the implementation bound of 64.

On exact structured outputs, the no-memory baseline passed `2/17`; the
memory arm passed `8/17`. All 13 memory-dependent cases retrieved exactly the
frozen active source set, and six became correct. The four cases that should
not retrieve memory all returned an empty selection; both arms passed two of
them. There were no regressions. The nine shared failures are concentrated in
the deliberately short 96/128-token answer budget: Qwen frequently consumed
the budget before emitting a complete JSON value, including all five
multi-step reasoning cases. This is therefore evidence that the current field
memory preserves, selects, corrects, and exposes useful work facts; it is not
evidence that the field performs natural-language reasoning or token emission.

The native Qi step used by both arms remains the single `[S,9M,B]` state named
by the CassiQwen charter. The refresh implements four-scale read availability,
guarded write, bounded Yang/Yin evolution, epsilon-memory update, and
inter-scale consolidation within those nine components. It does not introduce
the CassiFI resonant workspace, float64 GMRES solver, or another adaptive
sidecar into the native graph. A 10,000-event CPU/Vulkan smoke remained finite
and bounded with one-event maximum absolute disagreement
`5.45696821e-11` and long-horizon maximum disagreement `0.00221395493`
against the declared `0.005` gate.

Machine-readable evidence is under
`_diag/cassifi-qwen-workcases-20260908/`: `protocol.json`, `prepare.json`,
`baseline.json`, `field.json`, `analysis.json`,
`independent-verification.json`, `prior-campaign-comparison.json`,
`representative-transcripts.txt`, and
`capability-and-memory-evolution.png`. The independent verifier recomputed
1,334 invariants with zero failures. The older 2026-09-07 campaign used
different cases, arm semantics, and schemas, so its numbers are retained as a
separate observation rather than treated as a matched statistical delta.

## CassiTheory corpus-memory stress evaluation (2026-09-09)

The 2026-09-09 campaign extends the realistic work evaluation from short
records to a `1,668,965`-byte technical corpus: 14 current CassiTheory
documents split into 352 exact source chunks, followed by six difficult
multi-document synthesis questions. It runs four separately restarted copies
of the same hash-pinned Qwen3.5-0.8B Vulkan server: a native-only diagnostic,
the shared answer contract with empty memory, CassiFI field recall, and a
literal-text placebo. Field recall and placebo use the same ordered source
chunks and have byte-identical answer-prompt hashes.

The persistence mechanics passed. Ingestion advanced from 0 to 352 active
revisions and from 11,944 to 211,732,657 persistent bytes. State identities
changed at every recorded 25-chunk interval, remained finite, and reproduced
exactly after close/reopen. Six query episodes returned 60/60 requested
payloads byte-for-byte, did not change the trained state during answer
generation, and reproduced the post-query state after another restart. The
finished persistence layer occupied 225,245,373 bytes, `134.96×` the source
corpus size. Directly reported numeric field arrays accounted for only 328,344
bytes: 101,376 chart-field bytes plus a 226,968-byte query workspace. Most of
the amplification is therefore exact records, journals, checkpoints, and
associated durability structures rather than field tensors. Prepared-branch
occupancy reached 60 of the configured 64 slots.

The semantic result is negative. Both planners were Qwen JSON-schema calls;
they chose every document and chunk identifier before CassiFI performed an
exact keyed lookup. Every question selected the ten-chunk ceiling. Relevant
documents appeared for 6/6 questions and required-source coverage averaged
`0.667`, but no question recovered its exact required source set, one missed
all relevant chunks, and the selections included 42 irrelevant documents.
More fundamentally, every record was deposited with the same constant
`memory.anchor=1`, `memory.signal=1` observation. Each of the 352 context-keyed
source charts received exactly one such observation, leaving event count as
the only field-side degree of freedom; they consequently had one distinct
numeric-field hash and one collision class of size 352. Recall ran one live,
finite field transition per lookup but resolved the supplied identifier
through exact guard/context equality. This run therefore demonstrates durable
source storage and exact retrieval plumbing, not field-owned semantic memory
or field-conditioned selection.

Answer quality is recorded as `NULL`. Empty memory, field recall, and literal
placebo use the same answer instructions and parameter values; field and
placebo additionally have identical prompts. Nevertheless, their six answers
matched exactly 0/6 times. A same-process replay of the fixed-charge prompt
with the same prompt hash, `temperature=0`, and seed `424242` produced five
different answers across the stored field/placebo samples and three fresh
replays. Completion lengths were `1,944`, `1,019`, `1,442`, `1,069`, and
`57,218` tokens; the last exhausted the available context. This fails the
decode-determinism precondition, so claims, citations, completion length, and
timing deltas between single generations are noise-bounded rather than causal.
The deterministic input cost is still measurable: retrieved context raised
total prompt tokens from 1,252 to 63,222, an overhead of 61,970 tokens, and
field versus literal-text prompt cost differed by zero.

The ownership receipt records zero native state, layer, operation, output-row,
or token displacement. CassiFI owns 352 durable record updates and performs 60
exact keyed source exposures; Qwen owns all 60 semantic source selections,
natural-language reasoning, and emitted tokens. The campaign attains no
intervention-ladder rung above additive off-graph storage, and specifically
does not reach rung 2 field-conditioned selection. Full answers and
machine-readable receipts are under the machine-local artifact path
`D:/cassi-theory-recall-0.8b-final8/`. Re-run the independent artifact verifier
on this workstation with:

```text
python -B research/verify_cassi_theory_recall.py --run-dir D:/cassi-theory-recall-0.8b-final8
```

The verifier independently reopens the persisted field, re-derives protocol,
corpus, runtime, prompt, retrieval, aggregate, ownership, collision, and input
cost invariants, and confirms the failed shared-parameter replay determinism gate.

## Field-native raw-event acquisition experiment

The 2026-09-09 isolated raw-event experiment tests whether a Cassi field can
acquire a reusable transition from experience without caller-supplied semantic
roles, a learned sidecar, or a model fallback. `cassi_raw_event_field.py` owns
one persistent `QiFieldState.field` tensor with shape `[4, 9216, 1]`.
The fixed boundary accepts reset-bounded streams of unordered opaque byte
spans. Event order is semantic; span presentation order is not. A witnessed
`observation -> action -> outcome` transition writes a fixed holographic
key/output binding into provisional field scales and, only when explicitly
requested, consolidated field scales. Prediction, depth-two planning,
history-conditioned recall, and targeted interventions all read that same
tensor.

The three-seed randomized campaign passed all measured cases. Each seed learned
two independently presented single-step transitions and then completed an
unseen entity's withheld two-action route without seeing that complete route.
All `3/3` compositions succeeded. The same current observation and action
resolved to two different outcomes under two learned prior-event histories in
all `3/3` temporal cases; removing the history field made both unresolved.
Three symmetric contradictory bindings were rejected as ambiguous rather than
guessed. Unseen actions remained unresolved.

The durable store committed each event exactly once, atomically paired its
journal and field checkpoint, and rejected conflicting same-sequence retries
without changing the predecessor. A restart in the middle of a pending action
restored that action and accepted its later outcome; all `3/3` final field
identities reproduced exactly after another restart. Episode-scoped revocation
and corrected replay passed `3/3`. A full checkpoint corruption was rejected,
and each capacity-exhaustion control preserved its predecessor.

The field remained finite across 3,072 inference queries. The maximum absolute
coordinate was `0.14309452105019604` against the configured energy limit of
`32`; the fixed field occupied `294,912` bytes. The receipt records 12
field-owned committed predictions and three field-owned plans, with zero Qwen
calls, teacher calls, learned sidecars, Qwen weight reads, or claimed
native-Qwen displacement. A targeted relation intervention changed a
supported decision to unresolved while preserving a separately trained,
unrelated relation and
its exact output.

The promotion control also passed `3/3`: with `promote=False`, repeated
experience remained solely provisional, survived clearing the already-empty
consolidated banks, and became unresolved when provisional banks were removed.
The same transition with promotion enabled remained supported after
provisional-bank removal. Paired static and dynamically evolved readouts
returned the same supported payload in `3/3` cases and neither mutated the
trained field.

This is evidence for bounded relational acquisition and causal use of learned
field state, not autonomous discovery of all useful structure. The
single-changed-span copy operator, byte framing, Qi chirp codebook, and
depth-first composition algorithm remain fixed machinery. Packets are limited
to three spans and sixteen encoded bytes; plans search only caller-authorized
actions to depth two. The experiment is isolated and does not alter the adopted
terminal or provider.

Run the campaign and its focused behavioral contracts with:

```text
python -B run_cassi_raw_event_scenario.py --seeds 101 202 303 --out-dir _diag/raw-event-acquisition
python -B -m unittest -v test_cassi_raw_event_field.py
```

The machine-readable v2 receipt is
`_diag/raw-event-acquisition/verification.json`, using schema
`cassi.raw-event-acquisition-scenario.v2` and self-hashed as
`b85d63a3ccd2d291235d56f110e2c1e252f2a9507a982e0aa7b0bff9cd6b8e41`.

## Field-native causal acquisition and online learning

`cassi_causal_event_field.py` adds a reset-aware causal protocol around the
raw-event field. It does not receive the correct action. At each step it senses
the current opaque packet, chooses from the actions actually available, commits
that action before the consequence exists, and only then observes the world's
consequence. A requested outcome packet supplies the goal used for bounded
route search, not a label for which action to take.

The learning rule is prediction-error gated. A relation with no supported
prediction enters the ordinary provisional field bank. If a supported ordinary
prediction is wrong and an immediately preceding reset-bounded observation is
available, the residual enters the conditional provisional bank. Promotion is
strictly prospective: a later reset-bounded episode may move that same relation
into its consolidated bank only when the provisional witness was already
present at that episode's entry. A same-episode replay may be read, but it
neither learns nor promotes. Correctly predicted events do not write, and an
identical unconfirmed retry does not
compound the provisional wave. Promotion receipts identify the confirmation
episode, witness bank, witness-state hash, pre-consequence state, and whether
the witness was present at confirmation-episode entry. All
readouts, first-action choices, conditional branches, and route plans are
computed from the one `QiFieldState.field`; no replay table, action-value table,
learned sidecar, teacher, or Qwen path participates.

The causal operator owns a dedicated `_CausalFieldKernel` composition kernel;
it does not subclass `RawEventLearner` and therefore cannot inherit the raw
`apply(event)` mutation protocol. The private raw learner is used only for the
fixed Qi tensor primitives and field checkpoint payload. The public `state`
property returns a detached tensor snapshot; mutating that object cannot change
the learner, including while an action is pending. Live state references and
validated replacements remain private to the causal kernel. Outcome admission
is transactional across both the field and causal context: it evolves and
validates a candidate, computes the receipt against that candidate, and commits
field plus event sequence only after every fallible step succeeds. The
capacity-rejection control preserves the complete checkpoint byte-for-byte,
including its pending action.

The 2026-09-09 evaluation used 20 independently randomized worlds
(`101` through `120`) and a matched frozen-field control. Each world ran 18
closed-loop episodes with three opaque actions, one useful action, two distinct
failure consequences, and canonical action identities whose meanings were
randomized per seed. In the first six episodes, after learning was already
allowed to occur within that window, the online field completed the goal at a
mean rate of `0.7583333333333333`. In the final six it completed the goal at
`1.0`; the frozen control remained at `0.3333333333333333`. The online arms
committed 311 field-owned first actions. Frozen fields remained byte-identical
to a fresh field.

The controls distinguish causal acquisition from replay bookkeeping:

- Correct action/outcome pairing recovered `1.0` true-world accuracy; changing
  only the pairing reduced accuracy to `0.0`.
- Mismatch-gated learning made two conditional writes in each seven-event
  history stream, versus six for the always-conditional control and zero for
  the unconditional-only control. The gated and always-conditional arms both
  recovered both branches; the unconditional-only arm could not represent the
  split.
- A deliberately colliding ordinary relation split into two correct
  history-conditioned branches. Removing only one relation wave changed only
  its target decision; removing a comparably structured unrelated wave did
  not. Exact checkpoint restoration recovered the original decision.
- Three separately acquired transitions composed into a withheld three-action
  route. Starting from its middle state produced the correct two-action suffix.
  The fixed changed-span operator transferred a two-step route to a withheld
  entity identifier, while an ungrounded renamed action remained unresolved.
- In a hidden-state task, the field selected a caller-authorized inspection
  action, used its observed consequence to select the correct repair, and
  reached the goal. With no inspection action available it abstained from a
  field-owned choice.

Continual memory was exercised by adding eight unrelated relations one at a
time and rechecking every predecessor after every addition. All eight remained
exact in all 20 worlds. A history-conditioned correction preserved the original
unconditioned relation and all seven unrelated relations. The campaign then
checkpointed immediately after an action but before its consequence, restored
into a fresh learner under the exact expected profile, and verified a
byte-identical pre-outcome checkpoint round trip plus the same successor field
after the consequence in all 20 worlds. The focused checkpoint contract also
verified equal outcome receipts and byte-identical post-outcome checkpoints.
Checkpoint v2 hashes the complete canonical causal header as well as the nested
protocol context and raw-field payload; payload tampering, causal-header
tampering, cross-policy restoration, and disagreement between the causal and
raw-field acquisition profiles were rejected in every world. Checkpoints
remained about `2.37` MB, and 256 read-only inference queries per
world left the trained field unchanged.

Capacity was measured rather than inferred. Each profile was asked to acquire
and retain 12 randomized relations in every one of the 20 worlds, checking all
predecessors after every addition:

| Field profile | Field bytes | Exact final relations | Seeds exact at every step | Loss checks |
|---|---:|---:|---:|---:|
| 512-wide, 2 channels | 294,912 | 46/240 | 0/20 | 1,205 |
| 1,024-wide, 4 channels | 589,824 | 76/240 | 0/20 | 731 |
| 2,048-wide, 8 channels | 1,179,648 | 229/240 | 11/20 | 11 |
| 4,096-wide, 8 channels | 2,359,296 | 240/240 | 20/20 | 0 |

The selected 4,096-wide profile therefore supports the measured 12-relation
workload; this is not an unbounded-capacity claim. Its largest observed field
coordinate was `0.17152634189408622`, and every campaign state was finite.
Across the 20 worlds, all closed-loop, policy, corrupted-pairing, collision,
intervention, composition, transfer, inquiry, correction, restart, causal
header integrity, expected-profile, atomic-capacity, inference, and capacity
cases passed. Fourteen focused behavioral contracts also pass. The ownership
receipt records zero Qwen calls, teacher calls, learned sidecars, native-state
displacement, native operation/layer/output-row skipping, and Qwen weight
reads.

This remains a bounded opaque-event learner, not open-vocabulary language
understanding. Packet framing, the Qi chirp codebook, sparse keyed masks,
single-changed-span copy binding, exact packet comparison, canonical
episode-rotated exploration, and breadth-first route search are fixed. Packets
are limited to three spans of at most eight bytes each and at most sixteen
encoded bytes total. Route depth, expansions, and authorized actions are
bounded, and the system does not learn which action is informational.

Run the causal campaign and its focused contracts with:

```text
python -B run_cassi_causal_acquisition.py --seeds 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119 120 --output _diag/causal-acquisition/verification.json
python -B -m unittest -v test_cassi_causal_acquisition.py
```

The machine-readable receipt is
`_diag/causal-acquisition/verification.json`, uses schema
`cassi.causal-acquisition-campaign.v2`, and is self-hashed as
`0dae6d52d93c5b3d5557c91f2906b21c4eb5efa2ab99f0fbc587334687eb347a`.

## Grounded causal-language acquisition

`cassi_causal_language.py` is a strict UTF-8 boundary and deterministic
grounded world around the causal Qi learner. It adds no learned lexer,
embedding, vocabulary matrix, transition table, or language model. A task
supplies a bounded pre-commit objective and available action packets, but not
the correct action or the expected consequence. This is explicitly
goal-directed bounded control: the field route-searches toward the declared
objective, commits first, and sees the world's result afterward. Construction,
entity, state, action, and explicit-role markers are fixed protocol framing;
acquired action meanings remain only in `QiFieldState.field`.

The 2026-09-09 campaign ran 20 randomized worlds (`301` through `320`) with a
matched frozen-field control. Each world acquired three one-character
constructions over six closed-loop episodes each: two independently grounded
surface forms for one action and one form for another. Across the 60
construction streams, successful task completion by episode was
`15, 29, 47, 60, 60, 60`; field-owned choices were
`0, 15, 29, 47, 60, 60`. After each construction was added, retained supported
relations totaled `20/20`, `40/40`, and `59/60`. Seed `304` lost one of its
first two exact relations after the third was acquired, so the measured exact
recall result is `59/60`, not a perfect-memory claim.
Under the explicit per-world capability criteria, `19/20` worlds pass. The
receipt status is therefore `PARTIAL`, not `PASS`; seed `304` is the measured
failure.


The evaluation separates capabilities that would otherwise be easy to
conflate:

| Probe | Measured result | Interpretation |
|---|---:|---|
| Exact seen-string recall | 59/60 | One interference loss after the third acquisition |
| Fixed held-entity renaming | 59/60 | Copy-binding transfer, reported separately from recombination |
| Independently grounded paraphrase transfer | 39/40 | Both forms were taught; equivalence was not inferred |
| Unseen commutative two-component composition | 20/20 | Two separately grounded construction spans formed an unordered multiset, then a field-owned two-action route reached a two-success goal; this is not sequence composition |
| Unknown construction execution and abstention | 20/20 | An exploratory action committed, the world returned deterministic unknown failure without consulting a correct-action oracle, and no unsupported field-owned decision was claimed |
| Unsupported goal abstention | 20/20 | No unsupported field-owned route |
| Canonically equivalent Unicode variant | 20/20 abstained | Normalization is deliberately `none`; precomposed and decomposed UTF-8 are distinct |
| Held-out swapped event sequence before exposure | 20/20 abstained | The explicit `<subject|relation|object>` frame, including end-expression `>`, remained distinct before learning; no syntactic-generalization claim |
| Forward and swapped sequences after separate exposure | 40/40 | Each fixed-position sequence was acquired independently, and the world parsed the committed observation to derive which action could succeed |
| Corrupted action/outcome causal control | 20/20 `EXPECTED_NEGATIVE` | All fields reproduced the deliberately corrupted experience (`0.0` true-world accuracy); this is a measured failure control, not a passed capability |

The ambiguity arm learned two discourse-conditioned clarification branches.
All 40 context-bearing probes selected the authorized inquiry action, all 20
world pairs produced context-specific plans, and both A and B continuations
committed their separately grounded repairs before the world computed the
resulting outcome. Removing the inquiry candidate
made all 20 decisions non-field-owned. With discourse history omitted, all 20
still selected the generic inquiry rather than guessing a terminal action; the
revealed consequence remained necessary to choose the repair. This
history-free generic-inquiry result is reported separately and is not evidence
that inquiry selection itself requires discourse history.

Persistence was exercised at the harder boundary: after a non-null discourse
history, an ambiguous observation, and a committed but unanswered inquiry.
All 20 approximately `2.378` MB checkpoints restored byte-for-byte into fresh
learners; the restored and uninterrupted continuations selected the same
context-sensitive repair and finished with byte-identical checkpoints. A
separate relation intervention removed the named construction in 20/20 worlds,
preserved the unrelated construction in 20/20, and preserved the independently
grounded paraphrase in 19/20, matching the same seed-`304` interference loss.

All field states remained finite. Read-only evaluation left trained field
state unchanged. The receipt reports 349 field-owned actions in the lexical
and fixed-sequence training streams, zero Qwen calls, zero teacher calls, and
no native-Qwen displacement. The component probe is commutative span
composition, while the ordered arm is a fixed-position exact-sequence
diagnostic; neither establishes learned syntax or temporal language
composition. This is grounded bounded action learning, not open-vocabulary
language understanding or free-text generation.

Run the campaign and focused contracts with:

```text
python -B run_cassi_causal_language.py --seeds 301 302 303 304 305 306 307 308 309 310 311 312 313 314 315 316 317 318 319 320 --output _diag/causal-language/verification.json
python -B -m unittest -v test_cassi_causal_language.py
```

The machine-readable receipt is
`_diag/causal-language/verification.json`, uses schema
`cassi.causal-language-campaign.v2`, has measured status `PARTIAL`, and is
self-hashed as
`55810488ab16c0be45c6474379e8113ced236d4b56c05ada7d7f2db12f0bf31a`.

The focused unittest includes a one-seed `run((303,))` receipt that passes its
contracts. That local PASS verifies the harness and does not upgrade the
20-world campaign: its independently stored status remains `PARTIAL` because
seed `304` loses one exact relation.

## Direct Qi-native runtime and offline organism research

`cassi_qi_field.py` and `cassi_field_language.py` are the adopted computation.
The only adaptive persistent value in a session is `QiFieldState.field` with
logical layout `[S,9M,B]`. The fixed boundary has 260 events: 256 raw UTF-8
bytes plus `end_turn`, `system`, `user`, and `assistant`.

Corpus experience lives inside the common-mode half of the same tensor as
ordered phase-coded trajectories. The differential half carries rolling live
histories at 16, 32, 64, and 128-event horizons. At emission, the field compares
those live histories with every stored circulation position, accumulates
positive outgoing port work, and commits the winning byte or control through a
negative characteristic reaction. The committed event advances the live
trajectory as an efference copy; it is never replayed as inbound sensing.

There is no count lattice, trie, vocabulary, embedding, learned head, feature
projection, optimizer, backpropagation path, or probabilistic sampler. The only
output filter is the fixed UTF-8 protocol-validity mask.

`cassi_organism.py`, `cassi_organism_law.py`, and
`cassi_organism_teacher.py` are offline research references, not the adopted
runtime. The learned language sector and its parameter ranges have been
removed. The remaining organism stack still contains engineered sectors and a
conventional learned world-model bridge, so it is not labelled Cassi-native and
is never imported by the terminal or provider.

`cassi_conscious_chat.py` is the terminal composition root. It restores one Qi
state, senses only the new user turn, emits through the active Qi text port, and
atomically checkpoints the successor state with bounded non-adaptive transcript
metadata. The obsolete conscious-agent/persistence stack that depended on the
learned organism language sector and world-model bridge is preserved only for
source recovery under
`_diag/cassi-qi-native/obsolete-conscious-stack/`; it is not importable from
the adopted root runtime.

`cassi_persistent_provider.py` exposes the same direct Qi path through an
OpenAI-compatible loopback service. Per-session Qi checkpoints are written
atomically and restored across process restart. Non-streaming and streaming
responses carry state, field-text, presentation, and displacement receipt
hashes. Requests for temperature sampling, top-k/top-p truncation, or sampling
seeds fail closed. There is no Qwen or conventional-model fallback.

`cassi_field_agent.py` closes the grounded language loop over
`DeterministicQiWorld`. Exact ordered proprioceptive bytes, colored-object
coordinates, user utterances, temporary reference cues, field-owned action,
identity, relation, change, cause, and temporal-order frames traverse the same
trajectory field. All five registered actions are evaluated from the same
predecessor state; the unique positive-margin winner is committed before the
world consequence exists. A prediction query commits that proposed action and
its learned successor change without stepping the world.

For spatial questions, the question trajectory resolves one of three relation
families and bounded live differential modes hold the raw object coordinates; a
fixed resonance probe resolves the two candidates in that field-selected
family. Binding explicitly consolidates a name and its subject/comparison cues
into common-mode trajectories. The active pronoun referent occupies a
persistent one-hot differential register.

Every executed action writes its exact predecessor, successor, action, and
validity marker into the same live differential field. Separate change and
cause ports render explanations, while a learned before/after target and a
register probe identify the requested state in forward or reversed
presentation order. Session metadata stores only counters and the world
snapshot, never names, an entity map, or a transition table. Failed saves roll
the world back; restarts continue the exact successor field, world state,
referents, and last transition. Prediction, spatial, reference, explanation,
and ordering queries leave trained memory unchanged.

Embodiment currently uses the deterministic Python reference world. It does
not add a CassiCosmos scene, Godot script, shader, 7599 mind-engine operation,
7273 mind-runtime endpoint, or mechanical actuator path.

## Qi multi-scale field and associative memory

`cassi_qi_field.py` is the canonical parameter-free Qi reference. Its sole
persistent adaptive value is `[S, 9*M, B]`: Yang/Yin position and velocity at
each scale plus the temporal imbalance accumulator used to derive coherence.
Qi is measured as phase flow (`J`, `q`, and `chi`); it is not a third stored
field. Fixed prime/quadratic-chirp codebooks map every scale into shared symbol
coordinates before cross-scale comparison and consolidation.

`cassi_qi_kv.py` wraps the same field with a bounded exact-recent ring and
supports `assist`, `compress`, and `replace` reads. The exact ring is ephemeral
and is deliberately absent from field-only checkpoints. The experimental loopback
daemon path is `cassi_field_daemon.py` protocol v2; the default-off
`cassi_f5_provider.py` is a separate opt-in experimental provider, not the live
conscious terminal or port-8086 service.

The matching native Qwen35 path is enabled with `--cassi-qi-field`; select its
field layer and fixed scale count with `--cassi-qi-field-layer N` and
`--cassi-qi-field-scales N`. `--cassi-qi-field-wave-modes N` sets how many
wave modes the field holds and `--cassi-qi-field-row-width N` sets how many
channels the substitution seam addresses, both defaulting to the current
values. `--cassi-qi-intervention mid` moves the live Qi
operation from the final hidden-state seam to immediately before the selected
Qwen layer. At that seam the graph executes
`inpL + alpha * first_n_embd(Qi_flux)`; `--cassi-qi-field-steps N` selects the
number of bounded field evolutions and `--cassi-qi-injection-scale F` selects
`alpha`. The defaults retain the final-seam path, one evolution, and unit
coupling. Mid-trunk mode is additive only and requires displacement level zero.
Baseline, legacy modal, single-scale field, and Qi paths remain mutually
exclusive.

`--cassi-qi-displacement N` raises that intervention from additive steering to
native removal at the selected layer. Level 3 suppresses the layer's
recurrent-state write, so the layer keeps the state it held and its own history
stops advancing there; level 4 additionally bypasses attention from that layer
on, level 5 bypasses the whole block, and level 6 emits from the field state
through the fixed deterministic transducer in place of the output projection.
Levels 4 and 5 leave the graph unable to produce text with a live field on the
27B, and level 6 is a different model, not a degraded one.
The field can also act on the generated token stream itself rather than only
on hidden-state or recurrent-state seams. `--cassi-qi-stream` adds the live
field's token score to every candidate before the normal sampling chain;
`--cassi-qi-stream-gain F` sets its signed strength. The optional
`--cassi-qi-stream-eog-gain F` adds a separate field-weighted bias to
end-of-generation tokens: positive values tend to make responses shorter,
negative values tend to preserve continuation. This is a token-level
intervention, so it can alter reasoning density and language style across
the whole generated sequence. Direct stream coupling uses CPU sampling
instead of backend sampling so the field score is applied before selection.

`--cassi-qi-field-dt F` sets the integrator step of the field itself, one bound
inside `cassi_qi_field_step.comp` (default `0.005`, the same step the CPU
reference uses). It is the field-capacity control: at `0.02` the 27B keeps its
open-ended continuation and the 16/17 memory arm with four answers changed, and
at `0.05` the field's own evolution degrades the memory-free arm to 4/17 while
the memory arm holds 11/17.

`--cassi-qi-read-absolute` reads the flux at the field's own magnitude instead of
at unit amplitude. The default readout divides each scale's differential by
`sqrt(rho)`, which is invariant to the state's overall scale, so a faded pattern
reads as a unit vector and its age survives nowhere in the readout. The absolute
read keeps the field's own size. It changes only what is reported and never what
evolves: on the 0.8B at layer 12 the field state is bit-identical with the flag on
and off (maximum absolute difference exactly `0.0`) while the logits move by
`1.8929` with a KL of `3.929e-2`.

`--cassi-qi-unwritten-latch` restricts the full-gain write latch to a mode that has
never been written. The default rule gives a full-gain write to every mode below
the energy floor, so a silent input multiplies a faded trace by `(1 - dt)` at every
token and drains it to zero instead of letting it decay at its own rate. The
restricted rule gives the full gain only to `rho == 0` and writes every other mode
through `structured_source * (1 - q)`. From a seed state holding `7605` written
modes, twenty-four continuation tokens take the default rule to `8757` written modes
on the additive channel and `12897` through the seam, while the restricted rule
holds `7605` and `10431`. The extra modes the default rule lights up are its own,
not the input's: a silent input has nothing to write, and the full-gain branch is
what turns a faded trace into one.

`--cassi-qi-scale-read-taper N` weights each scale of a mode's readout by
`exp(-N * scale * damping * dt)` against the mode's own damping and divides the
readout by the weighted sum. The pinned readout averages `chi` over the available
scales, so a mode reads at the same rate whatever symbol the bank gives it; the taper
reads each mode at the scales that resolve its own rate. It changes only what is
reported and never what evolves: the state successor is bit-identical to the pinned
run's at any taper, maximum absolute difference exactly `0.0`, while the seam arms move
`0.124` to `0.222` in logits at `-2`. The divisor also makes the flag exactly inert
when a readout has only one scale available, which is the regime the 0.8B probe's own
seed state occupies.

`--cassi-qi-mode-bank PATH` reads a raw F32 bank of exactly `mode_count` damping
symbols, one per mode, and replaces the ramp the field generates across
`[damping_min, damping_max]`. The loader sets both the op's damping bounds and its
mode-parameter bounds from the bank's own minimum and maximum, so the symbols reach
the integrate block unclipped. The symbols are a per-mode rate, and a mode's symbol
enters the step as `cassi_qi_clamp(abs(symbol), damping_min, damping_max)`, so a
bank that spans four decades of half-life is a bank whose readout is a mixture of
four decades of decay kernels rather than one near-permanent blend. Its effect is on
the state the step carries out rather than on the read taken from it, which the
probe below measures from both sides.

`research/train_field_bank.py` fits that bank. Kernels are measured from the exact
production rule through the port in `run_cassi_field_memory_study`, which is
validated against the op, rather than assumed to be `exp(-rate * age)`: a mode
leaves the readout through the energy floor and the shared read gate, so the
kernel is what the field actually delivers rather than what the symbol says.

The fit has two stages. Each candidate rate grid is measured once, with every bin
excited at once, so its kernel carries the shared gate; every grid is then measured
on the field and the grids are ranked by what the field realizes. Here that ranking
agrees with the model's, whose error never differs from the realized one by more than
a tenth of a percent, but the delivered grid is the field's and the receipt carries
both orders. Then the bin populations are solved against those kernels. The solve is
exact in the energy domain: modes do not couple, so the readout energy is the sum of
the per-mode energies and is linear in the populations whatever the gate and the floor
are doing, and only the profile, its square root, is nonlinear. A multiplicative
(Richardson-Lucy) update runs inside the grid search; the result is then polished by
SLSQP on the simplex, from the solved allocation and from eight random ones. The
polish is what closes the gap — the update stops at a mean log error of `0.242256` on
the winning grid and SLSQP takes that to `0.219390` — and the random starts are what
turn that number into a floor, since all nine starting points land on it.

```powershell
python research/train_field_bank.py --out _diag/field-bank/measured-32.bin --profile _diag/field-memory-study/distance-profile.json
python research/train_field_bank.py --out _diag/field-bank/power-law-32.bin --exponent 1.0
python research/train_field_bank.py --out _diag/field-bank/taper-m2.bin --profile _diag/field-memory-study/distance-profile.json --scale-read-taper -2
```

The first fits the model's own measured distance profile, so the field's memory
decays like the model's ability to use it. Its `6144` symbols span damping
`0.4480` to `375.0000`, and the bank is `24,576` bytes. Populations are laid out
inside `wave_mode_count`, the window that reaches the readout: all `3072` populated
modes sit inside that window and the other `3072` carry the slowest symbol, where
they contribute nothing, so allocating across the full `mode_count` spends half the
symbols on rates the readout never reads. Bins are contiguous blocks, not a stride:
the chirp index `(m^2 + m*p + 17*s) mod 16` cycles with period 16 in `m`, so any block
of 16 or more consecutive modes carries all 16 phases uniformly, where a stride would
phase-lock a bin. The allocation lands exactly on `wave_mode_count` by largest
remainder.

The fit spends two of its thirty-two bins: `61` modes at half-life `0.25` tokens and
`3011` at `373.6`. That the floor is reached from nine starting points makes this the
family's own optimum rather than a solve that stopped early, and it fixes the shape of
the residual — two rates behind one shared gate have to reproduce a profile spanning
four decades of age. The bank is therefore a slow memory with a small fast component,
`98` percent of its modes holding the long rate.

Over ages `16` to `1024` tokens the fitted bank tracks the model's profile at a
relative L1 of `0.2239` and a correlation of `0.9694`, with a decay exponent of
`0.699` against the model's own measured sensitivity slope of `0.72`. Ages `272`
to `658` match within one percent. Across the window the model's own importance
falls to `7.4` percent of its age-`16` value; the fitted bank reaches `11.4` percent
and the production ramp `23.1`, so the fit buys magnitude rather than ordering — over
the window both curves order the ages correctly, at rank correlation `0.9670` against
`0.9557`, and the difference is that the field forgets at closer to the model's own
rate. The production ramp is at `0.3278` and `0.9360` over the same window: it tracks
the bank to within a few percent as far as age `97`, then falls away faster and
reaches exactly `0.0000` at six consecutive ages from `272` to `568` before reviving
to `0.2306` at `1024`, so a faded memory that had gone silent comes back. The bank
holds the target's plateau there instead of dropping out of it.

Neither profile matches the model between ages `62` and `202`, where both sit `1.2`
to `1.8` times too high. That is the kernel family's own limit rather than a solve
that stopped early: on the winning grid SLSQP lands on `0.219390` from the delivered
allocation and from eight random ones, the field realizes `0.219420`, and the kernel
model is therefore accurate to a tenth of a percent while no population of these
kernels does better. The basin is genuinely shallow rather than flat: five of the
twelve grids reach a floor within one percent of the best and the winner still sits
`0.8` percent below the next, so the grid search is buying a real improvement with
little margin. A second residual remains at ages `762` to `1024`, where the readout
revives to `1.2`-`1.8` times the target.

The realized profile belongs to the bank's symbols rather than to the write that
excited them: three different write patterns give the delivered bank the same mean
log error to six decimals, `0.219420`, matching the port's own measurement of it.

The readout's gate is rate-independent by construction: it averages `chi` over the
available scales, so a mode reads at the same rate whatever symbol the bank gives it,
and the kernels differ only in where they leave that shared curve. Weighting scale `s`
of a mode by `exp(taper * s * damping * dt)`, which reads each mode at the scales that
resolve it, opens the family. At `taper -2` the floor falls from `0.219390` to
`0.139806`, a reduction of `36` percent, and the realized error follows it to
`0.139808`. The optimum stops being a two-rate solution: six of the twelve grids land
within `0.2` percent of `0.1398`, each polished from nine starting points that agree,
and their optima spend `3` or `4` of the `32` bins where the pinned gate spends `2`,
against a `1.0` percent spread over the same six grids. On a fixed grid, allocations
using `13` bins reach the same `0.1398`. The relative L1 in the window falls from
`0.2239` to `0.1784`. `research/sweep_readout_taper.py` measures the kernel table, the
shape rank and that floor on a fixed grid, so the two readout variants are compared on
the same bins.

What the taper adds is a steep, rate-ordered early collapse. Under the pinned gate
every bin falls from `1.0` at age `16` to between `0.2602` and `0.2710` at age `30`, a
spread of four percent across three decades of damping. At `taper -2` that same age
spans `0.0040` for the fastest bin to `0.2591` for the slowest, and the fast bin's
`0.0040` stays flat out to age `1024` where it previously held `0.2575`. The gain lands
where the pinned family could not reach: the residual at ages `234` to `762` falls from
`0.64`-`0.80` of the target to `0.90`-`0.97`.

The early window is untouched, and its cause is in the same table. No bin retains
between `0.4` and `0.7` at age `30` under either gate, so no mixture can sit at the
target's own `0.48` there, and the residual holds at `0.544` against `0.550`; the
age-`130` shoulder likewise stays at `1.175` against `1.158`. Those two residuals need
a kernel that holds its readout through the write transient and then falls, which no
rate supplies.

At `taper 0` the port's readout is bit-identical to the one it replaced: a reconstructed
pre-change readout and the current one give exactly equal profiles over the whole
`16`-`1024` window, maximum difference `0.0`. The trainer's default path is bit-identical
end to end, delivering the delivered bank's own bytes at
`sha256 cd5505f1f18aaf0c8264d3006e5117ada4bdc8ad130af38b4ff2cdc2565aac25` with an
identical fit block and profile.

`scale_read_taper` is a field flag rather than a port-side variant: the op takes it as an
argument and both backends apply it, the CPU step and the Vulkan shader weighting each
mode's readout at scale `s` by `exp(-taper * s * damping * dt)` against the mode's own
damping. Both of the step's readout passes use the weighted sum, and the scale-agreement
`cross` stays on the unweighted available count, because it counts how many scales agree
rather than measuring a magnitude. The flag defaults to `0`, where every weight is
exactly `1` and the weighted sum is the scale count, so the pinned readout is unchanged:
the twelve arms of `research/probe_cassi_qi_mode_bank.py` reproduce the pre-port build's
logits and state successors byte for byte, `336` files of the two runs with no
difference.

The divisor makes the flag exactly inert on a readout with one scale available, since
`w * chi / w` is `chi` whatever the weight is. The probe's own seed state sits in that
regime: scales `2` and `3` are empty and scale `1` holds `2.11e-06` rms against scale
`0`'s `9.79e-05`, so across `233,473` mode reads the readout found exactly one available
scale `5,706` times and two or more never. A probe run at any taper therefore reports no
change, which measures the state rather than the flag.

Given a state that fills all four scales, the flag moves the model. On a state built by
copying the seed's scale `0` slot to scales `1`, `2`, `3` at `1`, `2`, `3`, `4` times its
magnitude, `10` of the `11` arms move at `taper -2000` and the `reach-off` reference stays
at exactly `0.000e+00`. The scheduler places the op on `Vulkan0`, and the same split
holds there, so the shader and the CPU step agree both that the flag fires and that it
cannot fire without the readout reaching the model. At the flag's own `-2` the seam arms
move `0.124` to `0.222` in max `|d|` logits and the normalized additive arms move `0.005`
and `0.019`, while every arm's state successor stays at exactly `0.000e+00`: the taper
weights the read, not the write. `research/compare_readout_taper_arms.py` prints two
runs' per-arm deltas beside the scale population of the state each one started from.

The refit bank runs through the same op. At `_diag/field-bank/taper-m2.bin`, `sha256
61fc8bce…`, damping `0.6537` to `375.0000`, the taper moves `9` of the `11` arms at `-2`
with `reach-off` and every state successor at exactly `0.000e+00`. That same bank against
`measured-32.bin` at `taper 0` moves the four banked arms in the logits and the state by
`9.1e-4` to `1.0e-3`, and leaves the four ramp arms and `reach-off` at exactly
`0.000e+00` in both, since the ramp arms read no bank. The two controls separate the
mechanisms: the bank moves the write and the readout mix, the taper moves only the read.

`research/probe_cassi_qi_mode_bank.py` runs the op through the native session on the
0.8B at layer 12 and reads each control from the model rather than from the port,
against a reference that runs the field with nothing consuming its readout. The
field has two independent channels into the model and they are set by different
flags. The additive reach is `intervention 0` with `injection_scale` above zero,
which adds the readout's leading `n_embd` channels to the final normed hidden state.
The substitution seam is a positive `substitute` share at level 3 or deeper.
`llama_cassi_qi_state_field_width` reports the seam alone, so it reads `0` in the
additive family while the field is reaching the model there, and `1024` of the row's
`6144` channels with the seam on. Every arm runs the same seed state, prompt, and
continuation; the probe reports each arm against the reference and then pairwise
inside a channel, so a state that moved and a readout that did not are held apart.

Measured on the 0.8B at layer 12 from a seed state of norm `0.0230` holding `7605`
written modes, over a twenty-four-token continuation, with
`--cassi-qi-mode-bank _diag/field-bank/measured-32.bin` at
`sha256 cd5505f1…`, damping `0.4480` to `375.0000`:

| pair | logits max\|d\| | KL | state max\|d\| |
|---|---|---|---|
| read normalized vs absolute, additive | `1.8929` | `3.929e-2` | `0.0` |
| read normalized vs absolute, seam | `0.1852` | `5.382e-4` | `0.0` |
| bank vs ramp, normalized, additive | `0.5490` | `6.114e-3` | `3.633e-3` |
| bank vs ramp, normalized, seam | `0.1734` | `1.304e-3` | `3.633e-3` |
| bank vs ramp, absolute, additive | `0.0066` | `1.439e-6` | `3.633e-3` |
| bank vs ramp, absolute, seam | `0.1787` | `3.591e-4` | `3.633e-3` |
| latch vs default, absolute, additive | `0.0149` | `1.691e-6` | `9.389e-4` |
| latch vs default, absolute, seam | `0.1899` | `2.649e-4` | `9.390e-4` |

The bank is a write-side control and the read flags are read-side. The damping
multiplies the mode's velocity inside the step, so it changes the state the step
carries out; `read_absolute` and `unwritten_latch` select what the step reports, so
they change the injected logits on the pass that runs them. The bank's state
difference of `3.633e-3`, `2.83e-1` relative, is therefore read on a later pass and
wherever the readout is amplified to the model's scale: it moves the default
normalized read by `0.5490` and the seam by `0.1734`. At the absolute read the
readout runs at the field's own magnitude, so the same state difference reaches the
additive channel about eighty times weaker at `0.0066`, while the seam still carries
it at `0.1787`: the channel that hands the successor state to the next decode is the
one that reads what the damping decided. That is the shape the bank is for: it does
not turn a knob on the current read, it chooses what the field becomes.

The probe also reads the same comparison per decode, from the logits the trial
already writes at every step, which is the distance axis rather than a single
number. Against the reach-off reference, all five seam arms give KL exactly `0.0` at
step 0, the last prompt token, so the seam is not read on the pass that writes it.
`seam_first_read_step` is `1`; the normalized read is at `5.541e-3` there and climbs
to `2.839e-2` at step 16 and `3.366e-2` at step 21, an order of magnitude above
where it starts. The additive read runs `1.72e-2` at step 0 and stays in that band
across the continuation, between `5.6e-3` and `1.2e-1`, because it is injected on
every pass instead of only on the ones that read a written state. The full table is
in `_diag/qi-mode-bank/probe-summary.json` under `distance_kl`.

**The three controls are default-off and bit-identical.**
`research/run_cassi_qi_identity_control.py` runs `cassi-qwen --mode coupled` with a
zero state and no new flags on the build of 2026-09-17 and the build carrying these
controls, at both backends, and requires each build to reproduce its peer's state
fingerprints and out-state bytes at the same backend. Both do:
`4416846892684477315` before and `10299161634115612852` after with out-state
`sha256 caaa6728…` at `--gpu-layers 0`, and `5521001538589849774` with
`7f739dc3…` at `--gpu-layers 99`. The two backends differ from each other, which
separates the CPU reference from the Vulkan kernel rather than any control; each
build agrees with its peer within a backend. Receipt
`_diag/identity-control/identity-control.json`.

`--cassi-qi-substitute F` fills the write that level 3 suppresses instead of
leaving it stale. The write is the newest row of that layer's SSM `qkv`
convolution state, `conv_channels = d_inner + 2 * group_count * state_size`
channels wide, so it is mixing state and not hidden space. The seam blends the
field's readout into the leading `n_embd` channels of that row by channel index,
`(1 - F) * <the row the model would have written> + F * <the field's readout of
the layer's own input>`, and leaves the remaining channels to the model. There is
no learned projection: the field addresses those channels positionally, and the
field's readout is not trained to match them. On Qwen3.8-27B at layer 32 the
window is `3 x 10240` floats and the field addresses 5120 of those channels, so
the seam owns 20,480 of the 40,960 bytes of each suppressed decode-state row.

A positive share runs the field at the Qi layer on single-token decodes and
leaves the additive injection out, so one decode runs the field once and the
state write is the field's only channel at that layer. The seam applies at the
Qi layer alone, so a level 4 or deeper displacement, which suppresses many
layers, cannot write one layer's readout into the others. The server refuses a
positive share below level 3, where nothing is suppressed. At `F` zero every
path above is unchanged: the default continuation and the level-3 stream
reproduce byte-identical to the builds before the seam.

`probe_cassi_qi_substitution.py` measures the seam on the 0.8B harness with a
field-off arm, the intact-write arm, the level-3 lesion, the relocated-injection
arm (`F = 1e-6`), the half and full shares, and a phase-shuffled share. Every
arm runs intervention zero with no additive injection, so the arms differ by the
seam and nothing else, and the suppression gate compares arms that share an
injection placement. The counterfactual is the first decode that reads the
seam's write with the same input tokens in every arm: its captures show the
seam's reach growing with its share (`0`, `1.24e-2`, `2.31e-2` relative L2
against the relocated arm), the layer's own output unchanged on the pass that
writes the state, and the effect decaying across the layers above. The last
decode's captures are reported beside them and are larger at partial shares,
where they include the drift the seam then caused.

The prompt captures are byte-identical across the family, so the seam is
decode-only; the binary refuses a substitution aimed at a configuration that
suppresses nothing; and the suppression gate reads the graph, where the
layer's own state write is present in the intact arm (`1380` nodes) and absent
at the lesion (`1374`), with the seam supplying the row at `1393`.

The phase-shuffled arm runs the same share with a matched-norm scrambled
field. It reaches the activations to `1.08e-2` where the real field reaches
`2.31e-2`, so about half of what the seam writes there is the field's own
trajectory, and it commits `23` different tokens of two hundred against the
full share, so that trajectory survives into the tokens. What those tokens
follow is the content rather than the share: the half and full shares
commit the same two hundred tokens, the relocated arm at `F = 1e-6` differs
from the full share in exactly those twenty-three, and a matched-norm shuffled
field at the full share commits the relocated arm's tokens exactly. The
share's whole effect on this stream is the field's trajectory, and a scrambled
field writes a row the stream ignores.

How much of the suppressed row the field owns is a measured quantity, not an
inference: every receipt now carries `state_field_width` and `state_row_width`
from the graph the decode actually built. The seam addresses the flux view,
which is `n_embd` wide by default, and never more channels than the row holds.
On the 27B that is `5120` of `10240` channels, half the row and the `20,480`
of `40,960` bytes above; on the 0.8B it is `1024` of `6144`, a sixth.

`--cassi-qi-field-row-width N` widens the view, capped by the flux block the
field holds, so `6144` takes the 27B to `60%` and the 0.8B to `100%` without
changing the field. `--cassi-qi-field-wave-modes N` raises the wave count
itself, which is what a row wider than the block needs: `5120` gives the 27B
`10240` values and full ownership, and it changes the field's dynamics, where
the row width alone does not. Both default to the behaviour above.

The 0.8B ladder over the same field information, the same fixture and the same
two hundred tokens shows what ownership buys. At a sixth of the row the
scrambled full share is indistinguishable from the near-zero share (no token
changes at all), while the real share moves `23`. At full ownership the real
share moves `142`, the scrambled share moves `158` against it and `156` of the
field's own tokens differ by content, and the first-decode reach rises from
`2.31e-2` to `1.20e-1`. The removal comparison is unmoved (`192` either way),
so what ownership changes is not whether the suppressed write matters but
whether the field's replacement reaches the model at all.

The 27B row is `10240` channels and it divides. Its own metadata gives
`inner_size` `6144`, `group_count` `16` and `state_size` `128`, so the row is
the `6144` channel convolution input followed by the `2 * 16 * 128 = 4096`
channel recurrent state. Widths are therefore not interchangeable, and a sweep
with the field held at its default `6144` values, the pure-model and the
suppressed-write arms byte-identical in every run, gives the content share as
`115` tokens at `5120`, `136` at `5632`, `133` at `5888`, `0` at `6144`, and
`74` at `10240` with `--cassi-qi-field-wave-modes 5120`.

Content reaches the model at every width below `d_inner` and stops at
`d_inner` itself, where the field's tail meets the end of the convolution
input section, and it returns at the whole row only when the wave count is
raised so the field fills it. Half the row is not special: the ladder runs to
`5888`. A width of `5632` moves the most tokens of any setting measured and
gives up part of the trajectory channel in exchange (`89` against the
default's `126`), which is why the default stays the default.

A request above the block is met by the block: `7168` and `9216` both address
`6144` and reproduce that rung to fifteen digits, which is also the harness's
run-to-run determinism.

On the 27B, where the field runs at the layer and no injection is present, the
open-ended continuation takes four distinct forms across `F = 0, 1e-6, 0.5, 1.0`.

The same probe runs on the 27B, where the field's footprint is larger. Layer
32, the layer whose write the seam fills, leaves its own output unchanged on
the writing pass (`0.0` against the relocated arm), and every layer above it
moves by `1.9e-1` to `2.5e-1` relative, a shift that persists to the last
layer. The graph moves with it: `3660` nodes with the write intact, `3654` at
the lesion that removes it, and `3673` where the seam supplies the row.

The same receipt separates the three ways the field could reach the tokens.
Running at the layer while writing nothing commits the same two hundred tokens
as the field switched off, so an observer field is inert. Removing the layer's
own write moves `135` of them, so ownership of that write is what reaches the
stream. Replacing the field with a matched-norm phase-shuffled one at the same
share moves `115` of the same two hundred, with byte-identical prompt
captures, so most of what the seam moves is what the field says rather than
the act of substituting. Beside the tokens, the shuffled field reaches
`9.2e-2` of the real share's `3.4e-1` activation footprint.

Window length decides whether that reaches the token stream at all. Over forty
tokens of a chat-templated prompt every arm agrees byte for byte, which is the
thought block's boilerplate rather than a property of the field: those tokens
are the same continuation for any input. The probe's default window is `200`
tokens for that reason, and runs on the 27B pass `--generate-tokens`
explicitly, since each token costs GPU time. Receipts: `substitution-
probe.json` for the 0.8B and `27b-200/substitution-probe-27b-chat.json` for
the 27B.

The 27B workcase campaign runs a matched pair that differs by the substitution
alone, both arms at displacement 3 with no additive injection: `16/17` field
passes at `F = 1` against `16/17` at `F = 0`, `13/13` exact memory-dependent
retrievals in both, zero regressions, restart-exact state, and all seventeen case
texts identical across the 269 completion tokens of the substitution arm. Those
answers are short and greedy, so the seam's perturbation sits below their
resolution, while the open-ended instrument on the same build and the same flags
separates all four shares. The one configuration that did change these texts also
relocated the additive injection to that layer, so the marked difference is the
injection's placement, not the seam. The seam therefore buys a field-owned state
write at no task cost, and its reach appears in the activations and in
open-ended generation rather than in these texts. It changes no weight: the
displaced decision is the state write itself, and the run's record of it is the
launch argument `--cassi-qi-substitute 1.0` in `server-launch.json` beside the
substitution probe receipt. The campaign's own ownership block describes the
CassiFI memory layer, whose native counters are zero by construction; the
native-graph configuration is in the launch arguments, not in that block.

`test-cassi-qi-latent` exercises the mid-trunk graph with a field-off control,
a live `alpha=0` identity control, persistent and reset-every-generated-token
state, and a post-prompt matched-norm phase shuffle. It captures every remaining
layer input, prompt logits, final field state, generated tokens, and timing.
`research/run_cassi_latent_reasoning.py` runs the controlled work cases and writes raw
logs, F32 captures, per-arm receipts, and `verification.json`.

A harness invocation can carry a per-token coupling schedule with
`--schedule PATH`: one `STEPS ALPHA` line per generated-token decode, `#`
comments, `STEPS` at least 1, and `ALPHA` finite and non-negative. A decode that
should not inject holds the field with `ALPHA 0`, which the identity control
shows leaves the decoded stream unchanged; a zero-step entry is refused rather
than silently treated as a hold. The constructor `STEPS`/`ALPHA` still apply to
the prompt decode, so a scheduled arm starts from the same prompt treatment as
the constant arm it is compared with. Each arm reports its `coupling_budget`
(the sum of `steps x alpha` over applied decodes) and `schedule_applied`; the
runner refuses to interpret a placement run whose scheduled arms do not match
the constant `k4_a01` budget. Placement arms (`place_front16`, `place_back16`,
`place_spread16`, `place_digest16`) spend 1.28 on eight of thirty-two decodes at
16 x 0.01 instead of on every decode at 4 x 0.01.

`probe_cassi_coupling_placement.py` measures where a fixed budget works. On the
0.8B model, six cases and six arms: only `delayed_cue` responds at this
amplitude, where the constant arm, a single coupled decode at position 0, and a
front-loaded window all produce the correct answer with the same eleven changed
tokens, while the same budget spent from position 1 onwards changes nothing at
all. The measured conclusion is that placement, not budget, decides this case,
and that the constant arm spends eight times the coupling it needs. Of the remaining
cases, only `ordered_composition` moves anywhere, and there only under the
constant arm, by one token. Receipt:
`_diag/latent-reasoning/coupling-placement/placement.json`.

The measured 27B layer-56, `alpha=1`, 16-evolution ordered-composition case is
causally positive but narrow. The persistent field changed 136 generated-token
positions after the first divergence at position 19 and completed the correct
answer `Mira`. Field-off, live-identity, reset-every-token, and phase-shuffled
controls did not complete that answer. The phase shuffle changed the prompt
field hash while preserving its L2 norm to a relative error of
`3.14e-16`; it changed 45 token positions but did not reproduce the successful
result. The injected prompt state remained visible through layer 63: relative
hidden-state delta grew from `0.1469` at layer 56 to `0.1766` at layer 63, and
the prompt-logit relative delta was `0.1566`.

The broader result is mixed rather than a language-quality claim. In the
three-case persistent run, the same field retained the delayed-cue completion,
improved the ordered-composition completion, and changed a correct
reversible-state calculation into an incorrect final answer. Couplings through
`0.1` did not change the 27B greedy trajectory in the measured case; the
causal token effect required 16 evolutions at unit coupling. The live
`alpha=0` control was bit-identical to field-off at every captured hidden layer,
the prompt logits, and generated tokens. The graph-native Qi operator remains
within its CPU/Vulkan gates (`5.46e-11` one-event maximum and `0.002214` after
10,000 events); the full 0.8B graph arm was finite on both backends with a
`5.29e-05` maximum final-field difference.

This is additive field steering, not native replacement. Every Qwen layer,
native recurrent/KV state, LM-head row, and weight access remains active.
Native dynamic-state bytes removed, Qwen operations skipped, output rows
skipped, and weight bytes avoided are all zero. Qi adds 884,736 field bytes per
sequence at four scales. The primary raw receipts are
`_diag/latent-reasoning/campaign-27b-persistent/verification.json` and
`_diag/latent-reasoning/campaign-27b-phase-control/verification.json`.

## Native field apprenticeship

`cassi-qwen --mode apprentice` and the opt-in `--cassi-apprentice`
CLI/server path expose one persistent associative field as the inference owner.
The only adaptive state is the bounded
`cassi.qi.apprentice-engram.v1` image. Qwen is consulted under the declared
`adaptive`, `always`, or `never` teacher policy; a miss in `never` mode fails
with `apprentice_teacher_required` rather than silently returning to native
generation. Teacher/native observations used to choose a token are copied into
a request-bounded, nonadaptive host staging buffer. Its reported logical
payload is capped at the field-image size; allocator capacity and overhead are
not included. The persistent field, revision, and observation counters do not
change before `accept`. Cancelling a pending token discards that buffer without
allocating a full-field rollback image. If a partially field-owned pipeline
cannot complete, its staged native-service observations are discarded before
the declared full-teacher path runs. `accept` preflights the remaining revision
capacity before allocating rollback state, then takes the rollback image,
replays the staged observations under their original reconstructed field
contexts, applies the token-level associations, and advances the live context
as one transaction. Any mid-admission failure restores the exact preceding
field image, transient context, revision, eviction count, and receipt
accounting. Each accepted token is published atomically before its CLI output
or streaming delta is exposed.
Request completion is an unchanged-revision publication no-op. A publication
failure restores the exact preceding field image, transient context, revision,
internal and receipt observation/eviction accounting, field identity, and
committed-token counters before cleanup. The failure remains latched in the
receipt, the token is never exposed, and the previous checkpoint remains
available for recovery.

This native path is teacher-trajectory imitation: Qwen's selected token is the
learning target. It has no post-commit tool, test, user-correction, or verifier
outcome API and is not the causal outcome learner described in
`cassi_causal_event_field.py`. Native causal outcome learning requires a
separate explicit outcome boundary and a receipt showing that an external
consequence changed a later field-owned decision; the existing native replay
receipts do not make that claim.

Each `cassi.apprentice.receipt.v1` receipt separates field-owned decisions
from native work: model contexts and executions, graph nodes, logical weight
bytes, loaded tensor bytes, service computations/skips, teacher queries,
field-exact/interpolated/guided tokens, persistence identity, and durability.
The stats include `pending_admission_payload_bytes_peak` and
`pending_rollback_bytes_peak`, distinguishing the measured logical pre-accept
payload from the accept-time rollback image.
The common owner is shared by the direct executable, `llama-cli`, and
loopback-only `llama-server`; unsupported sampling, tool, grammar, embedding,
and multi-choice requests receive explicit capability errors without mutating
the field.

Measured receipts under `_diag/apprentice/` establish:

- independent NumPy agreement on CPU and Vulkan, bounded state through 10,000
  context-only steps, all 256 guided-byte decisions, exact checkpoint
  round-trip, and rejection without mutation for non-finite or invalid state;
- pending teacher cancellation leaves the checkpoint byte-identical without a
  full-field pre-accept snapshot; accepted learned-token rollback restores the
  exact predecessor; revision `UINT64_MAX` is rejected on import, and a
  mutating transaction from `UINT64_MAX - 1` fails before mutation or rollback
  allocation;
- two distinct eight-token trajectories learned and reproduced after
  termination by separate vocab-only processes on the 0.8B model, on both CPU
  and Vulkan, with every native-work counter zero during replay;
- the same result on `Qwen3.8-27B-Q4_K_M.gguf`: two distinct trajectories,
  64 active trunk layers, a 1,073,524,608-byte field image, and zero native
  work during teacher-free replay. The GGUF's 65th block is its auxiliary
  NextN/MTP layer and is not part of ordinary Qwen inference;
- a warmed `route=pipeline` run in which 99 native embedding,
  attention/recurrent, FFN, and head service opportunities were skipped with
  zero native service calls, all 24 service layers owned, 20,987,904 native
  cache tensor bytes displaced, and 2,717 native graph nodes skipped. This
  establishes routing and displacement for the trained prompts, not semantic
  independence; and
- no field emission on the four held-out wording variants. Each returned
  `apprentice_teacher_required`; exact replay is the attained capability,
  while broad semantic transfer is not.

Run the complete small-model CPU/Vulkan and primary-model transfer receipts
from the `CassiQwen` root:

```powershell
python -B research/run_cassi_apprentice_receipt.py --model Qwen3.5-0.8B-Q4_0.gguf --field-device CPU --gpu-layers 0 --memory-mib 128 --out _diag/apprentice/small-cpu
python -B research/run_cassi_apprentice_receipt.py --model Qwen3.5-0.8B-Q4_0.gguf --field-device Vulkan0 --gpu-layers 99 --memory-mib 128 --out _diag/apprentice/small-vulkan
python -B research/run_cassi_apprentice_receipt.py --model Qwen3.8-27B-Q4_K_M.gguf --field-device Vulkan0 --gpu-layers 99 --memory-mib 1024 --scenario transfer --out _diag/apprentice/primary-transfer
```

The serving verifier discovers the actual model identifier through
`GET /v1/models`, uses that identifier in requests, independently hashes the
expected local GGUF, and checks the model hash in every completed receipt.
Teacher and teacher-free evidence are separate files:

```powershell
python -B tests/test_native_cassi_apprentice_stream.py --base-url http://127.0.0.1:8084 --model Qwen3.5-0.8B-Q4_0.gguf --out _diag/apprentice/server-final/client-always.json
python -B tests/test_native_cassi_apprentice_stream.py --base-url http://127.0.0.1:8084 --model Qwen3.5-0.8B-Q4_0.gguf --prior _diag/apprentice/server-final/client-always.json --out _diag/apprentice/server-final/client-never.json --expect-teacher never
```

`_diag/apprentice/server-final/serving-build-identity.json` pins the exact
server, CLI, common, llama, GGML, and Vulkan binaries used by this pair.

## Offline conventional world-model comparator

`cassi_world_model.py` is **not Cassi-native**. It is a conventional PyTorch
latent model built from `nn.Linear`, `LayerNorm`, `SiLU`, Gaussian latent
losses, backpropagation, and `AdamW`. It is retained only as an explicitly
offline comparator for bounded historical measurements. The adopted terminal
and provider do not import it, load its checkpoints, or preserve its latent
state.

Its offline interface remains:

```text
observe:   (observation, action, reset) → posterior state + predictions
imagine:   (action, reset)              → prior state + predictions
```

The timing contract is fixed: `actions[:, t]` leads into
`observations[:, t]`; `resets[:, t]` clears state before that transition;
`valid[:, t] == false` preserves recurrent state and contributes nothing to
the loss. `observe_step` and `imagine_step` expose the same contract for
streaming callers.

Trajectory archives passed to `train_cassi_world_model.py` are strict `.npz`
files containing exactly these arrays:

```text
observations [N,T,O] float
actions      [N,T,A] float
rewards      [N,T,R] float
continues    [N,T]   float in [0,1]
valid        [N,T]   bool or integer 0/1
resets       [N,T]   bool or integer 0/1
```

Malformed shapes, extra or missing arrays, non-finite values, invalid masks,
empty valid rows, and resets on padded steps fail closed. A CPU training run
looks like:

```powershell
python train_cassi_world_model.py `
  --data trajectories.npz `
  --output _diag/cassi-world-model.pt `
  --observation-dim 6 `
  --action-dim 2 `
  --reward-dim 1 `
  --config-json world-model-config.json `
  --loss-json world-model-loss.json `
  --epochs 10 `
  --batch-size 8 `
  --device cpu
```

The trainer performs deterministic episode splitting, masked likelihood/KL
optimization, gradient-finiteness checks, gradient clipping, atomic
checkpoint writes, and resumable optimizer/model restoration. Checkpoints bind
the exact model configuration, native mode-layout/operator identities, a
configuration fingerprint, dataset digest, split receipt, epoch metrics, and
JSON-safe metadata. Per-session field/stochastic state is stored separately
through `save_world_model_state` and `load_world_model_state`; both persistence
paths use safe tensor-only loading and reject incompatible fingerprints.

Focused verification:

```powershell
python test_cassi_world_model.py
```

This full model is an offline trainable/inference surface. It does not silently
become a Qwen intervention, a live 7599 authority, or an OS-G7 adoption claim.

## Full-model performance benchmark

The frozen benchmark exercises the complete model on deterministic native-family
and off-family trajectories, with a 72-episode training split and 24 held-out
episodes per family:

```powershell
python benchmark_cassi_world_model.py --device cuda --require-supports
python verify_full_world_model_benchmark.py --require-supports
```

The measured result is `SUPPORTS` for both families. Native open-loop
observation MSE was `8.9136e-4` versus `1.3162e-3` for persistence
(`32.277%` improvement). Off-family open-loop observation MSE was
`7.3670e-3` versus `2.0574e-2` (`64.192%` improvement). Training took
`26.970 s` and `24.057 s`, respectively, on the RX 7900 XTX; evaluation
throughput was `9629`/`9437` trajectory steps per second and peak allocated
device memory was `149,294,592` bytes. Both checkpoint round trips had
zero maximum prediction difference.

The complete raw metrics, dataset/checkpoint hashes, configuration fingerprint,
and preregistration digest are retained in
`_diag/full-world-model-benchmark/`. These are offline trajectory results, not
language, multimodal, Qwen, live-authority, or OS-G7 adoption results.

## Robustness and baseline board

The follow-up board runs three fixed seeds for both families, a generic
parameter-count-recorded GRU control, and a `sigma=0.05` noisy-prefix test:

```powershell
python benchmark_cassi_world_model_robustness.py --device cuda
python verify_full_world_model_robustness.py
```

The mechanical verdict is valid, but the frozen quality verdict is `NULL`:
native clean improvement was `32.277%` at the median but `-53.474%` for the
worst seed, and the GRU median clean MSE (`6.9286e-4`) beat the full model
median (`8.9136e-4`). Off-family clean improvement was stronger
(`79.075%` median, `69.435%` worst), but the GRU still had the lower median
MSE (`1.7088e-3` versus `3.5358e-3`). The full model remained robust to the
frozen noisy-prefix protocol: native/off-family median improvements were
`77.776%`/`82.571%`. This board therefore records real seed sensitivity and
the current generic-control gap rather than promoting the single-seed result.

Raw per-seed checkpoints, data hashes, telemetry, and the independent
`NULL`-accepting verifier output are retained in
`_diag/full-world-model-robustness/`.


The terminal records for failed/invalid experiments are retained alongside passing records. They are part of the evidence trail, not stale work to erase.

## Offline native Qwen teacher and baseline

`start-llama-server.ps1` is not a live-runtime prerequisite. It launches the
hash-pinned 27B GGUF only for offline teacher capture, native intervention
experiments, and the measured displacement baseline:

The launcher also enables the direct token-stream seam by default with
`--cassi-qi-stream-gain 1.0`. Set `-CassiQiStreamGain` to sweep overall
language/reasoning pressure, `-CassiQiStreamEogGain` to sweep continuation
length, or use `-NoCassiQiStream` for the exact pre-stream comparator.

```powershell

powershell -ExecutionPolicy Bypass -File .\start-llama-server.ps1
```

The default launcher mode is the combined `--cassi-qi-maximal` profile on the
b8-learn native build with a 32768-token context. It enables full sense and memory
fill, four Qi evolutions per step, field-derived dense-attention history,
layer-32 recurrent-state substitution, and final output correction. The
profile is exercised on both prompt prefill and autoregressive continuation.
Use `-NoCassiQiMaximal` for the older `--cassi-qi-field` comparator, or
`-NoCassiQiField` for an explicit no-field comparator.

## Direct Qi-native terminal, provider, and field agent

The live terminal loads the fixed 260-event Qi configuration and the required
trajectory-trained `QiFieldState` checkpoint. Its single `field` tensor has
shape `[4,55296,1]` and contains both the read-only corpus circulation banks and
the mutable live differential trajectory. No organism checkpoint, Qwen server,
GGUF, llama.cpp process, tokenizer, vocabulary, decoder, neural layer,
optimizer, count table, or sampler is started or loaded:

```powershell
python .\train_cassi_field_language.py
python .\run_cassi_conscious_chat.py --runtime-config .\conscious-chat.json
```

Training defaults to the ordered, hash-bound manifest
`cassi-qi-corpus-first-wave.json`. It verifies all four declared source files,
then deterministically selects ten UTF-8 line episodes per source, capped at 96
bytes each. Each episode becomes one continuous
`user → prompt → end_turn → assistant → continuation → end_turn` trajectory.
Four independently selected suffix-region episodes per source remain held out.
The current manifest covers LightNovels, TinyStories-Instruct, WikiText-103,
and textbook data totalling `4,482,680,317` source bytes; the field itself
stores 40 sampled episodes and 3,360 encoded events, not a copy or count model
of all source bytes.

Run the independent reconstruction after training:

```powershell
python .\train_cassi_field_language.py
python .\verify_cassi_corpus_language.py
```

The generated checkpoint and receipts live under
`_diag/cassi-qi-corpus-language/`. The verifier rereads the declared source
bytes, reconstructs every sampled episode, rebuilds the one field tensor from
scratch, requires bit-exact circulation memory, and replays the recorded
generations through the live engine. A missing or mismatched source,
configuration, codec, trajectory law, or checkpoint fails startup rather than
falling back. `--corpus` remains the direct single-source training mode.

The canonical run reproduces its stored continuations:

| Prompt | Field generation |
|---|---|
| `gi High School culture fest` | `ival! It’s such an honor!` |
| `o quickly shift his battle-` | `axe back to defend himself. ` |
| `ve titles—one read Hand-Selected Knight Storie` | `s and the other Royal Academy Stories. Packaged ` |
| `es at the GF Bunko editorial office when Kenjiro` | ` Toki’s desk received an internal phone call. ` |

For prompts not stored as trajectories, the same field performs nearest
multiscale circulation recall:

| Prompt | Field generation |
|---|---|
| `Hello Cassi` | `ll provide a solid foundation for designing and ` |
| `Once upon a time` | `d to explore it.` |
| `The field` | `s. "Let's trade this pebble for a sweet fruit," ` |
| `light` | `hat.” Yukinari sounded pleased.` |
| `water` | ` cannot. Just like you envy me in the bottom of ` |

The measured event-retrieval accuracy is `0.984036` on the 40 stored episodes
and `0.301255` on 16 held-out episodes. Stored continuations remain exact, and
ordered suffix matching raises held-out retrieval from the former diffuse-match
result while preserving coherent corpus fragments for prompts outside the
stored set.

Every inbound event shifts the multiscale active trajectory. Each common-mode
bank stores complete episode events separated by an empty field mode. The
emission port gives primary weight to the contiguous ordered suffix, retains a
small distributed-match term, and integrates fixed prime-permuted Qi phase work
over the four live horizons. A next-event phase resonance breaks equal work,
and the port waits up to four dwell ticks for a strictly positive winner
margin. The selected event is committed as an outbound reaction; trained memory
modes are checked unchanged after inference.

The trajectory engine fingerprint rejects checkpoints from the superseded
count-lattice runtime instead of reinterpreting them. Use a new session or
state directory across this cutover.

The grounded action, spatial, reference, and temporal milestones are specified
in `GROUNDED-LANGUAGE-PLAN.md`. Train their derived checkpoints from the corpus
field, then run actions, questions, bindings, predictions, explanations, or
temporal ordering through the same persistent field and world session:

```powershell
python .\train_cassi_grounded_language.py
python .\train_cassi_spatial_language.py
python .\train_cassi_reference_language.py
python .\train_cassi_temporal_language.py
python .\run_cassi_field_agent.py `
  --instruction "turn your gaze left" `
  --instruction "turn your gaze right" `
  --instruction "raise your gaze up" `
  --instruction "lower your gaze down" `
  --instruction "remain still" `
  --no-consolidate
```

The canonical held-out run commits:

| Unseen utterance | Field-owned action | Margin | World consequence |
|---|---|---:|---|
| `turn your gaze left` | `action.gaze-left` | `7.985973` | $x: 0 \rightarrow -0.08$ |
| `turn your gaze right` | `action.gaze-right` | `10.041994` | $x: -0.08 \rightarrow 0$ in the live multi-turn smoke |
| `raise your gaze up` | `action.gaze-up` | `5.956003` | $y: 0 \rightarrow 0.08$ |
| `lower your gaze down` | `action.gaze-down` | `10.029530` | $y: 0.08 \rightarrow 0$ in the live multi-turn smoke |
| `remain still` | `action.hold` | `12.024390` | no world movement |

The grounded checkpoint contains one field tensor, 4,290 occupied trajectory
events out of 12,288 available event positions, ten causal training episodes,
and no external adaptive object. Held-out action accuracy is `1.0`; held-out
successor-observation prediction is `1.0`; the cyclically shuffled
utterance/action control is `0.0`. The field commits the action before the
acknowledgment and successor observation enter. Online mode then consolidates
the causal prefix and complete outcome episode; `--no-consolidate` provides the
declared inference-only arm.

The spatial checkpoint extends that same tensor to 5,626 occupied trajectory
events while retaining all five actions. It adds 24 balanced spatial episodes
and 1,336 typed events. Ask the same unseen questions in either held-out world:

```powershell
python .\run_cassi_field_agent.py --seed 101 `
  --question "please decide if red is left or right of blue" `
  --question "please decide if red is above or below blue" `
  --question "please decide if red and blue are near or far"
```

| Held-out world | Horizontal answer | Vertical answer | Distance answer |
|---|---:|---:|---:|
| seed `101` | `left` (`10.000000`) | `above` (`5.000000`) | `far` (`10.000000`) |
| seed `159` | `right` (`5.000000`) | `below` (`5.000000`) | `near` (`5.000000`) |

The same three paraphrases therefore reverse all three answers when only the
world layout changes. Substituting the opposite world's object frame makes the
field follow that frame in `6/6` episodes and produces `0/6` matches to the
original labels. Spatial inference preserves common-mode memory, close/reopen
preserves the live field and object layout, and the prior action board remains
`5/5`.

The reference checkpoint extends the field to 7,394 occupied trajectory events.
It adds 36 binding, literal-reference, and generic relation-family episodes with
1,768 typed events. The checkpoint never contains the held-out names `Mira`,
`Sable`, or `Orin`; their mappings are created only by live binding turns.

```powershell
python .\run_cassi_field_agent.py --seed 159 `
  --bind "Mira::let Mira refer to red" `
  --bind "Orin::let Orin refer to green" `
  --reference-query "Mira::blue::please decide the distance relation" `
  --reference-query "it::blue::please decide the distance relation" `
  --reference-query "Orin::blue::please decide the distance relation" `
  --reference-query "it::blue::please decide the distance relation"
```

Actual committed reference flow:

| Turn | Field identity | Field answer | Margin |
|---|---|---|---:|
| bind `Mira` | `reference.red` | binding committed | `13.997237` |
| bind `Orin` | `reference.green` | binding committed | `17.942223` |
| `Mira` relative to blue | red vs blue | `near` | `5.000000` |
| `it` relative to blue | red vs blue | `near` | `5.000000` |
| `Orin` relative to blue | green vs blue | `far` | `10.000000` |
| `it` relative to blue | green vs blue | `far` | `10.000000` |

All three held-out binding statements resolve correctly; literal subject and
comparison references score `6/6`; generic relation-family transfer scores
`6/6`; unknown `Quill` fails before binding; and the action and spatial boards
remain `5/5` and `6/6`. Binding is the only reference operation that changes
common-mode memory. Both names, the active green referent, the world layout,
and the next `far` answer survive close and reopen. Serialized metadata contains
three counters and world state but no name or referent mapping.

The temporal checkpoint extends the same field to 8,540 occupied trajectory
events. It adds 14 action-effect and before/after episodes containing 1,146
typed events:

```powershell
python .\train_cassi_temporal_language.py
python .\run_cassi_field_agent.py `
  --predict "turn your gaze right" `
  --instruction "turn your gaze right" `
  --explain-last `
  --order-last before
```

Actual live flow:

| Operation | Field result | World result |
|---|---|---|
| predict `turn your gaze right` | `action.gaze-right` → `change.x-increase` | unchanged at tick `0` |
| execute `turn your gaze right` | `action.gaze-right` | $x: 0 \rightarrow 0.08$ |
| explain last | `gaze-right caused x to increase` | unchanged at tick `1` |
| locate `before`, forward presentation | `position.first` | unchanged at tick `1` |

All five held-out action paraphrases predict their separately measured changes;
the shuffled-label control scores `0/5`, and all five counterfactual actions
branch correctly from one predecessor. Change and cause decisions score `5/5`.
Before/after ordering scores `4/4` across forward and reversed presentation.
Prediction, explanation, and ordering preserve trained memory, while changing
only live differential phase changes the prediction and changing only the
transition register changes the causal and order answers.

A second process reopening the same session reproduces
`gaze-right caused x to increase`; asking for `after` with reversed
presentation returns `position.first`. The temporal checkpoint itself is also
loaded and exercised after serialization before its training receipt passes.



The OpenAI-compatible provider uses the same direct Qi engine on loopback port
8086 with model id `cassi-qi-corpus-language-v1`:

```powershell
python .\cassi_persistent_provider.py
```

It exposes `GET /health`, `GET /v1/models`, and
`POST /v1/chat/completions`, including streamed completions and deterministic
per-session continuation. It has no teacher fallback and loads no organism,
learned world model, GGUF, tokenizer, KV cache, recurrent state, output rows,
optimizer, or probabilistic sampler.

### Displacement and field-dependence receipts

The offline native footprint board and the live field-only board are measured
separately:

```powershell
python .\measure_qwen_displacement_baseline.py
python .\measure_cassi_field_language_dependence.py
python .\run_cassi_field_only_displacement.py
```

The current pinned native baseline records one GGUF open, `17,095,778,304`
Qwen weight bytes loaded, `1,073,741,824` KV-cache bytes, `156,893,184`
recurrent-state bytes, and `248,320` output rows. The final live receipt records
zero for all corresponding Qwen graph, state, weight, transfer, output-row,
GGUF-open, and teacher-call counters; its symbol, output-byte, receipt, and
successor-state replay gates pass across a fresh checkpoint reload.

The current text counterfactual first primes every arm with the same stored
corpus trajectory, then rotates only the seeded live differential trajectory by
$0$, $\pi/2$, $\pi$, or $3\pi/2$ before the same `Continue` event. Trained
circulation memory remains bit-identical, but all four arms emit
`d to explore it.`. Its measured verdict is therefore
`NULL_NO_SYMBOL_CHANGE`. The grounded action, spatial, and reference suites
independently show committed-decision changes under live differential
intervention; the 16-symbol text probe itself does not.

Current local evidence is written to
`_diag/qwen-displacement/qi-field-dependence.json` and
`_diag/qwen-displacement/final-qi-native-evidence.json`; the pinned measured
Qwen reference remains `_diag/qwen-displacement/baseline-receipt.json`.
Earlier `first-wave-v3` records describe the superseded count-lattice runtime
and remain historical evidence only.

### Canonical native bridge, displacement, and field-only execution

The release path is the direct `cassi-qwen` executable. It does not use the
`llama-cli` wrapper. The canonical state boundary is exact:

```text
CassiFI checkpoint [scale=4, flattened_mode_plane=55296, batch=1]
    transpose, never reshape
native state       [sequence=1, scale=4, mode=6144, plane=9]
```

`ggml_cassi_qi_field_step.v2` is the defined native bridge transition. The
boundary, fixtures, and independent CPU/Vulkan oracle parity are canonical;
the transition is not described as a numerical reimplementation of
`QiFieldController.cycle`.

The displacement parameter is cumulative:

| Level | Native execution contract |
|---:|---|
| 0 | Qwen greedy output, with canonical field observation/state advance |
| 1 | The field chooses from Qwen's candidate set |
| 2 | The field owns selection over the full vocabulary |
| 3 | The selected recurrent convolution/SSM state write is omitted |
| 4 | Attention, recurrent, and KV work at and after the field layer is omitted |
| 5 | Entire transformer blocks at and after the field layer are omitted |
| 6 | Output norm, LM head, and model logits are omitted; exact field logits are passed to upstream greedy sampling |

Build and run the complete direct-native verification from the `CassiQwen`
root:

```powershell
& "C:/Program Files (x86)/Microsoft Visual Studio/18/BuildTools/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe" `
  --build native/llama.cpp/build-qi --config Release `
  --target test-cassi-qi-field test-cassi-qi-canonical test-cassi-qi-qwen cassi-qwen
python research/verify_native_qi_release.py
```

`research/verify_native_qi_release.py` hash-pins
`Qwen3.5-0.8B-Q4_0.gguf`, regenerates direct runtime states, exercises
displacement levels 0–6, checks machine-readable graph-node counts, runs
independent CPU/Vulkan parity, and verifies both production modes:

- `--mode coupled`: at the additive default (`--displacement 0`), Qwen owns
  the LM head, model logits, and native sampler while the field correction is
  injected into the model path. Explicit displacement levels remain separate
  experiments; at level 6 the field owns the logits and sampler input.
- `--mode field`: the GGUF is opened with `vocab_only=true`; Qwen tensors,
  context, forward passes, recurrent/KV state, model logits, LM head, and
  model sampler are absent. A fixed `fixed_64_mode_hash_v1` token-sense map
  supplies immutable input observations to the same native field transition.

The release verifier explicitly selects coupled level 6 for its field-logit
replacement check. Normal coupled invocations and the Python
`CassiFieldWorkMemory.execute_native` wrapper use additive defaults. A coupled
caller may explicitly pass
`differential_reference=<reference prompt>`; the wrapper composes the real task
frame, uses the caller's reference prompt verbatim, records both field-seed
preparations and the original native seed, then runs the native emitter from
the resulting differential state. This is an experimental numerical contrast,
not proof that semantics were isolated. Field-mode differential requests are
rejected.

With `CassiCosmos/scenes/mind_engine.tscn` listening on loopback port 7599, the
verified field-only state can be mirrored without giving the simulator write
authority:

```powershell
cd ../CassiCosmos
python tools/qi_state_bridge.py `
  --state ../CassiQwen/_diag/native-runtime-field-state.f32 `
  --contract ../CassiQwen/_diag/canonical-native-qi-v1/contract.json `
  --revision 1 --project-k 8
```

Seal the exact binaries, sources, states, model, parity evidence, field-order
counterfactual, mind-engine gate, and live bridge receipt after the handoff:

```powershell
cd ../CassiQwen
python research/write_native_qi_release_manifest.py
```

The machine-readable outputs are
`_diag/native-qi-release-verification.json` and
`_diag/native-qi-release-manifest.json`; the corresponding simulator handoff
is `../CassiCosmos/_diag/qi_state_bridge_receipt.json`.

The native verification target is the exact
[`ggml-org/Qwen3.5-0.8B-GGUF`](https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF)
Q4_0 artifact: `563,036,064` bytes with SHA-256
`57d1997790d1744fba5b40a7317df71ea5e2acee28c47e78f0cce39c0703f8cf`.
All live rungs were observed on the RX 7900 XTX after the iGPU was disabled.
The 27B model and `llama-cli` were deliberately not rerun after the two
iGPU-enabled hard hangs, so the release evidence makes no 27B equivalence
claim. The frozen Python ctypes runtime under
`runtimes/llama-b10472-wip9/` remains separate and unchanged.


## Offline Qwen request policy

When a separately invoked teacher/baseline capture needs the native server,
the historical deterministic request policy remains:

```json
{
  "temperature": 0,
  "stream": false,
  "chat_template_kwargs": { "enable_thinking": false }
}
```

Thinking mode is explicit and costlier. L8b measured 132 completion tokens for
two deliberate calls versus 5 for their fast counterparts, with both arms
returning the same exact answers on that narrow board. This is offline
measurement evidence, not a setting or dependency of either live field-only
path.

The generation prompt's thinking region is decided by the template and gated by
the server. The 27B GGUF's own template branches on the flag
(`tokenizer.chat_template`, read from the GGUF header): when `enable_thinking`
is undefined or true it ends with an open `<think>` block and a
`reasoning_effort` preamble that defaults to `xhigh`, and when it is false it
ends with a closed empty block and no preamble. The server reaches that
template only with reasoning enabled and jinja templates in use, since it
computes `enable_reasoning != 0 && use_jinja && template_supports_thinking`
(`native/llama.cpp/tools/server/server-context.cpp`); `start-llama-server.ps1`
passes neither `--no-jinja` nor a reasoning flag, and the pinned defaults are
jinja on with reasoning auto. A request that omits the flag therefore spends
completion budget on a trace. At the workcase caps of 96 and 128 tokens the
trace can consume the whole budget: two rows of the 2026-09-14 receipt report
96 and 128 completion tokens while `content` holds `{"launch_token":"A7-K` and
the empty string, and no recorded field carries the tokens between. Those two
campaigns omitted the flag, and their receipts record the server binary but not
its launch, so they show the budget effect without fixing which template
produced it. Where the tokens went is settled by the build itself: it defaults
to `COMMON_REASONING_FORMAT_DEEPSEEK` (`common/common.h`), which returns
thinking tag contents as `message.reasoning_content`, and those rows have no
reasoning field, so a trace was delivered and discarded rather than never
generated.

The harness now sends the policy, records it, and checks that the server applies
it. `LocalQwenClient.complete` defaults to `thinking=False`, returns `content`
and `reasoning_content` separately, and reports the parameters of the request it
actually sent; each workcase row carries those parameters plus the full
reasoning trace, and the arm receipt derives `request_policy` from the rows,
refusing an arm whose rows disagree. `probe_request_policy` sends two identical
requests that differ only in the flag, because `/props` cannot answer the
question: it reports the loaded template text and the jinja language caps, and
no thinking flag, while the server settles the gate itself. A run is refused
when the generations do not differ. The receipt records the loaded template's
digest and its `enable_thinking` scan, the server's `build_info` and jinja caps
as identity, and the two observed readings beside them rather than inside the
block the verifier compares across arms. On the campaign server the probe reads
7 completion tokens and no trace with the flag off, against 38 tokens and 107
trace characters with it on, at an identical prompt. `--thinking` selects the other policy
and belongs in its own run directory, because the verifier requires the baseline
and field arms to present identical model blocks. Raising any case's
`max_tokens` rewrites the hashed protocol, so a budget-raised campaign needs its
own frozen anchor.

`research/cassi-qwen-client.mjs` remains offline teacher/baseline tooling. It verifies
health and exact model identity before every completion, applies bounded
request deadlines, returns a provenance receipt, and never silently retries.

## Verification commands

Adopted Qi-native runtime verification:

```powershell
python -m unittest -v test_cassi_qi_field.py test_cassi_field_language.py test_cassi_conscious_chat.py test_cassi_persistent_provider.py test_cassi_field_agent.py test_cassi_qwen_displacement.py
python .\verify_cassi_corpus_language.py
python .\verify_cassi_native_runtime.py
python .\train_cassi_spatial_language.py
python .\train_cassi_temporal_language.py
```

The corpus verifier independently rereads every selected source episode,
reconstructs the phase-coded circulation banks inside a fresh `QiFieldState`,
requires bit-exact memory, recomputes stored and held-out event retrieval, and
replays the recorded generations. The native verifier separately requires an
exact stored-trajectory continuation, unchanged trained memory, one adaptive
tensor, active outbound ownership, and a live source surface with no learned or
Qwen-serving dependency.

Offline organism-reference checks are separate:

```powershell
python -m unittest -v test_cassi_organism.py test_cassi_organism_law.py test_cassi_organism_teacher.py
```

Offline teacher/baseline checks (require a separately launched Qwen service on
`127.0.0.1:8084`; neither live field-only path starts or contacts it):

```powershell
node --test research/cassi-qwen-client.test.mjs
node --test cassi-field-shadow.test.mjs
node --test cassi-field-candidate-mapper.test.mjs
node --test cassi-semantic-field-encoder.test.mjs
node research/run-baseline-receipt.mjs
node research/run-thinking-policy-receipt.mjs
node run-correction-persistence-board.mjs
node run-q4-q6-escalation.mjs
```

Native baseline instrumentation (offline pinned build, not live serving):

```powershell
python tests/test_native_llama_stream.py
python tests/test_native_llama_stream.py --expect-cassi-disabled  # only with -NoCassiModal
python tests/test_native_llama_parallel.py --requests 16
python tests/test_native_llama_slot.py
```

The stream smoke expects the modal metric to be enabled unless `--expect-cassi-disabled` is passed explicitly.

For the OMP-facing retained `mind_complete` seam, the spine now defaults to the existing local OpenAI-compatible llama-server transport against the same loopback service; an injected `createLlamaServerTransport({ baseUrl: "http://127.0.0.1:8080" })` remains the explicit override. Ordinary ohmypi provider sessions remain owned by OMP. The transport uses non-streaming `POST /v1/chat/completions` and does not change the native server's SSE surface.
This OMP/Qwen transport is separate from the field-only provider on `8086` and
is never started by the live conscious terminal.

For a temporary OpenAI-compatible OMP transport seam, run the native server on `8080`, then:

```powershell
python native_omp_provider.py --upstream http://127.0.0.1:8080 --port 8081
python tests/test_native_llama_stream.py --base-url http://127.0.0.1:8081
```

The proxy is loopback-only, forwards SSE without changing payloads, and owns no model or field state.


L15 is self-contained and does not require the Qwen service:

```powershell
node --test cassi-embedding-field-codec.test.mjs
node run-embedding-field-lift.mjs --prepare
<Godot console executable> --path ../CassiCosmos res://scenes/verify_cassi_qwen_embedding_field.tscn
node run-embedding-field-lift.mjs --analyze
python verify_embedding_field_lift.py
```

The Godot scene must run windowed. Its terminal checkpoint is 2,048 PDE steps (`t=10.24`).

L16 is a separate read-only lab probe. It requires exclusive use of the local model GPU; it never starts, patches, or uses `llama-server.exe`:

```powershell
node --test cassi-embedding-field-codec.test.mjs cassi-hidden-state-field-codec.test.mjs
python l16_hidden_state_probe.py
node run-l16-hidden-state-observatory.mjs --prepare-field
<Godot console executable> --path ../CassiCosmos res://scenes/verify_cassi_qwen_l16_hidden_state.tscn
node run-l16-hidden-state-observatory.mjs --analyze
python verify_l16_hidden_state_observatory.py
```

L16 captures the final prompt-token input residual at `floor(n_layer / 2)`, carries its original L2 norm as sidecar metadata, and evolves only the normalized direction. The scene must run windowed.

L17 extends that same read-only lab boundary across every layer. It requires exclusive use of the local model GPU; run it with `llama-server.exe` stopped:

```powershell
python l17_all_layer_hidden_probe.py
node run-l17-all-layer-iir-observatory.mjs --prepare-field
<Godot console executable> --path ../CassiCosmos res://scenes/verify_cassi_qwen_l17_all_layer_iir.tscn
node run-l17-all-layer-iir-observatory.mjs --analyze
python verify_l17_all_layer_iir.py
```

The field starts byte-zero, blends each normalized layer direction at a retained weight of `0.9`, advances four existing PDE steps per layer, and never returns a field value to Qwen. The scene must run windowed.

L18 is an isolated model-and-field lab, not a Qwen service feature. It requires exclusive use of the local model GPU and runs with `llama-server.exe` stopped. In one terminal, start its direct-child field scene windowed:

```powershell
<Godot console executable> --path ../CassiCosmos res://scenes/cassi_qwen_l18_field_lab.tscn
```

In another terminal, execute and independently verify a recorded run:

```powershell
python run_l18_field_output_loop.py --max-tokens 4 --run-id l18-first
python verify_l18_field_output_loop.py
```

The L18 lab listens only on loopback port 7601, records raw JSONL and a receipt under `_diag/l18-field-output-loop/`, and shuts down its scene after the runner completes.

L19 is the completed, preregistered control-surface follow-up to L18. Its frozen manifest derives the first positive crossover from L18’s raw output-head receipt at $\gamma_* = 0.2813035510306464$; it does not authorize another model run. Independently replay the completed artifacts and regenerate the diagnostic figure with:

```powershell
python verify_l19_output_control_surface.py
python plot_l19_output_control_surface.py
```

The verifier confirms the six serial arms, every 64-layer field update, exact raw event linkage, Fourier source encodings, decoded field direction, output-feature combination, planner no-action boundary, field-memory retrieval, and the frozen token transition. It writes `_diag/l19-output-control-surface/l19-verification.json`; the figure is `_diag/l19-output-control-surface/l19-output-control-surface.png`.

L20 is the frozen cross-prompt readiness board. It uses four prompt shapes, paired `baseline`/`residual` arms, and eight fresh 7601 lab runs:

```powershell
python run_l20_cross_prompt_board.py --freeze --commands
# Start the windowed lab once for each printed arm, then run its command.
python verify_l20_cross_prompt.py
python run_l20_cross_prompt_board.py --summarize
```

The independent verifier writes `_diag/l20-cross-prompt/l20-verification.json`. `DOES NOT EMERGE` here means that fewer than two of four prompt pairs changed committed tokens within four output steps; it does not invalidate the mechanically passing field-output path or prohibit using it experimentally.

L21-L26 are retained historical hybrid-provider evidence. Their field lab,
native-teacher fallback, student/correction modes, and port-8081 commands are
not part of the canonical runtime. `cassi_persistent_provider.py` now names the
field-only port-8086 provider, so the superseded hybrid launch command has been
removed rather than kept as a misleading alias. The frozen L21-L26 receipts,
tests, trace-store, student, and condensation tools remain available for
offline historical analysis.

The offline journal/student/condensation checks do not need the model or lab:

```powershell
python test_l22_trace_store.py
python test_l23_shadow_student.py
python test_l26_condensation.py
```

L27 is the frozen longer-generation comparison:

```powershell
python run_l27_long_generation.py --max-tokens 16 --output-dir _diag/l27-long-generation --session-prefix l27-long
python verify_l27_long_generation.py --board _diag/l27-long-generation/l27-board.json
```

The completed board is `_diag/l27-long-generation/l27-verification.json`. The fresh 16-token pair matched through token 10, first diverged at token 11, differed at five positions, and ended at 4,352 field steps with distinct terminal field hashes. The result is `EMERGES` for the preregistered mechanical-control statistic only.

L28 is the frozen offline field-world identification board. It does not need
the Qwen service, Godot, or a live field engine:

```powershell
python run_l28_field_world_model.py
python verify_l28_field_world_model.py --require-supports
python test_l28_field_world_model.py
```

The verifier replays the saved candidate on the declared held-out episodes and
requires exact operator/configuration/split/optimizer identities, source and
preregistration digests, sibling manifest/checkpoint paths, content hashes,
finite bounded trajectories, and deterministic duplicate-training state
digests. The resulting `SUPPORTS` report is evidence for this synthetic
identification question only; it is not a general-model or OS-G7 adoption gate.

`run-field-retrieval-gate.mjs` and `run-relational-arbitration-gate.mjs` are retained closed experiments. The retrieval gate was `NULL`; the relational surrogate was `SURROGATE-SUPPORTS` and still requires a future mechanism with actual field coupling.

`run-q4-q6-escalation.mjs` is a prerequisite checker until an exact same-model Q6/Q8 artifact is supplied.

## Field boundary

`cassi-field-shadow.mjs` is the only field-side adapter. It is disabled by default and permits only:

```text
ping → state → project(k ≤ 8)
```

It never sends `clear`, `deposit`, `step`, `readout`, or `snapshot`. A missing/malformed/timeout field service yields an unavailable observation rather than a completion-path failure.

The calibrated seeded native scene is:

```text
CassiCosmos/scenes/cassi_qwen_seeded_mind.tscn
```

It is a verification scene, not a production runtime dependency. It must be launched windowed; this machine’s Godot local RenderingDevice does not run headless.

L15’s generic full-field seed is an explicit in-process verification API. It does not expand `cassi-field-shadow.mjs`, the loopback TCP mutation surface, or the field-only runtime.

L16 resolves the installed llama.cpp WIP layer-input capture exports only in `l16_hidden_state_probe.py`. It adds no HTTP endpoint, TCP operation, server hook, activation write path, or live field adapter.

L17 uses `blend_full_field` only in the offline verification scene. It adds no HTTP endpoint, TCP command, activation write, server hook, or default behavior to the field-only runtime; its native modal configuration is separately invoked laboratory tooling.

L18 uses a separate direct-child, bridge-disabled offline lab on loopback port 7601. It transports all 64 trunk residuals into a persistent field, reads that field only within the lab, and combines its decoded value with the documented public final-output reference through Qwen's frozen output head to select laboratory tokens. It adds no operation or hook to the production 7599 mind engine and is not imported by either field-only launch path.

L19 reuses the same isolated 7601 laboratory and frozen output-head seam. Its positive-coupling crossover is evidence about that laboratory token-control surface only; it adds no endpoint, hook, or default behavior to the field-only path.

L20 keeps the same direct-child, bridge-disabled 7601 laboratory and the same raw llama.cpp capture/output-head seam. The frozen board remains historical evidence and adds no 7599 command, 7273 endpoint, or dependency to the terminal or port-8086 provider.

## Adoption rule

The live conscious terminal and port-8086 provider use the adopted field-only
Qi state and emit deterministic words selected from a hash-pinned,
non-adaptive lexical boundary; those choices may remain semantically poor.
They do not fall back to Qwen. The hash-pinned
Qwen/llama.cpp programs remain separately invoked offline teacher and
measurement tools. This cutover does not authorize changes to the 7599 mind
engine, 7273 HTTP channel, tool authorization, evidence truth evaluation,
unrelated providers, or CassiCosmos mechanical behavior.

## Primary records

- `MODEL-RECEIPT.md`
- `L2-BASELINE-PERFORMANCE-REPORT.md`
- `L3-FIELD-SHADOW-BRIDGE-REPORT.md`
- `L4-LIVE-FIELD-SIDECAR-REPORT.md`
- `L5D-CALIBRATED-SEEDED-BRIDGE-REPORT.md`
- `L6-FIELD-CANDIDATE-MAPPER-REPORT.md`
- `L7-FIELD-RETRIEVAL-GATE-REPORT.md`
- `L8B-THINKING-POLICY-RECEIPT-REPORT.md`
- `L9-SEMANTIC-CANDIDATE-ENCODER-REPORT.md`
- `L10B-RELATIONAL-ARBITRATION-PREREG.md`
- `L11C-GPU-RELATIONAL-PARITY-REPORT.md`
- `L12-CORRECTION-PERSISTENCE-REPORT.md`
- `L13-Q4-Q6-ESCALATION-REPORT.md`
- `L14-LOCAL-POOL-COUPLING-REPORT.md`
- `L15-EMBEDDING-FIELD-LIFT-PREREG.md`
- `L15-EMBEDDING-FIELD-LIFT-REPORT.md`
- `L16-HIDDEN-STATE-OBSERVATORY-PREREG.md`
- `L16-HIDDEN-STATE-OBSERVATORY-REPORT.md`
- `L17-ALL-LAYER-IIR-PREREG.md`
- `L18-FIELD-OUTPUT-LOOP-PREREG.md`
- `L19-OUTPUT-CONTROL-SURFACE-PREREG.md`
- `L20-CROSS-PROMPT-PREREG.md`
- `cassi_trace_store.py` (L22 durable journal)
- `cassi_shadow_student.py` (L23 student and checkpoints)
- `L24-LEARNED-CORRECTION-PREREG.md`
- `cassi_condensation.py` (L26 condensation and promotion)
- `L26-TRACE-CONDENSATION-PREREG.md`
- `run_l27_long_generation.py`
- `L27-LONGER-GENERATION-PREREG.md`
- `L28-FIELD-WORLD-MODEL-PREREG.md`
- `run_l28_field_world_model.py`
- `verify_l28_field_world_model.py`
- `test_l28_field_world_model.py`
- `cassi_world_model.py`
- `train_cassi_world_model.py`
- `test_cassi_world_model.py`
- `L28-FIELD-WORLD-MODEL-REPORT.md`
- `_diag/l28-field-world-model/l28-board.json`
- `_diag/l28-field-world-model/l28-manifest.json`
- `FULL-WORLD-MODEL-BENCHMARK-PREREG.md`
- `benchmark_cassi_world_model.py`
- `verify_full_world_model_benchmark.py`
- `_diag/full-world-model-benchmark/full-world-model-benchmark.json`
- `_diag/full-world-model-benchmark/FULL-WORLD-MODEL-BENCHMARK-REPORT.md`
- `_diag/full-world-model-benchmark/native-model.pt`
- `_diag/full-world-model-benchmark/off-family-model.pt`
- `FULL-WORLD-MODEL-ROBUSTNESS-PREREG.md`
- `benchmark_cassi_world_model_robustness.py`
- `verify_full_world_model_robustness.py`
- `_diag/full-world-model-robustness/full-world-model-robustness.json`
- `_diag/full-world-model-robustness/FULL-WORLD-MODEL-ROBUSTNESS-REPORT.md`
- `cassi_raw_event_field.py`
- `cassi_raw_event_store.py`
- `run_cassi_raw_event_scenario.py`
- `test_cassi_raw_event_field.py`
- `_diag/raw-event-acquisition/verification.json`
- `cassi_qi_field.py`
- `cassi-qi-language.json`
- `cassi_field_language.py`
- `cassi_grounded_language.py`
- `cassi_temporal_language.py`
- `train_cassi_grounded_language.py`
- `train_cassi_spatial_language.py`
- `train_cassi_reference_language.py`
- `train_cassi_temporal_language.py`
- `GROUNDED-LANGUAGE-PLAN.md`
- `cassi_conscious_chat.py`
- `run_cassi_conscious_chat.py`
- `cassi_persistent_provider.py`
- `cassi_field_agent.py`
- `run_cassi_field_agent.py`
- `test_cassi_field_agent.py`
- `cassi_qwen_displacement.py`
- `verify_cassi_native_runtime.py`
- `qi-native-field-dependence-prereg.md`
- `measure_qwen_displacement_baseline.py`
- `measure_cassi_field_language_dependence.py`
- `run_cassi_field_only_displacement.py`
- `_diag/qwen-displacement/baseline-receipt.json`
- `_diag/qwen-displacement/qi-field-dependence.json`
- `_diag/qwen-displacement/final-qi-native-evidence.json`
- `_diag/qwen-displacement/qi-native-runtime-gate.json`
- `_diag/cassi-qi-native/provider-restart-before.json`
- `_diag/cassi-qi-native/provider-restart-after.json`
- `_diag/cassi-qi-native/terminal-restart-before.json`
- `_diag/cassi-qi-native/terminal-restart-after.json`
- `_diag/cassi-qi-native/obsolete-conscious-stack/manifest.json`
- `_diag/cassi-qi-native/obsolete-classical-field-language-v3/CUTOVER-MANIFEST.json`
- `semantic-atlas-manifest.json`
- `semantic-atlas-broad-manifest.json`
- `run_native_semantic_atlas.py`
- `verify_native_semantic_atlas.py`
- `test_native_semantic_atlas.py`
- `_diag/native-semantic-atlas-20260917-r3/semantic-atlas-receipt.json`
- `_diag/native-semantic-atlas-broad-20260917-r1/semantic-atlas-receipt.json`
