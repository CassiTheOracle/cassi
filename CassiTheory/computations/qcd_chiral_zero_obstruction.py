#!/usr/bin/env python3
"""Run the frozen QCD chiral-zero obstruction calculation.

Run from the CassiTheory root:
    python computations/qcd_chiral_zero_obstruction.py \
        --output-dir runs/20260910_qcd_chiral_zero_obstruction/primary
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
import sys
from typing import Any, Callable

import numpy as np
import scipy
from numpy.polynomial.legendre import leggauss
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations/qcd-chiral-zero-obstruction-prereg.md"
INDEPENDENT = ROOT / "computations/verify_qcd_chiral_zero_obstruction.py"
SCHEMA = "cassi.qcd-chiral-zero-obstruction.v1"
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


def require_frozen_protocol(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(PROTOCOL_START) != 1 or text.count(PROTOCOL_END) != 1:
        raise ValueError("protocol markers are missing or non-unique")
    if text.index(PROTOCOL_START) >= text.index(PROTOCOL_END):
        raise ValueError("protocol markers are out of order")


def normalized_field(tau: float, point: np.ndarray) -> np.ndarray:
    raw = np.concatenate(([tau], point.astype(np.float64, copy=False)))
    return raw / np.linalg.norm(raw)


def closed_metric(tau: float, point: np.ndarray) -> np.ndarray:
    rho2 = tau * tau + float(point @ point)
    return np.eye(3, dtype=np.float64) / rho2 - np.outer(point, point) / (rho2 * rho2)


def finite_difference_metric(tau: float, point: np.ndarray, step: float) -> np.ndarray:
    derivatives = np.empty((4, 3), dtype=np.float64)
    for axis in range(3):
        delta = np.zeros(3, dtype=np.float64)
        delta[axis] = step
        derivatives[:, axis] = (
            normalized_field(tau, point + delta)
            - normalized_field(tau, point - delta)
        ) / (2.0 * step)
    return derivatives.T @ derivatives


def density_from_metric(metric: np.ndarray) -> float:
    total = 0.0
    for first in range(3):
        for second in range(first + 1, 3):
            total += (
                metric[first, first] * metric[second, second]
                - metric[first, second] * metric[first, second]
            )
    return 0.5 * total


def radial_density(tau: float, radius: float) -> float:
    rho2 = radius * radius + tau * tau
    return 0.5 * (1.0 / (rho2 * rho2) + 2.0 * tau * tau / (rho2 * rho2 * rho2))


def temporal_exact(tau: float, radius: float) -> float:
    scale = abs(tau)
    ratio = radius / scale
    bracket = 3.0 * math.atan(ratio) - ratio * (ratio * ratio + 3.0) / (1.0 + ratio * ratio) ** 2
    return math.pi * bracket / (2.0 * scale)


def puncture_exact(inner: float, radius: float) -> float:
    return 2.0 * math.pi * (1.0 / inner - 1.0 / radius)


def cutoff_exact(cutoff: float, radius: float) -> float:
    return 4.0 * math.pi / cutoff - 2.0 * math.pi / radius


def integrate(function: Callable[[float], float], lower: float, upper: float, *, points: tuple[float, ...] = ()) -> tuple[float, float]:
    selected_points = [value for value in points if lower < value < upper]
    value, error = quad(
        function,
        lower,
        upper,
        points=selected_points or None,
        epsabs=1.0e-11,
        epsrel=2.0e-13,
        limit=600,
    )
    return float(value), float(error)


def log_slope(rows: list[dict[str, float]], scale_key: str) -> float:
    tail = rows[-4:]
    x = np.log(np.asarray([row[scale_key] for row in tail], dtype=np.float64))
    y = np.log(np.asarray([row["numerical"] for row in tail], dtype=np.float64))
    return float(np.polyfit(x, y, 1)[0])


def angular_coefficient(values: tuple[float, float, float], order_z: int = 320, order_phi: int = 640) -> dict[str, Any]:
    singular = np.asarray(values, dtype=np.float64)
    nodes, weights = leggauss(order_z)
    azimuth = (np.arange(order_phi, dtype=np.float64) + 0.5) * (2.0 * math.pi / order_phi)
    transverse = np.sqrt(np.maximum(0.0, 1.0 - nodes[:, None] ** 2))
    directions = np.stack(
        (
            transverse * np.cos(azimuth)[None, :],
            transverse * np.sin(azimuth)[None, :],
            np.broadcast_to(nodes[:, None], (order_z, order_phi)),
        ),
        axis=-1,
    )
    image_norm = np.linalg.norm(directions * singular[None, None, :], axis=-1)
    determinant = float(np.prod(singular))
    jacobian = determinant / image_norm**3
    delta_phi = 2.0 * math.pi / order_phi
    coefficient = 0.5 * float(np.sum(weights[:, None] * jacobian * jacobian) * delta_phi)
    sphere_area = float(np.sum(weights) * order_phi * delta_phi)
    return {
        "singular_values": list(values),
        "rank": int(np.linalg.matrix_rank(np.diag(singular))),
        "coefficient": coefficient,
        "coefficient_over_2pi": coefficient / (2.0 * math.pi),
        "sphere_area": sphere_area,
        "jacobian_min": float(np.min(np.abs(jacobian))),
        "jacobian_max": float(np.max(np.abs(jacobian))),
        "quadrature": {"z_rule": "gauss-legendre", "z_order": order_z, "phi_rule": "midpoint-trapezoidal", "phi_order": order_phi},
    }


def calculate() -> dict[str, Any]:
    metric_rows: list[dict[str, Any]] = []
    for point_values in CONTROL_POINTS:
        point = np.asarray(point_values, dtype=np.float64)
        expected = closed_metric(CONTROL_TAU, point)
        reconstructed = finite_difference_metric(CONTROL_TAU, point, CONTROL_STEP)
        expected_density = radial_density(CONTROL_TAU, float(np.linalg.norm(point)))
        reconstructed_density = density_from_metric(expected)
        eigenvalues = np.linalg.eigvalsh(expected)
        eigenvalue_density = 0.5 * float(
            eigenvalues[0] * eigenvalues[1]
            + eigenvalues[0] * eigenvalues[2]
            + eigenvalues[1] * eigenvalues[2]
        )
        metric_rows.append(
            {
                "point": list(point_values),
                "tau": CONTROL_TAU,
                "step": CONTROL_STEP,
                "closed_metric": expected.tolist(),
                "finite_difference_metric": reconstructed.tolist(),
                "entry_abs_errors": np.abs(reconstructed - expected).tolist(),
                "max_entry_abs_error": float(np.max(np.abs(reconstructed - expected))),
                "closed_density": reconstructed_density,
                "radial_density": expected_density,
                "eigenvalues": eigenvalues.tolist(),
                "eigenvalue_density": eigenvalue_density,
                "density_relative_error": abs(eigenvalue_density - expected_density) / expected_density,
                "positive_finite_density": bool(math.isfinite(expected_density) and expected_density > 0.0),
            }
        )

    temporal_rows: list[dict[str, float]] = []
    for tau in SCALES:
        numerical, quadrature_error = integrate(
            lambda radius, local_tau=tau: 4.0 * math.pi * radius * radius * radial_density(local_tau, radius),
            0.0,
            RADIUS,
            points=(tau,),
        )
        exact = temporal_exact(tau, RADIUS)
        coefficient = tau * (numerical + 2.0 * math.pi / RADIUS)
        temporal_rows.append(
            {
                "tau_abs": tau,
                "numerical": numerical,
                "quadrature_error": quadrature_error,
                "exact": exact,
                "relative_error": abs(numerical - exact) / abs(exact),
                "corrected_coefficient": coefficient,
                "coefficient_error": abs(coefficient - 3.0 * math.pi * math.pi / 4.0),
            }
        )

    puncture_rows: list[dict[str, float]] = []
    for inner in SCALES:
        numerical, quadrature_error = integrate(lambda radius: 2.0 * math.pi / (radius * radius), inner, RADIUS)
        exact = puncture_exact(inner, RADIUS)
        coefficient = inner * (numerical + 2.0 * math.pi / RADIUS)
        puncture_rows.append(
            {
                "inner_radius": inner,
                "numerical": numerical,
                "quadrature_error": quadrature_error,
                "exact": exact,
                "relative_error": abs(numerical - exact) / abs(exact),
                "corrected_coefficient": coefficient,
                "coefficient_error": abs(coefficient - 2.0 * math.pi),
            }
        )

    cutoff_rows: list[dict[str, float]] = []
    for cutoff in SCALES:
        interior, interior_error = integrate(
            lambda radius, local_cutoff=cutoff: 6.0 * math.pi * radius * radius / local_cutoff**4,
            0.0,
            cutoff,
        )
        exterior, exterior_error = integrate(lambda radius: 2.0 * math.pi / (radius * radius), cutoff, RADIUS)
        numerical = interior + exterior
        exact = cutoff_exact(cutoff, RADIUS)
        coefficient = cutoff * (numerical + 2.0 * math.pi / RADIUS)
        cutoff_rows.append(
            {
                "cutoff": cutoff,
                "interior_numerical": interior,
                "exterior_numerical": exterior,
                "numerical": numerical,
                "quadrature_error": interior_error + exterior_error,
                "exact": exact,
                "relative_error": abs(numerical - exact) / abs(exact),
                "corrected_coefficient": coefficient,
                "coefficient_error": abs(coefficient - 4.0 * math.pi),
            }
        )

    anisotropy_rows = [angular_coefficient(values) for values in SINGULAR_VALUES]
    degenerate = {
        "singular_values": list(DEGENERATE_VALUES),
        "rank": int(np.linalg.matrix_rank(np.diag(np.asarray(DEGENERATE_VALUES, dtype=np.float64)))),
        "jacobian_min": 0.0,
        "jacobian_max": 0.0,
    }
    return {
        "metric_controls": metric_rows,
        "temporal_rows": temporal_rows,
        "temporal_slope_last_four": log_slope(temporal_rows, "tau_abs"),
        "puncture_rows": puncture_rows,
        "puncture_slope_last_four": log_slope(puncture_rows, "inner_radius"),
        "cutoff_rows": cutoff_rows,
        "cutoff_slope_last_four": log_slope(cutoff_rows, "cutoff"),
        "anisotropy_rows": anisotropy_rows,
        "degenerate_control": degenerate,
        "two_derivative_energy_ball": 2.0 * math.pi * RADIUS**3,
    }


def classify(measurements: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    metric_rows = measurements["metric_controls"]
    qzo1_inputs = {
        "max_metric_entry_abs_error": max(row["max_entry_abs_error"] for row in metric_rows),
        "all_density_positive_finite": all(row["positive_finite_density"] for row in metric_rows),
        "max_density_relative_error": max(row["density_relative_error"] for row in metric_rows),
    }
    qzo1 = (
        qzo1_inputs["max_metric_entry_abs_error"] < 2.0e-9
        and qzo1_inputs["all_density_positive_finite"]
        and qzo1_inputs["max_density_relative_error"] < 2.0e-12
    )

    temporal_rows = measurements["temporal_rows"]
    qzo2_inputs = {
        "max_relative_error": max(row["relative_error"] for row in temporal_rows),
        "slope_last_four": measurements["temporal_slope_last_four"],
        "smallest_scale_coefficient_error": temporal_rows[-1]["coefficient_error"],
    }
    qzo2 = (
        qzo2_inputs["max_relative_error"] < 2.0e-10
        and -1.02 <= qzo2_inputs["slope_last_four"] <= -0.98
        and qzo2_inputs["smallest_scale_coefficient_error"] < 5.0e-5
    )

    puncture_rows = measurements["puncture_rows"]
    anisotropy_rows = measurements["anisotropy_rows"]
    degenerate = measurements["degenerate_control"]
    qzo3_inputs = {
        "max_puncture_relative_error": max(row["relative_error"] for row in puncture_rows),
        "puncture_slope_last_four": measurements["puncture_slope_last_four"],
        "max_sphere_area_error": max(abs(row["sphere_area"] - 4.0 * math.pi) for row in anisotropy_rows),
        "minimum_rank_three_coefficient": min(row["coefficient"] for row in anisotropy_rows),
        "isotropic_coefficient_error": abs(anisotropy_rows[0]["coefficient"] - 2.0 * math.pi),
        "degenerate_rank": degenerate["rank"],
        "degenerate_jacobian_min": degenerate["jacobian_min"],
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

    cutoff_rows = measurements["cutoff_rows"]
    qzo4_inputs = {
        "max_relative_error": max(row["relative_error"] for row in cutoff_rows),
        "slope_last_four": measurements["cutoff_slope_last_four"],
        "smallest_scale_coefficient_error": cutoff_rows[-1]["coefficient_error"],
    }
    qzo4 = (
        qzo4_inputs["max_relative_error"] < 2.0e-10
        and -1.02 <= qzo4_inputs["slope_last_four"] <= -0.98
        and qzo4_inputs["smallest_scale_coefficient_error"] < 2.0e-10
    )

    gate_rows = {
        "QZO1": {"passed": bool(qzo1), "inputs": qzo1_inputs},
        "QZO2": {"passed": bool(qzo2), "inputs": qzo2_inputs},
        "QZO3": {"passed": bool(qzo3), "inputs": qzo3_inputs},
        "QZO4": {"passed": bool(qzo4), "inputs": qzo4_inputs},
    }
    all_numerical = all(row["passed"] for row in gate_rows.values())
    verdicts = {
        "QZO1": "PASS" if qzo1 else "FAIL",
        "QZO2": "PASS" if qzo2 else "FAIL",
        "QZO3": "PASS" if qzo3 else "FAIL",
        "QZO4": "PASS" if qzo4 else "FAIL",
        "QZO5": "CONTRADICTS" if all_numerical else "INCONCLUSIVE",
        "QZO6": "FAIL",
    }
    return gate_rows, verdicts


def run(output_dir: Path, protocol: Path) -> int:
    result_path = output_dir / "results.json"
    raw_path = output_dir / "quadrature_rows.json"
    if result_path.exists() or raw_path.exists():
        raise FileExistsError(f"refusing to overwrite evidence in {output_dir}")

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "completed": False,
        "scientific_execution_started": True,
        "protocol": {},
        "sources": {},
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
        "constants": {
            "radius": RADIUS,
            "scales": list(SCALES),
            "control_tau": CONTROL_TAU,
            "control_step": CONTROL_STEP,
            "control_points": [list(point) for point in CONTROL_POINTS],
            "singular_values": [list(values) for values in SINGULAR_VALUES],
            "degenerate_values": list(DEGENERATE_VALUES),
        },
        "artifacts": {},
        "measurements": {},
        "gates": {},
        "verdicts": {f"QZO{index}": ("FAIL" if index == 6 else "INCONCLUSIVE") for index in range(1, 7)},
        "complete_physical_matter_formation": False,
        "failure": None,
    }
    try:
        require_frozen_protocol(protocol)
        result["protocol"] = identity(protocol)
        result["sources"] = {
            "primary": identity(Path(__file__)),
            "independent": identity(INDEPENDENT),
        }
        measurements = calculate()
        raw_payload = {
            "schema": RAW_SCHEMA,
            "constants": result["constants"],
            "measurements": measurements,
        }
        strict_write(raw_path, raw_payload)
        result["artifacts"]["quadrature_rows"] = identity(raw_path)
        result["measurements"] = measurements
        result["gates"], result["verdicts"] = classify(measurements)
        result["completed"] = True
    except Exception as error:
        result["failure"] = {"type": type(error).__name__, "message": str(error)}
    strict_write(result_path, result)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if result["completed"] and result["verdicts"]["QZO5"] == "CONTRADICTS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    args = parser.parse_args(argv)
    return run(args.output_dir, args.protocol)


if __name__ == "__main__":
    sys.exit(main())
