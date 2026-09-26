"""Behavioral regressions for the exact cubic reduction discovery system."""

from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path
from typing import Any

import pytest

import cassi_cubic_reduction as reduction
import run_cubic_reduction_discovery as runner
import verify_cubic_reduction_discovery as verifier
from run_cubic_kernel_analysis import (
    ALL_BASES_TERNARY_SAT,
    ALL_BASES_TERNARY_UNSAT,
    SUPPORT_THREE_SAT,
    SUPPORT_THREE_UNSAT,
    switched_component_family,
)


def _rehash_result(result: dict[str, object]) -> None:
    body = dict(result)
    body.pop("result_sha256", None)
    result["result_sha256"] = verifier.digest(body)


def _rehash_node(node: dict[str, object]) -> None:
    body = dict(node)
    body.pop("proof_sha256", None)
    node["proof_sha256"] = verifier.digest(body)

def _rehash_receipt(receipt: dict[str, Any]) -> None:
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = verifier.digest(body)


@pytest.fixture(scope="module")
def small_receipt() -> dict[str, Any]:
    return runner.build_receipt(random_sizes=(9,), draws_per_size=1, seed=9182)




def test_canonical_system_normalizes_scale_sign_order_and_duplicates() -> None:
    system = reduction.canonical_affine_system(
        2,
        ((-2, -4), (1, 2), (0, 0), (2, 4)),
        (-6, 3, 0, 6),
    )

    assert system.coefficients == ((1, 2),)
    assert system.rhs == (3,)
    assert system.sha256 == verifier.system_digest(
        verifier.canonical_system(2, ((1, 2),), (3,))
    )


def test_private_cover_uses_distinct_columns_only_for_nonzero_targets() -> None:
    system = reduction.canonical_affine_system(
        3,
        ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
        (1, 1, 0),
    )
    production = reduction._sparse_boolean_witness(
        system,
        reduction._WorkLedger(),
    )
    independent = verifier.sparse_boolean_witness(
        verifier.canonical_system(
            3,
            ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
            (1, 1, 0),
        ),
        verifier.AuditLedger(),
    )

    assert production == independent
    assert production is not None
    assignment, certificate = production
    assert assignment == (1, 1, 0)
    assert certificate["witness_kind"] == "private_row_cover"
    assert certificate["selected_columns"] == [1, 2]
    assert set(certificate["private_cover_columns"]) == {1, 2}
    assert len(certificate["private_cover_columns"]) == 2


def test_low_arity_projection_fast_path_matches_independent_rref() -> None:
    systems = (
        (2, (), ()),
        (2, ((1, 0),), (0,)),
        (2, ((1, 1),), (1,)),
        (3, ((1, 1, 0), (0, 1, 1)), (1, 1)),
    )
    compared = 0
    for variable_count, rows, rhs in systems:
        production_ledger = reduction._WorkLedger()
        production_profile = reduction._affine_profile(
            reduction.canonical_affine_system(variable_count, rows, rhs),
            production_ledger,
        )
        reference_ledger = verifier.AuditLedger()
        reference_profile = verifier.affine_profile(
            verifier.canonical_system(variable_count, rows, rhs),
            reference_ledger,
        )
        assert production_profile.consistent == reference_profile.consistent
        assert production_profile.consistent
        for arity in (1, 2):
            for ports in itertools.combinations(range(variable_count), arity):
                rref_calls = production_ledger.rref_calls
                observed = reduction._allowed_boolean_states(
                    production_profile,
                    ports,
                    production_ledger,
                )
                expected = verifier.allowed_states(
                    reference_profile,
                    ports,
                    reference_ledger,
                )
                assert observed == expected
                assert production_ledger.rref_calls == rref_calls
                compared += 1
    inconsistent_ledger = reduction._WorkLedger()
    inconsistent = reduction._affine_profile(
        reduction.canonical_affine_system(1, ((0,),), (1,)),
        inconsistent_ledger,
    )
    assert reduction._allowed_boolean_states(
        inconsistent,
        (0,),
        inconsistent_ledger,
    ) == ()
    free_ledger = reduction._WorkLedger()
    free = reduction._affine_profile(
        reduction.canonical_affine_system(3, (), ()),
        free_ledger,
    )
    with pytest.raises(reduction.CubicReductionError, match="one or two coordinates"):
        reduction._allowed_boolean_states(free, (0, 1, 2), free_ledger)
    assert compared == 15


def test_fixed_nullity_terminals_make_only_checked_truth_claims() -> None:
    satisfiable = reduction.solve_cubic_reduction(SUPPORT_THREE_SAT)
    unsatisfiable = reduction.solve_cubic_reduction(SUPPORT_THREE_UNSAT)
    second_unsat = reduction.solve_cubic_reduction(ALL_BASES_TERNARY_UNSAT)

    assert satisfiable["status"] == "sat"
    assert satisfiable["assignment"] is not None
    assert unsatisfiable["status"] == second_unsat["status"] == "unsat"
    for result in (satisfiable, unsatisfiable, second_unsat):
        assert result["proof"]["kind"] == "bounded_nullity_enumeration"
        assert result["assessment"]["p_equals_np_claim"] is False


def test_growing_nullity_uses_exact_pairs_then_checked_sparse_witness() -> None:
    formula = switched_component_family(5, crown_core=False)[0]
    result = reduction.solve_cubic_reduction(
        formula,
        profile=reduction.ReductionProfile(schedule_mode="fixed"),
    )
    kinds = [event["kind"] for event in result["progress"]["events"]]

    assert result["status"] == "sat"
    assert kinds == [
        "functional_pair",
        "functional_pair",
        "functional_pair",
        "functional_pair",
        "sparse_boolean_witness",
    ]
    assert result["assignment"] is not None
    assert result["assessment"]["truth_claim"] == "sat"
    assert result["progress"]["final"] == 0
    assert result["progress"]["event_count"] <= result["progress"]["event_bound"]
    assert result["representation"]["bound_respected"] is True
    assert result["resource_ledger"]["sparse_witness_candidates"] > 0


def test_nonnegative_row_bound_resolves_former_hard_core_with_checked_lift() -> None:
    formula = runner.connected_chain(
        (ALL_BASES_TERNARY_SAT, ALL_BASES_TERNARY_SAT),
        ((0, 1),),
    )
    result = reduction.solve_cubic_reduction(
        formula,
        profile=reduction.ReductionProfile(
            terminal_nullity=4,
            schedule_mode="fixed",
        ),
    )
    nodes = list(runner._proof_nodes(result["proof"]))
    bound = next(node for node in nodes if node["kind"] == "nonnegative_row_bound")
    certificate = bound["certificate"]
    system = bound["system"]
    combined = [
        sum(
            multiplier * row[column]
            for multiplier, row in zip(
                certificate["row_multipliers"],
                system["coefficients"],
                strict=True,
            )
        )
        for column in range(system["variable_count"])
    ]
    target = sum(
        multiplier * rhs
        for multiplier, rhs in zip(
            certificate["row_multipliers"],
            system["rhs"],
            strict=True,
        )
    )

    assert result["status"] == "sat"
    assert result["assignment"] is not None
    assert "nonnegative_row_bound" in [
        event["kind"] for event in result["progress"]["events"]
    ]
    assert combined == certificate["combined_coefficients"]
    assert target == certificate["combined_rhs"]
    assert target >= 0 and min(combined) >= 0
    assert combined[certificate["forced_column"] - 1] > target
    assert (
        bound["assignment"][certificate["forced_column"] - 1]
        == certificate["forced_value"]
    )
    assert all(
        sum(result["assignment"][variable - 1] for variable in clause) == 1
        for clause in formula
    )
    checked = verifier.verify_result(
        result,
        verifier.canonical_formula(formula),
        verifier.AuditLedger(),
    )
    assert checked["status"] == "sat"


def test_nonnegative_row_bound_has_a_clean_negative_control() -> None:
    production_system = reduction.canonical_affine_system(
        2,
        ((1, 1),),
        (1,),
    )
    independent_system = verifier.canonical_system(2, ((1, 1),), (1,))

    assert reduction._nonnegative_row_bound(
        production_system,
        reduction._WorkLedger(),
    ) is None
    assert verifier.nonnegative_row_bound(
        independent_system,
        verifier.AuditLedger(),
    ) is None

def test_literal_propagation_matches_exhaustive_boolean_implications() -> None:
    formula = runner.connected_chain(
        (SUPPORT_THREE_SAT, SUPPORT_THREE_SAT),
        ((0, 1),),
    )
    _, system = reduction.system_from_cubic_formula(formula)
    solutions = [
        bits
        for bits in itertools.product((0, 1), repeat=system.variable_count)
        if all(
            sum(coefficient * bit for coefficient, bit in zip(row, bits, strict=True))
            == rhs
            for row, rhs in zip(system.coefficients, system.rhs, strict=True)
        )
    ]

    for column in range(system.variable_count):
        for value in (0, 1):
            trace = reduction._propagate_literal(
                system,
                column,
                value,
                reduction._WorkLedger(),
            )
            compatible = [bits for bits in solutions if bits[column] == value]
            if trace["outcome"] == "conflict":
                assert compatible == []
                continue
            for assigned_column, assigned_value in enumerate(trace["assignment"]):
                if assigned_value is not None:
                    assert compatible
                    assert all(
                        bits[assigned_column] == assigned_value for bits in compatible
                    )
            if trace["outcome"] == "complete":
                assert tuple(trace["assignment"]) in compatible


def test_literal_probing_is_bounded_opt_in_and_independently_replayed() -> None:
    hard = runner.connected_two_lift(ALL_BASES_TERNARY_SAT, 15)
    disabled = reduction.solve_cubic_reduction(
        hard,
        profile=reduction.ReductionProfile(
            terminal_nullity=4,
            literal_probing=False,
        ),
    )
    enabled = reduction.solve_cubic_reduction(
        hard,
        profile=reduction.ReductionProfile(
            terminal_nullity=4,
            literal_probing=True,
        ),
    )

    assert disabled["status"] == "unresolved"
    assert disabled["resource_ledger"]["literal_probe_trials"] == 0
    assert enabled["status"] == "sat"
    proof = enabled["proof"]
    while proof["kind"] != "literal_probe_witness":
        proof = proof["child"]
    assert proof["certificate"]["trials_checked"] <= 2 * proof["system"]["variable_count"]
    checked = verifier.verify_result(
        enabled,
        verifier.canonical_formula(hard),
        verifier.AuditLedger(),
    )
    assert checked["status"] == "sat"


def test_literal_conflict_forcing_is_exact_and_independently_replayed() -> None:
    formula = next(
        formula
        for name, _, formula in runner.fixed_cases()
        if name == "width-three-sat-chain-two"
    )
    result = reduction.solve_cubic_reduction(
        formula,
        profile=reduction.ReductionProfile(
            terminal_nullity=4,
            literal_probing=True,
        ),
    )
    proof = result["proof"]
    while proof["kind"] != "literal_probe_forcing":
        proof = proof["child"]
    trace = proof["certificate"]["selected_trial"]

    assert trace["outcome"] == "conflict"
    assert proof["certificate"]["forced_value"] == 1 - trace["assumption"]["value"]
    assert proof["certificate"]["trials_checked"] <= 2 * proof["system"]["variable_count"]
    checked = verifier.verify_result(
        result,
        verifier.canonical_formula(formula),
        verifier.AuditLedger(),
    )
    assert checked["status"] == result["status"]


def test_cap_five_unsat_control_exhausts_exactly_thirty_two_candidates() -> None:
    formula = next(
        formula
        for name, _, formula in runner.fixed_cases()
        if name == "nullity-five-connected-unsat"
    )
    result = reduction.solve_cubic_reduction(formula)
    proof = result["proof"]
    while proof["kind"] != "bounded_nullity_enumeration":
        proof = proof["child"]

    assert result["status"] == "unsat"
    assert proof["certificate"]["nullity"] == 5
    assert proof["certificate"]["candidate_bound"] == 32
    assert proof["certificate"]["candidates_checked"] == 32
    checked = verifier.verify_result(
        result,
        verifier.canonical_formula(formula),
        verifier.AuditLedger(),
    )
    assert checked["status"] == "unsat"



def test_duplicate_components_share_exact_residual_without_persistent_cache() -> None:
    formula = runner.direct_sum(SUPPORT_THREE_SAT, SUPPORT_THREE_SAT)
    first = reduction.solve_cubic_reduction(formula)
    second = reduction.solve_cubic_reduction(formula)

    assert first["status"] == second["status"] == "sat"
    assert first["representation"]["cache_hits"] == 1
    assert "canonical_cache_hit" in [event["kind"] for event in first["progress"]["events"]]
    assert first["field_preference"]["persistence"] == "invocation_local_only"
    assert first["field_preference"]["state_sha256"] == second["field_preference"]["state_sha256"]
    assert first["result_sha256"] == second["result_sha256"]


def test_preference_field_records_exact_evidence_only_within_one_invocation() -> None:
    formula = switched_component_family(5, crown_core=False)[0]
    result = reduction.solve_cubic_reduction(
        formula,
        profile=reduction.ReductionProfile(schedule_mode="fixed"),
    )
    evidence = {
        row["strategy"]: row for row in result["field_preference"]["evidence"]
    }

    assert evidence["functional_pair"]["applicable"] == 4
    assert evidence["functional_pair"]["variables_removed"] == 4
    assert evidence["sparse_witness"]["applicable"] == 1
    assert evidence["sparse_witness"]["terminal"] == 1
    assert result["field_preference"]["preferred_order_at_large_nullity"][0] == "sparse_witness"
    fresh = reduction.solve_cubic_reduction(
        formula,
        profile=reduction.ReductionProfile(schedule_mode="fixed"),
    )
    assert fresh["field_preference"] == result["field_preference"]


def test_bounded_separator_relation_is_exact_and_lifted() -> None:
    formula = runner.connected_chain(
        (SUPPORT_THREE_SAT, ALL_BASES_TERNARY_SAT),
        ((0, 1),),
    )
    result = reduction.solve_cubic_reduction(
        formula,
        profile=reduction.ReductionProfile(
            terminal_nullity=4,
            schedule_mode="adaptive",
        ),
    )
    nodes = list(runner._proof_nodes(result["proof"]))
    separator = next(
        node for node in nodes if node["kind"] == "bounded_separator_relation"
    )
    certificate = separator["certificate"]

    assert result["status"] == "sat"
    assert result["assignment"] is not None
    assert len(certificate["separator_variables"]) == 2
    assert certificate["local_nullity"] <= 4
    assert len(certificate["feasible_separator_states"]) != 3
    assert len(certificate["state_witnesses"]) == len(
        certificate["feasible_separator_states"]
    )
    assert result["resource_ledger"]["separator_relations_enumerated"] > 0
    checked = verifier.verify_result(
        result,
        verifier.canonical_formula(formula),
        verifier.AuditLedger(),
    )
    assert checked["status"] == "sat"


def test_exported_algorithm_is_finite_uniform_and_explicitly_incomplete() -> None:
    descriptor = reduction.candidate_algorithm_descriptor()

    assert descriptor["schedule"] == {
        "kind": "fresh invocation-local exact preference field",
        "mode": "fixed",
        "field_role": "observation_only",
        "default_condition": (
            "adaptive ordering is not the default unless a held-out exact-resource "
            "ablation protects completion and beats the fixed schedule"
        ),
        "literal_probing": "disabled",
        "persistent_advice": False,
        "training_corpus": None,
        "truth_authority": "exact guards and proof checking only",
        "fallback": None,
    }
    assert [row["id"] for row in descriptor["rules"]] == [
        "drop_unconstrained_variables",
        "component_split",
        "sparse_witness",
        "bounded_nullity",
        "forced_variable",
        "functional_pair",
        "literal_probe",
        "nonnegative_row_bound",
        "bounded_separator_relation",
    ]
    assert "unresolved_residual" in descriptor["open_obligation"]
    body = dict(descriptor)
    sha256 = body.pop("descriptor_sha256")
    assert sha256 == verifier.digest(body)


def test_adversarial_generator_is_deterministic_connected_and_cubic() -> None:
    left, left_receipt = runner.random_corpus(sizes=(9, 12), draws_per_size=2, seed=1234)
    right, right_receipt = runner.random_corpus(sizes=(9, 12), draws_per_size=2, seed=1234)

    assert left == right
    assert left_receipt == right_receipt
    assert len({runner.formula_digest(formula) for _, _, formula in left}) == 4
    for _, _, formula in left:
        assert verifier.canonical_formula(formula) == formula
        assert verifier.connected(formula)
def test_structured_heldout_corpus_is_independently_reconstructed() -> None:
    produced, production_receipt = runner.structured_corpus()
    rebuilt, independent_receipt = verifier.structured_specs()

    assert produced == rebuilt
    assert production_receipt == independent_receipt
    assert len(produced) == 11
    assert production_receipt["family_counts"] == {
        "connected_two_lift": 4,
        "connected_two_switch_walk": 3,
        "growing_switched_family": 1,
        "heterogeneous_two_switch_chain": 1,
        "variable_relabeling": 2,
    }
    assert all(verifier.connected(formula) for _, _, formula in produced)




def test_connected_unswitch_minimizer_shrinks_a_connected_counterexample() -> None:
    hard = runner.connected_two_lift(SUPPORT_THREE_SAT, 11)
    source = runner.connected_chain((hard, SUPPORT_THREE_SAT), ((0, 1),))
    minimized = runner.minimize_connected_counterexample(
        source,
        profile=reduction.ReductionProfile(),
    )

    assert minimized["method"] == (
        "exhaustive_single_two_switch_disconnect_and_component_selection"
    )
    assert minimized["source_connected"] is True
    assert minimized["source_reduction"]["status"] == "unresolved"
    assert minimized["status"] == "unresolved"
    assert minimized["variables"] == 18
    assert minimized["source_variables"] == 27
    assert minimized["source_variables"] - minimized["variables"] == 9
    assert minimized["connected"] is True
    assert minimized["irreducible_under_method"] is True
    assert len(minimized["steps"]) == 1
    assert minimized["steps"][0]["disconnecting_candidate_count"] == 1
    assert minimized["terminal_scan"]["disconnecting_candidate_count"] == 0

def test_cap_five_unresolved_profile_exhausts_only_its_active_schedule() -> None:
    hard = runner.connected_two_lift(SUPPORT_THREE_SAT, 11)
    result = reduction.solve_cubic_reduction(hard)
    proof = result["proof"]
    while proof["kind"] != "unresolved_residual":
        proof = proof["child"]

    assert result["status"] == "unresolved"
    assert result["algorithm"]["profile"]["terminal_nullity"] == 5
    assert result["algorithm"]["profile"]["literal_probing"] is False
    assert "literal_probe" not in proof["certificate"]["strategy_order"]
    assert len(proof["certificate"]["attempted"]) == len(
        proof["certificate"]["strategy_order"]
    )
    checked = verifier.verify_result(
        result,
        verifier.canonical_formula(hard),
        verifier.AuditLedger(),
    )
    assert checked["status"] == "unresolved"



def test_small_receipt_is_rebuilt_and_verified_independently(
    tmp_path: Path,
    small_receipt: dict[str, Any],
) -> None:
    path = tmp_path / "receipt.json"
    path.write_text(
        json.dumps(small_receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    checked = verifier.verify(path)

    assert checked["status"] == "verified"
    assert checked["unresolved_cases"] >= 1
    assert checked["proof_checking_resource_ledger"]["proof_nodes"] > 0
    assert checked["cases"] == (
        len(runner.fixed_cases()) + len(runner.structured_corpus()[0]) + 1
    )
    ablation = small_receipt["schedule_ablation"]
    assert ablation["decision"]["adaptive_measured_benefit"] is False
    assert ablation["decision"]["selected_default_schedule_mode"] == "fixed"
    assert (
        ablation["aggregates"]["fixed"]["work_units"]
        < ablation["aggregates"]["adaptive"]["work_units"]
    )
    inference = small_receipt["inference_ablation"]
    assert inference["decision"]["metric_order"] == [
        "unresolved_cases",
        "work_units",
        "failed_rule_attempts",
        "proof_bytes",
    ]
    assert inference["decision"]["selected_default_profile_name"] == "cap5_baseline"
    assert inference["decision"]["completion_gain_cases"]["cap5_baseline"] == [
        "heldout-all-bases-sat-two-lift-seed15"
    ]
    assert inference["aggregates"]["cap5_baseline"]["unresolved_cases"] == 1




def test_independent_verifier_rejects_structured_provenance_tamper(
    tmp_path: Path,
    small_receipt: dict[str, Any],
) -> None:
    tampered = copy.deepcopy(small_receipt)
    tampered["structured_generation"]["cases"][0]["formula_sha256"] = "0" * 64
    _rehash_receipt(tampered)
    path = tmp_path / "structured-tamper.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(
        verifier.VerificationError,
        match="structured held-out generation",
    ):
        verifier.verify(path)


def test_independent_verifier_rejects_ablation_metric_tamper(
    tmp_path: Path,
    small_receipt: dict[str, Any],
) -> None:
    tampered = copy.deepcopy(small_receipt)
    tampered["schedule_ablation"]["cases"][0]["fixed"]["work_units"] += 1
    _rehash_receipt(tampered)
    path = tmp_path / "ablation-tamper.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(
        verifier.VerificationError,
        match="exact-resource metrics",
    ):
        verifier.verify(path)

def test_independent_verifier_rejects_inference_selection_tamper(
    tmp_path: Path,
    small_receipt: dict[str, Any],
) -> None:
    tampered = copy.deepcopy(small_receipt)
    tampered["inference_ablation"]["decision"][
        "selected_default_profile_name"
    ] = "cap4_literal_probe"
    _rehash_receipt(tampered)
    path = tmp_path / "inference-selection-tamper.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(
        verifier.VerificationError,
        match="inference ablation decision",
    ):
        verifier.verify(path)



def test_independent_verifier_rejects_unswitch_operation_tamper(
    tmp_path: Path,
    small_receipt: dict[str, Any],
) -> None:
    tampered = copy.deepcopy(small_receipt)
    operation = tampered["minimization"]["steps"][0][
        "disconnecting_candidates"
    ][0]["operation"]
    operation["left_variable"] += 1
    _rehash_receipt(tampered)
    path = tmp_path / "minimization-tamper.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(
        verifier.VerificationError,
        match="disconnecting candidate",
    ):
        verifier.verify(path)


def test_independent_verifier_rejects_literal_witness_coordinate_tamper() -> None:
    formula = runner.connected_two_lift(ALL_BASES_TERNARY_SAT, 15)
    tampered = copy.deepcopy(
        reduction.solve_cubic_reduction(
            formula,
            profile=reduction.ReductionProfile(
                terminal_nullity=4,
                literal_probing=True,
            ),
        )
    )
    ancestors = []
    proof = tampered["proof"]
    while proof["kind"] != "literal_probe_witness":
        ancestors.append(proof)
        proof = proof["child"]
    deduction = proof["certificate"]["selected_trial"]["deductions"][0]
    deduction["column"] = (
        deduction["column"] % proof["system"]["variable_count"]
    ) + 1
    _rehash_node(proof)
    for ancestor in reversed(ancestors):
        _rehash_node(ancestor)
    _rehash_result(tampered)

    with pytest.raises(
        verifier.VerificationError,
        match="literal-probe witness certificate",
    ):
        verifier.verify_result(
            tampered,
            verifier.canonical_formula(formula),
            verifier.AuditLedger(),
        )


def test_independent_verifier_rejects_literal_conflict_coordinate_tamper() -> None:
    formula = next(
        formula
        for name, _, formula in runner.fixed_cases()
        if name == "width-three-sat-chain-two"
    )
    tampered = copy.deepcopy(
        reduction.solve_cubic_reduction(
            formula,
            profile=reduction.ReductionProfile(
                terminal_nullity=4,
                literal_probing=True,
            ),
        )
    )
    ancestors = []
    proof = tampered["proof"]
    while proof["kind"] != "literal_probe_forcing":
        ancestors.append(proof)
        proof = proof["child"]
    conflict = proof["certificate"]["selected_trial"]["conflict"]
    conflict["row"] = (conflict["row"] % len(proof["system"]["rhs"])) + 1
    _rehash_node(proof)
    for ancestor in reversed(ancestors):
        _rehash_node(ancestor)
    _rehash_result(tampered)

    with pytest.raises(
        verifier.VerificationError,
        match="literal-probe forcing certificate",
    ):
        verifier.verify_result(
            tampered,
            verifier.canonical_formula(formula),
            verifier.AuditLedger(),
        )


def test_independent_verifier_rejects_tampered_affine_guard() -> None:
    formula = switched_component_family(5, crown_core=False)[0]
    result = reduction.solve_cubic_reduction(formula)
    tampered = copy.deepcopy(result)
    proof = tampered["proof"]
    assert proof["kind"] == "functional_pair"
    proof["certificate"]["allowed_states"] = [[0, 0]]
    _rehash_node(proof)
    _rehash_result(tampered)

    with pytest.raises(verifier.VerificationError, match="guard states"):
        verifier.verify_result(tampered, verifier.canonical_formula(formula), verifier.AuditLedger())


def test_independent_verifier_rejects_tampered_sparse_certificate() -> None:
    formula = switched_component_family(5, crown_core=False)[0]
    tampered = copy.deepcopy(
        reduction.solve_cubic_reduction(
            formula,
            profile=reduction.ReductionProfile(schedule_mode="fixed"),
        )
    )
    ancestors = []
    proof = tampered["proof"]
    while proof["kind"] != "sparse_boolean_witness":
        ancestors.append(proof)
        proof = proof["child"]
    proof["certificate"]["selected_columns"] = [1]
    _rehash_node(proof)
    for ancestor in reversed(ancestors):
        _rehash_node(ancestor)
    _rehash_result(tampered)

    with pytest.raises(
        verifier.VerificationError,
        match="sparse witness certificate disagrees on selected_columns",
    ):
        verifier.verify_result(
            tampered,
            verifier.canonical_formula(formula),
            verifier.AuditLedger(),
        )


def test_independent_verifier_rejects_tampered_row_bound_certificate() -> None:
    formula = runner.connected_chain(
        (ALL_BASES_TERNARY_SAT, ALL_BASES_TERNARY_SAT),
        ((0, 1),),
    )
    tampered = copy.deepcopy(
        reduction.solve_cubic_reduction(
            formula,
            profile=reduction.ReductionProfile(
                terminal_nullity=4,
                schedule_mode="fixed",
            ),
        )
    )
    ancestors = []
    proof = tampered["proof"]
    while proof["kind"] != "nonnegative_row_bound":
        ancestors.append(proof)
        proof = proof["child"]
    multipliers = proof["certificate"]["row_multipliers"]
    multipliers[0] = 1 if multipliers[0] == 0 else -multipliers[0]
    _rehash_node(proof)
    for ancestor in reversed(ancestors):
        _rehash_node(ancestor)
    _rehash_result(tampered)

    with pytest.raises(
        verifier.VerificationError,
        match="nonnegative row-bound certificate disagrees",
    ):
        verifier.verify_result(
            tampered,
            verifier.canonical_formula(formula),
            verifier.AuditLedger(),
        )


def test_independent_verifier_rejects_tampered_separator_witness() -> None:
    formula = runner.connected_chain(
        (SUPPORT_THREE_SAT, ALL_BASES_TERNARY_SAT),
        ((0, 1),),
    )
    tampered = copy.deepcopy(
        reduction.solve_cubic_reduction(
            formula,
            profile=reduction.ReductionProfile(
                terminal_nullity=4,
                schedule_mode="adaptive",
            ),
        )
    )
    ancestors = []
    proof = tampered["proof"]
    while proof["kind"] != "bounded_separator_relation":
        ancestors.append(proof)
        proof = proof["child"]
    witness = proof["certificate"]["state_witnesses"][0]["assignment"]
    witness[-1] ^= 1
    _rehash_node(proof)
    for ancestor in reversed(ancestors):
        _rehash_node(ancestor)
    _rehash_result(tampered)

    with pytest.raises(
        verifier.VerificationError,
        match="bounded separator certificate disagrees",
    ):
        verifier.verify_result(
            tampered,
            verifier.canonical_formula(formula),
            verifier.AuditLedger(),
        )


def test_independent_verifier_rejects_schedule_profile_proof_mismatch() -> None:
    formula = switched_component_family(5, crown_core=False)[0]
    tampered = copy.deepcopy(reduction.solve_cubic_reduction(formula))
    algorithm = tampered["algorithm"]
    algorithm["profile"]["schedule_mode"] = "adaptive"
    algorithm["profile_sha256"] = verifier.digest(
        {
            "schema": verifier.ALGORITHM_SCHEMA,
            "profile": algorithm["profile"],
        }
    )
    algorithm["schedule"]["mode"] = "adaptive"
    algorithm["schedule"]["field_role"] = "adaptive_scheduler"
    descriptor_body = dict(algorithm)
    descriptor_body.pop("descriptor_sha256")
    algorithm["descriptor_sha256"] = verifier.digest(descriptor_body)
    _rehash_result(tampered)

    with pytest.raises(
        verifier.VerificationError,
        match="strategy order|preference field reconstruction",
    ):
        verifier.verify_result(
            tampered,
            verifier.canonical_formula(formula),
            verifier.AuditLedger(),
        )


def test_independent_verifier_rejects_non_decreasing_progress() -> None:
    formula = switched_component_family(5, crown_core=False)[0]
    result = reduction.solve_cubic_reduction(formula)
    tampered = copy.deepcopy(result)
    tampered["progress"]["events"][0]["component_after"] = tampered["progress"]["events"][0]["component_before"]
    _rehash_result(tampered)

    with pytest.raises(verifier.VerificationError, match="strictly descend"):
        verifier.verify_result(tampered, verifier.canonical_formula(formula), verifier.AuditLedger())


def test_invalid_profiles_and_non_cubic_inputs_fail_closed() -> None:
    with pytest.raises(reduction.CubicReductionError, match="terminal_nullity"):
        reduction.ReductionProfile(13)
    with pytest.raises(reduction.CubicReductionError, match="schedule_mode"):
        reduction.ReductionProfile(schedule_mode="learned")
    with pytest.raises(kernel_error_type(), match="exactly three"):
        reduction.solve_cubic_reduction(((1, 2), (1, 2), (1, 2)))


def kernel_error_type() -> type[Exception]:
    return __import__("cubic_kernel_decision").CubicKernelDecisionError
