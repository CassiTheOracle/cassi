"""Versioned regional storage and scheduling for :mod:`cassi_field_computer`.

This module is implementation support for ``FieldComputer`` rather than a
second computer.  It owns no persistent state: every adaptive value, queue
entry, automaton lane, continuation, and resource counter is encoded in the
single immutable float64 field returned to the caller.  Host objects decoded
here are disposable views over that field.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from types import CodeType, FunctionType, MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from cassi_constraint_dynamics import (
    ExcitableConstraintController,
    ExcitableConstraintProfile,
    ExcitableConstraintState,
)

REGIONAL_SCHEMA = "cassifi.field-computer.v3"
REGIONAL_LAYOUT = "field-computer-regional-nine-plane-v1"
REGIONAL_MAGIC = 0xC5FC0003
REGIONAL_LAYOUT_REVISION = 1
U32_MAX = 2**32 - 1
U64_MAX = 2**64 - 1
PERSISTENCE_PAGE_WORDS = 4_096

HEADER_WORDS = 64
DIRECTORY_WORDS = 16

# Header coordinates.
H_MAGIC = 0
H_LAYOUT_REVISION = 1
H_TOTAL_WORDS = 2
H_DIRECTORY_CAPACITY = 3
H_CLOCK = 4
H_NEXT_SEQUENCE = 6
H_BASE_EPOCH = 8
H_ACTIVE_CONTINUATION = 10
H_FREE_CURSOR = 12
H_QUEUE = 13
H_PROGRAM_CATALOG = 15
H_LEFT_STACK = 17
H_RIGHT_STACK = 19
H_SCHEDULER_PHASE = 21
H_STATUS = 22
H_REASON = 23
H_LEDGER = 24
H_PROFILE_SHA = 26
H_CATALOG_SHA = 34
H_REGISTRY = 42
H_ROOT_SCOPE = 44

STATUS_RUNNING = 0
STATUS_HALTED = 1
STATUS_WAITING = 2
STATUS_EXHAUSTED = 3
STATUS_FAULTED = 4
STATUS_COUNTER_EXHAUSTED = 5
STATUS_NAMES = {
    STATUS_RUNNING: "running",
    STATUS_HALTED: "halted",
    STATUS_WAITING: "waiting",
    STATUS_EXHAUSTED: "exhausted",
    STATUS_FAULTED: "faulted",
    STATUS_COUNTER_EXHAUSTED: "counter-exhausted",
}
REASON_NONE = 0
REASON_HALT = 1
REASON_NO_READY_EVENT = 2
REASON_STEP_BUDGET = 3
REASON_CAPACITY = 4
REASON_INVALID_INSTRUCTION = 5
REASON_KERNEL_FAULT = 6
REASON_COUNTER_EXHAUSTED = 7
REASON_NAMES = {
    REASON_NONE: None,
    REASON_HALT: "halt",
    REASON_NO_READY_EVENT: "no-ready-event",
    REASON_STEP_BUDGET: "max_steps",
    REASON_CAPACITY: "capacity",
    REASON_INVALID_INSTRUCTION: "invalid-instruction",
    REASON_KERNEL_FAULT: "kernel-fault",
    REASON_COUNTER_EXHAUSTED: "counter-exhausted",
}

# Region kinds and codecs are fixed catalog values.
KIND_FREE = 0
KIND_REGISTRY = 1
KIND_SCOPE = 2
KIND_PROGRAM = 3
KIND_QUEUE = 4
KIND_AUTOMATON = 5
KIND_LEDGER = 6
KIND_VALUE = 7
KIND_CONTINUATION = 8
KIND_RELATION = 9
KIND_PROCEDURE = 10
KIND_EVIDENCE_PROGRESS = 11
KIND_BINDINGS = 12
KIND_CREDIT = 13
KIND_QUARANTINE = 14
KIND_NAMES = {
    KIND_REGISTRY: "registry",
    KIND_SCOPE: "scope",
    KIND_PROGRAM: "program",
    KIND_QUEUE: "queue",
    KIND_AUTOMATON: "automaton",
    KIND_LEDGER: "ledger",
    KIND_VALUE: "value",
    KIND_CONTINUATION: "continuation",
    KIND_RELATION: "relation",
    KIND_PROCEDURE: "procedure",
    KIND_EVIDENCE_PROGRESS: "evidence-progress",
    KIND_BINDINGS: "bindings",
    KIND_CREDIT: "credit",
    KIND_QUARANTINE: "quarantine",
}
CODEC_JSON = 1
CODEC_WORDS = 2

FLAG_LIVE = 1
FLAG_IMMUTABLE = 2
FLAG_QUARANTINED = 4
FLAG_PROTECTED = 8

RIGHT_READ = 1
RIGHT_WRITE = 2
RIGHT_EXECUTE = 4
RIGHT_EMIT = 8
RIGHT_MANAGE = 16
RIGHT_ALL = RIGHT_READ | RIGHT_WRITE | RIGHT_EXECUTE | RIGHT_EMIT | RIGHT_MANAGE

# Canonical semantic identities carried inside the same regional image.  These
# are logical records rather than additional adaptive owners: kernels decode
# and update them only as values of field-resident regions.
SEMANTIC_RECORD_SCHEMA_VERSION = 1
SEMANTIC_RECORD_KINDS = (
    "Assessment",
    "Binding",
    "Event",
    "Obligation",
    "Program",
    "Value",
)
SEMANTIC_EPISTEMIC_KINDS = (
    "assessed",
    "asserted",
    "assumed",
    "attributed",
    "corrected",
    "derived",
    "hypothesized",
    "hypothetical",
    "induced",
    "observed",
    "predicted",
    "proposed",
)
SEMANTIC_ANSWER_STATUSES = (
    "alternatives",
    "non-identifiable",
    "pending-observation",
    "representation-insufficient",
    "resource-exhausted",
    "support-gap",
    "supported",
    "waiting",
)

CAPABILITY_SET_SCHEMA = "cassifi.regional-capability-set.v1"
TYPE_RECORD_SCHEMA = "cassifi.regional-type-record.v1"
DEPENDENCY_LIST_SCHEMA = "cassifi.regional-dependency-list.v1"

D_GENERATION = 0
D_KIND = 1
D_CODEC = 2
D_FLAGS = 3
D_BASE = 4
D_USED = 5
D_CAPACITY = 6
D_SCOPE_ID = 7
D_VERSION = 8
D_READ_CAPS = 10
D_WRITE_CAPS = 11
D_PARENT_REF = 12
D_TYPE_REF = 13
D_DEPENDENCY_REF = 14
D_RESERVED = 15

_CATALOG_OPERATIONS = (
    "HALT",
    "READ",
    "WRITE",
    "WRITE_EMIT",
    "COPY",
    "ALLOC",
    "RELEASE",
    "CALL",
    "RETURN",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "EMIT",
    "AWAIT",
    "YIELD",
    "NATIVE",
)


class RegionalFieldError(ValueError):
    """A regional profile, image, reference, program, or transition is invalid."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RegionalFieldError("value is not canonical JSON") from exc


def _integer(value: Any, name: str, *, minimum: int = 0, maximum: int = U32_MAX) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise RegionalFieldError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return int(value)


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise RegionalFieldError(f"{name} must be a nonempty bounded string")
    return value


def _sha_words(digest: str) -> tuple[int, ...]:
    if not isinstance(digest, str) or len(digest) != 64:
        raise RegionalFieldError("SHA-256 text is invalid")
    try:
        raw = bytes.fromhex(digest)
    except ValueError as exc:
        raise RegionalFieldError("SHA-256 text is invalid") from exc
    return tuple(int.from_bytes(raw[index:index + 4], "little") for index in range(0, 32, 4))


def _words_sha(words: Sequence[int]) -> str:
    if len(words) != 8:
        raise RegionalFieldError("SHA-256 word record is invalid")
    return b"".join(_integer(int(word), "SHA word").to_bytes(4, "little") for word in words).hex()


def _read_u64(flat: np.ndarray, offset: int) -> int:
    return int(flat[offset]) | (int(flat[offset + 1]) << 32)


def _write_u64(flat: np.ndarray, offset: int, value: int) -> None:
    value = _integer(value, "u64", maximum=U64_MAX)
    flat[offset] = value & U32_MAX
    flat[offset + 1] = value >> 32


def _json_words(value: Any) -> tuple[int, ...]:
    raw = _canonical(value)
    if len(raw) > U32_MAX:
        raise RegionalFieldError("JSON payload exceeds u32 length")
    framed = len(raw).to_bytes(4, "little") + raw
    framed += b"\x00" * ((-len(framed)) % 4)
    return tuple(int.from_bytes(framed[index:index + 4], "little") for index in range(0, len(framed), 4))


def _decode_json_words(words: Sequence[int]) -> Any:
    raw = b"".join(_integer(int(word), "payload word").to_bytes(4, "little") for word in words)
    if len(raw) < 4:
        raise RegionalFieldError("JSON payload frame is truncated")
    length = int.from_bytes(raw[:4], "little")
    if length > len(raw) - 4 or any(raw[4 + length:]):
        raise RegionalFieldError("JSON payload frame is noncanonical")
    try:
        value = json.loads(raw[4:4 + length].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegionalFieldError("JSON payload is invalid") from exc
    if _canonical(value) != raw[4:4 + length]:
        raise RegionalFieldError("JSON payload is noncanonical")
    return value


@dataclass(frozen=True, slots=True)
class RegionalProfile:
    """Fixed geometry and bounded-work policy for a v3 field image."""

    mode_count: int = 16_384
    directory_capacity: int = 128
    max_steps: int = 1_000_000
    max_events: int = 256
    fairness_interval: int = 8
    max_scope_depth: int = 32
    max_registry_entries: int = 4096
    automaton_sites: int = 64
    automaton_scale: int = 1_000_000
    automaton_max_ticks: int = 2_000_000_000
    registry_words: int = 24_576
    queue_words: int = 16_384
    program_words: int = 16_384
    ledger_words: int = 2_048
    default_value_words: int = 4_096
    reclaim_quantum: int = 1_024
    max_native_work: int = 1_000_000
    kernel_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "mode_count", "directory_capacity", "max_events", "fairness_interval",
            "max_scope_depth", "max_registry_entries", "automaton_sites",
            "automaton_scale", "automaton_max_ticks", "registry_words", "queue_words",
            "program_words", "ledger_words", "default_value_words", "reclaim_quantum",
            "max_native_work",
        ):
            _integer(getattr(self, name), name, minimum=1)
        _integer(self.max_steps, "max_steps", minimum=0, maximum=U64_MAX - 1)
        if not isinstance(self.kernel_names, tuple) or any(
            not isinstance(name, str) or not name for name in self.kernel_names
        ):
            raise RegionalFieldError("kernel_names must be a tuple of nonempty strings")
        if len(set(self.kernel_names)) != len(self.kernel_names) or tuple(sorted(self.kernel_names)) != self.kernel_names:
            raise RegionalFieldError("kernel_names must be unique and sorted")
        if self.total_words > U32_MAX:
            raise RegionalFieldError("regional field exceeds u32 address capacity")
        minimum = HEADER_WORDS + DIRECTORY_WORDS * self.directory_capacity
        boot = (
            self.registry_words + self.queue_words + self.program_words
            + self.ledger_words + (4 * self.automaton_sites + 8)
            + 4 * self.default_value_words
        )
        if minimum + boot > self.total_words:
            raise RegionalFieldError("regional profile cannot hold its bootstrap closure")
        if self.max_events > self.max_registry_entries:
            raise RegionalFieldError("event capacity exceeds identity capacity")

    @property
    def total_words(self) -> int:
        return 9 * self.mode_count

    @property
    def shape(self) -> tuple[int, int, int]:
        return (1, self.total_words, 1)

    @property
    def state_bytes(self) -> int:
        return self.total_words * np.dtype(np.float64).itemsize

    @property
    def catalog_sha256(self) -> str:
        return hashlib.sha256(_canonical({
            "operations": _CATALOG_OPERATIONS,
            "kernels": self.kernel_names,
            "revision": 1,
        })).hexdigest()

    @property
    def fingerprint(self) -> str:
        value = asdict(self)
        value["kernel_names"] = list(self.kernel_names)
        return hashlib.sha256(_canonical({
            "schema": REGIONAL_SCHEMA,
            "layout": REGIONAL_LAYOUT,
            "catalog_sha256": self.catalog_sha256,
            **value,
        })).hexdigest()

    @property
    def profile_sha256(self) -> str:
        return self.fingerprint

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["kernel_names"] = list(self.kernel_names)
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RegionalProfile":
        if not isinstance(value, Mapping):
            raise RegionalFieldError("regional profile must be a mapping")
        row = dict(value)
        if "kernel_names" in row:
            raw = row["kernel_names"]
            if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
                raise RegionalFieldError("regional kernel_names are invalid")
            row["kernel_names"] = tuple(raw)
        try:
            return cls(**row)
        except TypeError as exc:
            raise RegionalFieldError("regional profile keys are invalid") from exc


@dataclass(frozen=True, slots=True)
class RegionRef:
    slot: int
    generation: int
    offset: int = 0
    length: int = 0
    rights: int = RIGHT_READ

    def __post_init__(self) -> None:
        _integer(self.slot, "reference slot", minimum=1)
        _integer(self.generation, "reference generation", minimum=1)
        _integer(self.offset, "reference offset")
        _integer(self.length, "reference length")
        rights = _integer(self.rights, "reference rights")
        if rights & ~RIGHT_ALL:
            raise RegionalFieldError("reference contains unknown rights")

    def as_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RegionRef":
        if not isinstance(value, Mapping) or set(value) != {"slot", "generation", "offset", "length", "rights"}:
            raise RegionalFieldError("region reference is invalid")
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class SemanticRef:
    """Stable typed reference to one immutable semantic record version."""

    id: str
    kind: str
    content_version: int

    def __post_init__(self) -> None:
        _identifier(self.id, "semantic reference ID")
        if self.kind not in SEMANTIC_RECORD_KINDS:
            raise RegionalFieldError("semantic reference kind is invalid")
        _integer(
            self.content_version,
            "semantic reference content version",
            minimum=1,
            maximum=U64_MAX,
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SemanticRef":
        if not isinstance(value, Mapping) or set(value) != {
            "content_version",
            "id",
            "kind",
        }:
            raise RegionalFieldError("semantic reference is invalid")
        return cls(
            id=value["id"],
            kind=value["kind"],
            content_version=value["content_version"],
        )


def _semantic_json(value: Any, name: str) -> Any:
    try:
        return json.loads(_canonical(value).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise RegionalFieldError(f"{name} is not canonical JSON") from exc


def canonical_semantic_record(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and detach one of the six shared semantic record families."""

    required = {
        "applicability",
        "content_version",
        "created_at",
        "dependencies",
        "derivation",
        "epistemic_kind",
        "frame",
        "id",
        "kind",
        "payload",
        "schema_version",
        "scope",
        "status",
        "supersedes",
        "support_roots",
        "units",
        "valid_time",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise RegionalFieldError("semantic record does not match the closed header")
    record = _semantic_json(dict(value), "semantic record")
    record_id = _identifier(record["id"], "semantic record ID")
    kind = record["kind"]
    if kind not in SEMANTIC_RECORD_KINDS:
        raise RegionalFieldError("semantic record kind is invalid")
    if record["schema_version"] != SEMANTIC_RECORD_SCHEMA_VERSION:
        raise RegionalFieldError("semantic record schema version is unsupported")
    version = _integer(
        record["content_version"],
        "semantic record content version",
        minimum=1,
        maximum=U64_MAX,
    )
    _integer(
        record["created_at"],
        "semantic record creation transition",
        maximum=U64_MAX,
    )
    supersedes_value = record["supersedes"]
    if supersedes_value is None:
        if version != 1:
            raise RegionalFieldError(
                "semantic revision after version one requires explicit lineage"
            )
    else:
        supersedes = SemanticRef.from_dict(supersedes_value)
        if (
            supersedes.id != record_id
            or supersedes.kind != kind
            or supersedes.content_version + 1 != version
        ):
            raise RegionalFieldError("semantic revision lineage is invalid")
    dependencies_value = record["dependencies"]
    if not isinstance(dependencies_value, list):
        raise RegionalFieldError("semantic dependencies must be a list")
    dependencies = [
        SemanticRef.from_dict(item) for item in dependencies_value
    ]
    dependency_keys = [
        (item.kind, item.id, item.content_version) for item in dependencies
    ]
    if dependency_keys != sorted(set(dependency_keys)):
        raise RegionalFieldError(
            "semantic dependencies must be sorted and duplicate-free"
        )
    roots = record["support_roots"]
    if not isinstance(roots, list):
        raise RegionalFieldError("semantic support roots must be a list")
    normalized_roots = [
        _identifier(item, "semantic support root") for item in roots
    ]
    if normalized_roots != sorted(set(normalized_roots)):
        raise RegionalFieldError(
            "semantic support roots must be sorted and duplicate-free"
        )
    if record["epistemic_kind"] not in SEMANTIC_EPISTEMIC_KINDS:
        raise RegionalFieldError("semantic epistemic kind is invalid")
    _identifier(record["status"], "semantic record status")
    for name in ("applicability", "derivation", "payload"):
        if not isinstance(record[name], dict):
            raise RegionalFieldError(f"semantic record {name} must be a mapping")
    if not isinstance(record["valid_time"], (dict, type(None))):
        raise RegionalFieldError(
            "semantic valid_time must be a mapping or null"
        )
    if not isinstance(record["scope"], (dict, str)):
        raise RegionalFieldError("semantic scope must be a mapping or string")
    if not isinstance(record["frame"], (dict, str, type(None))):
        raise RegionalFieldError(
            "semantic frame must be a mapping, string, or null"
        )
    if not isinstance(record["units"], (dict, str, type(None))):
        raise RegionalFieldError(
            "semantic units must be a mapping, string, or null"
        )
    record["dependencies"] = [item.as_dict() for item in dependencies]
    record["support_roots"] = normalized_roots
    return record


def make_semantic_record(
    *,
    record_id: str,
    kind: str,
    content_version: int,
    created_at: int,
    payload: Mapping[str, Any],
    scope: Mapping[str, Any] | str,
    epistemic_kind: str,
    status: str,
    supersedes: SemanticRef | Mapping[str, Any] | None = None,
    valid_time: Mapping[str, Any] | None = None,
    frame: Mapping[str, Any] | str | None = None,
    units: Mapping[str, Any] | str | None = None,
    dependencies: Sequence[SemanticRef | Mapping[str, Any]] = (),
    support_roots: Sequence[str] = (),
    derivation: Mapping[str, Any] | None = None,
    applicability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct one closed, immutable semantic record revision."""

    dependency_rows = [
        (
            item
            if isinstance(item, SemanticRef)
            else SemanticRef.from_dict(item)
        )
        for item in dependencies
    ]
    dependency_rows.sort(
        key=lambda item: (item.kind, item.id, item.content_version)
    )
    predecessor = (
        None
        if supersedes is None
        else (
            supersedes
            if isinstance(supersedes, SemanticRef)
            else SemanticRef.from_dict(supersedes)
        ).as_dict()
    )
    return canonical_semantic_record(
        {
            "id": record_id,
            "kind": kind,
            "schema_version": SEMANTIC_RECORD_SCHEMA_VERSION,
            "content_version": content_version,
            "created_at": created_at,
            "supersedes": predecessor,
            "scope": scope,
            "valid_time": valid_time,
            "frame": frame,
            "units": units,
            "dependencies": [item.as_dict() for item in dependency_rows],
            "support_roots": sorted(set(support_roots)),
            "derivation": dict(derivation or {}),
            "epistemic_kind": epistemic_kind,
            "applicability": dict(applicability or {}),
            "status": status,
            "payload": dict(payload),
        }
    )


def semantic_record_ref(record: Mapping[str, Any]) -> SemanticRef:
    """Return the typed immutable identity of a validated record."""

    canonical = canonical_semantic_record(record)
    return SemanticRef(
        canonical["id"],
        canonical["kind"],
        canonical["content_version"],
    )


def resolve_semantic_record(
    records: Mapping[str, Sequence[Mapping[str, Any]]],
    reference: SemanticRef | Mapping[str, Any],
    *,
    require_current: bool = False,
) -> dict[str, Any]:
    """Resolve a typed semantic version and fail closed on stale/mistyped use."""

    ref = (
        reference
        if isinstance(reference, SemanticRef)
        else SemanticRef.from_dict(reference)
    )
    raw_versions = records.get(ref.id)
    if (
        raw_versions is None
        or isinstance(raw_versions, (str, bytes, bytearray))
        or not isinstance(raw_versions, Sequence)
        or not raw_versions
    ):
        raise RegionalFieldError("semantic reference identity is unavailable")
    versions = [canonical_semantic_record(item) for item in raw_versions]
    version_numbers = [int(item["content_version"]) for item in versions]
    if version_numbers != list(range(1, len(versions) + 1)):
        raise RegionalFieldError("semantic record history is not contiguous")
    selected = versions[ref.content_version - 1] if (
        ref.content_version <= len(versions)
    ) else None
    if (
        selected is None
        or selected["id"] != ref.id
        or selected["kind"] != ref.kind
    ):
        raise RegionalFieldError("semantic reference version or type is stale")
    if require_current and ref.content_version != len(versions):
        raise RegionalFieldError("semantic reference is not current")
    return selected


@dataclass(frozen=True, slots=True)
class KernelResult:
    """One bounded native quantum over a decoded regional value."""

    state: Any
    status: str = "done"
    work: int = 1
    output: Any = None
    events: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if self.status not in {"done", "yield", "blocked", "fault"}:
            raise RegionalFieldError("native kernel returned an invalid status")
        _integer(self.work, "native work", minimum=0)
        if not isinstance(self.events, tuple) or any(not isinstance(event, Mapping) for event in self.events):
            raise RegionalFieldError("native kernel events must be a tuple of mappings")
        _canonical(self.state)
        _canonical(self.output)


NativeKernel = Callable[[Any, Mapping[str, Any], int], KernelResult]


def _code_identity(code: CodeType) -> Mapping[str, Any]:
    constants: list[Any] = []
    for value in code.co_consts:
        if isinstance(value, CodeType):
            constants.append({"code": _code_identity(value)})
        elif value is None or isinstance(value, (bool, int, float, str)):
            constants.append(value)
        elif isinstance(value, tuple):
            constants.append(
                [
                    item
                    if item is None or isinstance(item, (bool, int, float, str))
                    else {"type": type(item).__qualname__}
                    for item in value
                ]
            )
        else:
            constants.append({"type": type(value).__qualname__})
    return {
        "argcount": code.co_argcount,
        "code_b64": base64.b64encode(code.co_code).decode("ascii"),
        "constants": constants,
        "flags": code.co_flags,
        "kwonlyargcount": code.co_kwonlyargcount,
        "names": list(code.co_names),
        "posonlyargcount": code.co_posonlyargcount,
        "varnames": list(code.co_varnames),
    }


def _kernel_identity(kernel: NativeKernel) -> str:
    if not isinstance(kernel, FunctionType) or kernel.__closure__:
        raise RegionalFieldError(
            "native kernels must be closure-free module functions"
        )
    material = {
        "code": _code_identity(kernel.__code__),
        "defaults": kernel.__defaults__,
        "kwdefaults": kernel.__kwdefaults__,
        "module": kernel.__module__,
        "qualname": kernel.__qualname__,
    }
    return hashlib.sha256(_canonical(material)).hexdigest()


def _canonical_kernel_contract(
    value: Mapping[str, Any], kernel_name: str
) -> dict[str, Any]:
    required = {
        "read_capabilities",
        "state_schemas",
        "type_name",
        "write_capabilities",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise RegionalFieldError(
            f"kernel {kernel_name} contract keys are invalid"
        )
    result = copy.deepcopy(dict(value))
    result["type_name"] = _identifier(
        result["type_name"], f"kernel {kernel_name} state type"
    )
    for key in (
        "read_capabilities",
        "state_schemas",
        "write_capabilities",
    ):
        rows = result[key]
        if (
            not isinstance(rows, list)
            or not rows
            or any(
                not isinstance(item, str) or not item
                for item in rows
            )
            or rows != sorted(set(rows))
        ):
            raise RegionalFieldError(
                f"kernel {kernel_name} {key} are not canonical"
            )
    return result


@dataclass(frozen=True, slots=True)
class KernelCatalog:
    """Fixed stateless kernel mapping bound by the regional profile hash."""

    kernels: Mapping[str, NativeKernel]
    max_work: Mapping[str, int]
    contracts: Mapping[str, Mapping[str, Any]] | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.kernels, Mapping)
            or not isinstance(self.max_work, Mapping)
            or (
                self.contracts is not None
                and not isinstance(self.contracts, Mapping)
            )
        ):
            raise RegionalFieldError("kernel catalog mappings are required")
        names = tuple(sorted(self.kernels))
        if set(names) != set(self.max_work):
            raise RegionalFieldError("kernel work bounds do not match kernel names")
        raw_contracts = dict(self.contracts or {})
        if set(raw_contracts) - set(names):
            raise RegionalFieldError(
                "kernel contracts name an unknown kernel"
            )
        contracts: dict[str, Mapping[str, Any]] = {}
        for name in names:
            _identifier(name, "kernel name")
            if not callable(self.kernels[name]):
                raise RegionalFieldError("kernel entry is not callable")
            _integer(self.max_work[name], f"kernel {name} work bound", minimum=1)
            if name in raw_contracts:
                contracts[name] = MappingProxyType(
                    _canonical_kernel_contract(raw_contracts[name], name)
                )
        object.__setattr__(self, "kernels", MappingProxyType(dict(self.kernels)))
        object.__setattr__(self, "max_work", MappingProxyType(dict(self.max_work)))
        object.__setattr__(self, "contracts", MappingProxyType(contracts))

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(
            _canonical(
                {
                    "kernels": {
                        name: {
                            "contract": (
                                None
                                if name not in (self.contracts or {})
                                else dict((self.contracts or {})[name])
                            ),
                            "identity": _kernel_identity(self.kernels[name]),
                            "max_work": self.max_work[name],
                        }
                        for name in self.names
                    },
                    "operations": _CATALOG_OPERATIONS,
                    "revision": 2,
                }
            )
        ).hexdigest()

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.kernels))


EMPTY_KERNEL_CATALOG = KernelCatalog({}, {})


def _directory(flat: np.ndarray, profile: RegionalProfile) -> np.ndarray:
    start = HEADER_WORDS
    end = start + DIRECTORY_WORDS * profile.directory_capacity
    return flat[start:end].reshape(profile.directory_capacity, DIRECTORY_WORDS)


def _descriptor_ref(flat: np.ndarray, offset: int) -> RegionRef | None:
    slot = int(flat[offset])
    generation = int(flat[offset + 1])
    if slot == generation == 0:
        return None
    if slot == 0 or generation == 0:
        raise RegionalFieldError("distinguished reference is half-null")
    return RegionRef(slot, generation, rights=RIGHT_ALL)


def _write_descriptor_ref(flat: np.ndarray, offset: int, ref: RegionRef | None) -> None:
    if ref is None:
        flat[offset:offset + 2] = 0
    else:
        flat[offset] = ref.slot
        flat[offset + 1] = ref.generation


def _row_for_ref(flat: np.ndarray, profile: RegionalProfile, ref: RegionRef, *, right: int = RIGHT_READ) -> np.ndarray:
    if not ref.rights & right:
        raise RegionalFieldError("reference does not carry required rights")
    if ref.slot > profile.directory_capacity:
        raise RegionalFieldError("reference slot is outside the directory")
    row = _directory(flat, profile)[ref.slot - 1]
    if int(row[D_GENERATION]) != ref.generation or not int(row[D_FLAGS]) & FLAG_LIVE:
        raise RegionalFieldError("reference is stale or not live")
    used = int(row[D_USED])
    length = ref.length or used - ref.offset
    if ref.offset > used or length > used - ref.offset:
        raise RegionalFieldError("reference range is outside the live value")
    return row


def _payload_words(flat: np.ndarray, row: np.ndarray) -> np.ndarray:
    base = int(row[D_BASE])
    used = int(row[D_USED])
    return flat[base:base + used]


def _read_region(flat: np.ndarray, profile: RegionalProfile, ref: RegionRef) -> Any:
    row = _row_for_ref(flat, profile, ref, right=RIGHT_READ)
    words = _payload_words(flat, row)
    if int(row[D_CODEC]) == CODEC_JSON:
        return _decode_json_words([int(word) for word in words])
    if int(row[D_CODEC]) == CODEC_WORDS:
        return [int(word) for word in words]
    raise RegionalFieldError("region codec is unsupported")


def _write_region(flat: np.ndarray, profile: RegionalProfile, ref: RegionRef, value: Any) -> bool:
    row = _row_for_ref(flat, profile, ref, right=RIGHT_WRITE)
    if int(row[D_FLAGS]) & FLAG_IMMUTABLE:
        raise RegionalFieldError("immutable region cannot be written")
    if int(row[D_CODEC]) == CODEC_JSON:
        words = _json_words(value)
    elif int(row[D_CODEC]) == CODEC_WORDS:
        if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
            raise RegionalFieldError("word region requires a finite sequence")
        words = tuple(_integer(int(word), "region word") for word in value)
    else:
        raise RegionalFieldError("region codec is unsupported")
    if len(words) > int(row[D_CAPACITY]):
        raise RegionalFieldError("region value exceeds allocated capacity")
    base = int(row[D_BASE])
    old_used = int(row[D_USED])
    old = tuple(int(word) for word in flat[base:base + old_used])
    if old == words:
        return False
    version = _read_u64(row, D_VERSION)
    if version >= U64_MAX:
        raise RegionalFieldError("region version is exhausted")
    flat[base:base + int(row[D_CAPACITY])] = 0
    if words:
        flat[base:base + len(words)] = words
    row[D_USED] = len(words)
    _write_u64(row, D_VERSION, version + 1)
    return True


def _registry(flat: np.ndarray, profile: RegionalProfile) -> tuple[RegionRef, dict[str, Any]]:
    ref = _descriptor_ref(flat, H_REGISTRY)
    if ref is None:
        raise RegionalFieldError("regional image has no registry")
    value = _read_region(flat, profile, ref)
    if not isinstance(value, dict):
        raise RegionalFieldError("reference registry is invalid")
    return ref, value


def _resolve_object(flat: np.ndarray, profile: RegionalProfile, object_id: int, *, right: int = RIGHT_READ) -> RegionRef:
    object_id = _integer(object_id, "object ID", minimum=1)
    _registry_ref, registry = _registry(flat, profile)
    entry = registry.get("entries", {}).get(str(object_id))
    if not isinstance(entry, dict) or entry.get("status") != "live":
        raise RegionalFieldError("object identity is missing or tombstoned")
    ref = RegionRef.from_dict(entry["reference"])
    if not ref.rights & right:
        raise RegionalFieldError("object identity lacks required rights")
    _row_for_ref(flat, profile, ref, right=right)
    return ref


def _update_registry(flat: np.ndarray, profile: RegionalProfile, registry: Mapping[str, Any]) -> None:
    ref = _descriptor_ref(flat, H_REGISTRY)
    if ref is None:
        raise RegionalFieldError("regional image has no registry")
    writable = RegionRef(ref.slot, ref.generation, rights=RIGHT_ALL)
    _write_region(flat, profile, writable, registry)


def _find_payload_base(flat: np.ndarray, profile: RegionalProfile, capacity: int) -> int:
    arena_start = HEADER_WORDS + DIRECTORY_WORDS * profile.directory_capacity
    occupied = []
    for row in _directory(flat, profile):
        if int(row[D_FLAGS]) & (FLAG_LIVE | FLAG_QUARANTINED):
            occupied.append((int(row[D_BASE]), int(row[D_BASE]) + int(row[D_CAPACITY])))
    cursor = arena_start
    for start, end in sorted(occupied):
        if cursor + capacity <= start:
            return cursor
        cursor = max(cursor, end)
    if cursor + capacity > profile.total_words:
        raise RegionalFieldError("payload arena is exhausted")
    return cursor


def _allocate_raw(
    flat: np.ndarray,
    profile: RegionalProfile,
    *,
    kind: int,
    codec: int,
    value: Any,
    capacity: int,
    scope_id: int,
    flags: int = FLAG_LIVE,
    register: bool = True,
) -> tuple[RegionRef, int]:
    if kind not in KIND_NAMES:
        raise RegionalFieldError("region kind is invalid")
    if codec not in (CODEC_JSON, CODEC_WORDS):
        raise RegionalFieldError("region codec is invalid")
    if flags & ~(FLAG_LIVE | FLAG_IMMUTABLE | FLAG_QUARANTINED | FLAG_PROTECTED):
        raise RegionalFieldError("region flags are invalid")
    if not flags & FLAG_LIVE:
        raise RegionalFieldError("allocated region must be live")
    capacity = _integer(capacity, "region capacity", minimum=1)
    rows = _directory(flat, profile)
    start = int(flat[H_FREE_CURSOR]) % profile.directory_capacity
    selected = None
    for delta in range(profile.directory_capacity):
        index = (start + delta) % profile.directory_capacity
        if not int(rows[index, D_FLAGS]) & (FLAG_LIVE | FLAG_QUARANTINED):
            selected = index
            break
    if selected is None:
        raise RegionalFieldError("region directory is exhausted")
    row = rows[selected]
    old_generation = int(row[D_GENERATION])
    if old_generation >= U32_MAX:
        raise RegionalFieldError("region slot generation is exhausted")
    generation = old_generation + 1
    base = _find_payload_base(flat, profile, capacity)
    words = _json_words(value) if codec == CODEC_JSON else tuple(
        _integer(int(word), "region word") for word in value
    )
    if len(words) > capacity:
        raise RegionalFieldError("initial region value exceeds allocated capacity")
    row[:] = 0
    row[D_GENERATION] = generation
    row[D_KIND] = kind
    row[D_CODEC] = codec
    row[D_FLAGS] = flags
    row[D_BASE] = base
    row[D_USED] = len(words)
    row[D_CAPACITY] = capacity
    row[D_SCOPE_ID] = scope_id
    _write_u64(row, D_VERSION, 1)
    flat[base:base + capacity] = 0
    if words:
        flat[base:base + len(words)] = words
    flat[H_FREE_CURSOR] = (selected + 1) % profile.directory_capacity
    ref = RegionRef(selected + 1, generation, rights=RIGHT_ALL)
    if not register:
        return ref, 0
    registry_ref, registry = _registry(flat, profile)
    next_id = _integer(registry.get("next_id"), "next registry ID", minimum=1)
    if next_id > profile.max_registry_entries:
        raise RegionalFieldError("reference registry is exhausted")
    entries = dict(registry.get("entries", {}))
    entries[str(next_id)] = {
        "kind": KIND_NAMES[kind],
        "reference": ref.as_dict(),
        "status": "live",
    }
    updated = {**registry, "entries": entries, "next_id": next_id + 1}
    writable_registry = RegionRef(registry_ref.slot, registry_ref.generation, rights=RIGHT_ALL)
    _write_region(flat, profile, writable_registry, updated)
    return ref, next_id


def _allocate_descriptor_metadata(
    flat: np.ndarray,
    profile: RegionalProfile,
    *,
    kernel_contracts: Mapping[str, Mapping[str, Any]],
    state_object_id: int,
    argument_object_ids: Sequence[int],
    scope_id: int,
) -> None:
    state_ref = _resolve_object(
        flat, profile, state_object_id, right=RIGHT_WRITE
    )
    state_row = _row_for_ref(
        flat, profile, state_ref, right=RIGHT_WRITE
    )
    if any(
        int(state_row[column])
        for column in (
            D_READ_CAPS,
            D_WRITE_CAPS,
            D_PARENT_REF,
            D_TYPE_REF,
            D_DEPENDENCY_REF,
        )
    ):
        raise RegionalFieldError(
            "native state already has descriptor metadata"
        )
    names = sorted(kernel_contracts)
    if not names:
        raise RegionalFieldError(
            "descriptor metadata requires a kernel contract"
        )
    state_value = _read_region(flat, profile, state_ref)
    if (
        not isinstance(state_value, Mapping)
        or not isinstance(state_value.get("schema"), str)
        or not state_value["schema"]
    ):
        raise RegionalFieldError(
            "native state requires a typed schema"
        )

    def allocate(
        value: Mapping[str, Any],
        *,
        immutable: bool = True,
        capacity: int | None = None,
    ) -> int:
        words = _json_words(value)
        flags = FLAG_LIVE | FLAG_PROTECTED
        if immutable:
            flags |= FLAG_IMMUTABLE
        _ref, object_id = _allocate_raw(
            flat,
            profile,
            kind=KIND_VALUE,
            codec=CODEC_JSON,
            value=value,
            capacity=max(1, len(words), capacity or 0),
            scope_id=scope_id,
            flags=flags,
        )
        return object_id

    read_id = allocate(
        {
            "capabilities": {
                name: list(kernel_contracts[name]["read_capabilities"])
                for name in names
            },
            "mode": "read",
            "schema": CAPABILITY_SET_SCHEMA,
        }
    )
    write_id = allocate(
        {
            "capabilities": {
                name: list(kernel_contracts[name]["write_capabilities"])
                for name in names
            },
            "mode": "write",
            "schema": CAPABILITY_SET_SCHEMA,
        }
    )
    type_id = allocate(
        {
            "bootstrap_schema": state_value["schema"],
            "kernel_types": {
                name: {
                    "accepted_schemas": list(
                        kernel_contracts[name]["state_schemas"]
                    ),
                    "name": kernel_contracts[name]["type_name"],
                }
                for name in names
            },
            "name": "regional-native-state",
            "schema": TYPE_RECORD_SCHEMA,
        }
    )
    dependency_entries: list[dict[str, int]] = []
    for object_id in sorted(set(argument_object_ids)):
        argument_ref = _resolve_object(flat, profile, object_id)
        argument_row = _row_for_ref(flat, profile, argument_ref)
        dependency_entries.append(
            {
                "object_id": object_id,
                "version": _read_u64(argument_row, D_VERSION),
            }
        )
    dependency_value = {
        "entries": dependency_entries,
        "schema": DEPENDENCY_LIST_SCHEMA,
    }
    dependency_capacity = len(
        _json_words(
            {
                "entries": [
                    {**entry, "version": U64_MAX}
                    for entry in dependency_entries
                ],
                "schema": DEPENDENCY_LIST_SCHEMA,
            }
        )
    )
    dependency_id = allocate(
        dependency_value,
        immutable=False,
        capacity=dependency_capacity,
    )
    state_row[D_READ_CAPS] = read_id
    state_row[D_WRITE_CAPS] = write_id
    state_row[D_PARENT_REF] = scope_id
    state_row[D_TYPE_REF] = type_id
    state_row[D_DEPENDENCY_REF] = dependency_id


def _canonical_instruction(value: Any, length: int, index: int) -> dict[str, Any]:
    if not isinstance(value, Mapping) or "op" not in value:
        raise RegionalFieldError(f"program[{index}] must be an instruction mapping")
    row = dict(value)
    op = row.get("op")
    if not isinstance(op, str):
        raise RegionalFieldError(f"program[{index}].op must be a string")
    op = op.upper()
    if op not in _CATALOG_OPERATIONS:
        raise RegionalFieldError(f"program[{index}] uses an unknown operation")
    row["op"] = op
    if op == "HALT":
        allowed = {"op"}
    elif op in {"YIELD", "BEGIN", "COMMIT", "ROLLBACK"}:
        allowed = {"op", "next"}
    elif op in {"READ", "COPY"}:
        allowed = {"op", "source", "target", "next"}
    elif op == "WRITE":
        allowed = {"op", "target", "value", "source", "next"}
        if ("value" in row) == ("source" in row):
            raise RegionalFieldError("WRITE requires exactly one of value or source")
    elif op == "WRITE_EMIT":
        allowed = {"op", "target", "value", "source", "event", "next"}
        if ("value" in row) == ("source" in row):
            raise RegionalFieldError("WRITE_EMIT requires exactly one of value or source")
    elif op == "ALLOC":
        allowed = {"op", "kind", "codec", "value", "capacity", "target", "next"}
    elif op == "RELEASE":
        allowed = {"op", "target", "next"}
    elif op == "CALL":
        allowed = {"op", "target_pc", "next"}
    elif op == "RETURN":
        allowed = {"op"}
    elif op == "EMIT":
        allowed = {"op", "event", "next"}
    elif op == "AWAIT":
        allowed = {"op", "target", "next"}
    elif op == "NATIVE":
        allowed = {"op", "kernel", "state", "arguments", "next", "output"}
    else:
        raise RegionalFieldError("unsupported operation")
    if set(row) - allowed:
        raise RegionalFieldError(f"program[{index}] contains invalid keys")
    for key in ("next", "target_pc"):
        if key in row:
            row[key] = _integer(row[key], f"program[{index}].{key}")
            if row[key] >= length:
                raise RegionalFieldError(f"program[{index}].{key} is outside the program")
    for key in ("source", "target", "state", "output"):
        if key in row:
            operand = row[key]
            if isinstance(operand, str):
                row[key] = _identifier(operand, f"program[{index}].{key}")
            else:
                row[key] = _integer(operand, f"program[{index}].{key}", minimum=1)
    if "kernel" in row:
        row["kernel"] = _identifier(row["kernel"], f"program[{index}].kernel")
    if "event" in row and not isinstance(row["event"], Mapping):
        raise RegionalFieldError(f"program[{index}].event must be a mapping")
    _canonical(row)
    return row


def canonical_program(program: Any) -> list[dict[str, Any]]:
    if isinstance(program, (str, bytes, bytearray)) or not isinstance(program, Sequence):
        raise RegionalFieldError("regional program must be a finite instruction sequence")
    rows = list(program)
    if not rows:
        raise RegionalFieldError("regional program cannot be empty")
    return [_canonical_instruction(row, len(rows), index) for index, row in enumerate(rows)]


def _initial_registry_words(profile: RegionalProfile, ref: RegionRef) -> tuple[int, ...]:
    registry = {
        "entries": {
            "1": {
                "kind": KIND_NAMES[KIND_REGISTRY],
                "reference": ref.as_dict(),
                "status": "live",
            }
        },
        "next_id": 2,
        "schema": "cassifi.regional-reference-registry.v1",
    }
    return _json_words(registry)


def initial_field(
    profile: RegionalProfile,
    program: Any,
    *,
    values: Mapping[str, Any] | None = None,
    value_capacities: Mapping[str, int] | None = None,
    catalog: KernelCatalog = EMPTY_KERNEL_CATALOG,
    entry: int = 0,
) -> np.ndarray:
    """Create one canonical regional image with one admitted root program."""

    if not isinstance(profile, RegionalProfile):
        raise RegionalFieldError("RegionalProfile required")
    if not isinstance(catalog, KernelCatalog):
        raise RegionalFieldError("KernelCatalog required")
    if profile.kernel_names != catalog.names:
        raise RegionalFieldError("regional profile/catalog mismatch")
    rows = canonical_program(program)
    entry = _integer(entry, "entry")
    if entry >= len(rows):
        raise RegionalFieldError("entry is outside the regional program")
    field = np.zeros(profile.shape, dtype=np.float64)
    flat = field.reshape(-1)
    flat[H_MAGIC] = REGIONAL_MAGIC
    flat[H_LAYOUT_REVISION] = REGIONAL_LAYOUT_REVISION
    flat[H_TOTAL_WORDS] = profile.total_words
    flat[H_DIRECTORY_CAPACITY] = profile.directory_capacity
    _write_u64(flat, H_CLOCK, 0)
    _write_u64(flat, H_NEXT_SEQUENCE, 2)
    _write_u64(flat, H_BASE_EPOCH, 0)
    flat[H_STATUS] = STATUS_RUNNING
    flat[H_REASON] = REASON_NONE
    flat[H_PROFILE_SHA:H_PROFILE_SHA + 8] = _sha_words(profile.fingerprint)
    flat[H_CATALOG_SHA:H_CATALOG_SHA + 8] = _sha_words(catalog.fingerprint)

    arena_start = HEADER_WORDS + DIRECTORY_WORDS * profile.directory_capacity
    directory = _directory(flat, profile)
    registry_row = directory[0]
    registry_row[D_GENERATION] = 1
    registry_row[D_KIND] = KIND_REGISTRY
    registry_row[D_CODEC] = CODEC_JSON
    registry_row[D_FLAGS] = FLAG_LIVE | FLAG_PROTECTED
    registry_row[D_BASE] = arena_start
    registry_row[D_CAPACITY] = profile.registry_words
    _write_u64(registry_row, D_VERSION, 1)
    registry_ref = RegionRef(1, 1, rights=RIGHT_ALL)
    registry_words = _initial_registry_words(profile, registry_ref)
    if len(registry_words) > profile.registry_words:
        raise RegionalFieldError("registry bootstrap exceeds capacity")
    registry_row[D_USED] = len(registry_words)
    flat[arena_start:arena_start + len(registry_words)] = registry_words
    _write_descriptor_ref(flat, H_REGISTRY, registry_ref)
    flat[H_FREE_CURSOR] = 1

    scope_ref, scope_id = _allocate_raw(
        flat, profile, kind=KIND_SCOPE, codec=CODEC_JSON,
        value={"assumptions": [], "bindings": {}, "depth": 0, "live": True,
               "parent_scope_id": 0, "schema": "cassifi.regional-scope.v1"},
        capacity=profile.default_value_words, scope_id=0,
        flags=FLAG_LIVE | FLAG_PROTECTED,
    )
    _directory(flat, profile)[scope_ref.slot - 1, D_SCOPE_ID] = scope_id
    _write_descriptor_ref(flat, H_ROOT_SCOPE, scope_ref)


    ledger_ref, _ledger_id = _allocate_raw(
        flat, profile, kind=KIND_LEDGER, codec=CODEC_JSON,
        value={
            "allocations": 4, "automaton_local_ops": 0, "bytes_read": 0,
            "bytes_written": 0, "dispatches": 0, "logical_transitions": 0,
            "native_work": 0, "reclaims": 0, "scheduler_work": 0,
            "schema": "cassifi.regional-ledger.v1",
        },
        capacity=profile.ledger_words, scope_id=scope_id,
        flags=FLAG_LIVE | FLAG_PROTECTED,
    )
    _write_descriptor_ref(flat, H_LEDGER, ledger_ref)

    automaton_controller = ExcitableConstraintController(ExcitableConstraintProfile(
        size=profile.automaton_sites,
        scale=profile.automaton_scale,
        max_ticks=profile.automaton_max_ticks,
    ))
    automaton_words = [int(value) for value in automaton_controller.initial_lanes()]
    automaton_ref, automaton_id = _allocate_raw(
        flat, profile, kind=KIND_AUTOMATON, codec=CODEC_WORDS,
        value=automaton_words, capacity=len(automaton_words), scope_id=scope_id,
        flags=FLAG_LIVE | FLAG_PROTECTED,
    )

    initial_values = dict(values or {})
    capacities = dict(value_capacities or {})
    unknown_capacities = set(capacities) - set(initial_values)
    if unknown_capacities:
        raise RegionalFieldError(
            "value capacities name undeclared values: "
            + ", ".join(sorted(unknown_capacities))
        )
    named_values: dict[str, int] = {}
    for name, value in sorted(initial_values.items()):
        _identifier(name, "initial value name")
        capacity = _integer(
            capacities.get(name, profile.default_value_words),
            f"value capacity for {name}",
            minimum=1,
        )
        ref, object_id = _allocate_raw(
            flat, profile, kind=KIND_VALUE, codec=CODEC_JSON, value=value,
            capacity=capacity, scope_id=scope_id,
        )
        _ = ref
        named_values[name] = object_id

    resolved_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        resolved = dict(row)
        for key in ("source", "target", "state", "output", "arguments"):
            operand = resolved.get(key)
            if isinstance(operand, str):
                if operand not in named_values:
                    raise RegionalFieldError(
                        f"program[{index}].{key} names an unknown initial value"
                    )
                resolved[key] = named_values[operand]
        resolved_rows.append(resolved)
    rows = canonical_program(resolved_rows)
    for index, row in enumerate(rows):
        if row["op"] == "NATIVE" and row["kernel"] not in catalog.kernels:
            raise RegionalFieldError(
                f"program[{index}] names an unregistered native kernel"
            )
    metadata_groups: dict[int, dict[str, Any]] = {}
    for row in rows:
        if row["op"] != "NATIVE":
            continue
        contract = (catalog.contracts or {}).get(row["kernel"])
        if contract is None:
            continue
        state_object_id = _integer(
            row["state"], "native state object ID", minimum=1
        )
        group = metadata_groups.setdefault(
            state_object_id,
            {"argument_object_ids": set(), "kernel_contracts": {}},
        )
        group["kernel_contracts"][row["kernel"]] = contract
        arguments = row.get("arguments", {})
        if isinstance(arguments, int) and not isinstance(arguments, bool):
            group["argument_object_ids"].add(arguments)
    for state_object_id in sorted(metadata_groups):
        group = metadata_groups[state_object_id]
        _allocate_descriptor_metadata(
            flat,
            profile,
            kernel_contracts=group["kernel_contracts"],
            state_object_id=state_object_id,
            argument_object_ids=sorted(group["argument_object_ids"]),
            scope_id=scope_id,
        )
    program_ref, program_id = _allocate_raw(
        flat, profile, kind=KIND_PROGRAM, codec=CODEC_JSON,
        value={"instructions": rows, "schema": "cassifi.regional-program.v1"},
        capacity=profile.program_words, scope_id=scope_id,
        flags=FLAG_LIVE | FLAG_IMMUTABLE,
    )
    _write_descriptor_ref(flat, H_PROGRAM_CATALOG, program_ref)

    root_event = {
        "dependencies": {}, "event_id": 1, "kind": "continue",
        "payload": None, "pc": entry, "priority": 0,
        "program_id": program_id, "ready_at": 0, "reason": None,
        "scope_id": scope_id, "sequence": 1, "site": 0,
        "source_id": program_id, "state": "ready", "target_id": program_id,
    }
    queue_ref, _queue_id = _allocate_raw(
        flat, profile, kind=KIND_QUEUE, codec=CODEC_JSON,
        value={
            "automaton_id": automaton_id, "dispatch_count": 0,
            "events": [root_event], "named_values": named_values,
            "next_event_id": 2, "schema": "cassifi.regional-queue.v1",
        },
        capacity=profile.queue_words, scope_id=scope_id,
        flags=FLAG_LIVE | FLAG_PROTECTED,
    )
    _write_descriptor_ref(flat, H_QUEUE, queue_ref)
    _write_descriptor_ref(flat, H_ACTIVE_CONTINUATION, program_ref)

    # Bootstrap allocations changed committed base contents once.
    _write_u64(flat, H_BASE_EPOCH, 1)
    return field


def _validate_directory(flat: np.ndarray, profile: RegionalProfile) -> None:
    arena_start = HEADER_WORDS + DIRECTORY_WORDS * profile.directory_capacity
    intervals: list[tuple[int, int, int]] = []
    live_slots: set[tuple[int, int]] = set()
    for index, row in enumerate(_directory(flat, profile)):
        generation = int(row[D_GENERATION])
        flags = int(row[D_FLAGS])
        if flags == 0:
            if any(int(row[column]) != 0 for column in range(1, DIRECTORY_WORDS)):
                raise RegionalFieldError("free directory row is noncanonical")
            continue
        if flags & ~(FLAG_LIVE | FLAG_IMMUTABLE | FLAG_QUARANTINED | FLAG_PROTECTED):
            raise RegionalFieldError("directory flags are invalid")
        if bool(flags & FLAG_LIVE) == bool(flags & FLAG_QUARANTINED):
            raise RegionalFieldError("directory row must be live or quarantined")
        if generation == 0:
            raise RegionalFieldError("occupied directory row has zero generation")
        if int(row[D_KIND]) not in KIND_NAMES or int(row[D_CODEC]) not in (CODEC_JSON, CODEC_WORDS):
            raise RegionalFieldError("directory kind or codec is invalid")
        base, used, capacity = (int(row[D_BASE]), int(row[D_USED]), int(row[D_CAPACITY]))
        if capacity <= 0 or used > capacity or base < arena_start or base + capacity > profile.total_words:
            raise RegionalFieldError("directory payload range is invalid")
        if int(row[D_RESERVED]) != 0:
            raise RegionalFieldError("directory reserved word is nonzero")
        metadata_ids = [
            int(row[column])
            for column in (
                D_READ_CAPS,
                D_WRITE_CAPS,
                D_PARENT_REF,
                D_TYPE_REF,
                D_DEPENDENCY_REF,
            )
        ]
        if any(metadata_ids) and not all(metadata_ids):
            raise RegionalFieldError(
                "descriptor metadata references are only partially populated"
            )
        for object_id in metadata_ids:
            _integer(
                object_id,
                "descriptor metadata object ID",
                maximum=profile.max_registry_entries,
            )
        intervals.append((base, base + capacity, index + 1))
        live_slots.add((index + 1, generation))
        if flags & FLAG_QUARANTINED:
            if used != 0:
                raise RegionalFieldError("quarantined region cannot expose used words")
        elif int(row[D_CODEC]) == CODEC_JSON:
            _decode_json_words([int(word) for word in _payload_words(flat, row)])
        else:
            for word in _payload_words(flat, row):
                _integer(int(word), "regional word")
    intervals.sort()
    for previous, current in zip(intervals, intervals[1:]):
        if previous[1] > current[0]:
            raise RegionalFieldError("regional payload ranges overlap")
    for offset in (H_ACTIVE_CONTINUATION, H_QUEUE, H_PROGRAM_CATALOG, H_LEFT_STACK,
                   H_RIGHT_STACK, H_LEDGER, H_REGISTRY, H_ROOT_SCOPE):
        ref = _descriptor_ref(flat, offset)
        if ref is not None and (ref.slot, ref.generation) not in live_slots:
            raise RegionalFieldError("distinguished reference is stale")


def _descriptor_metadata_record(
    flat: np.ndarray,
    profile: RegionalProfile,
    object_id: int,
    *,
    immutable: bool = True,
) -> tuple[np.ndarray, Mapping[str, Any]]:
    ref = _resolve_object(flat, profile, object_id)
    row = _row_for_ref(flat, profile, ref)
    if (
        int(row[D_KIND]) != KIND_VALUE
        or int(row[D_CODEC]) != CODEC_JSON
        or not int(row[D_FLAGS]) & FLAG_PROTECTED
        or (
            immutable
            and not int(row[D_FLAGS]) & FLAG_IMMUTABLE
        )
    ):
        raise RegionalFieldError(
            "descriptor metadata target has an invalid region kind"
        )
    value = _read_region(flat, profile, ref)
    if not isinstance(value, Mapping):
        raise RegionalFieldError(
            "descriptor metadata target is not a mapping"
        )
    return row, value


def _descriptor_metadata_for_row(
    flat: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    row: np.ndarray,
) -> dict[str, Any] | None:
    ids = {
        "read": int(row[D_READ_CAPS]),
        "write": int(row[D_WRITE_CAPS]),
        "parent": int(row[D_PARENT_REF]),
        "type": int(row[D_TYPE_REF]),
        "dependencies": int(row[D_DEPENDENCY_REF]),
    }
    if not any(ids.values()):
        return None
    if not all(ids.values()):
        raise RegionalFieldError(
            "descriptor metadata references are only partially populated"
        )
    parent_row = _row_for_ref(
        flat,
        profile,
        _resolve_object(flat, profile, ids["parent"]),
    )
    read_row, read_value = _descriptor_metadata_record(
        flat, profile, ids["read"]
    )
    write_row, write_value = _descriptor_metadata_record(
        flat, profile, ids["write"]
    )
    type_row, type_value = _descriptor_metadata_record(
        flat, profile, ids["type"]
    )
    dependency_row, dependency_value = _descriptor_metadata_record(
        flat, profile, ids["dependencies"], immutable=False
    )
    if (
        int(parent_row[D_KIND]) != KIND_SCOPE
        or ids["parent"] != int(row[D_SCOPE_ID])
        or any(
            int(metadata_row[D_SCOPE_ID]) != int(row[D_SCOPE_ID])
            for metadata_row in (
                read_row,
                write_row,
                type_row,
                dependency_row,
            )
        )
    ):
        raise RegionalFieldError(
            "descriptor metadata scope or parent is invalid"
        )
    capability_maps: dict[str, dict[str, list[str]]] = {}
    for mode, value in (("read", read_value), ("write", write_value)):
        raw_capabilities = value.get("capabilities")
        if (
            set(value) != {"capabilities", "mode", "schema"}
            or value.get("schema") != CAPABILITY_SET_SCHEMA
            or value.get("mode") != mode
            or not isinstance(raw_capabilities, Mapping)
        ):
            raise RegionalFieldError(
                "descriptor capability set is invalid"
            )
        capabilities: dict[str, list[str]] = {}
        for kernel_name, raw_names in raw_capabilities.items():
            _identifier(kernel_name, "descriptor capability kernel")
            if (
                not isinstance(raw_names, list)
                or not raw_names
                or any(
                    not isinstance(item, str) or not item
                    for item in raw_names
                )
                or raw_names != sorted(set(raw_names))
            ):
                raise RegionalFieldError(
                    "descriptor capability set is invalid"
                )
            capabilities[kernel_name] = list(raw_names)
        if list(capabilities) != sorted(capabilities):
            raise RegionalFieldError(
                "descriptor capability kernels are not canonical"
            )
        capability_maps[mode] = capabilities
    kernel_types_raw = type_value.get("kernel_types")
    if (
        set(type_value)
        != {
            "bootstrap_schema",
            "kernel_types",
            "name",
            "schema",
        }
        or type_value.get("schema") != TYPE_RECORD_SCHEMA
        or type_value.get("name") != "regional-native-state"
        or not isinstance(type_value.get("bootstrap_schema"), str)
        or not type_value["bootstrap_schema"]
        or not isinstance(kernel_types_raw, Mapping)
    ):
        raise RegionalFieldError("descriptor type record is invalid")
    if (
        set(capability_maps["read"])
        != set(capability_maps["write"])
        or set(capability_maps["read"]) != set(kernel_types_raw)
        or list(kernel_types_raw) != sorted(kernel_types_raw)
    ):
        raise RegionalFieldError(
            "descriptor kernel contracts disagree"
        )
    kernel_types: dict[str, dict[str, Any]] = {}
    accepted_schemas = {type_value["bootstrap_schema"]}
    for kernel_name, raw_type in kernel_types_raw.items():
        contract = (catalog.contracts or {}).get(kernel_name)
        if (
            contract is None
            or not isinstance(raw_type, Mapping)
            or set(raw_type) != {"accepted_schemas", "name"}
            or raw_type.get("accepted_schemas")
            != list(contract["state_schemas"])
            or raw_type.get("name") != contract["type_name"]
            or capability_maps["read"][kernel_name]
            != list(contract["read_capabilities"])
            or capability_maps["write"][kernel_name]
            != list(contract["write_capabilities"])
        ):
            raise RegionalFieldError(
                "descriptor metadata does not match its kernel contract"
            )
        accepted_schemas.update(raw_type["accepted_schemas"])
        kernel_types[kernel_name] = {
            "accepted_schemas": list(raw_type["accepted_schemas"]),
            "name": raw_type["name"],
        }
    if (
        set(dependency_value) != {"entries", "schema"}
        or dependency_value.get("schema") != DEPENDENCY_LIST_SCHEMA
        or not isinstance(dependency_value.get("entries"), list)
    ):
        raise RegionalFieldError(
            "descriptor dependency list is invalid"
        )
    dependency_entries: list[dict[str, int]] = []
    for raw in dependency_value["entries"]:
        if not isinstance(raw, Mapping) or set(raw) != {
            "object_id",
            "version",
        }:
            raise RegionalFieldError(
                "descriptor dependency entry is invalid"
            )
        object_id = _integer(
            raw["object_id"], "descriptor dependency object ID", minimum=1
        )
        version = _integer(
            raw["version"],
            "descriptor dependency version",
            minimum=1,
            maximum=U64_MAX,
        )
        _resolve_object(flat, profile, object_id)
        dependency_entries.append(
            {"object_id": object_id, "version": version}
        )
    dependency_ids = [
        item["object_id"] for item in dependency_entries
    ]
    if dependency_ids != sorted(set(dependency_ids)):
        raise RegionalFieldError(
            "descriptor dependencies are not canonical"
        )
    state_value = _decode_json_words(
        [int(word) for word in _payload_words(flat, row)]
    )
    if (
        not isinstance(state_value, Mapping)
        or state_value.get("schema") not in accepted_schemas
    ):
        raise RegionalFieldError(
            "descriptor state does not match its declared type"
        )
    return {
        "dependencies": dependency_entries,
        "kernel_types": kernel_types,
        "kernels": sorted(kernel_types),
        "parent": ids["parent"],
        "read_capabilities": capability_maps["read"],
        "state_schema": state_value["schema"],
        "write_capabilities": capability_maps["write"],
    }


def _validate_descriptor_metadata(
    flat: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
) -> None:
    expected: dict[int, dict[str, set[Any]]] = {}
    for program_index, program_row in enumerate(
        _directory(flat, profile)
    ):
        if (
            not int(program_row[D_FLAGS]) & FLAG_LIVE
            or int(program_row[D_KIND]) != KIND_PROGRAM
        ):
            continue
        program_value = _read_region(
            flat,
            profile,
            RegionRef(
                program_index + 1,
                int(program_row[D_GENERATION]),
                rights=RIGHT_READ,
            ),
        )
        if (
            not isinstance(program_value, Mapping)
            or program_value.get("schema")
            != "cassifi.regional-program.v1"
        ):
            raise RegionalFieldError("regional program record is invalid")
        for instruction in canonical_program(
            program_value.get("instructions")
        ):
            if instruction["op"] != "NATIVE":
                continue
            contract = (catalog.contracts or {}).get(
                instruction["kernel"]
            )
            if contract is None:
                continue
            state_object_id = _integer(
                instruction["state"],
                "native state object ID",
                minimum=1,
            )
            item = expected.setdefault(
                state_object_id,
                {"dependencies": set(), "kernels": set()},
            )
            item["kernels"].add(instruction["kernel"])
            arguments = instruction.get("arguments", {})
            if isinstance(arguments, int) and not isinstance(
                arguments, bool
            ):
                item["dependencies"].add(arguments)
    expected_slots: dict[tuple[int, int], int] = {}
    for state_object_id, item in expected.items():
        state_ref = _resolve_object(flat, profile, state_object_id)
        state_row = _row_for_ref(flat, profile, state_ref)
        metadata = _descriptor_metadata_for_row(
            flat, profile, catalog, state_row
        )
        metadata_dependency_ids = (
            set()
            if metadata is None
            else {
                int(entry["object_id"])
                for entry in metadata["dependencies"]
            }
        )
        if (
            metadata is None
            or set(metadata["kernels"]) != item["kernels"]
            or metadata_dependency_ids != item["dependencies"]
        ):
            raise RegionalFieldError(
                "descriptor metadata disagrees with native program"
            )
        expected_slots[(state_ref.slot, state_ref.generation)] = (
            state_object_id
        )
    for index, row in enumerate(_directory(flat, profile)):
        if not int(row[D_FLAGS]) & FLAG_LIVE:
            continue
        has_metadata = any(
            int(row[column])
            for column in (
                D_READ_CAPS,
                D_WRITE_CAPS,
                D_PARENT_REF,
                D_TYPE_REF,
                D_DEPENDENCY_REF,
            )
        )
        key = (index + 1, int(row[D_GENERATION]))
        if has_metadata and key not in expected_slots:
            raise RegionalFieldError(
                "descriptor metadata is not owned by a native state"
            )


def validate_field(field: np.ndarray, profile: RegionalProfile, catalog: KernelCatalog) -> None:
    if not isinstance(field, np.ndarray) or field.dtype != np.float64 or field.shape != profile.shape or not field.flags.c_contiguous:
        raise RegionalFieldError("regional field shape or dtype is invalid")
    if not np.isfinite(field).all() or not np.equal(field, np.floor(field)).all():
        raise RegionalFieldError("regional field contains noncanonical words")
    if np.any(field < 0) or np.any(field > U32_MAX):
        raise RegionalFieldError("regional field word is outside u32")
    flat = field.reshape(-1)
    if int(flat[H_MAGIC]) != REGIONAL_MAGIC or int(flat[H_LAYOUT_REVISION]) != REGIONAL_LAYOUT_REVISION:
        raise RegionalFieldError("regional header identity is invalid")
    if int(flat[H_TOTAL_WORDS]) != profile.total_words or int(flat[H_DIRECTORY_CAPACITY]) != profile.directory_capacity:
        raise RegionalFieldError("regional header geometry is invalid")
    if _words_sha([int(word) for word in flat[H_PROFILE_SHA:H_PROFILE_SHA + 8]]) != profile.fingerprint:
        raise RegionalFieldError("regional profile digest is invalid")
    if (
        _words_sha(
            [int(word) for word in flat[H_CATALOG_SHA:H_CATALOG_SHA + 8]]
        )
        != catalog.fingerprint
    ):
        raise RegionalFieldError("regional catalog digest is invalid")
    if catalog.names != profile.kernel_names:
        raise RegionalFieldError("runtime kernel catalog does not match profile")
    if int(flat[H_STATUS]) not in STATUS_NAMES or int(flat[H_REASON]) not in REASON_NAMES:
        raise RegionalFieldError("regional status or reason is invalid")
    if any(int(word) != 0 for word in flat[46:HEADER_WORDS]):
        raise RegionalFieldError("regional header padding is nonzero")
    clock = _read_u64(flat, H_CLOCK)
    if clock > profile.max_steps and int(flat[H_STATUS]) not in (STATUS_EXHAUSTED, STATUS_COUNTER_EXHAUSTED):
        raise RegionalFieldError("regional transition budget is exceeded")
    _validate_directory(flat, profile)
    registry_ref, registry = _registry(flat, profile)
    if registry.get("schema") != "cassifi.regional-reference-registry.v1":
        raise RegionalFieldError("reference registry schema is invalid")
    entries = registry.get("entries")
    if not isinstance(entries, dict):
        raise RegionalFieldError("reference registry entries are invalid")
    next_id = _integer(registry.get("next_id"), "next registry ID", minimum=1)
    if next_id > profile.max_registry_entries + 1:
        raise RegionalFieldError("reference registry next ID is invalid")
    seen_targets: set[tuple[int, int]] = set()
    for text_id, entry in entries.items():
        try:
            object_id = int(text_id)
        except (TypeError, ValueError) as exc:
            raise RegionalFieldError("reference registry ID is invalid") from exc
        if str(object_id) != text_id or not 1 <= object_id < next_id or not isinstance(entry, dict):
            raise RegionalFieldError("reference registry entry is invalid")
        if entry.get("status") == "live":
            reference = entry.get("reference")
            if not isinstance(reference, Mapping):
                raise RegionalFieldError("live registry reference is invalid")
            ref = RegionRef.from_dict(reference)
            row = _row_for_ref(flat, profile, ref)
            if (ref.slot, ref.generation) in seen_targets:
                raise RegionalFieldError("registry aliases a live region identity")
            if entry.get("kind") != KIND_NAMES[int(row[D_KIND])]:
                raise RegionalFieldError("registry kind disagrees with directory")
            seen_targets.add((ref.slot, ref.generation))
        elif entry.get("status") != "tombstone":
            raise RegionalFieldError("registry status is invalid")
    if (registry_ref.slot, registry_ref.generation) not in seen_targets:
        raise RegionalFieldError("registry does not contain its own identity")
    _validate_descriptor_metadata(flat, profile, catalog)
    queue_ref = _descriptor_ref(flat, H_QUEUE)
    if queue_ref is None:
        raise RegionalFieldError("regional queue is missing")
    queue = _read_region(flat, profile, queue_ref)
    _validate_queue(flat, profile, queue)


def _validate_queue(flat: np.ndarray, profile: RegionalProfile, queue: Any) -> None:
    if not isinstance(queue, dict) or queue.get("schema") != "cassifi.regional-queue.v1":
        raise RegionalFieldError("regional queue is invalid")
    events = queue.get("events")
    if not isinstance(events, list) or len(events) > profile.max_events:
        raise RegionalFieldError("regional event queue exceeds its bound")
    event_ids: set[int] = set()
    sequences: set[int] = set()
    for event in events:
        if not isinstance(event, dict):
            raise RegionalFieldError("regional event is invalid")
        required = {
            "dependencies", "event_id", "kind", "payload", "pc", "priority",
            "program_id", "ready_at", "reason", "scope_id", "sequence", "site",
            "source_id", "state", "target_id",
        }
        if set(event) != required:
            raise RegionalFieldError("regional event keys are noncanonical")
        event_id = _integer(event["event_id"], "event ID", minimum=1)
        sequence = _integer(event["sequence"], "event sequence", minimum=1, maximum=U64_MAX - 1)
        if event_id in event_ids or sequence in sequences:
            raise RegionalFieldError("regional event identity is duplicated")
        event_ids.add(event_id)
        sequences.add(sequence)
        if event["state"] not in {"ready", "waiting", "active", "blocked", "faulted"}:
            raise RegionalFieldError("regional event state is invalid")
        _integer(event["site"], "event site", maximum=profile.automaton_sites - 1)
        _integer(event["pc"], "event pc")
        _integer(event["priority"], "event priority", maximum=profile.automaton_scale)
        _integer(event["ready_at"], "event ready_at", maximum=U64_MAX - 1)
        _integer(event["program_id"], "event program ID", minimum=1)
        _integer(event["scope_id"], "event scope ID", minimum=1)
        if not isinstance(event["dependencies"], dict):
            raise RegionalFieldError("event dependencies are invalid")
        _resolve_object(flat, profile, event["program_id"], right=RIGHT_EXECUTE)
        _resolve_object(flat, profile, event["scope_id"], right=RIGHT_READ)
    _integer(queue.get("dispatch_count"), "dispatch count", maximum=U64_MAX - 1)
    _integer(queue.get("next_event_id"), "next event ID", minimum=1)
    if not isinstance(queue.get("named_values"), dict):
        raise RegionalFieldError("named value bindings are invalid")


def state_sha256(field: np.ndarray, profile: RegionalProfile) -> str:
    digest = hashlib.sha256(_canonical({
        "layout": REGIONAL_LAYOUT,
        "profile_sha256": profile.fingerprint,
        "shape": profile.shape,
    }))
    digest.update(field.tobytes(order="C"))
    return digest.hexdigest()


def _program_for(flat: np.ndarray, profile: RegionalProfile, object_id: int) -> list[dict[str, Any]]:
    ref = _resolve_object(flat, profile, object_id, right=RIGHT_EXECUTE)
    row = _row_for_ref(flat, profile, ref)
    if int(row[D_KIND]) != KIND_PROGRAM:
        raise RegionalFieldError("event program identity has the wrong kind")
    value = _read_region(flat, profile, ref)
    if not isinstance(value, dict) or value.get("schema") != "cassifi.regional-program.v1":
        raise RegionalFieldError("regional program record is invalid")
    return canonical_program(value.get("instructions"))


def _scope_live(flat: np.ndarray, profile: RegionalProfile, scope_id: int) -> bool:
    depth = 0
    current = scope_id
    seen: set[int] = set()
    while current:
        if current in seen or depth > profile.max_scope_depth:
            raise RegionalFieldError("scope ancestry is cyclic or too deep")
        seen.add(current)
        ref = _resolve_object(flat, profile, current)
        row = _row_for_ref(flat, profile, ref)
        if int(row[D_KIND]) != KIND_SCOPE:
            raise RegionalFieldError("scope identity has the wrong kind")
        value = _read_region(flat, profile, ref)
        if not isinstance(value, dict) or not isinstance(value.get("live"), bool):
            raise RegionalFieldError("scope record is invalid")
        if not value["live"]:
            return False
        current = _integer(value.get("parent_scope_id"), "parent scope ID")
        depth += 1
    return True


def _refresh_descriptor_dependencies(
    flat: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
) -> None:
    for row in _directory(flat, profile):
        if not int(row[D_FLAGS]) & FLAG_LIVE:
            continue
        metadata = _descriptor_metadata_for_row(
            flat, profile, catalog, row
        )
        if metadata is None:
            continue
        entries: list[dict[str, int]] = []
        for item in metadata["dependencies"]:
            object_id = int(item["object_id"])
            dependency_ref = _resolve_object(
                flat, profile, object_id
            )
            dependency_row = _row_for_ref(
                flat, profile, dependency_ref
            )
            entries.append(
                {
                    "object_id": object_id,
                    "version": _read_u64(
                        dependency_row, D_VERSION
                    ),
                }
            )
        dependency_ref = _resolve_object(
            flat,
            profile,
            int(row[D_DEPENDENCY_REF]),
            right=RIGHT_WRITE,
        )
        _write_region(
            flat,
            profile,
            dependency_ref,
            {
                "entries": entries,
                "schema": DEPENDENCY_LIST_SCHEMA,
            },
        )


def _native_contract_status(
    flat: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    event: Mapping[str, Any],
    instruction: Mapping[str, Any],
) -> str | None:
    contract = (catalog.contracts or {}).get(instruction["kernel"])
    state_ref = _resolve_object(
        flat, profile, instruction["state"], right=RIGHT_WRITE
    )
    state_row = _row_for_ref(
        flat, profile, state_ref, right=RIGHT_WRITE
    )
    metadata = _descriptor_metadata_for_row(
        flat, profile, catalog, state_row
    )
    if contract is None:
        return None
    kernel_type = (
        None
        if metadata is None
        else metadata["kernel_types"].get(instruction["kernel"])
    )
    if (
        metadata is None
        or kernel_type is None
        or metadata["parent"] != int(event["scope_id"])
        or metadata["state_schema"]
        not in kernel_type["accepted_schemas"]
    ):
        return "permission-denied"
    arguments = instruction.get("arguments", {})
    argument_id = (
        arguments
        if isinstance(arguments, int) and not isinstance(arguments, bool)
        else None
    )
    dependencies = {
        int(item["object_id"]): int(item["version"])
        for item in metadata["dependencies"]
    }
    if argument_id is not None and argument_id not in dependencies:
        return "permission-denied"
    for object_id, expected_version in dependencies.items():
        dependency_ref = _resolve_object(flat, profile, object_id)
        dependency_row = _row_for_ref(flat, profile, dependency_ref)
        if _read_u64(dependency_row, D_VERSION) != expected_version:
            return "stale"
    return None


def _eligibility(flat: np.ndarray, profile: RegionalProfile, event: Mapping[str, Any], catalog: KernelCatalog) -> tuple[bool, str | None, dict[str, Any] | None]:
    if event["state"] not in {"ready", "waiting"}:
        return False, event.get("reason") or event["state"], None
    if event["state"] == "waiting" and event.get("reason") == "kernel-blocked":
        return False, "kernel-blocked", None
    try:
        if not _scope_live(flat, profile, int(event["scope_id"])):
            return False, "scope-closed", None
        program = _program_for(flat, profile, int(event["program_id"]))
        pc = int(event["pc"])
        if not 0 <= pc < len(program):
            return False, "fault", None
        instruction = program[pc]
        for text_id, expected in event["dependencies"].items():
            object_id = int(text_id)
            ref = _resolve_object(flat, profile, object_id)
            row = _row_for_ref(flat, profile, ref)
            if _read_u64(row, D_VERSION) != int(expected):
                return False, "stale", instruction
        op = instruction["op"]
        if op == "AWAIT":
            target = _read_region(
                flat,
                profile,
                _resolve_object(flat, profile, instruction["target"]),
            )
            if (
                not isinstance(target, Mapping)
                or target.get("status") not in {"done", "halted"}
            ):
                return False, "await", instruction
        if op == "NATIVE":
            if instruction["kernel"] not in catalog.kernels:
                return False, "fault", instruction
            contract_status = _native_contract_status(
                flat, profile, catalog, event, instruction
            )
            if contract_status is not None:
                return False, contract_status, instruction
            _resolve_object(flat, profile, instruction["state"], right=RIGHT_WRITE)
            arguments = instruction.get("arguments", {})
            if not isinstance(arguments, Mapping):
                _resolve_object(flat, profile, arguments)
        for key in ("source", "target", "output"):
            if key in instruction:
                right = RIGHT_READ if key == "source" else RIGHT_WRITE
                _resolve_object(flat, profile, instruction[key], right=right)
        return True, None, instruction
    except (RegionalFieldError, ValueError, TypeError):
        return False, "fault", None


def _event_sort_key(event: Mapping[str, Any]) -> tuple[int, int, int, int, int]:
    return (
        -int(event["priority"]), int(event["ready_at"]),
        int(event["source_id"]), int(event["target_id"]), int(event["sequence"]),
    )


def _advance_automaton(
    flat: np.ndarray,
    profile: RegionalProfile,
    queue: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    eligible: Sequence[bool],
) -> tuple[int | None, Mapping[str, Any]]:
    automaton_id = _integer(queue.get("automaton_id"), "automaton object ID", minimum=1)
    ref = _resolve_object(flat, profile, automaton_id, right=RIGHT_WRITE)
    words = _read_region(flat, profile, ref)
    lanes = np.asarray(words, dtype=np.float64)
    controller = ExcitableConstraintController(ExcitableConstraintProfile(
        size=profile.automaton_sites, scale=profile.automaton_scale,
        max_ticks=profile.automaton_max_ticks,
    ))
    positive = [int(event["priority"]) + 1 for event in candidates]
    negative = [0 for _event in candidates]
    selected, receipt = controller.advance_lanes(
        lanes, positive=positive, negative=negative, eligible=eligible,
    )
    _write_region(flat, profile, ref, [int(value) for value in lanes])
    return (None if selected is None else selected - 1), receipt


def _queue_ref(flat: np.ndarray) -> RegionRef:
    ref = _descriptor_ref(flat, H_QUEUE)
    if ref is None:
        raise RegionalFieldError("regional queue is missing")
    return RegionRef(ref.slot, ref.generation, rights=RIGHT_ALL)


def _ledger_ref(flat: np.ndarray) -> RegionRef:
    ref = _descriptor_ref(flat, H_LEDGER)
    if ref is None:
        raise RegionalFieldError("regional ledger is missing")
    return RegionRef(ref.slot, ref.generation, rights=RIGHT_ALL)


def _next_pc(instruction: Mapping[str, Any], pc: int) -> int:
    return int(instruction.get("next", pc + 1))


def _event_from_spec(
    flat: np.ndarray,
    profile: RegionalProfile,
    queue: dict[str, Any],
    parent: Mapping[str, Any],
    spec: Mapping[str, Any],
    *,
    clock: int,
) -> dict[str, Any]:
    allowed = {"dependencies", "kind", "payload", "pc", "priority", "program_id", "scope_id", "site", "target_id"}
    if not isinstance(spec, Mapping) or set(spec) - allowed:
        raise RegionalFieldError("emitted event specification is invalid")
    event_id = _integer(queue["next_event_id"], "next event ID", minimum=1)
    sequence = _read_u64(flat, H_NEXT_SEQUENCE)
    if sequence >= U64_MAX:
        raise RegionalFieldError("event sequence is exhausted")
    if len(queue["events"]) >= profile.max_events:
        raise RegionalFieldError("event queue is exhausted")
    program_id = _integer(spec.get("program_id", parent["program_id"]), "event program ID", minimum=1)
    scope_id = _integer(spec.get("scope_id", parent["scope_id"]), "event scope ID", minimum=1)
    _resolve_object(flat, profile, program_id, right=RIGHT_EXECUTE)
    _resolve_object(flat, profile, scope_id, right=RIGHT_READ)
    event = {
        "dependencies": dict(spec.get("dependencies", {})),
        "event_id": event_id,
        "kind": str(spec.get("kind", "continue")),
        "payload": spec.get("payload"),
        "pc": _integer(spec.get("pc", 0), "event pc"),
        "priority": _integer(spec.get("priority", 0), "event priority", maximum=profile.automaton_scale),
        "program_id": program_id,
        "ready_at": clock,
        "reason": None,
        "scope_id": scope_id,
        "sequence": sequence,
        "site": _integer(spec.get("site", parent["site"]), "event site", maximum=profile.automaton_sites - 1),
        "source_id": int(parent["target_id"]),
        "state": "ready",
        "target_id": _integer(spec.get("target_id", program_id), "event target ID", minimum=1),
    }
    queue["next_event_id"] = event_id + 1
    _write_u64(flat, H_NEXT_SEQUENCE, sequence + 1)
    return event


def _execute_instruction(
    flat: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    queue: dict[str, Any],
    event: dict[str, Any],
    instruction: Mapping[str, Any],
    *,
    clock: int,
) -> tuple[str, Any, int, list[dict[str, Any]]]:
    op = instruction["op"]
    output: Any = None
    work = 1
    emitted: list[dict[str, Any]] = []
    if op == "HALT":
        return "done", None, work, emitted
    if op in {"READ", "COPY"}:
        value = _read_region(flat, profile, _resolve_object(flat, profile, instruction["source"]))
        _write_region(flat, profile, _resolve_object(flat, profile, instruction["target"], right=RIGHT_WRITE), value)
        output = value
    elif op in {"WRITE", "WRITE_EMIT"}:
        value = instruction.get("value")
        if "source" in instruction:
            value = _read_region(flat, profile, _resolve_object(flat, profile, instruction["source"]))
        if op == "WRITE_EMIT":
            emitted.append(_event_from_spec(flat, profile, queue, event, instruction["event"], clock=clock))
        _write_region(flat, profile, _resolve_object(flat, profile, instruction["target"], right=RIGHT_WRITE), value)
        output = value
    elif op == "ALLOC":
        ref, object_id = _allocate_raw(
            flat, profile, kind=_integer(instruction["kind"], "allocation kind", minimum=1),
            codec=_integer(instruction["codec"], "allocation codec", minimum=1),
            value=instruction["value"], capacity=_integer(instruction["capacity"], "allocation capacity", minimum=1),
            scope_id=int(event["scope_id"]),
        )
        output = {"object_id": object_id, "reference": ref.as_dict()}
        if "target" in instruction:
            _write_region(flat, profile, _resolve_object(flat, profile, instruction["target"], right=RIGHT_WRITE), output)
    elif op == "RELEASE":
        target_id = int(instruction["target"])
        ref = _resolve_object(flat, profile, target_id, right=RIGHT_MANAGE)
        row = _row_for_ref(flat, profile, ref, right=RIGHT_MANAGE)
        if int(row[D_FLAGS]) & FLAG_PROTECTED:
            raise RegionalFieldError("protected region cannot be released")
        base, capacity = int(row[D_BASE]), int(row[D_CAPACITY])
        if capacity > profile.reclaim_quantum:
            raise RegionalFieldError("release requires a bounded reclamation continuation")
        flat[base:base + capacity] = 0
        row[D_USED] = 0
        row[D_FLAGS] = 0
        registry_ref, registry = _registry(flat, profile)
        entries = dict(registry["entries"])
        entries[str(target_id)] = {"status": "tombstone"}
        _write_region(flat, profile, RegionRef(registry_ref.slot, registry_ref.generation, rights=RIGHT_ALL), {**registry, "entries": entries})
    elif op == "EMIT":
        emitted.append(_event_from_spec(flat, profile, queue, event, instruction["event"], clock=clock))
    elif op == "YIELD":
        event["pc"] = _next_pc(instruction, int(event["pc"]))
        return "yield", None, work, emitted
    elif op == "AWAIT":
        target = _read_region(flat, profile, _resolve_object(flat, profile, instruction["target"]))
        if not isinstance(target, Mapping) or target.get("status") not in {"done", "halted"}:
            return "blocked", None, work, emitted
        output = target
    elif op == "NATIVE":
        kernel_name = instruction["kernel"]
        kernel = catalog.kernels[kernel_name]
        state_ref = _resolve_object(flat, profile, instruction["state"], right=RIGHT_WRITE)
        state = _read_region(flat, profile, state_ref)
        raw_arguments = instruction.get("arguments", {})
        if isinstance(raw_arguments, Mapping):
            arguments = dict(raw_arguments)
        elif isinstance(raw_arguments, int) and not isinstance(
            raw_arguments, bool
        ):
            arguments_ref = _resolve_object(flat, profile, raw_arguments)
            stored_arguments = _read_region(flat, profile, arguments_ref)
            if not isinstance(stored_arguments, Mapping):
                raise RegionalFieldError("native argument region must contain a mapping")
            arguments = dict(stored_arguments)
        else:
            raise RegionalFieldError(
                "native arguments must be a mapping or object reference"
            )
        bound = min(profile.max_native_work, int(catalog.max_work[kernel_name]))
        result = kernel(state, arguments, bound)
        if not isinstance(result, KernelResult) or result.work > bound:
            raise RegionalFieldError("native kernel exceeded its declared quantum")
        _write_region(flat, profile, state_ref, result.state)
        output = result.output
        work = result.work
        if "output" in instruction:
            _write_region(
                flat,
                profile,
                _resolve_object(
                    flat, profile, instruction["output"], right=RIGHT_WRITE
                ),
                result.output,
            )
        for spec in result.events:
            emitted.append(
                _event_from_spec(
                    flat, profile, queue, event, spec, clock=clock
                )
            )
        if result.status in {"yield", "blocked", "fault"}:
            return result.status, output, work, emitted
    elif op == "BEGIN":
        parent_scope_id = int(event["scope_id"])
        parent_ref = _resolve_object(flat, profile, parent_scope_id)
        parent = _read_region(flat, profile, parent_ref)
        depth = _integer(parent.get("depth"), "scope depth") + 1
        if depth > profile.max_scope_depth:
            raise RegionalFieldError("scope depth is exhausted")
        _ref, scope_id = _allocate_raw(
            flat, profile, kind=KIND_SCOPE, codec=CODEC_JSON,
            value={"assumptions": [], "bindings": {}, "depth": depth, "live": True,
                   "parent_scope_id": parent_scope_id, "schema": "cassifi.regional-scope.v1"},
            capacity=profile.default_value_words, scope_id=parent_scope_id,
        )
        event["scope_id"] = scope_id
        output = {"scope_id": scope_id}
    elif op in {"COMMIT", "ROLLBACK"}:
        scope_id = int(event["scope_id"])
        scope_ref = _resolve_object(flat, profile, scope_id, right=RIGHT_WRITE)
        scope = _read_region(flat, profile, scope_ref)
        parent_scope_id = _integer(scope.get("parent_scope_id"), "parent scope ID")
        if parent_scope_id == 0:
            raise RegionalFieldError("root scope cannot be committed or rolled back")
        if op == "COMMIT" and (scope.get("assumptions") or scope.get("bindings")):
            parent_ref = _resolve_object(flat, profile, parent_scope_id, right=RIGHT_WRITE)
            parent = _read_region(flat, profile, parent_ref)
            merged = dict(parent)
            merged["assumptions"] = list(parent.get("assumptions", [])) + list(scope.get("assumptions", []))
            merged["bindings"] = {**dict(parent.get("bindings", {})), **dict(scope.get("bindings", {}))}
            _write_region(flat, profile, parent_ref, merged)
        closed = {**scope, "live": False, "closed_as": op.lower()}
        _write_region(flat, profile, scope_ref, closed)
        event["scope_id"] = parent_scope_id
    elif op == "CALL":
        payload = dict(event.get("payload") or {})
        stack = list(payload.get("return_stack", []))
        if len(stack) >= profile.max_scope_depth:
            raise RegionalFieldError("call depth is exhausted")
        stack.append(_next_pc(instruction, int(event["pc"])))
        event["payload"] = {**payload, "return_stack": stack}
        event["pc"] = int(instruction["target_pc"])
        return "continue", output, work, emitted
    elif op == "RETURN":
        payload = dict(event.get("payload") or {})
        stack = list(payload.get("return_stack", []))
        if not stack:
            raise RegionalFieldError("RETURN has no call frame")
        event["pc"] = _integer(stack.pop(), "return pc")
        event["payload"] = {**payload, "return_stack": stack}
        return "continue", output, work, emitted
    else:
        raise RegionalFieldError("regional operation is not implemented")
    event["pc"] = _next_pc(instruction, int(event["pc"]))
    return "continue", output, work, emitted


def step_field(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog = EMPTY_KERNEL_CATALOG,
    *,
    _input_validated: bool = False,
    _validate_output: bool = True,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Execute one automaton-selected, bounded regional transition."""

    if not _input_validated:
        validate_field(field, profile, catalog)
    before_sha = state_sha256(field, profile)
    flat_before = field.reshape(-1)
    status = int(flat_before[H_STATUS])
    if status not in (STATUS_RUNNING, STATUS_WAITING):
        return field, {
            "schema": REGIONAL_SCHEMA, "kind": "noop", "status": STATUS_NAMES[status],
            "reason": REASON_NAMES[int(flat_before[H_REASON])], "state_unchanged": True,
            "previous_state_sha256": before_sha, "state_sha256": before_sha,
        }
    clock = _read_u64(flat_before, H_CLOCK)
    if clock >= U64_MAX - 1:
        mutable = np.array(field, copy=True, order="C").reshape(-1)
        _write_u64(mutable, H_CLOCK, U64_MAX)
        mutable[H_STATUS] = STATUS_COUNTER_EXHAUSTED
        mutable[H_REASON] = REASON_COUNTER_EXHAUSTED
        successor = mutable.reshape(profile.shape)
        if _validate_output:
            validate_field(successor, profile, catalog)
        return successor, {
            "schema": REGIONAL_SCHEMA, "kind": "counter-exhausted",
            "status": "counter-exhausted", "reason": "counter-exhausted",
            "previous_state_sha256": before_sha,
            "state_sha256": state_sha256(successor, profile),
            "logical_transition": U64_MAX,
        }
    if clock >= profile.max_steps:
        mutable = np.array(field, copy=True, order="C").reshape(-1)
        mutable[H_STATUS] = STATUS_EXHAUSTED
        mutable[H_REASON] = REASON_STEP_BUDGET
        successor = mutable.reshape(profile.shape)
        if _validate_output:
            validate_field(successor, profile, catalog)
        return successor, {
            "schema": REGIONAL_SCHEMA, "kind": "exhausted", "status": "exhausted",
            "reason": "max_steps", "previous_state_sha256": before_sha,
            "state_sha256": state_sha256(successor, profile), "logical_transition": clock,
        }

    mutable_field = np.array(field, copy=True, order="C")
    flat = mutable_field.reshape(-1)
    queue_ref = _queue_ref(flat)
    queue = _read_region(flat, profile, queue_ref)
    events = [dict(event) for event in queue["events"]]
    candidates = sorted(events, key=_event_sort_key)
    eligibility_rows = [_eligibility(flat, profile, event, catalog) for event in candidates]
    eligible = [row[0] for row in eligibility_rows]
    automaton_index, automaton_receipt = _advance_automaton(flat, profile, queue, candidates, eligible)
    ready_indices = [index for index, flag in enumerate(eligible) if flag]
    if not ready_indices:
        for event, row in zip(candidates, eligibility_rows):
            event["state"] = "faulted" if row[1] == "fault" else "waiting"
            event["reason"] = row[1]
        queue["events"] = sorted(candidates, key=lambda event: int(event["sequence"]))
        _write_region(flat, profile, queue_ref, queue)
        _write_u64(flat, H_CLOCK, clock + 1)
        flat[H_STATUS] = STATUS_FAULTED if any(row[1] == "fault" for row in eligibility_rows) else STATUS_WAITING
        flat[H_REASON] = REASON_INVALID_INSTRUCTION if int(flat[H_STATUS]) == STATUS_FAULTED else REASON_NO_READY_EVENT
        successor = mutable_field
        if _validate_output:
            validate_field(successor, profile, catalog)
        return successor, {
            "schema": REGIONAL_SCHEMA, "kind": "no-ready-event",
            "status": STATUS_NAMES[int(flat[H_STATUS])], "reason": REASON_NAMES[int(flat[H_REASON])],
            "blocked_reasons": [row[1] for row in eligibility_rows],
            "previous_state_sha256": before_sha,
            "state_sha256": state_sha256(successor, profile), "logical_transition": clock + 1,
            "automaton": dict(automaton_receipt),
        }

    dispatch_count = int(queue["dispatch_count"]) + 1
    if dispatch_count % profile.fairness_interval == 0:
        selected_index = min(ready_indices, key=lambda index: (
            int(candidates[index]["ready_at"]), int(candidates[index]["sequence"])
        ))
    else:
        selected_index = automaton_index if automaton_index in ready_indices else ready_indices[0]
    selected = candidates[selected_index]
    instruction = eligibility_rows[selected_index][2]
    if instruction is None:
        raise RegionalFieldError("eligible event has no instruction")
    selected["state"] = "active"
    selected["reason"] = None
    output: Any = None
    work = 0
    emitted: list[dict[str, Any]] = []
    fault_detail: str | None = None
    trial_field = np.array(mutable_field, copy=True, order="C")
    trial_flat = trial_field.reshape(-1)
    trial_queue = copy.deepcopy(queue)
    trial_selected = copy.deepcopy(selected)
    try:
        disposition, output, work, emitted = _execute_instruction(
            trial_flat,
            profile,
            catalog,
            trial_queue,
            trial_selected,
            instruction,
            clock=clock + 1,
        )
        mutable_field = trial_field
        flat = trial_flat
        queue = trial_queue
        selected = trial_selected
    except RegionalFieldError as exc:
        fault_detail = str(exc)
        disposition = "fault"

    survivors = [event for event in candidates if int(event["event_id"]) != int(selected["event_id"])]
    if disposition in {"continue", "yield"}:
        sequence = _read_u64(flat, H_NEXT_SEQUENCE)
        if sequence >= U64_MAX:
            raise RegionalFieldError("event sequence is exhausted")
        selected["state"] = "ready"
        selected["reason"] = None
        selected["ready_at"] = clock + 1
        selected["sequence"] = sequence
        _write_u64(flat, H_NEXT_SEQUENCE, sequence + 1)
        survivors.append(selected)
    elif disposition == "blocked":
        selected["state"] = "waiting"
        selected["reason"] = "kernel-blocked"
        survivors.append(selected)
    elif disposition == "fault":
        selected["state"] = "faulted"
        selected["reason"] = "kernel-fault"
        survivors.append(selected)
    survivors.extend(emitted)
    if len(survivors) > profile.max_events:
        raise RegionalFieldError("event queue is exhausted")
    queue["events"] = sorted(survivors, key=lambda event: int(event["sequence"]))
    queue["dispatch_count"] = dispatch_count
    _write_region(flat, profile, queue_ref, queue)

    ledger_ref = _ledger_ref(flat)
    ledger = dict(_read_region(flat, profile, ledger_ref))
    ledger["dispatches"] = int(ledger["dispatches"]) + 1
    ledger["logical_transitions"] = int(ledger["logical_transitions"]) + 1
    ledger["native_work"] = int(ledger["native_work"]) + int(work)
    ledger["scheduler_work"] = int(ledger["scheduler_work"]) + len(candidates)
    ledger["automaton_local_ops"] = int(ledger["automaton_local_ops"]) + int(automaton_receipt["work"]["local_ops"])
    _write_region(flat, profile, ledger_ref, ledger)

    _write_u64(flat, H_CLOCK, clock + 1)
    _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
    flat[H_STATUS] = STATUS_FAULTED if disposition == "fault" else (STATUS_HALTED if not survivors else STATUS_RUNNING)
    flat[H_REASON] = REASON_KERNEL_FAULT if disposition == "fault" else (REASON_HALT if not survivors else REASON_NONE)
    successor = mutable_field
    if _validate_output:
        validate_field(successor, profile, catalog)
    eligibility_digest = hashlib.sha256(_canonical([
        {"event_id": int(event["event_id"]), "eligible": bool(row[0]), "reason": row[1]}
        for event, row in zip(candidates, eligibility_rows)
    ])).hexdigest()
    return successor, {
        "schema": REGIONAL_SCHEMA,
        "kind": "regional-transition",
        "status": STATUS_NAMES[int(flat[H_STATUS])],
        "reason": REASON_NAMES[int(flat[H_REASON])],
        "event_id": int(selected["event_id"]),
        "program_id": int(selected["program_id"]),
        "pc": int(selected["pc"]),
        "operation": instruction["op"],
        "disposition": disposition,
        "fault_detail": fault_detail,
        "output": output,
        "work": {"native": int(work), "scheduler": len(candidates), **dict(automaton_receipt["work"])},
        "eligibility_sha256": eligibility_digest,
        "automaton": dict(automaton_receipt),
        "previous_state_sha256": before_sha,
        "state_sha256": state_sha256(successor, profile),
        "logical_transition": clock + 1,
    }


def run_field(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog = EMPTY_KERNEL_CATALOG,
    *,
    steps: int | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    validate_field(field, profile, catalog)
    if steps is not None:
        steps = _integer(steps, "steps")
    initial_sha = state_sha256(field, profile)
    current = field
    receipts: list[dict[str, Any]] = []
    while int(current.reshape(-1)[H_STATUS]) in (STATUS_RUNNING, STATUS_WAITING):
        if steps is not None and len(receipts) >= steps:
            break
        successor, receipt = step_field(
            current,
            profile,
            catalog,
            _input_validated=True,
            _validate_output=False,
        )
        receipts.append(receipt)
        if successor is current or receipt["kind"] in {"no-ready-event", "exhausted", "counter-exhausted"}:
            current = successor
            break
        current = successor
    validate_field(current, profile, catalog)
    return current, {
        "schema": REGIONAL_SCHEMA,
        "initial_state_sha256": initial_sha,
        "state_sha256": state_sha256(current, profile),
        "status": STATUS_NAMES[int(current.reshape(-1)[H_STATUS])],
        "reason": REASON_NAMES[int(current.reshape(-1)[H_REASON])],
        "paused": steps is not None and len(receipts) >= steps and int(current.reshape(-1)[H_STATUS]) == STATUS_RUNNING,
        "transitions_executed": len(receipts),
        "transition_receipts": receipts,
    }


def inspect_field(field: np.ndarray, profile: RegionalProfile, catalog: KernelCatalog) -> dict[str, Any]:
    validate_field(field, profile, catalog)
    flat = field.reshape(-1)
    queue = _read_region(flat, profile, _queue_ref(flat))
    ledger = _read_region(flat, profile, _ledger_ref(flat))
    regions = []
    for index, row in enumerate(_directory(flat, profile)):
        flags = int(row[D_FLAGS])
        if flags & (FLAG_LIVE | FLAG_QUARANTINED):
            item: dict[str, Any] = {
                "slot": index + 1,
                "generation": int(row[D_GENERATION]),
                "kind": KIND_NAMES[int(row[D_KIND])],
                "flags": flags,
                "used_words": int(row[D_USED]),
                "capacity_words": int(row[D_CAPACITY]),
                "scope_id": int(row[D_SCOPE_ID]),
                "version": _read_u64(row, D_VERSION),
            }
            metadata = (
                _descriptor_metadata_for_row(
                    flat, profile, catalog, row
                )
                if flags & FLAG_LIVE
                else None
            )
            if metadata is not None:
                item["descriptor_metadata"] = {
                    **metadata,
                    "references": {
                        "dependencies": int(row[D_DEPENDENCY_REF]),
                        "parent": int(row[D_PARENT_REF]),
                        "read_capabilities": int(row[D_READ_CAPS]),
                        "type": int(row[D_TYPE_REF]),
                        "write_capabilities": int(row[D_WRITE_CAPS]),
                    },
                }
            regions.append(item)
    return {
        "schema": REGIONAL_SCHEMA,
        "layout": REGIONAL_LAYOUT,
        "profile_sha256": profile.fingerprint,
        "catalog_sha256": catalog.fingerprint,
        "state_sha256": state_sha256(field, profile),
        "status": STATUS_NAMES[int(flat[H_STATUS])],
        "reason": REASON_NAMES[int(flat[H_REASON])],
        "logical_transition": _read_u64(flat, H_CLOCK),
        "base_epoch": _read_u64(flat, H_BASE_EPOCH),
        "field_bytes": int(field.nbytes),
        "regions": regions,
        "events": queue["events"],
        "named_values": queue["named_values"],
        "resource_ledger": ledger,
    }


def descriptor(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
) -> dict[str, Any]:
    """Encode the logical image as canonical nonzero persistence pages."""

    validate_field(field, profile, catalog)
    flat = field.reshape(-1)
    pages: list[dict[str, Any]] = []
    for index, start in enumerate(
        range(0, profile.total_words, PERSISTENCE_PAGE_WORDS)
    ):
        page = flat[start:start + PERSISTENCE_PAGE_WORDS]
        if not np.any(page):
            continue
        raw = page.astype("<f8", copy=False).tobytes(order="C")
        pages.append(
            {
                "index": index,
                "words": int(page.size),
                "data_b64": base64.b64encode(raw).decode("ascii"),
            }
        )
    return {
        "schema": REGIONAL_SCHEMA,
        "layout": REGIONAL_LAYOUT,
        "profile": profile.as_dict(),
        "profile_sha256": profile.fingerprint,
        "catalog_sha256": catalog.fingerprint,
        "page_words": PERSISTENCE_PAGE_WORDS,
        "field_pages": pages,
        "state_sha256": state_sha256(field, profile),
    }


def from_descriptor(
    value: Mapping[str, Any], catalog: KernelCatalog
) -> tuple[RegionalProfile, np.ndarray]:
    required = {
        "schema", "layout", "profile", "profile_sha256",
        "catalog_sha256", "page_words", "field_pages", "state_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise RegionalFieldError("regional descriptor keys are invalid")
    if value["schema"] != REGIONAL_SCHEMA or value["layout"] != REGIONAL_LAYOUT:
        raise RegionalFieldError("regional descriptor identity is invalid")
    if value["page_words"] != PERSISTENCE_PAGE_WORDS:
        raise RegionalFieldError("regional persistence page geometry is invalid")
    profile = RegionalProfile.from_dict(value["profile"])
    if (
        value["profile_sha256"] != profile.fingerprint
        or value["catalog_sha256"] != catalog.fingerprint
    ):
        raise RegionalFieldError(
            "regional descriptor profile or catalog digest mismatches"
        )
    encoded_pages = value["field_pages"]
    if not isinstance(encoded_pages, list):
        raise RegionalFieldError("regional descriptor pages are invalid")
    field = np.zeros(profile.shape, dtype=np.float64)
    flat = field.reshape(-1)
    previous = -1
    page_count = (
        profile.total_words + PERSISTENCE_PAGE_WORDS - 1
    ) // PERSISTENCE_PAGE_WORDS
    try:
        for page in encoded_pages:
            if not isinstance(page, Mapping) or set(page) != {
                "index", "words", "data_b64"
            }:
                raise ValueError("invalid page record")
            index = _integer(page["index"], "page index")
            if index <= previous or index >= page_count:
                raise ValueError("page order or index is invalid")
            start = index * PERSISTENCE_PAGE_WORDS
            expected_words = min(
                PERSISTENCE_PAGE_WORDS, profile.total_words - start
            )
            words = _integer(page["words"], "page words", minimum=1)
            if words != expected_words or not isinstance(
                page["data_b64"], str
            ):
                raise ValueError("page geometry is invalid")
            raw = base64.b64decode(page["data_b64"], validate=True)
            if (
                len(raw) != words * 8
                or base64.b64encode(raw).decode("ascii")
                != page["data_b64"]
            ):
                raise ValueError("page encoding is noncanonical")
            decoded = np.frombuffer(raw, dtype="<f8")
            if not np.any(decoded):
                raise ValueError("zero persistence page is noncanonical")
            flat[start:start + words] = decoded
            previous = index
    except (TypeError, ValueError) as exc:
        raise RegionalFieldError(
            "regional descriptor pages are invalid"
        ) from exc
    validate_field(field, profile, catalog)
    if value["state_sha256"] != state_sha256(field, profile):
        raise RegionalFieldError("regional descriptor state digest mismatches")
    return profile, field
def enqueue_event(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    event: Mapping[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    """Admit one external event as an explicit field transition."""

    validate_field(field, profile, catalog)
    if not isinstance(event, Mapping):
        raise RegionalFieldError("event submission must be a mapping")
    before = state_sha256(field, profile)
    mutable = np.array(field, copy=True, order="C")
    flat = mutable.reshape(-1)
    clock = _read_u64(flat, H_CLOCK)
    if clock >= U64_MAX - 1 or clock >= profile.max_steps:
        raise RegionalFieldError("event admission has no remaining transition capacity")
    queue_ref = _queue_ref(flat)
    queue = dict(_read_region(flat, profile, queue_ref))
    live_events = list(queue["events"])
    if live_events:
        parent = dict(live_events[0])
    else:
        program_ref = _descriptor_ref(flat, H_PROGRAM_CATALOG)
        scope_ref = _descriptor_ref(flat, H_ROOT_SCOPE)
        if program_ref is None or scope_ref is None:
            raise RegionalFieldError("root program or scope is missing")
        registry = _registry(flat, profile)[1]
        program_id = 0
        scope_id = 0
        for text_id, item in registry["entries"].items():
            if item.get("status") != "live":
                continue
            reference = RegionRef.from_dict(item["reference"])
            identity = (reference.slot, reference.generation)
            if identity == (program_ref.slot, program_ref.generation):
                program_id = int(text_id)
            if identity == (scope_ref.slot, scope_ref.generation):
                scope_id = int(text_id)
        if not program_id or not scope_id:
            raise RegionalFieldError("root program or scope identity is missing")
        parent = {
            "program_id": program_id,
            "scope_id": scope_id,
            "site": 0,
            "target_id": program_id,
        }
    admitted = _event_from_spec(
        flat,
        profile,
        queue,
        parent,
        event,
        clock=clock + 1,
    )
    live_events.append(admitted)
    queue["events"] = sorted(
        live_events, key=lambda item: int(item["sequence"])
    )
    _write_region(flat, profile, queue_ref, queue)
    _write_u64(flat, H_CLOCK, clock + 1)
    _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
    flat[H_STATUS] = STATUS_RUNNING
    flat[H_REASON] = REASON_NONE
    validate_field(mutable, profile, catalog)


    return mutable, {
        "schema": REGIONAL_SCHEMA,
        "kind": "event-admission",
        "event_id": admitted["event_id"],
        "logical_transition": clock + 1,
        "previous_state_sha256": before,
        "state_sha256": state_sha256(mutable, profile),
    }


def write_named_value(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    name: str,
    value: Any,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Publish one host-lowered input as an explicit regional transition."""

    validate_field(field, profile, catalog)
    _identifier(name, "named value")
    before = state_sha256(field, profile)
    mutable = np.array(field, copy=True, order="C")
    flat = mutable.reshape(-1)
    clock = _read_u64(flat, H_CLOCK)
    if clock >= U64_MAX - 1 or clock >= profile.max_steps:
        raise RegionalFieldError("input publication has no remaining transition capacity")
    queue = _read_region(flat, profile, _queue_ref(flat))
    object_id = queue["named_values"].get(name)
    if object_id is None:
        raise RegionalFieldError("named value is not declared")
    ref = _resolve_object(flat, profile, object_id, right=RIGHT_WRITE)
    changed = _write_region(flat, profile, ref, value)
    _write_u64(flat, H_CLOCK, clock + 1)
    if changed:
        _write_u64(
            flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1
        )
    validate_field(mutable, profile, catalog)
    return mutable, {
        "schema": REGIONAL_SCHEMA,
        "kind": "input-publication",
        "name": name,
        "changed": changed,
        "logical_transition": clock + 1,
        "previous_state_sha256": before,
        "state_sha256": state_sha256(mutable, profile),
    }
def restart_field(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    *,
    entry: int = 0,
    values: Mapping[str, Any] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Restart the admitted root program without resetting unrelated state."""

    validate_field(field, profile, catalog)
    entry = _integer(entry, "entry")
    before = state_sha256(field, profile)
    mutable = np.array(field, copy=True, order="C")
    flat = mutable.reshape(-1)
    clock = _read_u64(flat, H_CLOCK)
    if clock >= U64_MAX - 1 or clock >= profile.max_steps:
        raise RegionalFieldError("restart has no remaining transition capacity")
    queue_ref = _queue_ref(flat)
    queue = dict(_read_region(flat, profile, queue_ref))
    program_ref = _descriptor_ref(flat, H_PROGRAM_CATALOG)
    root_scope_ref = _descriptor_ref(flat, H_ROOT_SCOPE)
    if program_ref is None or root_scope_ref is None:
        raise RegionalFieldError("root program or scope is missing")
    registry_ref, registry = _registry(flat, profile)
    _ = registry_ref
    program_id = 0
    scope_id = 0
    for text_id, item in registry["entries"].items():
        if item.get("status") != "live":
            continue
        reference = RegionRef.from_dict(item["reference"])
        if (reference.slot, reference.generation) == (
            program_ref.slot,
            program_ref.generation,
        ):
            program_id = int(text_id)
        if (reference.slot, reference.generation) == (
            root_scope_ref.slot,
            root_scope_ref.generation,
        ):
            scope_id = int(text_id)
    if not program_id or not scope_id:
        raise RegionalFieldError("root program or scope identity is missing")
    program = _program_for(flat, profile, program_id)
    if entry >= len(program):
        raise RegionalFieldError("restart entry is outside the program")
    named = dict(queue["named_values"])
    for name, value in sorted((values or {}).items()):
        if name not in named:
            raise RegionalFieldError("restart cannot create an undeclared named value")
        ref = _resolve_object(flat, profile, int(named[name]), right=RIGHT_WRITE)
        _write_region(flat, profile, ref, value)
    _refresh_descriptor_dependencies(flat, profile, catalog)
    retained = [
        event
        for event in queue["events"]
        if int(event["program_id"]) != program_id
    ]
    replaced = len(queue["events"]) - len(retained)
    if len(retained) >= profile.max_events:
        raise RegionalFieldError("event queue is exhausted")
    event_id = _integer(queue["next_event_id"], "next event ID", minimum=1)
    sequence = _read_u64(flat, H_NEXT_SEQUENCE)
    if sequence >= U64_MAX:
        raise RegionalFieldError("event sequence is exhausted")
    retained.append(
        {
            "dependencies": {},
            "event_id": event_id,
            "kind": "restart",
            "payload": None,
            "pc": entry,
            "priority": 0,
            "program_id": program_id,
            "ready_at": clock + 1,
            "reason": None,
            "scope_id": scope_id,
            "sequence": sequence,
            "site": 0,
            "source_id": program_id,
            "state": "ready",
            "target_id": program_id,
        }
    )
    queue["events"] = sorted(retained, key=lambda event: int(event["sequence"]))
    queue["next_event_id"] = event_id + 1
    _write_u64(flat, H_NEXT_SEQUENCE, sequence + 1)
    _write_region(flat, profile, queue_ref, queue)
    _write_u64(flat, H_CLOCK, clock + 1)
    _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
    flat[H_STATUS] = STATUS_RUNNING
    flat[H_REASON] = REASON_NONE
    validate_field(mutable, profile, catalog)
    return mutable, {
        "schema": REGIONAL_SCHEMA,
        "kind": "restart",
        "replaced_events": replaced,
        "logical_transition": clock + 1,
        "previous_state_sha256": before,
        "state_sha256": state_sha256(mutable, profile),
    }


def grow_field(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    *,
    mode_count: int,
    max_steps: int | None = None,
) -> tuple[RegionalProfile, np.ndarray, dict[str, Any]]:
    """Perform one explicit profile-changing storage transition."""

    validate_field(field, profile, catalog)
    mode_count = _integer(mode_count, "mode_count", minimum=profile.mode_count)
    target_steps = profile.max_steps if max_steps is None else _integer(
        max_steps, "max_steps", minimum=profile.max_steps, maximum=U64_MAX - 1
    )
    if mode_count == profile.mode_count and target_steps == profile.max_steps:
        raise RegionalFieldError("growth must increase storage or transition capacity")
    successor_profile = replace(
        profile, mode_count=mode_count, max_steps=target_steps
    )
    clock = _read_u64(field.reshape(-1), H_CLOCK)
    if clock >= U64_MAX - 1 or clock + 1 > target_steps:
        raise RegionalFieldError("growth has no representable successor transition")
    successor = np.zeros(successor_profile.shape, dtype=np.float64)
    successor.reshape(-1)[: profile.total_words] = field.reshape(-1)
    flat = successor.reshape(-1)
    flat[H_TOTAL_WORDS] = successor_profile.total_words
    flat[H_PROFILE_SHA:H_PROFILE_SHA + 8] = _sha_words(
        successor_profile.fingerprint
    )
    _write_u64(flat, H_CLOCK, clock + 1)
    _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
    validate_field(successor, successor_profile, catalog)
    return successor_profile, successor, {
        "schema": REGIONAL_SCHEMA,
        "kind": "grow",
        "old_profile_sha256": profile.fingerprint,
        "profile_sha256": successor_profile.fingerprint,
        "logical_transition": clock + 1,
        "previous_state_sha256": state_sha256(field, profile),
        "state_sha256": state_sha256(successor, successor_profile),
        "copied_words": profile.total_words,
    }


def intervene_automaton(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    *,
    site: int,
    excitation: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply a field-only scheduler intervention for a causal comparison."""

    validate_field(field, profile, catalog)
    site = _integer(site, "site", maximum=profile.automaton_sites - 1)
    excitation = _integer(
        excitation, "excitation", maximum=profile.automaton_scale
    )
    mutable = np.array(field, copy=True, order="C")
    flat = mutable.reshape(-1)
    queue = _read_region(flat, profile, _queue_ref(flat))
    automaton_id = _integer(
        queue["automaton_id"], "automaton object ID", minimum=1
    )
    automaton_ref = _resolve_object(
        flat, profile, automaton_id, right=RIGHT_WRITE
    )
    words = _read_region(flat, profile, automaton_ref)
    controller = ExcitableConstraintController(
        ExcitableConstraintProfile(
            size=profile.automaton_sites,
            scale=profile.automaton_scale,
            max_ticks=profile.automaton_max_ticks,
        )
    )
    native = ExcitableConstraintState(
        np.asarray(words, dtype=np.float64),
        controller.profile.fingerprint,
    )
    changed = controller.intervene(
        native, variable=site + 1, excitation=excitation
    )
    _write_region(
        flat,
        profile,
        automaton_ref,
        [int(value) for value in changed._field],
    )
    clock = _read_u64(flat, H_CLOCK)
    if clock >= U64_MAX - 1 or clock >= profile.max_steps:
        raise RegionalFieldError("intervention has no remaining transition capacity")
    _write_u64(flat, H_CLOCK, clock + 1)
    _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
    validate_field(mutable, profile, catalog)
    return mutable, {
        "schema": REGIONAL_SCHEMA,
        "kind": "automaton-intervention",
        "site": site,
        "excitation": excitation,
        "logical_transition": clock + 1,
        "previous_state_sha256": state_sha256(field, profile),
        "state_sha256": state_sha256(mutable, profile),
    }



def object_value(field: np.ndarray, profile: RegionalProfile, catalog: KernelCatalog, object_id: int) -> Any:
    validate_field(field, profile, catalog)
    return _read_region(field.reshape(-1), profile, _resolve_object(field.reshape(-1), profile, object_id))


def named_object_id(field: np.ndarray, profile: RegionalProfile, catalog: KernelCatalog, name: str) -> int:
    validate_field(field, profile, catalog)
    _identifier(name, "value name")
    queue = _read_region(field.reshape(-1), profile, _queue_ref(field.reshape(-1)))
    value = queue["named_values"].get(name)
    return _integer(value, "named object ID", minimum=1)


def named_values(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    names: Sequence[str],
) -> dict[str, Any]:
    """Read several named values through one validated field snapshot."""

    validate_field(field, profile, catalog)
    flat = field.reshape(-1)
    queue = _read_region(flat, profile, _queue_ref(flat))
    identifiers = queue["named_values"]
    result: dict[str, Any] = {}
    for name in names:
        _identifier(name, "value name")
        object_id = _integer(
            identifiers.get(name), "named object ID", minimum=1
        )
        result[name] = _read_region(
            flat, profile, _resolve_object(flat, profile, object_id)
        )
    return result


__all__ = [
    "CAPABILITY_SET_SCHEMA",
    "CODEC_JSON",
    "CODEC_WORDS",
    "DEPENDENCY_LIST_SCHEMA",
    "EMPTY_KERNEL_CATALOG",
    "KIND_BINDINGS",
    "KIND_CONTINUATION",
    "KIND_CREDIT",
    "KIND_EVIDENCE_PROGRESS",
    "KIND_LEDGER",
    "KIND_PROCEDURE",
    "KIND_PROGRAM",
    "KIND_QUEUE",
    "KIND_RELATION",
    "KIND_SCOPE",
    "KIND_VALUE",
    "KernelCatalog",
    "KernelResult",
    "REGIONAL_LAYOUT",
    "REGIONAL_MAGIC",
    "REGIONAL_SCHEMA",
    "RIGHT_ALL",
    "RIGHT_EMIT",
    "RIGHT_EXECUTE",
    "RIGHT_MANAGE",
    "RIGHT_READ",
    "RIGHT_WRITE",
    "RegionRef",
    "RegionalFieldError",
    "RegionalProfile",
    "SEMANTIC_ANSWER_STATUSES",
    "SEMANTIC_EPISTEMIC_KINDS",
    "SEMANTIC_RECORD_KINDS",
    "SEMANTIC_RECORD_SCHEMA_VERSION",
    "SemanticRef",
    "TYPE_RECORD_SCHEMA",
    "canonical_program",
    "canonical_semantic_record",
    "descriptor",
    "from_descriptor",
    "grow_field",
    "initial_field",
    "inspect_field",
    "intervene_automaton",
    "make_semantic_record",
    "named_object_id",
    "named_values",
    "object_value",
    "resolve_semantic_record",
    "restart_field",
    "run_field",
    "semantic_record_ref",
    "state_sha256",
    "step_field",
    "validate_field",
    "write_named_value",
]
