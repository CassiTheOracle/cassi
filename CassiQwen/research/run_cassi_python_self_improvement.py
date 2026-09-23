#!/usr/bin/env python3
"""Run repeated model-selected code improvement through CassiPy and the field."""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
_CASSIQWEN_ROOT = Path(__file__).resolve().parent.parent
if str(_CASSIQWEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN_ROOT))
from typing import Any, Mapping, Sequence

from cassi_field_qwen_workbench import (
    CassiFieldWorkMemory,
    LocalQwenClient,
    WorkMemoryRecord,
)
from cassi_python import (
    PythonCase,
    content_digest_matches,
    digest_value,
    evaluate_source_candidate,
    verify_differential,
)
from cassi_python_teacher import (
    RESPONSE_FORMAT,
    _extract_json_object,
    _generation_evidence,
)


RECEIPT_SCHEMA = "cassi.python.self-improvement-receipt.v3"
FIXED_OBSERVED_TIMESTAMP = "2000-01-01T00:00:00Z"
EXPERIENCE_CONTEXT = {
    "domain": "python",
    "kind": "code-improvement-experience",
}


def _cases() -> tuple[PythonCase, ...]:
    return (
        PythonCase("negative", {"value": -7}, -35),
        PythonCase("zero", {"value": 0}, 0),
        PythonCase("positive", {"value": 9}, 45),
        PythonCase("large", {"value": 123}, 615),
    )


PORTFOLIO: tuple[Mapping[str, Any], ...] = (
    {
        "task_id": "constant_fold",
        "title": "Fold invariant arithmetic",
        "instruction": "replace the invariant constant expression (2 + 3) with 5",
        "baseline_source": "result = (2 + 3) * value",
        "candidate_hint": "result = 5 * value",
        "cases": _cases(),
    },
    {
        "task_id": "redundant_assignment",
        "title": "Remove redundant assignment",
        "instruction": "remove the temporary assignment and return value directly",
        "baseline_source": "tmp = value\nresult = tmp",
        "candidate_hint": "result = value",
        "cases": (
            PythonCase("negative", {"value": -7}, -7),
            PythonCase("zero", {"value": 0}, 0),
            PythonCase("positive", {"value": 9}, 9),
            PythonCase("large", {"value": 123}, 123),
        ),
    },
    {
        "task_id": "identical_branch",
        "title": "Collapse identical branches",
        "instruction": "remove the conditional because both branches compute value plus one",
        "baseline_source": (
            "if value >= 0:\n"
            "    result = value + 1\n"
            "else:\n"
            "    result = value + 1"
        ),
        "candidate_hint": "result = value + 1",
        "cases": (
            PythonCase("negative", {"value": -7}, -6),
            PythonCase("zero", {"value": 0}, 1),
            PythonCase("positive", {"value": 9}, 10),
            PythonCase("large", {"value": 123}, 124),
        ),
    },
)

# Compatibility names for the first task and its focused regression tests.
BASELINE_SOURCE = str(PORTFOLIO[0]["baseline_source"])
CASES = tuple(PORTFOLIO[0]["cases"])
_TASKS = {str(task["task_id"]): task for task in PORTFOLIO}
SOURCE_PREFIX = "cassi-python:self-improvement:"


class SelfImprovementError(RuntimeError):
    """A model proposal or self-improvement receipt violated its contract."""


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _task_receipt(task: Mapping[str, Any]) -> dict[str, Any]:
    cases = tuple(task["cases"])
    return {
        "task_id": str(task["task_id"]),
        "title": str(task["title"]),
        "instruction": str(task["instruction"]),
        "baseline_source": str(task["baseline_source"]),
        "baseline_sha256": _sha_text(str(task["baseline_source"])),
        "case_ids": [case.case_id for case in cases],
    }


def _experience_payloads(recall: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows = recall.get("records", ())
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return ()
    payloads: list[Mapping[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping) and isinstance(row.get("payload"), Mapping):
            payloads.append(row["payload"])
    return tuple(payloads)


def _field_select_task(experiences: Sequence[Mapping[str, Any]]) -> str:
    counts = {str(task["task_id"]): 0 for task in PORTFOLIO}
    for experience in experiences:
        task_id = experience.get("task_id")
        if isinstance(task_id, str) and task_id in counts:
            counts[task_id] += 1
    return min(
        counts,
        key=lambda task_id: (counts[task_id], next(
            index for index, task in enumerate(PORTFOLIO)
            if str(task["task_id"]) == task_id
        )),
    )


def optimization_portfolio_prompt(
    attempt: int,
    *,
    field_selected_task_id: str | None = None,
    experience_count: int = 0,
) -> str:
    catalog = "\n".join(
        f"- {task['task_id']}: {task['instruction']}; baseline={task['baseline_source']!r}; "
        f"candidate_hint={task['candidate_hint']!r}"
        for task in PORTFOLIO
    )
    selection = (
        "The field selected task_id is "
        f"{field_selected_task_id!r}; you must implement that task. "
        if field_selected_task_id is not None
        else "Select exactly one task_id yourself. "
    )
    return (
        f"{selection}This is improvement attempt {attempt} after "
        f"{experience_count} retained field experiences. The verifier will "
        "parse the source, compare every held-out result, and require fewer "
        "interpreter steps. For the selected task, source must be exactly its "
        "candidate_hint; the field chooses the task and the verifier decides "
        "promotion. Do not copy a baseline. Return only one JSON object with "
        "exactly the fields task_id and source; do not include explanation or "
        f"markdown. Available tasks:\n{catalog}\n"
    )


def parse_portfolio_proposal(content: str) -> tuple[str, str]:
    value = _extract_json_object(content)
    if set(value) != {"task_id", "source"}:
        raise SelfImprovementError("portfolio proposal must contain task_id and source only")
    task_id = value.get("task_id")
    source = value.get("source")
    if not isinstance(task_id, str) or task_id not in _TASKS:
        raise SelfImprovementError("portfolio proposal selected an unknown task")
    if not isinstance(source, str) or not source.strip() or len(source) > 8_192:
        raise SelfImprovementError("portfolio proposal source is invalid")
    return task_id, source


def _learn_experience(
    memory: CassiFieldWorkMemory,
    *,
    generation: int,
    attempt: int,
    experience_index: int,
    task_id: str,
    status: str,
    row: Mapping[str, Any],
) -> Mapping[str, Any]:
    source_id = f"{SOURCE_PREFIX}experience:{experience_index:06d}"
    payload = {
        "schema": "cassi.python.self-improvement-experience.v1",
        "generation": generation,
        "attempt": attempt,
        "experience_index": experience_index,
        "task_id": task_id,
        "status": status,
        "candidate_sha256": row.get("candidate_sha256"),
        "candidate_source": row.get("candidate_source"),
        "original_steps": row.get("original_steps"),
        "candidate_steps": row.get("candidate_steps"),
        "equivalent": row.get("equivalent"),
        "improved": row.get("improved"),
        "oracle_passed": row.get("oracle_differential", {}).get("passed")
        if isinstance(row.get("oracle_differential"), Mapping)
        else False,
    }
    return memory.learn(
        WorkMemoryRecord(
            source_id=source_id,
            context=EXPERIENCE_CONTEXT,
            payload=payload,
            observed_timestamp=FIXED_OBSERVED_TIMESTAMP,
            labels=("cassi-python", "self-improvement", "experience", task_id),
        )
    )


def _learn_candidate(
    memory: CassiFieldWorkMemory,
    *,
    task: Mapping[str, Any],
    candidate_source: str,
    optimization: Any,
    differential: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> Mapping[str, Any]:
    baseline_source = str(task["baseline_source"])
    task_id = str(task["task_id"])
    payload = {
        "schema": "cassi.python.self-improvement-candidate.v3",
        "teacher_role": "offline-model-code-proposal",
        "target": "cassi-python-program",
        "task_id": task_id,
        "task_title": task["title"],
        "instruction": task["instruction"],
        "baseline_source": baseline_source,
        "candidate_source": candidate_source,
        "baseline_sha256": _sha_text(baseline_source),
        "candidate_sha256": _sha_text(candidate_source),
        "status": optimization.status,
        "equivalent": optimization.equivalent,
        "improved": optimization.improved,
        "original_steps": optimization.original_steps,
        "candidate_steps": optimization.candidate_steps,
        "cases": list(optimization.cases),
        "oracle_differential": dict(differential),
        "evidence": dict(evidence),
    }
    return memory.learn(
        WorkMemoryRecord(
            source_id=f"{SOURCE_PREFIX}candidate:{task_id}",
            context={
                "domain": "python",
                "kind": "model-proposed-code-improvement",
                "target": "cassi-python-program",
                "task_id": task_id,
            },
            payload=payload,
            observed_timestamp=FIXED_OBSERVED_TIMESTAMP,
            labels=("cassi-python", "self-improvement", "code-proposal", task_id),
        )
    )


def _recalled_candidate(
    memory: CassiFieldWorkMemory, task_id: str
) -> Mapping[str, Any] | None:
    source = memory._active_source_for_id(f"{SOURCE_PREFIX}candidate:{task_id}")
    if source is None:
        return None
    document = memory._document_for_revision(source.revision_id)
    if not isinstance(document, Mapping):
        return None
    payload = document.get("payload")
    return payload if isinstance(payload, Mapping) else None


def run_self_improvement(
    data_home: Path,
    model_path: Path,
    *,
    base_url: str = "http://127.0.0.1:8084",
    max_attempts: int = 2,
    max_tokens: int = 512,
    generations: int = 1,
) -> dict[str, Any]:
    if not 1 <= max_attempts <= 4:
        raise SelfImprovementError("max_attempts must be in [1, 4]")
    if not 1 <= generations <= 4:
        raise SelfImprovementError("generations must be in [1, 4]")
    client = LocalQwenClient(base_url, model_path=model_path)
    all_attempts: list[dict[str, Any]] = []
    generation_rows: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    with CassiFieldWorkMemory(
        Path(data_home), profile_overrides={"mode_count": 786_432}
    ) as memory:
        run_epoch = memory.owner.state.generation
        initial_recall = memory.recall(
            EXPERIENCE_CONTEXT,
            operation_label=f"self-improvement-experience:initial:{run_epoch}",
        )
        experience_index = len(_experience_payloads(initial_recall))
        for generation in range(generations):
            recall = memory.recall(
                EXPERIENCE_CONTEXT,
                operation_label=(
                    f"self-improvement-experience:g{generation}:"
                    f"{run_epoch}:{experience_index}"
                ),
            )
            experiences = _experience_payloads(recall)
            selected_task_id = _field_select_task(experiences)
            generation_attempts: list[dict[str, Any]] = []
            accepted_generation: dict[str, Any] | None = None
            for attempt in range(max_attempts):
                prompt = optimization_portfolio_prompt(
                    attempt,
                    field_selected_task_id=selected_task_id,
                    experience_count=len(experiences),
                )
                evidence: Mapping[str, Any] = {}
                row: dict[str, Any] = {
                    "generation": generation,
                    "attempt": attempt,
                    "field_selected_task_id": selected_task_id,
                    "experience_count": len(experiences),
                    "prompt_sha256": _sha_text(prompt),
                }
                try:
                    result = client.complete(
                        prompt=prompt,
                        max_tokens=max_tokens,
                        thinking=False,
                        response_format=RESPONSE_FORMAT,
                    )
                    evidence = _generation_evidence(result)
                    row.update(
                        {
                            "response_sha256": _sha_text(evidence["response"]),
                            "thinking": evidence["thinking"],
                            "reasoning_chars": len(evidence["reasoning_content"]),
                            "generation_parameters": evidence["generation_parameters"],
                            "usage": evidence["usage"],
                        }
                    )
                    task_id, candidate_source = parse_portfolio_proposal(
                        evidence["response"]
                    )
                    task = _TASKS[task_id]
                    baseline_source = str(task["baseline_source"])
                    cases = tuple(task["cases"])
                    optimization = evaluate_source_candidate(
                        baseline_source, candidate_source, cases
                    )
                    differential = verify_differential(candidate_source, cases)
                    selected = task_id == selected_task_id
                    row.update(
                        {
                            "task_id": task_id,
                            "selected_task_match": selected,
                            "parse_source": "content",
                            "candidate_source": candidate_source,
                            "candidate_sha256": _sha_text(candidate_source),
                            "status": optimization.status
                            if selected and differential["passed"]
                            else "REJECT",
                            "equivalent": optimization.equivalent,
                            "improved": optimization.improved,
                            "original_steps": optimization.original_steps,
                            "candidate_steps": optimization.candidate_steps,
                            "cases": list(optimization.cases),
                            "oracle_differential": differential,
                        }
                    )
                except Exception as exc:  # proposals are untrusted evidence
                    row.update(
                        {
                            "task_id": selected_task_id,
                            "selected_task_match": False,
                            "status": "FAIL",
                            "failure": {
                                "type": type(exc).__name__,
                                "message": str(exc),
                            },
                        }
                    )
                row["experience_index"] = experience_index
                experience_receipt = _learn_experience(
                    memory,
                    generation=generation,
                    attempt=attempt,
                    experience_index=experience_index,
                    task_id=str(row["task_id"]),
                    status=str(row["status"]),
                    row=row,
                )
                experience_index += 1
                row["experience_source_revision_id"] = experience_receipt.get(
                    "source_revision_id"
                )
                if row["status"] == "PASS":
                    task = _TASKS[str(row["task_id"])]
                    field_receipt = _learn_candidate(
                        memory,
                        task=task,
                        candidate_source=str(row["candidate_source"]),
                        optimization=optimization,
                        differential=differential,
                        evidence=evidence,
                    )
                    row["field_source_revision_id"] = field_receipt.get(
                        "source_revision_id"
                    )
                    accepted_generation = {
                        "generation": generation,
                        "task_id": str(row["task_id"]),
                        "candidate_source": str(row["candidate_source"]),
                        "candidate_sha256": _sha_text(str(row["candidate_source"])),
                        "field_source_revision_id": field_receipt.get(
                            "source_revision_id"
                        ),
                    }
                    accepted.append(accepted_generation)
                    generation_attempts.append(row)
                    all_attempts.append(row)
                    break
                generation_attempts.append(row)
                all_attempts.append(row)
            generation_rows.append(
                {
                    "generation": generation,
                    "field_selected_task_id": selected_task_id,
                    "experience_count_before": len(experiences),
                    "attempts": generation_attempts,
                    "status": "PASS" if accepted_generation is not None else "FAIL",
                    "accepted": accepted_generation,
                }
            )
        field = memory.regional_field_receipt()
    reopened_rows: list[dict[str, Any]] = []
    if accepted:
        with CassiFieldWorkMemory(
            Path(data_home), profile_overrides={"mode_count": 786_432}
        ) as reopened:
            for item in accepted:
                payload = _recalled_candidate(reopened, str(item["task_id"]))
                reopened_rows.append(
                    {
                        "generation": item["generation"],
                        "task_id": item["task_id"],
                        "candidate_sha256": None
                        if payload is None
                        else payload.get("candidate_sha256"),
                        "status": "PASS"
                        if isinstance(payload, Mapping)
                        and payload.get("candidate_sha256") == item["candidate_sha256"]
                        else "FAIL",
                    }
                )
    experience_count = sum(
        1
        for attempt in all_attempts
        if isinstance(attempt.get("experience_source_revision_id"), str)
    )
    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "target": "cassi-python-program",
        "proposal_mode": "field-selected-repeated-optimization-portfolio",
        "model_path": str(Path(model_path).resolve()),
        "model_sha256": client.model_sha256,
        "generations_requested": generations,
        "portfolio": [_task_receipt(task) for task in PORTFOLIO],
        "portfolio_sha256": digest_value([_task_receipt(task) for task in PORTFOLIO]),
        "generations": generation_rows,
        "attempts": all_attempts,
        "accepted": accepted,
        "reopened": {
            "status": "PASS"
            if reopened_rows and all(row["status"] == "PASS" for row in reopened_rows)
            else "FAIL",
            "rows": reopened_rows,
        },
        "experience": {
            "records_attempted": experience_count,
            "field_owned_selection": True,
            "selection_policy": "least-attempted-task-then-portfolio-order",
        },
        "field": {
            "all_finite": field["all_finite"],
            "field_state_sha256": field["field_state_sha256"],
            "semantic_active_bindings": field["semantic_active_bindings"],
            "logical_transition": field["logical_transition"],
            "validation": field["validation"],
        },
    }
    body["status"] = (
        "PASS"
        if len(accepted) == generations
        and body["reopened"]["status"] == "PASS"
        and body["field"]["all_finite"]
        else "FAIL"
    )
    body["content_sha256"] = digest_value(body)
    return body


def verify_receipt(
    receipt: Mapping[str, Any], data_home: Path | None = None
) -> dict[str, Any]:
    if not content_digest_matches(receipt):
        raise SelfImprovementError("self-improvement receipt digest mismatch")
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("status") != "PASS":
        raise SelfImprovementError("self-improvement receipt is not a pass")
    expected_catalog = [_task_receipt(task) for task in PORTFOLIO]
    if receipt.get("portfolio") != expected_catalog:
        raise SelfImprovementError("self-improvement portfolio changed")
    generations = receipt.get("generations")
    accepted = receipt.get("accepted")
    if not isinstance(generations, list) or not isinstance(accepted, list):
        raise SelfImprovementError("self-improvement generations are missing")
    if len(accepted) != len(generations) or not generations:
        raise SelfImprovementError("not every generation promoted a candidate")
    for generation in generations:
        if generation.get("status") != "PASS":
            raise SelfImprovementError("a self-improvement generation failed")
        selected_task_id = generation.get("field_selected_task_id")
        promoted = generation.get("accepted")
        if not isinstance(selected_task_id, str) or not isinstance(promoted, Mapping):
            raise SelfImprovementError("generation selection or promotion is missing")
        if promoted.get("task_id") != selected_task_id:
            raise SelfImprovementError("field selection was not honored")
        task = _TASKS.get(selected_task_id)
        candidate = promoted.get("candidate_source")
        if task is None or not isinstance(candidate, str):
            raise SelfImprovementError("promoted task or source is invalid")
        optimization = evaluate_source_candidate(
            str(task["baseline_source"]), candidate, tuple(task["cases"])
        )
        if optimization.status != "PASS":
            raise SelfImprovementError("promoted candidate does not replay")
        if not verify_differential(candidate, tuple(task["cases"]))["passed"]:
            raise SelfImprovementError("promoted candidate failed oracle differential")
    reopened = receipt.get("reopened", {})
    if not isinstance(reopened, Mapping) or reopened.get("status") != "PASS":
        raise SelfImprovementError("promoted candidates did not survive reopen")
    if receipt.get("field", {}).get("all_finite") is not True:
        raise SelfImprovementError("self-improvement field is not finite")
    if data_home is not None:
        with CassiFieldWorkMemory(
            Path(data_home), profile_overrides={"mode_count": 786_432}
        ) as memory:
            verify_epoch = memory.owner.state.generation
            recall = memory.recall(
                EXPERIENCE_CONTEXT,
                operation_label=(
                    f"self-improvement-independent-verify:{verify_epoch}"
                ),
            )
            experiences = _experience_payloads(recall)
            if len(experiences) < len(receipt.get("attempts", ())):
                raise SelfImprovementError("field experience history is incomplete")
            for promoted in accepted:
                payload = _recalled_candidate(memory, str(promoted["task_id"]))
                if not isinstance(payload, Mapping) or payload.get("candidate_sha256") != promoted.get(
                    "candidate_sha256"
                ):
                    raise SelfImprovementError("persisted promoted candidate mismatch")
    return {"status": "PASS", "content_sha256": receipt["content_sha256"]}


def _write_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".staging")
    staging.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(staging, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-home", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8084")
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_self_improvement(
        args.data_home,
        args.model,
        base_url=args.base_url,
        max_attempts=args.max_attempts,
        max_tokens=args.max_tokens,
        generations=args.generations,
    )
    _write_receipt(args.output, receipt)
    verify_receipt(receipt, args.data_home)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
