"""Canonical guarded compilation artifacts for field-owned programs.

Artifacts are derived implementations of an identified program.  They never own
adaptive state: adoption, guard outcomes, costs, and deoptimization history live
inside the invoking regional continuation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from programs.python.records import canonical_json_bytes, digest_value


ARTIFACT_SCHEMA = "cassifi.compiled-regional-artifact.v1"
COMPILER_VERSION = "cassifi.fixed-python-specializer.v1"


class OptimizationRecordError(ValueError):
    """A compiled artifact is incomplete or not canonically representable."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 65_536:
        raise OptimizationRecordError(f"{label} must be bounded nonempty text")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise OptimizationRecordError(f"{label} must be a SHA-256 digest")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise OptimizationRecordError(f"{label} must be a SHA-256 digest") from exc
    return value.lower()


def _plain(value: Any) -> Any:
    try:
        return __import__("json").loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise OptimizationRecordError("artifact value is not canonical JSON") from exc


@dataclass(frozen=True, slots=True)
class CompiledArtifact:
    """One exact regional replacement plus complete guard/deoptimization data."""

    artifact_id: str
    kind: str
    program_id: str
    program_version: int
    program_sha256: str
    source_sha256: str
    code_id: str
    start_pc: int
    next_pc: int
    original_sha256: str
    replacement: Mapping[str, Any]
    guards: tuple[Mapping[str, Any], ...]
    semantics_sha256: str
    regional_catalog_sha256: str
    arithmetic_profile_sha256: str
    target_profile: Mapping[str, Any]
    dependencies: tuple[str, ...]
    logical_instructions: int
    safe_points: tuple[Mapping[str, Any], ...]
    deoptimization: Mapping[str, Any]
    proof: Mapping[str, Any]
    compiler_version: str = COMPILER_VERSION

    def __post_init__(self) -> None:
        for value, label in (
            (self.artifact_id, "artifact_id"),
            (self.kind, "kind"),
            (self.program_id, "program_id"),
            (self.code_id, "code_id"),
            (self.compiler_version, "compiler_version"),
        ):
            _text(value, label)
        if self.kind not in {"constant-fold", "guarded-load-name"}:
            raise OptimizationRecordError("artifact kind is unsupported")
        if isinstance(self.program_version, bool) or self.program_version < 1:
            raise OptimizationRecordError("program_version must be positive")
        if (
            isinstance(self.start_pc, bool)
            or isinstance(self.next_pc, bool)
            or self.start_pc < 0
            or self.next_pc <= self.start_pc
        ):
            raise OptimizationRecordError("artifact program counters are invalid")
        if (
            isinstance(self.logical_instructions, bool)
            or self.logical_instructions < 1
            or self.logical_instructions != self.next_pc - self.start_pc
        ):
            raise OptimizationRecordError("logical instruction charge is invalid")
        for value, label in (
            (self.program_sha256, "program_sha256"),
            (self.source_sha256, "source_sha256"),
            (self.original_sha256, "original_sha256"),
            (self.semantics_sha256, "semantics_sha256"),
            (self.regional_catalog_sha256, "regional_catalog_sha256"),
            (self.arithmetic_profile_sha256, "arithmetic_profile_sha256"),
        ):
            _digest(value, label)
        object.__setattr__(self, "replacement", _plain(dict(self.replacement)))
        object.__setattr__(self, "guards", tuple(_plain(dict(row)) for row in self.guards))
        object.__setattr__(self, "target_profile", _plain(dict(self.target_profile)))
        object.__setattr__(self, "dependencies", tuple(_text(item, "dependency") for item in self.dependencies))
        object.__setattr__(self, "safe_points", tuple(_plain(dict(row)) for row in self.safe_points))
        object.__setattr__(self, "deoptimization", _plain(dict(self.deoptimization)))
        object.__setattr__(self, "proof", _plain(dict(self.proof)))
        canonical_json_bytes(self.as_dict())

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "schema": ARTIFACT_SCHEMA,
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "program_id": self.program_id,
            "program_version": self.program_version,
            "program_sha256": self.program_sha256,
            "source_sha256": self.source_sha256,
            "code_id": self.code_id,
            "start_pc": self.start_pc,
            "next_pc": self.next_pc,
            "original_sha256": self.original_sha256,
            "replacement": _plain(self.replacement),
            "guards": [_plain(row) for row in self.guards],
            "semantics_sha256": self.semantics_sha256,
            "regional_catalog_sha256": self.regional_catalog_sha256,
            "arithmetic_profile_sha256": self.arithmetic_profile_sha256,
            "target_profile": _plain(self.target_profile),
            "dependencies": list(self.dependencies),
            "logical_instructions": self.logical_instructions,
            "safe_points": [_plain(row) for row in self.safe_points],
            "deoptimization": _plain(self.deoptimization),
            "proof": _plain(self.proof),
            "compiler_version": self.compiler_version,
        }

    @property
    def sha256(self) -> str:
        return digest_value(self.as_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CompiledArtifact":
        if not isinstance(value, Mapping) or value.get("schema") != ARTIFACT_SCHEMA:
            raise OptimizationRecordError("compiled artifact schema is invalid")
        return cls(
            artifact_id=value["artifact_id"],
            kind=value["kind"],
            program_id=value["program_id"],
            program_version=value["program_version"],
            program_sha256=value["program_sha256"],
            source_sha256=value["source_sha256"],
            code_id=value["code_id"],
            start_pc=value["start_pc"],
            next_pc=value["next_pc"],
            original_sha256=value["original_sha256"],
            replacement=value["replacement"],
            guards=tuple(value.get("guards", ())),
            semantics_sha256=value["semantics_sha256"],
            regional_catalog_sha256=value["regional_catalog_sha256"],
            arithmetic_profile_sha256=value["arithmetic_profile_sha256"],
            target_profile=value["target_profile"],
            dependencies=tuple(value.get("dependencies", ())),
            logical_instructions=value["logical_instructions"],
            safe_points=tuple(value.get("safe_points", ())),
            deoptimization=value["deoptimization"],
            proof=value["proof"],
            compiler_version=value.get("compiler_version", COMPILER_VERSION),
        )


def artifact_set_sha256(values: Sequence[Mapping[str, Any]]) -> str:
    """Identify an ordered adopted artifact set."""

    return digest_value([CompiledArtifact.from_dict(value).as_dict() for value in values])


__all__ = [
    "ARTIFACT_SCHEMA",
    "COMPILER_VERSION",
    "CompiledArtifact",
    "OptimizationRecordError",
    "artifact_set_sha256",
]
