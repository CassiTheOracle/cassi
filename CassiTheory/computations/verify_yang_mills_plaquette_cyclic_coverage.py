#!/usr/bin/env python3
"""Measure finite plaquette-cyclic coverage of the centered Q sector.

Protocol:
``computations/yang-mills-plaquette-cyclic-coverage-prereg.md``.

The calculation reuses the recovered finite SU(2) Hamiltonian on the open
3x2x2 graph at C=1.  It solves each declared finite ground-state problem,
constructs the eleven normalized fundamental plaquette multiplication
operators, applies every ordered plaquette word through degree three, projects
out the vacuum, and measures the cumulative singular-value rank.  The result
is a finite operator-algebra coverage screen, not a conditional inequality or
continuum claim.
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

PROTOCOL = ROOT / "computations" / "yang-mills-plaquette-cyclic-coverage-prereg-v3.md"
SOURCE = Path(__file__).resolve()
INDEPENDENT_SOURCE = ROOT / "computations" / "verify_yang_mills_plaquette_cyclic_coverage_independent.py"
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
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_plaquette_cyclic_coverage" / "verification-v3.json"

COUPLINGS = (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1, 1))
MAX_DEGREE = 3
MATRIX_TOLERANCE = 1.0e-10
RANK_TOLERANCE = 1.0e-10
EXPECTED_WORD_COUNTS = (1, 11, 121, 1331)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def check(name: str, passed: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **details}


def load_large_source() -> Any:
    return importlib.import_module("computations.verify_yang_mills_su2_larger_volume_hamiltonian")


def as_real(value: Any, name: str) -> np.ndarray:
    array = np.asarray(value)
    imaginary = float(np.max(np.abs(array.imag))) if np.iscomplexobj(array) and array.size else 0.0
    if imaginary > MATRIX_TOLERANCE:
        raise ArithmeticError(f"{name} has imaginary residual {imaginary}")
    return np.asarray(array.real, dtype=float)


def rank_from_singular_values(singular_values: np.ndarray) -> int:
    if singular_values.size == 0:
        return 0
    scale = max(1.0, float(singular_values[0]))
    return int(np.count_nonzero(singular_values > RANK_TOLERANCE * scale))


def build_plaquette_source(
    large: Any,
    states: tuple[Any, ...],
    source_receipt: dict[str, Any],
) -> tuple[list[dict[str, Any]], Any, list[dict[str, Any]]]:
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


def cyclic_word_rows(omega: np.ndarray, operators: list[Any]) -> tuple[list[dict[str, Any]], np.ndarray]:
    """Return degree rows and the final projected ordered-word matrix."""
    dimension = int(omega.size)
    words = omega.reshape(dimension, 1)
    projected_by_degree: list[np.ndarray] = []
    rows: list[dict[str, Any]] = []

    for degree in range(MAX_DEGREE + 1):
        if degree > 0:
            words = np.column_stack([operator @ words for operator in operators])
            words = as_real(words, f"degree-{degree} word vectors")
        centered = words - omega[:, None] * (omega @ words)[None, :]
        centered = as_real(centered, f"degree-{degree} projected word vectors")
        if degree > 0:
            projected_by_degree.append(centered)
        cumulative = np.column_stack(projected_by_degree) if projected_by_degree else np.zeros((dimension, 0))
        singular_values = np.linalg.svd(cumulative, compute_uv=False) if cumulative.shape[1] else np.zeros(0)
        rank = rank_from_singular_values(singular_values)
        rows.append(
            {
                "degree": degree,
                "word_count": int(words.shape[1]),
                "cumulative_word_count": int(cumulative.shape[1]),
                "rank": rank,
                "nullity": int(dimension - 1 - rank),
                "singular_values": singular_values.tolist(),
                "minimum_retained_singular_value": (
                    float(singular_values[rank - 1]) if rank else 0.0
                ),
                "maximum_discarded_singular_value": (
                    float(singular_values[rank]) if rank < singular_values.size else 0.0
                ),
            }
        )
    final = np.column_stack(projected_by_degree)
    return rows, final


def build_row(
    large: Any,
    states: tuple[Any, ...],
    plaquette_rows: list[dict[str, Any]],
    operator: Any,
    coupling: Fraction,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    solved = large.solve_ritz(states, plaquette_rows, coupling, operator=operator)
    omega = as_real(solved["physical_vector"], "ground vector")
    dimension = len(states)
    omega_norm = float(omega @ omega)
    normalized_operators = [
        large.normalized_operator(row["matrix"], states)
        for row in plaquette_rows
    ]
    degree_rows, projected_words = cyclic_word_rows(omega, normalized_operators)
    final_rank = int(degree_rows[-1]["rank"])
    q_dimension = dimension - 1
    classification = (
        "PLAQUETTE_CYCLIC_COVERAGE_COMPLETE"
        if final_rank == q_dimension
        else "PLAQUETTE_CYCLIC_COVERAGE_INCOMPLETE"
    )
    row_key = str(coupling.numerator / coupling.denominator)
    final_singular_values = np.asarray(degree_rows[-1]["singular_values"], dtype=float)
    max_vacuum_overlap = float(np.max(np.abs(omega @ projected_words))) if projected_words.size else 0.0
    row_checks = [
        check(
            f"word_count_schedule_x{row_key}",
            tuple(item["word_count"] for item in degree_rows) == EXPECTED_WORD_COUNTS
            and tuple(item["cumulative_word_count"] for item in degree_rows)
            == (0, 11, 132, 1463),
            word_counts=[item["word_count"] for item in degree_rows],
            cumulative_word_counts=[item["cumulative_word_count"] for item in degree_rows],
        ),
        check(
            f"ground_state_q_decomposition_x{row_key}",
            np.isfinite(solved["ground_energy"])
            and np.isfinite(solved["ritz_gap"])
            and solved["ritz_gap"] > 0.0
            and solved["generalized_residual"] <= MATRIX_TOLERANCE
            and abs(omega_norm - 1.0) <= MATRIX_TOLERANCE
            and max_vacuum_overlap <= MATRIX_TOLERANCE,
            ground_energy=float(solved["ground_energy"]),
            ritz_gap=float(solved["ritz_gap"]),
            generalized_residual=float(solved["generalized_residual"]),
            omega_norm_squared=omega_norm,
            maximum_vacuum_overlap=max_vacuum_overlap,
        ),
        check(
            f"finite_word_matrix_x{row_key}",
            projected_words.shape == (dimension, 1463)
            and bool(np.isfinite(projected_words).all()),
            shape=list(projected_words.shape),
            finite=bool(np.isfinite(projected_words).all()),
        ),
        check(
            f"cumulative_rank_x{row_key}",
            all(0 <= item["rank"] <= q_dimension for item in degree_rows)
            and all(
                degree_rows[index]["rank"] <= degree_rows[index + 1]["rank"]
                for index in range(len(degree_rows) - 1)
            ),
            ranks=[item["rank"] for item in degree_rows],
            q_dimension=q_dimension,
        ),
        check(
            f"singular_values_nullity_x{row_key}",
            all(
                item["nullity"] == q_dimension - item["rank"]
                and all(
                    item["singular_values"][index] >= item["singular_values"][index + 1]
                    for index in range(len(item["singular_values"]) - 1)
                )
                for item in degree_rows
            )
            and bool(np.isfinite(final_singular_values).all()),
            nullities=[item["nullity"] for item in degree_rows],
            final_singular_value_count=int(final_singular_values.size),
        ),
        check(
            f"full_q_boundary_x{row_key}",
            q_dimension == 867
            and final_rank <= q_dimension
            and classification
            in {"PLAQUETTE_CYCLIC_COVERAGE_COMPLETE", "PLAQUETTE_CYCLIC_COVERAGE_INCOMPLETE"},
            q_dimension=q_dimension,
            final_rank=final_rank,
            finite_deficiency=q_dimension - final_rank,
            classification=classification,
        ),
    ]
    row = {
        "coupling": float(coupling),
        "dimension": dimension,
        "ground_energy": float(solved["ground_energy"]),
        "first_excited": float(solved["first_excited"]),
        "ritz_gap": float(solved["ritz_gap"]),
        "generalized_residual": float(solved["generalized_residual"]),
        "omega_norm_squared": omega_norm,
        "q_dimension": q_dimension,
        "degree_rows": degree_rows,
        "final_rank": final_rank,
        "finite_deficiency": q_dimension - final_rank,
        "classification": classification,
        "checks": row_checks,
    }
    return row, row_checks


def run(output: Path) -> dict[str, Any]:
    required = (
        PROTOCOL,
        LARGE_SOURCE,
        LARGE_PROTOCOL,
        LARGE_RECOVERY_PROTOCOL,
        LARGE_HELPER,
        LARGE_RECEIPT,
        INDEPENDENT_SOURCE,
    )
    if not all(path.is_file() for path in required):
        missing = [relative(path) for path in required if not path.is_file()]
        raise FileNotFoundError(f"missing cyclic-coverage dependency: {missing}")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")

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
    checks: list[dict[str, Any]] = [
        check("protocol_path", PROTOCOL.is_file()),
        check("source_path", relative(SOURCE) == "computations/verify_yang_mills_plaquette_cyclic_coverage.py"),
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
            "plaquette_order_and_source_hashes",
            tuple(large.PLAQUETTE_NAMES)
            == (
                "xy_z0_0", "xy_z0_1", "xy_z1_0", "xy_z1_1",
                "xz_y0_0", "xz_y0_1", "xz_y1_0", "xz_y1_1",
                "yz_x0", "yz_x1", "yz_x2",
            )
            and all(item["pass"] for item in matrix_checks),
            matrix_checks=matrix_checks,
        ),
        check(
            "coupling_and_degree_schedule",
            tuple(COUPLINGS) == (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1, 1))
            and MAX_DEGREE == 3
            and EXPECTED_WORD_COUNTS == (1, 11, 121, 1331),
            couplings=[float(value) for value in COUPLINGS],
            max_degree=MAX_DEGREE,
            expected_word_counts=list(EXPECTED_WORD_COUNTS),
        ),
    ]

    rows: list[dict[str, Any]] = []
    for coupling in COUPLINGS:
        row, row_checks = build_row(large, states, plaquette_rows, operator, coupling)
        rows.append(row)
        checks.extend(row_checks)
    if len(checks) != 32:
        raise ArithmeticError(f"primary check contract changed: {len(checks)}")

    checks_passed = all(item["passed"] for item in checks)
    complete = all(row["classification"] == "PLAQUETTE_CYCLIC_COVERAGE_COMPLETE" for row in rows)
    record: dict[str, Any] = {
        "schema": "yang_mills_plaquette_cyclic_coverage_v3",
        "status": "PASS" if checks_passed and complete else "FAIL",
        "classification": (
            "PLAQUETTE_CYCLIC_COVERAGE_COMPLETE"
            if checks_passed and complete
            else "PLAQUETTE_CYCLIC_COVERAGE_INCOMPLETE"
            if checks_passed
            else "FAIL"
        ),
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
        "couplings": [float(value) for value in COUPLINGS],
        "max_degree": MAX_DEGREE,
        "word_counts": list(EXPECTED_WORD_COUNTS),
        "rows": rows,
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "minimum_final_rank": min(row["final_rank"] for row in rows),
        "maximum_finite_deficiency": max(row["finite_deficiency"] for row in rows),
        "continuum_claim": False,
        "thermodynamic_claim": False,
        "mass_gap_claim": False,
        "scope": "finite C=1 plaquette-cyclic operator coverage through degree three on the recovered open 3x2x2 SU(2) graph",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
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
        f"minimum_final_rank={record['minimum_final_rank']} "
        f"maximum_finite_deficiency={record['maximum_finite_deficiency']}"
    )
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
