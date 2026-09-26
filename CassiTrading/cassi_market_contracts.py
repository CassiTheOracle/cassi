"""Canonical typed contracts for the Cassi market intelligence system.

These contracts are deliberately boring: immutable dataclasses, deterministic
JSON documents, and fail-closed validation.  They are the shared spine between
historical evidence, the field-owned capability layer, synthesized programs,
policies, and checkpoint lineage.

The contracts do not learn, rank, or execute anything.  They make ownership,
provenance, availability, and identity explicit so those behaviors can be
implemented by the field and fixed kernels without parallel hidden state.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


CONTRACTS_SCHEMA = "cassi.market-contracts.v1"
EVENT_SCHEMA = "cassi.market-event.v1"
OBSERVATION_SCHEMA = "cassi.market-observation.v1"
SKILL_SCHEMA = "cassi.market-skill.v1"
HYPOTHESIS_SCHEMA = "cassi.market-hypothesis.v1"
PROGRAM_SCHEMA = "cassi.market-program.v1"
REGIME_SCHEMA = "cassi.market-regime.v1"
PREDICTION_SCHEMA = "cassi.market-prediction.v1"
OUTCOME_SCHEMA = "cassi.market-outcome.v1"
POLICY_SCHEMA = "cassi.market-policy.v1"
SPLIT_SCHEMA = "cassi.market-split-manifest.v1"
CHECKPOINT_SCHEMA = "cassi.market-checkpoint.v1"

_VALID_HYPOTHESIS_STATUSES = frozenset(
    {
        "proposed",
        "supported",
        "partially-supported",
        "contradicted",
        "unresolved",
        "inapplicable",
        "revoked",
    }
)
_VALID_MODES = frozenset({"research", "shadow", "authorized"})


class ContractError(ValueError):
    """A canonical market contract is malformed or internally inconsistent."""


def canonical_bytes(value: Any) -> bytes:
    """Serialize JSON-compatible contract data with stable bytes."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError("contract contains non-canonical JSON data") from exc


def digest_value(value: Any) -> str:
    """Return the SHA-256 digest of a canonical JSON-compatible value."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be nonempty text")
    return value


def _texts(name: str, values: Sequence[Any], *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise ContractError(f"{name} must be a sequence")
    result = tuple(_text(f"{name}[{index}]", value) for index, value in enumerate(values))
    if not allow_empty and not result:
        raise ContractError(f"{name} cannot be empty")
    return result


def _mapping(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be an object")
    result = dict(value)
    canonical_bytes(result)
    return result


def _finite_number(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ContractError(f"{name} must be finite")
    return result


def _document(schema: str, values: Mapping[str, Any]) -> dict[str, Any]:
    result = {"schema": schema}
    result.update(values)
    return result


class _Document:
    """Mixin shared by immutable contract documents."""

    def as_dict(self) -> dict[str, Any]:  # pragma: no cover - abstract protocol
        raise NotImplementedError

    @property
    def content_sha256(self) -> str:
        return digest_value(self.as_dict())


@dataclass(frozen=True, slots=True)
class Event(_Document):
    event_id: str
    source_id: str
    source_revision: str
    observed_at: str
    available_at: str
    event_type: str
    subject_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    units: Mapping[str, str] = field(default_factory=dict)
    coordinate_frame: str = "raw"
    missingness: Mapping[str, Any] = field(default_factory=dict)
    uncertainty: Mapping[str, Any] = field(default_factory=dict)
    source_span: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("event_id", "source_id", "source_revision", "observed_at", "available_at", "event_type", "coordinate_frame"):
            _text(name, getattr(self, name))
        _texts("subject_ids", self.subject_ids)
        _mapping("payload", self.payload)
        units = _mapping("units", self.units)
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in units.items()):
            raise ContractError("units must map text names to text units")
        _mapping("missingness", self.missingness)
        _mapping("uncertainty", self.uncertainty)
        _mapping("source_span", self.source_span)

    def as_dict(self) -> dict[str, Any]:
        return _document(
            EVENT_SCHEMA,
            {
                "event_id": self.event_id,
                "source_id": self.source_id,
                "source_revision": self.source_revision,
                "observed_at": self.observed_at,
                "available_at": self.available_at,
                "event_type": self.event_type,
                "subject_ids": list(self.subject_ids),
                "payload": dict(self.payload),
                "units": dict(self.units),
                "coordinate_frame": self.coordinate_frame,
                "missingness": dict(self.missingness),
                "uncertainty": dict(self.uncertainty),
                "source_span": dict(self.source_span),
            },
        )


@dataclass(frozen=True, slots=True)
class DerivedObservation(_Document):
    observation_id: str
    operator_id: str
    operator_version: str
    input_event_ids: tuple[str, ...]
    input_digests: tuple[str, ...]
    parameters: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    value: Any
    units: Mapping[str, str]
    valid_from: str
    valid_until: str | None = None

    def __post_init__(self) -> None:
        for name in ("observation_id", "operator_id", "operator_version", "valid_from"):
            _text(name, getattr(self, name))
        if self.valid_until is not None:
            _text("valid_until", self.valid_until)
        event_ids = _texts("input_event_ids", self.input_event_ids, allow_empty=False)
        digests = _texts("input_digests", self.input_digests, allow_empty=False)
        if len(event_ids) != len(digests):
            raise ContractError("input event IDs and digests must have equal length")
        _mapping("parameters", self.parameters)
        _mapping("output_schema", self.output_schema)
        units = _mapping("units", self.units)
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in units.items()):
            raise ContractError("units must map text names to text units")
        canonical_bytes(self.value)

    def as_dict(self) -> dict[str, Any]:
        return _document(
            OBSERVATION_SCHEMA,
            {
                "observation_id": self.observation_id,
                "operator_id": self.operator_id,
                "operator_version": self.operator_version,
                "input_event_ids": list(self.input_event_ids),
                "input_digests": list(self.input_digests),
                "parameters": dict(self.parameters),
                "output_schema": dict(self.output_schema),
                "value": self.value,
                "units": dict(self.units),
                "valid_from": self.valid_from,
                "valid_until": self.valid_until,
            },
        )


@dataclass(frozen=True, slots=True)
class Skill(_Document):
    skill_id: str
    title: str
    domains: tuple[str, ...]
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    source_program: str
    canonical_ast: Mapping[str, Any]
    verification_cases: tuple[Mapping[str, Any], ...]
    support_roots: tuple[str, ...] = ()
    applicability_guards: tuple[str, ...] = ()
    known_failures: tuple[str, ...] = ()
    resource_budget: Mapping[str, Any] = field(default_factory=dict)
    revision_id: str = "initial"

    def __post_init__(self) -> None:
        for name in ("skill_id", "title", "source_program", "revision_id"):
            _text(name, getattr(self, name))
        _texts("domains", self.domains, allow_empty=False)
        _mapping("input_schema", self.input_schema)
        _mapping("output_schema", self.output_schema)
        _mapping("canonical_ast", self.canonical_ast)
        if not isinstance(self.verification_cases, (tuple, list)) or not self.verification_cases:
            raise ContractError("verification_cases cannot be empty")
        for index, case in enumerate(self.verification_cases):
            _mapping(f"verification_cases[{index}]", case)
        _texts("support_roots", self.support_roots)
        _texts("applicability_guards", self.applicability_guards)
        _texts("known_failures", self.known_failures)
        _mapping("resource_budget", self.resource_budget)

    def as_dict(self) -> dict[str, Any]:
        return _document(
            SKILL_SCHEMA,
            {
                "skill_id": self.skill_id,
                "title": self.title,
                "domains": list(self.domains),
                "input_schema": dict(self.input_schema),
                "output_schema": dict(self.output_schema),
                "source_program": self.source_program,
                "canonical_ast": dict(self.canonical_ast),
                "verification_cases": [dict(case) for case in self.verification_cases],
                "support_roots": list(self.support_roots),
                "applicability_guards": list(self.applicability_guards),
                "known_failures": list(self.known_failures),
                "resource_budget": dict(self.resource_budget),
                "revision_id": self.revision_id,
            },
        )


@dataclass(frozen=True, slots=True)
class Hypothesis(_Document):
    hypothesis_id: str
    claim: str
    target_schema: Mapping[str, Any]
    expected_direction_or_outcome: Mapping[str, Any]
    applicable_context: Mapping[str, Any]
    assumptions: tuple[str, ...]
    candidate_program_ids: tuple[str, ...]
    evidence_roots: tuple[str, ...]
    disconfirming_observations: tuple[str, ...] = ()
    status: str = "proposed"

    def __post_init__(self) -> None:
        for name in ("hypothesis_id", "claim", "status"):
            _text(name, getattr(self, name))
        if self.status not in _VALID_HYPOTHESIS_STATUSES:
            raise ContractError(f"unknown hypothesis status: {self.status}")
        for name in ("target_schema", "expected_direction_or_outcome", "applicable_context"):
            _mapping(name, getattr(self, name))
        _texts("assumptions", self.assumptions)
        _texts("candidate_program_ids", self.candidate_program_ids)
        _texts("evidence_roots", self.evidence_roots)
        _texts("disconfirming_observations", self.disconfirming_observations)

    def as_dict(self) -> dict[str, Any]:
        return _document(
            HYPOTHESIS_SCHEMA,
            {
                "hypothesis_id": self.hypothesis_id,
                "claim": self.claim,
                "target_schema": dict(self.target_schema),
                "expected_direction_or_outcome": dict(self.expected_direction_or_outcome),
                "applicable_context": dict(self.applicable_context),
                "assumptions": list(self.assumptions),
                "candidate_program_ids": list(self.candidate_program_ids),
                "evidence_roots": list(self.evidence_roots),
                "disconfirming_observations": list(self.disconfirming_observations),
                "status": self.status,
            },
        )


@dataclass(frozen=True, slots=True)
class Program(_Document):
    program_id: str
    parent_ids: tuple[str, ...]
    source: str
    canonical_ast: Mapping[str, Any]
    typed_inputs: Mapping[str, Any]
    typed_outputs: Mapping[str, Any]
    guards: tuple[str, ...]
    state_ports: Mapping[str, Any]
    resource_budget: Mapping[str, Any]
    evidence_roots: tuple[str, ...]
    skill_dependencies: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("program_id", "source"):
            _text(name, getattr(self, name))
        _texts("parent_ids", self.parent_ids)
        _mapping("canonical_ast", self.canonical_ast)
        _mapping("typed_inputs", self.typed_inputs)
        _mapping("typed_outputs", self.typed_outputs)
        _texts("guards", self.guards)
        _mapping("state_ports", self.state_ports)
        budget = _mapping("resource_budget", self.resource_budget)
        for key, value in budget.items():
            if isinstance(value, bool):
                raise ContractError(f"resource budget {key} cannot be boolean")
            if isinstance(value, (int, float)):
                _finite_number(f"resource_budget.{key}", value)
        _texts("evidence_roots", self.evidence_roots)
        _texts("skill_dependencies", self.skill_dependencies)

    def as_dict(self) -> dict[str, Any]:
        return _document(
            PROGRAM_SCHEMA,
            {
                "program_id": self.program_id,
                "parent_ids": list(self.parent_ids),
                "source": self.source,
                "canonical_ast": dict(self.canonical_ast),
                "typed_inputs": dict(self.typed_inputs),
                "typed_outputs": dict(self.typed_outputs),
                "guards": list(self.guards),
                "state_ports": dict(self.state_ports),
                "resource_budget": dict(self.resource_budget),
                "evidence_roots": list(self.evidence_roots),
                "skill_dependencies": list(self.skill_dependencies),
            },
        )


@dataclass(frozen=True, slots=True)
class Regime(_Document):
    regime_id: str
    state_variables: Mapping[str, Any]
    applicability_guards: tuple[str, ...]
    supporting_observations: tuple[str, ...]
    competing_regimes: tuple[str, ...]
    transition_programs: tuple[str, ...]
    uncertainty: Mapping[str, Any]
    revision_id: str = "initial"

    def __post_init__(self) -> None:
        for name in ("regime_id", "revision_id"):
            _text(name, getattr(self, name))
        _mapping("state_variables", self.state_variables)
        _texts("applicability_guards", self.applicability_guards)
        _texts("supporting_observations", self.supporting_observations)
        _texts("competing_regimes", self.competing_regimes)
        _texts("transition_programs", self.transition_programs)
        _mapping("uncertainty", self.uncertainty)

    def as_dict(self) -> dict[str, Any]:
        return _document(
            REGIME_SCHEMA,
            {
                "regime_id": self.regime_id,
                "state_variables": dict(self.state_variables),
                "applicability_guards": list(self.applicability_guards),
                "supporting_observations": list(self.supporting_observations),
                "competing_regimes": list(self.competing_regimes),
                "transition_programs": list(self.transition_programs),
                "uncertainty": dict(self.uncertainty),
                "revision_id": self.revision_id,
            },
        )


@dataclass(frozen=True, slots=True)
class Prediction(_Document):
    prediction_id: str
    predecessor_field_sha256: str
    policy_id: str
    program_id: str
    input_event_ids: tuple[str, ...]
    available_at: str
    predicted_outcome: Mapping[str, Any]
    alternatives: tuple[Mapping[str, Any], ...]
    cost_expectation: Mapping[str, Any]
    risk_expectation: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in ("prediction_id", "predecessor_field_sha256", "policy_id", "program_id", "available_at"):
            _text(name, getattr(self, name))
        _texts("input_event_ids", self.input_event_ids, allow_empty=False)
        _mapping("predicted_outcome", self.predicted_outcome)
        if not isinstance(self.alternatives, (tuple, list)):
            raise ContractError("alternatives must be a sequence")
        for index, alternative in enumerate(self.alternatives):
            _mapping(f"alternatives[{index}]", alternative)
        _mapping("cost_expectation", self.cost_expectation)
        _mapping("risk_expectation", self.risk_expectation)

    def as_dict(self) -> dict[str, Any]:
        return _document(
            PREDICTION_SCHEMA,
            {
                "prediction_id": self.prediction_id,
                "predecessor_field_sha256": self.predecessor_field_sha256,
                "policy_id": self.policy_id,
                "program_id": self.program_id,
                "input_event_ids": list(self.input_event_ids),
                "available_at": self.available_at,
                "predicted_outcome": dict(self.predicted_outcome),
                "alternatives": [dict(alternative) for alternative in self.alternatives],
                "cost_expectation": dict(self.cost_expectation),
                "risk_expectation": dict(self.risk_expectation),
            },
        )


@dataclass(frozen=True, slots=True)
class Outcome(_Document):
    outcome_id: str
    prediction_id: str
    observed_at: str
    realized_outcome: Mapping[str, Any]
    execution_trace: Mapping[str, Any]
    attribution: Mapping[str, Any]
    cost_vector: Mapping[str, Any]
    source_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("outcome_id", "prediction_id", "observed_at"):
            _text(name, getattr(self, name))
        for name in ("realized_outcome", "execution_trace", "attribution", "cost_vector"):
            _mapping(name, getattr(self, name))
        _texts("source_event_ids", self.source_event_ids, allow_empty=False)

    def as_dict(self) -> dict[str, Any]:
        return _document(
            OUTCOME_SCHEMA,
            {
                "outcome_id": self.outcome_id,
                "prediction_id": self.prediction_id,
                "observed_at": self.observed_at,
                "realized_outcome": dict(self.realized_outcome),
                "execution_trace": dict(self.execution_trace),
                "attribution": dict(self.attribution),
                "cost_vector": dict(self.cost_vector),
                "source_event_ids": list(self.source_event_ids),
            },
        )


@dataclass(frozen=True, slots=True)
class Policy(_Document):
    policy_id: str
    regime_bindings: Mapping[str, str]
    program_bindings: Mapping[str, str]
    portfolio_controller: Mapping[str, Any]
    execution_controller: Mapping[str, Any]
    abstention_rules: tuple[str, ...]
    risk_limits: Mapping[str, Any]
    applicability: Mapping[str, Any]
    support_roots: tuple[str, ...]

    def __post_init__(self) -> None:
        _text("policy_id", self.policy_id)
        for name in ("regime_bindings", "program_bindings"):
            bindings = _mapping(name, getattr(self, name))
            if any(not isinstance(key, str) or not isinstance(value, str) for key, value in bindings.items()):
                raise ContractError(f"{name} must map text keys to text IDs")
        for name in ("portfolio_controller", "execution_controller", "risk_limits", "applicability"):
            _mapping(name, getattr(self, name))
        _texts("abstention_rules", self.abstention_rules)
        _texts("support_roots", self.support_roots)

    def as_dict(self) -> dict[str, Any]:
        return _document(
            POLICY_SCHEMA,
            {
                "policy_id": self.policy_id,
                "regime_bindings": dict(self.regime_bindings),
                "program_bindings": dict(self.program_bindings),
                "portfolio_controller": dict(self.portfolio_controller),
                "execution_controller": dict(self.execution_controller),
                "abstention_rules": list(self.abstention_rules),
                "risk_limits": dict(self.risk_limits),
                "applicability": dict(self.applicability),
                "support_roots": list(self.support_roots),
            },
        )


@dataclass(frozen=True, slots=True)
class SplitManifest(_Document):
    manifest_id: str
    availability_cutoff: str
    partitions: Mapping[str, tuple[str, ...]]
    source_digests: Mapping[str, str]
    policy: str = "available_at"

    def __post_init__(self) -> None:
        _text("manifest_id", self.manifest_id)
        _text("availability_cutoff", self.availability_cutoff)
        _text("policy", self.policy)
        partitions = _mapping("partitions", self.partitions)
        seen: set[str] = set()
        for name, event_ids in partitions.items():
            _text("partition name", name)
            ids = _texts(f"partitions.{name}", event_ids)
            overlap = seen.intersection(ids)
            if overlap:
                raise ContractError(f"event IDs overlap partitions: {sorted(overlap)}")
            seen.update(ids)
        digests = _mapping("source_digests", self.source_digests)
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in digests.items()):
            raise ContractError("source_digests must map text IDs to text digests")

    def as_dict(self) -> dict[str, Any]:
        return _document(
            SPLIT_SCHEMA,
            {
                "manifest_id": self.manifest_id,
                "availability_cutoff": self.availability_cutoff,
                "partitions": {key: list(value) for key, value in self.partitions.items()},
                "source_digests": dict(self.source_digests),
                "policy": self.policy,
            },
        )


@dataclass(frozen=True, slots=True)
class CheckpointManifest(_Document):
    checkpoint_id: str
    predecessor_field_sha256: str | None
    field_sha256: str
    evidence_root: str
    program_root: str
    policy_root: str
    authority_generation: str
    operation_id: str
    resource_counters: Mapping[str, Any]
    recovery_envelope: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in ("checkpoint_id", "field_sha256", "evidence_root", "program_root", "policy_root", "authority_generation", "operation_id"):
            _text(name, getattr(self, name))
        if self.predecessor_field_sha256 is not None:
            _text("predecessor_field_sha256", self.predecessor_field_sha256)
        _mapping("resource_counters", self.resource_counters)
        _mapping("recovery_envelope", self.recovery_envelope)

    def as_dict(self) -> dict[str, Any]:
        return _document(
            CHECKPOINT_SCHEMA,
            {
                "checkpoint_id": self.checkpoint_id,
                "predecessor_field_sha256": self.predecessor_field_sha256,
                "field_sha256": self.field_sha256,
                "evidence_root": self.evidence_root,
                "program_root": self.program_root,
                "policy_root": self.policy_root,
                "authority_generation": self.authority_generation,
                "operation_id": self.operation_id,
                "resource_counters": dict(self.resource_counters),
                "recovery_envelope": dict(self.recovery_envelope),
            },
        )


@dataclass(frozen=True, slots=True)
class Authority(_Document):
    mode: str
    objective_id: str
    permission_generation: str
    revocation_generation: str
    venue_limits: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode not in _VALID_MODES:
            raise ContractError(f"unknown authority mode: {self.mode}")
        for name in ("objective_id", "permission_generation", "revocation_generation"):
            _text(name, getattr(self, name))
        _mapping("venue_limits", self.venue_limits)

    def as_dict(self) -> dict[str, Any]:
        return _document(
            CONTRACTS_SCHEMA,
            {
                "mode": self.mode,
                "objective_id": self.objective_id,
                "permission_generation": self.permission_generation,
                "revocation_generation": self.revocation_generation,
                "venue_limits": dict(self.venue_limits),
            },
        )


__all__ = [
    "Authority",
    "CHECKPOINT_SCHEMA",
    "CONTRACTS_SCHEMA",
    "ContractError",
    "CheckpointManifest",
    "DerivedObservation",
    "Event",
    "EVENT_SCHEMA",
    "HYPOTHESIS_SCHEMA",
    "Hypothesis",
    "OBSERVATION_SCHEMA",
    "Outcome",
    "PREDICTION_SCHEMA",
    "POLICY_SCHEMA",
    "PROGRAM_SCHEMA",
    "Prediction",
    "Policy",
    "Program",
    "REGIME_SCHEMA",
    "Regime",
    "SKILL_SCHEMA",
    "SPLIT_SCHEMA",
    "Skill",
    "SplitManifest",
    "canonical_bytes",
    "digest_value",
]
