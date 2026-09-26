from __future__ import annotations
import json
from cassi_python import evaluate_source_candidate
from run_cassi_python_cumulative_improvement import (
    BASELINE_SOURCE,
    CASES,
    TASKS,
    _candidate_pool_for_task,
    _task_local_invariant,
    cumulative_multi_prompt,
    cumulative_prompt,
    field_select_edit,
    field_select_task,
    parse_proposal,
    parse_proposals,
    rank_model_proposals,
)

def test_cumulative_field_selection_follows_current_program() -> None:
    assert field_select_task(BASELINE_SOURCE, ()) == "constant_fold"
    after_constant = BASELINE_SOURCE.replace("(2 + 3)", "5")
    assert field_select_task(
        after_constant,
        ({"task_id": "constant_fold", "status": "PASS"},),
    ) == "redundant_assignment"
    after_redundant = after_constant.replace("tmp = value\n", "").replace(
        " * tmp", " * value"
    )
    assert field_select_task(
        after_redundant,
        (
            {"task_id": "constant_fold", "status": "PASS"},
            {"task_id": "redundant_assignment", "status": "PASS"},
        ),
    ) == "identical_branch"


def test_field_selects_promotable_edit_from_competing_pool() -> None:
    selected = field_select_edit(BASELINE_SOURCE, ())
    assert selected is not None
    assert selected["edit_id"] == "constant_fold:canonical"
    pool = _candidate_pool_for_task(
        "result = 5 * value + 1 if value >= 0 else 5 * value + 1",
        "identical_branch",
    )
    assert {row["variant_id"] for row in pool} == {
        "canonical",
        "parenthesized",
        "commuted_multiply",
        "unchanged",
        "drop_offset",
    }
    assert [row["status"] for row in pool] == [
        "PASS",
        "PASS",
        "PASS",
        "REJECT",
        "REJECT",
    ]


def test_multi_proposal_contract_and_field_ranking() -> None:
    content = (
        '{"proposals":['
        '{"proposal_id":"identical_branch:canonical","task_id":"identical_branch",'
        '"source":"result = 5 * value + 1"},'
        '{"proposal_id":"identical_branch:parenthesized","task_id":"identical_branch",'
        '"source":"result = (5 * value) + 1"},'
        '{"proposal_id":"identical_branch:drop_offset","task_id":"identical_branch",'
        '"source":"result = 5 * value"}]}'
    )
    proposals = parse_proposals(content)
    source = "result = 5 * value + 1 if value >= 0 else 5 * value + 1"
    pool = _candidate_pool_for_task(source, "identical_branch")
    outcomes, selected = rank_model_proposals(
        source,
        "identical_branch",
        proposals,
        pool,
        (),
    )
    assert len(outcomes) == 3
    assert selected is not None
    assert selected["edit_id"] == "identical_branch:canonical"
    assert selected["proposal_id"] == "identical_branch:canonical"
    assert [row["status"] for row in outcomes] == ["PASS", "PASS", "REJECT"]
    assert sum(row["field_rank_selected"] for row in outcomes) == 1
    prompt = cumulative_multi_prompt(
        0,
        source,
        "identical_branch",
        0,
        "identical_branch:canonical",
        pool,
    )
    assert '"proposals"' in prompt
    assert "identical_branch:parenthesized" in prompt


def test_novel_model_proposal_is_bounded_and_ranked() -> None:
    source = "result = 5 * value + 1 if value >= 0 else 5 * value + 1"
    novel = "result = (value * 5) + 1"
    pool = _candidate_pool_for_task(source, "identical_branch")
    proposals = parse_proposals(
        json.dumps(
            {"proposals": [{"proposal_id": "model-novel", "task_id": "identical_branch", "source": novel}]}
        )
    )
    outcomes, selected = rank_model_proposals(
        source,
        "identical_branch",
        proposals,
        pool,
        (),
    )
    assert selected is not None
    assert selected["edit_id"].startswith("model:")
    assert selected["candidate_origin"] == "model_novel"
    assert selected["novel_candidate"] is True
    assert outcomes[0]["status"] == "PASS"
    assert outcomes[0]["field_rank_selected"] is True
    assert outcomes[0]["candidate_source"] == novel

    prompt = cumulative_multi_prompt(
        0,
        source,
        "identical_branch",
        0,
        "identical_branch:canonical",
        pool,
    )
    assert "not an allow-list" in prompt
    assert "bounded CassiPy subset" in prompt


def test_novel_proposal_cannot_change_selected_task() -> None:
    source = "result = 5 * value + 1 if value >= 0 else 5 * value + 1"
    proposals = parse_proposals(
        '{"proposals":[{"proposal_id":"wrong-task","task_id":"constant_fold",'
        '"source":"result = (value * 5) + 1"}]}'
    )
    outcomes, selected = rank_model_proposals(
        source,
        "identical_branch",
        proposals,
        _candidate_pool_for_task(source, "identical_branch"),
        (),
    )
    assert selected is None
    assert outcomes[0]["status"] == "REJECT"
    assert outcomes[0]["selected_task_match"] is False


def test_duplicate_model_sources_are_rejected_as_non_distinct() -> None:
    source = "result = 5 * value + 1 if value >= 0 else 5 * value + 1"
    proposals = parse_proposals(
        json.dumps(
            {
                "proposals": [
                    {"proposal_id": "first", "task_id": "identical_branch", "source": "result = value * 5 + 1"},
                    {"proposal_id": "duplicate", "task_id": "identical_branch", "source": "result = value * 5 + 1"},
                ]
            }
        )
    )
    outcomes, selected = rank_model_proposals(
        source,
        "identical_branch",
        proposals,
        _candidate_pool_for_task(source, "identical_branch"),
        (),
    )
    assert selected is not None
    assert outcomes[0]["status"] == "PASS"
    assert outcomes[1]["status"] == "REJECT"
    assert "duplicate proposal source" in outcomes[1]["failure"]["message"]



def test_novel_proposal_wins_equal_step_tie_with_prefix_repair() -> None:
    source = "result = 5 * value + 1 if value >= 0 else 5 * value + 1"
    proposals = parse_proposals(
        json.dumps(
            {
                "proposals": [
                    {
                        "proposal_id": "canonical",
                        "task_id": "identical_branch",
                        "source": "result = 5 * value + 1",
                    },
                    {
                        "proposal_id": "novel",
                        "task_id": "identical_branch:commuted_multiply",
                        "source": "result = 1 + value * 5",
                    },
                ]
            }
        )
    )
    outcomes, selected = rank_model_proposals(
        source,
        "identical_branch",
        proposals,
        _candidate_pool_for_task(source, "identical_branch"),
        (),
    )
    assert selected is not None
    assert selected["candidate_origin"] == "model_novel"
    assert selected["novel_candidate"] is True
    assert selected["metadata_repair_reason"] == "task_id_prefix"
    assert selected["candidate_steps"] == 24
    assert outcomes[1]["field_rank_selected"] is True
def test_identity_task_families_use_ast_eligibility() -> None:
    for source, task_id in (
        ("result = (5 * value + 1) + 0", "redundant_add_zero"),
        ("result = (5 * value + 1) * 1", "redundant_multiply_one"),
    ):
        assert field_select_task(source, ()) == task_id
        pool = _candidate_pool_for_task(source, task_id)
        assert pool[0]["status"] == "PASS"
        assert pool[0]["task_invariant"] is True
        assert pool[1]["task_invariant"] is False
    reverse = BASELINE_SOURCE.replace("(2 + 3)", "(3 + 2)")
    reverse_pool = _candidate_pool_for_task(reverse, "constant_fold")
    assert reverse_pool[0]["candidate_source"] == reverse.replace("(3 + 2)", "5")
    assert reverse_pool[0]["status"] == "PASS"


def test_behavior_preserving_unrelated_edit_fails_task_invariant() -> None:
    source = BASELINE_SOURCE
    unrelated = "result = (2 + 3) * value + 1"
    assert _task_local_invariant(source, unrelated, "constant_fold") is False
    proposals = parse_proposals(
        json.dumps(
            {
                "proposals": [
                    {
                        "proposal_id": "unrelated",
                        "task_id": "constant_fold",
                        "source": unrelated,
                    }
                ]
            }
        )
    )
    outcomes, selected = rank_model_proposals(
        source,
        "constant_fold",
        proposals,
        _candidate_pool_for_task(source, "constant_fold"),
        (),
    )
    assert selected is None
    assert outcomes[0]["status"] == "REJECT"
    assert outcomes[0]["task_invariant"] is False


def test_promoted_candidates_form_one_behavior_preserving_chain() -> None:
    current = BASELINE_SOURCE
    candidates = (
        current.replace("(2 + 3)", "5"),
        current.replace("(2 + 3)", "5").replace("tmp = value\n", "").replace(
            " * tmp", " * value"
        ),
        "result = 5 * value + 1",
    )
    steps: list[int] = []
    for candidate in candidates:
        result = evaluate_source_candidate(current, candidate, CASES)
        assert result.status == "PASS"
        assert result.equivalent is True
        assert result.improved is True
        steps.append(result.candidate_steps)
        current = candidate
    assert steps == sorted(steps, reverse=True)
    assert current == "result = 5 * value + 1"


def test_cumulative_proposal_contract_and_prompt() -> None:
    task_id, source = parse_proposal(
        '{"task_id":"constant_fold","source":"result = 5 * value"}'
    )
    assert task_id == "constant_fold"
    assert source == "result = 5 * value"
    prompt = cumulative_prompt(0, BASELINE_SOURCE, "constant_fold", 0)
    assert "constant_fold" in prompt
    assert BASELINE_SOURCE in prompt
    assert [str(task["task_id"]) for task in TASKS] == [
        "constant_fold",
        "redundant_assignment",
        "identical_branch",
        "redundant_add_zero",
        "redundant_multiply_one",
    ]

def test_mutation_controls_reject_regressions() -> None:
    from run_cassi_python_cumulative_improvement import mutation_control_rows

    rows = mutation_control_rows()
    assert len(rows) == 3
    assert all(row["status"] == "REJECT" for row in rows)
    assert rows[0]["oracle_differential"]["passed"] is False
    assert rows[1]["equivalent"] is True
    assert rows[1]["improved"] is False
    assert rows[2]["oracle_differential"]["passed"] is False
