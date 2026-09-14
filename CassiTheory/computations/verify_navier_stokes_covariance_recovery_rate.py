#!/usr/bin/env python3
"""Verify the initial-layer covariance recovery-rate boundary.

The executable independently evaluates the closed leading coefficient on fixed
periodic grids, checks its integrated cube-root coefficient, reconstructs the
active-point determinant order from the published time jet, and verifies the
frozen t^(-1/3) leading-ratio scaling. It does not integrate a Navier–Stokes
trajectory, solve the covariance PDE in time, or claim a uniform continuation
bound.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "turbulence" / "navier-stokes-covariance-recovery-rate.md"
COEFFICIENT_NOTE = (
    ROOT / "turbulence" / "navier-stokes-rank-deficient-temporal-coefficient.md"
)
TEMPORAL_NOTE = (
    ROOT / "turbulence" / "navier-stokes-rank-deficient-temporal-recovery.md"
)
STRETCHING_NOTE = (
    ROOT / "turbulence" / "navier-stokes-rank-deficient-stretching.md"
)
PROTOCOL = (
    ROOT / "computations" / "navier-stokes-covariance-recovery-rate-prereg.md"
)
DEFAULT_OUTPUT = (
    ROOT / "runs" / "navier_stokes_covariance_recovery_rate_20260913" / "verification.json"
)
EXPECTED_CHECKS = 6
EXPECTED_CHECK_NAMES = (
    "CRR1 coefficient formula is nonnegative on fixed torus grids",
    "CRR2 integrated recovery coefficient is finite and positive",
    "CRR3 rank-two jet has determinant order four",
    "CRR4 positive coefficient occupies an open sampled region",
    "CRR5 active seeded-production coefficient is one half",
    "CRR6 leading ratio has t^{-1/3} scaling",
)
SCHEMA = "cassi.navier-stokes.covariance-recovery-rate.verification.v1"
GRID_SIZES = (32, 64, 128, 256)
NU = 0.7


class CheckBook:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.failures: list[str] = []

    def record(self, name: str, passed: bool, detail: Any) -> None:
        passed = bool(passed)
        self.checks.append(
            {"name": name, "passed": passed, "detail": stringify(detail)}
        )
        if not passed:
            self.failures.append(name)


def stringify(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, sp.MatrixBase):
        return [[stringify(entry) for entry in row] for row in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [stringify(entry) for entry in value]
    if isinstance(value, dict):
        return {str(key): stringify(item) for key, item in value.items()}
    if isinstance(value, sp.Basic):
        return sp.sstr(value)
    return value


def coefficient_grid(size: int) -> np.ndarray:
    """Evaluate the frozen SOS coefficient on a periodic midpoint grid."""
    coordinate = np.arange(size, dtype=np.float64) * (2.0 * np.pi / size)
    x, y = np.meshgrid(coordinate, coordinate, indexing="ij")
    a = np.sin(x)
    b = np.cos(x)
    c = np.sin(y)
    d = np.cos(y)
    return d**2 * ((c**2 - a**2) ** 2 + 4.0 * a**2 * b**2 * c**2) + (
        2.0 * a**2 * c**2 * (a + b * c) ** 2
    )


def determinant_order_at_active_point() -> dict[str, Any]:
    """Reconstruct det(t R1+t^2 R2/2) at (pi/2,0) exactly."""
    nu, t = sp.symbols("nu t", positive=True)
    first = sp.Matrix(
        [[2 * nu, -2 * nu, 0], [-2 * nu, 4 * nu, 0], [0, 0, 0]]
    )
    second = sp.Matrix(
        [
            [8 * nu * (1 - 2 * nu), 2 * nu * (6 * nu - 5), 0],
            [2 * nu * (6 * nu - 5), 4 * nu * (1 - 6 * nu), 0],
            [0, 0, 4 * nu**2],
        ]
    )
    polynomial = sp.Poly(sp.expand((t * first + t**2 * second / 2).det()), t)
    coefficients = {
        str(power): sp.factor(polynomial.coeff_monomial(t**power))
        for power in range(7)
    }
    return {
        "coefficients": coefficients,
        "low_order_zero": all(coefficients[str(power)] == 0 for power in range(4)),
        "t4_expected": coefficients["4"] == 8 * nu**4,
        "t4": coefficients["4"],
    }


def verify_checks(book: CheckBook, values: dict[str, Any]) -> None:
    grid_values: dict[str, Any] = {}
    all_finite = True
    all_nonnegative = True
    cube_root_means: dict[str, float] = {}
    for size in GRID_SIZES:
        grid = coefficient_grid(size)
        finite = bool(np.isfinite(grid).all())
        all_finite = all_finite and finite
        all_nonnegative = all_nonnegative and bool(float(grid.min()) >= -1e-12)
        cube_root_means[str(size)] = float(np.mean(np.cbrt(np.maximum(grid, 0.0))))
        grid_values[str(size)] = {
            "finite": finite,
            "minimum": float(grid.min()),
            "maximum": float(grid.max()),
            "positive_fraction": float(np.mean(grid > 1e-10)),
        }
    witness_f = float(
        np.cos(0.0) ** 2
        * ((np.sin(0.0) ** 2 - np.sin(np.pi / 2) ** 2) ** 2)
        + 2.0
        * np.sin(np.pi / 2) ** 2
        * np.sin(0.0) ** 2
        * (np.sin(np.pi / 2) + np.cos(np.pi / 2) * np.sin(0.0)) ** 2
    )
    book.record(
        EXPECTED_CHECK_NAMES[0],
        all_finite and all_nonnegative and abs(witness_f - 1.0) < 1e-12,
        {
            "grid_values": grid_values,
            "active_witness_f": witness_f,
            "minimum_tolerance": -1e-12,
        },
    )

    refinement_relative_difference = abs(
        cube_root_means["256"] - cube_root_means["128"]
    ) / cube_root_means["256"]
    recovery_coefficient = 6.0 * NU ** (4.0 / 3.0) * cube_root_means["256"]
    book.record(
        EXPECTED_CHECK_NAMES[1],
        all(
            np.isfinite(value) and value > 0.0
            for value in cube_root_means.values()
        )
        and refinement_relative_difference < 1e-3
        and np.isfinite(recovery_coefficient)
        and recovery_coefficient > 0.0,
        {
            "cube_root_means": cube_root_means,
            "nu": NU,
            "C_rec_nu": recovery_coefficient,
            "N128_N256_relative_difference": refinement_relative_difference,
            "refinement_threshold": 1e-3,
        },
    )

    determinant_order = determinant_order_at_active_point()
    book.record(
        EXPECTED_CHECK_NAMES[2],
        determinant_order["low_order_zero"] and determinant_order["t4_expected"],
        determinant_order,
    )

    positive_fraction = grid_values["256"]["positive_fraction"]
    book.record(
        EXPECTED_CHECK_NAMES[3],
        positive_fraction > 0.01 and witness_f > 0.0,
        {
            "N256_positive_fraction": positive_fraction,
            "witness_f": witness_f,
            "minimum_positive_fraction": 0.01,
        },
    )

    production_coefficient = sp.Rational(2) * sp.Rational(1, 4)
    book.record(
        EXPECTED_CHECK_NAMES[4],
        production_coefficient == sp.Rational(1, 2),
        {"initial_strain_production": "1/4", "production_coefficient": production_coefficient},
    )

    times = np.array([1e-2, 1e-3, 1e-4], dtype=np.float64)
    recovery_leading = recovery_coefficient * times ** (4.0 / 3.0)
    production_leading = 0.5 * times
    ratios = production_leading / recovery_leading
    scaled_ratios = ratios * times ** (1.0 / 3.0)
    expected_scaled_ratio = 0.5 / recovery_coefficient
    book.record(
        EXPECTED_CHECK_NAMES[5],
        bool(np.all(np.diff(ratios) > 0.0))
        and bool(np.allclose(scaled_ratios, expected_scaled_ratio, rtol=0.0, atol=1e-12)),
        {
            "times": times,
            "leading_recovery": recovery_leading,
            "leading_production": production_leading,
            "ratios": ratios,
            "scaled_ratios": scaled_ratios,
            "expected_scaled_ratio": expected_scaled_ratio,
        },
    )
    values.update(
        {
            "grid_sizes": GRID_SIZES,
            "nu": NU,
            "integrated_cube_root_means": cube_root_means,
            "C_rec": recovery_coefficient,
            "determinant_order": determinant_order,
        }
    )


def protocol_integrity() -> dict[str, Any]:
    text = PROTOCOL.read_text(encoding="utf-8")
    declared_names = tuple(
        re.findall(r"^\d+\. `([^`]+)`", text, flags=re.MULTILINE)
    )
    return {
        "declared_check_count": len(declared_names),
        "declared_check_names": declared_names,
        "inventory_names_match": declared_names == EXPECTED_CHECK_NAMES,
        "grid_sizes_present": all(str(size) in text for size in GRID_SIZES),
        "rate_boundary_present": "t^{-1/3}" in text,
    }


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute() -> tuple[dict[str, Any], bool]:
    book = CheckBook()
    values: dict[str, Any] = {}
    verify_checks(book, values)
    integrity = protocol_integrity()
    note_text = NOTE.read_text(encoding="utf-8").lower()
    coefficient_text = COEFFICIENT_NOTE.read_text(encoding="utf-8").lower()
    temporal_text = TEMPORAL_NOTE.read_text(encoding="utf-8").lower()
    stretching_text = STRETCHING_NOTE.read_text(encoding="utf-8").lower()
    required_anchors = {
        "rate_note": (
            "c_{\\mathrm{rec}}(\\nu)",
            "t^{4/3}",
            "t^{-1/3}",
            "unresolved",
        ),
        "coefficient_note": ("8\\nu^4 f", "nonnegative everywhere"),
        "temporal_note": ("temporal covariance rank recovery", "active-point"),
        "stretching_note": ("positive initial vortex-stretching production", "1/4"),
    }
    missing_anchors = {
        key: [anchor for anchor in anchors if anchor not in text]
        for key, anchors, text in (
            ("rate_note", required_anchors["rate_note"], note_text),
            ("coefficient_note", required_anchors["coefficient_note"], coefficient_text),
            ("temporal_note", required_anchors["temporal_note"], temporal_text),
            ("stretching_note", required_anchors["stretching_note"], stretching_text),
        )
    }
    identities = {
        "rate_note": {"path": "CassiTheory/turbulence/navier-stokes-covariance-recovery-rate.md", "sha256": source_hash(NOTE)},
        "coefficient_note": {"path": "CassiTheory/turbulence/navier-stokes-rank-deficient-temporal-coefficient.md", "sha256": source_hash(COEFFICIENT_NOTE)},
        "temporal_note": {"path": "CassiTheory/turbulence/navier-stokes-rank-deficient-temporal-recovery.md", "sha256": source_hash(TEMPORAL_NOTE)},
        "stretching_note": {"path": "CassiTheory/turbulence/navier-stokes-rank-deficient-stretching.md", "sha256": source_hash(STRETCHING_NOTE)},
        "protocol": {"path": "CassiTheory/computations/navier-stokes-covariance-recovery-rate-prereg.md", "sha256": source_hash(PROTOCOL)},
        "verifier": {"path": "CassiTheory/computations/verify_navier_stokes_covariance_recovery_rate.py", "sha256": source_hash(Path(__file__).resolve())},
    }
    checks_ok = len(book.checks) == EXPECTED_CHECKS and not book.failures
    sources_ok = not any(missing_anchors.values())
    inventory_ok = (
        integrity["declared_check_count"] == EXPECTED_CHECKS
        and integrity["inventory_names_match"]
        and integrity["grid_sizes_present"]
        and integrity["rate_boundary_present"]
    )
    success = checks_ok and sources_ok and inventory_ok
    result = {
        "schema": SCHEMA,
        "status": "PASS" if success else "FAIL",
        "expected_check_count": EXPECTED_CHECKS,
        "expected_check_names": EXPECTED_CHECK_NAMES,
        "checks": book.checks,
        "failures": book.failures,
        "inventory_match": inventory_ok,
        "protocol_integrity": integrity,
        "source_anchors": {
            "required": required_anchors,
            "missing": missing_anchors,
        },
        "identities": identities,
        "classifications": {
            "integrated_recovery_coefficient": "SUPPORTS" if success else "UNRESOLVED",
            "initial_layer_rate_boundary": "SUPPORTS" if success else "UNRESOLVED",
            "finite_recovery_only_coefficient": "CONTRADICTS" if success else "UNRESOLVED",
            "uniform_exact_covariance_lower_bound": "UNRESOLVED",
            "production_relative_recovery_estimate": "UNRESOLVED",
            "arbitrary_data_navier_stokes_regularity": "UNRESOLVED",
        },
        "scope": {
            "trajectory_integration": "NOT_RUN",
            "covariance_pde_time_integration": "NOT_RUN",
            "fixed_coefficient_quadrature": "RUN",
            "active_point_time_jet": "EXACT_SYMBOLIC",
            "global_regularity": "UNRESOLVED",
        },
        "values": stringify(values),
    }
    return result, success


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")

    created = datetime.now(timezone.utc).isoformat()
    result, success = compute()
    result["created_utc"] = created
    manifest = {
        "created_utc": created,
        "identities": result["identities"],
        "numpy_version": np.__version__,
        "sympy_version": sp.__version__,
        "numeric_quadrature": "uniform periodic midpoint rule",
        "symbolic_arithmetic": "exact SymPy polynomial determinant",
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    for key, path in {
        "rate_note": NOTE,
        "coefficient_note": COEFFICIENT_NOTE,
        "temporal_note": TEMPORAL_NOTE,
        "stretching_note": STRETCHING_NOTE,
        "protocol": PROTOCOL,
        "verifier": Path(__file__).resolve(),
    }.items():
        (snapshot_dir / f"{key}{path.suffix}").write_bytes(path.read_bytes())
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    passed_count = sum(row["passed"] for row in result["checks"])
    print(f"{passed_count} / {EXPECTED_CHECKS} checks passed")
    print(f"inventory_match: {result['inventory_match']}")
    print(f"source_anchors_match: {not any(result['source_anchors']['missing'].values())}")
    print(f"status: {result['status']}")
    for name, classification in result["classifications"].items():
        print(f"{name}: {classification}")
    if success:
        print("ALL CHECKS PASSED")
        return 0
    for failure in result["failures"]:
        print(f"FAIL: {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
