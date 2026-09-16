from __future__ import annotations

import itertools
import json

import pytest

from cassi_alias_exact_one_field import regular_monotone_formula, recognize_degree_two_three_exact_one
from cassi_alias_obstruction import evaluate_alias_candidate
from cassi_alias_cut_field import (
    AliasCutError,
    AliasCutField,
    REGIONAL_KERNEL_MAX_WORK,
    REGIONAL_KERNEL_NAME,
    REGIONAL_STATE_SCHEMA,
    regional_kernel,
    regional_state,
)
from verify_alias_cut_field import verify_obstruction_cut, verify_result


def variable_count(formula: tuple[tuple[int, ...], ...] | list[list[int]]) -> int:
    return max(variable for clause in formula for variable in clause)


def relabel_formula(
    formula: tuple[tuple[int, ...], ...] | list[list[int]],
    mapping: dict[int, int],
) -> list[list[int]]:
    return sorted([sorted(mapping[variable] for variable in clause) for clause in formula])



def brute_model(formula: list[list[int]], variables: int) -> list[int] | None:
    for assignment in itertools.product((0, 1), repeat=variables):
        if all(sum(assignment[variable - 1] for variable in clause) == 1 for clause in formula):
            return list(assignment)
    return None


def test_each_small_obstruction_cut_is_independently_verified() -> None:
    formula = [list(clause) for clause in regular_monotone_formula(8, 4, seed=3)]
    variables = variable_count(formula)
    recognized = recognize_degree_two_three_exact_one(formula, variable_count=variables)
    cubic_positions = {variable: index for index, variable in enumerate(recognized.cubic_variables)}
    unsat_kinds: set[str] = set()

    for bits in itertools.product((0, 1), repeat=len(recognized.cubic_variables)):
        candidate = evaluate_alias_candidate(recognized, bits)
        if candidate["status"] == "sat":
            assert candidate["cut"] is None
            assert all(
                sum(candidate["assignment"][variable - 1] for variable in clause) == 1
                for clause in formula
            )
            continue
        cut = candidate["cut"]
        assert cut is not None
        report = verify_obstruction_cut(formula, variables, cut)
        unsat_kinds.add(report["kind"])
        # The projected clause is false at the exact alias cube that produced it.
        assert all(
            not ((bits[cubic_positions[abs(literal)]] == 1) if literal > 0 else (bits[cubic_positions[abs(literal)]] == 0))
            for literal in cut["literals"]
        )

    assert unsat_kinds == {"overfill", "tutte"}


def test_cut_solver_supports_noncontiguous_cubic_ids() -> None:
    base = regular_monotone_formula(8, 4, seed=0)
    mapping = {
        1: 2, 2: 4, 3: 7, 4: 10,
        5: 1, 6: 3, 7: 5, 8: 6, 9: 8, 10: 9,
    }
    formula = relabel_formula(base, mapping)
    variables = variable_count(formula)
    recognized = recognize_degree_two_three_exact_one(formula, variable_count=variables)
    assert recognized.cubic_variables == (2, 4, 7, 10)
    assert recognized.cubic_variables != tuple(range(1, len(recognized.cubic_variables) + 1))

    for bits in itertools.product((0, 1), repeat=len(recognized.cubic_variables)):
        candidate = evaluate_alias_candidate(recognized, bits)
        if candidate["status"] == "unsat":
            assert candidate["cut"] is not None
            verify_obstruction_cut(formula, variables, candidate["cut"])

    field, initial = AliasCutField.initialize(formula, variable_count=variables)

    final, result = field.solve(initial)
    expected = "sat" if brute_model(formula, variables) is not None else "unsat"
    assert result["status"] == expected
    assert result["cubic_variables"] == [2, 4, 7, 10]
    assert result["cuts"]
    assert verify_result(result)["status"] == expected
    assert field.inspect(final)["status"] == expected


@pytest.mark.parametrize(
    ("clauses", "cubic", "seed"),
    ((6, 2, 0), (6, 2, 1), (8, 4, 3), (10, 6, 2), (10, 6, 0)),
)
def test_cut_solver_matches_exact_control_and_independent_result_audit(
    clauses: int,
    cubic: int,
    seed: int,
) -> None:
    formula = [list(clause) for clause in regular_monotone_formula(clauses, cubic, seed=seed)]
    variables = variable_count(formula)
    field, initial = AliasCutField.initialize(formula, variable_count=variables)
    final, result = field.solve(initial)
    expected = "sat" if brute_model(formula, variables) is not None else "unsat"
    assert result["status"] == expected
    assert verify_result(result)["status"] == expected
    assert field.inspect(final)["status"] == expected


def test_cut_solver_checkpoint_roundtrip_preserves_complete_result() -> None:
    formula = [list(clause) for clause in regular_monotone_formula(8, 4, seed=3)]
    variables = variable_count(formula)
    field, initial = AliasCutField.initialize(formula, variable_count=variables)
    final, result = field.solve(initial)
    restored_field, restored_state = AliasCutField.from_descriptor(field.descriptor(final))
    assert restored_field.state_sha256(restored_state) == field.state_sha256(final)
    assert restored_field.result(restored_state) == result
    unchanged, transition = restored_field.step(restored_state)
    assert unchanged is restored_state
    assert transition["status"] == result["status"]


def test_cut_solver_exhaustion_carries_no_false_assignment_or_refutation() -> None:
    formula = [list(clause) for clause in regular_monotone_formula(6, 2, seed=1)]
    variables = variable_count(formula)
    field, initial = AliasCutField.initialize(
        formula,
        variable_count=variables,
        max_cuts=0,
        max_steps=100,
    )
    _, result = field.solve(initial)
    assert result["status"] == "exhausted"
    assert result["assignment"] is None
    assert result["alias_assignment"] is None
    assert result["proof"] is None
    assert verify_result(result)["status"] == "exhausted"


def test_cut_state_is_a_snapshot_and_rejects_profile_mismatch() -> None:
    formula = [list(clause) for clause in regular_monotone_formula(6, 2, seed=0)]
    variables = variable_count(formula)
    field, initial = AliasCutField.initialize(formula, variable_count=variables)
    before = field.state_sha256(initial)
    snapshot = initial.field
    snapshot.reshape(-1)[0] = 0
    assert field.state_sha256(initial) == before
    other, other_state = AliasCutField.initialize(formula, variable_count=variables, max_cuts=4)
    assert other.profile.fingerprint != field.profile.fingerprint
    with pytest.raises(AliasCutError, match="state/profile mismatch"):
        other.validate(initial)
    assert other_state.profile_sha256 == other.profile.fingerprint


def test_regional_alias_cut_quantum_roundtrip_resume_matches_public_result() -> None:
    formula = [
        [1, 2, 7],
        [1, 3, 7],
        [2, 3, 7],
        [4, 5, 8],
        [4, 6, 8],
        [5, 6, 8],
    ]
    variables = variable_count(formula)
    regional = regional_state(
        formula,
        variable_count=variables,
        max_steps=1000,
    )
    assert REGIONAL_KERNEL_NAME == "exact.alias-cut"
    assert REGIONAL_KERNEL_MAX_WORK > 0
    assert REGIONAL_STATE_SCHEMA.endswith("-state.v3")
    assert set(regional) == {
        "schema", "source", "profile", "phase",
        "continuation", "journal", "ledger", "result",
    }
    assert regional["result"] is None
    assert regional["ledger"]["steps"] == 0
    first = regional_kernel(
        json.loads(json.dumps(regional, sort_keys=True, allow_nan=False)),
        {},
        1,
    )
    assert first.status == "yield"
    assert first.work <= 1
    regional = json.loads(json.dumps(first.state, sort_keys=True, allow_nan=False))
    assert regional["ledger"]["steps"] == 1
    assert regional["continuation"]["candidate_cursor"]["index"] == 1
    assert regional["continuation"]["frontier"]["next_candidate"] != [0, 0]

    while True:
        checkpoint = json.loads(json.dumps(regional, sort_keys=True, allow_nan=False))
        transition = regional_kernel(checkpoint, {}, 1)
        regional = json.loads(json.dumps(transition.state, sort_keys=True, allow_nan=False))
        if transition.status == "done":
            break
        assert transition.status == "yield"
        assert transition.work <= 1
        assert regional["result"] is None

    public_field, public_initial = AliasCutField.initialize(
        formula,
        variable_count=variables,
        max_steps=1000,
    )
    _public_final, public_result = public_field.solve(public_initial)
    assert regional["result"]["status"] == public_result["status"]
    assert regional["result"]["reason"] == public_result["reason"]
    assert regional["journal"]["proof"] == regional["result"]["proof"]
    expected_evidence = (
        "sat-witness"
        if public_result["status"] == "sat"
        else "unsat-certificate"
    )
    assert regional["journal"]["evidence"]["kind"] == expected_evidence
    assert regional["ledger"]["status"] == public_result["work"]["status"]
