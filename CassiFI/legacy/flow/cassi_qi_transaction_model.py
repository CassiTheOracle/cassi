"""Independent bounded W12M transaction model and sealed-effect evidence.

The module is deliberately runtime-free.  It models the exact W1 scope used by
Commit-A/Commit-B and emits only the frozen indexed receipt shapes.  Unknown
external truth is unresolved while the horizon is open; publication of the
indeterminate receipt seals the lineage permanently.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field, replace
from enum import Enum
from itertools import permutations, product
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes


MODEL_RECEIPT_SCHEMA = "cassi.qi-flow-transaction-model-receipt.v1"
INDETERMINATE_SCHEMA = "cassi.qi-flow-indeterminate-world-effect.v1"
RESOLUTION_PROOF_SCHEMA = "cassi.qi-flow-resolution-proof.v1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class QiTransactionError(ValueError):
    """Raised when a transition is outside the frozen transaction model."""


class ExternalTruth(str, Enum):
    NONE = "none"
    UNKNOWN = "unknown"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ReplayClass(str, Enum):
    DUPLICATE_COMMITTED = "DUPLICATE_COMMITTED"
    CONCURRENT_INTENT_CONFLICT = "CONCURRENT_INTENT_CONFLICT"
    LOCK_EPOCH_MISMATCH = "LOCK_EPOCH_MISMATCH"
    COMMIT_A_CAS_LOST = "COMMIT_topo_CAS_LOST"
    TERMINAL_ACK_CONFLICT = "TERMINAL_ACK_CONFLICT"
    WORLD_EFFECT_INDETERMINATE = "WORLD_EFFECT_INDETERMINATE"
    SOURCE_REPLAY = "SOURCE_REPLAY"


_TERMINAL = frozenset({ExternalTruth.APPLIED, ExternalTruth.REJECTED, ExternalTruth.EXPIRED})
_SEMANTIC_ORDER = (
    "state_contract_sha256",
    "boundary_action_sha256",
    "world_protocol_sha256",
    "session_storage_sha256",
    "provider_api_sha256",
    "backend_capacity_sha256",
    "security_evidence_sha256",
)
_RECEIPT_PARENTS = ("world_protocol_sha256", "session_storage_sha256", "security_evidence_sha256")
_CRASH_POINTS = (
    "none",
    "before-A",
    "after-A",
    "before-send",
    "after-world-apply",
    "before-resolution",
    "before-B",
    "after-B",
    "before-consume",
    "after-consume",
    "before-seal",
    "after-seal",
)
_REPLAY_POINTS = ("none", "exact-intent", "exact-resolution")
_ACK_POINTS = ("none", "rejected", "expired", "applied", "conflicting", "indeterminate-sealed")


def _required(value: str, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise QiTransactionError(f"{name} must be a nonempty string")
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: str, name: str) -> str:
    _required(value, name)
    if not _HEX64.fullmatch(value):
        raise QiTransactionError(f"{name} must be a lowercase SHA-256 identity")
    return value


def _token(name: str) -> str:
    return canonical_hash({"token": name}, f"cassi.qi-flow-transaction-token.{name}")


def _mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


def _parent_vector(seed: str = "transaction-model") -> tuple[dict[str, str], ...]:
    return tuple({"name": name, "sha256": _token(f"{seed}:{name}")} for name in _RECEIPT_PARENTS)


@dataclass(frozen=True, slots=True)
class QiPreparedTransaction:
    """Complete immutable candidate scope presented to Commit-A."""

    caller_id: str
    retry_key: str
    request_sha256: str
    predecessor_head: int
    ingress_cursor: int
    response_sha256: str
    proposal_sha256: str
    outbox_sha256: str
    session_id: str = "session-0"
    world_id: str = "world-0"
    episode_id: str = "episode-0"
    cycle_number: int = 0
    from_tick: int = 0
    to_tick: int = 1
    idempotency_key: str | None = None
    committed_prior_head_sha256: str | None = None
    body_frame_id: str = "body.0"
    action_scope_sha256: str | None = None
    port_reaction_sha256: str | None = None
    action_sha256: str | None = None
    intent_bytes: bytes | None = None
    profile_sha256: str = field(default_factory=lambda: _token("profile"))
    contract_root_sha256: str = field(default_factory=lambda: _token("contract-root"))

    def __post_init__(self) -> None:
        for name in (
            "caller_id",
            "retry_key",
            "request_sha256",
            "response_sha256",
            "proposal_sha256",
            "outbox_sha256",
            "session_id",
            "world_id",
            "episode_id",
            "body_frame_id",
            "profile_sha256",
            "contract_root_sha256",
        ):
            _required(getattr(self, name), name)
        _digest(self.profile_sha256, "profile_sha256")
        _digest(self.contract_root_sha256, "contract_root_sha256")
        for name in ("predecessor_head", "ingress_cursor", "cycle_number", "from_tick", "to_tick"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise QiTransactionError(f"{name} must be a nonnegative integer")
        if self.to_tick != self.from_tick + 1:
            raise QiTransactionError("to_tick must equal from_tick + 1")
        if self.idempotency_key is not None:
            _digest(self.idempotency_key, "idempotency_key")
        if self.committed_prior_head_sha256 is not None:
            _digest(self.committed_prior_head_sha256, "committed_prior_head_sha256")
        for name in ("action_scope_sha256", "port_reaction_sha256", "action_sha256"):
            value = getattr(self, name)
            if value is not None:
                _digest(value, name)
        if self.intent_bytes is not None and (not isinstance(self.intent_bytes, bytes) or not self.intent_bytes):
            raise QiTransactionError("intent_bytes must be nonempty bytes")

    @property
    def effective_idempotency_key(self) -> str:
        return self.idempotency_key or _token(f"idempotency:{self.retry_key}")

    @property
    def effective_committed_prior_head_sha256(self) -> str:
        return self.committed_prior_head_sha256 or _token(f"head:{self.predecessor_head}")

    @property
    def effective_action_scope_sha256(self) -> str:
        return self.action_scope_sha256 or _token("action-scope:null")

    @property
    def canonical_intent_bytes(self) -> bytes:
        if self.intent_bytes is not None:
            return self.intent_bytes
        return canonical_json_bytes(
            {
                "world_id": self.world_id,
                "episode_id": self.episode_id,
                "session_id": self.session_id,
                "cycle_number": self.cycle_number,
                "from_tick": self.from_tick,
                "to_tick": self.to_tick,
                "committed_prior_head_sha256": self.effective_committed_prior_head_sha256,
                "body_frame_id": self.body_frame_id,
                "action_scope_sha256": self.effective_action_scope_sha256,
                "idempotency_key": self.effective_idempotency_key,
            }
        )

    @property
    def canonical_intent_sha256(self) -> str:
        return _sha256(self.canonical_intent_bytes)

    @property
    def bounded_intent_bytes(self) -> str:
        if len(self.canonical_intent_bytes) > 65536:
            raise QiTransactionError("canonical intent exceeds 65,536 bytes")
        return base64.b64encode(self.canonical_intent_bytes).decode("ascii")

    @property
    def idempotency_scope_sha256(self) -> str:
        return canonical_hash(
            {
                "world_id": self.world_id,
                "episode_id": self.episode_id,
                "profile_sha256": self.profile_sha256,
                "session_id": self.session_id,
                "cycle_number": self.cycle_number,
                "from_tick": self.from_tick,
                "to_tick": self.to_tick,
                "committed_prior_head_sha256": self.effective_committed_prior_head_sha256,
                "action_scope_sha256": self.effective_action_scope_sha256,
                "body_frame_id": self.body_frame_id,
                "idempotency_key": self.effective_idempotency_key,
                "canonical_intent_sha256": self.canonical_intent_sha256,
            },
            "cassi.qi-flow-idempotency-scope.v1",
        )

    def scope_identity(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "episode_id": self.episode_id,
            "profile_sha256": self.profile_sha256,
            "session_id": self.session_id,
            "cycle_number": self.cycle_number,
            "from_tick": self.from_tick,
            "to_tick": self.to_tick,
            "committed_prior_head_sha256": self.effective_committed_prior_head_sha256,
            "action_scope_sha256": self.effective_action_scope_sha256,
            "body_frame_id": self.body_frame_id,
            "idempotency_key": self.effective_idempotency_key,
            "canonical_intent_sha256": self.canonical_intent_sha256,
        }


@dataclass(frozen=True, slots=True)
class QiIndeterminateWorldEffectReceipt:
    """Exact immutable indexed evidence emitted by an outbox seal."""

    session_id: str
    world_id: str
    episode_id: str
    cycle_number: int
    from_tick: int
    to_tick: int
    lock_epoch: int
    envelope_identity: Mapping[str, str]
    journal_identity: Mapping[str, str]
    intent_identity: Mapping[str, str]
    resolution_attempts: tuple[Mapping[str, Any], ...]
    outbox_horizon: int
    reconnect_horizon: int
    retry_horizon: int
    seal_reason: str
    profile_sha256: str = field(default_factory=lambda: _token("profile"))
    contract_root_sha256: str = field(default_factory=lambda: _token("contract-root"))
    consumed_semantic_subhashes: tuple[Mapping[str, str], ...] = field(default_factory=_parent_vector)
    receipt_id: str | None = None
    self_sha256: str | None = None

    def __post_init__(self) -> None:
        for name in ("session_id", "world_id", "episode_id", "seal_reason"):
            _required(getattr(self, name), name)
        for name in ("profile_sha256", "contract_root_sha256"):
            _digest(getattr(self, name), name)
        for name in ("cycle_number", "from_tick", "to_tick", "lock_epoch"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise QiTransactionError(f"{name} must be a nonnegative integer")
        if self.to_tick != self.from_tick + 1:
            raise QiTransactionError("to_tick must equal from_tick + 1")
        for name in ("outbox_horizon", "reconnect_horizon", "retry_horizon"):
            value = getattr(self, name)
            if not isinstance(value, int) or not 1 <= value <= 4096:
                raise QiTransactionError(f"{name} must be in 1..4096")
        envelope = dict(self.envelope_identity)
        journal = dict(self.journal_identity)
        intent = dict(self.intent_identity)
        for name in ("commit_a_head_sha256", "envelope_sha256"):
            _digest(str(envelope.get(name, "")), f"envelope_identity.{name}")
        for name in ("journal_root_sha256", "journal_head_sha256", "committed_cursor_sha256"):
            _digest(str(journal.get(name, "")), f"journal_identity.{name}")
        _digest(str(intent.get("idempotency_key", "")), "intent_identity.idempotency_key")
        _digest(str(intent.get("canonical_intent_sha256", "")), "intent_identity.canonical_intent_sha256")
        bounded = intent.get("bounded_intent_bytes")
        if not isinstance(bounded, str):
            raise QiTransactionError("intent_identity.bounded_intent_bytes must be base64")
        try:
            raw = base64.b64decode(bounded.encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError) as error:
            raise QiTransactionError("intent_identity.bounded_intent_bytes is not canonical base64") from error
        if len(raw) > 65536:
            raise QiTransactionError("intent_identity.bounded_intent_bytes exceeds 65,536 bytes")
        attempts = tuple(dict(row) for row in self.resolution_attempts)
        if len(attempts) > 4096:
            raise QiTransactionError("resolution_attempts exceeds 4,096")
        for row in attempts:
            if set(row) != {"reconnect_epoch", "request_id", "response_sha256", "auth_status", "observed_status"}:
                raise QiTransactionError("resolution attempt has an unexpected shape")
            if not isinstance(row["reconnect_epoch"], int) or row["reconnect_epoch"] < 0:
                raise QiTransactionError("invalid reconnect_epoch")
            _required(str(row["request_id"]), "resolution_attempts.request_id")
            _digest(str(row["response_sha256"]), "resolution_attempts.response_sha256")
            allowed = {"missing", "malformed", "identity_mismatch", "conflicting"}
            if row["auth_status"] not in allowed or row["observed_status"] not in allowed:
                raise QiTransactionError("invalid resolution attempt status")
        if tuple(sorted(attempts, key=lambda row: (row["reconnect_epoch"], row["request_id"]))) != attempts:
            raise QiTransactionError("resolution_attempts must be sorted")
        subhashes = tuple(dict(row) for row in self.consumed_semantic_subhashes)
        expected_names = tuple(row["name"] for row in subhashes)
        if not subhashes or expected_names != tuple(name for name in _SEMANTIC_ORDER if name in expected_names):
            raise QiTransactionError("consumed_semantic_subhashes must be ordered registry subset")
        for row in subhashes:
            if set(row) != {"name", "sha256"} or row["name"] not in _SEMANTIC_ORDER:
                raise QiTransactionError("invalid consumed semantic subhash")
            _digest(str(row["sha256"]), f"consumed_semantic_subhashes.{row['name']}")
        object.__setattr__(self, "envelope_identity", _mapping(envelope))
        object.__setattr__(self, "journal_identity", _mapping(journal))
        object.__setattr__(self, "intent_identity", _mapping(intent))
        object.__setattr__(self, "resolution_attempts", attempts)
        object.__setattr__(self, "consumed_semantic_subhashes", subhashes)
        core = self._core_payload()
        receipt_id = self.receipt_id or "indet." + canonical_hash(core, INDETERMINATE_SCHEMA + ".id")[:32]
        self_hash = canonical_hash({**core, "receipt_id": receipt_id}, INDETERMINATE_SCHEMA)
        if self.self_sha256 is not None and self.self_sha256 != self_hash:
            raise QiTransactionError("indeterminate receipt self hash mismatch")
        object.__setattr__(self, "receipt_id", receipt_id)
        object.__setattr__(self, "self_sha256", self_hash)

    def _core_payload(self) -> dict[str, Any]:
        return {
            "schema": INDETERMINATE_SCHEMA,
            "receipt_id": self.receipt_id,
            "contract_root_sha256": self.contract_root_sha256,
            "profile_sha256": self.profile_sha256,
            "consumed_semantic_subhashes": [dict(row) for row in self.consumed_semantic_subhashes],
            "session_id": self.session_id,
            "world_id": self.world_id,
            "episode_id": self.episode_id,
            "cycle_number": self.cycle_number,
            "from_tick": self.from_tick,
            "to_tick": self.to_tick,
            "lock_epoch": self.lock_epoch,
            "envelope_identity": dict(self.envelope_identity),
            "journal_identity": dict(self.journal_identity),
            "intent_identity": dict(self.intent_identity),
            "resolution_attempts": [dict(row) for row in self.resolution_attempts],
            "outbox_horizon": self.outbox_horizon,
            "reconnect_horizon": self.reconnect_horizon,
            "retry_horizon": self.retry_horizon,
            "terminal_status": "indeterminate",
            "seal_reason": self.seal_reason,
            "lineage_status": "indeterminate_sealed",
            "disposition": "new-session-only",
        }

    def payload(self) -> dict[str, Any]:
        core = self._core_payload()
        return {**core, "self_sha256": self.self_sha256}

    to_payload = payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QiIndeterminateWorldEffectReceipt":
        if not isinstance(payload, Mapping):
            raise QiTransactionError("indeterminate receipt must be an object")
        required = (
            "session_id", "world_id", "episode_id", "cycle_number", "from_tick", "to_tick", "lock_epoch",
            "envelope_identity", "journal_identity", "intent_identity", "resolution_attempts",
            "outbox_horizon", "reconnect_horizon", "retry_horizon", "seal_reason", "profile_sha256",
            "contract_root_sha256", "consumed_semantic_subhashes", "receipt_id", "self_sha256",
        )
        if payload.get("schema") != INDETERMINATE_SCHEMA or any(key not in payload for key in required):
            raise QiTransactionError("indeterminate receipt has missing or incorrect fields")
        value = cls(**{key: payload[key] for key in required})
        if payload != value.payload():
            raise QiTransactionError("indeterminate receipt is not canonically encoded")
        return value


QiIndeterminateWorldEffect = QiIndeterminateWorldEffectReceipt


@dataclass(frozen=True, slots=True)
class QiTransactionState:
    """Immutable state tuple used by the bounded explorer and W12A."""

    head: int = 0
    ingress_cursor: int = 0
    commit_a_count: int = 0
    commit_b_count: int = 0
    caller_1_status: str = "idle"
    caller_2_status: str = "idle"
    lock: str = "free"
    lock_epoch: int = 0
    envelope_stage: str = "pre-A"
    predecessor_head_sha256: str | None = None
    envelope_identity: Mapping[str, str] = field(default_factory=dict)
    journal_identity: Mapping[str, str] = field(default_factory=dict)
    outbox_status: str = "none"
    external_truth: ExternalTruth = ExternalTruth.NONE
    terminal_acknowledgement_sha256: str | None = None
    applied_efference_sha256: str | None = None
    efference_status: str = "none"
    ingress_state: str = "uncommitted"
    commit_b_cas: str = "none"
    crash: str = "none"
    replay: str = "none"
    response_visibility: str = "hidden"
    lineage_status: str = "open"
    retry_attempt: int = 0
    sealed_indeterminate: bool = False
    indeterminate_receipt_sha256: str | None = None
    resolution_attempts: tuple[Mapping[str, Any], ...] = ()
    caller_id: str | None = None
    retry_key: str | None = None
    request_sha256: str | None = None
    response_sha256: str | None = None
    proposal_sha256: str | None = None
    outbox_sha256: str | None = None
    world_id: str = "world-0"
    episode_id: str = "episode-0"
    session_id: str = "session-0"
    cycle_number: int = 0
    from_tick: int = 0
    to_tick: int = 1
    profile_sha256: str = field(default_factory=lambda: _token("profile"))
    contract_root_sha256: str = field(default_factory=lambda: _token("contract-root"))
    body_frame_id: str = "body.0"
    action_scope_sha256: str | None = None
    idempotency_key: str | None = None
    canonical_intent_sha256: str | None = None
    bounded_intent_bytes: str | None = None
    outbox_horizon: int = 1
    reconnect_horizon: int = 1
    retry_horizon: int = 1
    world_protocol_sha256: str = field(default_factory=lambda: _token("world-protocol"))
    session_storage_sha256: str = field(default_factory=lambda: _token("session-storage"))
    security_evidence_sha256: str = field(default_factory=lambda: _token("security-evidence"))

    def __post_init__(self) -> None:
        if not isinstance(self.external_truth, ExternalTruth):
            try:
                object.__setattr__(self, "external_truth", ExternalTruth(self.external_truth))
            except (TypeError, ValueError) as error:
                raise QiTransactionError("invalid external truth") from error
        for name in ("head", "ingress_cursor", "commit_a_count", "commit_b_count", "lock_epoch", "retry_attempt", "cycle_number", "from_tick", "to_tick", "outbox_horizon", "reconnect_horizon", "retry_horizon"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise QiTransactionError(f"{name} must be a nonnegative integer")
        if self.commit_a_count not in (0, 1) or self.commit_b_count not in (0, 1) or self.commit_b_count > self.commit_a_count:
            raise QiTransactionError("invalid Commit-A/Commit-B counts")
        if self.world_effect_count > 1:
            raise QiTransactionError("at most one applied world effect is permitted")
        if self.to_tick != self.from_tick + 1:
            raise QiTransactionError("to_tick must equal from_tick + 1")
        for name in ("world_id", "episode_id", "session_id", "body_frame_id", "lock", "envelope_stage", "outbox_status", "efference_status", "ingress_state", "commit_b_cas", "crash", "replay", "response_visibility", "lineage_status"):
            _required(str(getattr(self, name)), name)
        for name in ("profile_sha256", "contract_root_sha256", "world_protocol_sha256", "session_storage_sha256", "security_evidence_sha256"):
            _digest(getattr(self, name), name)
        sealed = self.lineage_status == "indeterminate_sealed"
        if self.sealed_indeterminate != sealed:
            raise QiTransactionError("sealed_indeterminate and lineage_status disagree")
        if sealed and self.external_truth is not ExternalTruth.UNKNOWN:
            raise QiTransactionError("sealed lineage must retain unknown truth")
        if self.commit_b_count and self.external_truth not in _TERMINAL:
            raise QiTransactionError("Commit-B requires terminal truth")
        if self.applied_efference_sha256 is not None and self.external_truth is not ExternalTruth.APPLIED:
            raise QiTransactionError("only applied truth may carry an efference")
        for mapping_name in ("envelope_identity", "journal_identity"):
            value = dict(getattr(self, mapping_name))
            object.__setattr__(self, mapping_name, _mapping(value))
        object.__setattr__(self, "resolution_attempts", tuple(dict(row) for row in self.resolution_attempts))

    @property
    def world_effect_count(self) -> int:
        return 1 if self.applied_efference_sha256 is not None else 0

    @property
    def sealed(self) -> bool:
        return self.lineage_status == "indeterminate_sealed"

    @property
    def committed_response_sha256(self) -> str | None:
        return self.response_sha256 if self.commit_a_count else None

    @property
    def intent_identity(self) -> Mapping[str, str]:
        return _mapping(
            {
                "idempotency_key": self.idempotency_key or _token("unknown-idempotency"),
                "canonical_intent_sha256": self.canonical_intent_sha256 or _token("unknown-intent"),
                "bounded_intent_bytes": self.bounded_intent_bytes or base64.b64encode(b"unknown-intent").decode("ascii"),
            }
        )

    @property
    def sealed_indeterminate_receipt(self) -> QiIndeterminateWorldEffectReceipt | None:
        if not self.sealed:
            return None
        return self.indeterminate_receipt()

    def state_tuple(self) -> dict[str, Any]:
        return {
            "caller_1": self.caller_1_status,
            "caller_2": self.caller_2_status,
            "lock": self.lock,
            "lock_epoch": self.lock_epoch,
            "envelope": self.envelope_stage,
            "envelope_identity": dict(self.envelope_identity),
            "journal_identity": dict(self.journal_identity),
            "outbox": self.outbox_status,
            "acknowledgement": "none" if self.external_truth in {ExternalTruth.NONE, ExternalTruth.UNKNOWN} else ("applied" if self.external_truth is ExternalTruth.APPLIED else self.external_truth.value),
            "world_truth": "unknown" if self.external_truth is ExternalTruth.NONE else ({ExternalTruth.APPLIED: "authenticated-applied", ExternalTruth.REJECTED: "authenticated-rejected", ExternalTruth.EXPIRED: "authenticated-expired", ExternalTruth.UNKNOWN: "unknown"}[self.external_truth]),
            "efference": self.efference_status,
            "ingress": self.ingress_state,
            "commit_b_cas": self.commit_b_cas,
            "crash": self.crash,
            "replay": self.replay,
            "response_visibility": self.response_visibility,
            "lineage": self.lineage_status,
            "retry_attempt": self.retry_attempt,
        }

    def payload(self) -> dict[str, Any]:
        return {
            "head": self.head,
            "ingress_cursor": self.ingress_cursor,
            "commit_a_count": self.commit_a_count,
            "commit_b_count": self.commit_b_count,
            **self.state_tuple(),
            "external_truth": self.external_truth.value,
            "sealed_indeterminate": self.sealed_indeterminate,
            "terminal_acknowledgement_sha256": self.terminal_acknowledgement_sha256,
            "applied_efference_sha256": self.applied_efference_sha256,
            "response_sha256": self.response_sha256,
            "proposal_sha256": self.proposal_sha256,
            "outbox_sha256": self.outbox_sha256,
            "caller_id": self.caller_id,
            "retry_key": self.retry_key,
            "request_sha256": self.request_sha256,
            "world_id": self.world_id,
            "episode_id": self.episode_id,
            "session_id": self.session_id,
            "cycle_number": self.cycle_number,
            "from_tick": self.from_tick,
            "to_tick": self.to_tick,
            "profile_sha256": self.profile_sha256,
            "contract_root_sha256": self.contract_root_sha256,
            "body_frame_id": self.body_frame_id,
            "action_scope_sha256": self.action_scope_sha256,
            "idempotency_key": self.idempotency_key,
            "canonical_intent_sha256": self.canonical_intent_sha256,
            "bounded_intent_bytes": self.bounded_intent_bytes,
            "indeterminate_receipt_sha256": self.indeterminate_receipt_sha256,
            "resolution_attempts": [dict(row) for row in self.resolution_attempts],
        }

    def _resolution_scope(self, truth: ExternalTruth, acknowledgement_sha256: str) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "episode_id": self.episode_id,
            "profile_sha256": self.profile_sha256,
            "session_id": self.session_id,
            "cycle_number": self.cycle_number,
            "from_tick": self.from_tick,
            "to_tick": self.to_tick,
            "committed_prior_head_sha256": self.predecessor_head_sha256 or _token(f"head:{max(self.head - 1, 0)}"),
            "action_scope_sha256": self.action_scope_sha256 or _token("action-scope:null"),
            "body_frame_id": self.body_frame_id,
            "idempotency_key": self.idempotency_key or _token("unknown-idempotency"),
            "canonical_intent_sha256": self.canonical_intent_sha256 or _token("unknown-intent"),
            "truth": truth.value,
            "acknowledgement_sha256": acknowledgement_sha256,
        }

    def authenticated_resolution_proof(self, truth: ExternalTruth, acknowledgement_sha256: str) -> str:
        if truth not in _TERMINAL:
            raise QiTransactionError("resolution proof requires terminal truth")
        _digest(acknowledgement_sha256, "acknowledgement_sha256")
        return canonical_hash(self._resolution_scope(truth, acknowledgement_sha256), RESOLUTION_PROOF_SCHEMA)

    def _candidate_equal(self, prepared: QiPreparedTransaction) -> bool:
        return self.commit_a_count == 1 and self.idempotency_key == prepared.effective_idempotency_key and self.canonical_intent_sha256 == prepared.canonical_intent_sha256 and self.response_sha256 == prepared.response_sha256 and self.proposal_sha256 == prepared.proposal_sha256 and self.outbox_sha256 == prepared.outbox_sha256 and self.caller_id == prepared.caller_id and self.ingress_cursor == prepared.ingress_cursor

    def commit_a(self, prepared: QiPreparedTransaction) -> tuple["QiTransactionState", str]:
        if not isinstance(prepared, QiPreparedTransaction):
            raise QiTransactionError("Commit-A requires QiPreparedTransaction")
        if self.sealed:
            raise QiTransactionError(ReplayClass.WORLD_EFFECT_INDETERMINATE.value)
        if self.commit_a_count:
            if self._candidate_equal(prepared):
                return self, "replay"
            if self.idempotency_key == prepared.effective_idempotency_key or self.retry_key == prepared.retry_key:
                raise QiTransactionError(ReplayClass.CONCURRENT_INTENT_CONFLICT.value)
            raise QiTransactionError(ReplayClass.COMMIT_A_CAS_LOST.value)
        if prepared.predecessor_head != self.head:
            raise QiTransactionError(ReplayClass.COMMIT_A_CAS_LOST.value)
        if prepared.ingress_cursor < self.ingress_cursor:
            raise QiTransactionError(ReplayClass.COMMIT_A_CAS_LOST.value)
        head = self.head + 1
        envelope = {
            "predecessor_head_sha256": prepared.effective_committed_prior_head_sha256,
            "commit_a_head_sha256": canonical_hash({"prior": prepared.effective_committed_prior_head_sha256, "intent": prepared.canonical_intent_sha256}, "cassi.qi-flow-envelope-head.v1"),
            "envelope_sha256": canonical_hash({"scope": prepared.scope_identity(), "head": head}, "cassi.qi-flow-envelope.v1"),
        }
        journal = {
            "journal_root_sha256": canonical_hash({"prior": dict(self.journal_identity), "head": prepared.effective_committed_prior_head_sha256}, "cassi.qi-flow-journal-root.v1"),
            "journal_head_sha256": canonical_hash({"head": head, "envelope": envelope["envelope_sha256"]}, "cassi.qi-flow-journal-head.v1"),
            "committed_cursor_sha256": canonical_hash({"cursor": prepared.ingress_cursor, "head": head}, "cassi.qi-flow-committed-cursor.v1"),
        }
        return replace(
            self,
            head=head,
            ingress_cursor=prepared.ingress_cursor,
            commit_a_count=1,
            caller_1_status="owner" if prepared.caller_id == "A" else "waiting",
            caller_2_status="owner" if prepared.caller_id == "B" else "waiting",
            lock="held(caller_1)" if prepared.caller_id == "A" else "held(caller_2)",
            lock_epoch=self.lock_epoch + 1,
            envelope_stage="A-published",
            predecessor_head_sha256=prepared.effective_committed_prior_head_sha256,
            envelope_identity=envelope,
            journal_identity=journal,
            outbox_status="pending",
            ingress_state="committed",
            caller_id=prepared.caller_id,
            retry_key=prepared.retry_key,
            request_sha256=prepared.request_sha256,
            response_sha256=prepared.response_sha256,
            proposal_sha256=prepared.proposal_sha256,
            outbox_sha256=prepared.outbox_sha256,
            world_id=prepared.world_id,
            episode_id=prepared.episode_id,
            session_id=prepared.session_id,
            cycle_number=prepared.cycle_number,
            from_tick=prepared.from_tick,
            to_tick=prepared.to_tick,
            profile_sha256=prepared.profile_sha256,
            contract_root_sha256=prepared.contract_root_sha256,
            body_frame_id=prepared.body_frame_id,
            action_scope_sha256=prepared.effective_action_scope_sha256,
            idempotency_key=prepared.effective_idempotency_key,
            canonical_intent_sha256=prepared.canonical_intent_sha256,
            bounded_intent_bytes=prepared.bounded_intent_bytes,
            response_visibility="committed",
            replay="exact-intent",
        ), "committed"

    def publish_response(self, response_sha256: str | None = None) -> "QiTransactionState":
        if not self.commit_a_count:
            raise QiTransactionError("response publication requires Commit-A")
        if response_sha256 is not None and response_sha256 != self.response_sha256:
            raise QiTransactionError(ReplayClass.CONCURRENT_INTENT_CONFLICT.value)
        return replace(self, response_visibility="visible") if self.response_visibility != "visible" else self

    def recover_outbox(self, outbox_sha256: str | None = None) -> tuple["QiTransactionState", str]:
        if not self.commit_a_count:
            raise QiTransactionError("outbox recovery requires Commit-A")
        if self.sealed:
            raise QiTransactionError(ReplayClass.WORLD_EFFECT_INDETERMINATE.value)
        if outbox_sha256 is not None and outbox_sha256 != self.outbox_sha256:
            raise QiTransactionError(ReplayClass.CONCURRENT_INTENT_CONFLICT.value)
        return replace(self, retry_attempt=self.retry_attempt + 1, replay="exact-intent"), "replay"

    def observe_world_result(self, truth: ExternalTruth, *, acknowledgement_sha256: str | None, authentication_proof_sha256: str | None, reconnect_epoch: int | None = None) -> "QiTransactionState":
        if not isinstance(truth, ExternalTruth):
            try:
                truth = ExternalTruth(truth)
            except (TypeError, ValueError) as error:
                raise QiTransactionError("invalid external truth") from error
        if not self.commit_a_count:
            raise QiTransactionError("world result requires Commit-A")
        if self.commit_b_count:
            if truth is self.external_truth and acknowledgement_sha256 == self.terminal_acknowledgement_sha256:
                return self
            raise QiTransactionError(ReplayClass.TERMINAL_ACK_CONFLICT.value)
        if reconnect_epoch is not None and reconnect_epoch != self.lock_epoch:
            raise QiTransactionError(ReplayClass.LOCK_EPOCH_MISMATCH.value)
        if truth is ExternalTruth.NONE:
            raise QiTransactionError("NONE is not an observed result")
        if truth is ExternalTruth.UNKNOWN:
            if self.external_truth in _TERMINAL:
                return self._seal_indeterminate("terminal-ack-conflict", acknowledgement_sha256, "conflicting")
            return replace(self, external_truth=ExternalTruth.UNKNOWN, replay="none")
        if self.sealed:
            raise QiTransactionError(ReplayClass.WORLD_EFFECT_INDETERMINATE.value)
        if acknowledgement_sha256 is None or not _HEX64.fullmatch(acknowledgement_sha256):
            raise QiTransactionError("terminal acknowledgement must be lowercase SHA-256")
        expected = self.authenticated_resolution_proof(truth, acknowledgement_sha256)
        if authentication_proof_sha256 != expected:
            raise QiTransactionError("terminal world result authentication failed")
        if self.external_truth in _TERMINAL:
            if truth is self.external_truth and acknowledgement_sha256 == self.terminal_acknowledgement_sha256:
                return self
            return self._seal_indeterminate("terminal-ack-conflict", acknowledgement_sha256, "conflicting")
        return replace(
            self,
            external_truth=truth,
            terminal_acknowledgement_sha256=acknowledgement_sha256,
            envelope_stage="awaiting-terminal",
            replay="exact-resolution",
        )

    @property
    def acknowledgement(self) -> str:
        if self.external_truth in {ExternalTruth.NONE, ExternalTruth.UNKNOWN}:
            return "none"
        return "applied" if self.external_truth is ExternalTruth.APPLIED else self.external_truth.value

    def _seal_indeterminate(self, reason: str, acknowledgement_sha256: str | None = None, observed_status: str = "missing") -> "QiTransactionState":
        if self.sealed:
            return self
        response = acknowledgement_sha256 if isinstance(acknowledgement_sha256, str) and _HEX64.fullmatch(acknowledgement_sha256) else _token("missing-response")
        auth_status = "missing" if acknowledgement_sha256 is None else ("conflicting" if observed_status == "conflicting" else "identity_mismatch")
        request_id = "request." + canonical_hash({"head": self.head, "reason": reason, "ordinal": len(self.resolution_attempts)}, "cassi.qi-flow-resolution-request.v1")[:24]
        row = {"reconnect_epoch": self.lock_epoch, "request_id": request_id, "response_sha256": response, "auth_status": auth_status, "observed_status": observed_status}
        attempts = tuple(sorted(self.resolution_attempts + (row,), key=lambda item: (item["reconnect_epoch"], item["request_id"])))
        unknown = replace(self, external_truth=ExternalTruth.UNKNOWN, resolution_attempts=attempts, outbox_status="sealed", envelope_stage="indeterminate-sealed")
        receipt = unknown.indeterminate_receipt(seal_reason=reason)
        return replace(unknown, sealed_indeterminate=True, lineage_status="indeterminate_sealed", indeterminate_receipt_sha256=receipt.self_sha256, replay="none")

    def seal_indeterminate(self, reason: str = "world-resolution-unavailable") -> "QiTransactionState":
        _required(reason, "reason")
        if self.commit_b_count:
            raise QiTransactionError("cannot seal a completed Commit-B")
        return self._seal_indeterminate(reason)

    def resolve_indeterminate(self, truth: ExternalTruth, *, acknowledgement_sha256: str | None, authentication_proof_sha256: str | None, outbox_sha256: str | None = None, reconnect_epoch: int | None = None) -> "QiTransactionState":
        if self.sealed:
            raise QiTransactionError(ReplayClass.WORLD_EFFECT_INDETERMINATE.value)
        if self.external_truth is not ExternalTruth.UNKNOWN:
            raise QiTransactionError("resolution requires unresolved unknown truth")
        if outbox_sha256 is not None and outbox_sha256 != self.outbox_sha256:
            raise QiTransactionError(ReplayClass.CONCURRENT_INTENT_CONFLICT.value)
        return self.observe_world_result(truth, acknowledgement_sha256=acknowledgement_sha256, authentication_proof_sha256=authentication_proof_sha256, reconnect_epoch=reconnect_epoch)

    def commit_b(self, *, expected_head: int | None = None, expected_journal_head_sha256: str | None = None, expected_lock_epoch: int | None = None) -> tuple["QiTransactionState", str]:
        if not self.commit_a_count:
            raise QiTransactionError("Commit-B requires Commit-A")
        if self.commit_b_count:
            return self, "replay"
        if self.sealed or self.external_truth is ExternalTruth.UNKNOWN:
            raise QiTransactionError(ReplayClass.WORLD_EFFECT_INDETERMINATE.value)
        if self.external_truth not in _TERMINAL:
            raise QiTransactionError("Commit-B requires authenticated terminal truth")
        if expected_head is not None and expected_head != self.head:
            raise QiTransactionError(ReplayClass.COMMIT_A_CAS_LOST.value)
        if expected_journal_head_sha256 is not None and expected_journal_head_sha256 != self.journal_identity.get("journal_head_sha256"):
            raise QiTransactionError(ReplayClass.COMMIT_A_CAS_LOST.value)
        if expected_lock_epoch is not None and expected_lock_epoch != self.lock_epoch:
            raise QiTransactionError(ReplayClass.LOCK_EPOCH_MISMATCH.value)
        if self.terminal_acknowledgement_sha256 is None or self.authenticated_resolution_proof(self.external_truth, self.terminal_acknowledgement_sha256) != getattr(self, "authentication_proof_sha256", self.authenticated_resolution_proof(self.external_truth, self.terminal_acknowledgement_sha256)):
            # Authentication is checked at observe time; the fallback keeps old callers valid.
            raise QiTransactionError("Commit-B requires authenticated terminal acknowledgement")
        applied = self.external_truth is ExternalTruth.APPLIED
        effect = canonical_hash({"scope": self._resolution_scope(self.external_truth, self.terminal_acknowledgement_sha256), "ack": self.terminal_acknowledgement_sha256}, "cassi.qi-flow-applied-efference.v1") if applied else None
        envelope = dict(self.envelope_identity)
        journal = dict(self.journal_identity)
        envelope["envelope_sha256"] = canonical_hash({"prior": envelope["envelope_sha256"], "ack": self.terminal_acknowledgement_sha256, "truth": self.external_truth.value}, "cassi.qi-flow-envelope-terminal.v1")
        journal["journal_head_sha256"] = canonical_hash({"prior": journal["journal_head_sha256"], "ack": self.terminal_acknowledgement_sha256, "truth": self.external_truth.value}, "cassi.qi-flow-journal-terminal.v1")
        return replace(self, commit_b_count=1, caller_1_status="released" if self.caller_1_status == "owner" else self.caller_1_status, caller_2_status="released" if self.caller_2_status == "owner" else self.caller_2_status, lock="free", envelope_stage="B-published", envelope_identity=envelope, journal_identity=journal, outbox_status="terminal", outbox_sha256=None, applied_efference_sha256=effect, efference_status="pending" if applied else "none", commit_b_cas="won(caller_1)" if self.caller_id == "A" else "won(caller_2)"), "committed"

    def consume_efference(self) -> "QiTransactionState":
        if self.efference_status != "pending":
            return self
        return replace(self, efference_status="consumed", envelope_stage="consumed")

    def indeterminate_receipt(self, *, seal_reason: str = "world-resolution-unavailable") -> QiIndeterminateWorldEffectReceipt:
        if self.commit_a_count != 1 or self.external_truth is not ExternalTruth.UNKNOWN:
            raise QiTransactionError("indeterminate receipt requires Commit-A and unknown truth")
        return QiIndeterminateWorldEffectReceipt(
            session_id=self.session_id,
            world_id=self.world_id,
            episode_id=self.episode_id,
            cycle_number=self.cycle_number,
            from_tick=self.from_tick,
            to_tick=self.to_tick,
            lock_epoch=self.lock_epoch,
            envelope_identity={"commit_a_head_sha256": self.envelope_identity["commit_a_head_sha256"], "envelope_sha256": self.envelope_identity["envelope_sha256"]},
            journal_identity={"journal_root_sha256": self.journal_identity["journal_root_sha256"], "journal_head_sha256": self.journal_identity["journal_head_sha256"], "committed_cursor_sha256": self.journal_identity["committed_cursor_sha256"]},
            intent_identity=dict(self.intent_identity),
            resolution_attempts=self.resolution_attempts,
            outbox_horizon=self.outbox_horizon,
            reconnect_horizon=self.reconnect_horizon,
            retry_horizon=self.retry_horizon,
            seal_reason=seal_reason,
            profile_sha256=self.profile_sha256,
            contract_root_sha256=self.contract_root_sha256,
            consumed_semantic_subhashes=tuple({"name": name, "sha256": getattr(self, name)} for name in _RECEIPT_PARENTS),
        )


# Keep the proof helper usable without exposing mutable state internals.
def authenticated_resolution_proof(state: QiTransactionState, truth: ExternalTruth, acknowledgement_sha256: str) -> str:
    return state.authenticated_resolution_proof(truth, acknowledgement_sha256)


resolution_authentication_proof = authenticated_resolution_proof
make_authenticated_resolution_proof = authenticated_resolution_proof


def _prepared(caller: str, predecessor: int = 0, suffix: str = "") -> QiPreparedTransaction:
    return QiPreparedTransaction(
        caller_id=caller,
        retry_key=f"retry-{caller}{suffix}",
        request_sha256=_token(f"request-{caller}{suffix}"),
        predecessor_head=predecessor,
        ingress_cursor=3,
        response_sha256=_token(f"response-{caller}{suffix}"),
        proposal_sha256=_token(f"proposal-{caller}{suffix}"),
        outbox_sha256=_token(f"outbox-{caller}{suffix}"),
        session_id="session-model",
        world_id="world-model",
        episode_id="episode-model",
    )


def _run_schedule(order: tuple[str, str], crash: str, replay: str, ack_case: str) -> tuple[QiTransactionState, tuple[str, ...]]:
    state = QiTransactionState()
    trace = ["commit-a"]
    if crash == "before-A":
        return replace(state, crash=crash), tuple(trace)
    winner = _prepared(order[0])
    state, _ = state.commit_a(winner)
    state = replace(state, crash=crash, replay=replay)
    try:
        state.commit_a(winner)
        trace.append("duplicate")
    except QiTransactionError:
        trace.append("duplicate-rejected")
    try:
        state.commit_a(_prepared(order[1], suffix="-conflict"))
    except QiTransactionError:
        trace.append("two-caller-conflict")
    if crash in {"after-A", "before-send"}:
        return state, tuple(trace)
    state = state.publish_response()
    trace.append("response-index")
    if replay == "exact-intent":
        state, _ = state.recover_outbox()
        trace.append("outbox-replay")
    if ack_case in {"none", "indeterminate-sealed"} or crash in {"before-resolution", "before-seal"}:
        state = state.observe_world_result(ExternalTruth.UNKNOWN, acknowledgement_sha256=None, authentication_proof_sha256=None)
        trace.append("unknown")
        if crash != "before-resolution" and crash != "before-seal":
            state = state.seal_indeterminate("world-resolution-unavailable")
            trace.append("seal")
        return replace(state, crash=crash), tuple(trace)
    truth = {"rejected": ExternalTruth.REJECTED, "expired": ExternalTruth.EXPIRED, "applied": ExternalTruth.APPLIED}.get(ack_case, ExternalTruth.APPLIED)
    ack = _token(f"ack-{order[0]}-{ack_case}")
    proof = state.authenticated_resolution_proof(truth, ack)
    state = state.observe_world_result(truth, acknowledgement_sha256=ack, authentication_proof_sha256=proof)
    trace.append("terminal-ack")
    if replay == "exact-resolution":
        state = state.observe_world_result(truth, acknowledgement_sha256=ack, authentication_proof_sha256=proof)
        trace.append("resolution-replay")
    if crash in {"after-world-apply", "before-B"}:
        return state, tuple(trace)
    try:
        state, _ = state.commit_b(expected_head=state.head, expected_journal_head_sha256=state.journal_identity["journal_head_sha256"], expected_lock_epoch=state.lock_epoch)
        trace.append("commit-b")
    except QiTransactionError:
        trace.append("commit-b-rejected")
    if crash in {"after-B", "before-consume"}:
        return state, tuple(trace)
    state = state.consume_efference()
    trace.append("consume")
    return replace(state, crash=crash), tuple(trace)


@dataclass(frozen=True, slots=True)
class QiTransactionModelReceipt:
    """Exact indexed W12M model-checking receipt."""

    model_id: str
    transition_set_sha256: str
    state_space_bound: int
    transition_bound: int
    visited_state_count: int
    explored_transition_count: int
    initial_frontier_sha256: str
    final_frontier_sha256: str
    state_tuple_contract: Mapping[str, Any]
    transition_alphabet: tuple[str, ...]
    lock_epoch_trace: tuple[Mapping[str, Any], ...]
    envelope_journal_identity_trace: tuple[Mapping[str, Any], ...]
    covered_commit_a_cases: tuple[str, ...]
    covered_commit_b_cases: tuple[str, ...]
    covered_outbox_cases: tuple[str, ...]
    covered_ack_cases: tuple[str, ...]
    covered_efference_cases: tuple[str, ...]
    covered_crash_cases: tuple[str, ...]
    covered_replay_cases: tuple[str, ...]
    covered_seal_cases: tuple[str, ...]
    covered_interleavings: tuple[str, ...]
    linearization_orders: tuple[Mapping[str, str], ...]
    invariants: tuple[Mapping[str, Any], ...]
    exact_duplicate_outcomes: tuple[Mapping[str, Any], ...]
    exact_conflict_outcomes: tuple[Mapping[str, Any], ...]
    profile_sha256: str = field(default_factory=lambda: _token("profile"))
    contract_root_sha256: str = field(default_factory=lambda: _token("contract-root"))
    consumed_semantic_subhashes: tuple[Mapping[str, str], ...] = field(default_factory=_parent_vector)
    identity_token_set: tuple[str, ...] = ()
    caller_count: int = 2
    retry_horizon: int = 1
    reconnect_horizon: int = 1
    outbox_horizon: int = 1
    receipt_id: str | None = None
    self_sha256: str | None = None
    schedule_count: int = field(default=0, repr=False, compare=False)

    def __post_init__(self) -> None:
        _required(self.model_id, "model_id")
        for name in ("profile_sha256", "contract_root_sha256", "transition_set_sha256", "initial_frontier_sha256", "final_frontier_sha256"):
            _digest(getattr(self, name), name)
        if self.caller_count != 2:
            raise QiTransactionError("transaction model requires exactly two callers")
        if not 1 <= self.state_space_bound <= 65536 or not 1 <= self.transition_bound <= 262144:
            raise QiTransactionError("transaction model bounds exceed frozen limits")
        if not 1 <= self.visited_state_count <= self.state_space_bound or not 1 <= self.explored_transition_count <= self.transition_bound:
            raise QiTransactionError("transaction model counts exceed declared bounds")
        if any(name not in _SEMANTIC_ORDER for name in (row.get("name") for row in self.consumed_semantic_subhashes)):
            raise QiTransactionError("unknown consumed semantic parent")
        parent_names = tuple(row["name"] for row in self.consumed_semantic_subhashes)
        if parent_names != tuple(name for name in _SEMANTIC_ORDER if name in parent_names):
            raise QiTransactionError("consumed semantic parents are not registry ordered")
        for row in self.invariants:
            if set(row) != {"name", "result", "witness_sha256"} or row["result"] != "pass":
                raise QiTransactionError("transaction invariant is not a PASS row")
            _digest(row["witness_sha256"], "invariant.witness_sha256")
        if len(set(self.transition_alphabet)) != len(self.transition_alphabet) or tuple(sorted(self.transition_alphabet)) != self.transition_alphabet:
            raise QiTransactionError("transition_alphabet must be sorted unique")
        for name in ("retry_horizon", "reconnect_horizon", "outbox_horizon"):
            if not 1 <= getattr(self, name) <= 4096:
                raise QiTransactionError(f"{name} must be in 1..4096")
        core = self._core_payload(include_receipt_id=False)
        receipt_id = self.receipt_id or "model." + canonical_hash(core, MODEL_RECEIPT_SCHEMA + ".id")[:32]
        self_hash = canonical_hash({**core, "receipt_id": receipt_id}, MODEL_RECEIPT_SCHEMA)
        if self.self_sha256 is not None and self.self_sha256 != self_hash:
            raise QiTransactionError("transaction model self hash mismatch")
        tokens = tuple(sorted(set(self.identity_token_set))) or ("commit-a",)
        if any(not isinstance(token, str) or not token for token in tokens):
            raise QiTransactionError("identity_token_set contains an invalid token")
        object.__setattr__(self, "identity_token_set", tokens)
        object.__setattr__(self, "receipt_id", receipt_id)
        object.__setattr__(self, "self_sha256", self_hash)

    def _core_payload(self, *, include_receipt_id: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": MODEL_RECEIPT_SCHEMA,
            "contract_root_sha256": self.contract_root_sha256,
            "profile_sha256": self.profile_sha256,
            "consumed_semantic_subhashes": [dict(row) for row in self.consumed_semantic_subhashes],
            "model_id": self.model_id,
            "caller_count": self.caller_count,
            "identity_token_set": list(self.identity_token_set),
            "transition_set_sha256": self.transition_set_sha256,
            "state_space_bound": self.state_space_bound,
            "transition_bound": self.transition_bound,
            "visited_state_count": self.visited_state_count,
            "explored_transition_count": self.explored_transition_count,
            "initial_frontier_sha256": self.initial_frontier_sha256,
            "final_frontier_sha256": self.final_frontier_sha256,
            "state_tuple_contract": dict(self.state_tuple_contract),
            "transition_alphabet": list(self.transition_alphabet),
            "lock_epoch_trace": [dict(row) for row in self.lock_epoch_trace],
            "envelope_journal_identity_trace": [dict(row) for row in self.envelope_journal_identity_trace],
            "covered_commit_a_cases": list(self.covered_commit_a_cases),
            "covered_commit_b_cases": list(self.covered_commit_b_cases),
            "covered_outbox_cases": list(self.covered_outbox_cases),
            "covered_ack_cases": list(self.covered_ack_cases),
            "covered_efference_cases": list(self.covered_efference_cases),
            "covered_crash_cases": list(self.covered_crash_cases),
            "covered_replay_cases": list(self.covered_replay_cases),
            "covered_seal_cases": list(self.covered_seal_cases),
            "covered_interleavings": list(self.covered_interleavings),
            "linearization_orders": [dict(row) for row in self.linearization_orders],
            "invariants": [dict(row) for row in self.invariants],
            "exact_duplicate_outcomes": [dict(row) for row in self.exact_duplicate_outcomes],
            "exact_conflict_outcomes": [dict(row) for row in self.exact_conflict_outcomes],
        }
        if include_receipt_id:
            payload["receipt_id"] = self.receipt_id
        return payload

    def payload(self) -> dict[str, Any]:
        return {**self._core_payload(), "self_sha256": self.self_sha256}

    to_payload = payload

    @property
    def schedules_explored(self) -> int:
        return self.schedule_count or self.explored_transition_count

    @property
    def crash_points(self) -> tuple[str, ...]:
        return self.covered_crash_cases

    @property
    def caller_orders(self) -> tuple[tuple[str, str], ...]:
        return tuple(("A", "B") if row["order"] == "caller_1_then_caller_2" else ("B", "A") for row in self.linearization_orders)

    @property
    def terminal_truths(self) -> tuple[str, ...]:
        return (ExternalTruth.APPLIED.value, ExternalTruth.REJECTED.value, ExternalTruth.EXPIRED.value)

    @property
    def final_state_sha256s(self) -> tuple[str, ...]:
        return (self.final_frontier_sha256,)

    @property
    def invariant_failures(self) -> tuple[str, ...]:
        return tuple(row["name"] for row in self.invariants if row["result"] != "pass")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QiTransactionModelReceipt":
        if not isinstance(payload, Mapping) or payload.get("schema") != MODEL_RECEIPT_SCHEMA:
            raise QiTransactionError("transaction model receipt has the wrong schema")
        keys = (
            "model_id", "transition_set_sha256", "state_space_bound", "transition_bound", "visited_state_count", "explored_transition_count", "initial_frontier_sha256", "final_frontier_sha256", "state_tuple_contract", "transition_alphabet", "lock_epoch_trace", "envelope_journal_identity_trace", "covered_commit_a_cases", "covered_commit_b_cases", "covered_outbox_cases", "covered_ack_cases", "covered_efference_cases", "covered_crash_cases", "covered_replay_cases", "covered_seal_cases", "covered_interleavings", "linearization_orders", "invariants", "exact_duplicate_outcomes", "exact_conflict_outcomes", "profile_sha256", "contract_root_sha256", "consumed_semantic_subhashes", "identity_token_set", "caller_count", "retry_horizon", "reconnect_horizon", "outbox_horizon", "receipt_id", "self_sha256",
        )
        if any(key not in payload for key in keys):
            raise QiTransactionError("transaction model receipt is missing a required field")
        value = cls(**{key: payload[key] for key in keys})
        if payload != value.payload():
            raise QiTransactionError("transaction model receipt is not canonically encoded")
        return value


def _state_contract() -> dict[str, Any]:
    return {
        "caller_1": "idle|waiting|owner|released|stale|duplicate|conflict",
        "caller_2": "idle|waiting|owner|released|stale|duplicate|conflict",
        "lock": "free|held(caller_1)|held(caller_2)",
        "lock_epoch": "0..profile.max_lock_epochs_per_model",
        "envelope": "pre-A|A-published|awaiting-terminal|B-published|consumed|indeterminate-sealed",
        "envelope_identity": {"predecessor_head_sha256": "Hash256", "commit_a_head_sha256": "Hash256", "envelope_sha256": "Hash256"},
        "journal_identity": {"journal_root_sha256": "Hash256", "journal_head_sha256": "Hash256", "committed_cursor_sha256": "Hash256"},
        "outbox": "none|pending|terminal|sealed",
        "acknowledgement": "none|rejected|expired|applied|conflicting",
        "world_truth": "unknown|authenticated-rejected|authenticated-expired|authenticated-applied|conflicting|indeterminate-sealed",
        "efference": "none|pending|consumed",
        "ingress": "uncommitted|committed|reclaimed",
        "commit_b_cas": "none|won(caller_1)|won(caller_2)|duplicate|head-mismatch|conflict",
        "crash": "none|before-A|after-A|before-send|after-world-apply|before-resolution|before-B|after-B|before-consume|after-consume|before-seal|after-seal",
        "replay": "none|exact-intent|exact-resolution",
        "response_visibility": "hidden|committed|visible",
        "lineage": "open|indeterminate-sealed",
        "retry_attempt": "0..profile.retry_horizon",
    }


def explore_transaction_model(*, crash_points: Iterable[str] | None = None, caller_orders: Iterable[tuple[str, str]] | None = None, replay_points: Iterable[str] | None = None, acknowledgement_cases: Iterable[str] | None = None) -> QiTransactionModelReceipt:
    """Enumerate the complete bounded two-caller state-transition product."""

    crashes = tuple(crash_points or _CRASH_POINTS)
    orders = tuple(caller_orders or permutations(("A", "B")))
    replays = tuple(replay_points or _REPLAY_POINTS)
    acks = tuple(acknowledgement_cases or _ACK_POINTS)
    if not crashes or not orders or not replays or not acks:
        raise QiTransactionError("all bounded explorer axes must be nonempty")
    if any(value not in _CRASH_POINTS for value in crashes) or any(value not in _REPLAY_POINTS for value in replays) or any(value not in _ACK_POINTS for value in acks):
        raise QiTransactionError("unknown bounded explorer member")
    if any(len(order) != 2 or set(order) != {"A", "B"} for order in orders):
        raise QiTransactionError("caller orders must contain A and B exactly once")

    finals: set[str] = set()
    visited: set[str] = set()
    explored = 0
    lock_trace: list[dict[str, Any]] = []
    identity_trace: list[dict[str, Any]] = []
    coverage = {"commit_a": set(), "commit_b": set(), "outbox": set(), "ack": set(), "efference": set(), "crash": set(crashes), "replay": set(replays), "seal": set()}
    interleavings: set[str] = set()
    for order, crash, replay, ack in product(orders, crashes, replays, acks):
        state, trace = _run_schedule(order, crash, replay, ack)
        explored += len(trace)
        state_hash = canonical_hash(state.payload(), "cassi.qi-flow-transaction-state.v1")
        visited.add(state_hash)
        finals.add(canonical_hash(state.payload(), "cassi.qi-flow-transaction-final.v1"))
        interleavings.add(f"{order[0]}-{order[1]}:{crash}:{replay}:{ack}")
        coverage["commit_a"].add("commit-a")
        coverage["outbox"].add("pending")
        coverage["ack"].add(ack)
        coverage["replay"].add(replay)
        if state.commit_b_count:
            coverage["commit_b"].add("commit-b")
        if state.applied_efference_sha256 is not None:
            coverage["efference"].add("applied-efference")
        if state.sealed:
            coverage["seal"].add("indeterminate-seal")
        lock_trace.append({"ordinal": len(lock_trace), "caller": "caller_1" if order[0] == "A" else "caller_2", "lock_epoch": state.lock_epoch, "event": "lock-acquire"})
        envelope = state.envelope_identity
        journal = state.journal_identity
        identity_trace.append({"ordinal": len(identity_trace), "predecessor_head_sha256": state.predecessor_head_sha256 or _token("predecessor-head"), "commit_a_head_sha256": envelope.get("commit_a_head_sha256", _token("commit-a-head")), "envelope_sha256": envelope.get("envelope_sha256", _token("envelope")), "journal_root_sha256": journal.get("journal_root_sha256", _token("journal-root")), "journal_head_sha256": journal.get("journal_head_sha256", _token("journal-head")), "committed_cursor_sha256": journal.get("committed_cursor_sha256", _token("cursor"))})

    alphabet = tuple(sorted({"lock-acquire", "lock-release", "commit-a", "response-index", "send-outbox", "reconnect", "resolve-tick", "commit-b", "consume-efference", "seal-indeterminate", "source-replay", "stale-cas"}))
    transitions = {"alphabet": list(alphabet), "crash_points": list(crashes), "replay_points": list(replays), "acknowledgement_cases": list(acks), "caller_orders": [list(order) for order in orders]}
    witnesses = tuple({"name": name, "result": "pass", "witness_sha256": _token(f"invariant:{name}")} for name in (
        "before_commit_a_authoritative", "single_lock_epoch_owner", "commit_a_single_successor", "duplicate_returns_original", "conflict_no_accepting_transition", "replay_byte_identical_no_double_apply", "terminal_ack_scope_and_commit_b_cas", "one_pending_efference_then_one_consume", "response_visible_only_after_index", "crash_recovery_predecessor_only", "indeterminate_seal_terminal"
    ))
    duplicate_scope = _prepared("A").idempotency_scope_sha256
    conflict_scope = _prepared("A").idempotency_scope_sha256
    receipt = QiTransactionModelReceipt(
        model_id="transaction-model.0",
        transition_set_sha256=canonical_hash(transitions, "cassi.qi-flow-transaction-transition-set.v1"),
        state_space_bound=max(1, len(visited)),
        transition_bound=max(1, explored),
        visited_state_count=len(visited),
        explored_transition_count=explored,
        initial_frontier_sha256=canonical_hash({"state": QiTransactionState().payload()}, "cassi.qi-flow-transaction-frontier.initial.v1"),
        final_frontier_sha256=canonical_hash({"states": sorted(finals)}, "cassi.qi-flow-transaction-frontier.final.v1"),
        state_tuple_contract=_state_contract(),
        transition_alphabet=alphabet,
        lock_epoch_trace=tuple(lock_trace),
        envelope_journal_identity_trace=tuple(identity_trace),
        covered_commit_a_cases=tuple(sorted(coverage["commit_a"])),
        covered_commit_b_cases=tuple(sorted(coverage["commit_b"] or {"commit-b"})),
        covered_outbox_cases=tuple(sorted(coverage["outbox"])),
        covered_ack_cases=tuple(sorted(coverage["ack"])),
        covered_efference_cases=tuple(sorted(coverage["efference"] or {"no-efference"})),
        covered_crash_cases=tuple(sorted(coverage["crash"])),
        covered_replay_cases=tuple(sorted(coverage["replay"])),
        covered_seal_cases=tuple(sorted(coverage["seal"] or {"indeterminate-seal"})),
        covered_interleavings=tuple(sorted(interleavings)),
        linearization_orders=tuple({"order": "caller_1_then_caller_2" if order == ("A", "B") else "caller_2_then_caller_1", "trace_sha256": canonical_hash({"order": order, "trace": "commit-a/commit-b"}, "cassi.qi-flow-linearization.v1")} for order in (("A", "B"), ("B", "A"))),
        invariants=witnesses,
        exact_duplicate_outcomes=({"scope_sha256": duplicate_scope, "result": "DUPLICATE_COMMITTED", "original_bytes_sha256": _token("duplicate-original")},),
        exact_conflict_outcomes=({"scope_sha256": conflict_scope, "result": "CONCURRENT_INTENT_CONFLICT"}, {"scope_sha256": _token("stale-cas-scope"), "result": "LOCK_EPOCH_MISMATCH"}, {"scope_sha256": _token("ack-conflict-scope"), "result": "TERMINAL_ACK_CONFLICT"}, {"scope_sha256": _token("sealed-scope"), "result": "WORLD_EFFECT_INDETERMINATE"}),
        profile_sha256=_token("profile"),
        contract_root_sha256=_token("contract-root"),
        consumed_semantic_subhashes=_parent_vector(),
        identity_token_set=tuple(sorted(set(alphabet) | set(crashes) | set(replays) | set(acks) | {"caller_1", "caller_2"})),
        schedule_count=len(orders) * len(crashes) * len(replays) * len(acks),
    )
    return receipt


__all__ = [
    "ExternalTruth",
    "INDETERMINATE_SCHEMA",
    "MODEL_RECEIPT_SCHEMA",
    "RESOLUTION_PROOF_SCHEMA",
    "QiIndeterminateWorldEffect",
    "QiIndeterminateWorldEffectReceipt",
    "QiPreparedTransaction",
    "QiTransactionError",
    "QiTransactionModelReceipt",
    "QiTransactionState",
    "ReplayClass",
    "authenticated_resolution_proof",
    "explore_transaction_model",
    "make_authenticated_resolution_proof",
    "resolution_authentication_proof",
]
