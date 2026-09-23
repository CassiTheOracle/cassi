from __future__ import annotations

from cassi_python import evaluate_source_candidate
from run_cassi_python_self_improvement import (
    BASELINE_SOURCE,
    CASES,
    PORTFOLIO,
    optimization_portfolio_prompt,
    parse_portfolio_proposal,
)


def test_model_candidate_is_exact_and_strictly_cheaper() -> None:
    result = evaluate_source_candidate(BASELINE_SOURCE, "result = 5 * value", CASES)
    assert result.status == "PASS"
    assert result.equivalent is True
    assert result.improved is True
    assert result.original_steps > result.candidate_steps
    assert all(row["same"] for row in result.cases)



def test_portfolio_proposal_records_task_selection() -> None:
    task_id, source = parse_portfolio_proposal(
        '{"task_id":"redundant_assignment","source":"result = value"}'
    )
    assert task_id == "redundant_assignment"
    assert source == "result = value"
    prompt = optimization_portfolio_prompt(0)
    assert all(str(task["task_id"]) in prompt for task in PORTFOLIO)
def test_field_selection_prefers_untried_tasks() -> None:
    from run_cassi_python_self_improvement import _field_select_task

    assert _field_select_task(()) == "constant_fold"
    assert _field_select_task(
        ({"task_id": "constant_fold", "status": "PASS"},)
    ) == "redundant_assignment"
    assert _field_select_task(
        (
            {"task_id": "constant_fold", "status": "PASS"},
            {"task_id": "redundant_assignment", "status": "REJECT"},
        )
    ) == "identical_branch"


def test_each_portfolio_candidate_passes_exact_acceptance_gate() -> None:
    expected = {
        "constant_fold": "result = 5 * value",
        "redundant_assignment": "result = value",
        "identical_branch": "result = value + 1",
    }
    for task in PORTFOLIO:
        result = evaluate_source_candidate(
            str(task["baseline_source"]),
            expected[str(task["task_id"])],
            tuple(task["cases"]),
        )
        assert result.status == "PASS"
        assert result.improved is True

def test_unchanged_source_cannot_be_promoted() -> None:
    result = evaluate_source_candidate(BASELINE_SOURCE, BASELINE_SOURCE, CASES)
    assert result.status == "REJECT"
    assert result.equivalent is True
    assert result.improved is False
    assert result.changes == 0
