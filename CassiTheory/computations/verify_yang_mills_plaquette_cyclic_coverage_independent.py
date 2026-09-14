#!/usr/bin/env python3
"""Audit the serialized plaquette-cyclic coverage receipt independently.

This verifier intentionally does not import the primary implementation.  It
reconstructs the declared word-count, rank, singular-value, nullity and
finite-classification arithmetic from the primary JSON receipt.  It is an
arithmetic receipt audit, not a second Hamiltonian reconstruction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-plaquette-cyclic-coverage-prereg-v3.md"
SOURCE = Path(__file__).resolve()
PRIMARY_SOURCE = ROOT / "computations" / "verify_yang_mills_plaquette_cyclic_coverage.py"
PRIMARY_RECEIPT = ROOT / "runs" / "yang_mills_plaquette_cyclic_coverage" / "verification-v3.json"
LARGE_SOURCE = ROOT / "computations" / "verify_yang_mills_su2_larger_volume_hamiltonian.py"
LARGE_RECEIPT = ROOT / "runs" / "yang_mills_su2_larger_volume_hamiltonian_recovery" / "current-verification.json"
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_plaquette_cyclic_coverage" / "verification-independent-v3.json"

COUPLINGS = (1.0 / 64.0, 1.0 / 16.0, 1.0 / 4.0, 1.0)
MAX_DEGREE = 3
EXPECTED_WORD_COUNTS = (1, 11, 121, 1331)
EXPECTED_CUMULATIVE_WORD_COUNTS = (0, 11, 132, 1463)
Q_DIMENSION = 867
RANK_TOLERANCE = 1.0e-10
TOLERANCE = 1.0e-12


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def check(name: str, passed: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **details}


def rank_from_singular_values(values: list[float]) -> int:
    singular_values = np.asarray(values, dtype=float)
    if singular_values.size == 0:
        return 0
    scale = max(1.0, float(singular_values[0]))
    return int(np.count_nonzero(singular_values > RANK_TOLERANCE * scale))


def close(actual: float, expected: float) -> bool:
    return abs(float(actual) - float(expected)) <= TOLERANCE * max(1.0, abs(float(expected)))


def run(primary_path: Path, output: Path) -> dict[str, Any]:
    if not PROTOCOL.is_file() or not PRIMARY_SOURCE.is_file() or not primary_path.is_file():
        raise FileNotFoundError("missing cyclic protocol, primary source, or primary receipt")
    if not LARGE_SOURCE.is_file() or not LARGE_RECEIPT.is_file():
        raise FileNotFoundError("missing larger-volume source or qualified source receipt")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    rows = primary.get("rows", [])
    dependencies = primary.get("dependencies", {})
    checks: list[dict[str, Any]] = [
        check("protocol_path", PROTOCOL.is_file()),
        check("primary_source_path", PRIMARY_SOURCE.is_file()),
        check("primary_receipt_path", primary_path.is_file()),
        check("larger_receipt_path", LARGE_RECEIPT.is_file()),
        check(
            "primary_receipt_status",
            primary.get("schema") == "yang_mills_plaquette_cyclic_coverage_v3"
            and primary.get("status")
            == (
                "PASS"
                if primary.get("classification") == "PLAQUETTE_CYCLIC_COVERAGE_COMPLETE"
                else "FAIL"
            )
            and primary.get("classification")
            in {
                "PLAQUETTE_CYCLIC_COVERAGE_COMPLETE",
                "PLAQUETTE_CYCLIC_COVERAGE_INCOMPLETE",
            }
            and primary.get("checks_passed") == 32
            and primary.get("checks_total") == 32
            and all(item.get("passed") is True for item in primary.get("checks", [])),
            schema=primary.get("schema"),
            status=primary.get("status"),
            checks_passed=primary.get("checks_passed"),
            checks_total=primary.get("checks_total"),
        ),
        check(
            "primary_source_binding",
            dependencies.get(relative(PRIMARY_SOURCE)) == sha256(PRIMARY_SOURCE),
            recorded=dependencies.get(relative(PRIMARY_SOURCE)),
            observed=sha256(PRIMARY_SOURCE),
        ),
        check(
            "protocol_binding",
            dependencies.get(relative(PROTOCOL)) == sha256(PROTOCOL),
            recorded=dependencies.get(relative(PROTOCOL)),
            observed=sha256(PROTOCOL),
        ),
        check(
            "schedule_binding",
            tuple(primary.get("couplings", [])) == COUPLINGS
            and primary.get("max_degree") == MAX_DEGREE
            and tuple(primary.get("word_counts", [])) == EXPECTED_WORD_COUNTS
            and primary.get("graph", {}).get("q_dimension") == Q_DIMENSION,
            couplings=primary.get("couplings"),
            max_degree=primary.get("max_degree"),
            word_counts=primary.get("word_counts"),
            q_dimension=primary.get("graph", {}).get("q_dimension"),
        ),
    ]

    row_checks: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        degree_rows = row.get("degree_rows", [])
        ranks = [int(item.get("rank", -1)) for item in degree_rows]
        nullities = [int(item.get("nullity", -1)) for item in degree_rows]
        singular_values = [item.get("singular_values", []) for item in degree_rows]
        word_counts = [int(item.get("word_count", -1)) for item in degree_rows]
        cumulative_counts = [int(item.get("cumulative_word_count", -1)) for item in degree_rows]
        final_rank = int(row.get("final_rank", -1))
        deficiency = int(row.get("finite_deficiency", -1))
        row_key = row.get("coupling", index)
        row_checks.extend(
            [
                check(
                    f"word_count_rank_arithmetic_row_{index}",
                    len(degree_rows) == MAX_DEGREE + 1
                    and tuple(word_counts) == EXPECTED_WORD_COUNTS
                    and tuple(cumulative_counts) == EXPECTED_CUMULATIVE_WORD_COUNTS
                    and ranks == sorted(ranks)
                    and all(0 <= rank <= Q_DIMENSION for rank in ranks)
                    and final_rank == ranks[-1]
                    and deficiency == Q_DIMENSION - final_rank,
                    coupling=row_key,
                    word_counts=word_counts,
                    cumulative_word_counts=cumulative_counts,
                    ranks=ranks,
                    final_rank=final_rank,
                    deficiency=deficiency,
                ),
                check(
                    f"singular_value_nullity_arithmetic_row_{index}",
                    len(degree_rows) == MAX_DEGREE + 1
                    and all(
                        nullities[degree] == Q_DIMENSION - ranks[degree]
                        and all(
                            np.isfinite(np.asarray(singular_values[degree], dtype=float))
                        )
                        and all(
                            singular_values[degree][position]
                            >= singular_values[degree][position + 1]
                            for position in range(len(singular_values[degree]) - 1)
                        )
                        and rank_from_singular_values(singular_values[degree]) == ranks[degree]
                        for degree in range(len(degree_rows))
                    ),
                    coupling=row_key,
                    nullities=nullities,
                    singular_value_counts=[len(values) for values in singular_values],
                ),
                check(
                    f"classification_arithmetic_row_{index}",
                    row.get("q_dimension") == Q_DIMENSION
                    and row.get("classification")
                    == (
                        "PLAQUETTE_CYCLIC_COVERAGE_COMPLETE"
                        if final_rank == Q_DIMENSION
                        else "PLAQUETTE_CYCLIC_COVERAGE_INCOMPLETE"
                    )
                    and row.get("classification") in {
                        "PLAQUETTE_CYCLIC_COVERAGE_COMPLETE",
                        "PLAQUETTE_CYCLIC_COVERAGE_INCOMPLETE",
                    },
                    coupling=row_key,
                    q_dimension=row.get("q_dimension"),
                    final_rank=final_rank,
                    classification=row.get("classification"),
                ),
            ]
        )
    checks.extend(row_checks)
    if len(checks) != 20:
        raise ArithmeticError(f"independent check contract changed: {len(checks)}")

    passed = all(item["passed"] for item in checks)
    primary_classification = primary.get("classification")
    record: dict[str, Any] = {
        "schema": "yang_mills_plaquette_cyclic_coverage_independent_v1",
        "status": "PASS" if passed else "FAIL",
        "classification": "PRIMARY_RECEIPT_CYCLIC_RANK_AUDIT_PASS" if passed else "FAIL",
        "primary_classification": primary_classification,
        "protocol": relative(PROTOCOL),
        "source": relative(SOURCE),
        "primary_source": relative(PRIMARY_SOURCE),
        "primary_receipt": relative(primary_path),
        "larger_source": relative(LARGE_SOURCE),
        "larger_receipt": relative(LARGE_RECEIPT),
        "dependencies": {
            relative(PROTOCOL): sha256(PROTOCOL),
            relative(SOURCE): sha256(SOURCE),
            relative(PRIMARY_SOURCE): sha256(PRIMARY_SOURCE),
            relative(primary_path): sha256(primary_path),
            relative(LARGE_SOURCE): sha256(LARGE_SOURCE),
            relative(LARGE_RECEIPT): sha256(LARGE_RECEIPT),
        },
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "scope": "independent arithmetic audit of the finite plaquette-cyclic coverage receipt; no second Hamiltonian solve",
        "continuum_claim": False,
        "thermodynamic_claim": False,
        "mass_gap_claim": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, default=PRIMARY_RECEIPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    record = run(args.primary, args.output)
    print(
        f"status={record['status']} classification={record['classification']} "
        f"checks={record['checks_passed']}/{record['checks_total']} "
        f"primary_classification={record['primary_classification']}"
    )
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
