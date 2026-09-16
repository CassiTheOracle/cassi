from __future__ import annotations

from copy import deepcopy
import json
from itertools import product

import numpy as np
import pytest

from cassi_clause_field import (
    ClauseField,
    ClauseFieldError,
    ClauseFieldProfile,
    REGIONAL_KERNEL_NAME,
    REGIONAL_KERNEL_MAX_WORK,
    REGIONAL_STATE_SCHEMA,
    regional_kernel,
    regional_state,
)
from run_p_vs_np_clause_field_probe import build_proof_certificate
from verify_p_vs_np_clause_field_probe import audit_proof


def controller(
    variables: int,
    clauses: int,
    *,
    learned: int | None = None,
    max_transitions: int = 100_000,
) -> ClauseField:
    return ClauseField(
        ClauseFieldProfile(
            max_variables=variables,
            max_original_clauses=clauses,
            max_clause_width=variables,
            max_learned_clauses=4 * variables if learned is None else learned,
            max_transitions=max_transitions,
        )
    )


def satisfies(clauses: tuple[tuple[int, ...], ...], assignment: tuple[int, ...]) -> bool:
    return all(
        any(assignment[abs(literal) - 1] == (1 if literal > 0 else -1) for literal in clause)
        for clause in clauses
    )


def satisfying_assignments(
    clauses: tuple[tuple[int, ...], ...], variables: int
) -> tuple[tuple[int, ...], ...]:
    return tuple(
        assignment
        for assignment in product((-1, 1), repeat=variables)
        if satisfies(clauses, assignment)
    )


def test_field_owned_solver_returns_sat_certificate_and_complete_unsat_result() -> None:
    sat_clauses = ((1, 2), (-1, 3), (-2, -3))
    sat_field = controller(3, len(sat_clauses))
    sat_state, sat_result = sat_field.solve(
        sat_field.initial(sat_clauses, variable_count=3)
    )
    assignment = tuple(sat_result["assignment"])
    assert sat_result["status"] == "sat"
    assert 0 not in assignment
    assert satisfies(sat_clauses, assignment)
    assert sat_result["resource_ledger"]["transitions"] > 0

    unsat_clauses = ((1,), (-1,))
    unsat_field = controller(1, len(unsat_clauses))
    _, unsat_result = unsat_field.solve(
        unsat_field.initial(unsat_clauses, variable_count=1)
    )
    assert unsat_result["status"] == "unsat"
    assert not satisfying_assignments(unsat_clauses, 1)
    assert unsat_result["resource_ledger"]["conflicts"] == 1


def test_conflict_nogoods_are_field_resident_and_logically_entailed() -> None:
    # The occurrence heuristic first tries x1=false, although the first two
    # clauses jointly imply x1. Unit propagation exposes the conflict.
    clauses = ((1, 2), (1, -2), (-1, 3), (-1, 4), (-1, 3, 4))
    field = controller(4, len(clauses))
    state, result = field.solve(field.initial(clauses, variable_count=4))
    learned = field.clauses(state, learned=True)
    models = satisfying_assignments(clauses, 4)

    assert result["status"] == "sat"
    assert result["resource_ledger"]["conflicts"] >= 1
    assert learned
    assert models
    assert all(satisfies(learned, assignment) for assignment in models)
    assert satisfies(clauses, tuple(result["assignment"]))


def test_each_step_is_immutable_and_checkpoint_roundtrip_is_exact() -> None:
    clauses = ((1, 2), (1, -2), (-1, 3), (-1, -3))
    field = controller(3, len(clauses))
    initial = field.initial(clauses, variable_count=3)
    initial_bytes = initial.field.tobytes()
    successor, receipt = field.step(initial)

    assert initial.field.tobytes() == initial_bytes
    assert receipt["previous_state_sha256"] == field.state_sha256(initial)
    assert receipt["state_sha256"] == field.state_sha256(successor)
    with pytest.raises(ValueError):
        initial._field[0, 0, 0] = 1

    restored_field, restored = ClauseField.from_descriptor(field.descriptor(successor))
    assert restored_field.profile == field.profile
    assert restored_field.state_sha256(restored) == field.state_sha256(successor)
    assert np.array_equal(restored.field, successor.field)

    final_a, result_a = field.solve(successor)
    final_b, result_b = restored_field.solve(restored)
    assert result_a == result_b
    assert field.state_sha256(final_a) == restored_field.state_sha256(final_b)


def test_unsat_run_emits_an_independently_checkable_resolution_refutation() -> None:
    clauses = ((1, 2), (-1, 2), (1, -2), (-1, -2))
    field = controller(2, len(clauses))
    state = field.initial(clauses, variable_count=2)
    conflicts: list[dict[str, object]] = []
    while field.status(state) == "running":
        state, step = field.step(state)
        if step["conflict_proof"] is not None:
            conflicts.append(dict(step["conflict_proof"]))
    result = field.inspect(state)
    proof = build_proof_certificate(conflicts, status="unsat")
    audit = audit_proof(
        clauses,
        field.clauses(state, learned=True),
        proof,
        variables=2,
        status="unsat",
        expected_conflicts=result["resource_ledger"]["conflicts"],
        max_learned_clauses=field.profile.max_learned_clauses,
    )

    assert proof["root_line"] is not None
    assert proof["closure_steps"]
    assert audit["conflict_derivations"] == result["resource_ledger"]["conflicts"]
    assert audit["leaf_resolution_steps"] == result["resource_ledger"]["proof_resolutions"]


def test_root_level_conflict_is_a_complete_one_leaf_refutation() -> None:
    clauses = ((1,), (-1,))
    field = controller(1, len(clauses))
    state = field.initial(clauses, variable_count=1)
    conflicts: list[dict[str, object]] = []
    while field.status(state) == "running":
        state, step = field.step(state)
        if step["conflict_proof"] is not None:
            conflicts.append(dict(step["conflict_proof"]))
    proof = build_proof_certificate(conflicts, status="unsat")
    result = field.inspect(state)
    audit = audit_proof(
        clauses,
        field.clauses(state, learned=True),
        proof,
        variables=1,
        status="unsat",
        expected_conflicts=result["resource_ledger"]["conflicts"],
        max_learned_clauses=field.profile.max_learned_clauses,
    )

    assert proof["root_line"] == 1
    assert proof["closure_steps"] == []
    assert audit["conflict_derivations"] == 1
    assert audit["closure_resolution_steps"] == 0


def test_independent_checker_rejects_resolution_and_closure_tampering() -> None:
    clauses = ((1, 2), (-1, 2), (1, -2), (-1, -2))
    field = controller(2, len(clauses))
    state = field.initial(clauses, variable_count=2)
    conflicts: list[dict[str, object]] = []
    while field.status(state) == "running":
        state, step = field.step(state)
        if step["conflict_proof"] is not None:
            conflicts.append(dict(step["conflict_proof"]))
    proof = build_proof_certificate(conflicts, status="unsat")
    learned = field.clauses(state, learned=True)
    ledger = field.inspect(state)["resource_ledger"]

    false_resolution = deepcopy(proof)
    false_resolution["conflict_derivations"][0]["resolution_steps"][0]["resolvent"] = []
    with pytest.raises(AssertionError, match="false resolution inference"):
        audit_proof(
            clauses,
            learned,
            false_resolution,
            variables=2,
            status="unsat",
            expected_conflicts=ledger["conflicts"],
            max_learned_clauses=field.profile.max_learned_clauses,
        )

    false_closure = deepcopy(proof)
    false_closure["closure_steps"][0]["resolvent"] = [1]
    with pytest.raises(AssertionError, match="false inference"):
        audit_proof(
            clauses,
            learned,
            false_closure,
            variables=2,
            status="unsat",
            expected_conflicts=ledger["conflicts"],
            max_learned_clauses=field.profile.max_learned_clauses,
        )




def test_transition_bound_exposes_exhaustion_without_false_decision() -> None:
    clauses = ((1, 2), (-1, 2), (1, -2), (-1, -2))
    field = controller(2, len(clauses), max_transitions=1)
    state, result = field.solve(field.initial(clauses, variable_count=2))

    assert result["status"] == "exhausted"
    assert result["resource_ledger"]["transitions"] == 1
    assert field.status(state) == "exhausted"


def test_variable_clause_and_literal_permutations_preserve_the_decision() -> None:
    clauses = ((1, 2, -3), (-1, 3), (-2, 3), (-3, 4), (-4,))
    permutation = {1: 3, 2: 1, 3: 4, 4: 2}
    permuted = tuple(
        tuple(
            (1 if literal > 0 else -1) * permutation[abs(literal)]
            for literal in reversed(clause)
        )
        for clause in reversed(clauses)
    )
    expected_sat = bool(satisfying_assignments(clauses, 4))

    outcomes: list[bool] = []
    for formula in (clauses, permuted):
        field = controller(4, len(formula))
        _, result = field.solve(field.initial(formula, variable_count=4))
        outcomes.append(result["status"] == "sat")
        if result["status"] == "sat":
            assert satisfies(formula, tuple(result["assignment"]))
    assert outcomes == [expected_sat, expected_sat]


def test_profile_capacity_and_malformed_state_fail_closed() -> None:
    with pytest.raises(ClauseFieldError, match="decision nogood"):
        ClauseFieldProfile(4, 4, 3, 4)

    field = controller(2, 1)
    with pytest.raises(ClauseFieldError, match="clause count"):
        field.initial(((1,), (2,)), variable_count=2)


    state = field.initial(((1,),), variable_count=2)
    descriptor = field.descriptor(state)
    descriptor["state_sha256"] = "0" * 64
    with pytest.raises(ClauseFieldError, match="digest mismatch"):
        ClauseField.from_descriptor(descriptor)


def test_regional_clause_quantum_one_roundtrip_resume_and_terminal_parity() -> None:
    clauses = ((1, 2), (-1, 2), (1, -2), (-1, -2))
    field = controller(2, len(clauses))
    public_state = field.initial(clauses, variable_count=2)
    public_conflicts: list[dict[str, object]] = []
    while field.status(public_state) == "running":
        public_state, receipt = field.step(public_state)
        if receipt["conflict_proof"] is not None:
            public_conflicts.append(dict(receipt["conflict_proof"]))
    public_result = field.solve(field.initial(clauses, variable_count=2))[1]
    public_proof = build_proof_certificate(public_conflicts, status="unsat")

    regional = regional_state(
        clauses,
        variable_count=2,
        profile=field.profile,
    )
    assert regional["schema"] == REGIONAL_STATE_SCHEMA
    assert REGIONAL_KERNEL_NAME == "exact.clause"
    regional = json.loads(json.dumps(regional))
    assert json.loads(json.dumps(regional)) == regional
    assert REGIONAL_KERNEL_MAX_WORK > 0
    first_assignment = list(regional["continuation"]["assignment"])
    first = regional_kernel(regional, {}, 1)
    assert first.status == "yield"
    assert first.work == 1
    assert first.state["continuation"]["assignment"] != first_assignment

    regional = first.state
    while regional["phase"] == "search":
        regional = json.loads(json.dumps(regional))
        quantum = regional_kernel(regional, {}, 1)
        assert quantum.work <= 1
        regional = quantum.state
        assert json.loads(json.dumps(regional)) == regional

    assert regional["result"]["status"] == public_result["status"] == "unsat"
    assert regional["result"]["resource_ledger"] == public_result["resource_ledger"]
    assert regional["result"]["evidence"]["proof"] == public_proof

