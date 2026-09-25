"""Deterministic, hash-bound promotion of architecture candidates.

The kernel is a deliberately small persistence boundary.  It stores immutable
source generations in a parent-linked DAG, binds every generation to candidate,
source, receipt, and field-state digests, and changes only one atomic current
pointer.  State migrations are bounded JSON edits with declared source/target
schemas and digests; no callable migration code is accepted.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

KERNEL_SCHEMA = "cassimindfield.promotion-kernel.v1"
GENERATION_SCHEMA = "cassimindfield.promotion-generation.v1"
POINTER_SCHEMA = "cassimindfield.promotion-pointer.v1"
CANDIDATE_SCHEMA = "cassimindfield.promotion-candidate.v1"
STATE_SCHEMA = "cassimindfield.field-state.v1"
MIGRATION_SCHEMA = "cassimindfield.state-migration.v1"
PATCH_RECEIPT_SCHEMA = "cassimindfield.architecture-synthesis.v1"

_MAX_JSON_BYTES = 1_048_576
_MAX_JSON_DEPTH = 16
_MAX_JSON_ITEMS = 4096
_MAX_MIGRATION_OPERATIONS = 128
_MAX_PATH_DEPTH = 16
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,63}$")
_SCHEMA_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_GENERATION_ID = re.compile(r"^g([0-9]{4,})$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class PromotionError(ValueError):
    """Base class for malformed promotion requests."""


class PromotionRefusal(PromotionError):
    """Raised when a mutation, stale parent, or unsafe edit is detected."""


class PromotionIntegrityError(PromotionError):
    """Raised when persisted bytes no longer match their receipt."""


def _fail(message: str, error_type: type[PromotionError] = PromotionError) -> None:
    raise error_type(message)


def _require(condition: bool, message: str, error_type: type[PromotionError] = PromotionError) -> None:
    if not condition:
        _fail(message, error_type)


def _object(value: Any, label: str, required: set[str], optional: set[str] | None = None) -> Mapping[str, Any]:
    if optional is None:
        optional = set()
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    keys = set(value)
    missing = required - keys
    unknown = keys - required - optional
    if missing:
        _fail(f"{label} missing keys: {sorted(missing)}")
    if unknown:
        _fail(f"{label} has unknown keys: {sorted(unknown)}")
    return value


def _text(value: Any, label: str, maximum: int = 4096, *, empty: bool = False) -> str:
    if not isinstance(value, str):
        _fail(f"{label} must be a string")
    if not empty and not value:
        _fail(f"{label} must not be empty")
    if len(value) > maximum:
        _fail(f"{label} exceeds {maximum} characters")
    return value


def _schema_id(value: Any, label: str) -> str:
    value = _text(value, label, 64)
    if not _SCHEMA_ID.fullmatch(value):
        _fail(f"{label} is not a bounded schema identifier")
    return value


def _digest(value: Any, label: str) -> str:
    value = _text(value, label, 64)
    if not _DIGEST.fullmatch(value):
        _fail(f"{label} must be a lowercase SHA-256 digest")
    return value


def _identifier(value: Any, label: str) -> str:
    value = _text(value, label, 64)
    if not _IDENTIFIER.fullmatch(value):
        _fail(f"{label} is not an identifier")
    return value


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        _fail(f"value is not strict JSON: {error}")


def canonical_json(value: Any) -> bytes:
    """Public canonical JSON helper shared by receipts and the verifier."""
    return _canonical_json(value)


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _validate_json(value: Any, label: str = "json", depth: int = 0) -> None:
    if depth > _MAX_JSON_DEPTH:
        _fail(f"{label} exceeds JSON depth bound")
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, str) and len(value.encode("utf-8")) > _MAX_JSON_BYTES:
            _fail(f"{label} string exceeds byte bound")
        if isinstance(value, float) and (value != value or value in {float("inf"), float("-inf")}):
            _fail(f"{label} contains a non-finite number")
        return
    if isinstance(value, list):
        if len(value) > _MAX_JSON_ITEMS:
            _fail(f"{label} exceeds item bound")
        for index, item in enumerate(value):
            _validate_json(item, f"{label}[{index}]", depth + 1)
        return
    if isinstance(value, Mapping):
        if len(value) > _MAX_JSON_ITEMS:
            _fail(f"{label} exceeds item bound")
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                _fail(f"{label} has a non-string or empty key")
            if len(key) > 256:
                _fail(f"{label} key is too long")
            _validate_json(item, f"{label}.{key}", depth + 1)
        return
    _fail(f"{label} contains a non-JSON value: {type(value).__name__}")


def _validated_json(value: Any, label: str) -> Any:
    _validate_json(value, label)
    encoded = _canonical_json(value)
    if len(encoded) > _MAX_JSON_BYTES:
        _fail(f"{label} exceeds {_MAX_JSON_BYTES} canonical bytes")
    return json.loads(encoded.decode("utf-8"))


def _relative_path(value: Any, label: str = "path") -> str:
    value = _text(value, label, 240)
    if "\\" in value or value.startswith("/"):
        _fail(f"{label} must be a relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        _fail(f"{label} has an unsafe component")
    if not value.endswith(".py"):
        _fail(f"{label} must name a Python source file")
    return value


def _file_map(files: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(files, Mapping):
        _fail("candidate files must be a mapping")
    if not files or len(files) > _MAX_JSON_ITEMS:
        _fail("candidate files must be non-empty and bounded")
    result: dict[str, str] = {}
    for raw_path, source in files.items():
        path = _relative_path(raw_path, "candidate file path")
        source = _text(source, f"candidate source {path}", _MAX_JSON_BYTES, empty=True)
        if len(source.encode("utf-8")) > _MAX_JSON_BYTES:
            _fail(f"candidate source exceeds byte bound: {path}")
        result[path] = source
    return {path: result[path] for path in sorted(result)}


def source_digest(files: Mapping[str, str]) -> str:
    """Digest names and bytes, not mapping insertion order."""
    normalized = _file_map(files)
    return digest({path: hashlib.sha256(normalized[path].encode("utf-8")).hexdigest() for path in normalized})


@dataclass(frozen=True)
class FieldState:
    schema: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        _schema_id(self.schema, "field state schema")
        normalized = _validated_json(self.payload, "field state payload")
        if not isinstance(normalized, dict):
            _fail("field state payload must be a JSON object")
        object.__setattr__(self, "payload", normalized)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "payload": copy.deepcopy(self.payload)}

    def digest(self) -> str:
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, value: Any) -> "FieldState":
        item = _object(value, "field state", {"schema", "payload"})
        return cls(_schema_id(item["schema"], "field state schema"), _validated_json(item["payload"], "field state payload"))


@dataclass(frozen=True)
class StateMigration:
    source_schema: str
    target_schema: str
    source_digest: str
    target_digest: str
    operations: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        _schema_id(self.source_schema, "migration.source_schema")
        _schema_id(self.target_schema, "migration.target_schema")
        if self.source_schema == self.target_schema:
            _fail("migration source and target schemas must differ")
        _digest(self.source_digest, "migration.source_digest")
        _digest(self.target_digest, "migration.target_digest")
        if len(self.operations) > _MAX_MIGRATION_OPERATIONS:
            _fail("migration exceeds operation bound")
        normalized = tuple(_parse_migration_operation(item) for item in self.operations)
        object.__setattr__(self, "operations", normalized)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": MIGRATION_SCHEMA, "source_schema": self.source_schema, "target_schema": self.target_schema, "source_digest": self.source_digest, "target_digest": self.target_digest, "operations": [copy.deepcopy(item) for item in self.operations]}

    @classmethod
    def from_dict(cls, value: Any) -> "StateMigration":
        item = _object(value, "state migration", {"schema", "source_schema", "target_schema", "source_digest", "target_digest", "operations"})
        if item["schema"] != MIGRATION_SCHEMA:
            _fail("unsupported state migration schema")
        raw_operations = item["operations"]
        if not isinstance(raw_operations, list):
            _fail("migration.operations must be a list")
        return cls(_schema_id(item["source_schema"], "migration.source_schema"), _schema_id(item["target_schema"], "migration.target_schema"), _digest(item["source_digest"], "migration.source_digest"), _digest(item["target_digest"], "migration.target_digest"), tuple(_parse_migration_operation(entry) for entry in raw_operations))


def _path(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or len(value) > _MAX_PATH_DEPTH:
        _fail(f"{label} must be a non-empty bounded list")
    return tuple(_identifier(part, f"{label} item") for part in value)


def _parse_migration_operation(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("migration operation must be an object")
    kind = value.get("kind")
    if kind == "set":
        item = _object(value, "migration set", {"kind", "path", "value"})
        return {"kind": "set", "path": list(_path(item["path"], "migration set.path")), "value": _validated_json(item["value"], "migration set.value")}
    if kind in {"delete", "rename", "copy"}:
        required = {"kind", "path"} if kind == "delete" else {"kind", "path", "target"}
        item = _object(value, f"migration {kind}", required)
        result = {"kind": kind, "path": list(_path(item["path"], f"migration {kind}.path"))}
        if kind != "delete":
            result["target"] = list(_path(item["target"], f"migration {kind}.target"))
        return result
    _fail(f"unsupported migration operation: {kind!r}")


def _read_path(payload: Mapping[str, Any], path: Sequence[str], operation: str) -> Any:
    current: Any = payload
    for part in path:
        _require(isinstance(current, Mapping) and part in current, f"migration {operation}: missing path {'/'.join(path)}", PromotionRefusal)
        current = current[part]
    return current


def _parent_mapping(payload: dict[str, Any], path: Sequence[str], operation: str) -> tuple[dict[str, Any], str]:
    _require(path, f"migration {operation}: empty path", PromotionRefusal)
    current: Any = payload
    for part in path[:-1]:
        _require(isinstance(current, dict) and part in current, f"migration {operation}: missing parent {'/'.join(path)}", PromotionRefusal)
        current = current[part]
    _require(isinstance(current, dict), f"migration {operation}: parent is not an object", PromotionRefusal)
    return current, path[-1]


def apply_state_migration(state: FieldState, migration: StateMigration | Mapping[str, Any]) -> FieldState:
    """Apply only bounded JSON operations and verify both declared digests."""
    if not isinstance(state, FieldState):
        state = FieldState.from_dict(state)
    if not isinstance(migration, StateMigration):
        migration = StateMigration.from_dict(migration)
    _require(state.schema == migration.source_schema, "migration source schema mismatch", PromotionRefusal)
    _require(state.digest() == migration.source_digest, "migration source digest mismatch", PromotionRefusal)
    payload = copy.deepcopy(state.payload)
    for index, operation in enumerate(migration.operations):
        kind = operation["kind"]
        label = f"operation {index} ({kind})"
        path = tuple(operation["path"])
        if kind == "set":
            parent, key = _parent_mapping(payload, path, label)
            _require(key not in parent, f"migration {label}: set target already exists", PromotionRefusal)
            parent[key] = copy.deepcopy(operation["value"])
        elif kind == "delete":
            parent, key = _parent_mapping(payload, path, label)
            _require(key in parent, f"migration {label}: delete target is absent", PromotionRefusal)
            del parent[key]
        elif kind == "rename":
            parent, key = _parent_mapping(payload, path, label)
            target = tuple(operation["target"])
            target_parent, target_key = _parent_mapping(payload, target, label)
            _require(key in parent, f"migration {label}: rename source is absent", PromotionRefusal)
            _require(target_key not in target_parent, f"migration {label}: rename target exists", PromotionRefusal)
            target_parent[target_key] = parent.pop(key)
        elif kind == "copy":
            value = _read_path(payload, path, label)
            target_parent, target_key = _parent_mapping(payload, tuple(operation["target"]), label)
            _require(target_key not in target_parent, f"migration {label}: copy target exists", PromotionRefusal)
            target_parent[target_key] = copy.deepcopy(value)
        else:  # validated by StateMigration, retained as a fail-closed guard
            _fail(f"migration {label}: unsupported operation", PromotionRefusal)
        _validated_json(payload, f"migrated payload after {label}")
    target = FieldState(migration.target_schema, payload)
    _require(target.digest() == migration.target_digest, "migration target digest mismatch", PromotionRefusal)
    return target


@dataclass(frozen=True)
class PromotionCandidate:
    candidate_id: str
    files: dict[str, str]
    receipt: dict[str, Any]
    declared_source_digest: str | None = None
    declared_candidate_digest: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.candidate_id, "candidate_id")
        normalized_files = _file_map(self.files)
        normalized_receipt = _validated_json(self.receipt, "candidate receipt")
        if not isinstance(normalized_receipt, dict):
            _fail("candidate receipt must be a JSON object")
        object.__setattr__(self, "files", normalized_files)
        object.__setattr__(self, "receipt", normalized_receipt)
        if self.declared_source_digest is not None:
            _digest(self.declared_source_digest, "candidate source digest")
        if self.declared_candidate_digest is not None:
            _digest(self.declared_candidate_digest, "candidate digest")

    def source_digest(self) -> str:
        value = source_digest(self.files)
        if self.declared_source_digest is not None:
            _require(value == self.declared_source_digest, "candidate source digest mismatch", PromotionRefusal)
        receipt_source = self.receipt.get("source_digest")
        if receipt_source is not None:
            _require(receipt_source == value, "candidate receipt source digest mismatch", PromotionRefusal)
        return value

    def receipt_digest(self) -> str:
        return digest(self.receipt)

    def candidate_digest(self) -> str:
        value = digest({"schema": CANDIDATE_SCHEMA, "candidate_id": self.candidate_id, "source_digest": self.source_digest(), "receipt_digest": self.receipt_digest(), "files": {path: hashlib.sha256(self.files[path].encode("utf-8")).hexdigest() for path in sorted(self.files)}})
        if self.declared_candidate_digest is not None:
            _require(value == self.declared_candidate_digest, "candidate digest mismatch", PromotionRefusal)
        return value

    def to_dict(self) -> dict[str, Any]:
        return {"schema": CANDIDATE_SCHEMA, "candidate_id": self.candidate_id, "files": copy.deepcopy(self.files), "receipt": copy.deepcopy(self.receipt), "source_digest": self.source_digest(), "candidate_digest": self.candidate_digest()}

    @classmethod
    def from_dict(cls, value: Any) -> "PromotionCandidate":
        item = _object(value, "promotion candidate", {"schema", "candidate_id", "files", "receipt"}, {"source_digest", "candidate_digest"})
        if item["schema"] != CANDIDATE_SCHEMA:
            _fail("unsupported promotion candidate schema")
        return cls(_identifier(item["candidate_id"], "candidate_id"), _file_map(item["files"]), _validated_json(item["receipt"], "candidate receipt"), item.get("source_digest"), item.get("candidate_digest"))


def candidate_from_workspace(workspace: Any, candidate_id: str = "architecture_successor") -> PromotionCandidate:
    """Adapt an architecture synthesizer result without importing it."""
    files = getattr(workspace, "files", None)
    receipt = getattr(workspace, "manifest", None)
    if files is None or receipt is None:
        _fail("workspace candidate must expose files and manifest")
    declared = getattr(workspace, "source_digest", None)
    return PromotionCandidate(candidate_id, files, receipt, declared_source_digest=declared)


@dataclass(frozen=True)
class GenerationRecord:
    generation: str
    parent_generation: str | None
    candidate_id: str
    candidate_digest: str
    source_digest: str
    field_state_digest: str
    field_state_schema: str
    receipt_digest: str
    files: dict[str, str]
    migration: dict[str, Any] | None
    generation_digest: str

    def core_dict(self) -> dict[str, Any]:
        return {"schema": GENERATION_SCHEMA, "generation": self.generation, "parent_generation": self.parent_generation, "candidate_id": self.candidate_id, "candidate_digest": self.candidate_digest, "source_digest": self.source_digest, "field_state_digest": self.field_state_digest, "field_state_schema": self.field_state_schema, "receipt_digest": self.receipt_digest, "files": dict(sorted(self.files.items())), "migration": copy.deepcopy(self.migration)}

    def to_dict(self) -> dict[str, Any]:
        value = self.core_dict()
        value["generation_digest"] = self.generation_digest
        return value


class PromotionKernel:
    """Filesystem-backed immutable generation DAG with one atomic pointer."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.generations_root = self.root / "generations"
        self.pointer_path = self.root / "current.json"
        self.root.mkdir(parents=True, exist_ok=True)
        self.generations_root.mkdir(parents=True, exist_ok=True)

    def initialize(self, candidate: PromotionCandidate | Mapping[str, Any], state: FieldState | Mapping[str, Any]) -> GenerationRecord:
        _require(not self.pointer_path.exists(), "promotion kernel is already initialized", PromotionRefusal)
        _require(not any(path.is_dir() and _GENERATION_ID.fullmatch(path.name) for path in self.generations_root.iterdir()), "generation DAG already exists", PromotionRefusal)
        return self.promote(candidate, state, parent_generation=None)

    def promote(self, candidate: PromotionCandidate | Mapping[str, Any], state: FieldState | Mapping[str, Any], migration: StateMigration | Mapping[str, Any] | None = None, parent_generation: str | None = None) -> GenerationRecord:
        candidate = candidate if isinstance(candidate, PromotionCandidate) else PromotionCandidate.from_dict(candidate)
        state = state if isinstance(state, FieldState) else FieldState.from_dict(state)
        if parent_generation is None:
            current = self.current()
            parent_generation = None if current is None else current.generation
        parent = None if parent_generation is None else self.read_generation(parent_generation)
        if parent is None:
            _require(migration is None, "initial generation cannot carry a state migration", PromotionRefusal)
        else:
            if migration is not None:
                migration = migration if isinstance(migration, StateMigration) else StateMigration.from_dict(migration)
                migrated = apply_state_migration(self.read_state(parent.generation), migration)
                _require(migrated.to_dict() == state.to_dict(), "promoted state differs from declared migration target", PromotionRefusal)
            else:
                _require(parent.field_state_digest == state.digest(), "field state changed without an explicit migration", PromotionRefusal)
        candidate_source_digest = candidate.source_digest()
        candidate_receipt_digest = candidate.receipt_digest()
        candidate_hash = candidate.candidate_digest()
        generation = self._next_generation()
        migration_dict = None if migration is None else migration.to_dict()
        files_hashes = {path: hashlib.sha256(candidate.files[path].encode("utf-8")).hexdigest() for path in sorted(candidate.files)}
        core = {"schema": GENERATION_SCHEMA, "generation": generation, "parent_generation": parent_generation, "candidate_id": candidate.candidate_id, "candidate_digest": candidate_hash, "source_digest": candidate_source_digest, "field_state_digest": state.digest(), "field_state_schema": state.schema, "receipt_digest": candidate_receipt_digest, "files": files_hashes, "migration": migration_dict}
        generation_hash = digest(core)
        record = GenerationRecord(generation, parent_generation, candidate.candidate_id, candidate_hash, candidate_source_digest, state.digest(), state.schema, candidate_receipt_digest, files_hashes, migration_dict, generation_hash)
        self._write_generation(record, candidate.files, candidate.receipt, state)
        self._write_pointer(record)
        return record

    def rollback(self, generation: str) -> GenerationRecord:
        record = self.read_generation(generation)
        self._write_pointer(record)
        return record

    def current(self) -> GenerationRecord | None:
        if not self.pointer_path.exists():
            return None
        try:
            pointer = self._read_json(self.pointer_path, "current pointer")
            item = _object(pointer, "current pointer", {"schema", "generation", "generation_digest"})
            if item["schema"] != POINTER_SCHEMA:
                _fail("current pointer schema mismatch", PromotionIntegrityError)
            generation = self._generation_id(item["generation"], "current pointer generation")
            record = self.read_generation(generation)
            _require(record.generation_digest == item["generation_digest"], "current pointer digest mismatch", PromotionIntegrityError)
            return record
        except PromotionIntegrityError:
            raise
        except PromotionError as error:
            raise PromotionIntegrityError(str(error)) from error

    def read_generation(self, generation: str) -> GenerationRecord:
        generation = self._generation_id(generation, "generation")
        directory = self.generations_root / generation
        record_path = directory / "generation.json"
        _require(record_path.is_file(), f"generation is missing: {generation}", PromotionIntegrityError)
        raw = self._read_json(record_path, f"generation {generation} record")
        item = _object(raw, f"generation {generation}", {"schema", "generation", "parent_generation", "candidate_id", "candidate_digest", "source_digest", "field_state_digest", "field_state_schema", "receipt_digest", "files", "migration", "generation_digest"})
        _require(item["schema"] == GENERATION_SCHEMA, f"generation schema mismatch: {generation}", PromotionIntegrityError)
        _require(item["generation"] == generation, f"generation id mismatch: {generation}", PromotionIntegrityError)
        parent = item["parent_generation"]
        if parent is not None:
            parent = self._generation_id(parent, f"generation {generation} parent")
            _require(parent != generation and int(parent[1:]) < int(generation[1:]), f"generation parent is not an earlier node: {generation}", PromotionIntegrityError)
            _require((self.generations_root / parent / "generation.json").is_file(), f"generation parent is missing: {parent}", PromotionIntegrityError)
        candidate_id = _identifier(item["candidate_id"], "generation candidate_id")
        candidate_hash = _digest(item["candidate_digest"], "generation candidate_digest")
        source_hash = _digest(item["source_digest"], "generation source_digest")
        state_hash = _digest(item["field_state_digest"], "generation field_state_digest")
        state_schema = _schema_id(item["field_state_schema"], "generation field_state_schema")
        receipt_hash = _digest(item["receipt_digest"], "generation receipt_digest")
        files = item["files"]
        if not isinstance(files, Mapping) or not files:
            _fail(f"generation files are invalid: {generation}", PromotionIntegrityError)
        file_hashes = {path: _digest(value, f"generation file digest {path}") for path, value in files.items()}
        file_hashes = {path: file_hashes[path] for path in sorted(file_hashes)}
        migration_raw = item["migration"]
        migration = None if migration_raw is None else StateMigration.from_dict(migration_raw).to_dict()
        generation_hash = _digest(item["generation_digest"], "generation digest")
        core = {"schema": GENERATION_SCHEMA, "generation": generation, "parent_generation": parent, "candidate_id": candidate_id, "candidate_digest": candidate_hash, "source_digest": source_hash, "field_state_digest": state_hash, "field_state_schema": state_schema, "receipt_digest": receipt_hash, "files": file_hashes, "migration": migration}
        _require(digest(core) == generation_hash, f"generation receipt digest mismatch: {generation}", PromotionIntegrityError)
        source_root = directory / "source"
        actual_files: dict[str, str] = {}
        for path, expected_hash in file_hashes.items():
            source_path = source_root / Path(path)
            _require(source_path.is_file(), f"generation source is missing: {path}", PromotionIntegrityError)
            actual = source_path.read_text(encoding="utf-8")
            actual_files[path] = actual
            _require(hashlib.sha256(actual.encode("utf-8")).hexdigest() == expected_hash, f"generation source digest mismatch: {path}", PromotionIntegrityError)
        _require(source_digest(actual_files) == source_hash, f"generation source manifest mismatch: {generation}", PromotionIntegrityError)
        receipt = self._read_json(directory / "receipt.json", f"generation {generation} receipt")
        _require(digest(receipt) == receipt_hash, f"generation receipt mutation detected: {generation}", PromotionIntegrityError)
        state = FieldState.from_dict(self._read_json(directory / "field_state.json", f"generation {generation} field state"))
        _require(state.schema == state_schema and state.digest() == state_hash, f"generation field-state mutation detected: {generation}", PromotionIntegrityError)
        candidate = PromotionCandidate(candidate_id, actual_files, receipt)
        _require(candidate.source_digest() == source_hash and candidate.candidate_digest() == candidate_hash, f"generation candidate digest mismatch: {generation}", PromotionIntegrityError)
        if migration is not None:
            _require(parent is not None, f"initial generation has migration: {generation}", PromotionIntegrityError)
            parent_state = self.read_state(parent)
            migrated = apply_state_migration(parent_state, migration)
            _require(migrated.digest() == state_hash and migrated.schema == state_schema, f"generation migration target mismatch: {generation}", PromotionIntegrityError)
        return GenerationRecord(generation, parent, candidate_id, candidate_hash, source_hash, state_hash, state_schema, receipt_hash, file_hashes, migration, generation_hash)

    def read_state(self, generation: str) -> FieldState:
        generation = self._generation_id(generation, "generation")
        path = self.generations_root / generation / "field_state.json"
        return FieldState.from_dict(self._read_json(path, f"generation {generation} field state"))

    def verify_dag(self) -> list[GenerationRecord]:
        records = []
        for path in sorted(self.generations_root.iterdir(), key=lambda item: item.name):
            if path.is_dir() and _GENERATION_ID.fullmatch(path.name):
                records.append(self.read_generation(path.name))
        seen = {record.generation for record in records}
        for record in records:
            if record.parent_generation is not None:
                _require(record.parent_generation in seen, f"DAG parent not found: {record.generation}", PromotionIntegrityError)
        return records

    def _next_generation(self) -> str:
        numbers = [int(match.group(1)) for path in self.generations_root.iterdir() if path.is_dir() and (match := _GENERATION_ID.fullmatch(path.name))]
        return f"g{(max(numbers) + 1 if numbers else 0):04d}"

    @staticmethod
    def _generation_id(value: Any, label: str) -> str:
        value = _text(value, label, 32)
        if not _GENERATION_ID.fullmatch(value):
            _fail(f"{label} is invalid")
        return value

    @staticmethod
    def _read_json(path: Path, label: str) -> Any:
        _require(path.is_file(), f"{label} is missing", PromotionIntegrityError)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            _fail(f"{label} cannot be read: {error}", PromotionIntegrityError)
        _validate_json(value, label)
        return value

    @staticmethod
    def _atomic_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = _canonical_json(value) + b"\n"
        temporary = path.with_name(path.name + ".tmp")
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    def _write_generation(self, record: GenerationRecord, files: Mapping[str, str], receipt: Mapping[str, Any], state: FieldState) -> None:
        final = self.generations_root / record.generation
        _require(not final.exists(), f"generation already exists: {record.generation}", PromotionRefusal)
        staging = Path(tempfile.mkdtemp(prefix=f".{record.generation}.", dir=self.generations_root))
        try:
            for path, source in sorted(files.items()):
                destination = staging / "source" / Path(path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(source, encoding="utf-8", newline="\n")
            self._atomic_json(staging / "receipt.json", receipt)
            self._atomic_json(staging / "field_state.json", state.to_dict())
            self._atomic_json(staging / "generation.json", record.to_dict())
            os.replace(staging, final)
        except Exception:
            if staging.exists():
                for path in sorted(staging.rglob("*"), reverse=True):
                    if path.is_file() or path.is_symlink():
                        path.unlink()
                    elif path.is_dir():
                        path.rmdir()
                staging.rmdir()
            raise

    def _write_pointer(self, record: GenerationRecord) -> None:
        self._atomic_json(self.pointer_path, {"schema": POINTER_SCHEMA, "generation": record.generation, "generation_digest": record.generation_digest})


__all__ = [
    "KERNEL_SCHEMA",
    "GENERATION_SCHEMA",
    "POINTER_SCHEMA",
    "CANDIDATE_SCHEMA",
    "STATE_SCHEMA",
    "MIGRATION_SCHEMA",
    "PromotionError",
    "PromotionRefusal",
    "PromotionIntegrityError",
    "FieldState",
    "StateMigration",
    "PromotionCandidate",
    "GenerationRecord",
    "PromotionKernel",
    "apply_state_migration",
    "candidate_from_workspace",
    "canonical_json",
    "digest",
    "source_digest",
]
