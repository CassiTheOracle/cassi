"""Generate direct evidence for the degree-three-alias matching algorithm."""

from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

from cassi_alias_exact_one_field import (
    AliasExactOneDecisionError,
    AliasExactOneDecisionField,
    regular_monotone_formula,
)

OUTPUT = Path("_diag/alias_exact_one_decision.json")


def variable_count(formula) -> int:
    return max(variable for clause in formula for variable in clause)


def brute_model(formula, variables: int):
    for assignment in itertools.product((0, 1), repeat=variables):
        if all(sum(assignment[variable - 1] for variable in clause) == 1 for clause in formula):
            return assignment
    return None


def run_case(
    name: str,
    clauses: int,
    cubic: int,
    seed: int,
    *,
    enumerate_expected: bool,
    replay_steps: bool,
) -> dict:
    formula = regular_monotone_formula(clauses, cubic, seed=seed)
    variables = variable_count(formula)
    field, initial = AliasExactOneDecisionField.initialize(
        formula,
        variable_count=variables,
    )
    final, certificate = field.solve(initial)
    if enumerate_expected:
        expected = "sat" if brute_model(formula, variables) is not None else "unsat"
        if certificate["status"] != expected:
            raise AssertionError(f"{name}: branch/matching result disagrees with truth table")
    if replay_steps:
        stepped = initial
        transition_count = 0
        while field.inspect(stepped)["status"] == "running":
            stepped, _ = field.step(stepped)
            transition_count += 1
        if field.state_sha256(stepped) != field.state_sha256(final):
            raise AssertionError(f"{name}: public-step/bulk state mismatch")
        if transition_count != certificate["branches_checked"]:
            raise AssertionError(f"{name}: public transition count mismatch")
    descriptor = field.descriptor(final)
    restored_field, restored = AliasExactOneDecisionField.from_descriptor(descriptor)
    if restored_field.certificate(restored) != certificate:
        raise AssertionError(f"{name}: restored certificate mismatch")
    return {
        "name": name,
        "clauses": clauses,
        "variables": variables,
        "cubic": cubic,
        "seed": seed,
        "formula": [list(clause) for clause in formula],
        "enumerated": enumerate_expected,
        "public_steps_replayed": replay_steps,
        "certificate": certificate,
        "state": descriptor,
    }


def controls() -> list[dict]:
    formula = regular_monotone_formula(8, 4, seed=3)
    rows = []
    malformed = (
        ("degree-one-variable", ((1, 2, 3),), 3, "exactly two or three"),
        ("repeated-clause-variable", ((1, 1, 2),), 2, "repeats a variable"),
        ("negative-variable", ((-1, 2, 3),) + tuple(formula[1:]), 10, "three positive"),
    )
    for name, source, variables, expected in malformed:
        try:
            AliasExactOneDecisionField.initialize(source, variable_count=variables)
        except AliasExactOneDecisionError as exc:
            if expected not in str(exc):
                raise AssertionError(f"{name}: unexpected rejection: {exc}") from exc
            rows.append({"name": name, "status": "rejected", "error": str(exc)})
        else:
            raise AssertionError(f"{name}: malformed source accepted")
    field, initial = AliasExactOneDecisionField.initialize(formula, variable_count=10)
    damaged = copy.deepcopy(field.descriptor(initial))
    damaged["state_sha256"] = "0" * 64
    try:
        AliasExactOneDecisionField.from_descriptor(damaged)
    except AliasExactOneDecisionError as exc:
        if "state digest mismatch" not in str(exc):
            raise
        rows.append({"name": "damaged-checkpoint", "status": "rejected", "error": str(exc)})
    else:
        raise AssertionError("damaged checkpoint accepted")
    return rows


def run(output: Path = OUTPUT) -> dict:
    cases = []
    for clauses, cubic_values in (
        (4, (0, 2, 4)),
        (6, (0, 2, 4, 6)),
        (8, (0, 2, 4, 6, 8)),
        (10, (0, 2, 4, 6, 8, 10)),
    ):
        for cubic in cubic_values:
            if (clauses - cubic) % 2:
                continue
            for seed in range(3):
                cases.append(
                    run_case(
                        f"truth-c{clauses}-k{cubic}-s{seed}",
                        clauses,
                        cubic,
                        seed,
                        enumerate_expected=True,
                        replay_steps=seed == 0,
                    )
                )
    for clauses, cubic, seed in (
        (12, 0, 10),
        (14, 2, 11),
        (18, 4, 12),
        (24, 6, 13),
        (30, 8, 14),
        (36, 10, 15),
        (42, 12, 16),
        (48, 14, 17),
    ):
        cases.append(
            run_case(
                f"fixed-parameter-c{clauses}-k{cubic}",
                clauses,
                cubic,
                seed,
                enumerate_expected=False,
                replay_steps=True,
            )
        )
    for cubic in (8, 10, 14):
        cases.append(
            run_case(
                f"pure-cubic-modular-unsat-k{cubic}",
                cubic,
                cubic,
                100 + cubic,
                enumerate_expected=cubic <= 10,
                replay_steps=True,
            )
        )
    sat = sum(row["certificate"]["status"] == "sat" for row in cases)
    unsat = len(cases) - sat
    receipt = {
        "schema": "cassifi.alias-exact-one-receipt.v1",
        "assessment": {
            "result": "fixed-parameter exact decision by cubic-variable count",
            "search_bound": "O(2^k c^3)",
            "certificate_bound": "O(2^k c) entries",
            "p_equals_np": "not established",
            "hard_boundary": (
                "k=0 is graph perfect matching; k=c is cubic monotone "
                "1-in-3 SAT, NP-complete even for planar incidence graphs"
            ),
        },
        "field_contract": {
            "tensor": "one immutable float64 [1, 13+3c+2v+k, 1] field",
            "owned_state": "formula, degrees, cubic branch cursor, assignment, exact counters",
            "persistent_adaptive_side_tables": 0,
            "host_search_hints": 0,
            "model_calls": 0,
        },
        "cases": cases,
        "controls": controls(),
        "summary": {
            "cases": len(cases),
            "truth_table_cases": sum(row["enumerated"] for row in cases),
            "step_replays": sum(row["public_steps_replayed"] for row in cases),
            "sat": sat,
            "unsat": unsat,
            "maximum_clauses": max(row["clauses"] for row in cases),
            "maximum_variables": max(row["variables"] for row in cases),
            "maximum_cubic_variables": max(row["cubic"] for row in cases),
            "maximum_available_branches": max(row["certificate"]["branches"] for row in cases),
            "maximum_branches_checked": max(row["certificate"]["branches_checked"] for row in cases),
            "maximum_field_bytes": max(row["certificate"]["field_bytes"] for row in cases),
            "maximum_search_matching_runs": max(
                row["certificate"]["search_matching_runs"] for row in cases
            ),
            "maximum_proof_barrier_runs": max(
                row["certificate"]["proof_barrier_matching_runs"] for row in cases
            ),
            "all_checkpoints_exact": True,
            "all_truth_tables_agree": True,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["summary"], sort_keys=True))
    return receipt


if __name__ == "__main__":
    run()
