"""Independently verify the bounded degeneracy-quotient receipt."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn, Sequence

import verify_cubic_lift_realization_probe as exact

SCHEMA = "cassifi.cubic-degeneracy-quotient-probe.v1"
ROOT = Path(__file__).resolve().parent
DEFAULT_RECEIPT = ROOT / "_diag/cubic_degeneracy_quotient_probe.json"
DEFAULT_STRUCTURE = ROOT / "_diag/cubic_degeneracy_structure_probe.json"
DEFAULT_LIFT = ROOT / "_diag/cubic_lift_realization_probe.json"

Vector = tuple[Fraction, ...]
BasisRow = tuple[tuple[int, ...], int]


class VerificationError(ValueError):
    """Raised when quotient evidence disagrees with reconstruction."""


def fail(message: str) -> NoReturn:
    raise VerificationError(message)


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    ).hexdigest()


def affine_profile(
    matrix: Sequence[Sequence[Fraction]], rhs: Sequence[Fraction]
) -> dict[str, Any]:
    column_count = len(matrix[0]) if matrix else 0
    augmented = [
        list(row) + [target] for row, target in zip(matrix, rhs, strict=True)
    ]
    reduced, pivots = exact.rref(augmented)
    if column_count in pivots:
        return {
            "consistent": False,
            "rank": len(pivots) - 1,
            "nullity": 0,
            "particular": tuple(),
            "vectors": tuple(),
        }
    coefficient_pivots = tuple(pivot for pivot in pivots if pivot < column_count)
    free = tuple(
        column for column in range(column_count) if column not in coefficient_pivots
    )
    pivot_rows = {pivot: row for row, pivot in enumerate(coefficient_pivots)}
    free_positions = {column: index for index, column in enumerate(free)}
    particular = []
    vectors = []
    for column in range(column_count):
        if column in free_positions:
            index = free_positions[column]
            particular.append(Fraction(0))
            vectors.append(
                tuple(Fraction(int(position == index)) for position in range(len(free)))
            )
        else:
            row = pivot_rows[column]
            particular.append(reduced[row][-1])
            vectors.append(tuple(-reduced[row][free_column] for free_column in free))
    return {
        "consistent": True,
        "rank": len(coefficient_pivots),
        "nullity": len(free),
        "particular": tuple(particular),
        "vectors": tuple(vectors),
    }


def basis_rows(vectors: tuple[Vector, ...]) -> tuple[BasisRow, ...]:
    if not vectors or len(vectors[0]) == 0:
        return ((tuple(), 0),)
    dimension = len(vectors[0])
    rows = []
    for selected in itertools.combinations(range(len(vectors)), dimension):
        basis = tuple(vectors[index] for index in selected)
        if exact.vector_rank(basis) != dimension:
            continue
        width = max(
            sum(coordinate != 0 for coordinate in exact.basis_coordinates(basis, vector))
            for vector in vectors
        )
        rows.append((tuple(index + 1 for index in selected), width))
    return tuple(rows)


def exclusive_pairs(rows: Sequence[BasisRow], size: int) -> list[tuple[int, int]]:
    width_two = tuple(basis for basis, width in rows if width <= 2)
    pairs = []
    for left, right in itertools.combinations(range(1, size + 1), 2):
        states = {
            f"{int(left in basis)}{int(right in basis)}" for basis in width_two
        }
        if states == {"01", "10"}:
            pairs.append((left, right))
    return pairs


def boolean_solutions(
    matrix: Sequence[Sequence[Fraction]], rhs: Sequence[Fraction]
) -> tuple[tuple[int, ...], ...]:
    size = len(matrix[0]) if matrix else 0
    return tuple(
        assignment
        for assignment in itertools.product((0, 1), repeat=size)
        if all(
            sum(
                coefficient * value
                for coefficient, value in zip(row, assignment, strict=True)
            )
            == target
            for row, target in zip(matrix, rhs, strict=True)
        )
    )


def pair_projection_allowed(
    profile: dict[str, Any], left: int, right: int
) -> tuple[tuple[int, int], ...]:
    particular = profile["particular"]
    vectors = profile["vectors"]
    allowed = []
    for pair in itertools.product((0, 1), repeat=2):
        equations = (vectors[left], vectors[right])
        targets = (
            Fraction(pair[0]) - particular[left],
            Fraction(pair[1]) - particular[right],
        )
        coefficient_rank = exact.vector_rank(equations)
        augmented_rank = exact.vector_rank(
            tuple(
                vector + (target,)
                for vector, target in zip(equations, targets, strict=True)
            )
        )
        if coefficient_rank == augmented_rank:
            allowed.append(pair)
    return tuple(allowed)


def expected_substitution(
    matrix: Sequence[Sequence[Fraction]],
    rhs: Sequence[Fraction],
    left: int,
    right: int,
    category: str,
    profile: dict[str, Any],
) -> tuple[list[list[Fraction]], list[Fraction], dict[str, Any]]:
    size = len(matrix[0])
    survivors = [index for index in range(size) if index not in (left, right)]
    old_to_new = {old: new for new, old in enumerate(survivors)}
    offset = [Fraction(0) for _ in range(size)]
    transform = [
        [Fraction(0) for _ in range(len(survivors) + 1)] for _ in range(size)
    ]
    for old, new in old_to_new.items():
        transform[old][new] = Fraction(1)
    if category == "primal_twins":
        if not all(row[left] == row[right] for row in matrix):
            fail("claimed primal twins have distinct coefficient columns")
        transform[left][-1] = Fraction(1)
        relation: dict[str, Any] = {
            "kind": "twin_sum_canonical_lift",
            "allowed_original_pairs": [[0, 0], [1, 0], [0, 1]],
            "canonical_parameter_pairs": [[0, 0], [1, 0]],
        }
    elif category == "dual_parallel":
        if exact.vector_rank((profile["vectors"][left], profile["vectors"][right])) >= 2:
            fail("claimed dual-parallel pair has rank two")
        allowed = pair_projection_allowed(profile, left, right)
        if not allowed:
            return [[Fraction(0)]], [Fraction(1)], {
                "kind": "contradiction",
                "allowed_original_pairs": [],
            }
        if len(allowed) == 1:
            transform = [row[:-1] for row in transform]
            offset[left] = Fraction(allowed[0][0])
            offset[right] = Fraction(allowed[0][1])
            relation = {
                "kind": "forced_pair",
                "allowed_original_pairs": [list(allowed[0])],
            }
        elif len(allowed) == 2:
            first, second = allowed
            offset[left] = Fraction(first[0])
            offset[right] = Fraction(first[1])
            transform[left][-1] = Fraction(second[0] - first[0])
            transform[right][-1] = Fraction(second[1] - first[1])
            relation = {
                "kind": "affine_boolean_pair",
                "allowed_original_pairs": [list(first), list(second)],
            }
        else:
            fail(f"parallel projection has {len(allowed)} Boolean pairs")
    else:
        fail(f"unknown pair category {category!r}")
    new_matrix = [
        [
            sum(
                (row[old] * transform[old][new] for old in range(size)),
                start=Fraction(0),
            )
            for new in range(len(transform[0]) if transform else 0)
        ]
        for row in matrix
    ]
    new_rhs = [
        target
        - sum(
            (row[old] * offset[old] for old in range(size)),
            start=Fraction(0),
        )
        for row, target in zip(matrix, rhs, strict=True)
    ]
    relation["survivor_old_indices"] = survivors
    relation["offset"] = [str(value) for value in offset]
    relation["transform"] = [[str(value) for value in row] for row in transform]
    return new_matrix, new_rhs, relation


def project_solution(
    assignment: tuple[int, ...], left: int, right: int, relation: dict[str, Any]
) -> tuple[int, ...]:
    projected = [assignment[index] for index in relation["survivor_old_indices"]]
    if relation["kind"] == "twin_sum_canonical_lift":
        projected.append(assignment[left] + assignment[right])
    elif relation["kind"] == "affine_boolean_pair":
        allowed = [tuple(pair) for pair in relation["allowed_original_pairs"]]
        projected.append(allowed.index((assignment[left], assignment[right])))
    return tuple(projected)


def row_signature(row: Sequence[Fraction], rhs: Fraction) -> str:
    return json.dumps(
        {
            "coefficients": [str(value) for value in sorted(value for value in row if value)],
            "rhs": str(rhs),
        },
        sort_keys=True,
    )


def terminal_details(
    matrix: list[list[Fraction]], rhs: list[Fraction], rows: Sequence[BasisRow]
) -> dict[str, Any]:
    return {
        "final_solution_count": len(boolean_solutions(matrix, rhs)),
        "final_width_two_basis_count": sum(width <= 2 for _, width in rows),
        "final_row_signature_histogram": dict(
            sorted(
                Counter(
                    row_signature(row, target)
                    for row, target in zip(matrix, rhs, strict=True)
                ).items()
            )
        ),
        "final_matrix": [[str(value) for value in row] for row in matrix],
        "final_rhs": [str(value) for value in rhs],
    }


def expected_trace(
    initial_matrix: list[list[Fraction]], initial_rhs: list[Fraction]
) -> dict[str, Any]:
    matrix = [row[:] for row in initial_matrix]
    rhs = initial_rhs[:]
    steps = []
    for _ in range(16):
        profile = affine_profile(matrix, rhs)
        size = len(matrix[0]) if matrix else 0
        if not profile["consistent"]:
            return {"steps": steps, "terminal": "contradiction"}
        rows = basis_rows(profile["vectors"])
        if profile["nullity"] <= 2:
            return {
                "steps": steps,
                "terminal": "nullity_at_most_two",
                "final_variable_count": size,
                "final_nullity": profile["nullity"],
                **terminal_details(matrix, rhs, rows),
            }
        pairs = exclusive_pairs(rows, size)
        if not pairs:
            return {
                "steps": steps,
                "terminal": "width_two_basis_without_exclusive_pair",
                "final_variable_count": size,
                "final_nullity": profile["nullity"],
                **terminal_details(matrix, rhs, rows),
            }
        left, right = pairs[0][0] - 1, pairs[0][1] - 1
        column_equal = all(row[left] == row[right] for row in matrix)
        dual_parallel = exact.vector_rank(
            (profile["vectors"][left], profile["vectors"][right])
        ) < 2
        if dual_parallel:
            category = "dual_parallel"
        elif column_equal:
            category = "primal_twins"
        else:
            return {
                "steps": steps,
                "terminal": "stuck_nondegenerate_exclusive_pair",
                "ports": [left + 1, right + 1],
            }
        original_solutions = boolean_solutions(matrix, rhs)
        if category == "primal_twins" and any(
            assignment[left] == assignment[right] == 1
            for assignment in original_solutions
        ):
            return {
                "steps": steps,
                "terminal": "stuck_twin_allows_double_one",
                "ports": [left + 1, right + 1],
            }
        new_matrix, new_rhs, relation = expected_substitution(
            matrix, rhs, left, right, category, profile
        )
        quotient_solutions = boolean_solutions(new_matrix, new_rhs)
        projected = {
            project_solution(solution, left, right, relation)
            for solution in original_solutions
        }
        if projected != set(quotient_solutions):
            fail("recursive projected solution set mismatch")
        steps.append(
            {
                "variable_count_before": size,
                "nullity_before": profile["nullity"],
                "ports": [left + 1, right + 1],
                "category": category,
                "relation_kind": relation["kind"],
                "solution_count_before": len(original_solutions),
                "solution_count_after": len(quotient_solutions),
            }
        )
        matrix, rhs = new_matrix, new_rhs
    return {"steps": steps, "terminal": "step_limit"}


def reconstruct_case(
    case: dict[str, Any], formula: Sequence[Sequence[int]]
) -> dict[str, Any]:
    size = len(formula)
    matrix = [
        [Fraction(int(variable + 1 in clause)) for variable in range(size)]
        for clause in formula
    ]
    rhs = [Fraction(1) for _ in formula]
    profile = affine_profile(matrix, rhs)
    left, right = case["ports"][0] - 1, case["ports"][1] - 1
    new_matrix, new_rhs, relation = expected_substitution(
        matrix, rhs, left, right, case["category"], profile
    )
    quotient_profile = affine_profile(new_matrix, new_rhs)
    quotient_rows = basis_rows(quotient_profile["vectors"])
    original_solutions = boolean_solutions(matrix, rhs)
    quotient_solutions = boolean_solutions(new_matrix, new_rhs)
    projected = {
        project_solution(solution, left, right, relation)
        for solution in original_solutions
    }
    if projected != set(quotient_solutions):
        fail("first quotient projected solution set mismatch")
    return {
        "canonical_family_sha256": case["canonical_family_sha256"],
        "formula_sha256": case["formula_sha256"],
        "category": case["category"],
        "ports": case["ports"],
        "relation": relation,
        "original": {
            "variable_count": size,
            "rank": profile["rank"],
            "nullity": profile["nullity"],
            "solution_count": len(original_solutions),
        },
        "quotient": {
            "variable_count": len(new_matrix[0]),
            "rank": quotient_profile["rank"],
            "nullity": quotient_profile["nullity"],
            "solution_count": len(quotient_solutions),
            "width_two_basis_count": sum(width <= 2 for _, width in quotient_rows),
            "exclusive_pairs": [
                list(pair) for pair in exclusive_pairs(quotient_rows, len(new_matrix[0]))
            ],
            "row_signature_histogram": dict(
                sorted(
                    Counter(
                        row_signature(row, target)
                        for row, target in zip(new_matrix, new_rhs, strict=True)
                    ).items()
                )
            ),
        },
        "projected_solution_set_matches": True,
        "recursive_reduction": expected_trace(new_matrix, new_rhs),
    }


def compare(expected: Any, observed: Any, path: str = "$") -> None:
    if type(expected) is not type(observed):
        fail(f"{path}: type {type(observed).__name__}, expected {type(expected).__name__}")
    if isinstance(expected, dict):
        if expected.keys() != observed.keys():
            fail(
                f"{path}: keys differ; missing={sorted(set(expected) - set(observed))}, "
                f"extra={sorted(set(observed) - set(expected))}"
            )
        for key in expected:
            compare(expected[key], observed[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if len(expected) != len(observed):
            fail(f"{path}: length {len(observed)}, expected {len(expected)}")
        for index, (left, right) in enumerate(zip(expected, observed, strict=True)):
            compare(left, right, f"{path}[{index}]")
    elif expected != observed:
        fail(f"{path}: observed {observed!r}, expected {expected!r}")


def verify(
    receipt: dict[str, Any], structure: dict[str, Any], lift: dict[str, Any]
) -> dict[str, Any]:
    if receipt.get("schema") != SCHEMA:
        fail("schema mismatch")
    compare(
        [
            "assessment",
            "case_stream_sha256",
            "cases",
            "schema",
            "selection",
            "sources",
            "summary",
        ],
        sorted(receipt),
        "$.top_level_keys",
    )
    compare(
        {
            "degeneracy_structure_schema": structure["schema"],
            "degeneracy_structure_receipt_sha256": digest(structure),
            "lift_schema": lift["schema"],
            "lift_receipt_sha256": digest(lift),
        },
        receipt["sources"],
        "$.sources",
    )
    compare(
        {
            "representative_rule": (
                "lexicographically first retained target per canonical "
                "width-two family"
            ),
            "pair_rule": "every exclusive pair of each representative",
        },
        receipt["selection"],
        "$.selection",
    )
    compare(
        {
            "bounded_result": (
                "Every quotient preserves the projected Boolean solution set "
                "and a width-two basis; every deterministic recursive path "
                "reaches a constructive terminal on the four representatives."
            ),
            "scope": (
                "Four canonical order-nine representatives and their nine "
                "exclusive pairs; not an arbitrary-order closure theorem."
            ),
        },
        receipt["assessment"],
        "$.assessment",
    )
    if digest(lift) != structure["source"]["receipt_sha256"]:
        fail("lift receipt is not the source bound by Result AA")
    formulas = {
        target["formula_sha256"]: target["formula"]
        for order in lift["orders"]
        for target in order["targets"]
        if target["status"] == "analyzed"
    }
    representatives: dict[str, dict[str, Any]] = {}
    for target in structure["targets"]:
        representatives.setdefault(
            target["canonical_width_two_family_sha256"], target
        )
    expected_keys = [
        (
            family,
            target["formula_sha256"],
            pair["category"],
            pair["ports"],
        )
        for family, target in sorted(representatives.items())
        for pair in target["exclusive_pairs"]
    ]
    observed_keys = [
        (
            case["canonical_family_sha256"],
            case["formula_sha256"],
            case["category"],
            case["ports"],
        )
        for case in receipt["cases"]
    ]
    compare(expected_keys, observed_keys, "$.case_selection")
    rebuilt_cases = [
        reconstruct_case(case, formulas[case["formula_sha256"]])
        for case in receipt["cases"]
    ]
    compare(rebuilt_cases, receipt["cases"], "$.cases")
    compare(digest(rebuilt_cases), receipt["case_stream_sha256"], "$.case_stream_sha256")

    constructive = {"nullity_at_most_two", "width_two_basis_without_exclusive_pair"}
    summary = {
        "representative_family_count": len(representatives),
        "quotient_case_count": len(rebuilt_cases),
        "category_histogram": dict(
            sorted(Counter(case["category"] for case in rebuilt_cases).items())
        ),
        "relation_histogram": dict(
            sorted(Counter(case["relation"]["kind"] for case in rebuilt_cases).items())
        ),
        "quotient_nullity_histogram": dict(
            sorted(
                Counter(str(case["quotient"]["nullity"]) for case in rebuilt_cases).items()
            )
        ),
        "quotients_with_width_two_basis": sum(
            case["quotient"]["width_two_basis_count"] > 0 for case in rebuilt_cases
        ),
        "quotients_with_exclusive_pair": sum(
            bool(case["quotient"]["exclusive_pairs"]) for case in rebuilt_cases
        ),
        "projected_solution_set_mismatches": sum(
            not case["projected_solution_set_matches"] for case in rebuilt_cases
        ),
        "recursive_terminal_histogram": dict(
            sorted(
                Counter(
                    case["recursive_reduction"]["terminal"] for case in rebuilt_cases
                ).items()
            )
        ),
        "maximum_recursive_steps_after_first_quotient": max(
            len(case["recursive_reduction"]["steps"]) for case in rebuilt_cases
        ),
        "constructive_recursive_terminals": sum(
            case["recursive_reduction"]["terminal"] in constructive
            and case["recursive_reduction"]["final_width_two_basis_count"] > 0
            for case in rebuilt_cases
        ),
    }
    compare(summary, receipt["summary"], "$.summary")
    if summary["projected_solution_set_mismatches"] != 0:
        fail("projected solution-set acceptance is nonzero")
    if summary["quotients_with_width_two_basis"] != len(rebuilt_cases):
        fail("a first quotient lost all width-two bases")
    if summary["constructive_recursive_terminals"] != len(rebuilt_cases):
        fail("a recursive path did not reach a constructive terminal")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--structure-receipt", type=Path, default=DEFAULT_STRUCTURE)
    parser.add_argument("--lift-receipt", type=Path, default=DEFAULT_LIFT)
    args = parser.parse_args()
    try:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        structure = json.loads(args.structure_receipt.read_text(encoding="utf-8"))
        lift = json.loads(args.lift_receipt.read_text(encoding="utf-8"))
        summary = verify(receipt, structure, lift)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"verification failed: cannot read receipt: {exc}") from exc
    except VerificationError as exc:
        raise SystemExit(f"verification failed: {exc}") from exc
    print(json.dumps(summary, sort_keys=True))
    print("independent verification passed")


if __name__ == "__main__":
    main()
