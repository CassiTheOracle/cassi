#!/usr/bin/env python3
"""Audit the serialized simple-cycle coverage receipt independently.

The audit does not import the primary implementation or reconstruct Hamiltonian
matrices.  It checks the canonical cycle inventory, finite column schedule,
singular-value rank arithmetic, nullities and classification from the JSON
receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-closed-wilson-simple-cycle-coverage-prereg.md"
SOURCE = Path(__file__).resolve()
PRIMARY_SOURCE = ROOT / "computations" / "verify_yang_mills_closed_wilson_simple_cycle_coverage.py"
V4_SOURCE = ROOT / "computations" / "verify_yang_mills_plaquette_cyclic_coverage_v4.py"
V4_PROTOCOL = ROOT / "computations" / "yang-mills-plaquette-cyclic-coverage-prereg-v4.md"
PRIMARY_RECEIPT = ROOT / "runs" / "yang_mills_closed_wilson_simple_cycle_coverage" / "verification.json"
LARGE_SOURCE = ROOT / "computations" / "verify_yang_mills_su2_larger_volume_hamiltonian.py"
LARGE_RECEIPT = ROOT / "runs" / "yang_mills_su2_larger_volume_hamiltonian_recovery" / "current-verification.json"
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_closed_wilson_simple_cycle_coverage" / "verification-independent.json"

COUPLINGS = (1.0 / 64.0, 1.0 / 16.0, 1.0 / 4.0, 1.0)
MAX_DEGREE = 4
EXPECTED_RAW_CYCLES = 3880
EXPECTED_CYCLE_COUNT = 225
EXPECTED_LENGTH_COUNTS = {"4": 11, "6": 36, "8": 72, "10": 84, "12": 22}
EXPECTED_PLAQUETTE_COUNTS = (11, 121, 1331, 14641)
EXPECTED_BLOCK_NAMES = (
    "simple_cycles",
    "plaquette_degree_1",
    "plaquette_degree_2",
    "plaquette_degree_3",
    "plaquette_degree_4",
)
EXPECTED_BLOCK_COUNTS = (225, 11, 121, 1331, 14641)
EXPECTED_CUMULATIVE_COUNTS = (225, 236, 357, 1688, 16329)
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


def run(primary_path: Path, output: Path) -> dict[str, Any]:
    if not PROTOCOL.is_file() or not PRIMARY_SOURCE.is_file() or not primary_path.is_file():
        raise FileNotFoundError("missing simple-cycle protocol, primary source, or primary receipt")
    if not V4_SOURCE.is_file() or not V4_PROTOCOL.is_file():
        raise FileNotFoundError("missing degree-four lineage source or protocol")
    if not LARGE_SOURCE.is_file() or not LARGE_RECEIPT.is_file():
        raise FileNotFoundError("missing larger-volume source or qualified source receipt")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    rows = primary.get("rows", [])
    dependencies = primary.get("dependencies", {})
    inventory = primary.get("cycle_inventory", {})
    checks: list[dict[str, Any]] = [
        check("protocol_path", PROTOCOL.is_file()),
        check("primary_source_path", PRIMARY_SOURCE.is_file()),
        check("primary_receipt_path", primary_path.is_file()),
        check("larger_receipt_path", LARGE_RECEIPT.is_file()),
        check(
            "primary_receipt_status",
            primary.get("schema") == "yang_mills_closed_wilson_simple_cycle_coverage_v1"
            and primary.get("status")
            == (
                "PASS"
                if primary.get("classification") == "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_COMPLETE"
                else "FAIL"
            )
            and primary.get("classification")
            in {
                "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_COMPLETE",
                "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_INCOMPLETE",
            }
            and primary.get("checks_passed") == 40
            and primary.get("checks_total") == 40
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
            "inventory_and_schedule_binding",
            tuple(primary.get("couplings", [])) == COUPLINGS
            and inventory.get("raw_directed_occurrences") == EXPECTED_RAW_CYCLES
            and inventory.get("canonical_count") == EXPECTED_CYCLE_COUNT
            and inventory.get("length_counts") == EXPECTED_LENGTH_COUNTS
            and tuple(primary.get("plaquette_counts", [])) == EXPECTED_PLAQUETTE_COUNTS
            and primary.get("projected_column_count") == EXPECTED_CUMULATIVE_COUNTS[-1]
            and primary.get("graph", {}).get("q_dimension") == Q_DIMENSION,
            couplings=primary.get("couplings"),
            raw_directed_occurrences=inventory.get("raw_directed_occurrences"),
            canonical_count=inventory.get("canonical_count"),
            length_counts=inventory.get("length_counts"),
            plaquette_counts=primary.get("plaquette_counts"),
            projected_column_count=primary.get("projected_column_count"),
            q_dimension=primary.get("graph", {}).get("q_dimension"),
        ),
    ]

    row_checks: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        family_blocks = row.get("family_blocks", [])
        block_names = [item.get("block") for item in family_blocks]
        block_counts = [int(item.get("block_column_count", -1)) for item in family_blocks]
        cumulative_counts = [int(item.get("cumulative_column_count", -1)) for item in family_blocks]
        ranks = [int(item.get("rank", -1)) for item in family_blocks]
        nullities = [int(item.get("nullity", -1)) for item in family_blocks]
        singular_values = [item.get("singular_values", []) for item in family_blocks]
        final_rank = int(row.get("final_rank", -1))
        deficiency = int(row.get("finite_deficiency", -1))
        first_full = next(
            (name for name, rank in zip(block_names, ranks) if rank == Q_DIMENSION),
            None,
        )
        row_checks.extend(
            [
                check(
                    f"family_block_rank_arithmetic_row_{index}",
                    tuple(block_names) == EXPECTED_BLOCK_NAMES
                    and tuple(block_counts) == EXPECTED_BLOCK_COUNTS
                    and tuple(cumulative_counts) == EXPECTED_CUMULATIVE_COUNTS
                    and ranks == sorted(ranks)
                    and all(0 <= rank <= Q_DIMENSION for rank in ranks)
                    and final_rank == ranks[-1]
                    and deficiency == Q_DIMENSION - final_rank,
                    coupling=row.get("coupling", index),
                    block_names=block_names,
                    block_counts=block_counts,
                    cumulative_counts=cumulative_counts,
                    ranks=ranks,
                    final_rank=final_rank,
                    deficiency=deficiency,
                ),
                check(
                    f"singular_value_nullity_arithmetic_row_{index}",
                    len(family_blocks) == len(EXPECTED_BLOCK_NAMES)
                    and all(
                        nullities[block] == Q_DIMENSION - ranks[block]
                        and all(np.isfinite(np.asarray(singular_values[block], dtype=float)))
                        and all(
                            singular_values[block][position]
                            >= singular_values[block][position + 1]
                            for position in range(len(singular_values[block]) - 1)
                        )
                        and rank_from_singular_values(singular_values[block]) == ranks[block]
                        for block in range(len(family_blocks))
                    ),
                    coupling=row.get("coupling", index),
                    nullities=nullities,
                    singular_value_counts=[len(values) for values in singular_values],
                ),
                check(
                    f"augmented_schedule_arithmetic_row_{index}",
                    row.get("q_dimension") == Q_DIMENSION
                    and row.get("simple_cycle_column_count") == EXPECTED_CYCLE_COUNT
                    and tuple(row.get("plaquette_block_counts", [])) == EXPECTED_PLAQUETTE_COUNTS
                    and row.get("augmented_column_count") == EXPECTED_CUMULATIVE_COUNTS[-1]
                    and sum(EXPECTED_BLOCK_COUNTS) == EXPECTED_CUMULATIVE_COUNTS[-1],
                    coupling=row.get("coupling", index),
                    simple_cycle_column_count=row.get("simple_cycle_column_count"),
                    plaquette_block_counts=row.get("plaquette_block_counts"),
                    augmented_column_count=row.get("augmented_column_count"),
                ),
                check(
                    f"classification_arithmetic_row_{index}",
                    row.get("first_full_block") == first_full
                    and row.get("classification")
                    == (
                        "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_COMPLETE"
                        if final_rank == Q_DIMENSION
                        else "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_INCOMPLETE"
                    )
                    and row.get("classification")
                    in {
                        "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_COMPLETE",
                        "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_INCOMPLETE",
                    },
                    coupling=row.get("coupling", index),
                    first_full_block=row.get("first_full_block"),
                    expected_first_full_block=first_full,
                    final_rank=final_rank,
                    classification=row.get("classification"),
                ),
            ]
        )
    checks.extend(row_checks)
    if len(checks) != 24:
        raise ArithmeticError(f"independent check contract changed: {len(checks)}")

    passed = all(item["passed"] for item in checks)
    primary_classification = primary.get("classification")
    record: dict[str, Any] = {
        "schema": "yang_mills_closed_wilson_simple_cycle_coverage_independent_v1",
        "status": "PASS" if passed else "FAIL",
        "classification": "PRIMARY_RECEIPT_SIMPLE_CYCLE_RANK_AUDIT_PASS" if passed else "FAIL",
        "primary_classification": primary_classification,
        "protocol": relative(PROTOCOL),
        "source": relative(SOURCE),
        "primary_source": relative(PRIMARY_SOURCE),
        "degree_four_source": relative(V4_SOURCE),
        "degree_four_protocol": relative(V4_PROTOCOL),
        "primary_receipt": relative(primary_path),
        "larger_source": relative(LARGE_SOURCE),
        "larger_receipt": relative(LARGE_RECEIPT),
        "dependencies": {
            relative(PROTOCOL): sha256(PROTOCOL),
            relative(SOURCE): sha256(SOURCE),
            relative(PRIMARY_SOURCE): sha256(PRIMARY_SOURCE),
            relative(V4_SOURCE): sha256(V4_SOURCE),
            relative(V4_PROTOCOL): sha256(V4_PROTOCOL),
            relative(primary_path): sha256(primary_path),
            relative(LARGE_SOURCE): sha256(LARGE_SOURCE),
            relative(LARGE_RECEIPT): sha256(LARGE_RECEIPT),
        },
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "scope": "independent arithmetic audit of the finite simple-cycle plus degree-four plaquette coverage receipt; no second Hamiltonian solve",
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
