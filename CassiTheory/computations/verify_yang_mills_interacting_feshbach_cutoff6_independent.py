#!/usr/bin/env python3
"""Audit the cutoff-six Feshbach receipt without assembling matrices."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations/yang-mills-interacting-feshbach-cutoff6-prereg.md"
PRIMARY_SOURCE = ROOT / "computations/verify_yang_mills_interacting_feshbach_cutoff6.py"
REFERENCE = ROOT / "computations/verify_yang_mills_exact_block_spectrum.py"
PREDECESSOR_SOURCE = ROOT / "computations/verify_yang_mills_interacting_feshbach_cutoff_screen.py"
PREDECESSOR_RECEIPT = ROOT / "runs/yang_mills_interacting_feshbach_cutoff/verification.json"
PRIMARY = ROOT / "runs/yang_mills_interacting_feshbach_cutoff6/verification.json"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_interacting_feshbach_cutoff6/verification-independent.json"

CUTOFFS = (1, 2, 3, 4, 5, 6)
CUTOFF_PAIRS = tuple(
    (inner, outer)
    for outer in CUTOFFS[1:]
    for inner in CUTOFFS[:outer - 1]
)
COUPLINGS = ("1/4", "1", "4", "16")
EXPECTED_DIMENSIONS = {1: 4, 2: 11, 3: 23, 4: 42, 5: 69, 6: 106}
TOLERANCE = 1.0e-10


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual: float, expected: float) -> bool:
    return abs(float(actual) - float(expected)) <= TOLERANCE * max(
        1.0, abs(float(actual)), abs(float(expected))
    )


def record_check(result: dict[str, Any], name: str, passed: bool, detail: Any) -> None:
    result["checks"].append({"name": name, "passed": bool(passed), "detail": detail})
    if not passed:
        result["failures"].append(name)


def expected_family_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for coupling in COUPLINGS:
        selected = [row for row in rows if row.get("coupling") == coupling]
        roots = [row["certified_gap_lower_bound"] for row in selected
                 if row["certified_gap_lower_bound"] is not None]
        ratios = [row["root_to_gap_ratio"] for row in selected
                  if row["root_to_gap_ratio"] is not None]
        summary[coupling] = {
            "rows": len(selected),
            "min_certified_root": min(roots) if roots else None,
            "min_root_to_gap_ratio": min(ratios) if ratios else None,
            "min_self_energy_ratio_at_zero": min(row["self_energy_ratio_at_zero"] for row in selected),
            "max_self_energy_ratio_at_zero": max(row["self_energy_ratio_at_zero"] for row in selected),
        }
    return summary


def expected_adjacent_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [row for row in rows if row["outer_cutoff"] == row["inner_cutoff"] + 1]
    roots = [row["certified_gap_lower_bound"] for row in selected
             if row["certified_gap_lower_bound"] is not None]
    ratios = [row["root_to_gap_ratio"] for row in selected
              if row["root_to_gap_ratio"] is not None]
    return {
        "rows": len(selected),
        "positive_certified_rows": len(roots),
        "min_certified_root": min(roots) if roots else None,
        "min_root_to_gap_ratio": min(ratios) if ratios else None,
        "max_self_energy_ratio_at_zero": max(row["self_energy_ratio_at_zero"] for row in selected),
    }


def audit() -> dict[str, Any]:
    primary = json.loads(PRIMARY.read_text(encoding="utf-8"))
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.interacting-feshbach-cutoff6.independent.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(), "sha256": digest(PROTOCOL)},
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(SOURCE)},
            "primary_source": {"path": PRIMARY_SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(PRIMARY_SOURCE)},
            "reference": {"path": REFERENCE.relative_to(ROOT).as_posix(), "sha256": digest(REFERENCE)},
            "predecessor_source": {"path": PREDECESSOR_SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(PREDECESSOR_SOURCE)},
            "predecessor_receipt": {"path": PREDECESSOR_RECEIPT.relative_to(ROOT).as_posix(), "sha256": digest(PREDECESSOR_RECEIPT)},
            "primary_receipt": {"path": PRIMARY.relative_to(ROOT).as_posix(), "sha256": digest(PRIMARY)},
        },
        "checks": [],
        "failures": [],
    }
    source_record = primary.get("sources", {})
    record_check(
        result,
        "primary status and complete checks",
        primary.get("status") == "PASS"
        and primary.get("failures") == []
        and primary.get("summary", {}).get("rows") == 60
        and primary.get("summary", {}).get("checks") == 603
        and primary.get("summary", {}).get("passing_checks") == 603
        and primary.get("summary", {}).get("adjacent_rows") == 20,
        {"status": primary.get("status"), "summary": primary.get("summary")},
    )
    expected_bindings = {
        "protocol": PROTOCOL,
        "source": PRIMARY_SOURCE,
        "independent_source": SOURCE,
        "reference": REFERENCE,
        "predecessor_source": PREDECESSOR_SOURCE,
        "predecessor_receipt": PREDECESSOR_RECEIPT,
    }
    for key, path in expected_bindings.items():
        record_check(
            result,
            f"primary {key} binding",
            source_record.get(key, {}).get("sha256") == digest(path),
            {"recorded": source_record.get(key, {}).get("sha256"), "computed": digest(path)},
        )
    record_check(
        result,
        "fixed family schedule",
        primary.get("schedule") == {
            "cutoffs": list(CUTOFFS),
            "cutoff_pairs": [list(pair) for pair in CUTOFF_PAIRS],
            "couplings": list(COUPLINGS),
            "expected_dimensions": {str(key): value for key, value in EXPECTED_DIMENSIONS.items()},
            "adjacent_pairs": [[cutoff - 1, cutoff] for cutoff in CUTOFFS[1:]],
        },
        primary.get("schedule"),
    )

    rows = primary.get("rows", [])
    adjacent_rows = [row for row in rows if row.get("outer_cutoff") == row.get("inner_cutoff") + 1]
    positive_adjacent = [row for row in adjacent_rows
                         if row.get("certified_gap_lower_bound") is not None
                         and row["certified_gap_lower_bound"] > 0.0]
    expected_classification = (
        "SUPPORTS_FINITE_ADJACENT_FAMILY"
        if len(positive_adjacent) == len(adjacent_rows)
        else "NO_POSITIVE_ADJACENT_FAMILY_CERTIFICATE"
    )
    record_check(
        result,
        "primary scientific classification",
        primary.get("classification") == expected_classification,
        {"recorded": primary.get("classification"), "recomputed": expected_classification},
    )
    seen: set[tuple[int, int, str]] = set()
    for row in rows:
        inner = int(row["inner_cutoff"])
        outer = int(row["outer_cutoff"])
        coupling = str(row["coupling"])
        label = f"cP={inner},cQ={outer},x={coupling}"
        seen.add((inner, outer, coupling))
        expected_p = EXPECTED_DIMENSIONS.get(inner)
        expected_q = EXPECTED_DIMENSIONS.get(outer)
        alpha = float(row["alpha_retained"])
        delta = float(row["delta_discarded"])
        beta = float(row["beta_coupling"])
        lam = float(row["lambda_test"])
        gap = float(row["finite_gap"])
        resolvent_bound = 1.0 / (delta - lam)
        self_energy_bound = beta * beta / (delta - lam)
        phi_test = alpha - lam - self_energy_bound
        phi_zero = alpha - beta * beta / delta
        discriminant = (alpha - delta) ** 2 + 4.0 * beta * beta
        root = 0.5 * (alpha + delta - math.sqrt(discriminant)) if phi_zero > 0.0 else None
        record_check(result, f"{label}:dimensions and ranks",
                     expected_p is not None and expected_q is not None
                     and row["full_dimension"] == expected_q
                     and row["retained_dimension"] == expected_p
                     and row["discarded_dimension"] == expected_q - 1 - expected_p,
                     {key: row.get(key) for key in ("full_dimension", "retained_dimension", "discarded_dimension")})
        record_check(result, f"{label}:resolvent arithmetic",
                     float(row["resolvent_norm"]) <= resolvent_bound * (1.0 + TOLERANCE),
                     {"actual": row["resolvent_norm"], "recomputed_bound": resolvent_bound})
        record_check(result, f"{label}:self-energy arithmetic",
                     float(row["self_energy_norm"]) <= self_energy_bound * (1.0 + TOLERANCE),
                     {"actual": row["self_energy_norm"], "recomputed_bound": self_energy_bound})
        record_check(result, f"{label}:Schur scalar reconstruction",
                     close(row["phi_test"], phi_test)
                     and close(row["phi_zero"], phi_zero),
                     {"recorded_phi_test": row["phi_test"], "recomputed_phi_test": phi_test,
                      "recorded_phi_zero": row["phi_zero"], "recomputed_phi_zero": phi_zero})
        record_check(result, f"{label}:root reconstruction",
                     (root is None and row["certified_gap_lower_bound"] is None)
                     or (root is not None and row["certified_gap_lower_bound"] is not None
                         and close(row["certified_gap_lower_bound"], root)),
                     {"recorded": row["certified_gap_lower_bound"], "recomputed": root})
        expected_ratio = None if root is None else root / gap
        record_check(result, f"{label}:root-to-gap reconstruction",
                     (expected_ratio is None and row["root_to_gap_ratio"] is None)
                     or (expected_ratio is not None and close(row["root_to_gap_ratio"], expected_ratio)),
                     {"recorded": row["root_to_gap_ratio"], "recomputed": expected_ratio})
        record_check(result, f"{label}:gap ordering",
                     root is None or gap + TOLERANCE >= root,
                     {"gap": gap, "root": root})
        record_check(result, f"{label}:tail-floor guard",
                     row["tail_floor_resolvent_defined"] is False
                     and float(row["tail_floor_distance"]) == 0.0,
                     {"distance": row["tail_floor_distance"],
                      "resolvent_defined": row["tail_floor_resolvent_defined"]})
        record_check(result, f"{label}:matrix hash format",
                     isinstance(row.get("outer_matrix_sha256"), str)
                     and len(row["outer_matrix_sha256"]) == 64,
                     {"outer_matrix_sha256": row.get("outer_matrix_sha256")})

    expected_keys = {(inner, outer, coupling)
                     for inner, outer in CUTOFF_PAIRS for coupling in COUPLINGS}
    grouped = expected_family_summary(rows)
    record_check(result, "row schedule and family summary",
                 len(rows) == 60 and seen == expected_keys
                 and primary.get("family_summary") is not None
                 and all(primary["family_summary"].get(coupling, {}).get("rows") == 15
                         for coupling in COUPLINGS),
                 {"row_count": len(rows), "seen_count": len(seen), "summary": primary.get("family_summary")})
    recorded_summary = primary.get("family_summary", {})
    summary_matches = True
    for coupling in COUPLINGS:
        recorded = recorded_summary.get(coupling, {})
        expected = grouped[coupling]
        summary_matches = summary_matches and recorded.get("rows") == expected["rows"]
        for key in ("min_certified_root", "min_root_to_gap_ratio",
                    "min_self_energy_ratio_at_zero", "max_self_energy_ratio_at_zero"):
            left, right = recorded.get(key), expected[key]
            summary_matches = summary_matches and (
                (left is None and right is None)
                or (left is not None and right is not None and close(left, right))
            )
    record_check(result, "family summary arithmetic", summary_matches,
                 {"recorded": recorded_summary, "recomputed": grouped})
    expected_adjacent = expected_adjacent_summary(rows)
    recorded_adjacent = primary.get("adjacent_family_summary", {})
    adjacent_matches = all(
        (recorded_adjacent.get(key) == expected_adjacent[key])
        if key in ("rows", "positive_certified_rows")
        else (
            (recorded_adjacent.get(key) is None and expected_adjacent[key] is None)
            or (recorded_adjacent.get(key) is not None
                and expected_adjacent[key] is not None
                and close(recorded_adjacent[key], expected_adjacent[key]))
        )
        for key in expected_adjacent
    )
    record_check(result, "adjacent family summary arithmetic", adjacent_matches,
                 {"recorded": recorded_adjacent, "recomputed": expected_adjacent})

    result["status"] = "PASS" if not result["failures"] else "FAIL"
    result["classification"] = "ARITHMETIC_AND_BINDING_AUDIT_ONLY"
    result["scope"] = {
        "matrix_reassembly": "NOT_PERFORMED",
        "finite_resolvent_arithmetic": "RECONSTRUCTED",
        "uniform_spacing_bound": "UNRESOLVED",
        "uniform_volume_bound": "UNRESOLVED",
        "continuum_recovery": "UNRESOLVED",
        "continuum_mass_gap": "UNRESOLVED",
    }
    result["summary"] = {
        "checks": len(result["checks"]),
        "passing_checks": sum(1 for row in result["checks"] if row["passed"]),
        "rows_reconstructed": len(rows),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    required = (PROTOCOL, SOURCE, PRIMARY_SOURCE, REFERENCE, PREDECESSOR_SOURCE, PREDECESSOR_RECEIPT, PRIMARY)
    if not all(path.exists() for path in required):
        raise FileNotFoundError("protocol, sources, reference, predecessor or primary receipt is missing")
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Receipt: {output}")
    print(json.dumps({key: result[key] for key in ("status", "classification", "summary", "failures")}, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
