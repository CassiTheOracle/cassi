# CassiPi — Full Implementation Plan

Status: P01–P11, the isolated P12 provider comparison, and the canonical CassiFI v4 runtime closure are implemented and measured. CassiPi runs the v4 closure installed against the active main Oh My Pi profile: the `cassipi` launcher reuses the profile’s existing configuration and credentials, loads the pinned 18.1.10 owner host with CassiPi alone, binds field data under `~/.omp/cassipi`, and applies exclusive ownership through a launcher-only overlay. The global CassiPi registry entry is disabled, so ordinary upstream `omp` retains `remote-pi@0.7.0` without a competing context mutator. A local-provider smoke exercised the v3 temporal configure/register/learn/bind/select/advance/inspect cycle and changed the field head; a separate ordinary-profile smoke also passed. No external provider was called during this upgrade. The earlier synthetic `cassipi-live` provider trial still records a failed two-request safety bound, so unattended provider cutover remains held pending a bounded extension-tool path and fresh provider approval.

This plan began against the earlier `CassiFI/prototype` runtime. Prototype-specific class names, storage sketches, and checklist wording below are retained as the execution record; they are not current runtime authority. The present implementation is defined by `../CassiFI/runtime/cassipi_closure.json`, `../CassiFI/cassi_field_owner.py`, the CassiPi source, and `README.md`.

## 1. Product and completion boundary

CassiPi is a standalone Oh My Pi plugin that maintains continuity through one field-owned memory, attention, and compaction lifecycle. The model context is a temporary, budgeted view of retained experience. Exact evidence remains recoverable outside the context window.

The predecessor systems contribute capabilities, not three running services:

- Mnemic Field contributes source-bound experience, associations, correction, and learning from outcomes.
- Thalamus contributes context scarcity, protected working material, reversible omission, and source recovery.
- The current CassiFI `FieldIntelligenceOwner` owns all adaptive association, deliberation, selection, consolidation, and correction in one cooperating atlas state.

Oh My Pi continues to own model calls, tools, execution, and permission checks. CassiPi does not execute coding tools or authorize actions on the user's behalf.

### Included in the complete implementation

- Automatic observation, field-owned retention and recall, request-time context projection, and exact evidence recovery.
- Manual and automatic compaction, including threshold, provider overflow, incomplete-response recovery, idle, and mid-turn entry points.
- Source-backed branch summaries, tree navigation, fork, new/resumed/switched sessions, clear, and handoff.
- Explicit remember, recall, correction, forgetting, and inspection through one agent tool.
- Durable replay, crash recovery, concurrent-session isolation, source revision tracking, and cancellation.
- One-time migration of selected predecessor memory and session data, with provenance and validity preserved.
- A standalone local installation, a compatible host build, an isolated-profile rehearsal, an explicit live cutover, and rollback.
- Actual Oh My Pi scenarios and field interventions demonstrating the stated behavior.

### Deliberate product choices

- The implementation packages the current Python CassiFI variational field, atlas, cognition layer, and owner. It does not create a smaller TypeScript imitation or retain the prototype Qi/text runtime.
- No Mnemic Field, Thalamus, CassiCore daemon, Godot, Qwen, embedding service, or auxiliary summarization-model dependency is introduced into the live plugin.
- Native remote/snapcompact/shake summarization strategies are replaced in the CassiPi-owned profile. A request for an incompatible native method is rejected clearly, not silently run beside FI.
- Native speculative/background compaction is disabled in the supported profile. CassiPi's compaction is prepared against a stable revision and committed synchronously at a legal boundary. Concurrent sessions remain supported; this is not a single-session restriction.
- Public npm/PyPI publication, corpus redistribution, cloud synchronization, and new world-action capabilities are not part of the requested local plugin. Local packaging must not accidentally publish restricted assets.
- No independent learned relevance scores, embeddings, topic policies, reinforcement caches, or routing tensors are permitted. Deterministic indexes, source metadata, transient projections, and receipts are allowed.

The release is complete only when the entire included lifecycle is exercised. A plugin that merely mirrors post-compaction events, or works only with ordinary `/compact`, is not complete.

## 2. Grounded starting point

### 2.1 Oh My Pi compatibility

The executable observed in this session reports `omp/18.1.10`. Its inspected launcher path is `C:/Users/Carina/.bun/bin/omp.exe`, with SHA-256:

```text
00b25bb0ad2992d252326a7ecea2527cfb85019b4a6d24a67842cf3712cd6625
```

The separately resolved global npm source package reports `18.0.6`; CassiCore's spine development dependency is `17.3.4`. Neither is the implementation contract for CassiPi.

The source audit uses the exact upstream `v18.1.10` tag and the published npm `18.1.10` metadata. The npm package metadata binds SHA-1 `3d63ff9642390851744d861ca204068aab988fc8` and the release tarball/SHA-512 integrity listed in [O1]. These are source/package identities, not evidence that the binary has already exercised CassiPi's callbacks. Phase P01 verifies the actual target binary and produces a compatibility receipt before installation.

Important source-observed limitations of stock 18.1.10:

1. `session_before_compact` can provide a custom `CompactionResult`; `session_compact` occurs after the host has committed the result.
2. Ordinary extension exceptions/timeouts are caught by the runner and can become `undefined`. In the compaction path that means the default implementation can proceed. Returning `{cancel: true}` handles an error caught inside the callback, but does not cover a runner timeout.
3. Multiple pre-hook results can overwrite each other in registration order. There is no exclusive context-owner declaration in the audited API.
4. Automatic shake and per-turn tool-output pruning bypass the pre-compaction hook. Manual shake performs a persisted history rewrite. Handoff and clear have additional direct paths.
5. Tree-summary generation is a separate path. A missing custom summary can invoke the default branch summarizer; post-tree notification is too late to veto navigation.
6. Context hooks mutate a cloned request view. They do not own the persistent session journal, and later provider transformations still run.
7. `appendEntry` can persist an extension marker, but is not an atomic transaction with a compaction entry or tree/reset operation.

Consequently the full implementation includes a narrowly scoped host ownership facility. It is not honest to promise exclusive, fail-closed ownership using only stock hooks. See section 8.

### 2.2 Current profile requiring cutover

Only relevant configuration keys were inspected. No settings were changed:

| Setting | Observed value | CassiPi cutover intent |
|---|---|---|
| `memory.backend` | `mnemopi` | `off` in the CassiPi profile; CassiPi owns its tool and injection |
| `mnemopi.scoping` | `global` | Preserve source scope during import; do not silently map all global data to a project |
| `autolearn.enabled` | `true` | Disable the competing background memory-writing path |
| `autolearn.autoContinue` | `true` | Disable along with that path |
| `compaction.methodOrder` | `shake`, `remote`, `soft` | Route to the exclusive owner; supported profile retains only the ordinary soft entry point |
| `compaction.dropUseless` | `true` | Disable independent pruning |
| `compaction.supersedeReads` | `true` | Disable independent pruning; perform source-aware replacement through CassiPi |
| `compaction.midTurnEnabled` | `true` | Preserve through owned compaction at legal tool-group boundaries |
| `compaction.thresholdTokens` | `150000` | Preserve as a user preference where it fits the selected model; also enforce actual model limits |
| `compaction.thresholdPercent` | `-1` | Preserve unless the explicitly reviewed profile changes it |

Also set native `compaction.asyncEnabled: false` in the supported profile. Inventory other memory extensions and context-mutating handlers before cutover; do not infer their absence from these keys.

### 2.3 Current CassiFI foundation

The packaged runtime uses the root CassiFI stack directly:

- `cassi_variational_field.py` supplies the zero-centred variational field and deterministic numeric primitives.
- `cassi_field_atlas.py` supplies typed variables, guarded relation charts, field queries, immutable atlas state, and checkpoint encoding.
- `cassi_field_cognition.py` supplies field-owned deliberation, plans, predictions, and computation records.
- `cassi_field_owner.py` is the sole publisher for exact evidence, adaptive field state, checkpoints, corrections, revocation, and replay-safe operations.

The CassiPi boundary adds only work that is host-specific:

- a fixed, visible host-metadata codec; it has no tokenizer, embedding model, content hash feature, or learned sidecar;
- source/event translation, scope guards, provider-compatible projection rendering, and token accounting;
- branch/version bindings and lifecycle prepare/commit/cancel markers;
- an authenticated, single-writer loopback worker and read-only predecessor importers.

Exact source bytes enter CassiFI's own evidence store. Observations enter guarded atlas charts through `FieldIntelligenceSurface`; queries, exact recall, correction, forgetting, and checkpoint activation use the same surface. CassiPi does not reach into a prototype tensor layout or maintain parallel learned state.

## 3. Runtime and ownership architecture

```text
Oh My Pi tools, messages, and lifecycle
                 |
                 v
Thin CassiPi TypeScript extension
                 |
       authenticated local requests
                 |
                 v
One managed Python runtime owner per data home
  - current CassiFI atlas transitions and checkpoints
  - CassiFI exact evidence and source revisions
  - field-directed context projection
  - host lineage bindings, receipts, and recovery markers
                 |
                 v
Provider-compatible context / prepared host transition
```

### 3.1 One runtime owner

Use one supervised Python process per CassiPi data home. Multiple Oh My Pi sessions attach as clients. The process imports the current CassiFI owner in-process and calls its closed surface; it does not relay between independent services or expose a provider/chat endpoint.

The simplest interoperable transport here is a private loopback HTTP endpoint using Python's standard library and the extension's existing HTTP client. It binds only `127.0.0.1`, uses an OS-assigned port and a generated bearer secret, and exposes only CassiPi operations. It does not expose chat completion, arbitrary filesystem access, world execution, or shell endpoints.

- A process lock owns the data home for the full worker lifetime. A second process must attach or fail; it must not initialize a second writable field owner.
- Startup writes an atomic endpoint descriptor containing launch identity, protocol/runtime identities, and the endpoint. Store it under user-only permissions; never log its bearer secret.
- Verify the descriptor with an authenticated identity handshake. A stale descriptor is not authority to kill an arbitrary PID.
- Serialize transitions for a field lineage, and compare expected head/version before commit. Requests from different sessions cannot mutate an uncommitted shared tensor concurrently.
- Shutdown drains admitted work and commits a recoverable boundary. A worker may stop when no clients or pending operations remain. An owner crash releases the process lock; the next owner reconciles durable records before serving context.
- Reads use a committed snapshot or a disposable working view. Only an explicit observation/consolidation/correction transition can change retained adaptive state.

The endpoint is an implementation boundary, not a separately administered product. Installation, diagnostics, launch, and shutdown belong to the one plugin.

### 3.2 One owner, with distinct data roles

`FieldIntelligenceOwner` is the sole authority for exact evidence, atlas state, operation replay, and immutable checkpoints. CassiPi's JSON control ledger contains only host lineage bindings and pending/applied lifecycle markers; deleting it loses host reconciliation metadata, never a second learned state. The loopback descriptor is replaceable process metadata.

Current data-home layout:

```text
field-intelligence-v2/evidence/       CassiFI source manifests and content-addressed exact bytes
field-intelligence-v2/checkpoints/    immutable atlas states and manifests
field-intelligence-v2/operations.log  replay-safe CassiFI operation receipts
cassipi-field-control.json            nonadaptive host bindings and lifecycle markers
runtime.json                          private endpoint descriptor; replaceable
```

The exact-evidence store and checkpoint chain commit under the owner's lock. Rebuildable in-memory lookups may accelerate reads, but they cannot answer semantic recall independently of the field or become a second commit authority.

### 3.3 Scope and branch model

Identifiers are opaque and stable:

- `profile_id`: the explicitly selected Oh My Pi profile/data home.
- `project_id`: an assigned identity bound to the canonical workspace root(s), not a directory basename. Record worktree/repository relationships explicitly.
- `session_id`: the native Oh My Pi session identity.
- `branch_id`: a CassiPi lineage identity anchored to native entry IDs and their parent chain.
- `task_scope`: the active task within that lineage.
- `head_id`: an immutable field-version/checkpoint reference.

Do not confuse native `session_id` with the provider's existing user/storage key. Map `identity_scope` to a stable profile identity and keep it equal to the provider `user`, as the current canonical API requires. Native session, project, branch, and task identities are separate operation metadata. Extend canonical lineage/head selection so multiple branch versions can be stored and activated under that stable identity; do not spoof a new user on every fork or overwrite a single shared checkpoint path across branches.

Forks and branches are versions of the same canonical computation, not Mnemic/Thalamus/FI submodels. A fork starts by referencing an existing head; it does not reteach all inherited messages. Subsequent events create descendant heads. Only the canonical owner activates and advances a view.

A branch view is materialized from its baseline, permitted shared-memory generation, and ancestral events. Learning in a sibling's private task is not silently present in that view. A scope filter applied only after a contaminated shared tensor is read is insufficient.

Project-wide or profile-wide learning enters another branch through explicit, idempotent source-promotion events and canonical replay/transition. Do not average tensors or merge independently trained vectors. A correction/revocation to shared information invalidates affected projections and requires a clean eligible view before another request.

Cross-project and cross-profile disclosure is denied by default. Shared personal memory is explicit. Native additional workspace directories require a declared project mapping; selecting a similarly named folder does not grant access.

## 4. Source, event, and checkpoint semantics

### 4.1 Exact source records

Each immutable source revision records:

- source ID, revision ID, full content hash, byte length, MIME/codec, and object reference;
- profile/project/session/branch/task scope and native source entry identity;
- parent revision, supersession/revocation status, and any exact source span;
- author/origin, original message role, observed timestamp, and trust/claim category;
- fidelity: exact observed bytes, resolved original artifact, partial/truncated observation, or imported derived summary;
- referenced tool call/action identity and observed outcome where applicable.

Full object hashes validate storage. FI's fixed field-address codec may use its existing shorter address representation; a collision or mismatched full digest is an error, never a silent alias.

Record the bytes actually observed. If a tool already returned a truncated representation, label that limit. Resolve and retain the corresponding original artifact only when accessible and within the session's authorized scope. Never advertise unavailable pre-truncation bytes as archived.

Use UTF-8 byte spans with explicit codecs. Preserve code fences, line endings, source-read decorations, and edit anchors as observed. A remembered source read is not a fresh authorization to edit a changed file; check its revision and obtain a fresh read when necessary.

### 4.2 One event vocabulary

Normalize all paths into a bounded canonical envelope:

```text
schema_version, event_id, producer_id, producer_sequence, predecessor_event_id
profile_id, project_id, session_id, branch_id, task_scope
native_entry_id / tool_call_id / provisional observation identity
parent_head_id, event_kind, source_refs, payload_hash, payload
```

Event kinds cover observation, explicit memory declaration, correction, action proposal/start/outcome, shared-source promotion, context reset, branch activation, revocation, and import. These are fixed protocol categories, not learned sidecar state.

- Native entry ID plus source part identifies persisted messages. Pre-persistence tool events use the stable execution/tool-call identity and event stage, then bind to the final entry without a second field deposit.
- Do not use content hash alone as event identity: two deliberate identical user messages are distinct events.
- Store idempotency receipts for the full admitted history, not just the latest watermark. Replaying an older acknowledged request must return its receipt without relearning or dispatching anything.
- Mismatched payload under an existing ID, missing predecessor, conflicting expected head, or incompatible schema fails explicitly.
- Oversized events are chunked into source objects with exact references, not silently shortened to fit a codec limit. Only bounded deterministic observation features enter the field.

Wrap these envelopes in the existing fixed `BoundaryPacket` format. Observation packets may drive a canonical field transition; admission/applied/canceled receipts and host-binding packets are bookkeeping and never become new training observations. A runtime sequence orders packets while the original producer/event identity provides full-history idempotency.

### 4.3 Admission and field commit

The commit protocol is recoverable rather than falsely described as one filesystem transaction:

1. Resolve and hash source bytes; fsync new objects before referencing them.
2. Append one context-admission packet containing the immutable event and pending operation against the expected lineage head. `QiIngressJournal` advances its hash-linked HEAD durably before acknowledging admission.
3. Under the canonical owner's lineage lock, apply the event once from the recorded input head. The field's checkpoint metadata binds the event ID/sequence, source-root digest, and revocation epoch.
4. Write the native checkpoint atomically and obtain its validated output hash.
5. Under the same owner lock, compare the expected lineage head and append an applied-receipt packet binding the output checkpoint, input event, and previous head. The journal record is authoritative; any in-memory or optional SQLite index advances only after that append.
6. Only then acknowledge an applied mutation or expose that head to a projection.

Recovery cases:

| Crash boundary | Required recovery |
|---|---|
| Object written, event not admitted | Object is unreachable; no learned state changed |
| Event admitted, field not committed | Replay that exact event from its recorded parent |
| Checkpoint written, receipt/head not committed | Validate the checkpoint's embedded event binding; finish the receipt/head commit without applying again |
| Reply lost after commit | Return the existing operation receipt |
| Conflicting checkpoint or missing bytes | Quarantine the affected head and stop; never silently initialize an empty field |

One canonical owner performs checkpoint serialization. Extend its transaction metadata/API where needed; do not make the TypeScript extension a second checkpoint writer.

P03 extends the journal's existing latest-packet duplicate check into complete operation/event idempotency and verifies source-object durability before HEAD advancement. Its current append path scans replayed history for a stream watermark; replace repeated full-history scans with a checked, rebuildable in-memory watermark index, not a new event authority. Make the cumulative journal quota explicit, stream large payloads within the existing chunk format, and exercise quota exhaustion without acknowledging lost data.

#### P03-Sizing — deterministic quota policy

P03-Sizing is a required substep of the P03 admission/commit task, completed before that implementation is accepted. It selects concrete shipping defaults and supported hard ceilings from the packaged runtime's actual maximum encoded checkpoint/packet sizes and the declared storage envelope. Record those values in the runtime configuration/schema and diagnostics, not a separate planning document. P11 measures performance at those limits; it does not postpone choosing them until release.

The accounting policy is fixed here:

| Limit | Accounting unit and coverage |
|---|---|
| Logical journal bytes | Integer bytes using the journal's payload-plus-canonical-packet accounting, including control/receipt packets; deduplication does not erase an admitted logical charge |
| Managed physical bytes | Actual bytes of all plugin-managed journal objects, field checkpoints, and staged replacement generations; an obsolete managed generation still counts until removed |
| Packet count | Every committed journal packet, including bookkeeping, plus its prospective admission; source memories and packets are not interchangeable counts |
| Object/file count | Every managed source/manifest/head/checkpoint/staging file; shared content-addressed objects count once physically |
| Recovery reserve | Capacity unavailable to new observations, reserved for outstanding applied/canceled receipts, head changes, and validated checkpoint replacement/rollback |

Use integer byte values internally; display binary units with their exact byte equivalents. Configured quotas must be positive and below the independently declared hard ceilings. Reject a configuration whose recovery reserve leaves no admissible space. Do not silently raise a ceiling or adopt the existing journal's default as the product's sized limit.

Compute the required reserve from two maximum encoded checkpoint sizes plus the maximum outstanding control-record/head cost under the supported in-flight-operation bound. Include file/packet slots as well as bytes. A pending journal-generation rebuild must fit its staging requirement before starting; it cannot consume the reserve needed to finish or cancel existing operations.

Before admission, calculate each prospective charged total. If any would exceed the new-observation allowance, return typed `ADMISSION_CAPACITY` with the limiting metric, used/projected/limit/reserved amounts, and current committed head. Do not admit or teach the observation, acknowledge it as durable, or compact its only remaining host copy. Read-only inspection remains available. Reserved capacity serves completion/cancellation/recovery records only. An actual filesystem write failure still follows the crash-recovery protocol; free-space checks are not a guarantee against another process filling the disk.

P03-Sizing acceptance includes small configurable test budgets: just below/at/above each limit, enough source space but insufficient reserve, receipt completion after source capacity is exhausted, interrupted checkpoint replacement, and interrupted generation rebuild. Tests assert admission, committed heads, exact source recovery, and explicit rejection. Quota exhaustion never triggers automatic forgetting or source deletion.

### 4.4 Provenance and epistemic distinctions

The archive distinguishes a user instruction, a design assumption, an assistant claim, an observed tool result, a hypothesis, and an imported summary. Hash validation proves identity, not semantic truth.

For example, the instruction to assume the cooperating FI core will be ready is a current design premise. It must survive compaction without converting historical implementation evidence into a false completion receipt.

An action proposal is not dispatch. Dispatch is not success. A missing outcome remains unresolved. Tool failures can teach against an attempted action while retaining the failure evidence as useful experience; do not globally weaken every memory involved in an unsuccessful task.

## 5. Field-owned retention and context projection

### 5.1 Canonical API additions

The following are proposed capabilities of the existing canonical transition owner, not claims about its current public operation list:

- `observe`: validate and apply a source-bound event, with durable idempotency and complete state receipts.
- `project`: read a committed scoped state under task and token-budget inputs; return selected source spans, representation choices, support/margin, and references.
- `activate`: activate a lineage/version with expected native session/branch binding.
- `rebuild`: replay eligible retained events from a compatible clean baseline after revocation or an approved migration.

Explicit remember/correct operations normalize to `observe` with appropriate typed payloads. Existing canonical teach/recall/plan mechanisms remain implementation primitives inside that owner. The extension never constructs a field controller or manipulates individual layout slices.

The worker must extend the direct Python owner rather than assuming the existing HTTP chat/context routes expose these operations. Runtime code has no authority to call FI world execution merely because that method exists.

### 5.2 How projection selects evidence

1. Determine hard eligibility from scope, ancestry, validity, revocation, and current authorization.
2. Reserve mandatory material: active instructions, the current request, required tool-call/result groups, exact working reads, and unresolved action boundaries.
3. Supply the current task, source identities, and remaining budget to the canonical field operation.
4. Obtain multiple source/span candidates and representation choices from the field. Extend the existing single-winner readout instead of adding an external learned reranker.
5. Pack the returned choices deterministically, retaining dependency groups and native message order where required.
6. Render valid provider-compatible messages and an auditable projection receipt.

The eligible candidate set must not be secretly truncated by a lexical top-N service before FI sees it. Fixed address encodings and batched scoring are legitimate optimizations if they preserve the canonical field ordering and support/abstention semantics. Prove equivalence before adopting an optimization.

Use exact source IDs for deterministic ties. Do not invent a second weighted score mixing recency, importance, outcome count, and field signal. Hard safety constraints are rules, not an adaptive scoring system.

### 5.3 Representation and language boundary

Supported representations are exact evidence, a source-backed typed account, a reference, and dormant experience. A typed account can render known fields such as an observed command outcome or a declared decision using fixed framing and exact cited text.

Do not make unrestricted FI prose generation a hidden dependency. Field-selected excerpts and deterministic rendering are sufficient for a real continuation context. Assistant-authored concise notes remain attributed derived claims with source references; they are not automatically elevated to user-confirmed facts.

Segment source text at valid message, sentence, code, and tool-structure boundaries. Preserve qualifying context and dependent spans. If a safe concise representation is unavailable, choose exact evidence/reference or report insufficient capacity; do not synthesize an unsupported paraphrase.

A projection typically exposes the current goal, governing decisions, observed progress, unresolved questions/actions, rejected approaches with reasons, and evidence required next. This is a readable view, not a mandatory six-database schema.

### 5.4 Budget and provider correctness

Budget against the actual selected model and host request accounting, including system instructions, tool schemas, protected messages, image costs, and reserved output. Do not budget only the injected memory block.

- Use native legal compaction boundaries and keep tool invocation/result groups intact.
- Preserve required reasoning/replay metadata through the host's validated serializer. Never edit encrypted/provider-native internals as text.
- Preserve trusted instruction roles. Recalled material is explicitly labeled background evidence and does not acquire system/developer authority merely because it is injected by an extension.
- Native normalization and safety/privacy transforms still apply. The final host preflight checks fit and protected structural invariants after those transformations.
- If mandatory material cannot fit, stop with a capacity explanation and recovery choices. Do not discard the user's latest correction or silently send an oversized request.
- When a provider reports overflow despite estimated fit, use the host's bounded recovery path with a smaller owned projection. No unbounded cancellation/retry loop or fallback summarizer is allowed.

Freeze a projection for its declared input revision and provider call. Reuse it only while task, model budget, source revisions, scope, and revocation epoch remain valid. New tool results are new observations; the next request may legitimately have a new projection. Do not reorder an unchanged prefix unnecessarily and destroy prompt-cache reuse.

### 5.5 Learning and consolidation

Initial admission records experience. Canonical observation transitions deposit its permitted features once. Completed action/turn evidence can consolidate the relation between the context used, action attempted, and actual outcome through the same field.

Reading, rendering, inspecting, copying a summary, navigating, and replaying an acknowledged event do not count as new corroboration. Context-generation scratch evolution must not silently alter trained persistent memory.

A compacted summary is never recursively promoted into primary experience. Reconstruct from original source-bound records plus the canonical state. Source relationships remain exact provenance unless the canonical transition actually learns an association; an event that only advances a watermark is not proof of field learning.

## 6. Oh My Pi event and tool integration

### 6.1 Event handling

| Surface | CassiPi responsibility |
|---|---|
| Extension load | Register one factory, one owner declaration, one tool, and `/cassi`; perform no runtime action during factory loading |
| `session_start` | Connect/launch owner, validate compatibility and profile mapping, recover pending operations, activate the correct durable head |
| Message/tool lifecycle | Capture exact observed payloads, attach stable source/action identities, reconcile pre-persistence observations, and enqueue each canonical event once |
| `context` | Produce the transient provider view from an acknowledged scoped head; never rewrite native session history here |
| `before_provider_request` / host final preflight | Verify the final accounting and required structure; do not rebuild opaque provider payloads with ad hoc JSON surgery |
| `session_before_compact` | Prepare and return the complete custom `CompactionResult`, or explicit cancellation |
| `session_compact` | Confirm the native committed entry, bind its ID to the prepared operation, and reconcile; never act as the authorization point |
| `session_before_tree` | Prepare target activation and, only when requested, the branch summary from the same field projection |
| `session_tree` | Confirm actual resulting leaf/summary IDs and activate the corresponding head before another model request |
| `session_before_switch` / `session_switch` | Prepare/commit new, forked, resumed, or switched session identities through the same lifecycle |
| Branch/retry/reanswer surfaces | Bind their actual native parent/target IDs; do not treat reanswer as an unrelated new memory stream |
| Clear/handoff/shake entry points | Enter the host-owned rewrite/transition path described below; no direct native bypass |
| Shutdown/disconnect | Flush admitted events, retain unresolved action status, and release the client without pretending pending actions succeeded |

Hook names above are audited 18.1.10 surfaces where present. The host additions in section 8 provide missing ownership, failure propagation, stable operation binding, and bypass coverage.

### 6.2 One agent tool

Tool name: `cassi_memory`. Its operation schema is closed and versioned.

| Action | Inputs | Observable result |
|---|---|---|
| `recall` | Query or exact source reference, permitted scope, bounded result budget | Selected evidence/refs, provenance, support/abstention, continuation cursor where needed |
| `remember` | Content/declaration and source refs; scope requested explicitly when wider than the task | Source ID/revision, committed event/head/receipt, attributed claim category |
| `correct` | Target revision, replacement/correction, source refs, intended scope | Explicit supersession and canonical correction receipt; historical source remains distinguishable |
| `forget` | Exact target/scope and a confirmed preview token | Revocation/rebuild result, remaining external copies/limitations, receipt without re-embedding erased content |
| `inspect` | Current state/projection/operation/source selector | Data-backed state, eligibility, source references, field metrics, and current recovery status |

Scope and authority come from the authenticated host session, not arbitrary tool arguments. The tool cannot grant itself access to another project. Its result is bounded and paged through the same single tool.

A forgetting confirmation token is minted only after direct interactive user approval. Bind it to the exact target set, scope, current revision/revocation epoch, and one operation; consume it once. An agent-supplied `confirm: true`, quoted approval, or token for a different target is not confirmation.

`inspect` reports observable receipts and field support, not invented introspective explanations. A field margin is not a calibrated truth probability.

### 6.3 One human command

`/cassi` exposes status, current context/evidence inspection, explicit remember/correct/forget, capture pause/resume, import preview, and recovery/diagnostics. Use existing Oh My Pi UI components, concise labels, and plain descriptions. Do not create a second dashboard application.

Paused capture means no new CassiPi learning. It does not delete host history. In exclusive mode, a missing required archive/owner cannot be silently bypassed: context rewrite pauses until recovery or an explicit owner deactivation. Normal `/compact` uses CassiPi while ownership is active.

Do not alias or silently shadow stock memory tools/URLs. Stock memory is disabled in the supported profile; the source index and tool are CassiPi-owned. A generic host memory-backend registry is unnecessary for this release.

## 7. Compaction, tree navigation, and session transitions

### 7.1 Compaction preparation and commit

For each owned compaction:

1. Settle prior observed events and capture the native session ID, leaf, preparation boundary, source coverage, and expected FI head.
2. Persist a prepared operation with a unique operation ID. Preparation is not a claim that the host committed anything.
3. Obtain a source-backed projection against that stable revision and remaining budget.
4. Return the host's `CompactionResult`: `summary`, `firstKeptEntryId`, `tokensBefore`, and structured `details`; populate additional supported display metadata only as verified by the pinned types.
5. Put protocol/runtime identity, operation ID, checkpoint hash, source-root digest, covered-through entry, selected refs, and revocation epoch in `details`. The summary must be useful without dereferencing hidden metadata.
6. The host validates the result and commits the native compaction entry using that operation identity. It preserves the legal retained suffix and does not run another compactor afterward.
7. Post-commit notification acknowledges the actual native entry ID. The owner records the binding; repeated notifications are idempotent.

On restart, match prepared operations against durable native entries/markers. A prepared operation without a matching host commit is not activated. A matching commit without a post-event acknowledgement is completed without learning twice.

Cancellation, owner timeout, malformed output, missing exact source, stale expected head, or insufficient protected budget cancels the operation. The previous host history and acknowledged field head remain usable. If a native commit has already occurred, recovery reconciles that committed fact and blocks further provider use until the correct head is activated; it does not pretend the commit never happened.

### 7.2 Tree navigation and branch summaries

Use the native target ID, old leaf ID, deepest common ancestor, entries-to-summarize, and `userWantsSummary` from preparation. These are source identities, not hints to reconstruct from UI text.

Before navigation:

- Prepare the target lineage view without switching the active field head.
- If the user requests a summary, project the abandoned branch's relevant experience with explicit originating-branch/source provenance. Return `{summary: {summary, details}}` through `SessionBeforeTreeResult`.
- If no summary is requested, do not generate or persist one. Still prepare activation and its recoverable operation binding.
- On no-op navigation, cancellation, or a stale source leaf, leave the active state unchanged.
- Respect native user-message editing and ask-tool reanswer semantics. The requested target ID and resulting leaf ID are not always equal.

After the native commit:

- Use actual `newLeafId`, `oldLeafId`, summary entry, and native parent chain, not the initially guessed target, to confirm activation.
- Bind the resulting head to a durable native owner marker/summary details through the host facility. Navigation without a summary still needs a recoverable active-head marker.
- Keep transferred summaries as attributed branch evidence. Do not reteach the original observations or make abandoned-branch assumptions silently authoritative.
- A worker/post-hook failure prevents the next provider request until reconciliation completes.

Restoring conversational state does not undo files or executed actions. Validate recalled working-tree claims against current revisions.

### 7.3 Fork, switch, resume, clear, and handoff

| Operation | Required semantics |
|---|---|
| Fork | New native session identity; inherited source aliases and shared head reference; no duplicate deposit, no invented new action outcomes; future task events diverge |
| Switch/resume | Drain/persist the departing session, validate the target's committed marker and source lineage, activate target view, then allow model use |
| New session | Start a new task view with explicitly eligible shared experience; do not carry the previous session's unfinished task implicitly |
| Clear | Preserve exact archive and eligible durable project memory, but commit a context-reset boundary and a fresh working-task view; never resurrect pre-clear working context on rebuild |
| Handoff | Produce the handoff through the same projection/commit operation with source and head references; no separate LLM-generated handoff memory |
| Shake | Route a requested reduction through the owner and preserve exact archive. Reject a requested images/thinking rewrite if the host cannot preserve valid provider/tool structure; never call the old direct rewrite as fallback |
| Drop/delete-session | Require the native explicit user action and point-of-risk scope. Explain whether this removes the host transcript only or also requests CassiPi forgetting; do not conflate them |

Native remote/snapcompact method requests are not supported while CassiPi owns context. The host returns an explicit ownership error with the supported `/compact` path. This is the removal of competing compactors, not a hidden fallback.

## 8. Required Oh My Pi ownership facility

This is planned upstream/host work, not a capability asserted for stock 18.1.10. Keep it optional and default-off so profiles without CassiPi retain current behavior.

### 8.1 Minimal host changes

1. **One explicit owner declaration.** Add a singleton extension context-owner registration/capability, scoped to the active session/profile and extension identity. Reuse the existing context/pre-compaction/pre-tree/switch event vocabulary. Reject a second owner or conflicting mutating handler rather than choosing by load order. Observers may remain observers.
2. **Owner-scoped fail-closed dispatch.** For owned requests/transitions, exceptions, timeout, missing required result, invalid result, or extension unload produce typed cancellation/unavailability. They never degrade to `undefined` and invoke a default compactor, summarizer, or uncurated provider request. Propagate cancellation signals into worker operations and prevent late results from committing.
3. **One rewrite admission point.** Route all active history-reducing paths through owner preparation: manual/automatic compaction, overflow/incomplete/idle/mid-turn maintenance, handoff, shake, pruning, and clear. In an owned profile the native competing methods are not invoked. Unsupported explicit modes return an error before mutation.
4. **Stable transition binding.** Persist owner operation ID and checkpoint/source references with native compaction, branch summary, reset, fork/switch, and no-summary navigation markers. Add the necessary durable marker to the native session storage transaction/batch, rather than claiming extension `appendEntry` is atomic. Specify recovery if a platform storage operation spans files.
5. **Final request guard.** After native message conversion/normalization and applicable safety transforms, ensure a compatible acknowledged owner projection is present, verify budget/structural invariants, and block if required ownership is unavailable. Do not expose an opaque payload-rewrite API as a substitute for correct message construction.
6. **Disable unsafe fallback loops.** Owned cancellation/unavailability is not a failed native strategy to try again with the next configured method. Surface one actionable error; resume only after recovery, a changed budget, or explicit deactivation.

Target existing host areas: extension types/runner, shared events, session maintenance and agent-session transition paths, session entries/storage, SDK/provider-context composition, and settings/profile validation. Do not hard-code Cassi-specific field mathematics into the host.

### 8.2 Proposed owner declaration and result binding

Use the following new host contract for implementation. These symbols and fields are proposed additions, not stock 18.1.10 APIs:

```typescript
pi.registerContextOwner({ id: "cassipi", apiVersion: 1 });
```

The registration is tied to the calling extension instance. The new optional profile setting `context.owner: cassipi` makes that owner required even if its extension is absent, disabled, unloaded, or fails to initialize. Without this persistent requirement, restarting with `--no-extensions` could accidentally revert to native behavior. Existing profiles without `context.owner` retain their normal behavior.

The host adds an `ownership` envelope to owned pre-events with its operation ID, reason, source native session/leaf, requested target when applicable, cancellation signal, and applicable context-budget accounting. Existing event payloads remain available.

The owner returns an `owner` binding alongside the existing result:

```text
operationId, expectedSessionId, expectedLeafId
inputHeadId, preparedHeadId, journalHeadSha256, revocationEpoch
projectionId (when the operation constructs context)
```

Thus `context` returns `{messages, owner}`, pre-compaction returns `{compaction, owner}`, and pre-tree returns `{summary, owner}` when a summary is requested or `{owner}` otherwise. Owned switch/reset preparation returns `{owner}` or explicit cancellation. Ordinary non-owner result shapes remain backward compatible.

The host validates the binding against the prepared operation and current native revision, then persists it with the actual commit. The canonical owner validates checkpoint/source hashes; the host must not trust arbitrary paths supplied by a result. A read-only projection normally has identical input/prepared retained heads. Post-events include the native committed identity for reconciliation.

An owner-required profile cannot return to native compaction merely because the module disappears. Deactivation is an explicit configuration/profile transition, with retained archive/head references and an explained recovery path. P01 includes absent-on-startup and unload tests, not just callback failures.

### 8.3 Delivery strategy for the host change

Prefer an upstream optional ownership API. Until available in a release, build a version-pinned host with a reviewable patch and record its source/base/binary hashes. Keep patch/build receipts with CassiPi's compatibility artifacts. Never overwrite the user's installed executable automatically.

The plugin checks an explicit ownership-capability version during handshake. A matching version string alone is insufficient. On an unsupported host it offers diagnostics and remains inactive; it does not present partial ownership as the complete plugin.

P01 implements and exercises this seam before later phases rely on it. If upstream review changes the proposed symbols or envelope, update this plan, the pinned host types, and every consumer together; remove temporary spellings rather than carrying compatibility aliases.

### 8.4 Porting the ownership patch to a newer host release

The patch is 15 files and 109,895 bytes against `f241301c8` (18.1.10). The same 15 files have moved under `v18.3.2`: `packages/coding-agent/src/config/settings-schema.ts` no longer exists — settings moved to `config/settings.ts`, and compaction settings to `session/context-settings.ts` with `config/compaction-threshold.ts` — so the settings surface the patch extends has to be re-derived, and `agent-session.ts` drifted +2,242/−796, `session-maintenance.ts` +1,414/−186, `sdk.ts` +1,069/−349, `session-manager.ts` +755/−119, `command-controller.ts` +359/−262, `extensions/types.ts` +161/−108, `extensions/runner.ts` +224/−28, `extensions/loader.ts` +50/−135, `shared-events.ts` +50/−3, `session-entries.ts` +24/−1, `shake-types.ts` +1/−1, and the three host-wired tests +392/−64, +249/−4, +28/−20. Per-file drift is reproduced by diffing `git -C .host-work/upstream show f241301c8:<path>` against `show v18.3.2:<path>` for each path named in the patch.

The port re-derives the patch against the target tag file by file while keeping the symbols the extension already consumes (`context.owner`, the owner declaration, the ownership result binding, and the compaction, handoff, and tree callbacks), then updates `.host-work/patched`, rebuilds the private release with `bun .host-work/patched/packages/coding-agent/scripts/build-binary.ts`, and repeats `verify:release-host`, the installer identity checks, `probe:owner` against the mock provider, `probe:installed`, and both measurement scripts before the pin moves. `verify:host-pin` remains historical: it checks the unpatched 18.1.10 binary, which the ordinary installation has moved past.

## 9. Corrections, forgetting, security, and failure behavior

### 9.1 Correction

`correct` records a new immutable revision and explicit supersession. Historical evidence remains addressable as historical. The canonical field transition inhibits/revises the old association and learns the replacement through the same state owner.

Conflicts between independent sources are retained as conflicts unless an authoritative correction or decisive observation resolves them. Do not simply select the newest sentence globally. Changing a design premise for one task does not rewrite all project evidence.

### 9.2 Actual forgetting

Ordinary decay or omission is not forgetting. Explicit forgetting has a preview, exact target/scope confirmation, and a revocation operation:

1. Enumerate matching source revisions, derived accounts, affected field heads, managed checkpoints, and local exports under plugin control.
2. Commit a revocation epoch/tombstone that prevents readout and re-import of the revoked source identities.
3. Rebuild affected field views from a clean compatible baseline and retained eligible events. Nonlinear learned influence is not assumed removable by deleting a row or subtracting one deposit.
4. Remove the targeted payloads and affected managed checkpoints only as authorized, while preserving non-content revocation/recovery metadata.
5. Verify recall, resume, branch switch, replay, and import cannot resurrect the revoked data.

The existing immutable journal has no safe forgetting operation merely by deleting referenced chunks. Add an authorized generation-rebuild path: construct and verify a replacement journal generation containing retained source/events plus non-content revocation metadata, bind rebuilt field heads to that generation, then atomically switch the active generation reference. Preserve original retained event/source identities as provenance even where new packet/chain hashes are required. Only one generation is authoritative; a staged replacement cannot serve requests.

Block affected views from projection as soon as revocation is admitted until their clean heads are ready. After the cutover, remove obsolete managed payload chunks/checkpoints only when no retained source still references them. Old generations and checkpoints are rejected by revocation epoch on restore. Do not leave broken manifests in the active chain and call their resulting corruption “forgetting.”

A forgotten source may already exist in native Oh My Pi transcripts, external files, backups, model-provider records, or exports outside the plugin's control. Report these limits. Do not claim secure physical erasure of storage media or silently delete host history. A restore/import must apply the current revocation set before making a field visible.

### 9.3 Security boundaries

- All retrieved text, archived tool output, documents, and source annotations are untrusted data. They cannot authorize execution, imports from another scope, wider disclosure, or forgetting.
- Only direct user action supplies point-of-risk confirmation. Tool arguments or an old authorization receipt are not a fresh permission grant.
- Keep provider safety approvals intact and interactive where required. CassiPi never fabricates or bypasses them.
- Authenticate local transport, reject unknown schemas/operations and oversized bodies, validate object paths and hashes, and never return raw secrets in logs or diagnostic receipts.
- Enforce user-only data permissions. Do not invent custom encryption; document reliance on OS account/disk protections and any configured storage policy.
- Pause/admission exclusions are explicit and explain what the host itself may still retain. Imports and exports show exact source/destination/scope before side effects.
- Imported checkpoints are versioned data, not executable pickle input from an untrusted party. Use the canonical validated safe loader and refuse incompatible/unsafe artifacts.

### 9.4 Failure table

| Failure | Behavior |
|---|---|
| Worker absent or incompatible | No owned context rewrite/provider use; show recovery or explicit deactivation |
| Owner fails during preparation | Cancel; keep old committed host/field state |
| Host commit succeeds, acknowledgement is lost | Reconcile from durable native operation marker; do not relearn |
| Event replay/retry | Return known receipt or resume recorded pending operation |
| Conflicting writer/head | Reject and reconcile; never last-writer-wins a learned field |
| Missing/corrupt source/checkpoint | Quarantine affected head; recover exact compatible ancestor or stop |
| Candidate ambiguity/weak field support | Abstain; retain mandatory recent context and expose recoverable evidence refs without inventing certainty |
| Context capacity exceeded | Explain protected minimum; use bounded owned recovery, not a competing summarizer |
| Missing action outcome | Preserve unresolved status; never replay an external tool automatically |
| Disk full or archive quota reached | Do not acknowledge durable admission or compact away unarchived evidence; expose retention/capacity choices |
| User cancellation | Stop preparation, invalidate pending token, and prevent late commits |
| Unsupported native command/method | Explicit ownership error before any rewrite |

## 10. Migration, packaging, and deployment

### 10.1 Import sources

Import only from an explicit selected snapshot or export. Preserve the original source stores.

| Source | Preserve | Do not import as adaptive authority |
|---|---|---|
| Mnemic exact records/journal | Original bytes, revisions, spans, node type, author/scope, corrections, action/outcome provenance | Zero/spatial compatibility fields or obsolete store behavior |
| Older Mnemic engrams | Content, identity, source metadata, typed relationships and available revision history | Embeddings, spatial coordinates, PageRank/potentiation, Lightning/reranker weights, recall counters |
| Thalamus artifacts | Source-referenced curation/drop receipts and original expansion bytes if recoverable | Independent luminance scores, thresholds, learned topic state, a second curation database |
| Mnemopi 18.1.10 | Working/episodic records, facts/annotations with source links, veracity, validity/supersession, scope and attribution | Embeddings, combined recall scores, importance/retrieval counts as reinforcement |
| Oh My Pi sessions | Native entry/parent IDs, original roles, messages, compactions/branch summaries with fidelity labels, action identities and accessible artifacts | Old summaries as newly verified observations or provider accounting as learned relevance |

Detect schema/version before reading. Unknown layouts fail with an actionable report; do not guess column meanings or mutate the source DB to run its migrations. For live SQLite sources take a consistent supported backup/export, not a lone DB-file copy that ignores WAL state.

Use `(source snapshot hash, source record identity, revision)` as import identity. A dry run reports counts, conflicts, missing provenance, unsupported rows, sensitive/wider scopes, and required disk space. The committed import uses normal canonical events and is resumable/idempotent. A second run must not teach twice.

Imported records enter through fresh CassiPi source/field-ingest receipts. Never call predecessor `ExactStore.update` or another mutating memory API to perform the import. Excluded embedding/ranking fields are discarded or retained only in an explicitly quarantined source snapshot; they are not restored as learned state.

Global Mnemopi data must retain its original global/imported scope until the user approves its destination. Do not disclose it automatically into every project. Summaries without underlying sources remain labeled imported derived evidence.

### 10.2 Standalone package

Proposed package name: `cassipi`, private/local until licensing and publication are explicitly resolved. Use one `omp.extensions` entry and one default extension factory. Do not register the same code as both a hook and extension.

- TypeScript/Bun integration; use the existing host API/types and installed tooling conventions. No new JS memory engine or UI framework.
- Python 3.12 plus the canonical runtime's supported NumPy/PyTorch environment. CPU is the documented local baseline; any GPU execution must use a supported canonical backend and have separate reproducibility/performance evidence.
- Extract/package a narrow FI-owned canonical worker entrypoint and its allowlisted source/config/checkpoint dependency closure. Do not blindly ship/import the monolithic `cassi_persistent_provider.py`: its optional particle/program and other surface imports are not automatically part of CassiPi. Migrate affected FI callers as needed, preserve or explicitly migrate module/checkpoint identities, and leave one canonical implementation.
- Keep the canonical runtime an FI-owned installed dependency, not a diverging vendored fork. The private CassiPi artifact contains its launcher/client and adapters; it locates an explicitly installed, hash-pinned local FI runtime artifact. Production code must not require a sibling `../CassiFI/prototype` checkout. Do not copy the paper, corpora, experiments, or unrelated world interfaces into the plugin.
- Record runtime/protocol/codebook/layout/checkpoint identities in the plugin compatibility manifest. No silent download, checkpoint substitution, baseline reset, or automatic dependency installation during extension load.
- Use the existing supported Python environment for local development; installation diagnostics explain exact missing dependencies. Explicit installation/bootstrap actions require authorization and keep provider checks intact.
- Revalidate after any checkpoint/layout/codec change. Upgrade via staged compatible load or explicit journal rebuild, never by silently accepting old state under new semantics.

The current FI bundle declares no publication license and treats external integrations separately [F6]. Local implementation uses an owner-controlled runtime artifact built/installed from the user's source; it does not infer redistribution rights. Before any third-party distribution, obtain an explicit owner decision on the runtime's license and the code/config/checkpoint assets permitted to ship, then verify dependency licenses. That decision blocks external distribution, not the requested private local implementation.

P02 verifies the actual startup import graph and runtime receipts: optional particle-program, Qwen/teacher, legacy agent, and world-execution paths must be absent, not merely inactive after being imported. The narrow worker calls canonical Python methods in-process through its new explicit adapter. It does not invent routes on the existing HTTP provider or pretend the existing `/v1/context/*` surface exposes every operation.

### 10.3 Proposed implementation files

All paths in this subsection are proposed files, not claims that code already exists:

```text
CassiPi/
  package.json                     private plugin package; one omp.extensions entry
  tsconfig.json                    host-aligned strict TypeScript configuration
  src/index.ts                     factory, lifecycle registration, one tool and command
  src/client.ts                    owner discovery, handshake, bounded authenticated requests
  src/context.ts                   native message/source mapping and host result construction
  runtime/worker.py                managed service; co-located canonical FI owner
  runtime/store.py                 QiIngressJournal context adapter and rebuildable indexes
  runtime/context.py               projection orchestration/rendering; no learned policy
  runtime/import_memory.py         read-only predecessor adapters into canonical events
  compatibility/                   exact host/runtime identities and reviewed ownership patch
  tests/                           behavior-focused TS/Python regression cases
  scripts/                         packaging and actual-host smoke entry points
  IMPLEMENTATION-PLAN.md            this implementation plan
```

Keep files together until real ownership or size requires a split. Do not create a package for each predecessor, a generic storage-provider framework, or a plugin-specific field implementation. Canonical FI changes stay in FI's owned runtime; host changes stay in the exact host source/patch. Update their affected callers/tests together during implementation.

The final implementation adds concise installation, configuration, privacy/recovery, and tool documentation after the real smoke proves the product. It does not create governance/preregistration/frozen-verdict documents inside CassiFI.

### 10.4 Isolated rehearsal, cutover, and rollback

1. Build and fingerprint the compatible host and plugin/runtime artifacts without replacing the installed binary.
2. Create a separate Oh My Pi profile/data home using the documented profile mechanism; do not overwrite the live profile.
3. Install the plugin there, explicitly provision the supported FI runtime, and validate owner capabilities.
4. Bind the generated launcher to a unique `CASSIPI_PROFILE_ID`, profile-local `CASSIPI_DATA_HOME`, and installed `CASSIPI_FI_RUNTIME`.
5. Disable stock memory/autolearn/speculative compaction paths and retain only the owner-routed `soft` entry point.
6. Keep `remote-pi@0.7.0` absent: its `context` and `session_before_compact` handlers are competing mutators, and the pinned host correctly rejects the combination.
7. Import an approved snapshot, then run all end-to-end scenarios in disposable workspaces.
8. Present the exact proposed live config changes, selected memory scope, executable/plugin identities, and rollback locations.
9. Confirm before creating the live profile, authenticating a provider, or making a live provider call.
10. With authorization, create the isolated profile and import the final delta once. Do not run both memory pipelines as a comparison mode.
11. Confirm status reports exactly one owner and the expected data head; perform a live continuation/compact/resume check.
12. Keep the predecessor profile, executable, data, and remote-pi installation unchanged as the rollback path.
13. Roll back by exiting the CassiPi profile and relaunching the original profile. Data written after cutover remains exportable with provenance; do not pretend an old backend understands the new field checkpoint.

No commit, push, public release, executable replacement, source-store deletion, or live-profile change is authorized merely by writing this plan.

## 11. Ordered implementation work

All checkboxes below are implementation tasks, currently uncompleted. Each phase includes observable completion conditions. Phase order follows dependencies; the complete release requires P01–P12, not just the first runnable subset.

| Phase | Depends on | Ownership |
|---|---|---|
| P01 Host ownership and exact compatibility | None | Host integration |
| P02 Canonical runtime package and managed owner | None | FI/runtime integration |
| P03 Exact evidence and recoverable field commits | P02 | Runtime/storage |
| P04 Field-driven retention and projection | P03 | Canonical FI + runtime |
| P05 Oh My Pi observation/context adapter | P01, P03 | Plugin integration |
| P06 Owned compaction and rewrite coverage | P04, P05 | Plugin + host integration |
| P07 Branch/session continuity | P03, P05, P06 | Plugin + canonical lineage |
| P08 Memory tool, corrections, forgetting, and UI | P03, P04 | Runtime + plugin |
| P09 Predecessor migration | P03, P08 | Migration |
| P10 Packaging and isolated installation | P01, P02, P08 | Packaging |
| P11 Failure, isolation, capacity, and integration exercise | P06–P10 | Integration owner |
| P12 Actual-agent comparison and live cutover | P11 | Integration owner + user authorization |

### P01 — Host ownership and exact compatibility

- [ ] First run a disposable probe extension against the untouched installed 18.1.10 binary in an isolated profile: verify exact manual/automatic pre-compaction result shapes, requested/unrequested tree summaries, canceled navigation, and failure behavior. Record native bypass/fail-open results before applying host changes; never use the live profile for this probe.
- [ ] Pin exact host source/package/binary identities; reject the stale spine shim and unrelated global package as type authorities.
- [ ] Add the optional singleton owner declaration, owner-scoped fail-closed dispatch, and compatible capability version.
- [ ] Route every rewrite/session-transition entry point in sections 6–8 through preparation; disable native strategy fallthrough while owned.
- [ ] Persist operation/head bindings with native entries/markers and add the final request guard.
- [ ] Prove ordinary non-owner profiles retain their existing behavior.

Completion: the actual compatible host loads a throwaway owner fixture and demonstrates custom compaction/tree results, explicit cancellation, timeout/unload/error cancellation, conflicting-owner rejection, no native fallback, and recoverable operation markers. This fixture tests host mechanics, not FI intelligence. Record the real binary used.

### P02 — Canonical runtime package and managed owner

- [ ] Extract and package the narrow FI-owned canonical worker entrypoint/dependency closure; resolve its private installation inputs without assuming publication rights.
- [ ] Implement a co-located worker calling direct canonical Python APIs with a version/fingerprint handshake.
- [ ] Implement single-owner process locking, authenticated loopback transport, client lifecycle, bounded payloads, and clean shutdown/recovery.
- [ ] Add diagnostics for incompatible codebooks/layout/checkpoints, absent dependencies, wrong data permissions, and owner contention.

Completion: launch from a directory outside both repositories; two clients attach to one owner; a second writer cannot initialize; exact checkpoint save/reload and incompatible-artifact rejection work. Startup import inspection and exercised receipts show no optional particle-program, Qwen/teacher, world-execution, Godot, CassiCore, legacy agent, or secondary field controller in the supported live path.

### P03 — Exact evidence and recoverable field commits

- [ ] Extend `QiIngressJournal` with context source revisions, event IDs, native/provisional bindings, lineage commits, and operation receipts; retain one event authority and rebuildable indexes.
- [ ] Extend canonical observation with complete replay/idempotency receipts and checkpoint event bindings.
- [ ] Complete P03-Sizing, then implement the admission/apply/receipt commit protocol, object checks, and recovery table in section 4.
- [ ] Preserve observed action stages without executing or automatically replaying external tools.
- [ ] Keep source and stream growth out of bounded adaptive checkpoint metadata; reference the authoritative archive by heads/digests instead.

Completion: terminate at each durability boundary and recover to the same committed state/source coverage; duplicate and older retried events do not relearn; missing/corrupt bytes and conflicting IDs fail explicitly.

### P04 — Field-driven retention and projection

- [ ] Add canonical multi-source/span projection and source-bound observation/correction operations.
- [ ] Implement eligible source enumeration, hard protections, field readout, deterministic representation packing, and source-backed rendering.
- [ ] Integrate task/action/outcome consolidation through the same canonical state.
- [ ] Implement weak-support abstention, exact evidence retrieval, source revision checks, and full-request token accounting.
- [ ] Remove any proposed external semantic shortlist/reranker or persisted learned score from this path.

Completion: source-backed context changes meaningfully after a relevant field transition; read/inspect/project preserve retained memory when no consolidation is requested; every selected span resolves exactly; a field-only intervention changes a committed selection while archive and encoder remain fixed.

### P05 — Oh My Pi observation and context adapter

- [ ] Implement one plugin factory, owner registration, stable profile/project/session mapping, and canonical client connection.
- [ ] Map message/tool/native entry events into exactly-once observations, including late bindings and interrupted actions.
- [ ] Replace transient request context using canonical projection, preserving original session records and provider/tool structure.
- [ ] Guard use of stale, unacknowledged, revoked, or wrong-scope projections.

Completion: actual host message/tool exchanges produce one source/event sequence; replay and provider retries do not duplicate learning; the provider sees the intended valid context with exact current working material.

### P06 — Owned compaction and rewrite coverage

- [ ] Implement complete custom `CompactionResult` preparation and durable post-commit reconciliation.
- [ ] Exercise manual, threshold, overflow, incomplete, idle, and mid-turn compaction through the owner.
- [ ] Implement owned handoff/reduction behavior and explicit rejection of incompatible native method requests.
- [ ] Prevent native shake/pruning/remote/snapcompact/background fallthrough and competing extension replacement.
- [ ] Handle cancellation, stale preparations, insufficient protected budget, and lost acknowledgement.

Completion: repeated actual-host compactions preserve the continuation task and exact recovery sources; no default summarizer or native rewrite runs behind the owner. Kill the worker during preparation and after native commit to exercise both distinct recovery outcomes.

### P07 — Branch and session continuity

- [ ] Implement canonical lineage heads, native source ancestry, task boundaries, and explicit shared-memory promotion.
- [ ] Implement pre/post tree behavior with and without a summary, cancellation, no-op, user-message edit, and ask reanswer.
- [ ] Implement fork/new/switch/resume/clear/handoff identity transitions and durable head markers.
- [ ] Reconcile post-commit failures and verify conversational rollback does not misrepresent external file/tool effects.

Completion: create sibling branches with conflicting private task facts, navigate and resume each, and observe no implicit cross-branch contamination. Inherited history is not relearned; requested branch summaries carry exact provenance; no-summary navigation remains resumable.

### P08 — Memory tool, correction, forgetting, and UI

- [ ] Implement the closed `cassi_memory` operations and one `/cassi` command with bounded/paged output.
- [ ] Implement explicit supersession and scoped contradiction handling.
- [ ] Implement preview/confirmation, revocation epochs, affected-head rebuild, managed-copy removal, and resurrection prevention.
- [ ] Implement status/inspection and clear paused/unavailable/recovery messaging using existing host UI patterns.
- [ ] Preserve user authority and provider safety approval boundaries.

Completion: correct the design premise used in the discussion, compact/restart, and retain the current premise without rewriting old evidence. Forget a selected item, then exercise recall, branch, resume, import retry, and an old-checkpoint restore attempt without resurrecting it. Inspect the real command UI.

### P09 — Predecessor migration

- [ ] Implement schema-detected read-only adapters for selected Mnemic, Thalamus, Mnemopi, and native session snapshots.
- [ ] Preserve source trust, validity, supersession, original identities, missing-provenance labels, and exact recoverable bytes.
- [ ] Implement dry-run scope review, import identities, resumability, conflict reports, and final-delta import.
- [ ] Exclude obsolete learned ranking/embedding state and verify the originals remain unchanged.

Completion: migrate representative corrected, invalidated, episodic, action, and source-gap records; repeat and interrupt the import; observe identical final admitted identities and no duplicate field teaching. Global data is not exposed to an unapproved project.

### P10 — Packaging and isolated installation

- [ ] Produce the private plugin/runtime artifacts and compatible host build/patch with exact identities.
- [ ] Install one `omp.extensions` entry in a separate profile; avoid duplicate registration through hooks or explicit paths.
- [ ] Validate outside-checkout startup, dependency diagnostics, upgrade/restore compatibility, and supported-platform declarations.
- [ ] Exclude paper/corpora/secrets/local data from distribution and retain licensing/publication boundaries.
- [ ] Write concise installation, operations, privacy, and recovery documentation after the actual installation smoke succeeds.

Completion: a clean supported environment can install, start, retain, compact, stop, and resume using only the distributed artifacts and declared dependencies. Unsupported hosts/dependencies fail visibly without changing data or falling back.

### P11 — Integration, fault, isolation, and capacity exercise

- [ ] Run the behavior matrix in section 12 across the fully integrated product.
- [ ] Keep only regression tests that defend real contracts; use temporary scripts for one-off instrumentation and remove them after use.
- [ ] Measure warm/cold latency, p50/p95 projection and compaction duration, peak RAM, archive/checkpoint growth, token use, and concurrency behavior.
- [ ] Exercise at least three simultaneous local sessions, including sibling branches and an unrelated project, without multiple field writers or data leakage.
- [ ] Publish the supported state/candidate/source-size envelope from measurements. Exercise just below/at/above actual limits with explicit errors or complete archival admission; never silently crop or evict to conceal capacity.

Completion: no unacknowledged mutation, invalid provider history, source resurrection, hidden fallback, or scope leakage appears in the exercised cases. Measured performance and remaining platform limits are recorded without claiming unmeasured speed or intelligence gains.

### P12 — Actual-agent comparison and live cutover

- [x] Run the end-to-end task in section 12 with stock compaction and CassiPi at matched model/context budgets.
- [x] Run the field-only intervention, unchanged-archive control, restart replay, and held-out retrieval/continuation cases.
- [x] Exercise at least the user's actual provider route and another available provider family with different tool/replay requirements; obtain required interactive provider approval rather than bypassing checks.
- [x] Harden and exercise a profile-isolated launcher with explicit owner settings, field data/runtime bindings, and a fail-closed `remote-pi@0.7.0` conflict check.

- [x] Review the exact profile/executable/data-scope changes and activate the isolated profile with a fresh field; no data import was selected.
- [ ] Close the live safety gate before production cutover. One owner, field-owned compaction, stop/resume continuity, and the `omp` rollback command were exercised, but two prompt turns generated four provider requests through extension-tool loops.

Measured comparison: `probes/receipts/provider-comparison.json` records `PASS` for eight isolated arms across `openai-codex/gpt-5.6-sol`, `opencode-go/qwen3.8-flash`, `harbor-relay`, and `quartz-batcher`. All four CassiPi arms passed the named behavior, navigation, compaction, source, and verifier checks. Every paired token and cost ratio remained below 1.5; medians were 0.962 and 0.737 respectively. `probes/receipts/field-control.json` and `probes/receipts/integration-envelope.json` retain the field-only intervention, unchanged replay, restart, and bounded-envelope evidence.

The `cassipi-live` trial used a fresh synthetic field and one profile-local OAuth credential. A verification-only `compaction.keepRecentTokens: 1` overlay created a legal boundary for the one-turn fixture. CassiPi's summary retained both latch values, the worker stopped, the same session resumed, and the second answer was exact. The synthetic session, workspace, and field were then removed; the credential remains and no user memory was imported.

The live gate is `FAIL_PROVIDER_REQUEST_BUDGET`, not a cutover pass. `--no-tools` removed built-in tools but left the CassiPi extension tool available; the resumed prompt produced two tool-use responses with four `cassi_memory` calls before its final answer, for four provider requests across two prompt turns. `probes/receipts/case-matrix.json` records 27,789 tokens, $0.1039848, all artifact hashes, clean worker shutdown, and the rollback observation measured during that trial. The receipt retains the then-current 18.1.13 ordinary-host observation as historical evidence. The current ordinary `omp` host is 18.1.16 with `remote-pi@0.7.0`; `cassipi` remains isolated on the pinned 18.1.10 owner host. No further live request is authorized by this result.

Completion: the named end-to-end behaviors work on the installed compatible host, all requirements in this plan are implemented or explicitly resolved with the user, and the final report distinguishes measured outcomes from design expectations. No public release or destructive predecessor cleanup is implied.

## 12. Acceptance and verification

### 12.1 Behavioral matrix

| Case | Required observation |
|---|---|
| Changed premise | The current instruction survives compaction/resume; historical receipts retain their original meaning |
| Failed approach | The resumed agent can recover why the attempt failed and does not repeat it solely because context was compacted |
| Exact working read | The next edit uses intact current source bytes/anchors; stale revisions trigger a fresh read |
| Proposal versus result | An interrupted/unexecuted action is never reported as completed |
| Repeated compaction | Evidence remains source-bound; summaries do not recursively acquire factual authority |
| Older acknowledged retry | No new deposit/consolidation occurs |
| Owner timeout/unload | Host cancels; no native/default compactor or unowned provider request runs |
| Competing handler | Owner registration/result cannot be overwritten by load order |
| Commit acknowledgement lost | Recovery binds the existing host entry to the prepared head without relearning |
| Tree with summary | One field-generated projection, exact source/branch refs, correct resulting leaf |
| Tree without summary | No summary model call or implicit summary entry; correct resumable head |
| Tree cancel/no-op/reanswer | Correct native semantics and no premature field activation |
| Fork | Inherited source identities/head reference, no duplicate deposit, independent subsequent task views |
| Clear | Old task context does not resurrect; exact archive is retained unless separately forgotten |
| Cross-project/session | No private learning or source leakage through either field state or returned records |
| Correction | Explicit new revision; old source remains historical, not silently rewritten |
| Forget | Revoked influence and source cannot return through any managed restore/replay/import path |
| Malicious recalled text | It cannot become higher-priority instructions, permission, or a tool action |
| Archive/checkpoint corruption | Explicit recovery failure/quarantine; no silent empty-state reset |
| Import restart/repeat | Same identities and teaching count; source snapshot unchanged |
| Boundary capacity | Valid fit or explicit failure, no hidden crop, eviction, or endless retry |
| Worker contention | One writable owner; clients cannot overwrite each other's head |
| Unsupported host | Plugin remains inactive and diagnostic; no partial-ownership claim |

### 12.2 Real end-to-end task

Use a disposable coding workspace with a task whose answer depends on an early decision, a later correction, a failed attempted fix, and an exact source revision. Include an unresolved action and a sibling branch with a conflicting task assumption. Insert irrelevant but real tool output sufficient to force several compactions.

Run the actual host and model, perform the work, compact at least three times, close/reopen, navigate with and without a branch summary, then continue. Evaluate observable actions and source recovery, not just whether a fluent summary was emitted. The latest correction, rejected approach, outstanding work, and exact evidence must remain recoverable.

Compare stock compaction and CassiPi at matched model/budget/task conditions using separate profiles and data homes. Repeat on held-out task variants; avoid teaching the evaluation answer into the field. Report task success, correction adherence, repeated-failure rate, exact-source retrieval, abstention/false-confident selection, tokens, latency, and state growth. Do not claim universal superiority from one demonstration.

For the causal check, keep archive, input, encoder, candidate eligibility, and rendering unchanged while replacing the relevant trained field state with a compatible baseline or controlled intervention. A meaningful selected source/context/action must change. This proves field involvement in that exercised decision, not general intelligence by itself.

### 12.3 Verification discipline

During implementation, add deterministic regression cases for uncertain boundaries: idempotency, crash windows, authority, branch isolation, invalidation, provider structure, and owner fail-closed behavior. Test consumer-visible effects, not source strings, field forwarding, incidental defaults, or mock echoes.

Run real CLI/TUI interaction and actual provider paths for integration proof. Unit tests or a fake owner alone do not prove the plugin works in the installed host. During parallel development, workers skip builds/tests/formatters; the integration owner validates after the relevant edit wave has joined.

No code tests or GPU/model experiments were run merely to write this plan. Documentation QA checks this document's structure, source links, and coverage; implementation verification remains P01–P12 work.

## 13. Work distribution and change control

P01 and P02 are independent and can run concurrently. After their interfaces are fixed, storage/runtime and TypeScript observation work can proceed on disjoint files. Projection, memory operations, and migration can run concurrently only after their shared event/source schema and canonical operation boundary are agreed in code. One integration owner owns the host/plugin boundary, this plan, and final acceptance.

Do not let separate workers invent competing RPC schemas, source IDs, checkpoint formats, field layouts, or token accounting. Shared-file edits are serialized at that boundary. Each work packet names exact targets, inputs/outputs, non-goals, and observable acceptance, and skips validation until integration.

The live FI source may advance while CassiPi is built. Re-read changed sections and bind the runtime artifact actually used; do not rewrite historical FI receipts or reseal the paper bundle as incidental plugin work. CassiAI, unrelated CassiCore packages, CassiTheory, and CassiCosmos are outside this implementation unless a separately authorized change is necessary.

## 14. Source index and snapshot notes

The links below are inspected sources. File names in the proposed implementation tree are future targets, not missing source references.

### Current CassiFI and historical predecessor sources

- [Current sole field/evidence owner](../CassiFI/cassi_field_owner.py)
- [Current typed atlas and checkpoint model](../CassiFI/cassi_field_atlas.py)
- [Current cognition layer](../CassiFI/cassi_field_cognition.py)
- [Current variational field](../CassiFI/cassi_variational_field.py)
- [Packaged runtime closure](../CassiFI/runtime/cassipi_closure.json)
- Historical prototype sources under `../CassiFI/prototype/` informed the original plan but are not packaged or imported by CassiPi.
- [F1: historical canonical provider and checkpoint store](../CassiFI/prototype/cassi_persistent_provider.py)
- [F2: historical canonical field agency](../CassiFI/prototype/cassi_canonical_runtime.py)
- [F3: historical Mnemic condensation](../CassiFI/prototype/cassi_mnemic_condensation.py)
- [F4: historical ingress and universal codecs](../CassiFI/prototype/cassi_universal_data.py)
- [F5: historical prototype implementation plan](../CassiFI/prototype/IMPLEMENTATION-AND-PUBLICATION-PLAN.md)
- [F6: supported local runtime and publication limitations](../CassiFI/prototype/README.md)
- [M1: exact predecessor records and source/action journal](../CassiCore/packages/mnemic-field/src/exact-store.ts)
- [M2: older engram/spatial/reinforcement storage schema](../CassiCore/packages/mnemic-field/src/schema.ts)
- [M3: exact live-read protection](../CassiCore/packages/thalamus/src/distiller.ts)
- [M4: old spine dependency/version boundary](../CassiCore/packages/spine/package.json)

### Exact Oh My Pi 18.1.10 sources

- [O1: published package metadata](https://registry.npmjs.org/@oh-my-pi%2Fpi-coding-agent/18.1.10)
- [O2: shared events and pre/post result types](https://github.com/can1357/oh-my-pi/blob/v18.1.10/packages/coding-agent/src/extensibility/shared-events.ts)
- [O3: extension runner, timeout/error and result precedence](https://github.com/can1357/oh-my-pi/blob/v18.1.10/packages/coding-agent/src/extensibility/extensions/runner.ts)
- [O4: compaction, pruning, shake, handoff, and clear](https://github.com/can1357/oh-my-pi/blob/v18.1.10/packages/coding-agent/src/session/session-maintenance.ts)
- [O5: session switch, fork, and tree navigation](https://github.com/can1357/oh-my-pi/blob/v18.1.10/packages/coding-agent/src/session/agent-session.ts)
- [O6: native session entry and extension metadata shapes](https://github.com/can1357/oh-my-pi/blob/v18.1.10/packages/coding-agent/src/session/session-entries.ts)
- [O7: session ancestry and persistence operations](https://github.com/can1357/oh-my-pi/blob/v18.1.10/packages/coding-agent/src/session/session-manager.ts)
- [O8: plugin loading and profile conventions](https://github.com/can1357/oh-my-pi/blob/v18.1.10/docs/extension-loading.md)
- [O9: Mnemopi import record types](https://github.com/can1357/oh-my-pi/blob/v18.1.10/packages/mnemopi/src/types.ts)
- [O10: Mnemopi SQLite opening and transaction behavior](https://github.com/can1357/oh-my-pi/blob/v18.1.10/packages/mnemopi/src/db.ts)

Local source hashes observed during planning:

| Source | SHA-256 |
|---|---|
| `CassiFI/prototype/cassi_canonical_runtime.py` | `ddc6478caa58e609a7cb12c8dd2637215ede13373dc97229e5edcd1a6c36f0a2` |
| `CassiFI/prototype/cassi_persistent_provider.py` | `07edeb84894f1acbcb2cd0ce2b7f48ffcea1edce28080225fdf14f35cf82b411` |
| `CassiFI/prototype/cassi_mnemic_condensation.py` | `b2d684771e12b41685f3994ae4c0dfe8434203d7fe84a26529d77fa4413925e4` |
| `CassiCore/packages/mnemic-field/src/exact-store.ts` | `f963425ac23ab7a4486eca6487acd25c8ceeee2f2a7167dbd6eaef26cfee1962` |

These identify the inspected snapshots. They are not a frozen research verdict and do not prevent adopting a newer canonical runtime with an explicit compatible artifact and updated implementation evidence.

[F1]: ../CassiFI/prototype/cassi_persistent_provider.py
[F2]: ../CassiFI/prototype/cassi_canonical_runtime.py
[F3]: ../CassiFI/prototype/cassi_mnemic_condensation.py
[F4]: ../CassiFI/prototype/cassi_universal_data.py
[F6]: ../CassiFI/prototype/README.md
[O1]: https://registry.npmjs.org/@oh-my-pi%2Fpi-coding-agent/18.1.10
