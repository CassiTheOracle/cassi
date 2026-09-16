# CassiQwen

Field-organism language and native-Qwen displacement work for the Cassi program. The live conscious terminal and OpenAI-compatible provider are Cassi Field Intelligence; the pinned Qwen/llama.cpp runtime remains explicit offline teacher and measured-baseline tooling.

> The Field Intelligence working prototype is organized in `../CassiFI`.
> This document retains the Qwen/native integration and intervention notes.

The [Universal Latent Reasoning System design](LATENT-REASONING-DESIGN.md)
specifies the full integration with CassiFI: portable reasoning, model-specific
latent interfaces, lifelong acquisition, paired execution, and field-owned
state, emission, and native computation. It distinguishes the implemented
basis from specified mechanisms and unresolved research.

Its [packet-aware reasoning extension](LATENT-REASONING-DESIGN.md#packet-aware-reasoning-scope-and-status)
specifies a resident multi-operation work loop, semantic packet bindings,
root-budgeted child calls, safe coarse-to-fine readouts, correction-local repair,
and acquisition of reusable interfaces and procedures. The numerical packet
basis is implemented in CassiFI; this task-directed reasoning extension is
specified, not yet an exercised capability. The
[implementation sequence](LATENT-REASONING-DESIGN.md#packet-aware-reasoning-increments)
separates state/continuation handoff and budget enforcement from scheduling,
acquisition, and optional native integration.

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

| CassiTheory field-memory stress (2026-09-09) | **PASS for exact storage/restart; NULL for semantic selection and answer quality** | The 14-document, 352-chunk campaign returned 60/60 Qwen-requested payloads byte-exact and round-tripped the field state before and after six difficult questions. All source-chart numeric fields were identical, Qwen selected every document/chunk ID, and a literal-text placebo received byte-identical answer prompts. Same-process shared-parameter replay produced five distinct answers for one identical prompt, so no answer-quality delta is attributable to the field. |
| Live-order text counterfactual | **FIELD_DEPENDENT (exploratory)** | Reversing only bounded live-event order changes committed field-owned symbols while trained circulation stays bit-identical. This is separate from the unavailable frozen `qi-field-dependence.v2` receipt and from the null phase-rotation probe above |
| CassiCosmos canonical Qi mirror | **PASS** | Hash-bound monotonic `qi_snapshot` handoff, deterministic top-mode projection, idempotent replay, stale/conflicting revision rejection, and exact PDE isolation |

## 2026-09-14 current CassiFI regional adapter upgrade

`cassi_field_qwen_workbench.py` now uses the current CassiFI owner and its
`cognition.field` semantic kernel rather than the retired adapter-side
adaptive-memory assumptions. The source identity is hash-bound to the complete
25-file CassiFI production closure, and the owner is reopened through one
regional `LearningComputer` with a fixed profile.

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
python -B verify_cassi_theory_recall.py --run-dir D:/cassi-theory-recall-0.8b-final8
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

`--cassi-qi-field-dt F` sets the integrator step of the field itself, one bound
inside `cassi_qi_field_step.comp` (default `0.005`, the same step the CPU
reference uses). It is the field-capacity control: at `0.02` the 27B keeps its
open-ended continuation and the 16/17 memory arm with four answers changed, and
at `0.05` the field's own evolution degrades the memory-free arm to 4/17 while
the memory arm holds 11/17.

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
`run_cassi_latent_reasoning.py` runs the controlled work cases and writes raw
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
python -B run_cassi_apprentice_receipt.py --model Qwen3.5-0.8B-Q4_0.gguf --field-device CPU --gpu-layers 0 --memory-mib 128 --out _diag/apprentice/small-cpu
python -B run_cassi_apprentice_receipt.py --model Qwen3.5-0.8B-Q4_0.gguf --field-device Vulkan0 --gpu-layers 99 --memory-mib 128 --out _diag/apprentice/small-vulkan
python -B run_cassi_apprentice_receipt.py --model Qwen3.8-27B-Q4_K_M.gguf --field-device Vulkan0 --gpu-layers 99 --memory-mib 1024 --scenario transfer --out _diag/apprentice/primary-transfer
```

The serving verifier discovers the actual model identifier through
`GET /v1/models`, uses that identifier in requests, independently hashes the
expected local GGUF, and checks the model hash in every completed receipt.
Teacher and teacher-free evidence are separate files:

```powershell
python -B test_native_cassi_apprentice_stream.py --base-url http://127.0.0.1:8084 --model Qwen3.5-0.8B-Q4_0.gguf --out _diag/apprentice/server-final/client-always.json
python -B test_native_cassi_apprentice_stream.py --base-url http://127.0.0.1:8084 --model Qwen3.5-0.8B-Q4_0.gguf --prior _diag/apprentice/server-final/client-always.json --out _diag/apprentice/server-final/client-never.json --expect-teacher never
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

```powershell
powershell -ExecutionPolicy Bypass -File .\start-llama-server.ps1
```

The launcher binds its native server to loopback. Its Qi, modal, field,
tokenizer, output-head, KV-cache, and recurrent-state paths are never imported
or contacted by the canonical terminal or port-8086 provider. Historical
native experiments may still select `-NoCassiQiField`, `-NoCassiModal`, or the
explicit intervention controls described by their frozen preregistrations.

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
python verify_native_qi_release.py
```

`verify_native_qi_release.py` hash-pins
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
python write_native_qi_release_manifest.py
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

`cassi-qwen-client.mjs` remains offline teacher/baseline tooling. It verifies
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
node --test cassi-qwen-client.test.mjs
node --test cassi-field-shadow.test.mjs
node --test cassi-field-candidate-mapper.test.mjs
node --test cassi-semantic-field-encoder.test.mjs
node run-baseline-receipt.mjs
node run-thinking-policy-receipt.mjs
node run-correction-persistence-board.mjs
node run-q4-q6-escalation.mjs
```

Native baseline instrumentation (offline pinned build, not live serving):

```powershell
python test_native_llama_stream.py
python test_native_llama_stream.py --expect-cassi-disabled  # only with -NoCassiModal
python test_native_llama_parallel.py --requests 16
python test_native_llama_slot.py
```

The stream smoke expects the modal metric to be enabled unless `--expect-cassi-disabled` is passed explicitly.

For the OMP-facing retained `mind_complete` seam, the spine now defaults to the existing local OpenAI-compatible llama-server transport against the same loopback service; an injected `createLlamaServerTransport({ baseUrl: "http://127.0.0.1:8080" })` remains the explicit override. Ordinary ohmypi provider sessions remain owned by OMP. The transport uses non-streaming `POST /v1/chat/completions` and does not change the native server's SSE surface.
This OMP/Qwen transport is separate from the field-only provider on `8086` and
is never started by the live conscious terminal.

For a temporary OpenAI-compatible OMP transport seam, run the native server on `8080`, then:

```powershell
python native_omp_provider.py --upstream http://127.0.0.1:8080 --port 8081
python test_native_llama_stream.py --base-url http://127.0.0.1:8081
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
