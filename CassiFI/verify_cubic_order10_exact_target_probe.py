#!/usr/bin/env python3
"""Independently verify the complete order-ten exact-target receipt.

The verifier imports neither the exact-target runner nor the production
matching-cover module.  It uses the separate rational implementation in
``verify_cubic_lift_realization_probe`` and reconstructs the full order-ten
stream, modular filter, exact basis profiles, pair profiles, aggregate counts,
and every target row from scratch.
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
from typing import Any, Iterable, NoReturn

import verify_cubic_lift_realization_probe as independent

ROOT = Path(__file__).resolve().parent
DEFAULT_FEASIBILITY = ROOT / "_diag" / "cubic_order10_feasibility_screen.json"
DEFAULT_RECEIPT = ROOT / "_diag" / "cubic_order10_exact_target_probe.json"
SOURCE_FILE = ROOT / "run_cubic_lift_realization_probe.py"
SCHEMA = "cassifi.cubic-order10-exact-target-probe.v1"
FEASIBILITY_SCHEMA = "cassifi.cubic-order10-feasibility-screen.v1"
ORDER = 10
TARGET_NULLITY = 3
PAIR_KEYS = (
    "pair_cases_checked",
    "exclusive_pairs",
    "rank_below_two_distinct",
    "rank_below_two_identical",
    "rank_two_identical",
    "eligible_pairs",
    "two_sided_width_barriers",
)
CATEGORY_KEYS = {
    "rank_below_two_distinct",
    "rank_below_two_identical",
    "rank_two_identical",
    "eligible",
}

VerificationError = independent.VerificationError


def fail(message: str) -> NoReturn:
    raise VerificationError(message)


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


def sorted_hash_digest(
    connection: sqlite3.Connection,
    *,
    target_only: bool,
) -> str:
    where = " WHERE modular_target = 1" if target_only else ""
    rows = connection.execute(
        "SELECT formula_sha256 FROM formulas" + where + " ORDER BY formula_sha256"
    )
    return hash_stream_digest((row[0] for row in rows))


def analyze_target(
    formula_sha256: str,
    formula: independent.Formula,
    first_factorization: dict[str, Any],
    modular_rank: int,
) -> dict[str, Any]:
    canonical = independent.canonical(formula)
    basis_census, vectors, basis_rows = independent.basis_profile(canonical)
    exact_nullity = int(basis_census["nullity"])
    connected = independent.incidence_connected(canonical)
    pair_profile = (
        independent.pair_profile(canonical, vectors, basis_rows)
        if connected and exact_nullity >= TARGET_NULLITY
        else None
    )
    if exact_nullity < TARGET_NULLITY:
        status = "modular_false_positive"
    elif not connected:
        status = "exact_target_disconnected"
    else:
        status = "exact_target_connected"
    return {
        "formula_sha256": formula_sha256,
        "formula": [list(clause) for clause in canonical],
        "first_factorization": first_factorization,
        "modular_rank": modular_rank,
        "rank": basis_census["rank"],
        "nullity": exact_nullity,
        "connected": connected,
        "status": status,
        "basis_census": basis_census,
        "pair_profile": pair_profile,
    }


def rebuild_deterministic(
    feasibility: dict[str, Any],
    feasibility_path: Path,
    source_path: Path,
) -> dict[str, Any]:
    if feasibility.get("schema") != FEASIBILITY_SCHEMA:
        fail("feasibility receipt schema mismatch")
    if feasibility.get("assessment", {}).get("status") != "complete":
        fail("feasibility receipt is not complete")
    identity = tuple(range(ORDER))
    partitions = tuple(independent.cycle_partitions(ORDER))
    modular_histogram: Counter[int] = Counter()
    partition_rows: list[dict[str, Any]] = []
    candidates: dict[str, dict[str, Any]] = {}
    permutations_scanned = 0
    legal_factorizations = 0
    distinct_clause_factorizations = 0

    with tempfile.TemporaryDirectory(prefix="cassi-order10-exact-verify-") as temporary:
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
                second = independent.canonical_cycle_permutation(partition)
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
                    formula = independent.formula_from_factorization(second, third)
                    if len(set(formula)) != ORDER:
                        continue
                    distinct_clause_factorizations += 1
                    partition_distinct += 1
                    formula_sha256 = independent.formula_digest(formula)
                    inserted = connection.execute(
                        "INSERT OR IGNORE INTO formulas(formula_sha256) VALUES (?)",
                        (formula_sha256,),
                    ).rowcount
                    if inserted != 1:
                        continue
                    modular_rank = independent.rank_mod_prime(formula)
                    modular_target = int(modular_rank <= ORDER - TARGET_NULLITY)
                    connection.execute(
                        "UPDATE formulas SET modular_rank = ?, modular_target = ? "
                        "WHERE formula_sha256 = ?",
                        (modular_rank, modular_target, formula_sha256),
                    )
                    partition_new_count += 1
                    partition_formula_stream.update(
                        formula_sha256.encode("ascii") + b"\n"
                    )
                    partition_rank_histogram[modular_rank] += 1
                    modular_histogram[modular_rank] += 1
                    if modular_target:
                        partition_target_count += 1
                        partition_target_stream.update(
                            formula_sha256.encode("ascii") + b"\n"
                        )
                        candidates[formula_sha256] = analyze_target(
                            formula_sha256,
                            formula,
                            {
                                "cycle_partition": list(partition),
                                "identity_matching": list(range(1, ORDER + 1)),
                                "second_matching": [value + 1 for value in second],
                                "third_matching": [value + 1 for value in third],
                            },
                            modular_rank,
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

    candidate_rows = [candidates[key] for key in sorted(candidates)]
    status_histogram = Counter(row["status"] for row in candidate_rows)
    exact_target_rows = [
        row
        for row in candidate_rows
        if row["status"] in {"exact_target_connected", "exact_target_disconnected"}
    ]
    connected_rows = [
        row for row in candidate_rows if row["status"] == "exact_target_connected"
    ]
    pair_profiles = [row["pair_profile"] for row in connected_rows]
    pair_summary = {
        key: sum(profile["counts"][key] for profile in pair_profiles)
        for key in PAIR_KEYS
    }
    eligible_rows = [
        row
        for row in connected_rows
        if row["pair_profile"]["counts"]["eligible_pairs"] > 0
    ]
    exact_nullity_histogram = Counter(str(row["nullity"]) for row in exact_target_rows)
    category_histogram = Counter(
        category
        for profile in pair_profiles
        for category, count in profile["counts"].items()
        if category in CATEGORY_KEYS
        for _ in range(count)
    )
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
        "exact_target_count": len(exact_target_rows),
        "modular_false_positive_count": status_histogram["modular_false_positive"],
        "exact_nullity_histogram": {
            key: exact_nullity_histogram[key]
            for key in sorted(exact_nullity_histogram)
        },
        "connected_exact_target_count": len(connected_rows),
        "disconnected_exact_target_count": status_histogram[
            "exact_target_disconnected"
        ],
        "pair_profiled_exact_target_count": len(connected_rows),
        "pair_category_histogram": dict(sorted(category_histogram.items())),
        "pair_summary": pair_summary,
        "nondegenerate_exclusive_target_count": pair_summary["eligible_pairs"],
        "targets_with_nondegenerate_exclusive_pair": len(eligible_rows),
        "all_modular_targets_exactly_profiled": len(candidate_rows)
        == modular_target_count,
        "all_connected_exact_targets_pair_checked": len(connected_rows)
        == len(pair_profiles),
        "exact_target_is_modular_superset_check": all(
            row["nullity"] >= TARGET_NULLITY for row in exact_target_rows
        ),
    }
    domain = {
        "order": ORDER,
        "target_nullity": TARGET_NULLITY,
        "modular_rank_threshold": ORDER - TARGET_NULLITY,
        "modular_prime": independent.MODULAR_PRIME,
        "generator": (
            "fix the first perfect matching to identity, choose the canonical fixed-point-free cycle representative for the second, and enumerate every third permutation disjoint from both"
        ),
        "screen_rule": (
            "profile every globally new simple formula whose rank modulo the declared prime is at most seven; exact rational rank is computed for every retained modular target"
        ),
        "exact_profile_rule": (
            "enumerate every original kernel-coordinate ground basis, record exact coefficient width, and check every variable pair for the two-sided width-two barrier when exact nullity is at least three and incidence is connected"
        ),
        "coverage_lemma": (
            "if rational rank is at most seven, every 8-by-8 minor vanishes over the integers, so modular rank is at most seven; the modular target set is a sound superset of all exact nullity-at-least-three formulas"
        ),
        "storage_rule": (
            "retain only formula SHA-256 keys and modular-rank flags in temporary on-disk SQLite; retain exact profiles only for the 64 measured modular targets"
        ),
        "stopping_rule": "complete the declared order-ten source domain; no early stopping",
    }
    source = {
        "feasibility_receipt_file": feasibility_path.name,
        "feasibility_receipt_file_sha256": sha256_file(feasibility_path),
        "feasibility_receipt_canonical_digest": json_digest(feasibility),
        "feasibility_schema": feasibility["schema"],
        "generator_file": source_path.name,
        "generator_file_sha256": sha256_file(source_path),
        "generator_schema": independent.SCHEMA,
    }
    assessment_result = (
        "order10_nondegenerate_exclusive_pair_found"
        if census["nondegenerate_exclusive_target_count"]
        else "order10_no_nondegenerate_exclusive_pair"
    )
    assessment = {
        "status": "complete",
        "result": assessment_result,
        "scope": (
            "Complete order-ten canonical matching-factorization cover, with exact rational basis and pair profiling for every modular target; no claim beyond order ten is made."
        ),
        "bounded_conclusion": (
            "A nondegenerate exclusive pair occurs in the complete order-ten cover."
            if census["nondegenerate_exclusive_target_count"]
            else "No nondegenerate exclusive pair occurs in the complete order-ten cover."
        ),
        "next_decision": (
            "promote the witness to an independently checked exact certificate"
            if census["nondegenerate_exclusive_target_count"]
            else "either prove the degeneracy mechanism preserves under quotienting and extension, or search the next order with the same modular-target screen"
        ),
    }
    deterministic = {
        "schema": SCHEMA,
        "domain": domain,
        "source": source,
        "partitions": partition_rows,
        "census": census,
        "assessment": assessment,
        "targets": candidate_rows,
    }
    return deterministic


def verify_receipt_object(
    actual: dict[str, Any],
    expected: dict[str, Any],
    source_path: str | Path = SOURCE_FILE,
) -> dict[str, Any]:
    if actual.get("schema") != SCHEMA:
        fail("exact-target receipt schema mismatch")
    measurement = actual.get("measurement")
    if not isinstance(measurement, dict):
        fail("exact-target receipt measurement is missing")
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
        fail("exact-target receipt measurement is invalid")
    if actual.get("deterministic_receipt_sha256") != json_digest(expected):
        fail("exact-target deterministic digest mismatch")
    deterministic_actual = {
        key: value
        for key, value in actual.items()
        if key not in {"measurement", "deterministic_receipt_sha256"}
    }
    if deterministic_actual != expected:
        fail("exact-target receipt mismatch")
    if expected["source"]["generator_file_sha256"] != sha256_file(Path(source_path)):
        fail("exact-target source generator digest mismatch")
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
    receipt_path: str | Path = DEFAULT_RECEIPT,
    feasibility_path: str | Path = DEFAULT_FEASIBILITY,
    source_path: str | Path = SOURCE_FILE,
) -> dict[str, Any]:
    receipt_file = Path(receipt_path)
    feasibility_file = Path(feasibility_path)
    source_file = Path(source_path)
    actual = load_json(receipt_file)
    feasibility = load_json(feasibility_file)
    expected = rebuild_deterministic(feasibility, feasibility_file, source_file)
    return verify_receipt_object(actual, expected, source_file)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--feasibility-receipt", default=str(DEFAULT_FEASIBILITY))
    parser.add_argument("--source", default=str(SOURCE_FILE))
    arguments = parser.parse_args()
    print(
        json.dumps(
            verify(
                arguments.receipt,
                arguments.feasibility_receipt,
                arguments.source,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
