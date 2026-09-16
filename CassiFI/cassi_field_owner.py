from __future__ import annotations

"""One persistent cognitive owner and thin surfaces for the field atlas."""

import base64
import hashlib
import json
import os
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, NoReturn, Protocol, Sequence

from cassi_field_atlas import (
    ATLAS_SCHEMA,
    PACKET_IMPULSE_EVENT_KIND,
    AffineConstraint,
    AtlasState,
    FieldAtlas,
    FieldIntelligenceError,
    FieldProgram,
    Guard,
    PlanRecord,
    PlanSegment,
    PredictionRecord,
    QueryResult,
    RelationChart,
    VariableSpec,
    canonical_json_bytes,
    sha256_value,
)
from cassi_resonant_field import (
    ResonantNumericalError,
    ResonantWorkspace,
    score_pool_probes,
)
from cassi_temporal_field import TemporalField, TemporalFieldError
from cassi_temporal_inquiry import TemporalInquiryError, choose_temporal_inquiry
from cassi_field_cognition import (
    ActionDecision,
    ActionReadout,
    FieldCognition,
    InquiryDecision,
    InquiryOperation,
    Survivor,
    choose_inquiry,
)


SOURCE_SCHEMA = "cassifi.exact-source.v1"
EVIDENCE_EVENT_SCHEMA = "cassifi.field-evidence-event.v1"
CHECKPOINT_SCHEMA = "cassifi.field-atlas-checkpoint.v2"
ROOT_SCHEMA = "cassifi.field-atlas-root.v2"
REVOCATION_SCHEMA = "cassifi.field-revocation-fence.v1"
AUTHORITY_SCHEMA = "cassifi.external-authority-grant.v1"
AUTHORITY_CONTROL_SCHEMA = "cassifi.authority-control.v2"
RPC_SCHEMA = "cassifi.field-intelligence-request.v2"
EVIDENCE_INDEX_SCHEMA = "cassifi.evidence-index.v2"
RPC_RESPONSE_SCHEMA = "cassifi.field-intelligence-response.v2"
WORLD_ADAPTER_JOURNAL_SCHEMA = "cassifi.world-adapter-journal.v2"
PENDING_OPERATION_SCHEMA = "cassifi.pending-owner-operation.v2"
_PENDING_PAYLOAD_KEYS = {
    "acknowledgment": frozenset(
        {
            "acknowledgment",
            "attribution_candidates",
            "learn_chart_ids",
            "prediction_id",
        }
    ),
    "computation-episode": frozenset(
        {
            "context",
            "feature_bindings",
            "outcomes",
            "source",
            "target_chart_ids",
            "workspace",
        }
    ),
    "observation": frozenset(
        {
            "context",
            "derivation_roots",
            "epistemic_type",
            "event_kind",
            "source",
            "target_chart_ids",
            "values",
            "weight",
        }
    ),
    "temporal-episode": frozenset(
        {
            "admitted_step_count",
            "context",
            "event_id",
            "evidence_tick",
            "expected_state_sha256",
            "memory_id",
            "predecessor_manifest_sha256",
            "predecessor_state_sha256",
            "resonant_workspace_state_sha256",
            "source",
            "source_revision_id",
            "temporal_memory_sha256",
        }
    ),
}
_TEMPORAL_RECEIPT_KEYS = {
    "configure-temporal": frozenset(
        {"memory_id", "memory_sha256", "state_count"}
    ),
    "learn-temporal": frozenset(
        {
            "algorithm",
            "available_skills",
            "causal_predecessor",
            "event_id",
            "formed_skills",
            "memory_id",
            "memory_sha256",
            "pending_skills",
            "previous_state_sha256",
            "resonance_coupling",
            "source_revision_id",
            "source_revision_ids",
            "state_count",
            "state_sha256",
            "statistical_limit",
            "status",
            "unresolved_participants",
            "withdrawn_skills",
        }
    ),
    "reset-temporal": frozenset(
        {"memory_id", "memory_sha256", "state_sha256"}
    ),
    "condense-temporal-skill": frozenset(
        {
            "bound_memory_sha256",
            "resonance_coupling",
            "skill_id",
            "start_state_supported",
            "state_sha256",
            "status",
            "supported_states",
        }
    ),
    "bind-temporal": frozenset(
        {
            "memory_id",
            "memory_sha256",
            "participant_id",
            "state_sha256",
        }
    ),
    "compose-temporal-task": frozenset(
        {"execution_authorized", "step_count", "task_id"}
    ),
    "propose-temporal-task": frozenset(
        {
            "action",
            "execution_authorized",
            "proposal",
            "reason",
            "status",
            "task_id",
        }
    ),
    "acknowledge-temporal-task": frozenset(
        {
            "consumed",
            "execution_authorized",
            "proposal_id",
            "status",
            "task_id",
        }
    ),
}
_TEMPORAL_ADVANCE_RECEIPT_KEYS = (
    frozenset(
        {
            "action",
            "context",
            "halted",
            "observation",
            "previous_state_sha256",
            "state",
            "state_sha256",
            "supported",
            "unknown_successor",
        }
    ),
    frozenset(
        {
            "action",
            "context",
            "halted",
            "missing_states",
            "observation",
            "previous_state_sha256",
            "state",
            "state_sha256",
            "supported",
            "unknown_successor",
        }
    ),
)
_COMPUTATIONAL_TRANSITIONS = frozenset({
    "advance", "think", "advance-temporal", "reset-temporal",
})


def _identifier(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 512
        or any(ord(character) < 32 for character in value)
    ):
        raise FieldIntelligenceError(
            "INVALID_IDENTITY", f"{label} must be bounded nonempty text"
        )
    return value


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise FieldIntelligenceError(
            "INVALID_IDENTITY", f"{label} must be a lowercase SHA-256 digest"
        )
    return value

def _regional_source_dependencies(value: Any) -> tuple[str, ...]:
    """Collect explicitly typed evidence references from a regional request."""

    found: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                if key == "source_revision_id":
                    if nested is not None:
                        found.add(_digest(nested, "regional source revision"))
                    continue
                if key == "source_revision_ids":
                    if (
                        isinstance(nested, (str, bytes))
                        or not isinstance(nested, Sequence)
                    ):
                        raise FieldIntelligenceError(
                            "INVALID_EVIDENCE",
                            "regional source revisions must be a sequence",
                        )
                    found.update(
                        _digest(revision, "regional source revision")
                        for revision in nested
                    )
                    continue
                visit(nested)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
            for nested in item:
                visit(nested)

    visit(value)
    return tuple(sorted(found))


def _integer(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise FieldIntelligenceError(
            "INVALID_INTEGER", f"{label} must be an integer >= {minimum}"
        )
    return value


def _finite(value: Any, label: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FieldIntelligenceError("INVALID_NUMERIC_VALUE", f"{label} must be numeric")
    result = float(value)
    if not __import__("math").isfinite(result) or nonnegative and result < 0:
        raise FieldIntelligenceError(
            "INVALID_NUMERIC_VALUE", f"{label} must be finite and valid"
        )
    return result


def _packet_direction(
    path: Any, component: Any, flow_signal: Any
) -> tuple[str, str, list[float]]:
    """Validate one declared packet direction; the write and the read share it.

    The write half and the read half of the packet path address the field by the
    same declaration -- a packet path, a component and a two-channel flow signal
    -- so both validate it here rather than each accepting a slightly different
    request.
    """

    if (
        not isinstance(path, str)
        or len(path.encode("utf-8")) > 512
        or any(character not in "LR" for character in path)
    ):
        raise FieldIntelligenceError(
            "INVALID_REQUEST", "packet path must contain only L and R"
        )
    component = _identifier(component, "packet component")
    if isinstance(flow_signal, (str, bytes)) or not isinstance(flow_signal, Sequence):
        raise FieldIntelligenceError(
            "INVALID_REQUEST", "packet flow signal must be a sequence"
        )
    signal = [_finite(value, "flow_signal") for value in flow_signal]
    if len(signal) != 2:
        raise FieldIntelligenceError(
            "INVALID_REQUEST", "packet flow signal needs two channels"
        )
    return path, component, signal


def _query_result(value: QueryResult | Mapping[str, Any]) -> QueryResult:
    if isinstance(value, QueryResult):
        return value
    if not isinstance(value, Mapping):
        raise FieldIntelligenceError("INVALID_PREPARED_QUERY", "prepared query must be an object")
    fields = (
        "status",
        "state_sha256",
        "field_generation",
        "branches",
        "requested",
        "observed",
        "context",
        "memory_unchanged",
        "query_id",
        "checkpoint_receipt",
    )
    try:
        keys = set(value)
        expected = set(fields)
        allowed = expected | {"resonance_receipt"}
        if not expected.issubset(keys) or not keys.issubset(allowed):
            raise ValueError("prepared query schema is invalid")
        if "resonance_receipt" in value:
            resonance_receipt = value["resonance_receipt"]
            if not isinstance(resonance_receipt, Mapping):
                raise TypeError("prepared query resonance receipt must be an object")
            canonical_json_bytes(dict(resonance_receipt))
        return QueryResult.from_dict({name: value[name] for name in fields})
    except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
        raise FieldIntelligenceError(
            "INVALID_PREPARED_QUERY", "prepared query is malformed"
        ) from exc


def _canonical_read(path: Path) -> Mapping[str, Any]:
    try:
        encoded = path.read_bytes()
        value = json.loads(encoded.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FieldIntelligenceError(
            "PERSISTENCE_CORRUPT", f"{path.name} is unreadable"
        ) from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != encoded:
        raise FieldIntelligenceError(
            "PERSISTENCE_CORRUPT", f"{path.name} is not canonical JSON"
        )
    return value


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _put_object(directory: Path, payload: bytes) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    path = directory / digest
    if path.exists():
        if path.read_bytes() != payload:
            raise FieldIntelligenceError(
                "OBJECT_COLLISION", "content-addressed object identity conflicts"
            )
        return digest
    _atomic_write(path, payload)
    return digest


class OwnerProcessLock:
    """Nonblocking cross-process exclusion for the sole persistent publisher."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            self.handle.write(b"\0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            platform_name = getattr(os, "name", "")
            if platform_name == "nt":
                module = __import__("msvcrt")
                module.locking(self.handle.fileno(), module.LK_NBLCK, 1)
            else:
                module = __import__("fcntl")
                module.flock(
                    self.handle.fileno(),
                    module.LOCK_EX | module.LOCK_NB,
                )
        except (OSError, BlockingIOError) as exc:
            self.handle.close()
            raise FieldIntelligenceError(
                "OWNER_ACTIVE",
                "another process already owns this persistent field",
            ) from exc
        self.closed = False

    def close(self) -> None:
        if self.closed:
            return
        try:
            self.handle.seek(0)
            platform_name = getattr(os, "name", "")
            if platform_name == "nt":
                module = __import__("msvcrt")
                module.locking(self.handle.fileno(), module.LK_UNLCK, 1)
            else:
                module = __import__("fcntl")
                module.flock(self.handle.fileno(), module.LOCK_UN)
        finally:
            self.handle.close()
            self.closed = True


@dataclass(frozen=True, slots=True)
class CapacityLimits:
    """Hard resource ceilings for one owner transition and its checkpoint closure."""

    max_state_bytes: int = 64 * 1024 * 1024
    max_source_bytes: int = 16 * 1024 * 1024
    max_total_evidence_bytes: int = 2 * 1024 * 1024 * 1024
    max_variables: int = 100_000
    max_charts: int = 100_000
    max_programs: int = 100_000
    max_predictions: int = 250_000
    max_plans: int = 25_000
    max_branches_per_query: int = 64
    max_solver_iterations: int = 4096
    max_ports: int = 1_000_000
    max_workspace_bytes: int = 64 * 1024 * 1024
    max_ticks_per_batch: int = 64
    max_operator_effort: int = 4096
    max_source_work: int = 4096
    max_prepared_branches: int = 64
    max_pending_operations: int = 1024
    max_history_entries: int = 4096
    max_checkpoint_frequency: int = 1

    def __post_init__(self) -> None:
        names = (
            "max_state_bytes",
            "max_source_bytes",
            "max_total_evidence_bytes",
            "max_variables",
            "max_charts",
            "max_programs",
            "max_predictions",
            "max_plans",
            "max_branches_per_query",
            "max_solver_iterations",
            "max_ports",
            "max_workspace_bytes",
            "max_ticks_per_batch",
            "max_operator_effort",
            "max_source_work",
            "max_prepared_branches",
            "max_pending_operations",
            "max_history_entries",
            "max_checkpoint_frequency",
        )
        for name in names:
            _integer(getattr(self, name), name, minimum=1)
        if self.max_source_bytes > self.max_total_evidence_bytes:
            raise FieldIntelligenceError(
                "INVALID_CAPACITY", "per-source limit exceeds total evidence limit"
            )
        if self.max_workspace_bytes > self.max_state_bytes:
            raise FieldIntelligenceError(
                "INVALID_CAPACITY", "workspace limit exceeds state limit"
            )

    def as_dict(self) -> Mapping[str, int]:
        return {
            name: getattr(self, name)
            for name in (
                "max_branches_per_query",
                "max_charts",
                "max_checkpoint_frequency",
                "max_history_entries",
                "max_operator_effort",
                "max_pending_operations",
                "max_plans",
                "max_ports",
                "max_prepared_branches",
                "max_predictions",
                "max_programs",
                "max_solver_iterations",
                "max_source_bytes",
                "max_source_work",
                "max_state_bytes",
                "max_ticks_per_batch",
                "max_total_evidence_bytes",
                "max_variables",
                "max_workspace_bytes",
            )
        }


@dataclass(frozen=True, slots=True)
class SourceInput:
    source_id: str
    content: bytes
    media_type: str
    codec: str
    observed_timestamp: str
    scope: str
    claim_category: str
    fidelity: str
    parent_revision_id: str | None = None
    span: tuple[int, int] | None = None
    labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.source_id, "source_id")
        if not isinstance(self.content, bytes):
            raise FieldIntelligenceError(
                "INVALID_SOURCE",
                "source content must be exact bytes",
            )
        for name in (
            "media_type",
            "codec",
            "observed_timestamp",
            "scope",
            "claim_category",
            "fidelity",
        ):
            _identifier(getattr(self, name), name)
        if self.parent_revision_id is not None:
            _digest(self.parent_revision_id, "parent_revision_id")
        if self.span is not None:
            if (
                isinstance(self.span, (str, bytes))
                or not isinstance(self.span, Sequence)
            ):
                raise FieldIntelligenceError(
                    "INVALID_SOURCE",
                    "source span is invalid",
                )
            span = tuple(self.span)
            if (
                len(span) != 2
                or any(
                    isinstance(item, bool) or not isinstance(item, int)
                    for item in span
                )
                or not 0 <= span[0] <= span[1] <= len(self.content)
            ):
                raise FieldIntelligenceError(
                    "INVALID_SOURCE",
                    "source span is invalid",
                )
            object.__setattr__(self, "span", span)
        if (
            isinstance(self.labels, (str, bytes))
            or not isinstance(self.labels, Sequence)
        ):
            raise FieldIntelligenceError(
                "INVALID_SOURCE",
                "source access labels must be a sequence",
            )
        labels = tuple(self.labels)
        for label in labels:
            _identifier(label, "source access label")
        if len(set(labels)) != len(labels):
            raise FieldIntelligenceError(
                "INVALID_SOURCE",
                "source access labels must be unique",
            )
        object.__setattr__(self, "labels", labels)
    def revision_identity(self) -> Mapping[str, Any]:
        return {
            "claim_category": self.claim_category,
            "codec": self.codec,
            "content_sha256": hashlib.sha256(self.content).hexdigest(),
            "fidelity": self.fidelity,
            "labels": list(self.labels),
            "media_type": self.media_type,
            "observed_timestamp": self.observed_timestamp,
            "parent_revision_id": self.parent_revision_id,
            "scope": self.scope,
            "source_id": self.source_id,
            "span": None if self.span is None else list(self.span),
        }

    @property
    def revision_id(self) -> str:
        return sha256_value(self.revision_identity())

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "claim_category": self.claim_category,
            "codec": self.codec,
            "content_base64": base64.b64encode(self.content).decode("ascii"),
            "fidelity": self.fidelity,
            "labels": list(self.labels),
            "media_type": self.media_type,
            "observed_timestamp": self.observed_timestamp,
            "parent_revision_id": self.parent_revision_id,
            "scope": self.scope,
            "source_id": self.source_id,
            "span": None if self.span is None else list(self.span),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SourceInput:
        try:
            if not isinstance(value, Mapping):
                raise TypeError("source input must be an object")
            row = dict(value)
            required = {
                "claim_category",
                "codec",
                "content_base64",
                "fidelity",
                "labels",
                "media_type",
                "observed_timestamp",
                "parent_revision_id",
                "scope",
                "source_id",
                "span",
            }
            if set(row) != required:
                raise ValueError("source input schema is invalid")
            row["content"] = base64.b64decode(
                row.pop("content_base64"),
                validate=True,
            )
            if (
                isinstance(row["labels"], (str, bytes))
                or not isinstance(row["labels"], list)
            ):
                raise TypeError("source labels must be a list")
            row["labels"] = tuple(row["labels"])
            if row["span"] is not None:
                if not isinstance(row["span"], list):
                    raise TypeError("source span must be a list")
                row["span"] = tuple(row["span"])
            return cls(**row)
        except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "INVALID_SOURCE",
                "source input cannot be decoded safely",
            ) from exc


@dataclass(frozen=True, slots=True)
class StoredSource:
    revision_id: str
    source_id: str
    content_sha256: str
    byte_length: int
    object_sha256: str
    media_type: str
    codec: str
    observed_timestamp: str
    scope: str
    claim_category: str
    fidelity: str
    parent_revision_id: str | None
    span: tuple[int, int] | None
    labels: tuple[str, ...]
    status: str
    revocation_generation: int | None = None

    def __post_init__(self) -> None:
        _digest(self.revision_id, "revision_id")
        _identifier(self.source_id, "source_id")
        for name in (
            "media_type",
            "codec",
            "observed_timestamp",
            "scope",
            "claim_category",
            "fidelity",
        ):
            _identifier(getattr(self, name), name)
        for name in ("content_sha256", "object_sha256"):
            _digest(getattr(self, name), name)
        if self.content_sha256 != self.object_sha256:
            raise FieldIntelligenceError(
                "INVALID_SOURCE",
                "source object identity differs from its content identity",
            )
        _integer(self.byte_length, "source byte_length", minimum=0)
        if self.parent_revision_id is not None:
            _digest(self.parent_revision_id, "parent_revision_id")
        if self.span is not None:
            if (
                isinstance(self.span, (str, bytes))
                or not isinstance(self.span, Sequence)
            ):
                raise FieldIntelligenceError(
                    "INVALID_SOURCE",
                    "stored source span is invalid",
                )
            span = tuple(self.span)
            if (
                len(span) != 2
                or any(
                    isinstance(item, bool) or not isinstance(item, int)
                    for item in span
                )
                or not 0 <= span[0] <= span[1] <= self.byte_length
            ):
                raise FieldIntelligenceError(
                    "INVALID_SOURCE",
                    "stored source span is invalid",
                )
            object.__setattr__(self, "span", span)
        if (
            isinstance(self.labels, (str, bytes))
            or not isinstance(self.labels, Sequence)
        ):
            raise FieldIntelligenceError(
                "INVALID_SOURCE",
                "stored source labels must be a sequence",
            )
        labels = tuple(self.labels)
        for label in labels:
            _identifier(label, "source access label")
        if len(set(labels)) != len(labels):
            raise FieldIntelligenceError(
                "INVALID_SOURCE",
                "stored source labels must be unique",
            )
        object.__setattr__(self, "labels", labels)
        if self.status not in {
            "active",
            "superseded",
            "revoked",
            "deleted",
        }:
            raise FieldIntelligenceError(
                "INVALID_SOURCE",
                "source status is unsupported",
            )
        if self.status in {"active", "superseded"}:
            if self.revocation_generation is not None:
                raise FieldIntelligenceError(
                    "INVALID_SOURCE",
                    "live source has a revocation generation",
                )
        elif self.revocation_generation is None:
            raise FieldIntelligenceError(
                "INVALID_SOURCE",
                "revoked source lacks its revocation generation",
            )
        else:
            _integer(
                self.revocation_generation,
                "source revocation generation",
                minimum=1,
            )
        expected_revision_id = sha256_value(
            {
                "claim_category": self.claim_category,
                "codec": self.codec,
                "content_sha256": self.content_sha256,
                "fidelity": self.fidelity,
                "labels": list(self.labels),
                "media_type": self.media_type,
                "observed_timestamp": self.observed_timestamp,
                "parent_revision_id": self.parent_revision_id,
                "scope": self.scope,
                "source_id": self.source_id,
                "span": (
                    None if self.span is None else list(self.span)
                ),
            }
        )
        if self.revision_id != expected_revision_id:
            raise FieldIntelligenceError(
                "INVALID_SOURCE",
                "stored source revision identity is invalid",
            )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "byte_length": self.byte_length,
            "claim_category": self.claim_category,
            "codec": self.codec,
            "content_sha256": self.content_sha256,
            "fidelity": self.fidelity,
            "labels": list(self.labels),
            "media_type": self.media_type,
            "object_sha256": self.object_sha256,
            "observed_timestamp": self.observed_timestamp,
            "parent_revision_id": self.parent_revision_id,
            "revision_id": self.revision_id,
            "revocation_generation": self.revocation_generation,
            "schema": SOURCE_SCHEMA,
            "scope": self.scope,
            "source_id": self.source_id,
            "span": None if self.span is None else list(self.span),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> StoredSource:
        try:
            if not isinstance(value, Mapping):
                raise TypeError("stored source must be an object")
            row = dict(value)
            required = {
                "byte_length",
                "claim_category",
                "codec",
                "content_sha256",
                "fidelity",
                "labels",
                "media_type",
                "object_sha256",
                "observed_timestamp",
                "parent_revision_id",
                "revision_id",
                "revocation_generation",
                "schema",
                "scope",
                "source_id",
                "span",
                "status",
            }
            if set(row) != required or row.pop("schema") != SOURCE_SCHEMA:
                raise ValueError("stored source schema is incompatible")
            if not isinstance(row["labels"], list):
                raise TypeError("stored source labels must be a list")
            row["labels"] = tuple(row["labels"])
            if row["span"] is not None:
                if not isinstance(row["span"], list):
                    raise TypeError("stored source span must be a list")
                row["span"] = tuple(row["span"])
            return cls(**row)
        except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "stored source cannot be decoded safely",
            ) from exc


@dataclass(frozen=True, slots=True)
class EvidenceEvent:
    event_id: str
    operation_id: str
    event_kind: str
    source_revision_id: str
    predecessor_state_sha256: str
    values: Mapping[str, float]
    context: Mapping[str, Any]
    epistemic_type: str
    derivation_roots: tuple[str, ...]
    logical_sequence: int

    @classmethod
    def create(
        cls,
        *,
        operation_id: str,
        event_kind: str,
        source_revision_id: str,
        predecessor_state_sha256: str,
        values: Mapping[str, float],
        context: Mapping[str, Any],
        epistemic_type: str,
        derivation_roots: Sequence[str],
        logical_sequence: int,
    ) -> EvidenceEvent:
        operation_id = _identifier(operation_id, "operation_id")
        event_kind = _identifier(event_kind, "event_kind")
        source_revision_id = _digest(
            source_revision_id,
            "source_revision_id",
        )
        predecessor_state_sha256 = _digest(
            predecessor_state_sha256,
            "predecessor_state_sha256",
        )
        if not isinstance(values, Mapping):
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE",
                "event values must be an object",
            )
        normalized_values = {
            _identifier(name, "event variable"): _finite(value, name)
            for name, value in values.items()
        }
        if not isinstance(context, Mapping):
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE",
                "event context must be an object",
            )
        try:
            normalized_context = json.loads(
                canonical_json_bytes(dict(context))
            )
        except Exception as exc:
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE",
                "event context is invalid",
            ) from exc
        epistemic_type = _identifier(
            epistemic_type,
            "epistemic_type",
        )
        if epistemic_type not in {"observed", "asserted", "derived"}:
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE",
                "event epistemic type cannot teach a chart",
            )
        if (
            isinstance(derivation_roots, (str, bytes))
            or not isinstance(derivation_roots, Sequence)
        ):
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE",
                "event derivation roots must be a sequence",
            )
        normalized_roots = tuple(
            _digest(root, "event derivation root")
            for root in derivation_roots
        )
        logical_sequence = _integer(
            logical_sequence,
            "logical_sequence",
            minimum=1,
        )
        identity = {
            "context": normalized_context,
            "derivation_roots": list(normalized_roots),
            "epistemic_type": epistemic_type,
            "event_kind": event_kind,
            "logical_sequence": logical_sequence,
            "operation_id": operation_id,
            "predecessor_state_sha256": predecessor_state_sha256,
            "source_revision_id": source_revision_id,
            "values": normalized_values,
        }
        return cls(
            event_id=sha256_value(identity),
            operation_id=operation_id,
            event_kind=event_kind,
            source_revision_id=source_revision_id,
            predecessor_state_sha256=predecessor_state_sha256,
            values=normalized_values,
            context=normalized_context,
            epistemic_type=epistemic_type,
            derivation_roots=normalized_roots,
            logical_sequence=logical_sequence,
        )

    def __post_init__(self) -> None:
        _digest(self.event_id, "event_id")
        _identifier(self.operation_id, "operation_id")
        _identifier(self.event_kind, "event_kind")
        _digest(self.source_revision_id, "source_revision_id")
        _digest(
            self.predecessor_state_sha256,
            "predecessor_state_sha256",
        )
        if not isinstance(self.values, Mapping):
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE",
                "event values must be an object",
            )
        normalized: dict[str, float] = {}
        for name, value in self.values.items():
            normalized[_identifier(name, "event variable")] = _finite(
                value,
                name,
            )
        object.__setattr__(self, "values", normalized)
        if not isinstance(self.context, Mapping):
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE",
                "event context must be an object",
            )
        try:
            normalized_context = json.loads(
                canonical_json_bytes(dict(self.context))
            )
        except Exception as exc:
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE",
                "event context is invalid",
            ) from exc
        object.__setattr__(self, "context", normalized_context)
        _identifier(self.epistemic_type, "epistemic_type")
        if self.epistemic_type not in {"observed", "asserted", "derived"}:
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE",
                "event epistemic type cannot teach a chart",
            )
        if (
            isinstance(self.derivation_roots, (str, bytes))
            or not isinstance(self.derivation_roots, Sequence)
        ):
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE",
                "event derivation roots must be a sequence",
            )
        roots = tuple(self.derivation_roots)
        for root in roots:
            _digest(root, "event derivation root")
        object.__setattr__(self, "derivation_roots", roots)
        _integer(self.logical_sequence, "logical_sequence", minimum=1)
        expected = sha256_value(
            {
                "context": dict(self.context),
                "derivation_roots": list(self.derivation_roots),
                "epistemic_type": self.epistemic_type,
                "event_kind": self.event_kind,
                "logical_sequence": self.logical_sequence,
                "operation_id": self.operation_id,
                "predecessor_state_sha256": (
                    self.predecessor_state_sha256
                ),
                "source_revision_id": self.source_revision_id,
                "values": dict(self.values),
            }
        )
        if expected != self.event_id:
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE",
                "event identity is invalid",
            )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "context": dict(self.context),
            "derivation_roots": list(self.derivation_roots),
            "epistemic_type": self.epistemic_type,
            "event_id": self.event_id,
            "event_kind": self.event_kind,
            "logical_sequence": self.logical_sequence,
            "operation_id": self.operation_id,
            "predecessor_state_sha256": self.predecessor_state_sha256,
            "schema": EVIDENCE_EVENT_SCHEMA,
            "source_revision_id": self.source_revision_id,
            "values": dict(self.values),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EvidenceEvent:
        try:
            if not isinstance(value, Mapping):
                raise TypeError("evidence event must be an object")
            row = dict(value)
            required = {
                "context",
                "derivation_roots",
                "epistemic_type",
                "event_id",
                "event_kind",
                "logical_sequence",
                "operation_id",
                "predecessor_state_sha256",
                "schema",
                "source_revision_id",
                "values",
            }
            if (
                set(row) != required
                or row.pop("schema") != EVIDENCE_EVENT_SCHEMA
            ):
                raise ValueError("event schema is incompatible")
            if not isinstance(row["derivation_roots"], list):
                raise TypeError("event derivation roots must be a list")
            row["derivation_roots"] = tuple(row["derivation_roots"])
            return cls(**row)
        except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "evidence event cannot be decoded safely",
            ) from exc


class ExactEvidenceStore:
    def __init__(self, root: Path, *, limits: CapacityLimits) -> None:
        self.root = Path(root)
        self.limits = limits
        self.blobs = self.root / "blobs"
        self.sources = self.root / "sources"
        self.events = self.root / "events"
        self.index_path = self.root / "index.json"
        for directory in (self.blobs, self.sources, self.events):
            directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._index_cache: dict[str, Any] = {}
        if not self.index_path.exists():
            self._save_index(
                {
                    "active_revision_ids": [],
                    "event_ids": [],
                    "operation_events": {},
                    "revision_ids": [],
                    "schema": EVIDENCE_INDEX_SCHEMA,
                    "source_heads": {},
                }
            )
        else:
            value = dict(_canonical_read(self.index_path))
            if value.get("schema") == "cassifi.evidence-index.v1":
                if (
                    set(value)
                    != {
                        "event_ids",
                        "operation_events",
                        "revision_ids",
                        "schema",
                        "source_heads",
                    }
                    or not isinstance(value["revision_ids"], list)
                ):
                    raise FieldIntelligenceError(
                        "PERSISTENCE_CORRUPT",
                        "legacy evidence index schema is incompatible",
                    )
                active = [
                    revision_id
                    for revision_id in value["revision_ids"]
                    if self.source(revision_id).status == "active"
                ]
                value["active_revision_ids"] = active
                value["schema"] = EVIDENCE_INDEX_SCHEMA
                self._save_index(value)
            else:
                self._index_cache = self._validate_index(value)
        self._validate_index_closure(self._index())

    @staticmethod
    def _validate_index(value: Mapping[str, Any]) -> dict[str, Any]:
        try:
            required = {
                "active_revision_ids",
                "event_ids",
                "operation_events",
                "revision_ids",
                "schema",
                "source_heads",
            }
            if (
                not isinstance(value, Mapping)
                or set(value) != required
                or value["schema"] != EVIDENCE_INDEX_SCHEMA
            ):
                raise ValueError("evidence index schema is incompatible")

            def digest_list(name: str) -> list[str]:
                raw = value[name]
                if not isinstance(raw, list):
                    raise TypeError(f"{name} must be a list")
                normalized = [
                    _digest(item, f"evidence index {name}")
                    for item in raw
                ]
                if len(set(normalized)) != len(normalized):
                    raise ValueError(f"{name} contains duplicates")
                return normalized

            revisions = digest_list("revision_ids")
            active = digest_list("active_revision_ids")
            events = digest_list("event_ids")
            if not set(active).issubset(revisions):
                raise ValueError(
                    "active source revisions are absent from the index"
                )

            raw_heads = value["source_heads"]
            if not isinstance(raw_heads, Mapping):
                raise TypeError("source heads must be an object")
            source_heads = {
                _identifier(source_id, "indexed source_id"): _digest(
                    revision_id,
                    "indexed source head",
                )
                for source_id, revision_id in raw_heads.items()
            }
            if (
                len(set(source_heads.values())) != len(source_heads)
                or set(source_heads.values()) != set(active)
            ):
                raise ValueError(
                    "source heads and active revisions disagree"
                )

            raw_operations = value["operation_events"]
            if not isinstance(raw_operations, Mapping):
                raise TypeError("operation events must be an object")
            operation_events = {
                _identifier(
                    operation_id,
                    "indexed evidence operation",
                ): _digest(event_id, "indexed evidence event")
                for operation_id, event_id in raw_operations.items()
            }
            if (
                len(set(operation_events.values()))
                != len(operation_events)
                or set(operation_events.values()) != set(events)
            ):
                raise ValueError(
                    "operation events and event identities disagree"
                )
            return {
                "active_revision_ids": active,
                "event_ids": events,
                "operation_events": operation_events,
                "revision_ids": revisions,
                "schema": EVIDENCE_INDEX_SCHEMA,
                "source_heads": source_heads,
            }
        except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "evidence index cannot be decoded safely",
            ) from exc

    def _validate_index_closure(
        self,
        index: Mapping[str, Any],
    ) -> None:
        try:
            revision_ids = tuple(index["revision_ids"])
            active_ids = set(index["active_revision_ids"])
            sources: dict[str, StoredSource] = {}
            for revision_id in revision_ids:
                try:
                    sources[revision_id] = self.source(revision_id)
                except FieldIntelligenceError as exc:
                    if exc.code == "SOURCE_NOT_FOUND":
                        raise FieldIntelligenceError(
                            "SOURCE_MISSING",
                            "indexed source revision is unavailable",
                        ) from exc
                    raise
            for revision_id, source in sources.items():
                if source.revision_id != revision_id:
                    raise ValueError(
                        "source revision identity differs from its index key"
                    )
                if (source.status == "active") != (
                    revision_id in active_ids
                ):
                    raise ValueError(
                        "source status differs from the active index"
                    )
                parent_id = source.parent_revision_id
                if parent_id is not None:
                    parent = sources.get(parent_id)
                    if parent is None or parent.source_id != source.source_id:
                        raise ValueError(
                            "source parent lineage is unavailable"
                        )
                if source.status != "deleted":
                    object_path = self.blobs / source.object_sha256
                    if not object_path.is_file():
                        raise FieldIntelligenceError(
                            "SOURCE_MISSING",
                            "indexed source content object is unavailable",
                        )
                    content = object_path.read_bytes()
                    if (
                        len(content) != source.byte_length
                        or hashlib.sha256(content).hexdigest()
                        != source.content_sha256
                    ):
                        raise FieldIntelligenceError(
                            "SOURCE_CORRUPT",
                            "indexed source content object failed integrity checks",
                        )

            heads = index["source_heads"]
            if any(
                sources[revision_id].source_id != source_id
                for source_id, revision_id in heads.items()
            ):
                raise ValueError(
                    "source head identity differs from its source"
                )

            event_ids = tuple(index["event_ids"])
            events: dict[str, EvidenceEvent] = {}
            for event_id in event_ids:
                events[event_id] = self.event(event_id)
            if tuple(
                event.logical_sequence for event in events.values()
            ) != tuple(range(1, len(event_ids) + 1)):
                raise ValueError(
                    "evidence event sequence differs from index order"
                )
            operations = index["operation_events"]
            for event_id, event in events.items():
                if (
                    event.event_id != event_id
                    or event.source_revision_id not in sources
                    or operations.get(event.operation_id) != event_id
                ):
                    raise ValueError(
                        "evidence event identity differs from its index"
                    )
        except FieldIntelligenceError as exc:
            if exc.code in {
                "EVENT_NOT_FOUND",
                "SOURCE_CORRUPT",
                "SOURCE_MISSING",
            }:
                raise
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "evidence index closure cannot be decoded safely",
            ) from exc
        except (KeyError, OSError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "evidence index closure cannot be decoded safely",
            ) from exc

    def _index(self) -> dict[str, Any]:
        return self._validate_index(self._index_cache)

    def _save_index(self, value: Mapping[str, Any]) -> None:
        validated = self._validate_index(value)
        encoded = canonical_json_bytes(validated)
        _atomic_write(self.index_path, encoded)
        self._index_cache = dict(json.loads(encoded))

    def physical_bytes(self) -> int:
        total = 0
        for directory in (self.blobs, self.sources, self.events):
            for path in directory.iterdir():
                if path.is_file():
                    total += path.stat().st_size
        return total

    def store_source(
        self,
        source: SourceInput,
        *,
        reserved_bytes: int = 0,
        commit: bool = True,
    ) -> StoredSource:
        with self._lock:
            reserved = _integer(
                reserved_bytes, "reserved evidence bytes", minimum=0
            )
            if len(source.content) > self.limits.max_source_bytes:
                raise FieldIntelligenceError(
                    "SOURCE_CAPACITY",
                    "source exceeds the configured per-revision byte limit",
                    details={"bytes": len(source.content), "limit": self.limits.max_source_bytes},
                )
            index = self._index()
            identity = source.revision_identity()
            content_sha = identity["content_sha256"]
            revision_id = source.revision_id
            if revision_id in index["revision_ids"]:
                stored = self.source(revision_id)
                try:
                    existing_content = (self.blobs / stored.object_sha256).read_bytes()
                except OSError as exc:
                    raise FieldIntelligenceError(
                        "SOURCE_MISSING", "idempotent source bytes are unavailable"
                    ) from exc
                if (
                    existing_content != source.content
                    or hashlib.sha256(existing_content).hexdigest()
                    != stored.content_sha256
                ):
                    raise FieldIntelligenceError(
                        "SOURCE_CONFLICT", "source identity resolves to different bytes"
                    )
                if stored.status != "active":
                    raise FieldIntelligenceError(
                        "SOURCE_STALE",
                        "revoked or superseded evidence cannot be admitted again",
                    )
                if (
                    self.physical_bytes() + reserved
                    > self.limits.max_total_evidence_bytes
                ):
                    raise FieldIntelligenceError(
                        "EVIDENCE_CAPACITY",
                        "exact evidence capacity is exhausted",
                    )
                return stored
            head_id = index["source_heads"].get(source.source_id)
            if (
                source.parent_revision_id is not None
                and head_id != source.parent_revision_id
            ):
                raise FieldIntelligenceError(
                    "SOURCE_PARENT_CONFLICT",
                    "source revision does not extend the active source head",
                    details={
                        "actual": source.parent_revision_id,
                        "expected": head_id,
                    },
                )
            if source.parent_revision_id is None and head_id is not None:
                raise FieldIntelligenceError(
                    "SOURCE_PARENT_REQUIRED",
                    "existing source requires its active parent revision",
                )
            stored = StoredSource(
                revision_id=revision_id,
                source_id=source.source_id,
                content_sha256=content_sha,
                byte_length=len(source.content),
                object_sha256=content_sha,
                media_type=source.media_type,
                codec=source.codec,
                observed_timestamp=source.observed_timestamp,
                scope=source.scope,
                claim_category=source.claim_category,
                fidelity=source.fidelity,
                parent_revision_id=source.parent_revision_id,
                span=source.span,
                labels=source.labels,
                status="active",
            )
            stored_encoded = canonical_json_bytes(stored.as_dict())
            projected = self.physical_bytes() + len(stored_encoded) + reserved
            blob_path = self.blobs / content_sha
            if not blob_path.is_file():
                projected += len(source.content)
            previous: StoredSource | None = None
            superseded_encoded: bytes | None = None
            if head_id is not None:
                previous = self.source(head_id)
                superseded_encoded = canonical_json_bytes(
                    replace(previous, status="superseded").as_dict()
                )
                projected += len(superseded_encoded) - (
                    self.sources / head_id
                ).stat().st_size
            if projected > self.limits.max_total_evidence_bytes:
                raise FieldIntelligenceError(
                    "EVIDENCE_CAPACITY", "exact evidence capacity is exhausted"
                )
            if not commit:
                return stored
            object_sha = _put_object(self.blobs, source.content)
            if object_sha != stored.object_sha256:
                raise FieldIntelligenceError(
                    "PERSISTENCE_CORRUPT", "source object identity changed during storage"
                )
            _atomic_write(self.sources / revision_id, stored_encoded)
            if previous is not None and superseded_encoded is not None:
                _atomic_write(self.sources / previous.revision_id, superseded_encoded)
            index["revision_ids"].append(revision_id)
            if head_id is not None:
                index["active_revision_ids"].remove(head_id)
            index["active_revision_ids"].append(revision_id)
            index["source_heads"][source.source_id] = revision_id
            self._save_index(index)
            return stored

    def source(self, revision_id: str) -> StoredSource:
        digest = _digest(revision_id, "revision_id")
        path = self.sources / digest
        if not path.is_file():
            raise FieldIntelligenceError("SOURCE_NOT_FOUND", "source revision is unavailable")
        return StoredSource.from_dict(_canonical_read(path))

    def read(
        self,
        reference: StoredSource | str,
        *,
        allow_historical: bool = False,
        allowed_labels: frozenset[str] | None = None,
    ) -> bytes:
        source = self.source(reference) if isinstance(reference, str) else reference
        if source.status in {"revoked", "deleted"}:
            raise FieldIntelligenceError("SOURCE_REVOKED", "source revision is revoked")
        if source.status != "active" and not allow_historical:
            raise FieldIntelligenceError(
                "SOURCE_STALE", "source revision is exact but no longer current"
            )
        if allowed_labels is not None and not set(source.labels).issubset(allowed_labels):
            raise FieldIntelligenceError("SOURCE_ACCESS", "source labels exceed caller access")
        try:
            content = (self.blobs / source.object_sha256).read_bytes()
        except OSError as exc:
            raise FieldIntelligenceError("SOURCE_MISSING", "source bytes are unavailable") from exc
        if (
            len(content) != source.byte_length
            or hashlib.sha256(content).hexdigest() != source.content_sha256
            or hashlib.sha256(content).hexdigest() != source.object_sha256
        ):
            raise FieldIntelligenceError("SOURCE_CORRUPT", "source bytes failed integrity checks")
        return content

    def active_revision_ids(self) -> frozenset[str]:
        return frozenset(self._index()["active_revision_ids"])

    def all_revision_ids(self) -> tuple[str, ...]:
        return tuple(self._index()["revision_ids"])

    def all_event_ids(self) -> tuple[str, ...]:
        return tuple(self._index()["event_ids"])

    def event_for_operation(self, operation_id: str) -> EvidenceEvent | None:
        event_id = self._index()["operation_events"].get(
            _identifier(operation_id, "operation_id")
        )
        return None if event_id is None else self.event(event_id)
    def active_event(self, event_id: str) -> EvidenceEvent:
        event = self.event(event_id)
        if event.source_revision_id not in self.active_revision_ids():
            raise FieldIntelligenceError(
                "EVIDENCE_INACTIVE",
                "evidence event belongs to a non-active source revision",
            )
        return event



    def revoke(
        self,
        revision_ids: Sequence[str],
        *,
        generation: int,
        delete_bytes: bool = False,
    ) -> None:
        with self._lock:
            index = self._index()
            targets = tuple(_digest(item, "revision_id") for item in revision_ids)
            rows = [self.source(item) for item in targets]
            for row in rows:
                revoked = replace(
                    row,
                    status="deleted" if delete_bytes else "revoked",
                    revocation_generation=generation,
                )
                _atomic_write(
                    self.sources / row.revision_id,
                    canonical_json_bytes(revoked.as_dict()),
                )
                if index["source_heads"].get(row.source_id) == row.revision_id:
                    del index["source_heads"][row.source_id]
                if row.revision_id in index["active_revision_ids"]:
                    index["active_revision_ids"].remove(row.revision_id)
            self._save_index(index)
            if delete_bytes:
                referenced = {
                    self.source(item).object_sha256
                    for item in index["revision_ids"]
                    if self.source(item).status != "deleted"
                }
                for row in rows:
                    if row.object_sha256 not in referenced:
                        try:
                            (self.blobs / row.object_sha256).unlink()
                        except FileNotFoundError:
                            pass

    def append_event(self, event: EvidenceEvent) -> EvidenceEvent:
        with self._lock:
            index = self._index()
            existing_id = index["operation_events"].get(event.operation_id)
            if existing_id is not None:
                existing = self.event(existing_id)
                if existing != event:
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "operation identity is already bound to different evidence",
                    )
                return existing
            encoded = canonical_json_bytes(event.as_dict())
            projected = self.physical_bytes() + len(encoded)
            if projected > self.limits.max_total_evidence_bytes:
                raise FieldIntelligenceError(
                    "EVIDENCE_CAPACITY", "exact evidence capacity is exhausted"
                )
            _atomic_write(self.events / event.event_id, encoded)
            index["event_ids"].append(event.event_id)
            index["operation_events"][event.operation_id] = event.event_id
            self._save_index(index)
            return event

    def event(self, event_id: str) -> EvidenceEvent:
        digest = _digest(event_id, "event_id")
        path = self.events / digest
        if not path.is_file():
            raise FieldIntelligenceError(
                "EVENT_NOT_FOUND", "evidence event is unavailable"
            )
        event = EvidenceEvent.from_dict(_canonical_read(path))
        if event.event_id != digest:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "evidence event filename does not match its identity",
            )
        return event

    def events_for_source(self, revision_id: str) -> tuple[EvidenceEvent, ...]:
        target = _digest(revision_id, "revision_id")
        return tuple(
            event
            for event_id in self._index()["event_ids"]
            for event in (self.event(event_id),)
            if event.source_revision_id == target
        )

    @property
    def event_count(self) -> int:
        return len(self._index()["event_ids"])


@dataclass(frozen=True, slots=True)
class CheckpointReceipt:
    operation_id: str
    manifest_sha256: str
    state_sha256: str
    predecessor_manifest_sha256: str
    generation: int
    replayed: bool

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "generation": self.generation,
            "manifest_sha256": self.manifest_sha256,
            "operation_id": self.operation_id,
            "predecessor_manifest_sha256": self.predecessor_manifest_sha256,
            "replayed": self.replayed,
            "state_sha256": self.state_sha256,
        }


class AtlasCheckpointStore:
    def __init__(
        self,
        root: Path,
        *,
        limits: CapacityLimits,
        initial_state: AtlasState | None = None,
    ) -> None:
        self.root = Path(root)
        self.limits = limits
        self.objects = self.root / "objects"
        self.manifests = self.root / "manifests"
        self.staging = self.root / "staging"
        self.operations = self.root / "operations"
        self.current_path = self.root / "CURRENT"
        self.revocation_path = self.root / "REVOCATION"
        self.history_floor_path = self.root / "HISTORY_FLOOR"
        self.quarantine_path = self.root / "QUARANTINE"
        for directory in (self.objects, self.manifests, self.staging, self.operations):
            directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if self.quarantine_path.exists():
            raise FieldIntelligenceError(
                "STATE_QUARANTINED", "field store requires explicit recovery"
            )
        if not self.history_floor_path.exists():
            _atomic_write(
                self.history_floor_path,
                canonical_json_bytes(
                    {
                        "discarded_operation_ids": [],
                        "floor_generation": 0,
                        "floor_manifest_sha256": None,
                        "schema": "cassifi.field-history-floor.v1",
                        "watermarks": {},
                    }
                ),
            )
        if not self.revocation_path.exists():
            self._write_revocation(0, (), "genesis")
        if not self.current_path.exists():
            self._initialize(initial_state or AtlasState())
        self.recover()
        self.current_manifest_sha256, self.current_manifest = self._load_current()
        self.state = self._load_state(self.current_manifest)
        self._validate_history_chain(self.current_manifest)
        self._validate_operation_records()
        fence = self.revocation_fence()
        if self.state.revocation_generation > fence["generation"]:
            self._quarantine(
                "REVOCATION_ROLLBACK",
                {
                    "field_generation": self.state.revocation_generation,
                    "fence_generation": fence["generation"],
                },
            )

    def _quarantine(self, reason: str, details: Mapping[str, Any]) -> NoReturn:
        payload = {
            "details": dict(details),
            "reason": reason,
            "schema": "cassifi.field-quarantine.v1",
        }
        _atomic_write(self.quarantine_path, canonical_json_bytes(payload))
        raise FieldIntelligenceError(
            "STATE_QUARANTINED",
            "field store entered quarantine instead of guessing recovery",
            details=payload,
        )

    def _write_revocation(
        self, generation: int, revision_ids: Sequence[str], operation_id: str
    ) -> None:
        payload = {
            "generation": generation,
            "operation_id": operation_id,
            "revision_ids": sorted(revision_ids),
            "schema": REVOCATION_SCHEMA,
        }
        _atomic_write(self.revocation_path, canonical_json_bytes(payload))

    def revocation_fence(self) -> Mapping[str, Any]:
        try:
            value = _canonical_read(self.revocation_path)
            if (
                set(value)
                != {
                    "generation",
                    "operation_id",
                    "revision_ids",
                    "schema",
                }
                or value["schema"] != REVOCATION_SCHEMA
            ):
                raise ValueError(
                    "revocation fence schema is incompatible"
                )
            _integer(value["generation"], "revocation generation")
            _identifier(
                value["operation_id"],
                "revocation operation_id",
            )
            raw_revisions = value["revision_ids"]
            if not isinstance(raw_revisions, list):
                raise TypeError(
                    "revoked revision identities must be a list"
                )
            revisions = [
                _digest(revision_id, "revoked revision")
                for revision_id in raw_revisions
            ]
            if revisions != sorted(set(revisions)):
                raise ValueError(
                    "revoked revision identities are not canonical"
                )
            return value
        except (
            FieldIntelligenceError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "revocation fence cannot be decoded safely",
            ) from exc

    def advance_revocation(
        self, revision_ids: Sequence[str], *, operation_id: str
    ) -> Mapping[str, Any]:
        with self._lock:
            _identifier(operation_id, "operation_id")
            targets = tuple(sorted({_digest(item, "revision_id") for item in revision_ids}))
            if not targets:
                raise FieldIntelligenceError("INVALID_REVOCATION", "revocation target cannot be empty")
            current = self.revocation_fence()
            if current["operation_id"] == operation_id:
                if tuple(current["revision_ids"]) != targets:
                    raise FieldIntelligenceError("OPERATION_CONFLICT", "revocation operation target conflicts")
                return current
            value = {
                "generation": int(current["generation"]) + 1,
                "operation_id": operation_id,
                "revision_ids": list(targets),
                "schema": REVOCATION_SCHEMA,
            }
            _atomic_write(self.revocation_path, canonical_json_bytes(value))
            return value

    def _state_descriptor(self, state: AtlasState) -> tuple[str, str]:
        encoded = state.encode()
        pages = state.object_pages()
        if not isinstance(pages, Mapping):
            raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "state page closure is invalid")
        page_hashes: list[str] = []
        seen_pages: set[str] = set()
        closure_bytes = len(encoded)
        for page_sha, page in sorted(pages.items()):
            page_sha = _digest(page_sha, "state page identity")
            if page_sha in seen_pages:
                raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "duplicate state page identity")
            seen_pages.add(page_sha)
            if not isinstance(page, bytes) or hashlib.sha256(page).hexdigest() != page_sha:
                raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "state page identity is invalid")
            page_hashes.append(page_sha)
            closure_bytes += len(page)
        descriptor = canonical_json_bytes(
            {
                "history_floor": dict(self._history_floor()),
                "pages": page_hashes,
                "schema": ROOT_SCHEMA,
                "state": json.loads(encoded.decode("utf-8")),
                "state_sha256": state.state_sha256,
            }
        )
        closure_bytes += len(descriptor)
        if closure_bytes > self.limits.max_state_bytes:
            raise FieldIntelligenceError(
                "STATE_CAPACITY",
                "reachable field checkpoint closure exceeds its configured byte limit",
                details={"bytes": closure_bytes, "limit": self.limits.max_state_bytes},
            )
        for page in pages.values():
            _put_object(self.objects, page)
        descriptor_sha = _put_object(self.objects, descriptor)
        return descriptor_sha, state.state_sha256

    def _hydrate_descriptor(self, descriptor_sha256: str) -> AtlasState:
        path = self.objects / _digest(descriptor_sha256, "state descriptor")
        try:
            encoded = path.read_bytes()
        except OSError as exc:
            raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "state descriptor is unavailable") from exc
        if hashlib.sha256(encoded).hexdigest() != descriptor_sha256:
            raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "state descriptor identity is invalid")
        try:
            root = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "state descriptor is unreadable") from exc
        if (
            not isinstance(root, dict)
            or set(root) not in (
                {"pages", "schema", "state", "state_sha256"},
                {"history_floor", "pages", "schema", "state", "state_sha256"},
            )
            or root["schema"] != ROOT_SCHEMA
            or not isinstance(root["pages"], list)
            or not isinstance(root["state"], dict)
        ):
            raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "state descriptor schema is invalid")
        objects: dict[str, bytes] = {}
        closure_bytes = len(encoded)
        for page_sha in root["pages"]:
            page_sha = _digest(page_sha, "state page identity")
            try:
                page = (self.objects / page_sha).read_bytes()
            except OSError as exc:
                raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "state page is unavailable") from exc
            if hashlib.sha256(page).hexdigest() != page_sha:
                raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "state page identity is invalid")
            objects[page_sha] = page
            closure_bytes += len(page)
        if closure_bytes > self.limits.max_state_bytes:
            raise FieldIntelligenceError(
                "STATE_CAPACITY",
                "reachable field checkpoint closure exceeds its configured byte limit",
                details={"bytes": closure_bytes, "limit": self.limits.max_state_bytes},
            )
        state = AtlasState.decode(canonical_json_bytes(root["state"]), objects=objects)
        if state.state_sha256 != _digest(root["state_sha256"], "state_sha256"):
            raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "hydrated state identity does not match")
        return state

    def _initialize(self, state: AtlasState) -> None:
        descriptor_sha, state_sha = self._state_descriptor(state)
        manifest = {
            "event_id": None,
            "generation": state.generation,
            "operation_id": "genesis",
            "parent_manifest_sha256": None,
            "revocation_generation": state.revocation_generation,
            "schema": CHECKPOINT_SCHEMA,
            "state_descriptor_sha256": descriptor_sha,
            "state_sha256": state_sha,
            "transition": {"kind": "genesis"},
        }
        manifest_bytes = canonical_json_bytes(manifest)
        manifest_sha = _put_object(self.manifests, manifest_bytes)
        _atomic_write(self.current_path, (manifest_sha + "\n").encode("ascii"))

    def _manifest(self, digest: str) -> Mapping[str, Any]:
        digest = _digest(digest, "manifest_sha256")
        path = self.manifests / digest
        try:
            value = _canonical_read(path)
        except (OSError, FieldIntelligenceError) as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "checkpoint manifest is unavailable",
            ) from exc
        if hashlib.sha256(canonical_json_bytes(value)).hexdigest() != digest:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "manifest identity is invalid",
            )
        if value.get("schema") == "cassifi.field-atlas-checkpoint.v1":
            raise FieldIntelligenceError(
                "MIGRATION_REQUIRED",
                "v1 checkpoint requires explicit FieldIntelligenceOwner.migrate_v1",
            )
        try:
            required = {
                "event_id",
                "generation",
                "operation_id",
                "parent_manifest_sha256",
                "revocation_generation",
                "schema",
                "state_descriptor_sha256",
                "state_sha256",
                "transition",
            }
            if (
                not isinstance(value, Mapping)
                or set(value) != required
                or value["schema"] != CHECKPOINT_SCHEMA
            ):
                raise ValueError(
                    "checkpoint manifest schema is invalid"
                )
            _integer(value["generation"], "manifest generation")
            _integer(
                value["revocation_generation"],
                "manifest revocation generation",
            )
            _identifier(
                value["operation_id"],
                "manifest operation_id",
            )
            _digest(
                value["state_descriptor_sha256"],
                "manifest state descriptor",
            )
            _digest(value["state_sha256"], "manifest state")
            if value["event_id"] is not None:
                _digest(value["event_id"], "manifest event")
            if value["parent_manifest_sha256"] is not None:
                _digest(
                    value["parent_manifest_sha256"],
                    "manifest parent",
                )
            transition = value["transition"]
            if not isinstance(transition, Mapping):
                raise TypeError(
                    "checkpoint transition must be an object"
                )
            transition_kind = _identifier(
                transition.get("kind"),
                "checkpoint transition kind",
            )
            if transition_kind == "genesis" and set(transition) != {
                "kind"
            }:
                raise ValueError("genesis transition is malformed")
            if transition_kind == "migrate-v1":
                if set(transition) != {
                    "kind",
                    "source_manifest_sha256",
                }:
                    raise ValueError(
                        "migration transition is malformed"
                    )
                _digest(
                    transition["source_manifest_sha256"],
                    "migration source manifest",
                )
        except (
            FieldIntelligenceError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "checkpoint manifest cannot be decoded safely",
            ) from exc
        return value

    def _load_current(self) -> tuple[str, Mapping[str, Any]]:
        try:
            text = self.current_path.read_text(encoding="ascii")
        except (OSError, UnicodeError) as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "CURRENT is unreadable",
            ) from exc
        if not text.endswith("\n"):
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "CURRENT is malformed",
            )
        try:
            digest = _digest(text[:-1], "CURRENT")
        except FieldIntelligenceError as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "CURRENT is malformed",
            ) from exc
        return digest, self._manifest(digest)

    def _validate_history_chain(
        self,
        current: Mapping[str, Any],
    ) -> None:
        floor = self._history_floor()
        floor_sha = floor["floor_manifest_sha256"]
        floor_generation = int(floor["floor_generation"])
        if floor_sha is None and floor_generation != 0:
            raise FieldIntelligenceError(
                "HISTORY_CORRUPT",
                "history floor has no anchor",
            )
        if (
            floor_sha is not None
            and not (self.manifests / floor_sha).is_file()
        ):
            raise FieldIntelligenceError(
                "HISTORY_CORRUPT",
                "history floor anchor is unavailable",
            )

        cursor = current
        cursor_sha = hashlib.sha256(
            canonical_json_bytes(dict(cursor))
        ).hexdigest()
        seen = {cursor_sha}
        while True:
            generation = int(cursor["generation"])
            if floor_sha is not None and cursor_sha == floor_sha:
                if generation != floor_generation:
                    raise FieldIntelligenceError(
                        "HISTORY_CORRUPT",
                        "history floor generation is inconsistent",
                    )
                break

            parent = cursor["parent_manifest_sha256"]
            if parent is None:
                if floor_sha is not None or cursor["transition"].get(
                    "kind"
                ) not in {"genesis", "migrate-v1"}:
                    raise FieldIntelligenceError(
                        "HISTORY_CORRUPT",
                        "retained manifest chain has no valid root",
                    )
                break
            if generation <= floor_generation or parent in seen:
                raise FieldIntelligenceError(
                    "HISTORY_CORRUPT",
                    "retained manifest chain is broken",
                )
            seen.add(parent)
            parent_manifest = self._manifest(parent)
            if int(parent_manifest["generation"]) != generation - 1:
                raise FieldIntelligenceError(
                    "HISTORY_CORRUPT",
                    "retained manifest generations are discontinuous",
                )
            cursor = parent_manifest
            cursor_sha = parent

    def _history_floor(self) -> Mapping[str, Any]:
        try:
            value = _canonical_read(self.history_floor_path)
            required = {
                "discarded_operation_ids",
                "floor_generation",
                "floor_manifest_sha256",
                "schema",
                "watermarks",
            }
            if (
                set(value) != required
                or value["schema"]
                != "cassifi.field-history-floor.v1"
            ):
                raise ValueError("history floor schema is invalid")
            floor_generation = _integer(
                value["floor_generation"],
                "history floor generation",
            )
            floor_sha = value["floor_manifest_sha256"]
            if floor_sha is not None:
                _digest(floor_sha, "history floor manifest")
            elif floor_generation != 0:
                raise ValueError(
                    "history floor without an anchor is nonzero"
                )
            tombstones = value["discarded_operation_ids"]
            if not isinstance(tombstones, list):
                raise TypeError("history tombstones are invalid")
            normalized_tombstones = [
                _identifier(operation_id, "discarded operation")
                for operation_id in tombstones
            ]
            if len(set(normalized_tombstones)) != len(
                normalized_tombstones
            ):
                raise ValueError("history tombstones contain duplicates")
            watermarks = value["watermarks"]
            if not isinstance(watermarks, Mapping):
                raise TypeError("history watermarks are invalid")
            for producer, sequence in watermarks.items():
                _identifier(producer, "history producer")
                _integer(sequence, "history sequence")
            return value
        except (
            FieldIntelligenceError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            raise FieldIntelligenceError(
                "HISTORY_CORRUPT",
                "history floor cannot be decoded safely",
            ) from exc

    def operation_compacted(self, operation_id: str) -> bool:
        operation_id = _identifier(operation_id, "operation_id")
        floor = self._history_floor()
        if operation_id in floor["discarded_operation_ids"]:
            return True
        if ":" not in operation_id:
            return False
        producer, sequence_text = operation_id.rsplit(":", 1)
        if not sequence_text.isdigit():
            return False
        return int(sequence_text) <= int(floor["watermarks"].get(producer, -1))

    def _compact_history_for(self, successor: AtlasState) -> None:
        # Manifest files are immutable content-addressed objects.  Keep a
        # disposable index of the files seen under the owner lock so a normal
        # publication does not rescan and reparse the complete manifest
        # directory.  The index is deliberately rebuilt after an unexpected
        # deletion failure; it is never durable state or field knowledge.
        manifest_cache: dict[str, Mapping[str, Any]] = getattr(
            self, "_compaction_manifest_cache", {}
        )
        manifest_paths: dict[str, Path] | None = getattr(
            self, "_compaction_manifest_paths", None
        )
        if manifest_paths is None:
            manifest_paths = {
                path.name: path
                for path in self.manifests.iterdir()
                if path.is_file()
            }
            self._compaction_manifest_paths = manifest_paths
            self._compaction_manifest_cache = manifest_cache
        entries: list[tuple[int, Path, Mapping[str, Any]]] = []
        for name, path in tuple(manifest_paths.items()):
            if not path.is_file():
                manifest_paths.pop(name, None)
                manifest_cache.pop(name, None)
                continue
            manifest = manifest_cache.get(name)
            if manifest is None:
                try:
                    manifest = _canonical_read(path)
                    generation = _integer(manifest.get("generation"), "manifest generation")
                except (FieldIntelligenceError, OSError, ValueError, TypeError):
                    continue
                manifest_cache[name] = manifest
            else:
                generation = _integer(manifest.get("generation"), "manifest generation")
            entries.append((generation, path, manifest))
        computational_count = sum(
            row[2].get("transition", {}).get("kind") in _COMPUTATIONAL_TRANSITIONS for row in entries
        )
        if computational_count + 1 <= self.limits.max_history_entries:
            return
        entries.sort(key=lambda item: (item[0], item[1].name))
        tail_count = max(1, self.limits.max_history_entries // 2)
        anchor = entries[-tail_count]
        floor = self._history_floor()
        protected_operations = {
            f"proposal:{row.operation_id}"
            for row in successor.predictions
            if row.operation_id is not None
        }
        removed = [item for item in entries if item[0] < anchor[0]]
        tombstones = list(floor["discarded_operation_ids"])
        watermarks = dict(floor["watermarks"])
        deletions: list[tuple[Path, str | None]] = []
        for _, path, manifest in removed:
            operation_id = manifest.get("operation_id")
            # Non-advance transitions remain addressable for exact evidence,
            # effect, and pending-operation replay; only computational history
            # is eligible for floor compaction.
            transition_kind = manifest.get("transition", {}).get("kind")
            if operation_id in protected_operations or transition_kind not in _COMPUTATIONAL_TRANSITIONS:
                continue
            if isinstance(operation_id, str):
                producer, separator, sequence_text = operation_id.rpartition(":")
                if separator and producer and sequence_text.isascii() and sequence_text.isdigit():
                    watermarks[producer] = max(
                        int(watermarks.get(producer, -1)), int(sequence_text)
                    )
                else:
                    tombstones.append(operation_id)
            deletions.append((path, operation_id if isinstance(operation_id, str) else None))
        tombstones = list(dict.fromkeys(tombstones))
        if len(tombstones) + len(watermarks) > self.limits.max_history_entries * 4:
            raise FieldIntelligenceError(
                "HISTORY_CAPACITY",
                "replay identities are full; recurring producers must use monotonic producer:sequence IDs",
            )
        # Publish the floor before removing anything.  A crash after this
        # point leaves a conservative floor (and therefore replay rejection),
        # whereas deleting first could leave CURRENT pointing below a missing
        # anchor.
        _atomic_write(
            self.history_floor_path,
            canonical_json_bytes(
                {
                    "discarded_operation_ids": tombstones,
                    "floor_generation": anchor[0],
                    "floor_manifest_sha256": anchor[1].name,
                    "schema": "cassifi.field-history-floor.v1",
                    "watermarks": watermarks,
                }
            ),
        )
        try:
            for path, operation_id in deletions:
                # Remove the replay pointer first: a crash can then only
                # reject an old operation through the already-published floor,
                # never replay it.
                if operation_id is not None:
                    self._operation_path(operation_id).unlink(missing_ok=True)
                path.unlink(missing_ok=True)
                manifest_paths.pop(path.name, None)
                manifest_cache.pop(path.name, None)
        except BaseException:
            # A partially completed deletion must not leave stale disposable
            # metadata in use by the next publication in this process.
            self._compaction_manifest_paths = None
            self._compaction_manifest_cache = {}
            raise
        # Roots include retained exact-evidence/effect history and staged
        # publications. Collect only unreachable content-addressed field pages.
        reachable: set[str] = set()
        for name, path in tuple(manifest_paths.items()):
            if not path.is_file():
                manifest_paths.pop(name, None)
                manifest_cache.pop(name, None)
                continue
            manifest = manifest_cache.get(name)
            if manifest is None:
                # Preserve the historical fail-closed behavior for malformed
                # manifests that were not eligible for the fast-path cache.
                manifest = _canonical_read(path)
            descriptor_sha = _digest(manifest["state_descriptor_sha256"], "state descriptor")
            descriptor = _canonical_read(self.objects / descriptor_sha)
            reachable.add(descriptor_sha)
            reachable.update(descriptor["pages"])
        for path in self.objects.iterdir():
            if path.is_file() and path.name not in reachable:
                path.unlink()

    def _load_state(self, manifest: Mapping[str, Any]) -> AtlasState:
        state = self._hydrate_descriptor(manifest["state_descriptor_sha256"])
        if (
            state.state_sha256 != manifest["state_sha256"]
            or state.generation != manifest["generation"]
            or state.revocation_generation != manifest["revocation_generation"]
        ):
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT", "checkpoint manifest and field state disagree"
            )
        return state

    def _operation_path(self, operation_id: str) -> Path:
        return self.operations / hashlib.sha256(operation_id.encode("utf-8")).hexdigest()

    def _validate_operation_record(
        self,
        operation_id: str,
        record: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        try:
            required = {
                "manifest_sha256",
                "operation_id",
                "parent_manifest_sha256",
                "semantic_sha256",
            }
            if set(record) != required:
                raise ValueError("operation record schema is invalid")
            if (
                _identifier(record["operation_id"], "record operation_id")
                != operation_id
            ):
                raise ValueError("operation record identity differs")
            manifest_sha256 = _digest(
                record["manifest_sha256"],
                "operation manifest",
            )
            parent_manifest_sha256 = _digest(
                record["parent_manifest_sha256"],
                "operation parent manifest",
            )
            semantic_sha256 = _digest(
                record["semantic_sha256"],
                "operation semantic identity",
            )
            manifest = self._manifest(manifest_sha256)
            transition = manifest["transition"]
            if not isinstance(transition, Mapping):
                raise TypeError("operation transition must be an object")
            manifest_event_id = manifest["event_id"]
            if manifest_event_id is not None:
                _digest(manifest_event_id, "operation event identity")
            _digest(manifest["state_sha256"], "operation state identity")
            _integer(manifest["generation"], "operation generation")
            manifest_operation_id = _identifier(
                manifest["operation_id"],
                "manifest operation_id",
            )
            manifest_parent = manifest["parent_manifest_sha256"]
            if transition.get("kind") == "migrate-v1":
                parent_matches = (
                    operation_id == "migrate-v1"
                    and manifest_parent is None
                    and _digest(
                        transition["source_manifest_sha256"],
                        "migration source manifest",
                    )
                    == parent_manifest_sha256
                )
            else:
                parent_matches = (
                    _digest(
                        manifest_parent,
                        "manifest parent identity",
                    )
                    == parent_manifest_sha256
                )
            if (
                manifest_operation_id != operation_id
                or not parent_matches
                or semantic_sha256
                != sha256_value(
                    {
                        "event_id": manifest_event_id,
                        "state_sha256": manifest["state_sha256"],
                        "transition": dict(transition),
                    }
                )
            ):
                raise ValueError("operation record and manifest differ")
            return manifest
        except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "operation replay pointer is invalid",
                details={"operation_id": operation_id},
            ) from exc

    def _validate_operation_records(self) -> None:
        for path in sorted(self.operations.iterdir()):
            if not path.is_file():
                raise FieldIntelligenceError(
                    "CHECKPOINT_CORRUPT",
                    "operation replay pointer is not a file",
                )
            try:
                _digest(path.name, "operation replay filename")
                record = _canonical_read(path)
                operation_id = _identifier(
                    record.get("operation_id"),
                    "record operation_id",
                )
                if self._operation_path(operation_id) != path:
                    raise ValueError(
                        "operation replay filename differs"
                    )
                self._validate_operation_record(
                    operation_id,
                    record,
                )
            except (
                FieldIntelligenceError,
                KeyError,
                OSError,
                TypeError,
                ValueError,
            ) as exc:
                raise FieldIntelligenceError(
                    "CHECKPOINT_CORRUPT",
                    "operation replay closure cannot be decoded safely",
                    details={"path": path.name},
                ) from exc

    def _committed_operation(
        self,
        operation_id: str,
    ) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
        operation_id = _identifier(operation_id, "operation_id")
        path = self._operation_path(operation_id)
        if not path.exists():
            return None
        if not path.is_file():
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "operation replay pointer is not a file",
                details={"operation_id": operation_id},
            )
        try:
            record = _canonical_read(path)
        except FieldIntelligenceError as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "operation replay pointer is unreadable",
                details={"operation_id": operation_id},
            ) from exc
        manifest = self._validate_operation_record(operation_id, record)
        return record, manifest

    def _stage_path(self, operation_id: str) -> Path:
        return self.staging / hashlib.sha256(operation_id.encode("utf-8")).hexdigest()

    def _promote_stage(self, path: Path, operation_id: str) -> None:
        # The stage already contains the durable replay identity.  Move those
        # bytes after CURRENT is durable instead of rewriting and flushing them.
        os.replace(path, self._operation_path(operation_id))
        _fsync_directory(self.operations)
        _fsync_directory(self.staging)

    def recover(self) -> None:
        with self._lock:
            # Recovery may promote a staged manifest that is newer than a
            # previously primed compaction index.  Rebuild that disposable
            # metadata before any later history/GC pass.
            self._compaction_manifest_paths = None
            self._compaction_manifest_cache = {}
            try:
                current_text = self.current_path.read_text(encoding="ascii")
                current_sha = _digest(current_text.removesuffix("\n"), "CURRENT")
            except (OSError, UnicodeDecodeError) as exc:
                raise FieldIntelligenceError("PERSISTENCE_CORRUPT", "CURRENT is unreadable") from exc
            current = _canonical_read(self.manifests / current_sha)
            if hashlib.sha256(canonical_json_bytes(current)).hexdigest() != current_sha:
                raise FieldIntelligenceError("PERSISTENCE_CORRUPT", "current manifest identity is invalid")
            for path in sorted(self.staging.iterdir()):
                if not path.is_file():
                    continue
                staged = _canonical_read(path)
                try:
                    operation_id = _identifier(
                        staged.get("operation_id"),
                        "staged operation_id",
                    )
                    if path != self._stage_path(operation_id):
                        raise FieldIntelligenceError(
                            "CHECKPOINT_CORRUPT",
                            "staged operation path differs from its identity",
                        )
                    manifest = self._validate_operation_record(
                        operation_id,
                        staged,
                    )
                except FieldIntelligenceError as exc:
                    self._quarantine(
                        "STAGE_INVALID",
                        {"cause": exc.code, "path": path.name},
                    )
                manifest_sha = staged["manifest_sha256"]
                if current.get("schema") == "cassifi.field-atlas-checkpoint.v1" and (
                    manifest["transition"].get("kind") != "migrate-v1"
                    or manifest["transition"].get("source_manifest_sha256") != current_sha
                ):
                    raise FieldIntelligenceError("MIGRATION_REQUIRED", "v1 publication requires explicit migration")
                if current_sha == staged["parent_manifest_sha256"]:
                    _atomic_write(self.current_path, (manifest_sha + "\n").encode("ascii"))
                    current_sha = manifest_sha
                elif current_sha != manifest_sha:
                    self._quarantine(
                        "LINEAGE_COMMIT_CONFLICT",
                        {
                            "current": current_sha,
                            "staged_parent": staged["parent_manifest_sha256"],
                        },
                    )
                self._promote_stage(path, staged["operation_id"])
            self._load_current()


    def commit(
        self,
        *,
        operation_id: str,
        successor: AtlasState,
        event_id: str | None,
        transition: Mapping[str, Any],
    ) -> CheckpointReceipt:
        with self._lock:
            _identifier(operation_id, "operation_id")
            if event_id is not None:
                _digest(event_id, "event_id")
            encoded = successor.encode()
            encoded_bytes = encoded.encode("utf-8") if isinstance(encoded, str) else encoded
            if len(encoded_bytes) > self.limits.max_state_bytes:
                raise FieldIntelligenceError(
                    "STATE_CAPACITY",
                    "field state exceeds the configured byte limit",
                    details={"bytes": len(encoded_bytes), "limit": self.limits.max_state_bytes},
                )
            semantic = sha256_value(
                {
                    "event_id": event_id,
                    "state_sha256": successor.state_sha256,
                    "transition": dict(transition),
                }
            )
            committed = self._committed_operation(operation_id)
            if committed is not None:
                existing, manifest = committed
                if existing["semantic_sha256"] != semantic:
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "operation identity is bound to a different field transition",
                    )
                manifest_sha = existing["manifest_sha256"]
                return CheckpointReceipt(
                    operation_id=operation_id,
                    manifest_sha256=manifest_sha,
                    state_sha256=manifest["state_sha256"],
                    predecessor_manifest_sha256=existing["parent_manifest_sha256"],
                    generation=manifest["generation"],
                    replayed=True,
                )
            if self.operation_compacted(operation_id):
                raise FieldIntelligenceError(
                    "REPLAY_FLOOR",
                    "operation was discarded behind the retained history floor",
                )
            current_sha, current = self._load_current()
            if successor.generation <= current["generation"]:
                raise FieldIntelligenceError(
                    "LINEAGE_CONFLICT", "successor generation does not advance the field"
                )
            fence = self.revocation_fence()
            if successor.revocation_generation != fence["generation"]:
                raise FieldIntelligenceError(
                    "REVOCATION_FENCE",
                    "successor does not reference the current revocation generation",
                    details={
                        "field": successor.revocation_generation,
                        "fence": fence["generation"],
                    },
                )
            self._compact_history_for(successor)
            descriptor_sha, state_sha = self._state_descriptor(successor)
            manifest = {
                "event_id": event_id,
                "generation": successor.generation,
                "operation_id": operation_id,
                "parent_manifest_sha256": current_sha,
                "revocation_generation": successor.revocation_generation,
                "schema": CHECKPOINT_SCHEMA,
                "state_descriptor_sha256": descriptor_sha,
                "state_sha256": state_sha,
                "transition": json.loads(canonical_json_bytes(dict(transition))),
            }
            manifest_sha = _put_object(self.manifests, canonical_json_bytes(manifest))
            # Keep the disposable compaction index in sync with publications
            # made after its initial directory snapshot.  Other integrity
            # paths continue to read and hash manifests from disk.
            manifest_paths = getattr(self, "_compaction_manifest_paths", None)
            if manifest_paths is not None:
                manifest_paths[manifest_sha] = self.manifests / manifest_sha
                self._compaction_manifest_cache[manifest_sha] = manifest
            staged = {
                "manifest_sha256": manifest_sha,
                "operation_id": operation_id,
                "parent_manifest_sha256": current_sha,
                "semantic_sha256": semantic,
            }
            stage_path = self._stage_path(operation_id)
            _atomic_write(stage_path, canonical_json_bytes(staged))
            _atomic_write(self.current_path, (manifest_sha + "\n").encode("ascii"))
            self._promote_stage(stage_path, operation_id)
            self.current_manifest_sha256 = manifest_sha
            self.current_manifest = manifest
            self.state = successor
            return CheckpointReceipt(
                operation_id=operation_id,
                manifest_sha256=manifest_sha,
                state_sha256=state_sha,
                predecessor_manifest_sha256=current_sha,
                generation=successor.generation,
                replayed=False,
            )

    def refresh(self) -> AtlasState:
        with self._lock:
            self.current_manifest_sha256, self.current_manifest = self._load_current()
            self.state = self._load_state(self.current_manifest)
            self._validate_history_chain(self.current_manifest)
            return self.state
    def _retained_manifest(self, manifest_sha256: str) -> Mapping[str, Any]:
        manifest_sha256 = _digest(manifest_sha256, "manifest_sha256")
        manifest = self._manifest(manifest_sha256)
        floor = self._history_floor()
        if int(manifest["generation"]) < int(floor["floor_generation"]):
            raise FieldIntelligenceError(
                "STALE_HISTORY",
                "manifest was discarded behind the retained history floor",
            )
        fence = self.revocation_fence()
        if manifest["revocation_generation"] < fence["generation"]:
            raise FieldIntelligenceError(
                "STALE_REVOCATION",
                "old field generation cannot bypass a newer revocation boundary",
            )
        return manifest

    def load_version(self, manifest_sha256: str) -> AtlasState:
        return self._load_state(self._retained_manifest(manifest_sha256))

    def export_bundle(self, manifest_sha256: str | None = None) -> bytes:
        """Export one verified checkpoint and its complete reachable page closure."""
        with self._lock:
            selected = self.current_manifest_sha256 if manifest_sha256 is None else _digest(
                manifest_sha256, "manifest_sha256"
            )
            manifest = self._retained_manifest(selected)
            state = self._load_state(manifest)
            state_bundle = state.encode_bundle()
            payload = {
                "manifest": dict(manifest),
                "manifest_sha256": selected,
                "schema": "cassifi.field-atlas-checkpoint-bundle.v2",
                "state_bundle_base64": base64.b64encode(state_bundle).decode("ascii"),
            }
            encoded = canonical_json_bytes(payload)
            if len(encoded) > self.limits.max_state_bytes:
                raise FieldIntelligenceError("STATE_CAPACITY", "standalone checkpoint bundle exceeds capacity")
            return encoded

    @classmethod
    def migrate_v1(
        cls, root: Path, *, limits: CapacityLimits = CapacityLimits(),
        evidence: ExactEvidenceStore | None = None,
    ) -> Mapping[str, Any]:
        """Explicitly migrate an on-disk v1 head; normal opening never does this."""
        root = Path(root)
        current_path = root / "CURRENT"
        try:
            current_text = current_path.read_text(encoding="ascii")
            old_manifest_sha = _digest(current_text[:-1], "CURRENT") if current_text.endswith("\n") else ""
            old_manifest = _canonical_read(root / "manifests" / old_manifest_sha)
        except (OSError, FieldIntelligenceError) as exc:
            raise FieldIntelligenceError("MIGRATION_REQUIRED", "v1 checkpoint head is unavailable") from exc
        if old_manifest.get("schema") != "cassifi.field-atlas-checkpoint.v1":
            raise FieldIntelligenceError("MIGRATION_NOT_REQUIRED", "checkpoint head is not v1")
        if hashlib.sha256(canonical_json_bytes(old_manifest)).hexdigest() != old_manifest_sha:
            raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 manifest identity is invalid")
        descriptor_sha = _digest(old_manifest["state_descriptor_sha256"], "state descriptor")
        descriptor_path = root / "objects" / descriptor_sha
        try:
            descriptor_bytes = descriptor_path.read_bytes()
            descriptor = json.loads(descriptor_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 state descriptor is unreadable") from exc
        if hashlib.sha256(descriptor_bytes).hexdigest() != descriptor_sha:
            raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 descriptor identity is invalid")
        closure_bytes = len(descriptor_bytes)
        if closure_bytes > limits.max_state_bytes:
            raise FieldIntelligenceError("STATE_CAPACITY", "v1 checkpoint closure exceeds capacity")
        if descriptor.get("schema") != "cassifi.field-atlas-root.v1":
            raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 state descriptor schema is invalid")
        pages = descriptor.get("pages")
        if not isinstance(pages, list):
            raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 state page list is invalid")
        seen_pages: set[str] = set()
        for page_ref in pages:
            page_sha = _digest(page_ref, "numeric page object")
            try:
                page = (root / "objects" / page_sha).read_bytes()
            except OSError as exc:
                raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 state page is unavailable") from exc
            if hashlib.sha256(page).hexdigest() != page_sha:
                raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 state page identity is invalid")
            if page_sha not in seen_pages:
                seen_pages.add(page_sha)
                closure_bytes += len(page)
                if closure_bytes > limits.max_state_bytes:
                    raise FieldIntelligenceError("STATE_CAPACITY", "v1 checkpoint closure exceeds capacity")
        payload = descriptor.get("state")
        if not isinstance(payload, dict):
            raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 state payload is invalid")
        payload = json.loads(canonical_json_bytes(payload).decode("utf-8"))
        for chart in payload.get("charts", []):
            reference = chart.get("numeric_field")
            if not isinstance(reference, dict):
                raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 chart page reference is invalid")
            page_sha = _digest(reference.get("object_sha256"), "numeric page object")
            try:
                page = (root / "objects" / page_sha).read_bytes()
                chart["numeric_field"] = json.loads(page.decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 chart page is unavailable") from exc
            if hashlib.sha256(canonical_json_bytes(chart["numeric_field"])).hexdigest() != page_sha:
                raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 chart page identity is invalid")
            if page_sha not in seen_pages:
                seen_pages.add(page_sha)
                closure_bytes += len(page)
                if closure_bytes > limits.max_state_bytes:
                    raise FieldIntelligenceError("STATE_CAPACITY", "v1 checkpoint closure exceeds capacity")
        legacy_state_sha = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        if descriptor.get("state_sha256") != legacy_state_sha or old_manifest.get("state_sha256") != legacy_state_sha:
            raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 state identity is invalid")
        if (
            payload.get("generation") != old_manifest.get("generation")
            or payload.get("revocation_generation") != old_manifest.get("revocation_generation")
        ):
            raise FieldIntelligenceError("MIGRATION_CORRUPT", "v1 state and manifest lineage disagree")
        state = AtlasState.migrate_v1(canonical_json_bytes(payload))
        helper = cls.__new__(cls)
        helper.root = root
        helper.limits = limits
        helper.objects = root / "objects"
        helper.manifests = root / "manifests"
        helper.staging = root / "staging"
        helper.operations = root / "operations"
        helper.current_path = current_path
        helper.revocation_path = root / "REVOCATION"
        helper.history_floor_path = root / "HISTORY_FLOOR"
        helper.quarantine_path = root / "QUARANTINE"
        if helper.quarantine_path.exists():
            raise FieldIntelligenceError("STATE_QUARANTINED", "quarantined state cannot be migrated")
        fence = helper.revocation_fence()
        if fence["generation"] != state.revocation_generation:
            raise FieldIntelligenceError("MIGRATION_PENDING", "complete the v1 revocation before migration")
        if helper.staging.exists() and any(helper.staging.iterdir()):
            raise FieldIntelligenceError("MIGRATION_PENDING", "complete the staged v1 publication before migration")
        if evidence is not None:
            active = evidence.active_revision_ids()
            if any(not chart.active_source_revisions().issubset(active) for chart in state.charts):
                raise FieldIntelligenceError("MIGRATION_CORRUPT", "learned support refers to unavailable evidence")
        _atomic_write(
            helper.history_floor_path,
            canonical_json_bytes(
                {
                    "discarded_operation_ids": [],
                    "floor_generation": 0,
                    "floor_manifest_sha256": None,
                    "schema": "cassifi.field-history-floor.v1",
                    "watermarks": {},
                }
            ),
        )
        for directory in (helper.objects, helper.manifests, helper.staging, helper.operations):
            directory.mkdir(parents=True, exist_ok=True)
        descriptor_sha, state_sha = helper._state_descriptor(state)
        manifest = {
            "event_id": None,
            "generation": state.generation,
            "operation_id": "migrate-v1",
            "parent_manifest_sha256": None,
            "revocation_generation": state.revocation_generation,
            "schema": CHECKPOINT_SCHEMA,
            "state_descriptor_sha256": descriptor_sha,
            "state_sha256": state_sha,
            "transition": {"kind": "migrate-v1", "source_manifest_sha256": old_manifest_sha},
        }
        new_manifest_sha = _put_object(helper.manifests, canonical_json_bytes(manifest))
        # Verify the complete new closure before making it recoverably publishable.
        helper._load_state(manifest)
        semantic = sha256_value({
            "event_id": None, "state_sha256": state_sha, "transition": manifest["transition"],
        })
        stage_path = helper._stage_path("migrate-v1")
        _atomic_write(stage_path, canonical_json_bytes({
            "manifest_sha256": new_manifest_sha,
            "operation_id": "migrate-v1",
            "parent_manifest_sha256": old_manifest_sha,
            "semantic_sha256": semantic,
        }))
        _atomic_write(current_path, (new_manifest_sha + "\n").encode("ascii"))
        _atomic_write(helper._operation_path("migrate-v1"), canonical_json_bytes({
            "manifest_sha256": new_manifest_sha,
            "operation_id": "migrate-v1",
            "parent_manifest_sha256": old_manifest_sha,
            "semantic_sha256": semantic,
        }))
        stage_path.unlink()
        return {
            "manifest_sha256": new_manifest_sha,
            "state_sha256": state_sha,
            "source_manifest_sha256": old_manifest_sha,
            "schema": CHECKPOINT_SCHEMA,
        }


@dataclass(frozen=True, slots=True)
class AuthorityGrant:
    grant_id: str
    issuer: str
    generation: int
    operation: str
    target: str
    scope: str
    one_use: bool = True
    schema: str = AUTHORITY_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != AUTHORITY_SCHEMA:
            raise FieldIntelligenceError("AUTHORITY_INVALID", "authority schema is incompatible")
        for name in ("grant_id", "issuer", "operation", "target", "scope"):
            _identifier(getattr(self, name), name)
        _integer(self.generation, "authority generation", minimum=0)
        if not isinstance(self.one_use, bool):
            raise FieldIntelligenceError(
                "AUTHORITY_INVALID",
                "authority one_use must be a boolean",
            )

    def permits(
        self, *, operation: str, target: str, scope: str, generation: int
    ) -> bool:
        return (
            self.operation == operation
            and self.target == target
            and self.scope == scope
            and self.generation == generation
        )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "generation": self.generation,
            "grant_id": self.grant_id,
            "issuer": self.issuer,
            "one_use": self.one_use,
            "operation": self.operation,
            "schema": self.schema,
            "scope": self.scope,
            "target": self.target,
        }
    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AuthorityGrant:
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class WorldAcknowledgment:
    acknowledgment_id: str
    operation_id: str
    status: str
    observed_values: Mapping[str, float]
    context: Mapping[str, Any]
    source_content: bytes

    def __post_init__(self) -> None:
        _identifier(self.acknowledgment_id, "acknowledgment_id")
        _identifier(self.operation_id, "operation_id")
        _identifier(self.status, "acknowledgment status")
        if self.status not in {"succeeded", "failed", "unknown"}:
            raise FieldIntelligenceError(
                "INVALID_ACKNOWLEDGMENT",
                "world acknowledgment status is unsupported",
            )
        if not isinstance(self.source_content, bytes):
            raise FieldIntelligenceError(
                "INVALID_ACKNOWLEDGMENT",
                "acknowledgment source must be exact bytes",
            )
        if not isinstance(self.observed_values, Mapping):
            raise FieldIntelligenceError(
                "INVALID_ACKNOWLEDGMENT",
                "acknowledgment values must be an object",
            )
        normalized_values = {
            _identifier(name, "acknowledgment variable"): _finite(
                value,
                "acknowledgment value",
            )
            for name, value in self.observed_values.items()
        }
        object.__setattr__(
            self,
            "observed_values",
            normalized_values,
        )
        if not isinstance(self.context, Mapping):
            raise FieldIntelligenceError(
                "INVALID_ACKNOWLEDGMENT",
                "acknowledgment context must be an object",
            )
        try:
            normalized_context = json.loads(
                canonical_json_bytes(dict(self.context))
            )
        except Exception as exc:
            raise FieldIntelligenceError(
                "INVALID_ACKNOWLEDGMENT",
                "acknowledgment context must be canonical JSON",
            ) from exc
        object.__setattr__(self, "context", normalized_context)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "acknowledgment_id": self.acknowledgment_id,
            "context": dict(self.context),
            "observed_values": dict(self.observed_values),
            "operation_id": self.operation_id,
            "source_content_base64": base64.b64encode(self.source_content).decode(
                "ascii"
            ),
            "status": self.status,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> WorldAcknowledgment:
        try:
            if not isinstance(value, Mapping):
                raise TypeError("world acknowledgment must be an object")
            row = dict(value)
            required = {
                "acknowledgment_id",
                "context",
                "observed_values",
                "operation_id",
                "source_content_base64",
                "status",
            }
            if set(row) != required:
                raise ValueError(
                    "world acknowledgment schema is invalid"
                )
            row["source_content"] = base64.b64decode(
                row.pop("source_content_base64"),
                validate=True,
            )
            return cls(**row)
        except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "world acknowledgment cannot be decoded safely",
            ) from exc


class WorldAdapter(Protocol):
    adapter_id: str

    def bind_durable_journal(self, path: Path) -> None: ...

    def execute_once(
        self, *, operation_id: str, action: str, target: str, payload: Mapping[str, Any]
    ) -> WorldAcknowledgment: ...

    def resolve(self, operation_id: str) -> WorldAcknowledgment | None: ...


class DeterministicWorldAdapter:
    """Controlled adapter with a durable, fail-closed operation journal."""

    def __init__(
        self,
        transition: Callable[[str, str, Mapping[str, Any]], WorldAcknowledgment],
        *,
        adapter_id: str = "deterministic-world",
    ) -> None:
        self.transition = transition
        self.adapter_id = _identifier(adapter_id, "world adapter_id")
        self.execute_count = 0
        self._journal: Path | None = None
        self._lock = threading.RLock()

    def bind_durable_journal(self, path: Path) -> None:
        with self._lock:
            journal = Path(path)
            if self._journal is not None:
                if self._journal != journal:
                    raise FieldIntelligenceError(
                        "ADAPTER_DURABILITY",
                        "world adapter is already bound to another durable journal",
                    )
                return
            journal.mkdir(parents=True, exist_ok=True)
            self._journal = journal
            try:
                self._validate_journal()
            except BaseException:
                self._journal = None
                raise

    def _operation_path(self, operation_id: str) -> Path:
        _identifier(operation_id, "world operation_id")
        if self._journal is None:
            raise FieldIntelligenceError(
                "ADAPTER_DURABILITY",
                "world adapter must be bound to a durable journal before use",
            )
        return self._journal / hashlib.sha256(operation_id.encode("utf-8")).hexdigest()

    def _validate_journal(self) -> None:
        assert self._journal is not None
        for path in sorted(self._journal.iterdir()):
            try:
                if not path.is_file():
                    raise ValueError(
                        "world adapter journal entry is not a file"
                    )
                _digest(path.name, "world journal filename")
                record = _canonical_read(path)
                request = record.get("request")
                if not isinstance(request, Mapping):
                    raise TypeError(
                        "world adapter request is unavailable"
                    )
                operation_id = _identifier(
                    request.get("operation_id"),
                    "world operation_id",
                )
                if self._operation_path(operation_id) != path:
                    raise ValueError(
                        "world adapter journal filename differs"
                    )
                self._read_record(operation_id)
            except (
                FieldIntelligenceError,
                KeyError,
                OSError,
                TypeError,
                ValueError,
            ) as exc:
                raise FieldIntelligenceError(
                    "PERSISTENCE_CORRUPT",
                    "world adapter journal closure cannot be decoded safely",
                    details={"path": path.name},
                ) from exc

    @staticmethod
    def _request(
        operation_id: str,
        action: str,
        target: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        operation_id = _identifier(
            operation_id,
            "world operation_id",
        )
        action = _identifier(action, "world action")
        target = _identifier(target, "world target")
        if not isinstance(payload, Mapping):
            raise FieldIntelligenceError(
                "INVALID_REQUEST",
                "world effect payload must be an object",
            )
        try:
            normalized_payload = json.loads(
                canonical_json_bytes(dict(payload))
            )
        except Exception as exc:
            raise FieldIntelligenceError(
                "INVALID_REQUEST",
                "world effect payload must be canonical JSON",
            ) from exc
        return {
            "action": action,
            "operation_id": operation_id,
            "payload": normalized_payload,
            "target": target,
        }

    def _read_record(
        self,
        operation_id: str,
    ) -> tuple[Mapping[str, Any], WorldAcknowledgment | None] | None:
        path = self._operation_path(operation_id)
        if not path.exists():
            return None
        if not path.is_file():
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "world adapter journal record is not a file",
                details={"operation_id": operation_id},
            )
        try:
            record = _canonical_read(path)
            required = {
                "acknowledgment",
                "acknowledgment_sha256",
                "request",
                "request_sha256",
                "schema",
                "status",
            }
            if (
                set(record) != required
                or record["schema"] != WORLD_ADAPTER_JOURNAL_SCHEMA
                or record["status"]
                not in {"executing", "acknowledged"}
                or not isinstance(record["request"], Mapping)
            ):
                raise ValueError(
                    "world adapter journal schema is invalid"
                )
            raw_request = record["request"]
            if (
                set(raw_request)
                != {"action", "operation_id", "payload", "target"}
            ):
                raise ValueError(
                    "world adapter request schema is invalid"
                )
            request = self._request(
                raw_request["operation_id"],
                raw_request["action"],
                raw_request["target"],
                raw_request["payload"],
            )
            if (
                request["operation_id"] != operation_id
                or request != raw_request
                or _digest(
                    record["request_sha256"],
                    "world request identity",
                )
                != sha256_value(request)
            ):
                raise ValueError(
                    "world adapter request identity is invalid"
                )
            if record["status"] == "executing":
                if (
                    record["acknowledgment"] is not None
                    or record["acknowledgment_sha256"] is not None
                ):
                    raise ValueError(
                        "executing world effect contains an acknowledgment"
                    )
                return record, None
            raw_acknowledgment = record["acknowledgment"]
            if not isinstance(raw_acknowledgment, Mapping):
                raise TypeError(
                    "world adapter acknowledgment is unavailable"
                )
            if (
                _digest(
                    record["acknowledgment_sha256"],
                    "world acknowledgment identity",
                )
                != sha256_value(dict(raw_acknowledgment))
            ):
                raise ValueError(
                    "world acknowledgment identity is invalid"
                )
            acknowledgment = WorldAcknowledgment.from_dict(
                raw_acknowledgment
            )
            if acknowledgment.operation_id != operation_id:
                raise ValueError(
                    "world acknowledgment operation identity differs"
                )
            return record, acknowledgment
        except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "world adapter journal record cannot be decoded safely",
                details={"operation_id": operation_id},
            ) from exc

    def resolve(self, operation_id: str) -> WorldAcknowledgment | None:
        with self._lock:
            loaded = self._read_record(operation_id)
            return None if loaded is None else loaded[1]

    def execute_once(
        self,
        *,
        operation_id: str,
        action: str,
        target: str,
        payload: Mapping[str, Any],
    ) -> WorldAcknowledgment:
        with self._lock:
            request = self._request(
                operation_id,
                action,
                target,
                payload,
            )
            path = self._operation_path(operation_id)
            loaded = self._read_record(operation_id)
            if loaded is not None:
                record, existing = loaded
                if record["request"] != request:
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "world operation identity has different effect semantics",
                    )
                if existing is not None:
                    return existing
                raise FieldIntelligenceError(
                    "EFFECT_OUTCOME_UNKNOWN",
                    "world effect began without a durable acknowledgment; refusing replay",
                )
            request_sha256 = sha256_value(request)
            _atomic_write(
                path,
                canonical_json_bytes(
                    {
                        "acknowledgment": None,
                        "acknowledgment_sha256": None,
                        "request": request,
                        "request_sha256": request_sha256,
                        "schema": WORLD_ADAPTER_JOURNAL_SCHEMA,
                        "status": "executing",
                    }
                ),
            )
            result = self.transition(
                request["action"],
                request["target"],
                request["payload"],
            )
            if not isinstance(result, WorldAcknowledgment):
                raise FieldIntelligenceError(
                    "INVALID_ACKNOWLEDGMENT",
                    "world adapter returned an invalid acknowledgment",
                )
            if result.operation_id != operation_id:
                raise FieldIntelligenceError(
                    "INVALID_ACKNOWLEDGMENT",
                    "world acknowledgment operation identity differs",
                )
            acknowledgment = result.as_dict()
            _atomic_write(
                path,
                canonical_json_bytes(
                    {
                        "acknowledgment": acknowledgment,
                        "acknowledgment_sha256": sha256_value(
                            acknowledgment
                        ),
                        "request": request,
                        "request_sha256": request_sha256,
                        "schema": WORLD_ADAPTER_JOURNAL_SCHEMA,
                        "status": "acknowledged",
                    }
                ),
            )
            self.execute_count += 1
            return result


class FieldIntelligenceOwner:
    """Sole publisher for field, evidence, plans, and predictive episodes."""

    @classmethod
    def migrate_v1(
        cls,
        data_home: Path,
        *,
        limits: CapacityLimits | None = None,
        authority_generation: int = 0,
    ) -> Mapping[str, Any]:
        del authority_generation
        root = Path(data_home)
        root.mkdir(parents=True, exist_ok=True)
        process_lock = OwnerProcessLock(root / "OWNER.lock")
        try:
            effective_limits = limits or CapacityLimits()
            if not (root / "evidence" / "index.json").is_file():
                raise FieldIntelligenceError("MIGRATION_CORRUPT", "legacy evidence index is missing")
            evidence = ExactEvidenceStore(root / "evidence", limits=effective_limits)
            revisions = frozenset(evidence.all_revision_ids())
            active = evidence.active_revision_ids()
            for revision in revisions:
                source = evidence.source(revision)
                if source.revision_id != revision or ((source.status == "active") != (revision in active)):
                    raise FieldIntelligenceError("MIGRATION_CORRUPT", "evidence source index disagrees")
                if source.status != "deleted":
                    try:
                        content = (evidence.blobs / source.object_sha256).read_bytes()
                    except OSError as exc:
                        raise FieldIntelligenceError("SOURCE_MISSING", "legacy source bytes are missing") from exc
                    if (
                        len(content) != source.byte_length
                        or hashlib.sha256(content).hexdigest() != source.content_sha256
                        or source.content_sha256 != source.object_sha256
                    ):
                        raise FieldIntelligenceError("SOURCE_CORRUPT", "legacy source bytes failed integrity checks")
            for event_id in evidence.all_event_ids():
                event = evidence.event(event_id)
                if (
                    event.event_id != event_id
                    or event.source_revision_id not in revisions
                    or evidence.event_for_operation(event.operation_id) != event
                ):
                    raise FieldIntelligenceError("MIGRATION_CORRUPT", "evidence event index disagrees")
            return AtlasCheckpointStore.migrate_v1(
                root / "field", limits=effective_limits, evidence=evidence
            )
        finally:
            process_lock.close()

    def __init__(
        self,
        data_home: Path,
        *,
        limits: CapacityLimits | None = None,
        authority_generation: int = 0,
        initial_state: AtlasState | None = None,
    ) -> None:
        self.data_home = Path(data_home)
        self.data_home.mkdir(parents=True, exist_ok=True)
        self.pending_path = self.data_home / "pending"
        self.pending_path.mkdir(parents=True, exist_ok=True)
        self.pending_failures_path = self.data_home / "pending-failures"
        self.pending_failures_path.mkdir(parents=True, exist_ok=True)
        self._process_lock = OwnerProcessLock(self.data_home / "OWNER.lock")
        try:
            self.limits = limits or CapacityLimits()
            self.atlas = FieldAtlas()
            self.cognition = FieldCognition(self.atlas)
            self.evidence = ExactEvidenceStore(self.data_home / "evidence", limits=self.limits)
            self.checkpoints = AtlasCheckpointStore(
                self.data_home / "field",
                limits=self.limits,
                initial_state=initial_state,
            )
            self.state = self.checkpoints.state
            self._lock = threading.RLock()
            self.authority_path = self.data_home / "authority-control.json"
            if not self.authority_path.exists():
                _atomic_write(
                    self.authority_path,
                    canonical_json_bytes(
                        {
                            "generation": authority_generation,
                            "schema": AUTHORITY_CONTROL_SCHEMA,
                            "used_grant_bindings": {},
                            "used_grant_ids": [],
                        }
                    ),
                )
            control = self._authority_control()
            if control["generation"] != authority_generation and self.state.generation == 0:
                raise FieldIntelligenceError(
                    "AUTHORITY_CONFLICT", "configured authority generation differs from durable state"
                )
            self._recover_revocation()
            self._recover_pending_operations()
            self._recover_effect_grant_bindings()
        except BaseException:
            try:
                self._process_lock.close()
            except BaseException:
                pass
            raise

    def close(self) -> None:
        self._process_lock.close()

    def __enter__(self) -> FieldIntelligenceOwner:
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        del _exc_type, _exc, _traceback
        self.close()

    def __del__(self) -> None:
        process_lock = getattr(self, "_process_lock", None)
        if process_lock is not None:
            try:
                process_lock.close()
            except Exception:
                pass

    def _pending_file(self, operation_id: str) -> Path:
        _identifier(operation_id, "operation_id")
        return self.pending_path / hashlib.sha256(
            operation_id.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _validate_pending_payload(
        *,
        kind: str,
        operation_id: str,
        payload: Mapping[str, Any],
        predecessor: Mapping[str, Any],
    ) -> None:
        expected_keys = _PENDING_PAYLOAD_KEYS.get(kind)
        if expected_keys is None or set(payload) != expected_keys:
            raise FieldIntelligenceError(
                "PENDING_OPERATION_CORRUPT",
                "pending owner operation payload has an incompatible shape",
                details={"kind": kind},
            )
        try:
            if kind == "observation":
                SourceInput.from_dict(payload["source"])
                if (
                    not isinstance(payload["context"], Mapping)
                    or not isinstance(payload["values"], Mapping)
                    or not isinstance(payload["derivation_roots"], list)
                ):
                    raise TypeError("observation payload containers are invalid")
                for name, value in payload["values"].items():
                    _identifier(name, "pending observation variable")
                    _finite(value, "pending observation value")
                if payload["epistemic_type"] not in {
                    "observed",
                    "asserted",
                    "derived",
                }:
                    raise ValueError("pending epistemic type is invalid")
                _identifier(payload["event_kind"], "pending event kind")
                weight = _finite(
                    payload["weight"],
                    "pending observation weight",
                    nonnegative=True,
                )
                if weight == 0.0:
                    raise ValueError("pending observation weight must be positive")
                for root in payload["derivation_roots"]:
                    _digest(root, "pending derivation root")
                targets = payload["target_chart_ids"]
                if targets is not None:
                    if not isinstance(targets, list):
                        raise TypeError("pending target charts must be a list")
                    for chart_id in targets:
                        _identifier(chart_id, "pending target chart")
            elif kind == "temporal-episode":
                source = SourceInput.from_dict(payload["source"])
                if not isinstance(payload["context"], Mapping):
                    raise TypeError("pending temporal context must be an object")
                _identifier(payload["memory_id"], "pending temporal memory")
                _integer(
                    payload["admitted_step_count"],
                    "pending admitted step count",
                    minimum=0,
                )
                _integer(
                    payload["evidence_tick"],
                    "pending evidence tick",
                    minimum=1,
                )
                for name in (
                    "event_id",
                    "predecessor_manifest_sha256",
                    "predecessor_state_sha256",
                    "source_revision_id",
                    "temporal_memory_sha256",
                ):
                    _digest(payload[name], f"pending {name}")
                for name in (
                    "expected_state_sha256",
                    "resonant_workspace_state_sha256",
                ):
                    value = payload[name]
                    if value is not None:
                        _digest(value, f"pending {name}")
                if source.revision_id != payload["source_revision_id"]:
                    raise ValueError("pending source revision identity differs")
                if (
                    payload["predecessor_manifest_sha256"]
                    != predecessor["manifest_sha256"]
                    or payload["predecessor_state_sha256"]
                    != predecessor["state_sha256"]
                    or payload["resonant_workspace_state_sha256"]
                    != predecessor["resonant_workspace_state_sha256"]
                    or payload["temporal_memory_sha256"]
                    != predecessor["temporal_memory_sha256"]
                    or payload["evidence_tick"]
                    != predecessor["logical_tick"] + 1
                ):
                    raise ValueError("pending temporal predecessor fields differ")
            elif kind == "computation-episode":
                SourceInput.from_dict(payload["source"])
                ResonantWorkspace.from_dict(payload["workspace"])
                for name in ("context", "feature_bindings", "outcomes"):
                    if not isinstance(payload[name], Mapping):
                        raise TypeError(f"pending {name} must be an object")
                targets = payload["target_chart_ids"]
                if not isinstance(targets, list):
                    raise TypeError("pending target charts must be a list")
                for chart_id in targets:
                    _identifier(chart_id, "pending target chart")
            else:
                acknowledgment = WorldAcknowledgment.from_dict(
                    payload["acknowledgment"]
                )
                _digest(payload["prediction_id"], "pending prediction")
                candidates = payload["attribution_candidates"]
                if not isinstance(candidates, list):
                    raise TypeError(
                        "pending attribution candidates must be a list"
                    )
                for candidate in candidates:
                    _identifier(candidate, "pending attribution candidate")
                targets = payload["learn_chart_ids"]
                if targets is not None:
                    if not isinstance(targets, list):
                        raise TypeError("pending learned charts must be a list")
                    for chart_id in targets:
                        _identifier(chart_id, "pending learned chart")
                if operation_id != f"ack:{acknowledgment.operation_id}":
                    raise ValueError(
                        "pending acknowledgment operation identity differs"
                    )
        except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "PENDING_OPERATION_CORRUPT",
                "pending owner operation payload cannot be recovered safely",
                details={"kind": kind},
            ) from exc

    def _read_pending(self, path: Path) -> Mapping[str, Any]:
        envelope = _canonical_read(path)
        if (
            set(envelope)
            != {"kind", "operation_id", "payload", "predecessor", "schema"}
            or envelope["schema"] != PENDING_OPERATION_SCHEMA
            or not isinstance(envelope["payload"], Mapping)
            or not isinstance(envelope["predecessor"], Mapping)
            or set(envelope["predecessor"])
            != {
                "generation",
                "logical_tick",
                "manifest_sha256",
                "resonant_workspace_state_sha256",
                "state_sha256",
                "temporal_memory_sha256",
            }
        ):
            raise FieldIntelligenceError(
                "PENDING_OPERATION_CORRUPT",
                "pending owner operation cannot be recovered safely",
            )
        try:
            operation_id = _identifier(
                envelope["operation_id"],
                "operation_id",
            )
            kind = _identifier(
                envelope["kind"],
                "pending operation kind",
            )
            if path != self._pending_file(operation_id):
                raise ValueError(
                    "pending operation path does not match its identity"
                )
            predecessor = envelope["predecessor"]
            _digest(
                predecessor["state_sha256"],
                "pending predecessor state",
            )
            _digest(
                predecessor["manifest_sha256"],
                "pending predecessor manifest",
            )
            for name in (
                "resonant_workspace_state_sha256",
                "temporal_memory_sha256",
            ):
                value = predecessor[name]
                if value is not None:
                    _digest(value, f"pending predecessor {name}")
            _integer(
                predecessor["generation"],
                "pending predecessor generation",
                minimum=0,
            )
            _integer(
                predecessor["logical_tick"],
                "pending predecessor logical tick",
                minimum=0,
            )
            self._validate_pending_payload(
                kind=kind,
                operation_id=operation_id,
                payload=envelope["payload"],
                predecessor=predecessor,
            )
        except (FieldIntelligenceError, KeyError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "PENDING_OPERATION_CORRUPT",
                "pending owner operation cannot be recovered safely",
            ) from exc
        return envelope

    def _pending_operation(self, operation_id: str) -> Mapping[str, Any] | None:
        path = self._pending_file(operation_id)
        return self._read_pending(path) if path.is_file() else None

    def _pending_predecessor(
        self, *, temporal_memory_sha256: str | None = None
    ) -> Mapping[str, Any]:
        workspace = self.state.resonant_workspace
        return {
            "generation": self.state.generation,
            "logical_tick": self.state.logical_tick,
            "manifest_sha256": self.checkpoints.current_manifest_sha256,
            "resonant_workspace_state_sha256": (
                None if workspace is None else workspace.state_sha256
            ),
            "state_sha256": self.state.state_sha256,
            "temporal_memory_sha256": temporal_memory_sha256,
        }

    def _assert_pending_predecessor(
        self, envelope: Mapping[str, Any]
    ) -> None:
        predecessor = envelope["predecessor"]
        current_workspace = self.state.resonant_workspace
        actual = self._pending_predecessor(
            temporal_memory_sha256=predecessor["temporal_memory_sha256"]
        )
        temporal_memory_sha256 = predecessor["temporal_memory_sha256"]
        if temporal_memory_sha256 is not None:
            payload = envelope["payload"]
            memory_id = payload.get("memory_id")
            if not isinstance(memory_id, str):
                raise FieldIntelligenceError(
                    "PENDING_OPERATION_CORRUPT",
                    "temporal pending operation does not name its memory",
                )
            try:
                actual = {
                    **actual,
                    "temporal_memory_sha256": self.state.temporal(
                        memory_id
                    ).memory_sha256,
                }
            except FieldIntelligenceError as exc:
                raise FieldIntelligenceError(
                    "LINEAGE_CONFLICT",
                    "pending temporal predecessor is no longer current",
                    details={"operation_id": envelope["operation_id"]},
                ) from exc
        if canonical_json_bytes(actual) != canonical_json_bytes(predecessor):
            raise FieldIntelligenceError(
                "LINEAGE_CONFLICT",
                "pending operation can resume only from its exact predecessor",
                details={
                    "actual_generation": self.state.generation,
                    "actual_manifest_sha256": self.checkpoints.current_manifest_sha256,
                    "actual_state_sha256": self.state.state_sha256,
                    "expected_generation": predecessor["generation"],
                    "expected_manifest_sha256": predecessor["manifest_sha256"],
                    "expected_state_sha256": predecessor["state_sha256"],
                    "operation_id": envelope["operation_id"],
                    "workspace_changed": (
                        predecessor["resonant_workspace_state_sha256"]
                        != (
                            None
                            if current_workspace is None
                            else current_workspace.state_sha256
                        )
                    ),
                },
            )
    def _operation_is_committed(self, operation_id: str) -> bool:
        return self.checkpoints._committed_operation(operation_id) is not None

    @staticmethod
    def _pending_commit_operation_id(envelope: Mapping[str, Any]) -> str:
        operation_id = _identifier(envelope["operation_id"], "operation_id")
        if envelope["kind"] == "acknowledgment":
            return f"{operation_id}:publish"
        return operation_id

    def _assert_publication_order(self, operation_id: str) -> None:
        for path in sorted(self.pending_path.iterdir()):
            if not path.is_file():
                continue
            envelope = self._read_pending(path)
            pending_operation_id = envelope["operation_id"]
            commit_operation_id = self._pending_commit_operation_id(envelope)
            if operation_id != commit_operation_id:
                raise FieldIntelligenceError(
                    "LINEAGE_CONFLICT",
                    "another owner operation must recover before publication",
                    details={
                        "blocked_operation_id": operation_id,
                        "pending_operation_id": pending_operation_id,
                    },
                )
            if not self._operation_is_committed(commit_operation_id):
                self._assert_pending_predecessor(envelope)

    def _stage_pending(
        self,
        *,
        operation_id: str,
        kind: str,
        payload: Mapping[str, Any],
        temporal_memory_sha256: str | None = None,
    ) -> None:
        _identifier(operation_id, "operation_id")
        if temporal_memory_sha256 is not None:
            _digest(temporal_memory_sha256, "temporal memory predecessor")
        envelope = {
            "kind": _identifier(kind, "pending operation kind"),
            "operation_id": operation_id,
            "payload": json.loads(canonical_json_bytes(dict(payload))),
            "predecessor": self._pending_predecessor(
                temporal_memory_sha256=temporal_memory_sha256
            ),
            "schema": PENDING_OPERATION_SCHEMA,
        }
        path = self._pending_file(operation_id)
        pending_paths = tuple(
            path
            for path in sorted(self.pending_path.iterdir())
            if path.is_file()
        )
        if path.exists():
            for other_path in pending_paths:
                if other_path == path:
                    continue
                other = self._read_pending(other_path)
                raise FieldIntelligenceError(
                    "LINEAGE_CONFLICT",
                    "another owner operation must recover before admission",
                    details={
                        "blocked_operation_id": operation_id,
                        "pending_operation_id": other["operation_id"],
                    },
                )
            existing = self._read_pending(path)
            self._assert_pending_predecessor(existing)
            if path.read_bytes() != canonical_json_bytes(envelope):
                raise FieldIntelligenceError(
                    "OPERATION_CONFLICT",
                    "pending operation identity has different semantics",
                )
            return
        if len(pending_paths) >= self.limits.max_pending_operations:
            raise FieldIntelligenceError(
                "FIELD_CAPACITY", "pending admission exceeds its configured limit",
                details={"resource": "pending_operations", "count": len(pending_paths) + 1,
                         "limit": self.limits.max_pending_operations},
            )
        if pending_paths:
            other = self._read_pending(pending_paths[0])
            raise FieldIntelligenceError(
                "LINEAGE_CONFLICT",
                "another owner operation must recover before admission",
                details={
                    "blocked_operation_id": operation_id,
                    "pending_operation_id": other["operation_id"],
                },
            )
        _atomic_write(path, canonical_json_bytes(envelope))

    def _finish_pending(self, operation_id: str) -> None:
        try:
            self._pending_file(operation_id).unlink()
        except FileNotFoundError:
            pass

    def _recover_pending_operations(self) -> None:
        fatal_codes = {
            "CHECKPOINT_CORRUPT",
            "LINEAGE_CONFLICT",
            "PENDING_OPERATION_CORRUPT",
            "PERSISTENCE_CORRUPT",
            "REVOCATION_FENCE",
            "STALE_REVOCATION",
        }
        for path in sorted(self.pending_path.iterdir()):
            if not path.is_file():
                continue
            envelope = self._read_pending(path)
            operation_id = _identifier(envelope["operation_id"], "operation_id")
            try:
                commit_operation_id = self._pending_commit_operation_id(envelope)
                if not self._operation_is_committed(commit_operation_id):
                    self._assert_pending_predecessor(envelope)
                self._resume_pending(envelope)
            except FieldIntelligenceError as exc:
                if exc.code in fatal_codes:
                    raise
                _atomic_write(
                    self.pending_failures_path / path.name,
                    canonical_json_bytes(
                        {
                            "error": {
                                "code": exc.code,
                                "details": dict(exc.details),
                                "message": str(exc),
                            },
                            "operation": envelope,
                            "schema": "cassifi.pending-owner-failure.v1",
                        }
                    ),
                )
            self._finish_pending(operation_id)

    def _resume_pending(self, envelope: Mapping[str, Any]) -> None:
        operation_id = _identifier(envelope["operation_id"], "operation_id")
        payload = envelope["payload"]
        if envelope["kind"] == "observation":
            self.admit_observation(
                operation_id=operation_id,
                source=SourceInput.from_dict(payload["source"]),
                values=payload["values"],
                context=payload["context"],
                epistemic_type=payload["epistemic_type"],
                weight=payload["weight"],
                derivation_roots=tuple(payload["derivation_roots"]),
                target_chart_ids=(
                    None
                    if payload["target_chart_ids"] is None
                    else tuple(payload["target_chart_ids"])
                ),
                event_kind=payload["event_kind"],
            )
        elif envelope["kind"] == "temporal-episode":
            self.learn_temporal(
                operation_id, memory_id=payload["memory_id"],
                source=SourceInput.from_dict(payload["source"]),
                context=payload["context"],
                expected_state_sha256=payload["expected_state_sha256"],
            )
        elif envelope["kind"] == "computation-episode":
            self.admit_computation_episode(
                operation_id=operation_id,
                source=SourceInput.from_dict(payload["source"]),
                workspace=ResonantWorkspace.from_dict(payload["workspace"]),
                feature_bindings=payload["feature_bindings"],
                outcomes=payload["outcomes"],
                context=payload["context"],
                target_chart_ids=tuple(payload["target_chart_ids"]),
            )
        elif envelope["kind"] == "acknowledgment":
            self.admit_acknowledgment(
                prediction_id=payload["prediction_id"],
                acknowledgment=WorldAcknowledgment.from_dict(
                    payload["acknowledgment"]
                ),
                attribution_candidates=tuple(payload["attribution_candidates"]),
                learn_chart_ids=(
                    None
                    if payload["learn_chart_ids"] is None
                    else tuple(payload["learn_chart_ids"])
                ),
            )
        else:
            raise FieldIntelligenceError(
                "PENDING_OPERATION_CORRUPT",
                "pending owner operation kind is unsupported",
                details={"kind": envelope["kind"]},
            )

    def _authority_control(self) -> dict[str, Any]:
        try:
            value = dict(_canonical_read(self.authority_path))
            if value.get("schema") == "cassifi.authority-control.v1":
                if set(value) != {
                    "generation",
                    "schema",
                    "used_grant_ids",
                }:
                    raise ValueError(
                        "legacy authority control schema is incompatible"
                    )
                _integer(
                    value["generation"],
                    "authority generation",
                    minimum=0,
                )
                legacy_ids = value["used_grant_ids"]
                if not isinstance(legacy_ids, list):
                    raise TypeError(
                        "used grant identities must be a list"
                    )
                normalized_legacy_ids = [
                    _identifier(grant_id, "used grant_id")
                    for grant_id in legacy_ids
                ]
                if len(set(normalized_legacy_ids)) != len(
                    normalized_legacy_ids
                ):
                    raise ValueError(
                        "used grant identities contain duplicates"
                    )
                value = {
                    "generation": value["generation"],
                    "schema": AUTHORITY_CONTROL_SCHEMA,
                    "used_grant_bindings": {},
                    "used_grant_ids": normalized_legacy_ids,
                }
                _atomic_write(
                    self.authority_path,
                    canonical_json_bytes(value),
                )
            if (
                set(value)
                != {
                    "generation",
                    "schema",
                    "used_grant_bindings",
                    "used_grant_ids",
                }
                or value["schema"] != AUTHORITY_CONTROL_SCHEMA
            ):
                raise ValueError(
                    "authority control schema is incompatible"
                )
            generation = _integer(
                value["generation"],
                "authority generation",
                minimum=0,
            )
            grant_ids = value["used_grant_ids"]
            if not isinstance(grant_ids, list):
                raise TypeError("used grant identities must be a list")
            normalized_ids = [
                _identifier(grant_id, "used grant_id")
                for grant_id in grant_ids
            ]
            if len(set(normalized_ids)) != len(normalized_ids):
                raise ValueError(
                    "used grant identities contain duplicates"
                )
            raw_bindings = value["used_grant_bindings"]
            if not isinstance(raw_bindings, Mapping):
                raise TypeError(
                    "used grant bindings must be an object"
                )
            normalized_bindings: dict[str, Mapping[str, Any]] = {}
            operation_ids: set[str] = set()
            for raw_grant_id, raw_binding in raw_bindings.items():
                grant_id = _identifier(
                    raw_grant_id,
                    "bound grant_id",
                )
                if (
                    grant_id not in normalized_ids
                    or not isinstance(raw_binding, Mapping)
                ):
                    raise ValueError(
                        "bound grant is not durably consumed"
                    )
                binding = dict(raw_binding)
                if set(binding) != {
                    "grant",
                    "prediction_id",
                    "request",
                    "request_sha256",
                }:
                    raise ValueError(
                        "used grant binding schema is invalid"
                    )
                if not isinstance(binding["grant"], Mapping):
                    raise TypeError(
                        "bound authority grant must be an object"
                    )
                grant = AuthorityGrant.from_dict(binding["grant"])
                if (
                    grant.grant_id != grant_id
                    or not isinstance(grant.one_use, bool)
                    or not grant.one_use
                    or grant.generation != generation
                ):
                    raise ValueError(
                        "bound authority grant is invalid"
                    )
                prediction_id = _digest(
                    binding["prediction_id"],
                    "bound prediction_id",
                )
                raw_request = binding["request"]
                if (
                    not isinstance(raw_request, Mapping)
                    or set(raw_request)
                    != {
                        "action",
                        "operation_id",
                        "payload",
                        "scope",
                        "target",
                    }
                    or not isinstance(raw_request["payload"], Mapping)
                ):
                    raise ValueError(
                        "bound effect request schema is invalid"
                    )
                request = {
                    "action": _identifier(
                        raw_request["action"],
                        "bound effect action",
                    ),
                    "operation_id": _identifier(
                        raw_request["operation_id"],
                        "bound effect operation_id",
                    ),
                    "payload": json.loads(
                        canonical_json_bytes(
                            dict(raw_request["payload"])
                        )
                    ),
                    "scope": _identifier(
                        raw_request["scope"],
                        "bound effect scope",
                    ),
                    "target": _identifier(
                        raw_request["target"],
                        "bound effect target",
                    ),
                }
                request_sha256 = _digest(
                    binding["request_sha256"],
                    "bound effect request identity",
                )
                if (
                    canonical_json_bytes(request)
                    != canonical_json_bytes(dict(raw_request))
                    or request_sha256 != sha256_value(request)
                    or grant.operation not in {"effect", "computer-effect"}
                    or (
                        grant.operation == "computer-effect"
                        and request["action"] != "dispatch-action"
                    )
                    or not grant.permits(
                        operation=grant.operation,
                        target=request["target"],
                        scope=request["scope"],
                        generation=generation,
                    )
                    or request["operation_id"] in operation_ids
                ):
                    raise ValueError(
                        "bound effect request is invalid"
                    )
                operation_ids.add(request["operation_id"])
                normalized_bindings[grant_id] = {
                    "grant": grant.as_dict(),
                    "prediction_id": prediction_id,
                    "request": request,
                    "request_sha256": request_sha256,
                }
            if (
                canonical_json_bytes(normalized_bindings)
                != canonical_json_bytes(dict(raw_bindings))
            ):
                raise ValueError(
                    "used grant bindings are not canonical"
                )
            return value
        except (
            FieldIntelligenceError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "authority control cannot be decoded safely",
            ) from exc

    @property
    def authority_generation(self) -> int:
        return int(self._authority_control()["generation"])

    def set_authority_generation(self, generation: int) -> None:
        """Accept a host-owned authority epoch; this does not grant an operation."""
        value = self._authority_control()
        generation = _integer(generation, "authority generation")
        if generation < value["generation"]:
            raise FieldIntelligenceError(
                "AUTHORITY_ROLLBACK", "authority generation cannot move backward"
            )
        if generation == value["generation"]:
            return
        value["generation"] = generation
        value["used_grant_ids"] = []
        value["used_grant_bindings"] = {}
        _atomic_write(self.authority_path, canonical_json_bytes(value))

    def _validate_grant(
        self,
        grant: AuthorityGrant,
        *,
        operation: str,
        target: str,
        scope: str,
        consume: bool,
        binding: Mapping[str, Any] | None = None,
    ) -> None:
        control = self._authority_control()
        if not grant.permits(
            operation=operation,
            target=target,
            scope=scope,
            generation=control["generation"],
        ):
            raise FieldIntelligenceError(
                "AUTHORITY_REQUIRED",
                "grant does not authorize this exact operation",
            )
        if grant.grant_id in control["used_grant_ids"]:
            raise FieldIntelligenceError(
                "AUTHORITY_CONSUMED",
                "one-use authority grant was already consumed",
            )
        if consume and grant.one_use:
            control["used_grant_ids"].append(grant.grant_id)
            if binding is not None:
                control["used_grant_bindings"][grant.grant_id] = json.loads(
                    canonical_json_bytes(dict(binding))
                )
            _atomic_write(
                self.authority_path,
                canonical_json_bytes(control),
            )

    @staticmethod
    def _effect_dispatch_request(
        prediction: PredictionRecord,
    ) -> Mapping[str, Any]:
        if prediction.operation_id is None:
            raise FieldIntelligenceError(
                "INVALID_PREDICTION",
                "effect prediction has no operation identity",
            )
        payload = prediction.query["payload"]
        if not isinstance(payload, Mapping):
            raise FieldIntelligenceError(
                "INVALID_PREDICTION",
                "effect prediction payload is invalid",
            )
        return {
            "action": _identifier(
                prediction.predicted["action"],
                "effect action",
            ),
            "operation_id": _identifier(
                prediction.operation_id,
                "effect operation_id",
            ),
            "payload": json.loads(
                canonical_json_bytes(dict(payload))
            ),
            "scope": _identifier(
                prediction.query["scope"],
                "effect scope",
            ),
            "target": _identifier(
                prediction.query["target"],
                "effect target",
            ),
        }

    @staticmethod
    def _computer_effect_dispatch_request(
        proposal: Mapping[str, Any] | None,
    ) -> Mapping[str, Any] | None:
        if not isinstance(proposal, Mapping):
            return None
        dispatch = proposal.get("dispatch")
        if not isinstance(dispatch, Mapping):
            return None
        return {
            "action": "dispatch-action",
            "operation_id": proposal.get("proposal_id"),
            "payload": {
                "adapter_id": dispatch.get("adapter_id"),
                "dispatch_id": dispatch.get("dispatch_id"),
                "idempotency": dispatch.get("idempotency"),
                "idempotency_key": dispatch.get("idempotency_key"),
            },
            "scope": proposal.get("scope"),
            "target": proposal.get("target"),
        }


    def _effect_grant_binding(
        self,
        prediction: PredictionRecord,
        grant: AuthorityGrant,
    ) -> Mapping[str, Any]:
        request = self._effect_dispatch_request(prediction)
        return {
            "grant": grant.as_dict(),
            "prediction_id": prediction.prediction_id,
            "request": request,
            "request_sha256": sha256_value(request),
        }

    def _effect_grant_is_reserved(
        self,
        prediction: PredictionRecord,
    ) -> bool:
        request = self._effect_dispatch_request(prediction)
        matches = [
            binding
            for binding in self._authority_control()[
                "used_grant_bindings"
            ].values()
            if binding["request"]["operation_id"]
            == prediction.operation_id
        ]
        if not matches:
            return False
        binding = matches[0]
        if (
            binding["prediction_id"] != prediction.prediction_id
            or canonical_json_bytes(binding["request"])
            != canonical_json_bytes(request)
        ):
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "effect authority reservation differs from its prediction",
            )
        return True

    def _reserve_effect_grant(
        self,
        prediction: PredictionRecord,
        grant: AuthorityGrant,
    ) -> None:
        if self._effect_grant_is_reserved(prediction):
            return
        request = self._effect_dispatch_request(prediction)
        self._validate_grant(
            grant,
            operation="effect",
            target=request["target"],
            scope=request["scope"],
            consume=True,
            binding=self._effect_grant_binding(prediction, grant),
        )

    def _clear_effect_grant_binding(self, operation_id: str) -> None:
        operation_id = _identifier(
            operation_id,
            "effect operation_id",
        )
        control = self._authority_control()
        retained = {
            grant_id: binding
            for grant_id, binding in control[
                "used_grant_bindings"
            ].items()
            if binding["request"]["operation_id"] != operation_id
        }
        if len(retained) == len(control["used_grant_bindings"]):
            return
        control["used_grant_bindings"] = retained
        _atomic_write(
            self.authority_path,
            canonical_json_bytes(control),
        )

    def _recover_effect_grant_bindings(self) -> None:
        control = self._authority_control()
        bindings = dict(control["used_grant_bindings"])
        if not bindings:
            return
        predictions = {
            row.operation_id: row
            for row in self.state.predictions
            if row.operation_id is not None
        }
        retained: dict[str, Mapping[str, Any]] = {}
        for grant_id, binding in bindings.items():
            grant = AuthorityGrant.from_dict(binding["grant"])
            if grant.operation == "computer-effect":
                proposal = None
                expected = None
                for computer in self.state.computers:
                    task = computer.inspect().get("task")
                    candidate = (
                        task.get("continuation", {}).get("proposal")
                        if isinstance(task, Mapping)
                        else None
                    )
                    candidate_request = self._computer_effect_dispatch_request(
                        candidate
                    )
                    if (
                        candidate_request is not None
                        and candidate_request["operation_id"]
                        == binding["request"]["operation_id"]
                    ):
                        proposal = candidate
                        expected = candidate_request
                        break
                if (
                    expected is None
                    or not isinstance(proposal, Mapping)
                    or binding["prediction_id"] != proposal.get("proposal_id")
                    or canonical_json_bytes(binding["request"])
                    != canonical_json_bytes(expected)
                ):
                    raise FieldIntelligenceError(
                        "PERSISTENCE_CORRUPT",
                        "computer-effect authority reservation differs from "
                        "its regional dispatch",
                    )
                retained[grant_id] = binding
                continue
            operation_id = binding["request"]["operation_id"]
            prediction = predictions.get(operation_id)
            if prediction is None:
                raise FieldIntelligenceError(
                    "PERSISTENCE_CORRUPT",
                    "effect authority reservation has no prediction",
                )
            expected = self._effect_dispatch_request(prediction)
            if (
                binding["prediction_id"] != prediction.prediction_id
                or canonical_json_bytes(binding["request"])
                != canonical_json_bytes(expected)
            ):
                raise FieldIntelligenceError(
                    "PERSISTENCE_CORRUPT",
                    "effect authority reservation differs from its prediction",
                )
            if prediction.status == "proposed":
                prediction = self._publish_effect_pending(prediction)
                retained[grant_id] = binding
            elif prediction.status == "pending":
                retained[grant_id] = binding
            elif prediction.status not in {
                "acknowledged",
                "invalidated",
            }:
                raise FieldIntelligenceError(
                    "PERSISTENCE_CORRUPT",
                    "effect authority reservation has an invalid state",
                )
        if len(retained) != len(bindings):
            control["used_grant_bindings"] = retained
            _atomic_write(
                self.authority_path,
                canonical_json_bytes(control),
            )

    def _publish_effect_pending(
        self,
        prediction: PredictionRecord,
    ) -> PredictionRecord:
        if prediction.status == "pending":
            return prediction
        if prediction.status != "proposed" or prediction.operation_id is None:
            raise FieldIntelligenceError(
                "PROPOSAL_STALE",
                "effect prediction is no longer dispatchable",
            )
        pending = replace(prediction, status="pending")
        predictions = tuple(
            pending
            if row.prediction_id == prediction.prediction_id
            else row
            for row in self.state.predictions
        )
        successor = self.state.with_transition(
            "effect-pending",
            {
                "operation_id": prediction.operation_id,
                "prediction_id": prediction.prediction_id,
            },
            predictions=predictions,
        )
        self._publish(
            operation_id=f"pending:{prediction.operation_id}",
            successor=successor,
            event_id=None,
            transition={
                "kind": "effect-pending",
                "prediction_id": prediction.prediction_id,
            },
        )
        return pending

    def _check_capacity(self, state: AtlasState) -> None:
        workspace_usage = state.workspace_usage()
        rows = {
            "charts": (len(state.charts), self.limits.max_charts),
            "plans": (len(state.plans), self.limits.max_plans),
            "predictions": (len(state.predictions), self.limits.max_predictions),
            "programs": (
                len(state.programs) + len(state.constructions) + len(state.macros)
                + len(state.transceivers) + len(state.temporal_fields) + len(state.computers),
                self.limits.max_programs,
            ),
            "variables": (len(state.variables), self.limits.max_variables),
            "prepared_branches": (workspace_usage["prepared_branches"], self.limits.max_prepared_branches),
            "workspace_bytes": (workspace_usage["workspace_bytes"], self.limits.max_workspace_bytes),
            "ports": (workspace_usage["ports"], self.limits.max_ports),
        }
        state_bytes = state.closure_bytes
        exceeded = {
            name: {"actual": actual, "limit": limit}
            for name, (actual, limit) in rows.items()
            if actual > limit
        }
        if state_bytes > self.limits.max_state_bytes:
            exceeded["state_bytes"] = {"actual": state_bytes, "limit": self.limits.max_state_bytes}
        if exceeded:
            raise FieldIntelligenceError(
                "FIELD_CAPACITY",
                "field operation exceeds configured capacity",
                details=exceeded,
            )

    def _prepare_world_adapter(self, adapter: WorldAdapter) -> None:
        try:
            adapter_id = _identifier(adapter.adapter_id, "world adapter_id")
            adapter.bind_durable_journal(
                self.data_home
                / "world-adapters"
                / hashlib.sha256(adapter_id.encode("utf-8")).hexdigest()
            )
        except AttributeError as exc:
            raise FieldIntelligenceError(
                "ADAPTER_DURABILITY",
                "world adapter does not expose durable operation replay",
            ) from exc

    def _publish(
        self,
        *,
        operation_id: str,
        successor: AtlasState,
        event_id: str | None,
        transition: Mapping[str, Any],
    ) -> CheckpointReceipt:
        self._assert_publication_order(operation_id)
        self._check_capacity(successor)
        receipt = self.checkpoints.commit(
            operation_id=operation_id,
            successor=successor,
            event_id=event_id,
            transition=transition,
        )
        self.state = self.checkpoints.state
        return receipt
    def _committed_replay(
        self,
        operation_id: str,
        *,
        require_retained: bool = False,
    ) -> tuple[Mapping[str, Any], CheckpointReceipt] | None:
        committed = self.checkpoints._committed_operation(operation_id)
        if committed is None:
            return None
        record, manifest = committed
        if require_retained:
            manifest = self.checkpoints._retained_manifest(
                record["manifest_sha256"]
            )
        receipt = CheckpointReceipt(
            operation_id=operation_id,
            manifest_sha256=record["manifest_sha256"],
            state_sha256=manifest["state_sha256"],
            predecessor_manifest_sha256=record["parent_manifest_sha256"],
            generation=manifest["generation"],
            replayed=True,
        )
        return manifest, receipt

    def _committed_result(
        self,
        operation_id: str,
        *,
        expected_kind: str,
        expected_request: Mapping[str, Any],
        expected_result_keys: frozenset[str],
        expected_mapping_result_fields: frozenset[str] = frozenset(),
        expected_transition_fields: Mapping[str, Any] | None = None,
        replay_bound_request_fields: frozenset[str] = frozenset(),
        require_retained: bool = False,
    ) -> tuple[Mapping[str, Any], dict[str, Any], CheckpointReceipt] | None:
        """Return an authenticated replay whose caller contract still matches."""
        replay = self._committed_replay(
            operation_id,
            require_retained=require_retained,
        )
        if replay is None:
            return None
        manifest, receipt = replay
        transition = manifest["transition"]
        if transition.get("kind") != expected_kind:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "operation identity is already bound to different request semantics",
            )
        stored_request = transition.get("request")
        try:
            if not isinstance(stored_request, Mapping):
                raise TypeError("committed request is not an object")
            stored_request = dict(stored_request)
            stored_request_bytes = canonical_json_bytes(stored_request)
            stored_request_sha256 = hashlib.sha256(
                stored_request_bytes
            ).hexdigest()
            if stored_request_sha256 != transition["request_sha256"]:
                raise ValueError(
                    "committed request digest disagrees with its payload"
                )
            effective_request = dict(expected_request)
            for key in replay_bound_request_fields:
                if key not in effective_request or key not in stored_request:
                    raise KeyError(key)
                effective_request[key] = stored_request[key]
            expected_request_bytes = canonical_json_bytes(effective_request)
            expected_request_sha256 = hashlib.sha256(
                expected_request_bytes
            ).hexdigest()
        except (
            FieldIntelligenceError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "committed replay request cannot be decoded safely",
            ) from exc
        if (
            transition["request_sha256"] != expected_request_sha256
            or stored_request_bytes != expected_request_bytes
        ):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "operation identity is already bound to different request semantics",
            )
        if expected_transition_fields is not None:
            try:
                fields_match = all(
                    key in transition
                    and canonical_json_bytes(transition[key])
                    == canonical_json_bytes(value)
                    for key, value in expected_transition_fields.items()
                )
            except (FieldIntelligenceError, TypeError, ValueError) as exc:
                raise FieldIntelligenceError(
                    "CHECKPOINT_CORRUPT",
                    "committed replay transition cannot be decoded safely",
                ) from exc
            if not fields_match:
                raise FieldIntelligenceError(
                    "OPERATION_CONFLICT",
                    "operation identity is already bound to different result semantics",
                )
        stored_result = transition.get("result")
        if (
            not isinstance(stored_result, Mapping)
            or set(stored_result) != set(expected_result_keys)
        ):
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "committed replay result has an invalid schema",
            )
        try:
            result = json.loads(
                canonical_json_bytes(dict(stored_result)).decode("utf-8")
            )
        except (
            FieldIntelligenceError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "committed replay result cannot be decoded safely",
            ) from exc
        if not isinstance(result, dict):
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "committed replay result must be an object",
            )
        if any(
            key not in result or not isinstance(result[key], Mapping)
            for key in expected_mapping_result_fields
        ):
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "committed replay result contains an invalid object field",
            )
        return manifest, result, receipt
    def _validate_acknowledgment_replay(
        self,
        *,
        manifest: Mapping[str, Any],
        stored_result: Mapping[str, Any],
        prediction: PredictionRecord,
        acknowledgment: WorldAcknowledgment,
        attribution_candidates: tuple[str, ...],
        learn_chart_ids: tuple[str, ...] | None,
    ) -> None:
        """Recompute a retained outcome from its authenticated predecessor and event."""
        event_operation_id = f"ack:{acknowledgment.operation_id}"
        try:
            transition = manifest["transition"]
            if (
                not isinstance(transition, Mapping)
                or set(transition)
                != {
                    "attribution_candidates",
                    "kind",
                    "learning",
                    "prediction_id",
                    "request",
                    "request_sha256",
                    "result",
                }
            ):
                raise ValueError(
                    "committed action outcome transition has an invalid schema"
                )
            event_id = _digest(
                manifest["event_id"],
                "action outcome event identity",
            )
            event = self.evidence.active_event(event_id)
            if self.evidence.event_for_operation(event_operation_id) != event:
                raise ValueError(
                    "committed action outcome is rebound to another event"
                )
            source = SourceInput(
                source_id=f"world-ack:{acknowledgment.operation_id}",
                content=acknowledgment.source_content,
                media_type="application/json",
                codec="utf-8",
                observed_timestamp=acknowledgment.acknowledgment_id,
                scope=prediction.query["scope"],
                claim_category="world-observation",
                fidelity="exact-record",
                labels=(prediction.query["scope"],),
            )
            stored_source = self.evidence.source(event.source_revision_id)
            if (
                stored_source.revision_id != source.revision_id
                or self.evidence.read(
                    stored_source,
                    allowed_labels=frozenset(source.labels),
                )
                != source.content
            ):
                raise ValueError(
                    "committed action outcome source differs from its acknowledgment"
                )
            event_ids = self.evidence.all_event_ids()
            if (
                event.logical_sequence > len(event_ids)
                or event_ids[event.logical_sequence - 1] != event.event_id
            ):
                raise ValueError(
                    "committed action outcome has an invalid evidence sequence"
                )
            parent_manifest_sha256 = _digest(
                manifest["parent_manifest_sha256"],
                "action outcome predecessor manifest",
            )
            predecessor = self.checkpoints.load_version(
                parent_manifest_sha256
            )
            expected_event = EvidenceEvent.create(
                operation_id=event_operation_id,
                event_kind="action-outcome",
                source_revision_id=source.revision_id,
                predecessor_state_sha256=predecessor.state_sha256,
                values=acknowledgment.observed_values,
                context=acknowledgment.context,
                epistemic_type="observed",
                derivation_roots=(),
                logical_sequence=event.logical_sequence,
            )
            if event != expected_event:
                raise ValueError(
                    "committed action outcome event differs from replay semantics"
                )
            actual = {
                "context": dict(acknowledgment.context),
                "observed_values": dict(acknowledgment.observed_values),
                "status": acknowledgment.status,
            }
            successor, resolved = self.cognition.resolve_prediction(
                predecessor,
                prediction_id=prediction.prediction_id,
                actual=actual,
                attribution_candidates=attribution_candidates,
            )
            learning: Mapping[str, Any] | None = None
            if learn_chart_ids is not None:
                successor, learning = self.atlas.admit_observation(
                    successor,
                    event_id=event.event_id,
                    source_revision_id=source.revision_id,
                    values=acknowledgment.observed_values,
                    context=acknowledgment.context,
                    epistemic_type="observed",
                    target_chart_ids=learn_chart_ids,
                )
            expected_result = {
                "acknowledgment_id": acknowledgment.acknowledgment_id,
                "prediction": resolved.as_dict(),
                "status": "acknowledged",
            }
            if (
                successor.state_sha256 != manifest["state_sha256"]
                or resolved != prediction
                or canonical_json_bytes(
                    transition["attribution_candidates"]
                )
                != canonical_json_bytes(list(attribution_candidates))
                or canonical_json_bytes(transition["learning"])
                != canonical_json_bytes(learning)
                or canonical_json_bytes(dict(stored_result))
                != canonical_json_bytes(expected_result)
            ):
                raise ValueError(
                    "committed action outcome disagrees with its successor"
                )
        except FieldIntelligenceError as exc:
            if exc.code in {"STALE_HISTORY", "STALE_REVOCATION"}:
                raise
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "committed action outcome cannot be replayed safely",
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "committed action outcome cannot be replayed safely",
            ) from exc

    def _committed_receipt(
        self,
        operation_id: str,
        *,
        expected_event_id: str | None = None,
        expected_transition: Mapping[str, Any] | None = None,
        expected_transition_fields: Mapping[str, Any] | None = None,
    ) -> CheckpointReceipt | None:
        replay = self._committed_replay(operation_id)
        if replay is None:
            return None
        manifest, receipt = replay
        transition = manifest["transition"]
        if (
            expected_event_id is not None
            and manifest["event_id"] != expected_event_id
        ):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "operation identity is already bound to a different event",
            )
        if (
            expected_transition is not None
            and canonical_json_bytes(transition)
            != canonical_json_bytes(dict(expected_transition))
        ):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "operation identity is already bound to different semantics",
            )
        if expected_transition_fields is not None and any(
            key not in transition or transition[key] != value
            for key, value in expected_transition_fields.items()
        ):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "operation identity is already bound to different semantics",
            )
        return receipt

    def _active_event(self, event_id: str) -> EvidenceEvent:
        return self.evidence.active_event(event_id)

    def _transition_position(self, field: str, identity: str) -> int:
        positions = [
            index
            for index, transition in enumerate(self.state.transition_log)
            if isinstance(transition.get("payload"), Mapping)
            and transition["payload"].get(field) == identity
        ]
        if not positions:
            raise FieldIntelligenceError(
                "EVIDENCE_SEQUENCE",
                f"field transition for {field} is unavailable",
            )
        return positions[-1]

    def _require_event_after(
        self, event: EvidenceEvent, *, field: str, identity: str
    ) -> None:
        prerequisite = self._transition_position(field, identity)
        outcome = self._transition_position("event_id", event.event_id)
        if outcome <= prerequisite:
            raise FieldIntelligenceError(
                "EVIDENCE_SEQUENCE",
                "assessment evidence must follow its frozen prediction",
            )

    @staticmethod
    def _require_event_values(
        event: EvidenceEvent, values: Mapping[str, Any]
    ) -> None:
        for name, expected in values.items():
            if name not in event.values:
                raise FieldIntelligenceError(
                    "EVIDENCE_MISMATCH",
                    f"evidence event does not contain outcome variable {name}",
                )
            actual = event.values[name]
            if isinstance(actual, bool) or isinstance(expected, bool):
                matches = actual == expected
            elif isinstance(actual, (int, float)) and isinstance(
                expected, (int, float, str)
            ):
                try:
                    matches = float(actual) == float(expected)
                except ValueError:
                    matches = False
            else:
                matches = actual == expected
            if not matches:
                raise FieldIntelligenceError(
                    "EVIDENCE_MISMATCH",
                    f"supplied outcome differs from evidence variable {name}",
                )

    def _require_exact_event_text(
        self, event: EvidenceEvent, text: str
    ) -> None:
        source = self.evidence.source(event.source_revision_id)
        if source.codec.lower() != "utf-8":
            raise FieldIntelligenceError(
                "EVIDENCE_MISMATCH",
                "language evidence must use the UTF-8 exact-source codec",
            )
        try:
            exact_text = self.evidence.read(source).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FieldIntelligenceError(
                "EVIDENCE_MISMATCH",
                "language evidence source is not valid UTF-8",
            ) from exc
        if exact_text != text:
            raise FieldIntelligenceError(
                "EVIDENCE_MISMATCH",
                "language text differs from its exact evidence source",
            )

    def _recover_revocation(self) -> None:
        fence = self.checkpoints.revocation_fence()
        if self.state.revocation_generation == fence["generation"]:
            return
        if self.state.revocation_generation > fence["generation"]:
            raise FieldIntelligenceError(
                "REVOCATION_ROLLBACK", "field is ahead of its authority fence"
            )
        targets = tuple(fence["revision_ids"])
        self.evidence.revoke(targets, generation=fence["generation"])
        successor, details = self.atlas.retract_sources(
            self.state,
            targets,
            revocation_generation=fence["generation"],
        )
        self._publish(
            operation_id=f"recover:{fence['operation_id']}",
            successor=successor,
            event_id=None,
            transition={"kind": "revocation-recovery", **details},
        )

    def configure_variable(
        self, operation_id: str, variable: VariableSpec
    ) -> CheckpointReceipt:
        with self._lock:
            transition = {
                "kind": "configure-variable",
                "variable": variable.as_dict(),
            }
            replay = self._committed_receipt(
                operation_id, expected_transition=transition
            )
            if replay is not None:
                return replay
            successor = self.atlas.add_variable(self.state, variable)
            if successor is self.state:
                return CheckpointReceipt(
                    operation_id=operation_id,
                    manifest_sha256=self.checkpoints.current_manifest_sha256,
                    state_sha256=self.state.state_sha256,
                    predecessor_manifest_sha256=(
                        self.checkpoints.current_manifest_sha256
                    ),
                    generation=self.state.generation,
                    replayed=True,
                )
            return self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition=transition,
            )

    def configure_chart(
        self, operation_id: str, chart: RelationChart
    ) -> CheckpointReceipt:
        with self._lock:
            transition = {"chart": chart.as_dict(), "kind": "configure-chart"}
            replay = self._committed_receipt(
                operation_id, expected_transition=transition
            )
            if replay is not None:
                return replay
            successor = self.atlas.add_chart(self.state, chart)
            return self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition=transition,
            )

    def configure_program(
        self, operation_id: str, program: FieldProgram
    ) -> CheckpointReceipt:
        with self._lock:
            transition = {
                "kind": "configure-program",
                "program": program.as_dict(),
            }
            replay = self._committed_receipt(
                operation_id, expected_transition=transition
            )
            if replay is not None:
                return replay
            successor = self.atlas.add_program(self.state, program)
            return self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition=transition,
            )

    def admit_observation(
        self,
        *,
        operation_id: str,
        source: SourceInput,
        values: Mapping[str, float],
        context: Mapping[str, Any],
        epistemic_type: str = "observed",
        weight: float = 1.0,
        derivation_roots: Sequence[str] = (),
        target_chart_ids: Sequence[str] | None = None,
        event_kind: str = "observation",
    ) -> Mapping[str, Any]:
        with self._lock:
            operation_id = _identifier(operation_id, "operation_id")
            if not isinstance(source, SourceInput):
                raise FieldIntelligenceError(
                    "INVALID_SOURCE",
                    "observation source must be a SourceInput",
                )
            if not isinstance(values, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_EVIDENCE",
                    "observation values must be an object",
                )
            values = {
                _identifier(name, "observation variable"): _finite(
                    value,
                    "observation value",
                )
                for name, value in values.items()
            }
            if not isinstance(context, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_EVIDENCE",
                    "observation context must be an object",
                )
            try:
                context = json.loads(
                    canonical_json_bytes(dict(context)).decode("utf-8")
                )
            except Exception as exc:
                raise FieldIntelligenceError(
                    "INVALID_EVIDENCE",
                    "observation context must be canonical JSON",
                ) from exc
            epistemic_type = _identifier(
                epistemic_type,
                "epistemic_type",
            )
            if epistemic_type not in {"observed", "asserted", "derived"}:
                raise FieldIntelligenceError(
                    "INVALID_EVIDENCE",
                    "observation epistemic type cannot teach a chart",
                )
            event_kind = _identifier(event_kind, "event_kind")
            weight = _finite(
                weight,
                "observation weight",
                nonnegative=True,
            )
            if weight == 0.0:
                raise FieldIntelligenceError(
                    "INVALID_NUMERIC_VALUE",
                    "observation weight must be positive",
                )
            if (
                isinstance(derivation_roots, (str, bytes))
                or not isinstance(derivation_roots, Sequence)
            ):
                raise FieldIntelligenceError(
                    "INVALID_EVIDENCE",
                    "observation derivation roots must be a sequence",
                )
            derivation_roots = tuple(
                _digest(root, "observation derivation root")
                for root in derivation_roots
            )
            if (
                isinstance(target_chart_ids, (str, bytes))
                or (
                    target_chart_ids is not None
                    and not isinstance(target_chart_ids, Sequence)
                )
            ):
                raise FieldIntelligenceError(
                    "INVALID_EVIDENCE",
                    "observation target charts must be a sequence",
                )
            target_chart_ids = (
                None
                if target_chart_ids is None
                else tuple(
                    _identifier(chart_id, "observation target chart")
                    for chart_id in target_chart_ids
                )
            )
            pending_payload = {
                "context": dict(context),
                "derivation_roots": list(derivation_roots),
                "epistemic_type": epistemic_type,
                "event_kind": event_kind,
                "source": source.as_dict(),
                "target_chart_ids": (
                    None if target_chart_ids is None else list(target_chart_ids)
                ),
                "values": dict(values),
                "weight": weight,
            }
            request_sha256 = sha256_value(
                {
                    "context": dict(context),
                    "derivation_roots": list(derivation_roots),
                    "epistemic_type": epistemic_type,
                    "event_kind": event_kind,
                    "source_content_sha256": hashlib.sha256(
                        source.content
                    ).hexdigest(),
                    "source_revision_id": source.revision_id,
                    "target_chart_ids": (
                        None
                        if target_chart_ids is None
                        else list(target_chart_ids)
                    ),
                    "values": dict(values),
                    "weight": weight,
                }
            )
            existing_operation = self.evidence.event_for_operation(operation_id)
            event: EvidenceEvent
            if existing_operation is not None:
                event = existing_operation
                if (
                    event.source_revision_id != source.revision_id
                    or dict(event.values) != dict(values)
                    or dict(event.context) != dict(context)
                    or event.epistemic_type != epistemic_type
                    or tuple(event.derivation_roots) != tuple(derivation_roots)
                    or event.event_kind != event_kind
                ):
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "observation retry has different evidence semantics",
                    )
                stored = self.evidence.source(event.source_revision_id)
                if self.evidence.read(stored) != source.content:
                    raise FieldIntelligenceError(
                        "SOURCE_CONFLICT",
                        "observation retry resolves to different source bytes",
                    )
                replay = self._committed_receipt(
                    operation_id,
                    expected_event_id=event.event_id,
                    expected_transition_fields={
                        "kind": event_kind,
                        "request_sha256": request_sha256,
                    },
                )
                if replay is not None:
                    self._finish_pending(operation_id)
                    return {
                        "event": event.as_dict(),
                        "receipt": replay.as_dict(),
                        "source": stored.as_dict(),
                    }
            else:
                event = EvidenceEvent.create(
                    operation_id=operation_id,
                    event_kind=event_kind,
                    source_revision_id=source.revision_id,
                    predecessor_state_sha256=self.state.state_sha256,
                    values=values,
                    context=context,
                    epistemic_type=epistemic_type,
                    derivation_roots=derivation_roots,
                    logical_sequence=self.evidence.event_count + 1,
                )
                stored = self.evidence.store_source(
                    source,
                    reserved_bytes=len(canonical_json_bytes(event.as_dict())),
                    commit=False,
                )

            working = self.state
            supersession: Mapping[str, Any] | None = None
            supersession_operation: str | None = None
            expected_fence_generation = working.revocation_generation
            if source.parent_revision_id is not None:
                supersession_operation = f"{operation_id}:supersede"
                fence = self.checkpoints.revocation_fence()
                if fence["operation_id"] == supersession_operation:
                    if tuple(fence["revision_ids"]) != (
                        source.parent_revision_id,
                    ):
                        raise FieldIntelligenceError(
                            "OPERATION_CONFLICT",
                            "source correction revocation target conflicts",
                        )
                    expected_fence_generation = int(fence["generation"])
                elif working.revocation_generation == fence["generation"]:
                    expected_fence_generation = int(fence["generation"]) + 1
                else:
                    raise FieldIntelligenceError(
                        "REVOCATION_FENCE",
                        "source correction was overtaken by another revocation",
                    )
                if working.revocation_generation < expected_fence_generation:
                    working, supersession = self.atlas.retract_sources(
                        working,
                        (source.parent_revision_id,),
                        revocation_generation=expected_fence_generation,
                    )
                elif working.revocation_generation > expected_fence_generation:
                    raise FieldIntelligenceError(
                        "REVOCATION_FENCE",
                        "source correction was overtaken by another revocation",
                    )

            successor, transition = self.atlas.admit_observation(
                working,
                event_id=event.event_id,
                source_revision_id=stored.revision_id,
                values=event.values,
                context=event.context,
                epistemic_type=event.epistemic_type,
                weight=weight,
                derivation_roots=event.derivation_roots,
                target_chart_ids=target_chart_ids,
            )
            self._check_capacity(successor)
            self._stage_pending(
                operation_id=operation_id,
                kind="observation",
                payload=pending_payload,
            )
            if existing_operation is None:
                stored = self.evidence.store_source(
                    source,
                    reserved_bytes=len(canonical_json_bytes(event.as_dict())),
                )
                event = self.evidence.append_event(event)
            if supersession_operation is not None:
                assert source.parent_revision_id is not None
                applied_fence = self.checkpoints.advance_revocation(
                    (source.parent_revision_id,),
                    operation_id=supersession_operation,
                )
                if applied_fence["generation"] != expected_fence_generation:
                    raise FieldIntelligenceError(
                        "REVOCATION_FENCE",
                        "source correction fence changed before publication",
                    )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=event.event_id,
                transition={
                    "kind": event_kind,
                    "learning": dict(transition),
                    "request_sha256": request_sha256,
                    "supersession": supersession,
                },
            )
            self._finish_pending(operation_id)
            return {
                "event": event.as_dict(),
                "receipt": receipt.as_dict(),
                "source": stored.as_dict(),
                "transition": transition,
            }
    def admit_computation_episode(
        self,
        *,
        operation_id: str,
        source: SourceInput,
        workspace: ResonantWorkspace,
        feature_bindings: Mapping[str, Any],
        outcomes: Mapping[str, Any],
        context: Mapping[str, Any],
        target_chart_ids: Sequence[str] = (),
    ) -> Mapping[str, Any]:
        """Admit one measured computation episode through the field owner."""
        with self._lock:
            operation_id = _identifier(operation_id, "operation_id")
            if not isinstance(workspace, ResonantWorkspace):
                raise FieldIntelligenceError(
                    "INVALID_WORKSPACE", "computation episode needs a ResonantWorkspace"
                )
            normalized_features = json.loads(
                canonical_json_bytes(dict(feature_bindings)).decode("utf-8")
            )
            normalized_outcomes = json.loads(
                canonical_json_bytes(dict(outcomes)).decode("utf-8")
            )
            normalized_context = json.loads(
                canonical_json_bytes(dict(context)).decode("utf-8")
            )
            chart_ids = tuple(_identifier(item, "target chart id") for item in target_chart_ids)
            workspace_payload = json.loads(
                canonical_json_bytes(workspace.as_dict()).decode("utf-8")
            )
            workspace_sha256 = hashlib.sha256(
                canonical_json_bytes(workspace_payload)
            ).hexdigest()
            transition = {
                "context": normalized_context,
                "episode_id": source.revision_id,
                "feature_bindings": normalized_features,
                "kind": "computation-episode",
                "outcomes": normalized_outcomes,
                "source_content_sha256": hashlib.sha256(source.content).hexdigest(),
                "source_revision_id": source.revision_id,
                "target_chart_ids": list(chart_ids),
                "workspace_sha256": workspace_sha256,
            }
            replay = self._committed_receipt(
                operation_id,
                expected_transition=transition,
            )
            if replay is not None:
                return {
                    "receipt": replay.as_dict(),
                    "source": self.evidence.source(source.revision_id).as_dict(),
                    "replayed": True,
                }
            stored = self.evidence.store_source(
                source,
                reserved_bytes=len(canonical_json_bytes(transition)),
                commit=False,
            )
            pending_payload = {
                "context": normalized_context,
                "feature_bindings": normalized_features,
                "outcomes": normalized_outcomes,
                "source": source.as_dict(),
                "target_chart_ids": list(chart_ids),
                "workspace": workspace_payload,
            }
            self._stage_pending(
                operation_id=operation_id,
                kind="computation-episode",
                payload=pending_payload,
            )
            successor, computation_receipt = self.cognition.admit_computation_episode(
                self.state,
                episode_id=source.revision_id,
                source_revision_id=stored.revision_id,
                workspace=workspace,
                feature_bindings=normalized_features,
                outcomes=normalized_outcomes,
                context=normalized_context,
                target_chart_ids=chart_ids,
            )
            self._check_capacity(successor)
            stored = self.evidence.store_source(
                source,
                reserved_bytes=len(canonical_json_bytes(transition)),
            )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition=transition,
            )
            self._finish_pending(operation_id)
            record = dict(computation_receipt)
            return {
                "receipt": receipt.as_dict(),
                "record": record,
                "source": stored.as_dict(),
                "replayed": False,
            }
    def archive_source(
        self,
        *,
        operation_id: str,
        source: SourceInput,
        context: Mapping[str, Any],
        epistemic_type: str = "observed",
        event_kind: str = "archive",
    ) -> Mapping[str, Any]:
        """Persist identified evidence without teaching an adaptive relation."""
        with self._lock:
            normalized_context = json.loads(canonical_json_bytes(dict(context)))
            transition = {
                "context": normalized_context,
                "kind": event_kind,
                "source_revision_id": source.revision_id,
            }
            replay = self._committed_receipt(
                operation_id,
                expected_transition=transition,
            )
            if replay is not None:
                event = self.evidence.event_for_operation(operation_id)
                if event is None:
                    raise FieldIntelligenceError(
                        "EVIDENCE_MISSING",
                        "committed archive event is unavailable",
                    )
                return {
                    "event": event.as_dict(),
                    "receipt": replay.as_dict(),
                    "source": self.evidence.source(source.revision_id).as_dict(),
                }
            existing_event = self.evidence.event_for_operation(operation_id)
            if existing_event is None:
                stored = self.evidence.store_source(source)
                event = EvidenceEvent.create(
                    operation_id=operation_id,
                    event_kind=event_kind,
                    source_revision_id=stored.revision_id,
                    predecessor_state_sha256=self.state.state_sha256,
                    values={},
                    context=normalized_context,
                    epistemic_type=epistemic_type,
                    derivation_roots=(),
                    logical_sequence=self.evidence.event_count + 1,
                )
                self.evidence.append_event(event)
            else:
                event = existing_event
                if (
                    event.source_revision_id != source.revision_id
                    or dict(event.context) != normalized_context
                    or event.event_kind != event_kind
                    or event.epistemic_type != epistemic_type
                ):
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "archive retry has different evidence semantics",
                    )
                stored = self.evidence.source(event.source_revision_id)
            successor = replace(self.state, generation=self.state.generation + 1)
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=event.event_id,
                transition=transition,
            )
            return {
                "event": event.as_dict(),
                "receipt": receipt.as_dict(),
                "source": stored.as_dict(),
            }

    def activate_checkpoint(
        self,
        *,
        operation_id: str,
        target_manifest_sha256: str,
        context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Publish a historical field view as a new, auditable head."""
        with self._lock:
            target_manifest_sha256 = _digest(
                target_manifest_sha256,
                "target_manifest_sha256",
            )
            transition = {
                "context": json.loads(canonical_json_bytes(dict(context))),
                "kind": "activate-checkpoint",
                "target_manifest_sha256": target_manifest_sha256,
            }
            replay = self._committed_receipt(
                operation_id,
                expected_transition=transition,
            )
            if replay is not None:
                return {"receipt": replay.as_dict()}
            target = self.checkpoints.load_version(target_manifest_sha256)
            successor = replace(
                target,
                generation=self.state.generation + 1,
                revocation_generation=self.state.revocation_generation,
            )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition=transition,
            )
            return {"receipt": receipt.as_dict()}


    def think(
        self,
        operation_id: str,
        *,
        observed: Mapping[str, float],
        requested: Sequence[str],
        context: Mapping[str, Any] | None = None,
        constraints: Sequence[Any] = (),
        valid_source_revision_ids: Sequence[str] | None = None,
        tolerance: float = 1e-8,
        max_iterations: int | None = None,
        max_branches: int | None = None,
        ticks: int | None = None,
        query_id: str | None = None,
    ) -> Mapping[str, Any]:
        """Advance one prepared query and publish it as one idempotent transition."""
        with self._lock:
            _identifier(operation_id, "operation_id")
            max_iterations = min(512, self.limits.max_operator_effort, self.limits.max_solver_iterations) if max_iterations is None else _integer(
                max_iterations, "max_iterations", minimum=1
            )
            max_branches = self.limits.max_branches_per_query if max_branches is None else _integer(
                max_branches, "max_branches", minimum=1
            )
            ticks = self.limits.max_ticks_per_batch if ticks is None else _integer(
                ticks, "ticks", minimum=1
            )
            if max_iterations > min(512, self.limits.max_operator_effort, self.limits.max_solver_iterations):
                raise FieldIntelligenceError(
                    "WORK_CAPACITY", "think operator effort exceeds configured limit"
                )
            if max_branches > self.limits.max_branches_per_query:
                raise FieldIntelligenceError(
                    "WORK_CAPACITY", "think branch budget exceeds configured limit"
                )
            if ticks > self.limits.max_ticks_per_batch:
                raise FieldIntelligenceError("WORK_CAPACITY", "think tick budget exceeds configured limit")
            source_ids = (
                tuple(sorted(self.evidence.active_revision_ids()))
                if valid_source_revision_ids is None
                else tuple(
                    sorted(
                        {
                            _digest(item, "source revision")
                            for item in valid_source_revision_ids
                        }
                    )
                )
            )
            if len(source_ids) > self.limits.max_source_work:
                raise FieldIntelligenceError(
                    "WORK_CAPACITY", "think source work exceeds configured limit"
                )
            request = {
                "constraints": [
                    item.as_dict() if hasattr(item, "as_dict") else str(item)
                    for item in constraints
                ],
                "context": dict(context or {}),
                "max_branches": max_branches,
                "max_iterations": max_iterations,
                "observed": dict(observed),
                "query_id": query_id,
                "requested": list(requested),
                "source_ids": list(source_ids),
                "ticks": ticks,
                "tolerance": tolerance,
            }
            request_sha256 = sha256_value(request)
            committed = self._committed_result(
                operation_id,
                expected_kind="think",
                expected_request=request,
                expected_result_keys=frozenset(
                    {
                        "branches",
                        "checkpoint_receipt",
                        "context",
                        "field_generation",
                        "memory_unchanged",
                        "observed",
                        "query_id",
                        "requested",
                        "resonance_receipt",
                        "state_sha256",
                        "status",
                    }
                ),
                expected_mapping_result_fields=frozenset(
                    {"resonance_receipt"}
                ),
                replay_bound_request_fields=(
                    frozenset({"source_ids"})
                    if valid_source_revision_ids is None
                    else frozenset()
                ),
            )
            if committed is not None:
                manifest, replay, receipt = committed
                transition = manifest["transition"]
                query_payload = {
                    key: value
                    for key, value in replay.items()
                    if key != "resonance_receipt"
                }
                try:
                    query_replay = QueryResult.from_dict(query_payload)
                    parent = self.checkpoints._manifest(
                        manifest["parent_manifest_sha256"]
                    )
                    stored_request = transition["request"]
                    stored_source_ids = stored_request["source_ids"]
                    if not isinstance(stored_source_ids, list):
                        raise TypeError(
                            "think source selection must be an array"
                        )
                    bound_source_ids = frozenset(
                        _digest(item, "source revision")
                        for item in stored_source_ids
                    )
                    if len(stored_source_ids) > self.limits.max_source_work:
                        raise ValueError(
                            "think source selection exceeds its durable limit"
                        )
                    if any(
                        not set(branch.source_revision_ids).issubset(
                            bound_source_ids
                        )
                        for branch in query_replay.branches
                    ):
                        raise ValueError(
                            "think result cites evidence outside its request"
                        )
                    if (
                        canonical_json_bytes(query_replay.as_dict())
                        != canonical_json_bytes(query_payload)
                        or query_replay.query_id != transition.get("query_id")
                        or query_replay.state_sha256 != parent["state_sha256"]
                        or query_replay.field_generation != parent["generation"]
                        or query_replay.checkpoint_receipt is None
                        or canonical_json_bytes(
                            query_replay.checkpoint_receipt
                        )
                        != canonical_json_bytes(replay["resonance_receipt"])
                        or canonical_json_bytes(replay["resonance_receipt"])
                        != canonical_json_bytes(
                            transition.get("resonance_receipt")
                        )
                    ):
                        raise ValueError("think replay result is inconsistent")
                except (
                    FieldIntelligenceError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    raise FieldIntelligenceError(
                        "CHECKPOINT_CORRUPT",
                        "committed think result cannot be decoded safely",
                    ) from exc
                replay["checkpoint_receipt"] = receipt.as_dict()
                return replay
            successor, query_result, resonance_receipt = self.atlas.think(
                self.state,
                observed=observed,
                requested=requested,
                context=context,
                constraints=tuple(constraints),
                valid_source_revision_ids=frozenset(source_ids),
                tolerance=tolerance,
                max_iterations=max_iterations,
                max_branches=max_branches,
                ticks=ticks,
                query_id=query_id,
            )
            self._check_capacity(successor)
            result = dict(query_result.as_dict())
            result["query_id"] = query_result.query_id
            result["resonance_receipt"] = dict(resonance_receipt)
            transition = {
                "kind": "think",
                "query_id": query_result.query_id,
                "request_sha256": request_sha256,
                "request": request,
                "result": result,
                "resonance_receipt": result["resonance_receipt"],
            }
            checkpoint = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition=transition,
            )
            result["checkpoint_receipt"] = checkpoint.as_dict()
            return result

    def query(self, query_id: str) -> Mapping[str, Any]:
        """Read a previously prepared query; this path never runs inference."""
        _identifier(query_id, "query_id")
        with self._lock:
            result = self.atlas.query_prepared(self.state, query_id)
            return result.as_dict()

    def advance(
        self,
        operation_id: str,
        *,
        ticks: int = 1,
        expected_state_sha256: str | None = None,
        source_enabled: bool = True,
    ) -> Mapping[str, Any]:
        with self._lock:
            _identifier(operation_id, "operation_id")
            ticks = _integer(ticks, "ticks", minimum=1)
            if ticks > self.limits.max_ticks_per_batch:
                raise FieldIntelligenceError(
                    "WORK_CAPACITY", "advance tick budget exceeds configured limit"
                )
            if expected_state_sha256 is not None:
                expected_state_sha256 = _digest(expected_state_sha256, "expected state")
            request = {
                "expected_state_sha256": expected_state_sha256,
                "source_enabled": bool(source_enabled),
                "ticks": ticks,
            }
            transition_prefix = {"kind": "advance", **request}
            committed = self._committed_result(
                operation_id,
                expected_kind="advance",
                expected_request=request,
                expected_result_keys=frozenset({"resonance_receipt"}),
                expected_mapping_result_fields=frozenset(
                    {"resonance_receipt"}
                ),
                expected_transition_fields=request,
            )
            if committed is not None:
                manifest, replay, receipt = committed
                if canonical_json_bytes(replay["resonance_receipt"]) != (
                    canonical_json_bytes(
                        manifest["transition"].get("resonance_receipt")
                    )
                ):
                    raise FieldIntelligenceError(
                        "CHECKPOINT_CORRUPT",
                        "committed advance result disagrees with its transition",
                    )
                replay["checkpoint_receipt"] = receipt.as_dict()
                return replay
            if expected_state_sha256 is not None and _digest(expected_state_sha256, "expected state") != self.state.state_sha256:
                raise FieldIntelligenceError("LINEAGE_CONFLICT", "advance predecessor does not match current state")
            successor, resonance_receipt = self.atlas.advance(
                self.state, ticks=ticks, source_enabled=source_enabled
            )
            self._check_capacity(successor)
            receipt_value = dict(resonance_receipt)
            transition = {
                **transition_prefix,
                "request": request,
                "request_sha256": sha256_value(request),
                "resonance_receipt": receipt_value,
                "result": {"resonance_receipt": receipt_value},
            }
            checkpoint = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition=transition,
            )
            result = dict(transition["result"])
            result["checkpoint_receipt"] = checkpoint.as_dict()
            return result

    def inspect_resonance(self) -> Mapping[str, Any]:
        with self._lock:
            value = dict(self.atlas.inspect_resonance(self.state))
            value["state_sha256"] = self.state.state_sha256
            value["manifest_sha256"] = self.checkpoints.current_manifest_sha256
            value["generation"] = self.state.generation
            return value

    def write_packet_impulse(
        self,
        operation_id: str,
        *,
        path: str,
        component: str,
        flow_signal: Sequence[float],
        work_budget: float,
        event_kind: str = PACKET_IMPULSE_EVENT_KIND,
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        """Write one declared packet impulse into the wave as an owner transition.

        This is the owner write path: a written packet impulse enters the field
        through the owner's own transition machinery rather than through an
        externally modified workspace. It publishes one immutable successor, so
        the written pattern is part of the owner's checkpoint closure, is
        exactly-once under its operation identity, and can be read back after a
        restart. No evidence is consumed: a write is a field intervention, so the
        logical tick, the evidence store and the learned memory are unchanged.
        """

        with self._lock:
            _identifier(operation_id, "operation_id")
            path, component, signal = _packet_direction(path, component, flow_signal)
            budget = _finite(work_budget, "work_budget")
            if not 0.0 <= budget <= 1.0:
                raise FieldIntelligenceError(
                    "INVALID_REQUEST", "work_budget must be in [0,1]"
                )
            event_kind = _identifier(event_kind, "event_kind")
            if expected_state_sha256 is not None:
                expected_state_sha256 = _digest(
                    expected_state_sha256, "expected state"
                )
            request = {
                "path": path,
                "component": component,
                "flow_signal": signal,
                "work_budget": budget,
                "event_kind": event_kind,
                "expected_state_sha256": expected_state_sha256,
            }
            transition_prefix = {"kind": "write-packet-impulse", **request}
            committed = self._committed_result(
                operation_id,
                expected_kind="write-packet-impulse",
                expected_request=request,
                expected_result_keys=frozenset({"impulse_receipt"}),
                expected_mapping_result_fields=frozenset({"impulse_receipt"}),
                expected_transition_fields=request,
            )
            if committed is not None:
                manifest, replay, receipt = committed
                if canonical_json_bytes(replay["impulse_receipt"]) != (
                    canonical_json_bytes(
                        manifest["transition"].get("impulse_receipt")
                    )
                ):
                    raise FieldIntelligenceError(
                        "CHECKPOINT_CORRUPT",
                        "committed packet impulse result disagrees with its transition",
                    )
                replay["checkpoint_receipt"] = receipt.as_dict()
                return replay
            if (
                expected_state_sha256 is not None
                and expected_state_sha256 != self.state.state_sha256
            ):
                raise FieldIntelligenceError(
                    "LINEAGE_CONFLICT",
                    "packet impulse predecessor does not match current state",
                )
            try:
                successor, impulse_receipt = self.atlas.write_packet_impulse(
                    self.state,
                    path=path,
                    component=component,
                    flow_signal=signal,
                    work_budget=budget,
                    event_kind=event_kind,
                )
            except ResonantNumericalError as exc:
                raise FieldIntelligenceError("RESONANT_NUMERICAL", str(exc)) from exc
            self._check_capacity(successor)
            receipt_value = dict(impulse_receipt)
            transition = {
                **transition_prefix,
                "request": request,
                "request_sha256": sha256_value(request),
                "impulse_receipt": receipt_value,
                "result": {"impulse_receipt": receipt_value},
            }
            checkpoint = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition=transition,
            )
            result = dict(transition["result"])
            result["checkpoint_receipt"] = checkpoint.as_dict()
            return result

    def read_packet_deposit(
        self,
        *,
        path: str,
        component: str,
        flow_signal: Sequence[float],
    ) -> Mapping[str, Any]:
        """Recover a written direction's deposit from the canonical page.

        This is the read half of the write path. It names a direction exactly as
        the write names it -- a packet path, a component and a two-channel flow
        signal -- and returns the deposit the canonical page carries along that
        direction's own read-frame response.

        The value is declared as the design declares a readout
        (FIELD-INTELLIGENCE-DESIGN.md 27.3; README.md 653-657): a temporal
        prediction of the canonical page, labeled ``temporal-prediction``, which
        adds no observed support and does not advance the evidence clock. It is a
        read: it publishes no successor, writes nothing to the checkpoint
        closure, consumes no operation identity and leaves the page, the field
        generation, the logical tick and the evidence store unchanged. Declaring
        it as evidence instead would be a different operation, and that choice is
        left open; see the receipt's ``read_operation`` block.
        """

        with self._lock:
            path, component, signal = _packet_direction(path, component, flow_signal)
            try:
                value = dict(
                    self.atlas.read_packet_deposit(
                        self.state,
                        path=path,
                        component=component,
                        flow_signal=signal,
                    )
                )
            except ResonantNumericalError as exc:
                raise FieldIntelligenceError("RESONANT_NUMERICAL", str(exc)) from exc
            value["state_sha256"] = self.state.state_sha256
            value["manifest_sha256"] = self.checkpoints.current_manifest_sha256
            value["generation"] = self.state.generation
            return value

    def _validate_temporal_replay_result(
        self,
        *,
        manifest: Mapping[str, Any],
        request: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> None:
        try:
            kind = request["kind"]
            receipt = result["receipt"]
            if not isinstance(kind, str) or not isinstance(receipt, Mapping):
                raise TypeError("temporal replay payload is malformed")
            receipt = dict(receipt)
            receipt_keys = frozenset(receipt)
            if kind == "advance-temporal":
                if receipt_keys not in _TEMPORAL_ADVANCE_RECEIPT_KEYS:
                    raise ValueError(
                        "temporal advance receipt schema is invalid"
                    )
            elif (
                kind not in _TEMPORAL_RECEIPT_KEYS
                or receipt_keys != _TEMPORAL_RECEIPT_KEYS[kind]
            ):
                raise ValueError("temporal receipt schema is invalid")

            for key in (
                "action",
                "memory_id",
                "observation",
                "participant_id",
                "proposal_id",
                "skill_id",
                "task_id",
            ):
                if (
                    key in request
                    and key in receipt
                    and canonical_json_bytes(receipt[key])
                    != canonical_json_bytes(request[key])
                ):
                    raise ValueError(
                        f"temporal receipt {key} disagrees with its request"
                    )

            successor = self.checkpoints._load_state(manifest)
            memory_id = request.get("memory_id")
            if memory_id is None:
                memory_id = receipt.get("memory_id")
            if memory_id is not None:
                if not isinstance(memory_id, str):
                    raise TypeError("temporal receipt memory_id is invalid")
                memory = successor.temporal(memory_id)
                if (
                    "state_sha256" in receipt
                    and receipt["state_sha256"] != memory.state_sha256
                ):
                    raise ValueError(
                        "temporal receipt state digest is inconsistent"
                    )
                if (
                    "memory_sha256" in receipt
                    and receipt["memory_sha256"] != memory.memory_sha256
                ):
                    raise ValueError(
                        "temporal receipt memory digest is inconsistent"
                    )
                if (
                    "bound_memory_sha256" in receipt
                    and receipt["bound_memory_sha256"]
                    != memory.memory_sha256
                ):
                    raise ValueError(
                        "temporal skill binding digest is inconsistent"
                    )
                if (
                    "state_count" in receipt
                    and receipt["state_count"] != memory.state_count
                ):
                    raise ValueError(
                        "temporal receipt state count is inconsistent"
                    )
                if (
                    "source_revision_ids" in receipt
                    and canonical_json_bytes(
                        receipt["source_revision_ids"]
                    )
                    != canonical_json_bytes(
                        list(memory.source_revision_ids)
                    )
                ):
                    raise ValueError(
                        "temporal receipt source closure is inconsistent"
                    )
                if "previous_state_sha256" in receipt:
                    parent = self.checkpoints._manifest(
                        manifest["parent_manifest_sha256"]
                    )
                    previous = self.checkpoints._load_state(parent).temporal(
                        memory_id
                    )
                    if (
                        receipt["previous_state_sha256"]
                        != previous.state_sha256
                    ):
                        raise ValueError(
                            "temporal predecessor digest is inconsistent"
                        )

            task_id = request.get("task_id")
            if task_id is not None:
                plan = next(
                    (
                        row
                        for row in successor.plans
                        if row.goal_id == task_id
                        and row.goal.get("kind") == "temporal-task"
                    ),
                    None,
                )
                if plan is None:
                    raise ValueError(
                        "temporal receipt task is absent from successor"
                    )
                if (
                    kind == "compose-temporal-task"
                    and receipt["step_count"] != len(plan.segments)
                ):
                    raise ValueError(
                        "temporal receipt step count is inconsistent"
                    )
            if (
                "execution_authorized" in receipt
                and receipt["execution_authorized"] is not False
            ):
                raise ValueError(
                    "temporal replay incorrectly authorizes execution"
                )
        except FieldIntelligenceError as exc:
            if exc.code == "CHECKPOINT_CORRUPT":
                raise
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "committed temporal result cannot be decoded safely",
            ) from exc
        except (KeyError, StopIteration, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "committed temporal result cannot be decoded safely",
            ) from exc

    def _temporal_replay(
        self, operation_id: str, request: Mapping[str, Any]
    ) -> Mapping[str, Any] | None:
        _identifier(operation_id, "operation_id")
        expected = request.get("expected_state_sha256")
        if expected is not None:
            _digest(expected, "expected state")
        committed = self._committed_result(
            operation_id,
            expected_kind=str(request["kind"]),
            expected_request=request,
            expected_result_keys=frozenset({"receipt"}),
            expected_mapping_result_fields=frozenset({"receipt"}),
            require_retained=True,
        )
        if committed is not None:
            manifest, result, receipt = committed
            self._validate_temporal_replay_result(
                manifest=manifest,
                request=request,
                result=result,
            )
            result["checkpoint_receipt"] = receipt.as_dict()
            return result
        if self.checkpoints.operation_compacted(operation_id):
            raise FieldIntelligenceError("HISTORY_COMPACTED", "temporal operation precedes the retained replay floor")
        if expected is not None and expected != self.state.state_sha256:
            raise FieldIntelligenceError("LINEAGE_CONFLICT", "temporal predecessor does not match current state")
        return None

    @staticmethod
    def _temporal_apply(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except (TemporalFieldError, TemporalInquiryError) as exc:
            raise FieldIntelligenceError("INVALID_TEMPORAL", str(exc)) from exc

    def _temporal_memory(self, memory_id: str) -> TemporalField:
        row = self.state.temporal(_identifier(memory_id, "memory_id"))
        if not set(row.source_revision_ids).issubset(self.evidence.active_revision_ids()):
            raise FieldIntelligenceError("STALE_REVOCATION", "temporal memory depends on inactive evidence")
        return row

    def _temporal_plan_sources(self, row: TemporalField) -> tuple[PlanRecord, ...]:
        """Rebind live task evidence, retaining outstanding effects and completed work."""
        plans = []
        for plan in self.state.plans:
            if (plan.goal.get("kind") != "temporal-task"
                    or plan.status in {"completed", "invalidated"}
                    or not any(segment.payload["binding"]["memory_id"] == row.memory_id for segment in plan.segments)):
                plans.append(plan)
                continue
            sources = set()
            for segment in plan.segments:
                memory_id = segment.payload["binding"]["memory_id"]
                # A source revision may be superseded while this transition is
                # being assembled.  The target row is the only row rebinding
                # here; retain the other task bindings exactly as published.
                memory = row if memory_id == row.memory_id else self.state.temporal(memory_id)
                sources.update(memory.source_revision_ids)
            plans.append(replace(plan, source_revision_ids=tuple(sorted(sources))))
        return tuple(plans)

    def _temporal_successor(
        self,
        row: TemporalField,
        request: Mapping[str, Any],
        *,
        evidence: bool = False,
        resonant_workspace: ResonantWorkspace | None = None,
    ) -> AtlasState:
        rows = tuple(item for item in self.state.temporal_fields if item.memory_id != row.memory_id)
        workspace = (
            self.state.resonant_workspace
            if resonant_workspace is None
            else resonant_workspace
        )
        payload = {"memory_id": row.memory_id}
        if workspace is not None and workspace is not self.state.resonant_workspace:
            payload["resonant_workspace_state_sha256"] = workspace.state_sha256
        return self.state.with_transition(
            request["kind"],
            payload,
            temporal_fields=(*rows, row),
            plans=self._temporal_plan_sources(row) if evidence else self.state.plans,
            resonant_workspace=workspace,
            logical_tick=self.state.logical_tick + int(evidence),
        )

    def _publish_temporal(
        self, operation_id: str, request: Mapping[str, Any], successor: AtlasState,
        receipt: Mapping[str, Any], *, event_id: str | None = None,
    ) -> Mapping[str, Any]:
        result = json.loads(canonical_json_bytes({"receipt": dict(receipt)}))
        checkpoint = self._publish(
            operation_id=operation_id, successor=successor, event_id=event_id,
            transition={
                "kind": request["kind"], "request_sha256": sha256_value(request),
                "request": dict(request), "result": result,
            },
        )
        return {**result, "checkpoint_receipt": checkpoint.as_dict()}

    def configure_temporal(
        self, operation_id: str, *, memory_id: str, action_ids: Sequence[str],
        observation_ids: Sequence[str], max_states: int = 128,
        context: Mapping[str, Any] | None = None, expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            row = self._temporal_apply(
                TemporalField.initial, memory_id, action_ids=action_ids,
                observation_ids=observation_ids, max_states=max_states, context=context,
            )
            request = {
                "kind": "configure-temporal", "memory_id": row.memory_id,
                "action_ids": list(row.action_ids), "observation_ids": list(row.observation_ids),
                "max_states": row.max_states, "context": dict(row.context),
                "expected_state_sha256": expected_state_sha256,
            }
            replay = self._temporal_replay(operation_id, request)
            if replay is not None:
                return replay
            if any(item.memory_id == row.memory_id for item in self.state.temporal_fields):
                raise FieldIntelligenceError("OPERATION_CONFLICT", "temporal memory already exists")
            successor = self._temporal_successor(row, request)
            return self._publish_temporal(operation_id, request, successor, {
                "memory_id": row.memory_id, "memory_sha256": row.memory_sha256,
                "state_count": row.state_count,
            })

    @staticmethod
    def _temporal_episode(content: bytes) -> list[Mapping[str, str]]:
        try:
            value = json.loads(content.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise FieldIntelligenceError("INVALID_TEMPORAL_EPISODE", "episode is not UTF-8 JSON") from exc
        if (
            not isinstance(value, dict) or set(value) != {"schema", "steps"}
            or value["schema"] != "cassifi.temporal-episode.v1"
            or not isinstance(value["steps"], list) or not 1 <= len(value["steps"]) <= 4096
            or canonical_json_bytes(value) != content
        ):
            raise FieldIntelligenceError("INVALID_TEMPORAL_EPISODE", "episode must be bounded canonical ordered evidence")
        for step in value["steps"]:
            if not isinstance(step, dict) or set(step) != {"action", "observation"}:
                raise FieldIntelligenceError("INVALID_TEMPORAL_EPISODE", "episode step must contain current action and observation")
            _identifier(step["action"], "episode action")
            _identifier(step["observation"], "episode observation")
        return value["steps"]

    def _temporal_revision(
        self,
        row: TemporalField,
        source: SourceInput,
        episode: Sequence[Mapping[str, str]],
    ) -> tuple[
        tuple[str, ...],
        list[list[Mapping[str, str]]],
        int,
    ]:
        """Validate and prepare a strict append-only revision.

        Evidence storage enforces the global source head, while this method
        enforces the stronger temporal contract: the parent must be the
        current head admitted by this memory, provenance must remain fixed,
        and the new ordered episode must be a proper continuation.
        """
        parent_id = source.parent_revision_id
        if parent_id is None:
            if any(item.source_id == source.source_id for item in (
                self.evidence.source(revision) for revision in self.evidence.all_revision_ids()
            )):
                raise FieldIntelligenceError(
                    "SOURCE_STALE", "an independent episode cannot reuse an existing source identity"
                )
            prior = [
                self._temporal_episode(self.evidence.read(self.evidence.source(revision)))
                for revision in row.source_revision_ids
            ]
            return (
                (*row.source_revision_ids, source.revision_id),
                prior,
                0,
            )

        if parent_id not in row.source_revision_ids:
            raise FieldIntelligenceError(
                "SOURCE_PARENT_CONFLICT", "revision parent is not admitted to this temporal memory"
            )
        parent = self.evidence.source(parent_id)
        if parent.status in {"revoked", "deleted"}:
            raise FieldIntelligenceError(
                "STALE_REVOCATION", "a revoked episode cannot be extended"
            )
        if parent.status == "active" and parent_id not in self.evidence.active_revision_ids():
            raise FieldIntelligenceError(
                "SOURCE_PARENT_CONFLICT", "revision parent is not an active source head"
            )
        try:
            candidate = self.evidence.source(source.revision_id)
        except FieldIntelligenceError as exc:
            if exc.code != "SOURCE_NOT_FOUND":
                raise
            candidate = None
        if candidate is not None:
            if candidate.status != "active" or candidate.parent_revision_id != parent_id:
                raise FieldIntelligenceError(
                    "SOURCE_STALE", "temporal revision is no longer the active source head"
                )
            # The only valid superseded parent is the one replaced by this
            # exact candidate during an interrupted admission.
            if parent.status != "superseded":
                raise FieldIntelligenceError(
                    "SOURCE_PARENT_CONFLICT", "stored temporal revision has an invalid active parent"
                )
        elif parent.status != "active":
            raise FieldIntelligenceError(
                "SOURCE_PARENT_CONFLICT", "revision parent is a stale source head"
            )
        metadata = (
            ("source_id", source.source_id),
            ("media_type", source.media_type),
            ("codec", source.codec),
            ("observed_timestamp", source.observed_timestamp),
            ("scope", source.scope),
            ("claim_category", source.claim_category),
            ("fidelity", source.fidelity),
            ("labels", tuple(source.labels)),
            ("span", source.span),
        )
        for name, actual in metadata:
            expected = getattr(parent, name)
            if actual != expected:
                raise FieldIntelligenceError(
                    "SOURCE_SCOPE_CONFLICT",
                    f"temporal revision changes source provenance field {name}",
                )
        parent_episode = self._temporal_episode(
            self.evidence.read(parent, allow_historical=True)
        )
        if len(episode) <= len(parent_episode) or list(episode[:len(parent_episode)]) != parent_episode:
            raise FieldIntelligenceError(
                "INVALID_TEMPORAL_EPISODE",
                "temporal revisions must append strictly after the unchanged parent episode",
            )
        if candidate is None:
            # A dry-run admission checks the current global head without
            # mutating evidence; commit happens only after every check below.
            self.evidence.store_source(source, commit=False)
        prior = [
            self._temporal_episode(
                self.evidence.read(self.evidence.source(revision), allow_historical=revision == parent_id)
            )
            for revision in row.source_revision_ids
            if revision != parent_id
        ]
        revisions = tuple(
            source.revision_id if revision == parent_id else revision
            for revision in row.source_revision_ids
        )
        return revisions, prior, len(parent_episode)

    def learn_temporal(
        self, operation_id: str, *, memory_id: str, source: SourceInput,
        context: Mapping[str, Any] | None = None, expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        """Admit one exact episode or a strict append-only source revision."""
        with self._lock:
            memory_id = _identifier(memory_id, "memory_id")
            # Do not reject a pending revision merely because its source was
            # committed before a crash and consequently superseded the parent.
            # The revision validator below permits exactly that recovery case.
            row = self.state.temporal(memory_id)
            if context is not None and dict(context) != dict(row.context):
                raise FieldIntelligenceError("TEMPORAL_SCOPE_CONFLICT", "episode context differs from its field")
            if source.codec.lower() != "utf-8":
                raise FieldIntelligenceError(
                    "INVALID_TEMPORAL_EPISODE", "episodes require the UTF-8 exact-source codec"
                )
            episode = self._temporal_episode(source.content)
            request = {
                "kind": "learn-temporal", "memory_id": memory_id,
                "source_revision_id": source.revision_id, "context": dict(row.context),
                "expected_state_sha256": expected_state_sha256,
            }
            replay = self._temporal_replay(operation_id, request)
            if replay is not None:
                self._finish_pending(operation_id)
                return replay

            parent_id = source.parent_revision_id
            existing = self.evidence.event_for_operation(operation_id)
            if parent_id is None:
                row = self._temporal_memory(memory_id)
            revisions, prior_episodes, admitted_step_offset = (
                self._temporal_revision(row, source, episode)
            )
            admitted_step_count = len(episode) - admitted_step_offset
            try:
                stored = self.evidence.source(source.revision_id)
            except FieldIntelligenceError as exc:
                if exc.code != "SOURCE_NOT_FOUND":
                    raise
                stored = None
            pending_present = self._pending_file(operation_id).exists()
            source_events = self.evidence.events_for_source(source.revision_id)
            if any(item.operation_id != operation_id for item in source_events):
                raise FieldIntelligenceError(
                    "OPERATION_CONFLICT", "source revision is already bound to another operation"
                )
            if stored is not None and existing is None and not pending_present:
                raise FieldIntelligenceError(
                    "SOURCE_STALE", "source revision is already admitted under another operation"
                )
            if source.revision_id in row.source_revision_ids:
                raise FieldIntelligenceError(
                    "OPERATION_CONFLICT", "episode was already admitted under another operation"
                )
            if len(revisions) > self.limits.max_source_work:
                raise FieldIntelligenceError("WORK_CAPACITY", "temporal source reconstruction exceeds configured limit")
            event = existing or EvidenceEvent.create(
                operation_id=operation_id, event_kind="temporal-episode",
                source_revision_id=source.revision_id,
                predecessor_state_sha256=self.state.state_sha256,
                values={
                    "steps": float(len(episode)),
                    "admitted_steps": float(admitted_step_count),
                },
                context=row.context,
                epistemic_type="observed", derivation_roots=(),
                logical_sequence=self.evidence.event_count + 1,
            )
            expected_predecessor = self.state.state_sha256
            if (
                event.event_kind != "temporal-episode"
                or event.source_revision_id != source.revision_id
                or event.predecessor_state_sha256 != expected_predecessor
                or dict(event.context) != dict(row.context)
                or event.values.get("steps") != float(len(episode))
                or event.values.get("admitted_steps")
                != float(admitted_step_count)
            ):
                if event.predecessor_state_sha256 != expected_predecessor:
                    raise FieldIntelligenceError(
                        "LINEAGE_CONFLICT",
                        "pending temporal event can resume only from its exact predecessor",
                        details={
                            "actual_state_sha256": expected_predecessor,
                            "event_predecessor_state_sha256": event.predecessor_state_sha256,
                            "operation_id": operation_id,
                        },
                    )
                raise FieldIntelligenceError("OPERATION_CONFLICT", "pending temporal evidence differs")
            reserve = len(canonical_json_bytes(event.as_dict()))
            # This is deliberately a dry-run for new revisions.  It checks
            # source-head and capacity constraints without unsupported writes.
            self.evidence.store_source(source, reserved_bytes=reserve, commit=False)
            learned, learning = self._temporal_apply(
                row.learn, [*prior_episodes, episode], source_revision_ids=revisions,
            )
            workspace, resonance_coupling = (
                self.atlas.couple_temporal_transition(
                    self.state,
                    previous=row,
                    current=learned,
                    evidence_tick=self.state.logical_tick + 1,
                    episode=episode,
                    admitted_step_offset=admitted_step_offset,
                    evidence_event_id=event.event_id,
                )
            )
            successor = self._temporal_successor(
                learned,
                request,
                evidence=True,
                resonant_workspace=workspace,
            )
            self._check_capacity(successor)
            causal_predecessor = self._pending_predecessor(
                temporal_memory_sha256=row.memory_sha256
            )
            self._stage_pending(
                operation_id=operation_id,
                kind="temporal-episode",
                payload={
                    "context": dict(row.context),
                    "admitted_step_count": admitted_step_count,
                    "event_id": event.event_id,
                    "evidence_tick": self.state.logical_tick + 1,
                    "expected_state_sha256": expected_state_sha256,
                    "memory_id": memory_id,
                    "predecessor_manifest_sha256": self.checkpoints.current_manifest_sha256,
                    "predecessor_state_sha256": self.state.state_sha256,
                    "resonant_workspace_state_sha256": (
                        None
                        if self.state.resonant_workspace is None
                        else self.state.resonant_workspace.state_sha256
                    ),
                    "source": source.as_dict(),
                    "source_revision_id": source.revision_id,
                    "temporal_memory_sha256": row.memory_sha256,
                },
                temporal_memory_sha256=row.memory_sha256,
            )
            if existing is None:
                self.evidence.store_source(source, reserved_bytes=reserve)
                self.evidence.append_event(event)
            result = self._publish_temporal(
                operation_id,
                request,
                successor,
                {
                    **dict(learning),
                    "causal_predecessor": dict(causal_predecessor),
                    "resonance_coupling": dict(resonance_coupling),
                    "event_id": event.event_id,
                    "source_revision_id": source.revision_id,
                },
                event_id=event.event_id,
            )
            self._finish_pending(operation_id)
            return result

    def _require_temporal_idle(self, memory_id: str, participant_id: str | None) -> None:
        for plan in self.state.plans:
            if plan.goal.get("kind") != "temporal-task" or plan.status == "invalidated":
                continue
            for segment in plan.segments:
                proposal = segment.payload.get("pending")
                if (isinstance(proposal, Mapping) and proposal["memory_id"] == memory_id
                        and proposal["participant_id"] == participant_id):
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT", "participant has an outstanding task effect; acknowledge that proposal first")

    def advance_temporal(
        self, operation_id: str, *, memory_id: str, action: str, observation: str,
        participant_id: str | None = None,
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            request = {
                "kind": "advance-temporal", "memory_id": _identifier(memory_id, "memory_id"),
                "action": _identifier(action, "action"), "observation": _identifier(observation, "observation"),
                "expected_state_sha256": expected_state_sha256,
            }
            if participant_id is not None:
                request["participant_id"] = _identifier(participant_id, "participant_id")
            replay = self._temporal_replay(operation_id, request)
            if replay is not None:
                return replay
            self._require_temporal_idle(memory_id, participant_id)
            row, receipt = self._temporal_apply(
                self._temporal_memory(memory_id).consume, action, observation,
                participant_id=participant_id,
            )
            return self._publish_temporal(operation_id, request, self._temporal_successor(row, request), receipt)

    def reset_temporal(
        self, operation_id: str, *, memory_id: str, expected_state_sha256: str | None = None,
        participant_id: str | None = None, known_start: bool = True,
    ) -> Mapping[str, Any]:
        with self._lock:
            if not isinstance(known_start, bool):
                raise FieldIntelligenceError("INVALID_TEMPORAL", "known_start must be boolean")
            request = {
                "kind": "reset-temporal", "memory_id": _identifier(memory_id, "memory_id"),
                "expected_state_sha256": expected_state_sha256,
            }
            if participant_id is not None:
                request["participant_id"] = _identifier(participant_id, "participant_id")
            if not known_start:
                request["known_start"] = False
            replay = self._temporal_replay(operation_id, request)
            if replay is not None:
                return replay
            self._require_temporal_idle(memory_id, participant_id)
            row = self._temporal_apply(
                self._temporal_memory(memory_id).reset,
                participant_id=participant_id, known_start=known_start,
            )
            return self._publish_temporal(operation_id, request, self._temporal_successor(row, request), {
                "memory_id": memory_id, "memory_sha256": row.memory_sha256, "state_sha256": row.state_sha256,
            })

    def condense_temporal_skill(
        self, operation_id: str, *, memory_id: str, skill_id: str,
        goal_observations: Sequence[str], forbidden_observations: Sequence[str] = (),
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            if isinstance(goal_observations, (str, bytes)) or isinstance(forbidden_observations, (str, bytes)):
                raise FieldIntelligenceError("INVALID_TEMPORAL", "skill observation sets must be sequences")
            request = {
                "kind": "condense-temporal-skill", "memory_id": _identifier(memory_id, "memory_id"),
                "skill_id": _identifier(skill_id, "skill_id"),
                "goal_observations": list(goal_observations), "forbidden_observations": list(forbidden_observations),
                "expected_state_sha256": expected_state_sha256,
            }
            replay = self._temporal_replay(operation_id, request)
            if replay is not None:
                return replay
            previous = self._temporal_memory(memory_id)
            row, receipt = self._temporal_apply(
                previous.condense_skill,
                skill_id,
                goal_observations=goal_observations,
                forbidden_observations=forbidden_observations,
            )
            workspace, resonance_coupling = self.atlas.couple_temporal_transition(
                self.state,
                previous=previous,
                current=row,
                evidence_tick=self.state.logical_tick,
            )
            successor = self._temporal_successor(
                row,
                request,
                resonant_workspace=workspace,
            )
            return self._publish_temporal(
                operation_id,
                request,
                successor,
                {**dict(receipt), "resonance_coupling": dict(resonance_coupling)},
            )

    def inspect_temporal(
        self, memory_id: str, *, action: str | None = None, skill_id: str | None = None,
        participant_id: str | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            row = self._temporal_memory(memory_id)
            result: dict[str, Any] = {
                "memory_id": row.memory_id, "context": dict(row.context),
                "memory_sha256": row.memory_sha256, "state_sha256": row.state_sha256,
                "state_count": row.state_count, "source_revision_ids": list(row.source_revision_ids),
                "field_bytes": row.nbytes,
                "skill_ids": list(row.skill_ids),
                "formed_skill_ids": list(row.formed_skill_ids),
                "pending_skill_ids": list(row.pending_skill_ids),
                "participant_ids": list(row.participant_ids),
                "candidate_states": list(self._temporal_apply(row.candidate_states, participant_id=participant_id)),
                "working_context": self._temporal_apply(row.context_status, participant_id=participant_id),
            }
            if action is not None:
                result["prediction"] = self._temporal_apply(row.predict, action, participant_id=participant_id)
            if skill_id is not None:
                result["skill"] = self._temporal_apply(
                    row.skill_action,
                    skill_id,
                    participant_id=participant_id,
                )
                result["skill_pool_signal"] = self._temporal_apply(
                    row.skill_pool_signal,
                    skill_id,
                )
            return result

    def select_temporal_action(
        self,
        memory_id: str,
        *,
        skill_ids: Sequence[str],
        operations: Sequence[Mapping[str, Any]],
        participant_id: str | None = None,
        minimum_margin: float = 1e-9,
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        """Choose among independently safe categorical skills without learning."""
        with self._lock:
            if (
                isinstance(skill_ids, (str, bytes))
                or not isinstance(skill_ids, Sequence)
                or not 1 <= len(skill_ids) <= self.limits.max_prepared_branches
                or len(set(skill_ids)) != len(skill_ids)
            ):
                raise FieldIntelligenceError(
                    "INVALID_TEMPORAL",
                    "skill_ids must be a bounded unique ordered sequence",
                )
            requested_skills = tuple(
                _identifier(skill_id, "skill_id") for skill_id in skill_ids
            )
            if (
                isinstance(operations, (str, bytes))
                or not isinstance(operations, Sequence)
                or len(operations) > self.limits.max_prepared_branches
            ):
                raise FieldIntelligenceError(
                    "INVALID_TEMPORAL", "operations must be a bounded sequence"
                )
            normalized_operations: list[dict[str, Any]] = []
            for operation in operations:
                if (
                    not isinstance(operation, Mapping)
                    or set(operation)
                    != {
                        "action",
                        "authorized",
                        "feasible",
                        "represented_forbidden",
                    }
                    or any(
                        not isinstance(operation[name], bool)
                        for name in (
                            "authorized",
                            "feasible",
                            "represented_forbidden",
                        )
                    )
                ):
                    raise FieldIntelligenceError(
                        "INVALID_TEMPORAL",
                        "each operation must carry action, authority, feasibility, and represented safety",
                    )
                normalized_operations.append(
                    {
                        "action": _identifier(operation["action"], "action"),
                        "authorized": operation["authorized"],
                        "feasible": operation["feasible"],
                        "represented_forbidden": operation[
                            "represented_forbidden"
                        ],
                    }
                )
            if len({row["action"] for row in normalized_operations}) != len(
                normalized_operations
            ):
                raise FieldIntelligenceError(
                    "INVALID_TEMPORAL", "operation actions must be unique"
                )
            margin_floor = _finite(
                minimum_margin, "minimum_margin", nonnegative=True
            )
            if expected_state_sha256 is not None:
                expected_state_sha256 = _digest(
                    expected_state_sha256, "expected state"
                )
                if expected_state_sha256 != self.state.state_sha256:
                    raise FieldIntelligenceError(
                        "LINEAGE_CONFLICT",
                        "selection predecessor does not match current state",
                    )
            before_state_sha256 = self.state.state_sha256
            before_manifest_sha256 = self.checkpoints.current_manifest_sha256
            row = self._temporal_memory(memory_id)
            before_memory_sha256 = row.state_sha256
            workspace = self.state.resonant_workspace
            before_workspace_sha256 = (
                None if workspace is None else workspace.state_sha256
            )
            categorical = self._temporal_apply(
                row.admissible_skill_actions,
                requested_skills,
                participant_id=participant_id,
            )
            operation_by_action: dict[str, dict[str, Any]] = {
                operation["action"]: operation
                for operation in normalized_operations
            }
            candidates = []
            excluded = [
                {
                    **dict(candidate),
                    "exclusion_reason": f"categorical-{candidate['status']}",
                }
                for candidate in categorical["excluded"]
            ]
            for candidate_value in categorical["candidates"]:
                candidate = dict(candidate_value)
                operation = operation_by_action.get(candidate["action"])
                if operation is None:
                    excluded.append(
                        {
                            **candidate,
                            "exclusion_reason": "operation-unavailable",
                        }
                    )
                    continue
                reason = None
                if operation["represented_forbidden"]:
                    reason = "represented-forbidden"
                elif not operation["authorized"]:
                    reason = "unauthorized"
                elif not operation["feasible"]:
                    reason = "infeasible"
                if reason is not None:
                    excluded.append(
                        {**candidate, "exclusion_reason": reason}
                    )
                    continue
                candidates.append(
                    {
                        **candidate,
                        "operation": operation.copy(),
                    }
                )
            candidates.sort(key=lambda candidate: candidate["candidate_sha256"])
            excluded.sort(key=lambda candidate: candidate["candidate_sha256"])
            candidate_set_sha256 = sha256_value(
                [candidate["candidate_sha256"] for candidate in candidates]
            )
            status = "unresolved"
            reason = "no-admissible-candidate"
            selected: Mapping[str, Any] | None = None
            scoring: Mapping[str, Any] | None = None
            selection_margin: float | None = None
            distinct_actions = {candidate["action"] for candidate in candidates}
            if len(candidates) == 1:
                status = "selected"
                reason = "categorical-singleton"
                selected = {
                    "action": candidates[0]["action"],
                    "candidate_sha256": candidates[0]["candidate_sha256"],
                    "skill_id": candidates[0]["skill_id"],
                    "supporting_skill_ids": [candidates[0]["skill_id"]],
                }
            elif candidates and len(distinct_actions) == 1:
                status = "selected"
                reason = "categorical-action-consensus"
                selected = {
                    "action": candidates[0]["action"],
                    "candidate_sha256": None,
                    "skill_id": None,
                    "supporting_skill_ids": sorted(
                        candidate["skill_id"] for candidate in candidates
                    ),
                }
            elif candidates and workspace is None:
                reason = "resonant-workspace-unavailable"
            elif len(candidates) > 1 and workspace is not None:
                try:
                    scoring = score_pool_probes(
                        workspace,
                        {
                            candidate["candidate_sha256"]: candidate["pool_signal"]
                            for candidate in candidates
                        },
                    )
                except ResonantNumericalError as exc:
                    raise FieldIntelligenceError(
                        "RESONANT_NUMERICAL", str(exc)
                    ) from exc
                scores = {
                    score["probe_id"]: score
                    for score in scoring["scores"]
                }
                candidates = [
                    {
                        **candidate,
                        "resonant_score": dict(
                            scores[candidate["candidate_sha256"]]
                        ),
                    }
                    for candidate in candidates
                ]
                ranked = sorted(
                    candidates,
                    key=lambda candidate: -float(
                        candidate["resonant_score"]["compatibility"]
                    ),
                )
                selection_margin = float(
                    ranked[0]["resonant_score"]["compatibility"]
                    - ranked[1]["resonant_score"]["compatibility"]
                )
                if selection_margin > margin_floor:
                    status = "selected"
                    reason = "resonant-compatibility"
                    selected = {
                        "action": ranked[0]["action"],
                        "candidate_sha256": ranked[0]["candidate_sha256"],
                        "skill_id": ranked[0]["skill_id"],
                        "supporting_skill_ids": [ranked[0]["skill_id"]],
                    }
                else:
                    reason = "insufficient-resonant-margin"
            if (
                self.state.state_sha256 != before_state_sha256
                or self.checkpoints.current_manifest_sha256
                != before_manifest_sha256
                or self._temporal_memory(memory_id).state_sha256
                != before_memory_sha256
                or (
                    None
                    if self.state.resonant_workspace is None
                    else self.state.resonant_workspace.state_sha256
                )
                != before_workspace_sha256
            ):
                raise FieldIntelligenceError(
                    "READ_ONLY_VIOLATION", "action selection mutated persistent state"
                )
            result = {
                "schema": "cassifi.temporal-resonant-action-selection.v1",
                "status": status,
                "reason": reason,
                "memory_id": row.memory_id,
                "participant_id": participant_id,
                "state_sha256": before_state_sha256,
                "manifest_sha256": before_manifest_sha256,
                "categorical_state_sha256": before_memory_sha256,
                "memory_sha256": row.memory_sha256,
                "resonant_workspace_state_sha256": before_workspace_sha256,
                "field_ticks": (
                    None if workspace is None else workspace.field_ticks
                ),
                "evidence_tick": (
                    None if workspace is None else workspace.evidence_tick
                ),
                "presented_skill_ids": list(requested_skills),
                "presentation_order_sha256": categorical[
                    "presentation_order_sha256"
                ],
                "candidate_set_sha256": candidate_set_sha256,
                "operations_sha256": sha256_value(normalized_operations),
                "minimum_margin": margin_floor,
                "selection_margin": selection_margin,
                "candidates": candidates,
                "excluded": excluded,
                "selected": selected,
                "resonant_scoring": scoring,
                "read_only": True,
                "memory_unchanged": True,
                "workspace_unchanged": True,
            }
            result["decision_sha256"] = sha256_value(result)
            return result

    def bind_temporal(
        self, operation_id: str, *, memory_id: str, participant_id: str,
        known_start: bool = True, expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            if not isinstance(known_start, bool):
                raise FieldIntelligenceError("INVALID_TEMPORAL", "known_start must be boolean")
            request = {
                "kind": "bind-temporal", "memory_id": _identifier(memory_id, "memory_id"),
                "participant_id": _identifier(participant_id, "participant_id"),
                "known_start": known_start, "expected_state_sha256": expected_state_sha256,
            }
            replay = self._temporal_replay(operation_id, request)
            if replay is not None:
                return replay
            self._require_temporal_idle(memory_id, participant_id)
            row = self._temporal_apply(
                self._temporal_memory(memory_id).bind, participant_id, known_start=known_start,
            )
            return self._publish_temporal(operation_id, request, self._temporal_successor(row, request), {
                "memory_id": memory_id, "participant_id": participant_id,
                "memory_sha256": row.memory_sha256, "state_sha256": row.state_sha256,
            })

    def inquire_temporal(
        self, memory_id: str, *, operations: Sequence[Mapping[str, Any]],
        participant_id: str | None = None, skill_id: str | None = None,
        goal_observations: Sequence[str] = (),
        horizon: int = 3, max_nodes: int = 4096,
        forbidden_observations: Sequence[str] = (),
    ) -> Mapping[str, Any]:
        with self._lock:
            return self._temporal_apply(
                choose_temporal_inquiry, self._temporal_memory(memory_id),
                participant_id=participant_id, operations=operations, skill_id=skill_id,
                goal_observations=goal_observations,
                horizon=horizon, max_nodes=max_nodes,
                forbidden_observations=forbidden_observations,
            )

    def _temporal_task(self, task_id: str) -> PlanRecord:
        _identifier(task_id, "task_id")
        for plan in self.state.plans:
            if plan.goal.get("kind") == "temporal-task" and plan.goal_id == task_id:
                return plan
        raise FieldIntelligenceError("TEMPORAL_TASK_NOT_FOUND", "temporal task does not exist")

    def _temporal_task_view(self, plan: PlanRecord) -> Mapping[str, Any]:
        steps: list[Mapping[str, Any]] = []
        pending = None
        next_step = None
        for index, segment in enumerate(plan.segments):
            binding = dict(segment.payload["binding"])
            decision: Mapping[str, Any] = {"status": "unresolved", "action": None}
            if plan.status != "invalidated":
                memory = self._temporal_memory(binding["memory_id"])
                decision = self._temporal_apply(
                    memory.skill_action, binding["skill_id"],
                    participant_id=binding["participant_id"],
                )
            status = segment.status
            if plan.status == "invalidated":
                status = "invalidated"
            elif status != "completed":
                status = {"complete": "completed", "proposed": "ready"}.get(decision["status"], "unresolved")
            proposal = segment.payload.get("pending")
            if proposal is not None:
                pending = dict(proposal)
                status = "ready" if plan.status != "invalidated" else "invalidated"
            if next_step is None and (status != "completed" or proposal is not None):
                next_step = index
            steps.append({**binding, "status": status, "decision": dict(decision)})
        status = "invalidated" if plan.status == "invalidated" else (
            "complete" if next_step is None else (
                "pending" if pending is not None else
                "ready" if steps[next_step]["status"] == "ready" else "unresolved"
            )
        )
        return {
            "task_id": plan.goal_id, "context": dict(plan.goal["context"]),
            "steps": steps, "status": status, "next_step": next_step,
            "pending_proposal": pending, "state_sha256": self.state.state_sha256,
        }

    def inspect_temporal_task(self, task_id: str) -> Mapping[str, Any]:
        with self._lock:
            return self._temporal_task_view(self._temporal_task(task_id))

    def compose_temporal_task(
        self, operation_id: str, *, task_id: str, steps: Sequence[Mapping[str, str]],
        context: Mapping[str, Any] | None = None, expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            _identifier(task_id, "task_id")
            if not isinstance(steps, (list, tuple)) or not 1 <= len(steps) <= 64:
                raise FieldIntelligenceError("INVALID_TEMPORAL", "task needs one to 64 bound skill goals")
            if context is not None and not isinstance(context, Mapping):
                raise FieldIntelligenceError("INVALID_TEMPORAL", "task context must be an object")
            normalized = []
            for step in steps:
                if not isinstance(step, Mapping) or set(step) != {"memory_id", "participant_id", "skill_id"}:
                    raise FieldIntelligenceError("INVALID_TEMPORAL", "task step must bind a memory, participant and skill")
                normalized.append({key: _identifier(step[key], key) for key in ("memory_id", "participant_id", "skill_id")})
            request = {
                "kind": "compose-temporal-task", "task_id": task_id, "steps": normalized,
                "context": dict(context or {}), "expected_state_sha256": expected_state_sha256,
            }
            replay = self._temporal_replay(operation_id, request)
            if replay is not None:
                return replay
            if any(plan.goal_id == task_id for plan in self.state.plans):
                raise FieldIntelligenceError("OPERATION_CONFLICT", "task identity is already occupied")
            sources: set[str] = set()
            segments = []
            for index, binding in enumerate(normalized):
                memory = self._temporal_memory(binding["memory_id"])
                if binding["participant_id"] not in memory.participant_ids or binding["skill_id"] not in memory.skill_ids:
                    raise FieldIntelligenceError("INVALID_TEMPORAL", "task binding or skill does not exist")
                if dict(memory.context) != request["context"]:
                    raise FieldIntelligenceError("TEMPORAL_SCOPE_CONFLICT", "task and all memories must have identical context")
                sources.update(memory.source_revision_ids)
                segments.append(PlanSegment(
                    segment_id=f"{task_id}:{index}", level="tactical", kind="action",
                    payload={"binding": binding, "pending": None},
                    dependency_versions=(),
                ))
            plan = PlanRecord(
                plan_id=sha256_value({"kind": "temporal-task", "task_id": task_id}),
                goal_id=task_id, goal={"kind": "temporal-task", "context": request["context"]},
                assumptions={}, segments=tuple(segments),
                source_revision_ids=tuple(sorted(sources)), authority_generation=self.authority_generation,
            )
            successor = self.state.with_transition(
                request["kind"], {"task_id": task_id}, plans=(*self.state.plans, plan),
            )
            return self._publish_temporal(operation_id, request, successor, {
                "task_id": task_id, "step_count": len(segments), "execution_authorized": False,
            })

    def propose_temporal_task(
        self, operation_id: str, *, task_id: str,
        allowed_actions: Sequence[Mapping[str, str]], expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        """Publish an idempotent proposal; the external adapter still owns permission and execution."""
        with self._lock:
            if not isinstance(allowed_actions, (list, tuple)) or len(allowed_actions) > 4096:
                raise FieldIntelligenceError("INVALID_TEMPORAL", "allowed actions must be a bounded array")
            allowed = []
            for item in allowed_actions:
                if not isinstance(item, Mapping) or set(item) != {"participant_id", "action"}:
                    raise FieldIntelligenceError("INVALID_TEMPORAL", "allowed action must identify its participant")
                allowed.append({key: _identifier(item[key], key) for key in ("participant_id", "action")})
            request = {
                "kind": "propose-temporal-task", "task_id": _identifier(task_id, "task_id"),
                "allowed_actions": allowed, "expected_state_sha256": expected_state_sha256,
            }
            replay = self._temporal_replay(operation_id, request)
            if replay is not None:
                return replay
            plan = self._temporal_task(task_id)
            view = self._temporal_task_view(plan)
            index = view["next_step"]
            proposal = view["pending_proposal"]
            action = None
            if index is not None and view["status"] != "invalidated":
                step = view["steps"][index]
                decision = step["decision"]
                action = decision["action"] if decision["status"] == "proposed" else None
                if proposal is not None and action != proposal["action"]:
                    action = None
                if {"participant_id": step["participant_id"], "action": action} not in allowed:
                    action = None
            segments = [
                replace(segment, status="completed") if step["status"] == "completed" else segment
                for segment, step in zip(plan.segments, view["steps"], strict=True)
            ]
            status = "complete" if view["status"] == "complete" else "unresolved"
            if action is not None and index is not None:
                step = view["steps"][index]
                if proposal is None:
                    self._require_temporal_idle(step["memory_id"], step["participant_id"])
                    proposal = {
                        "proposal_id": sha256_value({"operation_id": operation_id, "request": request,
                                                     "predecessor": self.state.state_sha256}),
                        "task_id": task_id, "step_index": index,
                        "participant_id": step["participant_id"], "memory_id": step["memory_id"],
                        "skill_id": step["skill_id"], "action": action,
                    }
                    segment = segments[index]
                    segments[index] = replace(segment, payload={**dict(segment.payload), "pending": proposal}, status="ready")
                status = "proposed"
            updated = replace(plan, segments=tuple(segments),
                              status="completed" if status == "complete" else plan.status)
            successor = self.state.with_transition(
                request["kind"], {"task_id": task_id},
                plans=tuple(updated if item.plan_id == plan.plan_id else item for item in self.state.plans),
            )
            return self._publish_temporal(operation_id, request, successor, {
                "task_id": task_id, "status": status, "action": action,
                "proposal": proposal if action is not None else None,
                "execution_authorized": False,
                "reason": "supported bound skill" if action is not None else view["status"],
            })

    def acknowledge_temporal_task(
        self, operation_id: str, *, task_id: str, proposal_id: str,
        participant_id: str, action: str, observation: str,
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            request = {
                "kind": "acknowledge-temporal-task", "task_id": _identifier(task_id, "task_id"),
                "proposal_id": _digest(proposal_id, "proposal_id"),
                "participant_id": _identifier(participant_id, "participant_id"),
                "action": _identifier(action, "action"), "observation": _identifier(observation, "observation"),
                "expected_state_sha256": expected_state_sha256,
            }
            replay = self._temporal_replay(operation_id, request)
            if replay is not None:
                return replay
            plan = self._temporal_task(task_id)
            if plan.status == "invalidated":
                raise FieldIntelligenceError("STALE_REVOCATION", "task support has been revoked")
            matches = [(index, segment, segment.payload.get("pending")) for index, segment in enumerate(plan.segments)
                       if segment.payload.get("pending") is not None]
            if len(matches) != 1:
                raise FieldIntelligenceError("OPERATION_CONFLICT", "task has no unique outstanding proposal")
            index, segment, proposal = matches[0]
            if not isinstance(proposal, Mapping):
                raise FieldIntelligenceError("INVALID_STATE", "pending task proposal is corrupt")
            if any(proposal[key] != request[key] for key in ("proposal_id", "participant_id", "action", "task_id")):
                raise FieldIntelligenceError("OPERATION_CONFLICT", "acknowledgment does not match the exact bound proposal")
            memory, consumed = self._temporal_apply(
                self._temporal_memory(proposal["memory_id"]).consume,
                action, observation, participant_id=participant_id,
            )
            decision = self._temporal_apply(memory.skill_action, proposal["skill_id"], participant_id=participant_id)
            segments = list(plan.segments)
            segments[index] = replace(
                segment, payload={**dict(segment.payload), "pending": None},
                status="completed" if decision["status"] == "complete" else
                       "ready" if decision["status"] == "proposed" else "unresolved",
            )
            complete = all(item.status == "completed" for item in segments)
            updated = replace(plan, segments=tuple(segments), status="completed" if complete else "open")
            successor = self.state.with_transition(
                request["kind"], {"task_id": task_id, "proposal_id": proposal_id},
                temporal_fields=tuple(memory if item.memory_id == memory.memory_id else item for item in self.state.temporal_fields),
                plans=tuple(updated if item.plan_id == plan.plan_id else item for item in self.state.plans),
            )
            return self._publish_temporal(operation_id, request, successor, {
                "task_id": task_id, "proposal_id": proposal_id, "consumed": dict(consumed),
                "status": "complete" if complete else decision["status"],
                "execution_authorized": False,
            })

    def _validate_transceiver_sources(
        self,
        state: AtlasState,
        *,
        transceiver_ids: Sequence[str] = (),
    ) -> tuple[str, ...]:
        """Reject selected active transceiver work whose source authority is stale."""
        active = set(self.evidence.active_revision_ids())
        selected = set(transceiver_ids)
        source_ids: set[str] = set()
        for transceiver in state.transceivers:
            if transceiver.transceiver_id not in selected:
                continue
            if transceiver.status != "active":
                continue
            sources = tuple(transceiver.source_revision_ids)
            if not set(sources).issubset(active):
                raise FieldIntelligenceError(
                    "STALE_REVOCATION",
                    "transceiver depends on a revoked or superseded source",
                    details={"transceiver_id": transceiver.transceiver_id},
                )
            source_ids.update(sources)
        return tuple(sorted(source_ids))

    @staticmethod
    def _transceiver_request(
        *,
        transceiver_id: str,
        chart_ids: Sequence[str] = (),
        input_ids: Sequence[str] = (),
        output_ids: Sequence[str] = (),
        context: Mapping[str, Any] | None = None,
        observed: Mapping[str, float] | None = None,
        rank: int = 16,
        error_allowance: float = 1e-3,
        input_bound: float = 4.0,
        horizon_ticks: int = 64,
    ) -> Mapping[str, Any]:
        transceiver_id = _identifier(transceiver_id, "transceiver_id")
        def ids(value: Sequence[str], label: str) -> list[str]:
            if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
                raise FieldIntelligenceError("INVALID_REQUEST", f"{label} must be a sequence")
            return [_identifier(item, label) for item in value]
        if context is None:
            context = {}
        if not isinstance(context, Mapping):
            raise FieldIntelligenceError("INVALID_REQUEST", "transceiver context must be an object")
        if observed is not None and not isinstance(observed, Mapping):
            raise FieldIntelligenceError("INVALID_REQUEST", "transceiver observed values must be an object")
        normalized_observed = None if observed is None else {
            _identifier(name, "observed variable"): _finite(value, "observed value")
            for name, value in observed.items()
        }
        rank = _integer(rank, "rank", minimum=1)
        error_allowance = _finite(error_allowance, "error_allowance", nonnegative=True)
        input_bound = _finite(input_bound, "input_bound", nonnegative=True)
        horizon_ticks = _integer(horizon_ticks, "horizon_ticks", minimum=1)
        return {
            "transceiver_id": transceiver_id,
            "chart_ids": ids(chart_ids, "chart_id"),
            "input_ids": ids(input_ids, "input_id"),
            "output_ids": ids(output_ids, "output_id"),
            "context": dict(context),
            "observed": normalized_observed,
            "rank": rank,
            "error_allowance": error_allowance,
            "input_bound": input_bound,
            "horizon_ticks": horizon_ticks,
        }
    @staticmethod
    def _transceiver_receipt_semantics(value: Any) -> Any:
        """Normalize timing values while retaining their required structural positions."""
        if isinstance(value, Mapping):
            normalized: dict[str, Any] = {}
            for key, item in value.items():
                if key == "elapsed_seconds":
                    _finite(item, "transceiver elapsed_seconds", nonnegative=True)
                    normalized[key] = 0.0
                else:
                    normalized[key] = FieldIntelligenceOwner._transceiver_receipt_semantics(
                        item
                    )
            return normalized
        if isinstance(value, (list, tuple)):
            return [
                FieldIntelligenceOwner._transceiver_receipt_semantics(item)
                for item in value
            ]
        return value

    def _validate_transceiver_replay_result(
        self,
        *,
        manifest: Mapping[str, Any],
        request: Mapping[str, Any],
        result: Mapping[str, Any],
        expected_kind: str,
    ) -> None:
        """Recompute a stored transceiver operation from its authenticated predecessor."""
        try:
            raw_receipt = result["receipt"]
            if not isinstance(raw_receipt, Mapping):
                raise TypeError("transceiver receipt is not an object")
            parent_sha256 = manifest["parent_manifest_sha256"]
            if parent_sha256 is None:
                raise ValueError("transceiver operation has no predecessor")
            parent = self.checkpoints._load_state(
                self.checkpoints._manifest(parent_sha256)
            )
            successor = self.checkpoints._load_state(manifest)

            if expected_kind == "condense-transceiver":
                recomputed, expected_receipt = self.atlas.condense_transceiver(
                    parent,
                    transceiver_id=request["transceiver_id"],
                    chart_ids=tuple(request["chart_ids"]),
                    input_ids=tuple(request["input_ids"]),
                    output_ids=tuple(request["output_ids"]),
                    context=request["context"],
                    observed=request["observed"],
                    rank=request["rank"],
                    error_allowance=request["error_allowance"],
                    input_bound=request["input_bound"],
                    horizon_ticks=request["horizon_ticks"],
                )
            elif expected_kind == "advance-transceivers":
                recomputed, expected_receipt = self.atlas.advance_transceivers(
                    parent,
                    stimuli=request["stimuli"],
                    context=request["context"],
                    ticks=request["ticks"],
                    connections=tuple(request["connections"]),
                    force_full=request["force_full"],
                )
            elif expected_kind == "reset-transceiver":
                recomputed, expected_receipt = self.atlas.reset_transceiver(
                    parent,
                    transceiver_id=request["transceiver_id"],
                )
            else:
                raise ValueError("unsupported transceiver replay kind")

            receipt = self._transceiver_receipt_semantics(raw_receipt)
            expected = self._transceiver_receipt_semantics(expected_receipt)
            if (
                recomputed.state_sha256 != successor.state_sha256
                or canonical_json_bytes(receipt) != canonical_json_bytes(expected)
            ):
                raise ValueError(
                    "transceiver replay disagrees with its committed successor"
                )
        except (
            FieldIntelligenceError,
            KeyError,
            ResonantNumericalError,
            TypeError,
            ValueError,
        ) as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT",
                "committed transceiver result cannot be decoded safely",
            ) from exc

    def condense_transceiver(
        self,
        operation_id: str,
        *,
        transceiver_id: str,
        chart_ids: Sequence[str],
        input_ids: Sequence[str],
        output_ids: Sequence[str],
        context: Mapping[str, Any],
        observed: Mapping[str, float] | None = None,
        rank: int = 16,
        error_allowance: float = 1e-3,
        input_bound: float = 4.0,
        horizon_ticks: int = 64,
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            _identifier(operation_id, "operation_id")
            request = self._transceiver_request(
                transceiver_id=transceiver_id, chart_ids=chart_ids, input_ids=input_ids,
                output_ids=output_ids, context=context, observed=observed, rank=rank,
                error_allowance=error_allowance, input_bound=input_bound,
                horizon_ticks=horizon_ticks,
            )
            if expected_state_sha256 is not None:
                expected_state_sha256 = _digest(expected_state_sha256, "expected state")
            request = {**request, "expected_state_sha256": expected_state_sha256}
            request_sha256 = sha256_value(request)
            committed = self._committed_result(
                operation_id,
                expected_kind="condense-transceiver",
                expected_request=request,
                expected_result_keys=frozenset({"receipt"}),
                expected_mapping_result_fields=frozenset({"receipt"}),
                require_retained=True,
            )
            if committed is not None:
                manifest, replay, receipt = committed
                self._validate_transceiver_replay_result(
                    manifest=manifest,
                    request=request,
                    result=replay,
                    expected_kind="condense-transceiver",
                )
                replay["checkpoint_receipt"] = receipt.as_dict()
                return replay
            if expected_state_sha256 is not None and expected_state_sha256 != self.state.state_sha256:
                raise FieldIntelligenceError("LINEAGE_CONFLICT", "transceiver predecessor does not match current state")
            active_sources = set(self.evidence.active_revision_ids())
            chart_lookup = {chart.chart_id: chart for chart in self.state.charts}
            chart_sources: set[str] = set()
            for chart_id in chart_ids:
                chart = chart_lookup.get(_identifier(chart_id, "chart_id"))
                if chart is None:
                    raise FieldIntelligenceError("INVALID_CHART", "transceiver chart is unavailable")
                chart_sources.update(chart.active_source_revisions())
            if not chart_sources.issubset(active_sources):
                raise FieldIntelligenceError(
                    "STALE_REVOCATION",
                    "transceiver chart depends on a revoked or superseded source",
                )
            if len(chart_sources) > self.limits.max_source_work:
                raise FieldIntelligenceError("WORK_CAPACITY", "transceiver source work exceeds configured limit")
            successor, receipt = self.atlas.condense_transceiver(
                self.state, transceiver_id=request["transceiver_id"],
                chart_ids=tuple(request["chart_ids"]), input_ids=tuple(request["input_ids"]),
                output_ids=tuple(request["output_ids"]), context=request["context"],
                observed=request["observed"], rank=request["rank"],
                error_allowance=request["error_allowance"], input_bound=request["input_bound"],
                horizon_ticks=request["horizon_ticks"],
            )
            self._check_capacity(successor)
            result: dict[str, Any] = {"receipt": dict(receipt)}
            transition = {
                "kind": "condense-transceiver", "request_sha256": request_sha256,
                "request": request, "result": result,
            }
            checkpoint = self._publish(operation_id=operation_id, successor=successor, event_id=None, transition=transition)
            result["checkpoint_receipt"] = checkpoint.as_dict()
            return result

    def advance_transceivers(
        self,
        operation_id: str,
        *,
        stimuli: Mapping[str, Mapping[str, float]],
        context: Mapping[str, Any],
        ticks: int = 1,
        connections: Sequence[Mapping[str, str]] = (),
        force_full: bool = False,
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            _identifier(operation_id, "operation_id")
            ticks = _integer(ticks, "ticks", minimum=1)
            if ticks > self.limits.max_ticks_per_batch:
                raise FieldIntelligenceError("WORK_CAPACITY", "transceiver tick budget exceeds configured limit")
            if expected_state_sha256 is not None:
                expected_state_sha256 = _digest(expected_state_sha256, "expected state")
            if not isinstance(context, Mapping):
                raise FieldIntelligenceError("INVALID_REQUEST", "transceiver context must be an object")
            if not isinstance(stimuli, Mapping):
                raise FieldIntelligenceError("INVALID_REQUEST", "transceiver stimuli must be an object")
            normalized_stimuli: dict[str, dict[str, float]] = {}
            for transceiver_key, values in stimuli.items():
                transceiver_key = _identifier(transceiver_key, "transceiver_id")
                if not isinstance(values, Mapping):
                    raise FieldIntelligenceError("INVALID_REQUEST", "transceiver stimulus must be an object")
                normalized_stimuli[transceiver_key] = {
                    _identifier(input_id, "input_id"): _finite(value, "stimulus")
                    for input_id, value in values.items()
                }
            if isinstance(connections, (str, bytes)) or not isinstance(connections, Sequence):
                raise FieldIntelligenceError("INVALID_REQUEST", "transceiver connections must be a sequence")
            normalized_connections: list[dict[str, str]] = []
            for connection in connections:
                if not isinstance(connection, Mapping) or set(connection) != {"source", "output", "target", "input"}:
                    raise FieldIntelligenceError("INVALID_REQUEST", "transceiver connection is malformed")
                normalized_connections.append({
                    key: _identifier(connection[key], f"connection.{key}")
                    for key in ("source", "output", "target", "input")
                })
            if not isinstance(force_full, bool):
                raise FieldIntelligenceError("INVALID_REQUEST", "force_full must be boolean")
            request = {
                "stimuli": normalized_stimuli,
                "context": dict(context), "ticks": ticks,
                "connections": normalized_connections,
                "force_full": force_full,
                "expected_state_sha256": expected_state_sha256,
            }
            request_sha256 = sha256_value(request)
            committed = self._committed_result(
                operation_id,
                expected_kind="advance-transceivers",
                expected_request=request,
                expected_result_keys=frozenset({"receipt"}),
                expected_mapping_result_fields=frozenset({"receipt"}),
                require_retained=True,
            )
            if committed is not None:
                manifest, replay, receipt = committed
                self._validate_transceiver_replay_result(
                    manifest=manifest,
                    request=request,
                    result=replay,
                    expected_kind="advance-transceivers",
                )
                replay["checkpoint_receipt"] = receipt.as_dict()
                return replay
            if expected_state_sha256 is not None and expected_state_sha256 != self.state.state_sha256:
                raise FieldIntelligenceError("LINEAGE_CONFLICT", "transceiver predecessor does not match current state")
            selected_ids = set(normalized_stimuli)
            for connection in normalized_connections:
                selected_ids.update((connection["source"], connection["target"]))
            if not selected_ids:
                selected_ids = {
                    row.transceiver_id
                    for row in self.state.transceivers
                    if row.matches(dict(context))
                }
            source_ids = self._validate_transceiver_sources(
                self.state, transceiver_ids=tuple(sorted(selected_ids))
            )
            if len(source_ids) > self.limits.max_source_work:
                raise FieldIntelligenceError("WORK_CAPACITY", "transceiver source work exceeds configured limit")
            successor, receipt = self.atlas.advance_transceivers(
                self.state, stimuli=request["stimuli"], context=request["context"], ticks=request["ticks"],
                connections=tuple(request["connections"]), force_full=request["force_full"],
            )
            self._check_capacity(successor)
            result: dict[str, Any] = {"receipt": dict(receipt)}
            transition = {"kind": "advance-transceivers", "request_sha256": request_sha256, "request": request, "result": result}
            checkpoint = self._publish(operation_id=operation_id, successor=successor, event_id=None, transition=transition)
            result["checkpoint_receipt"] = checkpoint.as_dict()
            return result

    def reset_transceiver(
        self,
        operation_id: str,
        *,
        transceiver_id: str,
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            _identifier(operation_id, "operation_id")
            transceiver_id = _identifier(transceiver_id, "transceiver_id")
            if expected_state_sha256 is not None:
                expected_state_sha256 = _digest(expected_state_sha256, "expected state")
            request = {"transceiver_id": transceiver_id, "expected_state_sha256": expected_state_sha256}
            request_sha256 = sha256_value(request)
            committed = self._committed_result(
                operation_id,
                expected_kind="reset-transceiver",
                expected_request=request,
                expected_result_keys=frozenset({"receipt"}),
                expected_mapping_result_fields=frozenset({"receipt"}),
                require_retained=True,
            )
            if committed is not None:
                manifest, replay, receipt = committed
                self._validate_transceiver_replay_result(
                    manifest=manifest,
                    request=request,
                    result=replay,
                    expected_kind="reset-transceiver",
                )
                replay["checkpoint_receipt"] = receipt.as_dict()
                return replay
            if expected_state_sha256 is not None and expected_state_sha256 != self.state.state_sha256:
                raise FieldIntelligenceError("LINEAGE_CONFLICT", "transceiver predecessor does not match current state")
            successor, receipt = self.atlas.reset_transceiver(
                self.state, transceiver_id=transceiver_id
            )
            self._check_capacity(successor)
            result: dict[str, Any] = {"receipt": dict(receipt)}
            transition = {"kind": "reset-transceiver", "request_sha256": request_sha256, "request": request, "result": result}
            checkpoint = self._publish(operation_id=operation_id, successor=successor, event_id=None, transition=transition)
            result["checkpoint_receipt"] = checkpoint.as_dict()
            return result

    def inspect_transceivers(self) -> Mapping[str, Any]:
        with self._lock:
            value = dict(self.atlas.inspect_transceivers(self.state))
            value["state_sha256"] = self.state.state_sha256
            value["manifest_sha256"] = self.checkpoints.current_manifest_sha256
            value["generation"] = self.state.generation
            return value

    def exact_recall(
        self,
        *,
        revision_id: str,
        allowed_labels: frozenset[str],
        span: tuple[int, int] | None = None,
        allow_historical: bool = False,
    ) -> Mapping[str, Any]:
        source = self.evidence.source(revision_id)
        content = self.evidence.read(
            source,
            allow_historical=allow_historical,
            allowed_labels=allowed_labels,
        )
        selected_span = span if span is not None else source.span
        if selected_span is not None:
            if not 0 <= selected_span[0] <= selected_span[1] <= len(content):
                raise FieldIntelligenceError("SOURCE_SPAN", "requested source span is invalid")
            selected = content[selected_span[0] : selected_span[1]]
        else:
            selected = content
        return {
            "bytes_base64": base64.b64encode(selected).decode("ascii"),
            "codec": source.codec,
            "content_sha256": hashlib.sha256(selected).hexdigest(),
            "full_revision_sha256": source.content_sha256,
            "revision_id": source.revision_id,
            "source_id": source.source_id,
            "span": None if selected_span is None else list(selected_span),
            "status": source.status,
        }

    @staticmethod
    def _readout_from_dict(value: Mapping[str, Any]) -> ActionReadout:
        return ActionReadout(
            readout_id=value["readout_id"],
            version=value["version"],
            labels=tuple(value["labels"]),
            coefficients=tuple(value["coefficients"]),
            observed_error_radius=value["observed_error_radius"],
            observation_error_map=(
                None
                if value["observation_error_map"] is None
                else tuple(tuple(row) for row in value["observation_error_map"])
            ),
        )
    def action_decision(
        self,
        *,
        observed: Mapping[str, float],
        readout: ActionReadout,
        context: Mapping[str, Any] | None = None,
        authority_current: bool = False,
        task_feasible: bool = True,
        model_applicable: bool = True,
        prepared_query: QueryResult | Mapping[str, Any] | None = None,
    ) -> ActionDecision:
        prepared = _query_result(prepared_query) if prepared_query is not None else None
        return self.cognition.certify_action(
            self.state,
            observed=observed,
            readout=readout,
            context=context,
            valid_source_revision_ids=self.evidence.active_revision_ids(),
            authority_current=authority_current,
            task_feasible=task_feasible,
            model_applicable=model_applicable,
            prepared_query=prepared,
        )
    def propose_effect(
        self,
        *,
        operation_id: str,
        observed: Mapping[str, float],
        readout: ActionReadout,
        target: str,
        scope: str,
        payload: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
        goal_id: str | None = None,
        task_feasible: bool = True,
        model_applicable: bool = True,
        prepared_query: QueryResult | Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            operation_id = _identifier(operation_id, "operation_id")
            target = _identifier(target, "effect target")
            scope = _identifier(scope, "effect scope")
            if not isinstance(observed, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_REQUEST", "effect observations must be an object"
                )
            if not isinstance(readout, ActionReadout):
                raise FieldIntelligenceError(
                    "INVALID_REQUEST", "effect readout is invalid"
                )
            if context is not None and not isinstance(context, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_REQUEST", "effect context must be an object"
                )
            if not isinstance(payload, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_REQUEST", "effect payload must be an object"
                )
            if not isinstance(task_feasible, bool) or not isinstance(
                model_applicable, bool
            ):
                raise FieldIntelligenceError(
                    "INVALID_REQUEST",
                    "effect feasibility and applicability must be boolean",
                )
            if goal_id is not None:
                goal_id = _identifier(goal_id, "goal_id")
            normalized_observed = {
                _identifier(name, "observed variable"): _finite(
                    value, "observed value"
                )
                for name, value in observed.items()
            }
            try:
                normalized_context = json.loads(
                    canonical_json_bytes(dict(context or {})).decode("utf-8")
                )
                normalized_payload = json.loads(
                    canonical_json_bytes(dict(payload)).decode("utf-8")
                )
            except (TypeError, ValueError) as exc:
                raise FieldIntelligenceError(
                    "INVALID_REQUEST",
                    "effect context and payload must be canonical JSON",
                ) from exc
            prepared_input = (
                None
                if prepared_query is None
                else _query_result(prepared_query)
            )
            proposal_request = json.loads(
                canonical_json_bytes(
                    {
                        "context": normalized_context,
                        "goal_id": goal_id,
                        "model_applicable": model_applicable,
                        "observed": normalized_observed,
                        "payload": normalized_payload,
                        "prepared_query": (
                            None
                            if prepared_input is None
                            else prepared_input.as_dict()
                        ),
                        "readout": readout.as_dict(),
                        "scope": scope,
                        "target": target,
                        "task_feasible": task_feasible,
                    }
                ).decode("utf-8")
            )
            proposal_request_sha256 = sha256_value(proposal_request)
            prior = next(
                (
                    row
                    for row in self.state.predictions
                    if row.operation_id == operation_id
                ),
                None,
            )
            if prior is not None:
                if (
                    prior.query.get("proposal_request_sha256")
                    != proposal_request_sha256
                ):
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "effect operation identity has different proposal semantics",
                    )
                committed = self._committed_result(
                    f"proposal:{operation_id}",
                    expected_kind="effect-proposed",
                    expected_request=proposal_request,
                    expected_result_keys=frozenset(
                        {"decision", "prediction", "status"}
                    ),
                    expected_mapping_result_fields=frozenset(
                        {"decision", "prediction"}
                    ),
                    expected_transition_fields={
                        "prediction_id": prior.prediction_id
                    },
                )
                if committed is None:
                    if self.checkpoints.operation_compacted(
                        f"proposal:{operation_id}"
                    ):
                        raise FieldIntelligenceError(
                            "HISTORY_COMPACTED",
                            "effect proposal precedes the retained replay floor",
                        )
                    raise FieldIntelligenceError(
                        "CHECKPOINT_CORRUPT",
                        "effect proposal has no committed operation record",
                    )
                _, stored_result, receipt = committed
                original_prediction = replace(
                    prior,
                    actual=None,
                    attribution_candidates=(),
                    status="proposed",
                )
                try:
                    stored_prediction = PredictionRecord.from_dict(
                        stored_result["prediction"]
                    )
                    if (
                        stored_result["status"] != "proposed"
                        or stored_prediction != original_prediction
                        or canonical_json_bytes(stored_result["decision"])
                        != canonical_json_bytes(
                            original_prediction.query["decision"]
                        )
                    ):
                        raise ValueError("proposal replay result is inconsistent")
                except (
                    FieldIntelligenceError,
                    KeyError,
                    TypeError,
                    ValueError,
                ) as exc:
                    raise FieldIntelligenceError(
                        "CHECKPOINT_CORRUPT",
                        "committed effect proposal cannot be decoded safely",
                    ) from exc
                return {
                    "decision": json.loads(
                        canonical_json_bytes(
                            prior.query["decision"]
                        ).decode("utf-8")
                    ),
                    "prediction": prior.as_dict(),
                    "receipt": receipt.as_dict(),
                    "status": prior.status,
                }
            observed = normalized_observed
            context = normalized_context
            payload = normalized_payload
            prepared = prepared_input
            if prepared is None:
                requested = tuple(name for name in readout.variables if name not in observed)
                if not requested:
                    requested = tuple(readout.variables)
                prepared_payload = self.think(
                    f"prepare:{operation_id}",
                    observed=observed,
                    requested=requested,
                    context=context,
                )
                prepared = _query_result(prepared_payload)
            else:
                prepared = _query_result(prepared)
            decision = self.action_decision(
                observed=observed,
                readout=readout,
                context=context,
                authority_current=False,
                task_feasible=task_feasible,
                model_applicable=model_applicable,
                prepared_query=prepared,
            )
            stable = {
                row.certified_action
                for row in decision.certificates
                if row.certified_action is not None
            }
            if len(stable) != 1 or any(
                not row.numerical_valid
                or not row.evidence_valid
                or not row.model_applicable
                or not row.feasible
                for row in decision.certificates
            ):
                return {
                    "decision": decision.as_dict(),
                    "prediction_id": None,
                    "status": "unresolved",
                }
            action = next(iter(stable))
            dependency_versions = tuple(
                sorted(
                    {
                        item
                        for branch in decision.query.branches
                        for item in branch.active_chart_versions
                    }
                )
            )
            source_ids = tuple(
                sorted(
                    {
                        item
                        for branch in decision.query.branches
                        for item in branch.source_revision_ids
                    }
                )
            )
            prediction_identity = {
                "decision": decision.as_dict(),
                "field_generation": self.state.generation,
                "operation_id": operation_id,
                "payload": dict(payload),
                "scope": scope,
                "target": target,
            }
            prediction = PredictionRecord(
                prediction_id=sha256_value(prediction_identity),
                field_generation=self.state.generation,
                branch_id=decision.query.branches[0].branch_id,
                query={
                    "context": dict(context or {}),
                    "decision": decision.as_dict(),
                    "observed": dict(observed),
                    "payload": json.loads(canonical_json_bytes(dict(payload))),
                    "prepared_query": prepared.as_dict(),
                    "readout": readout.as_dict(),
                    "scope": scope,
                    "proposal_request_sha256": proposal_request_sha256,
                    "target": target,
                },
                predicted={
                    "action": action,
                    "values": {
                        name: decision.query.branches[0].values[name]
                        for name in decision.query.requested
                    },
                },
                dependency_versions=dependency_versions,
                source_revision_ids=source_ids,
                goal_id=goal_id,
                authority_generation=self.authority_generation,
                operation_id=operation_id,
                status="proposed",
            )
            existing = next(
                (
                    row
                    for row in self.state.predictions
                    if row.prediction_id == prediction.prediction_id
                ),
                None,
            )
            if existing is not None:
                raise FieldIntelligenceError(
                    "PREDICTION_CONFLICT", "effect proposal identity conflicts"
                )
            result = json.loads(
                canonical_json_bytes(
                    {
                        "decision": decision.as_dict(),
                        "prediction": prediction.as_dict(),
                        "status": "proposed",
                    }
                ).decode("utf-8")
            )
            successor = self.state.with_transition(
                "effect-proposed",
                {
                    "action": action,
                    "operation_id": operation_id,
                    "prediction_id": prediction.prediction_id,
                },
                predictions=(*self.state.predictions, prediction),
            )
            receipt = self._publish(
                operation_id=f"proposal:{operation_id}",
                successor=successor,
                event_id=None,
                transition={
                    "kind": "effect-proposed",
                    "prediction_id": prediction.prediction_id,
                    "request": proposal_request,
                    "request_sha256": proposal_request_sha256,
                    "result": result,
                },
            )
            return {**result, "receipt": receipt.as_dict()}

    def dispatch_effect(
        self,
        *,
        prediction_id: str,
        grant: AuthorityGrant,
        adapter: WorldAdapter,
    ) -> Mapping[str, Any]:
        self._prepare_world_adapter(adapter)
        with self._lock:
            prediction = next(
                (
                    row
                    for row in self.state.predictions
                    if row.prediction_id == prediction_id
                ),
                None,
            )
            if prediction is None:
                raise FieldIntelligenceError(
                    "PREDICTION_NOT_FOUND",
                    "effect prediction is unavailable",
                )
            if prediction.status == "acknowledged":
                if prediction.operation_id is not None:
                    self._clear_effect_grant_binding(
                        prediction.operation_id
                    )
                return {
                    "prediction": prediction.as_dict(),
                    "status": "already-acknowledged",
                }
            if prediction.status not in {"proposed", "pending"}:
                raise FieldIntelligenceError(
                    "PROPOSAL_STALE",
                    "effect prediction is no longer dispatchable",
                )
            target = prediction.query["target"]
            scope = prediction.query["scope"]
            operation_id = prediction.operation_id
            assert operation_id is not None
            if prediction.status == "pending":
                acknowledgment = adapter.resolve(operation_id)
                if acknowledgment is not None:
                    return self.admit_acknowledgment(
                        prediction_id=prediction_id,
                        acknowledgment=acknowledgment,
                    )
            reserved = self._effect_grant_is_reserved(prediction)
            action = prediction.predicted["action"]
            if not reserved:
                self._validate_grant(
                    grant,
                    operation="effect",
                    target=target,
                    scope=scope,
                    consume=False,
                )
            readout = self._readout_from_dict(
                prediction.query["readout"]
            )
            decision = self.action_decision(
                observed=prediction.query["observed"],
                readout=readout,
                context=prediction.query["context"],
                authority_current=True,
                prepared_query=QueryResult.from_dict(
                    prediction.query["prepared_query"]
                ),
            )
            if decision.committed_action != action:
                raise FieldIntelligenceError(
                    "PROPOSAL_STALE",
                    "current field dependencies do not reproduce the proposed action",
                    details={
                        "proposed": action,
                        "current": decision.committed_action,
                        "obligations": list(decision.obligations),
                    },
                )
            current_versions = {
                chart.chart_id: chart.version
                for chart in self.state.charts
            }
            if any(
                current_versions.get(chart_id) != version
                for chart_id, version in prediction.dependency_versions
            ) or not set(prediction.source_revision_ids).issubset(
                self.evidence.active_revision_ids()
            ):
                raise FieldIntelligenceError(
                    "PROPOSAL_STALE",
                    "effect dependencies changed before dispatch",
                )
            if not reserved:
                self._reserve_effect_grant(prediction, grant)
            if prediction.status == "proposed":
                prediction = self._publish_effect_pending(prediction)
        acknowledgment = adapter.execute_once(
            operation_id=operation_id,
            action=action,
            target=target,
            payload=prediction.query["payload"],
        )
        return self.admit_acknowledgment(
            prediction_id=prediction_id,
            acknowledgment=acknowledgment,
        )

    def admit_acknowledgment(
        self,
        *,
        prediction_id: str,
        acknowledgment: WorldAcknowledgment,
        attribution_candidates: Sequence[str] = (
            "sensor-error",
            "context-change",
            "transition-model",
            "execution-failure",
        ),
        learn_chart_ids: Sequence[str] | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            prediction_id = _identifier(prediction_id, "prediction_id")
            normalized_attribution = tuple(
                _identifier(value, "attribution candidate")
                for value in attribution_candidates
            )
            normalized_learn_chart_ids = (
                None
                if learn_chart_ids is None
                else tuple(
                    _identifier(value, "chart_id")
                    for value in learn_chart_ids
                )
            )
            prediction = next(
                (
                    row
                    for row in self.state.predictions
                    if row.prediction_id == prediction_id
                ),
                None,
            )
            if (
                prediction is None
                or prediction.operation_id != acknowledgment.operation_id
            ):
                raise FieldIntelligenceError(
                    "ACKNOWLEDGMENT_CONFLICT",
                    "acknowledgment does not join the original prediction operation",
                )
            actual = {
                "context": dict(acknowledgment.context),
                "observed_values": dict(acknowledgment.observed_values),
                "status": acknowledgment.status,
            }
            journal_operation_id = f"ack:{acknowledgment.operation_id}"
            acknowledgment_request = json.loads(
                canonical_json_bytes(
                    {
                        "acknowledgment": acknowledgment.as_dict(),
                        "attribution_candidates": list(
                            normalized_attribution
                        ),
                        "learn_chart_ids": (
                            None
                            if normalized_learn_chart_ids is None
                            else list(normalized_learn_chart_ids)
                        ),
                        "prediction_id": prediction_id,
                    }
                ).decode("utf-8")
            )
            acknowledgment_request_sha256 = sha256_value(
                acknowledgment_request
            )
            if prediction.status == "acknowledged":
                if prediction.actual != actual:
                    raise FieldIntelligenceError(
                        "ACKNOWLEDGMENT_CONFLICT",
                        "operation already has another outcome",
                    )
                committed = self._committed_result(
                    f"{journal_operation_id}:publish",
                    expected_kind="action-outcome",
                    expected_request=acknowledgment_request,
                    expected_result_keys=frozenset(
                        {"acknowledgment_id", "prediction", "status"}
                    ),
                    expected_mapping_result_fields=frozenset({"prediction"}),
                    expected_transition_fields={
                        "prediction_id": prediction_id
                    },
                    require_retained=True,
                )
                if committed is None:
                    if self.checkpoints.operation_compacted(
                        f"{journal_operation_id}:publish"
                    ):
                        raise FieldIntelligenceError(
                            "HISTORY_COMPACTED",
                            "action outcome precedes the retained replay floor",
                        )
                    raise FieldIntelligenceError(
                        "CHECKPOINT_CORRUPT",
                        "action outcome has no committed operation record",
                    )
                manifest, stored_result, receipt = committed
                self._validate_acknowledgment_replay(
                    manifest=manifest,
                    stored_result=stored_result,
                    prediction=prediction,
                    acknowledgment=acknowledgment,
                    attribution_candidates=normalized_attribution,
                    learn_chart_ids=normalized_learn_chart_ids,
                )
                self._finish_pending(journal_operation_id)
                self._clear_effect_grant_binding(
                    acknowledgment.operation_id
                )
                return {
                    "acknowledgment_id": acknowledgment.acknowledgment_id,
                    "prediction": prediction.as_dict(),
                    "receipt": receipt.as_dict(),
                    "status": "replayed",
                }
            if normalized_learn_chart_ids is not None and (
                len(normalized_attribution) != 1
                or normalized_attribution[0] != "transition-model"
            ):
                raise FieldIntelligenceError(
                    "ATTRIBUTION_UNRESOLVED",
                    "specific model learning requires resolved transition attribution",
                )
            attribution_candidates = normalized_attribution
            learn_chart_ids = normalized_learn_chart_ids
            source = SourceInput(
                source_id=f"world-ack:{acknowledgment.operation_id}",
                content=acknowledgment.source_content,
                media_type="application/json",
                codec="utf-8",
                observed_timestamp=acknowledgment.acknowledgment_id,
                scope=prediction.query["scope"],
                claim_category="world-observation",
                fidelity="exact-record",
                labels=(prediction.query["scope"],),
            )
            existing_event = self.evidence.event_for_operation(
                journal_operation_id
            )
            if existing_event is None:
                event = EvidenceEvent.create(
                    operation_id=journal_operation_id,
                    event_kind="action-outcome",
                    source_revision_id=source.revision_id,
                    predecessor_state_sha256=self.state.state_sha256,
                    values=acknowledgment.observed_values,
                    context=acknowledgment.context,
                    epistemic_type="observed",
                    derivation_roots=(),
                    logical_sequence=self.evidence.event_count + 1,
                )
                stored = self.evidence.store_source(
                    source,
                    reserved_bytes=len(canonical_json_bytes(event.as_dict())),
                    commit=False,
                )
            else:
                event = existing_event
                if (
                    event.source_revision_id != source.revision_id
                    or dict(event.values) != dict(acknowledgment.observed_values)
                    or dict(event.context) != dict(acknowledgment.context)
                    or event.event_kind != "action-outcome"
                ):
                    raise FieldIntelligenceError(
                        "ACKNOWLEDGMENT_CONFLICT",
                        "acknowledgment retry has different evidence semantics",
                    )
                stored = self.evidence.store_source(source, commit=False)
            successor, resolved = self.cognition.resolve_prediction(
                self.state,
                prediction_id=prediction_id,
                actual=actual,
                attribution_candidates=attribution_candidates,
            )
            learning: Mapping[str, Any] | None = None
            if learn_chart_ids is not None:
                successor, learning = self.atlas.admit_observation(
                    successor,
                    event_id=event.event_id,
                    source_revision_id=stored.revision_id,
                    values=acknowledgment.observed_values,
                    context=acknowledgment.context,
                    target_chart_ids=learn_chart_ids,
                )
            self._check_capacity(successor)
            self._stage_pending(
                operation_id=journal_operation_id,
                kind="acknowledgment",
                payload={
                    "acknowledgment": acknowledgment.as_dict(),
                    "attribution_candidates": list(attribution_candidates),
                    "learn_chart_ids": (
                        None
                        if learn_chart_ids is None
                        else list(learn_chart_ids)
                    ),
                    "prediction_id": prediction_id,
                },
            )
            if existing_event is None:
                stored = self.evidence.store_source(
                    source,
                    reserved_bytes=len(canonical_json_bytes(event.as_dict())),
                )
                event = self.evidence.append_event(event)
            receipt = self._publish(
                operation_id=f"{journal_operation_id}:publish",
                successor=successor,
                event_id=event.event_id,
                transition={
                    "attribution_candidates": list(attribution_candidates),
                    "kind": "action-outcome",
                    "learning": learning,
                    "prediction_id": prediction_id,
                    "request": acknowledgment_request,
                    "request_sha256": acknowledgment_request_sha256,
                    "result": {
                        "acknowledgment_id": acknowledgment.acknowledgment_id,
                        "prediction": resolved.as_dict(),
                        "status": "acknowledged",
                    },
                },
            )
            self._finish_pending(journal_operation_id)
            self._clear_effect_grant_binding(
                acknowledgment.operation_id
            )
            return {
                "acknowledgment_id": acknowledgment.acknowledgment_id,
                "prediction": resolved.as_dict(),
                "receipt": receipt.as_dict(),
                "status": "acknowledged",
            }

    def recover_pending_effects(
        self,
        adapter: WorldAdapter,
    ) -> tuple[Mapping[str, Any], ...]:
        self._prepare_world_adapter(adapter)
        results: list[Mapping[str, Any]] = []
        for prediction in tuple(self.state.predictions):
            if (
                prediction.status != "pending"
                or prediction.operation_id is None
            ):
                continue
            acknowledgment = adapter.resolve(prediction.operation_id)
            if acknowledgment is None:
                if not self._effect_grant_is_reserved(prediction):
                    results.append(
                        {
                            "operation_id": prediction.operation_id,
                            "status": "awaiting-authority",
                        }
                    )
                    continue
                request = self._effect_dispatch_request(prediction)
                acknowledgment = adapter.execute_once(
                    operation_id=request["operation_id"],
                    action=request["action"],
                    target=request["target"],
                    payload=request["payload"],
                )
            results.append(
                self.admit_acknowledgment(
                    prediction_id=prediction.prediction_id,
                    acknowledgment=acknowledgment,
                )
            )
        return tuple(results)

    def choose_inquiry(
        self,
        survivors: Sequence[Survivor],
        operations: Sequence[InquiryOperation],
    ) -> InquiryDecision:
        return choose_inquiry(survivors, operations)

    def create_plan(
        self,
        *,
        operation_id: str,
        goal_id: str,
        goal: Mapping[str, Any],
        assumptions: Mapping[str, Any],
        action_decision: ActionDecision | None,
        inquiry: InquiryDecision | None,
        future_macros: Sequence[str] = (),
    ) -> Mapping[str, Any]:
        with self._lock:
            successor, plan = self.cognition.create_plan(
                self.state,
                goal_id=goal_id,
                goal=goal,
                assumptions=assumptions,
                action_decision=action_decision,
                inquiry=inquiry,
                future_macros=future_macros,
                authority_generation=self.authority_generation,
            )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition={"kind": "plan-created", "plan_id": plan.plan_id},
            )
            return {"plan": plan.as_dict(), "receipt": receipt.as_dict()}

    def repair_plans(
        self, *, operation_id: str, context: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any]:
        with self._lock:
            successor, plan_ids = self.cognition.repair_plans(
                self.state, context=context
            )
            if not plan_ids:
                return {"plan_ids": [], "status": "unchanged"}
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition={"kind": "plans-repaired", "plan_ids": list(plan_ids)},
            )
            return {
                "plan_ids": list(plan_ids),
                "receipt": receipt.as_dict(),
                "status": "invalidated",
            }

    def explain_query(
        self,
        *,
        query_id: str,
        allowed_labels: frozenset[str],
    ) -> Mapping[str, Any]:
        """Explain a query that was already prepared by ``think``.

        Explanations must never create a hidden solver readout.  The prepared
        query is resolved through the canonical read-only path and then passed
        to cognition for evidence attribution.
        """
        _identifier(query_id, "query_id")
        with self._lock:
            query = self.atlas.query_prepared(self.state, query_id)
            allowed_sources = frozenset(
                revision_id
                for revision_id in self.evidence.active_revision_ids()
                if set(self.evidence.source(revision_id).labels).issubset(allowed_labels)
            )
            return self.cognition.explain_query(
                self.state,
                query,
                allowed_source_revision_ids=allowed_sources,
            )

    def preview_forget(self, revision_ids: Sequence[str]) -> Mapping[str, Any]:
        targets = tuple(sorted({_digest(item, "revision_id") for item in revision_ids}))
        sources = [self.evidence.source(item) for item in targets]
        affected_charts = sorted(
            chart.chart_id
            for chart in self.state.charts
            if chart.active_source_revisions().intersection(targets)
        )
        affected_programs = sorted(
            program.program_id
            for program in self.state.programs
            if set(program.support_event_ids).intersection(
                event.event_id
                for target in targets
                for event in self.evidence.events_for_source(target)
            )
        )
        affected_temporal = sorted(
            row.memory_id for row in self.state.temporal_fields
            if set(row.source_revision_ids).intersection(targets)
        )
        binding = {
            "affected_chart_ids": affected_charts,
            "affected_program_ids": affected_programs,
            "affected_temporal_ids": affected_temporal,
            "field_state_sha256": self.state.state_sha256,
            "revision_ids": list(targets),
            "source_statuses": {
                source.revision_id: source.status for source in sources
            },
        }
        return {
            "binding": binding,
            "effects": {
                "adaptive_support": "rebuild",
                "backup_erasure": "not-performed",
                "exact_bytes": "retained-unless-delete_bytes-is-authorized",
                "source_use": "revoked",
            },
            "preview_id": sha256_value(binding),
        }

    def forget(
        self,
        *,
        operation_id: str,
        preview_id: str,
        revision_ids: Sequence[str],
        grant: AuthorityGrant,
        scope: str,
        delete_bytes: bool = False,
    ) -> Mapping[str, Any]:
        with self._lock:
            operation_id = _identifier(operation_id, "operation_id")
            preview_id = _digest(preview_id, "preview_id")
            scope = _identifier(scope, "forget scope")
            if not isinstance(delete_bytes, bool):
                raise FieldIntelligenceError(
                    "INVALID_REQUEST", "delete_bytes must be boolean"
                )
            targets = tuple(
                sorted({_digest(item, "revision_id") for item in revision_ids})
            )
            forget_request = {
                "delete_bytes": delete_bytes,
                "preview_id": preview_id,
                "scope": scope,
                "source_revision_ids": list(targets),
            }
            forget_request_sha256 = sha256_value(forget_request)
            committed = self._committed_result(
                operation_id,
                expected_kind="forget",
                expected_request=forget_request,
                expected_result_keys=frozenset(
                    {
                        "adaptive_forgetting",
                        "backup_erasure",
                        "exact_bytes_deleted",
                        "preview_id",
                        "revocation_generation",
                        "source_use_revoked",
                    }
                ),
                expected_transition_fields={
                    "delete_bytes": delete_bytes,
                    "scope": scope,
                    "source_revision_ids": list(targets),
                },
                require_retained=True,
            )
            if committed is not None:
                manifest, result, receipt = committed
                if (
                    result["adaptive_forgetting"] is not True
                    or result["backup_erasure"] is not False
                    or result["exact_bytes_deleted"] is not delete_bytes
                    or result["preview_id"] != preview_id
                    or result["revocation_generation"]
                    != manifest["revocation_generation"]
                    or result["source_use_revoked"] is not True
                ):
                    raise FieldIntelligenceError(
                        "CHECKPOINT_CORRUPT",
                        "committed forget result disagrees with its transition",
                    )
                return {**result, "receipt": receipt.as_dict()}
            preview = self.preview_forget(targets)
            if preview["preview_id"] != preview_id:
                raise FieldIntelligenceError(
                    "FORGET_PREVIEW_STALE",
                    "forget preview no longer matches current state and targets",
                )
            target = sha256_value(list(targets))
            self._validate_grant(
                grant,
                operation="forget-delete" if delete_bytes else "forget",
                target=target,
                scope=scope,
                consume=True,
            )
            fence = self.checkpoints.advance_revocation(
                targets, operation_id=operation_id
            )
            self.evidence.revoke(
                targets,
                generation=fence["generation"],
                delete_bytes=delete_bytes,
            )
            successor, details = self.atlas.retract_sources(
                self.state,
                targets,
                revocation_generation=fence["generation"],
            )
            result = {
                "adaptive_forgetting": True,
                "backup_erasure": False,
                "exact_bytes_deleted": delete_bytes,
                "preview_id": preview_id,
                "revocation_generation": fence["generation"],
                "source_use_revoked": True,
            }
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition={
                    **details,
                    "delete_bytes": delete_bytes,
                    "kind": "forget",
                    "request": forget_request,
                    "request_sha256": forget_request_sha256,
                    "result": result,
                    "scope": scope,
                    "source_revision_ids": list(targets),
                },
            )
            return {**result, "receipt": receipt.as_dict()}

    def propose_relational_structure(
        self,
        *,
        operation_id: str,
        problem_id: str,
        input_roles: Sequence[str],
        output_role: str,
        support_event_ids: Sequence[str],
        guards: Sequence[Guard] = (),
        max_candidates: int = 32,
    ) -> Mapping[str, Any]:
        with self._lock:
            required_variables = set(input_roles) | {output_role}
            for event_id in support_event_ids:
                event = self._active_event(event_id)
                missing = required_variables - set(event.values)
                if missing:
                    raise FieldIntelligenceError(
                        "EVIDENCE_MISMATCH",
                        "structure support omits required relational variables",
                        details={"missing": sorted(missing)},
                    )
            successor, candidate_ids = self.cognition.propose_relational_structure(
                self.state,
                problem_id=problem_id,
                input_roles=input_roles,
                output_role=output_role,
                support_event_ids=support_event_ids,
                guards=guards,
                max_candidates=max_candidates,
            )
            if successor is self.state:
                return {"candidate_ids": list(candidate_ids), "status": "replayed"}
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition={
                    "candidate_ids": list(candidate_ids),
                    "kind": "structure-candidates-proposed",
                    "problem_id": problem_id,
                },
            )
            return {
                "candidate_ids": list(candidate_ids),
                "receipt": receipt.as_dict(),
                "status": "proposed",
            }

    def begin_program_assessment(
        self,
        *,
        operation_id: str,
        program_id: str,
        bindings: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        with self._lock:
            successor, prediction = self.cognition.begin_program_assessment(
                self.state,
                program_id=program_id,
                bindings=bindings,
                authority_generation=self.authority_generation,
            )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition={
                    "kind": "program-assessment-begun",
                    "prediction_id": prediction.prediction_id,
                    "program_id": program_id,
                },
            )
            return {
                "prediction": prediction.as_dict(),
                "receipt": receipt.as_dict(),
            }

    def resolve_program_assessment(
        self,
        *,
        operation_id: str,
        program_id: str,
        prediction_id: str,
        outcome: Mapping[str, Any],
        event_id: str,
        loss_scale: float,
    ) -> Mapping[str, Any]:
        with self._lock:
            event = self._active_event(event_id)
            self._require_event_values(event, outcome)
            self._require_event_after(
                event, field="prediction_id", identity=prediction_id
            )
            successor, assessment = self.cognition.resolve_program_assessment(
                self.state,
                program_id=program_id,
                prediction_id=prediction_id,
                outcome=outcome,
                event_id=event_id,
                loss_scale=loss_scale,
            )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=event_id,
                transition={
                    "assessment_id": assessment.assessment_id,
                    "kind": "program-assessment-resolved",
                    "program_id": program_id,
                },
            )
            return {
                "assessment": assessment.as_dict(),
                "receipt": receipt.as_dict(),
            }

    def promote_program(
        self,
        *,
        operation_id: str,
        candidate_ids: Sequence[str],
        minimum_assessments: int,
        maximum_average_loss: float,
        bit_penalty: float,
    ) -> Mapping[str, Any]:
        with self._lock:
            successor, program = self.cognition.promote_program(
                self.state,
                candidate_ids=candidate_ids,
                minimum_assessments=minimum_assessments,
                maximum_average_loss=maximum_average_loss,
                bit_penalty=bit_penalty,
            )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition={
                    "kind": "program-promoted",
                    "program_id": program.program_id,
                },
            )
            return {"program": program.as_dict(), "receipt": receipt.as_dict()}

    def propose_language_construction(
        self,
        *,
        operation_id: str,
        construction_id: str,
        examples: Sequence[Mapping[str, Any]],
        semantic_program_id: str,
        guards: Sequence[Guard] = (),
    ) -> Mapping[str, Any]:
        with self._lock:
            for example in examples:
                if set(example) != {"event_id", "roles", "text"} or not isinstance(
                    example["roles"], Mapping
                ):
                    raise FieldIntelligenceError(
                        "INVALID_CONSTRUCTION",
                        "language examples require event_id, roles, and text",
                    )
                event = self._active_event(example["event_id"])
                self._require_exact_event_text(event, example["text"])
                self._require_event_values(event, example["roles"])
            successor, construction = self.cognition.propose_language_construction(
                self.state,
                construction_id=construction_id,
                examples=examples,
                semantic_program_id=semantic_program_id,
                guards=guards,
            )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition={
                    "construction_id": construction_id,
                    "kind": "construction-proposed",
                },
            )
            return {
                "construction": construction.as_dict(),
                "receipt": receipt.as_dict(),
            }

    def assess_language_construction(
        self,
        *,
        operation_id: str,
        construction_id: str,
        text: str,
        expected_roles: Mapping[str, str],
        event_id: str,
    ) -> Mapping[str, Any]:
        with self._lock:
            event = self._active_event(event_id)
            self._require_exact_event_text(event, text)
            self._require_event_values(event, expected_roles)
            self._require_event_after(
                event, field="construction_id", identity=construction_id
            )
            successor, assessment = self.cognition.assess_language_construction(
                self.state,
                construction_id=construction_id,
                text=text,
                expected_roles=expected_roles,
                event_id=event_id,
            )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=event_id,
                transition={
                    "assessment_id": assessment.assessment_id,
                    "construction_id": construction_id,
                    "kind": "construction-assessed",
                },
            )
            return {
                "assessment": assessment.as_dict(),
                "receipt": receipt.as_dict(),
            }

    def promote_language_construction(
        self,
        *,
        operation_id: str,
        construction_id: str,
        minimum_assessments: int = 1,
    ) -> Mapping[str, Any]:
        with self._lock:
            successor, construction = self.cognition.promote_language_construction(
                self.state,
                construction_id=construction_id,
                minimum_assessments=minimum_assessments,
            )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition={
                    "construction_id": construction_id,
                    "kind": "construction-promoted",
                },
            )
            return {
                "construction": construction.as_dict(),
                "receipt": receipt.as_dict(),
            }

    def interpret(
        self,
        *,
        text: str,
        context: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        return self.cognition.interpret_utterance(
            self.state, text=text, context=context
        )

    def express(
        self,
        *,
        semantic_program_id: str,
        bindings: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
        max_tokens: int = 128,
    ) -> Mapping[str, Any]:
        return self.cognition.express_meaning(
            self.state,
            semantic_program_id=semantic_program_id,
            bindings=bindings,
            context=context,
            max_tokens=max_tokens,
        )

    def derive_exact_reduction(
        self,
        *,
        operation_id: str,
        macro_id: str,
        boundary: Sequence[str],
        interior: Sequence[str],
        context: Mapping[str, Any] | None = None,
        linear: Mapping[str, float] | None = None,
        constant: float = 0.0,
    ) -> Mapping[str, Any]:
        with self._lock:
            successor = self.atlas.derive_schur_reduction(
                self.state,
                macro_id=macro_id,
                boundary=boundary,
                interior=interior,
                context=context,
                linear=linear,
                constant=constant,
            )
            macro = next(row for row in successor.macros if row.macro_id == macro_id)
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition={
                    "kind": "exact-reduction-derived",
                    "macro_id": macro_id,
                },
            )
            return {"macro": macro.as_dict(), "receipt": receipt.as_dict()}

    def counterfactual_without_chart(
        self,
        *,
        chart_id: str,
        observed: Mapping[str, float],
        requested: Sequence[str],
        context: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        return self.cognition.counterfactual_without_chart(
            self.state,
            chart_id=chart_id,
            observed=observed,
            requested=requested,
            context=context,
        )

    def record_computation(
        self,
        *,
        operation_id: str,
        operation: str,
        inputs: Mapping[str, Any],
        outcome: str,
        elapsed_ns: int,
        work_units: int,
        residual_before: float | None = None,
        residual_after: float | None = None,
    ) -> Mapping[str, Any]:
        with self._lock:
            successor, record = self.cognition.record_computation(
                self.state,
                operation=operation,
                inputs=inputs,
                outcome=outcome,
                elapsed_ns=elapsed_ns,
                work_units=work_units,
                residual_before=residual_before,
                residual_after=residual_after,
            )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition={
                    "kind": "computation-observed",
                    "record_id": record.record_id,
                },
            )
            return {
                "receipt": receipt.as_dict(),
                "record": record.as_dict(),
            }
    def export_bundle(self, manifest_sha256: str | None = None) -> bytes:
        """Return a verified standalone v2 checkpoint bundle."""
        with self._lock:
            return self.checkpoints.export_bundle(manifest_sha256)


    def operate_computer(
        self, operation_id: str, *, computer_id: str, action: str,
        arguments: Mapping[str, Any] | None = None,
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        """Execute one bounded, replay-safe operation on an atlas-owned computer."""
        from cassi_learning_computer import LearningComputer

        schemas = {
            "configure": (frozenset(), frozenset({"profile"})),
            "load": (frozenset({"program"}), frozenset({"left", "right", "entry"})),
            "advance": (frozenset({"steps"}), frozenset()),
            "submit": (
                frozenset({"kernel", "state"}),
                frozenset({"arguments", "kind", "steps"}),
            ),
            "call": (
                frozenset({"call_id", "kernel", "return_binding"}),
                frozenset(
                    {
                        "allowance",
                        "allowance_id",
                        "arguments",
                        "dependencies",
                        "expected_return",
                        "kind",
                        "request_identity",
                        "reservation",
                        "state",
                        "steps",
                    }
                ),
            ),
            "cancel-call": (
                frozenset({"call_id"}),
                frozenset(),
            ),
            "invoke": (
                frozenset({"arguments"}),
                frozenset({"steps"}),
            ),
            "authorized-invoke": (
                frozenset({"arguments", "grant", "scope", "target"}),
                frozenset({"steps"}),
            ),
            "restart": (frozenset(), frozenset({"left", "right", "entry"})),
            "grow": (frozenset({"stack_capacity"}), frozenset({"max_steps"})),
            "solve": (
                frozenset({"source"}),
                frozenset({"budget", "learn", "method"}),
            ),
            "continue-solve": (
                frozenset({"source"}),
                frozenset({"budget"}),
            ),
        }
        _identifier(operation_id, "operation_id")
        _identifier(computer_id, "computer_id")
        if not isinstance(action, str) or action not in schemas:
            raise FieldIntelligenceError("INVALID_COMPUTER", "unsupported computer action")
        if arguments is not None and not isinstance(arguments, Mapping):
            raise FieldIntelligenceError("INVALID_COMPUTER", "computer arguments must be an object")
        args = dict(arguments or {})
        required, optional = schemas[action]
        FieldIntelligenceSurface._require(args, required=required, optional=optional)
        if action in {"call", "invoke"}:
            invocation = args.get("arguments")
            if (
                isinstance(invocation, Mapping)
                and (
                    invocation.get("operation")
                    in {"authorize-action", "dispatch-action"}
                    or "authority" in invocation
                )
            ):
                raise FieldIntelligenceError(
                    "AUTHORITY_REQUIRED",
                    "ordinary computer invocation cannot authorize or "
                    "dispatch an action",
                )
        if expected_state_sha256 is not None:
            _digest(expected_state_sha256, "expected state")
        dependencies = _regional_source_dependencies(args)
        if len(dependencies) > self.limits.max_source_work:
            raise FieldIntelligenceError(
                "WORK_CAPACITY",
                "regional request evidence dependencies exceed source-work limit",
            )
        revocation_notice = (
            action == "invoke"
            and isinstance(args.get("arguments"), Mapping)
            and args["arguments"].get("operation") == "revocation"
        )
        with self._lock:
            for revision_id in dependencies:
                source = self.evidence.source(revision_id)
                if not revocation_notice:
                    self.evidence.read(source)
            request = {
                "kind": "computer",
                "computer_id": computer_id,
                "action": action,
                "arguments": args,
                "expected_state_sha256": expected_state_sha256,
                "evidence_binding": {
                    "revocation_generation": self.state.revocation_generation,
                    "source_revision_ids": list(dependencies),
                },
            }
            if len(canonical_json_bytes(request)) > self.limits.max_source_bytes:
                raise FieldIntelligenceError(
                    "WORK_CAPACITY",
                    "computer request exceeds source byte limit",
                )
            committed = self._committed_result(
                operation_id, expected_kind="computer", expected_request=request,
                expected_result_keys=frozenset({"receipt"}),
                expected_mapping_result_fields=frozenset({"receipt"}), require_retained=True,
            )
            if committed is not None:
                manifest, result, checkpoint = committed
                retained = self.checkpoints._load_state(manifest)
                row = next((item for item in retained.computers if item.computer_id == computer_id), None)
                receipt = result["receipt"]
                if (row is None or receipt.get("computer_id") != computer_id
                        or receipt.get("action") != action
                        or receipt.get("computer_state_sha256") != sha256_value(row.as_dict())):
                    raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "computer replay differs from its field")
                return {**result, "checkpoint_receipt": checkpoint.as_dict()}
            if self.checkpoints.operation_compacted(operation_id):
                raise FieldIntelligenceError("HISTORY_COMPACTED", "computer operation precedes retained history")
            if expected_state_sha256 is not None and expected_state_sha256 != self.state.state_sha256:
                raise FieldIntelligenceError("LINEAGE_CONFLICT", "computer predecessor differs from current field")
            self._assert_publication_order(operation_id)
            row = next((item for item in self.state.computers if item.computer_id == computer_id), None)
            available_bytes = self.limits.max_workspace_bytes - self.state.workspace_usage()["workspace_bytes"]
            replacement_bytes = available_bytes + (0 if row is None else row.nbytes)
            try:
                if action == "configure":
                    if row is not None:
                        raise FieldIntelligenceError("OPERATION_CONFLICT", "computer already exists")
                    requested_profile = args.get("profile")
                    if isinstance(requested_profile, Mapping):
                        requested_modes = max(
                            int(requested_profile.get("mode_count", 0)),
                            int(requested_profile.get("program_capacity", 0)),
                            int(requested_profile.get("stack_capacity", 0)),
                        )
                        if requested_modes * 9 * 8 > available_bytes:
                            raise FieldIntelligenceError(
                                "WORK_CAPACITY",
                                "computer profile exceeds workspace limit",
                            )
                    successor_row = LearningComputer.initial(
                        computer_id,
                        profile=args.get("profile"),
                        max_field_bytes=available_bytes,
                    )
                    if successor_row.nbytes > available_bytes:
                        raise FieldIntelligenceError("WORK_CAPACITY", "computer geometry exceeds workspace limit")
                    receipt = successor_row.inspect()
                else:
                    if row is None:
                        raise FieldIntelligenceError("UNKNOWN_COMPUTER", "configure the computer first")
                    if action in {
                        "advance",
                        "authorized-invoke",
                        "call",
                        "invoke",
                        "submit",
                    }:
                        steps = _integer(
                            args.get("steps", 1),
                            "steps",
                            minimum=1,
                        )
                        if steps > self.limits.max_operator_effort:
                            raise FieldIntelligenceError(
                                "WORK_CAPACITY",
                                "computer batch exceeds operator limit",
                            )
                        if action == "call":
                            args["steps"] = steps
                            try:
                                successor_row, receipt = row.call(**args)
                            except (TypeError, ValueError) as exc:
                                raise FieldIntelligenceError(
                                    "INVALID_REGIONAL_TASK", str(exc)
                                ) from exc
                        elif action == "submit":
                            args["steps"] = steps
                            try:
                                successor_row, receipt = row.submit(**args)
                            except (TypeError, ValueError) as exc:
                                raise FieldIntelligenceError(
                                    "INVALID_REGIONAL_TASK", str(exc)
                                ) from exc
                        elif action == "authorized-invoke":
                            grant_value = args["grant"]
                            if not isinstance(grant_value, Mapping):
                                raise FieldIntelligenceError(
                                    "AUTHORITY_INVALID",
                                    "computer authority grant must be an object",
                                )
                            grant = AuthorityGrant.from_dict(grant_value)
                            target = _identifier(
                                args["target"], "computer effect target"
                            )
                            scope = _identifier(
                                args["scope"], "computer effect scope"
                            )
                            task = row.inspect().get("task")
                            proposal = (
                                task.get("continuation", {}).get("proposal")
                                if isinstance(task, Mapping)
                                else None
                            )
                            event = args["arguments"]
                            if not isinstance(event, Mapping):
                                raise FieldIntelligenceError(
                                    "AUTHORITY_REQUIRED",
                                    "authorized computer action must be an object",
                                )
                            action_operation = event.get("operation")
                            proposal_id = event.get("proposal_id")
                            required_status = (
                                "proposed"
                                if action_operation == "authorize-action"
                                else "authorized"
                            )
                            if (
                                action_operation
                                not in {"authorize-action", "dispatch-action"}
                                or "authority" in event
                                or not isinstance(proposal, Mapping)
                                or proposal.get("proposal_id") != proposal_id
                                or proposal.get("target") != target
                                or proposal.get("scope") != scope
                                or proposal.get("status") != required_status
                            ):
                                raise FieldIntelligenceError(
                                    "AUTHORITY_REQUIRED",
                                    "computer action is not bound to the exact "
                                    "pending proposal phase",
                                )
                            self._validate_grant(
                                grant,
                                operation="computer-effect",
                                target=target,
                                scope=scope,
                                consume=False,
                            )
                            authority = {
                                "generation": grant.generation,
                                "grant_id": grant.grant_id,
                                "grant_sha256": sha256_value(grant.as_dict()),
                                "issuer": grant.issuer,
                                "one_use": grant.one_use,
                                "operation": grant.operation,
                                "scope": grant.scope,
                                "target": grant.target,
                            }
                            successor_row, receipt = row._authorized_invoke(
                                arguments={
                                    **dict(event),
                                    "authority": authority,
                                },
                                steps=steps,
                            )
                            if action_operation == "dispatch-action":
                                successor_task = successor_row.inspect().get("task")
                                successor_continuation = (
                                    successor_task.get("continuation")
                                    if isinstance(successor_task, Mapping)
                                    else None
                                )
                                successor_proposal = (
                                    successor_continuation.get("proposal")
                                    if isinstance(successor_continuation, Mapping)
                                    else None
                                )
                                effect_request = (
                                    self._computer_effect_dispatch_request(
                                        successor_proposal
                                    )
                                )
                                if effect_request is None:
                                    raise FieldIntelligenceError(
                                        "INVALID_REGIONAL_TASK",
                                        "dispatch did not persist its regional proposal",
                                    )
                                self._validate_grant(
                                    grant,
                                    operation="computer-effect",
                                    target=target,
                                    scope=scope,
                                    consume=True,
                                    binding={
                                        "grant": grant.as_dict(),
                                        "prediction_id": proposal_id,
                                        "request": effect_request,
                                        "request_sha256": sha256_value(
                                            effect_request
                                        ),
                                    },
                                )
                        elif action == "invoke":
                            args["steps"] = steps
                            successor_row, receipt = row.invoke(**args)
                        else:
                            successor_row, receipt = row.advance(**args)
                    elif action == "cancel-call":
                        successor_row, receipt = row.cancel_call(**args)
                    elif action == "restart":
                        successor_row, receipt = row.restart(**args)
                    elif action in ("solve", "continue-solve"):
                        budget = _integer(
                            args.get("budget", 2000),
                            "budget",
                            minimum=1,
                        )
                        if budget > min(
                            self.limits.max_operator_effort,
                            self.limits.max_solver_iterations,
                        ):
                            raise FieldIntelligenceError(
                                "WORK_CAPACITY",
                                "solver budget exceeds its configured limit",
                            )
                        solver_bytes = max(1, replacement_bytes)
                        if action == "solve":
                            successor_row, receipt = row.solve(
                                **args,
                                max_field_bytes=solver_bytes,
                                lifetime_budget=(
                                    self.limits.max_solver_iterations
                                ),
                            )
                        else:
                            successor_row, receipt = (
                                row.continue_solve(
                                    **args,
                                    max_field_bytes=solver_bytes,
                                )
                            )
                    elif action == "load":
                        if row.nbytes > replacement_bytes:
                            raise FieldIntelligenceError("WORK_CAPACITY", "computer program exceeds workspace limit")
                        successor_row, receipt = row.load(**args)
                    else:
                        if row.nbytes > replacement_bytes:
                            raise FieldIntelligenceError("WORK_CAPACITY", "computer growth exceeds workspace limit")
                        successor_row, receipt = row.grow(**args)
            except FieldIntelligenceError:
                raise
            except (TypeError, ValueError) as exc:
                raise FieldIntelligenceError("INVALID_COMPUTER", str(exc)) from exc
            if successor_row.nbytes > replacement_bytes:
                raise FieldIntelligenceError(
                    "WORK_CAPACITY", "computer successor exceeds workspace limit"
                )
            receipt = {
                **dict(receipt), "computer_id": computer_id, "action": action,
                "computer_state_sha256": sha256_value(successor_row.as_dict()),
            }
            computers = tuple(item for item in self.state.computers if item.computer_id != computer_id)
            learning_applied = isinstance(
                receipt.get("observation"), Mapping
            )
            successor = self.state.with_transition(
                "computer",
                {
                    "computer_id": computer_id,
                    "action": action,
                    "request_sha256": sha256_value(request),
                },
                computers=(*computers, successor_row),
                logical_tick=(
                    self.state.logical_tick + int(learning_applied)
                ),
            )
            result = json.loads(canonical_json_bytes({"receipt": receipt}))
            checkpoint = self._publish(
                operation_id=operation_id, successor=successor, event_id=None,
                transition={"kind": "computer", "request": request,
                            "request_sha256": sha256_value(request), "result": result},
            )
            return {**result, "checkpoint_receipt": checkpoint.as_dict()}

    def admit_computer_input(
        self,
        operation_id: str,
        *,
        computer_id: str,
        source: SourceInput,
        cursor: int = 0,
        page_size: int = 128,
        shape: Sequence[int] | None = None,
        dtype: str | None = None,
        units: Sequence[str] | None = None,
        stream_id: str | None = None,
        chunk_index: int | None = None,
        steps: int = 4096,
        expected_state_sha256: str | None = None,
    ) -> Mapping[str, Any]:
        """Archive one exact source page and admit its typed view to cognition."""

        from cassi_field_cognition import (
            REGIONAL_KERNEL_NAME,
            semantic_cognition_state,
        )
        from cassi_field_input import (
            SourceViewError,
            semantic_observe_request,
            source_observation_page,
        )

        operation_id = _identifier(operation_id, "operation_id")
        computer_id = _identifier(computer_id, "computer_id")
        if not isinstance(source, SourceInput):
            raise FieldIntelligenceError(
                "INVALID_SOURCE",
                "computer input source must be a SourceInput",
            )
        steps = _integer(steps, "steps", minimum=1)
        if steps > self.limits.max_operator_effort:
            raise FieldIntelligenceError(
                "WORK_CAPACITY",
                "computer input batch exceeds operator limit",
            )
        source_operation = f"{operation_id}:source"
        computer_operation = f"{operation_id}:computer"
        try:
            page = source_observation_page(
                source,
                cursor=cursor,
                page_size=page_size,
                shape=shape,
                dtype=dtype,
                units=units,
            )
        except SourceViewError as exc:
            raise FieldIntelligenceError(
                "INVALID_SOURCE_VIEW", str(exc)
            ) from exc
        context = {
            "computer_id": computer_id,
            "cursor": page["cursor"],
            "next_cursor": page["next_cursor"],
            "reason": page["reason"],
            "source_revision_id": source.revision_id,
            "status": page["status"],
            "view_sha256": page["view_sha256"],
        }
        with self._lock:
            source_committed = self._operation_is_committed(source_operation)
            if (
                expected_state_sha256 is not None
                and not source_committed
                and expected_state_sha256 != self.state.state_sha256
            ):
                raise FieldIntelligenceError(
                    "LINEAGE_CONFLICT",
                    "computer input predecessor differs from current field",
                )
            if page["status"] != "supported":
                evidence = self.archive_source(
                    operation_id=source_operation,
                    source=source,
                    context=context,
                    event_kind="computer-input-unsupported",
                )
                return {
                    "computer": None,
                    "evidence": evidence,
                    "status": "unsupported",
                    "view": page,
                }
            evidence = self.archive_source(
                operation_id=source_operation,
                source=source,
                context=context,
                event_kind="computer-input",
            )
            semantic_request = semantic_observe_request(
                page,
                operation_id=f"{operation_id}:observe",
                event_id=f"source-event:{evidence['event']['event_id']}",
                delivery_id=f"source-view:{page['view_sha256']}",
                stream_id=stream_id,
                chunk_index=chunk_index,
            )
            committed_computer = self.checkpoints._committed_operation(
                computer_operation
            )
            if committed_computer is not None:
                stored_request = committed_computer[1]["transition"].get(
                    "request"
                )
                if (
                    not isinstance(stored_request, Mapping)
                    or stored_request.get("kind") != "computer"
                    or stored_request.get("computer_id") != computer_id
                    or stored_request.get("action")
                    not in {"invoke", "submit"}
                    or not isinstance(
                        stored_request.get("arguments"), Mapping
                    )
                ):
                    raise FieldIntelligenceError(
                        "CHECKPOINT_CORRUPT",
                        "committed computer input request is invalid",
                    )
                action = str(stored_request["action"])
                if action == "submit":
                    arguments = {
                        "arguments": semantic_request,
                        "kernel": REGIONAL_KERNEL_NAME,
                        "kind": "semantic-cognition",
                        "state": semantic_cognition_state(
                            scope=source.scope
                        ),
                        "steps": steps,
                    }
                else:
                    arguments = {
                        "arguments": semantic_request,
                        "steps": steps,
                    }
            else:
                row = next(
                    (
                        item
                        for item in self.state.computers
                        if item.computer_id == computer_id
                    ),
                    None,
                )
                if row is None:
                    raise FieldIntelligenceError(
                        "UNKNOWN_COMPUTER", "configure the computer first"
                    )
                inspected = row.inspect()
                session = inspected.get("session")
                if (
                    isinstance(session, Mapping)
                    and session.get("status") == "idle"
                ):
                    action = "submit"
                    arguments = {
                        "arguments": semantic_request,
                        "kernel": REGIONAL_KERNEL_NAME,
                        "kind": "semantic-cognition",
                        "state": semantic_cognition_state(
                            scope=source.scope
                        ),
                        "steps": steps,
                    }
                elif (
                    isinstance(session, Mapping)
                    and session.get("kernel") == REGIONAL_KERNEL_NAME
                ):
                    action = "invoke"
                    arguments = {
                        "arguments": semantic_request,
                        "steps": steps,
                    }
                else:
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "computer input requires an idle or resident "
                        "cognition field",
                    )
            computer = self.operate_computer(
                computer_operation,
                computer_id=computer_id,
                action=action,
                arguments=arguments,
            )
            return {
                "computer": computer,
                "evidence": evidence,
                "status": "supported",
                "view": page,
            }

    def inspect_computers(self) -> Mapping[str, Any]:
        with self._lock:
            return {
                "computers": [row.inspect() for row in self.state.computers],
                "state_sha256": self.state.state_sha256,
                "generation": self.state.generation,
            }

    def inspect_computer_policy(
        self,
        *,
        computer_id: str,
        source: Mapping[str, Any],
        budget: int = 2000,
        explore: bool = True,
    ) -> Mapping[str, Any]:
        """Explain one prospective selection without publishing a transition."""

        _identifier(computer_id, "computer_id")
        if not isinstance(source, Mapping):
            raise FieldIntelligenceError(
                "INVALID_COMPUTER", "solver source must be an object"
            )
        budget = _integer(budget, "budget", minimum=1)
        if budget > self.limits.max_operator_effort:
            raise FieldIntelligenceError(
                "WORK_CAPACITY",
                "solver budget exceeds operator limit",
            )
        if not isinstance(explore, bool):
            raise FieldIntelligenceError(
                "INVALID_COMPUTER", "explore must be boolean"
            )
        if len(canonical_json_bytes(source)) > self.limits.max_source_bytes:
            raise FieldIntelligenceError(
                "WORK_CAPACITY", "computer request exceeds source byte limit"
            )
        with self._lock:
            row = next(
                (
                    item
                    for item in self.state.computers
                    if item.computer_id == computer_id
                ),
                None,
            )
            if row is None:
                raise FieldIntelligenceError(
                    "UNKNOWN_COMPUTER", "configure the computer first"
                )
            try:
                inspection = row.explain(
                    source, budget=budget, explore=explore
                )
            except (TypeError, ValueError) as exc:
                raise FieldIntelligenceError(
                    "INVALID_COMPUTER", str(exc)
                ) from exc
            return {
                "computer_id": computer_id,
                "inspection": json.loads(
                    canonical_json_bytes(inspection)
                ),
                "state_sha256": self.state.state_sha256,
                "generation": self.state.generation,
                "read_only": True,
            }

    def inspect(self) -> Mapping[str, Any]:
        field_bytes = self.state.closure_bytes
        evidence_bytes = self.evidence.physical_bytes()
        resonance = self.inspect_resonance()
        workspace_usage = self.state.workspace_usage()
        return {
            "authority_generation": self.authority_generation,
            "capacity": {
                "limits": self.limits.as_dict(),
                "usage": {
                    "charts": len(self.state.charts),
                    "evidence_bytes": evidence_bytes,
                    "field_bytes": field_bytes,
                    "macros": len(self.state.macros),
                    "plans": len(self.state.plans),
                    "predictions": len(self.state.predictions),
                    "programs": len(self.state.programs),
                    "computers": len(self.state.computers),
                    "variables": len(self.state.variables),
                    **workspace_usage,
                },
            },
            "checkpoint_manifest_sha256": self.checkpoints.current_manifest_sha256,
            "field_generation": self.state.generation,
            "field_state_sha256": self.state.state_sha256,
            "resonance": resonance,
            "revocation_generation": self.state.revocation_generation,
            "schema": ATLAS_SCHEMA,
        }


class FieldIntelligenceSurface:
    """Closed-schema in-process RPC facade; transport and tools remain host-owned."""

    def __init__(self, owner: FieldIntelligenceOwner) -> None:
        self.owner = owner

    @staticmethod
    def _require(
        params: Mapping[str, Any],
        *,
        required: frozenset[str],
        optional: frozenset[str] = frozenset(),
    ) -> None:
        keys = set(params)
        if not required.issubset(keys) or keys - required - optional:
            raise FieldIntelligenceError(
                "INVALID_REQUEST",
                "operation params do not match the closed schema",
                details={
                    "actual": sorted(keys),
                    "optional": sorted(optional),
                    "required": sorted(required),
                },
            )

    def handle(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        if set(request) != {"operation", "params", "request_id", "schema"}:
            raise FieldIntelligenceError(
                "PROTOCOL_MISMATCH", "request schema is closed"
            )
        if request["schema"] != RPC_SCHEMA:
            raise FieldIntelligenceError(
                "PROTOCOL_MISMATCH", "request schema is incompatible"
            )
        request_id = _identifier(request["request_id"], "request_id")
        operation = _identifier(request["operation"], "operation")
        params = request["params"]
        if not isinstance(params, Mapping):
            raise FieldIntelligenceError(
                "INVALID_REQUEST", "params must be an object"
            )
        if operation == "inspect":
            self._require(params, required=frozenset())
            result = self.owner.inspect()
        elif operation == "computer":
            self._require(
                params, required=frozenset({"operation_id", "computer_id", "action"}),
                optional=frozenset({"arguments", "expected_state_sha256"}),
            )
            result = self.owner.operate_computer(**dict(params))
        elif operation == "inspect_computers":
            self._require(params, required=frozenset())
            result = self.owner.inspect_computers()
        elif operation == "inspect_computer_policy":
            self._require(
                params,
                required=frozenset({"computer_id", "source"}),
                optional=frozenset({"budget", "explore"}),
            )
            result = self.owner.inspect_computer_policy(**dict(params))
        elif operation == "inspect_resonance":
            self._require(params, required=frozenset())
            result = self.owner.inspect_resonance()
        elif operation == "export_bundle":
            self._require(
                params,
                required=frozenset(),
                optional=frozenset({"manifest_sha256"}),
            )
            bundle = self.owner.export_bundle(params.get("manifest_sha256"))
            result = {
                "bundle_base64": base64.b64encode(bundle).decode("ascii"),
                "bytes": len(bundle),
            }
        elif operation == "think":
            self._require(
                params,
                required=frozenset({"observed", "operation_id", "requested"}),
                optional=frozenset(
                    {
                        "constraints",
                        "context",
                        "max_branches",
                        "max_iterations",
                        "query_id",
                        "ticks",
                        "tolerance",
                        "valid_source_revision_ids",
                    }
                ),
            )
            arguments = dict(params)
            arguments["constraints"] = tuple(
                item
                if isinstance(item, AffineConstraint)
                else AffineConstraint(
                    coefficients=item["coefficients"],
                    target=item["target"],
                    evidence_event_ids=tuple(item.get("evidence_event_ids", ())),
                )
                for item in arguments.get("constraints", ())
            )
            result = self.owner.think(**arguments)
        elif operation == "advance":
            self._require(
                params,
                required=frozenset({"operation_id", "ticks"}),
                optional=frozenset({"expected_state_sha256", "source_enabled"}),
            )
            result = self.owner.advance(**dict(params))
        elif operation == "condense_transceiver":
            self._require(
                params,
                required=frozenset({
                    "chart_ids", "context", "input_ids", "operation_id",
                    "output_ids", "transceiver_id",
                }),
                optional=frozenset({
                    "error_allowance", "expected_state_sha256", "horizon_ticks",
                    "input_bound", "observed", "rank",
                }),
            )
            result = self.owner.condense_transceiver(**dict(params))
        elif operation == "advance_transceivers":
            self._require(
                params,
                required=frozenset({"context", "operation_id", "stimuli"}),
                optional=frozenset({
                    "connections", "expected_state_sha256", "force_full", "ticks",
                }),
            )
            result = self.owner.advance_transceivers(**dict(params))
        elif operation == "reset_transceiver":
            self._require(
                params,
                required=frozenset({"operation_id", "transceiver_id"}),
                optional=frozenset({"expected_state_sha256"}),
            )
            result = self.owner.reset_transceiver(**dict(params))
        elif operation == "read_packet_deposit":
            self._require(
                params,
                required=frozenset({"path", "component", "flow_signal"}),
            )
            result = self.owner.read_packet_deposit(**dict(params))
        elif operation == "inspect_transceivers":
            self._require(params, required=frozenset())
            result = self.owner.inspect_transceivers()
        elif operation == "configure_temporal":
            self._require(params, required=frozenset({
                "operation_id", "memory_id", "action_ids", "observation_ids",
            }), optional=frozenset({"max_states", "context", "expected_state_sha256"}))
            result = self.owner.configure_temporal(**dict(params))
        elif operation == "learn_temporal":
            self._require(params, required=frozenset({
                "operation_id", "memory_id", "source",
            }), optional=frozenset({"context", "expected_state_sha256"}))
            arguments = dict(params)
            arguments["source"] = SourceInput.from_dict(arguments["source"])
            result = self.owner.learn_temporal(**arguments)
        elif operation == "advance_temporal":
            self._require(params, required=frozenset({
                "operation_id", "memory_id", "action", "observation",
            }), optional=frozenset({"expected_state_sha256", "participant_id"}))
            result = self.owner.advance_temporal(**dict(params))
        elif operation == "reset_temporal":
            self._require(params, required=frozenset({"operation_id", "memory_id"}),
                          optional=frozenset({"expected_state_sha256", "participant_id", "known_start"}))
            result = self.owner.reset_temporal(**dict(params))
        elif operation == "condense_temporal_skill":
            self._require(params, required=frozenset({
                "operation_id", "memory_id", "skill_id", "goal_observations",
            }), optional=frozenset({"forbidden_observations", "expected_state_sha256"}))
            result = self.owner.condense_temporal_skill(**dict(params))
        elif operation == "inspect_temporal":
            self._require(params, required=frozenset({"memory_id"}),
                          optional=frozenset({"action", "skill_id", "participant_id"}))
            result = self.owner.inspect_temporal(**dict(params))
        elif operation == "select_temporal_action":
            self._require(
                params,
                required=frozenset({"memory_id", "skill_ids", "operations"}),
                optional=frozenset({
                    "participant_id", "minimum_margin", "expected_state_sha256",
                }),
            )
            result = self.owner.select_temporal_action(**dict(params))
        elif operation == "bind_temporal":
            self._require(params, required=frozenset({"operation_id", "memory_id", "participant_id"}),
                          optional=frozenset({"known_start", "expected_state_sha256"}))
            result = self.owner.bind_temporal(**dict(params))
        elif operation == "inquire_temporal":
            self._require(params, required=frozenset({"memory_id", "operations"}),
                          optional=frozenset({"participant_id", "skill_id", "goal_observations", "horizon", "max_nodes", "forbidden_observations"}))
            result = self.owner.inquire_temporal(**dict(params))
        elif operation == "compose_temporal_task":
            self._require(params, required=frozenset({"operation_id", "task_id", "steps"}),
                          optional=frozenset({"context", "expected_state_sha256"}))
            result = self.owner.compose_temporal_task(**dict(params))
        elif operation == "inspect_temporal_task":
            self._require(params, required=frozenset({"task_id"}))
            result = self.owner.inspect_temporal_task(**dict(params))
        elif operation == "propose_temporal_task":
            self._require(params, required=frozenset({"operation_id", "task_id", "allowed_actions"}),
                          optional=frozenset({"expected_state_sha256"}))
            result = self.owner.propose_temporal_task(**dict(params))
        elif operation == "acknowledge_temporal_task":
            self._require(params, required=frozenset({
                "operation_id", "task_id", "proposal_id", "participant_id", "action", "observation",
            }), optional=frozenset({"expected_state_sha256"}))
            result = self.owner.acknowledge_temporal_task(**dict(params))
        elif operation == "query":
            self._require(params, required=frozenset({"query_id"}))
            result = self.owner.query(params["query_id"])
        elif operation == "continue_inquiry":
            raise FieldIntelligenceError(
                "UNSUPPORTED_OPERATION", "continue_inquiry was removed by the v2 surface"
            )
        elif operation == "exact_recall":
            self._require(
                params,
                required=frozenset(
                    {
                        "allowed_labels",
                        "allow_historical",
                        "revision_id",
                        "span",
                    }
                ),
            )
            result = self.owner.exact_recall(
                revision_id=params["revision_id"],
                allowed_labels=frozenset(params["allowed_labels"]),
                span=(
                    None
                    if params["span"] is None
                    else tuple(params["span"])
                ),
                allow_historical=params["allow_historical"],
            )
        elif operation == "admit_computation_episode":
            self._require(
                params,
                required=frozenset(
                    {
                        "context",
                        "feature_bindings",
                        "operation_id",
                        "outcomes",
                        "source",
                        "target_chart_ids",
                        "workspace",
                    }
                ),
            )
            arguments = dict(params)
            arguments["source"] = SourceInput.from_dict(arguments["source"])
            arguments["workspace"] = ResonantWorkspace.from_dict(arguments["workspace"])
            arguments["target_chart_ids"] = tuple(arguments["target_chart_ids"])
            result = self.owner.admit_computation_episode(**arguments)
        elif operation == "admit":
            self._require(
                params,
                required=frozenset(
                    {"context", "operation_id", "source", "values"}
                ),
                optional=frozenset(
                    {
                        "derivation_roots",
                        "epistemic_type",
                        "event_kind",
                        "target_chart_ids",
                        "weight",
                    }
                ),
            )
            arguments = dict(params)
            arguments["source"] = SourceInput.from_dict(arguments["source"])
            if arguments.get("target_chart_ids") is not None:
                arguments["target_chart_ids"] = tuple(
                    arguments["target_chart_ids"]
                )
            result = self.owner.admit_observation(**arguments)
        elif operation == "archive":
            self._require(
                params,
                required=frozenset({"context", "operation_id", "source"}),
                optional=frozenset({"epistemic_type", "event_kind"}),
            )
            arguments = dict(params)
            arguments["source"] = SourceInput.from_dict(arguments["source"])
            result = self.owner.archive_source(**arguments)
        elif operation == "computer_input":
            self._require(
                params,
                required=frozenset(
                    {"computer_id", "operation_id", "source"}
                ),
                optional=frozenset(
                    {
                        "chunk_index",
                        "cursor",
                        "dtype",
                        "expected_state_sha256",
                        "page_size",
                        "shape",
                        "steps",
                        "stream_id",
                        "units",
                    }
                ),
            )
            arguments = dict(params)
            arguments["source"] = SourceInput.from_dict(arguments["source"])
            result = self.owner.admit_computer_input(**arguments)
        elif operation == "activate":
            self._require(
                params,
                required=frozenset(
                    {"context", "operation_id", "target_manifest_sha256"}
                ),
            )
            result = self.owner.activate_checkpoint(**dict(params))
        elif operation == "propose_effect":
            self._require(
                params,
                required=frozenset(
                    {
                        "observed",
                        "operation_id",
                        "payload",
                        "readout",
                        "scope",
                        "target",
                    }
                ),
                optional=frozenset(
                    {
                        "context",
                        "goal_id",
                        "model_applicable",
                        "prepared_query",
                        "task_feasible",
                    }
                ),
            )
            arguments = dict(params)
            arguments["readout"] = self.owner._readout_from_dict(
                arguments["readout"]
            )
            result = self.owner.propose_effect(**arguments)
        elif operation == "admit_acknowledgment":
            self._require(
                params,
                required=frozenset(
                    {"acknowledgment", "prediction_id"}
                ),
                optional=frozenset(
                    {"attribution_candidates", "learn_chart_ids"}
                ),
            )
            arguments = dict(params)
            arguments["acknowledgment"] = WorldAcknowledgment.from_dict(
                arguments["acknowledgment"]
            )
            if "attribution_candidates" in arguments:
                arguments["attribution_candidates"] = tuple(
                    arguments["attribution_candidates"]
                )
            if arguments.get("learn_chart_ids") is not None:
                arguments["learn_chart_ids"] = tuple(
                    arguments["learn_chart_ids"]
                )
            result = self.owner.admit_acknowledgment(**arguments)
        elif operation == "preview_forget":
            self._require(
                params, required=frozenset({"revision_ids"})
            )
            result = self.owner.preview_forget(params["revision_ids"])
        elif operation == "forget":
            self._require(
                params,
                required=frozenset(
                    {
                        "grant",
                        "operation_id",
                        "preview_id",
                        "revision_ids",
                        "scope",
                    }
                ),
                optional=frozenset({"delete_bytes"}),
            )
            arguments = dict(params)
            arguments["grant"] = AuthorityGrant.from_dict(arguments["grant"])
            result = self.owner.forget(**arguments)
        elif operation == "interpret":
            self._require(
                params,
                required=frozenset({"text"}),
                optional=frozenset({"context"}),
            )
            result = self.owner.interpret(**dict(params))
        elif operation == "express":
            self._require(
                params,
                required=frozenset({"bindings", "semantic_program_id"}),
                optional=frozenset({"context", "max_tokens"}),
            )
            result = self.owner.express(**dict(params))
        elif operation == "explain":
            self._require(
                params,
                required=frozenset({"allowed_labels", "query_id"}),
            )
            arguments = dict(params)
            arguments["allowed_labels"] = frozenset(arguments["allowed_labels"])
            result = self.owner.explain_query(**arguments)
        elif operation == "revise":
            self._require(
                params,
                required=frozenset({"arguments", "revision_kind"}),
            )
            arguments = params["arguments"]
            if not isinstance(arguments, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_REQUEST", "revision arguments must be an object"
                )
            if params["revision_kind"] == "repair-plans":
                result = self.owner.repair_plans(**dict(arguments))
            elif params["revision_kind"] == "derive-exact-reduction":
                result = self.owner.derive_exact_reduction(**dict(arguments))
            elif params["revision_kind"] == "record-computation":
                result = self.owner.record_computation(**dict(arguments))
            else:
                raise FieldIntelligenceError(
                    "INVALID_REQUEST", "revision kind is unsupported"
                )
        elif operation == "checkpoint":
            self._require(params, required=frozenset())
            result = {
                "field_generation": self.owner.state.generation,
                "manifest_sha256": (
                    self.owner.checkpoints.current_manifest_sha256
                ),
                "revocation_generation": (
                    self.owner.state.revocation_generation
                ),
                "state_sha256": self.owner.state.state_sha256,
            }
        elif operation == "recover":
            self._require(params, required=frozenset())
            self.owner.checkpoints.recover()
            self.owner.state = self.owner.checkpoints.refresh()
            self.owner._recover_revocation()
            self.owner._recover_pending_operations()
            result = self.owner.inspect()
        else:
            raise FieldIntelligenceError(
                "UNSUPPORTED_OPERATION",
                f"surface operation is unsupported: {operation}",
            )
        return {
            "ok": True,
            "request_id": request_id,
            "result": result,
            "schema": RPC_RESPONSE_SCHEMA,
        }


__all__ = [
    "AUTHORITY_SCHEMA",
    "AuthorityGrant",
    "CapacityLimits",
    "CheckpointReceipt",
    "DeterministicWorldAdapter",
    "EvidenceEvent",
    "ExactEvidenceStore",
    "FieldIntelligenceOwner",
    "FieldIntelligenceSurface",
    "SourceInput",
    "StoredSource",
    "WorldAcknowledgment",
    "WorldAdapter",
]
