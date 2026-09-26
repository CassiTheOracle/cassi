#!/usr/bin/env python3
"""Audit the serialized repeated-edge Wilson coverage receipt independently."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import computations.verify_yang_mills_su2_larger_volume_hamiltonian as large

PROTOCOL = ROOT / "computations" / "yang-mills-closed-wilson-repeated-edge-coverage-prereg.md"
SOURCE = Path(__file__).resolve()
PRIMARY_SOURCE = ROOT / "computations" / "verify_yang_mills_closed_wilson_repeated_edge_coverage.py"
PRIMARY_RECEIPT = ROOT / "runs" / "yang_mills_closed_wilson_repeated_edge_coverage" / "verification.json"
LARGE_SOURCE = ROOT / "computations" / "verify_yang_mills_su2_larger_volume_hamiltonian.py"
LARGE_RECEIPT = ROOT / "runs" / "yang_mills_su2_larger_volume_hamiltonian_recovery" / "current-verification.json"
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_closed_wilson_repeated_edge_coverage" / "verification-independent.json"

COUPLINGS = (1.0 / 64.0, 1.0 / 16.0, 1.0 / 4.0, 1.0)
EXPECTED_DECLARED_RAW_COUNTS = {"4": 88, "6": 432, "8": 1944, "10": 1680, "12": 528}
EXPECTED_LENGTH_COUNTS = {"4": 11, "6": 36, "8": 127, "10": 84, "12": 22}
EXPECTED_ENUMERATED_RAW_COUNTS = {"4": 88, "6": 432, "8": 1944, "10": 11760, "12": 66136}
EXPECTED_SIMPLE_RAW_COUNTS = {"4": 88, "6": 432, "8": 1152, "10": 1680, "12": 528}
EXPECTED_REPEATED_RAW_LENGTH8 = 792
EXPECTED_REPEATED_COUNT = 55
EXPECTED_SIMPLE_COUNT = 225
EXPECTED_FAMILY_COUNT = 280
EXPECTED_PLAQUETTE_COUNTS = (11, 121, 1331, 14641)
EXPECTED_BLOCK_NAMES = ("closed_wilson", "plaquette_degree_1", "plaquette_degree_2", "plaquette_degree_3", "plaquette_degree_4")
EXPECTED_BLOCK_COUNTS = (280, 11, 121, 1331, 14641)
EXPECTED_CUMULATIVE_COUNTS = (280, 291, 412, 1743, 16384)
Q_DIMENSION = 867
RANK_TOLERANCE = 1.0e-10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def check(name: str, passed: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **details}


def inverse(term: tuple[int, int]) -> tuple[int, int]:
    return term[0], -term[1]


def rotations(word: Sequence[tuple[int, int]]) -> list[tuple[tuple[int, int], ...]]:
    return [tuple(word[index:]) + tuple(word[:index]) for index in range(len(word))]


def reverse_word(word: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    return tuple((edge, -orientation) for edge, orientation in reversed(word))


def canonical_word(word: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    forward = tuple(word)
    return min(rotations(forward) + rotations(reverse_word(forward)))


def word_is_simple(word: Sequence[tuple[int, int]]) -> bool:
    return (
        len(set(edge for edge, _ in word)) == len(word)
        and len({vertex for edge, _ in word for vertex in (large.LINK_TAILS[edge], large.LINK_HEADS[edge])}) == len(word)
    )


def enumerate_inventory() -> tuple[dict[int, int], dict[int, int], dict[int, set[tuple[tuple[int, int], ...]]], dict[int, set[tuple[tuple[int, int], ...]]]]:
    adjacency: dict[int, list[tuple[int, int, int]]] = {vertex: [] for vertex in range(len(large.VERTEX_COORDS))}
    for edge, (tail, head) in enumerate(zip(large.LINK_TAILS, large.LINK_HEADS)):
        adjacency[tail].append((head, edge, +1))
        adjacency[head].append((tail, edge, -1))
    for vertex in adjacency:
        adjacency[vertex].sort(key=lambda item: (item[0], item[1], item[2]))
    lengths = (4, 6, 8, 10, 12)
    raw_counts: dict[int, int] = {}
    simple_raw_counts: dict[int, int] = {}
    canonical: dict[int, set[tuple[tuple[int, int], ...]]] = {length: set() for length in lengths}
    simple_canonical: dict[int, set[tuple[tuple[int, int], ...]]] = {length: set() for length in lengths}
    for length in lengths:
        raw = 0
        simple_raw = 0

        def extend(root: int, current: int, word: tuple[tuple[int, int], ...]) -> None:
            nonlocal raw, simple_raw
            if len(word) == length:
                if current == root and word[-1] != inverse(word[0]):
                    raw += 1
                    key = canonical_word(word)
                    canonical[length].add(key)
                    if word_is_simple(word):
                        simple_raw += 1
                        simple_canonical[length].add(key)
                return
            for next_vertex, edge, orientation in adjacency[current]:
                term = (edge, orientation)
                if word and term == inverse(word[-1]):
                    continue
                extend(root, next_vertex, word + (term,))

        for root in adjacency:
            extend(root, root, ())
        raw_counts[length] = raw
        simple_raw_counts[length] = simple_raw
    return raw_counts, simple_raw_counts, canonical, simple_canonical


def rank_from_singular_values(values: list[float]) -> int:
    singular_values = np.asarray(values, dtype=float)
    if singular_values.size == 0:
        return 0
    scale = float(singular_values[0])
    if scale <= 0.0:
        return 0
    return int(np.count_nonzero(singular_values > RANK_TOLERANCE * scale))


def run(primary_path: Path, output: Path) -> dict[str, Any]:
    if not PROTOCOL.is_file() or not PRIMARY_SOURCE.is_file() or not primary_path.is_file():
        raise FileNotFoundError("missing repeated-edge protocol, primary source, or primary receipt")
    if not LARGE_SOURCE.is_file() or not LARGE_RECEIPT.is_file():
        raise FileNotFoundError("missing larger-volume source or qualified source receipt")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    rows = primary.get("rows", [])
    dependencies = primary.get("dependencies", {})
    inventory = primary.get("cycle_inventory", {})
    raw_counts, simple_raw_counts, canonical_by_length, simple_canonical_by_length = enumerate_inventory()
    family_sets = {
        4: canonical_by_length[4],
        6: canonical_by_length[6],
        8: canonical_by_length[8],
        10: simple_canonical_by_length[10],
        12: simple_canonical_by_length[12],
    }
    family_words = tuple(sorted(set().union(*family_sets.values()), key=lambda word: (len(word), word)))
    family_serialized = [[[edge, orientation] for edge, orientation in word] for word in family_words]
    repeated_words = tuple(word for word in family_words if word not in set().union(*simple_canonical_by_length.values()))
    expected_status = "PASS" if primary.get("classification") == "REPEATED_EDGE_CLOSED_WILSON_COVERAGE_COMPLETE" else "FAIL"
    checks: list[dict[str, Any]] = [
        check("protocol_path", PROTOCOL.is_file()),
        check("primary_source_path", PRIMARY_SOURCE.is_file()),
        check("primary_receipt_path", primary_path.is_file()),
        check("larger_receipt_path", LARGE_RECEIPT.is_file()),
        check(
            "primary_receipt_status",
            primary.get("schema") == "yang_mills_closed_wilson_repeated_edge_coverage_v1"
            and primary.get("status") == expected_status
            and primary.get("classification") in {"REPEATED_EDGE_CLOSED_WILSON_COVERAGE_COMPLETE", "REPEATED_EDGE_CLOSED_WILSON_COVERAGE_INCOMPLETE"}
            and primary.get("checks_passed") == 41
            and primary.get("checks_total") == 41
            and all(item.get("passed") is True for item in primary.get("checks", [])),
            schema=primary.get("schema"), status=primary.get("status"), classification=primary.get("classification"), checks_passed=primary.get("checks_passed"), checks_total=primary.get("checks_total"),
        ),
        check("primary_source_binding", dependencies.get(relative(PRIMARY_SOURCE)) == sha256(PRIMARY_SOURCE), recorded=dependencies.get(relative(PRIMARY_SOURCE)), observed=sha256(PRIMARY_SOURCE)),
        check("protocol_binding", dependencies.get(relative(PROTOCOL)) == sha256(PROTOCOL), recorded=dependencies.get(relative(PROTOCOL)), observed=sha256(PROTOCOL)),
        check(
            "inventory_and_schedule_binding",
            tuple(primary.get("couplings", [])) == COUPLINGS
            and inventory.get("raw_directed_occurrences_by_length") == EXPECTED_DECLARED_RAW_COUNTS
            and inventory.get("enumerated_raw_directed_occurrences_by_length") == {str(key): value for key, value in sorted(raw_counts.items())}
            and inventory.get("simple_raw_directed_occurrences_by_length") == {str(key): value for key, value in sorted(simple_raw_counts.items())}
            and inventory.get("canonical_count") == EXPECTED_FAMILY_COUNT
            and inventory.get("length_counts") == EXPECTED_LENGTH_COUNTS
            and inventory.get("repeated_edge_length8_raw_directed_occurrences") == EXPECTED_REPEATED_RAW_LENGTH8
            and inventory.get("repeated_edge_length8_count") == EXPECTED_REPEATED_COUNT
            and inventory.get("simple_count") == EXPECTED_SIMPLE_COUNT
            and inventory.get("words") == family_serialized
            and tuple(primary.get("plaquette_counts", [])) == EXPECTED_PLAQUETTE_COUNTS
            and primary.get("projected_column_count") == EXPECTED_CUMULATIVE_COUNTS[-1]
            and primary.get("graph", {}).get("q_dimension") == Q_DIMENSION,
            couplings=primary.get("couplings"), raw_counts=inventory.get("raw_directed_occurrences_by_length"), canonical_count=inventory.get("canonical_count"), length_counts=inventory.get("length_counts"), repeated_count=inventory.get("repeated_edge_length8_count"), plaquette_counts=primary.get("plaquette_counts"), projected_column_count=primary.get("projected_column_count"), q_dimension=primary.get("graph", {}).get("q_dimension"), reconstructed_family_count=len(family_words), reconstructed_repeated_count=len(repeated_words),
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
        first_full = next((name for name, rank in zip(block_names, ranks) if rank == Q_DIMENSION), None)
        row_checks.extend([
            check(f"family_block_rank_arithmetic_row_{index}", tuple(block_names) == EXPECTED_BLOCK_NAMES and tuple(block_counts) == EXPECTED_BLOCK_COUNTS and tuple(cumulative_counts) == EXPECTED_CUMULATIVE_COUNTS and ranks == sorted(ranks) and all(0 <= rank <= Q_DIMENSION for rank in ranks) and final_rank == ranks[-1] and deficiency == Q_DIMENSION - final_rank, coupling=row.get("coupling", index), block_names=block_names, block_counts=block_counts, cumulative_counts=cumulative_counts, ranks=ranks, final_rank=final_rank, deficiency=deficiency),
            check(f"singular_value_nullity_arithmetic_row_{index}", len(family_blocks) == len(EXPECTED_BLOCK_NAMES) and all(nullities[block] == Q_DIMENSION - ranks[block] and all(np.isfinite(np.asarray(singular_values[block], dtype=float))) and all(singular_values[block][position] >= singular_values[block][position + 1] for position in range(len(singular_values[block]) - 1)) and rank_from_singular_values(singular_values[block]) == ranks[block] for block in range(len(family_blocks))), coupling=row.get("coupling", index), nullities=nullities, singular_value_counts=[len(values) for values in singular_values]),
            check(f"augmented_schedule_arithmetic_row_{index}", row.get("q_dimension") == Q_DIMENSION and row.get("closed_wilson_column_count") == EXPECTED_FAMILY_COUNT and tuple(row.get("plaquette_block_counts", [])) == EXPECTED_PLAQUETTE_COUNTS and row.get("augmented_column_count") == EXPECTED_CUMULATIVE_COUNTS[-1] and sum(EXPECTED_BLOCK_COUNTS) == EXPECTED_CUMULATIVE_COUNTS[-1], coupling=row.get("coupling", index), closed_wilson_column_count=row.get("closed_wilson_column_count"), plaquette_block_counts=row.get("plaquette_block_counts"), augmented_column_count=row.get("augmented_column_count")),
            check(f"classification_arithmetic_row_{index}", row.get("first_full_block") == first_full and row.get("classification") == ("REPEATED_EDGE_CLOSED_WILSON_COVERAGE_COMPLETE" if final_rank == Q_DIMENSION else "REPEATED_EDGE_CLOSED_WILSON_COVERAGE_INCOMPLETE") and row.get("classification") in {"REPEATED_EDGE_CLOSED_WILSON_COVERAGE_COMPLETE", "REPEATED_EDGE_CLOSED_WILSON_COVERAGE_INCOMPLETE"}, coupling=row.get("coupling", index), first_full_block=row.get("first_full_block"), expected_first_full_block=first_full, final_rank=final_rank, classification=row.get("classification")),
        ])
    checks.extend(row_checks)
    if len(checks) != 24:
        raise ArithmeticError(f"independent check contract changed: {len(checks)}")
    passed = all(item["passed"] for item in checks)
    primary_classification = primary.get("classification")
    record: dict[str, Any] = {
        "schema": "yang_mills_closed_wilson_repeated_edge_coverage_independent_v1",
        "status": "PASS" if passed else "FAIL",
        "classification": "PRIMARY_RECEIPT_REPEATED_EDGE_RANK_AUDIT_PASS" if passed else "FAIL",
        "primary_classification": primary_classification,
        "protocol": relative(PROTOCOL), "source": relative(SOURCE), "primary_source": relative(PRIMARY_SOURCE), "primary_receipt": relative(primary_path), "larger_source": relative(LARGE_SOURCE), "larger_receipt": relative(LARGE_RECEIPT),
        "dependencies": {relative(PROTOCOL): sha256(PROTOCOL), relative(SOURCE): sha256(SOURCE), relative(PRIMARY_SOURCE): sha256(PRIMARY_SOURCE), relative(primary_path): sha256(primary_path), relative(LARGE_SOURCE): sha256(LARGE_SOURCE), relative(LARGE_RECEIPT): sha256(LARGE_RECEIPT)},
        "checks": checks, "checks_passed": sum(item["passed"] for item in checks), "checks_total": len(checks), "scope": "independent arithmetic audit of the finite repeated-edge closed-Wilson plus degree-four coverage receipt; no second Hamiltonian solve", "continuum_claim": False, "thermodynamic_claim": False, "mass_gap_claim": False,
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
    print(f"status={record['status']} classification={record['classification']} checks={record['checks_passed']}/{record['checks_total']}")
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
