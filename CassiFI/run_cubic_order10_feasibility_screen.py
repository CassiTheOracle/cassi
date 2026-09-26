#!/usr/bin/env python3
"""Measure the complete order-ten cubic factorization cover without exact profiling.

This is a feasibility screen, not an order-ten width-barrier result. It reuses
the canonical matching-factorization generator from
``run_cubic_lift_realization_probe`` and records actual permutation, legal-
factorization, distinct-formula, and modular-rank counts. Rational nullity,
exact basis, and pair profiling are deliberately deferred until the measured
cost is reviewed.

Unique formulas are indexed by SHA-256 in a temporary on-disk SQLite table.
The screen therefore has bounded Python memory and never retains the full
formula population or per-partition formula lists in RAM.
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

import run_cubic_lift_realization_probe as source

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "_diag" / "cubic_order10_feasibility_screen.json"
SOURCE_FILE = ROOT / "run_cubic_lift_realization_probe.py"
SCHEMA = "cassifi.cubic-order10-feasibility-screen.v1"
ORDER = 10
TARGET_NULLITY = 3


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


def sqlite_directory_size(path: Path) -> int:
    return sum(
        child.stat().st_size
        for child in path.rglob("*")
        if child.is_file()
    )


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
            process = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(
                process,
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


def sorted_hash_digest(connection: sqlite3.Connection, *, target_only: bool) -> str:
    where = " WHERE modular_target = 1" if target_only else ""
    rows = connection.execute(
        "SELECT formula_sha256 FROM formulas" + where + " ORDER BY formula_sha256"
    )
    return hash_stream_digest((row[0] for row in rows))


def run_screen() -> dict[str, Any]:
    identity = tuple(range(ORDER))
    partitions = tuple(source.cycle_partitions(ORDER))
    modular_histogram: Counter[int] = Counter()
    partition_rows: list[dict[str, Any]] = []
    permutations_scanned = 0
    legal_factorizations = 0
    distinct_clause_factorizations = 0
    started = time.perf_counter()
    unique_formula_count = 0
    modular_target_count = 0
    formula_hash_stream_sha256 = ""
    modular_target_hash_stream_sha256 = ""
    temporary_storage_bytes = 0

    with tempfile.TemporaryDirectory(prefix="cassi-order10-screen-") as temporary:
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
                second = source.canonical_cycle_permutation(partition)
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
                    formula = source.formula_from_factorization(second, third)
                    if len(set(formula)) != ORDER:
                        continue
                    distinct_clause_factorizations += 1
                    partition_distinct += 1
                    formula_sha256 = source.formula_digest(formula)
                    inserted = connection.execute(
                        "INSERT OR IGNORE INTO formulas(formula_sha256) VALUES (?)",
                        (formula_sha256,),
                    ).rowcount
                    if inserted != 1:
                        continue
                    rank = source.rank_mod_prime(formula)
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
                temporary_storage_bytes = sqlite_directory_size(Path(temporary))
        finally:
            connection.close()

    elapsed_seconds = time.perf_counter() - started
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
        "minimum_order": source.MINIMUM_ORDER,
        "source_maximum_supported_order": source.MAXIMUM_SUPPORTED_ORDER,
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
    deterministic = {
        "schema": SCHEMA,
        "source": {
            "generator_file": SOURCE_FILE.name,
            "generator_file_sha256": sha256_file(SOURCE_FILE),
            "generator_schema": source.SCHEMA,
        },
        "domain": domain,
        "partitions": partition_rows,
        "census": census,
        "assessment": assessment,
    }
    return {
        **deterministic,
        "measurement": {
            "elapsed_seconds": round(elapsed_seconds, 6),
            "peak_working_set_bytes": peak_working_set_bytes(),
            "temporary_storage_bytes": temporary_storage_bytes,
            "storage_deleted_after_receipt": True,
        },
        "deterministic_receipt_sha256": json_digest(deterministic),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    receipt = run_screen()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt["census"], indent=2, sort_keys=True))
    print(json.dumps(receipt["measurement"], indent=2, sort_keys=True))
    print(f"wrote {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
