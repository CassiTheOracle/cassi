"""Independent verification of the alias-compression analysis receipt."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any, cast

import sympy as sp

SOURCE = Path("_diag/alias_exact_one_decision.json")
RECEIPT = Path("_diag/alias_compression_analysis.json")
SCHEMA = "cassifi.alias-compression-analysis.v2"
PUBLISHED_MONOTONE_BASE = 1.0984


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def reconstruct_cover(
    formula: list[list[int]],
    variable_count: int,
) -> dict[str, Any]:
    occurrence_masks = [0] * variable_count
    for clause_index, clause in enumerate(formula):
        for variable in clause:
            occurrence_masks[variable - 1] |= 1 << clause_index
    incident: list[list[tuple[int, int]]] = [[] for _ in formula]
    for variable_index, mask in enumerate(occurrence_masks):
        for clause_index in range(len(formula)):
            if mask >> clause_index & 1:
                incident[clause_index].append((variable_index + 1, mask))

    memo: dict[int, tuple[int, ...] | None] = {}
    state_count = 0
    choice_count = 0
    cache_hit_count = 0
    missing = object()

    def search(mask: int) -> tuple[int, ...] | None:
        nonlocal state_count, choice_count, cache_hit_count
        cached = memo.get(mask, missing)
        if cached is not missing:
            cache_hit_count += 1
            return cast(tuple[int, ...] | None, cached)
        state_count += 1
        if mask == 0:
            memo[mask] = ()
            return ()
        best: tuple[int, int, tuple[tuple[int, int], ...]] | None = None
        for clause_index in range(len(formula)):
            if not (mask >> clause_index) & 1:
                continue
            choices = tuple(
                (variable, edge)
                for variable, edge in incident[clause_index]
                if edge & mask == edge
            )
            candidate = (len(choices), clause_index, choices)
            if best is None or candidate[:2] < best[:2]:
                best = candidate
        assert best is not None
        for variable, edge in best[2]:
            choice_count += 1
            suffix = search(mask ^ edge)
            if suffix is not None:
                answer = (variable, *suffix)
                memo[mask] = answer
                return answer
        memo[mask] = None
        return None

    chosen = search((1 << len(formula)) - 1)
    if chosen is not None:
        assignment = [0] * variable_count
        for variable in chosen:
            require(assignment[variable - 1] == 0, "cover repeats a variable")
            assignment[variable - 1] = 1
        require(
            all(
                sum(assignment[variable - 1] for variable in clause) == 1
                for clause in formula
            ),
            "cover assignment does not satisfy source formula",
        )
    return {
        "status": "sat" if chosen is not None else "unsat",
        "selected_variables": list(chosen) if chosen is not None else None,
        "states": state_count,
        "choices": choice_count,
        "cache_hits": cache_hit_count,
    }


def transform_signature(
    signature: tuple[int, int, int, int],
    matrix: Any,
) -> tuple[Any, ...]:
    coordinates = []
    for weight in range(4):
        output = (1,) * weight + (0,) * (3 - weight)
        value = sp.Integer(0)
        for source in itertools.product((0, 1), repeat=3):
            term = sp.Integer(signature[sum(source)])
            for position in range(3):
                term *= matrix[output[position], source[position]]
            value += term
        coordinates.append(sp.expand(value))
    return tuple(coordinates)


def reconstruct_matchgate_analysis() -> dict[str, Any]:
    a, b, c, d, inverse_det = sp.symbols("a b c d inverse_det")
    matrix = sp.Matrix(((a, b), (c, d)))
    dual_matrices = (
        ("inverse", sp.Matrix(((d, -b), (-c, a)))),
        ("inverse_transpose", sp.Matrix(((d, -c), (-b, a)))),
    )
    equality = transform_signature((1, 0, 0, 1), matrix)
    rows = []
    for convention, dual in dual_matrices:
        exact_one = transform_signature((0, 1, 0, 0), dual)
        for equality_parity in ("even", "odd"):
            for exact_one_parity in ("even", "odd"):
                equality_zero = (1, 3) if equality_parity == "even" else (0, 2)
                exact_zero = (1, 3) if exact_one_parity == "even" else (0, 2)
                ideal = [equality[index] for index in equality_zero]
                ideal += [exact_one[index] for index in exact_zero]
                ideal += [inverse_det * (a * d - b * c) - 1]
                basis = sp.groebner(
                    ideal,
                    inverse_det,
                    a,
                    b,
                    c,
                    d,
                    order="lex",
                )
                reduced = [str(polynomial.as_expr()) for polynomial in basis.polys]
                rows.append(
                    {
                        "convention": convention,
                        "equality_parity": equality_parity,
                        "exact_one_parity": exact_one_parity,
                        "groebner_basis": reduced,
                        "invertible_basis_exists": reduced != ["1"],
                    }
                )
    return {
        "equality_transformed": [str(value) for value in equality],
        "cases": rows,
        "all_uniform_basis_cases_eliminated": all(
            not row["invertible_basis_exists"] for row in rows
        ),
        "scope": (
            "necessary parity condition for standard arity-three planar "
            "matchgate signatures under one uniform invertible 2x2 basis"
        ),
    }


def exhaustive_small_equivalence() -> dict[str, int]:
    checked = 0
    sat = 0
    unsat = 0
    for variable_count in (4, 5):
        clause_types = tuple(
            itertools.combinations(range(1, variable_count + 1), 3)
        )
        minimum_clauses = math.ceil(2 * variable_count / 3)
        for clause_count in range(minimum_clauses, variable_count + 1):
            for raw_formula in itertools.combinations_with_replacement(
                clause_types,
                clause_count,
            ):
                degrees = tuple(
                    sum(variable in clause for clause in raw_formula)
                    for variable in range(1, variable_count + 1)
                )
                if any(degree not in (2, 3) for degree in degrees):
                    continue
                formula = [list(clause) for clause in raw_formula]
                reconstructed = reconstruct_cover(formula, variable_count)
                brute_sat = any(
                    all(
                        sum(assignment[variable - 1] for variable in clause)
                        == 1
                        for clause in formula
                    )
                    for assignment in itertools.product(
                        (0, 1),
                        repeat=variable_count,
                    )
                )
                require(
                    (reconstructed["status"] == "sat") == brute_sat,
                    "exhaustive exact-cover recurrence mismatch",
                )
                checked += 1
                sat += brute_sat
                unsat += not brute_sat
    return {
        "formulas": checked,
        "sat": sat,
        "unsat": unsat,
    }


def verify(
    source_path: Path = SOURCE,
    receipt_path: Path = RECEIPT,
) -> dict[str, Any]:
    source_raw = source_path.read_bytes()
    source = json.loads(source_raw)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    require(receipt.get("schema") == SCHEMA, "receipt schema mismatch")
    require(
        receipt.get("source_receipt_sha256") == hashlib.sha256(source_raw).hexdigest(),
        "source receipt digest mismatch",
    )
    source_by_name = {row["name"]: row for row in source["cases"]}
    rows = receipt.get("cases")
    require(
        isinstance(rows, list)
        and len(rows) == len(source_by_name)
        and {row.get("name") for row in rows} == set(source_by_name),
        "comparison case inventory mismatch",
    )
    audited = []
    for row in rows:
        name = row["name"]
        source_row = source_by_name[name]
        reconstructed = reconstruct_cover(
            source_row["formula"],
            source_row["variables"],
        )
        expected = {
            "name": name,
            "clauses": len(source_row["formula"]),
            "variables": source_row["variables"],
            "cubic_variables": len(source_row["certificate"]["cubic_variables"]),
            "status": source_row["certificate"]["status"],
            "binary_assignments_checked": source_row["certificate"]["branches_checked"],
            "cover_states": reconstructed["states"],
            "cover_choices": reconstructed["choices"],
            "cover_cache_hits": reconstructed["cache_hits"],
            "selected_variables": reconstructed["selected_variables"],
        }
        require(row == expected, f"{name}: comparison row mismatch")
        require(
            reconstructed["status"] == expected["status"],
            f"{name}: independently reconstructed verdict mismatch",
        )
        audited.append(expected)

    alpha = math.log2(PUBLISHED_MONOTONE_BASE)
    crossover = 3.0 * alpha / (2.0 + alpha)
    golden_ratio = (1.0 + math.sqrt(5.0)) / 2.0
    degree_two_fixture = ((1, 2, 3), (1, 4, 5), (2, 4, 6), (3, 5, 6))
    degree_two_root_removals = [
        sum(variable in clause for clause in degree_two_fixture)
        for variable in degree_two_fixture[0]
    ]
    recurrence = receipt.get("recurrence")
    require(
        recurrence
        == {
            "all_cubic_local_case": "T(c) <= 3 T(c-3)",
            "mixed_local_case": "T(c) <= T(c-3) + 2 T(c-2)",
            "mixed_local_characteristic": "rho^3 = 2 rho + 1",
            "mixed_local_base": golden_ratio,
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
        "recurrence analysis mismatch",
    )
    require(
        abs(golden_ratio**3 - 2.0 * golden_ratio - 1.0) < 1e-12,
        "mixed local recurrence root mismatch",
    )
    require(
        degree_two_root_removals == [2, 2, 2],
        "degree-two local counterexample mismatch",
    )

    matchgate = reconstruct_matchgate_analysis()
    require(receipt.get("matchgate") == matchgate, "matchgate elimination mismatch")
    require(matchgate["all_uniform_basis_cases_eliminated"], "uniform basis survived")
    exhaustive = exhaustive_small_equivalence()
    summary = {
        "cases": len(audited),
        "all_verdicts_agree": True,
        "cover_states_below_binary_checks": sum(
            row["cover_states"] < row["binary_assignments_checked"]
            for row in audited
        ),
        "cover_states_equal_binary_checks": sum(
            row["cover_states"] == row["binary_assignments_checked"]
            for row in audited
        ),
        "cover_states_above_binary_checks": sum(
            row["cover_states"] > row["binary_assignments_checked"]
            for row in audited
        ),
        "total_binary_assignments_checked": sum(
            row["binary_assignments_checked"] for row in audited
        ),
        "total_cover_states": sum(row["cover_states"] for row in audited),
        "maximum_binary_assignments_checked": max(
            row["binary_assignments_checked"] for row in audited
        ),
        "maximum_cover_states": max(row["cover_states"] for row in audited),
        "uniform_matchgate_parity_cases": len(matchgate["cases"]),
        "uniform_matchgate_parity_cases_eliminated": sum(
            not row["invertible_basis_exists"] for row in matchgate["cases"]
        ),
    }
    require(receipt.get("summary") == summary, "summary mismatch")
    result = {
        **summary,
        "source_digest_checked": True,
        "recurrence_checked": True,
        "matchgate_ideals_recomputed": True,
        "exhaustive_small_formulas": exhaustive["formulas"],
        "exhaustive_small_sat": exhaustive["sat"],
        "exhaustive_small_unsat": exhaustive["unsat"],
    }
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    verify()
