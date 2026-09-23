from __future__ import annotations

import json

from cassi_math_dataset import (
    MATH_DATASET_LESSON_SCHEMA,
    audit_gsm8k_text,
    mine_gsm8k_lessons,
    parse_gsm8k_records,
)
from run_cassi_math_dataset_pilot import run_pilot


_SAMPLE = """Q: A basket has 6 apples and receives 4 more. How many apples?
A: Compute 6 + 4 = 1010 apples.
#### 10

Q: A basket has 6 apples and receives 4 more. How many apples?
A: Compute 6 + 4 = 1111 apples.
#### 11
"""


def test_gsm8k_parser_keeps_questions_reasoning_and_declared_answers():
    records = parse_gsm8k_records(_SAMPLE)

    assert len(records) == 2
    assert records[0]["question"].startswith("A basket")
    assert records[0]["reasoning"] == "Compute 6 + 4 = 1010 apples."
    assert records[0]["answer_text"] == "10"


def test_audit_admits_only_exact_equation_answer_replays():
    report = audit_gsm8k_text(_SAMPLE)

    assert report["counts"]["records"] == 2
    assert report["counts"]["verified_cases"] == 1
    assert report["cases"][0]["equation_latex"] == "10"
    assert report["cases"][0]["answer"] == "10"
    assert report["counts"]["equation_mismatches"] == 1


def test_lesson_miner_emits_typed_train_and_holdout_contract():
    cases = [
        {"index": 0, "equation_surface": "6+4"},
        {"index": 1, "equation_surface": "10+2"},
        {"index": 2, "equation_surface": "12+3"},
    ]

    lessons = mine_gsm8k_lessons(
        cases,
        max_lessons=1,
        max_examples=2,
        holdout_count=1,
    )

    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson["schema"] == MATH_DATASET_LESSON_SCHEMA
    assert len(lesson["examples"]) == 2
    assert len(lesson["holdout"]) == 1
    assert lesson["examples"][0]["english"] == "( 6 plus 4 )"
    assert lesson["holdout"][0]["latex"] == "12+3"


def test_field_pilot_submits_verified_cases_to_persistent_math_state(tmp_path):
    source = tmp_path / "gsm8k.txt"
    source.write_text(_SAMPLE, encoding="utf-8")
    state_path = tmp_path / "state.json"

    receipt = run_pilot(source, 8, holdout_count=1, state_output=state_path)

    assert json.loads(state_path.read_text(encoding="utf-8"))["ledger"]["transitions"] == 1
    assert receipt["state_checkpoint"] == str(state_path)
    assert receipt["field_intake"]["training"]["submitted_cases"] == 0
    assert receipt["field_intake"]["heldout"]["submitted_cases"] == 1
    assert receipt["field_intake"]["heldout"]["exact_answer_replays"] == 1
    assert receipt["field_intake"]["supported"] == 1
    assert receipt["field_intake"]["exact_answer_replays"] == 1
    assert receipt["field_intake"]["state_operation_count"] == 1
    assert receipt["field_intake"]["failures"] == []
