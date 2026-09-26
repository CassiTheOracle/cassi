#!/usr/bin/env python3
"""Independently reconstruct and verify the population quotient receipt."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

import verify_cubic_degeneracy_quotient_probe as independent

ROOT = Path(__file__).resolve().parent
DEFAULT_RECEIPT = ROOT / "_diag" / "cubic_degeneracy_quotient_population_probe.json"
DEFAULT_STRUCTURE = ROOT / "_diag" / "cubic_degeneracy_structure_probe.json"
DEFAULT_LIFT = ROOT / "_diag" / "cubic_lift_realization_probe.json"
SCHEMA = "cassifi.cubic-degeneracy-quotient-population-probe.v1"
STRUCTURE_SCHEMA = "cassifi.cubic-degeneracy-structure-probe.v1"
LIFT_SCHEMA = "cassifi.cubic-lift-realization-probe.v1"

VerificationError = independent.VerificationError


def fail(message: str) -> None:
    raise VerificationError(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path}: expected a JSON object")
    return value

def formula_index(lift: dict[str, Any]) -> dict[str, list[list[int]]]:
    formulas: dict[str, list[list[int]]] = {}
    seen_hashes: set[str] = set()
    for order in lift["orders"]:
        for target in order["targets"]:
            formula_sha256 = target["formula_sha256"]
            if formula_sha256 in seen_hashes:
                fail(f"duplicate lift formula hash {formula_sha256}")
            seen_hashes.add(formula_sha256)
            if target["status"] == "analyzed":
                formulas[formula_sha256] = target["formula"]
    return formulas


def validate_target(target: dict[str, Any], formula: list[list[int]]) -> None:
    formula_sha256 = target["formula_sha256"]
    order = target["order"]
    if len(formula) != order:
        fail(
            f"{formula_sha256}: matrix column count {len(formula)}, expected order {order}"
        )
    if any(
        len(clause) != 3
        or any(type(variable) is not int or not 1 <= variable <= order for variable in clause)
        for clause in formula
    ):
        fail(f"{formula_sha256}: malformed cubic formula")
    pairs = target["exclusive_pairs"]
    if len(pairs) != target["exclusive_pair_count"]:
        fail(
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
            fail(f"{formula_sha256}: malformed exclusive-pair record")
        port_key = (ports[0], ports[1])
        if port_key in seen_ports:
            fail(f"{formula_sha256}: duplicate exclusive pair {ports}")
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


def compact_case(
    target: dict[str, Any], pair: dict[str, Any], formula: list[list[int]]
) -> dict[str, Any]:
    family = target["canonical_width_two_family_sha256"]
    rich = independent.reconstruct_case(
        {
            "canonical_family_sha256": family,
            "formula_sha256": target["formula_sha256"],
            "category": pair["category"],
            "ports": pair["ports"],
        },
        formula,
    )
    relation = rich["relation"]
    quotient = rich["quotient"]
    trace = rich["recursive_reduction"]
    relation_compact = {
        "kind": relation["kind"],
        "allowed_original_pairs": relation["allowed_original_pairs"],
    }
    final_instance = {
        "matrix": trace.get("final_matrix"),
        "rhs": trace.get("final_rhs"),
    }
    case = {
        "formula_sha256": target["formula_sha256"],
        "canonical_width_two_family_sha256": family,
        "category": pair["category"],
        "ports": pair["ports"],
        "relation_kind": relation["kind"],
        "allowed_original_pairs": relation["allowed_original_pairs"],
        "projected_solution_set_matches": rich["projected_solution_set_matches"],
        "original": {
            "nullity": rich["original"]["nullity"],
            "solution_count": rich["original"]["solution_count"],
            "variable_count": rich["original"]["variable_count"],
        },
        "quotient": {
            "nullity": quotient["nullity"],
            "rank": quotient["rank"],
            "solution_count": quotient["solution_count"],
            "variable_count": quotient["variable_count"],
            "width_two_basis_count": quotient["width_two_basis_count"],
            "exclusive_pair_count": len(quotient["exclusive_pairs"]),
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
        "relation_sha256": independent.digest(relation),
        "recursive_trace_sha256": independent.digest(trace),
        "final_instance_sha256": independent.digest(final_instance),
        "compact_relation_sha256": independent.digest(relation_compact),
    }
    case["behavior_signature"] = behavior_signature(case)
    case["behavior_signature_sha256"] = independent.digest(case["behavior_signature"])
    return case


def build_expected(
    structure: dict[str, Any], lift: dict[str, Any]
) -> dict[str, Any]:
    if structure.get("schema") != STRUCTURE_SCHEMA:
        fail("degeneracy-structure schema mismatch")
    if lift.get("schema") != LIFT_SCHEMA:
        fail("lift schema mismatch")
    if independent.digest(lift) != structure["source"]["receipt_sha256"]:
        fail("lift receipt is not the source bound by Result AA")
    formulas = formula_index(lift)
    targets = structure["targets"]
    pair_count = sum(len(target["exclusive_pairs"]) for target in targets)
    if len(targets) != 1402 or pair_count != 2887:
        fail(
            "population scope mismatch: expected 1,402 targets and 2,887 pairs, "
            f"observed {len(targets)} targets and {pair_count} pairs"
        )
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
            fail(f"duplicate Result AA target hash {formula_sha256}")
        seen_target_hashes.add(formula_sha256)
        if formula_sha256 not in formulas:
            fail(f"missing lift formula for {formula_sha256}")
        validate_target(target, formulas[formula_sha256])
        family = target["canonical_width_two_family_sha256"]
        for pair in target["exclusive_pairs"]:
            case = compact_case(target, pair, formulas[formula_sha256])
            cases.append(case)
            if formula_sha256 == representatives[family]:
                representative_signatures[family].add(case["behavior_signature_sha256"])
    for case in cases:
        family = case["canonical_width_two_family_sha256"]
        case["behavior_novel_relative_to_representative"] = (
            case["behavior_signature_sha256"] not in representative_signatures[family]
        )

    terminal_structures = Counter(
        independent.digest(
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
            "degeneracy_structure_schema": structure["schema"],
            "degeneracy_structure_receipt_sha256": independent.digest(structure),
            "lift_schema": lift["schema"],
            "lift_receipt_sha256": independent.digest(lift),
        },
        "assessment": {
            "bounded_result": bounded_result,
            "scope": "All 1,402 retained connected order-nine cubic targets and all 2,887 listed exclusive pairs; not an arbitrary-order closure theorem.",
        },
        "summary": summary,
        "case_stream_sha256": independent.digest(cases),
        "cases": cases,
    }


def verify(
    receipt: dict[str, Any], structure: dict[str, Any], lift: dict[str, Any]
) -> dict[str, Any]:
    expected = build_expected(structure, lift)
    independent.compare(expected, receipt)
    summary = expected["summary"]
    if summary["target_count"] != 1402 or summary["quotient_case_count"] != 2887:
        fail("population cardinality changed")
    if summary["projected_solution_set_mismatches"]:
        fail("a projected Boolean solution set differs")
    if summary["quotients_without_width_two_basis"]:
        fail("a first quotient lost every width-two basis")
    if summary["nonconstructive_recursive_terminals"]:
        fail("a recursive quotient path is nonconstructive")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--structure-receipt", type=Path, default=DEFAULT_STRUCTURE)
    parser.add_argument("--lift-receipt", type=Path, default=DEFAULT_LIFT)
    args = parser.parse_args()
    try:
        summary = verify(
            load_json(args.receipt),
            load_json(args.structure_receipt),
            load_json(args.lift_receipt),
        )
    except (KeyError, TypeError, ValueError, VerificationError) as error:
        raise SystemExit(f"verification failed: {error}") from error
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("independent population verification passed")


if __name__ == "__main__":
    main()
