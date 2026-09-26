#!/usr/bin/env python3
"""Independently verify the regular polynomial chiral-stabilizer receipt.

Run from the CassiTheory repository root after the primary program:
    python computations/verify_qcd_polynomial_stabilizer.py
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "qcd-polynomial-stabilizer-prereg.md"
PRIMARY_SOURCE = ROOT / "computations" / "qcd_polynomial_stabilizer.py"
PRIMARY_DIR = ROOT / "runs" / "20260910_qcd_polynomial_stabilizer" / "primary_recovery1"
PRIMARY_RESULTS = PRIMARY_DIR / "results.json"
OUT_DIR = ROOT / "runs" / "20260910_qcd_polynomial_stabilizer" / "verification_recovery1"
RESULTS = OUT_DIR / "verification.json"

F_PI = 93.0
M_PI = 138.0
M_SIGMA = 600.0
E_COUPLING = 4.25
X_MAX = 18.0
SEED = 20260910
GRID_INTERVALS = (256, 512, 1024)
RADII = (0.37, 0.91, 1.73, 3.20)
DIRECTIONS = ((1.0, 2.0, 3.0), (-2.0, 1.0, 4.0), (3.0, -4.0, 2.0))
CARTESIAN_STEP = 1.0e-6

LAMBDA = (M_SIGMA**2 - M_PI**2) / (2.0 * F_PI**2)
MU2 = (M_PI / F_PI) ** 2
VBAR2 = 1.0 - MU2 / LAMBDA
ALPHA = LAMBDA / (4.0 * E_COUPLING**2)
BETA = MU2 / E_COUPLING**2


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_error(a: float, b: float, floor: float = 1.0e-14) -> float:
    return abs(a - b) / max(abs(a), abs(b), floor)


def load_fields(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, Path]:
    path = PRIMARY_DIR / f"fields_N{n}.npz"
    with np.load(path) as data:
        x = np.asarray(data["x"], dtype=np.float64)
        s = np.asarray(data["s"], dtype=np.float64)
        f = np.asarray(data["f"], dtype=np.float64)
    return x, s, f, path


def radial_energy_independent(x: np.ndarray, s: np.ndarray, f: np.ndarray) -> dict[str, float]:
    dx_values = np.diff(x)
    if not np.allclose(dx_values, dx_values[0], rtol=0.0, atol=1.0e-15):
        raise ValueError("independent verifier requires the frozen uniform grid")
    dx = float(dx_values[0])
    radius = 0.5 * (x[:-1] + x[1:])
    sm = 0.5 * (s[:-1] + s[1:])
    fm = 0.5 * (f[:-1] + f[1:])
    ds = np.diff(s) / dx
    df = np.diff(f) / dx
    angular = np.sin(fm) ** 2
    radial_norm = ds**2 + sm**2 * df**2

    term_two = 0.5 * radius**2 * radial_norm + sm**2 * angular
    term_four = sm**2 * angular * radial_norm + sm**4 * angular**2 / (2.0 * radius**2)
    term_zero = radius**2 * (
        ALPHA * ((sm**2 - VBAR2) ** 2 - (1.0 - VBAR2) ** 2)
        + BETA * (1.0 - sm * np.cos(fm))
    )
    two = float(dx * np.add.reduce(term_two))
    four = float(dx * np.add.reduce(term_four))
    zero = float(dx * np.add.reduce(term_zero))
    return {
        "two_derivative": two,
        "quartic": four,
        "potential": zero,
        "total_dimensionless": two + four + zero,
    }


def profile_value(point: np.ndarray, x: np.ndarray, s: np.ndarray, f: np.ndarray) -> np.ndarray:
    radius = float(np.linalg.norm(point))
    if radius == 0.0:
        return np.array((0.0, 0.0, 0.0, -s[0]), dtype=np.float64)
    sval = float(np.interp(radius, x, s))
    fval = float(np.interp(radius, x, f))
    pion = sval * math.sin(fval) * point / radius
    return np.concatenate((pion, np.array([sval * math.cos(fval)])))


def profile_value_and_slopes(
    radius: float, x: np.ndarray, s: np.ndarray, f: np.ndarray
) -> tuple[float, float, float, float]:
    index = int(np.searchsorted(x, radius, side="right") - 1)
    index = max(0, min(index, len(x) - 2))
    width = float(x[index + 1] - x[index])
    fraction = (radius - float(x[index])) / width
    sval = float((1.0 - fraction) * s[index] + fraction * s[index + 1])
    fval = float((1.0 - fraction) * f[index] + fraction * f[index + 1])
    ds = float((s[index + 1] - s[index]) / width)
    df = float((f[index + 1] - f[index]) / width)
    return sval, fval, ds, df


def density_from_derivatives(field: np.ndarray, derivatives: np.ndarray) -> dict[str, float]:
    gram = derivatives @ derivatives.T
    trace = float(np.trace(gram))
    two = 0.5 * trace
    four = 0.25 * (trace**2 - float(np.sum(gram * gram)))
    amplitude_square = float(field @ field)
    potential = (
        ALPHA * ((amplitude_square - VBAR2) ** 2 - (1.0 - VBAR2) ** 2)
        + BETA * (1.0 - float(field[3]))
    )
    return {"two_derivative": two, "quartic": four, "potential": potential}


def radial_density(radius: float, s: float, f: float, ds: float, df: float) -> dict[str, float]:
    angular = math.sin(f) ** 2
    radial_norm = ds**2 + s**2 * df**2
    return {
        "two_derivative": 0.5 * radial_norm + s**2 * angular / radius**2,
        "quartic": (
            s**2 * angular * radial_norm / radius**2
            + s**4 * angular**2 / (2.0 * radius**4)
        ),
        "potential": (
            ALPHA * ((s**2 - VBAR2) ** 2 - (1.0 - VBAR2) ** 2)
            + BETA * (1.0 - s * math.cos(f))
        ),
    }


def cartesian_controls(x: np.ndarray, s: np.ndarray, f: np.ndarray) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for radius in RADII:
        sval, fval, ds, df = profile_value_and_slopes(radius, x, s, f)
        expected = radial_density(radius, sval, fval, ds, df)
        for direction_values in DIRECTIONS:
            direction = np.asarray(direction_values, dtype=np.float64)
            direction /= np.linalg.norm(direction)
            point = radius * direction
            field = profile_value(point, x, s, f)
            derivatives = np.empty((3, 4), dtype=np.float64)
            for axis in range(3):
                shift = np.zeros(3, dtype=np.float64)
                shift[axis] = CARTESIAN_STEP
                derivatives[axis] = (
                    profile_value(point + shift, x, s, f)
                    - profile_value(point - shift, x, s, f)
                ) / (2.0 * CARTESIAN_STEP)
            measured = density_from_derivatives(field, derivatives)
            errors = {
                name: relative_error(measured[name], expected[name])
                for name in expected
            }
            rows.append(
                {
                    "radius": radius,
                    "direction": direction_values,
                    "expected": expected,
                    "cartesian": measured,
                    "relative_errors": errors,
                    "max_relative_error": max(errors.values()),
                }
            )
    return rows


def gram_controls() -> dict[str, Any]:
    rng = np.random.default_rng(SEED)
    random_values: list[float] = []
    for _ in range(512):
        derivatives = rng.normal(size=(3, 4))
        gram = derivatives @ derivatives.T
        trace = float(np.trace(gram))
        random_values.append(0.25 * (trace**2 - float(np.sum(gram * gram))))

    rank_one_values: list[float] = []
    for _ in range(32):
        left = rng.normal(size=3)
        right = rng.normal(size=4)
        derivatives = np.outer(left, right)
        gram = derivatives @ derivatives.T
        trace = float(np.trace(gram))
        rank_one_values.append(0.25 * (trace**2 - float(np.sum(gram * gram))))

    zero_derivative = np.zeros((3, 4), dtype=np.float64)
    zero_field = np.zeros(4, dtype=np.float64)
    zero_density = density_from_derivatives(zero_field, zero_derivative)
    finite_derivative = rng.normal(size=(3, 4))
    finite_zero_density = density_from_derivatives(zero_field, finite_derivative)
    return {
        "random_count": len(random_values),
        "random_min_quartic": float(min(random_values)),
        "random_max_quartic": float(max(random_values)),
        "rank_one_count": len(rank_one_values),
        "rank_one_max_abs_quartic": float(max(abs(value) for value in rank_one_values)),
        "zero_field_zero_derivative": zero_density,
        "zero_field_finite_derivative": finite_zero_density,
        "all_chiral_zero_values_finite": bool(
            all(np.isfinite(value) for value in zero_density.values())
            and all(np.isfinite(value) for value in finite_zero_density.values())
        ),
    }


def homotopy_independent(s: np.ndarray, f: np.ndarray) -> list[dict[str, float | bool]]:
    n = len(s) - 1
    dx = X_MAX / n
    radius = (np.arange(n, dtype=np.float64) + 0.5) * dx
    pion_start = s * np.sin(f)
    sigma_start = s * np.cos(f)
    rows: list[dict[str, float | bool]] = []
    for index in range(401):
        u = index * 0.0025
        pion = (1.0 - u) * pion_start
        sigma = (1.0 - u) * sigma_start + u
        pm = 0.5 * (pion[:-1] + pion[1:])
        qm = 0.5 * (sigma[:-1] + sigma[1:])
        dp = np.diff(pion) / dx
        dq = np.diff(sigma) / dx
        radial_norm = dp**2 + dq**2
        amplitude_square = pm**2 + qm**2
        integrand = (
            0.5 * radius**2 * radial_norm
            + pm**2
            + pm**2 * radial_norm
            + pm**4 / (2.0 * radius**2)
            + radius**2
            * (
                ALPHA
                * ((amplitude_square - VBAR2) ** 2 - (1.0 - VBAR2) ** 2)
                + BETA * (1.0 - qm)
            )
        )
        total = float(dx * np.add.reduce(integrand))
        rows.append({"u": u, "energy_dimensionless": total, "finite": bool(np.isfinite(total))})
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    primary = json.loads(PRIMARY_RESULTS.read_text(encoding="utf-8"))

    dimensions = {
        "fermion_or_scalar_kinetic": 4,
        "polynomial_quartic_derivative": 4,
        "quartic_chiral_potential": 4,
        "explicit_chiral_breaking": 4,
    }
    amplitude_powers = {
        "two_derivative": (0, 2),
        "polynomial_quartic_derivative": (0, 2, 4),
        "potential": (0, 1, 2, 4),
    }
    gram = gram_controls()
    rps1_pass = bool(
        all(value == 4 for value in dimensions.values())
        and all(min(values) >= 0 for values in amplitude_powers.values())
        and gram["all_chiral_zero_values_finite"]
        and gram["random_min_quartic"] >= -1.0e-13
        and gram["rank_one_max_abs_quartic"] < 1.0e-13
    )

    energy_checks: dict[str, Any] = {}
    loaded: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, Path]] = {}
    for n in GRID_INTERVALS:
        x, s, f, path = load_fields(n)
        loaded[n] = (x, s, f, path)
        independent = radial_energy_independent(x, s, f)
        reported = primary["grids"][str(n)]["energy"]
        errors = {
            key: relative_error(independent[key], float(reported[key]))
            for key in independent
        }
        energy_checks[str(n)] = {
            "independent": independent,
            "reported": {key: float(reported[key]) for key in independent},
            "relative_errors": errors,
            "max_relative_error": max(errors.values()),
            "fields_sha256": sha256(path),
            "reported_fields_sha256": primary["grids"][str(n)]["fields_sha256"],
        }

    x1024, s1024, f1024, _ = loaded[1024]
    cartesian = cartesian_controls(x1024, s1024, f1024)
    max_cartesian_error = max(row["max_relative_error"] for row in cartesian)
    max_energy_error = max(row["max_relative_error"] for row in energy_checks.values())
    hashes_match = all(
        row["fields_sha256"] == row["reported_fields_sha256"]
        for row in energy_checks.values()
    )
    rps2_pass = bool(
        max_cartesian_error < 2.0e-6
        and max_energy_error < 2.0e-11
        and hashes_match
    )

    independent_path = homotopy_independent(s1024, f1024)
    primary_path_file = ROOT / primary["homotopy"]["1024"]["rows_file"]
    primary_path = json.loads(primary_path_file.read_text(encoding="utf-8"))
    path_errors = [
        relative_error(
            float(independent_row["energy_dimensionless"]),
            float(primary_row["energy_dimensionless"]),
        )
        for independent_row, primary_row in zip(independent_path, primary_path, strict=True)
    ]
    max_path_error = max(path_errors)
    primary_rps5 = primary["primary_gate_inputs"]["RPS5_without_independent_agreement"]
    rps5_pass = bool(
        primary_rps5 == "PASS"
        and all(bool(row["finite"]) for row in independent_path)
        and max_path_error < 2.0e-10
        and sha256(primary_path_file) == primary["homotopy"]["1024"]["rows_sha256"]
    )

    rps3 = primary["final_verdicts"]["RPS3"]
    rps4 = primary["final_verdicts"]["RPS4"]
    verdicts = {
        "RPS1": "PASS" if rps1_pass else "FAIL",
        "RPS2": "PASS" if rps2_pass else "FAIL",
        "RPS3": rps3,
        "RPS4": rps4,
        "RPS5": "PASS" if rps5_pass else "FAIL",
    }
    verdicts["RPS6"] = (
        "ADOPT" if all(value == "PASS" for value in verdicts.values()) else "REJECT"
    )
    verdicts["physical_completion"] = "FAIL"

    receipt: dict[str, Any] = {
        "protocol": "qcd-polynomial-stabilizer",
        "dimensions": dimensions,
        "amplitude_powers": amplitude_powers,
        "gram_controls": gram,
        "cartesian_controls": cartesian,
        "max_cartesian_relative_error": max_cartesian_error,
        "energy_checks": energy_checks,
        "max_radial_energy_relative_error": max_energy_error,
        "field_hashes_match": hashes_match,
        "homotopy": {
            "row_count": len(independent_path),
            "all_finite": all(bool(row["finite"]) for row in independent_path),
            "max_energy_relative_error": max_path_error,
            "primary_rows_sha256": sha256(primary_path_file),
            "reported_primary_rows_sha256": primary["homotopy"]["1024"]["rows_sha256"],
        },
        "verdicts": verdicts,
        "complete_physical_matter_formation": False,
        "hashes": {
            "protocol_sha256": sha256(PROTOCOL),
            "reported_protocol_sha256": primary["hashes"]["protocol_sha256"],
            "primary_source_sha256": sha256(PRIMARY_SOURCE),
            "reported_primary_source_sha256": primary["hashes"]["primary_source_sha256"],
            "verification_source_sha256": sha256(Path(__file__).resolve()),
            "primary_results_sha256": sha256(PRIMARY_RESULTS),
        },
    }
    RESULTS.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verdicts, indent=2))
    print(f"max Cartesian density relative error: {max_cartesian_error:.3e}")
    print(f"max radial energy relative error: {max_energy_error:.3e}")
    print(f"max homotopy energy relative error: {max_path_error:.3e}")
    print(f"wrote {RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
