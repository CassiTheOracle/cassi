"""Deterministic bounded reference world and authenticated world wire.

This module is intentionally self contained.  It exposes an analytic reference
world whose only mutable state is the bounded environment, plus the exact W13R
world protocol.  Provider, policy, field, and consequence code never enters the
module or the authenticated wire.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import math
import re
import struct
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Iterable, Mapping, Protocol, Sequence

from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes, canonical_json_loads

# ---------------------------------------------------------------------------
# Frozen identities and protocol limits

ACTION_SCHEMA = "cassi.qi-flow-action.v1"
ACTION_SCOPE_SCHEMA = "cassi.qi-flow-action-scope.v1"
TICK_INTENT_SCHEMA = "cassi.qi-flow-tick-intent.v1"
TICK_ACK_SCHEMA = "cassi.qi-flow-tick-ack.v1"
WORLD_FRAME_SCHEMA = "cassi.qi-world-frame.v1"
WORLD_WIRE_SCHEMA = "cassi.qi-world-wire.v1"
WORLD_PROTOCOL_VERSION = "1"
AUTH_DOMAIN = "cassi.qi-world-auth.v1"
CANONICAL_SCHEMA = "cassi.canonical-json.v1"

HELLO_SCHEMA = "cassi.qi-world-hello.v1"
HELLO_ACK_SCHEMA = "cassi.qi-world-hello-ack.v1"
OBSERVE_REQUEST_SCHEMA = "cassi.qi-world-observe-request.v1"
OBSERVATION_SCHEMA = "cassi.qi-world-observation.v1"
OBSERVATION_COMPLETE_SCHEMA = "cassi.qi-world-observation-complete.v1"
DESCRIBE_ACTIONS_SCHEMA = "cassi.qi-world-describe-actions.v1"
ACTION_DESCRIPTORS_SCHEMA = "cassi.qi-world-action-descriptors.v1"
ADVANCE_TICK_SCHEMA = "cassi.qi-world-advance-tick.v1"
RESOLVE_TICK_SCHEMA = "cassi.qi-world-resolve-tick.v1"
TICK_COMPLETE_SCHEMA = "cassi.qi-world-tick-complete.v1"
HEARTBEAT_SCHEMA = "cassi.qi-world-heartbeat.v1"
HEARTBEAT_ACK_SCHEMA = "cassi.qi-world-heartbeat-ack.v1"
CLOSE_SCHEMA = "cassi.qi-world-close.v1"
CLOSE_ACK_SCHEMA = "cassi.qi-world-close-ack.v1"
ERROR_SCHEMA = "cassi.qi-world-error.v1"

MAX_CANONICAL_HEADER_BYTES = 65_536
MAX_RAW_PAYLOAD_BYTES = 1_048_576
MAX_OUTER_FRAME_BYTES = 1_114_112
MAX_CANONICAL_OBJECT_BYTES = 65_536
MAX_U64 = (1 << 53) - 1  # bootstrap's exact JSON integer ceiling
MAX_I64 = (1 << 63) - 1
MIN_I64 = -(1 << 63)
MAX_QUEUE_DEPTH = 64
ZERO_SHA256 = "0" * 64
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_ID_RE = re.compile(r"[a-z][a-z0-9._:-]{0,127}\Z")
_PROJECTION_ORDER = (
    "state_contract",
    "boundary_action",
    "world_protocol",
    "session_storage",
    "provider_api",
    "backend_capacity",
    "security_evidence",
)

WIRE_KINDS = (
    "hello",
    "hello_ack",
    "observe_request",
    "observation",
    "observation_complete",
    "describe_actions",
    "action_descriptors",
    "advance_tick",
    "resolve_tick",
    "tick_complete",
    "heartbeat",
    "heartbeat_ack",
    "close",
    "close_ack",
    "error",
)
_REQUEST_KINDS = {"hello", "observe_request", "describe_actions", "advance_tick", "resolve_tick", "heartbeat", "close"}
_RESPONSE_KINDS = set(WIRE_KINDS) - _REQUEST_KINDS
_KIND_SCHEMA = {
    "hello": HELLO_SCHEMA,
    "hello_ack": HELLO_ACK_SCHEMA,
    "observe_request": OBSERVE_REQUEST_SCHEMA,
    "observation": OBSERVATION_SCHEMA,
    "observation_complete": OBSERVATION_COMPLETE_SCHEMA,
    "describe_actions": DESCRIBE_ACTIONS_SCHEMA,
    "action_descriptors": ACTION_DESCRIPTORS_SCHEMA,
    "advance_tick": ADVANCE_TICK_SCHEMA,
    "resolve_tick": RESOLVE_TICK_SCHEMA,
    "tick_complete": TICK_COMPLETE_SCHEMA,
    "heartbeat": HEARTBEAT_SCHEMA,
    "heartbeat_ack": HEARTBEAT_ACK_SCHEMA,
    "close": CLOSE_SCHEMA,
    "close_ack": CLOSE_ACK_SCHEMA,
    "error": ERROR_SCHEMA,
}
_KIND_LIMITS = {
    "hello": (4096, 0),
    "hello_ack": (8192, 0),
    "observe_request": (4096, 0),
    "observation": (12288, MAX_RAW_PAYLOAD_BYTES),
    "observation_complete": (8192, 0),
    "describe_actions": (4096, 0),
    "action_descriptors": (MAX_CANONICAL_HEADER_BYTES, 0),
    "advance_tick": (MAX_CANONICAL_HEADER_BYTES, 0),
    "resolve_tick": (MAX_CANONICAL_HEADER_BYTES, 0),
    "tick_complete": (MAX_CANONICAL_HEADER_BYTES, 0),
    "heartbeat": (4096, 0),
    "heartbeat_ack": (4096, 0),
    "close": (4096, 0),
    "close_ack": (4096, 0),
    "error": (4096, 0),
}


class QiWorldError(ValueError):
    """A fail-closed world or protocol error."""


class WireError(QiWorldError):
    """Malformed, unauthenticated, or replayed wire data."""


class WorldStateError(QiWorldError):
    """Invalid world transition or snapshot."""


# ---------------------------------------------------------------------------
# Primitive validators and exact canonical shapes


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise QiWorldError(f"{name} must be a canonical Id")
    return value


def _text(value: Any, name: str) -> str:
    # Human-readable reason/detail strings are not Ids, but remain bounded.
    if not isinstance(value, str) or not value or len(value) > 256 or "\x00" in value:
        raise QiWorldError(f"{name} must be a nonempty bounded string")
    return value


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or value.lower() != value or any(c not in "0123456789abcdef" for c in value):
        raise QiWorldError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _u64(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_U64:
        raise QiWorldError(f"{name} must be an unsigned exact integer")
    return value


def _i64(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not MIN_I64 <= value <= MAX_I64:
        raise QiWorldError(f"{name} must be a signed exact integer")
    return value


def _f64(value: float | int | str) -> str:
    if isinstance(value, bool):
        raise QiWorldError("finite value cannot be bool")
    if isinstance(value, str):
        if not value.startswith("f64:") or len(value) != 20 or any(c not in "0123456789abcdef" for c in value[4:]):
            raise QiWorldError("finite value must be f64 bits")
        try:
            number = struct.unpack(">d", bytes.fromhex(value[4:]))[0]
        except (ValueError, struct.error) as exc:
            raise QiWorldError("invalid finite bits") from exc
    else:
        number = float(value)
    if not math.isfinite(number) or (number == 0.0 and math.copysign(1.0, number) < 0.0):
        raise QiWorldError("finite value must be finite and not negative zero")
    return "f64:" + struct.pack(">d", number).hex()


def _f64_value(value: Any) -> float:
    bits = _f64(value)
    return struct.unpack(">d", bytes.fromhex(bits[4:]))[0]


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _unb64(value: Any, name: str, *, max_bytes: int | None = None) -> bytes:
    if not isinstance(value, str):
        raise QiWorldError(f"{name} must be base64 text")
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise QiWorldError(f"{name} is not canonical base64") from exc
    if _b64(raw) != value or max_bytes is not None and len(raw) > max_bytes:
        raise QiWorldError(f"{name} is not canonical base64")
    return raw


def _bytes_obj(raw: bytes) -> dict[str, Any]:
    raw = bytes(raw)
    return {"byte_count": len(raw), "bytes_b64": _b64(raw), "encoding": "base64", "sha256": _sha256_bytes(raw)}


def _bytes_value(value: Any, name: str, *, max_bytes: int = MAX_CANONICAL_OBJECT_BYTES) -> bytes:
    if not isinstance(value, Mapping) or set(value) != {"byte_count", "bytes_b64", "encoding", "sha256"}:
        raise QiWorldError(f"{name} must be a canonical Bytes object")
    if value["encoding"] != "base64":
        raise QiWorldError(f"{name} encoding mismatch")
    raw = _unb64(value["bytes_b64"], f"{name}.bytes_b64", max_bytes=max_bytes)
    if value["byte_count"] != len(raw) or value["sha256"] != _sha256_bytes(raw):
        raise QiWorldError(f"{name} byte identity mismatch")
    return raw


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(bytes(raw)).hexdigest()


def _rational(value: Any, name: str = "rational") -> dict[str, int]:
    if isinstance(value, Fraction):
        value = {"d": value.denominator, "n": value.numerator}
    if not isinstance(value, Mapping) or set(value) != {"d", "n"}:
        raise QiWorldError(f"{name} must be a reduced rational")
    n, d = _i64(value["n"], f"{name}.n"), _u64(value["d"], f"{name}.d")
    if d < 1 or math.gcd(abs(n), d) != 1:
        raise QiWorldError(f"{name} must be reduced")
    return {"d": d, "n": n}


def _watermark(value: Any) -> dict[str, str]:
    if hasattr(value, "payload"):
        value = value.payload()
    if not isinstance(value, Mapping) or set(value) != {"frontier_sha256", "journal_head_sha256", "committed_cursor_sha256"}:
        raise QiWorldError("watermark fields mismatch")
    return {key: _sha(value[key], key) for key in ("frontier_sha256", "journal_head_sha256", "committed_cursor_sha256")}


def _capture_interval(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"capture_start", "capture_end"}:
        raise QiWorldError("capture interval fields mismatch")
    start, end = _rational(value["capture_start"], "capture_start"), _rational(value["capture_end"], "capture_end")
    if Fraction(start["n"], start["d"]) >= Fraction(end["n"], end["d"]):
        raise QiWorldError("capture interval must be half-open and increasing")
    return {"capture_end": end, "capture_start": start}


def _semantic_parents(value: Any, expected: Sequence[str]) -> list[dict[str, str]]:
    if value is None:
        # Convenience defaults are deterministic but callers may always pin real
        # root projection hashes explicitly.
        return [{"name": name, "sha256": canonical_hash({"projection": name}, f"cassi.qi-world-parent.{name}")} for name in expected]
    if not isinstance(value, (list, tuple)) or len(value) != len(expected):
        raise QiWorldError("semantic parent vector length mismatch")
    result: list[dict[str, str]] = []
    for item, name in zip(value, expected):
        if not isinstance(item, Mapping) or set(item) != {"name", "sha256"} or item["name"] != name:
            raise QiWorldError("semantic parent vector order mismatch")
        result.append({"name": _id(item["name"], "semantic parent name"), "sha256": _sha(item["sha256"], "semantic parent hash")})
    return result


def _strict_keys(value: Any, required: Iterable[str], *, nullable: Iterable[str] = ()) -> None:
    if not isinstance(value, Mapping):
        raise QiWorldError("object expected")
    required = set(required)
    if set(value) != required:
        raise QiWorldError(f"object fields mismatch; missing={sorted(required - set(value))}, extra={sorted(set(value) - required)}")
    for key in required - set(nullable):
        if value[key] is None:
            raise QiWorldError(f"{key} cannot be null")


def _self_hash(value: Mapping[str, Any], field_name: str, schema: str) -> str:
    return canonical_hash({key: item for key, item in value.items() if key != field_name}, schema)


def _check_self(value: Mapping[str, Any], field_name: str, schema: str) -> None:
    if value.get(field_name) != _self_hash(value, field_name, schema):
        raise QiWorldError(f"{schema} self hash mismatch")


def _scope_hash(action_scope: Mapping[str, Any] | None) -> str:
    if action_scope is None:
        # §3.1's null scope is a framed literal, not a JSON null object.
        domain = ACTION_SCOPE_SCHEMA.encode("utf-8")
        raw = b"null"
        return hashlib.sha256(len(domain).to_bytes(8, "big") + domain + len(raw).to_bytes(8, "big") + raw).hexdigest()
    return canonical_hash(action_scope, ACTION_SCOPE_SCHEMA)


# ---------------------------------------------------------------------------
# Exact action / tick objects


def _channel_values(values: Any, name: str = "requested_values") -> tuple[dict[str, str], ...]:
    if isinstance(values, Mapping):
        values = [{"channel_id": key, "unit": "unit", "value": value} for key, value in values.items()]
    if not isinstance(values, (list, tuple)) or len(values) > 256:
        raise QiWorldError(f"{name} must be a bounded channel array")
    result: list[dict[str, str]] = []
    previous = None
    for item in values:
        if isinstance(item, Mapping) and set(item) == {"channel_id", "unit", "value"}:
            channel = _id(item["channel_id"], f"{name}.channel_id")
            unit = _id(item["unit"], f"{name}.unit")
            value = _f64(item["value"])
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            channel, value = _id(item[0], f"{name}.channel_id"), _f64(item[1])
            unit = "unit"
        else:
            raise QiWorldError(f"{name} entries must be ChannelValue objects")
        if previous is not None and channel <= previous:
            raise QiWorldError(f"{name} must be strictly sorted by channel_id")
        previous = channel
        result.append({"channel_id": channel, "unit": unit, "value": value})
    return tuple(result)


def _values_payload(values: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    return [dict(value) for value in values]


@dataclass(frozen=True, slots=True)
class QiActionCommand:
    world_id: str
    episode_id: str
    action_id: str
    idempotency_key: str
    parent_step_id: str
    proposal_id: str
    logical_tick: int
    effective_tick: int
    command_timestamp_ns_telemetry: int
    valid_until_tick: int
    target_actuator: str
    body_frame_id: str
    requested_values: tuple[dict[str, str], ...]
    profile_sha256: str
    descriptor_sha256: str
    state_before_sha256: str
    current_sha256: str
    command_sha256: str = ""
    contract_root_sha256: str = ZERO_SHA256
    semantic_parents: tuple[Mapping[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in ("world_id", "episode_id", "action_id", "parent_step_id", "proposal_id", "target_actuator", "body_frame_id"):
            _id(getattr(self, name), name)
        _sha(self.idempotency_key, "idempotency_key")
        for name in ("profile_sha256", "descriptor_sha256", "state_before_sha256", "current_sha256", "contract_root_sha256"):
            _sha(getattr(self, name), name)
        for name in ("logical_tick", "effective_tick", "valid_until_tick"):
            _u64(getattr(self, name), name)
        _i64(self.command_timestamp_ns_telemetry, "command_timestamp_ns_telemetry")
        if self.effective_tick != self.logical_tick + 1 or self.valid_until_tick != self.effective_tick:
            raise QiWorldError("canonical action tick range is invalid")
        object.__setattr__(self, "requested_values", _channel_values(self.requested_values))
        object.__setattr__(self, "semantic_parents", tuple(_semantic_parents(self.semantic_parents or None, ("state_contract", "boundary_action", "world_protocol"))))
        if self.command_sha256:
            _sha(self.command_sha256, "command_sha256")
            if self.command_sha256 != _self_hash(self.payload(), "command_sha256", ACTION_SCHEMA):
                raise QiWorldError("command self hash mismatch")
        else:
            object.__setattr__(self, "command_sha256", _self_hash(self.payload(), "command_sha256", ACTION_SCHEMA))

    def payload(self) -> dict[str, Any]:
        return {
            "schema": ACTION_SCHEMA,
            "contract_root_sha256": self.contract_root_sha256,
            "profile_sha256": self.profile_sha256,
            "semantic_parents": [dict(item) for item in self.semantic_parents],
            "world_id": self.world_id,
            "episode_id": self.episode_id,
            "action_id": self.action_id,
            "idempotency_key": self.idempotency_key,
            "parent_step_id": self.parent_step_id,
            "proposal_id": self.proposal_id,
            "logical_tick": self.logical_tick,
            "effective_tick": self.effective_tick,
            "command_timestamp_ns_telemetry": self.command_timestamp_ns_telemetry,
            "valid_until_tick": self.valid_until_tick,
            "target_actuator": self.target_actuator,
            "body_frame_id": self.body_frame_id,
            "requested_values": _values_payload(self.requested_values),
            "descriptor_sha256": self.descriptor_sha256,
            "state_before_sha256": self.state_before_sha256,
            "current_sha256": self.current_sha256,
            "command_sha256": self.command_sha256,
        }

    @property
    def action_sha256(self) -> str:
        return self.command_sha256

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.payload())

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QiActionCommand":
        required = {"schema", "contract_root_sha256", "profile_sha256", "semantic_parents", "world_id", "episode_id", "action_id", "idempotency_key", "parent_step_id", "proposal_id", "logical_tick", "effective_tick", "command_timestamp_ns_telemetry", "valid_until_tick", "target_actuator", "body_frame_id", "requested_values", "descriptor_sha256", "state_before_sha256", "current_sha256", "command_sha256"}
        _strict_keys(payload, required)
        if payload["schema"] != ACTION_SCHEMA:
            raise QiWorldError("action schema mismatch")
        return cls(**{key: payload[key] for key in required if key != "schema"})

    @classmethod
    def make(cls, *, world_id: str, episode_id: str, action_id: str, logical_tick: int, requested_values: Any, profile_sha256: str, descriptor_sha256: str, state_before_sha256: str, current_sha256: str, idempotency_key: str | None = None, parent_step_id: str | None = None, proposal_id: str | None = None, command_timestamp_ns_telemetry: int = 0, effective_tick: int | None = None, valid_until_tick: int | None = None, target_actuator: str = "gaze", body_frame_id: str = "body.0", contract_root_sha256: str = ZERO_SHA256, semantic_parents: Sequence[Mapping[str, str]] | None = None, session_id: str = "session.0", cycle_number: int = 0, committed_prior_head_sha256: str = ZERO_SHA256) -> "QiActionCommand":
        effective_tick = logical_tick + 1 if effective_tick is None else effective_tick
        valid_until_tick = effective_tick if valid_until_tick is None else valid_until_tick
        parent_step_id = parent_step_id or f"step.{logical_tick}"
        proposal_id = proposal_id or f"proposal.{logical_tick}"
        values = _channel_values(requested_values)
        if idempotency_key is None:
            seed = {"world_id": world_id, "episode_id": episode_id, "profile_sha256": profile_sha256, "session_id": session_id, "cycle_number": cycle_number, "from_tick": logical_tick, "to_tick": effective_tick, "committed_prior_head_sha256": committed_prior_head_sha256, "proposal_id": proposal_id, "body_frame_id": body_frame_id, "command_scope_seed_sha256": canonical_hash({"action_id": action_id, "requested_values": _values_payload(values), "descriptor_sha256": descriptor_sha256}, "cassi.qi-flow-command-scope-seed.v1")}
            idempotency_key = canonical_hash(seed, "cassi.qi-flow-idempotency-key.v1")
        return cls(world_id, episode_id, action_id, idempotency_key, parent_step_id, proposal_id, logical_tick, effective_tick, command_timestamp_ns_telemetry, valid_until_tick, target_actuator, body_frame_id, values, profile_sha256, descriptor_sha256, state_before_sha256, current_sha256, contract_root_sha256=contract_root_sha256, semantic_parents=tuple(semantic_parents or ()))


@dataclass(frozen=True, slots=True)
class QiWorldTickIntent:
    world_id: str
    episode_id: str
    profile_sha256: str
    session_id: str
    cycle_number: int
    from_tick: int
    to_tick: int
    committed_prior_head_sha256: str
    body_frame_id: str
    idempotency_key: str
    action_scope: Mapping[str, Any] | None
    action_scope_sha256: str = ""
    canonical_intent_sha256: str = ""
    contract_root_sha256: str = ZERO_SHA256
    semantic_parents: tuple[Mapping[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in ("world_id", "episode_id", "session_id", "body_frame_id"):
            _id(getattr(self, name), name)
        for name in ("profile_sha256", "committed_prior_head_sha256", "idempotency_key", "contract_root_sha256"):
            _sha(getattr(self, name), name)
        for name in ("cycle_number", "from_tick", "to_tick"):
            _u64(getattr(self, name), name)
        if self.to_tick != self.from_tick + 1:
            raise QiWorldError("tick intent must advance exactly one logical tick")
        scope = self.action_scope
        if scope is not None:
            if not isinstance(scope, Mapping) or set(scope) != {"action_sha256", "canonical_action_bytes"}:
                raise QiWorldError("action scope fields mismatch")
            action_bytes = _bytes_value(scope["canonical_action_bytes"], "canonical_action_bytes")
            action = QiActionCommand.from_payload(canonical_json_loads(action_bytes))
            if scope["action_sha256"] != action.command_sha256:
                raise QiWorldError("action scope digest mismatch")
            object.__setattr__(self, "action_scope", {"action_sha256": _sha(scope["action_sha256"], "action_sha256"), "canonical_action_bytes": _bytes_obj(action_bytes)})
        object.__setattr__(self, "semantic_parents", tuple(_semantic_parents(self.semantic_parents or None, ("world_protocol", "session_storage"))))
        expected_scope = _scope_hash(self.action_scope)
        if self.action_scope_sha256:
            _sha(self.action_scope_sha256, "action_scope_sha256")
            if self.action_scope_sha256 != expected_scope:
                raise QiWorldError("action scope self hash mismatch")
        else:
            object.__setattr__(self, "action_scope_sha256", expected_scope)
        if self.canonical_intent_sha256:
            _sha(self.canonical_intent_sha256, "canonical_intent_sha256")
            if self.canonical_intent_sha256 != _self_hash(self.payload(), "canonical_intent_sha256", TICK_INTENT_SCHEMA):
                raise QiWorldError("intent self hash mismatch")
        else:
            object.__setattr__(self, "canonical_intent_sha256", _self_hash(self.payload(), "canonical_intent_sha256", TICK_INTENT_SCHEMA))

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.payload())

    def payload(self) -> dict[str, Any]:
        return {"schema": TICK_INTENT_SCHEMA, "contract_root_sha256": self.contract_root_sha256, "profile_sha256": self.profile_sha256, "semantic_parents": [dict(item) for item in self.semantic_parents], "world_id": self.world_id, "episode_id": self.episode_id, "session_id": self.session_id, "cycle_number": self.cycle_number, "from_tick": self.from_tick, "to_tick": self.to_tick, "committed_prior_head_sha256": self.committed_prior_head_sha256, "body_frame_id": self.body_frame_id, "idempotency_key": self.idempotency_key, "action_scope": None if self.action_scope is None else {"action_sha256": self.action_scope["action_sha256"], "canonical_action_bytes": dict(self.action_scope["canonical_action_bytes"])}, "action_scope_sha256": self.action_scope_sha256, "canonical_intent_sha256": self.canonical_intent_sha256}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QiWorldTickIntent":
        required = {"schema", "contract_root_sha256", "profile_sha256", "semantic_parents", "world_id", "episode_id", "session_id", "cycle_number", "from_tick", "to_tick", "committed_prior_head_sha256", "body_frame_id", "idempotency_key", "action_scope", "action_scope_sha256", "canonical_intent_sha256"}
        _strict_keys(payload, required, nullable=("action_scope",))
        if payload["schema"] != TICK_INTENT_SCHEMA:
            raise QiWorldError("intent schema mismatch")
        return cls(**{key: payload[key] for key in required if key != "schema"})

    @classmethod
    def make(cls, *, world_id: str, episode_id: str, profile_sha256: str, session_id: str, cycle_number: int, from_tick: int, committed_prior_head_sha256: str, body_frame_id: str, action: QiActionCommand | None = None, action_scope: Mapping[str, Any] | None = None, prediction_context_sha256: str | None = None, idempotency_key: str | None = None, contract_root_sha256: str = ZERO_SHA256, semantic_parents: Sequence[Mapping[str, str]] | None = None) -> "QiWorldTickIntent":
        # prediction_context is deliberately not a world-wire field.  Rejecting
        # it prevents future/candidate information crossing the runtime edge.
        if prediction_context_sha256 is not None:
            raise QiWorldError("prediction context is not part of the world intent")
        if action is not None and action_scope is not None:
            raise QiWorldError("provide action or action_scope, not both")
        if action is not None:
            action_scope = {"action_sha256": action.command_sha256, "canonical_action_bytes": _bytes_obj(action.canonical_bytes)}
        action_scope_hash = _scope_hash(action_scope)
        if idempotency_key is None:
            identity = {"world_id": world_id, "episode_id": episode_id, "profile_sha256": profile_sha256, "session_id": session_id, "cycle_number": cycle_number, "from_tick": from_tick, "to_tick": from_tick + 1, "committed_prior_head_sha256": committed_prior_head_sha256, "body_frame_id": body_frame_id, "action_scope_sha256": action_scope_hash}
            idempotency_key = canonical_hash(identity, "cassi.qi-flow-idempotency-key.v1")
        return cls(world_id, episode_id, profile_sha256, session_id, cycle_number, from_tick, from_tick + 1, committed_prior_head_sha256, body_frame_id, idempotency_key, action_scope, action_scope_hash, contract_root_sha256=contract_root_sha256, semantic_parents=tuple(semantic_parents or ()))


@dataclass(frozen=True, slots=True)
class QiWorldTickAck:
    tick_ack_id: str
    world_id: str
    episode_id: str
    profile_sha256: str
    session_id: str
    cycle_number: int
    from_tick: int
    to_tick: int
    committed_prior_head_sha256: str
    body_frame_id: str
    idempotency_key: str
    action_scope_sha256: str
    canonical_intent_sha256: str
    status: str
    terminal_status: str | None
    world_effect: str
    requested_values_sha256: str
    status_reason_sha256: str
    acknowledged_at_ns_telemetry: int
    terminal_result: Mapping[str, Any]
    tick_ack_sha256: str = ""
    contract_root_sha256: str = ZERO_SHA256
    semantic_parents: tuple[Mapping[str, str], ...] = ()

    def __post_init__(self) -> None:
        _id(self.tick_ack_id, "tick_ack_id")
        for name in ("world_id", "episode_id", "session_id", "body_frame_id"):
            _id(getattr(self, name), name)
        for name in ("profile_sha256", "committed_prior_head_sha256", "idempotency_key", "action_scope_sha256", "canonical_intent_sha256", "requested_values_sha256", "status_reason_sha256", "contract_root_sha256"):
            _sha(getattr(self, name), name)
        for name in ("cycle_number", "from_tick", "to_tick"):
            _u64(getattr(self, name), name)
        _i64(self.acknowledged_at_ns_telemetry, "acknowledged_at_ns_telemetry")
        if self.to_tick != self.from_tick + 1:
            raise QiWorldError("ack tick range invalid")
        if self.status not in {"accepted", "started", "applied", "rejected", "expired", "hold"}:
            raise QiWorldError("unknown acknowledgement status")
        expected_terminal = self.status if self.status in {"applied", "rejected", "expired", "hold"} else None
        if self.terminal_status != expected_terminal:
            raise QiWorldError("terminal status matrix mismatch")
        expected_effect = "true" if self.status == "applied" else "unknown" if expected_terminal is None else "false"
        if self.world_effect != expected_effect:
            raise QiWorldError("world effect matrix mismatch")
        if not isinstance(self.terminal_result, Mapping):
            raise QiWorldError("terminal result must be an object")
        result = dict(self.terminal_result)
        if set(result) != ({"kind", "application_tick", "first_visible_observation_tick", "applied_values", "body_transition", "original_result_digest"} if self.status == "applied" else {"kind", "original_result_digest"}):
            raise QiWorldError("terminal result fields mismatch")
        if result["kind"] != self.status:
            raise QiWorldError("terminal result kind mismatch")
        _sha(result["original_result_digest"], "original_result_digest")
        if self.status == "applied":
            _u64(result["application_tick"], "application_tick")
            _u64(result["first_visible_observation_tick"], "first_visible_observation_tick")
            if result["first_visible_observation_tick"] < result["application_tick"]:
                raise QiWorldError("observation visibility precedes application")
            values = _channel_values(result["applied_values"], "applied_values")
            transition = result["body_transition"]
            if not isinstance(transition, Mapping) or set(transition) != {"body_frame_before_id", "body_frame_after_id", "transform_sha256", "remap_descriptor_sha256"}:
                raise QiWorldError("body transition fields mismatch")
            _id(transition["body_frame_before_id"], "body_frame_before_id")
            _id(transition["body_frame_after_id"], "body_frame_after_id")
            _sha(transition["transform_sha256"], "transform_sha256")
            _sha(transition["remap_descriptor_sha256"], "remap_descriptor_sha256")
            result["applied_values"] = _values_payload(values)
            result["body_transition"] = dict(transition)
        object.__setattr__(self, "terminal_result", result)
        object.__setattr__(self, "semantic_parents", tuple(_semantic_parents(self.semantic_parents or None, ("world_protocol", "session_storage", "security_evidence"))))
        if self.tick_ack_sha256:
            _sha(self.tick_ack_sha256, "tick_ack_sha256")
            if self.tick_ack_sha256 != _self_hash(self.payload(), "tick_ack_sha256", TICK_ACK_SCHEMA):
                raise QiWorldError("ack self hash mismatch")
        else:
            object.__setattr__(self, "tick_ack_sha256", _self_hash(self.payload(), "tick_ack_sha256", TICK_ACK_SCHEMA))

    def payload(self) -> dict[str, Any]:
        return {"schema": TICK_ACK_SCHEMA, "contract_root_sha256": self.contract_root_sha256, "profile_sha256": self.profile_sha256, "semantic_parents": [dict(item) for item in self.semantic_parents], "tick_ack_id": self.tick_ack_id, "world_id": self.world_id, "episode_id": self.episode_id, "session_id": self.session_id, "cycle_number": self.cycle_number, "from_tick": self.from_tick, "to_tick": self.to_tick, "committed_prior_head_sha256": self.committed_prior_head_sha256, "body_frame_id": self.body_frame_id, "idempotency_key": self.idempotency_key, "action_scope_sha256": self.action_scope_sha256, "canonical_intent_sha256": self.canonical_intent_sha256, "status": self.status, "terminal_status": self.terminal_status, "world_effect": self.world_effect, "requested_values_sha256": self.requested_values_sha256, "status_reason_sha256": self.status_reason_sha256, "acknowledged_at_ns_telemetry": self.acknowledged_at_ns_telemetry, "terminal_result": dict(self.terminal_result), "tick_ack_sha256": self.tick_ack_sha256}

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.payload())

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QiWorldTickAck":
        required = {"schema", "contract_root_sha256", "profile_sha256", "semantic_parents", "tick_ack_id", "world_id", "episode_id", "session_id", "cycle_number", "from_tick", "to_tick", "committed_prior_head_sha256", "body_frame_id", "idempotency_key", "action_scope_sha256", "canonical_intent_sha256", "status", "terminal_status", "world_effect", "requested_values_sha256", "status_reason_sha256", "acknowledged_at_ns_telemetry", "terminal_result", "tick_ack_sha256"}
        _strict_keys(payload, required, nullable=("terminal_status",))
        if payload["schema"] != TICK_ACK_SCHEMA:
            raise QiWorldError("ack schema mismatch")
        return cls(**{key: payload[key] for key in required if key != "schema"})


# Public object builders/parsers used by W12A and tests.
def build_action_command(**kwargs: Any) -> dict[str, Any]:
    return QiActionCommand.make(**kwargs).payload()


def parse_action_command(payload: Mapping[str, Any]) -> QiActionCommand:
    return QiActionCommand.from_payload(payload)


def build_tick_intent(**kwargs: Any) -> dict[str, Any]:
    return QiWorldTickIntent.make(**kwargs).payload()


def parse_tick_intent(payload: Mapping[str, Any]) -> QiWorldTickIntent:
    return QiWorldTickIntent.from_payload(payload)


def build_tick_ack(**kwargs: Any) -> dict[str, Any]:
    return QiWorldTickAck(**kwargs).payload()


def parse_tick_ack(payload: Mapping[str, Any]) -> QiWorldTickAck:
    return QiWorldTickAck.from_payload(payload)


# ---------------------------------------------------------------------------
# World observations/descriptors and deterministic bounded environment


@dataclass(frozen=True, slots=True)
class QiActionChannel:
    channel_id: str
    physical_unit: str
    minimum: str
    maximum: str
    zero: str
    quantization: str
    slew: str
    latency_ticks: int
    horizon_ticks: int
    capability: bool

    def payload(self) -> dict[str, Any]:
        return {"channel_id": _id(self.channel_id, "channel_id"), "physical_unit": _id(self.physical_unit, "physical_unit"), "minimum": _f64(self.minimum), "maximum": _f64(self.maximum), "zero": _f64(self.zero), "quantization": _f64(self.quantization), "slew": _f64(self.slew), "latency_ticks": _u64(self.latency_ticks, "latency_ticks"), "horizon_ticks": _u64(self.horizon_ticks, "horizon_ticks"), "capability": bool(self.capability)}


@dataclass(frozen=True, slots=True)
class QiActionDescriptor:
    action_descriptor_id: str
    target_actuator: str
    body_frame_id: str
    geometry_sha256: str
    cost_model_sha256: str
    bounds_sha256: str
    capability_sha256: str
    operator_sha256: str

    def __post_init__(self) -> None:
        for name in ("action_descriptor_id", "target_actuator", "body_frame_id"):
            _id(getattr(self, name), name)
        for name in ("geometry_sha256", "cost_model_sha256", "bounds_sha256", "capability_sha256", "operator_sha256"):
            _sha(getattr(self, name), name)

    @property
    def action_id(self) -> str:
        return self.action_descriptor_id

    @property
    def descriptor_sha256(self) -> str:
        return canonical_hash(self.payload(), "cassi.qi-world-action-descriptor.v1")

    def payload(self) -> dict[str, Any]:
        return {"action_descriptor_id": self.action_descriptor_id, "target_actuator": self.target_actuator, "body_frame_id": self.body_frame_id, "geometry_sha256": self.geometry_sha256, "cost_model_sha256": self.cost_model_sha256, "bounds_sha256": self.bounds_sha256, "capability_sha256": self.capability_sha256, "operator_sha256": self.operator_sha256}


@dataclass(frozen=True, slots=True)
class QiWorldObservation:
    logical_tick: int
    capture_interval: Mapping[str, Any]
    source_epoch: int
    source_stream_id: str
    source_sequence: int
    watermark: Mapping[str, Any]
    body_frame_id: str
    modality: str
    descriptor_sha256: str
    payload_dtype: str
    payload_shape: tuple[int, ...]
    physical_unit: str
    data: bytes

    def __post_init__(self) -> None:
        _u64(self.logical_tick, "logical_tick")
        object.__setattr__(self, "capture_interval", _capture_interval(self.capture_interval))
        _u64(self.source_epoch, "source_epoch")
        _id(self.source_stream_id, "source_stream_id")
        _u64(self.source_sequence, "source_sequence")
        object.__setattr__(self, "watermark", _watermark(self.watermark))
        _id(self.body_frame_id, "body_frame_id")
        _id(self.modality, "modality")
        _sha(self.descriptor_sha256, "descriptor_sha256")
        if self.payload_dtype not in {"f32le", "f64le"}:
            raise QiWorldError("payload dtype mismatch")
        shape = tuple(_u64(item, "payload_shape") for item in self.payload_shape)
        if not 1 <= len(shape) <= 8 or any(item < 1 for item in shape):
            raise QiWorldError("payload shape must have 1..8 positive dimensions")
        object.__setattr__(self, "payload_shape", shape)
        _id(self.physical_unit, "physical_unit")
        if not isinstance(self.data, bytes):
            object.__setattr__(self, "data", bytes(self.data))
        expected = math.prod(shape) * (4 if self.payload_dtype == "f32le" else 8)
        if expected != len(self.data):
            raise QiWorldError("payload bytes do not match dtype/shape")

    @property
    def data_sha256(self) -> str:
        return _sha256_bytes(self.data)

    @property
    def frame_id(self) -> str:
        # Python convenience only; never serialized on the exact wire.
        return self.body_frame_id

    def payload(self) -> dict[str, Any]:
        return {"logical_tick": self.logical_tick, "capture_interval": dict(self.capture_interval), "source_epoch": self.source_epoch, "source_stream_id": self.source_stream_id, "source_sequence": self.source_sequence, "watermark": dict(self.watermark), "body_frame_id": self.body_frame_id, "modality": self.modality, "descriptor_sha256": self.descriptor_sha256, "payload_dtype": self.payload_dtype, "payload_shape": list(self.payload_shape), "physical_unit": self.physical_unit}

    @property
    def canonical_bytes(self) -> bytes:
        return self.data

    def extension(self) -> dict[str, Any]:
        return self.payload()


@dataclass(frozen=True, slots=True)
class WorldSchedule:
    optical: Fraction = Fraction(1, 1)
    audio: Fraction = Fraction(1, 1)
    proprioceptive: Fraction = Fraction(1, 1)
    actuator: Fraction = Fraction(1, 1)

    def __post_init__(self) -> None:
        for name in ("optical", "audio", "proprioceptive", "actuator"):
            value = getattr(self, name)
            if not isinstance(value, Fraction) or value <= 0:
                raise WorldStateError(f"{name} cadence must be positive rational")

    def period(self, modality: str) -> Fraction:
        if modality not in {"optical", "audio", "proprioceptive", "actuator"}:
            raise WorldStateError("unknown schedule modality")
        return getattr(self, modality)

    def due(self, modality: str, tick: int) -> bool:
        _u64(tick, "tick")
        return Fraction(tick, 1) % self.period(modality) == 0

    def payload(self) -> dict[str, Any]:
        return {name: {"n": getattr(self, name).numerator, "d": getattr(self, name).denominator} for name in ("optical", "audio", "proprioceptive", "actuator")}


@dataclass(slots=True)
class _WorldObject:
    object_id: str
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    phase: float


class QiWorldPort(Protocol):
    @property
    def world_id(self) -> str: ...
    @property
    def episode_id(self) -> str: ...
    @property
    def profile_sha256(self) -> str: ...
    @property
    def session_id(self) -> str: ...
    @property
    def body_frame_id(self) -> str: ...
    @property
    def logical_tick(self) -> int: ...
    @property
    def state_sha256(self) -> str: ...

    def observe(self, tick: int, watermark: Mapping[str, Any], requested_modalities: Sequence[str] | None = None, *, max_packets: int | None = None) -> tuple[QiWorldObservation, ...]: ...
    def describe_actions(self, tick: int) -> tuple[QiActionDescriptor, ...]: ...
    def advance_tick(self, intent: QiWorldTickIntent) -> QiWorldTickAck: ...
    def resolve_tick(self, intent: QiWorldTickIntent) -> QiWorldTickAck: ...


class DeterministicQiWorld:
    """Analytic bounded world; object identities never enter observation bytes."""

    optical_shape = (16, 16)
    audio_shape = (32,)
    proprioceptive_shape = (2,)
    actuator_shape = (2,)

    def __init__(self, seed: int = 0, *, world_id: str = "world.ref", episode_id: str = "episode.0", profile_sha256: str | None = None, boundary_registry_sha256: str | None = None, clock_sha256: str | None = None, session_id: str = "session.0", schedule: WorldSchedule | None = None, object_count: int = 5, physics_steps_per_tick: int = 1, occlusion: bool = True, body_frame_id: str = "body.0") -> None:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_U64:
            raise WorldStateError("seed must be an unsigned exact integer")
        if not 1 <= object_count <= 64 or not 1 <= physics_steps_per_tick <= 64:
            raise WorldStateError("bounded world dimensions outside range")
        self.seed = seed
        self.world_id, self.episode_id, self.session_id, self.body_frame_id = _id(world_id, "world_id"), _id(episode_id, "episode_id"), _id(session_id, "session_id"), _id(body_frame_id, "body_frame_id")
        self.profile_sha256 = _sha(profile_sha256 or canonical_hash({"world_id": self.world_id, "episode_id": self.episode_id}, "cassi.qi-world-profile.v1"), "profile_sha256")
        self.boundary_registry_sha256 = _sha(boundary_registry_sha256 or canonical_hash({"modalities": ["audio", "optical", "proprioceptive"]}, "cassi.qi-world-boundary.v1"), "boundary_registry_sha256")
        self.clock_sha256 = _sha(clock_sha256 or canonical_hash({"schedule": (schedule or WorldSchedule()).payload()}, "cassi.qi-flow-clock.v1"), "clock_sha256")
        self.schedule = schedule or WorldSchedule()
        self.object_count, self.physics_steps_per_tick, self.occlusion = object_count, physics_steps_per_tick, bool(occlusion)
        self.logical_tick = 0
        self._agent_x = self._agent_y = self._agent_vx = self._agent_vy = 0.0
        self._last_action_id: str | None = None
        self._last_values: tuple[dict[str, str], ...] = ()
        self._closed = False
        self._objects = self._make_objects(object_count)
        self._seen: dict[str, tuple[bytes, QiWorldTickAck]] = {}
        self._tick_log: list[dict[str, Any]] = []
        self.source_identity_sha256 = canonical_hash(self._identity_payload(), "cassi.qi-world-source-identity.v1")
        self.world_identity_sha256 = canonical_hash({**self._identity_payload(), "source_identity_sha256": self.source_identity_sha256}, "cassi.qi-world-identity.v1")
        self._initial_snapshot = self.snapshot()

    def _identity_payload(self) -> dict[str, Any]:
        return {"world_id": self.world_id, "episode_id": self.episode_id, "seed": self.seed, "schedule": self.schedule.payload(), "object_count": self.object_count, "physics_steps_per_tick": self.physics_steps_per_tick, "occlusion": self.occlusion, "modalities": ["optical", "audio", "proprioceptive"]}

    def _make_objects(self, count: int) -> list[_WorldObject]:
        result: list[_WorldObject] = []
        for index in range(count):
            digest = hashlib.sha256(f"{self.seed}:object:{index}".encode("ascii")).digest()
            result.append(_WorldObject(f"object.{index}", -0.82 + (digest[0] / 255.0) * 1.64, -0.82 + (digest[1] / 255.0) * 1.64, -0.018 + (digest[2] / 255.0) * 0.036, -0.018 + (digest[3] / 255.0) * 0.036, 0.025 + (digest[4] / 255.0) * 0.04, digest[5] / 255.0 * math.tau))
        return result

    @property
    def objects(self) -> tuple[tuple[float, float, float, float, float], ...]:
        # No object IDs: this is a geometry-only test hook.
        return tuple((obj.x, obj.y, obj.vx, obj.vy, obj.radius) for obj in self._objects)

    def _state_payload(self) -> dict[str, Any]:
        return {"schema": "cassi.qi-world-state.v1", "world_id": self.world_id, "episode_id": self.episode_id, "seed": self.seed, "logical_tick": self.logical_tick, "body_frame_id": self.body_frame_id, "agent": [_f64(self._agent_x), _f64(self._agent_y), _f64(self._agent_vx), _f64(self._agent_vy)], "objects": [{"object_id": obj.object_id, "x": _f64(obj.x), "y": _f64(obj.y), "vx": _f64(obj.vx), "vy": _f64(obj.vy), "radius": _f64(obj.radius), "phase": _f64(obj.phase)} for obj in self._objects], "last_action_id": self._last_action_id, "last_values": _values_payload(self._last_values), "closed": self._closed}

    @property
    def state_sha256(self) -> str:
        return canonical_hash(self._state_payload(), "cassi.qi-world-state.v1")

    def _snapshot_payload(self) -> dict[str, Any]:
        return {"schema": "cassi.qi-world-snapshot.v1", "identity": self._identity_payload(), "state": self._state_payload(), "tick_log": [{"intent_bytes": _bytes_obj(entry["intent_bytes"]), "ack_bytes": _bytes_obj(entry["ack_bytes"])} for entry in self._tick_log]}

    @property
    def snapshot_sha256(self) -> str:
        return canonical_hash(self._snapshot_payload(), "cassi.qi-world-snapshot.v1")

    def snapshot(self) -> dict[str, Any]:
        body = self._snapshot_payload()
        body["snapshot_sha256"] = canonical_hash(body, "cassi.qi-world-snapshot.v1")
        return body

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        if not isinstance(snapshot, Mapping) or set(snapshot) != {"schema", "identity", "state", "tick_log", "snapshot_sha256"} or snapshot["schema"] != "cassi.qi-world-snapshot.v1":
            raise WorldStateError("snapshot fields mismatch")
        body = {key: snapshot[key] for key in snapshot if key != "snapshot_sha256"}
        if snapshot["snapshot_sha256"] != canonical_hash(body, "cassi.qi-world-snapshot.v1") or snapshot["identity"] != self._identity_payload():
            raise WorldStateError("snapshot identity mismatch")
        state = snapshot["state"]
        if not isinstance(state, Mapping) or state.get("schema") != "cassi.qi-world-state.v1" or state.get("world_id") != self.world_id or state.get("episode_id") != self.episode_id or state.get("seed") != self.seed:
            raise WorldStateError("state identity mismatch")
        self.logical_tick = _u64(state["logical_tick"], "logical_tick")
        self.body_frame_id = _id(state["body_frame_id"], "body_frame_id")
        agent = state["agent"]
        if not isinstance(agent, list) or len(agent) != 4:
            raise WorldStateError("agent state shape mismatch")
        self._agent_x, self._agent_y, self._agent_vx, self._agent_vy = (_f64_value(item) for item in agent)
        objects = state["objects"]
        if not isinstance(objects, list) or len(objects) != self.object_count:
            raise WorldStateError("object state count mismatch")
        restored: list[_WorldObject] = []
        for item in objects:
            if not isinstance(item, Mapping) or set(item) != {"object_id", "x", "y", "vx", "vy", "radius", "phase"}:
                raise WorldStateError("object state fields mismatch")
            restored.append(_WorldObject(_id(item["object_id"], "object_id"), _f64_value(item["x"]), _f64_value(item["y"]), _f64_value(item["vx"]), _f64_value(item["vy"]), _f64_value(item["radius"]), _f64_value(item["phase"])))
        self._objects = restored
        self._last_action_id = None if state["last_action_id"] is None else _id(state["last_action_id"], "last_action_id")
        self._last_values = _channel_values(state["last_values"], "last_values")
        if not isinstance(state["closed"], bool):
            raise WorldStateError("closed flag must be bool")
        self._closed = state["closed"]
        self._tick_log = []
        for entry in snapshot["tick_log"]:
            if not isinstance(entry, Mapping) or set(entry) != {"intent_bytes", "ack_bytes"}:
                raise WorldStateError("tick log fields mismatch")
            self._tick_log.append({"intent_bytes": _bytes_value(entry["intent_bytes"], "intent_bytes"), "ack_bytes": _bytes_value(entry["ack_bytes"], "ack_bytes")})

    def reset(self) -> None:
        self.restore(self._initial_snapshot)

    def restart_provider(self) -> dict[str, Any]:
        # A provider-local restart does not touch world state or identities.
        return {"restart_kind": "provider", "world_id": self.world_id, "episode_id": self.episode_id, "session_id": self.session_id, "logical_tick": self.logical_tick, "state_sha256": self.state_sha256}

    def restart_world(self) -> None:
        # Full world restart is the only operation allowed to rewind truth.
        self.reset()

    def _watermark_hash(self, watermark: Mapping[str, Any]) -> str:
        return canonical_hash(_watermark(watermark), "cassi.qi-world-watermark.v1")

    def _pixel(self, x: int, y: int, tick: int) -> float:
        wx = (x + 0.5) / self.optical_shape[0] * 2.0 - 1.0
        wy = (y + 0.5) / self.optical_shape[1] * 2.0 - 1.0
        value = 0.03 * math.sin((x + 1) * 0.47 + (y + 1) * 0.23 + tick * 0.17 + self.seed * 0.01)
        candidates = sorted((math.hypot(wx - obj.x, wy - obj.y), index) for index, obj in enumerate(self._objects))
        for distance, index in candidates:
            obj = self._objects[index]
            if self.occlusion and any(other_index != index and other_distance + 0.001 < distance and self._objects[other_index].radius > obj.radius * 0.85 for other_distance, other_index in candidates):
                continue
            if distance <= obj.radius:
                value += 0.75 * (1.0 - distance / obj.radius)
                break
        return max(-1.0, min(1.0, value))

    def _render_optical(self) -> bytes:
        return struct.pack("<" + "f" * math.prod(self.optical_shape), *[self._pixel(x, y, self.logical_tick) for y in range(self.optical_shape[1]) for x in range(self.optical_shape[0])])

    def _render_audio(self) -> bytes:
        values = [0.2 * math.sin(2.0 * math.pi * (index + 1) / self.audio_shape[0] + self.logical_tick * 0.13 + self.seed * 0.001) for index in range(self.audio_shape[0])]
        return struct.pack("<" + "f" * len(values), *values)

    def _render_proprioceptive(self) -> bytes:
        return struct.pack("<ff", self._agent_x, self._agent_y)

    def _descriptor_hash(self, modality: str) -> str:
        return canonical_hash({"modality": modality, "shape": list(getattr(self, f"{modality}_shape")), "dtype": "f32le", "unit": "normalized"}, "cassi.qi-world-observation-descriptor.v1")

    def _observation(self, modality: str, data: bytes, watermark: Mapping[str, Any], sequence: int) -> QiWorldObservation:
        return QiWorldObservation(self.logical_tick, {"capture_start": {"n": self.logical_tick, "d": 1}, "capture_end": {"n": self.logical_tick + 1, "d": 1}}, 1, f"{modality}.0", sequence, watermark, self.body_frame_id, modality, self._descriptor_hash(modality), "f32le", tuple(getattr(self, f"{modality}_shape")), "normalized", data)

    def observe(self, tick: int, watermark: Mapping[str, Any], requested_modalities: Sequence[str] | None = None, *, max_packets: int | None = None) -> tuple[QiWorldObservation, ...]:
        if self._closed:
            raise WorldStateError("world is closed")
        _u64(tick, "logical_tick")
        if tick != self.logical_tick:
            raise WorldStateError("observations are only available at committed logical tick")
        wm = _watermark(watermark)
        modalities = tuple(requested_modalities or ("optical", "audio", "proprioceptive"))
        if len(modalities) > 32 or len(set(modalities)) != len(modalities) or any(item not in {"optical", "audio", "proprioceptive"} for item in modalities):
            raise WorldStateError("unknown or duplicate modality")
        if max_packets is not None and (not isinstance(max_packets, int) or max_packets < 0 or max_packets > 4096):
            raise WorldStateError("max_packets outside bound")
        result: list[QiWorldObservation] = []
        sequence = 0
        for modality in modalities:
            if not self.schedule.due(modality, tick):
                continue
            data = self._render_optical() if modality == "optical" else self._render_audio() if modality == "audio" else self._render_proprioceptive()
            result.append(self._observation(modality, data, wm, sequence))
            sequence += 1
        if max_packets is not None and len(result) > max_packets:
            raise WorldStateError("observation packet budget exceeded")
        return tuple(result)

    def describe_actions(self, tick: int) -> tuple[QiActionDescriptor, ...]:
        if tick != self.logical_tick:
            raise WorldStateError("action descriptions are tick-bound")
        base = {"body_frame_id": self.body_frame_id, "target_actuator": "gaze"}
        result = []
        for action_id in ("action.gaze-left", "action.gaze-right", "action.gaze-up", "action.gaze-down", "action.hold"):
            result.append(QiActionDescriptor(action_id, base["target_actuator"] if action_id != "action.hold" else "hold", self.body_frame_id, canonical_hash({**base, "action": action_id}, "cassi.qi-world-geometry.v1"), canonical_hash({"action": action_id, "cost": "f64:0000000000000000"}, "cassi.qi-world-cost.v1"), canonical_hash({"minimum": "f64:bfd0000000000000", "maximum": "f64:3fd0000000000000"}, "cassi.qi-world-bounds.v1"), canonical_hash({"action": action_id, "capability": True}, "cassi.qi-world-capability.v1"), canonical_hash({"action": action_id, "operator": "bounded-translation-v1"}, "cassi.qi-world-operator.v1")))
        return tuple(result)

    def _validate_action(self, action: QiActionCommand) -> None:
        if action.world_id != self.world_id or action.episode_id != self.episode_id or action.profile_sha256 != self.profile_sha256 or action.body_frame_id != self.body_frame_id or action.logical_tick != self.logical_tick or action.effective_tick != self.logical_tick + 1:
            raise WorldStateError("action identity/tick mismatch")
        descriptors = {descriptor.action_descriptor_id: descriptor for descriptor in self.describe_actions(self.logical_tick)}
        descriptor = descriptors.get(action.action_id)
        if descriptor is None or action.descriptor_sha256 != descriptor.descriptor_sha256:
            # action_id is a command identity, descriptor hash binds the exact
            # fixed descriptor; no unknown action or candidate outcome is seen.
            raise WorldStateError("unknown or mismatched action descriptor")
        if action.action_id == "action.hold":
            if action.requested_values:
                raise WorldStateError("hold action must have no values")
            return
        if len(action.requested_values) != 1 or action.requested_values[0]["channel_id"] != "gaze.yaw" and action.requested_values[0]["channel_id"] != "gaze.pitch":
            raise WorldStateError("gaze action requires exactly one channel")
        value = _f64_value(action.requested_values[0]["value"])
        if not -1.0 <= value <= 1.0:
            raise WorldStateError("action value outside descriptor bounds")

    def _advance_environment(self, action: QiActionCommand | None) -> None:
        self._agent_vx = self._agent_vy = 0.0
        if action is not None and action.action_id != "action.hold":
            value = _f64_value(action.requested_values[0]["value"])
            if action.action_id.endswith("left"):
                self._agent_vx = -0.08 * value
            elif action.action_id.endswith("right"):
                self._agent_vx = 0.08 * value
            elif action.action_id.endswith("up"):
                self._agent_vy = 0.08 * value
            elif action.action_id.endswith("down"):
                self._agent_vy = -0.08 * value
        for _ in range(self.physics_steps_per_tick):
            self._agent_x = max(-1.0, min(1.0, self._agent_x + self._agent_vx))
            self._agent_y = max(-1.0, min(1.0, self._agent_y + self._agent_vy))
            for obj in self._objects:
                obj.x += obj.vx
                obj.y += obj.vy
                if not -0.85 <= obj.x <= 0.85:
                    obj.vx = -obj.vx
                    obj.x = max(-0.85, min(0.85, obj.x))
                if not -0.85 <= obj.y <= 0.85:
                    obj.vy = -obj.vy
                    obj.y = max(-0.85, min(0.85, obj.y))
                obj.phase = (obj.phase + 0.03) % math.tau
        self.logical_tick += 1

    def _make_ack(self, intent: QiWorldTickIntent, action: QiActionCommand | None, *, status: str, world_effect: str, prior_values: Sequence[Mapping[str, str]] = ()) -> QiWorldTickAck:
        requested = () if action is None else action.requested_values
        requested_hash = canonical_hash(_values_payload(requested), "cassi.qi-world-requested-values.v1")
        reason = "applied" if status == "applied" else "hold" if status == "hold" else "rejected" if status == "rejected" else status
        reason_hash = canonical_hash(reason, "cassi.qi-world-status-reason.v1")
        if status == "applied":
            result_core = {"kind": "applied", "application_tick": intent.to_tick, "first_visible_observation_tick": intent.to_tick, "applied_values": _values_payload(requested), "body_transition": {"body_frame_before_id": intent.body_frame_id, "body_frame_after_id": intent.body_frame_id, "transform_sha256": canonical_hash({"before": intent.body_frame_id, "after": intent.body_frame_id}, "cassi.qi-world-body-transform.v1"), "remap_descriptor_sha256": canonical_hash({"body_frame_id": intent.body_frame_id}, "cassi.qi-world-remap.v1")}}
        else:
            result_core = {"kind": status}
        result_digest = canonical_hash(result_core, "cassi.qi-world-terminal-result.v1")
        terminal_result = {**result_core, "original_result_digest": result_digest}
        ack_id = f"ack.{intent.canonical_intent_sha256[:32]}"
        return QiWorldTickAck(ack_id, self.world_id, self.episode_id, self.profile_sha256, self.session_id, intent.cycle_number, intent.from_tick, intent.to_tick, intent.committed_prior_head_sha256, intent.body_frame_id, intent.idempotency_key, intent.action_scope_sha256, intent.canonical_intent_sha256, status, status if status in {"applied", "rejected", "expired", "hold"} else None, world_effect, requested_hash, reason_hash, 0, terminal_result)

    def _validate_intent(self, intent: QiWorldTickIntent) -> QiActionCommand | None:
        if not isinstance(intent, QiWorldTickIntent):
            raise WorldStateError("tick intent type mismatch")
        if (intent.world_id, intent.episode_id, intent.profile_sha256, intent.session_id) != (self.world_id, self.episode_id, self.profile_sha256, self.session_id):
            raise WorldStateError("tick intent identity mismatch")
        if intent.from_tick != self.logical_tick or intent.to_tick != self.logical_tick + 1:
            raise WorldStateError("wrong, skipped, repeated, or future logical tick")
        if intent.committed_prior_head_sha256 != self.state_sha256:
            raise WorldStateError("committed prior head mismatch")
        if intent.action_scope is None:
            return None
        action = QiActionCommand.from_payload(canonical_json_loads(_bytes_value(intent.action_scope["canonical_action_bytes"], "canonical_action_bytes")))
        self._validate_action(action)
        return action

    def advance_tick(self, intent: QiWorldTickIntent) -> QiWorldTickAck:
        if self._closed:
            raise WorldStateError("world is closed")
        existing = self._seen.get(intent.idempotency_key)
        if existing is not None:
            if existing[0] != intent.canonical_bytes:
                raise WorldStateError("idempotency key reused with different intent bytes")
            return existing[1]
        action = self._validate_intent(intent)
        status = "hold" if action is None or action.action_id == "action.hold" else "applied"
        self._advance_environment(action)
        self._last_action_id = None if action is None else action.action_id
        self._last_values = () if action is None else action.requested_values
        ack = self._make_ack(intent, action, status=status, world_effect="false" if status == "hold" else "true")
        self._seen[intent.idempotency_key] = (intent.canonical_bytes, ack)
        self._tick_log.append({"intent_bytes": intent.canonical_bytes, "ack_bytes": ack.canonical_bytes})
        return ack

    def resolve_tick(self, intent: QiWorldTickIntent) -> QiWorldTickAck:
        existing = self._seen.get(intent.idempotency_key)
        if existing is None or existing[0] != intent.canonical_bytes:
            raise WorldStateError("resolve requires exact retained intent bytes")
        return existing[1]

    def step(self, action: QiActionCommand | None = None, *, cycle_number: int | None = None, committed_prior_head_sha256: str | None = None) -> QiWorldTickAck:
        cycle = self.logical_tick if cycle_number is None else cycle_number
        prior = self.state_sha256 if committed_prior_head_sha256 is None else committed_prior_head_sha256
        intent = QiWorldTickIntent.make(world_id=self.world_id, episode_id=self.episode_id, profile_sha256=self.profile_sha256, session_id=self.session_id, cycle_number=cycle, from_tick=self.logical_tick, committed_prior_head_sha256=prior, body_frame_id=self.body_frame_id, action=action)
        return self.advance_tick(intent)


# ---------------------------------------------------------------------------
# Exact world-wire extension validators/builders


def _sorted_ids(values: Sequence[str], name: str, *, max_len: int = 32) -> list[str]:
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= max_len:
        raise WireError(f"{name} length outside bound")
    result = [_id(value, name) for value in values]
    if result != sorted(set(result)):
        raise WireError(f"{name} must be sorted and unique")
    return result


def _validate_descriptor(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"action_descriptor_id", "target_actuator", "body_frame_id", "geometry_sha256", "cost_model_sha256", "bounds_sha256", "capability_sha256", "operator_sha256"}:
        raise WireError("descriptor fields mismatch")
    descriptor = QiActionDescriptor(value["action_descriptor_id"], value["target_actuator"], value["body_frame_id"], value["geometry_sha256"], value["cost_model_sha256"], value["bounds_sha256"], value["capability_sha256"], value["operator_sha256"])
    return descriptor.payload()


def _validate_extension(kind: str, extension: Mapping[str, Any], raw: bytes) -> dict[str, Any]:
    if not isinstance(extension, Mapping):
        raise WireError("kind extension must be an object")
    ext = dict(extension)
    expected: set[str] = {
        "hello": {"client_nonce", "supported_protocol_versions", "requested_capabilities", "client_process_creation_identity_sha256"},
        "hello_ack": {"echo_client_nonce", "server_process_creation_identity_sha256", "negotiated_protocol_version", "negotiated_capabilities", "retention"},
        "observe_request": {"logical_tick", "watermark", "requested_modalities"},
        "observation": {"logical_tick", "capture_interval", "source_epoch", "source_stream_id", "source_sequence", "watermark", "body_frame_id", "modality", "descriptor_sha256", "payload_dtype", "payload_shape", "physical_unit"},
        "observation_complete": {"logical_tick", "watermark", "observation_count", "observation_set_sha256"},
        "describe_actions": {"logical_tick"},
        "action_descriptors": {"logical_tick", "descriptors", "descriptor_set_sha256"},
        "advance_tick": {"tick_intent"},
        "resolve_tick": {"tick_intent"},
        "tick_complete": {"delivery", "tick_ack", "original_result_digest"},
        "heartbeat": {"liveness_nonce", "last_received_message_sequence"},
        "heartbeat_ack": {"echo_liveness_nonce", "last_received_message_sequence"},
        "close": {"close_reason", "last_received_message_sequence"},
        "close_ack": {"close_reason", "last_received_message_sequence"},
        "error": {"failed_kind", "error_code", "retryable", "error_detail_sha256"},
    }[kind]
    if set(ext) != expected:
        raise WireError(f"{kind} extension fields mismatch")
    if kind == "hello":
        if not isinstance(ext["client_nonce"], str) or not re.fullmatch(r"[0-9a-f]{32}", ext["client_nonce"]): raise WireError("client nonce mismatch")
        if ext["supported_protocol_versions"] != ["1"]: raise WireError("protocol negotiation mismatch")
        ext["requested_capabilities"] = _sorted_ids(ext["requested_capabilities"], "requested_capabilities")
        _sha(ext["client_process_creation_identity_sha256"], "client_process_creation_identity_sha256")
    elif kind == "hello_ack":
        if not isinstance(ext["echo_client_nonce"], str) or not re.fullmatch(r"[0-9a-f]{32}", ext["echo_client_nonce"]): raise WireError("echo nonce mismatch")
        _sha(ext["server_process_creation_identity_sha256"], "server_process_creation_identity_sha256")
        if ext["negotiated_protocol_version"] != "1": raise WireError("protocol negotiation mismatch")
        ext["negotiated_capabilities"] = _sorted_ids(ext["negotiated_capabilities"], "negotiated_capabilities")
        if not isinstance(ext["retention"], Mapping) or set(ext["retention"]) != {"outbox_age_ticks", "reconnect_ticks", "retry_ticks"}: raise WireError("retention fields mismatch")
        for key in ext["retention"]: _u64(ext["retention"][key], f"retention.{key}")
    elif kind == "observe_request":
        _u64(ext["logical_tick"], "logical_tick"); ext["watermark"] = _watermark(ext["watermark"]); ext["requested_modalities"] = _sorted_ids(ext["requested_modalities"], "requested_modalities")
        if any(item not in {"audio", "optical", "proprioceptive"} for item in ext["requested_modalities"]): raise WireError("unknown requested modality")
    elif kind == "observation":
        _u64(ext["logical_tick"], "logical_tick"); ext["capture_interval"] = _capture_interval(ext["capture_interval"]); _u64(ext["source_epoch"], "source_epoch"); _id(ext["source_stream_id"], "source_stream_id"); _u64(ext["source_sequence"], "source_sequence"); ext["watermark"] = _watermark(ext["watermark"]); _id(ext["body_frame_id"], "body_frame_id"); _id(ext["modality"], "modality"); _sha(ext["descriptor_sha256"], "descriptor_sha256")
        if ext["payload_dtype"] not in {"f32le", "f64le"}: raise WireError("payload dtype mismatch")
        shape = ext["payload_shape"]
        if not isinstance(shape, list) or not 1 <= len(shape) <= 8 or any(_u64(item, "payload_shape") < 1 for item in shape): raise WireError("payload shape mismatch")
        element_size = 4 if ext["payload_dtype"] == "f32le" else 8
        if math.prod(shape) * element_size != len(raw): raise WireError("observation payload shape/byte mismatch")
        _id(ext["physical_unit"], "physical_unit")
    elif kind == "observation_complete":
        _u64(ext["logical_tick"], "logical_tick"); ext["watermark"] = _watermark(ext["watermark"]); _u64(ext["observation_count"], "observation_count"); _sha(ext["observation_set_sha256"], "observation_set_sha256")
        if raw: raise WireError("observation complete has no raw payload")
    elif kind == "describe_actions":
        _u64(ext["logical_tick"], "logical_tick");
    elif kind == "action_descriptors":
        _u64(ext["logical_tick"], "logical_tick")
        descriptors = ext["descriptors"]
        if not isinstance(descriptors, list) or len(descriptors) > 256: raise WireError("descriptor count outside bound")
        normalized = [_validate_descriptor(item) for item in descriptors]
        if [item["action_descriptor_id"] for item in normalized] != sorted(item["action_descriptor_id"] for item in normalized): raise WireError("descriptors not sorted")
        ext["descriptors"] = normalized
        _sha(ext["descriptor_set_sha256"], "descriptor_set_sha256")
        if ext["descriptor_set_sha256"] != canonical_hash(normalized, "cassi.qi-world-action-descriptor-set.v1"): raise WireError("descriptor set digest mismatch")
    elif kind in {"advance_tick", "resolve_tick"}:
        if not isinstance(ext["tick_intent"], Mapping): raise WireError("nested tick intent required")
        intent = QiWorldTickIntent.from_payload(ext["tick_intent"])
        ext["tick_intent"] = intent.payload()
    elif kind == "tick_complete":
        if ext["delivery"] not in {"original", "duplicate"}: raise WireError("delivery mismatch")
        if not isinstance(ext["tick_ack"], Mapping): raise WireError("nested tick ack required")
        ack = QiWorldTickAck.from_payload(ext["tick_ack"])
        ext["tick_ack"] = ack.payload(); _sha(ext["original_result_digest"], "original_result_digest")
        if ext["original_result_digest"] != ack.terminal_result["original_result_digest"]: raise WireError("original result digest mismatch")
    elif kind == "heartbeat":
        _id(ext["liveness_nonce"], "liveness_nonce"); _u64(ext["last_received_message_sequence"], "last_received_message_sequence")
    elif kind == "heartbeat_ack":
        _id(ext["echo_liveness_nonce"], "echo_liveness_nonce"); _u64(ext["last_received_message_sequence"], "last_received_message_sequence")
    elif kind in {"close", "close_ack"}:
        if ext["close_reason"] not in {"normal", "client_shutdown", "server_shutdown", "protocol_error"}: raise WireError("close reason mismatch")
        _u64(ext["last_received_message_sequence"], "last_received_message_sequence")
    elif kind == "error":
        _id(ext["failed_kind"], "failed_kind")
        _id(ext["error_code"], "error_code")
        if ext["retryable"] is not False: raise WireError("world error must not be retryable")
        _sha(ext["error_detail_sha256"], "error_detail_sha256")
    if kind != "observation" and raw:
        raise WireError(f"{kind} does not permit a raw payload")
    return ext


def build_hello(*, client_nonce: str, supported_protocol_versions: Sequence[str] = ("1",), requested_capabilities: Sequence[str] = ("audio", "motor", "optical", "proprio"), client_process_creation_identity_sha256: str) -> dict[str, Any]:
    return _validate_extension("hello", {"client_nonce": client_nonce, "supported_protocol_versions": list(supported_protocol_versions), "requested_capabilities": list(requested_capabilities), "client_process_creation_identity_sha256": client_process_creation_identity_sha256}, b"")


def build_hello_ack(*, echo_client_nonce: str, server_process_creation_identity_sha256: str, negotiated_capabilities: Sequence[str], retention: Mapping[str, int] = {"outbox_age_ticks": 1, "reconnect_ticks": 1, "retry_ticks": 1}) -> dict[str, Any]:
    return _validate_extension("hello_ack", {"echo_client_nonce": echo_client_nonce, "server_process_creation_identity_sha256": server_process_creation_identity_sha256, "negotiated_protocol_version": "1", "negotiated_capabilities": list(negotiated_capabilities), "retention": dict(retention)}, b"")


def build_observe_request(*, logical_tick: int, watermark: Mapping[str, Any], requested_modalities: Sequence[str]) -> dict[str, Any]:
    return _validate_extension("observe_request", {"logical_tick": logical_tick, "watermark": watermark, "requested_modalities": list(requested_modalities)}, b"")


def build_observation(*, observation: QiWorldObservation, raw: bytes | None = None) -> tuple[dict[str, Any], bytes]:
    if not isinstance(observation, QiWorldObservation): raise WireError("observation type mismatch")
    raw = observation.data if raw is None else bytes(raw)
    return _validate_extension("observation", observation.extension(), raw), raw


def build_observation_complete(*, logical_tick: int, watermark: Mapping[str, Any], observation_count: int, observation_set_sha256: str) -> dict[str, Any]:
    return _validate_extension("observation_complete", {"logical_tick": logical_tick, "watermark": watermark, "observation_count": observation_count, "observation_set_sha256": observation_set_sha256}, b"")


def build_describe_actions(*, logical_tick: int) -> dict[str, Any]:
    return _validate_extension("describe_actions", {"logical_tick": logical_tick}, b"")


def build_action_descriptors(*, logical_tick: int, descriptors: Sequence[QiActionDescriptor]) -> dict[str, Any]:
    raw = [item.payload() if isinstance(item, QiActionDescriptor) else dict(item) for item in descriptors]
    return _validate_extension("action_descriptors", {"logical_tick": logical_tick, "descriptors": raw, "descriptor_set_sha256": canonical_hash(raw, "cassi.qi-world-action-descriptor-set.v1")}, b"")


def build_advance_tick(*, intent: QiWorldTickIntent | Mapping[str, Any]) -> dict[str, Any]:
    item = intent.payload() if isinstance(intent, QiWorldTickIntent) else dict(intent)
    return _validate_extension("advance_tick", {"tick_intent": item}, b"")


def build_resolve_tick(*, intent: QiWorldTickIntent | Mapping[str, Any]) -> dict[str, Any]:
    item = intent.payload() if isinstance(intent, QiWorldTickIntent) else dict(intent)
    return _validate_extension("resolve_tick", {"tick_intent": item}, b"")


def build_tick_complete(*, tick_ack: QiWorldTickAck | Mapping[str, Any], delivery: str = "original") -> dict[str, Any]:
    item = tick_ack.payload() if isinstance(tick_ack, QiWorldTickAck) else dict(tick_ack)
    ack = QiWorldTickAck.from_payload(item)
    return _validate_extension("tick_complete", {"delivery": delivery, "tick_ack": ack.payload(), "original_result_digest": ack.terminal_result["original_result_digest"]}, b"")


def build_heartbeat(*, liveness_nonce: str, last_received_message_sequence: int) -> dict[str, Any]:
    return _validate_extension("heartbeat", {"liveness_nonce": liveness_nonce, "last_received_message_sequence": last_received_message_sequence}, b"")


def build_close(*, close_reason: str = "normal", last_received_message_sequence: int = 0) -> dict[str, Any]:
    return _validate_extension("close", {"close_reason": close_reason, "last_received_message_sequence": last_received_message_sequence}, b"")


# ---------------------------------------------------------------------------
# Authenticated wire framing and in-memory transport server


def _auth_preimage(header_bytes: bytes, raw: bytes) -> bytes:
    domain = AUTH_DOMAIN.encode("utf-8")
    return len(domain).to_bytes(8, "big") + domain + struct.pack(">II", len(header_bytes), len(raw)) + header_bytes + raw


def _auth_nonce(value: bytes | str | None, seed: str) -> str:
    if value is None:
        value = hashlib.sha256(seed.encode("utf-8")).digest()[:16]
    if isinstance(value, bytes):
        if len(value) != 16: raise WireError("auth nonce must be 128 bits")
        return value.hex() + "0" * 32
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) or value[32:] != "0" * 32:
        raise WireError("auth nonce must be 32 hex digits followed by 32 zero digits")
    return value


def build_wire_frame(*, kind: str, payload: Mapping[str, Any] | bytes, key: bytes, extension: Mapping[str, Any] | None = None, auth_key_id: str = "world-key.0", run_id: str = "run.w1", episode_id: str = "episode.0", world_id: str = "world.ref", session_id: str = "session.0", connection_sequence: int = 0, message_sequence: int = 0, request_id: str | None = None, response_to: str | None = None, profile_sha256: str = ZERO_SHA256, boundary_registry_sha256: str = ZERO_SHA256, clock_sha256: str = ZERO_SHA256, protocol_version: str = "1", auth_nonce: bytes | str | None = None) -> bytes:
    if kind not in WIRE_KINDS: raise WireError("unknown world wire kind")
    if kind in _REQUEST_KINDS and request_id is None or kind in _RESPONSE_KINDS and response_to is None: raise WireError("correlation field missing for direction")
    if kind in _REQUEST_KINDS and response_to is not None or kind in _RESPONSE_KINDS and request_id is not None: raise WireError("correlation field present for wrong direction")
    if not isinstance(key, (bytes, bytearray)) or len(key) != 32: raise WireError("authentication key must be 32 bytes")
    if isinstance(payload, (bytes, bytearray, memoryview)):
        raw = bytes(payload)
        extension = {} if extension is None else dict(extension)
    else:
        if extension is not None: raise WireError("extension is only valid with raw payload")
        raw = b""
        extension = dict(payload)
    extension = _validate_extension(kind, extension, raw)
    header = {"schema": WORLD_FRAME_SCHEMA, "protocol_version": protocol_version, "kind": kind, "run_id": _id(run_id, "run_id"), "episode_id": _id(episode_id, "episode_id"), "world_id": _id(world_id, "world_id"), "session_id": _id(session_id, "session_id"), "connection_sequence": _u64(connection_sequence, "connection_sequence"), "message_sequence": _u64(message_sequence, "message_sequence"), "profile_sha256": _sha(profile_sha256, "profile_sha256"), "boundary_registry_sha256": _sha(boundary_registry_sha256, "boundary_registry_sha256"), "clock_sha256": _sha(clock_sha256, "clock_sha256"), "payload_bytes": len(raw), "payload_sha256": _sha256_bytes(raw), "auth_key_id": _id(auth_key_id, "auth_key_id"), "auth_nonce": _auth_nonce(auth_nonce, f"{run_id}:{episode_id}:{world_id}:{session_id}:{connection_sequence}"), "auth_sha256": ZERO_SHA256}
    if kind in _REQUEST_KINDS: header["request_id"] = _id(request_id, "request_id")
    else: header["response_to"] = _id(response_to, "response_to")
    header.update(extension)
    # The authenticated preimage contains the transmitted header with only
    # auth_sha256 zeroed.  Build and verify that exact canonical byte string.
    header["auth_sha256"] = ZERO_SHA256
    header_bytes = canonical_json_bytes(header)
    if len(header_bytes) > _KIND_LIMITS[kind][0] or len(header_bytes) > MAX_CANONICAL_HEADER_BYTES:
        raise WireError("header exceeds kind/profile bound")
    auth = hmac.new(bytes(key), _auth_preimage(header_bytes, raw), hashlib.sha256).hexdigest()
    header["auth_sha256"] = auth
    header_bytes = canonical_json_bytes(header)
    if len(header_bytes) > _KIND_LIMITS[kind][0] or len(header_bytes) > MAX_CANONICAL_HEADER_BYTES:
        raise WireError("authenticated header exceeds kind/profile bound")
    frame = struct.pack(">II", len(header_bytes), len(raw)) + header_bytes + raw
    if len(frame) > MAX_OUTER_FRAME_BYTES:
        raise WireError("outer frame exceeds bound")
    return frame


def parse_wire_frame(frame: bytes, *, key: bytes, expected_key_id: str | None = None, expected_connection_sequence: int | None = None, expected_message_sequence: int | None = None) -> tuple[dict[str, Any], bytes]:
    if not isinstance(frame, (bytes, bytearray, memoryview)) or len(frame) < 8: raise WireError("truncated frame")
    frame = bytes(frame)
    header_len, raw_len = struct.unpack(">II", frame[:8])
    if header_len > MAX_CANONICAL_HEADER_BYTES or raw_len > MAX_RAW_PAYLOAD_BYTES or header_len + raw_len + 8 > MAX_OUTER_FRAME_BYTES or len(frame) != header_len + raw_len + 8: raise WireError("invalid frame lengths")
    header_bytes, raw = frame[8:8 + header_len], frame[8 + header_len:]
    try: header = canonical_json_loads(header_bytes)
    except Exception as exc: raise WireError("header is not canonical JSON") from exc
    if not isinstance(header, Mapping): raise WireError("header must be an object")
    kind = header.get("kind")
    if kind not in WIRE_KINDS: raise WireError("unknown kind")
    required = {"schema", "protocol_version", "kind", "run_id", "episode_id", "world_id", "session_id", "connection_sequence", "message_sequence", "profile_sha256", "boundary_registry_sha256", "clock_sha256", "payload_bytes", "payload_sha256", "auth_key_id", "auth_nonce", "auth_sha256"}
    required.add("request_id" if kind in _REQUEST_KINDS else "response_to")
    if set(header) - (required | _KIND_EXTENSION_KEYS[kind]) or set(header) != required | _KIND_EXTENSION_KEYS[kind]: raise WireError("header fields mismatch")
    if header["schema"] != WORLD_FRAME_SCHEMA or header["protocol_version"] != "1": raise WireError("header identity mismatch")
    if header["payload_bytes"] != raw_len or header["payload_sha256"] != _sha256_bytes(raw): raise WireError("payload digest mismatch")
    if expected_key_id is not None and header["auth_key_id"] != expected_key_id: raise WireError("authentication key identity mismatch")
    if expected_connection_sequence is not None and header["connection_sequence"] != expected_connection_sequence: raise WireError("connection sequence mismatch")
    if expected_message_sequence is not None and header["message_sequence"] != expected_message_sequence: raise WireError("message sequence mismatch")
    _id(header["run_id"], "run_id"); _id(header["episode_id"], "episode_id"); _id(header["world_id"], "world_id"); _id(header["session_id"], "session_id"); _id(header["auth_key_id"], "auth_key_id")
    _u64(header["connection_sequence"], "connection_sequence"); _u64(header["message_sequence"], "message_sequence"); _sha(header["profile_sha256"], "profile_sha256"); _sha(header["boundary_registry_sha256"], "boundary_registry_sha256"); _sha(header["clock_sha256"], "clock_sha256"); _auth_nonce(header["auth_nonce"], "parse")
    if kind in _REQUEST_KINDS: _id(header["request_id"], "request_id")
    else: _id(header["response_to"], "response_to")
    zero = dict(header); zero["auth_sha256"] = ZERO_SHA256
    zero_bytes = canonical_json_bytes(zero)
    expected = hmac.new(bytes(key), _auth_preimage(zero_bytes, raw), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, header["auth_sha256"]): raise WireError("authentication failed")
    _validate_extension(kind, {key: header[key] for key in _KIND_EXTENSION_KEYS[kind]}, raw)
    return dict(header), raw


def decode_wire_frame(frame: bytes, *, key: bytes, expected_key_id: str | None = None) -> tuple[dict[str, Any], Any]:
    header, raw = parse_wire_frame(frame, key=key, expected_key_id=expected_key_id)
    extension = {key: header[key] for key in _KIND_EXTENSION_KEYS[header["kind"]]}
    if header["kind"] == "observation": return header, (extension, raw)
    return header, extension


encode_wire_frame = build_wire_frame
verify_wire_frame = parse_wire_frame


class QiWorldTransportServer:
    """In-memory authenticated server; socket lifecycle is deliberately external."""

    def __init__(self, world: DeterministicQiWorld, *, key: bytes, auth_key_id: str = "world-key.0", run_id: str = "run.w1", queue_limit: int = MAX_QUEUE_DEPTH) -> None:
        if not isinstance(key, (bytes, bytearray)) or len(key) != 32: raise WireError("authentication key must be 32 bytes")
        if not 1 <= queue_limit <= MAX_QUEUE_DEPTH: raise WireError("queue limit outside bound")
        self.world, self.key, self.auth_key_id, self.run_id, self.queue_limit = world, bytes(key), _id(auth_key_id, "auth_key_id"), _id(run_id, "run_id"), queue_limit
        self._connections: dict[tuple[str, int], dict[str, Any]] = {}
        self._used_connection_sequences: set[int] = set()

    def connect(self, *, session_id: str | None = None, connection_sequence: int = 0) -> str:
        sid = self.world.session_id if session_id is None else _id(session_id, "session_id")
        _u64(connection_sequence, "connection_sequence")
        if connection_sequence in self._used_connection_sequences: raise WireError("connection sequence reused")
        self._used_connection_sequences.add(connection_sequence)
        self._connections[(sid, connection_sequence)] = {"next_in": 0, "next_out": 0, "nonce": None, "hello": False, "closed": False, "queue": [], "requests": set()}
        return sid
    def _connection(self, header: Mapping[str, Any]) -> dict[str, Any]:
        key = (header["session_id"], header["connection_sequence"])
        if key not in self._connections:
            self.connect(session_id=key[0], connection_sequence=key[1])
        return self._connections[key]


    def _reply(self, request_header: Mapping[str, Any], kind: str, extension: Mapping[str, Any], state: dict[str, Any], raw: bytes = b"") -> bytes:
        if len(state["queue"]) >= self.queue_limit: raise WireError("world wire backpressure limit reached")
        frame = build_wire_frame(kind=kind, payload=raw if raw else extension, extension=extension if raw else None, key=self.key, auth_key_id=self.auth_key_id, run_id=self.run_id, episode_id=self.world.episode_id, world_id=self.world.world_id, session_id=request_header["session_id"], connection_sequence=request_header["connection_sequence"], message_sequence=state["next_out"], response_to=request_header.get("request_id"), profile_sha256=self.world.profile_sha256, boundary_registry_sha256=self.world.boundary_registry_sha256, clock_sha256=self.world.clock_sha256, auth_nonce=request_header["auth_nonce"])
        state["next_out"] += 1
        state["queue"].append(frame)
        return frame
 

    def receive(self, frame: bytes) -> tuple[bytes, ...]:
        header, _ = parse_wire_frame(frame, key=self.key, expected_key_id=self.auth_key_id)
        state = self._connection(header)
        nonce = header["auth_nonce"]
        if state["nonce"] is None: state["nonce"] = nonce
        elif state["nonce"] != nonce: raise WireError("nonce changed during connection")
        if header["message_sequence"] != state["next_in"]: raise WireError("message sequence is not contiguous")
        state["next_in"] += 1
        kind = header["kind"]
        extension = {key: header[key] for key in _KIND_EXTENSION_KEYS[kind]}
        if kind in _REQUEST_KINDS and kind != "hello" and not state["hello"]: raise WireError("hello required before request")
        if kind == "hello":
            if state["hello"]: raise WireError("duplicate hello")
            if extension["requested_capabilities"] != sorted(extension["requested_capabilities"]): raise WireError("capabilities not canonical")
            state["hello"] = True
            ack = build_hello_ack(echo_client_nonce=extension["client_nonce"], server_process_creation_identity_sha256=canonical_hash({"run_id": self.run_id, "world_id": self.world.world_id}, "cassi.qi-world-process.v1"), negotiated_capabilities=extension["requested_capabilities"])
            response = self._reply(header, "hello_ack", ack, state)
        elif kind == "observe_request":
            observations = self.world.observe(extension["logical_tick"], extension["watermark"], extension["requested_modalities"])
            raw_frames = [self._reply(header, "observation", obs.extension(), state, obs.data) for obs in observations]
            complete = build_observation_complete(logical_tick=extension["logical_tick"], watermark=extension["watermark"], observation_count=len(observations), observation_set_sha256=canonical_hash([obs.extension() | {"payload_sha256": obs.data_sha256} for obs in observations], "cassi.qi-world-observation-set.v1"))
            raw_frames.append(self._reply(header, "observation_complete", complete, state))
            response = tuple(raw_frames)
        elif kind == "describe_actions":
            response = self._reply(header, "action_descriptors", build_action_descriptors(logical_tick=extension["logical_tick"], descriptors=self.world.describe_actions(extension["logical_tick"])), state)
        elif kind in {"advance_tick", "resolve_tick"}:
            intent = QiWorldTickIntent.from_payload(extension["tick_intent"])
            ack = self.world.advance_tick(intent) if kind == "advance_tick" else self.world.resolve_tick(intent)
            response = self._reply(header, "tick_complete", build_tick_complete(tick_ack=ack), state)
        elif kind == "heartbeat":
            response = self._reply(header, "heartbeat_ack", {"echo_liveness_nonce": extension["liveness_nonce"], "last_received_message_sequence": header["message_sequence"]}, state)
        elif kind == "close":
            response = self._reply(header, "close_ack", {"close_reason": extension["close_reason"], "last_received_message_sequence": header["message_sequence"]}, state)
            state["closed"] = True
        else:
            raise WireError("unsupported client request")
        # Delivery is explicit: receive returns frames and clears their retained
        # queue; drain() exposes queued frames when a caller applies backpressure.
        if isinstance(response, tuple):
            delivered = response
        else:
            delivered = (response,)
        for item in delivered:
            if item in state["queue"]: state["queue"].remove(item)
        return delivered

    handle_frame = receive
    process = receive

    def drain(self, *, session_id: str | None = None, connection_sequence: int = 0) -> tuple[bytes, ...]:
        state = self._connections.get((session_id or self.world.session_id, connection_sequence))
        if state is None: return ()
        queue = tuple(state["queue"])
        state["queue"].clear()
        return queue


# Extension field sets are intentionally closed and shared by builders/parsers.
_KIND_EXTENSION_KEYS = {
    "hello": frozenset({"client_nonce", "supported_protocol_versions", "requested_capabilities", "client_process_creation_identity_sha256"}),
    "hello_ack": frozenset({"echo_client_nonce", "server_process_creation_identity_sha256", "negotiated_protocol_version", "negotiated_capabilities", "retention"}),
    "observe_request": frozenset({"logical_tick", "watermark", "requested_modalities"}),
    "observation": frozenset({"logical_tick", "capture_interval", "source_epoch", "source_stream_id", "source_sequence", "watermark", "body_frame_id", "modality", "descriptor_sha256", "payload_dtype", "payload_shape", "physical_unit"}),
    "observation_complete": frozenset({"logical_tick", "watermark", "observation_count", "observation_set_sha256"}),
    "describe_actions": frozenset({"logical_tick"}),
    "action_descriptors": frozenset({"logical_tick", "descriptors", "descriptor_set_sha256"}),
    "advance_tick": frozenset({"tick_intent"}),
    "resolve_tick": frozenset({"tick_intent"}),
    "tick_complete": frozenset({"delivery", "tick_ack", "original_result_digest"}),
    "heartbeat": frozenset({"liveness_nonce", "last_received_message_sequence"}),
    "heartbeat_ack": frozenset({"echo_liveness_nonce", "last_received_message_sequence"}),
    "close": frozenset({"close_reason", "last_received_message_sequence"}),
    "close_ack": frozenset({"close_reason", "last_received_message_sequence"}),
    "error": frozenset({"failed_kind", "error_code", "retryable", "error_detail_sha256"}),
}


WORLD_WIRE_REGISTRY: dict[str, Any] = {
    "schema": WORLD_WIRE_SCHEMA,
    "contract_root_sha256": ZERO_SHA256,
    "profile_sha256": ZERO_SHA256,
    "semantic_parents": [{"name": "world_protocol", "sha256": canonical_hash({"projection": "world_protocol"}, "cassi.qi-world-parent.world_protocol")}, {"name": "security_evidence", "sha256": canonical_hash({"projection": "security_evidence"}, "cassi.qi-world-parent.security_evidence")}],
    "protocol_version": "1",
    "frame_schema": WORLD_FRAME_SCHEMA,
    "canonical_json_schema": CANONICAL_SCHEMA,
    "auth_domain": AUTH_DOMAIN,
    "outer_framing": "uint32be-header,uint32be-payload,header,payload",
    "limits": {"max_header_bytes": MAX_CANONICAL_HEADER_BYTES, "max_raw_payload_bytes": MAX_RAW_PAYLOAD_BYTES, "max_outer_frame_bytes": MAX_OUTER_FRAME_BYTES},
    "kind_registry": [{"kind": kind, "schema": _KIND_SCHEMA[kind], "direction": "client_to_server" if kind in _REQUEST_KINDS else "server_to_client", "response_to_kind": None if kind in {"error"} else ({"hello_ack": "hello", "observation": "observe_request", "observation_complete": "observe_request", "action_descriptors": "describe_actions", "tick_complete": "advance_tick|resolve_tick", "heartbeat_ack": "heartbeat", "close_ack": "close"}.get(kind)), "terminal_response": kind in {"observation_complete", "tick_complete", "close_ack", "error"}, "max_header_bytes": _KIND_LIMITS[kind][0], "max_raw_payload_bytes": _KIND_LIMITS[kind][1]} for kind in WIRE_KINDS],
    "wire_registry_sha256": "",
}
WORLD_WIRE_REGISTRY["wire_registry_sha256"] = canonical_hash(WORLD_WIRE_REGISTRY, WORLD_WIRE_SCHEMA)
WORLD_WIRE_REGISTRY_SHA256 = WORLD_WIRE_REGISTRY["wire_registry_sha256"]


def build_wire_registry() -> dict[str, Any]:
    return dict(WORLD_WIRE_REGISTRY)


def parse_wire_registry(value: Mapping[str, Any]) -> dict[str, Any]:
    if dict(value) != WORLD_WIRE_REGISTRY:
        raise WireError("wire registry mismatch")
    return dict(value)


__all__ = [name for name in globals() if name.startswith("Qi") or name.startswith("WORLD_") or name.startswith("build_") or name.startswith("parse_") or name.endswith("_SCHEMA") or name in {"AUTH_DOMAIN", "CANONICAL_SCHEMA", "MAX_CANONICAL_HEADER_BYTES", "MAX_RAW_PAYLOAD_BYTES", "MAX_OUTER_FRAME_BYTES", "encode_wire_frame", "decode_wire_frame", "verify_wire_frame", "WireError", "WorldStateError"}]
