#!/usr/bin/env python3
"""Search a finite canonical order-ten extension domain for a nondegenerate exclusive pair.

The domain is deliberately targeted rather than a full order-ten matching cover:
choose the minimum-formula-hash representative of each of Result AA's four
order-nine width-two families, then insert one new row and one new column by
replacing every size-three matching of old incidence edges with the new vertex
stars.  Every generated simple connected candidate is analyzed exactly.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import run_cubic_lift_realization_probe as lift

ROOT = Path(__file__).resolve().parent
DEFAULT_STRUCTURE = ROOT / "_diag" / "cubic_degeneracy_structure_probe.json"
DEFAULT_LIFT = ROOT / "_diag" / "cubic_lift_realization_probe.json"
DEFAULT_OUTPUT = ROOT / "_diag" / "cubic_order10_targeted_probe.json"
SCHEMA = "cassifi.cubic-order10-targeted-probe.v1"
STRUCTURE_SCHEMA = "cassifi.cubic-degeneracy-structure-probe.v1"
LIFT_SCHEMA = "cassifi.cubic-lift-realization-probe.v1"
BASE_ORDER = 9
TARGET_ORDER = 10
TARGET_NULLITY = 3

Formula = tuple[tuple[int, int, int], ...]
Edge = tuple[int, int]


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def json_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def formula_digest(formula: Formula) -> str:
    return lift.formula_digest(formula)


def base_representatives(
    structure: dict[str, Any], lift_receipt: dict[str, Any]
) -> list[dict[str, Any]]:
    if structure.get("schema") != STRUCTURE_SCHEMA:
        raise ValueError("unexpected structure schema")
    if lift_receipt.get("schema") != LIFT_SCHEMA:
        raise ValueError("unexpected lift schema")
    if json_digest(lift_receipt) != structure["source"]["receipt_sha256"]:
        raise ValueError("lift receipt is not the source bound by Result AA")

    target_by_hash: dict[str, dict[str, Any]] = {}
    for target in structure["targets"]:
        formula_sha256 = target["formula_sha256"]
        if formula_sha256 in target_by_hash:
            raise ValueError(f"duplicate structure target {formula_sha256}")
        target_by_hash[formula_sha256] = target
    formula_by_hash: dict[str, Formula] = {}
    for order in lift_receipt["orders"]:
        for target in order["targets"]:
            formula_sha256 = target["formula_sha256"]
            if formula_sha256 in formula_by_hash:
                raise ValueError(f"duplicate lift formula {formula_sha256}")
            if target["status"] == "analyzed":
                clauses = target["formula"]
                if any(len(clause) != 3 for clause in clauses):
                    raise ValueError(f"{formula_sha256}: malformed source formula")
                formula_by_hash[formula_sha256] = tuple(
                    (int(clause[0]), int(clause[1]), int(clause[2]))
                    for clause in clauses
                )

    families = sorted(
        {target["canonical_width_two_family_sha256"] for target in structure["targets"]}
    )
    representatives: list[dict[str, Any]] = []
    for family in families:
        family_hashes = [
            target["formula_sha256"]
            for target in structure["targets"]
            if target["canonical_width_two_family_sha256"] == family
        ]
        formula_sha256 = min(family_hashes)
        formula = formula_by_hash.get(formula_sha256)
        if formula is None:
            raise ValueError(f"missing lift formula for representative {formula_sha256}")
        target = target_by_hash[formula_sha256]
        if len(formula) != BASE_ORDER or target["order"] != BASE_ORDER:
            raise ValueError(f"representative {formula_sha256} is not order nine")
        representatives.append(
            {
                "canonical_width_two_family_sha256": family,
                "formula_sha256": formula_sha256,
                "formula": formula,
            }
        )
    return representatives


def matching_edges(formula: Formula) -> tuple[Edge, ...]:
    return tuple(
        (row, variable)
        for row, clause in enumerate(formula)
        for variable in clause
    )


def extend_formula(formula: Formula, edges: tuple[Edge, Edge, Edge]) -> Formula:
    selected_rows = {row for row, _ in edges}
    selected_columns = {column for _, column in edges}
    if len(selected_rows) != 3 or len(selected_columns) != 3:
        raise ValueError("extension edges must form a size-three matching")
    rows = [list(clause) for clause in formula]
    for row, column in edges:
        rows[row].remove(column)
        rows[row].append(TARGET_ORDER)
    rows.append(sorted(selected_columns))
    return lift.production.canonical_cubic_formula(rows)


def generation_rows(
    representatives: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    candidates: dict[str, dict[str, Any]] = {}
    for representative in representatives:
        formula = representative["formula"]
        edges = matching_edges(formula)
        for selected in itertools.combinations(edges, 3):
            if len({row for row, _ in selected}) != 3:
                continue
            if len({column for _, column in selected}) != 3:
                continue
            edge_a, edge_b, edge_c = tuple(sorted(selected))
            ordered_edges = (edge_a, edge_b, edge_c)
            extended = extend_formula(formula, ordered_edges)
            candidate_hash = formula_digest(extended)
            row = {
                "base_canonical_width_two_family_sha256": representative[
                    "canonical_width_two_family_sha256"
                ],
                "base_formula_sha256": representative["formula_sha256"],
                "edges": [[row + 1, column] for row, column in ordered_edges],
                "formula_sha256": candidate_hash,
                "simple": len(set(extended)) == TARGET_ORDER,
            }
            rows.append(row)
            if not row["simple"]:
                continue
            candidate = candidates.setdefault(
                candidate_hash,
                {
                    "formula": extended,
                    "provenance": [],
                },
            )
            candidate["provenance"].append(
                {
                    "base_canonical_width_two_family_sha256": row[
                        "base_canonical_width_two_family_sha256"
                    ],
                    "base_formula_sha256": row["base_formula_sha256"],
                    "edges": row["edges"],
                }
            )
    rows.sort(
        key=lambda row: (
            row["base_canonical_width_two_family_sha256"],
            row["base_formula_sha256"],
            row["edges"],
        )
    )
    for candidate in candidates.values():
        candidate["provenance"].sort(
            key=lambda item: (
                item["base_canonical_width_two_family_sha256"],
                item["base_formula_sha256"],
                item["edges"],
            )
        )
    return rows, candidates


def is_nondegenerate_exclusive_pair(record: dict[str, Any]) -> bool:
    return (
        record["category"] == "eligible"
        and record["kernel_pair_rank"] == 2
        and not record["primal_incidence_identical"]
    )


def exclusive_pair_records(
    formula: Formula,
    vectors: tuple[tuple[Fraction, ...], ...],
    basis_rows: tuple[tuple[tuple[int, ...], int], ...],
) -> list[dict[str, Any]]:
    width_two = tuple(basis for basis, width in basis_rows if width <= 2)
    supports = lift._column_supports(formula)
    records: list[dict[str, Any]] = []
    for left, right in itertools.combinations(range(TARGET_ORDER), 2):
        states = {
            f"{int(left + 1 in basis)}{int(right + 1 in basis)}"
            for basis in width_two
        }
        if states != {"01", "10"}:
            continue
        pair_rank = lift.production._vector_rank((vectors[left], vectors[right]))
        identical = supports[left] == supports[right]
        category = lift.exclusive_category(pair_rank, identical)
        if (category == "eligible") != (pair_rank == 2 and not identical):
            raise AssertionError("eligible category disagrees with explicit criterion")
        records.append(
            {
                "ports": [left + 1, right + 1],
                "category": category,
                "kernel_pair_rank": pair_rank,
                "primal_incidence_identical": identical,
            }
        )
    return records


def analyze_candidate(
    candidate_hash: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    formula: Formula = candidate["formula"]
    connected = lift.production.incidence_connected(formula)
    profile, vectors, basis_rows = lift.basis_profile(formula)
    pair_records = (
        exclusive_pair_records(formula, vectors, basis_rows) if connected else []
    )
    category_histogram = Counter(row["category"] for row in pair_records)
    return {
        "basis_profile_exact": True,
        "pair_profile_exact": connected,
        "formula_sha256": candidate_hash,
        "formula": [list(clause) for clause in formula],
        "provenance": candidate["provenance"],
        "connected": connected,
        "rank": profile["rank"],
        "nullity": profile["nullity"],
        "status": "analyzed" if connected and profile["nullity"] >= TARGET_NULLITY else (
            "disconnected" if not connected else "nullity_below_target"
        ),
        "width_two_basis_count": profile["width_two_basis_count"],
        "basis_maximum_support_histogram": profile["basis_maximum_support_histogram"],
        "exclusive_pair_count": len(pair_records),
        "exclusive_pair_category_histogram": dict(sorted(category_histogram.items())),
        "nondegenerate_exclusive_pair_count": sum(
            is_nondegenerate_exclusive_pair(row) for row in pair_records
        ),
        "exclusive_pair_stream_sha256": json_digest(pair_records),
        "exclusive_pairs": pair_records,
    }


def build_receipt(
    structure: dict[str, Any],
    lift_receipt: dict[str, Any],
    structure_path: Path,
    lift_path: Path,
) -> dict[str, Any]:
    representatives = base_representatives(structure, lift_receipt)
    generation, candidates = generation_rows(representatives)
    candidate_rows = [
        analyze_candidate(candidate_hash, candidates[candidate_hash])
        for candidate_hash in sorted(candidates)
    ]
    analyzed = [row for row in candidate_rows if row["status"] == "analyzed"]
    connected_rows = [row for row in candidate_rows if row["connected"]]
    target_rows = analyzed
    all_nullity_histogram = Counter(str(row["nullity"]) for row in candidate_rows)
    target_nullity_histogram = Counter(str(row["nullity"]) for row in target_rows)
    status_histogram = Counter(row["status"] for row in candidate_rows)
    all_category_histogram = Counter(
        category
        for row in connected_rows
        for category, count in row["exclusive_pair_category_histogram"].items()
        for _ in range(count)
    )
    target_category_histogram = Counter(
        category
        for row in target_rows
        for category, count in row["exclusive_pair_category_histogram"].items()
        for _ in range(count)
    )
    all_pair_case_count = sum(row["exclusive_pair_count"] for row in connected_rows)
    target_pair_case_count = sum(row["exclusive_pair_count"] for row in target_rows)
    all_nondegenerate_count = sum(
        row["nondegenerate_exclusive_pair_count"] for row in connected_rows
    )
    target_nondegenerate_count = sum(
        row["nondegenerate_exclusive_pair_count"] for row in target_rows
    )
    summary = {
        "exactly_profiled_candidate_count": len(candidate_rows),
        "target_nullity_at_least_three_candidate_count": len(target_rows),
        "skipped_candidate_count": len(candidate_rows) - len(target_rows),
        "candidate_status_histogram": dict(sorted(status_histogram.items())),
        "all_candidate_nullity_histogram": dict(sorted(all_nullity_histogram.items())),
        "target_nullity_histogram": dict(sorted(target_nullity_histogram.items())),
        "non_simple_extension_count": sum(not row["simple"] for row in generation),
        "connected_candidate_count": sum(row["connected"] for row in candidate_rows),
        "pair_profiled_candidate_count": sum(
            row["pair_profile_exact"] for row in candidate_rows
        ),
        "all_candidates_exactly_profiled": all(
            row["basis_profile_exact"] for row in candidate_rows
        ),
        "all_connected_candidates_pair_checked": all(
            row["pair_profile_exact"] for row in candidate_rows if row["connected"]
        ),
        "all_connected_exclusive_pair_count": all_pair_case_count,
        "target_exclusive_pair_count": target_pair_case_count,
        "all_connected_exclusive_pair_category_histogram": dict(
            sorted(all_category_histogram.items())
        ),
        "target_exclusive_pair_category_histogram": dict(
            sorted(target_category_histogram.items())
        ),
        "all_connected_nondegenerate_exclusive_pair_count": all_nondegenerate_count,
        "target_nondegenerate_exclusive_pair_count": target_nondegenerate_count,
        "all_connected_candidates_with_nondegenerate_pair": sum(
            row["nondegenerate_exclusive_pair_count"] > 0 for row in connected_rows
        ),
        "target_candidates_with_nondegenerate_pair": sum(
            row["nondegenerate_exclusive_pair_count"] > 0 for row in target_rows
        ),
        "all_connected_exclusive_pairs_degenerate": all_nondegenerate_count == 0,
        "target_exclusive_pairs_degenerate": target_nondegenerate_count == 0,
        "pair_case_count_consistent": all_pair_case_count
        == sum(len(row["exclusive_pairs"]) for row in connected_rows),
        "target_pair_case_count_consistent": target_pair_case_count
        == sum(len(row["exclusive_pairs"]) for row in target_rows),
    }
    assessment_result = (
        "targeted_order10_no_nondegenerate_exclusive_pair"
        if summary["all_connected_exclusive_pairs_degenerate"]
        else "targeted_order10_nondegenerate_exclusive_pair_found"
    )
    return {
        "schema": SCHEMA,
        "domain": {
            "base_order": BASE_ORDER,
            "acceptance_criterion": (
                "a counterexample is an exclusive pair with kernel_pair_rank == 2 and primal_incidence_identical == false"
            ),
            "target_order": TARGET_ORDER,
            "base_selection_rule": (
                "minimum formula_sha256 target in each canonical Result AA family"
            ),
            "extension_rule": (
                "for each base representative, choose every size-three matching of old incidence edges; remove those edges, add variable 10 to their old rows, and make the new row the selected old columns"
            ),
            "candidate_rule": (
                "retain only simple row-sorted cubic extensions and deduplicate by formula_sha256"
            ),
            "analysis_rule": (
                "exactly profile every retained candidate; classify every exclusive pair across the complete width-two basis family for every connected candidate"
            ),
            "targeted_scope": (
                "canonical Result AA representatives plus all three-edge vertex insertions; not the complete order-ten matching cover"
            ),
            "stopping_rule": "exhaust the finite generated domain; no early stopping",
        },
        "sources": {
            "degeneracy_structure_schema": structure["schema"],
            "degeneracy_structure_file_sha256": sha256_file(structure_path),
            "lift_schema": lift_receipt["schema"],
            "lift_receipt_file_sha256": sha256_file(lift_path),
            "lift_receipt_canonical_digest": json_digest(lift_receipt),
        },
        "generation": {
            "base_representatives": [
                {
                    "canonical_width_two_family_sha256": row[
                        "canonical_width_two_family_sha256"
                    ],
                    "formula_sha256": row["formula_sha256"],
                }
                for row in representatives
            ],
            "generation_stream_sha256": json_digest(generation),
            "candidate_stream_sha256": json_digest(candidate_rows),
        },
        "summary": summary,
        "assessment": {
            "result": assessment_result,
            "scope": (
                "A finite targeted order-ten extension domain. A negative result does not exclude other order-ten cubic formulas or arbitrary-order witnesses."
            ),
            "bounded_conclusion": (
                "No nondegenerate exclusive pair occurs among any connected candidate in this targeted order-ten domain."
                if summary["all_connected_exclusive_pairs_degenerate"]
                else "A nondegenerate exclusive pair occurs in the targeted order-ten domain."
            ),
        },
        "generation_rows": generation,
        "candidates": candidate_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--structure-receipt", type=Path, default=DEFAULT_STRUCTURE)
    parser.add_argument("--lift-receipt", type=Path, default=DEFAULT_LIFT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = build_receipt(
        load_json(args.structure_receipt),
        load_json(args.lift_receipt),
        args.structure_receipt,
        args.lift_receipt,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["summary"], indent=2, sort_keys=True))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
