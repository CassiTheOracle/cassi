# Architecture, profiles, schemas, and cutover

> CassiFI implementation plan, Part 3. [Previous](./02-retention-capacity-and-cognition.md) · [Index](../README.md) · [Next](./04-execution-contract.md)

## Implementation phases

The implementation is organized as a mandatory dependency sequence:

1. current-law audit and truthful diagnostics;
2. versioned flow-profile and checkpoint identity;
3. spatial steering-field transport;
4. coherence-carrier activation and steering coupling;
5. explicit Yang/Yin conversion in the cycle;
6. reciprocal continuous scale coupling;
7. force-based multimodal boundaries;
8. body-frame remapping and residual return;
9. field-owned attention, gaze, and motor emission;
10. metastable memory and recall;
11. trajectory-based text input and emission;
12. terminal and provider cutover;
13. embodied world-loop integration;
14. CPU/ROCm parity and performance hardening;
15. complete validation and release cutover.

The detailed work packages below assign every phase to files and symbols,
define its inputs, mutations, schemas, dependencies, caller migrations,
failure behavior, artifacts, validation checks, and release stop conditions.

## Target source architecture and ownership

The endpoint is one integrated runtime, not a collection of probes. The source
layout below assigns one owner to every lasting concern and keeps adaptive state
out of boundary, serving, and world modules.

| Path | Ownership after cutover | Required public surface |
|---|---|---|
| `cassi_qi_profile.py` | Strict versioned profile, coordinate and numerical interfaces | `QiContractRoot`, `QiFlowProfile`, `QiSpatialProfile`, `QiScaleGeometryProfile`, `QiConversionProfile`, `QiExperienceProfile`, `QiBoundaryPermeabilityProfile`, `QiScaleCouplingProfile`, `QiRetentionProfile`, `QiTopologyProfile`, `QiStageSpec`, `QiExecutionProfile`, `QiStabilityEnvelope`, boundary/body/action profiles, canonical serialization, materialized-default validation, semantic projection registry, and `profile_sha256` |
| `cassi_qi_clock.py` | Exact rational causal clock, watermark ordering, antialias cadence, and replay frontiers | `QiClockTime`, `QiCausalClock`, `QiWatermark`, reduced-rational arithmetic, sequence/gap validation |
| `cassi-qi-flow.json` | Current release full-system profile instance | complete non-placeholder `cassi.qi-flow-profile.v1` values and hashes |
| `cassi-qi-flow-development.json` | W1-owned complete small engineering profile used by G0-G1 and focused development only | non-placeholder `cassi.qi-flow-profile.v1`; distinct identity and run roots; never a release profile |
| `cassi_qi_field.py` | Sole adaptive tensor, derived Yang/Yin coordinates, fixed operators, split integrator, diagnostics, checkpoint bytes | `QiFieldState`, `QiFieldController`, `QiFlowLedger`, `QiFlowStep`, `QiTopologicalRetentionLaw`, derived topology/Hodge operators, exact state dump/load |
| `cassi_qi_boundary.py` | Fixed modality descriptors and transient boundary packets | `QiBoundaryDescriptor`, `QiBoundaryPacket`, optical/audio/text/proprioceptive/motor descriptors, `QiBoundaryPermeabilityProfile` evaluation, validation, forward/adjoint transforms |
| `cassi_qi_body.py` | Stateless body registration, spectral translation/rotation, efference transforms | `QiBodyFrameDescriptor`, `QiBodyPose`, `QiBodyMotion`, `QiGazeRemapDescriptor`, forward/inverse/adjoint receipts |
| `cassi_qi_world.py` | World-port protocol, deterministic reference world, loopback transport, tick acknowledgements, replay rules | `QiWorldPort`, `QiWorldTransportServer`, `QiWorldObservation`, `QiActionCommand`, `QiWorldTickIntent`, `QiWorldTickAck`, `DeterministicQiWorld` |
| `../CassiCosmos/scripts/cassi_qi_world_adapter.gd`, `../CassiCosmos/scenes/qi_world_adapter.tscn`, `../CassiCosmos/scenes/verify_qi_world_adapter.tscn` | Default-off real embodied world adapter under a separate cross-repo ownership brief | raw viewport/audio/pose packets, bounded camera/body actions, idempotent acknowledgements, world identity, focused windowed verification |
| `test_cassi_qi_adapter_off_identity.py`, `verify_cassi_qi_adapter_off_identity.py` | W13C-owned independent adapter-off equality test/verifier | byte-identity comparison of frozen pre-adapter and adapter-disabled receipts, traces, anchors, battery outputs, wire bytes, and declared volatile projection; read-only, no field/world mutation |
| `cassi_qi_flow.py` | Runtime orchestration across timed packets, field evolution, prediction, action, acknowledgement, atomic receipt assembly | `CassiQiFlowEngine`, `QiFlowSession`, `QiPreparedStage`, `QiFlowDecision`, `QiFlowFailure`, and the one transaction FSM |
| `cassi_qi_backend.py` | One Torch CPU/ROCm execution contract, fixed caches, batching, synchronization | `QiFlowBackend`, `TorchFlowBackend`, `QiRuntimeConfig`, `QiCapacityProfile`, backend receipts |
| `cassi_qi_receipts.py` | Domain-separated canonical hashing and all flow receipt schemas | stage/stability/packet/action/remap/ledger/step/decision/failure/session/backend/space-scale/Hodge/retention/topology/displacement builders plus contract-root, capacity-ladder, sensory-openness, scale-geometry, scattering, dynamic-port, action-discriminability, delayed-influence, forgetting, text-ownership, text-codebook-packing, numerical-certificate/extension, lineage-fork, transaction-model, indeterminate-world-effect, and adapter-off evidence builders/validators |
| `verify_cassi_qi_flow.py` | Independent artifact verifier with no live runtime mutation | separate minimal canonical-codec/registry oracle, adversarial cross-implementation fixtures, receipt graph, work closure, replay, ownership, capacity, openness, scale-geometry, dynamic-port, action discriminability/delayed influence, scattering, numerical-certificate chains, forgetting, lineage, transaction-model/indeterminate-effect, adapter-off, and release-readiness checks |
| `verify_cassi_qi_requirements_registry.py` | W16B-owned read-only documentation/registry verifier | exact QI-ID uniqueness, owner/package/gate/artifact/failure columns, indexed-document coverage, package/gate inventory, and dependency-manifest consistency |
| `benchmark_cassi_qi_flow.py` / `profile_cassi_qi_flow.py` | Performance and allocation evidence | capacity-profile benchmarks and profiler receipts |
| `run_cassi_qi_artifact_cleanup.py` | W12A-owned digest-exact artifact planning/quarantine/purge operator | plan/apply modes, root/index confinement, interactive approval boundary, cleanup receipts |
| `cassi_field_language.py` | Fixed UTF-8/control port implemented as a flow boundary adapter, trajectory-based output, fixture-local event/result chain | `CassiFieldTextCodec`, `CassiQiTextEngine`, flow text receipts; canonical v3 session persistence remains solely in `cassi_qi_flow.py`/W12A |
| `cassi_conscious_chat.py` | Terminal composition root over the unified flow engine | terminal config, session lifecycle, field-only interaction |
| `run_cassi_conscious_chat.py` | CLI argument parsing and explicit profile selection only | no field law or state mutation |
| `cassi_persistent_provider.py` | Loopback OpenAI-compatible service composition root | health, models, completion/streaming, session locking, receipt exposure |
| `cassi_qwen_displacement.py` | Qwen-zero ownership/displacement receipt builder | flow-profile and flow-chain evidence only; never a live inference dependency |
| `run_cassi_field_only_displacement.py` | Independent runtime receipt driver | full chain, restart, counterfactual, and zero-Qwen evidence |
| `README.md` | User-visible current runtime map and commands | reflects the released flow path without claiming unimplemented embodiment |

`cassi_qi_field.py` owns all physics and is the only module permitted to mutate
`QiFieldState.field`. `cassi_qi_boundary.py` can construct a transient drive but
cannot retain it or modify state. `cassi_qi_world.py` can expose observations
and acknowledge actions but cannot inspect the field tensor. `cassi_qi_flow.py`
is the sole authorized coordinator: it passes validated transient packets to the
controller and records hashes/scalars, never a second adaptive cache.

The existing `cassi_conscious_*` files **except the canonical
`cassi_conscious_chat.py`**, plus `cassi_organism*`, `cassi_world_model*`,
`cassi_qi_kv.py`, `cassi_field_daemon.py`, old F-stage providers, and `_diag`
probes are not silently made part of the new live graph.
`cassi_conscious_chat.py` and `run_cassi_conscious_chat.py` are explicitly
canonical callers and must migrate in place. Before the core API is removed,
every other importer is classified once:

1. **Canonical flow caller** — migrate it to the new profile, packet, and
   cycle APIs.
2. **Flow experiment** — migrate it to the new APIs and update its claim and
   receipt.
3. **Historical/offline experiment** — pin it to an explicitly named frozen
   legacy source boundary that is unreachable from the terminal, provider, and
   new verification commands. It must not import a compatibility alias from
   the live core.
4. **Retired diagnostic** — retain its existing artifact only as history, stop
   invoking it in current evidence, and do not let it determine a flow result.

This is a clean cutover. There is no live `QiFieldConfig` alias, static
`sense_wave` shortcut, snapshot `emit` alias, old-checkpoint adapter, automatic
state conversion, or fallback to the v2 controller after the flow profile
becomes canonical.

## Current-path disposition and clean-cutover matrix

The cutover does not leave today's callers to discover the new interface by
accident. G0 expands this table to a hash-level import inventory, and W15A must
realize every caller disposition before the release board can pass.

| Current path or family | Disposition | Required endpoint state |
|---|---|---|
| `cassi_qi_field.py` | **Migrate in place; canonical** | Replace `QiFieldConfig` and independent `sense/evolve/convert/consolidate/emit` production methods with `QiFlowProfile`, one `[S,9M,B]` state, fixed operators, `advance()`, exact checkpoints, and derived diagnostics. Delete obsolete public symbols after all canonical callers move. |
| `cassi_field_language.py` | **Migrate in place; canonical** | Preserve the fixed 260-symbol codec and UTF-8/control protocol; replace snapshot emission and `sense -> evolve -> consolidate` with timed boundary packets and integrated outbound work. Session schema becomes flow v3 and persists one field only. |
| `cassi_conscious_chat.py` / `run_cassi_conscious_chat.py` | **Migrate in place; canonical** | Compose `CassiQiFlowEngine`, explicit flow profile/backend, atomic session store, and terminal receipts. No law, fallback, template, or hidden state remains in the CLI layer. |
| `cassi_persistent_provider.py` | **Migrate in place; canonical** | Serve the unified flow engine on loopback `8086`; remove live `cassi_qwen_displacement` and baseline-artifact imports; bound session locks and queues; implement atomic stream/nonstream semantics. |
| `cassi-qi-language.json` | **Freeze as historical v2 input; reject live** | Copy its exact bytes and hash into the historical v2 manifest. Canonical constructors reject its schema. It is replaced, not extended, by `cassi-qi-flow.json`. |
| `cassi-qi-flow-development.json` | **Add under W1; engineering-only** | Complete small analytic profile for G0/G1 and focused development; never selected by terminal/provider release composition. |
| `cassi-qi-flow.json` | **Add; canonical** | Contain the complete validated non-placeholder full-system profile selected by terminal, provider, world drivers, tests, and receipts. |
| `conscious-chat.json` | **Migrate in place; canonical composition** | Point to `cassi-qi-flow.json`, backend/capacity selection, v3 state directory, strict limits, and no baseline receipt or legacy mode. |
| `cassi_qwen_displacement.py` | **Retain as offline evidence only; update** | Build Qwen-zero ownership/displacement evidence from verified flow-chain receipts. It cannot be imported by terminal, provider, field, boundary, body, or world modules. |
| `run_cassi_field_only_displacement.py` | **Migrate; offline gate driver** | Exercise the final flow engine, counterfactual, exact restart, actual process evidence, and zero-Qwen receipt without a pinned baseline dependency in the live graph. |
| `measure_cassi_field_language_dependence.py` | **Migrate; focused counterfactual driver** | Use complete trajectory receipts and registered field perturbations; delete direct `sense/evolve/emit` calls. |
| `verify_cassi_native_runtime.py` | **Retire after coverage transfer** | Move its still-valid Qwen-zero checks into independent `verify_cassi_qi_flow.py`; do not keep two current release-readiness authorities. |
| `test_cassi_qi_field.py` | **Migrate; focused core-law tests** | Retain only observable profile/checkpoint/transport/conversion/retention contracts; transfer other coverage to focused geometry, scale, backend, receipt, and release tests; remove obsolete clipping/top-one assertions. |
| `test_cassi_field_language.py`, `test_cassi_conscious_chat.py`, `test_cassi_persistent_provider.py` | **Migrate; canonical tests** | Cover the new text trajectory, terminal, provider, persistence, concurrency, restart, failure, and no-fallback contracts. |
| `test_l21_*`, `test_l24_*`, `test_l25_*`, `test_l26_*`, and current provider policy/API/restart tests | **Migrate or replace by named G12A/G12E cases** | Preserve externally observable HTTP/session/security interfaces that remain valid; explicitly delete stale schema/default assertions. |
| `test_cassi_qwen_displacement.py` | **Migrate; offline receipt test** | Verify the final flow receipt builder and zero-Qwen process evidence; it is not a live startup test dependency. |
| `cassi_field_daemon.py`, `cassi_f5_provider.py`, and their tests/drivers | **Quarantine as historical F3/F5 surfaces** | Pin to an explicit `historical/qi-v2/` source snapshot and historical config. They are unreachable from canonical imports, ports, configs, gate commands, and provider health. No compatibility alias points back into the live core. |
| `cassi_qi_kv.py` and `run_cassi_qi_behavior_demo.py` | **Quarantine as historical Qi-v2 experiments** | Retain reproducibility under the versioned historical snapshot only. KV/recent-ring state never enters the flow runtime, checkpoint, or evidence graph. |
| `cassi_conscious_cortex.py`, `cassi_conscious_field.py`, `cassi_conscious_world.py`, and their tests | **Quarantine as historical conscious-stack experiments** | Pin to the historical v2 field and learned-world dependencies; remove all canonical import edges. Their access gates, branch states, and ledgers are not current release field state. |
| `cassi_organism.py`, `cassi_organism_law.py`, conscious/organism persistence and agent modules, and their tests | **Quarantine as historical organism experiments** | Preserve source reproducibility in `historical/qi-v2/`; never translate organism arenas, world-model state, teacher data, journals, or unconsumed historical world commands into the new field session. |
| `cassi_world_model.py`, `cassi_world_provider.py`, `cassi_modal_torch.py`, teacher/training/checkpoint scripts | **Historical/offline only** | Remain unreachable from canonical modules and current release commands. Learned outputs may be used only by a separately identified offline comparator, never as a boundary or fallback. |
| `native/llama.cpp/` Qi/GGML/Vulkan paths | **Unchanged offline native intervention laboratory** | Not built, loaded, or cited as evidence for the Python/Torch flow endpoint. A future dedicated field kernel, if G14B requires it, is a new non-Qwen backend project with a new identity. |
| `_diag/cassi-qi-native/*`, page/active-gaze/byte/span probes, and old displacement/conscious artifacts | **Immutable historical evidence** | Do not edit or rerun them under the new profile. The release board identifies them as non-parent artifacts and never promotes their findings. |
| `README.md` | **Update for release** | Name the actual released commands, capacity, measured capabilities, unsupported behavior, and limitations after G15B; remove stale canonical-path claims in the same cutover. |

The historical snapshot is a source quarantine, not a compatibility layer:

- it has an explicit `historical.qi-v2` identity and copied source/config
  hashes;
- canonical modules never import it and it never binds a canonical port;
- historical callers import versioned historical symbols directly;
- no historical checkpoint is accepted by `QiFlowProfile` or the v3 session
  store;
- source history remains recoverable, but only the flow modules participate in
  current commands, tests, receipts, and documentation claims.

W15A may discover more callers than this source survey. Each new caller must be
added to the G0 inventory and assigned one of the same explicit dispositions;
discovery never licenses an adapter, alias, or second live law.

## Canonical versioned profile

`cassi_qi_profile.py` introduces one strict top-level JSON document:

```text
cassi.qi-flow-profile.v1
```

The profile carries a canonical composite `profile_sha256`. It is immutable
while a runtime/session uses it, but a new profile revision is ordinary
engineering work. Runtime envelopes, receipts, actions, and provider health
carry the full composite hash for deployment provenance.

The profile declares these ordered semantic subhashes:

- `state_contract_sha256` for packed layout, dtype, active geometry, field law,
  split order, and checkpoint-continuation semantics;
- `boundary_action_sha256` for boundary frames, probes, body maps, decisions,
  motor transducers, and world-visible units;
- `world_protocol_sha256` for tick, wire, idempotency, and acknowledgement
  semantics;
- `session_storage_sha256` for object, checkpoint, outbox, and transaction
  formats;
- `provider_api_sha256` for HTTP/SSE limits and request behavior;
- `backend_capacity_sha256` for backend numerical and resource contracts;
- `security_evidence_sha256` for authentication, trace, retention, and
  independent-verifier schemas.

### QI-ID-001 (W1/G1): self-describing contract root

`cassi.qi-flow-contract-root.v1` is the first profile-selected
content-addressed object loaded for a profile. It is opened only through the
fixed, non-profile-selectable
`cassi.qi-flow-contract-root-bootstrap.v1` framing/parser contract whose exact
canonical key/scalar rules, size bound, source identity, and cross-language
fixtures are pinned by W0/W1. The bootstrap parses only this root schema and
verifies its self-hash; it cannot be replaced by a profile. The verified root
then binds the descendant canonical codec, schema registry, semantic
projection registry, profile-schema digest, and fully materialized default map
used to interpret every profile and receipt. Its canonical payload is:

```text
schema = cassi.qi-flow-contract-root.v1
contract_root_id
bootstrap_codec = {
  schema = cassi.qi-flow-contract-root-bootstrap.v1,
  sha256
}
canonical_codec = {
  schema = cassi.canonical-json.v1,
  sha256
}
schema_registry = {
  schema = cassi.qi-flow-schema-registry.v1,
  sha256
}
projection_registry = {
  schema = cassi.qi-flow-profile-projections.v1,
  sha256
}
profile_schema_sha256
materialized_defaults = {
  every schema-defaulted profile JSON Pointer,
  canonical type/null encoding,
  explicit materialized value
}
defaults_policy = release-explicit-no-omission-v1
self_sha256
```

The root digest is computed with the fixed bootstrap's domain-separated frame,
with `self_sha256` removed while hashing; it is never computed by trusting the
descendant codec that the root names. The root object, bootstrap codec source
and fixtures, descendant codec bytes, schema-registry bytes,
projection-registry bytes, and complete materialized-default map are each
retained and indexed; a digest without its referenced bytes is not a contract
root. Once the root self-hash and `bootstrap_codec.sha256` match the W0/W1
source identity, the descendant codec validates every child object.
`contract_root_sha256` is a required profile leaf and the root digest is
included in every semantic projection as an interpretation parent. It is not
an eighth semantic subhash and it never owns adaptive state.

Profile loading resolves and verifies the root before applying any schema
semantics. It then checks that the profile contains every root-listed
defaulted pointer explicitly, with the exact canonical value or an explicitly
declared profile value; no loader, projection, or receipt builder may insert a
default after hashing. Omitted defaults, an unknown or duplicate pointer, a
registry/codec/projection digest mismatch, a root that is not self-describing,
or a profile whose `contract_root_sha256` is not the indexed root fail closed.
Release profiles therefore reject omitted defaults rather than silently
normalizing them. The root, its registries, and materialized defaults are
interpretation metadata only: they add no tensor, cache, embedding, optimizer,
replay buffer, or policy state.

`P0` below includes the verified root digest and the complete explicit profile
leaf set. The projection registry records the root as a parent of all seven
semantic projections, so two implementations cannot compute apparently equal
subhashes under different codec, schema, projection, or default rules.


Let `P0` be the profile with `semantic_subhashes` and `profile_sha256` removed.
The schema fixes one ordered semantic registry in the seven names listed above.
Each entry selects a canonical projection of `P0`; a field that governs more
than one semantic domain appears in every affected projection, and no
functional profile field may be omitted. For each registry entry:

The registry is itself frozen as `run-spec/profile-projections.json`. It lists
every leaf JSON Pointer in `P0`, its canonical type/null encoding, ordered array
semantics, and the nonempty set of semantic projections that consume it.
Pointers may intentionally appear in several projections, but no functional
leaf may appear in zero. Schema defaults are materialized before projection;
unknown, missing, duplicated, wildcard-selected, or ordering-dependent
membership is invalid. G0/G1 walk the profile schema against this registry and
use one mutation fixture per leaf to prove exactly the declared subhash set
changes.

```text
semantic_subhash[name] =
  sha256(frame(utf8("cassi.qi-flow-semantic." + name + ".v1")) ||
         frame(canonical_projection(P0, registry[name])))
```

Let `P1` be the profile with the computed `semantic_subhashes` present and only
`profile_sha256` removed. Then:

```text
profile_sha256 =
  sha256(frame(utf8("cassi.qi-flow-profile.v1")) ||
         frame(canonical_json(P1)))
```

Raw field-state hashing is parented by `state_contract_sha256`, not by unrelated
HTTP, retention, or ETW settings. The enclosing session and every release
receipt still identify the complete profile.

Composite profile identity is immutable for a session. Any
`profile_sha256` mismatch is `PROFILE_MISMATCH` and requires a new session,
even when the raw tensor's narrower `state_contract_sha256` would otherwise
match. There is no profile-rebind object, API, or compatibility path; unrelated
profile changes cannot reinterpret an existing trajectory.

### Semantic ownership of state and evidence contracts

The seven semantic subhash names remain the only profile projection names. The
registry additionally labels each projection `state_consuming` and records every
schema's consuming set. A state-consuming projection is one that can change the
decoding, coordinate meaning, numerical execution, or boundary/action operator
applied to a `QiFieldState`; the current conservative set is
`state_contract_sha256`, `boundary_action_sha256`, and
`backend_capacity_sha256`. A lineage fork compares the registry's complete
state-consuming set, not a hard-coded shortcut. A receipt may consume several
subhashes, but it never invents an unregistered parent:

| Requirement | Profile field or schema object | Owning package | Consumed semantic subhashes | State-consuming for fork |
|---|---|---|---|---|
| QI-ID-001 (W1/G1) | `cassi.qi-flow-contract-root.v1` and profile `contract_root_sha256` | Part 3 / W1 (consumed by G1) | all seven semantic projections as interpretation parents | yes |
| QI-CAP-001 (W6A/W6B/W10R; G6A/G6B/G6C) | `cassi.qi-flow-capacity-ladder.v1` | Part 2 / W6A/W6B/W10R / receipts+verifier (consumed by G6A/G6B/G6C) | `state_contract_sha256`, `backend_capacity_sha256` | artifact only |
| QI-SCALE-001 (W6T/G6T) | `QiScaleGeometryProfile.scale_geometry_mode` and preregistered `cassi.qi-flow-scale-geometry-comparison.v1` | `cassi_qi_profile.py` / `cassi_qi_receipts.py` | `state_contract_sha256`, `backend_capacity_sha256` | yes |
| QI-CONV-001 (W5V/G5V) | `QiConversionProfile.epsilon_memory_time` and complete-domain interval/analytic proof in `cassi.qi-flow-conversion-profile.v1` | `cassi_qi_profile.py` / `verify_cassi_qi_flow.py` | `state_contract_sha256` | yes |
| QI-RET-001 (W4R) | `QiRetentionProfile` topological-retention Hamiltonian/topology core | `cassi_qi_profile.py` / `cassi_qi_field.py` | `state_contract_sha256` | yes |
| QI-RET-002 (W4R/W10R) | `QiRetentionProfile.analog_acquisition` and `.topological_consolidation` tiers | `cassi_qi_profile.py` / `cassi_qi_field.py` | `state_contract_sha256` | yes |
| QI-RET-003 (W10R) | retention/topology receipt algebra, dynamical reachability, and `cassi.qi-flow-forgetting.v1` | `cassi_qi_receipts.py` / `verify_cassi_qi_flow.py` | `state_contract_sha256`, `backend_capacity_sha256` | artifact only |
| QI-BOUND-001 (W7P/G7P) | `QiBoundaryPermeabilityProfile` and `cassi.qi-flow-sensory-openness.v1` | `cassi_qi_profile.py` / `cassi_qi_boundary.py` / `verify_cassi_qi_flow.py` | `boundary_action_sha256`, `state_contract_sha256` | yes for the profile; artifact only for receipts |
| QI-ACT-001 (W9O/G9O) | finite-horizon no-peek term, `cassi.qi-flow-action-discriminability.v1`, and `cassi.qi-flow-delayed-influence.v1` | `cassi_qi_profile.py` / `cassi_qi_flow.py` / `verify_cassi_qi_flow.py` | `boundary_action_sha256`, `state_contract_sha256` | yes for the profile; artifact only for receipts |
| QI-PORT-001 (W6T/G6T) | `QiScatteringReceipt` | `cassi_qi_receipts.py` | `state_contract_sha256`, `boundary_action_sha256` | artifact only |
| QI-LEARN-001 (W10E/G10E) | `QiFieldExperiencePlan` | `cassi_qi_receipts.py` / `verify_cassi_qi_flow.py` | `boundary_action_sha256`, `session_storage_sha256`, `backend_capacity_sha256` | no |
| QI-TEXT-001 (W11D/G11D) | `QiDynamicPortFrame` | `cassi_qi_receipts.py` / `verify_cassi_qi_flow.py` | `state_contract_sha256`, `boundary_action_sha256`, `backend_capacity_sha256` | artifact only |
| QI-TEXT-002 (W11D/G11D) | interval-certified reaction-pruning record in `QiDynamicPortFrame` | `cassi_qi_receipts.py` / `verify_cassi_qi_flow.py` | `state_contract_sha256`, `boundary_action_sha256`, `backend_capacity_sha256` | artifact only |
| QI-TEXT-003 (W11D; G11/G11D) | `cassi.qi-flow-text-ownership.v1` and `cassi.qi-flow-text-codebook-packing.v1` | Part 8 / W11D (consumed by G11/G11D) / `verify_cassi_qi_flow.py` | `state_contract_sha256`, `boundary_action_sha256`, `backend_capacity_sha256` | artifact only |
| QI-LINEAGE-001 (W12L/G12L) | `QiStateLineageForkReceipt` | `cassi_qi_receipts.py` / `cassi_qi_flow.py` | `session_storage_sha256` plus the complete state-consuming set | yes |
| QI-NUM-001 (W3N/G3N) | immutable `QiNumericalCertificate` root and `cassi.qi-flow-certificate-extension.v1` chain | `cassi_qi_receipts.py` / `verify_cassi_qi_flow.py` | `state_contract_sha256`, `backend_capacity_sha256` | artifact only |
| QI-TXN-001 (W12M/G12M) | `QiTransactionModelReceipt` with two-caller CAS evidence and `cassi.qi-flow-indeterminate-world-effect.v1` | `cassi_qi_receipts.py` / `verify_cassi_qi_flow.py` | `world_protocol_sha256`, `session_storage_sha256`, `security_evidence_sha256` | no |
| QI-EVID-001 (G13D) | `cassi.qi-flow-adapter-off-evidence.v1` | `verify_cassi_qi_flow.py` | `security_evidence_sha256` plus every exact artifact's declared parent set | no |
| QI-DOC-001 (registry) | `cassi.qi-flow-schema-registry.v1` registry mapping | `verify_cassi_qi_flow.py` | `security_evidence_sha256` | no |


For every row, the schema registry fixes the canonical field set, parent
subhash order, maximum bytes, and fixture digest. A missing, extra, reordered,
or unlabelled consumed subhash is a profile/schema failure. These rows are
ownership declarations, not additional adaptive state or additional profile
hashes.

State-consuming entries are included in the canonical `semantic_subhashes`
records as a boolean registry property. This makes a fork auditable even when a
future profile revision adds a projection; the operation must compare the
complete ordered set and fails closed if either profile has an unknown or
different membership declaration.

```json
{
  "schema": "cassi.qi-flow-profile.v1",
  "contract_root_sha256": "...",
  "contract_root": {
    "schema": "cassi.qi-flow-contract-root.v1",
    "canonical_codec": { "schema": "cassi.canonical-json.v1", "sha256": "..." },
    "schema_registry": { "schema": "cassi.qi-flow-schema-registry.v1", "sha256": "..." },
    "projection_registry": { "schema": "cassi.qi-flow-profile-projections.v1", "sha256": "..." },
    "profile_schema_sha256": "...",
    "materialized_defaults_sha256": "...",
    "self_sha256": "..."
  },
  "profile_id": "qi-flow-full-v1",
  "field": { "scale_count": 4, "packed_slots_per_scale": 0, "..." : "strict field constants" },
  "spatial": {
    "spectral_transform": "unitary-fft2.v1",
    "active_shape": [0, 0],
    "active_site_order": "physical-row-major-yx.v1",
    "scale_spacing": [],
    "boundary_condition": "periodic",
    "active_masks": []
  },
  "scale_geometry": {
    "scale_geometry_mode": "temporal-full-rank",
    "comparison_receipt_sha256": "...",
    "selection_rule": "registered-comparison-v1"
  },
  "dynamics": {
    "steering": {},
    "carrier": {},
    "max_candidate_energy": 0,
    "numerical_tolerance": {}
  },
  "conversion": {
    "epsilon_memory_time": "f64:3ff0000000000000",
    "ema_update_mode": "exponential-v1",
    "frozen_q_map": {}
  },
  "retention": {},
  "scale_coupling": {},
  "boundaries": { "permeability_profiles": [] },
  "body_frame": {},
  "action": {},
  "world": {},
  "backend_contract": {},
  "capacity": {},
  "receipts": {},
  "execution": {},
  "experience": { "schema": "cassi.qi-flow-field-experience-plan.v1" },
  "numerical": { "schema": "cassi.qi-flow-numerical-certificate.v1" },
  "semantic_subhashes": [
    { "name": "state_contract_sha256", "sha256": "...", "state_consuming": true },
    { "name": "boundary_action_sha256", "sha256": "...", "state_consuming": true },
    { "name": "world_protocol_sha256", "sha256": "...", "state_consuming": false },
    { "name": "session_storage_sha256", "sha256": "...", "state_consuming": false },
    { "name": "provider_api_sha256", "sha256": "...", "state_consuming": false },
    { "name": "backend_capacity_sha256", "sha256": "...", "state_consuming": true },
    { "name": "security_evidence_sha256", "sha256": "...", "state_consuming": false }
  ],
  "profile_sha256": "..."
}
```

The example is a schema-shape illustration and is deliberately not a runnable
profile. The abbreviated root shape above does not stand in for its default
map: `materialized_defaults` is complete in every release root and every
defaulted leaf is also present in the release profile bytes.

Before the first run, `cassi-qi-flow.json` must replace every shown
placeholder with a measured or analytically derived value and contain every
constant, rectangular active-subspace definition, transform normalization,
descriptor hash, limit, and acceptance tolerance required by the G0 gate
manifest. A profile with an unknown key, missing key, duplicate canonical
descriptor identifier, incompatible `packed_slots_per_scale`, active rectangle
larger than `M`, invalid restricted adjoint, or unprovable step envelope fails
at load time.

The profile has these nested contracts:

### `QiSpatialProfile`

- per-scale `active_shape=(N_y,N_x)`, exact first-`N_s` row-major slot order,
  one-to-one `site <-> (y,x)` physical-grid map, and derived
  `site <-> (k_y,k_x)` DFT order;
- no internal inactive holes: inactive storage is tail-only, and every FFT,
  nonlinear force, remap, and boundary operator acts on the complete active
  rectangle before scattering back to storage;
- unitary forward/inverse FFT normalization and periodic boundary convention;
- release FFT sheets are explicitly periodic under this convention. Any future
  nonperiodic operator family is a different profile family and must register
  distinct transform, metric, boundary-flux, and adjoint identities; it cannot
  reuse the periodic FFT sheet or its energy/flux certificate by relabeling.
- physical extent and per-scale spacing, origin, axes, and handedness;
- positive active metric
  `W_s=diag(dx_s*dy_s)` of shape `[N_s,N_s]`;
- gather/scatter maps `\mathcal G_s: C^M -> C^N_s` and
  `\mathcal G_s^T`, declared low-pass restriction
  `P_s: C^N_s -> C^N_{s+1}`, restricted adjoint/prolongation
  `P_s^\dagger=W_s^{-1}P_s^H W_{s+1}`, and their norm/error contract;
- carrier and steering wave speeds, spectral symbols, per-scale body-remap
  convention, and operator hashes;
- calibration, embodied, and final-capacity profile identities.

All scales retain the same `[9M]` storage, but all physical operators are
defined only on their positive-metric active subspaces. A coarser scale is
represented by its fixed active rectangle and physical spacing, not an
undeclared tensor, a zero-volume metric row, or a projected internal mask. The
current v2 calibration mapping uses only `W=M/2=256` active sites as a
16-by-16 sheet at `M=512`; that mapping is a numerical calibration profile only
and cannot be promoted as the complete perceptual system. The final
full-capacity profile is separately named and must pass the same operator and
world-loop checks at its release geometry.

### `QiScaleGeometryProfile`

The profile contains one explicit
`scale_geometry_mode` with exactly these values:
`temporal-full-rank` or `spatiotemporal-pyramid`. The selected mode is part of
`state_contract_sha256` and `backend_capacity_sha256`; a caller cannot infer
rank loss from `active_shape`, storage capacity, or a missing scale map.
`temporal-full-rank` retains the declared full-rank temporal state at every
selected spatial sheet. `spatiotemporal-pyramid` may reduce spatial rank only
through the registered active rectangles, restriction/prolongation maps, metric
adjoints, and rank/error bounds in the profile.

`QiScaleGeometryProfile` also records
`cassi.qi-flow-scale-geometry-comparison.v1` as
`comparison_receipt_sha256`, the candidate-mode identities, the common
boundary/clock/backend fixture set, rank and conditioning intervals, work and
capacity measurements, and the deterministic selection rule. Production may
select a mode only after that registered comparison is independently
recomputed by W6T/G6T. A comparison that is absent, uses different inputs, or
shows an unaccounted rank loss rejects the profile; repeated rejection is not a
normalization or implicit mode-selection mechanism.

The scale-geometry payload is canonically encoded as
`cassi.qi-flow-scale-geometry.v1` with the selected mode, ordered candidate
mode identities, fixture/profile/backend hashes, rank/conditioning/work
intervals, selection rule, ordered consumed subhashes, and `self_sha256`
removed while hashing. Candidate arrays and scale identifiers use declared
registry order; intervals use the canonical rational/finite-bit encodings.
An unknown mode, missing comparison identity, reordered candidate set, or
comparison whose fixture/profile/backend parent differs is a
`SCALE_GEOMETRY_PROFILE_INVALID` failure before field allocation.
The companion comparison receipt
`cassi.qi-flow-scale-geometry-comparison.v1` stores both candidate outputs,
common fixture/source identities, rank/conditioning intervals, work/capacity
measurements, and the selection decision. It is independently recomputed by
the verifier; a selected mode without this receipt is not production-valid.

### `QiConversionProfile`

The conversion contract is a versioned object
`cassi.qi-flow-conversion-profile.v1`. It stores the physical constitutive
`epsilon_memory_time>0` in the profile's declared time unit, the frozen-`Q`
map/operator identity, the positive `rho_ref`, conversion work convention,
validity domain, and the one-update-per-step EMA stage identity. For a field
interval `h`, the runtime derives the dimensionless per-step coefficient

```text
tau_epsilon(h) = 1 - exp(-h / epsilon_memory_time)
```

from those canonical physical values; a per-step `tau_epsilon` is never stored
as an independent constitutive parameter. An explicitly named test-only
`ema_update_mode="freeze"` control is not a production conversion law and
cannot be selected by mutating a release profile.

W5V/G5V must prove a frozen complete-domain conversion interval/analytic
certificate for the frozen-`Q` map, including the derived coefficient and its
enclosure on every declared support-domain cell. Fixtures are witnesses only:
an unresolved cell fails profile construction, and the support domain is fixed
before observation and cannot shrink after seeing a conversion result. If the
map cannot produce that domain, the design revises the law and profile rather
than normalizing repeated rejection or adding a fallback conversion.
Missing/zero/nonfinite physical time, a nonpositive derived coefficient for a
positive `h`, a different EMA update count, or an unproven complete-domain
interval fails before state commit.

### `QiDynamicsProfile`

- coefficients for `D` and `C` propagation, damping, bounded nonlinear terms,
  local steering coupling, source budgets, and scale coupling;
- exact rational `h_min>0` and `h_max>=h_min` for every live duration;
- finite coordinate/scale amplitude caps \(R_{Z,s}>0\), with
  \(|Z_{s;m}|\leq R_{Z,s}\) throughout the declared admissible domain;
- an explicit stability safety margin
  \(0<\sigma_{\mathrm{stab}}<1\);
- explicit split-operator order and per-substep work convention;
- maximum permitted energy before any bound operator;
- exact linear-symbol/integrator choice;
- dtype-specific numerical tolerances, same-backend continuation contract, and
  `bound_policy="reject-before-commit"` for every promoted result: clipping
  and global rescaling are prohibited, not concealed as stable dynamics.

The coefficient domain is normative. The constant
`\phi=(1+\sqrt{5})/2` is immutable, positive, and dimensionless.
For every declared coordinate/scale, `c_{Z,s}>0`, `omega_{Z,s}>0`,
`gamma_{Z,s}>=0`, and `kappa_{Z,s}>=0`; every release adjacent-scale
`g_{Z,s}>0`; `0<=beta_s<1`; and `epsilon_ref,s>0`. The finite derived
certificate bounds are
\[
\gamma_{\max}:=\max_{Z,s}\gamma_{Z,s},
\qquad
R_{\max}:=\max_{Z,s}R_{Z,s},
\]
and the profile hashes both these derivations, every input
\(\gamma_{Z,s},R_{Z,s}\), and \(\sigma_{\mathrm{stab}}\) into its stability
envelope identity. The conversion contract stores
`epsilon_memory_time`, `rho_ref`, `lambda`, `h_min`, and `h_max`; it derives
the physical-time coefficient and its complete-domain enclosure from those
frozen values. Registered null controls may set the named `g`, `beta`, `lambda`,
external gain, or `ema_update_mode="freeze"` control to exact zero only in a
separately hashed control profile. No control changes the production profile in place.
Diagnostic and decision regularizers
`delta_amp`, `delta_phase`, and `J_ref` are strictly positive; residual and
action weights `eta_r`, `nu_r`, `mu_move`, and `mu_flow` are nonnegative, with
the stated normalization constraints. Every scalar has one exact
`cassi.canonical-json.v1` integer/rational/finite-bit encoding, unit, provenance
(`analytic`, `measured_fixture`, or `explicit_design`), and validity interval
in the contract manifest; an unfilled or out-of-domain value
blocks profile creation rather than becoming a zero/default.

### `QiBoundaryProfile`

- immutable descriptor IDs for optical, text, audio, proprioceptive, motor,
  and world-return ports;
- raw dimensions, physical units, timing resolution, saturation, validity,
  frame, normalization, phase convention, forward transform, and adjoint;
- descriptor collision and round-trip test identity;
- fixed simultaneous-event ordering and declared cross-modal delay windows;
- no vocabulary matrix, learned embedding, feature extractor, or adaptive
  boundary cache.

`QiBoundaryPermeabilityProfile` is the immutable passive sensory-coupling
contract `cassi.qi-flow-boundary-permeability-profile.v1`. For each declared
port and scale it records the field-derived permeability operator
`\Pi_{r,s}[\mathcal X]`, its admissible `[0,1]` interval, orientation, metric,
frequency/timing band, admitted/reflected/absorbed work integrals, interval/error
bounds, and operator/descriptor hashes. `\Pi_{r,s}` is evaluated from the
current declared field and fixed descriptors; it is not a learned gain,
history, cache, or request-time override. The receipt convention is

```text
W_incident = W_admitted + W_reflected + W_absorbed + R_permeability
W_admitted >= 0
W_reflected >= 0
W_absorbed >= 0
```

with `R_permeability` inside its independently verified enclosure. A missing
operator, out-of-range permeability/fraction, negative admitted, reflected, or
absorbed work, an unbounded remainder, or non-passive/candidate-dependent
coupling rejects the packet before controller mutation. The profile and every
admitted/reflected/absorbed work result are parented by
`boundary_action_sha256`.

QI-BOUND-001 additionally requires each mandatory sensory port to declare a
positive incident-work witness, an uncertainty-aware openness threshold, and a
finite recovery horizon. A port that remains permanently blind, supplies only
null/zero-work controls, or omits recovery evidence is not releasable; its
`cassi.qi-flow-sensory-openness.v1` receipt fails before capability claims.

### `QiBodyFrameProfile` and `QiActionProfile`

- body axes/origin, gaze and camera transform conventions, translation and
  rotation/remap algorithms, and round-trip tolerance;
- allowed action families, bounds, cadence, fixed cost, validity gates,
  idempotency format, and world acknowledgement timeout;
- explicit simulator versus physical-actuator identity. Physical activation is
  disabled until the operator separately authorizes its exact environment and
  envelope; the full architecture does not route a failed physical action to a
  simulated success.

`QiActionProfile` freezes a shared finite decision horizon `H`, geometry-only
candidate descriptors, and the no-peek observability-improvement term required
by QI-ACT-001. Its declared coefficient, target port set, baseline/hold
counterfactual, interval tolerance, and `observability_horizon` are part of
`boundary_action_sha256`. The term is computed only from the current committed
field, admitted packets, fixed body/action geometry, and zero-new-observation
candidate rollouts; no candidate observation, renderer, collision result, or
adapter state may enter it. A missing hold arm, unequal horizon, unregistered
term, or any observed future consequence fails closed before a proposal.

The action and receipt contracts also declare finite
`max_candidate_trajectories_per_cycle`, `max_dynamic_frames_per_cycle`,
`max_dynamic_response_bytes_per_frame`, `max_dynamic_evidence_bytes_per_cycle`,
and `max_scattering_receipts_per_cycle` values. Before any candidate clone,
trajectory sample, or receipt payload is allocated, the engine computes

```text
F_dynamic =
  selected_scales * selected_dynamic_ports * candidate_trajectory_count
B_dynamic =
  F_dynamic * (frame_header_max + response_sample_count *
               response_vector_width * scalar_bytes + interval_overhead)
```

using checked integer arithmetic and the profile's declared maxima. A zero
port/scale arm still emits its registered null object, while an overflow,
unbounded sample grid, or fanout/byte count above the profile fails before
controller mutation. Every dynamic-frame and candidate receipt records the
exact fanout, sample count, raw-byte count, and governing bound identity; raw
evidence is retained only under those bounds and never becomes a second field
or policy state.


### Execution, world, backend, capacity, and receipt profiles

- world protocol version, deterministic-reference and CassiCosmos adapter
  identities, logical timebase, loopback bind/peer policy, modality
  capabilities, wire size limits, idempotency horizon, and reconnect policy;
- permitted CPU/ROCm device/dtype identities, FFT/determinism contract,
  same-backend exactness, cross-backend tolerances, and explicit no-fallback
  rule;
- integrated and release field geometry, batch/session/candidate limits,
  queues, scratch/state formulas, latency/memory/allocation budgets, and
  long-horizon duration;
- receipt/schema versions, canonical JSON/float/tensor byte encodings,
  domain-separated hash tags, raw-artifact retention, parent graph, and
  independent-verifier contract;
- exact split cadence, packet watermark/order, failure policy, and gate
  schema/formula identities. Concrete run manifests consume the profile
  one-way and are never included inside its own hash.

`QiExperienceProfile` is a non-adaptive profile contract for
`QiFieldExperiencePlan`. It fixes the allowed byte/world stream descriptors,
clock and episode partition rules, admitted-work ceilings, washout interval,
stopping rule, control arms, and checkpoint-selection rule. It cannot contain
learned weights, embeddings, optimizer state, teacher state, replay buffers, or
post-hoc stream selection. A plan consumes this profile one-way and records
its exact plan hash in every experience receipt.

The receipt profile also registers the schemas for
`cassi.qi-flow-capacity-ladder.v1`,
`cassi.qi-flow-sensory-openness.v1`,
`cassi.qi-flow-dynamic-port-frame.v1`,
`cassi.qi-flow-scattering-receipt.v1`,
`cassi.qi-flow-action-discriminability.v1`,
`cassi.qi-flow-delayed-influence.v1`,
`cassi.qi-flow-forgetting.v1`,
`cassi.qi-flow-text-ownership.v1`,
`cassi.qi-flow-text-codebook-packing.v1`,
`cassi.qi-flow-numerical-certificate.v1`,
`cassi.qi-flow-certificate-extension.v1`,
`cassi.qi-flow-state-lineage-fork-receipt.v1`,
`cassi.qi-flow-transaction-model-receipt.v1`,
`cassi.qi-flow-indeterminate-world-effect.v1`, and the adapter-off evidence
object. The profile itself carries the indexed
`cassi.qi-flow-contract-root.v1`. Each entry declares its semantic parent set,
canonical fixtures, byte/fanout limit, lifecycle, and independent verifier.
Missing registration or a request-time replacement of any of these contracts
fails profile loading.


### Executable stage, stability, and retention profiles

`QiStageSpec` is the sole machine-readable operator-order contract:

```text
cassi.qi-flow-stage-spec.v1
  stage_id
  ordinal
  transition_kind = timed | timed_phase_slip | finite_map | diagnostic | port_reaction | retention_reset
  operator_sha256
  clock_increment_num / clock_increment_den
  effective_duration_num / effective_duration_den
  evaluate_from = predecessor | current_candidate | frozen_stage_copy
  read_slices[]
  write_slices[]
  drive_classes[]
  work_rows[]
  phase_charge_rows[]
  bound_checks[]
  synchronization_points[]
  permitted_failure_codes[]
```

`read_slices` and `write_slices` use canonical packed-plane and active-scale
identifiers. A stage cannot write a slice it did not declare, advance time from
a zero-time transition, update EMA outside its one stage, or emit a ledger row
owned by another stage. `effective_duration` records the physical interval used
by a centered finite map such as conversion even when that map adds no second
clock increment.

`QiExecutionProfile` contains the complete ordered `QiStageSpec` array,
simultaneous-event ordering, rational event grid, candidate/commit boundary,
and the schedule hash:

```text
execution_schedule_sha256 =
  sha256(frame(utf8("cassi.qi-flow-execution-schedule.v1")) ||
         frame(canonical_json(ordered_stage_specs)))
```

The canonical timed schedule is:

| Ordinal | Stage | Clock role | Sole work/continuity ownership |
|---:|---|---|---|
| 0 | validate/derive | zero | no work; predecessor/profile/drive identities |
| 1 | applied-efference body remap | finite map, zero clock increment | remap work and remap residual |
| 2 | external half-forces | zero clock increment; effective `h/2` | ingress and residual rows |
| 3 | conservative half-forces | zero clock increment; effective `h/2` | nonlinear, composition, link, retention rows |
| 4 | exact damped spectral half-propagator | advance first `h/2` | spectral transport plus exact damping quadrature |
| 5 | frozen-`Q` conversion | zero clock increment; effective centered duration `h` | conversion work and charge source |
| 6 | exact damped spectral half-propagator | advance second `h/2` | spectral transport plus exact damping quadrature |
| 7 | conservative half-forces | zero clock increment; effective `h/2` | reevaluated retention/link/composition/nonlinear rows |
| 8 | external half-forces | zero clock increment; effective `h/2` | reverse-order ingress/residual rows |
| 9 | coordinate reconstruction and EMA | zero clock increment | one EMA update and inactive-tail proof |
| 10 | diagnostics/preflight | zero clock increment | closure, endpoint topology, bounds, candidate identity |

`transition_kind=port_reaction` and `retention_reset` each have a registered
one-row zero-time schedule and cannot reuse or partially execute the timed
array. `timed_phase_slip` uses the complete timed schedule plus its frozen
topology-refinement observer; it adds no state write. The runtime and verifier
reject a missing, duplicate, reordered, undeclared, or backend-fused stage
unless the fusion has the same stage-visible results and a separately
registered operator/schedule hash.

`QiStabilityEnvelope` records the analytic component bounds, active amplitude
and work domain, intermediate-stage bounds, metric-normalized Hessian/operator
norms, remap amplification, exact-propagator branch identities, numerical
uncertainty, and strict safety margin. It is consumed by the profile loader
before any field allocation.

`QiRetentionProfile` is nested under the state contract and contains:

```text
retention_class = fading-retention | reciprocal-hamiltonian-topology
mode = fading-v1 | topological-v1
slow_scale
a_topo / b_topo
r_core / rho_ring / rho_topo / delta_topo / delta_topo_int
theta_0 / angle_encoding
E_topo / lambda_ph / lambda_core
radial_curvature_min / Delta_H_topo_min / barrier_uncertainty_guard
topology_endpoint_subdivision_sha256
edge_registry_sha256
cycle_registry_sha256
phase_slip_subdivision_sha256
barrier_certificate_sha256
reset_operator_sha256
fading_retention_comparator_profile_sha256
```

The release profile requires `mode=topological-v1,slow_scale=S-1,
a_{\mathrm{topo}}=0,b_{\mathrm{topo}}=1`. All values are immutable, bounded, unit-declared, and included
in `state_contract_sha256`; fading retention has `U_topo=0` and is a control profile only.
Derived order parameters, windings, and Hodge components are absent from
checkpoints and sessions.
QI-RET-001 is a stage-order requirement, not a label: W4R installs the
topological-retention Hamiltonian/topology core after W4 and before W5. W10R owns later
behavioral retention and consolidation; a topological-retention profile cannot defer its
Hamiltonian/topology terms to W10R or claim that a later receipt retroactively
installed them.

QI-RET-002 keeps within-sector analog acquisition and topological consolidation
as distinct memory tiers in the same one-field state. The analog tier records
continuous sector-local acquisition; the topology tier records the registered
sector/winding/barrier algebra. No extra memory tensor, replay buffer, or
hidden consolidation state is permitted.

QI-RET-003 requires measurements of topology algebra, reachable basin capacity,
saturation, overwrite, recovery, and dynamical forgetting, with predecessor/
candidate identities, exact canonical `advance()` trajectories, nonnegative
incident/source-work budgets, and work/barrier evidence. Reset is an explicit
administrative control and never counts as acquisition or forgetting. The
`cassi.qi-flow-forgetting.v1` receipt must distinguish geometric, reachable,
observable, usable, retained, and reusable capacity and must retain the
trajectory witnesses for every claimed transition. A receipt that reports only
final labels, omits unreachable/saturated controls, uses a post-hoc path, or
infers recovery/forgetting without the registered trajectory fails closed.

The top-level profile contains the versioned maximum and selected runtime
contract. `QiRuntimeConfig` may select a permitted backend and values no greater
than its resource maxima; it cannot alter field laws, tolerances, decision
thresholds, world semantics, or evidence rules during a session. Per-run
secrets, nonces, trace IDs, and release digests are downstream artifacts
and never profile inputs.

## State, checkpoint, and protocol schema cutover

The tensor layout remains `[S,9M,B]`. The semantic identity does not.

The tensor dtype is real `float32` or `float64`; complex fields are reconstructed
from paired real planes. Axis 1 has this immutable contiguous order:

```text
[0M:1M]  Y_re
[1M:2M]  Y_im
[2M:3M]  I_re
[3M:4M]  I_im
[4M:5M]  VY_re
[5M:6M]  VY_im
[6M:7M]  VI_re
[7M:8M]  VI_im
[8M:9M]  epsilon2_ema
```

Scale 0 is the finest/fastest sheet; increasing scale index is
coarser/slower. `B` lanes are independent and never coupled. Profile-inactive
sites are exactly zero in all nine planes and are verified after every
candidate; otherwise they would be undeclared hidden capacity.

After the fixed contract-root bootstrap has authenticated the root,
`cassi.qi-flow-schema-registry.v1` is the sole descendant schema namespace
authority. The source-pinned bootstrap is the one pre-registry primitive and
is mirrored in the registry for audit; it cannot be selected or redefined by
that registry. The registry contains each descendant schema's canonical JSON
Schema digest, parent/subhash mapping, maximum encoded bytes, canonical fixture
digest, and lifecycle classification. Every object-index entry and verifier
decoder is generated from this frozen registry; any other schema literal is a
gate failure. The profile, world-wire, OpenAI API, session-storage, and
evidence groupings below are subregistries of this one object, never
independent lists.

| Object | Schema | Persistent content | Explicitly excluded |
|---|---|---|---|
| Schema registry | `cassi.qi-flow-schema-registry.v1` | canonical schema/digest/size/fixture/parent entries | runtime-discovered or unversioned object types |
| Contract-root bootstrap | `cassi.qi-flow-contract-root-bootstrap.v1` | fixed non-profile-selectable root framing, canonical rules, size bound, source/toolchain identity, and cross-language fixtures | profile-selected bootstrap, descendant-codec self-interpretation, or an unpinned parser |
| Canonical encoding | `cassi.canonical-json.v1` | strict UTF-8 scalar/object/array/integer/rational/finite-bit encoding, ordering, limits, and cross-language fixtures | implementation-default JSON bytes |
| Contract root and identity | `cassi.qi-flow-contract-root.v1` | self-describing codec, schema-registry, projection-registry, profile-schema, and fully materialized-default identities | omitted defaults, implicit codec/registry selection, or unindexed referenced bytes |
| Run specification and boards | `cassi.qi-flow-run-index.v1`, `cassi.qi-flow-manifest.v1`, `cassi.qi-flow-dependency-manifest.v1`, `cassi.qi-flow-semantic-subhashes.v1`, `cassi.qi-flow-profile-projections.v1`, `cassi.qi-flow-source-identity.v1`, `cassi.qi-flow-raw-retention-policy.v1`, `cassi.qi-flow-capability-matrix.v1`, `cassi.qi-flow-toolchain.v1`, `cassi.qi-flow-command-inputs.v1`, `cassi.qi-flow-gate-status.v1`, `cassi.qi-flow-engineering-board.v1`, `cassi.qi-flow-candidate-result.v1`, `cassi.qi-flow-readme-verification.v1`, `cassi.qi-flow-release-board.v1`, `cassi.qi-flow-release-result.v1` | immutable indexed run identity, dependency node/edge/owner/consumer/artifact graph with source-section hashes, retention policy, validation statuses, candidate/documentation readiness, typed documentation verification, and release verdict | unindexed files, undeclared status, hand-edited graph, or unregistered graph schema |
| Profile | `cassi.qi-flow-profile.v1` | complete selected law plus required `contract_root_sha256`, explicit defaults, and state/operator/boundary/execution/evidence subhashes | request-time law overrides or omitted defaults |
| Stage and schedule | `cassi.qi-flow-stage-spec.v1`, `cassi.qi-flow-execution-schedule.v1` | ordered typed stage contracts and schedule hash | implicit call order |
| Clock time and clock | `cassi.qi-flow-clock-time.v1`, `cassi.qi-flow-clock.v1` | reduced rational times, LCM, field/world/source rates | host time as causal state |
| Antialias profile/receipt | `cassi.qi-flow-antialias.v1`, `cassi.qi-flow-antialias-receipt.v1` | fixed resampling operator and per-packet proof | undeclared sample dropping |
| Stability envelope | `cassi.qi-flow-stability-envelope.v1` | admitted domain, termwise bounds, margins, refinement identity | empirical clipping factor |
| Scale geometry and conversion | `cassi.qi-flow-scale-geometry.v1`, `cassi.qi-flow-scale-geometry-comparison.v1`, `cassi.qi-flow-conversion-profile.v1` | explicit `scale_geometry_mode`, registered mode comparison, physical `epsilon_memory_time`, frozen-`Q` map, and derived EMA coefficient contract | implicit rank loss, stored per-step constitutive time, or normalized repeated conversion rejection |
| Boundary permeability | `cassi.qi-flow-boundary-permeability-profile.v1` | field-derived passive permeability, admitted/reflected/absorbed work partition, metric/orientation, and enclosure | learned/history-dependent permeability, negative work, or unaccounted boundary injection |
| Sensory openness | `cassi.qi-flow-sensory-openness.v1` | incident-work-normalized admitted response, recovery interval, mandatory-port controls, and field-derived operator identity | permanent blindness, zero-work witness, learned/history gain, or candidate-dependent coupling |
| Field experience | `cassi.qi-flow-field-experience-plan.v1` | immutable byte/world streams, timing, work budgets, whole-episode splits, washout, stopping, controls, and checkpoint selection | optimizer/weights/embedding, post-hoc split, replay buffer, or adaptive teacher state |
| Capacity ladder | `cassi.qi-flow-capacity-ladder.v1` | geometric, reachable, observable, usable, retained, and reusable capacity intervals from exact trajectories and nonnegative work budgets | reset counted as acquisition, post-hoc paths, negative/unbounded work, or an extra memory object |
| Dynamic port and scattering | `cassi.qi-flow-dynamic-port-frame.v1`, `cassi.qi-flow-scattering-receipt.v1` | trajectory-response rank/conditioning/cross-talk and incident/reflected/transmitted/absorbed work at scale/external ports | static probe-only rank, hidden port state, or omitted work channel |
| Action discriminability and delayed influence | `cassi.qi-flow-action-discriminability.v1`, `cassi.qi-flow-delayed-influence.v1` | offline paired-world contrasts, no-peek candidate identity, uncertainty/null-thresholded causal consequence, and ordinary residual-packet links | runtime future-world peek, persistent credit/eligibility state, or a static action score |
| Numerical certificate | `cassi.qi-flow-numerical-certificate.v1` | offline high-precision/enclosure derivation, online scalar-guard contract, and independent replay identity | online finite check presented as enclosure proof or runtime self-verification |
| Certificate extension | `cassi.qi-flow-certificate-extension.v1` | immutable parent digest, complete cumulative section inventory, extension identity, and final certificate identity | parent mutation, replacement-in-place, omitted section, or mutable certificate history |
| Lineage and transaction evidence | `cassi.qi-flow-state-lineage-fork-receipt.v1`, `cassi.qi-flow-transaction-model-receipt.v1` | explicit new-session state fork and bounded Commit-A/Commit-B/outbox/ack/efference/crash/replay model evidence | profile rebind, continuity reuse, unbounded state exploration, or heuristic recovery |
| Indeterminate world effect | `cassi.qi-flow-indeterminate-world-effect.v1` | sealed unresolved external-effect scope, exact intent/lock/envelope/journal identities, and new-session-only disposition | clearing unknown truth, fabricated ack/reject, replay after seal, or continuation |
| Adapter-off evidence | `cassi.qi-flow-adapter-off-evidence.v1` | exact deterministic artifact manifest/equality and narrowly registered volatile projections with mutation controls | numerical similarity, projected field/physics/state bytes, or unregistered volatility |
| Field state | `cassi.qi-flow-state.v3` | raw tensor, state-contract identity, full-profile provenance, layout identity, dtype/backend continuation contract | learned weights, RNG, Qwen/KV state, packet payload, output cache |
| Boundary packet/no-sample | `cassi.qi-flow-packet.v1`, `cassi.qi-flow-no-sample.v1` | transient canonical packet identity/hash/scalars or explicit empty interval/reason | packet payload as adaptive state or an invented zero sample |
| Watermark | `cassi.qi-flow-watermark.v1` | source epochs/streams, rational interval frontier, packet digest frontier | wall-clock freshness inference |
| Ingress journal/source replay | `cassi.qi-flow-ingress-journal.v1`, `cassi.qi-flow-source-replay.v1` | bounded evidence bytes or replay range, head/cursor/retention identity | learned replay or transcript memory |
| Action prediction/proposal | `cassi.qi-flow-action-prediction.v1`, `cassi.qi-flow-action-proposal.v1` | world-blind candidate proof and committed selected proposal | world effect |
| Passive motor reaction | `cassi.qi-flow-motor-port-reaction.v1` | full-Hamiltonian debit, proposal/head link, `world_effect=false` | actuator success |
| Action command | `cassi.qi-flow-action.v1` | deterministic command identity, bounded requested values, cycle/idempotency key | hidden policy state |
| Applied efference | `cassi.qi-flow-applied-efference.v1` | terminal applied-ack bytes, actual values/ticks/body transition, Commit-A/predecessor link | proposal as imagined effect |
| World tick intent | `cassi.qi-flow-tick-intent.v1` | exact action or canonical null action, world/episode/logical/effective tick, idempotency scope, prediction-context hash, and canonical intent bytes | a second command queue or hidden retry policy |
| World tick acknowledgement | `cassi.qi-flow-tick-ack.v1` | exact complete tick scope, status/ack bytes/hash, applied action values/ticks, and original-terminal identity | self-declared simulated success |
| Tick outbox | `cassi.qi-flow-tick-outbox.v1` | one exact complete tick scope, intent hash, lifecycle status, deadline, terminal-ack identity | a second action or heuristic retry |
| Operator tick-outbox clear | `cassi.qi-flow-outbox-clear.v1` | approved session/world/key/hash, prior status, reason, operator identity, timestamp, self-hash | automatic timeout discard |
| Remap | `cassi.qi-flow-remap.v1` | declared transform identity, applied-efference reference, numerical residual | a separate pose memory |
| Ledger and step | `cassi.qi-flow-ledger.v1`, `cassi.qi-flow-step.v1` | work/energy/charge rows, predecessor/head, state-in/out and dependency hashes | raw field duplicates or unbounded traces |
| Boundary transfer/binding | `cassi.qi-flow-boundary-transfer.v1`, `cassi.qi-flow-multimodal-binding.v1` | paired intervention trajectories, work, response, ranks, controls, uncertainty | learned cross-modal map |
| Diagnostic receipts | `cassi.qi-flow-space-scale-receipt.v1`, `cassi.qi-flow-hodge-receipt.v1`, `cassi.qi-flow-retention-receipt.v1`, `cassi.qi-flow-topology-receipt.v1`, `cassi.qi-flow-backend-receipt.v1` | independently recomputable stage/scale/current/retention/topology/backend evidence | versionless builder output |
| Retention transitions | `cassi.qi-flow-retention-phase-slip.v1`, `cassi.qi-flow-retention-reset.v1` | predecessor/candidate sectors, barrier/work path or explicit uniform reset, full-Hamiltonian and topology proof | inferred sector coercion or hidden erasure |
| Forgetting and dynamical reachability | `cassi.qi-flow-forgetting.v1` | exact `advance()` predecessor/candidate trajectories, incident/source-work budget, overwrite and recovery intervals, and retention disposition | reset as acquisition, post-hoc reachability, hidden forgetting state, or unbounded trajectory set |
| Decision | `cassi.qi-flow-decision.v1` | matched-energy counterfactual identity and committed output/action | static-state claim |
| Failure | `cassi.qi-flow-failure.v1` | retained predecessor head, error class, rejected candidate identities | reset/fallback state |
| Checkpoint object | `cassi.qi-flow-checkpoint.v1` | content-addressed field-state object, predecessor, state/step/head identities | response bytes or mutable protocol state |
| Object index | `cassi.qi-flow-object-index.v1` | canonical sorted schema/digest/byte-count entries reachable from one envelope | newest-file inference or unindexed objects |
| Request/response records | `cassi.qi-flow-request-record.v1`, `cassi.qi-flow-response-record.v1` | bounded canonical request identity and exact committed response/SSE bytes | sensed transcript cache or post-crash recomputation |
| Session storage | `cassi.qi-flow-session-storage.v1` | root confinement, ACL, quota, retention, lock and atomic-replace primitive identities | permissive ambient filesystem policy |
| Session | `cassi.qi-flow-session.v3` | atomic state envelope, object index, bounded request/response identities, ingress journal/cursors/source frontiers/watermark, proposal/port-reaction identities, one tick outbox/terminal ack, pending/consumed applied efference, high-water marks, self-hash | a second adaptive object |
| Artifact cleanup | `cassi.qi-flow-artifact-cleanup.v1` | approved root, exact digest set, quarantine/result hashes | wildcard or newest-file deletion |
| Historical v2 snapshot | `cassi.qi-flow-historical-v2-manifest.v1`, `cassi.qi-flow-historical-v2-source-index.v1`, `cassi.qi-flow-historical-v2-checkpoint-index.v1` | immutable wrapper/config identity plus sorted original-path, frozen-path, digest, and byte-count entries for every preserved source and checkpoint | basename-only lookup, unindexed bytes, or state conversion |
| Runtime composition config | `cassi.qi-flow-runtime-config.v1` | profile/backend/session/world/API/resource selections within versioned maxima | law or tolerance override |
| OpenAI API bundle | `cassi.qi-flow-openai-api.v1` with nested `cassi.qi-flow-chat-request.v1`, `cassi.qi-flow-chat-response.v1`, `cassi.qi-flow-api-error.v1`, `cassi.qi-flow-sse-frame.v1` | canonical request/response/error/SSE schemas and wire fixtures | unregistered OpenAI fields |
| Runtime health | `cassi.qi-flow-health.v1` | readiness, profile/backend/source/session/world/process-evidence identities | baseline or fallback health |
| World wire | `cassi.qi-world-wire.v1`, `cassi.qi-world-frame.v1`, `cassi.qi-world-hello.v1`, `cassi.qi-world-hello-ack.v1`, `cassi.qi-world-observe-request.v1`, `cassi.qi-world-observation.v1`, `cassi.qi-world-observation-complete.v1`, `cassi.qi-world-describe-actions.v1`, `cassi.qi-world-action-descriptors.v1`, `cassi.qi-world-advance-tick.v1`, `cassi.qi-world-tick-complete.v1`, `cassi.qi-world-resolve-tick.v1`, `cassi.qi-world-heartbeat.v1`, `cassi.qi-world-heartbeat-ack.v1`, `cassi.qi-world-close.v1`, `cassi.qi-world-close-ack.v1`, `cassi.qi-world-error.v1` | canonical common header, kind-specific fields, request/response fixtures, authenticated outer lengths, per-kind maxima | mandatory null placeholders or unauthenticated identity change |
| Text ownership and codebook packing | `cassi.qi-flow-text-ownership.v1`, `cassi.qi-flow-text-codebook-packing.v1` | field-state-necessity intervention, uncertainty-aware codebook separation/packing, and bounded trajectory evidence | learned embedding, alphabet/rank conflation, or text receipt as adaptive state |
| Text event/result/turn | `cassi.qi-flow-text-event.v2`, `cassi.qi-flow-text-result.v2`, `cassi.qi-flow-chat-turn.v2` | trajectory, reaction, bytes/control, contiguous result/turn identities | static snapshot winner |
| Live ownership receipt | `cassi.qi-flow-ownership.v1` | field-owned state/decision counts and zero Qwen/GGUF/llama/KV/learned runtime counters | historical baseline dependency |
| Offline displacement receipt | `cassi.qi-flow-displacement.v2` | historical baseline hash plus verified live ownership/profile/step/decision/checkpoint identities | a live teacher or provider dependency |

There is no `cassi.qi-flow-action-ack.v1` alias: every external action result is
the registered `cassi.qi-flow-tick-ack.v1`, and only its terminal `applied`
case may parent an applied-efference object. Each diagnostic receipt above is a
standalone indexed object parented by the accepted step/ledger and named in the
session object graph; no versionless nested dictionary can satisfy it.

`QiFieldState.validate()` becomes a full invariant check: exact plane order,
shape, real dtype, device, contiguity, finite values, nonnegative real EMA,
zero inactive sites, state-contract/layout identity, site compatibility, and
declared bounds. A finite externally supplied oversize state is rejected rather
than allowed to evade the stability profile.

Serialization and external release use one content-addressed two-commit
protocol:

1. validate request, source/profile/clock identity, and durable ingress range
   before deriving a candidate field;
2. derive one closed causal cycle, complete ledger, output/reaction,
   `QiActionProposal` or canonical null proposal, and optional
   `QiWorldTickIntent`;
3. write each immutable receipt object under its domain-separated digest in a
   same-volume staging/object directory, flush its bytes through the platform
   durable-file primitive, and verify its digest after reopen;
4. build a session envelope whose embedded object index closes over every
   parent and whose request/response, ingress journal head/cursor/watermark,
   proposal/reaction, and optional tick-outbox records are complete;
5. **Commit A:** write, flush, close, reopen-verify, and publish that envelope
   as the sole commit marker with the profile-approved atomic replace
   primitive. On Windows/NTFS this is same-volume `MoveFileExW` replace with
   `MOVEFILE_WRITE_THROUGH`; another platform must name an equivalent primitive
   and pass the crash-injection fixture or remain `BLOCKED`;
6. after reopen-validating the envelope and every indexed parent, update
   in-memory state, acknowledge/reclaim only the committed ingress range, and
   expose committed text. For a world tick, release the session lock before
   sending or replaying the exact durable tick intent;
7. reacquire the lock, require the Commit-A head and pending tick identity to
   be unchanged, and **Commit B** the idempotent terminal tick acknowledgement
   plus an applied-efference object only when status is `applied`, before any
   successor observation/remap may consume it.

A crash before Commit A leaves the predecessor authoritative and replays the
same ingress range. A crash after Commit A starts after its cursor and reuses
the same committed response/outbox bytes. A crash around Commit B resolves the
world idempotency scope and can neither apply the action nor consume its
efference twice.

An immutable object written before step 5 but unreachable from the committed
envelope is an orphan, never a committed receipt. Recovery loads only the exact
configured session-envelope path and its embedded index; it never selects a
newest temporary. Invalid or orphaned temporaries are moved to a bounded
quarantine by digest after the prior envelope has been validated. Lock files
carry session/profile identity, PID, and process-creation identity, but age is
never authority: on Windows an exclusive no-share handle is the ownership
proof, and OS release of that handle is the only stale-lock condition.
Ambiguous lock ownership fails closed and requires the named operator recovery
command and receipt.

The session-storage profile confines all objects, journals, locks, responses,
and quarantine entries to one canonical non-reparse root with owner-only ACL,
per-session and global byte quotas, retention horizons, and content-addressed
cleanup. Paths are normalized and containment-checked before open. Cleanup
requires the exact registered digest set and `artifact-cleanup` receipt; no
wildcard, timestamp, or newest-file policy can delete evidence.

W12A implements this contract through exact subcommands of
`run_cassi_qi_artifact_cleanup.py`:

```text
python run_cassi_qi_artifact_cleanup.py --mode plan --root <run-root> --expected-index-sha256 <index_sha256> --approved-digests run-spec/raw-retention-policy.json --out gates/g12a-live-runtime/artifact-cleanup/plan.json
python run_cassi_qi_artifact_cleanup.py --mode apply --root <run-root> --plan gates/g12a-live-runtime/artifact-cleanup/plan.json --expected-plan-sha256 <plan_sha256> --out gates/g12a-live-runtime/artifact-cleanup/result.json
python run_cassi_qi_artifact_cleanup.py --mode purge --root <run-root> --result gates/g12a-live-runtime/artifact-cleanup/result.json --expected-result-sha256 <result_sha256> --out gates/g12a-live-runtime/artifact-cleanup/purge.json
```

`plan` performs no mutation. `apply` moves only plan-enumerated contained
objects to digest-named quarantine; `purge` acts only on that exact quarantine
receipt. Apply and purge require an attached interactive console, redisplay the
exact root/path/digest set, and require the operator to type the full expected
plan/result digest immediately before mutation; there is no `--yes`,
noninteractive approval, or reusable approval token. Root escape, reparse
traversal, index drift, wildcard/range/timestamp expansion, a changed digest
set, or an absent/mismatched prompt response fails closed. Each mode
reopen-verifies its exact output receipt.

`source_identity_sha256` covers every enabled source epoch/stream, replay
contract, journal root, world identity, and clock. It is part of the session
head. Startup requires exact equality. Changing source or composite profile
identity always creates a new session and cannot reinterpret an existing field
trajectory.

For every external tick, including a canonical null action, the idempotency
scope domain-separates immutable `world_id`, `episode_id`, `profile_sha256`,
`session_id`, `cycle_number`, committed prior head, `from_tick`, `to_tick`, and
action hash/null-action identity. The tick intent, tick outbox, and terminal
acknowledgement repeat that complete scope. A restart after an interrupted
commit resubmits the exact canonical intent bytes and requires the stored
terminal acknowledgement for the same scope; it never emits a second action or
accepts an acknowledgement from a reset/different world. A world port that
cannot retain and resolve this identity beyond the maximum reconnect/outbox
horizon causes a visible failed cycle, not a state reset or simulated
substitute.

Old v1/v2 state and session envelopes are deliberately incompatible. The
cutover exports their transcript/audit metadata only; it does not attempt to
reinterpret a static modal state as a spatial flow state. A new flow session
starts from the declared initial field and may receive future user input, but
the old field is never silently replayed through the new boundary.

