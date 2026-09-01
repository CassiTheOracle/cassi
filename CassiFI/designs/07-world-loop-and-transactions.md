# Unified world loop and transactional causality

> CassiFI implementation plan, Part 7. [Previous](./06-memory-and-learning.md) · [Index](../README.md) · [Next](./08-language-and-serving.md)

## Unified world loop

`cassi_qi_world.py` defines `QiWorldPort`:

```python
observe(tick: int, watermark: QiWatermark) -> tuple[QiWorldObservation, ...]
describe_actions(tick: int) -> tuple[QiActionDescriptor, ...]
advance_tick(intent: QiWorldTickIntent) -> QiWorldTickAck
resolve_tick(intent: QiWorldTickIntent) -> QiWorldTickAck
```

`QiWorldTickIntent` is mandatory for every transition, including hold,
abstention, rejected, and null-action paths. It contains `world_id`,
`episode_id`, `profile_sha256`, `session_id`, `cycle_number`, `from_tick`,
`to_tick`, committed prior field-head hash, exact `action_scope` (`null` or the
canonical command identity), body-frame identity, deterministic idempotency key,
canonical bytes, and self-hash.

`resolve_tick()` accepts the exact stored canonical `QiWorldTickIntent`, not a
partial key lookup. It compares its complete typed scope
`(world_id, episode_id, profile_sha256, session_id, cycle_number, from_tick,
to_tick, committed_prior_head_sha256, action_scope_sha256,
body_frame_sha256, idempotency_key, canonical_intent_sha256)` to the
world-retained original before returning the latest status, and rejects any
scope/byte/hash mismatch. The returned acknowledgement is then compared against
that same intent scope before Commit B. It never applies or replays the command
again. Exact replay is permitted only to recover a missing terminal reply.
`advance_tick()` is the only world-time transition and cannot skip or repeat a
committed logical tick.

The deterministic reference implementation supplies raw optical, audio,
proprioceptive, and actuator consequences from an analytic bounded world. It
has ordinary fixture/world state because a world changes over time, but that
state is external environment truth, never adaptive Qi memory and never
checkpointed as part of `QiFieldState`. It contains no learned model, latent
predictor, policy, or task solver.

Python owns the monotonic unsigned `logical_tick`; adapter clocks and
`source_timestamp_ns` are opaque telemetry and are never compared across
processes for freshness. At tick `t`, the world is already committed at `t`.
The engine requests the complete watermark-bounded observation set at `t`,
computes from only those packets, and emits at most one command with
`effective_tick=t+1`. The world accepts/rejects that command, applies an
accepted command at the beginning of the `t -> t+1` transition, advances
exactly the profile's `physics_steps_per_logical_tick` fixed world steps, and
returns terminal acknowledgement plus `tick_complete(t+1)`. Observations at
`t+1` carry the terminal action ID and are the first packets allowed to show
its effect. A hold/abstention still advances the same fixed number of world
steps with a null action identity. Wrong, skipped, repeated, stale, or future
logical ticks fail closed.

`CassiQiFlowEngine.step()` owns one causal tick and one restart-safe
single-flight transaction:

1. acquire the per-session interprocess lock and load one committed field/head;
2. if a bounded tick intent is unresolved, resolve or replay only its exact
   idempotency scope before admitting new work;
3. bind each ingress to a durable journal or replayable source, then read only
   the exact watermark-bounded half-open ranges after the committed cursor;
4. reject malformed, duplicate, late, overflow, wrong-clock, or wrong-profile
   packets with explicit receipts before controller mutation;
5. validate the current body-frame identity and consume at most one previously
   committed `QiAppliedEfference`/remap marker;
6. transform all on-time observations through fixed descriptors and call
   `QiFieldController.advance()` with the ordered immutable drive bundle;
7. derive successor predictions and score action candidates through the
   world-blind `B_{r,a}` operator, including the registered finite-horizon
   no-peek observability-improvement term;
8. construct the chosen `QiActionProposal` or canonical null proposal, its
   passive motor-port reaction, bounded prediction-context descriptor, and
   canonical `QiWorldTickIntent`. For every declared scale and external/text/
   motor port, derive the transient trajectory `QiDynamicPortFrame` and
   `QiScatteringReceipt` before publication; these artifacts contain no
   persistent field or policy state;
9. **Commit A:** atomically replace the session envelope with the successor
   field/head, exact admitted-frame digests, journal head/cursor/watermark,
   response/event chain, current body-frame/world cursor, proposal/reaction,
   dynamic-port-frame and scattering-receipt identities, and at most one
   pending tick intent;
10. reopen-verify Commit A, acknowledge/reclaim committed ingress, and release
    the session lock before every network send, poll, or external world call.
    The pending intent is the durable single-flight blocker;
11. send or replay the exact tick intent and resolve its identity-matched
    terminal result without changing its bytes or idempotency scope;
12. reacquire the lock, require the Commit-A head and pending intent identity
    to be unchanged, and **Commit B** the terminal acknowledgement plus, only
    for `applied`, one `QiAppliedEfference`;
13. on the next field interval, consume that applied efference exactly once,
    apply its acknowledged body remap, require its causal IDs on self-generated
    observations, and commit the consumption marker with the next successor;
14. expose only committed output events and the receipt chain.

No session lock is held across blocking I/O. The prediction descriptor stores
only identities, horizon/operator fields, and recomputation inputs; it contains
no hidden tensor or adaptive state.

This order deliberately does not claim an impossible atomic transaction
between a filesystem checkpoint and an external actuator. The durable tick
outbox closes the crash windows:

- before the envelope commit, neither successor nor tick intent exists;
- after commit but before I/O, restart replays the stored exact tick intent;
- after tick application but before terminal-result persistence, identity
  resolution returns the world's original result without applying it again;
- if resolution is missing, malformed, unauthenticated, or conflicting after
  the bounded horizon, recovery writes the indeterminate-world-effect receipt
  and seals the lineage; it does not clear or resume the outbox.
- after acknowledgement persistence but before remap consumption, the
  `ack_consumption/remap_applied` marker makes the next field interval consume
  the exact actual effect once;
- after marker persistence, restart cannot apply that body transform again.

The field state committed in the first transaction represents perception,
internal evolution, and the emitted tick attempt. The body/efference remap
occurs only after an `applied` acknowledgement. A rejected or expired terminal
result does not require an adaptive-state rollback. An exact terminal `applied`,
`rejected`, or authenticated `expired` result, bound to the complete stored
scope before the reconnect/outbox horizon, is the only result that can resolve
the outbox.
If the world cannot authenticate that result, the transaction writes an
immutable `cassi.qi-flow-indeterminate-world-effect.v1` receipt and seals the
lineage with `lineage_status=indeterminate_sealed`. The seal is terminal for
that session: `clear`, retry, reset, null substitution, rollback, or a recovered
state cannot turn unknown external truth into continuation. Subsequent calls
fail `WORLD_EFFECT_INDETERMINATE`; a new session must establish fresh
protocol/world/source identities and cannot silently reuse the sealed
lineage or assume whether the action applied. If a world adapter cannot
guarantee idempotent tick identity plus authenticated applied truth, the motor
path fails closed.

### Indeterminate external world effect

`cassi.qi-flow-indeterminate-world-effect.v1` is the sole receipt for an
outbox whose external application truth cannot be resolved exactly. It is
content-addressed, indexed by the last valid envelope, and contains:

```text
schema = cassi.qi-flow-indeterminate-world-effect.v1
receipt_id
profile_sha256 / session_id / world_id / episode_id
cycle_number / from_tick / to_tick
lock_epoch
envelope_identity = {commit_a_head_sha256, envelope_sha256}
journal_identity = {journal_root_sha256, journal_head_sha256, committed_cursor}
intent_identity = {idempotency_key, canonical_intent_sha256, bounded_intent_bytes}
resolution_attempts[] = {
  reconnect_epoch, request_id, response_sha256, auth_status,
  observed_status = missing | malformed | identity_mismatch | conflicting
}
outbox_horizon / reconnect_horizon / retry_horizon
terminal_status = indeterminate
seal_reason
lineage_status = indeterminate_sealed
disposition = new-session-only
self_sha256
```

The receipt names the exact envelope, journal, lock epoch, and canonical intent
that were authoritative when resolution became impossible. It retains bounded
attempt metadata and never invents an `applied`, `rejected`, `expired`, or
null acknowledgement. An authenticated `resolve_tick()` that returns the exact
stored scope before sealing may still complete Commit B; any missing,
unauthenticated, malformed, stale, or conflicting result seals instead. After
the seal, the session is read-only evidence: no caller may advance its field,
consume or create efference, send the intent again, clear the outbox, or
publish a successor. A new session starts from its declared initial field and
fresh identities; it is not a continuation of unknown external truth.

### QI-TXN-001 (W12M/G12M): bounded Commit-A/Commit-B model exploration

`QiTransactionModelReceipt` is an independently generated
`cassi.qi-flow-transaction-model-receipt.v1`, not a runtime state object. The
model checker performs bounded explicit-state exploration over the complete
single-flight transaction with **two competing callers**. It must explore
caller arrival, lock contention, stale reads, crash/reconnect, and every
Commit-A/Commit-B interleaving rather than proving only a sequential happy path.
Its finite state tuple is:

```text
(caller_1 = idle | waiting | owner | released | stale | duplicate | conflict,
 caller_2 = idle | waiting | owner | released | stale | duplicate | conflict,
 lock = free | held(caller_1) | held(caller_2),
 lock_epoch = 0..profile.max_lock_epochs_per_model,
 envelope = pre-A | A-published | awaiting-terminal | B-published
            | consumed | indeterminate-sealed,
 envelope_identity = {
   predecessor_head_sha256, commit_a_head_sha256, envelope_sha256
 },
 journal_identity = {
   journal_root_sha256, journal_head_sha256, committed_cursor
 },
 outbox = none | pending | terminal | sealed,
 acknowledgement = none | rejected | expired | applied | conflicting,
 world_truth = unknown | authenticated-rejected | authenticated-expired
                | authenticated-applied | conflicting | indeterminate-sealed,
 efference = none | pending | consumed,
 ingress = uncommitted | committed | reclaimed,
 commit_b_cas = none | won(caller_1) | won(caller_2)
                 | duplicate | head-mismatch | conflict,
 crash = none | before-A | after-A | before-send | after-world-apply
         | before-resolution | before-B | after-B | before-consume
         | after-consume | before-seal | after-seal,
 replay = none | exact-intent | exact-resolution,
 response_visibility = hidden | committed | visible,
 lineage = open | indeterminate-sealed,
 retry_attempt = 0..profile.retry_horizon)
```

The identity components are finite symbolic values drawn from the registered
profile/session/world scope: caller and request identities, lock epoch,
predecessor and Commit-A envelope heads, envelope and journal identities,
intent bytes/hash/idempotency scope, terminal acknowledgement bytes/hash, and
applied-efference hash. The bounds are explicit:
`max_callers=2`, `max_outbox=1`, `max_pending_efference=1`, one terminal
acknowledgement per idempotency scope, one unresolved scope, the profile lock
epoch/retry/reconnect horizons, and a declared maximum visited state count.
No unbounded queue, transcript, caller history, or world-state history is
abstracted into the model.

The transition alphabet includes two caller arrivals; lock acquire/release at
each epoch; candidate staging; Commit-A compare-and-swap; crash/recover at
every flush, replace, send, world-apply, resolution, acknowledgement, Commit-B,
and consumption boundary; exact intent send/replay; idempotent world
application; authenticated terminal resolution; conflicting or missing
terminal results; Commit-B compare-and-swap; one-time efference consumption;
response publication; and the named operator seal path. Every transition
checks the canonical profile/session/world identity, envelope and journal
identity, lock epoch, and declared predecessor before adding a state.

An accepted caller operation linearizes at its successful Commit-A or Commit-B
under one lock epoch. The explorer must enumerate all scheduler interleavings
in which either caller reads before or after the other caller's lock release,
including a stale Commit-B reacquisition. A pass requires every accepted
two-caller trace to be equivalent to one serial order (`caller_1` then
`caller_2`, or `caller_2` then `caller_1`), with no two successors from one
predecessor. The receipt records both possible linearization orders, the
lock-epoch trace, envelope/journal identity trace, and the exact CAS outcome
for each caller.

The exact duplicate/conflict outcomes are:

| Interleaving or input | Required outcome | Mutation |
|---|---|---|
| Same complete request and scope after the winner committed | `DUPLICATE_COMMITTED` (or `DUPLICATE_COMMIT_topo` for the same terminal bytes) | return the indexed original bytes; no new action, head, or efference |
| Same predecessor/cycle scope but different intent/action bytes | `CONCURRENT_INTENT_CONFLICT` | reject both candidate mutation and world send |
| Caller reacquires with a stale lock epoch, envelope head, or journal head | `LOCK_EPOCH_MISMATCH` or `COMMIT_topo_CAS_LOST` | reload only; never overwrite the newer envelope |
| Same stored scope but different terminal acknowledgement bytes | `TERMINAL_ACK_CONFLICT` | do not choose an acknowledgement; seal `indeterminate_sealed` |
| Exact resolution unavailable after the configured horizon | `WORLD_EFFECT_INDETERMINATE` | write the indeterminate receipt and seal; no continuation |

The model must prove at least these invariants:

1. before Commit A the predecessor remains authoritative and no successor,
   outbox, world command, or response is visible;
2. one lock owner and one lock epoch linearize the two callers; an accepted
   trace has a serial order and cannot publish two Commit-A successors from one
   predecessor;
3. Commit A publishes exactly one successor and, for an action, one complete
   durable outbox/intent scope before any network send;
4. an exact duplicate returns the already indexed bytes without mutation,
   while a differing intent for the same scope has no accepting transition;
5. replay uses byte-identical intent and idempotency scope and cannot apply a
   world command twice, even across crash/reconnect;
6. a terminal acknowledgement is accepted only for the stored world/episode/
   session/cycle/head/action scope, and Commit B succeeds only when its
   compare-and-swap sees the unchanged Commit-A head, journal head, and lock
   epoch;
7. only an `applied` acknowledgement creates one pending efference, and the
   next field interval consumes that identity at most once;
8. a committed response is visible only when its exact response object is
   indexed under the corresponding commit; a world response additionally
   requires the terminal acknowledgement, while no speculative or
   post-crash-recomputed bytes become visible;
9. crash recovery selects the predecessor before Commit A and the exact
   committed envelope after Commit A, never a newest temporary or an orphan;
10. missing, unauthenticated, malformed, stale, or conflicting world truth
    transitions only to `indeterminate_sealed`; no clear, retry, reset, null
    action, or later caller can make it normal continuation;
11. an identity, cursor, lock epoch, acknowledgement, efference, CAS, or
    response mismatch has no accepting transition and therefore fails closed.

`QiTransactionModelReceipt` is canonically encoded and domain-separated with
its ordered profile subhash list, `caller_count=2`, identity-token set,
transition-set hash, explicit state/transition bounds, lock-epoch and
linearization traces, exact duplicate/conflict outcomes, initial/final
frontier hashes, covered Commit-A/Commit-B/outbox/ack/efference/crash/replay/
seal interleavings, visited-state count, invariant names/results, and
`self_sha256`. Missing a two-caller interleaving, a CAS boundary, a
lock/journal/envelope identity, a seal path, a non-exhaustive state frontier,
an omitted response-visibility case, or a boundedness declaration yields
`TRANSACTION_MODEL_INCOMPLETE`; the transaction remains unreleased. A
runtime-generated green bit cannot satisfy this receipt.


### Backpressure, limits, and failure

All limits are versioned profile fields, immutable during a session, and are enforced from frame/header
metadata before payload allocation. HTTP limits cover header bytes/count,
canonical JSON body bytes/depth, messages, per-message bytes, total prompt
bytes/symbols, output symbols/events/bytes, retained response bytes, concurrent
connections/streams, sessions, candidate clones, request wall/CPU deadline,
cancel point, lock-acquisition deadline, and active-transaction deadline; an
owned exclusive handle is never broken by a lease heuristic. World limits cover
header/payload/frame bytes, per-modality and aggregate queue bytes/events,
frames per logical tick, observations per tick, audio samples, image pixels,
heartbeat interval, idle duration, action bytes, one command in flight,
outbox age, reconnect attempts, and acknowledgement-retention ticks.

Sensory queues use one declared deterministic reject or coalesce rule and
receipt every loss. Motor commands are never silently dropped or coalesced.
Late input never rewrites an already committed field state. Timeout/disconnect
records no imagined effect, retains the latest valid field checkpoint plus one
bounded outbox record, and blocks further world evolution until an exact
authenticated resolution succeeds or the lineage is sealed indeterminate.
Automatic retries are limited to the same canonical command bytes and
idempotency scope; once the configured horizon is exhausted, no retry may
silently continue the lineage.

Clearing an unresolved command is consequential. The two executable targets
remain:

```text
python run_cassi_qi_outbox_recovery.py inspect --session <session> --world-id <world_id> --episode-id <episode_id> --idempotency-key <key> --command-sha256 <sha256>
python run_cassi_qi_outbox_recovery.py clear --session <session> --world-id <world_id> --episode-id <episode_id> --idempotency-key <key> --command-sha256 <sha256> --reason <reason>
```

`clear` reopens and displays that exact scope, requires an attached interactive
console and owner entry of the complete command digest immediately before
mutation, and refuses any changed envelope, lock epoch, journal head, or
intent. If exact authenticated `resolve_tick()` has succeeded, the runtime
must perform the normal Commit-B path and `clear` refuses to overwrite it. If
truth remains unknown, `clear` atomically commits
`cassi.qi-flow-outbox-clear.v1` together with
`cassi.qi-flow-indeterminate-world-effect.v1`, marks
`lineage_status=indeterminate_sealed`, and leaves the field/world tick
unchanged. This operator seal is not a fabricated acknowledgement, reset, or
continuation: after it, every step/retry/reconnect on that session fails
`WORLD_EFFECT_INDETERMINATE`. There is no hidden retry, CPU fallback, Qwen
fallback, static action, or simulated success.

### Deterministic replay

The external replay artifact contains immutable packet bytes, timestamps,
ordering decisions, acknowledgements, profile/operator IDs, and the receipt
hash chain. It is diagnostic evidence, not an adaptive checkpoint.

Starting from the exact initial `QiFieldState`, replay must reproduce every
state, decision, action, acknowledgement, and receipt hash on the same
backend/profile. Missing events, changed clocks, altered transforms, or a
wrong profile fail closed. CPU/ROCm replay uses the parity contract below
rather than falsely demanding cross-backend byte identity.

A restart claim that crosses a world-process restart must also restore or
replay the exact registered world initial-state/seed identity and committed
tick log, then reproduce the world-state and acknowledgement hashes. A
provider-only restart fixture holds the same world process/identity fixed and
is labeled field-local; it cannot be cited as world-restart evidence.

### QI-LINEAGE-001 (W12L/G12L): explicit state-lineage fork

`QiStateLineageForkReceipt` (`cassi.qi-flow-state-lineage-fork-receipt.v1`) is
the only operation that may copy a canonical field state into a new session.
It is an explicit `fork_state_lineage(parent_session, new_profile,
new_session, reason)` administrative operation, never resume, profile rebind,
automatic migration, or crash recovery.

The operation first validates the complete parent envelope, indexed
`cassi.qi-flow-state.v3` object, state bytes, state hash, and self-hashes. It
then loads both profile projection registries and compares the complete ordered
set marked `state_consuming`: every name must be present in both profiles and
every old/new digest must be identical. The comparison is not satisfied by
matching only `profile_sha256`, `state_contract_sha256`, or a selected subset.
If a new profile adds, removes, reclassifies, or changes any state-consuming
projection, the fork is rejected before a child envelope is created.

When that comparison passes, the child receives an exact byte copy of the
parent's canonical field-state object. The copy is verified for byte count,
content digest, tensor layout, dtype, inactive-tail zeros, and
`state_contract_sha256` before publication; no decode/repack, precision
conversion, operator remap, or state normalization is permitted. The new
`profile_sha256` may differ only through non-state-consuming profile changes,
and the receipt records the old/new complete subhash vectors and the exact
copied state-object identity.

The child is nevertheless a new protocol and world session. It receives a new
session identity and fresh protocol epoch/connection, world/episode identity,
source identity and causal clock; starts at `logical_tick=0` and
`cycle_number=0`; and performs a new world handshake before any observation or
action. The operation copies no ingress journal cursor/frontier, watermark,
request high-water mark, response chain, transcript bytes, tick outbox,
terminal acknowledgement, applied efference, remap marker, body/world
continuity, or pending external command. The parent remains unchanged and
authoritative.

The receipt records `parent_session_id`, `new_session_id`,
`parent_profile_sha256`, `new_profile_sha256`, the ordered
`state_consuming_subhashes`, parent/child state-object and byte hashes, fresh
protocol/world/source/clock identities, reset reason, operator identity,
creation timestamp telemetry, and its domain-separated `self_sha256`. It is
indexed by the child envelope while retaining a parent reference; it does not
turn the parent and child into one causal session.

Any state-subhash mismatch, changed canonical bytes, nonempty pending outbox or
efference, attempted protocol/world continuity reuse, unknown registry entry,
or field-reinterpretation request fails closed with a named lineage error and
leaves both envelopes untouched. There is no compatibility shim, silent state
conversion, copied world acknowledgement, or fallback to the predecessor
profile.

A parent carrying `lineage_status=indeterminate_sealed` is evidence-only and
cannot be used as a continuity source for a child. The indeterminate receipt
must remain reachable from the parent envelope; a child can proceed only as a
fresh, separately authenticated world/session start with no copied outbox,
acknowledgement, or external-effect assumption.


### Loopback and cross-repository boundaries

The canonical provider process owns both the HTTP server at
`127.0.0.1:8086` and, only when `world.enabled=true` and `--world-server` are
present, `QiWorldTransportServer` at `127.0.0.1:8087`. There is no separately
stateful transport process and no alternate composition. Both delegate to the
same `CassiQiFlowEngine`, session store, lock, profile, and source identity.
Live configuration rejects every non-loopback bind.

Existing ports are not reused:

- CassiCosmos `7599` remains its separate field-engine protocol and has no
  camera/audio/proprio/`cassi.qi-flow-tick-ack.v1` contract;
- CassiCore `7273` remains orchestration/tool/memory, not a raw actuator port;
- `7600`, `7601`, `8082`, `8083`, and `8084` remain their documented
  experimental/offline surfaces;
- `cassi-field-shadow.mjs` remains read-only and is not expanded into a motor
  bridge.

The complete endpoint includes a CassiCosmos world adapter in addition to the
deterministic reference world. It is mandatory scope, not a later optional
enhancement. Before any CassiCosmos edit, W13C writes the exact target brief
`CASSI-QI-WORLD-ADAPTER-BRIEF.json` containing `brief_id`, authorized owner
paths/symbols, non-goals, source/profile/protocol/schema/fixture hashes,
Python/Godot conformance vectors, port/startup/readiness interface, raw artifact
paths, battery baseline identity, and acceptance commands. Because it crosses
an independent repository, the owner must authorize that exact brief; until
then G13C is `BLOCKED`, never reduced to the reference world.

The target adapter owns raw sensor capture, fixed-step world transition,
actuator application, retained acknowledgement truth, and a world-identity
digest. CassiQwen owns logical ticks, event ordering, fixed transforms,
`QiFieldState`, prediction, action choice, and receipts. The adapter uses the
new world transport, not `7599 deposit/step`, and cannot own a second Qi field.
Its Godot scene is default-off and its GPU/render exercise is windowed. Before
W13C, G0 freezes a `cassi.qi-flow-adapter-off-evidence.v1` baseline manifest
with exact canonical bytes, schema, byte count, and digest for the profile,
source/clock/operator identities, field/checkpoint/step/ledger/decision/
response artifacts, wire trace, process/socket inventory, anchors, and battery
outputs. With the adapter disabled after W13C, every deterministic artifact and
its digest must compare byte-for-byte with that manifest; a fresh 30/30 run or
numerically similar anchors is insufficient. The only exception is a path
explicitly marked `volatile` by the schema registry, whose raw bytes remain
retained and whose registered deterministic projection and mutation-control
receipt are compared instead. No field, checkpoint, physics, work, state hash,
profile, decision, or protocol identity may be projected. Unknown volatility,
an unregistered projection, or any altered deterministic byte fails QI-EVID-001
closed.

### External world wire protocol

`QiWorldTransportServer` implements `cassi.qi-world-wire.v1`. Each frame is:

```text
uint32_be canonical_json_header_bytes
uint32_be raw_payload_bytes
canonical UTF-8 JSON header
raw payload bytes
```

Both lengths are checked against profile maxima before allocation. Headers use
the exact `cassi.canonical-json.v1` contract: keys are unique and sorted by
unsigned UTF-8 bytes, string scalar sequences are preserved without Unicode
normalization, finite scalars use the registered bit encoding, and no
whitespace, BOM, or trailing newline is present.
Every frame carries only this common header:

```text
schema, protocol_version, kind
run_id, episode_id, world_id, session_id
connection_sequence, message_sequence
request_id, response_to
profile_sha256, boundary_registry_sha256, clock_sha256
payload_bytes, payload_sha256
auth_key_id, auth_nonce, auth_sha256
```

The registry then requires fields by `kind`, with no mandatory-null
placeholders:

- observations add logical tick, rational capture interval, source
  epoch/stream/sequence, watermark, body frame, dtype, shape, and physical unit;
- advance/resolve frames add logical/effective tick, cycle, committed prior
  head, proposal/action digest, and complete idempotency scope;
- tick-complete adds terminal status, exact requested/applied values and ticks,
  first visible observation tick, body transition, and original-result digest;
- action descriptors add only fixed geometry, cost, bounds, capability, and
  operator identity;
- hello/heartbeat/close/error carry only their registered negotiation,
  liveness, closure, or error fields.

Unknown fields, missing kind-required fields, or unrelated null placeholders
are rejected. `request_id` is unique within
`(run,episode,world,connection)`; every response repeats it as `response_to`.
Message sequence is contiguous in each direction. The allowed kinds and exact
request/response pairs are:

```text
hello -> hello_ack
observe_request -> observation* + observation_complete
describe_actions -> action_descriptors
advance_tick -> tick_complete
resolve_tick -> tick_complete
heartbeat -> heartbeat_ack
close -> close_ack
error
```

The top-level mapping is exact:

| Wire kind | Direction / correlation | Sole payload schema |
|---|---|---|
| `hello` | client request | `cassi.qi-world-hello.v1` |
| `hello_ack` | response to `hello` | `cassi.qi-world-hello-ack.v1` |
| `observe_request` | client request | `cassi.qi-world-observe-request.v1` |
| `observation` | repeated response to `observe_request` | `cassi.qi-world-observation.v1` |
| `observation_complete` | terminal response to `observe_request` | `cassi.qi-world-observation-complete.v1` |
| `describe_actions` | client request | `cassi.qi-world-describe-actions.v1` |
| `action_descriptors` | response to `describe_actions` | `cassi.qi-world-action-descriptors.v1` |
| `advance_tick` | client request | `cassi.qi-world-advance-tick.v1` |
| `resolve_tick` | client request | `cassi.qi-world-resolve-tick.v1` |
| `tick_complete` | terminal response to `advance_tick` or `resolve_tick` | `cassi.qi-world-tick-complete.v1` |
| `heartbeat` | client request | `cassi.qi-world-heartbeat.v1` |
| `heartbeat_ack` | response to `heartbeat` | `cassi.qi-world-heartbeat-ack.v1` |
| `close` | client request | `cassi.qi-world-close.v1` |
| `close_ack` | response to `close` | `cassi.qi-world-close-ack.v1` |
| `error` | authenticated failure response | `cassi.qi-world-error.v1` |

Both `advance_tick` and `resolve_tick` contain exactly one nested
`cassi.qi-flow-tick-intent.v1`; its `action_scope` contains either null or one
nested `cassi.qi-flow-action.v1`. For `resolve_tick`, those nested canonical
intent bytes and `canonical_intent_sha256` must equal the world-retained
original byte-for-byte; it is not a partial-key request. `tick_complete`
contains one nested `cassi.qi-flow-tick-ack.v1`. Nested schemas are never
additional top-level wire kinds. The frame header itself is
`cassi.qi-world-frame.v1`; the outer `cassi.qi-world-wire.v1` registry fixes
this mapping, direction, request/response relation, and maximum
canonical-header/raw-payload byte count.

Python assigns `logical_tick`; the adapter echoes it and supplies only its own
opaque capture-clock telemetry. Stale/future checks use logical tick, message
sequence, and request correlation, never nanosecond-clock comparison.

Loopback is not authentication. G0 provisions one 256-bit per-run world secret
with the OS CSPRNG outside the adaptive/runtime graph, stores it under the
owner-only run DACL, and gives the same key ID/secret to the provider and
authorized Godot client. Each connection begins with a never-reused 128-bit
client nonce and strictly increasing connection sequence; each direction then
uses contiguous message sequence.

Every transmitted frame is authenticated, including the two outer lengths and
raw payload. Let `H_0` be the exact canonical header with `auth_sha256`
replaced by sixty-four ASCII zeroes, which preserves the transmitted header
length. The authenticated bytes are

```text
frame(utf8("cassi.qi-world-auth.v1")) ||
uint32_be(transmitted_header_bytes) ||
uint32_be(raw_payload_bytes) ||
H_0 ||
raw_payload
```

`auth_sha256` is the lowercase hexadecimal HMAC-SHA256 of those bytes. The
receiver checks both lengths before allocation, reconstructs `H_0`, verifies
HMAC in constant time, verifies `payload_bytes/payload_sha256`, and only then
decodes kind-specific content. `hello_ack` binds the client nonce, server
process-creation identity, and negotiated identities in its authenticated
payload. The server persists a bounded connection-sequence high-water mark and
nonce digest set for the complete reconnect horizon; missing, replayed,
wrong-key, reordered, length-mutated, payload-mutated, or identity-changing
authentication fails closed. The explicit security boundary is a trusted local
Windows account with read access to that secret/run directory; the protocol
does not claim protection from compromise of that account.

Raw numeric payloads are canonical little-endian contiguous arrays whose
dtype/shape/unit/frame are declared in the header. There is no pickle, Torch
serialization, Godot `Variant` serialization, arbitrary object
deserialization, compression, path, shell text, URL, or semantic-label field
on the wire. The protocol fixture suite freezes valid and invalid Python/Godot
byte vectors for canonical JSON, HMAC, length, array, correlation, reconnect,
and status behavior.

The CassiCosmos adapter is a client of this transport:

- one declared `SubViewport` supplies calibrated raw optical frames/event
  increments at the profile cadence;
- one declared `AudioEffectCapture` path supplies raw waveform windows;
  audio is required in `qi-flow-full-v1`, and a missing capture/capability
  makes G13C `BLOCKED`;
- camera/body pose, velocities, contacts, and applied actuator values supply
  proprioception;
- text for the same grounded episode enters through the provider's W11 text
  boundary, with the identical session/episode/logical tick and a registered
  cross-modal schedule; Godot neither synthesizes nor semantically labels text;
- action descriptors expose camera gaze and declared bounded body controls,
  never candidate renderings or future frames;
- `advance_tick`/`resolve_tick` retain the original identity-matched terminal
  tick completion for at least `max_outbox_age + reconnect_horizon +
  retry_horizon` ticks;
- disabled means no socket, capture, actuator, allocation, or simulation
  behavior change.

Startup uses one versioned sequence: start
`python cassi_persistent_provider.py --config conscious-chat.json
--world-server`; wait until `/health` identifies the exact source/profile and
reports HTTP ready plus world port `awaiting_peer`; start the authorized
windowed Godot adapter scene; complete authenticated `hello`; then require
health fields `world_ready=true`, port, peer process/world/episode identity,
logical tick, audio/optical/proprio/motor capabilities, and retention horizon
before the exercise sends any input.

The focused Godot scene captures raw wire/world artifacts and exits with a
validation result. G0 captures a pre-adapter 30-arm battery receipt plus the
load-bearing deterministic `verify_river_isotropy` anchors and every existing
deterministic trace hash exposed by the battery. G13C reruns 30/30 and requires
exact equality of those baseline anchors/hashes when the adapter is disabled;
a green exit alone is insufficient. The adapter does not require or modify a
GPU compute shader, local RenderingDevice, SPIR-V layout, or existing
push-constant contract.

