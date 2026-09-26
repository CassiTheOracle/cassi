#!/usr/bin/env python3
"""Deterministic EY/EI topology observatory and synthetic self-test.

Run from the CassiCosmos repository root as::

    python research/meshless/verify_topology_observatory.py [snapshot.json]

The detector works only on theta = atan2(EI, EY).  Optional Pi and particle
vorticity arrays are reported as parent diagnostics and are never promoted to a
compact phase/current field.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

TAU = 2.0 * math.pi
SYNTHETIC_N = 33
AMPLITUDE = 1.0
AMP_FLOOR = 1.0e-12
PARENT_ACTIVITY_FLOOR = 1.0e-12
RING_RADIUS = 8.5
RING_LENGTH_REL_TOL = 0.65
ORIENTATIONS = ("xy", "yz", "zx")
NORMAL_AXIS = {"xy": 2, "yz": 0, "zx": 1}
DEFAULT_REPORT = Path(__file__).resolve().parents[2] / "_diag" / "topology_observatory_report.json"


class SnapshotError(ValueError):
    """Raised when a live snapshot does not satisfy the frozen input contract."""


@dataclass(frozen=True)
class DualFace:
    """One nonzero primal plaquette and its two dual-link endpoints."""

    orientation: str
    coordinate: tuple[int, int, int]
    winding: int
    endpoint_a: tuple[int, int, int]
    endpoint_b: tuple[int, int, int]
    normal_axis: int


@dataclass
class Detection:
    """Internal detector result; numpy arrays are kept out of JSON reports."""

    grid_n: int
    theta: np.ndarray
    amplitude: np.ndarray
    edges: dict[str, np.ndarray]
    windings: dict[str, np.ndarray]
    faces: list[DualFace]
    metrics: dict[str, Any]


@dataclass
class UnionFind:
    parent: list[int]
    rank: list[int]

    @classmethod
    def for_size(cls, size: int) -> "UnionFind":
        return cls(list(range(size)), [0] * size)

    def find(self, item: int) -> int:
        parent = self.parent
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        if self.rank[root_left] < self.rank[root_right]:
            root_left, root_right = root_right, root_left
        self.parent[root_right] = root_left
        if self.rank[root_left] == self.rank[root_right]:
            self.rank[root_left] += 1


def wrap_phase_delta(delta: np.ndarray) -> np.ndarray:
    """Wrap phase increments to the preregistered interval ``(-pi, pi]``."""

    wrapped = (delta + math.pi) % TAU - math.pi
    # The modulo expression is [-pi, pi); the endpoint is assigned to +pi.
    return np.where(wrapped <= -math.pi, math.pi, wrapped)


def _validate_cubic_field(field: np.ndarray) -> int:
    if field.ndim != 3 or field.shape[0] != field.shape[1] or field.shape[1] != field.shape[2]:
        raise ValueError("fields must have cubic shape (N, N, N)")
    if field.shape[0] < 2:
        raise ValueError("grid_N must be greater than one")
    return int(field.shape[0])


def phase_components(theta: np.ndarray, amplitude: float = AMPLITUDE) -> tuple[np.ndarray, np.ndarray]:
    """Convert a phase field to nonzero-amplitude EY/EI components."""

    return amplitude * np.cos(theta), amplitude * np.sin(theta)


def build_synthetic_theta(control: str, grid_n: int = SYNTHETIC_N) -> np.ndarray:
    """Build one frozen, deterministic 3-D phase control."""

    if grid_n < 2:
        raise ValueError("grid_n must be greater than one")
    x, y, z = np.indices((grid_n, grid_n, grid_n), dtype=np.float64)
    if control == "uniform":
        return np.full((grid_n, grid_n, grid_n), 0.35, dtype=np.float64)
    if control == "plane_wave":
        return 0.20 + TAU * 3.0 * x / float(grid_n)
    if control == "straight_line":
        x0 = grid_n // 2 - 1
        y0 = grid_n // 2 - 1
        return np.arctan2(y - (y0 + 0.5), x - (x0 + 0.5))
    if control == "vortex_ring":
        center = (grid_n - 1.0) / 2.0
        rho = np.hypot(x - center, y - center)
        return np.arctan2(z - center, rho - RING_RADIUS)
    if control == "global_rotation":
        return np.full((grid_n, grid_n, grid_n), 0.35 + 1.23456789, dtype=np.float64)
    raise ValueError(f"unknown synthetic control: {control}")


def _plaquette_windings(theta: np.ndarray) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Return open-domain wrapped edges and all three oriented winding arrays."""

    _validate_cubic_field(theta)
    dx = wrap_phase_delta(theta[1:, :, :] - theta[:-1, :, :])
    dy = wrap_phase_delta(theta[:, 1:, :] - theta[:, :-1, :])
    dz = wrap_phase_delta(theta[:, :, 1:] - theta[:, :, :-1])

    # +x,+y,-x,-y; normal +z.
    circulation_xy = dx[:, :-1, :] + dy[1:, :, :] - dx[:, 1:, :] - dy[:-1, :, :]
    # +y,+z,-y,-z; normal +x.
    circulation_yz = dy[:, :, :-1] + dz[:, 1:, :] - dy[:, :, 1:] - dz[:, :-1, :]
    # +z,+x,-z,-x; normal +y.
    circulation_zx = dz[:-1, :, :] + dx[:, :, 1:] - dz[1:, :, :] - dx[:, :, :-1]

    windings = {
        "xy": np.rint(circulation_xy / TAU).astype(np.int64),
        "yz": np.rint(circulation_yz / TAU).astype(np.int64),
        "zx": np.rint(circulation_zx / TAU).astype(np.int64),
    }
    edges = {"x": dx, "y": dy, "z": dz}
    return edges, windings


def _dual_face(orientation: str, coordinate: tuple[int, int, int], winding: int) -> DualFace:
    x, y, z = coordinate
    # A primal face at index k separates the adjacent cells k-1 and k.
    # This negative-normal offset makes all three dual-link families meet
    # at the same cell-centered dual nodes.
    if orientation == "xy":
        endpoint_a, endpoint_b = (x, y, z - 1), (x, y, z)
    elif orientation == "yz":
        endpoint_a, endpoint_b = (x - 1, y, z), (x, y, z)
    else:  # zx
        endpoint_a, endpoint_b = (x, y - 1, z), (x, y, z)
    return DualFace(
        orientation=orientation,
        coordinate=coordinate,
        winding=int(winding),
        endpoint_a=endpoint_a,
        endpoint_b=endpoint_b,
        normal_axis=NORMAL_AXIS[orientation],
    )


def extract_nonzero_plaquettes(windings: Mapping[str, np.ndarray]) -> list[DualFace]:
    """Extract integer hits in deterministic orientation/coordinate order."""

    faces: list[DualFace] = []
    for orientation in ORIENTATIONS:
        array = windings[orientation]
        for coordinate_array in np.argwhere(array != 0):
            coordinate = tuple(int(value) for value in coordinate_array)
            faces.append(_dual_face(orientation, coordinate, int(array[coordinate])))
    return faces


def _boundary_crossing(face: DualFace, grid_n: int) -> int:
    axis = face.normal_axis
    return int(face.endpoint_a[axis] == -1) + int(face.endpoint_b[axis] == grid_n - 1)


def reconstruct_components(faces: Sequence[DualFace], grid_n: int) -> list[dict[str, Any]]:
    """Union dual-face records when their dual links share an endpoint."""

    if not faces:
        return []
    union_find = UnionFind.for_size(len(faces))
    endpoint_faces: dict[tuple[int, int, int], int] = {}
    for index, face in enumerate(faces):
        for endpoint in (face.endpoint_a, face.endpoint_b):
            previous = endpoint_faces.get(endpoint)
            if previous is None:
                endpoint_faces[endpoint] = index
            else:
                union_find.union(index, previous)

    grouped: dict[int, list[int]] = {}
    for index in range(len(faces)):
        grouped.setdefault(union_find.find(index), []).append(index)

    components: list[dict[str, Any]] = []
    for component_id, indices in enumerate(sorted(grouped.values(), key=lambda group: min(group)), start=1):
        degrees: dict[tuple[int, int, int], int] = {}
        orientation_counts = {orientation: 0 for orientation in ORIENTATIONS}
        positive_count = 0
        negative_count = 0
        net_winding = 0
        boundary_crossings = 0
        for index in indices:
            face = faces[index]
            degrees[face.endpoint_a] = degrees.get(face.endpoint_a, 0) + 1
            degrees[face.endpoint_b] = degrees.get(face.endpoint_b, 0) + 1
            orientation_counts[face.orientation] += 1
            net_winding += face.winding
            positive_count += int(face.winding > 0)
            negative_count += int(face.winding < 0)
            boundary_crossings += _boundary_crossing(face, grid_n)
        if positive_count and not negative_count:
            sign = "positive"
        elif negative_count and not positive_count:
            sign = "negative"
        else:
            sign = "mixed"
        closed = bool(boundary_crossings == 0 and all(degree == 2 for degree in degrees.values()))
        components.append(
            {
                "component_id": component_id,
                "length": len(indices),
                "positive_plaquettes": positive_count,
                "negative_plaquettes": negative_count,
                "net_winding": int(net_winding),
                "sign": sign,
                "closed": closed,
                "boundary_crossings": int(boundary_crossings),
                "orientation_counts": orientation_counts,
            }
        )
    return components


def _orientation_summary(array: np.ndarray) -> dict[str, Any]:
    nonzero = array[array != 0]
    return {
        "shape": [int(value) for value in array.shape],
        "nonzero_count": int(nonzero.size),
        "positive_count": int(np.count_nonzero(array > 0)),
        "negative_count": int(np.count_nonzero(array < 0)),
        "sum_winding": int(np.sum(array, dtype=np.int64)),
        "max_abs_winding": int(np.max(np.abs(array))) if array.size else 0,
    }


def detect(ey: np.ndarray, ei: np.ndarray) -> Detection:
    """Run the detector on cubic EY/EI arrays without assuming any Pi field."""

    ey = np.asarray(ey, dtype=np.float64)
    ei = np.asarray(ei, dtype=np.float64)
    grid_n = _validate_cubic_field(ey)
    if ei.shape != ey.shape:
        raise ValueError("EY and EI shapes must match")
    if not np.all(np.isfinite(ey)) or not np.all(np.isfinite(ei)):
        raise ValueError("EY and EI must be finite")
    amplitude = np.hypot(ey, ei)
    theta = np.arctan2(ei, ey)
    edges, windings = _plaquette_windings(theta)
    faces = extract_nonzero_plaquettes(windings)
    components = reconstruct_components(faces, grid_n)
    plaquette_metrics = {orientation: _orientation_summary(windings[orientation]) for orientation in ORIENTATIONS}
    metrics: dict[str, Any] = {
        "grid_N": grid_n,
        "phase_valid": bool(np.all(np.isfinite(amplitude)) and np.all(amplitude > AMP_FLOOR)),
        "amplitude_min": float(np.min(amplitude)),
        "amplitude_max": float(np.max(amplitude)),
        "edge_shapes": {axis: [int(value) for value in edges[axis].shape] for axis in ("x", "y", "z")},
        "plaquette_metrics": plaquette_metrics,
        "nonzero_plaquettes": int(len(faces)),
        "component_count": int(len(components)),
        "boundary_crossings": int(sum(component["boundary_crossings"] for component in components)),
        "components": components,
    }
    return Detection(grid_n, theta, amplitude, edges, windings, faces, metrics)


def _null_control_passes(detection: Detection) -> tuple[bool, str]:
    exact_zero = all(np.count_nonzero(detection.windings[orientation]) == 0 for orientation in ORIENTATIONS)
    component_zero = detection.metrics["component_count"] == 0
    if exact_zero and component_zero:
        return True, "exact zero winding and zero components"
    return False, f"nonzero_plaquettes={detection.metrics['nonzero_plaquettes']} components={detection.metrics['component_count']}"


def _straight_control_passes(detection: Detection) -> tuple[bool, str]:
    grid_n = detection.grid_n
    x0 = grid_n // 2 - 1
    y0 = grid_n // 2 - 1
    xy = detection.windings["xy"]
    hits = np.argwhere(xy != 0)
    coordinates_ok = (
        len(hits) == grid_n
        and all(int(x) == x0 and int(y) == y0 for x, y, _ in hits)
        and {int(z) for _, _, z in hits} == set(range(grid_n))
    )
    orientation_ok = (
        int(np.count_nonzero(detection.windings["xy"])) == grid_n
        and int(np.count_nonzero(detection.windings["yz"])) == 0
        and int(np.count_nonzero(detection.windings["zx"])) == 0
    )
    components = detection.metrics["components"]
    component_ok = False
    if len(components) == 1:
        component = components[0]
        component_ok = bool(
            component["length"] == grid_n
            and component["sign"] in ("positive", "negative")
            and component["boundary_crossings"] == 2
            and not component["closed"]
        )
    passed = bool(coordinates_ok and orientation_ok and component_ok)
    if passed:
        return True, f"one signed W_xy plaquette per z layer, length={grid_n}, crossings=2"
    return (
        False,
        f"hits={len(hits)} components={len(components)} orientation_counts="
        f"{[int(np.count_nonzero(detection.windings[o])) for o in ORIENTATIONS]}",
    )


def _ring_control_passes(detection: Detection) -> tuple[bool, str]:
    expected_length = TAU * RING_RADIUS
    lower = expected_length * (1.0 - RING_LENGTH_REL_TOL)
    upper = expected_length * (1.0 + RING_LENGTH_REL_TOL)
    components = detection.metrics["components"]
    component_ok = False
    if len(components) == 1:
        component = components[0]
        component_ok = bool(
            component["length"] >= 1
            and component["closed"]
            and component["boundary_crossings"] == 0
            and lower <= component["length"] <= upper
            and component["positive_plaquettes"] > 0
            and component["negative_plaquettes"] > 0
        )
    if component_ok:
        return (
            True,
            f"one closed boundary-free dual loop, mixed local signs, "
            f"length={components[0]['length']} in [{lower:.2f}, {upper:.2f}]",
        )
    return False, f"components={len(components)} expected_length_interval=[{lower:.2f}, {upper:.2f}]"


def run_self_tests() -> tuple[bool, dict[str, Any], list[tuple[str, bool, str]]]:
    """Run exactly the frozen synthetic controls once."""

    controls = ("uniform", "plane_wave", "straight_line", "vortex_ring", "global_rotation")
    report: dict[str, Any] = {}
    gates: list[tuple[str, bool, str]] = []
    all_passed = True
    for control in controls:
        theta = build_synthetic_theta(control, SYNTHETIC_N)
        ey, ei = phase_components(theta)
        detection = detect(ey, ei)
        if control in {"uniform", "plane_wave", "global_rotation"}:
            passed, detail = _null_control_passes(detection)
        elif control == "straight_line":
            passed, detail = _straight_control_passes(detection)
        else:
            passed, detail = _ring_control_passes(detection)
        gate_name = {
            "uniform": "SYNTH_UNIFORM",
            "plane_wave": "SYNTH_PLANE_WAVE",
            "straight_line": "SYNTH_STRAIGHT_LINE",
            "vortex_ring": "SYNTH_VORTEX_RING",
            "global_rotation": "SYNTH_GLOBAL_ROTATION",
        }[control]
        gates.append((gate_name, passed, detail))
        report[control] = {
            "passed": bool(passed),
            "metrics": detection.metrics,
        }
        all_passed = all_passed and passed
    return all_passed, report, gates


def _flat_numeric(value: Any, field_name: str) -> np.ndarray:
    if not isinstance(value, list):
        raise SnapshotError(f"{field_name} must be a flat JSON array")
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise SnapshotError(f"{field_name} must contain only numbers") from exc
    if array.ndim != 1:
        raise SnapshotError(f"{field_name} must be a flat JSON array")
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise SnapshotError(f"{field_name} must contain finite values")
    return array


def load_snapshot(path: Path) -> tuple[int, np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"cannot read JSON snapshot {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SnapshotError("snapshot top level must be a JSON object")
    grid_n = payload.get("grid_N")
    if isinstance(grid_n, bool) or not isinstance(grid_n, int) or grid_n <= 1:
        raise SnapshotError("grid_N must be an integer greater than one")
    expected = grid_n**3
    ey_flat = _flat_numeric(payload.get("ey"), "ey")
    ei_flat = _flat_numeric(payload.get("ei"), "ei")
    if ey_flat.size != expected or ei_flat.size != expected:
        raise SnapshotError(f"ey and ei must each contain exactly grid_N**3={expected} values")
    optional: dict[str, np.ndarray] = {}
    for field_name in ("pi", "particle_vorticity"):
        if field_name in payload and payload[field_name] is not None:
            optional[field_name] = _flat_numeric(payload[field_name], field_name)
    shape = (grid_n, grid_n, grid_n)
    return grid_n, ey_flat.reshape(shape), ei_flat.reshape(shape), optional


def summarize_parent_field(values: np.ndarray | None) -> dict[str, Any]:
    """Summarize parent telemetry without interpreting it as compact phase."""

    if values is None:
        return {"present": False, "role": "diagnostic-only"}
    absolute = np.abs(values)
    return {
        "present": True,
        "role": "diagnostic-only",
        "entry_count": int(values.size),
        "finite": bool(np.all(np.isfinite(values))),
        "channel_count": None,
        "mean_abs": float(np.mean(absolute)),
        "max_abs": float(np.max(absolute)),
        "active_count": int(np.count_nonzero(absolute > PARENT_ACTIVITY_FLOOR)),
        "activity_floor": PARENT_ACTIVITY_FLOOR,
    }


def _live_report_for_snapshot(path: Path) -> tuple[dict[str, Any], bool]:
    try:
        grid_n, ey, ei, optional = load_snapshot(path)
    except SnapshotError as exc:
        return (
            {
                "present": True,
                "valid": False,
                "path": path.as_posix(),
                "verdict": "INCONCLUSIVE",
                "reason": str(exc),
                "analysis": None,
                "parent_circulation_metrics": {
                    "role": "diagnostic-only",
                    "pi": {"present": False, "role": "diagnostic-only"},
                    "particle_vorticity": {"present": False, "role": "diagnostic-only"},
                },
            },
            False,
        )

    detection = detect(ey, ei)
    phase_valid = bool(detection.metrics["phase_valid"])
    if not phase_valid:
        verdict = "INCONCLUSIVE"
        reason = f"some EY/EI amplitudes are <= AMP_FLOOR={AMP_FLOOR:g}"
    elif detection.metrics["nonzero_plaquettes"] == 0:
        verdict = "DOES NOT EMERGE"
        reason = "valid EY/EI phase has no nonzero integer plaquette winding"
    else:
        verdict = "SUPPORTS"
        reason = "valid EY/EI phase meets the detector-level nonzero-winding criterion"
    parent = {
        "role": "diagnostic-only",
        "pi": summarize_parent_field(optional.get("pi")),
        "particle_vorticity": summarize_parent_field(optional.get("particle_vorticity")),
    }
    if optional.get("pi") is not None:
        pi_size = int(optional["pi"].size)
        if pi_size % grid_n**3 == 0:
            parent["pi"]["channel_count"] = int(pi_size // (grid_n**3))
    if optional.get("particle_vorticity") is not None:
        vort_size = int(optional["particle_vorticity"].size)
        if vort_size % grid_n**3 == 0:
            parent["particle_vorticity"]["channel_count"] = int(vort_size // (grid_n**3))
    return (
        {
            "present": True,
            "valid": True,
            "path": path.as_posix(),
            "grid_N": grid_n,
            "verdict": verdict,
            "reason": reason,
            "analysis": detection.metrics,
            "parent_circulation_metrics": parent,
        },
        True,
    )


def _base_report(synthetic: dict[str, Any], self_tests_passed: bool) -> dict[str, Any]:
    return {
        "schema": "topology_observatory_report.v1",
        "observatory": "CassiCosmos meshless topology/circulation campaign",
        "self_tests_passed": bool(self_tests_passed),
        "conventions": {
            "available_state": ["EY", "EI"],
            "transient_state": ["PiY", "PiI"],
            "transient_locations": ["_field_vel", "site pi buffers"],
            "theta": "atan2(EI, EY)",
            "flat_order": "C-order reshape (x,y,z), z fastest",
            "native_buffer_flat_order": "Godot shader idx3 = x + grid_N*(y + grid_N*z), x fastest; live receipts are canonicalized before loading",
            "plaquette_orientations": {"xy": "+x,+y,-x,-y", "yz": "+y,+z,-y,-z", "zx": "+z,+x,-z,-x"},
            "dual_adjacency": "nonzero plaquette dual links share an endpoint",
            "dual_link_embedding": {
                "xy": "(x,y,z-1) -> (x,y,z)",
                "yz": "(x-1,y,z) -> (x,y,z)",
                "zx": "(x,y-1,z) -> (x,y,z)",
                "boundary_levels": "-1 and grid_N-1 along the link normal axis",
            },
            "compact_phase_field": {"present": False, "reason": "no persistent compact phase/current carrier is supplied"},
        },
        "thresholds": {
            "AMP_FLOOR": AMP_FLOOR,
            "nonzero_integer_winding": 1,
            "PARENT_ACTIVITY_FLOOR": PARENT_ACTIVITY_FLOOR,
            "RING_RADIUS": RING_RADIUS,
            "RING_LENGTH_REL_TOL": RING_LENGTH_REL_TOL,
        },
        "synthetic_controls": synthetic,
        "self_tests": {"passed": bool(self_tests_passed), "controls": synthetic},
        "live_snapshot": {
            "present": False,
            "valid": False,
            "path": None,
            "verdict": "INCONCLUSIVE",
            "reason": "no live snapshot supplied; synthetic controls are not live evidence",
            "analysis": None,
            "parent_circulation_metrics": {
                "role": "diagnostic-only",
                "pi": {"present": False, "role": "diagnostic-only"},
                "particle_vorticity": {"present": False, "role": "diagnostic-only"},
            },
        },
        "overall_verdict": "INCONCLUSIVE",
        "reserved_verdicts": ["SUPPORTS", "CONTRADICTS", "DOES NOT EMERGE", "INCONCLUSIVE"],
        "limitations": [
            "A detector hit is lattice winding in the sampled EY/EI pair only.",
            "Transient PiY/PiI values and particle_vorticity are diagnostic-only and do not enter the detector verdict.",
            "This campaign cannot establish a persistent compact phase/current field, physical strings, or string persistence.",
            "A no-live-field run is INCONCLUSIVE rather than a null physical result.",
        ],
    }


def _write_json(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, sort_keys=True, indent=2, ensure_ascii=False)
        handle.write("\n")


def _print_gate(name: str, passed: bool, detail: str) -> None:
    print(f"GATE {name} {'PASS' if passed else 'FAIL'} — {detail}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", nargs="?", type=Path, help="optional live snapshot JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT, help="JSON report path")
    args = parser.parse_args(argv)

    self_tests_passed, synthetic, gates = run_self_tests()
    for name, passed, detail in gates:
        _print_gate(name, passed, detail)

    report = _base_report(synthetic, self_tests_passed)
    live_valid = True
    if args.snapshot is None:
        _print_gate("LIVE_SNAPSHOT", True, "SKIP — no snapshot supplied; verdict remains INCONCLUSIVE")
    else:
        live_report, live_valid = _live_report_for_snapshot(args.snapshot)
        report["live_snapshot"] = live_report
        report["overall_verdict"] = live_report["verdict"] if live_valid and self_tests_passed else "INCONCLUSIVE"
        _print_gate("LIVE_SNAPSHOT", live_valid, live_report["reason"])

    if not self_tests_passed:
        report["overall_verdict"] = "INCONCLUSIVE"

    try:
        _write_json(args.output, report)
    except OSError as exc:
        _print_gate("REPORT_WRITTEN", False, str(exc))
        return 1
    _print_gate("REPORT_WRITTEN", True, args.output.as_posix())

    if self_tests_passed and live_valid:
        print("ALL CHECKS PASSED")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
