"""Versioned regional storage and scheduling for :mod:`cassi_field_computer`.

This module is implementation support for ``FieldComputer`` rather than a
second computer.  It owns no persistent state: every adaptive value, queue
entry, automaton lane, continuation, and resource counter is encoded in the
single immutable float64 field returned to the caller.  Host objects decoded
here are disposable views over that field.
"""
from __future__ import annotations

from bisect import bisect_left
import base64
import copy
import math
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field as dataclass_field, replace
import hashlib
import json
import os
import zlib
from functools import lru_cache
from threading import Lock
from types import CodeType, FunctionType, MappingProxyType
from typing import Any, Callable, Iterator, Mapping, Sequence

import numpy as np
from cassi_field_residency import ResourceLimits, ResourceWait, ResidencyManager
from cassi_field_storage import ObjectOverlay, ObjectSubset, StorageError, object_bytes
from cassi_page_tier_store import PageTierStore, PageTierStoreError

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
PERSISTENCE_CHUNK_SCHEMA = "cassifi.regional-page-chunks.v1"
PERSISTENCE_CHUNK_CODEC = "u32-le-zlib.v1"
PAGED_STATE_KIND_FLAT = "logical-f64-v1"
PAGED_STATE_KIND_ROOT = "page-tree-v1"
PAGED_STATE_IDENTITY_SCHEMA = "cassifi.regional-page-state.v1"
NEURAL_MEMBRANE_SCHEMA = "cassifi.neural-membrane.v1"
NEURAL_MEMBRANE_PLANES = ("observation", "yang", "yin", "readback")
NEURAL_MEMBRANE_PLANE_COUNT = len(NEURAL_MEMBRANE_PLANES)
NEURAL_MEMBRANE_FIRST_PLANE = 9 - NEURAL_MEMBRANE_PLANE_COUNT
NEURAL_MEMBRANE_MODE_QUANTUM = 65_536
NEURAL_MEMBRANE_DEFAULT_GAIN_PPM = 1_000
# Field-derived activity may modulate the automaton's priority among
# already-eligible continuations.  The rule is bounded, versioned, and off by
# default: with no declared activity the drive is exactly ``priority + 1``.
ACTIVITY_SCHEMA = "cassifi.regional-activity.v1"
ACTIVITY_UNIT = 1024
WAIT_CYCLE_SCHEMA = "cassifi.regional-wait-cycle.v1"
MAX_AWAIT_CYCLE_HOPS = 64
MAX_AWAIT_PREREQUISITE_LEND = 8
ACTIVITY_MIN_FACTOR = ACTIVITY_UNIT // 2
ACTIVITY_MAX_FACTOR = 2 * ACTIVITY_UNIT
INPUT_REGION_PAGE_BYTES = 64 * 1024
MAX_INPUT_REGION_BYTES = 64 * 1024 * 1024
MAX_INPUT_WINDOW_BYTES = 1024 * 1024

DEFAULT_ACTIVITY_WEIGHT = 0
_RUN_REGISTRY_CACHE: ContextVar[
    dict[tuple[int, int, int], dict[str, Any]] | None
] = ContextVar("_RUN_REGISTRY_CACHE", default=None)
_RUN_CANONICAL_PADDING: ContextVar[
    set[tuple[int, int]] | None
] = ContextVar("_RUN_CANONICAL_PADDING", default=None)
_HASH_EXECUTOR_LOCK = Lock()
_HASH_EXECUTOR: ThreadPoolExecutor | None = None


_CATALOG_FINGERPRINT_CACHE: dict[int, tuple[Any, str]] = {}


# Hashing releases the GIL; retain the pool across short runs so each
# immutable field transition does not pay thread creation and join costs.
def _shared_hash_executor(workers: int) -> ThreadPoolExecutor:
    global _HASH_EXECUTOR
    if _HASH_EXECUTOR is None:
        with _HASH_EXECUTOR_LOCK:
            if _HASH_EXECUTOR is None:
                _HASH_EXECUTOR = ThreadPoolExecutor(max_workers=workers)
    return _HASH_EXECUTOR




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
    "authority-denied",
    "non-identifiable",
    "pending-observation",
    "representation-insufficient",
    "resource-exhausted",
    "support-gap",
    "supported",
    "unresolved",
    "waiting",
)

EMBODIED_ROLE_BINDINGS_SCHEMA = "cassifi.embodied-role-bindings.v1"
EMBODIED_ROLE_BINDING_SCHEMA = "cassifi.embodied-role-binding.v1"
EMBODIED_ROLE_NAMES = ("core", "mantle", "fringe")

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
    "RECEIVE",
)


class RegionalFieldError(ValueError):
    """A regional profile, image, reference, program, or transition is invalid."""


_CANONICAL_CACHE: dict[Any, bytes] = {}

def _canonical(value: Any) -> bytes:
    try:
        # Attempt fast path for hashable values
        if isinstance(value, (str, int, float, bool, type(None))) or (isinstance(value, tuple) and all(isinstance(v, (str, int, float, bool, type(None))) for v in value)):
            # Check cache
            cached = _CANONICAL_CACHE.get(value)
            if cached is not None:
                return cached

        result = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False, check_circular=False,
        ).encode("utf-8")

        # Cache if hashable
        if isinstance(value, (str, int, float, bool, type(None))) or (isinstance(value, tuple) and all(isinstance(v, (str, int, float, bool, type(None))) for v in value)):
            _CANONICAL_CACHE[value] = result

        return result
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


class ImmutableInputPages:
    """Read-only bounded windows over one immutable sensory byte buffer.

    The buffer remains separate from the adaptive regional field.  Pages are
    logical fixed-size windows into the producer's immutable ``bytes`` object,
    so publication does not copy or materialise a dense field.
    """

    __slots__ = ("_pixels", "byte_length", "sha256")

    def __init__(self, pixels: bytes) -> None:
        if not isinstance(pixels, bytes):
            raise RegionalFieldError("input region must be immutable bytes")
        if len(pixels) > MAX_INPUT_REGION_BYTES:
            raise RegionalFieldError("input region exceeds the bounded byte limit")
        self._pixels = pixels
        self.byte_length = len(pixels)
        self.sha256 = hashlib.sha256(pixels).hexdigest()

    @property
    def page_count(self) -> int:
        return (
            self.byte_length + INPUT_REGION_PAGE_BYTES - 1
        ) // INPUT_REGION_PAGE_BYTES

    def read_page(self, page_index: int) -> bytes:
        page_index = _integer(
            page_index, "input page index", maximum=max(0, self.page_count - 1)
        )
        start = page_index * INPUT_REGION_PAGE_BYTES
        return self._pixels[
            start : min(self.byte_length, start + INPUT_REGION_PAGE_BYTES)
        ]

    def read_window(self, offset: int, length: int) -> bytes:
        offset = _integer(offset, "input window offset", maximum=self.byte_length)
        length = _integer(length, "input window length", maximum=MAX_INPUT_WINDOW_BYTES)
        end = offset + length
        if end > self.byte_length:
            raise RegionalFieldError("input window exceeds the published byte range")
        return self._pixels[offset:end]

    def page_views(self) -> Iterator[memoryview]:
        view = memoryview(self._pixels)
        for start in range(0, self.byte_length, INPUT_REGION_PAGE_BYTES):
            yield view[
                start : min(self.byte_length, start + INPUT_REGION_PAGE_BYTES)
            ]


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


def _json_words_from_raw(raw: bytes) -> np.ndarray:
    if len(raw) > U32_MAX:
        raise RegionalFieldError("JSON payload exceeds u32 length")
    framed = len(raw).to_bytes(4, "little") + raw
    framed += b"\x00" * ((-len(framed)) % 4)
    return np.frombuffer(framed, dtype="<u4")


def _json_words(value: Any) -> np.ndarray:
    return _json_words_from_raw(_canonical(value))


def _decode_json_words(
    words: Sequence[int] | np.ndarray,
    *,
    _validated: bool = False,
) -> Any:
    try:
        packed = np.asarray(words)
    except (TypeError, ValueError) as exc:
        raise RegionalFieldError("payload words are invalid") from exc
    if not _validated:
        if packed.ndim != 1 or packed.dtype.kind not in {"i", "u", "f"}:
            raise RegionalFieldError("payload words are invalid")
        if packed.size:
            if packed.dtype.kind == "f":
                if not np.isfinite(packed).all() or not np.equal(packed, np.floor(packed)).all():
                    raise RegionalFieldError("payload word must be an integer")
            if np.any(packed < 0) or np.any(packed > U32_MAX):
                raise RegionalFieldError("payload word is outside the u32 range")
    raw = packed.astype("<u4", copy=False).tobytes()
    if len(raw) < 4:
        raise RegionalFieldError("JSON payload frame is truncated")
    length = int.from_bytes(raw[:4], "little")
    if length > len(raw) - 4 or any(raw[4 + length:]):
        raise RegionalFieldError("JSON payload frame is noncanonical")
    try:
        value = json.loads(raw[4:4 + length])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegionalFieldError("JSON payload is invalid") from exc
    if not _validated and _canonical(value) != raw[4:4 + length]:
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
    neural_membrane: bool = False
    neural_membrane_gain_ppm: int = NEURAL_MEMBRANE_DEFAULT_GAIN_PPM

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
        if not isinstance(self.neural_membrane, bool):
            raise RegionalFieldError("neural_membrane must be boolean")
        _integer(
            self.neural_membrane_gain_ppm,
            "neural_membrane_gain_ppm",
            maximum=1_000_000,
        )
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
        if minimum + boot > self.workspace_words:
            raise RegionalFieldError("regional profile cannot hold its bootstrap closure")
        if self.max_events > self.max_registry_entries:
            raise RegionalFieldError("event capacity exceeds identity capacity")

    @property
    def total_words(self) -> int:
        return 9 * self.mode_count

    @property
    def workspace_words(self) -> int:
        """Words available to the regional allocator, excluding the membrane."""

        planes = (
            NEURAL_MEMBRANE_FIRST_PLANE
            if self.neural_membrane
            else 9
        )
        return planes * self.mode_count

    @property
    def neural_membrane_words(self) -> int:
        return (
            NEURAL_MEMBRANE_PLANE_COUNT * self.mode_count
            if self.neural_membrane
            else 0
        )

    @property
    def neural_membrane_offset(self) -> int:
        if not self.neural_membrane:
            raise RegionalFieldError("regional profile has no neural membrane")
        return self.workspace_words

    @property
    def shape(self) -> tuple[int, int, int]:
        return (1, self.total_words, 1)

    @property
    def state_bytes(self) -> int:
        return self.total_words * np.dtype(np.float64).itemsize

    @lru_cache(maxsize=64)
    def _catalog_sha256(self) -> str:
        return hashlib.sha256(_canonical({
            "operations": _CATALOG_OPERATIONS,
            "kernels": self.kernel_names,
            "revision": 1,
        })).hexdigest()

    @property
    def catalog_sha256(self) -> str:
        return self._catalog_sha256()

    @lru_cache(maxsize=64)
    def _fingerprint(self) -> str:
        value = asdict(self)
        value["kernel_names"] = list(self.kernel_names)
        if not self.neural_membrane:
            value.pop("neural_membrane")
            value.pop("neural_membrane_gain_ppm")
        return hashlib.sha256(_canonical({
            "schema": REGIONAL_SCHEMA,
            "layout": REGIONAL_LAYOUT,
            "catalog_sha256": self.catalog_sha256,
            **value,
        })).hexdigest()

    @property
    def fingerprint(self) -> str:
        return self._fingerprint()

    @property
    def profile_sha256(self) -> str:
        return self.fingerprint

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["kernel_names"] = list(self.kernel_names)
        if not self.neural_membrane:
            value.pop("neural_membrane")
            value.pop("neural_membrane_gain_ppm")
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


@dataclass(frozen=True, slots=True)
class EmbodiedRoleBinding:
    """Read-only binding of one embodied role to current owner field state.

    This is a detached projection, not another regional owner. Numeric region
    identities, operator descriptions, semantic references, and interfaces
    are supplied by the canonical owner and remain tied to its state hash and
    generation.
    """

    role: str
    status: str
    state_generation: int
    state_sha256: str
    region_ids: tuple[str, ...]
    layout: tuple[Mapping[str, Any], ...] = ()
    operator: tuple[Mapping[str, Any], ...] = ()
    semantic_refs: tuple[SemanticRef, ...] = ()
    interfaces: tuple[Mapping[str, Any], ...] = ()
    unknowns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.role not in EMBODIED_ROLE_NAMES:
            raise RegionalFieldError("embodied role name is invalid")
        if self.status not in {"bound", "partial", "unavailable"}:
            raise RegionalFieldError("embodied role status is invalid")
        _integer(
            self.state_generation,
            "embodied role state generation",
            maximum=U64_MAX,
        )
        if (
            not isinstance(self.state_sha256, str)
            or len(self.state_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.state_sha256)
        ):
            raise RegionalFieldError("embodied role state digest is invalid")
        if not isinstance(self.region_ids, tuple) or len(self.region_ids) > 64:
            raise RegionalFieldError("embodied role region IDs exceed their bound")
        for region_id in self.region_ids:
            if not isinstance(region_id, str) or not region_id or len(region_id) > 768:
                raise RegionalFieldError("embodied role region ID is invalid")
        if tuple(sorted(set(self.region_ids))) != self.region_ids:
            raise RegionalFieldError("embodied role region IDs must be sorted and unique")
        if self.status == "bound" and not self.region_ids:
            raise RegionalFieldError("a bound embodied role requires a numeric region")
        if self.status == "unavailable" and self.region_ids:
            raise RegionalFieldError("an unavailable embodied role cannot name regions")

        layout = self._canonical_rows(self.layout, "embodied role layout")
        layout_ids = {
            row.get("region_id")
            for row in layout
            if isinstance(row.get("region_id"), str)
        }
        if any(
            not isinstance(row.get("region_id"), str)
            or row["region_id"] not in self.region_ids
            for row in layout
        ):
            raise RegionalFieldError("embodied role layout names an unbound region")
        if layout_ids != set(self.region_ids):
            raise RegionalFieldError("embodied role layout does not cover its regions")
        object.__setattr__(self, "layout", layout)
        object.__setattr__(
            self, "operator", self._canonical_rows(self.operator, "embodied role operator")
        )
        if not isinstance(self.semantic_refs, tuple) or len(self.semantic_refs) > 64:
            raise RegionalFieldError("embodied role semantic refs exceed their bound")
        refs = tuple(
            item if isinstance(item, SemanticRef) else SemanticRef.from_dict(item)
            for item in self.semantic_refs
        )
        ref_keys = tuple((item.kind, item.id, item.content_version) for item in refs)
        if ref_keys != tuple(sorted(set(ref_keys))):
            raise RegionalFieldError(
                "embodied role semantic refs must be sorted and unique"
            )
        object.__setattr__(self, "semantic_refs", refs)
        object.__setattr__(
            self,
            "interfaces",
            self._canonical_rows(self.interfaces, "embodied role interfaces"),
        )
        if not isinstance(self.unknowns, tuple) or any(
            not isinstance(item, str) or not item or len(item) > 256
            for item in self.unknowns
        ):
            raise RegionalFieldError("embodied role unknowns are invalid")
        if len(self.unknowns) > 64:
            raise RegionalFieldError("embodied role has too many unknowns")
        if self.status == "partial" and not self.unknowns:
            raise RegionalFieldError("a partial embodied role must name its unknowns")

    @staticmethod
    def _canonical_rows(
        rows: tuple[Mapping[str, Any], ...], name: str
    ) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(rows, tuple) or len(rows) > 64:
            raise RegionalFieldError(f"{name} rows are invalid")
        normalized: list[Mapping[str, Any]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                raise RegionalFieldError(f"{name} row must be a mapping")
            value = _semantic_json(dict(row), name)
            if not isinstance(value, dict):
                raise RegionalFieldError(f"{name} row must be an object")
            normalized.append(value)
        return tuple(normalized)

    def as_dict(self) -> dict[str, Any]:
        return json.loads(_canonical({
            "schema": EMBODIED_ROLE_BINDING_SCHEMA,
            "role": self.role,
            "status": self.status,
            "state_generation": self.state_generation,
            "state_sha256": self.state_sha256,
            "region_ids": list(self.region_ids),
            "layout": [dict(row) for row in self.layout],
            "operator": [dict(row) for row in self.operator],
            "semantic_refs": [item.as_dict() for item in self.semantic_refs],
            "interfaces": [dict(row) for row in self.interfaces],
            "unknowns": list(self.unknowns),
        }))


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
            supersedes.id != record["id"]
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
    _state_words: np.ndarray = dataclass_field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.status not in {"done", "yield", "blocked", "fault"}:
            raise RegionalFieldError("native kernel returned an invalid status")
        _integer(self.work, "native work", minimum=0)
        if not isinstance(self.events, tuple) or any(not isinstance(event, Mapping) for event in self.events):
            raise RegionalFieldError("native kernel events must be a tuple of mappings")
        trusted_raw = getattr(
            self.state, "_cassi_canonical_json", None
        )
        if (
            not isinstance(trusted_raw, bytes)
            or not getattr(
                self.state,
                "_cassi_canonical_json_trusted",
                False,
            )
        ):
            trusted_raw = _canonical(self.state)
        if getattr(self.state, "_cassi_region_reusable", False):
            setattr(
                self.state,
                "_cassi_canonical_json",
                trusted_raw,
            )
        object.__setattr__(
            self,
            "_state_words",
            _json_words_from_raw(trusted_raw),
        )
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


@lru_cache(maxsize=128)
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
        cache_key = id(self)
        cached = _CATALOG_FINGERPRINT_CACHE.get(cache_key)
        if cached is not None and cached[0] is self:
            return cached[1]
        digest = hashlib.sha256(
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
        _CATALOG_FINGERPRINT_CACHE[cache_key] = (self, digest)
        return digest

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
        return _decode_json_words(words, _validated=True)
    if int(row[D_CODEC]) == CODEC_WORDS:
        return [int(word) for word in words]
    raise RegionalFieldError("region codec is unsupported")


def _write_region(
    flat: np.ndarray,
    profile: RegionalProfile,
    ref: RegionRef,
    value: Any,
    *,
    _encoded_json_words: np.ndarray | None = None,
) -> bool:
    row = _row_for_ref(flat, profile, ref, right=RIGHT_WRITE)
    if int(row[D_FLAGS]) & FLAG_IMMUTABLE:
        raise RegionalFieldError("immutable region cannot be written")
    if int(row[D_CODEC]) == CODEC_JSON:
        words = (
            _json_words(value)
            if _encoded_json_words is None
            else _encoded_json_words
        )
    elif int(row[D_CODEC]) == CODEC_WORDS:
        if isinstance(value, (str, bytes, bytearray)) or not isinstance(
            value, Sequence
        ):
            raise RegionalFieldError(
                "word region requires a finite sequence"
            )
        words = tuple(
            _integer(int(word), "region word") for word in value
        )
    else:
        raise RegionalFieldError("region codec is unsupported")
    if len(words) > int(row[D_CAPACITY]):
        raise RegionalFieldError(
            "region value exceeds allocated capacity"
            f" (slot {ref.slot}: {len(words)} > {int(row[D_CAPACITY])} words)"
        )
    base = int(row[D_BASE])
    old_used = int(row[D_USED])
    if old_used == len(words) and np.array_equal(
        flat[base:base + old_used], words
    ):
        return False
    version = _read_u64(row, D_VERSION)
    if version >= U64_MAX:
        raise RegionalFieldError("region version is exhausted")
    padding_cache = _RUN_CANONICAL_PADDING.get()
    padding_key = (ref.slot, ref.generation)
    first_write = padding_cache is None or padding_key not in padding_cache
    if first_write and not isinstance(flat, _PagedFieldView):
        flat[base:base + int(row[D_CAPACITY])] = 0
    elif len(words) < old_used:
        flat[base + len(words):base + old_used] = 0
    if first_write and padding_cache is not None:
        padding_cache.add(padding_key)
    if len(words):
        flat[base:base + len(words)] = words
    row[D_USED] = len(words)
    _write_u64(row, D_VERSION, version + 1)
    return True


def _registry(
    flat: np.ndarray,
    profile: RegionalProfile,
) -> tuple[RegionRef, dict[str, Any]]:
    ref = _descriptor_ref(flat, H_REGISTRY)
    if ref is None:
        raise RegionalFieldError("regional image has no registry")
    row = _row_for_ref(flat, profile, ref)
    cache_key = (
        ref.slot,
        ref.generation,
        _read_u64(row, D_VERSION),
    )
    cache = _RUN_REGISTRY_CACHE.get()
    if cache is not None and cache_key in cache:
        return ref, cache[cache_key]
    value = _read_region(flat, profile, ref)
    if not isinstance(value, dict):
        raise RegionalFieldError("reference registry is invalid")
    if cache is not None:
        cache[cache_key] = value
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
    if cursor + capacity > profile.workspace_words:
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
    if len(words):
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
    elif op == "RECEIVE":
        allowed = {"op", "target", "next"}
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


def _initial_registry_words(profile: RegionalProfile, ref: RegionRef) -> np.ndarray:
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

    # Pre-calculate valid kinds and codecs for faster lookup
    valid_kinds = set(KIND_NAMES)
    valid_codecs = {CODEC_JSON, CODEC_WORDS}

    # Cache the mask for flag validation to avoid repeated bitwise ops in loop
    valid_flag_mask = FLAG_LIVE | FLAG_IMMUTABLE | FLAG_QUARANTINED | FLAG_PROTECTED

    for index, row in enumerate(_directory(flat, profile)):
        # Inline _integer for generation and flags to avoid function call overhead
        generation = int(row[D_GENERATION])
        flags = int(row[D_FLAGS])

        if flags == 0:
            # Check if all other columns are 0
            # Using a generator expression with any is fast, but we can optimize
            # by checking if the sum of absolute values is 0 or just iterating
            # Since DIRECTORY_WORDS is small (16), a direct check is fine.
            # However, 'any' is implemented in C and very fast.
            if any(int(row[column]) != 0 for column in range(1, DIRECTORY_WORDS)):
                raise RegionalFieldError("free directory row is noncanonical")
            continue

        if flags & ~valid_flag_mask:
            raise RegionalFieldError("directory flags are invalid")

        if bool(flags & FLAG_LIVE) == bool(flags & FLAG_QUARANTINED):
            raise RegionalFieldError("directory row must be live or quarantined")

        if generation == 0:
            raise RegionalFieldError("occupied directory row has zero generation")

        kind = int(row[D_KIND])
        codec = int(row[D_CODEC])

        if kind not in valid_kinds or codec not in valid_codecs:
            raise RegionalFieldError("directory kind or codec is invalid")

        base = int(row[D_BASE])
        used = int(row[D_USED])
        capacity = int(row[D_CAPACITY])

        if capacity <= 0 or used > capacity or base < arena_start or base + capacity > profile.workspace_words:
            raise RegionalFieldError("directory payload range is invalid")

        if int(row[D_RESERVED]) != 0:
            raise RegionalFieldError("directory reserved word is nonzero")

        # Metadata references
        # D_READ_CAPS, D_WRITE_CAPS, D_PARENT_REF, D_TYPE_REF, D_DEPENDENCY_REF
        # These are indices 5, 6, 7, 8, 9 in the directory row? 
        # Assuming D_* constants map to these offsets relative to row start.
        # We need to access them efficiently.
        # Let's assume D_READ_CAPS=5, D_WRITE_CAPS=6, etc. based on typical layout.
        # If not, we should use the constants directly.
        metadata_indices = (D_READ_CAPS, D_WRITE_CAPS, D_PARENT_REF, D_TYPE_REF, D_DEPENDENCY_REF)
        metadata_ids = [int(row[col]) for col in metadata_indices]

        if any(metadata_ids) and not all(metadata_ids):
            raise RegionalFieldError(
                "descriptor metadata references are only partially populated"
            )

        # Validate metadata IDs against max_registry_entries
        # Inlining _integer logic: check if int, in range [0, max]
        max_reg = profile.max_registry_entries
        for obj_id in metadata_ids:
            if obj_id < 0 or obj_id > max_reg:
                raise RegionalFieldError("descriptor metadata object ID is out of range")

        intervals.append((base, base + capacity, index + 1))
        live_slots.add((index + 1, generation))

        if flags & FLAG_QUARANTINED:
            if used != 0:
                raise RegionalFieldError("quarantined region cannot expose used words")
        elif codec == CODEC_JSON:
            # Optimization: Pass _validated=True to skip numpy validation overhead
            # The data is already known to be valid u32 words from the directory structure
            # and the fact that it's being read from a validated flat array.
            _decode_json_words(_payload_words(flat, row), _validated=True)
        else:
            # CODEC_WORDS
            # Inline _integer check for words
            for word in _payload_words(flat, row):
                w = int(word)
                if w < 0 or w > U32_MAX:
                    raise RegionalFieldError("regional word is out of range")

    intervals.sort()
    for previous, current in zip(intervals, intervals[1:]):
        if previous[1] > current[0]:
            raise RegionalFieldError("regional payload ranges overlap")

    distinguished_offsets = (H_ACTIVE_CONTINUATION, H_QUEUE, H_PROGRAM_CATALOG, H_LEFT_STACK,
                   H_RIGHT_STACK, H_LEDGER, H_REGISTRY, H_ROOT_SCOPE)

    for offset in distinguished_offsets:
        # Inline _descriptor_ref logic for performance
        slot = int(flat[offset])
        generation = int(flat[offset + 1])

        if slot == 0 and generation == 0:
            continue

        if slot == 0 or generation == 0:
            raise RegionalFieldError("distinguished reference is half-null")

        if (slot, generation) not in live_slots:
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
        _payload_words(flat, row), _validated=True
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


def _state_digest_head(
    profile: RegionalProfile, *, profile_sha256: str | None = None
) -> Any:
    """The canonical preamble every logical-state digest starts from."""

    return hashlib.sha256(_canonical({
        "layout": REGIONAL_LAYOUT,
        "profile_sha256": profile.fingerprint if profile_sha256 is None else profile_sha256,
        "shape": profile.shape,
    }))


def state_sha256(
    field: np.ndarray, profile: RegionalProfile, *, profile_sha256: str | None = None
) -> str:
    digest = _state_digest_head(profile, profile_sha256=profile_sha256)
    digest.update(memoryview(field))
    return digest.hexdigest()


def paged_root_state_sha256(
    profile: RegionalProfile,
    root_sha256: str,
    page_count: int,
    *,
    profile_sha256: str | None = None,
) -> str:
    """Exact Merkle identity for a paged image without a dense field scan."""

    return hashlib.sha256(
        _canonical(
            {
                "schema": PAGED_STATE_IDENTITY_SCHEMA,
                "profile_sha256": profile.fingerprint if profile_sha256 is None else profile_sha256,
                "root_sha256": root_sha256,
                "page_count": page_count,
                "page_words": PERSISTENCE_PAGE_WORDS,
            }
        )
    ).hexdigest()


def _program_for(
    flat: np.ndarray,
    profile: RegionalProfile,
    object_id: int,
    *,
    _program_cache: dict[
        tuple[int, int, int], list[dict[str, Any]]
    ] | None = None,
) -> list[dict[str, Any]]:
    ref = _resolve_object(
        flat,
        profile,
        object_id,
        right=RIGHT_EXECUTE,
    )
    row = _row_for_ref(flat, profile, ref)
    if int(row[D_KIND]) != KIND_PROGRAM:
        raise RegionalFieldError("event program identity has the wrong kind")
    cache_key = (
        ref.slot,
        ref.generation,
        _read_u64(row, D_VERSION),
    )
    if _program_cache is not None and cache_key in _program_cache:
        return _program_cache[cache_key]
    value = _read_region(flat, profile, ref)
    if (
        not isinstance(value, dict)
        or value.get("schema") != "cassifi.regional-program.v1"
    ):
        raise RegionalFieldError("regional program record is invalid")
    program = canonical_program(value.get("instructions"))
    if _program_cache is not None:
        stale_keys = [
            key
            for key in _program_cache
            if key[:2] == (ref.slot, ref.generation)
        ]
        for stale_key in stale_keys:
            del _program_cache[stale_key]
        _program_cache[cache_key] = program
    return program


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


def _descriptor_watch(
    flat: np.ndarray,
    profile: RegionalProfile,
    row: np.ndarray,
) -> tuple[tuple[int, int, int], ...]:
    watched: list[tuple[int, int, int]] = []
    for offset in (
        D_READ_CAPS,
        D_WRITE_CAPS,
        D_PARENT_REF,
        D_TYPE_REF,
        D_DEPENDENCY_REF,
    ):
        object_id = int(row[offset])
        if not object_id:
            continue
        ref = _resolve_object(flat, profile, object_id)
        target = _row_for_ref(flat, profile, ref)
        watched.append(
            (
                ref.slot,
                ref.generation,
                _read_u64(target, D_VERSION),
            )
        )
    return tuple(watched)


def _descriptor_watch_current(
    flat: np.ndarray,
    profile: RegionalProfile,
    watched: Sequence[tuple[int, int, int]],
) -> bool:
    for slot, generation, version in watched:
        row = _row_for_ref(
            flat,
            profile,
            RegionRef(slot, generation, rights=RIGHT_READ),
        )
        if _read_u64(row, D_VERSION) != version:
            return False
    return True


def _native_contract_status(
    flat: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    event: Mapping[str, Any],
    instruction: Mapping[str, Any],
    *,
    _descriptor_cache: dict[
        tuple[int, int], dict[str, Any]
    ] | None = None,
) -> str | None:
    contract = (catalog.contracts or {}).get(instruction["kernel"])
    state_ref = _resolve_object(
        flat, profile, instruction["state"], right=RIGHT_WRITE
    )
    state_row = _row_for_ref(
        flat, profile, state_ref, right=RIGHT_WRITE
    )
    descriptor_key = (state_ref.slot, state_ref.generation)
    state_version = _read_u64(state_row, D_VERSION)
    cached = (
        None
        if _descriptor_cache is None
        else _descriptor_cache.get(descriptor_key)
    )
    if (
        cached is not None
        and cached["state_version"] == state_version
        and _descriptor_watch_current(
            flat, profile, cached["watched"]
        )
    ):
        metadata = cached["metadata"]
    else:
        metadata = _descriptor_metadata_for_row(
            flat, profile, catalog, state_row
        )
        if _descriptor_cache is not None:
            _descriptor_cache[descriptor_key] = {
                "metadata": metadata,
                "state_version": state_version,
                "watched": _descriptor_watch(
                    flat, profile, state_row
                ),
            }
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


def _eligibility(
    flat: np.ndarray,
    profile: RegionalProfile,
    event: Mapping[str, Any],
    catalog: KernelCatalog,
    *,
    _descriptor_cache: dict[
        tuple[int, int], dict[str, Any]
    ] | None = None,
    _program_cache: dict[
        tuple[int, int, int], list[dict[str, Any]]
    ] | None = None,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    if event["state"] not in {"ready", "waiting"}:
        return False, event.get("reason") or event["state"], None
    if (
        event["state"] == "waiting"
        and event.get("reason") == "kernel-blocked"
    ):
        return False, "kernel-blocked", None
    try:
        if not _scope_live(flat, profile, int(event["scope_id"])):
            return False, "scope-closed", None
        program = _program_for(
            flat,
            profile,
            int(event["program_id"]),
            _program_cache=_program_cache,
        )
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
                _resolve_object(
                    flat,
                    profile,
                    instruction["target"],
                ),
            )
            if (
                not isinstance(target, Mapping)
                or target.get("status") not in {"done", "halted"}
            ):
                return False, "await", instruction
        if op == "RECEIVE":
            intent = _communication_intent_from_event(event)
            if intent is None or _validate_communication_event(
                flat, profile, event
            ) is not None:
                return False, "fault", None
            if (
                instruction["target"] != event["target_id"]
                or intent.get("receiver") != f"regional-object:{instruction['target']}"
            ):
                return False, "fault", None
            _resolve_object(
                flat, profile, instruction["target"], right=RIGHT_WRITE
            )
        if op == "NATIVE":
            if instruction["kernel"] not in catalog.kernels:
                return False, "fault", instruction
            contract_status = _native_contract_status(
                flat,
                profile,
                catalog,
                event,
                instruction,
                _descriptor_cache=_descriptor_cache,
            )
            if contract_status is not None:
                return False, contract_status, instruction
            _resolve_object(
                flat,
                profile,
                instruction["state"],
                right=RIGHT_WRITE,
            )
            arguments = instruction.get("arguments", {})
            if not isinstance(arguments, Mapping):
                _resolve_object(flat, profile, arguments)
        for key in ("source", "target", "output"):
            if key in instruction:
                right = (
                    RIGHT_READ
                    if key == "source"
                    else RIGHT_WRITE
                )
                _resolve_object(
                    flat,
                    profile,
                    instruction[key],
                    right=right,
                )
        return True, None, instruction
    except PageUnavailable:
        raise
    except (RegionalFieldError, ValueError, TypeError):
        return False, "fault", None


def _event_sort_key(event: Mapping[str, Any]) -> tuple[int, int, int, int, int]:
    return (
        -int(event["priority"]), int(event["ready_at"]),
        int(event["source_id"]), int(event["target_id"]), int(event["sequence"]),
    )


def _instruction_write_targets(instruction: Mapping[str, Any]) -> tuple[int, ...]:
    """Object IDs one execution of this instruction will write."""
    op = instruction["op"]
    if op == "NATIVE":
        targets = [int(instruction["state"])]
        if "output" in instruction:
            targets.append(int(instruction["output"]))
        return tuple(targets)
    if op in {"READ", "COPY", "WRITE", "WRITE_EMIT", "RECEIVE", "ALLOC"} and "target" in instruction:
        return (int(instruction["target"]),)
    return ()


def _await_target_pending(flat: np.ndarray, profile: RegionalProfile, object_id: int) -> bool:
    """Whether an AWAIT target object is still short of done/halted."""
    target = _read_region(flat, profile, _resolve_object(flat, profile, object_id))
    return not (
        isinstance(target, Mapping)
        and target.get("status") in {"done", "halted"}
    )


def _resume_blocked_awaits(
    flat: np.ndarray,
    profile: RegionalProfile,
    candidates: Sequence[dict[str, Any]],
    *,
    _program_cache: dict[tuple[int, int, int], list[dict[str, Any]]] | None = None,
) -> list[int]:
    """Resume AWAIT-cycle events whose target has actually been satisfied.

    A ``blocked`` verdict is a bounded statement about the declared event
    graph, never a sentence: an external producer may still complete the
    awaited object at any later step, so every blocked event re-checks its
    exact target first and resumes with its exact identity and continuation.
    """
    resumed: list[int] = []
    for event in candidates:
        if event.get("state") != "blocked" or event.get("reason") != "await-cycle":
            continue
        try:
            program = _program_for(
                flat, profile, int(event["program_id"]), _program_cache=_program_cache,
            )
            instruction = program[int(event["pc"])]
            if instruction["op"] != "AWAIT":
                event["state"], event["reason"] = "waiting", "await"
                continue
            pending = _await_target_pending(flat, profile, int(instruction["target"]))
        except PageUnavailable:
            raise
        except Exception:
            continue
        if not pending:
            event["state"], event["reason"] = "ready", None
            resumed.append(int(event["event_id"]))
    return resumed


def _await_cycle_analysis(
    flat: np.ndarray,
    profile: RegionalProfile,
    candidates: Sequence[Mapping[str, Any]],
    eligibility_rows: Sequence[tuple[bool, str | None, Mapping[str, Any] | None]],
    *,
    _program_cache: dict[tuple[int, int, int], list[dict[str, Any]]] | None = None,
) -> tuple[frozenset[int], dict[int, int], dict[str, Any]]:
    """Bounded closed-AWAIT-cycle verdict over the declared event graph.

    An event waiting on an unsatisfied AWAIT target is ``blocked`` only when
    every declared producer of that awaited object is itself an event whose
    resumption depends on the same closed wait chain, and no admissible
    producer outside that chain exists.  Anything else — an eligible writer,
    a writer program with a runnable event, or an object with no declared
    in-field writer at all — stays a live ``waiting`` event, because an
    external producer may still complete it.  The traversal is bounded by
    ``MAX_AWAIT_CYCLE_HOPS``; an unbounded trace is a live wait, never a
    deadlock verdict, so detection can miss but cannot falsely deadlock.
    """
    receipt: dict[str, Any] = {
        "schema": WAIT_CYCLE_SCHEMA,
        "kind": "await-cycle-analysis",
        "await_waiters": 0,
        "blocked_event_ids": [],
        "lent_event_ids": [],
    }
    waiters: dict[int, dict[str, Any]] = {}
    for event, row in zip(candidates, eligibility_rows):
        reason = row[1]
        instruction = row[2]
        if reason == "await-cycle":
            try:
                program = _program_for(
                    flat, profile, int(event["program_id"]), _program_cache=_program_cache,
                )
                instruction = program[int(event["pc"])]
            except PageUnavailable:
                raise
            except Exception:
                continue
        if instruction is None or instruction["op"] != "AWAIT":
            continue
        try:
            target_id = int(instruction["target"])
            pending = _await_target_pending(flat, profile, target_id)
        except PageUnavailable:
            raise
        except Exception:
            continue
        if pending:
            waiters[int(event["event_id"])] = {
                "program_id": int(event["program_id"]),
                "pc": int(event["pc"]),
                "target": target_id,
                "priority": int(event["priority"]),
                "reason": reason,
            }
    if not waiters:
        return frozenset(), {}, receipt
    receipt["await_waiters"] = len(waiters)

    programs: dict[int, list[dict[str, Any]] | None] = {}
    for event in candidates:
        program_id = int(event["program_id"])
        if program_id in programs:
            continue
        try:
            programs[program_id] = _program_for(
                flat, profile, program_id, _program_cache=_program_cache,
            )
        except PageUnavailable:
            raise
        except Exception:
            programs[program_id] = None
    writer_programs: dict[int, dict[int, tuple[int, ...]]] = {}
    for program_id, program in programs.items():
        if program is None:
            continue
        written: dict[int, list[int]] = {}
        for pc, instruction in enumerate(program):
            for target in _instruction_write_targets(instruction):
                written.setdefault(target, []).append(pc)
        for target, pcs in written.items():
            writer_programs.setdefault(target, {})[program_id] = tuple(pcs)
    events_by_program: dict[int, list[int]] = {}
    current_writers: dict[int, set[int]] = {}
    for event in candidates:
        event_id = int(event["event_id"])
        program_id = int(event["program_id"])
        events_by_program.setdefault(program_id, []).append(event_id)
        program = programs.get(program_id)
        pc = int(event["pc"])
        instruction = (
            program[pc]
            if program is not None and 0 <= pc < len(program)
            else None
        )
        if instruction is None:
            continue
        for target in _instruction_write_targets(instruction):
            current_writers.setdefault(target, set()).add(event_id)

    verdict: dict[int, bool] = {}
    visiting: set[int] = set()

    def trace(event_id: int, depth: int) -> bool:
        if event_id in verdict:
            return verdict[event_id]
        if event_id in visiting:
            return True
        if depth > MAX_AWAIT_CYCLE_HOPS:
            return False
        waiter = waiters[event_id]
        target = waiter["target"]
        program_id = waiter["program_id"]
        pc = waiter["pc"]
        for other in current_writers.get(target, ()):
            if other != event_id and other not in waiters:
                verdict[event_id] = False
                return False
        producers: set[int] = set()
        for writer_id, pcs in writer_programs.get(target, {}).items():
            members = [
                member for member in events_by_program.get(writer_id, ())
                if member != event_id
            ]
            if any(member not in waiters for member in members):
                verdict[event_id] = False
                return False
            if writer_id == program_id:
                if not members and any(pcs_index > pc for pcs_index in pcs):
                    producers.add(event_id)
                    continue
            producers.update(member for member in members if member in waiters)
        if not producers:
            verdict[event_id] = False
            return False
        visiting.add(event_id)
        try:
            result = all(
                trace(producer, depth + 1) for producer in sorted(producers)
            )
        finally:
            visiting.discard(event_id)
        verdict[event_id] = result
        return result

    blocked = frozenset(
        event_id for event_id in sorted(waiters) if trace(event_id, 0)
    )
    receipt["blocked_event_ids"] = sorted(blocked)
    return blocked, waiters, receipt


def _await_prerequisite_lending(
    flat: np.ndarray,
    profile: RegionalProfile,
    candidates: Sequence[Mapping[str, Any]],
    eligibility_rows: Sequence[tuple[bool, str, Mapping[str, Any] | None]],
    waiters: Mapping[int, Mapping[str, Any]],
    blocked: frozenset[int],
    *,
    dispatch_count: int,
) -> dict[int, int]:
    """Lend bounded priority from foreground blocked waits to prerequisites.

    Each foreground waiter lends one unit to one actual eligible event whose
    current execution will advance an awaited object or a stale declared
    dependency.  Both the waiter set and the chosen prerequisite rotate with
    ``dispatch_count`` so competing waits and multiple prerequisites share the
    lend fairly, and at most ``MAX_AWAIT_PREREQUISITE_LEND`` events carry a
    lent boost each step.  The boost is selection-time only: declared event
    priorities are never rewritten and the lend retracts automatically when
    the wait resolves or the prerequisite stops being eligible.
    """
    lends: dict[int, int] = {}
    waiter_ids = sorted(
        event_id for event_id, waiter in waiters.items()
        if event_id not in blocked and waiter["priority"] > 0
        and waiter["reason"] in {"await", "stale"}
    )
    if not waiter_ids:
        return lends
    waiter_ids = waiter_ids[dispatch_count % len(waiter_ids):] + waiter_ids[:dispatch_count % len(waiter_ids)]
    eligible_writers: dict[int, tuple[int, ...]] = {}
    for event, row in zip(candidates, eligibility_rows):
        if row[0] and row[2] is not None:
            eligible_writers[int(event["event_id"])] = _instruction_write_targets(row[2])
    for waiter_id in waiter_ids:
        if len(lends) >= MAX_AWAIT_PREREQUISITE_LEND:
            break
        waiter = waiters[waiter_id]
        if waiter["reason"] == "stale":
            awaited: set[int] = set()
            event = next(row for row in candidates if int(row["event_id"]) == waiter_id)
            for text_id, expected in event["dependencies"].items():
                try:
                    ref = _resolve_object(flat, profile, int(text_id))
                    row = _row_for_ref(flat, profile, ref)
                    if _read_u64(row, D_VERSION) != int(expected):
                        awaited.add(int(text_id))
                except PageUnavailable:
                    raise
                except RegionalFieldError:
                    continue
        else:
            awaited = {waiter["target"]}
        prerequisites = sorted(
            event_id for event_id, targets in eligible_writers.items()
            if event_id != waiter_id and awaited.intersection(targets)
        )
        if not prerequisites:
            continue
        chosen = prerequisites[(dispatch_count + waiter_id) % len(prerequisites)]
        lends[chosen] = max(lends.get(chosen, 0), int(waiter["priority"]))
    return lends


def canonical_activity(
    values: Mapping[Any, Any] | None,
) -> dict[int, float]:
    """Validate caller-supplied field activity against the declared range.

    Keys are event sequence numbers and values are finite numbers in
    ``[-1, 1]``.  Values outside the range are clamped, not refused: the
    modulation rule is bounded by construction, so an over-range caller
    measurement saturates rather than selecting a different rule.
    """

    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise RegionalFieldError("field activity must be a mapping")
    canonical: dict[int, float] = {}
    for key, value in values.items():
        sequence = _integer(key, "field activity event sequence")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RegionalFieldError("field activity value is not numeric")
        number = float(value)
        if not bool(np.isfinite(number)):
            raise RegionalFieldError("field activity value is not finite")
        canonical[sequence] = max(-1.0, min(1.0, number))
    return canonical


def _activity_drive(
    candidates: Sequence[Mapping[str, Any]],
    eligible: Sequence[bool],
    activity: Mapping[int, float],
    weight: int,
) -> tuple[list[int], dict[str, Any] | None]:
    """Modulate automaton drive among already-eligible candidates only.

    Field-derived activity reorders the positive drive the existing excitable
    automaton receives; it cannot make an ineligible candidate eligible, does
    not touch the fairness interval, and with no declared activity the drive is
    exactly ``priority + 1``.  The modulation factor is bounded to one half and
    twice the declared weight unit, and every applied value is recorded.
    """

    positive = [int(event["priority"]) + 1 for event in candidates]
    if not activity or weight == 0:
        return positive, None
    weight = _integer(weight, "field activity weight", minimum=0)
    weight = min(weight, ACTIVITY_UNIT)
    record: dict[str, Any] = {
        "schema": ACTIVITY_SCHEMA,
        "unit": ACTIVITY_UNIT,
        "weight": weight,
        "applied": [],
        "unmatched": 0,
    }
    for index, event in enumerate(candidates):
        value = activity.get(int(event["sequence"]))
        if value is None:
            record["unmatched"] += 1
            continue
        if not eligible[index]:
            continue
        scaled = int(value * ACTIVITY_UNIT)
        factor = ACTIVITY_UNIT + (weight * scaled) // ACTIVITY_UNIT
        factor = max(ACTIVITY_MIN_FACTOR, min(ACTIVITY_MAX_FACTOR, factor))
        modulated = max(1, (positive[index] * factor) // ACTIVITY_UNIT)
        if modulated != positive[index]:
            record["applied"].append(
                {
                    "sequence": int(event["sequence"]),
                    "activity": scaled,
                    "factor": factor,
                    "drive": modulated,
                }
            )
        positive[index] = modulated
    if not record["applied"] and not record["unmatched"]:
        return positive, None
    return positive, record


def _advance_automaton(
    flat: np.ndarray,
    profile: RegionalProfile,
    queue: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    eligible: Sequence[bool],
    activity: Mapping[int, float] | None = None,
    activity_weight: int = DEFAULT_ACTIVITY_WEIGHT,
) -> tuple[int | None, Mapping[str, Any], dict[str, Any] | None]:
    automaton_id = _integer(queue.get("automaton_id"), "automaton object ID", minimum=1)
    ref = _resolve_object(flat, profile, automaton_id, right=RIGHT_WRITE)
    words = _read_region(flat, profile, ref)
    lanes = np.asarray(words, dtype=np.float64)
    controller = ExcitableConstraintController(ExcitableConstraintProfile(
        size=profile.automaton_sites, scale=profile.automaton_scale,
        max_ticks=profile.automaton_max_ticks,
    ))
    positive, modulation = _activity_drive(
        candidates, eligible, canonical_activity(activity), activity_weight
    )
    negative = [0 for _event in candidates]
    selected, receipt = controller.advance_lanes(
        lanes, positive=positive, negative=negative, eligible=eligible,
    )
    _write_region(flat, profile, ref, [int(value) for value in lanes])
    return (None if selected is None else selected - 1), receipt, modulation


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
    _native_state_cache: dict[tuple[int, int, int], Any] | None = None,
    _state_cache_updates: list[
        tuple[tuple[int, int, int], Any]
    ] | None = None,
) -> tuple[str, Any, int, list[dict[str, Any]]]:
    op = instruction["op"]
    output: Any = None
    work = 1
    emitted: list[dict[str, Any]] = []
    if op == "HALT":
        return "done", None, work, emitted
    if op in {"READ", "COPY"}:
        value = _read_region(
            flat,
            profile,
            _resolve_object(flat, profile, instruction["source"]),
        )
        _write_region(
            flat,
            profile,
            _resolve_object(
                flat,
                profile,
                instruction["target"],
                right=RIGHT_WRITE,
            ),
            value,
        )
        output = value
    elif op == "RECEIVE":
        intent = _communication_intent_from_event(event)
        if intent is None:
            raise RegionalFieldError("RECEIVE requires a field communication event")
        _validate_communication_event(flat, profile, event)
        if instruction["target"] != event["target_id"]:
            raise RegionalFieldError("RECEIVE target differs from event target")
        payload_ref = intent["payload_ref"]
        source_id = _integer(payload_ref["object_id"], "communication object ID", minimum=1)
        source_version = _integer(payload_ref["object_version"], "communication object version", minimum=1, maximum=U64_MAX)
        source_ref = _resolve_object(flat, profile, source_id, right=RIGHT_READ)
        source_row = _row_for_ref(flat, profile, source_ref, right=RIGHT_READ)
        value = _read_region(flat, profile, source_ref)
        source_digest = hashlib.sha256(_canonical(value)).hexdigest()
        if (
            _read_u64(source_row, D_VERSION) != source_version
            or source_digest != payload_ref["source_sha256"]
        ):
            raise RegionalFieldError("RECEIVE source version or digest is stale")
        target_ref = _resolve_object(
            flat, profile, instruction["target"], right=RIGHT_WRITE
        )
        _write_region(flat, profile, target_ref, value)
        target_row = _row_for_ref(flat, profile, target_ref)
        output = {
            "schema": "cassifi.field-communication-consumption.v1",
            "intent_sha256": hashlib.sha256(_canonical(intent)).hexdigest(),
            "consumer_use_id": intent["consumer_use_id"],
            "receiver": intent["receiver"],
            "source_object_id": source_id,
            "source_object_version": source_version,
            "source_root_sha256": payload_ref["root_sha256"],
            "source_sha256": source_digest,
            "target_id": instruction["target"],
            "target_version": _read_u64(target_row, D_VERSION),
            "result_sha256": hashlib.sha256(
                _canonical(_read_region(flat, profile, target_ref))
            ).hexdigest(),
        }
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
        state_ref = _resolve_object(
            flat, profile, instruction["state"], right=RIGHT_WRITE
        )
        state_row = _row_for_ref(
            flat, profile, state_ref, right=RIGHT_WRITE
        )
        state_cache_key = (
            state_ref.slot,
            state_ref.generation,
            _read_u64(state_row, D_VERSION),
        )
        state = (
            _native_state_cache.get(state_cache_key)
            if _native_state_cache is not None
            else None
        )
        if state is None:
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
        _write_region(
            flat,
            profile,
            state_ref,
            result.state,
            _encoded_json_words=result._state_words,
        )
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
        if (
            _state_cache_updates is not None
            and getattr(result.state, "_cassi_region_reusable", False)
        ):
            state_cache_key = (
                state_ref.slot,
                state_ref.generation,
                _read_u64(state_row, D_VERSION),
            )
            _state_cache_updates.append(
                (state_cache_key, result.state)
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
    activity: Mapping[Any, Any] | None = None,
    activity_weight: int = DEFAULT_ACTIVITY_WEIGHT,
    _input_validated: bool = False,
    _validate_output: bool = True,
    _native_state_cache: dict[
        tuple[int, int, int], Any
    ] | None = None,
    _descriptor_cache: dict[
        tuple[int, int], dict[str, Any]
    ] | None = None,
    _program_cache: dict[
        tuple[int, int, int], list[dict[str, Any]]
    ] | None = None,
    _previous_state_sha256: str | None = None,
    _defer_state_sha256: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Execute one automaton-selected, bounded regional transition."""

    if not _input_validated:
        validate_field(field, profile, catalog)
    before_sha = (
        _previous_state_sha256
        if _previous_state_sha256 is not None
        else state_sha256(field, profile)
    )
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
            "state_sha256": (
                None
                if _defer_state_sha256
                else state_sha256(successor, profile)
            ),
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
            "state_sha256": (
                None
                if _defer_state_sha256
                else state_sha256(successor, profile)
            ), "logical_transition": clock,
        }

    mutable_field = np.array(field, copy=True, order="C")
    flat = mutable_field.reshape(-1)
    queue_ref = _queue_ref(flat)
    queue = _read_region(flat, profile, queue_ref)
    events = [dict(event) for event in queue["events"]]
    candidates = sorted(events, key=_event_sort_key)
    resumed_awaits = _resume_blocked_awaits(
        flat, profile, candidates, _program_cache=_program_cache,
    )
    eligibility_rows = [
        _eligibility(
            flat,
            profile,
            event,
            catalog,
            _descriptor_cache=_descriptor_cache,
            _program_cache=_program_cache,
        )
        for event in candidates
    ]
    blocked_awaits, waiters, await_receipt = _await_cycle_analysis(
        flat, profile, candidates, eligibility_rows, _program_cache=_program_cache,
    )
    dispatch_count = int(queue["dispatch_count"]) + 1
    lends = _await_prerequisite_lending(
        flat, profile, candidates, eligibility_rows, waiters, blocked_awaits,
        dispatch_count=dispatch_count,
    )
    await_receipt["lent_event_ids"] = sorted(lends)
    await_receipt["resumed_event_ids"] = resumed_awaits
    eligible = [row[0] for row in eligibility_rows]
    automaton_index, automaton_receipt, activity_modulation = _advance_automaton(
        flat, profile, queue, candidates, eligible, activity, activity_weight
    )
    ready_indices = [index for index, flag in enumerate(eligible) if flag]
    if not ready_indices:
        for event, row in zip(candidates, eligibility_rows):
            if int(event["event_id"]) in blocked_awaits:
                event["state"], event["reason"] = "blocked", "await-cycle"
            else:
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
            "await_analysis": await_receipt,
            "state_sha256": (
                None
                if _defer_state_sha256
                else state_sha256(successor, profile)
            ), "logical_transition": clock + 1,
            "automaton": dict(automaton_receipt),
            **(
                {}
                if activity_modulation is None
                else {"activity_modulation": activity_modulation}
            ),
        }

    if dispatch_count % profile.fairness_interval == 0:
        selected_index = min(ready_indices, key=lambda index: (
            int(candidates[index]["ready_at"]), int(candidates[index]["sequence"])
        ))
    elif lends:
        selected_index = min(ready_indices, key=lambda index: (
            -max(int(candidates[index]["priority"]), lends.get(int(candidates[index]["event_id"]), 0)),
            -lends.get(int(candidates[index]["event_id"]), 0),
            int(candidates[index]["ready_at"]), int(candidates[index]["sequence"]),
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
    trial_field = mutable_field
    trial_flat = trial_field.reshape(-1)
    trial_queue = copy.deepcopy(queue)
    trial_selected = copy.deepcopy(selected)
    state_cache_updates: list[
        tuple[tuple[int, int, int], Any]
    ] = []
    try:
        disposition, output, work, emitted = _execute_instruction(
            trial_flat,
            profile,
            catalog,
            trial_queue,
            trial_selected,
            instruction,
            clock=clock + 1,
            _native_state_cache=_native_state_cache,
            _state_cache_updates=state_cache_updates,
        )
        mutable_field = trial_field
        flat = trial_flat
        queue = trial_queue
        selected = trial_selected
    except RegionalFieldError as exc:
        fault_detail = str(exc)
        disposition = "fault"
        mutable_field = np.array(field, copy=True, order="C")
        flat = mutable_field.reshape(-1)
        _advance_automaton(
            flat,
            profile,
            queue,
            candidates,
            eligible,
        )

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
    if activity_modulation is not None:
        ledger["activity_modulated"] = int(
            ledger.get("activity_modulated", 0)
        ) + len(activity_modulation["applied"])
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
    if _native_state_cache is not None:
        for cache_key, cached_state in state_cache_updates:
            slot, generation, _version = cache_key
            stale_keys = [
                key
                for key in _native_state_cache
                if key[:2] == (slot, generation)
            ]
            for stale_key in stale_keys:
                del _native_state_cache[stale_key]
            _native_state_cache[cache_key] = cached_state
            if _descriptor_cache is not None:
                descriptor_key = (slot, generation)
                descriptor = _descriptor_cache.get(descriptor_key)
                schema = (
                    cached_state.get("schema")
                    if isinstance(cached_state, Mapping)
                    else None
                )
                if descriptor is None or not isinstance(schema, str):
                    _descriptor_cache.pop(descriptor_key, None)
                else:
                    descriptor["state_version"] = cache_key[2]
                    descriptor["metadata"] = {
                        **descriptor["metadata"],
                        "state_schema": schema,
                    }
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
        "await_analysis": await_receipt,
        "automaton": dict(automaton_receipt),
        **(
            {}
            if activity_modulation is None
            else {"activity_modulation": activity_modulation}
        ),
        "previous_state_sha256": before_sha,
        "state_sha256": (
            None
            if _defer_state_sha256
            else state_sha256(successor, profile)
        ),
        "logical_transition": clock + 1,
    }


def run_field(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog = EMPTY_KERNEL_CATALOG,
    *,
    steps: int | None = None,
    activity: Mapping[Any, Any] | None = None,
    activity_weight: int = DEFAULT_ACTIVITY_WEIGHT,
    _input_validated: bool = False,
    _skip_final_validation: bool = False,
    _native_state_cache: dict[tuple[int, int, int], Any] | None = None,
    _state_sha256: str | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    if not _input_validated:
        validate_field(field, profile, catalog)
    if steps is not None:
        steps = _integer(steps, "steps")
    initial_sha = state_sha256(field, profile) if _state_sha256 is None else _state_sha256
    current_sha = initial_sha
    current = field
    receipts: list[dict[str, Any]] = []
    native_state_cache = (
        {} if _native_state_cache is None else _native_state_cache
    )
    descriptor_cache: dict[
        tuple[int, int], dict[str, Any]
    ] = {}
    program_cache: dict[
        tuple[int, int, int], list[dict[str, Any]]
    ] = {}
    hash_workers = min(16, os.cpu_count() or 1)
    hash_executor = (
        _shared_hash_executor(hash_workers)
        if (
            field.nbytes >= 1_048_576
            and hash_workers > 1
            and (steps is None or steps > 1)
        )
        else None
    )
    pending_hashes: list[tuple[int, Future[str]]] = []
    registry_cache_token = _RUN_REGISTRY_CACHE.set({})
    padding_cache_token = _RUN_CANONICAL_PADDING.set(set())
    try:
        while int(current.reshape(-1)[H_STATUS]) in (
            STATUS_RUNNING,
            STATUS_WAITING,
        ):
            if steps is not None and len(receipts) >= steps:
                break
            successor, receipt = step_field(
                current,
                profile,
                catalog,
                activity=activity,
                activity_weight=activity_weight,
                _input_validated=True,
                _validate_output=False,
                _native_state_cache=native_state_cache,
                _descriptor_cache=descriptor_cache,
                _program_cache=program_cache,
                _previous_state_sha256=(
                    current_sha
                    if hash_executor is None or not receipts
                    else ""
                ),
                _defer_state_sha256=hash_executor is not None,
            )
            receipts.append(receipt)
            if hash_executor is None:
                current_sha = str(receipt["state_sha256"])
            else:
                pending_hashes.append(
                    (
                        len(receipts) - 1,
                        hash_executor.submit(
                            state_sha256,
                            successor,
                            profile,
                        ),
                    )
                )
                if len(pending_hashes) > hash_workers * 2:
                    index, future = pending_hashes.pop(0)
                    completed_sha = future.result()
                    receipts[index]["state_sha256"] = completed_sha
                    receipts[index + 1][
                        "previous_state_sha256"
                    ] = completed_sha
            if successor is current or receipt["kind"] in {
                "no-ready-event",
                "exhausted",
                "counter-exhausted",
            }:
                current = successor
                break
            current = successor
        if not _skip_final_validation:
            validate_field(current, profile, catalog)
        for index, future in pending_hashes:
            completed_sha = future.result()
            receipts[index]["state_sha256"] = completed_sha
            if index + 1 < len(receipts):
                receipts[index + 1][
                    "previous_state_sha256"
                ] = completed_sha
            current_sha = completed_sha
    finally:
        try:
            _RUN_CANONICAL_PADDING.reset(padding_cache_token)
        finally:
            _RUN_REGISTRY_CACHE.reset(registry_cache_token)
    return current, {
        "schema": REGIONAL_SCHEMA,
        "initial_state_sha256": initial_sha,
        "state_sha256": current_sha,
        "status": STATUS_NAMES[int(current.reshape(-1)[H_STATUS])],
        "reason": REASON_NAMES[int(current.reshape(-1)[H_REASON])],
        "paused": (
            steps is not None
            and len(receipts) >= steps
            and int(current.reshape(-1)[H_STATUS]) == STATUS_RUNNING
        ),
        "transitions_executed": len(receipts),
        "transition_receipts": receipts,
    }


def inspect_field(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    *,
    _input_validated: bool = False,
    _state_sha256: str | None = None,
) -> dict[str, Any]:
    if not _input_validated:
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
        "state_sha256": (
            state_sha256(field, profile)
            if _state_sha256 is None
            else _state_sha256
        ),
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
    *,
    _input_validated: bool = False,
    _state_sha256: str | None = None,
) -> dict[str, Any]:
    """Encode the logical image as canonical nonzero persistence pages."""

    if not _input_validated:
        validate_field(field, profile, catalog)

    flat = field.reshape(-1)
    total_words = profile.total_words
    page_words = PERSISTENCE_PAGE_WORDS

    # Pre-calculate slice boundaries to avoid repeated multiplication in the loop
    # Start indices for each potential page
    start_indices = range(0, total_words, page_words)

    pages: list[dict[str, Any]] = []

    for index, start in enumerate(start_indices):
        end = start + page_words
        # Ensure we don't exceed the total field size
        if end > total_words:
            end = total_words

        # Extract page slice
        page = flat[start:end]

        # Skip empty pages
        if not np.any(page):
            continue

        # Convert to bytes and encode
        # Note: page size might be less than page_words if we hit the end of the field
        raw = page.astype("<f8", copy=False).tobytes(order="C")
        pages.append(
            {
                "index": index,
                "words": len(page),
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
        "state_sha256": (
            state_sha256(field, profile)
            if _state_sha256 is None
            else _state_sha256
        ),
    }

def chunked_descriptor(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    *,
    _input_validated: bool = False,
    _state_sha256: str | None = None,
) -> tuple[dict[str, Any], Mapping[str, bytes]]:
    """Encode independently recoverable immutable pages for checkpoint storage.

    The regional image is defined over canonical u32 words represented in
    float64 cells.  Checkpoint chunks store those validated words directly,
    with both decoded and physical identities.  Zero pages remain implicit.
    """

    if not _input_validated:
        validate_field(field, profile, catalog)
    flat = field.reshape(-1)
    chunks: list[dict[str, Any]] = []
    objects: dict[str, bytes] = {}
    for index, start in enumerate(
        range(0, profile.total_words, PERSISTENCE_PAGE_WORDS)
    ):
        page = flat[start:start + PERSISTENCE_PAGE_WORDS]
        if not np.any(page):
            continue
        if (
            not np.isfinite(page).all()
            or not np.equal(page, np.floor(page)).all()
            or np.any(page < 0)
            or np.any(page > U32_MAX)
        ):
            raise RegionalFieldError(
                "regional persistence page is not a canonical u32 image"
            )
        decoded = page.astype("<u4", copy=False).tobytes(order="C")
        physical = zlib.compress(decoded, level=6)
        decoded_sha = hashlib.sha256(decoded).hexdigest()
        object_sha = hashlib.sha256(physical).hexdigest()
        prior = objects.get(object_sha)
        if prior is not None and prior != physical:
            raise RegionalFieldError("regional chunk identity collision")
        objects[object_sha] = physical
        chunks.append(
            {
                "codec": PERSISTENCE_CHUNK_CODEC,
                "decoded_bytes": len(decoded),
                "decoded_sha256": decoded_sha,
                "index": index,
                "object_bytes": len(physical),
                "object_sha256": object_sha,
                "start_word": start,
                "words": int(page.size),
            }
        )
    descriptor_value = {
        "schema": PERSISTENCE_CHUNK_SCHEMA,
        "layout": REGIONAL_LAYOUT,
        "profile": profile.as_dict(),
        "profile_sha256": profile.fingerprint,
        "catalog_sha256": catalog.fingerprint,
        "page_words": PERSISTENCE_PAGE_WORDS,
        "byte_order": "little",
        "word_encoding": "u32",
        "chunks": chunks,
        "state_sha256": (
            state_sha256(field, profile)
            if _state_sha256 is None
            else _state_sha256
        ),
    }
    return descriptor_value, MappingProxyType(objects)


def decode_chunked_page(
    descriptor_value: Mapping[str, Any],
    page_index: int,
    objects: Mapping[str, bytes],
) -> np.ndarray:
    """Decode and verify one page without materialising the complete image."""

    if not isinstance(descriptor_value, Mapping):
        raise RegionalFieldError("regional chunk descriptor is invalid")
    chunks = descriptor_value.get("chunks")
    if not isinstance(chunks, list):
        raise RegionalFieldError("regional chunk directory is invalid")
    selected = next(
        (
            row
            for row in chunks
            if isinstance(row, Mapping) and row.get("index") == page_index
        ),
        None,
    )
    if selected is None:
        profile = RegionalProfile.from_dict(descriptor_value.get("profile", {}))
        start = page_index * PERSISTENCE_PAGE_WORDS
        if page_index < 0 or start >= profile.total_words:
            raise RegionalFieldError("regional chunk page index is invalid")
        words = min(PERSISTENCE_PAGE_WORDS, profile.total_words - start)
        return np.zeros(words, dtype=np.float64)
    required = {
        "codec",
        "decoded_bytes",
        "decoded_sha256",
        "index",
        "object_bytes",
        "object_sha256",
        "start_word",
        "words",
    }
    if set(selected) != required or selected["codec"] != PERSISTENCE_CHUNK_CODEC:
        raise RegionalFieldError("regional chunk record is invalid")
    object_sha = selected["object_sha256"]
    if not isinstance(object_sha, str):
        raise RegionalFieldError("regional chunk object identity is invalid")
    physical = objects.get(object_sha)
    if (
        not isinstance(physical, bytes)
        or len(physical) != selected["object_bytes"]
        or hashlib.sha256(physical).hexdigest() != object_sha
    ):
        raise RegionalFieldError("regional chunk object is missing or corrupt")
    try:
        decoded = zlib.decompress(physical)
    except zlib.error as exc:
        raise RegionalFieldError("regional chunk cannot be decoded") from exc
    if (
        len(decoded) != selected["decoded_bytes"]
        or hashlib.sha256(decoded).hexdigest() != selected["decoded_sha256"]
        or len(decoded) != int(selected["words"]) * 4
    ):
        raise RegionalFieldError("regional decoded chunk identity mismatches")
    return np.frombuffer(decoded, dtype="<u4").astype(np.float64)


def from_chunked_descriptor(
    value: Mapping[str, Any],
    objects: Mapping[str, bytes],
    catalog: KernelCatalog,
    *,
    page_indices: Sequence[int] | None = None,
    accept_recorded_catalog: bool = False,
) -> tuple[RegionalProfile, np.ndarray]:
    """Restore a complete image or a bounded verified page view.

    ``accept_recorded_catalog`` admits a retained image whose recorded catalog
    fingerprint differs from the running catalog while the profile's kernel
    names still agree.  The retained bytes are verified against their own state
    digest before the recorded catalog identity is replaced by the running one,
    and the restored field is then validated by the running catalog, so the
    image is re-identified rather than trusted.
    """

    required = {
        "schema",
        "layout",
        "profile",
        "profile_sha256",
        "catalog_sha256",
        "page_words",
        "byte_order",
        "word_encoding",
        "chunks",
        "state_sha256",
    }
    allowed = required | {
        "state_sha256_kind",
        "resident_limit",
        "dirty_limit",
    }
    if not isinstance(value, Mapping) or not required <= set(value) <= allowed:
        raise RegionalFieldError("regional chunk descriptor keys are invalid")
    if (
        value["schema"] != PERSISTENCE_CHUNK_SCHEMA
        or value["layout"] != REGIONAL_LAYOUT
        or value["page_words"] != PERSISTENCE_PAGE_WORDS
        or value["byte_order"] != "little"
        or value["word_encoding"] != "u32"
    ):
        raise RegionalFieldError("regional chunk descriptor identity is invalid")
    profile = RegionalProfile.from_dict(value["profile"])
    if "resident_limit" in value:
        _integer(
            value["resident_limit"],
            "resident page limit",
            minimum=1,
            maximum=MAX_RESIDENCY_PAGES,
        )
    if "dirty_limit" in value:
        _integer(
            value["dirty_limit"],
            "dirty page limit",
            minimum=1,
            maximum=MAX_RESIDENCY_PAGES,
        )
    recorded_profile = value["profile_sha256"]
    recorded_catalog = value["catalog_sha256"]
    reidentify = recorded_catalog != catalog.fingerprint
    if reidentify:
        if not accept_recorded_catalog:
            raise RegionalFieldError(
                "regional chunk descriptor profile or catalog digest mismatches"
            )
        _sha_words(recorded_catalog)
        _sha_words(recorded_profile)
        if catalog.names != profile.kernel_names:
            raise RegionalFieldError("runtime kernel catalog does not match profile")
    elif recorded_profile != profile.fingerprint:
        raise RegionalFieldError(
            "regional chunk descriptor profile or catalog digest mismatches"
        )
    raw_chunks = value["chunks"]
    if not isinstance(raw_chunks, list):
        raise RegionalFieldError("regional chunk directory is invalid")
    indices: list[int] = []
    previous = -1
    page_count = (
        profile.total_words + PERSISTENCE_PAGE_WORDS - 1
    ) // PERSISTENCE_PAGE_WORDS
    for raw in raw_chunks:
        if not isinstance(raw, Mapping):
            raise RegionalFieldError("regional chunk record is invalid")
        index = _integer(raw.get("index"), "page index")
        start = index * PERSISTENCE_PAGE_WORDS
        expected_words = min(
            PERSISTENCE_PAGE_WORDS, profile.total_words - start
        )
        if (
            index <= previous
            or index >= page_count
            or raw.get("start_word") != start
            or raw.get("words") != expected_words
        ):
            raise RegionalFieldError("regional chunk geometry is invalid")
        previous = index
        indices.append(index)
    selected = indices if page_indices is None else sorted(set(page_indices))
    if page_indices is not None:
        if any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= page_count
            for index in selected
        ):
            raise RegionalFieldError("requested regional page is invalid")
        pages = np.zeros((len(selected), PERSISTENCE_PAGE_WORDS), dtype=np.float64)
        for output_index, page_index in enumerate(selected):
            decoded = decode_chunked_page(value, page_index, objects)
            pages[output_index, : decoded.size] = decoded
        return profile, pages
    field = np.zeros(profile.shape, dtype=np.float64)
    flat = field.reshape(-1)
    for page_index in indices:
        decoded = decode_chunked_page(value, page_index, objects)
        start = page_index * PERSISTENCE_PAGE_WORDS
        flat[start:start + decoded.size] = decoded
    identity_kind = value.get("state_sha256_kind", PAGED_STATE_KIND_FLAT)
    if identity_kind == PAGED_STATE_KIND_ROOT:
        directory = PageDirectory(
            recorded_profile,
            page_count,
            tuple(PageLeaf.from_record(record) for record in raw_chunks),
        )
        expected_state_sha256 = paged_root_state_sha256(
            profile,
            directory.tree(profile).root_sha256,
            page_count,
            profile_sha256=recorded_profile,
        )
    elif identity_kind == PAGED_STATE_KIND_FLAT:
        expected_state_sha256 = state_sha256(
            field, profile, profile_sha256=recorded_profile
        )
    else:
        raise RegionalFieldError("regional chunk state identity kind is invalid")
    if value["state_sha256"] != expected_state_sha256:
        raise RegionalFieldError("regional chunked state digest mismatches")
    if reidentify:
        flat[H_PROFILE_SHA:H_PROFILE_SHA + 8] = _sha_words(profile.fingerprint)
        flat[H_CATALOG_SHA:H_CATALOG_SHA + 8] = _sha_words(catalog.fingerprint)
    validate_field(field, profile, catalog)
    return profile, field

def from_descriptor(
    value: Mapping[str, Any],
    catalog: KernelCatalog,
    *,
    accept_recorded_catalog: bool = False,
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
    recorded_profile = value["profile_sha256"]
    recorded_catalog = value["catalog_sha256"]
    reidentify = recorded_catalog != catalog.fingerprint
    if reidentify:
        if not accept_recorded_catalog:
            raise RegionalFieldError(
                "regional descriptor profile or catalog digest mismatches"
            )
        _sha_words(recorded_catalog)
        _sha_words(recorded_profile)
        if catalog.names != profile.kernel_names:
            raise RegionalFieldError("runtime kernel catalog does not match profile")
    elif recorded_profile != profile.fingerprint:
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
    if value["state_sha256"] != state_sha256(
        field, profile, profile_sha256=recorded_profile
    ):
        raise RegionalFieldError("regional descriptor state digest mismatches")
    if reidentify:
        flat[H_PROFILE_SHA:H_PROFILE_SHA + 8] = _sha_words(profile.fingerprint)
        flat[H_CATALOG_SHA:H_CATALOG_SHA + 8] = _sha_words(catalog.fingerprint)
    validate_field(field, profile, catalog)
    return profile, field
def _enqueue_event_flat(
    flat: Any,
    profile: RegionalProfile,
    event: Mapping[str, Any],
) -> tuple[dict[str, Any], int]:
    """Apply queue admission to a mutable flat array or bounded paged view."""

    if not isinstance(event, Mapping):
        raise RegionalFieldError("event submission must be a mapping")
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
        flat, profile, queue, parent, event, clock=clock + 1,
    )
    live_events.append(admitted)
    queue["events"] = sorted(live_events, key=lambda item: int(item["sequence"]))
    _write_region(flat, profile, queue_ref, queue)
    _write_u64(flat, H_CLOCK, clock + 1)
    _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
    flat[H_STATUS] = STATUS_RUNNING
    flat[H_REASON] = REASON_NONE
    return admitted, clock
def _communication_intent_from_event(event: Mapping[str, Any]) -> Mapping[str, Any] | None:
    payload = event.get("payload")
    if not isinstance(payload, Mapping) or "field_communication" not in payload:
        return None
    intent = payload["field_communication"]
    if not isinstance(intent, Mapping):
        raise RegionalFieldError("field communication intent must be a mapping")
    return intent


def _validate_communication_event(
    flat: np.ndarray,
    profile: RegionalProfile,
    event: Mapping[str, Any],
    *,
    root_sha256: str | None = None,
) -> None:
    intent = _communication_intent_from_event(event)
    if intent is None:
        return
    if intent.get("schema") != "cassifi.field-communication-intent.v1":
        raise RegionalFieldError("field communication intent schema is invalid")
    from cassi_field_communication import FieldIntent
    try:
        typed_intent = FieldIntent.from_dict(intent)
    except (TypeError, ValueError, KeyError) as exc:
        raise RegionalFieldError("field communication intent is invalid") from exc
    if typed_intent.as_dict() != dict(intent):
        raise RegionalFieldError("field communication intent is noncanonical")
    if intent.get("urgency") not in {"foreground", "background"}:
        raise RegionalFieldError("field communication urgency is invalid")
    if intent.get("kind") not in {"send", "need", "subscribe"}:
        raise RegionalFieldError("field communication kind is invalid")
    reference = intent.get("payload_ref")
    if not isinstance(reference, Mapping) or set(reference) != {
        "predecessor_root_sha256", "root_sha256", "source_sha256",
        "changed_pages", "object_id", "object_version",
    }:
        raise RegionalFieldError("field communication payload reference is invalid")
    for key in ("predecessor_root_sha256", "root_sha256", "source_sha256"):
        _sha_words(reference.get(key))
    object_id = _integer(reference.get("object_id"), "communication object ID", minimum=1)
    version = _integer(reference.get("object_version"), "communication object version", minimum=1, maximum=U64_MAX)
    source_ref = _resolve_object(flat, profile, object_id, right=RIGHT_READ)
    source_row = _row_for_ref(flat, profile, source_ref, right=RIGHT_READ)
    if _read_u64(source_row, D_VERSION) != version:
        raise RegionalFieldError("field communication source version is stale")
    value = _read_region(flat, profile, source_ref)
    if hashlib.sha256(_canonical(value)).hexdigest() != reference["source_sha256"]:
        raise RegionalFieldError("field communication source digest is stale")
    dependency_versions = intent.get("dependency_versions")
    if not isinstance(dependency_versions, Mapping):
        raise RegionalFieldError("field communication dependencies are invalid")
    for key, dependency in dependency_versions.items():
        if (
            not isinstance(key, str)
            or not key.isdigit()
            or not isinstance(dependency, Mapping)
            or set(dependency) != {
                "object_id", "object_version", "source_sha256"
            }
        ):
            raise RegionalFieldError("field communication dependency version is invalid")
        dependency_id = _integer(
            dependency["object_id"], "communication dependency ID", minimum=1
        )
        dependency_version = _integer(
            dependency["object_version"],
            "communication dependency version",
            minimum=1,
            maximum=U64_MAX,
        )
        if str(dependency_id) != key:
            raise RegionalFieldError("field communication dependency key is invalid")
        dependency_ref = _resolve_object(
            flat, profile, dependency_id, right=RIGHT_READ
        )
        dependency_row = _row_for_ref(
            flat, profile, dependency_ref, right=RIGHT_READ
        )
        if _read_u64(dependency_row, D_VERSION) != dependency_version:
            raise RegionalFieldError("field communication dependency is stale")
        dependency_value = _read_region(flat, profile, dependency_ref)
        if hashlib.sha256(_canonical(dependency_value)).hexdigest() != dependency[
            "source_sha256"
        ]:
            raise RegionalFieldError("field communication dependency digest is stale")
    expected_dependencies = {
        key: int(dependency["object_version"])
        for key, dependency in dependency_versions.items()
    }
    if event.get("dependencies") != expected_dependencies:
        raise RegionalFieldError("field communication event dependencies are invalid")
    if dependency_versions.get(str(object_id)) != {
        "object_id": object_id,
        "object_version": version,
        "source_sha256": reference["source_sha256"],
    }:
        raise RegionalFieldError("field communication source dependency is invalid")
    _identifier(intent.get("sender"), "communication sender")
    _identifier(intent.get("receiver"), "communication receiver")
    consumer_use_id = intent.get("consumer_use_id")
    if consumer_use_id is not None:
        _identifier(consumer_use_id, "consumer use ID")
    changed_pages = reference["changed_pages"]
    if not isinstance(changed_pages, list) or any(
        isinstance(page, bool) or not isinstance(page, int) or page < 0
        for page in changed_pages
    ) or changed_pages != sorted(set(changed_pages)):
        raise RegionalFieldError("field communication changed pages are invalid")
    # External admission accepts only live registered executable program and scope
    # identities, never raw descriptor slots or caller-selected aliases.
    if intent["receiver"] != f"regional-object:{event.get('target_id')}":
        raise RegionalFieldError("field communication receiver does not match event target")
    _identifier(consumer_use_id, "consumer use ID")
    if object_id == event.get("target_id"):
        raise RegionalFieldError("communication source and receiver must be distinct")
    if event.get("kind") != f"communication:{intent['kind']}":
        raise RegionalFieldError("communication event kind differs from its intent")
    program_id = _integer(event.get("program_id"), "event program ID", minimum=1)
    program_ref = _resolve_object(flat, profile, program_id, right=RIGHT_EXECUTE)
    if int(_row_for_ref(flat, profile, program_ref)[D_KIND]) != KIND_PROGRAM:
        raise RegionalFieldError("field communication target is not a registered program")
    program = _program_for(flat, profile, program_id)
    pc = _integer(event.get("pc", 0), "event pc")
    if pc >= len(program) or program[pc].get("op") != "RECEIVE":
        raise RegionalFieldError("communication event is not dispatched to RECEIVE")
    if program[pc].get("target") != event.get("target_id"):
        raise RegionalFieldError("communication event target differs from RECEIVE target")
    target_id = _integer(event.get("target_id"), "communication target ID", minimum=1)
    target_ref = _resolve_object(flat, profile, target_id, right=RIGHT_WRITE)
    if int(_row_for_ref(flat, profile, target_ref)[D_KIND]) != KIND_VALUE:
        raise RegionalFieldError("communication target is not a writable value object")
    scope_ref = _resolve_object(
        flat, profile, _integer(event.get("scope_id"), "event scope ID", minimum=1),
        right=RIGHT_READ,
    )
    if int(_row_for_ref(flat, profile, scope_ref)[D_KIND]) != KIND_SCOPE:
        raise RegionalFieldError("field communication scope is not registered")


def communication_receive_dispatches(
    field: np.ndarray | PagedFieldImage,
    profile: RegionalProfile | None = None,
    catalog: KernelCatalog | None = None,
) -> tuple[dict[str, int], ...]:
    """Derive dispatches only from the image's registered root RECEIVE program."""
    if isinstance(field, PagedFieldImage):
        image = field
        if profile is not None and profile.fingerprint != image.profile.fingerprint:
            raise RegionalFieldError("paged RECEIVE dispatch profile differs from its image")
        profile = image.profile
        if catalog is not None and catalog.names != profile.kernel_names:
            raise RegionalFieldError("paged RECEIVE dispatch catalog differs from its profile")
        flat = image.view()
    elif isinstance(field, np.ndarray):
        if not isinstance(profile, RegionalProfile) or not isinstance(
            catalog, KernelCatalog
        ):
            raise RegionalFieldError(
                "dense RECEIVE dispatch lookup requires its profile and catalog"
            )
        validate_field(field, profile, catalog)
        flat = field.reshape(-1)
    else:
        raise RegionalFieldError("RECEIVE dispatch lookup requires a regional image")
    if profile is None:
        raise RegionalFieldError("RECEIVE dispatch image has no regional profile")
    program_ref = _descriptor_ref(flat, H_PROGRAM_CATALOG)
    scope_ref = _descriptor_ref(flat, H_ROOT_SCOPE)
    if program_ref is None or scope_ref is None:
        raise RegionalFieldError("registered root program or scope is missing")
    registry = _registry(flat, profile)[1]

    def registered_id(reference: RegionRef, name: str) -> int:
        matches = [
            int(object_id)
            for object_id, entry in registry["entries"].items()
            if entry.get("status") == "live"
            and RegionRef.from_dict(entry["reference"]).slot == reference.slot
            and RegionRef.from_dict(entry["reference"]).generation
            == reference.generation
        ]
        if len(matches) != 1:
            raise RegionalFieldError(
                f"registered root {name} identity is missing or ambiguous"
            )
        return matches[0]

    program_id = registered_id(program_ref, "program")
    scope_id = registered_id(scope_ref, "scope")
    program_row = _row_for_ref(flat, profile, program_ref, right=RIGHT_EXECUTE)
    scope_row = _row_for_ref(flat, profile, scope_ref, right=RIGHT_READ)
    if (
        int(program_row[D_KIND]) != KIND_PROGRAM
        or int(scope_row[D_KIND]) != KIND_SCOPE
        or int(program_row[D_SCOPE_ID]) != scope_id
    ):
        raise RegionalFieldError("registered root program or scope has the wrong kind")
    program = _program_for(flat, profile, program_id)
    queue = _read_region(flat, profile, _queue_ref(flat))
    named_values = queue.get("named_values")
    if not isinstance(named_values, Mapping):
        raise RegionalFieldError("registered RECEIVE targets have no named-value table")
    dispatches: list[dict[str, int]] = []
    targets: set[int] = set()
    for pc, instruction in enumerate(program):
        if instruction.get("op") != "RECEIVE":
            continue
        target_id = _integer(
            instruction.get("target"), "registered RECEIVE target", minimum=1
        )
        if target_id in targets:
            raise RegionalFieldError("registered RECEIVE targets are not distinct")
        targets.add(target_id)
        target_ref = _resolve_object(
            flat, profile, target_id, right=RIGHT_WRITE
        )
        target_row = _row_for_ref(flat, profile, target_ref)
        if (
            int(target_row[D_KIND]) != KIND_VALUE
            or int(target_row[D_SCOPE_ID]) != scope_id
            or target_id not in named_values.values()
        ):
            raise RegionalFieldError(
                "registered RECEIVE target is not a root-scoped named value"
            )
        dispatches.append(
            {
                "program_id": program_id,
                "scope_id": scope_id,
                "pc": pc,
                "site": 0,
                "target_id": target_id,
            }
        )
    return tuple(dispatches)
def _communication_event_in_queue(
    flat: Any, profile: RegionalProfile, event_id: int, intent_sha256: str,
) -> tuple[RegionRef, dict[str, Any], Mapping[str, Any] | None]:
    event_id = _integer(event_id, "communication event ID", minimum=1)
    if not isinstance(intent_sha256, str) or len(intent_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in intent_sha256
    ):
        raise RegionalFieldError("communication intent digest is invalid")
    queue_ref = _queue_ref(flat)
    queue = dict(_read_region(flat, profile, queue_ref))
    for event in queue["events"]:
        if int(event["event_id"]) != event_id:
            continue
        intent = _communication_intent_from_event(event)
        if intent is None or hashlib.sha256(_canonical(intent)).hexdigest() != intent_sha256:
            raise RegionalFieldError("communication event identity differs")
        return queue_ref, queue, event
    return queue_ref, queue, None


def communication_event_pending(
    field: np.ndarray | PagedFieldImage,
    profile: RegionalProfile,
    event_id: int,
    intent_sha256: str,
) -> bool:
    """Inspect an exact field-owned event without changing its continuation."""
    flat = field.view() if isinstance(field, PagedFieldImage) else field.reshape(-1)
    return _communication_event_in_queue(flat, profile, event_id, intent_sha256)[2] is not None


def _cancel_communication_flat(
    flat: Any, profile: RegionalProfile, event_id: int, intent_sha256: str,
) -> dict[str, Any]:
    queue_ref, queue, event = _communication_event_in_queue(
        flat, profile, event_id, intent_sha256,
    )
    if event is None:
        raise RegionalFieldError("communication event is no longer pending")
    if event["state"] not in {"ready", "waiting", "blocked"}:
        raise RegionalFieldError("communication event cannot be cancelled while active")
    clock = _read_u64(flat, H_CLOCK)
    if clock >= U64_MAX - 1 or clock >= profile.max_steps:
        raise RegionalFieldError("communication cancellation has no remaining transition capacity")
    queue["events"] = [
        item for item in queue["events"] if int(item["event_id"]) != event_id
    ]
    _write_region(flat, profile, queue_ref, queue)
    _write_u64(flat, H_CLOCK, clock + 1)
    _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
    flat[H_STATUS] = STATUS_RUNNING if queue["events"] else STATUS_WAITING
    flat[H_REASON] = REASON_NONE if queue["events"] else REASON_NO_READY_EVENT
    return {
        "kind": "communication-cancellation",
        "event_id": event_id,
        "intent_sha256": intent_sha256,
        "logical_transition": clock + 1,
    }


def cancel_communication_event(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    event_id: int,
    intent_sha256: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    validate_field(field, profile, catalog)
    before = state_sha256(field, profile)
    successor = np.array(field, copy=True, order="C")
    receipt = _cancel_communication_flat(
        successor.reshape(-1), profile, event_id, intent_sha256,
    )
    validate_field(successor, profile, catalog)
    return successor, {
        "schema": REGIONAL_SCHEMA, **receipt,
        "previous_state_sha256": before,
        "state_sha256": state_sha256(successor, profile),
    }


def cancel_communication_event_paged(
    image: PagedFieldImage,
    event_id: int,
    intent_sha256: str,
) -> tuple[PagedFieldImage, dict[str, Any]]:
    return _paged_flat_transition(
        image,
        lambda flat: _cancel_communication_flat(
            flat, image.profile, event_id, intent_sha256,
        ),
        stage="cancel-communication",
        record_audit_digest=False,
    )


def enqueue_event(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    event: Mapping[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    """Admit one external event as an explicit field transition."""

    validate_field(field, profile, catalog)
    before = state_sha256(field, profile)
    _validate_communication_event(
        field.reshape(-1), profile, event, root_sha256=before
    )
    mutable = np.array(field, copy=True, order="C")
    admitted, clock = _enqueue_event_flat(mutable.reshape(-1), profile, event)
    validate_field(mutable, profile, catalog)
    return mutable, {
        "schema": REGIONAL_SCHEMA,
        "kind": "event-admission",
        "event_id": admitted["event_id"],
        "logical_transition": clock + 1,
        "previous_state_sha256": before,
        "state_sha256": state_sha256(mutable, profile),
    }

def _write_named_value_flat(
    flat: np.ndarray,
    profile: RegionalProfile,
    name: str,
    value: Any,
) -> dict[str, Any]:
    """Publish one named value into a mutable flat image or staged view."""

    _identifier(name, "named value")
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
    return {
        "schema": REGIONAL_SCHEMA,
        "kind": "input-publication",
        "name": name,
        "changed": changed,
        "logical_transition": clock + 1,
    }

def _declare_named_value_flat(
    flat: np.ndarray,
    profile: RegionalProfile,
    name: str,
    value: Any,
    capacity_words: int,
) -> dict[str, Any]:
    """Allocate a new canonical named value as one bounded field transition."""
    name = _identifier(name, "named value")
    capacity_words = _integer(
        capacity_words, "named value capacity", minimum=1
    )
    words = _json_words(value)
    if len(words) > capacity_words:
        raise RegionalFieldError("named value exceeds its declared capacity")
    clock = _read_u64(flat, H_CLOCK)
    if clock >= U64_MAX - 1 or clock >= profile.max_steps:
        raise RegionalFieldError(
            "named-value migration has no remaining transition capacity"
        )
    queue_ref = _queue_ref(flat)
    queue = dict(_read_region(flat, profile, queue_ref))
    named_values = dict(queue.get("named_values", {}))
    if name in named_values:
        raise RegionalFieldError("named value is already declared")
    scope_ref = _descriptor_ref(flat, H_ROOT_SCOPE)
    if scope_ref is None:
        raise RegionalFieldError("root scope is missing")
    scope_id = int(_row_for_ref(flat, profile, scope_ref)[D_SCOPE_ID])
    _ref, object_id = _allocate_raw(
        flat,
        profile,
        kind=KIND_VALUE,
        codec=CODEC_JSON,
        value=value,
        capacity=capacity_words,
        scope_id=scope_id,
    )
    named_values[name] = object_id
    queue["named_values"] = named_values
    _write_region(flat, profile, queue_ref, queue)
    _write_u64(flat, H_CLOCK, clock + 1)
    _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
    return {
        "schema": REGIONAL_SCHEMA,
        "kind": "named-value-migration",
        "name": name,
        "object_id": object_id,
        "capacity_words": capacity_words,
        "used_words": len(words),
        "logical_transition": clock + 1,
    }


def declare_named_value(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    name: str,
    value: Any,
    capacity_words: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Add one reserved name without rebuilding or re-identifying the image."""
    validate_field(field, profile, catalog)
    before = state_sha256(field, profile)
    mutable = np.array(field, copy=True, order="C")
    detail = _declare_named_value_flat(
        mutable.reshape(-1), profile, name, value, capacity_words
    )
    validate_field(mutable, profile, catalog)
    return mutable, {
        **detail,
        "previous_state_sha256": before,
        "state_sha256": state_sha256(mutable, profile),
    }


def declare_named_value_paged(
    image: PagedFieldImage,
    name: str,
    value: Any,
    capacity_words: int,
    *,
    stage: str = "named-value-migration",
    record_audit_digest: bool = False,
) -> tuple[PagedFieldImage, dict[str, Any]]:
    """Add one named value through the normal bounded paged commit path."""
    return _paged_flat_transition(
        image,
        lambda flat: _declare_named_value_flat(
            flat, image.profile, name, value, capacity_words
        ),
        stage=stage,
        record_audit_digest=record_audit_digest,
    )




def write_named_value(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    name: str,
    value: Any,
    *,
    _input_validated: bool = False,
    _state_sha256: str | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Publish one host-lowered input as an explicit regional transition."""

    if not _input_validated:
        validate_field(field, profile, catalog)
    before = state_sha256(field, profile) if _state_sha256 is None else _state_sha256
    mutable = np.array(field, copy=True, order="C")
    detail = _write_named_value_flat(mutable.reshape(-1), profile, name, value)
    validate_field(mutable, profile, catalog)
    return mutable, {
        **detail,
        "previous_state_sha256": before,
        "state_sha256": state_sha256(mutable, profile),
    }
def _restart_flat(
    flat: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    *,
    entry: int,
    values: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Restart the admitted root program inside a mutable flat image or view."""

    entry = _integer(entry, "entry")
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
    return {
        "schema": REGIONAL_SCHEMA,
        "kind": "restart",
        "replaced_events": replaced,
        "logical_transition": clock + 1,
    }


def restart_field(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    *,
    entry: int = 0,
    values: Mapping[str, Any] | None = None,
    _input_validated: bool = False,
    _state_sha256: str | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Restart the admitted root program without resetting unrelated state."""

    if not _input_validated:
        validate_field(field, profile, catalog)
    before = state_sha256(field, profile) if _state_sha256 is None else _state_sha256
    mutable = np.array(field, copy=True, order="C")
    detail = _restart_flat(
        mutable.reshape(-1),
        profile,
        catalog,
        entry=entry,
        values=values,
    )
    validate_field(mutable, profile, catalog)
    return mutable, {
        **detail,
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
    old_flat = field.reshape(-1)
    clock = _read_u64(old_flat, H_CLOCK)
    if clock >= U64_MAX - 1 or clock + 1 > target_steps:
        raise RegionalFieldError("growth has no representable successor transition")
    old_directory = _directory(old_flat, profile)
    old_rows: list[tuple[int, np.ndarray, np.ndarray]] = []
    for index, row in enumerate(old_directory):
        flags = int(row[D_FLAGS])
        if not flags & (FLAG_LIVE | FLAG_QUARANTINED):
            continue
        capacity = int(row[D_CAPACITY])
        base = int(row[D_BASE])
        old_rows.append(
            (
                index,
                np.array(row, copy=True),
                np.array(old_flat[base:base + capacity], copy=True),
            )
        )
    successor = np.zeros(successor_profile.shape, dtype=np.float64)
    flat = successor.reshape(-1)
    flat[:HEADER_WORDS + DIRECTORY_WORDS * profile.directory_capacity] = (
        old_flat[:HEADER_WORDS + DIRECTORY_WORDS * profile.directory_capacity]
    )
    flat[H_TOTAL_WORDS] = successor_profile.total_words
    flat[H_PROFILE_SHA:H_PROFILE_SHA + 8] = _sha_words(
        successor_profile.fingerprint
    )
    arena_start = HEADER_WORDS + DIRECTORY_WORDS * profile.directory_capacity
    cursor = arena_start
    resized_regions: list[dict[str, int]] = []
    for index, row, payload in sorted(old_rows, key=lambda item: int(item[1][D_BASE])):
        old_capacity = int(row[D_CAPACITY])
        new_capacity = old_capacity
        if int(row[D_KIND]) == KIND_VALUE:
            if mode_count > profile.mode_count:
                new_capacity = max(
                    new_capacity,
                    (old_capacity * mode_count + profile.mode_count - 1)
                    // profile.mode_count,
                )
            used = int(row[D_USED])
            if used * 2 >= old_capacity:
                new_capacity = max(
                    new_capacity, old_capacity + max(4096, old_capacity // 4)
                )
        if cursor + new_capacity > successor_profile.workspace_words:
            raise RegionalFieldError("growth cannot fit relocated payload arena")
        flat[cursor:cursor + len(payload)] = payload
        row[D_BASE] = cursor
        row[D_CAPACITY] = new_capacity
        flat[
            HEADER_WORDS + index * DIRECTORY_WORDS:
            HEADER_WORDS + (index + 1) * DIRECTORY_WORDS
        ] = row
        if new_capacity != old_capacity:
            resized_regions.append(
                {
                    "slot": index + 1,
                    "kind": int(row[D_KIND]),
                    "old_capacity": old_capacity,
                    "new_capacity": new_capacity,
                }
            )
        cursor += new_capacity
    if profile.neural_membrane:
        old_planes = old_flat.reshape(9, profile.mode_count)
        new_planes = flat.reshape(9, successor_profile.mode_count)
        new_planes[
            NEURAL_MEMBRANE_FIRST_PLANE:,
            : profile.mode_count,
        ] = old_planes[NEURAL_MEMBRANE_FIRST_PLANE:, :]
    flat[H_FREE_CURSOR] = old_flat[H_FREE_CURSOR]
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
        "relocated_payload_words": int(sum(len(payload) for _, _, payload in old_rows)),
        "resized_regions": resized_regions,
    }

def enable_neural_membrane(
    field: np.ndarray,
    profile: RegionalProfile,
    catalog: KernelCatalog,
    *,
    minimum_modes: int,
    gain_ppm: int = NEURAL_MEMBRANE_DEFAULT_GAIN_PPM,
) -> tuple[RegionalProfile, np.ndarray, dict[str, Any]]:
    """Reserve four physical field planes without changing prior payload bytes."""

    validate_field(field, profile, catalog)
    minimum_modes = _integer(minimum_modes, "minimum membrane modes", minimum=1)
    gain_ppm = _integer(gain_ppm, "neural membrane gain", maximum=1_000_000)
    old_workspace = profile.workspace_words
    target_modes = max(
        minimum_modes,
        profile.mode_count if profile.neural_membrane else 0,
        (old_workspace + NEURAL_MEMBRANE_FIRST_PLANE - 1)
        // NEURAL_MEMBRANE_FIRST_PLANE,
    )
    target_modes = (
        (target_modes + NEURAL_MEMBRANE_MODE_QUANTUM - 1)
        // NEURAL_MEMBRANE_MODE_QUANTUM
        * NEURAL_MEMBRANE_MODE_QUANTUM
    )
    if (
        profile.neural_membrane
        and target_modes == profile.mode_count
        and gain_ppm == profile.neural_membrane_gain_ppm
    ):
        raise RegionalFieldError("neural membrane already satisfies the request")
    successor_profile = replace(
        profile,
        mode_count=target_modes,
        neural_membrane=True,
        neural_membrane_gain_ppm=gain_ppm,
    )
    if successor_profile.workspace_words < old_workspace:
        raise RegionalFieldError("neural membrane migration would discard workspace")
    old_flat = field.reshape(-1)
    clock = _read_u64(old_flat, H_CLOCK)
    if clock >= U64_MAX - 1 or clock + 1 > successor_profile.max_steps:
        raise RegionalFieldError(
            "neural membrane migration has no representable successor transition"
        )
    successor = np.zeros(successor_profile.shape, dtype=np.float64)
    flat = successor.reshape(-1)
    flat[:old_workspace] = old_flat[:old_workspace]
    preserved_membrane_words = 0
    if profile.neural_membrane:
        old_planes = old_flat.reshape(9, profile.mode_count)
        new_planes = flat.reshape(9, successor_profile.mode_count)
        new_planes[
            NEURAL_MEMBRANE_FIRST_PLANE:,
            :profile.mode_count,
        ] = old_planes[NEURAL_MEMBRANE_FIRST_PLANE:, :]
        preserved_membrane_words = profile.neural_membrane_words
    flat[H_TOTAL_WORDS] = successor_profile.total_words
    flat[H_PROFILE_SHA:H_PROFILE_SHA + 8] = _sha_words(
        successor_profile.fingerprint
    )
    _write_u64(flat, H_CLOCK, clock + 1)
    _write_u64(flat, H_BASE_EPOCH, _read_u64(old_flat, H_BASE_EPOCH) + 1)
    validate_field(successor, successor_profile, catalog)
    return successor_profile, successor, {
        "schema": NEURAL_MEMBRANE_SCHEMA,
        "kind": "enable-neural-membrane",
        "old_profile_sha256": profile.fingerprint,
        "profile_sha256": successor_profile.fingerprint,
        "previous_state_sha256": state_sha256(field, profile),
        "state_sha256": state_sha256(successor, successor_profile),
        "logical_transition": clock + 1,
        "workspace_words_preserved": old_workspace,
        "membrane_words_preserved": preserved_membrane_words,
        "membrane_modes": successor_profile.mode_count,
        "membrane_gain_ppm": gain_ppm,
    }


def neural_membrane_planes(
    field: np.ndarray,
    profile: RegionalProfile,
    *,
    copy_planes: bool = False,
) -> np.ndarray:
    """Return the four exact u32-backed membrane planes."""

    if not profile.neural_membrane:
        raise RegionalFieldError("regional profile has no neural membrane")
    if (
        not isinstance(field, np.ndarray)
        or field.dtype != np.float64
        or field.shape != profile.shape
    ):
        raise RegionalFieldError("regional field shape or dtype is invalid")
    planes = field.reshape(9, profile.mode_count)[
        NEURAL_MEMBRANE_FIRST_PLANE:,
        :,
    ]
    return np.array(planes, copy=True) if copy_planes else planes


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


def read_bound_object_refs(
    field: np.ndarray | "_PagedFieldView",
    profile: RegionalProfile,
    input_refs: list[Mapping[str, Any]],
) -> dict[int, Any]:
    """Resolve bounded object refs against the current field and verify content.

    Each reference binds a registry version and digest. JSON values use their
    canonical encoding; raw u32 objects use the packed little-endian bytes
    that the resident native image exposes at their directory word range.
    """

    if not isinstance(input_refs, list) or len(input_refs) > 32:
        raise RegionalFieldError("bound object references must be a list of at most 32")
    if not isinstance(profile, RegionalProfile):
        raise RegionalFieldError("bound object profile is invalid")
    if isinstance(field, np.ndarray):
        if (
            field.dtype != np.float64
            or field.shape != profile.shape
            or not field.flags.c_contiguous
        ):
            raise RegionalFieldError("regional field shape or dtype is invalid")
        flat: Any = field.reshape(-1)
    elif isinstance(field, _PagedFieldView):
        if field._image.profile.fingerprint != profile.fingerprint:
            raise RegionalFieldError("paged field profile is stale")
        flat = field
    else:
        raise RegionalFieldError("regional field source is invalid")

    result: dict[int, Any] = {}
    previous_id = 0
    expected_keys = {"object_id", "object_version", "source_sha256"}
    for index, reference in enumerate(input_refs):
        if not isinstance(reference, Mapping) or set(reference) != expected_keys:
            raise RegionalFieldError(
                f"bound object reference {index} has an invalid shape"
            )
        object_id = _integer(
            reference["object_id"], "bound object ID", minimum=1
        )
        if object_id <= previous_id:
            raise RegionalFieldError(
                "bound object references must be sorted and unique"
            )
        previous_id = object_id
        expected_version = _integer(
            reference["object_version"],
            "bound object version",
            minimum=1,
            maximum=U64_MAX,
        )
        expected_digest = reference["source_sha256"]
        if (
            not isinstance(expected_digest, str)
            or len(expected_digest) != 64
            or any(char not in "0123456789abcdef" for char in expected_digest)
        ):
            raise RegionalFieldError("bound object digest is invalid")

        ref = _resolve_object(flat, profile, object_id, right=RIGHT_READ)
        row = _row_for_ref(flat, profile, ref, right=RIGHT_READ)
        if _read_u64(row, D_VERSION) != expected_version:
            raise RegionalFieldError("bound object version is stale")
        value = _read_region(flat, profile, ref)
        digest = hashlib.sha256(
            np.asarray(value, dtype="<u4").tobytes()
            if int(row[D_CODEC]) == CODEC_WORDS else _canonical(value)
        ).hexdigest()
        if digest != expected_digest:
            raise RegionalFieldError("bound object digest is stale")
        result[object_id] = value
    return result

def bound_u32_range(
    field: np.ndarray | "_PagedFieldView",
    profile: RegionalProfile,
    reference: Mapping[str, Any],
) -> tuple[int, int]:
    """Reverify one bound raw-u32 object and locate it in the canonical image."""
    values = read_bound_object_refs(
        field.reshape(profile.shape) if isinstance(field, np.ndarray) else field,
        profile, [reference],
    )
    object_id = int(reference["object_id"])
    if object_id not in values or not values[object_id]:
        raise RegionalFieldError("bound u32 array must contain at least one word")
    flat = field.reshape(-1) if isinstance(field, np.ndarray) else field
    ref = _resolve_object(flat, profile, object_id, right=RIGHT_READ)
    row = _row_for_ref(flat, profile, ref, right=RIGHT_READ)
    if int(row[D_KIND]) != KIND_VALUE or int(row[D_CODEC]) != CODEC_WORDS:
        raise RegionalFieldError("bound object is not a raw u32 value")
    return int(row[D_BASE]), int(row[D_USED])


def prefetch_bound_object_refs(
    image: "PagedFieldImage",
    profile: RegionalProfile,
    input_refs: Sequence[Mapping[str, Any]],
    *,
    limit: int = 4,
) -> dict[str, Any]:
    """Prefetch exact clean pages for bounded, versioned object references.

    This validates each referenced object and version in the committed image,
    then binds the selected data pages to its exact root and page generations.
    Content digests remain checked by the consumer's ordinary bound read.
    """

    if not isinstance(image, PagedFieldImage):
        raise RegionalFieldError("bound prefetch requires a paged image")
    if not isinstance(profile, RegionalProfile):
        raise RegionalFieldError("bound prefetch profile is invalid")
    if image.profile.fingerprint != profile.fingerprint:
        raise RegionalFieldError("paged field profile is stale")
    limit = _integer(
        limit, "prefetch page limit", minimum=1, maximum=MAX_PREFETCH_PAGES
    )
    if (
        isinstance(input_refs, (str, bytes))
        or not isinstance(input_refs, Sequence)
        or len(input_refs) > 32
    ):
        raise RegionalFieldError("bound object references must be a sequence of at most 32")
    flat = image.view(track_prefetch_use=False)
    object_ids: list[int] = []
    pages: list[int] = []
    seen_pages: set[int] = set()
    previous_id = 0
    expected_keys = {"object_id", "object_version", "source_sha256"}
    for offset, reference in enumerate(input_refs):
        if not isinstance(reference, Mapping) or set(reference) != expected_keys:
            raise RegionalFieldError(
                f"bound object reference {offset} has an invalid shape"
            )
        object_id = _integer(reference["object_id"], "bound object ID", minimum=1)
        if object_id <= previous_id:
            raise RegionalFieldError(
                "bound object references must be sorted and unique"
            )
        previous_id = object_id
        expected_version = _integer(
            reference["object_version"],
            "bound object version",
            minimum=1,
            maximum=U64_MAX,
        )
        expected_digest = reference["source_sha256"]
        if (
            not isinstance(expected_digest, str)
            or len(expected_digest) != 64
            or any(char not in "0123456789abcdef" for char in expected_digest)
        ):
            raise RegionalFieldError("bound object digest is invalid")
        ref = _resolve_object(flat, profile, object_id, right=RIGHT_READ)
        row = _row_for_ref(flat, profile, ref, right=RIGHT_READ)
        if _read_u64(row, D_VERSION) != expected_version:
            raise RegionalFieldError("bound object version is stale")
        start = int(row[D_BASE])
        used = int(row[D_USED])
        if used < 0 or start < 0 or start + used > profile.total_words:
            raise RegionalFieldError("bound object range is invalid")
        object_ids.append(object_id)
        if used:
            first = start // PERSISTENCE_PAGE_WORDS
            last = (start + used - 1) // PERSISTENCE_PAGE_WORDS
            for page_index in range(first, last + 1):
                if page_index in seen_pages:
                    continue
                if len(pages) >= limit:
                    break
                seen_pages.add(page_index)
                pages.append(page_index)
    receipt = image.prefetch_pages(
        image.page_read_hint(pages),
        max_pages=limit,
    )
    receipt["bound_object_ids"] = object_ids
    return receipt


def materialize_bound_values(
    field: np.ndarray | "_PagedFieldView",
    profile: RegionalProfile,
    values: Mapping[str, Any],
    *,
    u32_words: Sequence[str] = (),
) -> dict[str, dict[str, Any]]:
    """Allocate immutable-snapshot value objects in a regional root scope.

    The returned object references bind each regional object ID to its initial
    version and canonical value digest. Callers must execute against the
    successor field containing these allocations.
    """
    if not isinstance(values, Mapping) or not 1 <= len(values) <= 32:
        raise RegionalFieldError("bound values must contain 1..32 entries")
    if isinstance(u32_words, (str, bytes)) or not isinstance(u32_words, Sequence):
        raise RegionalFieldError("raw u32 bound names must be a sequence")
    names = set(u32_words)
    if len(names) != len(u32_words) or not names <= set(values) or not all(
        isinstance(name, str) for name in names
    ):
        raise RegionalFieldError("raw u32 bound names must uniquely identify bound values")
    if isinstance(field, np.ndarray):
        if (
            field.dtype != np.float64
            or field.shape != profile.shape
            or not field.flags.c_contiguous
        ):
            raise RegionalFieldError("regional field shape or dtype is invalid")
        flat: Any = field.reshape(-1)
    elif isinstance(field, _PagedFieldView):
        if field._image.profile.fingerprint != profile.fingerprint:
            raise RegionalFieldError("paged field profile is stale")
        flat = field
    else:
        raise RegionalFieldError("regional field source is invalid")

    scope_ref = _descriptor_ref(flat, H_ROOT_SCOPE)
    if scope_ref is None:
        raise RegionalFieldError("regional image has no root scope")
    _registry_ref, registry = _registry(flat, profile)
    root_scope_id = next(
        (
            int(object_id)
            for object_id, entry in registry.get("entries", {}).items()
            if isinstance(entry, Mapping)
            and entry.get("status") == "live"
            and entry.get("reference") == scope_ref.as_dict()
        ),
        None,
    )
    if root_scope_id is None:
        raise RegionalFieldError("regional root scope has no registered identity")
    result: dict[str, dict[str, Any]] = {}
    for name in sorted(values):
        _identifier(name, "bound value name")
        value = values[name]
        encoded = _canonical(value)
        if len(encoded) > 1024 * 1024:
            raise RegionalFieldError("bound value exceeds its size bound")
        raw = name in names
        if raw:
            if not isinstance(value, (list, tuple)) or not value or any(
                isinstance(word, bool) or not isinstance(word, int)
                or word < 0 or word > U32_MAX for word in value
            ):
                raise RegionalFieldError("raw u32 bound value must be a nonempty u32 array")
            words = tuple(value)
            digest = hashlib.sha256(np.asarray(words, dtype="<u4").tobytes()).hexdigest()
        else:
            words = _json_words(value)
            digest = hashlib.sha256(encoded).hexdigest()
        ref, object_id = _allocate_raw(
            flat,
            profile,
            kind=KIND_VALUE,
            codec=CODEC_WORDS if raw else CODEC_JSON,
            value=value,
            capacity=max(1, len(words)),
            scope_id=root_scope_id,
        )
        row = _row_for_ref(flat, profile, ref, right=RIGHT_READ)
        result[name] = {
            "object_id": object_id,
            "object_version": _read_u64(row, D_VERSION),
            "region_ref": ref.as_dict(),
            "source_sha256": digest,
            **({
                "codec": "u32-words",
                "first_word": int(row[D_BASE]),
                "word_count": int(row[D_USED]),
            } if raw else {}),
        }
    return result


BOUND_METHOD_SCHEMA = "cassifi.regional-bound-method.v1"

_VETTED_REGIONAL_OPS = frozenset((
    "identity", "constant", "add", "subtract", "multiply", "divide",
    "negate", "absolute", "equal", "less_equal", "convert", "vector",
))


def _regional_method_number(value: Any, label: str) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RegionalFieldError(f"{label} must be a finite number")
    if isinstance(value, float) and not math.isfinite(value):
        raise RegionalFieldError(f"{label} must be a finite number")
    return value


def _regional_port_value(value: Any, port_name: str, value_kind: str) -> Any:
    if value_kind == "scalar":
        return _regional_method_number(
            value, f"regional method port {port_name} value"
        )
    if value_kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise RegionalFieldError(
                f"regional method port {port_name} requires an integer"
            )
        return value
    if value_kind == "boolean":
        if not isinstance(value, bool):
            raise RegionalFieldError(
                f"regional method port {port_name} requires a boolean"
            )
        return value
    if value_kind in ("vector", "sequence"):
        if isinstance(value, tuple):
            value = list(value)
        if not isinstance(value, list) or len(value) > 256:
            raise RegionalFieldError(
                f"regional method port {port_name} requires a bounded list"
            )
        return [
            _regional_method_number(
                item, f"regional method port {port_name} element"
            )
            for item in value
        ]
    raise RegionalFieldError(
        f"regional method port {port_name} value_kind {value_kind} is not supported near data"
    )


def _regional_json_value(value: Any, label: str) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RegionalFieldError(f"{label} must be finite")
    elif isinstance(value, list):
        for item in value:
            _regional_json_value(item, label)
    elif not isinstance(value, (int, str, bool)) and value is not None:
        raise RegionalFieldError(f"{label} is not canonical regional JSON")
    return value


def _regional_root_scope(flat: Any, profile: RegionalProfile) -> int:
    """Resolve the registered object ID of the image's root scope."""

    scope_ref = _descriptor_ref(flat, H_ROOT_SCOPE)
    if scope_ref is None:
        raise RegionalFieldError("regional image has no root scope")
    _registry_ref, registry = _registry(flat, profile)
    root_scope_id = next(
        (
            int(object_id)
            for object_id, entry in registry.get("entries", {}).items()
            if isinstance(entry, Mapping)
            and entry.get("status") == "live"
            and entry.get("reference") == scope_ref.as_dict()
        ),
        None,
    )
    if root_scope_id is None:
        raise RegionalFieldError("regional root scope has no registered identity")
    return root_scope_id


def _regional_method_output(
    executable_method: Mapping[str, Any],
    bindings: Mapping[str, Any],
) -> tuple[str, Any, int, int]:
    """Evaluate one vetted Hive ExecutableMethod exactly as its host path does.

    Returns the output port name, output value, step count, and declared work
    bound. Arithmetic mirrors ``FieldProgram.execute`` operation by operation;
    operations outside the vetted regional set are rejected, not emulated.
    """

    from cassi_hive_collective import CollectiveHiveError, ExecutableMethod

    try:
        method = ExecutableMethod.from_dict(dict(executable_method))
    except CollectiveHiveError as exc:
        raise RegionalFieldError(str(exc)) from exc
    program = method.program
    interface = method.interface
    if len(interface.outputs) != 1:
        raise RegionalFieldError(
            "regional bound method must produce exactly one output"
        )
    if not program.steps or len(program.steps) > 256:
        raise RegionalFieldError("regional bound method program is unbounded")
    for step in program.steps:
        if step.operation not in _VETTED_REGIONAL_OPS:
            raise RegionalFieldError(
                f"regional bound method operation {step.operation} "
                "is not supported near data"
            )
    expected_inputs = {port.name for port in interface.inputs}
    if not isinstance(bindings, Mapping) or set(bindings) != expected_inputs:
        raise RegionalFieldError(
            "regional bound method bindings must cover its inputs exactly"
        )
    values: dict[str, Any] = {}
    for port in interface.inputs:
        values[port.symbol] = _regional_port_value(
            bindings[port.name], port.name, port.value_kind
        )
    for step in program.steps:
        args = [values[name] for name in step.inputs]
        try:
            if step.operation == "identity":
                result = args[0]
            elif step.operation == "constant":
                result = step.literal
            elif step.operation == "add":
                result = args[0] + args[1]
            elif step.operation == "subtract":
                result = args[0] - args[1]
            elif step.operation == "multiply":
                result = args[0] * args[1]
            elif step.operation == "divide":
                if args[1] == 0:
                    raise RegionalFieldError("regional bound method divides by zero")
                result = args[0] / args[1]
            elif step.operation == "negate":
                result = -args[0]
            elif step.operation == "absolute":
                result = abs(args[0])
            elif step.operation == "equal":
                result = args[0] == args[1]
            elif step.operation == "less_equal":
                result = args[0] <= args[1]
            elif step.operation == "vector":
                result = list(args)
            elif step.operation == "convert":
                result = args[0] * float(step.literal)
            else:  # pragma: no cover - the vetted set is closed
                raise AssertionError("vetted regional primitive")
        except (TypeError, ValueError, OverflowError) as exc:
            raise RegionalFieldError(
                f"regional primitive {step.operation} rejected its inputs"
            ) from exc
        values[step.output] = _regional_json_value(result, step.output)
    output_port = interface.outputs[0]
    output = _regional_port_value(
        values[output_port.symbol], output_port.name, output_port.value_kind
    )
    return output_port.name, output, len(program.steps), int(method.maximum_work)


def _regional_bound_execution_flat(
    field: Any,
    profile: RegionalProfile,
    *,
    executable_method: Mapping[str, Any],
    input_refs: list[Mapping[str, Any]],
    input_bindings: Mapping[str, Any],
    method_id: str,
    method_generation: int,
    method_source_sha256: str,
    program_sha256: str,
) -> dict[str, Any]:
    """Resolve, evaluate, and allocate one bound method over a flat image."""

    if isinstance(field, np.ndarray):
        if (
            field.dtype != np.float64
            or field.shape != profile.shape
            or not field.flags.c_contiguous
        ):
            raise RegionalFieldError("regional field shape or dtype is invalid")
        flat: Any = field.reshape(-1)
    elif isinstance(field, _PagedFieldView):
        if field._image.profile.fingerprint != profile.fingerprint:
            raise RegionalFieldError("paged field profile is stale")
        flat = field
    else:
        raise RegionalFieldError("regional field source is invalid")
    resolved = read_bound_object_refs(field, profile, input_refs)
    bindings: dict[str, Any] = {}
    for name, object_id in sorted(input_bindings.items()):
        _identifier(name, "bound method input name")
        if isinstance(object_id, bool) or not isinstance(object_id, int) or object_id < 1:
            raise RegionalFieldError("bound method object_id is invalid")
        if object_id not in resolved:
            raise RegionalFieldError(
                "bound method input binding is not part of the exact references"
            )
        bindings[name] = resolved[object_id]
    output_name, output_value, steps, maximum_work = _regional_method_output(
        executable_method, bindings
    )
    root_scope_id = _regional_root_scope(flat, profile)
    encoded = _canonical(output_value)
    if len(encoded) > 1024 * 1024:
        raise RegionalFieldError("bound method output exceeds its size bound")
    words = _json_words(output_value)
    ref, object_id = _allocate_raw(
        flat,
        profile,
        kind=KIND_VALUE,
        codec=CODEC_JSON,
        value=output_value,
        capacity=max(1, len(words)),
        scope_id=root_scope_id,
    )
    row = _row_for_ref(flat, profile, ref, right=RIGHT_READ)
    clock = _read_u64(flat, H_CLOCK)
    if clock >= U64_MAX - 1 or clock >= profile.max_steps:
        raise RegionalFieldError(
            "bound method execution has no remaining transition capacity"
        )
    _write_u64(flat, H_CLOCK, clock + 1)
    _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
    return {
        "kind": "bound-method-execution",
        "method_id": method_id,
        "method_generation": int(method_generation),
        "method_source_sha256": method_source_sha256,
        "program_sha256": program_sha256,
        "input_bindings": dict(input_bindings),
        "value": output_value,
        "output_port": output_name,
        "output_object_refs": [
            {
                "object_id": object_id,
                "object_version": _read_u64(row, D_VERSION),
                "source_sha256": hashlib.sha256(encoded).hexdigest(),
            }
        ],
        "output_regions": [
            {
                "object_id": object_id,
                "object_version": _read_u64(row, D_VERSION),
                "region_ref": ref.as_dict(),
                "source_sha256": hashlib.sha256(encoded).hexdigest(),
                "port": output_name,
            }
        ],
        "work": {"steps": steps, "maximum_work": maximum_work},
        "logical_transition": clock + 1,
    }


def execute_regional_bound_method(
    source: np.ndarray | PagedFieldImage,
    profile: RegionalProfile,
    *,
    executable_method: Mapping[str, Any],
    input_refs: list[Mapping[str, Any]],
    input_bindings: Mapping[str, Any],
    method_id: str,
    method_generation: int,
    method_source_sha256: str,
    program_sha256: str,
    stage: str = "bound-method-execution",
    record_audit_digest: bool = False,
) -> tuple[np.ndarray | PagedFieldImage, dict[str, Any]]:
    """Lower one vetted Hive method onto its bound regional field near data.

    Inputs are resolved from the exact bound object references (version and
    digest verified), the program is evaluated in place, and the output is
    published as new regional value objects inside the same successor
    transition.  Dense fields are copied; paged images go through the normal
    staged, canonically validated commit path.
    """

    if not isinstance(profile, RegionalProfile):
        raise RegionalFieldError("bound method profile is invalid")
    arguments = {
        "executable_method": executable_method,
        "input_refs": input_refs,
        "input_bindings": input_bindings,
        "method_id": method_id,
        "method_generation": method_generation,
        "method_source_sha256": method_source_sha256,
        "program_sha256": program_sha256,
    }
    if isinstance(source, PagedFieldImage):
        if source.profile.fingerprint != profile.fingerprint:
            raise RegionalFieldError("paged field profile is stale")
        successor, receipt = _paged_flat_transition(
            source,
            lambda flat: _regional_bound_execution_flat(flat, profile, **arguments),
            stage=stage,
            record_audit_digest=record_audit_digest,
        )
        return successor, receipt
    if (
        not isinstance(source, np.ndarray)
        or source.dtype != np.float64
        or source.shape != profile.shape
        or not source.flags.c_contiguous
    ):
        raise RegionalFieldError("regional field shape or dtype is invalid")
    before = state_sha256(source, profile)
    mutable = np.array(source, copy=True, order="C")
    receipt = _regional_bound_execution_flat(
        mutable, profile, **arguments
    )
    return mutable, {
        **receipt,
        "previous_state_sha256": before,
        "state_sha256": state_sha256(mutable, profile),
    }


def publish_bound_native_sum(
    source: np.ndarray | PagedFieldImage,
    profile: RegionalProfile,
    *,
    input_ref: Mapping[str, Any],
    value: int,
    method_id: str,
    method_generation: int,
    method_source_sha256: str,
) -> tuple[np.ndarray | PagedFieldImage, dict[str, Any]]:
    """Publish a verified native u32 reduction as one regional successor."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= U64_MAX:
        raise RegionalFieldError("native sum must be a u64")
    def advance(flat: Any) -> dict[str, Any]:
        first_word, count = bound_u32_range(flat, profile, input_ref)
        encoded = _canonical(value)
        ref, object_id = _allocate_raw(
            flat, profile, kind=KIND_VALUE, codec=CODEC_JSON, value=value,
            capacity=len(_json_words(value)),
            scope_id=_regional_root_scope(flat, profile),
        )
        row = _row_for_ref(flat, profile, ref, right=RIGHT_READ)
        clock = _read_u64(flat, H_CLOCK)
        if clock >= U64_MAX - 1 or clock >= profile.max_steps:
            raise RegionalFieldError("native sum has no remaining transition capacity")
        _write_u64(flat, H_CLOCK, clock + 1)
        _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
        output = {
            "object_id": object_id,
            "object_version": _read_u64(row, D_VERSION),
            "source_sha256": hashlib.sha256(encoded).hexdigest(),
        }
        return {
            "kind": "bound-method-execution",
            "method_id": method_id,
            "method_generation": method_generation,
            "method_source_sha256": method_source_sha256,
            "input_range": {"first_word": first_word, "count": count},
            "value": value,
            "output_port": "sum",
            "output_object_refs": [output],
            "output_regions": [{**output, "region_ref": ref.as_dict(), "port": "sum"}],
            "work": {"steps": count, "maximum_work": count},
            "logical_transition": clock + 1,
        }
    if isinstance(source, PagedFieldImage):
        if source.profile.fingerprint != profile.fingerprint:
            raise RegionalFieldError("paged field profile is stale")
        return _paged_flat_transition(
            source, advance, stage="bound-native-sum",
            record_audit_digest=False,
        )
    if not isinstance(source, np.ndarray) or source.dtype != np.float64 or source.shape != profile.shape or not source.flags.c_contiguous:
        raise RegionalFieldError("regional field shape or dtype is invalid")
    before = state_sha256(source, profile)
    mutable = np.array(source, copy=True, order="C")
    receipt = advance(mutable.reshape(-1))
    return mutable, {
        **receipt,
        "previous_state_sha256": before,
        "state_sha256": state_sha256(mutable, profile),
    }


def bind_regional_method_values(
    source: np.ndarray | PagedFieldImage,
    profile: RegionalProfile,
    *,
    values: Mapping[str, Any],
    u32_words: Sequence[str] = (),
    stage: str = "bound-input-binding",
    record_audit_digest: bool = False,
) -> tuple[np.ndarray | PagedFieldImage, dict[str, Any]]:
    """Allocate immutable bound input objects as one explicit regional transition.

    Returns the successor field and the exact object references
    ``{object_id, object_version, region_ref, source_sha256}`` per name, the
    legal currency for ``FieldIntent`` input bindings.
    """

    if not isinstance(profile, RegionalProfile):
        raise RegionalFieldError("bound value profile is invalid")
    if isinstance(source, PagedFieldImage):
        if source.profile.fingerprint != profile.fingerprint:
            raise RegionalFieldError("paged field profile is stale")

        def operation(flat: Any) -> dict[str, Any]:
            rows = materialize_bound_values(flat, profile, values, u32_words=u32_words)
            clock = _read_u64(flat, H_CLOCK)
            if clock >= U64_MAX - 1 or clock >= profile.max_steps:
                raise RegionalFieldError(
                    "bound input binding has no remaining transition capacity"
                )
            _write_u64(flat, H_CLOCK, clock + 1)
            _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
            return {
                "kind": "bound-input-binding",
                "objects": rows,
                "logical_transition": clock + 1,
            }

        successor, receipt = _paged_flat_transition(
            source,
            operation,
            stage=stage,
            record_audit_digest=record_audit_digest,
        )
        return successor, receipt
    if (
        not isinstance(source, np.ndarray)
        or source.dtype != np.float64
        or source.shape != profile.shape
        or not source.flags.c_contiguous
    ):
        raise RegionalFieldError("regional field shape or dtype is invalid")
    before = state_sha256(source, profile)
    mutable = np.array(source, copy=True, order="C")
    rows = materialize_bound_values(mutable, profile, values, u32_words=u32_words)
    flat = mutable.reshape(-1)
    clock = _read_u64(flat, H_CLOCK)
    if clock >= U64_MAX - 1 or clock >= profile.max_steps:
        raise RegionalFieldError(
            "bound input binding has no remaining transition capacity"
        )
    _write_u64(flat, H_CLOCK, clock + 1)
    _write_u64(flat, H_BASE_EPOCH, _read_u64(flat, H_BASE_EPOCH) + 1)
    return mutable, {
        "kind": "bound-input-binding",
        "objects": rows,
        "logical_transition": clock + 1,
        "previous_state_sha256": before,
        "state_sha256": state_sha256(mutable, profile),
    }




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
    *,
    _input_validated: bool = False,
) -> dict[str, Any]:
    """Read several named values through one validated field snapshot."""

    if not _input_validated:
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


# ---------------------------------------------------------------------------
# Versioned page directory, bounded residency, and page-aware execution.
#
# The logical image remains one validated regional field.  The physical layer
# is an ordered page directory over immutable content-addressed chunks, so
# instructions, reductions, and publication operate on bounded views, stage
# private dirty pages, and suspend on absent residency with a typed wait
# instead of materialising the complete image.
# ---------------------------------------------------------------------------

PAGE_TREE_SCHEMA = "cassifi.regional-page-tree.v1"
PAGED_MANIFEST_SCHEMA = "cassifi.regional-paged-manifest.v1"
LAYOUT_MIGRATION_SCHEMA = "cassifi.regional-layout-migration.v1"
RESIDENCY_WAIT_SCHEMA = "cassifi.regional-residency-wait.v1"
RESIDENCY_CONTINUATION_SCHEMA = "cassifi.regional-residency-continuation.v1"
DEFAULT_RESIDENT_PAGES = 24
DEFAULT_DIRTY_PAGES = 24
MAX_RESIDENCY_PAGES = 65_536
MAX_PREFETCH_PAGES = 8
PAGE_READ_HINT_SCHEMA = "cassifi.regional-page-read-hint.v1"
PAGE_PREFETCH_SCHEMA = "cassifi.regional-page-prefetch.v1"
PAGE_SEGMENTS = (
    "control",
    "registry",
    "queue",
    "programs",
    "stacks",
    "automaton",
    "ledger",
    "continuation",
    "values",
    "quarantine",
)
CONTROL_CLOSURE_SEGMENTS = (
    "control",
    "registry",
    "queue",
    "programs",
    "stacks",
    "automaton",
    "ledger",
    "continuation",
)


class ResidencyWait(Exception):
    """A bounded view needs pages that are not currently resident.

    This is a typed wait in the continuation machinery, not a fault: the
    requesting instruction, the exact page identities, the authority scope,
    completed work, the remaining allowance, and the private successor
    references travel with it.
    """

    def __init__(
        self,
        stage: str,
        pages: Sequence[int],
        *,
        versions: Sequence[str] = (),
        scope: int = 0,
        work: int = 0,
        allowance: int | None = None,
        private_pages: Sequence[int] = (),
        reason: str = "absent",
        segments: Sequence[str] = (),
    ) -> None:
        indices = tuple(sorted({int(index) for index in pages}))
        self.stage = str(stage)
        self.pages = indices
        self.versions = tuple(str(version) for version in versions)
        self.scope = int(scope)
        self.work = int(work)
        self.allowance = None if allowance is None else int(allowance)
        self.private_pages = tuple(sorted({int(index) for index in private_pages}))
        self.reason = str(reason)
        self.segments = tuple(sorted({str(name) for name in segments}))
        super().__init__(
            f"regional pages {list(indices)} are not resident for {self.stage}"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": RESIDENCY_WAIT_SCHEMA,
            "kind": "residency-wait",
            "stage": self.stage,
            "pages": list(self.pages),
            "page_versions": list(self.versions),
            "authority_scope": self.scope,
            "completed_work": self.work,
            "remaining_allowance": self.allowance,
            "private_pages": list(self.private_pages),
            "segments": list(self.segments),
            "reason": self.reason,
        }


class PageUnavailable(RegionalFieldError):
    """A required object is missing, corrupt, revoked, or unsupported."""

    def __init__(self, kind: str, detail: str, *, pages: Sequence[int] = ()) -> None:
        self.kind = str(kind)
        self.pages = tuple(sorted({int(index) for index in pages}))
        self.detail = str(detail)
        super().__init__(f"regional page {self.kind}: {self.detail}")


_LEAF_DIGEST_CACHE_LIMIT = 262_144
_LEAF_DIGESTS: dict[tuple[Any, ...], str] = {}


@dataclass(frozen=True, slots=True)
class PageLeaf:
    """One committed nonzero page: logical placement and content identity."""

    index: int
    start_word: int
    words: int
    codec: str = PERSISTENCE_CHUNK_CODEC
    decoded_bytes: int = 0
    decoded_sha256: str = ""
    object_bytes: int = 0
    object_sha256: str = ""

    def __post_init__(self) -> None:
        _integer(self.index, "page index")
        _integer(self.start_word, "page start word")
        _integer(self.words, "page words", minimum=1)
        if self.codec != PERSISTENCE_CHUNK_CODEC:
            raise RegionalFieldError("regional page codec is unsupported")
        if self.decoded_bytes != self.words * 4:
            raise RegionalFieldError("regional page decoded length is invalid")
        for name in ("decoded_sha256", "object_sha256"):
            digest = getattr(self, name)
            if not isinstance(digest, str) or len(digest) != 64:
                raise RegionalFieldError("regional page digest is invalid")
        _integer(self.object_bytes, "page object bytes", minimum=1)

    def as_record(self) -> dict[str, Any]:
        return {
            "codec": self.codec,
            "decoded_bytes": self.decoded_bytes,
            "decoded_sha256": self.decoded_sha256,
            "index": self.index,
            "object_bytes": self.object_bytes,
            "object_sha256": self.object_sha256,
            "start_word": self.start_word,
            "words": self.words,
        }

    @property
    def digest(self) -> str:
        """Content identity of this leaf.

        A leaf is immutable and content-addressed, and every bounded step of a
        paged image re-derives the digest of every live page, so the value is
        memoised by the leaf's own identity fields.
        """

        key = (
            self.index,
            self.start_word,
            self.words,
            self.codec,
            self.decoded_bytes,
            self.decoded_sha256,
            self.object_bytes,
            self.object_sha256,
        )
        cached = _LEAF_DIGESTS.get(key)
        if cached is not None:
            return cached
        digest = hashlib.sha256(_canonical(self.as_record())).hexdigest()
        if len(_LEAF_DIGESTS) >= _LEAF_DIGEST_CACHE_LIMIT:
            _LEAF_DIGESTS.clear()
        _LEAF_DIGESTS[key] = digest
        return digest

    def __repr__(self) -> str:
        return (
            f"PageLeaf(index={self.index}, words={self.words},"
            f" sha256={self.object_sha256[:12]})"
        )

    @classmethod
    def from_record(cls, value: Mapping[str, Any]) -> "PageLeaf":
        required = {
            "codec",
            "decoded_bytes",
            "decoded_sha256",
            "index",
            "object_bytes",
            "object_sha256",
            "start_word",
            "words",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise RegionalFieldError("regional page record keys are invalid")
        try:
            return cls(
                codec=str(value["codec"]),
                decoded_bytes=int(value["decoded_bytes"]),
                decoded_sha256=str(value["decoded_sha256"]),
                index=int(value["index"]),
                object_bytes=int(value["object_bytes"]),
                object_sha256=str(value["object_sha256"]),
                start_word=int(value["start_word"]),
                words=int(value["words"]),
            )
        except (TypeError, ValueError) as exc:
            raise RegionalFieldError("regional page record is invalid") from exc


@lru_cache(maxsize=None)
def _zero_page_digest(index: int, start_word: int, words: int) -> str:
    """Content identity of an implicit zero page.

    The digest is a pure function of its arguments and every bounded step of a
    paged image re-derives it for every absent page, so it is memoised.  The
    key space is bounded by the image's page count.
    """

    return hashlib.sha256(
        _canonical(
            {
                "codec": "zero",
                "index": index,
                "start_word": start_word,
                "words": words,
            }
        )
    ).hexdigest()


@lru_cache(maxsize=262_144)
def _node_digest(first: int, count: int, left: str, right: str) -> str:
    """One inner commitment node.  Pure, so repeated tree rebuilds reuse it."""

    return hashlib.sha256(
        _canonical(
            {
                "schema": PAGE_TREE_SCHEMA,
                "first": first,
                "count": count,
                "left": left,
                "right": right,
            }
        )
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class _PageNode:
    """One node of the versioned page commitment tree."""

    first: int
    count: int
    digest: str
    left: "_PageNode | None" = None
    right: "_PageNode | None" = None

    @property
    def leaf(self) -> bool:
        return self.count == 1

    def nodes(self) -> int:
        return 2 * self.count - 1


class PageTree:
    """Versioned commitment over the logical page directory.

    Leaves bind logical placement, length, codec, and decoded-content
    identity. Sparse updates replace only paths to changed leaves; untouched
    subtrees remain shared by identity.
    """

    __slots__ = ("page_count", "_digests", "root")

    def __init__(self, page_count: int, digests: Sequence[str], *, _reuse: Any = None) -> None:
        self.page_count = _integer(page_count, "page count", minimum=1)
        self._digests = tuple(str(digest) for digest in digests)
        if len(self._digests) != self.page_count:
            raise RegionalFieldError("page tree digest count is invalid")
        self.root = self._build(0, self.page_count, _reuse)
        self._digests = ()

    def _build(self, first: int, count: int, reuse: Any) -> _PageNode:
        if count == 1:
            if reuse is not None:
                reused = reuse.get((first, 1))
                if reused is not None and reused.digest == self._digests[first]:
                    return reused
            return _PageNode(first, 1, self._digests[first])
        half = count // 2
        left = self._build(first, half, reuse)
        right = self._build(first + half, count - half, reuse)
        return _PageNode(
            first, count, _node_digest(first, count, left.digest, right.digest), left, right
        )

    @property
    def root_sha256(self) -> str:
        return self.root.digest

    def digest(self, index: int) -> str:
        target = _integer(index, "page index", maximum=self.page_count - 1)
        node = self.root
        while not node.leaf:
            left = node.left
            if target < left.first + left.count:
                node = left
            else:
                node = node.right
        return node.digest

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": PAGE_TREE_SCHEMA,
            "page_count": self.page_count,
            "root_sha256": self.root_sha256,
            "node_count": self.root.nodes(),
        }

    def audit_path(self, index: int) -> tuple[str, ...]:
        """One leaf digest plus its sibling digests, from the leaf upward."""

        target = _integer(index, "page index", maximum=self.page_count - 1)
        siblings: list[str] = []
        node = self.root
        while not node.leaf:
            half = node.count // 2
            if target < node.first + half:
                siblings.append(node.right.digest)
                node = node.left
            else:
                siblings.append(node.left.digest)
                node = node.right
        return (node.digest, *reversed(siblings))

    def verify_audit_path(self, index: int, path: Sequence[str]) -> bool:
        """Recompute the root from one leaf and its sibling path.

        The check uses only the page index, the declared page count, and the
        supplied digests, so a holder of the leaf, the path, and the root can
        confirm membership without the tree itself.
        """

        target = _integer(index, "page index", maximum=self.page_count - 1)
        siblings: list[tuple[int, int, bool]] = []
        first, count = 0, self.page_count
        while count > 1:
            half = count // 2
            if target < first + half:
                siblings.append((first + half, count - half, True))
                count = half
            else:
                siblings.append((first, half, False))
                first += half
                count -= half
        if len(path) != len(siblings) + 1:
            return False
        digest = str(path[0])
        if digest != self.digest(target):
            return False
        first, count = target, 1
        for (sibling_first, sibling_count, sibling_right), sibling in zip(
            reversed(siblings), path[1:]
        ):
            if sibling_right:
                digest = _node_digest(first, count + sibling_count, digest, str(sibling))
            else:
                digest = _node_digest(
                    sibling_first, count + sibling_count, str(sibling), digest
                )
            first = min(first, sibling_first)
            count += sibling_count
        return digest == self.root_sha256

    def updated(self, changed: Mapping[int, str]) -> "PageTree":
        """Replace a sparse set of leaves without copying the full tree."""

        updates = {
            _integer(int(index), "page index", maximum=self.page_count - 1): str(digest)
            for index, digest in changed.items()
        }
        if not updates:
            return self
        pending = sorted(updates)

        def rebuild(node: _PageNode, start: int, stop: int) -> _PageNode:
            if start == stop:
                return node
            if node.leaf:
                digest = updates[pending[start]]
                return node if digest == node.digest else _PageNode(node.first, 1, digest)
            left = node.left
            right = node.right
            split = left.first + left.count
            middle = bisect_left(pending, split, start, stop)
            next_left = rebuild(left, start, middle)
            next_right = rebuild(right, middle, stop)
            if next_left is left and next_right is right:
                return node
            return _PageNode(
                node.first,
                node.count,
                _node_digest(
                    node.first, node.count, next_left.digest, next_right.digest
                ),
                next_left,
                next_right,
            )

        root = rebuild(self.root, 0, len(pending))
        if root is self.root:
            return self
        successor = object.__new__(PageTree)
        successor.page_count = self.page_count
        successor._digests = ()
        successor.root = root
        return successor

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PageTree):
            return NotImplemented
        return (
            self.page_count == other.page_count
            and self.root_sha256 == other.root_sha256
        )

    def __hash__(self) -> int:
        return hash((self.page_count, self.root_sha256))

    def shared_nodes(self, previous: "PageTree") -> int:
        """Count shared nodes using unchanged subtree sizes."""

        if not isinstance(previous, PageTree) or previous.page_count != self.page_count:
            return 0

        def count_shared(current: _PageNode, prior: _PageNode) -> int:
            if current is prior:
                return 2 * current.count - 1
            if current.leaf:
                return 0
            return count_shared(current.left, prior.left) + count_shared(
                current.right, prior.right
            )

        return count_shared(self.root, previous.root)



@dataclass(frozen=True, slots=True)
class PageDirectory:
    """Ordered committed page records with implicit zero pages."""

    profile_sha256: str
    page_count: int
    leaves: tuple[PageLeaf, ...] = ()

    def __post_init__(self) -> None:
        _integer(self.page_count, "page count", minimum=1)
        previous = -1
        for leaf in self.leaves:
            if leaf.index <= previous or leaf.index >= self.page_count:
                raise RegionalFieldError("regional page directory order is invalid")
            previous = leaf.index

    def leaf(self, index: int) -> PageLeaf | None:
        target = _integer(index, "page index", maximum=self.page_count - 1)
        if not self.leaves:
            return None
        low, high = 0, len(self.leaves)
        while low < high:
            middle = (low + high) // 2
            if self.leaves[middle].index < target:
                low = middle + 1
            else:
                high = middle
        if low < len(self.leaves) and self.leaves[low].index == target:
            return self.leaves[low]
        return None

    def records(self) -> list[dict[str, Any]]:
        return [leaf.as_record() for leaf in self.leaves]

    def page_words(self, total_words: int, index: int) -> int:
        start = index * PERSISTENCE_PAGE_WORDS
        return min(PERSISTENCE_PAGE_WORDS, total_words - start)

    def digests(self, profile: "RegionalProfile") -> tuple[str, ...]:
        digests: list[str] = []
        for index in range(self.page_count):
            leaf = self.leaf(index)
            if leaf is None:
                digests.append(
                    _zero_page_digest(
                        index,
                        index * PERSISTENCE_PAGE_WORDS,
                        self.page_words(profile.total_words, index),
                    )
                )
            else:
                digests.append(leaf.digest)
        return tuple(digests)

    def tree(
        self, profile: "RegionalProfile", *, previous: "PageTree | None" = None
    ) -> PageTree:
        """Commitment over this directory, reusing the previous tree's paths."""

        digests = self.digests(profile)
        if previous is None or previous.page_count != self.page_count:
            return PageTree(self.page_count, digests)
        changed = {
            index: digest
            for index, digest in enumerate(digests)
            if digest != previous.digest(index)
        }
        return previous.updated(changed)

    def with_changes(
        self, profile: "RegionalProfile", changed: Mapping[int, "PageLeaf | None"]
    ) -> "PageDirectory":
        rows = {leaf.index: leaf for leaf in self.leaves}
        for index, leaf in changed.items():
            target = _integer(int(index), "page index", maximum=self.page_count - 1)
            if leaf is None:
                rows.pop(target, None)
            else:
                rows[target] = leaf
        return PageDirectory(self.profile_sha256, self.page_count, tuple(rows[key] for key in sorted(rows)))


def _page_count(profile: "RegionalProfile") -> int:
    return (profile.total_words + PERSISTENCE_PAGE_WORDS - 1) // PERSISTENCE_PAGE_WORDS


def _control_pages(profile: "RegionalProfile") -> tuple[int, ...]:
    """The pinned control closure: header and directory pages.

    Every bounded request walks the control closure first, so an allowance
    below it could never serve a request and is refused as inadmissible.
    """

    control_words = HEADER_WORDS + DIRECTORY_WORDS * profile.directory_capacity
    return tuple(
        range((control_words + PERSISTENCE_PAGE_WORDS - 1) // PERSISTENCE_PAGE_WORDS)
    )


def _encode_page(page: np.ndarray) -> PageLeaf | None:
    """Encode one canonical u32 page; zero pages stay implicit."""

    if not np.any(page):
        return None
    if (
        not np.isfinite(page).all()
        or not np.equal(page, np.floor(page)).all()
        or np.any(page < 0)
        or np.any(page > U32_MAX)
    ):
        raise RegionalFieldError("regional persistence page is not a canonical u32 image")
    decoded = page.astype("<u4", copy=False).tobytes(order="C")
    return decoded


class PagedFieldImage:
    """The logical regional image addressed through bounded, versioned pages."""

    __slots__ = (
        "profile", "catalog", "directory", "objects", "resident_limit",
        "dirty_limit", "predecessor", "transition", "revoked_roots",
        "audited_state_sha256", "state_sha256_kind", "_logical_digest",
        "_tree", "_resident", "_resident_order", "_resident_tokens",
        "_placements", "_pinned", "_tier_store",
        "_counters", "_validated_pages", "_validated_root", "_resource_manager",
        "_prefetch_sessions", "_prefetched_pages", "_next_prefetch_id",
        "program_id",
    )

    def __init__(
        self,
        profile: "RegionalProfile",
        catalog: "KernelCatalog",
        directory: PageDirectory,
        objects: Mapping[str, bytes],
        *,
        resident_limit: int = DEFAULT_RESIDENT_PAGES,
        dirty_limit: int = DEFAULT_DIRTY_PAGES,
        predecessor: Mapping[str, Any] | None = None,
        transition: Mapping[str, Any] | None = None,
        revoked_roots: Sequence[str] = (),
        audited_state_sha256: str | None = None,
        state_sha256_kind: str | None = None,
        pinned: Sequence[int] = (),
        previous_tree: "PageTree | None" = None,
        _page_tree: "PageTree | None" = None,
        _objects_verified: bool = False,
        resource_limits: ResourceLimits | Mapping[str, Any] | None = None,
        resource_manager: ResidencyManager | None = None,
        program_id: str | None = None,
        tier_store: PageTierStore | None = None,
    ) -> None:
        if not isinstance(profile, RegionalProfile):
            raise RegionalFieldError("regional profile required for a paged image")
        if not isinstance(catalog, KernelCatalog):
            raise RegionalFieldError("kernel catalog required for a paged image")
        if directory.profile_sha256 != profile.fingerprint:
            raise RegionalFieldError("page directory profile mismatches the image profile")
        if directory.page_count != _page_count(profile):
            raise RegionalFieldError("page directory geometry mismatches the profile")
        _integer(resident_limit, "resident page limit", minimum=1, maximum=MAX_RESIDENCY_PAGES)
        _integer(dirty_limit, "dirty page limit", minimum=1, maximum=MAX_RESIDENCY_PAGES)
        identity_kind = (
            PAGED_STATE_KIND_FLAT
            if state_sha256_kind is None
            else str(state_sha256_kind)
        )
        if identity_kind not in {PAGED_STATE_KIND_FLAT, PAGED_STATE_KIND_ROOT}:
            raise RegionalFieldError("paged state identity kind is invalid")
        if identity_kind == PAGED_STATE_KIND_ROOT and audited_state_sha256 is not None:
            raise RegionalFieldError("page-tree identity cannot masquerade as a flat audit")
        if not isinstance(objects, Mapping):
            raise RegionalFieldError("regional page objects must be a mapping")
        lazy_backing = not isinstance(objects, (dict, MappingProxyType))
        for key in objects:
            if not isinstance(key, str) or len(key) != 64:
                raise RegionalFieldError("regional page object address is invalid")
        if not lazy_backing and not _objects_verified:
            for key in objects:
                value = objects[key]
                if not isinstance(value, bytes) or hashlib.sha256(value).hexdigest() != key:
                    raise PageUnavailable("corrupt", "object digest does not match its address")
        self.profile = profile
        self.catalog = catalog
        self.directory = directory
        self.objects = objects
        self.resident_limit = int(resident_limit)
        self.dirty_limit = int(dirty_limit)
        self.predecessor = None if predecessor is None else dict(predecessor)
        self.transition = (
            {"kind": "storage-only"}
            if transition is None
            else dict(transition)
        )
        self.revoked_roots = tuple(str(root) for root in revoked_roots)
        self.audited_state_sha256 = audited_state_sha256
        self.state_sha256_kind = identity_kind
        self._logical_digest: str | None = None
        self._placements: dict[str, set[int]] = {
            "ram": set(), "storage": set(), "nvme": set(), "hdd": set()
        }
        self._tier_store = tier_store
        if _page_tree is None:
            self._tree = directory.tree(profile, previous=previous_tree)
        elif (
            not isinstance(_page_tree, PageTree)
            or _page_tree.page_count != directory.page_count
        ):
            raise RegionalFieldError("precommitted page tree geometry is invalid")
        else:
            self._tree = _page_tree
        self._resident_tokens: dict[int, Any] = {}
        self._resident: dict[int, np.ndarray] = {}
        self._resident_order: list[int] = []
        self._pinned: set[int] = {int(index) for index in pinned}
        if self.resident_limit < len(self._pinned):
            raise RegionalFieldError(
                f"residency allowance must hold the {len(self._pinned)} pinned "
                "control pages"
            )
        self._validated_pages: set[int] = set()
        self._validated_root = self._tree.root_sha256
        self._resource_manager = (
            resource_manager
            if resource_manager is not None
            else ResidencyManager(resource_limits)
        )
        self.program_id = None if program_id is None else str(program_id)
        self._counters: dict[str, int] = {
            "page_decodes": 0,
            "page_misses": 0,
            "page_cache_hits": 0,
            "page_evictions": 0,
            "decoded_words": 0,
            "resident_high_water_pages": 0,
            "dense_materialisations": 0,
            "objects_written": 0,
            "objects_reused": 0,
            "object_verifications": 0 if lazy_backing else sum(1 for _ in objects),
            "deferred_object_verifications": sum(1 for _ in objects) if lazy_backing else 0,
            "prefetch_requests": 0,
            "prefetched_pages": 0,
            "prefetch_hits": 0,
            "unused_prefetch_misses": 0,
            "prefetch_deferred_pages": 0,
            "prefetch_stale": 0,
        }
        self._prefetch_sessions: dict[int, dict[str, Any]] = {}
        self._prefetched_pages: dict[int, int] = {}
        self._next_prefetch_id = 1

    # -- construction ----------------------------------------------------

    @classmethod
    def from_dense(
        cls,
        field: np.ndarray,
        profile: "RegionalProfile",
        catalog: "KernelCatalog" = EMPTY_KERNEL_CATALOG,
        *,
        resident_limit: int = DEFAULT_RESIDENT_PAGES,
        dirty_limit: int = DEFAULT_DIRTY_PAGES,
        validate: bool = True,
        pin_control: bool = True,
        resource_limits: ResourceLimits | Mapping[str, Any] | None = None,
        resource_manager: ResidencyManager | None = None,
        program_id: str | None = None,
        tier_store: PageTierStore | None = None,
    ) -> "PagedFieldImage":
        if validate:
            validate_field(field, profile, catalog)
        flat = field.reshape(-1)
        leaves: list[PageLeaf] = []
        objects: dict[str, bytes] = {}
        for index in range(_page_count(profile)):
            start = index * PERSISTENCE_PAGE_WORDS
            page = flat[start:start + PERSISTENCE_PAGE_WORDS]
            decoded = _encode_page(page)
            if decoded is None:
                continue
            physical = zlib.compress(decoded, level=6)
            object_sha = hashlib.sha256(physical).hexdigest()
            objects[object_sha] = physical
            leaves.append(
                PageLeaf(
                    index=index,
                    start_word=start,
                    words=int(page.size),
                    decoded_bytes=len(decoded),
                    decoded_sha256=hashlib.sha256(decoded).hexdigest(),
                    object_bytes=len(physical),
                    object_sha256=object_sha,
                )
            )
        directory = PageDirectory(profile.fingerprint, _page_count(profile), tuple(leaves))
        image = cls(
            profile,
            catalog,
            directory,
            objects,
            resident_limit=resident_limit,
            dirty_limit=dirty_limit,
            audited_state_sha256=state_sha256(field, profile),
            pinned=_control_pages(profile) if pin_control else (),
            _objects_verified=True,
            resource_limits=resource_limits,
            resource_manager=resource_manager,
            program_id=program_id,
            tier_store=tier_store,
        )
        image._validated_pages = set(range(directory.page_count))
        if pin_control:
            # Only the header and directory must stay resident for every
            # bounded operation; the rest of the control closure is read on
            # demand so the allowance is never exceeded by policy alone.
            image.pin(_control_pages(profile))
        return image

    @classmethod
    def from_descriptor(
        cls,
        value: Mapping[str, Any],
        objects: Mapping[str, bytes] | None = None,
        catalog: "KernelCatalog" = EMPTY_KERNEL_CATALOG,
        *,
        profile: "RegionalProfile | None" = None,
        resident_limit: int | None = None,
        dirty_limit: int | None = None,
        verify: str = "control",
        revoked_roots: Sequence[str] = (),
        _objects_verified: bool = False,
        resource_limits: ResourceLimits | Mapping[str, Any] | None = None,
        resource_manager: ResidencyManager | None = None,
        program_id: str | None = None,
        tier_store: PageTierStore | None = None,
    ) -> "PagedFieldImage":
        """Reopen a paged image from its descriptor.

        ``verify="control"`` loads and verifies the control/continuation
        closure; other chunks are verified when they are accessed.  No
        dormant byte is claimed as freshly audited.
        """

        required = {
            "schema",
            "layout",
            "profile",
            "profile_sha256",
            "catalog_sha256",
            "page_words",
            "byte_order",
            "word_encoding",
            "pages",
            "root_sha256",
            "page_count",
        }
        allowed = required | {
            "state_sha256",
            "state_sha256_kind",
            "segments",
            "control_pages",
            "predecessor",
            "transition",
            "semantic",
            "numerical",
            "continuations",
            "retention",
            "resource",
            "correction",
            "clock",
            "base_epoch",
            "resident_limit",
            "dirty_limit",
        }
        if not isinstance(value, Mapping) or not required <= set(value) <= allowed:
            raise RegionalFieldError("paged regional descriptor keys are invalid")
        if (
            value["schema"] != PAGED_MANIFEST_SCHEMA
            or value["layout"] != REGIONAL_LAYOUT
            or value["page_words"] != PERSISTENCE_PAGE_WORDS
            or value["byte_order"] != "little"
            or value["word_encoding"] != "u32"
        ):
            raise RegionalFieldError("paged regional descriptor identity is invalid")
        resolved = RegionalProfile.from_dict(value["profile"])
        if profile is not None and profile.fingerprint != resolved.fingerprint:
            raise RegionalFieldError("paged descriptor profile mismatches the requested image")
        if (
            value["profile_sha256"] != resolved.fingerprint
            or value["catalog_sha256"] != catalog.fingerprint
        ):
            raise RegionalFieldError("paged descriptor profile or catalog digest mismatches")
        raw_pages = value["pages"]
        if not isinstance(raw_pages, list):
            raise RegionalFieldError("paged descriptor page directory is invalid")
        leaves: list[PageLeaf] = []
        previous = -1
        count = _page_count(resolved)
        if value["page_count"] != count:
            raise RegionalFieldError("paged descriptor page count mismatches the profile")
        for raw in raw_pages:
            leaf = PageLeaf.from_record(raw)
            if (
                leaf.index <= previous
                or leaf.index >= count
                or leaf.start_word != leaf.index * PERSISTENCE_PAGE_WORDS
                or leaf.words
                != min(
                    PERSISTENCE_PAGE_WORDS,
                    resolved.total_words - leaf.start_word,
                )
            ):
                raise RegionalFieldError("paged descriptor page geometry is invalid")
            previous = leaf.index
            leaves.append(leaf)
        directory = PageDirectory(resolved.fingerprint, count, tuple(leaves))
        tree = directory.tree(resolved)
        if tree.root_sha256 != value["root_sha256"]:
            raise RegionalFieldError("paged descriptor page-tree root mismatches")
        identity_kind = value.get("state_sha256_kind", PAGED_STATE_KIND_FLAT)
        declared_state_sha256 = value.get("state_sha256")
        if identity_kind == PAGED_STATE_KIND_ROOT:
            expected_state_sha256 = paged_root_state_sha256(
                resolved,
                tree.root_sha256,
                count,
            )
            if declared_state_sha256 != expected_state_sha256:
                raise RegionalFieldError("paged page-tree state identity mismatches")
            audited_state_sha256 = None
        elif identity_kind == PAGED_STATE_KIND_FLAT:
            audited_state_sha256 = declared_state_sha256
        else:
            raise RegionalFieldError("paged state identity kind is invalid")
        resident_limit = _integer(
            value.get("resident_limit", DEFAULT_RESIDENT_PAGES)
            if resident_limit is None
            else resident_limit,
            "resident page limit",
            minimum=1,
            maximum=MAX_RESIDENCY_PAGES,
        )
        dirty_limit = _integer(
            value.get("dirty_limit", DEFAULT_DIRTY_PAGES)
            if dirty_limit is None
            else dirty_limit,
            "dirty page limit",
            minimum=1,
            maximum=MAX_RESIDENCY_PAGES,
        )
        image = cls(
            resolved,
            catalog,
            directory,
            objects,
            resident_limit=resident_limit,
            dirty_limit=dirty_limit,
            predecessor=value.get("predecessor"),
            transition=value.get("transition"),
            revoked_roots=revoked_roots,
            _objects_verified=_objects_verified,
            resource_limits=(
                resource_limits
                if resource_limits is not None
                else value.get("resource")
            ),
            resource_manager=resource_manager,
            program_id=program_id,
            audited_state_sha256=audited_state_sha256,
            tier_store=tier_store,
            state_sha256_kind=identity_kind,
        )
        if image._tree.root_sha256 in image.revoked_roots:
            raise PageUnavailable("revoked", "page-tree root is revoked")
        if verify not in {"none", "control"}:
            raise RegionalFieldError("paged reopen verification mode is unsupported")
        if verify == "control":
            for index in image.control_closure():
                image._verify_page(index)
        return image

    @classmethod
    def from_chunked_descriptor(
        cls,
        value: Mapping[str, Any],
        objects: Mapping[str, bytes],
        catalog: "KernelCatalog" = EMPTY_KERNEL_CATALOG,
        **kwargs: Any,
    ) -> "PagedFieldImage":
        """Reopen the established chunked checkpoint format as a paged image."""

        if not isinstance(value, Mapping) or value.get("schema") != PERSISTENCE_CHUNK_SCHEMA:
            raise RegionalFieldError("regional chunk descriptor identity is invalid")
        profile = RegionalProfile.from_dict(value["profile"])
        if value.get("profile_sha256") != profile.fingerprint:
            raise RegionalFieldError("regional chunk descriptor profile mismatches")
        if "resident_limit" in value:
            kwargs.setdefault(
                "resident_limit",
                _integer(
                    value["resident_limit"],
                    "resident page limit",
                    minimum=1,
                    maximum=MAX_RESIDENCY_PAGES,
                ),
            )
        if "dirty_limit" in value:
            kwargs.setdefault(
                "dirty_limit",
                _integer(
                    value["dirty_limit"],
                    "dirty page limit",
                    minimum=1,
                    maximum=MAX_RESIDENCY_PAGES,
                ),
            )
        manifest = {
            "schema": PAGED_MANIFEST_SCHEMA,
            "layout": REGIONAL_LAYOUT,
            "profile": profile.as_dict(),
            "profile_sha256": profile.fingerprint,
            "catalog_sha256": value["catalog_sha256"],
            "page_words": PERSISTENCE_PAGE_WORDS,
            "byte_order": "little",
            "word_encoding": "u32",
            "pages": [dict(record) for record in value["chunks"]],
            "page_count": _page_count(profile),
            "root_sha256": PageDirectory(
                profile.fingerprint,
                _page_count(profile),
                tuple(PageLeaf.from_record(record) for record in value["chunks"]),
            ).tree(profile).root_sha256,
            "state_sha256": value["state_sha256"],
            "predecessor": {
                "root_sha256": None,
                "state_sha256": value["state_sha256"],
                "layout": REGIONAL_LAYOUT,
            },
            "transition": {"kind": "storage-only"},
        }
        if "state_sha256_kind" in value:
            manifest["state_sha256_kind"] = value["state_sha256_kind"]
            manifest["predecessor"]["state_sha256_kind"] = value[
                "state_sha256_kind"
            ]
        if "resource" in value:
            manifest["resource"] = value["resource"]
        kwargs.setdefault("_objects_verified", True)
        return cls.from_descriptor(
            manifest,
            objects,
            catalog,
            profile=profile,
            **kwargs,
        )

    # -- identity and directory -----------------------------------------

    @property
    def page_count(self) -> int:
        return self.directory.page_count

    @property
    def root_sha256(self) -> str:
        return self._tree.root_sha256

    @property
    def tree(self) -> PageTree:
        return self._tree

    @property
    def counters(self) -> Mapping[str, int]:
        return MappingProxyType(dict(self._counters))
    @property
    def resource_manager(self) -> ResidencyManager:
        return self._resource_manager

    @property
    def resource_limits(self) -> ResourceLimits:
        return self._resource_manager.limits

    def with_resource_limits(
        self, limits: ResourceLimits | Mapping[str, Any]
    ) -> "PagedFieldImage":
        successor = PagedFieldImage(
            self.profile,
            self.catalog,
            self.directory,
            self.objects,
            resident_limit=self.resident_limit,
            dirty_limit=self.dirty_limit,
            predecessor=self.predecessor,
            transition=self.transition,
            revoked_roots=self.revoked_roots,
            audited_state_sha256=self.audited_state_sha256,
            state_sha256_kind=self.state_sha256_kind,
            pinned=self._pinned,
            _page_tree=self._tree,
            _objects_verified=True,
            resource_limits=ResourceLimits.from_dict(limits),
            tier_store=self._tier_store,
            program_id=self.program_id,
        )
        self.release_resident()
        return successor

    def place_pages(
        self,
        pages: Sequence[int],
        tier: str,
        *,
        root_sha256: str | None = None,
        max_pages: int = 16,
        continuation: Mapping[str, Any] | None = None,
        tier_store: PageTierStore | None = None,
    ) -> dict[str, Any]:
        """Place a bounded set of exact pages without changing root identity."""
        if tier == "vram":
            raise RegionalFieldError(
                "vram placement requires a real GPU page executor"
            )
        if tier not in {"ram", "storage", "nvme", "hdd"}:
            raise RegionalFieldError("page placement tier is invalid")
        max_pages = _integer(
            max_pages, "max_pages", minimum=1, maximum=MAX_RESIDENCY_PAGES
        )
        expected = self.root_sha256 if root_sha256 is None else str(root_sha256)
        requested = list(pages)
        if expected != self.root_sha256:
            raise RegionalFieldError("page placement root is stale")
        if continuation is not None:
            if continuation.get("root_sha256") != self.root_sha256:
                raise RegionalFieldError("page placement continuation root is stale")
            if continuation.get("tier") != tier:
                raise RegionalFieldError("page placement continuation tier is invalid")
            continued_pages = [
                _integer(index, "page index", maximum=self.page_count - 1)
                for index in continuation.get("remaining_pages", ())
            ]
            versions = continuation.get("page_versions", ())
            if len(continued_pages) != len(versions) or any(
                self.tree.digest(
                    _integer(index, "page index", maximum=self.page_count - 1)
                ) != str(version)
                for index, version in zip(continued_pages, versions)
            ):
                raise RegionalFieldError(
                    "page placement continuation versions are stale"
                )
            requested = continued_pages
        unique: list[int] = []
        seen: set[int] = set()
        for index in requested:
            index = _integer(index, "page index", maximum=self.page_count - 1)
            if index not in seen:
                seen.add(index)
                unique.append(index)
        batch = unique[:max_pages]
        remaining = unique[max_pages:]
        moved: list[int] = []
        moved_bytes = 0

        selected_store = self._tier_store if tier_store is None else tier_store
        if tier in {"nvme", "hdd"} and selected_store is None:
            raise RegionalFieldError(
                f"{tier} placement requires a configured page tier store"
            )
        if selected_store is not None:
            self._tier_store = selected_store

        for index in batch:
            leaf = self.directory.leaf(index)
            if tier in {"nvme", "hdd"}:
                if leaf is None:
                    continue
                store = selected_store
                assert store is not None
                page_version = self.tree.digest(index)
                existing = store.lookup(
                    tier,
                    root_sha256=self.root_sha256,
                    page_index=index,
                    page_version=page_version,
                    object_sha256=leaf.object_sha256,
                )
                if existing is not None:
                    stored = store.get(existing)
                    if (
                        not isinstance(stored, bytes)
                        or len(stored) != leaf.object_bytes
                        or hashlib.sha256(stored).hexdigest() != leaf.object_sha256
                    ):
                        raise PageTierStoreError(
                            "existing page-tier object does not match the exact page"
                        )
                    self._decode_page_object(index, leaf, stored)
                    self._placements[tier].add(index)
                    continue

                # Verify the logical page before publishing the unchanged,
                # content-addressed compressed object without RAM admission.
                physical = self._read_page_object(index, leaf)
                self._decode_page_object(index, leaf, physical)
                tier_bytes_before = store.used_bytes(tier)
                receipt = store.put(
                    tier,
                    physical,
                    root_sha256=self.root_sha256,
                    page_index=index,
                    page_version=page_version,
                    object_sha256=leaf.object_sha256,
                    expected_bytes=leaf.object_bytes,
                )
                if (
                    receipt.root_sha256 != self.root_sha256
                    or receipt.page_index != index
                    or receipt.page_version != page_version
                    or receipt.tier != tier
                    or receipt.object_sha256 != leaf.object_sha256
                    or receipt.byte_count != leaf.object_bytes
                ):
                    raise PageTierStoreError(
                        "page tier store returned a mismatched placement receipt"
                    )
                self._placements[tier].add(index)
                moved.append(index)
                moved_bytes += max(
                    0, store.used_bytes(tier) - tier_bytes_before
                )
                continue

            if tier == "ram":
                was_resident = index in self._resident
                page = self._page(index, record_prefetch_use=False)
                self._placements[tier].add(index)
                if not was_resident:
                    moved.append(index)
                    moved_bytes += int(page.nbytes)
                continue

            page = self._page(index, record_prefetch_use=False)
            backing = self.objects
            put = getattr(backing, "put", None)
            if not callable(put):
                backing = getattr(backing, "source", None)
                put = getattr(backing, "put", None)
            if not callable(put):
                raise RegionalFieldError(
                    "storage placement requires a writable object store"
                )
            if leaf is not None and index not in self._placements[tier]:
                physical = self._read_page_object(index, leaf)
                put(physical, digest=leaf.object_sha256)
                self._placements[tier].add(index)
                moved.append(index)
                moved_bytes += leaf.object_bytes

        next_cont = None
        if remaining:
            next_cont = {
                "schema": "cassifi.page-placement.v1",
                "root_sha256": self.root_sha256,
                "tier": tier,
                "remaining_pages": remaining,
                "page_versions": [self.tree.digest(index) for index in remaining],
            }
        return {
            "schema": "cassifi.page-placement.v1",
            "root_sha256": self.root_sha256,
            "tier": tier,
            "moved_pages": moved,
            "remaining_pages": remaining,
            "continuation": next_cont,
            "bytes": moved_bytes,
            "residency": self._resource_manager.report(),
        }

    def _read_page_object(self, index: int, leaf: PageLeaf) -> bytes:
        """Read the exact compressed object from a valid tier or canonical backing."""
        store = self._tier_store
        if store is not None:
            roots = getattr(store, "roots", None)
            tiers = tuple(
                tier for tier in ("nvme", "hdd")
                if roots is None or tier in roots
            )
            for tier in tiers:
                try:
                    receipt = store.lookup(
                        tier,
                        root_sha256=self.root_sha256,
                        page_index=index,
                        page_version=self.tree.digest(index),
                        object_sha256=leaf.object_sha256,
                    )
                    if receipt is None:
                        continue
                    if (
                        receipt.root_sha256 != self.root_sha256
                        or receipt.page_index != index
                        or receipt.page_version != self.tree.digest(index)
                        or receipt.tier != tier
                        or receipt.object_sha256 != leaf.object_sha256
                        or receipt.byte_count != leaf.object_bytes
                    ):
                        continue
                    physical = store.get(receipt)
                except PageTierStoreError:
                    # A stale, missing, or corrupt spill is not authoritative;
                    # the immutable canonical backing remains the fallback.
                    continue
                if (
                    isinstance(physical, bytes)
                    and len(physical) == leaf.object_bytes
                    and hashlib.sha256(physical).hexdigest() == leaf.object_sha256
                ):
                    return physical

        try:
            physical = self.objects[leaf.object_sha256]
        except (KeyError, StorageError) as exc:
            raise PageUnavailable(
                "missing", f"page {index} object is absent from storage", pages=[index]
            ) from exc
        if not isinstance(physical, bytes):
            raise PageUnavailable(
                "corrupt", f"page {index} object is not bytes", pages=[index]
            )
        if len(physical) != leaf.object_bytes:
            raise PageUnavailable(
                "corrupt", f"page {index} object length mismatches", pages=[index]
            )
        if hashlib.sha256(physical).hexdigest() != leaf.object_sha256:
            raise PageUnavailable(
                "corrupt", f"page {index} compressed identity mismatches", pages=[index]
            )
        return physical

    def _decode_page_object(
        self, index: int, leaf: PageLeaf, physical: bytes
    ) -> bytes:
        """Verify decoded identity without admitting a page to the RAM cache."""

        self._counters["object_verifications"] += 1
        try:
            decoded = zlib.decompress(physical)
        except zlib.error as exc:
            raise PageUnavailable(
                "corrupt", f"page {index} cannot be decoded", pages=[index]
            ) from exc
        if (
            len(decoded) != leaf.decoded_bytes
            or hashlib.sha256(decoded).hexdigest() != leaf.decoded_sha256
        ):
            raise PageUnavailable(
                "corrupt", f"page {index} decoded identity mismatches", pages=[index]
            )
        self._validated_pages.add(index)
        return decoded

    def _verify_page(self, index: int) -> np.ndarray:
        """Decode and verify one page's decoded-content identity."""

        leaf = self.directory.leaf(index)
        if leaf is None:
            page = np.zeros(
                self.directory.page_words(self.profile.total_words, index),
                dtype=np.float64,
            )
            page.setflags(write=False)
            return page
        physical = self._read_page_object(index, leaf)
        decoded = self._decode_page_object(index, leaf, physical)
        page = np.frombuffer(decoded, dtype="<u4").astype(np.float64)
        page.setflags(write=False)
        return page
    def _record_prefetch_hit(self, index: int) -> None:
        prefetch_id = self._prefetched_pages.pop(index, None)
        if prefetch_id is None:
            return
        session = self._prefetch_sessions.get(prefetch_id)
        if session is None:
            return
        session["used_pages"].add(index)
        self._counters["prefetch_hits"] += 1

    def _page(self, index: int, *, record_prefetch_use: bool) -> np.ndarray:
        target = _integer(index, "page index", maximum=self.page_count - 1)
        resident = self._resident.get(target)
        if resident is not None:
            self._touch(target)
            self._counters["page_cache_hits"] += 1
            if record_prefetch_use:
                self._record_prefetch_hit(target)
            return resident
        self._counters["page_misses"] += 1
        words = self.directory.page_words(self.profile.total_words, target)
        needed = max(1, int(words * np.dtype(np.float64).itemsize))
        try:
            token = self._resource_manager.reserve(
                "ram", needed, kind="resident", program_id=self.program_id,
            )
        except ResourceWait:
            self.release_to_fit("ram", needed)
            token = self._resource_manager.reserve(
                "ram", needed, kind="resident", program_id=self.program_id,
            )
        try:
            page = self._verify_page(target)
            self._counters["page_decodes"] += 1
            self._counters["decoded_words"] += int(page.size)
            self._insert(target, page, token)
        except Exception:
            token.release()
            raise
        return page

    def page(self, index: int) -> np.ndarray:
        """Return one resident page, reserving its decoded bytes first."""

        return self._page(index, record_prefetch_use=True)

    def page_read_hint(self, pages: Sequence[int]) -> dict[str, Any]:
        """Bind a bounded exact page read set to this image's page generations."""

        if isinstance(pages, (str, bytes)) or not isinstance(pages, Sequence):
            raise RegionalFieldError("page read hint requires a bounded page sequence")
        if len(pages) > MAX_PREFETCH_PAGES:
            raise RegionalFieldError("page read hint exceeds its bounded page limit")
        unique: list[int] = []
        seen: set[int] = set()
        for raw_index in pages:
            index = _integer(raw_index, "page index", maximum=self.page_count - 1)
            if index not in seen:
                seen.add(index)
                unique.append(index)
        return {
            "schema": PAGE_READ_HINT_SCHEMA,
            "profile_sha256": self.profile.fingerprint,
            "root_sha256": self.root_sha256,
            "page_count": self.page_count,
            "pages": [
                {
                    "index": index,
                    "generation_sha256": self.tree.digest(index),
                }
                for index in unique
            ],
        }

    def prefetch_pages(
        self,
        hint: Mapping[str, Any],
        *,
        max_pages: int = 4,
    ) -> dict[str, Any]:
        """Stage exact clean pages within spare cache capacity.

        A hint for another profile, root, or page generation is rejected as a
        stale no-op. Optional prefetch neither evicts existing residents nor
        turns a resource shortage into a failed foreground read.
        """

        max_pages = _integer(
            max_pages, "prefetch page limit", minimum=1, maximum=MAX_PREFETCH_PAGES
        )
        self._counters["prefetch_requests"] += 1
        required = {
            "schema", "profile_sha256", "root_sha256", "page_count", "pages",
        }
        if not isinstance(hint, Mapping) or set(hint) != required:
            raise RegionalFieldError("page read hint shape is invalid")
        if hint["schema"] != PAGE_READ_HINT_SCHEMA:
            raise RegionalFieldError("page read hint schema is invalid")
        if (
            hint["profile_sha256"] != self.profile.fingerprint
            or hint["root_sha256"] != self.root_sha256
            or hint["page_count"] != self.page_count
        ):
            self._counters["prefetch_stale"] += 1
            return {
                "schema": PAGE_PREFETCH_SCHEMA,
                "status": "stale",
                "reason": "state-identity",
                "prefetch_id": None,
                "root_sha256": self.root_sha256,
                "prefetched_pages": [],
                "already_resident_pages": [],
                "deferred_pages": [],
            }
        raw_pages = hint["pages"]
        if not isinstance(raw_pages, list) or len(raw_pages) > MAX_PREFETCH_PAGES:
            raise RegionalFieldError("page read hint page list is invalid")
        requested: list[int] = []
        seen: set[int] = set()
        for row in raw_pages:
            if not isinstance(row, Mapping) or set(row) != {
                "index", "generation_sha256",
            }:
                raise RegionalFieldError("page read hint generation is invalid")
            index = _integer(row["index"], "page index", maximum=self.page_count - 1)
            generation = row["generation_sha256"]
            if (
                not isinstance(generation, str)
                or len(generation) != 64
                or any(char not in "0123456789abcdef" for char in generation)
            ):
                raise RegionalFieldError("page read hint generation digest is invalid")
            if index in seen:
                raise RegionalFieldError("page read hint contains duplicate pages")
            seen.add(index)
            if self.tree.digest(index) != generation:
                self._counters["prefetch_stale"] += 1
                return {
                    "schema": PAGE_PREFETCH_SCHEMA,
                    "status": "stale",
                    "reason": "page-generation",
                    "prefetch_id": None,
                    "root_sha256": self.root_sha256,
                    "prefetched_pages": [],
                    "already_resident_pages": [],
                    "deferred_pages": [],
                }
            requested.append(index)

        selected = requested[:max_pages]
        deferred = [
            {"index": index, "reason": "request-limit"}
            for index in requested[max_pages:]
        ]
        staged: list[int] = []
        already_resident: list[int] = []
        for index in selected:
            if index in self._resident:
                already_resident.append(index)
                continue
            if len(self._resident) >= self.resident_limit:
                deferred.append({"index": index, "reason": "resident-limit"})
                continue
            words = self.directory.page_words(self.profile.total_words, index)
            needed = max(1, int(words * np.dtype(np.float64).itemsize))
            if self._resource_manager.available("ram") < needed:
                deferred.append({"index": index, "reason": "resource"})
                continue
            try:
                token = self._resource_manager.reserve(
                    "ram", needed, kind="resident", program_id=self.program_id,
                )
            except ResourceWait:
                deferred.append({"index": index, "reason": "resource"})
                continue
            try:
                page = self._verify_page(index)
            except PageUnavailable:
                token.release()
                deferred.append({"index": index, "reason": "unavailable"})
                continue
            except Exception:
                token.release()
                raise
            self._counters["page_decodes"] += 1
            self._counters["decoded_words"] += int(page.size)
            self._insert(index, page, token, prefetched=True)
            staged.append(index)

        prefetch_id: int | None = None
        if staged:
            prefetch_id = self._next_prefetch_id
            self._next_prefetch_id += 1
            self._prefetch_sessions[prefetch_id] = {
                "root_sha256": self.root_sha256,
                "staged_pages": tuple(staged),
                "used_pages": set(),
            }
            for index in staged:
                self._prefetched_pages[index] = prefetch_id
        self._counters["prefetched_pages"] += len(staged)
        self._counters["prefetch_deferred_pages"] += len(deferred)
        return {
            "schema": PAGE_PREFETCH_SCHEMA,
            "status": (
                "staged" if staged else
                "already-resident" if already_resident and not deferred else
                "deferred" if deferred else
                "empty"
            ),
            "prefetch_id": prefetch_id,
            "root_sha256": self.root_sha256,
            "requested_pages": requested,
            "prefetched_pages": staged,
            "already_resident_pages": already_resident,
            "deferred_pages": deferred,
        }

    def settle_prefetch(self, prefetch_id: int) -> dict[str, Any]:
        """Close a prefetch attempt; only real resident reads count as hits."""

        prefetch_id = _integer(prefetch_id, "prefetch ID", minimum=1, maximum=U64_MAX)
        session = self._prefetch_sessions.pop(prefetch_id, None)
        if session is None:
            raise RegionalFieldError("page prefetch is already settled or unknown")
        staged = tuple(session["staged_pages"])
        used = sorted(session["used_pages"])
        unused = sorted(set(staged) - session["used_pages"])
        for index in staged:
            if self._prefetched_pages.get(index) == prefetch_id:
                self._prefetched_pages.pop(index, None)
        self._counters["unused_prefetch_misses"] += len(unused)
        return {
            "schema": PAGE_PREFETCH_SCHEMA,
            "status": "settled",
            "prefetch_id": prefetch_id,
            "root_sha256": session["root_sha256"],
            "prefetched_pages": list(staged),
            "used_pages": used,
            "unused_pages": unused,
        }

    def _touch(self, index: int) -> None:
        order = self._resident_order
        try:
            order.remove(index)
        except ValueError:  # pragma: no cover - defensive
            pass
        order.append(index)

    def _evict_to_allowance(self, requested: int | None = None) -> None:
        """Release unlocked pages until the allowance holds again."""

        while len(self._resident) > self.resident_limit:
            candidates = [
                key for key in self._resident_order if key not in self._pinned
            ]
            if not candidates:
                # Every resident page is pinned: the request cannot be served
                # under the declared allowance.  This is a typed resource wait,
                # never an oversized silent allocation.
                raise ResidencyWait(
                    "residency",
                    [requested] if requested is not None else [],
                    versions=(
                        []
                        if requested is None
                        else [self._tree.digest(requested)]
                    ),
                    reason="resource",
                    allowance=self.resident_limit,
                    segments=(
                        []
                        if requested is None
                        else [
                            name
                            for name, segment_pages in self.segments().items()
                            if requested in segment_pages
                        ]
                    ),
                )
            victim = candidates[0]
            self._resident.pop(victim, None)
            self._prefetched_pages.pop(victim, None)
            self._resident_order.remove(victim)
            self._placements["ram"].discard(victim)
            token = self._resident_tokens.pop(victim, None)
            if token is not None:
                token.release()
            self._counters["page_evictions"] += 1

    def _release_one(self, index: int) -> None:
        """Drop one page from the resident cache and release its reservation."""
        self._resident.pop(index, None)
        self._prefetched_pages.pop(index, None)
        self._resident_order.remove(index)
        token = self._resident_tokens.pop(index, None)
        self._placements["ram"].discard(index)
        if token is not None:
            token.release()
        self._counters["page_evictions"] += 1

    def _resident_bytes(self) -> int:
        return sum(
            int(getattr(token, "nbytes", 0))
            for token in self._resident_tokens.values()
        )

    def release_resident(self) -> None:
        """Return every reservation this image holds to its manager.

        A value-object transition replaces this image with its successor, so
        the resident pages and placements it holds become unreachable while the
        manager keeps charging their bytes: nothing else can release a holding
        whose image is dropped, and the field's accounting then climbs for the
        whole run while the live state stays tens of pages.  Both holdings
        leave here, so a successor under the same manager starts from the
        memory its predecessor actually returned.
        """

        for index in sorted(self._resident):
            token = self._resident_tokens.pop(index, None)
            if token is not None:
                token.release()
        self._resident.clear()
        self._resident_order.clear()
        self._prefetched_pages.clear()
        self._placements["ram"].clear()

    def release_to_fit(self, tier: str, byte_count: int) -> None:
        """Release unlocked resident pages so a reservation can be made.

        A page fetch reserves its bytes before it can know which older pages
        are now useless, so a full tier would refuse a page that its own cache
        could pay for.  Releasing least-recently-used unlocked pages first
        keeps the declaration honest: the cache pays for what the work holds.
        When the machine itself is the short side, the cache is given back to
        the declared low watermark, and only a locked set or a machine still
        short after that escalates as a typed wait.
        """

        manager = self._resource_manager
        while manager.available(tier) < byte_count:
            candidates = [
                key for key in self._resident_order if key not in self._pinned
            ]
            if not candidates:
                return
            if manager.room(tier) < byte_count:
                if self._resident_bytes() <= manager.watermark_floor(tier):
                    return
            self._release_one(candidates[0])

    def _insert(
        self,
        index: int,
        page: np.ndarray,
        token: Any,
        *,
        prefetched: bool = False,
    ) -> None:
        self._resident[index] = page
        self._resident_tokens[index] = token
        if prefetched:
            self._resident_order.insert(0, index)
        else:
            self._touch(index)
        self._evict_to_allowance(index)
        self._counters["resident_high_water_pages"] = max(
            self._counters["resident_high_water_pages"], len(self._resident)
        )

    def pin(self, pages: Sequence[int]) -> None:
        for index in pages:
            self._pinned.add(_integer(int(index), "page index", maximum=self.page_count - 1))

    def unpin(self, pages: Sequence[int]) -> None:
        for index in pages:
            self._pinned.discard(int(index))

    def pinned(self) -> tuple[int, ...]:
        return tuple(sorted(self._pinned))

    # -- segments --------------------------------------------------------

    def segments(self) -> dict[str, tuple[int, ...]]:
        """Logical segments as page ranges, for bounded reopen and traversal."""

        groups: dict[str, set[int]] = {name: set() for name in PAGE_SEGMENTS}
        groups["control"].update(_control_pages(self.profile))
        flat = _SegmentReader(self)
        header = flat.words(0, HEADER_WORDS)
        kinds = {
            KIND_REGISTRY: "registry",
            KIND_QUEUE: "queue",
            KIND_PROGRAM: "programs",
            KIND_PROCEDURE: "programs",
            KIND_AUTOMATON: "automaton",
            KIND_LEDGER: "ledger",
            KIND_CONTINUATION: "continuation",
            KIND_QUARANTINE: "quarantine",
        }
        stack_slots = {
            int(header[H_LEFT_STACK]),
            int(header[H_RIGHT_STACK]),
        }
        for slot in range(1, self.profile.directory_capacity + 1):
            row = flat.words(HEADER_WORDS + (slot - 1) * DIRECTORY_WORDS, DIRECTORY_WORDS)
            if not int(row[D_FLAGS]) & (FLAG_LIVE | FLAG_QUARANTINED):
                continue
            base = int(row[D_BASE])
            used = int(row[D_USED])
            capacity = int(row[D_CAPACITY])
            if capacity <= 0 or used <= 0:
                continue
            if used > capacity:
                raise RegionalFieldError("region usage exceeds its page capacity")
            segment = kinds.get(int(row[D_KIND]))
            if segment is None:
                segment = "stacks" if slot in stack_slots else "values"
            first = base // PERSISTENCE_PAGE_WORDS
            last = (base + used - 1) // PERSISTENCE_PAGE_WORDS
            groups[segment].update(range(first, last + 1))
        return {
            name: tuple(sorted(groups[name]))
            for name in PAGE_SEGMENTS
            if groups[name]
        }

    def control_closure(self) -> tuple[int, ...]:
        groups = self.segments()
        pages: set[int] = set()
        for name in CONTROL_CLOSURE_SEGMENTS:
            pages.update(groups.get(name, ()))
        return tuple(sorted(pages))

    # -- views and staging ----------------------------------------------

    def view(
        self,
        staging: "PagedFieldStaging | None" = None,
        *,
        write: bool = False,
        track_prefetch_use: bool = True,
    ) -> "_PagedFieldView":
        return _PagedFieldView(
            self,
            staging,
            write=write,
            track_prefetch_use=track_prefetch_use,
        )

    def header_words(self, start: int, length: int) -> np.ndarray:
        """Read a bounded word range without materialising the whole image."""

        return _SegmentReader(self).words(start, length)

    def stage(self, *, stage: str = "transition") -> "PagedFieldStaging":
        return PagedFieldStaging(self, stage=stage)

    def materialise(
        self, *, pages: Sequence[int] | None = None, bounded: bool = False
    ) -> np.ndarray:
        """Materialise the complete dense image through an explicit audit.

        Bounded storage is the default working mode; this path is the
        declared full audit, so it lifts the residency allowance unless the
        caller asks for a bounded reconstruction.
        """

        self._counters["dense_materialisations"] += 1
        field = np.zeros(self.profile.shape, dtype=np.float64)
        flat = field.reshape(-1)
        selected = range(self.page_count) if pages is None else pages
        limit = self.resident_limit
        if not bounded:
            self.resident_limit = max(limit, self.page_count)
        try:
            for index in selected:
                page = self._page(index, record_prefetch_use=False)
                start = index * PERSISTENCE_PAGE_WORDS
                flat[start:start + page.size] = page
        finally:
            self.resident_limit = limit
            self._evict_to_allowance()
        return field

    def with_resident_limit(self, limit: int) -> "PagedFieldImage":
        """Return a twin of this image under a different page allowance."""

        target = _integer(
            limit, "resident page limit", minimum=1, maximum=MAX_RESIDENCY_PAGES
        )
        if target < len(self._pinned):
            raise RegionalFieldError(
                f"residency allowance must hold the {len(self._pinned)} pinned pages"
            )
        if target == self.resident_limit:
            return self
        successor = PagedFieldImage(
            self.profile, self.catalog, self.directory, self.objects,
            resident_limit=target, dirty_limit=self.dirty_limit,
            predecessor=self.predecessor, transition=self.transition,
            revoked_roots=self.revoked_roots,
            audited_state_sha256=self.audited_state_sha256,
            state_sha256_kind=self.state_sha256_kind, pinned=self._pinned,
            _page_tree=self._tree,
            tier_store=self._tier_store,
            resource_manager=self._resource_manager, program_id=self.program_id,
        )
        self.release_resident()
        return successor

    def with_resource_manager(
        self,
        manager: ResidencyManager,
        *,
        program_id: str | None = None,
    ) -> "PagedFieldImage":
        if not isinstance(manager, ResidencyManager):
            raise RegionalFieldError("residency manager is invalid")
        successor = PagedFieldImage(
            self.profile, self.catalog, self.directory, self.objects,
            resident_limit=self.resident_limit, dirty_limit=self.dirty_limit,
            predecessor=self.predecessor, transition=self.transition,
            revoked_roots=self.revoked_roots,
            audited_state_sha256=self.audited_state_sha256,
            state_sha256_kind=self.state_sha256_kind, pinned=self._pinned,
            _page_tree=self._tree,
            resource_manager=manager,
            tier_store=self._tier_store,
            program_id=self.program_id if program_id is None else program_id,
        )
        self.release_resident()
        return successor

    def flat_digest(self) -> str:
        return state_sha256(self.materialise(), self.profile)

    def logical_state_sha256(self) -> str:
        """The logical state identity, streamed page by page.

        Equal to ``flat_digest`` without holding the dense image or paying the
        bounded resident cache: the digest streams the immutable page records
        directly, and the result is cached because a committed image never
        changes.  A recorded commit audit is reused.
        """

        audited = self.audited_state_sha256
        if audited is not None:
            return audited
        cached = self._logical_digest
        if cached is None:
            cached = self._stream_state_digest()
            self._logical_digest = cached
        return cached

    def _stream_state_digest(self) -> str:
        """Equally exact flat digest, read straight off immutable page records.

        Each leaf object is fetched, length-checked, decoded and checked against
        its recorded decoded identity exactly as ``_verify_page`` does, but the
        converted bytes are handed to the hasher immediately: no page is
        inserted into the resident cache, evicted, or copied out again, and
        implicit zero pages contribute their zero bytes without a fetch.
        """

        digest = _state_digest_head(self.profile)
        previous_object: str | None = None
        previous_decoded: str | None = None
        previous_words: memoryview | None = None
        for index in range(self.page_count):
            leaf = self.directory.leaf(index)
            if leaf is None:
                words = self.directory.page_words(self.profile.total_words, index)
                digest.update(b"\x00" * (int(words) * 8))
                continue
            need = (
                leaf.object_sha256,
                leaf.decoded_sha256,
            )
            if need == (previous_object, previous_decoded):
                # Content-addressed equality with the page just hashed: the
                # verification performed for it settles this leaf, and the
                # logical plane only cares about the bytes.
                if previous_words is None:  # pragma: no cover - defensive
                    raise PageUnavailable(
                        "corrupt", f"page {index} decoded identity mismatches",
                        pages=[index],
                    )
                digest.update(previous_words)
                continue
            physical = self._read_page_object(index, leaf)
            self._counters["object_verifications"] += 1
            try:
                decoded = zlib.decompress(physical)
            except zlib.error as exc:
                raise PageUnavailable(
                    "corrupt", f"page {index} cannot be decoded", pages=[index]
                ) from exc
            if (
                len(decoded) != leaf.decoded_bytes
                or hashlib.sha256(decoded).hexdigest() != leaf.decoded_sha256
            ):
                raise PageUnavailable(
                    "corrupt", f"page {index} decoded identity mismatches", pages=[index]
                )
            self._counters["object_verifications"] += 1
            page = np.frombuffer(decoded, dtype="<u4").astype("<f8")
            words = memoryview(page)
            digest.update(words)
            previous_object = leaf.object_sha256
            previous_decoded = leaf.decoded_sha256
            previous_words = words
        return digest.hexdigest()

    def state_identity_sha256(self) -> str:
        """Persistent exact identity; wide page trees avoid a dense rehash."""

        if self.state_sha256_kind == PAGED_STATE_KIND_ROOT:
            return paged_root_state_sha256(
                self.profile,
                self.root_sha256,
                self.page_count,
            )
        return self.logical_state_sha256()

    def residency_report(self) -> dict[str, Any]:
        live = {leaf.object_sha256 for leaf in self.directory.leaves if leaf}
        unique_bytes = sum(leaf.object_bytes for leaf in self.directory.leaves if leaf)
        decoded_bytes = sum(leaf.decoded_bytes for leaf in self.directory.leaves if leaf)
        resident_words = sum(int(page.size) for page in self._resident.values())
        return {
            "schema": "cassifi.regional-residency.v1",
            "page_words": PERSISTENCE_PAGE_WORDS,
            "page_count": self.page_count,
            "committed_pages": len(self.directory.leaves),
            "implicit_zero_pages": self.page_count - len(self.directory.leaves),
            "logical_words": self.profile.total_words,
            "resident_pages": len(self._resident),
            "resident_limit": self.resident_limit,
            "resident_words": resident_words,
            "resident_high_water_pages": self._counters["resident_high_water_pages"],
            "pinned_pages": len(self._pinned),
            "unique_physical_bytes": unique_bytes,
            "decoded_physical_bytes": decoded_bytes,
            "validated_pages": len(self._validated_pages),
            "unvalidated_pages": self.page_count - len(self._validated_pages),
            "live_objects": len(live),
            "backing_kind": type(self.objects).__name__,
            "object_verifications": self._counters["object_verifications"],
            "deferred_object_verifications": self._counters["deferred_object_verifications"],
            "pending_prefetches": len(self._prefetch_sessions),
            "pending_prefetched_pages": len(self._prefetched_pages),
            "resources": self._resource_manager.report(),
            **{key: value for key, value in self._counters.items()},
        }

    def object_store(self) -> Mapping[str, bytes]:
        """Return a lazy metadata-only view of referenced objects."""

        referenced = {
            leaf.object_sha256
            for leaf in self.directory.leaves
            if leaf is not None
        }
        return ObjectSubset(self.objects, referenced)

    def missing_objects(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                leaf.object_sha256
                for leaf in self.directory.leaves
                if leaf is not None and leaf.object_sha256 not in self.objects
            )
        )

    # -- publication -----------------------------------------------------

    def successor(
        self,
        directory: PageDirectory,
        objects: Mapping[str, bytes],
        *,
        transition: Mapping[str, Any] | None = None,
        audited_state_sha256: str | None = None,
        _changed_page_digests: Mapping[int, str] | None = None,
    ) -> "PagedFieldImage":
        identity_kind = (
            PAGED_STATE_KIND_FLAT
            if audited_state_sha256 is not None
            else (
                PAGED_STATE_KIND_ROOT
                if self.profile.neural_membrane
                or self.page_count > MAX_RESIDENCY_PAGES
                else PAGED_STATE_KIND_FLAT
            )
        )
        predecessor = {
            "root_sha256": self.root_sha256,
            "state_sha256": self.state_identity_sha256(),
            "layout": REGIONAL_LAYOUT,
        }
        if self.state_sha256_kind != PAGED_STATE_KIND_FLAT:
            predecessor["state_sha256_kind"] = self.state_sha256_kind
        next_tree = (
            None
            if _changed_page_digests is None
            else self._tree.updated(_changed_page_digests)
        )
        successor = PagedFieldImage(
            self.profile, self.catalog, directory, objects,
            resident_limit=self.resident_limit, dirty_limit=self.dirty_limit,
            predecessor=predecessor, transition=transition or self.transition,
            revoked_roots=self.revoked_roots,
            audited_state_sha256=audited_state_sha256,
            state_sha256_kind=identity_kind, pinned=self._pinned,
            previous_tree=self._tree if next_tree is None else None,
            _page_tree=next_tree,
            _objects_verified=True,
            tier_store=self._tier_store,
            resource_manager=self._resource_manager, program_id=self.program_id,
        )
        self.release_resident()
        return successor

    def with_backing(self, store: Mapping[str, bytes]) -> "PagedFieldImage":
        """Publish referenced objects to ``store`` and switch to that backing."""
        put = getattr(store, "put", None)
        if not callable(put):
            raise RegionalFieldError("backing store must expose put(raw, digest=...)")
        refs = self.object_store()
        for key in refs:
            put(refs[key], digest=key)
        successor = PagedFieldImage(
            self.profile, self.catalog, self.directory, store,
            resident_limit=self.resident_limit, dirty_limit=self.dirty_limit,
            predecessor=self.predecessor, transition=self.transition,
            revoked_roots=self.revoked_roots,
            audited_state_sha256=self.audited_state_sha256,
            state_sha256_kind=self.state_sha256_kind, pinned=self._pinned,
            _page_tree=self._tree,
            tier_store=self._tier_store,
            resource_manager=self._resource_manager, program_id=self.program_id,
        )
        self.release_resident()
        return successor

    def descriptor(self, **blocks: Any) -> dict[str, Any]:
        """The durable paged descriptor: root plus its bound identity blocks."""
        value = {
            "schema": PAGED_MANIFEST_SCHEMA,
            "layout": REGIONAL_LAYOUT,
            "profile": self.profile.as_dict(),
            "profile_sha256": self.profile.fingerprint,
            "catalog_sha256": self.catalog.fingerprint,
            "page_words": PERSISTENCE_PAGE_WORDS,
            "byte_order": "little",
            "word_encoding": "u32",
            "pages": self.directory.records(),
            "page_count": self.page_count,
            "root_sha256": self.root_sha256,
            "segments": {name: list(pages) for name, pages in self.segments().items()},
            "control_pages": list(self.control_closure()),
            "predecessor": self.predecessor,
            "transition": self.transition,
            "resource": self.resource_limits.as_dict(),
        }
        if self.resident_limit != DEFAULT_RESIDENT_PAGES:
            value["resident_limit"] = self.resident_limit
        if self.dirty_limit != DEFAULT_DIRTY_PAGES:
            value["dirty_limit"] = self.dirty_limit
        value["state_sha256"] = self.state_identity_sha256()
        if self.state_sha256_kind != PAGED_STATE_KIND_FLAT:
            value["state_sha256_kind"] = self.state_sha256_kind
        for key, block in blocks.items():
            if block is not None:
                value[key] = block
        return value

    def chunks(self) -> tuple[list[dict[str, Any]], Mapping[str, bytes]]:
        """The established chunked checkpoint view of this image."""

        return self.directory.records(), self.object_store()


class _SegmentReader:
    """Bounded word reader used for structural inspection only."""

    __slots__ = ("_image",)

    def __init__(self, image: PagedFieldImage) -> None:
        self._image = image

    def words(self, start: int, length: int) -> np.ndarray:
        out = np.zeros(length, dtype=np.float64)
        first = start // PERSISTENCE_PAGE_WORDS
        last = (start + length - 1) // PERSISTENCE_PAGE_WORDS
        for index in range(first, last + 1):
            page = self._image._page(index, record_prefetch_use=False)
            base = index * PERSISTENCE_PAGE_WORDS
            lo = max(start, base)
            hi = min(start + length, base + page.size)
            out[lo - start:hi - start] = page[lo - base:hi - base]
        return out


class PagedFieldStaging:
    """Private dirty pages for one uncommitted transition.

    Reads fall through the overlay, spilled staging chunks, resident pages,
    and storage.  Writes never touch the committed image, so an abandoned
    transition is discarded rather than repaired, and a crash before
    publication leaves the predecessor untouched.
    """

    __slots__ = (
        "image",
        "stage",
        "dirty",
        "staging_objects",
        "spilled",
        "counters",
        "_dirty_order",
        "_parent",
        "dirty_limit",
        "_staging_tokens",
    )

    def __init__(
        self,
        image: PagedFieldImage,
        *,
        stage: str = "transition",
        parent: "PagedFieldStaging | None" = None,
        dirty_limit: int | None = None,
    ) -> None:
        self.image = image
        self.stage = str(stage)
        self.dirty_limit = (
            image.dirty_limit
            if dirty_limit is None
            else _integer(
                dirty_limit, "dirty page limit", minimum=1, maximum=MAX_RESIDENCY_PAGES
            )
        )
        self.dirty: dict[int, np.ndarray] = {}
        self.staging_objects: dict[str, bytes] = {}
        self._staging_tokens: dict[int, Any] = {}
        self.spilled: dict[int, PageLeaf] = {}
        self._dirty_order: list[int] = []
        self._parent = parent
        self.counters: dict[str, int] = {
            "staged_pages": 0,
            "staged_words": 0,
            "spilled_pages": 0,
            "detached_writes": 0,
            "windows": 0,
            "window_pages": 0,
        }

    @property
    def page_count(self) -> int:
        return self.image.page_count

    @property
    def profile(self) -> "RegionalProfile":
        return self.image.profile

    def view(self, *, write: bool = True) -> "_PagedFieldView":
        return _PagedFieldView(self.image, self, write=write)

    def page(
        self, index: int, *, record_prefetch_use: bool = True
    ) -> np.ndarray:
        target = _integer(index, "page index", maximum=self.page_count - 1)
        page = self.dirty.get(target)
        if page is not None:
            self._touch(target)
            return page
        leaf = self.spilled.get(target)
        if leaf is not None:
            return self._decode_staged(target, leaf)
        if self._parent is not None:
            return self._parent.page(
                target, record_prefetch_use=record_prefetch_use
            )
        return self.image._page(
            target, record_prefetch_use=record_prefetch_use
        )

    def _leaf_in_chain(self, index: int) -> PageLeaf | None:
        node: PagedFieldStaging | None = self
        while node is not None:
            leaf = node.spilled.get(index)
            if leaf is not None:
                return leaf
            if index in node.dirty:
                return None
            node = node._parent
        return None

    def _object_in_chain(self, object_sha256: str) -> bytes | None:
        node: PagedFieldStaging | None = self
        while node is not None:
            value = node.staging_objects.get(object_sha256)
            if value is not None:
                return value
            node = node._parent
        try:
            return self.image.objects[object_sha256]
        except (KeyError, StorageError):
            return None

    def _chain(self) -> list["PagedFieldStaging"]:
        chain: list[PagedFieldStaging] = []
        node: PagedFieldStaging | None = self
        while node is not None:
            chain.append(node)
            node = node._parent
        return chain

    def _decode_staged(self, index: int, leaf: PageLeaf) -> np.ndarray:
        physical = self._object_in_chain(leaf.object_sha256)
        if physical is None:
            raise PageUnavailable(
                "missing", f"staged page {index} is absent", pages=[index]
            )
        try:
            decoded = zlib.decompress(physical)
        except zlib.error as exc:
            raise PageUnavailable("corrupt", f"staged page {index} is corrupt", pages=[index]) from exc
        if hashlib.sha256(decoded).hexdigest() != leaf.decoded_sha256:
            raise PageUnavailable("corrupt", f"staged page {index} is corrupt", pages=[index])
        return np.frombuffer(decoded, dtype="<u4").astype(np.float64)

    def _touch(self, index: int) -> None:
        order = self._dirty_order
        try:
            order.remove(index)
        except ValueError:  # pragma: no cover - defensive
            pass
        order.append(index)

    def stage_page(self, index: int) -> np.ndarray:
        """Return a writable overlay page, copying the committed page once."""

        target = _integer(index, "page index", maximum=self.page_count - 1)
        page = self.dirty.get(target)
        if page is not None:
            self._touch(target)
            return page
        leaf = self.spilled.pop(target, None)
        source = (
            self._decode_staged(target, leaf)
            if leaf is not None
            else (
                self._parent.page(target, record_prefetch_use=False)
                if self._parent is not None
                else self.image._page(target, record_prefetch_use=False)
            )
        )
        overlay = np.array(source, copy=True)
        needed = max(1, int(overlay.nbytes))
        try:
            token = self.image.resource_manager.reserve(
                "ram", needed, kind="scratch",
                program_id=self.image.program_id,
            )
        except ResourceWait:
            # A staging page is paid for out of the cache before the machine
            # is asked to grow anything.
            self.spill_if_needed()
            self.image.release_to_fit("ram", needed)
            token = self.image.resource_manager.reserve(
                "ram", needed, kind="scratch",
                program_id=self.image.program_id,
            )
        self.dirty[target] = overlay
        self._staging_tokens[target] = token
        self._touch(target)
        self.counters["staged_pages"] += 1
        self.counters["staged_words"] += int(overlay.size)
        self.spill_if_needed()
        return overlay

    def spill_if_needed(self) -> None:
        while len(self.dirty) > self.dirty_limit:
            spare = [key for key in self._dirty_order if key in self.dirty]
            if not spare:
                return
            victim = spare[0]
            self.spill(victim)

    def spill(self, index: int) -> None:
        """Spill one dirty page to an immutable, unpublished staging chunk."""

        page = self.dirty.pop(index, None)
        token = self._staging_tokens.pop(index, None)
        if page is None:
            if token is not None:
                token.release()
            return
        try:
            self._dirty_order.remove(index)
        except ValueError:  # pragma: no cover - defensive
            pass
        decoded = _encode_page(page)
        if decoded is None:
            self.spilled.pop(index, None)
            if token is not None:
                token.release()
            return
        physical = zlib.compress(decoded, level=6)
        object_sha = hashlib.sha256(physical).hexdigest()
        backing = self.image.objects
        if object_sha not in backing:
            put = getattr(backing, "put", None)
            if callable(put):
                put(physical, digest=object_sha)
            else:
                self.staging_objects.setdefault(object_sha, physical)
        self.spilled[index] = PageLeaf(
            index=index,
            start_word=index * PERSISTENCE_PAGE_WORDS,
            words=int(page.size),
            decoded_bytes=len(decoded),
            decoded_sha256=hashlib.sha256(decoded).hexdigest(),
            object_bytes=len(physical),
            object_sha256=object_sha,
        )
        if token is not None:
            token.release()
        self.counters["spilled_pages"] += 1
    def stage_words(self, offsets: Sequence[int], values: Sequence[float]) -> None:
        """Stage a vector write while touching each changed page only once."""

        raw_offsets = np.asarray(offsets, dtype=np.int64).reshape(-1)
        raw_values = np.asarray(values, dtype=np.float64).reshape(-1)
        count = min(raw_offsets.size, raw_values.size)
        if count == 0:
            return
        raw_offsets = raw_offsets[:count]
        raw_values = raw_values[:count]
        page_indices = raw_offsets // PERSISTENCE_PAGE_WORDS
        if not np.all(page_indices[:-1] <= page_indices[1:]):
            order = np.argsort(page_indices, kind="stable")
            raw_offsets = raw_offsets[order]
            raw_values = raw_values[order]
            page_indices = page_indices[order]
        indexes, starts = np.unique(page_indices, return_index=True)
        ends = np.empty_like(starts)
        ends[:-1] = starts[1:]
        ends[-1] = count
        for index, start, end in zip(indexes, starts, ends):
            local_offsets = (
                raw_offsets[start:end] % PERSISTENCE_PAGE_WORDS
            ).astype(np.int64, copy=False)
            selected_values = raw_values[start:end]
            unique_offsets = np.unique(local_offsets).size == local_offsets.size
            if unique_offsets and np.array_equal(
                self.page(int(index), record_prefetch_use=False)[local_offsets],
                selected_values,
            ):
                continue
            page = self.stage_page(int(index))
            if unique_offsets:
                page[local_offsets] = selected_values
            else:
                for offset, value in zip(local_offsets, selected_values):
                    page[int(offset)] = float(value)
    def stage_u32_words(self, offsets: Sequence[int], values: Sequence[int]) -> None:
        """Stage exact u32 operations through the canonical float64 carrier."""

        packed = np.asarray(values)
        if packed.ndim != 1 or packed.dtype.kind not in {"i", "u"}:
            raise RegionalFieldError("u32 values must be a one-dimensional integer sequence")
        if packed.size and (np.any(packed < 0) or np.any(packed > U32_MAX)):
            raise RegionalFieldError("u32 value is outside the exact carrier range")
        self.stage_words(offsets, packed.astype(np.float64, copy=False))

    def stage_u32_span(self, start: int, values: Sequence[int] | np.ndarray) -> None:
        """Stage a contiguous exact-u32 write without a float conversion buffer."""

        target = _integer(start, "u32 span offset", maximum=self.profile.total_words)
        packed = np.asarray(values)
        if packed.ndim != 1 or packed.dtype.kind not in {"i", "u"}:
            raise RegionalFieldError("u32 values must be a one-dimensional integer sequence")
        if packed.size and (
            np.any(packed < 0) or np.any(packed > U32_MAX)
        ):
            raise RegionalFieldError("u32 value is outside the exact carrier range")
        end = target + int(packed.size)
        if end > self.profile.total_words:
            raise RegionalFieldError("u32 span exceeds the field address range")
        cursor = 0
        while cursor < packed.size:
            offset = target + cursor
            index = offset // PERSISTENCE_PAGE_WORDS
            local = offset % PERSISTENCE_PAGE_WORDS
            count = min(
                packed.size - cursor,
                self.image.directory.page_words(self.profile.total_words, index) - local,
            )
            selected = packed[cursor:cursor + count]
            source = self.page(index, record_prefetch_use=False)
            if not np.array_equal(source[local:local + count], selected):
                page = self.stage_page(index)
                page[local:local + count] = selected
            cursor += count

    def fill(self, start: int, length: int, value: float) -> None:
        if length <= 0:
            return
        first = start // PERSISTENCE_PAGE_WORDS
        last = (start + length - 1) // PERSISTENCE_PAGE_WORDS
        for index in range(first, last + 1):
            base = index * PERSISTENCE_PAGE_WORDS
            lo = max(start, base)
            hi = min(start + length, base + self.image.directory.page_words(
                self.profile.total_words, index
            ))
            start_in_page = lo - base
            end_in_page = hi - base
            source = self.page(index, record_prefetch_use=False)
            if np.all(source[start_in_page:end_in_page] == value):
                continue
            page = self.stage_page(index)
            page[start_in_page:end_in_page] = value

    def spawn(self, *, stage: str | None = None) -> "PagedFieldStaging":
        """Nested staging for a trial transition that can be discarded whole."""

        return PagedFieldStaging(
            self.image,
            stage=stage or self.stage,
            parent=self,
            dirty_limit=self.dirty_limit,
        )

    def changed_pages(self) -> tuple[int, ...]:
        changed: set[int] = set()
        for node in self._chain():
            changed |= set(node.dirty) | set(node.spilled)
        return tuple(sorted(changed))

    def release_overlay(self) -> None:
        """Return this overlay's reservations and drop its staged pages.

        A committed chain is one transaction: its successor carries the merged
        content of every node, and the caller that spawned a trial drops the
        parent once the trial is done with it.  Nothing reads a spent overlay
        again, so its staged pages and their scratch reservations leave here
        rather than staying charged to a manager that no live state can
        release them from.
        """

        for token in self._staging_tokens.values():
            token.release()
        self._staging_tokens.clear()
        self.dirty.clear()
        self.spilled.clear()
        self.staging_objects.clear()
        self._dirty_order.clear()

    def release_chain(self) -> None:
        """End this transaction: release every overlay in the spawn chain."""

        for node in self._chain():
            node.release_overlay()

    def commit(
        self,
        *,
        blocks: Mapping[str, Any] | None = None,
        audit_digest: bool = False,
        require_clean: bool = True,
    ) -> tuple[PagedFieldImage, dict[str, Any]]:
        """Publish this overlay as the successor image.

        Immutable chunks are written before the successor descriptor that
        references them; unchanged pages keep their leaf records and objects.
        """

        if require_clean and self.counters["detached_writes"]:
            raise RegionalFieldError(
                "staged transition contains writes detached from the page store"
            )
        pre_root = self.image.root_sha256
        chain = self._chain()
        changed: dict[int, PageLeaf | None] = {}
        new_objects: dict[str, bytes] = {}
        reused = 0
        changed_indices: set[int] = set()
        for node in chain:
            changed_indices |= set(node.dirty) | set(node.spilled)
        for index in sorted(changed_indices):
            leaf = self._leaf_in_chain(index)
            page = None
            for node in chain:
                if index in node.dirty:
                    page = node.dirty[index]
                    break
            if page is None:
                if leaf is None:  # pragma: no cover - defensive
                    continue
                previous = self.image.directory.leaf(index)
                if previous is not None and previous.digest == leaf.digest:
                    reused += 1
                    continue
                changed[index] = leaf
                physical = self._object_in_chain(leaf.object_sha256)
                if physical is None:  # pragma: no cover - defensive
                    raise PageUnavailable("missing", leaf.object_sha256)
                new_objects[leaf.object_sha256] = physical
                continue
            decoded = _encode_page(page)
            if decoded is None:
                if self.image.directory.leaf(index) is None:
                    continue
                changed[index] = None
                continue
            physical = zlib.compress(decoded, level=6)
            object_sha = hashlib.sha256(physical).hexdigest()
            leaf = PageLeaf(
                index=index,
                start_word=index * PERSISTENCE_PAGE_WORDS,
                words=int(page.size),
                decoded_bytes=len(decoded),
                decoded_sha256=hashlib.sha256(decoded).hexdigest(),
                object_bytes=len(physical),
                object_sha256=object_sha,
            )
            previous = self.image.directory.leaf(index)
            if previous is not None and previous.digest == leaf.digest:
                reused += 1
                continue
            changed[index] = leaf
            new_objects[object_sha] = physical
        directory = self.image.directory.with_changes(self.profile, changed)
        merged_objects: Mapping[str, bytes] = ObjectOverlay(new_objects, self.image.objects)
        backing_put = getattr(self.image.objects, "put", None)
        if callable(backing_put):
            for digest, physical in new_objects.items():
                backing_put(physical, digest=digest)
            merged_objects = self.image.objects
        live_objects = {
            leaf.object_sha256 for leaf in directory.leaves if leaf is not None
        }
        objects: Mapping[str, bytes] = ObjectSubset(merged_objects, live_objects)
        changed_tree_digests = {
            index: (
                leaf.digest
                if leaf is not None
                else _zero_page_digest(
                    index,
                    index * PERSISTENCE_PAGE_WORDS,
                    directory.page_words(self.profile.total_words, index),
                )
            )
            for index, leaf in changed.items()
        }
        successor = self.image.successor(
            directory,
            objects,
            transition={"kind": "storage-only"},
            _changed_page_digests=changed_tree_digests,
        )
        successor._validated_pages = {
            index
            for index in self.image._validated_pages
            if index not in changed
        }
        successor._counters["objects_written"] = len(new_objects)
        successor._counters["objects_reused"] = reused
        shared = successor.tree.shared_nodes(self.image.tree)
        receipt = {
            "schema": PAGED_MANIFEST_SCHEMA,
            "kind": "paged-commit",
            "stage": self.stage,
            "predecessor_root_sha256": pre_root,
            "root_sha256": successor.root_sha256,
            "changed_pages": sorted(changed),
            "released_pages": sorted(
                index for index, leaf in changed.items() if leaf is None
            ),
            "unchanged_leaf_pages": reused,
            "objects_written": len(new_objects),
            "object_bytes_written": sum(len(value) for value in new_objects.values()),
            "tree_nodes": successor.tree.root.nodes(),
            "tree_nodes_shared": shared,
            "staging": dict(self.counters),
            "residency": successor.residency_report(),
        }
        if audit_digest:
            digest = successor.logical_state_sha256()
            object.__setattr__  # noqa: B018 - successor is mutable by design
            successor.audited_state_sha256 = digest
            successor.state_sha256_kind = PAGED_STATE_KIND_FLAT
            receipt["state_sha256"] = digest
        if blocks:
            receipt["blocks"] = {key: value for key, value in blocks.items()}
        self.release_chain()
        return successor, receipt

    def discard(self) -> dict[str, Any]:
        report = dict(self.counters)
        self.release_overlay()
        return {"schema": PAGED_MANIFEST_SCHEMA, "kind": "paged-discard", **report}


class _PagedWindow(np.ndarray):
    """A bounded materialised window whose writes stage into its overlay.

    The regional machine mutates descriptor rows and payload ranges through
    ordinary numpy views.  This subclass preserves those semantics over paged
    storage: reads use the materialised window, and every write additionally
    lands in the staged successor pages, so the committed image is never
    modified in place.
    """

    def __new__(
        cls,
        buffer: np.ndarray,
        *,
        staging: "PagedFieldStaging | None",
        logical_start: int,
    ) -> "_PagedWindow":
        window = np.asarray(buffer, dtype=np.float64).view(cls)
        window._staging = staging
        window._logical_start = int(logical_start)
        window._root = window
        window._root_start = int(logical_start)
        return window

    def __array_finalize__(self, obj: Any) -> None:
        if obj is None:
            return
        self._staging = getattr(obj, "_staging", None)
        self._logical_start = getattr(obj, "_logical_start", 0)
        self._root = getattr(obj, "_root", None)
        self._root_start = getattr(obj, "_root_start", 0)

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self._stage(key)

    def _stage(self, key: Any) -> None:
        staging = getattr(self, "_staging", None)
        root = getattr(self, "_root", None)
        if staging is None or root is None:
            return
        if self.base is not None and not np.shares_memory(self, root):
            staging.counters["detached_writes"] += 1
            return
        if not np.shares_memory(self, root):
            staging.counters["detached_writes"] += 1
            return
        offset_bytes = self.ctypes.data - root.ctypes.data
        if offset_bytes < 0 or offset_bytes % self.itemsize:
            staging.counters["detached_writes"] += 1
            return
        index = np.arange(self.size).reshape(self.shape)[key]
        positions = np.asarray(index).reshape(-1)
        if positions.size == 0:
            return
        written = np.asarray(self)[key]
        values = np.asarray(written, dtype=np.float64).reshape(-1)
        if values.size == 1 and positions.size > 1:
            values = np.full(positions.size, float(values[0]))
        if values.size != positions.size:
            staging.counters["detached_writes"] += 1
            return
        base = offset_bytes // self.itemsize
        offsets = (getattr(root, "_root_start", 0) + base) + positions.astype(np.int64)
        staging.stage_words(offsets, values)


class _PagedFieldView:
    """Bounded, paged address space with the slice semantics of a flat image."""

    __slots__ = (
        "_image", "_staging", "_write", "_total", "_track_prefetch_use",
    )

    def __init__(
        self,
        image: PagedFieldImage,
        staging: PagedFieldStaging | None,
        *,
        write: bool = False,
        track_prefetch_use: bool = True,
    ) -> None:
        self._image = image
        self._staging = staging
        self._write = bool(write)
        self._total = image.profile.total_words
        self._track_prefetch_use = bool(track_prefetch_use)

    def _page(self, index: int) -> np.ndarray:
        if self._staging is not None:
            return self._staging.page(
                index, record_prefetch_use=self._track_prefetch_use
            )
        return self._image._page(
            index, record_prefetch_use=self._track_prefetch_use
        )


    # -- array-like surface used by the regional machine -----------------

    @property
    def shape(self) -> tuple[int]:
        return (self._total,)

    @property
    def ndim(self) -> int:
        return 1

    @property
    def size(self) -> int:
        return self._total

    @property
    def dtype(self) -> np.dtype:
        return np.dtype(np.float64)

    def __len__(self) -> int:
        return self._total

    def reshape(self, *shape: Any) -> "_PagedFieldView":
        resolved = shape[0] if len(shape) == 1 else shape
        if resolved in ((-1,), (self._total,), (1, self._total, 1)):
            return self
        raise RegionalFieldError("paged view supports only flat logical reshape")

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, slice):
            start, stop, step = key.indices(self._total)
            if step != 1:
                raise RegionalFieldError("paged view does not support strided access")
            return self.window(start, stop)
        if isinstance(key, (int, np.integer)) and not isinstance(key, bool):
            offset = int(key)
            if offset < 0:
                offset += self._total
            if not 0 <= offset < self._total:
                raise RegionalFieldError("paged view index is out of range")
            return float(self._read_word(offset))
        raise RegionalFieldError("paged view requires an integer or slice index")

    def __setitem__(self, key: Any, value: Any) -> None:
        if not self._write or self._staging is None:
            raise RegionalFieldError("paged view is read-only")
        if isinstance(key, slice):
            start, stop, step = key.indices(self._total)
            if step != 1:
                raise RegionalFieldError("paged view does not support strided writes")
            if np.isscalar(value):
                self._staging.fill(start, stop - start, float(value))
                return
            raw = np.asarray(value)
            if (
                raw.ndim == 1
                and raw.size == stop - start
                and raw.dtype.kind in {"i", "u"}
                and (
                    not raw.size
                    or (np.all(raw >= 0) and np.all(raw <= U32_MAX))
                )
            ):
                self._staging.stage_u32_span(start, raw)
                return
            window = self.window(start, stop)
            window[...] = np.asarray(raw, dtype=np.float64)
            return
        if isinstance(key, (int, np.integer)) and not isinstance(key, bool):
            offset = int(key)
            if offset < 0:
                offset += self._total
            if not 0 <= offset < self._total:
                raise RegionalFieldError("paged view index is out of range")
            if (
                isinstance(value, (int, np.integer))
                and not isinstance(value, (bool, np.bool_))
                and 0 <= value <= U32_MAX
            ):
                self._staging.stage_u32_words([offset], [int(value)])
            else:
                self._staging.stage_words([offset], [float(value)])
            return
        raise RegionalFieldError("paged view requires an integer or slice index")

    # -- bounded windows -------------------------------------------------

    def window(self, start: int, stop: int) -> _PagedWindow:
        """Materialise ``[start, stop)`` within the declared residency bound."""

        start = _integer(start, "window start", maximum=self._total)
        stop = _integer(stop, "window stop", maximum=self._total)
        if stop < start:
            raise RegionalFieldError("paged window range is reversed")
        length = stop - start
        if length == 0:
            return _PagedWindow(
                np.zeros(0, dtype=np.float64),
                staging=self._staging,
                logical_start=start,
            )
        first = start // PERSISTENCE_PAGE_WORDS
        last = (stop - 1) // PERSISTENCE_PAGE_WORDS
        page_span = last - first + 1
        limit = self._image.resident_limit
        if page_span > limit:
            # An indivisible working set beyond the allowance suspends for
            # resources rather than allocating past the declared bound.
            segments = self._image.segments()
            span = tuple(range(first, last + 1))
            raise ResidencyWait(
                "window",
                span,
                versions=[
                    self._image.tree.digest(index) for index in span
                ],
                reason="resource",
                allowance=limit,
                work=length,
                segments=[
                    name
                    for name, segment_pages in segments.items()
                    if any(index in segment_pages for index in span)
                ],
            )
        buffer = np.empty(length, dtype=np.float64)
        for index in range(first, last + 1):
            page = self._page(index)
            base = index * PERSISTENCE_PAGE_WORDS
            lo = max(start, base)
            hi = min(stop, base + page.size)
            buffer[lo - start:hi - start] = page[lo - base:hi - base]
        staging = self._staging
        if staging is not None:
            staging.counters["windows"] += 1
            staging.counters["window_pages"] += page_span
        return _PagedWindow(buffer, staging=staging, logical_start=start)

    def _read_word(self, offset: int) -> float:
        index = offset // PERSISTENCE_PAGE_WORDS
        page = self._page(index)
        return float(page[offset % PERSISTENCE_PAGE_WORDS])

    def read_region(self, ref: "RegionRef") -> Any:
        return _read_region(self, self._image.profile, ref)

    def object(self, object_id: int) -> Any:
        return _read_region(
            self,
            self._image.profile,
            _resolve_object(self, self._image.profile, object_id),
        )

    def named_values(self, names: Sequence[str]) -> dict[str, Any]:
        queue = _read_region(self, self._image.profile, _queue_ref(self))
        return {
            name: _read_region(
                self,
                self._image.profile,
                _resolve_object(
                    self,
                    self._image.profile,
                    _integer(queue["named_values"].get(name), "named object ID", minimum=1),
                ),
            )
            for name in names
        }


def validate_paged_delta(
    predecessor: PagedFieldImage,
    successor: PagedFieldImage,
    *,
    changed_pages: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Incremental validation of a paged successor.

    The immutable predecessor was validated at admission or by an earlier
    delta, and every chunk is verified against its decoded-content identity
    when it is loaded.  This check re-establishes the structural invariants
    that changed pages can affect: header/profile agreement, directory
    geometry, payload disjointness, descriptor words, and counter bounds.
    """

    profile = successor.profile
    reader = _SegmentReader(successor)
    header = reader.words(0, HEADER_WORDS)
    if (
        int(header[H_MAGIC]) != REGIONAL_MAGIC
        or int(header[H_LAYOUT_REVISION]) != REGIONAL_LAYOUT_REVISION
        or int(header[H_TOTAL_WORDS]) != profile.total_words
        or int(header[H_DIRECTORY_CAPACITY]) != profile.directory_capacity
    ):
        raise RegionalFieldError("paged image header mismatches its profile")
    if tuple(int(word) for word in header[H_PROFILE_SHA:H_PROFILE_SHA + 8]) != _sha_words(
        profile.fingerprint
    ):
        raise RegionalFieldError("paged image header profile digest mismatches")
    if tuple(int(word) for word in header[H_CATALOG_SHA:H_CATALOG_SHA + 8]) != _sha_words(
        successor.catalog.fingerprint
    ):
        raise RegionalFieldError("paged image header catalog digest mismatches")
    clock = _read_u64(header, H_CLOCK)
    if clock > U64_MAX - 1:
        raise RegionalFieldError("paged image clock is out of range")
    if int(header[H_STATUS]) not in STATUS_NAMES:
        raise RegionalFieldError("paged image status is invalid")
    if int(header[H_REASON]) not in REASON_NAMES:
        raise RegionalFieldError("paged image reason is invalid")
    arena_start = HEADER_WORDS + DIRECTORY_WORDS * profile.directory_capacity
    ranges: list[tuple[int, int, int]] = []
    for slot in range(1, profile.directory_capacity + 1):
        row = reader.words(HEADER_WORDS + (slot - 1) * DIRECTORY_WORDS, DIRECTORY_WORDS)
        if _read_u64(row, D_VERSION) > U64_MAX:
            raise RegionalFieldError("paged image region version is out of range")
        flags = int(row[D_FLAGS])
        if not flags & (FLAG_LIVE | FLAG_QUARANTINED):
            continue
        base, used, capacity = int(row[D_BASE]), int(row[D_USED]), int(row[D_CAPACITY])
        if not arena_start <= base <= base + capacity <= profile.workspace_words:
            raise RegionalFieldError("paged image region range is outside the arena")
        if used > capacity:
            raise RegionalFieldError("paged image region usage exceeds its capacity")
        if int(row[D_KIND]) not in KIND_NAMES or int(row[D_CODEC]) not in (CODEC_JSON, CODEC_WORDS):
            raise RegionalFieldError("paged image region kind or codec is invalid")
        if int(row[D_GENERATION]) <= 0:
            raise RegionalFieldError("paged image live region has no generation")
        ranges.append((base, base + capacity, slot))
    ranges.sort()
    for (start, stop, slot), (next_start, _next_stop, next_slot) in zip(ranges, ranges[1:]):
        if stop > next_start:
            raise RegionalFieldError(
                f"paged image regions overlap (slots {slot} and {next_slot})"
            )
    changed = (
        tuple(int(index) for index in changed_pages)
        if changed_pages is not None
        else None
    )
    if changed is not None:
        for index in changed:
            leaf = successor.directory.leaf(index)
            if leaf is None:
                continue
            page = successor._page(index, record_prefetch_use=False)
            if (
                not np.isfinite(page).all()
                or not np.equal(page, np.floor(page)).all()
                or np.any(page < 0)
                or np.any(page > U32_MAX)
            ):
                raise RegionalFieldError("paged image page is not a canonical u32 image")
    return {
        "schema": PAGED_MANIFEST_SCHEMA,
        "kind": "paged-delta-validation",
        "predecessor_root_sha256": predecessor.root_sha256,
        "root_sha256": successor.root_sha256,
        "changed_pages": list(changed or ()),
        "checked_slots": profile.directory_capacity,
        "checked_pages": len(successor._validated_pages),
    }


def validate_paged_structure(image: PagedFieldImage) -> dict[str, Any]:
    """Bounded structural validation of one paged image.

    Reads the control closure only: identity words, the committed directory,
    and the named regions the machine dereferences.  Page contents are bound
    by their recorded digests and verified when a page is decoded, so a
    bounded check is the paged analogue of holding a validated dense image;
    ``validate_paged_image`` is the declared full audited read.
    """

    profile = image.profile
    catalog = image.catalog
    header = image.header_words(0, HEADER_WORDS)
    directory = image.header_words(
        HEADER_WORDS, DIRECTORY_WORDS * profile.directory_capacity
    ).reshape(profile.directory_capacity, DIRECTORY_WORDS)
    if (
        int(header[H_MAGIC]) != REGIONAL_MAGIC
        or int(header[H_LAYOUT_REVISION]) != REGIONAL_LAYOUT_REVISION
    ):
        raise RegionalFieldError("paged header identity is invalid")
    if (
        int(header[H_TOTAL_WORDS]) != profile.total_words
        or int(header[H_DIRECTORY_CAPACITY]) != profile.directory_capacity
    ):
        raise RegionalFieldError("paged header geometry is invalid")
    if (
        _words_sha(
            [int(word) for word in header[H_PROFILE_SHA:H_PROFILE_SHA + 8]]
        )
        != profile.fingerprint
    ):
        raise RegionalFieldError("paged profile digest is invalid")
    if (
        _words_sha(
            [int(word) for word in header[H_CATALOG_SHA:H_CATALOG_SHA + 8]]
        )
        != catalog.fingerprint
    ):
        raise RegionalFieldError("paged catalog digest is invalid")
    if int(header[H_STATUS]) not in STATUS_NAMES or int(
        header[H_REASON]
    ) not in REASON_NAMES:
        raise RegionalFieldError("paged status or reason is invalid")
    committed = image.directory.tree(profile, previous=image.tree)
    if committed.root_sha256 != image.root_sha256:
        raise RegionalFieldError("paged page root does not match its directory")
    if image.audited_state_sha256 is not None and (
        len(image.audited_state_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in image.audited_state_sha256
        )
    ):
        raise RegionalFieldError("paged audited state digest is invalid")
    live = 0
    for row in directory:
        flags = int(row[D_FLAGS])
        if not flags & (FLAG_LIVE | FLAG_QUARANTINED):
            continue
        live += 1
        if int(row[D_KIND]) not in KIND_NAMES:
            raise RegionalFieldError("paged directory kind is invalid")
        if int(row[D_CODEC]) not in (CODEC_JSON, CODEC_WORDS):
            raise RegionalFieldError("paged directory codec is invalid")
        base = int(row[D_BASE])
        capacity = int(row[D_CAPACITY])
        if capacity <= 0 or base + capacity > profile.workspace_words:
            raise RegionalFieldError("paged region extent is outside the image")
    for index in range(image.page_count):
        leaf = image.directory.leaf(index)
        if leaf is None:
            continue
        physical = image.objects.get(leaf.object_sha256)
        if physical is None:
            raise PageUnavailable(
                "missing",
                f"page {index} object is absent from storage",
                pages=[index],
            )
        if len(physical) != leaf.object_bytes:
            raise PageUnavailable(
                "corrupt", f"page {index} object length mismatches", pages=[index]
            )
    view = image.view()
    _read_region(view, profile, _queue_ref(view))
    _read_region(view, profile, _ledger_ref(view))
    return {
        "schema": PAGED_MANIFEST_SCHEMA,
        "kind": "paged-structure",
        "root_sha256": image.root_sha256,
        "state_sha256": image.state_identity_sha256(),
        "profile_sha256": profile.fingerprint,
        "catalog_sha256": catalog.fingerprint,
        "status": STATUS_NAMES[int(header[H_STATUS])],
        "reason": REASON_NAMES[int(header[H_REASON])],
        "checked_slots": profile.directory_capacity,
        "checked_regions": live,
        "checked_pages": image.page_count,
        "check": "bounded-structure",
    }


def validate_paged_image(image: PagedFieldImage) -> dict[str, Any]:
    """Full audited validation: materialise, verify structure, re-hash."""

    field = image.materialise()
    validate_field(field, image.profile, image.catalog)
    digest = state_sha256(field, image.profile)
    if (
        image.audited_state_sha256 is not None
        and digest != image.audited_state_sha256
    ):
        raise RegionalFieldError("paged image audited digest mismatches")
    image._validated_pages = set(range(image.page_count))
    return {
        "schema": PAGED_MANIFEST_SCHEMA,
        "kind": "paged-full-validation",
        "root_sha256": image.root_sha256,
        "state_sha256": digest,
        "pages": image.page_count,
        "residency": image.residency_report(),
    }


def _paged_commit_blocks(
    image: PagedFieldImage, stage: str, clock: int | None
) -> dict[str, Any]:
    return {
        "clock": None if clock is None else int(clock),
        "base_epoch": int(_read_u64(_SegmentReader(image).words(0, HEADER_WORDS), H_BASE_EPOCH)),
    }


def _paged_status_receipt(
    successor: PagedFieldImage,
    predecessor: PagedFieldImage,
    record: Mapping[str, Any],
    *,
    kind: str,
    status: int,
    reason: int,
    clock: int,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": PAGED_MANIFEST_SCHEMA,
        "kind": kind,
        "paged": True,
        "status": STATUS_NAMES[int(status)],
        "reason": REASON_NAMES[int(reason)],
        "previous_state_sha256": predecessor.state_identity_sha256(),
        "state_sha256": successor.state_identity_sha256(),
        "predecessor_root_sha256": predecessor.root_sha256,
        "root_sha256": successor.root_sha256,
        "logical_transition": int(clock),
        "commit": dict(record),
    }
    if extra:
        receipt.update(extra)
    return receipt


def residency_continuation(
    wait: "ResidencyWait",
    *,
    root_sha256: str,
    staging: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Canonical record of one suspended paged transition.

    A residency wait is a continuation, not a fault: it carries the requesting
    stage, the exact page identities and versions, the declared layout segments
    under authority, the completed work, the remaining allowance, the root the
    request was made against, and the private successor references.  The host
    may checkpoint it and resume the same transition later; it grants no
    authority beyond the storage operation already authorised by the stage.
    """

    if not isinstance(wait, ResidencyWait):
        raise RegionalFieldError("residency continuation requires a wait")
    if not isinstance(root_sha256, str) or len(root_sha256) != 64:
        raise RegionalFieldError("residency continuation root is invalid")
    return {
        "schema": RESIDENCY_CONTINUATION_SCHEMA,
        "kind": "paged-continuation",
        "stage": wait.stage,
        "root_sha256": root_sha256,
        "pages": list(wait.pages),
        "page_versions": list(wait.versions),
        "segments": list(wait.segments),
        "authority_scope": wait.scope,
        "completed_work": wait.work,
        "remaining_allowance": wait.allowance,
        "private_pages": list(wait.private_pages),
        "reason": wait.reason,
        "staging": None if staging is None else dict(staging),
    }


def read_residency_continuation(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one canonical residency continuation record."""

    required = {
        "schema",
        "kind",
        "stage",
        "root_sha256",
        "pages",
        "page_versions",
        "segments",
        "authority_scope",
        "completed_work",
        "remaining_allowance",
        "private_pages",
        "reason",
        "staging",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise RegionalFieldError("invalid residency continuation keys")
    if (
        value["schema"] != RESIDENCY_CONTINUATION_SCHEMA
        or value["kind"] != "paged-continuation"
    ):
        raise RegionalFieldError("unsupported residency continuation")
    root = value["root_sha256"]
    if not isinstance(root, str) or len(root) != 64:
        raise RegionalFieldError("residency continuation root is invalid")
    pages = [_integer(index, "residency continuation page", minimum=0) for index in value["pages"]]
    if len(set(pages)) != len(pages):
        raise RegionalFieldError("residency continuation pages repeat")
    versions = value["page_versions"]
    if not isinstance(versions, Sequence) or isinstance(versions, (str, bytes)):
        raise RegionalFieldError("residency continuation versions are invalid")
    for version in versions:
        if not isinstance(version, str) or len(version) != 64:
            raise RegionalFieldError("residency continuation version is invalid")
    if len(versions) != len(pages):
        raise RegionalFieldError("residency continuation version count mismatch")
    segments = value["segments"]
    if not isinstance(segments, Sequence) or isinstance(segments, (str, bytes)):
        raise RegionalFieldError("residency continuation segments are invalid")
    for name in segments:
        if not isinstance(name, str) or not name:
            raise RegionalFieldError("residency continuation segment is invalid")
    _integer(value["authority_scope"], "residency continuation scope", minimum=0)
    _integer(value["completed_work"], "residency continuation work", minimum=0)
    if value["remaining_allowance"] is not None:
        _integer(
            value["remaining_allowance"],
            "residency continuation allowance",
            minimum=1,
        )
    if not isinstance(value["reason"], str) or not value["reason"]:
        raise RegionalFieldError("residency continuation reason is invalid")
    if not isinstance(value["stage"], str) or not value["stage"]:
        raise RegionalFieldError("residency continuation stage is invalid")
    if value["staging"] is not None and not isinstance(value["staging"], Mapping):
        raise RegionalFieldError("residency continuation staging is invalid")
    return dict(value)


def step_paged_image(
    image: PagedFieldImage,
    *,
    catalog: "KernelCatalog | None" = None,
    stage: str = "transition",
    record_audit_digest: bool = False,
    resident_limit: int | None = None,
    activity: Mapping[Any, Any] | None = None,
    activity_weight: int = DEFAULT_ACTIVITY_WEIGHT,
    _native_state_cache: dict[tuple[int, int, int], Any] | None = None,
    _descriptor_cache: dict[tuple[int, int], dict[str, Any]] | None = None,
    _program_cache: dict[tuple[int, int, int], list[dict[str, Any]]] | None = None,
) -> tuple[PagedFieldImage, dict[str, Any]]:
    """Execute one automaton-selected transition over bounded pages.

    The committed image is never modified: the transition's writes live in a
    private overlay until publication, so a fault, a residency wait, or a
    crash discards them and leaves the predecessor intact.
    """

    profile = image.profile
    if catalog is None:
        catalog = image.catalog
    if not isinstance(catalog, KernelCatalog):
        raise RegionalFieldError("kernel catalog required for a paged transition")
    if catalog.fingerprint != image.catalog.fingerprint:
        raise RegionalFieldError("paged image catalog mismatches the requested catalog")
    caller_image = image
    if resident_limit is not None:
        image = image.with_resident_limit(resident_limit)
    staging = image.stage(stage=stage)
    trial: PagedFieldStaging | None = None
    try:
        view = staging.view()
        status = int(view[H_STATUS])
        if status not in (STATUS_RUNNING, STATUS_WAITING):
            report = staging.discard()
            return image, {
                "schema": PAGED_MANIFEST_SCHEMA,
                "kind": "noop",
                "paged": True,
                "status": STATUS_NAMES[status],
                "reason": REASON_NAMES[int(view[H_REASON])],
                "state_unchanged": True,
                "previous_state_sha256": image.state_identity_sha256(),
                "state_sha256": image.state_identity_sha256(),
                "root_sha256": image.root_sha256,
                "staging": report,
            }
        clock = _read_u64(view, H_CLOCK)
        if clock >= U64_MAX - 1:
            _write_u64(view, H_CLOCK, U64_MAX)
            view[H_STATUS] = STATUS_COUNTER_EXHAUSTED
            view[H_REASON] = REASON_COUNTER_EXHAUSTED
            successor, record = staging.commit(
                blocks=_paged_commit_blocks(image, stage, U64_MAX),
                audit_digest=record_audit_digest,
            )
            validate_paged_delta(image, successor, changed_pages=record["changed_pages"])
            return successor, _paged_status_receipt(
                successor,
                image,
                record,
                kind="counter-exhausted",
                status=STATUS_COUNTER_EXHAUSTED,
                reason=REASON_COUNTER_EXHAUSTED,
                clock=U64_MAX,
            )
        if clock >= profile.max_steps:
            view[H_STATUS] = STATUS_EXHAUSTED
            view[H_REASON] = REASON_STEP_BUDGET
            successor, record = staging.commit(
                blocks=_paged_commit_blocks(image, stage, clock),
                audit_digest=record_audit_digest,
            )
            validate_paged_delta(image, successor, changed_pages=record["changed_pages"])
            return successor, _paged_status_receipt(
                successor,
                image,
                record,
                kind="exhausted",
                status=STATUS_EXHAUSTED,
                reason=REASON_STEP_BUDGET,
                clock=clock,
            )
        queue_ref = _queue_ref(view)
        queue = _read_region(view, profile, queue_ref)
        events = [dict(event) for event in queue["events"]]
        candidates = sorted(events, key=_event_sort_key)
        resumed_awaits = _resume_blocked_awaits(
            view, profile, candidates, _program_cache=_program_cache,
        )
        eligibility_rows = [
            _eligibility(
                view,
                profile,
                event,
                catalog,
                _descriptor_cache=_descriptor_cache,
                _program_cache=_program_cache,
            )
            for event in candidates
        ]
        blocked_awaits, waiters, await_receipt = _await_cycle_analysis(
            view, profile, candidates, eligibility_rows, _program_cache=_program_cache,
        )
        dispatch_count = int(queue["dispatch_count"]) + 1
        lends = _await_prerequisite_lending(
            view, profile, candidates, eligibility_rows, waiters, blocked_awaits,
            dispatch_count=dispatch_count,
        )
        await_receipt["lent_event_ids"] = sorted(lends)
        await_receipt["resumed_event_ids"] = resumed_awaits
        eligible = [row[0] for row in eligibility_rows]
        automaton_index, automaton_receipt, activity_modulation = (
            _advance_automaton(
                view,
                profile,
                queue,
                candidates,
                eligible,
                activity,
                activity_weight,
            )
        )
        ready_indices = [index for index, flag in enumerate(eligible) if flag]
        if not ready_indices:
            for event, row in zip(candidates, eligibility_rows):
                if int(event["event_id"]) in blocked_awaits:
                    event["state"], event["reason"] = "blocked", "await-cycle"
                else:
                    event["state"] = "faulted" if row[1] == "fault" else "waiting"
                    event["reason"] = row[1]
            queue["events"] = sorted(candidates, key=lambda event: int(event["sequence"]))
            _write_region(view, profile, queue_ref, queue)
            _write_u64(view, H_CLOCK, clock + 1)
            faulted = any(row[1] == "fault" for row in eligibility_rows)
            view[H_STATUS] = STATUS_FAULTED if faulted else STATUS_WAITING
            view[H_REASON] = (
                REASON_INVALID_INSTRUCTION if faulted else REASON_NO_READY_EVENT
            )
            successor, record = staging.commit(
                blocks=_paged_commit_blocks(image, stage, clock + 1),
                audit_digest=record_audit_digest,
            )
            validate_paged_delta(image, successor, changed_pages=record["changed_pages"])
            return successor, _paged_status_receipt(
                successor,
                image,
                record,
                kind="no-ready-event",
                status=STATUS_FAULTED if faulted else STATUS_WAITING,
                reason=REASON_INVALID_INSTRUCTION if faulted else REASON_NO_READY_EVENT,
                clock=clock + 1,
                extra={
                    "blocked_reasons": [row[1] for row in eligibility_rows],
                    "await_analysis": await_receipt,
                    "events": len(candidates),
                    "automaton": dict(automaton_receipt),
                    **(
                        {}
                        if activity_modulation is None
                        else {"activity_modulation": activity_modulation}
                    ),
                },
            )
        if dispatch_count % profile.fairness_interval == 0:
            selected_index = min(
                ready_indices,
                key=lambda index: (
                    int(candidates[index]["ready_at"]),
                    int(candidates[index]["sequence"]),
                ),
            )
        elif lends:
            selected_index = min(ready_indices, key=lambda index: (
                -max(int(candidates[index]["priority"]), lends.get(int(candidates[index]["event_id"]), 0)),
                -lends.get(int(candidates[index]["event_id"]), 0),
                int(candidates[index]["ready_at"]), int(candidates[index]["sequence"]),
            ))
        else:
            selected_index = (
                automaton_index if automaton_index in ready_indices else ready_indices[0]
            )
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
        trial = staging.spawn(stage=f"{stage}:trial")
        trial_queue = copy.deepcopy(queue)
        trial_selected = copy.deepcopy(selected)
        state_cache_updates: list[tuple[tuple[int, int, int], Any]] = []
        try:
            disposition, output, work, emitted = _execute_instruction(
                trial.view(),
                profile,
                catalog,
                trial_queue,
                trial_selected,
                instruction,
                clock=clock + 1,
                _native_state_cache=_native_state_cache,
                _state_cache_updates=state_cache_updates,
            )
        except PageUnavailable:
            trial.discard()
            report = staging.discard()
            raise
        except ResidencyWait:
            trial.discard()
            report = staging.discard()
            raise
        except RegionalFieldError as exc:
            fault_detail = str(exc)
            disposition = "fault"
            trial.discard()
            # A fault abandons everything the transition staged, including
            # the pre-dispatch automaton step, and replays that step on the
            # committed image: the dense machine rolls back to the image it
            # was handed and never keeps a partial advance.
            staging.discard()
            staging = image.stage(stage=stage)
            view = staging.view()
            _advance_automaton(view, profile, queue, candidates, eligible)
        else:
            queue = trial_queue
            selected = trial_selected
            staging = trial
            view = staging.view()
        survivors = [
            event
            for event in candidates
            if int(event["event_id"]) != int(selected["event_id"])
        ]
        if disposition in {"continue", "yield"}:
            sequence = _read_u64(view, H_NEXT_SEQUENCE)
            if sequence >= U64_MAX:
                raise RegionalFieldError("event sequence is exhausted")
            selected["state"] = "ready"
            selected["reason"] = None
            selected["ready_at"] = clock + 1
            selected["sequence"] = sequence
            _write_u64(view, H_NEXT_SEQUENCE, sequence + 1)
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
        _write_region(view, profile, queue_ref, queue)
        ledger_ref = _ledger_ref(view)
        ledger = dict(_read_region(view, profile, ledger_ref))
        ledger["dispatches"] = int(ledger["dispatches"]) + 1
        ledger["logical_transitions"] = int(ledger["logical_transitions"]) + 1
        ledger["native_work"] = int(ledger["native_work"]) + int(work)
        ledger["scheduler_work"] = int(ledger["scheduler_work"]) + len(candidates)
        ledger["automaton_local_ops"] = int(ledger["automaton_local_ops"]) + int(
            automaton_receipt["work"]["local_ops"]
        )
        if activity_modulation is not None:
            ledger["activity_modulated"] = int(
                ledger.get("activity_modulated", 0)
            ) + len(activity_modulation["applied"])
        _write_region(view, profile, ledger_ref, ledger)
        _write_u64(view, H_CLOCK, clock + 1)
        _write_u64(view, H_BASE_EPOCH, _read_u64(view, H_BASE_EPOCH) + 1)
        view[H_STATUS] = (
            STATUS_FAULTED
            if disposition == "fault"
            else (STATUS_HALTED if not survivors else STATUS_RUNNING)
        )
        view[H_REASON] = (
            REASON_KERNEL_FAULT
            if disposition == "fault"
            else (REASON_HALT if not survivors else REASON_NONE)
        )
        eligibility_digest = hashlib.sha256(
            _canonical(
                [
                    {"event_id": int(event["event_id"]), "eligible": bool(row[0]), "reason": row[1]}
                    for event, row in zip(candidates, eligibility_rows)
                ]
            )
        ).hexdigest()
        successor, record = staging.commit(
            blocks=_paged_commit_blocks(image, stage, clock + 1),
            audit_digest=record_audit_digest,
        )
        validate_paged_delta(image, successor, changed_pages=record["changed_pages"])
        successor._validated_pages |= set(image._validated_pages) - set(record["changed_pages"])
        if _native_state_cache is not None:
            for cache_key, cached_state in state_cache_updates:
                slot, generation, _version = cache_key
                for stale_key in [
                    key for key in _native_state_cache if key[:2] == (slot, generation)
                ]:
                    del _native_state_cache[stale_key]
                _native_state_cache[cache_key] = cached_state
        final_header = _SegmentReader(successor).words(H_STATUS, 2)
        return successor, {
            "schema": PAGED_MANIFEST_SCHEMA,
            "kind": "regional-transition",
            "paged": True,
            "status": STATUS_NAMES[int(final_header[0])],
            "reason": REASON_NAMES[int(final_header[1])],
            "event_id": int(selected["event_id"]),
            "program_id": int(selected["program_id"]),
            "pc": int(selected["pc"]),
            "operation": instruction["op"],
            "disposition": disposition,
            "fault_detail": fault_detail,
            "output": output,
            "work": {
                "native": int(work),
                "scheduler": len(candidates),
                **dict(automaton_receipt["work"]),
            },
            "eligibility_sha256": eligibility_digest,
            "await_analysis": await_receipt,
            "automaton": dict(automaton_receipt),
            **(
                {}
                if activity_modulation is None
                else {"activity_modulation": activity_modulation}
            ),
            "previous_state_sha256": image.state_identity_sha256(),
            "state_sha256": successor.state_identity_sha256(),
            "predecessor_root_sha256": image.root_sha256,
            "root_sha256": successor.root_sha256,
            "logical_transition": clock + 1,
            "commit": record,
        }
    except ResidencyWait as wait:
        report = dict(staging.counters)
        if trial is not None:
            trial.release_chain()
        staging.release_chain()
        continuation = residency_continuation(
            wait, root_sha256=image.root_sha256, staging=report
        )
        return caller_image, {
            "schema": PAGED_MANIFEST_SCHEMA,
            "kind": "residency-wait",
            "paged": True,
            "status": STATUS_NAMES[int(_SegmentReader(image).words(H_STATUS, 1)[0])],
            "reason": REASON_NAMES[int(_SegmentReader(image).words(H_REASON, 1)[0])],
            "state_unchanged": True,
            "previous_state_sha256": image.state_identity_sha256(),
            "state_sha256": image.state_identity_sha256(),
            "root_sha256": image.root_sha256,
            "wait": wait.as_dict(),
            "continuation": continuation,
        }
    except BaseException:
        # A physical resource wait or failed transition cannot retain any
        # scratch reservation from either the trial or its parent overlay.
        if trial is not None:
            trial.release_chain()
        staging.release_chain()
        raise


def run_paged_image(
    image: PagedFieldImage,
    *,
    steps: int | None = None,
    catalog: "KernelCatalog | None" = None,
    record_audit_digest: bool = False,
    activity: Mapping[Any, Any] | None = None,
    activity_weight: int = DEFAULT_ACTIVITY_WEIGHT,
) -> tuple[PagedFieldImage, dict[str, Any]]:
    """Run bounded paged transitions until halt, exhaustion, or a wait."""

    if steps is not None:
        _integer(steps, "paged run steps", minimum=0, maximum=U64_MAX)
    transitions: list[dict[str, Any]] = []
    waiting: dict[str, Any] | None = None
    executed = 0
    current = image
    limit = profile_steps = current.profile.max_steps if steps is None else steps
    while executed < limit:
        successor, receipt = step_paged_image(
            current,
            catalog=catalog,
            record_audit_digest=record_audit_digest,
            stage="run",
            activity=activity,
            activity_weight=activity_weight,
        )
        if receipt.get("kind") == "noop":
            stop = "settled" if executed else "noop"
            return successor, {
                "schema": PAGED_MANIFEST_SCHEMA,
                "kind": "paged-run",
                "steps": executed,
                "stop": stop,
                "status": receipt["status"],
                "reason": receipt["reason"],
                "root_sha256": successor.root_sha256,
                "state_sha256": successor.state_identity_sha256(),
                "transitions": transitions,
                "residency": successor.residency_report(),
            }
        if receipt.get("kind") == "residency-wait":
            waiting = receipt
            break
        transitions.append(dict(receipt))
        current = successor
        executed += 1
        if receipt["status"] in {"halted", "faulted", "exhausted", "counter-exhausted"}:
            break
    summary: dict[str, Any] = {
        "schema": PAGED_MANIFEST_SCHEMA,
        "kind": "paged-run",
        "steps": executed,
        "stop": "wait" if waiting is not None else (
            "settled" if executed < limit else "step-budget"
        ),
        "root_sha256": current.root_sha256,
        "state_sha256": current.state_identity_sha256(),
        "transitions": transitions,
        "residency": current.residency_report(),
    }
    if waiting is not None:
        summary["wait"] = waiting["wait"]
        summary["continuation"] = waiting["continuation"]
    return current, summary


def _paged_flat_transition(
    image: PagedFieldImage,
    operation: Any,
    *,
    stage: str,
    record_audit_digest: bool,
) -> tuple[PagedFieldImage, dict[str, Any]]:
    """Run one flat-image mutation over staged pages and publish it.

    The committed image is never modified: the operation writes into a private
    overlay, and only a successful, canonically validated overlay becomes the
    successor.  A resource wait or a refused transition discards the overlay
    and leaves the predecessor exactly as it was.
    """

    staging = PagedFieldStaging(image, stage=stage)
    view = staging.view()
    clock = _read_u64(view, H_CLOCK)
    try:
        detail = operation(view)
    except ResidencyWait as wait:
        # A refused input is a continuation, not a fault: the committed image
        # is untouched and the same operation resumes under a larger allowance.
        report = staging.discard()
        return image, {
            "schema": PAGED_MANIFEST_SCHEMA,
            "kind": "residency-wait",
            "paged": True,
            "stage": stage,
            "status": STATUS_NAMES[int(_SegmentReader(image).words(H_STATUS, 1)[0])],
            "reason": REASON_NAMES[int(_SegmentReader(image).words(H_REASON, 1)[0])],
            "state_unchanged": True,
            "previous_state_sha256": image.state_identity_sha256(),
            "state_sha256": image.state_identity_sha256(),
            "root_sha256": image.root_sha256,
            "wait": wait.as_dict(),
            "continuation": residency_continuation(
                wait, root_sha256=image.root_sha256, staging=report
            ),
        }
    except (PageUnavailable, RegionalFieldError):
        staging.discard()
        raise
    successor, record = staging.commit(
        blocks=_paged_commit_blocks(image, stage, clock + 1),
        audit_digest=record_audit_digest,
    )

    validate_paged_delta(
        image, successor, changed_pages=record["changed_pages"]
    )
    successor._validated_pages |= set(image._validated_pages) - set(
        record["changed_pages"]
    )
    return successor, {
        "schema": PAGED_MANIFEST_SCHEMA,
        **detail,
        "paged": True,
        "stage": stage,
        "previous_state_sha256": image.state_identity_sha256(),
        "state_sha256": successor.state_identity_sha256(),
        "predecessor_root_sha256": image.root_sha256,
        "root_sha256": successor.root_sha256,
        "commit": record,
    }
def enqueue_event_paged(
    image: PagedFieldImage,
    event: Mapping[str, Any],
    *,
    record_audit_digest: bool = False,
) -> tuple[PagedFieldImage, dict[str, Any]]:
    """Admit one event through private COW pages and publish atomically."""

    _validate_communication_event(
        image.view(), image.profile, event, root_sha256=image.root_sha256
    )
    def operation(flat: Any) -> dict[str, Any]:
        admitted, clock = _enqueue_event_flat(flat, image.profile, event)
        return {
            "kind": "event-admission",
            "event_id": admitted["event_id"],
            "logical_transition": clock + 1,
        }

    return _paged_flat_transition(
        image,
        operation,
        stage="event-admission",
        record_audit_digest=record_audit_digest,
    )



def write_named_value_paged(
    image: PagedFieldImage,
    name: str,
    value: Any,
    *,
    stage: str = "named-value",
    record_audit_digest: bool = False,
) -> tuple[PagedFieldImage, dict[str, Any]]:
    """Publish one host-lowered input over bounded pages."""

    return _paged_flat_transition(
        image,
        lambda flat: _write_named_value_flat(flat, image.profile, name, value),
        stage=stage,
        record_audit_digest=record_audit_digest,
    )





def restart_paged(
    image: PagedFieldImage,
    *,
    entry: int = 0,
    values: Mapping[str, Any] | None = None,
    stage: str = "restart",
    record_audit_digest: bool = False,
) -> tuple[PagedFieldImage, dict[str, Any]]:
    """Restart the admitted root program over bounded pages."""

    return _paged_flat_transition(
        image,
        lambda flat: _restart_flat(
            flat, image.profile, image.catalog, entry=entry, values=values
        ),
        stage=stage,
        record_audit_digest=record_audit_digest,
    )


def inspect_paged_image(image: PagedFieldImage) -> dict[str, Any]:
    """Read-only bounded inspection that decodes only control-closure pages."""

    view = image.view()
    profile = image.profile
    header = view.window(0, HEADER_WORDS)
    queue = _read_region(view, profile, _queue_ref(view))
    ledger = _read_region(view, profile, _ledger_ref(view))
    segments = image.segments()
    control_pages = tuple(
        sorted(
            {
                page
                for name in CONTROL_CLOSURE_SEGMENTS
                for page in segments.get(name, ())
            }
        )
    )
    directory = view.window(
        HEADER_WORDS,
        HEADER_WORDS + DIRECTORY_WORDS * profile.directory_capacity,
    ).reshape(profile.directory_capacity, DIRECTORY_WORDS)
    regions: list[dict[str, Any]] = []
    for index in range(profile.directory_capacity):
        row = directory[index]
        flags = int(row[D_FLAGS])
        if not flags & (FLAG_LIVE | FLAG_QUARANTINED):
            continue
        regions.append(
            {
                "slot": index + 1,
                "generation": int(row[D_GENERATION]),
                "kind": KIND_NAMES[int(row[D_KIND])],
                "flags": flags,
                "capacity_words": int(row[D_CAPACITY]),
                "used_words": int(row[D_USED]),
                "scope_id": _read_u64(row, D_SCOPE_ID),
                "version": _read_u64(row, D_VERSION),
            }
        )
    return {
        "schema": PAGED_MANIFEST_SCHEMA,
        "kind": "paged-inspection",
        "layout": REGIONAL_LAYOUT,
        "profile_sha256": profile.fingerprint,
        "catalog_sha256": _words_sha(
            [int(word) for word in header[H_CATALOG_SHA:H_CATALOG_SHA + 8]]
        ),
        "field_bytes": profile.total_words * 8,
        "status": STATUS_NAMES[int(header[H_STATUS])],
        "reason": REASON_NAMES[int(header[H_REASON])],
        "clock": _read_u64(header, H_CLOCK),
        "logical_transition": _read_u64(header, H_CLOCK),
        "sequence": _read_u64(header, H_NEXT_SEQUENCE),
        "base_epoch": _read_u64(header, H_BASE_EPOCH),
        "events": len(queue["events"]),
        "dispatch_count": int(queue["dispatch_count"]),
        "named_values": dict(queue["named_values"]),
        "named_value_names": sorted(queue["named_values"]),
        "ledger": dict(ledger),
        "resource_ledger": dict(ledger),
        "regions": regions,
        "regions_metadata": "deferred",
        "segments": {name: len(pages) for name, pages in segments.items()},
        "control_pages": list(control_pages),
        "root_sha256": image.root_sha256,
        "state_sha256": image.state_identity_sha256(),
        "residency": image.residency_report(),
    }


def paged_state_sha256(image: PagedFieldImage) -> str:
    """The logical state identity of one paged image, streamed page by page."""

    return image.logical_state_sha256()


def named_values_paged(
    image: PagedFieldImage, names: Sequence[str]
) -> dict[str, Any]:
    """Read named values through one bounded paged view."""

    return image.view().named_values(names)


def object_value_paged(image: PagedFieldImage, object_id: int) -> Any:
    """Read one object through a bounded paged view."""

    return image.view().object(object_id)


def migrate_flat_to_paged(
    field: np.ndarray | Mapping[str, Any],
    *,
    profile: "RegionalProfile | None" = None,
    catalog: "KernelCatalog" = EMPTY_KERNEL_CATALOG,
    objects: Mapping[str, bytes] | None = None,
    transition: Mapping[str, Any] | None = None,
    operator_versions: Mapping[str, Any] | None = None,
    resident_limit: int = DEFAULT_RESIDENT_PAGES,
    resource_limits: ResourceLimits | Mapping[str, Any] | None = None,
    validate: bool = True,
) -> tuple[PagedFieldImage, dict[str, Any]]:
    """Migrate a dense image or chunked checkpoint onto the paged layout.

    The predecessor's flat digest, logical layout, and identity are retained;
    a storage-only migration changes placement and identity protocol, never
    the numerical law.  A new numerical law is a separate declared kind.
    """

    kind = "storage-only" if transition is None else str(transition.get("kind"))
    if kind not in {"storage-only", "numerical-law"}:
        raise RegionalFieldError("paged migration kind is unsupported")
    if isinstance(field, Mapping):
        if profile is None:
            profile = RegionalProfile.from_dict(field["profile"])
        if not isinstance(objects, Mapping):
            raise RegionalFieldError("migration from a checkpoint requires its objects")
        packed = field
        image = PagedFieldImage.from_descriptor(
            {
                "schema": PAGED_MANIFEST_SCHEMA,
                "layout": REGIONAL_LAYOUT,
                "profile": profile.as_dict(),
                "profile_sha256": profile.fingerprint,
                "catalog_sha256": packed["catalog_sha256"],
                "page_words": PERSISTENCE_PAGE_WORDS,
                "byte_order": "little",
                "word_encoding": "u32",
                "pages": [dict(record) for record in packed["chunks"]],
                "page_count": _page_count(profile),
                "root_sha256": PageDirectory(
                    profile.fingerprint,
                    _page_count(profile),
                    tuple(PageLeaf.from_record(record) for record in packed["chunks"]),
                )
                .tree(profile)
                .root_sha256,
                "state_sha256": packed["state_sha256"],
                "predecessor": {
                    "root_sha256": None,
                    "state_sha256": packed["state_sha256"],
                    "layout": REGIONAL_LAYOUT,
                },
                "transition": {"kind": kind},
            },
            objects,
            catalog,
            resident_limit=resident_limit,
            resource_limits=resource_limits,
            verify="none",
        )
        predecessor = {
            "root_sha256": None,
            "state_sha256": packed["state_sha256"],
            "layout": REGIONAL_LAYOUT,
            "kind": "flat-checkpoint",
        }
    else:
        if profile is None:
            raise RegionalFieldError("migration from a dense image requires its profile")
        image = PagedFieldImage.from_dense(
            field,
            profile,
            catalog,
            resident_limit=resident_limit,
            resource_limits=resource_limits,
            validate=validate,
        )
        predecessor = {
            "root_sha256": None,
            "state_sha256": image.logical_state_sha256(),
            "layout": "dense-regional-image-v1",
            "kind": "dense-image",
        }
        if objects is not None:
            image = image.with_backing(objects)
    record = {
        "schema": LAYOUT_MIGRATION_SCHEMA,
        "kind": kind,
        "predecessor": predecessor,
        "successor": {
            "root_sha256": image.root_sha256,
            "layout": REGIONAL_LAYOUT,
            "page_words": PERSISTENCE_PAGE_WORDS,
            "page_count": image.page_count,
            "segments": {name: list(pages) for name, pages in image.segments().items()},
        },
        "logical_mapping": {
            "start_word": 0,
            "length": profile.total_words,
            "offset": 0,
            "layout": REGIONAL_LAYOUT,
        },
        "operator_versions": dict(operator_versions or {}),
        "identity": {
            "profile_sha256": profile.fingerprint,
            "catalog_sha256": catalog.fingerprint,
        },
        "resource_limits": image.resource_limits.as_dict(),
    }
    image.predecessor = predecessor
    image.transition = {"kind": kind, **(dict(transition or {}))}
    return image, record


def migrate_paged_layout(
    image: PagedFieldImage,
    profile: "RegionalProfile",
    *,
    catalog: "KernelCatalog | None" = None,
    transition: Mapping[str, Any] | None = None,
    operator_versions: Mapping[str, Any] | None = None,
    resource_limits: ResourceLimits | Mapping[str, Any] | None = None,
    validate: bool = True,
    relocate_regions: bool = False,
) -> tuple[PagedFieldImage, dict[str, Any]]:
    """Publish an explicit layout successor without dense reconstruction."""

    if not isinstance(profile, RegionalProfile):
        raise RegionalFieldError("regional profile required for a layout migration")
    catalog = image.catalog if catalog is None else catalog
    kind = "storage-only" if transition is None else str(transition.get("kind"))
    if kind not in {"storage-only", "numerical-law"}:
        raise RegionalFieldError("paged migration kind is unsupported")
    if profile.total_words < image.profile.total_words:
        raise RegionalFieldError("layout migration cannot discard logical words")
    if profile.directory_capacity != image.profile.directory_capacity:
        raise RegionalFieldError(
            "layout migration cannot move the arena start: region bases would need an explicit remap"
        )
    new_count = _page_count(profile)
    reader = _SegmentReader(image)
    target_pages: dict[int, np.ndarray] = {}


    def write_target(start: int, values: Sequence[float]) -> None:
        raw = np.asarray(values, dtype=np.float64).reshape(-1)
        first = start // PERSISTENCE_PAGE_WORDS
        last = (start + raw.size - 1) // PERSISTENCE_PAGE_WORDS if raw.size else first
        for index in range(first, last + 1):
            page = target_pages.setdefault(
                index,
                np.zeros(
                    min(PERSISTENCE_PAGE_WORDS, profile.total_words - index * PERSISTENCE_PAGE_WORDS),
                    dtype=np.float64,
                ),
            )
            base = index * PERSISTENCE_PAGE_WORDS
            lo = max(start, base)
            hi = min(start + raw.size, base + page.size)
            page[lo - base:hi - base] = raw[lo - start:hi - start]

    control_words = HEADER_WORDS + DIRECTORY_WORDS * profile.directory_capacity
    write_target(0, reader.words(0, control_words))
    old_rows: list[tuple[int, np.ndarray, np.ndarray]] = []
    old_header = reader.words(0, HEADER_WORDS)
    for slot in range(profile.directory_capacity):
        row = reader.words(HEADER_WORDS + slot * DIRECTORY_WORDS, DIRECTORY_WORDS)
        flags = int(row[D_FLAGS])
        if not flags & (FLAG_LIVE | FLAG_QUARANTINED):
            continue
        capacity = int(row[D_CAPACITY])
        old_rows.append((slot, row, reader.words(int(row[D_BASE]), capacity)))
    cursor = control_words
    resized_regions: list[dict[str, int]] = []
    for slot, row, payload in sorted(old_rows, key=lambda item: int(item[1][D_BASE])):
        old_capacity = int(row[D_CAPACITY])
        new_capacity = old_capacity
        if relocate_regions and int(row[D_KIND]) == KIND_VALUE:
            if profile.mode_count > image.profile.mode_count:
                new_capacity = max(
                    new_capacity,
                    (old_capacity * profile.mode_count + image.profile.mode_count - 1)
                    // image.profile.mode_count,
                )
            used = int(row[D_USED])
            if used * 2 >= old_capacity:
                new_capacity = max(
                    new_capacity, old_capacity + max(4096, old_capacity // 4)
                )
        target_base = cursor if relocate_regions else int(row[D_BASE])
        if target_base + new_capacity > profile.workspace_words:
            raise RegionalFieldError("growth cannot fit relocated payload arena")
        write_target(target_base, payload)
        if relocate_regions:
            row[D_BASE] = target_base
            row[D_CAPACITY] = new_capacity
        write_target(HEADER_WORDS + slot * DIRECTORY_WORDS, row)
        if new_capacity != old_capacity:
            resized_regions.append({
                "slot": slot + 1,
                "kind": int(row[D_KIND]),
                "old_capacity": old_capacity,
                "new_capacity": new_capacity,
            })
        if relocate_regions:
            cursor += new_capacity
    write_target(H_TOTAL_WORDS, [profile.total_words])
    write_target(H_PROFILE_SHA, _sha_words(profile.fingerprint))
    write_target(H_CATALOG_SHA, _sha_words(catalog.fingerprint))
    write_target(H_FREE_CURSOR, [old_header[H_FREE_CURSOR]])
    if profile.neural_membrane and image.profile.neural_membrane:
        for plane in range(NEURAL_MEMBRANE_PLANE_COUNT):
            old_start = image.profile.neural_membrane_offset + plane * image.profile.mode_count
            new_start = profile.neural_membrane_offset + plane * profile.mode_count
            write_target(new_start, reader.words(old_start, image.profile.mode_count))
    changed_objects: dict[str, bytes] = {}
    leaves: list[PageLeaf] = []
    for index, page in sorted(target_pages.items()):
        if not np.any(page):
            continue
        decoded = _encode_page(page)
        if decoded is None:
            continue
        physical = zlib.compress(decoded, level=6)
        object_sha = hashlib.sha256(physical).hexdigest()
        changed_objects[object_sha] = physical
        leaves.append(PageLeaf(
            index=index,
            start_word=index * PERSISTENCE_PAGE_WORDS,
            words=int(page.size),
            decoded_bytes=len(decoded),
            decoded_sha256=hashlib.sha256(decoded).hexdigest(),
            object_bytes=len(physical),
            object_sha256=object_sha,
        ))
    directory = PageDirectory(profile.fingerprint, new_count, tuple(leaves))
    predecessor = {
        "root_sha256": image.root_sha256,
        "state_sha256": image.state_identity_sha256(),
        "layout": REGIONAL_LAYOUT,
    }
    successor = PagedFieldImage(
        profile,
        catalog,
        directory,
        ObjectOverlay(changed_objects, image.objects),
        resident_limit=image.resident_limit,
        dirty_limit=image.dirty_limit,
        predecessor=predecessor,
        transition={"kind": kind, **dict(transition or {})},
        revoked_roots=image.revoked_roots,
        state_sha256_kind=image.state_sha256_kind,
        pinned=tuple(index for index in image.pinned() if index < new_count),
        previous_tree=None,
        _objects_verified=True,
        resource_limits=(
            image.resource_limits if resource_limits is None else resource_limits
        ),
        tier_store=image._tier_store,
    )
    record = {
        "schema": LAYOUT_MIGRATION_SCHEMA,
        "kind": kind,
        "predecessor": predecessor,
        "successor": {
            "root_sha256": successor.root_sha256,
            "layout": REGIONAL_LAYOUT,
            "page_words": PERSISTENCE_PAGE_WORDS,
            "page_count": successor.page_count,
            "segments": {name: list(pages) for name, pages in successor.segments().items()},
        },
        "logical_mapping": {
            "start_word": 0,
            "length": image.profile.total_words,
            "offset": 0,
            "layout": REGIONAL_LAYOUT,
        },
        "operator_versions": dict(operator_versions or {}),
        "identity": {
            "profile_sha256": profile.fingerprint,
            "catalog_sha256": catalog.fingerprint,
        },
        "resized_regions": resized_regions,
        "resource_limits": successor.resource_limits.as_dict(),
    }
    if validate:
        validate_paged_structure(successor)
    image.release_resident()
    return successor, record

def grow_paged_field(
    image: PagedFieldImage,
    profile: "RegionalProfile",
    *,
    catalog: "KernelCatalog | None" = None,
    transition: Mapping[str, Any] | None = None,
    operator_versions: Mapping[str, Any] | None = None,
    resource_limits: ResourceLimits | Mapping[str, Any] | None = None,
    validate: bool = True,
) -> tuple[PagedFieldImage, dict[str, Any]]:
    """Grow a paged field while relocating named regions incrementally."""
    if profile.total_words <= image.profile.total_words:
        raise RegionalFieldError("paged growth must increase total capacity")
    return migrate_paged_layout(
        image,
        profile,
        catalog=catalog,
        transition={"kind": "storage-only", **dict(transition or {})},
        operator_versions=operator_versions,
        resource_limits=resource_limits,
        validate=validate,
        relocate_regions=True,
    )



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
    "NEURAL_MEMBRANE_DEFAULT_GAIN_PPM",
    "NEURAL_MEMBRANE_FIRST_PLANE",
    "NEURAL_MEMBRANE_MODE_QUANTUM",
    "NEURAL_MEMBRANE_PLANES",
    "NEURAL_MEMBRANE_PLANE_COUNT",
    "NEURAL_MEMBRANE_SCHEMA",
    "RIGHT_ALL",
    "RIGHT_EMIT",
    "RIGHT_EXECUTE",
    "RIGHT_MANAGE",
    "RIGHT_READ",
    "RIGHT_WRITE",
    "DEFAULT_DIRTY_PAGES",
    "DEFAULT_RESIDENT_PAGES",
    "LAYOUT_MIGRATION_SCHEMA",
    "PAGED_MANIFEST_SCHEMA",
    "paged_state_sha256",
    "validate_paged_structure",
    "PAGE_TREE_SCHEMA",
    "PERSISTENCE_PAGE_WORDS",
    "PageDirectory",
    "PageLeaf",
    "PageTree",
    "PageUnavailable",
    "PagedFieldImage",
    "PagedFieldStaging",
    "ACTIVITY_SCHEMA",
    "ACTIVITY_UNIT",
    "DEFAULT_ACTIVITY_WEIGHT",
    "RESIDENCY_CONTINUATION_SCHEMA",
    "RESIDENCY_WAIT_SCHEMA",
    "canonical_activity",
    "read_residency_continuation",
    "residency_continuation",
    "RegionRef",
    "ImmutableInputPages",
    "INPUT_REGION_PAGE_BYTES",
    "MAX_INPUT_REGION_BYTES",
    "MAX_INPUT_WINDOW_BYTES",
    "RegionalFieldError",
    "ResidencyWait",
    "inspect_paged_image",
    "migrate_flat_to_paged",
    "restart_paged",
    "declare_named_value_paged",
    "enqueue_event",
    "enqueue_event_paged",
    "write_named_value_paged",
    "migrate_paged_layout",
    "grow_paged_field",
    "named_values_paged",
    "object_value_paged",
    "run_paged_image",
    "step_paged_image",
    "validate_paged_delta",
    "validate_paged_image",
    "RegionalProfile",
    "EMBODIED_ROLE_BINDINGS_SCHEMA",
    "EMBODIED_ROLE_BINDING_SCHEMA",
    "EMBODIED_ROLE_NAMES",
    "EmbodiedRoleBinding",
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
    "enable_neural_membrane",
    "neural_membrane_planes",
    "initial_field",
    "inspect_field",
    "declare_named_value",
    "intervene_automaton",
    "make_semantic_record",
    "named_object_id",
    "named_values",
    "read_bound_object_refs",
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
