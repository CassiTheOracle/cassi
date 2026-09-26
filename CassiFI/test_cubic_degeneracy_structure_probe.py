from __future__ import annotations

import copy

import pytest

import run_cubic_degeneracy_structure_probe as producer
import run_cubic_lift_realization_probe as lift_producer
import verify_cubic_degeneracy_structure_probe as verifier


def test_known_cubic_target_reconstructs_the_twin_mode_independently() -> None:
    target = lift_producer.analyze_formula(lift_producer.NULLITY_THREE_CONTROL)

    produced_row, produced_profile = producer._analyze_target(target, {})
    rebuilt_row, rebuilt_profile = verifier.analyze_target(target, {})

    assert produced_row == rebuilt_row
    assert produced_profile == rebuilt_profile == {
        "order": 9,
        "rank": 6,
        "nullity": 3,
        "ordinary_basis_width_histogram": {"2": 20, "3": 4},
        "width_two_basis_count": 20,
        "dual_projective_class_sizes": [5, 1, 1, 1, 1],
        "primal_incidence_class_sizes": [2, 2, 1, 1, 1, 1, 1],
    }
    assert produced_row["exclusive_pairs"] == [
        {
            "ports": [1, 2],
            "category": "primal_twins",
            "dual_pair_rank": 2,
            "primal_incidence_identical": True,
        },
        {
            "ports": [8, 9],
            "category": "primal_twins",
            "dual_pair_rank": 2,
            "primal_incidence_identical": True,
        },
    ]
    assert produced_row["finite_mode_rule_match"] is True
    assert produced_row["degeneracy_implication_violation_count"] == 0
    assert produced_row["degenerate_nonexclusive_pair_count"] == 10


def test_general_vector_controls_prove_the_implication_check_can_fire() -> None:
    produced = producer._synthetic_controls()
    rebuilt = verifier.synthetic_controls()

    assert produced == rebuilt
    positive = produced["positive_noncubic_general_vector_configuration"]
    assert positive["exclusive_width_two"] is True
    assert positive["dual_pair_rank"] == 2
    assert positive["primal_pair_rank"] == 2
    assert positive["primal_columns_identical"] is False
    assert positive["generalized_implication_violation"] is True

    negative = produced["negative_noncubic_general_vector_configuration"]
    assert negative["width_two_states"] == ["00", "01", "10", "11"]
    assert negative["exclusive_width_two"] is False
    assert negative["generalized_implication_violation"] is False


def test_basis_family_canonicalization_is_relabeling_invariant() -> None:
    _, _, basis_rows = lift_producer.basis_profile(
        lift_producer.NULLITY_THREE_CONTROL
    )
    family = tuple(basis for basis, width in basis_rows if width <= 2)
    order = len(lift_producer.NULLITY_THREE_CONTROL)
    relabel = {vertex: order + 1 - vertex for vertex in range(1, order + 1)}
    relabeled = tuple(
        sorted(
            tuple(sorted(relabel[vertex] for vertex in basis)) for basis in family
        )
    )

    expected = producer._canonical_basis_family(family, order)
    assert producer._canonical_basis_family(relabeled, order) == expected
    assert verifier.canonical_basis_family(family, order) == expected
    assert verifier.canonical_basis_family(relabeled, order) == expected


def test_quick_receipt_reconstructs_and_rejects_evidence_tampering() -> None:
    receipt = producer.build_receipt(maximum_order=6)

    assert receipt == verifier.expected_receipt(maximum_order=6)
    summary = verifier.verify(receipt)
    assert summary["target_formulas"] == 0
    assert summary["exclusive_degenerate_pairs"] == 0
    assert summary["exclusive_nondegenerate_pairs"] == 0
    assert summary["noncubic_control_violation_fired"] is True

    mutations = []
    changed_control = copy.deepcopy(receipt)
    changed_control["synthetic_controls"][
        "positive_noncubic_general_vector_configuration"
    ]["primal_pair_rank"] = 1
    mutations.append(changed_control)

    changed_cover = copy.deepcopy(receipt)
    changed_cover["source"]["formula_cover"][-1][
        "formula_stream_sha256"
    ] = "0" * 64
    mutations.append(changed_cover)

    changed_summary = copy.deepcopy(receipt)
    changed_summary["summary"]["canonical_width_two_families"] = 1
    mutations.append(changed_summary)

    for mutation in mutations:
        with pytest.raises(verifier.VerificationError):
            verifier.verify(mutation)
