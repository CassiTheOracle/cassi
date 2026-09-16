#!/usr/bin/env python3
"""Independently verify the order-ten factorization feasibility receipt.

This verifier is deliberately self-contained.  It imports neither the
feasibility runner, ``run_cubic_lift_realization_probe``, nor
``cubic_kernel_decision``.  It rebuilds the cheap matching-factorization,
simple-formula, SHA-256-key deduplication, and modular-rank accounting from
standard-library code only.  Exact rational basis and pair profiling remain
deferred to the exact-target probe.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Iterable, Iterator, NoReturn, Sequence

ROOT = Path(__file__).resolve().parent
DEFAULT_RECEIPT = ROOT / "_diag" / "cubic_order10_feasibility_screen.json"
SOURCE_FILE = ROOT / "run_cubic_lift_realization_probe.py"
SCHEMA = "cassifi.cubic-order10-feasibility-screen.v1"
GENERATOR_SCHEMA = "cassifi.cubic-lift-realization-probe.v1"
ORDER = 10
TARGET_NULLITY = 3
MODULAR_PRIME = 1_000_003
MINIMUM_ORDER = 3
MAXIMUM_SUPPORTED_ORDER = 9
Formula = tuple[tuple[int, int, int], ...]
Matching = tuple[int, ...]


class VerificationError(ValueError):
    """Raised when a feasibility receipt or source-domain invariant is invalid."""


def fail(message: str) -> NoReturn:
    raise VerificationError(message)


def cycle_partitions(
    total: int,
    minimum_part: int = 2,
) -> Iterator[tuple[int, ...]]:
    if total == 0:
        yield ()
        return
    for part in range(minimum_part, total + 1):
        for suffix in cycle_partitions(total - part, part):
            yield (part, *suffix)


def canonical_cycle_permutation(partition: Sequence[int]) -> Matching:
    if not partition or any(part < 2 for part in partition):
        fail("invalid fixed-point-free cycle partition")
    if tuple(partition) != tuple(sorted(partition)):
        fail("cycle partition is not nondecreasing")
    result: list[int] = []
    offset = 0
    for size in partition:
        result.extend(offset + index + 1 for index in range(size - 1))
        result.append(offset)
        offset += size
    return tuple(result)


def canonical_formula(formula: Sequence[Sequence[int]]) -> Formula:
    size = len(formula)
    if size < MINIMUM_ORDER:
        fail("formula has fewer than three clauses")
    occurrences = [0] * size
    clauses: list[tuple[int, int, int]] = []
    for raw_clause in formula:
        if len(raw_clause) != 3:
            fail("formula row is not a triple")
        values: list[int] = []
        for variable in raw_clause:
            if type(variable) is not int or not 1 <= variable <= size:
                fail("formula variable is outside 1..n")
            values.append(variable)
        if len(set(values)) != 3:
            fail("formula row contains a duplicate variable")
        ordered = sorted(values)
        clause = (ordered[0], ordered[1], ordered[2])
        clauses.append(clause)
        for variable in clause:
            occurrences[variable - 1] += 1
    if any(count != 3 for count in occurrences):
        fail("formula variable occurrence count is not cubic")
    return tuple(sorted(clauses))


def formula_from_factorization(
    second: Matching,
    third: Matching,
) -> Formula:
    size = len(second)
    expected = list(range(size))
    if len(third) != size or sorted(second) != expected or sorted(third) != expected:
        fail("matching factorization is not a pair of permutations")
    if any(third[row] in (row, second[row]) for row in range(size)):
        fail("matching factorization is not edge-disjoint")
    rows = tuple(
        tuple(sorted((row + 1, second[row] + 1, third[row] + 1)))
        for row in range(size)
    )
    return canonical_formula(rows)


def formula_digest(formula: Formula) -> str:
    canonical = canonical_formula(formula)
    return hashlib.sha256(
        json.dumps(canonical, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def rank_mod_prime(formula: Formula, prime: int = MODULAR_PRIME) -> int:
    size = len(formula)
    matrix = [
        [int(column in clause) for column in range(1, size + 1)]
        for clause in formula
    ]
    pivot_row = 0
    for column in range(size):
        source = next(
            (
                row
                for row in range(pivot_row, size)
                if matrix[row][column] % prime
            ),
            None,
        )
        if source is None:
            continue
        matrix[pivot_row], matrix[source] = matrix[source], matrix[pivot_row]
        inverse = pow(matrix[pivot_row][column], -1, prime)
        for row in range(pivot_row + 1, size):
            if not matrix[row][column] % prime:
                continue
            factor = matrix[row][column] * inverse % prime
            for target in range(column, size):
                matrix[row][target] = (
                    matrix[row][target]
                    - factor * matrix[pivot_row][target]
                ) % prime
        pivot_row += 1
        if pivot_row == size:
            break
    return pivot_row


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def json_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_stream_digest(values: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.encode("ascii") + b"\n")
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")
    if not isinstance(value, dict):
        fail(f"{path}: expected a JSON object")
    return value


def sorted_hash_digest(connection: sqlite3.Connection, *, target_only: bool) -> str:
    where = " WHERE modular_target = 1" if target_only else ""
    rows = connection.execute(
        "SELECT formula_sha256 FROM formulas" + where + " ORDER BY formula_sha256"
    )
    return hash_stream_digest((row[0] for row in rows))


def rebuild_deterministic() -> dict[str, Any]:
    identity = tuple(range(ORDER))
    partitions = tuple(cycle_partitions(ORDER))
    modular_histogram: Counter[int] = Counter()
    partition_rows: list[dict[str, Any]] = []
    permutations_scanned = 0
    legal_factorizations = 0
    distinct_clause_factorizations = 0

    with tempfile.TemporaryDirectory(prefix="cassi-order10-verify-") as temporary:
        database_path = Path(temporary) / "formula-digests.sqlite3"
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute("PRAGMA temp_store=FILE")
            connection.execute(
                "CREATE TABLE formulas ("
                "formula_sha256 TEXT PRIMARY KEY, "
                "modular_rank INTEGER NOT NULL DEFAULT -1, "
                "modular_target INTEGER NOT NULL DEFAULT 0"
                ")"
            )
            connection.commit()

            for partition in partitions:
                second = canonical_cycle_permutation(partition)
                partition_scanned = 0
                partition_legal = 0
                partition_distinct = 0
                partition_new_count = 0
                partition_target_count = 0
                partition_rank_histogram: Counter[int] = Counter()
                partition_formula_stream = hashlib.sha256()
                partition_target_stream = hashlib.sha256()
                for third in itertools.permutations(identity):
                    permutations_scanned += 1
                    partition_scanned += 1
                    if any(
                        third[row] in (row, second[row]) for row in range(ORDER)
                    ):
                        continue
                    legal_factorizations += 1
                    partition_legal += 1
                    formula = formula_from_factorization(second, third)
                    if len(set(formula)) != ORDER:
                        continue
                    distinct_clause_factorizations += 1
                    partition_distinct += 1
                    formula_sha256 = formula_digest(formula)
                    inserted = connection.execute(
                        "INSERT OR IGNORE INTO formulas(formula_sha256) VALUES (?)",
                        (formula_sha256,),
                    ).rowcount
                    if inserted != 1:
                        continue
                    rank = rank_mod_prime(formula)
                    modular_target = int(rank <= ORDER - TARGET_NULLITY)
                    connection.execute(
                        "UPDATE formulas SET modular_rank = ?, modular_target = ? "
                        "WHERE formula_sha256 = ?",
                        (rank, modular_target, formula_sha256),
                    )
                    partition_new_count += 1
                    partition_formula_stream.update(
                        formula_sha256.encode("ascii") + b"\n"
                    )
                    partition_rank_histogram[rank] += 1
                    modular_histogram[rank] += 1
                    if modular_target:
                        partition_target_count += 1
                        partition_target_stream.update(
                            formula_sha256.encode("ascii") + b"\n"
                        )
                connection.commit()
                partition_rows.append(
                    {
                        "cycle_partition": list(partition),
                        "third_permutations_scanned": partition_scanned,
                        "legal_factorizations": partition_legal,
                        "distinct_clause_factorizations": partition_distinct,
                        "new_unique_formula_count": partition_new_count,
                        "new_modular_target_count": partition_target_count,
                        "new_unique_formula_hash_stream_sha256": partition_formula_stream.hexdigest(),
                        "new_modular_target_hash_stream_sha256": partition_target_stream.hexdigest(),
                        "new_modular_rank_histogram": {
                            str(rank): partition_rank_histogram[rank]
                            for rank in sorted(partition_rank_histogram)
                        },
                    }
                )
            unique_formula_count = connection.execute(
                "SELECT COUNT(*) FROM formulas"
            ).fetchone()[0]
            modular_target_count = connection.execute(
                "SELECT COUNT(*) FROM formulas WHERE modular_target = 1"
            ).fetchone()[0]
            formula_hash_stream_sha256 = sorted_hash_digest(
                connection, target_only=False
            )
            modular_target_hash_stream_sha256 = sorted_hash_digest(
                connection, target_only=True
            )
        finally:
            connection.close()

    census = {
        "cycle_type_count": len(partitions),
        "third_permutations_scanned": permutations_scanned,
        "legal_factorizations": legal_factorizations,
        "distinct_clause_factorizations": distinct_clause_factorizations,
        "duplicate_row_sorted_factorizations": (
            distinct_clause_factorizations - unique_formula_count
        ),
        "unique_row_sorted_formulas": unique_formula_count,
        "formula_hash_stream_sha256": formula_hash_stream_sha256,
        "modular_rank_histogram": {
            str(rank): modular_histogram[rank]
            for rank in sorted(modular_histogram)
        },
        "modular_target_candidates": modular_target_count,
        "modular_target_hash_stream_sha256": modular_target_hash_stream_sha256,
        "rational_rank_measured": False,
        "exact_basis_profiles_measured": False,
        "exact_pair_profiles_measured": False,
    }
    domain = {
        "order": ORDER,
        "target_nullity": TARGET_NULLITY,
        "minimum_order": MINIMUM_ORDER,
        "source_maximum_supported_order": MAXIMUM_SUPPORTED_ORDER,
        "generator": (
            "fix the first perfect matching to identity, choose the canonical fixed-point-free cycle representative for the second, and enumerate every third permutation disjoint from both"
        ),
        "simple_formula_rule": (
            "each clause has three distinct variables, every variable occurs three times, and all clause triples are distinct"
        ),
        "screen_rule": (
            "count every source-domain permutation/legal factorization/distinct formula and compute modular rank for each globally new simple formula; do not run rational nullity or exact basis/pair profiling"
        ),
        "storage_rule": (
            "retain only formula SHA-256 keys and modular-rank flags in a temporary on-disk SQLite index; do not retain formula tuples or per-partition formula lists"
        ),
        "stopping_rule": "complete the declared order-ten source domain; no early stopping",
    }
    assessment = {
        "status": "complete",
        "result": "order10_generation_complete_exact_profile_deferred",
        "scope": (
            "Complete order-ten canonical matching-factorization generation and modular-rank screen only; no exact rational nullity, basis, or exclusive-pair claim is made."
        ),
        "next_decision": (
            "review measured generation counts, modular-target count, runtime, temporary storage, and peak working set before scheduling exact profiling"
        ),
    }
    return {
        "schema": SCHEMA,
        "source": {
            "generator_file": SOURCE_FILE.name,
            "generator_file_sha256": sha256_file(SOURCE_FILE),
            "generator_schema": GENERATOR_SCHEMA,
        },
        "domain": domain,
        "partitions": partition_rows,
        "census": census,
        "assessment": assessment,
    }


def verify_receipt_object(
    actual: dict[str, Any],
    expected: dict[str, Any],
    source_path: str | Path = SOURCE_FILE,
) -> dict[str, Any]:
    if actual.get("schema") != SCHEMA:
        fail("receipt schema mismatch")
    measurement = actual.get("measurement")
    if not isinstance(measurement, dict):
        fail("receipt measurement is missing")
    elapsed = measurement.get("elapsed_seconds")
    peak = measurement.get("peak_working_set_bytes")
    storage = measurement.get("temporary_storage_bytes")
    if (
        type(elapsed) not in (int, float)
        or elapsed <= 0
        or (peak is not None and (type(peak) is not int or peak <= 0))
        or type(storage) is not int
        or storage <= 0
        or measurement.get("storage_deleted_after_receipt") is not True
    ):
        fail("receipt measurement is invalid")
    if actual.get("deterministic_receipt_sha256") != json_digest(expected):
        fail("deterministic receipt digest mismatch")
    deterministic_actual = {
        key: value
        for key, value in actual.items()
        if key not in {"measurement", "deterministic_receipt_sha256"}
    }
    if deterministic_actual != expected:
        fail("receipt mismatch")
    if expected["source"]["generator_file_sha256"] != sha256_file(Path(source_path)):
        fail("source generator digest mismatch")
    return {
        "status": "verified",
        "schema": SCHEMA,
        "result": expected["assessment"]["result"],
        "memory_measurement_status": "available" if peak is not None else "unavailable",
        **expected["census"],
        "elapsed_seconds": elapsed,
        "peak_working_set_bytes": peak,
        "temporary_storage_bytes": storage,
    }


def verify(
    path: str | Path = DEFAULT_RECEIPT,
    source_path: str | Path = SOURCE_FILE,
) -> dict[str, Any]:
    actual = load_json(Path(path))
    expected = rebuild_deterministic()
    return verify_receipt_object(actual, expected, source_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--source", default=str(SOURCE_FILE))
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.receipt, arguments.source), sort_keys=True))


if __name__ == "__main__":
    main()
