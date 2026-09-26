"""Explicit exact-byte new-session lineage forks for CassiFI.

A fork is an administrative operation, not a state migration.  The only state
that crosses the boundary is an immutable byte-for-byte copy of the validated
v3 checkpoint.  Every identity used to interpret those bytes is compared
before a child session can be described.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes
from cassi_qi_field import load_v3_state_bytes
from cassi_qi_profile import PROJECTION_REGISTRY, QiFlowProfile


LINEAGE_RECEIPT_SCHEMA = "cassi.qi-flow-state-lineage-fork-receipt.v1"
LINEAGE_PROOF_SCHEMA = "cassi.qi-flow-state-lineage-compatibility-proof.v1"
LINEAGE_ARTIFACT_SCHEMA = "cassi.qi-flow-g12l-state-lineage.v1"
STATE_SCHEMA = "cassi.qi-flow-state.v3"
_MAX_SAFE_INTEGER = 9_007_199_254_740_991


class QiStateLineageError(ValueError):
    """Raised before a child exists when a state fork is unsafe."""


def _text(value: str, name: str, *, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise QiStateLineageError(f"{name} must be a nonempty string")
    if maximum is not None and len(value) > maximum:
        raise QiStateLineageError(f"{name} exceeds its {maximum}-character bound")
    try:
        value.encode("utf-8", "strict")
    except UnicodeEncodeError as exc:
        raise QiStateLineageError(f"{name} must be strict UTF-8") from exc
    return value


def _digest(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _identity_digest(value: str, name: str) -> str:
    """Hash an identity token without allowing an implicit encoding policy."""

    return _digest(_text(value, name).encode("utf-8", "strict"))


def _sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise QiStateLineageError(f"{name} must be a SHA-256 identity")
    try:
        int(value, 16)
    except ValueError as exc:
        raise QiStateLineageError(f"{name} must be a lowercase SHA-256 identity") from exc
    if value != value.lower():
        raise QiStateLineageError(f"{name} must be a lowercase SHA-256 identity")
    return value


def _plain(value: Any) -> Any:
    """Return canonical-codec-compatible plain containers from profile views."""

    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _state_consuming_vector(profile: QiFlowProfile) -> tuple[tuple[str, str], ...]:
    """Return the complete ordered registry-declared state-consuming vector."""

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
        state_consuming = row["state_consuming"]
        if type(state_consuming) is not bool:
            raise QiStateLineageError("profile state-consuming declaration is not boolean")
        digest = _sha256(row["sha256"], f"profile semantic subhash {name}")
        rows[name] = (digest, state_consuming)

    expected_rows: list[tuple[str, bool]] = []
    for row in PROJECTION_REGISTRY["projections"]:
        if not isinstance(row, Mapping):
            raise QiStateLineageError("projection registry row is malformed")
        expected_rows.append((_text(row["name"], "projection name"), bool(row["state_consuming"])))
    expected_names = {name for name, _ in expected_rows}
    if set(rows) != expected_names:
        raise QiStateLineageError("profile projection registry is missing or added")
    if tuple((name, rows[name][1]) for name, _ in expected_rows) != tuple(expected_rows):
        raise QiStateLineageError("profile projection registry is reordered or reclassified")
    return tuple((name, rows[name][0]) for name, consuming in expected_rows if consuming)


def _raw_profile(profile: QiFlowProfile) -> Mapping[str, Any]:
    return {
        key: _plain(value)
        for key, value in profile.payload.items()
        if key not in {"schema", "contract_root_sha256", "semantic_subhashes", "profile_sha256"}
    }


def _leaves(value: Any, path: str = "") -> dict[str, Any]:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: str(item).encode("utf-8")):
            result.update(_leaves(value[key], f"{path}/{key}"))
        return result
    if isinstance(value, list):
        result: dict[str, Any] = {}
        for index, item in enumerate(value):
            result.update(_leaves(item, f"{path}/{index}"))
        return result
    return {path or "/": value}


def _profile_differences(parent: QiFlowProfile, child: QiFlowProfile) -> tuple[dict[str, Any], ...]:
    old = _leaves(_raw_profile(parent))
    new = _leaves(_raw_profile(child))
    missing = object()
    rows: list[dict[str, Any]] = []
    for pointer in sorted(set(old) | set(new), key=lambda item: item.encode("utf-8")):
        previous = old.get(pointer, missing)
        current = new.get(pointer, missing)
        if previous != current:
            rows.append(
                {
                    "json_pointer": pointer,
                    "old": None if previous is missing else previous,
                    "new": None if current is missing else current,
                }
            )
    return tuple(rows)


def _profile_identity_bundle(profile: QiFlowProfile) -> dict[str, str]:
    """Derive all identities that can affect checkpoint interpretation."""

    layout = _plain(profile.state_layout)
    layout_sha = canonical_hash(layout, "cassi.qi-flow-state-layout.v3")
    operator_material = {
        "contract_root_sha256": profile.contract_root_sha256,
        "execution_schedule_sha256": profile.execution_schedule_sha256,
        "state_bounds_layout_sha256": profile.state_bounds_layout_sha256,
        "topology_sha256": profile.topology_sha256,
        "state_consuming_subhashes": [
            {"name": name, "sha256": digest}
            for name, digest in _state_consuming_vector(profile)
        ],
    }
    operator_sha = canonical_hash(operator_material, "cassi.qi-flow-state-lineage-operator.v1")
    schema_sha = canonical_hash(
        {
            "contract_root_sha256": profile.contract_root_sha256,
            "profile_schema": profile.payload["schema"],
            "state_schema": STATE_SCHEMA,
        },
        "cassi.qi-flow-state-lineage-schema.v1",
    )
    return {
        "state_contract_sha256": _sha256(profile.state_contract_sha256, "state_contract_sha256"),
        "layout_identity_sha256": layout_sha,
        "operator_identity_sha256": operator_sha,
        "schema_identity_sha256": schema_sha,
        "backend_identity_sha256": _sha256(profile.backend_sha256, "backend_sha256"),
        "source_profile_identity_sha256": _sha256(
            profile.source_identity_sha256,
            "source_profile_identity_sha256",
        ),
        "execution_schedule_sha256": _sha256(
            profile.execution_schedule_sha256,
            "execution_schedule_sha256",
        ),
        "topology_sha256": _sha256(profile.topology_sha256, "topology_sha256"),
    }


def _checkpoint_identity(
    *,
    state_sha256: str,
    byte_count: int,
    state_contract_sha256: str,
) -> str:
    return canonical_hash(
        {
            "state_contract_sha256": state_contract_sha256,
            "state_object_sha256": state_sha256,
            "state_byte_count": byte_count,
        },
        "cassi.qi-flow-state-lineage-checkpoint.v1",
    )


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
    lineage_status: str = "open"

    def __post_init__(self) -> None:
        for name in ("session_id", "protocol_epoch", "world_id", "episode_id"):
            _text(getattr(self, name), name)
        for name in ("head_sha256", "source_identity_sha256", "clock_sha256"):
            _sha256(getattr(self, name), name)
        if not isinstance(self.profile, QiFlowProfile):
            raise QiStateLineageError("parent profile is invalid")
        if type(self.state_object_bytes) is not bytes or not self.state_object_bytes:
            raise QiStateLineageError("parent state object must be nonempty immutable bytes")
        if self.lineage_status == "committed":
            # Existing callers used the pre-gate spelling; normalize it at the
            # immutable boundary rather than emitting a third status value.
            object.__setattr__(self, "lineage_status", "open")
        if self.lineage_status not in {"open", "indeterminate_sealed"}:
            raise QiStateLineageError("parent lineage status is invalid")
        for name in ("pending_outbox_sha256", "pending_applied_efference_sha256"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)


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
    parent_state_contract_sha256: str
    child_state_contract_sha256: str
    parent_source_identity_sha256: str
    new_source_identity_sha256: str
    parent_clock_sha256: str
    new_clock_sha256: str
    new_protocol_epoch: str
    new_world_id: str
    new_episode_id: str
    reset_reason: str
    operator_id: str
    creation_timestamp_ns_telemetry: int
    parent_lineage_status: str
    layout_identity_sha256: str
    operator_identity_sha256: str
    schema_identity_sha256: str
    backend_identity_sha256: str
    source_profile_identity_sha256: str
    checkpoint_identity_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "parent_session_id",
            "new_session_id",
            "parent_head_sha256",
            "parent_profile_sha256",
            "new_profile_sha256",
            "new_world_id",
            "new_episode_id",
            "operator_id",
        ):
            _text(getattr(self, name), name, maximum=256)
        for name in (
            "parent_head_sha256",
            "parent_profile_sha256",
            "new_profile_sha256",
            "parent_state_object_sha256",
            "child_state_object_sha256",
            "parent_state_contract_sha256",
            "child_state_contract_sha256",
            "parent_source_identity_sha256",
            "new_source_identity_sha256",
            "parent_clock_sha256",
            "new_clock_sha256",
            "layout_identity_sha256",
            "operator_identity_sha256",
            "schema_identity_sha256",
            "backend_identity_sha256",
            "source_profile_identity_sha256",
            "checkpoint_identity_sha256",
        ):
            _sha256(getattr(self, name), name)
        if type(self.parent_state_byte_count) is not int or self.parent_state_byte_count < 0:
            raise QiStateLineageError("parent_state_byte_count must be a nonnegative integer")
        if type(self.child_state_byte_count) is not int or self.child_state_byte_count < 0:
            raise QiStateLineageError("child_state_byte_count must be a nonnegative integer")
        if type(self.creation_timestamp_ns_telemetry) is not int or not 0 <= self.creation_timestamp_ns_telemetry <= _MAX_SAFE_INTEGER:
            raise QiStateLineageError("creation_timestamp_ns_telemetry is outside its exact integer range")
        _text(self.reset_reason, "reset_reason", maximum=512)
        if self.parent_lineage_status not in {"open", "indeterminate_sealed"}:
            raise QiStateLineageError("parent_lineage_status is invalid")
        if type(self.state_consuming_subhashes) is not tuple:
            raise QiStateLineageError("state_consuming_subhashes must be an immutable tuple")
        for row in self.state_consuming_subhashes:
            if set(row) != {"name", "parent_sha256", "child_sha256"}:
                raise QiStateLineageError("state-consuming receipt row is malformed")
            _text(row["name"], "state-consuming projection name", maximum=256)
            _sha256(row["parent_sha256"], "state-consuming parent hash")
            _sha256(row["child_sha256"], "state-consuming child hash")
        if type(self.differing_profile_leaves) is not tuple:
            raise QiStateLineageError("differing_profile_leaves must be an immutable tuple")

    def _core(self) -> dict[str, Any]:
        rows = [dict(row) for row in self.state_consuming_subhashes]
        differences = [dict(row) for row in self.differing_profile_leaves]
        proof = {
            "schema": LINEAGE_PROOF_SCHEMA,
            "state_contract_sha256": {
                "parent": self.parent_state_contract_sha256,
                "child": self.child_state_contract_sha256,
                "equal": self.parent_state_contract_sha256 == self.child_state_contract_sha256,
            },
            "state_consuming_subhashes": rows,
            "layout_identity_sha256": {"parent": self.layout_identity_sha256, "child": self.layout_identity_sha256, "equal": True},
            "operator_identity_sha256": {"parent": self.operator_identity_sha256, "child": self.operator_identity_sha256, "equal": True},
            "schema_identity_sha256": {"parent": self.schema_identity_sha256, "child": self.schema_identity_sha256, "equal": True},
            "backend_identity_sha256": {"parent": self.backend_identity_sha256, "child": self.backend_identity_sha256, "equal": True},
            "source_profile_identity_sha256": {"parent": self.source_profile_identity_sha256, "child": self.source_profile_identity_sha256, "equal": True},
            "checkpoint": {
                "parent_state_object_sha256": self.parent_state_object_sha256,
                "child_state_object_sha256": self.child_state_object_sha256,
                "parent_state_byte_count": self.parent_state_byte_count,
                "child_state_byte_count": self.child_state_byte_count,
                "exact_bytes": self.parent_state_object_sha256 == self.child_state_object_sha256 and self.parent_state_byte_count == self.child_state_byte_count,
                "checkpoint_identity_sha256": self.checkpoint_identity_sha256,
            },
            "differing_profile_leaves": differences,
            "profile_sha256_differs": self.parent_profile_sha256 != self.new_profile_sha256,
            "fresh_session_identity": self.parent_session_id != self.new_session_id,
            "fresh_source_identity": self.parent_source_identity_sha256 != self.new_source_identity_sha256,
            "fresh_clock_identity": self.parent_clock_sha256 != self.new_clock_sha256,
            "fresh_protocol_epoch": True,
            "fresh_world_identity": True,
            "fresh_episode_identity": True,
        }
        return {
            "schema": LINEAGE_RECEIPT_SCHEMA,
            "receipt_id": "",
            "parent_session_id": self.parent_session_id,
            "new_session_id": self.new_session_id,
            "parent_head_sha256": self.parent_head_sha256,
            "parent_profile_sha256": self.parent_profile_sha256,
            "new_profile_sha256": self.new_profile_sha256,
            "state_consuming_subhashes": rows,
            "differing_profile_leaves": differences,
            "parent_state_object_sha256": self.parent_state_object_sha256,
            "child_state_object_sha256": self.child_state_object_sha256,
            "parent_state_byte_count": self.parent_state_byte_count,
            "child_state_byte_count": self.child_state_byte_count,
            "parent_state_contract_sha256": self.parent_state_contract_sha256,
            "child_state_contract_sha256": self.child_state_contract_sha256,
            "old_source_identity_sha256": self.parent_source_identity_sha256,
            "new_source_identity_sha256": self.new_source_identity_sha256,
            "old_clock_sha256": self.parent_clock_sha256,
            "new_clock_sha256": self.new_clock_sha256,
            "new_protocol_epoch_sha256": _identity_digest(self.new_protocol_epoch, "new_protocol_epoch"),
            "new_world_id": self.new_world_id,
            "new_episode_id": self.new_episode_id,
            "reset_reason": self.reset_reason,
            "operator_id": self.operator_id,
            "creation_timestamp_ns_telemetry": self.creation_timestamp_ns_telemetry,
            "copied_state_exact": True,
            "continuity_reused": False,
            "parent_lineage_status": self.parent_lineage_status,
            "logical_tick": 0,
            "cycle_number": 0,
            "new_protocol_epoch": self.new_protocol_epoch,
            "operator_identity_sha256": self.operator_identity_sha256,
            "layout_identity_sha256": self.layout_identity_sha256,
            "schema_identity_sha256": self.schema_identity_sha256,
            "backend_identity_sha256": self.backend_identity_sha256,
            "source_profile_identity_sha256": self.source_profile_identity_sha256,
            "checkpoint_identity_sha256": self.checkpoint_identity_sha256,
            "exact_state_object_copy": True,
            "copied_protocol_or_world_continuity": False,
            "compatibility_proof": proof,
        }

    def payload(self) -> dict[str, Any]:
        """Return a canonical, self-addressed receipt payload."""

        core = self._core()
        material = {key: value for key, value in core.items() if key != "receipt_id"}
        core["receipt_id"] = canonical_hash(material, LINEAGE_RECEIPT_SCHEMA + ".receipt-id")
        core["self_sha256"] = canonical_hash(core, LINEAGE_RECEIPT_SCHEMA)
        return core


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
    operator_id: str | None = None,
    creation_timestamp_ns_telemetry: int = 0,
) -> QiStateLineageFork:
    """Copy one canonical state object exactly into a fresh compatible session."""

    if operator_id is None:
        raise QiStateLineageError("operator_id is required; no derived operator witness is accepted")
    operator = _text(operator_id, "operator_id", maximum=256)
    if not isinstance(creation_timestamp_ns_telemetry, int) or not 0 <= creation_timestamp_ns_telemetry <= _MAX_SAFE_INTEGER:
        raise QiStateLineageError("creation_timestamp_ns_telemetry is outside its exact integer range")

    if not isinstance(parent, QiParentSessionSnapshot):
        raise QiStateLineageError("fork requires an immutable parent snapshot")
    if parent.lineage_status == "indeterminate_sealed":
        raise QiStateLineageError("an indeterminate-sealed parent cannot provide continuity")
    if parent.pending_outbox_sha256 is not None or parent.pending_applied_efference_sha256 is not None:
        raise QiStateLineageError("parent has pending world continuity that cannot be copied")
    if not isinstance(new_profile, QiFlowProfile):
        raise QiStateLineageError("new profile must be validated before the fork")

    child_session = _text(new_session_id, "new_session_id", maximum=256)
    if child_session == parent.session_id:
        raise QiStateLineageError("state lineage fork requires a new session identity")
    reset_reason = _text(reason, "reason", maximum=512)
    fresh = {
        "protocol_epoch": _text(new_protocol_epoch, "new_protocol_epoch", maximum=256),
        "world_id": _text(new_world_id, "new_world_id", maximum=256),
        "episode_id": _text(new_episode_id, "new_episode_id", maximum=256),
        "source_identity_sha256": _text(new_source_identity_sha256, "new_source_identity_sha256", maximum=256),
        "clock_sha256": _text(new_clock_sha256, "new_clock_sha256", maximum=256),
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
    mismatches = [
        name
        for (name, parent_hash), (_, child_hash) in zip(parent_vector, child_vector)
        if parent_hash != child_hash
    ]
    if mismatches:
        raise QiStateLineageError("state-consuming profile difference: " + ", ".join(mismatches))

    parent_ids = _profile_identity_bundle(parent.profile)
    child_ids = _profile_identity_bundle(new_profile)
    for identity_name in (
        "state_contract_sha256",
        "layout_identity_sha256",
        "operator_identity_sha256",
        "schema_identity_sha256",
        "backend_identity_sha256",
        "source_profile_identity_sha256",
    ):
        if parent_ids[identity_name] != child_ids[identity_name]:
            raise QiStateLineageError(f"{identity_name} would reinterpret canonical bytes")
    if new_profile.profile_sha256 == parent.profile.profile_sha256:
        raise QiStateLineageError("state lineage fork requires a distinct complete profile identity")

    differences = _profile_differences(parent.profile, new_profile)
    if not differences:
        raise QiStateLineageError("state lineage fork requires an explicit profile difference")

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

    # The checkpoint header deliberately remains parent-authenticated.  Loading
    # it as a child would be an implicit profile rewrite; identity comparisons
    # above prove that the child has the same byte interpretation instead.
    vector_rows = tuple(
        {"name": name, "parent_sha256": digest, "child_sha256": digest}
        for name, digest in parent_vector
    )
    checkpoint_sha = _checkpoint_identity(
        state_sha256=source_sha,
        byte_count=len(source_bytes),
        state_contract_sha256=parent_ids["state_contract_sha256"],
    )
    receipt = QiStateLineageForkReceipt(
        parent_session_id=parent.session_id,
        new_session_id=child_session,
        parent_head_sha256=parent.head_sha256,
        parent_profile_sha256=parent.profile.profile_sha256,
        new_profile_sha256=new_profile.profile_sha256,
        state_consuming_subhashes=vector_rows,
        differing_profile_leaves=differences,
        parent_state_object_sha256=source_sha,
        child_state_object_sha256=child_sha,
        parent_state_byte_count=len(source_bytes),
        child_state_byte_count=len(copied_bytes),
        parent_state_contract_sha256=parent_ids["state_contract_sha256"],
        child_state_contract_sha256=child_ids["state_contract_sha256"],
        parent_source_identity_sha256=parent.source_identity_sha256,
        new_source_identity_sha256=fresh["source_identity_sha256"],
        parent_clock_sha256=parent.clock_sha256,
        new_clock_sha256=fresh["clock_sha256"],
        new_protocol_epoch=fresh["protocol_epoch"],
        new_world_id=fresh["world_id"],
        new_episode_id=fresh["episode_id"],
        reset_reason=reset_reason,
        operator_id=operator,
        creation_timestamp_ns_telemetry=creation_timestamp_ns_telemetry,
        parent_lineage_status=parent.lineage_status,
        layout_identity_sha256=parent_ids["layout_identity_sha256"],
        operator_identity_sha256=parent_ids["operator_identity_sha256"],
        schema_identity_sha256=parent_ids["schema_identity_sha256"],
        backend_identity_sha256=parent_ids["backend_identity_sha256"],
        source_profile_identity_sha256=parent_ids["source_profile_identity_sha256"],
        checkpoint_identity_sha256=checkpoint_sha,
    )
    return QiStateLineageFork(copied_bytes, receipt)


__all__ = [
    "LINEAGE_ARTIFACT_SCHEMA",
    "LINEAGE_PROOF_SCHEMA",
    "LINEAGE_RECEIPT_SCHEMA",
    "QiParentSessionSnapshot",
    "QiStateLineageError",
    "QiStateLineageFork",
    "QiStateLineageForkReceipt",
    "fork_state_lineage",
]
