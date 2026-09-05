# CassiFI Implementation and Publication Plan

**Status:** The bounded canonical local loop and portable evaluation are implemented. The mechanism-first technical paper and corpus-free public version 0.1.0 package are author-approved and license-declared. General system readiness remains `not_ready`; the complete local evidence bundle remains nonpublic because it contains distribution-uncleared material; no external publication action has occurred. This document is not a preregistration.

**Objective:** turn the relocated CassiFI working prototype into one cooperating, field-owned intelligence and then produce a reproducible paper release. The target is not a collection of adjacent demos that happen to share a tensor or a storage directory. It is one identity-scoped state machine whose chat, recall, planning, world interaction, correction, and restart paths all consume and return the same canonical adaptive state.

The plan deliberately separates three things:

1. **Implemented evidence:** behavior already present in the relocated prototype and preserved byte-for-byte.
2. **Packaging work:** making that evidence and its source closure portable without rewriting historical receipts.
3. **Planned evidence:** behavior that must be implemented and measured before any stronger paper language is allowed.

The current prototype is a bounded implementation and evidence base, not a claim that every architectural capability below has been established.

## 1. Current lineage and packaging boundary

### 1.1 Relocated prototype contents

The current implementation boundary is `prototype/`. Its live Python dependency closure, runtime entry points, configurations, schemas, designs, checkpoints, receipts, and tests have been relocated there. The root modules include (among others):

- `cassi_qi_field.py` (`QiFieldState`, `QiFieldController`);
- `cassi_field_language.py` (`CassiQiTextEngine` and field trajectory law);
- `cassi_grounded_language.py` (`CassiGroundedEventCodec` and grounded selection);
- `cassi_temporal_language.py` (effect prediction, transition registers, causal ports, ordering);
- `cassi_field_agent.py` (`CassiFieldAgent` and persistent world/session loop);
- `cassi_persistent_provider.py` (`SharedFieldLayout`, `SharedFieldSessionStore`, `PersistentFieldProvider`);
- `cassi_counterflow_runtime.py` (`DerivedCounterflowRuntime`);
- `cassi_qi_world.py` (`DeterministicQiWorld`);
- `cassi_universal_data.py` (exact ingress/replay boundary);
- the abstraction, relational, counterflow, recall, and gauntlet runners;
- `runtime/`, `training/`, `verification/`, `configs/`, `schemas/`, `designs/`, and `artifacts/`.
- The intended packaging end state is a clear CassiFI root: live implementation, paper, and release assets reside under `prototype/`; unused implementation remains under `legacy/prototype/`; the parent CassiFI root contains no duplicate live modules or ambiguous second source tree.

The root-level imports intentionally remain flat. Moving a module into a directory must not create an alternate import convention or require a second set of compatibility aliases.

### 1.2 What is evidence and what is not

The following are preserved current observations, not predictions of the integrated system:

- the next-symbol trajectory baseline has `0/16` exact natural continuations and `16/16` false settlements under autoregressive generation; bounded text abstraction instead abstains on all sixteen natural holdouts;
- the exact-context Phi harmonic field currently abstains on all `16/16` prose holdouts;
- the text and role grammar controls demonstrate supported finite laws, while natural continuation remains unsupported;
- the mixed general-task gauntlet reports diagnostic checks but `readiness.status = "not_ready"`, with learned cross-view transfer still unsupported;
- existing null/abstention labels, including `NULL_NO_SYMBOL_CHANGE`, and the current bounded grammar and capacity limitations remain part of the evidence record;
- existing relational, counterflow, universal-data, persistence, and replay results retain their existing denominators, margins, residuals, and control outcomes.

No relocation or paper rewrite may silently convert a null result to a success, pool historical arms into a new denominator, or describe a fixed projection as learned cross-view transfer.

### 1.3 Version and asset lineage

`paper-version.json` binds the current paper/source/assets. For a final release, the binding must cover:

- paper identity/version and the separately reported system readiness (`not_ready` while required capabilities are missing);
- exact relative path and SHA-256 for `cassi-technical-paper.md`;
- exact source paths and hashes for every claimed entry point and imported module;
- exact config and schema paths/hashes;
- exact corpus files and corpus manifest hashes;
- exact checkpoint files, state hashes, and training-receipt hashes;
- exact historical report/receipt references, with their original paths and hashes;
- the portable release receipt set and raw per-case output hashes;
- environment identity (Python, PyTorch, device, operating system, dependency lock/version data, and command-line arguments);
- an explicit distinction between historical absolute-path receipts and newly generated manifest-relative portable receipts;
- licensing/provenance status for every corpus and redistributable asset.

The manifest is a binding index, not a replacement for the receipts. Historical artifacts remain byte-identical in their current archived locations, even when their embedded paths are absolute or no longer valid on a clean machine.
The intended public prototype closure is one self-contained bundle of the current paper, live code, configurations, exact permitted corpus bytes, canonical checkpoints, and reports/receipts, with any unavailable corpus explicitly identified rather than silently omitted.

### 1.4 Corpus and checkpoint placement

Exact source bytes for any corpus used by a portable reproduction belong under `prototype/data/corpora/`. A manifest-relative source entry must identify the file, byte hash, encoding/codec, source license, and split membership. No runner may silently fetch or substitute a corpus.

The canonical checkpoint chain currently documented by the prototype is:

```text
artifacts/cassi-qi-corpus-language/field-state.pt
  -> artifacts/cassi-qi-grounded-language/field-state.pt
  -> artifacts/cassi-qi-spatial-language/field-state.pt
  -> artifacts/cassi-qi-reference-language/field-state.pt
  -> artifacts/cassi-qi-temporal-language/field-state.pt
```

The plan preserves those files and their current receipts. New training and replay output goes only to `prototype/artifacts/portable-release/` (or a precisely named child beneath it), never to a historical artifact directory and never over an old absolute-path receipt. Portable runners must resolve paths from the prototype root or the release manifest, not from the original checkout location.

`legacy/prototype/` is an archive boundary for unused prototype Python and related historical implementation surfaces. Archived code is not imported by the canonical runtime, is not a runtime fallback, and is not presented as part of the integrated implementation. Historical receipts, reports, preregistrations, and checkpoints are not rewritten merely to make the archive look clean.

### 1.5 Known hash discrepancy

A known historical source-hash mismatch exists between the current language source/trainer and a retained receipt. This is provenance information, not an invitation to repair history. The old receipt and any retained historical source snapshot remain unchanged; current source must not be described as the bytes bound by that receipt. The mismatch is recorded in the release manifest. A newly generated portable receipt binds the exact source actually executed, but must never overwrite or retroactively “correct” the old hash. The paper must state which receipt is historical and which receipt was regenerated from the exact release source.

## 2. Ordered implementation phases

The phases are ordered by dependency. The CassiFI-owned implementation and evaluation work has now been executed through the portable release receipt set. The resulting system and publication statuses remain separate: the canonical local runtime is implemented, evaluation gaps 1–5 and 7 are supported, gap 6 is `not_ready` because energy/FLOP instrumentation is unavailable, gap 8 is `not_ready` because the separately authorized authenticated CassiFI–CassiCosmos adapter and windowed receipt are absent, and publication remains `not_ready` pending licensing, paper revision, and any external release action.

### Phase 0 — Freeze the evidence boundary and make the package self-contained

**Targets:** `prototype/cassi_fi_paths.py`, all live imports of `ARTIFACT_DIR`, `CONFIG_DIR`, `DESIGN_DIR`, and `SCHEMA_DIR`; corpus manifests and source loaders; `prototype/paper-version.json`; `prototype/artifacts/portable-release/`; `prototype/data/corpora/`; the separate `legacy/prototype/` archive.

**Work:**

1. Make `ROOT = Path(__file__).resolve().parent` the only package-root anchor for live prototype paths. Convert live corpus references to manifest-relative entries under `data/corpora/`; do not add a second import/path convention.
2. Enumerate the exact code/config/schema/design/corpus/checkpoint/report closure of the current paper. Include imports that are exercised indirectly by runners, not only top-level scripts.
3. Record each historical artifact without editing its bytes. Mark absolute-path receipts as historical and do not pretend they are portable.
4. Create the `paper-version.json` binding described above and define a separate portable-release output namespace.
5. Check licenses and redistribution rights before copying any corpus bytes into a public release. If a source cannot be distributed, bind an explicit acquisition instruction and hash without claiming a self-contained public corpus.

**Deliverables:** a manifest-relative source/corpus/checkpoint closure; a populated version manifest; an untouched historical archive; and a portable-release directory reserved for newly generated receipts and raw outputs.

**Completion condition:** from a clean process launched with its working directory outside the original checkout, every claimed current-prototype command resolves only package-relative assets (except an explicitly optional world service), emits only under `artifacts/portable-release/`, and records exact source/config/schema/corpus/checkpoint/environment hashes. The historical receipts compare byte-for-byte with their pre-relocation copies. This is packaging proof only; it does not prove integrated intelligence.

### Phase 1 — Establish canonical field ownership before adding capability

**Targets:** `prototype/cassi_field_agent.py` (`CassiFieldAgent.__init__`, `open`, turn/commit methods); `prototype/cassi_field_language.py`; `prototype/cassi_persistent_provider.py` (`PersistentFieldProvider`, `SharedFieldLayout`, `SharedFieldSessionStore`); `prototype/cassi_counterflow_runtime.py` (`DerivedCounterflowRuntime.status`, consolidation); `prototype/cassi_qi_world.py`; provider/CassiCore boundary code.

The previous ownership issue is resolved in the current implementation: `CassiFieldAgent` derives routing from the provider-owned canonical persisted field instead of creating an independent adaptive `self._route_state`. `SharedFieldLayout` remains serialization/layout machinery; ownership is established by provider checkpoints and causal transition receipts rather than by tensor packing alone.

**Work:**

1. Remove the independent adaptive routing owner. Either derive routing from the canonical persisted `QiFieldState.field` or use a demonstrably fixed, nonadaptive codec. If a route is learned, its influence must be a defined region/transition of the canonical field and must be included in the provider-owned checkpoint lifecycle.
2. Define one state-in/transition/state-out path for chat, recall, planning, and world interaction. Every transition records explicit identity scope and task scope; no operation may read a private adaptive cache or commit a second learned state.
3. Make the provider own checkpoint creation, atomic replacement, restore, and lifecycle sequencing for all canonical components. A caller may supply an immutable request or fixed policy, but not a competing learned checkpoint.
4. Treat `SharedFieldLayout` as serialization/layout machinery only. Add ownership and causal receipts that show which transition wrote which field slice and that all consumers read the same prior state.
5. Preserve the current counterflow fact precisely: exact counterflow commit evidence is persisted in the provider's counterflow field slice. `DerivedCounterflowRuntime` operators/search paths are ephemeral execution machinery. Its status now distinguishes `mode: "persisted_provider_owned"`, `persistent_state: true`, and `derived_scratch: true`; this does not claim that ephemeral operators are learned state.
6. Exclude optional Qwen particle-program drafting and the legacy learned world-model from canonical execution. They may remain explicitly labeled experimental/archive surfaces but cannot become silent fallbacks.
7. Keep the CassiCosmos local `_plasticity_buf` / `_state_buf` learner experimental and off for the canonical bridge until ownership is unified. Do not claim that a shared API or shared tensor packing has unified it.

**Deliverables:** one canonical transition API in code; ownership and scope fields in transition receipts; provider-owned checkpoint lifecycle; route persistence/restart evidence; corrected counterflow status semantics; and explicit exclusion of noncanonical execution paths. Do not add a separate contract or governance document.

**Completion conditions:**

- changing a learned routing region changes a later route, and the same route influence is observed after close/reopen from the provider checkpoint;
- chat, recall, planning, and world calls each expose matching state-before/state-after hashes and identity/task scopes;
- a transition that bypasses the provider or writes an adaptive sidecar is rejected;
- the Phi, counterflow, and any additional canonical slices have one atomic state hash and one owner;
- a counterflow observation survives restart in its provider field slice while ephemeral operator/search objects are recreated; and
- Qwen particle drafting, the legacy world model, and the CassiCosmos local learner are absent from the canonical execution receipt.

No stronger cooperation result is claimed before these conditions pass.
**Executed status (portable release v3):** complete for the CassiFI-owned path. Ownership, checkpoint, route-restart, scope, sidecar rejection, counterflow, Qwen exclusion, and noncanonical learner exclusion are recorded in `artifacts/portable-release/implementation-evaluation.json`. The real CassiFI–CassiCosmos adapter remains a separate `not_ready` boundary under Gap 8.

### Phase 2 — Implement a crash-safe action lifecycle

**Targets:** `prototype/cassi_qi_world.py` action descriptors/revisions; `prototype/cassi_field_agent.py` action selection and `_save`; `prototype/cassi_persistent_provider.py` journal/session store; the transactional CassiCore/Mnemic journal boundary; action schemas under `prototype/schemas/`.

**Canonical lifecycle:**

```text
proposed -> authorized -> dispatched -> outcome_pending -> observed/consolidated
```

**Work:**

1. Give every proposed action a durable `action_id`, identity scope, task scope, predecessor field/world revision, command hash, authorization path, and validity interval.
2. Make authorization an explicit transition. A proposal is not a dispatch, and a dispatch is not an observed outcome. Fixed exact policy/journal state may live outside the tensor; it must be content-addressed and nonadaptive.
3. Journal the dispatch intent and world revision before execution, then record the dispatch acknowledgment and enter `outcome_pending`. Persist enough information to reconcile after a process crash.
4. On restart, reconcile an outstanding dispatch against the world/journal revision before permitting any retry. A crash after dispatch must not blindly execute the command again.
5. Admit exactly one observation for each action/world revision. Consolidation must be idempotent by `action_id` plus observation identity and must update the canonical field only after the observed result is verified.

**Deliverables:** versioned action journal records, durable world revisions, reconciliation logic, idempotent observation/consolidation, and targeted duplicate/restart/crash-after-dispatch tests with receipts for every lifecycle transition.

**Completion conditions:** duplicate authorization, duplicate dispatch, duplicate observation, restart during each lifecycle edge, and crash immediately after dispatch all produce one world effect, one observed outcome, and one field consolidation. Reconciliation either finds the already-dispatched action or records an explicit unresolved/failed state; it never blindly retries. Exact replay from the same checkpoint and journal is byte-identical.

The lifecycle is a prerequisite for the end-to-end scenario and for any claim that a learned field changes real action rather than merely changing a local proposal.
**Executed status (portable release v3):** complete for the exercised local action path. Insufficient authority is rejected before creating a durable proposal, allowing an authorized retry. Complete action/reconciliation transitions are serialized per identity across provider objects. Regression runs cover concurrent duplicate requests and crashes after world dispatch, outcome recording, and checkpoint persistence; they produce one world revision and one canonical field consolidation.

### Phase 3 — Demonstrate one end-to-end cooperating intelligence

**Targets:** the canonical agent/provider/world path assembled from `cassi_field_agent.py`, `cassi_persistent_provider.py`, `cassi_qi_world.py`, `cassi_field_language.py`, `cassi_temporal_language.py`, and the exact journal boundary.

**Scenario:** use one identity and declared task scope through:

```text
teach -> recall -> plan -> authorize -> execute -> observe -> correct -> restart
```

The scenario must include a task not seen in the teaching episodes. Its changed action must arise from retained field experience, not from a host lookup, route table, vector database, model service, or hidden metadata shortcut.

**Controls and interventions:**

- a relevant field lesion must change the committed decision or force an evidence-conditioned abstention;
- an unrelated lesion with matched magnitude/statistics must not change that decision;
- a restored checkpoint plus journal replay must recover the same identity, task scope, pending-action status, world revision, field hashes, and final decision;
- repeating the exact scenario in a clean process must produce byte-identical transition and receipt hashes;
- withholding the observation must prevent consolidation and prevent the system from claiming a learned outcome; and
- shuffled teaching/outcome correspondence must remove the claimed transfer rather than merely lower a cosmetic score.

**Deliverables:** one raw per-case trace and one summary receipt binding every state transition, field slice, action ID, world revision, lesion, restart point, and environment hash.

**Completion condition:** the complete trace runs in a clean process from the portable package, with any optional world service explicitly declared. Report every control and denominator. Until then, report component demos rather than one cooperating field-owned intelligence.
**Executed status (portable release v3):** complete for the canonical local provider and deterministic analytic-world scenario. The raw summary records teaching, recall, planning, authorization, execution, observation, correction, restart, lesions, withheld observation, shuffled correspondence, and clean-process replay. It does not claim a live Cosmos bridge.

## 3. Required evaluation gaps after ownership is real

These are eight distinct gaps. They must be evaluated only after Phases 1–3 have an unambiguous canonical path. Each gap requires raw per-case output, a matched control, an exact source/config/schema/corpus/checkpoint binding, and a status of `supported`, `unsupported`, `ambiguous`, or `not_ready`; a missing measurement is not a pass.

### Gap 1 — Shared overlapping capacity, contradiction, and supersession

**Target:** the canonical field update/recall path and its capacity accounting, not isolated component fixtures.

**Experiment:** train overlapping facts/tasks until capacity is shared rather than partitioned into disjoint demonstrations. Include contradictory observations, explicit supersession/replacement, stale facts, and unrelated facts. Separate intended replacement from accidental overwrite.

**Required evidence:** retained-fact accuracy, contradiction detection, supersession latency, old/new revision lineage, interference on unrelated facts, abstention when evidence is insufficient, and field/state hashes before and after each update. A replacement is successful only when the new revision is selected for the intended scope and the old revision remains auditable rather than disappearing.

**Pass condition:** the same canonical field accounts for capacity and shows scoped replacement without uncontrolled collateral loss. A failure is reported as such; it is not hidden by allocating a second memory store.

### Gap 2 — Target-blind, variable-length language

**Target:** `run_text_abstraction_comparison.py`, its language controller/oracle path, and the paper's language claims.

**Experiment:** replace target-length-dependent FIT/REPEAT-style inference with variable-length inputs and outputs and an inference API that cannot access the target or its length. Remove `_target_aware_oracle` from every claimed inference path. The oracle may remain a clearly labeled evaluator-only diagnostic, never evidence of learned language.

**Required evidence:** raw predictions, evaluator-only targets and lengths, input length, stopping decisions, per-position accuracy, exact continuation, abstention, and target-blindness checks. Verify that target-dependent padding, FIT/REPEAT arguments, metadata, and oracle-derived values cannot reach the controller; the separate evaluator may inspect targets to score results.

**Pass condition:** any language success survives target-blind variable-length evaluation; otherwise retain `not_ready` and the current `0/16` exact/`16/16` false-settlement result.

### Gap 3 — Risk coverage and calibrated uncertainty

**Target:** field decision receipts and abstention policy in the canonical agent/provider path.

**Experiment:** report risk-coverage curves over raw margins and abstentions, stratified by task and identity scope. Preserve every raw margin and runner-up score. Use ECE or Brier score only if the system emits genuine probabilities with a declared probability-generating law and held-out calibration data; margins are not probabilities.

**Required evidence:** coverage, selective risk, abstention reasons, calibration split, raw scores/margins, and confidence provenance. If no true probabilities exist, explicitly omit ECE/Brier and do not relabel margins as confidence probabilities.

**Pass condition:** selective behavior is measured without overclaiming calibration. A useful margin curve can pass while probability calibration remains `not_measured`.

### Gap 4 — Learned cross-view alignment

**Target:** `cassi_universal_data.py`, generative abstraction/gauntlet entry points, and the canonical state transition path.

**Experiment:** learn alignment from shared actions and experience anchors across JSON, raster, text, audio, and scientific tensor views. Randomize nuisance IDs, ordering, metadata, and surface names. Keep the evaluator pair key hidden until evaluation. Do not demand impossible zero-shot recovery of an arbitrary permutation with no shared anchors.

**Required evidence:** disjoint train/evaluation anchor sets, randomized nuisance manifest, hidden evaluator pair key, view-specific raw outputs, correspondence hashes, and a fixed-projection baseline. A fixed lossless projection demonstrates codec invariance, not learned alignment.

**Pass condition:** unseen cross-view pairs transfer using learned shared experience anchors and survive nuisance randomization; absent that, preserve `learned_cross_view_transfer: unsupported` and `readiness.status: not_ready`.

### Gap 5 — Longer compositions and representation shifts

**Target:** grounded/counterflow/relational planners and the language/world scenario.

**Experiment:** evaluate compositions longer than the current three-action and bounded grammar cases, with held-out orderings, renamed entities, moving distractors, boundary regimes, changed representation, and task/identity shifts. Keep source actions, endpoints, and intermediate evidence disjoint as appropriate.

**Required evidence:** exact world revisions, action-by-action trace, search budget, abstention/exhaustion reason, representation manifest, and matched controls for missing middle evidence and endpoint-only shortcuts.

**Pass condition:** the planner's operating range is measured and reported with its true boundary. It is acceptable for a regime to remain unsupported; it is not acceptable to extrapolate a finite candidate-library result into unrestricted composition.

### Gap 6 — Matched compute, memory, latency, and measured energy

**Target:** all comparative evaluation runners and portable-release environment receipts.

**Experiment:** compare canonical field intelligence against an explicitly specified conventional baseline under matched parameter/storage budget, input/output work, wall-clock protocol, batch size, precision, hardware, and warm-up policy. Measure peak memory, latency distributions, and energy with an actual measurement instrument/API.

**Required evidence:** raw timing samples, peak allocation/resident memory, parameter/field bytes, device/driver/runtime versions, measured energy and measurement method, and baseline configuration. TDP, nominal board power, or a static hardware specification is not an energy measurement.

**Pass condition:** any efficiency claim is limited to matched measured quantities. If measured energy is unavailable, omit energy claims rather than substituting a TDP proxy.

### Gap 7 — Orthogonal lesions and a same-statistics conventional baseline

**Target:** canonical field storage/update/search/codec code and the evaluation harness.

**Experiment:** apply orthogonal lesions to storage capacity, update law, search/transition operator, and codec/boundary while holding other factors fixed. Add a conventional baseline matched for data, compute, memory, and output policy. Include same-statistics random lesions and shuffled controls.

**Required evidence:** lesion definition and hash, affected/unaffected slice, raw decision changes, null controls, baseline configuration, and per-case causal effect. A lesion that merely changes a shared tensor checksum without changing the claimed behavior is not evidence of ownership.

**Pass condition:** each claimed mechanism has a selective behavioral signature and the conventional baseline is not disadvantaged by an unequal resource or metadata path. Otherwise downgrade the mechanism claim.

### Gap 8 — Real FI–CassiCosmos bridge

**Target:** the actual FI/CassiCosmos integration boundary; no canonical implementation is created by this plan alone.

**Experiment:** connect the canonical provider to a real CassiCosmos run with the local CassiCosmos learner off, one field-owned state/checkpoint owner, and one windowed GPU run following the house rules for launch, orphan hygiene, device-loss handling, and receipt capture. The bridge must use explicit observations/actions and the Phase 2 lifecycle, not an unlogged side channel.

**Required evidence:** bridge source/config/schema hashes, exact device/runtime metadata, one windowed run receipt, action/world revisions, provider field hashes, no `_plasticity_buf`/`_state_buf` learning, no hidden Qwen/legacy fallback, and raw GPU/window lifecycle evidence.

**Pass condition:** the real bridge produces a reproducible observed transition under those constraints. A CPU mock, a static screenshot, or a shared API surface is not a bridge result. If the local learner cannot remain off or ownership cannot be unified, report the bridge as `not_ready`.

## 4. Release integrity and reproduction

Release evidence is generated only after the exact source intended for the paper has been frozen. Before revising paper results, regenerate every claimed receipt from that source; do not edit receipt numbers by hand.

### 4.1 Binding requirements

Every portable receipt must bind:

- source files and import closure, each with a relative path and SHA-256;
- configuration values and config hash;
- schema versions and schema hashes;
- exact corpus bytes, corpus manifest, source license, split, and payload hashes;
- checkpoint bytes, state hash, learned-memory hash where defined, and parent checkpoint lineage;
- raw per-case outputs, trace files, and summary hash;
- command line, seed, process mode, Python/package versions, OS, CPU/GPU/device/driver, precision, thread settings, and relevant environment variables;
- optional external services by URL/version/config only when they are explicitly allowed, with the local path remaining the default; and
- release manifest and receipt schema versions.

No output path may point outside the package except an explicitly optional world service or an explicitly nonredistributable corpus acquisition path. The latter must be visible in the manifest and cannot be presented as self-contained reproduction.

### 4.2 Clean-process relocation proof

The release check runs from a copied/relocated package in a fresh process with the original absolute checkout path unavailable. It verifies that imports, corpus loading, checkpoint loading, receipt writing, journal replay, and restart restoration use manifest-relative paths. It compares the relocated run's deterministic hashes to the portable reference and checks that historical receipts remain untouched.

### 4.3 Licensing gate

Before any public corpus or checkpoint distribution, record the license, attribution, redistribution permission, and any required notice for each source. A hash-bound unavailable source may be referenced for reproducibility, but the paper must not call the release self-contained if the bytes cannot legally ship.

## 5. Paper rewrite and claim discipline

**Target:** `prototype/cassi-technical-paper.md` explains how field intelligence works and why its mechanisms matter for major AI problems. Preliminary experiments support and qualify that explanation; they do not determine the paper's structure. Missing information is identified explicitly rather than replaced with inferred results. The current manifest binds the rewritten manuscript after release regeneration.

### 5.1 Required present-state results

The paper must preserve the current negative and bounded results exactly, including:

- `not_ready` status for the general-task readiness surface;
- `0/16` exact next-symbol language continuations and `16/16` false settlements;
- Phi `16/16` abstentions;
- `NULL_NO_SYMBOL_CHANGE` where it is the current null result;
- the bounded grammar and its finite candidate-space interpretation;
- current capacity, boundary, noise, moving-distractor, and representation limitations; and
- the distinction between fixed codec/projection invariance and learned cross-view alignment.

Historical receipts remain historical. New portable receipts are cited as new lineage with their own hashes and status.

### 5.2 Terminology

Use the following terminology consistently:

- **field-resident adaptive memory** for the persisted adaptive tensor state;
- **gradient-free transition learning** for the local update law where that is exactly what was measured;
- **bidirectional multi-trajectory deliberation** for measured forward/backward or multi-trajectory search behavior;
- **evidence-conditioned commitment** for proposals/decisions gated by observed evidence and policy.

The adaptive tensor is parameter-like learned storage. Do not infer “no learned storage” from “no optimizer,” and do not conflate the absence of an optimizer with the absence of learned state. Conversely, do not call fixed metadata, a codec, a route table, or a packed layout adaptive field intelligence.

### 5.3 Related work

The related-work section may name Coconut, Titans, Latent Thought Flow, and Latent Recurrent Thoughts to contextualize recurrent/latent computation and memory claims. Each reference must be verified against the literature and described as related work, not as an independent Cassi replication or evidence for Cassi's results. The paper must separate literature comparison from the repository's measured implementation.

### 5.4 Publication gate

Stronger integrated-system language requires the corresponding ownership, lifecycle, and evaluation evidence. A bounded or negative study may be publication-ready without general system readiness: preserve `not_ready` wherever the system evidence requires it. Publication requires reproducible artifact lineage and claims that stay within measured results, not a positive outcome on every research question.

## 6. Dependency and release order

```text
freeze historical evidence and archive boundary
        |
        v
portable paths + corpus/checkpoint closure + paper-version.json
        |
        v
canonical state ownership and provider checkpoint lifecycle
        |
        v
crash-safe action journal and exactly-once observation
        |
        v
teach -> recall -> plan -> authorize -> execute -> observe -> correct -> restart
        |
        +--> shared capacity/contradiction/supersession
        +--> target-blind language
        +--> risk coverage/calibration
        +--> learned cross-view alignment
        +--> longer compositions/representation shifts
        +--> matched resources/energy
        +--> orthogonal lesions/baseline
        +--> real FI-CassiCosmos bridge
        |
        v
regenerate portable receipts from exact source
        |
        v
rewrite paper, verify citations/claims, then decide publication status
```

Independent evaluation gaps may run in parallel once the relevant canonical implementation and lifecycle are stable. Their receipts must be independently bound and must not share mutable adaptive sidecars. A failed gap blocks the corresponding stronger claim, not publication of a reproducible bounded or negative result. System readiness and publication readiness are separate decisions.

## 7. Final observable completion checklist

The implementation and evaluation programme has been executed through the CassiFI-owned boundary. The checklist below records what is verified, what remains `not_ready`, and what is intentionally outside this task.

- `prototype/` is self-contained for the claimed local reproduction, with exact corpus bytes where licensing permits;
- `legacy/prototype/` is noncanonical and no runtime fallback imports it;
- historical reports/receipts/preregs/checkpoints are byte-identical and are not relabeled as portable;
- `paper-version.json` binds paper, source, config, schema, corpus, checkpoints, raw cases, environment, licensing, and receipt lineage;
- live routes have no independent adaptive `_route_state`, or prove fixed-codec behavior, and learned route influence survives restart;
- chat, recall, planning, and world transitions share one provider-owned canonical state-in/transition/state-out path with explicit identity/task scopes;
- persisted counterflow evidence and ephemeral derived operators are distinguished in both code and receipts;
- optional Qwen particle drafting, legacy learned world-model behavior, and CassiCosmos local learner buffers are excluded from canonical execution;
- action IDs/world revisions and the full proposed-to-observed lifecycle survive duplicate, restart, reconciliation, and crash-after-dispatch scenarios exactly once;
- the end-to-end new-task, lesion, unrelated-lesion, correction, restore, and replay controls pass or are explicitly reported as failures;
- each of the eight evaluation gaps has raw evidence, matched controls, and a truthful status;
- no ECE/Brier or energy claim is emitted without true probabilities or measured energy, respectively;
- portable release evidence was regenerated from the exact source after the manuscript, licensing, and public-packaging changes; and
- the completed mechanism-first paper preserves nulls and limitations, separates system readiness from public-paper readiness, and makes no capability claim whose required evidence is missing.

## 8. Executed status and release boundary

### 8.1 Release receipt

The current release namespace is `cassifi-implementation-portable-3`. The generated manifest reports the exact inventoried file and byte counts, including the historical/private entries compared byte-for-byte against the preserved parent manifest. The binding files are:

- `artifacts/portable-release/source-closure.json`
- `artifacts/portable-release/implementation-evaluation.json`
- `artifacts/portable-release/implementation-state-final-3/` (current raw transition receipts, action journals, and final provider checkpoints; earlier `implementation-state/`, `implementation-state-action-fix/`, and `implementation-state-final-2/` runs preserve prior release evidence)
- `artifacts/portable-release/clean-process-reproduction.json`
- `artifacts/portable-release/licensing-receipt.json`
- `artifacts/portable-release/release-digest.json`

`verification/verify_paper_bundle.py` was run against the generated manifest and returned `status: "verified"`. The clean-process receipt ran two independent relocated copies outside the original checkout and matched deterministic hash `9c45afcefd2e79ca0a659eed5a9dc4a3f7054eb3cdad43e6f294c9e944a94db6`; it copied no corpus bytes.
The current retained lifecycle run uses `python verification/run_implementation_evaluation.py --state-dir artifacts/portable-release/implementation-state-final-3` with an initially absent state directory. Its raw files are immutable release inputs. For a new retained run, supply a different empty state directory and output path; the runner rejects a nonempty state directory. The evaluation schema v2 receipt binds the six executed source-file hashes and names its retained state directory explicitly.

### 8.2 Implementation and evaluation outcomes

The implementation receipt reports:

| Area | Status | Boundary |
|---|---|---|
| Canonical provider ownership and route restart | `supported` | Routing, transitions, checkpoints, and counterflow evidence use the provider-owned field; no independent adaptive route state |
| Crash-safe action lifecycle | `supported` | Authorized retries, concurrent duplicates, and dispatch/outcome/checkpoint crash controls produce one world effect and one field consolidation |
| End-to-end local loop | `supported` | `teach -> recall -> plan -> authorize -> execute -> observe -> correct -> restart` in the deterministic analytic world |
| Gap 1: capacity/contradiction/supersession | `supported` | Shared-address accounting, contradiction abstention, and intended supersession are measured |
| Gap 2: target-blind variable-length language | `supported` | No target length is supplied to inference; finite typed programs terminate at `EMIT` |
| Gap 3: risk coverage/calibration | `supported` | Nonprobabilistic selection-strength risk/coverage is measured; ECE/Brier is explicitly `not_measured` |
| Gap 4: learned cross-view alignment | `supported` | Learned anchors transfer; shuffled correspondence is the negative control |
| Gap 5: composition/representation shift | `supported` | Depth-three bounded composition survives mixed-case and out-of-envelope lengths |
| Gap 6: matched resources/energy | `not_ready` | Latency, memory, and accuracy are recorded; energy and FLOPs are unavailable from this runtime |
| Gap 7: orthogonal lesions/baseline | `supported` | Relevant lesion changes the decision; unrelated lesion preserves it; nearest-neighbor baseline is recorded |
| Gap 8: real FI–CassiCosmos bridge | `not_ready` | The separately authorized authenticated adapter and required windowed GPU receipt are absent |

The receipt therefore reports `canonical_runtime_complete: true`, `gap_receipts_complete: true`, `evaluation_receipts_complete: true`, and `implementation_complete: false` with blocking gaps 6 and 8. Receipt presence and status reporting do not mean all eight gaps have completed execution evidence. This is an implementation result, not a general-system-readiness claim.

### 8.3 Licensing and publication

The local corpus files were hash-verified against `data/corpus-provenance.json`, but every source remains `redistribution_status: "unknown"` with `publication_authorization: "none"`. `licensing-receipt.json` remains `blocked` for the complete local bundle because it binds those private bytes. The separate public-release policy excludes every corpus and trained/historical checkpoint. Source code is licensed under Apache-2.0; the manuscript and original figures are licensed under CC BY 4.0.

The corpus-free public release is author-approved for final version 0.1.0 packaging. Corpus redistribution rights, resource telemetry, and the real authenticated CassiFI–CassiCosmos integration remain unresolved without blocking the bounded paper release because the public policy excludes the uncleared corpus/checkpoint material and preserves those system limits. No upload, GitHub release, Zenodo deposit, DOI creation, or other external publication action has occurred.
