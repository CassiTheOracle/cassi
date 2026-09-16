from __future__ import annotations

import copy
from fractions import Fraction

import pytest

import run_cubic_degeneracy_quotient_probe as producer
import run_cubic_lift_realization_probe as lift
import verify_cubic_degeneracy_quotient_probe as verifier

DUAL_FORMULA = (
    (1, 2, 3),
    (1, 5, 9),
    (1, 8, 9),
    (2, 3, 4),
    (2, 7, 8),
    (3, 4, 6),
    (4, 5, 9),
    (5, 6, 7),
    (6, 7, 8),
)


def matrix_for(formula: tuple[tuple[int, int, int], ...]) -> list[list[Fraction]]:
    return [
        [Fraction(int(variable + 1 in clause)) for variable in range(len(formula))]
        for clause in formula
    ]


def assert_projected_solution_equivalence(
    formula: tuple[tuple[int, int, int], ...],
    ports: tuple[int, int],
    category: str,
) -> tuple[dict[str, object], list[list[Fraction]], list[Fraction]]:
    matrix = matrix_for(formula)
    rhs = [Fraction(1) for _ in formula]
    profile = producer.affine_profile(matrix, rhs)
    left, right = ports[0] - 1, ports[1] - 1
    quotient, quotient_rhs, relation = producer.substitute_pair(
        matrix, rhs, left, right, category, profile
    )
    expected_quotient, expected_rhs, expected_relation = verifier.expected_substitution(
        matrix,
        rhs,
        left,
        right,
        category,
        verifier.affine_profile(matrix, rhs),
    )
    assert quotient == expected_quotient
    assert quotient_rhs == expected_rhs
    assert relation == expected_relation

    original_solutions = producer.boolean_solutions(matrix, rhs)
    quotient_solutions = producer.boolean_solutions(quotient, quotient_rhs)
    projected = {
        producer.project_solution(solution, left, right, relation)
        for solution in original_solutions
    }
    assert projected == set(quotient_solutions)
    return relation, quotient, quotient_rhs


def test_primal_twin_sum_quotient_preserves_projected_solutions() -> None:
    formula = lift.NULLITY_THREE_CONTROL
    relation, quotient, rhs = assert_projected_solution_equivalence(
        formula, (1, 2), "primal_twins"
    )

    assert relation["kind"] == "twin_sum_canonical_lift"
    assert relation["allowed_original_pairs"] == [[0, 0], [1, 0], [0, 1]]
    profile = producer.affine_profile(quotient, rhs)
    rows = producer.basis_rows(profile["vectors"])
    assert profile["nullity"] == 2
    assert sum(width <= 2 for _, width in rows) == 13


def test_dual_parallel_equality_quotient_reaches_constructive_terminal() -> None:
    relation, quotient, rhs = assert_projected_solution_equivalence(
        DUAL_FORMULA, (1, 4), "dual_parallel"
    )

    assert relation["kind"] == "affine_boolean_pair"
    assert relation["allowed_original_pairs"] == [[0, 0], [1, 1]]
    first_profile = producer.affine_profile(quotient, rhs)
    first_rows = producer.basis_rows(first_profile["vectors"])
    assert first_profile["nullity"] == 3
    assert sum(width <= 2 for _, width in first_rows) == 4

    trace = producer.reduction_trace(quotient, rhs)
    assert trace["terminal"] == "width_two_basis_without_exclusive_pair"
    assert len(trace["steps"]) == 2
    assert trace["final_nullity"] == 3
    assert trace["final_width_two_basis_count"] == 1
    assert trace["final_solution_count"] == 4


def test_case_reconstruction_detects_relation_tampering() -> None:
    case = {
        "canonical_family_sha256": "fixture-family",
        "formula_sha256": "fixture-formula",
        "category": "dual_parallel",
        "ports": [1, 4],
    }
    expected = verifier.reconstruct_case(case, DUAL_FORMULA)
    tampered = copy.deepcopy(expected)
    tampered["relation"]["allowed_original_pairs"] = [[0, 1], [1, 0]]

    with pytest.raises(verifier.VerificationError):
        verifier.compare(expected, tampered)


def test_independent_substitution_refuses_false_pair_category() -> None:
    matrix = matrix_for(DUAL_FORMULA)
    rhs = [Fraction(1) for _ in DUAL_FORMULA]
    profile = verifier.affine_profile(matrix, rhs)

    with pytest.raises(verifier.VerificationError):
        verifier.expected_substitution(
            matrix, rhs, 0, 3, "primal_twins", profile
        )
