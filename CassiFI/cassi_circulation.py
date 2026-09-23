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

CIRCULATION_SCHEMA = "cassifi.resonant-circulation.v1"
CIRCULATION_STAGE_SCHEMA = "cassifi.resonant-circulation-stage.v1"
CIRCULATION_READOUT_SCHEMA = "cassifi.resonant-circulation-readout.v1"
CIRCULATION_ACTIVITY_SCHEMA = "cassifi.resonant-circulation-activity.v1"
CIRCULATION_MODULATION_AUTHORITY = "eligible-work-modulation-only"
CIRCULATION_ATTENTION_SCHEMA = "cassifi.resonant-attention.v1"
CIRCULATION_ROTATION_SCHEMA = "cassifi.resonant-frame-change.v1"
CIRCULATION_BASIS_VERSION = "block-haar-v1"
CIRCULATION_REGION_SCOPE = "resonant-scale"
CIRCULATION_STEP = 0.05
CIRCULATION_REMAINDER_FRACTION = 0.05
CIRCULATION_MAX_HALVINGS = 6
CIRCULATION_ATTENTION_STAGES = 32
CIRCULATION_DEFAULT_PASSES = 1
CIRCULATION_MAX_PASSES = 4096
CIRCULATION_VIEW_SOURCE = "rebuilt-on-refresh"

_CIRCULATION_KEYS = frozenset({
    "schema", "enabled", "basis", "views", "blocks", "regions", "edges",
    "stages", "geometry", "operator", "attention", "continuation", "ledger",
})
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
_STAGE_KEYS = frozenset({"version", "parent_version", "child_version", "digest"})
_PHASES = ("refresh", "exchange", "align", "close")
# Declared relative scales of the canonical metric structure, one per kind.
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
    stages: dict[str, Any] = {}
    for parent, child in circulation_interfaces(selected):
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
        "edges": [list(edge) for edge in circulation_interfaces(selected)],
        "stages": stages,
        "geometry": geometry,
        "operator": _operator_record(operator),
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


def validate_circulation(segment: Any) -> None:
    """Validate one canonical circulation segment."""

    if not isinstance(segment, Mapping) or set(segment) != _CIRCULATION_KEYS:
        raise ResonantNumericalError("circulation segment keys are invalid")
    if segment["schema"] != CIRCULATION_SCHEMA:
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
    return {
        "schema": CIRCULATION_ACTIVITY_SCHEMA,
        "values": values,
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
        "coverage": activity["coverage"],
        "signed_current": activity["signed_current"],
        "handedness": activity["handedness"],
        "degenerate": activity["degenerate"],
        "dependencies": {
            "basis": segment["basis"],
            "pass": int(segment["continuation"]["pass"]),
            "operator_digest": operator["digest"],
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
    weight = float(interface["weight"])
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
