"""Section 18 circulation: canonical segment, bounded stage, flow geometry.

The living-memory upgrade gives Cassi one continuing large-scale flow that
organises smaller circulations and receives their feedback.  This module is the
numerical consumer of that design inside the existing resonant family:

* :func:`initial_circulation` builds the canonical circulation segment of one
  regional resonant task.  Its regions are the declared scale blocks of the
  one field; a block owns the aggregate (coarse) mode of its ports plus the
  remaining (detail) modes of those same ports, so no block duplicates another
  block's state and no port is counted twice by an exchange.
* :func:`circulation_unit` executes one bounded unit of a circulation pass:
  refresh the derived block views, exchange influence along every declared
  interface, retune axial orientation and reference phase, then close the pass
  with a measured geometry.  A unit is a resumable cursor, so a suspended pass
  resumes at the same interface with the same versions.
* :func:`circulation_readout` reports where the circulation lives and what it
  has spent without changing it, and :func:`circulation_activity` turns the
  measured geometry into bounded eligible-work modulation for the existing
  excitable automaton.  Modulation reorders already-eligible work only; it
  never makes an ineligible continuation eligible and is never evidence.

One exchange drives the parent position with the child momentum gradient and
the child momentum with the parent position gradient.  Both gradients are read
at the same version-bound stage, so the exchanged powers are equal and
opposite and the first-order work cancels; only the declared discrete
remainder is charged.  A remainder beyond its allowance halves the step and
retries before the stage is admitted, and an interface record that disagrees
with its own bound versions is refused rather than applied.

The segment stores declared parameters and derived scalars: block bounds,
interface list, stage versions, orientation frames, reference phases, flow
geometry, cursors, attention and work accounts.  The numeric block views
(``detail_coordinates``/``detail_momenta``) are derived quantities rebuilt from
the owned words on every refresh and on every closing measurement, so the
persisted segment never duplicates the field it describes.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_resonant_field import (
    ResonantExchangeStage,
    ResonantGeometryRecord,
    ResonantNumericalError,
    ResonantRegionRecord,
    ResonantStageMismatchError,
    _RegionalWaveOperator,
    _as_f64,
    _axis_projection,
    _regional_coordinates,
    _regional_objective_data,
    _regional_profile_data,
    _regional_transport,
    alignment_energy,
    alignment_gradients,
    alignment_step,
    contraction_rate_ratio,
    geometry_from_flow,
    metric_edge_weights,
    uniform_axial_divergence,
)

CIRCULATION_SCHEMA = "cassifi.resonant-circulation.v2"
_LEGACY_CIRCULATION_SCHEMA = "cassifi.resonant-circulation.v1"
CIRCULATION_STAGE_SCHEMA = "cassifi.resonant-circulation-stage.v1"
CIRCULATION_READOUT_SCHEMA = "cassifi.resonant-circulation-readout.v2"
CIRCULATION_ACTIVITY_SCHEMA = "cassifi.resonant-circulation-activity.v2"
CIRCULATION_MODULATION_AUTHORITY = "eligible-work-modulation-only"
CIRCULATION_ATTENTION_SCHEMA = "cassifi.resonant-attention.v1"
CIRCULATION_ROTATION_SCHEMA = "cassifi.resonant-frame-change.v1"
CIRCULATION_BASIS_VERSION = "block-haar-v1"
SPECTRAL_STATE_SCHEMA = "cassifi.resonant-spectrum.v3"
_PREVIOUS_SPECTRAL_STATE_SCHEMA = "cassifi.resonant-spectrum.v2"
_LEGACY_SPECTRAL_STATE_SCHEMA = "cassifi.resonant-spectrum.v1"
SPECTRAL_BASIS_VERSION = "operator-projected-block-haar.v2"
_PREVIOUS_SPECTRAL_BASIS_VERSION = "operator-projected-block-haar.v2"
_LEGACY_SPECTRAL_BASIS_VERSION = "operator-projected-block-haar.v1"
CIRCULATION_REGION_SCOPE = "resonant-scale"
CIRCULATION_STEP = 0.05
CIRCULATION_REMAINDER_FRACTION = 0.05
CIRCULATION_MAX_HALVINGS = 6
CIRCULATION_ATTENTION_STAGES = 32
CIRCULATION_DEFAULT_PASSES = 1
CIRCULATION_MAX_PASSES = 4096
CIRCULATION_VIEW_SOURCE = "rebuilt-on-refresh"
SPECTRAL_BANDWIDTH_RATIO = 0.25
SPECTRAL_MAX_LOG_SHIFT = math.log(2.0)
SPECTRAL_HISTORY_LIMIT = 32
SPECTRAL_CONCERN_LIMIT = 128

_CIRCULATION_KEYS = frozenset({
    "schema", "enabled", "basis", "views", "blocks", "regions", "edges",
    "stages", "geometry", "operator", "attention", "continuation", "ledger",
    "spectrum",
})
_LEGACY_CIRCULATION_KEYS = _CIRCULATION_KEYS - {"spectrum"}
_VIEW_KEYS = frozenset({"detail", "source"})
_CIRCULATION_LEDGER_KEYS = (
    "stages", "exchanges", "alignments", "derived_updates", "parameter_work",
    "interface_transfer_work", "interface_first_order_work",
    "interface_halvings", "interface_allowance", "interface_remainder",
    "alignment_energy",
)
_ATTENTION_KEYS = frozenset({
    "target", "admitted_stage", "progress", "remaining", "settled",
    "entry_threshold", "exit_threshold", "stage_limit", "retargets",
})
_GEOMETRY_KEYS = frozenset({
    "longitudinal_direction", "signed_current", "handedness", "kappa", "omega",
    "axial_speed", "angular_convention", "divergence", "degenerate", "coverage",
})
_OPERATOR_KEYS = frozenset({
    "digest", "dependencies", "declared_from", "residual", "edge_count",
})
_OPERATOR_DEPENDENCY_KEYS = (
    "profile_layout", "basis", "coordinate_count", "pools", "ports_per_pool",
    "topology", "coupling", "coordinates_digest", "volumes_digest",
)
_CONTINUATION_KEYS = frozenset({
    "pass", "cursor", "phase", "amplitude", "angle", "measured", "pending",
})
_REGION_KEYS = frozenset({
    "identity", "owner_scope", "parent_id", "basis_ref", "content_version",
    "coarse_coordinates", "detail_coordinates", "coarse_momenta",
    "detail_momenta", "axial_frame", "signed_current", "handedness",
    "relative_phases", "geometric_parameters", "coupling_ports",
    "endpoint_turnarounds", "interface_dependencies", "arithmetic_profile",
    "numerical_time", "integration_phase", "unfinished_work",
    "resource_accounts", "interface_work", "stale",
})
_SPECTRUM_KEYS = frozenset({
    "schema", "basis", "status", "reason", "operator_digest", "regions",
    "interfaces", "ledger", "last_exchange", "last_feedback", "history",
    "compatibility",
})
_SPECTRAL_REGION_KEYS = frozenset({
    "status", "reason", "frequencies", "coarse_mode", "detail_mode",
    "coarse_weight", "detail_weight", "basis_sha256", "operator_residual",
})
_SPECTRAL_INTERFACE_KEYS = frozenset({
    "status", "reason", "emitter_mode", "receiver_mode", "emitter_log_shift",
    "receiver_log_shift", "bandwidth_ratio", "tuning_updates",
    "last_appraisal_ref", "concern_tunings",
})
_LEGACY_SPECTRAL_INTERFACE_KEYS = _SPECTRAL_INTERFACE_KEYS - {"concern_tunings"}
_SPECTRAL_TUNING_KEYS = frozenset({
    "concern_ref", "appraisal_ref", "appraisal_basis", "progress",
    "receiver_log_shift", "updates", "parameter_work", "operator_digest",
})
_SPECTRAL_LEDGER_KEYS = frozenset({
    "exchanges", "transfer_work", "feedback_updates", "tuning_parameter_work",
})
_SPECTRAL_EXCHANGE_KEYS = frozenset({
    "interface", "status", "reason", "emitter_mode", "receiver_mode",
    "emitter_frequency", "receiver_frequency", "log_mismatch", "bandwidth",
    "overlap", "base_weight", "effective_weight", "physical_transfer_work",
    "parameter_work", "basis_sha256", "state_sha256",
    "effective_receiver_log_shift", "concern_ids", "operator_residual",
})
_LEGACY_SPECTRAL_EXCHANGE_KEYS = _SPECTRAL_EXCHANGE_KEYS - {
    "effective_receiver_log_shift", "concern_ids", "operator_residual",
}
_SPECTRAL_FEEDBACK_KEYS = frozenset({
    "interface", "appraisal_ref", "outcome", "progress", "before_shift",
    "after_shift", "source_frequency", "receiver_frequency", "direction",
    "parameter_work", "state_sha256", "concern_ref", "appraisal_basis",
    "operator_digest", "operator_residual", "effective_before_shift",
    "effective_after_shift", "mismatch_before", "mismatch_after",
    "potential_before", "potential_after",
})
_LEGACY_SPECTRAL_FEEDBACK_KEYS = _SPECTRAL_FEEDBACK_KEYS - {
    "concern_ref", "appraisal_basis", "operator_digest", "operator_residual",
    "effective_before_shift", "effective_after_shift", "mismatch_before",
    "mismatch_after", "potential_before", "potential_after",
}
_STAGE_KEYS = frozenset({"version", "parent_version", "child_version", "digest"})
_PHASES = ("refresh", "exchange", "align", "close")
# Declared relative scales of the canonical metric, one per kind.
_EDGE_SCALES = {"intra": 0.5, "intra-closed": 0.35, "neck": 0.7, "circuit": 1.0}

_EPSILON = float(np.finfo(np.float64).eps)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _plain(value: Any) -> Any:
    return json.loads(_canonical(value).decode("utf-8"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _number(value: Any, name: str, *, minimum: float | None = None,
            maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResonantNumericalError(f"{name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ResonantNumericalError(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise ResonantNumericalError(f"{name} is below its declared bound")
    if maximum is not None and result > maximum:
        raise ResonantNumericalError(f"{name} is above its declared bound")
    return result


def _integer(value: Any, name: str, *, minimum: int = 0,
             maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResonantNumericalError(f"{name} must be an integer")
    if value < minimum:
        raise ResonantNumericalError(f"{name} is below its declared bound")
    if maximum is not None and value > maximum:
        raise ResonantNumericalError(f"{name} is above its declared bound")
    return int(value)


# ---------------------------------------------------------------------------
# Declared scale blocks and interfaces.
# ---------------------------------------------------------------------------


def circulation_blocks(profile: Mapping[str, Any]) -> tuple[tuple[int, int], ...]:
    """The declared scale blocks: one disjoint port range per pool."""

    pools = int(profile["pools"])
    ports = int(profile["ports_per_pool"])
    return tuple((pool * ports, (pool + 1) * ports) for pool in range(pools))


def circulation_region_id(index: int) -> str:
    return f"scale-{index}"


def circulation_interfaces(profile: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """Declared exchanges: every block with its own detail, then each neck.

    A self interface couples one block's aggregate mode with its own detail
    modes; a neck interface couples two disjoint neighbouring blocks.  No
    interface overlaps port ranges, so an exchange cannot count one port twice.
    """

    count = len(circulation_blocks(profile))
    edges: list[tuple[str, str]] = [
        (circulation_region_id(index), circulation_region_id(index))
        for index in range(count)
    ]
    edges += [
        (circulation_region_id(index), circulation_region_id(index + 1))
        for index in range(count - 1)
    ]
    return tuple(edges)


def _circulation_basis(length: int) -> tuple[np.ndarray, np.ndarray]:
    """Coarse (aggregate) and first detail direction of one block."""

    if length <= 0:
        raise ResonantNumericalError("circulation block length must be positive")
    coarse = np.full(length, 1.0 / math.sqrt(length), dtype=np.float64)
    split = (length + 1) // 2
    left, right = split, length - split
    weights = np.concatenate((
        np.full(left, 1.0 / left, dtype=np.float64),
        np.full(right, -1.0 / right, dtype=np.float64),
    ))
    norm = float(np.linalg.norm(weights))
    if norm == 0.0:
        raise ResonantNumericalError("circulation detail direction is degenerate")
    return coarse, weights / norm


def _circulation_frame(direction: Any) -> np.ndarray:
    """A proper rotation whose first column is the declared axial direction."""

    axis = np.asarray(direction, dtype=np.float64).reshape(3)
    norm = float(np.linalg.norm(axis))
    if norm <= 1e-12:
        return np.eye(3)
    axis = axis / norm
    seed = np.eye(3)[int(np.argmin(np.abs(axis)))]
    companion = seed - axis * float(seed @ axis)
    length = float(np.linalg.norm(companion))
    if length <= 1e-12:
        raise ResonantNumericalError("circulation frame companion is degenerate")
    companion = companion / length
    third = np.cross(axis, companion)
    third = third / max(float(np.linalg.norm(third)), 1e-12)
    return np.stack((axis, companion, third), axis=1)


def _block_axis(coordinates: np.ndarray, first: int, last: int) -> np.ndarray:
    """Principal longitudinal direction of one block from the canonical metric."""

    points = np.asarray(coordinates, dtype=np.float64)[first:last]
    if len(points) < 2:
        return np.asarray([1.0, 0.0, 0.0], dtype=np.float64)
    centred = points - points.mean(axis=0)
    _values, vectors = np.linalg.eigh(centred.T @ centred)
    axis = vectors[:, -1]
    chord = points[-1] - points[0]
    if float(axis @ chord) < 0.0:
        axis = -axis
    return axis


def _phase(common: float, relative: float) -> float:
    if common == 0.0 and relative == 0.0:
        return 0.0
    return float(math.atan2(relative, common))


def _winding(words: np.ndarray, first: int, last: int) -> float:
    count = words.size // 4
    qy, qi = words[:count], words[count:2 * count]
    py, pi = words[2 * count:3 * count], words[3 * count:4 * count]
    return float(np.sum(qy[first:last] * pi[first:last] - qi[first:last] * py[first:last]))


def _block_span(raw: Mapping[str, Any]) -> tuple[int, int]:
    ports = raw["coupling_ports"]
    if not isinstance(ports, (list, tuple)) or len(ports) != 2:
        raise ResonantNumericalError("circulation region block is invalid")
    return int(ports[0]), int(ports[1])


# ---------------------------------------------------------------------------
# Records.
# ---------------------------------------------------------------------------


def _record_payload(record: ResonantRegionRecord) -> dict[str, Any]:
    return _plain(record.as_dict())


def _persisted(raw: Mapping[str, Any]) -> dict[str, Any]:
    """One region record in its persisted form: scalars, no rebuilt views."""

    payload = dict(raw)
    payload["detail_coordinates"] = []
    payload["detail_momenta"] = []
    return _plain(payload)


def circulation_record(profile: Mapping[str, Any], values: Any, *,
                       identity: str, first: int, last: int, parent: str | None,
                       axis: Any) -> ResonantRegionRecord:
    """One scale block's canonical record derived from the owned port words."""

    words = _as_f64(values, (4 * int(profile["pools"]) * int(profile["ports_per_pool"]),),
                    "circulation wave words")
    count = words.size // 4
    coarse, detail = _circulation_basis(last - first)
    common = (words[:count] + words[count:2 * count]) / math.sqrt(2.0)
    relative = (words[:count] - words[count:2 * count]) / math.sqrt(2.0)
    momentum_y, momentum_i = words[2 * count:3 * count], words[3 * count:4 * count]
    coarse_coordinates = np.asarray([
        float(coarse @ common[first:last]),
        float(coarse @ relative[first:last]),
    ], dtype=np.float64)
    coarse_momenta = np.asarray([
        float(coarse @ momentum_y[first:last]),
        float(coarse @ momentum_i[first:last]),
    ], dtype=np.float64)
    detail_coordinates = np.concatenate((
        common[first:last] - coarse_coordinates[0] * coarse,
        relative[first:last] - coarse_coordinates[1] * coarse,
    ))
    detail_momenta = np.concatenate((
        momentum_y[first:last] - coarse_momenta[0] * coarse,
        momentum_i[first:last] - coarse_momenta[1] * coarse,
    ))
    winding = _winding(words, first, last)
    scale = max(1.0, float(np.max(np.abs(words), initial=0.0)))
    handedness = 0 if abs(winding) <= 1e-12 * scale else (1 if winding > 0.0 else -1)
    signed_current = float(coarse @ ((momentum_y[first:last] + momentum_i[first:last])
                                     / math.sqrt(2.0)))
    detail_mode = float(detail @ (
        (words[:count][first:last] - words[count:2 * count][first:last]) / math.sqrt(2.0)
    ))
    return ResonantRegionRecord(
        identity=identity,
        owner_scope=CIRCULATION_REGION_SCOPE,
        parent_id=parent,
        basis_ref=CIRCULATION_BASIS_VERSION,
        coarse_coordinates=coarse_coordinates,
        detail_coordinates=detail_coordinates,
        coarse_momenta=coarse_momenta,
        detail_momenta=detail_momenta,
        axial_frame=_circulation_frame(axis),
        signed_current=signed_current,
        handedness=handedness,
        relative_phases={"self": _phase(coarse_coordinates[0], coarse_coordinates[1]),
                         "detail": detail_mode},
        geometric_parameters={"block": [first, last]},
        coupling_ports=(first, last),
        endpoint_turnarounds=(first, last),
        interface_dependencies=(),
        numerical_time=0.0,
        integration_phase="idle",
        unfinished_work={},
        resource_accounts={"exchanges": 0.0, "alignments": 0.0, "derived_updates": 0.0},
        interface_work=0.0,
        stale=False,
    )


def _region_record(raw: Mapping[str, Any]) -> ResonantRegionRecord:
    return ResonantRegionRecord(
        identity=str(raw["identity"]),
        **{key: value for key, value in raw.items() if key != "identity"},
    )


def _declared_edge_scales(topology: str, pools: int, ports: int,
                          count: int) -> dict[tuple[int, int], float]:
    """The declared structural rules of the canonical metric.

    Each declared rule admits an oriented index pair and carries a relative
    scale.  Scales accumulate with the same orientation convention as the
    canonical transport (an admitted ``source -> destination`` contributes its
    scale to ``(destination, source)`` and its negative to
    ``(source, destination)``), so a pair admitted by two rules of opposite
    orientation carries the difference of their scales.  This is the declared
    model of the canonical transport, re-derived from the profile's own layout
    description; the residual records how well it describes the transport the
    field actually integrates.
    """

    scales: dict[tuple[int, int], float] = {}
    admitted: dict[tuple[int, int], list[str]] = {}

    def admit(source: int, destination: int, kind: str, scale: float) -> None:
        if source == destination:
            return
        key = (source, destination)
        if kind in admitted.get(key, []):
            return
        admitted.setdefault(key, []).append(kind)
        scales[key] = scales.get(key, 0.0) + float(scale)
        mirror = (destination, source)
        scales[mirror] = scales.get(mirror, 0.0) - float(scale)

    if topology != "isolated":
        ring = list(range(count)) + list(range(2 * count - 1, count - 1, -1))
        for source, destination in zip(ring, ring[1:] + ring[:1]):
            admit(source, destination, "circuit", _EDGE_SCALES["circuit"])
    for pool in range(pools):
        start = pool * ports
        for local in range(ports - 1):
            admit(start + local, start + local + 1, "intra", _EDGE_SCALES["intra"])
        admit(start, start + ports - 1, "intra-closed", _EDGE_SCALES["intra-closed"])
    if topology != "isolated":
        for pool in range(pools - 1):
            admit(pool * ports + ports - 1, (pool + 1) * ports, "neck",
                  _EDGE_SCALES["neck"])
    return scales


def _operator_edges(profile: Mapping[str, Any]) -> dict[str, Any]:
    """The canonical sparse operator: measured weights plus declared estimate."""

    coordinates, volumes = _regional_coordinates(profile)
    transport = np.asarray(_regional_transport(profile), dtype=np.float64)
    pools = int(profile["pools"])
    ports = int(profile["ports_per_pool"])
    count = pools * ports
    coupling = float(profile["coupling"])
    mask = (transport != 0.0) | (transport.T != 0.0)
    sources, destinations = np.nonzero(np.triu(mask, k=1))
    pairs = [(int(source), int(destination))
             for source, destination in zip(sources.tolist(), destinations.tolist())]
    scales = _declared_edge_scales(str(profile["topology"]), pools, ports, count)
    estimated = np.zeros(len(pairs), dtype=np.float64)
    kinds: list[str] = []
    for index, (source, destination) in enumerate(pairs):
        scale = abs(scales.get((destination, source), 0.0))
        kinds.append("declared" if scale > 0.0 else "undeclared")
        if scale == 0.0:
            continue
        estimated[index] = float(metric_edge_weights(
            coordinates, [(source, destination)], volumes, scale=coupling * scale,
        )[0])
    rows = [
        [source, destination, abs(float(transport[destination, source])), kind]
        for (source, destination), kind in zip(pairs, kinds)
    ]
    residual = (0.0 if not pairs else float(np.max(np.abs(
        estimated - np.asarray([row[2] for row in rows], dtype=np.float64)
    ))))
    dependencies = {
        "profile_layout": str(profile.get("layout_identity", "")),
        "basis": CIRCULATION_BASIS_VERSION,
        "coordinate_count": int(coordinates.shape[0]),
        "pools": pools,
        "ports_per_pool": ports,
        "topology": str(profile["topology"]),
        "coupling": coupling,
        "coordinates_digest": _digest(coordinates.tolist()),
        "volumes_digest": _digest(np.asarray(volumes, dtype=np.float64).tolist()),
    }
    return {
        "digest": _digest({"edges": rows, "dependencies": dependencies}),
        "dependencies": dependencies,
        "edges": rows,
        "declared_from": "metric_edge_weights",
        "residual": residual,
    }


def _operator_record(table: Mapping[str, Any]) -> dict[str, Any]:
    """The persisted operator record: provenance and measured residual."""

    return _plain({
        "digest": table["digest"],
        "dependencies": table["dependencies"],
        "declared_from": table["declared_from"],
        "residual": float(table["residual"]),
        "edge_count": len(table["edges"]),
    })


def _operator_rows(profile: Mapping[str, Any], operator: _RegionalWaveOperator,
                   record: Mapping[str, Any]) -> list[Any]:
    """Rebuild the operator's edge table for one kernel call.

    The table is a derived view of the profile, so it is cached on the
    call-local operator instead of being carried in the task state; the
    recorded digest pins it to the segment's own canonical metric.
    """

    table = getattr(operator, "_circulation_operator", None)
    if table is None:
        table = _operator_edges(profile)
        setattr(operator, "_circulation_operator", table)
    if table["digest"] != record["digest"]:
        raise ResonantNumericalError(
            "the circulation segment does not belong to this profile's canonical metric"
        )
    return table["edges"]

def _initial_spectrum(region_ids: Sequence[str],
                      edges: Sequence[tuple[str, str]]) -> dict[str, Any]:
    reason = "the active operator spectrum is measured before exchange"
    return {
        "schema": SPECTRAL_STATE_SCHEMA,
        "basis": SPECTRAL_BASIS_VERSION,
        "status": "pending",
        "reason": reason,
        "operator_digest": None,
        "regions": {
            identity: {
                "status": "pending", "reason": reason, "frequencies": [],
                "coarse_mode": None, "detail_mode": None,
                "coarse_weight": 0.0, "detail_weight": 0.0,
                "basis_sha256": None, "operator_residual": None,
            }
            for identity in region_ids
        },
        "interfaces": {
            f"{parent}->{child}": {
                "status": "pending", "reason": reason, "emitter_mode": None,
                "receiver_mode": None, "emitter_log_shift": 0.0,
                "receiver_log_shift": 0.0,
                "bandwidth_ratio": SPECTRAL_BANDWIDTH_RATIO,
                "tuning_updates": 0, "last_appraisal_ref": None,
                "concern_tunings": {},
            }
            for parent, child in edges
        },
        "ledger": {
            "exchanges": 0.0, "transfer_work": 0.0,
            "feedback_updates": 0.0, "tuning_parameter_work": 0.0,
        },
        "last_exchange": None,
        "last_feedback": None,
        "history": [],
        "compatibility": None,
    }


def _spectral_operator_digest(operator: _RegionalWaveOperator,
                              circulation_operator: Mapping[str, Any]) -> str:
    """Hash the local Hamiltonian Hessian and inverse-mass dependencies."""

    arrays = {
        name: _digest(np.asarray(getattr(operator, name), dtype=np.float64).tolist())
        for name in ("transport", "inv_mass", "beta", "k")
    }
    arrays["ports"] = _digest(np.asarray(operator.ports, dtype=np.int64).tolist())
    arrays["constraints"] = _digest(
        np.asarray(operator.constraints, dtype=np.float64).tolist()
    )
    arrays["targets"] = _digest(np.asarray(operator.targets, dtype=np.float64).tolist())
    return _digest({
        "circulation_operator": circulation_operator["digest"],
        "arrays": arrays,
        "relative_stiffness": float(operator.profile["relative_stiffness"]),
        "constraint_count": int(len(operator.targets)),
        "basis": SPECTRAL_BASIS_VERSION,
    })


def _canonicalize_projected_modes(
    eigenvalues: np.ndarray, eigenvectors: np.ndarray, mass_root: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Give numerically degenerate modes a deterministic channel-aware basis."""

    values = np.asarray(eigenvalues, dtype=np.float64).copy()
    vectors = np.asarray(eigenvectors, dtype=np.float64).copy()
    tolerance = 64.0 * _EPSILON * max(
        1.0, float(np.max(np.abs(values), initial=0.0))
    )
    scale = max(
        float(np.linalg.norm(mass_root, ord=2)),
        float(np.finfo(np.float64).tiny),
    )
    projection_floor = 64.0 * _EPSILON * scale
    inv_sqrt_two = 1.0 / math.sqrt(2.0)
    targets = np.asarray([
        [inv_sqrt_two, inv_sqrt_two, 0.0, 0.0],
        [0.0, 0.0, inv_sqrt_two, inv_sqrt_two],
        [inv_sqrt_two, -inv_sqrt_two, 0.0, 0.0],
        [0.0, 0.0, inv_sqrt_two, -inv_sqrt_two],
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ], dtype=np.float64)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and abs(float(values[end] - values[end - 1])) <= tolerance:
            end += 1
        rank = end - start
        subspace = vectors[:, start:end].copy()
        if rank > 1:
            basis: list[np.ndarray] = []
            for target in targets:
                coefficients = subspace.T @ mass_root @ target
                for prior in basis:
                    coefficients -= prior * float(prior @ coefficients)
                norm = float(np.linalg.norm(coefficients))
                if norm > projection_floor:
                    basis.append(coefficients / norm)
                    if len(basis) == rank:
                        break
            if len(basis) != rank:
                raise ResonantNumericalError(
                    "degenerate projected modes lack a canonical basis"
                )
            vectors[:, start:end] = subspace @ np.column_stack(basis)
            values[start:end] = float(np.mean(values[start:end]))
        for mode in range(start, end):
            position = mass_root @ vectors[:, mode]
            pivot = int(np.argmax(np.abs(position)))
            if position[pivot] < 0.0:
                vectors[:, mode] *= -1.0
        start = end
    return values, vectors


def _projected_region_spectrum(operator: _RegionalWaveOperator, words: np.ndarray,
                               first: int, last: int) -> dict[str, Any]:
    """Project exact local energy curvature and inverse mass onto Haar modes."""

    if len(operator.targets) or np.any(np.asarray(operator.constraints) != 0.0):
        raise ResonantNumericalError(
            "active affine constraints have no declared projected spectral basis"
        )
    count = int(operator.n)
    if not 0 <= first < last <= count:
        raise ResonantNumericalError("spectral region bounds are outside the operator")
    coarse, detail = _circulation_basis(last - first)
    spatial = (coarse, detail)
    q_basis: list[tuple[int, int]] = [
        (spatial_index, lane)
        for spatial_index in range(2) for lane in range(2)
    ]
    current = _as_f64(words, (4 * count,), "spectral wave words")
    relative_state = (current[:count] - current[count:2 * count]) / math.sqrt(2.0)
    relative_curvature = (
        float(operator.profile["relative_stiffness"])
        + 3.0 * np.asarray(operator.beta, dtype=np.float64) * relative_state ** 2
    )
    hessian = np.zeros((4, 4), dtype=np.float64)
    inverse_mass = np.zeros((4, 4), dtype=np.float64)

    def q_projection(y: np.ndarray, i: np.ndarray) -> np.ndarray:
        return np.asarray([
            float(direction @ lane[first:last])
            for direction in spatial for lane in (y, i)
        ], dtype=np.float64)

    def p_projection(momentum: np.ndarray) -> np.ndarray:
        py, pi = momentum[:count], momentum[count:]
        return np.asarray([
            float(direction @ lane[first:last])
            for direction in spatial for lane in (py, pi)
        ], dtype=np.float64)

    for column, (spatial_index, lane) in enumerate(q_basis):
        dy = np.zeros(count, dtype=np.float64)
        di = np.zeros(count, dtype=np.float64)
        if lane == 0:
            dy[first:last] = spatial[spatial_index]
        else:
            di[first:last] = spatial[spatial_index]
        common = (dy + di) / math.sqrt(2.0)
        relative = (dy - di) / math.sqrt(2.0)
        semantic = np.asarray(operator.semantic(common, force=False), dtype=np.float64)
        operator.applications += 1
        rel_gradient = relative_curvature * relative
        grad_y = (semantic + rel_gradient) / math.sqrt(2.0)
        grad_i = (semantic - rel_gradient) / math.sqrt(2.0)
        hessian[:, column] = q_projection(grad_y, grad_i)

        momentum = np.zeros(2 * count, dtype=np.float64)
        if lane == 0:
            momentum[first:last] = spatial[spatial_index]
        else:
            momentum[count + first:count + last] = spatial[spatial_index]
        inverse_mass[:, column] = p_projection(np.asarray(
            operator.mass_apply(momentum), dtype=np.float64
        ))
        operator.applications += 1

    hessian = (hessian + hessian.T) * 0.5
    inverse_mass = (inverse_mass + inverse_mass.T) * 0.5
    mass_values, mass_vectors = np.linalg.eigh(inverse_mass)
    mass_tolerance = 64.0 * _EPSILON * max(
        1.0, float(np.max(np.abs(mass_values), initial=0.0))
    )
    if float(np.min(mass_values)) <= mass_tolerance:
        raise ResonantNumericalError(
            "projected inverse mass is not positive definite"
        )
    mass_root = (mass_vectors * np.sqrt(mass_values)) @ mass_vectors.T
    dynamical = mass_root @ hessian @ mass_root
    dynamical = (dynamical + dynamical.T) * 0.5
    eigenvalues, eigenvectors = np.linalg.eigh(dynamical)
    tolerance = 64.0 * _EPSILON * max(
        1.0, float(np.max(np.abs(eigenvalues), initial=0.0))
    )
    if float(np.min(eigenvalues)) <= tolerance:
        raise ResonantNumericalError(
            "projected active energy curvature is not positive definite"
        )
    eigenvalues, eigenvectors = _canonicalize_projected_modes(
        eigenvalues, eigenvectors, mass_root
    )
    residual_matrix = dynamical @ eigenvectors - eigenvectors * eigenvalues[None, :]
    operator_residual = float(
        np.linalg.norm(residual_matrix, ord=2)
        / max(1.0, float(np.linalg.norm(dynamical, ord=2)))
    )
    if not math.isfinite(operator_residual) or operator_residual > 1e-10:
        raise ResonantNumericalError("projected operator eigensolve residual is too large")
    frequencies = np.sqrt(eigenvalues)
    positions = mass_root @ eigenvectors
    coarse_weights: list[float] = []
    detail_weights: list[float] = []
    for mode in range(4):
        q = positions[:, mode]
        norm = max(float(q @ q), 1e-300)
        coarse_common = (q[0] + q[1]) / math.sqrt(2.0)
        detail_common = (q[2] + q[3]) / math.sqrt(2.0)
        coarse_weights.append(float(min(1.0, coarse_common * coarse_common / norm)))
        detail_weights.append(float(min(1.0, detail_common * detail_common / norm)))
    coarse_mode = int(np.argmax(coarse_weights))
    detail_mode = int(np.argmax(detail_weights))
    if max(coarse_weights) < 0.25 or max(detail_weights) < 0.25:
        raise ResonantNumericalError(
            "projected local modes do not resolve coarse and detail channels"
        )
    basis_digest = _digest({
        "hessian": hessian.tolist(),
        "inverse_mass": inverse_mass.tolist(),
        "frequencies": frequencies.tolist(),
        "mode_vectors": eigenvectors.tolist(),
        "operator_residual": operator_residual,
    })
    return {
        "status": "available", "reason": None,
        "frequencies": [float(value) for value in frequencies],
        "coarse_mode": coarse_mode, "detail_mode": detail_mode,
        "coarse_weight": float(coarse_weights[coarse_mode]),
        "detail_weight": float(detail_weights[detail_mode]),
        "basis_sha256": basis_digest,
        "operator_residual": operator_residual,
    }


def _append_spectral_history(spectrum: dict[str, Any],
                             event: Mapping[str, Any]) -> None:
    history = list(spectrum["history"])
    history.append(_plain(event))
    spectrum["history"] = history[-SPECTRAL_HISTORY_LIMIT:]


def _upgrade_spectrum(spectrum: Mapping[str, Any]) -> dict[str, Any]:
    """Upgrade persisted spectral state while retaining supported attribution."""
    upgraded = _plain(spectrum)
    version = upgraded.get("schema")
    basis = upgraded.get("basis")
    if (version, basis) not in {
        (SPECTRAL_STATE_SCHEMA, SPECTRAL_BASIS_VERSION),
        (_PREVIOUS_SPECTRAL_STATE_SCHEMA, _PREVIOUS_SPECTRAL_BASIS_VERSION),
        (_LEGACY_SPECTRAL_STATE_SCHEMA, _LEGACY_SPECTRAL_BASIS_VERSION),
    }:
        raise ResonantNumericalError("spectral state schema or basis version is invalid")
    if version == SPECTRAL_STATE_SCHEMA:
        return upgraded
    for row in upgraded["interfaces"].values():
        row.setdefault("concern_tunings", {})
    if isinstance(upgraded.get("last_exchange"), Mapping):
        upgraded["last_exchange"].setdefault("effective_receiver_log_shift", None)
        upgraded["last_exchange"].setdefault("concern_ids", [])
        upgraded["last_exchange"].setdefault("operator_residual", None)
    if isinstance(upgraded.get("last_feedback"), Mapping):
        upgraded["last_feedback"].update({
            "concern_ref": None,
            "appraisal_basis": None,
            "operator_digest": upgraded.get("operator_digest"),
            "operator_residual": None,
            "effective_before_shift": None,
            "effective_after_shift": None,
            "mismatch_before": None,
            "mismatch_after": None,
            "potential_before": None,
            "potential_after": None,
        })
    upgraded["schema"] = SPECTRAL_STATE_SCHEMA
    upgraded["basis"] = SPECTRAL_BASIS_VERSION
    return upgraded


def _ensure_spectrum(segment: dict[str, Any], operator: _RegionalWaveOperator,
                     words: np.ndarray) -> dict[str, Any]:
    """Initialize or invalidate the persisted basis before an exchange."""

    spectrum = segment.get("spectrum")
    upgraded = False
    if spectrum is None:
        spectrum = _initial_spectrum(
            tuple(segment["regions"]),
            tuple(tuple(edge) for edge in segment["edges"]),
        )
        segment["spectrum"] = spectrum
    elif isinstance(spectrum, Mapping):
        upgraded = spectrum.get("schema") != SPECTRAL_STATE_SCHEMA
        spectrum = _upgrade_spectrum(spectrum)
        segment["spectrum"] = spectrum
    else:
        raise ResonantNumericalError("spectral state is invalid")
    signature = _spectral_operator_digest(operator, segment["operator"])
    if (
        not upgraded and spectrum["operator_digest"] == signature
        and spectrum["status"] != "pending"
    ):
        return spectrum
    prior_digest = spectrum["operator_digest"]
    compatible = prior_digest in (None, signature)
    operator_reason = None
    region_rows: dict[str, Any] = {}
    for identity, raw in _sorted_regions(segment):
        first, last = _block_span(raw)
        try:
            region_rows[identity] = _projected_region_spectrum(
                operator, words, first, last
            )
        except (ResonantNumericalError, np.linalg.LinAlgError) as exc:
            region_rows[identity] = {
                "status": "unavailable", "reason": str(exc), "frequencies": [],
                "coarse_mode": None, "detail_mode": None,
                "coarse_weight": 0.0, "detail_weight": 0.0,
                "basis_sha256": None, "operator_residual": None,
            }
            operator_reason = str(exc)
    interfaces: dict[str, Any] = {}
    for parent, child in (tuple(edge) for edge in segment["edges"]):
        key = f"{parent}->{child}"
        prior = spectrum["interfaces"].get(key, {})
        emitter = region_rows[parent]
        receiver = region_rows[child]
        if emitter["status"] == "available" and receiver["status"] == "available":
            interfaces[key] = {
                "status": "available", "reason": None,
                "emitter_mode": int(emitter["coarse_mode"]),
                "receiver_mode": int(receiver[
                    "detail_mode" if parent == child else "coarse_mode"
                ]),
                "emitter_log_shift": (
                    float(prior.get("emitter_log_shift", 0.0)) if compatible else 0.0
                ),
                "receiver_log_shift": (
                    float(prior.get("receiver_log_shift", 0.0)) if compatible else 0.0
                ),
                "bandwidth_ratio": float(prior.get(
                    "bandwidth_ratio", SPECTRAL_BANDWIDTH_RATIO
                )),
                "tuning_updates": (
                    int(prior.get("tuning_updates", 0)) if compatible else 0
                ),
                "last_appraisal_ref": (
                    _plain(prior["last_appraisal_ref"])
                    if compatible and prior.get("last_appraisal_ref") is not None
                    else None
                ),
                "concern_tunings": (
                    _plain(prior.get("concern_tunings", {}))
                    if compatible else {}
                ),
            }
        else:
            reason = emitter["reason"] or receiver["reason"]
            interfaces[key] = {
                "status": "unavailable", "reason": reason,
                "emitter_mode": None, "receiver_mode": None,
                "emitter_log_shift": 0.0, "receiver_log_shift": 0.0,
                "bandwidth_ratio": SPECTRAL_BANDWIDTH_RATIO,
                "tuning_updates": 0, "last_appraisal_ref": None,
                "concern_tunings": {},
            }
    available = sum(row["status"] == "available" for row in region_rows.values())
    status = ("available" if available == len(region_rows) else
              "partial" if available else "unavailable")
    if status == "available":
        reason = None
    elif status == "partial":
        reason = "one or more regional operator spectra are unavailable"
    else:
        reason = operator_reason or "no regional operator spectrum is available"
    spectrum.update({
        "schema": SPECTRAL_STATE_SCHEMA, "basis": SPECTRAL_BASIS_VERSION,
        "status": status, "reason": reason, "operator_digest": signature,
        "regions": region_rows, "interfaces": interfaces,
    })
    if not compatible:
        spectrum["last_exchange"] = None
        spectrum["last_feedback"] = None
        spectrum["compatibility"] = {
            "from_operator_digest": prior_digest,
            "to_operator_digest": signature,
            "reason": "operator basis changed; spectral tuning was reset",
        }
    return spectrum



def _effective_receiver_log_shift(link: Mapping[str, Any]) -> float:
    """Bound the base shift plus independent concern-specific shifts."""
    shift = float(link["receiver_log_shift"])
    tunings = link.get("concern_tunings", {})
    if isinstance(tunings, Mapping):
        shift += sum(
            float(tuning["receiver_log_shift"])
            for tuning in tunings.values()
        )
    return max(-SPECTRAL_MAX_LOG_SHIFT, min(SPECTRAL_MAX_LOG_SHIFT, shift))


def _spectral_exchange_factor(segment: dict[str, Any],
                              operator: _RegionalWaveOperator, words: np.ndarray,
                              parent: str, child: str) -> dict[str, Any]:
    spectrum = _ensure_spectrum(segment, operator, words)
    key = f"{parent}->{child}"
    link = spectrum["interfaces"][key]
    if link["status"] != "available":
        return {"status": "unavailable", "reason": link["reason"],
                "factor": 1.0, "interface": key}
    fresh: dict[str, dict[str, Any]] = {}
    for identity in {parent, child}:
        first, last = _block_span(segment["regions"][identity])
        try:
            fresh[identity] = _projected_region_spectrum(
                operator, words, first, last
            )
        except (ResonantNumericalError, np.linalg.LinAlgError) as exc:
            link["status"], link["reason"] = "unavailable", str(exc)
            return {"status": "unavailable", "reason": str(exc),
                    "factor": 1.0, "interface": key}
        spectrum["regions"][identity] = fresh[identity]
    emitter = fresh[parent]
    receiver = fresh[child]
    emitter_mode = int(emitter["coarse_mode"])
    receiver_mode = int(receiver[
        "detail_mode" if parent == child else "coarse_mode"
    ])
    effective_receiver_shift = _effective_receiver_log_shift(link)
    emitter_frequency = float(emitter["frequencies"][emitter_mode]) * math.exp(
        float(link["emitter_log_shift"])
    )
    receiver_frequency = float(receiver["frequencies"][receiver_mode]) * math.exp(
        effective_receiver_shift
    )
    mismatch = math.log(emitter_frequency / receiver_frequency)
    bandwidth = float(link["bandwidth_ratio"])
    overlap = 1.0 / (1.0 + (mismatch / bandwidth) ** 2)
    operator_residual = max(
        float(emitter["operator_residual"]), float(receiver["operator_residual"])
    )
    basis_sha = _digest({
        "emitter": emitter["basis_sha256"], "receiver": receiver["basis_sha256"],
        "operator": spectrum["operator_digest"],
        "operator_residual": operator_residual,
    })
    return {
        "status": "available", "reason": None, "interface": key,
        "factor": float(overlap), "emitter_mode": emitter_mode,
        "receiver_mode": receiver_mode, "emitter_frequency": emitter_frequency,
        "receiver_frequency": receiver_frequency, "log_mismatch": mismatch,
        "bandwidth": bandwidth, "overlap": float(overlap),
        "basis_sha256": basis_sha,
        "effective_receiver_log_shift": effective_receiver_shift,
        "concern_ids": sorted(link.get("concern_tunings", {})),
        "operator_residual": operator_residual,
    }

def _record_spectral_exchange(segment: dict[str, Any], trace: Mapping[str, Any], *,
                              base_weight: float, effective_weight: float,
                              physical_transfer_work: float,
                              words: np.ndarray) -> dict[str, Any]:
    spectrum = segment["spectrum"]
    ledger = dict(spectrum["ledger"])
    ledger["exchanges"] = float(ledger["exchanges"]) + 1.0
    ledger["transfer_work"] = float(ledger["transfer_work"]) + float(
        physical_transfer_work
    )
    spectrum["ledger"] = ledger
    available = trace["status"] == "available"
    record = {
        "interface": str(trace["interface"]),
        "status": "available" if available else "unavailable",
        "reason": None if available else str(trace["reason"]),
        "emitter_mode": trace.get("emitter_mode"),
        "receiver_mode": trace.get("receiver_mode"),
        "emitter_frequency": trace.get("emitter_frequency"),
        "receiver_frequency": trace.get("receiver_frequency"),
        "log_mismatch": trace.get("log_mismatch"),
        "bandwidth": float(trace.get("bandwidth", SPECTRAL_BANDWIDTH_RATIO)),
        "overlap": float(trace.get("overlap", 1.0)),
        "base_weight": float(base_weight),
        "effective_weight": float(effective_weight),
        "physical_transfer_work": float(physical_transfer_work),
        "parameter_work": 0.0,
        "basis_sha256": trace.get("basis_sha256"),
        "state_sha256": _digest(words.tolist()),
        "effective_receiver_log_shift": trace.get("effective_receiver_log_shift"),
        "concern_ids": list(trace.get("concern_ids", [])),
        "operator_residual": trace.get("operator_residual"),
    }
    spectrum["last_exchange"] = record
    _append_spectral_history(spectrum, {
        "kind": "exchange", "digest": _digest(record),
        "interface": record["interface"], "sequence": int(ledger["exchanges"]),
    })
    return record


def _interface_weights(rows: Sequence[Any], profile: Mapping[str, Any],
                       blocks: Mapping[str, tuple[int, int]], parent: str,
                       child: str) -> dict[str, Any]:
    """The measured transfer of one declared interface.

    A self interface transfers between one block's aggregate mode and its own
    first detail mode; a neck interface transfers between two blocks'
    aggregate modes.  Both are rank-one operators whose weight is the measured
    mean coupling of the interface's own edge set.
    """

    count = int(profile["pools"]) * int(profile["ports_per_pool"])
    first, last = blocks[parent]
    other_first, other_last = blocks[child]

    def inside(index: int, span: tuple[int, int]) -> bool:
        port = index % count
        return span[0] <= port < span[1]

    selected = [
        row for row in rows
        if (inside(row[0], (first, last)) and inside(row[1], (other_first, other_last)))
        or (inside(row[1], (first, last)) and inside(row[0], (other_first, other_last)))
    ]
    weight = float(np.mean([abs(float(row[2])) for row in selected])) if selected else 0.0
    if parent == child:
        coarse, detail = _circulation_basis(last - first)
        return {"kind": "self", "weight": weight, "parent_direction": coarse,
                "child_direction": detail, "span": [first, last],
                "edges": len(selected)}
    parent_basis, _ = _circulation_basis(last - first)
    child_basis, _ = _circulation_basis(other_last - other_first)
    return {"kind": "neck", "weight": weight, "parent_direction": parent_basis,
            "child_direction": child_basis, "span": [first, last],
            "edges": len(selected)}


def _geometry_payload(profile: Mapping[str, Any], regions: Mapping[str, Any],
                      previous: Mapping[str, Any] | None,
                      operator: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Measure the canonical geometry of the current block records."""

    selected = [_region_record(raw) for _identity, raw in sorted(regions.items())]
    axes = np.asarray([record.axial_frame[:, 0] for record in selected], dtype=np.float64)
    total_current = float(sum(record.signed_current for record in selected))
    prior = None
    if isinstance(previous, Mapping) and previous.get("longitudinal_direction") is not None:
        prior = _circulation_frame(previous["longitudinal_direction"])
    projection = _axis_projection(axes, signed_current=total_current, prior_frame=prior)
    coverage = (0.0 if not selected
                else sum(not record.stale for record in selected) / len(selected))
    winding = float(sum(record.handedness * abs(record.signed_current) for record in selected))
    scale = max(1.0, float(sum(abs(record.signed_current) for record in selected)))
    handedness = 0 if abs(winding) <= 1e-12 * scale else (1 if winding > 0.0 else -1)
    resolved = bool(projection["resolved"])
    direction = (np.asarray([0.0, 0.0, 1.0], dtype=np.float64) if not resolved
                 else np.asarray(projection["axis"], dtype=np.float64))
    amplitude = float(sum(
        math.hypot(float(record.coarse_coordinates[0]), float(record.coarse_coordinates[1]))
        for record in selected
    ))
    common = float(sum(float(record.coarse_coordinates[0]) for record in selected))
    relative = float(sum(float(record.coarse_coordinates[1]) for record in selected))
    angle = _phase(common, relative)
    duration = float(profile["time_step"])
    kappa = 0.0
    omega = 1.0
    axial_speed = 0.0
    degenerate = not resolved
    if isinstance(previous, Mapping) and duration > 0.0:
        prior_amplitude = float(previous.get("amplitude", 0.0))
        prior_angle = float(previous.get("angle", angle))
        prior_current = float(previous.get("signed_current", total_current))
        if prior_amplitude > 0.0 and amplitude > 0.0:
            kappa = max(0.0, -0.5 * math.log(amplitude / prior_amplitude) / duration)
        delta = math.remainder(angle - prior_angle, 2.0 * math.pi)
        if delta != 0.0:
            omega = abs(delta) / duration
        else:
            degenerate = True
        axial_speed = (total_current - prior_current) / duration
    payload = {
        "longitudinal_direction": direction.tolist(),
        "signed_current": total_current,
        "handedness": int(handedness),
        "kappa": float(kappa),
        "omega": float(omega),
        "axial_speed": float(axial_speed),
        "angular_convention": "quarter-turn",
        "divergence": float(uniform_axial_divergence(kappa)),
        "degenerate": bool(degenerate),
        "coverage": float(coverage),
    }
    measured = {
        "amplitude": amplitude,
        "angle": angle,
        "signed_current": total_current,
        "longitudinal_direction": direction.tolist(),
        "derived_from": "measured-block-aggregates",
        "operator_digest": operator["digest"],
    }
    return payload, measured


def _geometry_record(payload: Mapping[str, Any]) -> ResonantGeometryRecord:
    return geometry_from_flow(
        payload["longitudinal_direction"],
        signed_current=float(payload["signed_current"]),
        handedness=int(payload["handedness"]),
        kappa=float(payload["kappa"]),
        omega=float(payload["omega"]),
        axial_speed=float(payload["axial_speed"]),
        angular_convention=str(payload["angular_convention"]),
    )


def initial_circulation(profile: Mapping[str, Any], *, enabled: bool = False,
                        words: Any = None) -> dict[str, Any]:
    """The declared circulation segment of one regional resonant task."""

    selected = _regional_profile_data(profile)
    count = int(selected["pools"]) * int(selected["ports_per_pool"])
    values = (np.zeros(4 * count, dtype=np.float64) if words is None
              else _as_f64(words, (4 * count,), "circulation wave words"))
    coordinates, _volumes = _regional_coordinates(selected)
    blocks = circulation_blocks(selected)
    regions: dict[str, Any] = {}
    for index, (first, last) in enumerate(blocks):
        identity = circulation_region_id(index)
        record = circulation_record(
            selected, values, identity=identity, first=first, last=last,
            parent=None if index == 0 else circulation_region_id(index - 1),
            axis=_block_axis(coordinates, first, last),
        )
        regions[identity] = _persisted(_record_payload(record))
    operator = _operator_edges(selected)
    edges = circulation_interfaces(selected)
    stages: dict[str, Any] = {}
    for parent, child in edges:
        stage = ResonantExchangeStage.bind(f"{parent}@0", f"{child}@0", version="stage-0")
        stages[f"{parent}->{child}"] = {
            "version": stage.version, "parent_version": stage.parent_version,
            "child_version": stage.child_version, "digest": stage.digest,
        }
    geometry, _measured = _geometry_payload(selected, regions, None, operator)
    return _plain({
        "schema": CIRCULATION_SCHEMA,
        "enabled": bool(enabled),
        "basis": CIRCULATION_BASIS_VERSION,
        "views": {"detail": CIRCULATION_VIEW_SOURCE, "source": "state.wave_words"},
        "blocks": [list(block) for block in blocks],
        "regions": regions,
        "edges": [list(edge) for edge in edges],
        "stages": stages,
        "geometry": geometry,
        "operator": _operator_record(operator),
        "spectrum": _initial_spectrum(tuple(regions), edges),
        "attention": {
            "target": None, "admitted_stage": None, "progress": 0.0,
            "remaining": 0, "settled": True, "entry_threshold": 0.25,
            "exit_threshold": 0.1, "stage_limit": CIRCULATION_ATTENTION_STAGES,
            "retargets": 0,
        },
        "continuation": {
            "pass": 0, "cursor": 0, "phase": "refresh",
            "amplitude": 0.0, "angle": 0.0, "measured": False, "pending": 0,
        },
        "ledger": {key: 0.0 for key in _CIRCULATION_LEDGER_KEYS},
    })


def attach_measured(segment: dict[str, Any], measured: Mapping[str, Any]) -> None:
    """Record one measured geometry cursor on the segment's continuation."""

    continuation = dict(segment["continuation"])
    continuation["amplitude"] = float(measured["amplitude"])
    continuation["angle"] = float(measured["angle"])
    continuation["measured"] = True
    segment["continuation"] = continuation


def circulation_defer_unit(segment: dict[str, Any]) -> int:
    """Declare one completed field tick whose circulation unit has not run.

    A bounded dispatch that spends its whole work allowance on field ticks
    still owes each completed tick its circulation unit.  The debt is carried
    on the segment's own continuation, so it survives the dispatch, stays
    visible in the readout, and is discharged before further field work.
    """

    continuation = dict(segment["continuation"])
    continuation["pending"] = int(continuation["pending"]) + 1
    segment["continuation"] = continuation
    return int(continuation["pending"])


def circulation_take_pending(segment: dict[str, Any]) -> int:
    """Discharge one deferred circulation unit; returns the remaining debt."""

    continuation = dict(segment["continuation"])
    continuation["pending"] = max(0, int(continuation["pending"]) - 1)
    segment["continuation"] = continuation
    return int(continuation["pending"])




def _validate_semantic_ref(value: Any, label: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if (
        not isinstance(value, Mapping)
        or set(value) != {"id", "kind", "content_version"}
        or not isinstance(value.get("id"), str)
        or not isinstance(value.get("kind"), str)
        or isinstance(value.get("content_version"), bool)
        or not isinstance(value.get("content_version"), int)
        or value["content_version"] < 1
    ):
        raise ResonantNumericalError(f"{label} is not a versioned semantic reference")


def _validate_concern_ref(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value) != {
            "concern_id", "project_id", "question_ref", "object_refs", "goal_ref",
        }
        or not isinstance(value.get("project_id"), str)
        or not value["project_id"]
        or not isinstance(value.get("concern_id"), str)
        or len(value["concern_id"]) != 64
    ):
        raise ResonantNumericalError("spectral concern reference is invalid")
    question_ref, goal_ref = value["question_ref"], value["goal_ref"]
    _validate_semantic_ref(question_ref, "spectral concern question_ref", nullable=True)
    _validate_semantic_ref(goal_ref, "spectral concern goal_ref", nullable=True)
    object_refs = value["object_refs"]
    if not isinstance(object_refs, Sequence) or isinstance(object_refs, (str, bytes)):
        raise ResonantNumericalError("spectral concern object_refs are invalid")
    checked_objects = []
    for ref in object_refs:
        _validate_semantic_ref(ref, "spectral concern object_ref")
        checked_objects.append(dict(ref))
    keys = [(ref["id"], ref["kind"], ref["content_version"]) for ref in checked_objects]
    if keys != sorted(set(keys)):
        raise ResonantNumericalError("spectral concern object_refs must be sorted and unique")
    identity = {
        "project_id": value["project_id"],
        "question_id": None if question_ref is None else question_ref["id"],
        "object_ids": sorted({ref["id"] for ref in checked_objects}),
        "goal_id": None if goal_ref is None else goal_ref["id"],
    }
    if _digest(identity) != value["concern_id"]:
        raise ResonantNumericalError("spectral concern identity does not match its bindings")
    return _plain(value)


def _validate_appraisal_basis(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value) != {"assessment_ref", "source_revision_id", "source_sha256"}
        or not isinstance(value.get("source_revision_id"), str)
        or not value["source_revision_id"]
        or not isinstance(value.get("source_sha256"), str)
        or len(value["source_sha256"]) != 64
    ):
        raise ResonantNumericalError("spectral appraisal basis is invalid")
    _validate_semantic_ref(value["assessment_ref"], "spectral assessment_ref")
    if value["assessment_ref"]["kind"] != "Assessment":
        raise ResonantNumericalError("spectral appraisal basis must bind an Assessment")
    return _plain(value)
def _validate_spectrum(segment: Mapping[str, Any]) -> None:
    spectrum = segment["spectrum"]
    if not isinstance(spectrum, Mapping) or set(spectrum) != _SPECTRUM_KEYS:
        raise ResonantNumericalError("spectral state keys are invalid")
    schema = spectrum["schema"]
    basis = spectrum["basis"]
    if (schema, basis) not in {
        (SPECTRAL_STATE_SCHEMA, SPECTRAL_BASIS_VERSION),
        (_PREVIOUS_SPECTRAL_STATE_SCHEMA, _PREVIOUS_SPECTRAL_BASIS_VERSION),
        (_LEGACY_SPECTRAL_STATE_SCHEMA, _LEGACY_SPECTRAL_BASIS_VERSION),
    }:
        raise ResonantNumericalError("spectral state schema or basis version is invalid")
    current_schema = schema == SPECTRAL_STATE_SCHEMA
    legacy_modes = schema == _LEGACY_SPECTRAL_STATE_SCHEMA
    if spectrum["status"] not in {"pending", "available", "partial", "unavailable"}:
        raise ResonantNumericalError("spectral state status is invalid")
    if spectrum["reason"] is not None and not isinstance(spectrum["reason"], str):
        raise ResonantNumericalError("spectral state reason is invalid")
    operator_digest = spectrum["operator_digest"]
    if operator_digest is not None and (
            not isinstance(operator_digest, str) or len(operator_digest) != 64):
        raise ResonantNumericalError("spectral operator digest is invalid")
    regions = spectrum["regions"]
    if not isinstance(regions, Mapping) or set(regions) != set(segment["regions"]):
        raise ResonantNumericalError("spectral region rows are incomplete")
    for identity, row in regions.items():
        region_keys = _SPECTRAL_REGION_KEYS if current_schema else (
            _SPECTRAL_REGION_KEYS - {"operator_residual"}
        )
        if not isinstance(row, Mapping) or set(row) != region_keys:
            raise ResonantNumericalError("spectral region keys are invalid")
        status = row["status"]
        if status not in {"pending", "available", "unavailable"}:
            raise ResonantNumericalError("spectral region status is invalid")
        if row["reason"] is not None and not isinstance(row["reason"], str):
            raise ResonantNumericalError("spectral region reason is invalid")
        frequencies = row["frequencies"]
        if not isinstance(frequencies, list):
            raise ResonantNumericalError("spectral frequencies are invalid")
        if status == "available":
            if len(frequencies) != 4:
                raise ResonantNumericalError("available spectrum requires four modes")
            checked = [_number(value, "spectral frequency", minimum=0.0)
                       for value in frequencies]
            if (any(value <= 0.0 for value in checked)
                    or any(left > right for left, right in zip(checked, checked[1:]))
                    or (legacy_modes and any(
                        left >= right for left, right in zip(checked, checked[1:])
                    ))):
                raise ResonantNumericalError("spectral frequencies are not positive and ordered")
            for key in ("coarse_mode", "detail_mode"):
                _integer(row[key], f"spectral {key}", maximum=3)
            for key in ("coarse_weight", "detail_weight"):
                _number(row[key], f"spectral {key}", minimum=0.0, maximum=1.0)
            if not isinstance(row["basis_sha256"], str) or len(row["basis_sha256"]) != 64:
                raise ResonantNumericalError("spectral region basis digest is invalid")
            if current_schema:
                _number(row["operator_residual"], "spectral operator residual",
                        minimum=0.0, maximum=1e-10)
        elif (frequencies or row["coarse_mode"] is not None
              or row["detail_mode"] is not None or row["basis_sha256"] is not None):
            raise ResonantNumericalError("unavailable spectral region carries active modes")
        if current_schema and status != "available" and row["operator_residual"] is not None:
            raise ResonantNumericalError("unavailable spectrum carries an operator residual")
    interfaces = spectrum["interfaces"]
    expected_interfaces = {f"{parent}->{child}"
                           for parent, child in map(tuple, segment["edges"])}
    if not isinstance(interfaces, Mapping) or set(interfaces) != expected_interfaces:
        raise ResonantNumericalError("spectral interface rows are incomplete")
    for key, row in interfaces.items():
        interface_keys = _SPECTRAL_INTERFACE_KEYS if current_schema else (
            _SPECTRAL_INTERFACE_KEYS - {"concern_tunings"}
        )
        if not isinstance(row, Mapping) or set(row) != interface_keys:
            raise ResonantNumericalError("spectral interface keys are invalid")
        status = row["status"]
        if status not in {"pending", "available", "unavailable"}:
            raise ResonantNumericalError("spectral interface status is invalid")
        if row["reason"] is not None and not isinstance(row["reason"], str):
            raise ResonantNumericalError("spectral interface reason is invalid")
        for name in ("emitter_log_shift", "receiver_log_shift"):
            _number(row[name], f"spectral {name}",
                    minimum=-SPECTRAL_MAX_LOG_SHIFT,
                    maximum=SPECTRAL_MAX_LOG_SHIFT)
        _number(row["bandwidth_ratio"], "spectral bandwidth ratio",
                minimum=1e-6, maximum=1.0)
        _integer(row["tuning_updates"], "spectral tuning updates")
        if status == "available":
            _integer(row["emitter_mode"], "spectral emitter mode", maximum=3)
            _integer(row["receiver_mode"], "spectral receiver mode", maximum=3)
            if regions[key.split("->")[0]]["status"] != "available":
                raise ResonantNumericalError("spectral emitter mode has no basis")
            if regions[key.split("->")[1]]["status"] != "available":
                raise ResonantNumericalError("spectral receiver mode has no basis")
        elif row["emitter_mode"] is not None or row["receiver_mode"] is not None:
            raise ResonantNumericalError("unavailable spectral interface carries active modes")
        ref = row["last_appraisal_ref"]
        if current_schema:
            concern_tunings = row["concern_tunings"]
            if (
                not isinstance(concern_tunings, Mapping)
                or len(concern_tunings) > SPECTRAL_CONCERN_LIMIT
            ):
                raise ResonantNumericalError("spectral concern tunings exceed their bound")
            for concern_id, tuning in concern_tunings.items():
                if not isinstance(tuning, Mapping) or set(tuning) != _SPECTRAL_TUNING_KEYS:
                    raise ResonantNumericalError("spectral concern tuning is invalid")
                concern_ref = _validate_concern_ref(tuning["concern_ref"])
                if concern_ref["concern_id"] != concern_id:
                    raise ResonantNumericalError("spectral concern tuning identity changed")
                appraisal = tuning["appraisal_ref"]
                if (
                    not isinstance(appraisal, Mapping)
                    or set(appraisal) != {"operation_id", "assessment_sha256"}
                    or not isinstance(appraisal["operation_id"], str)
                    or not appraisal["operation_id"]
                    or not isinstance(appraisal["assessment_sha256"], str)
                    or len(appraisal["assessment_sha256"]) != 64
                ):
                    raise ResonantNumericalError("spectral concern appraisal reference is invalid")
                _validate_appraisal_basis(tuning["appraisal_basis"])
                _number(tuning["progress"], "spectral concern progress",
                        minimum=-1.0, maximum=1.0)
                _number(tuning["receiver_log_shift"], "spectral concern receiver shift",
                        minimum=-SPECTRAL_MAX_LOG_SHIFT,
                        maximum=SPECTRAL_MAX_LOG_SHIFT)
                _integer(tuning["updates"], "spectral concern tuning updates", minimum=1)
                _number(tuning["parameter_work"], "spectral concern parameter work")
                if (
                    not isinstance(tuning["operator_digest"], str)
                    or len(tuning["operator_digest"]) != 64
                ):
                    raise ResonantNumericalError("spectral concern operator digest is invalid")
        if ref is not None:
            if (not isinstance(ref, Mapping)
                    or set(ref) != {"operation_id", "assessment_sha256"}
                    or not isinstance(ref["operation_id"], str)
                    or not ref["operation_id"]
                    or not isinstance(ref["assessment_sha256"], str)
                    or len(ref["assessment_sha256"]) != 64):
                raise ResonantNumericalError("spectral appraisal reference is invalid")
    ledger = spectrum["ledger"]
    if not isinstance(ledger, Mapping) or set(ledger) != _SPECTRAL_LEDGER_KEYS:
        raise ResonantNumericalError("spectral ledger keys are invalid")
    for field in ("last_exchange", "last_feedback"):
        allowed = (
            (_SPECTRAL_EXCHANGE_KEYS if field == "last_exchange"
             else _SPECTRAL_FEEDBACK_KEYS)
            if current_schema else
            (_LEGACY_SPECTRAL_EXCHANGE_KEYS if field == "last_exchange"
             else _LEGACY_SPECTRAL_FEEDBACK_KEYS)
        )
        record = spectrum[field]
        if record is None:
            continue
        if not isinstance(record, Mapping) or set(record) != allowed:
            raise ResonantNumericalError(f"spectral {field} record is invalid")
        if record["interface"] not in expected_interfaces:
            raise ResonantNumericalError(f"spectral {field} interface is invalid")
        if not isinstance(record["state_sha256"], str) or len(record["state_sha256"]) != 64:
            raise ResonantNumericalError(f"spectral {field} state digest is invalid")
        parameter_work = _number(
            record["parameter_work"], f"spectral {field} parameter work"
        )
        if field == "last_exchange":
            if parameter_work != 0.0:
                raise ResonantNumericalError("spectral exchange cannot claim tuning work")
            if record["status"] not in {"available", "unavailable"}:
                raise ResonantNumericalError("spectral exchange status is invalid")
            for name in ("base_weight", "effective_weight"):
                _number(record[name], f"spectral exchange {name}", minimum=0.0)
            _number(record["physical_transfer_work"], "spectral physical transfer work")
            _number(record["overlap"], "spectral overlap", minimum=0.0, maximum=1.0)
            _number(record["bandwidth"], "spectral bandwidth", minimum=1e-6, maximum=1.0)
            if record["status"] == "available":
                _integer(record["emitter_mode"], "spectral emitter mode", maximum=3)
                _integer(record["receiver_mode"], "spectral receiver mode", maximum=3)
                _number(record["emitter_frequency"], "spectral emitter frequency",
                        minimum=1e-300)
                _number(record["receiver_frequency"], "spectral receiver frequency",
                        minimum=1e-300)
                _number(record["log_mismatch"], "spectral log mismatch")
                if not isinstance(record["basis_sha256"], str) or len(record["basis_sha256"]) != 64:
                    raise ResonantNumericalError("spectral exchange basis digest is invalid")
            elif not isinstance(record["reason"], str) or not record["reason"]:
                raise ResonantNumericalError("unavailable spectral exchange needs a reason")
            if current_schema:
                residual = record["operator_residual"]
                if residual is not None:
                    _number(residual, "spectral exchange operator residual",
                            minimum=0.0, maximum=1e-10)
                effective_shift = record["effective_receiver_log_shift"]
                if effective_shift is not None:
                    _number(effective_shift, "spectral exchange receiver shift",
                            minimum=-SPECTRAL_MAX_LOG_SHIFT,
                            maximum=SPECTRAL_MAX_LOG_SHIFT)
                concern_ids = record["concern_ids"]
                if (
                    not isinstance(concern_ids, list)
                    or len(concern_ids) > SPECTRAL_CONCERN_LIMIT
                    or any(not isinstance(value, str) or len(value) != 64
                           for value in concern_ids)
                    or len(concern_ids) != len(set(concern_ids))
                ):
                    raise ResonantNumericalError("spectral exchange concern IDs are invalid")
        else:
            ref = record["appraisal_ref"]
            if (
                not isinstance(ref, Mapping)
                or set(ref) != {"operation_id", "assessment_sha256"}
                or not isinstance(ref["operation_id"], str)
                or not ref["operation_id"]
                or not isinstance(ref["assessment_sha256"], str)
                or len(ref["assessment_sha256"]) != 64
            ):
                raise ResonantNumericalError("spectral feedback appraisal reference is invalid")
            if record["outcome"] not in {"progress", "obstruction", "no-progress"}:
                raise ResonantNumericalError("spectral feedback outcome is invalid")
            _number(
                record["progress"], "spectral feedback progress",
                minimum=-1.0 if current_schema else 0.0, maximum=1.0,
            )
            for name in ("before_shift", "after_shift"):
                _number(record[name], f"spectral feedback {name}",
                        minimum=-SPECTRAL_MAX_LOG_SHIFT,
                        maximum=SPECTRAL_MAX_LOG_SHIFT)
            _number(record["source_frequency"], "spectral source frequency", minimum=1e-300)
            _number(record["receiver_frequency"], "spectral receiver frequency", minimum=1e-300)
            if record["direction"] not in {"toward", "away"}:
                raise ResonantNumericalError("spectral feedback direction is invalid")
            if current_schema:
                concern_ref, appraisal_basis = (
                    record["concern_ref"], record["appraisal_basis"]
                )
                if (concern_ref is None) != (appraisal_basis is None):
                    raise ResonantNumericalError(
                        "spectral feedback concern and appraisal basis must be paired"
                    )
                if concern_ref is not None:
                    _validate_concern_ref(concern_ref)
                    _validate_appraisal_basis(appraisal_basis)
                digest = record["operator_digest"]
                if digest is not None and (
                    not isinstance(digest, str) or len(digest) != 64
                ):
                    raise ResonantNumericalError("spectral feedback operator digest is invalid")
                residual = record["operator_residual"]
                if residual is not None:
                    _number(residual, "spectral feedback operator residual",
                            minimum=0.0, maximum=1e-10)
                for name in ("effective_before_shift", "effective_after_shift"):
                    value = record[name]
                    if value is not None:
                        _number(value, f"spectral feedback {name}",
                                minimum=-SPECTRAL_MAX_LOG_SHIFT,
                                maximum=SPECTRAL_MAX_LOG_SHIFT)
                for name in ("mismatch_before", "mismatch_after"):
                    value = record[name]
                    if value is not None:
                        _number(value, f"spectral feedback {name}")
                for name in ("potential_before", "potential_after"):
                    value = record[name]
                    if value is not None:
                        _number(value, f"spectral feedback {name}", minimum=0.0)
    feedback_record = spectrum["last_feedback"]
    if current_schema and isinstance(feedback_record, Mapping):
        feedback_link = interfaces[feedback_record["interface"]]
        if feedback_record["operator_digest"] not in (None, operator_digest):
            raise ResonantNumericalError("spectral feedback operator basis changed")
        feedback_concern = feedback_record["concern_ref"]
        if feedback_concern is None:
            if feedback_link["last_appraisal_ref"] != feedback_record["appraisal_ref"]:
                raise ResonantNumericalError("unscoped spectral feedback reference changed")
        else:
            tuning = feedback_link["concern_tunings"].get(
                feedback_concern["concern_id"]
            )
            if (
                not isinstance(tuning, Mapping)
                or tuning["appraisal_ref"] != feedback_record["appraisal_ref"]
                or tuning["appraisal_basis"] != feedback_record["appraisal_basis"]
                or tuning["operator_digest"] != feedback_record["operator_digest"]
            ):
                raise ResonantNumericalError("spectral feedback concern attribution changed")
    history = spectrum["history"]
    if not isinstance(history, list) or len(history) > SPECTRAL_HISTORY_LIMIT:
        raise ResonantNumericalError("spectral history exceeds its declared bound")
    for row in history:
        if (not isinstance(row, Mapping)
                or set(row) != {"kind", "digest", "interface", "sequence"}):
            raise ResonantNumericalError("spectral history row is invalid")
        if row["kind"] not in {"exchange", "feedback"}:
            raise ResonantNumericalError("spectral history kind is invalid")
        if row["interface"] not in expected_interfaces:
            raise ResonantNumericalError("spectral history interface is invalid")
        _integer(row["sequence"], "spectral history sequence")
        if not isinstance(row["digest"], str) or len(row["digest"]) != 64:
            raise ResonantNumericalError("spectral history digest is invalid")
    compatibility = spectrum["compatibility"]
    if compatibility is not None:
        if (not isinstance(compatibility, Mapping)
                or set(compatibility) != {
                    "from_operator_digest", "to_operator_digest", "reason"
                }
                or not isinstance(compatibility["to_operator_digest"], str)
                or len(compatibility["to_operator_digest"]) != 64
                or not isinstance(compatibility["reason"], str)):
            raise ResonantNumericalError("spectral compatibility record is invalid")
        old_digest = compatibility["from_operator_digest"]
        if old_digest is not None and (
                not isinstance(old_digest, str) or len(old_digest) != 64):
            raise ResonantNumericalError("spectral prior operator digest is invalid")


def validate_circulation(segment: Any) -> None:
    """Validate one canonical circulation segment."""

    if not isinstance(segment, Mapping):
        raise ResonantNumericalError("circulation segment keys are invalid")
    schema = segment.get("schema")
    expected_keys = (_CIRCULATION_KEYS if schema == CIRCULATION_SCHEMA
                     else _LEGACY_CIRCULATION_KEYS
                     if schema == _LEGACY_CIRCULATION_SCHEMA else frozenset())
    if set(segment) != expected_keys:
        raise ResonantNumericalError("circulation segment keys are invalid")
    if schema not in {CIRCULATION_SCHEMA, _LEGACY_CIRCULATION_SCHEMA}:
        raise ResonantNumericalError("circulation segment schema is invalid")
    if segment["basis"] != CIRCULATION_BASIS_VERSION:
        raise ResonantNumericalError("circulation basis version is invalid")
    if not isinstance(segment["enabled"], bool):
        raise ResonantNumericalError("circulation enabled flag is invalid")
    views = segment["views"]
    if not isinstance(views, Mapping) or set(views) != _VIEW_KEYS:
        raise ResonantNumericalError("circulation view declaration is invalid")
    if views["detail"] != CIRCULATION_VIEW_SOURCE or not isinstance(views["source"], str):
        raise ResonantNumericalError("circulation view provenance is invalid")
    _canonical(segment)
    blocks = segment["blocks"]
    if not isinstance(blocks, list) or not blocks:
        raise ResonantNumericalError("circulation blocks are invalid")
    for row in blocks:
        if (not isinstance(row, list) or len(row) != 2
                or _integer(row[0], "block start") >= _integer(row[1], "block end")):
            raise ResonantNumericalError("circulation block range is invalid")
    regions = segment["regions"]
    if not isinstance(regions, Mapping) or len(regions) != len(blocks):
        raise ResonantNumericalError("circulation regions are invalid")
    for identity, raw in regions.items():
        if not isinstance(raw, Mapping) or set(raw) != _REGION_KEYS:
            raise ResonantNumericalError("circulation region keys are invalid")
        if raw["identity"] != identity:
            raise ResonantNumericalError("circulation region identity mismatch")
        if raw["owner_scope"] != CIRCULATION_REGION_SCOPE:
            raise ResonantNumericalError("circulation region scope is invalid")
        if raw["basis_ref"] != CIRCULATION_BASIS_VERSION:
            raise ResonantNumericalError("circulation region basis is invalid")
        if raw["arithmetic_profile"] != "numpy-cpu-float64":
            raise ResonantNumericalError("circulation region arithmetic profile is invalid")
        _integer(raw["content_version"], "region content version")
        _number(raw["numerical_time"], "region numerical time", minimum=0.0)
        _number(raw["interface_work"], "region interface work")
        if not isinstance(raw["stale"], bool):
            raise ResonantNumericalError("region stale flag is invalid")
        if not isinstance(raw["relative_phases"], Mapping):
            raise ResonantNumericalError("region relative phases are invalid")
        if not isinstance(raw["geometric_parameters"], Mapping):
            raise ResonantNumericalError("region geometric parameters are invalid")
        if not isinstance(raw["resource_accounts"], Mapping) or not isinstance(
                raw["unfinished_work"], Mapping):
            raise ResonantNumericalError("region work accounts are invalid")
        if not isinstance(raw["interface_dependencies"], (list, tuple)):
            raise ResonantNumericalError("region interface dependencies are invalid")
        _as_f64(raw["coarse_coordinates"], (2,), "region coarse coordinates")
        _as_f64(raw["coarse_momenta"], (2,), "region coarse momenta")
        _as_f64(raw["detail_coordinates"], name="region detail coordinates")
        _as_f64(raw["detail_momenta"], name="region detail momenta")
        _as_f64(raw["axial_frame"], (3, 3), "region axial frame")
        _number(raw["signed_current"], "region signed current")
        _integer(raw["handedness"], "region handedness", minimum=-1, maximum=1)
        first, last = _block_span(raw)
        if not 0 <= first < last:
            raise ResonantNumericalError("circulation region block is invalid")
        _region_record(raw)
    for identity, raw in regions.items():
        parent = raw["parent_id"]
        if parent is not None and parent not in regions:
            raise ResonantNumericalError("circulation region parent is unknown")
    stages = segment["stages"]
    if not isinstance(stages, Mapping) or not stages:
        raise ResonantNumericalError("circulation stages are invalid")
    for key, raw in stages.items():
        if not isinstance(raw, Mapping) or set(raw) != _STAGE_KEYS:
            raise ResonantNumericalError("circulation stage keys are invalid")
        parent, child = (raw["parent_version"].split("@")[0],
                         raw["child_version"].split("@")[0])
        if key != f"{parent}->{child}" or parent not in regions or child not in regions:
            raise ResonantNumericalError("circulation stage identity is invalid")
        if raw["digest"] != ResonantExchangeStage.bind(
            raw["parent_version"], raw["child_version"], version=raw["version"]
        ).digest:
            raise ResonantNumericalError("circulation stage digest is invalid")
    operator = segment["operator"]
    if not isinstance(operator, Mapping) or set(operator) != _OPERATOR_KEYS:
        raise ResonantNumericalError("circulation operator keys are invalid")
    dependencies = operator["dependencies"]
    if (not isinstance(dependencies, Mapping)
            or set(dependencies) != set(_OPERATOR_DEPENDENCY_KEYS)):
        raise ResonantNumericalError("circulation operator dependencies are invalid")
    if dependencies["basis"] != CIRCULATION_BASIS_VERSION:
        raise ResonantNumericalError("operator dependency basis is invalid")
    _integer(dependencies["coordinate_count"], "operator coordinate count", minimum=1)
    _integer(dependencies["pools"], "operator pools", minimum=1)
    _integer(dependencies["ports_per_pool"], "operator ports per pool", minimum=1)
    _number(dependencies["coupling"], "operator coupling", minimum=0.0)
    for name in ("coordinates_digest", "volumes_digest"):
        if not isinstance(dependencies[name], str) or len(dependencies[name]) != 64:
            raise ResonantNumericalError("operator dependency digest is invalid")
    if (not isinstance(operator["digest"], str) or len(operator["digest"]) != 64
            or operator["digest"] == ""):
        raise ResonantNumericalError("circulation operator digest is invalid")
    if operator["declared_from"] != "metric_edge_weights":
        raise ResonantNumericalError("circulation operator provenance is invalid")
    _number(operator["residual"], "operator residual", minimum=0.0)
    _integer(operator["edge_count"], "operator edge count", minimum=0)
    geometry = segment["geometry"]
    if not isinstance(geometry, Mapping) or set(geometry) != _GEOMETRY_KEYS:
        raise ResonantNumericalError("circulation geometry keys are invalid")
    _geometry_record(geometry)
    _number(geometry["coverage"], "geometry coverage", minimum=0.0, maximum=1.0)
    if not isinstance(geometry["degenerate"], bool):
        raise ResonantNumericalError("geometry degeneracy flag is invalid")
    attention = segment["attention"]
    if not isinstance(attention, Mapping) or set(attention) != _ATTENTION_KEYS:
        raise ResonantNumericalError("circulation attention keys are invalid")
    if attention["target"] is not None and attention["target"] not in regions:
        raise ResonantNumericalError("circulation attention target is unknown")
    _number(attention["progress"], "attention progress", minimum=0.0)
    _integer(attention["remaining"], "attention remaining",
             maximum=int(attention["stage_limit"]))
    if not isinstance(attention["settled"], bool):
        raise ResonantNumericalError("attention settled flag is invalid")
    _number(attention["entry_threshold"], "attention entry threshold", minimum=0.0)
    _number(attention["exit_threshold"], "attention exit threshold", minimum=0.0)
    if float(attention["exit_threshold"]) > float(attention["entry_threshold"]):
        raise ResonantNumericalError("attention thresholds are inverted")
    _integer(attention["stage_limit"], "attention stage limit", minimum=1)
    _integer(attention["retargets"], "attention retargets")
    if attention["admitted_stage"] is not None:
        _integer(attention["admitted_stage"], "attention admitted stage")
    continuation = segment["continuation"]
    if not isinstance(continuation, Mapping) or set(continuation) != _CONTINUATION_KEYS:
        raise ResonantNumericalError("circulation continuation keys are invalid")
    _integer(continuation["pass"], "circulation pass", maximum=CIRCULATION_MAX_PASSES)
    _integer(continuation["cursor"], "circulation cursor")
    if continuation["phase"] not in _PHASES:
        raise ResonantNumericalError("circulation phase is invalid")
    _number(continuation["amplitude"], "circulation amplitude", minimum=0.0)
    _number(continuation["angle"], "circulation angle")
    if not isinstance(continuation["measured"], bool):
        raise ResonantNumericalError("circulation measured flag is invalid")
    _integer(continuation["pending"], "circulation pending units")
    ledger = segment["ledger"]
    if not isinstance(ledger, Mapping) or set(ledger) != set(_CIRCULATION_LEDGER_KEYS):
        raise ResonantNumericalError("circulation ledger keys are invalid")
    nonnegative = set(_CIRCULATION_LEDGER_KEYS) - {
        "interface_transfer_work", "interface_first_order_work",
    }
    for key, value in ledger.items():
        _number(value, f"circulation ledger {key}",
                minimum=0.0 if key in nonnegative else None)
    declared = {"pools": len(blocks), "ports_per_pool": blocks[0][1] - blocks[0][0]}
    edges = segment["edges"]
    if not isinstance(edges, list) or tuple(tuple(edge) for edge in edges) != \
            circulation_interfaces(declared):
        raise ResonantNumericalError("circulation edges are invalid")
    if set(stages) != {f"{parent}->{child}"
                       for parent, child in circulation_interfaces(declared)}:
        raise ResonantNumericalError("circulation interface records are incomplete")
    if schema == CIRCULATION_SCHEMA:
        _validate_spectrum(segment)


def circulation_spectral_feedback(
    segment: dict[str, Any], *, interface: str,
    appraisal_ref: Mapping[str, Any], progress: float,
    expected_exchange_sha256: str,
    concern_ref: Mapping[str, Any] | None = None,
    appraisal_basis: Mapping[str, Any] | None = None,
    operator: _RegionalWaveOperator | None = None,
    words: Sequence[float] | np.ndarray | None = None,
    quiet: bool = False,
) -> dict[str, Any]:
    """Tune a receiver channel only from a current operator and bound appraisal."""

    if segment.get("schema") != CIRCULATION_SCHEMA or "spectrum" not in segment:
        return {
            "schema": "cassifi.resonant-spectral-feedback.v1",
            "status": "unavailable",
            "reason": "circulation has no migrated spectral state",
            "interface": interface, "admitted": False, "parameter_work": 0.0,
        }
    if (concern_ref is None) != (appraisal_basis is None):
        raise ResonantNumericalError(
            "spectral feedback concern and appraisal basis must be supplied together"
        )
    checked_concern = (
        None if concern_ref is None else _validate_concern_ref(concern_ref)
    )
    checked_basis = (
        None if appraisal_basis is None else _validate_appraisal_basis(appraisal_basis)
    )
    if (
        not isinstance(interface, str)
        or interface not in segment["spectrum"]["interfaces"]
    ):
        raise ResonantNumericalError("spectral feedback interface is unknown")
    if (
        not isinstance(appraisal_ref, Mapping)
        or set(appraisal_ref) != {"operation_id", "assessment_sha256"}
        or not isinstance(appraisal_ref["operation_id"], str)
        or not appraisal_ref["operation_id"]
        or not isinstance(appraisal_ref["assessment_sha256"], str)
        or len(appraisal_ref["assessment_sha256"]) != 64
    ):
        raise ResonantNumericalError("spectral feedback appraisal reference is invalid")
    measured_progress = _number(
        progress, "spectral feedback progress", minimum=-1.0, maximum=1.0
    )
    if (
        not isinstance(expected_exchange_sha256, str)
        or len(expected_exchange_sha256) != 64
    ):
        raise ResonantNumericalError("spectral feedback exchange digest is invalid")
    if not isinstance(quiet, bool):
        raise ResonantNumericalError("spectral feedback quiet mode must be boolean")
    if operator is None or words is None:
        return {
            "schema": "cassifi.resonant-spectral-feedback.v1",
            "status": "unavailable",
            "reason": "current operator and field words are required for feedback",
            "interface": interface, "admitted": False, "parameter_work": 0.0,
        }
    vector = _as_f64(words, (4 * operator.n,), "spectral wave words")
    spectrum = _ensure_spectrum(segment, operator, vector)
    validate_circulation(segment)
    link = spectrum["interfaces"][interface]
    reference = _plain(appraisal_ref)
    previous_concern = (
        link["concern_tunings"].get(checked_concern["concern_id"])
        if checked_concern is not None else None
    )
    if (
        previous_concern is not None
        and previous_concern["appraisal_ref"] == reference
    ) or (
        checked_concern is None and link["last_appraisal_ref"] == reference
    ):
        return {
            "schema": "cassifi.resonant-spectral-feedback.v1",
            "status": "duplicate", "reason": "appraisal was already applied",
            "interface": interface, "admitted": False, "parameter_work": 0.0,
        }
    exchange = spectrum["last_exchange"]
    if (
        link["status"] != "available" or exchange is None
        or exchange["status"] != "available"
    ):
        return {
            "schema": "cassifi.resonant-spectral-feedback.v1",
            "status": "unavailable",
            "reason": link["reason"] or "no verified spectral exchange is available",
            "interface": interface, "admitted": False, "parameter_work": 0.0,
        }
    current_digest = _digest(exchange)
    if exchange["interface"] != interface or current_digest != expected_exchange_sha256:
        return {
            "schema": "cassifi.resonant-spectral-feedback.v1",
            "status": "stale",
            "reason": "target spectral exchange changed before appraisal",
            "interface": interface, "admitted": False, "parameter_work": 0.0,
        }
    if measured_progress == 0.0:
        return {
            "schema": "cassifi.resonant-spectral-feedback.v1",
            "status": "unchanged", "reason": "zero progress carries no tuning direction",
            "interface": interface, "admitted": False, "parameter_work": 0.0,
            "exchange_sha256": current_digest,
        }

    parent, child = interface.split("->", 1)
    trace = _spectral_exchange_factor(segment, operator, vector, parent, child)
    if trace["status"] != "available":
        return {
            "schema": "cassifi.resonant-spectral-feedback.v1",
            "status": "unavailable", "reason": trace["reason"],
            "interface": interface, "admitted": False, "parameter_work": 0.0,
        }
    spectrum = segment["spectrum"]
    link = spectrum["interfaces"][interface]
    mismatch_before = float(trace["log_mismatch"])
    bandwidth = float(trace["bandwidth"])
    effective_before = float(trace["effective_receiver_log_shift"])
    before_shift = (
        float(previous_concern["receiver_log_shift"])
        if previous_concern is not None
        else 0.0 if checked_concern is not None
        else float(link["receiver_log_shift"])
    )
    receiver_frequency = float(trace["receiver_frequency"])
    source_frequency = float(trace["emitter_frequency"])
    profile = operator.profile
    time_step = float(profile["time_step"])
    damping = float(
        profile["quiet_damping"] if quiet else profile["damping"]
    )
    response_rate = math.hypot(damping, receiver_frequency)
    response = time_step * response_rate / (1.0 + time_step * response_rate)
    after_shift = max(
        -SPECTRAL_MAX_LOG_SHIFT,
        min(SPECTRAL_MAX_LOG_SHIFT,
            before_shift + response * measured_progress * mismatch_before),
    )
    effective_after = max(
        -SPECTRAL_MAX_LOG_SHIFT,
        min(SPECTRAL_MAX_LOG_SHIFT, effective_before + after_shift - before_shift),
    )
    if after_shift == before_shift or effective_after == effective_before:
        return {
            "schema": "cassifi.resonant-spectral-feedback.v1",
            "status": "unchanged", "reason": "bounded tuning produced no measurable shift",
            "interface": interface, "admitted": False, "parameter_work": 0.0,
            "exchange_sha256": current_digest,
        }
    region = spectrum["regions"][child]
    receiver_mode = int(link["receiver_mode"])
    receiver_base_frequency = float(region["frequencies"][receiver_mode])
    tuned_receiver_frequency = receiver_base_frequency * math.exp(effective_after)
    mismatch_after = math.log(source_frequency / tuned_receiver_frequency)
    potential_before = 0.5 * (mismatch_before / bandwidth) ** 2
    potential_after = 0.5 * (mismatch_after / bandwidth) ** 2
    parameter_work = potential_before - potential_after
    direction = "toward" if measured_progress > 0.0 else "away"
    if checked_concern is None:
        link["receiver_log_shift"] = float(after_shift)
    else:
        tunings = dict(link["concern_tunings"])
        tunings[checked_concern["concern_id"]] = {
            "concern_ref": checked_concern,
            "appraisal_ref": reference,
            "appraisal_basis": checked_basis,
            "progress": measured_progress,
            "receiver_log_shift": float(after_shift),
            "updates": 1 if previous_concern is None else (
                int(previous_concern["updates"]) + 1
            ),
            "parameter_work": parameter_work + (
                0.0 if previous_concern is None
                else float(previous_concern["parameter_work"])
            ),
            "operator_digest": spectrum["operator_digest"],
        }
        link["concern_tunings"] = tunings
    link["tuning_updates"] = int(link["tuning_updates"]) + 1
    link["last_appraisal_ref"] = reference
    ledger = dict(spectrum["ledger"])
    ledger["feedback_updates"] = float(ledger["feedback_updates"]) + 1.0
    ledger["tuning_parameter_work"] = (
        float(ledger["tuning_parameter_work"]) + parameter_work
    )
    spectrum["ledger"] = ledger
    state_sha256 = _digest({
        "operator_digest": spectrum["operator_digest"],
        "regions": spectrum["regions"],
        "interfaces": spectrum["interfaces"],
        "last_exchange": exchange,
    })
    record = {
        "interface": interface,
        "appraisal_ref": reference,
        "outcome": "progress" if measured_progress > 0.0 else "obstruction",
        "progress": measured_progress,
        "before_shift": before_shift,
        "after_shift": float(after_shift),
        "source_frequency": source_frequency,
        "receiver_frequency": tuned_receiver_frequency,
        "direction": direction,
        "parameter_work": parameter_work,
        "state_sha256": state_sha256,
        "concern_ref": checked_concern,
        "appraisal_basis": checked_basis,
        "operator_digest": spectrum["operator_digest"],
        "operator_residual": float(trace["operator_residual"]),
        "effective_before_shift": effective_before,
        "effective_after_shift": effective_after,
        "mismatch_before": mismatch_before,
        "mismatch_after": mismatch_after,
        "potential_before": potential_before,
        "potential_after": potential_after,
    }
    spectrum["last_feedback"] = record
    _append_spectral_history(spectrum, {
        "kind": "feedback", "digest": _digest(record),
        "interface": interface, "sequence": int(ledger["feedback_updates"]),
    })
    validate_circulation(segment)
    return {
        "schema": "cassifi.resonant-spectral-feedback.v1",
        "status": "updated", "reason": None, "interface": interface,
        "admitted": True, "progress": measured_progress,
        "direction": direction, "before_shift": before_shift,
        "after_shift": float(after_shift),
        "effective_before_shift": effective_before,
        "effective_after_shift": effective_after,
        "source_frequency": source_frequency,
        "receiver_frequency": tuned_receiver_frequency,
        "mismatch_before": mismatch_before, "mismatch_after": mismatch_after,
        "potential_before": potential_before, "potential_after": potential_after,
        "operator_digest": spectrum["operator_digest"],
        "operator_residual": float(trace["operator_residual"]),
        "parameter_work": parameter_work,
        "exchange_sha256": current_digest, "state_sha256": state_sha256,
    }


# ---------------------------------------------------------------------------
# Readout and eligible-work modulation.
# ---------------------------------------------------------------------------


def circulation_geometry(segment: Mapping[str, Any]) -> dict[str, Any]:
    """The measured flow geometry plus its declared derived quantities."""

    payload = segment["geometry"]
    record = _geometry_record(payload)
    result: dict[str, Any] = {
        "schema": "cassifi.resonant-geometry.v1",
        "longitudinal_direction": list(record.longitudinal_direction),
        "signed_current": float(record.signed_current),
        "handedness": int(record.handedness),
        "kappa": float(record.kappa),
        "omega": float(record.omega),
        "axial_speed": float(record.axial_speed),
        "angular_convention": str(record.angular_convention),
        "divergence": float(record.divergence),
        "degenerate": bool(payload["degenerate"]),
        "coverage": float(payload["coverage"]),
        "rates_measured": bool(segment["continuation"]["measured"]),
    }
    if record.kappa > 0.0:
        contraction = float(math.exp(-(math.pi / 2.0) * record.kappa / record.omega))
        result["taper_ratio"] = float(record.omega / record.kappa)
        result["quarter_turn_contraction"] = contraction
        result["kappa_roundtrip"] = float(
            contraction_rate_ratio(contraction, math.pi / 2.0, omega=record.omega)
        )
        result["axial_pitch"] = float((record.axial_speed / record.omega) * (math.pi / 2.0))
    return result


def circulation_spectrum_readout(segment: Mapping[str, Any]) -> dict[str, Any]:
    """Return the resident, bounded operator-spectral state without mutation."""

    spectrum = segment.get("spectrum")
    if spectrum is None:
        return {
            "schema": SPECTRAL_STATE_SCHEMA,
            "basis": SPECTRAL_BASIS_VERSION,
            "status": "unavailable",
            "reason": "legacy circulation has not been migrated by a writable unit",
            "operator_digest": None, "regions": {}, "interfaces": {},
            "ledger": {"exchanges": 0.0, "transfer_work": 0.0,
                       "feedback_updates": 0.0, "tuning_parameter_work": 0.0},
            "last_exchange": None, "last_feedback": None, "history": [],
            "compatibility": None,
        }
    return _plain(spectrum)

def circulation_readout(segment: Mapping[str, Any]) -> dict[str, Any]:
    """Read-only picture of the resident circulation and its work accounts."""

    regions = {
        identity: {
            "identity": identity,
            "parent_id": raw["parent_id"],
            "content_version": int(raw["content_version"]),
            "signed_current": float(raw["signed_current"]),
            "handedness": int(raw["handedness"]),
            "phase": float(raw["relative_phases"].get("self", 0.0)),
            "detail_mode": float(raw["relative_phases"].get("detail", 0.0)),
            "interface_work": float(raw["interface_work"]),
            "axial_frame": _plain(raw["axial_frame"]),
            "block": list(raw["coupling_ports"]),
            "numerical_time": float(raw["numerical_time"]),
            "integration_phase": raw["integration_phase"],
            "stale": bool(raw["stale"]),
        }
        for identity, raw in sorted(segment["regions"].items())
    }
    return {
        "schema": CIRCULATION_READOUT_SCHEMA,
        "enabled": bool(segment["enabled"]),
        "basis": segment["basis"],
        "views": _plain(segment["views"]),
        "blocks": [list(block) for block in segment["blocks"]],
        "interfaces": [list(edge) for edge in segment["edges"]],
        "regions": regions,
        "geometry": circulation_geometry(segment),
        "operator": {
            "digest": segment["operator"]["digest"],
            "declared_from": segment["operator"]["declared_from"],
            "residual": float(segment["operator"]["residual"]),
            "edge_count": int(segment["operator"]["edge_count"]),
            "dependencies": _plain(segment["operator"]["dependencies"]),
        },
        "spectrum": circulation_spectrum_readout(segment),
        "alignment": circulation_alignment(segment),
        "attention": _plain(segment["attention"]),
        "continuation": _plain(segment["continuation"]),
        "ledger": {key: float(value) for key, value in segment["ledger"].items()},
        "authority": "operational-report-only",
    }


def _region_view(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return {"identity": str(row["identity"]),
                "signed_current": float(row["signed_current"]),
                "handedness": int(row["handedness"]),
                "stale": bool(row["stale"])}
    return {"identity": str(row.identity),
            "signed_current": float(row.signed_current),
            "handedness": int(row.handedness),
            "stale": bool(row.stale)}


def _modulation_values(regions: Sequence[Any],
                       events: Sequence[Mapping[str, Any]], *,
                       coverage: float, total_current: float, kappa: float,
                       omega: float, flow_handedness: int,
                       scale: float) -> dict[int, float]:
    """The declared bounded eligible-work modulation of a circulation.

    For event sequence ``k`` the producer uses
    ``v_k = clip(tanh(scale)*C*tanh(I_r/(1+abs(I_r)))*
    (1/2 + kappa/(2*(omega+kappa)))*
    cos(pi*k/2 + pi*handedness/2), -1, 1)``, where ``C`` is the non-stale
    coverage and ``I_r`` the event's region current.  Every value lies in
    ``[-1, 1]``; no eligibility or fairness decision is made here.
    """

    if not events:
        return {}
    if not math.isfinite(float(scale)):
        raise ResonantNumericalError("activity scale must be finite")
    if not math.isfinite(kappa) or not math.isfinite(omega) or kappa < 0.0 or omega <= 0.0:
        raise ResonantNumericalError("activity flow rates must satisfy kappa >= 0 and omega > 0")
    if flow_handedness not in (-1, 0, 1):
        raise ResonantNumericalError("activity flow handedness must be -1, 0, or +1")
    geometric_factor = 0.5 + 0.5 * kappa / (omega + kappa)
    gain = math.tanh(float(scale))
    by_id = {view["identity"]: view for view in map(_region_view, regions)}
    output: dict[int, float] = {}
    for row in events:
        if not isinstance(row, Mapping) or isinstance(row.get("sequence"), bool):
            raise ResonantNumericalError("activity events require integer sequence rows")
        sequence = int(row.get("sequence"))
        if sequence != row.get("sequence") or sequence < 0:
            raise ResonantNumericalError(
                "activity event sequence must be a nonnegative integer"
            )
        region = by_id.get(str(row.get("region_id")))
        current = total_current if region is None else region["signed_current"]
        local_coverage = 0.0 if region is not None and region["stale"] else float(coverage)
        handedness = (int(flow_handedness) if region is None
                      else int(region["handedness"] or flow_handedness))
        value = gain * local_coverage * math.tanh(current / (1.0 + abs(current)))
        value *= geometric_factor * math.cos(
            math.pi * sequence / 2.0 + math.pi * handedness / 2.0
        )
        output[sequence] = float(max(-1.0, min(1.0, value)))
    return output


def _spectral_priority_offsets(segment: Mapping[str, Any],
                               events: Sequence[Mapping[str, Any]]) -> tuple[
                                   dict[int, float], dict[str, Any]
                               ]:
    """Project verified spectral overlap to bounded eligible-work priority.

    Explicit ``region_id`` rows use that declared region's mean interface
    overlap.  Unbound work rows use the last verified exchange and a stable
    sequence quadrature; this is a nonsemantic eligible-work bias, not a claim
    that a work item belongs to a region.
    """

    spectrum = segment.get("spectrum")
    if not isinstance(spectrum, Mapping):
        return {}, {"status": "unavailable",
                    "reason": "legacy circulation has no persisted spectrum",
                    "region_offsets": {}, "last_exchange": None,
                    "last_exchange_sha256": None, "ledger": {},
                    "basis": None,
                    "projection": "nonsemantic-eligible-work-sequence-quadrature.v1",
                    "projection_meaning": "eligible-work-priority-bias-only"}
    regions = spectrum.get("regions")
    links = spectrum.get("interfaces")
    if not isinstance(regions, Mapping) or not isinstance(links, Mapping):
        return {}, {"status": "unavailable",
                    "reason": "circulation spectrum has no regional interface map",
                    "region_offsets": {}, "last_exchange": None,
                    "last_exchange_sha256": None,
                    "ledger": _plain(spectrum.get("ledger", {})),
                    "basis": spectrum.get("basis"),
                    "projection": "nonsemantic-eligible-work-sequence-quadrature.v1",
                    "projection_meaning": "eligible-work-priority-bias-only"}
    by_region: dict[str, list[float]] = {}
    for key, link in links.items():
        if not isinstance(link, Mapping) or link.get("status") != "available":
            continue
        parent, separator, child = str(key).partition("->")
        if not separator or parent not in regions or child not in regions:
            continue
        emitter, receiver = regions[parent], regions[child]
        try:
            emitter_mode = int(link["emitter_mode"])
            receiver_mode = int(link["receiver_mode"])
            source_frequency = float(emitter["frequencies"][emitter_mode]) * math.exp(
                float(link["emitter_log_shift"])
            )
            target_frequency = float(receiver["frequencies"][receiver_mode]) * math.exp(
                float(link["receiver_log_shift"])
            )
            bandwidth = float(link["bandwidth_ratio"])
            if (source_frequency <= 0.0 or target_frequency <= 0.0
                    or not math.isfinite(source_frequency)
                    or not math.isfinite(target_frequency)
                    or not 0.0 < bandwidth <= 1.0):
                continue
            mismatch = math.log(source_frequency / target_frequency)
            overlap = 1.0 / (1.0 + (mismatch / bandwidth) ** 2)
        except (KeyError, IndexError, TypeError, ValueError, OverflowError):
            continue
        score = 2.0 * overlap - 1.0
        for identity in {parent, child}:
            by_region.setdefault(identity, []).append(score)
    offsets_by_region = {
        identity: 0.1 * (sum(scores) / len(scores))
        for identity, scores in by_region.items() if scores
    }

    exchange = spectrum.get("last_exchange")
    exchange_sha256 = _digest(exchange) if isinstance(exchange, Mapping) else None
    exchange_score = None
    if isinstance(exchange, Mapping) and exchange.get("status") == "available":
        try:
            overlap = float(exchange["overlap"])
            if math.isfinite(overlap) and 0.0 <= overlap <= 1.0:
                exchange_score = 2.0 * overlap - 1.0
        except (KeyError, TypeError, ValueError, OverflowError):
            exchange_score = None

    adjustments: dict[int, float] = {}
    for row in events:
        identity = row.get("region_id")
        sequence = int(row["sequence"])
        if identity is None:
            phase = (1.0, 0.0, -1.0, 0.0)[sequence % 4]
            adjustment = (
                0.1 * float(exchange_score) * phase
                if exchange_score is not None else 0.0
            )
        else:
            scores = by_region.get(str(identity), ())
            adjustment = 0.1 * (sum(scores) / len(scores)) if scores else 0.0
        adjustments[sequence] = float(max(-0.1, min(0.1, adjustment)))
    return adjustments, {
        "status": (
            "available" if exchange_score is not None else
            str(spectrum.get("status", "unavailable"))
        ),
        "reason": (
            None if exchange_score is not None else
            "no current verified spectral exchange is available"
        ),
        "region_offsets": offsets_by_region,
        "last_exchange": _plain(exchange) if isinstance(exchange, Mapping) else None,
        "last_exchange_sha256": exchange_sha256,
        "ledger": _plain(spectrum.get("ledger", {})),
        "basis": spectrum.get("basis"),
        "projection": "nonsemantic-eligible-work-sequence-quadrature.v1",
        "projection_meaning": "eligible-work-priority-bias-only",
    }




def circulation_activity(segment: Mapping[str, Any],
                         events: Sequence[Mapping[str, Any]], *,
                         scale: float = 1.0) -> dict[str, Any]:
    """Bounded eligible-work modulation produced by the measured circulation."""

    geometry = segment["geometry"]
    regions = sorted(segment["regions"].values(), key=lambda row: row["identity"])
    values = _modulation_values(
        regions, events, coverage=float(geometry["coverage"]),
        total_current=float(geometry["signed_current"]),
        kappa=float(geometry["kappa"]), omega=float(geometry["omega"]),
        flow_handedness=int(geometry["handedness"]), scale=float(scale),
    )
    spectral_values, spectral_transfer = _spectral_priority_offsets(segment, events)
    gain = math.tanh(float(scale)) * float(geometry["coverage"])
    for sequence, adjustment in spectral_values.items():
        spectral_values[sequence] = adjustment * gain
        values[sequence] = float(max(-1.0, min(1.0,
                                              values.get(sequence, 0.0) + spectral_values[sequence])))
    return {
        "schema": CIRCULATION_ACTIVITY_SCHEMA,
        "values": values,
        "spectral_values": spectral_values,
        "spectral_transfer": spectral_transfer,
        "coverage": float(geometry["coverage"]),
        "signed_current": float(geometry["signed_current"]),
        "handedness": int(geometry["handedness"]),
        "degenerate": bool(geometry["degenerate"]),
        "authority": CIRCULATION_MODULATION_AUTHORITY,
    }


CIRCULATION_ACTIVITY_SCALE = 0.25
"""Declared profile rule for the bounded eligible-work modulation.

The modulation is a priority hint among already eligible work; it is never
evidence and never authority.  The profile scale ``0.25`` bounds the
displacement of any one work site by ``tanh(0.25)`` (about ``0.245``) priority
units, which is the order of the bounded outcome-bound affect adjustment and
small enough that clearly separated obligations keep their order.  Flow
magnitude cannot validate an inference, override a correction, admit
inaccessible detail, or promote a hypothesis.
"""


def circulation_modulation(segment: Mapping[str, Any],
                           events: Sequence[Mapping[str, Any]], *,
                           scale: float = CIRCULATION_ACTIVITY_SCALE,
                           dependencies: Mapping[str, Any] | None = None,
                           ) -> dict[str, Any]:
    """The declared eligible-work modulation block consumed by the agenda.

    Carries the bounded per-sequence values, the profile scale that produced
    them, the measured flow geometry they were derived from, and the versioned
    dependencies binding them to one resident circulation state.  The block is
    a request field: the agenda validates it, applies it as a bounded priority
    adjustment among eligible work, and records what it applied.
    """

    activity = circulation_activity(segment, events, scale=scale)
    geometry = circulation_geometry(segment)
    operator = segment["operator"]
    return {
        "schema": CIRCULATION_ACTIVITY_SCHEMA,
        "authority": activity["authority"],
        "scale": float(scale),
        "values": {str(sequence): float(value)
                   for sequence, value in sorted(activity["values"].items())},
        "spectral_values": {str(sequence): float(value)
                            for sequence, value in sorted(
                                activity["spectral_values"].items())},
        "spectral_transfer": activity["spectral_transfer"],
        "coverage": activity["coverage"],
        "signed_current": activity["signed_current"],
        "handedness": activity["handedness"],
        "degenerate": activity["degenerate"],
        "dependencies": {
            "basis": segment["basis"],
            "pass": int(segment["continuation"]["pass"]),
            "operator_digest": operator["digest"],
            "spectrum_sha256": _digest(segment.get("spectrum", {})),
            "operator_residual": float(operator["residual"]),
            "operator_edges": int(operator["edge_count"]),
            "stages": {edge: row["digest"]
                       for edge, row in sorted(segment["stages"].items())},
            "kappa": geometry["kappa"],
            "omega": geometry["omega"],
            **(dict(dependencies) if dependencies is not None else {}),
        },
    }


# ---------------------------------------------------------------------------
# Attention: a continuing orientation with distinct entry and exit thresholds.
# ---------------------------------------------------------------------------


def circulation_alignment(segment: Mapping[str, Any]) -> dict[str, Any]:
    """The declared pairwise alignment potential of the current orientation."""

    edges = [tuple(edge) for edge in segment["edges"] if edge[0] != edge[1]]
    pairs: dict[str, float] = {}
    for parent, child in edges:
        parent_raw = segment["regions"][parent]
        child_raw = segment["regions"][child]
        pairs[f"{parent}->{child}"] = float(alignment_energy(
            np.asarray(parent_raw["axial_frame"], dtype=np.float64)[:, 0],
            np.asarray(child_raw["axial_frame"], dtype=np.float64)[:, 0],
            phase_parent=float(parent_raw["relative_phases"].get("self", 0.0)),
            phase_child=float(child_raw["relative_phases"].get("self", 0.0)),
        ))
    values = list(pairs.values())
    return {
        "pairs": pairs,
        "mean": float(np.mean(values)) if values else 0.0,
        "maximum": float(max(values)) if values else 0.0,
    }


def circulation_admit(segment: dict[str, Any], target: str | None, *,
                      stages: int | None = None) -> dict[str, Any]:
    """Admit or release one organising target under hysteresis.

    ``entry_threshold`` is the alignment potential above which admitting a new
    organising target is worth its stages; ``exit_threshold`` is the potential
    below which the currently admitted target counts as settled enough to be
    replaced.  Both readings come from :func:`circulation_alignment`, refusals
    are reported rather than silently ignored, and no decision is evidence.
    """

    attention = dict(segment["attention"])
    if target is not None and target not in segment["regions"]:
        raise ResonantNumericalError("organising target is unknown")
    if target is None:
        attention.update({"target": None, "remaining": 0, "settled": True,
                          "progress": 0.0, "admitted_stage": None})
        segment["attention"] = attention
        return {"schema": CIRCULATION_ATTENTION_SCHEMA, "admitted": False,
                "released": True, "target": None,
                "retargets": int(attention["retargets"])}
    limit = int(attention["stage_limit"]) if stages is None else int(stages)
    if limit < 1 or limit > int(attention["stage_limit"]):
        raise ResonantNumericalError("organising stage allowance is invalid")
    current = attention["target"]
    progress = float(attention["progress"])
    measured = (progress if not attention["settled"]
                else circulation_alignment(segment)["mean"])
    if (current is not None and current != target and not attention["settled"]
            and progress >= float(attention["exit_threshold"])):
        return {"schema": CIRCULATION_ATTENTION_SCHEMA, "admitted": False,
                "released": False, "target": current, "requested": target,
                "refused": "current organising frame is still settling",
                "progress": progress, "retargets": int(attention["retargets"])}
    if (current is None or current == target) and attention["settled"] and \
            measured < float(attention["entry_threshold"]):
        return {"schema": CIRCULATION_ATTENTION_SCHEMA, "admitted": False,
                "released": False, "target": None, "requested": target,
                "refused": "orientation is already aligned inside the entry threshold",
                "progress": measured, "retargets": int(attention["retargets"])}
    retarget = current != target
    attention.update({
        "target": target,
        "admitted_stage": int(segment["continuation"]["pass"]),
        "progress": measured,
        "remaining": limit,
        "settled": False,
        "retargets": int(attention["retargets"]) + (1 if retarget else 0),
    })
    segment["attention"] = attention
    return {"schema": CIRCULATION_ATTENTION_SCHEMA, "admitted": True,
            "released": False, "target": target, "retarget": retarget,
            "stages": limit, "retargets": int(attention["retargets"])}


# ---------------------------------------------------------------------------
# Bounded units.
# ---------------------------------------------------------------------------


def _bind_stage(segment: Mapping[str, Any], parent: str, child: str,
                version: str | None = None) -> dict[str, Any]:
    """Bind one interface to the current region versions.

    The recorded stage must agree with its own bound versions; when the
    regions' content advanced since it was written (a refresh or retune), the
    interface is re-bound to the current versions rather than admitting a
    transfer priced against another stage.
    """

    raw = segment["stages"][f"{parent}->{child}"]
    if version is not None and raw["version"] != version:
        raise ResonantStageMismatchError(
            "circulation interface is bound to another stage version"
        )
    recorded = ResonantExchangeStage.bind(
        raw["parent_version"], raw["child_version"], version=raw["version"]
    )
    if recorded.digest != raw["digest"]:
        raise ResonantStageMismatchError(
            "circulation interface stage does not match its recorded versions"
        )
    parent_version = f"{parent}@{int(segment['regions'][parent]['content_version'])}"
    child_version = f"{child}@{int(segment['regions'][child]['content_version'])}"
    rebound = (recorded.parent_version != parent_version
               or recorded.child_version != child_version)
    stage = (ResonantExchangeStage.bind(parent_version, child_version,
                                        version=raw["version"])
             if rebound else recorded)
    return {"stage": stage, "rebound": rebound, "parent_version": parent_version,
            "child_version": child_version, "recorded_digest": recorded.digest}


def _ledger(segment: Mapping[str, Any]) -> dict[str, float]:
    return {key: float(value) for key, value in segment["ledger"].items()}


def _sorted_regions(segment: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    return sorted(segment["regions"].items())


def _set_phase(segment: dict[str, Any], phase: str) -> None:
    continuation = dict(segment["continuation"])
    continuation["phase"] = phase
    continuation["cursor"] = 0
    segment["continuation"] = continuation


def _advance(segment: dict[str, Any], phase: str, cursor: int, limit: int) -> None:
    continuation = dict(segment["continuation"])
    if cursor + 1 < limit:
        continuation["cursor"] = cursor + 1
        segment["continuation"] = continuation
        return
    if phase == "close":
        continuation["pass"] = int(continuation["pass"]) + 1
        continuation["phase"] = "refresh"
    else:
        continuation["phase"] = _PHASES[_PHASES.index(phase) + 1]
    continuation["cursor"] = 0
    segment["continuation"] = continuation


def _phase_limit(phase: str, edges: Sequence[Any],
                 align_edges: Sequence[Any]) -> int:
    if phase == "exchange":
        return len(edges)
    if phase == "align":
        return len(align_edges)
    return 1


def _refresh_unit(segment: dict[str, Any], profile: Mapping[str, Any],
                  words: np.ndarray, phase: str) -> dict[str, Any]:
    """Rebuild every block's derived view from the owned words."""

    changed = 0
    for identity, raw in _sorted_regions(segment):
        first, last = _block_span(raw)
        record = circulation_record(
            profile, words, identity=identity, first=first, last=last,
            parent=raw["parent_id"],
            axis=np.asarray(raw["axial_frame"], dtype=np.float64)[:, 0],
        )
        payload = _record_payload(record)
        payload["content_version"] = int(raw["content_version"]) + 1
        payload["numerical_time"] = float(raw["numerical_time"])
        payload["integration_phase"] = phase
        payload["relative_phases"] = _plain(raw["relative_phases"])
        payload["geometric_parameters"] = _plain(raw["geometric_parameters"])
        accounts = dict(raw["resource_accounts"])
        accounts["derived_updates"] = float(accounts.get("derived_updates", 0.0) + 1.0)
        payload["resource_accounts"] = accounts
        payload["interface_work"] = float(raw["interface_work"])
        payload["interface_dependencies"] = list(raw["interface_dependencies"])
        payload["unfinished_work"] = _plain(raw["unfinished_work"])
        payload["stale"] = False
        segment["regions"][identity] = _persisted(payload)
        changed += 1
    ledger = _ledger(segment)
    ledger["derived_updates"] += float(changed)
    segment["ledger"] = ledger
    return {"phase": phase, "regions": changed}


def _exchange_unit(segment: dict[str, Any], profile: Mapping[str, Any],
                   operator: _RegionalWaveOperator, words: np.ndarray,
                   parent: str, child: str) -> dict[str, Any]:
    blocks = {identity: _block_span(raw) for identity, raw in _sorted_regions(segment)}
    table = _operator_rows(profile, operator, segment["operator"])
    interface = _interface_weights(table, profile, blocks, parent, child)
    binding = _bind_stage(segment, parent, child)
    count = words.size // 4
    energy_before, gradient = operator.energy_gradient(words)
    parent_first, parent_last = blocks[parent]
    child_first, child_last = blocks[child]
    parent_direction = np.asarray(interface["parent_direction"], dtype=np.float64)
    child_direction = np.asarray(interface["child_direction"], dtype=np.float64)
    base_weight = float(interface["weight"])
    spectral_trace = _spectral_exchange_factor(segment, operator, words, parent, child)
    weight = base_weight * float(spectral_trace["factor"])
    lanes = []
    pairing = 0.0
    for position_lane, momentum_lane in ((0, 2), (1, 3)):
        position = position_lane * count
        momentum = momentum_lane * count
        child_velocity = float(child_direction @ gradient[
            momentum + child_first:momentum + child_last
        ])
        parent_potential = float(parent_direction @ gradient[
            position + parent_first:position + parent_last
        ])
        lanes.append((position, momentum, parent_potential, child_velocity))
        pairing += abs(parent_potential * child_velocity)
    floor = max(64.0 * _EPSILON * max(1.0, abs(float(energy_before)),
                                       operator.roundoff_scales(words)[1]), 1e-300)
    step = CIRCULATION_STEP
    halvings = 0
    before = words.copy()
    change = 0.0
    first_order = 0.0
    remainder = 0.0
    allowance = 0.0
    shift = {"parent_position": 0.0, "child_momentum": 0.0}
    while True:
        before = words.copy()
        for position, momentum, parent_potential, child_velocity in lanes:
            words[position + parent_first:position + parent_last] += (
                step * weight * child_velocity * parent_direction
            )
            words[momentum + child_first:momentum + child_last] -= (
                step * weight * parent_potential * child_direction
            )
        first_order = 0.0
        shift = {"parent_position": 0.0, "child_momentum": 0.0}
        for position, momentum, _parent_potential, _child_velocity in lanes:
            delta_position = (words[position + parent_first:position + parent_last]
                              - before[position + parent_first:position + parent_last])
            delta_momentum = (words[momentum + child_first:momentum + child_last]
                              - before[momentum + child_first:momentum + child_last])
            first_order += float(
                gradient[position + parent_first:position + parent_last] @ delta_position
            ) + float(
                gradient[momentum + child_first:momentum + child_last] @ delta_momentum
            )
            shift["parent_position"] += float(np.linalg.norm(delta_position))
            shift["child_momentum"] += float(np.linalg.norm(delta_momentum))
        change = operator.energy_gradient(words)[0] - float(energy_before)
        remainder = abs(change - first_order)
        allowance = (CIRCULATION_REMAINDER_FRACTION * weight * pairing * step + floor)
        if remainder <= allowance or halvings >= CIRCULATION_MAX_HALVINGS:
            break
        words[:] = before
        step *= 0.5
        halvings += 1
    allowance_met = bool(remainder <= allowance)
    ledger = _ledger(segment)
    ledger["exchanges"] += 1.0
    ledger["interface_transfer_work"] += float(change)
    ledger["interface_first_order_work"] += float(first_order)
    ledger["interface_halvings"] += float(halvings)
    ledger["interface_allowance"] = max(ledger["interface_allowance"], float(allowance))
    ledger["interface_remainder"] = max(ledger["interface_remainder"], float(remainder))
    segment["ledger"] = ledger
    spectral_record = _record_spectral_exchange(
        segment, spectral_trace, base_weight=base_weight,
        effective_weight=weight, physical_transfer_work=change, words=words,
    )
    exchange_index = int(ledger["exchanges"])
    for identity in (parent, child):
        raw = dict(segment["regions"][identity])
        raw["content_version"] = int(raw["content_version"]) + 1
        raw["integration_phase"] = "exchange"
        raw["interface_work"] = float(raw["interface_work"]) + float(change) / 2.0
        raw["unfinished_work"] = {
            "pass": int(segment["continuation"]["pass"]),
            "interface": f"{parent}->{child}",
        }
        raw["interface_dependencies"] = [f"{parent}->{child}@{exchange_index}"]
        accounts = dict(raw["resource_accounts"])
        accounts["exchanges"] = float(accounts.get("exchanges", 0.0) + 1.0)
        raw["resource_accounts"] = _plain(accounts)
        raw["stale"] = True
        segment["regions"][identity] = _persisted(raw)
    next_version = f"stage-{exchange_index}"
    next_stage = ResonantExchangeStage.bind(
        f"{parent}@{int(segment['regions'][parent]['content_version'])}",
        f"{child}@{int(segment['regions'][child]['content_version'])}",
        version=next_version,
    )
    segment["stages"][f"{parent}->{child}"] = {
        "version": next_stage.version, "parent_version": next_stage.parent_version,
        "child_version": next_stage.child_version, "digest": next_stage.digest,
    }
    return {
        "phase": "exchange", "parent": parent, "child": child,
        "kind": interface["kind"], "weight": weight, "step": float(step),
        "halvings": halvings, "allowance": float(allowance),
        "remainder": float(remainder), "allowance_met": allowance_met,
        "transfer_scale": float(weight * pairing * step),
        "first_order_work": float(first_order), "transfer_work": float(change),
        "spectral": _plain(spectral_record),
        "stage": binding["stage"].digest, "rebound": bool(binding["rebound"]),
        "parent_position_shift": float(shift["parent_position"]),
        "child_momentum_shift": float(shift["child_momentum"]),
    }


def _align_unit(segment: dict[str, Any], parent: str, child: str) -> dict[str, Any]:
    """Retune two blocks' axial orientation and reference phase.

    The pair's declared alignment potential is decreased by one bounded step;
    the measured decrease is the parameter work this unit spends and is
    charged to the field's energy balance.  A step that would raise the
    potential is refused and reported instead of applied.
    """

    if parent == child:
        raise ResonantNumericalError("a scale block does not align with itself")
    parent_raw = dict(segment["regions"][parent])
    child_raw = dict(segment["regions"][child])
    parent_axis = np.asarray(parent_raw["axial_frame"], dtype=np.float64)[:, 0]
    child_axis = np.asarray(child_raw["axial_frame"], dtype=np.float64)[:, 0]
    parent_phase = float(parent_raw["relative_phases"].get("self", 0.0))
    child_phase = float(child_raw["relative_phases"].get("self", 0.0))
    before = alignment_energy(parent_axis, child_axis, phase_parent=parent_phase,
                              phase_child=child_phase)
    gradients = alignment_gradients(parent_axis, child_axis, phase_parent=parent_phase,
                                   phase_child=child_phase)
    tolerance = max(1e-15, 1e-12 * max(1.0, abs(before)))
    step = CIRCULATION_STEP
    halvings = 0
    after = before
    next_parent_axis, next_child_axis = parent_axis, child_axis
    next_parent_phase, next_child_phase = parent_phase, child_phase
    parent_residual = child_residual = 0.0
    while True:
        next_parent_axis, parent_residual = alignment_step(
            parent_axis, gradients["parent_axis"], step
        )
        next_child_axis, child_residual = alignment_step(
            child_axis, gradients["child_axis"], step
        )
        next_parent_phase = parent_phase - step * float(gradients["parent_phase"])
        next_child_phase = child_phase - step * float(gradients["child_phase"])
        after = alignment_energy(next_parent_axis, next_child_axis,
                                 phase_parent=next_parent_phase,
                                 phase_child=next_child_phase)
        if after <= before + tolerance or halvings >= CIRCULATION_MAX_HALVINGS:
            break
        step *= 0.5
        halvings += 1
    ledger = _ledger(segment)
    refused = None
    parameter_work = 0.0
    if after > before + tolerance:
        refused = "alignment step would increase the declared potential"
        after = before
        next_parent_axis, next_child_axis = parent_axis, child_axis
        next_parent_phase, next_child_phase = parent_phase, child_phase
    else:
        parameter_work = float(before - after)
        for identity, axis, phase in ((parent, next_parent_axis, next_parent_phase),
                                      (child, next_child_axis, next_child_phase)):
            raw = dict(segment["regions"][identity])
            raw["axial_frame"] = _circulation_frame(axis).tolist()
            phases = dict(raw["relative_phases"])
            phases["self"] = float(phase)
            raw["relative_phases"] = _plain(phases)
            raw["content_version"] = int(raw["content_version"]) + 1
            raw["integration_phase"] = "align"
            accounts = dict(raw["resource_accounts"])
            accounts["alignments"] = float(accounts.get("alignments", 0.0) + 1.0)
            raw["resource_accounts"] = _plain(accounts)
            segment["regions"][identity] = _persisted(raw)
        ledger["alignments"] += 1.0
        ledger["parameter_work"] += parameter_work
        ledger["alignment_energy"] = float(after)
        segment["ledger"] = ledger
    attention = dict(segment["attention"])
    if attention["target"] in {parent, child} and not attention["settled"]:
        attention["progress"] = float(after)
        attention["remaining"] = max(0, int(attention["remaining"]) - 1)
        if int(attention["remaining"]) == 0:
            attention["settled"] = True
        segment["attention"] = attention
    return {
        "phase": "align", "parent": parent, "child": child,
        "alignment_before": float(before), "alignment_after": float(after),
        "parameter_work": parameter_work, "refused": refused,
        "step": float(step), "halvings": halvings,
        "tangent_residual": float(max(parent_residual, child_residual)),
        "phase_mismatch": float(math.remainder(next_child_phase - next_parent_phase,
                                               2.0 * math.pi)),
        "target": attention["target"], "settled": bool(attention["settled"]),
    }


def _close_unit(segment: dict[str, Any], profile: Mapping[str, Any],
                operator: _RegionalWaveOperator, words: np.ndarray) -> dict[str, Any]:
    """Measure the pass's geometry over freshly derived block views."""

    _refresh_unit(segment, profile, words, "close")
    continuation = segment["continuation"]
    previous = None
    if continuation["measured"]:
        previous = {
            "longitudinal_direction": segment["geometry"]["longitudinal_direction"],
            "amplitude": float(continuation["amplitude"]),
            "angle": float(continuation["angle"]),
            "signed_current": float(segment["geometry"]["signed_current"]),
        }
    geometry, measured = _geometry_payload(profile, segment["regions"], previous,
                                           segment["operator"])
    segment["geometry"] = _plain(geometry)
    attach_measured(segment, measured)
    duration = float(profile["time_step"])
    for identity, raw in _sorted_regions(segment):
        payload = dict(raw)
        payload["numerical_time"] = float(raw["numerical_time"]) + duration
        payload["integration_phase"] = "idle"
        payload["unfinished_work"] = {}
        segment["regions"][identity] = _persisted(payload)
    ledger = _ledger(segment)
    ledger["stages"] += 1.0
    segment["ledger"] = ledger
    attention = dict(segment["attention"])
    if attention["target"] is not None and not attention["settled"]:
        attention["progress"] = circulation_alignment(segment)["mean"]
        attention["remaining"] = max(0, int(attention["remaining"]) - 1)
        if int(attention["remaining"]) == 0:
            attention["settled"] = True
        segment["attention"] = attention
    stage_receipt = {"phase": "close", "pass": int(continuation["pass"]) + 1,
                     "geometry": _plain(geometry), "measured": _plain(measured),
                     "coverage": float(geometry["coverage"]),
                     "attention": _plain(segment["attention"])}
    return stage_receipt


def circulation_unit(state: dict[str, Any], *,
                     operator: _RegionalWaveOperator | None = None,
                     device: str | None = None,
                     resource_limits: Any = None) -> dict[str, Any]:
    """Execute one bounded circulation unit over the canonical task state."""

    segment = state["circulation"]
    if segment["schema"] == _LEGACY_CIRCULATION_SCHEMA:
        segment["schema"] = CIRCULATION_SCHEMA
        segment["spectrum"] = _initial_spectrum(
            tuple(segment["regions"]), tuple(tuple(edge) for edge in segment["edges"])
        )
    profile = state["profile"]
    words = np.asarray(state["wave_words"]["values"], dtype=np.float64)
    selected = operator if operator is not None else _RegionalWaveOperator(
        profile, state["bindings"], _regional_objective_data(state["objective"]),
        device=device, resources=resource_limits,
    )
    edges = [tuple(edge) for edge in segment["edges"]]
    align_edges = [edge for edge in edges if edge[0] != edge[1]]
    continuation = segment["continuation"]
    phase = continuation["phase"]
    cursor = int(continuation["cursor"])
    if phase == "align" and not align_edges:
        _set_phase(segment, "close")
        phase, cursor = "close", 0
    limit = _phase_limit(phase, edges, align_edges)
    if phase == "refresh":
        receipt = _refresh_unit(segment, profile, words, "refresh")
    elif phase == "exchange":
        parent, child = edges[cursor]
        receipt = _exchange_unit(segment, profile, selected, words, parent, child)
    elif phase == "align":
        parent, child = align_edges[cursor]
        receipt = _align_unit(segment, parent, child)
    else:
        receipt = _close_unit(segment, profile, selected, words)
    _advance(segment, phase, cursor, limit)
    state["wave_words"] = {"layout": "qY,qI,pY,pI:f64", "values": words.tolist()}
    return receipt


def circulation_stage(state: dict[str, Any], *, quantum: int = 1,
                      passes: int = CIRCULATION_DEFAULT_PASSES,
                      operator: _RegionalWaveOperator | None = None,
                      device: str | None = None,
                      resource_limits: Any = None) -> dict[str, Any]:
    """Run bounded circulation units until the requested passes complete.

    ``operator`` reuses a caller's wave operator, so its application counter
    keeps accumulating on one instance across dispatch boundaries.  If omitted,
    ``device`` and ``resource_limits`` are forwarded to the regional operator.
    """

    bound = _integer(quantum, "circulation quantum", minimum=1,
                     maximum=CIRCULATION_MAX_PASSES)
    target = _integer(passes, "circulation passes", minimum=1,
                      maximum=CIRCULATION_MAX_PASSES)
    segment = state["circulation"]
    selected = operator if operator is not None else _RegionalWaveOperator(
        state["profile"], state["bindings"],
        _regional_objective_data(state["objective"]),
        device=device, resources=resource_limits,
    )
    executed = 0
    receipts: list[dict[str, Any]] = []
    while executed < bound:
        continuation = segment["continuation"]
        if (int(continuation["pass"]) >= target and continuation["phase"] == "refresh"
                and int(continuation["cursor"]) == 0):
            break
        receipts.append(circulation_unit(state, operator=selected))
        executed += 1
    continuation = segment["continuation"]
    complete = (int(continuation["pass"]) >= target
                and continuation["phase"] == "refresh"
                and int(continuation["cursor"]) == 0)
    return {
        "schema": CIRCULATION_STAGE_SCHEMA,
        "units": executed,
        "passes": int(continuation["pass"]),
        "complete": bool(complete),
        "phase": continuation["phase"],
        "cursor": int(continuation["cursor"]),
        "ledger": _ledger(segment),
        "receipts": receipts,
    }


def circulation_frame_change(segment: dict[str, Any], rotation: Any) -> dict[str, Any]:
    """Turn every declared axial frame by one proper rotation.

    A passive change of frame rotates the stored axial frames with their
    orientation-invariant scalars.  It changes no numerical state, spends no
    work, and leaves the measured readout scalars (signed current, handedness)
    unchanged.
    """

    matrix = _as_f64(rotation, (3, 3), "rotation")
    if (not np.allclose(matrix.T @ matrix, np.eye(3), atol=2e-10, rtol=0)
            or float(np.linalg.det(matrix)) <= 0.0):
        raise ResonantNumericalError("a passive frame change must be a proper rotation")
    before = circulation_readout(segment)
    for identity, raw in _sorted_regions(segment):
        payload = dict(raw)
        payload["axial_frame"] = _circulation_frame(
            matrix @ np.asarray(raw["axial_frame"], dtype=np.float64)[:, 0]
        ).tolist()
        payload["content_version"] = int(raw["content_version"]) + 1
        segment["regions"][identity] = _persisted(payload)
    after = circulation_readout(segment)
    report = {
        "schema": CIRCULATION_ROTATION_SCHEMA,
        "proper": True,
        "field_state_unchanged": True,
        "physical_work": 0.0,
        "parameter_work": float(segment["ledger"]["parameter_work"]),
        "signed_current_before": float(before["geometry"]["signed_current"]),
        "signed_current_after": float(after["geometry"]["signed_current"]),
        "handedness_before": int(before["geometry"]["handedness"]),
        "handedness_after": int(after["geometry"]["handedness"]),
        "authority": "operational-report-only",
    }
    if (report["signed_current_before"] != report["signed_current_after"]
            or report["handedness_before"] != report["handedness_after"]):
        raise ResonantNumericalError("a passive frame change altered a scalar readout")
    return report
def working_field_exchange_view(
    embodied_snapshot: Mapping[str, Any],
    selected_field: Mapping[str, Any],
    *,
    limit: int = 8,
) -> dict[str, Any]:
    """Return bounded owner-verified exchanges relevant to one working concern.

    The embodied snapshot is the owner's read-only projection.  This helper
    joins only its already source-verified exchange items to their exact
    regional operator reports; it neither reads nor retains field state.
    """

    bound = _integer(limit, "working-field exchange limit", minimum=1, maximum=64)
    concern_ref = selected_field.get("concern_ref")
    unavailable = {
        "status": "unavailable",
        "concern_ref": _plain(concern_ref) if isinstance(concern_ref, Mapping) else None,
        "items": [],
        "limit": bound,
        "truncated": False,
        "reason": "selected working field has no exact semantic concern reference",
    }
    def exact_ref(value: Any) -> bool:
        return isinstance(value, Mapping) and {
            "id", "kind", "content_version"
        }.issubset(value)

    nested_refs = (
        concern_ref.get("question_ref"),
        concern_ref.get("goal_ref"),
        *(concern_ref.get("object_refs", ()) if isinstance(
            concern_ref.get("object_refs", ()), (list, tuple)
        ) else ()),
    ) if isinstance(concern_ref, Mapping) else ()
    if not isinstance(concern_ref, Mapping) or not any(exact_ref(ref) for ref in nested_refs):
        return unavailable

    exchange_meaning = embodied_snapshot.get("exchange_meaning")
    if not isinstance(exchange_meaning, Mapping):
        unavailable["reason"] = "owner exchange projection is unavailable"
        return unavailable
    raw_items = exchange_meaning.get("items")
    regional_by_computer: dict[str, Mapping[str, Any]] = {}

    if not isinstance(raw_items, (list, tuple)):
        unavailable["reason"] = "owner exchange projection has no item list"
        return unavailable

    circulation = embodied_snapshot.get("circulation")
    circulation_value = (
        circulation.get("value") if isinstance(circulation, Mapping) else None
    )
    regional_reports = (
        circulation_value.get("regional")
        if isinstance(circulation_value, Mapping) else None
    )
    if isinstance(regional_reports, (list, tuple)):
        for report in regional_reports:
            if isinstance(report, Mapping) and isinstance(report.get("computer_id"), str):
                regional_by_computer[report["computer_id"]] = report


    if exchange_meaning.get("status") != "known":
        unavailable["reason"] = exchange_meaning.get("reason") or (
            "owner exchange projection is unavailable"
        )
        unavailable["truncated"] = bool(exchange_meaning.get("truncated"))
        return unavailable
    matching: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, Mapping) or item.get("concern_ref") != concern_ref:
            continue
        basis = item.get("appraisal_basis")
        assessment_ref = item.get("assessment_ref")
        source = item.get("result_source")
        appraisal = item.get("last_appraisal_ref")
        exchange = item.get("exchange")
        if (
            item.get("current_concern_ref") != concern_ref
            or not isinstance(basis, Mapping)
            or set(basis) != {"assessment_ref", "source_revision_id", "source_sha256"}
            or basis.get("assessment_ref") != assessment_ref
            or not isinstance(assessment_ref, Mapping)
            or not {"id", "kind", "content_version"}.issubset(assessment_ref)
            or not isinstance(basis.get("source_revision_id"), str)
            or not isinstance(basis.get("source_sha256"), str)
            or not isinstance(source, Mapping)
            or source.get("revision_id") != basis.get("source_revision_id")
            or source.get("content_sha256") != basis.get("source_sha256")
            or not isinstance(appraisal, Mapping)
            or not isinstance(appraisal.get("operation_id"), str)
            or not isinstance(appraisal.get("assessment_sha256"), str)
            or not isinstance(exchange, Mapping)
            or exchange.get("status") != "available"
            or not isinstance(exchange.get("owner_reported_last_exchange_sha256"), str)
        ):
            continue

        computer_id = item.get("computer_id")
        interface = item.get("interface")
        regional = regional_by_computer.get(computer_id) if isinstance(computer_id, str) else None
        spectrum = regional.get("spectrum") if isinstance(regional, Mapping) else None
        spectrum_interfaces = spectrum.get("interfaces") if isinstance(spectrum, Mapping) else None
        spectrum_interface = (
            spectrum_interfaces.get(interface)
            if isinstance(spectrum_interfaces, Mapping) and isinstance(interface, str)
            else None
        )
        feedback = exchange.get("feedback")
        if (
            not isinstance(feedback, Mapping)
            or feedback.get("status") != "available"
            or feedback.get("concern_ref") != concern_ref
            or feedback.get("appraisal_basis") != basis
        ):
            feedback = {
                "status": "unavailable",
                "reason": "no feedback matches this concern and appraisal",
            }
        matching.append({
            "computer_id": computer_id,
            "interface": interface,
            "emitter_region_id": item.get("emitter_region_id"),
            "receiver_region_id": item.get("receiver_region_id"),
            "obligation_ref": item.get("obligation_ref"),
            "concern_ref": item.get("concern_ref"),
            "assessment_ref": assessment_ref,
            "appraisal_basis": basis,
            "last_appraisal_ref": appraisal,
            "result_source": source,
            "exchange": exchange,
            "feedback": feedback,
            "spectrum_interface": (
                spectrum_interface if isinstance(spectrum_interface, Mapping)
                else {"status": "unavailable", "reason": (
                    "operator-projected spectrum interface is unavailable"
                )}
            ),
        })

    was_truncated = bool(exchange_meaning.get("truncated")) or (
        isinstance(circulation_value, Mapping)
        and bool(circulation_value.get("truncated"))
    )
    unavailable.update({
        "status": "known" if matching else "unavailable",
        "items": matching[:bound],
        "truncated": was_truncated or len(matching) > bound,
        "reason": None if matching else (
            "no owner exchange has a current exact concern, appraisal, and source identity"
        ),
    })
    return unavailable
