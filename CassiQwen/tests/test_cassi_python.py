from __future__ import annotations

import pytest

from cassi_python import (
    CassiPyBudgetError,
    CassiPySyntaxError,
    PythonCase,
    content_digest_matches,
    evaluate_optimization,
    evaluate_source_candidate,
    parse_source,
    run_apprenticeship,
    run_source,
    verify_receipt,
)


def test_interprets_assignment_conditionals_and_bounded_loops() -> None:
    source = """
result = 0
for value in values:
    if value > 0:
        result = result + value
"""
    result = run_source(source, {"values": [-2, 3, 5]})
    assert result.value == 8
    assert result.steps > 0


def test_interprets_recursive_functions() -> None:
    source = """
def factorial(value):
    if value <= 1:
        return 1
    return value * factorial(value - 1)
result = factorial(value)
"""
    assert run_source(source, {"value": 7}).value == 5040


def test_rejects_unsafe_python_surface() -> None:
    with pytest.raises(CassiPySyntaxError):
        parse_source("import os")
    with pytest.raises(CassiPySyntaxError):
        parse_source("result = object.value")
    with pytest.raises(CassiPySyntaxError):
        parse_source("while True:\n    result = 1")


def test_execution_budget_is_visible() -> None:
    source = """
result = 0
for value in range(100):
    result = result + value
"""
    with pytest.raises(CassiPyBudgetError):
        run_source(source, max_steps=10)


def test_optimizer_preserves_behavior_and_reduces_steps() -> None:
    program = parse_source("result = (2 + 3) * value", params=("value",))
    optimization = evaluate_optimization(
        program,
        (PythonCase("case", {"value": 9}, 45),),
    )
    assert optimization.status == "PASS"
    assert optimization.equivalent is True
    assert optimization.improved is True
    assert optimization.candidate_steps < optimization.original_steps


def test_source_candidate_is_promoted_only_after_behavioral_gain() -> None:
    result = evaluate_source_candidate(
        "result = (2 + 3) * value",
        "result = 5 * value",
        (PythonCase("source-case", {"value": 4}, 20),),
    )
    assert result.status == "PASS"
    assert result.equivalent is True
    assert result.candidate_steps < result.original_steps


def test_apprenticeship_receipt_passes_independent_digest_check() -> None:
    receipt = run_apprenticeship()
    assert receipt["status"] == "PASS"
    assert len(receipt["lessons"]) == 21
    assert [lesson["lesson_id"] for lesson in receipt["lessons"][-13:]] == [
        f"FM{index}" for index in range(13)
    ]
    assert content_digest_matches(receipt)
    assert verify_receipt(receipt)["status"] == "PASS"
