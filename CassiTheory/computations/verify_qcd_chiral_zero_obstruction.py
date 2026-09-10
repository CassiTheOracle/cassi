#!/usr/bin/env python3
"""Independently verify the frozen QCD chiral-zero obstruction receipt.

Run from the CassiTheory root after the primary calculation:
    python computations/verify_qcd_chiral_zero_obstruction.py \
        --input runs/20260910_qcd_chiral_zero_obstruction/primary/results.json \
        --output runs/20260910_qcd_chiral_zero_obstruction/verification/verification.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
import sys
from typing import Any, Callable, Mapping

import numpy as np
from numpy.polynomial.legendre import leggauss

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/qcd-chiral-zero-obstruction-prereg.md"
PRIMARY = ROOT / "computations/qcd_chiral_zero_obstruction.py"
SCHEMA = "cassi.qcd-chiral-zero-obstruction.verification.v1"
PRIMARY_SCHEMA = "cassi.qcd-chiral-zero-obstruction.v1"
RAW_SCHEMA = "cassi.qcd-chiral-zero-obstruction.raw.v1"
RADIUS = 4.0
SCALES = (0.4, 0.2, 0.1, 0.05, 0.025, 0.0125, 0.00625)
SINGULAR_VALUES = ((1.0, 1.0, 1.0), (0.6, 1.0, 1.8), (0.3, 1.2, 2.4))
DEGENERATE_VALUES = (0.0, 1.0, 2.0)
CONTROL_TAU = 0.15
CONTROL_STEP = 1.0e-6
CONTROL_POINTS = (
    (0.4, -0.3, 0.2),
    (-0.7, 0.1, 0.5),
    (0.2, 0.6, -0.4),
)
PROTOCOL_START = "<!-- qcd-chiral-zero-obstruction-protocol:start -->"
PROTOCOL_END = "<!-- qcd-chiral-zero-obstruction-protocol:end -->"
VERDICT_KEYS = tuple(f"QZO{index}" for index in range(1, 7))


class EvidenceFailure(RuntimeError):
    """A primary package is missing, malformed, or disagrees with reconstruction."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        display_path = resolved.relative_to(ROOT).as_posix()
    except ValueError:
        display_path = resolved.as_posix()
    data = resolved.read_bytes()
    return {"path": display_path, "sha256": sha256_bytes(data), "bytes": len(data)}


def strict_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def strict_json(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise EvidenceFailure(f"cannot read {path}: {error}") from error
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceFailure(f"malformed JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise EvidenceFailure(f"root of {path} is not an object")
    return value


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceFailure(f"{label} is not an object")
    return value


def require_list(value: Any, label: str, length: int | None = None) -> list[Any]:
    if not isinstance(value, list):
        raise EvidenceFailure(f"{label} is not an array")
    if length is not None and len(value) != length:
        raise EvidenceFailure(f"{label} has length {len(value)}, expected {length}")
    return value


def require_finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceFailure(f"{label} is not numeric")
    number = float(value)
    if not math.isfinite(number):
        raise EvidenceFailure(f"{label} is nonfinite")
    return number


def require_frozen_protocol(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(PROTOCOL_START) != 1 or text.count(PROTOCOL_END) != 1:
        raise EvidenceFailure("protocol markers are missing or non-unique")
    if text.index(PROTOCOL_START) >= text.index(PROTOCOL_END):
        raise EvidenceFailure("protocol markers are out of order")


def compare_identity(recorded: Any, actual: dict[str, Any], label: str) -> None:
    row = require_mapping(recorded, label)
    if dict(row) != actual:
        raise EvidenceFailure(f"{label} does not match the current file identity")


def projection_metric(tau: float, point: np.ndarray) -> np.ndarray:
    raw = np.concatenate(([tau], point.astype(np.float64, copy=False)))
    radius = float(np.linalg.norm(raw))
    unit = raw / radius
    projection = np.eye(4, dtype=np.float64) - np.outer(unit, unit)
    coordinate_derivatives = np.zeros((4, 3), dtype=np.float64)
    coordinate_derivatives[1:, :] = np.eye(3, dtype=np.float64)
    derivatives = projection @ coordinate_derivatives / radius
    return derivatives.T @ derivatives


def closed_metric(tau: float, point: np.ndarray) -> np.ndarray:
    rho2 = tau * tau + float(point @ point)
    return np.eye(3, dtype=np.float64) / rho2 - np.outer(point, point) / (rho2 * rho2)


def density_from_metric(metric: np.ndarray) -> float:
    minors = (
        metric[0, 0] * metric[1, 1] - metric[0, 1] ** 2
        + metric[0, 0] * metric[2, 2] - metric[0, 2] ** 2
        + metric[1, 1] * metric[2, 2] - metric[1, 2] ** 2
    )
    return 0.5 * float(minors)


def radial_density(tau: float, radius: float) -> float:
    rho2 = radius * radius + tau * tau
    return (radius * radius + 3.0 * tau * tau) / (2.0 * rho2**3)


def fixed_gauss(function: Callable[[np.ndarray], np.ndarray], lower: float, upper: float, order: int = 256) -> float:
    nodes, weights = leggauss(order)
    midpoint = 0.5 * (upper + lower)
    half_width = 0.5 * (upper - lower)
    values = np.asarray(function(midpoint + half_width * nodes), dtype=np.float64)
    return float(half_width * np.dot(weights, values))


def temporal_fixed(tau: float, radius: float) -> float:
    endpoint = math.atan(radius / tau)
    return fixed_gauss(
        lambda theta: (2.0 * math.pi / tau) * np.sin(theta) ** 2 * (1.0 + 2.0 * np.cos(theta) ** 2),
        0.0,
        endpoint,
    )


def puncture_fixed(inner: float, radius: float) -> float:
    endpoint = math.log(radius / inner)
    return fixed_gauss(lambda coordinate: (2.0 * math.pi / inner) * np.exp(-coordinate), 0.0, endpoint)


def cutoff_fixed(cutoff: float, radius: float) -> tuple[float, float, float]:
    interior = fixed_gauss(lambda coordinate: (6.0 * math.pi / cutoff) * coordinate**2, 0.0, 1.0)
    endpoint = math.log(radius / cutoff)
    exterior = fixed_gauss(lambda coordinate: (2.0 * math.pi / cutoff) * np.exp(-coordinate), 0.0, endpoint)
    return interior + exterior, interior, exterior


def temporal_exact(tau: float, radius: float) -> float:
    ratio = radius / tau
    return math.pi / (2.0 * tau) * (
        3.0 * math.atan(ratio)
        - ratio * (ratio * ratio + 3.0) / (1.0 + ratio * ratio) ** 2
    )


def puncture_exact(inner: float, radius: float) -> float:
    return 2.0 * math.pi * (1.0 / inner - 1.0 / radius)


def cutoff_exact(cutoff: float, radius: float) -> float:
    return 4.0 * math.pi / cutoff - 2.0 * math.pi / radius


def log_slope(rows: list[dict[str, float]], scale_key: str) -> float:
    tail = rows[-4:]
    x = np.log(np.asarray([row[scale_key] for row in tail], dtype=np.float64))
    y = np.log(np.asarray([row["numerical"] for row in tail], dtype=np.float64))
    design = np.stack((x, np.ones_like(x)), axis=1)
    solution = np.linalg.solve(design.T @ design, design.T @ y)
    return float(solution[0])


def angular_projection_coefficient(values: tuple[float, float, float], order_z: int = 512, order_phi: int = 1024) -> dict[str, Any]:
    linear = np.diag(np.asarray(values, dtype=np.float64))
    nodes, weights = leggauss(order_z)
    azimuths = (np.arange(order_phi, dtype=np.float64) + 0.5) * (2.0 * math.pi / order_phi)
    delta_phi = 2.0 * math.pi / order_phi
    total = 0.0
    minimum = math.inf
    maximum = 0.0
    for node, weight in zip(nodes, weights, strict=True):
        transverse = math.sqrt(max(0.0, 1.0 - float(node) ** 2))
        cos_phi = np.cos(azimuths)
        sin_phi = np.sin(azimuths)
        directions = np.stack(
            (transverse * cos_phi, transverse * sin_phi, np.full(order_phi, node)),
            axis=1,
        )
        derivative_z = np.stack(
            (
                (-float(node) / transverse) * cos_phi,
                (-float(node) / transverse) * sin_phi,
                np.ones(order_phi, dtype=np.float64),
            ),
            axis=1,
        )
        derivative_phi = np.stack(
            (-transverse * sin_phi, transverse * cos_phi, np.zeros(order_phi, dtype=np.float64)),
            axis=1,
        )
        image = directions @ linear.T
        image_norm = np.linalg.norm(image, axis=1)
        unit = image / image_norm[:, None]
        raw_z = derivative_z @ linear.T
        raw_phi = derivative_phi @ linear.T
        projected_z = (raw_z - unit * np.sum(unit * raw_z, axis=1)[:, None]) / image_norm[:, None]
        projected_phi = (raw_phi - unit * np.sum(unit * raw_phi, axis=1)[:, None]) / image_norm[:, None]
        jacobian = np.linalg.norm(np.cross(projected_z, projected_phi), axis=1)
        total += float(weight) * float(np.sum(jacobian * jacobian)) * delta_phi
        minimum = min(minimum, float(np.min(jacobian)))
        maximum = max(maximum, float(np.max(jacobian)))
    coefficient = 0.5 * total
    sphere_area = float(np.sum(weights) * order_phi * delta_phi)
    return {
        "singular_values": list(values),
        "rank": int(np.linalg.matrix_rank(linear)),
        "coefficient": coefficient,
        "coefficient_over_2pi": coefficient / (2.0 * math.pi),
        "sphere_area": sphere_area,
        "jacobian_min": minimum,
        "jacobian_max": maximum,
        "quadrature": {"z_rule": "fixed-gauss-legendre", "z_order": order_z, "phi_rule": "fixed-midpoint", "phi_order": order_phi},
    }


def degenerate_projection_control() -> dict[str, Any]:
    values = np.asarray(DEGENERATE_VALUES, dtype=np.float64)
    linear = np.diag(values)
    # The exact determinant vanishes, so the two-dimensional area Jacobian is
    # identically zero wherever the normalized map is defined.
    sampled = angular_projection_coefficient(DEGENERATE_VALUES, order_z=96, order_phi=192)
    return {
        "singular_values": list(DEGENERATE_VALUES),
        "rank": int(np.linalg.matrix_rank(linear)),
        "jacobian_min": 0.0,
        "sampled_jacobian_min": sampled["jacobian_min"],
        "sampled_jacobian_max": sampled["jacobian_max"],
    }


def reconstruct() -> dict[str, Any]:
    metric_rows: list[dict[str, Any]] = []
    for point_values in CONTROL_POINTS:
        point = np.asarray(point_values, dtype=np.float64)
        expected = closed_metric(CONTROL_TAU, point)
        projected = projection_metric(CONTROL_TAU, point)
        density = radial_density(CONTROL_TAU, float(np.linalg.norm(point)))
        metric_density = density_from_metric(projected)
        metric_rows.append(
            {
                "point": list(point_values),
                "tau": CONTROL_TAU,
                "projection_metric": projected.tolist(),
                "closed_metric": expected.tolist(),
                "max_projection_abs_error": float(np.max(np.abs(projected - expected))),
                "radial_density": density,
                "projection_density": metric_density,
                "density_relative_error": abs(metric_density - density) / density,
                "positive_finite_density": bool(math.isfinite(density) and density > 0.0),
            }
        )

    temporal_rows: list[dict[str, float]] = []
    for tau in SCALES:
        numerical = temporal_fixed(tau, RADIUS)
        exact = temporal_exact(tau, RADIUS)
        coefficient = tau * (numerical + 2.0 * math.pi / RADIUS)
        temporal_rows.append(
            {
                "tau_abs": tau,
                "numerical": numerical,
                "exact": exact,
                "relative_error": abs(numerical - exact) / abs(exact),
                "corrected_coefficient": coefficient,
                "coefficient_error": abs(coefficient - 3.0 * math.pi**2 / 4.0),
            }
        )

    puncture_rows: list[dict[str, float]] = []
    for inner in SCALES:
        numerical = puncture_fixed(inner, RADIUS)
        exact = puncture_exact(inner, RADIUS)
        coefficient = inner * (numerical + 2.0 * math.pi / RADIUS)
        puncture_rows.append(
            {
                "inner_radius": inner,
                "numerical": numerical,
                "exact": exact,
                "relative_error": abs(numerical - exact) / abs(exact),
                "corrected_coefficient": coefficient,
                "coefficient_error": abs(coefficient - 2.0 * math.pi),
            }
        )

    cutoff_rows: list[dict[str, float]] = []
    for cutoff in SCALES:
        numerical, interior, exterior = cutoff_fixed(cutoff, RADIUS)
        exact = cutoff_exact(cutoff, RADIUS)
        coefficient = cutoff * (numerical + 2.0 * math.pi / RADIUS)
        cutoff_rows.append(
            {
                "cutoff": cutoff,
                "interior_numerical": interior,
                "exterior_numerical": exterior,
                "numerical": numerical,
                "exact": exact,
                "relative_error": abs(numerical - exact) / abs(exact),
                "corrected_coefficient": coefficient,
                "coefficient_error": abs(coefficient - 4.0 * math.pi),
            }
        )

    anisotropy_rows = [angular_projection_coefficient(values) for values in SINGULAR_VALUES]
    return {
        "metric_controls": metric_rows,
        "temporal_rows": temporal_rows,
        "temporal_slope_last_four": log_slope(temporal_rows, "tau_abs"),
        "puncture_rows": puncture_rows,
        "puncture_slope_last_four": log_slope(puncture_rows, "inner_radius"),
        "cutoff_rows": cutoff_rows,
        "cutoff_slope_last_four": log_slope(cutoff_rows, "cutoff"),
        "anisotropy_rows": anisotropy_rows,
        "degenerate_control": degenerate_projection_control(),
        "two_derivative_energy_ball": 2.0 * math.pi * RADIUS**3,
    }


def classify(measurements: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    metric_rows = require_list(measurements["metric_controls"], "reconstruction.metric_controls", 3)
    qzo1_inputs = {
        "max_metric_entry_abs_error": max(require_finite(row["max_projection_abs_error"], "projection metric error") for row in metric_rows),
        "all_density_positive_finite": all(row.get("positive_finite_density") is True for row in metric_rows),
        "max_density_relative_error": max(require_finite(row["density_relative_error"], "density error") for row in metric_rows),
    }
    qzo1 = (
        qzo1_inputs["max_metric_entry_abs_error"] < 2.0e-9
        and qzo1_inputs["all_density_positive_finite"]
        and qzo1_inputs["max_density_relative_error"] < 2.0e-12
    )

    temporal_rows = require_list(measurements["temporal_rows"], "reconstruction.temporal_rows", 7)
    qzo2_inputs = {
        "max_relative_error": max(require_finite(row["relative_error"], "temporal error") for row in temporal_rows),
        "slope_last_four": require_finite(measurements["temporal_slope_last_four"], "temporal slope"),
        "smallest_scale_coefficient_error": require_finite(temporal_rows[-1]["coefficient_error"], "temporal coefficient error"),
    }
    qzo2 = (
        qzo2_inputs["max_relative_error"] < 2.0e-10
        and -1.02 <= qzo2_inputs["slope_last_four"] <= -0.98
        and qzo2_inputs["smallest_scale_coefficient_error"] < 5.0e-5
    )

    puncture_rows = require_list(measurements["puncture_rows"], "reconstruction.puncture_rows", 7)
    anisotropy_rows = require_list(measurements["anisotropy_rows"], "reconstruction.anisotropy_rows", 3)
    degenerate = require_mapping(measurements["degenerate_control"], "reconstruction.degenerate_control")
    qzo3_inputs = {
        "max_puncture_relative_error": max(require_finite(row["relative_error"], "puncture error") for row in puncture_rows),
        "puncture_slope_last_four": require_finite(measurements["puncture_slope_last_four"], "puncture slope"),
        "max_sphere_area_error": max(abs(require_finite(row["sphere_area"], "sphere area") - 4.0 * math.pi) for row in anisotropy_rows),
        "minimum_rank_three_coefficient": min(require_finite(row["coefficient"], "angular coefficient") for row in anisotropy_rows),
        "isotropic_coefficient_error": abs(require_finite(anisotropy_rows[0]["coefficient"], "isotropic coefficient") - 2.0 * math.pi),
        "degenerate_rank": int(degenerate["rank"]),
        "degenerate_jacobian_min": require_finite(degenerate["jacobian_min"], "degenerate Jacobian floor"),
    }
    qzo3 = (
        qzo3_inputs["max_puncture_relative_error"] < 2.0e-10
        and -1.02 <= qzo3_inputs["puncture_slope_last_four"] <= -0.98
        and qzo3_inputs["max_sphere_area_error"] < 2.0e-6
        and qzo3_inputs["minimum_rank_three_coefficient"] >= 2.0 * math.pi - 2.0e-5
        and qzo3_inputs["isotropic_coefficient_error"] < 2.0e-5
        and qzo3_inputs["degenerate_rank"] == 2
        and qzo3_inputs["degenerate_jacobian_min"] == 0.0
    )

    cutoff_rows = require_list(measurements["cutoff_rows"], "reconstruction.cutoff_rows", 7)
    qzo4_inputs = {
        "max_relative_error": max(require_finite(row["relative_error"], "cutoff error") for row in cutoff_rows),
        "slope_last_four": require_finite(measurements["cutoff_slope_last_four"], "cutoff slope"),
        "smallest_scale_coefficient_error": require_finite(cutoff_rows[-1]["coefficient_error"], "cutoff coefficient error"),
    }
    qzo4 = (
        qzo4_inputs["max_relative_error"] < 2.0e-10
        and -1.02 <= qzo4_inputs["slope_last_four"] <= -0.98
        and qzo4_inputs["smallest_scale_coefficient_error"] < 2.0e-10
    )

    gates = {
        "QZO1": {"passed": bool(qzo1), "inputs": qzo1_inputs},
        "QZO2": {"passed": bool(qzo2), "inputs": qzo2_inputs},
        "QZO3": {"passed": bool(qzo3), "inputs": qzo3_inputs},
        "QZO4": {"passed": bool(qzo4), "inputs": qzo4_inputs},
    }
    all_numerical = all(row["passed"] for row in gates.values())
    verdicts = {
        "QZO1": "PASS" if qzo1 else "FAIL",
        "QZO2": "PASS" if qzo2 else "FAIL",
        "QZO3": "PASS" if qzo3 else "FAIL",
        "QZO4": "PASS" if qzo4 else "FAIL",
        "QZO5": "CONTRADICTS" if all_numerical else "INCONCLUSIVE",
        "QZO6": "FAIL",
    }
    return gates, verdicts


def close(left: Any, right: Any, *, rel: float = 5.0e-10, absolute: float = 5.0e-11) -> bool:
    return math.isclose(require_finite(left, "comparison left"), require_finite(right, "comparison right"), rel_tol=rel, abs_tol=absolute)


def compare_primary(primary: Mapping[str, Any], raw: Mapping[str, Any], reconstructed: Mapping[str, Any], verdicts: Mapping[str, str], input_path: Path, raw_path: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("primary_schema", primary.get("schema") == PRIMARY_SCHEMA, primary.get("schema"))
    check("primary_completed", primary.get("completed") is True, primary.get("completed"))
    check("scientific_execution_started", primary.get("scientific_execution_started") is True, primary.get("scientific_execution_started"))
    check("complete_flag_false", primary.get("complete_physical_matter_formation") is False, primary.get("complete_physical_matter_formation"))
    check("failure_absent", primary.get("failure") is None, primary.get("failure"))

    protocol_identity = identity(PROTOCOL)
    primary_identity = identity(PRIMARY)
    independent_identity = identity(Path(__file__))
    compare_identity(primary.get("protocol"), protocol_identity, "primary.protocol")
    sources = require_mapping(primary.get("sources"), "primary.sources")
    compare_identity(sources.get("primary"), primary_identity, "primary.sources.primary")
    compare_identity(sources.get("independent"), independent_identity, "primary.sources.independent")
    artifacts = require_mapping(primary.get("artifacts"), "primary.artifacts")
    compare_identity(artifacts.get("quadrature_rows"), identity(raw_path), "primary.artifacts.quadrature_rows")
    check("source_hashes", True)

    expected_constants = {
        "radius": RADIUS,
        "scales": list(SCALES),
        "control_tau": CONTROL_TAU,
        "control_step": CONTROL_STEP,
        "control_points": [list(point) for point in CONTROL_POINTS],
        "singular_values": [list(values) for values in SINGULAR_VALUES],
        "degenerate_values": list(DEGENERATE_VALUES),
    }
    check("constants_exact", primary.get("constants") == expected_constants, primary.get("constants"))
    check("raw_schema", raw.get("schema") == RAW_SCHEMA, raw.get("schema"))
    check("raw_constants_exact", raw.get("constants") == expected_constants)
    primary_measurements = require_mapping(primary.get("measurements"), "primary.measurements")
    raw_measurements = require_mapping(raw.get("measurements"), "raw.measurements")
    check("raw_matches_primary", raw_measurements == primary_measurements)

    primary_metric = require_list(primary_measurements.get("metric_controls"), "primary.metric_controls", 3)
    independent_metric = require_list(reconstructed.get("metric_controls"), "reconstruction.metric_controls", 3)
    for index, (recorded, independent) in enumerate(zip(primary_metric, independent_metric, strict=True)):
        recorded_row = require_mapping(recorded, f"primary.metric_controls[{index}]")
        check(f"metric_{index}_point", recorded_row.get("point") == independent["point"])
        check(
            f"metric_{index}_closed",
            bool(np.allclose(np.asarray(recorded_row.get("closed_metric"), dtype=np.float64), np.asarray(independent["closed_metric"], dtype=np.float64), rtol=0.0, atol=2.0e-13)),
        )
        check(
            f"metric_{index}_finite_difference",
            bool(np.allclose(np.asarray(recorded_row.get("finite_difference_metric"), dtype=np.float64), np.asarray(independent["projection_metric"], dtype=np.float64), rtol=0.0, atol=2.0e-9)),
        )
        check(f"metric_{index}_density", close(recorded_row.get("radial_density"), independent["radial_density"], rel=2.0e-12, absolute=2.0e-13))

    for family, scale_key in (("temporal_rows", "tau_abs"), ("puncture_rows", "inner_radius"), ("cutoff_rows", "cutoff")):
        recorded_rows = require_list(primary_measurements.get(family), f"primary.{family}", 7)
        independent_rows = require_list(reconstructed.get(family), f"reconstruction.{family}", 7)
        for index, (recorded, independent) in enumerate(zip(recorded_rows, independent_rows, strict=True)):
            recorded_row = require_mapping(recorded, f"primary.{family}[{index}]")
            check(f"{family}_{index}_scale", recorded_row.get(scale_key) == independent[scale_key])
            for key in ("numerical", "exact", "relative_error", "corrected_coefficient", "coefficient_error"):
                check(f"{family}_{index}_{key}", close(recorded_row.get(key), independent[key], rel=5.0e-10, absolute=5.0e-11))
        slope_key = family.replace("_rows", "_slope_last_four")
        check(slope_key, close(primary_measurements.get(slope_key), reconstructed[slope_key], rel=0.0, absolute=2.0e-10))

    primary_angular = require_list(primary_measurements.get("anisotropy_rows"), "primary.anisotropy_rows", 3)
    independent_angular = require_list(reconstructed.get("anisotropy_rows"), "reconstruction.anisotropy_rows", 3)
    for index, (recorded, independent) in enumerate(zip(primary_angular, independent_angular, strict=True)):
        recorded_row = require_mapping(recorded, f"primary.anisotropy_rows[{index}]")
        check(f"anisotropy_{index}_values", recorded_row.get("singular_values") == independent["singular_values"])
        check(f"anisotropy_{index}_rank", recorded_row.get("rank") == independent["rank"])
        check(f"anisotropy_{index}_coefficient", close(recorded_row.get("coefficient"), independent["coefficient"], rel=2.0e-9, absolute=2.0e-8))
        check(f"anisotropy_{index}_sphere_area", close(recorded_row.get("sphere_area"), independent["sphere_area"], rel=0.0, absolute=2.0e-10))

    primary_degenerate = require_mapping(primary_measurements.get("degenerate_control"), "primary.degenerate_control")
    independent_degenerate = require_mapping(reconstructed.get("degenerate_control"), "reconstruction.degenerate_control")
    check("degenerate_values", primary_degenerate.get("singular_values") == independent_degenerate["singular_values"])
    check("degenerate_rank", primary_degenerate.get("rank") == independent_degenerate["rank"] == 2)
    check("degenerate_jacobian_floor", primary_degenerate.get("jacobian_min") == independent_degenerate["jacobian_min"] == 0.0)
    check("two_derivative_energy", close(primary_measurements.get("two_derivative_energy_ball"), reconstructed["two_derivative_energy_ball"], rel=0.0, absolute=1.0e-12))

    primary_verdicts = require_mapping(primary.get("verdicts"), "primary.verdicts")
    check("verdict_keys", set(primary_verdicts) == set(VERDICT_KEYS), sorted(primary_verdicts))
    for key in VERDICT_KEYS:
        check(f"verdict_{key}", primary_verdicts.get(key) == verdicts[key], {"recorded": primary_verdicts.get(key), "reconstructed": verdicts[key]})
    check("primary_receipt_identity", identity(input_path)["bytes"] > 0)
    return checks


def run(input_path: Path, output_path: Path) -> int:
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite {output_path}")
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "completed": False,
        "scientific_execution_started": True,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform()},
        "sources": {},
        "reconstruction": {},
        "checks": [],
        "mismatches": [],
        "gates": {},
        "verdicts": {key: ("FAIL" if key == "QZO6" else "INCONCLUSIVE") for key in VERDICT_KEYS},
        "exact_agreement": False,
        "complete_physical_matter_formation": False,
        "failure": None,
    }
    exit_code = 1
    try:
        require_frozen_protocol(PROTOCOL)
        primary = strict_json(input_path)
        artifacts = require_mapping(primary.get("artifacts"), "primary.artifacts")
        raw_descriptor = require_mapping(artifacts.get("quadrature_rows"), "primary.artifacts.quadrature_rows")
        raw_name = raw_descriptor.get("path")
        if not isinstance(raw_name, str) or not raw_name:
            raise EvidenceFailure("primary raw artifact path is missing")
        raw_path = (ROOT / raw_name).resolve()
        try:
            raw_path.relative_to(ROOT.resolve())
        except ValueError as error:
            raise EvidenceFailure("primary raw artifact lies outside the repository") from error
        raw = strict_json(raw_path)

        receipt["sources"] = {
            "protocol": identity(PROTOCOL),
            "primary_source": identity(PRIMARY),
            "independent_source": identity(Path(__file__)),
            "primary_receipt": identity(input_path),
            "raw_rows": identity(raw_path),
        }
        reconstructed = reconstruct()
        receipt["reconstruction"] = reconstructed
        receipt["gates"], receipt["verdicts"] = classify(reconstructed)
        receipt["checks"] = compare_primary(primary, raw, reconstructed, receipt["verdicts"], input_path, raw_path)
        receipt["mismatches"] = [row["name"] for row in receipt["checks"] if not row["passed"]]
        receipt["exact_agreement"] = not receipt["mismatches"]
        receipt["completed"] = True
        exit_code = 0 if receipt["exact_agreement"] and receipt["verdicts"]["QZO5"] == "CONTRADICTS" else 1
    except Exception as error:
        receipt["failure"] = {"type": type(error).__name__, "message": str(error)}
    strict_write(output_path, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False))
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(args.input, args.output)


if __name__ == "__main__":
    sys.exit(main())
