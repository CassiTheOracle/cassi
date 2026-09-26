"""Strict, JSON-serialisable architecture intermediate representation.

The IR is deliberately boring: it is a bounded data model, not an execution
engine.  All executable behaviour belongs to :mod:`architecture_synthesizer`.
Keeping validation here makes an architecture portable between a planner,
compiler, and independent verifier without allowing either to smuggle in
shell/model calls.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, ClassVar, Mapping, Sequence

IR_SCHEMA = "cassimindfield.architecture-ir.v1"
IR_VERSION = 1
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MAX_ITEMS = 4096
_MAX_SOURCE_BYTES = 1_048_576
_MAX_DESCRIPTION = 4096
_MAX_PATH = 240


class ArchitectureValidationError(ValueError):
    """Raised when an architecture document is not safe to compile."""


def _fail(message: str) -> None:
    raise ArchitectureValidationError(message)


def _object(value: Any, label: str, required: set[str], optional: set[str] = set()) -> Mapping[str, Any]:
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


def _string(value: Any, label: str, *, nonempty: bool = True, max_length: int = _MAX_DESCRIPTION) -> str:
    if not isinstance(value, str):
        _fail(f"{label} must be a string")
    if nonempty and not value:
        _fail(f"{label} must not be empty")
    if len(value) > max_length:
        _fail(f"{label} exceeds {max_length} characters")
    return value


def identifier(value: Any, label: str = "identifier") -> str:
    value = _string(value, label, max_length=128)
    if not _IDENTIFIER.fullmatch(value):
        _fail(f"{label} is not a Python-style identifier: {value!r}")
    return value


def relative_python_path(value: Any, label: str = "path") -> str:
    value = _string(value, label, max_length=_MAX_PATH)
    if "\\" in value or value.startswith("/") or value.startswith("."):
        _fail(f"{label} must be a relative POSIX path")
    pieces = value.split("/")
    if any(piece in {"", ".", ".."} for piece in pieces):
        _fail(f"{label} contains an invalid path component")
    if not value.endswith(".py"):
        _fail(f"{label} must name a Python file")
    return value


def _unique(values: Sequence[str], label: str) -> tuple[str, ...]:
    if len(values) > _MAX_ITEMS:
        _fail(f"{label} exceeds {_MAX_ITEMS} entries")
    if len(set(values)) != len(values):
        _fail(f"{label} contains duplicates")
    return tuple(values)


def _string_list(value: Any, label: str, *, identifiers: bool = False, paths: bool = False) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        _fail(f"{label} must be a list")
    result: list[str] = []
    for index, item in enumerate(value):
        item_label = f"{label}[{index}]"
        if identifiers:
            result.append(identifier(item, item_label))
        elif paths:
            result.append(relative_python_path(item, item_label))
        else:
            result.append(_string(item, item_label, max_length=256))
    return _unique(result, label)


def _source(value: Any, label: str) -> str:
    value = _string(value, label, nonempty=False, max_length=_MAX_SOURCE_BYTES)
    if len(value.encode("utf-8")) > _MAX_SOURCE_BYTES:
        _fail(f"{label} exceeds {_MAX_SOURCE_BYTES} UTF-8 bytes")
    try:
        ast.parse(value, filename=label)
    except SyntaxError as error:
        _fail(f"{label} is not valid Python: {error.msg}")
    return value


def _revision(value: Any, label: str) -> str:
    value = _string(value, label, max_length=64)
    if not _REVISION.fullmatch(value):
        _fail(f"{label} is not a bounded revision identifier")
    return value


def _digest(value: Any, label: str) -> str:
    value = _string(value, label, max_length=64)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        _fail(f"{label} must be a lowercase SHA-256 digest")
    return value


def canonical_json(value: Any) -> bytes:
    """Return the one canonical JSON encoding used by all IR digests."""
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ArchitectureValidationError(f"value is not strict JSON: {error}") from error


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class Component:
    id: str
    module: str
    kind: str
    symbols: tuple[str, ...]

    def __post_init__(self) -> None:
        identifier(self.id, "component.id")
        relative_python_path(self.module, "component.module")
        _string(self.kind, "component.kind", max_length=32)
        if self.kind not in {"module", "runtime", "service", "adapter", "test"}:
            _fail(f"component.kind is unsupported: {self.kind!r}")
        _unique(tuple(identifier(item, "component.symbols item") for item in self.symbols), "component.symbols")

    @classmethod
    def from_dict(cls, value: Any) -> "Component":
        item = _object(value, "component", {"id", "module", "kind", "symbols"})
        symbols = _string_list(item["symbols"], "component.symbols", identifiers=True)
        return cls(identifier(item["id"], "component.id"), relative_python_path(item["module"], "component.module"), _string(item["kind"], "component.kind", max_length=32), symbols)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "module": self.module, "kind": self.kind, "symbols": list(self.symbols)}


@dataclass(frozen=True)
class Interface:
    id: str
    provider: str
    consumers: tuple[str, ...]
    symbols: tuple[str, ...]
    protocol: str

    def __post_init__(self) -> None:
        identifier(self.id, "interface.id")
        identifier(self.provider, "interface.provider")
        _unique(tuple(identifier(item, "interface.consumers item") for item in self.consumers), "interface.consumers")
        _unique(tuple(identifier(item, "interface.symbols item") for item in self.symbols), "interface.symbols")
        _string(self.protocol, "interface.protocol", max_length=128)

    @classmethod
    def from_dict(cls, value: Any) -> "Interface":
        item = _object(value, "interface", {"id", "provider", "consumers", "symbols", "protocol"})
        return cls(identifier(item["id"], "interface.id"), identifier(item["provider"], "interface.provider"), _string_list(item["consumers"], "interface.consumers", identifiers=True), _string_list(item["symbols"], "interface.symbols", identifiers=True), _string(item["protocol"], "interface.protocol", max_length=128))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "provider": self.provider, "consumers": list(self.consumers), "symbols": list(self.symbols), "protocol": self.protocol}


@dataclass(frozen=True)
class StateOwnership:
    id: str
    owner: str
    path: str
    kind: str

    def __post_init__(self) -> None:
        identifier(self.id, "state_ownership.id")
        identifier(self.owner, "state_ownership.owner")
        relative_python_path(self.path, "state_ownership.path")
        _string(self.kind, "state_ownership.kind", max_length=32)
        if self.kind not in {"field", "runtime", "cache", "config", "external"}:
            _fail(f"state_ownership.kind is unsupported: {self.kind!r}")

    @classmethod
    def from_dict(cls, value: Any) -> "StateOwnership":
        item = _object(value, "state ownership", {"id", "owner", "path", "kind"})
        return cls(identifier(item["id"], "state_ownership.id"), identifier(item["owner"], "state_ownership.owner"), relative_python_path(item["path"], "state_ownership.path"), _string(item["kind"], "state_ownership.kind", max_length=32))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "owner": self.owner, "path": self.path, "kind": self.kind}


@dataclass(frozen=True)
class Flow:
    id: str
    source: str
    target: str
    interface: str
    kind: str

    def __post_init__(self) -> None:
        identifier(self.id, "flow.id")
        identifier(self.source, "flow.source")
        identifier(self.target, "flow.target")
        identifier(self.interface, "flow.interface")
        _string(self.kind, "flow.kind", max_length=32)
        if self.kind not in {"call", "data", "event", "control"}:
            _fail(f"flow.kind is unsupported: {self.kind!r}")

    @classmethod
    def from_dict(cls, value: Any) -> "Flow":
        item = _object(value, "flow", {"id", "source", "target", "interface", "kind"})
        return cls(identifier(item["id"], "flow.id"), identifier(item["source"], "flow.source"), identifier(item["target"], "flow.target"), identifier(item["interface"], "flow.interface"), _string(item["kind"], "flow.kind", max_length=32))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "source": self.source, "target": self.target, "interface": self.interface, "kind": self.kind}


@dataclass(frozen=True)
class Invariant:
    id: str
    kind: str
    description: str
    paths: tuple[str, ...]

    def __post_init__(self) -> None:
        identifier(self.id, "invariant.id")
        _string(self.kind, "invariant.kind", max_length=32)
        if self.kind not in {"syntax", "path", "ownership", "interface", "determinism", "custom"}:
            _fail(f"invariant.kind is unsupported: {self.kind!r}")
        _string(self.description, "invariant.description")
        _unique(tuple(relative_python_path(item, "invariant.paths item") for item in self.paths), "invariant.paths")

    @classmethod
    def from_dict(cls, value: Any) -> "Invariant":
        item = _object(value, "invariant", {"id", "kind", "description", "paths"})
        return cls(identifier(item["id"], "invariant.id"), _string(item["kind"], "invariant.kind", max_length=32), _string(item["description"], "invariant.description"), _string_list(item["paths"], "invariant.paths", paths=True))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "description": self.description, "paths": list(self.paths)}


@dataclass(frozen=True)
class ProofObligation:
    id: str
    kind: str
    description: str
    target: str

    def __post_init__(self) -> None:
        identifier(self.id, "proof_obligation.id")
        _string(self.kind, "proof_obligation.kind", max_length=32)
        if self.kind not in {"parse", "digest", "behavior", "ownership", "migration", "refusal", "custom"}:
            _fail(f"proof_obligation.kind is unsupported: {self.kind!r}")
        _string(self.description, "proof_obligation.description")
        _string(self.target, "proof_obligation.target", max_length=_MAX_PATH)

    @classmethod
    def from_dict(cls, value: Any) -> "ProofObligation":
        item = _object(value, "proof obligation", {"id", "kind", "description", "target"})
        return cls(identifier(item["id"], "proof_obligation.id"), _string(item["kind"], "proof_obligation.kind", max_length=32), _string(item["description"], "proof_obligation.description"), _string(item["target"], "proof_obligation.target", max_length=_MAX_PATH))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "description": self.description, "target": self.target}


@dataclass(frozen=True)
class MigrationMetadata:
    source_revision: str
    target_revision: str
    strategy: str
    compatibility: str
    notes: str
    source_digest: str | None = None

    def __post_init__(self) -> None:
        _revision(self.source_revision, "migration.source_revision")
        _revision(self.target_revision, "migration.target_revision")
        _string(self.strategy, "migration.strategy", max_length=32)
        if self.strategy not in {"clean_cutover", "incremental", "compatibility"}:
            _fail(f"migration.strategy is unsupported: {self.strategy!r}")
        _string(self.compatibility, "migration.compatibility", max_length=32)
        if self.compatibility not in {"breaking", "compatible", "unknown"}:
            _fail(f"migration.compatibility is unsupported: {self.compatibility!r}")
        _string(self.notes, "migration.notes")
        if self.source_digest is not None:
            _digest(self.source_digest, "migration.source_digest")

    @classmethod
    def from_dict(cls, value: Any) -> "MigrationMetadata":
        item = _object(value, "migration", {"source_revision", "target_revision", "strategy", "compatibility", "notes"}, {"source_digest"})
        source_digest = item.get("source_digest")
        return cls(_revision(item["source_revision"], "migration.source_revision"), _revision(item["target_revision"], "migration.target_revision"), _string(item["strategy"], "migration.strategy", max_length=32), _string(item["compatibility"], "migration.compatibility", max_length=32), _string(item["notes"], "migration.notes"), None if source_digest is None else _digest(source_digest, "migration.source_digest"))

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"source_revision": self.source_revision, "target_revision": self.target_revision, "strategy": self.strategy, "compatibility": self.compatibility, "notes": self.notes}
        if self.source_digest is not None:
            value["source_digest"] = self.source_digest
        return value


class Operation:
    """Base class for all typed architecture edits."""

    kind: ClassVar[str]
    id: str

    @classmethod
    def from_dict(cls, value: Any) -> "Operation":
        if not isinstance(value, Mapping):
            _fail("operation must be an object")
        kind = value.get("kind")
        factory = _OPERATION_TYPES.get(kind)
        if factory is None:
            _fail(f"unsupported operation kind: {kind!r}")
        return factory.from_dict(value)

    def to_dict(self) -> dict[str, Any]:  # pragma: no cover - concrete classes override
        raise NotImplementedError


@dataclass(frozen=True)
class CreateModule(Operation):
    kind: ClassVar[str] = "create_module"
    id: str
    path: str
    component: str
    source: str

    @classmethod
    def from_dict(cls, value: Any) -> "CreateModule":
        item = _object(value, "create_module", {"id", "kind", "path", "component", "source"})
        if item["kind"] != cls.kind:
            _fail("create_module kind mismatch")
        return cls(identifier(item["id"], "operation.id"), relative_python_path(item["path"], "operation.path"), identifier(item["component"], "operation.component"), _source(item["source"], "operation.source"))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "path": self.path, "component": self.component, "source": self.source}


@dataclass(frozen=True)
class DeleteModule(Operation):
    kind: ClassVar[str] = "delete_module"
    id: str
    path: str

    @classmethod
    def from_dict(cls, value: Any) -> "DeleteModule":
        item = _object(value, "delete_module", {"id", "kind", "path"})
        if item["kind"] != cls.kind:
            _fail("delete_module kind mismatch")
        return cls(identifier(item["id"], "operation.id"), relative_python_path(item["path"], "operation.path"))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "path": self.path}


@dataclass(frozen=True)
class MoveModule(Operation):
    kind: ClassVar[str] = "move_module"
    id: str
    source: str
    target: str

    @classmethod
    def from_dict(cls, value: Any) -> "MoveModule":
        item = _object(value, "move_module", {"id", "kind", "source", "target"})
        if item["kind"] != cls.kind:
            _fail("move_module kind mismatch")
        return cls(identifier(item["id"], "operation.id"), relative_python_path(item["source"], "operation.source"), relative_python_path(item["target"], "operation.target"))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "source": self.source, "target": self.target}


@dataclass(frozen=True)
class SplitTarget:
    path: str
    component: str
    source: str

    @classmethod
    def from_dict(cls, value: Any) -> "SplitTarget":
        item = _object(value, "split_module target", {"path", "component", "source"})
        return cls(relative_python_path(item["path"], "split target.path"), identifier(item["component"], "split target.component"), _source(item["source"], "split target.source"))

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "component": self.component, "source": self.source}


@dataclass(frozen=True)
class SplitModule(Operation):
    kind: ClassVar[str] = "split_module"
    id: str
    source: str
    targets: tuple[SplitTarget, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "SplitModule":
        item = _object(value, "split_module", {"id", "kind", "source", "targets"})
        if item["kind"] != cls.kind:
            _fail("split_module kind mismatch")
        if not isinstance(item["targets"], list) or not item["targets"]:
            _fail("split_module.targets must be a non-empty list")
        targets = tuple(SplitTarget.from_dict(target) for target in item["targets"])
        if len({target.path for target in targets}) != len(targets):
            _fail("split_module.targets contains duplicate paths")
        if len({target.component for target in targets}) != len(targets):
            _fail("split_module.targets contains duplicate components")
        return cls(identifier(item["id"], "operation.id"), relative_python_path(item["source"], "operation.source"), targets)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "source": self.source, "targets": [target.to_dict() for target in self.targets]}


@dataclass(frozen=True)
class MergeModule(Operation):
    kind: ClassVar[str] = "merge_module"
    id: str
    sources: tuple[str, ...]
    target: str
    source: str

    @classmethod
    def from_dict(cls, value: Any) -> "MergeModule":
        item = _object(value, "merge_module", {"id", "kind", "sources", "target", "source"})
        if item["kind"] != cls.kind:
            _fail("merge_module kind mismatch")
        sources = _string_list(item["sources"], "merge_module.sources", paths=True)
        if len(sources) < 2:
            _fail("merge_module.sources must contain at least two paths")
        return cls(identifier(item["id"], "operation.id"), sources, relative_python_path(item["target"], "merge_module.target"), _source(item["source"], "merge_module.source"))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "sources": list(self.sources), "target": self.target, "source": self.source}


@dataclass(frozen=True)
class SignatureMigration(Operation):
    kind: ClassVar[str] = "signature_migration"
    id: str
    path: str
    symbol: str
    old_signature: str
    new_signature: str

    @classmethod
    def from_dict(cls, value: Any) -> "SignatureMigration":
        item = _object(value, "signature_migration", {"id", "kind", "path", "symbol", "old_signature", "new_signature"})
        if item["kind"] != cls.kind:
            _fail("signature_migration kind mismatch")
        symbol = identifier(item["symbol"], "signature_migration.symbol")
        old = _string(item["old_signature"], "signature_migration.old_signature", max_length=4096)
        new = _string(item["new_signature"], "signature_migration.new_signature", max_length=4096)
        _signature_name(old, symbol, "signature_migration.old_signature")
        _signature_name(new, symbol, "signature_migration.new_signature")
        return cls(identifier(item["id"], "operation.id"), relative_python_path(item["path"], "signature_migration.path"), symbol, old, new)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "path": self.path, "symbol": self.symbol, "old_signature": self.old_signature, "new_signature": self.new_signature}


@dataclass(frozen=True)
class SymbolRename(Operation):
    kind: ClassVar[str] = "symbol_rename"
    id: str
    old_name: str
    new_name: str
    paths: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "SymbolRename":
        item = _object(value, "symbol_rename", {"id", "kind", "old_name", "new_name", "paths"})
        if item["kind"] != cls.kind:
            _fail("symbol_rename kind mismatch")
        old_name = identifier(item["old_name"], "symbol_rename.old_name")
        new_name = identifier(item["new_name"], "symbol_rename.new_name")
        if old_name == new_name:
            _fail("symbol_rename names must differ")
        paths = _string_list(item["paths"], "symbol_rename.paths", paths=True)
        if not paths:
            _fail("symbol_rename.paths must not be empty")
        return cls(identifier(item["id"], "operation.id"), old_name, new_name, paths)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "old_name": self.old_name, "new_name": self.new_name, "paths": list(self.paths)}


@dataclass(frozen=True)
class InlineCall(Operation):
    kind: ClassVar[str] = "inline_call"
    id: str
    path: str
    function: str
    find: str
    replace: str

    @classmethod
    def from_dict(cls, value: Any) -> "InlineCall":
        item = _object(value, "inline_call", {"id", "kind", "path", "function", "find", "replace"})
        if item["kind"] != cls.kind:
            _fail("inline_call kind mismatch")
        return cls(identifier(item["id"], "operation.id"), relative_python_path(item["path"], "inline_call.path"), identifier(item["function"], "inline_call.function"), _string(item["find"], "inline_call.find", max_length=4096), _string(item["replace"], "inline_call.replace", nonempty=False, max_length=4096))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "path": self.path, "function": self.function, "find": self.find, "replace": self.replace}


@dataclass(frozen=True)
class SourceReplacement(Operation):
    kind: ClassVar[str] = "source_replacement"
    id: str
    path: str
    find: str
    replace: str
    expected_count: int = 1

    @classmethod
    def from_dict(cls, value: Any) -> "SourceReplacement":
        item = _object(value, "source_replacement", {"id", "kind", "path", "find", "replace"}, {"expected_count"})
        if item["kind"] != cls.kind:
            _fail("source_replacement kind mismatch")
        expected = item.get("expected_count", 1)
        if isinstance(expected, bool) or not isinstance(expected, int) or expected != 1:
            _fail("source_replacement.expected_count must be exactly 1")
        return cls(identifier(item["id"], "operation.id"), relative_python_path(item["path"], "source_replacement.path"), _string(item["find"], "source_replacement.find"), _string(item["replace"], "source_replacement.replace", nonempty=False), expected)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "path": self.path, "find": self.find, "replace": self.replace, "expected_count": self.expected_count}


def _signature_name(signature: str, symbol: str, label: str) -> None:
    try:
        tree = ast.parse(signature + "\n    pass\n", filename=label)
    except SyntaxError as error:
        _fail(f"{label} is not a function signature: {error.msg}")
    if len(tree.body) != 1 or not isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)) or tree.body[0].name != symbol:
        _fail(f"{label} must define {symbol!r}")


_OPERATION_TYPES: dict[str, type[Operation]] = {
    CreateModule.kind: CreateModule,
    DeleteModule.kind: DeleteModule,
    MoveModule.kind: MoveModule,
    SplitModule.kind: SplitModule,
    MergeModule.kind: MergeModule,
    SignatureMigration.kind: SignatureMigration,
    SymbolRename.kind: SymbolRename,
    InlineCall.kind: InlineCall,
    SourceReplacement.kind: SourceReplacement,
}


@dataclass(frozen=True)
class ArchitectureIR:
    schema: str
    version: int
    components: tuple[Component, ...]
    interfaces: tuple[Interface, ...]
    state_ownership: tuple[StateOwnership, ...]
    flows: tuple[Flow, ...]
    invariants: tuple[Invariant, ...]
    operations: tuple[Operation, ...]
    proof_obligations: tuple[ProofObligation, ...]
    migration: MigrationMetadata

    def __post_init__(self) -> None:
        if self.schema != IR_SCHEMA:
            _fail(f"unsupported architecture schema: {self.schema!r}")
        if self.version != IR_VERSION:
            _fail(f"unsupported architecture IR version: {self.version!r}")
        for label, values in (("components", self.components), ("interfaces", self.interfaces), ("state_ownership", self.state_ownership), ("flows", self.flows), ("invariants", self.invariants), ("operations", self.operations), ("proof_obligations", self.proof_obligations)):
            if len(values) > _MAX_ITEMS:
                _fail(f"{label} exceeds {_MAX_ITEMS} entries")
        component_ids = _unique(tuple(item.id for item in self.components), "component ids")
        component_modules = _unique(tuple(item.module for item in self.components), "component modules")
        interface_ids = _unique(tuple(item.id for item in self.interfaces), "interface ids")
        state_ids = _unique(tuple(item.id for item in self.state_ownership), "state ownership ids")
        flow_ids = _unique(tuple(item.id for item in self.flows), "flow ids")
        invariant_ids = _unique(tuple(item.id for item in self.invariants), "invariant ids")
        operation_ids = _unique(tuple(item.id for item in self.operations), "operation ids")
        proof_ids = _unique(tuple(item.id for item in self.proof_obligations), "proof obligation ids")
        all_ids = list(component_ids) + list(interface_ids) + list(state_ids) + list(flow_ids) + list(invariant_ids) + list(operation_ids) + list(proof_ids)
        if len(set(all_ids)) != len(all_ids):
            _fail("architecture identifiers must be globally unique")
        component_id_set = set(component_ids)
        module_set = set(component_modules)
        interface_id_set = set(interface_ids)
        operation_id_set = set(operation_ids)
        owners: set[str] = set()
        state_paths: set[str] = set()
        for state in self.state_ownership:
            if state.owner not in component_id_set:
                _fail(f"state ownership references unknown component: {state.owner!r}")
            if state.owner in owners:
                _fail(f"component has duplicate state owners: {state.owner!r}")
            owners.add(state.owner)
            if state.path in state_paths:
                _fail(f"state ownership path is duplicated: {state.path!r}")
            state_paths.add(state.path)
            if state.path not in module_set:
                _fail(f"state ownership path is not a component module: {state.path!r}")
        for interface in self.interfaces:
            if interface.provider not in component_id_set:
                _fail(f"interface references unknown provider: {interface.provider!r}")
            if any(consumer not in component_id_set for consumer in interface.consumers):
                _fail(f"interface references unknown consumer: {interface.id!r}")
            provider_symbols = next(item.symbols for item in self.components if item.id == interface.provider)
            if any(symbol not in provider_symbols for symbol in interface.symbols):
                _fail(f"interface symbol is not exported by provider: {interface.id!r}")
        for flow in self.flows:
            if flow.source not in component_id_set or flow.target not in component_id_set:
                _fail(f"flow references unknown component: {flow.id!r}")
            if flow.interface not in interface_id_set:
                _fail(f"flow references unknown interface: {flow.id!r}")
            interface = next(item for item in self.interfaces if item.id == flow.interface)
            if interface.provider != flow.source or flow.target not in interface.consumers:
                _fail(f"flow does not match interface endpoints: {flow.id!r}")
        for invariant in self.invariants:
            if any(path not in module_set for path in invariant.paths):
                _fail(f"invariant references unknown component module: {invariant.id!r}")
        for obligation in self.proof_obligations:
            target = obligation.target
            if target not in component_id_set and target not in interface_id_set and target not in operation_id_set and target not in invariant_ids and target not in module_set:
                _fail(f"proof obligation references unknown target: {target!r}")
        for operation in self.operations:
            _validate_operation_identifiers(operation, component_id_set)
        if self.migration.source_revision == self.migration.target_revision:
            _fail("migration revisions must differ")

    @classmethod
    def from_dict(cls, value: Any) -> "ArchitectureIR":
        item = _object(value, "architecture IR", {"schema", "version", "components", "interfaces", "state_ownership", "flows", "invariants", "operations", "proof_obligations", "migration"})
        if item["schema"] != IR_SCHEMA:
            _fail(f"unsupported architecture schema: {item['schema']!r}")
        if item["version"] != IR_VERSION or isinstance(item["version"], bool) or not isinstance(item["version"], int):
            _fail("architecture IR version must be 1")
        fields: list[tuple[str, type[Any]]] = [("components", Component), ("interfaces", Interface), ("state_ownership", StateOwnership), ("flows", Flow), ("invariants", Invariant), ("proof_obligations", ProofObligation)]
        parsed: dict[str, Any] = {}
        for key, factory in fields:
            raw = item[key]
            if not isinstance(raw, list):
                _fail(f"architecture IR {key} must be a list")
            parsed[key] = tuple(factory.from_dict(entry) for entry in raw)
        raw_operations = item["operations"]
        if not isinstance(raw_operations, list):
            _fail("architecture IR operations must be a list")
        parsed["operations"] = tuple(Operation.from_dict(entry) for entry in raw_operations)
        parsed["migration"] = MigrationMetadata.from_dict(item["migration"])
        return cls(schema=item["schema"], version=item["version"], **parsed)

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.schema, "version": self.version, "components": [item.to_dict() for item in self.components], "interfaces": [item.to_dict() for item in self.interfaces], "state_ownership": [item.to_dict() for item in self.state_ownership], "flows": [item.to_dict() for item in self.flows], "invariants": [item.to_dict() for item in self.invariants], "operations": [item.to_dict() for item in self.operations], "proof_obligations": [item.to_dict() for item in self.proof_obligations], "migration": self.migration.to_dict()}

    def to_json(self) -> str:
        return canonical_json(self.to_dict()).decode("utf-8")

    def validate(self) -> "ArchitectureIR":
        """Re-run the strict constructor checks and return this IR."""
        type(self)(
            schema=self.schema,
            version=self.version,
            components=self.components,
            interfaces=self.interfaces,
            state_ownership=self.state_ownership,
            flows=self.flows,
            invariants=self.invariants,
            operations=self.operations,
            proof_obligations=self.proof_obligations,
            migration=self.migration,
        )
        return self

    @classmethod
    def from_json(cls, value: str) -> "ArchitectureIR":
        if not isinstance(value, str):
            _fail("architecture JSON must be a string")
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as error:
            _fail(f"architecture JSON is invalid: {error.msg}")
        return cls.from_dict(parsed)

    def digest(self) -> str:
        return digest(self.to_dict())


def _validate_operation_identifiers(operation: Operation, component_ids: set[str]) -> None:
    if isinstance(operation, (CreateModule, SplitModule)):
        components = [operation.component] if isinstance(operation, CreateModule) else [target.component for target in operation.targets]
        for component in components:
            if component not in component_ids:
                _fail(f"operation references unknown component: {component!r}")


def architecture_ir_from_dict(value: Any) -> ArchitectureIR:
    """Functional entry point kept convenient for scripts and verifiers."""
    return ArchitectureIR.from_dict(value)


def validate_architecture(value: ArchitectureIR | Mapping[str, Any]) -> ArchitectureIR:
    """Validate either an IR object or a strict JSON-shaped mapping."""
    if isinstance(value, ArchitectureIR):
        return value.validate()
    return ArchitectureIR.from_dict(value)


def example_input_workspace() -> dict[str, str]:
    """A complete two-file Python workspace used by the independent verifier."""
    return {
        "src/core.py": "def add(value):\n    return value + 1\n",
        "src/runtime.py": "from core import add\n\n\ndef run(value):\n    return add(value)\n",
    }


def example_architecture_ir() -> ArchitectureIR:
    """Return a small, complete multi-file successor architecture."""
    components = (
        Component("core", "src/core_math.py", "module", ("increment",)),
        Component("runtime", "src/runtime.py", "runtime", ("run",)),
        Component("api", "src/api.py", "adapter", ("execute",)),
    )
    interfaces = (
        Interface("core_runtime", "core", ("runtime",), ("increment",), "python-import"),
        Interface("runtime_api", "runtime", ("api",), ("run",), "python-import"),
    )
    return ArchitectureIR(
        schema=IR_SCHEMA,
        version=IR_VERSION,
        components=components,
        interfaces=interfaces,
        state_ownership=(StateOwnership("runtime_state", "runtime", "src/runtime.py", "runtime"),),
        flows=(Flow("core_to_runtime", "core", "runtime", "core_runtime", "call"), Flow("runtime_to_api", "runtime", "api", "runtime_api", "call")),
        invariants=(
            Invariant("all_python_parses", "syntax", "Every successor module parses as Python.", ("src/core_math.py", "src/runtime.py", "src/api.py")),
            Invariant("one_runtime_owner", "ownership", "Runtime state has exactly one owner.", ("src/runtime.py",)),
        ),
        operations=(
            MoveModule("move_core", "src/core.py", "src/core_math.py"),
            SymbolRename("rename_add", "add", "increment", ("src/core_math.py", "src/runtime.py")),
            SignatureMigration("migrate_increment", "src/core_math.py", "increment", "def increment(value):", "def increment(value, bias=1):"),
            SourceReplacement("use_bias", "src/core_math.py", "return value + 1", "return value + bias"),
            SourceReplacement("retarget_import", "src/runtime.py", "from core import increment", "from core_math import increment"),
            CreateModule("create_api", "src/api.py", "api", "from runtime import run\n\n\ndef execute(value):\n    return run(value)\n"),
        ),
        proof_obligations=(
            ProofObligation("parse_successor", "parse", "The synthesized successor parses independently.", "all_python_parses"),
            ProofObligation("digest_stable", "digest", "Repeated synthesis has one source digest.", "create_api"),
            ProofObligation("owner_unique", "ownership", "State owner uniqueness remains true.", "one_runtime_owner"),
        ),
        migration=MigrationMetadata("scenario-v12", "architecture-v1", "clean_cutover", "breaking", "Move the core into an explicit successor API."),
    )


def build_example() -> tuple[dict[str, str], ArchitectureIR]:
    return example_input_workspace(), example_architecture_ir()


__all__ = [
    "ArchitectureIR",
    "ArchitectureValidationError",
    "Component",
    "Interface",
    "StateOwnership",
    "Flow",
    "Invariant",
    "ProofObligation",
    "MigrationMetadata",
    "Operation",
    "CreateModule",
    "DeleteModule",
    "MoveModule",
    "SplitTarget",
    "SplitModule",
    "MergeModule",
    "SignatureMigration",
    "SymbolRename",
    "InlineCall",
    "SourceReplacement",
    "IR_SCHEMA",
    "IR_VERSION",
    "canonical_json",
    "digest",
    "validate_architecture",
    "example_input_workspace",
    "example_architecture_ir",
    "build_example",
]
