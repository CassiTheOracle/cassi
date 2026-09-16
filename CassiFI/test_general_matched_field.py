from __future__ import annotations

import copy
import itertools
import json
from typing import Sequence

import pytest

from cassi_general_matched_field import (
    GeneralMatchedDecisionError,
    GeneralMatchedDecisionField,
    GeneralMatchedProfile,
    REGIONAL_KERNEL_MAX_WORK,
    REGIONAL_KERNEL_NAME,
    REGIONAL_STATE_SCHEMA,
    matched_formula_from_topology,
    recognize_connected_matched_exact_one,
    regional_kernel,
    regional_state,
)


K4 = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
PARALLEL_K4 = ((0, 1), (0, 1), (2, 3), (2, 3), (0, 2), (1, 3))
PRISM6 = (
    (0, 1),
    (1, 2),
    (2, 0),
    (3, 4),
    (4, 5),
    (5, 3),
    (0, 3),
    (1, 4),
    (2, 5),
)
K33 = tuple((left, right) for left in range(3) for right in range(3, 6))
PETERSEN = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (4, 0),
    (5, 7),
    (7, 9),
    (9, 6),
    (6, 8),
    (8, 5),
    (0, 5),
    (1, 6),
    (2, 7),
    (3, 8),
    (4, 9),
)



def assignment_satisfies(formula: Sequence[Sequence[int]], assignment: Sequence[int]) -> bool:
    return all(
        any(
            assignment[abs(literal) - 1] == (1 if literal > 0 else 0)
            for literal in clause
        )
        for clause in formula
    )


def exact_one_has_model(formula: Sequence[Sequence[int]], variables: int) -> bool:
    recognized = recognize_connected_matched_exact_one(
        formula,
        variable_count=variables,
    )
    assignment = [0] * variables
    for choices in itertools.product(range(3), repeat=len(recognized.blocks)):
        assignment[:] = [0] * variables
        for block, choice in zip(recognized.blocks, choices):
            assignment[block[choice] - 1] = 1
        if assignment_satisfies(recognized.formula, assignment):
            return True
    return False


def component_sizes(vertex_count: int, edges: Sequence[Sequence[int]], removed: set[int]) -> list[int]:
    adjacency = [set() for _ in range(vertex_count)]
    for left, right, _ in edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    unseen = set(range(vertex_count)) - removed
    result = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        stack = [start]
        size = 0
        while stack:
            vertex = stack.pop()
            size += 1
            for neighbor in adjacency[vertex]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        result.append(size)
    return result


def assert_checked_decision(formula: Sequence[Sequence[int]], blocks: int) -> str:
    field, initial = GeneralMatchedDecisionField.initialize(
        formula,
        variable_count=3 * blocks,
    )
    final, certificate = field.solve(initial)
    expected_sat = exact_one_has_model(formula, 3 * blocks)
    assert certificate["status"] == ("sat" if expected_sat else "unsat")
    if expected_sat:
        assert assignment_satisfies(formula, certificate["assignment"])
        assert len(certificate["matching"]) * 2 == certificate["auxiliary_vertices"]
    else:
        barrier = set(certificate["tutte_barrier"])
        sizes = component_sizes(
            certificate["auxiliary_vertices"],
            certificate["auxiliary_edges"],
            barrier,
        )
        assert sizes == certificate["component_sizes"]
        assert sum(size % 2 for size in sizes) > len(barrier)
    assert field.inspect(final)["status"] == certificate["status"]
    return certificate["status"]


@pytest.mark.parametrize("topology", (K4, PARALLEL_K4))
def test_every_four_block_labeling_matches_independent_enumeration(topology) -> None:
    statuses = set()
    for labels in itertools.product((0, 1), repeat=6):
        formula = matched_formula_from_topology(4, topology, labels)
        statuses.add(assert_checked_decision(formula, 4))
    assert statuses == {"sat", "unsat"}


def test_prism_labelings_include_parity_consistent_unsat_cases() -> None:
    counts = {"sat": 0, "unsat": 0, "parity_consistent_unsat": 0}
    for labels in itertools.product((0, 1), repeat=9):
        formula = matched_formula_from_topology(6, PRISM6, labels)
        status = assert_checked_decision(formula, 6)
        counts[status] += 1
        if status == "unsat" and sum(labels) % 2 == 0:
            counts["parity_consistent_unsat"] += 1
    assert counts == {"sat": 241, "unsat": 271, "parity_consistent_unsat": 15}


@pytest.mark.parametrize(
    ("blocks", "topology"),
    ((6, K33), (10, PETERSEN)),
)
def test_distinct_cubic_topologies_match_independent_enumeration(
    blocks: int,
    topology,
) -> None:
    patterns = (
        (0,) * len(topology),
        (1,) * len(topology),
        tuple(index % 2 for index in range(len(topology))),
        tuple(((index * index + 3 * index) ^ (index >> 1)) & 1 for index in range(len(topology))),
    )
    statuses = {
        assert_checked_decision(
            matched_formula_from_topology(blocks, topology, labels),
            blocks,
        )
        for labels in patterns
    }
    assert statuses == {"sat", "unsat"}


def test_public_steps_bulk_solve_and_checkpoint_are_identical() -> None:
    labels = (1, 0, 1, 1, 0, 1, 0, 1, 0)
    formula = matched_formula_from_topology(6, PRISM6, labels)
    field, initial = GeneralMatchedDecisionField.initialize(formula, variable_count=18)
    bulk, bulk_certificate = field.solve(initial)
    stepped = initial
    transitions = []
    while field.inspect(stepped)["status"] == "running":
        stepped, transition = field.step(stepped)
        transitions.append(transition)
    assert field.state_sha256(stepped) == field.state_sha256(bulk)
    assert field.certificate(stepped) == bulk_certificate
    assert len(transitions) == field.profile.auxiliary_vertices

    restored_field, restored = GeneralMatchedDecisionField.from_descriptor(
        field.descriptor(stepped)
    )
    assert restored_field.certificate(restored) == bulk_certificate
    unchanged, transition = restored_field.step(restored)
    assert unchanged is restored
    assert transition["state_unchanged"] is True


@pytest.mark.parametrize(
    "labels",
    ((0, 0, 0, 0, 0, 0), (1, 1, 1, 1, 1, 1)),
)
def test_matched_regional_quantum_one_roundtrip_and_native_parity(labels) -> None:
    formula = matched_formula_from_topology(4, K4, labels)
    field, initial = GeneralMatchedDecisionField.initialize(
        formula,
        variable_count=12,
    )
    _, expected = field.solve(initial)
    state = regional_state(formula, variable_count=12)
    assert REGIONAL_KERNEL_NAME == "exact.matched"
    assert REGIONAL_KERNEL_MAX_WORK > 0
    assert state["schema"] == REGIONAL_STATE_SCHEMA
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

    first_successor = None
    for _ in range(10_000):
        state = json.loads(json.dumps(state, sort_keys=True))
        outcome = regional_kernel(state, {}, 1)
        assert outcome.work <= 1
        successor = json.loads(json.dumps(outcome.state, sort_keys=True))
        if first_successor is None:
            first_successor = successor
            assert successor["ledger"]["cumulative_work"] == 1
            assert successor["phase"] == "matching"
            assert successor["continuation"] != state["continuation"]
        state = successor
        if outcome.status == "done":
            break
        assert outcome.status == "yield"
    else:
        pytest.fail("quantum-one regional matched search did not terminate")

    regional_result = dict(state["result"])
    public_result = dict(expected)
    regional_result.pop("state_sha256")
    regional_result.pop("certificate_sha256")
    public_result.pop("state_sha256")
    public_result.pop("certificate_sha256")
    assert regional_result == public_result
    assert outcome.output == state["result"]
    assert expected["status"] in {"sat", "unsat"}
    if expected["status"] == "sat":
        assignment = state["result"]["assignment"]
        assert assignment is not None
        assert all(
            any(
                assignment[abs(literal) - 1]
                == (1 if literal > 0 else 0)
                for literal in clause
            )
            for clause in formula
        )
    else:
        assert state["result"]["tutte_barrier"] == expected["tutte_barrier"]


def test_tampered_checkpoint_and_malformed_formulas_fail_closed() -> None:
    formula = matched_formula_from_topology(4, K4, (1, 1, 1, 1, 1, 1))
    field, initial = GeneralMatchedDecisionField.initialize(formula, variable_count=12)
    descriptor = field.descriptor(initial)
    damaged = copy.deepcopy(descriptor)
    damaged["state_sha256"] = "0" * 64
    with pytest.raises(GeneralMatchedDecisionError, match="state digest mismatch"):
        GeneralMatchedDecisionField.from_descriptor(damaged)
    with pytest.raises(GeneralMatchedDecisionError, match="duplicate clauses"):
        GeneralMatchedDecisionField.initialize(
            tuple(formula) + (formula[0],),
            variable_count=12,
        )
    with pytest.raises(GeneralMatchedDecisionError, match="disconnected"):
        matched_formula = matched_formula_from_topology(
            4,
            ((0, 1), (0, 1), (0, 1), (2, 3), (2, 3), (2, 3)),
            (0, 0, 0, 0, 0, 0),
        )
        GeneralMatchedDecisionField.initialize(matched_formula, variable_count=12)

    with pytest.raises(GeneralMatchedDecisionError, match="exact float64"):
        GeneralMatchedProfile(1_000_000, 0)
    with pytest.raises(GeneralMatchedDecisionError, match="must be integers"):
        GeneralMatchedProfile(True, 0)