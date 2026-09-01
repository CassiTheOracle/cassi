# Universal Data Field Intelligence

**Status:** Implemented universal substrate, shared field persistence, and bounded measured capability accounting — 2026-09-01

This document is the capability-level north star for a bounded end state. Any
acquired finite payload can enter through one exact typed substrate; one
`QiFieldState.field` is the sole adaptive persistent state; and semantic
understanding is reported only for a measured modality, task family, and
transfer direction. An opaque, compressed, encrypted, malformed, or
undocumented payload may be retained exactly while its semantic result remains
`unsupported`. A **universal substrate** is never abbreviated to **universal understanding**.

The status labels below keep implementation truth and semantic limits separate:

- **Current implementation** means code on the live CassiFI or CassiCore path.
- **Measured capability** means an exercised scenario with exact named inputs,
  task family, nuisance set, direction, and restart evidence.
- **Capability boundary** means a deliberate `ambiguous` or `unsupported`
  result; exact retention never upgrades that result to semantic support.
- **Legacy reference** means useful code under `legacy/`, not a current
  contract.

Parts 0–13 remain the surrounding architecture. This document records the
implemented common packet, journal, typed view, adapter, exact-reference, and
shared-checkpoint seams without adding a service, learned modality head, model
fallback, or dependency.

## Operational end state

### Read

In the **current universal boundary**, to read an acquired payload means
preserving or resolving all of the following:

1. exact bytes or samples;
2. source identity and authority;
3. rational capture time and logical time;
4. source order and sequence;
5. dtype and shape;
6. codec identity;
7. validation result;
8. exact source spans or paths for every exposed view node;
9. deterministic replay; and
10. exact round-trip under a declared lossless codec.

Read is a claim about the acquired payload, not inaccessible world state. A
lossy physical-acquisition adapter must preserve the acquired samples exactly
and declare the acquisition loss. It must not imply that unmeasured light,
sound, motion, or other world state can be recovered.

### Understand

In the **current capability accounting**, understanding is a measured
capability vector,
not a scalar label. Every claim reports the tested values or coverage for these
exact dimensions:

- reconstruction;
- successor prediction;
- relation preservation under nuisance transforms;
- composition;
- intervention or counterfactual consequence;
- cross-view transfer;
- contradiction-driven revision;
- novelty or abstention; and
- exact evidence grounding.

The universal boundary has exactly three result semantics:

- `selected`: one outcome is separated by the admitted evidence and declared
  decision rule;
- `ambiguous`: multiple alternatives remain observationally or causally
  equivalent; and
- `unsupported`: the adapter, task family, evidence, work budget, or learned
  field capability does not support a semantic answer.

Current internal receipts may retain exact states such as `exhausted`,
`no_eligible_transition_data`, and `no_transition_data`. At the universal
boundary, each maps to `unsupported` with that exact internal reason
and evidence references. These receipts do not create a second success
vocabulary.

### Causal sufficiency

Let `P` be the field projection used for a declared task family, and
let `O(x, a)` be the observed consequence of supported intervention `a`. The
projection is causally sufficient only if

```text
P(x_1) = P(x_2) => O(x_1, a) = O(x_2, a)
```

for every supported intervention `a` in that task family. If the implication
fails, a confident shared answer is a failure. The field must instead retain
more of the discarded fibre, preserve the alternatives, request an informative
observation, or return `ambiguous` or `unsupported`.

## Universal substrate

### Common boundary event

The current [`BoundaryPacket`](../cassi_universal_data.py) implements the
Part 5 packet identity from
[Common packet identity](05-boundaries-body-and-action.md#common-packet-identity)
without adding an adaptive field. It preserves `schema`, `run_id`,
`episode_id`, `world_id`, `session_id`, `profile_sha256`, `clock_sha256`,
`descriptor_sha256`, `event_id`, `request_id`, `logical_tick`, rational
`logical_time`, `capture_start`, and `capture_end`, `source_epoch`,
`source_stream_id`, `source_sequence`, telemetry order, watermark and journal
identity, optional antialias and causal references, `body_frame_id`,
`payload_shape`, `payload_dtype`, `payload_sha256`, and `valid`.

Codec identity is deterministic descriptor metadata bound into the event
digest. Source authority remains fixed admission metadata rather than a learned
packet field.

The current [`QiIngressJournal`](../cassi_universal_data.py) journals packets
before adaptive field mutation. It stores payloads in content-addressed chunks,
stores exact packet objects and a hash-linked atomic `HEAD`, enforces strict
per-stream sequence order and bounded admitted bytes, supports exact replay,
and treats a retry of the current packet as idempotent. Capacity rejection
occurs before new content-addressed objects are written. The older
[`QiBoundaryPacket`](../legacy/flow/cassi_qi_boundary.py) remains a legacy
reference.

Exact bulk payload and replay ownership stays with `QiIngressJournal`.
[`MnemicExactStore`](../../CassiCore/packages/mnemic-field/src/exact-store.ts)
now stores durable observation revisions containing the exact packet,
payload-manifest, journal-head, codec, view, source path/span, and record
references; it does not copy bulk payload bytes. Thalamus
[`ContextCandidate`](../../CassiCore/packages/thalamus/src/attention/types.ts)
accepts that exact observation reference only under fixed kind, authority,
eligibility, required, and work-budget policy.

### Typed observation view

The current typed observation view is a fixed algebra, not a modality-specific
wire schema. It has exactly five constructors:

- `Atom`: an exact scalar or byte span with a primitive type;
- `Collection`: an ordered sequence or keyed map;
- `Tensor`: a dense block with dtype, shape, strides or chunk identity, and
  supplied units;
- `Relation`: a typed directed structural edge such as containment, order,
  reference, or derivation; and
- `Event`: an exact before reference, observed operation, after reference, and
  time.

Every view node carries or resolves to the source packet digest, codec identity,
and exact span or path. Dense tensors remain block-backed. A raster, waveform,
or scientific array is not expanded into one heap graph object per pixel or
sample.

### Adapter conformance

Adapter conformance is independent of semantic capability. A conformant
adapter must provide:

- deterministic packet bytes and hash;
- exact round-trip of the acquired payload under its declared lossless codec;
- exact source spans or paths;
- preserved ordering and timing;
- explicit malformed-input and no-sample behavior;
- no adaptive state;
- no semantic-role labels; and
- one common ingress interface.

An adapter may expose syntax it can prove, such as a JSON tree, raster topology,
table cells, or code syntax. It may not emit task answers such as `self`,
`target`, `cause`, `intent`, or `important`. Syntax exposure does not establish
understanding.

## Responsibility split

The current implementation gives each state or evidence kind one owner:

| Component | Sole responsibility | Explicit boundary |
|---|---|---|
| `QiIngressJournal` | Exact raw packet bytes or chunks, replay range, packet ordering, and bounded retention | Evidence outside adaptive state; never read as learned memory |
| `MnemicExactStore` | Inert durable observations, revisions, associations, outcomes, and exact references to boundary evidence | No copied bulk-payload store and no adaptive semantic state |
| Thalamus/context admission | Fixed source authority, `required`/kind eligibility, and work budget | May filter candidates; may not learn semantics or override field ordering within the admissible set |
| Deterministic adapters/interpreter | Proven syntax and execution of a field-selected typed program | No adaptive memory, role answers, learned codec, or hidden policy |
| `QiFieldState.field` | The only adaptive persistent object: structural/operator evidence, abstraction programs, cross-view correspondences, uncertainty, and retention | No parallel learned table, head, controller state, or model fallback |

Exact identity and transferable structure are separate. Hash-derived addresses
such as [`_address_for(...)`](../cassi_counterflow_runtime.py) remain provenance
and retrieval anchors. Geometry must come from typed relations, relative
values, events, and field-generated programs. Hash adjacency is never semantic
similarity.

[`SharedFieldLayout`](../cassi_persistent_provider.py) packs Phi continuation
and counterflow into non-overlapping contiguous views of one native
`QiFieldState.field`. [`SharedFieldSessionStore`](../cassi_persistent_provider.py)
writes one framed field payload with one shared state hash and rejects the
removed composite schema. Controller projections are ephemeral views into that
field; there is no second adaptive checkpoint.

## Field cognition

### Shared geometry

The shared persistence geometry is flat and contiguous; its fixed slices name
mechanisms, not modalities. JSON and raster structural evidence currently enter
the generative-abstraction field through the same five-constructor observation
interface. Text, code, audio, scientific tensor, and opaque adapters stop at
exact typed views until a named semantic task is separately measured.

The runtime preserves an exact, bounded active working set selected through
Mnemic retrieval and Thalamus eligibility. It does not allocate one persistent
field site for every historical byte. Journal evidence and inert Mnemic records
remain addressable while only admitted evidence occupies the active field.

### Masked structural completion

The current bounded cognition mechanism generalizes the measured generative
abstraction surface rather than adding a modality model. Unresolved typed slots
and program tokens receive upward observation evidence and downward
consequence/type constraints. A fixed interpreter executes surviving
field-selected programs. Consequence residuals return to the same field, and
alternatives remain explicit until an observation separates them.

Generation is whole-structure completion. Text is one serializer applied after
a typed structure or event trajectory settles; autoregressive text emission is
not the architectural primitive. The design adds no Gaussian diffusion,
autoregressive fallback, embedding, learned codec, modality head, optimizer,
or second controller state.

### Experience and inference lifecycle

The implemented boundary lifecycle has this fixed order:

1. journal the exact packet;
2. derive the deterministic typed view;
3. apply Thalamus eligibility and work budget;
4. deposit exact identity plus structural evidence;
5. mask or query and refine explicit alternatives;
6. return `selected`, `ambiguous`, or `unsupported` with exact evidence
   references;
7. render or apply an admitted proposal;
8. journal the actual external outcome;
9. return typed residual or transition evidence to the same field; and
10. consolidate only under the declared outcome-learning law.

Inference must leave checkpoint bytes unchanged. Generated output is never
training truth unless a separately observed external consequence establishes
the relevant transition.

## Measured implementation

The current implementation is distributed across:

- [`cassi_universal_data.py`](../cassi_universal_data.py): strict packet
  identity, `QiIngressJournal`, the five constructors, deterministic adapters,
  exact source provenance, and the three boundary result semantics;
- [`cassi_generative_abstraction.py`](../cassi_generative_abstraction.py):
  observation-view contexts, anonymous role inference by stable entity
  identity, sparse field evidence, and output-lattice decoding;
- [`run_generative_abstraction.py`](../run_generative_abstraction.py): the
  paired JSON/raster, directional transfer, adapter conformance, ablation, and
  restart scenarios;
- [`cassi_persistent_provider.py`](../cassi_persistent_provider.py): one shared
  native field and one checkpoint payload for continuation and counterflow;
- [`exact-store.ts`](../../CassiCore/packages/mnemic-field/src/exact-store.ts)
  and [`session.ts`](../../CassiCore/packages/thalamus/src/attention/session.ts):
  exact durable observation references and fixed admission; and
- [`test_cassi_generative_abstraction.py`](../tests/test_cassi_generative_abstraction.py)
  plus [`test_cassi_persistent_provider.py`](../tests/test_cassi_persistent_provider.py):
  observable contract coverage.

The 2026-09-01 heterogeneous scenario returned
`result == "UNIVERSAL_DATA_FIELD_OK"` with:

- 32 paired experience events, 64 exact JSON/raster views, and zero maximum
  experience residual;
- 32 exact held-out consequences, split 16 JSON and 16 raster, with zero
  maximum residual;
- source-only JSON experience transferring to 16/16 held-out raster queries,
  and source-only raster experience transferring to 16/16 held-out JSON
  queries, both at zero residual and with the same selected program hashes as
  the paired field;
- cross-view program/operator residual at most `1e-12` under randomized entity
  IDs, JSON key aliases and record order, raster plane assignment, and global
  grid translation;
- both unidentified acted-on cases returning `ambiguous`;
- shuffled pairing, missing pair identity, and hashes-without-structure controls
  preventing support;
- field evidence and operator ablations removing the result;
- exact checkpoint bytes, field state, journal replay, restarted outputs, and
  frozen inference; and
- zero teacher or model calls and one adaptive persistent object,
  `QiFieldState.field`.

The separate adapter scenario returned
`result == "TYPED_ADAPTER_CONFORMANCE_OK"` for UTF-8 text, Python syntax,
float64 audio, float32 scientific tensors, and opaque bytes. Each adapter
round-tripped exact bytes, reproduced its view hash, retained exact provenance,
and rejected its malformed control. Audio and scientific arrays remained one
block-backed `Tensor`. Every one of these five modalities still reports
semantic status `unsupported` because no semantic task was measured.

The bounded claim remains field-generated relational programs for the declared
two-entity grid task plus exact typed ingress. It does not establish arbitrary
data semantics, code behavior, audio event understanding, scientific
interpretation, or inaccessible-world reconstruction.

## Theory status and software observations

The theory sources used here retain their current master-registry headers:

- [`open-questions-cassi-answers.md`](../../CassiTheory/open-questions-cassi-answers.md):
  `Comprehensive catalog—August 2026`;
- [`parameter-inventory.md`](../../CassiTheory/parameter-inventory.md):
  `Reference—August 2026`; and
- [`predictions/falsifiable-predictions.md`](../../CassiTheory/predictions/falsifiable-predictions.md):
  `Reference—August 2026`.

The ledger below converts theory material only into bounded engineering tests.
It does not promote a theory tier or derive an AI capability.

| Document | Exact August 2026 status | Permitted engineering lesson | Direct software observation | Prohibited claim |
|---|---|---|---|---|
| [`interscale-current-soliton.md`](../../CassiTheory/foundations/interscale-current-soliton.md) | Hypothesized—August 2026 | Explicit linked-scale bookkeeping may inspire a test | Reconstruct every source, sink, and boundary term before calling a measured quantity transport | Semantics, a universal current, or a field-intelligence law follows from the hypothesized physical current |
| [`loop-to-bubble-projection-theorem.md`](../../CassiTheory/foundations/loop-to-bubble-projection-theorem.md) | Derived conditional projection, bubble map, and population spectrum; Hypothesized microscopic physical identification—August 2026 | Test discarded-fibre causality and closure | Hold the projection fixed, vary its fibre, apply the same intervention, and compare outcomes | A many-to-one projection is causally sufficient or physically identified without the test |
| [`qi-flow-double-helix.md`](../../CassiTheory/foundations/qi-flow-double-helix.md) | Derived density diagnostics, passive lift bounds, and conditional compact-current specialization; Hypothesized phase and helical physical structure—August 2026 | Test hidden association and transition history | Hold visible marginals fixed while varying association or event circulation | Helical structure, an independent Qi substance, or semantic transport is established |
| [`quantum-measurement-derivation.md`](../../CassiTheory/foundations/quantum-measurement-derivation.md) | Derived conditional (regulated quantum mechanics); Hypothesized (CassiFI physical identification)—August 2026 | Use record distinguishability only after defining a software metric | Compare exact evidence records and their task-relevant consequences; retain the DQ promotion verdict `REJECT` | Quantum measurement supplies an AI semantic law, physical CassiFI identification, or architecture authority |
| [`proton-coherence-budget.md`](../../CassiTheory/foundations/proton-coherence-budget.md), [`strong-cp-derivation.md`](../../CassiTheory/foundations/strong-cp-derivation.md), [`baryon-asymmetry.md`](../../CassiTheory/foundations/baryon-asymmetry.md), and [`spin-fibonacci-spiral.md`](../../CassiTheory/foundations/spin-fibonacci-spiral.md) | Proton: Mapped coordinate / Derived conditional arithmetic / Hypothesized mechanisms—August 2026. Strong CP: Derivation (span Mapped: GUT-seed anchor and δ_CP per ledger; θ̄ ≈ 1.2×10⁻¹⁷)—August 2026. Baryon: Derivation (mechanism Hypothesized, C7/Q6; $\eta_{\mathrm{fit}}$ exponent Mapped—ledger; conditional normalized product Hypothesized; single $\eta$ normalization open; 44-step span open—no closure found in the 2026-08-11 sweeps, §4.5 and the $\Gamma/H = 1$ rate-based attempt, §4.7)—August 2026. Spin/Fibonacci: Hypothesized—August 2026. | No engineering authority beyond preserving these mixed Mapped, Derived-conditional, and Hypothesized tiers and testing independently defined software quantities | No AI observable mapping exists | A Planck–proton, strong-CP, baryon, spin, or Fibonacci formula sets a software constant, reasoning-step count, semantic law, or architecture authority |

The direct software tests are:

| Theory object | Exact proposed software test |
|---|---|
| Reciprocal map $P_s$ | Excite one coupled singular vector and one nullspace vector of $W_{s+1}^{1/2}P_sW_s^{-1/2}$. Only the coupled direction may transfer. Record the singular spectrum, effective rank, and nullspace used by the test. |
| Classical reciprocal current $\mathcal K_{Z,s\to s+1}=-w_Zg_{Z,s}\operatorname{Im}\langle P_sZ_s,Z_{s+1}-P_sZ_s\rangle_{W_{s+1}}$ | Run an isolated two-sheet sign arm, phase-aligned-zero arm, reversed-phase arm, $P_s=0$ arm, nullspace arm, and exact checkpoint/restart arm. Independently recompute the source and target ledger rows and require equal magnitude with opposite sign. |
| Hypothesized interscale current $J_{n+1/2}=(K_{\mathfrak s}/\hbar)\operatorname{Im}(\Psi_n^\dagger U_n^\dagger\Psi_{n+1})$ | Reconstruct full node continuity, including spatial, boundary, port, remap, composition, conversion, residual-force, retention, and damping terms. The word conservation is unavailable until the complete residual closes. |
| Projection closure | Construct paired microstates with the same projection and different discarded fibre, then apply the same intervention. Different outcomes fail causal sufficiency and require retaining the fibre or returning `ambiguous`/`unsupported`. |
| Four-channel hidden association $\mathcal C$ | Construct states with the same $\mathcal N$, $\mathcal P$, and $\mathcal D$ but different $\mathcal C$, then require a task in which their observed successors differ. A model blind to $\mathcal C$ must fail or abstain. |
| Trajectory circulation | Produce identical terminal snapshots through different event histories, then measure a different next consequence. Snapshot-only state must fail or abstain. |
| Relaxation criterion $g_{\rm int}T_B\gg1$ | Sweep internal refinement relative to the query horizon and compare resolved with coarse successor prediction. Import neither a physical threshold nor a $\varphi$-derived reasoning-step count. |

The existing top-symbol-demodulated `j_scale` is a phase-quadrature diagnostic,
as recorded in [Part 0](00-foundations.md#present-implementation-truth). It is
not the interscale current equation above. Every proposed AI use of these tests
is an engineering analogy under direct observation, not a theory-derived
universal-understanding result.


## Capability accounting

Coverage uses only `supported`, `partial`, `unsupported`, and `unmeasured`.
Every semantic claim names a modality or view, task family, nuisance set,
direction, date, and evidence. Adapter conformance is independent of semantic
capability: an opaque payload can be substrate-`supported` while every semantic
query is `unsupported`.

| Modality/view | Adapter round-trip | Measured task family | Held-out nuisance transformations | Intervention result | Abstention result | Evidence/restart result | Transfer direction | Measured date | Status |
|---|---|---|---|---|---|---|---|---|---|
| Relational 2D typed programs | Exact observation-view fixtures | Bounded two-entity relational composition and action-role inference | Entity renaming, global translation, relation-equivalent programs, sensor intervals, and bounded layouts | 32/32 held-out consequences; prior 32/32 role bindings and 12/12 boundary consequences retained | Unidentified acted-on entity `ambiguous`; zero false settlement | Exact field checkpoint/restart; evidence and operator ablations remove support | Within typed relational view | 2026-09-01 | supported |
| Byte/control continuation | Exact fixed byte/control codec behavior | Sequence-specific Phi harmonic continuation | Exact sequence controls only | General semantic intervention not established | General semantic novelty not established | Phi and counterflow now persist in one shared field frame; affected provider suite green | Within byte/control view only | 2026-09-01 | partial |
| JSON structural view | Exact UTF-8 JSON round-trip, duplicate-key-safe deterministic tree, exact paths | Anonymous two-entity role binding and cardinal-action consequence | Random IDs, key aliases, record order, global grid translation, unseen layouts | 16/16 mixed held-out JSON queries exact | Unidentified role `ambiguous`; malformed JSON `unsupported` | Exact packet/view/Mnemic references and field restart | Within JSON and raster→JSON | 2026-09-01 | supported |
| Raster structural view | Exact contiguous `uint8` tensor round-trip, shape/stride/block digest | Anonymous two-plane role binding and cardinal-action consequence | Random plane assignment, global grid translation, unseen layouts | 16/16 mixed held-out raster queries exact | Unidentified plane `ambiguous`; malformed block `unsupported` | Exact packet/view/Mnemic references and field restart | Within raster and JSON→raster | 2026-09-01 | supported |
| JSON→raster | Both adapters exact; source-only JSON experience | Same bounded relational action-consequence program | Destination raster plane assignment and held-out layouts | 16/16 held-out raster consequences exact; max residual `0.0` | Hash-only structure removal returns no support | Selected interior and boundary program hashes match paired-field hashes | JSON to raster | 2026-09-01 | supported |
| Raster→JSON | Both adapters exact; source-only raster experience | Same bounded relational action-consequence program | Destination JSON IDs, aliases, order, and held-out layouts | 16/16 held-out JSON consequences exact; max residual `0.0` | Hash-only structure removal returns no support | Selected interior and boundary program hashes match paired-field hashes | Raster to JSON | 2026-09-01 | supported |
| UTF-8 text | Exact byte round-trip and deterministic decoded atom | UTF-8 syntax only | Malformed UTF-8 control | No semantic intervention measured | Semantic query `unsupported` | Exact journal replay and provenance | Substrate only | 2026-09-01 | partial |
| Python code | Exact byte round-trip and deterministic AST syntax tree | Python syntax only; no behavior task | Syntax-error control | Code behavior not measured | Malformed code `unsupported`; semantic query `unsupported` | Exact journal replay, source paths/spans, deterministic view hash | Within code syntax only | 2026-09-01 | partial |
| Audio samples | Exact float64 little-endian block-backed tensor | Acquired sample retention only | Length/dtype mismatch and no-sample controls | Audio events or meaning not measured | Malformed/no-sample `unsupported`; semantic query `unsupported` | Exact journal replay, shape/stride/block digest | Substrate only | 2026-09-01 | partial |
| Scientific tensor | Exact float32 block-backed tensor | Dtype, shape, stride, and acquired-value retention only | Length/shape mismatch control | Scientific interpretation not measured | Malformed tensor `unsupported`; semantic query `unsupported` | Exact journal replay and block digest | Substrate only | 2026-09-01 | partial |
| Unknown binary semantics | Exact opaque-byte retention | No semantic task | Unknown codec and descriptor-mismatch controls | No semantic intervention | `unsupported` with `no_adapter`, `descriptor_mismatch`, or no measured task | Exact packet, payload, and replay references remain available | No semantic transfer claim | 2026-09-01 | unsupported |
| Opaque acquired-payload retention | Exact bytes, digest, full span, and replay | Exact retention only | Byte-preserving replay | Not a semantic task | Semantic status remains `unsupported` | Five-entry adapter journal replay exact and idempotent | Substrate only | 2026-09-01 | supported |

## Implemented first slice

The heterogeneous world-transition slice is current CassiFI code. It reuses the
deterministic two-entity world and four cardinal actions. JSON exposes only its
tree and numeric values; raster exposes only tensor topology and spatial
indices. Neither adapter emits `self`, `target`, a shared object identifier, or
a precomputed cross-view correspondence. The field infers the acted-on anonymous
record or plane from observed intervention and consequence.

The implementation order is complete:

1. `ProgramContext` consumes the five-constructor `ObservationView`.
2. The paired JSON/raster scenario exercises 32 experience events, 32 held-out
   queries, nuisance invariance, ambiguity, pairing, structural, field, and
   operator controls.
3. Exact packet references are represented in CassiFI and stored by Mnemic;
   Thalamus admits the fixed reference under a hard work budget.
4. Phi continuation and counterflow persist in one native shared
   `QiFieldState`.
5. Composite state classes, split payloads, and the old checkpoint schema are
   removed in one clean cutover.
6. Text, code, audio, scientific tensor, and opaque adapters are each measured
   for exact conformance; their unmeasured semantic tasks remain
   `unsupported`.

The implementation adds no service, dependency, optimizer, teacher/model call,
learned codec, learned modality head, or second adaptive checkpoint.
