from __future__ import annotations

"""Run a bounded exact-intake and lesson pilot over inactive GSM8K data."""

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_cognition import semantic_cognition_kernel, semantic_cognition_state
from cassi_math_dataset import audit_gsm8k_file, mine_gsm8k_lessons
from cassi_math_language import evaluate, parse_latex


DEFAULT_DATASET = Path(
    "D:/carina/workspaces/cassi/datasets/inactive/gsm8k_train.txt"
)


def _step(
    state: Mapping[str, Any], request: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    transition = semantic_cognition_kernel(state, request, 4096)
    if transition.status != "done":
        raise RuntimeError(f"math dataset operation did not finish: {transition.status}")
    return transition.state, transition.output


def _learn_lessons(
    state: dict[str, Any], lessons: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    supported = 0
    failures: list[dict[str, Any]] = []
    for lesson in lessons:
        construction_id = str(lesson["construction_id"])
        try:
            state, result = _step(
                state,
                {
                    "operation": "learn-math",
                    "operation_id": f"gsm8k:lesson:{construction_id}",
                    "construction_id": construction_id,
                    "term_template": lesson["term_template"],
                    "examples": lesson["examples"],
                    "holdout": lesson["holdout"],
                    "source_policy": {
                        "content_admission": "requires-independent-source-rules",
                        "grants_authority": False,
                    },
                },
            )
            if result.get("status") != "supported":
                failures.append(
                    {
                        "construction_id": construction_id,
                        "reason": result.get("status"),
                        "holdout_failures": result.get("holdout_failures"),
                    }
                )
                continue
            supported += 1
        except Exception as exc:  # noqa: BLE001 - receipt records every failed lesson
            failures.append(
                {
                    "construction_id": construction_id,
                    "reason": type(exc).__name__,
                    "message": str(exc),
                }
            )
    return state, {
        "submitted_lessons": len(lessons),
        "supported": supported,
        "failures": failures,
    }


def _evaluate_lesson_holdouts(
    state: dict[str, Any], lessons: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    supported = 0
    exact = 0
    submitted = 0
    failures: list[dict[str, Any]] = []
    for lesson in lessons:
        construction_id = str(lesson["construction_id"])
        for offset, example in enumerate(lesson["holdout"]):
            submitted += 1
            try:
                state, result = _step(
                    state,
                    {
                        "operation": "interpret-math",
                        "operation_id": (
                            f"gsm8k:lesson-holdout:{construction_id}:{offset}"
                        ),
                        "surface": "english",
                        "text": example["english"],
                    },
                )
                if result.get("status") != "supported":
                    failures.append(
                        {
                            "construction_id": construction_id,
                            "offset": offset,
                            "reason": result.get("status"),
                        }
                    )
                    continue
                supported += 1
                expected = evaluate(parse_latex(example["latex"]))
                actual = evaluate(result["interpretation"]["term"])
                if actual == expected:
                    exact += 1
                else:
                    failures.append(
                        {
                            "construction_id": construction_id,
                            "offset": offset,
                            "reason": "lesson-holdout-mismatch",
                            "field_value": str(actual),
                            "expected_value": str(expected),
                        }
                    )
            except Exception as exc:  # noqa: BLE001 - receipt records every holdout
                failures.append(
                    {
                        "construction_id": construction_id,
                        "offset": offset,
                        "reason": type(exc).__name__,
                        "message": str(exc),
                    }
                )
    return state, {
        "submitted_cases": submitted,
        "supported": supported,
        "exact_term_replays": exact,
        "failures": failures,
    }


def _submit_cases(
    state: dict[str, Any],
    cases: Sequence[Mapping[str, Any]],
    phase: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    supported = 0
    exact = 0
    failures: list[dict[str, Any]] = []
    for case in cases:
        operation_id = f"gsm8k:{phase}:{case['index']}"
        try:
            state, result = _step(
                state,
                {
                    "operation": "interpret-math",
                    "operation_id": operation_id,
                    "surface": "latex",
                    "text": case["equation_latex"],
                },
            )
            if result.get("status") != "supported":
                failures.append(
                    {
                        "index": case["index"],
                        "phase": phase,
                        "reason": result.get("status"),
                    }
                )
                continue
            supported += 1
            value = evaluate(result["interpretation"]["term"])
            if str(value) == case["answer"]:
                exact += 1
            else:
                failures.append(
                    {
                        "index": case["index"],
                        "phase": phase,
                        "reason": "field-answer-mismatch",
                        "field_value": str(value),
                        "declared_answer": case["answer"],
                    }
                )
        except Exception as exc:  # noqa: BLE001 - receipt records every failed case
            failures.append(
                {
                    "index": case["index"],
                    "phase": phase,
                    "reason": type(exc).__name__,
                    "message": str(exc),
                }
            )
    return state, {
        "submitted_cases": len(cases),
        "supported": supported,
        "exact_answer_replays": exact,
        "failures": failures,
    }


def run_pilot(
    path: Path,
    limit: int,
    holdout_count: int = 0,
    state_output: Path | None = None,
    max_lessons: int = 8,
    max_lesson_examples: int = 8,
    lesson_holdout_count: int = 2,
) -> dict[str, Any]:
    if limit < 1 or holdout_count < 0:
        raise ValueError("limit must be positive and holdout_count must be nonnegative")
    audit = audit_gsm8k_file(path, max_cases=None)
    all_cases = audit["cases"]
    cases = all_cases[:limit]
    if holdout_count > len(cases):
        raise ValueError("holdout_count exceeds the selected cases available")
    train_cases = cases[:-holdout_count] if holdout_count else cases
    holdout_cases = cases[-holdout_count:] if holdout_count else []
    heldout_ids = {case["index"] for case in holdout_cases}
    lesson_source_cases = [
        case for case in all_cases if case["index"] not in heldout_ids
    ]
    lessons = mine_gsm8k_lessons(
        lesson_source_cases,
        max_lessons=max_lessons,
        max_examples=max_lesson_examples,
        holdout_count=lesson_holdout_count,
    )
    state = semantic_cognition_state()
    state, lesson_learning = _learn_lessons(state, lessons)
    state, lesson_holdout = _evaluate_lesson_holdouts(state, lessons)
    state, training = _submit_cases(state, train_cases, "train")
    state, heldout = _submit_cases(state, holdout_cases, "heldout")
    failures = [*training["failures"], *heldout["failures"]]
    receipt = {
        "audit": {
            "schema": audit["schema"],
            "audited_cases": len(all_cases),
            "counts": audit["counts"],
            "dataset": str(path),
        },
        "lesson_mining": {
            "source_cases": len(lesson_source_cases),
            "max_lessons": max_lessons,
            "max_examples": max_lesson_examples,
            "holdout_count": lesson_holdout_count,
        },
        "field_intake": {
            "requested_cases": limit,
            "lessons": lesson_learning,
            "lesson_holdout": lesson_holdout,
            "training": training,
            "heldout": heldout,
            "submitted_cases": training["submitted_cases"] + heldout["submitted_cases"],
            "supported": training["supported"] + heldout["supported"],
            "exact_answer_replays": training["exact_answer_replays"]
            + heldout["exact_answer_replays"],
            "failures": failures,
            "state_operation_count": len(state["ledger"]["operation_receipts"]),
        },
        "interpretation_boundary": (
            "validated numeric expressions plus generated arithmetic lessons; "
            "no natural-language construction inferred from raw GSM8K prose"
        ),
        "heldout_boundary": (
            "lesson holdouts test transfer of generated arithmetic surfaces; "
            "raw GSM8K holdouts test exact numeric replay, not word-problem generalization"
        ),
    }
    if state_output is not None:
        state_output.parent.mkdir(parents=True, exist_ok=True)
        state_output.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        receipt["state_checkpoint"] = str(state_output)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--holdout-count", type=int, default=16)
    parser.add_argument("--max-lessons", type=int, default=8)
    parser.add_argument("--max-lesson-examples", type=int, default=8)
    parser.add_argument("--lesson-holdout-count", type=int, default=2)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--state-output", type=Path)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.holdout_count < 0 or args.holdout_count > args.limit:
        parser.error("--holdout-count must be in 0..limit")
    if args.max_lessons < 1 or args.max_lesson_examples < 1:
        parser.error("lesson bounds must be positive")
    if args.lesson_holdout_count < 0:
        parser.error("--lesson-holdout-count must be nonnegative")
    receipt = run_pilot(
        args.dataset,
        args.limit,
        args.holdout_count,
        args.state_output,
        args.max_lessons,
        args.max_lesson_examples,
        args.lesson_holdout_count,
    )
    encoded = json.dumps(receipt, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
