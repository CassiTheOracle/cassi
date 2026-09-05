# State inventory, backends, receipts, and verification

> CassiFI implementation plan, Part 9. [Previous](./08-language-and-serving.md) · [Index](../README.md) · [Next](./10-work-packages.md)

## State and lifetime inventory

The one-state rule is operational, not rhetorical:

| Category | Objects | Owner and lifetime | Serialized | May change a future field step |
|---|---|---|---|---|
| Adaptive persistent state | `QiFieldState.field`, including `epsilon2_ema` | controller/session, across cycles and restarts | raw canonical tensor only | yes |
| Immutable operator identity | flow/retention/stability/clock profile, geometry, DFT symbols, `P/P†`, boundary probes, body transforms, action table, codec, contract root/registry/projection/default map | process/profile lifetime | hash plus required canonical descriptor | yes, but never adapts |
| Cycle-local transient | packet payloads, drives, body pose, candidate clones, predictions, residuals, remaps, ledgers, Hodge/topology maps, output integration windows | one bounded transaction | no raw tensors; hashes/scalars in receipts | only during that transaction |
| Bounded causal protocol/provenance | envelope/head/sequence, request/action idempotency, ingress journal/cursor/source frontiers/watermark, proposal/port-reaction hashes, dynamic-port-frame/scattering/capacity/openness/discriminability/delayed-influence/forgetting identities, at most one tick outbox/terminal ack, indeterminate-world-effect seal, pending/consumed applied efference, bounded response/display records | session envelope plus content-addressed audit objects | hashes, exact command/response bytes, statuses, bounded scalars, rank/conditioning intervals, work/fanout/byte channels, and sealed lineage identities only | packet exact-once ordering and one acknowledged efference/remap only; never sensed or scored as memory |
| External world truth | deterministic/simulated/physical world state, sensor calibration, actuator state | world adapter | separate replay/world artifact | only through a new validated observation |
| Offline plans/certificates | `QiFieldExperiencePlan`, `QiNumericalCertificate` plus immutable certificate extensions, `QiTransactionModelReceipt`, capacity/openness/action/delayed-influence/forgetting/text ownership/codebook receipts, `QiStateLineageForkReceipt`, adapter-off evidence, and indeterminate-world-effect evidence | independent verifier and content-addressed run tree; never live field lifetime | canonical plans, interval enclosures, finite model frontiers, exact artifact manifests, bounded trajectory/causal evidence, and fork/seal proofs | never; these objects cannot become adaptive state |

No residual EMA, trust EMA, pose history, attention vector, action history,
visited set, candidate cache, replay buffer, KV store, learned parameter,
optimizer, transcript-conditioned cursor, or running diagnostic tensor is added.
`cassi_qi_kv.py`, legacy conscious/organism persistence, learned-world state,
and native Qwen state remain unreachable from the canonical import graph.

Candidate field clones are capped by profile action count and freed before the
transaction returns. Diagnostic maps are reduced to receipt scalars or written
only to an explicitly requested raw verification artifact; they are never
loaded into a later live cycle.

## Symbols, dimensions, and units

| Symbol/name | Meaning | Shape or unit |
|---|---|---|
| `S` | number of field scales | integer |
| `M` | real slots per packed plane and scale; active slots are physical sites | integer |
| `B` | independent batch/session lanes; no lane coupling | integer |
| `N_s=N_{x,s}N_{y,s}` | active physical-sheet sites at scale `s` | integer, `N_s<=M` |
| `h` | field integrator interval | profile time unit |
| `phi=(1+sqrt(5))/2` | immutable Yang/Yin composition constant | dimensionless |
| `x,y,dx_s,dy_s` | body-frame sheet coordinates and spacing | profile length unit |
| `k_x,k_y` | derived angular spatial frequency | radians / length |
| `E_Y,E_I` | dimensionless complex Yang/Yin position fields reconstructed from real planes | normalized field amplitude |
| `V_Y,V_I` | complex Yang/Yin temporal velocities reconstructed from real planes | inverse time |
| `D,V_D` | differential coordinate and velocity | dimensionless; inverse time |
| `C,V_C` | complementary carrier coordinate and velocity | dimensionless; inverse time |
| `rho_pos` | `abs(E_Y)^2 + abs(E_I)^2` | dimensionless |
| `epsilon` | `abs(E_Y)^2 - phi*abs(E_I)^2` | dimensionless |
| `epsilon2_ema` | local EMA of `epsilon^2` | dimensionless |
| `delta_phase,delta_amp` | positive diagnostic regularizers | dimensionless |
| `Q` | bounded conversion/coherence factor used by the v3 law | dimensionless |
| `w_D,w_C` | induced coordinate-metric weights | dimensionless |
| `W_s` | positive cell-volume metric on the active sheet | diagonal `[N_s,N_s]`, length squared |
| `G_s` | induced `(D,C)` active-coordinate metric `diag(w_DW_s,w_CW_s)` | diagonal `[2N_s,2N_s]`, length squared |
| `mathcal G_s,mathcal G_s^T` | active gather and inactive-tail scatter | `[N_s,M]`, `[M,N_s]` linear maps |
| `omega_Z` | base angular frequency | inverse time |
| `g_Z,kappa_Z` | scale-link gain and cubic coefficient | inverse time squared |
| `c_Z` | propagation speed | length / time |
| `gamma_Z,lambda` | damping and conversion rates | inverse time |
| `beta` / `epsilon_memory_time` / `tau_epsilon(h)` | bounded composition gain / physical constitutive time / derived per-step EMA coefficient `1-exp(-h/epsilon_memory_time)` | dimensionless / time / dimensionless |
| `epsilon_ref` | composition-law imbalance scale | dimensionless and positive |
| `rho_ref` | positive Yang/Yin position-density reference | dimensionless |
| `r_core,rho_ring,rho_topo` | topological-retention smooth-core, ring, and endpoint amplitude scales | normalized field amplitude |
| `E_topo,U_topo,Delta_H_topo` | topological-retention energy scale, potential, and verified slip barrier | normalized field-energy units |
| `lambda_ph,lambda_core,delta_topo,delta_topo_int` | topological-retention phase/core weights and topology guards | dimensionless |
| `E_ref,r^obs,E_ref,r^action` | finite residual normalization energies | boundary-`r` metric squared units, positive |
| `nu_r,mu_move,mu_flow` | modality and action-score weights | dimensionless, nonnegative |
| `r_j,Delta q_a,j` | action component range and displacement | the same declared actuator unit |
| `m_a,d_a` | action-region mask and unit direction | inverse area; dimensionless vector |
| `J_ref` | positive current-alignment reference | same units as `J_D` after normalized-mask integration |
| `eta_r` | residual-return gain | field acceleration per boundary-`r` unit |
| `q_D,q_C` | phase-charge densities | inverse time |
| `J_D,J_C` | spatial phase currents | length / time squared |
| `P_D,P_C` | normalized wave-energy fluxes; never named `P_s` | length / time cubed |
| `R` | Yang/Yin density conversion rate | inverse time |
| `P_s` | fixed scale restriction operator only | `[N_{s+1},N_s]` linear map |
| `A_r` | boundary-`r` sensor injection `H_r -> H_field` | descriptor-specific linear map |
| `B_r,B_r†` | boundary-`r` prediction and metric adjoint | `H_field -> H_r`; `H_r -> H_field` |
| `W_r` | boundary-`r` metric/inner-product weight | descriptor units |
| `p_a,q_a` | text-port analysis/reaction vectors normalized in `W_0` | inverse length |
| `p_j,q_j` | motor-port analysis/metric-dual synthesis vectors | inverse length |
| `z_a,z_j` | text/motor generalized coordinates `<p,D_0>_W` | length |
| `u_a,v_j,a^{in/out}` | port velocities and characteristic amplitudes | length / time |
| `w_a^{out},P_j^{out}` | signed instantaneous characteristic power | length squared / time cubed |
| `M_{1,a,g}^{out}` / `M_{2,a,g}^{out}` | certified slope / curvature bounds for text-port output power | length squared / time to the fourth / fifth |
| `A_a,P_a,N_a,D_a,U_{A,a}^{(h)},U_{A,a}^{(2h)},U_{P,a},U_{N,a},W_emit,a,W_j^{out}` | integrated trajectory/work quantities and enclosures | length squared / time squared |
| `B_Gamma,Delta_H_topo,min,W_reset` | topological-retention path barrier, accepted threshold, and signed controller-reset work | length squared / time squared |
| `Delta_Q_Z,reset` | zero-clock topological-retention phase-charge impulse | length squared / time |
| `packet_sha256` | exact validated boundary payload identity | 32-byte digest |
| `Pi_{r,s}` | field-derived passive boundary permeability | dimensionless in `[0,1]` |
| `W_incident,W_admitted,W_reflected` | incident, admitted, and reflected permeability work | boundary-work units |
| `rank_dyn, kappa_dyn, chi_dyn` | dynamic trajectory-response rank, conditioning interval, and cross-talk bound | integer / dimensionless / dimensionless |
| `W_incident,W_reflected,W_transmitted,W_absorbed` | scattering work channels at a scale or external port | boundary-work units |
| `epsilon_num, U_num` | offline numerical enclosure center and certified uncertainty | field quantity / same units |

The plan uses `Q` only for the profile's local conversion/coherence factor and
never overloads it with spatial current. Boundary waves are written `W_r`;
wave-energy flux is `P_D/P_C`; scale maps are `P_s`. Every profile field states
its units. A caller cannot provide an unprofiled gain or normalization.

Field amplitude is dimensionless by definition after each descriptor's
calibration map. Physical sensor/actuator units remain in the boundary metric
and work receipt; they are never added directly to normalized field energy.
`delta_phase` is a positive dimensionless diagnostic regularizer frozen in the
profile and has no effect on evolution.

For each valid boundary packet `r`, residual comparison uses:

\[
\langle u,v\rangle_r=u^\dagger W_rv,
\]

\[
E_r=
\frac{
\|u_{\mathrm{obs}}-u_{\mathrm{pred}}\|_{W_r}^2
}{
\max(
\|u_{\mathrm{obs}}\|_{W_r}^2,
E^{\mathrm{obs}}_{\mathrm{ref},r}
)
},
\qquad E^{\mathrm{obs}}_{\mathrm{ref},r}>0.
\]

Packet validity is a separate boolean/schema decision. A valid all-zero
observation is data and penalizes a nonzero prediction; a missing or invalid
packet fails before this metric is evaluated.

Different modalities retain separate dimensionless residuals and work ledgers.
They are not averaged into a single score unless a fixed profile weighting and
its null calibration are explicitly declared.

## CPU/ROCm backend and capacity plan

The mandatory endpoint is the Python/Torch flow law running on both a CPU
reference backend and the workstation's ROCm backend. Native llama.cpp/GGML,
Vulkan Qwen operators, GGUF, and legacy modal Torch layouts remain separately
invoked offline experiments and cannot satisfy or substitute for this endpoint.

### Backend interface

`cassi_qi_backend.py` defines:

```python
class QiFlowBackend(Protocol):
    identity: QiBackendIdentity
    def prepare(profile: QiFlowProfile, batch: int) -> QiPreparedOperators: ...
    def execute_advance(state: QiFieldState, drive: QiDriveBundle) -> QiFlowStep: ...
    def fork(state: QiFieldState, count: int) -> QiCandidateBatch: ...
    def serialize_state(state: QiFieldState) -> bytes: ...
    def synchronize() -> None: ...
    def memory_receipt() -> QiBackendMemoryReceipt: ...
```

`TorchFlowBackend` implements the same tensor law for `cpu` and ROCm's Torch
`cuda` device. Construction requires an explicit device and dtype. Requested
ROCm execution fails if the profile-declared device identity or required
capability is unavailable; it never falls back to
CPU. The receipt records Torch/ROCm versions, actual device name/index/PCI
identity where available, dtype, deterministic settings, thread policy, FFT
identity, prepared-operator hash, fallback count, and synchronization policy.

`QiRuntimeConfig` is process-local and non-adaptive:

```text
schema
profile_path
device = cpu | cuda
dtype = float32 | float64
cpu_threads
interop_threads
deterministic_algorithms
same_backend_exact_replay
cross_backend_tolerances
max_sessions
max_batch
max_candidates
max_packet_bytes
max_queue_events
latency_budget
working_memory_budget
```

It is validated against the immutable physics profile. It cannot change field
coefficients, source gains, thresholds, or action behavior.

### Determinism contract

- all random APIs are absent from the live call graph;
- fixed operator tensors are built once in canonical order and hashed;
- Torch deterministic algorithms are enabled where supported and unsupported
  operations fail profile construction;
- FFT normalization/order is explicit and tested independently;
- reductions use fixed dimension/order expressions; no unordered host
  aggregation participates in decisions;
- device synchronization occurs before timing, receipt emission, state hash,
  and checkpoint copy;
- same backend/build/profile replay is byte-exact after deterministic warm-up;
- CPU/ROCm parity uses profile-declared scalar, field, current, work, and
  decision tolerances and requires identical discrete event/action choices;
- cross-backend state hashes are not falsely required to be identical when the
  declared numerical contract is tolerance-based.

### Numerical certificate, online guards, and independent replay

QI-NUM-001 (`W3N / G3N`) separates three evidence layers that must not be
collapsed into one runtime boolean. `QiNumericalCertificate`,
`cassi.qi-flow-numerical-certificate.v1`, is an immutable offline root
certificate and contains:

```text
certificate_id
certificate_chain_id
chain_ordinal = 0
parent_certificate_sha256 = null
profile_sha256
consumed_semantic_subhashes[]
operator_sha256 / execution_schedule_sha256
admitted_domain
offline_enclosure = {
  precision_bits, arithmetic, subdivision, interval_endpoints[],
  term_bounds[], remainder_bounds[], refinement_identity
}
online_guard_contract = {
  finite_state, amplitude_energy, inactive_tail, work_closure,
  residual, topology, and exact rejection thresholds
}
independent_replay = {
  input/state/packet hashes, backend/build identity,
  expected state/ledger/decision hashes or declared parity tolerances,
  replay command and result identity
}
complete_section_inventory[] = {
  section_id, owning_package, artifact_sha256, required, ordinal
}
chain_status = provisional | final
final_certificate_identity_sha256
self_sha256
```

The offline layer uses the registered high-precision/enclosure method to derive
termwise bounds over the complete admitted domain. Every interval endpoint,
precision, subdivision, rounding mode, remainder, and section-inventory entry
is canonically encoded. The online layer checks only cheap scalar guards on an
untouched candidate (finite values, declared amplitude/energy/work limits,
inactive-tail zeros, closure residuals, and topology/port thresholds); passing
those guards never claims to reproduce the enclosure. The independent replay
layer starts from retained canonical bytes in a separate verifier and
recomputes the state, ledger, and discrete decision under the declared
same-backend or cross-backend contract. A runtime-generated certificate or
self-reported finite counter is not independent replay.

Numerical evidence is extended only by an immutable,
content-addressed `cassi.qi-flow-certificate-extension.v1` object:

```text
schema = cassi.qi-flow-certificate-extension.v1
certificate_chain_id
chain_ordinal > 0
parent_certificate_sha256
parent_section_inventory_sha256
profile_sha256
consumed_semantic_subhashes[]
added_sections[] = {
  section_id, owning_package, artifact_sha256, required, ordinal
}
complete_section_inventory[] = {
  every parent section in identical order, plus every added section
}
chain_status = provisional | final
final_certificate_identity_sha256
self_sha256
```

An extension is accepted only when its parent digest and parent inventory
reopen exactly, its added section IDs are new and registry-declared, and its
complete inventory is the deterministic parent inventory followed by the
registered additions. It can add evidence but cannot mutate, replace, delete,
or reorder a parent section. The parent bytes remain retained and indexed
forever under their own digest. The final extension sets `chain_status=final`
and names the complete cumulative inventory; its
`final_certificate_identity_sha256` equals the terminal extension identity.
The `self_sha256` and `final_certificate_identity_sha256` fields are removed
from the identity preimage, so this check has no self-reference. A provisional
extension has a null final identity and may be followed only by another
extension with that exact parent. No certificate chain is final unless every
required section is present exactly once and the final identity is indexed.

The root and every extension are domain-separated, parented by the ordered
`state_contract_sha256` and `backend_capacity_sha256` values, and indexed with
their raw offline evidence. Missing precision metadata, a non-finite or
unordered interval, an admitted point outside the enclosure, a guard that is
not profile-declared, a missing/duplicate/reordered required section, a parent
digest or inventory mismatch, a replay that reuses runtime receipt builders, or
a high-precision claim supported only by online scalars fails closed as
`NUMERICAL_CERTIFICATE_INVALID`.

### Allocation and copy discipline

Prepared operators are immutable device tensors:

- active maps and masks;
- `k_x`, `k_y`, `|k|^2`, cell-volume weights;
- scale restriction/prolongation data;
- body remap tables;
- boundary probes and adjoints;
- text codebook;
- scalar coefficient banks.

They are allocated once per `(profile,backend,dtype)` and never modified. A
bounded cache uses explicit lifecycle/refcount and cannot grow by session.

The step path:

- keeps field, scratch, candidate, diagnostics, and prepared operators on the
  selected device;
- preallocates reusable scratch at the declared maximum batch/candidate shape;
- performs no `.to()`, `.cpu()`, `.numpy()`, implicit scalar sync, or new
  coefficient construction inside the substep loop;
- reduces diagnostics on device;
- transfers one bounded receipt block and, at checkpoint boundaries, one state
  block through pinned host memory after explicit synchronization;
- zeroes/releases candidate scratch before returning;
- reports steady-state allocation count and peak reserved/allocated memory.

Checkpoint bytes use a canonical little-endian host representation rather than
device-dependent `torch.save()` bytes. Device restore validates canonical bytes,
copies once to the requested backend, and verifies the logical state hash before
any evolution.

### Cost and memory formulas

For scalar byte width `d`, common packed width `M`, `S` scales, and batch
width `B`, the persistent field allocation is

\[
\text{state bytes}=9SMBd.
\]

The four transient complex active-coordinate views `D,C,V_D,V_C` require,
when materialized,

\[
\text{coordinate bytes}=8Bd\sum_s N_s.
\]

For `A_branch` simultaneously materialized complete field clones across
world-action evolution or text-reaction preflight, packed branch states require

\[
\text{candidate bytes}=9SMB A_{\mathrm{branch}}d.
\]

Boundary packets, padded nonlinear FFT work areas, scale-link residuals,
diagnostic maps, prepared operators, and backend workspaces are added
explicitly in the profile's working-memory formula. No capacity profile is
admitted if its worst-case bound exceeds the declared VRAM/RAM budget.

The dominant per-step complexity is

\[
O\!\left(
  B(1+A_{\mathrm{branch}})\sum_s N_s\log N_s
  +B\sum_s N_s
  +BSM
\right),
\]

where the branch factor applies only to clones that execute the affected
operator; zero-time preflights do not inherit a full FFT term unless they
actually recompute it. Candidate batching shares immutable prepared operators
but never couples batch lanes. The profile records both maximum logical
candidate count and maximum simultaneously materialized clone count.

Per-step complexity is not request cost. Let `A_act` be the maximum simultaneous
world-action branch count, `N_sym=260` the frozen text frame, and
`A_emit(k)<=N_sym` the raw-eligible text reactions preflighted in output window
`k`. For a request with `K_in` ingress symbols and `N_out` committed or
abstained emission windows, the frozen end-to-end model is

\[
\begin{aligned}
T_{\mathrm{request}}={}&
T_{\mathrm{prewarm}}
+K_{\mathrm{in}}\!
\left(T_{\mathrm{ingress}}+
n_{\mathrm{dwell,in}}T_{\mathrm{intrinsic}}\right)\\
&+\sum_{k=1}^{N_{\mathrm{out}}}\!
\left(
T_{\mathrm{emit\ frame}}
+n_{\mathrm{dwell,out}}T_{\mathrm{intrinsic}}
+T_{\mathrm{matched\ null},k}
+A_{\mathrm{emit}}(k)T_{\mathrm{reaction\ preflight},k}
\right)\\
&+T_{\mathrm{UTF8/event}}
+T_{\mathrm{body/remap}}
+T_{\mathrm{prediction/residual}}
+T_{\mathrm{action\ branches}}(A_{\mathrm{act}})
+T_{\mathrm{world\ wire}}
+T_{\mathrm{checkpoint(fsync+atomic\ commit)}} .
\end{aligned}
\]

The frame term explicitly includes the dense fixed-probe contraction
`O(N_out B N_sym N_0)`, terminal sampling/refinement, and device
synchronization. The matched-null term includes its same-predecessor
source-suppressed counterfactual; reaction cost includes every raw-eligible
clone and complete Hamiltonian/topology preflight. The request receipt also
accounts for packet/event/journal/world/response bytes, canonical JSON/HMAC,
checkpoint and object-index bytes, retained-response quota, scratch/candidate
peak bytes, allocator calls, host/device copies, and synchronization count.
Benchmarking reports cold-start and warm steady-state `p50/p95/max` for every
term and total latency, rather than presenting intrinsic-step latency as
provider latency. `T_prewarm` is zero only in a separately reported
already-prepared run.

Persistent live sessions use `B=1`. The executor may stack independent
same-profile/session states into a transient batch only when event timestamps,
substep counts, dtype, backend, and candidate shape match. Splitting the batch
must reproduce individual execution under the backend contract. Session state
is checkpointed separately.

### Capacity profiles

Engineering uses three distinct versioned profiles:

1. **analytic calibration profile** — a 16-by-16 active sheet at the current
   storage order, used for law calibration, exact fixtures, and independent
   operator checks;
2. **integrated development profile** — a capacity chosen from measured
   optical/audio/text collision, horizon, and resource requirements and able
   to run every modality and world loop;
3. **release profile** — the current capacity that passes the required
   analytic, embodiment, memory, grounding, language, serving, restart, and
   performance checks.

The calibration profile can never become the endpoint merely because it passes
transport checks. Profile-selection runs measure raw collision curves, spatial
resolution, active/inactive allocation, memory horizon, candidate count,
state/scratch formulas, and CPU/ROCm costs. Those measurements may drive normal
design revisions; each concrete run manifest records the exact choices it
executed. The release profile contains real numerical values and no
placeholders or inherited v2 oscillator constants.

### Backend gate sequence

1. CPU float64 analytic reference for geometry, forces, conversion, links, and
   work closure.
2. CPU float32 parity against the float64 reference under versioned error
   bounds.
3. ROCm float32 operator parity on the same raw states/packets.
4. Same-backend exact checkpoint/restart and replay on CPU and ROCm.
5. Batched-versus-individual parity for independent sessions and candidate
   branches.
6. Full multimodal world episode on both backends with identical discrete
   decisions and bounded numeric differences.
7. Warm steady-state profiling at release capacity: latency distribution,
   throughput, allocations, host/device copies, synchronization, peak memory,
   queue pressure, checkpoint time, and provider streaming time.
8. Long-horizon full-system run with zero fallback, zero unaccounted clipping,
   bounded memory/locks, and ledger residual under profile tolerance.

### Compiled-code decision

Torch remains the release executor when it meets the current candidate's
latency, memory, parity, and allocation budgets. A dedicated field kernel is
considered only after the complete Torch path is correct and all of these are
true:

1. the full-system profile misses its declared performance budget in three
   repeated profiler runs;
2. one fixed operator family accounts for at least 40 percent of synchronized
   step wall time;
3. removing Python/host synchronization does not resolve the miss;
4. the proposed kernel has a complete CPU/ROCm reference, backward-free
   inference interface, exact layout/profile identity, and focused parity test;
5. the kernel does not import or depend on llama.cpp, GGUF, Qwen state, or a
   conventional learned runtime.

Only the measured operator is fused. It must remain a live result, expose the
same ledger terms, synchronize before boundary/action use, and pass the complete
affected gate board. A native kernel is an optimization of the same flow law,
not another backend semantics or a fallback.

## Receipt graph and independent verification

### Canonical hashing

`cassi_qi_receipts.py` is the only production hashing implementation. All
internal canonical JSON, profile, receipt, session, world-header, HMAC, and
fixture objects use `cassi.canonical-json.v1`:

- input is strict UTF-8 with no BOM; malformed UTF-8, unpaired surrogates,
  duplicate object keys, and non-scalar strings reject before hashing;
- strings preserve their exact Unicode scalar sequence: no NFC, NFD, case,
  slash, or newline normalization occurs;
- object keys are sorted by their unsigned UTF-8 byte strings; array order is
  preserved; no insignificant whitespace or trailing newline is emitted;
- quote and reverse-solidus use `\"` and `\\`; every `U+0000..U+001F`
  scalar uses lowercase `\u00xx`; all other scalars are emitted as their
  shortest direct UTF-8 sequence and `/` is unescaped;
- `null`, `true`, and `false` use those lowercase literals. JSON integer
  numbers are base-10, have no plus sign, exponent, leading zero, or negative
  zero, and are limited to `[-(2^53-1),2^53-1]`;
- arbitrary-precision integers, including every rational time numerator and
  denominator, use schema-declared `int-decimal-v1` strings: `0` or an optional
  leading `-` followed by a nonzero digit and digits; denominators are positive;
- schema-declared finite binary scalars are not decimal JSON numbers. They are
  tagged strings `f32:` plus eight or `f64:` plus sixteen lowercase hexadecimal
  IEEE-754 bits in most-significant-byte order. NaN and infinity reject, and
  scalar negative zero canonicalizes to positive zero before encoding;
- raw numeric arrays remain separately length-bounded little-endian payloads
  whose dtype, shape, byte count, and payload hash are in the canonical header;
  their element bits are not rewritten by JSON canonicalization.

Define `frame(b)=uint64_be(len(b)) || b`. Object identity is

```text
sha256(
  frame(utf8(schema)) ||
  frame(canonical_json(payload_without_self_sha256))
)
```

Every builder removes exactly its registered self-hash field before encoding,
and every validator reconstructs it. Tensor identity is

```text
sha256(
  frame(utf8(tensor_domain)) ||
  frame(utf8(semantic_parent_sha256)) ||
  frame(utf8(dtype)) ||
  uint32_be(rank) ||
  uint64_be(dim_0) || ... || uint64_be(dim_rank_minus_1) ||
  uint64_be(raw_tensor_bytes) ||
  contiguous little-endian raw tensor bytes
)
```

For persistent field-state tensors, `semantic_parent_sha256` is
`state_contract_sha256`. Boundary, action, backend, and protocol tensor domains
use the ordered digest of only the semantic subhashes they consume. The full
`profile_sha256` remains envelope provenance; changing an unrelated HTTP or
evidence setting does not change raw field-state identity. Python and Godot
must produce byte-identical fixtures for empty/minimal/maximal objects, every
escape class, scalar edge, rational, float bit pattern, array shape, and
length-prefix boundary. Generic undomained `_digest()` helpers and the present
`boundary_fingerprint == codebook_fingerprint` alias are removed.

Every profile and release-relevant receipt payload carries the verified
`contract_root_sha256` or is directly indexed by the root object. The verifier
resolves that root before interpreting canonical bytes, defaults, schema fields,
or semantic-parent membership; a receipt cannot select a different codec,
registry, projection registry, or default map by request. A root mismatch is
an identity failure even when the local payload bytes happen to hash equally
under another implementation.


Every new profile or receipt object carries an explicit ordered
`consumed_semantic_subhashes` list whose names and values must match the
registry in `03-architecture-profiles-and-schemas.md`. The list is part of the
hashed payload, is sorted in registry order, and cannot be inferred from a
parent object. A builder rejects an omitted, duplicate, unknown, or
state-consuming reclassification; a validator recomputes both the list and
the object digest. Profile projection membership and `state_consuming` labels
are themselves frozen schema data, so lineage and evidence checks can audit
the exact ownership rather than trusting a caller-supplied label.

Interval endpoints, work channels, rank bounds, retry bounds, and model-state
enumerations in the new schemas use the existing integer/rational/finite-bit
canonical encodings. Raw trajectory or artifact bytes remain separately
length-bounded little-endian payloads referenced by digest; canonical JSON
never rounds or normalizes them. An object whose schema, parent subhashes,
raw-byte digest, byte limit, or self-hash cannot be reconstructed is
unindexed and fails closed.

### New profile and receipt object contracts

The following objects are the concrete schema records behind the ownership
table in Part 3. Each object is content-addressed, indexed from the committed
envelope or the independent run manifest, and carries the exact ordered
`consumed_semantic_subhashes` list. None is an adaptive state owner.

QI-ID-001 `QiContractRoot`
(`cassi.qi-flow-contract-root.v1`) is the indexed interpretation root for
every profile and receipt graph. The fixed, source-pinned
`cassi.qi-flow-contract-root-bootstrap.v1` parser opens only this root and
verifies its bootstrap-framed self-hash before any profile-selected codec is
trusted. The root's canonical fields are
`contract_root_id`,
`bootstrap_codec={schema,sha256}`,
`canonical_codec={schema,sha256}`,
`schema_registry={schema,sha256}`,
`projection_registry={schema,sha256}`, `profile_schema_sha256`,
`materialized_defaults={complete JSON-Pointer/value/type map}`,
`defaults_policy=release-explicit-no-omission-v1`, and `self_sha256`.
The root digest is computed with the fixed bootstrap after removing only
`self_sha256`; the bootstrap source/fixtures, descendant codec, registries,
profile schema, and complete default map are retained under their own digests.
A profile carries `contract_root_sha256` and every semantic projection
consumes it as interpretation metadata. A bootstrap mismatch, missing default
leaf, implicit registry/codec, descendant-codec attempt to interpret its own
root, or digest whose bytes are not indexed fails before field allocation.
This root is immutable metadata and never a second state object.


QI-BOUND-001 `QiBoundaryPermeabilityProfile`
(`cassi.qi-flow-boundary-permeability-profile.v1`) contains
`profile_sha256`, `boundary_action_sha256`, `port_id`, ordered `scale_ids`,
`descriptor_sha256`, `permeability_operator_sha256`, orientation and metric
identities, rational capture windows, the bounded gate and its transmitted/
admitted, reflected, and absorbed power fractions, their sum-to-one enclosure,
and the profile's complete work partition.
The operator is evaluated from the current field and fixed boundary descriptor;
the object stores no gain history or port cache. Its canonical work contract
is

```text
W_incident = W_admitted + W_reflected + W_absorbed + R_permeability
W_admitted >= 0
W_reflected >= 0
W_absorbed >= 0
```

The profile's fixture records the field-derived samples and independent
recomputation identity, not a learned permeability table. Nonfinite or
out-of-range permeability/fractions, negative admitted/reflected/absorbed
work, an unbounded remainder, descriptor/scale mismatch, candidate-dependent
behavior, or a missing closure proof is `PERMEABILITY_NONPASSIVE` and rejects
the boundary packet before field mutation.
W7P/G7P independently recomputes this profile and its work partition; the
profile cannot be accepted from a runtime scalar alone.

The QI-BOUND-001 evidence extension
`cassi.qi-flow-sensory-openness.v1` is the required witness that a
field-derived permeability is not permanently blind. Its canonical fields are:

```text
schema = cassi.qi-flow-sensory-openness.v1
receipt_id
profile_sha256 / state_contract_sha256 / boundary_action_sha256
step_head_sha256 / predecessor_head_sha256
mandatory_port_id / ordered_scale_ids / descriptor_sha256
permeability_operator_sha256
incident_work_budget = {lower, upper, unit}
positive_incident_arm[] = {
  source_packet_sha256, admitted_work_interval,
  reflected_work_interval, absorbed_work_interval,
  response_interval, trajectory_sha256
}
openness_interval = {lower, upper}
openness_threshold
recovery_horizon
recovery_arm[] = {perturbation_sha256, response_interval,
                  admitted_work_interval, recovery_interval}
null_or_closed_control_sha256
closure_residual_interval
fixture_sha256 / independent_replay_identity
consumed_semantic_subhashes[]
self_sha256
```

Every mandatory port has at least one registered positive incident-work arm
and one finite recovery arm under the same descriptor, metric, and profile.
`incident_work_budget.lower` is strictly positive; null or zero-work packets
are controls and cannot establish openness. The verifier checks the
incident-work-normalized openness and recovery intervals against the declared
uncertainty-aware threshold. Permanent blindness, an absent recovery witness,
an openness interval whose lower bound does not clear the threshold, a
negative/unbounded work channel, or a candidate/history-dependent operator
fails `SENSORY_OPENNESS_INSUFFICIENT`. The receipt is bounded evidence only
and never a permeability table or adaptive state.


QI-LEARN-001 `QiFieldExperiencePlan`
(`cassi.qi-flow-field-experience-plan.v1`) freezes an experience exercise
without adding memory. Its canonical field set is:

```text
plan_id / plan_sha256
profile_sha256 / source_identity_sha256 / state_contract_sha256
scale_geometry_mode = temporal-full-rank | spatiotemporal-pyramid
codec_sha256 / boundary_descriptor_sha256[] / body_frame_sha256
clock_schedule_identity
raw_utf8_control_streams[]
  {stream_id, descriptor_sha256, source_epoch, source_stream_id,
   intervals, byte_count, bytes_sha256}
grounded_world_episode_streams[]
  {world_id, episode_id, initial_state_sha256, tick_log_sha256}
event_and_chunk_partition_fixture_sha256
timing_and_delay_windows
work_budgets = {per_port, per_packet, per_event, per_episode, total}
residual_budget
work_classes = {incident, admitted, reflected, absorbed, residual}
curriculum_stage_specs[]
whole_episode_split_sha256
  {train_episode_ids, control_episode_ids, heldout_episode_ids}
washout_schedule / control_profile_sha256[]
stopping_rule
checkpoint_selection_rule
  {initial, pre_washout[], post_washout[], stage_boundary[], final}
raw_artifact_retention_policy_sha256
teacher_model_exclusion = true
plan_self_sha256
```

Raw stream bytes are retained under the run policy and referenced by digest;
they are not copied into `QiFieldState`. `raw_utf8_control_streams` preserve
exact bytes, role/control events, source order, chunk partitions, and episode
boundaries, while `grounded_world_episode_streams` preserve world identity,
initial state, and tick-log bytes.

The plan's arrays are sorted by their declared stream/episode keys and all
intervals use canonical rational encoding. A split that bisects an episode,
changes after seeing a result, omits washout, exceeds a work budget, uses an
unregistered stream/control, or selects a checkpoint post hoc fails
`EXPERIENCE_PLAN_INVALID`. The plan cannot contain weights, embeddings,
optimizer/teacher state, replay buffers, or an adaptive stopping signal.
W10E/G10E independently validates the plan before reading outcome metrics.

QI-CAP-001 (`W6A/W6B/W10R; G6A/G6B/G6C`) is recorded as the
`cassi.qi-flow-capacity-ladder.v1` receipt. topological-retention capacity is generated only
by exact canonical `advance()` trajectories under the frozen controller
grammar, the exact physical horizon, and a nonnegative incident/source-work
budget. Its canonical fields are:

```text
schema = cassi.qi-flow-capacity-ladder.v1
receipt_id
profile_sha256 / state_contract_sha256 / backend_capacity_sha256
initial_state_sha256 / controller_grammar_sha256
physical_horizon = {num, den, unit}
trajectory_set_sha256 / ordered_trajectory_ids[]
work_budget = {incident_lower, incident_upper,
               source_lower, source_upper, unit}
capacity_levels = {
  geometric, reachable, observable, usable, retained, reusable
}
capacity_intervals = {
  level: {lower, upper, unit, uncertainty}
}
reachability_witnesses[] = {
  trajectory_id, predecessor_sha256, candidate_sha256,
  advance_count, source_budget_interval = {lower, upper, unit},
  zero_clock_transport_sha256, work_rows_sha256, endpoint_sha256
}
reset_control_sha256 / saturation_control_sha256 / overwrite_control_sha256
washout_and_recovery_schedule_sha256
consumed_semantic_subhashes[]
self_sha256
```

`geometric` is the declared active-space/storage capacity; `reachable` is the
set reached by those exact trajectories; `observable` is the subset separated
by registered boundary observations; `usable` also clears the registered
decision/action thresholds; `retained` survives the declared washout/retention
horizon; and `reusable` is reacquired by a new exact trajectory after the
registered forgetting interval. These levels are not interchangeable and
their intervals may not be promoted by a larger geometric rank. A retention
reset is a control transition, never an acquisition witness. Missing
predecessor/candidate bytes, a post-hoc path, a negative or unbounded work
budget, reset counted as acquisition, or a capacity claim without the
corresponding controls fails `CAPACITY_LADDER_INVALID`. All trajectory data
are bounded receipt evidence; no capacity map, replay buffer, or other state
object is added to `QiFieldState`.

QI-RET-003 records dynamical reachability and forgetting as the
`cassi.qi-flow-forgetting.v1` receipt:

```text
schema = cassi.qi-flow-forgetting.v1
receipt_id
profile_sha256 / state_contract_sha256 / backend_capacity_sha256
retention_mode = topological-v1
initial_state_sha256 / controller_grammar_sha256
exact_physical_horizon / advance_schedule_sha256
trajectory_set_sha256 / ordered_trajectory_ids[]
incident_source_work_budget
predecessor_candidate_endpoint_hashes[]
capacity_level = geometric | reachable | observable | usable
forgetting_arm[] = {
  perturbation_sha256, overwrite_work_interval, washout_schedule_sha256,
  pre_forgetting_endpoint_sha256, post_forgetting_endpoint_sha256,
  retained_label_interval, recovery_interval,
  reacquisition_trajectory_sha256
}
reset_control_sha256 / saturation_control_sha256 / unreachable_control_sha256
uncertainty_threshold / closure_residual_interval
consumed_semantic_subhashes[]
self_sha256
```

Every arm is generated by the exact canonical `advance()` schedule under the
frozen controller grammar, exact physical horizon, and nonnegative
incident/source-work budget. `retained_label_interval` and
`recovery_interval` are measured after the registered washout; an explicit
retention reset is only a control and never an acquisition or forgetting
witness. The verifier requires predecessor/candidate bytes, reachable and
unreachable controls, saturation/overwrite work, and a fresh reacquisition
trajectory. Missing cells, post-hoc trajectories, negative/unbounded work,
or a final label without the dynamical path fails
`FORGETTING_RECEIPT_INVALID`. The receipt is bounded evidence and adds no
forgetting register, replay buffer, or second field object.



QI-TEXT-001 `QiDynamicPortFrame` (`cassi.qi-flow-dynamic-port-frame.v1`) is the retained
trajectory-response artifact for one declared port and common finite horizon.
It contains `frame_id`, step/predecessor/head hashes, port and descriptor
identity, horizon and intervention-set hashes, response-vector payload
digests, interval-certified `rank_lower/rank_upper`, singular-value and
conditioning intervals, cross-talk matrix/bound, sampling/refinement
identity, and the exact no-peek candidate inputs. The dynamic rank is not
inferred from the static probe Gram matrix.
The canonical payload also records `dynamic_frame_count`,
`candidate_trajectory_count`, `response_sample_count`,
`raw_evidence_byte_count`, `max_dynamic_frames_per_cycle`,
`max_dynamic_response_bytes_per_frame`, `max_dynamic_evidence_bytes_per_cycle`,
and `bound_identity`; these counts are verified before any response payload is
allocated.

The frame profile also freezes source/receiver probe ordering, actual fastest
sheet size `N_0`, predecessor state, null source, candidate amplitudes,
temporal sample grid, positive trajectory metric, rank resolution,
conditioning guard, cross-talk guard, interval/refinement identity, and the
finite profile bounds `max_candidate_trajectories_per_cycle`,
`max_dynamic_frames_per_cycle`, `max_dynamic_response_bytes_per_frame`, and
`max_dynamic_evidence_bytes_per_cycle`. Before candidate or response
allocation, the engine computes with checked integer arithmetic:

```text
F_dynamic =
  selected_scales * selected_dynamic_ports * candidate_trajectory_count
B_dynamic =
  F_dynamic * (frame_header_max + response_sample_count *
               response_vector_width * scalar_bytes + interval_overhead)
```

It rejects a fanout or byte count above the declared maxima and records the
exact counts, sample grid, raw-byte count, and bound identity in each frame.
The response matrix and trajectory arrays are retained only as these bounded
raw evidence bytes; no response matrix, probe activation, candidate cache, or
output history enters `QiFieldState`.

The same object carries the QI-TEXT-002 pruning proof:
`exhaustive_candidate_set_sha256`, `pruned_candidate_set_sha256`,
`interval_rule_sha256`, `decision_sha256`,
`decision_equivalent_to_exhaustive=true`, and per-candidate interval
outcomes. A candidate may be pruned only when interval bounds prove the same
winner/abstention and tie ordering as exhaustive evaluation; an overlapping
or undecided interval remains in the exhaustive set. Missing response bytes,
rank/conditioning enclosures, no-peek inputs, or a non-equivalent pruning
decision fails `DYNAMIC_PORT_FRAME_INVALID`. Dynamic frames are bounded
evidence and never loaded as a later field tensor.
W11D/G11D independently recomputes the frame and its interval-pruning proof.

QI-PORT-001 `QiScatteringReceipt` (`cassi.qi-flow-scattering-receipt.v1`) records one
scale or external-port scattering balance. Required fields are
`receipt_id`, step/head and port/scale identities, incoming trajectory digest,
orientation, `W_incident`, `W_reflected`, `W_transmitted`,
`W_absorbed`, each with canonical value and uncertainty enclosure,


closure residual/bound, permeability-profile reference, and independent
replay identity. Work channels are nonnegative magnitudes in the declared
boundary units; signed characteristic-port reaction remains in the ledger.
The receipt proves

```text
W_incident = W_reflected + W_transmitted + W_absorbed + R_scattering
abs(R_scattering) <= U_scattering
```

for every declared scale and external port, including zero/null traffic
objects. An omitted channel, negative channel, scale/port mismatch, closure
outside its enclosure, or receipt that is not parented by the corresponding
step/ledger and dynamic trajectory fails `SCATTERING_RECEIPT_INVALID`.
W6T/G6T independently recomputes every scale/external-port balance.
QI-ACT-001 extends the no-peek action contract with the offline
`cassi.qi-flow-action-discriminability.v1` receipt. It records:

```text
schema = cassi.qi-flow-action-discriminability.v1
receipt_id
profile_sha256 / state_contract_sha256 / boundary_action_sha256
predecessor_head_sha256 / candidate_set_sha256
decision_horizon / observability_horizon
baseline_hold_control_sha256 / paired_world_fixture_sha256
world_a_initial_state_sha256 / world_b_initial_state_sha256
candidate_input_digests[] / action_descriptor_sha256[]
offline_observation_response_digests[]
discriminability_interval = {lower, upper}
null_interval = {lower, upper}
causal_margin_interval = {lower, upper}
uncertainty_threshold / consequence_class
no_peek_runtime_input_sha256
consumed_semantic_subhashes[]
self_sha256
```

The runtime scorer sees only the current committed field, admitted packets,
fixed body/action geometry, and zero-new-observation candidate rollouts. It
never sees either future paired-world response. The verifier computes
discriminability offline from matched worlds and requires the
uncertainty-aware causal margin to clear the registered null threshold; an
overlapping interval is `INDETERMINATE`, not a capability claim. Unequal
horizons, unmatched initial states, a future-world value in runtime inputs, a
static probe-only score, or missing null/control evidence fails
`ACTION_DISCRIMINABILITY_INVALID`. This receipt is evidence, not a candidate
cache or policy state.

The delayed consequence is separately recorded as
`cassi.qi-flow-delayed-influence.v1`:

```text
schema = cassi.qi-flow-delayed-influence.v1
receipt_id
profile_sha256 / state_contract_sha256 / boundary_action_sha256
source_port_id / target_port_id / source_packet_sha256
predecessor_head_sha256 / delayed_horizon
delay_interval / source_perturbation_interval
response_packet_digests[] / ordinary_residual_packet_digests[]
matched_null_control_sha256
effect_interval / null_interval / causal_margin_interval
uncertainty_threshold / consequence_class
consumed_semantic_subhashes[]
self_sha256
```

Only ordinary bounded residual packets carry delayed influence through the
flow; the runtime stores no credit, eligibility trace, delayed-credit ledger,
or persistent causal state. A delayed claim requires a registered source,
target, finite horizon, matched null, and an interval margin that clears the
uncertainty threshold. Missing packets, an unbounded horizon, a persistent
credit object, or a margin that overlaps null is `DELAYED_INFLUENCE_INVALID`.

QI-TEXT-003 (`W11D; G11/G11D`) records text field necessity in
`cassi.qi-flow-text-ownership.v1` and uncertainty-aware codebook separation
in `cassi.qi-flow-text-codebook-packing.v1`. The ownership receipt contains:

```text
schema = cassi.qi-flow-text-ownership.v1
receipt_id
profile_sha256 / state_contract_sha256 / boundary_action_sha256
fixed_text_codec_identity = {symbol_count = 260, codec_sha256}
canonical_wire_schema = cassi.canonical-json.v1
text_descriptor_sha256
predecessor_head_sha256 / matched_input_trajectory_sha256
field_active_run_sha256 / field_intervention_run_sha256
intervention_operator_sha256
active_result_bytes_sha256 / intervention_result_bytes_sha256
active_control_bytes_sha256 / intervention_control_bytes_sha256
field_necessity_interval / null_interval / causal_margin_interval
uncertainty_threshold / consequence_class
heldout_trajectory_set_sha256
bounded_frame_count / bounded_evidence_bytes
consumed_semantic_subhashes[]
self_sha256
```

The intervention is an offline matched trajectory/control, not a second live
state: the runtime still owns only `QiFieldState.field`, and no intervention
field, embedding, vocabulary matrix, or output cache is retained. A text
ownership claim requires active and field-intervention runs with identical
codec, input bytes, horizons, and control ordering; the lower causal margin
must clear the registered uncertainty/null threshold on held-out trajectories.
An overlapping interval is `INDETERMINATE`, not ownership. Static template
agreement, a single output winner, or an unbounded intervention fanout fails
`TEXT_OWNERSHIP_INVALID`.

The companion packing receipt has this canonical field set:

```text
schema = cassi.qi-flow-text-codebook-packing.v1
receipt_id
profile_sha256 / state_contract_sha256 / boundary_action_sha256
codec_sha256 / codec_symbol_count = 260
descriptor_registry_sha256 / projection_registry_sha256
trajectory_response_matrix_sha256 / trajectory_metric_sha256
response_rank_interval = {lower, upper}
packing_rank_interval = {lower, upper}
separation_margin_interval / null_separation_interval
uncertainty_threshold / packing_rule_sha256
symbol_assignment_fixture_sha256 / heldout_fixture_sha256
bounded_candidate_trajectory_count / bounded_evidence_bytes
consumed_semantic_subhashes[]
self_sha256
```

`response_rank_interval` is measured from the registered trajectory-response
operator and `packing_rank_interval` is the rank used by the declared packing
rule. Neither is assumed to equal 260 or the alphabet size; rank, symbol
count, and descriptor count remain separate fields. The verifier requires
uncertainty-aware separation from the null/control interval, a realizable
resolution-scaled codebook, and the declared bounded candidate/evidence
counts. A nonpositive lower separation margin, rank/alphabet conflation,
unrealizable resolution, missing held-out fixture, or a learned/adaptive
codebook fails `TEXT_CODEBOOK_PACKING_INVALID`. Both receipts are bounded
evidence and never adaptive state.

`QiNumericalCertificate` is the immutable three-layer root described above.
Its canonical payload names a complete ordered section inventory; each section
names its owning work package/gate, law/operator/profile hashes,
dependency-section hashes, offline precision/subdivision/remainder records,
online guard names and thresholds, and independent replay input/result hashes.
W3N establishes the root and intrinsic-W3 section. W4, W4R, W5V, and W6T add
their completed composition, retention/barrier, conversion, and link/scattering
evidence only as immutable `cassi.qi-flow-certificate-extension.v1` objects
whose parent digest and complete cumulative inventory are retained. No package
may rewrite a root or extension. Missing, placeholder, duplicate, reordered,
or stale required sections, a parent mutation, or a missing final identity
fails closed; the verifier checks every interval/guard against the profile and
does not accept a runtime scalar or receipt builder as a substitute for the
offline or replay layers.

QI-LINEAGE-001 `QiStateLineageForkReceipt`
(`cassi.qi-flow-state-lineage-fork-receipt.v1`) contains
old/new `state_consuming_subhashes`, parent/child canonical state-object
hashes and byte counts, old/new source and clock identities, fresh
protocol/world/episode identities, reset reason, operator identity, and
`self_sha256`. The child state-object bytes must equal the parent bytes
exactly; the receipt is not a state conversion record. The operation and its
fail-closed conditions are defined in the world-loop section and are
independently verified before the child envelope is published.
W12L/G12L independently verifies the byte copy, complete subhash comparison,
and protocol/world reset.

QI-TXN-001 `QiTransactionModelReceipt`
(`cassi.qi-flow-transaction-model-receipt.v1`) contains the concrete bounded
two-caller model evidence:

```text
schema = cassi.qi-flow-transaction-model-receipt.v1
receipt_id
profile_sha256 / contract_root_sha256 / world_protocol_sha256 /
session_storage_sha256 / security_evidence_sha256
caller_count = 2
identity_token_set[]
state_space_bound / transition_bound / visited_state_count
lock_epoch_bound / lock_epoch_trace[]
envelope_identity_trace[] / journal_identity_trace[]
transition_set_sha256
initial_frontier_sha256 / final_frontier_sha256
retry_horizon / reconnect_horizon / outbox_horizon
covered_interleavings[] =
  {caller_arrival, lock, Commit-A, send, apply, resolve,
   Commit-B, ack, efference, crash, reconnect, replay, seal}
linearization_orders[] = [caller_1, caller_2] | [caller_2, caller_1]
duplicate_outcome_table[] / conflict_outcome_table[]
invariant_names[] / invariant_results[]
indeterminate_world_effect_receipt_schema = cassi.qi-flow-indeterminate-world-effect.v1
self_sha256
```

Only an independent explicit-state explorer may produce an accepting result;
runtime transaction flags cannot self-certify it. The receipt must include the
two-caller lock/epoch, envelope, journal, Commit-B CAS, exact
duplicate/conflict, and unresolved-world interleavings defined in the
world-loop section. Missing crash boundaries, stale-reader cases, unbounded
history, omitted response visibility, absent seal semantics, or a
non-exhaustive frontier fails `TRANSACTION_MODEL_INCOMPLETE`.
W12M/G12M independently verifies the bounded transition frontier and every
required invariant.

When a terminal world result cannot be authenticated, the transaction graph
adds the immutable `cassi.qi-flow-indeterminate-world-effect.v1` object:

```text
schema = cassi.qi-flow-indeterminate-world-effect.v1
receipt_id
profile_sha256 / contract_root_sha256 / world_id / episode_id / session_id
cycle_number / from_tick / to_tick / lock_epoch
envelope_identity = {commit_a_head_sha256, envelope_sha256}
journal_identity = {journal_root_sha256, journal_head_sha256, committed_cursor}
intent_identity = {idempotency_key, canonical_intent_sha256, bounded_intent_bytes}
resolution_attempts[] = {
  reconnect_epoch, request_id, response_sha256, auth_status,
  observed_status
}
terminal_status = indeterminate
seal_reason / lineage_status = indeterminate_sealed
disposition = new-session-only
consumed_semantic_subhashes[]
self_sha256
```

The indeterminate object is indexed from the last valid envelope and retains
the exact unresolved scope without fabricating an acknowledgement. It is
immutable evidence, not a cleared outbox, fallback result, reset state, or
second field. An exact authenticated resolution before sealing may complete
Commit B; any missing, malformed, stale, or conflicting result seals the
lineage and makes every continuation fail `WORLD_EFFECT_INDETERMINATE`.


QI-EVID-001 adapter-off evidence object
(`cassi.qi-flow-adapter-off-evidence.v1`) contains the baseline and candidate
run identities, disabled-adapter manifest, exact deterministic artifact
entries `{schema,path,byte_count,sha256,parent_subhashes}`, process/socket/
allocation observations, and any volatile projection entries. Every
deterministic entry requires exact byte and digest equality. A projection is
legal only when the schema registry marks that exact field path
`volatile=true` and names one canonical projection plus a mutation-control
fixture; raw bytes remain retained and hashed. The registry forbids
projections of `QiFieldState`, checkpoints, operators, profile/subhashes,
physics/work/ledger/decision/action/response bytes, or protocol identities.
Unknown volatility, a missing raw artifact, failed mutation control, or
numeric/tolerance-only equality fails `ADAPTER_OFF_EVIDENCE_INVALID`.
G13D independently compares the manifest and mutation controls; it cannot
delegate equality to the adapter or runtime.

### Causal graph

Each committed decision enters exactly one of two branch types:

```text
profile + backend + predecessor checkpoint/head
  + admitted packets + terminal prior-action ack/efference (if any)
    -> remap -> core flow step/ledger -> predicted boundary/port trajectories
    -> QiDynamicPortFrame (rank/conditioning/cross-talk)
    -> QiScatteringReceipt (incident/reflected/transmitted/absorbed work)
    -> matched directional counterfactual -> field decision

action branch:
  field decision -> successor checkpoint + durable QiWorldTickIntent [commit A]
    -> exact idempotent intent bytes -> terminal world acknowledgement
    -> acknowledgement-consumption checkpoint [commit B]
    -> action/world result + live ownership receipt
    -> unresolved/unauthenticated result -> indeterminate-world-effect seal

text branch:
  field decision -> characteristic-port reaction
    -> QiDynamicPortFrame + QiScatteringReceipt
    -> text-ownership necessity + text-codebook-packing evidence
    -> staged immutable text-event/result/turn/response object chain
    -> successor checkpoint + one session envelope publishing every hash [commit A]
    -> stored HTTP/terminal bytes + live ownership receipt

lineage branch:
  validated parent state object + equal state-consuming subhashes
    -> exact canonical state copy + fresh protocol/world session
    -> QiStateLineageForkReceipt
verification branch:
  capacity/openness/action/delayed/forgetting evidence
    -> `QiCapacityLadder` / sensory-openness / discriminability /
       delayed-influence / forgetting receipts
  bounded Commit-A/Commit-B exploration -> QiTransactionModelReceipt
  high-precision bounds + online guards + independent replay
    -> QiNumericalCertificate -> immutable certificate-extension chain
    -> adapter-off evidence
```

The checkpoint and tick intent in Commit A exist before external I/O. The
session lock is released before sending the exact durable intent bytes. After a
terminal acknowledgement is obtained or replayed, the lock is reacquired and
Commit B persists the acknowledgement and its one-time consumption marker. A
missing, malformed, unauthenticated, stale, or conflicting terminal result
cannot be cleared: before the resolution horizon it may be resolved only by
the exact stored scope, and after that it appends
`cassi.qi-flow-indeterminate-world-effect.v1` and seals the lineage with no
successor.

`QiDynamicPortFrame` and `QiScatteringReceipt` are mandatory graph nodes for
every declared dynamic/external port and scale in the selected geometry mode.
Before clone or response allocation, the graph builder checks
`F_dynamic`/`B_dynamic` against the profile's candidate/frame/response byte
maxima. Their raw trajectory/work payloads are retained separately under the
declared bound, and their hashes are published in the same Commit-A envelope
as the step/ledger identity. Neither artifact may be reconstructed from a
later response or used as unhashed controller state. The graph verifier
follows both edges and checks dynamic rank/conditioning/cross-talk, scattering
work closure, and exact fanout/byte counts before it accepts the decision
branch.

Every graph edge carries the exact predecessor hash. A failure receipt names
the last committed head and every rejected candidate identity while retaining
the prior state.

No committed branch has an orphan action, prediction, correction, output
event, or checkpoint.

An explicit retention reset is a separately typed administrative transition
edge between two committed step heads. It is neither a text nor an action
decision branch and cannot be created by recovery or ordinary stepping.

### Per-step ledger

`QiFlowLedger` records sign and units for:

- `E_wave`, `U_composition`, `E_links`, and, for topological retention, `U_topo` before/after;
- the topological-retention barrier margin, winding sheet, and any timed phase-slip work;
- spatial divergence contribution;
- sensory source work per modality;
- residual-return work;
- the field-derived permeability value/interval per port and its admitted and
  reflected work with the permeability closure residual;
- dynamic-port trajectory-response rank bounds, conditioning interval,
  cross-talk bound, finite-horizon no-peek inputs, and any exact interval
  reaction-pruning decision-equivalence result;
- nonnegative scattering `W_incident`, `W_reflected`, `W_transmitted`, and
  `W_absorbed` channels at every selected scale/external port plus their
  closure residual;
- signed characteristic-port reaction work for text and motor proposals,
  positive into the field and never mislabeled an applied world effect;
- the exact nonnegative damping dissipation;
- local nonlinear, reciprocal composition, scale-link, and retention coordinate
  work plus their potential deltas and conservative closure residuals;
- Yang/Yin density transfer and the single full conversion-stage energy delta;
- body remap norm/energy/diffusion work;
- candidate pre-check, committed-state values, and every rejected
  bound/saturation count;
- absolute and normalized unexplained residual.

The global sign convention is:

\[
\Delta\!\left(
E_{\mathrm{wave}}
+U_{\mathrm{composition}}
+E_{\mathrm{links}}
+\mathbf1_{\{\mathrm{retention.mode}=\mathrm{topological\text{-}v1}\}}U_{\mathrm{topo}}
\right)
=
W_{\mathrm{sensory}}
+W_{\mathrm{residual}}
+W_{\mathrm{remap}}
+W_{\mathrm{port\ reaction}}
+W_{\mathrm{conversion}}
-Q_{\mathrm{damping}}
+R_{\mathrm{unexplained}}.
\]
This equation applies to one positive-duration field step and never spans a
retention reset. The zero-clock reset edge instead closes
`Delta_H=W_reset` and records
`Delta_Q_Z,reset=Q_Z,after-Q_Z,before` as an external controller charge impulse.
The cumulative session ledger includes both signed quantities exactly once
between the adjacent step heads; no reset work or phase jump may appear in
`R_unexplained`.

For any passive text or actuator candidate,
`W_port reaction=-sum_j W_out,j<=0`; the separately stored
`Q_damping>=0` appears exactly once with the minus sign above. The canonical
profile rejects a net-inward egress candidate; any later sensed physical return
arrives as a separately authenticated inbound packet/work row. Proposal,
command, acknowledgement, and applied-efference metadata have zero field work
by themselves.

Internal nonlinear, reciprocal composition, reciprocal scale, and topological-retention
retention force work cancel against their explicitly included potential
deltas. Periodic integrated spatial divergence is zero; local divergence
remains measured. Accepted nominal results have zero
clip/rescale/projection count and `R_unexplained` within the profile's
independently verified absolute and normalized tolerance.

### Causal ownership receipt

`QiFlowDecisionReceipt` records:

- live state/flow/current hashes;
- identical boundary/profile/candidate inputs for live and control arms;
- the exact current reversal or scale/body-flow perturbation;
- matched energy and admissibility residual;
- live/control predicted-boundary hashes and metrics;
- live/control committed action or text event;
- whether the expected directional relation changed;
- boundary/world acknowledgement;
- decision counts owned by Qi versus left to an external system.

The receipt fails if the perturbation does not affect the relevant committed
prediction/action, if energy matching is outside tolerance, if a candidate arm
sees hidden sensory data, or if a static template/probe winner alone explains
the result.

QI-RET-001 is verified from the topological-retention Hamiltonian/topology receipt installed
by W4R after W4 and before W5; QI-RET-002 requires the within-sector analog
acquisition and topological consolidation tiers to remain distinct in the
same field state; and QI-RET-003 requires independently measured topology
algebra, reachable basin capacity, saturation, overwrite, and recovery. A
final sector label without those work/barrier and reachable-basin artifacts is
not a retention proof.

The live provider reports a `QiLiveOwnershipReceipt` built without importing or
loading `cassi_qwen_displacement.py` or a baseline artifact. It contains:

```text
qwen_processes = 0
qwen_modules_loaded = 0
qwen_requests = 0
qwen_weight_bytes_touched = 0
qwen_kv_bytes = 0
qwen_lm_head_rows = 0
qwen_sampler_decisions = 0
field_owned_decisions
field_abstentions
profile/step/checkpoint/backend identities
```

G12E does not accept those counters as self-evidence. The target
`run_cassi_qi_process_evidence.py` starts the provider as a child in a named
Windows Job object and records:

- an ETW file/image/process/network trace under the fixed
  `cassi-qi-flow-etw.wprp` profile from before import through shutdown;
- `CreateToolhelp32Snapshot` process/module inventories, executable paths,
  command lines, process-creation IDs, and the provider's canonical
  `sys.modules` manifest;
- `GetExtendedTcpTable` socket ownership before, during, and after the request;
- file-read byte counts grouped by canonical path and specifically by the
  manifest's pinned Qwen/GGUF/llama/model-weight path set;
- Job peak private/working-set memory and the runtime's independently
  recomputable field/scratch allocation formula.

The raw `.etl`, module/socket/process JSON, canonical path allowlist, and parser
result are retained and hashed. `verify_cassi_qi_process_evidence.py`, not the
provider, derives Qwen processes/modules/requests/weight bytes and unexplained
native-state upper bounds. If ETW or required Win32 observation is unavailable
or incomplete, G12E is `BLOCKED`; a runtime zero cannot replace it.

`run_cassi_field_only_displacement.py` is the separate offline evidence command
that combines this live receipt with the immutable pinned baseline receipt to
estimate native dynamic-state bytes, operations, output rows, and weight bytes
displaced. The canonical terminal/provider does not require that baseline file
to import, boot, generate, save, restore, or report health.

### Session/checkpoint integrity

`CassiQiSessionStore` v3 envelope contains these exact canonical-order fields:

```text
schema
session_id
contract_root_sha256
profile_sha256
state_contract_sha256
boundary_action_sha256
world_protocol_sha256
session_storage_sha256
backend_capacity_sha256
backend_semantics_id
clock_sha256
source_identity_sha256
source_replay_contract_sha256
lock_epoch
envelope_sequence
logical_tick
logical_time = {n,d}
cycle_number
request_high_watermark
predecessor_checkpoint_sha256 | null
receipt_head_sha256
state_sha256
state_object_sha256
body_frame_id
prediction_context_sha256 | null
ingress_journal_head_sha256
ingress_committed_cursor_sha256
watermark_sha256
source_frontiers = [{source_epoch, source_stream_id, descriptor_sha256,
                     capture_end={n,d}, source_sequence, frame_sha256}]
proposal_sha256
port_reaction_sha256
scale_geometry_mode
dynamic_port_frame_sha256[] sorted by (step,port_id,frame_id)
scattering_receipt_sha256[] sorted by (step,port_id,scale_id,receipt_id)
capacity_ladder_sha256 | null
sensory_openness_sha256[] sorted by (step,port_id,scale_id,receipt_id)
action_discriminability_sha256[] sorted by (step,candidate_set_sha256,receipt_id)
delayed_influence_sha256[] sorted by (step,source_port_id,target_port_id,receipt_id)
forgetting_sha256[] sorted by (trajectory_id,receipt_id)
text_ownership_sha256 | null
text_codebook_packing_sha256 | null
experience_plan_sha256 | null
numerical_certificate_sha256 | null
numerical_certificate_extension_sha256[] sorted by chain_ordinal
lineage_fork_receipt_sha256 | null
transaction_model_receipt_sha256 | null
indeterminate_world_effect_sha256 | null
lineage_status = open | indeterminate_sealed
last_terminal_tick_ack_sha256 | null
pending_applied_efference_sha256 | null
last_consumed_applied_efference_sha256 | null
object_index = [{schema, sha256, byte_count}] sorted by (schema, sha256)
request_records = [{sequence, idempotency_key, method, path,
                    request_sha256, stream, response_record_sha256,
                    retention_state}]
tick_outbox = null | {world_id, episode_id, profile_sha256, session_id,
                      cycle_number, committed_prior_head_sha256, from_tick,
                      to_tick, idempotency_key, intent_bytes, canonical_intent_sha256,
                      proposal_sha256, port_reaction_sha256, action_sha256,
                      action_scope_sha256, lock_epoch,
                      status = pending | terminal | sealed,
                      attempt_count, tick_ack_record_sha256,
                      indeterminate_world_effect_sha256,
                      applied_efference_sha256, ack_consumed}
bounded_transcript_display_bytes
bounded_transcript_display_sha256
schema_limit_identity
self_sha256

```

`cycle_number` is independent of HTTP request sequence and increments exactly
once when Commit A publishes a successor decision. An action Commit A also
publishes its complete tick intent/outbox; a text Commit A publishes its staged
event/result/turn/response chain. Content-addressed objects may be flushed
before the envelope, but the atomically replaced session envelope is their only
publication point; a crash can leave only unreachable cleanup candidates, not
a partially committed branch. The intent, embedded outbox record, and terminal
acknowledgement duplicate the complete idempotency scope so a world port can
resolve replay without inspecting a mutable session file.
The envelope's `contract_root_sha256` is resolved and verified before any of
these fields are interpreted; profile, schema, projection, and default
omission rules therefore cannot vary between restart implementations.

For the selected `scale_geometry_mode`, every declared dynamic/external port
and scale appends its `QiDynamicPortFrame` and `QiScatteringReceipt` identity
to these sorted envelope arrays before Commit A. Capacity, sensory-openness,
action-discriminability, delayed-influence, forgetting, text-ownership, and
text-codebook-packing receipts are likewise indexed before publication when
their exercise is selected. A missing frame, omitted scattering channel,
duplicate identity, post-commit insertion, or `F_dynamic`/`B_dynamic` bound
overflow invalidates the envelope. `experience_plan_sha256` and
`numerical_certificate_sha256` point to immutable run contracts when the
session participates in their exercise; extension identities preserve the
parent chain. A lineage fork points to its receipt only in the fresh child
session, and `transaction_model_receipt_sha256` is an independent proof
reference rather than runtime transaction state. If a terminal world result
cannot be authenticated, `indeterminate_world_effect_sha256` is published,
`tick_outbox.status=sealed`, and `lineage_status=indeterminate_sealed`; no
successor or continuation envelope is valid.


`source_frontiers` is sorted by
`(source_epoch,source_stream_id,descriptor_sha256)`, has no duplicate scope,
and must hash to `watermark_sha256`; its greatest contiguous entries must also
equal `ingress_committed_cursor_sha256` and be reachable from the immutable
ingress journal head. `proposal_sha256` and `port_reaction_sha256` always name
objects, including registered hold/abstention zero-work objects, rather than
using absence to erase a decision. A terminal tick acknowledgement and its
derived applied efference remain distinct objects. Commit B installs the latter
as `pending_applied_efference_sha256`; exactly one later evolution consumes it
as a timed source and moves that identity to
`last_consumed_applied_efference_sha256`.

`cassi.qi-flow-response-record.v1` contains the exact canonical nonstream body
bytes, ordered SSE frame bytes, each frame hash/ordinal, aggregate hash, finish
reason, content/event identities, and byte counts. The profile fixes maximum
index entries, retained requests, per-response bytes, aggregate response bytes,
tick-intent bytes, acknowledgement retention, and total object bytes. An index
or record that is unsorted, duplicated, oversized, absent, or references an
unindexed object fails before state load. Transcript metadata and all
request/response/tick records are bounded non-adaptive protocol/audit material;
restore never senses or scores them.


Transcript metadata is non-adaptive audit/display material. Restore never
replays it, uses it to choose a candidate, or derives a boundary suffix from
it. The field state, receipt head, durable tick intent, and consumed tick
acknowledgement marker are authoritative.

The store uses cross-process locking, bounded lock lifecycle, same-directory
temporary write, flush/sync, atomic replace, and post-write reopen validation.
No session lock is held across world network I/O. Corruption, partial write,
wrong session, mismatched consumed semantic subhash, wrong backend semantics,
wrong state hash, wrong self-hash, nonfinite/over-budget state, broken
predecessor chain, or any differing composite profile fails closed with the
registered profile-mismatch error. The store never resets, rebinds a
trajectory, imports v2, converts state automatically, or selects the newest
file heuristically.

### Independent verifier and artifact tree

Every validation, release, evidence, or verifier command that reads or writes a
canonical run tree takes an explicit `--run-id`. Every verifier additionally
takes `--root _diag/cassi-qi-flow` and run-relative `--manifest`, `--profile`,
and `--board` names as applicable. Those names must resolve to the exact
indexed objects below the selected canonical run root; absolute paths, `..`,
reparse escapes, external files, and hash-mismatched copies are rejected before
decode. Terminal/provider launch binds session/config identity; historical
bootstrap/rollback binds its immutable historical manifest; Godot binds the
authenticated adapter profile or unchanged battery contract. Those deliberate
non-run-tree commands do not accept a fictitious run ID. The sole
manifest/profile/schema authority is `run-spec/`, never a gate-local copy.

```text
_diag/cassi-qi-flow/<run_id>/
  index.json
  run-spec/
    manifest.json
    profile.json
    semantic-subhashes.json
    profile-projections.json
    schema-registry.json
    dependency-manifest.json
    contract-root.json
    oracle-fixtures/
    source-identity.json
    raw-retention-policy.json
    capability-matrix.json
    toolchain.json
    command-inputs.json
  objects/
  inputs/raw/
  states/raw/
  packets/raw/
  field-experience/
  capacity/
  sensory-openness/
  action-discriminability/
  delayed-influence/
  forgetting/
  text-ownership/
  text-codebook-packing/
  dynamic-port-frames/
  scattering/
  numerical-certificates/
  lineage/
  transaction-models/
  adapter-off/
  remaps/
  ledgers/
  steps/
  stage-receipts/
  space-scale/
  hodge/
  retention/
  topology/
  decisions/
  actions/
  acknowledgements/
  checkpoints/
  text-events/
  text-results/
  world-wire/frames/
  world/observations/
  provider/http/
  process-evidence/raw/
  backend/
  security/
  gates/g00-manifest/ ... gates/g15a-release-candidate/
  gates/g15b-release/
    readme-verification.json
  candidate/
  provisional-release-board.json
  provisional-release-result.json
  release-board.json
  release-result.json
```

Validation drivers may create only their registered subdirectory and immutable
content-addressed objects; `index.json` maps every check/schema/root digest and
is atomically replaced under the same commit rule. Fixed paths outside
`<run_id>` are invalid evidence.

Generated artifacts remain gitignored and never source. Validation runs create
the run root with an owner-and-SYSTEM-only Windows DACL, disabled inherited
access, and a manifest-declared aggregate/raw-per-modality byte quota before
raw capture. Live non-validation runs retain hashes/scalars only. Candidate raw
data is retained through final board verification; removal requires the
separately invoked operator-approved cleanup command, which verifies the board
and emits `cassi.qi-flow-artifact-cleanup.v1`. No artifact is uploaded or
disclosed by the runtime.

`verify_cassi_qi_flow.py` has no import edge to runtime profile constructors,
receipt builders, metrics, action scorers, text engines, backends, or world
adapters. It first invokes a separately maintained bootstrap oracle with the
source-pinned `cassi.qi-flow-contract-root-bootstrap.v1` bytes and fixtures to
open and authenticate the retained `cassi.qi-flow-contract-root.v1`. Only
after that root succeeds does it invoke the separately maintained minimal
descendant canonical-codec/registry oracle (with its own source identity and
fixtures) on retained canonical bytes, indexed schema/projection registry
bytes, and adversarial vectors. The oracles independently implement bootstrap
framing, descendant framing, canonical JSON/finite-bit encoding,
required-default presence, schema bounds, ordered parent/subhash lists, and
object self-hashes. The verifier consumes their byte/result output; it does
not import or call runtime builders.

Every verifier run records distinct
`oracle_source_identity_sha256`, `oracle_toolchain_identity_sha256`, and
`oracle_fixture_set_sha256` beside the runtime implementation identity. Those
identities are not derived from, or overwritten by, the runtime package; a
missing/distinctness failure blocks verification. The
`oracle-fixtures/` set is an adversarial golden cross-implementation corpus:
accepted vectors must be byte-identical between runtime and oracle, while
rejected vectors must agree on the named rejection class.


The oracle fixture set is adversarial and cross-implementation rather than a
copy of runtime examples. Each vector records
`fixture_id`, input bytes, expected accept/reject class, runtime
implementation identity and bytes/hash, oracle identity and bytes/hash, and
the fixture digest. Accepted canonical objects must match byte-for-byte;
rejected objects must produce the same named rejection class, not merely both
raise an exception. The set includes duplicate keys; malformed UTF-8 and
unpaired surrogates; Unicode normalization lookalikes; escape, slash, and
newline boundaries; integer/rational and finite-bit/negative-zero edges;
array ordering; length-prefix and raw-tensor byte limits; omitted, duplicate,
unknown, or reordered defaults; unknown registry/schema/projection entries;
wrong contract-root component digests; reordered semantic parents; self-hash
cycles; mutated certificate parents; over-fanout dynamic frames; candidate
byte-budget overflow; stale lock/envelope/journal epochs; duplicate and
conflicting Commit-B acknowledgements; and indeterminate-world seals. The
oracle never imports a runtime builder to manufacture a fixture.
From retained raw pre/post state bytes, packets, actions, acknowledgements, and
canonical profile it independently:


1. asks the separate oracle to validate the contract root, canonical codec,
   schema/projection registry, fully materialized defaults, every semantic
   parent list, self-hash, raw payload hash, byte bound, and receipt-graph edge;
2. reconstructs `Y/I/D/C` under the induced metric;
3. recomputes geometry, the explicit `scale_geometry_mode` comparison, DFT
   signs, transforms, and adjoints;
4. reproduces operator substeps and work terms;
5. recomputes currents, fluxes, continuity, conversion using physical
   `epsilon_memory_time`, and link closure;
6. validates each `QiBoundaryPermeabilityProfile` field-derived operator,
   admitted/reflected/absorbed work enclosure, passive closure, and every
   mandatory-port `cassi.qi-flow-sensory-openness.v1` positive-incident and
   recovery arm against its incident-work-normalized threshold;
7. validates `QiFieldExperiencePlan` byte/world streams, clock, budgets,
   whole-episode splits, washout, stopping, controls, and checkpoint choice;
   recomputes QI-CAP-001's exact `advance()` capacity ladder and
   QI-RET-003's dynamical reachability/forgetting trajectories, with reset
   excluded as acquisition and all geometric/reachable/observable/usable/
   retained/reusable levels distinguished;
8. validates finite-horizon no-peek candidate inputs and matched
   counterfactuals, then independently recomputes
   `cassi.qi-flow-action-discriminability.v1` and
   `cassi.qi-flow-delayed-influence.v1` paired-world intervals, null controls,
   and uncertainty-thresholded causal margins without importing world results
   into runtime candidate evaluation;
9. recomputes every `QiDynamicPortFrame` trajectory-response rank,
   conditioning, cross-talk, QI-TEXT-002 interval-pruning
   decision-equivalence result, and exact `F_dynamic`/`B_dynamic` fanout and
   byte bounds; validates QI-TEXT-003 text-ownership intervention evidence
   and text-codebook-packing separation/rank intervals;
10. recomputes every `QiScatteringReceipt` incident/reflected/transmitted/
    absorbed work channel and closure;
11. verifies the immutable `QiNumericalCertificate` root and every
    `cassi.qi-flow-certificate-extension.v1` parent digest, complete cumulative
    section inventory, no-parent-mutation rule, offline enclosure metadata,
    online scalar guards, independent replay, and final certificate identity
    as separate evidence layers;
12. reconstructs `QiStateLineageForkReceipt`, byte-compares copied state,
    compares every state-consuming subhash, and verifies fresh protocol/world
    continuity;
13. replays the bounded explicit-state two-caller Commit-A/Commit-B transaction
    model, including lock epochs, envelope/journal identities, exact CAS
    interleavings, duplicate/conflict outcomes, outbox, acknowledgement,
    efference, crash, reconnect, replay, response-visibility, and
    indeterminate-world seal paths;
14. verifies action idempotency and actual world application, refusing to
    convert unknown external truth into an acknowledgement or continuation;
15. verifies checkpoint exact continuation and replay;
16. compares QI-EVID-001 adapter-off deterministic artifacts byte-for-byte and
    executes every registered volatile-projection mutation control;
17. validates the live import/process Qwen-zero receipt;
18. emits the manifest-declared `PASS/FAIL/BLOCKED/NOT_RUN` engineering status.

A runtime-generated metric never verifies itself.

### External mandatory capability matrix

The endpoint contract, not the implementation under review, generates
`run-spec/capability-matrix.json`. Each row fixes capability ID, required or
optional status, owning work package/gate, profile and fixture identities,
required treatment/control arms, evidence schemas, hardware/authorization
prerequisites, and release consequence. Required rows include topological-retention
metastable/topological retention, intrinsic and endpoint capacity, passive text
and motor egress, proposal/applied-efference separation, reference-world and
CassiCosmos closure, provider/terminal restart, Qwen-zero process evidence,
backend parity, resource/security limits, and clean cutover.

The candidate can report `PASS`, `FAIL`, `BLOCKED`, or `NOT_RUN`; it cannot
remove a row, mark a required row optional, narrow its controls, or claim the
endpoint by under-declaring capability. W16A independently compares the matrix
to this plan before reading candidate results; W16B verifies that the final
documentation reports the unchanged matrix.

