#!/usr/bin/env python3
"""Audit exact degeneracy quotients across the complete retained order-nine population."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from typing import Any

import run_cubic_degeneracy_quotient_probe as quotient

ROOT = Path(__file__).resolve().parent
DEFAULT_STRUCTURE_RECEIPT = ROOT / "_diag" / "cubic_degeneracy_structure_probe.json"
DEFAULT_LIFT_RECEIPT = ROOT / "_diag" / "cubic_lift_realization_probe.json"
DEFAULT_OUTPUT = ROOT / "_diag" / "cubic_degeneracy_quotient_population_probe.json"
SCHEMA = "cassifi.cubic-degeneracy-quotient-population-probe.v1"
STRUCTURE_SCHEMA = "cassifi.cubic-degeneracy-structure-probe.v1"
LIFT_SCHEMA = "cassifi.cubic-lift-realization-probe.v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def formula_index(lift_receipt: dict[str, Any]) -> dict[str, tuple[tuple[int, ...], ...]]:
    formulas: dict[str, tuple[tuple[int, ...], ...]] = {}
    seen_hashes: set[str] = set()
    for order in lift_receipt["orders"]:
        for target in order["targets"]:
            formula_sha256 = target["formula_sha256"]
            if formula_sha256 in seen_hashes:
                raise ValueError(f"duplicate lift formula hash {formula_sha256}")
            seen_hashes.add(formula_sha256)
            if target["status"] == "analyzed":
                formulas[formula_sha256] = tuple(
                    tuple(clause) for clause in target["formula"]
                )
    return formulas


def validate_target(
    target: dict[str, Any], formula: tuple[tuple[int, ...], ...]
) -> None:
    formula_sha256 = target["formula_sha256"]
    order = target["order"]
    if len(formula) != order:
        raise ValueError(
            f"{formula_sha256}: matrix column count {len(formula)}, expected order {order}"
        )
    if any(
        len(clause) != 3
        or any(type(variable) is not int or not 1 <= variable <= order for variable in clause)
        for clause in formula
    ):
        raise ValueError(f"{formula_sha256}: malformed cubic formula")
    pairs = target["exclusive_pairs"]
    if len(pairs) != target["exclusive_pair_count"]:
        raise ValueError(
            f"{formula_sha256}: listed {len(pairs)} exclusive pairs, "
            f"declared {target['exclusive_pair_count']}"
        )
    seen_ports: set[tuple[int, int]] = set()
    for pair in pairs:
        ports = pair["ports"]
        if (
            pair["category"] not in {"primal_twins", "dual_parallel"}
            or not isinstance(ports, list)
            or len(ports) != 2
            or any(type(port) is not int for port in ports)
            or not 1 <= ports[0] < ports[1] <= order
        ):
            raise ValueError(f"{formula_sha256}: malformed exclusive-pair record")
        port_key = (ports[0], ports[1])
        if port_key in seen_ports:
            raise ValueError(f"{formula_sha256}: duplicate exclusive pair {ports}")
        seen_ports.add(port_key)


def behavior_signature(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "category": case["category"],
        "relation_kind": case["relation_kind"],
        "quotient_nullity": case["quotient"]["nullity"],
        "quotient_has_width_two_basis": case["quotient"]["width_two_basis_count"] > 0,
        "quotient_has_exclusive_pair": case["quotient"]["exclusive_pair_count"] > 0,
        "terminal": case["recursive"]["terminal"],
        "recursive_step_count": case["recursive"]["step_count"],
        "final_nullity": case["recursive"]["final_nullity"],
        "final_has_width_two_basis": case["recursive"]["final_width_two_basis_count"] > 0,
    }


def analyze_pair(
    formula_sha256: str,
    family_sha256: str,
    matrix: list[list[Fraction]],
    rhs: list[Fraction],
    original_profile: dict[str, Any],
    original_solutions: tuple[tuple[int, ...], ...],
    pair: dict[str, Any],
) -> dict[str, Any]:
    left, right = pair["ports"][0] - 1, pair["ports"][1] - 1
    category = pair["category"]
    new_matrix, new_rhs, relation = quotient.substitute_pair(
        matrix, rhs, left, right, category, original_profile
    )
    quotient_profile = quotient.affine_profile(new_matrix, new_rhs)
    quotient_rows = (
        quotient.basis_rows(quotient_profile["vectors"])
        if quotient_profile["consistent"]
        else tuple()
    )
    quotient_solutions = quotient.boolean_solutions(new_matrix, new_rhs)
    projected = {
        quotient.project_solution(solution, left, right, relation)
        for solution in original_solutions
    }
    remaining_pairs = quotient.exclusive_pairs(
        quotient_rows, len(new_matrix[0]) if new_matrix else 0
    )
    trace = quotient.reduction_trace(new_matrix, new_rhs)
    relation_compact = {
        "kind": relation["kind"],
        "allowed_original_pairs": relation["allowed_original_pairs"],
    }
    final_instance = {
        "matrix": trace.get("final_matrix"),
        "rhs": trace.get("final_rhs"),
    }
    case = {
        "formula_sha256": formula_sha256,
        "canonical_width_two_family_sha256": family_sha256,
        "category": category,
        "ports": pair["ports"],
        "relation_kind": relation["kind"],
        "allowed_original_pairs": relation["allowed_original_pairs"],
        "projected_solution_set_matches": projected == set(quotient_solutions),
        "original": {
            "nullity": original_profile["nullity"],
            "solution_count": len(original_solutions),
            "variable_count": len(matrix[0]),
        },
        "quotient": {
            "nullity": quotient_profile["nullity"],
            "rank": quotient_profile["rank"],
            "solution_count": len(quotient_solutions),
            "variable_count": len(new_matrix[0]) if new_matrix else 0,
            "width_two_basis_count": sum(width <= 2 for _, width in quotient_rows),
            "exclusive_pair_count": len(remaining_pairs),
        },
        "recursive": {
            "terminal": trace["terminal"],
            "step_count": len(trace["steps"]),
            "final_nullity": trace.get("final_nullity"),
            "final_solution_count": trace.get("final_solution_count"),
            "final_variable_count": trace.get("final_variable_count"),
            "final_width_two_basis_count": trace.get("final_width_two_basis_count", 0),
            "final_row_signature_histogram": trace.get("final_row_signature_histogram", {}),
        },
        "relation_sha256": digest(relation),
        "recursive_trace_sha256": digest(trace),
        "final_instance_sha256": digest(final_instance),
        "compact_relation_sha256": digest(relation_compact),
    }
    case["behavior_signature"] = behavior_signature(case)
    case["behavior_signature_sha256"] = digest(case["behavior_signature"])
    return case


def build_receipt(
    structure_receipt: dict[str, Any],
    lift_receipt: dict[str, Any],
) -> dict[str, Any]:
    if structure_receipt.get("schema") != STRUCTURE_SCHEMA:
        raise ValueError("unexpected degeneracy-structure schema")
    if lift_receipt.get("schema") != LIFT_SCHEMA:
        raise ValueError("unexpected lift schema")
    if digest(lift_receipt) != structure_receipt["source"]["receipt_sha256"]:
        raise ValueError("lift receipt does not match the structure receipt source digest")

    targets = structure_receipt["targets"]
    formulas = formula_index(lift_receipt)
    representatives = {
        family: min(
            target["formula_sha256"]
            for target in targets
            if target["canonical_width_two_family_sha256"] == family
        )
        for family in {
            target["canonical_width_two_family_sha256"] for target in targets
        }
    }
    cases: list[dict[str, Any]] = []
    representative_signatures: dict[str, set[str]] = defaultdict(set)
    seen_target_hashes: set[str] = set()

    for target in targets:
        formula_sha256 = target["formula_sha256"]
        if formula_sha256 in seen_target_hashes:
            raise ValueError(f"duplicate Result AA target hash {formula_sha256}")
        seen_target_hashes.add(formula_sha256)
        family_sha256 = target["canonical_width_two_family_sha256"]
        formula = formulas.get(formula_sha256)
        if formula is None:
            raise ValueError(f"missing lift formula for {formula_sha256}")
        validate_target(target, formula)
        size = len(formula)
        matrix = [
            [Fraction(int(variable + 1 in clause)) for variable in range(size)]
            for clause in formula
        ]
        rhs = [Fraction(1) for _ in formula]
        original_profile = quotient.affine_profile(matrix, rhs)
        original_solutions = quotient.boolean_solutions(matrix, rhs)

        for pair in target["exclusive_pairs"]:
            case = analyze_pair(
                formula_sha256,
                family_sha256,
                matrix,
                rhs,
                original_profile,
                original_solutions,
                pair,
            )
            cases.append(case)
            if formula_sha256 == representatives[family_sha256]:
                representative_signatures[family_sha256].add(
                    case["behavior_signature_sha256"]
                )

    for case in cases:
        family_sha256 = case["canonical_width_two_family_sha256"]
        case["behavior_novel_relative_to_representative"] = (
            case["behavior_signature_sha256"]
            not in representative_signatures[family_sha256]
        )

    terminal_structures = Counter(
        digest(
            {
                "terminal": case["recursive"]["terminal"],
                "final_nullity": case["recursive"]["final_nullity"],
                "final_variable_count": case["recursive"]["final_variable_count"],
                "final_solution_count": case["recursive"]["final_solution_count"],
                "final_width_two_basis_count": case["recursive"]["final_width_two_basis_count"],
                "final_row_signature_histogram": case["recursive"]["final_row_signature_histogram"],
            }
        )
        for case in cases
    )
    mismatches = sum(not case["projected_solution_set_matches"] for case in cases)
    without_width_two = sum(case["quotient"]["width_two_basis_count"] == 0 for case in cases)
    nonconstructive = sum(
        case["recursive"]["terminal"]
        not in {"nullity_at_most_two", "width_two_basis_without_exclusive_pair"}
        or case["recursive"]["final_width_two_basis_count"] == 0
        for case in cases
    )
    novel = sum(case["behavior_novel_relative_to_representative"] for case in cases)
    summary = {
        "target_count": len(targets),
        "canonical_family_count": len(representatives),
        "quotient_case_count": len(cases),
        "category_histogram": dict(sorted(Counter(case["category"] for case in cases).items())),
        "relation_histogram": dict(sorted(Counter(case["relation_kind"] for case in cases).items())),
        "quotient_nullity_histogram": dict(sorted(Counter(str(case["quotient"]["nullity"]) for case in cases).items())),
        "recursive_terminal_histogram": dict(sorted(Counter(case["recursive"]["terminal"] for case in cases).items())),
        "recursive_step_histogram": dict(sorted(Counter(str(case["recursive"]["step_count"]) for case in cases).items())),
        "family_case_histogram": dict(sorted(Counter(case["canonical_width_two_family_sha256"] for case in cases).items())),
        "family_novel_behavior_histogram": dict(sorted(Counter(case["canonical_width_two_family_sha256"] for case in cases if case["behavior_novel_relative_to_representative"]).items())),
        "terminal_structure_histogram": dict(sorted(terminal_structures.items())),
        "projected_solution_set_mismatches": mismatches,
        "quotients_without_width_two_basis": without_width_two,
        "nonconstructive_recursive_terminals": nonconstructive,
        "behavior_cases_novel_relative_to_representatives": novel,
        "maximum_recursive_steps_after_first_quotient": max((case["recursive"]["step_count"] for case in cases), default=0),
        "all_population_quotients_constructive": mismatches == 0 and without_width_two == 0 and nonconstructive == 0,
    }
    if len(targets) != 1402 or len(cases) != 2887:
        raise ValueError(
            f"population changed: expected 1402 targets/2887 cases, got {len(targets)}/{len(cases)}"
        )
    bounded_result = (
        "Every retained order-nine exclusive-pair quotient preserves its projected Boolean solution set and a width-two basis, and every deterministic recursive path reaches a constructive terminal."
        if summary["all_population_quotients_constructive"]
        else "At least one retained order-nine exclusive-pair quotient fails projected-solution, width-two-basis, or recursive-terminal construction."
    )
    return {
        "schema": SCHEMA,
        "selection": {
            "target_rule": "every retained Result AA target in receipt order",
            "pair_rule": "every exclusive pair of every target in listed order",
            "recursive_rule": "lexicographically first remaining exclusive pair",
            "representative_comparison_rule": "behavior signature must occur among the pair signatures of the smallest formula SHA-256 in the same canonical family",
        },
        "sources": {
            "degeneracy_structure_schema": structure_receipt["schema"],
            "degeneracy_structure_receipt_sha256": digest(structure_receipt),
            "lift_schema": lift_receipt["schema"],
            "lift_receipt_sha256": digest(lift_receipt),
        },
        "assessment": {
            "bounded_result": bounded_result,
            "scope": "All 1,402 retained connected order-nine cubic targets and all 2,887 listed exclusive pairs; not an arbitrary-order closure theorem.",
        },
        "summary": summary,
        "case_stream_sha256": digest(cases),
        "cases": cases,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--structure-receipt", type=Path, default=DEFAULT_STRUCTURE_RECEIPT)
    parser.add_argument("--lift-receipt", type=Path, default=DEFAULT_LIFT_RECEIPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = build_receipt(load_json(args.structure_receipt), load_json(args.lift_receipt))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["summary"], indent=2, sort_keys=True))
    print(f"wrote {args.output}")
    return 0 if receipt["summary"]["all_population_quotients_constructive"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
