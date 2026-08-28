"""Explicit exact-byte new-session lineage forks for CassiFI."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

from cassi_qi_bootstrap import canonical_hash
from cassi_qi_field import load_v3_state_bytes
from cassi_qi_profile import PROJECTION_REGISTRY, QiFlowProfile


LINEAGE_RECEIPT_SCHEMA = "cassi.qi-flow-state-lineage-fork-receipt.v1"


class QiStateLineageError(ValueError):
    """Raised before a child exists when a state fork is unsafe."""


def _text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise QiStateLineageError(f"{name} must be a nonempty string")
    return value


def _digest(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _state_consuming_vector(profile: QiFlowProfile) -> tuple[tuple[str, str], ...]:
    if not isinstance(profile, QiFlowProfile):
        raise QiStateLineageError("lineage profiles must be validated QiFlowProfile objects")
    declared = profile.payload.get("semantic_subhashes")
    if not isinstance(declared, list):
        raise QiStateLineageError("profile semantic-subhash vector is missing")
    rows: dict[str, tuple[str, bool]] = {}
    for row in declared:
        if not isinstance(row, Mapping) or set(row) != {"name", "sha256", "state_consuming"}:
            raise QiStateLineageError("profile semantic-subhash row is malformed")
        name = row["name"]
        if not isinstance(name, str) or name in rows:
            raise QiStateLineageError("profile semantic-subhash names are invalid or duplicated")
        rows[name] = (str(row["sha256"]), bool(row["state_consuming"]))
    expected = tuple(
        (str(row["name"]), bool(row["state_consuming"]))
        for row in PROJECTION_REGISTRY["projections"]
    )
    if tuple((name, rows.get(name, ("", False))[1]) for name, _ in expected) != expected or set(rows) != {name for name, _ in expected}:
        raise QiStateLineageError("profile projection registry is missing, added, or reclassified")
    return tuple((name, rows[name][0]) for name, state_consuming in expected if state_consuming)


def _raw_profile(profile: QiFlowProfile) -> Mapping[str, Any]:
    return {
        key: value
        for key, value in profile.payload.items()
        if key not in {"schema", "contract_root_sha256", "semantic_subhashes", "profile_sha256"}
    }


def _leaves(value: Any, path: str = "") -> dict[str, Any]:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value):
            result.update(_leaves(value[key], f"{path}/{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(_leaves(item, f"{path}/{index}"))
        return result
    return {path or "/": value}


def _profile_differences(parent: QiFlowProfile, child: QiFlowProfile) -> tuple[dict[str, Any], ...]:
    old = _leaves(_raw_profile(parent))
    new = _leaves(_raw_profile(child))
    rows = []
    for pointer in sorted(set(old) | set(new)):
        if old.get(pointer) != new.get(pointer):
            rows.append({"json_pointer": pointer, "old": old.get(pointer), "new": new.get(pointer)})
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class QiParentSessionSnapshot:
    session_id: str
    head_sha256: str
    profile: QiFlowProfile
    state_object_bytes: bytes
    protocol_epoch: str
    world_id: str
    episode_id: str
    source_identity_sha256: str
    clock_sha256: str
    pending_outbox_sha256: str | None = None
    pending_applied_efference_sha256: str | None = None
    lineage_status: str = "committed"

    def __post_init__(self) -> None:
        for name in (
            "session_id",
            "head_sha256",
            "protocol_epoch",
            "world_id",
            "episode_id",
            "source_identity_sha256",
            "clock_sha256",
        ):
            _text(getattr(self, name), name)
        if not isinstance(self.profile, QiFlowProfile):
            raise QiStateLineageError("parent profile is invalid")
        if not isinstance(self.state_object_bytes, bytes) or not self.state_object_bytes:
            raise QiStateLineageError("parent state object must be nonempty immutable bytes")
        if self.lineage_status not in {"committed", "indeterminate_sealed"}:
            raise QiStateLineageError("parent lineage status is invalid")


@dataclass(frozen=True, slots=True)
class QiStateLineageForkReceipt:
    parent_session_id: str
    new_session_id: str
    parent_head_sha256: str
    parent_profile_sha256: str
    new_profile_sha256: str
    state_consuming_subhashes: tuple[dict[str, str], ...]
    differing_profile_leaves: tuple[dict[str, Any], ...]
    parent_state_object_sha256: str
    child_state_object_sha256: str
    parent_state_byte_count: int
    child_state_byte_count: int
    parent_source_identity_sha256: str
    new_source_identity_sha256: str
    parent_clock_sha256: str
    new_clock_sha256: str
    new_protocol_epoch: str
    new_world_id: str
    new_episode_id: str
    reset_reason: str
    operator_identity_sha256: str

    def payload(self) -> dict[str, Any]:
        core = {
            "schema": LINEAGE_RECEIPT_SCHEMA,
            "parent_session_id": self.parent_session_id,
            "new_session_id": self.new_session_id,
            "parent_head_sha256": self.parent_head_sha256,
            "parent_profile_sha256": self.parent_profile_sha256,
            "new_profile_sha256": self.new_profile_sha256,
            "state_consuming_subhashes": list(self.state_consuming_subhashes),
            "differing_profile_leaves": list(self.differing_profile_leaves),
            "parent_state_object_sha256": self.parent_state_object_sha256,
            "child_state_object_sha256": self.child_state_object_sha256,
            "parent_state_byte_count": self.parent_state_byte_count,
            "child_state_byte_count": self.child_state_byte_count,
            "parent_source_identity_sha256": self.parent_source_identity_sha256,
            "new_source_identity_sha256": self.new_source_identity_sha256,
            "parent_clock_sha256": self.parent_clock_sha256,
            "new_clock_sha256": self.new_clock_sha256,
            "new_protocol_epoch": self.new_protocol_epoch,
            "new_world_id": self.new_world_id,
            "new_episode_id": self.new_episode_id,
            "logical_tick": 0,
            "cycle_number": 0,
            "reset_reason": self.reset_reason,
            "operator_identity_sha256": self.operator_identity_sha256,
            "exact_state_object_copy": True,
            "copied_protocol_or_world_continuity": False,
        }
        return {**core, "self_sha256": canonical_hash(core, LINEAGE_RECEIPT_SCHEMA)}


@dataclass(frozen=True, slots=True)
class QiStateLineageFork:
    state_object_bytes: bytes
    receipt: QiStateLineageForkReceipt


def fork_state_lineage(
    parent: QiParentSessionSnapshot,
    *,
    new_profile: QiFlowProfile,
    new_session_id: str,
    reason: str,
    new_protocol_epoch: str,
    new_world_id: str,
    new_episode_id: str,
    new_source_identity_sha256: str,
    new_clock_sha256: str,
) -> QiStateLineageFork:
    """Copy one canonical state object exactly into a fresh compatible session."""

    if not isinstance(parent, QiParentSessionSnapshot):
        raise QiStateLineageError("fork requires an immutable parent snapshot")
    if parent.lineage_status == "indeterminate_sealed":
        raise QiStateLineageError("an indeterminate-sealed parent cannot provide continuity")
    if parent.pending_outbox_sha256 is not None or parent.pending_applied_efference_sha256 is not None:
        raise QiStateLineageError("parent has pending world continuity that cannot be copied")
    if not isinstance(new_profile, QiFlowProfile):
        raise QiStateLineageError("new profile must be validated before the fork")
    child_session = _text(new_session_id, "new_session_id")
    if child_session == parent.session_id:
        raise QiStateLineageError("state lineage fork requires a new session identity")
    reset_reason = _text(reason, "reason")
    fresh = {
        "protocol_epoch": _text(new_protocol_epoch, "new_protocol_epoch"),
        "world_id": _text(new_world_id, "new_world_id"),
        "episode_id": _text(new_episode_id, "new_episode_id"),
        "source_identity_sha256": _text(new_source_identity_sha256, "new_source_identity_sha256"),
        "clock_sha256": _text(new_clock_sha256, "new_clock_sha256"),
    }
    old = {
        "protocol_epoch": parent.protocol_epoch,
        "world_id": parent.world_id,
        "episode_id": parent.episode_id,
        "source_identity_sha256": parent.source_identity_sha256,
        "clock_sha256": parent.clock_sha256,
    }
    reused = sorted(name for name in fresh if fresh[name] == old[name])
    if reused:
        raise QiStateLineageError("fresh child identities reused parent continuity: " + ", ".join(reused))

    parent_vector = _state_consuming_vector(parent.profile)
    child_vector = _state_consuming_vector(new_profile)
    if tuple(name for name, _ in parent_vector) != tuple(name for name, _ in child_vector):
        raise QiStateLineageError("state-consuming projection registry changed")
    mismatches = [name for (name, old_hash), (_, new_hash) in zip(parent_vector, child_vector) if old_hash != new_hash]
    if mismatches:
        raise QiStateLineageError("state-consuming profile difference: " + ", ".join(mismatches))
    if dict(parent.profile.state_layout) != dict(new_profile.state_layout):
        raise QiStateLineageError("state layout would reinterpret canonical bytes")

    try:
        restored = load_v3_state_bytes(parent.state_object_bytes, parent.profile)
        restored.validate(parent.profile)
    except Exception as exc:
        raise QiStateLineageError(f"parent state object is invalid: {type(exc).__name__}: {exc}") from exc
    source_bytes = parent.state_object_bytes
    copied_bytes = bytes(memoryview(source_bytes))
    if copied_bytes != source_bytes:
        raise QiStateLineageError("canonical state-object copy changed bytes")
    source_sha = _digest(source_bytes)
    child_sha = _digest(copied_bytes)
    if source_sha != child_sha or len(source_bytes) != len(copied_bytes):
        raise QiStateLineageError("canonical state-object copy identity mismatch")

    vector_rows = tuple(
        {"name": name, "parent_sha256": digest, "new_sha256": digest}
        for name, digest in parent_vector
    )
    operator_identity = canonical_hash(
        {
            "state_consuming_subhashes": list(vector_rows),
            "state_layout": dict(parent.profile.state_layout),
            "contract_root_sha256": parent.profile.contract_root_sha256,
        },
        "cassi.qi-flow-state-lineage-operator.v1",
    )
    receipt = QiStateLineageForkReceipt(
        parent_session_id=parent.session_id,
        new_session_id=child_session,
        parent_head_sha256=parent.head_sha256,
        parent_profile_sha256=parent.profile.profile_sha256,
        new_profile_sha256=new_profile.profile_sha256,
        state_consuming_subhashes=vector_rows,
        differing_profile_leaves=_profile_differences(parent.profile, new_profile),
        parent_state_object_sha256=source_sha,
        child_state_object_sha256=child_sha,
        parent_state_byte_count=len(source_bytes),
        child_state_byte_count=len(copied_bytes),
        parent_source_identity_sha256=parent.source_identity_sha256,
        new_source_identity_sha256=fresh["source_identity_sha256"],
        parent_clock_sha256=parent.clock_sha256,
        new_clock_sha256=fresh["clock_sha256"],
        new_protocol_epoch=fresh["protocol_epoch"],
        new_world_id=fresh["world_id"],
        new_episode_id=fresh["episode_id"],
        reset_reason=reset_reason,
        operator_identity_sha256=operator_identity,
    )
    return QiStateLineageFork(copied_bytes, receipt)


__all__ = [
    "LINEAGE_RECEIPT_SCHEMA",
    "QiParentSessionSnapshot",
    "QiStateLineageError",
    "QiStateLineageFork",
    "QiStateLineageForkReceipt",
    "fork_state_lineage",
]
