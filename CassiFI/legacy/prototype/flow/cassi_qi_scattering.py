"""Frozen W6T scale-geometry comparison and passive scattering evidence.

The module never advances the field or invents a boundary.  It materializes
registered periodic operators and validates replayable work receipts only.
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
import math
import struct
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import torch

from cassi_qi_bootstrap import canonical_hash, finite_bits
from cassi_qi_geometry import PeriodicSheetGeometry

QI_SCALE_GEOMETRY_PROFILE_SCHEMA = "cassi.qi-flow-scale-geometry.v1"
QI_SCALE_GEOMETRY_COMPARISON_SCHEMA = "cassi.qi-flow-scale-geometry-comparison.v1"
QI_SCATTERING_RECEIPT_SCHEMA = "cassi.qi-flow-scattering-receipt.v1"
QI_TOPOLOGY_CODEBOOK_SCHEMA = "cassi.qi-flow-topology-codebook-resolution.v1"
QI_SCALE_GEOMETRY_PROFILE_DOMAIN = QI_SCALE_GEOMETRY_PROFILE_SCHEMA
QI_SCALE_GEOMETRY_COMPARISON_DOMAIN = QI_SCALE_GEOMETRY_COMPARISON_SCHEMA
QI_SCATTERING_RECEIPT_DOMAIN = QI_SCATTERING_RECEIPT_SCHEMA
QI_TOPOLOGY_CODEBOOK_DOMAIN = QI_TOPOLOGY_CODEBOOK_SCHEMA
SCALE_GEOMETRY_MODE_IDS = ("temporal-full-rank", "spatiotemporal-pyramid")
CANDIDATE_MODE_IDS = SCALE_GEOMETRY_MODE_IDS
SELECTOR_ID = "lexicographic-F-rank-kappa-chi-work-cost-canonical-id-v1"
PERIODIC_FFT2_IDENTITY = "periodic-sheet-unitary-fft2-ortho-v1"
CONTROLLER_GRAMMAR_ID = "registered-controller-grammar-v1"
PYRAMID_ACTIVE_SHAPES = ((4, 8), (4, 4), (2, 4), (2, 2))
DEFAULT_SOURCE_FIXTURES = ("unit-constant", "pair-detail-nyquist-kernel", "impulse", "forward-reverse", "link-off", "adjoint-perturbed")
DEFAULT_ENDPOINT_PROBES = ("boundary-output", "action", "cross-scale")
SCATTERING_WORK_CHANNELS = ("W_incident", "W_reflected", "W_transmitted", "W_absorbed")


class ScatteringError(ValueError):
    """W6T evidence was malformed or could not be admitted."""


QiScatteringError = ScatteringError


def _num(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScatteringError(f"{name} must be a finite real")
    result = float(value)
    if not math.isfinite(result) or (result == 0.0 and math.copysign(1.0, result) < 0):
        raise ScatteringError(f"{name} must be finite and not negative zero")
    return result


def _nonnegative(name: str, value: Any) -> float:
    result = _num(name, value)
    if result < 0:
        raise ScatteringError(f"{name} must be non-negative")
    return result


def _int(name: str, value: Any, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or (value < 1 if positive else value < 0):
        raise ScatteringError(f"{name} must be {'positive' if positive else 'non-negative'} integer")
    return int(value)


def _text(name: str, value: Any, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value):
        raise ScatteringError(f"{name} must be a non-empty string")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ScatteringError(f"{name} contains an invalid surrogate")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze(item) for item in value), key=repr))
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _canonical(value: Any) -> Any:
    if isinstance(value, float):
        return finite_bits(value)
    if isinstance(value, complex):
        return {"re": finite_bits(float(value.real)), "im": finite_bits(float(value.imag))}
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _hash(value: Any, domain: str) -> str:
    return canonical_hash(_canonical(value), domain)


@dataclass(frozen=True)
class QiInterval:
    lower: float
    upper: float
    resolved: bool = True

    def __post_init__(self) -> None:
        lower, upper = _num("interval.lower", self.lower), _num("interval.upper", self.upper)
        if lower > upper or not isinstance(self.resolved, bool):
            raise ScatteringError("invalid interval")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)

    @classmethod
    def exact(cls, value: Any) -> "QiInterval":
        value = _num("interval value", value)
        return cls(value, value)

    @classmethod
    def unresolved(cls, lower: Any = 0.0, upper: Any = 0.0) -> "QiInterval":
        return cls(_num("interval.lower", lower), _num("interval.upper", upper), False)

    @property
    def is_exact(self) -> bool:
        return self.resolved and self.lower == self.upper

    def overlaps(self, other: "QiInterval") -> bool:
        return self.resolved and other.resolved and max(self.lower, other.lower) <= min(self.upper, other.upper)

    def encloses(self, other: "QiInterval") -> bool:
        return self.resolved and other.resolved and self.lower <= other.lower and self.upper >= other.upper

    def payload(self) -> dict[str, Any]:
        return {"lower": finite_bits(self.lower), "upper": finite_bits(self.upper), "resolved": self.resolved}


def _interval(name: str, value: Any) -> QiInterval:
    if isinstance(value, QiInterval):
        return value
    if isinstance(value, Mapping):
        if "lower" in value and "upper" in value:
            return QiInterval(value["lower"], value["upper"], bool(value.get("resolved", True)))
        if "value" in value:
            return QiInterval.exact(value["value"])
        raise ScatteringError(f"{name} mapping must contain lower and upper")
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return QiInterval(value[0], value[1])
    if value is None:
        return QiInterval.unresolved()
    return QiInterval.exact(value)


@dataclass(frozen=True)
class QiScaleGeometryThresholds:
    r_min: float = 1.0
    kappa_max: float = 1.0e12
    chi_max: float = 1.0
    w_max: float = 1.0e12
    c_max: float = 1.0e12
    receipt_id: str = ""

    def __post_init__(self) -> None:
        for name in ("r_min", "kappa_max", "chi_max", "w_max", "c_max"):
            object.__setattr__(self, name, _nonnegative(name, getattr(self, name)))
        expected = _hash(self.payload(), "cassi.qi-flow-scale-thresholds.v1")
        if self.receipt_id:
            _text("threshold receipt_id", self.receipt_id)
            if self.receipt_id != expected:
                raise ScatteringError("threshold receipt identity mismatch")
        else:
            object.__setattr__(self, "receipt_id", expected)

    def payload(self) -> dict[str, Any]:
        return {"schema": "cassi.qi-flow-scale-thresholds.v1", **{name: finite_bits(getattr(self, name)) for name in ("r_min", "kappa_max", "chi_max", "w_max", "c_max")}}


@dataclass(frozen=True)
class QiScaleGeometrySelectorReceipt:
    selector_id: str
    candidate_mode_ids: tuple[str, ...]
    thresholds: QiScaleGeometryThresholds
    feasible_mode_ids: tuple[str, ...]
    selected_mode: str | None
    status: str
    failure_reason: str | None = None
    decision_identity_sha256: str = ""

    def __post_init__(self) -> None:
        _text("selector_id", self.selector_id)
        if self.selector_id != SELECTOR_ID:
            raise ScatteringError("selector identity is not the frozen W6T selector")
        if tuple(self.candidate_mode_ids) != SCALE_GEOMETRY_MODE_IDS:
            raise ScatteringError("selector candidate set/order is not frozen")
        object.__setattr__(self, "candidate_mode_ids", SCALE_GEOMETRY_MODE_IDS)
        if not isinstance(self.thresholds, QiScaleGeometryThresholds):
            raise ScatteringError("selector thresholds are not immutable evidence")
        feasible = tuple(self.feasible_mode_ids)
        if any(mode not in SCALE_GEOMETRY_MODE_IDS for mode in feasible) or len(set(feasible)) != len(feasible):
            raise ScatteringError("selector feasible set is invalid")
        object.__setattr__(self, "feasible_mode_ids", feasible)
        if self.selected_mode not in (None, *SCALE_GEOMETRY_MODE_IDS):
            raise ScatteringError("selector mode is not registered")
        if self.status not in {"SELECTED", "FAIL"} or (self.status == "SELECTED") != (self.selected_mode is not None):
            raise ScatteringError("selector status/mode mismatch")
        if self.status == "FAIL" and not self.failure_reason:
            raise ScatteringError("failed selector needs a reason")
        expected = _hash(self.payload(), "cassi.qi-flow-scale-geometry-decision.v1")
        if self.decision_identity_sha256:
            _text("decision identity", self.decision_identity_sha256)
            if self.decision_identity_sha256 != expected:
                raise ScatteringError("selector decision identity mismatch")
        else:
            object.__setattr__(self, "decision_identity_sha256", expected)

    def payload(self) -> dict[str, Any]:
        return {"schema": "cassi.qi-flow-scale-geometry-selector.v1", "selector_id": self.selector_id, "candidate_mode_ids": list(self.candidate_mode_ids), "thresholds": self.thresholds.payload(), "feasible_mode_ids": list(self.feasible_mode_ids), "selected_mode": self.selected_mode, "status": self.status, "failure_reason": self.failure_reason}


@dataclass(frozen=True)
class QiScaleGeometryProfile:
    scale_geometry_mode: str | None = None
    candidate_mode_ids: tuple[str, ...] = SCALE_GEOMETRY_MODE_IDS
    candidate_profile_hashes: Mapping[str, str] = dc_field(default_factory=dict)
    periodic_fft_identity: str = PERIODIC_FFT2_IDENTITY
    controller_grammar: str = CONTROLLER_GRAMMAR_ID
    physical_horizon: QiInterval = dc_field(default_factory=lambda: QiInterval.exact(1.0))
    source_fixture_ids: tuple[str, ...] = DEFAULT_SOURCE_FIXTURES
    endpoint_probe_ids: tuple[str, ...] = DEFAULT_ENDPOINT_PROBES
    work_budget: Mapping[str, QiInterval] = dc_field(default_factory=lambda: {name: QiInterval.exact(1.0) for name in SCATTERING_WORK_CHANNELS})
    thresholds: QiScaleGeometryThresholds = dc_field(default_factory=QiScaleGeometryThresholds)
    selector: QiScaleGeometrySelectorReceipt | None = None
    profile_sha256: str = ""
    state_contract_sha256: str = ""
    backend_capacity_sha256: str = ""
    comparison_receipt_sha256: str | None = None
    self_sha256: str = ""
    def __post_init__(self) -> None:
        if tuple(self.candidate_mode_ids) != SCALE_GEOMETRY_MODE_IDS or (self.scale_geometry_mode is not None and self.scale_geometry_mode not in SCALE_GEOMETRY_MODE_IDS):
            raise ScatteringError("profile candidate registry is invalid")
        object.__setattr__(self, "candidate_mode_ids", SCALE_GEOMETRY_MODE_IDS)
        hashes = {str(key): _text("candidate hash", value) for key, value in dict(self.candidate_profile_hashes).items()}
        if set(hashes) - set(SCALE_GEOMETRY_MODE_IDS):
            raise ScatteringError("profile has an unknown candidate hash")
        object.__setattr__(self, "candidate_profile_hashes", MappingProxyType(hashes))
        object.__setattr__(self, "physical_horizon", _interval("physical horizon", self.physical_horizon))
        if not self.physical_horizon.resolved or self.physical_horizon.lower <= 0:
            raise ScatteringError("physical horizon must be resolved and positive")
        if self.periodic_fft_identity != PERIODIC_FFT2_IDENTITY or self.controller_grammar != CONTROLLER_GRAMMAR_ID:
            raise ScatteringError("profile periodic FFT/controller grammar is not frozen")
        fixtures, probes = tuple(_text("fixture", item) for item in self.source_fixture_ids), tuple(_text("probe", item) for item in self.endpoint_probe_ids)
        if not fixtures or not probes:
            raise ScatteringError("fixtures/probes cannot be empty")
        object.__setattr__(self, "source_fixture_ids", fixtures)
        object.__setattr__(self, "endpoint_probe_ids", probes)
        budget = {str(key): _interval(f"budget[{key}]", value) for key, value in dict(self.work_budget).items()}
        if set(budget) != set(SCATTERING_WORK_CHANNELS) or any(not value.resolved or value.lower < 0 for value in budget.values()):
            raise ScatteringError("work budget must freeze all four resolved channels")
        object.__setattr__(self, "work_budget", MappingProxyType(budget))
        selector = self.selector or QiScaleGeometrySelectorReceipt(SELECTOR_ID, SCALE_GEOMETRY_MODE_IDS, self.thresholds, (), None, "FAIL", "selection-not-yet-run")
        if selector.selector_id != SELECTOR_ID or selector.thresholds != self.thresholds:
            raise ScatteringError("profile selector is not the frozen W6T selector")
        object.__setattr__(self, "selector", selector)
        for name in ("profile_sha256", "state_contract_sha256", "backend_capacity_sha256"):
            if getattr(self, name):
                _text(name, getattr(self, name))
        if self.comparison_receipt_sha256 is not None:
            _text("comparison receipt", self.comparison_receipt_sha256)
        expected = _hash(self.payload(), QI_SCALE_GEOMETRY_PROFILE_DOMAIN)
        if self.self_sha256:
            _text("profile self hash", self.self_sha256)
            if self.self_sha256 != expected:
                raise ScatteringError("profile self identity mismatch")
        else:
            object.__setattr__(self, "self_sha256", expected)
        if self.profile_sha256:
            _text("profile identity", self.profile_sha256)
            if self.profile_sha256 != self.self_sha256:
                raise ScatteringError("profile identity does not match self hash")
        else:
            object.__setattr__(self, "profile_sha256", self.self_sha256)

    def payload(self) -> dict[str, Any]:
        return {"schema": QI_SCALE_GEOMETRY_PROFILE_SCHEMA, "scale_geometry_mode": self.scale_geometry_mode, "candidate_mode_ids": list(self.candidate_mode_ids), "candidate_profile_hashes": dict(self.candidate_profile_hashes), "periodic_fft_identity": self.periodic_fft_identity, "controller_grammar": self.controller_grammar, "physical_horizon": self.physical_horizon.payload(), "source_fixture_ids": list(self.source_fixture_ids), "endpoint_probe_ids": list(self.endpoint_probe_ids), "work_budget": {key: value.payload() for key, value in self.work_budget.items()}, "thresholds": self.thresholds.payload(), "selector": self.selector.payload(), "selector_decision_identity_sha256": self.selector.decision_identity_sha256, "state_contract_sha256": self.state_contract_sha256, "backend_capacity_sha256": self.backend_capacity_sha256, "comparison_receipt_sha256": self.comparison_receipt_sha256}


def _candidate_metric(candidate: Any, name: str) -> QiInterval:
    aliases = {"rank": ("rank_interval", "effective_rank_interval", "rank"), "condition": ("condition_interval", "conditioning_interval", "kappa_interval", "kappa"), "cross_talk": ("cross_talk_interval", "chi_interval", "cross_talk", "chi"), "work": ("work_interval", "work"), "cost": ("cost_interval", "cost")}
    for alias in aliases[name]:
        if isinstance(candidate, Mapping) and alias in candidate:
            return _interval(f"candidate.{alias}", candidate[alias])
        if hasattr(candidate, alias):
            return _interval(f"candidate.{alias}", getattr(candidate, alias))
    raise ScatteringError(f"candidate has no {name} interval")
 
def _matrix_tensor(value: Any) -> torch.Tensor:
    if torch.is_tensor(value):
        matrix = value.detach().cpu().to(torch.complex128)
    elif isinstance(value, (list, tuple)) and value and all(isinstance(row, (list, tuple)) for row in value):
        try:
            matrix = torch.tensor([[complex(item) for item in row] for row in value], dtype=torch.complex128)
        except (TypeError, ValueError) as exc:
            raise ScatteringError("operator map is not a finite matrix") from exc
    else:
        raise ScatteringError("operator map is not a matrix")
    if matrix.ndim != 2 or not bool(torch.isfinite(matrix.real).all().item()) or not bool(torch.isfinite(matrix.imag).all().item()):
        raise ScatteringError("operator map is not a finite matrix")
    return matrix.contiguous()


def _map_diagnostics(maps: Sequence[Any]) -> tuple[tuple[tuple[float, ...], ...], tuple[int, ...], tuple[int, ...], tuple[Any, ...], tuple[Any, ...], tuple[int, ...], float, float]:
    spectra, ranks, null_dims, null_bases, retained, collisions = [], [], [], [], [], []
    for value in maps:
        mapping = _matrix_tensor(value)
        singular = tuple(float(item.item()) for item in torch.linalg.svdvals(mapping))
        maximum = max(singular, default=0.0)
        tolerance = maximum * 1e-12
        rank = sum(item > tolerance for item in singular)
        _, _, vh = torch.linalg.svd(mapping)
        spectra.append(singular)
        ranks.append(rank)
        null_dims.append(mapping.shape[1] - rank)
        null_bases.append(_matrix_tuple(vh[rank:, :]))
        retained.append(_matrix_tuple(vh[:rank, :]))
        collisions.append(mapping.shape[1] - rank)
    nonzero = [item for row in spectra for item in row if item > max(row, default=0.0) * 1e-12]
    condition = max(nonzero) / min(nonzero) if nonzero else 0.0
    source_dimension = sum(_matrix_tensor(value).shape[1] for value in maps)
    cross_talk = sum(collisions) / max(1, source_dimension)
    return tuple(spectra), tuple(ranks), tuple(null_dims), tuple(null_bases), tuple(retained), tuple(collisions), condition, cross_talk


def _mode(candidate: Any) -> str:
    value = candidate.get("mode_id") if isinstance(candidate, Mapping) else getattr(candidate, "mode_id", None)
    return _text("candidate mode", value)


def _candidate_rows(candidates: Mapping[str, Any] | Sequence[Any]) -> dict[str, Any]:
    rows = dict(candidates) if isinstance(candidates, Mapping) else {_mode(candidate): candidate for candidate in candidates}
    if tuple(rows) != SCALE_GEOMETRY_MODE_IDS or any(_mode(candidate) != mode for mode, candidate in rows.items()):
        raise ScatteringError("candidate set/order must be exactly the two registered modes")
    return rows


def _feasible(candidate: Any, thresholds: QiScaleGeometryThresholds) -> bool:
    rank, condition, cross_talk, work, cost = (_candidate_metric(candidate, name) for name in ("rank", "condition", "cross_talk", "work", "cost"))
    return all(item.resolved for item in (rank, condition, cross_talk, work, cost)) and rank.lower >= thresholds.r_min and condition.upper <= thresholds.kappa_max and cross_talk.upper <= thresholds.chi_max and work.upper <= thresholds.w_max and cost.upper <= thresholds.c_max


def _order(left: QiInterval, right: QiInterval, maximize: bool) -> int | None:
    if not left.resolved or not right.resolved:
        return None
    if left.is_exact and right.is_exact and left.lower == right.lower:
        return 0
    if left.overlaps(right):
        return None
    if maximize:
        return 1 if left.lower > right.upper else -1 if right.lower > left.upper else None
    return 1 if left.upper < right.lower else -1 if right.upper < left.lower else None


def _compare(left: Any, right: Any) -> int | None:
    for name, maximize in (("rank", True), ("condition", False), ("cross_talk", False), ("work", False), ("cost", False)):
        result = _order(_candidate_metric(left, name), _candidate_metric(right, name), maximize)
        if result is None:
            return None
        if result:
            return result
    return 0


def select_scale_geometry(candidates: Mapping[str, Any] | Sequence[Any], *, thresholds: QiScaleGeometryThresholds, selector_id: str = SELECTOR_ID) -> QiScaleGeometrySelectorReceipt:
    if selector_id != SELECTOR_ID:
        raise ScatteringError("selector identity is not the frozen W6T selector")
    rows = _candidate_rows(candidates)
    feasible = tuple(mode for mode in SCALE_GEOMETRY_MODE_IDS if _feasible(rows[mode], thresholds))
    if not feasible:
        return QiScaleGeometrySelectorReceipt(selector_id, SCALE_GEOMETRY_MODE_IDS, thresholds, feasible, None, "FAIL", "empty-feasible-set")
    winner = rows[feasible[0]]
    for mode in feasible[1:]:
        result = _compare(winner, rows[mode])
        if result is None:
            return QiScaleGeometrySelectorReceipt(selector_id, SCALE_GEOMETRY_MODE_IDS, thresholds, feasible, None, "FAIL", f"undecidable-overlap:{_mode(winner)}:{mode}")
        if result < 0 or (result == 0 and mode < _mode(winner)):
            winner = rows[mode]
    return QiScaleGeometrySelectorReceipt(selector_id, SCALE_GEOMETRY_MODE_IDS, thresholds, feasible, _mode(winner), "SELECTED")


def select_candidate_mode(candidates: Mapping[str, Any] | Sequence[Any], *, thresholds: QiScaleGeometryThresholds, selector_id: str = SELECTOR_ID) -> str:
    receipt = select_scale_geometry(candidates, thresholds=thresholds, selector_id=selector_id)
    if receipt.status != "SELECTED":
        raise ScatteringError(receipt.failure_reason or "selection failed closed")
    return receipt.selected_mode or ""


@dataclass(frozen=True)
class QiScaleGeometryCandidate:
    mode_id: str
    profile_sha256: str
    operator_sha256: str
    periodic_fft_identity: str
    active_shapes: tuple[tuple[int, int], ...]
    active_site_counts: tuple[int, ...]
    packed_mode_count: int
    batch_lanes: int
    bytes_per_value: int
    active_bytes: int
    packed_bytes: int
    tail_bytes: int
    restriction_maps: tuple[Any, ...]
    adjoint_maps: tuple[Any, ...]
    singular_spectra: tuple[tuple[float, ...], ...]
    effective_ranks: tuple[int, ...]
    nullspace_dimensions: tuple[int, ...]
    nullspace_bases: tuple[Any, ...]
    retained_subspaces: tuple[Any, ...]
    dark_mode_counts: tuple[int, ...]
    collision_counts: tuple[int, ...]
    rank_interval: QiInterval
    condition_interval: QiInterval
    cross_talk_interval: QiInterval
    work_interval: QiInterval
    cost_interval: QiInterval
    topology_codebook_ids: tuple[str, ...] = ()
    full_spectrum_claim: bool = False
    controller_grammar: str = CONTROLLER_GRAMMAR_ID
    physical_horizon: QiInterval = dc_field(default_factory=lambda: QiInterval.exact(1.0))
    source_fixture_ids: tuple[str, ...] = DEFAULT_SOURCE_FIXTURES
    endpoint_probe_ids: tuple[str, ...] = DEFAULT_ENDPOINT_PROBES
    candidate_sha256: str = ""

    def __post_init__(self) -> None:
        if self.mode_id not in SCALE_GEOMETRY_MODE_IDS:
            raise ScatteringError("candidate mode is not registered")
        _text("candidate profile hash", self.profile_sha256)
        shapes = tuple(tuple(_int("shape dimension", dim, True) for dim in shape) for shape in self.active_shapes)
        counts = tuple(_int("active count", count, True) for count in self.active_site_counts)
        if len(shapes) != 4 or tuple(ny * nx for ny, nx in shapes) != counts:
            raise ScatteringError("candidate shapes/counts disagree")
        object.__setattr__(self, "active_shapes", shapes)
        object.__setattr__(self, "active_site_counts", counts)
        mode_count = _int("packed mode count", self.packed_mode_count, True)
        batch = _int("batch lanes", self.batch_lanes, True)
        bytes_per_value = _int("bytes per value", self.bytes_per_value, True)
        object.__setattr__(self, "packed_mode_count", mode_count)
        object.__setattr__(self, "batch_lanes", batch)
        object.__setattr__(self, "bytes_per_value", bytes_per_value)
        expected_active, expected_packed = 9 * bytes_per_value * batch * sum(counts), 9 * bytes_per_value * batch * 4 * mode_count
        if (self.active_bytes, self.packed_bytes, self.tail_bytes) != (expected_active, expected_packed, expected_packed - expected_active) or max(counts) > mode_count:
            raise ScatteringError("candidate byte accounting disagrees with [S,9M,B]")
        maps, adjoints = tuple(_matrix_tensor(item) for item in self.restriction_maps), tuple(_matrix_tensor(item) for item in self.adjoint_maps)
        if len(maps) != 3 or len(adjoints) != 3:
            raise ScatteringError("candidate maps need one item per adjacent link")
        for scale, (mapping, adjoint) in enumerate(zip(maps, adjoints)):
            if tuple(mapping.shape) != (counts[scale + 1], counts[scale]) or tuple(adjoint.shape) != (counts[scale], counts[scale + 1]):
                raise ScatteringError("candidate map dimensions disagree with active geometry")
        object.__setattr__(self, "restriction_maps", tuple(_matrix_tuple(item) for item in maps))
        object.__setattr__(self, "adjoint_maps", tuple(_matrix_tuple(item) for item in adjoints))
        for name in ("singular_spectra", "nullspace_bases", "retained_subspaces"):
            value = tuple(_freeze(item) for item in getattr(self, name))
            if len(value) != 3:
                raise ScatteringError(f"{name} needs one item per adjacent link")
            object.__setattr__(self, name, value)
        for name in ("effective_ranks", "nullspace_dimensions", "dark_mode_counts", "collision_counts"):
            value = tuple(_int(name, item) for item in getattr(self, name))
            if len(value) != 3:
                raise ScatteringError(f"{name} needs one item per adjacent link")
            object.__setattr__(self, name, value)
        expected_spectra, expected_ranks, expected_null_dims, expected_null_bases, expected_retained, expected_collisions, expected_condition, expected_cross_talk = _map_diagnostics(self.restriction_maps)
        if (self.singular_spectra, self.effective_ranks, self.nullspace_dimensions, self.nullspace_bases, self.retained_subspaces, self.dark_mode_counts, self.collision_counts) != (expected_spectra, expected_ranks, expected_null_dims, expected_null_bases, expected_retained, expected_null_dims, expected_collisions):
            raise ScatteringError("candidate rank/nullspace diagnostics do not match canonical maps")
        for name, expected in (("rank_interval", QiInterval.exact(min(expected_ranks))), ("condition_interval", QiInterval.exact(expected_condition)), ("cross_talk_interval", QiInterval.exact(expected_cross_talk))):
            interval = _interval(name, getattr(self, name))
            if interval != expected:
                raise ScatteringError(f"candidate {name} does not match canonical maps")
            object.__setattr__(self, name, interval)
        for name in ("work_interval", "cost_interval"):
            object.__setattr__(self, name, _interval(name, getattr(self, name)))
        if self.full_spectrum_claim and self.mode_id == "spatiotemporal-pyramid" and any(self.nullspace_dimensions):
            raise ScatteringError("rank-deficient pyramid cannot claim full spectrum")
        object.__setattr__(self, "topology_codebook_ids", tuple(_text("topology codebook", item) for item in self.topology_codebook_ids))
        fixtures = tuple(_text("candidate fixture", item) for item in self.source_fixture_ids)
        probes = tuple(_text("candidate probe", item) for item in self.endpoint_probe_ids)
        if not fixtures or not probes:
            raise ScatteringError("candidate fixtures/probes cannot be empty")
        object.__setattr__(self, "source_fixture_ids", fixtures)
        object.__setattr__(self, "endpoint_probe_ids", probes)
        object.__setattr__(self, "physical_horizon", _interval("candidate horizon", self.physical_horizon))
        if not self.physical_horizon.resolved or self.physical_horizon.lower <= 0:
            raise ScatteringError("candidate horizon must be resolved and positive")
        if self.periodic_fft_identity != PERIODIC_FFT2_IDENTITY or self.controller_grammar != CONTROLLER_GRAMMAR_ID:
            raise ScatteringError("candidate periodic FFT/controller grammar is not frozen")
        _text("candidate operator hash", self.operator_sha256)
        if not isinstance(self.full_spectrum_claim, bool):
            raise ScatteringError("candidate full spectrum claim must be boolean")
        expected_hash = _hash(self.payload(), "cassi.qi-flow-scale-geometry-candidate.v1")
        if self.candidate_sha256:
            _text("candidate hash", self.candidate_sha256)
            if self.candidate_sha256 != expected_hash:
                raise ScatteringError("candidate identity mismatch")
        else:
            object.__setattr__(self, "candidate_sha256", expected_hash)

    def payload(self) -> dict[str, Any]:
        return {"schema": "cassi.qi-flow-scale-geometry-candidate.v1", "mode_id": self.mode_id, "profile_sha256": self.profile_sha256, "operator_sha256": self.operator_sha256, "periodic_fft_identity": self.periodic_fft_identity, "active_shapes": [list(shape) for shape in self.active_shapes], "active_site_counts": list(self.active_site_counts), "packed_mode_count": self.packed_mode_count, "batch_lanes": self.batch_lanes, "bytes_per_value": self.bytes_per_value, "active_bytes": self.active_bytes, "packed_bytes": self.packed_bytes, "tail_bytes": self.tail_bytes, "restriction_maps": _plain(self.restriction_maps), "adjoint_maps": _plain(self.adjoint_maps), "singular_spectra": _plain(self.singular_spectra), "effective_ranks": list(self.effective_ranks), "nullspace_dimensions": list(self.nullspace_dimensions), "nullspace_bases": _plain(self.nullspace_bases), "retained_subspaces": _plain(self.retained_subspaces), "dark_mode_counts": list(self.dark_mode_counts), "collision_counts": list(self.collision_counts), "rank_interval": self.rank_interval.payload(), "condition_interval": self.condition_interval.payload(), "cross_talk_interval": self.cross_talk_interval.payload(), "work_interval": self.work_interval.payload(), "cost_interval": self.cost_interval.payload(), "topology_codebook_ids": list(self.topology_codebook_ids), "full_spectrum_claim": self.full_spectrum_claim, "controller_grammar": self.controller_grammar, "physical_horizon": self.physical_horizon.payload(), "source_fixture_ids": list(self.source_fixture_ids), "endpoint_probe_ids": list(self.endpoint_probe_ids)}

    def restriction_map_tensors(self) -> tuple[torch.Tensor, ...]:
        return tuple(torch.tensor([[complex(value) for value in row] for row in matrix], dtype=torch.complex128) for matrix in self.restriction_maps)

    def adjoint_map_tensors(self) -> tuple[torch.Tensor, ...]:
        return tuple(torch.tensor([[complex(value) for value in row] for row in matrix], dtype=torch.complex128) for matrix in self.adjoint_maps)

def _validate_candidate_replay(candidate: QiScaleGeometryCandidate) -> None:
    expected_spectra, expected_ranks, expected_null_dims, expected_null_bases, expected_retained, expected_collisions, expected_condition, expected_cross_talk = _map_diagnostics(candidate.restriction_maps)
    if (candidate.singular_spectra, candidate.effective_ranks, candidate.nullspace_dimensions, candidate.nullspace_bases, candidate.retained_subspaces, candidate.dark_mode_counts, candidate.collision_counts) != (expected_spectra, expected_ranks, expected_null_dims, expected_null_bases, expected_retained, expected_null_dims, expected_collisions):
        raise ScatteringError("candidate diagnostics fail independent replay")
    if candidate.rank_interval != QiInterval.exact(min(expected_ranks)) or candidate.condition_interval != QiInterval.exact(expected_condition) or candidate.cross_talk_interval != QiInterval.exact(expected_cross_talk):
        raise ScatteringError("candidate metric intervals fail independent replay")
    if candidate.candidate_sha256 != _hash(candidate.payload(), "cassi.qi-flow-scale-geometry-candidate.v1"):
        raise ScatteringError("candidate identity fails independent replay")


@dataclass(frozen=True)
class QiScaleGeometryComparisonReceipt:
    """Frozen comparison of exactly the two registered geometry candidates."""

    comparison_id: str
    profile: QiScaleGeometryProfile
    candidates: Mapping[str, QiScaleGeometryCandidate]
    selector: QiScaleGeometrySelectorReceipt
    topology_evidence: tuple[Any, ...] = ()
    scattering_receipt_ids: tuple[str, ...] = ()
    status: str = "FAIL"
    selected_mode: str | None = None
    self_sha256: str = ""

    def __post_init__(self) -> None:
        _text("comparison_id", self.comparison_id)
        if not isinstance(self.profile, QiScaleGeometryProfile):
            raise ScatteringError("comparison profile must be immutable profile evidence")
        rows = _candidate_rows(self.candidates)
        if any(not isinstance(row, QiScaleGeometryCandidate) for row in rows.values()):
            raise ScatteringError("comparison candidates must be immutable candidate evidence")
        object.__setattr__(self, "candidates", MappingProxyType(rows))
        if not isinstance(self.selector, QiScaleGeometrySelectorReceipt) or self.selector.selector_id != SELECTOR_ID or self.selector.candidate_mode_ids != SCALE_GEOMETRY_MODE_IDS or self.selector.thresholds != self.profile.thresholds or self.profile.selector.selector_id != SELECTOR_ID:
            raise ScatteringError("comparison selector does not match frozen profile")
        for mode, candidate in rows.items():
            if candidate.profile_sha256 != self.profile.profile_sha256:
                raise ScatteringError(f"candidate {mode} profile hash is not pinned to profile")
            expected_hash = self.profile.candidate_profile_hashes.get(mode, "")
            if expected_hash and expected_hash != candidate.profile_sha256:
                raise ScatteringError(f"candidate {mode} profile hash mismatch")
            if candidate.periodic_fft_identity != self.profile.periodic_fft_identity or candidate.controller_grammar != self.profile.controller_grammar or candidate.physical_horizon != self.profile.physical_horizon or tuple(candidate.source_fixture_ids) != self.profile.source_fixture_ids or tuple(candidate.endpoint_probe_ids) != self.profile.endpoint_probe_ids:
                raise ScatteringError(f"candidate {mode} changes a frozen comparison control")
        if self.status not in {"SELECTED", "FAIL"} or (self.status == "SELECTED") != (self.selected_mode is not None):
            raise ScatteringError("comparison status and selected mode disagree")
        if self.status == "SELECTED" and self.selected_mode != self.selector.selected_mode:
            raise ScatteringError("comparison selected mode disagrees with selector")
        object.__setattr__(self, "topology_evidence", tuple(self.topology_evidence))
        scattering_ids = tuple(_text("scattering receipt id", value) for value in self.scattering_receipt_ids)
        if len(scattering_ids) != len(set(scattering_ids)):
            raise ScatteringError("comparison scattering receipt identities are duplicated")
        object.__setattr__(self, "scattering_receipt_ids", scattering_ids)
        expected = _hash(self.payload(), QI_SCALE_GEOMETRY_COMPARISON_DOMAIN)
        if self.self_sha256:
            _text("comparison self hash", self.self_sha256)
            if self.self_sha256 != expected:
                raise ScatteringError("comparison self identity mismatch")
        else:
            object.__setattr__(self, "self_sha256", expected)

    def payload(self) -> dict[str, Any]:
        return {
            "schema": QI_SCALE_GEOMETRY_COMPARISON_SCHEMA,
            "comparison_id": self.comparison_id,
            "profile_sha256": self.profile.profile_sha256,
            "state_contract_sha256": self.profile.state_contract_sha256,
            "backend_capacity_sha256": self.profile.backend_capacity_sha256,
            "candidate_mode_ids": list(SCALE_GEOMETRY_MODE_IDS),
            "periodic_fft_identity": self.profile.periodic_fft_identity,
            "controller_grammar": self.profile.controller_grammar,
            "physical_horizon": self.profile.physical_horizon.payload(),
            "source_fixture_ids": list(self.profile.source_fixture_ids),
            "endpoint_probe_ids": list(self.profile.endpoint_probe_ids),
            "work_budget": {key: value.payload() for key, value in self.profile.work_budget.items()},
            "thresholds": self.profile.thresholds.payload(),
            "selector": self.selector.payload() | {"decision_identity_sha256": self.selector.decision_identity_sha256},
            "candidates": {key: value.payload() for key, value in self.candidates.items()},
            "topology_evidence": [_plain(value.payload() if hasattr(value, "payload") else value) for value in self.topology_evidence],
            "scattering_receipt_ids": list(self.scattering_receipt_ids),
            "status": self.status,
            "selected_mode": self.selected_mode,
        }


def build_scale_geometry_comparison(
    profile: QiScaleGeometryProfile,
    candidates: Mapping[str, QiScaleGeometryCandidate],
    *,
    comparison_id: str = "scale-geometry-comparison",
    topology_evidence: Sequence[Any] = (),
    scattering_receipt_ids: Sequence[str] = (),
) -> QiScaleGeometryComparisonReceipt:
    rows = _candidate_rows(candidates)
    for mode, candidate in rows.items():
        if (
            candidate.periodic_fft_identity != profile.periodic_fft_identity
            or candidate.controller_grammar != profile.controller_grammar
            or candidate.physical_horizon != profile.physical_horizon
            or tuple(candidate.source_fixture_ids) != profile.source_fixture_ids
            or tuple(candidate.endpoint_probe_ids) != profile.endpoint_probe_ids
        ):
            raise ScatteringError(f"candidate {mode} changes a frozen comparison control")
        if candidate.profile_sha256 != profile.profile_sha256:
            raise ScatteringError(f"candidate {mode} profile hash is not pinned to comparison profile")
        expected_hash = profile.candidate_profile_hashes.get(mode, "")
        if expected_hash and expected_hash != candidate.profile_sha256:
            raise ScatteringError(f"candidate {mode} profile hash mismatch")
        if mode == "spatiotemporal-pyramid" and candidate.full_spectrum_claim and any(candidate.nullspace_dimensions):
            raise ScatteringError("rank-deficient pyramid cannot claim full spectrum")
    selector = select_scale_geometry(rows, thresholds=profile.thresholds, selector_id=profile.selector.selector_id)
    selected = selector.selected_mode if selector.status == "SELECTED" else None
    if profile.scale_geometry_mode is not None and selected != profile.scale_geometry_mode:
        selector = QiScaleGeometrySelectorReceipt(selector.selector_id, selector.candidate_mode_ids, selector.thresholds, selector.feasible_mode_ids, None, "FAIL", "selected-mode-disagrees-with-frozen-profile")
        selected = None
    for evidence in topology_evidence:
        if selected is None or not isinstance(evidence, QiTopologyCodebookEvidence):
            raise ScatteringError("topology evidence requires a selected geometry mode")
        validate_topology_codebook_evidence(evidence, resolution=rows[selected].active_shapes[-1], periodic_fft_identity=profile.periodic_fft_identity)
    return QiScaleGeometryComparisonReceipt(
        comparison_id,
        profile,
        rows,
        selector,
        tuple(topology_evidence),
        tuple(scattering_receipt_ids),
        "SELECTED" if selected is not None else "FAIL",
        selected,
    )


def validate_scale_geometry_comparison(receipt: QiScaleGeometryComparisonReceipt, *, scattering_receipts: Sequence["QiScatteringReceipt"] = (), raw_work_rows: Mapping[str, Mapping[str, Any]] | None = None) -> None:
    if not isinstance(receipt, QiScaleGeometryComparisonReceipt) or _hash(receipt.payload(), QI_SCALE_GEOMETRY_COMPARISON_DOMAIN) != receipt.self_sha256:
        raise ScatteringError("scale geometry comparison self hash mismatch/type")
    if receipt.profile.comparison_receipt_sha256 is not None and receipt.profile.comparison_receipt_sha256 != receipt.self_sha256:
        raise ScatteringError("scale geometry comparison parent identity mismatch")
    rows = _candidate_rows(receipt.candidates)
    for candidate in rows.values():
        _validate_candidate_replay(candidate)
    recomputed = select_scale_geometry(rows, thresholds=receipt.profile.thresholds, selector_id=receipt.profile.selector.selector_id)
    if recomputed.payload() != receipt.selector.payload() or recomputed.decision_identity_sha256 != receipt.selector.decision_identity_sha256:
        raise ScatteringError("scale geometry selector fails independent replay")
    selected = recomputed.selected_mode if recomputed.status == "SELECTED" else None
    if receipt.status != "SELECTED" or receipt.selected_mode is None or selected != receipt.selected_mode or (receipt.profile.scale_geometry_mode is not None and receipt.profile.scale_geometry_mode != selected):
        raise ScatteringError("scale geometry comparison failed closed")
    for evidence in receipt.topology_evidence:
        if not isinstance(evidence, QiTopologyCodebookEvidence):
            raise ScatteringError("comparison topology evidence has an invalid type")
        validate_topology_codebook_evidence(evidence, resolution=rows[selected].active_shapes[-1], periodic_fft_identity=receipt.profile.periodic_fft_identity)
    if receipt.scattering_receipt_ids:
        supplied = tuple(scattering_receipts)
        by_id = {item.receipt_id: item for item in supplied}
        if set(by_id) != set(receipt.scattering_receipt_ids):
            raise ScatteringError("comparison scattering receipt identities are incomplete")
        for item in supplied:
            rows_for_item = raw_work_rows
            if raw_work_rows is not None and item.receipt_id in raw_work_rows and isinstance(raw_work_rows[item.receipt_id], Mapping):
                nested = raw_work_rows[item.receipt_id]
                if set(nested) == set(SCATTERING_WORK_CHANNELS):
                    rows_for_item = nested
            validate_scattering_receipt(item, raw_work_rows=rows_for_item)


def _surface(geometry: Any) -> Any:
    if isinstance(geometry, PeriodicSheetGeometry) or (hasattr(geometry, "cross_scale_matrix") and hasattr(geometry, "metric_matrix")):
        return geometry
    return PeriodicSheetGeometry(geometry)


def _mode_count(geometry: Any, profile: Any, state: torch.Tensor | None) -> int:
    if state is not None:
        return int(state.shape[1] // 9)
    if hasattr(profile, "state_layout") and isinstance(profile.state_layout, Mapping) and "mode_count" in profile.state_layout:
        return _int("mode count", profile.state_layout["mode_count"], True)
    surface = _surface(geometry)
    return max(int(surface.active_site_count(scale)) for scale in range(4))


def _shapes(geometry: Any, mode: str, active_shapes: Sequence[Sequence[int]] | None) -> tuple[tuple[int, int], ...]:
    if active_shapes is not None:
        result = tuple(tuple(int(dim) for dim in shape) for shape in active_shapes)
    elif mode == "spatiotemporal-pyramid":
        result = PYRAMID_ACTIVE_SHAPES
    else:
        surface = _surface(geometry)
        result = tuple(tuple(int(dim) for dim in surface.sheet_shape(scale)) for scale in range(4))
    if len(result) != 4 or any(len(shape) != 2 or any(dim < 1 for dim in shape) for shape in result):
        raise ScatteringError("candidate needs four positive rectangular sheets")
    if mode == "temporal-full-rank" and len(set(result)) != 1:
        raise ScatteringError("temporal-full-rank requires equal active sheets")
    if mode == "spatiotemporal-pyramid" and any(result[i + 1][0] * result[i + 1][1] >= result[i][0] * result[i][1] for i in range(3)):
        raise ScatteringError("pyramid active sheets must strictly decrease")
    return result


def _matrix_tuple(matrix: torch.Tensor) -> tuple[tuple[Any, ...], ...]:
    matrix = matrix.detach().cpu()
    return tuple(tuple(complex(item.item()) if torch.is_complex(matrix) else float(item.item()) for item in row) for row in matrix)


def _pair_average(source: tuple[int, int], target: tuple[int, int]) -> torch.Tensor:
    sy, sx, ty, tx = source[0], source[1], target[0], target[1]
    if sy % ty or sx % tx:
        raise ScatteringError("pyramid dimensions need integer periodic ratios")
    matrix = torch.zeros((ty * tx, sy * sx), dtype=torch.complex128)
    weight = 1.0 / ((sy // ty) * (sx // tx))
    for y in range(ty):
        for x in range(tx):
            for yy in range(y * sy // ty, (y + 1) * sy // ty):
                for xx in range(x * sx // tx, (x + 1) * sx // tx):
                    matrix[y * tx + x, yy * sx + xx] = weight
    return matrix


def _geometry_metric(surface: Any, scale: int, shape: tuple[int, int]) -> torch.Tensor:
    expected = shape[0] * shape[1]
    try:
        matrix = surface.metric_matrix(scale)
        if tuple(matrix.shape) == (expected, expected):
            return matrix.to(torch.complex128)
    except Exception:
        pass
    try:
        area = float(surface.cell_area_m2(scale))
    except Exception:
        area = 1.0
    return torch.eye(expected, dtype=torch.complex128) * area


def materialize_candidate_operator_data(mode: str, *, geometry: Any, profile: Any | None = None, state: Any | None = None, active_shapes: Sequence[Sequence[int]] | None = None, periodic_fft_identity: str = PERIODIC_FFT2_IDENTITY, controller_grammar: str = CONTROLLER_GRAMMAR_ID, physical_horizon: QiInterval | float = QiInterval.exact(1.0), source_fixture_ids: Sequence[str] = DEFAULT_SOURCE_FIXTURES, endpoint_probe_ids: Sequence[str] = DEFAULT_ENDPOINT_PROBES, work_interval: QiInterval | float | None = None, cost_interval: QiInterval | float | None = None, full_spectrum_claim: bool = False, topology_codebook_ids: Sequence[str] = ()) -> QiScaleGeometryCandidate:
    if mode not in SCALE_GEOMETRY_MODE_IDS:
        raise ScatteringError("unknown candidate mode")
    tensor = state.field if hasattr(state, "field") else state
    if tensor is not None:
        if not torch.is_tensor(tensor) or tensor.device.type != "cpu" or not tensor.is_contiguous() or tensor.ndim != 3 or tensor.shape[0] != 4 or tensor.shape[1] % 9 or tensor.shape[2] < 1 or tensor.dtype not in (torch.float32, torch.float64, torch.complex64, torch.complex128):
            raise ScatteringError("state must be fixed contiguous CPU [S,9M,B]")
        finite = torch.isfinite(tensor.real)
        if tensor.is_complex():
            finite = finite & torch.isfinite(tensor.imag)
        if not bool(finite.all().item()):
            raise ScatteringError("state has nonfinite values")
    surface, shapes, mode_count = _surface(geometry), _shapes(geometry, mode, active_shapes), _mode_count(geometry, profile, tensor)
    batch = int(tensor.shape[2]) if tensor is not None else 1
    if max(shape[0] * shape[1] for shape in shapes) > mode_count:
        raise ScatteringError("candidate exceeds packed mode count")
    if tensor is not None:
        for scale, shape in enumerate(shapes):
            active = shape[0] * shape[1]
            for component in range(9):
                if bool(torch.count_nonzero(tensor[scale, component * mode_count + active:(component + 1) * mode_count]).item()):
                    raise ScatteringError("inactive packed tail is not zero")
    maps, adjoints = [], []
    for scale in range(3):
        if mode == "temporal-full-rank":
            try:
                mapping, adjoint = surface.cross_scale_matrix(scale, scale + 1).to(torch.complex128), surface.cross_scale_adjoint_matrix(scale, scale + 1).to(torch.complex128)
            except Exception as exc:
                raise ScatteringError("periodic geometry map unavailable") from exc
        else:
            mapping = _pair_average(shapes[scale], shapes[scale + 1])
            adjoint = torch.linalg.solve(_geometry_metric(surface, scale, shapes[scale]), mapping.conj().T @ _geometry_metric(surface, scale + 1, shapes[scale + 1])).contiguous()
        maps.append(mapping.contiguous())
        adjoints.append(adjoint.contiguous())
    canonical_maps = tuple(_matrix_tuple(item) for item in maps)
    spectra, ranks, null_dims, null_bases, retained, collisions, condition, cross_talk = _map_diagnostics(canonical_maps)
    counts = tuple(shape[0] * shape[1] for shape in shapes)
    active_bytes, packed_bytes = 9 * (tensor.element_size() if tensor is not None else 8) * batch * sum(counts), 9 * (tensor.element_size() if tensor is not None else 8) * batch * 4 * mode_count
    profile_identity = "" if profile is None else str(getattr(profile, "profile_sha256", ""))
    if not profile_identity:
        profile_identity = _hash({"mode": mode, "active_shapes": shapes, "periodic_fft_identity": periodic_fft_identity, "controller_grammar": controller_grammar, "physical_horizon": _interval("horizon", physical_horizon).payload(), "source_fixture_ids": list(source_fixture_ids), "endpoint_probe_ids": list(endpoint_probe_ids)}, "cassi.qi-flow-standalone-profile.v1")
    return QiScaleGeometryCandidate(mode, profile_identity, _hash({"mode": mode, "shapes": shapes, "maps": canonical_maps, "periodic_fft_identity": periodic_fft_identity}, "cassi.qi-flow-scale-geometry-operator.v1"), periodic_fft_identity, shapes, counts, mode_count, batch, tensor.element_size() if tensor is not None else 8, active_bytes, packed_bytes, packed_bytes - active_bytes, canonical_maps, tuple(_matrix_tuple(item) for item in adjoints), tuple(spectra), tuple(ranks), tuple(null_dims), tuple(null_bases), tuple(retained), tuple(null_dims), tuple(collisions), QiInterval.exact(min(ranks)), QiInterval.exact(condition), QiInterval.exact(cross_talk), QiInterval.unresolved() if work_interval is None else _interval("work", work_interval), QiInterval.exact(sum(counts)) if cost_interval is None else _interval("cost", cost_interval), tuple(topology_codebook_ids), full_spectrum_claim, controller_grammar, _interval("horizon", physical_horizon), tuple(source_fixture_ids), tuple(endpoint_probe_ids))


def topology_witness_hash(codeword: Any, resolution: Sequence[int]) -> str:
    shape = tuple(_int("codebook resolution", item, True) for item in resolution)
    if len(shape) != 2:
        raise ScatteringError("topology witness resolution must be two-dimensional")
    return _hash({"resolution": list(shape), "codeword": _plain(_freeze(codeword))}, "cassi.qi-flow-topology-witness.v1")


@dataclass(frozen=True)
class QiTopologyCodebookEvidence:
    codebook_id: str
    resolution: tuple[int, int]
    codewords: tuple[Any, ...]
    witness_hashes: tuple[str, ...]
    periodic_fft_identity: str
    metric_identity: str
    operator_identity: str
    amplitude_guard: str
    branch_guard: str
    edge_registry_identity: str
    realizable: bool = True
    resolution_scaled: bool = True
    zero_clock_remap_preserved: bool = True
    zero_clock_remap_identity: str = "identity"
    self_sha256: str = ""
    def __post_init__(self) -> None:
        resolution = tuple(_int("codebook resolution", item, True) for item in self.resolution)
        if len(resolution) != 2 or not self.codewords or len(self.witness_hashes) != len(self.codewords):
            raise ScatteringError("invalid topology codebook evidence")
        words = tuple(_freeze(word) for word in self.codewords)
        if len({_hash(word, "cassi.qi-flow-topology-codeword.v1") for word in words}) != len(words):
            raise ScatteringError("topology codebook has duplicate codewords")
        witness_hashes = tuple(_text("witness hash", item) for item in self.witness_hashes)
        if witness_hashes != tuple(topology_witness_hash(word, resolution) for word in words):
            raise ScatteringError("topology witness does not match codeword/resolution")
        object.__setattr__(self, "resolution", resolution)
        object.__setattr__(self, "codewords", words)
        object.__setattr__(self, "witness_hashes", witness_hashes)
        for name in ("codebook_id", "periodic_fft_identity", "metric_identity", "operator_identity", "amplitude_guard", "branch_guard", "edge_registry_identity", "zero_clock_remap_identity"):
            _text(name, getattr(self, name))
        if self.periodic_fft_identity != PERIODIC_FFT2_IDENTITY:
            raise ScatteringError("topology evidence periodic FFT identity is not frozen")
        for name in ("realizable", "resolution_scaled", "zero_clock_remap_preserved"):
            if not isinstance(getattr(self, name), bool):
                raise ScatteringError(f"{name} must be boolean")
        expected = _hash(self.payload(), QI_TOPOLOGY_CODEBOOK_DOMAIN)
        if self.self_sha256:
            _text("codebook hash", self.self_sha256)
            if self.self_sha256 != expected:
                raise ScatteringError("topology codebook identity mismatch")
        else:
            object.__setattr__(self, "self_sha256", expected)

    def payload(self) -> dict[str, Any]:
        return {"schema": QI_TOPOLOGY_CODEBOOK_SCHEMA, "codebook_id": self.codebook_id, "resolution": list(self.resolution), "codewords": _plain(self.codewords), "witness_hashes": list(self.witness_hashes), "periodic_fft_identity": self.periodic_fft_identity, "metric_identity": self.metric_identity, "operator_identity": self.operator_identity, "amplitude_guard": self.amplitude_guard, "branch_guard": self.branch_guard, "edge_registry_identity": self.edge_registry_identity, "realizable": self.realizable, "resolution_scaled": self.resolution_scaled, "zero_clock_remap_preserved": self.zero_clock_remap_preserved, "zero_clock_remap_identity": self.zero_clock_remap_identity}


def validate_zero_clock_remap_preservation(evidence: QiTopologyCodebookEvidence, *, remap: Mapping[Any, Any] | None = None) -> None:
    if not evidence.zero_clock_remap_preserved or not evidence.zero_clock_remap_identity:
        raise ScatteringError("zero-clock remap preservation failed")
    if remap is not None:
        before = {_hash(word, "cassi.qi-flow-topology-codeword.v1") for word in evidence.codewords}
        transformed = []
        for word in evidence.codewords:
            try:
                transformed.append(_freeze(remap.get(word, word)))
            except TypeError:
                transformed.append(_freeze(remap.get(_hash(word, "cassi.qi-flow-topology-codeword.v1"), word)))
        after = {_hash(word, "cassi.qi-flow-topology-codeword.v1") for word in transformed}
        if before != after:
            raise ScatteringError("zero-clock remap changes codebook")


def validate_topology_codebook_evidence(evidence: QiTopologyCodebookEvidence, *, resolution: tuple[int, int], periodic_fft_identity: str, metric_identity: str | None = None, operator_identity: str | None = None, remap: Mapping[Any, Any] | None = None) -> None:
    expected_witnesses = tuple(topology_witness_hash(word, evidence.resolution) for word in evidence.codewords)
    if tuple(resolution) != evidence.resolution or evidence.periodic_fft_identity != periodic_fft_identity or (metric_identity is not None and evidence.metric_identity != metric_identity) or (operator_identity is not None and evidence.operator_identity != operator_identity) or evidence.witness_hashes != expected_witnesses or not evidence.realizable or not evidence.resolution_scaled:
        raise ScatteringError("topology codebook resolution/realizability mismatch")
    validate_zero_clock_remap_preservation(evidence, remap=remap)
    if _hash(evidence.payload(), QI_TOPOLOGY_CODEBOOK_DOMAIN) != evidence.self_sha256:
        raise ScatteringError("topology evidence hash mismatch")


def build_topology_codebook_evidence(**kwargs: Any) -> QiTopologyCodebookEvidence:
    return QiTopologyCodebookEvidence(**kwargs)


@dataclass(frozen=True)
class QiPortDescriptor:
    port_id: str
    interface_id: str
    kind: str
    source_scale: int | None
    target_scale: int | None
    orientation: int
    scale_geometry_mode: str
    profile_sha256: str = ""
    operator_sha256: str = ""
    metric_sha256: str = ""
    permeability_profile_sha256: str = ""
    descriptor_sha256: str = ""

    def __post_init__(self) -> None:
        _text("port_id", self.port_id); _text("interface_id", self.interface_id)
        if self.kind not in {"internal", "external"} or self.scale_geometry_mode not in SCALE_GEOMETRY_MODE_IDS or self.orientation not in {-1, 1}:
            raise ScatteringError("invalid port descriptor")
        if self.kind == "internal" and (not isinstance(self.source_scale, int) or not isinstance(self.target_scale, int) or self.source_scale < 0 or self.target_scale < 0 or self.source_scale == self.target_scale):
            raise ScatteringError("internal port needs distinct source/target scales")
        if self.kind == "external" and (self.source_scale is not None or self.target_scale is not None):
            raise ScatteringError("external port cannot claim a scale endpoint")
        identity_base = {"port_id": self.port_id, "interface_id": self.interface_id, "kind": self.kind, "source_scale": self.source_scale, "target_scale": self.target_scale, "orientation": self.orientation, "scale_geometry_mode": self.scale_geometry_mode}
        for name in ("profile_sha256", "operator_sha256", "metric_sha256", "permeability_profile_sha256"):
            value = getattr(self, name)
            if value:
                _text(name, value)
            else:
                object.__setattr__(self, name, _hash(identity_base | {"field": name}, "cassi.qi-flow-port-identity.v1"))
        expected = _hash(self.payload(), "cassi.qi-flow-port-descriptor.v1")
        if self.descriptor_sha256:
            _text("port descriptor hash", self.descriptor_sha256)
            if self.descriptor_sha256 != expected:
                raise ScatteringError("port descriptor identity mismatch")
        else:
            object.__setattr__(self, "descriptor_sha256", expected)

    def payload(self) -> dict[str, Any]:
        return {"schema": "cassi.qi-flow-port-descriptor.v1", "port_id": self.port_id, "interface_id": self.interface_id, "kind": self.kind, "source_scale": self.source_scale, "target_scale": self.target_scale, "orientation": self.orientation, "scale_geometry_mode": self.scale_geometry_mode, "profile_sha256": self.profile_sha256, "operator_sha256": self.operator_sha256, "metric_sha256": self.metric_sha256, "permeability_profile_sha256": self.permeability_profile_sha256}


def _port(value: QiPortDescriptor | Mapping[str, Any]) -> QiPortDescriptor:
    if isinstance(value, QiPortDescriptor):
        return value
    if not isinstance(value, Mapping):
        raise ScatteringError("port descriptor must be immutable evidence or mapping")
    source, target = value.get("source_scale", value.get("source")), value.get("target_scale", value.get("target"))
    return QiPortDescriptor(str(value.get("port_id", value.get("id", ""))), str(value.get("interface_id", value.get("port_id", value.get("id", "")))), str(value.get("kind", "external")), source, target, int(value.get("orientation", 1)), str(value.get("scale_geometry_mode", "temporal-full-rank")), str(value.get("profile_sha256", "")), str(value.get("operator_sha256", "")), str(value.get("metric_sha256", "")), str(value.get("permeability_profile_sha256", "")), str(value.get("descriptor_sha256", "")))


def declare_scale_interfaces(*, scale_count: int = 4, scale_geometry_mode: str = "temporal-full-rank", profile_sha256: str = "", operator_sha256: str = "", metric_sha256: str = "", permeability_profile_sha256: str = "") -> tuple[QiPortDescriptor, ...]:
    scale_count = _int("scale count", scale_count, True)
    if scale_count < 2:
        raise ScatteringError("at least two scales are required")
    return tuple(QiPortDescriptor(f"scale-link:{s}:{s + 1}", f"scale-link:{s}:{s + 1}", "internal", s, s + 1, 1, scale_geometry_mode, profile_sha256, operator_sha256, metric_sha256, permeability_profile_sha256) for s in range(scale_count - 1))
def _row(channel: str, value: Any, default_id: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        row = {str(key): _freeze(item) for key, item in value.items() if key != "volatile_telemetry"}
        row_id = _text(f"{channel} row_id", str(row.get("row_id", default_id)))
        if "interval" in row:
            interval = _interval(channel, row["interval"])
        elif "value" in row:
            interval = _interval(channel, row["value"])
        elif "work" in row:
            interval = _interval(channel, row["work"])
        else:
            raise ScatteringError(f"work row {channel} needs value/interval")
        if row.get("link_count", 1) != 1:
            raise ScatteringError("work row must link exactly once")
        row["row_id"], row["interval"] = row_id, interval
        return row
    return {"row_id": _text(f"{channel} row_id", default_id), "interval": _interval(channel, value)}


def _rows(interface_id: str, raw: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(raw, Mapping) or set(raw) != set(SCATTERING_WORK_CHANNELS):
        raise ScatteringError("work rows must contain all four channels")
    rows = {channel: _row(channel, raw[channel], f"{interface_id}:{channel}") for channel in SCATTERING_WORK_CHANNELS}
    if len({str(row["row_id"]) for row in rows.values()}) != 4:
        raise ScatteringError("work row is linked more than once")
    return MappingProxyType({channel: MappingProxyType(dict(row)) for channel, row in rows.items()})


def _work_hash(rows: Mapping[str, Mapping[str, Any]]) -> str:
    return _hash({channel: {key: value.payload() if isinstance(value, QiInterval) else _plain(value) for key, value in row.items() if key != "volatile_telemetry"} for channel, row in rows.items()}, "cassi.qi-flow-scattering-work-rows.v1")


def _subtract(*values: QiInterval) -> QiInterval:
    lower, upper = values[0].lower, values[0].upper
    for value in values[1:]:
        lower, upper = lower - value.upper, upper - value.lower
    return QiInterval(lower, upper, all(value.resolved for value in values))


def _closure(channels: Sequence[QiInterval], residual: QiInterval, bound: float) -> None:
    computed = _subtract(*channels)
    if not residual.resolved or not all(value.resolved and value.lower >= 0 for value in channels) or not residual.encloses(computed) or residual.lower < -bound or residual.upper > bound or computed.lower < -bound or computed.upper > bound:
        raise ScatteringError("scattering closure is not a resolved bounded enclosure")


@dataclass(frozen=True)
class QiScatteringReceipt:
    receipt_id: str
    step: int
    head_sha256: str
    port_id: str
    interface_id: str
    kind: str
    scale_geometry_mode: str
    source_scale: int | None
    target_scale: int | None
    orientation: int
    incoming_trajectory_sha256: str
    stage_id: str
    tick_interval: QiInterval
    profile_sha256: str
    operator_sha256: str
    metric_sha256: str
    active_rank: int
    nullspace_sha256: str
    W_incident: QiInterval
    W_reflected: QiInterval
    W_transmitted: QiInterval
    W_absorbed: QiInterval
    closure_residual: QiInterval
    closure_bound: float
    pre_state_sha256: str
    post_state_sha256: str
    permeability_profile_sha256: str
    work_rows: Mapping[str, Mapping[str, Any]]
    work_linkage: tuple[str, ...]
    raw_work_sha256: str
    replay_identity_sha256: str
    status: str = "ACCEPTED"
    self_sha256: str = ""

    def __post_init__(self) -> None:
        _int("step", self.step); _text("head hash", self.head_sha256); _text("port_id", self.port_id); _text("interface_id", self.interface_id)
        if self.receipt_id:
            _text("receipt_id", self.receipt_id)
        else:
            object.__setattr__(self, "receipt_id", "")
        if self.kind not in {"internal", "external"} or self.scale_geometry_mode not in SCALE_GEOMETRY_MODE_IDS or self.orientation not in {-1, 1}:
            raise ScatteringError("invalid receipt identity")
        if self.kind == "internal" and (not isinstance(self.source_scale, int) or not isinstance(self.target_scale, int) or self.source_scale < 0 or self.target_scale < 0 or self.source_scale == self.target_scale):
            raise ScatteringError("internal receipt needs source/target")
        if self.kind == "external" and (self.source_scale is not None or self.target_scale is not None):
            raise ScatteringError("external receipt cannot claim a scale endpoint")
        _text("trajectory", self.incoming_trajectory_sha256); _text("stage", self.stage_id)
        object.__setattr__(self, "tick_interval", _interval("tick", self.tick_interval))
        if not self.tick_interval.is_exact:
            raise ScatteringError("tick must be exact")
        object.__setattr__(self, "active_rank", _int("active rank", self.active_rank)); object.__setattr__(self, "closure_bound", _nonnegative("closure bound", self.closure_bound))
        for name in ("profile_sha256", "operator_sha256", "metric_sha256", "nullspace_sha256", "pre_state_sha256", "post_state_sha256", "permeability_profile_sha256", "replay_identity_sha256"):
            _text(name, getattr(self, name))
        channels = []
        for name in SCATTERING_WORK_CHANNELS:
            value = _interval(name, getattr(self, name))
            if not value.resolved or value.lower < 0:
                raise ScatteringError(f"{name} must be resolved non-negative interval")
            object.__setattr__(self, name, value); channels.append(value)
        residual = _interval("closure residual", self.closure_residual); object.__setattr__(self, "closure_residual", residual)
        rows = _rows(self.interface_id, self.work_rows); object.__setattr__(self, "work_rows", rows)
        ids = tuple(str(row["row_id"]) for row in rows.values()); linkage = tuple(self.work_linkage) if self.work_linkage else ids
        if set(linkage) != set(ids) or len(linkage) != len(set(linkage)):
            raise ScatteringError("work linkage must contain each row exactly once")
        object.__setattr__(self, "work_linkage", linkage)
        digest = _work_hash(rows)
        if self.raw_work_sha256 and self.raw_work_sha256 != digest:
            raise ScatteringError("raw work hash mismatch")
        object.__setattr__(self, "raw_work_sha256", digest); _closure(channels, residual, self.closure_bound)
        expected_id = _hash({"interface_id": self.interface_id, "port_id": self.port_id, "step": self.step, "trajectory": self.incoming_trajectory_sha256, "raw_work_sha256": digest, "orientation": self.orientation, "source_scale": self.source_scale, "target_scale": self.target_scale}, "cassi.qi-flow-scattering-receipt-id.v1")
        if self.receipt_id:
            if self.receipt_id != expected_id:
                raise ScatteringError("receipt identity mismatch")
        else:
            object.__setattr__(self, "receipt_id", expected_id)
        if self.status not in {"ACCEPTED", "REJECTED"}:
            raise ScatteringError("invalid receipt status")
        expected_self = _hash(self.payload(), QI_SCATTERING_RECEIPT_DOMAIN)
        if self.self_sha256:
            _text("receipt self hash", self.self_sha256)
            if self.self_sha256 != expected_self:
                raise ScatteringError("receipt self identity mismatch")
        else:
            object.__setattr__(self, "self_sha256", expected_self)

    @property
    def schema(self) -> str:
        return QI_SCATTERING_RECEIPT_SCHEMA

    @property
    def residual_interval(self) -> QiInterval:
        return self.closure_residual
    def payload(self) -> dict[str, Any]:
        return {"schema": QI_SCATTERING_RECEIPT_SCHEMA, "receipt_id": self.receipt_id, "step": self.step, "head_sha256": self.head_sha256, "port_id": self.port_id, "interface_id": self.interface_id, "kind": self.kind, "scale_geometry_mode": self.scale_geometry_mode, "source_scale": self.source_scale, "target_scale": self.target_scale, "orientation": self.orientation, "incoming_trajectory_sha256": self.incoming_trajectory_sha256, "stage_id": self.stage_id, "tick_interval": self.tick_interval.payload(), "profile_sha256": self.profile_sha256, "operator_sha256": self.operator_sha256, "metric_sha256": self.metric_sha256, "active_rank": self.active_rank, "nullspace_sha256": self.nullspace_sha256, "W_incident": self.W_incident.payload(), "W_reflected": self.W_reflected.payload(), "W_transmitted": self.W_transmitted.payload(), "W_absorbed": self.W_absorbed.payload(), "closure_residual": self.closure_residual.payload(), "closure_bound": finite_bits(self.closure_bound), "pre_state_sha256": self.pre_state_sha256, "post_state_sha256": self.post_state_sha256, "permeability_profile_sha256": self.permeability_profile_sha256, "work_rows": {channel: {key: value.payload() if isinstance(value, QiInterval) else _plain(value) for key, value in row.items() if key != "volatile_telemetry"} for channel, row in self.work_rows.items()}, "work_linkage": list(self.work_linkage), "raw_work_sha256": self.raw_work_sha256, "replay_identity_sha256": self.replay_identity_sha256, "status": self.status}

    def to_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(self.payload() | {"self_sha256": self.self_sha256})

    def __getitem__(self, key: str) -> Any:
        return self.payload()[key]

    def with_orientation_reversed(self) -> "QiScatteringReceipt":
        """Return a new receipt with signed direction and internal endpoints reversed."""
        return QiScatteringReceipt(
            "",
            self.step,
            self.head_sha256,
            self.port_id,
            self.interface_id,
            self.kind,
            self.scale_geometry_mode,
            self.target_scale if self.kind == "internal" else self.source_scale,
            self.source_scale if self.kind == "internal" else self.target_scale,
            -self.orientation,
            self.incoming_trajectory_sha256,
            self.stage_id,
            self.tick_interval,
            self.profile_sha256,
            self.operator_sha256,
            self.metric_sha256,
            self.active_rank,
            self.nullspace_sha256,
            self.W_incident,
            self.W_reflected,
            self.W_transmitted,
            self.W_absorbed,
            self.closure_residual,
            self.closure_bound,
            self.pre_state_sha256,
            self.post_state_sha256,
            self.permeability_profile_sha256,
            self.work_rows,
            self.work_linkage,
            self.raw_work_sha256,
            self.replay_identity_sha256,
            self.status,
        )


def build_qi_scattering_receipt(*, port: QiPortDescriptor | Mapping[str, Any], step: int, head_sha256: str, incoming_trajectory_sha256: str, stage_id: str, tick_interval: QiInterval | float, profile_sha256: str, operator_sha256: str, metric_sha256: str, active_rank: int, nullspace_sha256: str, pre_state_sha256: str, post_state_sha256: str, work_rows: Mapping[str, Any] | None = None, W_incident: Any = None, W_reflected: Any = None, W_transmitted: Any = None, W_absorbed: Any = None, closure_residual: Any = None, closure_bound: float | None = None, permeability_profile_sha256: str = "", replay_identity_sha256: str = "", work_linkage: Sequence[str] = (), volatile_telemetry: Any = None, receipt_id: str = "") -> QiScatteringReceipt:
    del volatile_telemetry
    descriptor = _port(port)
    if work_rows is None:
        if any(value is None for value in (W_incident, W_reflected, W_transmitted, W_absorbed)):
            raise ScatteringError("all four work channels are required")
        work_rows = {"W_incident": W_incident, "W_reflected": W_reflected, "W_transmitted": W_transmitted, "W_absorbed": W_absorbed}
    rows = _rows(descriptor.interface_id, work_rows)
    channels = {name: _interval(name, rows[name]["interval"]) for name in SCATTERING_WORK_CHANNELS}
    computed = _subtract(*(channels[name] for name in SCATTERING_WORK_CHANNELS))
    residual = computed if closure_residual is None else _interval("closure residual", closure_residual)
    bound = max(abs(computed.lower), abs(computed.upper)) if closure_bound is None else _nonnegative("closure bound", closure_bound)
    digest = _work_hash(rows)
    identities = {
        "profile_sha256": profile_sha256 or descriptor.profile_sha256,
        "operator_sha256": operator_sha256 or descriptor.operator_sha256,
        "metric_sha256": metric_sha256 or descriptor.metric_sha256,
        "permeability_profile_sha256": permeability_profile_sha256 or descriptor.permeability_profile_sha256,
    }
    for name, value in identities.items():
        _text(name, value)
    if profile_sha256 and profile_sha256 != descriptor.profile_sha256 or operator_sha256 and operator_sha256 != descriptor.operator_sha256 or metric_sha256 and metric_sha256 != descriptor.metric_sha256 or permeability_profile_sha256 and permeability_profile_sha256 != descriptor.permeability_profile_sha256:
        raise ScatteringError("receipt identity disagrees with port descriptor")
    replay_identity_sha256 = replay_identity_sha256 or digest
    _text("replay identity", replay_identity_sha256)
    identity_payload = {"interface_id": descriptor.interface_id, "port_id": descriptor.port_id, "step": step, "trajectory": incoming_trajectory_sha256, "raw_work_sha256": digest, "orientation": descriptor.orientation, "source_scale": descriptor.source_scale, "target_scale": descriptor.target_scale}
    if not receipt_id:
        receipt_id = _hash(identity_payload, "cassi.qi-flow-scattering-receipt-id.v1")
    return QiScatteringReceipt(receipt_id, step, head_sha256, descriptor.port_id, descriptor.interface_id, descriptor.kind, descriptor.scale_geometry_mode, descriptor.source_scale, descriptor.target_scale, descriptor.orientation, incoming_trajectory_sha256, stage_id, _interval("tick", tick_interval), identities["profile_sha256"], identities["operator_sha256"], identities["metric_sha256"], active_rank, nullspace_sha256, channels["W_incident"], channels["W_reflected"], channels["W_transmitted"], channels["W_absorbed"], residual, bound, pre_state_sha256, post_state_sha256, identities["permeability_profile_sha256"], rows, tuple(work_linkage), digest, replay_identity_sha256, "ACCEPTED")


def _validate_port_receipt_identity(descriptor: QiPortDescriptor, receipt: QiScatteringReceipt, *, reversed_internal: bool = False) -> None:
    source, target, orientation = descriptor.source_scale, descriptor.target_scale, descriptor.orientation
    if reversed_internal:
        source, target, orientation = target, source, -orientation
    expected = (descriptor.port_id, descriptor.interface_id, descriptor.kind, descriptor.scale_geometry_mode, source, target, orientation, descriptor.profile_sha256, descriptor.operator_sha256, descriptor.metric_sha256, descriptor.permeability_profile_sha256)
    actual = (receipt.port_id, receipt.interface_id, receipt.kind, receipt.scale_geometry_mode, receipt.source_scale, receipt.target_scale, receipt.orientation, receipt.profile_sha256, receipt.operator_sha256, receipt.metric_sha256, receipt.permeability_profile_sha256)
    if actual != expected:
        raise ScatteringError("receipt identity disagrees with declared port")


def _validate_work_replay(receipt: QiScatteringReceipt, raw_work_rows: Mapping[str, Any]) -> None:
    replay_rows = _rows(receipt.interface_id, raw_work_rows)
    if _plain(replay_rows) != _plain(receipt.work_rows) or _work_hash(replay_rows) != receipt.raw_work_sha256:
        raise ScatteringError("mutated raw work row")
    channels = tuple(_interval(name, replay_rows[name]["interval"]) for name in SCATTERING_WORK_CHANNELS)
    _closure(channels, receipt.closure_residual, receipt.closure_bound)
    if tuple(channels) != tuple(getattr(receipt, name) for name in SCATTERING_WORK_CHANNELS):
        raise ScatteringError("replayed work partition disagrees with receipt")


def validate_scattering_receipt(receipt: QiScatteringReceipt, *, port: QiPortDescriptor | Mapping[str, Any] | None = None, raw_work_rows: Mapping[str, Any] | None = None) -> None:
    if not isinstance(receipt, QiScatteringReceipt) or _hash(receipt.payload(), QI_SCATTERING_RECEIPT_DOMAIN) != receipt.self_sha256:
        raise ScatteringError("scattering receipt self hash mismatch/type")
    if raw_work_rows is not None:
        _validate_work_replay(receipt, raw_work_rows)
    if port is not None:
        descriptor = _port(port)
        _validate_port_receipt_identity(descriptor, receipt)
    _closure((receipt.W_incident, receipt.W_reflected, receipt.W_transmitted, receipt.W_absorbed), receipt.closure_residual, receipt.closure_bound)


def replay_scattering_receipt(receipt: QiScatteringReceipt, raw_work_rows: Mapping[str, Any], *, raw_trajectory_sha256: str | None = None, volatile_telemetry: Any = None) -> QiScatteringReceipt:
    del volatile_telemetry
    if raw_trajectory_sha256 is not None and raw_trajectory_sha256 != receipt.incoming_trajectory_sha256:
        raise ScatteringError("raw trajectory identity mismatch")
    validate_scattering_receipt(receipt, raw_work_rows=raw_work_rows)
    return receipt

def pair_internal_scattering_receipts(source_receipt: QiScatteringReceipt, target_receipt: QiScatteringReceipt) -> None:
    validate_scattering_receipt(source_receipt); validate_scattering_receipt(target_receipt)
    if source_receipt.kind != "internal" or target_receipt.kind != "internal" or source_receipt.interface_id != target_receipt.interface_id or source_receipt.port_id != target_receipt.port_id or source_receipt.source_scale != target_receipt.target_scale or source_receipt.target_scale != target_receipt.source_scale or source_receipt.orientation != -target_receipt.orientation or source_receipt.step != target_receipt.step or source_receipt.tick_interval != target_receipt.tick_interval or source_receipt.incoming_trajectory_sha256 != target_receipt.incoming_trajectory_sha256 or source_receipt.stage_id != target_receipt.stage_id or source_receipt.scale_geometry_mode != target_receipt.scale_geometry_mode or source_receipt.profile_sha256 != target_receipt.profile_sha256 or source_receipt.operator_sha256 != target_receipt.operator_sha256 or source_receipt.metric_sha256 != target_receipt.metric_sha256 or source_receipt.permeability_profile_sha256 != target_receipt.permeability_profile_sha256:
        raise ScatteringError("internal paired exchange identity does not cancel")
    if source_receipt.W_transmitted != target_receipt.W_transmitted or source_receipt.W_absorbed != QiInterval.exact(0) or target_receipt.W_absorbed != QiInterval.exact(0):
        raise ScatteringError("internal paired exchange does not cancel")
    source_link = str(source_receipt.work_rows["W_transmitted"]["row_id"]); target_link = str(target_receipt.work_rows["W_transmitted"]["row_id"])
    if source_link != target_link or set(source_receipt.work_linkage) & set(target_receipt.work_linkage) != {source_link}:
        raise ScatteringError("internal transmitted work must have one shared linkage")


def validate_scattering_receipt_set(receipts: Sequence[QiScatteringReceipt], *, declared_interfaces: Sequence[QiPortDescriptor | Mapping[str, Any]], external_ports: Sequence[QiPortDescriptor | Mapping[str, Any]] = ()) -> None:
    rows, interfaces, ports = tuple(receipts), tuple(_port(item) for item in declared_interfaces), tuple(_port(item) for item in external_ports)
    if not rows or any(not isinstance(item, QiScatteringReceipt) for item in rows) or len({item.interface_id for item in interfaces}) != len(interfaces) or len({item.port_id for item in ports}) != len(ports):
        raise ScatteringError("receipt declarations are duplicated/empty")
    if set(item.interface_id for item in interfaces) & set(item.port_id for item in ports):
        raise ScatteringError("internal and external receipt namespaces collide")
    if {item.interface_id for item in rows if item.kind == "internal"} != {item.interface_id for item in interfaces} or {item.port_id for item in rows if item.kind == "external"} != {item.port_id for item in ports}:
        raise ScatteringError("receipt declarations do not cover every declared interface/port")
    if len({item.receipt_id for item in rows}) != len(rows):
        raise ScatteringError("duplicate receipt identity")
    paired_links: set[str] = set()
    for descriptor in interfaces:
        pair = [item for item in rows if item.kind == "internal" and item.interface_id == descriptor.interface_id]
        if len(pair) != 2:
            raise ScatteringError("internal interface needs both directional receipts")
        forward = [item for item in pair if (item.source_scale, item.target_scale, item.orientation) == (descriptor.source_scale, descriptor.target_scale, descriptor.orientation)]
        reverse = [item for item in pair if (item.source_scale, item.target_scale, item.orientation) == (descriptor.target_scale, descriptor.source_scale, -descriptor.orientation)]
        if len(forward) != 1 or len(reverse) != 1:
            raise ScatteringError("internal interface direction is missing/transposed")
        _validate_port_receipt_identity(descriptor, forward[0]); _validate_port_receipt_identity(descriptor, reverse[0], reversed_internal=True)
        pair_internal_scattering_receipts(forward[0], reverse[0])
        paired_links.add(str(forward[0].work_rows["W_transmitted"]["row_id"]))
    for descriptor in ports:
        pair = [item for item in rows if item.kind == "external" and item.port_id == descriptor.port_id]
        if len(pair) != 1:
            raise ScatteringError("external port needs exactly one receipt")
        validate_scattering_receipt(pair[0], port=descriptor)
    linkage = [str(item) for receipt in rows for item in receipt.work_linkage]
    counts = {item: linkage.count(item) for item in set(linkage)}
    if any(count != (2 if item in paired_links else 1) for item, count in counts.items()) or any(item not in counts for item in paired_links):
        raise ScatteringError("work row linked more than once or partition is incomplete")


def validate_cross_scale_law(law: Any) -> Any:
    if law is None or not isinstance(getattr(law, "law_id", None), str) or not law.law_id or not callable(getattr(law, "energy", None)) or not callable(getattr(law, "additional_force", None)):
        raise ScatteringError("public QiCrossScaleLaw law_id/energy/additional_force required")
    return law


__all__ = [name for name in globals() if name.startswith("Qi") or name.startswith("QI_") or name in {"CANDIDATE_MODE_IDS", "SCALE_GEOMETRY_MODE_IDS", "SELECTOR_ID", "PERIODIC_FFT2_IDENTITY", "CONTROLLER_GRAMMAR_ID", "PYRAMID_ACTIVE_SHAPES", "SCATTERING_WORK_CHANNELS", "build_qi_scattering_receipt", "build_scale_geometry_comparison", "build_topology_codebook_evidence", "declare_scale_interfaces", "materialize_candidate_operator_data", "pair_internal_scattering_receipts", "replay_scattering_receipt", "select_candidate_mode", "select_scale_geometry", "topology_witness_hash", "validate_cross_scale_law", "validate_scattering_receipt", "validate_scattering_receipt_set", "validate_scale_geometry_comparison", "validate_topology_codebook_evidence", "validate_zero_clock_remap_preservation"}]
