#!/usr/bin/env python3
"""Exactly profile every modular target in the complete order-ten cover.

The preceding feasibility screen enumerates every order-ten canonical
matching-factorization and retains only formula SHA-256 keys in temporary
on-disk SQLite storage.  This pass repeats that complete source-domain stream,
computes exact rational basis profiles only for globally new formulas whose
modular rank is at most seven, and checks every exclusive pair for each exact
nullity-three target.  The modular filter is a sound superset because rank
modulo a prime cannot exceed the rational rank.
"""

from __future__ import annotations

import argparse
from collections import Counter
import ctypes
from ctypes import wintypes
import hashlib
import itertools
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Any, Iterable

import run_cubic_lift_realization_probe as lift

ROOT = Path(__file__).resolve().parent
DEFAULT_FEASIBILITY = ROOT / "_diag" / "cubic_order10_feasibility_screen.json"
DEFAULT_OUTPUT = ROOT / "_diag" / "cubic_order10_exact_target_probe.json"
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
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def peak_working_set_bytes() -> int | None:
    if os.name == "nt":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(ProcessMemoryCounters),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            if psapi.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(),
                ctypes.byref(counters),
                counters.cb,
            ):
                return int(counters.PeakWorkingSetSize)
        except (AttributeError, OSError):
            return None
        return None
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(usage * (1024 if usage < 10**9 else 1))
    except (ImportError, AttributeError):
        return None


def sqlite_directory_size(path: Path) -> int:
    return sum(
        child.stat().st_size
        for child in path.rglob("*")
        if child.is_file()
    )


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
    formula: lift.Formula,
    first_factorization: dict[str, Any],
    modular_rank: int,
) -> dict[str, Any]:
    canonical = lift.production.canonical_cubic_formula(formula)
    basis_census, vectors, basis_rows = lift.basis_profile(canonical)
    exact_nullity = int(basis_census["nullity"])
    connected = lift.production.incidence_connected(canonical)
    pair_profile = (
        lift.pair_profile(canonical, vectors, basis_rows)
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


def run_probe(feasibility: dict[str, Any], feasibility_path: Path) -> dict[str, Any]:
    if feasibility.get("schema") != FEASIBILITY_SCHEMA:
        raise ValueError("unexpected feasibility receipt schema")
    if feasibility.get("assessment", {}).get("status") != "complete":
        raise ValueError("feasibility receipt is not complete")
    if feasibility.get("census", {}).get("rational_rank_measured") is not False:
        raise ValueError("feasibility receipt is not a modular-only screen")

    identity = tuple(range(ORDER))
    partitions = tuple(lift.cycle_partitions(ORDER))
    modular_histogram: Counter[int] = Counter()
    partition_rows: list[dict[str, Any]] = []
    candidates: dict[str, dict[str, Any]] = {}
    permutations_scanned = 0
    legal_factorizations = 0
    distinct_clause_factorizations = 0
    started = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="cassi-order10-exact-") as temporary:
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
                second = lift.canonical_cycle_permutation(partition)
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
                    formula = lift.formula_from_factorization(second, third)
                    if len(set(formula)) != ORDER:
                        continue
                    distinct_clause_factorizations += 1
                    partition_distinct += 1
                    formula_sha256 = lift.formula_digest(formula)
                    inserted = connection.execute(
                        "INSERT OR IGNORE INTO formulas(formula_sha256) VALUES (?)",
                        (formula_sha256,),
                    ).rowcount
                    if inserted != 1:
                        continue
                    modular_rank = lift.rank_mod_prime(formula)
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
            temporary_storage_bytes = sqlite_directory_size(Path(temporary))
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
    category_keys = {
        "rank_below_two_distinct",
        "rank_below_two_identical",
        "rank_two_identical",
        "eligible",
    }
    category_histogram = Counter(
        category
        for profile in pair_profiles
        for category, count in profile["counts"].items()
        if category in category_keys
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
        "modular_prime": lift.MODULAR_PRIME,
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
        "generator_file": SOURCE_FILE.name,
        "generator_file_sha256": sha256_file(SOURCE_FILE),
        "generator_schema": lift.SCHEMA,
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
    return {
        **deterministic,
        "measurement": {
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "peak_working_set_bytes": peak_working_set_bytes(),
            "temporary_storage_bytes": temporary_storage_bytes,
            "storage_deleted_after_receipt": True,
        },
        "deterministic_receipt_sha256": json_digest(deterministic),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feasibility-receipt", type=Path, default=DEFAULT_FEASIBILITY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    receipt = run_probe(
        load_json(arguments.feasibility_receipt), arguments.feasibility_receipt
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt["census"], indent=2, sort_keys=True))
    print(json.dumps(receipt["assessment"], indent=2, sort_keys=True))
    print(json.dumps(receipt["measurement"], indent=2, sort_keys=True))
    print(f"wrote {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
