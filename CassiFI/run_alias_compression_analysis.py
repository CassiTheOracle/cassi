"""Measure exact-cover compression and the uniform matchgate-basis obstruction.

The decision recurrence is an analysis control, not a replacement runtime.
The golden-ratio recurrence describes one mixed local branch pattern; a
degree-two-only clause gives a different local pattern, so this implementation
has no proved global golden-ratio bound. The symbolic half checks whether the
degree-three equality seam can instead be removed by one uniform holographic
basis and the necessary matchgate parity condition.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any, Sequence

import sympy as sp

SOURCE = Path("_diag/alias_exact_one_decision.json")
OUTPUT = Path("_diag/alias_compression_analysis.json")
SCHEMA = "cassifi.alias-compression-analysis.v2"
PUBLISHED_MONOTONE_BASE = 1.0984


def exact_cover_decision(
    formula: Sequence[Sequence[int]],
    variable_count: int,
) -> dict[str, Any]:
    edges = [0] * variable_count
    for clause_index, clause in enumerate(formula):
        bit = 1 << clause_index
        for variable in clause:
            edges[variable - 1] |= bit
    incident = [[] for _ in formula]
    for variable, edge in enumerate(edges, 1):
        for clause_index in range(len(formula)):
            if edge & (1 << clause_index):
                incident[clause_index].append((variable, edge))

    memo: dict[int, tuple[int, ...] | None] = {}
    states = 0
    choices = 0
    cache_hits = 0

    def solve(uncovered: int) -> tuple[int, ...] | None:
        nonlocal states, choices, cache_hits
        if uncovered in memo:
            cache_hits += 1
            return memo[uncovered]
        states += 1
        if uncovered == 0:
            memo[uncovered] = ()
            return ()
        available_by_clause = []
        for clause_index in range(len(formula)):
            if not uncovered & (1 << clause_index):
                continue
            available = tuple(
                (variable, edge)
                for variable, edge in incident[clause_index]
                if edge & uncovered == edge
            )
            available_by_clause.append((len(available), clause_index, available))
        _, _, candidates = min(available_by_clause)
        for variable, edge in candidates:
            choices += 1
            suffix = solve(uncovered ^ edge)
            if suffix is not None:
                result = (variable,) + suffix
                memo[uncovered] = result
                return result
        memo[uncovered] = None
        return None

    selected = solve((1 << len(formula)) - 1)
    assignment = [0] * variable_count
    if selected is not None:
        for variable in selected:
            assignment[variable - 1] = 1
        assert all(
            sum(assignment[variable - 1] for variable in clause) == 1
            for clause in formula
        )
    return {
        "status": "sat" if selected is not None else "unsat",
        "selected_variables": list(selected) if selected is not None else None,
        "states": states,
        "choices": choices,
        "cache_hits": cache_hits,
    }


def transformed_signature(
    signature: tuple[int, int, int, int],
    transform: Any,
) -> tuple[Any, ...]:
    values: dict[tuple[int, ...], Any] = {}
    for output in itertools.product((0, 1), repeat=3):
        total = sp.Integer(0)
        for source in itertools.product((0, 1), repeat=3):
            total += (
                transform[output[0], source[0]]
                * transform[output[1], source[1]]
                * transform[output[2], source[2]]
                * signature[sum(source)]
            )
        values[output] = sp.expand(total)
    return tuple(
        values[(1,) * weight + (0,) * (3 - weight)]
        for weight in range(4)
    )


def uniform_matchgate_parity_analysis() -> dict[str, Any]:
    a, b, c, d, inverse_det = sp.symbols("a b c d inverse_det")
    basis = sp.Matrix([[a, b], [c, d]])
    duals = {
        "inverse": sp.Matrix([[d, -b], [-c, a]]),
        "inverse_transpose": sp.Matrix([[d, -c], [-b, a]]),
    }
    equality = transformed_signature((1, 0, 0, 1), basis)
    cases = []
    for convention, dual in duals.items():
        exact_one = transformed_signature((0, 1, 0, 0), dual)
        for equality_parity in ("even", "odd"):
            for exact_one_parity in ("even", "odd"):
                equality_forbidden = (
                    (1, 3) if equality_parity == "even" else (0, 2)
                )
                exact_one_forbidden = (
                    (1, 3) if exact_one_parity == "even" else (0, 2)
                )
                equations = [equality[index] for index in equality_forbidden]
                equations.extend(
                    exact_one[index] for index in exact_one_forbidden
                )
                equations.append(inverse_det * (a * d - b * c) - 1)
                groebner = sp.groebner(
                    equations,
                    inverse_det,
                    a,
                    b,
                    c,
                    d,
                    order="lex",
                )
                reduced = tuple(str(poly.as_expr()) for poly in groebner.polys)
                cases.append(
                    {
                        "convention": convention,
                        "equality_parity": equality_parity,
                        "exact_one_parity": exact_one_parity,
                        "groebner_basis": list(reduced),
                        "invertible_basis_exists": reduced != ("1",),
                    }
                )
    return {
        "equality_transformed": [str(value) for value in equality],
        "cases": cases,
        "all_uniform_basis_cases_eliminated": all(
            not row["invertible_basis_exists"] for row in cases
        ),
        "scope": (
            "necessary parity condition for standard arity-three planar "
            "matchgate signatures under one uniform invertible 2x2 basis"
        ),
    }


def run(source: Path = SOURCE, output: Path = OUTPUT) -> dict[str, object]:
    source_raw = source.read_bytes()
    source_receipt = json.loads(source_raw)
    rows = []
    for case in source_receipt["cases"]:
        result = exact_cover_decision(case["formula"], case["variables"])
        expected = case["certificate"]["status"]
        if result["status"] != expected:
            raise AssertionError(f"{case['name']}: exact-cover verdict mismatch")
        rows.append(
            {
                "name": case["name"],
                "clauses": len(case["formula"]),
                "variables": case["variables"],
                "cubic_variables": len(case["certificate"]["cubic_variables"]),
                "status": expected,
                "binary_assignments_checked": case["certificate"]["branches_checked"],
                "cover_states": result["states"],
                "cover_choices": result["choices"],
                "cover_cache_hits": result["cache_hits"],
                "selected_variables": result["selected_variables"],
            }
        )
    alpha = math.log2(PUBLISHED_MONOTONE_BASE)
    crossover = 3.0 * alpha / (2.0 + alpha)
    degree_two_fixture = ((1, 2, 3), (1, 4, 5), (2, 4, 6), (3, 5, 6))
    degree_two_root_removals = [
        sum(variable in clause for clause in degree_two_fixture)
        for variable in degree_two_fixture[0]
    ]
    matchgate = uniform_matchgate_parity_analysis()
    summary = {
        "cases": len(rows),
        "all_verdicts_agree": True,
        "cover_states_below_binary_checks": sum(
            row["cover_states"] < row["binary_assignments_checked"]
            for row in rows
        ),
        "cover_states_equal_binary_checks": sum(
            row["cover_states"] == row["binary_assignments_checked"]
            for row in rows
        ),
        "cover_states_above_binary_checks": sum(
            row["cover_states"] > row["binary_assignments_checked"]
            for row in rows
        ),
        "total_binary_assignments_checked": sum(
            row["binary_assignments_checked"] for row in rows
        ),
        "total_cover_states": sum(row["cover_states"] for row in rows),
        "maximum_binary_assignments_checked": max(
            row["binary_assignments_checked"] for row in rows
        ),
        "maximum_cover_states": max(row["cover_states"] for row in rows),
        "uniform_matchgate_parity_cases": len(matchgate["cases"]),
        "uniform_matchgate_parity_cases_eliminated": sum(
            not row["invertible_basis_exists"] for row in matchgate["cases"]
        ),
    }
    receipt = {
        "schema": SCHEMA,
        "source_receipt_sha256": hashlib.sha256(source_raw).hexdigest(),
        "recurrence": {
            "all_cubic_local_case": "T(c) <= 3 T(c-3)",
            "mixed_local_case": "T(c) <= T(c-3) + 2 T(c-2)",
            "mixed_local_characteristic": "rho^3 = 2 rho + 1",
            "mixed_local_base": (1.0 + math.sqrt(5.0)) / 2.0,
            "degree_two_local_case": "T(c) <= 3 T(c-2)",
            "degree_two_fixture_root_removals": degree_two_root_removals,
            "global_cover_bound": "not established",
            "published_monotone_base_per_variable": PUBLISHED_MONOTONE_BASE,
            "published_log2_base": alpha,
            "matching_branch_preferred_below_k_over_c": crossover,
            "conclusion": (
                "Cover-state counts are empirical. The golden-ratio mixed "
                "recurrence is local and is not a global bound for this "
                "implementation."
            ),
        },
        "matchgate": matchgate,
        "cases": rows,
        "summary": summary,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return receipt


if __name__ == "__main__":
    run()
