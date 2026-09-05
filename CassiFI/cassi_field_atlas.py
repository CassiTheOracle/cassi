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
from typing import Any, Final, Mapping, Never, Sequence

import torch
from torch import Tensor

from cassi_variational_field import VariationalField


ATLAS_SCHEMA: Final[str] = "cassifi.field-atlas.v1"
ARITHMETIC_PROFILE: Final[str] = "cpu-float64-reference.v1"
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
class AtlasState:
    generation: int = 0
    logical_tick: int = 0
    revocation_generation: int = 0
    variables: tuple[VariableSpec, ...] = ()
    charts: tuple[RelationChart, ...] = ()
    programs: tuple[FieldProgram, ...] = ()
    constructions: tuple[LanguageConstruction, ...] = ()
    macros: tuple[ExactReduction, ...] = ()
    predictions: tuple[PredictionRecord, ...] = ()
    plans: tuple[PlanRecord, ...] = ()
    computation_records: tuple[ComputationRecord, ...] = ()
    transition_log: tuple[Mapping[str, Any], ...] = ()
    _encoded: bytes = field(init=False, repr=False, compare=False)
    _state_sha256: str = field(init=False, repr=False, compare=False)
    schema: str = ATLAS_SCHEMA
    arithmetic_profile: str = ARITHMETIC_PROFILE

    def __post_init__(self) -> None:
        for name in (
            "variables",
            "charts",
            "programs",
            "constructions",
            "macros",
            "predictions",
            "plans",
            "computation_records",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        object.__setattr__(
            self,
            "transition_log",
            tuple(
                _json_value(dict(row), "transition record")
                for row in self.transition_log
            ),
        )
        if self.schema != ATLAS_SCHEMA or self.arithmetic_profile != ARITHMETIC_PROFILE:
            raise FieldIntelligenceError("INCOMPATIBLE_STATE", "field atlas schema is incompatible")
        for name in ("generation", "logical_tick", "revocation_generation"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise FieldIntelligenceError("INVALID_STATE", f"{name} must be nonnegative")
        collections = {
            "variable": [row.variable_id for row in self.variables],
            "chart": [row.chart_id for row in self.charts],
            "program": [row.program_id for row in self.programs],
            "construction": [row.construction_id for row in self.constructions],
            "macro": [row.macro_id for row in self.macros],
            "prediction": [row.prediction_id for row in self.predictions],
            "plan": [row.plan_id for row in self.plans],
            "computation": [row.record_id for row in self.computation_records],
        }
        for label, values in collections.items():
            if len(values) != len(set(values)):
                raise FieldIntelligenceError(
                    "INVALID_STATE", f"{label} identities must be unique"
                )
        variable_ids = set(collections["variable"])
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
        for row in self.transition_log:
            _json_value(dict(row), "transition record")
        encoded = canonical_json_bytes(self.as_dict())
        object.__setattr__(self, "_encoded", encoded)
        object.__setattr__(
            self, "_state_sha256", hashlib.sha256(encoded).hexdigest()
        )

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
        }
        return replace(
            self,
            generation=self.generation + 1,
            transition_log=(*self.transition_log, transition),
            **changes,
        )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "arithmetic_profile": self.arithmetic_profile,
            "charts": [row.as_dict() for row in self.charts],
            "computation_records": [row.as_dict() for row in self.computation_records],
            "constructions": [row.as_dict() for row in self.constructions],
            "generation": self.generation,
            "logical_tick": self.logical_tick,
            "macros": [row.as_dict() for row in self.macros],
            "plans": [row.as_dict() for row in self.plans],
            "predictions": [row.as_dict() for row in self.predictions],
            "programs": [row.as_dict() for row in self.programs],
            "revocation_generation": self.revocation_generation,
            "schema": self.schema,
            "transition_log": [_json_plain(row) for row in self.transition_log],
            "variables": [row.as_dict() for row in self.variables],
        }

    def encode(self) -> bytes:
        return self._encoded

    @classmethod
    def decode(cls, encoded: bytes) -> AtlasState:
        try:
            value = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FieldIntelligenceError("INVALID_STATE", "field checkpoint is unreadable") from exc
        if not isinstance(value, dict):
            raise FieldIntelligenceError("INVALID_STATE", "field checkpoint root must be an object")
        row = dict(value)
        row["variables"] = tuple(VariableSpec.from_dict(item) for item in row["variables"])
        row["charts"] = tuple(RelationChart.from_dict(item) for item in row["charts"])
        row["programs"] = tuple(FieldProgram.from_dict(item) for item in row["programs"])
        row["constructions"] = tuple(
            LanguageConstruction.from_dict(item) for item in row["constructions"]
        )
        row["macros"] = tuple(ExactReduction.from_dict(item) for item in row["macros"])
        row["predictions"] = tuple(
            PredictionRecord.from_dict(item) for item in row["predictions"]
        )
        row["plans"] = tuple(PlanRecord.from_dict(item) for item in row["plans"])
        row["computation_records"] = tuple(
            ComputationRecord.from_dict(item) for item in row["computation_records"]
        )
        row["transition_log"] = tuple(row["transition_log"])
        result = cls(**row)
        if result.encode() != encoded:
            raise FieldIntelligenceError(
                "NONCANONICAL_STATE", "field checkpoint is not canonical or exact-roundtrip"
            )
        return result


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
    residual_norm: float
    constraint_residual: float
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
    def __post_init__(self) -> None:
        object.__setattr__(self, "branches", tuple(self.branches))
        object.__setattr__(self, "requested", tuple(self.requested))
        object.__setattr__(
            self,
            "observed",
            _FrozenDict(
                {
                    _identifier(name, "observed variable"): _finite(
                        value, "observed value"
                    )
                    for name, value in self.observed.items()
                }
            ),
        )
        object.__setattr__(
            self, "context", _json_value(dict(self.context), "query context")
        )


    def as_dict(self) -> Mapping[str, Any]:
        return {
            "branches": [row.as_dict() for row in self.branches],
            "context": _json_plain(self.context),
            "field_generation": self.field_generation,
            "memory_unchanged": self.memory_unchanged,
            "observed": _json_plain(self.observed),
            "requested": list(self.requested),
            "state_sha256": self.state_sha256,
            "status": self.status,
        }


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
        return state.with_transition(
            "chart-replaced",
            {"chart_id": chart.chart_id, "previous_version": previous.version},
            charts=charts,
            macros=macros,
            predictions=predictions,
            plans=plans,
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
        return state.with_transition(
            "program-replaced",
            {"program_id": program.program_id, "previous_version": previous.version},
            programs=rows,
            constructions=constructions,
            predictions=predictions,
            plans=plans,
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
        return state.with_transition(
            "construction-replaced",
            {
                "construction_id": construction.construction_id,
                "previous_version": previous.version,
            },
            constructions=rows,
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
        successor = state.with_transition(
            "sources-revoked",
            {
                "affected_chart_ids": affected_charts,
                "source_revision_ids": sorted(targets),
            },
            logical_tick=tick,
            revocation_generation=revocation_generation,
            charts=tuple(charts),
            programs=programs,
            constructions=constructions,
            macros=macros,
            predictions=predictions,
            plans=plans,
        )
        return successor, {
            "affected_chart_ids": affected_charts,
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
    def _apply_precision(
        order: Sequence[str], charts: Sequence[RelationChart], vector: Tensor
    ) -> Tensor:
        index = {name: position for position, name in enumerate(order)}
        result = torch.zeros_like(vector)
        for chart in charts:
            positions = torch.tensor([index[name] for name in chart.scope], dtype=torch.long)
            local = vector[positions]
            result[positions] += chart.factor_weight * torch.linalg.solve(
                chart.covariance(), local
            )
        return result

    @staticmethod
    def _cg(
        apply: Any,
        rhs: Tensor,
        *,
        tolerance: float,
        max_iterations: int,
    ) -> tuple[Tensor, float, int]:
        value = torch.zeros_like(rhs)
        residual = rhs - apply(value)
        direction = residual.clone()
        rr = float(residual @ residual)
        rhs_norm = float(torch.linalg.vector_norm(rhs))
        target = tolerance * max(1.0, rhs_norm)
        if math.sqrt(rr) <= target:
            return value, math.sqrt(rr), 0
        for iteration in range(1, max_iterations + 1):
            applied = apply(direction)
            curvature = float(direction @ applied)
            if not math.isfinite(curvature) or curvature <= 0:
                raise FieldIntelligenceError(
                    "NUMERICAL_FAILURE", "matrix-free system is not positive definite"
                )
            alpha = rr / curvature
            value = value + alpha * direction
            residual = residual - alpha * applied
            next_rr = float(residual @ residual)
            if math.sqrt(next_rr) <= target:
                return value, math.sqrt(next_rr), iteration
            beta = next_rr / rr
            direction = residual + beta * direction
            rr = next_rr
        return value, math.sqrt(rr), max_iterations

    def _solve_branch(
        self,
        state: AtlasState,
        charts: Sequence[RelationChart],
        observed: Mapping[str, float],
        requested: Sequence[str],
        constraints: Sequence[AffineConstraint],
        *,
        method: str,
        tolerance: float,
        max_iterations: int,
    ) -> BranchSolution:
        order = self._variable_order(state, charts, observed, requested)
        index = {name: position for position, name in enumerate(order)}
        observed_all = dict(observed)
        for variable_id in order:
            spec = state.variable(variable_id)
            if spec.kind == "constant":
                assert spec.constant is not None
                if variable_id in observed_all and observed_all[variable_id] != spec.constant:
                    return self._failed_branch(
                        charts, order, observed, "infeasible", ("constant-conflict",)
                    )
                observed_all[variable_id] = spec.constant
        for variable_id, value in observed_all.items():
            if variable_id not in index:
                continue
            if not state.variable(variable_id).contains(value):
                return self._failed_branch(
                    charts, order, observed, "infeasible", ("observation-domain",)
                )
        if constraints:
            return self._solve_constrained(
                state,
                charts,
                order,
                observed,
                observed_all,
                constraints,
                tolerance=tolerance,
            )
        fixed = tuple(name for name in order if name in observed_all)
        free = tuple(name for name in order if name not in observed_all)
        boundary = torch.zeros(len(order), dtype=torch.float64)
        for name in fixed:
            boundary[index[name]] = observed_all[name]
        if not free:
            values = {name: float(boundary[index[name]]) for name in order}
            sources = sorted({source for chart in charts for source in chart.active_source_revisions()})
            versions = tuple((chart.chart_id, chart.version) for chart in charts)
            branch_id = sha256_value({"charts": versions, "modes": []})
            response = tuple(
                tuple(1.0 if name == observed_name else 0.0 for observed_name in observed)
                for name in order
            )
            return BranchSolution(
                branch_id=branch_id,
                status="settled",
                variable_order=order,
                values=values,
                response=response,
                observed_order=tuple(observed),
                active_chart_versions=versions,
                source_revision_ids=tuple(sources),
                residual_norm=0.0,
                constraint_residual=0.0,
                condition_number=1.0,
                spectral_lower_bound=None,
                solution_error_bound=0.0,
                numerical_settled=True,
                epistemically_supportable=all(
                    any(name in chart.scope and chart.contributions for chart in charts)
                    for name in requested
                ),
                obligations=(),
            )
        free_positions = torch.tensor([index[name] for name in free], dtype=torch.long)
        if method == "auto":
            method = "matrix-free" if len(order) > 32 else "direct"
        if method not in {"direct", "matrix-free"}:
            raise FieldIntelligenceError("INVALID_SOLVER", "solver method is unsupported")
        hessian: Tensor | None = None
        condition_number: float | None = None
        lower_bound: float | None = None
        iterations = 0
        response_residual_norms: list[float] = []
        response_rhs_norms: list[float] = []
        if method == "direct":
            hessian = self._assemble_precision(order, charts)
            free_hessian = hessian[free_positions[:, None], free_positions[None, :]]
            eigenvalues = torch.linalg.eigvalsh(free_hessian)
            lower_bound = float(eigenvalues.min())
            upper = float(eigenvalues.max())
            guard = 128 * torch.finfo(torch.float64).eps * max(1.0, upper) * len(free)
            if lower_bound <= guard:
                return self._failed_branch(
                    charts,
                    order,
                    observed,
                    "underdetermined",
                    ("numerical-nullspace",),
                )
            condition_number = upper / lower_bound
            rhs = -(hessian @ boundary)[free_positions]
            free_value = torch.linalg.solve(free_hessian, rhs)
            response_columns: list[Tensor] = []
            for observed_name in observed:
                unit = torch.zeros(len(order), dtype=torch.float64)
                unit[index[observed_name]] = 1.0
                response_rhs = -(hessian @ unit)[free_positions]
                column = torch.linalg.solve(free_hessian, response_rhs)
                response_columns.append(column)
                response_residual_norms.append(
                    float(
                        torch.linalg.vector_norm(
                            free_hessian @ column - response_rhs
                        )
                    )
                )
                response_rhs_norms.append(
                    float(torch.linalg.vector_norm(response_rhs))
                )
            residual = free_hessian @ free_value - rhs
        else:
            incidence: dict[str, float] = {name: 0.0 for name in free}
            upper_candidates: dict[str, float] = {name: 0.0 for name in free}
            for chart in charts:
                for name in chart.scope:
                    if name in incidence:
                        incidence[name] += chart.factor_weight / (
                            chart.ridge + chart.observation_norm_bound**2
                        )
                        upper_candidates[name] += chart.factor_weight / chart.ridge
            lower_bound = min(incidence.values(), default=0.0)
            if lower_bound <= 0:
                return self._failed_branch(
                    charts,
                    order,
                    observed,
                    "underdetermined",
                    ("numerical-nullspace",),
                )
            condition_number = max(upper_candidates.values()) / lower_bound

            def free_apply(value: Tensor) -> Tensor:
                full = torch.zeros(len(order), dtype=torch.float64)
                full[free_positions] = value
                return self._apply_precision(order, charts, full)[free_positions]

            rhs = -self._apply_precision(order, charts, boundary)[free_positions]
            free_value, _, iterations = self._cg(
                free_apply, rhs, tolerance=tolerance, max_iterations=max_iterations
            )
            response_columns = []
            for observed_name in observed:
                unit = torch.zeros(len(order), dtype=torch.float64)
                unit[index[observed_name]] = 1.0
                response_rhs = -self._apply_precision(
                    order, charts, unit
                )[free_positions]
                column, column_residual, used = self._cg(
                    free_apply,
                    response_rhs,
                    tolerance=tolerance,
                    max_iterations=max_iterations,
                )
                iterations = max(iterations, used)
                response_columns.append(column)
                response_residual_norms.append(column_residual)
                response_rhs_norms.append(
                    float(torch.linalg.vector_norm(response_rhs))
                )
            residual = free_apply(free_value) - rhs
        value = boundary.clone()
        value[free_positions] = free_value
        residual_norm = float(torch.linalg.vector_norm(residual))
        rhs_norm = float(torch.linalg.vector_norm(rhs))
        primal_settled = residual_norm <= tolerance * max(1.0, rhs_norm)
        responses_settled = all(
            response_residual <= tolerance * max(1.0, response_rhs_norm)
            for response_residual, response_rhs_norm in zip(
                response_residual_norms, response_rhs_norms, strict=True
            )
        )
        settled = primal_settled and responses_settled
        worst_residual = max((residual_norm, *response_residual_norms))
        error_bound = (
            worst_residual / lower_bound
            if lower_bound and lower_bound > 0
            else None
        )
        response_tensor = torch.zeros((len(order), len(observed)), dtype=torch.float64)
        for column_index, observed_name in enumerate(observed):
            response_tensor[index[observed_name], column_index] = 1.0
            if free:
                response_tensor[free_positions, column_index] = response_columns[column_index]
        values = {name: float(value[index[name]]) for name in order}
        if any(not state.variable(name).contains(item) for name, item in values.items()):
            return self._failed_branch(
                charts,
                order,
                observed,
                "infeasible",
                ("inferred-domain",),
            )
        sources = sorted({source for chart in charts for source in chart.active_source_revisions()})
        versions = tuple((chart.chart_id, chart.version) for chart in charts)
        mode_rows = sorted(
            (chart.mode_group, chart.mode)
            for chart in charts
            if chart.mode_group is not None
        )
        branch_id = sha256_value({"charts": versions, "modes": mode_rows})
        epistemic = all(
            any(name in chart.scope and chart.contributions for chart in charts)
            for name in requested
        )
        obligations: list[str] = []
        if not primal_settled:
            obligations.append("numerical-residual")
        if not responses_settled:
            obligations.append("response-residual")
        if not epistemic:
            obligations.append("missing-evidence")
        if method == "matrix-free" and iterations >= max_iterations and not settled:
            obligations.append("search-exhausted")
        return BranchSolution(
            branch_id=branch_id,
            status="settled" if settled else "exhausted",
            variable_order=order,
            values=values,
            response=tuple(tuple(float(item) for item in row) for row in response_tensor),
            observed_order=tuple(observed),
            active_chart_versions=versions,
            source_revision_ids=tuple(sources),
            residual_norm=residual_norm,
            constraint_residual=0.0,
            condition_number=condition_number,
            spectral_lower_bound=lower_bound,
            solution_error_bound=error_bound,
            numerical_settled=settled,
            epistemically_supportable=epistemic,
            obligations=tuple(obligations),
        )

    def _solve_constrained(
        self,
        state: AtlasState,
        charts: Sequence[RelationChart],
        order: Sequence[str],
        observed: Mapping[str, float],
        observed_all: Mapping[str, float],
        constraints: Sequence[AffineConstraint],
        *,
        tolerance: float,
    ) -> BranchSolution:
        index = {name: position for position, name in enumerate(order)}
        hessian = self._assemble_precision(order, charts)
        rows: list[Tensor] = []
        targets: list[float] = []
        observed_row: dict[str, int] = {}
        for name, value in observed_all.items():
            if name not in index:
                continue
            row = torch.zeros(len(order), dtype=torch.float64)
            row[index[name]] = 1.0
            observed_row[name] = len(rows)
            rows.append(row)
            targets.append(value)
        for constraint in constraints:
            unknown = set(constraint.coefficients) - set(order)
            if unknown:
                raise FieldIntelligenceError(
                    "INVALID_CONSTRAINT",
                    "constraint references variables outside the active problem",
                    details={"unknown": sorted(unknown)},
                )
            row = torch.zeros(len(order), dtype=torch.float64)
            for name, coefficient in constraint.coefficients.items():
                row[index[name]] = coefficient
            rows.append(row)
            targets.append(constraint.target)
        matrix = torch.stack(rows)
        target = torch.tensor(targets, dtype=torch.float64)
        rank = int(torch.linalg.matrix_rank(matrix))
        augmented = torch.cat((matrix, target[:, None]), dim=1)
        if int(torch.linalg.matrix_rank(augmented)) > rank:
            return self._failed_branch(
                charts, order, observed, "infeasible", ("inconsistent-constraints",)
            )
        if rank < matrix.shape[0]:
            keep: list[int] = []
            current = torch.empty((0, len(order)), dtype=torch.float64)
            current_rank = 0
            for row_index, row in enumerate(matrix):
                candidate = torch.cat((current, row[None, :]), dim=0)
                candidate_rank = int(torch.linalg.matrix_rank(candidate))
                if candidate_rank > current_rank:
                    keep.append(row_index)
                    current = candidate
                    current_rank = candidate_rank
            matrix = matrix[keep]
            target = target[keep]
            observed_row = {
                name: keep.index(row_index)
                for name, row_index in observed_row.items()
                if row_index in keep
            }
        zeros = torch.zeros((matrix.shape[0], matrix.shape[0]), dtype=torch.float64)
        kkt = torch.cat(
            (
                torch.cat((hessian, matrix.T), dim=1),
                torch.cat((matrix, zeros), dim=1),
            ),
            dim=0,
        )
        rhs = torch.cat((torch.zeros(len(order), dtype=torch.float64), target))
        try:
            solution = torch.linalg.solve(kkt, rhs)
        except RuntimeError:
            return self._failed_branch(
                charts, order, observed, "underdetermined", ("singular-constrained-system",)
            )
        value = solution[: len(order)]
        multipliers = solution[len(order) :]
        stationarity = hessian @ value + matrix.T @ multipliers
        constraint_residual = matrix @ value - target
        residual_norm = float(torch.linalg.vector_norm(stationarity))
        constraint_norm = float(torch.linalg.vector_norm(constraint_residual))
        scale = max(1.0, float(torch.linalg.vector_norm(rhs)))
        settled = max(residual_norm, constraint_norm) <= tolerance * scale
        response_tensor = torch.zeros((len(order), len(observed)), dtype=torch.float64)
        response_residual_norms: list[float] = []
        for column, name in enumerate(observed):
            if name not in observed_row:
                response_residual_norms.append(0.0)
                continue
            response_rhs = torch.zeros_like(rhs)
            response_rhs[len(order) + observed_row[name]] = 1.0
            response_solution = torch.linalg.solve(kkt, response_rhs)
            response_tensor[:, column] = response_solution[: len(order)]
            response_residual_norms.append(
                float(
                    torch.linalg.vector_norm(kkt @ response_solution - response_rhs)
                )
            )
        singular_values = torch.linalg.svdvals(kkt)
        minimum = float(singular_values.min())
        maximum = float(singular_values.max())
        condition = maximum / minimum if minimum > 0 else None
        combined_residual = math.hypot(residual_norm, constraint_norm)
        solution_error_bound = (
            max((combined_residual, *response_residual_norms)) / minimum
            if minimum > 0
            else None
        )
        response_settled = all(
            residual <= tolerance for residual in response_residual_norms
        )
        settled = settled and response_settled
        values = {name: float(value[position]) for position, name in enumerate(order)}
        if any(not state.variable(name).contains(item) for name, item in values.items()):
            return self._failed_branch(
                charts,
                order,
                observed,
                "infeasible",
                ("inferred-domain",),
            )
        sources = sorted({source for chart in charts for source in chart.active_source_revisions()})
        versions = tuple((chart.chart_id, chart.version) for chart in charts)
        branch_id = sha256_value(
            {
                "charts": versions,
                "constraints": [
                    {"coefficients": dict(row.coefficients), "target": row.target}
                    for row in constraints
                ],
                "modes": sorted(
                    (chart.mode_group, chart.mode)
                    for chart in charts
                    if chart.mode_group is not None
                ),
            }
        )
        epistemic = all(
            any(name in chart.scope and chart.contributions for chart in charts)
            for name in set(order) - set(observed_all)
        )
        obligations = tuple(
            item
            for item, failed in (
                ("numerical-residual", not settled),
                ("response-residual", not response_settled),
                ("missing-evidence", not epistemic),
            )
            if failed
        )
        return BranchSolution(
            branch_id=branch_id,
            status="settled" if settled else "exhausted",
            variable_order=tuple(order),
            values=values,
            response=tuple(tuple(float(item) for item in row) for row in response_tensor),
            observed_order=tuple(observed),
            active_chart_versions=versions,
            source_revision_ids=tuple(sources),
            residual_norm=residual_norm,
            constraint_residual=constraint_norm,
            condition_number=condition,
            spectral_lower_bound=None,
            solution_error_bound=solution_error_bound,
            numerical_settled=settled,
            epistemically_supportable=epistemic,
            obligations=obligations,
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
            residual_norm=math.inf,
            constraint_residual=math.inf if status == "infeasible" else 0.0,
            condition_number=None,
            spectral_lower_bound=None,
            solution_error_bound=None,
            numerical_settled=False,
            epistemically_supportable=False,
            obligations=obligations,
        )

    def query(
        self,
        state: AtlasState,
        *,
        observed: Mapping[str, float],
        requested: Sequence[str],
        context: Mapping[str, Any] | None = None,
        constraints: Sequence[AffineConstraint] = (),
        valid_source_revision_ids: frozenset[str] | None = None,
        method: str = "auto",
        tolerance: float = 1e-10,
        max_iterations: int = 512,
        max_branches: int = 32,
    ) -> QueryResult:
        if not requested or len(set(requested)) != len(requested):
            raise FieldIntelligenceError(
                "INVALID_QUERY", "requested variables must be nonempty and unique"
            )
        for variable_id in (*observed.keys(), *requested):
            state.variable(variable_id)
        normalized_observed = {
            name: _finite(value, name) for name, value in observed.items()
        }
        for name, value in normalized_observed.items():
            if not state.variable(name).contains(value):
                raise FieldIntelligenceError(
                    "OBSERVATION_OUT_OF_DOMAIN", f"{name} is outside its declared domain"
                )
        normalized_context = _json_value(dict(context or {}), "query context")
        tolerance = _finite(tolerance, "solver tolerance", positive=True)
        if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 1:
            raise FieldIntelligenceError("INVALID_SOLVER", "max_iterations must be positive")
        if isinstance(max_branches, bool) or not isinstance(max_branches, int) or max_branches < 1:
            raise FieldIntelligenceError("INVALID_QUERY", "max_branches must be positive")
        before = state.state_sha256
        charts = self._relevant_charts(
            state,
            frozenset(normalized_observed),
            frozenset(requested),
            normalized_context,
            valid_source_revision_ids,
        )
        if not charts:
            return QueryResult(
                status="unsupported",
                state_sha256=before,
                field_generation=state.generation,
                branches=(),
                requested=tuple(requested),
                observed=normalized_observed,
                context=normalized_context,
                memory_unchanged=state.state_sha256 == before,
            )
        branches = tuple(
            self._solve_branch(
                state,
                branch_charts,
                normalized_observed,
                requested,
                constraints,
                method=method,
                tolerance=tolerance,
                max_iterations=max_iterations,
            )
            for branch_charts in self._branches(charts, max_branches)
        )
        viable = tuple(
            row
            for row in branches
            if row.numerical_settled and row.epistemically_supportable
        )
        if not viable:
            status = "unresolved"
        elif len(viable) == 1:
            status = "supported"
        else:
            projected = {
                tuple(round(row.values[name], 14) for name in requested) for row in viable
            }
            status = "supported" if len(projected) == 1 else "alternatives"
        return QueryResult(
            status=status,
            state_sha256=before,
            field_generation=state.generation,
            branches=branches,
            requested=tuple(requested),
            observed=normalized_observed,
            context=normalized_context,
            memory_unchanged=state.state_sha256 == before,
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
    "ATLAS_SCHEMA",
    "AffineConstraint",
    "AssessmentRecord",
    "AtlasState",
    "BranchSolution",
    "ComputationRecord",
    "ExactReduction",
    "FieldAtlas",
    "FieldIntelligenceError",
    "FieldProgram",
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
