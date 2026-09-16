from __future__ import annotations

"""Cognitive operations whose learned content remains in one field atlas."""

import json
import math
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence, cast

from cassi_field_regions import (
    SEMANTIC_ANSWER_STATUSES,
    SEMANTIC_EPISTEMIC_KINDS,
    SEMANTIC_RECORD_KINDS,
    KernelResult,
    RegionalFieldError,
    SemanticRef,
    canonical_semantic_record,
    make_semantic_record,
    resolve_semantic_record,
    semantic_record_ref,
)
from cassi_field_program import (
    MECHANISM_STEP_KERNEL,
    MECHANISM_STEP_MAX_WORK,
    SEMANTIC_MECHANISM_KINDS,
    SEMANTIC_REPRESENTATION_SCHEMA,
    apply_semantic_representation_edits,
    canonical_semantic_representation_edits,
    canonical_semantic_program_payload,
    execute_semantic_program,
    semantic_program_payload,
)

import torch

from cassi_field_atlas import (
    AssessmentRecord,
    AtlasState,
    BranchSolution,
    ComputationRecord,
    FieldAtlas,
    FieldIntelligenceError,
    FieldProgram,
    Guard,
    LanguageConstruction,
    PlanRecord,
    PlanSegment,
    PredictionRecord,
    PrimitiveStep,
    QueryResult,
    canonical_json_bytes,
    sha256_value,
)
from cassi_resonant_field import (
    HELICAL_PACKET_CHANNELS,
    analyze_helical_packet,
    REGIONAL_KERNEL_NAME as RESONANT_REGIONAL_KERNEL_NAME,
    ResonantNumericalError,
    ResonantWorkspace,
    helical_packet_channels,
    resume_regional_state,
    split_helical_packet,
    workspace_from_regional_state,
)
MAX_INQUIRY_SURVIVORS = 4_096
MAX_INQUIRY_OPERATIONS = 256
MAX_INQUIRY_INTERVALS = 131_072

# The cognition family is one fixed catalog operation.  Its state is an
# ordinary JSON value so a checkpoint contains every cursor, partial binding,
# and assessment value needed for an exact restart.
REGIONAL_KERNEL_NAME = "cognition.field"
REGIONAL_KERNEL_MAX_WORK = 4_096
REGIONAL_STATE_SCHEMA = "cassifi.regional-cognition-state.v1"
REGIONAL_RESULT_SCHEMA = "cassifi.regional-kernel-result.v1"
REPRESENTATION_REGISTRY_SCHEMA = "cassifi.shared-representation-registry.v1"
COGNITION_REGIONAL_KERNEL_NAME = REGIONAL_KERNEL_NAME
COGNITION_REGIONAL_MAX_WORK = REGIONAL_KERNEL_MAX_WORK
COGNITION_REGIONAL_STATE_SCHEMA = REGIONAL_STATE_SCHEMA
COGNITION_REGIONAL_RESULT_SCHEMA = REGIONAL_RESULT_SCHEMA
SEMANTIC_STATE_SCHEMA = "cassifi.semantic-cognition-state.v1"
SEMANTIC_RESULT_SCHEMA = "cassifi.semantic-cognition-result.v1"
MECHANISM_STATE_SCHEMA = "cassifi.mechanism-step-state.v1"
SEMANTIC_MAX_RECORDS = 2_048
SEMANTIC_MAX_VERSIONS = 8
SEMANTIC_MAX_TIMELINE = 2_048
SEMANTIC_MAX_OPERATIONS = 2_048
SEMANTIC_MAX_OBSERVATIONS = 256
SEMANTIC_MAX_ALTERNATIVES = 128
_ABSENT = object()
PACKET_ASSEMBLY_SCHEMA = "cassifi.packet-assembly.v1"
PACKET_HIERARCHY_SCHEMA = "cassifi.packet-hierarchy.v1"
PACKET_WORK_ITEM_SCHEMA = "cassifi.packet-work-item.v1"
PACKET_REASONING_EPISODE_SCHEMA = "cassifi.packet-reasoning-episode.v1"
PACKET_CUE_SCHEMA = "cassifi.packet-reasoning-cue.v1"
PACKET_READOUT_SCHEMA = "cassifi.packet-affine-readout.v1"
PACKET_BOUND_SCHEMA = "cassifi.packet-readout-bound.v1"
PACKET_SCHEDULER_SCHEMA = "cassifi.packet-reasoning-scheduler.v1"
_PACKET_MAXIMUM_ABSOLUTE_VALUE = float.fromhex("0x1.fffffffffffffp+1023")
PACKET_RESOURCE_NAMES = (
    "branch_count",
    "evidence_reads",
    "frontier_size",
    "model_calls",
    "refinement_depth",
    "storage_words",
    "work",
)
PACKET_REASONING_PHASES = frozenset(
    {
        "checking-return",
        "ready",
        "reserved",
        "running-child",
        "terminal",
        "waiting",
    }
)
PACKET_WORK_KINDS = frozenset(
    {
        "branch",
        "model-native",
        "readout",
        "refine",
        "regional",
        "semantic",
        "temporal",
    }
)
PACKET_SELECTION_METHODS = frozenset(
    {
        "acquired",
        "baseline",
        "hierarchy",
        "live",
        "shuffled",
        "static",
    }
)
PACKET_SCHEDULER_FAIRNESS_BOUND = 4
SEMANTIC_OPERATION_NAMES = frozenset(
    {
        "acknowledgment",
        "admit-reasoning-input",
        "advance-invalidation",
        "advance-reasoning",
        "advance-time",
        "assess-prediction",
        "authorize-action",
        "cancel-action",
        "begin-reasoning",
        "consolidate",
        "correct",
        "dispatch-action",
        "explain",
        "finish-development",
        "finish-reasoning",
        "express",
        "idle",
        "inquire",
        "inspect",
        "run-development",
        "reuse-development-method",
        "start-development",
        "interpret",
        "learn",
        "learn-construction",
        "learn-hybrid",
        "learn-mechanism",
        "learn-parameters",
        "learn-predictive-state",
        "learn-procedure",
        "learn-representation",
        "mechanism-step",
        "migrate",
        "observe",
        "plan",
        "predict",
        "query",
        "register",
        "revise",
        "reopen-development",
        "revoke",
        "track-action",
        "update-perspective",
        "wait",
    }
)
SEMANTIC_PROGRAM_LIBRARY_ROLES = {
    "affordance": "affordances",
    "development-method": "development_methods",
    "construction": "constructions",
    "mechanism": "mechanisms",
    "predictive-state": "representations",
    "procedure": "procedures",
    "representation": "representations",
}
SEMANTIC_PROGRAM_ROLES = frozenset(
    {
        *SEMANTIC_PROGRAM_LIBRARY_ROLES,
        "consolidation",
        "migration",
        "plan",
        "reasoning",
    }
)

SEMANTIC_SPEECH_ACTS = frozenset(
    {
        "assertion",
        "commitment",
        "hypothesis",
        "prediction",
        "question",
        "quotation",
        "refusal",
        "request",
    }
)



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
        raise FieldIntelligenceError(
            "INVALID_NUMERIC_VALUE",
            f"{label} must be finite{' and positive' if positive else ''}",
        )
    return result


def _json(value: Any, label: str) -> Any:
    try:
        return __import__("json").loads(canonical_json_bytes(value))
    except Exception as exc:
        raise FieldIntelligenceError(
            "INVALID_TYPED_VALUE", f"{label} must be canonical JSON data"
        ) from exc


def tokenize(text: str) -> tuple[str, ...]:
    if not isinstance(text, str) or not text.strip():
        raise FieldIntelligenceError("INVALID_LANGUAGE", "utterance must be nonempty text")
    result: list[str] = []
    current: list[str] = []
    for character in text.strip():
        if character.isspace():
            if current:
                result.append("".join(current))
                current.clear()
        elif character in ".,?!:;":
            if current:
                result.append("".join(current))
                current.clear()
            result.append(character)
        else:
            current.append(character)
    if current:
        result.append("".join(current))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ActionReadout:
    readout_id: str
    version: int
    labels: tuple[str, ...]
    coefficients: tuple[Mapping[str, float], ...]
    observed_error_radius: float
    observation_error_map: tuple[tuple[float, ...], ...] | None = None

    def __post_init__(self) -> None:
        _identifier(self.readout_id, "readout_id")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise FieldIntelligenceError("INVALID_READOUT", "readout version must be positive")
        if len(self.labels) < 2 or len(set(self.labels)) != len(self.labels):
            raise FieldIntelligenceError(
                "INVALID_READOUT", "readout needs at least two unique action labels"
            )
        if len(self.coefficients) != len(self.labels):
            raise FieldIntelligenceError(
                "INVALID_READOUT", "readout rows must match action labels"
            )
        for label in self.labels:
            _identifier(label, "action label")
        normalized: list[Mapping[str, float]] = []
        for row in self.coefficients:
            if not isinstance(row, Mapping) or not row:
                raise FieldIntelligenceError(
                    "INVALID_READOUT", "each readout row must contain coefficients"
                )
            normalized.append(
                {
                    _identifier(name, "readout variable"): _finite(value, "readout coefficient")
                    for name, value in row.items()
                }
            )
        object.__setattr__(self, "coefficients", tuple(normalized))
        radius = _finite(self.observed_error_radius, "observation error radius")
        if radius < 0:
            raise FieldIntelligenceError(
                "INVALID_READOUT", "observation error radius cannot be negative"
            )
        if self.observation_error_map is not None:
            if not self.observation_error_map or any(
                len(row) != len(self.observation_error_map[0])
                for row in self.observation_error_map
            ):
                raise FieldIntelligenceError(
                    "INVALID_READOUT", "observation error map must be rectangular"
                )
            for row in self.observation_error_map:
                for value in row:
                    _finite(value, "observation error map coefficient")

    @property
    def variables(self) -> tuple[str, ...]:
        names = {name for row in self.coefficients for name in row}
        return tuple(sorted(names))

    @property
    def identity_sha256(self) -> str:
        return sha256_value(self.as_dict())

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "coefficients": [dict(row) for row in self.coefficients],
            "labels": list(self.labels),
            "observation_error_map": (
                None
                if self.observation_error_map is None
                else [list(row) for row in self.observation_error_map]
            ),
            "observed_error_radius": self.observed_error_radius,
            "readout_id": self.readout_id,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class ActionBranchCertificate:
    branch_id: str
    nominal_action: str | None
    certified_action: str | None
    scores: Mapping[str, float]
    competitors: tuple[str, ...]
    nominal_margins: tuple[float, ...]
    input_sensitivity_norms: tuple[float, ...]
    input_worst_margins: tuple[float, ...]
    solver_allowances: tuple[float, ...]
    combined_worst_margins: tuple[float, ...]
    numerical_guards: tuple[float, ...]
    limiting_competitor: str | None
    stability_radius: float | None
    worst_case_observation_delta: tuple[float, ...]
    numerical_valid: bool
    evidence_valid: bool
    model_applicable: bool
    feasible: bool
    authorized: bool
    commitment_eligible: bool
    refusal_reasons: tuple[str, ...]
    dependency_sha256: str

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "authorized": self.authorized,
            "branch_id": self.branch_id,
            "certified_action": self.certified_action,
            "combined_worst_margins": list(self.combined_worst_margins),
            "commitment_eligible": self.commitment_eligible,
            "competitors": list(self.competitors),
            "dependency_sha256": self.dependency_sha256,
            "evidence_valid": self.evidence_valid,
            "feasible": self.feasible,
            "input_sensitivity_norms": list(self.input_sensitivity_norms),
            "input_worst_margins": list(self.input_worst_margins),
            "limiting_competitor": self.limiting_competitor,
            "model_applicable": self.model_applicable,
            "nominal_action": self.nominal_action,
            "nominal_margins": list(self.nominal_margins),
            "numerical_guards": list(self.numerical_guards),
            "numerical_valid": self.numerical_valid,
            "refusal_reasons": list(self.refusal_reasons),
            "scores": dict(self.scores),
            "solver_allowances": list(self.solver_allowances),
            "stability_radius": self.stability_radius,
            "worst_case_observation_delta": list(self.worst_case_observation_delta),
        }


@dataclass(frozen=True, slots=True)
class ActionDecision:
    status: str
    query: QueryResult
    readout: Mapping[str, Any]
    certificates: tuple[ActionBranchCertificate, ...]
    committed_action: str | None
    obligations: tuple[str, ...]

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "certificates": [row.as_dict() for row in self.certificates],
            "committed_action": self.committed_action,
            "obligations": list(self.obligations),
            "query": self.query.as_dict(),
            "readout": dict(self.readout),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class Survivor:
    survivor_id: str
    action_set: tuple[str, ...]
    query_outcomes: Mapping[str, tuple[tuple[float, float], ...]]
    support_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.survivor_id, "survivor_id")
        if not self.action_set or len(set(self.action_set)) != len(self.action_set):
            raise FieldIntelligenceError(
                "INVALID_INQUIRY", "survivor action set must be nonempty and unique"
            )
        for action in self.action_set:
            _identifier(action, "survivor action")
        normalized: dict[str, tuple[tuple[float, float], ...]] = {}
        for query_id, intervals in self.query_outcomes.items():
            _identifier(query_id, "query_id")
            if not intervals:
                raise FieldIntelligenceError(
                    "INVALID_INQUIRY", "survivor query outcome set cannot be empty"
                )
            rows: list[tuple[float, float]] = []
            for interval in intervals:
                if len(interval) != 2:
                    raise FieldIntelligenceError(
                        "INVALID_INQUIRY", "outcome interval requires two endpoints"
                    )
                lower = _finite(interval[0], "outcome lower")
                upper = _finite(interval[1], "outcome upper")
                if lower > upper:
                    raise FieldIntelligenceError(
                        "INVALID_INQUIRY", "outcome interval endpoints are reversed"
                    )
                rows.append((lower, upper))
            normalized[query_id] = tuple(rows)
        object.__setattr__(self, "query_outcomes", normalized)
        for event_id in self.support_event_ids:
            _digest(event_id, "survivor support event")


@dataclass(frozen=True, slots=True)
class InquiryOperation:
    query_id: str
    cost: float
    risk: float
    authorized: bool
    feasible: bool

    def __post_init__(self) -> None:
        _identifier(self.query_id, "query_id")
        cost = _finite(self.cost, "inquiry cost")
        risk = _finite(self.risk, "inquiry risk")
        if cost < 0 or risk < 0:
            raise FieldIntelligenceError(
                "INVALID_INQUIRY", "inquiry cost and risk must be nonnegative"
            )


@dataclass(frozen=True, slots=True)
class InquiryDecision:
    status: str
    selected_query_id: str | None
    k_by_query: Mapping[str, int]
    guaranteed_eliminations: Mapping[str, int]
    refusal_reasons: tuple[str, ...]

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "guaranteed_eliminations": dict(self.guaranteed_eliminations),
            "k_by_query": dict(self.k_by_query),
            "refusal_reasons": list(self.refusal_reasons),
            "selected_query_id": self.selected_query_id,
            "status": self.status,
        }




def _possible_actions_at(
    survivors: Sequence[Survivor], query_id: str, value: float
) -> frozenset[str]:
    actions: set[str] = set()
    for survivor in survivors:
        intervals = survivor.query_outcomes.get(query_id, ())
        if any(lower <= value <= upper for lower, upper in intervals):
            actions.update(survivor.action_set)
    return frozenset(actions)


def _query_k(survivors: Sequence[Survivor], query_id: str) -> int:
    endpoints = sorted(
        {
            endpoint
            for survivor in survivors
            for interval in survivor.query_outcomes.get(query_id, ())
            for endpoint in interval
        }
    )
    if not endpoints:
        return math.inf  # type: ignore[return-value]
    probes = list(endpoints)
    probes.extend((left + right) / 2 for left, right in zip(endpoints, endpoints[1:]))
    values = [len(_possible_actions_at(survivors, query_id, probe)) for probe in probes]
    return max(values, default=0)


def choose_inquiry(
    survivors: Sequence[Survivor], operations: Sequence[InquiryOperation]
) -> InquiryDecision:
    if len(survivors) < 2:
        return InquiryDecision("not-needed", None, {}, {}, ())
    if len(survivors) > MAX_INQUIRY_SURVIVORS:
        raise FieldIntelligenceError(
            "INQUIRY_BUDGET", "survivor count exceeds the bounded inquiry budget"
        )
    if (
        not operations
        or len(operations) > MAX_INQUIRY_OPERATIONS
        or len({row.query_id for row in operations}) != len(operations)
    ):
        raise FieldIntelligenceError(
            "INQUIRY_BUDGET",
            "inquiry operations must be nonempty, unique, and within budget",
        )
    interval_count = sum(
        len(intervals)
        for survivor in survivors
        for intervals in survivor.query_outcomes.values()
    )
    if interval_count > MAX_INQUIRY_INTERVALS:
        raise FieldIntelligenceError(
            "INQUIRY_BUDGET", "outcome intervals exceed the bounded inquiry budget"
        )
    available_queries = {operation.query_id for operation in operations}
    if any(set(survivor.query_outcomes) != available_queries for survivor in survivors):
        raise FieldIntelligenceError(
            "INQUIRY_COVERAGE",
            "every survivor must declare an outcome set for every inquiry",
        )
    k_by_query = {
        operation.query_id: _query_k(survivors, operation.query_id)
        for operation in operations
    }
    eliminations: dict[str, int] = {}
    for operation in operations:
        query_id = operation.query_id
        endpoints = sorted(
            {
                endpoint
                for survivor in survivors
                for interval in survivor.query_outcomes[query_id]
                for endpoint in interval
            }
        )
        probes = list(endpoints)
        probes.extend((left + right) / 2 for left, right in zip(endpoints, endpoints[1:]))
        max_compatible = 0
        for probe in probes:
            compatible = sum(
                any(lower <= probe <= upper for lower, upper in survivor.query_outcomes[query_id])
                for survivor in survivors
            )
            max_compatible = max(max_compatible, compatible)
        eliminations[query_id] = len(survivors) - max_compatible
    feasible = [row for row in operations if row.authorized and row.feasible]
    resolving = [row for row in feasible if k_by_query[row.query_id] == 1]
    if resolving:
        selected = min(resolving, key=lambda row: (row.cost, row.risk, row.query_id))
        return InquiryDecision("resolving", selected.query_id, k_by_query, eliminations, ())
    separating = [row for row in feasible if eliminations[row.query_id] > 0]
    if separating:
        selected = min(
            separating,
            key=lambda row: (
                -eliminations[row.query_id],
                row.cost,
                row.risk,
                row.query_id,
            ),
        )
        return InquiryDecision(
            "partial", selected.query_id, k_by_query, eliminations, ("no-guaranteed-action-resolution",)
        )
    reasons: list[str] = []
    if not any(row.authorized for row in operations):
        reasons.append("authority")
    if not any(row.feasible for row in operations):
        reasons.append("feasibility")
    if not reasons:
        reasons.append("no-distinguishing-query")
    return InquiryDecision("unresolved", None, k_by_query, eliminations, tuple(reasons))


def model_uncertainty_bound(
    *,
    free_hessian: Sequence[Sequence[float]],
    boundary_block: Sequence[Sequence[float]],
    observed: Sequence[float],
    free_readout: Sequence[float],
    observed_readout: Sequence[float],
    hessian_error: float,
    boundary_error: float,
    observation_radius: float,
) -> Mapping[str, Any]:
    a = torch.tensor(free_hessian, dtype=torch.float64)
    b = torch.tensor(boundary_block, dtype=torch.float64)
    observation = torch.tensor(observed, dtype=torch.float64)
    c_u = torch.tensor(free_readout, dtype=torch.float64)
    c_o = torch.tensor(observed_readout, dtype=torch.float64)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or b.shape[0] != a.shape[0]:
        raise FieldIntelligenceError("INVALID_MODEL_BOUND", "model matrices have incompatible shapes")
    if b.shape[1] != observation.numel() or c_u.shape != (a.shape[0],) or c_o.shape != observation.shape:
        raise FieldIntelligenceError("INVALID_MODEL_BOUND", "model-bound vectors have incompatible shapes")
    if not all(bool(torch.isfinite(row).all()) for row in (a, b, observation, c_u, c_o)):
        raise FieldIntelligenceError("INVALID_MODEL_BOUND", "model-bound values must be finite")
    if not torch.equal(a, a.T):
        raise FieldIntelligenceError("INVALID_MODEL_BOUND", "free Hessian must be symmetric")
    eigenvalues = torch.linalg.eigvalsh(a)
    mu = float(eigenvalues.min())
    alpha = _finite(hessian_error, "Hessian error")
    beta = _finite(boundary_error, "boundary error")
    radius = _finite(observation_radius, "observation radius")
    if min(alpha, beta, radius) < 0 or alpha >= mu:
        raise FieldIntelligenceError(
            "MODEL_BOUND_UNAVAILABLE",
            "declared perturbation does not preserve a positive spectral margin",
        )
    k = -torch.linalg.solve(a, b)
    gamma_k = (beta + alpha * float(torch.linalg.matrix_norm(k, ord=2))) / (mu - alpha)
    sensor = radius * float(torch.linalg.vector_norm(k.T @ c_u + c_o))
    model = float(torch.linalg.vector_norm(c_u)) * gamma_k * (
        float(torch.linalg.vector_norm(observation)) + radius
    )
    nominal_u = k @ observation
    nominal = float(c_u @ nominal_u + c_o @ observation)
    return {
        "free_spectral_margin": mu,
        "input_bound": sensor,
        "model_bound": model,
        "nominal_score": nominal,
        "response_error_bound": gamma_k,
        "total_bound": sensor + model,
    }


def adjoint_readout_certificate(
    *,
    system: Sequence[Sequence[float]],
    rhs: Sequence[float],
    approximate_state: Sequence[float],
    readout: Sequence[float],
    approximate_adjoint: Sequence[float] | None = None,
) -> Mapping[str, Any]:
    a = torch.tensor(system, dtype=torch.float64)
    f = torch.tensor(rhs, dtype=torch.float64)
    state = torch.tensor(approximate_state, dtype=torch.float64)
    c = torch.tensor(readout, dtype=torch.float64)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or f.shape != (a.shape[0],):
        raise FieldIntelligenceError("INVALID_ADJOINT", "adjoint system shape is invalid")
    if state.shape != f.shape or c.shape != f.shape or not torch.equal(a, a.T):
        raise FieldIntelligenceError("INVALID_ADJOINT", "adjoint vectors or symmetry are invalid")
    eigenvalues = torch.linalg.eigvalsh(a)
    mu = float(eigenvalues.min())
    if mu <= 0:
        raise FieldIntelligenceError("ADJOINT_UNAVAILABLE", "adjoint system is not positive definite")
    residual = a @ state - f
    if approximate_adjoint is None:
        adjoint = torch.linalg.solve(a.T, c)
    else:
        adjoint = torch.tensor(approximate_adjoint, dtype=torch.float64)
        if adjoint.shape != f.shape:
            raise FieldIntelligenceError("INVALID_ADJOINT", "approximate adjoint shape is invalid")
    adjoint_residual = a.T @ adjoint - c
    signed_estimate = float(adjoint @ residual)
    correction = float(torch.linalg.vector_norm(adjoint_residual) * torch.linalg.vector_norm(residual) / mu)
    exact_state = torch.linalg.solve(a, f)
    actual_error = float(c @ (state - exact_state))
    return {
        "actual_readout_error": actual_error,
        "adjoint_residual_norm": float(torch.linalg.vector_norm(adjoint_residual)),
        "bound": abs(signed_estimate) + correction,
        "exact_identity_error": abs(actual_error - float(torch.linalg.solve(a.T, c) @ residual)),
        "residual_norm": float(torch.linalg.vector_norm(residual)),
        "signed_adjoint_estimate": signed_estimate,
        "spectral_lower_bound": mu,
    }


def directed_macro_margin(
    *,
    operators: Sequence[Sequence[Sequence[float]]],
    center: Sequence[float],
    score_direction: Sequence[float],
    initial_radius: float,
    disturbance_radii: Sequence[float],
) -> Mapping[str, Any]:
    if len(operators) != len(disturbance_radii):
        raise FieldIntelligenceError(
            "INVALID_MACRO_BOUND", "each directed step requires one disturbance radius"
        )
    center_tensor = torch.tensor(center, dtype=torch.float64)
    direction = torch.tensor(score_direction, dtype=torch.float64)
    matrices = [torch.tensor(row, dtype=torch.float64) for row in operators]
    if any(matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] for matrix in matrices):
        raise FieldIntelligenceError("INVALID_MACRO_BOUND", "directed operators must be square")
    if matrices and any(matrix.shape[0] != center_tensor.numel() for matrix in matrices):
        raise FieldIntelligenceError("INVALID_MACRO_BOUND", "directed operator dimensions differ")
    if direction.shape != center_tensor.shape:
        raise FieldIntelligenceError("INVALID_MACRO_BOUND", "score direction shape differs")
    radius = _finite(initial_radius, "initial radius")
    disturbances = [_finite(value, "disturbance radius") for value in disturbance_radii]
    if radius < 0 or any(value < 0 for value in disturbances):
        raise FieldIntelligenceError("INVALID_MACRO_BOUND", "radii cannot be negative")
    horizon = len(matrices)
    products: list[torch.Tensor] = [torch.eye(center_tensor.numel(), dtype=torch.float64) for _ in range(horizon + 1)]
    running = torch.eye(center_tensor.numel(), dtype=torch.float64)
    for index in range(horizon - 1, -1, -1):
        running = running @ matrices[index]
        products[index] = running
    nominal = float(direction @ products[0] @ center_tensor)
    initial_budget = radius * float(torch.linalg.vector_norm(products[0].T @ direction))
    disturbance_budgets = [
        disturbances[index]
        * float(torch.linalg.vector_norm(products[index + 1].T @ direction))
        for index in range(horizon)
    ]
    return {
        "disturbance_budgets": disturbance_budgets,
        "initial_budget": initial_budget,
        "lower_margin": nominal - initial_budget - sum(disturbance_budgets),
        "nominal_score": nominal,
    }


def consequence_partition(
    risks: Mapping[str, Mapping[str, Mapping[str, float]]], *, epsilon: float
) -> Mapping[str, Any]:
    tolerance = _finite(epsilon, "quotient epsilon")
    if tolerance < 0:
        raise FieldIntelligenceError("INVALID_QUOTIENT", "epsilon cannot be negative")
    if not risks:
        raise FieldIntelligenceError("INVALID_QUOTIENT", "risk family cannot be empty")
    hypotheses = sorted(risks)
    tests = set(next(iter(risks.values())))
    if any(set(risks[hypothesis]) != tests for hypothesis in hypotheses):
        raise FieldIntelligenceError("INVALID_QUOTIENT", "hypotheses must share tests")
    actions: set[str] | None = None
    for hypothesis in hypotheses:
        for test in tests:
            row = risks[hypothesis][test]
            if actions is None:
                actions = set(row)
            elif set(row) != actions:
                raise FieldIntelligenceError(
                    "INVALID_QUOTIENT", "risk rows must share one action domain"
                )
            for value in row.values():
                _finite(value, "risk")
    diameter = 0.0
    witness: tuple[str, str, str, str] | None = None
    assert actions is not None
    for left_index, left in enumerate(hypotheses):
        for right in hypotheses[left_index + 1 :]:
            for test in sorted(tests):
                for action in sorted(actions):
                    difference = abs(risks[left][test][action] - risks[right][test][action])
                    if difference > diameter:
                        diameter = difference
                        witness = (left, right, test, action)
    representative = hypotheses[0]
    excess: dict[str, dict[str, float]] = {}
    for hypothesis in hypotheses:
        excess[hypothesis] = {}
        for test in sorted(tests):
            selected = min(actions, key=lambda action: (risks[representative][test][action], action))
            best = min(risks[hypothesis][test].values())
            excess[hypothesis][test] = risks[hypothesis][test][selected] - best
    maximum_excess = max(value for rows in excess.values() for value in rows.values())
    admitted = diameter <= tolerance
    return {
        "admitted": admitted,
        "diameter": diameter,
        "excess_by_hypothesis": excess,
        "maximum_excess": maximum_excess,
        "representative": representative,
        "two_epsilon_bound": 2 * tolerance,
        "witness": None if witness is None else list(witness),
    }


def prequential_radius(*, count: int, prefix_code_bits: int, delta: float) -> float:
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise FieldIntelligenceError("INVALID_PREQUENTIAL", "count must be positive")
    if isinstance(prefix_code_bits, bool) or not isinstance(prefix_code_bits, int) or prefix_code_bits < 1:
        raise FieldIntelligenceError(
            "INVALID_PREQUENTIAL", "prefix-code length must be positive"
        )
    confidence = _finite(delta, "prequential delta")
    if not 0 < confidence < 1:
        raise FieldIntelligenceError("INVALID_PREQUENTIAL", "delta must lie in (0, 1)")
    return math.sqrt(
        (
            prefix_code_bits * math.log(2)
            + math.log(2 * count * (count + 1) / confidence)
        )
        / (2 * count)
    )
def _regional_plain(value: Any, label: str) -> Any:
    """Detach a typed reference record into bounded canonical JSON data."""

    if hasattr(value, "as_dict") and callable(value.as_dict):
        value = value.as_dict()
    return _json(value, label)


def _regional_integer(
    value: Any,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = REGIONAL_KERNEL_MAX_WORK,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or value > maximum
    ):
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK",
            f"{label} must be an integer in [{minimum}, {maximum}]",
        )
    return int(value)


def _regional_number(
    value: Any,
    label: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    inclusive_minimum: bool = True,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK", f"{label} must be a number"
        )
    number = float(value)
    if not math.isfinite(number):
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK", f"{label} must be finite"
        )
    if minimum is not None and (
        number < minimum if inclusive_minimum else number <= minimum
    ):
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK",
            f"{label} must be "
            f"{'at least' if inclusive_minimum else 'greater than'} {minimum}",
        )
    if maximum is not None and number > maximum:
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK", f"{label} must be at most {maximum}"
        )
    return number


def _regional_text(value: Any, label: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise FieldIntelligenceError("INVALID_REGIONAL_TASK", f"{label} must be text")
    if len(value.encode("utf-8")) > 64 * 1024:
        raise FieldIntelligenceError("INVALID_REGIONAL_TASK", f"{label} is too large")
    return value


def _regional_tokens(text: Any) -> tuple[str, ...]:
    value = _regional_text(text, "language text")
    if not value.strip():
        return ()
    result: list[str] = []
    current: list[str] = []
    for character in value.strip():
        if character.isspace():
            if current:
                result.append("".join(current))
                current.clear()
        elif character in ".,?!:;":
            if current:
                result.append("".join(current))
                current.clear()
            result.append(character)
        else:
            current.append(character)
    if current:
        result.append("".join(current))
    return tuple(result)


def _regional_guard_matches(guard: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    if not isinstance(guard, Mapping):
        return False
    field = guard.get("field")
    operator = guard.get("operator")
    value = guard.get("value")
    if not isinstance(field, str) or not isinstance(operator, str):
        return False
    present = field in context
    if operator == "exists":
        return present is bool(value)
    if not present:
        return False
    actual = context[field]
    if operator == "eq":
        return actual == value
    if operator == "ne":
        return actual != value
    if operator == "in":
        return isinstance(value, list) and actual in value
    if operator == "range":
        return (
            isinstance(value, list)
            and len(value) == 2
            and not isinstance(actual, bool)
            and isinstance(actual, (int, float))
            and float(value[0]) <= float(actual) <= float(value[1])
        )
    return False


def _regional_matches(
    row: Mapping[str, Any],
    context: Mapping[str, Any],
) -> bool:
    return row.get("status") == "promoted" and all(
        _regional_guard_matches(guard, context)
        for guard in row.get("guards", [])
    )


def _regional_program_source(program: Any) -> dict[str, Any]:
    source = _regional_plain(program, "regional program")
    if not isinstance(source, dict):
        raise FieldIntelligenceError("INVALID_REGIONAL_TASK", "program source is not an object")
    required = {"program_id", "version", "roles", "steps", "outputs", "status"}
    if not required.issubset(source):
        raise FieldIntelligenceError("INVALID_REGIONAL_TASK", "program source is incomplete")
    if (
        not isinstance(source["roles"], list)
        or not isinstance(source["steps"], list)
        or not isinstance(source["outputs"], list)
        or not isinstance(source["program_id"], str)
        or not isinstance(source["version"], int)
    ):
        raise FieldIntelligenceError("INVALID_REGIONAL_TASK", "program source has invalid types")
    return source


def _regional_construction_source(construction: Any) -> dict[str, Any]:
    source = _regional_plain(construction, "regional construction")
    if not isinstance(source, dict):
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK", "construction source is not an object"
        )
    required = {
        "construction_id",
        "version",
        "pattern",
        "roles",
        "semantic_program_id",
        "support_event_ids",
        "status",
    }
    if not required.issubset(source):
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK", "construction source is incomplete"
        )
    if not all(
        isinstance(source[name], list)
        for name in ("pattern", "roles", "support_event_ids")
    ):
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK", "construction source has invalid token fields"
        )
    return source


def _regional_construction_example(raw: Any, label: str) -> dict[str, Any]:
    example = _regional_plain(raw, label)
    if not isinstance(example, dict) or set(example) != {"event_id", "roles", "text"}:
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE", f"{label} schema is closed"
        )
    roles = example["roles"]
    if not isinstance(roles, dict) or not roles:
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE", f"{label} roles must be a nonempty object"
        )
    normalized_roles = {
        _identifier(name, f"{label} role"): _regional_text(value, f"{label} role value")
        for name, value in roles.items()
    }
    text = _regional_text(example["text"], f"{label} text")
    if len(_regional_tokens(text)) > 128:
        raise FieldIntelligenceError(
            "REGIONAL_CAPACITY", f"{label} exceeds the language token bound"
        )
    return {
        "event_id": _digest(example["event_id"], f"{label} event"),
        "roles": normalized_roles,
        "text": text,
    }


def _regional_induced_pattern(example: Mapping[str, Any]) -> list[str]:
    tokens = list(_regional_tokens(example["text"]))
    spans: list[tuple[int, int, str]] = []
    occupied: set[int] = set()
    for role in sorted(example["roles"]):
        value_tokens = list(_regional_tokens(example["roles"][role]))
        matches = [
            (start, start + len(value_tokens))
            for start in range(len(tokens) - len(value_tokens) + 1)
            if tokens[start : start + len(value_tokens)] == value_tokens
            and not occupied.intersection(range(start, start + len(value_tokens)))
        ]
        if len(matches) != 1:
            raise FieldIntelligenceError(
                "CONSTRUCTION_UNSUPPORTED",
                "each role span must occur exactly once without overlap",
                details={"role": role},
            )
        start, end = matches[0]
        occupied.update(range(start, end))
        spans.append((start, end, role))
    spans.sort()
    pattern: list[str] = []
    cursor = 0
    for start, end, role in spans:
        if start < cursor:
            raise FieldIntelligenceError(
                "CONSTRUCTION_UNSUPPORTED", "construction role spans overlap"
            )
        pattern.extend(tokens[cursor:start])
        pattern.append("{" + role + "}")
        cursor = end
    pattern.extend(tokens[cursor:])
    return pattern
def _regional_pattern_variants(row: Mapping[str, Any]) -> tuple[list[str], ...]:
    """Return learned surface variants while preserving the original pattern API."""
    raw_variants = row.get("pattern_variants")
    candidates: list[Any] = [row.get("pattern")]
    if raw_variants is not None:
        if not isinstance(raw_variants, list):
            raise FieldIntelligenceError(
                "INVALID_LANGUAGE", "construction pattern variants must be a list"
            )
        candidates.extend(raw_variants)
    variants: list[list[str]] = []
    seen: set[bytes] = set()
    for raw_pattern in candidates:
        if not isinstance(raw_pattern, list) or not raw_pattern or any(
            not isinstance(token, str) or not token for token in raw_pattern
        ):
            raise FieldIntelligenceError(
                "INVALID_LANGUAGE", "construction pattern variant is invalid"
            )
        normalized = [str(token) for token in raw_pattern]
        key = canonical_json_bytes(normalized)
        if key not in seen:
            seen.add(key)
            variants.append(normalized)
    if not variants:
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE", "construction requires one pattern variant"
        )
    return tuple(variants)


def _regional_variable_matches(
    row: Mapping[str, Any],
    tokens: Sequence[str],
    alias_entities: Mapping[str, Sequence[str]],
) -> list[dict[str, str]]:
    pattern = row["pattern"]
    frontier: list[tuple[int, int, dict[str, str]]] = [(0, 0, {})]
    completed: list[dict[str, str]] = []
    expansions = 0
    while frontier:
        pattern_cursor, token_cursor, bindings = frontier.pop()
        expansions += 1
        if expansions > REGIONAL_KERNEL_MAX_WORK:
            raise FieldIntelligenceError(
                "REGIONAL_CAPACITY", "language composition frontier exceeds its bound"
            )
        if pattern_cursor == len(pattern):
            if token_cursor == len(tokens):
                completed.append(bindings)
            continue
        expected = pattern[pattern_cursor]
        if not (
            isinstance(expected, str)
            and expected.startswith("{")
            and expected.endswith("}")
        ):
            if token_cursor < len(tokens) and expected == tokens[token_cursor]:
                frontier.append((pattern_cursor + 1, token_cursor + 1, bindings))
            continue
        role = expected[1:-1]
        remaining_pattern = len(pattern) - pattern_cursor - 1
        maximum_end = len(tokens) - remaining_pattern
        for end in range(token_cursor + 1, maximum_end + 1):
            surface = " ".join(tokens[token_cursor:end])
            candidates = list(alias_entities.get(surface, []))
            if len(candidates) > 1:
                continue
            resolved = candidates[0] if candidates else surface
            previous = bindings.get(role)
            if previous is not None and previous != resolved:
                continue
            successor = dict(bindings)
            successor[role] = resolved
            frontier.append((pattern_cursor + 1, end, successor))
    unique: dict[bytes, dict[str, str]] = {}
    for bindings in completed:
        unique[canonical_json_bytes(bindings)] = bindings
    return [unique[key] for key in sorted(unique)]


def _regional_program_eval(
    program: Mapping[str, Any],
    bindings: Mapping[str, Any],
) -> dict[str, Any]:
    roles = tuple(program["roles"])
    if set(bindings) != set(roles):
        raise FieldIntelligenceError(
            "PROGRAM_BINDING",
            "regional program bindings must cover its roles exactly",
            details={"expected": list(roles), "actual": sorted(bindings)},
        )
    values = {
        str(name): _regional_plain(value, f"binding {name}")
        for name, value in bindings.items()
    }
    for raw_step in program["steps"]:
        if not isinstance(raw_step, Mapping):
            raise FieldIntelligenceError("INVALID_REGIONAL_TASK", "program step is invalid")
        operation = raw_step.get("operation")
        inputs = raw_step.get("inputs")
        output = raw_step.get("output")
        if (
            not isinstance(operation, str)
            or not isinstance(inputs, list)
            or not isinstance(output, str)
            or output in values
            or any(name not in values for name in inputs)
        ):
            raise FieldIntelligenceError("PROGRAM_DOMAIN", "regional program step is invalid")
        args = [values[name] for name in inputs]
        try:
            if operation == "identity":
                result = args[0]
            elif operation == "constant":
                result = raw_step.get("literal")
            elif operation == "add":
                result = args[0] + args[1]
            elif operation == "subtract":
                result = args[0] - args[1]
            elif operation == "multiply":
                result = args[0] * args[1]
            elif operation == "divide":
                if args[1] == 0:
                    raise FieldIntelligenceError("PROGRAM_DOMAIN", "division by zero")
                result = args[0] / args[1]
            elif operation == "negate":
                result = -args[0]
            elif operation == "absolute":
                result = abs(args[0])
            elif operation == "equal":
                result = args[0] == args[1]
            elif operation == "less_equal":
                result = args[0] <= args[1]
            elif operation == "vector":
                result = list(args)
            elif operation == "convert":
                literal = raw_step.get("literal")
                if isinstance(literal, bool) or not isinstance(literal, (int, float)):
                    raise FieldIntelligenceError(
                        "PROGRAM_DOMAIN", "conversion scale is invalid"
                    )
                result = args[0] * float(literal)
            elif operation == "concat":
                result = "".join(str(item) for item in args)
            else:
                raise FieldIntelligenceError(
                    "PROGRAM_DOMAIN", f"unsupported regional primitive: {operation}"
                )
        except FieldIntelligenceError:
            raise
        except (TypeError, ValueError, OverflowError) as exc:
            raise FieldIntelligenceError(
                "PROGRAM_DOMAIN", f"regional primitive {operation} rejected its inputs"
            ) from exc
        values[output] = _regional_plain(result, f"program output {output}")
    return {
        str(name): values[name]
        for name in program["outputs"]
        if name in values
    }


def _regional_loss(predicted: Mapping[str, Any], outcome: Mapping[str, Any]) -> float:
    if set(predicted) != set(outcome):
        raise FieldIntelligenceError(
            "ASSESSMENT_CONFLICT",
            "outcome keys differ from the frozen prediction",
        )
    squared = 0.0
    for name, predicted_value in predicted.items():
        actual_value = outcome[name]
        if isinstance(predicted_value, bool) or isinstance(actual_value, bool):
            squared += 0.0 if predicted_value == actual_value else 1.0
        elif isinstance(predicted_value, (int, float)) and isinstance(
            actual_value, (int, float)
        ):
            difference = float(predicted_value) - float(actual_value)
            squared += difference * difference
        else:
            squared += 0.0 if predicted_value == actual_value else 1.0
    return squared


def _regional_state(
    operation: str,
    source: Mapping[str, Any],
    continuation: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": REGIONAL_STATE_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "operation": operation,
        "phase": "running",
        "source": _regional_plain(dict(source), "regional task source"),
        "continuation": _regional_plain(dict(continuation), "regional continuation"),
        "result": None,
    }


def regional_program_state(
    program: FieldProgram | Mapping[str, Any],
    bindings: Mapping[str, Any],
    *,
    outcome: Mapping[str, Any] | None = None,
    event_id: str | None = None,
    field_generation: int = 0,
    authority_generation: int = 0,
    assessment_sequence: int | None = None,
    loss_scale: float = 1.0,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Lower one candidate/program assessment to resumable typed task data."""

    source_program = _regional_program_source(program)
    if not isinstance(bindings, Mapping):
        raise FieldIntelligenceError("PROGRAM_BINDING", "regional bindings must be an object")
    generation = _regional_integer(field_generation, "field generation", maximum=2**53)
    authority = _regional_integer(
        authority_generation, "authority generation", maximum=2**53
    )
    scale = _finite(loss_scale, "assessment loss scale", positive=True)
    sequence = (
        len(source_program.get("assessments", [])) + 1
        if assessment_sequence is None
        else _regional_integer(assessment_sequence, "assessment sequence", minimum=1)
    )
    normalized_bindings = _regional_plain(dict(bindings), "program bindings")
    prediction_id = sha256_value(
        {
            "bindings": normalized_bindings,
            "field_generation": generation,
            "program_id": source_program["program_id"],
            "program_version": source_program["version"],
            "sequence": sequence,
        }
    )
    normalized_outcome = (
        None
        if outcome is None
        else _regional_plain(dict(outcome), "assessment outcome")
    )
    if normalized_outcome is not None and not isinstance(normalized_outcome, dict):
        raise FieldIntelligenceError("ASSESSMENT_CONFLICT", "assessment outcome is invalid")
    if normalized_outcome is not None:
        if event_id is None:
            raise FieldIntelligenceError(
                "ASSESSMENT_CONFLICT", "an outcome requires an assessment event id"
            )
        _digest(event_id, "assessment event_id")
    source = {
        "program": source_program,
        "bindings": normalized_bindings,
        "outcome": normalized_outcome,
        "event_id": event_id,
        "field_generation": generation,
        "authority_generation": authority,
        "assessment_sequence": sequence,
        "loss_scale": scale,
        "prediction_id": prediction_id,
        "context": _regional_plain(dict(context or {}), "program context"),
    }
    return _regional_state(
        "program-assessment",
        source,
        {
            "stage": "steps",
            "cursor": 0,
            "values": normalized_bindings,
            "prediction": None,
            "loss": None,
        },
    )
def regional_program_promotion_state(
    programs: Sequence[FieldProgram | Mapping[str, Any]],
    candidate_ids: Sequence[str],
    *,
    minimum_assessments: int = 1,
    maximum_average_loss: float = 0.0,
    bit_penalty: float = 0.0,
) -> dict[str, Any]:
    """Lower deterministic candidate selection and promotion into a cursor."""

    rows = [_regional_program_source(row) for row in programs]
    selected_ids = [_identifier(item, "candidate program") for item in candidate_ids]
    if not selected_ids:
        raise FieldIntelligenceError("INVALID_PROMOTION", "candidate set is empty")
    minimum = _regional_integer(
        minimum_assessments, "minimum assessments", minimum=1, maximum=2**53
    )
    threshold = _finite(maximum_average_loss, "maximum average loss")
    if not 0.0 <= threshold <= 1.0:
        raise FieldIntelligenceError(
            "INVALID_PROMOTION", "maximum average loss must lie in [0, 1]"
        )
    penalty = _finite(bit_penalty, "bit penalty")
    if penalty < 0:
        raise FieldIntelligenceError("INVALID_SELECTION", "bit penalty cannot be negative")
    source = {
        "programs": rows,
        "candidate_ids": selected_ids,
        "minimum_assessments": minimum,
        "maximum_average_loss": threshold,
        "bit_penalty": penalty,
    }
    return _regional_state(
        "program-promotion",
        source,
        {"candidate_cursor": 0, "evaluated": [], "eligible": []},
    )


def regional_language_state(
    constructions: Sequence[LanguageConstruction | Mapping[str, Any]],
    *,
    mode: str,
    text: str | None = None,
    bindings: Mapping[str, Any] | None = None,
    semantic_program_id: str | None = None,
    semantic_programs: (
        Mapping[str, FieldProgram | Mapping[str, Any]]
        | Sequence[FieldProgram | Mapping[str, Any]]
        | None
    ) = None,
    context: Mapping[str, Any] | None = None,
    representation_registry: Mapping[str, Any] | None = None,
    max_tokens: int = 128,
) -> dict[str, Any]:
    """Lower exact tokenize/role binding and rendering without a language model."""

    if mode not in {"interpret", "express"}:
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK", "language mode must be interpret or express"
        )
    rows = [_regional_construction_source(row) for row in constructions]
    if len(rows) > REGIONAL_KERNEL_MAX_WORK:
        raise FieldIntelligenceError("REGIONAL_CAPACITY", "too many language constructions")
    programs: dict[str, dict[str, Any]] = {}
    if semantic_programs is not None:
        values = (
            semantic_programs.items()
            if isinstance(semantic_programs, Mapping)
            else (
                (
                    _regional_program_source(item)["program_id"],
                    _regional_program_source(item),
                )
                for item in semantic_programs
            )
        )
        for key, value in values:
            program = _regional_program_source(value)
            programs[str(key)] = program
    alias_entities: dict[str, list[str]] = {}
    entity_aliases: dict[str, list[str]] = {}
    if representation_registry is not None:
        registry = _regional_plain(
            dict(representation_registry), "language representation registry"
        )
        if (
            not isinstance(registry, dict)
            or set(registry) != {"schema", "entities", "relations"}
            or registry["schema"] != REPRESENTATION_REGISTRY_SCHEMA
            or not isinstance(registry["entities"], list)
        ):
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION", "language representation registry is invalid"
            )
        for raw in registry["entities"]:
            if not isinstance(raw, dict):
                raise FieldIntelligenceError(
                    "INVALID_REPRESENTATION", "language entity record is invalid"
                )
            entity_id = _identifier(raw.get("entity_id"), "language entity")
            aliases = sorted(
                {
                    _regional_text(alias, "language entity alias")
                    for alias in raw.get("aliases", [])
                }
            )
            if not aliases:
                raise FieldIntelligenceError(
                    "INVALID_REPRESENTATION", "language entity has no lexical alias"
                )
            entity_aliases[entity_id] = aliases
            for alias in aliases:
                alias_entities.setdefault(alias, []).append(entity_id)
        for alias in alias_entities:
            alias_entities[alias].sort()
    if mode == "interpret":
        if text is None:
            raise FieldIntelligenceError("INVALID_LANGUAGE", "interpretation needs text")
        normalized_text = _regional_text(text, "language text")
        normalized_bindings = None
        semantic_id = None
    else:
        if semantic_program_id is None or not isinstance(semantic_program_id, str):
            raise FieldIntelligenceError(
                "INVALID_LANGUAGE", "expression needs a semantic program id"
            )
        if bindings is None or not isinstance(bindings, Mapping):
            raise FieldIntelligenceError(
                "INVALID_LANGUAGE", "expression needs role bindings"
            )
        normalized_text = None
        normalized_bindings = _regional_plain(dict(bindings), "expression bindings")
        semantic_id = semantic_program_id
    source = {
        "constructions": rows,
        "programs": programs,
        "mode": mode,
        "text": normalized_text,
        "bindings": normalized_bindings,
        "semantic_program_id": semantic_id,
        "context": _regional_plain(dict(context or {}), "language context"),
        "alias_entities": alias_entities,
        "entity_aliases": entity_aliases,
        "max_tokens": _regional_integer(max_tokens, "language token budget", minimum=1),
    }
    continuation = (
        {
            "construction_cursor": 0,
            "token_cursor": 0,
            "candidate": None,
            "matches": [],
        }
        if mode == "interpret"
        else {"construction_cursor": 0, "eligible_count": 0, "rendered": []}
    )
    return _regional_state("language", source, continuation)

def regional_construction_learning_state(
    acquisition_examples: Sequence[Mapping[str, Any]],
    validation_examples: Sequence[Mapping[str, Any]],
    *,
    construction_id: str,
    semantic_program_id: str,
    guards: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Learn one variable-span construction and validate it on held-out episodes."""

    acquisition = [
        _regional_construction_example(row, "construction acquisition example")
        for row in acquisition_examples
    ]
    validation = [
        _regional_construction_example(row, "construction validation example")
        for row in validation_examples
    ]
    if len(acquisition) < 2 or not validation:
        raise FieldIntelligenceError(
            "CONSTRUCTION_UNSUPPORTED",
            "construction learning needs two acquisitions and an independent validation",
        )
    if len(acquisition) + len(validation) > REGIONAL_KERNEL_MAX_WORK:
        raise FieldIntelligenceError(
            "REGIONAL_CAPACITY", "too many construction learning examples"
        )
    role_sets = {
        tuple(sorted(example["roles"]))
        for example in (*acquisition, *validation)
    }
    if len(role_sets) != 1:
        raise FieldIntelligenceError(
            "CONSTRUCTION_UNSUPPORTED", "construction examples must share semantic roles"
        )
    source = {
        "construction_id": _identifier(construction_id, "construction id"),
        "semantic_program_id": _identifier(
            semantic_program_id, "construction semantic program"
        ),
        "acquisition_examples": acquisition,
        "validation_examples": validation,
        "guards": _regional_plain(list(guards), "construction guards"),
    }
    return _regional_state(
        "construction-learning",
        source,
        {
            "stage": "acquisition",
            "cursor": 0,
            "pattern": None,
            "pattern_variants": [],
            "support_event_ids": [],
            "validation_event_ids": [],
        },
    )


def regional_representation_state(
    mentions: Sequence[Mapping[str, Any]],
    *,
    same_entity: Sequence[Sequence[str]] = (),
    distinct_entity: Sequence[Sequence[str]] = (),
    relations: Sequence[Mapping[str, Any]] = (),
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Learn stable entity/relation identities from bounded linked evidence."""

    retained = _regional_plain(
        dict(
            registry
            or {
                "schema": REPRESENTATION_REGISTRY_SCHEMA,
                "entities": [],
                "relations": [],
            }
        ),
        "representation registry",
    )
    if (
        not isinstance(retained, dict)
        or set(retained) != {"schema", "entities", "relations"}
        or retained["schema"] != REPRESENTATION_REGISTRY_SCHEMA
        or not isinstance(retained["entities"], list)
        or not isinstance(retained["relations"], list)
    ):
        raise FieldIntelligenceError(
            "INVALID_REPRESENTATION", "representation registry is invalid"
        )
    parent: dict[str, str] = {}
    entity_ids: dict[str, str] = {}
    known_mentions: set[str] = set()
    retained_entities: list[dict[str, Any]] = []
    for raw in retained["entities"]:
        if not isinstance(raw, dict) or set(raw) != {
            "entity_id",
            "mention_ids",
            "aliases",
            "feature_candidates",
            "support_event_ids",
        }:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION", "retained entity record is invalid"
            )
        entity_id = _identifier(raw["entity_id"], "retained entity")
        mention_ids = [
            _identifier(item, "retained mention") for item in raw["mention_ids"]
        ]
        if not mention_ids or any(item in known_mentions for item in mention_ids):
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION",
                "retained entity mentions are empty or duplicated",
            )
        root = min(mention_ids)
        for mention_id in mention_ids:
            known_mentions.add(mention_id)
            parent[mention_id] = root
        entity_ids[root] = entity_id
        retained_entities.append(_regional_plain(raw, "retained entity"))
    retained_relations: list[dict[str, Any]] = []
    for raw in retained["relations"]:
        if not isinstance(raw, dict) or set(raw) != {
            "relation_id",
            "predicate",
            "subject_entity_id",
            "object_entity_id",
            "support_event_ids",
        }:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION", "retained relation record is invalid"
            )
        retained_relations.append(_regional_plain(raw, "retained relation"))

    normalized_mentions: list[dict[str, Any]] = []
    for raw in mentions:
        if not isinstance(raw, Mapping) or set(raw) != {
            "mention_id", "aliases", "features", "support_event_ids"
        }:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION", "mention record is invalid"
            )
        mention_id = _identifier(raw["mention_id"], "mention")
        if mention_id in known_mentions:
            raise FieldIntelligenceError(
                "REPRESENTATION_CONFLICT", "mention identity is already retained"
            )
        known_mentions.add(mention_id)
        aliases = [_regional_text(item, "mention alias") for item in raw["aliases"]]
        if not aliases:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION", "mention requires at least one alias"
            )
        features = _regional_plain(dict(raw["features"]), "mention features")
        if not isinstance(features, dict):
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION", "mention features must be an object"
            )
        supports = [_digest(item, "mention support event") for item in raw["support_event_ids"]]
        if not supports:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION", "mention requires identified support"
            )
        normalized_mentions.append(
            {
                "mention_id": mention_id,
                "aliases": aliases,
                "features": features,
                "support_event_ids": supports,
            }
        )

    def pairs(values: Sequence[Sequence[str]], label: str) -> list[list[str]]:
        result: list[list[str]] = []
        for raw in values:
            if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) != 2:
                raise FieldIntelligenceError(
                    "INVALID_REPRESENTATION", f"{label} pair is invalid"
                )
            pair = [
                _identifier(raw[0], f"{label} mention"),
                _identifier(raw[1], f"{label} mention"),
            ]
            if pair[0] == pair[1] or any(item not in known_mentions for item in pair):
                raise FieldIntelligenceError(
                    "INVALID_REPRESENTATION", f"{label} pair references invalid mentions"
                )
            result.append(pair)
        return result

    normalized_same = pairs(same_entity, "same-entity")
    normalized_distinct = pairs(distinct_entity, "distinct-entity")
    normalized_relations: list[dict[str, Any]] = []
    for raw in relations:
        if not isinstance(raw, Mapping) or set(raw) != {
            "subject_mention", "predicate", "object_mention", "support_event_ids"
        }:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION", "relation evidence is invalid"
            )
        subject = _identifier(raw["subject_mention"], "relation subject")
        object_id = _identifier(raw["object_mention"], "relation object")
        if subject not in known_mentions or object_id not in known_mentions:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION", "relation references an unknown mention"
            )
        normalized_relations.append(
            {
                "subject_mention": subject,
                "predicate": _identifier(raw["predicate"], "relation predicate"),
                "object_mention": object_id,
                "support_event_ids": [
                    _digest(item, "relation support event")
                    for item in raw["support_event_ids"]
                ],
            }
        )
    total = (
        len(normalized_mentions) * 2
        + len(normalized_same)
        + len(normalized_distinct)
        + len(normalized_relations)
        + 1
    )
    if total > REGIONAL_KERNEL_MAX_WORK:
        raise FieldIntelligenceError(
            "REGIONAL_CAPACITY", "representation learning exceeds its work profile"
        )
    return _regional_state(
        "representation-learning",
        {
            "mentions": normalized_mentions,
            "same_entity": normalized_same,
            "distinct_entity": normalized_distinct,
            "relations": normalized_relations,
            "retained_entities": retained_entities,
            "retained_relations": retained_relations,
        },
        {
            "stage": "mentions",
            "cursor": 0,
            "parent": parent,
            "entity_ids": entity_ids,
            "entities": retained_entities,
            "relations": retained_relations,
            "entity_positions": {
                row["entity_id"]: index for index, row in enumerate(retained_entities)
            },
            "relation_positions": {
                row["relation_id"]: index for index, row in enumerate(retained_relations)
            },
        },
    )


def regional_query_state(
    query: QueryResult | Mapping[str, Any],
) -> dict[str, Any]:
    """Lower a prepared query into a branch cursor over its frozen records."""

    source_query = _regional_plain(query, "regional query")
    if not isinstance(source_query, dict) or not isinstance(
        source_query.get("branches"), list
    ):
        raise FieldIntelligenceError("INVALID_REGIONAL_TASK", "query source is invalid")
    if len(source_query["branches"]) > REGIONAL_KERNEL_MAX_WORK:
        raise FieldIntelligenceError("REGIONAL_CAPACITY", "too many query branches")
    return _regional_state(
        "query",
        {"query": source_query},
        {"branch_cursor": 0, "branches": []},
    )


def regional_plan_state(
    plan: PlanRecord | Mapping[str, Any],
) -> dict[str, Any]:
    """Lower a plan to a resumable segment cursor with explicit dependencies."""

    source_plan = _regional_plain(plan, "regional plan")
    if not isinstance(source_plan, dict) or not isinstance(
        source_plan.get("segments"), list
    ):
        raise FieldIntelligenceError("INVALID_REGIONAL_TASK", "plan source is invalid")
    if len(source_plan["segments"]) > REGIONAL_KERNEL_MAX_WORK:
        raise FieldIntelligenceError("REGIONAL_CAPACITY", "too many plan segments")
    return _regional_state(
        "plan",
        {"plan": source_plan},
        {"segment_cursor": 0, "segments": []},
    )


def regional_explanation_state(
    query: QueryResult | Mapping[str, Any],
    *,
    allowed_source_revision_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Lower query explanation to a branch cursor reading support IDs only."""

    source_query = _regional_plain(query, "regional explanation query")
    if not isinstance(source_query, dict) or not isinstance(
        source_query.get("branches"), list
    ):
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK", "explanation query source is invalid"
        )
    allowed = tuple(
        _digest(item, "allowed source revision") for item in allowed_source_revision_ids
    )
    return _regional_state(
        "explanation",
        {
            "query": source_query,
            "allowed_source_revision_ids": list(allowed),
        },
        {"branch_cursor": 0, "branches": []},
    )


def regional_revision_state(
    records: Sequence[Mapping[str, Any]],
    changed_premise_ids: Sequence[str],
    *,
    changed_dependency_versions: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Lower dependency revision propagation to a resumable record cursor."""

    rows = _regional_plain(list(records), "revision records")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise FieldIntelligenceError("INVALID_REGIONAL_TASK", "revision records are invalid")
    if len(rows) > REGIONAL_KERNEL_MAX_WORK:
        raise FieldIntelligenceError("REGIONAL_CAPACITY", "too many revision records")
    changed = [_identifier(item, "changed premise") for item in changed_premise_ids]
    versions = {} if changed_dependency_versions is None else dict(changed_dependency_versions)
    for key, value in versions.items():
        _identifier(key, "changed dependency")
        _regional_integer(value, "changed dependency version", minimum=1, maximum=2**53)
    return _regional_state(
        "revision",
        {
            "records": rows,
            "changed_premise_ids": changed,
            "changed_dependency_versions": versions,
        },
        {
            "record_cursor": 0,
            "records": [],
            "stale_ids": [],
            "credit_assignments": [],
            "unaffected_record_ids": [],
        },
    )


def regional_sustained_episode_state(
    *,
    instrument_alias: str,
    location_alias: str,
    access_allowed: bool,
    source_revision_id: str,
    action_target: str,
    action_scope: str,
    numeric_work: Sequence[float],
) -> dict[str, Any]:
    """Build one cross-capability task that waits for identified world events."""

    instrument = _identifier(instrument_alias, "instrument alias")
    location = _identifier(location_alias, "location alias")
    revision = _digest(source_revision_id, "episode source revision")
    target = _identifier(action_target, "episode action target")
    scope = _identifier(action_scope, "episode action scope")
    if not isinstance(access_allowed, bool):
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK", "episode access state must be boolean"
        )
    values = [
        _finite(item, "episode numerical work")
        for item in numeric_work
    ]
    if not values or len(values) > REGIONAL_KERNEL_MAX_WORK:
        raise FieldIntelligenceError(
            "REGIONAL_CAPACITY", "episode numerical work is empty or too large"
        )
    representation = regional_representation_state(
        (
            {
                "mention_id": "episode-instrument",
                "aliases": [instrument],
                "features": {"kind": "instrument"},
                "support_event_ids": [revision],
            },
            {
                "mention_id": "episode-location",
                "aliases": [location],
                "features": {"kind": "location"},
                "support_event_ids": [revision],
            },
        ),
        distinct_entity=(("episode-instrument", "episode-location"),),
        relations=(
            {
                "subject_mention": "episode-instrument",
                "predicate": "located-at",
                "object_mention": "episode-location",
                "support_event_ids": [revision],
            },
        ),
    )
    return _regional_state(
        "sustained-episode",
        {
            "instrument_alias": instrument,
            "location_alias": location,
            "access_allowed": access_allowed,
            "source_revision_id": revision,
            "action_target": target,
            "action_scope": scope,
            "numeric_work": values,
        },
        {
            "stage": "representation",
            "representation": representation,
            "language": None,
            "registry": None,
            "instrument_id": None,
            "location_id": None,
            "plan": None,
            "query": None,
            "explanation": None,
            "numeric_cursor": 0,
            "numeric_total": 0.0,
            "revision_event_id": None,
            "proposal": None,
            "acknowledgment": None,
            "assessment_updates": 0,
            "expression": None,
            "revocation_event_id": None,
            "unaffected_knowledge": {
                "fact_id": "episode-arithmetic",
                "value": "retained",
            },
            "work": 0,
        },
    )


def regional_state(
    source: Any = None,
    *,
    operation: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Dispatch the cognition family builders using one stable entry point.

    ``regional_state`` intentionally accepts the same typed records used by
    the reference APIs.  It only lowers those records; it never executes an
    atlas program or evaluator.
    """

    if operation is None:
        if isinstance(source, Mapping) and "operation" in source:
            operation = str(source["operation"])
            source = source.get("source")
        elif isinstance(source, FieldProgram) or (
            isinstance(source, Mapping) and "steps" in source
        ):
            operation = "program-assessment"
        else:
            mode_hint = kwargs.get("mode", "language")
            operation = "language" if mode_hint in {"express", "interpret"} else str(mode_hint)
    requested_operation = operation
    aliases = {
        "program": "program-assessment",
        "assessment": "program-assessment",
        "promote": "program-promotion",
        "promotion": "program-promotion",
        "program-promote": "program-promotion",
        "language-interpret": "language",
        "language-express": "language",
        "prepared-query": "query",
        "plan-cursor": "plan",
        "explain": "explanation",
        "revision-propagation": "revision",
        "representations": "representation-learning",
        "learn-representations": "representation-learning",
        "learn-construction": "construction-learning",
    }
    operation = aliases.get(operation, operation)
    if requested_operation == "language-express":
        kwargs.setdefault("mode", "express")
    elif requested_operation == "language-interpret":
        kwargs.setdefault("mode", "interpret")
    if operation == "program-assessment":
        if source is None:
            source = kwargs.pop("program", None)
        bindings = kwargs.pop("bindings", None)
        if bindings is None and isinstance(source, Mapping) and "bindings" in source:
            bindings = source["bindings"]
        if bindings is None:
            raise FieldIntelligenceError("PROGRAM_BINDING", "regional bindings are required")
        return regional_program_state(source, bindings, **kwargs)
    if operation == "program-promotion":
        if source is None:
            source = kwargs.pop("programs", ())
        candidate_ids = kwargs.pop("candidate_ids", ())
        return regional_program_promotion_state(cast(Any, source), candidate_ids, **kwargs)
    if operation == "language":
        if source is None:
            source = kwargs.pop("constructions", ())
        mode = kwargs.pop("mode", "interpret")
        return regional_language_state(cast(Any, source), mode=mode, **kwargs)
    if operation == "construction-learning":
        acquisition = (
            source if source is not None else kwargs.pop("acquisition_examples", ())
        )
        validation = kwargs.pop("validation_examples", ())
        return regional_construction_learning_state(
            cast(Any, acquisition), cast(Any, validation), **kwargs
        )
    if operation == "representation-learning":
        mentions = source if source is not None else kwargs.pop("mentions", ())
        return regional_representation_state(cast(Any, mentions), **kwargs)
    if operation == "query":
        return regional_query_state(cast(Any, source), **kwargs)
    if operation == "plan":
        return regional_plan_state(cast(Any, source), **kwargs)
    if operation == "explanation":
        return regional_explanation_state(cast(Any, source), **kwargs)
    if operation == "revision":
        records = source if source is not None else kwargs.pop("records", ())
        changed = kwargs.pop("changed_premise_ids", ())
        return regional_revision_state(cast(Any, records), changed, **kwargs)
    if operation == "sustained-episode":
        payload = dict(source) if isinstance(source, Mapping) else {}
        payload.update(kwargs)
        return regional_sustained_episode_state(**payload)
    raise FieldIntelligenceError(
        "INVALID_REGIONAL_TASK", f"unsupported cognition operation: {operation}"
    )
def _regional_result(operation: str, status: str, **payload: Any) -> dict[str, Any]:
    return {
        "schema": REGIONAL_RESULT_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "operation": operation,
        "status": status,
        **payload,
    }


def _regional_finish(
    current: dict[str, Any],
    status: str,
    payload: Mapping[str, Any],
) -> None:
    current["phase"] = "done"
    current["result"] = _regional_result(current["operation"], status, **dict(payload))


def _regional_program_step(current: dict[str, Any]) -> None:
    source = current["source"]
    program = source["program"]
    continuation = current["continuation"]
    values = dict(continuation["values"])
    if continuation["stage"] == "steps" and continuation["cursor"] == 0:
        if program.get("status") not in {"candidate", "promoted"}:
            _regional_finish(
                current,
                "unsupported",
                {
                    "program_id": program.get("program_id"),
                    "prediction_id": source["prediction_id"],
                    "reason": "PROGRAM_INACTIVE",
                    "prediction_before_outcome": True,
                },
            )
            return
        if not all(
            _regional_guard_matches(guard, source.get("context", {}))
            for guard in program.get("guards", [])
        ):
            _regional_finish(
                current,
                "unsupported",
                {
                    "program_id": program.get("program_id"),
                    "prediction_id": source["prediction_id"],
                    "reason": "guard-not-satisfied",
                    "prediction_before_outcome": True,
                },
            )
            return
    if continuation["stage"] == "steps":
        cursor = _regional_integer(
            continuation["cursor"],
            "regional program cursor",
            maximum=max(0, len(program["steps"])),
        )
        if cursor >= len(program["steps"]):
            prediction = _regional_program_eval(program, source["bindings"])
            continuation["prediction"] = prediction
            if source["outcome"] is None:
                _regional_finish(
                    current,
                    "predicted",
                    {
                        "prediction_id": source["prediction_id"],
                        "program_id": program["program_id"],
                        "program_version": program["version"],
                        "prediction": prediction,
                        "support_event_ids": list(program.get("support_event_ids", [])),
                        "dependency_ids": list(program.get("dependencies", [])),
                        "prediction_before_outcome": True,
                    },
                )
            else:
                continuation["stage"] = "outcome"
            return
        step = program["steps"][cursor]
        try:
            # This is the lowered primitive evaluator.  It intentionally
            # shares no call path with FieldProgram.execute.
            one_step = dict(program)
            one_step["roles"] = list(values.keys())
            one_step["steps"] = [step]
            one_step["outputs"] = [step["output"]]
            result = _regional_program_eval(one_step, values)
            values[step["output"]] = result[step["output"]]
        except (FieldIntelligenceError, KeyError, TypeError, IndexError) as exc:
            reason = exc.code if isinstance(exc, FieldIntelligenceError) else "PROGRAM_DOMAIN"
            _regional_finish(
                current,
                "unsupported",
                {
                    "program_id": program["program_id"],
                    "prediction_id": source["prediction_id"],
                    "reason": reason,
                    "prediction_before_outcome": True,
                },
            )
            return
        continuation["values"] = values
        continuation["cursor"] = cursor + 1
        if continuation["cursor"] == len(program["steps"]):
            continuation["prediction"] = _regional_program_eval(
                program, source["bindings"]
            )
            if source["outcome"] is None:
                _regional_finish(
                    current,
                    "predicted",
                    {
                        "prediction_id": source["prediction_id"],
                        "program_id": program["program_id"],
                        "program_version": program["version"],
                        "prediction": continuation["prediction"],
                        "support_event_ids": list(program.get("support_event_ids", [])),
                        "dependency_ids": list(program.get("dependencies", [])),
                        "prediction_before_outcome": True,
                    },
                )
            else:
                continuation["stage"] = "outcome"
        return
    prediction = continuation.get("prediction")
    outcome = source["outcome"]
    if not isinstance(prediction, dict) or not isinstance(outcome, dict):
        _regional_finish(
            current,
            "unsupported",
            {
                "program_id": program["program_id"],
                "prediction_id": source["prediction_id"],
                "reason": "missing-prediction-or-outcome",
            },
        )
        return
    try:
        squared = _regional_loss(prediction, outcome)
        scale = _finite(
            source.get("loss_scale", 1.0),
            "assessment loss scale",
            positive=True,
        )
        normalized_loss = min(1.0, math.sqrt(squared) / scale)
    except FieldIntelligenceError as exc:
        _regional_finish(
            current,
            "unsupported",
            {
                "program_id": program["program_id"],
                "prediction_id": source["prediction_id"],
                "reason": exc.code,
                "prediction": prediction,
            },
        )
        return
    event_id = source["event_id"]
    assessment_id = sha256_value(
        {
            "event_id": event_id,
            "outcome": outcome,
            "prediction_id": source["prediction_id"],
            "program_id": program["program_id"],
        }
    )
    _regional_finish(
        current,
        "acknowledged",
        {
            "assessment_id": assessment_id,
            "event_id": event_id,
            "prediction_id": source["prediction_id"],
            "program_id": program["program_id"],
            "program_version": program["version"],
            "prediction": prediction,
            "outcome": outcome,
            "normalized_loss": normalized_loss,
            "sequence": source["assessment_sequence"],
            "support_event_ids": list(program.get("support_event_ids", [])),
            "dependency_ids": list(program.get("dependencies", [])),
            "prediction_before_outcome": True,
        },
    )
def _regional_program_promotion_step(current: dict[str, Any]) -> None:
    source = current["source"]
    continuation = current["continuation"]
    programs = source["programs"]
    candidates = source["candidate_ids"]
    cursor = _regional_integer(
        continuation["candidate_cursor"],
        "promotion candidate cursor",
        maximum=len(candidates),
    )
    if cursor < len(candidates):
        candidate_id = candidates[cursor]
        row = next(
            (program for program in programs if program["program_id"] == candidate_id),
            None,
        )
        if row is None:
            raise FieldIntelligenceError(
                "PROGRAM_NOT_FOUND", f"unknown candidate program: {candidate_id}"
            )
        assessments = row.get("assessments", [])
        event_ids = [
            assessment.get("event_id")
            for assessment in assessments
            if isinstance(assessment, dict)
        ]
        loss = sum(
            float(assessment.get("normalized_loss", 1.0))
            for assessment in assessments
            if isinstance(assessment, dict)
        )
        adequate = (
            row.get("status") == "candidate"
            and len(assessments) >= source["minimum_assessments"]
            and len(set(event_ids)) == len(event_ids)
            and assessments
            and loss / len(assessments) <= source["maximum_average_loss"]
            and not row.get("known_exceptions", [])
        )
        continuation["evaluated"].append(
            {
                "program_id": candidate_id,
                "assessment_count": len(assessments),
                "average_loss": 0.0 if not assessments else loss / len(assessments),
                "eligible": bool(adequate),
            }
        )
        if adequate:
            continuation["eligible"].append(candidate_id)
        continuation["candidate_cursor"] = cursor + 1
        return
    if not continuation["eligible"]:
        _regional_finish(
            current,
            "refused",
            {
                "reason": "no-candidate-satisfies-assessment-requirements",
                "evaluated": continuation["evaluated"],
                "programs": programs,
            },
        )
        return
    eligible = {
        row["program_id"]: row
        for row in continuation["evaluated"]
        if row["eligible"]
    }
    selected_id = min(
        continuation["eligible"],
        key=lambda program_id: (
            eligible[program_id]["average_loss"]
            + source["bit_penalty"]
            * next(
                row.get("prefix_code_bits", 1)
                for row in programs
                if row["program_id"] == program_id
            ),
            program_id,
        ),
    )
    promoted_programs: list[dict[str, Any]] = []
    for row in programs:
        if row["program_id"] == selected_id:
            promoted = dict(row)
            promoted["status"] = "promoted"
            promoted["version"] = int(row["version"]) + 1
            promoted_programs.append(promoted)
        else:
            promoted_programs.append(row)
    _regional_finish(
        current,
        "promoted",
        {
            "program_id": selected_id,
            "programs": promoted_programs,
            "evaluated": continuation["evaluated"],
            "support_event_ids": list(
                next(
                    row.get("support_event_ids", [])
                    for row in promoted_programs
                    if row["program_id"] == selected_id
                )
            ),
        },
    )
def _representation_root(parent: Mapping[str, str], mention_id: str) -> str:
    current = mention_id
    traversed = 0
    while True:
        successor = parent.get(current)
        if successor is None:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION", "representation parent is missing"
            )
        if successor == current:
            return current
        current = successor
        traversed += 1
        if traversed > len(parent):
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION", "representation parent cycle detected"
            )


def _regional_representation_step(current: dict[str, Any]) -> None:
    source = current["source"]
    continuation = current["continuation"]
    stage = continuation["stage"]
    cursor = _regional_integer(
        continuation["cursor"], "representation cursor", maximum=REGIONAL_KERNEL_MAX_WORK
    )
    parent = continuation["parent"]
    entity_ids = continuation["entity_ids"]

    if stage == "mentions":
        rows = source["mentions"]
        if cursor < len(rows):
            mention_id = rows[cursor]["mention_id"]
            parent[mention_id] = mention_id
            entity_ids[mention_id] = sha256_value(
                {"kind": "entity", "anchor_mention_id": mention_id}
            )
            continuation["cursor"] = cursor + 1
            return
        continuation["stage"] = "same-entity"
        continuation["cursor"] = 0
        return

    if stage == "same-entity":
        rows = source["same_entity"]
        if cursor < len(rows):
            left, right = rows[cursor]
            left_root = _representation_root(parent, left)
            right_root = _representation_root(parent, right)
            if left_root != right_root:
                retained_ids = {
                    row["entity_id"] for row in source["retained_entities"]
                }
                left_id = entity_ids[left_root]
                right_id = entity_ids[right_root]
                retained = [item for item in (left_id, right_id) if item in retained_ids]
                if len(set(retained)) > 1:
                    raise FieldIntelligenceError(
                        "REPRESENTATION_CONFLICT",
                        "same-entity evidence would merge stable retained identities",
                    )
                root = min(left_root, right_root)
                removed = right_root if root == left_root else left_root
                parent[removed] = root
                entity_ids[root] = retained[0] if retained else min(left_id, right_id)
                entity_ids.pop(removed)
            continuation["cursor"] = cursor + 1
            return
        continuation["stage"] = "distinct-entity"
        continuation["cursor"] = 0
        return

    if stage == "distinct-entity":
        rows = source["distinct_entity"]
        if cursor < len(rows):
            left, right = rows[cursor]
            if _representation_root(parent, left) == _representation_root(parent, right):
                raise FieldIntelligenceError(
                    "REPRESENTATION_CONFLICT",
                    "same-entity and distinct-entity evidence conflict",
                )
            continuation["cursor"] = cursor + 1
            return
        continuation["stage"] = "aggregate"
        continuation["cursor"] = 0
        return

    if stage == "aggregate":
        rows = source["mentions"]
        if cursor < len(rows):
            mention = rows[cursor]
            root = _representation_root(parent, mention["mention_id"])
            entity_id = entity_ids[root]
            positions = continuation["entity_positions"]
            position = positions.get(entity_id)
            if position is None:
                position = len(continuation["entities"])
                positions[entity_id] = position
                continuation["entities"].append(
                    {
                        "entity_id": entity_id,
                        "mention_ids": [],
                        "aliases": [],
                        "feature_candidates": {},
                        "support_event_ids": [],
                    }
                )
            entity = continuation["entities"][position]
            entity["mention_ids"] = sorted(
                set(entity["mention_ids"]) | {mention["mention_id"]}
            )
            entity["aliases"] = sorted(set(entity["aliases"]) | set(mention["aliases"]))
            entity["support_event_ids"] = sorted(
                set(entity["support_event_ids"]) | set(mention["support_event_ids"])
            )
            features = entity["feature_candidates"]
            for name, value in mention["features"].items():
                candidates = list(features.get(name, []))
                encoded = canonical_json_bytes(value)
                if all(canonical_json_bytes(item) != encoded for item in candidates):
                    candidates.append(value)
                    candidates.sort(key=canonical_json_bytes)
                features[name] = candidates
            continuation["cursor"] = cursor + 1
            return
        continuation["stage"] = "relations"
        continuation["cursor"] = 0
        return

    if stage == "relations":
        rows = source["relations"]
        if cursor < len(rows):
            relation = rows[cursor]
            subject_id = entity_ids[
                _representation_root(parent, relation["subject_mention"])
            ]
            object_id = entity_ids[
                _representation_root(parent, relation["object_mention"])
            ]
            relation_id = sha256_value(
                {
                    "kind": "relation",
                    "predicate": relation["predicate"],
                    "subject_entity_id": subject_id,
                    "object_entity_id": object_id,
                }
            )
            positions = continuation["relation_positions"]
            position = positions.get(relation_id)
            if position is None:
                position = len(continuation["relations"])
                positions[relation_id] = position
                continuation["relations"].append(
                    {
                        "relation_id": relation_id,
                        "predicate": relation["predicate"],
                        "subject_entity_id": subject_id,
                        "object_entity_id": object_id,
                        "support_event_ids": [],
                    }
                )
            stored = continuation["relations"][position]
            stored["support_event_ids"] = sorted(
                set(stored["support_event_ids"]) | set(relation["support_event_ids"])
            )
            continuation["cursor"] = cursor + 1
            return
        continuation["stage"] = "finish"
        continuation["cursor"] = 0
        return

    if stage != "finish":
        raise FieldIntelligenceError(
            "INVALID_REPRESENTATION", "representation continuation stage is invalid"
        )
    registry = {
        "schema": REPRESENTATION_REGISTRY_SCHEMA,
        "entities": continuation["entities"],
        "relations": continuation["relations"],
    }
    _regional_finish(
        current,
        "learned",
        {
            "registry": registry,
            "entity_count": len(registry["entities"]),
            "relation_count": len(registry["relations"]),
            "charged_evidence_items": (
                len(source["mentions"])
                + len(source["same_entity"])
                + len(source["distinct_entity"])
                + len(source["relations"])
            ),
        },
    )


def _regional_construction_learning_step(current: dict[str, Any]) -> None:
    source = current["source"]
    continuation = current["continuation"]
    stage = continuation["stage"]
    if stage == "acquisition":
        rows = source["acquisition_examples"]
        cursor = _regional_integer(
            continuation["cursor"], "construction acquisition cursor", maximum=len(rows)
        )
        if cursor < len(rows):
            example = rows[cursor]
            pattern = _regional_induced_pattern(example)
            variants = continuation.setdefault("pattern_variants", [])
            if pattern not in variants:
                variants.append(pattern)
                variants.sort(key=canonical_json_bytes)
            if continuation["pattern"] is None:
                continuation["pattern"] = pattern
            continuation["support_event_ids"].append(example["event_id"])
            continuation["cursor"] = cursor + 1
            return
        continuation["stage"] = "validation"
        continuation["cursor"] = 0
        return
    if stage == "validation":
        rows = source["validation_examples"]
        cursor = _regional_integer(
            continuation["cursor"], "construction validation cursor", maximum=len(rows)
        )
        if cursor < len(rows):
            example = rows[cursor]
            pattern = _regional_induced_pattern(example)
            variants = continuation.setdefault("pattern_variants", [])
            if pattern not in variants:
                _regional_finish(
                    current,
                    "refused",
                    {
                        "reason": "held-out-pattern-mismatch",
                        "construction": None,
                        "validation_event_id": example["event_id"],
                    },
                )
                return
            continuation["validation_event_ids"].append(example["event_id"])
            continuation["cursor"] = cursor + 1
            return
        continuation["stage"] = "finish"
        continuation["cursor"] = 0
        return
    if stage != "finish":
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE", "construction learning stage is invalid"
        )
    construction = {
        "construction_id": source["construction_id"],
        "version": 1,
        "pattern": continuation["pattern"],
        "roles": sorted(source["acquisition_examples"][0]["roles"]),
        "semantic_program_id": source["semantic_program_id"],
        "support_event_ids": sorted(set(continuation["support_event_ids"])),
        "validation_event_ids": sorted(set(continuation["validation_event_ids"])),
        "guards": source["guards"],
        "variable_spans": True,
        "status": "promoted",
    }
    variants = continuation.get("pattern_variants", [])
    if len(variants) > 1:
        construction["pattern_variants"] = variants
    _regional_finish(
        current,
        "learned",
        {
            "construction": construction,
            "acquisition_count": len(source["acquisition_examples"]),
            "validation_count": len(source["validation_examples"]),
            "held_out_validated": True,
        },
    )


def _regional_language_step(current: dict[str, Any]) -> None:
    source = current["source"]
    continuation = current["continuation"]
    rows = source["constructions"]
    context = source["context"]
    if source["mode"] == "express":
        cursor = _regional_integer(
            continuation["construction_cursor"],
            "expression construction cursor",
            maximum=len(rows),
        )
        if cursor < len(rows):
            row = rows[cursor]
            if (
                row.get("semantic_program_id") == source["semantic_program_id"]
                and _regional_matches(row, context)
            ):
                bindings = source["bindings"]
                if set(bindings) == set(row["roles"]):
                    surface_bindings = {
                        name: source["entity_aliases"].get(str(value), [str(value)])[0]
                        for name, value in bindings.items()
                    }
                    expected_bindings = {
                        str(name): str(value) for name, value in bindings.items()
                    }
                    for pattern in _regional_pattern_variants(row):
                        tokens = [
                            surface_bindings[token[1:-1]]
                            if token.startswith("{") and token.endswith("}")
                            else token
                            for token in pattern
                        ]
                        text = " ".join(tokens)
                        for punctuation in (" .", " ,", " ?", " !", " :", " ;"):
                            text = text.replace(punctuation, punctuation[1:])
                        words = _regional_tokens(text)
                        if len(words) > source["max_tokens"]:
                            continue
                        if row.get("variable_spans"):
                            unambiguous = _regional_variable_matches(
                                {"pattern": pattern},
                                words,
                                source["alias_entities"],
                            ) == [expected_bindings]
                        else:
                            interpreted: dict[str, str] = {}
                            unambiguous = True
                            for expected, actual in zip(pattern, words):
                                if expected.startswith("{") and expected.endswith("}"):
                                    candidates = source["alias_entities"].get(actual, [])
                                    if len(candidates) > 1:
                                        unambiguous = False
                                        break
                                    interpreted[expected[1:-1]] = (
                                        candidates[0] if candidates else actual
                                    )
                            unambiguous = unambiguous and interpreted == expected_bindings
                        if unambiguous:
                            continuation["rendered"].append(
                                {
                                    "text": text,
                                    "construction_id": row["construction_id"],
                                    "construction_version": row["version"],
                                    "support_event_ids": list(row["support_event_ids"]),
                                }
                            )
                    continuation["eligible_count"] += 1
            continuation["construction_cursor"] = cursor + 1
            return
        rendered = continuation["rendered"]
        if not rendered:
            status = (
                "budget-exhausted"
                if continuation["eligible_count"]
                else "representation-insufficient"
            )
            _regional_finish(
                current,
                status,
                {
                    "text": None,
                    "semantic_program_id": source["semantic_program_id"],
                    "support_event_ids": [],
                    "unsupported": continuation["eligible_count"] == 0,
                    "reason": (
                        "no-matching-construction"
                        if continuation["eligible_count"] == 0
                        else "token-budget"
                    ),
                },
            )
            return
        selected = min(
            rendered,
            key=lambda row: (len(_regional_tokens(row["text"])), row["text"]),
        )
        _regional_finish(
            current,
            "expressed",
            {
                **selected,
                "semantic_program_id": source["semantic_program_id"],
                "target_blind_stop": True,
            },
        )
        return

    tokens = _regional_tokens(source["text"])
    cursor = _regional_integer(
        continuation["construction_cursor"],
        "interpretation construction cursor",
        maximum=len(rows),
    )
    candidate = continuation.get("candidate")
    if cursor >= len(rows):
        branches: list[dict[str, Any]] = []
        for match in continuation["matches"]:
            branch = dict(match)
            program = source["programs"].get(branch["semantic_program_id"])
            if program is not None:
                try:
                    branch["semantic"] = _regional_program_eval(
                        program, branch["bindings"]
                    )
                except FieldIntelligenceError:
                    branch["semantic"] = None
            else:
                branch["semantic"] = None
            branches.append(branch)
        status = (
            "understood"
            if len(branches) == 1
            else "ambiguous"
            if branches
            else "representation-insufficient"
        )
        _regional_finish(
            current,
            status,
            {
                "text": source["text"],
                "branches": branches,
                "unsupported": not branches,
                "reason": "no-matching-construction" if not branches else None,
            },
        )
        return
    row = rows[cursor]
    if candidate is None:
        if not _regional_matches(row, context):
            continuation["construction_cursor"] = cursor + 1
            return
        if row.get("variable_spans"):
            for pattern in _regional_pattern_variants(row):
                for bindings in _regional_variable_matches(
                    {"pattern": pattern}, tokens, source["alias_entities"]
                ):
                    continuation["matches"].append(
                        {
                            "bindings": bindings,
                            "construction_id": row["construction_id"],
                            "construction_version": row["version"],
                            "semantic_program_id": row["semantic_program_id"],
                            "support_event_ids": list(row["support_event_ids"]),
                        }
                    )
            continuation["construction_cursor"] = cursor + 1
            return
        pattern = _regional_pattern_variants(row)[0]
        candidate = {"bindings": {}, "construction_id": row["construction_id"]}
        continuation["candidate"] = candidate
        continuation["token_cursor"] = 0
        continuation["pattern"] = pattern
        return
    pattern = continuation.get("pattern", row["pattern"])
    token_cursor = _regional_integer(
        continuation["token_cursor"],
        "interpretation token cursor",
        maximum=max(0, len(pattern)),
    )
    if token_cursor >= len(pattern) or token_cursor >= len(tokens):
        continuation["candidate"] = None
        continuation["token_cursor"] = 0
        continuation["pattern"] = None
        continuation["construction_cursor"] = cursor + 1
        if token_cursor == len(pattern) == len(tokens):
            continuation["matches"].append(
                {
                    "bindings": dict(candidate["bindings"]),
                    "construction_id": row["construction_id"],
                    "construction_version": row["version"],
                    "semantic_program_id": row["semantic_program_id"],
                    "support_event_ids": list(row["support_event_ids"]),
                }
            )
        return
    expected = pattern[token_cursor]
    actual = tokens[token_cursor]
    matched = True
    if expected.startswith("{") and expected.endswith("}"):
        role = expected[1:-1]
        candidates = source["alias_entities"].get(actual, [])
        if len(candidates) > 1:
            matched = False
        else:
            resolved = candidates[0] if candidates else actual
            previous = candidate["bindings"].get(role)
            if previous is not None and previous != resolved:
                matched = False
            else:
                candidate["bindings"][role] = resolved
    elif expected != actual:
        matched = False
    if not matched:
        continuation["candidate"] = None
        continuation["token_cursor"] = 0
        continuation["pattern"] = None
        continuation["construction_cursor"] = cursor + 1
    else:
        continuation["token_cursor"] = token_cursor + 1


def _regional_query_step(current: dict[str, Any]) -> None:
    source_query = current["source"]["query"]
    continuation = current["continuation"]
    rows = source_query["branches"]
    cursor = _regional_integer(
        continuation["branch_cursor"],
        "query branch cursor",
        maximum=len(rows),
    )
    if cursor < len(rows):
        raw = rows[cursor]
        if not isinstance(raw, dict):
            raise FieldIntelligenceError("INVALID_REGIONAL_TASK", "query branch is invalid")
        continuation["branches"].append(
            {
                "branch_id": raw.get("branch_id"),
                "status": raw.get("status"),
                "values": dict(raw.get("values", {})),
                "dependency_versions": list(raw.get("active_chart_versions", [])),
                "source_revision_ids": list(raw.get("source_revision_ids", [])),
                "support_event_ids": list(raw.get("source_revision_ids", [])),
                "obligations": list(raw.get("obligations", [])),
            }
        )
        continuation["branch_cursor"] = cursor + 1
        return
    dependencies = [
        row["dependency_versions"]
        for row in continuation["branches"]
    ]
    supports = sorted(
        {
            item
            for row in continuation["branches"]
            for item in row["support_event_ids"]
        }
    )
    _regional_finish(
        current,
        str(source_query.get("status", "unresolved")),
        {
            "query_id": source_query.get("query_id"),
            "field_generation": source_query.get("field_generation"),
            "requested": list(source_query.get("requested", [])),
            "observed": dict(source_query.get("observed", {})),
            "branches": continuation["branches"],
            "dependency_versions": dependencies,
            "support_event_ids": supports,
            "state_sha256": source_query.get("state_sha256"),
        },
    )


def _regional_plan_step(current: dict[str, Any]) -> None:
    source_plan = current["source"]["plan"]
    continuation = current["continuation"]
    rows = source_plan["segments"]
    cursor = _regional_integer(
        continuation["segment_cursor"],
        "plan segment cursor",
        maximum=len(rows),
    )
    if cursor < len(rows):
        raw = rows[cursor]
        if not isinstance(raw, dict):
            raise FieldIntelligenceError("INVALID_REGIONAL_TASK", "plan segment is invalid")
        continuation["segments"].append(
            {
                "segment_id": raw.get("segment_id"),
                "level": raw.get("level"),
                "kind": raw.get("kind"),
                "payload": dict(raw.get("payload", {})),
                "status": raw.get("status"),
                "dependency_versions": list(raw.get("dependency_versions", [])),
                "support_event_ids": list(raw.get("source_revision_ids", [])),
            }
        )
        continuation["segment_cursor"] = cursor + 1
        return
    deps = [
        row["dependency_versions"]
        for row in continuation["segments"]
    ]
    supports = sorted(
        {
            item
            for item in source_plan.get("source_revision_ids", [])
        }.union(
            item
            for row in continuation["segments"]
            for item in row["support_event_ids"]
        )
    )
    _regional_finish(
        current,
        str(source_plan.get("status", "open")),
        {
            "plan_id": source_plan.get("plan_id"),
            "goal_id": source_plan.get("goal_id"),
            "goal": dict(source_plan.get("goal", {})),
            "assumptions": dict(source_plan.get("assumptions", {})),
            "segments": continuation["segments"],
            "dependency_versions": deps,
            "support_event_ids": supports,
        },
    )


def _regional_explanation_step(current: dict[str, Any]) -> None:
    source = current["source"]
    query = source["query"]
    continuation = current["continuation"]
    rows = query["branches"]
    cursor = _regional_integer(
        continuation["branch_cursor"],
        "explanation branch cursor",
        maximum=len(rows),
    )
    if cursor < len(rows):
        raw = rows[cursor]
        sources = list(raw.get("source_revision_ids", []))
        allowed = set(source["allowed_source_revision_ids"])
        visible = sorted(set(sources).intersection(allowed))
        continuation["branches"].append(
            {
                "branch_id": raw.get("branch_id"),
                "status": raw.get("status"),
                "values": {
                    name: raw.get("values", {})[name]
                    for name in query.get("requested", [])
                    if name in raw.get("values", {})
                },
                "dependency_versions": list(raw.get("active_chart_versions", [])),
                "support_event_ids": visible,
                "hidden_support_count": len(set(sources) - set(visible)),
                "obligations": list(raw.get("obligations", [])),
            }
        )
        continuation["branch_cursor"] = cursor + 1
        return
    supports = sorted(
        {
            item
            for row in continuation["branches"]
            for item in row["support_event_ids"]
        }
    )
    _regional_finish(
        current,
        str(query.get("status", "unresolved")),
        {
            "query_id": query.get("query_id"),
            "field_generation": query.get("field_generation"),
            "branches": continuation["branches"],
            "support_event_ids": supports,
            "inspection_kind": "reconstruction",
            "memory_unchanged": query.get("memory_unchanged"),
            "state_sha256": query.get("state_sha256"),
        },
    )


def _regional_revision_step(current: dict[str, Any]) -> None:
    source = current["source"]
    continuation = current["continuation"]
    rows = source["records"]
    cursor = _regional_integer(
        continuation["record_cursor"],
        "revision record cursor",
        maximum=len(rows),
    )
    if cursor < len(rows):
        row = dict(rows[cursor])
        dependencies = set()
        for key in (
            "dependency_ids",
            "support_event_ids",
            "source_revision_ids",
        ):
            values = row.get(key, [])
            if isinstance(values, list):
                dependencies.update(str(item) for item in values)
        pairs = row.get("dependency_versions", [])
        if isinstance(pairs, list):
            dependencies.update(
                str(item[0])
                for item in pairs
                if isinstance(item, list) and len(item) == 2
            )
        changed = set(source["changed_premise_ids"])
        version_changes = source["changed_dependency_versions"]
        matched_dependencies = sorted(dependencies.intersection(changed))
        matched_versions = sorted(
            str(item[0])
            for item in pairs
            if (
                isinstance(item, list)
                and len(item) == 2
                and item[0] in version_changes
                and item[1] != version_changes[item[0]]
            )
        ) if isinstance(pairs, list) else []
        causes = sorted(set(matched_dependencies) | set(matched_versions))
        dependent = bool(causes)
        identity = row.get(
            "record_id", row.get("answer_id", row.get("plan_id"))
        )
        if dependent:
            previous_status = row.get("status")
            row["status"] = "stale"
            if identity is not None:
                continuation["stale_ids"].append(identity)
                continuation["credit_assignments"].append(
                    {
                        "record_id": identity,
                        "status_before": previous_status,
                        "status_after": "stale",
                        "cause_ids": causes,
                        "credit": [
                            {
                                "dependency_id": cause,
                                "numerator": 1,
                                "denominator": len(causes),
                            }
                            for cause in causes
                        ],
                    }
                )
        elif identity is not None:
            continuation["unaffected_record_ids"].append(identity)
        continuation["records"].append(row)
        continuation["record_cursor"] = cursor + 1
        return
    _regional_finish(
        current,
        "revised",
        {
            "records": continuation["records"],
            "stale_ids": continuation["stale_ids"],
            "changed_premise_ids": list(source["changed_premise_ids"]),
            "changed_dependency_versions": dict(source["changed_dependency_versions"]),
            "credit_assignments": continuation["credit_assignments"],
            "unaffected_record_ids": continuation[
                "unaffected_record_ids"
            ],
        },
    )


def _regional_validate_premise_lineage(continuation: Mapping[str, Any]) -> None:
    explanation = continuation.get("explanation")
    if not isinstance(explanation, Mapping):
        return
    raw_ids = explanation.get("premise_revision_ids")
    if raw_ids is None:
        return
    if not isinstance(raw_ids, list) or any(
        not isinstance(item, str)
        or len(item) != 64
        or any(character not in "0123456789abcdef" for character in item)
        for item in raw_ids
    ):
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK",
            "explanation premise revision ids must be lowercase SHA-256 digests",
        )


def _regional_sustained_episode_step(
    current: dict[str, Any],
    arguments: Mapping[str, Any],
) -> bool:
    source = current["source"]
    continuation = current["continuation"]
    _regional_validate_premise_lineage(continuation)
    stage = continuation["stage"]
    continuation["work"] = _regional_integer(
        continuation["work"],
        "episode work",
        maximum=REGIONAL_KERNEL_MAX_WORK * 4,
    ) + 1

    if stage == "representation":
        nested = continuation["representation"]
        _regional_representation_step(nested)
        if nested["phase"] == "done":
            registry = nested["result"]["registry"]
            aliases = {
                alias: row["entity_id"]
                for row in registry["entities"]
                for alias in row["aliases"]
            }
            continuation["registry"] = registry
            continuation["instrument_id"] = aliases[source["instrument_alias"]]
            continuation["location_id"] = aliases[source["location_alias"]]
            construction = {
                "construction_id": "episode-request",
                "version": 1,
                "pattern": ["use", "{instrument}"],
                "roles": ["instrument"],
                "semantic_program_id": "use-instrument",
                "support_event_ids": [source["source_revision_id"]],
                "status": "promoted",
            }
            continuation["language"] = regional_language_state(
                (construction,),
                mode="interpret",
                text=f"use {source['instrument_alias']}",
                representation_registry=registry,
            )
            continuation["stage"] = "interpretation"
        return False

    if stage == "interpretation":
        nested = continuation["language"]
        _regional_language_step(nested)
        if nested["phase"] == "done":
            result = nested["result"]
            if result["status"] != "understood":
                _regional_finish(
                    current,
                    "unresolved",
                    {
                        "reason": "unsupported-language-binding",
                        "language": result,
                        "work": continuation["work"],
                    },
                )
            else:
                continuation["language"] = result
                continuation["stage"] = "planning"
        return False

    if stage == "planning":
        revision = source["source_revision_id"]
        instrument_id = continuation["instrument_id"]
        location_id = continuation["location_id"]
        continuation["plan"] = {
            "record_id": "episode-plan",
            "status": "ready" if source["access_allowed"] else "blocked",
            "instrument_id": instrument_id,
            "location_id": location_id,
            "dependency_ids": [revision],
            "alternatives": ["use-instrument", "request-access"],
        }
        continuation["query"] = {
            "record_id": "episode-query",
            "status": "supported" if source["access_allowed"] else "unresolved",
            "value": {"instrument_id": instrument_id, "location_id": location_id},
            "dependency_ids": [revision],
        }
        continuation["explanation"] = {
            "record_id": "episode-explanation",
            "status": "supported",
            "dependency_ids": [revision],
            "premise_revision_ids": [],
            "support_event_ids": [revision],
        }
        continuation["stage"] = "numeric-work"
        return False

    if stage == "numeric-work":
        cursor = _regional_integer(
            continuation["numeric_cursor"],
            "episode numerical cursor",
            maximum=len(source["numeric_work"]),
        )
        if cursor < len(source["numeric_work"]):
            continuation["numeric_total"] = _finite(
                continuation["numeric_total"] + source["numeric_work"][cursor],
                "episode numerical total",
            )
            continuation["numeric_cursor"] = cursor + 1
        else:
            continuation["stage"] = "await-premise"
        return False

    if stage == "await-premise":
        if arguments.get("operation") != "premise-change":
            return True
        event_id = _digest(arguments.get("event_id"), "premise event")
        if arguments.get("source_revision_id") != source["source_revision_id"]:
            raise FieldIntelligenceError(
                "INVALID_REGIONAL_TASK", "premise event names the wrong source revision"
            )
        access_allowed = arguments.get("access_allowed")
        if not isinstance(access_allowed, bool) or access_allowed == source["access_allowed"]:
            raise FieldIntelligenceError(
                "INVALID_REGIONAL_TASK", "premise event must change the access condition"
            )
        source["access_allowed"] = access_allowed
        continuation["revision_event_id"] = event_id
        continuation["explanation"]["premise_revision_ids"] = [event_id]
        for name in ("plan", "query", "explanation"):
            continuation[name]["status"] = "stale"
        continuation["stage"] = "refine"
        return False

    if stage == "refine":
        proposal_id = sha256_value(
            {
                "instrument_id": continuation["instrument_id"],
                "location_id": continuation["location_id"],
                "revision_event_id": continuation["revision_event_id"],
            }
        )
        continuation["plan"]["status"] = (
            "ready" if source["access_allowed"] else "blocked"
        )
        continuation["proposal"] = {
            "proposal_id": proposal_id,
            "status": "proposed",
            "action": "use-instrument",
            "target": source["action_target"],
            "scope": source["action_scope"],
            "prediction": "succeeded" if source["access_allowed"] else "refused",
            "evidence_revision_ids": [source["source_revision_id"]],
            "authority": "required",
        }
        continuation["stage"] = "await-authorization"
        return False

    if stage == "await-authorization":
        if arguments.get("operation") != "authorize-action":
            return True
        if (
            arguments.get("proposal_id")
            != continuation["proposal"]["proposal_id"]
            or not isinstance(arguments.get("authority"), Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_REGIONAL_TASK",
                "authorization does not satisfy the pending proposal",
            )
        continuation["proposal"]["authorization"] = _regional_plain(
            dict(arguments["authority"]), "episode action authority"
        )
        continuation["proposal"]["status"] = "authorized"
        continuation["stage"] = "await-dispatch"
        return False

    if stage == "await-dispatch":
        if arguments.get("operation") != "dispatch-action":
            return True
        if (
            arguments.get("proposal_id")
            != continuation["proposal"]["proposal_id"]
            or arguments.get("authority")
            != continuation["proposal"].get("authorization")
            or arguments.get("idempotency") != "guaranteed"
        ):
            raise FieldIntelligenceError(
                "INVALID_REGIONAL_TASK",
                "dispatch does not satisfy proposal, authority, and idempotency bindings",
            )
        dispatch = {
            "adapter_id": _identifier(
                arguments.get("adapter_id"), "episode adapter identity"
            ),
            "dispatch_id": _identifier(
                arguments.get("dispatch_id"), "episode dispatch identity"
            ),
            "idempotency": "guaranteed",
            "idempotency_key": _identifier(
                arguments.get("idempotency_key"),
                "episode idempotency key",
            ),
        }
        continuation["proposal"]["dispatch"] = dispatch
        continuation["proposal"]["status"] = "dispatched"
        continuation["stage"] = "await-acknowledgment"
        return False

    if stage == "await-acknowledgment":
        if arguments.get("operation") != "acknowledgment":
            return True
        event_id = _digest(arguments.get("event_id"), "acknowledgment event")
        if (
            arguments.get("proposal_id")
            != continuation["proposal"]["proposal_id"]
            or continuation["proposal"].get("status") != "dispatched"
            or "authority" in arguments
            or "authorized" in arguments
            or arguments.get("status") not in {"succeeded", "failed"}
        ):
            raise FieldIntelligenceError(
                "INVALID_REGIONAL_TASK",
                "acknowledgment does not match a dispatched proposal",
            )
        continuation["acknowledgment"] = {
            "event_id": event_id,
            "proposal_id": arguments["proposal_id"],
            "status": arguments["status"],
        }
        continuation["proposal"]["status"] = "acknowledged"
        continuation["plan"]["status"] = "acknowledged"
        continuation["assessment_updates"] = 1
        continuation["stage"] = "expression"
        return False

    if stage == "expression":
        continuation["query"]["status"] = "supported"
        continuation["explanation"]["status"] = "explained"
        continuation["expression"] = {
            "status": "expressed",
            "text": (
                f"used {source['instrument_alias']} at "
                f"{source['location_alias']}"
            ),
            "support_event_ids": [source["source_revision_id"]],
        }
        continuation["stage"] = "await-revocation"
        return False

    if stage == "await-revocation":
        if arguments.get("operation") != "revocation":
            return True
        event_id = _digest(arguments.get("event_id"), "revocation event")
        if arguments.get("source_revision_id") != source["source_revision_id"]:
            raise FieldIntelligenceError(
                "INVALID_REGIONAL_TASK", "revocation names the wrong source revision"
            )
        continuation["revocation_event_id"] = event_id
        continuation["query"]["status"] = "unsupported"
        continuation["query"]["value"] = None
        continuation["explanation"]["status"] = "source-revoked"
        continuation["expression"]["support_event_ids"] = []
        registry = continuation["registry"]
        for entity in registry["entities"]:
            entity["support_event_ids"] = [
                item
                for item in entity["support_event_ids"]
                if item != source["source_revision_id"]
            ]
        for relation in registry["relations"]:
            relation["support_event_ids"] = [
                item
                for item in relation["support_event_ids"]
                if item != source["source_revision_id"]
            ]
        _regional_finish(
            current,
            "complete",
            {
                "registry": registry,
                "language": continuation["language"],
                "plan": continuation["plan"],
                "query": continuation["query"],
                "explanation": continuation["explanation"],
                "numerical_total": continuation["numeric_total"],
                "proposal": continuation["proposal"],
                "acknowledgment": continuation["acknowledgment"],
                "assessment_updates": continuation["assessment_updates"],
                "expression": continuation["expression"],
                "revision_event_id": continuation["revision_event_id"],
                "revocation_event_id": event_id,
                "unaffected_knowledge": continuation["unaffected_knowledge"],
                "work": continuation["work"],
            },
        )
        return False

    raise FieldIntelligenceError(
        "INVALID_REGIONAL_TASK", f"invalid sustained episode stage: {stage}"
    )


def _regional_step(
    current: dict[str, Any],
    arguments: Mapping[str, Any],
) -> bool:
    operation = current["operation"]
    if operation == "sustained-episode":
        return _regional_sustained_episode_step(current, arguments)
    if arguments:
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK", "cognition operation takes no arguments"
        )
    if operation == "program-assessment":
        _regional_program_step(current)
    elif operation == "program-promotion":
        _regional_program_promotion_step(current)
    elif operation == "construction-learning":
        _regional_construction_learning_step(current)
    elif operation == "language":
        _regional_language_step(current)
    elif operation == "representation-learning":
        _regional_representation_step(current)
    elif operation == "query":
        _regional_query_step(current)
    elif operation == "plan":
        _regional_plan_step(current)
    elif operation == "explanation":
        _regional_explanation_step(current)
    elif operation == "revision":
        _regional_revision_step(current)
    else:
        raise FieldIntelligenceError(
            "INVALID_REGIONAL_TASK", f"unsupported cognition operation: {operation}"
        )
    return False


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance one cognition task using bounded direct regional operations."""
    if isinstance(state, Mapping) and state.get("schema") == SEMANTIC_STATE_SCHEMA:
        return semantic_cognition_kernel(state, arguments, quantum)

    if (
        not isinstance(state, Mapping)
        or state.get("schema") != REGIONAL_STATE_SCHEMA
        or state.get("family") != REGIONAL_KERNEL_NAME
        or set(state) != {
            "schema",
            "family",
            "operation",
            "phase",
            "source",
            "continuation",
            "result",
        }
    ):
        raise FieldIntelligenceError("INVALID_REGIONAL_TASK", "regional cognition state is invalid")
    bound = _regional_integer(
        quantum,
        "regional cognition quantum",
        minimum=1,
        maximum=REGIONAL_KERNEL_MAX_WORK,
    )
    current = _regional_plain(dict(state), "regional cognition state")
    if current["phase"] == "done":
        return KernelResult(state=current, status="done", work=0, output=current["result"])
    if current["phase"] != "running":
        raise FieldIntelligenceError("INVALID_REGIONAL_TASK", "regional cognition phase is invalid")
    work = 0
    while work < bound and current["phase"] == "running":
        blocked = _regional_step(current, arguments)
        work += 1
        if blocked:
            return KernelResult(
                state=current,
                status="blocked",
                work=max(1, work),
                output=_regional_result(
                    current["operation"],
                    "waiting",
                    stage=current["continuation"]["stage"],
                ),
            )
    if current["phase"] == "running":
        return KernelResult(state=current, status="yield", work=max(1, work))
    return KernelResult(
        state=current,
        status="done",
        work=max(1, work),
        output=current["result"],
    )


def regional_kernel_factory() -> Any:
    """Return the fixed catalog callable without capturing adaptive state."""

    return regional_kernel

class FieldCognition:
    def __init__(self, atlas: FieldAtlas | None = None) -> None:
        self.atlas = atlas or FieldAtlas()

    @staticmethod
    def _matrix(readout: ActionReadout, order: Sequence[str]) -> torch.Tensor:
        index = {name: position for position, name in enumerate(order)}
        unknown = set(readout.variables) - set(order)
        if unknown:
            raise FieldIntelligenceError(
                "READOUT_SCOPE",
                "readout references variables outside the active field problem",
                details={"unknown": sorted(unknown)},
            )
        matrix = torch.zeros((len(readout.labels), len(order)), dtype=torch.float64)
        for row_index, coefficients in enumerate(readout.coefficients):
            for name, value in coefficients.items():
                matrix[row_index, index[name]] = value
        return matrix

    @staticmethod
    def _error_map(readout: ActionReadout, observed_count: int) -> torch.Tensor:
        if readout.observation_error_map is None:
            return torch.eye(observed_count, dtype=torch.float64)
        matrix = torch.tensor(readout.observation_error_map, dtype=torch.float64)
        if matrix.shape[0] != observed_count:
            raise FieldIntelligenceError(
                "READOUT_ERROR_MAP",
                "error-map output rows must match observed-coordinate count",
            )
        return matrix

    def certify_action(
        self,
        state: AtlasState,
        *,
        observed: Mapping[str, float],
        readout: ActionReadout,
        context: Mapping[str, Any] | None = None,
        valid_source_revision_ids: frozenset[str] | None = None,
        authority_current: bool = False,
        task_feasible: bool = True,
        model_applicable: bool = True,
        method: str = "auto",
        tolerance: float = 1e-10,
        prepared_query: QueryResult | None = None,
    ) -> ActionDecision:
        requested = tuple(name for name in readout.variables if name not in observed)
        if not requested:
            requested = readout.variables
        for name, value in observed.items():
            spec = state.variable(name)
            if not spec.contains(float(value), radius=readout.observed_error_radius):
                model_applicable = False
        if prepared_query is None:
            raise FieldIntelligenceError(
                "PREPARED_QUERY_REQUIRED",
                "action certification requires a prepared resonant query",
            )
        query = prepared_query
        if query.query_id is None or query.checkpoint_receipt is None:
            raise FieldIntelligenceError(
                "INVALID_PREPARED_QUERY", "prepared query lacks checkpoint receipt"
            )
        if query.observed != observed:
            raise FieldIntelligenceError(
                "INVALID_PREPARED_QUERY", "prepared query observations do not match action"
            )
        if valid_source_revision_ids is not None:
            source_ids = {
                source
                for branch in query.branches
                for source in branch.source_revision_ids
            }
            if not source_ids.issubset(valid_source_revision_ids):
                raise FieldIntelligenceError(
                    "INVALID_PREPARED_QUERY", "prepared query source authority is stale"
                )
        if not set(requested).issubset(query.requested):
            raise FieldIntelligenceError(
                "INVALID_PREPARED_QUERY", "prepared query requested coordinates do not match action"
            )
        if context is not None and _json(context, "action context") != query.context:
            raise FieldIntelligenceError(
                "INVALID_PREPARED_QUERY", "prepared query context does not match action"
            )
        certificates: list[ActionBranchCertificate] = []
        readout_payload = readout.as_dict()
        matrix_cache: dict[tuple[str, ...], torch.Tensor] = {}
        error_map_cache: dict[int, torch.Tensor] = {}
        for branch in query.branches:
            if not branch.values or not branch.response:
                certificates.append(
                    ActionBranchCertificate(
                        branch_id=branch.branch_id,
                        nominal_action=None,
                        certified_action=None,
                        scores={},
                        competitors=(),
                        nominal_margins=(),
                        input_sensitivity_norms=(),
                        input_worst_margins=(),
                        solver_allowances=(),
                        combined_worst_margins=(),
                        numerical_guards=(),
                        limiting_competitor=None,
                        stability_radius=None,
                        worst_case_observation_delta=(),
                        numerical_valid=False,
                        evidence_valid=False,
                        model_applicable=model_applicable,
                        feasible=task_feasible,
                        authorized=authority_current,
                        commitment_eligible=False,
                        refusal_reasons=tuple(dict.fromkeys((*branch.obligations, "no-solution"))),
                        dependency_sha256=sha256_value(
                            {"branch": branch.branch_id, "readout": readout_payload}
                        ),
                    )
                )
                continue
            matrix = matrix_cache.get(branch.variable_order)
            if matrix is None:
                matrix = self._matrix(readout, branch.variable_order)
                matrix_cache[branch.variable_order] = matrix
            value = torch.tensor(
                [branch.values[name] for name in branch.variable_order], dtype=torch.float64
            )
            response = torch.tensor(branch.response, dtype=torch.float64)
            observed_count = len(branch.observed_order)
            error_map = error_map_cache.get(observed_count)
            if error_map is None:
                error_map = self._error_map(readout, observed_count)
                error_map_cache[observed_count] = error_map
            scale = float(matrix.abs().max()) or 1.0
            normalized = matrix / scale
            scores = normalized @ value
            maximum = float(scores.max())
            score_guard = 64 * torch.finfo(torch.float64).eps * max(
                1.0, float(scores.abs().max())
            )
            winners = [
                index for index, score in enumerate(scores) if maximum - float(score) <= score_guard
            ]
            if len(winners) != 1:
                nominal_index = winners[0]
                unique = False
            else:
                nominal_index = winners[0]
                unique = True
            competitors = [index for index in range(len(scores)) if index != nominal_index]
            differences = normalized[nominal_index] - normalized[competitors]
            gaps = differences @ value
            sensitivities = differences @ response @ error_map
            sensitivity_norms = torch.linalg.vector_norm(sensitivities, dim=1)
            input_worst = gaps - readout.observed_error_radius * sensitivity_norms
            solver_error = branch.solution_error_bound or 0.0
            solver_allowances = torch.linalg.vector_norm(differences, dim=1) * solver_error
            combined = input_worst - solver_allowances
            evaluation_scale = (
                differences.abs() @ value.abs()
                + readout.observed_error_radius
                * torch.linalg.vector_norm(differences.abs() @ response.abs() @ error_map.abs(), dim=1)
                + solver_allowances
            )
            guards = 64 * torch.finfo(torch.float64).eps * evaluation_scale + torch.finfo(torch.float64).tiny
            robust = unique and bool(torch.all(combined > guards))
            limiting = int(combined.argmin()) if competitors else 0
            norm = float(sensitivity_norms[limiting]) if competitors else 0.0
            if norm > 0:
                delta = -readout.observed_error_radius * sensitivities[limiting] / norm
            else:
                delta = torch.zeros(error_map.shape[1], dtype=torch.float64)
            distances = [
                max(0.0, float(gap / sensitivity))
                if float(sensitivity) > 0
                else (math.inf if float(gap) > 0 else 0.0)
                for gap, sensitivity in zip(gaps, sensitivity_norms)
            ]
            stability_radius = min(distances, default=math.inf)
            numerical_valid = branch.numerical_settled and all(
                math.isfinite(value)
                for value in (
                    *scores.tolist(),
                    *gaps.tolist(),
                    *combined.tolist(),
                    *guards.tolist(),
                )
            )
            evidence_valid = branch.epistemically_supportable
            eligible = all(
                (
                    robust,
                    numerical_valid,
                    evidence_valid,
                    model_applicable,
                    task_feasible,
                    authority_current,
                )
            )
            reasons: list[str] = []
            for reason, failed in (
                ("input-sensitive-action", not robust),
                ("numerical", not numerical_valid),
                ("evidence", not evidence_valid),
                ("model-applicability", not model_applicable),
                ("task-feasibility", not task_feasible),
                ("authority", not authority_current),
            ):
                if failed:
                    reasons.append(reason)
            dependency = {
                "branch_id": branch.branch_id,
                "chart_versions": [list(row) for row in branch.active_chart_versions],
                "field_generation": state.generation,
                "observed_order": list(branch.observed_order),
                "readout": readout_payload,
                "revocation_generation": state.revocation_generation,
                "source_revision_ids": list(branch.source_revision_ids),
            }
            certificates.append(
                ActionBranchCertificate(
                    branch_id=branch.branch_id,
                    nominal_action=readout.labels[nominal_index],
                    certified_action=readout.labels[nominal_index] if robust else None,
                    scores={
                        label: float(score) for label, score in zip(readout.labels, scores)
                    },
                    competitors=tuple(readout.labels[index] for index in competitors),
                    nominal_margins=tuple(float(value) for value in gaps),
                    input_sensitivity_norms=tuple(float(value) for value in sensitivity_norms),
                    input_worst_margins=tuple(float(value) for value in input_worst),
                    solver_allowances=tuple(float(value) for value in solver_allowances),
                    combined_worst_margins=tuple(float(value) for value in combined),
                    numerical_guards=tuple(float(value) for value in guards),
                    limiting_competitor=(
                        readout.labels[competitors[limiting]] if competitors else None
                    ),
                    stability_radius=(
                        stability_radius if math.isfinite(stability_radius) else None
                    ),
                    worst_case_observation_delta=tuple(float(value) for value in delta),
                    numerical_valid=numerical_valid,
                    evidence_valid=evidence_valid,
                    model_applicable=model_applicable,
                    feasible=task_feasible,
                    authorized=authority_current,
                    commitment_eligible=eligible,
                    refusal_reasons=tuple(reasons),
                    dependency_sha256=sha256_value(dependency),
                )
            )
        committed = {
            row.certified_action
            for row in certificates
            if row.commitment_eligible and row.certified_action is not None
        }
        if len(committed) == 1 and all(row.commitment_eligible for row in certificates):
            status = "commitment-eligible"
            action = next(iter(committed))
            obligations: tuple[str, ...] = ()
        elif certificates and all(row.certified_action is not None for row in certificates):
            status = "supported-proposal"
            action = None
            obligations = tuple(
                sorted({reason for row in certificates for reason in row.refusal_reasons})
            )
        else:
            status = "unresolved"
            action = None
            obligations = tuple(
                sorted({reason for row in certificates for reason in row.refusal_reasons})
            ) or ("no-applicable-branch",)
        return ActionDecision(
            status=status,
            query=query,
            readout=readout_payload,
            certificates=tuple(certificates),
            committed_action=action,
            obligations=obligations,
        )

    def retain_prediction(
        self,
        state: AtlasState,
        *,
        query: QueryResult,
        branch: BranchSolution,
        goal_id: str | None,
        authority_generation: int,
        operation_id: str | None = None,
        status: str = "predicted",
    ) -> tuple[AtlasState, PredictionRecord]:
        if branch not in query.branches or not branch.values:
            raise FieldIntelligenceError(
                "INVALID_PREDICTION", "prediction must retain a solved query branch"
            )
        identity = {
            "authority_generation": authority_generation,
            "branch_id": branch.branch_id,
            "field_generation": state.generation,
            "goal_id": goal_id,
            "operation_id": operation_id,
            "query": query.as_dict(),
        }
        prediction = PredictionRecord(
            prediction_id=sha256_value(identity),
            field_generation=state.generation,
            branch_id=branch.branch_id,
            query={
                "context": dict(query.context),
                "observed": dict(query.observed),
                "requested": list(query.requested),
            },
            predicted={name: branch.values[name] for name in query.requested},
            dependency_versions=branch.active_chart_versions,
            source_revision_ids=branch.source_revision_ids,
            goal_id=goal_id,
            authority_generation=authority_generation,
            operation_id=operation_id,
            status=status,
        )
        existing = next(
            (row for row in state.predictions if row.prediction_id == prediction.prediction_id),
            None,
        )
        if existing is not None:
            if existing != prediction:
                raise FieldIntelligenceError(
                    "PREDICTION_CONFLICT", "prediction identity has different semantics"
                )
            return state, existing
        successor = state.with_transition(
            "prediction-retained",
            {"prediction_id": prediction.prediction_id},
            predictions=(*state.predictions, prediction),
        )
        return successor, prediction

    def resolve_prediction(
        self,
        state: AtlasState,
        *,
        prediction_id: str,
        actual: Mapping[str, Any],
        attribution_candidates: Sequence[str],
    ) -> tuple[AtlasState, PredictionRecord]:
        _digest(prediction_id, "prediction_id")
        try:
            prediction = next(
                row for row in state.predictions if row.prediction_id == prediction_id
            )
        except StopIteration as exc:
            raise FieldIntelligenceError(
                "PREDICTION_NOT_FOUND", "prediction identity is unknown"
            ) from exc
        if prediction.status == "acknowledged":
            if prediction.actual != _json(dict(actual), "actual outcome"):
                raise FieldIntelligenceError(
                    "OUTCOME_CONFLICT", "prediction already has a different actual outcome"
                )
            return state, prediction
        candidates = tuple(_identifier(row, "attribution candidate") for row in attribution_candidates)
        resolved = replace(
            prediction,
            actual=_json(dict(actual), "actual outcome"),
            attribution_candidates=candidates,
            status="acknowledged",
        )
        predictions = tuple(
            resolved if row.prediction_id == prediction_id else row for row in state.predictions
        )
        successor = state.with_transition(
            "prediction-acknowledged",
            {
                "attribution_candidates": list(candidates),
                "prediction_id": prediction_id,
            },
            predictions=predictions,
        )
        return successor, resolved

    @staticmethod
    def _candidate_programs(
        *,
        problem_id: str,
        input_roles: Sequence[str],
        output_role: str,
        support_event_ids: Sequence[str],
        guards: Sequence[Guard],
        max_candidates: int,
    ) -> tuple[FieldProgram, ...]:
        roles = tuple(input_roles)
        if not roles or len(set(roles)) != len(roles) or output_role in roles:
            raise FieldIntelligenceError(
                "INVALID_STRUCTURE_PROBLEM", "input roles and output role must be distinct"
            )

        def operation_rows() -> Any:
            for role in roles:
                yield "identity", (role,), None
                yield "negate", (role,), None
                yield "absolute", (role,), None
            for left_index, left in enumerate(roles):
                for right in roles[left_index + 1 :]:
                    yield "add", (left, right), None
                    yield "subtract", (left, right), None
                    yield "subtract", (right, left), None
                    yield "multiply", (left, right), None
                    yield "divide", (left, right), None
                    yield "divide", (right, left), None

        result: list[FieldProgram] = []
        for index, (operation, inputs, literal) in enumerate(operation_rows()):
            if index >= max_candidates:
                break
            program_id = f"{problem_id}:candidate:{index:03d}:{operation}"
            result.append(
                FieldProgram(
                    program_id=program_id,
                    version=1,
                    roles=roles,
                    steps=(
                        PrimitiveStep(
                            operation=operation,
                            output=output_role,
                            inputs=inputs,
                            literal=literal,
                        ),
                    ),
                    outputs=(output_role,),
                    guards=tuple(guards),
                    support_event_ids=tuple(support_event_ids),
                    prefix_code_bits=max(
                        1, 4 + len(inputs) * 2 + index.bit_length()
                    ),
                    status="candidate",
                )
            )
        return tuple(result)

    def propose_relational_structure(
        self,
        state: AtlasState,
        *,
        problem_id: str,
        input_roles: Sequence[str],
        output_role: str,
        support_event_ids: Sequence[str],
        guards: Sequence[Guard] = (),
        max_candidates: int = 32,
    ) -> tuple[AtlasState, tuple[str, ...]]:
        _identifier(problem_id, "structure problem_id")
        if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 1:
            raise FieldIntelligenceError(
                "INVALID_STRUCTURE_PROBLEM", "candidate budget must be positive"
            )
        candidates = self._candidate_programs(
            problem_id=problem_id,
            input_roles=input_roles,
            output_role=output_role,
            support_event_ids=support_event_ids,
            guards=guards,
            max_candidates=max_candidates,
        )
        existing_ids = {row.program_id for row in state.programs}
        additions = tuple(row for row in candidates if row.program_id not in existing_ids)
        if not additions:
            return state, tuple(row.program_id for row in candidates)
        successor = state.with_transition(
            "structure-candidates-proposed",
            {
                "candidate_ids": [row.program_id for row in additions],
                "problem_id": problem_id,
            },
            programs=(*state.programs, *additions),
        )
        return successor, tuple(row.program_id for row in additions)

    def begin_program_assessment(
        self,
        state: AtlasState,
        *,
        program_id: str,
        bindings: Mapping[str, Any],
        authority_generation: int,
    ) -> tuple[AtlasState, PredictionRecord]:
        program = state.program(program_id)
        if program.status not in {"candidate", "promoted"}:
            raise FieldIntelligenceError(
                "PROGRAM_INACTIVE", "only candidate or promoted programs can predict"
            )
        predicted = program.execute(bindings)
        identity = {
            "bindings": dict(bindings),
            "field_generation": state.generation,
            "program_id": program_id,
            "program_version": program.version,
            "sequence": len(program.assessments) + 1,
        }
        prediction = PredictionRecord(
            prediction_id=sha256_value(identity),
            field_generation=state.generation,
            branch_id=f"program:{program_id}:{program.version}",
            query={"bindings": dict(bindings), "program_id": program_id},
            predicted=predicted,
            dependency_versions=((f"program:{program_id}", program.version),),
            source_revision_ids=(),
            goal_id=None,
            authority_generation=authority_generation,
        )
        if any(row.prediction_id == prediction.prediction_id for row in state.predictions):
            existing = next(
                row for row in state.predictions if row.prediction_id == prediction.prediction_id
            )
            if existing != prediction:
                raise FieldIntelligenceError(
                    "PREDICTION_CONFLICT", "program prediction identity conflicts"
                )
            return state, existing
        successor = state.with_transition(
            "prequential-prediction",
            {"prediction_id": prediction.prediction_id, "program_id": program_id},
            predictions=(*state.predictions, prediction),
        )
        return successor, prediction

    def resolve_program_assessment(
        self,
        state: AtlasState,
        *,
        program_id: str,
        prediction_id: str,
        outcome: Mapping[str, Any],
        event_id: str,
        loss_scale: float,
    ) -> tuple[AtlasState, AssessmentRecord]:
        program = state.program(program_id)
        try:
            prediction = next(
                row for row in state.predictions if row.prediction_id == prediction_id
            )
        except StopIteration as exc:
            raise FieldIntelligenceError(
                "PREDICTION_NOT_FOUND", "prequential prediction is unknown"
            ) from exc
        if prediction.query.get("program_id") != program_id:
            raise FieldIntelligenceError(
                "ASSESSMENT_CONFLICT", "prediction belongs to a different program"
            )
        normalized_outcome = _json(dict(outcome), "assessment outcome")
        if set(normalized_outcome) != set(prediction.predicted):
            raise FieldIntelligenceError(
                "ASSESSMENT_CONFLICT", "outcome keys differ from the frozen prediction"
            )
        normalized_event_id = _digest(event_id, "assessment event_id")
        if prediction.status == "acknowledged":
            existing = next(
                (
                    row
                    for row in program.assessments
                    if row.event_id == normalized_event_id
                    and row.outcome == normalized_outcome
                    and row.prediction == prediction.predicted
                ),
                None,
            )
            if existing is not None and prediction.actual == normalized_outcome:
                return state, existing
            raise FieldIntelligenceError(
                "ASSESSMENT_CONFLICT",
                "prequential prediction already has an acknowledged outcome",
            )
        if prediction.status != "predicted" or prediction.actual is not None:
            raise FieldIntelligenceError(
                "ASSESSMENT_CONFLICT",
                "only an unresolved prediction can receive an assessment",
            )
        squared = 0.0
        for name, predicted_value in prediction.predicted.items():
            actual_value = normalized_outcome[name]
            if isinstance(predicted_value, bool) or isinstance(actual_value, bool):
                squared += 0.0 if predicted_value == actual_value else 1.0
            elif isinstance(predicted_value, (int, float)) and isinstance(actual_value, (int, float)):
                difference = float(predicted_value) - float(actual_value)
                squared += difference * difference
            else:
                squared += 0.0 if predicted_value == actual_value else 1.0
        scale = _finite(loss_scale, "assessment loss scale", positive=True)
        loss = min(1.0, math.sqrt(squared) / scale)
        record = AssessmentRecord(
            assessment_id=sha256_value(
                {
                    "event_id": event_id,
                    "outcome": normalized_outcome,
                    "prediction_id": prediction_id,
                    "program_id": program_id,
                }
            ),
            prediction=dict(prediction.predicted),
            outcome=normalized_outcome,
            normalized_loss=loss,
            event_id=normalized_event_id,
            sequence=len(program.assessments) + 1,
        )
        updated_program = program.record_assessment(record)
        updated_prediction = replace(
            prediction,
            actual=normalized_outcome,
            status="acknowledged",
            attribution_candidates=("program-semantics", "input-binding", "representation"),
        )
        programs = tuple(
            updated_program if row.program_id == program_id else row for row in state.programs
        )
        predictions = tuple(
            updated_prediction if row.prediction_id == prediction_id else row
            for row in state.predictions
        )
        successor = state.with_transition(
            "prequential-outcome",
            {
                "assessment_id": record.assessment_id,
                "normalized_loss": record.normalized_loss,
                "program_id": program_id,
            },
            programs=programs,
            predictions=predictions,
        )
        return successor, record

    def promote_program(
        self,
        state: AtlasState,
        *,
        candidate_ids: Sequence[str],
        minimum_assessments: int,
        maximum_average_loss: float,
        bit_penalty: float,
    ) -> tuple[AtlasState, FieldProgram]:
        if isinstance(minimum_assessments, bool) or not isinstance(minimum_assessments, int) or minimum_assessments < 1:
            raise FieldIntelligenceError(
                "INVALID_PROMOTION", "minimum assessments must be positive"
            )
        threshold = _finite(maximum_average_loss, "maximum average loss")
        if not 0 <= threshold <= 1:
            raise FieldIntelligenceError(
                "INVALID_PROMOTION", "maximum average loss must lie in [0, 1]"
            )
        candidates = [state.program(program_id) for program_id in candidate_ids]
        if any(row.status != "candidate" for row in candidates):
            raise FieldIntelligenceError(
                "PROMOTION_UNSUPPORTED",
                "only active candidates can be promoted",
            )
        adequate = [
            row
            for row in candidates
            if len(row.assessments) >= minimum_assessments
            and len({item.event_id for item in row.assessments})
            == len(row.assessments)
            and row.prequential_loss / len(row.assessments) <= threshold
            and not row.known_exceptions
        ]
        if not adequate:
            raise FieldIntelligenceError(
                "PROMOTION_UNSUPPORTED",
                "no candidate satisfies the preserved assessment requirements",
            )
        selected = min(
            adequate,
            key=lambda row: (row.selection_score(bit_penalty=bit_penalty), row.program_id),
        )
        promoted = replace(selected, status="promoted", version=selected.version + 1)
        programs = tuple(
            promoted if row.program_id == selected.program_id else row for row in state.programs
        )
        successor = state.with_transition(
            "program-promoted",
            {
                "program_id": promoted.program_id,
                "selection_score": promoted.selection_score(bit_penalty=bit_penalty),
            },
            programs=programs,
        )
        return successor, promoted

    def propose_language_construction(
        self,
        state: AtlasState,
        *,
        construction_id: str,
        examples: Sequence[Mapping[str, Any]],
        semantic_program_id: str,
        guards: Sequence[Guard] = (),
    ) -> tuple[AtlasState, LanguageConstruction]:
        state.program(semantic_program_id)
        if len(examples) < 2:
            raise FieldIntelligenceError(
                "CONSTRUCTION_UNSUPPORTED", "at least two aligned episodes are required"
            )
        normalized_patterns: list[tuple[str, ...]] = []
        roles: tuple[str, ...] | None = None
        support: list[str] = []
        for example in examples:
            if set(example) != {"event_id", "roles", "text"}:
                raise FieldIntelligenceError(
                    "INVALID_LANGUAGE", "construction example schema is closed"
                )
            event_id = _digest(example["event_id"], "construction event_id")
            bindings = example["roles"]
            if not isinstance(bindings, Mapping) or not bindings:
                raise FieldIntelligenceError(
                    "INVALID_LANGUAGE", "construction roles must be a nonempty object"
                )
            role_order = tuple(sorted(_identifier(name, "construction role") for name in bindings))
            if roles is None:
                roles = role_order
            elif roles != role_order:
                raise FieldIntelligenceError(
                    "CONSTRUCTION_UNSUPPORTED", "aligned examples must share role identities"
                )
            tokens = list(tokenize(example["text"]))
            claimed: set[int] = set()
            for role in role_order:
                value_tokens = tokenize(str(bindings[role]))
                if len(value_tokens) != 1:
                    raise FieldIntelligenceError(
                        "CONSTRUCTION_UNSUPPORTED",
                        "first construction learner admits one-token role spans",
                    )
                matches = [
                    index
                    for index, token in enumerate(tokens)
                    if token == value_tokens[0] and index not in claimed
                ]
                if len(matches) != 1:
                    raise FieldIntelligenceError(
                        "CONSTRUCTION_UNSUPPORTED",
                        "each role value must occur exactly once in every aligned utterance",
                        details={"role": role},
                    )
                index = matches[0]
                tokens[index] = "{" + role + "}"
                claimed.add(index)
            normalized_patterns.append(tuple(tokens))
            support.append(event_id)
        if len(set(normalized_patterns)) != 1 or roles is None:
            raise FieldIntelligenceError(
                "CONSTRUCTION_UNSUPPORTED",
                "examples do not yield one consequence-preserving aligned pattern",
            )
        construction = LanguageConstruction(
            construction_id=construction_id,
            version=1,
            pattern=normalized_patterns[0],
            roles=roles,
            semantic_program_id=semantic_program_id,
            support_event_ids=tuple(support),
            guards=tuple(guards),
            status="candidate",
        )
        successor = self.atlas.add_construction(state, construction)
        return successor, construction

    def assess_language_construction(
        self,
        state: AtlasState,
        *,
        construction_id: str,
        text: str,
        expected_roles: Mapping[str, str],
        event_id: str,
    ) -> tuple[AtlasState, AssessmentRecord]:
        construction = state.construction(construction_id)
        normalized_event_id = _digest(event_id, "language assessment event_id")
        existing = next(
            (
                row
                for row in construction.assessments
                if row.event_id == normalized_event_id
            ),
            None,
        )
        if existing is not None:
            expected = _json(
                dict(expected_roles), "language assessment outcome"
            )
            predicted = construction.interpret(text)
            normalized_prediction = (
                {} if predicted is None else _json(dict(predicted), "language prediction")
            )
            if existing.outcome == expected and existing.prediction == normalized_prediction:
                return state, existing
            raise FieldIntelligenceError(
                "ASSESSMENT_CONFLICT",
                "language evidence event already has different assessment semantics",
            )
        predicted = construction.interpret(text)
        loss = 0.0 if predicted == dict(expected_roles) else 1.0
        record = AssessmentRecord(
            assessment_id=sha256_value(
                {
                    "construction_id": construction_id,
                    "event_id": event_id,
                    "expected_roles": dict(expected_roles),
                    "text": text,
                }
            ),
            prediction={} if predicted is None else dict(predicted),
            outcome=dict(expected_roles),
            normalized_loss=loss,
            event_id=normalized_event_id,
            sequence=len(construction.assessments) + 1,
        )
        updated = construction.record_assessment(record)
        constructions = tuple(
            updated if row.construction_id == construction_id else row
            for row in state.constructions
        )
        successor = state.with_transition(
            "construction-assessed",
            {
                "assessment_id": record.assessment_id,
                "construction_id": construction_id,
                "loss": loss,
            },
            constructions=constructions,
        )
        return successor, record

    def promote_language_construction(
        self,
        state: AtlasState,
        *,
        construction_id: str,
        minimum_assessments: int = 1,
    ) -> tuple[AtlasState, LanguageConstruction]:
        if (
            isinstance(minimum_assessments, bool)
            or not isinstance(minimum_assessments, int)
            or minimum_assessments < 1
        ):
            raise FieldIntelligenceError(
                "INVALID_PROMOTION", "minimum assessments must be positive"
            )
        construction = state.construction(construction_id)
        if construction.status != "candidate":
            raise FieldIntelligenceError(
                "PROMOTION_UNSUPPORTED",
                "only an active candidate construction can be promoted",
            )
        if (
            len(construction.assessments) < minimum_assessments
            or len({row.event_id for row in construction.assessments})
            != len(construction.assessments)
            or any(row.normalized_loss != 0 for row in construction.assessments)
        ):
            raise FieldIntelligenceError(
                "PROMOTION_UNSUPPORTED",
                "construction has not preserved meaning on its future assessments",
            )
        promoted = replace(
            construction, status="promoted", version=construction.version + 1
        )
        constructions = tuple(
            promoted if row.construction_id == construction_id else row
            for row in state.constructions
        )
        successor = state.with_transition(
            "construction-promoted",
            {"construction_id": construction_id},
            constructions=constructions,
        )
        return successor, promoted

    def interpret_utterance(
        self,
        state: AtlasState,
        *,
        text: str,
        context: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        context_value = dict(context or {})
        branches: list[Mapping[str, Any]] = []
        for construction in state.constructions:
            if not construction.matches(context_value):
                continue
            bindings = construction.interpret(text)
            if bindings is None:
                continue
            program = state.program(construction.semantic_program_id)
            if program.status != "promoted":
                continue
            semantic = program.execute(bindings)
            branches.append(
                {
                    "bindings": bindings,
                    "construction_id": construction.construction_id,
                    "construction_version": construction.version,
                    "semantic": semantic,
                    "support_event_ids": list(construction.support_event_ids),
                }
            )
        return {
            "branches": branches,
            "status": (
                "understood"
                if len(branches) == 1
                else "ambiguous"
                if branches
                else "representation-insufficient"
            ),
            "text": text,
        }

    def express_meaning(
        self,
        state: AtlasState,
        *,
        semantic_program_id: str,
        bindings: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
        max_tokens: int = 128,
    ) -> Mapping[str, Any]:
        context_value = dict(context or {})
        candidates = [
            row
            for row in state.constructions
            if row.semantic_program_id == semantic_program_id and row.matches(context_value)
        ]
        if not candidates:
            return {"status": "representation-insufficient", "text": None}
        rendered: list[tuple[str, LanguageConstruction]] = []
        for construction in candidates:
            text = construction.render(bindings)
            if len(tokenize(text)) <= max_tokens:
                rendered.append((text, construction))
        if not rendered:
            return {"status": "budget-exhausted", "text": None}
        text, construction = min(rendered, key=lambda row: (len(tokenize(row[0])), row[0]))
        interpreted = construction.interpret(text)
        if interpreted != {name: str(value) for name, value in bindings.items()}:
            raise FieldIntelligenceError(
                "EXPRESSION_SEMANTICS",
                "constructed utterance failed its role-preservation check",
            )
        return {
            "construction_id": construction.construction_id,
            "semantic_program_id": semantic_program_id,
            "status": "expressed",
            "support_event_ids": list(construction.support_event_ids),
            "target_blind_stop": True,
            "text": text,
        }

    def create_plan(
        self,
        state: AtlasState,
        *,
        goal_id: str,
        goal: Mapping[str, Any],
        assumptions: Mapping[str, Any],
        action_decision: ActionDecision | None,
        inquiry: InquiryDecision | None,
        future_macros: Sequence[str] = (),
        authority_generation: int,
    ) -> tuple[AtlasState, PlanRecord]:
        _identifier(goal_id, "goal_id")
        segments: list[PlanSegment] = []
        sources: set[str] = set()
        dependencies: set[tuple[str, int]] = set()
        if action_decision is not None:
            for certificate, branch in zip(
                action_decision.certificates, action_decision.query.branches
            ):
                sources.update(branch.source_revision_ids)
                dependencies.update(branch.active_chart_versions)
                proposal_eligible = all(
                    (
                        certificate.certified_action is not None,
                        certificate.numerical_valid,
                        certificate.evidence_valid,
                        certificate.model_applicable,
                        certificate.feasible,
                    )
                )
                if proposal_eligible:
                    segments.append(
                        PlanSegment(
                            segment_id=f"{goal_id}:immediate:{len(segments)}",
                            level="immediate",
                            kind="action",
                            payload={
                                "action": certificate.certified_action,
                                "authority_required": not certificate.authorized,
                                "dependency_sha256": certificate.dependency_sha256,
                            },
                            dependency_versions=branch.active_chart_versions,
                            status=(
                                "ready"
                                if certificate.commitment_eligible
                                else "open"
                            ),
                        )
                    )
                    break
        if not segments and inquiry is not None and inquiry.selected_query_id is not None:
            segments.append(
                PlanSegment(
                    segment_id=f"{goal_id}:inquiry:0",
                    level="immediate",
                    kind="inquiry",
                    payload={
                        "query_id": inquiry.selected_query_id,
                        "reason": inquiry.status,
                    },
                    dependency_versions=tuple(sorted(dependencies)),
                    status="ready",
                )
            )
        if not segments:
            segments.append(
                PlanSegment(
                    segment_id=f"{goal_id}:unresolved:0",
                    level="immediate",
                    kind="constraint",
                    payload={"missing": "evidence-or-representation"},
                    dependency_versions=tuple(sorted(dependencies)),
                    status="unresolved",
                )
            )
        for macro_id in future_macros:
            macro = next((row for row in state.macros if row.macro_id == macro_id), None)
            if macro is None:
                raise FieldIntelligenceError("MACRO_NOT_FOUND", f"unknown macro: {macro_id}")
            segments.append(
                PlanSegment(
                    segment_id=f"{goal_id}:macro:{len(segments)}",
                    level="strategic",
                    kind="macro",
                    payload={
                        "boundary": list(macro.boundary),
                        "error_bound": macro.error_bound,
                        "macro_id": macro_id,
                    },
                    dependency_versions=macro.parent_chart_versions,
                    guards=macro.guards,
                    status="open",
                )
            )
            dependencies.update(macro.parent_chart_versions)
        identity = {
            "assumptions": dict(assumptions),
            "authority_generation": authority_generation,
            "goal": dict(goal),
            "goal_id": goal_id,
            "segments": [row.as_dict() for row in segments],
            "state_generation": state.generation,
        }
        plan = PlanRecord(
            plan_id=sha256_value(identity),
            goal_id=goal_id,
            goal=dict(goal),
            assumptions=dict(assumptions),
            segments=tuple(segments),
            source_revision_ids=tuple(sorted(sources)),
            authority_generation=authority_generation,
            status=(
                "ready"
                if any(row.status == "ready" for row in segments)
                else "open"
                if any(row.status == "open" for row in segments)
                else "unresolved"
            ),
        )
        existing = next((row for row in state.plans if row.plan_id == plan.plan_id), None)
        if existing is not None:
            if existing != plan:
                raise FieldIntelligenceError("PLAN_CONFLICT", "plan identity conflicts")
            return state, existing
        successor = state.with_transition(
            "plan-created", {"goal_id": goal_id, "plan_id": plan.plan_id}, plans=(*state.plans, plan)
        )
        return successor, plan

    def repair_plans(
        self,
        state: AtlasState,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> tuple[AtlasState, tuple[str, ...]]:
        versions = {row.chart_id: row.version for row in state.charts}
        context_value = dict(context or {})
        changed_plans: list[str] = []
        plans: list[PlanRecord] = []
        for plan in state.plans:
            changed = False
            segments: list[PlanSegment] = []
            for segment in plan.segments:
                valid_dependencies = all(
                    versions.get(chart_id) == version
                    for chart_id, version in segment.dependency_versions
                )
                valid_guards = all(guard.matches(context_value) for guard in segment.guards)
                if segment.status not in {"completed", "invalidated"} and (
                    not valid_dependencies or not valid_guards
                ):
                    segments.append(replace(segment, status="invalidated"))
                    changed = True
                else:
                    segments.append(segment)
            if changed:
                changed_plans.append(plan.plan_id)
                plan = replace(plan, segments=tuple(segments), status="invalidated")
            plans.append(plan)
        if not changed_plans:
            return state, ()
        successor = state.with_transition(
            "plans-locally-invalidated",
            {"plan_ids": changed_plans},
            plans=tuple(plans),
        )
        return successor, tuple(changed_plans)

    def counterfactual_without_chart(
        self,
        state: AtlasState,
        *,
        chart_id: str,
        observed: Mapping[str, float],
        requested: Sequence[str],
        context: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        state.chart(chart_id)
        _, control, _ = self.atlas.think(
            state, observed=observed, requested=requested, context=context
        )
        counterfactual_state = replace(
            state, charts=tuple(row for row in state.charts if row.chart_id != chart_id)
        )
        _, counterfactual, _ = self.atlas.think(
            counterfactual_state,
            observed=observed,
            requested=requested,
            context=context,
        )
        return {
            "chart_id": chart_id,
            "control": control.as_dict(),
            "counterfactual": counterfactual.as_dict(),
            "learned_memory_mutated": False,
        }

    def explain_query(
        self,
        state: AtlasState,
        query: QueryResult,
        *,
        allowed_source_revision_ids: frozenset[str],
    ) -> Mapping[str, Any]:
        branches: list[Mapping[str, Any]] = []
        for branch in query.branches:
            charts = []
            for chart_id, version in branch.active_chart_versions:
                chart = state.chart(chart_id)
                visible_sources = sorted(
                    chart.active_source_revisions().intersection(
                        allowed_source_revision_ids
                    )
                )
                charts.append(
                    {
                        "chart_id": chart_id,
                        "hidden_source_count": len(chart.active_source_revisions())
                        - len(visible_sources),
                        "mode": chart.mode,
                        "mode_group": chart.mode_group,
                        "source_revision_ids": visible_sources,
                        "version": version,
                    }
                )
            branches.append(
                {
                    "branch_id": branch.branch_id,
                    "charts": charts,
                    "condition_number": branch.condition_number,
                    "constraint_residual": branch.constraint_residual,
                    "obligations": list(branch.obligations),
                    "residual_norm": branch.residual_norm,
                    "status": branch.status,
                    "values": {
                        name: branch.values[name]
                        for name in query.requested
                        if name in branch.values
                    },
                }
            )
        return {
            "branches": branches,
            "epistemic_product": query.status,
            "field_generation": query.field_generation,
            "inspection_kind": "reconstruction",
            "memory_unchanged": query.memory_unchanged,
            "state_sha256": query.state_sha256,
        }
    def admit_computation_episode(
        self,
        state: AtlasState,
        *,
        episode_id: str,
        source_revision_id: str,
        workspace: ResonantWorkspace,
        feature_bindings: Mapping[str, Mapping[str, Any]],
        outcomes: Mapping[str, float],
        context: Mapping[str, Any],
        target_chart_ids: Sequence[str] | None = None,
    ) -> tuple[AtlasState, Mapping[str, Any]]:
        """Admit one workspace quadrature episode as one derived observation."""
        _digest(episode_id, "episode_id")
        _digest(source_revision_id, "source_revision_id")
        if not isinstance(workspace, ResonantWorkspace):
            raise FieldIntelligenceError("INVALID_COMPUTATION_EPISODE", "workspace type is invalid")
        if not feature_bindings:
            raise FieldIntelligenceError("INVALID_COMPUTATION_EPISODE", "feature_bindings must be nonempty")
        if set(feature_bindings).intersection(outcomes):
            raise FieldIntelligenceError(
                "INVALID_COMPUTATION_EPISODE", "feature and outcome names must not overlap"
            )
        allowed = {"q_y", "q_i", "p_y", "p_i", "common_q", "relative_q", "common_p", "relative_p"}
        values: dict[str, float] = {}
        normalized_bindings: dict[str, Mapping[str, Any]] = {}
        common_q = workspace.common_coordinates()
        relative_q = workspace.relative_coordinates()
        field = workspace.field.reshape(-1)
        port_count = workspace.profile.port_count
        for variable_id, binding in feature_bindings.items():
            state.variable(variable_id)
            if not isinstance(binding, Mapping):
                raise FieldIntelligenceError("INVALID_COMPUTATION_EPISODE", "feature binding must be a mapping")
            port = binding.get("port")
            component = binding.get("component")
            scale = binding.get("scale")
            if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port < port_count:
                raise FieldIntelligenceError("INVALID_COMPUTATION_EPISODE", "feature port is invalid")
            if component not in allowed:
                raise FieldIntelligenceError("INVALID_COMPUTATION_EPISODE", "feature component is invalid")
            scale = _finite(scale, f"{variable_id} feature scale", positive=True)
            if component == "common_q":
                raw = float(common_q[port])
            elif component == "relative_q":
                raw = float(relative_q[port])
            elif component == "common_p":
                raw = float((field[9 * port + 2] + field[9 * port + 3]) / math.sqrt(2.0))
            elif component == "relative_p":
                raw = float((field[9 * port + 2] - field[9 * port + 3]) / math.sqrt(2.0))
            else:
                offset = {"q_y": 0, "q_i": 1, "p_y": 2, "p_i": 3}[component]
                raw = float(field[9 * port + offset])
            values[variable_id] = raw / scale
            normalized_bindings[variable_id] = {
                "component": component, "port": port, "scale": scale
            }
        for variable_id, outcome in outcomes.items():
            state.variable(variable_id)
            if variable_id in values:
                raise FieldIntelligenceError("INVALID_COMPUTATION_EPISODE", "outcome overlaps feature")
            values[variable_id] = _finite(outcome, variable_id)
        event_id = sha256_value(
            {"episode_id": episode_id, "source_revision_id": source_revision_id, "workspace": workspace.state_sha256}
        )
        episode_context = {
            **dict(context),
            "computation_episode_id": episode_id,
            "workspace_state_sha256": workspace.state_sha256,
            "workspace_page_sha256": __import__("hashlib").sha256(workspace.page_bytes).hexdigest(),
        }
        successor, admission = self.atlas.admit_observation(
            state,
            event_id=event_id,
            source_revision_id=source_revision_id,
            values=values,
            context=episode_context,
            epistemic_type="derived",
            derivation_roots=(episode_id,),
            target_chart_ids=target_chart_ids,
        )
        successor, record = self.record_computation(
            successor,
            operation="computation_episode.workspace_quadrature.v1",
            inputs={
                "episode_id": episode_id,
                "source_revision_id": source_revision_id,
                "workspace_state_sha256": workspace.state_sha256,
                "workspace_page_sha256": __import__("hashlib").sha256(workspace.page_bytes).hexdigest(),
                "profile": workspace.profile.as_dict(),
                "feature_bindings": normalized_bindings,
                "outcomes": dict(outcomes),
            },
            outcome="supported",
            elapsed_ns=0,
            work_units=1,
        )
        return successor, {
            "episode_id": episode_id,
            "admission": admission,
            "computation_record": record.as_dict(),
            "workspace_state_sha256": workspace.state_sha256,
        }
    def record_computation(
        self,
        state: AtlasState,
        *,
        operation: str,
        inputs: Mapping[str, Any],
        outcome: str,
        elapsed_ns: int,
        work_units: int,
        residual_before: float | None = None,
        residual_after: float | None = None,
    ) -> tuple[AtlasState, ComputationRecord]:
        identity = {
            "elapsed_ns": elapsed_ns,
            "generation": state.generation,
            "inputs": dict(inputs),
            "operation": operation,
            "outcome": outcome,
            "work_units": work_units,
        }
        record = ComputationRecord(
            record_id=sha256_value(identity),
            operation=operation,
            logical_tick=state.logical_tick,
            inputs=dict(inputs),
            outcome=outcome,
            elapsed_ns=elapsed_ns,
            work_units=work_units,
            residual_before=residual_before,
            residual_after=residual_after,
        )
        if any(row.record_id == record.record_id for row in state.computation_records):
            existing = next(
                row for row in state.computation_records if row.record_id == record.record_id
            )
            return state, existing
        successor = state.with_transition(
            "computation-observed",
            {"operation": operation, "record_id": record.record_id},
            computation_records=(*state.computation_records, record),
        )
        return successor, record


def _semantic_bounds(
    value: Mapping[str, Any] | None = None,
) -> dict[str, int]:
    defaults = {
        "max_alternatives": SEMANTIC_MAX_ALTERNATIVES,
        "max_observations": SEMANTIC_MAX_OBSERVATIONS,
        "max_operations": SEMANTIC_MAX_OPERATIONS,
        "max_records": SEMANTIC_MAX_RECORDS,
        "max_timeline": SEMANTIC_MAX_TIMELINE,
        "max_versions": SEMANTIC_MAX_VERSIONS,
        "max_work": REGIONAL_KERNEL_MAX_WORK,
    }
    supplied = dict(value or {})
    if set(supplied) - set(defaults):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic bounds contain unknown keys"
        )
    result = {**defaults, **supplied}
    for name, maximum in (
        ("max_alternatives", 4_096),
        ("max_observations", 4_096),
        ("max_operations", 65_536),
        ("max_records", 65_536),
        ("max_timeline", 65_536),
        ("max_versions", 1_024),
        ("max_work", 1_000_000),
    ):
        result[name] = _regional_integer(
            result[name], f"semantic {name}", minimum=1, maximum=maximum
        )
    return result


def _semantic_result(
    operation: str, status: str, **payload: Any
) -> dict[str, Any]:
    if status not in SEMANTIC_ANSWER_STATUSES:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATUS", "semantic result status is invalid"
        )
    return {
        "schema": SEMANTIC_RESULT_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "operation": operation,
        "status": status,
        **_regional_plain(payload, "semantic result"),
    }


def _semantic_validate_result(value: Any, label: str) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or not {"family", "operation", "schema", "status"}.issubset(value)
        or value.get("schema") != SEMANTIC_RESULT_SCHEMA
        or value.get("family") != REGIONAL_KERNEL_NAME
        or value.get("operation") not in SEMANTIC_OPERATION_NAMES
        or value.get("status") not in SEMANTIC_ANSWER_STATUSES
        or (
            "replayed" in value
            and not isinstance(value["replayed"], bool)
        )
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            f"{label} is invalid",
        )
    return value


def _semantic_empty_current() -> dict[str, dict[str, Any]]:
    return {kind: {} for kind in SEMANTIC_RECORD_KINDS}


def semantic_cognition_state(
    *,
    scope: Mapping[str, Any] | str = "world",
    frame: Mapping[str, Any] | str | None = None,
    seed_records: Sequence[Mapping[str, Any]] = (),
    bounds: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create the persistent six-family semantic graph inside one task value."""

    normalized_bounds = _semantic_bounds(bounds)
    state: dict[str, Any] = {
        "schema": SEMANTIC_STATE_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "status": "waiting",
        "scope": _regional_plain(scope, "semantic scope"),
        "frame": _regional_plain(frame, "semantic frame"),
        "invocation_returns": {},
        "invalidation": _semantic_empty_barrier(),
        "records": {},
        "current": _semantic_empty_current(),
        "indexes": {
            "bindings": {},
            "deliveries": {},
            "events": {},
            "obligations": {},
            "operations": {},
            "predictions": {},
            "streams": {},
        },
        "time": {"now": 0.0, "timeline": []},
        "beliefs": {"joint": {}, "predictive_classes": {}},
        "libraries": {
            "affordances": {},
            "development_methods": {},
            "constructions": {},
            "mechanisms": {},
            "perspectives": {},
            "procedures": {},
            "representations": {},
        },
        "continuation": {
            "cursor": 0,
            "operation_id": None,
            "partial": {},
            "proposal": None,
            "request": None,
            "request_sha256": None,
        },
        "last_result": _semantic_result(
            "idle", "waiting", reason="operation-required"
        ),
        "ledger": {
            "operation_receipts": [],
            "transitions": 0,
            "work": 0,
        },
        "bounds": normalized_bounds,
    }
    for raw in seed_records:
        record = canonical_semantic_record(raw)
        record_id = record["id"]
        history = state["records"].setdefault(record_id, [])
        expected = len(history) + 1
        if int(record["content_version"]) != expected:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "seed record history is not contiguous",
            )
        if history and history[-1]["kind"] != record["kind"]:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic identity changes record family",
            )
        history.append(record)
        reference = semantic_record_ref(record).as_dict()
        state["current"][record["kind"]][record_id] = reference
        _semantic_reindex_record(state, reference)
    return _canonical_semantic_state(state)


def _semantic_index_record(
    records: Mapping[str, Sequence[Mapping[str, Any]]],
    raw_reference: Any,
    *,
    kind: str,
    identity: str | None,
    label: str,
    require_current: bool = True,
) -> dict[str, Any]:
    """Resolve an index edge and reject mistyped, stale, or renamed targets."""

    try:
        reference = SemanticRef.from_dict(raw_reference)
        record = resolve_semantic_record(
            records,
            reference,
            require_current=require_current,
        )
    except RegionalFieldError as exc:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_REFERENCE",
            f"{label} is unavailable, stale, or mistyped",
        ) from exc
    if reference.kind != kind or (
        identity is not None and reference.id != identity
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_REFERENCE",
            f"{label} points to the wrong semantic identity or family",
        )
    return record

def _semantic_probability_model(value: Any, label: str) -> dict[str, Any]:
    required = {
        "model_id",
        "observation_law",
        "prior_or_frequency_basis",
        "reference_population",
    }
    if not isinstance(value, Mapping) or not required.issubset(value):
        raise FieldIntelligenceError(
            "INVALID_PROBABILITY_MODEL",
            f"{label} requires a named observation law, probability basis, "
            "and reference population",
        )
    normalized = _regional_plain(dict(value), label)
    normalized["model_id"] = _identifier(
        normalized["model_id"], f"{label} identity"
    )
    for field in required - {"model_id"}:
        if normalized[field] in (None, "", [], {}):
            raise FieldIntelligenceError(
                "INVALID_PROBABILITY_MODEL",
                f"{label} field {field} is empty",
            )
    return normalized


def _semantic_program_has_probability(
    program: Mapping[str, Any] | None,
) -> bool:
    if program is None:
        return False
    if (
        program.get("program_kind") == "hybrid"
        and isinstance(program.get("body"), Mapping)
        and program["body"].get("mode_weights") is not None
    ):
        return True
    for value in program.values():
        if isinstance(value, Mapping) and _semantic_program_has_probability(
            value
        ):
            return True
        if isinstance(value, list) and any(
            isinstance(item, Mapping)
            and _semantic_program_has_probability(item)
            for item in value
        ):
            return True
    return False


def _semantic_affordance_payload(payload: dict[str, Any]) -> None:
    required = {
        "action_context_support",
        "argument_roles",
        "effects",
        "execution",
        "obligations",
        "preconditions",
        "program",
        "program_role",
        "reversibility",
        "risk",
    }
    if set(payload) != required:
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE",
            "affordance Program payload has an invalid schema",
        )
    roles = payload["argument_roles"]
    if not isinstance(roles, list) or len(roles) > SEMANTIC_MAX_ALTERNATIVES:
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE", "affordance argument roles are invalid"
        )
    names: set[str] = set()
    normalized_roles: list[dict[str, Any]] = []
    for raw in roles:
        if not isinstance(raw, Mapping) or set(raw) != {
            "binding_constraints",
            "bounds",
            "name",
            "required",
            "units",
            "value_type",
        }:
            raise FieldIntelligenceError(
                "INVALID_AFFORDANCE",
                "affordance argument role schema is invalid",
            )
        role = _regional_plain(dict(raw), "affordance argument role")
        name = _identifier(role["name"], "affordance argument role")
        if name in names:
            raise FieldIntelligenceError(
                "INVALID_AFFORDANCE",
                "affordance argument roles must be unique",
            )
        names.add(name)
        if role["value_type"] not in {
            "boolean",
            "integer",
            "number",
            "object",
            "string",
        }:
            raise FieldIntelligenceError(
                "INVALID_AFFORDANCE",
                "affordance argument value type is invalid",
            )
        if not isinstance(role["required"], bool):
            raise FieldIntelligenceError(
                "INVALID_AFFORDANCE",
                "affordance argument required flag must be Boolean",
            )
        if role["units"] is not None:
            role["units"] = _identifier(
                role["units"], "affordance argument units"
            )
        constraints = role["binding_constraints"]
        if (
            not isinstance(constraints, Mapping)
            or set(constraints) - {"equals_binding", "member_of_binding"}
        ):
            raise FieldIntelligenceError(
                "INVALID_AFFORDANCE",
                "affordance binding constraints are invalid",
            )
        role["binding_constraints"] = {
            key: _identifier(
                value, f"affordance {key.replace('_', ' ')}"
            )
            for key, value in constraints.items()
        }
        bounds = role["bounds"]
        if bounds is not None:
            if (
                not isinstance(bounds, Mapping)
                or set(bounds) - {"max", "min"}
                or not bounds
            ):
                raise FieldIntelligenceError(
                    "INVALID_AFFORDANCE",
                    "affordance argument bounds are invalid",
                )
            normalized_bounds = {
                key: _finite(value, f"affordance argument {key}")
                for key, value in bounds.items()
            }
            if (
                "min" in normalized_bounds
                and "max" in normalized_bounds
                and normalized_bounds["min"] > normalized_bounds["max"]
            ):
                raise FieldIntelligenceError(
                    "INVALID_AFFORDANCE",
                    "affordance argument bounds are reversed",
                )
            role["bounds"] = normalized_bounds
        normalized_roles.append(role)
    payload["argument_roles"] = normalized_roles

    preconditions = payload["preconditions"]
    if not isinstance(preconditions, Mapping) or set(preconditions) != {
        "latent",
        "observable",
        "probability_model",
        "semantics",
    }:
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE", "affordance preconditions are invalid"
        )
    normalized_preconditions = _regional_plain(
        dict(preconditions), "affordance preconditions"
    )
    for category in ("observable", "latent"):
        rows = normalized_preconditions[category]
        if not isinstance(rows, list):
            raise FieldIntelligenceError(
                "INVALID_AFFORDANCE",
                f"affordance {category} preconditions must be a list",
            )
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                "binding_id",
                "expected",
            }:
                raise FieldIntelligenceError(
                    "INVALID_AFFORDANCE",
                    f"affordance {category} precondition is invalid",
                )
            row["binding_id"] = _identifier(
                row["binding_id"],
                f"affordance {category} precondition binding",
            )
    semantics = normalized_preconditions["semantics"]
    if semantics not in {"probability", "set"}:
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE",
            "affordance precondition uncertainty semantics is invalid",
        )
    if semantics == "probability":
        normalized_preconditions["probability_model"] = (
            _semantic_probability_model(
                normalized_preconditions["probability_model"],
                "affordance precondition probability model",
            )
        )
    elif normalized_preconditions["probability_model"] is not None:
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE",
            "set-valued affordance preconditions carry a probability model",
        )
    payload["preconditions"] = normalized_preconditions

    execution = payload["execution"]
    if not isinstance(execution, Mapping) or set(execution) != {
        "concurrency",
        "duration",
        "resource_occupancy",
        "termination_conditions",
    }:
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE", "affordance execution contract is invalid"
        )
    execution = _regional_plain(dict(execution), "affordance execution")
    duration = execution["duration"]
    if not isinstance(duration, dict) or set(duration) != {
        "lower",
        "units",
        "upper",
    }:
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE", "affordance duration is invalid"
        )
    duration["lower"] = _finite(duration["lower"], "affordance duration lower")
    duration["upper"] = _finite(duration["upper"], "affordance duration upper")
    duration["units"] = _identifier(
        duration["units"], "affordance duration units"
    )
    if duration["lower"] < 0.0 or duration["lower"] > duration["upper"]:
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE", "affordance duration bounds are invalid"
        )
    if (
        not isinstance(execution["concurrency"], Mapping)
        or not isinstance(execution["resource_occupancy"], list)
        or not isinstance(execution["termination_conditions"], list)
    ):
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE",
            "affordance concurrency, resources, or termination is invalid",
        )
    payload["execution"] = execution

    effects = payload["effects"]
    if (
        not isinstance(effects, Mapping)
        or set(effects)
        != {
            "expected_observations",
            "failure_modes",
            "intended",
            "possible_side_effects",
        }
        or not isinstance(effects["intended"], Mapping)
        or any(
            not isinstance(effects[name], list)
            for name in (
                "expected_observations",
                "failure_modes",
                "possible_side_effects",
            )
        )
    ):
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE", "affordance effects are invalid"
        )
    payload["effects"] = _regional_plain(dict(effects), "affordance effects")

    support = payload["action_context_support"]
    if not isinstance(support, list) or any(
        not isinstance(item, Mapping) for item in support
    ):
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE",
            "affordance action-context support is invalid",
        )
    payload["action_context_support"] = [
        _regional_plain(dict(item), "affordance supported context")
        for item in support
    ]
    reversibility = payload["reversibility"]
    if (
        not isinstance(reversibility, Mapping)
        or set(reversibility) != {"compensation", "mode"}
        or reversibility["mode"]
        not in {"compensatable", "irreversible", "reversible"}
        or (
            reversibility["compensation"] is not None
            and not isinstance(reversibility["compensation"], Mapping)
        )
    ):
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE", "affordance reversibility is invalid"
        )
    payload["reversibility"] = _regional_plain(
        dict(reversibility), "affordance reversibility"
    )
    risk = payload["risk"]
    if (
        not isinstance(risk, Mapping)
        or set(risk) != {"minimum", "possible_harms", "units"}
        or not isinstance(risk["possible_harms"], list)
    ):
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE", "affordance risk contract is invalid"
        )
    normalized_risk = _regional_plain(dict(risk), "affordance risk")
    normalized_risk["minimum"] = _finite(
        normalized_risk["minimum"], "affordance minimum risk"
    )
    normalized_risk["units"] = _identifier(
        normalized_risk["units"], "affordance risk units"
    )
    if normalized_risk["minimum"] < 0.0:
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE", "affordance risk must be nonnegative"
        )
    payload["risk"] = normalized_risk
    obligations = payload["obligations"]
    if (
        not isinstance(obligations, Mapping)
        or set(obligations)
        != {"authority", "disclosure", "source_access"}
        or any(not isinstance(rows, list) for rows in obligations.values())
    ):
        raise FieldIntelligenceError(
            "INVALID_AFFORDANCE", "affordance obligations are invalid"
        )
    payload["obligations"] = _regional_plain(
        dict(obligations), "affordance obligations"
    )


def _semantic_validate_program_record(record: dict[str, Any]) -> None:
    if record["kind"] != "Program":
        return
    payload = record["payload"]
    raw_program = payload.get("program")
    if not isinstance(raw_program, Mapping):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic Program records require a canonical program payload",
        )
    try:
        payload["program"] = canonical_semantic_program_payload(raw_program)
    except (RegionalFieldError, ValueError) as exc:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic Program payload is not executable",
        ) from exc
    role = payload.get("program_role")
    if role is not None and role not in SEMANTIC_PROGRAM_ROLES:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic Program role is invalid"
        )
    if role == "construction":
        body = payload["program"].get("body")
        raw_variants = body.get("pattern_variants") if isinstance(body, Mapping) else None
        if raw_variants is not None:
            if not isinstance(raw_variants, list) or not raw_variants or any(
                not isinstance(pattern, list)
                or not pattern
                or any(not isinstance(token, str) or not token for token in pattern)
                for pattern in raw_variants
            ):
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "semantic construction pattern variants are invalid",
                )
    if role == "affordance":
        _semantic_affordance_payload(payload)
    if role == "predictive-state":
        signature = _semantic_predictive_signature(
            payload.get("signature"), "predictive Program signature"
        )
        if payload["program"].get("body", {}).get("signature") != signature:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "predictive Program signature diverges from its executable "
                "body",
            )
        payload["signature"] = signature
    causal_authority = payload.get("causal_authority")
    if causal_authority is not None and not isinstance(causal_authority, bool):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic mechanism causal authority must be Boolean",
        )
    raw_observation_model = payload.get("observation_model")
    if raw_observation_model is not None:
        if not isinstance(raw_observation_model, Mapping):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic observation model must be a Program payload",
            )
        payload["observation_model"] = _canonical_mechanism_program(
            raw_observation_model
        )
    raw_latent_prior = payload.get("latent_prior")
    if raw_latent_prior is not None:
        if (
            not isinstance(raw_latent_prior, Mapping)
            or any(
                isinstance(weight, bool)
                or not isinstance(weight, (int, float))
                or not math.isfinite(float(weight))
                or float(weight) < 0.0
                for weight in raw_latent_prior.values()
            )
            or (
                raw_latent_prior
                and abs(
                    sum(float(weight) for weight in raw_latent_prior.values())
                    - 1.0
                )
                > 1.0e-9
            )
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic latent prior is not normalized",
            )
    if role == "mechanism":
        payload["program"] = _canonical_mechanism_program(payload["program"])
    raw_parameter_learning = payload.get("parameter_learning")
    if raw_parameter_learning is not None:
        payload["parameter_learning"] = _semantic_validate_parameter_learning(
            raw_parameter_learning, record
        )
    raw_probability_model = payload.get("probability_model")
    probability_model = (
        None
        if raw_probability_model is None
        else _semantic_probability_model(
            raw_probability_model, "semantic mechanism probability model"
        )
    )
    if probability_model is not None:
        payload["probability_model"] = probability_model
    if (
        bool(raw_latent_prior)
        or _semantic_program_has_probability(payload["program"])
        or _semantic_program_has_probability(payload.get("observation_model"))
    ) and probability_model is None:
        raise FieldIntelligenceError(
            "INVALID_PROBABILITY_MODEL",
            "weighted mechanism branches require an explicit probability "
            "model",
        )



def _semantic_operation_identity(request: Mapping[str, Any]) -> str:
    return _identifier(
        request.get("operation_id", sha256_value(request)),
        "semantic operation identity",
    )


def _semantic_effect_count(
    value: Mapping[str, Any] | None,
    *,
    default_lower: int,
    default_upper: int,
) -> dict[str, int]:
    raw = (
        {"lower": default_lower, "upper": default_upper}
        if value is None
        else dict(value)
    )
    if set(raw) != {"lower", "upper"}:
        raise FieldIntelligenceError(
            "INVALID_ACTION_LIFECYCLE",
            "action effect-count range must contain lower and upper",
        )
    lower = _regional_integer(
        raw["lower"], "action effect-count lower bound"
    )
    upper = _regional_integer(
        raw["upper"], "action effect-count upper bound"
    )
    if lower > upper:
        raise FieldIntelligenceError(
            "INVALID_ACTION_LIFECYCLE",
            "action effect-count lower bound exceeds its upper bound",
        )
    return {"lower": lower, "upper": upper}


def _semantic_action_phase(
    state: Mapping[str, Any],
    proposal: dict[str, Any],
    request: Mapping[str, Any],
    *,
    phase: str,
    proposal_status: str,
    progress: Mapping[str, Any] | None = None,
    effect_count: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_progress = _regional_plain(
        dict(progress or {"completed": 0, "total": 1}),
        "action phase progress",
    )
    if (
        set(normalized_progress) != {"completed", "total"}
        or isinstance(normalized_progress["completed"], bool)
        or not isinstance(normalized_progress["completed"], (int, float))
        or isinstance(normalized_progress["total"], bool)
        or not isinstance(normalized_progress["total"], (int, float))
        or not math.isfinite(float(normalized_progress["completed"]))
        or not math.isfinite(float(normalized_progress["total"]))
        or float(normalized_progress["completed"]) < 0.0
        or float(normalized_progress["total"]) < 0.0
        or float(normalized_progress["completed"])
        > float(normalized_progress["total"])
    ):
        raise FieldIntelligenceError(
            "INVALID_ACTION_LIFECYCLE", "action phase progress is invalid"
        )
    normalized_effect_count = _semantic_effect_count(
        effect_count,
        default_lower=0,
        default_upper=0,
    )
    predecessor_phase = (
        None if not proposal["phases"] else proposal["phases"][-1]["phase"]
    )
    predecessor_receipt = (
        None
        if not proposal["phases"]
        else proposal["phases"][-1]["receipt_rho"]
    )
    normalized_metadata = _regional_plain(
        dict(metadata or {}), "action phase metadata"
    )
    raw_reason = normalized_metadata.get("reason")
    reason = (
        None
        if raw_reason is None
        else _identifier(raw_reason, "action phase reason")
    )
    body = {
        "admitted_k": int(state["ledger"]["transitions"]) + 1,
        "concurrency_id": proposal["concurrency_id"],
        "effect_count": normalized_effect_count,
        "episode_id": proposal["episode_id"],
        "metadata": normalized_metadata,
        "operation_id": proposal["operation_id"],
        "phase": _identifier(phase, "action phase"),
        "predecessor_phase": predecessor_phase,
        "predecessor_receipt": predecessor_receipt,
        "progress": normalized_progress,
        "proposal_status": _identifier(
            proposal_status, "action proposal status"
        ),
        "reason": reason,
        "transition_id": _semantic_operation_identity(request),
        "world_time": {
            "start": float(state["time"]["now"]),
            "end": float(state["time"]["now"]),
        },
    }
    row = {**body, "receipt_rho": sha256_value(body)}
    proposal["phases"].append(row)
    proposal["status"] = proposal_status
    return row


def _semantic_new_action_proposal(
    state: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    action: Mapping[str, Any],
    affordance: Mapping[str, Any],
    proposal_id: str,
    target: str,
    scope: str,
    plan: Mapping[str, Any] | None = None,
    prediction: Mapping[str, Any] | None = None,
    model: Mapping[str, Any] | None = None,
    expected_observation_window: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    operation_id = _digest(proposal_id, "action operation identity")
    proposal = {
        "affordance": _regional_plain(
            dict(affordance), "action proposal affordance"
        ),
        "acknowledgment": None,
        "action": _regional_plain(dict(action), "proposed action"),
        "assessment": None,
        "authorization": None,
        "cancellation": None,
        "concurrency_id": sha256_value({"scope": scope, "target": target}),
        "context": _regional_plain(
            dict(cast(Any, request.get("context", {}))),
            "action proposal context",
        ),
        "dispatch": None,
        "episode_id": operation_id,
        "expected_observation_window": (
            None
            if expected_observation_window is None
            else _semantic_interval(
                expected_observation_window,
                default=float(state["time"]["now"]),
            )
        ),
        "model": (
            None
            if model is None
            else _regional_plain(dict(model), "action proposal model")
        ),
        "obligation": None,
        "operation_id": operation_id,
        "phases": [],
        "plan": (
            None
            if plan is None
            else _regional_plain(dict(plan), "action proposal plan")
        ),
        "prediction": (
            None
            if prediction is None
            else _regional_plain(
                dict(prediction), "action proposal prediction"
            )
        ),
        "proposal_id": operation_id,
        "scope": scope,
        "status": "proposed",
        "target": target,
        "tracking": [],
    }
    _semantic_action_phase(
        state,
        proposal,
        request,
        phase="proposed",
        proposal_status="proposed",
        metadata={
            "frozen_affordance": proposal["affordance"],
            "frozen_context": proposal["context"],
            "frozen_model": proposal["model"],
            "frozen_prediction": proposal["prediction"],
            "expected_observation_window": proposal[
                "expected_observation_window"
            ],
        },
    )
    return proposal


def _semantic_validate_action_proposal(
    proposal: Any,
    records: Mapping[str, Sequence[Mapping[str, Any]]],
) -> None:
    required = {
        "affordance",
        "acknowledgment",
        "action",
        "assessment",
        "authorization",
        "cancellation",
        "concurrency_id",
        "context",
        "dispatch",
        "episode_id",
        "expected_observation_window",
        "model",
        "obligation",
        "operation_id",
        "phases",
        "plan",
        "prediction",
        "proposal_id",
        "scope",
        "status",
        "target",
        "tracking",
    }
    statuses = {
        "acknowledged",
        "assessed",
        "authorized",
        "cancel-requested",
        "cancelled",
        "dispatch-uncertain",
        "dispatched",
        "invalidated",
        "proposed",
        "tracking",
    }
    if (
        not isinstance(proposal, dict)
        or set(proposal) != required
        or not isinstance(proposal["action"], dict)
        or not isinstance(proposal["context"], dict)
        or not isinstance(proposal["phases"], list)
        or not proposal["phases"]
        or not isinstance(proposal["tracking"], list)
        or proposal["status"] not in statuses
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic action proposal payload is invalid",
        )
    for name in (
        "concurrency_id",
        "episode_id",
        "operation_id",
        "proposal_id",
    ):
        _digest(proposal[name], f"semantic proposal {name}")
    if (
        proposal["proposal_id"] != proposal["operation_id"]
        or proposal["episode_id"] != proposal["operation_id"]
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic proposal operation identity diverges",
        )
    _identifier(proposal["scope"], "semantic proposal scope")
    _identifier(proposal["target"], "semantic proposal target")
    if proposal["expected_observation_window"] is not None:
        proposal["expected_observation_window"] = _semantic_interval(
            proposal["expected_observation_window"],
            default=0.0,
        )
    predecessor_phase: str | None = None
    predecessor_receipt: str | None = None
    for index, row in enumerate(proposal["phases"]):
        row_keys = {
            "admitted_k",
            "concurrency_id",
            "effect_count",
            "episode_id",
            "metadata",
            "operation_id",
            "phase",
            "predecessor_phase",
            "predecessor_receipt",
            "progress",
            "proposal_status",
            "reason",
            "receipt_rho",
            "transition_id",
            "world_time",
        }
        if (
            not isinstance(row, dict)
            or set(row) != row_keys
            or not isinstance(row["metadata"], dict)
            or not isinstance(row["progress"], dict)
            or set(row["progress"]) != {"completed", "total"}
            or row["predecessor_phase"] != predecessor_phase
            or row["predecessor_receipt"] != predecessor_receipt
            or row["operation_id"] != proposal["operation_id"]
            or row["episode_id"] != proposal["episode_id"]
            or row["concurrency_id"] != proposal["concurrency_id"]
            or (index == 0 and row["phase"] != "proposed")
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic action phase chain is invalid",
            )
        phase = _identifier(row["phase"], "semantic action phase")
        _identifier(row["proposal_status"], "semantic action phase status")
        _identifier(row["transition_id"], "semantic action transition")
        _regional_integer(row["admitted_k"], "semantic action admitted k")
        row["world_time"] = _semantic_interval(
            row["world_time"], default=0.0
        )
        if row["reason"] is not None:
            _identifier(row["reason"], "semantic action phase reason")
        completed = _finite(
            row["progress"]["completed"], "semantic action completed progress"
        )
        total = _finite(
            row["progress"]["total"], "semantic action total progress"
        )
        if completed < 0.0 or total < 0.0 or completed > total:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic action progress is invalid",
            )
        row["effect_count"] = _semantic_effect_count(
            row["effect_count"], default_lower=0, default_upper=0
        )
        receipt = _digest(
            row["receipt_rho"], "semantic action phase receipt rho"
        )
        body = {
            key: value for key, value in row.items() if key != "receipt_rho"
        }
        if receipt != sha256_value(body):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic action phase receipt diverges",
            )
        predecessor_phase = phase
        predecessor_receipt = receipt
    if proposal["phases"][-1]["proposal_status"] != proposal["status"]:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic action status diverges from its phase chain",
        )
    affordance_record = _semantic_index_record(
        records,
        proposal["affordance"],
        kind="Program",
        identity=None,
        label="semantic proposal affordance",
        require_current=False,
    )
    if affordance_record["payload"].get("program_role") != "affordance":
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic proposal affordance has the wrong Program role",
        )
    if proposal.get("plan") is not None:
        _semantic_index_record(
            records,
            proposal["plan"],
            kind="Program",
            identity=None,
            label="semantic proposal plan",
            require_current=False,
        )
    prediction_record = None
    if proposal.get("prediction") is not None:
        prediction_record = _semantic_index_record(
            records,
            proposal["prediction"],
            kind="Assessment",
            identity=None,
            label="semantic proposal prediction",
            require_current=False,
        )
        if prediction_record["payload"].get("purpose") != "prediction":
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic proposal prediction has the wrong purpose",
            )
    if proposal.get("model") is not None:
        _semantic_index_record(
            records,
            proposal["model"],
            kind="Program",
            identity=None,
            label="semantic proposal model",
            require_current=False,
        )
    if proposal.get("obligation") is not None:
        _semantic_index_record(
            records,
            proposal["obligation"],
            kind="Obligation",
            identity=None,
            label="semantic proposal obligation",
            require_current=True,
        )
    acknowledgment = proposal.get("acknowledgment")
    if acknowledgment is not None:
        _semantic_index_record(
            records,
            acknowledgment,
            kind="Event",
            identity=None,
            label="semantic proposal acknowledgment",
            require_current=True,
        )
    assessment = proposal.get("assessment")
    if assessment is not None:
        assessment_record = _semantic_index_record(
            records,
            assessment,
            kind="Assessment",
            identity=None,
            label="semantic proposal outcome assessment",
            require_current=True,
        )
        if (
            proposal["status"] != "assessed"
            or prediction_record is None
            or assessment_record["status"] != "assessed"
            or SemanticRef.from_dict(assessment).id
            != SemanticRef.from_dict(proposal["prediction"]).id
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic proposal assessment is inconsistent",
            )


def _semantic_validate_development_provenance(record: Mapping[str, Any]) -> None:
    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        return
    provenance = payload.get("provenance")
    if provenance is not None and provenance not in _SEMANTIC_DEVELOPMENT_PROVENANCES:
        raise FieldIntelligenceError(
            "INVALID_DEVELOPMENT",
            "development provenance must be caller-supplied or executed",
        )
    observed = payload.get("observed_outcome", _ABSENT)
    if observed is not _ABSENT and provenance != "executed":
        raise FieldIntelligenceError(
            "INVALID_DEVELOPMENT",
            "an observed development outcome requires executed provenance",
        )
    verified = payload.get("verified_improvement", _ABSENT)
    if verified is not _ABSENT and not isinstance(verified, bool):
        raise FieldIntelligenceError(
            "INVALID_DEVELOPMENT",
            "development verified_improvement must be boolean",
        )
    if verified is True and provenance != "executed":
        raise FieldIntelligenceError(
            "INVALID_DEVELOPMENT",
            "verified development improvement requires executed provenance",
        )

def _canonical_semantic_state(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "beliefs",
        "bounds",
        "continuation",
        "current",
        "family",
        "frame",
        "indexes",
        "invalidation",
        "invocation_returns",
        "last_result",
        "ledger",
        "libraries",
        "records",
        "schema",
        "scope",
        "status",
        "time",
    }
    if isinstance(value, Mapping):
        legacy = dict(value)
        if "invocation_returns" not in legacy:
            legacy["invocation_returns"] = {}
        if "invalidation" not in legacy:
            legacy["invalidation"] = _semantic_empty_barrier()
        value = legacy
    if not isinstance(value, Mapping) or set(value) != required:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic cognition state does not match its closed schema",
        )
    state = _regional_plain(dict(value), "semantic cognition state")
    if (
        state["schema"] != SEMANTIC_STATE_SCHEMA
        or state["family"] != REGIONAL_KERNEL_NAME
        or state["status"] not in {"running", "waiting"}
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic cognition header is invalid"
        )
    if isinstance(state["scope"], str):
        _identifier(state["scope"], "semantic cognition scope")
    elif not isinstance(state["scope"], dict):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic cognition scope must be text or a mapping",
        )
    if isinstance(state["frame"], str):
        _identifier(state["frame"], "semantic cognition frame")
    elif state["frame"] is not None and not isinstance(state["frame"], dict):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic cognition frame must be null, text, or a mapping",
        )
    state["bounds"] = _semantic_bounds(state["bounds"])
    if (
        not isinstance(state["invocation_returns"], dict)
        or len(state["invocation_returns"]) > state["bounds"]["max_operations"]
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic invocation returns exceed their bounded mapping",
        )
    for binding, returned in state["invocation_returns"].items():
        _identifier(binding, "semantic invocation return binding")
        if (
            not isinstance(returned, dict)
            or returned.get("schema")
            not in {
                "cassifi.learning-computer-child-return.v1",
                "cassifi.learning-computer-child-return.v2",
            }
            or returned.get("status")
            not in {
                "cancelled",
                "counter-exhausted",
                "exhausted",
                "faulted",
                "halted",
            }
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic invocation return is invalid",
            )
    if not isinstance(state["records"], dict):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic records must be a mapping"
        )
    total_versions = 0
    normalized_records: dict[str, list[dict[str, Any]]] = {}
    expected_current = _semantic_empty_current()
    for record_id, raw_history in state["records"].items():
        _identifier(record_id, "semantic record identity")
        if not isinstance(raw_history, list) or not raw_history:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE", "semantic history must be nonempty"
            )
        if len(raw_history) > state["bounds"]["max_versions"]:
            raise FieldIntelligenceError(
                "WORK_CAPACITY", "semantic version capacity is exhausted"
            )
        history = [canonical_semantic_record(item) for item in raw_history]
        for record in history:
            _semantic_validate_program_record(record)
            _semantic_validate_development_provenance(record)
            if record["kind"] in {"Binding", "Value"} and (
                record["payload"].get("representation") != "joint"
                and "alternatives" in record["payload"]
            ):
                semantics = str(
                    record["payload"].get("belief_semantics", "")
                )
                record["payload"]["alternatives"] = _semantic_binding_rows(
                    record["payload"]["alternatives"],
                    state["bounds"]["max_alternatives"],
                    semantics=semantics,
                )

        if any(item["id"] != record_id for item in history):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE", "semantic history identity diverges"
            )
        if [item["content_version"] for item in history] != list(
            range(1, len(history) + 1)
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE", "semantic history is not contiguous"
            )
        if len({item["kind"] for item in history}) != 1:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE", "semantic record changes family"
            )
        normalized_records[record_id] = history
        latest = history[-1]
        expected_current[latest["kind"]][record_id] = (
            semantic_record_ref(latest).as_dict()
        )
        total_versions += len(history)
    if total_versions > state["bounds"]["max_records"]:
        raise FieldIntelligenceError(
            "WORK_CAPACITY", "semantic record capacity is exhausted"
        )
    state["records"] = normalized_records
    if state["current"] != expected_current:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic current-reference index diverges"
        )
    for history in normalized_records.values():
        for record in history:
            for dependency in record["dependencies"]:
                try:
                    resolve_semantic_record(normalized_records, dependency)
                except RegionalFieldError as exc:
                    raise FieldIntelligenceError(
                        "INVALID_SEMANTIC_REFERENCE",
                        "semantic dependency is unavailable or mistyped",
                    ) from exc
    barrier = state["invalidation"]
    expected_barrier = _semantic_empty_barrier()
    if not isinstance(barrier, dict) or set(barrier) != set(expected_barrier):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic invalidation barrier does not match its closed schema",
        )
    for name in ("active",):
        if not isinstance(barrier[name], bool):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic invalidation barrier flag is invalid",
            )
    for name in ("causes", "frontier"):
        if (
            not isinstance(barrier[name], list)
            or len(barrier[name]) > state["bounds"]["max_records"]
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                f"semantic invalidation {name} is invalid",
            )
        for reference in barrier[name]:
            if not isinstance(reference, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    f"semantic invalidation {name} must hold typed references",
                )
            try:
                semantic_ref = SemanticRef.from_dict(dict(reference))
            except RegionalFieldError as exc:
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    f"semantic invalidation {name} reference is malformed",
                ) from exc
            record = _semantic_index_record(
                normalized_records,
                semantic_ref.as_dict(),
                kind=semantic_ref.kind,
                identity=semantic_ref.id,
                label=f"semantic invalidation {name} reference",
                require_current=False,
            )
            if record["id"] != semantic_ref.id:
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    f"semantic invalidation {name} reference diverges",
                )
            reference.clear()
            reference.update(semantic_ref.as_dict())
    for name in ("cursor", "passes"):
        if (
            isinstance(barrier[name], bool)
            or not isinstance(barrier[name], int)
            or barrier[name] < 0
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                f"semantic invalidation {name} is invalid",
            )
    if barrier["reason"] is not None:
        _identifier(barrier["reason"], "semantic invalidation reason")
    if not isinstance(barrier["checked"], dict):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic invalidation checked map is invalid",
        )
    for record_id, count in barrier["checked"].items():
        if (
            record_id not in normalized_records
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or count > len(barrier["causes"])
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic invalidation checked row is invalid",
            )
    if not barrier["active"]:
        barrier["checked"] = {
            record_id: max(
                int(barrier["checked"].get(record_id, 0)),
                len(barrier["causes"]),
            )
            for record_id in normalized_records
        }
    expected_indexes = {
        "bindings",
        "deliveries",
        "events",
        "obligations",
        "operations",
        "predictions",
        "streams",
    }
    if not isinstance(state["indexes"], dict) or set(
        state["indexes"]
    ) != expected_indexes:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic indexes are invalid"
        )
    if any(not isinstance(state["indexes"][name], dict) for name in expected_indexes):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic index rows are invalid"
        )
    for index_name, kind in (
        ("bindings", "Binding"),
        ("events", "Event"),
        ("obligations", "Obligation"),
        ("predictions", "Assessment"),
    ):
        for identity, reference in state["indexes"][index_name].items():
            normalized_identity = _identifier(
                identity, f"semantic {index_name} identity"
            )
            record = _semantic_index_record(
                normalized_records,
                reference,
                kind=kind,
                identity=normalized_identity,
                label=f"semantic {index_name} reference",
            )
            if (
                index_name == "predictions"
                and record["payload"].get("purpose") != "prediction"
            ):
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "prediction index points to a nonprediction assessment",
                )
    for delivery_id, delivery in state["indexes"]["deliveries"].items():
        _identifier(delivery_id, "semantic delivery identity")
        if (
            not isinstance(delivery, dict)
            or set(delivery) != {"request_sha256", "result"}
            or not isinstance(delivery["result"], dict)
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic delivery index row is invalid",
            )
        _digest(delivery["request_sha256"], "semantic delivery request")
        delivery_result = _semantic_validate_result(
            delivery["result"], "semantic delivery result"
        )
        if delivery_result["operation"] != "observe":
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic delivery result is not an observation",
            )
    for stream_key, request_sha256 in state["indexes"]["streams"].items():
        _identifier(stream_key, "semantic stream chunk identity")
        _digest(request_sha256, "semantic stream chunk request")
    expected_libraries = {
        "affordances",
        "constructions",
        "development_methods",
        "mechanisms",
        "perspectives",
        "procedures",
        "representations",
    }
    legacy_libraries = expected_libraries - {"development_methods"}
    if isinstance(state["libraries"], dict) and set(
        state["libraries"]
    ) == legacy_libraries:
        state["libraries"]["development_methods"] = {}
    if not isinstance(state["libraries"], dict) or set(
        state["libraries"]
    ) != expected_libraries:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic libraries are invalid"
        )
    if any(
        not isinstance(state["libraries"][name], dict)
        for name in expected_libraries
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic library rows are invalid"
        )
    if (
        not isinstance(state["beliefs"], dict)
        or set(state["beliefs"]) != {"joint", "predictive_classes"}
        or not all(isinstance(item, dict) for item in state["beliefs"].values())
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic belief state is invalid"
        )
    required_program_roles = {
        "affordances": "affordance",
        "constructions": "construction",
        "development_methods": "development-method",
        "mechanisms": "mechanism",
        "procedures": "procedure",
        "representations": {"predictive-state", "representation"},
    }
    for library_name, required_role in required_program_roles.items():
        for identity, reference in state["libraries"][library_name].items():
            normalized_identity = _identifier(
                identity, f"semantic {library_name} identity"
            )
            record = _semantic_index_record(
                normalized_records,
                reference,
                kind="Program",
                identity=normalized_identity,
                label=f"semantic {library_name} reference",
            )
            role = record["payload"].get("program_role")
            allowed_roles = (
                required_role if isinstance(required_role, set) else {required_role}
            )
            if role not in allowed_roles:
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    f"semantic {library_name} entry has the wrong Program role",
                )

    for perspective_id, perspective in state["libraries"]["perspectives"].items():
        normalized_perspective_id = _identifier(
            perspective_id, "semantic perspective identity"
        )
        if not isinstance(perspective, dict):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic perspective row is invalid",
            )
        for name, reference in perspective.items():
            normalized_name = _identifier(
                name, "semantic perspective binding name"
            )
            record = _semantic_index_record(
                normalized_records,
                reference,
                kind="Binding",
                identity=None,
                label="semantic perspective binding",
            )
            payload = record["payload"]
            normalized_agent = _identifier(
                payload.get("agent_id"), "semantic perspective agent"
            )
            stored_perspective_id = _identifier(
                payload.get("perspective_id", normalized_agent),
                "stored semantic perspective identity",
            )
            path = payload.get("perspective_path", [normalized_agent])
            if (
                not isinstance(path, list)
                or not path
                or len(path) > 8
                or any(not isinstance(item, str) or not item for item in path)
                or path[-1] != normalized_agent
            ):
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "semantic perspective path is invalid",
                )
            expected_scope = (
                {"perspective": normalized_agent}
                if path == [normalized_agent]
                else {
                    "perspective": stored_perspective_id,
                    "perspective_path": path,
                }
            )
            if (
                normalized_perspective_id != stored_perspective_id
                or record["scope"] != expected_scope
                or payload.get("attribute") != normalized_name
            ):
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "semantic perspective Binding metadata is inconsistent",
                )
    for identity, reference in state["beliefs"]["joint"].items():
        normalized_identity = _identifier(identity, "semantic joint belief identity")
        record = _semantic_index_record(
            normalized_records,
            reference,
            kind="Value",
            identity=normalized_identity,
            label="semantic joint belief reference",
        )
        if record["payload"].get("representation") != "joint":
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "joint-belief index points to the wrong Value profile",
            )
        record["payload"]["alternatives"] = _semantic_joint_rows(
            record["payload"].get("alternatives"),
            state["bounds"]["max_alternatives"],
            semantics=str(record["payload"].get("belief_semantics", "")),
        )
    for identity, reference in state["beliefs"]["predictive_classes"].items():
        normalized_identity = _identifier(
            identity, "semantic predictive state identity"
        )
        record = _semantic_index_record(
            normalized_records,
            reference,
            kind="Program",
            identity=normalized_identity,
            label="semantic predictive state reference",
        )
        if record["payload"].get("program_role") != "predictive-state":
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "predictive-state index points to the wrong Program role",
            )

    if (
        not isinstance(state["time"], dict)
        or set(state["time"]) != {"now", "timeline"}
        or not isinstance(state["time"]["timeline"], list)
        or len(state["time"]["timeline"]) > state["bounds"]["max_timeline"]
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic time state is invalid"
        )
    state["time"]["now"] = _finite(state["time"]["now"], "semantic now")
    timeline_order: list[tuple[float, float, str, int]] = []
    for item in state["time"]["timeline"]:
        if not isinstance(item, dict) or set(item) != {"event", "time"}:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic timeline entry is invalid",
            )
        event = _semantic_index_record(
            normalized_records,
            item["event"],
            kind="Event",
            identity=None,
            label="semantic timeline event",
            require_current=True,
        )
        event_time = _semantic_interval(
            cast(Any, item["time"]),
            default=float(state["time"]["now"]),
        )
        if event["valid_time"] != event_time:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic timeline time diverges from its event",
            )
        item["time"] = event_time
        timeline_order.append(
            (
                event_time["start"],
                event_time["end"],
                event["id"],
                int(item["event"]["content_version"]),
            )
        )
    if timeline_order != sorted(timeline_order):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic timeline is not in world-time order",
        )
    if timeline_order and max(item[1] for item in timeline_order) > state["time"]["now"]:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic timeline extends beyond current world time",
        )
    continuation_keys = {
        "cursor",
        "operation_id",
        "partial",
        "proposal",
        "request",
        "request_sha256",
    }
    continuation = state["continuation"]
    if (
        not isinstance(continuation, dict)
        or set(continuation) != continuation_keys
        or not isinstance(continuation["partial"], dict)
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic continuation is invalid"
        )
    _regional_integer(
        continuation["cursor"],
        "semantic continuation cursor",
        maximum=state["bounds"]["max_work"],
    )
    active = continuation["request"] is not None
    if active != (continuation["request_sha256"] is not None):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic continuation is incomplete"
        )
    if active:
        if not isinstance(continuation["request"], dict):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE", "semantic request is invalid"
            )
        _digest(
            continuation["request_sha256"],
            "semantic continuation request digest",
        )
        _identifier(
            continuation["operation_id"], "semantic continuation operation"
        )
        if sha256_value(continuation["request"]) != continuation["request_sha256"]:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic continuation request digest diverges",
            )
        expected_operation_id = continuation["request"].get(
            "operation_id", continuation["request_sha256"]
        )
        if continuation["operation_id"] != expected_operation_id:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic continuation operation identity diverges",
            )
    elif continuation["operation_id"] is not None:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "idle continuation retains an operation"
        )
    proposal = continuation["proposal"]
    if proposal is not None:
        _semantic_validate_action_proposal(proposal, normalized_records)
    ledger = state["ledger"]
    if (
        not isinstance(ledger, dict)
        or set(ledger) != {"operation_receipts", "transitions", "work"}
        or not isinstance(ledger["operation_receipts"], list)
        or len(ledger["operation_receipts"])
        > state["bounds"]["max_operations"]
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE", "semantic ledger is invalid"
        )
    transition_count = _regional_integer(
        ledger["transitions"],
        "semantic transitions",
        maximum=state["bounds"]["max_operations"],
    )
    total_work = _regional_integer(
        ledger["work"],
        "semantic work",
        maximum=state["bounds"]["max_operations"] * state["bounds"]["max_work"],
    )
    expected_operation_ids: set[str] = set()
    receipt_work = 0
    indexed_results: list[dict[str, Any]] = []
    for position, receipt in enumerate(ledger["operation_receipts"], start=1):
        receipt_keys = {
            "operation_id",
            "request_sha256",
            "result_sha256",
            "transition",
            "work",
        }
        if not isinstance(receipt, dict) or set(receipt) != receipt_keys:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic operation receipt is invalid",
            )
        operation_id = _identifier(
            receipt["operation_id"], "semantic receipt operation identity"
        )
        if operation_id in expected_operation_ids:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic operation receipt identity is duplicated",
            )
        expected_operation_ids.add(operation_id)
        _digest(receipt["request_sha256"], "semantic receipt request")
        _digest(receipt["result_sha256"], "semantic receipt result")
        if _regional_integer(
            receipt["transition"],
            "semantic receipt transition",
            minimum=1,
            maximum=state["bounds"]["max_operations"],
        ) != position:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic operation receipt sequence is not contiguous",
            )
        operation_work = _regional_integer(
            receipt["work"],
            "semantic receipt work",
            minimum=1,
            maximum=state["bounds"]["max_work"],
        )
        receipt_work += operation_work
        operation_row = state["indexes"]["operations"].get(operation_id)
        if (
            not isinstance(operation_row, dict)
            or set(operation_row) != receipt_keys | {"result"}
            or any(operation_row[key] != receipt[key] for key in receipt_keys)
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic operation index diverges from its receipt",
            )
        operation_result = _semantic_validate_result(
            operation_row["result"], "semantic indexed operation result"
        )
        if (
            operation_result.get("replayed") is True
            and operation_result["operation"] != "observe"
        ) or sha256_value(operation_result) != receipt["result_sha256"]:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic operation result diverges from its receipt",
            )
        indexed_results.append(operation_result)
    if set(state["indexes"]["operations"]) != expected_operation_ids:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic operation index is not closed over the ledger",
        )
    if transition_count != len(indexed_results) or total_work != receipt_work:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic ledger counters diverge from its receipts",
        )
    last_result = _semantic_validate_result(
        state["last_result"], "semantic last result"
    )
    if active:
        if (
            state["status"] != "running"
            or set(continuation["partial"]) != {"required_work"}
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "active semantic continuation has invalid progress state",
            )
        required_work = _regional_integer(
            continuation["partial"]["required_work"],
            "semantic continuation required work",
            minimum=1,
            maximum=state["bounds"]["max_work"],
        )
        if not 0 < continuation["cursor"] < required_work:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic continuation cursor is outside its work interval",
            )
        expected_progress = _semantic_result(
            str(continuation["request"]["operation"]),
            "waiting",
            completed_work=continuation["cursor"],
            required_work=required_work,
        )
        if last_result != expected_progress:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic continuation result diverges from its cursor",
            )
    else:
        if (
            state["status"] != "waiting"
            or continuation["cursor"] != 0
            or continuation["partial"]
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "idle semantic continuation retains progress",
            )
        if not indexed_results:
            valid_last_results = [
                _semantic_result(
                    "idle", "waiting", reason="operation-required"
                )
            ]
        else:
            valid_last_results = [indexed_results[-1]]
            valid_last_results.extend(
                {**result, "replayed": True} for result in indexed_results
            )
        if last_result not in valid_last_results:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic last result is not ledger-backed",
            )
    return state


def _semantic_current_record(
    state: Mapping[str, Any], kind: str, record_id: str
) -> dict[str, Any]:
    if kind not in SEMANTIC_RECORD_KINDS:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_REFERENCE", "semantic family is invalid"
        )
    reference = state["current"][kind].get(record_id)
    if reference is None:
        raise FieldIntelligenceError(
            "UNKNOWN_SEMANTIC_RECORD", "semantic identity is unavailable"
        )
    if _semantic_barrier_blocks(state, reference):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_REFERENCE",
            "semantic record is blocked by an unfinished invalidation barrier",
        )
    try:
        return resolve_semantic_record(
            state["records"], reference, require_current=True
        )
    except RegionalFieldError as exc:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_REFERENCE",
            "semantic current reference is stale or mistyped",
        ) from exc


def _semantic_append_record(
    state: dict[str, Any],
    *,
    record_id: str,
    kind: str,
    payload: Mapping[str, Any],
    status: str = "active",
    epistemic_kind: str = "asserted",
    dependencies: Sequence[SemanticRef | Mapping[str, Any]] = (),
    support_roots: Sequence[str] = (),
    derivation: Mapping[str, Any] | None = None,
    applicability: Mapping[str, Any] | None = None,
    valid_time: Mapping[str, Any] | None = None,
    frame: Mapping[str, Any] | str | None = None,
    units: Mapping[str, Any] | str | None = None,
    scope: Mapping[str, Any] | str | None = None,
) -> dict[str, Any]:
    _identifier(record_id, "semantic record identity")
    if kind not in SEMANTIC_RECORD_KINDS:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_RECORD", "semantic family is invalid"
        )
    if epistemic_kind not in SEMANTIC_EPISTEMIC_KINDS:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_RECORD", "semantic epistemic kind is invalid"
        )
    histories = state["records"]
    history = histories.get(record_id, [])
    if history and history[-1]["kind"] != kind:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_RECORD", "semantic identity changes family"
        )
    if len(history) >= state["bounds"]["max_versions"]:
        raise FieldIntelligenceError(
            "WORK_CAPACITY", "semantic version capacity is exhausted"
        )
    if sum(len(item) for item in histories.values()) >= state["bounds"]["max_records"]:
        raise FieldIntelligenceError(
            "WORK_CAPACITY", "semantic record capacity is exhausted"
        )
    predecessor = None if not history else semantic_record_ref(history[-1])
    try:
        record = make_semantic_record(
            record_id=record_id,
            kind=kind,
            content_version=len(history) + 1,
            created_at=int(state["ledger"]["transitions"]) + 1,
            payload=payload,
            scope=state["scope"] if scope is None else scope,
            epistemic_kind=epistemic_kind,
            status=status,
            supersedes=predecessor,
            valid_time=valid_time,
            frame=state["frame"] if frame is None else frame,
            units=units,
            dependencies=dependencies,
            support_roots=support_roots,
            derivation=derivation,
            applicability=applicability,
        )
    except RegionalFieldError as exc:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_RECORD", str(exc)
        ) from exc
    _semantic_validate_program_record(record)
    histories.setdefault(record_id, []).append(record)
    reference = semantic_record_ref(record).as_dict()
    state["current"][kind][record_id] = reference
    barrier = state.get("invalidation")
    if isinstance(barrier, dict) and barrier.get("active"):
        dependency_ids = {str(item["id"]) for item in record["dependencies"]}
        barrier["checked"][record_id] = (
            0
            if any(
                int(barrier["checked"].get(dependency_id, 0))
                < len(barrier["causes"])
                and histories.get(dependency_id)
                and histories[dependency_id][-1]["dependencies"]
                and histories[dependency_id][-1]["status"] != "invalidated"
                for dependency_id in dependency_ids
            )
            else len(barrier["causes"])
        )
    return reference


def _semantic_publish_event(
    state: dict[str, Any],
    event_ref: Mapping[str, Any],
    event_time: Mapping[str, Any],
) -> None:
    event = _semantic_index_record(
        state["records"],
        event_ref,
        kind="Event",
        identity=None,
        label="published semantic event",
    )
    normalized_time = _semantic_interval(
        event_time, default=float(state["time"]["now"])
    )
    if event["valid_time"] != normalized_time:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_TIME",
            "published event interval diverges from its record",
        )
    timeline = state["time"]["timeline"]
    reference = SemanticRef.from_dict(event_ref).as_dict()
    for item in timeline:
        if item["event"] != reference:
            continue
        if item["time"] != normalized_time:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_TIME",
                "published event already has a different timeline interval",
            )
        state["indexes"]["events"][event["id"]] = reference
        state["time"]["now"] = max(
            float(state["time"]["now"]), normalized_time["end"]
        )
        return
    retained_timeline = [
        item
        for item in timeline
        if item["event"]["id"] != event["id"]
    ]
    replaced_prior = len(retained_timeline) != len(timeline)
    timeline[:] = retained_timeline
    if not replaced_prior and len(timeline) >= state["bounds"]["max_timeline"]:
        raise FieldIntelligenceError(
            "WORK_CAPACITY", "semantic timeline capacity is exhausted"
        )
    state["indexes"]["events"][event["id"]] = reference
    timeline.append({"event": reference, "time": normalized_time})
    timeline.sort(
        key=lambda item: (
            float(item["time"]["start"]),
            float(item["time"]["end"]),
            item["event"]["id"],
            int(item["event"]["content_version"]),
        )
    )
    state["time"]["now"] = max(
        float(state["time"]["now"]), normalized_time["end"]
    )


_PROPOSAL_WARRANT_REFERENCES = (
    ("acknowledgment", "Event"),
    ("assessment", "Assessment"),
    ("obligation", "Obligation"),
)
_PROPOSAL_IN_FLIGHT_STATUSES = frozenset(
    {
        "acknowledged",
        "authorized",
        "cancel-requested",
        "dispatch-uncertain",
        "dispatched",
        "proposed",
        "tracking",
    }
)


def _semantic_retire_action_proposal(
    state: dict[str, Any],
    proposal: dict[str, Any],
    reference: Mapping[str, Any],
    *,
    reason: str,
) -> None:
    """Close an action proposal whose warrant record stopped being active."""

    if proposal["assessment"] is not None:
        proposal["assessment"] = None
    _semantic_action_phase(
        state,
        proposal,
        {
            "operation_id": sha256_value(
                {
                    "phase": "invalidated",
                    "proposal_id": proposal["proposal_id"],
                    "record": dict(reference),
                }
            )
        },
        phase="invalidated",
        proposal_status="invalidated",
        effect_count=proposal["phases"][-1]["effect_count"],
        metadata={
            "invalidating_record": dict(reference),
            "reason": reason,
        },
    )


def _semantic_reanchor_action_proposal(
    state: dict[str, Any],
    record: Mapping[str, Any],
    reference: Mapping[str, Any],
) -> None:
    """Keep the live action proposal consistent with one revised record version.

    Revision publishes a new content version under an unchanged identity, so a
    proposal pointer that was exact becomes stale and the whole cognition state
    stops validating.  Pointers to records the proposal still governs move to
    the current version; an in-flight proposal whose obligation, acknowledgment,
    or outcome assessment stops being active is retired through its phase chain
    rather than continuing as if its warrant still held, while a settled or
    retired proposal keeps its assessed history.
    """

    continuation = state.get("continuation")
    proposal = (
        continuation.get("proposal") if isinstance(continuation, dict) else None
    )
    if not isinstance(proposal, dict):
        return
    warrants = [
        name
        for name, kind in _PROPOSAL_WARRANT_REFERENCES
        if isinstance(proposal.get(name), Mapping)
        and proposal[name].get("kind") == reference["kind"]
        and proposal[name].get("id") == reference["id"]
    ]
    plan = proposal.get("plan")
    plan_matches = (
        isinstance(plan, Mapping)
        and plan.get("kind") == reference["kind"]
        and plan.get("id") == reference["id"]
    )
    if not warrants and not plan_matches:
        return
    for name in warrants:
        proposal[name] = dict(reference)
    if record["status"] == "active":
        return
    if plan_matches and proposal["status"] == "proposed":
        _semantic_retire_action_proposal(
            state, proposal, reference, reason="plan-became-inactive"
        )
        return
    if not warrants or proposal["status"] not in _PROPOSAL_IN_FLIGHT_STATUSES:
        return
    for name, reason in (
        ("obligation", "obligation-became-inactive"),
        ("acknowledgment", "acknowledgment-became-inactive"),
        ("assessment", "outcome-assessment-became-inactive"),
    ):
        if name in warrants:
            _semantic_retire_action_proposal(
                state, proposal, reference, reason=reason
            )
            return


def _semantic_reindex_record(
    state: dict[str, Any], reference: Mapping[str, Any]
) -> None:
    """Publish every secondary view implied by one current semantic record."""

    semantic_ref = SemanticRef.from_dict(reference)
    record = _semantic_index_record(
        state["records"],
        reference,
        kind=semantic_ref.kind,
        identity=semantic_ref.id,
        label="semantic reindex reference",
    )
    normalized_ref = semantic_ref.as_dict()
    _semantic_reanchor_action_proposal(state, record, normalized_ref)
    if semantic_ref.kind == "Binding":
        state["indexes"]["bindings"][semantic_ref.id] = normalized_ref
        for perspective in state["libraries"]["perspectives"].values():
            for name, raw_ref in list(perspective.items()):
                prior = SemanticRef.from_dict(raw_ref)
                if prior.kind == "Binding" and prior.id == semantic_ref.id:
                    del perspective[name]
        payload = record["payload"]
        belief_semantics = payload.get("belief_semantics")
        if belief_semantics == "probability":
            payload["probability_model"] = _semantic_probability_model(
                payload.get("probability_model"),
                "semantic Binding probability model",
            )
        elif payload.get("probability_model") is not None:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "nonprobabilistic Binding carries a probability model",
            )
        agent_id = payload.get("agent_id")
        perspective_id = payload.get("perspective_id", agent_id)
        attribute = payload.get("attribute")
        if perspective_id is not None or (
            isinstance(record["scope"], dict)
            and "perspective" in record["scope"]
        ):
            normalized_agent = _identifier(
                agent_id, "semantic perspective agent"
            )
            normalized_perspective = _identifier(
                perspective_id, "semantic perspective identity"
            )
            normalized_attribute = _identifier(
                attribute, "semantic perspective attribute"
            )
            path = payload.get("perspective_path", [normalized_agent])
            if (
                not isinstance(path, list)
                or not path
                or len(path) > 8
                or any(not isinstance(item, str) or not item for item in path)
                or path[-1] != normalized_agent
            ):
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "perspective Binding path is invalid",
                )
            expected_scope = (
                {"perspective": normalized_agent}
                if path == [normalized_agent]
                else {
                    "perspective": normalized_perspective,
                    "perspective_path": path,
                }
            )
            if record["scope"] != expected_scope:
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "perspective Binding scope is inconsistent",
                )
            state["libraries"]["perspectives"].setdefault(
                normalized_perspective, {}
            )[normalized_attribute] = normalized_ref
        return
    if semantic_ref.kind == "Event":
        if record["valid_time"] is None:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_TIME",
                "semantic events require an explicit valid interval",
            )
        _semantic_publish_event(state, normalized_ref, record["valid_time"])
        return
    if semantic_ref.kind == "Obligation":
        state["indexes"]["obligations"][semantic_ref.id] = normalized_ref
        return
    if semantic_ref.kind == "Assessment":
        state["indexes"]["predictions"].pop(semantic_ref.id, None)
        if record["payload"].get("purpose") == "prediction":
            state["indexes"]["predictions"][semantic_ref.id] = normalized_ref
        return
    if semantic_ref.kind == "Program":
        role = record["payload"].get("program_role")
        for name in set(SEMANTIC_PROGRAM_LIBRARY_ROLES.values()):
            library = state["libraries"][name]
            for identity, raw_ref in list(library.items()):
                prior = SemanticRef.from_dict(raw_ref)
                if prior.kind == "Program" and prior.id == semantic_ref.id:
                    del library[identity]
        state["beliefs"]["predictive_classes"].pop(semantic_ref.id, None)
        library_name = SEMANTIC_PROGRAM_LIBRARY_ROLES.get(role)
        if library_name is not None and record["status"] == "active":
            state["libraries"][library_name][semantic_ref.id] = normalized_ref
        if role == "predictive-state" and record["status"] == "active":
            state["beliefs"]["predictive_classes"][
                semantic_ref.id
            ] = normalized_ref
        return
    if semantic_ref.kind == "Value":
        state["beliefs"]["joint"].pop(semantic_ref.id, None)
        if record["payload"].get("representation") == "joint":
            belief_semantics = record["payload"].get("belief_semantics")
            if belief_semantics == "probability":
                record["payload"][
                    "probability_model"
                ] = _semantic_probability_model(
                    record["payload"].get("probability_model"),
                    "semantic joint probability model",
                )
            elif record["payload"].get("probability_model") is not None:
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "nonprobabilistic joint belief carries a probability model",
                )
            state["beliefs"]["joint"][semantic_ref.id] = normalized_ref


def _semantic_reference(
    state: Mapping[str, Any],
    value: Mapping[str, Any] | SemanticRef,
    *,
    expected_kind: str | None = None,
    require_current: bool = False,
) -> tuple[SemanticRef, dict[str, Any]]:
    if require_current and _semantic_barrier_blocks(state, value):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_REFERENCE",
            "semantic reference is blocked by an unfinished invalidation barrier",
        )
    try:
        reference = (
            value if isinstance(value, SemanticRef) else SemanticRef.from_dict(value)
        )
        record = resolve_semantic_record(
            state["records"], reference, require_current=require_current
        )
        if expected_kind is not None and reference.kind != expected_kind:
            raise RegionalFieldError(
                "semantic reference has the wrong record kind"
            )
    except RegionalFieldError as exc:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_REFERENCE",
            "semantic reference is unavailable, stale, or mistyped",
        ) from exc
    return reference, record


def _semantic_empty_barrier() -> dict[str, Any]:
    return {
        "active": False,
        "causes": [],
        "checked": {},
        "cursor": 0,
        "frontier": [],
        "passes": 0,
        "reason": None,
    }


def _semantic_barrier(state: Mapping[str, Any]) -> dict[str, Any]:
    barrier = state.get("invalidation")
    if not isinstance(barrier, dict):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic invalidation barrier is unavailable",
        )
    return barrier


def _semantic_barrier_blocks(
    state: Mapping[str, Any], reference: Mapping[str, Any] | SemanticRef
) -> bool:
    """Report whether an unfinished barrier still covers one current record.

    A record with no dependencies cannot depend on a changed root, and a record
    whose current version is already the repaired one carries its own state, so
    only a dependency-bearing record that has not been examined against every
    known cause stays unavailable.
    """

    barrier = state.get("invalidation")
    if not isinstance(barrier, dict) or not barrier.get("active"):
        return False
    try:
        resolved = (
            reference.as_dict()
            if isinstance(reference, SemanticRef)
            else {
                "content_version": reference["content_version"],
                "id": reference["id"],
            }
        )
    except (KeyError, TypeError):
        return False
    history = state.get("records", {}).get(str(resolved["id"]))
    if not history:
        return False
    latest = history[-1]
    if int(latest["content_version"]) != int(resolved["content_version"]):
        return False
    if not latest["dependencies"] or latest["status"] == "invalidated":
        return False
    return int(barrier["checked"].get(str(resolved["id"]), 0)) < len(
        barrier["causes"]
    )


def _semantic_start_invalidation(
    state: dict[str, Any],
    changed: Sequence[SemanticRef | Mapping[str, Any]],
    *,
    reason: str,
) -> None:
    """Publish a barrier over the causes whose closure still has to be checked."""

    barrier = _semantic_barrier(state)
    causes = [
        item if isinstance(item, SemanticRef) else SemanticRef.from_dict(item)
        for item in changed
    ]
    known = {
        (item["kind"], item["id"], int(item["content_version"]))
        for item in barrier["causes"]
    }
    for cause in causes:
        key = (cause.kind, cause.id, cause.content_version)
        if key in known:
            continue
        if len(barrier["causes"]) >= state["bounds"]["max_records"]:
            raise FieldIntelligenceError(
                "WORK_CAPACITY", "semantic invalidation causes are exhausted"
            )
        known.add(key)
        barrier["causes"].append(cause.as_dict())
    if not causes:
        return
    if not barrier["active"]:
        barrier["frontier"] = []
        barrier["checked"] = {}
    barrier["active"] = True
    barrier["cursor"] = 0
    barrier["reason"] = str(reason)


def _semantic_advance_invalidation(
    state: dict[str, Any], *, quanta: int
) -> dict[str, Any]:
    """Check a bounded number of records against every known invalidation cause."""

    barrier = _semantic_barrier(state)
    frontier = list(barrier["frontier"])
    if not barrier["active"]:
        return {
            "active": False,
            "causes": list(barrier["causes"]),
            "checked_records": len(barrier["checked"]),
            "frontier": frontier,
            "passes": int(barrier["passes"]),
            "pending_records": 0,
            "reason": barrier["reason"],
            "scans": 0,
        }
    budget = max(1, int(quanta))
    scans = 0
    while barrier["active"] and scans < budget:
        record_ids = sorted(state["records"])
        if int(barrier["cursor"]) >= len(record_ids):
            barrier["cursor"] = 0
            barrier["passes"] = int(barrier["passes"]) + 1
            if all(
                int(barrier["checked"].get(record_id, 0))
                >= len(barrier["causes"])
                for record_id in record_ids
            ):
                barrier["active"] = False
                break
        cause_count = len(barrier["causes"])
        if all(
            int(barrier["checked"].get(record_id, 0)) >= cause_count
            for record_id in record_ids
        ):
            barrier["active"] = False
            break
        record_id = record_ids[int(barrier["cursor"])]
        barrier["cursor"] = int(barrier["cursor"]) + 1
        scans += 1
        history = state["records"][record_id]
        record = history[-1]
        if int(barrier["checked"].get(record_id, 0)) < cause_count:
            cause_keys = {
                (item["kind"], item["id"], int(item["content_version"]))
                for item in barrier["causes"][
                    int(barrier["checked"].get(record_id, 0)) :
                ]
            }
            dependency_keys = {
                (item["kind"], item["id"], int(item["content_version"]))
                for item in record["dependencies"]
            }
            if (
                record["status"] not in {"expired", "invalidated", "revoked"}
                and dependency_keys & cause_keys
            ):
                cause = next(
                    item
                    for item in reversed(barrier["causes"])
                    if (
                        item["kind"],
                        item["id"],
                        int(item["content_version"]),
                    )
                    in dependency_keys
                )
                old_ref = semantic_record_ref(record)
                new_ref = _semantic_append_record(
                    state,
                    record_id=record_id,
                    kind=record["kind"],
                    payload=record["payload"],
                    status="invalidated",
                    epistemic_kind=record["epistemic_kind"],
                    dependencies=record["dependencies"],
                    support_roots=record["support_roots"],
                    derivation={
                        **record["derivation"],
                        "invalidation_cause": cause,
                        "reason": barrier["reason"],
                    },
                    applicability=record["applicability"],
                    valid_time=record["valid_time"],
                    frame=record["frame"],
                    units=record["units"],
                    scope=record["scope"],
                )
                _semantic_reindex_record(state, new_ref)
                frontier.append(new_ref)
                barrier["frontier"].append(new_ref)
                barrier["checked"][record_id] = len(barrier["causes"])
                old_key = (
                    old_ref.kind,
                    old_ref.id,
                    old_ref.content_version,
                )
                if not any(
                    (
                        item["kind"],
                        item["id"],
                        int(item["content_version"]),
                    )
                    == old_key
                    for item in barrier["causes"]
                ):
                    if len(barrier["causes"]) >= state["bounds"]["max_records"]:
                        raise FieldIntelligenceError(
                            "WORK_CAPACITY",
                            "semantic invalidation frontier is exhausted",
                        )
                    barrier["causes"].append(old_ref.as_dict())
                continue
        barrier["checked"][record_id] = len(barrier["causes"])
    pending = sum(
        1
        for record_id, history in state["records"].items()
        if history[-1]["dependencies"]
        and history[-1]["status"] != "invalidated"
        and int(barrier["checked"].get(record_id, 0)) < len(barrier["causes"])
    )
    return {
        "active": bool(barrier["active"]),
        "causes": list(barrier["causes"]),
        "checked_records": len(barrier["checked"]),
        "frontier": frontier,
        "passes": int(barrier["passes"]),
        "pending_records": pending,
        "reason": barrier["reason"],
        "scans": scans,
    }


def _semantic_invalidate(
    state: dict[str, Any],
    changed: Sequence[SemanticRef | Mapping[str, Any]],
    *,
    reason: str,
) -> list[dict[str, Any]]:
    """Publish an invalidation barrier and check as much of its closure as fits."""

    _semantic_start_invalidation(state, changed, reason=reason)
    summary = _semantic_advance_invalidation(
        state, quanta=int(state["bounds"]["max_work"])
    )
    return list(summary["frontier"])


def _canonical_mechanism_program(
    program: Mapping[str, Any],
) -> dict[str, Any]:
    canonical = canonical_semantic_program_payload(program)
    if canonical["program_kind"] not in SEMANTIC_MECHANISM_KINDS:
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_PROGRAM",
            "representation and procedure programs are not transition mechanisms",
        )
    return canonical


def _mechanism_required_work(program: Mapping[str, Any], depth: int = 0) -> int:
    if depth > 8:
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_PROGRAM", "mechanism nesting is exhausted"
        )
    canonical = _canonical_mechanism_program(program)
    kind = canonical["program_kind"]
    body = canonical["body"]
    if kind == "table":
        rows = body.get("rows", [])
        if not isinstance(rows, list):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_PROGRAM", "table rows are invalid"
            )
        return max(1, len(rows))
    if kind == "affine":
        outputs = body.get("outputs", {})
        if not isinstance(outputs, dict):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_PROGRAM", "affine outputs are invalid"
            )
        return max(1, len(outputs))
    if kind == "factor":
        constraints = body.get("constraints", [])
        if not isinstance(constraints, list):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_PROGRAM", "factor constraints are invalid"
            )
        return max(1, len(constraints))
    if kind == "hybrid":
        modes = body.get("modes", {})
        transitions = body.get("transitions", [])
        if (
            not isinstance(modes, dict)
            or not modes
            or not isinstance(transitions, list)
        ):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_PROGRAM", "hybrid body is invalid"
            )
        nested_work = sum(
            _mechanism_required_work(item, depth + 1)
            for item in modes.values()
        )
        transition_work = sum(
            max(
                1,
                sum(
                    1
                    for transition in transitions
                    if isinstance(transition, Mapping)
                    and transition.get("from") == mode
                ),
            )
            for mode in modes
        )
        return max(1, nested_work + transition_work)
    return 1


def mechanism_step_state(
    program: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    action: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    interval: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standalone task for the same fixed mechanism interpreter."""
    if not isinstance(program, Mapping) or not isinstance(state, Mapping):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_STATE",
            "mechanism program and state must be mappings",
        )
    for label, value in (
        ("action", action),
        ("context", context),
        ("interval", interval),
    ):
        if value is not None and not isinstance(value, Mapping):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_STATE",
                f"mechanism {label} must be a mapping",
            )

    return {
        "family": MECHANISM_STEP_KERNEL,
        "schema": MECHANISM_STATE_SCHEMA,
        "status": "running",
        "program": _canonical_mechanism_program(program),
        "state": _regional_plain(dict(state), "mechanism state"),
        "action": _regional_plain(dict(action or {}), "mechanism action"),
        "context": _regional_plain(dict(context or {}), "mechanism context"),
        "interval": _regional_plain(dict(interval or {}), "mechanism interval"),
        "result": None,
    }


def mechanism_step_kernel(
    state: Any, arguments: Mapping[str, Any], quantum: int
) -> KernelResult:
    """Execute a typed Program payload with bounded, deterministic work."""

    del arguments
    _regional_integer(
        quantum,
        "mechanism step quantum",
        minimum=1,
        maximum=MECHANISM_STEP_MAX_WORK,
    )
    if (
        not isinstance(state, Mapping)
        or set(state)
        != {
            "action",
            "family",
            "context",
            "interval",
            "program",
            "result",
            "schema",
            "state",
            "status",
        }
        or state.get("schema") != MECHANISM_STATE_SCHEMA
        or state.get("family") != MECHANISM_STEP_KERNEL
    ):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_STATE", "mechanism task state is invalid"
        )
    current = _regional_plain(dict(state), "mechanism task state")
    if any(
        not isinstance(current[name], dict)
        for name in ("action", "context", "interval", "program", "state")
    ):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_STATE",
            "mechanism state, program, action, context, and interval must be mappings",
        )
    try:
        current["program"] = _canonical_mechanism_program(current["program"])
    except (RegionalFieldError, ValueError) as exc:
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_PROGRAM", str(exc)
        ) from exc
    if current["status"] == "done":
        result = _semantic_validate_result(
            current["result"], "completed mechanism result"
        )
        if result["operation"] != "mechanism-step":
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_STATE",
                "completed mechanism result names the wrong operation",
            )
        return KernelResult(
            state=current,
            status="done",
            work=0,
            output=result,
        )
    if current["status"] != "running":
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_STATE", "mechanism task status is invalid"
        )
    required_work = _mechanism_required_work(current["program"])
    declared_work = int(current["program"]["bounds"]["max_work"])
    if required_work > declared_work or required_work > quantum:
        outcome = {
            "status": "resource-exhausted",
            "values": current["state"],
            "alternatives": [],
            "limitations": [
                (
                    "program-work-bound"
                    if required_work > declared_work
                    else "kernel-quantum"
                )
            ],
            "required_work": required_work,
            "available_work": min(declared_work, quantum),
            "work": 1,
        }
        current["result"] = _semantic_result(
            "mechanism-step", "resource-exhausted", outcome=outcome
        )
        current["status"] = "done"
        return KernelResult(
            state=current,
            status="done",
            work=1,
            output=current["result"],
        )
    try:
        outcome = execute_semantic_program(
            current["program"],
            current["state"],
            action=current["action"],
            context=current["context"],
            interval=current["interval"],
        )
    except (RegionalFieldError, ValueError) as exc:
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_PROGRAM", str(exc)
        ) from exc
    current["result"] = _semantic_result(
        "mechanism-step", outcome["status"], outcome=outcome
    )
    current["status"] = "done"
    return KernelResult(
        state=current,
        status="done",
        work=min(MECHANISM_STEP_MAX_WORK, max(1, int(outcome["work"]))),
        output=current["result"],
    )


def mechanism_step_kernel_factory() -> Any:
    return mechanism_step_kernel


def _semantic_keys(
    request: Mapping[str, Any],
    *,
    required: Sequence[str] = (),
    optional: Sequence[str] = (),
) -> None:
    allowed = {"operation", "operation_id", *required, *optional}
    missing = set(required) - set(request)
    unknown = set(request) - allowed
    if missing or unknown:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_OPERATION",
            (
                f"semantic operation keys are invalid"
                f" (missing={sorted(missing)}, unknown={sorted(unknown)})"
            ),
        )


def _semantic_interval(
    value: Mapping[str, Any] | None,
    *,
    default: float,
) -> dict[str, float]:
    if value is None:
        return {"start": default, "end": default}
    if not isinstance(value, Mapping) or set(value) != {"end", "start"}:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_TIME",
            "semantic interval requires exactly start and end",
        )
    start = _finite(value["start"], "semantic interval start")
    end = _finite(value["end"], "semantic interval end")
    if end < start:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_TIME", "semantic interval is reversed"
        )
    return {"start": start, "end": end}


def _semantic_observation_rows(
    request: Mapping[str, Any], bounds: Mapping[str, int]
) -> list[dict[str, Any]]:
    raw_rows = request.get("observations", [])
    if not isinstance(raw_rows, list):
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", "observations must be a list"
        )
    rows = [
        _regional_plain(dict(item), "semantic observation")
        if isinstance(item, Mapping)
        else None
        for item in raw_rows
    ]
    if any(item is None for item in rows):
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", "observation rows must be mappings"
        )
    packed = request.get("packed_observations")
    if packed is not None:
        if (
            not isinstance(packed, Mapping)
            or set(packed) != {"columns", "rows"}
            or not isinstance(packed["columns"], list)
            or not isinstance(packed["rows"], list)
            or any(
                not isinstance(column, str) or not column
                for column in packed["columns"]
            )
            or len(set(packed["columns"])) != len(packed["columns"])
        ):
            raise FieldIntelligenceError(
                "INVALID_OBSERVATION", "packed observations are invalid"
            )
        for raw in packed["rows"]:
            if (
                not isinstance(raw, list)
                or len(raw) != len(packed["columns"])
            ):
                raise FieldIntelligenceError(
                    "INVALID_OBSERVATION",
                    "packed observation row width is invalid",
                )
            rows.append(dict(zip(packed["columns"], raw, strict=True)))
    if not rows and request.get("joint_alternatives") is None:
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", "observation delivery is empty"
        )
    if len(rows) > bounds["max_observations"]:
        raise FieldIntelligenceError(
            "WORK_CAPACITY", "observation batch exceeds its declared bound"
        )
    return cast(list[dict[str, Any]], rows)


def _semantic_joint_rows(
    value: Any,
    maximum: int,
    *,
    semantics: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value or len(value) > maximum:
        raise FieldIntelligenceError(
            "INVALID_BELIEF", "joint alternatives exceed their bound"
        )
    if semantics not in {
        "constraint-set",
        "model-family",
        "probability",
    }:
        raise FieldIntelligenceError(
            "INVALID_BELIEF", "joint belief semantics are invalid"
        )
    normalized: list[dict[str, Any]] = []
    total = 0.0
    for raw in value:
        expected_keys = (
            {"assignment", "weight"}
            if semantics == "probability"
            else {"assignment", "model"}
            if semantics == "model-family"
            else {"assignment"}
        )
        if (
            not isinstance(raw, Mapping)
            or set(raw) != expected_keys
            or not isinstance(raw["assignment"], Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_BELIEF",
                "joint alternative does not match its declared semantics",
            )
        row = {
            "assignment": _regional_plain(
                dict(raw["assignment"]), "joint assignment"
            )
        }
        if semantics == "probability":
            weight = _finite(raw["weight"], "joint alternative weight")
            if weight <= 0.0:
                raise FieldIntelligenceError(
                    "INVALID_BELIEF",
                    "joint alternative weight must be positive",
                )
            row["weight"] = weight
            total += weight
        elif semantics == "model-family":
            row["model"] = _identifier(
                raw["model"], "joint alternative model"
            )
        normalized.append(row)
    normalized.sort(
        key=lambda item: (
            canonical_json_bytes(item["assignment"]),
            str(item.get("model", "")),
        )
    )
    identity_keys = {
        canonical_json_bytes(
            {
                "assignment": item["assignment"],
                **(
                    {"model": item["model"]}
                    if semantics == "model-family"
                    else {}
                ),
            }
        )
        for item in normalized
    }
    if len(identity_keys) != len(normalized):
        raise FieldIntelligenceError(
            "INVALID_BELIEF", "joint alternatives contain duplicates"
        )
    if semantics == "probability":
        for item in normalized:
            item["weight"] = item["weight"] / total
    return normalized


def _semantic_binding_rows(
    value: Any,
    maximum: int,
    *,
    semantics: str,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > maximum:
        raise FieldIntelligenceError(
            "INVALID_BELIEF", "binding alternatives exceed their bound"
        )
    if not value:
        if semantics != "deterministic":
            raise FieldIntelligenceError(
                "INVALID_BELIEF",
                "empty binding alternatives must be deterministic",
            )
        return []
    if semantics not in {
        "constraint-set",
        "model-family",
        "probability",
    }:
        raise FieldIntelligenceError(
            "INVALID_BELIEF", "binding belief semantics are invalid"
        )
    normalized: list[dict[str, Any]] = []
    total = 0.0
    for raw in value:
        expected_keys = (
            {"value", "weight"}
            if semantics == "probability"
            else {"model", "value"}
            if semantics == "model-family"
            else {"value"}
        )
        if not isinstance(raw, Mapping) or set(raw) != expected_keys:
            raise FieldIntelligenceError(
                "INVALID_BELIEF",
                "binding alternative does not match its declared semantics",
            )
        row = {
            "value": _regional_plain(
                raw["value"], "binding alternative value"
            )
        }
        if semantics == "probability":
            weight = _finite(raw["weight"], "binding alternative weight")
            if weight <= 0.0:
                raise FieldIntelligenceError(
                    "INVALID_BELIEF",
                    "binding alternative weight must be positive",
                )
            row["weight"] = weight
            total += weight
        elif semantics == "model-family":
            row["model"] = _identifier(
                raw["model"], "binding alternative model"
            )
        normalized.append(row)
    normalized.sort(key=canonical_json_bytes)
    if len({canonical_json_bytes(item) for item in normalized}) != len(
        normalized
    ):
        raise FieldIntelligenceError(
            "INVALID_BELIEF", "binding alternatives contain duplicates"
        )
    if semantics == "probability":
        for item in normalized:
            item["weight"] = float(item["weight"]) / total
    return normalized

def _semantic_receipt_stamp(
    value: Any, *, default_time: float
) -> dict[str, Any]:
    if value is None:
        return {
            "clock_domain": "machine-receipt",
            "time": default_time,
            "uncertainty": 0.0,
        }
    if not isinstance(value, Mapping) or set(value) != {
        "clock_domain",
        "time",
        "uncertainty",
    }:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_TIME",
            "receipt stamp requires clock_domain, time, and uncertainty",
        )
    uncertainty = _finite(value["uncertainty"], "receipt uncertainty")
    if uncertainty < 0.0:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_TIME",
            "receipt uncertainty must be nonnegative",
        )
    return {
        "clock_domain": _identifier(
            value["clock_domain"], "receipt clock domain"
        ),
        "time": _finite(value["time"], "receipt time"),
        "uncertainty": uncertainty,
    }


def _semantic_world_clock(value: Any) -> dict[str, Any]:
    if value is None:
        return {"clock_domain": "world", "uncertainty": 0.0}
    if not isinstance(value, Mapping) or set(value) != {
        "clock_domain",
        "uncertainty",
    }:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_TIME",
            "world clock requires clock_domain and uncertainty",
        )
    uncertainty = _finite(value["uncertainty"], "world clock uncertainty")
    if uncertainty < 0.0:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_TIME",
            "world clock uncertainty must be nonnegative",
        )
    return {
        "clock_domain": _identifier(
            value["clock_domain"], "world clock domain"
        ),
        "uncertainty": uncertainty,
    }


def _semantic_measurement_context(
    value: Any, label: str
) -> dict[str, Any]:
    if value is None:
        return {
            "availability": "observed",
            "censoring": {},
            "observed_mask": [],
            "precision": {},
            "selection": {},
            "smoothing": False,
        }
    allowed = {
        "availability",
        "censoring",
        "observed_mask",
        "precision",
        "selection",
        "smoothing",
    }
    if not isinstance(value, Mapping) or set(value) - allowed:
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", f"{label} is invalid"
        )
    availability = value.get("availability", "observed")
    if availability not in {
        "censored",
        "missing",
        "observed",
        "occluded",
        "partial",
    }:
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION",
            f"{label} availability is invalid",
        )
    observed_mask = value.get("observed_mask", [])
    if (
        not isinstance(observed_mask, list)
        or any(not isinstance(item, str) or not item for item in observed_mask)
        or len(set(observed_mask)) != len(observed_mask)
    ):
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", f"{label} observed mask is invalid"
        )
    raw_precision = value.get("precision", {})
    if isinstance(raw_precision, Mapping):
        precision = {
            _identifier(name, f"{label} precision coordinate"): _finite(
                number, f"{label} precision"
            )
            for name, number in raw_precision.items()
        }
        if any(number < 0.0 for number in precision.values()):
            raise FieldIntelligenceError(
                "INVALID_OBSERVATION",
                f"{label} precision must be nonnegative",
            )
    else:
        scalar_precision = _finite(raw_precision, f"{label} precision")
        if scalar_precision < 0.0:
            raise FieldIntelligenceError(
                "INVALID_OBSERVATION",
                f"{label} precision must be nonnegative",
            )
        precision = {"value": scalar_precision}
    raw_censoring = value.get("censoring", {})
    if not isinstance(raw_censoring, Mapping):
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", f"{label} censoring is invalid"
        )
    censoring: dict[str, list[float]] = {}
    for name, interval in raw_censoring.items():
        if not isinstance(interval, list) or len(interval) != 2:
            raise FieldIntelligenceError(
                "INVALID_OBSERVATION",
                f"{label} censoring interval is invalid",
            )
        lower = _finite(interval[0], f"{label} censoring lower bound")
        upper = _finite(interval[1], f"{label} censoring upper bound")
        if upper < lower:
            raise FieldIntelligenceError(
                "INVALID_OBSERVATION",
                f"{label} censoring interval is reversed",
            )
        censoring[
            _identifier(name, f"{label} censoring coordinate")
        ] = [lower, upper]
    selection = value.get("selection", {})
    if not isinstance(selection, Mapping):
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", f"{label} selection is invalid"
        )
    smoothing = value.get("smoothing", False)
    if not isinstance(smoothing, bool):
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", f"{label} smoothing flag is invalid"
        )
    return {
        "availability": availability,
        "censoring": censoring,
        "observed_mask": observed_mask,
        "precision": precision,
        "selection": _regional_plain(dict(selection), f"{label} selection"),
        "smoothing": smoothing,
    }


def _semantic_observation_program(
    state: Mapping[str, Any], value: Any, label: str
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", f"{label} must be a Program reference"
        )
    reference, record = _semantic_reference(
        state, value, expected_kind="Program", require_current=True
    )
    if record["status"] != "active":
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", f"{label} is not active"
        )
    return reference.as_dict()


def _semantic_time_invalidate(
    state: dict[str, Any],
    event_time: Mapping[str, float],
    affected_bindings: Sequence[str],
) -> list[dict[str, Any]]:
    frontier: list[dict[str, Any]] = []
    affected = set(affected_bindings)
    for record_id, raw_ref in list(state["current"]["Assessment"].items()):
        record = resolve_semantic_record(state["records"], raw_ref)
        payload = record["payload"]
        if (
            record["status"] != "active"
            or payload.get("purpose") != "prediction"
        ):
            continue
        prediction_time = record["valid_time"]
        prediction_bindings = set(payload.get("binding_ids", []))
        if (
            not isinstance(prediction_time, Mapping)
            or float(prediction_time.get("end", -math.inf))
            < float(event_time["start"])
            or (affected and not affected.intersection(prediction_bindings))
        ):
            continue
        invalidated_ref = _semantic_append_record(
            state,
            record_id=record_id,
            kind="Assessment",
            payload=payload,
            status="invalidated",
            epistemic_kind=record["epistemic_kind"],
            dependencies=record["dependencies"],
            support_roots=record["support_roots"],
            derivation={
                **record["derivation"],
                "reason": "late-observation",
            },
            applicability=record["applicability"],
            valid_time=record["valid_time"],
            frame=record["frame"],
            units=record["units"],
            scope=record["scope"],
        )
        _semantic_reindex_record(state, invalidated_ref)
        frontier.append(invalidated_ref)
    return frontier


def _semantic_observe(
    state: dict[str, Any],
    request: Mapping[str, Any],
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("delivery_id", "event_id"),
        optional=(
            "action_id",
            "chunk_index",
            "episode_id",
            "frame",
            "joint_alternatives",
            "joint_id",
            "joint_model",
            "joint_semantics",
            "measurement",
            "measurement_program",
            "obligations",
            "observations",
            "packed_observations",
            "receipt",
            "scope",
            "source",
            "stream_id",
            "support_roots",
            "time",
            "world_clock",
        ),
    )
    delivery_id = _identifier(request["delivery_id"], "delivery identity")
    event_id = _identifier(request["event_id"], "event identity")
    delivery_sha256 = sha256_value(
        {
            name: value
            for name, value in request.items()
            if name != "operation_id"
        }
    )
    prior = state["indexes"]["deliveries"].get(delivery_id)
    if prior is not None:
        if prior.get("request_sha256") != delivery_sha256:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "delivery identity was already used by different content",
            )
        replay = {**dict(prior["result"]), "replayed": True}
        return replay, 1
    stream_key: str | None = None
    if event_id in state["current"]["Event"]:
        raise FieldIntelligenceError(
            "OPERATION_CONFLICT",
            "event identity was already used by another delivery",
        )
    stream_id = request.get("stream_id")
    chunk_index = request.get("chunk_index")
    if (stream_id is None) != (chunk_index is None):
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION",
            "stream identity and chunk index must be supplied together",
        )
    if stream_id is not None:
        stream_key = (
            f"{_identifier(stream_id, 'stream identity')}:"
            f"{_regional_integer(chunk_index, 'stream chunk index')}"
        )
        prior_chunk = state["indexes"]["streams"].get(stream_key)
        if prior_chunk is not None and prior_chunk != delivery_sha256:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT", "stream chunk content changed"
            )
    rows = _semantic_observation_rows(request, state["bounds"])
    event_time = _semantic_interval(
        cast(Any, request.get("time")), default=float(state["time"]["now"])
    )
    source = _regional_plain(request.get("source", {}), "observation source")
    if not isinstance(source, Mapping):
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", "observation source must be a mapping"
        )
    receipt = _semantic_receipt_stamp(
        request.get("receipt"),
        default_time=float(state["ledger"]["transitions"]) + 1.0,
    )
    world_clock = _semantic_world_clock(request.get("world_clock"))
    event_measurement = _semantic_measurement_context(
        request.get("measurement"), "event measurement context"
    )
    measurement_program_ref = _semantic_observation_program(
        state,
        request.get("measurement_program"),
        "event measurement program",
    )
    joint_present = request.get("joint_alternatives") is not None
    if not joint_present and (
        request.get("joint_semantics") is not None
        or request.get("joint_model") is not None
    ):
        raise FieldIntelligenceError(
            "INVALID_BELIEF",
            "joint belief metadata requires joint alternatives",
        )
    joint_semantics: str | None = None
    joint_model: dict[str, Any] | None = None
    if joint_present:
        joint_semantics = _identifier(
            request.get("joint_semantics"), "joint belief semantics"
        )
        raw_joint_model = request.get("joint_model")
        if joint_semantics == "probability":
            joint_model = _semantic_probability_model(
                raw_joint_model, "joint probability model"
            )
        elif raw_joint_model is not None:
            raise FieldIntelligenceError(
                "INVALID_BELIEF",
                "only probabilistic joint belief accepts a probability model",
            )
    action_id = (
        None
        if request.get("action_id") is None
        else _identifier(request["action_id"], "related action identity")
    )
    episode_id = (
        None
        if request.get("episode_id") is None
        else _identifier(request["episode_id"], "episode identity")
    )
    support_roots = request.get("support_roots", [])
    if (
        not isinstance(support_roots, list)
        or any(not isinstance(item, str) or not item for item in support_roots)
    ):
        raise FieldIntelligenceError(
            "INVALID_OBSERVATION", "observation support roots are invalid"
        )
    event_ref = _semantic_append_record(
        state,
        record_id=event_id,
        kind="Event",
        payload={
            "action_id": action_id,
            "admitted_k": int(state["ledger"]["transitions"]) + 1,
            "delivery_id": delivery_id,
            "episode_id": episode_id,
            "measurement": event_measurement,
            "measurement_program": measurement_program_ref,
            "joint_belief": (
                None
                if not joint_present
                else {
                    "id": request.get("joint_id", f"joint:{event_id}"),
                    "semantics": joint_semantics,
                }
            ),
            "observation_count": len(rows),
            "receipt": receipt,
            "source": dict(source),
            "world_clock": world_clock,
        },
        epistemic_kind="observed",
        valid_time=event_time,
        frame=request.get("frame", state["frame"]),
        scope=request.get("scope", state["scope"]),
        dependencies=(
            ()
            if measurement_program_ref is None
            else (measurement_program_ref,)
        ),
        support_roots=support_roots,
    )
    changed_refs: list[dict[str, Any]] = []
    joint_ref: dict[str, Any] | None = None
    if request.get("joint_alternatives") is not None:
        joint_id = _identifier(
            request.get("joint_id", f"joint:{event_id}"),
            "joint belief identity",
        )
        alternatives = _semantic_joint_rows(
            request["joint_alternatives"],
            state["bounds"]["max_alternatives"],
            semantics=cast(str, joint_semantics),
        )
        old_joint = state["current"]["Value"].get(joint_id)
        if old_joint is not None:
            changed_refs.append(old_joint)
        joint_ref = _semantic_append_record(
            state,
            record_id=joint_id,
            kind="Value",
            payload={
                "alternatives": alternatives,
                "belief_semantics": joint_semantics,
                "probability_model": joint_model,
                "representation": "joint",
            },
            epistemic_kind="observed",
            dependencies=(event_ref,),
            support_roots=support_roots,
            valid_time=event_time,
            frame=request.get("frame", state["frame"]),
            scope=request.get("scope", state["scope"]),
        )
    binding_refs: list[dict[str, Any]] = []
    changed_binding_ids: list[str] = []
    for index, row in enumerate(rows):
        allowed = {
            "alternatives",
            "belief_semantics",
            "attribute",
            "binding_id",
            "confidence",
            "epistemic_kind",
            "frame",
            "measurement",
            "measurement_program",
            "probability_model",
            "status",
            "subject",
            "units",
            "value",
        }
        if set(row) - allowed or "value" not in row:
            raise FieldIntelligenceError(
                "INVALID_OBSERVATION",
                f"observation {index} has invalid keys",
            )
        subject = _identifier(
            row.get("subject", "world"), f"observation {index} subject"
        )
        attribute = _identifier(
            row.get("attribute", "value"),
            f"observation {index} attribute",
        )
        binding_id = _identifier(
            row.get("binding_id", f"binding:{subject}:{attribute}"),
            f"observation {index} binding identity",
        )
        confidence = _finite(
            row.get("confidence", 1.0),
            f"observation {index} confidence",
        )
        if not 0.0 <= confidence <= 1.0:
            raise FieldIntelligenceError(
                "INVALID_OBSERVATION", "observation confidence is outside [0, 1]"
            )
        binding_semantics = str(
            row.get("belief_semantics", "deterministic")
        )
        alternatives = _semantic_binding_rows(
            row.get("alternatives", []),
            state["bounds"]["max_alternatives"],
            semantics=binding_semantics,
        )
        raw_binding_model = row.get("probability_model")
        binding_probability_model = (
            _semantic_probability_model(
                raw_binding_model,
                f"observation {index} probability model",
            )
            if binding_semantics == "probability"
            else None
        )
        if binding_semantics != "probability" and raw_binding_model is not None:
            raise FieldIntelligenceError(
                "INVALID_BELIEF",
                "only a probabilistic binding accepts a probability model",
            )
        measurement = _semantic_measurement_context(
            row.get("measurement", request.get("measurement")),
            f"observation {index} measurement context",
        )
        observed_mask = measurement["observed_mask"]
        if observed_mask and (
            not isinstance(row["value"], Mapping)
            or any(name not in row["value"] for name in observed_mask)
        ):
            raise FieldIntelligenceError(
                "INVALID_OBSERVATION",
                f"observation {index} mask names an unavailable coordinate",
            )
        observation_program_ref = _semantic_observation_program(
            state,
            row.get(
                "measurement_program",
                request.get("measurement_program"),
            ),
            f"observation {index} measurement program",
        )
        value_id = f"value:{event_id}:{index}:{binding_id}"
        value_ref = _semantic_append_record(
            state,
            record_id=value_id,
            kind="Value",
            payload={
                "alternatives": alternatives,
                "belief_semantics": binding_semantics,
                "probability_model": binding_probability_model,
                "confidence": confidence,
                "value": _regional_plain(
                    row["value"], "observed semantic value"
                ),
                "measurement": measurement,
                "measurement_program": observation_program_ref,
            },
            status=str(row.get("status", "active")),
            epistemic_kind=str(row.get("epistemic_kind", "observed")),
            dependencies=(
                event_ref,
                *(() if joint_ref is None else (joint_ref,)),
                *(
                    ()
                    if observation_program_ref is None
                    else (observation_program_ref,)
                ),
            ),
            support_roots=support_roots,
            valid_time=event_time,
            frame=row.get("frame", request.get("frame", state["frame"])),
            units=row.get("units"),
            scope=request.get("scope", state["scope"]),
        )
        old_binding = state["current"]["Binding"].get(binding_id)
        if old_binding is not None:
            changed_refs.append(old_binding)
        binding_ref = _semantic_append_record(
            state,
            record_id=binding_id,
            kind="Binding",
            payload={
                "alternatives": alternatives,
                "belief_semantics": binding_semantics,
                "probability_model": binding_probability_model,
                "attribute": attribute,
                "confidence": confidence,
                "subject": subject,
                "value": _regional_plain(
                    row["value"], "observed binding value"
                ),
                "measurement": measurement,
                "measurement_program": observation_program_ref,
                "value_ref": value_ref,
            },
            status=str(row.get("status", "active")),
            epistemic_kind=str(row.get("epistemic_kind", "observed")),
            dependencies=(
                event_ref,
                value_ref,
                *(() if joint_ref is None else (joint_ref,)),
            ),
            support_roots=support_roots,
            valid_time=event_time,
            frame=row.get("frame", request.get("frame", state["frame"])),
            units=row.get("units"),
            scope=request.get("scope", state["scope"]),
        )

        binding_refs.append(binding_ref)
        changed_binding_ids.append(binding_id)
    obligations = request.get("obligations", [])
    if not isinstance(obligations, list):
        raise FieldIntelligenceError(
            "INVALID_OBLIGATION", "observation obligations must be a list"
        )
    obligation_refs: list[dict[str, Any]] = []
    for raw in obligations:
        if not isinstance(raw, Mapping) or "obligation_id" not in raw:
            raise FieldIntelligenceError(
                "INVALID_OBLIGATION", "observation obligation is invalid"
            )
        obligation = _regional_plain(
            dict(raw), "observation obligation"
        )
        obligation_id = _identifier(
            obligation.pop("obligation_id"), "obligation identity"
        )
        raw_valid_time = obligation.pop("valid_time", None)
        obligation_time = (
            None
            if raw_valid_time is None
            else _semantic_interval(
                cast(Any, raw_valid_time),
                default=float(event_time["end"]),
            )
        )
        if obligation_id in state["current"]["Obligation"]:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "obligation identity was already published by another delivery",
            )
        obligation_ref = _semantic_append_record(
            state,
            record_id=obligation_id,
            kind="Obligation",
            payload={**obligation, "state": "pending"},
            dependencies=(event_ref,),
            support_roots=support_roots,
            valid_time=obligation_time,
            scope=request.get("scope", state["scope"]),
        )

        obligation_refs.append(obligation_ref)
    frontier = _semantic_invalidate(
        state, changed_refs, reason="binding-revision"
    )
    if event_time["start"] < float(state["time"]["now"]):
        frontier.extend(
            _semantic_time_invalidate(
                state, event_time, changed_binding_ids
            )
        )
    if joint_ref is not None:
        _semantic_reindex_record(state, joint_ref)
    for reference in (*binding_refs, *obligation_refs):
        _semantic_reindex_record(state, reference)
    _semantic_reindex_record(state, event_ref)
    if stream_key is not None:
        state["indexes"]["streams"][stream_key] = delivery_sha256
    result = _semantic_result(
        "observe",
        "supported",
        event=event_ref,
        bindings=binding_refs,
        changed_binding_ids=sorted(set(changed_binding_ids)),
        invalidation_frontier=frontier,
        joint_belief=joint_ref,
        obligations=obligation_refs,
        replayed=False,
    )
    state["indexes"]["deliveries"][delivery_id] = {
        "request_sha256": delivery_sha256,
        "result": result,
    }
    return result, max(
        1, 1 + len(rows) + len(obligations) + len(frontier)
    )


def _semantic_correct(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("correction_id", "replacement", "target"),
        optional=("reason", "source", "support_roots"),
    )
    correction_id = _identifier(
        request["correction_id"], "correction identity"
    )
    correction_event_id = f"event:correction:{correction_id}"
    if correction_event_id in state["current"]["Event"]:
        raise FieldIntelligenceError(
            "OPERATION_CONFLICT",
            "correction identity was already published",
        )
    if not isinstance(request["target"], Mapping):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_REFERENCE", "correction target is invalid"
        )
    target_ref, target = _semantic_reference(
        state, request["target"], require_current=True
    )
    if not isinstance(request["replacement"], Mapping):
        raise FieldIntelligenceError(
            "INVALID_CORRECTION", "correction replacement must be a mapping"
        )
    replacement = _regional_plain(
        dict(request["replacement"]), "correction replacement"
    )
    payload = {**target["payload"], **replacement}
    if target_ref.kind == "Binding":
        raw_alternatives = (
            []
            if "value" in replacement and "alternatives" not in replacement
            else replacement.get(
                "alternatives", target["payload"].get("alternatives", [])
            )
        )
        binding_semantics = str(
            replacement.get(
                "belief_semantics",
                (
                    "deterministic"
                    if not raw_alternatives
                    else target["payload"].get("belief_semantics", "")
                ),
            )
        )
        payload["alternatives"] = _semantic_binding_rows(
            raw_alternatives,
            state["bounds"]["max_alternatives"],
            semantics=binding_semantics,
        )
        payload["belief_semantics"] = binding_semantics
        raw_probability_model = replacement.get(
            "probability_model",
            (
                target["payload"].get("probability_model")
                if binding_semantics == "probability"
                else None
            ),
        )
        if binding_semantics == "probability":
            payload["probability_model"] = _semantic_probability_model(
                raw_probability_model, "corrected binding probability model"
            )
        else:
            if (
                "probability_model" in replacement
                and raw_probability_model is not None
            ):
                raise FieldIntelligenceError(
                    "INVALID_BELIEF",
                    "only a probabilistic binding accepts a probability model",
                )
            payload["probability_model"] = None
    dependencies: list[Mapping[str, Any]] = list(target["dependencies"])
    if target_ref.kind == "Binding" and "value" in replacement:
        value_ref = _semantic_append_record(
            state,
            record_id=f"value:{correction_id}:{target_ref.id}",
            kind="Value",
            payload={
                "alternatives": payload["alternatives"],
                "belief_semantics": payload["belief_semantics"],
                "probability_model": payload["probability_model"],
                "confidence": replacement.get(
                    "confidence", target["payload"].get("confidence", 1.0)
                ),
                "measurement": target["payload"].get("measurement", {}),
                "measurement_program": target["payload"].get(
                    "measurement_program"
                ),
                "value": replacement["value"],
            },
            epistemic_kind="corrected",
            support_roots=cast(Any, request.get("support_roots", [])),
            valid_time=target["valid_time"],
            frame=target["frame"],
            units=target["units"],
            scope=target["scope"],
        )
        payload["value_ref"] = value_ref
        prior_value_ref = target["payload"].get("value_ref")
        dependencies = [
            item
            for item in dependencies
            if not (
                isinstance(prior_value_ref, Mapping)
                and item == prior_value_ref
            )
        ]
        dependencies.append(value_ref)
    revised_ref = _semantic_append_record(
        state,
        record_id=target_ref.id,
        kind=target_ref.kind,
        payload=payload,
        status="active",
        epistemic_kind="corrected",
        dependencies=dependencies,
        support_roots=sorted(
            set(
                target["support_roots"]
                + list(cast(Any, request.get("support_roots", [])))
            )
        ),
        derivation={
            "correction_id": correction_id,
            "reason": request.get("reason"),
            "source": request.get("source"),
            "target": target_ref.as_dict(),
        },
        applicability=target["applicability"],
        valid_time=target["valid_time"],
        frame=target["frame"],
        units=target["units"],
        scope=target["scope"],
    )
    frontier = _semantic_invalidate(
        state, (target_ref,), reason=f"correction:{correction_id}"
    )
    _semantic_reindex_record(state, revised_ref)
    correction_event = _semantic_append_record(
        state,
        record_id=correction_event_id,
        kind="Event",
        payload={
            "correction_id": correction_id,
            "reason": request.get("reason"),
            "target": target_ref.as_dict(),
        },
        epistemic_kind="corrected",
        dependencies=(revised_ref,),
        support_roots=cast(Any, request.get("support_roots", [])),
        valid_time={"start": state["time"]["now"], "end": state["time"]["now"]},
    )
    _semantic_reindex_record(state, correction_event)
    return (
        _semantic_result(
            "correct",
            "supported",
            correction_event=correction_event,
            previous=target_ref.as_dict(),
            current=revised_ref,
            invalidation_frontier=frontier,
        ),
        max(1, 2 + len(frontier)),
    )


def _semantic_explanation(
    state: Mapping[str, Any],
    reference: Mapping[str, Any],
    allowed_roots: Sequence[str] | None,
) -> tuple[str, dict[str, Any]]:
    root_ref, root = _semantic_reference(state, reference)
    allowed = None if allowed_roots is None else set(allowed_roots)
    queue = [root_ref.as_dict()]
    seen: set[tuple[str, str, int]] = set()
    nodes: list[dict[str, Any]] = []
    limitations: list[str] = []
    while queue:
        raw = queue.pop(0)
        key = (raw["kind"], raw["id"], int(raw["content_version"]))
        if key in seen:
            continue
        seen.add(key)
        _, record = _semantic_reference(state, raw)
        visible_roots = (
            record["support_roots"]
            if allowed is None
            else [
                item for item in record["support_roots"] if item in allowed
            ]
        )
        if allowed is not None and record["support_roots"] and not visible_roots:
            limitations.append(f"support-redacted:{record['id']}")
        nodes.append(
            {
                "applicability": record["applicability"],
                "derivation": record["derivation"],
                "epistemic_kind": record["epistemic_kind"],
                "reference": semantic_record_ref(record).as_dict(),
                "status": record["status"],
                "support_roots": visible_roots,
            }
        )
        queue.extend(record["dependencies"])
        if len(nodes) > state["bounds"]["max_records"]:
            return "resource-exhausted", {
                "root": root_ref.as_dict(),
                "nodes": nodes,
                "limitations": [*limitations, "explanation-bound"],
            }
    current_ref = state["current"][root["kind"]].get(root["id"])
    status = (
        "supported"
        if current_ref == root_ref.as_dict() and root["status"] == "active"
        else "support-gap"
    )
    return status, {
        "root": root_ref.as_dict(),
        "current": current_ref,
        "nodes": nodes,
        "limitations": sorted(set(limitations)),
    }


def _semantic_representation_binding_inputs(
    state: Mapping[str, Any], value: Any
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, Any],
    list[str],
]:
    """Resolve exact observed Binding versions into transient inputs."""

    if (
        not isinstance(value, Mapping)
        or not value
        or len(value) > state["bounds"]["max_observations"]
        or any(not isinstance(role, str) for role in value)
    ):
        raise FieldIntelligenceError(
            "INVALID_QUERY",
            "representation Binding inputs must be a bounded nonempty mapping",
        )
    features: dict[str, Any] = {}
    source_refs: list[dict[str, Any]] = []
    input_metadata: dict[str, Any] = {}
    limitations: list[str] = []
    for raw_role in sorted(value):
        role = _identifier(raw_role, "representation input role")
        raw_input = value[raw_role]
        if (
            not isinstance(raw_input, Mapping)
            or set(raw_input) not in ({"binding"}, {"binding", "coordinate"})
            or not isinstance(raw_input["binding"], Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_QUERY",
                f"representation input {role} is invalid",
            )
        try:
            requested_ref = SemanticRef.from_dict(raw_input["binding"])
        except RegionalFieldError as exc:
            raise FieldIntelligenceError(
                "INVALID_QUERY",
                f"representation input {role} requires an exact Binding reference",
            ) from exc
        if requested_ref.kind != "Binding":
            raise FieldIntelligenceError(
                "INVALID_QUERY",
                f"representation input {role} must reference a Binding",
            )
        coordinate = (
            None
            if "coordinate" not in raw_input
            else _identifier(
                raw_input["coordinate"],
                f"representation input {role} coordinate",
            )
        )
        try:
            _, record = _semantic_reference(
                state,
                requested_ref,
                expected_kind="Binding",
                require_current=True,
            )
        except FieldIntelligenceError as exc:
            if exc.code != "INVALID_SEMANTIC_REFERENCE":
                raise
            limitations.append(f"representation-binding-unavailable:{role}")
            continue
        if record["status"] != "active":
            limitations.append(
                f"representation-binding-{record['status']}:{role}"
            )
            continue
        if record["epistemic_kind"] not in {"corrected", "observed"}:
            limitations.append(f"representation-binding-unobserved:{role}")
            continue
        binding_payload = record["payload"]
        raw_value_ref = binding_payload.get("value_ref")
        if not isinstance(raw_value_ref, Mapping):
            limitations.append(f"representation-value-unavailable:{role}")
            continue
        try:
            value_ref, value_record = _semantic_reference(
                state,
                raw_value_ref,
                expected_kind="Value",
                require_current=True,
            )
        except FieldIntelligenceError as exc:
            if exc.code != "INVALID_SEMANTIC_REFERENCE":
                raise
            limitations.append(f"representation-value-unavailable:{role}")
            continue
        if value_record["status"] != "active":
            limitations.append(
                f"representation-value-{value_record['status']}:{role}"
            )
            continue
        if value_record["epistemic_kind"] not in {"corrected", "observed"}:
            limitations.append(f"representation-value-unobserved:{role}")
            continue
        payload = value_record["payload"]
        if (
            binding_payload.get("value", _ABSENT)
            != payload.get("value", _ABSENT)
            or record["frame"] != value_record["frame"]
            or record["units"] != value_record["units"]
        ):
            limitations.append(f"representation-binding-value-diverged:{role}")
            continue
        if (
            payload.get("belief_semantics") != "deterministic"
            or payload.get("alternatives")
        ):
            limitations.append(f"representation-binding-nondeterministic:{role}")
            continue
        source_refs.append(
            {
                "binding": requested_ref.as_dict(),
                "coordinate": coordinate,
                "role": role,
                "value": value_ref.as_dict(),
            }
        )
        measurement = payload.get("measurement")
        if not isinstance(measurement, Mapping):
            limitations.append(
                f"representation-binding-measurement-unavailable:{role}"
            )
            continue
        availability = measurement.get("availability")
        observed_mask = measurement.get("observed_mask")
        precision = measurement.get("precision")
        censoring = measurement.get("censoring")
        if not isinstance(observed_mask, list) or not isinstance(
            precision, Mapping
        ) or not isinstance(censoring, Mapping):
            limitations.append(
                f"representation-binding-measurement-unavailable:{role}"
            )
            continue
        if availability == "censored":
            limitations.append(f"representation-binding-censored:{role}")
            continue
        if availability not in {"observed", "partial"}:
            limitations.append(f"representation-binding-unobserved:{role}")
            continue
        if availability == "partial":
            if coordinate is None:
                limitations.append(f"representation-coordinate-required:{role}")
                continue
            if coordinate not in observed_mask:
                limitations.append(
                    f"representation-coordinate-unobserved:{role}:{coordinate}"
                )
                continue
        raw_value = payload.get("value", _ABSENT)
        if coordinate is None:
            if observed_mask:
                limitations.append(f"representation-coordinate-required:{role}")
                continue
            selected_value = raw_value
            selected_units = value_record["units"]
        else:
            if not isinstance(raw_value, Mapping) or coordinate not in raw_value:
                limitations.append(
                    f"representation-coordinate-unavailable:{role}:{coordinate}"
                )
                continue
            if observed_mask and coordinate not in observed_mask:
                limitations.append(
                    f"representation-coordinate-unobserved:{role}:{coordinate}"
                )
                continue
            selected_value = raw_value[coordinate]
            raw_units = value_record["units"]
            selected_units = (
                raw_units.get(coordinate, _ABSENT)
                if isinstance(raw_units, Mapping)
                else raw_units
            )
        precision_coordinate = coordinate if coordinate is not None else "value"
        raw_selected_precision = precision.get(
            precision_coordinate,
            precision.get("value") if coordinate is not None else None,
        )
        if raw_selected_precision is None:
            selected_precision = None
        elif (
            isinstance(raw_selected_precision, bool)
            or not isinstance(raw_selected_precision, (int, float))
            or not math.isfinite(float(raw_selected_precision))
            or float(raw_selected_precision) < 0.0
        ):
            limitations.append(f"representation-precision-invalid:{role}")
            continue
        else:
            selected_precision = float(raw_selected_precision)
        if (coordinate is None and censoring) or (
            coordinate is not None
            and (coordinate in censoring or "value" in censoring)
        ):
            limitations.append(f"representation-binding-censored:{role}")
            continue
        if selected_value is _ABSENT:
            limitations.append(
                f"representation-binding-value-unavailable:{role}"
            )
            continue
        if value_record["frame"] is None:
            limitations.append(f"representation-frame-missing:{role}")
            continue
        if selected_units is _ABSENT or selected_units is None:
            limitations.append(f"representation-units-missing:{role}")
            continue
        features[role] = selected_value
        input_metadata[role] = {
            "binding_epistemic_kind": record["epistemic_kind"],
            "confidence": payload.get("confidence"),
            "coordinate": coordinate,
            "frame": value_record["frame"],
            "measurement": measurement,
            "precision": selected_precision,
            "observed": True,
            "units": selected_units,
            "value_epistemic_kind": value_record["epistemic_kind"],
        }
    if not limitations and len(input_metadata) == len(value):
        first_metadata = next(iter(input_metadata.values()))
        if any(
            row["frame"] != first_metadata["frame"]
            for row in input_metadata.values()
        ):
            limitations.append("representation-frames-incompatible")
        if any(
            row["units"] != first_metadata["units"]
            for row in input_metadata.values()
        ):
            limitations.append("representation-units-incompatible")
    return (
        features,
        source_refs,
        input_metadata,
        sorted(set(limitations)),
    )


def _semantic_query(
    state: Mapping[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("query",),
        optional=("allowed_support_roots",),
    )
    query = request["query"]
    if not isinstance(query, Mapping) or "kind" not in query:
        raise FieldIntelligenceError(
            "INVALID_QUERY", "semantic query must name a kind"
        )
    kind = query["kind"]
    if kind == "binding":
        if set(query) != {"binding_id", "kind"}:
            raise FieldIntelligenceError(
                "INVALID_QUERY", "binding query keys are invalid"
            )
        binding = _semantic_current_record(
            state, "Binding", _identifier(query["binding_id"], "binding identity")
        )
        alternatives = binding["payload"].get("alternatives", [])
        is_active = binding["status"] == "active"
        status = (
            "support-gap"
            if not is_active
            else ("alternatives" if alternatives else "supported")
        )
        return _semantic_result(
            "query",
            status,
            answer=(binding["payload"].get("value") if is_active else None),
            alternatives=alternatives,
            binding=semantic_record_ref(binding).as_dict(),
            epistemic_kind=binding["epistemic_kind"],
            limitations=(
                [binding["status"]] if status == "support-gap" else []
            ),
        ), 1
    if kind == "perspective":
        allowed = {
            "agent_id",
            "attribute",
            "category",
            "kind",
            "name",
            "perspective_path",
        }
        if set(query) - allowed or "agent_id" not in query:
            raise FieldIntelligenceError(
                "INVALID_QUERY", "perspective query is invalid"
            )
        agent_id = _identifier(
            query["agent_id"], "perspective query agent"
        )
        raw_path = query.get("perspective_path", [agent_id])
        if (
            not isinstance(raw_path, list)
            or not raw_path
            or len(raw_path) > 8
        ):
            raise FieldIntelligenceError(
                "INVALID_QUERY", "perspective query path is invalid"
            )
        path = [
            _identifier(item, "perspective query path agent")
            for item in raw_path
        ]
        if path[-1] != agent_id:
            raise FieldIntelligenceError(
                "INVALID_QUERY",
                "perspective query path must end at the modeled agent",
            )
        perspective_id = (
            agent_id
            if len(path) == 1
            else f"nested:{sha256_value(path)[:32]}"
        )
        row = state["libraries"]["perspectives"].get(perspective_id)
        if row is None:
            return _semantic_result(
                "query",
                "support-gap",
                answer=None,
                limitations=["perspective-unavailable"],
                perspective_id=perspective_id,
                world_fact=False,
            ), 1
        attribute = query.get("attribute")
        if attribute is None and (
            "category" in query or "name" in query
        ):
            if not {"category", "name"}.issubset(query):
                raise FieldIntelligenceError(
                    "INVALID_QUERY",
                    "perspective category query is incomplete",
                )
            category = _identifier(
                query["category"], "perspective query category"
            )
            name = _identifier(
                query["name"], "perspective query name"
            )
            attribute = f"{category}:{name}"
        if attribute is not None:
            attribute = _identifier(
                attribute, "perspective query attribute"
            )
            raw_ref = row.get(attribute)
            if raw_ref is None:
                return _semantic_result(
                    "query",
                    "support-gap",
                    answer=None,
                    limitations=["perspective-attribute-unavailable"],
                    perspective_id=perspective_id,
                    world_fact=False,
                ), 1
            _, binding = _semantic_reference(
                state, raw_ref, expected_kind="Binding", require_current=True
            )
            return _semantic_result(
                "query",
                "supported" if binding["status"] == "active" else "support-gap",
                answer=(
                    binding["payload"].get("value")
                    if binding["status"] == "active"
                    else None
                ),
                attribute=attribute,
                binding=raw_ref,
                epistemic_kind="attributed",
                limitations=(
                    [] if binding["status"] == "active" else [binding["status"]]
                ),
                perspective_id=perspective_id,
                perspective_path=path,
                world_fact=False,
            ), 1
        answers: dict[str, Any] = {}
        references: dict[str, Any] = {}
        for name, raw_ref in sorted(row.items()):
            _, binding = _semantic_reference(
                state, raw_ref, expected_kind="Binding", require_current=True
            )
            if binding["status"] == "active":
                answers[name] = binding["payload"].get("value")
                references[name] = raw_ref
        return _semantic_result(
            "query",
            "supported" if answers else "support-gap",
            answer=answers if answers else None,
            bindings=references,
            epistemic_kind="attributed",
            limitations=[] if answers else ["perspective-inactive"],
            perspective_id=perspective_id,
            perspective_path=path,
            world_fact=False,
        ), max(1, len(row))
    if kind == "record":
        if set(query) != {"kind", "reference"} or not isinstance(
            query["reference"], Mapping
        ):
            raise FieldIntelligenceError(
                "INVALID_QUERY", "record query keys are invalid"
            )
        reference, record = _semantic_reference(state, query["reference"])
        current = state["current"][record["kind"]].get(record["id"])
        status = (
            "supported"
            if current == reference.as_dict() and record["status"] == "active"
            else "support-gap"
        )
        return _semantic_result(
            "query",
            status,
            record=record,
            current=current,
            limitations=([] if status == "supported" else ["stale-or-inactive"]),
        ), 1
    if kind == "joint":
        if set(query) != {"joint_id", "kind"}:
            raise FieldIntelligenceError(
                "INVALID_QUERY", "joint query keys are invalid"
            )
        joint_id = _identifier(query["joint_id"], "joint belief identity")
        raw_ref = state["beliefs"]["joint"].get(joint_id)
        if raw_ref is None:
            return _semantic_result(
                "query",
                "support-gap",
                answer=None,
                alternatives=[],
                limitations=["joint-belief-unavailable"],
            ), 1
        _, record = _semantic_reference(state, raw_ref, require_current=True)
        alternatives = record["payload"]["alternatives"]
        is_active = record["status"] == "active"
        status = (
            "support-gap"
            if not is_active
            else ("alternatives" if len(alternatives) > 1 else "supported")
        )
        return _semantic_result(
            "query",
            status,
            answer=(alternatives[0] if is_active and len(alternatives) == 1 else None),
            alternatives=alternatives,
            joint_belief=raw_ref,
            belief_semantics=record["payload"].get("belief_semantics"),
            probability_model=record["payload"].get("probability_model"),
            limitations=[] if is_active else [record["status"]],
        ), 1
    if kind == "predictive-state":
        allowed = {
            "action",
            "context",
            "history",
            "kind",
            "question",
            "representation_id",
            "signature",
        }
        if (
            set(query) - allowed
            or not {
                "history",
                "kind",
                "representation_id",
                "signature",
            }.issubset(query)
            or not isinstance(query["history"], list)
            or not isinstance(query.get("action", {}), Mapping)
            or not isinstance(query.get("context", {}), Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_QUERY", "predictive-state query is invalid"
            )
        representation_id = _identifier(
            query["representation_id"], "predictive state identity"
        )
        raw_ref = state["beliefs"]["predictive_classes"].get(
            representation_id
        )
        if raw_ref is None:
            return _semantic_result(
                "query",
                "support-gap",
                answer=None,
                alternatives=[],
                representation=None,
                limitations=["predictive-state-unavailable"],
            ), 1
        _, record = _semantic_reference(state, raw_ref, require_current=True)
        if record["status"] != "active":
            return _semantic_result(
                "query",
                "support-gap",
                answer=None,
                alternatives=[],
                representation=raw_ref,
                limitations=[f"predictive-state-{record['status']}"],
            ), 1
        program = canonical_semantic_program_payload(
            record["payload"]["program"]
        )
        body = program["body"]
        window = _regional_integer(
            body.get("window"),
            "predictive state window",
            minimum=1,
            maximum=256,
        )
        classes = body.get("classes")
        if not isinstance(classes, list):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "predictive state classes are invalid",
            )
        query_signature = _semantic_predictive_signature(
            query["signature"], "predictive query signature"
        )
        if query_signature != body.get("signature"):
            return _semantic_result(
                "query",
                "support-gap",
                answer=None,
                alternatives=[],
                representation=raw_ref,
                signature=query_signature,
                limitations=["predictive-signature-mismatch"],
            ), 1
        history = _regional_plain(
            query["history"][-window:], "predictive query history"
        )
        condition = {
            "action": _regional_plain(
                dict(query.get("action", {})), "predictive query action"
            ),
            "context": _regional_plain(
                dict(query.get("context", {})), "predictive query context"
            ),
            "question": _regional_plain(
                query.get("question"), "predictive query question"
            ),
        }
        selected_class: Mapping[str, Any] | None = None
        for candidate in classes:
            if not isinstance(candidate, Mapping) or not isinstance(
                candidate.get("histories"), list
            ):
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "predictive state class is invalid",
                )
            if history in candidate["histories"]:
                selected_class = candidate
                break
        if selected_class is None:
            return _semantic_result(
                "query",
                "support-gap",
                answer=None,
                alternatives=[],
                representation=raw_ref,
                signature=query_signature,
                limitations=["predictive-history-uncovered"],
            ), max(1, len(classes))
        tests = selected_class.get("tests")
        if not isinstance(tests, list):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "predictive state tests are invalid",
            )
        selected_test = next(
            (
                test
                for test in tests
                if isinstance(test, Mapping)
                and test.get("condition") == condition
            ),
            None,
        )
        if selected_test is None or not isinstance(
            selected_test.get("consequences"), list
        ):
            return _semantic_result(
                "query",
                "support-gap",
                answer=None,
                alternatives=[],
                representation=raw_ref,
                class_id=selected_class.get("class_id"),
                signature=query_signature,
                limitations=["predictive-condition-uncovered"],
            ), max(1, len(tests))
        prediction_semantics = selected_test.get("prediction_semantics")
        if prediction_semantics not in {"constraint-set", "probability"}:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "predictive state semantics are invalid",
            )
        consequences = selected_test["consequences"]
        alternatives = []
        for item in consequences:
            expected = (
                {"future", "support_count", "weight"}
                if prediction_semantics == "probability"
                else {"future", "support_count"}
            )
            if not isinstance(item, Mapping) or set(item) != expected:
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "predictive state consequence is invalid",
                )
            alternative = {
                "support_count": item["support_count"],
                "values": item["future"],
            }
            if prediction_semantics == "probability":
                alternative["weight"] = item["weight"]
            alternatives.append(alternative)
        if not alternatives:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "predictive state consequence set is empty",
            )
        status = "supported" if len(alternatives) == 1 else "alternatives"
        return _semantic_result(
            "query",
            status,
            answer=(
                alternatives[0]["values"]
                if len(alternatives) == 1
                else None
            ),
            alternatives=alternatives,
            representation=raw_ref,
            class_id=selected_class.get("class_id"),
            prediction_semantics=prediction_semantics,
            probability_model=query_signature["probability_model"],
            signature=query_signature,
            split_registry=record["payload"].get("splits", []),
            limitations=[],
        ), max(1, len(classes) + len(tests))
    if kind == "representation":
        allowed = {
            "action",
            "context",
            "features",
            "inputs",
            "kind",
            "representation_id",
            "readout",
        }
        binding_backed = "inputs" in query
        feature_backed = "features" in query
        if (
            set(query) - allowed
            or "representation_id" not in query
            or binding_backed == feature_backed
            or not isinstance(query.get("action", {}), Mapping)
            or not isinstance(query.get("context", {}), Mapping)
            or (feature_backed and not isinstance(query["features"], Mapping))
            or query.get("readout", "outcome") not in {"encoded", "outcome"}
        ):
            raise FieldIntelligenceError(
                "INVALID_QUERY", "representation query is invalid"
            )
        readout = query.get("readout", "outcome")
        representation_id = _identifier(
            query["representation_id"], "representation identity"
        )
        raw_ref = state["libraries"]["representations"].get(
            representation_id
        )
        if raw_ref is None:
            return _semantic_result(
                "query",
                "support-gap",
                answer=None,
                alternatives=[],
                limitations=["representation-unavailable"],
                representation=None,
            ), 1
        _, record = _semantic_reference(state, raw_ref, require_current=True)
        if (
            record["status"] != "active"
            or record["payload"].get("program_role")
            != "representation"
        ):
            return _semantic_result(
                "query",
                "support-gap",
                answer=None,
                alternatives=[],
                limitations=[
                    f"representation-{record['status']}"
                ],
                representation=raw_ref,
            ), 1
        source_refs: list[dict[str, Any]] = []
        input_metadata: dict[str, Any] = {}
        input_count = 0
        if binding_backed:
            input_count = len(query["inputs"])
            (
                features,
                source_refs,
                input_metadata,
                input_limitations,
            ) = _semantic_representation_binding_inputs(
                state, query["inputs"]
            )
            if input_limitations:
                return _semantic_result(
                    "query",
                    "support-gap",
                    answer=None,
                    alternatives=[],
                    limitations=input_limitations,
                    representation=raw_ref,
                    representation_output=None,
                ), max(1, input_count)
            execution_state = {
                "features": features,
                "input_metadata": input_metadata,
            }
        else:
            execution_state = {
                "features": _regional_plain(
                    dict(query["features"]),
                    "representation query features",
                )
            }
        program = record["payload"]["program"]
        if (
            readout == "encoded"
            and program["program_kind"] == "construction"
            and program["body"].get("schema")
            == SEMANTIC_REPRESENTATION_SCHEMA
        ):
            body = program["body"]
            transformed = apply_semantic_representation_edits(
                cast(Mapping[str, Any], execution_state["features"]),
                cast(Sequence[Mapping[str, Any]], body["edits"]),
                action=cast(Any, query.get("action", {})),
                context=cast(Any, query.get("context", {})),
            )
            encoded = {
                role: transformed["values"][role]
                for role in body["output_roles"]
                if role in transformed["values"]
            }
            complete = len(encoded) == len(body["output_roles"])
            execution = {
                "alternatives": [],
                "limitations": [
                    *transformed["limitations"],
                    *(
                        []
                        if complete
                        else ["representation-output-missing"]
                    ),
                ],
                "output": (
                    {
                        "encoded": encoded,
                        "information_boundary": body[
                            "information_boundary"
                        ],
                        "question": body["question"],
                        "readout": "encoded",
                        "transformed": transformed["values"],
                    }
                    if transformed["status"] == "supported" and complete
                    else None
                ),
                "status": (
                    "supported"
                    if transformed["status"] == "supported" and complete
                    else "support-gap"
                ),
                "values": execution_state,
                "work": max(
                    1,
                    int(transformed["work"]) + len(body["output_roles"]),
                ),
            }
        else:
            execution = execute_semantic_program(
                program,
                execution_state,
                action=cast(Any, query.get("action", {})),
                context=cast(Any, query.get("context", {})),
            )
        raw_output = execution.get("output")
        output: dict[str, Any] | None = None
        limitations = list(execution.get("limitations", []))
        if execution["status"] == "supported" and isinstance(
            raw_output, Mapping
        ):
            output = dict(raw_output)
            if binding_backed:
                output["input_metadata"] = input_metadata
                output["source_refs"] = source_refs
        elif (
            binding_backed
            and execution["status"] == "supported"
            and program["program_kind"] == "affine"
        ):
            raw_values = execution.get("values")
            raw_targets = program["body"].get("outputs")
            raw_uncertainty = execution.get("uncertainty")
            if (
                isinstance(raw_values, Mapping)
                and isinstance(raw_targets, Mapping)
                and isinstance(raw_uncertainty, Mapping)
            ):
                values = {
                    target: raw_values[target]
                    for target in sorted(raw_targets)
                    if target in raw_values
                }
                uncertainty: dict[str, list[float]] = {}
                propagated_radii: dict[str, float] = {}
                missing_precision: set[str] = set()
                for target in sorted(raw_targets):
                    expression = raw_targets[target]
                    bounds = raw_uncertainty.get(target)
                    if (
                        target not in values
                        or not isinstance(expression, Mapping)
                        or not isinstance(expression.get("terms"), Mapping)
                        or not isinstance(bounds, list)
                        or len(bounds) != 2
                    ):
                        continue
                    center = float(values[target])
                    radius = max(
                        abs(center - float(bounds[0])),
                        abs(float(bounds[1]) - center),
                    )
                    for source, coefficient in expression["terms"].items():
                        source_radius = propagated_radii.get(source, 0.0)
                        if source.startswith("features."):
                            role = source.split(".", 2)[1]
                            metadata = input_metadata.get(role)
                            if metadata is not None:
                                precision = metadata["precision"]
                                if precision is None:
                                    missing_precision.add(role)
                                    continue
                                source_radius = float(precision)
                        radius += abs(float(coefficient)) * source_radius
                    lower = center - radius
                    upper = center + radius
                    clamps = program["body"].get("clamp")
                    if isinstance(clamps, Mapping):
                        clamp = clamps.get(target)
                        if isinstance(clamp, list) and len(clamp) == 2:
                            lower = max(lower, float(clamp[0]))
                            upper = min(upper, float(clamp[1]))
                    uncertainty[target] = [lower, upper]
                    propagated_radii[target] = max(
                        abs(center - lower),
                        abs(upper - center),
                    )
                if missing_precision:
                    limitations.extend(
                        f"representation-precision-missing:{role}"
                        for role in sorted(missing_precision)
                    )
                elif (
                    len(values) == len(raw_targets)
                    and len(uncertainty) == len(raw_targets)
                ):
                    output = {
                        "input_metadata": input_metadata,
                        "source_refs": source_refs,
                        "uncertainty": uncertainty,
                        "uncertainty_semantics": (
                            "clamped-program-error-plus-absolute-affine-"
                            "input-precision"
                        ),
                        "values": values,
                    }
        if (
            execution["status"] == "supported"
            and output is None
            and not any(
                item.startswith("representation-precision-missing:")
                for item in limitations
            )
        ):
            limitations.append(
                f"representation-output-unavailable:{program['program_kind']}"
            )
        supported = execution["status"] == "supported" and output is not None
        answer: Any = None
        if output is not None:
            if readout == "encoded" and isinstance(
                output.get("encoded"), Mapping
            ):
                answer = output["encoded"]
            elif "outcome" in output:
                answer = output["outcome"]
            elif isinstance(output.get("values"), Mapping):
                values = output["values"]
                answer = values.get("outcome", values)
        return _semantic_result(
            "query",
            "supported" if supported else "support-gap",
            answer=answer,
            alternatives=[],
            limitations=sorted(set(limitations)),
            representation=raw_ref,
            readout=readout,
            representation_output=output if supported else None,
        ), max(
            1,
            int(execution["work"]) + input_count,
        )
    if kind == "timeline":
        if set(query) - {"end", "kind", "start"}:
            raise FieldIntelligenceError(
                "INVALID_QUERY", "timeline query keys are invalid"
            )
        start = (
            -1.0e308
            if "start" not in query
            else _finite(query["start"], "timeline start")
        )
        end = (
            1.0e308
            if "end" not in query
            else _finite(query["end"], "timeline end")
        )
        rows = [
            item
            for item in state["time"]["timeline"]
            if float(item["time"]["end"]) >= start
            and float(item["time"]["start"]) <= end
        ]
        return _semantic_result(
            "query",
            "supported" if rows else "support-gap",
            events=rows,
            limitations=[] if rows else ["interval-unobserved"],
        ), max(1, len(rows))
    if kind == "explain":
        if set(query) != {"kind", "reference"} or not isinstance(
            query["reference"], Mapping
        ):
            raise FieldIntelligenceError(
                "INVALID_QUERY", "explanation query keys are invalid"
            )
        allowed = request.get("allowed_support_roots")
        if allowed is not None and (
            not isinstance(allowed, list)
            or any(not isinstance(item, str) for item in allowed)
        ):
            raise FieldIntelligenceError(
                "INVALID_QUERY", "allowed support roots are invalid"
            )
        status, explanation = _semantic_explanation(
            state, query["reference"], cast(Any, allowed)
        )
        return _semantic_result(
            "query", status, explanation=explanation
        ), max(1, len(explanation["nodes"]))
    if kind == "library":
        if set(query) != {"kind", "library"}:
            raise FieldIntelligenceError(
                "INVALID_QUERY", "library query keys are invalid"
            )
        library = query["library"]
        if library not in state["libraries"]:
            raise FieldIntelligenceError(
                "INVALID_QUERY", "semantic library is unknown"
            )
        return _semantic_result(
            "query",
            "supported",
            entries=state["libraries"][library],
            limitations=[],
        ), max(1, len(state["libraries"][library]))
    if kind == "causal":
        return _semantic_causal_query(
            cast(dict[str, Any], state), request, query
        )
    raise FieldIntelligenceError(
        "INVALID_QUERY", f"unsupported semantic query kind: {kind}"
    )
def _semantic_explain(
    state: Mapping[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("reference",),
        optional=("allowed_support_roots",),
    )
    if not isinstance(request["reference"], Mapping):
        raise FieldIntelligenceError(
            "INVALID_QUERY", "explanation reference must be typed"
        )
    allowed = request.get("allowed_support_roots")
    if allowed is not None and (
        not isinstance(allowed, list)
        or any(not isinstance(item, str) for item in allowed)
    ):
        raise FieldIntelligenceError(
            "INVALID_QUERY", "allowed support roots are invalid"
        )
    status, explanation = _semantic_explanation(
        state, request["reference"], cast(Any, allowed)
    )
    return _semantic_result(
        "explain", status, explanation=explanation
    ), max(1, len(explanation["nodes"]))


def _semantic_state_alternatives(
    state: Mapping[str, Any],
    request: Mapping[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
    str,
]:
    explicit = request.get("state", {})
    if not isinstance(explicit, Mapping):
        raise FieldIntelligenceError(
            "INVALID_PREDICTION", "prediction state must be a mapping"
        )
    assignments = [
        {"state": _regional_plain(dict(explicit), "prediction state")}
    ]
    belief_semantics = "deterministic"
    dependencies: list[dict[str, Any]] = []
    binding_ids: list[str] = []

    def compose_source(
        rows: Sequence[Mapping[str, Any]],
        source_semantics: str,
        source_id: str,
    ) -> None:
        nonlocal assignments, belief_semantics
        effective_source = (
            "deterministic"
            if source_semantics == "constraint-set" and len(rows) == 1
            else source_semantics
        )
        if belief_semantics == "deterministic":
            combined_semantics = effective_source
        elif effective_source == "deterministic":
            combined_semantics = belief_semantics
        elif belief_semantics == effective_source == "probability":
            combined_semantics = "probability"
        elif belief_semantics == effective_source == "constraint-set":
            combined_semantics = "constraint-set"
        else:
            combined_semantics = "model-family"
        expanded: list[dict[str, Any]] = []
        for assignment in assignments:
            for row_index, row in enumerate(rows):
                branch: dict[str, Any] = {
                    "state": {
                        **assignment["state"],
                        **cast(Mapping[str, Any], row["state_delta"]),
                    }
                }
                if combined_semantics == "probability":
                    branch["weight"] = float(
                        assignment.get("weight", 1.0)
                    ) * float(row.get("weight", 1.0))
                elif combined_semantics == "constraint-set":
                    branch["set_path"] = [
                        *cast(
                            list[dict[str, Any]],
                            assignment.get("set_path", []),
                        ),
                        {
                            "alternative_index": row_index,
                            "source": source_id,
                        },
                    ]
                elif combined_semantics == "model-family":
                    model_path = [
                        *cast(
                            list[dict[str, Any]],
                            assignment.get("model_path", []),
                        ),
                        *cast(
                            list[dict[str, Any]],
                            assignment.get("set_path", []),
                        ),
                    ]
                    if effective_source == "model-family":
                        model_path.append(
                            {
                                "model_ids": [row["model"]],
                                "source": source_id,
                            }
                        )
                    elif effective_source == "constraint-set":
                        model_path.append(
                            {
                                "alternative_index": row_index,
                                "source": source_id,
                            }
                        )
                    branch["model_path"] = model_path
                    probability_factor: float | None = None
                    if "conditional_weight" in assignment:
                        probability_factor = float(
                            assignment["conditional_weight"]
                        )
                    elif belief_semantics == "probability":
                        probability_factor = float(
                            assignment.get("weight", 1.0)
                        )
                    if effective_source == "probability":
                        probability_factor = (
                            1.0
                            if probability_factor is None
                            else probability_factor
                        ) * float(row["weight"])
                    if probability_factor is not None:
                        branch["conditional_weight"] = probability_factor
                expanded.append(branch)
        assignments = expanded
        belief_semantics = combined_semantics

    joint_id = request.get("joint_id")
    if joint_id is not None:
        normalized_joint = _identifier(joint_id, "joint belief identity")
        raw_ref = state["beliefs"]["joint"].get(normalized_joint)
        if raw_ref is None:
            raise FieldIntelligenceError(
                "UNKNOWN_SEMANTIC_RECORD",
                "prediction joint belief is unavailable",
            )
        _, joint = _semantic_reference(state, raw_ref, require_current=True)
        if joint["status"] != "active":
            raise FieldIntelligenceError(
                "PREDICTION_SUPPORT_GAP",
                f"joint belief {normalized_joint} is not active",
            )
        dependencies.append(raw_ref)
        joint_semantics = str(
            joint["payload"].get("belief_semantics", "")
        )
        if joint_semantics not in {
            "constraint-set",
            "model-family",
            "probability",
        }:
            raise FieldIntelligenceError(
                "INVALID_BELIEF",
                "joint belief has no valid uncertainty semantics",
            )
        joint_rows = []
        for raw_alternative in joint["payload"]["alternatives"]:
            row: dict[str, Any] = {
                "state_delta": dict(raw_alternative["assignment"])
            }
            if joint_semantics == "probability":
                row["weight"] = float(raw_alternative["weight"])
            elif joint_semantics == "model-family":
                row["model"] = raw_alternative["model"]
            joint_rows.append(row)
        compose_source(
            joint_rows, joint_semantics, f"joint:{normalized_joint}"
        )
    bindings = request.get("bindings", {})
    if isinstance(bindings, list):
        bindings = {item: item for item in bindings}
    if not isinstance(bindings, Mapping) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in bindings.items()
    ):
        raise FieldIntelligenceError(
            "INVALID_PREDICTION", "prediction bindings are invalid"
        )
    for alias, binding_id in sorted(bindings.items()):
        record = _semantic_current_record(state, "Binding", binding_id)
        reference = semantic_record_ref(record).as_dict()
        dependencies.append(reference)
        binding_ids.append(binding_id)
        if record["status"] != "active":
            raise FieldIntelligenceError(
                "PREDICTION_SUPPORT_GAP",
                f"binding {binding_id} is not currently observed",
            )
        alternatives = record["payload"].get("alternatives", [])
        if alternatives:
            binding_semantics = record["payload"].get("belief_semantics")
            if binding_semantics not in {
                "constraint-set",
                "model-family",
                "probability",
            }:
                raise FieldIntelligenceError(
                    "INVALID_BELIEF",
                    "binding alternatives lack explicit uncertainty semantics",
                )
            binding_rows: list[dict[str, Any]] = []
            total_weight = 0.0
            for raw in alternatives:
                if not isinstance(raw, Mapping) or "value" not in raw:
                    raise FieldIntelligenceError(
                        "INVALID_BELIEF",
                        "binding alternative is invalid",
                    )
                expected = (
                    {"value", "weight"}
                    if binding_semantics == "probability"
                    else {"model", "value"}
                    if binding_semantics == "model-family"
                    else {"value"}
                )
                if set(raw) != expected:
                    raise FieldIntelligenceError(
                        "INVALID_BELIEF",
                        "binding alternative does not match its semantics",
                    )
                row = {"state_delta": {alias: raw["value"]}}
                if binding_semantics == "probability":
                    weight = _finite(
                        raw["weight"], "binding alternative weight"
                    )
                    if weight <= 0.0:
                        raise FieldIntelligenceError(
                            "INVALID_BELIEF",
                            "binding alternative weight must be positive",
                        )
                    row["weight"] = weight
                    total_weight += weight
                elif binding_semantics == "model-family":
                    row["model"] = _identifier(
                        raw["model"], "binding alternative model"
                    )
                binding_rows.append(row)
            binding_rows.sort(
                key=lambda item: canonical_json_bytes(item)
            )
            if binding_semantics == "probability":
                for row in binding_rows:
                    row["weight"] = float(row["weight"]) / total_weight
            compose_source(
                binding_rows,
                str(binding_semantics),
                f"binding:{binding_id}",
            )
        else:
            for assignment in assignments:
                assignment["state"][alias] = record["payload"].get("value")
        if len(assignments) > state["bounds"]["max_alternatives"]:
            raise FieldIntelligenceError(
                "WORK_CAPACITY",
                "prediction alternatives exceed their declared bound",
            )
    if not assignments:
        raise FieldIntelligenceError(
            "INVALID_BELIEF", "prediction alternative set is empty"
        )
    if belief_semantics == "probability":
        total = sum(float(item["weight"]) for item in assignments)
        if total <= 0.0:
            raise FieldIntelligenceError(
                "INVALID_BELIEF", "prediction alternative mass is empty"
            )
        for item in assignments:
            item["weight"] = float(item["weight"]) / total
    dependencies.sort(
        key=lambda item: (
            item["kind"],
            item["id"],
            int(item["content_version"]),
        )
    )
    return (
        assignments,
        dependencies,
        sorted(set(binding_ids)),
        (
            "constraint-set"
            if belief_semantics == "deterministic"
            else belief_semantics
        ),
    )


def _semantic_program_record(
    state: Mapping[str, Any], mechanism_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    record = _semantic_current_record(state, "Program", mechanism_id)
    if record["status"] != "active":
        raise FieldIntelligenceError(
            "PREDICTION_SUPPORT_GAP", "mechanism is not active"
        )
    raw_program = record["payload"].get("program", record["payload"])
    try:
        program = _canonical_mechanism_program(raw_program)
    except ValueError as exc:
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_PROGRAM",
            "program record has no executable semantic payload",
        ) from exc
    return record, program

def _semantic_mechanism_coverage(
    mechanism: Mapping[str, Any],
    program: Mapping[str, Any],
    *,
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    interval: Mapping[str, Any],
    horizon: int,
) -> list[str]:
    coverage = mechanism["payload"].get("coverage", [])
    if not isinstance(coverage, list):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_PROGRAM",
            "mechanism coverage is not a bounded row set",
        )
    for raw_row in coverage:
        if (
            isinstance(raw_row, Mapping)
            and raw_row.get("outcome_status") == "observed-and-scored"
            and raw_row.get("action") == action
            and raw_row.get("context") == context
            and raw_row.get("interval") == interval
            and horizon == 1
        ):
            return []
    applicability = program.get("applicability", {})
    if not isinstance(applicability, Mapping):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_PROGRAM",
            "mechanism applicability is not a mapping",
        )

    def permits(name: str, value: Mapping[str, Any]) -> bool:
        domain = applicability.get(name)
        return domain == "any" or (
            isinstance(domain, list)
            and any(item == value for item in domain)
        )

    limitations: list[str] = []
    if not permits("action_domain", action):
        limitations.append("unseen-action")
    if not permits("context_domain", context):
        limitations.append("unseen-context")
    if not permits("interval_domain", interval):
        limitations.append("unseen-duration-or-interval")
    supported_horizon = applicability.get("max_supported_horizon")
    if (
        isinstance(supported_horizon, bool)
        or not isinstance(supported_horizon, int)
        or horizon > supported_horizon
    ):
        limitations.append("unsupported-horizon")
    return limitations


def _semantic_merge_predictions(
    alternatives: Sequence[Mapping[str, Any]],
    maximum: int,
    *,
    semantics: str,
) -> list[dict[str, Any]]:
    if semantics not in {
        "constraint-set",
        "model-family",
        "probability",
    }:
        raise FieldIntelligenceError(
            "INVALID_BELIEF", "prediction semantics are invalid"
        )
    merged: dict[bytes, dict[str, Any]] = {}
    for raw in alternatives:
        values = _regional_plain(raw["values"], "predicted values")
        identity: dict[str, Any] = {"values": values}
        if semantics == "constraint-set":
            identity["set_path"] = raw.get("set_path", [])
        elif semantics == "model-family":
            identity["model_path"] = raw.get("model_path", [])
        key = canonical_json_bytes(identity)
        if key not in merged:
            merged[key] = {
                **identity,
                "uncertainty": _regional_plain(
                    raw.get("uncertainty", {}),
                    "predicted uncertainty",
                ),
            }
            if semantics == "probability":
                merged[key]["weight"] = 0.0
            elif semantics == "model-family":
                merged[key]["conditional_weight"] = 0.0
                merged[key]["conditional_weight_known"] = True
        branch = merged[key]
        if semantics == "probability":
            if "weight" not in raw:
                raise FieldIntelligenceError(
                    "INVALID_BELIEF",
                    "probability prediction branch lacks mass",
                )
            branch["weight"] += float(raw["weight"])
        elif semantics == "model-family":
            if "conditional_weight" in raw:
                branch["conditional_weight"] += float(
                    raw["conditional_weight"]
                )
            else:
                branch["conditional_weight_known"] = False
        incoming_uncertainty = raw.get("uncertainty", {})
        if isinstance(incoming_uncertainty, Mapping):
            for name, raw_bounds in incoming_uncertainty.items():
                prior_bounds = branch["uncertainty"].get(name)
                if (
                    isinstance(raw_bounds, list)
                    and len(raw_bounds) == 2
                    and isinstance(prior_bounds, list)
                    and len(prior_bounds) == 2
                    and all(
                        isinstance(item, (int, float))
                        and not isinstance(item, bool)
                        for item in (*raw_bounds, *prior_bounds)
                    )
                ):
                    branch["uncertainty"][name] = [
                        min(float(prior_bounds[0]), float(raw_bounds[0])),
                        max(float(prior_bounds[1]), float(raw_bounds[1])),
                    ]
    if len(merged) > maximum:
        raise FieldIntelligenceError(
            "WORK_CAPACITY",
            "prediction branch count exceeds its declared bound",
        )
    result = [merged[key] for key in sorted(merged)]
    if semantics == "probability":
        total = sum(float(item["weight"]) for item in result)
        if total <= 0.0:
            raise FieldIntelligenceError(
                "INVALID_BELIEF", "prediction probability mass is empty"
            )
        for item in result:
            item["weight"] = float(item["weight"]) / total
    elif semantics == "model-family":
        groups: dict[bytes, list[dict[str, Any]]] = {}
        for item in result:
            model_key = canonical_json_bytes(item.get("model_path", []))
            groups.setdefault(model_key, []).append(item)
        for group in groups.values():
            known = all(
                bool(item.pop("conditional_weight_known", False))
                for item in group
            )
            total = sum(
                float(item.get("conditional_weight", 0.0))
                for item in group
            )
            if known and total > 0.0:
                for item in group:
                    item["conditional_weight"] = (
                        float(item["conditional_weight"]) / total
                    )
            else:
                for item in group:
                    item.pop("conditional_weight", None)
    return result


def _semantic_predict(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("mechanism_id", "prediction_id"),
        optional=(
            "action",
            "actions",
            "bindings",
            "collection_policy",
            "context",
            "horizon",
            "dependencies",
            "interval",
            "joint_id",
            "state",
            "missingness",
            "query_kind",
            "time",
            "support_roots",
            "target",
            "units",
        ),
    )
    prediction_id = _identifier(
        request["prediction_id"], "prediction identity"
    )
    if prediction_id in state["current"]["Assessment"]:
        raise FieldIntelligenceError(
            "OPERATION_CONFLICT", "prediction identity already exists"
        )
    mechanism_id = _identifier(
        request["mechanism_id"], "mechanism identity"
    )
    mechanism_record = _semantic_current_record(
        state, "Program", mechanism_id
    )
    if mechanism_record["status"] != "active":
        mechanism_reference = semantic_record_ref(mechanism_record).as_dict()
        inadequacy_ref = None
        for raw_ref in state["current"]["Obligation"].values():
            _, obligation = _semantic_reference(
                state, raw_ref, require_current=True
            )
            if obligation["payload"].get("candidate") == mechanism_reference:
                inadequacy_ref = SemanticRef.from_dict(raw_ref).as_dict()
                break
        reason = mechanism_record["payload"].get(
            "inadequacy_reason",
            "representation-insufficient",
        )
        return _semantic_result(
            "predict",
            "representation-insufficient",
            model_inadequacy=inadequacy_ref,
            prediction=None,
            limitations=sorted(
                {
                    "model-inadequacy",
                    "representation-insufficient",
                    str(reason),
                }
            ),
        ), 1
    mechanism, program = _semantic_program_record(state, mechanism_id)
    raw_observation_program = mechanism["payload"].get("observation_model")
    observation_program = (
        None
        if raw_observation_program is None
        else _canonical_mechanism_program(
            cast(Mapping[str, Any], raw_observation_program)
        )
    )
    mechanism_variants: list[
        tuple[str, dict[str, Any], dict[str, Any] | None]
    ] = [
        (
            str(mechanism["payload"].get("selected_candidate", "selected")),
            program,
            observation_program,
        )
    ]
    if mechanism["payload"].get("selection_ambiguity") is True:
        raw_ambiguous_ids = mechanism["payload"].get(
            "indistinguishable_candidates", []
        )
        raw_candidate_family = mechanism["payload"].get(
            "candidate_family", []
        )
        if isinstance(raw_ambiguous_ids, list) and isinstance(
            raw_candidate_family, list
        ):
            ambiguous_ids = {str(item) for item in raw_ambiguous_ids}
            variants: list[
                tuple[str, dict[str, Any], dict[str, Any] | None]
            ] = []
            for raw_candidate_ref in raw_candidate_family:
                if not isinstance(raw_candidate_ref, Mapping):
                    continue
                _, candidate_record = _semantic_reference(
                    state, raw_candidate_ref, require_current=True
                )
                candidate_id = str(
                    candidate_record["payload"].get(
                        "candidate_id", raw_candidate_ref.get("id")
                    )
                )
                if candidate_id not in ambiguous_ids:
                    continue
                candidate_program = _canonical_mechanism_program(
                    cast(
                        Mapping[str, Any],
                        candidate_record["payload"]["program"],
                    )
                )
                raw_candidate_observation = candidate_record["payload"].get(
                    "observation_model"
                )
                candidate_observation = (
                    None
                    if raw_candidate_observation is None
                    else _canonical_mechanism_program(
                        cast(Mapping[str, Any], raw_candidate_observation)
                    )
                )
                variants.append(
                    (candidate_id, candidate_program, candidate_observation)
                )
            if variants:
                mechanism_variants = variants
    raw_mechanism_probability_model = mechanism["payload"].get(
        "probability_model",
        (
            mechanism["payload"].get("signature", {}).get(
                "probability_model"
            )
            if isinstance(mechanism["payload"].get("signature"), Mapping)
            else None
        ),
    )
    mechanism_probability_model = (
        None
        if raw_mechanism_probability_model is None
        else _semantic_probability_model(
            raw_mechanism_probability_model,
            "prediction mechanism probability model",
        )
    )
    horizon = _regional_integer(
        request.get("horizon", 1),
        "prediction horizon",
        minimum=1,
        maximum=1_000_000,
    )
    if horizon > int(program["bounds"]["max_horizon"]):
        return _semantic_result(
            "predict",
            "resource-exhausted",
            prediction=None,
            limitations=["program-horizon-bound"],
        ), 1
    actions = request.get("actions")
    if actions is None:
        actions = [request.get("action", {})] * horizon
    if (
        not isinstance(actions, list)
        or len(actions) != horizon
        or any(not isinstance(item, Mapping) for item in actions)
    ):
        raise FieldIntelligenceError(
            "INVALID_PREDICTION",
            "prediction actions must match the requested horizon",
        )
    context = request.get("context", {})
    interval = request.get("interval", {})
    if not isinstance(context, Mapping) or not isinstance(interval, Mapping):
        raise FieldIntelligenceError(
            "INVALID_PREDICTION", "prediction context or interval is invalid"
        )
    collection_policy = request.get("collection_policy", {})
    missingness = request.get("missingness", {})
    if not isinstance(collection_policy, Mapping) or not isinstance(
        missingness, Mapping
    ):
        raise FieldIntelligenceError(
            "INVALID_PREDICTION",
            "prediction collection policy and missingness must be mappings",
        )
    query_kind = _identifier(
        request.get("query_kind", "prediction"), "prediction query kind"
    )
    if query_kind not in {
        "intervention",
        "observation-conditioning",
        "planning-rollout",
        "prediction",
        "unit-counterfactual",
    }:
        raise FieldIntelligenceError(
            "INVALID_PREDICTION", "prediction query kind is unsupported"
        )
    raw_extra_dependencies = request.get("dependencies", [])
    if not isinstance(raw_extra_dependencies, list):
        raise FieldIntelligenceError(
            "INVALID_PREDICTION", "prediction dependencies must be a list"
        )
    extra_dependencies: list[dict[str, Any]] = []
    dependency_support_roots: set[str] = set(mechanism["support_roots"])
    for raw_dependency in raw_extra_dependencies:
        if not isinstance(raw_dependency, Mapping):
            raise FieldIntelligenceError(
                "INVALID_PREDICTION",
                "prediction dependencies must be typed references",
            )
        dependency_ref, dependency_record = _semantic_reference(
            state, raw_dependency, require_current=True
        )
        extra_dependencies.append(dependency_ref.as_dict())
        dependency_support_roots.update(dependency_record["support_roots"])
    raw_support_roots = request.get("support_roots", [])
    if (
        not isinstance(raw_support_roots, list)
        or any(
            not isinstance(item, str) or not item
            for item in raw_support_roots
        )
    ):
        raise FieldIntelligenceError(
            "INVALID_PREDICTION", "prediction support roots are invalid"
        )
    dependency_support_roots.update(raw_support_roots)
    coverage_limitations = sorted(
        {
            limitation
            for action in actions
            for limitation in _semantic_mechanism_coverage(
                mechanism,
                program,
                action=cast(Mapping[str, Any], action),
                context=cast(Mapping[str, Any], context),
                interval=cast(Mapping[str, Any], interval),
                horizon=horizon,
            )
        }
    )
    if coverage_limitations:
        return _semantic_result(
            "predict",
            "support-gap",
            prediction=None,
            limitations=coverage_limitations,
        ), max(1, len(actions))
    try:
        (
            alternatives,
            dependencies,
            binding_ids,
            prediction_semantics,
        ) = _semantic_state_alternatives(state, request)
    except FieldIntelligenceError as exc:
        if exc.code != "PREDICTION_SUPPORT_GAP":
            raise
        return _semantic_result(
            "predict",
            "support-gap",
            prediction=None,
            limitations=[str(exc)],
        ), 1
    probability_models: list[dict[str, Any]] = []
    if mechanism_probability_model is not None:
        probability_models.append(
            {
                "model": mechanism_probability_model,
                "source": semantic_record_ref(mechanism).as_dict(),
            }
        )
    for dependency in dependencies:
        _, dependency_record = _semantic_reference(
            state, dependency, require_current=True
        )
        dependency_support_roots.update(
            dependency_record["support_roots"]
        )
        dependency_probability_model = dependency_record["payload"].get(
            "probability_model"
        )
        if dependency_probability_model is not None:
            probability_models.append(
                {
                    "model": _semantic_probability_model(
                        dependency_probability_model,
                        "prediction dependency probability model",
                    ),
                    "source": dependency,
                }
            )
    work = len(extra_dependencies) + len(dependencies)
    limitations: list[str] = []

    def combine_semantics(left: str, right: str) -> str:
        if left == "deterministic":
            return right
        if right == "deterministic":
            return left
        if left == right and left in {"constraint-set", "probability"}:
            return left
        return "model-family"

    def outcome_branches(
        outcome: Mapping[str, Any],
        source: str,
    ) -> tuple[list[dict[str, Any]], str]:
        limitations.extend(outcome.get("limitations", []))
        declared_semantics = outcome.get(
            "uncertainty_semantics", "deterministic"
        )
        if declared_semantics not in {
            "constraint-set",
            "deterministic",
            "model-family",
            "probability",
        }:
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_PROGRAM",
                "mechanism uncertainty semantics are invalid",
            )
        if outcome["status"] == "supported":
            if (
                declared_semantics == "probability"
                and mechanism_probability_model is None
            ):
                raise FieldIntelligenceError(
                    "INVALID_PROBABILITY_MODEL",
                    "probabilistic mechanism output has no named model",
                )
            row: dict[str, Any] = {
                "uncertainty": outcome.get("uncertainty", {}),
                "values": outcome["values"],
            }
            if declared_semantics == "probability":
                row["weight"] = 1.0
            elif declared_semantics == "constraint-set":
                row["set_path"] = [
                    {"alternative_index": 0, "source": source}
                ]
            elif declared_semantics == "model-family":
                row["model_path"] = [
                    {"alternative_index": 0, "source": source}
                ]
            return [row], declared_semantics
        if outcome["status"] != "alternatives":
            return [], "deterministic"
        branches = outcome["alternatives"]
        if not isinstance(branches, list):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_PROGRAM",
                "mechanism alternatives are not a bounded row set",
            )
        raw_weights = outcome.get("alternative_weights")
        if raw_weights is not None:
            if (
                not isinstance(raw_weights, list)
                or len(raw_weights) != len(branches)
                or any(
                    isinstance(item, bool)
                    or not isinstance(item, (int, float))
                    or float(item) < 0.0
                    for item in raw_weights
                )
                or abs(sum(float(item) for item in raw_weights) - 1.0)
                > 1.0e-9
            ):
                raise FieldIntelligenceError(
                    "INVALID_MECHANISM_PROGRAM",
                    "mechanism alternative probability is invalid",
                )
            branch_semantics = "probability"
            if mechanism_probability_model is None:
                raise FieldIntelligenceError(
                    "INVALID_PROBABILITY_MODEL",
                    "weighted mechanism output has no named probability model",
                )
        else:
            raw_details = outcome.get("alternative_details")
            branch_semantics = (
                "model-family"
                if isinstance(raw_details, list)
                and len(raw_details) == len(branches)
                else "constraint-set"
            )
            limitations.append("unweighted-alternatives")
        raw_uncertainties = outcome.get("alternative_uncertainties")
        has_uncertainties = (
            isinstance(raw_uncertainties, list)
            and len(raw_uncertainties) == len(branches)
            and all(isinstance(item, Mapping) for item in raw_uncertainties)
        )
        result: list[dict[str, Any]] = []
        for index, branch_values in enumerate(branches):
            row: dict[str, Any] = {
                "uncertainty": (
                    cast(list[Any], raw_uncertainties)[index]
                    if has_uncertainties
                    else outcome.get("uncertainty", {})
                ),
                "values": branch_values,
            }
            if branch_semantics == "probability":
                row["weight"] = float(cast(list[Any], raw_weights)[index])
            elif branch_semantics == "model-family":
                details = cast(list[Any], outcome["alternative_details"])[
                    index
                ]
                row["model_path"] = [
                    {
                        "alternative_index": index,
                        "model_ids": sorted(
                            str(item)
                            for item in (
                                details.get("modes", [])
                                if isinstance(details, Mapping)
                                else []
                            )
                        ),
                        "source": source,
                    }
                ]
            else:
                row["set_path"] = [
                    {
                        "alternative_index": index,
                        "source": source,
                    }
                ]
            result.append(row)
        return result, branch_semantics

    for step in range(horizon):
        staged: list[dict[str, Any]] = []
        encountered_semantics: list[str] = []
        for alternative in alternatives:
            bound_candidate = alternative.get("_mechanism_candidate")
            candidate_rows = (
                mechanism_variants
                if bound_candidate is None
                else [
                    item
                    for item in mechanism_variants
                    if item[0] == str(bound_candidate)
                ]
            )
            for candidate_id, candidate_program, candidate_observation in (
                candidate_rows
            ):
                try:
                    outcome = execute_semantic_program(
                        candidate_program,
                        alternative["state"],
                        action=cast(Mapping[str, Any], actions[step]),
                        context=cast(Mapping[str, Any], context),
                        interval=cast(Mapping[str, Any], interval),
                    )
                    work += max(1, int(outcome["work"]))
                    transition_branches, transition_semantics = (
                        outcome_branches(
                            outcome,
                            f"transition:{step}:{candidate_id}",
                        )
                    )
                    encountered_semantics.append(transition_semantics)
                    for transition_branch in transition_branches:
                        observation_branches = [
                            {
                                "uncertainty": {},
                                "values": transition_branch["values"],
                            }
                        ]
                        observation_semantics = "deterministic"
                        if candidate_observation is not None:
                            observation = execute_semantic_program(
                                candidate_observation,
                                transition_branch["values"],
                                action=cast(
                                    Mapping[str, Any], actions[step]
                                ),
                                context=cast(
                                    Mapping[str, Any], context
                                ),
                                interval=cast(
                                    Mapping[str, Any], interval
                                ),
                            )
                            work += max(1, int(observation["work"]))
                            (
                                observation_branches,
                                observation_semantics,
                            ) = outcome_branches(
                                observation,
                                f"observation:{step}:{candidate_id}",
                            )
                            encountered_semantics.append(observation_semantics)
                        for observed_branch in observation_branches:
                            staged.append(
                                {
                                    "base": alternative,
                                    "mechanism_candidate": candidate_id,
                                    "observation": observed_branch,
                                    "observation_semantics": (
                                        observation_semantics
                                    ),
                                    "transition": transition_branch,
                                    "transition_semantics": (
                                        transition_semantics
                                    ),
                                }
                            )
                except (RegionalFieldError, TypeError, ValueError):
                    return _semantic_result(
                        "predict",
                        "support-gap",
                        prediction=None,
                        limitations=["mechanism-execution-invalid"],
                    ), max(1, work)
        if not staged:
            return _semantic_result(
                "predict",
                "support-gap",
                prediction=None,
                limitations=sorted(set(limitations or ["transition-uncovered"])),
            ), max(1, work)
        next_semantics = prediction_semantics
        if next_semantics == "constraint-set" and len(alternatives) == 1:
            next_semantics = "deterministic"
        for encountered in encountered_semantics:
            next_semantics = combine_semantics(
                next_semantics, encountered
            )
        if next_semantics == "deterministic":
            next_semantics = "constraint-set"
        successors: list[dict[str, Any]] = []
        for row in staged:
            base = cast(Mapping[str, Any], row["base"])
            transition = cast(Mapping[str, Any], row["transition"])
            observation = cast(Mapping[str, Any], row["observation"])
            successor: dict[str, Any] = {
                "values": observation["values"],
                "uncertainty": {
                    **dict(transition["uncertainty"]),
                    **dict(observation["uncertainty"]),
                },
            }
            probability_factor = 1.0
            has_probability = False
            if prediction_semantics == "probability":
                probability_factor *= float(base["weight"])
                has_probability = True
            elif (
                prediction_semantics == "model-family"
                and "conditional_weight" in base
            ):
                probability_factor *= float(base["conditional_weight"])
                has_probability = True
            for branch, branch_semantics in (
                (transition, row["transition_semantics"]),
                (observation, row["observation_semantics"]),
            ):
                if branch_semantics == "probability":
                    probability_factor *= float(branch["weight"])
                    has_probability = True
            if next_semantics == "probability":
                successor["weight"] = probability_factor
            elif next_semantics == "constraint-set":
                successor["set_path"] = [
                    *cast(list[Any], base.get("set_path", [])),
                    *cast(list[Any], transition.get("set_path", [])),
                    *cast(list[Any], observation.get("set_path", [])),
                ]
            else:
                successor["model_path"] = [
                    *cast(list[Any], base.get("model_path", [])),
                    *cast(list[Any], base.get("set_path", [])),
                    *cast(list[Any], transition.get("model_path", [])),
                    *cast(list[Any], transition.get("set_path", [])),
                    *cast(list[Any], observation.get("model_path", [])),
                    *cast(list[Any], observation.get("set_path", [])),
                ]
                if has_probability:
                    successor["conditional_weight"] = probability_factor
            successors.append(successor)
        merged = _semantic_merge_predictions(
            successors,
            state["bounds"]["max_alternatives"],
            semantics=next_semantics,
        )
        alternatives = [
            {
                "state": item["values"],
                "uncertainty": item["uncertainty"],
                **(
                    {"weight": item["weight"]}
                    if "weight" in item
                    else {}
                ),
                **(
                    {"set_path": item["set_path"]}
                    if "set_path" in item
                    else {}
                ),
                **(
                    {"model_path": item["model_path"]}
                    if "model_path" in item
                    else {}
                ),
                **(
                    {"conditional_weight": item["conditional_weight"]}
                    if "conditional_weight" in item
                    else {}
                ),
            }
            for item in merged
        ]
        prediction_semantics = next_semantics
        if work > state["bounds"]["max_work"]:
            return _semantic_result(
                "predict",
                "resource-exhausted",
                prediction=None,
                limitations=["semantic-work-bound"],
            ), state["bounds"]["max_work"]
    predicted = []
    for item in alternatives:
        prediction_row: dict[str, Any] = {
            "values": item["state"],
            "uncertainty": item.get("uncertainty", {}),
        }
        if prediction_semantics == "probability":
            prediction_row["weight"] = item["weight"]
        elif prediction_semantics == "constraint-set":
            prediction_row["alternative_path"] = item.get("set_path", [])
        else:
            prediction_row["model_path"] = item.get("model_path", [])
            if "conditional_weight" in item:
                prediction_row["conditional_weight"] = item[
                    "conditional_weight"
                ]
        predicted.append(prediction_row)
    if prediction_semantics == "probability" and not probability_models:
        raise FieldIntelligenceError(
            "INVALID_PROBABILITY_MODEL",
            "probability prediction has no named probability source",
        )
    valid_time = _semantic_interval(
        cast(Any, request.get("time")),
        default=float(state["time"]["now"]) + float(horizon),
    )
    all_dependencies = {
        (
            item["kind"],
            item["id"],
            int(item["content_version"]),
        ): item
        for item in (*dependencies, *extra_dependencies)
    }
    belief_boundary = [
        all_dependencies[key] for key in sorted(all_dependencies)
    ]
    mechanism_ref = semantic_record_ref(mechanism).as_dict()
    prediction_ref = _semantic_append_record(
        state,
        record_id=prediction_id,
        kind="Assessment",
        payload={
            "action_sequence": [
                _regional_plain(dict(item), "prediction action")
                for item in actions
            ],
            "alternatives": predicted,
            "family_adequacy": "not-established",
            "belief_boundary": belief_boundary,
            "binding_ids": binding_ids,
            "collection_policy": _regional_plain(
                dict(collection_policy), "prediction collection policy"
            ),
            "context": _regional_plain(
                dict(context), "prediction context"
            ),
            "horizon": horizon,
            "interval": _regional_plain(
                dict(interval), "prediction interval"
            ),
            "issued_at": float(state["time"]["now"]),
            "limitations": sorted(set(limitations)),
            "mechanism": mechanism_ref,
            "missingness": _regional_plain(
                dict(missingness), "prediction missingness"
            ),
            "purpose": "prediction",
            "prediction_semantics": prediction_semantics,
            "probability_models": probability_models,
            "query_kind": query_kind,
            "target": _regional_plain(
                request.get("target"), "prediction target"
            ),
            "units": _regional_plain(
                request.get("units"), "prediction units"
            ),
        },
        epistemic_kind="predicted",
        dependencies=(mechanism_ref, *belief_boundary),
        support_roots=sorted(dependency_support_roots),
        valid_time=valid_time,
        applicability=mechanism["applicability"],
        units=request.get("units"),
    )
    _semantic_reindex_record(state, prediction_ref)
    status = "alternatives" if len(predicted) > 1 else "supported"
    return _semantic_result(
        "predict",
        status,
        prediction=prediction_ref,
        alternatives=predicted,
        prediction_semantics=prediction_semantics,
        probability_models=probability_models,
        limitations=sorted(set(limitations)),
    ), max(1, work + 1)


def _semantic_causal_query(
    state: dict[str, Any],
    request: Mapping[str, Any],
    query: Mapping[str, Any],
) -> tuple[dict[str, Any], int]:
    common_keys = {
        "bindings",
        "collection_policy",
        "context",
        "dependencies",
        "horizon",
        "interval",
        "kind",
        "mechanism_id",
        "meaning",
        "missingness",
        "prediction_id",
        "state",
        "support_roots",
        "target",
        "time",
        "units",
    }
    if not {"kind", "meaning", "mechanism_id"}.issubset(query):
        raise FieldIntelligenceError(
            "INVALID_QUERY",
            "causal query must name its meaning and mechanism",
        )
    meaning = query["meaning"]
    meaning_keys = {
        "observation-conditioning": {"action", "actions", "observed"},
        "intervention": {"action", "actions"},
        "unit-counterfactual": {
            "actual_event",
            "alternative_action",
            "coupling",
        },
    }
    if meaning not in meaning_keys or set(query) - (
        common_keys | meaning_keys.get(cast(str, meaning), set())
    ):
        raise FieldIntelligenceError(
            "INVALID_QUERY",
            "causal query meaning or keys are invalid",
        )
    mechanism_id = _identifier(
        query["mechanism_id"], "causal mechanism identity"
    )
    mechanism, _ = _semantic_program_record(state, mechanism_id)
    mechanism_ref = semantic_record_ref(mechanism).as_dict()
    causal_authority = mechanism["payload"].get(
        "causal_authority", False
    )
    if not isinstance(causal_authority, bool):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "causal mechanism authority is not Boolean",
        )
    evidence_class = mechanism["payload"].get(
        "evidence_class", "observational"
    )
    identification = mechanism["payload"].get("identification", {})
    coverage = mechanism["payload"].get("coverage", [])
    identification_limitations = mechanism["payload"].get(
        "identification_limitations", []
    )
    if (
        not isinstance(identification, Mapping)
        or not isinstance(coverage, list)
        or not isinstance(identification_limitations, list)
        or any(not isinstance(item, str) for item in identification_limitations)
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "causal mechanism evidence metadata is invalid",
        )

    def non_identifiable(*limitations: str) -> tuple[dict[str, Any], int]:
        return _semantic_result(
            "query",
            "non-identifiable",
            answer_kind=meaning,
            alternatives=[],
            causal_authority=causal_authority,
            coverage=coverage,
            evidence_class=evidence_class,
            identification=dict(identification),
            identification_limitations=identification_limitations,
            mechanism=mechanism_ref,
            prediction=None,
            limitations=sorted(
                set([*identification_limitations, *limitations])
            ),
        ), 1

    prediction_id = _identifier(
        query.get(
            "prediction_id",
            (
                "prediction:causal:"
                f"{request.get('operation_id', sha256_value(query))}"
            ),
        ),
        "causal prediction identity",
    )
    prediction_request: dict[str, Any] = {
        "mechanism_id": mechanism_id,
        "operation": "predict",
        "prediction_id": prediction_id,
        "query_kind": meaning,
    }
    for name in (
        "action",
        "actions",
        "bindings",
        "collection_policy",
        "context",
        "dependencies",
        "horizon",
        "interval",
        "missingness",
        "state",
        "support_roots",
        "target",
        "time",
        "units",
    ):
        if name in query:
            prediction_request[name] = query[name]

    if meaning == "observation-conditioning":
        observed = query.get("observed")
        if not isinstance(observed, Mapping):
            raise FieldIntelligenceError(
                "INVALID_QUERY",
                "observation conditioning requires observed coordinates",
            )
        raw_state = query.get("state", {})
        if not isinstance(raw_state, Mapping):
            raise FieldIntelligenceError(
                "INVALID_QUERY",
                "causal query state must be a mapping",
            )
        prediction_request["state"] = {
            **dict(raw_state),
            **dict(observed),
        }
    elif meaning == "intervention":
        if "action" not in query and "actions" not in query:
            raise FieldIntelligenceError(
                "INVALID_QUERY",
                "intervention query requires a controlled action",
            )
        if not causal_authority:
            limitation = (
                "intervention-design-not-identified"
                if evidence_class == "interventional-unidentified"
                else "observational-evidence-does-not-identify-intervention"
            )
            return non_identifiable(limitation)
    else:
        if (
            not isinstance(query.get("actual_event"), Mapping)
            or not isinstance(query.get("alternative_action"), Mapping)
            or query.get("coupling") not in {"fresh-noise", "shared-causes"}
        ):
            raise FieldIntelligenceError(
                "INVALID_QUERY",
                "unit counterfactual requires an event, alternative action, and coupling",
            )
        if not causal_authority:
            return non_identifiable(
                "unit-counterfactual-mechanism-is-not-causally-identified"
            )
        actual_ref, actual_event = _semantic_reference(
            state,
            cast(Mapping[str, Any], query["actual_event"]),
            expected_kind="Event",
            require_current=True,
        )
        if (
            actual_event["status"] != "active"
            or actual_event["epistemic_kind"] != "observed"
            or actual_event["payload"].get("episode_id") is None
        ):
            return non_identifiable(
                "particular-observed-episode-is-unavailable"
            )
        if query["coupling"] == "fresh-noise":
            return non_identifiable(
                "fresh-noise-is-a-population-query-not-a-unit-counterfactual"
            )
        prediction_request["action"] = dict(query["alternative_action"])
        raw_dependencies = prediction_request.get("dependencies", [])
        if not isinstance(raw_dependencies, list):
            raise FieldIntelligenceError(
                "INVALID_QUERY",
                "counterfactual dependencies must be a list",
            )
        prediction_request["dependencies"] = [
            *raw_dependencies,
            actual_ref.as_dict(),
        ]

    predicted, work = _semantic_predict(state, prediction_request)
    limitations = list(predicted.get("limitations", []))
    status = str(predicted["status"])
    if (
        meaning == "unit-counterfactual"
        and status == "alternatives"
        and not query.get("bindings")
    ):
        status = "non-identifiable"
        limitations.append("shared-cause-state-is-not-abduced")
    return _semantic_result(
        "query",
        status,
        answer_kind=meaning,
        alternatives=predicted.get("alternatives", []),
        causal_authority=causal_authority,
        coupling=(
            query.get("coupling")
            if meaning == "unit-counterfactual"
            else None
        ),
        coverage=coverage,
        evidence_class=evidence_class,
        identification=dict(identification),
        identification_limitations=identification_limitations,
        mechanism=mechanism_ref,
        prediction=predicted.get("prediction"),
        limitations=sorted(set(limitations)),
    ), max(1, work + 1)


def _semantic_prediction_loss(
    alternatives: Sequence[Mapping[str, Any]],
    actual: Mapping[str, Any],
    *,
    semantics: str,
) -> dict[str, Any]:
    if not alternatives:
        raise FieldIntelligenceError(
            "INVALID_PREDICTION", "prediction has no alternatives"
        )
    if semantics not in {
        "constraint-set",
        "model-family",
        "probability",
    }:
        raise FieldIntelligenceError(
            "INVALID_PREDICTION",
            "prediction has no valid uncertainty semantics",
        )

    def branch_loss(alternative: Mapping[str, Any]) -> float:
        values = alternative["values"]
        uncertainty = alternative.get("uncertainty", {})
        squared = 0.0
        for name, observed in actual.items():
            predicted = values.get(name)
            bounds = (
                uncertainty.get(name)
                if isinstance(uncertainty, Mapping)
                else None
            )
            if (
                not isinstance(observed, bool)
                and isinstance(observed, (int, float))
                and isinstance(bounds, list)
                and len(bounds) == 2
                and all(
                    not isinstance(item, bool)
                    and isinstance(item, (int, float))
                    for item in bounds
                )
            ):
                lower, upper = float(bounds[0]), float(bounds[1])
                observed_number = float(observed)
                if observed_number < lower:
                    squared += (lower - observed_number) ** 2
                elif observed_number > upper:
                    squared += (observed_number - upper) ** 2
            elif (
                not isinstance(predicted, bool)
                and not isinstance(observed, bool)
                and isinstance(predicted, (int, float))
                and isinstance(observed, (int, float))
            ):
                squared += (float(predicted) - float(observed)) ** 2
            else:
                squared += 0.0 if predicted == observed else 1.0
        return squared / max(1, len(actual))

    branch_losses = [branch_loss(item) for item in alternatives]
    coverage_loss = min(branch_losses)
    worst_case_loss = max(branch_losses)
    interval_widths = []
    for alternative in alternatives:
        uncertainty = alternative.get("uncertainty", {})
        if not isinstance(uncertainty, Mapping):
            continue
        for bounds in uncertainty.values():
            if (
                isinstance(bounds, list)
                and len(bounds) == 2
                and all(
                    not isinstance(item, bool)
                    and isinstance(item, (int, float))
                    for item in bounds
                )
            ):
                interval_widths.append(float(bounds[1]) - float(bounds[0]))
    metrics: dict[str, Any] = {
        "alternative_count": len(alternatives),
        "branch_losses": branch_losses,
        "coverage": coverage_loss <= 1.0e-12,
        "coverage_loss": coverage_loss,
        "interval_width_total": sum(interval_widths),
        "out_of_family": coverage_loss > 1.0e-12,
        "prediction_semantics": semantics,
        "worst_case_loss": worst_case_loss,
    }
    if semantics == "probability":
        weights = [
            _finite(item.get("weight"), "prediction alternative weight")
            for item in alternatives
        ]
        total = sum(weights)
        if (
            total <= 0.0
            or any(weight < 0.0 for weight in weights)
            or abs(total - 1.0) > 1.0e-9
        ):
            raise FieldIntelligenceError(
                "INVALID_PREDICTION",
                "prediction probability is not normalized",
            )
        metrics.update(
            {
                "loss": sum(
                    weight * loss
                    for weight, loss in zip(
                        weights, branch_losses, strict=True
                    )
                ),
                "probability_score_status": (
                    "proper-score-unavailable-without-observation-density"
                ),
                "scoring_rule": "probability-weighted-squared-error",
            }
        )
    elif semantics == "constraint-set":
        metrics.update(
            {
                "loss": coverage_loss,
                "scoring_rule": "set-coverage",
                "set_size": len(alternatives),
            }
        )
    else:
        model_losses: dict[bytes, list[tuple[float | None, float]]] = {}
        model_labels: dict[bytes, Any] = {}
        for alternative, loss in zip(
            alternatives, branch_losses, strict=True
        ):
            model_path = alternative.get("model_path", [])
            key = canonical_json_bytes(model_path)
            model_labels[key] = model_path
            model_losses.setdefault(key, []).append(
                (
                    (
                        float(alternative["conditional_weight"])
                        if "conditional_weight" in alternative
                        else None
                    ),
                    loss,
                )
            )
        per_model: list[dict[str, Any]] = []
        for key in sorted(model_losses):
            rows = model_losses[key]
            if all(weight is not None for weight, _ in rows):
                conditional_loss = sum(
                    cast(float, weight) * loss for weight, loss in rows
                )
                rule = "conditional-probability-weighted-squared-error"
            else:
                conditional_loss = min(loss for _, loss in rows)
                rule = "model-conditional-set-coverage"
            per_model.append(
                {
                    "loss": conditional_loss,
                    "model_path": model_labels[key],
                    "scoring_rule": rule,
                }
            )
        metrics.update(
            {
                "loss": min(item["loss"] for item in per_model),
                "model_conditional_losses": per_model,
                "scoring_rule": "model-family-unaggregated",
            }
        )
    return metrics


def _semantic_assess_prediction(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("actual", "event_id", "prediction_id"),
        optional=("source", "support_roots"),
    )
    prediction_id = _identifier(
        request["prediction_id"], "prediction identity"
    )
    prediction = _semantic_current_record(
        state, "Assessment", prediction_id
    )
    if (
        prediction["payload"].get("purpose") != "prediction"
        or prediction["status"] != "active"
    ):
        raise FieldIntelligenceError(
            "ASSESSMENT_CONFLICT", "prediction is not awaiting assessment"
        )
    if not isinstance(request["actual"], Mapping):
        raise FieldIntelligenceError(
            "ASSESSMENT_CONFLICT", "prediction outcome must be a mapping"
        )
    actual = _regional_plain(
        dict(request["actual"]), "prediction outcome"
    )
    event_id = _identifier(request["event_id"], "outcome event identity")
    outcome_event = _semantic_current_record(state, "Event", event_id)
    outcome_event_ref = semantic_record_ref(outcome_event).as_dict()
    if outcome_event["epistemic_kind"] != "observed":
        raise FieldIntelligenceError(
            "ASSESSMENT_CONFLICT",
            "prediction assessment requires a verified observed outcome",
        )
    assessment_metrics = _semantic_prediction_loss(
        prediction["payload"]["alternatives"],
        actual,
        semantics=str(
            prediction["payload"].get("prediction_semantics", "")
        ),
    )
    loss = float(assessment_metrics["loss"])
    assessed_ref = _semantic_append_record(
        state,
        record_id=prediction_id,
        kind="Assessment",
        payload={
            **prediction["payload"],
            "actual": actual,
            "assessment_metrics": assessment_metrics,
            "loss": loss,
        },
        status="assessed",
        epistemic_kind="observed",
        dependencies=(*prediction["dependencies"], outcome_event_ref),
        support_roots=sorted(
            set(
                prediction["support_roots"]
                + outcome_event["support_roots"]
                + list(cast(Any, request.get("support_roots", [])))
            )
        ),
        derivation={
            **prediction["derivation"],
            "outcome_event": outcome_event_ref,
            "source": request.get("source"),
        },
        applicability=prediction["applicability"],
        valid_time=prediction["valid_time"],
        frame=prediction["frame"],
        units=prediction["units"],
        scope=prediction["scope"],
    )

    frontier: list[dict[str, Any]] = []
    _semantic_reindex_record(state, assessed_ref)
    proposal = state["continuation"].get("proposal")
    lifecycle_phase: dict[str, Any] | None = None
    resolved_obligation: dict[str, Any] | None = None
    if (
        isinstance(proposal, dict)
        and isinstance(proposal.get("prediction"), Mapping)
        and SemanticRef.from_dict(proposal["prediction"]).id == prediction_id
    ):
        acknowledgment = proposal.get("acknowledgment")
        if (
            proposal.get("status") != "acknowledged"
            or not isinstance(acknowledgment, Mapping)
            or SemanticRef.from_dict(acknowledgment).id != event_id
            or outcome_event["payload"].get("observation_verified") is not True
            or outcome_event["payload"].get("observation") != actual
        ):
            raise FieldIntelligenceError(
                "ASSESSMENT_CONFLICT",
                "action prediction assessment does not match its verified "
                "acknowledgment",
            )
        proposal["assessment"] = assessed_ref
        lifecycle_phase = _semantic_action_phase(
            state,
            proposal,
            request,
            phase="assessed",
            proposal_status="assessed",
            progress={"completed": 1, "total": 1},
            effect_count=proposal["phases"][-1]["effect_count"],
            metadata={
                "assessment": assessed_ref,
                "assessment_metrics": assessment_metrics,
                "outcome_event": outcome_event_ref,
            },
        )
        resolved_obligation = _semantic_revise_action_obligation(
            state,
            proposal,
            outcome_state="assessed",
            status="resolved",
            epistemic_kind="assessed",
            dependency=assessed_ref,
        )
    return _semantic_result(
        "assess-prediction",
        "supported",
        prediction=assessed_ref,
        assessment_metrics=assessment_metrics,
        loss=loss,
        invalidation_frontier=frontier,
        action_phase=lifecycle_phase,
        action_proposal=proposal if lifecycle_phase is not None else None,
        obligation=resolved_obligation,
    ), max(1, 1 + len(frontier))


def _semantic_mechanism_episode(
    value: Mapping[str, Any], label: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"{label} must be a mapping",
        )
    allowed = {
        "action",
        "collection",
        "context",
        "episode_id",
        "pair_id",
        "intervention",
        "interval",
        "next",
        "outcome_status",
        "state",
    }
    if set(value) - allowed or not {"next", "state"}.issubset(value):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"{label} has an invalid episode schema",
        )
    episode = _regional_plain(dict(value), label)
    for name in ("state", "next", "action", "context", "interval"):
        item = (
            episode.get(name, {})
            if name not in {"state", "next"}
            else episode.get(name)
        )
        if not isinstance(item, dict):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_EVIDENCE",
                f"{label} {name} must be a mapping",
            )
    if "intervention" in episode and not isinstance(
        episode["intervention"], bool
    ):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"{label} intervention must be Boolean",
        )
    outcome_status = episode.get("outcome_status", "observed-and-scored")
    if outcome_status not in {
        "abandoned-unresolved-effect",
        "canceled-before-effect",
        "censored",
        "observation-unavailable",
        "observed-and-scored",
        "partially-observed",
        "pending",
    }:
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"{label} outcome status is invalid",
        )
    episode["outcome_status"] = outcome_status
    collection = episode.get("collection", {})
    if not isinstance(collection, dict):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"{label} collection record must be a mapping",
        )
    allowed_collection = {
        "available_actions",
        "constraints",
        "outcome_availability",
        "policy_version",
        "randomization_probability",
        "selected_action",
        "selection_assumptions",
        "selection_mode",
    }
    if set(collection) - allowed_collection:
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"{label} collection record is invalid",
        )
    selected_action = collection.get("selected_action")
    if selected_action is not None and (
        not isinstance(selected_action, dict)
        or selected_action != episode.get("action", {})
    ):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"{label} selected action disagrees with the episode",
        )
    available_actions = collection.get("available_actions", [])
    if (
        not isinstance(available_actions, list)
        or any(not isinstance(item, dict) for item in available_actions)
        or (
            selected_action is not None
            and available_actions
            and selected_action not in available_actions
        )
    ):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"{label} available action set is invalid",
        )
    selection_mode = collection.get("selection_mode", "unknown")
    if selection_mode not in {"deterministic", "randomized", "unknown"}:
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"{label} collection selection mode is invalid",
        )
    propensity = collection.get("randomization_probability")
    if propensity is not None:
        probability = _finite(propensity, f"{label} propensity")
        if (
            probability <= 0.0
            or probability > 1.0
            or selection_mode != "randomized"
        ):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_EVIDENCE",
                f"{label} randomization probability is invalid",
            )
        collection["randomization_probability"] = probability
    elif selection_mode == "randomized":
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"{label} randomized collection lacks its actual propensity",
        )
    if collection.get("policy_version") is not None:
        collection["policy_version"] = _identifier(
            collection["policy_version"], f"{label} policy version"
        )
    selection_assumptions = collection.get("selection_assumptions", [])
    if not isinstance(selection_assumptions, list):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"{label} selection assumptions are invalid",
        )
    collection["selection_assumptions"] = [
        _identifier(item, f"{label} selection assumption")
        for item in selection_assumptions
    ]
    collection["selection_mode"] = selection_mode
    episode["collection"] = collection
    if episode.get("episode_id") is not None:
        episode["episode_id"] = _identifier(
            episode["episode_id"], f"{label} identity"
        )
    if episode.get("pair_id") is not None:
        episode["pair_id"] = _identifier(
            episode["pair_id"], f"{label} pair identity"
        )
    return episode


def _semantic_episode_loss(
    program: Mapping[str, Any],
    episode: Mapping[str, Any],
    *,
    observation_program: Mapping[str, Any] | None = None,
) -> tuple[float | None, str]:
    normalized = _semantic_mechanism_episode(
        episode, "mechanism evidence episode"
    )
    if normalized["outcome_status"] != "observed-and-scored":
        return None, str(normalized["outcome_status"])

    def program_alternatives(
        outcome: Mapping[str, Any], source: str
    ) -> tuple[list[dict[str, Any]], str]:
        if outcome["status"] == "supported":
            return (
                [
                    {
                        "uncertainty": outcome.get("uncertainty", {}),
                        "values": outcome["values"],
                    }
                ],
                "deterministic",
            )
        branches = outcome.get("alternatives")
        if not isinstance(branches, list):
            return [], "deterministic"
        weights = outcome.get("alternative_weights")
        if weights is not None:
            if (
                not isinstance(weights, list)
                or len(weights) != len(branches)
                or any(
                    isinstance(item, bool)
                    or not isinstance(item, (int, float))
                    or float(item) < 0.0
                    for item in weights
                )
                or abs(sum(float(item) for item in weights) - 1.0)
                > 1.0e-9
            ):
                raise FieldIntelligenceError(
                    "INVALID_MECHANISM_EVIDENCE",
                    "candidate alternative probability is invalid",
                )
            semantics = "probability"
        else:
            details = outcome.get("alternative_details")
            semantics = (
                "model-family"
                if isinstance(details, list)
                and len(details) == len(branches)
                else "constraint-set"
            )
        uncertainty_rows = outcome.get("alternative_uncertainties")
        result = []
        for index, values in enumerate(branches):
            row: dict[str, Any] = {
                "uncertainty": (
                    uncertainty_rows[index]
                    if isinstance(uncertainty_rows, list)
                    and len(uncertainty_rows) == len(branches)
                    and isinstance(uncertainty_rows[index], Mapping)
                    else outcome.get("uncertainty", {})
                ),
                "values": values,
            }
            if semantics == "probability":
                row["weight"] = float(weights[index])
            elif semantics == "model-family":
                row["model_path"] = [
                    {
                        "alternative_index": index,
                        "model_ids": [
                            str(item)
                            for item in (
                                outcome.get("alternative_details", [])[index].get(
                                    "modes", []
                                )
                                if isinstance(
                                    outcome.get("alternative_details"), list
                                )
                                and len(outcome["alternative_details"])
                                == len(branches)
                                and isinstance(
                                    outcome["alternative_details"][index],
                                    Mapping,
                                )
                                else []
                            )
                        ],
                        "source": source,
                    }
                ]
            else:
                row["set_path"] = [
                    {
                        "alternative_index": index,
                        "source": source,
                    }
                ]
            result.append(row)
        return result, semantics

    def combined_semantics(left: str, right: str) -> str:
        if left == "deterministic":
            return right
        if right == "deterministic":
            return left
        if left == right and left in {"constraint-set", "probability"}:
            return left
        return "model-family"

    try:
        outcome = execute_semantic_program(
            program,
            normalized["state"],
            action=normalized.get("action", {}),
            context=normalized.get("context", {}),
            interval=normalized.get("interval", {}),
        )
        if outcome["status"] not in {"supported", "alternatives"}:
            return 1.0e12, str(outcome["status"])
        transition_rows, transition_semantics = program_alternatives(
            outcome, "transition"
        )
        if observation_program is None:
            alternatives = transition_rows
            semantics = (
                "constraint-set"
                if transition_semantics == "deterministic"
                else transition_semantics
            )
        else:
            staged: list[
                tuple[Mapping[str, Any], Mapping[str, Any], str]
            ] = []
            observation_semantics_seen: list[str] = []
            for transition in transition_rows:
                observation = execute_semantic_program(
                    observation_program,
                    transition["values"],
                    action=normalized.get("action", {}),
                    context=normalized.get("context", {}),
                    interval=normalized.get("interval", {}),
                )
                if observation["status"] not in {
                    "supported",
                    "alternatives",
                }:
                    return (
                        1.0e12,
                        f"observation-{observation['status']}",
                    )
                observation_rows, observation_semantics = (
                    program_alternatives(observation, "observation")
                )
                observation_semantics_seen.append(observation_semantics)
                staged.extend(
                    (
                        transition,
                        observed,
                        observation_semantics,
                    )
                    for observed in observation_rows
                )
            semantics = transition_semantics
            for observed_semantics in observation_semantics_seen:
                semantics = combined_semantics(
                    semantics, observed_semantics
                )
            if semantics == "deterministic":
                semantics = "constraint-set"
            alternatives = []
            for transition, observed, observed_semantics in staged:
                row = {
                    "uncertainty": {
                        **dict(transition.get("uncertainty", {})),
                        **dict(observed.get("uncertainty", {})),
                    },
                    "values": observed["values"],
                }
                probability_factor = 1.0
                has_probability = False
                if transition_semantics == "probability":
                    probability_factor *= float(transition["weight"])
                    has_probability = True
                if observed_semantics == "probability":
                    probability_factor *= float(observed["weight"])
                    has_probability = True
                if semantics == "probability":
                    row["weight"] = probability_factor
                elif semantics == "model-family":
                    row["model_path"] = [
                        *cast(list[Any], transition.get("model_path", [])),
                        *cast(list[Any], transition.get("set_path", [])),
                        *cast(list[Any], observed.get("model_path", [])),
                        *cast(list[Any], observed.get("set_path", [])),
                    ]
                    if has_probability:
                        row["conditional_weight"] = probability_factor
                alternatives.append(row)
    except (RegionalFieldError, ValueError) as exc:
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            f"mechanism evidence cannot execute: {exc}",
        ) from exc
    if not alternatives:
        return 1.0e12, "support-gap"
    if semantics == "probability":
        total_weight = sum(float(item["weight"]) for item in alternatives)
        if total_weight <= 0.0:
            return 1.0e12, "support-gap"
        for alternative in alternatives:
            alternative["weight"] = (
                float(alternative["weight"]) / total_weight
            )
    metrics = _semantic_prediction_loss(
        alternatives,
        cast(Mapping[str, Any], normalized["next"]),
        semantics=semantics,
    )
    return float(metrics["loss"]), (
        "supported" if len(alternatives) == 1 else "alternatives"
    )


def _semantic_table_candidate(
    episodes: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for episode in episodes:
        state = episode.get("state")
        action = episode.get("action", {})
        successor = episode.get("next")
        if not all(
            isinstance(item, Mapping) for item in (state, action, successor)
        ):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_EVIDENCE", "mechanism episode is invalid"
            )
        normalized_state = cast(Mapping[str, Any], state)
        normalized_action = cast(Mapping[str, Any], action)
        normalized_successor = cast(Mapping[str, Any], successor)
        when = {
            **dict(normalized_state),
            **{
                f"action.{name}": value
                for name, value in normalized_action.items()
            },
        }
        row = {
            "when": _regional_plain(when, "table condition"),
            "set": _regional_plain(
                dict(normalized_successor), "table successor"
            ),
        }
        if row not in rows:
            rows.append(row)
    rows.sort(key=canonical_json_bytes)
    return semantic_program_payload(
        program_kind="table",
        body={"rows": rows, "default": None},
        max_work=max(1, len(rows)),
        max_branches=max(1, len(rows)),
    )


def _semantic_timer_candidate(
    request: Mapping[str, Any],
    episodes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    output_key = _identifier(
        request.get("output_key", "observation"), "timer output key"
    )
    elapsed_key = _identifier(
        request.get("elapsed_key", "elapsed"), "timer elapsed key"
    )
    fired = request.get("fired", "fired")
    quiet = request.get("quiet", "quiet")
    fired_times: list[float] = []
    quiet_times: list[float] = []
    for episode in episodes:
        state = episode.get("state", {})
        successor = episode.get("next", {})
        interval = episode.get("interval", {})
        if not isinstance(state, Mapping) or not isinstance(
            successor, Mapping
        ) or not isinstance(interval, Mapping):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_EVIDENCE", "timer episode is invalid"
            )
        elapsed = _finite(
            state.get(elapsed_key, 0.0), "timer evidence elapsed"
        )
        if "duration" in interval:
            elapsed += _finite(
                interval["duration"], "timer evidence duration"
            )
        observed = successor.get(output_key)
        if observed == fired:
            fired_times.append(elapsed)
        elif observed == quiet:
            quiet_times.append(elapsed)
    if not fired_times or not quiet_times or max(quiet_times) >= min(fired_times):
        raise FieldIntelligenceError(
            "REPRESENTATION_INSUFFICIENT",
            "timer evidence does not identify a separating threshold",
        )
    threshold = (max(quiet_times) + min(fired_times)) / 2.0
    return semantic_program_payload(
        program_kind="timer",
        body={
            "elapsed_key": elapsed_key,
            "fired": fired,
            "output_key": output_key,
            "quiet": quiet,
            "reset_on": list(request.get("reset_on", [])),
            "threshold": threshold,
        },
        max_work=1,
    )


PARAMETER_LEARNING_SCHEMA = "cassifi.semantic-parameter-learning.v1"
PARAMETER_PATHS = frozenset(
    {
        "analytic-local",
        "continuous-cells",
        "finite-alternatives",
        "observed-sufficient-statistics",
    }
)


def _semantic_matrix_rank(matrix: Sequence[Sequence[float]]) -> int:
    rows = [list(map(float, row)) for row in matrix]
    if not rows:
        return 0
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE", "parameter matrix is ragged"
        )
    scale = max(
        1.0,
        max((abs(value) for row in rows for value in row), default=0.0),
    )
    tolerance = 1.0e-12 * scale
    rank = 0
    for column in range(width):
        pivot = max(
            range(rank, len(rows)),
            key=lambda index: abs(rows[index][column]),
            default=rank,
        )
        if rank >= len(rows) or abs(rows[pivot][column]) <= tolerance:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        divisor = rows[rank][column]
        rows[rank] = [value / divisor for value in rows[rank]]
        for index in range(len(rows)):
            if index == rank:
                continue
            factor = rows[index][column]
            if abs(factor) <= tolerance:
                continue
            rows[index] = [
                value - factor * pivot_value
                for value, pivot_value in zip(
                    rows[index], rows[rank], strict=True
                )
            ]
        rank += 1
        if rank == len(rows):
            break
    return rank


def _semantic_linear_solve(
    matrix: Sequence[Sequence[float]], right: Sequence[float]
) -> list[float] | None:
    size = len(matrix)
    if (
        size == 0
        or len(right) != size
        or any(len(row) != size for row in matrix)
    ):
        return None
    rows = [
        [*map(float, row), float(value)]
        for row, value in zip(matrix, right, strict=True)
    ]
    scale = max(
        1.0,
        max((abs(value) for row in rows for value in row), default=0.0),
    )
    tolerance = 1.0e-12 * scale
    for column in range(size):
        pivot = max(
            range(column, size),
            key=lambda index: abs(rows[index][column]),
        )
        if abs(rows[pivot][column]) <= tolerance:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [value / divisor for value in rows[column]]
        for index in range(size):
            if index == column:
                continue
            factor = rows[index][column]
            rows[index] = [
                value - factor * pivot_value
                for value, pivot_value in zip(
                    rows[index], rows[column], strict=True
                )
            ]
    return [row[-1] for row in rows]


def _semantic_parameter_evidence(
    state: Mapping[str, Any], raw: Any, label: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(raw, Mapping):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_EVIDENCE",
            f"{label} must be an Event reference",
        )
    reference, event = _semantic_reference(
        state,
        raw,
        expected_kind="Event",
        require_current=True,
    )
    if event["status"] != "active" or event["epistemic_kind"] not in {
        "corrected",
        "observed",
    }:
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_EVIDENCE",
            f"{label} is not an active observed Event",
        )
    return reference.as_dict(), event


def _semantic_parameter_contributions(
    state: Mapping[str, Any],
    raw: Any,
    evidence_prefix: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if (
        not isinstance(raw, list)
        or len(raw) > state["bounds"]["max_observations"]
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_EVIDENCE",
            "parameter contributions must be a bounded list",
        )
    prefix_keys = {
        (
            item["kind"],
            item["id"],
            int(item["content_version"]),
        )
        for item in evidence_prefix
    }
    contributions: list[dict[str, Any]] = []
    identities: set[str] = set()
    evidence_keys: set[tuple[str, str, int]] = set()
    for index, item in enumerate(raw):
        if (
            not isinstance(item, Mapping)
            or set(item)
            != {
                "contribution_id",
                "evidence",
                "values",
            }
            or not isinstance(item["values"], Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_EVIDENCE",
                f"parameter contribution {index} has an invalid schema",
            )
        contribution_id = _identifier(
            item["contribution_id"],
            f"parameter contribution {index} identity",
        )
        if contribution_id in identities:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "parameter contribution identity is duplicated",
            )
        evidence_ref, _ = _semantic_parameter_evidence(
            state,
            item["evidence"],
            f"parameter contribution {index} evidence",
        )
        evidence_key = (
            evidence_ref["kind"],
            evidence_ref["id"],
            int(evidence_ref["content_version"]),
        )
        if evidence_key not in prefix_keys:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_EVIDENCE",
                "parameter contribution evidence is outside its prefix",
            )
        if evidence_key in evidence_keys:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "one Event cannot contribute twice to one parameter update",
            )
        identities.add(contribution_id)
        evidence_keys.add(evidence_key)
        body = {
            "contribution_id": contribution_id,
            "evidence": evidence_ref,
            "values": _regional_plain(
                dict(item["values"]),
                f"parameter contribution {index} values",
            ),
        }
        contributions.append(
            {**body, "contribution_sha256": sha256_value(body)}
        )
    return contributions


def _semantic_parameter_interpretation(
    value: Any, label: str
) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value)
        != {
            "assumptions",
            "likelihood_or_compatibility",
            "probability_model",
            "semantics",
        }
        or value["semantics"] not in {"compatibility", "probability"}
        or not isinstance(value["assumptions"], list)
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE", f"{label} is invalid"
        )
    assumptions = [
        _identifier(item, f"{label} assumption")
        for item in value["assumptions"]
    ]
    rule = _identifier(
        value["likelihood_or_compatibility"], f"{label} rule"
    )
    probability_model = (
        _semantic_probability_model(
            value["probability_model"], f"{label} probability model"
        )
        if value["semantics"] == "probability"
        else None
    )
    if value["semantics"] == "compatibility" and value[
        "probability_model"
    ] is not None:
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "compatibility statistics cannot carry probability metadata",
        )
    return {
        "assumptions": assumptions,
        "likelihood_or_compatibility": rule,
        "probability_model": probability_model,
        "semantics": value["semantics"],
    }


def _semantic_parameter_prefix(
    state: Mapping[str, Any], raw: Any
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if (
        not isinstance(raw, list)
        or len(raw) > state["bounds"]["max_observations"]
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_EVIDENCE",
            "parameter evidence prefix is invalid",
        )
    prefix: list[dict[str, Any]] = []
    dependencies: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for index, item in enumerate(raw):
        reference, _ = _semantic_parameter_evidence(
            state, item, f"parameter evidence prefix {index}"
        )
        key = (
            reference["kind"],
            reference["id"],
            int(reference["content_version"]),
        )
        if key in seen:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "parameter evidence prefix repeats an Event",
            )
        seen.add(key)
        prefix.append(reference)
        dependencies.append(reference)
    return prefix, dependencies


def _semantic_parameter_new_contributions(
    prior: Mapping[str, Any] | None,
    evidence_prefix: Sequence[Mapping[str, Any]],
    contributions: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if prior is None:
        prior_prefix: list[dict[str, Any]] = []
        prior_contributions: list[dict[str, Any]] = []
    else:
        prior_prefix = list(prior.get("evidence_prefix", []))
        prior_contributions = list(prior.get("contributions", []))
        if evidence_prefix[: len(prior_prefix)] != prior_prefix:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_EVIDENCE",
                "parameter evidence prefix does not extend frozen history",
            )
    prior_by_id = {
        str(item["contribution_id"]): item for item in prior_contributions
    }
    prior_evidence = {
        canonical_json_bytes(item["evidence"]) for item in prior_contributions
    }
    new_rows: list[dict[str, Any]] = []
    for contribution in contributions:
        contribution_id = str(contribution["contribution_id"])
        existing = prior_by_id.get(contribution_id)
        if existing is not None:
            if existing != contribution:
                raise FieldIntelligenceError(
                    "OPERATION_CONFLICT",
                    "parameter contribution identity changed content",
                )
            continue
        if canonical_json_bytes(contribution["evidence"]) in prior_evidence:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "old evidence cannot acquire a second parameter contribution",
            )
        new_rows.append(dict(contribution))
    suffix = list(evidence_prefix[len(prior_prefix) :])
    if [item["evidence"] for item in new_rows] != suffix:
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_EVIDENCE",
            "new contributions must cover the new evidence prefix exactly once",
        )
    return prior_contributions + new_rows, new_rows


def _semantic_parameter_statistics(
    request: Mapping[str, Any],
    prior: Mapping[str, Any] | None,
    all_contributions: Sequence[Mapping[str, Any]],
    new_contributions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    raw_variables = request.get("variables")
    if (
        not isinstance(raw_variables, list)
        or not raw_variables
        or len(raw_variables) > 64
        or len(set(raw_variables)) != len(raw_variables)
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "sufficient statistics require unique bounded variables",
        )
    variables = [
        _identifier(item, "sufficient-statistic variable")
        for item in raw_variables
    ]
    interpretation = _semantic_parameter_interpretation(
        request.get("interpretation"), "sufficient-statistic interpretation"
    )
    raw_design = request.get("design_variables", variables)
    raw_targets = request.get("target_variables", [])
    if (
        not isinstance(raw_design, list)
        or not isinstance(raw_targets, list)
        or len(set(raw_design)) != len(raw_design)
        or len(set(raw_targets)) != len(raw_targets)
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "sufficient-statistic design or target variables are invalid",
        )
    design_variables = [
        _identifier(item, "sufficient-statistic design variable")
        for item in raw_design
    ]
    target_variables = [
        _identifier(item, "sufficient-statistic target variable")
        for item in raw_targets
    ]
    if (
        any(item not in variables for item in design_variables)
        or any(item not in variables for item in target_variables)
        or set(design_variables) & set(target_variables)
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "design and target variables must be disjoint declared variables",
        )
    if prior is not None:
        frozen = prior["state"]
        if (
            frozen.get("variables") != variables
            or frozen.get("design_variables") != design_variables
            or frozen.get("target_variables") != target_variables
            or frozen.get("interpretation") != interpretation
        ):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "sufficient-statistic definition changed across updates",
            )
    sums = {name: 0.0 for name in variables}
    cross_products = {
        left: {right: 0.0 for right in variables} for left in variables
    }
    for contribution in all_contributions:
        values = contribution["values"]
        if any(
            name not in values
            or isinstance(values[name], bool)
            or not isinstance(values[name], (int, float))
            or not math.isfinite(float(values[name]))
            for name in variables
        ):
            raise FieldIntelligenceError(
                "INSUFFICIENT_OBSERVATION",
                "sufficient statistics require every declared variable observed",
            )
        row = {name: float(values[name]) for name in variables}
        for name in variables:
            sums[name] += row[name]
        for left in variables:
            for right in variables:
                cross_products[left][right] += row[left] * row[right]
    gram = [
        [cross_products[left][right] for right in design_variables]
        for left in design_variables
    ]
    rank = _semantic_matrix_rank(gram)
    parameters: dict[str, dict[str, float]] = {}
    if design_variables and rank == len(design_variables):
        for target in target_variables:
            solved = _semantic_linear_solve(
                gram,
                [
                    cross_products[source][target]
                    for source in design_variables
                ],
            )
            if solved is not None:
                parameters[target] = {
                    source: coefficient
                    for source, coefficient in zip(
                        design_variables, solved, strict=True
                    )
                }
    limitations = []
    if design_variables and rank < len(design_variables):
        limitations.append("rank-deficient-design")
    return {
        "count": len(all_contributions),
        "cross_products": cross_products,
        "design_rank": rank,
        "design_variables": design_variables,
        "identified": (
            bool(design_variables)
            and rank == len(design_variables)
            and bool(target_variables)
        ),
        "interpretation": interpretation,
        "limitations": limitations,
        "parameters": parameters,
        "sums": sums,
        "target_variables": target_variables,
        "variables": variables,
    }


def _semantic_finite_parameter_state(
    state: Mapping[str, Any],
    request: Mapping[str, Any],
    prior: Mapping[str, Any] | None,
    new_contributions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    semantics = request.get("alternative_semantics")
    if semantics not in {"constraint-set", "probability"}:
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "finite alternatives require constraint-set or probability semantics",
        )
    raw_alternatives = request.get("alternatives")
    if (
        not isinstance(raw_alternatives, list)
        or not raw_alternatives
        or len(raw_alternatives) > state["bounds"]["max_alternatives"]
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "finite parameter alternatives are empty or exceed their bound",
        )
    alternatives: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_alternatives):
        allowed = {
            "alternative_id",
            "constraints",
            "latent",
            "parameters",
            "parent_id",
            "prior_mass",
        }
        if (
            not isinstance(raw, Mapping)
            or set(raw) - allowed
            or not {"alternative_id", "parameters"}.issubset(raw)
            or not isinstance(raw["parameters"], Mapping)
            or not isinstance(raw.get("latent", {}), Mapping)
            or not isinstance(raw.get("constraints", []), list)
        ):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                f"finite parameter alternative {index} is invalid",
            )
        alternative_id = _identifier(
            raw["alternative_id"],
            f"finite parameter alternative {index} identity",
        )
        if alternative_id in seen:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "finite parameter alternative identity is duplicated",
            )
        seen.add(alternative_id)
        parent_id = (
            None
            if raw.get("parent_id") is None
            else _identifier(
                raw["parent_id"],
                f"finite parameter alternative {index} parent",
            )
        )
        raw_mass = raw.get("prior_mass")
        mass = (
            None
            if raw_mass is None
            else _finite(
                raw_mass, f"finite parameter alternative {index} prior mass"
            )
        )
        if mass is not None and mass < 0.0:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "finite parameter prior mass must be nonnegative",
            )
        if (semantics == "probability") != (mass is not None):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "probabilistic finite alternatives require prior mass and sets forbid it",
            )
        alternatives.append(
            {
                "alternative_id": alternative_id,
                "constraints": _regional_plain(
                    raw.get("constraints", []),
                    f"finite parameter alternative {index} constraints",
                ),
                "latent": _regional_plain(
                    dict(raw.get("latent", {})),
                    f"finite parameter alternative {index} latent state",
                ),
                "parameters": _regional_plain(
                    dict(raw["parameters"]),
                    f"finite parameter alternative {index} parameters",
                ),
                "parent_id": parent_id,
                "prior_mass": mass,
            }
        )
    alternatives.sort(key=lambda item: item["alternative_id"])
    frozen_masses: dict[str, float] = {}
    if prior is None:
        if semantics == "probability":
            total = sum(
                cast(float, item["prior_mass"]) for item in alternatives
            )
            if abs(total - 1.0) > 1.0e-9:
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_UPDATE",
                    "finite parameter prior masses are not normalized",
                )
            frozen_masses = {
                item["alternative_id"]: cast(float, item["prior_mass"])
                for item in alternatives
            }
        if any(item["parent_id"] is not None for item in alternatives):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "initial finite alternatives cannot name refinement parents",
            )
    else:
        frozen = prior["state"]
        if frozen.get("semantics") != semantics:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "finite parameter semantics changed across updates",
            )
        previous_rows = {
            item["alternative_id"]: item
            for item in frozen.get("alternatives", [])
        }
        child_rows: dict[str, list[dict[str, Any]]] = {}
        unchanged: set[str] = set()
        for item in alternatives:
            alternative_id = item["alternative_id"]
            parent_id = item["parent_id"]
            if alternative_id in previous_rows:
                previous = previous_rows[alternative_id]
                if parent_id is not None or any(
                    item[name] != previous[name]
                    for name in ("constraints", "latent", "parameters")
                ):
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "retained finite alternative changed its definition",
                    )
                unchanged.add(alternative_id)
            elif parent_id is None or parent_id not in previous_rows:
                raise FieldIntelligenceError(
                    "OPERATION_CONFLICT",
                    "new finite alternative lacks a current refinement parent",
                )
            else:
                child_rows.setdefault(parent_id, []).append(item)
        if set(previous_rows) != unchanged | set(child_rows):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "finite refinement silently removed an alternative",
            )
        for parent_id, children in child_rows.items():
            if semantics == "probability":
                parent_mass = float(previous_rows[parent_id]["mass"])
                child_mass = sum(
                    cast(float, item["prior_mass"]) for item in children
                )
                if abs(child_mass - parent_mass) > 1.0e-9:
                    raise FieldIntelligenceError(
                        "INVALID_PARAMETER_UPDATE",
                        "finite refinement does not conserve parent mass",
                    )
        if semantics == "probability":
            for item in alternatives:
                if item["alternative_id"] in previous_rows:
                    expected = float(
                        previous_rows[item["alternative_id"]]["mass"]
                    )
                    if abs(cast(float, item["prior_mass"]) - expected) > 1.0e-9:
                        raise FieldIntelligenceError(
                            "INVALID_PARAMETER_UPDATE",
                            "finite update did not freeze the pre-update mass",
                        )
            frozen_masses = {
                item["alternative_id"]: cast(float, item["prior_mass"])
                for item in alternatives
            }
    likelihoods = {
        item["alternative_id"]: 1.0 for item in alternatives
    }
    compatible = {item["alternative_id"]: True for item in alternatives}
    contribution_likelihoods: list[dict[str, Any]] = []
    for contribution in new_contributions:
        values = contribution["values"]
        field = "likelihoods" if semantics == "probability" else "compatible"
        raw_scores = values.get(field)
        if not isinstance(raw_scores, Mapping) or set(raw_scores) != seen:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_EVIDENCE",
                f"finite parameter contribution requires {field} for every alternative",
            )
        normalized_scores: dict[str, Any] = {}
        for alternative_id in sorted(seen):
            score = raw_scores[alternative_id]
            if semantics == "probability":
                likelihood = _finite(
                    score,
                    f"finite alternative {alternative_id} likelihood",
                )
                if likelihood < 0.0:
                    raise FieldIntelligenceError(
                        "INVALID_PARAMETER_EVIDENCE",
                        "finite alternative likelihood must be nonnegative",
                    )
                likelihoods[alternative_id] *= likelihood
                normalized_scores[alternative_id] = likelihood
            else:
                if not isinstance(score, bool):
                    raise FieldIntelligenceError(
                        "INVALID_PARAMETER_EVIDENCE",
                        "finite alternative compatibility must be Boolean",
                    )
                compatible[alternative_id] &= score
                normalized_scores[alternative_id] = score
        contribution_likelihoods.append(
            {
                "contribution_id": contribution["contribution_id"],
                field: normalized_scores,
            }
        )
    contradiction = False
    if semantics == "probability":
        unnormalized = {
            alternative_id: frozen_masses[alternative_id]
            * likelihoods[alternative_id]
            for alternative_id in sorted(seen)
        }
        denominator = sum(unnormalized.values())
        contradiction = denominator == 0.0
        posterior = (
            {}
            if contradiction
            else {
                alternative_id: mass / denominator
                for alternative_id, mass in unnormalized.items()
            }
        )
    else:
        posterior = {}
        contradiction = not any(compatible.values())
    result_rows = []
    for item in alternatives:
        alternative_id = item["alternative_id"]
        result_rows.append(
            {
                **item,
                "compatible": compatible[alternative_id],
                "likelihood": (
                    likelihoods[alternative_id]
                    if semantics == "probability"
                    else None
                ),
                "mass": (
                    posterior.get(alternative_id)
                    if semantics == "probability"
                    else None
                ),
            }
        )
    raw_frontier = request.get("frontier", [])
    if (
        not isinstance(raw_frontier, list)
        or len(raw_frontier) > state["bounds"]["max_alternatives"]
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "finite parameter frontier exceeds its bound",
        )
    return {
        "alternatives": result_rows,
        "contradiction": contradiction,
        "contribution_scores": (
            (
                []
                if prior is None
                else list(prior["state"].get("contribution_scores", []))
            )
            + contribution_likelihoods
        ),
        "frozen_preupdate_mass": frozen_masses,
        "frontier": _regional_plain(
            raw_frontier, "finite parameter frontier"
        ),
        "semantics": semantics,
        "survivors": [
            item["alternative_id"]
            for item in result_rows
            if (
                item["mass"] is not None and item["mass"] > 0.0
                if semantics == "probability"
                else item["compatible"]
            )
        ],
    }


def _semantic_cell_volume(bounds: Mapping[str, Sequence[float]]) -> float:
    volume = 1.0
    for interval in bounds.values():
        volume *= float(interval[1]) - float(interval[0])
    return volume


def _semantic_cells_overlap(
    left: Mapping[str, Sequence[float]],
    right: Mapping[str, Sequence[float]],
) -> bool:
    return all(
        max(float(left[name][0]), float(right[name][0]))
        < min(float(left[name][1]), float(right[name][1]))
        for name in left
    )


def _semantic_continuous_parameter_state(
    state: Mapping[str, Any],
    request: Mapping[str, Any],
    prior: Mapping[str, Any] | None,
    new_contributions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    semantics = request.get("cell_semantics")
    if semantics not in {"probability-measure", "set-enclosure"}:
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "continuous cells require probability-measure or set-enclosure semantics",
        )
    raw_integration = request.get("integration")
    if (
        not isinstance(raw_integration, Mapping)
        or set(raw_integration)
        != {"error_rule", "method", "reference_measure", "semantics"}
        or raw_integration["semantics"]
        not in {"exact-partition", "interval-enclosure", "quadrature"}
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "continuous cell integration declaration is invalid",
        )
    integration = {
        "error_rule": _regional_plain(
            raw_integration["error_rule"], "continuous cell error rule"
        ),
        "method": _identifier(
            raw_integration["method"], "continuous cell integration method"
        ),
        "reference_measure": _identifier(
            raw_integration["reference_measure"],
            "continuous cell reference measure",
        ),
        "semantics": raw_integration["semantics"],
    }
    raw_cells = request.get("cells")
    if (
        not isinstance(raw_cells, list)
        or not raw_cells
        or len(raw_cells) > state["bounds"]["max_alternatives"]
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "continuous parameter cells are empty or exceed their bound",
        )
    cells: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    variables: list[str] | None = None
    for index, raw in enumerate(raw_cells):
        if (
            not isinstance(raw, Mapping)
            or set(raw)
            - {"bounds", "cell_id", "parent_id", "prior_mass"}
            or not {"bounds", "cell_id"}.issubset(raw)
            or not isinstance(raw["bounds"], Mapping)
            or not raw["bounds"]
        ):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                f"continuous parameter cell {index} is invalid",
            )
        cell_id = _identifier(
            raw["cell_id"], f"continuous parameter cell {index} identity"
        )
        if cell_id in identifiers:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "continuous parameter cell identity is duplicated",
            )
        identifiers.add(cell_id)
        normalized_bounds: dict[str, list[float]] = {}
        for name, raw_interval in raw["bounds"].items():
            variable = _identifier(name, "continuous parameter variable")
            if (
                not isinstance(raw_interval, list)
                or len(raw_interval) != 2
            ):
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_UPDATE",
                    "continuous parameter bound is not an interval",
                )
            lower = _finite(
                raw_interval[0], f"continuous parameter {variable} lower bound"
            )
            upper = _finite(
                raw_interval[1], f"continuous parameter {variable} upper bound"
            )
            if upper <= lower:
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_UPDATE",
                    "continuous probabilistic cells cannot be point guesses",
                )
            normalized_bounds[variable] = [lower, upper]
        names = sorted(normalized_bounds)
        if variables is None:
            variables = names
        elif names != variables:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "continuous cells do not share one parameter coordinate set",
            )
        raw_mass = raw.get("prior_mass")
        mass = (
            None
            if raw_mass is None
            else _finite(raw_mass, f"continuous cell {cell_id} prior mass")
        )
        if mass is not None and mass < 0.0:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "continuous cell prior mass must be nonnegative",
            )
        if (semantics == "probability-measure") != (mass is not None):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "probability cells require prior mass and set cells forbid it",
            )
        cells.append(
            {
                "bounds": {name: normalized_bounds[name] for name in names},
                "cell_id": cell_id,
                "parent_id": (
                    None
                    if raw.get("parent_id") is None
                    else _identifier(
                        raw["parent_id"],
                        f"continuous cell {cell_id} parent",
                    )
                ),
                "prior_mass": mass,
            }
        )
    cells.sort(key=lambda item: item["cell_id"])
    frozen_masses: dict[str, float] = {}
    if prior is None:
        if any(item["parent_id"] is not None for item in cells):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "initial continuous cells cannot name refinement parents",
            )
        for left_index, left in enumerate(cells):
            for right in cells[left_index + 1 :]:
                if _semantic_cells_overlap(left["bounds"], right["bounds"]):
                    raise FieldIntelligenceError(
                        "INVALID_PARAMETER_UPDATE",
                        "continuous parameter cells overlap",
                    )
        if semantics == "probability-measure":
            total = sum(cast(float, item["prior_mass"]) for item in cells)
            if abs(total - 1.0) > 1.0e-9:
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_UPDATE",
                    "continuous cell prior mass is not normalized",
                )
            frozen_masses = {
                item["cell_id"]: cast(float, item["prior_mass"])
                for item in cells
            }
    else:
        frozen = prior["state"]
        if (
            frozen.get("semantics") != semantics
            or frozen.get("integration") != integration
            or frozen.get("variables") != variables
        ):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "continuous cell definition changed across updates",
            )
        previous = {
            item["cell_id"]: item for item in frozen.get("cells", [])
        }
        retained: set[str] = set()
        children_by_parent: dict[str, list[dict[str, Any]]] = {}
        for item in cells:
            cell_id = item["cell_id"]
            parent_id = item["parent_id"]
            if cell_id in previous:
                if (
                    parent_id is not None
                    or item["bounds"] != previous[cell_id]["bounds"]
                ):
                    raise FieldIntelligenceError(
                        "OPERATION_CONFLICT",
                        "retained continuous cell changed its definition",
                    )
                retained.add(cell_id)
            elif parent_id is None or parent_id not in previous:
                raise FieldIntelligenceError(
                    "OPERATION_CONFLICT",
                    "new continuous cell lacks a current refinement parent",
                )
            else:
                children_by_parent.setdefault(parent_id, []).append(item)
        if set(previous) != retained | set(children_by_parent):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "continuous refinement silently removed a cell",
            )
        for parent_id, children in children_by_parent.items():
            parent = previous[parent_id]
            parent_bounds = parent["bounds"]
            for child in children:
                if any(
                    float(child["bounds"][name][0])
                    < float(parent_bounds[name][0])
                    or float(child["bounds"][name][1])
                    > float(parent_bounds[name][1])
                    for name in cast(list[str], variables)
                ):
                    raise FieldIntelligenceError(
                        "INVALID_PARAMETER_UPDATE",
                        "continuous child lies outside its parent cell",
                    )
            for left_index, left in enumerate(children):
                for right in children[left_index + 1 :]:
                    if _semantic_cells_overlap(
                        left["bounds"], right["bounds"]
                    ):
                        raise FieldIntelligenceError(
                            "INVALID_PARAMETER_UPDATE",
                            "continuous refinement children overlap",
                        )
            child_volume = sum(
                _semantic_cell_volume(item["bounds"]) for item in children
            )
            if abs(
                child_volume - _semantic_cell_volume(parent_bounds)
            ) > 1.0e-9 * max(
                1.0, _semantic_cell_volume(parent_bounds)
            ):
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_UPDATE",
                    "continuous children do not partition their parent cell",
                )
            if semantics == "probability-measure":
                frozen_parent_mass = float(parent["mass"])
                child_mass = sum(
                    cast(float, item["prior_mass"]) for item in children
                )
                if abs(child_mass - frozen_parent_mass) > 1.0e-9:
                    raise FieldIntelligenceError(
                        "INVALID_PARAMETER_UPDATE",
                        "continuous refinement does not conserve current parent mass",
                    )
        if semantics == "probability-measure":
            for item in cells:
                if item["cell_id"] in previous:
                    frozen_mass = float(previous[item["cell_id"]]["mass"])
                    if abs(
                        cast(float, item["prior_mass"]) - frozen_mass
                    ) > 1.0e-9:
                        raise FieldIntelligenceError(
                            "INVALID_PARAMETER_UPDATE",
                            "continuous update did not freeze pre-update mass",
                        )
            frozen_masses = {
                item["cell_id"]: cast(float, item["prior_mass"])
                for item in cells
            }
    likelihood_bounds = {
        item["cell_id"]: [1.0, 1.0] for item in cells
    }
    contribution_likelihoods: list[dict[str, Any]] = []
    for contribution in new_contributions:
        raw_likelihoods = contribution["values"].get("likelihoods")
        if (
            not isinstance(raw_likelihoods, Mapping)
            or set(raw_likelihoods) != identifiers
        ):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_EVIDENCE",
                "continuous contribution requires likelihoods for every cell",
            )
        normalized_likelihoods: dict[str, list[float]] = {}
        for cell_id in sorted(identifiers):
            raw_likelihood = raw_likelihoods[cell_id]
            if isinstance(raw_likelihood, list):
                if len(raw_likelihood) != 2:
                    raise FieldIntelligenceError(
                        "INVALID_PARAMETER_EVIDENCE",
                        "continuous likelihood enclosure is invalid",
                    )
                lower = _finite(
                    raw_likelihood[0],
                    f"continuous cell {cell_id} likelihood lower bound",
                )
                upper = _finite(
                    raw_likelihood[1],
                    f"continuous cell {cell_id} likelihood upper bound",
                )
            else:
                lower = upper = _finite(
                    raw_likelihood,
                    f"continuous cell {cell_id} likelihood",
                )
            if lower < 0.0 or upper < lower:
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_EVIDENCE",
                    "continuous likelihood bounds are invalid",
                )
            prior_bounds = likelihood_bounds[cell_id]
            likelihood_bounds[cell_id] = [
                prior_bounds[0] * lower,
                prior_bounds[1] * upper,
            ]
            normalized_likelihoods[cell_id] = [lower, upper]
        contribution_likelihoods.append(
            {
                "contribution_id": contribution["contribution_id"],
                "likelihood_bounds": normalized_likelihoods,
            }
        )
    if semantics == "probability-measure":
        unnormalized = {
            cell_id: [
                frozen_masses[cell_id] * bounds[0],
                frozen_masses[cell_id] * bounds[1],
            ]
            for cell_id, bounds in likelihood_bounds.items()
        }
        total_upper = sum(bounds[1] for bounds in unnormalized.values())
        contradiction = total_upper == 0.0
        posterior_bounds: dict[str, list[float]] = {}
        posterior: dict[str, float] = {}
        if not contradiction:
            exact = all(
                bounds[0] == bounds[1] for bounds in unnormalized.values()
            )
            if exact:
                denominator = sum(
                    bounds[0] for bounds in unnormalized.values()
                )
                posterior = {
                    cell_id: bounds[0] / denominator
                    for cell_id, bounds in unnormalized.items()
                }
                posterior_bounds = {
                    cell_id: [mass, mass]
                    for cell_id, mass in posterior.items()
                }
            else:
                for cell_id, bounds in unnormalized.items():
                    other_upper = sum(
                        candidate[1]
                        for other_id, candidate in unnormalized.items()
                        if other_id != cell_id
                    )
                    other_lower = sum(
                        candidate[0]
                        for other_id, candidate in unnormalized.items()
                        if other_id != cell_id
                    )
                    lower_denominator = bounds[0] + other_upper
                    upper_denominator = bounds[1] + other_lower
                    posterior_bounds[cell_id] = [
                        (
                            0.0
                            if lower_denominator == 0.0
                            else bounds[0] / lower_denominator
                        ),
                        (
                            1.0
                            if upper_denominator == 0.0
                            else bounds[1] / upper_denominator
                        ),
                    ]
        else:
            posterior_bounds = {}
            posterior = {}
    else:
        contradiction = all(
            bounds[1] == 0.0 for bounds in likelihood_bounds.values()
        )
        posterior_bounds = {}
        posterior = {}
    result_cells = [
        {
            **item,
            "likelihood_bounds": likelihood_bounds[item["cell_id"]],
            "mass": (
                posterior.get(item["cell_id"])
                if semantics == "probability-measure"
                else None
            ),
            "mass_bounds": (
                posterior_bounds.get(item["cell_id"])
                if semantics == "probability-measure"
                else None
            ),
        }
        for item in cells
    ]
    interval_uncertainty = any(
        bounds[0] != bounds[1] for bounds in likelihood_bounds.values()
    )
    ordering = "exact"
    if interval_uncertainty and not contradiction:
        ordering = "unresolved"
        exact_winner = any(
            all(
                posterior_bounds[cell_id][0]
                > posterior_bounds[other_id][1]
                for other_id in identifiers
                if other_id != cell_id
            )
            for cell_id in identifiers
        )
        if exact_winner:
            ordering = "partially-ordered"
    return {
        "cells": result_cells,
        "computational_uncertainty": (
            ["likelihood-enclosure"] if interval_uncertainty else []
        ),
        "contradiction": contradiction,
        "contribution_likelihoods": (
            (
                []
                if prior is None
                else list(
                    prior["state"].get("contribution_likelihoods", [])
                )
            )
            + contribution_likelihoods
        ),
        "frozen_preupdate_mass": frozen_masses,
        "integration": integration,
        "ordering": ordering,
        "semantics": semantics,
        "variables": variables,
    }


def _semantic_analytic_parameter_state(
    request: Mapping[str, Any],
    prior: Mapping[str, Any] | None,
    all_contributions: Sequence[Mapping[str, Any]],
    new_contributions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    raw_rule = request.get("analytic_rule")
    if (
        not isinstance(raw_rule, Mapping)
        or not isinstance(raw_rule.get("assumptions"), list)
        or not isinstance(raw_rule.get("prior"), Mapping)
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "analytic local update requires a family, assumptions, and prior",
        )
    family = raw_rule.get("family")
    family_keys = {
        "beta-bernoulli": {
            "assumptions",
            "family",
            "outcome_key",
            "prior",
        },
        "normal-mean-known-variance": {
            "assumptions",
            "family",
            "observation_variance",
            "prior",
            "value_key",
        },
        "normal-linear-through-origin-known-variance": {
            "assumptions",
            "family",
            "input_key",
            "observation_variance",
            "output_key",
            "prior",
        },
    }
    required_assumptions = {
        "beta-bernoulli": {"conditionally-independent-bernoulli"},
        "normal-mean-known-variance": {
            "conditionally-independent-normal-noise",
            "known-observation-variance",
        },
        "normal-linear-through-origin-known-variance": {
            "conditionally-independent-normal-noise",
            "known-observation-variance",
            "linear-through-origin",
        },
    }
    if family not in family_keys or set(raw_rule) != family_keys[family]:
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "analytic local update family or schema is unsupported",
        )
    assumptions = [
        _identifier(item, "analytic update assumption")
        for item in raw_rule["assumptions"]
    ]
    if not required_assumptions[family].issubset(assumptions):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "analytic update lacks its conditional assumptions",
        )
    raw_prior = raw_rule["prior"]
    if family == "beta-bernoulli":
        if set(raw_prior) != {"alpha", "beta"}:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "beta prior requires alpha and beta",
            )
        alpha = _finite(raw_prior["alpha"], "beta prior alpha")
        beta = _finite(raw_prior["beta"], "beta prior beta")
        if alpha <= 0.0 or beta <= 0.0:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "beta prior parameters must be positive",
            )
        initial_prior = {"alpha": alpha, "beta": beta}
        outcome_key = _identifier(
            raw_rule["outcome_key"], "Bernoulli outcome key"
        )
        rule = {
            "assumptions": assumptions,
            "family": family,
            "outcome_key": outcome_key,
            "prior": initial_prior,
        }
        successes = 0
        failures = 0
        for contribution in all_contributions:
            outcome = contribution["values"].get(outcome_key)
            if outcome not in {0, 1, False, True}:
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_EVIDENCE",
                    "Bernoulli contribution is not binary",
                )
            successes += int(bool(outcome))
            failures += int(not bool(outcome))
        posterior = {
            "alpha": alpha + successes,
            "beta": beta + failures,
            "mean": (alpha + successes)
            / (alpha + beta + successes + failures),
        }
        statistics = {
            "count": successes + failures,
            "failures": failures,
            "successes": successes,
        }
        identified = bool(all_contributions)
        limitations: list[str] = []
    else:
        if set(raw_prior) != {"mean", "variance"}:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "normal prior requires mean and variance",
            )
        prior_mean = _finite(raw_prior["mean"], "normal prior mean")
        prior_variance = _finite(
            raw_prior["variance"], "normal prior variance"
        )
        observation_variance = _finite(
            raw_rule["observation_variance"],
            "known observation variance",
        )
        if prior_variance <= 0.0 or observation_variance <= 0.0:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "normal variances must be positive",
            )
        initial_prior = {
            "mean": prior_mean,
            "variance": prior_variance,
        }
        if family == "normal-mean-known-variance":
            value_key = _identifier(
                raw_rule["value_key"], "normal observation key"
            )
            values: list[float] = []
            for contribution in all_contributions:
                raw_value = contribution["values"].get(value_key)
                values.append(
                    _finite(raw_value, "normal mean observation")
                )
            data_precision = len(values) / observation_variance
            weighted_data = sum(values) / observation_variance
            statistics = {
                "count": len(values),
                "sum": sum(values),
                "sum_squares": sum(value * value for value in values),
            }
            rule = {
                "assumptions": assumptions,
                "family": family,
                "observation_variance": observation_variance,
                "prior": initial_prior,
                "value_key": value_key,
            }
            identified = bool(values)
            limitations = []
        else:
            input_key = _identifier(
                raw_rule["input_key"], "linear update input key"
            )
            output_key = _identifier(
                raw_rule["output_key"], "linear update output key"
            )
            sum_xx = 0.0
            sum_xy = 0.0
            sum_yy = 0.0
            for contribution in all_contributions:
                x = _finite(
                    contribution["values"].get(input_key),
                    "linear update input",
                )
                y = _finite(
                    contribution["values"].get(output_key),
                    "linear update output",
                )
                sum_xx += x * x
                sum_xy += x * y
                sum_yy += y * y
            data_precision = sum_xx / observation_variance
            weighted_data = sum_xy / observation_variance
            statistics = {
                "count": len(all_contributions),
                "sum_xx": sum_xx,
                "sum_xy": sum_xy,
                "sum_yy": sum_yy,
            }
            rule = {
                "assumptions": assumptions,
                "family": family,
                "input_key": input_key,
                "observation_variance": observation_variance,
                "output_key": output_key,
                "prior": initial_prior,
            }
            identified = sum_xx > 1.0e-15
            limitations = [] if identified else ["insufficient-excitation"]
        posterior_precision = 1.0 / prior_variance + data_precision
        posterior_variance = 1.0 / posterior_precision
        posterior = {
            "mean": posterior_variance
            * (prior_mean / prior_variance + weighted_data),
            "variance": posterior_variance,
        }
    if prior is not None:
        prior_state = prior["state"]
        if prior_state.get("update_rule") != rule:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "analytic update rule changed across parameter updates",
            )
        frozen_preupdate = prior_state["posterior"]
    else:
        frozen_preupdate = initial_prior
    return {
        "frozen_preupdate": frozen_preupdate,
        "identified": identified,
        "limitations": limitations,
        "posterior": posterior,
        "statistics": statistics,
        "update_rule": rule,
    }


def _semantic_likelihood_bounds(value: Any, label: str) -> list[float]:
    if isinstance(value, list):
        if len(value) != 2:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_EVIDENCE",
                f"{label} enclosure is invalid",
            )
        lower = _finite(value[0], f"{label} lower bound")
        upper = _finite(value[1], f"{label} upper bound")
    else:
        lower = upper = _finite(value, label)
    if lower < 0.0 or upper < lower:
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_EVIDENCE",
            f"{label} must be a nonnegative ordered enclosure",
        )
    return [lower, upper]


def _semantic_candidate_family_update(
    state: Mapping[str, Any],
    request: Mapping[str, Any],
    prior_family: Mapping[str, Any] | None,
    all_contributions: Sequence[Mapping[str, Any]],
    new_contributions: Sequence[Mapping[str, Any]],
    evidence_prefix: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    raw_family = request.get("family_update")
    if raw_family is None:
        return (
            None
            if prior_family is None
            else _regional_plain(dict(prior_family), "prior candidate family")
        )
    allowed = {
        "activation_basis",
        "activation_mass",
        "activation_transition",
        "candidate_family_version",
        "candidates",
        "previous_family_version",
        "probability_model",
        "reconstruction",
        "update_semantics",
    }
    required = {
        "activation_transition",
        "candidate_family_version",
        "candidates",
        "probability_model",
        "update_semantics",
    }
    if (
        not isinstance(raw_family, Mapping)
        or set(raw_family) - allowed
        or not required.issubset(raw_family)
        or not isinstance(raw_family["candidates"], list)
        or not raw_family["candidates"]
        or len(raw_family["candidates"])
        > state["bounds"]["max_alternatives"]
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "candidate family update is invalid",
        )
    family_version = _identifier(
        raw_family["candidate_family_version"],
        "candidate family version",
    )
    activation_transition = _regional_integer(
        raw_family["activation_transition"],
        "candidate family activation transition",
        maximum=state["bounds"]["max_operations"],
    )
    semantics = raw_family["update_semantics"]
    if semantics not in {
        "fixed-family",
        "prospective-activation",
        "retrospective-reconstruction",
        "unweighted-expansion",
    }:
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "candidate family update semantics are unsupported",
        )
    probability_model = (
        None
        if semantics == "unweighted-expansion"
        else _semantic_probability_model(
            raw_family["probability_model"],
            "candidate family probability model",
        )
    )
    if (
        semantics == "unweighted-expansion"
        and raw_family["probability_model"] is not None
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "unweighted expansion cannot carry posterior probability metadata",
        )
    candidate_rows: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()
    for index, raw_candidate in enumerate(raw_family["candidates"]):
        expected_keys = (
            {"candidate_id"}
            if semantics == "unweighted-expansion"
            else {"candidate_id", "prior_mass"}
        )
        if (
            not isinstance(raw_candidate, Mapping)
            or set(raw_candidate) != expected_keys
        ):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                f"candidate family row {index} is invalid",
            )
        candidate_id = _identifier(
            raw_candidate["candidate_id"],
            f"candidate family row {index} identity",
        )
        if candidate_id in candidate_ids:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "candidate family identity is duplicated",
            )
        candidate_ids.add(candidate_id)
        candidate_rows.append(
            {
                "candidate_id": candidate_id,
                "prior_mass": (
                    None
                    if semantics == "unweighted-expansion"
                    else _finite(
                        raw_candidate["prior_mass"],
                        f"candidate {candidate_id} prior mass",
                    )
                ),
            }
        )
    candidate_rows.sort(key=lambda item: item["candidate_id"])
    if semantics != "unweighted-expansion":
        if any(
            cast(float, item["prior_mass"]) < 0.0
            for item in candidate_rows
        ) or abs(
            sum(cast(float, item["prior_mass"]) for item in candidate_rows)
            - 1.0
        ) > 1.0e-9:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "candidate family prior mass is not normalized",
            )
    prior_version = (
        None
        if prior_family is None
        else prior_family["candidate_family_version"]
    )
    declared_previous = raw_family.get("previous_family_version")
    same_version = prior_version == family_version
    activation_record: dict[str, Any] | None = None
    if same_version:
        if semantics != "fixed-family":
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "an activated candidate family can only receive fixed-family updates",
            )
        if declared_previous not in {None, prior_version}:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "candidate family predecessor changed",
            )
        previous_rows = {
            item["candidate_id"]: item
            for item in prior_family["candidates"]
        }
        if set(previous_rows) != candidate_ids:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "fixed candidate family membership changed",
            )
        if (
            prior_family["activation_transition"] != activation_transition
            or prior_family["probability_model"] != probability_model
        ):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "fixed candidate family metadata changed",
            )
        for item in candidate_rows:
            current_mass = previous_rows[item["candidate_id"]].get("mass")
            if current_mass is None or abs(
                cast(float, item["prior_mass"]) - float(current_mass)
            ) > 1.0e-9:
                raise FieldIntelligenceError(
                    "OPERATION_CONFLICT",
                    "candidate update did not freeze pre-update model mass",
                )
    elif prior_family is not None:
        if declared_previous != prior_version:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "new candidate family does not name the current predecessor",
            )
        if semantics == "fixed-family":
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "candidate addition requires declared family-expansion semantics",
            )
        if activation_transition != int(state["ledger"]["transitions"]) + 1:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "new candidate family activation is not this transition",
            )
        prior_ids = {
            item["candidate_id"] for item in prior_family["candidates"]
        }
        added_ids = candidate_ids - prior_ids
        if semantics in {
            "prospective-activation",
            "unweighted-expansion",
        } and (not prior_ids < candidate_ids):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "family expansion must retain incumbents and add a candidate",
            )
        if semantics == "prospective-activation":
            if (
                len(added_ids) != 1
                or not isinstance(raw_family.get("activation_basis"), Mapping)
                or not raw_family["activation_basis"]
                or "activation_mass" not in raw_family
                or prior_family.get("ordering") != "exact"
                or prior_family.get("probability_model")
                != probability_model
            ):
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_UPDATE",
                    "prospective activation requires one candidate, a justified mass, and an exact incumbent posterior",
                )
            activation_mass = _finite(
                raw_family["activation_mass"],
                "prospective candidate activation mass",
            )
            if not 0.0 < activation_mass < 1.0:
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_UPDATE",
                    "prospective activation mass must lie strictly between zero and one",
                )
            prior_masses = {
                item["candidate_id"]: item.get("mass")
                for item in prior_family["candidates"]
            }
            if any(value is None for value in prior_masses.values()):
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_UPDATE",
                    "prospective activation requires calibrated incumbent masses",
                )
            proposed_masses = {
                item["candidate_id"]: cast(float, item["prior_mass"])
                for item in candidate_rows
            }
            added_id = next(iter(added_ids))
            expected_masses = {
                candidate_id: float(mass) * (1.0 - activation_mass)
                for candidate_id, mass in prior_masses.items()
            }
            expected_masses[added_id] = activation_mass
            if any(
                abs(proposed_masses[candidate_id] - expected) > 1.0e-9
                for candidate_id, expected in expected_masses.items()
            ):
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_UPDATE",
                    "prospective family prior does not apply the declared activation mass",
                )
            activation_record = {
                "basis": _regional_plain(
                    dict(raw_family["activation_basis"]),
                    "prospective activation basis",
                ),
                "evidence_count_before_activation": (
                    len(all_contributions) - len(new_contributions)
                ),
                "mass": activation_mass,
                "new_candidate_id": added_id,
            }
        elif (
            "activation_mass" in raw_family
            or "activation_basis" in raw_family
        ):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "only prospective activation accepts activation mass metadata",
            )
    elif declared_previous is not None:
        raise FieldIntelligenceError(
            "OPERATION_CONFLICT",
            "initial candidate family cannot name a predecessor",
        )
    elif semantics in {
        "prospective-activation",
        "retrospective-reconstruction",
        "unweighted-expansion",
    }:
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "initial candidate family must use fixed-family semantics",
        )
    if same_version:
        activation_record = cast(
            Any, prior_family.get("activation")
        )
    elif semantics != "prospective-activation" and (
        "activation_mass" in raw_family
        or "activation_basis" in raw_family
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "only prospective activation accepts activation mass metadata",
        )
    if semantics == "retrospective-reconstruction":
        reconstruction = raw_family.get("reconstruction")
        if (
            not isinstance(reconstruction, Mapping)
            or set(reconstruction)
            != {
                "common_initialization",
                "complete_online_rules",
                "historical_likelihoods",
            }
            or reconstruction["complete_online_rules"] is not True
            or not isinstance(reconstruction["common_initialization"], Mapping)
            or not isinstance(reconstruction["historical_likelihoods"], Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "retrospective reconstruction lacks complete common rules",
            )
        historical_scores = reconstruction["historical_likelihoods"]
        if set(historical_scores) != {
            item["contribution_id"] for item in all_contributions
        }:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_EVIDENCE",
                "retrospective reconstruction does not replay every contribution once",
            )
        scored_contributions = [
            {
                **dict(item),
                "values": {
                    **dict(item["values"]),
                    "candidate_likelihoods": historical_scores[
                        item["contribution_id"]
                    ],
                },
            }
            for item in all_contributions
        ]
        reconstruction_record = {
            "common_initialization": _regional_plain(
                dict(reconstruction["common_initialization"]),
                "candidate reconstruction initialization",
            ),
            "complete_online_rules": True,
        }
    else:
        if raw_family.get("reconstruction") is not None:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_UPDATE",
                "only retrospective reconstruction accepts replay metadata",
            )
        scored_contributions = list(new_contributions)
        reconstruction_record = None
    if semantics == "unweighted-expansion":
        prior_compatibility = (
            {}
            if prior_family is None
            else {
                item["candidate_id"]: bool(item.get("compatible", True))
                for item in prior_family["candidates"]
            }
        )
        compatibility = {
            candidate_id: prior_compatibility.get(candidate_id, True)
            for candidate_id in candidate_ids
        }
        contribution_scores = []
        for contribution in scored_contributions:
            raw_compatibility = contribution["values"].get(
                "candidate_compatibility"
            )
            if (
                not isinstance(raw_compatibility, Mapping)
                or set(raw_compatibility) != candidate_ids
                or any(
                    not isinstance(value, bool)
                    for value in raw_compatibility.values()
                )
            ):
                raise FieldIntelligenceError(
                    "INVALID_PARAMETER_EVIDENCE",
                    "unweighted family contribution requires Boolean compatibility",
                )
            for candidate_id, accepted in raw_compatibility.items():
                compatibility[candidate_id] &= accepted
            contribution_scores.append(
                {
                    "candidate_compatibility": dict(raw_compatibility),
                    "contribution_id": contribution["contribution_id"],
                }
            )
        contradiction = not any(compatibility.values())
        return {
            "activation": activation_record,
            "activation_transition": activation_transition,
            "candidate_family_version": family_version,
            "candidates": [
                {
                    **item,
                    "compatible": compatibility[item["candidate_id"]],
                    "mass": None,
                    "mass_bounds": None,
                }
                for item in candidate_rows
            ],
            "contradiction": contradiction,
            "contribution_scores": contribution_scores,
            "evidence_prefix": list(evidence_prefix),
            "ordering": "set-valued",
            "previous_family_version": prior_version,
            "probability_model": None,
            "reconstruction": reconstruction_record,
            "update_semantics": semantics,
        }
    likelihood_bounds = {
        candidate_id: [1.0, 1.0] for candidate_id in candidate_ids
    }
    contribution_scores = []
    for contribution in scored_contributions:
        raw_likelihoods = contribution["values"].get(
            "candidate_likelihoods"
        )
        if (
            not isinstance(raw_likelihoods, Mapping)
            or set(raw_likelihoods) != candidate_ids
        ):
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_EVIDENCE",
                "candidate update requires one likelihood per model",
            )
        normalized = {}
        for candidate_id in sorted(candidate_ids):
            bounds = _semantic_likelihood_bounds(
                raw_likelihoods[candidate_id],
                f"candidate {candidate_id} marginal likelihood",
            )
            prior_bounds = likelihood_bounds[candidate_id]
            likelihood_bounds[candidate_id] = [
                prior_bounds[0] * bounds[0],
                prior_bounds[1] * bounds[1],
            ]
            normalized[candidate_id] = bounds
        contribution_scores.append(
            {
                "contribution_id": contribution["contribution_id"],
                "likelihood_bounds": normalized,
            }
        )
    frozen_prior = {
        item["candidate_id"]: cast(float, item["prior_mass"])
        for item in candidate_rows
    }
    unnormalized = {
        candidate_id: [
            frozen_prior[candidate_id] * likelihood_bounds[candidate_id][0],
            frozen_prior[candidate_id] * likelihood_bounds[candidate_id][1],
        ]
        for candidate_id in sorted(candidate_ids)
    }
    contradiction = sum(bounds[1] for bounds in unnormalized.values()) == 0.0
    exact = all(bounds[0] == bounds[1] for bounds in unnormalized.values())
    posterior: dict[str, float] = {}
    posterior_bounds: dict[str, list[float]] = {}
    if not contradiction and exact:
        denominator = sum(bounds[0] for bounds in unnormalized.values())
        if not math.isfinite(denominator) or denominator <= 0.0:
            raise FieldIntelligenceError(
                "INVALID_PARAMETER_EVIDENCE",
                "candidate posterior normalizer is nonfinite",
            )
        posterior = {
            candidate_id: bounds[0] / denominator
            for candidate_id, bounds in unnormalized.items()
        }
        posterior_bounds = {
            candidate_id: [mass, mass]
            for candidate_id, mass in posterior.items()
        }
        ordering = "exact"
    elif not contradiction:
        for candidate_id, bounds in unnormalized.items():
            other_upper = sum(
                item[1]
                for other_id, item in unnormalized.items()
                if other_id != candidate_id
            )
            other_lower = sum(
                item[0]
                for other_id, item in unnormalized.items()
                if other_id != candidate_id
            )
            posterior_bounds[candidate_id] = [
                (
                    0.0
                    if bounds[0] + other_upper == 0.0
                    else bounds[0] / (bounds[0] + other_upper)
                ),
                (
                    1.0
                    if bounds[1] + other_lower == 0.0
                    else bounds[1] / (bounds[1] + other_lower)
                ),
            ]
        ordering = "unresolved-numerical-enclosure"
    else:
        ordering = "contradiction"
    return {
        "activation": activation_record,
        "activation_transition": activation_transition,
        "candidate_family_version": family_version,
        "candidates": [
            {
                **item,
                "likelihood_bounds": likelihood_bounds[item["candidate_id"]],
                "mass": posterior.get(item["candidate_id"]),
                "mass_bounds": posterior_bounds.get(item["candidate_id"]),
            }
            for item in candidate_rows
        ],
        "contradiction": contradiction,
        "contribution_scores": contribution_scores,
        "evidence_prefix": list(evidence_prefix),
        "frozen_preupdate_mass": frozen_prior,
        "ordering": ordering,
        "previous_family_version": prior_version,
        "probability_model": probability_model,
        "reconstruction": reconstruction_record,
        "update_semantics": semantics,
    }


def _semantic_validate_parameter_learning(
    value: Any, record: Mapping[str, Any]
) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value) != {"schema", "sets"}
        or value.get("schema") != PARAMETER_LEARNING_SCHEMA
        or not isinstance(value.get("sets"), Mapping)
    ):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_STATE",
            "semantic parameter-learning payload is invalid",
        )
    normalized_sets: dict[str, Any] = {}
    dependency_keys = {
        (
            item["kind"],
            item["id"],
            int(item["content_version"]),
        )
        for item in record["dependencies"]
    }
    for raw_identity, raw_set in value["sets"].items():
        identity = _identifier(
            raw_identity, "semantic parameter-set identity"
        )
        if (
            not isinstance(raw_set, Mapping)
            or set(raw_set)
            != {
                "candidate_family",
                "contributions",
                "evidence_prefix",
                "parameter_path",
                "parameter_set_id",
                "state",
            }
            or raw_set["parameter_set_id"] != identity
            or raw_set["parameter_path"] not in PARAMETER_PATHS
            or not isinstance(raw_set["contributions"], list)
            or not isinstance(raw_set["evidence_prefix"], list)
            or not isinstance(raw_set["state"], Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic parameter set is invalid",
            )
        contributions = []
        evidence = []
        contribution_ids: set[str] = set()
        for raw_contribution in raw_set["contributions"]:
            if (
                not isinstance(raw_contribution, Mapping)
                or set(raw_contribution)
                != {
                    "contribution_id",
                    "contribution_sha256",
                    "evidence",
                    "values",
                }
                or not isinstance(raw_contribution["values"], Mapping)
            ):
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "semantic parameter contribution is invalid",
                )
            contribution_id = _identifier(
                raw_contribution["contribution_id"],
                "semantic parameter contribution identity",
            )
            if contribution_id in contribution_ids:
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "semantic parameter contribution is duplicated",
                )
            contribution_ids.add(contribution_id)
            try:
                evidence_ref = SemanticRef.from_dict(
                    raw_contribution["evidence"]
                ).as_dict()
            except RegionalFieldError as exc:
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "semantic parameter evidence reference is invalid",
                ) from exc
            if evidence_ref["kind"] != "Event":
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "semantic parameter evidence is not an Event",
                )
            body = {
                "contribution_id": contribution_id,
                "evidence": evidence_ref,
                "values": _regional_plain(
                    dict(raw_contribution["values"]),
                    "semantic parameter contribution values",
                ),
            }
            if raw_contribution["contribution_sha256"] != sha256_value(body):
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "semantic parameter contribution digest diverges",
                )
            key = (
                evidence_ref["kind"],
                evidence_ref["id"],
                int(evidence_ref["content_version"]),
            )
            if key not in dependency_keys:
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "semantic parameter evidence is outside dependencies",
                )
            contributions.append(
                {
                    **body,
                    "contribution_sha256": raw_contribution[
                        "contribution_sha256"
                    ],
                }
            )
            evidence.append(evidence_ref)
        if raw_set["evidence_prefix"] != evidence:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "semantic parameter evidence prefix diverges from lineage",
            )
        candidate_family = raw_set["candidate_family"]
        if candidate_family is not None:
            if (
                not isinstance(candidate_family, Mapping)
                or not {
                    "activation_transition",
                    "candidate_family_version",
                    "candidates",
                    "contradiction",
                    "evidence_prefix",
                    "ordering",
                    "previous_family_version",
                    "probability_model",
                    "update_semantics",
                }.issubset(candidate_family)
                or not isinstance(candidate_family["evidence_prefix"], list)
                or list(candidate_family["evidence_prefix"])
                != evidence[: len(candidate_family["evidence_prefix"])]
                or not isinstance(candidate_family["candidates"], list)
                or not isinstance(candidate_family["contradiction"], bool)
            ):
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "semantic candidate family is invalid",
                )
            _identifier(
                candidate_family["candidate_family_version"],
                "semantic candidate family version",
            )
        normalized_sets[identity] = {
            "candidate_family": _regional_plain(
                candidate_family, "semantic candidate family"
            ),
            "contributions": contributions,
            "evidence_prefix": evidence,
            "parameter_path": raw_set["parameter_path"],
            "parameter_set_id": identity,
            "state": _regional_plain(
                dict(raw_set["state"]), "semantic parameter state"
            ),
        }
    return {"schema": PARAMETER_LEARNING_SCHEMA, "sets": normalized_sets}


def _semantic_learn_parameters(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=(
            "contributions",
            "evidence_prefix",
            "mechanism_id",
            "parameter_path",
            "parameter_set_id",
        ),
        optional=(
            "alternative_semantics",
            "alternatives",
            "analytic_rule",
            "cell_semantics",
            "cells",
            "design_variables",
            "family_update",
            "frontier",
            "integration",
            "interpretation",
            "support_roots",
            "target_variables",
            "variables",
        ),
    )
    mechanism_id = _identifier(
        request["mechanism_id"], "parameter mechanism identity"
    )
    parameter_set_id = _identifier(
        request["parameter_set_id"], "parameter set identity"
    )
    parameter_path = request["parameter_path"]
    if parameter_path not in PARAMETER_PATHS:
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "parameter path is unsupported",
        )
    mechanism, _ = _semantic_program_record(state, mechanism_id)
    if (
        mechanism["status"] != "active"
        or mechanism["payload"].get("program_role") != "mechanism"
    ):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "parameter learning requires an active mechanism Program",
        )
    raw_learning = mechanism["payload"].get("parameter_learning")
    if raw_learning is None:
        learning = {"schema": PARAMETER_LEARNING_SCHEMA, "sets": {}}
    else:
        learning = _semantic_validate_parameter_learning(
            raw_learning, mechanism
        )
    prior_set = learning["sets"].get(parameter_set_id)
    if (
        prior_set is not None
        and prior_set["parameter_path"] != parameter_path
    ):
        raise FieldIntelligenceError(
            "OPERATION_CONFLICT",
            "parameter set cannot change its update path",
        )
    evidence_prefix, evidence_dependencies = _semantic_parameter_prefix(
        state, request["evidence_prefix"]
    )
    contributions = _semantic_parameter_contributions(
        state, request["contributions"], evidence_prefix
    )
    activation_only = (
        prior_set is not None
        and not contributions
        and isinstance(request.get("family_update"), Mapping)
        and request["family_update"].get("update_semantics")
        == "prospective-activation"
        and evidence_prefix == prior_set["evidence_prefix"]
    )
    if not contributions and not activation_only:
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_EVIDENCE",
            "empty parameter contributions are reserved for prospective family activation",
        )
    all_contributions, new_contributions = (
        _semantic_parameter_new_contributions(
            prior_set,
            evidence_prefix,
            contributions,
        )
    )
    if parameter_path == "observed-sufficient-statistics":
        parameter_state = _semantic_parameter_statistics(
            request,
            prior_set,
            all_contributions,
            new_contributions,
        )
    elif parameter_path == "finite-alternatives":
        parameter_state = _semantic_finite_parameter_state(
            state,
            request,
            prior_set,
            new_contributions,
        )
    elif parameter_path == "continuous-cells":
        parameter_state = _semantic_continuous_parameter_state(
            state,
            request,
            prior_set,
            new_contributions,
        )
    else:
        parameter_state = _semantic_analytic_parameter_state(
            request,
            prior_set,
            all_contributions,
            new_contributions,
        )
    candidate_family = _semantic_candidate_family_update(
        state,
        request,
        (
            None
            if prior_set is None
            else prior_set.get("candidate_family")
        ),
        all_contributions,
        new_contributions,
        evidence_prefix,
    )
    structural_change = prior_set is None
    if prior_set is not None and parameter_path == "finite-alternatives":
        stable_keys = (
            "alternative_id",
            "constraints",
            "latent",
            "parameters",
        )
        structural_change = [
            {name: row[name] for name in stable_keys}
            for row in parameter_state["alternatives"]
        ] != [
            {name: row[name] for name in stable_keys}
            for row in prior_set["state"]["alternatives"]
        ] or parameter_state["frontier"] != prior_set["state"]["frontier"]
    elif prior_set is not None and parameter_path == "continuous-cells":
        structural_change = [
            {"bounds": row["bounds"], "cell_id": row["cell_id"]}
            for row in parameter_state["cells"]
        ] != [
            {"bounds": row["bounds"], "cell_id": row["cell_id"]}
            for row in prior_set["state"]["cells"]
        ]
    if prior_set is not None:
        prior_family = prior_set.get("candidate_family")
        structural_change = structural_change or (
            (None if prior_family is None else prior_family[
                "candidate_family_version"
            ])
            != (
                None if candidate_family is None else candidate_family[
                    "candidate_family_version"
                ]
            )
        )
    if (
        prior_set is not None
        and not new_contributions
        and not structural_change
    ):
        return _semantic_result(
            "learn-parameters",
            "supported",
            assessment=None,
            candidate_family=prior_set["candidate_family"],
            invalidation_frontier=[],
            limitations=prior_set["state"].get("limitations", []),
            mechanism=semantic_record_ref(mechanism).as_dict(),
            parameter_set=prior_set,
            reused_evidence=True,
        ), 1
    parameter_set = {
        "candidate_family": candidate_family,
        "contributions": all_contributions,
        "evidence_prefix": evidence_prefix,
        "parameter_path": parameter_path,
        "parameter_set_id": parameter_set_id,
        "state": parameter_state,
    }
    if prior_set == parameter_set:
        return _semantic_result(
            "learn-parameters",
            "supported",
            assessment=None,
            candidate_family=candidate_family,
            invalidation_frontier=[],
            limitations=parameter_state.get("limitations", []),
            mechanism=semantic_record_ref(mechanism).as_dict(),
            parameter_set=parameter_set,
            reused_evidence=True,
        ), 1
    updated_learning = {
        "schema": PARAMETER_LEARNING_SCHEMA,
        "sets": {
            **learning["sets"],
            parameter_set_id: parameter_set,
        },
    }
    dependency_rows = {
        (
            item["kind"],
            item["id"],
            int(item["content_version"]),
        ): dict(item)
        for item in (*mechanism["dependencies"], *evidence_dependencies)
    }
    support_roots = set(mechanism["support_roots"])
    for event_ref in evidence_dependencies:
        _, event = _semantic_reference(state, event_ref)
        support_roots.update(event["support_roots"])
    raw_support_roots = request.get("support_roots", [])
    if not isinstance(raw_support_roots, list):
        raise FieldIntelligenceError(
            "INVALID_PARAMETER_UPDATE",
            "parameter support roots must be a list",
        )
    support_roots.update(
        _identifier(item, "parameter support root")
        for item in raw_support_roots
    )
    prior_ref = semantic_record_ref(mechanism).as_dict()
    mechanism_ref = _semantic_append_record(
        state,
        record_id=mechanism_id,
        kind="Program",
        payload={
            **mechanism["payload"],
            "parameter_learning": updated_learning,
        },
        status="active",
        epistemic_kind="induced",
        dependencies=tuple(
            dependency_rows[key] for key in sorted(dependency_rows)
        ),
        support_roots=sorted(support_roots),
        derivation={
            **mechanism["derivation"],
            "parameter_path": parameter_path,
            "parameter_set_id": parameter_set_id,
            "parameter_update_operation": request.get("operation_id"),
        },
        applicability=mechanism["applicability"],
        valid_time=mechanism["valid_time"],
        frame=mechanism["frame"],
        units=mechanism["units"],
        scope=mechanism["scope"],
    )
    contradiction = bool(parameter_state.get("contradiction")) or bool(
        candidate_family is not None
        and candidate_family.get("contradiction")
    )
    assessment_id = (
        f"assessment:parameters:{mechanism_id}:{parameter_set_id}:"
        f"{mechanism_ref['content_version']}"
    )
    assessment_ref = _semantic_append_record(
        state,
        record_id=assessment_id,
        kind="Assessment",
        payload={
            "candidate_family": candidate_family,
            "contradiction": contradiction,
            "evidence_prefix": evidence_prefix,
            "frozen_preupdate": (
                None if prior_set is None else prior_set["state"]
            ),
            "parameter_path": parameter_path,
            "parameter_set": mechanism_ref,
            "postupdate": parameter_state,
            "purpose": "parameter-update",
        },
        status="active",
        epistemic_kind="derived",
        dependencies=(mechanism_ref, *evidence_dependencies),
        support_roots=sorted(support_roots),
        derivation={
            "assessment_boundary": "frozen-before-parameter-update",
            "operation_id": request.get("operation_id"),
        },
    )
    frontier = _semantic_invalidate(
        state, (prior_ref,), reason="parameter-state-updated"
    )
    _semantic_reindex_record(state, mechanism_ref)
    obligation_ref: dict[str, Any] | None = None
    if contradiction:
        obligation_ref = _semantic_append_record(
            state,
            record_id=(
                f"obligation:parameters:{mechanism_id}:"
                f"{parameter_set_id}:{mechanism_ref['content_version']}"
            ),
            kind="Obligation",
            payload={
                "candidate_family": candidate_family,
                "evidence_prefix": evidence_prefix,
                "parameter_set": mechanism_ref,
                "purpose": "model-inadequacy",
                "reason": "all-exact-support-zero",
                "state": "pending",
            },
            epistemic_kind="derived",
            dependencies=(mechanism_ref, assessment_ref),
            support_roots=sorted(support_roots),
        )
        _semantic_reindex_record(state, obligation_ref)
    limitations = list(parameter_state.get("limitations", []))
    if candidate_family is not None and candidate_family.get(
        "ordering"
    ) == "unresolved-numerical-enclosure":
        limitations.append("candidate-ordering-unresolved-by-numerical-error")
    if contradiction:
        limitations.append("model-family-contradiction")
    return _semantic_result(
        "learn-parameters",
        "support-gap" if contradiction else "supported",
        assessment=assessment_ref,
        candidate_family=candidate_family,
        invalidation_frontier=frontier,
        limitations=sorted(set(limitations)),
        mechanism=mechanism_ref,
        model_inadequacy=obligation_ref,
        parameter_set=parameter_set,
        reused_evidence=False,
    ), max(
        1,
        len(new_contributions)
        + len(frontier)
        + 2
        + (1 if obligation_ref is not None else 0),
    )


def _semantic_learn_mechanism(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    operation = str(request["operation"])
    _semantic_keys(
        request,
        required=("episodes", "mechanism_id"),
        optional=(
            "candidates",
            "identification",
            "elapsed_key",
            "fired",
            "holdout",
            "output_key",
            "quiet",
            "reset_on",
            "support_roots",
        ),
    )
    mechanism_id = _identifier(
        request["mechanism_id"], "mechanism identity"
    )
    episodes = request["episodes"]
    holdout = request.get("holdout", [])
    if (
        not isinstance(episodes, list)
        or not episodes
        or not isinstance(holdout, list)
        or any(not isinstance(item, Mapping) for item in [*episodes, *holdout])
    ):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE",
            "mechanism evidence must be nonempty episode rows",
        )
    episodes = [
        _semantic_mechanism_episode(item, f"training episode {index}")
        for index, item in enumerate(episodes)
    ]
    holdout = [
        _semantic_mechanism_episode(item, f"holdout episode {index}")
        for index, item in enumerate(holdout)
    ]
    raw_candidates = request.get("candidates")
    candidates: list[dict[str, Any]] = []
    if raw_candidates is None:
        inferred = (
            _semantic_timer_candidate(request, episodes)
            if operation == "learn-hybrid"
            else _semantic_table_candidate(episodes)
        )
        candidates.append(
            {
                "candidate_id": "induced",
                "latent_prior": {},
                "observation_model": None,
                "probability_model": None,
                "parameter_domain": {},
                "program": inferred,
                "selection_assumptions": [],
                "update_rule": {},
            }
        )
    else:
        if (
            not isinstance(raw_candidates, list)
            or not raw_candidates
            or len(raw_candidates) > state["bounds"]["max_alternatives"]
        ):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_EVIDENCE",
                "candidate family is empty or exceeds its bound",
            )
        allowed_candidate_keys = {
            "candidate_id",
            "latent_prior",
            "observation_model",
            "parameter_domain",
            "probability_model",
            "program",
            "selection_assumptions",
            "update_rule",
        }
        for raw in raw_candidates:
            if (
                not isinstance(raw, Mapping)
                or set(raw) - allowed_candidate_keys
                or not {"candidate_id", "program"}.issubset(raw)
                or not isinstance(raw.get("program"), Mapping)
                or (
                    raw.get("observation_model") is not None
                    and not isinstance(raw.get("observation_model"), Mapping)
                )
                or not isinstance(raw.get("parameter_domain", {}), Mapping)
                or not isinstance(raw.get("latent_prior", {}), Mapping)
                or (
                    raw.get("probability_model") is not None
                    and not isinstance(raw.get("probability_model"), Mapping)
                )
                or not isinstance(raw.get("selection_assumptions", []), list)
                or not isinstance(raw.get("update_rule", {}), Mapping)
            ):
                raise FieldIntelligenceError(
                    "INVALID_MECHANISM_EVIDENCE",
                    "mechanism candidate is invalid",
                )
            candidate_id = _identifier(
                raw["candidate_id"], "mechanism candidate identity"
            )
            assumptions = [
                _identifier(item, "mechanism selection assumption")
                for item in raw.get("selection_assumptions", [])
            ]
            latent_prior = {
                _identifier(name, "latent prior state"): _finite(
                    weight, "latent prior weight"
                )
                for name, weight in raw.get("latent_prior", {}).items()
            }
            if latent_prior and (
                any(weight < 0.0 for weight in latent_prior.values())
                or abs(sum(latent_prior.values()) - 1.0) > 1.0e-9
            ):
                raise FieldIntelligenceError(
                    "INVALID_MECHANISM_EVIDENCE",
                    "latent prior weights are not nonnegative and normalized",
                )
            candidate_program = _canonical_mechanism_program(
                cast(Mapping[str, Any], raw["program"])
            )
            if latent_prior:
                candidate_body = candidate_program["body"]
                if (
                    candidate_program["program_kind"] != "hybrid"
                    or not isinstance(candidate_body.get("modes"), Mapping)
                    or set(candidate_body["modes"]) != set(latent_prior)
                ):
                    raise FieldIntelligenceError(
                        "INVALID_MECHANISM_EVIDENCE",
                        "latent prior does not cover a hybrid mode family",
                    )
                declared_weights = candidate_body.get("mode_weights")
                if declared_weights is not None and (
                    not isinstance(declared_weights, Mapping)
                    or dict(declared_weights) != latent_prior
                ):
                    raise FieldIntelligenceError(
                        "INVALID_MECHANISM_EVIDENCE",
                        "latent prior conflicts with program mode weights",
                    )
                candidate_program = _canonical_mechanism_program(
                    {
                        **candidate_program,
                        "body": {
                            **candidate_body,
                            "mode_weights": latent_prior,
                        },
                    }
                )
            raw_observation_model = raw.get("observation_model")
            observation_model = (
                None
                if raw_observation_model is None
                else _canonical_mechanism_program(
                    cast(Mapping[str, Any], raw_observation_model)
                )
            )
            raw_probability_model = raw.get("probability_model")
            probability_model = (
                None
                if raw_probability_model is None
                else _semantic_probability_model(
                    raw_probability_model,
                    "mechanism candidate probability model",
                )
            )
            if (
                bool(latent_prior)
                or _semantic_program_has_probability(candidate_program)
                or _semantic_program_has_probability(observation_model)
            ) and probability_model is None:
                raise FieldIntelligenceError(
                    "INVALID_PROBABILITY_MODEL",
                    "weighted mechanism branches require a named probability "
                    "model",
                )
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "latent_prior": latent_prior,
                    "observation_model": observation_model,
                    "probability_model": probability_model,
                    "parameter_domain": _regional_plain(
                        dict(raw.get("parameter_domain", {})),
                        "mechanism parameter domain",
                    ),
                    "program": candidate_program,
                    "selection_assumptions": assumptions,
                    "update_rule": _regional_plain(
                        dict(raw.get("update_rule", {})),
                        "mechanism update rule",
                    ),
                }
            )
        candidate_ids = [item["candidate_id"] for item in candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "mechanism candidate identities must be unique",
            )
    support_roots = request.get("support_roots", [])
    if not isinstance(support_roots, list):
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_EVIDENCE", "support roots are invalid"
        )
    evidence = [*episodes, *holdout]
    acquisition_coverage: list[dict[str, Any]] = []
    outcome_status_counts: dict[str, int] = {}
    policy_versions: set[str] = set()
    unknown_selection_count = 0
    for attempt_index, episode in enumerate(evidence):
        outcome_status = episode["outcome_status"]
        outcome_status_counts[outcome_status] = (
            outcome_status_counts.get(outcome_status, 0) + 1
        )
        policy_version = episode["collection"].get("policy_version")
        if isinstance(policy_version, str):
            policy_versions.add(policy_version)
        if episode["collection"].get("selection_mode") == "unknown":
            unknown_selection_count += 1
        acquisition_coverage.append(
            {
                "action": episode.get("action", {}),
                "attempt_index": attempt_index,
                "collection": episode["collection"],
                "context": episode.get("context", {}),
                "episode_id": episode.get("episode_id"),
                "pair_id": episode.get("pair_id"),
                "intervention": episode.get("intervention", False),
                "interval": episode.get("interval", {}),
                "outcome_status": outcome_status,
                "population": (
                    "training"
                    if attempt_index < len(episodes)
                    else "holdout"
                ),
            }
        )
    outcome_population = {
        "attempt_count": len(evidence),
        "holdout_attempt_count": len(holdout),
        "observed_and_scored_count": outcome_status_counts.get(
            "observed-and-scored", 0
        ),
        "outcome_status_counts": {
            key: outcome_status_counts[key]
            for key in sorted(outcome_status_counts)
        },
        "policy_versions": sorted(policy_versions),
        "training_attempt_count": len(episodes),
        "unknown_selection_count": unknown_selection_count,
        "unresolved_count": (
            len(evidence)
            - outcome_status_counts.get("observed-and-scored", 0)
            - outcome_status_counts.get("canceled-before-effect", 0)
        ),
    }
    raw_identification = request.get("identification")
    if raw_identification is None:
        identification = {
            "assumptions": [],
            "controlled_variables": [],
            "design": "unidentified",
            "randomized_unit": None,
        }
    else:
        if not isinstance(raw_identification, Mapping):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_EVIDENCE",
                "causal identification metadata must be a mapping",
            )
        _semantic_keys(
            raw_identification,
            required=("assumptions", "design"),
            optional=("controlled_variables", "randomized_unit"),
        )
        design = _identifier(
            raw_identification["design"], "causal identification design"
        )
        if design not in {
            "controlled-intervention",
            "paired-intervention",
            "randomized",
        }:
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_EVIDENCE",
                "causal identification design is unsupported",
            )
        assumptions = raw_identification["assumptions"]
        controlled = raw_identification.get("controlled_variables", [])
        if not isinstance(assumptions, list) or not isinstance(
            controlled, list
        ):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_EVIDENCE",
                "causal identification assumptions are invalid",
            )
        identification = {
            "assumptions": [
                _identifier(item, "causal identification assumption")
                for item in assumptions
            ],
            "controlled_variables": [
                _identifier(item, "causal controlled variable")
                for item in controlled
            ],
            "design": design,
            "randomized_unit": (
                None
                if raw_identification.get("randomized_unit") is None
                else _identifier(
                    raw_identification["randomized_unit"],
                    "causal randomized unit",
                )
            ),
        }
    scored_interventions = [
        item
        for item in evidence
        if item.get("intervention") is True
        and item.get("outcome_status") == "observed-and-scored"
    ]
    intervention_actions = {
        canonical_json_bytes(item.get("action", {}))
        for item in scored_interventions
    }
    identification_limitations: list[str] = []
    identified_design = raw_identification is not None
    context_actions: dict[bytes, set[bytes]] = {}
    pair_actions: dict[str, set[bytes]] = {}
    for item in scored_interventions:
        action_key = canonical_json_bytes(item.get("action", {}))
        context_key = canonical_json_bytes(item.get("context", {}))
        context_actions.setdefault(context_key, set()).add(action_key)
        pair_id = item.get("pair_id")
        if isinstance(pair_id, str):
            pair_actions.setdefault(pair_id, set()).add(action_key)
    if any(
        item["collection"].get("selection_mode") == "unknown"
        or not isinstance(item["collection"].get("selected_action"), Mapping)
        or len(item["collection"].get("available_actions", [])) < 2
        for item in scored_interventions
    ):
        identification_limitations.append("collection-policy-incomplete")
    if not any(len(actions) >= 2 for actions in context_actions.values()):
        identification_limitations.append(
            "no-action-overlap-within-context"
        )
    if identified_design and identification["design"] == "randomized":
        if identification["randomized_unit"] is None:
            identification_limitations.append("randomized-unit-unrecorded")
        if any(
            item["collection"].get("selection_mode") != "randomized"
            or item["collection"].get("randomization_probability") is None
            for item in scored_interventions
        ):
            identification_limitations.append(
                "randomization-propensity-or-policy-unrecorded"
            )
    elif (
        identified_design
        and identification["design"] == "controlled-intervention"
        and not identification["controlled_variables"]
    ):
        identification_limitations.append("controlled-variable-unrecorded")
    elif identified_design and identification["design"] == "paired-intervention":
        if (
            any(item.get("pair_id") is None for item in scored_interventions)
            or not any(len(actions) >= 2 for actions in pair_actions.values())
        ):
            identification_limitations.append(
                "paired-intervention-coverage-incomplete"
            )
    if len(intervention_actions) < 2:
        identification_limitations.append("insufficient-action-overlap")
    identification_limitations = sorted(set(identification_limitations))
    causal_authority = identified_design and not identification_limitations
    evidence_class = (
        "identified-interventional"
        if causal_authority
        else "interventional-unidentified"
        if intervention_actions
        else "observational"
    )
    scored: list[dict[str, Any]] = []
    candidate_refs: list[dict[str, Any]] = []
    work = 0
    for candidate in candidates:
        training_losses: list[float] = []
        holdout_losses: list[float] = []
        statuses: list[str] = []
        for index, episode in enumerate(evidence):
            loss, status = _semantic_episode_loss(
                candidate["program"],
                episode,
                observation_program=candidate["observation_model"],
            )
            work += 1
            statuses.append(status)
            if loss is not None:
                (
                    training_losses
                    if index < len(episodes)
                    else holdout_losses
                ).append(loss)
        complexity_bits = (
            len(
                canonical_json_bytes(
                    {
                        "latent_prior": candidate["latent_prior"],
                        "observation_model": candidate[
                            "observation_model"
                        ],
                        "probability_model": candidate[
                            "probability_model"
                        ],
                        "parameter_domain": candidate["parameter_domain"],
                        "program": candidate["program"],
                        "selection_assumptions": candidate[
                            "selection_assumptions"
                        ],
                        "update_rule": candidate["update_rule"],
                    }
                )
            )
            * 8
        )
        prequential_loss = (
            sum(training_losses) / len(training_losses)
            if training_losses
            else 1.0e12
        )
        validation_loss = (
            sum(holdout_losses) / len(holdout_losses)
            if holdout_losses
            else 1.0e12
            if holdout
            else prequential_loss
        )
        validation_basis = (
            "holdout"
            if holdout_losses
            else "no-scored-holdout"
            if holdout
            else "training-only"
            if training_losses
            else "no-scored-evidence"
        )
        all_losses = [*training_losses, *holdout_losses]
        fit_within_noise = (
            bool(training_losses)
            and bool(all_losses)
            and len(all_losses) == len(evidence)
            and not (bool(holdout) and not holdout_losses)
            and max(all_losses) <= 1.0e-12
        )
        score = validation_loss + complexity_bits / 1_000_000.0
        candidate_record_id = (
            f"{mechanism_id}:candidate:{candidate['candidate_id']}"
        )
        candidate_ref = _semantic_append_record(
            state,
            record_id=candidate_record_id,
            kind="Program",
            payload={
                "candidate_id": candidate["candidate_id"],
                "causal_authority": causal_authority,
                "coverage": acquisition_coverage,
                "evidence_class": evidence_class,
                "identification": identification,
                "identification_limitations": identification_limitations,
                "outcome_population": outcome_population,
                "latent_prior": candidate["latent_prior"],
                "observation_model": candidate["observation_model"],
                "probability_model": candidate["probability_model"],
                "parameter_domain": candidate["parameter_domain"],
                "program": candidate["program"],
                "selection_assumptions": candidate[
                    "selection_assumptions"
                ],
                "update_rule": candidate["update_rule"],
                "statistics": {
                    "complexity_bits": complexity_bits,
                    "fit_within_noise": fit_within_noise,
                    "holdout_count": len(holdout),
                    "max_loss": max(all_losses) if all_losses else 1.0e12,
                    "scored_holdout_count": len(holdout_losses),
                    "scored_training_count": len(training_losses),
                    "prequential_loss": prequential_loss,
                    "score": score,
                    "statuses": statuses,
                    "training_count": len(episodes),
                    "validation_loss": validation_loss,
                    "validation_basis": validation_basis,
                },
            },
            status="candidate",
            epistemic_kind="induced",
            support_roots=cast(Any, support_roots),
            derivation={"operation": operation},
        )
        assessment_ref = _semantic_append_record(
            state,
            record_id=f"assessment:{candidate_record_id}",
            kind="Assessment",
            payload={
                "candidate": candidate_ref,
                "losses": training_losses,
                "outcome_population": outcome_population,
                "purpose": "mechanism-selection",
                "validation_losses": holdout_losses,
            },
            epistemic_kind="derived",
            dependencies=(candidate_ref,),
            support_roots=cast(Any, support_roots),
        )
        candidate_refs.append(candidate_ref)
        scored.append(
            {
                "assessment": assessment_ref,
                "candidate": candidate,
                "candidate_id": candidate["candidate_id"],
                "candidate_ref": candidate_ref,
                "complexity_bits": complexity_bits,
                "fit_within_noise": fit_within_noise,
                "max_loss": max(all_losses) if all_losses else 1.0e12,
                "program": candidate["program"],
                "score": score,
                "statuses": statuses,
                "validation_loss": validation_loss,
                "scored_training_count": len(training_losses),
                "validation_basis": validation_basis,
            }
        )
    scored.sort(
        key=lambda item: (
            float(item["score"]),
            str(item["candidate_id"]),
        )
    )
    candidate_comparison = [
        {
            "candidate_id": item["candidate_id"],
            "complexity_bits": item["complexity_bits"],
            "fit_within_noise": item["fit_within_noise"],
            "max_loss": item["max_loss"],
            "score": item["score"],
            "score_semantics": (
                "validation-loss-plus-description-length-penalty"
            ),
            "validation_loss": item["validation_loss"],
        }
        for item in scored
    ]
    winner = scored[0]
    winner_candidate = winner["candidate"]
    fit_candidates = [
        item for item in scored if item["fit_within_noise"]
    ]
    indistinguishable = []
    if fit_candidates:
        best_validation_loss = min(
            float(item["validation_loss"]) for item in fit_candidates
        )
        indistinguishable = [
            item
            for item in fit_candidates
            if math.isclose(
                float(item["validation_loss"]),
                best_validation_loss,
                rel_tol=1.0e-9,
                abs_tol=1.0e-12,
            )
        ]
    indistinguishable_candidates = [
        str(item["candidate_id"]) for item in indistinguishable
    ]
    winner_adequate = bool(winner["fit_within_noise"])
    inadequacy_reason = (
        "no-scored-evidence"
        if int(winner["scored_training_count"]) == 0
        else "no-scored-holdout"
        if winner["validation_basis"] == "no-scored-holdout"
        else "no-candidate-fits-within-noise"
    )
    prior_ref = state["current"]["Program"].get(mechanism_id)
    mechanism_record_id = (
        mechanism_id
        if winner_adequate or prior_ref is None
        else (
            f"{mechanism_id}:revision-candidate:"
            f"{request.get('operation_id', sha256_value(request))}"
        )
    )
    mechanism_ref = _semantic_append_record(
        state,
        record_id=mechanism_record_id,
        kind="Program",
        payload={
            "candidate_family": candidate_refs,
            "candidate_family_adequacy": (
                "adequate" if winner_adequate else "representation-insufficient"
            ),
            "inadequacy_reason": (
                None if winner_adequate else inadequacy_reason
            ),
            "causal_authority": causal_authority,
            "coverage": acquisition_coverage,
            "evidence_class": evidence_class,
            "identification": identification,
            "identification_limitations": identification_limitations,
            "outcome_population": outcome_population,
            "latent_prior": winner_candidate["latent_prior"],
            "candidate_comparison": candidate_comparison,
            "indistinguishable_candidates": indistinguishable_candidates,
            "observation_model": winner_candidate["observation_model"],
            "probability_model": winner_candidate["probability_model"],
            "parameter_domain": winner_candidate["parameter_domain"],
            "program": winner["program"],
            "program_role": "mechanism",
            "selected_candidate": winner["candidate_id"],
            "selection_ambiguity": len(indistinguishable_candidates) > 1,
            "selection_assumptions": winner_candidate[
                "selection_assumptions"
            ],
            "statistics": {
                "episode_count": len(episodes),
                "holdout_count": len(holdout),
                "outcome_population": outcome_population,
                "statuses": winner["statuses"],
                "validation_loss": winner["validation_loss"],
            },
            "update_rule": winner_candidate["update_rule"],
        },
        status=("active" if winner_adequate else "candidate"),
        epistemic_kind="induced",
        dependencies=tuple(candidate_refs),
        support_roots=cast(Any, support_roots),
        derivation={
            "criterion": "prequential-loss-plus-description-length",
            "goal_independent": True,
            "operation": operation,
        },
    )

    frontier = (
        _semantic_invalidate(
            state, (prior_ref,), reason="mechanism-relearned"
        )
        if winner_adequate and prior_ref is not None
        else []
    )
    _semantic_reindex_record(state, mechanism_ref)
    inadequacy_ref: dict[str, Any] | None = None
    if not winner_adequate:
        inadequacy_ref = _semantic_append_record(
            state,
            record_id=f"obligation:{mechanism_record_id}:model-inadequacy",
            kind="Obligation",
            payload={
                "candidate": mechanism_ref,
                "question": "find a mechanism family covering the evidence",
                "reason": inadequacy_reason,
                "statuses": winner["statuses"],
            },
            epistemic_kind="derived",
            dependencies=(mechanism_ref,),
            support_roots=cast(Any, support_roots),
        )
        _semantic_reindex_record(state, inadequacy_ref)
    return _semantic_result(
        operation,
        "supported" if winner_adequate else "representation-insufficient",
        mechanism=mechanism_ref,
        causal_authority=causal_authority,
        evidence_class=evidence_class,
        identification=identification,
        identification_limitations=identification_limitations,
        candidate_comparison=candidate_comparison,
        indistinguishable_candidates=indistinguishable_candidates,
        probability_model=winner_candidate["probability_model"],
        model_inadequacy=inadequacy_ref,
        limitations=(
            identification_limitations
            + ([] if winner_adequate else [inadequacy_reason])
        ),
        invalidation_frontier=frontier,
    ), max(
        1,
        work
        + len(scored) * 2
        + len(frontier)
        + (1 if inadequacy_ref is not None else 0),
    )


def _semantic_predictive_signature(value: Any, label: str) -> dict[str, Any]:
    required = {
        "clock_boundary",
        "collection_boundary",
        "comparison_metric",
        "horizon",
        "interval",
        "output_measure",
        "prediction_semantics",
        "probability_model",
        "tolerance",
        "units",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise FieldIntelligenceError(
            "INVALID_PREDICTIVE_STATE",
            f"{label} does not match the predictive signature schema",
        )
    if any(
        not isinstance(value[name], Mapping)
        for name in ("clock_boundary", "collection_boundary", "interval")
    ):
        raise FieldIntelligenceError(
            "INVALID_PREDICTIVE_STATE",
            f"{label} boundaries must be mappings",
        )
    semantics = value["prediction_semantics"]
    if semantics not in {"constraint-set", "probability"}:
        raise FieldIntelligenceError(
            "INVALID_PREDICTIVE_STATE",
            f"{label} prediction semantics are unsupported",
        )
    raw_probability_model = value["probability_model"]
    probability_model = (
        _semantic_probability_model(
            raw_probability_model, f"{label} probability model"
        )
        if semantics == "probability"
        else None
    )
    if semantics == "constraint-set" and raw_probability_model is not None:
        raise FieldIntelligenceError(
            "INVALID_PREDICTIVE_STATE",
            f"{label} set semantics cannot carry probability metadata",
        )
    tolerance = value["tolerance"]
    if not isinstance(tolerance, Mapping):
        tolerance_number = _finite(tolerance, f"{label} tolerance")
        if tolerance_number < 0.0:
            raise FieldIntelligenceError(
                "INVALID_PREDICTIVE_STATE",
                f"{label} tolerance must be nonnegative",
            )
        normalized_tolerance: Any = tolerance_number
    else:
        normalized_tolerance = _regional_plain(
            dict(tolerance), f"{label} tolerance"
        )
    return {
        "clock_boundary": _regional_plain(
            dict(value["clock_boundary"]), f"{label} clock boundary"
        ),
        "collection_boundary": _regional_plain(
            dict(value["collection_boundary"]),
            f"{label} collection boundary",
        ),
        "comparison_metric": _identifier(
            value["comparison_metric"], f"{label} comparison metric"
        ),
        "horizon": _regional_integer(
            value["horizon"],
            f"{label} horizon",
            minimum=1,
            maximum=1_000_000,
        ),
        "interval": _regional_plain(
            dict(value["interval"]), f"{label} interval"
        ),
        "output_measure": _regional_plain(
            value["output_measure"], f"{label} output measure"
        ),
        "prediction_semantics": semantics,
        "probability_model": probability_model,
        "tolerance": normalized_tolerance,
        "units": _regional_plain(value["units"], f"{label} units"),
    }


def _semantic_learn_predictive_state(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("examples", "representation_id", "signature"),
        optional=("holdout", "support_roots", "window"),
    )
    representation_id = _identifier(
        request["representation_id"], "predictive state identity"
    )
    signature = _semantic_predictive_signature(
        request["signature"], "predictive state signature"
    )
    prediction_semantics = str(signature["prediction_semantics"])
    examples = request["examples"]
    holdout = request.get("holdout", [])
    window = _regional_integer(
        request.get("window", 1),
        "predictive state window",
        minimum=1,
        maximum=256,
    )
    if (
        not isinstance(examples, list)
        or not examples
        or not isinstance(holdout, list)
    ):
        raise FieldIntelligenceError(
            "INVALID_PREDICTIVE_STATE",
            "predictive-state examples are invalid",
        )
    evidence_refs: dict[
        tuple[str, str, int], dict[str, Any]
    ] = {}
    evidence_support_roots: set[str] = set()

    def normalize_example(raw: Any, label: str) -> dict[str, Any]:
        allowed = {
            "action",
            "context",
            "future",
            "future_ref",
            "history",
            "history_ref",
            "question",
        }
        if (
            not isinstance(raw, Mapping)
            or set(raw) - allowed
            or not {"future", "history"}.issubset(raw)
            or not isinstance(raw["history"], list)
            or not isinstance(raw.get("action", {}), Mapping)
            or not isinstance(raw.get("context", {}), Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_PREDICTIVE_STATE", f"{label} is invalid"
            )
        refs: dict[str, dict[str, Any]] = {}
        for ref_name in ("history_ref", "future_ref"):
            raw_ref = raw.get(ref_name)
            if raw_ref is None:
                continue
            if not isinstance(raw_ref, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_PREDICTIVE_STATE",
                    f"{label} {ref_name} is invalid",
                )
            reference, record = _semantic_reference(
                state, raw_ref, require_current=True
            )
            normalized_ref = reference.as_dict()
            refs[ref_name] = normalized_ref
            evidence_refs[
                (
                    reference.kind,
                    reference.id,
                    reference.content_version,
                )
            ] = normalized_ref
            evidence_support_roots.update(record["support_roots"])
        return {
            "action": _regional_plain(
                dict(raw.get("action", {})), f"{label} action"
            ),
            "context": _regional_plain(
                dict(raw.get("context", {})), f"{label} context"
            ),
            "future": _regional_plain(raw["future"], f"{label} future"),
            "future_ref": refs.get("future_ref"),
            "history": _regional_plain(
                raw["history"][-window:], f"{label} history"
            ),
            "history_ref": refs.get("history_ref"),
            "question": _regional_plain(
                raw.get("question"), f"{label} question"
            ),
        }

    training = [
        normalize_example(raw, f"predictive training example {index}")
        for index, raw in enumerate(examples)
    ]
    validation = [
        normalize_example(raw, f"predictive holdout example {index}")
        for index, raw in enumerate(holdout)
    ]
    counts: dict[bytes, dict[bytes, dict[bytes, int]]] = {}
    histories: dict[bytes, Any] = {}
    history_refs: dict[bytes, list[dict[str, Any]]] = {}
    conditions: dict[bytes, dict[str, Any]] = {}
    futures: dict[bytes, Any] = {}
    for example in training:
        history_key = canonical_json_bytes(example["history"])
        condition = {
            "action": example["action"],
            "context": example["context"],
            "question": example["question"],
        }
        condition_key = canonical_json_bytes(condition)
        future_key = canonical_json_bytes(example["future"])
        histories[history_key] = example["history"]
        if example["history_ref"] is not None:
            refs = history_refs.setdefault(history_key, [])
            if example["history_ref"] not in refs:
                refs.append(example["history_ref"])
        conditions[condition_key] = condition
        futures[future_key] = example["future"]
        bucket = counts.setdefault(history_key, {}).setdefault(
            condition_key, {}
        )
        bucket[future_key] = bucket.get(future_key, 0) + 1

    def consequence_signature(
        bucket: Mapping[bytes, int],
    ) -> tuple[tuple[bytes, int], ...]:
        ordered = sorted(bucket.items())
        if prediction_semantics == "constraint-set":
            return tuple((future_key, 1) for future_key, _ in ordered)
        total = sum(count for _, count in ordered)
        microprobabilities = [
            (future_key, 1_000_000 * count // total)
            for future_key, count in ordered
        ]
        remainder = 1_000_000 - sum(
            probability for _, probability in microprobabilities
        )
        return tuple(
            (
                future_key,
                probability + (1 if index < remainder else 0),
            )
            for index, (future_key, probability) in enumerate(
                microprobabilities
            )
        )

    signatures: dict[
        tuple[tuple[bytes, tuple[tuple[bytes, int], ...]], ...],
        list[bytes],
    ] = {}
    for history_key, condition_counts in counts.items():
        signature_rows = tuple(
            (
                condition_key,
                consequence_signature(bucket),
            )
            for condition_key, bucket in sorted(condition_counts.items())
        )
        signatures.setdefault(signature_rows, []).append(history_key)

    classes: list[dict[str, Any]] = []
    lookup: dict[bytes, int] = {}
    class_test_maps: list[dict[bytes, dict[str, Any]]] = []
    for class_index, class_signature in enumerate(
        sorted(signatures, key=repr)
    ):
        history_keys = sorted(signatures[class_signature])
        tests: list[dict[str, Any]] = []
        test_map: dict[bytes, dict[str, Any]] = {}
        for condition_key, distribution in class_signature:
            bucket = counts[history_keys[0]][condition_key]
            consequences = []
            for future_key, encoded_weight in distribution:
                consequence = {
                    "future": futures[future_key],
                    "support_count": bucket[future_key],
                }
                if prediction_semantics == "probability":
                    consequence["weight"] = encoded_weight / 1_000_000.0
                consequences.append(consequence)
            test = {
                "condition": conditions[condition_key],
                "consequences": consequences,
                "prediction_semantics": prediction_semantics,
            }
            tests.append(test)
            test_map[condition_key] = test
        class_history_refs = sorted(
            (
                ref
                for history_key in history_keys
                for ref in history_refs.get(history_key, [])
            ),
            key=canonical_json_bytes,
        )
        classes.append(
            {
                "class_id": class_index,
                "histories": [histories[key] for key in history_keys],
                "history_refs": class_history_refs,
                "tests": tests,
            }
        )
        class_test_maps.append(test_map)
        for key in history_keys:
            lookup[key] = class_index

    validation_misses: list[dict[str, Any]] = []
    for index, example in enumerate(validation):
        history_key = canonical_json_bytes(example["history"])
        condition = {
            "action": example["action"],
            "context": example["context"],
            "question": example["question"],
        }
        condition_key = canonical_json_bytes(condition)
        class_index = lookup.get(history_key)
        reason = "unseen-history"
        if class_index is not None:
            matching_test = class_test_maps[class_index].get(condition_key)
            if matching_test is None:
                reason = "unseen-condition"
            elif canonical_json_bytes(example["future"]) not in {
                canonical_json_bytes(item["future"])
                for item in matching_test["consequences"]
            }:
                reason = "future-outside-class"
            else:
                continue
        validation_misses.append(
            {
                "condition": condition,
                "future": example["future"],
                "future_ref": example["future_ref"],
                "history": example["history"],
                "history_ref": example["history_ref"],
                "holdout_index": index,
                "reason": reason,
            }
        )
    validation_error = len(validation_misses) / max(1, len(validation))

    splits: list[dict[str, Any]] = []
    for left_index in range(len(classes)):
        for right_index in range(left_index + 1, len(classes)):
            left_tests = class_test_maps[left_index]
            right_tests = class_test_maps[right_index]
            separating_key = next(
                (
                    key
                    for key in sorted(set(left_tests) | set(right_tests))
                    if canonical_json_bytes(left_tests.get(key))
                    != canonical_json_bytes(right_tests.get(key))
                ),
                None,
            )
            if separating_key is None:
                continue
            left_test = left_tests.get(separating_key)
            right_test = right_tests.get(separating_key)
            splits.append(
                {
                    "first_separating_test": (
                        left_test["condition"]
                        if left_test is not None
                        else right_test["condition"]
                    ),
                    "history_refs": {
                        "left": classes[left_index]["history_refs"],
                        "right": classes[right_index]["history_refs"],
                    },
                    "left_class_id": classes[left_index]["class_id"],
                    "right_class_id": classes[right_index]["class_id"],
                    "split_mapping": {
                        "left": (
                            None
                            if left_test is None
                            else left_test["consequences"]
                        ),
                        "right": (
                            None
                            if right_test is None
                            else right_test["consequences"]
                        ),
                    },
                }
            )
    test_specs = [
        {
            "class_id": item["class_id"],
            "first_separating_test": (
                item["tests"][0]["condition"] if item["tests"] else None
            ),
            "histories": item["histories"],
            "history_refs": item["history_refs"],
            "test_kind": "prospective-equivalence",
        }
        for item in classes
        if len(item["histories"]) > 1
    ]
    test_specs.extend(
        {**split, "test_kind": "first-separating-test"}
        for split in splits
    )
    test_specs.extend(
        {**item, "test_kind": "validation-miss"}
        for item in validation_misses
    )
    if len(test_specs) > state["bounds"]["max_alternatives"]:
        return _semantic_result(
            "learn-predictive-state",
            "resource-exhausted",
            representation=None,
            limitations=["predictive-test-obligation-bound"],
        ), max(1, len(training) + len(validation))

    program = semantic_program_payload(
        program_kind="construction",
        body={
            "belief_semantics": prediction_semantics,
            "classes": classes,
            "signature": signature,
            "splits": splits,
            "window": window,
        },
        reads=("history", "action", "context", "question", "signature"),
        emits=(
            "future-distribution"
            if prediction_semantics == "probability"
            else "future-set",
        ),
        max_work=max(
            1, sum(1 + len(item["tests"]) for item in classes)
        ),
        max_branches=max(
            1,
            max(
                (
                    len(test["consequences"])
                    for item in classes
                    for test in item["tests"]
                ),
                default=1,
            ),
        ),
    )
    prior_ref = state["current"]["Program"].get(representation_id)
    raw_support_roots = request.get("support_roots", [])
    if not isinstance(raw_support_roots, list):
        raise FieldIntelligenceError(
            "INVALID_PREDICTIVE_STATE",
            "predictive state support roots must be a list",
        )
    support_roots = sorted(
        evidence_support_roots
        | {
            _identifier(item, "predictive state support root")
            for item in raw_support_roots
        }
    )
    dependencies = tuple(evidence_refs[key] for key in sorted(evidence_refs))
    reference = _semantic_append_record(
        state,
        record_id=representation_id,
        kind="Program",
        payload={
            "program_role": "predictive-state",
            "program": program,
            "signature": signature,
            "splits": splits,
            "statistics": {
                "class_count": len(classes),
                "example_count": len(training),
                "holdout_count": len(validation),
                "validation_error": validation_error,
            },
        },
        status="active" if not validation_misses else "candidate",
        epistemic_kind="induced",
        dependencies=dependencies,
        support_roots=support_roots,
        derivation={
            "criterion": (
                "conditional-frequency-equivalence"
                if prediction_semantics == "probability"
                else "consequence-set-equivalence"
            ),
            "goal_independent": True,
        },
    )
    changed_refs: list[Mapping[str, Any]] = []
    if prior_ref is not None:
        changed_refs.append(prior_ref)
    obligation_refs: list[dict[str, Any]] = []
    for spec in test_specs:
        obligation_id = (
            f"obligation:predictive:{representation_id}:{sha256_value(spec)}"
        )
        old_obligation = state["current"]["Obligation"].get(obligation_id)
        if old_obligation is not None:
            changed_refs.append(old_obligation)
        obligation_refs.append(
            _semantic_append_record(
                state,
                record_id=obligation_id,
                kind="Obligation",
                payload={
                    "purpose": "predictive-state-test",
                    "representation": reference,
                    "state": "pending",
                    "test": spec,
                },
                epistemic_kind="derived",
                dependencies=(reference,),
                support_roots=support_roots,
            )
        )
    frontier = _semantic_invalidate(
        state, changed_refs, reason="predictive-state-relearned"
    )
    _semantic_reindex_record(state, reference)
    for obligation_ref in obligation_refs:
        _semantic_reindex_record(state, obligation_ref)
    status = "supported" if not validation_misses else "support-gap"
    return _semantic_result(
        "learn-predictive-state",
        status,
        representation=reference,
        classes=classes,
        prediction_semantics=prediction_semantics,
        signature=signature,
        splits=splits,
        test_obligations=obligation_refs,
        validation_error=validation_error,
        validation_misses=validation_misses,
        invalidation_frontier=frontier,
        limitations=[] if not validation_misses else ["predictive-holdout-miss"],
    ), max(
        1,
        len(training)
        + len(validation)
        + len(obligation_refs)
        + len(frontier),
    )




def _semantic_representation_assessment(
    output_roles: Sequence[str],
    edits: Sequence[Mapping[str, Any]],
    examples: Sequence[Mapping[str, Any]],
    *,
    frozen_table: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    table = (
        {}
        if frozen_table is None
        else cast(
            dict[str, Any],
            _regional_plain(
                dict(frozen_table), "frozen representation table"
            ),
        )
    )
    buckets: dict[bytes, dict[bytes, int]] = {}
    encoded_values: dict[bytes, Any] = {}
    outcome_values: dict[bytes, Any] = {}
    errors = 0
    abstained = 0
    rare_failures: list[str] = []
    prospective_predictions: list[dict[str, Any]] = []
    work = 0
    for index, example in enumerate(examples):
        if (
            not isinstance(example, Mapping)
            or set(example)
            - {
                "action",
                "context",
                "example_id",
                "features",
                "outcome",
                "rare_case",
            }
            or not isinstance(example.get("features"), Mapping)
            or "outcome" not in example
            or not isinstance(example.get("action", {}), Mapping)
            or not isinstance(example.get("context", {}), Mapping)
            or not isinstance(example.get("rare_case", False), bool)
        ):
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION_EVIDENCE",
                "representation example is invalid",
            )
        example_id = _identifier(
            example.get("example_id", f"example:{index}"),
            "representation example identity",
        )
        try:
            transformed = apply_semantic_representation_edits(
                cast(Mapping[str, Any], example["features"]),
                edits,
                action=cast(Mapping[str, Any], example.get("action", {})),
                context=cast(Mapping[str, Any], example.get("context", {})),
            )
        except (ValueError, TypeError) as exc:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION_EVIDENCE",
                "representation edit program is invalid",
            ) from exc
        work += int(transformed["work"])
        if transformed["status"] != "supported":
            abstained += 1
            if example.get("rare_case", False):
                rare_failures.append(example_id)
            if frozen_table is not None:
                prospective_predictions.append(
                    {
                        "answered": False,
                        "example_id": example_id,
                        "prediction": None,
                    }
                )
            continue
        encoded: dict[str, Any] = {}
        for role in output_roles:
            if role not in transformed["values"]:
                abstained += 1
                if example.get("rare_case", False):
                    rare_failures.append(example_id)
                if frozen_table is not None:
                    prospective_predictions.append(
                        {
                            "answered": False,
                            "example_id": example_id,
                            "prediction": None,
                        }
                    )
                break
            encoded[role] = transformed["values"][role]
        else:
            encoded_key = canonical_json_bytes(encoded)
            outcome_key = canonical_json_bytes(example["outcome"])
            if frozen_table is None:
                encoded_values[encoded_key] = encoded
                outcome_values[outcome_key] = example["outcome"]
                bucket = buckets.setdefault(encoded_key, {})
                bucket[outcome_key] = bucket.get(outcome_key, 0) + 1
            else:
                row = table.get(encoded_key.hex())
                correct = (
                    isinstance(row, Mapping)
                    and row.get("encoded") == encoded
                    and row.get("outcome") == example["outcome"]
                )
                prospective_predictions.append(
                    {
                        "answered": isinstance(row, Mapping)
                        and row.get("encoded") == encoded,
                        "example_id": example_id,
                        "prediction": (
                            row.get("outcome")
                            if isinstance(row, Mapping)
                            and row.get("encoded") == encoded
                            else None
                        ),
                    }
                )
                if not correct:
                    errors += 1
                    if example.get("rare_case", False):
                        rare_failures.append(example_id)
    if frozen_table is None:
        for encoded_key, bucket in sorted(buckets.items()):
            selected = min(
                bucket,
                key=lambda key: (-bucket[key], key),
            )
            bucket_errors = sum(bucket.values()) - bucket[selected]
            errors += bucket_errors
            table[encoded_key.hex()] = {
                "encoded": encoded_values[encoded_key],
                "outcome": outcome_values[selected],
                "support": sum(bucket.values()),
            }
    attempted = len(examples)
    answered = attempted - abstained
    loss = (errors + abstained) / max(1, attempted)
    return {
        "abstained": abstained,
        "answered": answered,
        "attempted": attempted,
        "coverage": answered / max(1, attempted),
        "errors": errors,
        "loss": loss,
        "precision": (
            None if answered == 0 else 1.0 - errors / answered
        ),
        "rare_failures": sorted(set(rare_failures)),
        "prospective_predictions": prospective_predictions,
        "table": table,
        "work": max(1, work + attempted),
    }


def _semantic_generated_representation_candidates(
    state: Mapping[str, Any],
    representation_id: str,
    examples: Sequence[Mapping[str, Any]],
    *,
    question: Mapping[str, Any],
    information_boundary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Propose a bounded deterministic edit frontier from field evidence."""

    if any(
        not isinstance(example, Mapping)
        or not isinstance(example.get("features"), Mapping)
        for example in examples
    ):
        raise FieldIntelligenceError(
            "INVALID_REPRESENTATION_EVIDENCE",
            "autonomous representation examples require feature mappings",
        )
    feature_sets = [
        set(cast(Mapping[str, Any], example["features"]))
        for example in examples
    ]
    roles = sorted(set.intersection(*feature_sets)) if feature_sets else []
    roles = [_identifier(role, "representation feature role") for role in roles]
    if not roles:
        raise FieldIntelligenceError(
            "INVALID_REPRESENTATION_EVIDENCE",
            "autonomous representation search has no common feature roles",
        )
    maximum = int(state["bounds"]["max_alternatives"])
    prior_ref = state["current"]["Program"].get(representation_id)
    prior_history: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []

    def add(
        family: str,
        output_roles: Sequence[str],
        edits: Sequence[Mapping[str, Any]],
        *,
        detail: Mapping[str, Any],
    ) -> None:
        descriptor = {
            "edits": list(edits),
            "family": family,
            "output_roles": sorted(output_roles),
        }
        proposals.append(
            {
                "candidate_id": (
                    f"auto:{family}:{sha256_value(descriptor)[:16]}"
                ),
                "edits": list(edits),
                "frontier": {
                    "generator": "closed-typed-edit-grammar",
                    "status": "proposed",
                },
                "information_boundary": dict(information_boundary),
                "output_roles": sorted(output_roles),
                "parent_refs": [],
                "proposal_history": [
                    *prior_history,
                    {
                        "detail": dict(detail),
                        "kind": "field-generated",
                    },
                ],
                "question": dict(question),
            }
        )

    if prior_ref is not None:
        _, prior = _semantic_reference(state, prior_ref, require_current=True)
        prior_program = prior["payload"].get("program")
        if (
            prior["status"] == "active"
            and prior["payload"].get("program_role") == "representation"
            and isinstance(prior_program, Mapping)
            and isinstance(prior_program.get("body"), Mapping)
            and prior_program["body"].get("schema")
            == SEMANTIC_REPRESENTATION_SCHEMA
        ):
            prior_body = prior_program["body"]
            prior_history = [
                {
                    "kind": "retained-prior",
                    "reference": dict(prior_ref),
                }
            ]
            add(
                "prior",
                cast(Sequence[str], prior_body["output_roles"]),
                cast(Sequence[Mapping[str, Any]], prior_body["edits"]),
                detail={"content_version": prior_ref["content_version"]},
            )
    add("all-observed", roles, [], detail={"roles": roles})
    for role in roles:
        add("observed", [role], [], detail={"role": role})
    numeric_roles = [
        role
        for role in roles
        if all(
            isinstance(cast(Mapping[str, Any], example["features"])[role], (int, float))
            and not isinstance(cast(Mapping[str, Any], example["features"])[role], bool)
            and math.isfinite(
                float(cast(Mapping[str, Any], example["features"])[role])
            )
            for example in examples
        )
    ]
    for left_index, left in enumerate(numeric_roles):
        for right in numeric_roles[left_index + 1 :]:
            for relation in (
                "difference",
                "distance",
                "equal",
                "order",
                "ratio",
                "sum",
            ):
                signature = {"left": left, "relation": relation, "right": right}
                target = f"derived:{relation}:{sha256_value(signature)[:16]}"
                add(
                    relation,
                    [target],
                    [
                        {
                            "family": "relational-variable",
                            "guard": None,
                            "relation": relation,
                            "sources": [left, right],
                            "target": target,
                            "tolerance": 0.0,
                            "units": None,
                        }
                    ],
                    detail=signature,
                )
            signature = {
                "left": left,
                "operator": "absolute-difference",
                "right": right,
            }
            target = f"derived:symmetry:{sha256_value(signature)[:16]}"
            add(
                "symmetry",
                [target],
                [
                    {
                        "claim": "empirical",
                        "family": "symmetry",
                        "operator": "absolute-difference",
                        "sources": [left, right],
                        "target": target,
                    }
                ],
                detail=signature,
            )
    if len(numeric_roles) >= 2:
        for reducer in ("max", "mean", "min", "sum"):
            signature = {"reducer": reducer, "sources": numeric_roles}
            target = f"derived:scale:{sha256_value(signature)[:16]}"
            add(
                f"scale-{reducer}",
                [target],
                [
                    {
                        "boundary": "preserve",
                        "factor": 1.0,
                        "family": "scale",
                        "reducer": reducer,
                        "sources": numeric_roles,
                        "target": target,
                    }
                ],
                detail=signature,
            )
    boolean_roles = [
        role
        for role in roles
        if all(
            (
                isinstance(
                    cast(Mapping[str, Any], example["features"])[role], bool
                )
                or cast(Mapping[str, Any], example["features"])[role] in (0, 1)
            )
            for example in examples
        )
    ]
    if len(boolean_roles) >= 2:
        for relation in ("all-equal", "exactly-one", "exclusion", "xor"):
            signature = {"relation": relation, "sources": boolean_roles}
            target = f"derived:factor:{sha256_value(signature)[:16]}"
            add(
                f"factor-{relation}",
                [target],
                [
                    {
                        "family": "factor-scope",
                        "relation": relation,
                        "sources": boolean_roles,
                        "target": target,
                    }
                ],
                detail=signature,
            )
    deduplicated: list[dict[str, Any]] = []
    seen: set[bytes] = set()
    for proposal in proposals:
        identity = canonical_json_bytes(
            {
                "edits": proposal["edits"],
                "output_roles": proposal["output_roles"],
            }
        )
        if identity in seen:
            continue
        seen.add(identity)
        deduplicated.append(proposal)
    retained = deduplicated[:maximum]
    remaining = [
        proposal["candidate_id"] for proposal in deduplicated[maximum:]
    ]
    for proposal in retained:
        proposal["frontier"] = {
            **proposal["frontier"],
            "remaining": remaining,
            "status": "bounded" if remaining else "evaluated",
        }
    return retained


def _semantic_learn_representation(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("examples", "representation_id"),
        optional=(
            "candidates",
            "exploration_reserve",
            "holdout",
            "information_boundary",
            "question",
            "support_roots",
        ),
    )
    representation_id = _identifier(
        request["representation_id"], "representation identity"
    )
    examples = request["examples"]
    holdout = request.get("holdout", [])
    if (
        not isinstance(examples, list)
        or not examples
        or not isinstance(holdout, list)
    ):
        raise FieldIntelligenceError(
            "INVALID_REPRESENTATION_EVIDENCE",
            "representation example evidence is invalid",
        )
    question = _regional_plain(
        request.get("question", {"target": "outcome"}),
        "representation question",
    )
    information_boundary = _regional_plain(
        request.get(
            "information_boundary",
            {"available": ["features", "action", "context"]},
        ),
        "representation information boundary",
    )
    if not isinstance(question, dict) or not isinstance(
        information_boundary, dict
    ):
        raise FieldIntelligenceError(
            "INVALID_REPRESENTATION_EVIDENCE",
            "representation question and information boundary must be mappings",
        )
    supplied_candidates = request.get("candidates")
    if supplied_candidates is None:
        candidates = _semantic_generated_representation_candidates(
            state,
            representation_id,
            cast(Sequence[Mapping[str, Any]], examples),
            question=cast(Mapping[str, Any], question),
            information_boundary=cast(
                Mapping[str, Any], information_boundary
            ),
        )
    else:
        candidates = supplied_candidates
    if (
        not isinstance(candidates, list)
        or not candidates
        or len(candidates) > state["bounds"]["max_alternatives"]
    ):
        raise FieldIntelligenceError(
            "INVALID_REPRESENTATION_EVIDENCE",
            "representation candidate evidence is invalid",
        )
    exploration_reserve = _regional_integer(
        request.get("exploration_reserve", max(1, len(candidates) // 4)),
        "representation exploration reserve",
        minimum=1,
        maximum=state["bounds"]["max_work"],
    )
    scored: list[dict[str, Any]] = []
    candidate_refs: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()
    total_work = exploration_reserve
    rich_keys = {
        "applicability",
        "candidate_id",
        "edits",
        "exceptions",
        "frontier",
        "information_boundary",
        "measured_cost",
        "output_roles",
        "parameter_initialization",
        "parent_refs",
        "proposal_history",
        "prospective_predictions",
        "question",
    }
    for raw in candidates:
        if not isinstance(raw, Mapping):
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION_EVIDENCE",
                "representation candidate is invalid",
            )
        legacy = set(raw) == {"candidate_id", "keys"}
        if not legacy and (
            set(raw) - rich_keys
            or not {"candidate_id", "edits", "output_roles"}.issubset(raw)
        ):
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION_EVIDENCE",
                "typed representation candidate has an invalid schema",
            )
        candidate_id = _identifier(
            raw["candidate_id"], "representation candidate identity"
        )
        if candidate_id in candidate_ids:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION_EVIDENCE",
                "representation candidate identities must be unique",
            )
        candidate_ids.add(candidate_id)
        raw_roles = raw["keys"] if legacy else raw["output_roles"]
        if not isinstance(raw_roles, list) or not raw_roles:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION_EVIDENCE",
                "representation output roles are invalid",
            )
        output_roles = [
            _identifier(item, "representation output role")
            for item in raw_roles
        ]
        if output_roles != sorted(set(output_roles)):
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION_EVIDENCE",
                "representation output roles must be sorted and unique",
            )
        try:
            edits = canonical_semantic_representation_edits(
                [] if legacy else raw["edits"]
            )
        except (TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION_EVIDENCE",
                "representation edit grammar is invalid",
            ) from exc
        candidate_question = _regional_plain(
            question if legacy else raw.get("question", question),
            "candidate representation question",
        )
        candidate_boundary = _regional_plain(
            (
                information_boundary
                if legacy
                else raw.get("information_boundary", information_boundary)
            ),
            "candidate representation information boundary",
        )
        if (
            candidate_question != question
            or candidate_boundary != information_boundary
        ):
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION_EVIDENCE",
                "representation candidates changed the comparison boundary",
            )
        parent_refs: list[dict[str, Any]] = []
        raw_parents = [] if legacy else raw.get("parent_refs", [])
        if not isinstance(raw_parents, list):
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION_EVIDENCE",
                "representation candidate parents must be a list",
            )
        for raw_parent in raw_parents:
            if not isinstance(raw_parent, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_REPRESENTATION_EVIDENCE",
                    "representation parent must be a typed reference",
                )
            parent_ref, parent = _semantic_reference(
                state, raw_parent, require_current=True
            )
            if parent_ref.kind != "Program" or parent["status"] != "active":
                raise FieldIntelligenceError(
                    "INVALID_REPRESENTATION_EVIDENCE",
                    "representation parent must be an active Program",
                )
            parent_refs.append(parent_ref.as_dict())
        training = _semantic_representation_assessment(
            output_roles, edits, cast(Any, examples)
        )
        validation = (
            _semantic_representation_assessment(
                output_roles,
                edits,
                cast(Any, holdout),
                frozen_table=training["table"],
            )
            if holdout
            else {
                **training,
                "prospective_predictions": [],
            }
        )
        candidate_program = semantic_program_payload(
            program_kind="construction",
            body={
                "edits": edits,
                "information_boundary": information_boundary,
                "output_roles": output_roles,
                "question": question,
                "schema": SEMANTIC_REPRESENTATION_SCHEMA,
                "table": training["table"],
            },
            reads=output_roles,
            max_work=max(
                1,
                min(
                    state["bounds"]["max_work"],
                    int(training["work"]) + len(edits) + len(output_roles),
                ),
            ),
            max_branches=max(1, len(training["table"])),
            applicability=cast(
                Any, {} if legacy else raw.get("applicability", {})
            ),
        )
        complexity_bits = 8 * len(
            canonical_json_bytes(
                {
                    "edits": edits,
                    "output_roles": output_roles,
                    "program": candidate_program,
                }
            )
        )
        score = (
            float(validation["loss"])
            + complexity_bits / 1_000_000.0
            + (
                int(training["work"]) + int(validation["work"])
            )
            / 1_000_000_000.0
        )
        declared_predictions = (
            [] if legacy else raw.get("prospective_predictions", [])
        )
        proposal_history = [] if legacy else raw.get("proposal_history", [])
        exceptions = [] if legacy else raw.get("exceptions", [])
        frontier = (
            {"remaining": [], "status": "evaluated"}
            if legacy
            else raw.get(
                "frontier", {"remaining": [], "status": "evaluated"}
            )
        )
        declared_cost = {} if legacy else raw.get("measured_cost", {})
        parameter_initialization = (
            {} if legacy else raw.get("parameter_initialization", {})
        )
        if (
            not isinstance(declared_predictions, list)
            or not isinstance(proposal_history, list)
            or not isinstance(exceptions, list)
            or not isinstance(frontier, Mapping)
            or not isinstance(declared_cost, Mapping)
            or not isinstance(parameter_initialization, Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_REPRESENTATION_EVIDENCE",
                "representation candidate retained search metadata is invalid",
            )
        statistics = {
            "complexity_bits": complexity_bits,
            "holdout": {
                key: validation[key]
                for key in (
                    "abstained",
                    "answered",
                    "attempted",
                    "coverage",
                    "errors",
                    "loss",
                    "precision",
                    "rare_failures",
                )
            },
            "score": score,
            "training": {
                key: training[key]
                for key in (
                    "abstained",
                    "answered",
                    "attempted",
                    "coverage",
                    "errors",
                    "loss",
                    "precision",
                    "rare_failures",
                )
            },
        }
        measured_cost = {
            "declared": _regional_plain(
                dict(declared_cost), "declared representation cost"
            ),
            "evaluation_work": int(training["work"])
            + int(validation["work"]),
            "proposal_work": 1,
        }
        candidate_ref = _semantic_append_record(
            state,
            record_id=f"{representation_id}:candidate:{candidate_id}",
            kind="Program",
            payload={
                "applicability": candidate_program["applicability"],
                "candidate_id": candidate_id,
                "exceptions": sorted(
                    {
                        canonical_json_bytes(item).decode("utf-8")
                        for item in [
                            *exceptions,
                            *validation["rare_failures"],
                        ]
                    }
                ),
                "inference_frontier": _regional_plain(
                    dict(frontier), "representation inference frontier"
                ),
                "information_boundary": information_boundary,
                "measured_cost": measured_cost,
                "output_question": question,
                "parameter_initialization": _regional_plain(
                    dict(parameter_initialization),
                    "representation parameter initialization",
                ),
                "parent_versions": parent_refs,
                "program": candidate_program,
                "proposal_history": _regional_plain(
                    proposal_history, "representation proposal history"
                ),
                "prospective_predictions": [
                    *cast(list[Any], declared_predictions),
                    *cast(
                        list[Any],
                        validation["prospective_predictions"],
                    ),
                ],
                "statistics": statistics,
                "support_roots": sorted(
                    set(cast(list[str], request.get("support_roots", [])))
                ),
            },
            status="candidate",
            epistemic_kind="induced",
            dependencies=parent_refs,
            support_roots=cast(Any, request.get("support_roots", [])),
            derivation={
                "candidate_family": [
                    edit["family"] for edit in edits
                ],
                "comparison_boundary": "frozen-training-before-holdout",
            },
        )
        candidate_refs.append(candidate_ref)
        total_work += (
            int(training["work"]) + int(validation["work"]) + 1
        )
        scored.append(
            {
                "candidate_id": candidate_id,
                "holdout": statistics["holdout"],
                "measured_cost": measured_cost,
                "output_roles": output_roles,
                "program": candidate_program,
                "score": score,
                "statistics": statistics,
                "training": statistics["training"],
            }
        )
    scored.sort(
        key=lambda item: (
            len(
                (
                    item["holdout"] if holdout else item["training"]
                )["rare_failures"]
            ),
            int(
                (
                    item["holdout"] if holdout else item["training"]
                )["errors"]
            )
            + int(
                (
                    item["holdout"] if holdout else item["training"]
                )["abstained"]
            ),
            -float(
                (
                    item["holdout"] if holdout else item["training"]
                )["coverage"]
            ),
            int(item["statistics"]["complexity_bits"]),
            int(item["measured_cost"]["evaluation_work"]),
            item["candidate_id"],
        )
    )
    winner = scored[0]
    winner_holdout = winner["holdout"]
    adequate = (
        not holdout
        or (
            float(winner_holdout["loss"]) == 0.0
            and float(winner_holdout["coverage"]) == 1.0
            and not winner_holdout["rare_failures"]
        )
    )
    prior = state["current"]["Program"].get(representation_id)
    reference = _semantic_append_record(
        state,
        record_id=representation_id,
        kind="Program",
        payload={
            "candidate_family": candidate_refs,
            "exploration_reserve": exploration_reserve,
            "information_boundary": information_boundary,
            "output_question": question,
            "program": winner["program"],
            "program_role": "representation",
            "selected_candidate": winner["candidate_id"],
            "statistics": winner["statistics"],
        },
        status="active" if adequate else "candidate",
        epistemic_kind="induced",
        dependencies=tuple(candidate_refs),
        support_roots=cast(Any, request.get("support_roots", [])),
        derivation={
            "criterion": (
                "prospective-loss-coverage-rare-cases-description-and-work"
            ),
            "goal_independent": True,
        },
    )
    frontier = (
        []
        if prior is None
        else _semantic_invalidate(
            state, (prior,), reason="representation-relearned"
        )
    )
    _semantic_reindex_record(state, reference)
    obligation_ref: dict[str, Any] | None = None
    if not adequate:
        obligation_ref = _semantic_append_record(
            state,
            record_id=(
                f"obligation:representation:{representation_id}:"
                f"{reference['content_version']}"
            ),
            kind="Obligation",
            payload={
                "purpose": "representation-inadequacy",
                "representation": reference,
                "state": "pending",
                "validation": winner_holdout,
            },
            epistemic_kind="derived",
            dependencies=(reference,),
            support_roots=cast(Any, request.get("support_roots", [])),
        )
        _semantic_reindex_record(state, obligation_ref)
    return _semantic_result(
        "learn-representation",
        "supported" if adequate else "representation-insufficient",
        candidates=scored,
        exploration_reserve=exploration_reserve,
        invalidation_frontier=frontier,
        obligation=obligation_ref,
        representation=reference,
        selected_candidate=winner["candidate_id"],
    ), max(1, total_work + len(frontier))


def _semantic_learn_procedure(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("procedure_id", "traces"),
        optional=("holdout", "max_length", "support_roots"),
    )
    procedure_id = _identifier(
        request["procedure_id"], "procedure identity"
    )
    maximum = _regional_integer(
        request.get("max_length", 8),
        "procedure maximum length",
        minimum=2,
        maximum=64,
    )
    raw_traces = request["traces"]
    raw_holdout = request.get("holdout", [])
    if (
        not isinstance(raw_traces, list)
        or not raw_traces
        or not isinstance(raw_holdout, list)
    ):
        raise FieldIntelligenceError(
            "INVALID_PROCEDURE_EVIDENCE", "procedure traces are invalid"
        )

    def normalize_trace(
        raw: Any, index: int, *, partition: str
    ) -> dict[str, Any]:
        if isinstance(raw, list):
            value: Mapping[str, Any] = {
                "steps": raw,
                "success": True,
                "trace_id": f"{partition}:{index}",
            }
        elif isinstance(raw, Mapping):
            allowed = {
                "context",
                "effects",
                "failure",
                "outcome",
                "rare_case",
                "steps",
                "success",
                "trace_id",
                "work",
            }
            if set(raw) - allowed or "steps" not in raw:
                raise FieldIntelligenceError(
                    "INVALID_PROCEDURE_EVIDENCE",
                    "procedure trace has an invalid schema",
                )
            value = raw
        else:
            raise FieldIntelligenceError(
                "INVALID_PROCEDURE_EVIDENCE",
                "procedure trace must be a step list or mapping",
            )
        steps = value["steps"]
        success = value.get("success", value.get("failure") is None)
        if (
            not isinstance(steps, list)
            or not steps
            or len(steps) > state["bounds"]["max_observations"]
            or any(not isinstance(step, Mapping) for step in steps)
            or not isinstance(success, bool)
            or not isinstance(value.get("context", {}), Mapping)
            or not isinstance(value.get("effects", {}), Mapping)
            or not isinstance(value.get("rare_case", False), bool)
        ):
            raise FieldIntelligenceError(
                "INVALID_PROCEDURE_EVIDENCE",
                "procedure trace contents are invalid",
            )
        work = _regional_integer(
            value.get("work", len(steps)),
            "procedure trace work",
            minimum=1,
            maximum=state["bounds"]["max_work"],
        )
        return {
            "context": _regional_plain(
                dict(cast(Mapping[str, Any], value.get("context", {}))),
                "procedure trace context",
            ),
            "effects": _regional_plain(
                dict(cast(Mapping[str, Any], value.get("effects", {}))),
                "procedure trace effects",
            ),
            "failure": _regional_plain(
                value.get("failure"), "procedure trace failure"
            ),
            "outcome": _regional_plain(
                value.get("outcome"), "procedure trace outcome"
            ),
            "rare_case": value.get("rare_case", False),
            "steps": [
                _regional_plain(
                    dict(cast(Mapping[str, Any], step)),
                    "procedure trace step",
                )
                for step in steps
            ],
            "success": success,
            "trace_id": _identifier(
                value.get("trace_id", f"{partition}:{index}"),
                "procedure trace identity",
            ),
            "work": work,
        }

    traces = [
        normalize_trace(raw, index, partition="training")
        for index, raw in enumerate(raw_traces)
    ]
    holdout = [
        normalize_trace(raw, index, partition="holdout")
        for index, raw in enumerate(raw_holdout)
    ]
    trace_ids = [trace["trace_id"] for trace in [*traces, *holdout]]
    if len(trace_ids) != len(set(trace_ids)):
        raise FieldIntelligenceError(
            "INVALID_PROCEDURE_EVIDENCE",
            "procedure trace identities must be unique",
        )

    structural_fields = {
        "action",
        "command",
        "kind",
        "op",
        "operation",
        "tool",
        "type",
    }

    def value_type(value: Any) -> str:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        return "json"

    def skeleton(value: Any, field: str | None = None) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): skeleton(item, str(key))
                for key, item in sorted(value.items())
            }
        if isinstance(value, list):
            return [skeleton(item) for item in value]
        if field in structural_fields:
            return {"$constant": value}
        return {"$type": value_type(value)}

    groups: dict[bytes, list[dict[str, Any]]] = {}
    work = 0
    for trace_index, trace in enumerate(traces):
        if not trace["success"]:
            continue
        steps = trace["steps"]
        for length in range(2, min(maximum, len(steps)) + 1):
            for start in range(len(steps) - length + 1):
                window = steps[start : start + length]
                key = canonical_json_bytes(skeleton(window))
                groups.setdefault(key, []).append(
                    {
                        "start": start,
                        "trace_index": trace_index,
                        "window": window,
                    }
                )
                work += 1
                if work > state["bounds"]["max_work"]:
                    return _semantic_result(
                        "learn-procedure",
                        "resource-exhausted",
                        limitations=["procedure-search-bound"],
                        procedure=None,
                    ), state["bounds"]["max_work"]
    repeated = [
        occurrences
        for occurrences in groups.values()
        if len(occurrences) >= 2
    ]
    if not repeated:
        return _semantic_result(
            "learn-procedure",
            "representation-insufficient",
            limitations=["no-repeated-successful-parameterized-subsequence"],
            procedure=None,
        ), max(1, work)

    assessed: list[dict[str, Any]] = []
    for occurrences in repeated:
        values = [row["window"] for row in occurrences]
        bindings: list[dict[str, Any]] = [
            {} for _ in occurrences
        ]
        roles: list[dict[str, Any]] = []
        signature_roles: dict[tuple[bytes, ...], str] = {}

        def anti_unify(items: Sequence[Any], path: tuple[str, ...]) -> Any:
            first_key = canonical_json_bytes(items[0])
            if all(canonical_json_bytes(item) == first_key for item in items):
                return _regional_plain(items[0], "procedure constant")
            if all(isinstance(item, Mapping) for item in items):
                key_sets = [set(cast(Mapping[str, Any], item)) for item in items]
                if all(key_set == key_sets[0] for key_set in key_sets):
                    return {
                        key: anti_unify(
                            [
                                cast(Mapping[str, Any], item)[key]
                                for item in items
                            ],
                            (*path, str(key)),
                        )
                        for key in sorted(key_sets[0])
                    }
            if all(isinstance(item, list) for item in items):
                lengths = [len(cast(list[Any], item)) for item in items]
                if all(length == lengths[0] for length in lengths):
                    return [
                        anti_unify(
                            [
                                cast(list[Any], item)[position]
                                for item in items
                            ],
                            (*path, str(position)),
                        )
                        for position in range(lengths[0])
                    ]
            signature = tuple(canonical_json_bytes(item) for item in items)
            role_name = signature_roles.get(signature)
            if role_name is None:
                role_name = f"role_{len(roles)}"
                signature_roles[signature] = role_name
                types = {value_type(item) for item in items}
                roles.append(
                    {
                        "name": role_name,
                        "paths": [".".join(path)],
                        "required": True,
                        "type": (
                            next(iter(types)) if len(types) == 1 else "json"
                        ),
                    }
                )
            else:
                for descriptor in roles:
                    if descriptor["name"] == role_name:
                        descriptor["paths"].append(".".join(path))
                        descriptor["paths"].sort()
                        break
            for index, item in enumerate(items):
                bindings[index][role_name] = _regional_plain(
                    item, "procedure role value"
                )
            return {"$role": role_name}

        template = anti_unify(values, ())
        if not isinstance(template, list):
            raise FieldIntelligenceError(
                "INVALID_PROCEDURE_EVIDENCE",
                "procedure anti-unification did not produce a sequence",
            )

        def match(
            expected: Any,
            observed: Any,
            role_bindings: dict[str, Any],
        ) -> bool:
            if isinstance(expected, Mapping) and set(expected) == {"$role"}:
                role = expected["$role"]
                prior_value = role_bindings.get(str(role), _ABSENT)
                if prior_value is _ABSENT:
                    role_bindings[str(role)] = observed
                    return True
                return canonical_json_bytes(prior_value) == canonical_json_bytes(
                    observed
                )
            if isinstance(expected, Mapping):
                return (
                    isinstance(observed, Mapping)
                    and set(expected) == set(observed)
                    and all(
                        match(
                            expected[key],
                            cast(Mapping[str, Any], observed)[key],
                            role_bindings,
                        )
                        for key in expected
                    )
                )
            if isinstance(expected, list):
                return (
                    isinstance(observed, list)
                    and len(expected) == len(observed)
                    and all(
                        match(left, right, role_bindings)
                        for left, right in zip(expected, observed)
                    )
                )
            return canonical_json_bytes(expected) == canonical_json_bytes(
                observed
            )

        support_trace_indices = sorted(
            {int(row["trace_index"]) for row in occurrences}
        )
        support_traces = [traces[index] for index in support_trace_indices]
        common_context: dict[str, Any] = {}
        if support_traces:
            first_context = support_traces[0]["context"]
            for key, value in sorted(first_context.items()):
                if (
                    isinstance(key, str)
                    and key
                    and "." not in key
                    and all(
                        key in trace["context"]
                        and canonical_json_bytes(trace["context"][key])
                        == canonical_json_bytes(value)
                        for trace in support_traces[1:]
                    )
                ):
                    common_context[key] = value
        guards = [
            {"left": f"context.{key}", "op": "eq", "right": value}
            for key, value in sorted(common_context.items())
        ]

        def trace_match(trace: Mapping[str, Any]) -> dict[str, Any] | None:
            if any(
                trace["context"].get(key, _ABSENT) != value
                for key, value in common_context.items()
            ):
                return None
            trace_steps = trace["steps"]
            for start in range(
                max(0, len(trace_steps) - len(template) + 1)
            ):
                found: dict[str, Any] = {}
                if match(
                    template,
                    trace_steps[start : start + len(template)],
                    found,
                ):
                    return found
            return None

        def project(items: Sequence[Any]) -> Any:
            first_key = canonical_json_bytes(items[0])
            if all(canonical_json_bytes(item) == first_key for item in items):
                return _regional_plain(items[0], "procedure consequence")
            signature = tuple(canonical_json_bytes(item) for item in items)
            role = signature_roles.get(signature)
            if role is not None:
                return {"$role": role}
            if all(isinstance(item, Mapping) for item in items):
                key_sets = [set(cast(Mapping[str, Any], item)) for item in items]
                if all(key_set == key_sets[0] for key_set in key_sets):
                    return {
                        key: project(
                            [
                                cast(Mapping[str, Any], item)[key]
                                for item in items
                            ]
                        )
                        for key in sorted(key_sets[0])
                    }
            alternatives = {
                canonical_json_bytes(item): _regional_plain(
                    item, "procedure consequence alternative"
                )
                for item in items
            }
            return {
                "observed_alternatives": [
                    alternatives[key] for key in sorted(alternatives)
                ]
            }

        inferred_effects = project(
            [trace["effects"] for trace in support_traces]
        )
        postconditions = project(
            [trace["outcome"] for trace in support_traces]
        )
        failure_groups: dict[bytes, dict[str, Any]] = {}
        unsafe_training: list[str] = []
        unsafe_holdout: list[str] = []
        for partition, rows, unsafe in (
            ("training", traces, unsafe_training),
            ("holdout", holdout, unsafe_holdout),
        ):
            for trace in rows:
                if trace["success"]:
                    continue
                found = trace_match(trace)
                if found is None:
                    continue
                unsafe.append(trace["trace_id"])
                failure = (
                    trace["failure"]
                    if trace["failure"] is not None
                    else {"reason": "unspecified"}
                )
                key = canonical_json_bytes(failure)
                group = failure_groups.setdefault(
                    key,
                    {
                        "count": 0,
                        "failure": failure,
                        "partitions": [],
                        "trace_ids": [],
                    },
                )
                group["count"] += 1
                group["partitions"].append(partition)
                group["trace_ids"].append(trace["trace_id"])
        failure_behavior = [
            {
                **failure_groups[key],
                "partitions": sorted(
                    set(failure_groups[key]["partitions"])
                ),
                "trace_ids": sorted(
                    set(failure_groups[key]["trace_ids"])
                ),
            }
            for key in sorted(failure_groups)
        ]
        holdout_successes = [
            trace for trace in holdout if trace["success"]
        ]
        holdout_bindings: list[dict[str, Any]] = []
        holdout_misses: list[str] = []
        rare_failures: list[str] = []
        for trace in holdout_successes:
            found = trace_match(trace)
            if found is None:
                holdout_misses.append(trace["trace_id"])
                if trace["rare_case"]:
                    rare_failures.append(trace["trace_id"])
            else:
                holdout_bindings.append(
                    {
                        "bindings": found,
                        "trace_id": trace["trace_id"],
                    }
                )
        validation_attempts = len(holdout_successes) + len(
            [trace for trace in holdout if not trace["success"]]
        )
        validation_errors = len(holdout_misses) + len(unsafe_holdout)
        validation_loss = validation_errors / max(1, validation_attempts)
        gross_steps = len(template) * len(occurrences)
        dispatch_work = len(occurrences)
        binding_work = len(roles) * len(occurrences)
        net_savings = gross_steps - dispatch_work - binding_work
        complexity_bits = 8 * len(
            canonical_json_bytes(
                {
                    "guards": guards,
                    "roles": roles,
                    "steps": template,
                }
            )
        )
        score = (
            validation_loss
            + len(unsafe_training) / max(1, len(traces))
            + (1.0 if net_savings <= 0 else 0.0)
            + complexity_bits / 1_000_000.0
            - max(0, net_savings) / 1_000_000.0
        )
        program_roles = [
            {"name": role["name"], "type": role["type"]}
            for role in roles
        ]
        arguments = {
            role["name"]: {
                "required": True,
                "type": role["type"],
                "units": None,
            }
            for role in roles
        }
        program = semantic_program_payload(
            program_kind="procedure",
            arguments=arguments,
            guards=guards,
            body={
                "effects": inferred_effects,
                "failure_behavior": failure_behavior,
                "ordering_constraints": [
                    {"after": index + 1, "before": index}
                    for index in range(len(template) - 1)
                ],
                "postconditions": postconditions,
                "preconditions": guards,
                "roles": program_roles,
                "steps": template,
            },
            writes=(
                sorted(inferred_effects)
                if isinstance(inferred_effects, Mapping)
                else ()
            ),
            emits=("proposed-actions",),
            max_horizon=max(1, len(template)),
            max_work=max(1, len(template)),
            applicability={
                "induction": "typed-trace-anti-unification",
                "training_trace_ids": [
                    trace["trace_id"] for trace in support_traces
                ],
            },
        )
        assessed.append(
            {
                "bindings": bindings,
                "candidate_id": sha256_value(
                    {
                        "guards": guards,
                        "roles": roles,
                        "steps": template,
                    }
                ),
                "failure_behavior": failure_behavior,
                "holdout_bindings": holdout_bindings,
                "holdout_misses": sorted(holdout_misses),
                "measured_cost": {
                    "binding_work": binding_work,
                    "dispatch_work": dispatch_work,
                    "gross_steps": gross_steps,
                    "net_saved_steps": net_savings,
                    "search_work": work,
                },
                "program": program,
                "rare_failures": sorted(rare_failures),
                "roles": roles,
                "score": score,
                "statistics": {
                    "complexity_bits": complexity_bits,
                    "holdout_attempts": validation_attempts,
                    "holdout_errors": validation_errors,
                    "holdout_loss": validation_loss,
                    "holdout_support": len(holdout_bindings),
                    "training_occurrences": len(occurrences),
                    "training_trace_support": len(support_traces),
                    "unsafe_holdout_failures": sorted(unsafe_holdout),
                    "unsafe_training_failures": sorted(unsafe_training),
                },
            }
        )
        work += len(occurrences) + len(holdout) + len(traces)
        if work > state["bounds"]["max_work"]:
            return _semantic_result(
                "learn-procedure",
                "resource-exhausted",
                limitations=["procedure-assessment-bound"],
                procedure=None,
            ), state["bounds"]["max_work"]
    assessed.sort(
        key=lambda item: (
            float(item["score"]),
            -int(item["measured_cost"]["net_saved_steps"]),
            item["candidate_id"],
        )
    )
    assessed = assessed[: state["bounds"]["max_alternatives"]]
    candidate_refs: list[dict[str, Any]] = []
    for candidate in assessed:
        candidate_ref = _semantic_append_record(
            state,
            record_id=(
                f"{procedure_id}:candidate:{candidate['candidate_id']}"
            ),
            kind="Program",
            payload={
                "candidate_id": candidate["candidate_id"],
                "failure_behavior": candidate["failure_behavior"],
                "holdout_bindings": candidate["holdout_bindings"],
                "holdout_misses": candidate["holdout_misses"],
                "measured_cost": candidate["measured_cost"],
                "parameter_roles": candidate["roles"],
                "program": candidate["program"],
                "rare_failures": candidate["rare_failures"],
                "statistics": candidate["statistics"],
            },
            status="candidate",
            epistemic_kind="induced",
            support_roots=cast(Any, request.get("support_roots", [])),
            derivation={
                "criterion": (
                    "heldout-transfer-safety-description-and-saved-work"
                ),
                "goal_independent": True,
            },
        )
        candidate_refs.append(candidate_ref)
    winner = assessed[0]
    statistics = winner["statistics"]
    adequate = (
        (
            not holdout
            or (
                int(statistics["holdout_errors"]) == 0
                and not winner["rare_failures"]
            )
        )
        and not statistics["unsafe_training_failures"]
        and int(winner["measured_cost"]["net_saved_steps"]) > 0
    )
    prior = state["current"]["Program"].get(procedure_id)
    reference = _semantic_append_record(
        state,
        record_id=procedure_id,
        kind="Program",
        payload={
            "candidate_family": candidate_refs,
            "failure_behavior": winner["failure_behavior"],
            "measured_cost": winner["measured_cost"],
            "parameter_roles": winner["roles"],
            "program": winner["program"],
            "program_role": "procedure",
            "selected_candidate": winner["candidate_id"],
            "statistics": statistics,
        },
        status="active" if adequate else "candidate",
        epistemic_kind="induced",
        dependencies=tuple(candidate_refs),
        support_roots=cast(Any, request.get("support_roots", [])),
        derivation={
            "criterion": "parameterized-heldout-transfer-with-net-savings",
            "goal_independent": True,
        },
    )
    frontier = (
        []
        if prior is None
        else _semantic_invalidate(
            state, (prior,), reason="procedure-relearned"
        )
    )
    _semantic_reindex_record(state, reference)
    obligation_ref: dict[str, Any] | None = None
    if not adequate:
        obligation_ref = _semantic_append_record(
            state,
            record_id=(
                f"obligation:procedure:{procedure_id}:"
                f"{reference['content_version']}"
            ),
            kind="Obligation",
            payload={
                "holdout_misses": winner["holdout_misses"],
                "net_saved_steps": winner["measured_cost"][
                    "net_saved_steps"
                ],
                "procedure": reference,
                "purpose": "procedure-transfer-or-savings-inadequacy",
                "rare_failures": winner["rare_failures"],
                "state": "pending",
                "statistics": statistics,
            },
            epistemic_kind="derived",
            dependencies=(reference,),
            support_roots=cast(Any, request.get("support_roots", [])),
        )
        _semantic_reindex_record(state, obligation_ref)
    return _semantic_result(
        "learn-procedure",
        "supported" if adequate else "representation-insufficient",
        candidates=[
            {
                "candidate_id": item["candidate_id"],
                "measured_cost": item["measured_cost"],
                "score": item["score"],
                "statistics": item["statistics"],
            }
            for item in assessed
        ],
        invalidation_frontier=frontier,
        obligation=obligation_ref,
        procedure=reference,
        selected_candidate=winner["candidate_id"],
    ), max(1, work + len(frontier))


def _semantic_ground_language(
    value: Any, bindings: Mapping[str, Any]
) -> tuple[Any, list[str]]:
    if isinstance(value, Mapping):
        if set(value) == {"$role"}:
            role = value["$role"]
            if not isinstance(role, str) or role not in bindings:
                return None, [str(role)]
            return _regional_plain(
                bindings[role], "grounded language role"
            ), []
        result: dict[str, Any] = {}
        unresolved: list[str] = []
        for key, item in value.items():
            grounded, missing = _semantic_ground_language(item, bindings)
            result[str(key)] = grounded
            unresolved.extend(missing)
        return result, sorted(set(unresolved))
    if isinstance(value, list):
        result_list: list[Any] = []
        unresolved: list[str] = []
        for item in value:
            grounded, missing = _semantic_ground_language(item, bindings)
            result_list.append(grounded)
            unresolved.extend(missing)
        return result_list, sorted(set(unresolved))
    return _regional_plain(value, "grounded language value"), []


def _semantic_learn_construction(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("construction_id", "examples", "meaning"),
        optional=(
            "components",
            "discourse_effects",
            "guards",
            "holdout",
            "source_policy",
            "speech_act",
            "support_roots",
        ),
    )
    construction_id = _identifier(
        request["construction_id"], "construction identity"
    )
    examples = request["examples"]
    holdout = request.get("holdout", [])
    if (
        not isinstance(examples, list)
        or not examples
        or not isinstance(holdout, list)
        or any(not isinstance(item, Mapping) for item in [*examples, *holdout])
    ):
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE", "construction examples are invalid"
        )
    meaning = _regional_plain(
        request["meaning"], "construction meaning"
    )
    inferred_speech_act = (
        meaning.get("speech_act")
        if isinstance(meaning, Mapping)
        else None
    )
    speech_act = _identifier(
        request.get("speech_act", inferred_speech_act or "assertion"),
        "construction speech act",
    )
    if speech_act not in SEMANTIC_SPEECH_ACTS:
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE", "construction speech act is unsupported"
        )
    guards = _regional_plain(
        request.get("guards", {}), "construction guards"
    )
    discourse_effects = _regional_plain(
        request.get("discourse_effects", {}),
        "construction discourse effects",
    )
    source_policy = _regional_plain(
        request.get(
            "source_policy",
            {
                "content_admission": (
                    "requires-independent-source-rules"
                    if speech_act in {"assertion", "prediction", "hypothesis"}
                    else "not-a-world-claim"
                ),
                "grants_authority": False,
            },
        ),
        "construction source policy",
    )
    if not all(
        isinstance(value, Mapping)
        for value in (guards, discourse_effects, source_policy)
    ) or source_policy.get("grants_authority") is not False:
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE",
            "construction guards, discourse effects, or source policy are invalid",
        )
    dependencies: list[dict[str, Any]] = []
    components = request.get("components", [])
    if not isinstance(components, list):
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE", "construction components must be a list"
        )
    for raw_component in components:
        if not isinstance(raw_component, Mapping):
            raise FieldIntelligenceError(
                "INVALID_LANGUAGE",
                "construction component reference must be typed",
            )
        component_ref, component = _semantic_reference(
            state, raw_component, require_current=True
        )
        if (
            component_ref.kind != "Program"
            or component["status"] != "active"
            or component["payload"].get("program_role") != "construction"
        ):
            raise FieldIntelligenceError(
                "INVALID_LANGUAGE",
                "construction component must be an active construction",
            )
        dependencies.append(component_ref.as_dict())
    patterns: list[list[str]] = []
    roles: set[str] = set()

    def parse_example(example: Mapping[str, Any]) -> tuple[list[str], dict[str, str]]:
        if (
            set(example) - {"bindings", "context", "speech_act", "text"}
            or not {"bindings", "text"}.issubset(example)
            or not isinstance(example["bindings"], Mapping)
            or not isinstance(example["text"], str)
            or not isinstance(example.get("context", {}), Mapping)
            or example.get("speech_act", speech_act) != speech_act
        ):
            raise FieldIntelligenceError(
                "INVALID_LANGUAGE", "construction example is invalid"
            )
        normalized_roles = {
            _identifier(name, "construction role"): _regional_text(
                value, "construction role value"
            )
            for name, value in example["bindings"].items()
        }
        return (
            _regional_induced_pattern(
                {"text": example["text"], "roles": normalized_roles}
            ),
            normalized_roles,
        )

    for example in examples:
        pattern, normalized_roles = parse_example(example)
        roles.update(normalized_roles)
        patterns.append(pattern)
    unique_patterns: dict[bytes, list[str]] = {}
    for pattern in patterns:
        unique_patterns[canonical_json_bytes(pattern)] = pattern
    pattern_variants = [
        unique_patterns[key] for key in sorted(unique_patterns)
    ]
    pattern = pattern_variants[0]
    failures = 0
    for example in holdout:
        _, normalized_roles = parse_example(example)
        if not any(
            normalized_roles
            in _regional_variable_matches(
                {"pattern": candidate},
                _regional_tokens(example["text"]),
                {},
            )
            for candidate in pattern_variants
        ):
            failures += 1
    body = {
        "components": dependencies,
        "discourse_effects": dict(discourse_effects),
        "guards": dict(guards),
        "meaning": meaning,
        "pattern": pattern,
        "roles": sorted(roles),
        "source_policy": dict(source_policy),
        "speech_act": speech_act,
    }
    if len(pattern_variants) > 1:
        body["pattern_variants"] = pattern_variants
    program = semantic_program_payload(
        program_kind="construction",
        body=body,
        max_work=max(
            1,
            max(len(candidate) for candidate in pattern_variants)
            + len(dependencies),
        ),
    )
    prior = state["current"]["Program"].get(construction_id)
    reference = _semantic_append_record(
        state,
        record_id=construction_id,
        kind="Program",
        payload={
            "program_role": "construction",
            "program": program,
            "statistics": {
                "component_count": len(dependencies),
                "example_count": len(examples),
                "holdout_count": len(holdout),
                "holdout_failures": failures,
                "role_count": len(roles),
            },
        },
        status="active" if failures == 0 else "candidate",
        epistemic_kind="induced",
        dependencies=dependencies,
        support_roots=cast(Any, request.get("support_roots", [])),
        derivation={
            "criterion": "shared-grounded-form-meaning-and-speech-act",
            "productive_roles": True,
        },
    )
    frontier = (
        []
        if prior is None
        else _semantic_invalidate(
            state, (prior,), reason="construction-relearned"
        )
    )
    _semantic_reindex_record(state, reference)
    status = "supported" if failures == 0 else "support-gap"
    result_payload = {
        "construction": reference,
        "discourse_effects": dict(discourse_effects),
        "holdout_failures": failures,
        "invalidation_frontier": frontier,
        "limitations": [] if failures == 0 else ["holdout-mismatch"],
        "pattern": pattern,
        "speech_act": speech_act,
    }
    if len(pattern_variants) > 1:
        result_payload["pattern_variants"] = pattern_variants
    return _semantic_result(
        "learn-construction",
        status,
        **result_payload,
    ), max(1, len(examples) + len(holdout) + len(frontier))


def _semantic_language_perspectives(
    state: Mapping[str, Any], value: Any
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE",
            "language perspective references must be a list",
        )
    references: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise FieldIntelligenceError(
                "INVALID_LANGUAGE",
                "language perspective reference must be typed",
            )
        reference, record = _semantic_reference(
            state,
            raw,
            expected_kind="Binding",
            require_current=True,
        )
        scope = record["scope"]
        if (
            record["status"] != "active"
            or not isinstance(scope, Mapping)
            or not isinstance(scope.get("perspective"), str)
        ):
            raise FieldIntelligenceError(
                "LANGUAGE_SUPPORT_GAP",
                "language perspective reference is not active",
            )
        references.append(reference.as_dict())
    return references


def _semantic_interpret(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("text",),
        optional=(
            "discourse_id",
            "discourse_ref",
            "listener",
            "permitted_context",
            "perspective_refs",
            "source_id",
            "speaker",
            "support_roots",
            "time",
            "utterance_ref",
        ),
    )
    text = _regional_text(request["text"], "utterance")
    speaker = request.get("speaker")
    listener = request.get("listener")
    if speaker is not None:
        speaker = _identifier(speaker, "utterance speaker")
    if listener is not None:
        listener = _identifier(listener, "utterance listener")
    source_id = request.get("source_id", speaker)
    if source_id is not None:
        source_id = _identifier(source_id, "utterance source")
    permitted_context = _regional_plain(
        request.get("permitted_context", {}),
        "permitted language context",
    )
    if not isinstance(permitted_context, Mapping):
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE", "permitted context must be a mapping"
        )
    perspective_refs = _semantic_language_perspectives(
        state, request.get("perspective_refs")
    )
    dependencies = list(perspective_refs)
    utterance_ref = request.get("utterance_ref")
    if utterance_ref is not None:
        if not isinstance(utterance_ref, Mapping):
            raise FieldIntelligenceError(
                "INVALID_LANGUAGE", "utterance reference must be typed"
            )
        resolved_utterance, utterance = _semantic_reference(
            state,
            utterance_ref,
            expected_kind="Event",
            require_current=True,
        )
        if utterance["status"] != "active":
            raise FieldIntelligenceError(
                "LANGUAGE_SUPPORT_GAP",
                "utterance evidence is not active",
            )
        dependencies.append(resolved_utterance.as_dict())
    prior_discourse_ref: dict[str, Any] | None = None
    prior_discourse: Mapping[str, Any] | None = None
    if request.get("discourse_ref") is not None:
        if not isinstance(request["discourse_ref"], Mapping):
            raise FieldIntelligenceError(
                "INVALID_LANGUAGE", "discourse reference must be typed"
            )
        resolved_discourse, prior_discourse = _semantic_reference(
            state,
            request["discourse_ref"],
            expected_kind="Binding",
            require_current=True,
        )
        if prior_discourse["status"] != "active":
            raise FieldIntelligenceError(
                "LANGUAGE_SUPPORT_GAP",
                "discourse reference is not active",
            )
        prior_discourse_ref = resolved_discourse.as_dict()
        dependencies.append(prior_discourse_ref)
    prior_referents = (
        prior_discourse["payload"].get("referents", {})
        if prior_discourse is not None
        else {}
    )
    if not isinstance(prior_referents, Mapping):
        prior_referents = {}
    alternatives: list[dict[str, Any]] = []
    work = 0
    pronouns = {"he", "her", "him", "it", "she", "that", "them", "they", "this"}
    for construction_id, raw_ref in sorted(
        state["libraries"]["constructions"].items()
    ):
        _, record = _semantic_reference(state, raw_ref, require_current=True)
        if record["status"] != "active":
            continue
        program = canonical_semantic_program_payload(
            record["payload"]["program"]
        )
        body = program["body"]
        guards = body.get("guards", {})
        if not isinstance(guards, Mapping) or any(
            permitted_context.get(name, _ABSENT) != value
            for name, value in guards.items()
        ):
            continue
        matches: list[dict[str, str]] = []
        for pattern in _regional_pattern_variants(
            {
                "pattern": body["pattern"],
                "pattern_variants": body.get("pattern_variants"),
            }
        ):
            matches.extend(
                _regional_variable_matches(
                    {"pattern": pattern},
                    _regional_tokens(text),
                    {},
                )
            )
        for bindings in matches:
            unresolved_pronouns: list[str] = []
            grounded: dict[str, Any] = {}
            for name, value in bindings.items():
                folded = value.casefold()
                if folded == "i" and speaker is not None:
                    grounded[name] = speaker
                elif folded == "you" and listener is not None:
                    grounded[name] = listener
                elif folded in pronouns:
                    resolved = prior_referents.get(folded, _ABSENT)
                    if resolved is _ABSENT:
                        grounded[name] = value
                        unresolved_pronouns.append(name)
                    else:
                        grounded[name] = resolved
                else:
                    grounded[name] = value
            grounded_meaning, unresolved_roles = _semantic_ground_language(
                body["meaning"], grounded
            )
            speech_act = body.get("speech_act", "assertion")
            if speech_act not in SEMANTIC_SPEECH_ACTS:
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "stored construction speech act is invalid",
                )
            source_policy = body.get(
                "source_policy",
                {
                    "content_admission": "requires-independent-source-rules",
                    "grants_authority": False,
                },
            )
            if (
                not isinstance(source_policy, Mapping)
                or source_policy.get("grants_authority") is not False
            ):
                raise FieldIntelligenceError(
                    "INVALID_SEMANTIC_STATE",
                    "stored construction source policy is invalid",
                )
            alternatives.append(
                {
                    "authority_granted": False,
                    "bindings": grounded,
                    "construction": raw_ref,
                    "construction_id": construction_id,
                    "content": grounded_meaning,
                    "content_status": (
                        "speaker-attributed"
                        if speech_act
                        in {"assertion", "hypothesis", "prediction"}
                        else "communicative-act"
                    ),
                    "discourse_effects": body.get(
                        "discourse_effects", {}
                    ),
                    "meaning": body["meaning"],
                    "perspective": {
                        "listener": listener,
                        "speaker": speaker,
                    },
                    "references": [
                        dict(reference) for reference in dependencies
                    ],
                    "source_id": source_id,
                    "source_policy": dict(source_policy),
                    "speech_act": speech_act,
                    "unresolved_pronouns": sorted(
                        set(unresolved_pronouns)
                    ),
                    "unresolved_roles": unresolved_roles,
                    "utterance_utf8_hex": text.encode("utf-8").hex(),
                }
            )
        work += max(1, len(body["pattern"]))
        if len(alternatives) > state["bounds"]["max_alternatives"]:
            return _semantic_result(
                "interpret",
                "resource-exhausted",
                alternatives=[],
                limitations=["interpretation-branch-bound"],
            ), min(work, state["bounds"]["max_work"])
    unique = {
        canonical_json_bytes(alternative): alternative
        for alternative in alternatives
    }
    alternatives = [unique[key] for key in sorted(unique)]
    separating_question: dict[str, Any] | None = None
    if len(alternatives) > 1:
        binding_names = sorted(
            {
                name
                for alternative in alternatives
                for name in alternative["bindings"]
            }
        )
        for name in binding_names:
            values = {
                canonical_json_bytes(
                    alternative["bindings"].get(name)
                ): alternative["bindings"].get(name)
                for alternative in alternatives
            }
            if len(values) > 1:
                separating_question = {
                    "options": [values[key] for key in sorted(values)],
                    "role": name,
                    "speech_act": "question",
                }
                break
        if separating_question is None:
            separating_question = {
                "construction_options": sorted(
                    {
                        alternative["construction_id"]
                        for alternative in alternatives
                    }
                ),
                "speech_act": "question",
                "target": "intended-construction",
            }
    discourse_reference: dict[str, Any] | None = None
    invalidation_frontier: list[dict[str, Any]] = []
    discourse_id = request.get("discourse_id")
    if discourse_id is not None:
        discourse_id = _identifier(discourse_id, "discourse identity")
        record_id = f"discourse:{discourse_id}"
        previous = state["current"]["Binding"].get(record_id)
        referents = dict(prior_referents)
        for alternative in alternatives:
            if not alternative["unresolved_pronouns"]:
                for role, value in alternative["bindings"].items():
                    referents[str(role)] = value
        commitments = [
            alternative["content"]
            for alternative in alternatives
            if alternative["speech_act"] == "commitment"
        ]
        dependency_rows = {
            canonical_json_bytes(reference): reference
            for reference in [
                *dependencies,
                *[
                    alternative["construction"]
                    for alternative in alternatives
                ],
            ]
        }
        discourse_reference = _semantic_append_record(
            state,
            record_id=record_id,
            kind="Binding",
            payload={
                "alternatives": [
                    {"value": alternative}
                    for alternative in alternatives
                ],
                "belief_semantics": (
                    "constraint-set"
                    if alternatives
                    else "deterministic"
                ),
                "commitments": commitments,
                "perspective_refs": perspective_refs,
                "presuppositions": [
                    alternative["discourse_effects"].get(
                        "presuppositions", []
                    )
                    for alternative in alternatives
                    if isinstance(
                        alternative["discourse_effects"], Mapping
                    )
                ],
                "referents": referents,
                "separating_question": separating_question,
                "temporal_scope": _regional_plain(
                    request.get("time"), "discourse temporal scope"
                ),
                "unresolved_pronouns": sorted(
                    {
                        role
                        for alternative in alternatives
                        for role in alternative["unresolved_pronouns"]
                    }
                ),
                "value": (
                    alternatives[0] if len(alternatives) == 1 else None
                ),
            },
            status="active",
            epistemic_kind="derived",
            dependencies=[
                dependency_rows[key] for key in sorted(dependency_rows)
            ],
            support_roots=cast(Any, request.get("support_roots", [])),
            scope={"discourse": discourse_id},
            derivation={
                "codec": "utf8-exact",
                "operation": "interpret",
            },
        )
        if previous is not None:
            invalidation_frontier = _semantic_invalidate(
                state, (previous,), reason="discourse-reinterpreted"
            )
        _semantic_reindex_record(state, discourse_reference)
    status = (
        "support-gap"
        if not alternatives
        else ("alternatives" if len(alternatives) > 1 else "supported")
    )
    return _semantic_result(
        "interpret",
        status,
        alternatives=alternatives,
        discourse=discourse_reference,
        interpretation=(alternatives[0] if len(alternatives) == 1 else None),
        invalidation_frontier=invalidation_frontier,
        limitations=[] if alternatives else ["no-supported-construction"],
        separating_question=separating_question,
        utterance_utf8_hex=text.encode("utf-8").hex(),
    ), max(1, work + len(invalidation_frontier))


def _semantic_resolve_surface_value(
    state: Mapping[str, Any], value: Any
) -> tuple[Any, dict[str, Any] | None]:
    if isinstance(value, Mapping) and set(value) == {
        "content_version",
        "id",
        "kind",
    }:
        reference, record = _semantic_reference(
            state, value, require_current=True
        )
        if record["status"] != "active":
            raise FieldIntelligenceError(
                "LANGUAGE_SUPPORT_GAP",
                "expression reference is not active",
            )
        return (
            record["payload"].get("value", record["payload"]),
            reference.as_dict(),
        )
    if isinstance(value, Mapping) and set(value) == {"binding_id"}:
        record = _semantic_current_record(
            state, "Binding", str(value["binding_id"])
        )
        if record["status"] != "active":
            raise FieldIntelligenceError(
                "LANGUAGE_SUPPORT_GAP",
                "expression binding is not active",
            )
        return (
            record["payload"].get("value"),
            semantic_record_ref(record).as_dict(),
        )
    return value, None


def _semantic_express(
    state: Mapping[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("bindings",),
        optional=(
            "communicative_purpose",
            "construction_id",
            "listener",
            "meaning",
            "permitted_disclosures",
            "perspective_refs",
            "speaker",
            "speech_act",
        ),
    )
    if not isinstance(request["bindings"], Mapping):
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE", "expression bindings must be a mapping"
        )
    requested_speech_act = request.get("speech_act")
    if (
        requested_speech_act is not None
        and requested_speech_act not in SEMANTIC_SPEECH_ACTS
    ):
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE", "expression speech act is unsupported"
        )
    permitted_disclosures = request.get("permitted_disclosures")
    if permitted_disclosures is not None and (
        not isinstance(permitted_disclosures, list)
        or any(not isinstance(item, str) for item in permitted_disclosures)
    ):
        raise FieldIntelligenceError(
            "INVALID_LANGUAGE",
            "permitted disclosures must be support-root identities",
        )
    permitted = (
        None
        if permitted_disclosures is None
        else set(permitted_disclosures)
    )
    perspective_refs = _semantic_language_perspectives(
        state, request.get("perspective_refs")
    )
    candidates: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    requested = request.get("construction_id")
    for construction_id, raw_ref in sorted(
        state["libraries"]["constructions"].items()
    ):
        if requested is not None and construction_id != requested:
            continue
        _, record = _semantic_reference(state, raw_ref, require_current=True)
        if record["status"] != "active":
            continue
        program = canonical_semantic_program_payload(
            record["payload"]["program"]
        )
        if (
            requested_speech_act is not None
            and program["body"].get("speech_act", "assertion")
            != requested_speech_act
        ):
            continue
        candidates.append((construction_id, raw_ref, program["body"]))
    rendered: list[dict[str, Any]] = []
    stale_reference = False
    disclosure_blocked = False
    for construction_id, raw_ref, body in candidates:
        words: list[str] = []
        valid = True
        references = [dict(raw_ref), *perspective_refs]
        resolved_bindings: dict[str, Any] = {}
        for token in _regional_pattern_variants(
            {
                "pattern": body["pattern"],
                "pattern_variants": body.get("pattern_variants"),
            }
        )[0]:
            if (
                isinstance(token, str)
                and token.startswith("{")
                and token.endswith("}")
            ):
                role = token[1:-1]
                if role not in request["bindings"]:
                    valid = False
                    break
                try:
                    resolved, resolved_ref = _semantic_resolve_surface_value(
                        state, request["bindings"][role]
                    )
                except FieldIntelligenceError as exc:
                    if exc.code not in {
                        "INVALID_SEMANTIC_REFERENCE",
                        "LANGUAGE_SUPPORT_GAP",
                        "UNKNOWN_SEMANTIC_RECORD",
                    }:
                        raise
                    stale_reference = True
                    valid = False
                    break
                if resolved_ref is not None and permitted is not None:
                    _, resolved_record = _semantic_reference(
                        state, resolved_ref, require_current=True
                    )
                    if not set(resolved_record["support_roots"]).issubset(
                        permitted
                    ):
                        disclosure_blocked = True
                        valid = False
                        break
                words.append(str(resolved))
                resolved_bindings[role] = resolved
                if resolved_ref is not None:
                    references.append(resolved_ref)
            else:
                words.append(str(token))
        if not valid:
            continue
        grounded_meaning, unresolved = _semantic_ground_language(
            body["meaning"], resolved_bindings
        )
        if unresolved or (
            "meaning" in request
            and grounded_meaning != request["meaning"]
        ):
            continue
        speech_act = body.get("speech_act", "assertion")
        source_policy = body.get(
            "source_policy",
            {
                "content_admission": "requires-independent-source-rules",
                "grants_authority": False,
            },
        )
        rendered.append(
            {
                "authority_granted": False,
                "bindings": resolved_bindings,
                "communicative_purpose": _regional_plain(
                    request.get("communicative_purpose"),
                    "communicative purpose",
                ),
                "construction": raw_ref,
                "construction_id": construction_id,
                "content": grounded_meaning,
                "epistemic_obligations": {
                    "content_admission": source_policy.get(
                        "content_admission"
                    ),
                    "disclosure_checked": permitted is not None,
                },
                "perspective": {
                    "listener": request.get("listener"),
                    "speaker": request.get("speaker"),
                },
                "references": [
                    dict(reference) for reference in references
                ],
                "speech_act": speech_act,
                "text": " ".join(words),
                "utf8_hex": " ".join(words).encode("utf-8").hex(),
            }
        )
    status = (
        "support-gap"
        if not rendered
        else ("alternatives" if len(rendered) > 1 else "supported")
    )
    return _semantic_result(
        "express",
        status,
        alternatives=rendered,
        expression=(rendered[0] if len(rendered) == 1 else None),
        limitations=(
            []
            if rendered
            else [
                (
                    "disclosure-not-permitted"
                    if disclosure_blocked
                    else (
                        "stale-expression-reference"
                        if stale_reference
                        else "no-supported-expression"
                    )
                )
            ]
        ),
    ), max(1, len(candidates))


def _semantic_update_perspective(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("agent_id", "updates"),
        optional=(
            "perspective_path",
            "source_ref",
            "support_roots",
        ),
    )
    agent_id = _identifier(request["agent_id"], "perspective agent")
    raw_path = request.get("perspective_path", [agent_id])
    if (
        not isinstance(raw_path, list)
        or not raw_path
        or len(raw_path) > 8
    ):
        raise FieldIntelligenceError(
            "INVALID_PERSPECTIVE",
            "perspective path must contain one to eight agents",
        )
    perspective_path = [
        _identifier(item, "perspective path agent") for item in raw_path
    ]
    if perspective_path[-1] != agent_id:
        raise FieldIntelligenceError(
            "INVALID_PERSPECTIVE",
            "perspective path must end at the modeled agent",
        )
    perspective_id = (
        agent_id
        if len(perspective_path) == 1
        else f"nested:{sha256_value(perspective_path)[:32]}"
    )
    scope = (
        {"perspective": agent_id}
        if len(perspective_path) == 1
        else {
            "perspective": perspective_id,
            "perspective_path": perspective_path,
        }
    )
    updates = request["updates"]
    if not isinstance(updates, Mapping) or not updates:
        raise FieldIntelligenceError(
            "INVALID_PERSPECTIVE", "perspective updates must be nonempty"
        )
    categories = {
        "beliefs",
        "goals",
        "information_access",
        "policies",
    }
    typed = bool(set(updates) & categories)
    if typed and set(updates) - categories:
        raise FieldIntelligenceError(
            "INVALID_PERSPECTIVE",
            "typed perspective updates cannot mix unscoped attributes",
        )
    flattened: list[tuple[str, str, Any]] = []
    if typed:
        for category, values in sorted(updates.items()):
            if not isinstance(values, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_PERSPECTIVE",
                    "typed perspective category must be a mapping",
                )
            for name, value in sorted(values.items()):
                normalized_name = _identifier(
                    name, "perspective category key"
                )
                flattened.append(
                    (
                        str(category),
                        f"{category}:{normalized_name}",
                        value,
                    )
                )
    else:
        flattened = [
            (
                "beliefs",
                _identifier(name, "perspective key"),
                value,
            )
            for name, value in sorted(updates.items())
        ]
    if not flattened:
        raise FieldIntelligenceError(
            "INVALID_PERSPECTIVE",
            "perspective update categories must be nonempty",
        )
    dependencies: tuple[Mapping[str, Any], ...] = ()
    if request.get("source_ref") is not None:
        source_ref, source_record = _semantic_reference(
            state, request["source_ref"], require_current=True
        )
        if source_record["status"] != "active":
            raise FieldIntelligenceError(
                "INVALID_PERSPECTIVE",
                "perspective source reference is not active",
            )
        dependencies = (source_ref.as_dict(),)
    references: list[dict[str, Any]] = []
    changed_refs: list[dict[str, Any]] = []
    for category, attribute, value in flattened:
        value_id = (
            f"perspective-value:{perspective_id}:{attribute}"
        )
        old_value = state["current"]["Value"].get(value_id)
        if old_value is not None:
            changed_refs.append(old_value)
        normalized_value = _regional_plain(value, "perspective value")
        value_ref = _semantic_append_record(
            state,
            record_id=value_id,
            kind="Value",
            payload={
                "agent_id": agent_id,
                "category": category,
                "perspective_id": perspective_id,
                "perspective_path": perspective_path,
                "value": normalized_value,
            },
            epistemic_kind="attributed",
            dependencies=dependencies,
            support_roots=cast(Any, request.get("support_roots", [])),
            scope=scope,
        )
        binding_id = (
            f"perspective:{perspective_id}:{attribute}"
        )
        old_binding = state["current"]["Binding"].get(binding_id)
        if old_binding is not None:
            changed_refs.append(old_binding)
        binding_ref = _semantic_append_record(
            state,
            record_id=binding_id,
            kind="Binding",
            payload={
                "agent_id": agent_id,
                "attribute": attribute,
                "category": category,
                "perspective_id": perspective_id,
                "perspective_path": perspective_path,
                "value": normalized_value,
                "value_ref": value_ref,
                "world_fact": False,
            },
            epistemic_kind="attributed",
            dependencies=(value_ref, *dependencies),
            support_roots=cast(Any, request.get("support_roots", [])),
            scope=scope,
        )
        references.append(binding_ref)
    frontier = _semantic_invalidate(
        state, changed_refs, reason="perspective-revision"
    )
    for reference in references:
        _semantic_reindex_record(state, reference)
    return _semantic_result(
        "update-perspective",
        "supported",
        agent_id=agent_id,
        bindings=references,
        invalidation_frontier=frontier,
        perspective_id=perspective_id,
        perspective_path=perspective_path,
        world_fact_promoted=False,
    ), max(1, 2 * len(references) + len(frontier))


def _semantic_affordance_support(
    state: Mapping[str, Any],
    affordance: Mapping[str, Any],
    action: Mapping[str, Any],
    context: Mapping[str, Any],
) -> tuple[list[str], float]:
    payload = affordance["payload"]
    roles = {
        row["name"]: row
        for row in cast(list[dict[str, Any]], payload["argument_roles"])
    }
    limitations: list[str] = []
    for name, role in roles.items():
        if role["required"] and name not in action:
            limitations.append(f"missing-action-argument:{name}")
    for name in action:
        if name not in roles:
            limitations.append(f"undeclared-action-argument:{name}")

    def binding_value(binding_id: str) -> tuple[bool, Any]:
        reference = state["current"]["Binding"].get(binding_id)
        if not isinstance(reference, Mapping):
            return False, None
        binding = resolve_semantic_record(state["records"], reference)
        if binding["status"] != "active":
            return False, None
        return True, binding["payload"].get("value", binding["payload"])

    for name, value in action.items():
        role = roles.get(name)
        if role is None:
            continue
        value_type = role["value_type"]
        valid_type = (
            (value_type == "boolean" and isinstance(value, bool))
            or (
                value_type == "integer"
                and isinstance(value, int)
                and not isinstance(value, bool)
            )
            or (
                value_type == "number"
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
            )
            or (value_type == "object" and isinstance(value, Mapping))
            or (value_type == "string" and isinstance(value, str))
        )
        if not valid_type:
            limitations.append(f"action-argument-type:{name}")
            continue
        bounds = role["bounds"]
        if bounds is not None:
            numeric = float(cast(float, value))
            if "min" in bounds and numeric < float(bounds["min"]):
                limitations.append(f"action-argument-below-bound:{name}")
            if "max" in bounds and numeric > float(bounds["max"]):
                limitations.append(f"action-argument-above-bound:{name}")
        constraints = role["binding_constraints"]
        equals_binding = constraints.get("equals_binding")
        if equals_binding is not None:
            available, expected = binding_value(equals_binding)
            if not available:
                limitations.append(
                    f"affordance-binding-unavailable:{equals_binding}"
                )
            elif value != expected:
                limitations.append(f"action-binding-mismatch:{name}")
        member_binding = constraints.get("member_of_binding")
        if member_binding is not None:
            available, allowed = binding_value(member_binding)
            if not available:
                limitations.append(
                    f"affordance-binding-unavailable:{member_binding}"
                )
            elif not isinstance(allowed, list) or value not in allowed:
                limitations.append(f"action-binding-membership:{name}")

    preconditions = payload["preconditions"]
    for category in ("observable", "latent"):
        for condition in preconditions[category]:
            binding_id = condition["binding_id"]
            available, actual = binding_value(binding_id)
            if not available:
                limitations.append(
                    f"{category}-precondition-unavailable:{binding_id}"
                )
            elif actual != condition["expected"]:
                limitations.append(
                    f"{category}-precondition-unsatisfied:{binding_id}"
                )
    supported_contexts = payload["action_context_support"]
    if supported_contexts and not any(
        all(context.get(name) == value for name, value in supported.items())
        for supported in supported_contexts
    ):
        limitations.append("unsupported-action-context")
    return sorted(set(limitations)), float(payload["risk"]["minimum"])




def _semantic_goal_satisfied(
    effects: Mapping[str, Any], goal: Mapping[str, Any]
) -> bool:
    for name, expected in goal.items():
        if name not in effects:
            return False
        actual = effects[name]
        if (
            isinstance(expected, Mapping)
            and set(expected).issubset({"max", "min"})
        ):
            if (
                "min" in expected
                and _finite(actual, "candidate effect")
                < _finite(expected["min"], "goal minimum")
            ):
                return False
            if (
                "max" in expected
                and _finite(actual, "candidate effect")
                > _finite(expected["max"], "goal maximum")
            ):
                return False
        elif actual != expected:
            return False
    return True


def _semantic_plan(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("candidates", "goal", "plan_id", "scope", "target"),
        optional=(
            "assumption_bindings",
            "bindings",
            "causal_required",
            "context",
            "criterion",
            "interval",
            "joint_id",
            "state",
            "support_roots",
            "time",
        ),
    )
    pending = state["continuation"].get("proposal")
    if (
        isinstance(pending, Mapping)
        and pending.get("status")
        in {
            "authorized",
            "cancel-requested",
            "dispatch-uncertain",
            "dispatched",
            "proposed",
            "tracking",
        }
    ):
        return _semantic_result(
            "plan",
            "support-gap",
            plan=pending.get("plan"),
            proposal=dict(pending),
            refused=[],
            limitations=["external-effect-already-pending"],
        ), 1
    plan_id = _identifier(request["plan_id"], "plan identity")
    target = _identifier(request["target"], "plan effect target")
    scope = _identifier(request["scope"], "plan effect scope")
    if (
        not isinstance(request["goal"], Mapping)
        or not isinstance(request["candidates"], list)
        or not isinstance(request.get("context", {}), Mapping)
    ):
        raise FieldIntelligenceError(
            "INVALID_PLAN", "plan goal, candidates, or context are invalid"
        )
    assumptions = request.get("assumption_bindings", [])
    if not isinstance(assumptions, list):
        raise FieldIntelligenceError(
            "INVALID_PLAN", "plan assumptions are invalid"
        )
    dependencies: list[Mapping[str, Any]] = []
    unavailable_assumptions: list[str] = []
    for binding_id in assumptions:
        normalized_binding_id = _identifier(
            binding_id, "plan assumption"
        )
        binding = _semantic_current_record(
            state, "Binding", normalized_binding_id
        )
        if binding["status"] != "active":
            unavailable_assumptions.append(normalized_binding_id)
            continue
        dependencies.append(semantic_record_ref(binding).as_dict())
    if unavailable_assumptions:
        return _semantic_result(
            "plan",
            "support-gap",
            plan=None,
            proposal=None,
            refused=[],
            limitations=[
                f"inactive-assumption:{item}"
                for item in sorted(unavailable_assumptions)
            ],
        ), max(1, len(unavailable_assumptions))

    causal_required = request.get("causal_required", False)
    if not isinstance(causal_required, bool):
        raise FieldIntelligenceError(
            "INVALID_PLAN", "causal_required must be Boolean"
        )
    criterion = request.get("criterion", "all-supported")
    if criterion != "all-supported":
        raise FieldIntelligenceError(
            "INVALID_PLAN",
            "set-valued planning requires the all-supported criterion",
        )
    viable: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    work = 0
    for candidate_index, raw in enumerate(request["candidates"]):
        if (
            not isinstance(raw, Mapping)
            or set(raw)
            - {"action", "affordance_id", "cost", "mechanism_id", "risk"}
            or not {"action", "affordance_id", "mechanism_id"}.issubset(raw)
            or not isinstance(raw.get("action"), Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_PLAN", "plan candidate is invalid"
            )
        candidate = _regional_plain(dict(raw), "plan candidate")
        affordance_id = _identifier(
            candidate["affordance_id"], "plan affordance identity"
        )
        affordance = _semantic_current_record(
            state, "Program", affordance_id
        )
        if (
            affordance["status"] != "active"
            or affordance["payload"].get("program_role") != "affordance"
        ):
            refused.append(
                {
                    "action": candidate["action"],
                    "reason": "affordance-is-not-active",
                }
            )
            continue
        affordance_ref = semantic_record_ref(affordance).as_dict()
        affordance_limitations, minimum_risk = _semantic_affordance_support(
            state,
            affordance,
            candidate["action"],
            cast(Mapping[str, Any], request.get("context", {})),
        )
        if affordance_limitations:
            refused.append(
                {
                    "action": candidate["action"],
                    "reason": "affordance-inapplicable",
                    "limitations": affordance_limitations,
                }
            )
            continue
        mechanism_id = _identifier(
            candidate["mechanism_id"], "plan mechanism identity"
        )
        mechanism = _semantic_current_record(
            state, "Program", mechanism_id
        )
        if (
            mechanism["status"] != "active"
            or mechanism["payload"].get("program_role") != "mechanism"
        ):
            refused.append(
                {
                    "action": candidate["action"],
                    "reason": "mechanism-is-not-active",
                }
            )
            continue
        mechanism_ref = semantic_record_ref(mechanism).as_dict()
        causal_authority = mechanism["payload"].get(
            "causal_authority", False
        )
        if not isinstance(causal_authority, bool):
            raise FieldIntelligenceError(
                "INVALID_PLAN",
                "mechanism causal authority must be Boolean",
            )
        if causal_required and not causal_authority:
            refused.append(
                {
                    "action": candidate["action"],
                    "reason": (
                        "observational-mechanism-has-no-causal-authority"
                    ),
                }
            )
            continue
        cost = _finite(candidate.get("cost", 0.0), "plan cost")
        risk = max(
            _finite(candidate.get("risk", 0.0), "plan risk"),
            minimum_risk,
        )
        if cost < 0.0 or risk < 0.0:
            raise FieldIntelligenceError(
                "INVALID_PLAN", "plan cost and risk must be nonnegative"
            )
        prediction_request: dict[str, Any] = {
            "action": candidate["action"],
            "mechanism_id": mechanism_id,
            "operation": "predict",
            "prediction_id": (
                f"prediction:{plan_id}:{candidate_index}:"
                f"{request.get('operation_id', sha256_value(request))}"
            ),
        }
        for name in (
            "bindings",
            "context",
            "interval",
            "joint_id",
            "state",
            "time",
        ):
            if name in request:
                prediction_request[name] = request[name]
        prediction_result, prediction_work = _semantic_predict(
            state, prediction_request
        )
        work += prediction_work
        if prediction_result["status"] not in {
            "alternatives",
            "supported",
        }:
            refused.append(
                {
                    "action": candidate["action"],
                    "reason": "prediction-support-gap",
                    "limitations": prediction_result.get(
                        "limitations", []
                    ),
                }
            )
            continue
        predicted_alternatives = prediction_result["alternatives"]
        if not all(
            _semantic_goal_satisfied(item["values"], request["goal"])
            for item in predicted_alternatives
        ):
            refused.append(
                {
                    "action": candidate["action"],
                    "reason": "goal-not-supported-across-alternatives",
                }
            )
            continue
        viable.append(
            {
                **candidate,
                "affordance_ref": affordance_ref,
                "cost": cost,
                "effects": (
                    predicted_alternatives[0]["values"]
                    if len(predicted_alternatives) == 1
                    else None
                ),
                "mechanism_ref": mechanism_ref,
                "predicted_alternatives": predicted_alternatives,
                "prediction_ref": prediction_result["prediction"],
                "risk": risk,
            }
        )
    if not viable:
        return _semantic_result(
            "plan",
            "support-gap",
            plan=None,
            proposal=None,
            refused=refused,
            limitations=["no-supported-causally-authorized-plan"],
        ), max(1, work)
    viable.sort(
        key=lambda item: (
            float(item["risk"]),
            float(item["cost"]),
            canonical_json_bytes(item["action"]),
        )
    )
    selected = viable[0]
    for reference_name in (
        "affordance_ref",
        "mechanism_ref",
        "prediction_ref",
    ):
        selected_reference = selected.get(reference_name)
        if not isinstance(selected_reference, Mapping):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_STATE",
                "viable plan candidate lost a required semantic reference",
            )
        dependencies.append(selected_reference)
    program = semantic_program_payload(
        program_kind="procedure",
        body={
            "goal": _regional_plain(request["goal"], "plan goal"),
            "steps": [selected["action"]],
        },
        max_work=1,
    )
    prior = state["current"]["Program"].get(plan_id)
    plan_ref = _semantic_append_record(
        state,
        record_id=plan_id,
        kind="Program",
        payload={
            "program_role": "plan",
            "affordance": selected["affordance_ref"],
            "action": selected["action"],
            "cost": selected["cost"],
            "effects": selected["effects"],
            "goal": _regional_plain(request["goal"], "plan goal"),
            "predicted_alternatives": selected["predicted_alternatives"],
            "prediction": selected["prediction_ref"],
            "program": program,
            "risk": selected["risk"],
            "selection_criterion": criterion,
            "status": "proposed",
        },
        epistemic_kind="derived",
        dependencies=tuple(dependencies),
        support_roots=cast(Any, request.get("support_roots", [])),
        derivation={
            "criterion": "mechanism-prediction-then-risk-then-cost"
        },
    )
    frontier = (
        []
        if prior is None
        else _semantic_invalidate(state, (prior,), reason="plan-replanned")
    )
    _semantic_reindex_record(state, plan_ref)
    prediction_record = resolve_semantic_record(
        state["records"], selected["prediction_ref"]
    )
    proposal_id = sha256_value(
        {
            "action": selected["action"],
            "affordance": selected["affordance_ref"],
            "context": request.get("context", {}),
            "expected_observation_window": prediction_record["valid_time"],
            "model": selected["mechanism_ref"],
            "plan": plan_ref,
            "prediction": selected["prediction_ref"],
            "scope": scope,
            "target": target,
        }
    )
    proposal = _semantic_new_action_proposal(
        state,
        request,
        action=selected["action"],
        affordance=selected["affordance_ref"],
        proposal_id=proposal_id,
        target=target,
        scope=scope,
        plan=plan_ref,
        prediction=selected["prediction_ref"],
        model=selected["mechanism_ref"],
        expected_observation_window=prediction_record["valid_time"],
    )
    obligation_ref = _semantic_append_record(
        state,
        record_id=f"obligation:{proposal_id}:outcome",
        kind="Obligation",
        payload={
            "expected_observation_window": prediction_record["valid_time"],
            "operation_id": proposal["operation_id"],
            "prediction": selected["prediction_ref"],
            "proposal_id": proposal_id,
            "state": "pending",
        },
        epistemic_kind="derived",
        dependencies=(plan_ref, selected["prediction_ref"]),
        support_roots=cast(Any, request.get("support_roots", [])),
        valid_time=prediction_record["valid_time"],
    )
    _semantic_reindex_record(state, obligation_ref)
    proposal["obligation"] = obligation_ref
    state["continuation"]["proposal"] = proposal
    return _semantic_result(
        "plan",
        "supported",
        plan=plan_ref,
        proposal=proposal,
        obligation=obligation_ref,
        refused=refused,
        invalidation_frontier=frontier,
    ), max(1, work + 2 + len(frontier))


def _semantic_inquire(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=(
            "affordance_id",
            "alternatives",
            "questions",
            "scope",
            "target",
        ),
        optional=("context", "support_roots"),
    )
    pending = state["continuation"].get("proposal")
    if (
        isinstance(pending, Mapping)
        and pending.get("status")
        in {
            "authorized",
            "cancel-requested",
            "dispatch-uncertain",
            "dispatched",
            "proposed",
            "tracking",
        }
    ):
        return _semantic_result(
            "inquire",
            "support-gap",
            proposal=dict(pending),
            limitations=["external-effect-already-pending"],
        ), 1
    if not isinstance(request.get("context", {}), Mapping):
        raise FieldIntelligenceError(
            "INVALID_INQUIRY", "inquiry context is invalid"
        )
    affordance_id = _identifier(
        request["affordance_id"], "inquiry affordance identity"
    )
    affordance = _semantic_current_record(
        state, "Program", affordance_id
    )
    if (
        affordance["status"] != "active"
        or affordance["payload"].get("program_role") != "affordance"
    ):
        return _semantic_result(
            "inquire",
            "support-gap",
            proposal=None,
            limitations=["affordance-is-not-active"],
        ), 1
    affordance_ref = semantic_record_ref(affordance).as_dict()
    alternatives = request["alternatives"]
    questions = request["questions"]
    if (
        not isinstance(alternatives, list)
        or len(alternatives) < 2
        or len(alternatives) > state["bounds"]["max_alternatives"]
        or not isinstance(questions, list)
        or not questions
        or len(questions) > state["bounds"]["max_alternatives"]
    ):
        raise FieldIntelligenceError(
            "INVALID_INQUIRY", "inquiry alternatives or questions are invalid"
        )
    normalized_alternatives = [
        _regional_plain(item, "inquiry alternative") for item in alternatives
    ]
    alternative_keys = [
        canonical_json_bytes(item) for item in normalized_alternatives
    ]
    if len(set(alternative_keys)) != len(alternative_keys):
        raise FieldIntelligenceError(
            "INVALID_INQUIRY", "inquiry alternatives must be unique"
        )
    scored: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for raw in questions:
        if (
            not isinstance(raw, Mapping)
            or set(raw)
            != {"cost", "outcomes", "question", "question_id", "risk"}
            or not isinstance(raw["outcomes"], Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_INQUIRY", "inquiry question is invalid"
            )
        covered: set[bytes] = set()
        partitions: list[int] = []
        if not raw["outcomes"]:
            continue
        for outcome_name, values in raw["outcomes"].items():
            _identifier(outcome_name, "inquiry outcome identity")
            if not isinstance(values, list) or not values:
                raise FieldIntelligenceError(
                    "INVALID_INQUIRY",
                    "inquiry outcome buckets must be nonempty lists",
                )
            bucket = {canonical_json_bytes(value) for value in values}
            if (
                len(bucket) != len(values)
                or not bucket.issubset(alternative_keys)
                or covered.intersection(bucket)
            ):
                raise FieldIntelligenceError(
                    "INVALID_INQUIRY",
                    "inquiry outcomes must partition the alternatives exactly once",
                )
            covered.update(bucket)
            partitions.append(len(bucket))
        if covered != set(alternative_keys):
            raise FieldIntelligenceError(
                "INVALID_INQUIRY",
                "inquiry outcomes do not cover every alternative",
            )
        action = {
            "kind": "inquiry",
            "question": raw["question"],
            "question_id": _identifier(
                raw["question_id"], "inquiry question identity"
            ),
        }
        affordance_limitations, minimum_risk = _semantic_affordance_support(
            state,
            affordance,
            action,
            cast(Mapping[str, Any], request.get("context", {})),
        )
        if affordance_limitations:
            refused.append(
                {
                    "question_id": action["question_id"],
                    "limitations": affordance_limitations,
                }
            )
            continue
        scored.append(
            {
                "cost": _finite(raw["cost"], "inquiry cost"),
                "question": raw["question"],
                "question_id": action["question_id"],
                "risk": max(
                    _finite(raw["risk"], "inquiry risk"), minimum_risk
                ),
                "worst_remaining": max(partitions),
            }
        )
    if not scored:
        return _semantic_result(
            "inquire",
            "support-gap",
            proposal=None,
            refused=refused,
            limitations=["no-separating-question"],
        ), max(1, len(questions))
    scored.sort(
        key=lambda item: (
            item["worst_remaining"],
            item["risk"],
            item["cost"],
            item["question_id"],
        )
    )
    selected = scored[0]
    if selected["worst_remaining"] >= len(alternative_keys):
        return _semantic_result(
            "inquire",
            "support-gap",
            proposal=None,
            limitations=["questions-do-not-reduce-alternatives"],
        ), len(questions)
    target = _identifier(request["target"], "inquiry target")
    scope = _identifier(request["scope"], "inquiry scope")
    proposal_id = sha256_value(
        {
            "affordance": affordance_ref,
            "question_id": selected["question_id"],
            "state_transition": state["ledger"]["transitions"],
            "target": target,
        }
    )
    proposal = _semantic_new_action_proposal(
        state,
        request,
        action={
            "kind": "inquiry",
            "question": selected["question"],
            "question_id": selected["question_id"],
        },
        affordance=affordance_ref,
        proposal_id=proposal_id,
        target=target,
        scope=scope,
    )
    obligation_id = f"obligation:inquiry:{proposal_id}"
    obligation_ref = _semantic_append_record(
        state,
        record_id=obligation_id,
        kind="Obligation",
        payload={
            "action": proposal["action"],
            "proposal_id": proposal_id,
            "state": "pending",
        },
        epistemic_kind="derived",
        dependencies=(affordance_ref,),
        support_roots=cast(Any, request.get("support_roots", [])),
        scope=scope,
    )
    _semantic_reindex_record(state, obligation_ref)
    proposal["obligation"] = obligation_ref
    state["continuation"]["proposal"] = proposal
    return _semantic_result(
        "inquire",
        "supported",
        proposal=proposal,
        obligation=obligation_ref,
        refused=refused,
        score=selected,
    ), max(1, len(questions) + 1)


def _semantic_pending_action(
    state: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    allowed_statuses: set[str],
) -> dict[str, Any]:
    proposal = state["continuation"]["proposal"]
    if (
        not isinstance(proposal, dict)
        or request.get("proposal_id") != proposal.get("proposal_id")
        or proposal.get("status") not in allowed_statuses
    ):
        raise FieldIntelligenceError(
            "ACTION_LIFECYCLE_CONFLICT",
            "action transition does not match the pending proposal phase",
        )
    return proposal


def _semantic_action_authority(
    value: Any,
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "generation",
        "grant_id",
        "grant_sha256",
        "issuer",
        "one_use",
        "operation",
        "scope",
        "target",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise FieldIntelligenceError(
            "AUTHORITY_REQUIRED",
            "action transition requires owner-bound authority metadata",
        )
    authority = _regional_plain(dict(value), "action authority")
    _regional_integer(
        authority["generation"], "action authority generation"
    )
    for name in ("grant_id", "issuer", "operation", "scope", "target"):
        authority[name] = _identifier(
            authority[name], f"action authority {name}"
        )
    _digest(authority["grant_sha256"], "action authority grant digest")
    if (
        not isinstance(authority["one_use"], bool)
        or authority["operation"] != "computer-effect"
        or authority["scope"] != proposal["scope"]
        or authority["target"] != proposal["target"]
    ):
        raise FieldIntelligenceError(
            "AUTHORITY_REQUIRED",
            "action authority does not bind the exact proposal target and scope",
        )
    return authority


def _semantic_revise_action_obligation(
    state: dict[str, Any],
    proposal: dict[str, Any],
    *,
    outcome_state: str,
    status: str,
    epistemic_kind: str,
    dependency: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    raw_ref = proposal.get("obligation")
    if not isinstance(raw_ref, Mapping):
        return None
    obligation_ref, obligation = _semantic_reference(
        state, raw_ref, require_current=True
    )
    dependencies = list(obligation["dependencies"])
    if dependency is not None:
        dependencies.append(dict(dependency))
    revised_ref = _semantic_append_record(
        state,
        record_id=obligation_ref.id,
        kind="Obligation",
        payload={**obligation["payload"], "state": outcome_state},
        status=status,
        epistemic_kind=epistemic_kind,
        dependencies=dependencies,
        support_roots=obligation["support_roots"],
        derivation={
            **obligation["derivation"],
            "action_phase": proposal["status"],
        },
        valid_time=obligation["valid_time"],
        frame=obligation["frame"],
        units=obligation["units"],
        scope=obligation["scope"],
    )
    _semantic_reindex_record(state, revised_ref)
    proposal["obligation"] = revised_ref
    return resolve_semantic_record(state["records"], revised_ref)


def _semantic_authorize_action(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("authority", "proposal_id"),
    )
    proposal = _semantic_pending_action(
        state, request, allowed_statuses={"proposed"}
    )
    authority = _semantic_action_authority(request["authority"], proposal)
    proposal["authorization"] = authority
    phase = _semantic_action_phase(
        state,
        proposal,
        request,
        phase="authorized",
        proposal_status="authorized",
        metadata={
            "authority_generation": authority["generation"],
            "grant_id": authority["grant_id"],
            "grant_sha256": authority["grant_sha256"],
        },
    )
    return _semantic_result(
        "authorize-action",
        "supported",
        phase=phase,
        proposal=proposal,
    ), 1


def _semantic_dispatch_action(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=(
            "adapter_id",
            "authority",
            "dispatch_id",
            "idempotency",
            "idempotency_key",
            "proposal_id",
        ),
    )
    proposal = _semantic_pending_action(
        state, request, allowed_statuses={"authorized"}
    )
    authority = _semantic_action_authority(request["authority"], proposal)
    if authority != proposal["authorization"]:
        raise FieldIntelligenceError(
            "AUTHORITY_REQUIRED",
            "dispatch authority differs from the authorization phase",
        )
    adapter_id = _identifier(request["adapter_id"], "action adapter identity")
    dispatch_id = _identifier(
        request["dispatch_id"], "action dispatch identity"
    )
    idempotency_key = _identifier(
        request["idempotency_key"], "action idempotency key"
    )
    idempotency = request["idempotency"]
    if idempotency not in {"guaranteed", "unknown"}:
        raise FieldIntelligenceError(
            "INVALID_ACTION_LIFECYCLE",
            "adapter idempotency must be guaranteed or unknown",
        )
    intent = {
        "action": proposal["action"],
        "adapter_id": adapter_id,
        "dispatch_id": dispatch_id,
        "episode_id": proposal["episode_id"],
        "idempotency_key": idempotency_key,
        "operation_id": proposal["operation_id"],
        "scope": proposal["scope"],
        "target": proposal["target"],
    }
    dispatch = {
        **intent,
        "idempotency": idempotency,
        "intent_sha256": sha256_value(intent),
    }
    proposal["dispatch"] = dispatch
    uncertain = idempotency == "unknown"
    proposal_status = "dispatch-uncertain" if uncertain else "dispatched"
    phase = _semantic_action_phase(
        state,
        proposal,
        request,
        phase=proposal_status,
        proposal_status=proposal_status,
        progress={"completed": 0, "total": 1},
        effect_count={"lower": 0, "upper": 1},
        metadata=dispatch,
    )
    return _semantic_result(
        "dispatch-action",
        "waiting",
        blind_retry_permitted=False,
        dispatch=dispatch,
        phase=phase,
        proposal=proposal,
        reconciliation_required=uncertain,
    ), 1


def _semantic_track_action(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("proposal_id", "status", "tracking_id"),
        optional=("adapter_receipt", "effect_count", "progress"),
    )
    proposal = _semantic_pending_action(
        state,
        request,
        allowed_statuses={
            "cancel-requested",
            "dispatch-uncertain",
            "dispatched",
            "tracking",
        },
    )
    tracking_status = request["status"]
    allowed_tracking = {
        "expired",
        "in-flight",
        "interrupted",
        "not-dispatched",
        "partial",
        "transport-delivered",
        "unknown",
    }
    if tracking_status not in allowed_tracking:
        raise FieldIntelligenceError(
            "INVALID_ACTION_LIFECYCLE", "action tracking status is invalid"
        )
    tracking_id = _identifier(
        request["tracking_id"], "action tracking identity"
    )
    if any(
        item.get("tracking_id") == tracking_id
        for item in proposal["tracking"]
    ):
        raise FieldIntelligenceError(
            "OPERATION_CONFLICT", "action tracking identity is already in use"
        )
    progress = request.get("progress", {"completed": 0, "total": 1})
    if not isinstance(progress, Mapping):
        raise FieldIntelligenceError(
            "INVALID_ACTION_LIFECYCLE", "action tracking progress is invalid"
        )
    raw_effect_count = request.get("effect_count")
    if raw_effect_count is not None and not isinstance(
        raw_effect_count, Mapping
    ):
        raise FieldIntelligenceError(
            "INVALID_ACTION_LIFECYCLE",
            "action tracking effect-count range is invalid",
        )
    effect_count = _semantic_effect_count(
        cast(Any, raw_effect_count),
        default_lower=0,
        default_upper=1,
    )
    adapter_receipt = _regional_plain(
        request.get("adapter_receipt"), "action adapter receipt"
    )
    tracking = {
        "adapter_receipt": adapter_receipt,
        "effect_count": effect_count,
        "progress": _regional_plain(dict(progress), "action tracking progress"),
        "status": tracking_status,
        "tracking_id": tracking_id,
    }
    proposal["tracking"].append(tracking)
    if tracking_status == "not-dispatched":
        proposal_status = "cancelled"
        effect_count = {"lower": 0, "upper": 0}
        obligation = _semantic_revise_action_obligation(
            state,
            proposal,
            outcome_state="canceled-before-effect",
            status="resolved",
            epistemic_kind="asserted",
        )
    else:
        proposal_status = (
            "cancel-requested"
            if proposal["status"] == "cancel-requested"
            else "tracking"
        )
        obligation = None
    phase = _semantic_action_phase(
        state,
        proposal,
        request,
        phase=(
            "reconciled-not-dispatched"
            if tracking_status == "not-dispatched"
            else "tracked"
        ),
        proposal_status=proposal_status,
        progress=cast(Any, progress),
        effect_count=effect_count,
        metadata=tracking,
    )
    return _semantic_result(
        "track-action",
        "supported" if tracking_status == "not-dispatched" else "waiting",
        blind_retry_permitted=False,
        obligation=obligation,
        phase=phase,
        proposal=proposal,
        tracking=tracking,
    ), 1


def _semantic_cancel_action(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("cancellation_id", "proposal_id", "reason"),
    )
    proposal = _semantic_pending_action(
        state,
        request,
        allowed_statuses={
            "authorized",
            "dispatch-uncertain",
            "dispatched",
            "proposed",
            "tracking",
        },
    )
    cancellation_id = _identifier(
        request["cancellation_id"], "action cancellation identity"
    )
    reason = _identifier(request["reason"], "action cancellation reason")
    dispatched = proposal["dispatch"] is not None
    cancellation = {
        "cancellation_id": cancellation_id,
        "effect_prevention_confirmed": not dispatched,
        "reason": reason,
    }
    proposal["cancellation"] = cancellation
    if dispatched:
        proposal_status = "cancel-requested"
        effect_count = proposal["phases"][-1]["effect_count"]
        obligation = _semantic_revise_action_obligation(
            state,
            proposal,
            outcome_state="abandoned-unresolved-effect",
            status="active",
            epistemic_kind="asserted",
        )
        result_status = "waiting"
    else:
        proposal_status = "cancelled"
        effect_count = {"lower": 0, "upper": 0}
        obligation = _semantic_revise_action_obligation(
            state,
            proposal,
            outcome_state="canceled-before-effect",
            status="resolved",
            epistemic_kind="asserted",
        )
        result_status = "supported"
    phase = _semantic_action_phase(
        state,
        proposal,
        request,
        phase=proposal_status,
        proposal_status=proposal_status,
        effect_count=effect_count,
        metadata=cancellation,
    )
    return _semantic_result(
        "cancel-action",
        result_status,
        effect_prevention_confirmed=not dispatched,
        obligation=obligation,
        phase=phase,
        proposal=proposal,
    ), 1


def _semantic_acknowledge(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("event_id", "proposal_id", "status"),
        optional=(
            "observation",
            "observation_verified",
            "support_roots",
            "transport_receipt",
        ),
    )
    proposal = _semantic_pending_action(
        state,
        request,
        allowed_statuses={
            "cancel-requested",
            "dispatch-uncertain",
            "dispatched",
            "tracking",
        },
    )
    status = request["status"]
    if status not in {"failed", "succeeded", "unknown"}:
        raise FieldIntelligenceError(
            "INVALID_ACTION_LIFECYCLE",
            "action acknowledgment status is invalid",
        )
    observation = request.get("observation")
    observation_verified = request.get("observation_verified", False)
    if (
        not isinstance(observation_verified, bool)
        or (
            observation is not None
            and not isinstance(observation, Mapping)
        )
        or (observation_verified and not isinstance(observation, Mapping))
    ):
        raise FieldIntelligenceError(
            "ASSESSMENT_CONFLICT",
            "verified action observation must be a mapping",
        )
    event_id = _identifier(request["event_id"], "acknowledgment event")
    if event_id in state["current"]["Event"]:
        raise FieldIntelligenceError(
            "OPERATION_CONFLICT",
            "acknowledgment event identity is already in use",
        )
    event_dependencies = [
        proposal[name]
        for name in ("plan", "prediction")
        if isinstance(proposal.get(name), Mapping)
    ]
    event_ref = _semantic_append_record(
        state,
        record_id=event_id,
        kind="Event",
        payload={
            "observation": observation,
            "observation_verified": observation_verified,
            "operation_id": proposal["operation_id"],
            "proposal_id": proposal["proposal_id"],
            "transport_receipt": _regional_plain(
                request.get("transport_receipt"),
                "action transport receipt",
            ),
            "transport_status": status,
        },
        epistemic_kind="observed" if observation_verified else "asserted",
        dependencies=tuple(event_dependencies),
        support_roots=cast(Any, request.get("support_roots", [])),
        valid_time={
            "start": state["time"]["now"],
            "end": state["time"]["now"],
        },
    )
    _semantic_reindex_record(state, event_ref)
    proposal["acknowledgment"] = event_ref
    effect_count = (
        {"lower": 1, "upper": 1}
        if status == "succeeded" and observation_verified
        else (
            {"lower": 0, "upper": 0}
            if status == "failed"
            else {"lower": 0, "upper": 1}
        )
    )
    phase = _semantic_action_phase(
        state,
        proposal,
        request,
        phase="acknowledged",
        proposal_status="acknowledged",
        progress={
            "completed": 1 if status != "unknown" else 0,
            "total": 1,
        },
        effect_count=effect_count,
        metadata={
            "event": event_ref,
            "observation_verified": observation_verified,
            "transport_status": status,
        },
    )
    prediction_ref = proposal.get("prediction")
    if isinstance(prediction_ref, Mapping):
        obligation_state = (
            "outcome-observed-awaiting-assessment"
            if observation_verified
            else "awaiting-verified-observation"
        )
        obligation_status = "active"
    else:
        obligation_state = (
            "fulfilled"
            if status == "succeeded"
            else ("failed" if status == "failed" else "unresolved")
        )
        obligation_status = "resolved" if status != "unknown" else "active"
    obligation = _semantic_revise_action_obligation(
        state,
        proposal,
        outcome_state=obligation_state,
        status=obligation_status,
        epistemic_kind="observed" if observation_verified else "asserted",
        dependency=event_ref,
    )
    return _semantic_result(
        "acknowledgment",
        "supported" if status != "unknown" else "waiting",
        assessment_required=(
            isinstance(prediction_ref, Mapping) and observation_verified
        ),
        event=event_ref,
        obligation=obligation,
        phase=phase,
        proposal=proposal,
        transport_is_world_observation=observation_verified,
    ), 1


def _semantic_register(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("kind", "payload", "record_id"),
        optional=(
            "applicability",
            "dependencies",
            "epistemic_kind",
            "frame",
            "scope",
            "status",
            "support_roots",
            "units",
            "valid_time",
        ),
    )
    if not isinstance(request["payload"], Mapping):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_RECORD", "semantic payload must be a mapping"
        )
    dependencies = request.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_REFERENCE",
            "semantic dependencies must be a list",
        )
    normalized_dependencies: list[dict[str, Any]] = []
    for raw in dependencies:
        if not isinstance(raw, Mapping):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_REFERENCE",
                "semantic dependency must be a typed reference",
            )
        reference, _ = _semantic_reference(state, raw)
        normalized_dependencies.append(reference.as_dict())
    kind = request["kind"]
    if kind not in SEMANTIC_RECORD_KINDS:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_RECORD", "semantic family is invalid"
        )
    record_id = _identifier(request["record_id"], "semantic record identity")
    prior = (
        state["current"].get(kind, {}).get(record_id)
        if isinstance(kind, str)
        else None
    )
    valid_time = (
        _semantic_interval(
            cast(Any, request.get("valid_time")),
            default=float(state["time"]["now"]),
        )
        if kind == "Event"
        else cast(Any, request.get("valid_time"))
    )
    reference = _semantic_append_record(
        state,
        record_id=record_id,
        kind=kind,
        payload=request["payload"],
        status=str(request.get("status", "active")),
        epistemic_kind=str(request.get("epistemic_kind", "asserted")),
        dependencies=normalized_dependencies,
        support_roots=cast(Any, request.get("support_roots", [])),
        applicability=cast(Any, request.get("applicability")),
        valid_time=valid_time,
        frame=cast(Any, request.get("frame", state["frame"])),
        units=cast(Any, request.get("units")),
        scope=cast(Any, request.get("scope", state["scope"])),
    )
    frontier = (
        []
        if prior is None
        else _semantic_invalidate(
            state, (prior,), reason="explicit-semantic-revision"
        )
    )
    _semantic_reindex_record(state, reference)
    return _semantic_result(
        "register",
        "supported",
        record=reference,
        invalidation_frontier=frontier,
    ), max(1, 1 + len(frontier))


def _semantic_mechanism_step(
    state: Mapping[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("mechanism_id", "state"),
        optional=("action", "context", "interval"),
    )
    for name in ("state", "action", "context", "interval"):
        if not isinstance(request.get(name, {}), Mapping):
            raise FieldIntelligenceError(
                "INVALID_MECHANISM_STATE",
                f"mechanism {name} must be a mapping",
            )
    mechanism, program = _semantic_program_record(
        state,
        _identifier(request["mechanism_id"], "mechanism identity"),
    )
    try:
        outcome = execute_semantic_program(
            program,
            request["state"],
            action=cast(Mapping[str, Any], request.get("action", {})),
            context=cast(Mapping[str, Any], request.get("context", {})),
            interval=cast(Mapping[str, Any], request.get("interval", {})),
        )
    except (RegionalFieldError, ValueError) as exc:
        raise FieldIntelligenceError(
            "INVALID_MECHANISM_STATE",
            f"mechanism input cannot execute: {exc}",
        ) from exc
    return _semantic_result(
        "mechanism-step",
        outcome["status"],
        mechanism=semantic_record_ref(mechanism).as_dict(),
        outcome=outcome,
    ), max(1, int(outcome["work"]))


def _semantic_advance_time(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("event_id",),
        optional=("duration", "now", "support_roots"),
    )
    if ("duration" in request) == ("now" in request):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_TIME",
            "advance-time requires exactly one of duration or now",
        )
    old_now = float(state["time"]["now"])
    new_now = (
        old_now
        + _finite(request["duration"], "semantic time duration")
        if "duration" in request
        else _finite(request["now"], "semantic now")
    )
    if new_now < old_now:
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_TIME", "semantic time cannot move backward"
        )
    event_id = _identifier(request["event_id"], "time event identity")
    if event_id in state["current"]["Event"]:
        raise FieldIntelligenceError(
            "OPERATION_CONFLICT", "time event identity already exists"
        )
    event_ref = _semantic_append_record(
        state,
        record_id=event_id,
        kind="Event",
        payload={"from": old_now, "kind": "time-advanced", "to": new_now},
        epistemic_kind="observed",
        support_roots=cast(Any, request.get("support_roots", [])),
        valid_time={"start": old_now, "end": new_now},
    )
    _semantic_reindex_record(state, event_ref)
    expired: list[dict[str, Any]] = []
    for obligation_id, raw_ref in list(
        state["indexes"]["obligations"].items()
    ):
        obligation = resolve_semantic_record(state["records"], raw_ref)
        valid_time = obligation["valid_time"]
        if (
            obligation["status"] == "active"
            and isinstance(valid_time, Mapping)
            and float(valid_time.get("end", new_now)) < new_now
        ):
            revised = _semantic_append_record(
                state,
                record_id=obligation_id,
                kind="Obligation",
                payload={**obligation["payload"], "state": "expired"},
                status="expired",
                epistemic_kind="derived",
                dependencies=(*obligation["dependencies"], event_ref),
                support_roots=obligation["support_roots"],
                derivation={"time_event": event_ref},
                valid_time=obligation["valid_time"],
                frame=obligation["frame"],
                units=obligation["units"],
                scope=obligation["scope"],
            )
            _semantic_reindex_record(state, revised)
            expired.append(revised)
    awaiting: list[dict[str, Any]] = []
    for prediction_id, raw_ref in state["indexes"]["predictions"].items():
        prediction = resolve_semantic_record(state["records"], raw_ref)
        valid_time = prediction["valid_time"]
        if (
            prediction["status"] == "active"
            and isinstance(valid_time, Mapping)
            and float(valid_time.get("end", new_now)) <= new_now
        ):
            awaiting.append(
                {
                    "prediction_id": prediction_id,
                    "reference": raw_ref,
                }
            )
    status = "waiting" if awaiting else "supported"
    return _semantic_result(
        "advance-time",
        status,
        event=event_ref,
        expired_obligations=expired,
        awaiting_outcomes=awaiting,
        now=new_now,
        limitations=(
            ["delayed-outcomes-pending"] if awaiting else []
        ),
    ), max(1, 1 + len(expired) + len(awaiting))


def _semantic_revoke(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("reason", "target"),
        optional=("obligation_ref",),
    )
    if not isinstance(request["target"], Mapping):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_REFERENCE", "revocation target is invalid"
        )
    target_ref, target = _semantic_reference(
        state, request["target"], require_current=True
    )
    authorizing_ref: dict[str, Any] | None = None
    if request.get("obligation_ref") is not None:
        obligation_ref, obligation = _semantic_reference(
            state, request["obligation_ref"], require_current=True
        )
        if (
            obligation_ref.kind != "Obligation"
            or obligation["status"] != "active"
            or obligation["payload"].get("action") not in {
                "forget",
                "revoke",
            }
            or obligation["payload"].get("target") != target_ref.as_dict()
        ):
            raise FieldIntelligenceError(
                "AUTHORITY_REQUIRED",
                "revocation obligation does not authorize the target",
            )
        authorizing_ref = obligation_ref.as_dict()
    if target_ref.kind not in {"Assessment", "Obligation", "Program", "Value"}:
        if authorizing_ref is None:
            raise FieldIntelligenceError(
                "AUTHORITY_REQUIRED",
                "revoking durable world facts requires an explicit obligation",
            )
    dependencies = list(target["dependencies"])
    if authorizing_ref is not None:
        dependencies.append(authorizing_ref)
    revoked_ref = _semantic_append_record(
        state,
        record_id=target_ref.id,
        kind=target_ref.kind,
        payload=target["payload"],
        status="revoked",
        epistemic_kind="derived",
        dependencies=dependencies,
        support_roots=target["support_roots"],
        derivation={
            **target["derivation"],
            "reason": request["reason"],
            "revocation_obligation": authorizing_ref,
        },
        applicability=target["applicability"],
        valid_time=target["valid_time"],
        frame=target["frame"],
        units=target["units"],
        scope=target["scope"],
    )
    frontier = _semantic_invalidate(
        state, (target_ref,), reason="semantic-revocation"
    )
    _semantic_reindex_record(state, revoked_ref)
    return _semantic_result(
        "revoke",
        "supported",
        previous=target_ref.as_dict(),
        revoked=revoked_ref,
        invalidation_frontier=frontier,
    ), max(1, 1 + len(frontier))


def _semantic_migrate(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=(
            "affected_bindings",
            "mapping",
            "migration_id",
            "new_schema",
            "old_schema",
            "preservation",
            "recovery",
            "replacement_payload",
            "resource_bounds",
            "source_access",
            "target",
        ),
        optional=("applicability", "support_roots"),
    )
    if not isinstance(request["target"], Mapping) or not isinstance(
        request["replacement_payload"], Mapping
    ):
        raise FieldIntelligenceError(
            "INVALID_MIGRATION", "semantic migration payload is invalid"
        )
    target_ref, target = _semantic_reference(
        state, request["target"], require_current=True
    )
    migration_id = _identifier(
        request["migration_id"], "migration identity"
    )
    old_schema = _identifier(
        request["old_schema"], "migration old schema"
    )
    new_schema = _identifier(
        request["new_schema"], "migration new schema"
    )

    def payload_schema(payload: Mapping[str, Any], kind: str) -> str:
        if isinstance(payload.get("schema"), str):
            return cast(str, payload["schema"])
        program = payload.get("program")
        if isinstance(program, Mapping) and isinstance(
            program.get("schema"), str
        ):
            return cast(str, program["schema"])
        return f"semantic-record:{kind}"

    if (
        payload_schema(target["payload"], target_ref.kind) != old_schema
        or payload_schema(
            request["replacement_payload"], target_ref.kind
        )
        != new_schema
    ):
        raise FieldIntelligenceError(
            "INVALID_MIGRATION",
            "migration schema identities do not match the record payloads",
        )
    raw_mapping = request["mapping"]
    if not isinstance(raw_mapping, list) or not raw_mapping:
        raise FieldIntelligenceError(
            "INVALID_MIGRATION", "migration mapping must be nonempty"
        )
    mapping: list[dict[str, Any]] = []
    has_loss = False
    for raw in raw_mapping:
        if (
            not isinstance(raw, Mapping)
            or set(raw) != {"new", "old", "semantics"}
            or raw["semantics"]
            not in {
                "exact",
                "lost",
                "many-to-one",
                "one-to-many",
                "set-valued",
            }
        ):
            raise FieldIntelligenceError(
                "INVALID_MIGRATION", "migration mapping row is invalid"
            )
        semantics = str(raw["semantics"])
        new_value = _regional_plain(
            raw["new"], "migration new mapping value"
        )
        if semantics in {"one-to-many", "set-valued"} and (
            not isinstance(new_value, list) or len(new_value) < 2
        ):
            raise FieldIntelligenceError(
                "INVALID_MIGRATION",
                "set-valued migration mappings require alternatives",
            )
        if semantics == "lost":
            has_loss = True
            if new_value is not None:
                raise FieldIntelligenceError(
                    "INVALID_MIGRATION",
                    "lost migration mappings must have a null new value",
                )
        mapping.append(
            {
                "new": new_value,
                "old": _regional_plain(
                    raw["old"], "migration old mapping value"
                ),
                "semantics": semantics,
            }
        )
    preservation = request["preservation"]
    if not isinstance(preservation, Mapping) or set(preservation) != {
        "approximate_queries",
        "exact_queries",
        "lost_distinctions",
    }:
        raise FieldIntelligenceError(
            "INVALID_MIGRATION",
            "migration preservation declaration is invalid",
        )
    exact_queries = preservation["exact_queries"]
    approximate_queries = preservation["approximate_queries"]
    lost_distinctions = preservation["lost_distinctions"]
    if (
        not isinstance(exact_queries, list)
        or any(not isinstance(item, str) or not item for item in exact_queries)
        or not isinstance(approximate_queries, list)
        or not isinstance(lost_distinctions, list)
        or any(
            not isinstance(item, str) or not item
            for item in lost_distinctions
        )
    ):
        raise FieldIntelligenceError(
            "INVALID_MIGRATION",
            "migration preserved query sets are invalid",
        )
    normalized_approximate: list[dict[str, Any]] = []
    for row in approximate_queries:
        if (
            not isinstance(row, Mapping)
            or set(row) - {"error_bound", "query", "units"}
            or not {"error_bound", "query"}.issubset(row)
            or not isinstance(row["query"], str)
            or not row["query"]
        ):
            raise FieldIntelligenceError(
                "INVALID_MIGRATION",
                "approximate migration query declaration is invalid",
            )
        error_bound = _finite(
            row["error_bound"], "migration approximation error"
        )
        if error_bound < 0.0:
            raise FieldIntelligenceError(
                "INVALID_MIGRATION",
                "migration approximation error must be nonnegative",
            )
        normalized_approximate.append(
            {
                "error_bound": error_bound,
                "query": row["query"],
                "units": _regional_plain(
                    row.get("units"), "migration approximation units"
                ),
            }
        )
    if has_loss and not lost_distinctions:
        raise FieldIntelligenceError(
            "INVALID_MIGRATION",
            "lossy migration must name its lost distinctions",
        )
    if set(exact_queries) & set(lost_distinctions):
        raise FieldIntelligenceError(
            "INVALID_MIGRATION",
            "a migration query cannot be both exact and lost",
        )
    affected_bindings = request["affected_bindings"]
    if not isinstance(affected_bindings, list):
        raise FieldIntelligenceError(
            "INVALID_MIGRATION",
            "affected migration bindings must be a list",
        )
    affected: list[dict[str, Any]] = []
    affected_ids: set[str] = set()
    for row in affected_bindings:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"replacement_payload", "target"}
            or not isinstance(row["target"], Mapping)
            or not isinstance(row["replacement_payload"], Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_MIGRATION",
                "affected migration binding row is invalid",
            )
        binding_ref, binding = _semantic_reference(
            state,
            row["target"],
            expected_kind="Binding",
            require_current=True,
        )
        if binding_ref.id in affected_ids:
            raise FieldIntelligenceError(
                "INVALID_MIGRATION",
                "affected migration binding is duplicated",
            )
        affected_ids.add(binding_ref.id)
        affected.append(
            {
                "record": binding,
                "replacement_payload": _regional_plain(
                    dict(row["replacement_payload"]),
                    "migrated Binding payload",
                ),
                "source": binding_ref.as_dict(),
            }
        )
    source_access = request["source_access"]
    if not isinstance(source_access, Mapping) or set(source_access) != {
        "available",
        "required",
    }:
        raise FieldIntelligenceError(
            "INVALID_MIGRATION",
            "migration source-access declaration is invalid",
        )
    required_sources = source_access["required"]
    available_sources = source_access["available"]
    if (
        not isinstance(required_sources, list)
        or not isinstance(available_sources, list)
        or any(not isinstance(item, str) for item in required_sources)
        or any(not isinstance(item, str) for item in available_sources)
    ):
        raise FieldIntelligenceError(
            "INVALID_MIGRATION",
            "migration source identities are invalid",
        )
    missing_sources = sorted(
        set(required_sources) - set(available_sources)
    )
    recovery = request["recovery"]
    if (
        not isinstance(recovery, Mapping)
        or set(recovery)
        != {"available", "requires_authorization", "route"}
        or not isinstance(recovery["available"], bool)
        or not isinstance(recovery["requires_authorization"], bool)
    ):
        raise FieldIntelligenceError(
            "INVALID_MIGRATION",
            "migration recovery declaration is invalid",
        )
    resource_bounds = request["resource_bounds"]
    if (
        not isinstance(resource_bounds, Mapping)
        or set(resource_bounds) != {"max_output_bytes", "max_work"}
    ):
        raise FieldIntelligenceError(
            "INVALID_MIGRATION",
            "migration resource bounds are invalid",
        )
    max_work = _regional_integer(
        resource_bounds["max_work"],
        "migration work bound",
        minimum=1,
        maximum=state["bounds"]["max_work"],
    )
    max_output_bytes = _regional_integer(
        resource_bounds["max_output_bytes"],
        "migration output byte bound",
        minimum=1,
        maximum=64 * 1024 * 1024,
    )
    output_bytes = len(canonical_json_bytes(request["replacement_payload"])) + sum(
        len(canonical_json_bytes(row["replacement_payload"]))
        for row in affected
    )
    required_work = max(
        1,
        1 + len(mapping) + len(affected) + (output_bytes + 255) // 256,
    )
    progress = {
        "completed": 0,
        "output_bytes": output_bytes,
        "required": required_work,
    }
    if required_work > max_work or output_bytes > max_output_bytes:
        return _semantic_result(
            "migrate",
            "resource-exhausted",
            limitations=["migration-resource-bound"],
            migration=None,
            progress=progress,
        ), 1
    program_body = {
        "affected_bindings": [
            {
                "replacement_payload_sha256": sha256_value(
                    row["replacement_payload"]
                ),
                "source": row["source"],
            }
            for row in affected
        ],
        "mapping": mapping,
        "new_schema": new_schema,
        "old_schema": old_schema,
        "preservation": {
            "approximate_queries": normalized_approximate,
            "exact_queries": sorted(set(exact_queries)),
            "lost_distinctions": sorted(set(lost_distinctions)),
        },
        "progress": progress,
        "recovery": _regional_plain(
            dict(recovery), "migration recovery declaration"
        ),
        "schema": "cassifi.semantic-migration-program.v1",
        "source_access": {
            "available": sorted(set(available_sources)),
            "required": sorted(set(required_sources)),
        },
        "target": target_ref.as_dict(),
    }
    program = semantic_program_payload(
        program_kind="migration",
        body=program_body,
        reads=[
            target_ref.id,
            *[row["source"]["id"] for row in affected],
        ],
        writes=[
            target_ref.id,
            *[row["source"]["id"] for row in affected],
        ],
        max_work=required_work,
    )
    migration_dependencies = [
        target_ref.as_dict(),
        *[row["source"] for row in affected],
    ]
    if missing_sources:
        migration_ref = _semantic_append_record(
            state,
            record_id=migration_id,
            kind="Program",
            payload={
                "program": program,
                "program_role": "migration",
                "progress": progress,
                "status_detail": "awaiting-source-access",
            },
            status="candidate",
            epistemic_kind="derived",
            dependencies=migration_dependencies,
            support_roots=cast(Any, request.get("support_roots", [])),
            derivation={"lifecycle_handler": "migrate"},
        )
        obligation_ref = _semantic_append_record(
            state,
            record_id=f"obligation:migration:{migration_id}",
            kind="Obligation",
            payload={
                "migration": migration_ref,
                "missing_sources": missing_sources,
                "purpose": "migration-source-access",
                "recovery": dict(recovery),
                "state": "pending",
            },
            epistemic_kind="derived",
            dependencies=(migration_ref,),
            support_roots=cast(Any, request.get("support_roots", [])),
        )
        _semantic_reindex_record(state, migration_ref)
        _semantic_reindex_record(state, obligation_ref)
        return _semantic_result(
            "migrate",
            "support-gap",
            limitations=["migration-source-access-unavailable"],
            migration=migration_ref,
            obligation=obligation_ref,
            progress=progress,
        ), max(1, required_work)
    migrated_ref = _semantic_append_record(
        state,
        record_id=target_ref.id,
        kind=target_ref.kind,
        payload=request["replacement_payload"],
        status="active",
        epistemic_kind="derived",
        support_roots=sorted(
            set(
                target["support_roots"]
                + list(cast(Any, request.get("support_roots", [])))
            )
        ),
        derivation={
            "mapping": mapping,
            "migration_id": migration_id,
            "source": target_ref.as_dict(),
        },
        applicability=cast(
            Any, request.get("applicability", target["applicability"])
        ),
        valid_time=target["valid_time"],
        frame=target["frame"],
        units=target["units"],
        scope=target["scope"],
    )
    frontier = _semantic_invalidate(
        state, (target_ref,), reason=f"migration:{migration_id}"
    )
    migrated_bindings: list[dict[str, Any]] = []
    for row in affected:
        source = row["record"]
        source_ref = SemanticRef.from_dict(row["source"])
        migrated_binding = _semantic_append_record(
            state,
            record_id=source_ref.id,
            kind="Binding",
            payload=row["replacement_payload"],
            status="active",
            epistemic_kind="derived",
            dependencies=(migrated_ref,),
            support_roots=source["support_roots"],
            derivation={
                "mapping": mapping,
                "migration_id": migration_id,
                "source": row["source"],
            },
            applicability=source["applicability"],
            valid_time=source["valid_time"],
            frame=source["frame"],
            units=source["units"],
            scope=source["scope"],
        )
        frontier.extend(
            _semantic_invalidate(
                state,
                (row["source"],),
                reason=f"migration:{migration_id}",
            )
        )
        _semantic_reindex_record(state, migrated_binding)
        migrated_bindings.append(migrated_binding)
    progress["completed"] = required_work
    completed_body = {
        **program_body,
        "progress": progress,
    }
    completed_program = semantic_program_payload(
        program_kind="migration",
        body=completed_body,
        reads=program["effects"]["reads"],
        writes=program["effects"]["writes"],
        max_work=required_work,
    )
    migration_ref = _semantic_append_record(
        state,
        record_id=migration_id,
        kind="Program",
        payload={
            "migrated_bindings": migrated_bindings,
            "migrated_record": migrated_ref,
            "program": completed_program,
            "program_role": "migration",
            "progress": progress,
            "status_detail": "complete",
        },
        status="active",
        epistemic_kind="derived",
        dependencies=(migrated_ref, *migrated_bindings),
        support_roots=sorted(
            set(
                target["support_roots"]
                + list(cast(Any, request.get("support_roots", [])))
            )
        ),
        derivation={"lifecycle_handler": "migrate"},
    )
    prior_obligation = state["current"]["Obligation"].get(
        f"obligation:migration:{migration_id}"
    )
    resolved_obligation: dict[str, Any] | None = None
    if prior_obligation is not None:
        obligation = resolve_semantic_record(
            state["records"], prior_obligation
        )
        resolved_obligation = _semantic_append_record(
            state,
            record_id=f"obligation:migration:{migration_id}",
            kind="Obligation",
            payload={
                **obligation["payload"],
                "migration": migration_ref,
                "state": "resolved",
            },
            epistemic_kind="derived",
            dependencies=(migration_ref,),
            support_roots=obligation["support_roots"],
            derivation={"resolution": "migration-complete"},
        )
        _semantic_reindex_record(state, resolved_obligation)
    _semantic_reindex_record(state, migrated_ref)
    _semantic_reindex_record(state, migration_ref)
    return _semantic_result(
        "migrate",
        "supported",
        invalidation_frontier=frontier,
        migrated=migrated_ref,
        migrated_bindings=migrated_bindings,
        migration=migration_ref,
        previous=target_ref.as_dict(),
        progress=progress,
        resolved_obligation=resolved_obligation,
    ), max(1, required_work + len(frontier))
_SEMANTIC_DEVELOPMENT_PROVENANCES = frozenset({"caller-supplied", "executed"})


def _semantic_development_execution_plan(
    state: Mapping[str, Any],
    information: Mapping[str, Any],
    allocation: Mapping[str, int],
    requested: Any = _ABSENT,
) -> dict[str, Any]:
    """Normalize only work inputs; outcomes are computed when the child runs."""
    raw = requested
    if raw is _ABSENT and "numeric_work" in information:
        raw = {"kind": "numeric-reduction", "values": information["numeric_work"]}
    if raw is _ABSENT and "field_work" in information:
        field_work = information["field_work"]
        raw = (
            {"kind": "field-read", "binding_ids": field_work}
            if isinstance(field_work, list)
            else {
                "kind": "field-read",
                **dict(field_work),
            }
            if isinstance(field_work, Mapping)
            else {"kind": "field-read", "binding_ids": field_work}
        )
    if raw is None or (
        isinstance(raw, Mapping) and raw.get("kind") == "none"
    ):
        return {"kind": "none"}
    if raw is _ABSENT:
        return {"kind": "none"}
    if isinstance(raw, list):
        raw = {"kind": "numeric-reduction", "values": raw}
    if not isinstance(raw, Mapping):
        raise FieldIntelligenceError(
            "INVALID_DEVELOPMENT", "development executed work must be a mapping"
        )
    kind = raw.get("kind")
    if kind in {"numeric", "numeric-reduction"}:
        values = raw.get("values", raw.get("numeric_values"))
        if (
            not isinstance(values, list)
            or not values
            or len(values) > allocation["work"]
            or len(values) > state["bounds"]["max_work"]
        ):
            raise FieldIntelligenceError(
                "INVALID_DEVELOPMENT",
                "numeric development work must be bounded and nonempty",
            )
        normalized = [_finite(value, "development numeric work value") for value in values]
        return {"kind": "numeric-reduction", "values": normalized}
    if kind in {"field", "field-read"}:
        raw_ids = raw.get("binding_ids")
        if raw_ids is None and "binding_id" in raw:
            raw_ids = [raw["binding_id"]]
        if (
            not isinstance(raw_ids, list)
            or not raw_ids
            or len(raw_ids) > allocation["work"]
            or len(raw_ids) > state["bounds"]["max_work"]
            or any(not isinstance(item, str) or not item for item in raw_ids)
        ):
            raise FieldIntelligenceError(
                "INVALID_DEVELOPMENT",
                "field development work must name bounded bindings",
            )
        return {
            "kind": "field-read",
            "binding_ids": [_identifier(item, "development work binding") for item in raw_ids],
        }
    raise FieldIntelligenceError(
        "INVALID_DEVELOPMENT",
        "development executed work kind is unsupported",
    )


def _semantic_execute_development_work(
    state: Mapping[str, Any], plan: Mapping[str, Any]
) -> dict[str, Any] | None:
    kind = plan.get("kind")
    if kind == "none":
        return None
    if kind == "numeric-reduction":
        values = plan["values"]
        total = _finite(math.fsum(float(value) for value in values), "development numeric total")
        return {
            "kind": kind,
            "numeric_total": total,
            "outcome": total,
            "values": list(values),
            "work_units": len(values),
        }
    if kind == "field-read":
        references: list[dict[str, Any]] = []
        values: list[Any] = []
        for binding_id in plan["binding_ids"]:
            record = _semantic_current_record(state, "Binding", binding_id)
            reference = semantic_record_ref(record).as_dict()
            references.append(reference)
            values.append(
                _regional_plain(
                    record["payload"].get("value"), "development field outcome"
                )
            )
        outcome: Any = values[0] if len(values) == 1 else values
        return {
            "binding_ids": list(plan["binding_ids"]),
            "kind": kind,
            "outcome": outcome,
            "references": references,
            "work_units": len(values),
        }
    raise FieldIntelligenceError(
        "INVALID_DEVELOPMENT", "development execution plan is invalid"
    )
_DEVELOPMENT_SKILLS = (
    "consolidate",
    "investigate",
    "meditate",
    "practice",
    "reflect",
    "study",
    "teach",
)
_DEVELOPMENT_DIAGNOSIS_SKILL = {
    "communication-gap": "teach",
    "incorrect-procedure": "practice",
    "inadequate-representation": "meditate",
    "method-selection": "reflect",
    "missing-evidence": "study",
    "repeated-structure": "consolidate",
    "wrong-binding": "investigate",
}


def _semantic_development_allocation(
    value: Any, state: Mapping[str, Any]
) -> dict[str, int]:
    required = {"evidence_reads", "model_calls", "storage_words", "work"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise FieldIntelligenceError(
            "INVALID_DEVELOPMENT",
            "development allocation must declare every bounded resource",
        )
    allocation = {
        name: _regional_integer(
            value[name],
            f"development {name}",
            minimum=1 if name == "work" else 0,
        )
        for name in required
    }
    if allocation["work"] > state["bounds"]["max_work"]:
        raise FieldIntelligenceError(
            "WORK_CAPACITY", "development work allocation exceeds its bound"
        )
    return allocation


def _packet_resources(
    value: Mapping[str, Any],
    label: str,
    *,
    require_work: bool = False,
) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) - set(PACKET_RESOURCE_NAMES):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            f"{label} contains unknown resources",
        )
    result: dict[str, int] = {}
    for name in PACKET_RESOURCE_NAMES:
        raw = value.get(name, 0)
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                f"{label} {name} must be a nonnegative integer",
            )
        result[name] = raw
    if require_work and result["work"] < 1:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            f"{label} work must be positive",
        )
    return result


def _packet_resource_add(
    left: Mapping[str, int], right: Mapping[str, int]
) -> dict[str, int]:
    return {
        name: int(left[name]) + int(right[name])
        for name in PACKET_RESOURCE_NAMES
    }


def _packet_normalize_invocation(
    value: Mapping[str, Any],
    *,
    default_reservation: Mapping[str, int],
) -> dict[str, Any]:
    allowed = {
        "adapter",
        "arguments",
        "expected_return",
        "kernel",
        "request",
        "reservation",
        "state",
    }
    if not isinstance(value, Mapping) or set(value) - allowed:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning invocation has an invalid schema",
        )
    kernel = value.get("kernel")
    adapter = value.get("adapter")
    if (kernel is None) == (adapter is None):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning invocation requires exactly one kernel or adapter",
        )
    if kernel is not None:
        _identifier(kernel, "reasoning invocation kernel")
        raw_state = value.get("state")
        if raw_state is not None and not isinstance(raw_state, Mapping):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "regional reasoning invocation requires task state or null",
            )
        state_value: dict[str, Any] | None = (
            None
            if raw_state is None
            else _regional_plain(
                dict(cast(Mapping[str, Any], raw_state)),
                "reasoning invocation state",
            )
        )
        request_value = None
    else:
        _identifier(adapter, "reasoning invocation adapter")
        if not isinstance(value.get("request"), Mapping):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "external reasoning invocation requires a request",
            )
        request_value = _regional_plain(
            dict(cast(Mapping[str, Any], value["request"])),
            "reasoning adapter request",
        )
        state_value = None
    arguments = value.get("arguments", {})
    expected_return = value.get("expected_return", {})
    if not isinstance(arguments, Mapping) or not isinstance(
        expected_return, Mapping
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning invocation arguments or return contract is invalid",
        )
    return {
        "adapter": adapter,
        "arguments": _regional_plain(
            dict(arguments), "reasoning invocation arguments"
        ),
        "expected_return": _regional_plain(
            dict(expected_return), "reasoning expected return"
        ),
        "kernel": kernel,
        "request": request_value,
        "reservation": _packet_resources(
            cast(
                Mapping[str, Any],
                value.get("reservation", default_reservation),
            ),
            "reasoning invocation reservation",
            require_work=True,
        ),
        "state": state_value,
    }


def _packet_local_reservation(
    item: Mapping[str, Any],
    *,
    hierarchy: Mapping[str, Any] | None,
) -> dict[str, int]:
    """Bound the resources one host-executed work item will charge.

    A local item has no child to charge it back, so its reservation is read
    from the contract it carries: the readout vectors it inspects, the
    hypotheses it publishes, or the hierarchy packets a refinement rewrites.
    """

    reservation = {name: 0 for name in PACKET_RESOURCE_NAMES}
    kind = str(item["kind"])
    if kind == "readout":
        readout = cast(Mapping[str, Any], item["readout"])
        coefficients = readout["scaled_coefficients"]
        inspected = readout["inspected_indices"]
        provenance = cast(Mapping[str, Any], readout["bound_provider"])
        reservation["evidence_reads"] = max(1, len(coefficients))
        reservation["work"] = max(
            1,
            int(provenance["construction_work"]) + len(inspected),
        )
        result_bound = {
            "schema": "cassifi.packet-affine-readout-result.v1",
            "bound": _PACKET_MAXIMUM_ABSOLUTE_VALUE,
            "decision": True,
            "estimate": _PACKET_MAXIMUM_ABSOLUTE_VALUE,
            "inspected_indices": list(range(len(coefficients))),
            "interval": {
                "lower": -_PACKET_MAXIMUM_ABSOLUTE_VALUE,
                "upper": _PACKET_MAXIMUM_ABSOLUTE_VALUE,
            },
            "omitted_indices": list(range(len(coefficients))),
            "output_units": "x" * 128,
            "reason": "refinement-required",
            "source_state_sha256": "f" * 64,
            "status": "unresolved",
        }
        reservation["storage_words"] = (
            len(canonical_json_bytes(result_bound)) + 3
        ) // 4
        return reservation
    if kind == "branch":
        contract = cast(Mapping[str, Any], item["branch"])
        hypotheses = cast(list[Any], contract["hypotheses"])
        reservation["branch_count"] = len(hypotheses)
        reservation["frontier_size"] = len(hypotheses)
        reservation["work"] = max(1, len(hypotheses))
        reservation["storage_words"] = (
            2 * len(canonical_json_bytes(contract)) + 256 + 3
        ) // 4
        return reservation
    if kind == "refine":
        contract = cast(Mapping[str, Any], item["refinement"])
        if hierarchy is None:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning refinement requires a packet hierarchy",
            )
        path = str(contract["path"])
        parent = next(
            (
                packet
                for packet in cast(
                    list[Mapping[str, Any]], hierarchy["packets"]
                )
                if str(packet["path"]) == path
            ),
            None,
        )
        if parent is None:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning refinement path is outside its hierarchy",
            )
        width = int(parent["support"]["stop"]) - int(
            parent["support"]["start"]
        )
        reservation["frontier_size"] = 1
        reservation["refinement_depth"] = 1
        reservation["work"] = max(1, width)
        reservation["storage_words"] = (
            2 * len(canonical_json_bytes(parent)) + 1024 + 3
        ) // 4
        return reservation
    return reservation


def _packet_source_binding(value: Any) -> dict[str, Any] | None:
    """Normalize a declared source span that a work item or input cites.

    A binding names an admitted source revision and, optionally, the exact byte
    span within it. Structural form is enforced here; authority is enforced where
    the episode's admitted inputs are known.
    """
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) - {
        "source_revision_id",
        "span",
    }:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "source binding is invalid",
        )
    identity = value.get("source_revision_id")
    if (
        not isinstance(identity, str)
        or len(identity) != 64
        or any(character not in "0123456789abcdef" for character in identity)
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "source binding identity is invalid",
        )
    raw_span = value.get("span")
    if raw_span is None:
        span: list[int] | None = None
    else:
        if (
            isinstance(raw_span, (str, bytes))
            or not isinstance(raw_span, Sequence)
            or len(raw_span) != 2
            or any(
                isinstance(offset, bool) or not isinstance(offset, int)
                for offset in raw_span
            )
        ):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "source binding span is invalid",
            )
        start = int(raw_span[0])
        stop = int(raw_span[1])
        if start < 0 or stop < start:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "source binding span is invalid",
            )
        span = [start, stop]
    return {"source_revision_id": identity, "span": span}


def _packet_authorize_source_binding(
    payload: Mapping[str, Any], item: Mapping[str, Any]
) -> None:
    """Refuse work that cites a source span the episode never admitted.

    An admitted input authorizes exactly the source revision it names and, when it
    declares a span, only spans inside that span. A work item that cites anything
    else is refused rather than recorded as if the citation were valid.
    """
    binding = item.get("source_binding")
    if not isinstance(binding, Mapping):
        return
    identity = str(binding["source_revision_id"])
    candidates = [
        row["source_binding"]
        for row in payload.get("inputs", [])
        if isinstance(row.get("source_binding"), Mapping)
        and str(row["source_binding"]["source_revision_id"]) == identity
    ]
    if not candidates:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning work cites a source the episode did not admit",
        )
    span = binding.get("span")
    if span is None:
        return
    for candidate in candidates:
        admitted_span = candidate.get("span")
        if admitted_span is None:
            continue
        if (
            int(admitted_span[0]) <= int(span[0])
            and int(span[1]) <= int(admitted_span[1])
        ):
            return
    raise FieldIntelligenceError(
        "INVALID_REASONING_EPISODE",
        "reasoning work cites a span the episode did not admit",
    )


def _packet_support_spans(
    hierarchy: Mapping[str, Any] | None,
    paths: Sequence[str],
) -> dict[str, Any]:
    """Resolve work-item support paths to the packet spans they read."""
    resolved: list[dict[str, Any]] = []
    unresolved: list[str] = []
    if hierarchy is None or not paths:
        return {"resolved": resolved, "unresolved": unresolved}
    by_path = {
        str(packet["path"]): packet for packet in hierarchy.get("packets", [])
    }
    for path in paths:
        packet = by_path.get(str(path))
        if packet is None:
            unresolved.append(str(path))
            continue
        resolved.append(
            {
                "path": str(path),
                "start": int(packet["support"]["start"]),
                "stop": int(packet["support"]["stop"]),
            }
        )
    return {"resolved": resolved, "unresolved": unresolved}


def _packet_normalize_work_item(
    value: Mapping[str, Any],
    *,
    index: int,
    default_reservation: Mapping[str, int],
    hierarchy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    allowed = {
        "assumptions",
        "branch",
        "cue",
        "dependencies",
        "invocation",
        "item_id",
        "kind",
        "priority",
        "read_footprint",
        "readout",
        "refinement",
        "required_checks",
        "scope",
        "source_binding",
        "support_paths",
        "write_footprint",
    }
    if not isinstance(value, Mapping) or set(value) - allowed:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning work item has an invalid schema",
        )
    item_id = _identifier(value.get("item_id"), "reasoning work item")
    kind = _identifier(value.get("kind"), "reasoning work kind")
    if kind not in PACKET_WORK_KINDS:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning work kind is unsupported",
        )
    dependencies = value.get("dependencies", [])
    support_paths = value.get("support_paths", [])
    if (
        not isinstance(dependencies, list)
        or len(dependencies) > SEMANTIC_MAX_ALTERNATIVES
        or any(not isinstance(item, str) or not item for item in dependencies)
        or len(set(dependencies)) != len(dependencies)
        or not isinstance(support_paths, list)
        or any(not isinstance(path, str) for path in support_paths)
        or len(set(support_paths)) != len(support_paths)
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning work dependencies or packet supports are invalid",
        )
    priority = _regional_integer(
        value.get("priority", 0),
        "reasoning work priority",
        minimum=-1_000_000,
        maximum=1_000_000,
    )
    invocation = value.get("invocation")
    requires_invocation = kind in {
        "model-native",
        "regional",
        "semantic",
        "temporal",
    }
    if requires_invocation != isinstance(invocation, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning work invocation does not match its kind",
        )
    normalized_invocation = (
        None
        if invocation is None
        else _packet_normalize_invocation(
            cast(Mapping[str, Any], invocation),
            default_reservation=default_reservation,
        )
    )
    for footprint_name in (
        "read_footprint",
        "required_checks",
        "write_footprint",
    ):
        footprint = value.get(footprint_name, [])
        if not isinstance(footprint, list) or len(footprint) > 4_096:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                f"reasoning {footprint_name} is invalid",
            )
    branch = value.get("branch")
    cue = value.get("cue")
    readout = value.get("readout")
    refinement = value.get("refinement")
    source_binding = _packet_source_binding(value.get("source_binding"))
    if kind == "branch" and not isinstance(branch, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "branch work requires a branch contract",
        )
    if kind == "readout" and not isinstance(readout, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "readout work requires an affine readout",
        )
    if kind == "refine" and not isinstance(refinement, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "refinement work requires a refinement contract",
        )
    normalized = {
        "schema": PACKET_WORK_ITEM_SCHEMA,
        "age": 0,
        "assumptions": _regional_plain(
            value.get("assumptions", {}),
            "reasoning work assumptions",
        ),
        "branch": (
            None
            if branch is None
            else _regional_plain(dict(branch), "reasoning branch contract")
        ),
        "cue": (
            None
            if cue is None
            else _regional_plain(dict(cue), "reasoning cue contract")
        ),
        "dependencies": list(dependencies),
        "invocation": normalized_invocation,
        "item_id": item_id,
        "kind": kind,
        "priority": priority,
        "read_footprint": _regional_plain(
            value.get("read_footprint", []),
            "reasoning read footprint",
        ),
        "readout": (
            None
            if readout is None
            else _regional_plain(dict(readout), "reasoning affine readout")
        ),
        "ready_sequence": index,
        "refinement": (
            None
            if refinement is None
            else _regional_plain(
                dict(refinement), "reasoning refinement contract"
            )
        ),
        "required_checks": _regional_plain(
            value.get("required_checks", []),
            "reasoning required checks",
        ),
        "result": None,
        "scope": _regional_plain(
            value.get("scope", "episode"), "reasoning work scope"
        ),
        "status": "ready" if not dependencies else "deferred",
        "source_binding": source_binding,
        "support_paths": list(support_paths),
        "write_footprint": _regional_plain(
            value.get("write_footprint", []),
            "reasoning write footprint",
        ),
    }
    if normalized_invocation is None:
        normalized["reservation"] = _packet_local_reservation(
            normalized, hierarchy=hierarchy
        )
        normalized["reservation_declared"] = True
    else:
        normalized["reservation"] = normalized_invocation["reservation"]
        normalized["reservation_declared"] = bool(
            isinstance(invocation, Mapping) and "reservation" in invocation
        )
    normalized["reuse_key"] = sha256_value(
        {
            name: normalized[name]
            for name in (
                "assumptions",
                "cue",
                "dependencies",
                "invocation",
                "read_footprint",
                "required_checks",
                "scope",
                "support_paths",
                "write_footprint",
            )
        }
    )
    return normalized


def _packet_validate_work_program(
    values: Sequence[Mapping[str, Any]],
    *,
    allocation: Mapping[str, int],
    hierarchy: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Sequence)
        or not values
        or len(values) > SEMANTIC_MAX_ALTERNATIVES
        or len(values) > max(1, int(allocation["frontier_size"]))
    ):
        raise FieldIntelligenceError(
            "WORK_CAPACITY",
            "reasoning work frontier exceeds its root allowance",
        )
    default_reservation = {
        name: int(allocation[name]) for name in PACKET_RESOURCE_NAMES
    }
    default_reservation["work"] = max(
        1, min(int(allocation["work"]), REGIONAL_KERNEL_MAX_WORK)
    )
    items = [
        _packet_normalize_work_item(
            row,
            index=index,
            default_reservation=default_reservation,
            hierarchy=hierarchy,
        )
        for index, row in enumerate(values)
    ]
    identities = [item["item_id"] for item in items]
    if len(set(identities)) != len(identities):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning work item identities are duplicated",
        )
    known = set(identities)
    if any(
        dependency not in known
        for item in items
        for dependency in item["dependencies"]
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning work dependency is unknown",
        )
    pending = {item["item_id"]: set(item["dependencies"]) for item in items}
    resolved: set[str] = set()
    while pending:
        ready = sorted(
            item_id
            for item_id, dependencies in pending.items()
            if dependencies <= resolved
        )
        if not ready:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "cyclic reasoning work requires an explicit solver operation",
            )
        for item_id in ready:
            resolved.add(item_id)
            del pending[item_id]
    return items


def _packet_normalize_hierarchy(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "a_clip",
        "active_paths",
        "assembly_id",
        "channel_scales",
        "channel_units",
        "codec",
        "frame",
        "hierarchy_id",
        "packets",
        "priority_scale",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet hierarchy has an invalid schema",
        )
    hierarchy_id = _identifier(value["hierarchy_id"], "packet hierarchy")
    assembly_id = _identifier(value["assembly_id"], "packet assembly")
    scales = value["channel_scales"]
    units = value["channel_units"]
    if (
        not isinstance(scales, Mapping)
        or set(scales) != set(HELICAL_PACKET_CHANNELS)
        or not isinstance(units, Mapping)
        or set(units) != set(HELICAL_PACKET_CHANNELS)
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet channel scales or units are incomplete",
        )
    normalized_scales: dict[str, float] = {}
    normalized_units: dict[str, str] = {}
    for channel in HELICAL_PACKET_CHANNELS:
        normalized_scales[channel] = _regional_number(
            scales[channel],
            f"packet {channel} scale",
            minimum=0.0,
            inclusive_minimum=False,
        )
        normalized_units[channel] = _identifier(
            units[channel], f"packet {channel} units"
        )
    a_clip = _regional_number(
        value["a_clip"],
        "packet activation clip",
        minimum=0.0,
        inclusive_minimum=False,
    )
    priority_scale = _regional_integer(
        value["priority_scale"],
        "packet priority scale",
        minimum=1,
        maximum=1_000_000_000,
    )
    packets = value["packets"]
    active_paths = value["active_paths"]
    if (
        not isinstance(packets, list)
        or not packets
        or len(packets) > SEMANTIC_MAX_ALTERNATIVES
        or not isinstance(active_paths, list)
        or not active_paths
        or any(not isinstance(path, str) for path in active_paths)
        or len(set(active_paths)) != len(active_paths)
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet hierarchy packets or active frontier are invalid",
        )
    packet_by_path: dict[str, dict[str, Any]] = {}
    shared: tuple[Any, ...] | None = None
    for raw_packet in packets:
        try:
            helical_packet_channels(raw_packet)
        except (ResonantNumericalError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "packet hierarchy contains an invalid numerical packet",
            ) from exc
        packet = _regional_plain(
            dict(raw_packet), "packet hierarchy numerical packet"
        )
        path = str(packet["path"])
        if path in packet_by_path:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "packet hierarchy path is duplicated",
            )
        identity = (
            packet["source_state_sha256"],
            packet["profile_sha256"],
            packet["layout_identity"],
            packet["basis"],
        )
        if shared is None:
            shared = identity
        elif identity != shared:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "packet hierarchy mixes numerical sources or bases",
            )
        packet_by_path[path] = packet
    if any(path not in packet_by_path for path in active_paths):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet active frontier names an unavailable support",
        )
    active_packets = [packet_by_path[path] for path in active_paths]
    active_packets.sort(
        key=lambda packet: (
            int(packet["support"]["start"]),
            int(packet["support"]["stop"]),
            str(packet["path"]),
        )
    )
    prior_stop = -1
    prior_path: str | None = None
    for packet in active_packets:
        start = int(packet["support"]["start"])
        stop = int(packet["support"]["stop"])
        path = str(packet["path"])
        if (
            start < prior_stop
            or (
                prior_path is not None
                and (path.startswith(prior_path) or prior_path.startswith(path))
            )
        ):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "packet active frontier is not a disjoint antichain",
            )
        prior_stop = stop
        prior_path = path
    hierarchy = {
        "schema": PACKET_HIERARCHY_SCHEMA,
        "a_clip": a_clip,
        "active_paths": [str(packet["path"]) for packet in active_packets],
        "assembly_id": assembly_id,
        "basis": shared[3] if shared is not None else None,
        "channel_scales": normalized_scales,
        "channel_units": normalized_units,
        "codec": _regional_plain(value["codec"], "packet hierarchy codec"),
        "codec_sha256": sha256_value(value["codec"]),
        "frame": _regional_plain(value["frame"], "packet hierarchy frame"),
        "hierarchy_id": hierarchy_id,
        "layout_identity": shared[2] if shared is not None else None,
        "max_depth": max(len(path) for path in packet_by_path),
        "packets": [
            packet_by_path[path] for path in sorted(packet_by_path)
        ],
        "priority_scale": priority_scale,
        "profile_sha256": shared[1] if shared is not None else None,
        "source_state_sha256": shared[0] if shared is not None else None,
    }
    activation = _packet_activation(hierarchy, hierarchy["active_paths"])
    hierarchy["initial_activation"] = activation
    return hierarchy


def _packet_activation(
    hierarchy: Mapping[str, Any], paths: Sequence[str]
) -> dict[str, Any]:
    packet_by_path = {
        str(packet["path"]): packet for packet in hierarchy["packets"]
    }
    if (
        not paths
        or any(path not in packet_by_path for path in paths)
        or len(set(paths)) != len(paths)
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet activation cover is invalid",
        )
    packets = sorted(
        (packet_by_path[path] for path in paths),
        key=lambda packet: (
            int(packet["support"]["start"]),
            int(packet["support"]["stop"]),
            str(packet["path"]),
        ),
    )
    prior_stop = -1
    prior_path: str | None = None
    terms: list[float] = []
    union_size = 0
    for packet in packets:
        path = str(packet["path"])
        start = int(packet["support"]["start"])
        stop = int(packet["support"]["stop"])
        if (
            start < prior_stop
            or (
                prior_path is not None
                and (path.startswith(prior_path) or prior_path.startswith(path))
            )
            or packet["source_state_sha256"]
            != hierarchy["source_state_sha256"]
        ):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "packet activation requires a source-bound disjoint antichain",
            )
        prior_stop = stop
        prior_path = path
        union_size += stop - start
        coefficients = packet["coefficients"]
        for row in coefficients:
            for channel_index, channel in enumerate(HELICAL_PACKET_CHANNELS):
                term = float(row[channel_index]) / float(
                    hierarchy["channel_scales"][channel]
                )
                square = term * term
                if not math.isfinite(square):
                    raise FieldIntelligenceError(
                        "INVALID_REASONING_EPISODE",
                        "packet activation coefficient is nonfinite",
                    )
                terms.append(square)
    if union_size < 1:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet activation cover is empty",
        )
    activation = math.fsum(terms) / float(union_size)
    if not math.isfinite(activation):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet activation is nonfinite",
        )
    clipped = min(activation / float(hierarchy["a_clip"]), 1.0)
    priority_input = math.floor(
        int(hierarchy["priority_scale"]) * clipped
    )
    cover = [
        {
            "path": packet["path"],
            "start": packet["support"]["start"],
            "stop": packet["support"]["stop"],
        }
        for packet in packets
    ]
    return {
        "activation": activation,
        "activation_input": priority_input,
        "codec_sha256": hierarchy["codec_sha256"],
        "cover": cover,
        "cover_sha256": sha256_value(cover),
        "source_state_sha256": hierarchy["source_state_sha256"],
        "union_ports": union_size,
    }

def _packet_affine_readout(
    value: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, int]]:
    required = {
        "bias",
        "bound_provider",
        "codec_sha256",
        "comparison",
        "inspected_indices",
        "output_units",
        "readout_sha256",
        "scaled_coefficients",
        "scaled_weights",
        "schema",
        "source_state_sha256",
        "threshold",
        "tolerance",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet affine readout has an invalid schema",
        )
    if value["schema"] != PACKET_READOUT_SCHEMA:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet affine readout schema is unsupported",
        )
    for name in ("codec_sha256", "readout_sha256", "source_state_sha256"):
        digest = value[name]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                f"packet readout {name} is invalid",
            )
    coefficients = value["scaled_coefficients"]
    weights = value["scaled_weights"]
    inspected = value["inspected_indices"]
    if (
        not isinstance(coefficients, list)
        or not coefficients
        or len(coefficients) > 65_536
        or not isinstance(weights, list)
        or len(weights) != len(coefficients)
        or not isinstance(inspected, list)
        or any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(coefficients)
            for index in inspected
        )
        or len(set(inspected)) != len(inspected)
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet affine readout vectors or inspected set are invalid",
        )
    x = [
        _regional_number(item, "scaled packet coefficient")
        for item in coefficients
    ]
    v = [
        _regional_number(item, "scaled packet readout weight")
        for item in weights
    ]
    provider = value["bound_provider"]
    provider_keys = {
        "arithmetic_epsilon",
        "codec_sha256",
        "construction_work",
        "omitted_indices",
        "readout_sha256",
        "schema",
        "source_state_sha256",
        "x_norm_upper",
    }
    if (
        not isinstance(provider, Mapping)
        or set(provider) != provider_keys
        or provider.get("schema") != PACKET_BOUND_SCHEMA
        or provider.get("source_state_sha256")
        != value["source_state_sha256"]
        or provider.get("codec_sha256") != value["codec_sha256"]
        or provider.get("readout_sha256") != value["readout_sha256"]
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet readout bound provider identity is invalid",
        )
    omitted = provider["omitted_indices"]
    expected_omitted = sorted(set(range(len(x))) - set(inspected))
    if (
        not isinstance(omitted, list)
        or omitted != expected_omitted
        or any(
            isinstance(index, bool) or not isinstance(index, int)
            for index in omitted
        )
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet readout omitted set is not the exact complement",
        )
    x_norm_upper = _regional_number(
        provider["x_norm_upper"],
        "packet omitted coefficient norm bound",
        minimum=0.0,
    )
    arithmetic_epsilon = _regional_number(
        provider["arithmetic_epsilon"],
        "packet readout arithmetic allowance",
        minimum=0.0,
    )
    construction_work = _regional_integer(
        provider["construction_work"],
        "packet bound construction work",
        minimum=len(x),
        maximum=1_000_000,
    )
    actual_omitted_norm = math.sqrt(
        math.fsum(x[index] * x[index] for index in omitted)
    )
    roundoff = max(
        arithmetic_epsilon,
        math.ulp(max(1.0, actual_omitted_norm)),
    )
    if actual_omitted_norm > x_norm_upper + roundoff:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet coefficient norm exceeds its certified enclosure",
        )
    bias = _regional_number(value["bias"], "packet readout bias")
    estimate = bias + math.fsum(v[index] * x[index] for index in inspected)
    omitted_weight_norm = math.sqrt(
        math.fsum(v[index] * v[index] for index in omitted)
    )
    bound = math.nextafter(
        omitted_weight_norm * x_norm_upper + arithmetic_epsilon,
        math.inf,
    )
    if not math.isfinite(estimate) or not math.isfinite(bound):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet affine readout produced a nonfinite enclosure",
        )
    lower = math.nextafter(estimate - bound, -math.inf)
    upper = math.nextafter(estimate + bound, math.inf)
    threshold = value["threshold"]
    tolerance = value["tolerance"]
    comparison = value["comparison"]
    decision: bool | None = None
    status = "unresolved"
    reason = "refinement-required"
    if threshold is not None:
        threshold_value = _regional_number(
            threshold, "packet readout threshold"
        )
        if comparison not in {"ge", "gt", "le", "lt"}:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "packet threshold comparison is invalid",
            )
        if comparison == "gt":
            if lower > threshold_value:
                decision = True
            elif upper <= threshold_value:
                decision = False
        elif comparison == "ge":
            if lower >= threshold_value:
                decision = True
            elif upper < threshold_value:
                decision = False
        elif comparison == "lt":
            if upper < threshold_value:
                decision = True
            elif lower >= threshold_value:
                decision = False
        else:
            if upper <= threshold_value:
                decision = True
            elif lower > threshold_value:
                decision = False
        if decision is not None:
            status = "exact"
            reason = "threshold-separated"
    else:
        if comparison is not None or tolerance is None:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "packet estimate requires a tolerance and no comparison",
            )
        tolerance_value = _regional_number(
            tolerance, "packet readout tolerance", minimum=0.0
        )
        if bound <= tolerance_value:
            status = "estimated"
            reason = "error-within-tolerance"
    result = {
        "schema": "cassifi.packet-affine-readout-result.v1",
        "bound": bound,
        "decision": decision,
        "estimate": estimate,
        "inspected_indices": list(inspected),
        "interval": {"lower": lower, "upper": upper},
        "omitted_indices": omitted,
        "output_units": _identifier(
            value["output_units"], "packet readout output units"
        ),
        "reason": reason,
        "source_state_sha256": value["source_state_sha256"],
        "status": status,
    }
    resources = {name: 0 for name in PACKET_RESOURCE_NAMES}
    resources["evidence_reads"] = len(x)
    resources["work"] = construction_work + len(inspected)
    resources["storage_words"] = (len(canonical_json_bytes(result)) + 3) // 4
    return result, resources


def _packet_publish_assembly(
    state: dict[str, Any],
    value: Mapping[str, Any],
    *,
    dependencies: Sequence[Mapping[str, Any]],
    support_roots: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    required = {
        "assembly_id",
        "assistance",
        "bindings",
        "hierarchy_id",
        "interface",
        "retained_expansion",
        "workspace_state",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet assembly has an invalid schema",
        )
    assembly_id = _identifier(value["assembly_id"], "packet assembly")
    hierarchy_id = _identifier(
        value["hierarchy_id"], "packet assembly hierarchy"
    )
    if value["assistance"] not in {"acquired", "supplied"}:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet assembly assistance boundary is invalid",
        )
    if not isinstance(value["interface"], Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet assembly interface must be a mapping",
        )
    bindings = value["bindings"]
    if (
        not isinstance(bindings, list)
        or len(bindings) > SEMANTIC_MAX_ALTERNATIVES
        or any(not isinstance(binding, Mapping) for binding in bindings)
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet assembly bindings are invalid",
        )
    resolved_dependencies = list(dependencies)
    normalized_bindings: list[dict[str, Any]] = []
    for raw_binding in bindings:
        binding = _regional_plain(
            dict(raw_binding), "packet assembly binding"
        )
        semantic_reference = binding.get("semantic_ref")
        if semantic_reference is not None:
            if not isinstance(semantic_reference, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_REASONING_EPISODE",
                    "packet assembly semantic binding is mistyped",
                )
            reference, _record = _semantic_reference(
                state, semantic_reference, require_current=True
            )
            binding["semantic_ref"] = reference.as_dict()
            resolved_dependencies.append(reference.as_dict())
        normalized_bindings.append(binding)
    workspace_state = value["workspace_state"]
    if workspace_state is not None and not isinstance(
        workspace_state, Mapping
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet assembly workspace state is invalid",
        )
    interface_ref = _semantic_append_record(
        state,
        record_id=f"program:packet-interface:{assembly_id}",
        kind="Program",
        payload={
            "assistance": value["assistance"],
            "interface": _regional_plain(
                dict(value["interface"]), "packet assembly interface"
            ),
            "program": semantic_program_payload(
                program_kind="identity", body={}
            ),
            "program_role": "representation",
            "purpose": "packet-interface",
        },
        epistemic_kind=(
            "derived" if value["assistance"] == "acquired" else "asserted"
        ),
        dependencies=resolved_dependencies,
        support_roots=support_roots,
    )
    _semantic_reindex_record(state, interface_ref)
    assembly_ref = _semantic_append_record(
        state,
        record_id=f"binding:packet-assembly:{assembly_id}",
        kind="Binding",
        payload={
            "schema": PACKET_ASSEMBLY_SCHEMA,
            "assembly_id": assembly_id,
            "assistance": value["assistance"],
            "bindings": normalized_bindings,
            "hierarchy_id": hierarchy_id,
            "interface": interface_ref,
            "representation": "packet-assembly",
            "retained_expansion": _regional_plain(
                value["retained_expansion"],
                "packet assembly retained expansion",
            ),
            "workspace_state": (
                None
                if workspace_state is None
                else _regional_plain(
                    dict(workspace_state),
                    "packet assembly workspace state",
                )
            ),
        },
        epistemic_kind=(
            "derived" if value["assistance"] == "acquired" else "asserted"
        ),
        dependencies=(*resolved_dependencies, interface_ref),
        support_roots=support_roots,
    )
    _semantic_reindex_record(state, assembly_ref)
    return interface_ref, assembly_ref


def _packet_publish_hierarchy(
    state: dict[str, Any],
    value: Mapping[str, Any],
    *,
    assembly_ref: Mapping[str, Any],
    support_roots: Sequence[str],
) -> dict[str, Any]:
    hierarchy = _packet_normalize_hierarchy(value)
    reference = _semantic_append_record(
        state,
        record_id=f"value:packet-hierarchy:{hierarchy['hierarchy_id']}",
        kind="Value",
        payload={
            **hierarchy,
            "representation": "packet-hierarchy",
        },
        epistemic_kind="derived",
        dependencies=(assembly_ref,),
        support_roots=support_roots,
    )
    _semantic_reindex_record(state, reference)
    return reference


def _packet_reasoning_episode(
    state: dict[str, Any], episode_id: str
) -> dict[str, Any]:
    obligation = _semantic_current_record(
        state, "Obligation", f"obligation:reasoning:{episode_id}"
    )
    if obligation["payload"].get("schema") != PACKET_REASONING_EPISODE_SCHEMA:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning episode predates the packet-aware work loop",
        )
    payload = _regional_plain(
        dict(obligation["payload"]), "reasoning episode payload"
    )
    repaired_slots: dict[str, Any] = {}
    changed = False
    for slot in ("dependencies", "assemblies"):
        repaired: list[dict[str, Any]] = []
        for raw in payload[slot]:
            reference = SemanticRef.from_dict(dict(raw))
            current = _semantic_current_record(
                state, reference.kind, reference.id
            )
            if int(current["content_version"]) == reference.content_version:
                repaired.append(reference.as_dict())
                continue
            repaired.append(semantic_record_ref(current).as_dict())
            payload.setdefault("repairs", []).append(
                {
                    "slot": slot,
                    "prior": reference.as_dict(),
                    "current": semantic_record_ref(current).as_dict(),
                }
            )
            changed = True
        repaired_slots[slot] = repaired
    raw_hierarchy = payload.get("hierarchy")
    repaired_hierarchy = raw_hierarchy
    if isinstance(raw_hierarchy, Mapping):
        reference = SemanticRef.from_dict(dict(raw_hierarchy))
        current = _semantic_current_record(state, reference.kind, reference.id)
        if int(current["content_version"]) != reference.content_version:
            repaired_hierarchy = semantic_record_ref(current).as_dict()
            payload.setdefault("repairs", []).append(
                {
                    "slot": "hierarchy",
                    "prior": reference.as_dict(),
                    "current": repaired_hierarchy,
                }
            )
            changed = True
    if changed:
        payload["dependencies"] = repaired_slots["dependencies"]
        payload["assemblies"] = repaired_slots["assemblies"]
        payload["hierarchy"] = repaired_hierarchy
        if len(payload["repairs"]) > SEMANTIC_MAX_ALTERNATIVES:
            raise FieldIntelligenceError(
                "WORK_CAPACITY",
                "reasoning episode dependency repairs are exhausted",
            )
        active = payload.get("active")
        if isinstance(active, Mapping):
            released = _packet_resources(
                cast(Mapping[str, Any], active["reservation"]),
                "released reasoning reservation",
                require_work=True,
            )
            for name in PACKET_RESOURCE_NAMES:
                payload["resources"]["reserved"][name] = max(
                    0,
                    int(payload["resources"]["reserved"][name])
                    - int(released[name]),
                )
            for row in payload["work_items"]:
                if row["item_id"] == active["item_id"] and row["status"] in {
                    "ready",
                    "reserved",
                }:
                    row["status"] = "ready"
                    row["result"] = {
                        "call_id": active["call_id"],
                        "reason": "dependency-repaired",
                        "status": "ineligible",
                    }
            payload.setdefault("releases", []).append(
                {
                    "call_id": str(active["call_id"]),
                    "item_id": str(active["item_id"]),
                    "reason": "dependency-repaired",
                }
            )
            if len(payload["releases"]) > SEMANTIC_MAX_ALTERNATIVES:
                raise FieldIntelligenceError(
                    "WORK_CAPACITY",
                    "reasoning episode releases are exhausted",
                )
            payload["active"] = None
            payload["phase"] = "ready"
        _packet_update_episode(state, obligation, payload, terminal=False)
        obligation = _semantic_current_record(
            state, "Obligation", str(obligation["id"])
        )
    return obligation


def _packet_update_episode(
    state: dict[str, Any],
    obligation: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    dependencies: Sequence[Mapping[str, Any]] = (),
    terminal: bool = False,
) -> dict[str, Any]:
    recorded: list[dict[str, Any]] = [
        semantic_record_ref(obligation).as_dict()
    ]
    for reference in (
        *cast(Sequence[Mapping[str, Any]], payload["dependencies"]),
        *dependencies,
    ):
        row = dict(reference)
        if row not in recorded:
            recorded.append(row)
    updated = _semantic_append_record(
        state,
        record_id=str(obligation["id"]),
        kind="Obligation",
        payload=payload,
        status="assessed" if terminal else "active",
        epistemic_kind="derived",
        dependencies=tuple(recorded),
        support_roots=obligation["support_roots"],
    )
    _semantic_reindex_record(state, updated)
    return updated


def _packet_hierarchy_record(
    state: Mapping[str, Any],
    episode: Mapping[str, Any],
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    source = episode["payload"] if payload is None else payload
    reference = source.get("hierarchy")
    if reference is None:
        return None
    if not isinstance(reference, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning hierarchy reference is invalid",
        )
    _ref, record = _semantic_reference(
        state, reference, expected_kind="Value", require_current=True
    )
    if record["payload"].get("schema") != PACKET_HIERARCHY_SCHEMA:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning hierarchy has the wrong value schema",
        )
    return record


def _packet_scheduler_score(
    state: Mapping[str, Any],
    episode: Mapping[str, Any],
    item: Mapping[str, Any],
    hierarchy_record: Mapping[str, Any] | None,
) -> tuple[int, dict[str, Any]]:
    payload = episode["payload"]
    method = payload["scheduler"]["method"]
    base = int(item["priority"])
    cue = 0
    cue_source: Mapping[str, Any] | None = None
    paths = item["support_paths"]
    if method in {"hierarchy", "live", "static"} and paths:
        if hierarchy_record is None:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "packet-scored work has no hierarchy",
            )
        hierarchy = hierarchy_record["payload"]
        if method == "hierarchy":
            cue = int(hierarchy["max_depth"]) - min(
                len(path) for path in paths
            )
            cue_source = {
                "kind": "hierarchy-depth",
                "paths": list(paths),
                "value": cue,
            }
        else:
            activation = (
                hierarchy["initial_activation"]
                if method == "static"
                else _packet_activation(hierarchy, paths)
            )
            cue = int(activation["activation_input"])
            cue_source = {"kind": f"{method}-activation", **activation}
    elif method == "shuffled":
        digest = sha256_value(
            {
                "episode": payload["content_sha256"],
                "item_id": item["item_id"],
                "method": method,
            }
        )
        cue = int(digest[:12], 16) % 1_000_001
        cue_source = {
            "kind": "deterministic-shuffled",
            "digest": digest,
            "value": cue,
        }
    elif method == "acquired":
        selector_ref = payload["scheduler"].get("selector")
        if not isinstance(selector_ref, Mapping):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "acquired scheduler has no selector program",
            )
        _ref, selector = _semantic_reference(
            state,
            selector_ref,
            expected_kind="Program",
            require_current=True,
        )
        activation = (
            _packet_activation(hierarchy_record["payload"], paths)
            if hierarchy_record is not None and paths
            else None
        )
        try:
            outcome = execute_semantic_program(
                selector["payload"]["program"],
                {
                    "activation": (
                        0
                        if activation is None
                        else int(activation["activation_input"])
                    ),
                    "age": int(item["age"]),
                    "base_priority": base,
                    "dependency_count": len(item["dependencies"]),
                    "has_support": 1 if paths else 0,
                    "support_count": len(paths),
                },
                action={},
            )
        except (RegionalFieldError, ValueError) as exc:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "acquired scheduler program could not execute",
            ) from exc
        values = outcome.get("values")
        if (
            outcome.get("status") != "supported"
            or not isinstance(values, Mapping)
        ):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "acquired scheduler did not return supported values",
            )
        priority = values.get("priority")
        if isinstance(priority, float) and priority.is_integer():
            priority = int(priority)
        cue = _regional_integer(
            priority,
            "acquired scheduling priority",
            minimum=-1_000_000_000,
            maximum=1_000_000_000,
        )
        cue_source = {
            "kind": "acquired-selector",
            "program": selector_ref,
            "value": cue,
        }
    return base + cue, {
        "base_priority": base,
        "cue": cue_source,
        "effective_priority": base + cue,
    }

def _packet_cue_component(
    value: Mapping[str, Any], label: str
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("kind") not in {
        "boolean",
        "missing",
        "residual",
    }:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            f"{label} cue component is invalid",
        )
    kind = value["kind"]
    if kind == "boolean":
        if set(value) != {"kind", "value"} or not isinstance(
            value["value"], bool
        ):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                f"{label} Boolean cue component is invalid",
            )
        return {"kind": kind, "normalized": int(value["value"]), **dict(value)}
    if kind == "missing":
        if set(value) != {"frame", "kind", "units"}:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                f"{label} missing cue component is invalid",
            )
        return {
            "frame": _regional_plain(value["frame"], f"{label} cue frame"),
            "kind": kind,
            "normalized": None,
            "units": _identifier(value["units"], f"{label} cue units"),
        }
    if set(value) != {
        "frame",
        "kind",
        "scale",
        "scale_units",
        "units",
        "value",
    }:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            f"{label} residual cue component is invalid",
        )
    units = _identifier(value["units"], f"{label} cue units")
    if units != _identifier(
        value["scale_units"], f"{label} cue scale units"
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            f"{label} cue residual and scale units differ",
        )
    residual = _regional_number(value["value"], f"{label} cue residual")
    scale = _regional_number(
        value["scale"],
        f"{label} cue scale",
        minimum=0.0,
        inclusive_minimum=False,
    )
    normalized = (
        math.copysign(1.0, residual)
        if abs(residual) >= scale
        else residual / scale
    )
    return {
        "frame": _regional_plain(value["frame"], f"{label} cue frame"),
        "kind": kind,
        "normalized": normalized,
        "scale": scale,
        "scale_units": units,
        "units": units,
        "value": residual,
    }


def _packet_prepare_cues(
    state: dict[str, Any],
    values: Sequence[Mapping[str, Any]],
    *,
    hierarchy: Mapping[str, Any] | None,
    assembly_ref: Mapping[str, Any] | None,
    allocation: Mapping[str, int],
    support_roots: Sequence[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Sequence)
        or len(values) > SEMANTIC_MAX_OBSERVATIONS
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning cues exceed their bounded sequence",
        )
    generated: list[dict[str, Any]] = []
    cue_refs: list[dict[str, Any]] = []
    for raw in values:
        required = {
            "consequence",
            "constraint",
            "cue_id",
            "dependencies",
            "event_kind",
            "hierarchy_id",
            "source_operation_id",
            "w_max",
        }
        if not isinstance(raw, Mapping) or set(raw) != required:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning cue has an invalid schema",
            )
        cue_id = _identifier(raw["cue_id"], "reasoning cue")
        source_operation_id = _identifier(
            raw["source_operation_id"], "reasoning cue source operation"
        )
        if raw["event_kind"] != "reasoning-work":
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "internally generated packet cues require reasoning-work attribution",
            )
        dependencies = raw["dependencies"]
        if not isinstance(dependencies, list):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning cue dependencies are invalid",
            )
        resolved_dependencies: list[dict[str, Any]] = []
        for dependency in dependencies:
            if not isinstance(dependency, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_REASONING_EPISODE",
                    "reasoning cue dependency is mistyped",
                )
            reference, _record = _semantic_reference(
                state, dependency, require_current=True
            )
            resolved_dependencies.append(reference.as_dict())
        consequence = _packet_cue_component(
            cast(Mapping[str, Any], raw["consequence"]), "consequence"
        )
        constraint = _packet_cue_component(
            cast(Mapping[str, Any], raw["constraint"]), "constraint"
        )
        w_max = _regional_number(
            raw["w_max"], "reasoning cue work maximum", minimum=0.0, maximum=1.0
        )
        normalized = [consequence["normalized"], constraint["normalized"]]
        masked = any(value is None for value in normalized)
        requested_work = (
            0.0
            if masked
            else w_max
            * (
                float(normalized[0]) * float(normalized[0])
                + float(normalized[1]) * float(normalized[1])
            )
            / 2.0
        )
        event_payload = {
            "schema": PACKET_CUE_SCHEMA,
            "consequence": consequence,
            "constraint": constraint,
            "cue_id": cue_id,
            "event_kind": "reasoning-work",
            "hierarchy_id": _identifier(
                raw["hierarchy_id"], "reasoning cue hierarchy"
            ),
            "mask": [value is not None for value in normalized],
            "normalized_flow": normalized,
            "requested_work": requested_work,
            "source_operation_id": source_operation_id,
            "w_max": w_max,
        }
        event_ref = _semantic_append_record(
            state,
            record_id=f"event:reasoning-cue:{cue_id}",
            kind="Event",
            payload=event_payload,
            epistemic_kind="derived",
            dependencies=resolved_dependencies,
            support_roots=support_roots,
            valid_time={
                "start": float(state["time"]["now"]),
                "end": float(state["time"]["now"]),
            },
        )
        _semantic_reindex_record(state, event_ref)
        obligation_ref = _semantic_append_record(
            state,
            record_id=f"obligation:reasoning-cue:{cue_id}",
            kind="Obligation",
            payload={
                "accepted_work": 0.0,
                "consumed_operation_ids": [],
                "cue": event_ref,
                "cursor": 0,
                "destination": (
                    None if hierarchy is None else hierarchy["hierarchy_id"]
                ),
                "requested_work": requested_work,
                "state": "masked" if masked else "pending",
            },
            epistemic_kind="derived",
            dependencies=(event_ref,),
            support_roots=support_roots,
        )
        _semantic_reindex_record(state, obligation_ref)
        cue_refs.extend((event_ref, obligation_ref))
        if masked or requested_work == 0.0:
            continue
        if hierarchy is None or assembly_ref is None:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "unmasked packet cue requires an assembly and hierarchy",
            )
        if hierarchy["hierarchy_id"] != raw["hierarchy_id"]:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning cue names a different packet hierarchy",
            )
        assembly = resolve_semantic_record(
            state["records"], assembly_ref, require_current=True
        )
        workspace_state = assembly["payload"].get("workspace_state")
        if not isinstance(workspace_state, Mapping):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "packet cue destination has no owned numerical workspace",
            )
        packets = {
            packet["path"]: packet for packet in hierarchy["packets"]
        }
        active = [packets[path] for path in hierarchy["active_paths"]]
        sizes = [
            int(packet["support"]["stop"])
            - int(packet["support"]["start"])
            for packet in active
        ]
        total_ports = sum(sizes)
        shares: list[float] = []
        allocated = 0.0
        for index, size in enumerate(sizes):
            if index + 1 == len(sizes):
                share = max(0.0, requested_work - allocated)
            else:
                share = requested_work * float(size) / float(total_ports)
                allocated += share
            shares.append(share)
        prior_item: str | None = None
        for index, (packet, share) in enumerate(zip(active, shares, strict=True)):
            item_id = f"cue:{cue_id}:{index}"
            dependency_items = [] if prior_item is None else [prior_item]
            generated.append(
                {
                    "assumptions": {
                        "cue": event_ref,
                        "cue_obligation": obligation_ref,
                    },
                    "cue": {
                        "component": "scale",
                        "event_kind": "reasoning-work",
                        "flow_signal": normalized,
                        "obligation": obligation_ref,
                        "path": packet["path"],
                        "requested_work": share,
                    },
                    "dependencies": dependency_items,
                    "invocation": {
                        "arguments": {},
                        "expected_return": {"status": ["halted"]},
                        "kernel": RESONANT_REGIONAL_KERNEL_NAME,
                        "state": dict(workspace_state),
                    },
                    "item_id": item_id,
                    "kind": "regional",
                    "priority": 1_000_000,
                    "read_footprint": [assembly_ref, event_ref],
                    "required_checks": [obligation_ref],
                    "scope": {"cue_id": cue_id},
                    "support_paths": [str(packet["path"])],
                    "write_footprint": [assembly_ref],
                }
            )
            prior_item = item_id
    if generated:
        share = {
            name: max(
                1 if name in {"storage_words", "work"} else 0,
                int(allocation[name]) // len(generated),
            )
            for name in PACKET_RESOURCE_NAMES
        }
        share["work"] = max(1, min(share["work"], 4_096))
        for item in generated:
            item["invocation"]["reservation"] = dict(share)
    return generated, cue_refs


def _packet_materialize_invocation(
    state: Mapping[str, Any],
    episode: Mapping[str, Any],
    item: Mapping[str, Any],
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    invocation = _regional_plain(
        dict(item["invocation"]), "selected reasoning invocation"
    )
    cue = item.get("cue")
    if not isinstance(cue, Mapping):
        return invocation
    source = episode["payload"] if payload is None else payload
    assemblies = source.get("assemblies", [])
    if len(assemblies) != 1:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet cue work requires one owning assembly",
        )
    assembly = resolve_semantic_record(
        state["records"], assemblies[0], require_current=True
    )
    workspace_state = assembly["payload"].get("workspace_state")
    if not isinstance(workspace_state, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet cue work has no current owned workspace",
        )
    impulse = {
        "component": cue["component"],
        "event_kind": cue["event_kind"],
        "evidence_tick": int(
            workspace_state.get("local_ticks", {}).get("evidence", 0)
        ),
        "flow_signal": cue["flow_signal"],
        "path": cue["path"],
        "work_budget": cue["requested_work"],
    }
    try:
        if workspace_state.get("phase") == "done":
            child_state = resume_regional_state(
                workspace_state, packet_impulse=impulse
            )
        else:
            child_state = _regional_plain(
                dict(workspace_state), "packet cue initial workspace"
            )
            continuation = child_state.get("continuation", {})
            if (
                child_state.get("phase") != "running"
                or continuation.get("operation") != "prepare"
                or bool(continuation.get("initialized"))
            ):
                raise ResonantNumericalError(
                    "packet cue is not at a valid integration boundary"
                )
            child_state["request"] = {
                **dict(child_state["request"]),
                "impulse": impulse,
                "operation": "packet-impulse",
            }
    except (ResonantNumericalError, TypeError, ValueError) as exc:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet cue could not construct a source-bound child state",
        ) from exc
    invocation["state"] = child_state
    return invocation


def _packet_effective_reservation(
    item: Mapping[str, Any], resources: Mapping[str, Any]
) -> dict[str, int]:
    """Return the reservation one work item holds against the allowance.

    A declared reservation is the item's own bound. An item that declares none
    may use whatever the episode has left, so its reservation is the remaining
    allowance rather than the whole limit, which would strand every later item
    once anything has been charged.
    """

    reservation = item["reservation"]
    if item.get("reservation_declared", True):
        return {name: int(reservation[name]) for name in PACKET_RESOURCE_NAMES}
    return {
        name: max(
            0,
            int(resources["limits"][name])
            - int(resources["charged"][name])
            - int(resources["reserved"][name]),
        )
        for name in PACKET_RESOURCE_NAMES
    }


def _packet_select_work(
    state: dict[str, Any],
    episode: Mapping[str, Any],
    payload: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, int]:
    payload = _regional_plain(
        dict(episode["payload"] if payload is None else payload),
        "reasoning episode payload",
    )
    items = payload["work_items"]
    by_id = {item["item_id"]: item for item in items}
    terminal_statuses = {
        "completed",
        "failed",
        "limited",
        "reused",
        "skipped",
    }
    for item in items:
        if item["status"] != "deferred":
            continue
        dependencies = [by_id[item_id] for item_id in item["dependencies"]]
        if any(
            dependency["status"] in {"failed", "limited", "skipped"}
            for dependency in dependencies
        ):
            item["status"] = "skipped"
            item["result"] = {
                "status": "missing-evidence",
                "reason": "prerequisite-did-not-complete",
            }
        elif all(
            dependency["status"] in {"completed", "reused"}
            for dependency in dependencies
        ):
            item["status"] = "ready"
    for item in items:
        if item["status"] != "ready":
            continue
        shared = next(
            (
                prior
                for prior in items
                if prior["item_id"] != item["item_id"]
                and prior["status"] in {"completed", "reused"}
                and prior["reuse_key"] == item["reuse_key"]
            ),
            None,
        )
        if shared is not None:
            item["status"] = "reused"
            item["result"] = {
                "schema": "cassifi.packet-shared-result.v1",
                "result": shared["result"],
                "shared_item_id": shared["item_id"],
                "status": "reused",
            }
            payload["shared_work"].append(
                {
                    "consumer": item["item_id"],
                    "producer": shared["item_id"],
                    "reuse_key": item["reuse_key"],
                }
            )
            payload["phase"] = "ready"
            return payload, None, 1
    candidates = [item for item in items if item["status"] == "ready"]
    if not candidates:
        if all(item["status"] in terminal_statuses for item in items):
            payload["phase"] = "terminal"
        else:
            payload["phase"] = "waiting"
        return payload, None, 1
    hierarchy_record = _packet_hierarchy_record(state, episode, payload)
    scored: list[tuple[dict[str, Any], int, dict[str, Any]]] = []
    resources = payload["resources"]
    for item in candidates:
        reservation = _packet_effective_reservation(item, resources)
        fits = all(
            int(resources["charged"][name])
            + int(resources["reserved"][name])
            + int(reservation[name])
            <= int(resources["limits"][name])
            for name in PACKET_RESOURCE_NAMES
        )
        if not fits:
            continue
        score, details = _packet_scheduler_score(
            state, episode, item, hierarchy_record
        )
        scored.append((item, score, details))
    if not scored:
        payload["phase"] = "terminal"
        payload["limitation"] = {
            "kind": "resource-exhausted",
            "remaining_items": [
                item["item_id"] for item in candidates
            ],
        }
        for item in candidates:
            item["status"] = "limited"
            item["result"] = payload["limitation"]
        return payload, None, 1
    fairness_bound = int(payload["scheduler"]["fairness_bound"])
    dispatch_number = int(payload["scheduler"]["dispatch_count"]) + 1
    if dispatch_number % fairness_bound == 0:
        selected, score, details = min(
            scored,
            key=lambda row: (
                int(row[0]["ready_sequence"]),
                str(row[0]["item_id"]),
            ),
        )
        selection_reason = "oldest-ready-fairness"
    else:
        selected, score, details = max(
            scored,
            key=lambda row: (
                int(row[1]),
                int(row[0]["age"]),
                -int(row[0]["ready_sequence"]),
                str(row[0]["item_id"]),
            ),
        )
        selection_reason = "priority"
    _packet_authorize_source_binding(payload, selected)
    for candidate, _score, _details in scored:
        if candidate["item_id"] != selected["item_id"]:
            candidate["age"] = int(candidate["age"]) + 1
    selected["age"] = 0
    selected["reservation"] = _packet_effective_reservation(selected, resources)
    reservation = selected["reservation"]
    for name in PACKET_RESOURCE_NAMES:
        resources["reserved"][name] += int(reservation[name])
    call_id = (
        f"reasoning:{payload['episode_id']}:{selected['item_id']}:"
        f"{dispatch_number}"
    )
    return_binding = f"{call_id}:return"
    snapshot = {
        "dispatch": dispatch_number,
        "eligible": [
            {
                "age": item["age"],
                "item_id": item["item_id"],
                "score": item_score,
            }
            for item, item_score, _details in sorted(
                scored, key=lambda row: str(row[0]["item_id"])
            )
        ],
        "hierarchy": (
            None
            if hierarchy_record is None
            else semantic_record_ref(hierarchy_record).as_dict()
        ),
        "reason": selection_reason,
        "selected": selected["item_id"],
        "selected_score": score,
        "selected_score_details": details,
        "selected_source_binding": selected.get("source_binding"),
        "selected_support": _packet_support_spans(
            None if hierarchy_record is None else hierarchy_record["payload"],
            selected.get("support_paths", []),
        ),
    }
    snapshot["snapshot_sha256"] = sha256_value(snapshot)
    payload["scheduler"]["dispatch_count"] = dispatch_number
    payload["scheduler"]["snapshots"].append(snapshot)
    selected["status"] = "reserved"
    payload["active"] = {
        "call_id": call_id,
        "item_id": selected["item_id"],
        "request_sha256": None,
        "reservation": reservation,
        "reservation_sha256": sha256_value(reservation),
        "return_binding": return_binding,
        "selection_sha256": snapshot["snapshot_sha256"],
    }
    payload["phase"] = "reserved"
    if selected["invocation"] is None:
        return payload, None, 1
    _identity, _digest, emitted = _packet_build_emission(
        state, episode, payload, selected
    )
    payload["active"]["request_sha256"] = _digest
    return payload, emitted, 1


def _packet_build_emission(
    state: Mapping[str, Any],
    episode: Mapping[str, Any],
    payload: Mapping[str, Any],
    item: Mapping[str, Any],
) -> tuple[dict[str, Any], str, dict[str, Any] | None]:
    """Build the published invitation, its content identity, and the host payload."""

    invocation = _packet_materialize_invocation(state, episode, item, payload)
    dependency_refs = [
        *payload["dependencies"],
        *payload["assemblies"],
        *([] if payload["hierarchy"] is None else [payload["hierarchy"]]),
    ]
    request_identity = json.loads(
        canonical_json_bytes(
            {
                "content_sha256": payload["content_sha256"],
                "dependencies": dependency_refs,
                "episode_id": payload["episode_id"],
                "invocation": invocation,
                "item_id": item["item_id"],
                "selection_sha256": payload["active"]["selection_sha256"],
            }
        )
    )
    request_sha256 = sha256_value(request_identity)
    if invocation["kernel"] is None:
        emitted = {
            "adapter": invocation["adapter"],
            "call_id": payload["active"]["call_id"],
            "request": invocation["request"],
            "request_identity": request_identity,
            "request_sha256": request_sha256,
            "reservation": payload["active"]["reservation"],
            "return_binding": payload["active"]["return_binding"],
        }
    else:
        emitted = {
            key: value
            for key, value in {
                "allowance": (
                    payload["resources"]["limits"]
                    if payload["resources"]["enforced"]
                    else None
                ),
                "allowance_id": (
                    payload["root_allowance_id"]
                    if payload["resources"]["enforced"]
                    else None
                ),
                "arguments": invocation["arguments"],
                "call_id": payload["active"]["call_id"],
                "dependencies": dependency_refs,
                "expected_return": invocation["expected_return"],
                "kernel": invocation["kernel"],
                "kind": f"reasoning-{item['kind']}",
                "request_identity": request_identity,
                "reservation": (
                    payload["active"]["reservation"]
                    if payload["resources"]["enforced"]
                    else None
                ),
                "return_binding": payload["active"]["return_binding"],
                "state": invocation["state"],
            }.items()
            if value is not None
        }
    return request_identity, request_sha256, emitted

def _packet_reconcile_resources(
    payload: dict[str, Any],
    reservation: Mapping[str, Any],
    actual: Mapping[str, Any],
) -> None:
    reserved = _packet_resources(
        reservation, "reasoning resource reservation", require_work=True
    )
    consumed = _packet_resources(
        actual,
        "reasoning consumed resources",
    )
    if payload["resources"]["enforced"] and any(
        consumed[name] > reserved[name] for name in PACKET_RESOURCE_NAMES
    ):
        raise FieldIntelligenceError(
            "WORK_CAPACITY",
            "reasoning result exceeds its published reservation",
        )
    resources = payload["resources"]
    for name in PACKET_RESOURCE_NAMES:
        resources["reserved"][name] -= reserved[name]
        resources["charged"][name] += consumed[name]
        if resources["reserved"][name] < 0 or (
            resources["enforced"]
            and resources["charged"][name] > resources["limits"][name]
        ):
            raise FieldIntelligenceError(
                "WORK_CAPACITY",
                "reasoning resource reconciliation exceeds the root allowance",
            )


def _packet_execute_local(
    state: dict[str, Any],
    episode: Mapping[str, Any],
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    active = payload["active"]
    if not isinstance(active, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "local reasoning work has no active reservation",
        )
    item = next(
        row
        for row in payload["work_items"]
        if row["item_id"] == active["item_id"]
    )
    dependencies: list[dict[str, Any]] = []
    if item["kind"] == "readout":
        result, actual = _packet_affine_readout(item["readout"])
    elif item["kind"] == "branch":
        contract = item["branch"]
        if (
            not isinstance(contract, Mapping)
            or set(contract) != {"hypotheses", "parent_rule"}
            or contract["parent_rule"]
            not in {"conditional", "conjunction", "supported-set"}
            or not isinstance(contract["hypotheses"], list)
            or not contract["hypotheses"]
            or len(contract["hypotheses"]) > SEMANTIC_MAX_ALTERNATIVES
        ):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning branch contract is invalid",
            )
        alternatives: list[dict[str, Any]] = []
        for raw_hypothesis in contract["hypotheses"]:
            if (
                not isinstance(raw_hypothesis, Mapping)
                or set(raw_hypothesis)
                != {"assumptions", "conclusion", "hypothesis_id"}
            ):
                raise FieldIntelligenceError(
                    "INVALID_REASONING_EPISODE",
                    "reasoning hypothesis is invalid",
                )
            hypothesis_id = _identifier(
                raw_hypothesis["hypothesis_id"],
                "reasoning hypothesis",
            )
            claim = _semantic_append_record(
                state,
                record_id=(
                    f"value:reasoning:{payload['episode_id']}:"
                    f"{item['item_id']}:{hypothesis_id}"
                ),
                kind="Value",
                payload={
                    "assumptions": _regional_plain(
                        raw_hypothesis["assumptions"],
                        "reasoning hypothesis assumptions",
                    ),
                    "conclusion": _regional_plain(
                        raw_hypothesis["conclusion"],
                        "reasoning hypothesis conclusion",
                    ),
                    "hypothesis_id": hypothesis_id,
                    "purpose": "reasoning-alternative",
                },
                epistemic_kind="hypothetical",
                dependencies=payload["dependencies"],
                support_roots=episode["support_roots"],
                scope={
                    "episode_id": payload["episode_id"],
                    "hypothesis_id": hypothesis_id,
                },
            )
            _semantic_reindex_record(state, claim)
            dependencies.append(claim)
            alternatives.append(
                {
                    "assumptions": raw_hypothesis["assumptions"],
                    "claim": claim,
                    "conclusion": raw_hypothesis["conclusion"],
                    "hypothesis_id": hypothesis_id,
                }
            )
        result = {
            "schema": "cassifi.packet-branch-result.v1",
            "alternatives": alternatives,
            "parent_rule": contract["parent_rule"],
            "status": "alternatives",
        }
        actual = {name: 0 for name in PACKET_RESOURCE_NAMES}
        actual["branch_count"] = len(alternatives)
        actual["frontier_size"] = len(alternatives)
        actual["storage_words"] = (
            len(canonical_json_bytes(result)) + 3
        ) // 4
        actual["work"] = len(alternatives)
    elif item["kind"] == "refine":
        refinement = item["refinement"]
        if (
            not isinstance(refinement, Mapping)
            or set(refinement) != {"hierarchy_id", "path", "reason"}
        ):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning refinement contract is invalid",
            )
        hierarchy_record = _packet_hierarchy_record(state, episode, payload)
        if (
            hierarchy_record is None
            or hierarchy_record["payload"]["hierarchy_id"]
            != refinement["hierarchy_id"]
        ):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning refinement hierarchy is unavailable",
            )
        hierarchy = _regional_plain(
            dict(hierarchy_record["payload"]),
            "reasoning refinement hierarchy",
        )
        path = str(refinement["path"])
        if path not in hierarchy["active_paths"]:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning refinement path is not active",
            )
        parent = next(
            packet for packet in hierarchy["packets"]
            if packet["path"] == path
        )
        try:
            left, right = split_helical_packet(parent)
        except (ResonantNumericalError, TypeError, ValueError) as exc:
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning refinement cannot split this support",
            ) from exc
        hierarchy["packets"].extend(
            (
                _regional_plain(dict(left), "left refined packet"),
                _regional_plain(dict(right), "right refined packet"),
            )
        )
        hierarchy["packets"] = [
            packet
            for _path, packet in sorted(
                {
                    str(packet["path"]): packet
                    for packet in hierarchy["packets"]
                }.items()
            )
        ]
        hierarchy["active_paths"] = sorted(
            [
                active_path
                for active_path in hierarchy["active_paths"]
                if active_path != path
            ]
            + [str(left["path"]), str(right["path"])],
            key=lambda active_path: int(
                next(
                    packet["support"]["start"]
                    for packet in hierarchy["packets"]
                    if packet["path"] == active_path
                )
            ),
        )
        hierarchy["max_depth"] = max(
            len(packet["path"]) for packet in hierarchy["packets"]
        )
        hierarchy["initial_activation"] = _packet_activation(
            hierarchy, hierarchy["active_paths"]
        )
        hierarchy_ref = _semantic_append_record(
            state,
            record_id=str(hierarchy_record["id"]),
            kind="Value",
            payload=hierarchy,
            epistemic_kind="derived",
            dependencies=(
                semantic_record_ref(hierarchy_record).as_dict(),
            ),
            support_roots=hierarchy_record["support_roots"],
        )
        _semantic_reindex_record(state, hierarchy_ref)
        payload["hierarchy"] = hierarchy_ref
        dependencies.append(hierarchy_ref)
        result = {
            "schema": "cassifi.packet-refinement-result.v1",
            "children": [left["path"], right["path"]],
            "hierarchy": hierarchy_ref,
            "parent": path,
            "reason": _regional_plain(
                refinement["reason"], "reasoning refinement reason"
            ),
            "status": "refined",
        }
        actual = {name: 0 for name in PACKET_RESOURCE_NAMES}
        actual["frontier_size"] = 1
        actual["refinement_depth"] = 1
        actual["storage_words"] = (
            len(canonical_json_bytes(left))
            + len(canonical_json_bytes(right))
            + 7
        ) // 4
        actual["work"] = (
            int(parent["support"]["stop"])
            - int(parent["support"]["start"])
        )
    else:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "selected local reasoning work is not executable",
        )
    _packet_reconcile_resources(payload, active["reservation"], actual)
    item["status"] = "completed"
    item["result"] = result
    payload["results"][item["item_id"]] = result
    payload["active"] = None
    payload["phase"] = "ready"
    return payload, dependencies, max(1, int(actual["work"]))


def _packet_update_workspace_from_return(
    state: dict[str, Any],
    episode: Mapping[str, Any],
    payload: dict[str, Any],
    item: Mapping[str, Any],
    returned: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(item.get("cue"), Mapping):
        return []
    task = returned.get("task")
    if not isinstance(task, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet cue return omitted its owned numerical state",
        )
    try:
        workspace = workspace_from_regional_state(
            task, require_complete=True
        )
    except (ResonantNumericalError, TypeError, ValueError) as exc:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet cue returned an invalid numerical successor",
        ) from exc
    assemblies = payload["assemblies"]
    if len(assemblies) != 1:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "packet cue successor has no unique owning assembly",
        )
    _assembly_ref, assembly = _semantic_reference(
        state, assemblies[0], expected_kind="Binding", require_current=True
    )
    assembly_payload = {
        **assembly["payload"],
        "workspace_state": _regional_plain(
            dict(task), "returned packet workspace state"
        ),
    }
    assembly_successor = _semantic_append_record(
        state,
        record_id=str(assembly["id"]),
        kind="Binding",
        payload=assembly_payload,
        epistemic_kind="derived",
        dependencies=(
            semantic_record_ref(assembly).as_dict(),
            item["cue"]["obligation"],
        ),
        support_roots=assembly["support_roots"],
    )
    _semantic_reindex_record(state, assembly_successor)
    payload["assemblies"] = [assembly_successor]
    hierarchy_record = _packet_hierarchy_record(state, episode, payload)
    updates = [assembly_successor]
    if hierarchy_record is not None:
        hierarchy = _regional_plain(
            dict(hierarchy_record["payload"]),
            "returned packet hierarchy",
        )
        refreshed = [
            _regional_plain(
                dict(analyze_helical_packet(workspace, path=packet["path"])),
                "refreshed numerical packet",
            )
            for packet in hierarchy["packets"]
        ]
        hierarchy.update(
            {
                "layout_identity": workspace.profile.layout_identity,
                "packets": refreshed,
                "profile_sha256": refreshed[0]["profile_sha256"],
                "source_state_sha256": workspace.state_sha256,
            }
        )
        hierarchy["initial_activation"] = _packet_activation(
            hierarchy, hierarchy["active_paths"]
        )
        hierarchy_successor = _semantic_append_record(
            state,
            record_id=str(hierarchy_record["id"]),
            kind="Value",
            payload=hierarchy,
            epistemic_kind="derived",
            dependencies=(
                semantic_record_ref(hierarchy_record).as_dict(),
                assembly_successor,
            ),
            support_roots=hierarchy_record["support_roots"],
        )
        _semantic_reindex_record(state, hierarchy_successor)
        payload["hierarchy"] = hierarchy_successor
        updates.append(hierarchy_successor)
    cue_identifier = str(item["cue"]["obligation"]["id"])
    cue_obligation = _semantic_current_record(
        state, "Obligation", cue_identifier
    )
    child_result = returned.get("result")
    accepted_work = (
        float(child_result.get("applied_work", 0.0))
        if isinstance(child_result, Mapping)
        else 0.0
    )
    cue_payload = {
        **cue_obligation["payload"],
        "accepted_work": float(
            cue_obligation["payload"].get("accepted_work", 0.0)
        )
        + accepted_work,
        "consumed_operation_ids": [
            *cue_obligation["payload"].get("consumed_operation_ids", []),
            returned["call_id"],
        ],
        "cursor": int(cue_obligation["payload"].get("cursor", 0)) + 1,
        "state": "advancing",
    }
    cue_successor = _semantic_append_record(
        state,
        record_id=str(cue_obligation["id"]),
        kind="Obligation",
        payload=cue_payload,
        epistemic_kind="derived",
        dependencies=(
            semantic_record_ref(cue_obligation).as_dict(),
            assembly_successor,
        ),
        support_roots=cue_obligation["support_roots"],
    )
    _semantic_reindex_record(state, cue_successor)
    cue_reference = dict(cue_successor)
    for row in payload["work_items"]:
        row_cue = row.get("cue")
        if (
            isinstance(row_cue, Mapping)
            and isinstance(row_cue.get("obligation"), Mapping)
            and str(row_cue["obligation"]["id"]) == cue_identifier
        ):
            row_cue["obligation"] = cue_reference
            assumptions = row.get("assumptions")
            if isinstance(assumptions, Mapping) and "cue_obligation" in assumptions:
                assumptions["cue_obligation"] = cue_reference
    payload["energy"]["accepted"] += accepted_work
    payload["energy"]["requested"] += float(
        item["cue"]["requested_work"]
    )
    updates.append(cue_successor)
    return updates


def _packet_consume_return(
    state: dict[str, Any],
    episode: Mapping[str, Any],
    payload: dict[str, Any],
    *,
    external_return: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    active = payload.get("active")
    if not isinstance(active, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning return has no active operation",
        )
    binding = str(active["return_binding"])
    returned = (
        external_return
        if external_return is not None
        else state["invocation_returns"].get(binding)
    )
    if not isinstance(returned, Mapping):
        payload["phase"] = "running-child"
        return payload, [], 1
    if (
        returned.get("call_id") != active["call_id"]
        or returned.get("request_sha256") != active["request_sha256"]
        or returned.get("status")
        not in {
            "cancelled",
            "counter-exhausted",
            "exhausted",
            "faulted",
            "halted",
        }
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning return identity or disposition is invalid",
        )
    if external_return is None:
        del state["invocation_returns"][binding]
    if returned.get("schema") == "cassifi.learning-computer-child-return.v2":
        actual = _packet_resources(
            cast(Mapping[str, Any], returned.get("resources")),
            "reasoning child resources",
        )
    else:
        actual = {name: 0 for name in PACKET_RESOURCE_NAMES}
        actual["storage_words"] = (
            len(canonical_json_bytes(returned)) + 3
        ) // 4
        actual["work"] = 1
    _packet_reconcile_resources(payload, active["reservation"], actual)
    item = next(
        row
        for row in payload["work_items"]
        if row["item_id"] == active["item_id"]
    )
    child_status = str(returned["status"])
    child_result = _regional_plain(
        returned.get("result"), "reasoning child result"
    )
    item["result"] = {
        "child_status": child_status,
        "continuation": returned.get("continuation"),
        "outcome": returned.get("outcome"),
        "resources": actual,
        "result": child_result,
        "state_sha256": returned.get("state_sha256"),
        "status": (
            "completed"
            if child_status == "halted"
            else "failed" if child_status == "faulted" else "limited"
        ),
        "task": returned.get("task"),
    }
    item["status"] = item["result"]["status"]
    payload["results"][item["item_id"]] = item["result"]
    updates = _packet_update_workspace_from_return(
        state, episode, payload, item, returned
    )
    payload["consumed_returns"].append(
        {
            "call_id": active["call_id"],
            "request_sha256": active["request_sha256"],
            "return_binding": binding,
            "state_sha256": returned.get("state_sha256"),
        }
    )
    payload["active"] = None
    payload["phase"] = "ready"
    return payload, updates, max(1, int(actual["work"]))
_PACKET_LEGACY_ALLOCATION_NAMES = frozenset(
    {"evidence_reads", "model_calls", "storage_words", "work"}
)
_PACKET_LOCAL_RESULT_SCHEMAS = frozenset(
    {
        "cassifi.packet-affine-readout-result.v1",
        "cassifi.packet-branch-result.v1",
        "cassifi.packet-refinement-result.v1",
    }
)
_PACKET_RESULT_STATUSES = {
    "alternatives": "alternatives",
    "exact": "supported",
    "estimated": "supported",
    "non-identifiable": "non-identifiable",
    "pending-observation": "pending-observation",
    "refined": "supported",
    "representation-insufficient": "representation-insufficient",
    "resource-exhausted": "resource-exhausted",
    "support-gap": "support-gap",
    "supported": "supported",
    "unresolved": "non-identifiable",
    "waiting": "pending-observation",
}


def _packet_item_status(item: Mapping[str, Any]) -> str:
    """Translate one completed work item's outcome into an episode status."""

    result = item["result"]
    if not isinstance(result, Mapping):
        return "support-gap"
    if result.get("schema") == "cassifi.packet-shared-result.v1":
        inner = result.get("result")
        if isinstance(inner, Mapping):
            return _packet_item_status({"result": inner})
    if result.get("schema") in _PACKET_LOCAL_RESULT_SCHEMAS:
        return _PACKET_RESULT_STATUSES.get(
            str(result.get("status")), "support-gap"
        )
    child = result.get("result")
    if not isinstance(child, Mapping):
        return "support-gap"
    accepted = child.get("accepted")
    if isinstance(accepted, bool):
        return "supported" if accepted else "support-gap"
    return _PACKET_RESULT_STATUSES.get(str(child.get("status")), "support-gap")


def _packet_allocation(
    state: Mapping[str, Any], value: Any
) -> tuple[dict[str, int], bool]:
    """Normalize a root allocation and report whether its limits are enforced.

    The four-name allocation is the first design's direct-caller form: it is
    accepted, marked unenforced, and every other resource reads as zero.  The
    complete seven-resource allocation is the episode form and is enforced.
    """

    if not isinstance(value, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE", "reasoning allocation is invalid"
        )
    if set(value) == _PACKET_LEGACY_ALLOCATION_NAMES:
        allocation = {name: 0 for name in PACKET_RESOURCE_NAMES}
        for name in _PACKET_LEGACY_ALLOCATION_NAMES:
            allocation[name] = _regional_integer(
                value[name],
                f"reasoning {name}",
                minimum=1 if name == "work" else 0,
            )
        if allocation["work"] > state["bounds"]["max_work"]:
            raise FieldIntelligenceError(
                "WORK_CAPACITY", "reasoning work allocation exceeds its bound"
            )
        return allocation, False
    allocation = _packet_resources(
        value, "reasoning allocation", require_work=True
    )
    if allocation["work"] > state["bounds"]["max_work"]:
        raise FieldIntelligenceError(
            "WORK_CAPACITY", "reasoning work allocation exceeds its bound"
        )
    return allocation, True


def _packet_selection_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) - {"method", "selector"}:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning selection contract is invalid",
        )
    method = value.get("method", "baseline")
    if method not in PACKET_SELECTION_METHODS:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning selection method is unsupported",
        )
    selector = value.get("selector")
    if method == "acquired":
        if not isinstance(selector, Mapping):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "acquired selection requires a selector program",
            )
    elif selector is not None:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "only acquired selection accepts a selector program",
        )
    return {
        "method": method,
        "selector": (
            None
            if selector is None
            else _regional_plain(
                dict(selector), "reasoning selection selector"
            )
        ),
    }


def _packet_stopping_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) - {"max_dispatches"}:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning stopping contract is invalid",
        )
    return {
        "max_dispatches": _regional_integer(
            value.get("max_dispatches", 64),
            "reasoning dispatch limit",
            minimum=1,
            maximum=1_000_000,
        )
    }


def _packet_direct_request(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or value.get("operation") not in SEMANTIC_OPERATION_NAMES
        or value.get("operation")
        in {
            "admit-reasoning-input",
            "advance-reasoning",
            "begin-reasoning",
            "finish-reasoning",
        }
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning episode request or dependencies are invalid",
        )
    return _regional_plain(dict(value), "reasoning child request")


def _packet_work_program(
    state: Mapping[str, Any],
    *,
    allocation: Mapping[str, int],
    hierarchy: Mapping[str, Any] | None = None,
    provided: Mapping[str, Any] | None,
    program_ref: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if program_ref is not None:
        _ref, program = _semantic_reference(
            state, program_ref, expected_kind="Program", require_current=True
        )
        if program["payload"].get("program_role") != "reasoning":
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning program reference is not a reasoning program",
            )
        provided = program["payload"].get("work_program")
    allowed = {"selection", "stopping", "work_items"}
    if (
        not isinstance(provided, Mapping)
        or set(provided) - allowed
        or not isinstance(provided.get("work_items"), list)
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning program has an invalid schema",
        )
    items = _packet_validate_work_program(
        provided["work_items"], allocation=allocation, hierarchy=hierarchy
    )
    selection = _packet_selection_contract(provided.get("selection", {}))
    stopping = _packet_stopping_contract(provided.get("stopping", {}))
    return items, selection, stopping


def _packet_episode_payload(
    *,
    allocation: Mapping[str, int],
    enforced: bool,
    assemblies: Sequence[Mapping[str, Any]],
    content_sha256: str,
    dependencies: Sequence[Mapping[str, Any]],
    episode_id: str,
    hierarchy: Mapping[str, Any] | None,
    items: Sequence[Mapping[str, Any]],
    question: Any,
    return_binding: str,
    scope: Any,
    stopping: Mapping[str, Any],
    support_roots: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema": PACKET_REASONING_EPISODE_SCHEMA,
        "active": None,
        "assemblies": list(assemblies),
        "assistance": "supplied",
        "consumed_returns": [],
        "content_sha256": content_sha256,
        "dependencies": list(dependencies),
        "episode_id": episode_id,
        "inputs": [],
        "limitation": None,
        "phase": "ready",
        "question": _regional_plain(question, "reasoning question"),
        "resources": {
            "charged": {name: 0 for name in PACKET_RESOURCE_NAMES},
            "enforced": bool(enforced),
            "limits": dict(allocation),
            "reserved": {name: 0 for name in PACKET_RESOURCE_NAMES},
        },
        "results": {},
        "return_binding": return_binding,
        "root_allowance_id": f"reasoning:{episode_id}",
        "scheduler": {
            "dispatch_count": 0,
            "fairness_bound": PACKET_SCHEDULER_FAIRNESS_BOUND,
            "snapshots": [],
            "method": "baseline",
            "selector": None,
        },
        "scope": _regional_plain(scope, "reasoning scope"),
        "shared_work": [],
        "stopping": dict(stopping),
        "energy": {"accepted": 0.0, "requested": 0.0},
        "hierarchy": None if hierarchy is None else dict(hierarchy),
        "work_items": [_regional_plain(dict(item), "reasoning work item") for item in items],
        "support_roots": list(support_roots),
    }


def _packet_episode_status(payload: Mapping[str, Any]) -> str:
    statuses: list[str] = []
    failures = False
    waiting = False
    for item in payload["work_items"]:
        if item["status"] in {"completed", "reused"}:
            statuses.append(_packet_item_status(item))
        elif item["status"] in {"failed", "limited", "skipped"}:
            failures = True
        else:
            waiting = True
    if waiting:
        return "pending-observation"
    limitation = payload.get("limitation")
    if (
        failures
        and isinstance(limitation, Mapping)
        and limitation.get("kind") == "resource-exhausted"
    ):
        return "resource-exhausted"
    if "supported" in statuses and not failures and len(set(statuses)) == 1:
        return "supported"
    if "alternatives" in statuses and not failures and len(set(statuses)) == 1:
        return "alternatives"
    distinct = {status for status in statuses if status != "support-gap"}
    if not failures and len(statuses) == 1 and statuses[0] != "support-gap":
        return statuses[0]
    if not failures and len(distinct) == 1 and statuses and all(
        status == statuses[0] for status in statuses
    ):
        return statuses[0]
    return "support-gap"


def _packet_retained_invocation(
    state: dict[str, Any],
    episode: Mapping[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Re-emit a retained reservation so a crashed dispatch can be retried."""

    active = payload["active"]
    item = next(
        row
        for row in payload["work_items"]
        if row["item_id"] == active["item_id"]
    )
    _identity, digest, emitted = _packet_build_emission(
        state, episode, payload, item
    )
    if digest != active["request_sha256"] or emitted is None:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "retained reasoning reservation changed its declared invocation",
        )
    return emitted


def _packet_transition(
    state: dict[str, Any],
    episode: Mapping[str, Any],
    payload: dict[str, Any],
    *,
    external_return: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, bool, list[str]]:
    """Advance the work loop by one bounded phase."""

    notes: list[str] = []
    emitted: dict[str, Any] | None = None
    active = payload.get("active")
    if isinstance(active, Mapping):
        binding = str(active["return_binding"])
        returned = (
            external_return
            if external_return is not None
            else state["invocation_returns"].get(binding)
        )
        if isinstance(returned, Mapping):
            payload["phase"] = "checking-return"
            payload, _updates, _work = _packet_consume_return(
                state,
                episode,
                payload,
                external_return=external_return,
            )
            notes.append("consumed-return")
        else:
            emitted = _packet_retained_invocation(state, episode, payload)
            return payload, emitted, False, [*notes, "retained-reservation"]
    if payload["phase"] == "terminal":
        return payload, None, True, [*notes, "terminal"]
    if int(payload["scheduler"]["dispatch_count"]) >= int(
        payload["stopping"]["max_dispatches"]
    ):
        payload["phase"] = "waiting"
        payload["limitation"] = {
            "kind": "dispatch-limit",
            "max_dispatches": int(payload["stopping"]["max_dispatches"]),
        }
        return payload, None, False, [*notes, "dispatch-limit"]
    payload, emitted, _work = _packet_select_work(state, episode, payload)
    if emitted is not None:
        return payload, emitted, False, [*notes, "emitted-invocation"]
    if payload["phase"] == "reserved" and isinstance(payload["active"], Mapping):
        payload, _dependencies, _work = _packet_execute_local(
            state, episode, payload
        )
        notes.append("local-step")
        if payload["phase"] == "terminal":
            return payload, None, True, notes
    return payload, None, payload["phase"] == "terminal", notes


def _semantic_begin_reasoning(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("allocation", "episode_id", "question"),
        optional=(
            "assemblies",
            "assistance",
            "cues",
            "dependencies",
            "hierarchy",
            "program",
            "program_ref",
            "request",
            "scope",
            "support_roots",
        ),
    )
    episode_id = _identifier(request["episode_id"], "reasoning episode")
    supplied_forms = [
        name
        for name in ("program", "program_ref", "request")
        if request.get(name) is not None
    ]
    if len(supplied_forms) > 1 or not (
        supplied_forms or request.get("cues")
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning episode requires one request, program, or cue work",
        )
    allocation, enforced = _packet_allocation(state, request["allocation"])
    dependencies = request.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning episode request or dependencies are invalid",
        )
    resolved_dependencies: list[dict[str, Any]] = []
    for raw in dependencies:
        if not isinstance(raw, Mapping):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning dependencies must be typed references",
            )
        reference, _record = _semantic_reference(
            state, raw, require_current=True
        )
        resolved_dependencies.append(reference.as_dict())
    support_roots = request.get("support_roots", [])
    if not isinstance(support_roots, Sequence) or isinstance(
        support_roots, (str, bytes)
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE", "reasoning support roots are invalid"
        )
    assistance = request.get("assistance", "supplied")
    if assistance not in {"acquired", "supplied"}:
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning assistance boundary is invalid",
        )
    return_binding = f"reasoning:{episode_id}:result"
    obligation_id = f"obligation:reasoning:{episode_id}"
    if obligation_id in state["current"]["Obligation"]:
        raise FieldIntelligenceError(
            "OPERATION_CONFLICT", "reasoning episode already exists"
        )
    raw_assemblies = request.get("assemblies", [])
    if (
        isinstance(raw_assemblies, (str, bytes))
        or not isinstance(raw_assemblies, Sequence)
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE", "reasoning assemblies are invalid"
        )
    assemblies: list[dict[str, Any]] = []
    hierarchy_ref: dict[str, Any] | None = None
    for raw_assembly in raw_assemblies:
        if not isinstance(raw_assembly, Mapping):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning assembly must be a mapping",
            )
        _interface_ref, assembly_ref = _packet_publish_assembly(
            state,
            raw_assembly,
            dependencies=resolved_dependencies,
            support_roots=support_roots,
        )
        assemblies.append(assembly_ref)
        if request.get("hierarchy") is not None:
            if len(raw_assemblies) != 1:
                raise FieldIntelligenceError(
                    "INVALID_REASONING_EPISODE",
                    "a reasoning hierarchy requires exactly one owning assembly",
                )
            hierarchy_ref = _packet_publish_hierarchy(
                state,
                cast(Mapping[str, Any], request["hierarchy"]),
                assembly_ref=assembly_ref,
                support_roots=support_roots,
            )
    hierarchy_value = None
    if hierarchy_ref is not None:
        _hierarchy_reference, hierarchy_record = _semantic_reference(
            state,
            hierarchy_ref,
            expected_kind="Value",
            require_current=True,
        )
        hierarchy_value = _regional_plain(
            dict(hierarchy_record["payload"]),
            "reasoning hierarchy value",
        )
    raw_program = request.get("program")
    if raw_program is not None and not isinstance(raw_program, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE", "reasoning program must be a mapping"
        )
    direct_request = (
        _packet_direct_request(request["request"])
        if request.get("request") is not None
        else None
    )
    if direct_request is not None:
        items: list[dict[str, Any]] = _packet_validate_work_program(
            [
                {
                    "dependencies": [],
                    "invocation": {
                        "arguments": direct_request,
                        "expected_return": {"status": ["halted"]},
                        "kernel": REGIONAL_KERNEL_NAME,
                        "state": None,
                    },
                    "item_id": "request",
                    "kind": "semantic",
                    "priority": 1_000_000,
                    "scope": {"episode_id": episode_id},
                }
            ],
            allocation=allocation,
        )
        selection = {"method": "baseline", "selector": None}
        stopping = _packet_stopping_contract({})
    else:
        if raw_program is None and request.get("program_ref") is None:
            items = []
            selection = {"method": "baseline", "selector": None}
            stopping = _packet_stopping_contract({})
        else:
            items, selection, stopping = _packet_work_program(
                state,
                allocation=allocation,
                hierarchy=hierarchy_value,
                provided=cast(Mapping[str, Any] | None, raw_program),
                program_ref=(
                    None
                    if request.get("program_ref") is None
                    else cast(Mapping[str, Any], request["program_ref"])
                ),
            )
    raw_cues = request.get("cues", [])
    if (
        isinstance(raw_cues, (str, bytes))
        or not isinstance(raw_cues, Sequence)
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE", "reasoning cues are invalid"
        )
    cue_items: list[dict[str, Any]] = []
    cue_refs: list[dict[str, Any]] = []
    if raw_cues:
        generated, cue_refs = _packet_prepare_cues(
            state,
            raw_cues,
            hierarchy=hierarchy_value,
            assembly_ref=assemblies[0] if assemblies else None,
            allocation=allocation,
            support_roots=support_roots,
        )
        cue_items = _packet_validate_work_program(
            generated, allocation=allocation, hierarchy=hierarchy_value
        )
    if len({item["item_id"] for item in [*items, *cue_items]}) != len(
        items
    ) + len(cue_items):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning work item identities are duplicated",
        )
    if len(items) + len(cue_items) > max(
        1, int(allocation["frontier_size"])
    ):
        raise FieldIntelligenceError(
            "WORK_CAPACITY",
            "reasoning work frontier exceeds its root allowance",
        )
    items = [*items, *cue_items]
    for index, item in enumerate(items):
        item["ready_sequence"] = index
    content_sha256 = sha256_value(
        {
            "episode_id": episode_id,
            "items": [
                _regional_plain(dict(item), "reasoning program item")
                for item in items
            ],
            "question": request["question"],
        }
    )
    payload = _packet_episode_payload(
        allocation=allocation,
        enforced=enforced,
        assemblies=assemblies,
        content_sha256=content_sha256,
        dependencies=resolved_dependencies,
        episode_id=episode_id,
        hierarchy=hierarchy_ref,
        items=items,
        question=request["question"],
        return_binding=return_binding,
        scope=request.get("scope", {"episode_id": episode_id}),
        stopping=stopping,
        support_roots=support_roots,
    )
    payload["assistance"] = assistance
    payload["scheduler"]["method"] = selection["method"]
    payload["scheduler"]["selector"] = selection["selector"]
    obligation = _semantic_append_record(
        state,
        record_id=obligation_id,
        kind="Obligation",
        payload=payload,
        epistemic_kind="proposed",
        dependencies=(
            *resolved_dependencies,
            *assemblies,
            *([] if hierarchy_ref is None else [hierarchy_ref]),
            *cue_refs,
        ),
        support_roots=cast(Any, support_roots),
    )
    _semantic_reindex_record(state, obligation)
    episode_record = _semantic_current_record(
        state, "Obligation", obligation_id
    )
    payload, emitted, _terminal, notes = _packet_transition(
        state, episode_record, payload
    )
    updated = _packet_update_episode(
        state,
        episode_record,
        payload,
        dependencies=(
            *assemblies,
            *([] if hierarchy_ref is None else [hierarchy_ref]),
            *cue_refs,
        ),
        terminal=payload["phase"] == "terminal",
    )
    if payload["phase"] == "terminal":
        status = _packet_episode_status(payload)
    else:
        status = "waiting"
    return _semantic_result(
        "begin-reasoning",
        status,
        episode=updated,
        invocation=emitted,
        phase=payload["phase"],
        steps=notes,
        work_items=[
            {
                "dependencies": list(item["dependencies"]),
                "item_id": item["item_id"],
                "kind": item["kind"],
                "status": item["status"],
            }
            for item in payload["work_items"]
        ],
        limitation=payload["limitation"],
    ), 2 if emitted is not None else 1


def _semantic_advance_reasoning(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request, required=("episode_id",), optional=("expected_return",)
    )
    episode_id = _identifier(request["episode_id"], "reasoning episode")
    expected = request.get("expected_return")
    if expected is not None and not isinstance(expected, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning expected return must be a mapping",
        )
    obligation = _packet_reasoning_episode(state, episode_id)
    payload = _regional_plain(
        dict(obligation["payload"]), "reasoning episode payload"
    )
    if payload["phase"] == "terminal":
        return _semantic_result(
            "advance-reasoning",
            _packet_episode_status(payload),
            episode=obligation,
            invocation=None,
            phase="terminal",
            steps=[],
            results=payload["results"],
            limitation=payload["limitation"],
        ), 1
    payload, emitted, terminal, notes = _packet_transition(
        state,
        obligation,
        payload,
        external_return=cast(Mapping[str, Any] | None, expected),
    )
    updated = _packet_update_episode(
        state,
        obligation,
        payload,
        dependencies=(
            *payload["assemblies"],
            *([] if payload["hierarchy"] is None else [payload["hierarchy"]]),
        ),
        terminal=terminal,
    )
    return _semantic_result(
        "advance-reasoning",
        "waiting" if not terminal else _packet_episode_status(payload),
        episode=updated,
        invocation=emitted,
        phase=payload["phase"],
        steps=notes,
        work_items=[
            {
                "dependencies": list(item["dependencies"]),
                "item_id": item["item_id"],
                "kind": item["kind"],
                "status": item["status"],
            }
            for item in payload["work_items"]
        ],
        consumed_returns=payload["consumed_returns"],
        limitation=payload["limitation"],
    ), 2 if emitted is not None else 1


def _semantic_admit_reasoning_input(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request, required=("episode_id", "inputs"), optional=("source",)
    )
    episode_id = _identifier(request["episode_id"], "reasoning episode")
    raw_inputs = request["inputs"]
    if (
        isinstance(raw_inputs, (str, bytes))
        or not isinstance(raw_inputs, Sequence)
        or not raw_inputs
        or len(raw_inputs) > SEMANTIC_MAX_OBSERVATIONS
    ):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning inputs exceed their bounded sequence",
        )
    source = _identifier(
        request.get("source", "external"), "reasoning input source"
    )
    obligation = _packet_reasoning_episode(state, episode_id)
    payload = _regional_plain(
        dict(obligation["payload"]), "reasoning episode payload"
    )
    if payload["phase"] == "terminal":
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "a terminal reasoning episode accepts no further input",
        )
    admitted: list[dict[str, Any]] = []
    for raw in raw_inputs:
        if (
            not isinstance(raw, Mapping)
            or set(raw)
            - {"input_id", "payload", "reference", "source_revision_id", "span"}
            or set(raw) & {"input_id", "payload", "reference"} == set()
        ):
            raise FieldIntelligenceError(
                "INVALID_REASONING_EPISODE",
                "reasoning input row is invalid",
            )
        input_id = _identifier(raw.get("input_id"), "reasoning input")
        declared = {
            key: raw[key]
            for key in ("source_revision_id", "span")
            if key in raw
        }
        source_binding = (
            _packet_source_binding(declared) if declared else None
        )
        if any(row["input_id"] == input_id for row in payload["inputs"]):
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT", "reasoning input already exists"
            )
        if len(payload["inputs"]) >= SEMANTIC_MAX_OBSERVATIONS:
            raise FieldIntelligenceError(
                "WORK_CAPACITY", "reasoning input capacity is exhausted"
            )
        reference = raw.get("reference")
        if reference is not None:
            if not isinstance(reference, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_REASONING_EPISODE",
                    "reasoning input reference is mistyped",
                )
            resolved, _record = _semantic_reference(
                state, reference, require_current=True
            )
            admitted.append(
                {
                    "input_id": input_id,
                    "reference": resolved.as_dict(),
                    "source": source,
                    "source_binding": source_binding,
                }
            )
            continue
        event_ref = _semantic_append_record(
            state,
            record_id=f"event:reasoning-input:{episode_id}:{input_id}",
            kind="Event",
            payload={
                "input_id": input_id,
                "payload": _regional_plain(
                    raw.get("payload"), "reasoning input payload"
                ),
                "source": source,
                "source_binding": source_binding,
            },
            epistemic_kind="observed",
            dependencies=(semantic_record_ref(obligation).as_dict(),),
            support_roots=obligation["support_roots"],
            valid_time={
                "start": float(state["time"]["now"]),
                "end": float(state["time"]["now"]),
            },
        )
        _semantic_reindex_record(state, event_ref)
        admitted.append(
            {
                "input_id": input_id,
                "reference": event_ref,
                "source": source,
                "source_binding": source_binding,
            }
        )
    payload["inputs"] = [*payload["inputs"], *admitted]
    updated = _packet_update_episode(
        state,
        obligation,
        payload,
        dependencies=tuple(row["reference"] for row in admitted),
    )
    return _semantic_result(
        "admit-reasoning-input",
        "supported",
        admitted=admitted,
        episode=updated,
        phase=payload["phase"],
        pending_inputs=len(payload["inputs"]),
    ), 2


def _semantic_finish_reasoning(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request, required=("episode_id",), optional=("expected_return",)
    )
    episode_id = _identifier(request["episode_id"], "reasoning episode")
    obligation = _packet_reasoning_episode(state, episode_id)
    payload = _regional_plain(
        dict(obligation["payload"]), "reasoning episode payload"
    )
    expected = request.get("expected_return")
    if expected is not None and not isinstance(expected, Mapping):
        raise FieldIntelligenceError(
            "INVALID_REASONING_EPISODE",
            "reasoning expected return must be a mapping",
        )
    if payload["phase"] != "terminal" and isinstance(
        payload["active"], Mapping
    ):
        binding = str(payload["active"]["return_binding"])
        returned = state["invocation_returns"].get(binding)
        payload, emitted, terminal, _notes = _packet_transition(
            state,
            obligation,
            payload,
            external_return=cast(Mapping[str, Any] | None, expected),
        )
        if emitted is not None:
            updated = _packet_update_episode(
                state, obligation, payload
            )
            return _semantic_result(
                "finish-reasoning",
                "waiting",
                episode=updated,
                invocation=emitted,
                phase=payload["phase"],
                limitations=["resident-child-result-unavailable"],
            ), 1
        if not isinstance(returned, Mapping) and not isinstance(
            expected, Mapping
        ):
            return _semantic_result(
                "finish-reasoning",
                "waiting",
                episode=obligation,
                limitations=["resident-child-result-unavailable"],
            ), 1
    payload, _emitted, _terminal, _notes = _packet_transition(
        state, obligation, payload
    )
    for item in payload["work_items"]:
        if item["status"] in {"deferred", "ready", "reserved"}:
            item["status"] = "limited"
            item["result"] = {
                "status": "missing-evidence",
                "reason": "dispatch-stopped-by-finish",
            }
    completed = [
        item
        for item in payload["work_items"]
        if item["status"] in {"completed", "reused"}
    ]
    child_result: Any = None
    if len(completed) == 1 and isinstance(
        completed[0]["result"], Mapping
    ) and isinstance(completed[0]["result"].get("result"), Mapping):
        child_result = completed[0]["result"]["result"]
    status = (
        _packet_item_status(completed[0])
        if len(completed) == 1
        else _packet_episode_status(payload)
    )
    if child_result is None:
        child_result = {
            "schema": "cassifi.packet-reasoning-conclusion.v1",
            "episode_id": episode_id,
            "limitation": payload["limitation"],
            "results": payload["results"],
            "status": status,
            "work_items": [
                {"item_id": item["item_id"], "status": item["status"]}
                for item in payload["work_items"]
            ],
        }
    terminal_payload = {
        **payload,
        "phase": "terminal",
        "active": None,
        "limitation": payload["limitation"],
        "results": payload["results"],
    }
    event = _semantic_append_record(
        state,
        record_id=f"event:reasoning:{episode_id}",
        kind="Event",
        payload={
            "child_state_sha256": (
                completed[0]["result"].get("state_sha256")
                if len(completed) == 1
                else None
            ),
            "episode_id": episode_id,
            "result": _regional_plain(child_result, "reasoning child result"),
            "task_sha256": (
                sha256_value(completed[0]["result"]["task"])
                if len(completed) == 1
                and isinstance(completed[0]["result"], Mapping)
                and isinstance(completed[0]["result"].get("task"), Mapping)
                else None
            ),
        },
        epistemic_kind="observed",
        dependencies=(semantic_record_ref(obligation).as_dict(),),
        support_roots=obligation["support_roots"],
        valid_time={
            "start": float(state["time"]["now"]),
            "end": float(state["time"]["now"]),
        },
    )
    assessment = _semantic_append_record(
        state,
        record_id=f"assessment:reasoning:{episode_id}",
        kind="Assessment",
        payload={
            "episode": semantic_record_ref(obligation).as_dict(),
            "event": event,
            "limitation": terminal_payload["limitation"],
            "purpose": "reasoning-result",
            "result": _regional_plain(
                child_result, "reasoning assessed result"
            ),
            "status": status,
            "work_items": terminal_payload["results"],
        },
        status="assessed",
        epistemic_kind="derived",
        dependencies=(semantic_record_ref(obligation).as_dict(), event),
        support_roots=obligation["support_roots"],
    )
    resolved = _semantic_append_record(
        state,
        record_id=obligation["id"],
        kind="Obligation",
        payload={
            **terminal_payload,
            "assessment": assessment,
            "state": "resolved" if status == "supported" else "blocked",
        },
        status="assessed",
        epistemic_kind="derived",
        dependencies=(assessment,),
        support_roots=obligation["support_roots"],
    )
    binding = str(payload["return_binding"])
    if binding in state["invocation_returns"]:
        del state["invocation_returns"][binding]
    _semantic_reindex_record(state, event)
    _semantic_reindex_record(state, assessment)
    _semantic_reindex_record(state, resolved)
    return _semantic_result(
        "finish-reasoning",
        status,
        assessment=assessment,
        episode=resolved,
        event=event,
        limitation=terminal_payload["limitation"],
        result=child_result,
        work_items=[
            {
                "item_id": item["item_id"],
                "kind": item["kind"],
                "status": item["status"],
            }
            for item in terminal_payload["work_items"]
        ],
    ), 3


def _semantic_start_development(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=(
            "allocation",
            "assessment",
            "available_information",
            "capabilities",
            "capability_target",
            "diagnosis",
            "episode_id",
            "remit",
            "stopping_condition",
            "write_classes",
        ),
        optional=("eligible_skills", "executed_work", "support_roots"),
    )
    episode_id = _identifier(request["episode_id"], "development episode")
    diagnosis = _identifier(
        request["diagnosis"], "development diagnosis"
    )
    eligible = request.get("eligible_skills", list(_DEVELOPMENT_SKILLS))
    if (
        not isinstance(eligible, list)
        or not eligible
        or any(skill not in _DEVELOPMENT_SKILLS for skill in eligible)
    ):
        raise FieldIntelligenceError(
            "INVALID_DEVELOPMENT", "eligible development skills are invalid"
        )
    selected = _DEVELOPMENT_DIAGNOSIS_SKILL.get(diagnosis)
    if selected not in eligible:
        selected = sorted(set(eligible))[0]
    for name in (
        "assessment",
        "available_information",
        "capabilities",
        "capability_target",
        "remit",
        "stopping_condition",
    ):
        if not isinstance(request[name], Mapping):
            raise FieldIntelligenceError(
                "INVALID_DEVELOPMENT",
                f"development {name} must be a mapping",
            )
    if (
        not isinstance(request["write_classes"], list)
        or any(
            not isinstance(item, str) or not item
            for item in request["write_classes"]
        )
    ):
        raise FieldIntelligenceError(
            "INVALID_DEVELOPMENT",
            "development write classes must be bounded names",
        )
    allocation = _semantic_development_allocation(
        request["allocation"], state
    )
    specification = {
        name: dict(cast(Mapping[str, Any], request[name]))
        for name in (
            "assessment",
            "available_information",
            "capabilities",
            "capability_target",
            "remit",
            "stopping_condition",
        )
    }
    information = cast(Mapping[str, Any], specification["available_information"])
    execution_plan = _semantic_development_execution_plan(
        state,
        information,
        allocation,
        request.get("executed_work", _ABSENT),
    )
    target = cast(Mapping[str, Any], specification["capability_target"])
    raw_family = target.get("task_family", information.get("task_family"))
    if not isinstance(raw_family, str) or not raw_family:
        parameter = target.get("parameter", information.get("parameter"))
        raw_family = (
            parameter.split("-", 1)[0]
            if isinstance(parameter, str) and parameter
            else "general-development"
        )
    applicability = {"task_family": _identifier(raw_family, "development applicability")}
    return_binding = f"development:{episode_id}:result"
    method_id = f"development-method:{episode_id}"
    program = semantic_program_payload(
        program_kind="procedure",
        body={
            "allocation": allocation,
            "diagnosis": diagnosis,
            "episode_id": episode_id,
            "execution_plan": execution_plan,
            "selected_skill": selected,
            "specification": specification,
        },
        writes=sorted(set(cast(list[str], request["write_classes"]))),
        max_work=allocation["work"],
        applicability=applicability,
    )
    method = _semantic_append_record(
        state,
        record_id=method_id,
        kind="Program",
        payload={
            "applicability": applicability,
            "program": program,
            "program_role": "development-method",
            "selected_skill": selected,
            "selector": applicability["task_family"],
        },
        status="candidate",
        epistemic_kind="proposed",
        support_roots=cast(Any, request.get("support_roots", [])),
        applicability=applicability,
    )
    obligation_id = f"obligation:development:{episode_id}"
    if obligation_id in state["current"]["Obligation"]:
        raise FieldIntelligenceError(
            "OPERATION_CONFLICT", "development episode already exists"
        )
    obligation = _semantic_append_record(
        state,
        record_id=obligation_id,
        kind="Obligation",
        payload={
            "allocation": allocation,
            "applicability": applicability,
            "diagnosis": diagnosis,
            "episode_id": episode_id,
            "execution_plan": execution_plan,
            "method": method,
            "return_binding": return_binding,
            "selected_skill": selected,
            "specification": specification,
            "state": "in-progress",
        },
        epistemic_kind="proposed",
        dependencies=(method,),
        support_roots=cast(Any, request.get("support_roots", [])),
    )
    _semantic_reindex_record(state, method)
    _semantic_reindex_record(state, obligation)
    return _semantic_result(
        "start-development",
        "supported",
        episode=obligation,
        method=method,
        selected_skill=selected,
        invocation={
            "arguments": {
                "episode_id": episode_id,
                "operation": "run-development",
            },
            "call_id": f"development:{episode_id}",
            "dependencies": [method, obligation],
            "kernel": REGIONAL_KERNEL_NAME,
            "return_binding": return_binding,
        },
    ), 2


def _semantic_run_development(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(request, required=("episode_id",))
    episode_id = _identifier(request["episode_id"], "development episode")
    obligation = _semantic_current_record(
        state, "Obligation", f"obligation:development:{episode_id}"
    )
    payload = obligation["payload"]
    if payload.get("state") != "in-progress":
        raise FieldIntelligenceError(
            "INVALID_DEVELOPMENT", "development episode is not active"
        )
    selected = payload["selected_skill"]
    specification = payload["specification"]
    information = specification["available_information"]
    assessment = specification["assessment"]
    execution_plan = payload.get("execution_plan", {"kind": "none"})
    executed_work = _semantic_execute_development_work(state, execution_plan)
    unresolved = sorted(
        record_id
        for record_id, raw_ref in state["current"]["Obligation"].items()
        if resolve_semantic_record(state["records"], raw_ref)["payload"].get(
            "state"
        )
        in {"blocked", "in-progress", "pending"}
    )
    limitations: list[str] = []
    findings: dict[str, Any] = {
        "active_obligations": unresolved[
            : state["bounds"]["max_observations"]
        ],
        "family_counts": {
            kind: len(state["current"][kind])
            for kind in SEMANTIC_RECORD_KINDS
        },
    }
    if selected == "study" and not information.get("source_revision_ids"):
        limitations.append("authorized-study-source-unavailable")
    elif selected == "investigate":
        findings["separating_alternatives"] = assessment.get(
            "alternatives", []
        )
    elif selected == "practice":
        findings["attempts"] = assessment.get("attempts", [])
        if not findings["attempts"]:
            limitations.append("prospective-practice-attempt-unavailable")
    elif selected == "reflect":
        findings["predicted"] = assessment.get("predicted")
        if executed_work is None:
            limitations.append("executed-outcome-unavailable")
        else:
            findings["actual"] = executed_work["outcome"]
            findings["executed_work"] = executed_work
        if "predicted" not in assessment:
            limitations.append("prediction-outcome-pair-unavailable")
    elif selected == "teach":
        findings["recipient_observation"] = assessment.get(
            "recipient_observation"
        )
        if findings["recipient_observation"] is None:
            limitations.append("recipient-observation-unavailable")
    elif selected == "consolidate":
        findings["repeated_families"] = sorted(
            kind
            for kind, count in findings["family_counts"].items()
            if count > 1
        )
    elif selected == "meditate":
        findings["information_boundary"] = sorted(information)
    work = min(
        payload["allocation"]["work"],
        max(
            1,
            len(unresolved)
            + len(findings["family_counts"])
            + (0 if executed_work is None else int(executed_work["work_units"])),
        ),
    )
    return _semantic_result(
        "run-development",
        "support-gap" if limitations else "supported",
        episode=semantic_record_ref(obligation).as_dict(),
        executed_work=executed_work,
        findings=findings,
        limitations=limitations,
        measured_work=work,
        selected_skill=selected,
    ), work


def _semantic_finish_development(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(request, required=("episode_id",))
    episode_id = _identifier(request["episode_id"], "development episode")
    obligation_id = f"obligation:development:{episode_id}"
    obligation = _semantic_current_record(
        state, "Obligation", obligation_id
    )
    return_binding = obligation["payload"].get("return_binding")
    returned = state["invocation_returns"].get(return_binding)
    if not isinstance(returned, Mapping):
        return _semantic_result(
            "finish-development",
            "waiting",
            episode=semantic_record_ref(obligation).as_dict(),
            limitations=["resident-development-result-unavailable"],
        ), 1
    child_result = returned.get("result")
    raw_executed = (
        child_result.get("executed_work")
        if isinstance(child_result, Mapping)
        else None
    )
    executed = (
        raw_executed
        if isinstance(raw_executed, Mapping)
        and raw_executed.get("kind") not in {None, "none"}
        and "outcome" in raw_executed
        and isinstance(raw_executed.get("work_units"), int)
        and raw_executed["work_units"] > 0
        else None
    )
    base_success = (
        isinstance(child_result, Mapping)
        and child_result.get("operation") == "run-development"
        and child_result.get("status") in {"supported", "support-gap"}
    )
    declared = obligation["payload"]["specification"]["assessment"]
    observed_outcome = None if executed is None else executed["outcome"]
    successful = bool(
        base_success
        and executed is not None
        and (
            "predicted" not in declared
            or declared["predicted"] == observed_outcome
        )
    )
    provenance = "executed" if executed is not None else "caller-supplied"
    event_dependencies: list[dict[str, Any]] = [
        semantic_record_ref(obligation).as_dict()
    ]
    if executed is not None:
        for raw_reference in executed.get("references", []):
            if not isinstance(raw_reference, Mapping):
                raise FieldIntelligenceError(
                    "INVALID_DEVELOPMENT",
                    "executed development references must be typed",
                )
            reference, _record = _semantic_reference(
                state, raw_reference, expected_kind="Binding", require_current=True
            )
            event_dependencies.append(reference.as_dict())
    event_payload: dict[str, Any] = {
        "child_state_sha256": returned.get("state_sha256"),
        "episode_id": episode_id,
        "provenance": provenance,
        "result": _regional_plain(
            child_result, "development child result"
        ),
        "task_sha256": returned.get("task_sha256"),
    }
    if executed is not None:
        event_payload["observed_outcome"] = observed_outcome
        event_payload["executed_work"] = _regional_plain(
            dict(executed), "development executed work"
        )
    event = _semantic_append_record(
        state,
        record_id=f"event:development:{episode_id}",
        kind="Event",
        payload=event_payload,
        epistemic_kind="observed" if executed is not None else "asserted",
        dependencies=event_dependencies,
        support_roots=obligation["support_roots"],
        valid_time={
            "start": float(state["time"]["now"]),
            "end": float(state["time"]["now"]),
        },
    )
    method = obligation["payload"]["method"]
    if successful:
        method_record = _semantic_current_record(
            state, "Program", SemanticRef.from_dict(method).id
        )
        method = _semantic_append_record(
            state,
            record_id=method_record["id"],
            kind="Program",
            payload={
                **method_record["payload"],
                "provenance": "executed",
            },
            status="active",
            epistemic_kind="derived",
            dependencies=(event,),
            support_roots=method_record["support_roots"],
            applicability=method_record["applicability"],
        )
        _semantic_reindex_record(state, method)
    assessment_payload: dict[str, Any] = {
        "allocation": obligation["payload"]["allocation"],
        "episode": semantic_record_ref(obligation).as_dict(),
        "event": event,
        "method": method,
        "provenance": provenance,
        "purpose": "self-development",
        "result": _regional_plain(
            child_result, "development assessed result"
        ),
        "selected_skill": obligation["payload"]["selected_skill"],
        "successful": successful,
        "verified_improvement": successful,
    }
    if executed is None:
        assessment_payload["declared_assessment"] = _regional_plain(
            declared, "caller development assessment"
        )
    else:
        assessment_payload["observed_outcome"] = observed_outcome
    assessment = _semantic_append_record(
        state,
        record_id=f"assessment:development:{episode_id}",
        kind="Assessment",
        payload=assessment_payload,
        status="assessed",
        epistemic_kind="derived",
        dependencies=(
            semantic_record_ref(obligation).as_dict(),
            method,
            event,
        ),
        support_roots=obligation["support_roots"],
    )
    resolved = _semantic_append_record(
        state,
        record_id=obligation_id,
        kind="Obligation",
        payload={
            **obligation["payload"],
            "assessment": assessment,
            "method": method,
            "state": "resolved" if successful else "blocked",
        },
        epistemic_kind="derived",
        dependencies=(assessment,),
        support_roots=obligation["support_roots"],
    )
    del state["invocation_returns"][str(return_binding)]
    _semantic_reindex_record(state, event)
    _semantic_reindex_record(state, assessment)
    _semantic_reindex_record(state, resolved)
    return _semantic_result(
        "finish-development",
        "supported" if base_success else "support-gap",
        assessment=assessment,
        episode=resolved,
        event=event,
        observed_outcome=observed_outcome,
        provenance=provenance,
        result=child_result,
        verified_improvement=successful,
    ), 3


def _semantic_reuse_development_method(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("task_family",),
        optional=("method_id", "parameter"),
    )
    task_family = _identifier(
        request["task_family"], "development reuse task family"
    )
    requested_id = request.get("method_id")
    if requested_id is not None:
        requested_id = _identifier(
            requested_id, "development reuse method identity"
        )
    candidates: list[dict[str, Any]] = []
    for raw_ref in state["current"]["Program"].values():
        record = resolve_semantic_record(state["records"], raw_ref, require_current=True)
        if (
            record["status"] != "active"
            or record["payload"].get("program_role") != "development-method"
        ):
            continue
        if requested_id is not None and record["id"] != requested_id:
            continue
        applicability = record.get("applicability", {})
        if (
            not isinstance(applicability, Mapping)
            or applicability.get("task_family") != task_family
        ):
            continue
        candidates.append(record)
    if not candidates:
        return _semantic_result(
            "reuse-development-method",
            "support-gap",
            applicability={"task_family": task_family},
            limitations=["no-acquired-method-for-applicability"],
            method=None,
            reused=False,
        ), 1
    selected = min(
        candidates,
        key=lambda record: (
            int(record["created_at"]),
            record["id"],
            int(record["content_version"]),
        ),
    )
    reference = semantic_record_ref(selected).as_dict()
    return _semantic_result(
        "reuse-development-method",
        "supported",
        applicability=dict(selected["applicability"]),
        method=reference,
        reused=True,
        selected_skill=selected["payload"].get("selected_skill"),
    ), 1

def _semantic_reopen_development(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=("allocation", "episode_id", "justification"),
    )
    episode_id = _identifier(request["episode_id"], "development episode")
    justification = request["justification"]
    allowed = {
        "changed-premise",
        "different-method",


        "justified-replication",
        "new-allocation",
        "new-evidence",
    }
    if (
        not isinstance(justification, Mapping)
        or justification.get("kind") not in allowed
        or not justification.get("detail")
    ):
        raise FieldIntelligenceError(
            "INVALID_DEVELOPMENT",
            "development reopening requires a material justification",
        )
    prior = _semantic_current_record(
        state, "Obligation", f"obligation:development:{episode_id}"
    )
    if prior["payload"].get("state") not in {"blocked", "resolved"}:
        raise FieldIntelligenceError(
            "INVALID_DEVELOPMENT",
            "only a completed development episode can be reopened",
        )
    allocation = _semantic_development_allocation(
        request["allocation"], state
    )
    reopened = _semantic_append_record(
        state,
        record_id=prior["id"],
        kind="Obligation",
        payload={
            **prior["payload"],
            "allocation": allocation,
            "justification": _regional_plain(
                dict(justification), "development reopening justification"
            ),
            "state": "in-progress",
        },
        epistemic_kind="proposed",
        dependencies=(semantic_record_ref(prior).as_dict(),),
        support_roots=prior["support_roots"],
    )
    _semantic_reindex_record(state, reopened)
    return _semantic_result(
        "reopen-development",
        "supported",
        episode=reopened,
        invocation={
            "arguments": {
                "episode_id": episode_id,
                "operation": "run-development",
            },
            "call_id": (
                f"development:{episode_id}:"
                f"{reopened['content_version']}"
            ),
            "dependencies": [
                prior["payload"]["method"],
                reopened,
            ],
            "kernel": REGIONAL_KERNEL_NAME,
            "return_binding": prior["payload"]["return_binding"],
        },
    ), 1


def _semantic_consolidate(
    state: dict[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(
        request,
        required=(
            "measured_cost",
            "questions",
            "reconstruction",
            "record_id",
            "references",
            "retention",
            "summary",
        ),
        optional=("support_roots",),
    )
    references = request["references"]
    if (
        not isinstance(references, list)
        or not references
        or not isinstance(request["summary"], Mapping)
        or not isinstance(request["measured_cost"], Mapping)
    ):
        raise FieldIntelligenceError(
            "INVALID_CONSOLIDATION", "consolidation request is invalid"
        )
    dependencies: list[dict[str, Any]] = []
    source_records: list[dict[str, Any]] = []
    seen_references: set[bytes] = set()
    for raw in references:
        if not isinstance(raw, Mapping):
            raise FieldIntelligenceError(
                "INVALID_CONSOLIDATION",
                "consolidation references must be typed",
            )
        reference, record = _semantic_reference(
            state, raw, require_current=True
        )
        key = canonical_json_bytes(reference.as_dict())
        if key in seen_references:
            continue
        seen_references.add(key)
        dependencies.append(reference.as_dict())
        source_records.append(record)
    retention = request["retention"]
    if not isinstance(retention, Mapping) or set(retention) != {
        "lost_details",
        "rare_exceptions",
        "rare_exceptions_preserved",
        "recoverable_details",
        "sufficient_summaries",
    }:
        raise FieldIntelligenceError(
            "INVALID_CONSOLIDATION",
            "consolidation retention declaration is invalid",
        )
    retention_lists: dict[str, list[str]] = {}
    for name in (
        "lost_details",
        "rare_exceptions",
        "recoverable_details",
        "sufficient_summaries",
    ):
        rows = retention[name]
        if (
            not isinstance(rows, list)
            or any(not isinstance(item, str) or not item for item in rows)
        ):
            raise FieldIntelligenceError(
                "INVALID_CONSOLIDATION",
                f"consolidation {name} are invalid",
            )
        retention_lists[name] = sorted(set(rows))
    if not isinstance(retention["rare_exceptions_preserved"], bool):
        raise FieldIntelligenceError(
            "INVALID_CONSOLIDATION",
            "rare-exception preservation flag must be boolean",
        )
    if (
        not retention["rare_exceptions_preserved"]
        or set(retention_lists["rare_exceptions"])
        & set(retention_lists["lost_details"])
    ):
        raise FieldIntelligenceError(
            "INVALID_CONSOLIDATION",
            "consolidation cannot erase a required rare exception",
        )
    questions = request["questions"]
    if not isinstance(questions, Mapping) or set(questions) != {
        "preserved",
        "unavailable",
    }:
        raise FieldIntelligenceError(
            "INVALID_CONSOLIDATION",
            "consolidation question declaration is invalid",
        )
    preserved_questions = questions["preserved"]
    unavailable_questions = questions["unavailable"]
    if (
        not isinstance(preserved_questions, list)
        or not isinstance(unavailable_questions, list)
        or any(
            not isinstance(item, str) or not item
            for item in [*preserved_questions, *unavailable_questions]
        )
        or set(preserved_questions) & set(unavailable_questions)
        or (
            retention_lists["lost_details"]
            and not unavailable_questions
        )
    ):
        raise FieldIntelligenceError(
            "INVALID_CONSOLIDATION",
            "consolidation preserved and unavailable questions are inconsistent",
        )
    reconstruction = request["reconstruction"]
    if not isinstance(reconstruction, Mapping) or set(reconstruction) != {
        "authorized_inputs",
        "contribution_partitions",
        "initialization_lineage",
        "strategy",
    }:
        raise FieldIntelligenceError(
            "INVALID_CONSOLIDATION",
            "consolidation reconstruction declaration is invalid",
        )
    strategy = reconstruction["strategy"]
    if strategy not in {
        "additive-partitions",
        "inseparable-invalidates",
        "nonlinear-recompute",
    }:
        raise FieldIntelligenceError(
            "INVALID_CONSOLIDATION",
            "consolidation reconstruction strategy is unsupported",
        )
    for name in (
        "authorized_inputs",
        "contribution_partitions",
        "initialization_lineage",
    ):
        if not isinstance(reconstruction[name], list):
            raise FieldIntelligenceError(
                "INVALID_CONSOLIDATION",
                f"consolidation reconstruction {name} must be a list",
            )
    if strategy == "additive-partitions" and not reconstruction[
        "contribution_partitions"
    ]:
        raise FieldIntelligenceError(
            "INVALID_CONSOLIDATION",
            "additive reconstruction requires removable partitions",
        )
    if strategy == "nonlinear-recompute" and (
        not reconstruction["authorized_inputs"]
        or not reconstruction["initialization_lineage"]
    ):
        raise FieldIntelligenceError(
            "INVALID_CONSOLIDATION",
            "nonlinear reconstruction requires inputs and initialization",
        )
    record_id = _identifier(
        request["record_id"], "consolidation identity"
    )
    support_union = sorted(
        {
            root
            for record in source_records
            for root in record["support_roots"]
        }
    )
    requested_roots = set(cast(list[Any], request.get("support_roots", [])))
    if not requested_roots.issubset(set(support_union)):
        raise FieldIntelligenceError(
            "INVALID_CONSOLIDATION",
            "consolidation cannot manufacture independent support roots",
        )
    lineage = [
        {
            "reference": reference,
            "support_roots": record["support_roots"],
        }
        for reference, record in zip(dependencies, source_records)
    ]
    normalized_summary = _regional_plain(
        request["summary"], "consolidation summary"
    )
    normalized_reconstruction = _regional_plain(
        dict(reconstruction), "consolidation reconstruction"
    )
    normalized_cost = _regional_plain(
        dict(request["measured_cost"]), "consolidation declared cost"
    )
    actual_cost = {
        "declared": normalized_cost,
        "input_records": len(dependencies),
        "output_bytes": len(canonical_json_bytes(normalized_summary)),
        "work": max(
            1,
            len(dependencies)
            + len(retention_lists["recoverable_details"])
            + len(retention_lists["sufficient_summaries"])
            + len(retention_lists["lost_details"]),
        ),
    }
    if actual_cost["work"] > state["bounds"]["max_work"]:
        return _semantic_result(
            "consolidate",
            "resource-exhausted",
            limitations=["consolidation-work-bound"],
            summary=None,
        ), 1
    program_body = {
        "lineage": lineage,
        "measured_cost": actual_cost,
        "questions": {
            "preserved": sorted(set(preserved_questions)),
            "unavailable": sorted(set(unavailable_questions)),
        },
        "reconstruction": normalized_reconstruction,
        "retention": {
            **retention_lists,
            "rare_exceptions_preserved": True,
        },
        "schema": "cassifi.semantic-consolidation-program.v1",
        "summary_sha256": sha256_value(normalized_summary),
    }
    program = semantic_program_payload(
        program_kind="consolidation",
        body=program_body,
        reads=[reference["id"] for reference in dependencies],
        writes=[record_id],
        max_work=actual_cost["work"],
    )
    prior = state["current"]["Value"].get(record_id)
    frontier = (
        []
        if prior is None
        else _semantic_invalidate(
            state, (prior,), reason="consolidation-revised"
        )
    )
    program_id = f"consolidation-program:{record_id}"
    prior_program = state["current"]["Program"].get(program_id)
    if prior_program is not None:
        frontier.extend(
            _semantic_invalidate(
                state,
                (prior_program,),
                reason="consolidation-program-revised",
            )
        )
    program_ref = _semantic_append_record(
        state,
        record_id=program_id,
        kind="Program",
        payload={
            "program": program,
            "program_role": "consolidation",
            "reconstruction_strategy": strategy,
            "semantic_loss": bool(retention_lists["lost_details"]),
        },
        epistemic_kind="derived",
        dependencies=dependencies,
        support_roots=support_union,
        derivation={
            "lifecycle_handler": "consolidate",
            "observation_identity_preserved": True,
        },
    )
    summary_ref = _semantic_append_record(
        state,
        record_id=record_id,
        kind="Value",
        payload={
            "consolidation_program": program_ref,
            "contribution_lineage": lineage,
            "questions": program_body["questions"],
            "reconstruction": normalized_reconstruction,
            "retention": program_body["retention"],
            "semantic_loss": bool(retention_lists["lost_details"]),
            "summary": normalized_summary,
            "support_root_count": len(support_union),
        },
        epistemic_kind="derived",
        dependencies=(program_ref, *dependencies),
        support_roots=support_union,
        derivation={
            "criterion": "explicit-lineage-and-recoverability-consolidation",
            "replay_adds_support": False,
        },
    )
    _semantic_reindex_record(state, program_ref)
    _semantic_reindex_record(state, summary_ref)
    return _semantic_result(
        "consolidate",
        "supported",
        consolidation_program=program_ref,
        invalidation_frontier=frontier,
        measured_cost=actual_cost,
        questions=program_body["questions"],
        reconstruction_strategy=strategy,
        retained_references=dependencies,
        semantic_loss=bool(retention_lists["lost_details"]),
        summary=summary_ref,
        support_root_count=len(support_union),
    ), max(1, int(actual_cost["work"]) + len(frontier))


def _semantic_inspect(
    state: Mapping[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], int]:
    _semantic_keys(request)
    family_counts = {
        kind: len(state["current"][kind]) for kind in SEMANTIC_RECORD_KINDS
    }
    active_counts = {
        kind: sum(
            1
            for raw_ref in state["current"][kind].values()
            if resolve_semantic_record(state["records"], raw_ref)["status"]
            == "active"
        )
        for kind in SEMANTIC_RECORD_KINDS
    }
    return _semantic_result(
        "inspect",
        "supported",
        active_counts=active_counts,
        family_counts=family_counts,
        logical_time=state["time"]["now"],
        operation_count=len(state["indexes"]["operations"]),
        pending_proposal=state["continuation"]["proposal"],
        timeline_length=len(state["time"]["timeline"]),
        work=state["ledger"]["work"],
    ), 1

def _semantic_dispatch(
    state: dict[str, Any],
    request: Mapping[str, Any],
) -> tuple[dict[str, Any], int]:
    operation = request["operation"]
    if operation == "learn":
        learning_kind = _identifier(
            request.get("learning_kind"), "semantic learning kind"
        )
        delegated_operations = {
            "construction": "learn-construction",
            "hybrid": "learn-hybrid",
            "mechanism": "learn-mechanism",
            "predictive-state": "learn-predictive-state",
            "procedure": "learn-procedure",
            "parameters": "learn-parameters",
            "representation": "learn-representation",
        }
        delegated_operation = delegated_operations.get(learning_kind)
        if delegated_operation is None:
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_OPERATION",
                "semantic learning kind is unsupported",
            )
        delegated_request = {
            key: value
            for key, value in request.items()
            if key != "learning_kind"
        }
        delegated_request["operation"] = delegated_operation
        result, work = _semantic_dispatch(state, delegated_request)
        return {
            **result,
            "learning_kind": learning_kind,
            "operation": "learn",
        }, work
    if operation == "begin-reasoning":
        return _semantic_begin_reasoning(state, request)
    if operation == "advance-reasoning":
        return _semantic_advance_reasoning(state, request)
    if operation == "admit-reasoning-input":
        return _semantic_admit_reasoning_input(state, request)
    if operation == "finish-reasoning":
        return _semantic_finish_reasoning(state, request)
    if operation == "advance-invalidation":
        _semantic_keys(request, optional=("quanta",))
        budget = _regional_integer(
            request.get("quanta", 64),
            "invalidation quantum",
            minimum=1,
            maximum=1_000_000,
        )
        summary = _semantic_advance_invalidation(state, quanta=budget)
        return _semantic_result(
            "advance-invalidation",
            "supported" if not summary["active"] else "waiting",
            active=summary["active"],
            causes=summary["causes"],
            checked_records=summary["checked_records"],
            frontier=summary["frontier"],
            limitation=(
                None
                if not summary["active"]
                else {
                    "kind": "invalidation-incomplete",
                    "pending_records": summary["pending_records"],
                }
            ),
            passes=summary["passes"],
            pending_records=summary["pending_records"],
            reason=summary["reason"],
            scans=summary["scans"],
        ), max(1, int(summary["scans"]))
    if operation == "start-development":
        return _semantic_start_development(state, request)
    if operation == "run-development":
        return _semantic_run_development(state, request)
    if operation == "reuse-development-method":
        return _semantic_reuse_development_method(state, request)
    if operation == "finish-development":
        return _semantic_finish_development(state, request)
    if operation == "reopen-development":
        return _semantic_reopen_development(state, request)
    if operation == "observe":
        return _semantic_observe(state, request)
    if operation in {"correct", "revise"}:
        if operation == "revise":
            request = {**dict(request), "operation": "correct"}
        return _semantic_correct(state, request)
    if operation == "query":
        return _semantic_query(state, request)
    if operation == "predict":
        return _semantic_predict(state, request)
    if operation == "assess-prediction":
        return _semantic_assess_prediction(state, request)
    if operation in {"learn-mechanism", "learn-hybrid"}:
        return _semantic_learn_mechanism(state, request)
    if operation == "learn-parameters":
        return _semantic_learn_parameters(state, request)
    if operation == "learn-predictive-state":
        return _semantic_learn_predictive_state(state, request)
    if operation == "learn-representation":
        return _semantic_learn_representation(state, request)
    if operation == "explain":
        return _semantic_explain(state, request)
    if operation == "learn-procedure":
        return _semantic_learn_procedure(state, request)
    if operation == "learn-construction":
        return _semantic_learn_construction(state, request)
    if operation == "interpret":
        return _semantic_interpret(state, request)
    if operation == "express":
        return _semantic_express(state, request)
    if operation == "update-perspective":
        return _semantic_update_perspective(state, request)
    if operation == "plan":
        return _semantic_plan(state, request)
    if operation == "inquire":
        return _semantic_inquire(state, request)
    if operation == "authorize-action":
        return _semantic_authorize_action(state, request)
    if operation == "dispatch-action":
        return _semantic_dispatch_action(state, request)
    if operation == "track-action":
        return _semantic_track_action(state, request)
    if operation == "cancel-action":
        return _semantic_cancel_action(state, request)
    if operation == "acknowledgment":
        return _semantic_acknowledge(state, request)
    if operation == "register":
        return _semantic_register(state, request)
    if operation == "mechanism-step":
        return _semantic_mechanism_step(state, request)
    if operation == "advance-time":
        return _semantic_advance_time(state, request)
    if operation == "revoke":
        return _semantic_revoke(state, request)
    if operation == "migrate":
        return _semantic_migrate(state, request)
    if operation == "consolidate":
        return _semantic_consolidate(state, request)
    if operation == "inspect":
        return _semantic_inspect(state, request)
    if operation == "wait":
        _semantic_keys(request)
        return _semantic_result(
            "wait", "waiting", reason="external-observation-required"
        ), 1
    raise FieldIntelligenceError(
        "INVALID_SEMANTIC_OPERATION",
        f"unsupported semantic operation: {operation}",
    )


def semantic_cognition_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance the persistent semantic graph through one owner-visible request."""

    bound = _regional_integer(
        quantum,
        "semantic cognition quantum",
        minimum=1,
        maximum=REGIONAL_KERNEL_MAX_WORK,
    )
    current = _canonical_semantic_state(cast(Mapping[str, Any], state))
    continuation = current["continuation"]
    supplied = _regional_plain(
        dict(arguments), "semantic operation arguments"
    )
    if not isinstance(supplied, dict):
        raise FieldIntelligenceError(
            "INVALID_SEMANTIC_OPERATION",
            "semantic operation arguments must be a mapping",
        )
    if continuation["request"] is None:
        if not supplied:
            current["status"] = "waiting"
            return KernelResult(
                state=current,
                status="blocked",
                work=1,
                output=current["last_result"],
            )
        if not isinstance(supplied.get("operation"), str):
            raise FieldIntelligenceError(
                "INVALID_SEMANTIC_OPERATION",
                "semantic request must name an operation",
            )
        request = json.loads(canonical_json_bytes(supplied))
        request_sha256 = sha256_value(request)
        operation_id = _identifier(
            request.get("operation_id", request_sha256),
            "semantic operation identity",
        )
        prior = current["indexes"]["operations"].get(operation_id)
        if prior is not None:
            if prior["request_sha256"] != request_sha256:
                raise FieldIntelligenceError(
                    "OPERATION_CONFLICT",
                    "semantic operation identity changed request content",
                )
            replay = {**dict(prior["result"]), "replayed": True}
            current["last_result"] = replay
            current["status"] = "waiting"
            return KernelResult(
                state=current,
                status="done",
                work=0,
                output=replay,
            )
        continuation.update(
            {
                "cursor": 0,
                "operation_id": operation_id,
                "partial": {},
                "request": request,
                "request_sha256": request_sha256,
            }
        )
    else:
        request = continuation["request"]
        request_sha256 = continuation["request_sha256"]
        operation_id = continuation["operation_id"]
        if supplied and sha256_value(supplied) != request_sha256:
            raise FieldIntelligenceError(
                "OPERATION_CONFLICT",
                "semantic continuation received different operation content",
            )
    current["status"] = "running"
    cursor = int(continuation["cursor"])
    required = continuation["partial"].get("required_work")
    if required is not None and cursor + bound < int(required):
        continuation["cursor"] = cursor + bound
        progress = _semantic_result(
            str(request["operation"]),
            "waiting",
            completed_work=continuation["cursor"],
            required_work=required,
        )
        current["last_result"] = progress
        return KernelResult(
            state=_canonical_semantic_state(current),
            status="yield",
            work=bound,
            output=progress,
        )
    working = _regional_plain(current, "semantic working state")
    result, work = _semantic_dispatch(working, request)
    work = max(1, int(work))
    if work > working["bounds"]["max_work"]:
        result = _semantic_result(
            str(request["operation"]),
            "resource-exhausted",
            limitations=["semantic-work-bound"],
            required_work=work,
        )
        working = _regional_plain(current, "semantic bounded state")
        work = int(working["bounds"]["max_work"])
    if cursor + bound < work:
        continuation["partial"] = {"required_work": work}
        continuation["cursor"] = cursor + bound
        progress = _semantic_result(
            str(request["operation"]),
            "waiting",
            completed_work=continuation["cursor"],
            required_work=work,
        )
        current["last_result"] = progress
        return KernelResult(
            state=_canonical_semantic_state(current),
            status="yield",
            work=bound,
            output=progress,
        )
    remaining_work = max(1, work - cursor)
    working["status"] = "waiting"
    working["ledger"]["transitions"] = (
        int(working["ledger"]["transitions"]) + 1
    )
    working["ledger"]["work"] = int(working["ledger"]["work"]) + work
    receipt = {
        "operation_id": operation_id,
        "request_sha256": request_sha256,
        "result_sha256": sha256_value(result),
        "transition": working["ledger"]["transitions"],
        "work": work,
    }
    if len(working["ledger"]["operation_receipts"]) >= working["bounds"][
        "max_operations"
    ]:
        raise FieldIntelligenceError(
            "WORK_CAPACITY", "semantic operation ledger is exhausted"
        )
    working["ledger"]["operation_receipts"].append(receipt)
    working["indexes"]["operations"][operation_id] = {
        **receipt,
        "result": result,
    }
    working["last_result"] = result
    proposal = working["continuation"]["proposal"]
    working["continuation"] = {
        "cursor": 0,
        "operation_id": None,
        "partial": {},
        "proposal": proposal,
        "request": None,
        "request_sha256": None,
    }
    canonical = _canonical_semantic_state(working)
    return KernelResult(
        state=canonical,
        status="done",
        work=min(bound, remaining_work),
        output=result,
    )


def semantic_cognition_kernel_factory() -> Any:
    return semantic_cognition_kernel


__all__ = [
    "ActionBranchCertificate",
    "ActionDecision",
    "ActionReadout",
    "COGNITION_REGIONAL_KERNEL_NAME",
    "COGNITION_REGIONAL_MAX_WORK",
    "COGNITION_REGIONAL_STATE_SCHEMA",
    "COGNITION_REGIONAL_RESULT_SCHEMA",
    "FieldCognition",
    "InquiryDecision",
    "InquiryOperation",
    "MECHANISM_STATE_SCHEMA",
    "MECHANISM_STEP_KERNEL",
    "MECHANISM_STEP_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_STATE_SCHEMA",
    "REGIONAL_RESULT_SCHEMA",
    "SEMANTIC_RESULT_SCHEMA",
    "SEMANTIC_STATE_SCHEMA",
    "AssessmentRecord",
    "LanguageConstruction",
    "PlanRecord",
    "PredictionRecord",
    "Survivor",
    "adjoint_readout_certificate",
    "choose_inquiry",
    "consequence_partition",
    "directed_macro_margin",
    "model_uncertainty_bound",
    "prequential_radius",
    "mechanism_step_kernel",
    "mechanism_step_kernel_factory",
    "mechanism_step_state",
    "regional_explanation_state",
    "regional_kernel",
    "regional_kernel_factory",
    "regional_program_promotion_state",
    "regional_construction_learning_state",
    "regional_language_state",
    "regional_plan_state",
    "regional_program_state",
    "regional_representation_state",
    "regional_query_state",
    "regional_revision_state",
    "regional_sustained_episode_state",
    "regional_state",
    "semantic_cognition_kernel",
    "semantic_cognition_kernel_factory",
    "semantic_cognition_state",
    "tokenize",
]
