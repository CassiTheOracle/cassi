from __future__ import annotations

"""Typed, field-owned atlas built on the common variational relation core.

The canonical :class:`AtlasState` is the only adaptive owner.  Numerical chart
memory, learned structure, support, predictions, plans, and measured
computational experience are serialized together.  Exact source bytes and
nonlearned authority remain explicit boundaries rather than hidden learners.
"""

import base64
import hashlib
import itertools
import json
import math
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Final, Mapping, Never, Sequence

import torch
from torch import Tensor

from cassi_variational_field import VariationalField
from cassi_temporal_field import TemporalField, TemporalFieldError
from cassi_resonant_field import (
    ResonantProblem,
    ResonantWorkspace,
    advance_workspace,
    apply_pool_impulse,
    bind_workspace,
    expand_resolution,
    initial_workspace,
    inspect_workspace,
)
from cassi_field_transceiver import (
    advance_transceiver,
    condense_workspace,
    inspect_transceiver,
    reset_transceiver as reset_transceiver_workspace,
    validate_transceiver,
)


ATLAS_SCHEMA: Final[str] = "cassifi.field-atlas.v2"
ATLAS_LEGACY_SCHEMA: Final[str] = "cassifi.field-atlas.v1"
ARITHMETIC_PROFILE: Final[str] = "cpu-float64-reference.v1"
_TEMPORAL_ADMISSION_WORK: Final[float] = 1e-3
EPISTEMIC_TYPES: Final[frozenset[str]] = frozenset(
    {"observed", "asserted", "derived", "hypothetical", "desired", "permitted"}
)
LEARNING_MODES: Final[frozenset[str]] = frozenset(
    {"stationary", "contextual", "structural"}
)
PROGRAM_STATUSES: Final[frozenset[str]] = frozenset(
    {"candidate", "promoted", "stale", "rejected"}
)
CHART_STATUSES: Final[frozenset[str]] = frozenset({"active", "stale", "revoked"})
VARIABLE_KINDS: Final[frozenset[str]] = frozenset(
    {"scalar", "constant", "boolean", "symbol", "interval", "vector"}
)
_ATLAS_PAGE_NAMES: Final[tuple[str, ...]] = (
    "variables",
    "charts",
    "programs",
    "constructions",
    "macros",
    "predictions",
    "plans",
    "computation_records",
    "transition_log",
    "prepared_queries",
    "transceivers",
    "temporal_fields",
)

class FieldIntelligenceError(RuntimeError):
    def __init__(
        self, code: str, message: str, *, details: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})

class _FrozenDict(dict[str, Any]):
    """JSON-compatible mapping that cannot be mutated after construction."""

    __slots__ = ()

    @staticmethod
    def _immutable(*args: Any, **kwargs: Any) -> Never:
        del args, kwargs
        raise TypeError("field-owned JSON values are immutable")
    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return _FrozenDict({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _json_plain(value: Any) -> Any:
    """Return detached ordinary JSON containers for an external response."""

    return json.loads(canonical_json_bytes(value))


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FieldIntelligenceError(
            "NONCANONICAL_VALUE", "value cannot be represented as canonical JSON"
        ) from exc


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


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


def _finite(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FieldIntelligenceError("INVALID_NUMERIC_VALUE", f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        qualifier = "finite and positive" if positive else "finite"
        raise FieldIntelligenceError(
            "INVALID_NUMERIC_VALUE", f"{label} must be {qualifier}"
        )
    return result


def _json_value(value: Any, label: str) -> Any:
    try:
        encoded = canonical_json_bytes(value)
    except FieldIntelligenceError as exc:
        raise FieldIntelligenceError(
            "INVALID_TYPED_VALUE", f"{label} must be canonical JSON data"
        ) from exc
    if len(encoded) > 64 * 1024:
        raise FieldIntelligenceError(
            "INVALID_TYPED_VALUE", f"{label} exceeds the typed-value byte limit"
        )
    return _freeze_json(json.loads(encoded))

def _canonical_diagnostics(value: Any, label: str) -> Any:
    """Canonicalize receipts while representing unsupported nonfinite diagnostics as null."""
    if isinstance(value, Mapping):
        return _json_value(
            {str(key): _canonical_diagnostics(item, label) for key, item in value.items()},
            label,
        )
    if isinstance(value, (tuple, list)):
        return _json_value(
            [_canonical_diagnostics(item, label) for item in value],
            label,
        )
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _tensor_payload(value: Tensor) -> Mapping[str, Any]:
    if (
        not isinstance(value, Tensor)
        or value.dtype != torch.float64
        or value.requires_grad
        or not bool(torch.isfinite(value).all())
    ):
        raise FieldIntelligenceError(
            "INVALID_FIELD_PAGE", "numeric field pages must be finite float64 tensors"
        )
    raw = value.detach().cpu().contiguous().numpy().astype("<f8", copy=False).tobytes()
    return {
        "bytes_base64": base64.b64encode(raw).decode("ascii"),
        "dtype": "float64-le",
        "shape": list(value.shape),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _tensor_from_payload(value: Any) -> Tensor:
    if not isinstance(value, Mapping) or set(value) != {
        "bytes_base64",
        "dtype",
        "shape",
        "sha256",
    }:
        raise FieldIntelligenceError("INVALID_FIELD_PAGE", "numeric page envelope is invalid")
    if value["dtype"] != "float64-le":
        raise FieldIntelligenceError("INVALID_FIELD_PAGE", "numeric page dtype is incompatible")
    shape = value["shape"]
    if (
        not isinstance(shape, list)
        or not shape
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in shape)
    ):
        raise FieldIntelligenceError("INVALID_FIELD_PAGE", "numeric page shape is invalid")
    try:
        raw = base64.b64decode(value["bytes_base64"], validate=True)
    except Exception as exc:
        raise FieldIntelligenceError("INVALID_FIELD_PAGE", "numeric page bytes are invalid") from exc
    if hashlib.sha256(raw).hexdigest() != _digest(value["sha256"], "page sha256"):
        raise FieldIntelligenceError("INVALID_FIELD_PAGE", "numeric page digest does not match")
    expected = math.prod(shape) * 8
    if len(raw) != expected:
        raise FieldIntelligenceError("INVALID_FIELD_PAGE", "numeric page byte length is invalid")
    # bytearray makes the buffer writable, avoiding a non-writable-buffer tensor.
    return torch.frombuffer(bytearray(raw), dtype=torch.float64).clone().reshape(shape)


@dataclass(frozen=True, slots=True)
class VariableSpec:
    variable_id: str
    kind: str = "scalar"
    unit: str = "1"
    frame: str = "canonical"
    lower: float | None = None
    upper: float | None = None
    constant: float | None = None

    def __post_init__(self) -> None:
        _identifier(self.variable_id, "variable_id")
        if self.kind not in VARIABLE_KINDS:
            raise FieldIntelligenceError("INVALID_VARIABLE", "variable kind is unsupported")
        _identifier(self.unit, "variable unit")
        _identifier(self.frame, "variable frame")
        lower = None if self.lower is None else _finite(self.lower, "variable lower bound")
        upper = None if self.upper is None else _finite(self.upper, "variable upper bound")
        if lower is not None and upper is not None and lower > upper:
            raise FieldIntelligenceError("INVALID_VARIABLE", "variable bounds are reversed")
        if self.kind == "constant":
            if self.constant is None:
                raise FieldIntelligenceError("INVALID_VARIABLE", "constant variable needs a value")
            constant = _finite(self.constant, "constant value")
            if lower is not None and constant < lower or upper is not None and constant > upper:
                raise FieldIntelligenceError("INVALID_VARIABLE", "constant is outside its domain")
        elif self.constant is not None:
            raise FieldIntelligenceError(
                "INVALID_VARIABLE", "only a constant variable may carry a constant value"
            )

    def contains(self, value: float, *, radius: float = 0.0) -> bool:
        number = _finite(value, self.variable_id)
        uncertainty = _finite(radius, "domain radius")
        if uncertainty < 0:
            raise FieldIntelligenceError("INVALID_DOMAIN", "domain radius cannot be negative")
        return not (
            self.lower is not None and number - uncertainty < self.lower
            or self.upper is not None and number + uncertainty > self.upper
        )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "constant": self.constant,
            "frame": self.frame,
            "kind": self.kind,
            "lower": self.lower,
            "unit": self.unit,
            "upper": self.upper,
            "variable_id": self.variable_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> VariableSpec:
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class Guard:
    field: str
    operator: str
    value: Any = None

    def __post_init__(self) -> None:
        _identifier(self.field, "guard field")
        if self.operator not in {"eq", "ne", "in", "range", "exists"}:
            raise FieldIntelligenceError("INVALID_GUARD", "guard operator is unsupported")
        object.__setattr__(self, "value", _json_value(self.value, "guard value"))
        if self.operator == "in" and not isinstance(self.value, tuple):
            raise FieldIntelligenceError("INVALID_GUARD", "in guard requires a list")
        if self.operator == "range":
            if (
                not isinstance(self.value, tuple)
                or len(self.value) != 2
                or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in self.value)
            ):
                raise FieldIntelligenceError("INVALID_GUARD", "range guard requires [lower, upper]")
            lower, upper = map(float, self.value)
            if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
                raise FieldIntelligenceError("INVALID_GUARD", "range guard bounds are invalid")

    def matches(self, context: Mapping[str, Any]) -> bool:
        present = self.field in context
        if self.operator == "exists":
            return present is bool(self.value)
        if not present:
            return False
        actual = context[self.field]
        if self.operator == "eq":
            return actual == self.value
        if self.operator == "ne":
            return actual != self.value
        if self.operator == "in":
            return actual in self.value
        if self.operator == "range":
            return (
                not isinstance(actual, bool)
                and isinstance(actual, (int, float))
                and self.value[0] <= float(actual) <= self.value[1]
            )
        raise AssertionError("validated guard operator")

    def as_dict(self) -> Mapping[str, Any]:
        return {"field": self.field, "operator": self.operator, "value": _json_plain(self.value)}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Guard:
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class SupportContribution:
    event_id: str
    source_revision_id: str
    values: tuple[float, ...]
    weight: float
    logical_tick: int
    epistemic_type: str
    context_sha256: str
    derivation_roots: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(self.values))
        object.__setattr__(self, "derivation_roots", tuple(self.derivation_roots))
        _digest(self.event_id, "event_id")
        _digest(self.source_revision_id, "source_revision_id")
        if not self.values:
            raise FieldIntelligenceError("INVALID_SUPPORT", "contribution vector cannot be empty")
        for index, value in enumerate(self.values):
            _finite(value, f"contribution value {index}")
        _finite(self.weight, "contribution weight", positive=True)
        if isinstance(self.logical_tick, bool) or not isinstance(self.logical_tick, int) or self.logical_tick < 1:
            raise FieldIntelligenceError("INVALID_SUPPORT", "logical tick must be positive")
        if self.epistemic_type not in {"observed", "asserted", "derived"}:
            raise FieldIntelligenceError(
                "INVALID_SUPPORT", "only observed, asserted, or derived evidence can teach a chart"
            )
        _digest(self.context_sha256, "context_sha256")
        for root in self.derivation_roots:
            _digest(root, "derivation root")
        if self.epistemic_type == "derived" and not self.derivation_roots:
            raise FieldIntelligenceError(
                "INVALID_SUPPORT", "derived support must retain its premise roots"
            )

    def effective_weight(self, at_tick: int, half_life: float | None) -> float:
        if half_life is None:
            return self.weight
        age = max(0, at_tick - self.logical_tick)
        return self.weight * math.exp2(-age / half_life)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "context_sha256": self.context_sha256,
            "derivation_roots": list(self.derivation_roots),
            "epistemic_type": self.epistemic_type,
            "event_id": self.event_id,
            "logical_tick": self.logical_tick,
            "source_revision_id": self.source_revision_id,
            "values": list(self.values),
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SupportContribution:
        row = dict(value)
        row["values"] = tuple(row["values"])
        row["derivation_roots"] = tuple(row.get("derivation_roots", ()))
        return cls(**row)


@dataclass(frozen=True, slots=True)
class RelationChart:
    chart_id: str
    version: int
    scope: tuple[str, ...]
    _numeric_field: Tensor = field(repr=False)
    ridge: float
    observation_norm_bound: float
    prior_mass: float = 1.0
    factor_weight: float = 1.0
    learning_mode: str = "stationary"
    recency_half_life: float | None = None
    guards: tuple[Guard, ...] = ()
    mode_group: str | None = None
    mode: str | None = None
    representation_id: str = "raw"
    dependencies: tuple[str, ...] = ()
    contributions: tuple[SupportContribution, ...] = ()
    status: str = "active"

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope", tuple(self.scope))
        object.__setattr__(self, "guards", tuple(self.guards))
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "contributions", tuple(self.contributions))
        if not isinstance(self._numeric_field, Tensor):
            raise FieldIntelligenceError(
                "INVALID_CHART", "numeric field must be a tensor"
            )
        object.__setattr__(
            self,
            "_numeric_field",
            self._numeric_field.detach().clone(memory_format=torch.contiguous_format),
        )
        _identifier(self.chart_id, "chart_id")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise FieldIntelligenceError("INVALID_CHART", "chart version must be positive")
        if not self.scope or len(set(self.scope)) != len(self.scope):
            raise FieldIntelligenceError("INVALID_CHART", "chart scope must be nonempty and unique")
        for variable_id in self.scope:
            _identifier(variable_id, "chart variable")
        ridge = _finite(self.ridge, "chart ridge", positive=True)
        norm_bound = _finite(
            self.observation_norm_bound, "chart observation norm bound", positive=True
        )
        _finite(self.prior_mass, "chart prior mass", positive=True)
        _finite(self.factor_weight, "chart factor weight", positive=True)
        if self.learning_mode not in LEARNING_MODES:
            raise FieldIntelligenceError("INVALID_CHART", "chart learning mode is unsupported")
        if self.learning_mode == "contextual":
            if self.recency_half_life is None:
                raise FieldIntelligenceError(
                    "INVALID_CHART", "contextual chart requires a recency half-life"
                )
            _finite(self.recency_half_life, "recency half-life", positive=True)
        elif self.recency_half_life is not None:
            raise FieldIntelligenceError(
                "INVALID_CHART", "only contextual charts may carry recency decay"
            )
        if (self.mode_group is None) != (self.mode is None):
            raise FieldIntelligenceError(
                "INVALID_CHART", "mode group and mode identity must be supplied together"
            )
        if self.mode_group is not None:
            _identifier(self.mode_group, "mode_group")
            _identifier(self.mode, "mode")
        _identifier(self.representation_id, "representation_id")
        for dependency in self.dependencies:
            _identifier(dependency, "chart dependency")
        if self.status not in CHART_STATUSES:
            raise FieldIntelligenceError("INVALID_CHART", "chart status is unsupported")
        engine = VariationalField(
            dimension=len(self.scope),
            scopes=(tuple(range(len(self.scope))),),
            ridge=ridge,
            observation_norm_bound=norm_bound,
        )
        try:
            engine.validate(self._numeric_field)
            workspace = engine.workspace(self._numeric_field)
        except ValueError as exc:
            raise FieldIntelligenceError("INVALID_CHART", str(exc)) from exc
        if bool(torch.count_nonzero(workspace)):
            raise FieldIntelligenceError(
                "INVALID_CHART", "canonical chart pages cannot retain provisional workspace"
            )
        seen: set[str] = set()
        for contribution in self.contributions:
            if len(contribution.values) != len(self.scope):
                raise FieldIntelligenceError(
                    "INVALID_CHART", "contribution width does not match chart scope"
                )
            if contribution.event_id in seen:
                raise FieldIntelligenceError(
                    "INVALID_CHART", "chart repeats an evidence contribution"
                )
            seen.add(contribution.event_id)

    @classmethod
    def empty(
        cls,
        *,
        chart_id: str,
        scope: Sequence[str],
        ridge: float = 1e-4,
        observation_norm_bound: float = 4.0,
        prior_mass: float = 1.0,
        factor_weight: float = 1.0,
        learning_mode: str = "stationary",
        recency_half_life: float | None = None,
        guards: Sequence[Guard] = (),
        mode_group: str | None = None,
        mode: str | None = None,
        representation_id: str = "raw",
        dependencies: Sequence[str] = (),
    ) -> RelationChart:
        scope_tuple = tuple(scope)
        engine = VariationalField(
            dimension=len(scope_tuple),
            scopes=(tuple(range(len(scope_tuple))),),
            ridge=ridge,
            observation_norm_bound=observation_norm_bound,
        )
        return cls(
            chart_id=chart_id,
            version=1,
            scope=scope_tuple,
            _numeric_field=engine.initial_state(),
            ridge=ridge,
            observation_norm_bound=observation_norm_bound,
            prior_mass=prior_mass,
            factor_weight=factor_weight,
            learning_mode=learning_mode,
            recency_half_life=recency_half_life,
            guards=tuple(guards),
            mode_group=mode_group,
            mode=mode,
            representation_id=representation_id,
            dependencies=tuple(dependencies),
        )

    @property
    def numeric_field(self) -> Tensor:
        """Return a detached copy; adaptive tensor storage remains field-owned."""

        return self._numeric_field.clone()

    @property
    def engine(self) -> VariationalField:
        return VariationalField(
            dimension=len(self.scope),
            scopes=(tuple(range(len(self.scope))),),
            ridge=self.ridge,
            observation_norm_bound=self.observation_norm_bound,
        )

    def matches(self, context: Mapping[str, Any]) -> bool:
        return self.status == "active" and all(guard.matches(context) for guard in self.guards)

    def observed_mass(self, at_tick: int) -> float:
        return sum(
            row.effective_weight(at_tick, self.recency_half_life)
            for row in self.contributions
        )

    def active_source_revisions(self) -> frozenset[str]:
        return frozenset(row.source_revision_id for row in self.contributions)

    def covariance(self) -> Tensor:
        return self.engine.covariance(self._numeric_field, 0).clone()

    def precision(self) -> Tensor:
        covariance = self.covariance()
        return torch.cholesky_inverse(torch.linalg.cholesky(covariance))

    def rebuild(self, *, at_tick: int, contributions: Sequence[SupportContribution]) -> RelationChart:
        ordered = tuple(sorted(contributions, key=lambda row: (row.logical_tick, row.event_id)))
        field = self.engine.initial_state()
        mass = self.prior_mass
        for row in ordered:
            weight = row.effective_weight(at_tick, self.recency_half_life)
            if weight <= torch.finfo(torch.float64).tiny:
                continue
            exposure = math.log1p(weight / mass)
            field = self.engine.observe(field, 0, row.values, exposure=exposure)
            field = self.engine.clamp(field, range(len(self.scope)), [0.0] * len(self.scope))
            mass += weight
        return replace(self, _numeric_field=field, contributions=ordered, version=self.version + 1)

    def admit(self, contribution: SupportContribution, *, at_tick: int) -> RelationChart:
        existing = next(
            (row for row in self.contributions if row.event_id == contribution.event_id), None
        )
        if existing is not None:
            if existing != contribution:
                raise FieldIntelligenceError(
                    "EVIDENCE_IDENTITY_CONFLICT",
                    "event identity is already attached with different chart evidence",
                    details={"chart_id": self.chart_id, "event_id": contribution.event_id},
                )
            return self
        if len(contribution.values) != len(self.scope):
            raise FieldIntelligenceError(
                "PARTIAL_OBSERVATION",
                "a chart can learn only when every local coordinate was observed",
                details={"chart_id": self.chart_id, "scope": list(self.scope)},
            )
        norm = math.sqrt(sum(value * value for value in contribution.values))
        if norm > self.observation_norm_bound:
            raise FieldIntelligenceError(
                "OBSERVATION_OUT_OF_DOMAIN",
                "local observation exceeds the chart norm bound",
                details={"chart_id": self.chart_id, "norm": norm},
            )
        ordered_after_existing = not self.contributions or (
            contribution.logical_tick,
            contribution.event_id,
        ) > (
            self.contributions[-1].logical_tick,
            self.contributions[-1].event_id,
        )
        if self.recency_half_life is None and ordered_after_existing:
            mass = self.prior_mass + sum(row.weight for row in self.contributions)
            exposure = math.log1p(contribution.weight / mass)
            field = self.engine.observe(
                self._numeric_field,
                0,
                contribution.values,
                exposure=exposure,
            )
            field = self.engine.clamp(
                field, range(len(self.scope)), [0.0] * len(self.scope)
            )
            return replace(
                self,
                _numeric_field=field,
                contributions=(*self.contributions, contribution),
                version=self.version + 1,
            )
        return self.rebuild(
            at_tick=at_tick,
            contributions=(*self.contributions, contribution),
        )

    def remove_evidence(
        self,
        source_revision_ids: frozenset[str],
        event_ids: frozenset[str],
        *,
        at_tick: int,
    ) -> RelationChart:
        retained = tuple(
            row
            for row in self.contributions
            if row.source_revision_id not in source_revision_ids
            and row.event_id not in event_ids
        )
        if retained == self.contributions:
            return self
        return self.rebuild(at_tick=at_tick, contributions=retained)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "chart_id": self.chart_id,
            "contributions": [row.as_dict() for row in self.contributions],
            "dependencies": list(self.dependencies),
            "factor_weight": self.factor_weight,
            "guards": [guard.as_dict() for guard in self.guards],
            "learning_mode": self.learning_mode,
            "mode": self.mode,
            "mode_group": self.mode_group,
            "numeric_field": _tensor_payload(self._numeric_field),
            "observation_norm_bound": self.observation_norm_bound,
            "prior_mass": self.prior_mass,
            "recency_half_life": self.recency_half_life,
            "representation_id": self.representation_id,
            "ridge": self.ridge,
            "scope": list(self.scope),
            "status": self.status,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> RelationChart:
        row = dict(value)
        row["scope"] = tuple(row["scope"])
        row["_numeric_field"] = _tensor_from_payload(row.pop("numeric_field"))
        row["guards"] = tuple(Guard.from_dict(item) for item in row["guards"])
        row["dependencies"] = tuple(row["dependencies"])
        row["contributions"] = tuple(
            SupportContribution.from_dict(item) for item in row["contributions"]
        )
        return cls(**row)


@dataclass(frozen=True, slots=True)
class PrimitiveStep:
    operation: str
    output: str
    inputs: tuple[str, ...] = ()
    literal: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", tuple(self.inputs))
        if self.operation not in {
            "identity",
            "constant",
            "add",
            "subtract",
            "multiply",
            "divide",
            "negate",
            "absolute",
            "equal",
            "less_equal",
            "vector",
            "convert",
            "concat",
        }:
            raise FieldIntelligenceError(
                "INVALID_PROGRAM", f"unsupported primitive: {self.operation}"
            )
        _identifier(self.output, "program output")
        for item in self.inputs:
            _identifier(item, "program input")
        object.__setattr__(self, "literal", _json_value(self.literal, "program literal"))
        arity = {
            "identity": 1,
            "constant": 0,
            "add": 2,
            "subtract": 2,
            "multiply": 2,
            "divide": 2,
            "negate": 1,
            "absolute": 1,
            "equal": 2,
            "less_equal": 2,
            "convert": 1,
        }.get(self.operation)
        if arity is not None and len(self.inputs) != arity:
            raise FieldIntelligenceError(
                "INVALID_PROGRAM", f"{self.operation} requires {arity} inputs"
            )
        if self.operation == "convert":
            _finite(self.literal, "conversion scale")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "inputs": list(self.inputs),
            "literal": _json_plain(self.literal),
            "operation": self.operation,
            "output": self.output,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PrimitiveStep:
        row = dict(value)
        row["inputs"] = tuple(row["inputs"])
        return cls(**row)


@dataclass(frozen=True, slots=True)
class AssessmentRecord:
    assessment_id: str
    prediction: Any
    outcome: Any
    normalized_loss: float
    event_id: str
    sequence: int

    def __post_init__(self) -> None:
        _digest(self.assessment_id, "assessment_id")
        _digest(self.event_id, "assessment event_id")
        object.__setattr__(self, "prediction", _json_value(self.prediction, "prediction"))
        object.__setattr__(self, "outcome", _json_value(self.outcome, "outcome"))
        loss = _finite(self.normalized_loss, "normalized loss")
        if not 0 <= loss <= 1:
            raise FieldIntelligenceError("INVALID_ASSESSMENT", "normalized loss must be in [0, 1]")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise FieldIntelligenceError("INVALID_ASSESSMENT", "assessment sequence must be positive")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "event_id": self.event_id,
            "normalized_loss": self.normalized_loss,
            "outcome": _json_plain(self.outcome),
            "prediction": _json_plain(self.prediction),
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AssessmentRecord:
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class FieldProgram:
    program_id: str
    version: int
    roles: tuple[str, ...]
    steps: tuple[PrimitiveStep, ...]
    outputs: tuple[str, ...]
    guards: tuple[Guard, ...] = ()
    support_event_ids: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    known_exceptions: tuple[str, ...] = ()
    assessments: tuple[AssessmentRecord, ...] = ()
    prefix_code_bits: int = 1
    status: str = "candidate"

    def __post_init__(self) -> None:
        for name in (
            "roles",
            "steps",
            "outputs",
            "guards",
            "support_event_ids",
            "dependencies",
            "known_exceptions",
            "assessments",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        _identifier(self.program_id, "program_id")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise FieldIntelligenceError("INVALID_PROGRAM", "program version must be positive")
        if len(set(self.roles)) != len(self.roles):
            raise FieldIntelligenceError("INVALID_PROGRAM", "program roles must be unique")
        for role in self.roles:
            _identifier(role, "program role")
        if not self.steps or not self.outputs:
            raise FieldIntelligenceError("INVALID_PROGRAM", "program requires steps and outputs")
        available = set(self.roles)
        for step in self.steps:
            if any(item not in available for item in step.inputs):
                raise FieldIntelligenceError(
                    "INVALID_PROGRAM",
                    "program step reads a value before it is bound",
                    details={"program_id": self.program_id, "step": step.as_dict()},
                )
            if step.output in available:
                raise FieldIntelligenceError(
                    "INVALID_PROGRAM", "program outputs cannot overwrite an existing binding"
                )
            available.add(step.output)
        if any(output not in available for output in self.outputs):
            raise FieldIntelligenceError("INVALID_PROGRAM", "declared program output is unbound")
        for digest in (*self.support_event_ids,):
            _digest(digest, "program support event")
        for dependency in self.dependencies:
            _identifier(dependency, "program dependency")
        for exception in self.known_exceptions:
            _digest(exception, "program exception event")
        if isinstance(self.prefix_code_bits, bool) or not isinstance(self.prefix_code_bits, int) or self.prefix_code_bits < 1:
            raise FieldIntelligenceError("INVALID_PROGRAM", "prefix-code length must be positive")
        if self.status not in PROGRAM_STATUSES:
            raise FieldIntelligenceError("INVALID_PROGRAM", "program status is unsupported")

    def matches(self, context: Mapping[str, Any]) -> bool:
        return self.status == "promoted" and all(guard.matches(context) for guard in self.guards)

    def execute(self, bindings: Mapping[str, Any], *, max_steps: int = 256) -> Mapping[str, Any]:
        if len(self.steps) > max_steps:
            raise FieldIntelligenceError("PROGRAM_BUDGET", "program exceeds its execution budget")
        if set(bindings) != set(self.roles):
            raise FieldIntelligenceError(
                "PROGRAM_BINDING",
                "program bindings must cover its roles exactly",
                details={"expected": list(self.roles), "actual": sorted(bindings)},
            )
        values: dict[str, Any] = {name: _json_value(bindings[name], name) for name in self.roles}
        for step in self.steps:
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
                        raise FieldIntelligenceError("PROGRAM_DOMAIN", "division by zero")
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
                elif step.operation == "concat":
                    result = "".join(str(item) for item in args)
                else:
                    raise AssertionError("validated primitive")
            except FieldIntelligenceError:
                raise
            except (TypeError, ValueError, OverflowError) as exc:
                raise FieldIntelligenceError(
                    "PROGRAM_DOMAIN", f"primitive {step.operation} rejected its inputs"
                ) from exc
            values[step.output] = _json_value(result, step.output)
        return {name: values[name] for name in self.outputs}

    @property
    def prequential_loss(self) -> float:
        return sum(row.normalized_loss for row in self.assessments)

    def selection_score(self, *, bit_penalty: float) -> float:
        penalty = _finite(bit_penalty, "bit penalty")
        if penalty < 0:
            raise FieldIntelligenceError("INVALID_SELECTION", "bit penalty cannot be negative")
        return self.prequential_loss + penalty * self.prefix_code_bits

    def record_assessment(self, record: AssessmentRecord) -> FieldProgram:
        existing = next(
            (row for row in self.assessments if row.assessment_id == record.assessment_id), None
        )
        if existing is not None:
            if existing != record:
                raise FieldIntelligenceError(
                    "ASSESSMENT_CONFLICT", "assessment identity was reused with different data"
                )
            return self
        return replace(self, assessments=(*self.assessments, record), version=self.version + 1)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "assessments": [row.as_dict() for row in self.assessments],
            "dependencies": list(self.dependencies),
            "guards": [row.as_dict() for row in self.guards],
            "known_exceptions": list(self.known_exceptions),
            "outputs": list(self.outputs),
            "prefix_code_bits": self.prefix_code_bits,
            "program_id": self.program_id,
            "roles": list(self.roles),
            "status": self.status,
            "steps": [row.as_dict() for row in self.steps],
            "support_event_ids": list(self.support_event_ids),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FieldProgram:
        row = dict(value)
        for name in ("roles", "outputs", "support_event_ids", "dependencies", "known_exceptions"):
            row[name] = tuple(row[name])
        row["steps"] = tuple(PrimitiveStep.from_dict(item) for item in row["steps"])
        row["guards"] = tuple(Guard.from_dict(item) for item in row["guards"])
        row["assessments"] = tuple(
            AssessmentRecord.from_dict(item) for item in row["assessments"]
        )
        return cls(**row)


@dataclass(frozen=True, slots=True)
class LanguageConstruction:
    construction_id: str
    version: int
    pattern: tuple[str, ...]
    roles: tuple[str, ...]
    semantic_program_id: str
    support_event_ids: tuple[str, ...]
    assessments: tuple[AssessmentRecord, ...] = ()
    guards: tuple[Guard, ...] = ()
    status: str = "candidate"

    def __post_init__(self) -> None:
        for name in (
            "pattern",
            "roles",
            "support_event_ids",
            "assessments",
            "guards",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        _identifier(self.construction_id, "construction_id")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise FieldIntelligenceError(
                "INVALID_CONSTRUCTION", "construction version must be positive"
            )
        if not self.pattern or not self.roles or len(set(self.roles)) != len(self.roles):
            raise FieldIntelligenceError(
                "INVALID_CONSTRUCTION", "construction pattern and unique roles are required"
            )
        for token in self.pattern:
            _identifier(token, "construction token")
        for role in self.roles:
            _identifier(role, "construction role")
        slots = tuple(token[1:-1] for token in self.pattern if token.startswith("{") and token.endswith("}"))
        if set(slots) != set(self.roles) or len(slots) != len(self.roles):
            raise FieldIntelligenceError(
                "INVALID_CONSTRUCTION", "construction slots must bind every role exactly once"
            )
        _identifier(self.semantic_program_id, "semantic_program_id")
        for event_id in self.support_event_ids:
            _digest(event_id, "construction support")
        if self.status not in PROGRAM_STATUSES:
            raise FieldIntelligenceError(
                "INVALID_CONSTRUCTION", "construction status is unsupported"
            )

    def matches(self, context: Mapping[str, Any]) -> bool:
        return self.status == "promoted" and all(guard.matches(context) for guard in self.guards)

    def render(self, bindings: Mapping[str, Any]) -> str:
        if set(bindings) != set(self.roles):
            raise FieldIntelligenceError(
                "CONSTRUCTION_BINDING", "construction bindings must cover every role exactly"
            )
        tokens = [
            str(bindings[token[1:-1]])
            if token.startswith("{") and token.endswith("}")
            else token
            for token in self.pattern
        ]
        text = " ".join(tokens)
        for punctuation in (" .", " ,", " ?", " !", " :", " ;"):
            text = text.replace(punctuation, punctuation[1:])
        return text

    def interpret(self, text: str) -> Mapping[str, str] | None:
        if not isinstance(text, str) or not text:
            return None
        words = _tokenize(text)
        if len(words) != len(self.pattern):
            return None
        bindings: dict[str, str] = {}
        for expected, actual in zip(self.pattern, words):
            if expected.startswith("{") and expected.endswith("}"):
                bindings[expected[1:-1]] = actual
            elif expected != actual:
                return None
        return bindings

    def record_assessment(self, record: AssessmentRecord) -> LanguageConstruction:
        existing = next(
            (row for row in self.assessments if row.assessment_id == record.assessment_id), None
        )
        if existing is not None:
            if existing != record:
                raise FieldIntelligenceError(
                    "ASSESSMENT_CONFLICT", "construction assessment identity conflicts"
                )
            return self
        return replace(self, assessments=(*self.assessments, record), version=self.version + 1)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "assessments": [row.as_dict() for row in self.assessments],
            "construction_id": self.construction_id,
            "guards": [row.as_dict() for row in self.guards],
            "pattern": list(self.pattern),
            "roles": list(self.roles),
            "semantic_program_id": self.semantic_program_id,
            "status": self.status,
            "support_event_ids": list(self.support_event_ids),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> LanguageConstruction:
        row = dict(value)
        for name in ("pattern", "roles", "support_event_ids"):
            row[name] = tuple(row[name])
        row["guards"] = tuple(Guard.from_dict(item) for item in row["guards"])
        row["assessments"] = tuple(
            AssessmentRecord.from_dict(item) for item in row["assessments"]
        )
        return cls(**row)


def _tokenize(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    current: list[str] = []
    for character in text.strip():
        if character.isspace():
            if current:
                tokens.append("".join(current))
                current.clear()
        elif character in ".,?!:;":
            if current:
                tokens.append("".join(current))
                current.clear()
            tokens.append(character)
        else:
            current.append(character)
    if current:
        tokens.append("".join(current))
    return tuple(tokens)


@dataclass(frozen=True, slots=True)
class ExactReduction:
    macro_id: str
    version: int
    boundary: tuple[str, ...]
    interior: tuple[str, ...]
    hessian: tuple[tuple[float, ...], ...]
    linear: tuple[float, ...]
    constant: float
    parent_chart_versions: tuple[tuple[str, int], ...]
    guards: tuple[Guard, ...]
    support_event_ids: tuple[str, ...]
    expansion_variables: tuple[str, ...]
    exact: bool = True
    error_bound: float = 0.0
    status: str = "promoted"

    def __post_init__(self) -> None:
        for name in (
            "boundary",
            "interior",
            "linear",
            "parent_chart_versions",
            "guards",
            "support_event_ids",
            "expansion_variables",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(
            self, "hessian", tuple(tuple(row) for row in self.hessian)
        )
        _identifier(self.macro_id, "macro_id")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise FieldIntelligenceError("INVALID_MACRO", "macro version must be positive")
        if (
            not self.boundary
            or len(set(self.boundary)) != len(self.boundary)
            or len(set(self.interior)) != len(self.interior)
            or set(self.boundary).intersection(self.interior)
            or len(set(self.expansion_variables)) != len(self.expansion_variables)
        ):
            raise FieldIntelligenceError(
                "INVALID_MACRO",
                "macro variables must be unique with a nonempty boundary disjoint from its interior",
            )
        size = len(self.boundary)
        if len(self.hessian) != size or any(len(row) != size for row in self.hessian):
            raise FieldIntelligenceError("INVALID_MACRO", "macro Hessian shape is invalid")
        if len(self.linear) != size:
            raise FieldIntelligenceError("INVALID_MACRO", "macro linear term shape is invalid")
        values = [item for row in self.hessian for item in row]
        values.extend(self.linear)
        values.extend((self.constant, self.error_bound))
        for index, value in enumerate(values):
            _finite(value, f"macro numeric value {index}")
        if self.error_bound < 0:
            raise FieldIntelligenceError("INVALID_MACRO", "macro error bound cannot be negative")
        for chart_id, version in self.parent_chart_versions:
            _identifier(chart_id, "macro parent chart")
            if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                raise FieldIntelligenceError("INVALID_MACRO", "macro parent version is invalid")
        for event_id in self.support_event_ids:
            _digest(event_id, "macro support event")
        if self.status not in PROGRAM_STATUSES:
            raise FieldIntelligenceError("INVALID_MACRO", "macro status is unsupported")

    def valid_for(self, state: AtlasState, context: Mapping[str, Any]) -> bool:
        if self.status != "promoted" or not all(guard.matches(context) for guard in self.guards):
            return False
        versions = {chart.chart_id: chart.version for chart in state.charts}
        return all(versions.get(chart_id) == version for chart_id, version in self.parent_chart_versions)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "boundary": list(self.boundary),
            "constant": self.constant,
            "error_bound": self.error_bound,
            "exact": self.exact,
            "expansion_variables": list(self.expansion_variables),
            "guards": [row.as_dict() for row in self.guards],
            "hessian": [list(row) for row in self.hessian],
            "interior": list(self.interior),
            "linear": list(self.linear),
            "macro_id": self.macro_id,
            "parent_chart_versions": [list(row) for row in self.parent_chart_versions],
            "status": self.status,
            "support_event_ids": list(self.support_event_ids),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ExactReduction:
        row = dict(value)
        for name in ("boundary", "interior", "linear", "expansion_variables", "support_event_ids"):
            row[name] = tuple(row[name])
        row["hessian"] = tuple(tuple(item) for item in row["hessian"])
        row["parent_chart_versions"] = tuple(
            (item[0], int(item[1])) for item in row["parent_chart_versions"]
        )
        row["guards"] = tuple(Guard.from_dict(item) for item in row["guards"])
        return cls(**row)


@dataclass(frozen=True, slots=True)
class PredictionRecord:
    prediction_id: str
    field_generation: int
    branch_id: str
    query: Mapping[str, Any]
    predicted: Mapping[str, Any]
    dependency_versions: tuple[tuple[str, int], ...]
    source_revision_ids: tuple[str, ...]
    goal_id: str | None
    authority_generation: int
    operation_id: str | None = None
    status: str = "predicted"
    actual: Mapping[str, Any] | None = None
    attribution_candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dependency_versions",
            tuple((item[0], int(item[1])) for item in self.dependency_versions),
        )
        object.__setattr__(
            self, "source_revision_ids", tuple(self.source_revision_ids)
        )
        object.__setattr__(
            self, "attribution_candidates", tuple(self.attribution_candidates)
        )
        _digest(self.prediction_id, "prediction_id")
        if isinstance(self.field_generation, bool) or not isinstance(self.field_generation, int) or self.field_generation < 0:
            raise FieldIntelligenceError("INVALID_PREDICTION", "field generation is invalid")
        _identifier(self.branch_id, "branch_id")
        object.__setattr__(self, "query", _json_value(dict(self.query), "prediction query"))
        object.__setattr__(self, "predicted", _json_value(dict(self.predicted), "prediction value"))
        for chart_id, version in self.dependency_versions:
            _identifier(chart_id, "prediction chart dependency")
            if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                raise FieldIntelligenceError(
                    "INVALID_PREDICTION", "prediction dependency version is invalid"
                )
        for revision in self.source_revision_ids:
            _digest(revision, "prediction source revision")
        if self.goal_id is not None:
            _identifier(self.goal_id, "goal_id")
        if isinstance(self.authority_generation, bool) or not isinstance(self.authority_generation, int) or self.authority_generation < 0:
            raise FieldIntelligenceError("INVALID_PREDICTION", "authority generation is invalid")
        if self.operation_id is not None:
            _identifier(self.operation_id, "operation_id")
        if self.status not in {"predicted", "proposed", "pending", "acknowledged", "invalidated"}:
            raise FieldIntelligenceError("INVALID_PREDICTION", "prediction status is unsupported")
        if self.actual is not None:
            object.__setattr__(self, "actual", _json_value(dict(self.actual), "actual outcome"))
        for candidate in self.attribution_candidates:
            _identifier(candidate, "attribution candidate")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "actual": None if self.actual is None else _json_plain(self.actual),
            "attribution_candidates": list(self.attribution_candidates),
            "authority_generation": self.authority_generation,
            "branch_id": self.branch_id,
            "dependency_versions": [list(row) for row in self.dependency_versions],
            "field_generation": self.field_generation,
            "goal_id": self.goal_id,
            "operation_id": self.operation_id,
            "predicted": _json_plain(self.predicted),
            "prediction_id": self.prediction_id,
            "query": _json_plain(self.query),
            "source_revision_ids": list(self.source_revision_ids),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PredictionRecord:
        row = dict(value)
        row["dependency_versions"] = tuple(
            (item[0], int(item[1])) for item in row["dependency_versions"]
        )
        row["source_revision_ids"] = tuple(row["source_revision_ids"])
        row["attribution_candidates"] = tuple(row["attribution_candidates"])
        return cls(**row)


@dataclass(frozen=True, slots=True)
class PlanSegment:
    segment_id: str
    level: str
    kind: str
    payload: Mapping[str, Any]
    dependency_versions: tuple[tuple[str, int], ...]
    guards: tuple[Guard, ...] = ()
    status: str = "open"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dependency_versions",
            tuple((item[0], int(item[1])) for item in self.dependency_versions),
        )
        object.__setattr__(self, "guards", tuple(self.guards))
        _identifier(self.segment_id, "segment_id")
        if self.level not in {"strategic", "tactical", "immediate"}:
            raise FieldIntelligenceError("INVALID_PLAN", "plan segment level is unsupported")
        if self.kind not in {"macro", "action", "inquiry", "constraint", "calculation"}:
            raise FieldIntelligenceError("INVALID_PLAN", "plan segment kind is unsupported")
        object.__setattr__(self, "payload", _json_value(dict(self.payload), "plan payload"))
        if self.status not in {"open", "ready", "completed", "invalidated", "unresolved"}:
            raise FieldIntelligenceError("INVALID_PLAN", "plan segment status is unsupported")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "dependency_versions": [list(row) for row in self.dependency_versions],
            "guards": [row.as_dict() for row in self.guards],
            "kind": self.kind,
            "level": self.level,
            "payload": _json_plain(self.payload),
            "segment_id": self.segment_id,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PlanSegment:
        row = dict(value)
        row["dependency_versions"] = tuple(
            (item[0], int(item[1])) for item in row["dependency_versions"]
        )
        row["guards"] = tuple(Guard.from_dict(item) for item in row["guards"])
        return cls(**row)


@dataclass(frozen=True, slots=True)
class PlanRecord:
    plan_id: str
    goal_id: str
    goal: Mapping[str, Any]
    assumptions: Mapping[str, Any]
    segments: tuple[PlanSegment, ...]
    source_revision_ids: tuple[str, ...]
    authority_generation: int
    status: str = "open"

    def __post_init__(self) -> None:
        object.__setattr__(self, "segments", tuple(self.segments))
        object.__setattr__(
            self, "source_revision_ids", tuple(self.source_revision_ids)
        )
        _digest(self.plan_id, "plan_id")
        _identifier(self.goal_id, "goal_id")
        object.__setattr__(self, "goal", _json_value(dict(self.goal), "plan goal"))
        object.__setattr__(self, "assumptions", _json_value(dict(self.assumptions), "plan assumptions"))
        for revision in self.source_revision_ids:
            _digest(revision, "plan source revision")
        if isinstance(self.authority_generation, bool) or not isinstance(self.authority_generation, int) or self.authority_generation < 0:
            raise FieldIntelligenceError("INVALID_PLAN", "plan authority generation is invalid")
        if self.status not in {"open", "ready", "completed", "invalidated", "unresolved"}:
            raise FieldIntelligenceError("INVALID_PLAN", "plan status is unsupported")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "assumptions": _json_plain(self.assumptions),
            "authority_generation": self.authority_generation,
            "goal": _json_plain(self.goal),
            "goal_id": self.goal_id,
            "plan_id": self.plan_id,
            "segments": [row.as_dict() for row in self.segments],
            "source_revision_ids": list(self.source_revision_ids),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PlanRecord:
        row = dict(value)
        row["segments"] = tuple(PlanSegment.from_dict(item) for item in row["segments"])
        row["source_revision_ids"] = tuple(row["source_revision_ids"])
        return cls(**row)


@dataclass(frozen=True, slots=True)
class ComputationRecord:
    record_id: str
    operation: str
    logical_tick: int
    inputs: Mapping[str, Any]
    outcome: str
    elapsed_ns: int
    work_units: int
    residual_before: float | None = None
    residual_after: float | None = None

    def __post_init__(self) -> None:
        _digest(self.record_id, "computation record_id")
        _identifier(self.operation, "computation operation")
        if isinstance(self.logical_tick, bool) or not isinstance(self.logical_tick, int) or self.logical_tick < 0:
            raise FieldIntelligenceError("INVALID_COMPUTATION", "computation tick is invalid")
        object.__setattr__(self, "inputs", _json_value(dict(self.inputs), "computation inputs"))
        _identifier(self.outcome, "computation outcome")
        for name in ("elapsed_ns", "work_units"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise FieldIntelligenceError("INVALID_COMPUTATION", f"{name} is invalid")
        for name in ("residual_before", "residual_after"):
            value = getattr(self, name)
            if value is not None:
                _finite(value, name)

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "elapsed_ns": self.elapsed_ns,
            "inputs": _json_plain(self.inputs),
            "logical_tick": self.logical_tick,
            "operation": self.operation,
            "outcome": self.outcome,
            "record_id": self.record_id,
            "residual_after": self.residual_after,
            "residual_before": self.residual_before,
            "work_units": self.work_units,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ComputationRecord:
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class FieldTransceiver:
    """A derived computation and its provisional activity, owned by the field."""

    transceiver_id: str
    parent_chart_versions: tuple[tuple[str, int], ...]
    source_revision_ids: tuple[str, ...]
    context: Mapping[str, Any]
    input_ids: tuple[str, ...]
    output_ids: tuple[str, ...]
    observed: Mapping[str, float]
    kernel: Mapping[str, Any] | None
    working_state: Mapping[str, Any] | None
    status: str = "active"
    reason: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.transceiver_id, "transceiver_id")
        for name in ("input_ids", "output_ids"):
            ids = tuple(getattr(self, name))
            if not ids or len(ids) != len(set(ids)):
                raise FieldIntelligenceError("INVALID_TRANSCEIVER", f"{name} must be nonempty and unique")
            for item in ids:
                _identifier(item, name)
            object.__setattr__(self, name, ids)
        if set(self.input_ids).intersection(self.output_ids):
            raise FieldIntelligenceError("INVALID_TRANSCEIVER", "receiving and transmitting ports must be distinct")
        parents = tuple((name, version) for name, version in self.parent_chart_versions)
        if not parents or len(parents) != len({name for name, _ in parents}):
            raise FieldIntelligenceError("INVALID_TRANSCEIVER", "parent charts must be nonempty and unique")
        for name, version in parents:
            _identifier(name, "transceiver parent")
            if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                raise FieldIntelligenceError("INVALID_TRANSCEIVER", "invalid parent version")
        object.__setattr__(self, "parent_chart_versions", parents)
        sources = tuple(self.source_revision_ids)
        if not sources or len(sources) != len(set(sources)):
            raise FieldIntelligenceError("INVALID_TRANSCEIVER", "source closure must be nonempty and unique")
        for source in sources:
            _digest(source, "transceiver source")
        object.__setattr__(self, "source_revision_ids", sources)
        object.__setattr__(self, "context", _json_value(dict(self.context), "transceiver context"))
        object.__setattr__(self, "observed", _json_value(
            {name: _finite(value, name) for name, value in self.observed.items()}, "transceiver observations"
        ))
        if self.status not in {"active", "stale"}:
            raise FieldIntelligenceError("INVALID_TRANSCEIVER", "invalid transceiver status")
        if self.reason is not None:
            _identifier(self.reason, "transceiver reason")
        if self.status == "stale":
            if self.kernel is not None or self.working_state is not None:
                raise FieldIntelligenceError("INVALID_TRANSCEIVER", "stale derived knowledge must be discarded")
        else:
            if not isinstance(self.kernel, Mapping) or not isinstance(self.working_state, Mapping):
                raise FieldIntelligenceError("INVALID_TRANSCEIVER", "active transceiver needs a realization")
            try:
                validate_transceiver(self.kernel, self.working_state)
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                raise FieldIntelligenceError("INVALID_TRANSCEIVER", str(exc)) from exc
            # Numeric realizations are field pages, not 64 KiB typed symbols.
            # Schema/dimension checks above and owner closure/workspace limits
            # bound them; canonicalization still rejects nonfinite payloads.
            if not isinstance(self.kernel, _FrozenDict):
                object.__setattr__(self, "kernel", _freeze_json(_json_plain(self.kernel)))
            if not isinstance(self.working_state, _FrozenDict):
                object.__setattr__(self, "working_state", _freeze_json(_json_plain(self.working_state)))

    def matches(self, context: Mapping[str, Any]) -> bool:
        return self.status == "active" and all(
            key in context and context[key] == value for key, value in self.context.items()
        )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "transceiver_id": self.transceiver_id,
            "parent_chart_versions": [list(row) for row in self.parent_chart_versions],
            "source_revision_ids": list(self.source_revision_ids),
            "context": _json_plain(self.context),
            "input_ids": list(self.input_ids),
            "output_ids": list(self.output_ids),
            "observed": _json_plain(self.observed),
            "kernel": None if self.kernel is None else _json_plain(self.kernel),
            "working_state": None if self.working_state is None else _json_plain(self.working_state),
            "status": self.status,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FieldTransceiver:
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class AtlasState:
    generation: int = 0
    logical_tick: int = 0
    revocation_generation: int = 0
    transition_epoch_floor: int = 0
    variables: tuple[VariableSpec, ...] = ()
    charts: tuple[RelationChart, ...] = ()
    programs: tuple[FieldProgram, ...] = ()
    constructions: tuple[LanguageConstruction, ...] = ()
    macros: tuple[ExactReduction, ...] = ()
    predictions: tuple[PredictionRecord, ...] = ()
    plans: tuple[PlanRecord, ...] = ()
    computation_records: tuple[ComputationRecord, ...] = ()
    transceivers: tuple[FieldTransceiver, ...] = ()
    temporal_fields: tuple[TemporalField, ...] = ()
    transition_log: tuple[Mapping[str, Any], ...] = ()
    resonant_workspace: ResonantWorkspace | None = field(default_factory=initial_workspace)
    prepared_queries: tuple[Mapping[str, Any], ...] = ()
    frozen_query_ids: frozenset[str] = frozenset()
    _encoded: bytes = field(init=False, repr=False, compare=False)
    _state_sha256: str = field(init=False, repr=False, compare=False)
    schema: str = ATLAS_SCHEMA
    arithmetic_profile: str = ARITHMETIC_PROFILE
    # Entries are (immutable owner, SHA-256 digest, canonical bytes).
    # Owners are retained directly (never a whole AtlasState), so identity
    # remains valid even if an unrelated predecessor is garbage-collected.
    _page_cache: dict[str, tuple[Any, str, bytes]] = field(
        default_factory=dict, init=True, repr=False, compare=False, kw_only=True
    )

    def __post_init__(self) -> None:
        inherited_cache = dict(self._page_cache)
        workspace = self.resonant_workspace
        if workspace is not None and not isinstance(workspace, ResonantWorkspace):
            try:
                workspace = ResonantWorkspace.from_dict(workspace)
            except Exception as exc:
                raise FieldIntelligenceError(
                    "INVALID_STATE", "resonant workspace is invalid"
                ) from exc
        object.__setattr__(self, "resonant_workspace", workspace)
        for name in (
            "variables",
            "charts",
            "programs",
            "constructions",
            "macros",
            "predictions",
            "plans",
            "computation_records",
            "transceivers",
            "temporal_fields",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if any(not isinstance(row, TemporalField) for row in self.temporal_fields):
            raise FieldIntelligenceError("INVALID_STATE", "temporal memory must be an immutable field")
        chart_index = {chart.chart_id: chart for chart in self.charts}
        retained_transceivers: list[FieldTransceiver] = []
        for transceiver in self.transceivers:
            if not isinstance(transceiver, FieldTransceiver):
                raise FieldIntelligenceError("INVALID_STATE", "transceiver must be an immutable field record")
            if transceiver.status == "active" and any(
                name not in chart_index
                or chart_index[name].version != version
                or chart_index[name].status != "active"
                for name, version in transceiver.parent_chart_versions
            ):
                transceiver = replace(
                    transceiver, status="stale", reason="parent-changed",
                    kernel=None, working_state=None, observed={},
                )
            retained_transceivers.append(transceiver)
        if any(old is not new for old, new in zip(self.transceivers, retained_transceivers)):
            object.__setattr__(self, "transceivers", tuple(retained_transceivers))
        object.__setattr__(
            self,
            "transition_log",
            tuple(_json_value(dict(row), "transition record") for row in self.transition_log),
        )
        normalized_queries: list[Mapping[str, Any]] = []
        query_ids: set[str] = set()
        for raw_query in self.prepared_queries:
            if not isinstance(raw_query, Mapping):
                raise FieldIntelligenceError("INVALID_STATE", "prepared query must be a mapping")
            query = dict(raw_query)
            unknown = set(query) - {
                "query_id", "status", "frozen", "result", "branch_workspaces",
                "branch_receipts", "reason",
            }
            if unknown:
                raise FieldIntelligenceError(
                    "INVALID_STATE", "prepared query has unknown keys",
                    details={"unknown": sorted(unknown)},
                )
            query_id = _identifier(query.get("query_id"), "prepared query_id")
            if query_id in query_ids:
                raise FieldIntelligenceError("INVALID_STATE", "prepared query identities must be unique")
            query_ids.add(query_id)
            status = query.get("status")
            if status not in {"prepared", "invalidated"}:
                raise FieldIntelligenceError("INVALID_STATE", "prepared query status is unsupported")
            if status == "prepared" and "result" not in query:
                raise FieldIntelligenceError("INVALID_STATE", "prepared query lacks result")
            if "result" in query:
                if not isinstance(query["result"], Mapping):
                    raise FieldIntelligenceError("INVALID_STATE", "prepared query result must be a mapping")
                query["result"] = _json_value(dict(query["result"]), "prepared query result")
            branches = query.get("branch_workspaces", ())
            if not isinstance(branches, (tuple, list)):
                raise FieldIntelligenceError("INVALID_STATE", "prepared branch workspaces must be a sequence")
            normalized_branches: list[Mapping[str, Any]] = []
            for record in branches:
                if not isinstance(record, Mapping) or set(record) != {
                    "workspace", "state_sha256", "page_sha256"
                }:
                    raise FieldIntelligenceError(
                        "INVALID_STATE", "prepared branch workspace record is not canonical"
                    )
                try:
                    branch_workspace = record["workspace"]
                    if not isinstance(branch_workspace, ResonantWorkspace):
                        branch_workspace = ResonantWorkspace.from_dict(branch_workspace)
                    state_digest = _digest(record["state_sha256"], "workspace state digest")
                    page_digest = _digest(record["page_sha256"], "workspace page digest")
                    if branch_workspace.state_sha256 != state_digest:
                        raise ValueError("workspace state digest mismatch")
                    if hashlib.sha256(branch_workspace.page_bytes).hexdigest() != page_digest:
                        raise ValueError("workspace page digest mismatch")
                except Exception as exc:
                    raise FieldIntelligenceError(
                        "INVALID_STATE", "prepared branch workspace is invalid"
                    ) from exc
                normalized_branches.append(
                    _FrozenDict({
                        "workspace": branch_workspace,
                        "state_sha256": state_digest,
                        "page_sha256": page_digest,
                    })
                )
            query["branch_workspaces"] = tuple(normalized_branches)
            if "branch_receipts" in query:
                query["branch_receipts"] = _json_value(query["branch_receipts"], "branch receipts")
            normalized_queries.append(_FrozenDict(query))
        valid_page_names = set(_ATLAS_PAGE_NAMES) | {
            "resonant_workspace", "resonant_workspace:field"
        }
        for name in tuple(inherited_cache):
            if name not in valid_page_names:
                inherited_cache.pop(name, None)
        object.__setattr__(self, "prepared_queries", tuple(normalized_queries))
        for name in _ATLAS_PAGE_NAMES:
            owner = getattr(self, name)
            entry = inherited_cache.get(name)
            if entry is not None and entry[0] is not owner:
                inherited_cache.pop(name, None)
        workspace_owners: list[ResonantWorkspace] = []
        if workspace is not None:
            workspace_owners.append(workspace)
        for query in self.prepared_queries:
            for branch in query.get("branch_workspaces", ()):
                workspace_owners.append(branch["workspace"])
        for name in ("resonant_workspace", "resonant_workspace:field"):
            entry = inherited_cache.get(name)
            if entry is not None and not any(entry[0] is owner for owner in workspace_owners):
                inherited_cache.pop(name, None)
        object.__setattr__(self, "frozen_query_ids", frozenset(self.frozen_query_ids))
        if self.schema != ATLAS_SCHEMA or self.arithmetic_profile != ARITHMETIC_PROFILE:
            raise FieldIntelligenceError("INCOMPATIBLE_STATE", "field atlas schema is incompatible")
        for name in ("generation", "logical_tick", "revocation_generation", "transition_epoch_floor"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise FieldIntelligenceError("INVALID_STATE", f"{name} must be nonnegative")
        if self.transition_epoch_floor > self.generation:
            raise FieldIntelligenceError("INVALID_STATE", "transition epoch floor exceeds generation")
        collections = {
            "variable": [row.variable_id for row in self.variables],
            "chart": [row.chart_id for row in self.charts],
            "program": [row.program_id for row in self.programs],
            "construction": [row.construction_id for row in self.constructions],
            "macro": [row.macro_id for row in self.macros],
            "prediction": [row.prediction_id for row in self.predictions],
            "plan": [row.plan_id for row in self.plans],
            "computation": [row.record_id for row in self.computation_records],
            "transceiver": [row.transceiver_id for row in self.transceivers],
            "temporal": [row.memory_id for row in self.temporal_fields],
        }
        for label, values in collections.items():
            if len(values) != len(set(values)):
                raise FieldIntelligenceError("INVALID_STATE", f"{label} identities must be unique")
        variable_ids = set(collections["variable"])
        if workspace is not None:
            occupied_ports: set[int] = set()
            binding_ids: set[str] = set()
            for variable_id, binding in workspace.bindings.items():
                if variable_id not in variable_ids:
                    raise FieldIntelligenceError(
                        "INVALID_STATE", "resonant binding names an unknown variable",
                        details={"variable_id": variable_id},
                    )
                if not isinstance(binding, Mapping) or set(binding) != {
                    "pool", "port", "component", "binding_id"
                }:
                    raise FieldIntelligenceError("INVALID_STATE", "resonant binding is not canonical")
                pool = binding["pool"]
                if isinstance(pool, bool) or not isinstance(pool, int) or not 0 <= pool < workspace.profile.pools:
                    raise FieldIntelligenceError("INVALID_STATE", "resonant binding pool is invalid")
                port = binding["port"]
                if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port < workspace.profile.port_count:
                    raise FieldIntelligenceError("INVALID_STATE", "resonant binding port is invalid")
                if port in occupied_ports:
                    raise FieldIntelligenceError("INVALID_STATE", "resonant bindings reuse a port")
                occupied_ports.add(port)
                _identifier(binding["component"], "binding component")
                binding_id = _identifier(binding["binding_id"], "binding_id")
                if binding_id in binding_ids:
                    raise FieldIntelligenceError("INVALID_STATE", "resonant binding identities must be unique")
                binding_ids.add(binding_id)
        for transceiver in self.transceivers:
            if not set((*transceiver.input_ids, *transceiver.output_ids)).issubset(variable_ids):
                raise FieldIntelligenceError("INVALID_STATE", "transceiver ports name unknown variables")
        for chart in self.charts:
            missing = set(chart.scope) - variable_ids
            if missing:
                raise FieldIntelligenceError(
                    "INVALID_STATE",
                    "chart scope names unknown variables",
                    details={"chart_id": chart.chart_id, "missing": sorted(missing)},
                )
        program_ids = set(collections["program"])
        for construction in self.constructions:
            if construction.semantic_program_id not in program_ids:
                raise FieldIntelligenceError(
                    "INVALID_STATE", "construction names an unknown semantic program"
                )
        object.__setattr__(self, "_page_cache", inherited_cache)
        encoded = self.encode()
        object.__setattr__(self, "_encoded", encoded)
        object.__setattr__(self, "_state_sha256", hashlib.sha256(encoded).hexdigest())

    @property
    def state_sha256(self) -> str:
        return self._state_sha256

    def variable(self, variable_id: str) -> VariableSpec:
        try:
            return next(row for row in self.variables if row.variable_id == variable_id)
        except StopIteration as exc:
            raise FieldIntelligenceError(
                "VARIABLE_NOT_FOUND", f"unknown variable: {variable_id}"
            ) from exc

    def chart(self, chart_id: str) -> RelationChart:
        try:
            return next(row for row in self.charts if row.chart_id == chart_id)
        except StopIteration as exc:
            raise FieldIntelligenceError("CHART_NOT_FOUND", f"unknown chart: {chart_id}") from exc

    def transceiver(self, transceiver_id: str) -> FieldTransceiver:
        try:
            return next(row for row in self.transceivers if row.transceiver_id == transceiver_id)
        except StopIteration as exc:
            raise FieldIntelligenceError(
                "TRANSCEIVER_NOT_FOUND", f"unknown transceiver: {transceiver_id}"
            ) from exc
    def temporal(self, memory_id: str) -> TemporalField:
        try:
            return next(row for row in self.temporal_fields if row.memory_id == memory_id)
        except StopIteration as exc:
            raise FieldIntelligenceError(
                "TEMPORAL_NOT_FOUND", f"unknown temporal memory: {memory_id}"
            ) from exc


    def program(self, program_id: str) -> FieldProgram:
        try:
            return next(row for row in self.programs if row.program_id == program_id)
        except StopIteration as exc:
            raise FieldIntelligenceError(
                "PROGRAM_NOT_FOUND", f"unknown program: {program_id}"
            ) from exc

    def construction(self, construction_id: str) -> LanguageConstruction:
        try:
            return next(row for row in self.constructions if row.construction_id == construction_id)
        except StopIteration as exc:
            raise FieldIntelligenceError(
                "CONSTRUCTION_NOT_FOUND", f"unknown construction: {construction_id}"
            ) from exc

    def with_transition(self, kind: str, payload: Mapping[str, Any], **changes: Any) -> AtlasState:
        _identifier(kind, "transition kind")
        transition = {
            "kind": kind,
            "logical_tick": changes.get("logical_tick", self.logical_tick),
            "payload": _json_value(dict(payload), "transition payload"),
            "predecessor_generation": self.generation,
            "predecessor_state_sha256": self.state_sha256,
        }
        history = (*self.transition_log, transition)
        floor = self.transition_epoch_floor
        if len(history) > 128:
            drop = len(history) - 128
            history = history[drop:]
            floor += drop
        return replace(
            self,
            generation=self.generation + 1,
            transition_epoch_floor=floor,
            transition_log=history,
            **changes,
        )

    def _workspace_page(
        self,
        workspace: ResonantWorkspace,
    ) -> tuple[str, bytes, str, bytes]:
        owner = workspace
        descriptor_entry = self._page_cache.get("resonant_workspace")
        field_entry = self._page_cache.get("resonant_workspace:field")
        if (
            descriptor_entry is not None
            and field_entry is not None
            and descriptor_entry[0] is owner
            and field_entry[0] is owner
        ):
            return descriptor_entry[1], descriptor_entry[2], field_entry[1], field_entry[2]
        page_raw = workspace.page_bytes
        page_digest = hashlib.sha256(page_raw).hexdigest()
        descriptor = dict(workspace.as_dict())
        descriptor.pop("field", None)
        descriptor.pop("field_b64", None)
        descriptor["page_sha256"] = page_digest
        descriptor_raw = canonical_json_bytes(descriptor)
        descriptor_digest = hashlib.sha256(descriptor_raw).hexdigest()
        self._page_cache["resonant_workspace"] = (owner, descriptor_digest, descriptor_raw)
        self._page_cache["resonant_workspace:field"] = (owner, page_digest, page_raw)
        return descriptor_digest, descriptor_raw, page_digest, page_raw

    def _page_payload(self, name: str) -> Any:
        if name == "transition_log":
            return [_json_plain(row) for row in self.transition_log]
        if name == "prepared_queries":
            prepared_queries: list[Mapping[str, Any]] = []
            for raw_query in self.prepared_queries:
                query = dict(raw_query)
                branches: list[Mapping[str, Any]] = []
                for raw_branch in query.get("branch_workspaces", ()):
                    branch = dict(raw_branch)
                    branch_workspace = branch.get("workspace")
                    if not isinstance(branch_workspace, ResonantWorkspace):
                        raise FieldIntelligenceError("INVALID_STATE", "prepared workspace is not hydrated")
                    workspace_sha256, _, _, _ = self._workspace_page(branch_workspace)
                    branches.append({
                        "workspace_sha256": workspace_sha256,
                        "state_sha256": branch["state_sha256"],
                        "page_sha256": branch["page_sha256"],
                    })
                query["branch_workspaces"] = branches
                prepared_queries.append(_json_plain(query))
            return prepared_queries
        rows = getattr(self, name)
        return [row.as_dict() for row in rows]

    def _page_bytes(self, name: str) -> tuple[str, bytes]:
        owner = getattr(self, name)
        entry = self._page_cache.get(name)
        if entry is not None and entry[0] is owner:
            return entry[1], entry[2]
        raw = canonical_json_bytes(self._page_payload(name))
        digest = hashlib.sha256(raw).hexdigest()
        self._page_cache[name] = (owner, digest, raw)
        return digest, raw

    def _full_dict(self) -> Mapping[str, Any]:
        workspace = self.resonant_workspace
        full: dict[str, Any] = {
            name: json.loads(self._page_bytes(name)[1].decode("utf-8"))
            for name in _ATLAS_PAGE_NAMES
        }
        full.update({
            "arithmetic_profile": self.arithmetic_profile,
            "frozen_query_ids": sorted(self.frozen_query_ids),
            "generation": self.generation,
            "logical_tick": self.logical_tick,
            "resonant_workspace": (
                None if workspace is None
                else {"workspace_sha256": self._workspace_page(workspace)[0]}
            ),
            "revocation_generation": self.revocation_generation,
            "schema": self.schema,
            "transition_epoch_floor": self.transition_epoch_floor,
        })
        return full

    def as_dict(self) -> Mapping[str, Any]:
        return self._full_dict()

    def object_pages(self) -> Mapping[str, bytes]:
        pages: dict[str, bytes] = {}
        for name in _ATLAS_PAGE_NAMES:
            if name in {"transceivers", "temporal_fields"} and not getattr(self, name):
                continue
            digest, raw = self._page_bytes(name)
            pages[digest] = raw
        workspaces: list[ResonantWorkspace] = []
        if self.resonant_workspace is not None:
            workspaces.append(self.resonant_workspace)
        for query in self.prepared_queries:
            for branch in query.get("branch_workspaces", ()):
                workspaces.append(branch["workspace"])
        for workspace in workspaces:
            descriptor_digest, descriptor_raw, page_digest, page_raw = self._workspace_page(workspace)
            pages[descriptor_digest] = descriptor_raw
            pages[page_digest] = page_raw
        return MappingProxyType(pages)

    def workspace_usage(self) -> Mapping[str, int]:
        """Count the unique reachable body and retained branch workspace pages."""
        seen_pages: set[str] = set()
        workspace_bytes = 0
        ports = 0
        workspaces = itertools.chain(
            (self.resonant_workspace,),
            (
                branch["workspace"]
                for query in self.prepared_queries
                for branch in query.get("branch_workspaces", ())
            ),
        )
        for workspace in workspaces:
            if workspace is None:
                continue
            descriptor_digest, descriptor_raw, page_digest, page_raw = self._workspace_page(workspace)
            if page_digest not in seen_pages:
                ports += workspace.profile.port_count
            for digest, raw in ((descriptor_digest, descriptor_raw), (page_digest, page_raw)):
                if digest not in seen_pages:
                    seen_pages.add(digest)
                    workspace_bytes += len(raw)
        if self.transceivers:
            workspace_bytes += len(self._page_bytes("transceivers")[1])
            ports += sum(len(row.input_ids) + len(row.output_ids) for row in self.transceivers)
        if self.temporal_fields:
            workspace_bytes += len(self._page_bytes("temporal_fields")[1])
            ports += sum(len(row.action_ids) + len(row.observation_ids) for row in self.temporal_fields)
        return {
            "workspace_bytes": workspace_bytes,
            "ports": ports,
            "prepared_branches": sum(
                max(1, len(query.get("branch_workspaces", ())))
                for query in self.prepared_queries
            ),
        }

    def _descriptor(self) -> Mapping[str, Any]:
        page_names = {
            name: self._page_bytes(name)[0]
            for name in _ATLAS_PAGE_NAMES
            if name not in {"transceivers", "temporal_fields"} or getattr(self, name)
        }
        page_names["resonant_workspace"] = (
            None if self.resonant_workspace is None
            else self._workspace_page(self.resonant_workspace)[0]
        )
        return {
            "arithmetic_profile": self.arithmetic_profile,
            "frozen_query_ids": sorted(self.frozen_query_ids),
            "generation": self.generation,
            "logical_tick": self.logical_tick,
            "pages": page_names,
            "revocation_generation": self.revocation_generation,
            "schema": self.schema,
            "transition_epoch_floor": self.transition_epoch_floor,
        }

    @property
    def closure_bytes(self) -> int:
        return len(self.encode()) + sum(len(raw) for raw in self.object_pages().values())

    def encode(self) -> bytes:
        encoded = getattr(self, "_encoded", None)
        if encoded is None:
            return canonical_json_bytes(self._descriptor())
        return encoded

    def encode_bundle(self) -> bytes:
        objects = {
            digest: base64.b64encode(raw).decode("ascii")
            for digest, raw in self.object_pages().items()
        }
        return canonical_json_bytes({"descriptor": json.loads(self.encode()), "objects": objects})

    @classmethod
    def _from_full_dict(cls, row: Mapping[str, Any]) -> AtlasState:
        value = dict(row)
        workspace = value.get("resonant_workspace")
        if workspace is not None and not isinstance(workspace, ResonantWorkspace):
            workspace = ResonantWorkspace.from_dict(workspace)
        value["resonant_workspace"] = workspace
        value["variables"] = tuple(VariableSpec.from_dict(item) for item in value.get("variables", ()))
        value["charts"] = tuple(RelationChart.from_dict(item) for item in value.get("charts", ()))
        value["programs"] = tuple(FieldProgram.from_dict(item) for item in value.get("programs", ()))
        value["constructions"] = tuple(LanguageConstruction.from_dict(item) for item in value.get("constructions", ()))
        value["macros"] = tuple(ExactReduction.from_dict(item) for item in value.get("macros", ()))
        value["predictions"] = tuple(PredictionRecord.from_dict(item) for item in value.get("predictions", ()))
        value["plans"] = tuple(PlanRecord.from_dict(item) for item in value.get("plans", ()))
        value["computation_records"] = tuple(ComputationRecord.from_dict(item) for item in value.get("computation_records", ()))
        value["transceivers"] = tuple(FieldTransceiver.from_dict(item) for item in value.get("transceivers", ()))
        try:
            value["temporal_fields"] = tuple(
                TemporalField.from_dict(item) for item in value.get("temporal_fields", ())
            )
        except TemporalFieldError as exc:
            raise FieldIntelligenceError("INVALID_STATE", str(exc)) from exc
        value["transition_log"] = tuple(value.get("transition_log", ()))
        value["prepared_queries"] = tuple(value.get("prepared_queries", ()))
        value["frozen_query_ids"] = frozenset(value.get("frozen_query_ids", ()))
        value["schema"] = ATLAS_SCHEMA
        return cls(**value)

    @staticmethod
    def _load_workspace_object(
        objects: Mapping[str, bytes], descriptor_digest: str
    ) -> tuple[ResonantWorkspace, str]:
        raw = objects.get(descriptor_digest)
        if raw is None or hashlib.sha256(raw).hexdigest() != descriptor_digest:
            raise FieldIntelligenceError("INVALID_STATE_OBJECT", "missing or corrupt workspace descriptor")
        try:
            descriptor = json.loads(raw.decode("utf-8"))
            if not isinstance(descriptor, Mapping) or set(descriptor) != {
                "schema", "profile", "layout", "bindings", "field_ticks",
                "heartbeat_phase", "heartbeat_cycles", "breath_phase", "breath_cycles",
                "activity", "evidence_tick", "subdivision_ticks", "paused", "ledger",
                "layout_transition", "state_sha256", "page_sha256",
            }:
                raise ValueError("workspace descriptor is not canonical")
            page_digest = _digest(descriptor["page_sha256"], "workspace page digest")
            page_raw = objects.get(page_digest)
            if page_raw is None or hashlib.sha256(page_raw).hexdigest() != page_digest:
                raise ValueError("workspace page is missing or corrupt")
            payload = dict(descriptor)
            payload.pop("page_sha256")
            payload["field_b64"] = base64.b64encode(page_raw).decode("ascii")
            workspace = ResonantWorkspace.from_dict(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError("INVALID_STATE_OBJECT", "workspace descriptor is invalid") from exc
        return workspace, page_digest

    @classmethod
    def decode(cls, encoded: bytes, objects: Mapping[str, bytes] | None = None) -> AtlasState:
        try:
            value = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FieldIntelligenceError("INVALID_STATE", "field checkpoint is unreadable") from exc
        if not isinstance(value, dict) or value.get("schema") != ATLAS_SCHEMA:
            raise FieldIntelligenceError("INCOMPATIBLE_STATE", "normal decode accepts v2 descriptors only")
        if set(value) != {
            "arithmetic_profile", "frozen_query_ids", "generation", "logical_tick",
            "pages", "revocation_generation", "schema", "transition_epoch_floor",
        }:
            raise FieldIntelligenceError("NONCANONICAL_STATE", "field descriptor keys are not canonical")
        pages = value.get("pages")
        page_names = {
            "variables", "charts", "programs", "constructions", "macros", "predictions",
            "plans", "computation_records", "transition_log", "prepared_queries",
            "resonant_workspace",
        }
        if isinstance(pages, dict) and "transceivers" in pages:
            page_names.add("transceivers")
        if isinstance(pages, dict) and "temporal_fields" in pages:
            page_names.add("temporal_fields")
        if not isinstance(pages, dict) or set(pages) != page_names:
            raise FieldIntelligenceError("INVALID_STATE", "v2 descriptor pages are not canonical")
        if objects is None:
            raise FieldIntelligenceError("MISSING_STATE_OBJECTS", "descriptor requires content-addressed objects")
        if not isinstance(objects, Mapping):
            raise FieldIntelligenceError("INVALID_STATE_OBJECT", "state objects must be a mapping")
        for digest, raw in objects.items():
            _digest(digest, "state object digest")
            if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != digest:
                raise FieldIntelligenceError("INVALID_STATE_OBJECT", "state object is missing or corrupt")
        full: dict[str, Any] = {
            key: value[key] for key in (
                "arithmetic_profile", "frozen_query_ids", "generation", "logical_tick",
                "revocation_generation", "transition_epoch_floor", "schema",
            )
        }
        expected_objects: set[str] = set()
        for name in page_names:
            digest = pages[name]
            if digest is None:
                if name != "resonant_workspace":
                    raise FieldIntelligenceError("INVALID_STATE", f"{name} page cannot be null")
                full[name] = None
                continue
            _digest(digest, f"{name} page digest")
            raw = objects.get(digest)
            if raw is None:
                raise FieldIntelligenceError("INVALID_STATE_OBJECT", f"missing {name} page")
            expected_objects.add(digest)
            if name == "resonant_workspace":
                full[name] = {"workspace_sha256": digest}
                continue
            try:
                full[name] = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise FieldIntelligenceError("INVALID_STATE_OBJECT", f"{name} page is unreadable") from exc
        prepared = full["prepared_queries"]
        if not isinstance(prepared, list):
            raise FieldIntelligenceError("INVALID_STATE_OBJECT", "prepared query page must be a list")
        hydrated_queries: list[Mapping[str, Any]] = []
        for raw_query in prepared:
            if not isinstance(raw_query, Mapping):
                raise FieldIntelligenceError("INVALID_STATE_OBJECT", "prepared query is not a mapping")
            query = dict(raw_query)
            branches = query.get("branch_workspaces", [])
            if not isinstance(branches, list):
                raise FieldIntelligenceError("INVALID_STATE_OBJECT", "prepared branch workspaces are not a list")
            hydrated_branches: list[Mapping[str, Any]] = []
            for raw_branch in branches:
                if not isinstance(raw_branch, Mapping) or set(raw_branch) != {
                    "workspace_sha256", "state_sha256", "page_sha256"
                }:
                    raise FieldIntelligenceError("INVALID_STATE_OBJECT", "prepared workspace reference is not canonical")
                workspace_digest = _digest(raw_branch["workspace_sha256"], "workspace descriptor digest")
                state_digest = _digest(raw_branch["state_sha256"], "workspace state digest")
                page_digest = _digest(raw_branch["page_sha256"], "workspace page digest")
                workspace, descriptor_page_digest = cls._load_workspace_object(
                    objects, workspace_digest
                )
                expected_objects.update({workspace_digest, descriptor_page_digest})
                if descriptor_page_digest != page_digest or workspace.state_sha256 != state_digest:
                    raise FieldIntelligenceError("INVALID_STATE_OBJECT", "workspace reference digest mismatch")
                hydrated_branches.append({
                    "workspace": workspace,
                    "state_sha256": state_digest,
                    "page_sha256": page_digest,
                })
            query["branch_workspaces"] = hydrated_branches
            hydrated_queries.append(query)
        full["prepared_queries"] = hydrated_queries
        root_workspace = full.get("resonant_workspace")
        if root_workspace is not None:
            if not isinstance(root_workspace, Mapping) or set(root_workspace) != {"workspace_sha256"}:
                raise FieldIntelligenceError("INVALID_STATE_OBJECT", "resonant workspace reference is not canonical")
            workspace_digest = _digest(root_workspace["workspace_sha256"], "workspace descriptor digest")
            workspace, page_digest = cls._load_workspace_object(objects, workspace_digest)
            expected_objects.update({workspace_digest, page_digest})
            full["resonant_workspace"] = workspace
        if set(objects) != expected_objects:
            raise FieldIntelligenceError("NONCANONICAL_STATE", "state object closure contains unreachable objects")
        result = cls._from_full_dict(full)
        if result.encode() != encoded:
            raise FieldIntelligenceError("NONCANONICAL_STATE", "field descriptor is not canonical")
        return result
    @classmethod
    def decode_bundle(cls, encoded: bytes) -> AtlasState:
        try:
            bundle = json.loads(encoded.decode("utf-8"))
            if not isinstance(bundle, dict) or set(bundle) != {"descriptor", "objects"}:
                raise ValueError("state bundle keys are not canonical")
            if canonical_json_bytes(bundle) != encoded:
                raise ValueError("state bundle is not canonical")
            descriptor = canonical_json_bytes(bundle["descriptor"])
            raw_objects = bundle["objects"]
            if not isinstance(raw_objects, Mapping):
                raise ValueError("state bundle objects are not a mapping")
            objects = {
                digest: base64.b64decode(raw.encode("ascii"), validate=True)
                for digest, raw in raw_objects.items()
            }
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, AttributeError, json.JSONDecodeError) as exc:
            raise FieldIntelligenceError("INVALID_STATE", "state bundle is unreadable") from exc
        return cls.decode(descriptor, objects)

    @classmethod
    def migrate_v1(cls, encoded: bytes) -> AtlasState:
        try:
            value = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FieldIntelligenceError("INVALID_STATE", "legacy checkpoint is unreadable") from exc
        if not isinstance(value, dict) or value.get("schema") != ATLAS_LEGACY_SCHEMA:
            raise FieldIntelligenceError("INCOMPATIBLE_STATE", "expected a v1 atlas checkpoint")
        value["prepared_queries"] = ()
        value["frozen_query_ids"] = ()
        value["resonant_workspace"] = initial_workspace()
        value["transition_epoch_floor"] = 0
        return cls._from_full_dict(value)


@dataclass(frozen=True, slots=True)
class AffineConstraint:
    coefficients: Mapping[str, float]
    target: float
    evidence_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.coefficients:
            raise FieldIntelligenceError("INVALID_CONSTRAINT", "constraint cannot be empty")
        normalized: dict[str, float] = {}
        for variable_id, coefficient in self.coefficients.items():
            _identifier(variable_id, "constraint variable")
            normalized[variable_id] = _finite(coefficient, "constraint coefficient")
        if not any(value != 0 for value in normalized.values()):
            raise FieldIntelligenceError("INVALID_CONSTRAINT", "constraint coefficients are all zero")
        object.__setattr__(self, "coefficients", _FrozenDict(normalized))
        object.__setattr__(
            self, "evidence_event_ids", tuple(self.evidence_event_ids)
        )
        _finite(self.target, "constraint target")
        for event_id in self.evidence_event_ids:
            _digest(event_id, "constraint evidence event")


@dataclass(frozen=True, slots=True)
class BranchSolution:
    branch_id: str
    status: str
    variable_order: tuple[str, ...]
    values: Mapping[str, float]
    response: tuple[tuple[float, ...], ...]
    observed_order: tuple[str, ...]
    active_chart_versions: tuple[tuple[str, int], ...]
    source_revision_ids: tuple[str, ...]
    residual_norm: float | None
    constraint_residual: float | None
    condition_number: float | None
    spectral_lower_bound: float | None
    solution_error_bound: float | None
    numerical_settled: bool
    epistemically_supportable: bool
    obligations: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "variable_order", tuple(self.variable_order))
        object.__setattr__(
            self,
            "values",
            _FrozenDict(
                {
                    _identifier(name, "branch variable"): _finite(
                        value, "branch value"
                    )
                    for name, value in self.values.items()
                }
            ),
        )
        object.__setattr__(
            self, "response", tuple(tuple(row) for row in self.response)
        )
        object.__setattr__(self, "observed_order", tuple(self.observed_order))
        object.__setattr__(
            self,
            "active_chart_versions",
            tuple((item[0], int(item[1])) for item in self.active_chart_versions),
        )
        object.__setattr__(
            self, "source_revision_ids", tuple(self.source_revision_ids)
        )
        object.__setattr__(self, "obligations", tuple(self.obligations))
        _identifier(self.branch_id, "branch_id")
        if self.status not in {"settled", "underdetermined", "infeasible", "exhausted"}:
            raise FieldIntelligenceError("INVALID_QUERY_RESULT", "branch status is unsupported")
        for name in (
            "residual_norm", "constraint_residual", "condition_number",
            "spectral_lower_bound", "solution_error_bound",
        ):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value))
            ):
                object.__setattr__(self, name, None)
                object.__setattr__(self, "numerical_settled", False)
        if any(
            getattr(self, name) is None
            for name in ("residual_norm", "constraint_residual")
        ) and "nonfinite-diagnostic" not in self.obligations:
            object.__setattr__(
                self, "obligations", (*self.obligations, "nonfinite-diagnostic")
            )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "active_chart_versions": [list(row) for row in self.active_chart_versions],
            "branch_id": self.branch_id,
            "condition_number": self.condition_number,
            "constraint_residual": self.constraint_residual,
            "epistemically_supportable": self.epistemically_supportable,
            "numerical_settled": self.numerical_settled,
            "obligations": list(self.obligations),
            "observed_order": list(self.observed_order),
            "residual_norm": self.residual_norm,
            "response": [list(row) for row in self.response],
            "solution_error_bound": self.solution_error_bound,
            "source_revision_ids": list(self.source_revision_ids),
            "spectral_lower_bound": self.spectral_lower_bound,
            "status": self.status,
            "values": _json_plain(self.values),
            "variable_order": list(self.variable_order),
        }


@dataclass(frozen=True, slots=True)
class QueryResult:
    status: str
    state_sha256: str
    field_generation: int
    branches: tuple[BranchSolution, ...]
    requested: tuple[str, ...]
    observed: Mapping[str, float]
    context: Mapping[str, Any]
    memory_unchanged: bool
    query_id: str | None = None
    checkpoint_receipt: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "branches", tuple(self.branches))
        object.__setattr__(self, "requested", tuple(self.requested))
        object.__setattr__(
            self,
            "observed",
            _FrozenDict(
                {
                    _identifier(name, "observed variable"): _finite(value, "observed value")
                    for name, value in self.observed.items()
                }
            ),
        )
        object.__setattr__(self, "context", _json_value(dict(self.context), "query context"))
        if self.query_id is not None:
            _identifier(self.query_id, "query_id")
        if self.checkpoint_receipt is not None:
            object.__setattr__(
                self,
                "checkpoint_receipt",
                _json_value(dict(self.checkpoint_receipt), "checkpoint receipt"),
            )


    def as_dict(self) -> Mapping[str, Any]:
        return {
            "branches": [row.as_dict() for row in self.branches],
            "checkpoint_receipt": None if self.checkpoint_receipt is None else _json_plain(self.checkpoint_receipt),
            "context": _json_plain(self.context),
            "field_generation": self.field_generation,
            "memory_unchanged": self.memory_unchanged,
            "observed": _json_plain(self.observed),
            "query_id": self.query_id,
            "requested": list(self.requested),
            "state_sha256": self.state_sha256,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> QueryResult:
        row = dict(value)
        row["branches"] = tuple(
            BranchSolution(
                branch_id=item["branch_id"],
                status=item["status"],
                variable_order=tuple(item["variable_order"]),
                values=item["values"],
                response=tuple(tuple(v) for v in item["response"]),
                observed_order=tuple(item["observed_order"]),
                active_chart_versions=tuple(tuple(v) for v in item["active_chart_versions"]),
                source_revision_ids=tuple(item["source_revision_ids"]),
                residual_norm=item["residual_norm"],
                constraint_residual=item["constraint_residual"],
                condition_number=item["condition_number"],
                spectral_lower_bound=item["spectral_lower_bound"],
                solution_error_bound=item["solution_error_bound"],
                numerical_settled=item["numerical_settled"],
                epistemically_supportable=item["epistemically_supportable"],
                obligations=tuple(item["obligations"]),
            )
            for item in row["branches"]
        )
        row["requested"] = tuple(row["requested"])
        return cls(**row)


class FieldAtlas:
    """Pure operations over one immutable adaptive :class:`AtlasState`."""

    def initial_state(self) -> AtlasState:
        return AtlasState()

    @staticmethod
    def _replace_identified(rows: Sequence[Any], identity: str, replacement: Any, attr: str) -> tuple[Any, ...]:
        found = False
        result: list[Any] = []
        for row in rows:
            if getattr(row, attr) == identity:
                result.append(replacement)
                found = True
            else:
                result.append(row)
        if not found:
            raise FieldIntelligenceError("IDENTITY_NOT_FOUND", f"unknown identity: {identity}")
        return tuple(result)

    def add_variable(self, state: AtlasState, variable: VariableSpec) -> AtlasState:
        if any(row.variable_id == variable.variable_id for row in state.variables):
            existing = state.variable(variable.variable_id)
            if existing == variable:
                return state
            raise FieldIntelligenceError(
                "VARIABLE_CONFLICT", "variable identity already has different semantics"
            )
        return state.with_transition(
            "variable-added",
            {"variable_id": variable.variable_id},
            variables=(*state.variables, variable),
        )

    def add_chart(self, state: AtlasState, chart: RelationChart) -> AtlasState:
        for variable_id in chart.scope:
            state.variable(variable_id)
        if any(row.chart_id == chart.chart_id for row in state.charts):
            existing = state.chart(chart.chart_id)
            if existing.as_dict() == chart.as_dict():
                return state
            raise FieldIntelligenceError(
                "CHART_CONFLICT", "chart identity already has different semantics"
            )
        return state.with_transition(
            "chart-added", {"chart_id": chart.chart_id}, charts=(*state.charts, chart)
        )

    def replace_chart(self, state: AtlasState, chart: RelationChart) -> AtlasState:
        previous = state.chart(chart.chart_id)
        if chart.version <= previous.version:
            chart = replace(chart, version=previous.version + 1)
        charts = self._replace_identified(state.charts, chart.chart_id, chart, "chart_id")
        macros = tuple(
            replace(row, status="stale", version=row.version + 1)
            if any(parent_id == chart.chart_id for parent_id, _ in row.parent_chart_versions)
            else row
            for row in state.macros
        )
        predictions = tuple(
            replace(row, status="invalidated")
            if row.status in {"predicted", "proposed"}
            and any(parent_id == chart.chart_id for parent_id, _ in row.dependency_versions)
            else row
            for row in state.predictions
        )
        plans = tuple(
            replace(
                row,
                status="invalidated",
                segments=tuple(
                    replace(segment, status="invalidated")
                    if any(
                        parent_id == chart.chart_id
                        for parent_id, _ in segment.dependency_versions
                    )
                    and segment.status in {"open", "ready", "unresolved"}
                    else segment
                    for segment in row.segments
                ),
            )
            if row.status in {"open", "ready", "unresolved"}
            and any(
                parent_id == chart.chart_id
                for segment in row.segments
                for parent_id, _ in segment.dependency_versions
            )
            else row
            for row in state.plans
        )
        prepared_queries = tuple(
            {**row, "status": "invalidated", "reason": "chart-replaced"}
            for row in state.prepared_queries
        )
        return state.with_transition(
            "chart-replaced",
            {"chart_id": chart.chart_id, "previous_version": previous.version},
            charts=charts,
            macros=macros,
            predictions=predictions,
            plans=plans,
            prepared_queries=prepared_queries,
            frozen_query_ids=frozenset(),
        )

    def add_program(self, state: AtlasState, program: FieldProgram) -> AtlasState:
        if any(row.program_id == program.program_id for row in state.programs):
            existing = state.program(program.program_id)
            if existing.as_dict() == program.as_dict():
                return state
            raise FieldIntelligenceError(
                "PROGRAM_CONFLICT", "program identity already has different semantics"
            )
        return state.with_transition(
            "program-added", {"program_id": program.program_id}, programs=(*state.programs, program)
        )

    def replace_program(self, state: AtlasState, program: FieldProgram) -> AtlasState:
        previous = state.program(program.program_id)
        if program.version <= previous.version:
            program = replace(program, version=previous.version + 1)
        rows = self._replace_identified(state.programs, program.program_id, program, "program_id")
        constructions = tuple(
            replace(row, status="stale", version=row.version + 1)
            if row.semantic_program_id == program.program_id
            else row
            for row in state.constructions
        )
        predictions = tuple(
            replace(row, status="invalidated")
            if row.status in {"predicted", "proposed"}
            and any(
                dependency_id == program.program_id
                for dependency_id, _ in row.dependency_versions
            )
            else row
            for row in state.predictions
        )
        plans = tuple(
            replace(row, status="invalidated")
            if row.status in {"open", "ready", "unresolved"}
            and any(
                dependency_id == program.program_id
                for segment in row.segments
                for dependency_id, _ in segment.dependency_versions
            )
            else row
            for row in state.plans
        )
        prepared_queries = tuple(
            {**row, "status": "invalidated", "reason": "program-replaced"}
            for row in state.prepared_queries
        )
        return state.with_transition(
            "program-replaced",
            {"program_id": program.program_id, "previous_version": previous.version},
            programs=rows,
            constructions=constructions,
            predictions=predictions,
            plans=plans,
            prepared_queries=prepared_queries,
            frozen_query_ids=frozenset(),
        )

    def add_construction(self, state: AtlasState, construction: LanguageConstruction) -> AtlasState:
        state.program(construction.semantic_program_id)
        if any(row.construction_id == construction.construction_id for row in state.constructions):
            existing = state.construction(construction.construction_id)
            if existing.as_dict() == construction.as_dict():
                return state
            raise FieldIntelligenceError(
                "CONSTRUCTION_CONFLICT", "construction identity already has different semantics"
            )
        return state.with_transition(
            "construction-added",
            {"construction_id": construction.construction_id},
            constructions=(*state.constructions, construction),
        )

    def replace_construction(
        self, state: AtlasState, construction: LanguageConstruction
    ) -> AtlasState:
        previous = state.construction(construction.construction_id)
        if construction.version <= previous.version:
            construction = replace(construction, version=previous.version + 1)
        rows = self._replace_identified(
            state.constructions,
            construction.construction_id,
            construction,
            "construction_id",
        )
        prepared_queries = tuple(
            {**row, "status": "invalidated", "reason": "construction-replaced"}
            for row in state.prepared_queries
        )
        return state.with_transition(
            "construction-replaced",
            {
                "construction_id": construction.construction_id,
                "previous_version": previous.version,
            },
            constructions=rows,
            prepared_queries=prepared_queries,
            frozen_query_ids=frozenset(),
        )
    def admit_observation(
        self,
        state: AtlasState,
        *,
        event_id: str,
        source_revision_id: str,
        values: Mapping[str, float],
        context: Mapping[str, Any],
        epistemic_type: str = "observed",
        weight: float = 1.0,
        derivation_roots: Sequence[str] = (),
        target_chart_ids: Sequence[str] | None = None,
    ) -> tuple[AtlasState, Mapping[str, Any]]:
        _digest(event_id, "event_id")
        _digest(source_revision_id, "source_revision_id")
        if epistemic_type not in {"observed", "asserted", "derived"}:
            raise FieldIntelligenceError(
                "EPISTEMIC_BOUNDARY",
                "hypothetical, desired, and permitted values cannot teach observed memory",
            )
        normalized_values: dict[str, float] = {}
        for variable_id, value in values.items():
            spec = state.variable(variable_id)
            number = _finite(value, variable_id)
            if not spec.contains(number):
                raise FieldIntelligenceError(
                    "OBSERVATION_OUT_OF_DOMAIN", f"{variable_id} is outside its declared domain"
                )
            normalized_values[variable_id] = number
        normalized_context = _json_value(dict(context), "observation context")
        tick = state.logical_tick + 1
        targets = None if target_chart_ids is None else frozenset(target_chart_ids)
        if targets is not None:
            for chart_id in targets:
                state.chart(chart_id)
        updated: list[RelationChart] = []
        learned: list[str] = []
        partial: list[str] = []
        context_sha = sha256_value(normalized_context)
        for chart in state.charts:
            selected = targets is None or chart.chart_id in targets
            if not selected or not chart.matches(normalized_context):
                updated.append(chart)
                continue
            if not set(chart.scope).issubset(normalized_values):
                partial.append(chart.chart_id)
                updated.append(chart)
                continue
            contribution = SupportContribution(
                event_id=event_id,
                source_revision_id=source_revision_id,
                values=tuple(normalized_values[name] for name in chart.scope),
                weight=_finite(weight, "observation weight", positive=True),
                logical_tick=tick,
                epistemic_type=epistemic_type,
                context_sha256=context_sha,
                derivation_roots=tuple(derivation_roots),
            )
            successor = chart.admit(contribution, at_tick=tick)
            updated.append(successor)
            if successor is not chart:
                learned.append(chart.chart_id)
        if not learned and targets is not None and partial:
            raise FieldIntelligenceError(
                "PARTIAL_OBSERVATION",
                "requested charts lack fully observed local coordinates",
                details={"partial_chart_ids": partial},
            )
        if not learned:
            raise FieldIntelligenceError(
                "NO_APPLICABLE_CHART",
                "observation did not fully support any applicable chart",
                details={"partial_chart_ids": partial},
            )
        prepared_queries = tuple(
            {**row, "status": "invalidated", "reason": "observation-admitted"}
            for row in state.prepared_queries
        )
        successor = state.with_transition(
            "observation-admitted",
            {
                "event_id": event_id,
                "learned_chart_ids": learned,
                "partial_chart_ids": partial,
                "source_revision_id": source_revision_id,
            },
            logical_tick=tick,
            charts=tuple(updated),
            prepared_queries=prepared_queries,
            frozen_query_ids=frozenset(),
        )
        return successor, {
            "event_id": event_id,
            "learned_chart_ids": learned,
            "partial_chart_ids": partial,
            "predecessor_state_sha256": state.state_sha256,
            "successor_state_sha256": successor.state_sha256,
        }

    def retract_sources(
        self,
        state: AtlasState,
        source_revision_ids: Sequence[str],
        *,
        revocation_generation: int,
    ) -> tuple[AtlasState, Mapping[str, Any]]:
        targets = frozenset(_digest(item, "source_revision_id") for item in source_revision_ids)
        if not targets:
            raise FieldIntelligenceError("INVALID_REVOCATION", "revocation target cannot be empty")
        if revocation_generation <= state.revocation_generation:
            raise FieldIntelligenceError(
                "STALE_REVOCATION", "revocation generation must advance monotonically"
            )
        tick = state.logical_tick + 1
        invalid_roots: set[str] = set(targets)
        removed_events: set[str] = set()
        changed = True
        while changed:
            changed = False
            for chart in state.charts:
                for contribution in chart.contributions:
                    if contribution.event_id in removed_events:
                        continue
                    if (
                        contribution.source_revision_id in targets
                        or invalid_roots.intersection(contribution.derivation_roots)
                    ):
                        removed_events.add(contribution.event_id)
                        invalid_roots.add(contribution.event_id)
                        changed = True
        removed_event_ids = frozenset(removed_events)
        affected_charts: list[str] = []
        charts: list[RelationChart] = []
        for chart in state.charts:
            successor = chart.remove_evidence(
                targets,
                removed_event_ids,
                at_tick=tick,
            )
            if successor is not chart:
                affected_charts.append(chart.chart_id)
            charts.append(successor)
        programs = tuple(
            replace(row, status="stale", version=row.version + 1)
            if targets.intersection(
                contribution.source_revision_id
                for chart in state.charts
                for contribution in chart.contributions
                if contribution.event_id in row.support_event_ids
            )
            or set(row.support_event_ids).intersection(removed_events)
            else row
            for row in state.programs
        )
        constructions = tuple(
            replace(row, status="stale", version=row.version + 1)
            if set(row.support_event_ids).intersection(removed_events)
            else row
            for row in state.constructions
        )
        macros = tuple(
            replace(row, status="stale", version=row.version + 1)
            if set(row.support_event_ids).intersection(removed_events)
            or any(parent in affected_charts for parent, _ in row.parent_chart_versions)
            else row
            for row in state.macros
        )
        predictions = tuple(
            replace(row, status="invalidated")
            if set(row.source_revision_ids).intersection(targets)
            or any(parent in affected_charts for parent, _ in row.dependency_versions)
            else row
            for row in state.predictions
        )
        plans = tuple(
            replace(row, status="invalidated")
            if set(row.source_revision_ids).intersection(targets)
            or any(
                parent in affected_charts
                for segment in row.segments
                for parent, _ in segment.dependency_versions
            )
            else row
            for row in state.plans
        )
        prepared_queries = tuple(
            {
                **row,
                "status": "invalidated",
                "reason": "source-revoked",
            }
            if targets.intersection(
                source
                for branch in QueryResult.from_dict(row["result"]).branches
                for source in branch.source_revision_ids
            )
            else row
            for row in state.prepared_queries
        )
        affected_temporal = [
            row.memory_id for row in state.temporal_fields
            if targets.intersection(row.source_revision_ids)
        ]
        temporal_fields = tuple(
            TemporalField.initial(
                row.memory_id, action_ids=row.action_ids,
                observation_ids=row.observation_ids, max_states=row.max_states,
                context=row.context,
            ) if row.memory_id in affected_temporal else row
            for row in state.temporal_fields
        )
        successor = state.with_transition(
            "sources-revoked",
            {
                "affected_chart_ids": affected_charts,
                "source_revision_ids": sorted(targets),
                "affected_temporal_ids": affected_temporal,
            },
            logical_tick=tick,
            revocation_generation=revocation_generation,
            charts=tuple(charts),
            programs=programs,
            constructions=constructions,
            macros=macros,
            predictions=predictions,
            plans=plans,
            prepared_queries=prepared_queries,
            temporal_fields=temporal_fields,
            frozen_query_ids=frozenset(
                query_id
                for query_id in state.frozen_query_ids
                if any(row.get("query_id") == query_id and row.get("status") == "prepared" for row in prepared_queries)
            ),
        )
        return successor, {
            "affected_chart_ids": affected_charts,
            "affected_temporal_ids": affected_temporal,
            "removed_event_ids": sorted(removed_events),
            "revocation_generation": revocation_generation,
        }

    @staticmethod
    def _relevant_charts(
        state: AtlasState,
        observed: frozenset[str],
        requested: frozenset[str],
        context: Mapping[str, Any],
        valid_sources: frozenset[str] | None,
    ) -> tuple[RelationChart, ...]:
        candidates = tuple(
            chart
            for chart in state.charts
            if chart.matches(context)
            and chart.contributions
            and (
                valid_sources is None
                or chart.active_source_revisions().issubset(valid_sources)
            )
        )
        relevant = set(observed | requested)
        selected: set[str] = set()
        changed = True
        while changed:
            changed = False
            for chart in candidates:
                if chart.chart_id in selected or not relevant.intersection(chart.scope):
                    continue
                selected.add(chart.chart_id)
                before = len(relevant)
                relevant.update(chart.scope)
                changed = changed or len(relevant) != before
        return tuple(chart for chart in candidates if chart.chart_id in selected)

    @staticmethod
    def _branches(charts: Sequence[RelationChart], max_branches: int) -> tuple[tuple[RelationChart, ...], ...]:
        common = [chart for chart in charts if chart.mode_group is None]
        grouped: dict[str, list[RelationChart]] = {}
        for chart in charts:
            if chart.mode_group is not None:
                grouped.setdefault(chart.mode_group, []).append(chart)
        choices: list[tuple[tuple[RelationChart, ...], ...]] = []
        for group in sorted(grouped):
            by_mode: dict[str, list[RelationChart]] = {}
            for chart in grouped[group]:
                assert chart.mode is not None
                by_mode.setdefault(chart.mode, []).append(chart)
            choices.append(tuple(tuple(by_mode[mode]) for mode in sorted(by_mode)))
        count = math.prod(len(row) for row in choices) if choices else 1
        if count > max_branches:
            raise FieldIntelligenceError(
                "BRANCH_BUDGET",
                "surviving discrete modes exceed the branch budget",
                details={"required": count, "limit": max_branches},
            )
        if not choices:
            return (tuple(common),)
        return tuple(tuple(common) + tuple(itertools.chain.from_iterable(parts)) for parts in itertools.product(*choices))

    @staticmethod
    def _variable_order(
        state: AtlasState,
        charts: Sequence[RelationChart],
        observed: Mapping[str, float],
        requested: Sequence[str],
    ) -> tuple[str, ...]:
        relevant = set(observed) | set(requested)
        for chart in charts:
            relevant.update(chart.scope)
        return tuple(row.variable_id for row in state.variables if row.variable_id in relevant)

    @staticmethod
    def _assemble_precision(
        order: Sequence[str], charts: Sequence[RelationChart]
    ) -> Tensor:
        index = {name: position for position, name in enumerate(order)}
        result = torch.zeros((len(order), len(order)), dtype=torch.float64)
        for chart in charts:
            local = chart.factor_weight * chart.precision()
            positions = torch.tensor([index[name] for name in chart.scope], dtype=torch.long)
            result[positions[:, None], positions[None, :]] += local
        return result
    @staticmethod
    def _inconsistent_constraint_residual(
        problem: ResonantProblem | None,
        *,
        tolerance: float,
    ) -> float | None:
        """Return a finite contradiction witness before the wave solver runs."""
        if problem is None or problem.affine_constraints is None:
            return None
        rows, targets = problem.affine_constraints
        if len(rows) == 0:
            return None
        matrix = torch.tensor(rows, dtype=torch.float64)
        target = torch.tensor(targets, dtype=torch.float64)
        singular = torch.linalg.svdvals(matrix)
        scale = float(singular.max()) if singular.numel() else 0.0
        threshold = max(matrix.shape) * torch.finfo(torch.float64).eps * max(1.0, scale)
        rank = int(torch.count_nonzero(singular > threshold))
        inverse = torch.linalg.pinv(matrix)
        residual = target - matrix @ (inverse @ target)
        norm = float(torch.linalg.vector_norm(residual))
        if rank < matrix.shape[0] and norm > tolerance * max(1.0, float(torch.linalg.vector_norm(target))):
            return norm
        return None

    @staticmethod
    def _inconsistent_branch(
        charts: Sequence[RelationChart],
        order: Sequence[str],
        observed: Mapping[str, float],
        workspace: ResonantWorkspace,
        constraint_residual: float,
    ) -> BranchSolution:
        versions = tuple((chart.chart_id, chart.version) for chart in charts)
        sources = tuple(sorted({source for chart in charts for source in chart.active_source_revisions()}))
        return BranchSolution(
            branch_id=sha256_value({
                "charts": versions,
                "resonant": workspace.state_sha256,
                "status": "infeasible",
            }),
            status="infeasible",
            variable_order=tuple(order),
            values={},
            response=tuple(tuple(0.0 for _ in observed) for _ in order),
            observed_order=tuple(observed),
            active_chart_versions=versions,
            source_revision_ids=sources,
            residual_norm=0.0,
            constraint_residual=constraint_residual,
            condition_number=None,
            spectral_lower_bound=None,
            solution_error_bound=constraint_residual,
            numerical_settled=False,
            epistemically_supportable=False,
            obligations=("inconsistent-constraints",),
        )



    @staticmethod
    def _failed_branch(
        charts: Sequence[RelationChart],
        order: Sequence[str],
        observed: Mapping[str, float],
        status: str,
        obligations: tuple[str, ...],
    ) -> BranchSolution:
        versions = tuple((chart.chart_id, chart.version) for chart in charts)
        sources = sorted({source for chart in charts for source in chart.active_source_revisions()})
        return BranchSolution(
            branch_id=sha256_value({"charts": versions, "status": status}),
            status=status,
            variable_order=tuple(order),
            values={},
            response=(),
            observed_order=tuple(observed),
            active_chart_versions=versions,
            source_revision_ids=tuple(sources),
            residual_norm=None,
            constraint_residual=None,
            condition_number=None,
            spectral_lower_bound=None,
            solution_error_bound=None,
            numerical_settled=False,
            epistemically_supportable=False,
            obligations=obligations,
        )

    @staticmethod
    def _resonant_problem(
        state: AtlasState,
        charts: Sequence[RelationChart],
        observed: Mapping[str, float],
        constraints: Sequence[AffineConstraint],
    ) -> ResonantProblem | None:
        if not charts:
            return None
        order = FieldAtlas._variable_order(state, charts, observed, ())
        if not order:
            return None
        precision = FieldAtlas._assemble_precision(order, charts)
        dependency = sha256_value(
            {
                "charts": [(chart.chart_id, chart.version) for chart in charts],
                "sources": sorted(
                    {source for chart in charts for source in chart.active_source_revisions()}
                ),
            }
        )
        rows: list[tuple[tuple[float, ...], float]] = []
        for constraint in constraints:
            rows.append(
                (
                    tuple(float(constraint.coefficients.get(name, 0.0)) for name in order),
                    float(constraint.target),
                )
            )
        for name, value in observed.items():
            if name in order:
                rows.append(
                    (
                        tuple(1.0 if variable == name else 0.0 for variable in order),
                        float(value),
                    )
                )
        for spec in state.variables:
            if spec.variable_id in order and spec.kind == "constant" and spec.constant is not None:
                rows.append(
                    (
                        tuple(1.0 if variable == spec.variable_id else 0.0 for variable in order),
                        float(spec.constant),
                    )
                )
        affine = (tuple(row for row, _ in rows), tuple(target for _, target in rows)) if rows else None
        return ResonantProblem(
            variable_ids=tuple(order),
            precision=precision,
            linear_b=torch.zeros(len(order), dtype=torch.float64),
            observed=dict(observed),
            affine_constraints=affine,
            dependency_sha256=dependency,
        )

    def condense_transceiver(
        self,
        state: AtlasState,
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
    ) -> tuple[AtlasState, Mapping[str, Any]]:
        """Compile supported local work without adding evidence or another learner."""
        _identifier(transceiver_id, "transceiver_id")
        chart_ids, input_ids, output_ids = tuple(chart_ids), tuple(input_ids), tuple(output_ids)
        if not chart_ids or len(chart_ids) != len(set(chart_ids)):
            raise FieldIntelligenceError("INVALID_TRANSCEIVER", "chart_ids must be nonempty and unique")
        for label, ids in (("input_ids", input_ids), ("output_ids", output_ids)):
            if not ids or len(ids) != len(set(ids)):
                raise FieldIntelligenceError("INVALID_TRANSCEIVER", f"{label} must be nonempty and unique")
        if set(input_ids).intersection(output_ids):
            raise FieldIntelligenceError("INVALID_TRANSCEIVER", "input and output ports must be distinct")
        existing = next((row for row in state.transceivers if row.transceiver_id == transceiver_id), None)
        if existing is not None and existing.status == "active":
            raise FieldIntelligenceError("IDENTITY_CONFLICT", "active transceiver already exists")
        normalized_context = _json_value(dict(context), "transceiver context")
        charts = tuple(state.chart(name) for name in chart_ids)
        if any(not chart.matches(normalized_context) or not chart.contributions for chart in charts):
            raise FieldIntelligenceError("UNSUPPORTED_TRANSCEIVER", "condensation requires applicable observed support")
        modes: dict[str, str] = {}
        for chart in charts:
            if chart.mode_group is not None:
                if chart.mode_group in modes and modes[chart.mode_group] != chart.mode:
                    raise FieldIntelligenceError("AMBIGUOUS_TRANSCEIVER", "alternative chart modes cannot be blended")
                modes[chart.mode_group] = str(chart.mode)
        scope = {name for chart in charts for name in chart.scope}
        if not set((*input_ids, *output_ids)).issubset(scope):
            raise FieldIntelligenceError("INVALID_TRANSCEIVER", "all ports must belong to the supported computation")
        if len(scope) > 128:
            raise FieldIntelligenceError("WORK_CAPACITY", "local transceiver scope exceeds 128 variables")
        fixed: dict[str, float] = {}
        for name, value in (observed or {}).items():
            spec = state.variable(name)
            number = _finite(value, name)
            if name not in scope or name in (*input_ids, *output_ids):
                raise FieldIntelligenceError("INVALID_TRANSCEIVER", "fixed observations must be internal boundary variables")
            if not spec.contains(number) or spec.kind == "constant" and number != spec.constant:
                raise FieldIntelligenceError("OBSERVATION_OUT_OF_DOMAIN", "fixed boundary is outside its domain")
            fixed[name] = number
        for name in scope:
            spec = state.variable(name)
            if spec.kind == "constant":
                if name in (*input_ids, *output_ids):
                    raise FieldIntelligenceError("INVALID_TRANSCEIVER", "constant variables cannot be driven or emitted")
                fixed[name] = float(spec.constant)
        order = self._variable_order(state, charts, {}, ())
        sources = tuple(sorted({source for chart in charts for source in chart.active_source_revisions()}))
        versions = tuple((chart.chart_id, chart.version) for chart in charts)
        problem = ResonantProblem(
            variable_ids=order,
            precision=self._assemble_precision(order, charts),
            observed={**fixed, **{name: 0.0 for name in input_ids}},
            dependency_sha256=sha256_value({"charts": versions, "sources": sources}),
        )
        root = state.resonant_workspace or initial_workspace()
        workspace = initial_workspace(root.profile)._copy(
            bindings={name: binding for name, binding in root.bindings.items() if name in scope},
            evidence_tick=state.logical_tick,
        )
        try:
            workspace = bind_workspace(workspace, problem)
            kernel, working_state, receipt = condense_workspace(
                workspace, problem, input_ids=input_ids, output_ids=output_ids,
                rank=rank, error_allowance=error_allowance,
                input_bound=input_bound, horizon_ticks=horizon_ticks,
            )
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise FieldIntelligenceError("INVALID_TRANSCEIVER", str(exc)) from exc
        transceiver = FieldTransceiver(
            transceiver_id=transceiver_id, parent_chart_versions=versions,
            source_revision_ids=sources, context=normalized_context,
            input_ids=input_ids, output_ids=output_ids, observed=fixed,
            kernel=kernel, working_state=working_state,
        )
        records = tuple(
            transceiver if row.transceiver_id == transceiver_id else row for row in state.transceivers
        )
        if existing is None:
            records = (*records, transceiver)
        successor = state.with_transition(
            "transceiver-condensed",
            {"transceiver_id": transceiver_id, "parent_chart_versions": versions},
            transceivers=records,
        )
        return successor, _json_value({
            **receipt, "transceiver_id": transceiver_id,
            "parent_chart_versions": versions, "source_revision_ids": sources,
            "evidence_tick": state.logical_tick, "evidence_added": False,
        }, "condensation receipt")

    def advance_transceivers(
        self,
        state: AtlasState,
        *,
        stimuli: Mapping[str, Mapping[str, float]],
        context: Mapping[str, Any],
        ticks: int = 1,
        connections: Sequence[Mapping[str, str]] = (),
        force_full: bool = False,
    ) -> tuple[AtlasState, Mapping[str, Any]]:
        """Advance synchronous field-owned assemblies; connected ports have one tick delay."""
        if isinstance(ticks, bool) or not isinstance(ticks, int) or not 1 <= ticks <= 64:
            raise FieldIntelligenceError("WORK_CAPACITY", "transceiver ticks must be in 1..64")
        if not isinstance(force_full, bool) or not isinstance(stimuli, Mapping) or not isinstance(context, Mapping):
            raise FieldIntelligenceError("INVALID_TRANSCEIVER", "invalid stimulus, context, or full-mode flag")
        normalized_context = _json_value(dict(context), "transceiver context")
        if len(connections) > 512:
            raise FieldIntelligenceError("WORK_CAPACITY", "transceiver connections exceed 512")
        records = {row.transceiver_id: row for row in state.transceivers}
        selected = set(stimuli)
        links: list[tuple[str, str, str, str]] = []
        driven: set[tuple[str, str]] = set()
        for connection in connections:
            if not isinstance(connection, Mapping) or set(connection) != {"source", "output", "target", "input"}:
                raise FieldIntelligenceError("INVALID_TRANSCEIVER", "connection keys are not canonical")
            source, output, target, receiving = (
                _identifier(connection[key], f"connection {key}") for key in ("source", "output", "target", "input")
            )
            source_row, target_row = state.transceiver(source), state.transceiver(target)
            if output not in source_row.output_ids or receiving not in target_row.input_ids:
                raise FieldIntelligenceError("INVALID_TRANSCEIVER", "connection names a nonexistent port")
            source_spec, target_spec = state.variable(output), state.variable(receiving)
            if (source_spec.kind, source_spec.unit, source_spec.frame) != (
                target_spec.kind, target_spec.unit, target_spec.frame
            ):
                raise FieldIntelligenceError("PORT_TYPE_MISMATCH", "connected variables have incompatible types, units, or frames")
            if (target, receiving) in driven or receiving in stimuli.get(target, {}):
                raise FieldIntelligenceError("AMBIGUOUS_TRANSCEIVER", "a receiving port must have exactly one driver")
            driven.add((target, receiving))
            selected.update((source, target))
            links.append((source, output, target, receiving))
        if not selected:
            selected = {name for name, row in records.items() if row.matches(normalized_context)}
        if len(selected) * ticks > 4096:
            raise FieldIntelligenceError("WORK_CAPACITY", "transceiver tick work exceeds 4096 unit steps")
        inputs: dict[str, dict[str, float]] = {}
        for name in sorted(selected):
            row = state.transceiver(name)
            if not row.matches(normalized_context):
                raise FieldIntelligenceError(
                    "TRANSCEIVER_INAPPLICABLE", "transceiver is stale or its context does not match",
                    details={"transceiver_id": name, "reason": row.reason},
                )
            payload = stimuli.get(name, {})
            if not isinstance(payload, Mapping) or not set(payload).issubset(row.input_ids):
                raise FieldIntelligenceError("INVALID_TRANSCEIVER", "stimulus names an unknown receiving port")
            inputs[name] = {port: _finite(payload.get(port, 0.0), port) for port in row.input_ids}
            for port, value in inputs[name].items():
                if not state.variable(port).contains(value):
                    raise FieldIntelligenceError("OBSERVATION_OUT_OF_DOMAIN", "transceiver stimulus is outside its domain")
        if not selected:
            raise FieldIntelligenceError("TRANSCEIVER_INAPPLICABLE", "no transceiver applies to this context")
        steps: list[Mapping[str, Any]] = []
        latest: dict[str, Mapping[str, Any]] = {}
        for tick in range(ticks):
            before = {
                name: inspect_transceiver(records[name].kernel, records[name].working_state)
                for name in selected
            }
            routed = {name: dict(values) for name, values in inputs.items()}
            input_errors: dict[str, dict[str, float]] = {name: {} for name in selected}
            for source, output, target, receiving in links:
                source_receipt = before[source]
                value = _finite(source_receipt["values"][output], output)
                radius = _finite(source_receipt["error_bound"], "connected output error")
                if radius < 0 or not state.variable(receiving).contains(value, radius=radius):
                    raise FieldIntelligenceError("UNCERTIFIED_TRANSMISSION", "transmission leaves the receiving domain")
                routed[target][receiving] = value
                input_errors[target][receiving] = radius
            successors: dict[str, FieldTransceiver] = {}
            for name in sorted(selected):
                row = records[name]
                try:
                    working, receipt = advance_transceiver(
                        row.kernel, row.working_state, inputs=routed[name],
                        input_errors=input_errors[name], ticks=1, force_full=force_full,
                    )
                except (ValueError, TypeError, KeyError, OverflowError) as exc:
                    raise FieldIntelligenceError(
                        "TRANSCEIVER_NUMERICAL", str(exc), details={"transceiver_id": name}
                    ) from exc
                successors[name] = replace(row, working_state=working)
                latest[name] = receipt
                steps.append({"transceiver_id": name, "tick": tick + 1, **receipt})
            records.update(successors)
        successor = state.with_transition(
            "transceivers-advanced",
            {"transceiver_ids": sorted(selected), "ticks": ticks, "connections": links},
            transceivers=tuple(records[row.transceiver_id] for row in state.transceivers),
        )
        return successor, _json_value({
            "transceivers": latest, "steps": steps, "ticks": ticks,
            "connection_delay_ticks": 1, "evidence_tick": state.logical_tick,
            "evidence_added": False, "readout_kind": "temporal-prediction",
        }, "transceiver advance receipt")

    def reset_transceiver(
        self, state: AtlasState, *, transceiver_id: str
    ) -> tuple[AtlasState, Mapping[str, Any]]:
        """Start a new temporal episode without changing condensed knowledge."""
        row = state.transceiver(transceiver_id)
        if row.status != "active":
            raise FieldIntelligenceError("TRANSCEIVER_INAPPLICABLE", "stale transceiver must be recondensed")
        working_state = reset_transceiver_workspace(row.kernel)
        updated = replace(row, working_state=working_state)
        successor = state.with_transition(
            "transceiver-reset", {"transceiver_id": transceiver_id},
            transceivers=tuple(updated if old.transceiver_id == transceiver_id else old for old in state.transceivers),
        )
        return successor, _json_value({
            "transceiver_id": transceiver_id,
            **inspect_transceiver(updated.kernel, updated.working_state),
            "evidence_tick": state.logical_tick, "evidence_added": False,
        }, "transceiver reset receipt")

    def inspect_transceivers(self, state: AtlasState) -> Mapping[str, Any]:
        return _json_value({
            "state_sha256": state.state_sha256, "evidence_tick": state.logical_tick,
            "transceivers": {
                row.transceiver_id: {
                    "status": row.status, "reason": row.reason,
                    "input_ids": row.input_ids, "output_ids": row.output_ids,
                    "parent_chart_versions": row.parent_chart_versions,
                    "source_revision_ids": row.source_revision_ids,
                    "response": None if row.status != "active" else inspect_transceiver(row.kernel, row.working_state),
                }
                for row in state.transceivers
            },
        }, "transceiver inspection")

    def couple_temporal_transition(
        self,
        state: AtlasState,
        *,
        previous: TemporalField,
        current: TemporalField,
        evidence_tick: int,
        episode: Sequence[Mapping[str, str]] = (),
        admitted_step_offset: int = 0,
        evidence_event_id: str | None = None,
    ) -> tuple[ResonantWorkspace | None, Mapping[str, Any]]:
        """Couple admitted outcomes and categorical skill changes into the wave."""
        if (
            not isinstance(previous, TemporalField)
            or not isinstance(current, TemporalField)
            or previous.memory_id != current.memory_id
        ):
            raise FieldIntelligenceError(
                "INVALID_TEMPORAL",
                "temporal resonance coupling requires two revisions of one memory",
            )
        if (
            isinstance(admitted_step_offset, bool)
            or not isinstance(admitted_step_offset, int)
            or not 0 <= admitted_step_offset <= len(episode)
        ):
            raise FieldIntelligenceError(
                "INVALID_TEMPORAL",
                "admitted temporal step offset is out of range",
            )
        if len(episode) > admitted_step_offset and evidence_event_id is None:
            raise FieldIntelligenceError(
                "INVALID_TEMPORAL",
                "admitted temporal outcomes require one evidence event identity",
            )
        try:
            outcome_signals = (
                current.episode_pool_signals(
                    episode,
                    previous=previous,
                )[admitted_step_offset:]
                if episode
                else ()
            )
        except TemporalFieldError as exc:
            raise FieldIntelligenceError(
                "INVALID_TEMPORAL", str(exc)
            ) from exc

        formed = tuple(
            sorted(
                set(current.formed_skill_ids)
                - set(previous.formed_skill_ids)
            )
        )
        withdrawn = tuple(
            sorted(
                set(previous.formed_skill_ids)
                - set(current.formed_skill_ids)
            )
        )
        events: list[dict[str, Any]] = [
            {
                "event_kind": signal["event_kind"],
                "evidence_event_id": evidence_event_id,
                "step_index": signal["step_index"],
                "action": signal["action"],
                "observation": signal["observation"],
                "expected_by_predecessor": signal[
                    "expected_by_predecessor"
                ],
                "source_states": signal["source_states"],
                "destination_states": signal["destination_states"],
                "predecessor_source_states": signal[
                    "predecessor_source_states"
                ],
                "predecessor_destination_states": signal[
                    "predecessor_destination_states"
                ],
                "contributions": signal["contributions"],
                "signal_norm_before_normalization": signal[
                    "signal_norm_before_normalization"
                ],
                "pool_signal": signal["pool_signal"],
            }
            for signal in outcome_signals
        ]
        for event_kind, skill_id, source in sorted(
            [
                *[("formation", skill_id, current) for skill_id in formed],
                *[
                    ("withdrawal", skill_id, previous)
                    for skill_id in withdrawn
                ],
            ],
            key=lambda row: (row[1], row[0]),
        ):
            projection = dict(source.skill_pool_signal(skill_id))
            signal = [
                float(value) for value in projection["pool_signal"]
            ]
            if event_kind == "withdrawal":
                signal = [-value for value in signal]
            events.append({
                "event_kind": event_kind,
                "evidence_event_id": evidence_event_id,
                "skill_id": skill_id,
                "mapping": projection["mapping"],
                "supported_states": projection["supported_states"],
                "maximum_rank": projection["maximum_rank"],
                "pool_signal": signal,
            })

        active_count = sum(
            any(float(value) != 0.0 for value in event["pool_signal"])
            for event in events
        )
        event_work_budget = (
            _TEMPORAL_ADMISSION_WORK / active_count
            if active_count
            else 0.0
        )
        start_workspace = state.resonant_workspace
        if not active_count:
            for event in events:
                event["impulse"] = None
            return start_workspace, _json_value(
                {
                    "schema": "cassifi.temporal-resonance-coupling.v2",
                    "applied": False,
                    "memory_id": current.memory_id,
                    "formed_skills": list(formed),
                    "withdrawn_skills": list(withdrawn),
                    "admitted_step_count": len(episode) - admitted_step_offset,
                    "evidence_event_id": evidence_event_id,
                    "admission_work_budget": _TEMPORAL_ADMISSION_WORK,
                    "event_work_budget": 0.0,
                    "active_event_count": 0,
                    "total_applied_work": 0.0,
                    "events": events,
                    "start_workspace_state_sha256": (
                        None
                        if start_workspace is None
                        else start_workspace.state_sha256
                    ),
                    "end_workspace_state_sha256": (
                        None
                        if start_workspace is None
                        else start_workspace.state_sha256
                    ),
                    "evidence_tick": evidence_tick,
                },
                "temporal resonance coupling receipt",
            )

        workspace = start_workspace or initial_workspace()
        start_sha256 = workspace.state_sha256
        for event in events:
            signal = [
                float(value) for value in event["pool_signal"]
            ]
            if not any(value != 0.0 for value in signal):
                event["impulse"] = None
                continue
            workspace, impulse = apply_pool_impulse(
                workspace,
                pool_signal=signal,
                work_budget=event_work_budget,
                evidence_tick=evidence_tick,
                event_kind=event["event_kind"],
            )
            event["impulse"] = impulse
        total_applied_work = math.fsum(
            float(event["impulse"]["applied_work"])
            for event in events
            if event["impulse"] is not None
        )
        if total_applied_work > _TEMPORAL_ADMISSION_WORK + 1e-12:
            raise FieldIntelligenceError(
                "TEMPORAL_COUPLING_WORK",
                "temporal event coupling exceeded its admission work budget",
            )
        return workspace, _json_value(
            {
                "schema": "cassifi.temporal-resonance-coupling.v2",
                "applied": True,
                "memory_id": current.memory_id,
                "formed_skills": list(formed),
                "withdrawn_skills": list(withdrawn),
                "admitted_step_count": len(episode) - admitted_step_offset,
                "evidence_event_id": evidence_event_id,
                "admission_work_budget": _TEMPORAL_ADMISSION_WORK,
                "event_work_budget": event_work_budget,
                "active_event_count": active_count,
                "total_applied_work": total_applied_work,
                "events": events,
                "start_workspace_state_sha256": start_sha256,
                "end_workspace_state_sha256": workspace.state_sha256,
                "evidence_tick": evidence_tick,
            },
            "temporal resonance coupling receipt",
        )


    def advance(
        self,
        state: AtlasState,
        *,
        ticks: int = 1,
        source_enabled: bool = True,
    ) -> tuple[AtlasState, Mapping[str, Any]]:
        if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 1:
            raise FieldIntelligenceError("INVALID_RESONANCE", "ticks must be positive")
        workspace = state.resonant_workspace or initial_workspace()
        workspace, receipt = advance_workspace(
            workspace,
            ticks=ticks,
            source_enabled=source_enabled,
            quiet=False,
        )
        successor = state.with_transition(
            "resonance-advanced",
            {"ticks": ticks, "source_enabled": bool(source_enabled)},
            resonant_workspace=workspace,
        )
        return successor, _json_value(dict(receipt), "resonance receipt")
    def inspect_resonance(self, state: AtlasState) -> Mapping[str, Any]:
        workspace = state.resonant_workspace
        if workspace is None:
            return {"status": "uninitialized", "state_sha256": state.state_sha256}
        return _json_value(
            {
                **dict(inspect_workspace(workspace)),
                "status": "ready",
                "state_sha256": state.state_sha256,
                "workspace_state_sha256": workspace.state_sha256,
                "field_generation": state.generation,
                "evidence_tick": state.logical_tick,
                "field_time_step": workspace.profile.time_step,
                "profile": workspace.profile.as_dict(),
                "snapshot_age_seconds": 0.0,
            },
            "resonance inspection",
        )

    def _resonant_branch(
        self,
        state: AtlasState,
        workspace: ResonantWorkspace,
        charts: Sequence[RelationChart],
        observed: Mapping[str, float],
        requested: Sequence[str],
        constraints: Sequence[AffineConstraint],
        *,
        tolerance: float,
    ) -> BranchSolution:
        """Certify the retained wave; never replace it with a solved target."""
        order = self._variable_order(state, charts, observed, requested)
        versions = tuple((chart.chart_id, chart.version) for chart in charts)
        sources = tuple(sorted({source for chart in charts for source in chart.active_source_revisions()}))
        index = {name: position for position, name in enumerate(order)}
        common = workspace.common_coordinates()
        q = torch.tensor(
            [common[int(workspace.bindings[name]["port"])] for name in order],
            dtype=torch.float64,
        )
        precision = self._assemble_precision(order, charts)
        rows: list[list[float]] = []
        targets: list[float] = []
        boundary_response: list[list[float]] = []
        observed_order = tuple(observed)
        for name, value in observed.items():
            row = [0.0] * len(order)
            row[index[name]] = 1.0
            rows.append(row)
            targets.append(float(value))
            boundary_response.append([float(name == item) for item in observed_order])
        for name in order:
            spec = state.variable(name)
            if spec.kind == "constant":
                row = [0.0] * len(order)
                row[index[name]] = 1.0
                rows.append(row)
                targets.append(float(spec.constant))
                boundary_response.append([0.0] * len(observed_order))
        for constraint in constraints:
            rows.append([float(constraint.coefficients.get(name, 0.0)) for name in order])
            targets.append(float(constraint.target))
            boundary_response.append([0.0] * len(observed_order))
        correction = torch.zeros_like(q)
        response = torch.zeros((len(order), len(observed)), dtype=torch.float64)
        constraint_residual = 0.0
        if rows:
            matrix = torch.tensor(rows, dtype=torch.float64)
            target = torch.tensor(targets, dtype=torch.float64)
            _, singular, vh = torch.linalg.svd(matrix, full_matrices=True)
            threshold = max(matrix.shape) * torch.finfo(torch.float64).eps * float(singular.max())
            rank = int(torch.count_nonzero(singular > threshold))
            tangent = vh[rank:].T
            inverse = torch.linalg.pinv(matrix)
            boundary_error = target - matrix @ q
            correction = inverse @ boundary_error
            constraint_residual = float(torch.linalg.vector_norm(boundary_error))
            response = inverse @ torch.tensor(boundary_response, dtype=torch.float64)
        else:
            tangent = torch.eye(len(order), dtype=torch.float64)
        feasible_q = q + correction
        residual = tangent.T @ (precision @ feasible_q)
        residual_norm = float(torch.linalg.vector_norm(residual))
        error_bound = float(torch.linalg.vector_norm(correction))
        lower: float | None = None
        condition: float | None = None
        if tangent.shape[1]:
            reduced = tangent.T @ precision @ tangent
            eigenvalues = torch.linalg.eigvalsh(reduced)
            rounding = 64 * torch.finfo(torch.float64).eps * len(order) * float(eigenvalues.abs().max())
            lower = float(eigenvalues.min()) - rounding
            if lower <= 0:
                return self._failed_branch(
                    charts, order, observed, "underdetermined", ("uncertified-curvature",)
                )
            condition = float(eigenvalues.max()) / lower
            error_bound += residual_norm / lower
            # This solve is a boundary-sensitivity certificate, never a primal answer.
            response -= tangent @ torch.linalg.solve(reduced, tangent.T @ precision @ response)
        epistemic = all(
            name in observed
            or state.variable(name).kind == "constant"
            or any(name in chart.scope and chart.contributions for chart in charts)
            for name in order
        )
        finite = bool(torch.isfinite(q).all()) and math.isfinite(error_bound)
        settled = finite and error_bound <= tolerance * max(1.0, float(torch.linalg.vector_norm(q)))
        # Fixed inputs are boundary data, not inferred coordinates. Their
        # deviation from the retained wave remains in the certificate above.
        values = {}
        for name in order:
            spec = state.variable(name)
            values[name] = (
                float(observed[name]) if name in observed
                else float(spec.constant) if spec.kind == "constant"
                else float(q[index[name]])
            )
        in_domain = all(state.variable(name).contains(value) for name, value in values.items())
        obligations = tuple(
            reason
            for reason, failed in (
                ("numerical-residual", not settled),
                ("missing-evidence", not epistemic),
                ("constraint-residual", constraint_residual > tolerance),
                ("solution-out-of-domain", not in_domain),
            )
            if failed
        )
        return BranchSolution(
            branch_id=sha256_value({"charts": versions, "resonant": workspace.state_sha256}),
            status="infeasible" if not in_domain or constraint_residual > tolerance else ("settled" if settled else "exhausted"),
            variable_order=tuple(order),
            values=values,
            response=tuple(tuple(float(item) for item in row) for row in response),
            observed_order=observed_order,
            active_chart_versions=versions,
            source_revision_ids=sources,
            residual_norm=residual_norm,
            constraint_residual=constraint_residual,
            condition_number=condition,
            spectral_lower_bound=lower,
            solution_error_bound=error_bound,
            numerical_settled=settled,
            epistemically_supportable=epistemic,
            obligations=obligations,
        )

    def think(
        self,
        state: AtlasState,
        *,
        observed: Mapping[str, float],
        requested: Sequence[str],
        context: Mapping[str, Any] | None = None,
        constraints: Sequence[AffineConstraint] = (),
        valid_source_revision_ids: frozenset[str] | None = None,
        tolerance: float = 1e-8,
        max_iterations: int = 512,
        max_branches: int = 64,
        ticks: int = 64,
        query_id: str | None = None,
    ) -> tuple[AtlasState, QueryResult, Mapping[str, Any]]:
        if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 1:
            raise FieldIntelligenceError("INVALID_RESONANCE", "ticks must be positive")
        normalized_observed = {
            _identifier(name, "observed variable"): _finite(value, f"observed {name}")
            for name, value in observed.items()
        }
        normalized_requested = tuple(_identifier(name, "requested variable") for name in requested)
        if len(normalized_requested) != len(set(normalized_requested)):
            raise FieldIntelligenceError("INVALID_QUERY", "requested variables must be unique")
        for name in (*normalized_observed, *normalized_requested):
            state.variable(name)
        known_variables = {row.variable_id for row in state.variables}
        for constraint in constraints:
            if not isinstance(constraint, AffineConstraint):
                raise FieldIntelligenceError("INVALID_CONSTRAINT", "constraints must be affine constraints")
            unknown = set(constraint.coefficients) - known_variables
            if unknown:
                raise FieldIntelligenceError(
                    "INVALID_CONSTRAINT", "constraint references unknown variables",
                    details={"unknown": sorted(unknown)},
                )
        normalized_context = _json_value(dict(context or {}), "query context")
        charts = self._relevant_charts(
            state,
            frozenset(normalized_observed),
            frozenset(normalized_requested),
            normalized_context,
            valid_source_revision_ids,
        )
        base_workspace = state.resonant_workspace or initial_workspace()
        branch_charts = self._branches(charts, max_branches) if charts else ()
        ready_demand = (
            1.0
            if branch_charts
            and any(
                all(chart.contributions and chart.active_source_revisions() for chart in selected)
                for selected in branch_charts
            )
            else 0.0
        )
        try:
            body_workspace, body_receipt = advance_workspace(
                base_workspace,
                ticks=ticks,
                demand=ready_demand,
                source_enabled=True,
                quiet=False,
                max_iterations=max_iterations,
                tolerance=tolerance,
            )
            body_receipt_value = _canonical_diagnostics(dict(body_receipt), "resonance receipt")
        except Exception as exc:
            body_workspace = base_workspace
            body_receipt_value = _json_value(
                {
                    "accepted": False,
                    "error": type(exc).__name__,
                    "ticks": ticks,
                },
                "resonance failure receipt",
            )
        branch_workspaces: list[ResonantWorkspace] = []
        branch_receipts: list[Mapping[str, Any]] = []
        branch_rows: list[BranchSolution] = []
        resonance_receipts: list[Mapping[str, Any]] = [body_receipt_value]
        for selected_charts in branch_charts:
            try:
                problem = self._resonant_problem(
                    state, selected_charts, normalized_observed, constraints
                )
                inconsistent = self._inconsistent_constraint_residual(
                    problem, tolerance=tolerance
                )
                if inconsistent is not None:
                    branch = self._inconsistent_branch(
                        selected_charts,
                        self._variable_order(
                            state,
                            selected_charts,
                            normalized_observed,
                            normalized_requested,
                        ),
                        normalized_observed,
                        base_workspace,
                        inconsistent,
                    )
                    normalized_receipt = _json_value(
                        {
                            "accepted": False,
                            "error": "InconsistentConstraints",
                            "ticks": ticks,
                        },
                        "inconsistent constraint receipt",
                    )
                    branch_workspaces.append(base_workspace)
                else:
                    branch_workspace = base_workspace
                    if problem is not None:
                        required_ports = len(
                            set(branch_workspace.bindings) | set(problem.variable_ids)
                        )
                        if required_ports > branch_workspace.profile.port_count:
                            branch_workspace, _ = expand_resolution(
                                branch_workspace,
                                ports_per_pool=math.ceil(
                                    required_ports / branch_workspace.profile.pools
                                ),
                            )
                        branch_workspace = bind_workspace(branch_workspace, problem)
                    evolved_workspace, branch_receipt = advance_workspace(
                        branch_workspace,
                        problem=problem,
                        ticks=ticks,
                        demand=1.0,
                        source_enabled=True,
                        quiet=True,
                        max_iterations=max_iterations,
                        tolerance=tolerance,
                    )
                    branch = self._resonant_branch(
                        state,
                        evolved_workspace,
                        selected_charts,
                        normalized_observed,
                        normalized_requested,
                        constraints,
                        tolerance=tolerance,
                    )
                    normalized_receipt = _canonical_diagnostics(
                        dict(branch_receipt), "resonance receipt"
                    )
                    branch_workspaces.append(evolved_workspace)
            except Exception as exc:
                status = "infeasible" if constraints else (
                    "infeasible"
                    if isinstance(exc, FieldIntelligenceError)
                    and exc.code in {"INVALID_CONSTRAINT", "NUMERICAL_FAILURE"}
                    else "exhausted"
                )
                branch = self._failed_branch(
                    selected_charts,
                    self._variable_order(state, selected_charts, normalized_observed, normalized_requested),
                    normalized_observed,
                    status,
                    ("resonance-failure", type(exc).__name__),
                )
                normalized_receipt = _json_value(
                    {"accepted": False, "error": type(exc).__name__, "ticks": ticks},
                    "resonance failure receipt",
                )
                branch_workspaces.append(base_workspace)
            branch_receipts.append(normalized_receipt)
            resonance_receipts.append(normalized_receipt)
            branch_rows.append(branch)
        workspace = body_workspace
        working = replace(state, resonant_workspace=workspace)
        branches = tuple(branch_rows)
        if not branches:
            result = QueryResult(
                status="unsupported",
                state_sha256=state.state_sha256,
                field_generation=state.generation,
                branches=(),
                requested=normalized_requested,
                observed=normalized_observed,
                context=normalized_context,
                memory_unchanged=True,
            )
        else:
            viable = tuple(
                row for row in branches
                if row.numerical_settled and row.epistemically_supportable and row.status == "settled"
            )
            if not viable:
                status = "unresolved"
            elif len(viable) == 1:
                status = "supported"
            else:
                projected = {
                    tuple(round(row.values[name], 14) for name in normalized_requested)
                    for row in viable
                }
                status = "supported" if len(projected) == 1 else "alternatives"
            result = QueryResult(
                status=status,
                state_sha256=state.state_sha256,
                field_generation=state.generation,
                branches=branches,
                requested=normalized_requested,
                observed=normalized_observed,
                context=normalized_context,
                memory_unchanged=True,
            )
        effective_query_id = query_id or sha256_value(
            {
                "state_sha256": state.state_sha256,
                "observed": dict(normalized_observed),
                "requested": list(normalized_requested),
                "context": normalized_context,
            }
        )
        _identifier(effective_query_id, "query_id")
        receipt = _canonical_diagnostics(
            {
                "query_id": effective_query_id,
                "predecessor_state_sha256": state.state_sha256,
                "successor_workspace_sha256": workspace.state_sha256,
                "resonance": resonance_receipts,
                "branch_receipts": branch_receipts,
            },
            "checkpoint receipt",
        )
        result = replace(result, query_id=effective_query_id, checkpoint_receipt=receipt)
        record = {
            "query_id": effective_query_id,
            "status": "prepared",
            "frozen": False,
            "result": result.as_dict(),
            "branch_workspaces": [
                {
                    "workspace": item,
                    "state_sha256": item.state_sha256,
                    "page_sha256": hashlib.sha256(item.page_bytes).hexdigest(),
                }
                for item in branch_workspaces
            ],
            "branch_receipts": branch_receipts,
        }
        successor = working.with_transition(
            "query-prepared",
            {"query_id": effective_query_id, "status": result.status},
            prepared_queries=(
                *tuple(row for row in working.prepared_queries if row.get("query_id") != effective_query_id),
                record,
            ),
        )
        return successor, result, receipt

    def query_prepared(self, state: AtlasState, query_id: str) -> QueryResult:
        _identifier(query_id, "query_id")
        for row in state.prepared_queries:
            if row.get("query_id") == query_id:
                if row.get("status") != "prepared":
                    raise FieldIntelligenceError("QUERY_INVALIDATED", "prepared query was invalidated")
                result = QueryResult.from_dict(row["result"])
                if result.query_id != query_id or result.status not in {
                    "supported", "alternatives", "unresolved", "unsupported"
                }:
                    raise FieldIntelligenceError("INVALID_STATE", "prepared query dependency is inconsistent")
                for branch_result in result.branches:
                    active_sources: set[str] = set()
                    for chart_id, version in branch_result.active_chart_versions:
                        chart = state.chart(chart_id)
                        if chart.version != version:
                            raise FieldIntelligenceError(
                                "QUERY_INVALIDATED", "prepared query chart dependency changed"
                            )
                        active_sources.update(chart.active_source_revisions())
                    if not set(branch_result.source_revision_ids).issubset(active_sources):
                        raise FieldIntelligenceError(
                            "QUERY_INVALIDATED", "prepared query source dependency changed"
                        )
                _digest(result.state_sha256, "prepared result state digest")
                for branch in row.get("branch_workspaces", ()):
                    workspace = branch["workspace"]
                    if (
                        workspace.state_sha256 != branch["state_sha256"]
                        or hashlib.sha256(workspace.page_bytes).hexdigest() != branch["page_sha256"]
                    ):
                        raise FieldIntelligenceError("INVALID_STATE", "prepared branch dependency is corrupt")
                return result
        raise FieldIntelligenceError("QUERY_NOT_FOUND", f"unknown prepared query: {query_id}")

    def freeze_query(self, state: AtlasState, query_id: str) -> AtlasState:
        self.query_prepared(state, query_id)
        rows = tuple(
            {**row, "frozen": True} if row.get("query_id") == query_id else row
            for row in state.prepared_queries
        )
        return state.with_transition(
            "query-frozen",
            {"query_id": query_id},
            prepared_queries=rows,
            frozen_query_ids=frozenset((*state.frozen_query_ids, query_id)),
        )

    def invalidate_query(self, state: AtlasState, query_id: str, *, reason: str) -> AtlasState:
        _identifier(query_id, "query_id")
        _identifier(reason, "invalidation reason")
        found = False
        rows: list[Mapping[str, Any]] = []
        for row in state.prepared_queries:
            if row.get("query_id") == query_id:
                found = True
                rows.append({**row, "status": "invalidated", "reason": reason})
            else:
                rows.append(row)
        if not found:
            raise FieldIntelligenceError("QUERY_NOT_FOUND", f"unknown prepared query: {query_id}")
        return state.with_transition(
            "query-invalidated",
            {"query_id": query_id, "reason": reason},
            prepared_queries=tuple(rows),
        )


    def relax_block(
        self,
        state: AtlasState,
        *,
        values: Mapping[str, float],
        block: Sequence[str],
        context: Mapping[str, Any] | None = None,
        duration: float = 1.0,
    ) -> Mapping[str, Any]:
        if not block or len(set(block)) != len(block):
            raise FieldIntelligenceError("INVALID_BLOCK", "block must be nonempty and unique")
        duration = _finite(duration, "block duration", positive=True)
        normalized = {name: _finite(value, name) for name, value in values.items()}
        for name in normalized:
            state.variable(name)
        for name in block:
            state.variable(name)
            if name not in normalized:
                raise FieldIntelligenceError("INVALID_BLOCK", "block value is missing")
        context_value = _json_value(dict(context or {}), "block context")
        charts = self._relevant_charts(
            state,
            frozenset(normalized),
            frozenset(block),
            context_value,
            None,
        )
        order = self._variable_order(state, charts, normalized, block)
        if set(order) != set(normalized):
            raise FieldIntelligenceError(
                "INVALID_BLOCK", "values must cover the entire active local neighborhood"
            )
        hessian = self._assemble_precision(order, charts)
        index = {name: position for position, name in enumerate(order)}
        positions = torch.tensor([index[name] for name in block], dtype=torch.long)
        neighbors = torch.tensor(
            [index[name] for name in order if name not in set(block)], dtype=torch.long
        )
        current = torch.tensor([normalized[name] for name in order], dtype=torch.float64)
        local = hessian[positions[:, None], positions[None, :]]
        rhs = current[positions]
        if neighbors.numel():
            rhs -= duration * hessian[positions[:, None], neighbors[None, :]] @ current[neighbors]
        system = torch.eye(len(block), dtype=torch.float64) + duration * local
        updated = torch.linalg.solve(system, rhs)
        candidate = current.clone()
        candidate[positions] = updated
        delta = candidate - current
        decrement = float(delta @ delta / duration + 0.5 * delta @ hessian @ delta)
        residual = system @ updated - rhs
        return {
            "decrement": decrement,
            "memory_unchanged": state.state_sha256 == state.state_sha256,
            "residual_norm": float(torch.linalg.vector_norm(residual)),
            "values": {name: float(candidate[position]) for position, name in enumerate(order)},
        }

    def derive_schur_reduction(
        self,
        state: AtlasState,
        *,
        macro_id: str,
        boundary: Sequence[str],
        interior: Sequence[str],
        context: Mapping[str, Any] | None = None,
        linear: Mapping[str, float] | None = None,
        constant: float = 0.0,
    ) -> AtlasState:
        boundary_tuple = tuple(boundary)
        interior_tuple = tuple(interior)
        if (
            not boundary_tuple
            or len(set(boundary_tuple)) != len(boundary_tuple)
            or len(set(interior_tuple)) != len(interior_tuple)
            or set(boundary_tuple).intersection(interior_tuple)
        ):
            raise FieldIntelligenceError(
                "INVALID_REDUCTION",
                "boundary and interior variables must be unique, with a nonempty boundary disjoint from the interior",
            )
        for name in (*boundary_tuple, *interior_tuple):
            state.variable(name)
        unknown_linear = set(linear or {}) - set(boundary_tuple) - set(interior_tuple)
        if unknown_linear:
            raise FieldIntelligenceError(
                "INVALID_REDUCTION",
                "linear term references variables outside the reduction",
                details={"unknown": sorted(unknown_linear)},
            )
        context_value = _json_value(dict(context or {}), "reduction context")
        charts = self._relevant_charts(
            state,
            frozenset(boundary_tuple),
            frozenset(interior_tuple),
            context_value,
            None,
        )
        order = tuple((*boundary_tuple, *interior_tuple))
        if any(set(chart.scope) - set(order) for chart in charts):
            raise FieldIntelligenceError(
                "INVALID_REDUCTION",
                "reduction boundary must include every active neighbor of its interior",
            )
        hessian = self._assemble_precision(order, charts)
        b_size = len(boundary_tuple)
        h_bb = hessian[:b_size, :b_size]
        h_bi = hessian[:b_size, b_size:]
        h_ib = hessian[b_size:, :b_size]
        h_ii = hessian[b_size:, b_size:]
        linear_vector = torch.tensor(
            [float((linear or {}).get(name, 0.0)) for name in order], dtype=torch.float64
        )
        b_b = linear_vector[:b_size]
        b_i = linear_vector[b_size:]
        if interior_tuple:
            try:
                solve_hib = torch.linalg.solve(h_ii, h_ib)
                solve_bi = torch.linalg.solve(h_ii, b_i)
            except RuntimeError as exc:
                raise FieldIntelligenceError(
                    "INVALID_REDUCTION", "interior Hessian is not positive definite"
                ) from exc
            effective_h = h_bb - h_bi @ solve_hib
            effective_b = b_b - h_bi @ solve_bi
            effective_c = float(constant) - 0.5 * float(b_i @ solve_bi)
        else:
            effective_h = h_bb
            effective_b = b_b
            effective_c = float(constant)
        support = sorted(
            {row.event_id for chart in charts for row in chart.contributions}
        )
        macro = ExactReduction(
            macro_id=macro_id,
            version=1,
            boundary=boundary_tuple,
            interior=interior_tuple,
            hessian=tuple(tuple(float(item) for item in row) for row in effective_h),
            linear=tuple(float(item) for item in effective_b),
            constant=effective_c,
            parent_chart_versions=tuple((chart.chart_id, chart.version) for chart in charts),
            guards=tuple(
                guard
                for chart in charts
                for guard in chart.guards
            ),
            support_event_ids=tuple(support),
            expansion_variables=order,
        )
        if any(row.macro_id == macro_id for row in state.macros):
            previous = next(row for row in state.macros if row.macro_id == macro_id)
            macro = replace(macro, version=previous.version + 1)
            macros = self._replace_identified(state.macros, macro_id, macro, "macro_id")
        else:
            macros = (*state.macros, macro)
        return state.with_transition(
            "exact-reduction-derived",
            {"boundary": list(boundary_tuple), "macro_id": macro_id},
            macros=tuple(macros),
        )


__all__ = [
    "ARITHMETIC_PROFILE",
    "ATLAS_LEGACY_SCHEMA",
    "ATLAS_SCHEMA",
    "AssessmentRecord",
    "AtlasState",
    "BranchSolution",
    "ComputationRecord",
    "ExactReduction",
    "FieldAtlas",
    "FieldIntelligenceError",
    "FieldProgram",
    "FieldTransceiver",
    "Guard",
    "LanguageConstruction",
    "PlanRecord",
    "PlanSegment",
    "PredictionRecord",
    "PrimitiveStep",
    "QueryResult",
    "RelationChart",
    "SupportContribution",
    "VariableSpec",
    "canonical_json_bytes",
    "sha256_value",
]
