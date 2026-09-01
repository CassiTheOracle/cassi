"""W6B/G6C endpoint causal-capacity evidence.

This module is deliberately a data/evidence layer.  It accepts frozen identities,
intervention descriptions, and an ``advance`` protocol; it does not import a
runtime, provider, world server, or learned model.  Every accepted endpoint is
replayed from one predecessor through the declared canonical horizon and carries
raw trajectory/table hashes for an independent verifier.
"""
from __future__ import annotations
from dataclasses import dataclass, field, fields
import hashlib
import math
import re
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Sequence

from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes, finite_bits, finite_float


SCHEMA = "cassi.qi-flow-endpoint-capacity.v1"
BOUNDARY_TRANSFER_SCHEMA = "cassi.qi-flow-boundary-transfer.v1"
MULTIMODAL_BINDING_SCHEMA = "cassi.qi-flow-multimodal-binding.v1"
RAW_DOMAIN = "cassi.qi-flow-endpoint-raw.v1"
TRANSFER_DOMAIN = BOUNDARY_TRANSFER_SCHEMA
BINDING_DOMAIN = MULTIMODAL_BINDING_SCHEMA
ZERO_SHA256 = "0" * 64
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TARGET_KINDS = ("boundary_observation", "text_output", "action", "applied_effect")
_TRANSFER_CONTROL_KINDS = (
    "source_suppressed", "disconnected_path", "c_only", "d_only", "matched_cd", "phase_current_reversal"
)
_BINDING_CONTROL_KINDS = (
    "modality_alone", "shuffled", "lagged", "mirrored", "transfer_permuted",
    "phase_current_reversed", "class_a", "matched_energy_opposite_current", "equal_work_null"
)
_CONTROL_KINDS = _TRANSFER_CONTROL_KINDS + _BINDING_CONTROL_KINDS + (
    "fading_retention", "source_free_residence", "field_state_shuffle",
    "topology_preserving_permutation", "source_action_dissociation",
    "replay", "proposal_only", "reset_counted_as_acquisition",
    "negative_work", "unknown_work",
)
_PARTITION_KINDS = ("passive_channels", "proposed_actuation", "acknowledged_applied_effect", "residual_return")


class EndpointCapacityError(ValueError):
    """Raised when endpoint evidence is incomplete, noncausal, or noncanonical."""


def _fail(message: str) -> None:
    raise EndpointCapacityError(message)


def _sha(value: Any, domain: str = SCHEMA) -> str:
    return canonical_hash(_plain(value), domain)


def _raw_sha(value: Any, domain: str = RAW_DOMAIN) -> str:
    raw = value if isinstance(value, bytes) else canonical_json_bytes(_plain(value))
    domain_bytes = domain.encode("utf-8")
    framed = len(domain_bytes).to_bytes(8, "big") + domain_bytes + len(raw).to_bytes(8, "big") + raw
    return hashlib.sha256(framed).hexdigest()


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _require_sha(value: Any, name: str) -> str:
    if not _is_sha(value):
        _fail(f"{name} must be a lowercase SHA-256")
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if isinstance(value, bytes):
        return {"encoding": "raw-bytes-v1", "hex": value.hex()}
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        return finite_bits(value)
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    if hasattr(value, "payload"):
        return _plain(value.payload())
    _fail(f"unsupported evidence value {type(value).__name__}")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(v) for v in value)
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{name} must be a mapping")
    return value


def _text(value: Any, name: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value):
        _fail(f"{name} must be a nonempty string")
    if any(ord(c) < 0x20 for c in value):
        _fail(f"{name} contains a control character")
    return value


def _finite(value: Any, name: str) -> float:
    try:
        result = finite_float(value, name=name)
    except Exception as exc:
        _fail(str(exc))
    return result


def _interval(value: Any, name: str, *, unit: str = "normalized", nonnegative: bool = False) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        if not {"value", "lower", "upper"}.issubset(value):
            _fail(f"{name} must contain value/lower/upper")
        raw_value, raw_lower, raw_upper = value["value"], value["lower"], value["upper"]
        actual_unit = value.get("unit", unit)
    else:
        raw_value = raw_lower = raw_upper = value
        actual_unit = unit
    actual_unit = _text(actual_unit, f"{name}.unit")
    v = _finite(raw_value, f"{name}.value")
    lo = _finite(raw_lower, f"{name}.lower")
    hi = _finite(raw_upper, f"{name}.upper")
    if lo > v or v > hi:
        _fail(f"{name} bounds do not enclose value")
    if nonnegative and lo < 0.0:
        _fail(f"{name} lower bound is negative")
    return MappingProxyType({"value": finite_bits(v), "lower": finite_bits(lo), "upper": finite_bits(hi), "unit": actual_unit})


def _scalar(value: Any, name: str, *, nonnegative: bool = False) -> Mapping[str, Any]:
    item = _interval(value, name, nonnegative=nonnegative)
    return MappingProxyType({k: item[k] for k in ("value", "lower", "upper")})


def _number(item: Mapping[str, Any], key: str = "value") -> float:
    return _finite(item[key], key)


def _work(value: Any, name: str, *, nonnegative: bool = True) -> Mapping[str, Any]:
    item = _interval(value, name, unit="joule", nonnegative=nonnegative)
    return item


def _work_value(value: Mapping[str, Any]) -> float:
    return _number(value)


def _horizon(value: Any, name: str = "horizon") -> Mapping[str, Any]:
    value = _mapping(value, name)
    if "n" in value or "d" in value:
        n, d = value.get("n"), value.get("d")
    else:
        n, d = value.get("num"), value.get("den")
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        _fail(f"{name}.n must be a positive integer")
    if isinstance(d, bool) or not isinstance(d, int) or d < 1:
        _fail(f"{name}.d must be a positive integer")
    if math.gcd(n, d) != 1:
        _fail(f"{name} must be reduced")
    result = {"n": n, "d": d}
    if "unit" in value:
        result["unit"] = _text(value["unit"], f"{name}.unit")
    return MappingProxyType(result)


def _horizon_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return int(left["n"]) == int(right["n"]) and int(left["d"]) == int(right["d"]) and left.get("unit", "tick") == right.get("unit", "tick")


def _rational_delay(value: Any, name: str = "delay") -> Mapping[str, int]:
    result = dict(_horizon(value, name))
    if result["n"] < 1:
        _fail(f"{name} must be positive")
    return MappingProxyType({k: result[k] for k in ("n", "d")})


def _forbidden(value: Any, path: str = "input") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if (
                key_text in {
                    "label", "labels", "semantic", "semantic_label", "task",
                    "task_label", "task_id", "meaning", "intent",
                    "class_label", "target_label", "category_label",
                    "future_observation", "future_observations",
                    "candidate_consequence", "candidate_consequences",
                    "predicted_consequence", "post_hoc_consequence",
                }
                or key_text.endswith(("_semantic", "_task", "_label"))
            ):
                _fail(f"{path}.{key} is not causal evidence")
            _forbidden(item, f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _forbidden(item, f"{path}[{index}]")


def _sequence(value: Any, name: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, (tuple, list)):
        _fail(f"{name} must be a finite sequence")
    return tuple(_freeze(item) for item in value)


def _matrix(value: Any, name: str) -> tuple[tuple[float, ...], ...]:
    if value is None:
        return ((1.0,),)
    if not isinstance(value, (tuple, list)) or not value:
        _fail(f"{name} must be a nonempty matrix")
    rows = []
    width = None
    for i, row in enumerate(value):
        if not isinstance(row, (tuple, list)) or not row:
            _fail(f"{name}[{i}] must be a nonempty row")
        converted = tuple(_finite(item, f"{name}[{i}]") for item in row)
        width = len(converted) if width is None else width
        if len(converted) != width:
            _fail(f"{name} is ragged")
        rows.append(converted)
    return tuple(rows)


def _rank(matrix: Sequence[Sequence[float]], tol: float = 1e-10) -> int:
    rows = [list(map(float, row)) for row in matrix]
    if not rows:
        return 0
    m, n = len(rows), len(rows[0])
    rank = 0
    for col in range(n):
        pivot = max(range(rank, m), key=lambda i: abs(rows[i][col]), default=rank)
        if pivot >= m or abs(rows[pivot][col]) <= tol:
            continue
        rows[rank], rows[pivot] = rows[pivot], rows[rank]
        scale = rows[rank][col]
        rows[rank] = [x / scale for x in rows[rank]]
        for i in range(m):
            if i != rank and abs(rows[i][col]) > tol:
                factor = rows[i][col]
                rows[i] = [a - factor * b for a, b in zip(rows[i], rows[rank])]
        rank += 1
        if rank == m:
            break
    return rank


def _spectrum(matrix: Sequence[Sequence[float]]) -> tuple[float, ...]:
    """Deterministic singular-value bounds without a numerical-runtime import."""
    if not matrix:
        return ()
    cols = len(matrix[0])
    gram = [[sum(float(row[i]) * float(row[j]) for row in matrix) for j in range(cols)] for i in range(cols)]
    for _ in range(64):
        p, q, magnitude = 0, 0, 0.0
        for i in range(cols):
            for j in range(i + 1, cols):
                if abs(gram[i][j]) > magnitude:
                    p, q, magnitude = i, j, abs(gram[i][j])
        if magnitude <= 1e-12:
            break
        theta = 0.5 * math.atan2(2.0 * gram[p][q], gram[p][p] - gram[q][q])
        c, s = math.cos(theta), math.sin(theta)
        for k in range(cols):
            gram[p][k], gram[q][k] = c * gram[p][k] - s * gram[q][k], s * gram[p][k] + c * gram[q][k]
        for k in range(cols):
            gram[k][p], gram[k][q] = c * gram[k][p] - s * gram[k][q], s * gram[k][p] + c * gram[k][q]
    return tuple(sorted((math.sqrt(max(0.0, gram[i][i])) for i in range(cols)), reverse=True))


def _nullspace_hash(matrix: Sequence[Sequence[float]], rank: int | None = None) -> str:
    rank = _rank(matrix) if rank is None else rank
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    return _sha({"matrix": [[finite_bits(float(v)) for v in row] for row in matrix], "rank": rank, "dimension": max(0, cols - rank)}, "cassi.qi-flow-endpoint-nullspace.v1")


def _raw_array(matrix: Sequence[Sequence[float]]) -> Mapping[str, Any]:
    flat = [float(v) for row in matrix for v in row]
    raw = b"".join(float(v).hex().encode("ascii") + b"\n" for v in flat)
    return MappingProxyType({
        "encoding": "little-endian-array-v1", "dtype": "f64_le",
        "shape": (len(matrix), len(matrix[0]) if matrix else 0), "byte_count": len(raw), "sha256": _raw_sha(raw, "cassi.qi-flow-endpoint-array.v1")
    })


def _descriptor_hash(value: Any, fallback: str) -> str:
    if _is_sha(value):
        return value
    return _sha(value if value is not None else fallback, "cassi.qi-flow-endpoint-descriptor.v1")


def _partition(value: Any, incident: Mapping[str, Any], name: str) -> Mapping[str, Mapping[str, Any]]:
    if value is None:
        rows = {key: _work(0.0, f"{name}.{key}") for key in _PARTITION_KINDS}
        rows["passive_channels"] = _work(incident, f"{name}.passive_channels")
    else:
        value = _mapping(value, name)
        if set(value) != set(_PARTITION_KINDS):
            _fail(f"{name} must have exactly {list(_PARTITION_KINDS)}")
        rows = {key: _work(value[key], f"{name}.{key}") for key in _PARTITION_KINDS}
    total = sum(_work_value(item) for item in rows.values())
    incident_value = _work_value(incident)
    if abs(total - incident_value) > 1e-8 * max(1.0, abs(incident_value)):
        _fail(f"{name} does not conserve incident work")
    return MappingProxyType(rows)


def _semantic_parents(value: Any, profile: Mapping[str, Any]) -> tuple[Mapping[str, str], ...]:
    source = value if value is not None else profile.get("consumed_semantic_subhashes", ())
    rows = []
    for row in source:
        row = _mapping(row, "consumed_semantic_subhashes")
        name = _text(row.get("name"), "semantic parent name")
        rows.append(MappingProxyType({"name": name, "sha256": _require_sha(row.get("sha256"), f"semantic parent {name}")}))
    if len(rows) != 3:
        _fail("endpoint evidence requires exactly three semantic parents")
    if len({row["name"] for row in rows}) != 3:
        _fail("semantic parents are duplicated")
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class QiEndpointCapacityProfile:
    """Frozen selector and dependency identities for endpoint evidence."""

    profile_sha256: str = ZERO_SHA256
    capacity_ladder_sha256: str = ZERO_SHA256
    controller_grammar_sha256: str = ZERO_SHA256
    physical_horizon: Mapping[str, Any] = field(default_factory=lambda: {"n": 1, "d": 1, "unit": "tick"})
    predecessor_head_sha256: str = ZERO_SHA256
    predecessor_state_sha256: str = ZERO_SHA256
    source_coordinate_ids: tuple[str, ...] = ()
    target_coordinate_ids: tuple[str, ...] = ()
    source_port_ids: Mapping[str, str] = field(default_factory=dict)
    target_kinds: tuple[str, ...] = _TARGET_KINDS
    target_port_ids: Mapping[str, str] = field(default_factory=dict)
    target_descriptor_sha256s: Mapping[str, str] = field(default_factory=dict)
    coordinate_geometric: Mapping[str, bool] = field(default_factory=dict)
    reachability_matrices: Mapping[str, Any] = field(default_factory=dict)
    observability_matrices: Mapping[str, Any] = field(default_factory=dict)
    uncertainty_thresholds: Mapping[str, Any] = field(default_factory=dict)
    null_thresholds: Mapping[str, Any] = field(default_factory=dict)
    consumed_semantic_subhashes: tuple[Mapping[str, str], ...] = ()
    contract_root_sha256: str = ZERO_SHA256
    clock_sha256: str = ZERO_SHA256
    body_frame_sha256: str = ZERO_SHA256
    ordinary_packet_set_sha256: str = ZERO_SHA256
    event_order_sha256: str = ZERO_SHA256
    topology_sha256: str = ZERO_SHA256
    forgetting_sha256: str = ZERO_SHA256
    retained_coordinates: tuple[str, ...] = ()
    reusable_coordinates: tuple[str, ...] = ()
    required_control_kinds: tuple[str, ...] = _CONTROL_KINDS
    source_modalities: Mapping[str, Sequence[str]] = field(default_factory=dict)
    control_specs: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("profile_sha256", "capacity_ladder_sha256", "controller_grammar_sha256", "predecessor_head_sha256", "predecessor_state_sha256", "contract_root_sha256", "clock_sha256", "body_frame_sha256", "ordinary_packet_set_sha256", "event_order_sha256", "topology_sha256", "forgetting_sha256"):
            _require_sha(getattr(self, name), f"profile.{name}")
        horizon = _horizon(self.physical_horizon, "profile.physical_horizon")
        object.__setattr__(self, "physical_horizon", horizon)
        sources = tuple(_text(item, "source coordinate") for item in self.source_coordinate_ids)
        targets = tuple(_text(item, "target coordinate") for item in self.target_coordinate_ids)
        if len(set(sources)) != len(sources) or len(set(targets)) != len(targets):
            _fail("profile coordinates are duplicated")
        if not sources:
            _fail("profile has no source coordinates")
        if not targets:
            _fail("profile has no target coordinates")
        kinds = tuple(_text(item, "target kind") for item in self.target_kinds)
        if not set(kinds) <= set(_TARGET_KINDS) or not kinds:
            _fail("profile target kinds are invalid")
        if len(set(kinds)) != len(kinds):
            _fail("profile target kinds are duplicated")
        source_ports = _mapping(self.source_port_ids, "profile.source_port_ids")
        target_ports = _mapping(self.target_port_ids, "profile.target_port_ids")
        descriptors = _mapping(self.target_descriptor_sha256s, "profile.target_descriptor_sha256s")
        geometric = _mapping(self.coordinate_geometric, "profile.coordinate_geometric")
        reachability = _mapping(self.reachability_matrices, "profile.reachability_matrices")
        observability = _mapping(self.observability_matrices, "profile.observability_matrices")
        missing_sources = [coordinate for coordinate in sources if coordinate not in source_ports]
        missing_targets = [coordinate for coordinate in targets if coordinate not in target_ports or coordinate not in descriptors or coordinate not in geometric or coordinate not in reachability or coordinate not in observability]
        if missing_sources:
            _fail(f"profile source ports missing {missing_sources}")
        if missing_targets:
            _fail(f"profile target operators/descriptors missing {missing_targets}")
        for coordinate in targets:
            if not isinstance(geometric[coordinate], bool):
                _fail(f"profile geometric flag for {coordinate} must be boolean")
            _matrix(reachability[coordinate], f"profile.reachability.{coordinate}")
            _matrix(observability[coordinate], f"profile.observability.{coordinate}")
            _require_sha(descriptors[coordinate], f"profile.target_descriptor_sha256s.{coordinate}")
        parents = _semantic_parents(self.consumed_semantic_subhashes, {})
        required_parents = {"state_contract_sha256", "boundary_action_sha256", "backend_capacity_sha256"}
        if {row["name"] for row in parents} != required_parents:
            _fail("profile semantic parents do not match endpoint contract")
        object.__setattr__(self, "consumed_semantic_subhashes", parents)
        object.__setattr__(self, "source_coordinate_ids", sources)
        object.__setattr__(self, "target_coordinate_ids", targets)
        object.__setattr__(self, "target_kinds", kinds)
        object.__setattr__(self, "source_port_ids", _freeze(source_ports))
        object.__setattr__(self, "target_port_ids", _freeze(target_ports))
        object.__setattr__(self, "target_descriptor_sha256s", _freeze(descriptors))
        object.__setattr__(self, "coordinate_geometric", _freeze(geometric))
        object.__setattr__(self, "reachability_matrices", _freeze(reachability))
        object.__setattr__(self, "observability_matrices", _freeze(observability))
        object.__setattr__(self, "uncertainty_thresholds", _freeze(self.uncertainty_thresholds))
        object.__setattr__(self, "null_thresholds", _freeze(self.null_thresholds))
        retained = tuple(_text(item, "retained coordinate") for item in self.retained_coordinates)
        reusable = tuple(_text(item, "reusable coordinate") for item in self.reusable_coordinates)
        if not set(retained) <= set(targets) or not set(reusable) <= set(retained):
            _fail("profile retained/reusable coordinates are not nested targets")
        object.__setattr__(self, "retained_coordinates", retained)
        object.__setattr__(self, "reusable_coordinates", reusable)
        required_controls = tuple(_text(item, "required control kind") for item in self.required_control_kinds)
        if len(set(required_controls)) != len(required_controls) or not set(required_controls) <= set(_CONTROL_KINDS):
            _fail("profile required controls are invalid")
        object.__setattr__(self, "required_control_kinds", required_controls)
        object.__setattr__(self, "source_modalities", _freeze(self.source_modalities))
        object.__setattr__(self, "control_specs", _freeze(self.control_specs))

    @classmethod
    def from_dependencies(cls, **kwargs: Any) -> "QiEndpointCapacityProfile":
        """Construct from explicit W6A/W7-W11/W12R identity mappings."""
        return cls(**kwargs)

    def payload(self) -> Mapping[str, Any]:
        return {
            "profile_sha256": self.profile_sha256,
            "capacity_ladder_sha256": self.capacity_ladder_sha256,
            "controller_grammar_sha256": self.controller_grammar_sha256,
            "physical_horizon": _plain(self.physical_horizon),
            "predecessor_head_sha256": self.predecessor_head_sha256,
            "predecessor_state_sha256": self.predecessor_state_sha256,
            "source_coordinate_ids": list(self.source_coordinate_ids),
            "target_coordinate_ids": list(self.target_coordinate_ids),
            "target_kinds": list(self.target_kinds),
            "source_port_ids": _plain(self.source_port_ids),
            "target_port_ids": _plain(self.target_port_ids),
            "target_descriptor_sha256s": _plain(self.target_descriptor_sha256s),
            "coordinate_geometric": _plain(self.coordinate_geometric),
            "reachability_matrices": _plain(self.reachability_matrices),
            "observability_matrices": _plain(self.observability_matrices),
            "uncertainty_thresholds": _plain(self.uncertainty_thresholds),
            "null_thresholds": _plain(self.null_thresholds),
            "consumed_semantic_subhashes": _plain(self.consumed_semantic_subhashes),
            "contract_root_sha256": self.contract_root_sha256,
            "clock_sha256": self.clock_sha256,
            "body_frame_sha256": self.body_frame_sha256,
            "ordinary_packet_set_sha256": self.ordinary_packet_set_sha256,
            "event_order_sha256": self.event_order_sha256,
            "topology_sha256": self.topology_sha256,
            "forgetting_sha256": self.forgetting_sha256,
            "retained_coordinates": list(self.retained_coordinates),
            "reusable_coordinates": list(self.reusable_coordinates),
            "required_control_kinds": list(self.required_control_kinds),
            "source_modalities": _plain(self.source_modalities),
            "control_specs": _plain(self.control_specs),
        }

    @property
    def identity_sha256(self) -> str:
        return _sha(self.payload(), "cassi.qi-flow-endpoint-profile.v1")


@dataclass(frozen=True, slots=True)
class QiEndpointIntervention:
    """One finite, causal intervention at one declared endpoint."""

    intervention_id: str = ""
    source_coordinate_id: str = ""
    target_coordinate_id: str = ""
    target_kind: str = "boundary_observation"
    drives: tuple[Any, ...] = ()
    horizon: Mapping[str, Any] = field(default_factory=lambda: {"n": 1, "d": 1, "unit": "tick"})
    predecessor_state: Any = field(default_factory=dict)
    endpoint_state: Any = None
    trajectory: tuple[Any, ...] = ()
    incident_work: Any = field(default_factory=lambda: {"value": 1.0, "lower": 1.0, "upper": 1.0, "unit": "joule"})
    source_work: Any = None
    work_partition: Any = None
    reachability_matrix: Any = None
    observability_matrix: Any = None
    target_response: Any = 1.0
    null_response: Any = 0.0
    delayed_prediction_residual: Any = 1.0
    uncertainty: Any = 0.0
    delay: Mapping[str, Any] = field(default_factory=lambda: {"n": 1, "d": 1})
    committed: bool = True
    acknowledged: bool = True
    proposal: bool = False
    reset: bool = False
    control_kind: str = "treatment"
    controller_grammar_sha256: str = ZERO_SHA256
    predecessor_head_sha256: str = ZERO_SHA256
    drive_script_sha256: str = ""
    source_packet_sha256: str = ""
    source_descriptor_sha256: str = ""
    target_descriptor_sha256: str = ""
    target_operator_sha256: str = ""
    source_port_id: str = ""
    target_port_id: str = ""
    committed_consequence_sha256: str | None = None
    path_hashes: Mapping[str, str] = field(default_factory=dict)
    retention_state: str = "not_claimed"
    canonical_advance: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _text(self.intervention_id, "intervention_id")
        _text(self.source_coordinate_id, "source_coordinate_id")
        _text(self.target_coordinate_id, "target_coordinate_id")
        if self.target_kind not in _TARGET_KINDS:
            _fail("intervention target_kind is invalid")
        if self.control_kind not in ("treatment", *_CONTROL_KINDS):
            _fail("unknown intervention control kind")
        self_drives = _sequence(self.drives, "drives")
        self_trajectory = _sequence(self.trajectory, "trajectory")
        object.__setattr__(self, "drives", self_drives)
        object.__setattr__(self, "trajectory", self_trajectory)
        object.__setattr__(self, "horizon", _horizon(self.horizon, "intervention.horizon"))
        object.__setattr__(self, "delay", _rational_delay(self.delay))
        _forbidden(self.metadata, "metadata")
        if not all(isinstance(value, bool) for value in (self.committed, self.acknowledged, self.proposal, self.reset, self.canonical_advance)):
            _fail("intervention flags must be boolean")
        if self.retention_state not in ("not_claimed", "retained", "reusable", "forgotten"):
            _fail("intervention retention_state is invalid")
        for name in ("controller_grammar_sha256", "predecessor_head_sha256"):
            _require_sha(getattr(self, name), f"intervention {name}")
        for name in ("drive_script_sha256", "source_packet_sha256", "source_descriptor_sha256", "target_descriptor_sha256", "target_operator_sha256", "source_port_id", "target_port_id"):
            value = getattr(self, name)
            if value and name.endswith("_sha256"):
                _require_sha(value, f"intervention {name}")
            elif value:
                _text(value, f"intervention {name}")
        if self.committed_consequence_sha256 is not None:
            _require_sha(self.committed_consequence_sha256, "intervention committed consequence")
        if not isinstance(self.path_hashes, Mapping):
            _fail("intervention path_hashes must be a mapping")
        for name, value in self.path_hashes.items():
            _text(str(name), "intervention path hash name")
            _require_sha(value, f"intervention path_hashes.{name}")
        object.__setattr__(self, "path_hashes", _freeze(self.path_hashes))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "QiEndpointIntervention":
        _mapping(value, "intervention")
        _forbidden(value)
        data = dict(value)
        # The singular source/work names are schema names, not alternate APIs.
        if "source_work" in data and "incident_work" not in data:
            data["incident_work"] = data["source_work"]
        if "trajectory" in data and isinstance(data["trajectory"], list):
            data["trajectory"] = tuple(data["trajectory"])
        if "drives" in data and isinstance(data["drives"], list):
            data["drives"] = tuple(data["drives"])
        return cls(**data)

    def payload(self) -> Mapping[str, Any]:
        return {
            "intervention_id": self.intervention_id,
            "source_coordinate_id": self.source_coordinate_id,
            "target_coordinate_id": self.target_coordinate_id,
            "target_kind": self.target_kind,
            "drives": _plain(self.drives),
            "horizon": _plain(self.horizon),
            "predecessor_state": _plain(self.predecessor_state),
            "endpoint_state": _plain(self.endpoint_state),
            "trajectory": _plain(self.trajectory),
            "incident_work": _plain(self.incident_work),
            "source_work": _plain(self.source_work),
            "work_partition": _plain(self.work_partition),
            "reachability_matrix": _plain(self.reachability_matrix),
            "observability_matrix": _plain(self.observability_matrix),
            "target_response": _plain(self.target_response),
            "null_response": _plain(self.null_response),
            "delayed_prediction_residual": _plain(self.delayed_prediction_residual),
            "uncertainty": _plain(self.uncertainty),
            "delay": _plain(self.delay),
            "committed": self.committed,
            "acknowledged": self.acknowledged,
            "proposal": self.proposal,
            "reset": self.reset,
            "control_kind": self.control_kind,
            "controller_grammar_sha256": self.controller_grammar_sha256,
            "predecessor_head_sha256": self.predecessor_head_sha256,
            "drive_script_sha256": self.drive_script_sha256,
            "source_packet_sha256": self.source_packet_sha256,
            "source_descriptor_sha256": self.source_descriptor_sha256,
            "target_descriptor_sha256": self.target_descriptor_sha256,
            "target_operator_sha256": self.target_operator_sha256,
            "source_port_id": self.source_port_id,
            "target_port_id": self.target_port_id,
            "committed_consequence_sha256": self.committed_consequence_sha256,
            "path_hashes": _plain(self.path_hashes),
            "retention_state": self.retention_state,
            "canonical_advance": self.canonical_advance,
            "metadata": _plain(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class QiEndpointTransferRow:
    """Per-coordinate endpoint transfer and capacity classification."""

    source_coordinate_id: str = ""
    target_coordinate_id: str = ""
    target_kind: str = "boundary_observation"
    horizon: Mapping[str, Any] = field(default_factory=lambda: {"n": 1, "d": 1, "unit": "tick"})
    treatment_response_interval: Mapping[str, Any] = field(default_factory=lambda: _scalar(1.0, "response"))
    null_response_interval: Mapping[str, Any] = field(default_factory=lambda: _scalar(0.0, "null_response"))
    effect_interval: Mapping[str, Any] = field(default_factory=lambda: _scalar(1.0, "effect"))
    uncertainty_interval: Mapping[str, Any] = field(default_factory=lambda: _scalar(0.0, "uncertainty", nonnegative=True))
    delay: Mapping[str, Any] = field(default_factory=lambda: {"n": 1, "d": 1})
    incident_work_interval: Mapping[str, Any] = field(default_factory=lambda: _work(1.0, "incident"))
    source_work_interval: Mapping[str, Any] = field(default_factory=lambda: _work(1.0, "source"))
    work_partition: Mapping[str, Any] = field(default_factory=dict)
    reachability_matrix: tuple[tuple[float, ...], ...] = ((1.0,),)
    observability_matrix: tuple[tuple[float, ...], ...] = ((1.0,),)
    reachability_rank: int = 1
    observability_rank: int = 1
    reachability_spectrum: tuple[float, ...] = (1.0,)
    observability_spectrum: tuple[float, ...] = (1.0,)
    reachability_nullspace_sha256: str = ZERO_SHA256
    observability_nullspace_sha256: str = ZERO_SHA256
    geometric: bool = True
    reachable: bool = True
    observable: bool = True
    usable: bool = True
    retained: bool = False
    reusable: bool = False
    null_predicates: Mapping[str, bool] = field(default_factory=dict)
    committed_consequence_sha256: str | None = None
    trajectory_sha256: str = ZERO_SHA256
    endpoint_state_sha256: str = ZERO_SHA256
    predecessor_state_sha256: str = ZERO_SHA256
    path_hashes: Mapping[str, str] = field(default_factory=dict)
    control_kind: str = "treatment"
    excluded: bool = False

    def __post_init__(self) -> None:
        _text(self.source_coordinate_id, "transfer source_coordinate_id")
        _text(self.target_coordinate_id, "transfer target_coordinate_id")
        if self.target_kind not in _TARGET_KINDS:
            _fail("transfer target_kind is invalid")
        if self.control_kind not in ("treatment", *_CONTROL_KINDS):
            _fail("transfer control_kind is invalid")
        object.__setattr__(self, "horizon", _horizon(self.horizon, "transfer.horizon"))
        object.__setattr__(self, "delay", _rational_delay(self.delay, "transfer.delay"))
        for name in ("treatment_response_interval", "null_response_interval", "effect_interval"):
            object.__setattr__(self, name, _scalar(getattr(self, name), f"transfer.{name}"))
        object.__setattr__(self, "uncertainty_interval", _scalar(self.uncertainty_interval, "transfer.uncertainty", nonnegative=True))
        object.__setattr__(self, "incident_work_interval", _work(self.incident_work_interval, "transfer.incident_work"))
        object.__setattr__(self, "source_work_interval", _work(self.source_work_interval, "transfer.source_work"))
        object.__setattr__(self, "reachability_matrix", _matrix(self.reachability_matrix, "transfer.reachability_matrix"))
        object.__setattr__(self, "observability_matrix", _matrix(self.observability_matrix, "transfer.observability_matrix"))
        if not isinstance(self.reachability_rank, int) or isinstance(self.reachability_rank, bool) or self.reachability_rank < 0 or self.reachability_rank > min(len(self.reachability_matrix), len(self.reachability_matrix[0])):
            _fail("transfer reachability_rank is invalid")
        if not isinstance(self.observability_rank, int) or isinstance(self.observability_rank, bool) or self.observability_rank < 0 or self.observability_rank > min(len(self.observability_matrix), len(self.observability_matrix[0])):
            _fail("transfer observability_rank is invalid")
        object.__setattr__(self, "reachability_spectrum", tuple(_finite(v, "transfer.reachability_spectrum") for v in self.reachability_spectrum))
        object.__setattr__(self, "observability_spectrum", tuple(_finite(v, "transfer.observability_spectrum") for v in self.observability_spectrum))
        for name in ("reachability_nullspace_sha256", "observability_nullspace_sha256", "trajectory_sha256", "endpoint_state_sha256", "predecessor_state_sha256"):
            _require_sha(getattr(self, name), f"transfer.{name}")
        if self.committed_consequence_sha256 is not None:
            _require_sha(self.committed_consequence_sha256, "transfer.committed_consequence_sha256")
        if not isinstance(self.path_hashes, Mapping):
            _fail("transfer.path_hashes must be a mapping")
        for name, value in self.path_hashes.items():
            _text(str(name), "transfer path hash name")
            _require_sha(value, f"transfer.path_hashes.{name}")
        if not isinstance(self.null_predicates, Mapping) or not all(isinstance(value, bool) for value in self.null_predicates.values()):
            _fail("transfer.null_predicates must map names to booleans")
        for name in ("geometric", "reachable", "observable", "usable", "retained", "reusable", "excluded"):
            if not isinstance(getattr(self, name), bool):
                _fail(f"transfer.{name} must be boolean")
        if self.reusable and not self.retained:
            _fail("transfer reusable requires retained")
        object.__setattr__(self, "work_partition", _freeze(self.work_partition))
        object.__setattr__(self, "path_hashes", _freeze(self.path_hashes))
        object.__setattr__(self, "null_predicates", _freeze(self.null_predicates))

    def payload(self) -> Mapping[str, Any]:
        return {
            "source_coordinate_id": self.source_coordinate_id,
            "target_coordinate_id": self.target_coordinate_id,
            "target_kind": self.target_kind,
            "horizon": _plain(self.horizon),
            "treatment_response_interval": _plain(self.treatment_response_interval),
            "null_response_interval": _plain(self.null_response_interval),
            "effect_interval": _plain(self.effect_interval),
            "uncertainty_interval": _plain(self.uncertainty_interval),
            "delay": _plain(self.delay),
            "incident_work_interval": _plain(self.incident_work_interval),
            "source_work_interval": _plain(self.source_work_interval),
            "work_partition": _plain(self.work_partition),
            "reachability_matrix": [[finite_bits(v) for v in row] for row in self.reachability_matrix],
            "observability_matrix": [[finite_bits(v) for v in row] for row in self.observability_matrix],
            "reachability_rank": self.reachability_rank,
            "observability_rank": self.observability_rank,
            "reachability_spectrum": [finite_bits(v) for v in self.reachability_spectrum],
            "observability_spectrum": [finite_bits(v) for v in self.observability_spectrum],
            "reachability_nullspace_sha256": self.reachability_nullspace_sha256,
            "observability_nullspace_sha256": self.observability_nullspace_sha256,
            "geometric": self.geometric,
            "reachable": self.reachable,
            "observable": self.observable,
            "usable": self.usable,
            "retained": self.retained,
            "reusable": self.reusable,
            "null_predicates": _plain(self.null_predicates),
            "committed_consequence_sha256": self.committed_consequence_sha256,
            "trajectory_sha256": self.trajectory_sha256,
            "endpoint_state_sha256": self.endpoint_state_sha256,
            "predecessor_state_sha256": self.predecessor_state_sha256,
            "path_hashes": _plain(self.path_hashes),
            "control_kind": self.control_kind,
            "excluded": self.excluded,
        }


@dataclass(frozen=True, slots=True)
class QiEndpointCapacityReceipt:
    """Atomic W6B/G6C endpoint evidence and independent-replay inputs."""

    profile_sha256: str = ZERO_SHA256
    capacity_ladder_sha256: str = ZERO_SHA256
    controller_grammar_sha256: str = ZERO_SHA256
    physical_horizon: Mapping[str, Any] = field(default_factory=lambda: {"n": 1, "d": 1, "unit": "tick"})
    predecessor_head_sha256: str = ZERO_SHA256
    predecessor_state_sha256: str = ZERO_SHA256
    transfer_rows: tuple[Mapping[str, Any], ...] = ()
    boundary_transfer_receipts: tuple[Mapping[str, Any], ...] = ()
    multimodal_binding_receipts: tuple[Mapping[str, Any], ...] = ()
    capacity_levels: Mapping[str, int] = field(default_factory=dict)
    capacity_classification: Mapping[str, Any] = field(default_factory=dict)
    controls: tuple[Mapping[str, Any], ...] = ()
    partitions: Mapping[str, Any] = field(default_factory=dict)
    raw_trajectories: tuple[Mapping[str, Any], ...] = ()
    raw_transfer_table: Mapping[str, Any] = field(default_factory=dict)
    verifier_inputs: Mapping[str, Any] = field(default_factory=dict)
    consumed_semantic_subhashes: tuple[Mapping[str, str], ...] = ()
    independent_replay_identity: str = ZERO_SHA256
    fixture_sha256: str = ZERO_SHA256
    receipt_id: str = ""
    self_sha256: str = ""

    def __post_init__(self) -> None:
        for name in ("profile_sha256", "capacity_ladder_sha256", "controller_grammar_sha256", "predecessor_head_sha256", "predecessor_state_sha256"):
            _require_sha(getattr(self, name), f"receipt.{name}")
        object.__setattr__(self, "physical_horizon", _horizon(self.physical_horizon, "receipt.physical_horizon"))
        object.__setattr__(self, "transfer_rows", tuple(_freeze(_mapping(row, "transfer row")) for row in self.transfer_rows))
        object.__setattr__(self, "boundary_transfer_receipts", tuple(_freeze(_mapping(row, "boundary transfer")) for row in self.boundary_transfer_receipts))
        object.__setattr__(self, "multimodal_binding_receipts", tuple(_freeze(_mapping(row, "multimodal binding")) for row in self.multimodal_binding_receipts))
        object.__setattr__(self, "controls", tuple(_freeze(_mapping(row, "control")) for row in self.controls))
        object.__setattr__(self, "raw_trajectories", tuple(_freeze(_mapping(row, "raw trajectory")) for row in self.raw_trajectories))
        object.__setattr__(self, "capacity_levels", _freeze(self.capacity_levels))
        object.__setattr__(self, "capacity_classification", _freeze(self.capacity_classification))
        object.__setattr__(self, "partitions", _freeze(self.partitions))
        object.__setattr__(self, "raw_transfer_table", _freeze(self.raw_transfer_table))
        object.__setattr__(self, "verifier_inputs", _freeze(self.verifier_inputs))
        object.__setattr__(self, "consumed_semantic_subhashes", tuple(_freeze(row) for row in self.consumed_semantic_subhashes))
        for name in ("independent_replay_identity", "fixture_sha256"):
            _require_sha(getattr(self, name), f"receipt.{name}")
        if self.receipt_id and not _is_sha(self.receipt_id):
            _fail("receipt_id is invalid")
        if self.self_sha256 and not _is_sha(self.self_sha256):
            _fail("self_sha256 is invalid")

    def payload(self) -> Mapping[str, Any]:
        return {
            "schema": SCHEMA,
            "profile_sha256": self.profile_sha256,
            "capacity_ladder_sha256": self.capacity_ladder_sha256,
            "controller_grammar_sha256": self.controller_grammar_sha256,
            "physical_horizon": _plain(self.physical_horizon),
            "predecessor_head_sha256": self.predecessor_head_sha256,
            "predecessor_state_sha256": self.predecessor_state_sha256,
            "transfer_rows": _plain(self.transfer_rows),
            "boundary_transfer_receipts": _plain(self.boundary_transfer_receipts),
            "multimodal_binding_receipts": _plain(self.multimodal_binding_receipts),
            "capacity_levels": _plain(self.capacity_levels),
            "capacity_classification": _plain(self.capacity_classification),
            "controls": _plain(self.controls),
            "partitions": _plain(self.partitions),
            "raw_trajectories": _plain(self.raw_trajectories),
            "raw_transfer_table": _plain(self.raw_transfer_table),
            "verifier_inputs": _plain(self.verifier_inputs),
            "consumed_semantic_subhashes": _plain(self.consumed_semantic_subhashes),
            "independent_replay_identity": self.independent_replay_identity,
            "fixture_sha256": self.fixture_sha256,
            "receipt_id": self.receipt_id,
        }

    def to_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(dict(self.payload()) | {"self_sha256": self.self_sha256})


# --- replay/build implementation -------------------------------------------------

def _profile(value: QiEndpointCapacityProfile | Mapping[str, Any]) -> QiEndpointCapacityProfile:
    if isinstance(value, QiEndpointCapacityProfile):
        return value
    return QiEndpointCapacityProfile(**dict(_mapping(value, "profile")))


def _intervention(value: QiEndpointIntervention | Mapping[str, Any]) -> QiEndpointIntervention:
    if isinstance(value, QiEndpointIntervention):
        return value
    return QiEndpointIntervention.from_mapping(value)


def _advance_once(advance: Any, state: Any, drive: Any) -> Any:
    operation = getattr(advance, "execute_advance", None) or getattr(advance, "advance", None) or advance
    if not callable(operation):
        _fail("canonical advance is not callable")
    before = _plain(state)
    result = operation(state, drive)
    if _plain(state) != before:
        _fail("canonical advance mutated predecessor state")
    if hasattr(result, "committable"):
        if not bool(result.committable) or getattr(result, "candidate", None) is None:
            _fail("canonical advance returned an uncommittable step")
        result = result.candidate
    if hasattr(result, "field"):
        result = result.field
    return _freeze(result)


def _canonical_trajectory(item: QiEndpointIntervention, profile: QiEndpointCapacityProfile, advance: Any) -> tuple[Any, ...]:
    expected_steps = int(profile.physical_horizon["n"])
    if not _horizon_equal(item.horizon, profile.physical_horizon):
        _fail(f"{item.intervention_id}: horizon differs from frozen physical horizon")
    if item.controller_grammar_sha256 != profile.controller_grammar_sha256:
        _fail(f"{item.intervention_id}: controller grammar identity mismatch")
    if item.predecessor_head_sha256 != profile.predecessor_head_sha256:
        _fail(f"{item.intervention_id}: predecessor head identity mismatch")
    if item.source_coordinate_id not in profile.source_coordinate_ids:
        _fail(f"{item.intervention_id}: source coordinate is not registered")
    if item.target_coordinate_id not in profile.target_coordinate_ids:
        _fail(f"{item.intervention_id}: target coordinate is not registered")
    if item.target_kind not in profile.target_kinds:
        _fail(f"{item.intervention_id}: target kind is not registered")
    if not item.canonical_advance:
        _fail(f"{item.intervention_id}: canonical advance identity is false")
    _forbidden(item.drives, f"{item.intervention_id}.drives")
    _forbidden(item.predecessor_state, f"{item.intervention_id}.predecessor_state")
    _forbidden(item.endpoint_state, f"{item.intervention_id}.endpoint_state")
    _forbidden(item.trajectory, f"{item.intervention_id}.trajectory")
    if item.reset or item.proposal or not item.committed or not item.acknowledged:
        return ()
    state = item.predecessor_state
    if state is None:
        state = {"state_sha256": profile.predecessor_state_sha256}
    drives = item.drives
    if len(drives) != expected_steps:
        _fail(f"{item.intervention_id}: drive count does not equal exact horizon")
    trajectory = [state]
    for drive in drives:
        trajectory.append(_advance_once(advance, trajectory[-1], drive))
    if len(trajectory) != expected_steps + 1:
        _fail(f"{item.intervention_id}: canonical trajectory length mismatch")
    if item.trajectory:
        supplied = tuple(_plain(v) for v in item.trajectory)
        actual = tuple(_plain(v) for v in trajectory)
        if supplied != actual:
            _fail(f"{item.intervention_id}: supplied trajectory is not canonical advance output")
    if item.endpoint_state is not None and _plain(item.endpoint_state) != _plain(trajectory[-1]):
        _fail(f"{item.intervention_id}: endpoint state is not canonical trajectory endpoint")
    return tuple(_freeze(v) for v in trajectory)


_INTERVENTION_FIELDS = frozenset(item.name for item in fields(QiEndpointIntervention))


def _control_intervention(
    kind: str,
    spec: Mapping[str, Any],
    reference: QiEndpointIntervention,
    profile: QiEndpointCapacityProfile,
) -> QiEndpointIntervention:
    raw = dict(_mapping(spec, f"control_specs.{kind}"))
    _forbidden(raw, f"control_specs.{kind}")
    nested = raw.get("intervention")
    if nested is not None:
        base = dict(_mapping(nested, f"control_specs.{kind}.intervention"))
    else:
        base = {key: value for key, value in raw.items() if key in _INTERVENTION_FIELDS}
    for name in ("drives", "incident_work", "source_work", "work_partition"):
        if name not in base:
            _fail(f"control {kind} requires measured {name}")
    if "target_response" not in base and "response" not in raw:
        _fail(f"control {kind} requires measured target_response")
    base["intervention_id"] = str(base.get("intervention_id") or f"control-{kind}-{reference.intervention_id}")
    base["source_coordinate_id"] = str(base.get("source_coordinate_id") or reference.source_coordinate_id)
    base["target_coordinate_id"] = str(base.get("target_coordinate_id") or reference.target_coordinate_id)
    base["target_kind"] = str(base.get("target_kind") or reference.target_kind)
    base["horizon"] = base.get("horizon", _plain(reference.horizon))
    base["predecessor_state"] = base.get("predecessor_state", reference.predecessor_state)
    base["controller_grammar_sha256"] = profile.controller_grammar_sha256
    base["predecessor_head_sha256"] = profile.predecessor_head_sha256
    base["control_kind"] = kind
    base["target_response"] = base.get("target_response", raw["response"])
    base["null_response"] = base.get("null_response", raw.get("null_response", 0.0))
    base["delayed_prediction_residual"] = base.get(
        "delayed_prediction_residual", raw.get("delayed_prediction_residual", 1.0)
    )
    base["uncertainty"] = base.get("uncertainty", raw.get("uncertainty", 0.0))
    base["delay"] = base.get("delay", raw.get("delay", _plain(reference.delay)))
    if kind == "proposal_only":
        base.update(committed=False, acknowledged=False, proposal=True)
    elif kind == "reset_counted_as_acquisition":
        base["reset"] = True
    else:
        base.setdefault("committed", True)
        base.setdefault("acknowledged", True)
    base.setdefault("proposal", False)
    base.setdefault("reset", False)
    base["committed_consequence_sha256"] = base.get("committed_consequence_sha256")
    return QiEndpointIntervention.from_mapping(base)


def _control_record(
    kind: str,
    *,
    treatment_hash: str,
    spec: Mapping[str, Any],
    item: QiEndpointIntervention,
    row: QiEndpointTransferRow,
    raw: Mapping[str, Any],
    reference_row: QiEndpointTransferRow,
) -> Mapping[str, Any]:
    relation = _plain(spec.get("expected_relation", "registered-control"))
    _forbidden(relation, f"control_specs.{kind}.expected_relation")
    treatment_work = _work(
        spec.get("reference_incident_work", reference_row.incident_work_interval),
        "control.reference_incident",
    )
    treatment_source_work = _work(
        spec.get("reference_source_work", reference_row.source_work_interval),
        "control.reference_source",
    )
    incident = row.incident_work_interval
    source = row.source_work_interval
    incident_ratio = abs(_number(incident) - _number(treatment_work)) / max(abs(_number(treatment_work)), 1e-12)
    source_ratio = abs(_number(source) - _number(treatment_source_work)) / max(abs(_number(treatment_source_work)), 1e-12)
    epsilon = _finite(spec.get("epsilon_work", 0.0), f"control_specs.{kind}.epsilon_work")
    if epsilon < 0.0 or max(incident_ratio, source_ratio) > epsilon:
        _fail(f"control {kind} does not satisfy declared equal-work bound")
    residual = _interval(item.delayed_prediction_residual, f"control.{kind}.residual", nonnegative=True)
    control_arm = _sha(
        {
            "kind": kind,
            "target_coordinate_id": row.target_coordinate_id,
            "source_coordinate_id": row.source_coordinate_id,
            "trajectory_sha256": raw["trajectory_sha256"],
            "endpoint_state_sha256": raw["endpoint_state_sha256"],
            "incident_work_interval": _plain(incident),
            "source_work_interval": _plain(source),
            "target_response_interval": _plain(row.treatment_response_interval),
            "delayed_prediction_residual_interval": _plain(residual),
        },
        "cassi.qi-flow-endpoint-control-arm.v1",
    )
    payload = {
        "control_id": str(spec.get("control_id") or f"endpoint-control-{kind}-{row.source_coordinate_id}-{row.target_coordinate_id}"),
        "kind": kind,
        "status": "PASS",
        "source_coordinate_id": row.source_coordinate_id,
        "target_coordinate_id": row.target_coordinate_id,
        "target_kind": row.target_kind,
        "treatment_arm_sha256": treatment_hash,
        "control_arm_sha256": control_arm,
        "trajectory_sha256": raw["trajectory_sha256"],
        "endpoint_state_sha256": raw["endpoint_state_sha256"],
        "predecessor_state_sha256": raw["predecessor_state_sha256"],
        "incident_work_interval": _plain(incident),
        "source_work_interval": _plain(source),
        "target_response_interval": _plain(row.treatment_response_interval),
        "effect_interval": _plain(row.effect_interval),
        "uncertainty_interval": _plain(row.uncertainty_interval),
        "delayed_prediction_residual_interval": _plain(residual),
        "delay": _plain(row.delay),
        "equal_work_ratio": _plain(_scalar(max(incident_ratio, source_ratio), f"control.{kind}.equal_work_ratio")),
        "epsilon_work": _plain(_scalar(epsilon, f"control.{kind}.epsilon_work")),
        "expected_relation": relation,
        "expected_relation_sha256": _sha(relation, "cassi.qi-flow-endpoint-control-relation.v1"),
        "excluded": row.excluded,
        "null_predicates": _plain(row.null_predicates),
    }
    payload["self_sha256"] = _sha(
        {key: value for key, value in payload.items() if key != "self_sha256"},
        "cassi.qi-flow-endpoint-control.v1",
    )
    return MappingProxyType(payload)


def _work_from_item(item: QiEndpointIntervention) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    incident = _work(item.incident_work, f"{item.intervention_id}.incident")
    if item.source_work is None:
        _fail(f"{item.intervention_id}: source work must be explicit")
    if item.work_partition is None:
        _fail(f"{item.intervention_id}: work partition must be explicit")
    source = _work(item.source_work, f"{item.intervention_id}.source")
    partition = _partition(item.work_partition, incident, f"{item.intervention_id}.work_partition")
    return incident, source, partition


def _response(item: QiEndpointIntervention, name: str) -> Mapping[str, Any]:
    return _scalar(getattr(item, name), f"{item.intervention_id}.{name}")


def _threshold(profile: QiEndpointCapacityProfile, coordinate: str, source: Mapping[str, Any], *, null: bool = False) -> float:
    table = profile.null_thresholds if null else profile.uncertainty_thresholds
    value = table.get(coordinate, 0.0) if isinstance(table, Mapping) else 0.0
    if isinstance(value, Mapping):
        value = value.get("value", value.get("upper", 0.0))
    return _finite(value, f"threshold.{coordinate}")

def _transfer_row(item: QiEndpointIntervention, profile: QiEndpointCapacityProfile, trajectory: tuple[Any, ...], incident: Mapping[str, Any], source: Mapping[str, Any], partition: Mapping[str, Any]) -> tuple[QiEndpointTransferRow, Mapping[str, Any]]:
    reach_matrix = _matrix(item.reachability_matrix if item.reachability_matrix is not None else profile.reachability_matrices.get(item.target_coordinate_id), "reachability_matrix")
    obs_matrix = _matrix(item.observability_matrix if item.observability_matrix is not None else profile.observability_matrices.get(item.target_coordinate_id), "observability_matrix")
    rr, orank = _rank(reach_matrix), _rank(obs_matrix)
    rs, os = _spectrum(reach_matrix), _spectrum(obs_matrix)
    uncertainty = _interval(item.uncertainty, f"{item.intervention_id}.uncertainty", nonnegative=True)
    treatment = _response(item, "target_response")
    null = _response(item, "null_response")
    effect_value = _number(treatment) - _number(null)
    effect = _scalar({"value": effect_value, "lower": _number(treatment, "lower") - _number(null, "upper"), "upper": _number(treatment, "upper") - _number(null, "lower")}, f"{item.intervention_id}.effect")
    geometric = bool(profile.coordinate_geometric.get(item.target_coordinate_id, True))
    null_threshold = _threshold(profile, item.target_coordinate_id, null, null=True)
    uncertainty_threshold = _threshold(profile, item.target_coordinate_id, uncertainty, null=False)
    clear = _number(effect, "lower") > null_threshold and _number(uncertainty, "upper") <= uncertainty_threshold
    committed = item.committed and item.acknowledged and not item.proposal and not item.reset
    reachable = geometric and rr > 0 and committed and _work_value(source) > 0.0
    observable = geometric and orank > 0 and committed and _number(uncertainty, "upper") <= uncertainty_threshold
    usable = reachable and observable and clear
    retained = usable and item.retention_state in ("retained", "reusable") and item.target_coordinate_id in profile.retained_coordinates
    reusable = retained and item.retention_state == "reusable" and item.target_coordinate_id in profile.reusable_coordinates
    if reusable and not retained:
        _fail(f"{item.intervention_id}: reusable endpoint is not retained")
    nulls = {
        "reachability_null": rr == 0,
        "observability_null": orank == 0,
        "uncertainty_null": _number(uncertainty, "upper") > uncertainty_threshold,
        "effect_null": not clear,
        "dark": not geometric,
        "uncommitted": not committed,
        "proposal_only": bool(item.proposal),
        "reset_excluded": bool(item.reset),
    }
    endpoint_hash = _raw_sha(trajectory[-1] if trajectory else {"excluded": item.intervention_id}, "cassi.qi-flow-endpoint-state.v1")
    predecessor_hash = _raw_sha(trajectory[0] if trajectory else item.predecessor_state, "cassi.qi-flow-endpoint-state.v1")
    traj_hash = _raw_sha(list(trajectory), "cassi.qi-flow-endpoint-trajectory.v1") if trajectory else _raw_sha({"excluded": item.intervention_id}, "cassi.qi-flow-endpoint-trajectory.v1")
    committed_hash = item.committed_consequence_sha256
    if committed and item.control_kind == "treatment" and item.target_kind != "boundary_observation" and not _is_sha(committed_hash):
        _fail(f"{item.intervention_id}: committed non-boundary consequence hash is required")
    if not committed and committed_hash is not None:
        _fail(f"{item.intervention_id}: uncommitted intervention cannot carry a consequence")
    row = QiEndpointTransferRow(
        source_coordinate_id=item.source_coordinate_id, target_coordinate_id=item.target_coordinate_id, target_kind=item.target_kind,
        horizon=item.horizon, treatment_response_interval=treatment, null_response_interval=null, effect_interval=effect,
        uncertainty_interval=uncertainty, delay=item.delay, incident_work_interval=incident, source_work_interval=source,
        work_partition=partition, reachability_matrix=reach_matrix, observability_matrix=obs_matrix, reachability_rank=rr,
        observability_rank=orank, reachability_spectrum=rs, observability_spectrum=os,
        reachability_nullspace_sha256=_nullspace_hash(reach_matrix, rr), observability_nullspace_sha256=_nullspace_hash(obs_matrix, orank),
        geometric=geometric, reachable=reachable, observable=observable, usable=usable, retained=retained, reusable=reusable,
        null_predicates=nulls, committed_consequence_sha256=committed_hash, trajectory_sha256=traj_hash,
        endpoint_state_sha256=endpoint_hash, predecessor_state_sha256=predecessor_hash,
        path_hashes=item.path_hashes, control_kind=item.control_kind, excluded=not bool(trajectory),
    )
    return row, {"trajectory": trajectory, "endpoint_state_sha256": endpoint_hash, "predecessor_state_sha256": predecessor_hash, "trajectory_sha256": traj_hash, "committed_consequence_sha256": committed_hash}


def _transfer_payload(row: QiEndpointTransferRow, item: QiEndpointIntervention, profile: QiEndpointCapacityProfile, trajectory_hashes: Mapping[str, Any], treatment_hash: str, controls: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    source_descriptor = _descriptor_hash(item.source_descriptor_sha256, item.source_coordinate_id)
    target_descriptor = _descriptor_hash(item.target_descriptor_sha256 or profile.target_descriptor_sha256s.get(item.target_coordinate_id), item.target_coordinate_id)
    drive_hash = _descriptor_hash(item.drive_script_sha256, {"intervention_id": item.intervention_id, "drives": _plain(item.drives)})
    packet_hash = _descriptor_hash(item.source_packet_sha256, {"source": item.source_coordinate_id, "intervention": item.intervention_id})
    forward_hash = _descriptor_hash(item.target_operator_sha256, {"target": item.target_coordinate_id, "kind": item.target_kind})
    adjoint_hash = _sha({"forward_operator_sha256": forward_hash, "target": item.target_coordinate_id}, "cassi.qi-flow-endpoint-adjoint.v1")
    source = {
        "port_id": item.source_port_id or profile.source_port_ids.get(item.source_coordinate_id, item.source_coordinate_id),
        "descriptor_sha256": source_descriptor, "coordinate_id": item.source_coordinate_id, "source_packet_sha256": packet_hash,
        "source_drive_script_sha256": drive_hash, "incident_work_interval": _plain(row.incident_work_interval),
        "admitted_work_interval": _plain(row.source_work_interval), "forward_operator_sha256": forward_hash, "adjoint_operator_sha256": adjoint_hash,
    }
    shared = {
        "body_frame_sha256": profile.body_frame_sha256, "ordinary_packet_set_sha256": profile.ordinary_packet_set_sha256,
        "start_time": {"n": 0, "d": 1}, "horizon": {"n": int(row.horizon["n"]), "d": int(row.horizon["d"])}, "event_order_sha256": profile.event_order_sha256,
    }
    arm = {
        "trajectory_sha256": row.trajectory_sha256, "raw_trajectory_sha256": trajectory_hashes["trajectory_sha256"],
        "endpoint_state_sha256": row.endpoint_state_sha256, "raw_endpoint_state_sha256": trajectory_hashes["endpoint_state_sha256"],
        "predecessor_state_sha256": row.predecessor_state_sha256, "raw_predecessor_state_sha256": trajectory_hashes["predecessor_state_sha256"],
        "ledger_sha256": _sha({"incident": _plain(row.incident_work_interval), "partition": _plain(row.work_partition)}, "cassi.qi-flow-endpoint-ledger.v1"),
        "drive_script_sha256": drive_hash,
    }
    null_arm = dict(arm)
    target = {
        "target_kind": row.target_kind, "target_port_id": item.target_port_id or profile.target_port_ids.get(row.target_coordinate_id, row.target_coordinate_id),
        "target_descriptor_sha256": target_descriptor, "target_coordinate_id": row.target_coordinate_id,
        "target_operator_sha256": forward_hash, "treatment_response_interval": _plain(row.treatment_response_interval),
        "null_response_interval": _plain(row.null_response_interval), "effect_interval": _plain(row.effect_interval),
        "uncertainty_interval": _plain(row.uncertainty_interval), "delay": _plain(row.delay),
        "clear_predicate_sha256": _sha(_plain(row.null_predicates), "cassi.qi-flow-endpoint-clear-predicate.v1"),
        "committed_consequence_sha256": row.committed_consequence_sha256 if row.target_kind != "boundary_observation" else None,
    }
    response_matrix = row.reachability_matrix
    spectrum = {
        "matrix": _raw_array(response_matrix),
        "rank_interval": _plain(_interval({"value": float(row.reachability_rank), "lower": float(row.reachability_rank), "upper": float(row.reachability_rank)}, "rank", nonnegative=True)),
        "singular_value_intervals": [_plain(_interval({"value": v, "lower": v, "upper": v}, "singular", nonnegative=True)) for v in row.reachability_spectrum],
        "nullspace_sha256": row.reachability_nullspace_sha256,
    }
    path = {"target_coordinate_id": row.target_coordinate_id,
            "spatial_path_sha256": row.path_hashes.get("spatial", _sha({"source": item.source_coordinate_id, "target": row.target_coordinate_id}, "cassi.qi-flow-endpoint-spatial-path.v1")),
            "scale_link_path_sha256": row.path_hashes.get("scale", _sha({"source": item.source_coordinate_id, "target": row.target_coordinate_id}, "cassi.qi-flow-endpoint-scale-path.v1")),
            "passive_egress_path_sha256": row.path_hashes.get("passive", _sha({"target": row.target_coordinate_id}, "cassi.qi-flow-endpoint-passive-path.v1"))}
    matched = []
    for kind in _TRANSFER_CONTROL_KINDS:
        control = next(
            (
                candidate
                for candidate in controls
                if candidate.get("kind") == kind
                and candidate.get("source_coordinate_id", row.source_coordinate_id) == row.source_coordinate_id
                and candidate.get("target_coordinate_id", row.target_coordinate_id) == row.target_coordinate_id
            ),
            None,
        )
        if control is None:
            _fail(f"transfer {row.source_coordinate_id}->{row.target_coordinate_id} lacks measured {kind} control")
        matched.append(
            {
                "control_id": control["control_id"],
                "kind": kind,
                "source_coordinate_id": row.source_coordinate_id,
                "target_coordinate_id": row.target_coordinate_id,
                "treatment_arm_sha256": treatment_hash,
                "control_arm_sha256": control["control_arm_sha256"],
                "expected_relation_sha256": control["expected_relation_sha256"],
                "control_trajectory_sha256": control["trajectory_sha256"],
                "control_endpoint_state_sha256": control["endpoint_state_sha256"],
                "equal_work_ratio": control["equal_work_ratio"],
            }
        )
    classification = {"geometric": row.geometric, "reachable": row.reachable, "observable": row.observable, "usable": row.usable, "retained": row.retained, "reusable": row.reusable, "dark_coordinate_ids": [row.target_coordinate_id] if row.null_predicates.get("dark") else []}
    base = {
        "schema": BOUNDARY_TRANSFER_SCHEMA, "contract_root_sha256": profile.contract_root_sha256, "profile_sha256": profile.profile_sha256,
        "consumed_semantic_subhashes": _plain(profile.consumed_semantic_subhashes), "transfer_id": f"boundary-transfer-{item.intervention_id}",
        "capacity_ladder_sha256": profile.capacity_ladder_sha256, "controller_grammar_sha256": profile.controller_grammar_sha256,
        "clock_sha256": profile.clock_sha256, "predecessor_head_sha256": profile.predecessor_head_sha256,
        "predecessor_state_sha256": profile.predecessor_state_sha256, "source": source, "shared_context": shared,
        "treatment_arm": arm, "null_arm": null_arm, "target_responses": [target], "response_spectrum": spectrum,
        "path_witnesses": [path], "matched_controls": matched, "capacity_classification": classification,
        "fixture_sha256": _sha({"transfer_id": item.intervention_id, "target": row.target_coordinate_id}, "cassi.qi-flow-endpoint-fixture.v1"),
    }
    base["independent_replay_identity"] = _sha({"transfer_id": base["transfer_id"], "predecessor_state_sha256": profile.predecessor_state_sha256, "horizon": shared["horizon"], "trajectory_sha256": row.trajectory_sha256}, "cassi.qi-flow-endpoint-replay.v1")
    base["self_sha256"] = _sha(base, TRANSFER_DOMAIN)
    return MappingProxyType(base)


def _binding_payload(
    rows: Sequence[QiEndpointTransferRow],
    items: Sequence[QiEndpointIntervention],
    profile: QiEndpointCapacityProfile,
    transfer_hashes: Sequence[str],
    treatment_hash: str,
    controls: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    if len(profile.source_coordinate_ids) < 2 or not rows or not items:
        return None
    if not set(profile.source_coordinate_ids) <= {item.source_coordinate_id for item in items}:
        return None
    required_binding = set(profile.required_control_kinds) & set(_BINDING_CONTROL_KINDS)
    if not required_binding:
        return None
    target_row = next((row for row in rows if row.target_kind in profile.target_kinds), rows[0])
    target_item = next(
        (item for item in items if item.target_coordinate_id == target_row.target_coordinate_id),
        items[0],
    )
    relevant = [
        control
        for control in controls
        if control.get("target_coordinate_id") == target_row.target_coordinate_id
    ]
    by_kind: dict[str, list[Mapping[str, Any]]] = {}
    for control in relevant:
        by_kind.setdefault(str(control["kind"]), []).append(control)
    missing = required_binding - set(by_kind)
    if missing:
        _fail(f"multimodal binding lacks measured controls: {sorted(missing)}")
    grouped = profile.source_modalities
    modalities = []
    if grouped:
        for port, coords in grouped.items():
            modalities.append(
                {
                    "port_id": port,
                    "descriptor_sha256": _descriptor_hash(None, port),
                    "coordinate_ids": list(coords),
                }
            )
    else:
        for coordinate in profile.source_coordinate_ids:
            modalities.append(
                {
                    "port_id": coordinate,
                    "descriptor_sha256": _descriptor_hash(None, coordinate),
                    "coordinate_ids": [coordinate],
                }
            )
    if len(modalities) < 2:
        return None
    treatment_work = target_row.incident_work_interval
    modality_scripts = []
    for modality in modalities:
        source = next(
            (
                item
                for item in items
                if item.source_coordinate_id in modality["coordinate_ids"]
            ),
            None,
        )
        if source is None:
            _fail(f"multimodal modality {modality['port_id']} lacks treatment source")
        modality_scripts.append(
            (
                modality,
                {
                    "port_id": modality["port_id"],
                    "descriptor_sha256": modality["descriptor_sha256"],
                    "coordinate_ids": list(modality["coordinate_ids"]),
                    "drive_script_sha256": _descriptor_hash(
                        source.drive_script_sha256, source.intervention_id
                    ),
                    "packet_sha256": _descriptor_hash(
                        source.source_packet_sha256, source.intervention_id
                    ),
                    "incident_work_interval": _plain(
                        _work(source.incident_work, "binding.source.incident")
                    ),
                    "admitted_work_interval": _plain(
                        _work(source.source_work, "binding.source.admitted")
                    ),
                },
            )
        )
    source_scripts = [script for _, script in modality_scripts]
    target_hash = target_row.committed_consequence_sha256
    treatment_residual = _interval(
        target_item.delayed_prediction_residual,
        "binding.treatment.residual",
        nonnegative=True,
    )
    treatment_response = target_row.treatment_response_interval

    def treatment_arm() -> Mapping[str, Any]:
        return {
            "arm_id": "treatment",
            "arm_kind": "treatment",
            "source_scripts": _plain(source_scripts),
            "trajectory_sha256": target_row.trajectory_sha256,
            "endpoint_state_sha256": target_row.endpoint_state_sha256,
            "predecessor_state_sha256": target_row.predecessor_state_sha256,
            "ledger_sha256": _sha(
                {"work": _plain(treatment_work), "arm": treatment_hash},
                "cassi.qi-flow-endpoint-ledger.v1",
            ),
            "target_response_interval": _plain(treatment_response),
            "delayed_prediction_residual_interval": _plain(treatment_residual),
            "delay": _plain(target_row.delay),
            "uncertainty_interval": _plain(target_row.uncertainty_interval),
            "committed_consequence_sha256": target_hash,
        }

    def control_arm(control: Mapping[str, Any], arm_id: str) -> Mapping[str, Any]:
        matching_ports = {
            modality["port_id"]
            for modality in modalities
            if control["source_coordinate_id"] in modality["coordinate_ids"]
        }
        scripts = [
            script for script in source_scripts if script["port_id"] in matching_ports
        ]
        if not scripts:
            scripts = source_scripts[:1]
        return {
            "arm_id": arm_id,
            "arm_kind": control["kind"],
            "source_scripts": _plain(scripts),
            "trajectory_sha256": control["trajectory_sha256"],
            "endpoint_state_sha256": control["endpoint_state_sha256"],
            "predecessor_state_sha256": control["predecessor_state_sha256"],
            "ledger_sha256": control.get(
                "ledger_sha256",
                _sha(
                    {
                        "work": control["incident_work_interval"],
                        "arm": arm_id,
                    },
                    "cassi.qi-flow-endpoint-ledger.v1",
                ),
            ),
            "target_response_interval": control["target_response_interval"],
            "delayed_prediction_residual_interval": control[
                "delayed_prediction_residual_interval"
            ],
            "delay": control["delay"],
            "uncertainty_interval": control["uncertainty_interval"],
            "committed_consequence_sha256": target_hash if not control["excluded"] else None,
        }

    control_arms: list[Mapping[str, Any]] = []
    modality_controls = by_kind.get("modality_alone", [])
    if "modality_alone" in required_binding:
        for modality in modalities:
            candidate = next(
                (
                    control
                    for control in modality_controls
                    if control["source_coordinate_id"] in modality["coordinate_ids"]
                ),
                None,
            )
            if candidate is None:
                _fail(f"modality {modality['port_id']} lacks measured modality-alone control")
            control_arms.append(
                control_arm(candidate, f"control-modality-{modality['port_id']}")
            )
    for kind in _BINDING_CONTROL_KINDS:
        if kind == "modality_alone" or kind not in required_binding:
            continue
        candidate = by_kind[kind][0]
        control_arms.append(control_arm(candidate, f"control-{kind}"))

    matching = []
    causal_margins = []
    residual_improvements = []
    for control in control_arms:
        candidate = next(
            arm
            for arm in relevant
            if arm["trajectory_sha256"] == control["trajectory_sha256"]
        )
        margin = _scalar(
            {
                "value": _number(treatment_response) - _number(candidate["target_response_interval"]),
                "lower": _number(treatment_response, "lower")
                - _number(candidate["target_response_interval"], "upper"),
                "upper": _number(treatment_response, "upper")
                - _number(candidate["target_response_interval"], "lower"),
            },
            "binding.causal_margin",
        )
        improvement = _scalar(
            {
                "value": _number(candidate["delayed_prediction_residual_interval"])
                - _number(treatment_residual),
                "lower": _number(candidate["delayed_prediction_residual_interval"], "lower")
                - _number(treatment_residual, "upper"),
                "upper": _number(candidate["delayed_prediction_residual_interval"], "upper")
                - _number(treatment_residual, "lower"),
            },
            "binding.residual_improvement",
        )
        if _number(margin, "lower") <= 0.0:
            _fail(f"binding treatment does not beat control {control['arm_id']}")
        if _number(improvement, "lower") <= 0.0:
            _fail(f"binding treatment does not reduce residual versus {control['arm_id']}")
        causal_margins.append(margin)
        residual_improvements.append(improvement)
        matching.append(
            {
                "control_arm_id": control["arm_id"],
                "control_id": candidate["control_id"],
                "port_id": control["source_scripts"][0]["port_id"],
                "treatment_incident_work": _plain(treatment_work),
                "control_incident_work": candidate["incident_work_interval"],
                "reference_work": _plain(treatment_work),
                "epsilon_work": candidate["epsilon_work"],
                "relative_difference_interval": candidate["equal_work_ratio"],
                "causal_margin_interval": _plain(margin),
                "residual_improvement_interval": _plain(improvement),
            }
        )
    causal_margin = {
        "value": min(_number(item) for item in causal_margins),
        "lower": min(_number(item, "lower") for item in causal_margins),
        "upper": max(_number(item, "upper") for item in causal_margins),
    }
    residual_improvement = {
        "value": min(_number(item) for item in residual_improvements),
        "lower": min(_number(item, "lower") for item in residual_improvements),
        "upper": max(_number(item, "upper") for item in residual_improvements),
    }
    null_threshold = _interval(
        profile.null_thresholds.get(target_row.target_coordinate_id, 0.0),
        "binding.null_threshold",
        nonnegative=True,
    )
    effect = {
        "residual_improvement_interval": _plain(
            _scalar(residual_improvement, "binding.residual_improvement")
        ),
        "target_effect_interval": _plain(target_row.effect_interval),
        "causal_margin_interval": _plain(_scalar(causal_margin, "binding.causal_margin")),
        "null_threshold": _plain(null_threshold),
        "clear_predicate_sha256": _sha(
            {
                "treatment": _plain(treatment_response),
                "controls": [
                    _plain(arm["target_response_interval"]) for arm in control_arms
                ],
            },
            "cassi.qi-flow-endpoint-clear-predicate.v1",
        ),
    }
    base = {
        "schema": MULTIMODAL_BINDING_SCHEMA,
        "contract_root_sha256": profile.contract_root_sha256,
        "profile_sha256": profile.profile_sha256,
        "consumed_semantic_subhashes": _plain(profile.consumed_semantic_subhashes),
        "binding_id": "multimodal-binding-endpoint",
        "capacity_ladder_sha256": profile.capacity_ladder_sha256,
        "controller_grammar_sha256": profile.controller_grammar_sha256,
        "clock_sha256": profile.clock_sha256,
        "predecessor_head_sha256": profile.predecessor_head_sha256,
        "predecessor_state_sha256": profile.predecessor_state_sha256,
        "source_modalities": modalities,
        "target": {
            "target_kind": target_row.target_kind,
            "target_id": target_row.target_coordinate_id,
            "descriptor_sha256": _descriptor_hash(
                target_item.target_descriptor_sha256,
                target_row.target_coordinate_id,
            ),
            "coordinate_ids": [target_row.target_coordinate_id],
            "committed_consequence_sha256": target_hash,
        },
        "treatment_arm": treatment_arm(),
        "control_arms": control_arms,
        "work_matching": matching,
        "binding_effect": effect,
        "transfer_receipt_sha256s": list(transfer_hashes),
        "fixture_sha256": _sha(
            {"binding": "multimodal-binding-endpoint", "transfers": list(transfer_hashes)},
            "cassi.qi-flow-endpoint-fixture.v1",
        ),
        "independent_replay_identity": _sha(
            {
                "binding": "multimodal-binding-endpoint",
                "horizon": _plain(profile.physical_horizon),
                "treatment_arm_sha256": treatment_hash,
                "controls": [control["control_arm_sha256"] for control in relevant],
                "transfers": list(transfer_hashes),
            },
            "cassi.qi-flow-endpoint-replay.v1",
        ),
    }
    base["self_sha256"] = _sha(base, BINDING_DOMAIN)
    return MappingProxyType(base)


def _capacity_levels(rows: Sequence[QiEndpointTransferRow]) -> tuple[Mapping[str, int], Mapping[str, Any]]:
    levels = {key: sum(bool(getattr(row, key)) for row in rows if not row.excluded) for key in ("geometric", "reachable", "observable", "usable", "retained", "reusable")}
    classification = {"geometric": levels["geometric"] > 0, "reachable": levels["reachable"] > 0, "observable": levels["observable"] > 0,
                      "usable": levels["usable"] > 0, "retained": levels["retained"] > 0, "reusable": levels["reusable"] > 0,
                      "dark_coordinate_ids": sorted({row.target_coordinate_id for row in rows if row.null_predicates.get("dark")})}
    return MappingProxyType(levels), MappingProxyType(classification)


def build_endpoint_capacity_receipt(profile: QiEndpointCapacityProfile | Mapping[str, Any], interventions: Iterable[QiEndpointIntervention | Mapping[str, Any]] | None = None, *, advance: Any = None, controls: Iterable[Mapping[str, Any]] | Mapping[str, Any] | None = None) -> QiEndpointCapacityReceipt:
    """Build one immutable endpoint receipt from exact-horizon interventions."""
    profile_obj = _profile(profile)
    raw_items = interventions if interventions is not None else profile_obj.control_specs.get("interventions", ())
    items = tuple(_intervention(item) for item in raw_items)
    if not items:
        _fail("endpoint intervention registry is empty")
    rows: list[QiEndpointTransferRow] = []
    boundary: list[Mapping[str, Any]] = []
    raw_trajectories: list[Mapping[str, Any]] = []
    raw_trajectories_by_id: dict[str, Mapping[str, Any]] = {}
    intervention_hashes: dict[str, str] = {}
    for item in items:
        trajectory = _canonical_trajectory(item, profile_obj, advance)
        if not trajectory:
            # Excluded proposals/resets are retained as explicit controls, never capacity rows.
            if not (item.proposal or item.reset or not item.committed or not item.acknowledged):
                _fail(f"{item.intervention_id}: canonical trajectory was empty")
        incident, source, partition = _work_from_item(item)
        row, raw = _transfer_row(item, profile_obj, trajectory, incident, source, partition)
        rows.append(row)
        raw_record = {"intervention_id": item.intervention_id, "trajectory": _plain(trajectory), "trajectory_sha256": raw["trajectory_sha256"], "endpoint_state_sha256": raw["endpoint_state_sha256"], "predecessor_state_sha256": raw["predecessor_state_sha256"], "byte_count": len(canonical_json_bytes(_plain(trajectory))), "canonical_advance": bool(item.canonical_advance), "excluded": row.excluded}
        raw_trajectories.append(raw_record)
        raw_trajectories_by_id[item.intervention_id] = raw_record
        intervention_hashes[item.intervention_id] = row.trajectory_sha256
    records = sorted(zip(items, rows, raw_trajectories), key=lambda record: (record[1].target_coordinate_id, record[1].source_coordinate_id, record[1].target_kind, record[0].intervention_id))
    items = tuple(record[0] for record in records)
    rows = [record[1] for record in records]
    raw_trajectories = [record[2] for record in records]
    treatment_rows = [row for row in rows if row.control_kind == "treatment" and not row.excluded]
    if not treatment_rows:
        _fail("endpoint registry has no committed treatment intervention")
    treatment_hash = _sha({"rows": [row.payload() for row in treatment_rows]}, "cassi.qi-flow-endpoint-treatment-arm.v1")
    control_records: list[Mapping[str, Any]] = []
    provided_specs: dict[str, Mapping[str, Any]] = {}
    if controls is not None:
        values = controls.items() if isinstance(controls, Mapping) else (
            (str(_mapping(value, "control").get("kind")), value) for value in controls
        )
        for key, value in values:
            spec = _mapping(value, f"control_specs.{key}")
            kind = str(spec.get("kind", key))
            if kind not in _CONTROL_KINDS:
                _fail(f"unknown control kind {kind}")
            provided_specs[kind] = spec
    specs = profile_obj.control_specs
    treatment_pairs = [
        (item, row, raw_trajectories_by_id[item.intervention_id])
        for item, row in zip(items, rows)
        if row.control_kind == "treatment"
    ]
    required_kinds = tuple(dict.fromkeys((*_TRANSFER_CONTROL_KINDS, *profile_obj.required_control_kinds)))
    for kind in required_kinds:
        if kind not in _CONTROL_KINDS:
            _fail(f"profile requires unknown control {kind}")
        spec = provided_specs.get(kind, specs.get(kind))
        if spec is None:
            _fail(f"control {kind} has no measured intervention specification")
        arms = spec.get("arms", (spec,)) if isinstance(spec, Mapping) else (spec,)
        if not isinstance(arms, (tuple, list)) or not arms:
            _fail(f"control {kind} arms are empty")
        for reference, reference_row, _ in treatment_pairs:
            selected = next(
                (
                    _mapping(arm, f"control_specs.{kind}.arm")
                    for arm in arms
                    if isinstance(arm, Mapping)
                    and arm.get("source_coordinate_id", reference.source_coordinate_id) == reference.source_coordinate_id
                    and arm.get("target_coordinate_id", reference.target_coordinate_id) == reference.target_coordinate_id
                ),
                _mapping(arms[0], f"control_specs.{kind}.arm"),
            )
            selected = dict(selected)
            nested = dict(_mapping(selected.get("intervention", {}), f"control_specs.{kind}.intervention"))
            nested.update(
                intervention_id=f"control-{kind}-{reference.source_coordinate_id}-{reference.target_coordinate_id}",
                source_coordinate_id=reference.source_coordinate_id,
                target_coordinate_id=reference.target_coordinate_id,
                target_kind=reference.target_kind,
            )
            selected["intervention"] = nested
            control_item = _control_intervention(kind, selected, reference, profile_obj)
            control_trajectory = _canonical_trajectory(control_item, profile_obj, advance)
            control_incident, control_source, control_partition = _work_from_item(control_item)
            control_row, control_raw = _transfer_row(
                control_item,
                profile_obj,
                control_trajectory,
                control_incident,
                control_source,
                control_partition,
            )
            control_raw_record = {
                "intervention_id": control_item.intervention_id,
                "trajectory": _plain(control_trajectory),
                "trajectory_sha256": control_raw["trajectory_sha256"],
                "endpoint_state_sha256": control_raw["endpoint_state_sha256"],
                "predecessor_state_sha256": control_raw["predecessor_state_sha256"],
                "byte_count": len(canonical_json_bytes(_plain(control_trajectory))),
                "canonical_advance": bool(control_item.canonical_advance),
                "excluded": control_row.excluded,
                "control_kind": kind,
            }
            raw_trajectories.append(control_raw_record)
            raw_trajectories_by_id[control_item.intervention_id] = control_raw_record
            intervention_hashes[control_item.intervention_id] = control_raw["trajectory_sha256"]
            control_records.append(
                _control_record(
                    kind,
                    treatment_hash=treatment_hash,
                    spec=selected,
                    item=control_item,
                    row=control_row,
                    raw=control_raw,
                    reference_row=reference_row,
                )
            )
    control_records.sort(key=lambda row: str(row["kind"]))
    for item, row in zip(items, rows):
        if row.control_kind != "treatment" or row.excluded:
            continue
        boundary.append(_transfer_payload(row, item, profile_obj, raw_trajectories_by_id[item.intervention_id], treatment_hash, control_records))
    transfer_hashes = [transfer["self_sha256"] for transfer in boundary]
    multimodal = _binding_payload(
        treatment_rows,
        [
            item
            for item in items
            if item.control_kind == "treatment"
            and not item.proposal
            and not item.reset
            and item.committed
            and item.acknowledged
        ],
        profile_obj,
        transfer_hashes,
        treatment_hash,
        control_records,
    )
    levels, classification = _capacity_levels(rows)
    partitions = {row.target_coordinate_id: _plain(row.work_partition) for row in rows}
    raw_table = {"rows": [row.payload() for row in rows], "sha256": _raw_sha([row.payload() for row in rows], "cassi.qi-flow-endpoint-transfer-table.v1"), "byte_count": len(canonical_json_bytes([row.payload() for row in rows]))}
    replay_identity = _sha({"profile_sha256": profile_obj.profile_sha256, "capacity_ladder_sha256": profile_obj.capacity_ladder_sha256, "controller_grammar_sha256": profile_obj.controller_grammar_sha256,
                           "physical_horizon": _plain(profile_obj.physical_horizon), "predecessor_state_sha256": profile_obj.predecessor_state_sha256,
                           "trajectories": intervention_hashes, "transfers": transfer_hashes}, "cassi.qi-flow-endpoint-replay.v1")
    verifier_inputs = {"profile": profile_obj.payload(), "raw_trajectories": raw_trajectories, "raw_transfer_table": raw_table, "boundary_transfer_receipts": boundary,
                       "multimodal_binding_receipts": [multimodal] if multimodal else [], "controls": control_records, "replay_identity": replay_identity}
    semantic = _semantic_parents(profile_obj.consumed_semantic_subhashes, profile_obj.payload())
    base = dict(profile_sha256=profile_obj.profile_sha256, capacity_ladder_sha256=profile_obj.capacity_ladder_sha256,
                controller_grammar_sha256=profile_obj.controller_grammar_sha256, physical_horizon=profile_obj.physical_horizon,
                predecessor_head_sha256=profile_obj.predecessor_head_sha256, predecessor_state_sha256=profile_obj.predecessor_state_sha256,
                transfer_rows=tuple(row.payload() for row in rows), boundary_transfer_receipts=tuple(boundary),
                multimodal_binding_receipts=(multimodal,) if multimodal else (), capacity_levels=levels, capacity_classification=classification,
                controls=tuple(control_records), partitions=partitions, raw_trajectories=tuple(raw_trajectories), raw_transfer_table=raw_table,
                verifier_inputs=verifier_inputs, consumed_semantic_subhashes=semantic, independent_replay_identity=replay_identity,
                fixture_sha256=_sha({"rows": [row.payload() for row in rows], "transfers": transfer_hashes}, "cassi.qi-flow-endpoint-fixture.v1"), receipt_id="")
    receipt_id = _sha({"profile_sha256": base["profile_sha256"], "independent_replay_identity": base["independent_replay_identity"], "capacity_levels": _plain(levels)}, "cassi.qi-flow-endpoint-receipt-id.v1")
    base["receipt_id"] = receipt_id
    receipt = QiEndpointCapacityReceipt(**base)
    self_hash = _sha(receipt.payload(), SCHEMA)
    return QiEndpointCapacityReceipt(**(base | {"self_sha256": self_hash}))


def _validate_transfer_payload(value: Mapping[str, Any], profile: Mapping[str, Any], *, expected_hash: str | None = None) -> None:
    required = {"schema", "contract_root_sha256", "profile_sha256", "consumed_semantic_subhashes", "transfer_id", "capacity_ladder_sha256", "controller_grammar_sha256", "clock_sha256", "predecessor_head_sha256", "predecessor_state_sha256", "source", "shared_context", "treatment_arm", "null_arm", "target_responses", "response_spectrum", "path_witnesses", "matched_controls", "capacity_classification", "fixture_sha256", "independent_replay_identity", "self_sha256"}
    if set(value) != required or value.get("schema") != BOUNDARY_TRANSFER_SCHEMA:
        _fail("boundary transfer keys/schema mismatch")
    for name in ("contract_root_sha256", "profile_sha256", "capacity_ladder_sha256", "controller_grammar_sha256", "clock_sha256", "predecessor_head_sha256", "predecessor_state_sha256", "fixture_sha256", "independent_replay_identity", "self_sha256"):
        _require_sha(value[name], f"transfer.{name}")
    if value["profile_sha256"] != profile["profile_sha256"] or value["capacity_ladder_sha256"] != profile["capacity_ladder_sha256"] or value["controller_grammar_sha256"] != profile["controller_grammar_sha256"]:
        _fail("boundary transfer dependency identity mismatch")
    if expected_hash is not None and value["self_sha256"] != expected_hash:
        _fail("boundary transfer hash mismatch")
    if _sha({k: value[k] for k in value if k != "self_sha256"}, TRANSFER_DOMAIN) != value["self_sha256"]:
        _fail("boundary transfer self hash mismatch")
    source = _mapping(value["source"], "transfer.source")
    for name in ("incident_work_interval", "admitted_work_interval"):
        work = _mapping(source[name], f"transfer.source.{name}")
        if _number(work, "lower") < 0.0 or _number(work, "value") < _number(work, "lower") or _number(work, "upper") < _number(work, "value"):
            _fail("transfer work is negative or unordered")
    context = _mapping(value["shared_context"], "transfer.shared_context")
    if _horizon(context["horizon"], "transfer horizon")["n"] < 1:
        _fail("transfer horizon invalid")
    responses = value["target_responses"]
    if not isinstance(responses, list) or not responses:
        _fail("transfer target response table is empty")
    if [row["target_coordinate_id"] for row in responses] != sorted(row["target_coordinate_id"] for row in responses):
        _fail("transfer responses are not sorted")
    if len(value["path_witnesses"]) != len(responses):
        _fail("transfer path witness coverage mismatch")
    if len(value["matched_controls"]) < len(_TRANSFER_CONTROL_KINDS) or {row["kind"] for row in value["matched_controls"]} < set(_TRANSFER_CONTROL_KINDS):
        _fail("transfer controls are incomplete")
    classification = _mapping(value["capacity_classification"], "transfer capacity classification")
    chain = ("geometric", "reachable", "observable", "usable", "retained", "reusable")
    if any(bool(classification[chain[i + 1]]) and not bool(classification[chain[i]]) for i in range(len(chain) - 1)):
        _fail("transfer capacity labels are not nested")
    for row in responses:
        kind = row.get("target_kind")
        if kind != "boundary_observation" and not _is_sha(row.get("committed_consequence_sha256")):
            _fail("non-boundary transfer lacks committed consequence")


def validate_endpoint_capacity_receipt(receipt: QiEndpointCapacityReceipt | Mapping[str, Any], *, profile: QiEndpointCapacityProfile | Mapping[str, Any] | None = None) -> QiEndpointCapacityReceipt:
    """Strictly validate an endpoint receipt without changing it."""
    if isinstance(receipt, QiEndpointCapacityReceipt):
        value = receipt.to_dict()
    else:
        value = _mapping(receipt, "receipt")
    required = {"schema", "profile_sha256", "capacity_ladder_sha256", "controller_grammar_sha256", "physical_horizon", "predecessor_head_sha256", "predecessor_state_sha256", "transfer_rows", "boundary_transfer_receipts", "multimodal_binding_receipts", "capacity_levels", "capacity_classification", "controls", "partitions", "raw_trajectories", "raw_transfer_table", "verifier_inputs", "consumed_semantic_subhashes", "independent_replay_identity", "fixture_sha256", "receipt_id", "self_sha256"}
    if set(value) != required or value.get("schema") != SCHEMA:
        _fail("endpoint receipt keys/schema mismatch")
    profile_map = _profile(profile).payload() if profile is not None else {"profile_sha256": value["profile_sha256"], "capacity_ladder_sha256": value["capacity_ladder_sha256"], "controller_grammar_sha256": value["controller_grammar_sha256"]}
    for name in ("profile_sha256", "capacity_ladder_sha256", "controller_grammar_sha256", "predecessor_head_sha256", "predecessor_state_sha256", "independent_replay_identity", "fixture_sha256", "self_sha256", "receipt_id"):
        _require_sha(value[name], f"receipt.{name}")
    if value["profile_sha256"] != profile_map["profile_sha256"] or value["capacity_ladder_sha256"] != profile_map["capacity_ladder_sha256"] or value["controller_grammar_sha256"] != profile_map["controller_grammar_sha256"]:
        _fail("endpoint dependency identity mismatch")
    if _sha({k: value[k] for k in value if k != "self_sha256"}, SCHEMA) != value["self_sha256"]:
        _fail("endpoint receipt self hash mismatch")
    if not isinstance(value["transfer_rows"], list) or not value["transfer_rows"]:
        _fail("endpoint transfer table is empty")
    levels = _mapping(value["capacity_levels"], "capacity levels")
    expected_levels = {"geometric", "reachable", "observable", "usable", "retained", "reusable"}
    if set(levels) != expected_levels or any(not isinstance(levels[k], int) or isinstance(levels[k], bool) or levels[k] < 0 for k in levels):
        _fail("capacity levels are invalid")
    if any(levels[left] < levels[right] for left, right in zip(("geometric", "reachable", "observable", "usable", "retained", "reusable"), ("reachable", "observable", "usable", "retained", "reusable", "reusable"))):
        # Last comparison is harmless and makes the chain explicit.
        _fail("capacity levels are not nested")
    rows = value["transfer_rows"]
    coordinate_keys = [(row.get("target_coordinate_id"), row.get("source_coordinate_id"), row.get("target_kind")) for row in rows]
    if coordinate_keys != sorted(coordinate_keys):
        _fail("endpoint transfer rows are not deterministically ordered")
    for row in rows:
        row = _mapping(row, "transfer row")
        if row.get("excluded") is not False and not row.get("null_predicates", {}).get("uncommitted", False):
            _fail("excluded endpoint row lacks uncommitted predicate")
        work = _mapping(row["source_work_interval"], "row source work")
        if _number(work, "lower") < 0.0:
            _fail("negative source work")
        nulls = _mapping(row.get("null_predicates"), "row null predicates")
        if bool(row.get("reusable")) and not bool(row.get("retained")):
            _fail("reusable row is not retained")
        if bool(row.get("retained")) and not bool(row.get("usable")):
            _fail("retained row is not usable")
        if bool(row.get("usable")) and not bool(row.get("observable")):
            _fail("usable row is not observable")
        if bool(row.get("observable")) and not bool(row.get("reachable")):
            _fail("observable row is not reachable")
        if bool(row.get("reachable")) and not bool(row.get("geometric")):
            _fail("reachable row is not geometric")
        if bool(row.get("reachable")) and bool(nulls.get("uncommitted")):
            _fail("uncommitted row counted as reachable")
    controls = value["controls"]
    kinds = {control.get("kind") for control in controls}
    required_controls = set(_CONTROL_KINDS)
    if not required_controls <= kinds:
        _fail("endpoint control registry is incomplete")
    for control in controls:
        if _sha({k: control[k] for k in control if k != "self_sha256"}, "cassi.qi-flow-endpoint-control.v1") != control.get("self_sha256"):
            _fail("control identity mismatch")
    raw_table = _mapping(value["raw_transfer_table"], "raw transfer table")
    if raw_table.get("sha256") != _raw_sha(raw_table.get("rows"), "cassi.qi-flow-endpoint-transfer-table.v1"):
        _fail("raw transfer table hash mismatch")
    for transfer in value["boundary_transfer_receipts"]:
        _validate_transfer_payload(transfer, profile_map)
    replay = _mapping(value["verifier_inputs"], "verifier inputs")
    if replay.get("replay_identity") != value["independent_replay_identity"]:
        _fail("independent replay input identity mismatch")
    return receipt if isinstance(receipt, QiEndpointCapacityReceipt) else QiEndpointCapacityReceipt(**{k: value[k] for k in value if k != "schema"})


def replay_endpoint_capacity_receipt(receipt: QiEndpointCapacityReceipt | Mapping[str, Any], *, profile: QiEndpointCapacityProfile | Mapping[str, Any] | None = None) -> QiEndpointCapacityReceipt:
    """Replay the immutable raw evidence and return the validated receipt."""
    validated = validate_endpoint_capacity_receipt(receipt, profile=profile)
    value = validated.to_dict()
    raw_rows = value["raw_transfer_table"]["rows"]
    if raw_rows != value["transfer_rows"]:
        _fail("raw transfer table does not replay transfer rows")
    for trajectory in value["raw_trajectories"]:
        raw = trajectory["trajectory"]
        if trajectory["trajectory_sha256"] != _raw_sha(raw, "cassi.qi-flow-endpoint-trajectory.v1") and not trajectory.get("excluded"):
            _fail("raw trajectory hash mismatch")
    if value["fixture_sha256"] != _sha({"rows": value["transfer_rows"], "transfers": [transfer["self_sha256"] for transfer in value["boundary_transfer_receipts"]]}, "cassi.qi-flow-endpoint-fixture.v1"):
        _fail("endpoint fixture hash mismatch")
    return validated


__all__ = [
    "EndpointCapacityError", "QiEndpointCapacityProfile", "QiEndpointIntervention", "QiEndpointTransferRow", "QiEndpointCapacityReceipt",
    "build_endpoint_capacity_receipt", "validate_endpoint_capacity_receipt", "replay_endpoint_capacity_receipt",
    "SCHEMA", "BOUNDARY_TRANSFER_SCHEMA", "MULTIMODAL_BINDING_SCHEMA",
]
