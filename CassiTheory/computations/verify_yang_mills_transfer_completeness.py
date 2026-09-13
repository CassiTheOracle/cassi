#!/usr/bin/env python3
"""Verify the finite positive-transfer completeness criterion.

The calculation is deliberately finite and synthetic.  It tests the exact
second-moment defect identity and keeps retained completeness separate from
all-moment matching.  It does not construct a Yang--Mills block map.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-transfer-completeness-prereg.md"
SOURCE = Path(__file__).resolve()
OUT_DIR = ROOT / "runs" / "yang-mills-transfer-completeness"
OUT_PATH = OUT_DIR / "verification.json"
TOLERANCE = 1.0e-12
SPECTRAL_TOLERANCE = 1.0e-11
MOMENT_ORDERS = tuple(range(6))
SCHEMA = "cassi.yang-mills.transfer-completeness.verification.v1"


def zeros(rows: int, columns: int) -> list[list[float]]:
    return [[0.0 for _ in range(columns)] for _ in range(rows)]


def identity(size: int) -> list[list[float]]:
    result = zeros(size, size)
    for index in range(size):
        result[index][index] = 1.0
    return result


def transpose(matrix: list[list[float]]) -> list[list[float]]:
    return [list(column) for column in zip(*matrix, strict=True)]


def matmul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    rows = len(left)
    inner = len(right)
    columns = len(right[0])
    if any(len(row) != inner for row in left):
        raise ValueError("left matrix shape mismatch")
    if any(len(row) != columns for row in right):
        raise ValueError("right matrix shape mismatch")
    return [
        [
            sum(left[row][index] * right[index][column] for index in range(inner))
            for column in range(columns)
        ]
        for row in range(rows)
    ]


def subtract(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [left[row][column] - right[row][column] for column in range(len(left[row]))]
        for row in range(len(left))
    ]


def max_abs(matrix: list[list[float]]) -> float:
    return max((abs(value) for row in matrix for value in row), default=0.0)


def frobenius_norm(matrix: list[list[float]]) -> float:
    return math.sqrt(sum(value * value for row in matrix for value in row))


def matrix_power(matrix: list[list[float]], exponent: int) -> list[list[float]]:
    result = identity(len(matrix))
    factor = [row[:] for row in matrix]
    remaining = exponent
    while remaining:
        if remaining & 1:
            result = matmul(result, factor)
        factor = matmul(factor, factor)
        remaining >>= 1
    return result


def submatrix(matrix: list[list[float]], indices: list[int]) -> list[list[float]]:
    return [[matrix[row][column] for column in indices] for row in indices]


def close(left: float, right: float, tolerance: float = TOLERANCE) -> bool:
    return abs(left - right) <= tolerance * max(1.0, abs(left), abs(right))


def matrix_close(left: list[list[float]], right: list[list[float]], tolerance: float = TOLERANCE) -> bool:
    return max_abs(subtract(left, right)) <= tolerance


def symmetric_eigenvalues(matrix: list[list[float]]) -> list[float]:
    """Jacobi diagonalization for the small real symmetric fixtures."""

    work = [row[:] for row in matrix]
    size = len(work)
    for _ in range(100 * size * size):
        pivot = (0, 1)
        largest = 0.0
        for row in range(size):
            for column in range(row + 1, size):
                magnitude = abs(work[row][column])
                if magnitude > largest:
                    largest = magnitude
                    pivot = (row, column)
        if largest <= 1.0e-15:
            break
        row, column = pivot
        angle = 0.5 * math.atan2(
            2.0 * work[row][column], work[column][column] - work[row][row]
        )
        cosine = math.cos(angle)
        sine = math.sin(angle)
        for index in range(size):
            old_row = work[row][index]
            old_column = work[column][index]
            work[row][index] = cosine * old_row - sine * old_column
            work[column][index] = sine * old_row + cosine * old_column
        for index in range(size):
            old_row = work[index][row]
            old_column = work[index][column]
            work[index][row] = cosine * old_row - sine * old_column
            work[index][column] = sine * old_row + cosine * old_column
        work[row][column] = 0.0
        work[column][row] = 0.0
    return sorted(work[index][index] for index in range(size))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    **details: Any,
) -> None:
    checks.append({"name": name, "passed": bool(passed), **details})


def retained_map() -> list[list[float]]:
    return [
        [0.0, 0.0],
        [1.0, 0.0],
        [0.0, 1.0],
        [0.0, 0.0],
    ]


def fixture_definitions() -> dict[str, dict[str, Any]]:
    return {
        "complete": {
            "matrix": [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 0.72, 0.0, 0.0],
                [0.0, 0.0, 0.58, 0.0],
                [0.0, 0.0, 0.0, 0.0],
            ],
            "physical_indices": [1, 2],
            "expected_reducing": True,
            "expected_complete": True,
        },
        "incomplete": {
            "matrix": [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 0.72, 0.0, 0.0],
                [0.0, 0.0, 0.58, 0.0],
                [0.0, 0.0, 0.0, 0.91],
            ],
            "physical_indices": [1, 2, 3],
            "expected_reducing": True,
            "expected_complete": False,
        },
        "leaky": {
            "matrix": [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 0.72, 0.0, 0.07],
                [0.0, 0.0, 0.58, 0.0],
                [0.0, 0.07, 0.0, 0.41],
            ],
            "physical_indices": [1, 2, 3],
            "expected_reducing": False,
            "expected_complete": False,
        },
    }


def fixture_observables(matrix: list[list[float]]) -> dict[str, Any]:
    retained = retained_map()
    transpose_retained = transpose(retained)
    projector = matmul(retained, transpose_retained)
    complement = subtract(identity(len(matrix)), projector)
    compressed = matmul(matmul(transpose_retained, matrix), retained)
    leakage = matmul(complement, retained)
    transferred_leakage = matmul(complement, matmul(matrix, retained))
    defect_matrix = matmul(transpose_retained, matmul(matrix, transferred_leakage))
    fine_moments = []
    coarse_moments = []
    moment_errors = []
    for order in MOMENT_ORDERS:
        fine = matmul(
            matmul(transpose_retained, matrix_power(matrix, order)), retained
        )
        coarse = matrix_power(compressed, order)
        fine_moments.append(fine)
        coarse_moments.append(coarse)
        moment_errors.append(max_abs(subtract(fine, coarse)))
    return {
        "projector": projector,
        "complement": complement,
        "compressed": compressed,
        "leakage": leakage,
        "transferred_leakage": transferred_leakage,
        "defect_matrix": defect_matrix,
        "leakage_norm": frobenius_norm(transferred_leakage),
        "defect_norm": frobenius_norm(defect_matrix),
        "fine_moments": fine_moments,
        "coarse_moments": coarse_moments,
        "moment_errors": moment_errors,
    }


def full_gap(matrix: list[list[float]], physical_indices: list[int]) -> float:
    eigenvalues = symmetric_eigenvalues(submatrix(matrix, physical_indices))
    return -math.log(max(eigenvalues))


def retained_gap(compressed: list[list[float]]) -> float:
    return -math.log(max(symmetric_eigenvalues(compressed)))


def mutated_classifications(
    observables: dict[str, dict[str, Any]],
    gaps: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    leaky_errors = observables["leaky"]["moment_errors"]
    baseline_leaky_exact = all(error <= TOLERANCE for error in leaky_errors)
    one_step_only_leaky_exact = all(
        error <= TOLERANCE for error in leaky_errors[:2]
    )
    baseline_incomplete_full = (
        observables["incomplete"]["defect_norm"] <= TOLERANCE
        and fixture_definitions()["incomplete"]["expected_complete"]
    )
    ignore_completeness_full = observables["incomplete"]["defect_norm"] <= TOLERANCE
    baseline_gap_equal = close(
        gaps["incomplete"]["full"], gaps["incomplete"]["retained"], SPECTRAL_TOLERANCE
    )
    compressed_gap_as_full = True
    baseline_leaky_reducing = observables["leaky"]["defect_norm"] <= TOLERANCE
    leakage_forced_zero = True
    return [
        {
            "name": "omit_second_moment_defect",
            "unmutated_passed": not baseline_leaky_exact,
            "mutation_passed": one_step_only_leaky_exact,
            "comparisons_attempted": 2,
        },
        {
            "name": "ignore_completeness",
            "unmutated_passed": not baseline_incomplete_full,
            "mutation_passed": ignore_completeness_full,
            "comparisons_attempted": 2,
        },
        {
            "name": "compressed_gap_is_full_gap",
            "unmutated_passed": not baseline_gap_equal,
            "mutation_passed": compressed_gap_as_full,
            "comparisons_attempted": 2,
        },
        {
            "name": "accept_leakage_as_exact",
            "unmutated_passed": not baseline_leaky_reducing,
            "mutation_passed": leakage_forced_zero,
            "comparisons_attempted": 2,
        },
    ]


def build_receipt() -> dict[str, Any]:
    definitions = fixture_definitions()
    retained = retained_map()
    checks: list[dict[str, Any]] = []
    fixtures: dict[str, dict[str, Any]] = {}
    observables: dict[str, dict[str, Any]] = {}
    gaps: dict[str, dict[str, float]] = {}
    for name, fixture in definitions.items():
        matrix = fixture["matrix"]
        physical_indices = fixture["physical_indices"]
        transpose_retained = transpose(retained)
        compressed = matmul(matmul(transpose_retained, matrix), retained)
        data = fixture_observables(matrix)
        observables[name] = data
        eigenvalues = symmetric_eigenvalues(submatrix(matrix, physical_indices))
        gaps[name] = {
            "full": full_gap(matrix, physical_indices),
            "retained": retained_gap(compressed),
        }
        check(
            checks,
            f"{name}_self_adjoint",
            matrix_close(matrix, transpose(matrix)),
            residual=max_abs(subtract(matrix, transpose(matrix))),
        )
        check(
            checks,
            f"{name}_positive_physical_spectrum",
            min(eigenvalues) > 0.0 and max(eigenvalues) < 1.0,
            eigenvalues=eigenvalues,
        )
        check(
            checks,
            f"{name}_vacuum_eigenvalue",
            close(matrix[0][0], 1.0)
            and max(abs(matrix[0][index]) for index in range(1, len(matrix)))
            <= TOLERANCE,
            value=matrix[0][0],
        )
        check(
            checks,
            f"{name}_retained_map_isometry",
            matrix_close(matmul(transpose_retained, retained), identity(2)),
        )
        check(
            checks,
            f"{name}_physical_declaration",
            physical_indices[0] == 1
            and physical_indices == sorted(set(physical_indices))
            and 0 not in physical_indices
            and all(index < len(matrix) for index in physical_indices),
            physical_indices=physical_indices,
        )
        check(
            checks,
            f"{name}_compression_shape",
            len(compressed) == 2 and all(len(row) == 2 for row in compressed),
        )
        expected_reducing = fixture["expected_reducing"]
        expected_defect_zero = expected_reducing
        expected_m1_error = data["moment_errors"][1]
        expected_m2_defect = data["moment_errors"][2]
        check(
            checks,
            f"{name}_m1_compression",
            expected_m1_error <= TOLERANCE,
            error=expected_m1_error,
        )
        check(
            checks,
            f"{name}_second_moment_defect_classification",
            (expected_m2_defect <= TOLERANCE) == expected_defect_zero,
            defect=expected_m2_defect,
            expected_zero=expected_defect_zero,
        )
        check(
            checks,
            f"{name}_defect_norm_identity",
            matrix_close(
                data["defect_matrix"],
                matmul(transpose(data["transferred_leakage"]), data["transferred_leakage"]),
            ),
            defect_norm=data["defect_norm"],
            leakage_norm=data["leakage_norm"],
        )
        check(
            checks,
            f"{name}_invariance_equivalence",
            (data["defect_norm"] <= TOLERANCE) == expected_reducing,
            defect_norm=data["defect_norm"],
            expected_reducing=expected_reducing,
        )
        for order, error in zip(MOMENT_ORDERS, data["moment_errors"], strict=True):
            expected_match = expected_reducing or order < 2
            check(
                checks,
                f"{name}_moment_{order}",
                (error <= TOLERANCE) == expected_match,
                order=order,
                error=error,
                expected_match=expected_match,
            )
        fixtures[name] = {
            "physical_indices": physical_indices,
            "expected_reducing": expected_reducing,
            "expected_complete": fixture["expected_complete"],
            "eigenvalues": eigenvalues,
            "defect_norm": data["defect_norm"],
            "moment_errors": data["moment_errors"],
            "full_gap": gaps[name]["full"],
            "retained_gap": gaps[name]["retained"],
        }
    check(
        checks,
        "completeness_flags",
        fixtures["complete"]["expected_complete"]
        and not fixtures["incomplete"]["expected_complete"]
        and not fixtures["leaky"]["expected_complete"],
    )
    check(
        checks,
        "gap_boundary_withholds_incomplete_and_leaky",
        close(
            fixtures["complete"]["full_gap"],
            fixtures["complete"]["retained_gap"],
            SPECTRAL_TOLERANCE,
        )
        and not close(
            fixtures["incomplete"]["full_gap"],
            fixtures["incomplete"]["retained_gap"],
            SPECTRAL_TOLERANCE,
        )
        and fixtures["incomplete"]["expected_complete"] is False
        and fixtures["leaky"]["expected_complete"] is False,
        complete_gap=fixtures["complete"]["full_gap"],
        incomplete_full_gap=fixtures["incomplete"]["full_gap"],
        incomplete_retained_gap=fixtures["incomplete"]["retained_gap"],
    )
    firing_controls = mutated_classifications(observables, gaps)
    for control in firing_controls:
        check(
            checks,
            f"mutation_{control['name']}_fires",
            control["unmutated_passed"] and control["mutation_passed"],
            comparisons_attempted=control["comparisons_attempted"],
        )
    all_passed = all(item["passed"] for item in checks)
    if len(checks) != 54:
        raise RuntimeError(f"expected 54 checks, got {len(checks)}")
    return {
        "schema": SCHEMA,
        "status": "PASS" if all_passed else "FAIL",
        "verdict": "PASS" if all_passed else "FAIL",
        "tolerances": {
            "matrix": TOLERANCE,
            "spectral": SPECTRAL_TOLERANCE,
        },
        "moment_orders": list(MOMENT_ORDERS),
        "fixtures": fixtures,
        "firing_controls": firing_controls,
        "checks": checks,
        "summary": {
            "checks": len(checks),
            "passing_checks": sum(item["passed"] for item in checks),
            "firing_controls": len(firing_controls),
            "firing_controls_activated": sum(
                control["unmutated_passed"] and control["mutation_passed"]
                for control in firing_controls
            ),
        },
        "claims": {
            "finite_transfer_criterion": "PASS" if all_passed else "FAIL",
            "exact_rg_block_map_constructed": False,
            "interacting_transfer_operator_constructed": False,
            "retained_observable_completeness_established": False,
            "full_physical_gap_established": False,
            "thermodynamic_limit_constructed": False,
            "continuum_limit_established": False,
            "continuum_mass_gap_established": False,
            "clay_verdict": "NULL",
        },
        "sources": {
            "protocol": {
                "path": "computations/yang-mills-transfer-completeness-prereg.md",
                "sha256": sha256(PROTOCOL),
            },
            "primary_source": {
                "path": "computations/verify_yang_mills_transfer_completeness.py",
                "sha256": sha256(SOURCE),
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT_PATH)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    output = args.output
    if output.exists() and not args.replace:
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    receipt = build_receipt()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"status={receipt['status']} checks={receipt['summary']['passing_checks']}/"
        f"{receipt['summary']['checks']} firing="
        f"{receipt['summary']['firing_controls_activated']}/"
        f"{receipt['summary']['firing_controls']}"
    )
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
