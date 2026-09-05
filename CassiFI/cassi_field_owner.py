from __future__ import annotations

"""One persistent cognitive owner and thin surfaces for the field atlas."""

import base64
import hashlib
import json
import os
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from cassi_field_atlas import (
    ATLAS_SCHEMA,
    AtlasState,
    FieldAtlas,
    FieldIntelligenceError,
    FieldProgram,
    Guard,
    PredictionRecord,
    RelationChart,
    VariableSpec,
    canonical_json_bytes,
    sha256_value,
)
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
CHECKPOINT_SCHEMA = "cassifi.field-atlas-checkpoint.v1"
ROOT_SCHEMA = "cassifi.field-atlas-root.v1"
REVOCATION_SCHEMA = "cassifi.field-revocation-fence.v1"
AUTHORITY_SCHEMA = "cassifi.external-authority-grant.v1"
RPC_SCHEMA = "cassifi.field-intelligence-request.v1"
EVIDENCE_INDEX_SCHEMA = "cassifi.evidence-index.v2"
RPC_RESPONSE_SCHEMA = "cassifi.field-intelligence-response.v1"
WORLD_ADAPTER_JOURNAL_SCHEMA = "cassifi.world-adapter-journal.v1"


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

    def __post_init__(self) -> None:
        for name in (
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
        ):
            _integer(getattr(self, name), name, minimum=1)
        if self.max_source_bytes > self.max_total_evidence_bytes:
            raise FieldIntelligenceError(
                "INVALID_CAPACITY", "per-source limit exceeds total evidence limit"
            )

    def as_dict(self) -> Mapping[str, int]:
        return {
            name: getattr(self, name)
            for name in (
                "max_branches_per_query",
                "max_charts",
                "max_plans",
                "max_predictions",
                "max_programs",
                "max_solver_iterations",
                "max_source_bytes",
                "max_state_bytes",
                "max_total_evidence_bytes",
                "max_variables",
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
            raise FieldIntelligenceError("INVALID_SOURCE", "source content must be exact bytes")
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
                len(self.span) != 2
                or any(isinstance(item, bool) or not isinstance(item, int) for item in self.span)
                or not 0 <= self.span[0] <= self.span[1] <= len(self.content)
            ):
                raise FieldIntelligenceError("INVALID_SOURCE", "source span is invalid")
        for label in self.labels:
            _identifier(label, "source access label")
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
        row = dict(value)
        try:
            row["content"] = base64.b64decode(row.pop("content_base64"), validate=True)
        except Exception as exc:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT", "pending source bytes are invalid"
            ) from exc
        row["labels"] = tuple(row["labels"])
        row["span"] = None if row["span"] is None else tuple(row["span"])
        return cls(**row)


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
        for name in ("content_sha256", "object_sha256"):
            _digest(getattr(self, name), name)
        _integer(self.byte_length, "source byte_length")
        if self.status not in {"active", "superseded", "revoked", "deleted"}:
            raise FieldIntelligenceError("INVALID_SOURCE", "source status is unsupported")
        if self.revocation_generation is not None:
            _integer(self.revocation_generation, "source revocation generation", minimum=1)

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
        row = dict(value)
        if row.pop("schema", None) != SOURCE_SCHEMA:
            raise FieldIntelligenceError("INVALID_SOURCE", "stored source schema is incompatible")
        row["labels"] = tuple(row["labels"])
        row["span"] = None if row["span"] is None else tuple(row["span"])
        return cls(**row)


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
        identity = {
            "context": dict(context),
            "derivation_roots": list(derivation_roots),
            "epistemic_type": epistemic_type,
            "event_kind": event_kind,
            "logical_sequence": logical_sequence,
            "operation_id": operation_id,
            "predecessor_state_sha256": predecessor_state_sha256,
            "source_revision_id": source_revision_id,
            "values": dict(values),
        }
        return cls(
            event_id=sha256_value(identity),
            operation_id=operation_id,
            event_kind=event_kind,
            source_revision_id=source_revision_id,
            predecessor_state_sha256=predecessor_state_sha256,
            values=dict(values),
            context=dict(context),
            epistemic_type=epistemic_type,
            derivation_roots=tuple(derivation_roots),
            logical_sequence=logical_sequence,
        )

    def __post_init__(self) -> None:
        _digest(self.event_id, "event_id")
        _identifier(self.operation_id, "operation_id")
        _identifier(self.event_kind, "event_kind")
        _digest(self.source_revision_id, "source_revision_id")
        _digest(self.predecessor_state_sha256, "predecessor_state_sha256")
        normalized: dict[str, float] = {}
        for name, value in self.values.items():
            normalized[_identifier(name, "event variable")] = _finite(value, name)
        object.__setattr__(self, "values", normalized)
        try:
            normalized_context = json.loads(canonical_json_bytes(dict(self.context)))
        except Exception as exc:
            raise FieldIntelligenceError("INVALID_EVIDENCE", "event context is invalid") from exc
        object.__setattr__(self, "context", normalized_context)
        if self.epistemic_type not in {"observed", "asserted", "derived"}:
            raise FieldIntelligenceError(
                "INVALID_EVIDENCE", "event epistemic type cannot teach a chart"
            )
        for root in self.derivation_roots:
            _digest(root, "event derivation root")
        _integer(self.logical_sequence, "logical_sequence", minimum=1)
        expected = sha256_value(
            {
                "context": dict(self.context),
                "derivation_roots": list(self.derivation_roots),
                "epistemic_type": self.epistemic_type,
                "event_kind": self.event_kind,
                "logical_sequence": self.logical_sequence,
                "operation_id": self.operation_id,
                "predecessor_state_sha256": self.predecessor_state_sha256,
                "source_revision_id": self.source_revision_id,
                "values": dict(self.values),
            }
        )
        if expected != self.event_id:
            raise FieldIntelligenceError("INVALID_EVIDENCE", "event identity is invalid")

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
        row = dict(value)
        if row.pop("schema", None) != EVIDENCE_EVENT_SCHEMA:
            raise FieldIntelligenceError("INVALID_EVIDENCE", "event schema is incompatible")
        row["derivation_roots"] = tuple(row["derivation_roots"])
        return cls(**row)


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
                active = [
                    revision_id
                    for revision_id in value.get("revision_ids", ())
                    if self.source(revision_id).status == "active"
                ]
                value["active_revision_ids"] = active
                value["schema"] = EVIDENCE_INDEX_SCHEMA
                self._save_index(value)
            else:
                self._index_cache = value
        self._index()

    def _index(self) -> dict[str, Any]:
        value = self._index_cache
        if set(value) != {
            "active_revision_ids",
            "event_ids",
            "operation_events",
            "revision_ids",
            "schema",
            "source_heads",
        } or value["schema"] != EVIDENCE_INDEX_SCHEMA:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT", "evidence index schema is incompatible"
            )
        return {
            "active_revision_ids": list(value["active_revision_ids"]),
            "event_ids": list(value["event_ids"]),
            "operation_events": dict(value["operation_events"]),
            "revision_ids": list(value["revision_ids"]),
            "schema": value["schema"],
            "source_heads": dict(value["source_heads"]),
        }

    def _save_index(self, value: Mapping[str, Any]) -> None:
        encoded = canonical_json_bytes(dict(value))
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
            raise FieldIntelligenceError("EVENT_NOT_FOUND", "evidence event is unavailable")
        return EvidenceEvent.from_dict(_canonical_read(path))

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
        self.quarantine_path = self.root / "QUARANTINE"
        for directory in (self.objects, self.manifests, self.staging, self.operations):
            directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if self.quarantine_path.exists():
            raise FieldIntelligenceError(
                "STATE_QUARANTINED", "field store requires explicit recovery"
            )
        if not self.revocation_path.exists():
            self._write_revocation(0, (), "genesis")
        if not self.current_path.exists():
            self._initialize(initial_state or AtlasState())
        self.recover()
        self.current_manifest_sha256, self.current_manifest = self._load_current()
        self.state = self._load_state(self.current_manifest)
        fence = self.revocation_fence()
        if self.state.revocation_generation > fence["generation"]:
            self._quarantine(
                "REVOCATION_ROLLBACK",
                {
                    "field_generation": self.state.revocation_generation,
                    "fence_generation": fence["generation"],
                },
            )

    def _quarantine(self, reason: str, details: Mapping[str, Any]) -> None:
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
        value = _canonical_read(self.revocation_path)
        if set(value) != {"generation", "operation_id", "revision_ids", "schema"} or value["schema"] != REVOCATION_SCHEMA:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT", "revocation fence schema is incompatible"
            )
        _integer(value["generation"], "revocation generation")
        for revision_id in value["revision_ids"]:
            _digest(revision_id, "revoked revision")
        return value

    def advance_revocation(
        self, revision_ids: Sequence[str], *, operation_id: str
    ) -> Mapping[str, Any]:
        with self._lock:
            _identifier(operation_id, "operation_id")
            targets = tuple(sorted({_digest(item, "revision_id") for item in revision_ids}))
            if not targets:
                raise FieldIntelligenceError(
                    "INVALID_REVOCATION", "revocation target cannot be empty"
                )
            current = self.revocation_fence()
            if current["operation_id"] == operation_id:
                if tuple(current["revision_ids"]) != targets:
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT", "revocation operation target conflicts"
                    )
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
        payload = json.loads(state.encode())
        for chart in payload["charts"]:
            page = canonical_json_bytes(chart["numeric_field"])
            page_sha = _put_object(self.objects, page)
            chart["numeric_field"] = {
                "object_sha256": page_sha,
                "schema": "cassifi.numeric-page-reference.v1",
            }
        descriptor = canonical_json_bytes(
            {"schema": ROOT_SCHEMA, "state": payload, "state_sha256": state.state_sha256}
        )
        if len(descriptor) > self.limits.max_state_bytes:
            raise FieldIntelligenceError(
                "STATE_CAPACITY",
                "field structural root exceeds its configured byte limit",
                details={"bytes": len(descriptor), "limit": self.limits.max_state_bytes},
            )
        return _put_object(self.objects, descriptor), state.state_sha256

    def _hydrate_descriptor(self, descriptor_sha256: str) -> AtlasState:
        path = self.objects / _digest(descriptor_sha256, "state descriptor")
        try:
            encoded = path.read_bytes()
        except OSError as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT", "state descriptor is unavailable"
            ) from exc
        if hashlib.sha256(encoded).hexdigest() != descriptor_sha256:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT", "state descriptor identity is invalid"
            )
        try:
            root = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT", "state descriptor is unreadable"
            ) from exc
        if (
            not isinstance(root, dict)
            or set(root) != {"schema", "state", "state_sha256"}
            or root["schema"] != ROOT_SCHEMA
        ):
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT", "state descriptor schema is invalid"
            )
        state_payload = root["state"]
        if not isinstance(state_payload, dict):
            raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "state payload is invalid")
        for chart in state_payload["charts"]:
            reference = chart["numeric_field"]
            if (
                not isinstance(reference, dict)
                or set(reference) != {"object_sha256", "schema"}
                or reference["schema"] != "cassifi.numeric-page-reference.v1"
            ):
                raise FieldIntelligenceError(
                    "CHECKPOINT_CORRUPT", "numeric page reference is invalid"
                )
            page_sha = _digest(reference["object_sha256"], "numeric page object")
            try:
                page = (self.objects / page_sha).read_bytes()
            except OSError as exc:
                raise FieldIntelligenceError(
                    "CHECKPOINT_CORRUPT", "numeric page object is unavailable"
                ) from exc
            if hashlib.sha256(page).hexdigest() != page_sha:
                raise FieldIntelligenceError(
                    "CHECKPOINT_CORRUPT", "numeric page object identity is invalid"
                )
            chart["numeric_field"] = json.loads(page.decode("utf-8"))
        state = AtlasState.decode(canonical_json_bytes(state_payload))
        if state.state_sha256 != _digest(root["state_sha256"], "state_sha256"):
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT", "hydrated state identity does not match"
            )
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
        path = self.manifests / _digest(digest, "manifest_sha256")
        value = _canonical_read(path)
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
        if set(value) != required or value["schema"] != CHECKPOINT_SCHEMA:
            raise FieldIntelligenceError(
                "CHECKPOINT_CORRUPT", "checkpoint manifest schema is invalid"
            )
        return value

    def _load_current(self) -> tuple[str, Mapping[str, Any]]:
        try:
            text = self.current_path.read_text(encoding="ascii")
        except OSError as exc:
            raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "CURRENT is unreadable") from exc
        if not text.endswith("\n"):
            raise FieldIntelligenceError("CHECKPOINT_CORRUPT", "CURRENT is malformed")
        digest = _digest(text[:-1], "CURRENT")
        return digest, self._manifest(digest)

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

    def _stage_path(self, operation_id: str) -> Path:
        return self.staging / hashlib.sha256(operation_id.encode("utf-8")).hexdigest()

    def recover(self) -> None:
        with self._lock:
            current_sha, _ = self._load_current()
            for path in sorted(self.staging.iterdir()):
                if not path.is_file():
                    continue
                staged = _canonical_read(path)
                required = {
                    "manifest_sha256",
                    "operation_id",
                    "parent_manifest_sha256",
                    "semantic_sha256",
                }
                if set(staged) != required:
                    self._quarantine("STAGE_INVALID", {"path": path.name})
                manifest_sha = _digest(staged["manifest_sha256"], "staged manifest")
                manifest = self._manifest(manifest_sha)
                if manifest["operation_id"] != staged["operation_id"]:
                    self._quarantine("STAGE_CONFLICT", {"path": path.name})
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
                operation_record = {
                    "manifest_sha256": manifest_sha,
                    "operation_id": staged["operation_id"],
                    "semantic_sha256": staged["semantic_sha256"],
                }
                _atomic_write(
                    self._operation_path(staged["operation_id"]),
                    canonical_json_bytes(operation_record),
                )
                path.unlink()

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
            if len(encoded) > self.limits.max_state_bytes:
                raise FieldIntelligenceError(
                    "STATE_CAPACITY",
                    "field state exceeds the configured byte limit",
                    details={"bytes": len(encoded), "limit": self.limits.max_state_bytes},
                )
            semantic = sha256_value(
                {
                    "event_id": event_id,
                    "state_sha256": successor.state_sha256,
                    "transition": dict(transition),
                }
            )
            operation_path = self._operation_path(operation_id)
            if operation_path.exists():
                existing = _canonical_read(operation_path)
                if (
                    existing.get("operation_id") != operation_id
                    or existing.get("semantic_sha256") != semantic
                ):
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "operation identity is bound to a different field transition",
                    )
                manifest_sha = existing["manifest_sha256"]
                manifest = self._manifest(manifest_sha)
                return CheckpointReceipt(
                    operation_id=operation_id,
                    manifest_sha256=manifest_sha,
                    state_sha256=manifest["state_sha256"],
                    predecessor_manifest_sha256=manifest["parent_manifest_sha256"],
                    generation=manifest["generation"],
                    replayed=True,
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
            staged = {
                "manifest_sha256": manifest_sha,
                "operation_id": operation_id,
                "parent_manifest_sha256": current_sha,
                "semantic_sha256": semantic,
            }
            stage_path = self._stage_path(operation_id)
            _atomic_write(stage_path, canonical_json_bytes(staged))
            _atomic_write(self.current_path, (manifest_sha + "\n").encode("ascii"))
            operation_record = {
                "manifest_sha256": manifest_sha,
                "operation_id": operation_id,
                "semantic_sha256": semantic,
            }
            _atomic_write(operation_path, canonical_json_bytes(operation_record))
            try:
                stage_path.unlink()
            except FileNotFoundError:
                pass
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
            return self.state

    def load_version(self, manifest_sha256: str) -> AtlasState:
        manifest = self._manifest(manifest_sha256)
        fence = self.revocation_fence()
        if manifest["revocation_generation"] < fence["generation"]:
            raise FieldIntelligenceError(
                "STALE_REVOCATION",
                "old field generation cannot bypass a newer revocation boundary",
            )
        return self._load_state(manifest)


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
        _integer(self.generation, "authority generation")

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
        if self.status not in {"succeeded", "failed", "unknown"}:
            raise FieldIntelligenceError(
                "INVALID_ACKNOWLEDGMENT", "world acknowledgment status is unsupported"
            )
        if not isinstance(self.source_content, bytes):
            raise FieldIntelligenceError(
                "INVALID_ACKNOWLEDGMENT", "acknowledgment source must be exact bytes"
            )
        normalized_values = {
            _identifier(name, "acknowledgment variable"): _finite(
                value, "acknowledgment value"
            )
            for name, value in self.observed_values.items()
        }
        object.__setattr__(self, "observed_values", normalized_values)
        try:
            normalized_context = json.loads(canonical_json_bytes(dict(self.context)))
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
    def from_dict(cls, value: Mapping[str, Any]) -> WorldAcknowledgment:
        row = dict(value)
        try:
            row["source_content"] = base64.b64decode(
                row.pop("source_content_base64"), validate=True
            )
        except Exception as exc:
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "pending acknowledgment bytes are invalid",
            ) from exc
        return cls(**row)


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
        journal = Path(path)
        journal.mkdir(parents=True, exist_ok=True)
        if self._journal is not None and self._journal != journal:
            raise FieldIntelligenceError(
                "ADAPTER_DURABILITY",
                "world adapter is already bound to another durable journal",
            )
        self._journal = journal

    def _operation_path(self, operation_id: str) -> Path:
        _identifier(operation_id, "world operation_id")
        if self._journal is None:
            raise FieldIntelligenceError(
                "ADAPTER_DURABILITY",
                "world adapter must be bound to a durable journal before use",
            )
        return self._journal / hashlib.sha256(operation_id.encode("utf-8")).hexdigest()

    @staticmethod
    def _request(
        operation_id: str,
        action: str,
        target: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return {
            "action": action,
            "operation_id": operation_id,
            "payload": json.loads(canonical_json_bytes(dict(payload))),
            "target": target,
        }

    def resolve(self, operation_id: str) -> WorldAcknowledgment | None:
        path = self._operation_path(operation_id)
        if not path.is_file():
            return None
        record = _canonical_read(path)
        if (
            set(record) != {"acknowledgment", "request", "schema", "status"}
            or record["schema"] != WORLD_ADAPTER_JOURNAL_SCHEMA
            or record["status"] not in {"executing", "acknowledged"}
        ):
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "world adapter journal record is incompatible",
            )
        if record["status"] == "executing":
            return None
        if not isinstance(record["acknowledgment"], Mapping):
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT",
                "world adapter acknowledgment is unavailable",
            )
        return WorldAcknowledgment.from_dict(record["acknowledgment"])

    def execute_once(
        self, *, operation_id: str, action: str, target: str, payload: Mapping[str, Any]
    ) -> WorldAcknowledgment:
        with self._lock:
            request = self._request(operation_id, action, target, payload)
            path = self._operation_path(operation_id)
            if path.is_file():
                record = _canonical_read(path)
                if record.get("request") != request:
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "world operation identity has different effect semantics",
                    )
                existing = self.resolve(operation_id)
                if existing is not None:
                    return existing
                raise FieldIntelligenceError(
                    "EFFECT_OUTCOME_UNKNOWN",
                    "world effect began without a durable acknowledgment; refusing replay",
                )
            _atomic_write(
                path,
                canonical_json_bytes(
                    {
                        "acknowledgment": None,
                        "request": request,
                        "schema": WORLD_ADAPTER_JOURNAL_SCHEMA,
                        "status": "executing",
                    }
                ),
            )
            result = self.transition(action, target, payload)
            if result.operation_id != operation_id:
                result = replace(result, operation_id=operation_id)
            _atomic_write(
                path,
                canonical_json_bytes(
                    {
                        "acknowledgment": result.as_dict(),
                        "request": request,
                        "schema": WORLD_ADAPTER_JOURNAL_SCHEMA,
                        "status": "acknowledged",
                    }
                ),
            )
            self.execute_count += 1
            return result


class FieldIntelligenceOwner:
    """Sole publisher for field, evidence, plans, and predictive episodes."""

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
                        "schema": "cassifi.authority-control.v1",
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

    def _stage_pending(
        self,
        *,
        operation_id: str,
        kind: str,
        payload: Mapping[str, Any],
    ) -> None:
        envelope = {
            "kind": _identifier(kind, "pending operation kind"),
            "operation_id": operation_id,
            "payload": json.loads(canonical_json_bytes(dict(payload))),
            "schema": "cassifi.pending-owner-operation.v1",
        }
        path = self._pending_file(operation_id)
        encoded = canonical_json_bytes(envelope)
        if path.exists():
            if path.read_bytes() != encoded:
                raise FieldIntelligenceError(
                    "OPERATION_CONFLICT",
                    "pending operation identity has different semantics",
                )
            return
        _atomic_write(path, encoded)

    def _finish_pending(self, operation_id: str) -> None:
        try:
            self._pending_file(operation_id).unlink()
        except FileNotFoundError:
            pass

    def _recover_pending_operations(self) -> None:
        fatal_codes = {
            "CHECKPOINT_CORRUPT",
            "PENDING_OPERATION_CORRUPT",
            "PERSISTENCE_CORRUPT",
            "REVOCATION_FENCE",
            "STALE_REVOCATION",
        }
        for path in sorted(self.pending_path.iterdir()):
            if not path.is_file():
                continue
            envelope = _canonical_read(path)
            if (
                set(envelope) != {"kind", "operation_id", "payload", "schema"}
                or envelope["schema"] != "cassifi.pending-owner-operation.v1"
                or not isinstance(envelope["payload"], Mapping)
            ):
                raise FieldIntelligenceError(
                    "PENDING_OPERATION_CORRUPT",
                    "pending owner operation cannot be recovered safely",
                )
            operation_id = _identifier(envelope["operation_id"], "operation_id")
            try:
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
        value = dict(_canonical_read(self.authority_path))
        if set(value) != {"generation", "schema", "used_grant_ids"} or value["schema"] != "cassifi.authority-control.v1":
            raise FieldIntelligenceError(
                "PERSISTENCE_CORRUPT", "authority control schema is incompatible"
            )
        _integer(value["generation"], "authority generation")
        for grant_id in value["used_grant_ids"]:
            _identifier(grant_id, "used grant_id")
        return value

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
        _atomic_write(self.authority_path, canonical_json_bytes(value))

    def _validate_grant(
        self,
        grant: AuthorityGrant,
        *,
        operation: str,
        target: str,
        scope: str,
        consume: bool,
    ) -> None:
        control = self._authority_control()
        if not grant.permits(
            operation=operation,
            target=target,
            scope=scope,
            generation=control["generation"],
        ):
            raise FieldIntelligenceError(
                "AUTHORITY_REQUIRED", "grant does not authorize this exact operation"
            )
        if grant.grant_id in control["used_grant_ids"]:
            raise FieldIntelligenceError(
                "AUTHORITY_CONSUMED", "one-use authority grant was already consumed"
            )
        if consume and grant.one_use:
            control["used_grant_ids"].append(grant.grant_id)
            _atomic_write(self.authority_path, canonical_json_bytes(control))

    def _check_capacity(self, state: AtlasState) -> None:
        rows = {
            "charts": (len(state.charts), self.limits.max_charts),
            "plans": (len(state.plans), self.limits.max_plans),
            "predictions": (len(state.predictions), self.limits.max_predictions),
            "programs": (
                len(state.programs) + len(state.constructions) + len(state.macros),
                self.limits.max_programs,
            ),
            "variables": (len(state.variables), self.limits.max_variables),
        }
        exceeded = {
            name: {"actual": actual, "limit": limit}
            for name, (actual, limit) in rows.items()
            if actual > limit
        }
        if len(state.encode()) > self.limits.max_state_bytes:
            exceeded["state_bytes"] = {
                "actual": len(state.encode()),
                "limit": self.limits.max_state_bytes,
            }
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
        self._check_capacity(successor)
        receipt = self.checkpoints.commit(
            operation_id=operation_id,
            successor=successor,
            event_id=event_id,
            transition=transition,
        )
        self.state = self.checkpoints.state
        return receipt
    def _committed_receipt(
        self,
        operation_id: str,
        *,
        expected_transition: Mapping[str, Any] | None = None,
    ) -> CheckpointReceipt | None:
        path = self.checkpoints._operation_path(operation_id)
        if not path.exists():
            return None
        record = _canonical_read(path)
        manifest = self.checkpoints._manifest(record["manifest_sha256"])
        if (
            expected_transition is not None
            and canonical_json_bytes(manifest["transition"])
            != canonical_json_bytes(dict(expected_transition))
        ):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "operation identity is already bound to different semantics",
            )
        return CheckpointReceipt(
            operation_id=operation_id,
            manifest_sha256=record["manifest_sha256"],
            state_sha256=manifest["state_sha256"],
            predecessor_manifest_sha256=manifest["parent_manifest_sha256"],
            generation=manifest["generation"],
            replayed=True,
        )

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
                operation_path = self.checkpoints._operation_path(operation_id)
                if operation_path.exists():
                    record = _canonical_read(operation_path)
                    manifest = self.checkpoints._manifest(
                        record["manifest_sha256"]
                    )
                    self._finish_pending(operation_id)
                    return {
                        "event": event.as_dict(),
                        "receipt": CheckpointReceipt(
                            operation_id=operation_id,
                            manifest_sha256=record["manifest_sha256"],
                            state_sha256=manifest["state_sha256"],
                            predecessor_manifest_sha256=manifest[
                                "parent_manifest_sha256"
                            ],
                            generation=manifest["generation"],
                            replayed=True,
                        ).as_dict(),
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


    def query(
        self,
        *,
        observed: Mapping[str, float],
        requested: Sequence[str],
        context: Mapping[str, Any] | None = None,
        method: str = "auto",
        tolerance: float = 1e-10,
    ) -> Mapping[str, Any]:
        result = self.atlas.query(
            self.state,
            observed=observed,
            requested=requested,
            context=context,
            valid_source_revision_ids=self.evidence.active_revision_ids(),
            method=method,
            tolerance=tolerance,
            max_iterations=self.limits.max_solver_iterations,
            max_branches=self.limits.max_branches_per_query,
        )
        return result.as_dict()

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
    ) -> ActionDecision:
        return self.cognition.certify_action(
            self.state,
            observed=observed,
            readout=readout,
            context=context,
            valid_source_revision_ids=self.evidence.active_revision_ids(),
            authority_current=authority_current,
            task_feasible=task_feasible,
            model_applicable=model_applicable,
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
    ) -> Mapping[str, Any]:
        with self._lock:
            prior = next(
                (
                    row
                    for row in self.state.predictions
                    if row.operation_id == operation_id
                ),
                None,
            )
            if prior is not None:
                expected = {
                    "context": dict(context or {}),
                    "goal_id": goal_id,
                    "observed": dict(observed),
                    "payload": dict(payload),
                    "readout": readout.as_dict(),
                    "scope": scope,
                    "target": target,
                }
                actual = {
                    "context": prior.query.get("context"),
                    "goal_id": prior.goal_id,
                    "observed": prior.query.get("observed"),
                    "payload": prior.query.get("payload"),
                    "readout": prior.query.get("readout"),
                    "scope": prior.query.get("scope"),
                    "target": prior.query.get("target"),
                }
                if canonical_json_bytes(expected) != canonical_json_bytes(actual):
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "effect operation identity has different proposal semantics",
                    )
                receipt = self._committed_receipt(
                    f"proposal:{operation_id}"
                )
                return {
                    "decision": prior.query["decision"],
                    "prediction": prior.as_dict(),
                    "receipt": None if receipt is None else receipt.as_dict(),
                    "status": prior.status,
                }
            decision = self.action_decision(
                observed=observed,
                readout=readout,
                context=context,
                authority_current=False,
                task_feasible=task_feasible,
                model_applicable=model_applicable,
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
                    "readout": readout.as_dict(),
                    "scope": scope,
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
            if existing is None:
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
                    transition={"kind": "effect-proposed", "prediction_id": prediction.prediction_id},
                )
            elif existing != prediction:
                raise FieldIntelligenceError(
                    "PREDICTION_CONFLICT", "effect proposal identity conflicts"
                )
            else:
                receipt = CheckpointReceipt(
                    operation_id=f"proposal:{operation_id}",
                    manifest_sha256=self.checkpoints.current_manifest_sha256,
                    state_sha256=self.state.state_sha256,
                    predecessor_manifest_sha256=self.checkpoints.current_manifest_sha256,
                    generation=self.state.generation,
                    replayed=True,
                )
            return {
                "decision": decision.as_dict(),
                "prediction": prediction.as_dict(),
                "receipt": receipt.as_dict(),
                "status": "proposed",
            }

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
                    "PREDICTION_NOT_FOUND", "effect prediction is unavailable"
                )
            if prediction.status == "acknowledged":
                return {"prediction": prediction.as_dict(), "status": "already-acknowledged"}
            if prediction.status not in {"proposed", "pending"}:
                raise FieldIntelligenceError(
                    "PROPOSAL_STALE", "effect prediction is no longer dispatchable"
                )
            target = prediction.query["target"]
            scope = prediction.query["scope"]
            operation_id = prediction.operation_id
            assert operation_id is not None
            action = prediction.predicted["action"]
            self._validate_grant(
                grant,
                operation="effect",
                target=target,
                scope=scope,
                consume=False,
            )
            readout = self._readout_from_dict(prediction.query["readout"])
            decision = self.action_decision(
                observed=prediction.query["observed"],
                readout=readout,
                context=prediction.query["context"],
                authority_current=True,
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
                chart.chart_id: chart.version for chart in self.state.charts
            }
            if any(
                current_versions.get(chart_id) != version
                for chart_id, version in prediction.dependency_versions
            ) or not set(prediction.source_revision_ids).issubset(
                self.evidence.active_revision_ids()
            ):
                raise FieldIntelligenceError(
                    "PROPOSAL_STALE", "effect dependencies changed before dispatch"
                )
            if prediction.status == "proposed":
                pending = replace(prediction, status="pending")
                predictions = tuple(
                    pending if row.prediction_id == prediction_id else row
                    for row in self.state.predictions
                )
                successor = self.state.with_transition(
                    "effect-pending",
                    {"operation_id": operation_id, "prediction_id": prediction_id},
                    predictions=predictions,
                )
                self._publish(
                    operation_id=f"pending:{operation_id}",
                    successor=successor,
                    event_id=None,
                    transition={"kind": "effect-pending", "prediction_id": prediction_id},
                )
                prediction = pending
            self._validate_grant(
                grant,
                operation="effect",
                target=target,
                scope=scope,
                consume=True,
            )
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
            if prediction.status == "acknowledged":
                if prediction.actual != actual:
                    raise FieldIntelligenceError(
                        "ACKNOWLEDGMENT_CONFLICT",
                        "operation already has another outcome",
                    )
                self._finish_pending(journal_operation_id)
                return {"prediction": prediction.as_dict(), "status": "replayed"}
            if learn_chart_ids is not None and (
                len(attribution_candidates) != 1
                or attribution_candidates[0] != "transition-model"
            ):
                raise FieldIntelligenceError(
                    "ATTRIBUTION_UNRESOLVED",
                    "specific model learning requires resolved transition attribution",
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
                },
            )
            self._finish_pending(journal_operation_id)
            return {
                "acknowledgment_id": acknowledgment.acknowledgment_id,
                "prediction": resolved.as_dict(),
                "receipt": receipt.as_dict(),
                "status": "acknowledged",
            }

    def recover_pending_effects(self, adapter: WorldAdapter) -> tuple[Mapping[str, Any], ...]:
        self._prepare_world_adapter(adapter)
        results: list[Mapping[str, Any]] = []
        for prediction in tuple(self.state.predictions):
            if prediction.status != "pending" or prediction.operation_id is None:
                continue
            acknowledgment = adapter.resolve(prediction.operation_id)
            if acknowledgment is None:
                results.append(
                    {
                        "operation_id": prediction.operation_id,
                        "status": "awaiting-acknowledgment",
                    }
                )
            else:
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
        observed: Mapping[str, float],
        requested: Sequence[str],
        context: Mapping[str, Any] | None,
        allowed_labels: frozenset[str],
    ) -> Mapping[str, Any]:
        result = self.atlas.query(
            self.state,
            observed=observed,
            requested=requested,
            context=context,
            valid_source_revision_ids=self.evidence.active_revision_ids(),
            max_branches=self.limits.max_branches_per_query,
            max_iterations=self.limits.max_solver_iterations,
        )
        allowed_sources = frozenset(
            revision_id
            for revision_id in self.evidence.active_revision_ids()
            if set(self.evidence.source(revision_id).labels).issubset(allowed_labels)
        )
        return self.cognition.explain_query(
            self.state,
            result,
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
        binding = {
            "affected_chart_ids": affected_charts,
            "affected_program_ids": affected_programs,
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
            replay = self._committed_receipt(operation_id)
            if replay is not None:
                manifest = self.checkpoints._manifest(
                    replay.manifest_sha256
                )
                transition = manifest["transition"]
                expected_targets = sorted(
                    _digest(item, "revision_id") for item in revision_ids
                )
                if (
                    transition.get("source_revision_ids")
                    != expected_targets
                    or transition.get("delete_bytes") is not delete_bytes
                    or transition.get("scope") != scope
                ):
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "forget operation identity has different semantics",
                    )
                return {
                    "adaptive_forgetting": True,
                    "backup_erasure": False,
                    "exact_bytes_deleted": delete_bytes,
                    "preview_id": preview_id,
                    "receipt": replay.as_dict(),
                    "revocation_generation": manifest[
                        "revocation_generation"
                    ],
                    "source_use_revoked": True,
                }
            preview = self.preview_forget(revision_ids)
            if preview["preview_id"] != preview_id:
                raise FieldIntelligenceError(
                    "FORGET_PREVIEW_STALE",
                    "forget preview no longer matches current state and targets",
                )
            target = sha256_value(sorted(revision_ids))
            self._validate_grant(
                grant,
                operation="forget-delete" if delete_bytes else "forget",
                target=target,
                scope=scope,
                consume=True,
            )
            fence = self.checkpoints.advance_revocation(
                revision_ids, operation_id=operation_id
            )
            self.evidence.revoke(
                revision_ids,
                generation=fence["generation"],
                delete_bytes=delete_bytes,
            )
            successor, details = self.atlas.retract_sources(
                self.state,
                revision_ids,
                revocation_generation=fence["generation"],
            )
            receipt = self._publish(
                operation_id=operation_id,
                successor=successor,
                event_id=None,
                transition={
                    "delete_bytes": delete_bytes,
                    "kind": "forget",
                    "scope": scope,
                    "source_revision_ids": sorted(revision_ids),
                    **details,
                },
            )
            return {
                "adaptive_forgetting": True,
                "backup_erasure": False,
                "exact_bytes_deleted": delete_bytes,
                "preview_id": preview_id,
                "receipt": receipt.as_dict(),
                "revocation_generation": fence["generation"],
                "source_use_revoked": True,
            }

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

    def inspect(self) -> Mapping[str, Any]:
        field_bytes = len(self.state.encode())
        evidence_bytes = self.evidence.physical_bytes()
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
                    "variables": len(self.state.variables),
                },
            },
            "checkpoint_manifest_sha256": self.checkpoints.current_manifest_sha256,
            "field_generation": self.state.generation,
            "field_state_sha256": self.state.state_sha256,
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
        elif operation in {"query", "continue_inquiry"}:
            self._require(
                params,
                required=frozenset({"observed", "requested"}),
                optional=frozenset({"context", "method", "tolerance"}),
            )
            result = self.owner.query(**dict(params))
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
                required=frozenset(
                    {
                        "allowed_labels",
                        "context",
                        "observed",
                        "requested",
                    }
                ),
            )
            arguments = dict(params)
            arguments["allowed_labels"] = frozenset(
                arguments["allowed_labels"]
            )
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
