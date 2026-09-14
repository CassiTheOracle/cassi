#!/usr/bin/env python3
"""Verify the simultaneous finite translated-block residual Gramian.

Protocol:
``computations/yang-mills-simultaneous-residual-gramian-prereg.md``.

The calculation reuses the recovered 3x2x2 C=1 gauge-invariant Hamiltonian
source, solves the four declared finite ground-state problems, places all
centered plaquette vectors in one common Euclidean Hilbert space, and builds
all eleven exterior-space residual projections simultaneously.  The receipt
reports both the positive floor on the eleven-vector source sector and the
zero floor of its zero extension to the complete centered Q sector.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROTOCOL = ROOT / "computations" / "yang-mills-simultaneous-residual-gramian-prereg.md"
SOURCE = Path(__file__).resolve()
INDEPENDENT_SOURCE = ROOT / "computations" / "verify_yang_mills_simultaneous_residual_gramian_independent.py"
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
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_simultaneous_residual_gramian" / "verification-v4.json"

COUPLINGS = (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1, 1))
MATRIX_TOLERANCE = 1.0e-10
COMPARISON_TOLERANCE = 1.0e-8
RANK_TOLERANCE = 1.0e-10
WEIGHTS = np.full(11, 1.0 / 11.0, dtype=float)
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


def scalar(value: Any) -> float:
    return float(np.real(value))


def as_real(vector: Any, name: str) -> np.ndarray:
    array = np.asarray(vector)
    imaginary = float(np.max(np.abs(array.imag))) if np.iscomplexobj(array) and array.size else 0.0
    if imaginary > MATRIX_TOLERANCE:
        raise ArithmeticError(f"{name} has imaginary residual {imaginary}")
    return np.asarray(array.real, dtype=float)


def matrix_error(actual: np.ndarray, expected: np.ndarray) -> float:
    difference = np.asarray(actual) - np.asarray(expected)
    denominator = max(1.0, float(np.linalg.norm(expected, ord=2)))
    return float(np.linalg.norm(difference, ord=2)) / denominator


def load_large_source():
    return importlib.import_module("computations.verify_yang_mills_su2_larger_volume_hamiltonian")


def check(name: str, passed: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **details}


def build_plaquette_source(large: Any, states: tuple[Any, ...], source_receipt: dict[str, Any]) -> tuple[list[dict[str, Any]], Any, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    operator = large.csr_matrix((len(states), len(states)), dtype=complex)
    matrix_checks: list[dict[str, Any]] = []
    expected_rows = source_receipt["matrices"]["1"]
    expected_by_name = {row["name"]: row for row in expected_rows}
    for name, word in zip(large.PLAQUETTE_NAMES, large.PLAQUETTES):
        evaluated = large.evaluate_plaquette(states, {}, {}, word, 1)
        matrix = evaluated["matrix"]
        operator = (operator + matrix).tocsr()
        expected = expected_by_name[name]
        same_hash = evaluated["matrix_hash"] == expected["matrix_hash"]
        same_count = evaluated["candidate_entries"] == expected["candidate_entries"]
        same_nonzero = evaluated["nonzero_entries"] == expected["nonzero_entries"]
        matrix_checks.append(
            {
                "name": name,
                "matrix_hash": evaluated["matrix_hash"],
                "expected_matrix_hash": expected["matrix_hash"],
                "candidate_entries": evaluated["candidate_entries"],
                "expected_candidate_entries": expected["candidate_entries"],
                "nonzero_entries": evaluated["nonzero_entries"],
                "expected_nonzero_entries": expected["nonzero_entries"],
                "pass": bool(same_hash and same_count and same_nonzero),
            }
        )
        rows.append(evaluated)
    operator.sum_duplicates()
    operator.sort_indices()
    return rows, operator, matrix_checks


def residual_family(vectors: np.ndarray) -> dict[str, Any]:
    dimension, count = vectors.shape
    residuals = np.zeros_like(vectors)
    exterior_ranks: list[int] = []
    residual_norms: list[float] = []
    orthogonality_errors: list[float] = []
    reconstruction_errors: list[float] = []
    for index in range(count):
        exterior = np.delete(vectors, index, axis=1)
        left, singular_values, _ = np.linalg.svd(exterior, full_matrices=False)
        scale = float(singular_values[0]) if singular_values.size else 0.0
        rank = int(np.count_nonzero(singular_values > RANK_TOLERANCE * max(1.0, scale)))
        frame = left[:, :rank]
        projection = frame @ (frame.T @ vectors[:, index])
        residual = vectors[:, index] - projection
        norm = float(np.linalg.norm(residual))
        if norm <= MATRIX_TOLERANCE:
            raise ArithmeticError(f"zero residual for source block {index}")
        unit = residual / norm
        residuals[:, index] = unit
        exterior_ranks.append(rank)
        residual_norms.append(norm)
        orthogonality_errors.append(float(np.linalg.norm(frame.T @ unit)) if rank else 0.0)
        reconstruction_errors.append(float(np.linalg.norm(projection + residual - vectors[:, index])))
    direct_coverage = residuals.T @ residuals
    inverse_gramian = np.linalg.inv(vectors.T @ vectors)
    inverse_coverage = inverse_gramian / np.sqrt(np.outer(np.diag(inverse_gramian), np.diag(inverse_gramian)))
    return {
        "residual_vectors": residuals,
        "exterior_ranks": exterior_ranks,
        "residual_norms": residual_norms,
        "orthogonality_errors": orthogonality_errors,
        "reconstruction_errors": reconstruction_errors,
        "coverage_matrix": direct_coverage,
        "inverse_gramian": inverse_gramian,
        "coverage_error": matrix_error(direct_coverage, inverse_coverage),
    }


def probe_rows(
    vectors: np.ndarray,
    inverse_gramian: np.ndarray,
    residual_vectors: np.ndarray,
) -> list[dict[str, Any]]:
    if vectors.ndim != 2 or vectors.shape[1] != 11:
        raise ValueError(f"source vectors must have shape (D, 11), got {vectors.shape}")
    if residual_vectors.shape != vectors.shape:
        raise ValueError(
            f"residual vectors must share the physical/source dimensions {vectors.shape}, "
            f"got {residual_vectors.shape}"
        )
    rows: list[dict[str, Any]] = []
    for name, coefficients in PROBE_COEFFICIENTS.items():
        field = vectors @ coefficients
        denominator = float(field @ field)
        residual_coordinates = residual_vectors.T @ field
        direct_numerator = float(np.sum(WEIGHTS * residual_coordinates * residual_coordinates))
        direct = direct_numerator / denominator
        formula_numerator = float(np.sum(WEIGHTS * coefficients * coefficients / np.diag(inverse_gramian)))
        formula_denominator = float(coefficients @ np.linalg.inv(inverse_gramian) @ coefficients)
        formula = formula_numerator / formula_denominator
        rows.append(
            {
                "name": name,
                "coefficients": coefficients.tolist(),
                "norm_squared": denominator,
                "direct_rayleigh": direct,
                "formula_rayleigh": formula,
                "absolute_error": abs(direct - formula),
            }
        )
    return rows

def build_row(large: Any, states: tuple[Any, ...], plaquette_rows: list[dict[str, Any]], operator: Any, coupling: Fraction) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    solved = large.solve_ritz(states, plaquette_rows, coupling, operator=operator)
    omega = as_real(solved["physical_vector"], "ground vector")
    omega_norm = float(omega @ omega)
    normalized_vectors: list[np.ndarray] = []
    means: list[float] = []
    for row in plaquette_rows:
        matrix = large.sparse_from_row(row, len(states)) if "matrix" not in row else row["matrix"]
        physical = large.normalized_operator(matrix, states)
        action = as_real(physical @ omega, "normalized plaquette action")
        mean = float(omega @ action)
        means.append(mean)
        normalized_vectors.append(action - mean * omega)
    vectors = np.column_stack(normalized_vectors)
    source_gramian = vectors.T @ vectors
    source_eigenvalues = np.linalg.eigvalsh(source_gramian)
    source_rank = int(np.linalg.matrix_rank(source_gramian, tol=RANK_TOLERANCE))
    family = residual_family(vectors)
    residuals = family["residual_vectors"]
    coverage = family["coverage_matrix"]
    inverse_gramian = family["inverse_gramian"]
    coverage_eigenvalues = np.linalg.eigvalsh(coverage / 11.0)
    q_compatibility = np.column_stack(
        [vector - omega * float(omega @ vector) for vector in normalized_vectors]
    )
    probe_data = probe_rows(vectors, inverse_gramian, residuals)
    source_floor = float(coverage_eigenvalues[0])
    full_q_dimension = len(states) - 1
    residual_rank = int(np.linalg.matrix_rank(residuals, tol=RANK_TOLERANCE))
    full_q_nullity = full_q_dimension - residual_rank
    row_key = str(coupling.numerator / coupling.denominator)
    row_checks = [
        check(
            f"finite_spectrum_x{row_key}",
            np.isfinite(solved["ground_energy"])
            and np.isfinite(solved["ritz_gap"])
            and solved["ritz_gap"] > 0.0
            and solved["generalized_residual"] <= MATRIX_TOLERANCE,
            ground_energy=solved["ground_energy"],
            ritz_gap=solved["ritz_gap"],
            residual=solved["generalized_residual"],
        ),
        check(
            f"q_decomposition_x{row_key}",
            abs(omega_norm - 1.0) <= MATRIX_TOLERANCE
            and float(np.linalg.norm(omega @ vectors)) <= MATRIX_TOLERANCE
            and float(np.linalg.norm(q_compatibility - vectors)) <= MATRIX_TOLERANCE,
            omega_norm=omega_norm,
            source_q_residual=float(np.linalg.norm(omega @ vectors)),
        ),
        check(
            f"source_gramian_x{row_key}",
            source_rank == 11
            and float(np.min(source_eigenvalues)) > MATRIX_TOLERANCE
            and matrix_error(source_gramian, source_gramian.T) <= MATRIX_TOLERANCE,
            rank=source_rank,
            minimum_eigenvalue=float(np.min(source_eigenvalues)),
        ),
        check(
            f"exterior_schedule_x{row_key}",
            family["exterior_ranks"] == [10] * 11
            and min(family["residual_norms"]) > MATRIX_TOLERANCE,
            exterior_ranks=family["exterior_ranks"],
            minimum_residual_norm=min(family["residual_norms"]),
        ),
        check(
            f"residual_projectors_x{row_key}",
            max(family["orthogonality_errors"] + family["reconstruction_errors"]) <= MATRIX_TOLERANCE
            and matrix_error(coverage, coverage.T) <= MATRIX_TOLERANCE
            and float(np.max(np.abs(np.diag(coverage) - 1.0))) <= MATRIX_TOLERANCE,
            maximum_exterior_orthogonality=max(family["orthogonality_errors"]),
            maximum_reconstruction=max(family["reconstruction_errors"]),
        ),
        check(
            f"null_compatibility_x{row_key}",
            float(np.max(np.abs(omega @ residuals))) <= MATRIX_TOLERANCE,
            maximum_vacuum_overlap=float(np.max(np.abs(omega @ residuals))),
        ),
        check(
            f"coverage_reconstruction_x{row_key}",
            family["coverage_error"] <= MATRIX_TOLERANCE,
            coverage_error=family["coverage_error"],
        ),
        check(
            f"source_floor_x{row_key}",
            source_floor > 0.0
            and np.isfinite(source_floor)
            and abs(source_floor - float(np.min(coverage_eigenvalues))) <= MATRIX_TOLERANCE,
            gamma_source=source_floor,
            amplification=float(1.0 / source_floor),
            coverage_eigenvalues=coverage_eigenvalues.tolist(),
        ),
        check(
            f"probe_reconstruction_x{row_key}",
            all(
                row["norm_squared"] > MATRIX_TOLERANCE
                and np.isfinite(row["direct_rayleigh"])
                and abs(row["absolute_error"]) <= MATRIX_TOLERANCE
                for row in probe_data
            ),
            maximum_probe_error=max(row["absolute_error"] for row in probe_data),
        ),
        check(
            f"full_q_boundary_x{row_key}",
            full_q_dimension == 867
            and residual_rank == 11
            and full_q_nullity == 856,
            q_dimension=full_q_dimension,
            residual_rank=residual_rank,
            full_q_floor=0.0,
            full_q_nullity=full_q_nullity,
        ),
    ]
    row = {
        "coupling": float(coupling),
        "dimension": len(states),
        "ground_energy": float(solved["ground_energy"]),
        "first_excited": float(solved["first_excited"]),
        "ritz_gap": float(solved["ritz_gap"]),
        "generalized_residual": float(solved["generalized_residual"]),
        "omega_norm_squared": omega_norm,
        "means": means,
        "source_gramian": source_gramian.tolist(),
        "source_gramian_eigenvalues": source_eigenvalues.tolist(),
        "source_gramian_rank": source_rank,
        "inverse_source_gramian": inverse_gramian.tolist(),
        "exterior_ranks": family["exterior_ranks"],
        "residual_norms": family["residual_norms"],
        "residual_vectors": residuals.tolist(),
        "coverage_matrix": coverage.tolist(),
        "coverage_eigenvalues_weighted": coverage_eigenvalues.tolist(),
        "source_floor": source_floor,
        "source_amplification": float(1.0 / source_floor),
        "q_dimension": full_q_dimension,
        "residual_rank": residual_rank,
        "full_q_floor": 0.0,
        "full_q_nullity": full_q_nullity,
        "probe_rows": probe_data,
        "checks": row_checks,
    }
    return row, row_checks


def run(output: Path) -> dict[str, Any]:
    if not PROTOCOL.is_file() or not LARGE_SOURCE.is_file() or not LARGE_RECEIPT.is_file():
        raise FileNotFoundError("missing protocol, larger-volume source, or recovered source receipt")
    if not INDEPENDENT_SOURCE.is_file():
        raise FileNotFoundError(f"independent verifier source is required before primary run: {INDEPENDENT_SOURCE}")
    source_receipt = json.loads(LARGE_RECEIPT.read_text(encoding="utf-8"))
    source_failed_checks = tuple(
        item.get("name")
        for item in source_receipt.get("checks", [])
        if item.get("passed") is False
    )
    source_qualification_ok = (
        source_receipt.get("checks_passed") == 234
        and source_receipt.get("checks_total") == 238
        and set(source_failed_checks) == set(LARGE_RECEIPT_TAIL_QUALIFICATIONS)
        and len(source_failed_checks) == len(LARGE_RECEIPT_TAIL_QUALIFICATIONS)
    )
    large = load_large_source()
    states = tuple(large.basis_states(1))
    if len(states) != 868:
        raise ArithmeticError(f"unexpected C=1 dimension {len(states)}")
    plaquette_rows, operator, matrix_checks = build_plaquette_source(large, states, source_receipt)
    rows: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    dependencies = {
        relative(PROTOCOL): sha256(PROTOCOL),
        relative(SOURCE): sha256(SOURCE),
        relative(INDEPENDENT_SOURCE): sha256(INDEPENDENT_SOURCE),
        relative(LARGE_SOURCE): sha256(LARGE_SOURCE),
        relative(LARGE_PROTOCOL): sha256(LARGE_PROTOCOL),
        relative(LARGE_RECOVERY_PROTOCOL): sha256(LARGE_RECOVERY_PROTOCOL),
        relative(LARGE_HELPER): sha256(LARGE_HELPER),
        relative(LARGE_RECEIPT): sha256(LARGE_RECEIPT),
    }
    checks.extend(
        [
            check("protocol_path", PROTOCOL.is_file()),
            check("source_path", relative(SOURCE) == "computations/verify_yang_mills_simultaneous_residual_gramian.py"),
            check("independent_source_path", INDEPENDENT_SOURCE.is_file()),
            check("larger_source_path", LARGE_SOURCE.is_file()),
            check(
                "larger_receipt_binding",
                source_receipt.get("status") == "PASS"
                and source_receipt.get("classification") == "PASS_RECOVERED_FINITE_CONSTRUCTION"
                and source_receipt.get("source_sha256") == sha256(LARGE_SOURCE)
                and source_receipt.get("helper_sha256") == sha256(LARGE_HELPER)
                and source_receipt.get("protocol_sha256") == sha256(LARGE_RECOVERY_PROTOCOL)
                and source_receipt.get("scientific_protocol_sha256") == sha256(LARGE_PROTOCOL)
                and source_qualification_ok,
                source_status=source_receipt.get("status"),
                source_classification=source_receipt.get("classification"),
                source_checks_passed=source_receipt.get("checks_passed"),
                source_checks_total=source_receipt.get("checks_total"),
                source_failed_checks=list(source_failed_checks),
                unresolved_tail_qualifications=list(LARGE_RECEIPT_TAIL_QUALIFICATIONS),
            ),
            check("graph_dimension", len(states) == 868),
            check(
                "plaquette_order",
                tuple(large.PLAQUETTE_NAMES)
                == ("xy_z0_0", "xy_z0_1", "xy_z1_0", "xy_z1_1", "xz_y0_0", "xz_y0_1", "xz_y1_0", "xz_y1_1", "yz_x0", "yz_x1", "yz_x2"),
            ),
            check("coupling_schedule", tuple(COUPLINGS) == (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1, 1))),
            check("weight_contract", abs(float(np.sum(WEIGHTS)) - 1.0) <= MATRIX_TOLERANCE and float(np.max(WEIGHTS)) <= 1.0 / 11.0),
            check("source_matrix_hashes", all(item["pass"] for item in matrix_checks), matrix_checks=matrix_checks),
        ]
    )
    for coupling in COUPLINGS:
        row, row_checks = build_row(large, states, plaquette_rows, operator, coupling)
        rows.append(row)
        checks.extend(row_checks)
    if len(checks) != 50:
        raise ArithmeticError(f"primary check contract changed: {len(checks)}")
    passed = all(item["passed"] for item in checks)
    source_floor_values = [row["source_floor"] for row in rows]
    record: dict[str, Any] = {
        "schema": "yang_mills_simultaneous_residual_gramian_v1",
        "status": "PASS" if passed else "FAIL",
        "classification": "QUALIFIED_FINITE_SOURCE_SECTOR_RECOVERY" if passed and min(source_floor_values) > 0.0 else "FAIL",
        "protocol": relative(PROTOCOL),
        "source": relative(SOURCE),
        "independent_source": relative(INDEPENDENT_SOURCE),
        "larger_source": relative(LARGE_SOURCE),
        "larger_protocol": relative(LARGE_PROTOCOL),
        "larger_recovery_protocol": relative(LARGE_RECOVERY_PROTOCOL),
        "larger_helper": relative(LARGE_HELPER),
        "larger_receipt": relative(LARGE_RECEIPT),
        "larger_receipt_status": source_receipt.get("status"),
        "larger_receipt_classification": source_receipt.get("classification"),
        "larger_receipt_checks_passed": source_receipt.get("checks_passed"),
        "larger_receipt_checks_total": source_receipt.get("checks_total"),
        "larger_receipt_failed_checks": list(source_failed_checks),
        "larger_receipt_tail_qualifications": list(LARGE_RECEIPT_TAIL_QUALIFICATIONS),
        "larger_receipt_qualification_passed": source_qualification_ok,
        "dependencies": dependencies,
        "graph": {
            "vertices": 12,
            "links": 20,
            "state_dimension_C1": len(states),
            "q_dimension": len(states) - 1,
        },
        "plaquette_names": list(large.PLAQUETTE_NAMES),
        "plaquette_centers": PLAQUETTE_CENTERS.tolist(),
        "couplings": [float(value) for value in COUPLINGS],
        "weights": WEIGHTS.tolist(),
        "rows": rows,
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "minimum_source_floor": min(source_floor_values),
        "maximum_source_amplification": max(row["source_amplification"] for row in rows),
        "full_q_floor_rows": [row["full_q_floor"] for row in rows],
        "full_q_nullity_rows": [row["full_q_nullity"] for row in rows],
        "continuum_claim": False,
        "thermodynamic_claim": False,
        "mass_gap_claim": False,
        "scope": "finite C=1 source-sector residual Gramian on the recovered open 3x2x2 SU(2) graph",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    record = run(args.output)
    print(
        f"status={record['status']} classification={record['classification']} "
        f"checks={record['checks_passed']}/{record['checks_total']} "
        f"minimum_source_floor={record['minimum_source_floor']:.12g}"
    )
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
