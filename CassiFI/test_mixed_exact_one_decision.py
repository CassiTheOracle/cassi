from __future__ import annotations

import base64
import itertools
import json

import pytest

from cassi_mixed_exact_one_field import (
    CanonicalMixedDecisionField,
    CanonicalMixedDecisionProfile,
    MixedExactOneDecisionError,
    REGIONAL_KERNEL_MAX_WORK,
    REGIONAL_KERNEL_NAME,
    REGIONAL_STATE_SCHEMA,
    canonical_formula_from_labels,
    regional_kernel,
    regional_state,
)


def label_signature(blocks: int, selected_ports: tuple[int, ...]) -> tuple[int, ...]:
    def value(block: int, port: int) -> int:
        return int(selected_ports[block] == port)

    labels = [
        value(block, 1) ^ value((block + 1) % blocks, 0)
        for block in range(blocks)
    ]
    labels.extend(
        value(block, 2) ^ value(block + 1, 2)
        for block in range(0, blocks, 2)
    )
    return tuple(labels)


def achievable_labels(blocks: int) -> set[tuple[int, ...]]:
    return {
        label_signature(blocks, selected_ports)
        for selected_ports in itertools.product(range(3), repeat=blocks)
    }


def satisfies(formula: tuple[tuple[int, ...], ...], assignment: list[int]) -> bool:
    return all(
        any(
            assignment[abs(literal) - 1] == (1 if literal > 0 else 0)
            for literal in clause
        )
        for clause in formula
    )


@pytest.mark.parametrize("blocks", [4, 6])
def test_every_small_labeling_matches_independent_exact_one_enumeration(blocks: int) -> None:
    reachable = achievable_labels(blocks)
    field = CanonicalMixedDecisionField(CanonicalMixedDecisionProfile(blocks))
    sat = 0
    unsat = 0
    for labels in itertools.product((0, 1), repeat=3 * blocks // 2):
        formula = canonical_formula_from_labels(blocks, labels)
        final, certificate = field.solve(field.initial(formula, variable_count=3 * blocks))
        expected_sat = labels in reachable
        assert (certificate["status"] == "sat") is expected_sat
        assert field.inspect(final)["status"] == certificate["status"]
        if expected_sat:
            sat += 1
            assert satisfies(formula, certificate["assignment"])
        else:
            unsat += 1
            assert certificate["assignment"] is None
    assert (sat, unsat) == ({4: (31, 33), 6: (235, 277)}[blocks])


def test_step_checkpoint_and_bulk_solve_are_exactly_equivalent() -> None:
    blocks = 12
    labels = tuple(index % 3 == 0 for index in range(3 * blocks // 2))
    formula = canonical_formula_from_labels(blocks, labels)
    field = CanonicalMixedDecisionField(CanonicalMixedDecisionProfile(blocks))
    initial = field.initial(formula, variable_count=3 * blocks)
    stepped = initial
    transitions = []
    while field.inspect(stepped)["status"] == "running":
        stepped, transition = field.step(stepped)
        transitions.append(transition)
    solved, certificate = field.solve(initial)
    assert field.state_sha256(stepped) == field.state_sha256(solved)
    assert len(transitions) == blocks // 2
    assert [transition["pair"] for transition in transitions] == list(range(blocks // 2))
    restored_field, restored = CanonicalMixedDecisionField.from_descriptor(
        field.descriptor(solved)
    )
    assert restored_field.state_sha256(restored) == field.state_sha256(solved)
    assert restored_field.certificate(restored) == certificate


@pytest.mark.parametrize("labels", [(0,) * 6, (1,) + (0,) * 5])
def test_regional_quantum_one_json_roundtrip_resumes_exact_terminal_evidence(
    labels: tuple[int, ...],
) -> None:
    blocks = 4
    formula = canonical_formula_from_labels(blocks, labels)
    field = CanonicalMixedDecisionField(CanonicalMixedDecisionProfile(blocks))
    _, expected = field.solve(field.initial(formula, variable_count=3 * blocks))

    state = regional_state(formula, variable_count=3 * blocks)
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
    assert REGIONAL_KERNEL_NAME == "exact.mixed-exact-one"
    assert REGIONAL_KERNEL_MAX_WORK > 0
    saw_progress = False
    while True:
        before = json.loads(json.dumps(state, sort_keys=True))
        result = regional_kernel(json.loads(json.dumps(state)), {}, 1)
        assert result.work <= 1
        assert result.state == json.loads(json.dumps(result.state, sort_keys=True))
        if result.status == "yield":
            saw_progress = True
            assert result.state["continuation"] != before["continuation"]
            state = json.loads(json.dumps(result.state))
            continue
        assert result.status == "done"
        assert result.output == expected
        state = json.loads(json.dumps(result.state))
        break
    assert saw_progress
    assert state["phase"] == "terminal"
    assert state["result"] == expected


def test_linear_resource_formulas_hold_at_scaling_sizes() -> None:
    for blocks in (8, 12, 24, 48, 96, 192, 384, 768):
        profile = CanonicalMixedDecisionProfile(blocks)
        assert profile.field_values == 12 + 21 * blocks // 2
        assert profile.field_bytes == 96 + 84 * blocks
        for labels, expected in (
            ((0,) * (3 * blocks // 2), "sat"),
            ((1,) + (0,) * (3 * blocks // 2 - 1), "unsat"),
        ):
            field = CanonicalMixedDecisionField(profile)
            final, certificate = field.solve(
                field.initial(
                    canonical_formula_from_labels(blocks, labels),
                    variable_count=3 * blocks,
                )
            )
            assert certificate["status"] == expected
            assert certificate["transitions"] == blocks // 2
            assert certificate["candidate_checks"] == 8 * blocks
            assert final.nbytes == 96 + 84 * blocks


def test_descriptor_corruption_and_noncanonical_formula_fail_closed() -> None:
    blocks = 4
    labels = (0,) * 6
    formula = canonical_formula_from_labels(blocks, labels)
    field = CanonicalMixedDecisionField(CanonicalMixedDecisionProfile(blocks))
    final, _ = field.solve(field.initial(formula, variable_count=12))
    descriptor = field.descriptor(final)
    damaged = dict(descriptor)
    raw = bytearray(base64.b64decode(damaged["field_b64"]))
    raw[-1] ^= 1
    damaged["field_b64"] = base64.b64encode(raw).decode("ascii")
    with pytest.raises(MixedExactOneDecisionError, match="state digest mismatch"):
        CanonicalMixedDecisionField.from_descriptor(damaged)
    with pytest.raises(MixedExactOneDecisionError, match="canonical mixed class"):
        field.initial(formula[:-1], variable_count=12)
