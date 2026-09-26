"""Measure the proof-carrying obstruction-cut continuation.

The existing AliasExactOneDecisionField is retained as an enumeration control.
This runner only generates deterministic regular sources, drives AliasCutField,
and records both results without importing the independent verifier.  It never
turns a bounded exhaustion into a decision.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from cassi_alias_exact_one_field import (
    AliasExactOneDecisionField,
    regular_monotone_formula,
)
from cassi_alias_cut_field import AliasCutField

OUTPUT = Path("_diag/alias_cut_analysis.json")


def variable_count(formula: Sequence[Sequence[int]]) -> int:
    return max(variable for clause in formula for variable in clause)


def is_connected(formula: Sequence[Sequence[int]], variables: int) -> bool:
    """Check connectivity of the source incidence bipartite graph."""
    total = variables + len(formula)
    graph = [set() for _ in range(total)]
    for clause_index, clause in enumerate(formula):
        clause_node = variables + clause_index
        for variable in clause:
            variable_node = variable - 1
            graph[variable_node].add(clause_node)
            graph[clause_node].add(variable_node)
    seen = {0}
    stack = [0]
    while stack:
        node = stack.pop()
        for neighbor in sorted(graph[node]):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return len(seen) == total


def build_connected_obstruction_family(
    clause_count: int,
    cubic_variables: int,
    *,
    seed: int,
) -> list[list[int]]:
    """Construct one deterministic connected regular degree-two/three source."""
    formula = regular_monotone_formula(clause_count, cubic_variables, seed=seed)
    variables = variable_count(formula)
    if not is_connected(formula, variables):
        raise AssertionError("regular source is not connected")
    return [list(clause) for clause in formula]


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _baseline(formula: Sequence[Sequence[int]]) -> dict[str, Any]:
    variables = variable_count(formula)
    field, initial = AliasExactOneDecisionField.initialize(
        formula,
        variable_count=variables,
    )
    final, certificate = field.solve(initial)
    return {
        "status": certificate["status"],
        "branches": certificate["branches"],
        "branches_checked": certificate["branches_checked"],
        "matching_runs": certificate["search_matching_runs"],
        "proof_barrier_matching_runs": certificate["proof_barrier_matching_runs"],
        "field_bytes": certificate["field_bytes"],
        "certificate_sha256": _digest(certificate),
        "state_sha256": field.state_sha256(final),
    }


def run_case(
    name: str,
    formula: Sequence[Sequence[int]],
    *,
    expected_status: str,
    baseline: bool = True,
) -> dict[str, Any]:
    variables = variable_count(formula)
    field, initial = AliasCutField.initialize(
        formula,
        variable_count=variables,
        max_cuts=512,
        max_cut_bytes=65_536,
        max_journal_bytes=65_536,
        max_steps=50_000,
        max_learned_clauses=512,
    )
    final, result = field.solve(initial)
    if result["status"] != expected_status:
        raise AssertionError(
            f"{name}: expected {expected_status}, got {result['status']} ({result['reason']})"
        )
    descriptor = field.descriptor(final)
    restored_field, restored_state = AliasCutField.from_descriptor(descriptor)
    restored_result = restored_field.result(restored_state)
    restart_verified = restored_result == result
    if not restart_verified:
        raise AssertionError(f"{name}: descriptor restart changed result")

    baseline_result = _baseline(formula) if baseline else None
    if baseline_result is not None and baseline_result["status"] != result["status"]:
        raise AssertionError(
            f"{name}: cut solver disagrees with enumeration control: "
            f"{result['status']} != {baseline_result['status']}"
        )
    source_connected = is_connected(formula, variables)
    if not source_connected:
        raise AssertionError(f"{name}: source connectivity check failed")
    cut_kinds = sorted({cut["kind"] for cut in result["cuts"]})
    return {
        "name": name,
        "kind": result["status"],
        "formula": [list(clause) for clause in formula],
        "variable_count": variables,
        "cubic_variables": result["cubic_variables"],
        "source_connected": source_connected,
        "cut_kinds": cut_kinds,
        "result": result,
        "descriptor": descriptor,
        "restart_verified": restart_verified,
        "baseline": baseline_result,
    }


def _case_specs() -> tuple[tuple[str, int, int, int, str], ...]:
    return (
        ("matched-control-c4-k0-s0", 4, 0, 0, "sat"),
        ("connected-sat-c6-k2-s0", 6, 2, 0, "sat"),
        ("connected-unsat-c6-k2-s1", 6, 2, 1, "unsat"),
        ("connected-sat-c8-k4-s0", 8, 4, 0, "sat"),
        ("connected-unsat-c8-k4-s3", 8, 4, 3, "unsat"),
        ("connected-sat-c10-k6-s2", 10, 6, 2, "sat"),
        ("connected-unsat-c10-k6-s0", 10, 6, 0, "unsat"),
        ("connected-sat-c12-k8-s0", 12, 8, 0, "sat"),
        ("connected-unsat-c12-k8-s2", 12, 8, 2, "unsat"),
        ("connected-sat-c14-k10-s1", 14, 10, 1, "sat"),
        ("connected-unsat-c14-k10-s0", 14, 10, 0, "unsat"),
    )


def run_analysis(output: Path = OUTPUT) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for name, clauses, cubic, seed, expected in _case_specs():
        formula = build_connected_obstruction_family(clauses, cubic, seed=seed)
        cases.append(run_case(name, formula, expected_status=expected))

    all_cuts = [cut for case in cases for cut in case["result"]["cuts"]]
    summary = {
        "cases": len(cases),
        "sat": sum(case["kind"] == "sat" for case in cases),
        "unsat": sum(case["kind"] == "unsat" for case in cases),
        "exhausted": sum(case["kind"] == "exhausted" for case in cases),
        "all_connected": all(case["source_connected"] for case in cases),
        "all_restart_verified": all(case["restart_verified"] for case in cases),
        "baseline_agreement": all(
            case["baseline"] is None or case["baseline"]["status"] == case["kind"]
            for case in cases
        ),
        "cuts": len(all_cuts),
        "overfill_cuts": sum(cut["kind"] == "overfill" for cut in all_cuts),
        "tutte_cuts": sum(cut["kind"] == "tutte" for cut in all_cuts),
        "tutte_cuts_with_boundary_witnesses": sum(
            cut["kind"] == "tutte" and bool(cut["boundary_witnesses"])
            for cut in all_cuts
        ),
        "tutte_cuts_with_nonempty_components": sum(
            cut["kind"] == "tutte" and bool(cut["components"])
            for cut in all_cuts
        ),
        "oracle_calls": sum(case["result"]["work"]["oracle_calls"] for case in cases),
        "matching_runs": sum(case["result"]["work"]["matching_runs"] for case in cases),
        "barrier_matching_runs": sum(
            case["result"]["work"]["barrier_matching_runs"] for case in cases
        ),
        "matching_work_bound": sum(
            case["result"]["work"]["matching_work_bound"] for case in cases
        ),
        "alias_steps": sum(case["result"]["work"]["alias_transitions"] for case in cases),
        "max_cubic_variables": max(len(case["cubic_variables"]) for case in cases),
        "max_cuts_in_case": max(case["result"]["work"]["cuts"] for case in cases),
        "max_matching_work_bound": max(
            case["result"]["work"]["matching_work_bound"] for case in cases
        ),
    }
    receipt = {
        "schema": "cassifi.alias-cut-analysis.v1",
        "algorithm": {
            "name": "projected obstruction cuts over alias CNF",
            "baseline": "AliasExactOneDecisionField exhaustive cubic assignment control",
            "claim": "restricted exact continuation; no unrestricted polynomial bound",
            "matching_work_bound": "each matching call is charged c^3; all barrier runs included",
        },
        "cases": cases,
        "summary": summary,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return receipt


if __name__ == "__main__":
    run_analysis()
