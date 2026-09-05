from __future__ import annotations

"""Cognitive operations whose learned content remains in one field atlas."""

import math
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

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
MAX_INQUIRY_SURVIVORS = 4_096
MAX_INQUIRY_OPERATIONS = 256
MAX_INQUIRY_INTERVALS = 131_072



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
        method: str = "direct",
        tolerance: float = 1e-10,
    ) -> ActionDecision:
        requested = tuple(name for name in readout.variables if name not in observed)
        if not requested:
            requested = readout.variables
        for name, value in observed.items():
            spec = state.variable(name)
            if not spec.contains(float(value), radius=readout.observed_error_radius):
                model_applicable = False
        query = self.atlas.query(
            state,
            observed=observed,
            requested=requested,
            context=context,
            valid_source_revision_ids=valid_source_revision_ids,
            method=method,
            tolerance=tolerance,
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
        control = self.atlas.query(
            state, observed=observed, requested=requested, context=context
        )
        counterfactual_state = replace(
            state, charts=tuple(row for row in state.charts if row.chart_id != chart_id)
        )
        counterfactual = self.atlas.query(
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


__all__ = [
    "ActionBranchCertificate",
    "ActionDecision",
    "ActionReadout",
    "FieldCognition",
    "InquiryDecision",
    "InquiryOperation",
    "Survivor",
    "adjoint_readout_certificate",
    "choose_inquiry",
    "consequence_partition",
    "directed_macro_margin",
    "model_uncertainty_bound",
    "prequential_radius",
    "tokenize",
]
