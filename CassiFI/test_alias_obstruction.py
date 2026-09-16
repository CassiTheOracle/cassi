from __future__ import annotations

import json

from cassi_alias_exact_one_field import (
    recognize_degree_two_three_exact_one,
    regular_monotone_formula,
)
from cassi_alias_obstruction import (
    REGIONAL_KERNEL_MAX_WORK,
    REGIONAL_KERNEL_NAME,
    REGIONAL_STATE_SCHEMA,
    evaluate_alias_candidate,
    regional_kernel,
    regional_state,
)


def test_regional_obstruction_quantum_one_roundtrip_and_public_parity() -> None:
    formula = regular_monotone_formula(8, 4, seed=3)
    recognized = recognize_degree_two_three_exact_one(formula, variable_count=10)
    bits = (0,) * len(recognized.cubic_variables)
    expected = evaluate_alias_candidate(recognized, bits)

    state = regional_state(recognized, bits)
    assert REGIONAL_KERNEL_NAME == "exact.alias-obstruction"
    assert REGIONAL_KERNEL_MAX_WORK > 0
    assert state["schema"] == REGIONAL_STATE_SCHEMA
    assert {"source", "phase", "continuation", "progress", "facts", "journal", "outcome", "evidence", "work"} <= set(state)

    first = regional_kernel(state, {}, 1)
    assert first.status == "yield"
    assert first.work <= 1
    assert first.state["progress"] != state["progress"]

    current = first.state
    transitions = 0
    while True:
        current = json.loads(json.dumps(current, sort_keys=True))
        transition = regional_kernel(current, {}, 1)
        transitions += 1
        assert transition.work <= 1
        assert json.loads(json.dumps(transition.state, sort_keys=True)) == transition.state
        if transition.status != "yield":
            assert transition.status == "done"
            assert transition.output == expected
            assert transition.state["outcome"] == expected
            break
        current = transition.state
        assert transitions < 100_000
