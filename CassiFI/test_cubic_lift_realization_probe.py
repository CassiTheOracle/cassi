from __future__ import annotations

import copy
import json

import pytest

import run_cubic_lift_realization_probe as producer
import verify_cubic_lift_realization_probe as verifier


def test_cycle_type_representatives_preserve_every_small_isomorphism_class() -> None:
    produced = producer.symmetry_completeness_control()
    rebuilt = verifier.symmetry_completeness_control()

    assert produced == rebuilt
    assert produced["all_small_order_classes_preserved"] is True
    assert [
        (
            row["order"],
            row["full_row_sorted_formulas"],
            row["representative_row_sorted_formulas"],
            row["full_isomorphism_classes"],
        )
        for row in produced["orders"]
    ] == [
        (4, 1, 1, 1),
        (5, 12, 10, 1),
        (6, 330, 136, 4),
    ]


def test_nullity_three_control_reconstructs_exact_basis_degeneracy() -> None:
    formula = producer.NULLITY_THREE_CONTROL
    produced = producer.analyze_formula(formula)
    rebuilt = verifier.analyze_formula(formula)

    assert produced == rebuilt
    assert produced["connected"] is True
    assert produced["rank"] == 6
    assert produced["nullity"] == 3
    assert produced["basis_census"]["width_two_basis_count"] == 20
    counts = produced["pair_profile"]["counts"]
    assert counts == {
        "pair_cases_checked": 36,
        "exclusive_pairs": 2,
        "rank_below_two_distinct": 0,
        "rank_below_two_identical": 0,
        "rank_two_identical": 2,
        "eligible_pairs": 0,
        "two_sided_width_barriers": 0,
    }


def test_quick_symmetry_cover_reconstructs_independently() -> None:
    produced = producer.build_receipt(maximum_order=6)
    rebuilt = verifier.expected_receipt(maximum_order=6)

    assert produced == rebuilt
    assert produced["summary"] == {
        "connected_target_formulas": 0,
        "disconnected_target_formulas": 0,
        "eligible_pairs": 0,
        "exact_nullity_at_least_three_formulas": 0,
        "exclusive_pairs": 0,
        "first_order_with_nullity_at_least_three": None,
        "maximum_order": 6,
        "minimum_order": 3,
        "modular_false_positives": 0,
        "modular_target_candidates": 0,
        "orders_screened": 4,
        "pair_cases_checked": 0,
        "rank_below_two_distinct": 0,
        "rank_below_two_identical": 0,
        "rank_two_identical": 0,
        "two_sided_width_barriers": 0,
        "unique_row_sorted_formulas": 147,
    }
    assert producer.rank_mod_prime(formula=producer.NULLITY_THREE_CONTROL) == 6
    assert verifier.rank_mod_prime(formula=verifier.NULLITY_THREE_CONTROL) == 6


def test_independent_verifier_rejects_structural_and_summary_tampering(
    tmp_path,
) -> None:
    receipt = producer.build_receipt(maximum_order=6)
    path = tmp_path / "lift.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(
        verifier.VerificationError,
        match="receipt maximum order mismatch",
    ):
        verifier.verify(path)
    assert verifier.verify(path, maximum_order=6)["status"] == "verified"

    mutations = []
    changed_control = copy.deepcopy(receipt)
    changed_control["controls"]["nullity_three_rank_two_identical_control"][
        "formula_sha256"
    ] = "0" * 64
    mutations.append(changed_control)

    changed_quotient = copy.deepcopy(receipt)
    changed_quotient["coverage_certificate"]["small_order_bruteforce_control"][
        "orders"
    ][-1]["class_stream_sha256"] = "f" * 64
    mutations.append(changed_quotient)

    changed_population = copy.deepcopy(receipt)
    changed_population["orders"][-1]["formula_stream_sha256"] = "a" * 64
    mutations.append(changed_population)

    changed_summary = copy.deepcopy(receipt)
    changed_summary["summary"]["unique_row_sorted_formulas"] += 1
    mutations.append(changed_summary)

    for index, mutation in enumerate(mutations):
        mutated_path = tmp_path / f"lift-mutated-{index}.json"
        mutated_path.write_text(json.dumps(mutation), encoding="utf-8")
        with pytest.raises(verifier.VerificationError, match="receipt mismatch"):
            verifier.verify(mutated_path, maximum_order=6)
