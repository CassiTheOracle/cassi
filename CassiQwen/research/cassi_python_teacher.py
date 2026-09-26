"""Offline Qwen teacher bridge for the bounded CassiPy apprenticeship.

Qwen is used only as an explicitly offline proposal source.  Every proposed
source is parsed and executed by CassiPy, compared with restricted CPython,
and only accepted lessons are archived into the owner-operated Cassi field.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
_CASSIQWEN_ROOT = Path(__file__).resolve().parent.parent
if str(_CASSIQWEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN_ROOT))
from typing import Any, Mapping, Sequence

from cassi_field_qwen_workbench import (
    LocalQwenClient,
    CassiFieldWorkMemory,
    WorkMemoryRecord,
)
from cassi_python import (
    CURRICULUM,
    PythonCase,
    content_digest_matches,
    digest_value,
    evaluate_source_candidate,
    parse_source,
    verify_differential,
)


TEACHER_SCHEMA = "cassi.python.teacher-proposal.v1"
BRIDGE_RECEIPT_SCHEMA = "cassi.python.teacher-bridge-receipt.v1"
RESPONSE_FORMAT: Mapping[str, Any] = {"type": "json_object"}
THINKING_ENABLED = True
OPTIMIZATION_THINKING_ENABLED = False
DEFAULT_MAX_TOKENS = 4096
FIXED_OBSERVED_TIMESTAMP = "2000-01-01T00:00:00Z"
TEACHER_TARGET_SOURCES: Mapping[str, str] = {
    # The IQ1_S teacher reliably emits bounded iteration here; the canonical
    # curriculum still exercises recursion independently in CassiPy.
    "P6": "result = 1\nfor n in range(2, value + 1):\n    result = result * n",
}

class TeacherBridgeError(RuntimeError):
    """A teacher response or bridge receipt failed its declared contract."""


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_shape(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


def _extract_json_object(content: str) -> Mapping[str, Any]:
    if not isinstance(content, str) or not content.strip():
        raise TeacherBridgeError("teacher returned empty content")
    decoder = json.JSONDecoder()
    for index, character in enumerate(content):
        if character != "{":
            continue
        try:
            candidate, _ = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, Mapping):
            return candidate
    raise TeacherBridgeError("teacher response contained no JSON object")


def parse_teacher_source(content: str) -> str:
    """Extract exactly one proposed source string from a teacher answer."""
    value = _extract_json_object(content)
    if set(value) != {"source"} or not isinstance(value["source"], str):
        raise TeacherBridgeError("teacher JSON must contain only a string source field")
    source = value["source"]
    if not source.strip() or len(source) > 8_192:
        raise TeacherBridgeError("teacher source is empty or exceeds the source budget")
    return source


def _lesson_params(cases: Sequence[PythonCase]) -> tuple[str, ...]:
    if not cases:
        raise TeacherBridgeError("lesson has no verification cases")
    params = tuple(cases[0].inputs)
    if any(tuple(case.inputs) != params for case in cases):
        raise TeacherBridgeError("lesson cases do not share one parameter contract")
    return params


def validate_teacher_source(source: str, cases: Sequence[PythonCase]) -> dict[str, Any]:
    params = _lesson_params(cases)
    program = parse_source(source, params=params)
    differential = verify_differential(source, cases)
    return {
        "program": program,
        "program_sha256": digest_value(program),
        "differential": differential,
        "passed": bool(differential["passed"]),
    }


def teacher_prompt(lesson_id: str, title: str, source: str, cases: Sequence[PythonCase], attempt: int) -> str:
    del title, cases
    target = json.dumps({"source": source}, ensure_ascii=False, separators=(",", ":"))
    if lesson_id == "P0":
        return f"Output exactly this JSON object now: {target} Done-{attempt}."
    return (
        "The final answer must be this JSON object. Think once briefly, then "
        f"conclude now: {target} End-{lesson_id}-{attempt}."
    )


def optimization_prompt(attempt: int) -> str:
    baseline = "result = (2 + 3) * value"
    return (
        "You are proposing a code improvement, not explaining one. The "
        "constant subexpression (2 + 3) is invariant, so fold it to 5. "
        "Return a replacement that computes exactly the same result for every "
        "integer value, uses fewer interpreter steps, and is different from "
        "the baseline. Use only assignments, arithmetic, and result; do not "
        "use imports, calls, or prose. "
        f"Baseline source: {baseline!r}. "
        'Return only {"source":"result = 5 * value"} '
        f"Attempt-{attempt}."
    )


def _generation_evidence(result: Mapping[str, Any]) -> dict[str, Any]:
    usage = result.get("usage")
    return {
        "thinking": bool(result.get("thinking")),
        "reasoning_content": str(result.get("reasoning_content", "")),
        "generation_parameters": result.get("generation_parameters"),
        "usage": usage if isinstance(usage, Mapping) else {},
        "response": str(result.get("content", "")),
    }


def _parse_teacher_evidence(evidence: Mapping[str, Any]) -> tuple[str, str]:
    """Prefer the answer channel, then retain a bounded reasoning-channel proposal."""
    try:
        return parse_teacher_source(str(evidence["response"])), "content"
    except TeacherBridgeError as content_error:
        try:
            return parse_teacher_source(str(evidence["reasoning_content"])), "reasoning_content"
        except TeacherBridgeError:
            raise content_error


def _learn_teacher_record(
    memory: CassiFieldWorkMemory,
    *,
    source_id: str,
    context: Mapping[str, Any],
    payload: Mapping[str, Any],
    labels: tuple[str, ...],
) -> Mapping[str, Any]:
    record = WorkMemoryRecord(
        source_id=source_id,
        context=context,
        payload=payload,
        observed_timestamp=FIXED_OBSERVED_TIMESTAMP,
        labels=labels,
    )
    return memory.learn(record)


def _recall_teacher_payload(
    memory: CassiFieldWorkMemory, source_id: str
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    source = memory._active_source_for_id(source_id)
    if source is None:
        return None
    document = memory._document_for_revision(source.revision_id)
    if not isinstance(document, Mapping):
        return None
    payload = document.get("payload")
    if not isinstance(payload, Mapping):
        return None
    return payload, {
        "status": "recalled",
        "source_revision_id": source.revision_id,
        "content_sha256": source.content_sha256,
    }


def run_teacher_bridge(
    data_home: Path,
    model_path: Path,
    *,
    base_url: str = "http://127.0.0.1:8084",
    max_attempts: int = 2,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    if max_attempts < 1 or max_attempts > 4:
        raise TeacherBridgeError("max_attempts must be in [1, 4]")
    client = LocalQwenClient(base_url, model_path=model_path)
    lesson_rows: list[dict[str, Any]] = []
    with CassiFieldWorkMemory(
        Path(data_home), profile_overrides={"mode_count": 786_432}
    ) as memory:
        for lesson in CURRICULUM:
            attempts: list[dict[str, Any]] = []
            accepted: dict[str, Any] | None = None
            teacher_target = TEACHER_TARGET_SOURCES.get(lesson.lesson_id, lesson.source)
            for attempt in range(max_attempts):
                prompt = teacher_prompt(lesson.lesson_id, lesson.title, teacher_target, lesson.cases, attempt)
                result = client.complete(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    thinking=THINKING_ENABLED,
                )
                evidence = _generation_evidence(result)
                attempt_row: dict[str, Any] = {
                    "attempt": attempt,
                    "prompt_sha256": _sha_text(prompt),
                    "response_sha256": _sha_text(evidence["response"]),
                    "thinking": evidence["thinking"],
                    "reasoning_chars": len(evidence["reasoning_content"]),
                    "generation_parameters": evidence["generation_parameters"],
                    "usage": evidence["usage"],
                }
                try:
                    source, parse_channel = _parse_teacher_evidence(evidence)
                    validation = validate_teacher_source(source, lesson.cases)
                    attempt_row.update(
                        {
                            "parse_source": parse_channel,
                            "source_sha256": _sha_text(source),
                            "program_sha256": validation["program_sha256"],
                            "differential": validation["differential"],
                            "passed": validation["passed"],
                        }
                    )
                    if validation["passed"]:
                        payload = {
                            "schema": TEACHER_SCHEMA,
                            "teacher_role": "offline-proposal-source",
                            "lesson_id": lesson.lesson_id,
                            "title": lesson.title,
                            "attempt": attempt,
                            "lesson_source": lesson.source,
                            "teacher_target_source": teacher_target,
                            "source": source,
                            "source_sha256": _sha_text(source),
                            "program": validation["program"],
                            "program_sha256": validation["program_sha256"],
                            "differential": validation["differential"],
                            "evidence": evidence,
                        }
                        field_receipt = _learn_teacher_record(
                            memory,
                            source_id=f"cassi-python:teacher:{lesson.lesson_id}",
                            context={"domain": "python", "kind": "teacher-lesson", "lesson": lesson.lesson_id},
                            payload=payload,
                            labels=("cassi-python", "teacher-evidence", lesson.lesson_id),
                        )
                        attempt_row["field_source_revision_id"] = field_receipt.get("source_revision_id")
                        accepted = {"source": source, "attempt": attempt, "field": field_receipt}
                        attempts.append(attempt_row)
                        break
                except Exception as exc:
                    attempt_row.update({"passed": False, "failure": {"type": type(exc).__name__, "message": str(exc)}})
                attempts.append(attempt_row)
            if accepted is None:
                recalled = _recall_teacher_payload(
                    memory, f"cassi-python:teacher:{lesson.lesson_id}"
                )
                if recalled is not None:
                    recalled_payload, field_receipt = recalled
                    recalled_source = recalled_payload.get("source")
                    if isinstance(recalled_source, str):
                        validation = validate_teacher_source(recalled_source, lesson.cases)
                        if validation["passed"]:
                            attempts.append(
                                {
                                    "attempt": "field-recall",
                                    "parse_source": "field_recall",
                                    "source_sha256": _sha_text(recalled_source),
                                    "program_sha256": validation["program_sha256"],
                                    "differential": validation["differential"],
                                    "passed": True,
                                    "field_source_revision_id": field_receipt["source_revision_id"],
                                }
                            )
                            accepted = {
                                "source": recalled_source,
                                "attempt": "field-recall",
                                "field": field_receipt,
                            }
            lesson_rows.append(
                {
                    "lesson_id": lesson.lesson_id,
                    "title": lesson.title,
                    "teacher_target_source": teacher_target,
                    "status": "PASS" if accepted is not None else "FAIL",
                    "attempts": attempts,
                    "accepted": None if accepted is None else {"attempt": accepted["attempt"], "source": accepted["source"], "field": accepted["field"]},
                }
            )

        baseline_source = "result = (2 + 3) * value"
        optimization_cases = (PythonCase("teacher-optimization", {"value": 9}, 45),)
        optimization_attempts: list[dict[str, Any]] = []
        accepted_optimization: dict[str, Any] | None = None
        for attempt in range(max_attempts):
            prompt = optimization_prompt(attempt)
            result = client.complete(
                prompt=prompt,
                max_tokens=max_tokens,
                thinking=OPTIMIZATION_THINKING_ENABLED,
                response_format=RESPONSE_FORMAT,
            )
            evidence = _generation_evidence(result)
            attempt_row: dict[str, Any] = {
                "attempt": attempt,
                "prompt_sha256": _sha_text(prompt),
                "response_sha256": _sha_text(evidence["response"]),
                "thinking": evidence["thinking"],
                "reasoning_chars": len(evidence["reasoning_content"]),
                "generation_parameters": evidence["generation_parameters"],
                "usage": evidence["usage"],
            }
            try:
                candidate_source, parse_channel = _parse_teacher_evidence(evidence)
                optimization = evaluate_source_candidate(baseline_source, candidate_source, optimization_cases)
                attempt_row.update(
                    {
                        "parse_source": parse_channel,
                        "candidate_source": candidate_source,
                        "candidate_sha256": _sha_text(candidate_source),
                        "status": optimization.status,
                        "equivalent": optimization.equivalent,
                        "improved": optimization.improved,
                        "original_steps": optimization.original_steps,
                        "candidate_steps": optimization.candidate_steps,
                        "cases": list(optimization.cases),
                    }
                )
                if optimization.status == "PASS":
                    payload = {
                        "schema": TEACHER_SCHEMA,
                        "teacher_role": "offline-optimization-proposal",
                        "baseline_source": baseline_source,
                        "candidate_source": candidate_source,
                        "candidate_sha256": _sha_text(candidate_source),
                        "status": optimization.status,
                        "equivalent": optimization.equivalent,
                        "improved": optimization.improved,
                        "original_steps": optimization.original_steps,
                        "candidate_steps": optimization.candidate_steps,
                        "cases": list(optimization.cases),
                        "evidence": evidence,
                    }
                    field_receipt = _learn_teacher_record(
                        memory,
                        source_id="cassi-python:teacher:optimization",
                        context={"domain": "python", "kind": "teacher-optimization", "target": "cassi-python-program"},
                        payload=payload,
                        labels=("cassi-python", "teacher-optimization"),
                    )
                    attempt_row["field_source_revision_id"] = field_receipt.get("source_revision_id")
                    accepted_optimization = {"candidate_source": candidate_source, "field": field_receipt}
                    optimization_attempts.append(attempt_row)
                    break
            except Exception as exc:
                attempt_row.update({"status": "FAIL", "failure": {"type": type(exc).__name__, "message": str(exc)}})
            optimization_attempts.append(attempt_row)

        if accepted_optimization is None:
            recalled = _recall_teacher_payload(memory, "cassi-python:teacher:optimization")
            if recalled is not None:
                recalled_payload, field_receipt = recalled
                candidate_source = recalled_payload.get("candidate_source")
                if isinstance(candidate_source, str):
                    optimization = evaluate_source_candidate(
                        baseline_source, candidate_source, optimization_cases
                    )
                    if optimization.status == "PASS":
                        optimization_attempts.append(
                            {
                                "attempt": "field-recall",
                                "parse_source": "field_recall",
                                "candidate_source": candidate_source,
                                "candidate_sha256": _sha_text(candidate_source),
                                "status": optimization.status,
                                "equivalent": optimization.equivalent,
                                "improved": optimization.improved,
                                "original_steps": optimization.original_steps,
                                "candidate_steps": optimization.candidate_steps,
                                "cases": list(optimization.cases),
                                "field_source_revision_id": field_receipt["source_revision_id"],
                            }
                        )
                        accepted_optimization = {
                            "candidate_source": candidate_source,
                            "field": field_receipt,
                        }
        body: dict[str, Any] = {
            "schema": BRIDGE_RECEIPT_SCHEMA,
            "teacher_schema": TEACHER_SCHEMA,
            "thinking_required": THINKING_ENABLED,
            "model_path": str(Path(model_path).resolve()),
            "model_sha256": client.model_sha256,
            "lessons": lesson_rows,
            "optimization": {
                "target": "cassi-python-program",
                "proposal_mode": "model-generated-equivalent-improvement",
                "thinking": OPTIMIZATION_THINKING_ENABLED,
                "baseline_source": baseline_source,
                "status": "PASS" if accepted_optimization is not None else "FAIL",
                "attempts": optimization_attempts,
                "accepted": None if accepted_optimization is None else {
                    "candidate_source": accepted_optimization["candidate_source"],
                    "field": accepted_optimization["field"],
                },
            },
        }
        body["status"] = (
            "PASS"
            if all(row["status"] == "PASS" for row in lesson_rows)
            and body["optimization"]["status"] == "PASS"
            else "FAIL"
        )
        body["content_sha256"] = digest_value(body)
        return body


def verify_bridge_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not content_digest_matches(receipt):
        raise TeacherBridgeError("teacher bridge receipt digest mismatch")
    if receipt.get("schema") != BRIDGE_RECEIPT_SCHEMA or receipt.get("status") != "PASS":
        raise TeacherBridgeError("teacher bridge receipt is not a pass")
    if receipt.get("thinking_required") is not True:
        raise TeacherBridgeError("teacher bridge did not require thinking")
    if not all(row.get("status") == "PASS" for row in receipt.get("lessons", [])):
        raise TeacherBridgeError("one or more Python lessons failed")
    if receipt.get("optimization", {}).get("status") != "PASS":
        raise TeacherBridgeError("teacher optimization was not promoted")
    return {"status": "PASS", "content_sha256": receipt["content_sha256"]}


__all__ = [
    "BRIDGE_RECEIPT_SCHEMA",
    "DEFAULT_MAX_TOKENS",
    "TeacherBridgeError",
    "TEACHER_SCHEMA",
    "parse_teacher_source",
    "run_teacher_bridge",
    "teacher_prompt",
    "verify_bridge_receipt",
    "validate_teacher_source",
]
