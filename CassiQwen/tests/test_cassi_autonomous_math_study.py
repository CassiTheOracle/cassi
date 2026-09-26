#!/usr/bin/env python3
"""Behavioral verification for the complete autonomous mathematics course."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from cassi_autonomous_math_study import (
    COURSE,
    DEFAULT_METHOD,
    PROGRAM_SCHEMA,
    AutonomousMathStudy,
    StudyError,
    atomic_json,
    canonical_program,
    course_manifest,
    execute_program,
    teacher_prompt,
)
from run_cassi_autonomous_math_study import _completed_checkpoint


def determinant_program() -> dict[str, object]:
    matrix = {"op": "arg", "name": "matrix"}

    def cell(row: int, column: int) -> dict[str, object]:
        return {
            "op": "get",
            "value": {
                "op": "get",
                "value": matrix,
                "index": {"op": "const", "value": row},
            },
            "index": {"op": "const", "value": column},
        }

    return {
        "schema": PROGRAM_SCHEMA,
        "params": ["matrix"],
        "body": {
            "op": "sub",
            "a": {"op": "mul", "args": [cell(0, 0), cell(1, 1)]},
            "b": {"op": "mul", "args": [cell(0, 1), cell(1, 0)]},
        },
    }


class DeterminantTeacher:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, *, prompt: str, max_tokens: int, thinking: bool = False):
        self.prompts.append(prompt)
        return {
            "content": json.dumps({"program": determinant_program()}),
            "reasoning_content": "",
            "generation_parameters": {
                "max_tokens": max_tokens,
                "thinking": thinking,
                "temperature": 0,
            },
            "usage": {"completion_tokens": 96},
        }


def test_course_is_complete_gradual_and_partitioned() -> None:
    manifest = course_manifest()

    assert manifest["levels"] == 27
    assert manifest["problems"] == 162
    assert [unit.level for unit in COURSE] == list(range(27))
    assert COURSE[0].prerequisites == ()
    assert all(unit.prerequisites == (COURSE[index - 1].unit_id,) for index, unit in enumerate(COURSE[1:], 1))
    assert all(len(unit.training) == 3 for unit in COURSE)
    assert all(len(unit.practice) == 2 for unit in COURSE)
    assert all(len(unit.examinations) == 1 for unit in COURSE)
    assert COURSE[-1].unit_id == "m26-prime-generation"
    assert COURSE[-1].examinations[0].expected[-1] == 997
    assert len(COURSE[-1].examinations[0].expected) == 168


def test_vm_executes_general_program_and_refuses_unbounded_work() -> None:
    program = determinant_program()
    answer, steps = execute_program(program, {"matrix": [[1, 2], [3, 4]]})

    assert answer == -2
    assert steps > 0
    shorthand = {
        "schema": PROGRAM_SCHEMA,
        "params": ["x"],
        "body": {"op": "add", "args": [1, {"op": "arg", "name": "x"}]},
    }
    shorthand_answer, _ = execute_program(shorthand, {"x": 2})
    assert shorthand_answer == 3
    oversized = {
        "schema": PROGRAM_SCHEMA,
        "params": ["n"],
        "body": {
            "op": "range",
            "start": {"op": "const", "value": 0},
            "stop": {"op": "const", "value": 3000},
            "step": {"op": "const", "value": 1},
        },
    }
    with pytest.raises(StudyError, match="list exceeded"):
        execute_program(oversized, {"n": 1})
    with pytest.raises(StudyError, match="unsupported program operation"):
        canonical_program(
            {
                "schema": PROGRAM_SCHEMA,
                "params": ["x"],
                "body": {"op": "python-eval", "value": "x"},
            }
        )


def test_teacher_prompt_never_contains_protected_exam() -> None:
    unit = COURSE[8]
    prompt = teacher_prompt(unit, DEFAULT_METHOD, 0, ())
    protected = unit.examinations[0]

    assert protected.case_id not in prompt
    assert json.dumps(protected.arguments, sort_keys=True) not in prompt
    assert all(case.case_id in prompt for case in (*unit.training, *unit.practice))


def test_full_controller_studies_reopens_examines_and_regresses_without_teacher() -> None:
    teacher = DeterminantTeacher()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        controller = AutonomousMathStudy(
            root / "field",
            root / "audit.json",
            teacher=teacher,
            profile_overrides={"mode_count": 65_536},
        )
        receipt = controller.run_unit("m8-determinant-2x2")

        assert receipt["ready_to_continue"] is True
        assert len(teacher.prompts) == 1
        assert receipt["protected_examination"]["teacher_disconnected"] is True
        assert receipt["protected_examination"]["teacher_calls_during_examination"] == 0
        assert receipt["protected_examination"]["examination"]["cases"][0]["actual"] == -2
        assert receipt["regression"]["status"] == "passed"
        assert receipt["ownership"]["sole_adaptive_persistent_object"] == "QiFieldState.field"
        assert receipt["ownership"]["qwen_in_live_answer_path"] is False
        assert receipt["resource_accounting"]["teacher_calls"] == 1

        reopened = AutonomousMathStudy(
            root / "field",
            root / "audit.json",
            teacher=None,
            profile_overrides={"mode_count": 65_536},
        )
        regression = reopened.regression()
        assert regression["status"] == "passed"
        assert reopened.promoted_units() == ("m8-determinant-2x2",)
        output = root / "m8-determinant-2x2-receipt.json"
        atomic_json(output, receipt)
        checkpoint = _completed_checkpoint(
            reopened, "m8-determinant-2x2", output
        )
        assert checkpoint is not None
        assert checkpoint["resumed"] is True


def test_next_generation_comparison_is_matched_before_method_promotion() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        controller = AutonomousMathStudy(
            root / "field",
            root / "audit.json",
            teacher=DeterminantTeacher(),
            profile_overrides={"mode_count": 65_536},
        )
        controller.ensure_method()
        candidate = {
            **DEFAULT_METHOD,
            "generation": 1,
            "actions": ["seek-counterexample", "derive-rule", "repair-program"],
        }
        plan = controller.matched_method_comparison_plan(
            candidate_method=candidate,
            evaluation_units=("m9-binomial-square", "m10-quadratic-roots"),
        )

        assert plan["matched_budget"]["same_starting_field_checkpoint"] is True
        assert plan["matched_budget"]["same_teacher_identity"] is True
        assert plan["matched_budget"]["same_development_and_protected_cases"] is True
        assert plan["regression_required"] is True
