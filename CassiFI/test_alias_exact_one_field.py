from __future__ import annotations

import copy
import itertools
import json

import pytest
from cassi_alias_exact_one_field import (
    AliasExactOneDecisionError,
    AliasExactOneDecisionField,
    AliasExactOneProfile,
    REGIONAL_KERNEL_NAME,
    REGIONAL_KERNEL_MAX_WORK,
    REGIONAL_STATE_SCHEMA,
    recognize_degree_two_three_exact_one,
    regional_kernel,
    regional_state,
    regular_monotone_formula,
)


def variable_count(formula) -> int:
    return max(variable for clause in formula for variable in clause)


def brute_model(formula, variables: int):
    for assignment in itertools.product((0, 1), repeat=variables):
        if all(sum(assignment[variable - 1] for variable in clause) == 1 for clause in formula):
            return assignment
    return None


def assert_exact_decision(clauses: int, cubic: int, seed: int) -> str:
    formula = regular_monotone_formula(clauses, cubic, seed=seed)
    variables = variable_count(formula)
    field, initial = AliasExactOneDecisionField.initialize(
        formula,
        variable_count=variables,
    )
    final, certificate = field.solve(initial)
    expected = brute_model(formula, variables)
    assert certificate["status"] == ("sat" if expected is not None else "unsat")
    if certificate["status"] == "sat":
        assignment = certificate["assignment"]
        assert all(sum(assignment[v - 1] for v in clause) == 1 for clause in formula)
        assert len(certificate["branch_witnesses"]) == 1
    else:
        assert len(certificate["branch_witnesses"]) == 1 << cubic
        assert {row["reason"] for row in certificate["branch_witnesses"]} <= {
            "clause-conflict",
            "odd-residual",
            "tutte-barrier",
        }
    assert field.inspect(final)["status"] == certificate["status"]
    return certificate["status"]


@pytest.mark.parametrize(
    ("clauses", "cubic", "seed"),
    (
        (4, 0, 0),
        (6, 0, 1),
        (6, 2, 0),
        (8, 4, 0),
        (8, 4, 7),
        (8, 8, 0),
        (8, 8, 2),
        (10, 6, 0),
        (10, 6, 2),
        (10, 10, 0),
    ),
)
def test_alias_decisions_match_exhaustive_boolean_enumeration(
    clauses: int,
    cubic: int,
    seed: int,
) -> None:
    assert_exact_decision(clauses, cubic, seed)


def test_every_four_variable_occurrence_multiset_matches_truth_table() -> None:
    clause_types = tuple(itertools.combinations(range(1, 5), 3))
    checked = 0
    for clause_count in (3, 4):
        for formula in itertools.combinations_with_replacement(
            clause_types,
            clause_count,
        ):
            degrees = tuple(
                sum(variable in clause for clause in formula)
                for variable in range(1, 5)
            )
            if any(degree not in (2, 3) for degree in degrees):
                continue
            field, initial = AliasExactOneDecisionField.initialize(
                formula,
                variable_count=4,
            )
            _, certificate = field.solve(initial)
            expected = brute_model(formula, 4)
            assert certificate["status"] == (
                "sat" if expected is not None else "unsat"
            )
            checked += 1
    assert checked == 5


def test_persistent_field_size_is_linear_in_clause_count() -> None:
    profile = AliasExactOneProfile(
        clauses=768,
        variables=1_152,
        cubic_variables=0,
    )
    assert profile.field_values == 13 + 6 * 768
    assert profile.field_bytes == 8 * (13 + 6 * 768)


def test_degree_three_aliases_produce_both_outcomes() -> None:
    statuses = {
        assert_exact_decision(10, 6, seed)
        for seed in range(4)
    }
    assert statuses == {"sat", "unsat"}


def test_public_branch_steps_bulk_solve_and_checkpoint_are_identical() -> None:
    formula = regular_monotone_formula(8, 8, seed=0)
    field, initial = AliasExactOneDecisionField.initialize(
        formula,
        variable_count=8,
    )
    bulk, certificate = field.solve(initial)
    stepped = initial
    transitions = []
    while field.inspect(stepped)["status"] == "running":
        stepped, transition = field.step(stepped)
        transitions.append(transition)
    assert len(transitions) == 256
    assert field.state_sha256(stepped) == field.state_sha256(bulk)
    assert field.certificate(stepped) == certificate

    restored_field, restored = AliasExactOneDecisionField.from_descriptor(
        field.descriptor(stepped)
    )
    assert restored_field.certificate(restored) == certificate
    unchanged, transition = restored_field.step(restored)
    assert unchanged is restored
    assert transition["state_unchanged"] is True


def test_recognizer_and_state_fail_closed() -> None:
    formula = regular_monotone_formula(8, 4, seed=3)
    recognized = recognize_degree_two_three_exact_one(
        formula,
        variable_count=10,
    )
    assert recognized.degrees.count(3) == 4
    assert recognized.degrees.count(2) == 6

    with pytest.raises(AliasExactOneDecisionError, match="exactly two or three"):
        AliasExactOneDecisionField.initialize(((1, 2, 3),), variable_count=3)
    duplicate_clause_field, duplicate_clause_state = (
        AliasExactOneDecisionField.initialize(
            ((1, 2, 3), (1, 2, 3)),
            variable_count=3,
        )
    )
    duplicate_clause_final, duplicate_clause_certificate = (
        duplicate_clause_field.solve(duplicate_clause_state)
    )
    assert duplicate_clause_field.inspect(duplicate_clause_final)["status"] == "sat"
    assert duplicate_clause_certificate["assignment"] == [1, 0, 0]
    with pytest.raises(AliasExactOneDecisionError, match="three positive"):
        AliasExactOneDecisionField.initialize(
            ((-1, 2, 3),) + tuple(formula[1:]),
            variable_count=10,
        )
    with pytest.raises(AliasExactOneDecisionError, match="exact float64"):
        AliasExactOneProfile(1_000_000, 1_000_000, 10)
    with pytest.raises(AliasExactOneDecisionError, match="identifier range"):
        AliasExactOneProfile(1, 2**53, 0)

    field, initial = AliasExactOneDecisionField.initialize(
        formula,
        variable_count=10,
    )
    descriptor = field.descriptor(initial)
    malformed_profile = copy.deepcopy(descriptor)
    malformed_profile["profile"]["clauses"] = str(
        malformed_profile["profile"]["clauses"]
    )
    with pytest.raises(AliasExactOneDecisionError, match="profile is invalid"):
        AliasExactOneDecisionField.from_descriptor(malformed_profile)
    damaged = copy.deepcopy(descriptor)
    damaged["state_sha256"] = "0" * 64
    with pytest.raises(AliasExactOneDecisionError, match="state digest mismatch"):
        AliasExactOneDecisionField.from_descriptor(damaged)

def test_regional_alias_quantum_one_round_trip_and_native_parity() -> None:
    formula = regular_monotone_formula(8, 8, seed=0)
    native_field, native_initial = AliasExactOneDecisionField.initialize(
        formula,
        variable_count=8,
    )
    _, native_certificate = native_field.solve(native_initial)

    assert REGIONAL_KERNEL_NAME == "exact.alias-enumeration"
    assert REGIONAL_KERNEL_MAX_WORK >= 1
    state = regional_state(formula, variable_count=8)
    assert json.loads(json.dumps(state)) == state
    assert set(state) == {
        "schema",
        "source",
        "profile",
        "phase",
        "continuation",
        "journal",
        "ledger",
        "result",
    }
    assert state["schema"] == REGIONAL_STATE_SCHEMA
    first = regional_kernel(state, {}, 1)
    assert first.status == "yield"
    assert first.work == 1
    assert first.state["continuation"]["cursor"] == 1
    assert first.state != state

    state = first.state
    while first.status == "yield":
        state = json.loads(json.dumps(state))
        first = regional_kernel(state, {}, 1)
        assert first.work == 1
        state = first.state
        assert json.loads(json.dumps(state)) == state

    assert first.status == "done"
    assert first.output == native_certificate
    assert state["result"]["terminal_tensor"]["state_sha256"] == native_certificate["state_sha256"]
    assert state["result"]["outcome"] == native_certificate

    repeated = regional_kernel(json.loads(json.dumps(state)), {}, 1)
    assert repeated.status == "done"
    assert repeated.work == 0
    assert repeated.output == native_certificate
