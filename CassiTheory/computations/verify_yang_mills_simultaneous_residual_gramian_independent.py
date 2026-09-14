#!/usr/bin/env python3
"""Independently reconstruct the simultaneous residual Gramian receipt.

Protocol:
``computations/yang-mills-simultaneous-residual-gramian-prereg.md``.

This verifier does not import the primary residual-Gramian implementation. It
reconstructs the inverse-Gramian coverage identity, weighted source spectrum,
spatial probe quotients, and full-Q rank boundary from the primary receipt,
while independently checking every source and protocol hash binding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-simultaneous-residual-gramian-prereg.md"
SOURCE = Path(__file__).resolve()
PRIMARY_SOURCE = ROOT / "computations" / "verify_yang_mills_simultaneous_residual_gramian.py"
LARGE_SOURCE = ROOT / "computations" / "verify_yang_mills_su2_larger_volume_hamiltonian.py"
LARGE_PROTOCOL = ROOT / "computations" / "yang-mills-su2-larger-volume-hamiltonian-prereg.md"
LARGE_RECOVERY_PROTOCOL = ROOT / "computations" / "yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
LARGE_HELPER = ROOT / "computations" / "verify_yang_mills_exact_block_spectrum.py"
LARGE_RECEIPT = ROOT / "runs" / "yang_mills_su2_larger_volume_hamiltonian_recovery" / "current-verification.json"
LARGE_RECEIPT_TAIL_QUALIFICATIONS = (
    "tail_separation_C1_x0.25",
    "tail_separation_C2_x0.25",
    "tail_separation_C1_x1.0",
    "tail_separation_C2_x1.0",
)
DEFAULT_PRIMARY = ROOT / "runs/yang_mills_simultaneous_residual_gramian/verification-v4.json"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_simultaneous_residual_gramian/verification-independent-v4.json"

COUPLINGS = (1.0 / 64.0, 1.0 / 16.0, 1.0 / 4.0, 1.0)
TOLERANCE = 1.0e-8
MATRIX_TOLERANCE = 1.0e-10
WEIGHTS = np.full(11, 1.0 / 11.0, dtype=float)
PLAQUETTE_NAMES = (
    "xy_z0_0",
    "xy_z0_1",
    "xy_z1_0",
    "xy_z1_1",
    "xz_y0_0",
    "xz_y0_1",
    "xz_y1_0",
    "xz_y1_1",
    "yz_x0",
    "yz_x1",
    "yz_x2",
)
PLAQUETTE_CENTERS = np.asarray(
    [
        (0.5, 0.5, 0.0),
        (1.5, 0.5, 0.0),
        (0.5, 0.5, 1.0),
        (1.5, 0.5, 1.0),
        (0.5, 0.0, 0.5),
        (1.5, 0.0, 0.5),
        (0.5, 1.0, 0.5),
        (1.5, 1.0, 0.5),
        (0.0, 0.5, 0.5),
        (1.0, 0.5, 0.5),
        (2.0, 0.5, 0.5),
    ],
    dtype=float,
)
PROBE_COEFFICIENTS = {
    "constant": np.ones(11, dtype=float),
    "x_cosine": np.cos(np.pi * (PLAQUETTE_CENTERS[:, 0] + 0.5) / 3.0),
    "y_cosine": np.cos(np.pi * (PLAQUETTE_CENTERS[:, 1] + 0.5) / 2.0),
    "z_cosine": np.cos(np.pi * (PLAQUETTE_CENTERS[:, 2] + 0.5) / 2.0),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def check(name: str, passed: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **details}


def array(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=float)


def close_scalar(actual: float, expected: float, tolerance: float = TOLERANCE) -> bool:
    return abs(float(actual) - float(expected)) <= tolerance * max(1.0, abs(float(expected)))


def close_matrix(actual: np.ndarray, expected: np.ndarray, tolerance: float = TOLERANCE) -> bool:
    return float(np.max(np.abs(np.asarray(actual) - np.asarray(expected)))) <= tolerance


def expected_coverage(gramian: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    inverse = np.linalg.inv(gramian)
    diagonal = np.diag(inverse)
    coverage = inverse / np.sqrt(np.outer(diagonal, diagonal))
    return inverse, coverage


def run(primary_path: Path, output: Path) -> dict[str, Any]:
    if not primary_path.is_file():
        raise FileNotFoundError(primary_path)
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    dependencies = primary.get("dependencies", {})
    expected_dependency_paths = {
        relative(PROTOCOL): PROTOCOL,
        relative(PRIMARY_SOURCE): PRIMARY_SOURCE,
        relative(SOURCE): SOURCE,
        relative(LARGE_SOURCE): LARGE_SOURCE,
        relative(LARGE_PROTOCOL): LARGE_PROTOCOL,
        relative(LARGE_RECOVERY_PROTOCOL): LARGE_RECOVERY_PROTOCOL,
        relative(LARGE_HELPER): LARGE_HELPER,
        relative(LARGE_RECEIPT): LARGE_RECEIPT,
    }
    dependency_pass = all(
        path.is_file() and dependencies.get(name) == sha256(path)
        for name, path in expected_dependency_paths.items()
    )
    rows = primary.get("rows", [])
    checks: list[dict[str, Any]] = [
        check("protocol_path", PROTOCOL.is_file()),
        check("independent_source_path", SOURCE.is_file()),
        check("primary_receipt_path", primary_path.is_file()),
        check("primary_status", primary.get("status") == "PASS", status=primary.get("status")),
        check("primary_schema", primary.get("schema") == "yang_mills_simultaneous_residual_gramian_v1"),
        check(
            "primary_protocol_binding",
            dependencies.get(relative(PROTOCOL)) == sha256(PROTOCOL),
            observed=dependencies.get(relative(PROTOCOL)),
            expected=sha256(PROTOCOL),
        ),
        check(
            "primary_source_binding",
            dependencies.get(relative(PRIMARY_SOURCE)) == sha256(PRIMARY_SOURCE),
            observed=dependencies.get(relative(PRIMARY_SOURCE)),
            expected=sha256(PRIMARY_SOURCE),
        ),
        check("larger_dependency_binding", dependency_pass, dependency_count=len(dependencies)),
        check(
            "schedule_binding",
            primary.get("couplings") == list(COUPLINGS)
            and primary.get("plaquette_names") == list(PLAQUETTE_NAMES)
            and len(rows) == len(COUPLINGS),
            observed_couplings=primary.get("couplings"),
            observed_row_count=len(rows),
        ),
        check(
            "primary_check_contract",
            primary.get("checks_total") == 50
            and primary.get("checks_passed") == 50
            and primary.get("classification") == "QUALIFIED_FINITE_SOURCE_SECTOR_RECOVERY"
            and primary.get("larger_receipt_qualification_passed") is True
            and primary.get("larger_receipt_failed_checks") == list(LARGE_RECEIPT_TAIL_QUALIFICATIONS)
            and len(primary.get("checks", [])) == 50
            and all(item.get("passed") for item in primary.get("checks", [])),
            checks_passed=primary.get("checks_passed"),
            checks_total=primary.get("checks_total"),
            primary_classification=primary.get("classification"),
            source_failed_checks=primary.get("larger_receipt_failed_checks"),
        ),
    ]
    independent_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        coupling = float(row["coupling"])
        gramian = array(row["source_gramian"])
        inverse, coverage = expected_coverage(gramian)
        observed_coverage = array(row["coverage_matrix"])
        weighted_eigenvalues = np.linalg.eigvalsh(coverage / 11.0)
        observed_weighted_eigenvalues = array(row["coverage_eigenvalues_weighted"])
        source_rank = int(np.linalg.matrix_rank(gramian, tol=MATRIX_TOLERANCE))
        row_key = str(coupling)
        checks.extend(
            [
                check(
                    f"source_gramian_reconstruction_x{row_key}",
                    gramian.shape == (11, 11)
                    and source_rank == 11
                    and float(np.min(np.linalg.eigvalsh(gramian))) > MATRIX_TOLERANCE
                    and close_matrix(gramian, gramian.T)
                    and close_matrix(gramian @ inverse, np.eye(11)),
                    rank=source_rank,
                    minimum_eigenvalue=float(np.min(np.linalg.eigvalsh(gramian))),
                ),
                check(
                    f"coverage_reconstruction_x{row_key}",
                    close_matrix(observed_coverage, coverage)
                    and close_matrix(observed_coverage, observed_coverage.T)
                    and close_matrix(np.diag(observed_coverage), np.ones(11)),
                    maximum_error=float(np.max(np.abs(observed_coverage - coverage))),
                ),
                check(
                    f"source_spectrum_reconstruction_x{row_key}",
                    close_matrix(observed_weighted_eigenvalues, weighted_eigenvalues)
                    and close_scalar(float(row["source_floor"]), float(weighted_eigenvalues[0]))
                    and float(weighted_eigenvalues[0]) > 0.0,
                    gamma=float(weighted_eigenvalues[0]),
                    observed_gamma=float(row["source_floor"]),
                ),
                check(
                    f"soft_probe_reconstruction_x{row_key}",
                    all(
                        item.get("name") in PROBE_COEFFICIENTS
                        and close_scalar(
                            float(item["direct_rayleigh"]),
                            float(
                                np.sum(
                                    WEIGHTS
                                    * PROBE_COEFFICIENTS[item["name"]] ** 2
                                    / np.diag(inverse)
                                )
                                / (
                                    PROBE_COEFFICIENTS[item["name"]]
                                    @ gramian
                                    @ PROBE_COEFFICIENTS[item["name"]]
                                )
                            ),
                        )
                        and close_scalar(float(item["formula_rayleigh"]), float(item["direct_rayleigh"]))
                        for item in row.get("probe_rows", [])
                    )
                    and {item.get("name") for item in row.get("probe_rows", [])} == set(PROBE_COEFFICIENTS),
                    probe_count=len(row.get("probe_rows", [])),
                ),
                check(
                    f"full_q_boundary_reconstruction_x{row_key}",
                    row.get("q_dimension") == 867
                    and row.get("residual_rank") == 11
                    and row.get("full_q_nullity") == 856
                    and float(row.get("full_q_floor")) == 0.0,
                    q_dimension=row.get("q_dimension"),
                    residual_rank=row.get("residual_rank"),
                    full_q_nullity=row.get("full_q_nullity"),
                ),
            ]
        )
        independent_rows.append(
            {
                "coupling": coupling,
                "source_rank": source_rank,
                "source_eigenvalues": np.linalg.eigvalsh(gramian).tolist(),
                "coverage_matrix": coverage.tolist(),
                "weighted_coverage_eigenvalues": weighted_eigenvalues.tolist(),
                "source_floor": float(weighted_eigenvalues[0]),
            }
        )
    if len(checks) != 30:
        raise ArithmeticError(f"independent check contract changed: {len(checks)}")
    passed = all(item["passed"] for item in checks)
    record: dict[str, Any] = {
        "schema": "yang_mills_simultaneous_residual_gramian_independent_v1",
        "status": "PASS" if passed else "FAIL",
        "classification": "PRIMARY_RECEIPT_ARITHMETIC_AUDIT_PASS" if passed else "FAIL",
        "protocol": relative(PROTOCOL),
        "source": relative(SOURCE),
        "primary_source": relative(PRIMARY_SOURCE),
        "primary_receipt": relative(primary_path),
        "dependencies": {name: sha256(path) for name, path in expected_dependency_paths.items()},
        "rows": independent_rows,
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "scope": "independent arithmetic reconstruction of the finite source-sector residual Gramian",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    record = run(args.primary, args.output)
    print(
        f"status={record['status']} classification={record['classification']} "
        f"checks={record['checks_passed']}/{record['checks_total']}"
    )
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
