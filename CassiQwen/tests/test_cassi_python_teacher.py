from __future__ import annotations

import json

import pytest

from cassi_python import PythonCase
from cassi_python_teacher import (
    TeacherBridgeError,
    _parse_teacher_evidence,
    parse_teacher_source,
    optimization_prompt,
    teacher_prompt,
    validate_teacher_source,
)


def test_teacher_source_parser_extracts_only_json_source() -> None:
    source = parse_teacher_source('reasoning\n{"source":"result = value * 2"}\n')
    assert source == "result = value * 2"



def test_teacher_evidence_recovers_proposal_from_reasoning_channel() -> None:
    source, channel = _parse_teacher_evidence(
        {
            "response": "",
            "reasoning_content": 'I will return {"source":"result = value * 2"}',
        }
    )
    assert source == "result = value * 2"
    assert channel == "reasoning_content"

def test_teacher_source_validation_uses_cassipy_and_cpython() -> None:
    validation = validate_teacher_source(
        "result = value * 2",
        (PythonCase("double", {"value": 7}, 14),),
    )
    assert validation["passed"] is True
    assert validation["program_sha256"]


def test_teacher_source_parser_rejects_extra_fields() -> None:
    with pytest.raises(TeacherBridgeError):
        parse_teacher_source(json.dumps({"source": "result = 1", "extra": True}))


def test_optimization_prompt_requests_a_model_generated_improvement() -> None:
    prompt = optimization_prompt(0)
    assert "proposing a code improvement" in prompt
    assert "result = (2 + 3) * value" in prompt
    assert "different from the baseline" in prompt
    assert '"source":"result = 5 * value"' in prompt


def test_teacher_prompt_declares_compact_thinking_contract() -> None:
    prompt = teacher_prompt(
        "P1",
        "Names and assignment",
        "result = value * value",
        (PythonCase("square", {"value": 3}, 9),),
        0,
    )
    assert "final answer must be this JSON object" in prompt
    assert '"source":"result = value * value"' in prompt