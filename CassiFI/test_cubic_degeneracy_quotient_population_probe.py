from __future__ import annotations

import copy
from fractions import Fraction
from typing import Any

import pytest

import run_cubic_degeneracy_quotient_population_probe as producer
import run_cubic_degeneracy_quotient_probe as quotient
import verify_cubic_degeneracy_quotient_population_probe as verifier
import verify_cubic_degeneracy_quotient_probe as independent

TWIN_FORMULA = (
    (1, 2, 3),
    (1, 2, 4),
    (1, 2, 5),
    (3, 4, 6),
    (3, 6, 7),
    (4, 8, 9),
    (5, 6, 7),
    (5, 8, 9),
    (7, 8, 9),
)

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


def production_case(
    formula: tuple[tuple[int, int, int], ...],
    category: str,
    ports: list[int],
) -> dict[str, Any]:
    size = len(formula)
    matrix = [
        [Fraction(int(variable + 1 in clause)) for variable in range(size)]
        for clause in formula
    ]
    rhs = [Fraction(1) for _ in formula]
    profile = quotient.affine_profile(matrix, rhs)
    solutions = quotient.boolean_solutions(matrix, rhs)
    return producer.analyze_pair(
        "fixture-formula",
        "fixture-family",
        matrix,
        rhs,
        profile,
        solutions,
        {"category": category, "ports": ports},
    )


def independent_case(
    formula: tuple[tuple[int, int, int], ...],
    category: str,
    ports: list[int],
) -> dict[str, Any]:
    return verifier.compact_case(
        {
            "formula_sha256": "fixture-formula",
            "canonical_width_two_family_sha256": "fixture-family",
        },
        {"category": category, "ports": ports},
        [list(clause) for clause in formula],
    )


def test_compact_twin_case_matches_independent_reconstruction() -> None:
    observed = production_case(TWIN_FORMULA, "primal_twins", [1, 2])
    expected = independent_case(TWIN_FORMULA, "primal_twins", [1, 2])

    assert observed == expected
    assert observed["allowed_original_pairs"] == [[0, 0], [1, 0], [0, 1]]
    assert observed["projected_solution_set_matches"] is True
    assert observed["quotient"]["nullity"] == 2
    assert observed["recursive"]["terminal"] == "nullity_at_most_two"


def test_compact_dual_case_matches_independent_recursive_evidence() -> None:
    observed = production_case(DUAL_FORMULA, "dual_parallel", [1, 4])
    expected = independent_case(DUAL_FORMULA, "dual_parallel", [1, 4])

    assert observed == expected
    assert observed["allowed_original_pairs"] == [[0, 0], [1, 1]]
    assert observed["quotient"]["nullity"] == 3
    assert observed["recursive"]["step_count"] == 2
    assert observed["recursive"]["final_width_two_basis_count"] == 1
    assert observed["recursive"]["terminal"] == "width_two_basis_without_exclusive_pair"


def test_compact_receipt_comparison_rejects_digest_tampering() -> None:
    expected = independent_case(DUAL_FORMULA, "dual_parallel", [1, 4])
    tampered = copy.deepcopy(expected)
    tampered["final_instance_sha256"] = "0" * 64

    with pytest.raises(independent.VerificationError):
        independent.compare(expected, tampered)


def test_source_join_validation_rejects_declared_pair_count_mismatch() -> None:
    target = {
        "formula_sha256": "fixture-formula",
        "order": 9,
        "exclusive_pair_count": 2,
        "exclusive_pairs": [{"category": "primal_twins", "ports": [1, 2]}],
    }

    with pytest.raises(ValueError, match="listed 1 exclusive pairs, declared 2"):
        producer.validate_target(target, TWIN_FORMULA)
    with pytest.raises(
        independent.VerificationError,
        match="listed 1 exclusive pairs, declared 2",
    ):
        verifier.validate_target(target, [list(clause) for clause in TWIN_FORMULA])


def test_source_join_validation_rejects_duplicate_lift_formula_hash() -> None:
    lift_receipt = {
        "orders": [
            {
                "targets": [
                    {
                        "formula_sha256": "duplicate",
                        "formula": [list(clause) for clause in TWIN_FORMULA],
                        "status": "analyzed",
                    },
                    {
                        "formula_sha256": "duplicate",
                        "formula": [list(clause) for clause in DUAL_FORMULA],
                        "status": "analyzed",
                    },
                ]
            }
        ]
    }

    with pytest.raises(ValueError, match="duplicate lift formula hash"):
        producer.formula_index(lift_receipt)
    with pytest.raises(
        independent.VerificationError, match="duplicate lift formula hash"
    ):
        verifier.formula_index(lift_receipt)