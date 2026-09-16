from __future__ import annotations

import copy
import hashlib
import json
from itertools import product
from typing import Any

import numpy as np
import pytest

from cassi_hybrid_inference import (
    HybridInferenceField,
    HybridInferenceProfile,
    HybridInferenceState,
    REGIONAL_KERNEL_MAX_WORK,
    REGIONAL_KERNEL_NAME,
    REGIONAL_STATE_SCHEMA,
    regional_kernel,
    regional_state,
)
from run_p_vs_np_hybrid_inference import (
    canonical_formula,
    connected_matched_exact_one,
    connected_matched_exact_one_labeled,
    extension_unsat,
    mixed_exact_one_even_parity,
    parity_clauses,
    pigeonhole,
    tseitin_prism,
)
from verify_hybrid_inference import (
    audit_proof,
    recognize_connected_matched_exact_one,
)


def field_for(
    variables: int,
    formula: tuple[tuple[int, ...], ...],
    *,
    extensions: int = 0,
    resolution: int = 0,
    transitions: int = 100_000,
    lines: int | None = None,
) -> HybridInferenceField:
    clauses = len(canonical_formula(formula))
    return HybridInferenceField(
        HybridInferenceProfile(
            max_variables=variables,
            max_original_clauses=clauses,
            max_lines=(
                lines
                if lines is not None
                else max(512, 5 * clauses + 16 * variables + 256)
            ),
            max_extensions=extensions,
            max_resolution_inferences=resolution,
            max_transitions=transitions,
        )
    )


def solve(
    variables: int,
    formula: tuple[tuple[int, ...], ...],
    **options: int,
) -> tuple[HybridInferenceField, HybridInferenceState, dict[str, Any]]:
    formula = canonical_formula(formula)
    field = field_for(variables, formula, **options)
    final, _ = field.solve(field.initial(formula, variable_count=variables))
    proof = field.proof(final)
    audit_proof(formula, proof, variables=variables)
    return field, final, proof


def resign(proof: dict[str, object]) -> None:
    payload = dict(proof)
    payload.pop("proof_sha256", None)
    proof["proof_sha256"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def test_counting_proof_bypasses_the_pigeonhole_resolution_obstruction() -> None:
    formula = pigeonhole(8)
    _, _, proof = solve(72, formula)
    rules = {line["rule"] for line in proof["lines"]}  # type: ignore[index]

    assert proof["status"] == "unsat"
    assert {"pb-add", "pb-scale", "pb-divide"}.issubset(rules)
    assert "resolve" not in rules


def test_parity_proof_recovers_cnf_equations_and_cancels_them() -> None:
    formula = tseitin_prism(8, odd_charge=True)
    _, _, proof = solve(24, formula)
    lines = proof["lines"]  # type: ignore[assignment]
    imported = [line for line in lines if line["rule"] == "parity-import"]

    assert proof["status"] == "unsat"
    assert len(imported) == 16
    assert all(len(line["variables"]) == 3 for line in imported)
    assert lines[proof["root_line"] - 1]["variables"] == []  # type: ignore[index,operator]
    assert lines[proof["root_line"] - 1]["rhs"] == 1  # type: ignore[index,operator]


def test_mixed_proof_requires_the_counting_to_parity_bridge() -> None:
    formula = mixed_exact_one_even_parity()
    _, _, proof = solve(3, formula, extensions=4)
    rules = [line["rule"] for line in proof["lines"]]  # type: ignore[index]

    assert proof["status"] == "unsat"
    assert "pb-divide" in rules
    assert rules.count("cardinality-parity") == 2
    assert rules[-1] == "xor-add"

def test_connected_matched_class_has_the_claimed_checked_proof_formula() -> None:
    for blocks in (4, 8):
        formula = canonical_formula(
            connected_matched_exact_one(blocks, inconsistent=True)
        )
        recognized = recognize_connected_matched_exact_one(
            formula,
            variables=3 * blocks,
        )
        _, final, proof = solve(3 * blocks, formula)
        audit = audit_proof(formula, proof, variables=3 * blocks)

        assert recognized["quotient_connected"] is True
        assert recognized["contradiction"] is True
        assert recognized["global_rhs"] == 1
        assert len(formula) == 7 * blocks
        assert proof["status"] == "unsat"
        assert audit["proof_lines"] == 25 * blocks
        assert audit["derived_lines"] == 18 * blocks
        assert audit["maximum_integer_magnitude"] == blocks
        assert final.field.nbytes == 17_928 * blocks * blocks + 55_296 * blocks


def test_every_small_edge_labeling_respects_the_global_parity_boundary() -> None:
    for blocks in (4, 6):
        contradictory = 0
        consistent = 0
        line_limit = 40 * blocks * blocks + 32 * blocks + 256
        for labels in product((0, 1), repeat=3 * blocks // 2):
            formula = canonical_formula(
                connected_matched_exact_one_labeled(blocks, labels)
            )
            recognized = recognize_connected_matched_exact_one(
                formula,
                variables=3 * blocks,
            )
            _, _, proof = solve(
                3 * blocks,
                formula,
                lines=line_limit,
            )
            if recognized["contradiction"]:
                contradictory += 1
                assert proof["status"] == "unsat"
                assert len(proof["lines"]) <= line_limit
            else:
                consistent += 1
                assert proof["status"] == "exhausted"
                assert proof["root_line"] is None

        assert contradictory == 2 ** (3 * blocks // 2 - 1)
        assert consistent == contradictory


def test_mixed_class_recognizer_rejects_disconnected_local_components() -> None:
    formula: list[tuple[int, ...]] = []
    for start in (1, 4, 7, 10):
        block = (start, start + 1, start + 2)
        formula.append(block)
        formula.extend(
            (-left, -right)
            for left, right in (
                (block[0], block[1]),
                (block[0], block[2]),
                (block[1], block[2]),
            )
        )
    for left, right in (
        (1, 4),
        (2, 5),
        (3, 6),
        (7, 10),
        (8, 11),
        (9, 12),
    ):
        formula.extend(parity_clauses((left, right), 0))

    with pytest.raises(AssertionError, match="quotient graph is disconnected"):
        recognize_connected_matched_exact_one(
            canonical_formula(tuple(formula)),
            12,
        )


def test_incomplete_parity_block_and_missing_capacity_edge_do_not_prove_unsat() -> None:
    incomplete_parity = parity_clauses((1, 2, 3), 0)[:-1] + parity_clauses((4, 5, 6), 1)
    _, _, parity_proof = solve(6, incomplete_parity)
    imported_supports = {
        tuple(line["variables"])
        for line in parity_proof["lines"]  # type: ignore[index]
        if line["rule"] == "parity-import"
    }
    _, _, counting_proof = solve(6, pigeonhole(2)[:-1])

    assert parity_proof["status"] == "exhausted"
    assert (1, 2, 3) not in imported_supports
    assert (4, 5, 6) in imported_supports
    assert counting_proof["status"] == "exhausted"
    assert counting_proof["root_line"] is None


def test_extension_definition_is_used_by_a_checked_resolution_refutation() -> None:
    formula = extension_unsat()
    _, _, proof = solve(3, formula, extensions=2, resolution=128)
    lines = proof["lines"]  # type: ignore[assignment]
    extension_lines = [line for line in lines if line["rule"] == "extension-define"]

    assert proof["status"] == "unsat"
    assert len(extension_lines) == 1
    assert extension_lines[0]["new_variable"] == 4
    assert any(line["rule"] == "resolve" and line.get("aux") == 4 for line in lines)


def test_independent_checker_rejects_semantically_false_cross_system_steps() -> None:
    formula = canonical_formula(mixed_exact_one_even_parity())
    _, _, proof = solve(3, formula, extensions=4)

    bridge_tamper = copy.deepcopy(proof)
    bridge = next(
        line
        for line in bridge_tamper["lines"]  # type: ignore[index]
        if line["rule"] == "cardinality-parity"
    )
    bridge["rhs"] ^= 1
    resign(bridge_tamper)
    with pytest.raises(AssertionError, match="false cardinality-parity inference"):
        audit_proof(formula, bridge_tamper, variables=3)

    extension_formula = canonical_formula(extension_unsat())
    _, _, extension_proof = solve(3, extension_formula, extensions=2, resolution=128)
    extension_tamper = copy.deepcopy(extension_proof)
    axiom = next(
        line
        for line in extension_tamper["lines"]  # type: ignore[index]
        if line["rule"] == "extension-clause"
    )
    axiom["literals"][-1] *= -1
    axiom["literals"].sort(key=lambda literal: (abs(literal), literal < 0))
    resign(extension_tamper)
    with pytest.raises(AssertionError, match="false extension-clause inference"):
        audit_proof(extension_formula, extension_tamper, variables=3)


def test_state_is_immutable_exactly_persistent_and_deterministic() -> None:
    formula = canonical_formula(mixed_exact_one_even_parity())
    field = field_for(3, formula, extensions=4)
    initial = field.initial(formula, variable_count=3)
    initial_copy = initial.field
    successor, transition = field.step(initial)

    assert np.array_equal(initial.field, initial_copy)
    assert transition["previous_state_sha256"] == field.state_sha256(initial)
    assert transition["state_sha256"] == field.state_sha256(successor)
    restored_field, restored = HybridInferenceField.from_descriptor(field.descriptor(successor))
    assert restored_field.state_sha256(restored) == field.state_sha256(successor)

    final_a, _ = field.solve(successor)
    final_b, _ = restored_field.solve(restored)
    assert field.state_sha256(final_a) == restored_field.state_sha256(final_b)
    assert field.proof(final_a)["proof_sha256"] == restored_field.proof(final_b)["proof_sha256"]


def test_resource_exhaustion_never_becomes_an_unsat_claim() -> None:
    formula = canonical_formula(pigeonhole(2))
    field = field_for(6, formula, transitions=1)
    final, result = field.solve(field.initial(formula, variable_count=6))
    proof = field.proof(final)

    assert result["status"] == "exhausted"
    assert proof["root_line"] is None
    assert audit_proof(formula, proof, variables=6)["status"] == "exhausted"


def test_regional_hybrid_quantum_one_round_trips_and_preserves_native_outcomes() -> None:
    assert REGIONAL_KERNEL_NAME == "exact.hybrid"
    assert REGIONAL_KERNEL_MAX_WORK > 0
    assert REGIONAL_STATE_SCHEMA.startswith("cassifi.regional-hybrid")

    def drain(state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        state = json.loads(json.dumps(state))
        intermediate: list[dict[str, Any]] = []
        for _ in range(10_000):
            result = regional_kernel(state, {}, 1)
            assert result.work <= 1
            assert result.status in {"yield", "done", "fault"}
            state = json.loads(json.dumps(result.state))
            intermediate.append(state)
            if result.status != "yield":
                return state, intermediate
        raise AssertionError("regional hybrid kernel did not terminate")

    sat_state = regional_state(((1,),), variable_count=1)
    sat_final, sat_intermediate = drain(sat_state)
    assert sat_intermediate[0]["phase"] == "running"
    assert sat_intermediate[0]["continuation"]["pc"] == 2
    assert sat_intermediate[0]["journal"]
    assert sat_final["phase"] == "terminal"
    assert sat_final["result"]["status"] == "sat"
    assert sat_final["result"]["witness"] == {"1": True}

    unsat_formula = canonical_formula(((1,), (-1,)))
    unsat_state = regional_state(unsat_formula, variable_count=1)
    unsat_final, _ = drain(unsat_state)
    expected_field = field_for(1, unsat_formula)
    expected_final, _ = expected_field.solve(
        expected_field.initial(unsat_formula, variable_count=1)
    )
    assert unsat_final["result"] == expected_field.proof(expected_final)
    assert unsat_final["result"]["status"] == "unsat"

    exhausted_state = regional_state(
        unsat_formula,
        variable_count=1,
        max_transitions=1,
    )
    exhausted_final, _ = drain(exhausted_state)
    exhausted_field = field_for(1, unsat_formula, transitions=1)
    exhausted_native, _ = exhausted_field.solve(
        exhausted_field.initial(unsat_formula, variable_count=1)
    )
    assert exhausted_final["result"] == exhausted_field.proof(exhausted_native)
    assert exhausted_final["result"]["status"] == "exhausted"
