#!/usr/bin/env python3
"""Compose promoted code candidates into the next field-owned program state."""
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
from cassi_teacher_field import TeacherFieldController
from cassi_python import (
    PythonCase,
    content_digest_matches,
    digest_value,
    evaluate_source_candidate,
    parse_source,
    verify_differential,
)
from cassi_python_teacher import RESPONSE_FORMAT, _extract_json_object, _generation_evidence
from run_cassi_python_self_improvement import SelfImprovementError


RECEIPT_SCHEMA = "cassi.python.self-improvement-cumulative-receipt.v5"
FIXED_OBSERVED_TIMESTAMP = "2000-01-01T00:00:00Z"
EXPERIENCE_CONTEXT = {
    "domain": "python",
    "kind": "cumulative-code-improvement-experience",
}
STATE_CONTEXT = {
    "domain": "python",
    "kind": "cumulative-code-state",
}
SOURCE_PREFIX = "cassi-python:cumulative:"

BASELINE_SOURCE = (
    "tmp = value\n"
    "result = (2 + 3) * tmp + 1 if value >= 0 else (2 + 3) * tmp + 1"
)
CASES = (
    PythonCase("negative", {"value": -7}, -34),
    PythonCase("zero", {"value": 0}, 1),
    PythonCase("positive", {"value": 9}, 46),
    PythonCase("large", {"value": 123}, 616),
)
TASKS: tuple[Mapping[str, Any], ...] = (
    {
        "task_id": "constant_fold",
        "title": "Fold invariant arithmetic in the current program",
        "instruction": "replace the invariant expression (2 + 3) with 5, and make no other transformation",
    },
    {
        "task_id": "redundant_assignment",
        "title": "Remove the temporary from the current program",
        "instruction": "remove tmp = value and use value directly at both result sites, and make no other transformation",
    },
    {
        "task_id": "identical_branch",
        "title": "Collapse the identical branches in the current program",
        "instruction": "remove the conditional expression because both arms compute the same result, and make no other transformation",
    },
    {
        "task_id": "redundant_add_zero",
        "title": "Remove an additive identity",
        "instruction": "replace an addition by zero with its unchanged operand, and make no other transformation",
    },
    {
        "task_id": "redundant_multiply_one",
        "title": "Remove a multiplicative identity",
        "instruction": "replace multiplication by one with its unchanged operand, and make no other transformation",
    },
)
_TASKS = {str(task["task_id"]): task for task in TASKS}
_TASK_ORDER = {str(task["task_id"]): index for index, task in enumerate(TASKS)}


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _task_receipt(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": str(task["task_id"]),
        "title": str(task["title"]),
        "instruction": str(task["instruction"]),
    }


def _payloads(recall: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows = recall.get("records", ())
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return ()
    return tuple(
        row["payload"]
        for row in rows
        if isinstance(row, Mapping) and isinstance(row.get("payload"), Mapping)
    )


def _ast_nodes(source: str) -> tuple[Mapping[str, Any], ...]:
    tree = parse_source(source, params=tuple(CASES[0].inputs))
    found: list[Mapping[str, Any]] = []
    pending: list[Any] = [tree]
    while pending:
        value = pending.pop()
        if isinstance(value, Mapping):
            found.append(value)
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return tuple(found)


def _is_constant(node: Any, expected: Any) -> bool:
    return (
        isinstance(node, Mapping)
        and node.get("type") == "constant"
        and node.get("value") == expected
    )


def _is_identity_binop(node: Any, op: str, identity: Any) -> bool:
    if not isinstance(node, Mapping) or node.get("type") != "binop" or node.get("op") != op:
        return False
    return _is_constant(node.get("right"), identity) or (
        op == "mul" and _is_constant(node.get("left"), identity)
    )
def _is_constant_fold_binop(node: Any) -> bool:
    return (
        isinstance(node, Mapping)
        and node.get("type") == "binop"
        and node.get("op") == "add"
        and (
            (_is_constant(node.get("left"), 2) and _is_constant(node.get("right"), 3))
            or (_is_constant(node.get("left"), 3) and _is_constant(node.get("right"), 2))
        )
    )




def _eligible(source: str, task_id: str) -> bool:
    nodes = _ast_nodes(source)
    if task_id == "constant_fold":
        return any(_is_constant_fold_binop(node) for node in nodes)
    if task_id == "redundant_assignment":
        return any(
            node.get("type") == "assign"
            and isinstance(node.get("target"), Mapping)
            and node["target"].get("type") == "name"
            and node["target"].get("id") == "tmp"
            for node in nodes
        )
    if task_id == "identical_branch":
        return any(
            node.get("type") == "ifexp" and node.get("then") == node.get("else")
            for node in nodes
        )
    if task_id == "redundant_add_zero":
        return any(_is_identity_binop(node, "add", 0) for node in nodes)
    if task_id == "redundant_multiply_one":
        return any(_is_identity_binop(node, "mul", 1) for node in nodes)
    raise SelfImprovementError(f"unknown cumulative task {task_id}")


def _task_local_invariant(previous: str, candidate: str, task_id: str) -> bool:
    before = _ast_nodes(previous)
    after = _ast_nodes(candidate)
    if task_id == "constant_fold":
        before_count = sum(_is_constant_fold_binop(node) for node in before)
        after_count = sum(_is_constant_fold_binop(node) for node in after)
        return before_count > after_count and any(
            _is_constant(node, 5) for node in after
        )
    if task_id == "redundant_assignment":
        before_count = sum(
            1
            for node in before
            if node.get("type") == "assign"
            and isinstance(node.get("target"), Mapping)
            and node["target"].get("type") == "name"
            and node["target"].get("id") == "tmp"
        )
        after_tmp = any(
            node.get("type") == "name" and node.get("id") == "tmp" for node in after
        )
        return before_count > 0 and not after_tmp
    if task_id == "identical_branch":
        before_count = sum(
            1
            for node in before
            if node.get("type") == "ifexp" and node.get("then") == node.get("else")
        )
        after_count = sum(
            1
            for node in after
            if node.get("type") == "ifexp" and node.get("then") == node.get("else")
        )
        return before_count > after_count
    if task_id == "redundant_add_zero":
        before_count = sum(_is_identity_binop(node, "add", 0) for node in before)
        after_count = sum(_is_identity_binop(node, "add", 0) for node in after)
        return before_count > after_count
    if task_id == "redundant_multiply_one":
        before_count = sum(_is_identity_binop(node, "mul", 1) for node in before)
        after_count = sum(_is_identity_binop(node, "mul", 1) for node in after)
        return before_count > after_count
    raise SelfImprovementError(f"unknown cumulative task {task_id}")


def field_select_task(source: str, experiences: Sequence[Mapping[str, Any]]) -> str | None:
    counts = {
        task_id: sum(1 for row in experiences if row.get("task_id") == task_id)
        for task_id in _TASKS
    }
    eligible = [task_id for task_id in _TASKS if _eligible(source, task_id)]
    if not eligible:
        return None
    return min(eligible, key=lambda task_id: (counts[task_id], _TASK_ORDER[task_id]))


def expected_candidate(source: str, task_id: str) -> str:
    if task_id == "constant_fold":
        return source.replace("(2 + 3)", "5").replace("(3 + 2)", "5")
    if task_id == "redundant_assignment":
        return source.replace("tmp = value\n", "").replace(" * tmp", " * value")
    if task_id == "identical_branch":
        return "result = 5 * value + 1"
    if task_id == "redundant_add_zero":
        return source.replace(" + 0", "", 1)
    if task_id == "redundant_multiply_one":
        return source.replace(" * 1", "", 1).replace("1 * ", "", 1)
    raise SelfImprovementError(f"unknown cumulative task {task_id}")
def _candidate_pool_for_task(source: str, task_id: str) -> tuple[Mapping[str, Any], ...]:
    canonical = expected_candidate(source, task_id)
    if task_id == "constant_fold":
        alternatives = (
            ("canonical", canonical),
            ("unchanged", source),
            ("drop_offset", canonical.replace(" + 1", "")),
        )
    elif task_id == "redundant_assignment":
        alternatives = (
            ("canonical", canonical),
            ("unchanged", source),
            ("wrong_binding", canonical.replace("value", "value + 1")),
        )
    elif task_id == "identical_branch":
        alternatives = (
            ("canonical", canonical),
            ("parenthesized", "result = (5 * value) + 1"),
            ("commuted_multiply", "result = value * 5 + 1"),
            ("unchanged", source),
            ("drop_offset", "result = 5 * value"),
        )
    elif task_id == "redundant_add_zero":
        alternatives = (
            ("canonical", canonical),
            ("unchanged", source),
            ("wrong_binding", canonical.replace("value", "value + 1", 1)),
        )
    elif task_id == "redundant_multiply_one":
        alternatives = (
            ("canonical", canonical),
            ("unchanged", source),
            ("wrong_binding", canonical.replace("value", "value + 1", 1)),
        )
    else:
        raise SelfImprovementError(f"unknown cumulative task {task_id}")
    rows: list[Mapping[str, Any]] = []
    for variant_id, candidate in alternatives:
        optimization = evaluate_source_candidate(source, candidate, CASES)
        differential = verify_differential(candidate, CASES)
        task_invariant = _task_local_invariant(source, candidate, task_id)
        rows.append(
            {
                "edit_id": f"{task_id}:{variant_id}",
                "task_id": task_id,
                "variant_id": variant_id,
                "candidate_source": candidate,
                "candidate_sha256": _sha_text(candidate),
                "status": optimization.status
                if differential["passed"] and task_invariant
                else "REJECT",
                "equivalent": optimization.equivalent,
                "improved": optimization.improved,
                "oracle_passed": differential["passed"],
                "task_invariant": task_invariant,
                "candidate_steps": optimization.candidate_steps,
            }
        )
    return tuple(rows)


def field_select_edit(
    source: str, experiences: Sequence[Mapping[str, Any]]
) -> Mapping[str, Any] | None:
    attempted = {
        str(row.get("edit_id")): sum(
            1 for prior in experiences if prior.get("edit_id") == row.get("edit_id")
        )
        for task_id in _TASKS
        if _eligible(source, task_id)
        for row in _candidate_pool_for_task(source, task_id)
    }
    pool = [
        row
        for task_id in _TASKS
        if _eligible(source, task_id)
        for row in _candidate_pool_for_task(source, task_id)
        if row.get("status") == "PASS" and row.get("improved") is True
    ]
    if not pool:
        return None
    return min(
        pool,
        key=lambda row: (
            attempted.get(str(row["edit_id"]), 0),
            _TASK_ORDER[str(row["task_id"])],
            str(row["variant_id"]),
        ),
    )




def cumulative_prompt(
    attempt: int,
    current_source: str,
    selected_task_id: str,
    experience_count: int,
    selected_edit_id: str | None = None,
) -> str:
    task = _TASKS[selected_task_id]
    required_change = {
        "constant_fold": "The candidate MUST contain 5 and MUST NOT contain (2 + 3).",
        "redundant_assignment": "The candidate MUST NOT contain the line tmp = value.",
        "identical_branch": "The candidate MUST NOT contain the conditional expression.",
        "redundant_add_zero": "The candidate MUST remove the AST addition whose identity operand is zero.",
        "redundant_multiply_one": "The candidate MUST remove the AST multiplication whose identity operand is one.",
    }[selected_task_id]
    target = expected_candidate(current_source, selected_task_id)
    return (
        f"This is cumulative improvement attempt {attempt} after {experience_count} "
        "retained field experiences. The field selected exactly task_id "
        f"{selected_task_id!r} and edit_id {selected_edit_id or f'{selected_task_id}:canonical'!r}. "
        "Apply only this transformation: "
        f"{task['instruction']} {required_change} The current program is:\n"
        f"```python\n{current_source}\n```\n"
        "Preserve every result on the held-out inputs. Return exactly this "
        "JSON shape and replace only the source value with TARGET:\n"
        f'{{"task_id":"{selected_task_id}","source":"{target}"}}\n'
        "Do not add fields, markdown, or explanation. Use JSON \\n escapes for "
        "source line breaks; never replace line breaks with semicolons."
    )


def parse_proposal(content: str) -> tuple[str, str]:
    value = _extract_json_object(content)
    if set(value) != {"task_id", "source"}:
        raise SelfImprovementError("cumulative proposal must contain task_id and source only")
    task_id = value.get("task_id")
    source = value.get("source")
    if not isinstance(task_id, str) or task_id not in _TASKS:
        raise SelfImprovementError("cumulative proposal selected an unknown task")
    if not isinstance(source, str) or not source.strip() or len(source) > 8_192:
        raise SelfImprovementError("cumulative proposal source is invalid")
    return task_id, source


def parse_proposals(content: str) -> tuple[Mapping[str, str], ...]:
    value = _extract_json_object(content)
    if set(value) != {"proposals"}:
        raise SelfImprovementError("cumulative multi-proposal response must contain proposals only")
    proposals = value.get("proposals")
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= 4:
        raise SelfImprovementError("cumulative response must contain one to four proposals")
    parsed: list[Mapping[str, str]] = []
    seen_ids: set[str] = set()
    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, Mapping) or set(proposal) != {
            "proposal_id",
            "task_id",
            "source",
        }:
            raise SelfImprovementError("each cumulative proposal has an invalid shape")
        raw_id = proposal.get("proposal_id")
        proposal_id = (
            raw_id
            if isinstance(raw_id, str) and raw_id and raw_id not in seen_ids
            else f"invalid-proposal-{index}"
        )
        raw_task_id = proposal.get("task_id")
        task_id = raw_task_id if isinstance(raw_task_id, str) else ""
        raw_source = proposal.get("source")
        source = raw_source if isinstance(raw_source, str) else ""
        seen_ids.add(proposal_id)
        parsed.append(
            {
                "proposal_id": proposal_id,
                "task_id": task_id,
                "source": source,
            }
        )
    return tuple(parsed)


def cumulative_multi_prompt(
    attempt: int,
    current_source: str,
    selected_task_id: str,
    experience_count: int,
    selected_edit_id: str,
    task_pool: Sequence[Mapping[str, Any]],
    control_frame: Mapping[str, Any] | None = None,
) -> str:
    task = _TASKS[selected_task_id]
    examples = [
        {
            "edit_id": row["edit_id"],
            "source": row["candidate_source"],
        }
        for row in task_pool
        if row.get("status") == "PASS" and row.get("improved") is True
    ]
    control_text = (
        ""
        if control_frame is None
        else (
            "Consume this fixed field control frame exactly; do not alter it: "
            f"{json.dumps(dict(control_frame), ensure_ascii=False, sort_keys=True)}\n"
        )
    )
    return (
        f"This is cumulative improvement attempt {attempt} after {experience_count} "
        "retained field experiences. The field selected one task and edit family: "
        f"task_id {selected_task_id!r}, edit_id {selected_edit_id!r}. "
        f"{control_text}"
        f"Apply only this task: {task['instruction']} The current program is:\n"
        f"```python\n{current_source}\n```\n"
        "Return two to four distinct proposals for the same task. The first "
        "proposal may copy a verified candidate, but the second proposal MUST "
        "be novel: its source text must differ from every verified candidate "
        "below while remaining behavior-preserving. The verified candidate "
        "sources below are examples, not an allow-list. Every proposal must "
        "remain inside the bounded CassiPy subset (no imports, attributes, I/O, "
        "reflection, or arbitrary eval/exec), preserve all held-out results, "
        "and reduce the measured execution steps. Use the selected task_id for "
        "every proposal. "
        f"Verified candidate examples: {json.dumps(examples, ensure_ascii=False, sort_keys=True)}\n"
        'Return exactly {"proposals":[{"proposal_id":"PROPOSAL_ID","task_id":"TASK_ID",'
        '"source":"SOURCE"}, ...]}. Do not add fields, markdown, or explanation. '
        "Use JSON \\n escapes for source line breaks."
    )


def _learn_experience(
    memory: CassiFieldWorkMemory,
    *,
    index: int,
    generation: int,
    attempt: int,
    task_id: str,
    status: str,
    row: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = {
        "schema": "cassi.python.self-improvement-cumulative-experience.v2",
        "experience_index": index,
        "generation": generation,
        "attempt": attempt,
        "edit_id": row.get("field_selected_edit_id"),
        "task_id": task_id,
        "status": status,
        "field_planned_edit_id": row.get("field_planned_edit_id"),
        "selected_proposal_id": row.get("selected_proposal_id"),
        "proposal_outcomes": row.get("proposal_outcomes", []),
        "candidate_origin": row.get("candidate_origin"),
        "novel_candidate": row.get("novel_candidate"),
        "previous_source_sha256": row.get("previous_source_sha256"),
        "candidate_sha256": row.get("candidate_sha256"),
        "candidate_source": row.get("candidate_source"),
        "original_steps": row.get("original_steps"),
        "candidate_steps": row.get("candidate_steps"),
        "equivalent": row.get("equivalent"),
        "improved": row.get("improved"),
        "task_invariant": row.get("task_invariant"),
        "oracle_passed": (
            row.get("oracle_differential", {}).get("passed")
            if isinstance(row.get("oracle_differential"), Mapping)
            else False
        ),
    }
    return memory.learn(
        WorkMemoryRecord(
            source_id=f"{SOURCE_PREFIX}experience:{index:06d}",
            context=EXPERIENCE_CONTEXT,
            payload=payload,
            observed_timestamp=FIXED_OBSERVED_TIMESTAMP,
            labels=("cassi-python", "self-improvement", "cumulative", task_id),
        )
    )


def rank_model_proposals(
    previous_source: str,
    selected_task_id: str,
    proposals: Sequence[Mapping[str, str]],
    candidate_pool: Sequence[Mapping[str, Any]],
    experiences: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], Mapping[str, Any] | None]:
    static_by_hash = {
        str(row["candidate_sha256"]): row
        for row in candidate_pool
        if row.get("task_id") == selected_task_id
    }
    experience_counts: dict[str, int] = {}
    for prior in experiences:
        edit_id = prior.get("edit_id")
        if isinstance(edit_id, str):
            experience_counts[edit_id] = experience_counts.get(edit_id, 0) + 1
    outcomes: list[dict[str, Any]] = []
    seen_candidate_hashes: set[str] = set()
    for proposal in proposals:
        source = str(proposal["source"])
        candidate_sha256 = _sha_text(source)
        static = static_by_hash.get(candidate_sha256)
        raw_task_id = str(proposal["task_id"])
        metadata_repair_reason: str | None = None
        if static is not None:
            effective_task_id = str(static["task_id"])
            if raw_task_id != effective_task_id:
                metadata_repair_reason = "source_hash"
        elif raw_task_id == selected_task_id:
            effective_task_id = selected_task_id
        elif raw_task_id.startswith(f"{selected_task_id}:"):
            effective_task_id = selected_task_id
            metadata_repair_reason = "task_id_prefix"
        else:
            effective_task_id = raw_task_id
        edit_id = (
            str(static["edit_id"])
            if static is not None
            else f"model:{candidate_sha256[:16]}"
        )
        candidate_origin = "verified_pool" if static is not None else "model_novel"
        outcome: dict[str, Any] = {
            "proposal_id": str(proposal["proposal_id"]),
            "raw_task_id": raw_task_id,
            "task_id": effective_task_id,
            "candidate_source": source,
            "candidate_sha256": candidate_sha256,
            "candidate_origin": candidate_origin,
            "novel_candidate": candidate_origin == "model_novel",
            "edit_id": edit_id,
            "selected_task_match": effective_task_id == selected_task_id,
            "metadata_repaired": metadata_repair_reason is not None,
            "metadata_repair_reason": metadata_repair_reason,
        }
        if candidate_sha256 in seen_candidate_hashes:
            outcome.update(
                {
                    "status": "REJECT",
                    "failure": {
                        "type": "SelfImprovementError",
                        "message": "duplicate proposal source is not a distinct candidate",
                    },
                }
            )
            if static is not None:
                outcome["pool_variant_id"] = static["variant_id"]
            outcomes.append(outcome)
            continue
        seen_candidate_hashes.add(candidate_sha256)
        try:
            if len(source) > 8_192:
                raise SelfImprovementError("model proposal source exceeds the 8192-character bound")
            optimization = evaluate_source_candidate(previous_source, source, CASES)
            differential = verify_differential(source, CASES)
            task_invariant = _task_local_invariant(previous_source, source, effective_task_id)
            outcome.update(
                {
                    "status": (
                        "PASS"
                        if outcome["selected_task_match"]
                        and optimization.status == "PASS"
                        and differential["passed"]
                        and task_invariant
                        else "REJECT"
                    ),
                    "original_steps": optimization.original_steps,
                    "candidate_steps": optimization.candidate_steps,
                    "equivalent": optimization.equivalent,
                    "improved": optimization.improved,
                    "task_invariant": task_invariant,
                    "cases": list(optimization.cases),
                    "oracle_differential": differential,
                }
            )
        except Exception as exc:
            outcome.update(
                {
                    "status": "FAIL",
                    "failure": {"type": type(exc).__name__, "message": str(exc)},
                }
            )
        if static is not None:
            outcome["pool_variant_id"] = static["variant_id"]
        outcomes.append(outcome)
    promotable = [row for row in outcomes if row.get("status") == "PASS"]
    selected = (
        min(
            promotable,
            key=lambda row: (
                experience_counts.get(str(row["edit_id"]), 0),
                int(row.get("candidate_steps", 1_000_000)),
                0 if row.get("novel_candidate") is True else 1,
                str(row["edit_id"]),
                str(row["proposal_id"]),
            ),
        )
        if promotable
        else None
    )
    for row in outcomes:
        row["field_rank_selected"] = (
            selected is not None and row["proposal_id"] == selected["proposal_id"]
        )
    return outcomes, selected




def _learn_state(
    memory: CassiFieldWorkMemory,
    *,
    index: int,
    generation: int,
    task_id: str,
    previous_source: str,
    candidate_source: str,
    optimization: Any,
    differential: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = {
        "schema": "cassi.python.self-improvement-cumulative-state.v1",
        "state_index": index,
        "generation": generation,
        "task_id": task_id,
        "previous_source_sha256": _sha_text(previous_source),
        "candidate_source": candidate_source,
        "candidate_sha256": _sha_text(candidate_source),
        "original_steps": optimization.original_steps,
        "candidate_steps": optimization.candidate_steps,
        "equivalent": optimization.equivalent,
        "improved": optimization.improved,
        "oracle_differential": dict(differential),
    }
    return memory.learn(
        WorkMemoryRecord(
            source_id=f"{SOURCE_PREFIX}state:{index:06d}",
            context=STATE_CONTEXT,
            payload=payload,
            observed_timestamp=FIXED_OBSERVED_TIMESTAMP,
            labels=("cassi-python", "self-improvement", "cumulative-state", task_id),
        )
    )


def _latest_state(states: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    candidates = [
        state
        for state in states
        if isinstance(state.get("candidate_source"), str)
        and isinstance(state.get("state_index"), int)
    ]
    return max(candidates, key=lambda state: int(state["state_index"])) if candidates else None
def mutation_control_rows() -> list[dict[str, Any]]:
    final_source = "result = 5 * value + 1"
    controls = (
        ("wrong-result", final_source, "result = 5 * value"),
        ("unchanged-source", final_source, final_source),
        (
            "zero-regression",
            final_source,
            "result = 5 * value + 1 if value > 0 else 0",
        ),
    )
    rows: list[dict[str, Any]] = []
    for control_id, previous, candidate in controls:
        optimization = evaluate_source_candidate(previous, candidate, CASES)
        differential = verify_differential(candidate, CASES)
        rows.append(
            {
                "control_id": control_id,
                "previous_source_sha256": _sha_text(previous),
                "candidate_source": candidate,
                "candidate_sha256": _sha_text(candidate),
                "status": (
                    "REJECT"
                    if optimization.status != "PASS" or not differential["passed"]
                    else "FAIL"
                ),
                "equivalent": optimization.equivalent,
                "improved": optimization.improved,
                "oracle_differential": differential,
            }
        )
    return rows




def run_cumulative_self_improvement(
    data_home: Path,
    model_path: Path,
    *,
    base_url: str = "http://127.0.0.1:8084",
    max_attempts: int = 2,
    max_tokens: int = 512,
    generations: int = 3,
    teacher_control: str = "host",
) -> dict[str, Any]:
    if teacher_control not in {"host", "field", "field-off"}:
        raise SelfImprovementError(
            "teacher_control must be one of host, field, field-off"
        )
    if not 1 <= max_attempts <= 4:
        raise SelfImprovementError("max_attempts must be in [1, 4]")
    if not 1 <= generations <= 4:
        raise SelfImprovementError("generations must be in [1, 4]")
    client = LocalQwenClient(base_url, model_path=model_path)
    teacher_policy_probe: Mapping[str, Any] | None = None
    thinking_capability: Mapping[str, Any] | None = None
    if teacher_control != "host":
        probe_budget = max(1, min(max_tokens, 64))
        teacher_policy_probe = client.probe_request_policy(max_tokens=probe_budget)
        probe_readings = teacher_policy_probe.get("probe")
        if not isinstance(probe_readings, Mapping):
            raise SelfImprovementError("teacher thinking policy probe is incomplete")
        quiet = probe_readings.get("thinking_off")
        loud = probe_readings.get("thinking_on")
        if not isinstance(quiet, Mapping) or not isinstance(loud, Mapping):
            raise SelfImprovementError("teacher thinking policy readings are incomplete")
        thinking_capability = {
            "answer_channel_viable": bool(
                quiet.get("content_chars", 0) > 0
                and quiet.get("reasoning_chars", 0) == 0
                and loud.get("content_chars", 0) > 0
                and teacher_policy_probe.get("flag_effective") is True
            ),
            "flag_effective": teacher_policy_probe.get("flag_effective") is True,
            "probe_max_tokens": probe_budget,
        }
    generation_rows: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    with CassiFieldWorkMemory(
        Path(data_home), profile_overrides={"mode_count": 786_432}
    ) as memory:
        run_epoch = memory.owner.state.generation
        teacher_field = (
            None
            if teacher_control == "host"
            else TeacherFieldController(
                memory,
                run_id=f"cassi-python:{_sha_text(str(Path(model_path).resolve()))[:16]}:{run_epoch}",
                field_off=teacher_control == "field-off",
            )
        )
        initial_experiences = _payloads(
            memory.recall(
                EXPERIENCE_CONTEXT,
                operation_label=f"cumulative-experience:initial:{run_epoch}",
            )
        )
        initial_states = _payloads(
            memory.recall(
                STATE_CONTEXT,
                operation_label=f"cumulative-state:initial:{run_epoch}",
            )
        )
        current_state = _latest_state(initial_states)
        current_source = (
            str(current_state["candidate_source"])
            if current_state is not None
            else BASELINE_SOURCE
        )
        experience_index = len(initial_experiences)
        state_index = len(initial_states)
        for generation in range(generations):
            recall = memory.recall(
                EXPERIENCE_CONTEXT,
                operation_label=(
                    f"cumulative-experience:g{generation}:{run_epoch}:"
                    f"{experience_index}"
                ),
            )
            experiences = _payloads(recall)
            selected_edit = field_select_edit(current_source, experiences)
            selected_task_id = (
                None if selected_edit is None else str(selected_edit["task_id"])
            )
            selected_edit_id = (
                None if selected_edit is None else str(selected_edit["edit_id"])
            )
            candidate_pool = [
                row
                for task_id in _TASKS
                if _eligible(current_source, task_id)
                for row in _candidate_pool_for_task(current_source, task_id)
            ]
            candidate_descriptors = [
                {
                    "candidate_id": str(candidate["edit_id"]),
                    "candidate_origin": "verified_pool",
                    "candidate_sha256": str(candidate["candidate_sha256"]),
                    "candidate_steps": int(candidate["candidate_steps"]),
                    "improved": bool(candidate["improved"]),
                    "status": str(candidate["status"]),
                    "task_id": str(candidate["task_id"]),
                }
                for candidate in candidate_pool
                if selected_task_id is not None
                and candidate.get("task_id") == selected_task_id
            ][:4]
            generation_attempts: list[dict[str, Any]] = []
            accepted_generation: dict[str, Any] | None = None
            previous_source = current_source
            for attempt in range(max_attempts):
                row: dict[str, Any] = {
                    "generation": generation,
                    "attempt": attempt,
                    "field_selected_task_id": selected_task_id,
                    "field_planned_edit_id": selected_edit_id,
                    "field_selected_edit_id": selected_edit_id,
                    "selected_edit_candidate_sha256": (
                        None
                        if selected_edit is None
                        else selected_edit["candidate_sha256"]
                    ),
                    "candidate_pool": candidate_pool,
                    "experience_count": len(experiences),
                    "experience_index": experience_index,
                    "previous_source": previous_source,
                    "previous_source_sha256": _sha_text(previous_source),
                    "teacher_control_mode": teacher_control,
                }
                evidence: Mapping[str, Any] = {}
                attempt_edit_id = selected_edit_id
                teacher_begin: Mapping[str, Any] | None = None
                teacher_action: Mapping[str, Any] | None = None
                try:
                    if selected_task_id is None or selected_edit_id is None:
                        raise SelfImprovementError(
                            "field found no eligible cumulative transformation"
                        )
                    task_pool = [
                        candidate
                        for candidate in candidate_pool
                        if candidate.get("task_id") == selected_task_id
                    ]
                    if teacher_field is not None:
                        teacher_begin = teacher_field.begin(
                            generation=generation,
                            attempt=attempt,
                            previous_source_sha256=_sha_text(previous_source),
                            candidate_descriptors=candidate_descriptors,
                            planned_edit_id=attempt_edit_id,
                            thinking_max_tokens=min(max_tokens, 256),
                            thinking_capability=thinking_capability,
                        )
                        teacher_action = teacher_begin["action"]
                        if teacher_action["task_id"] != selected_task_id:
                            raise SelfImprovementError(
                                "teacher field selected a task outside the eligible pool"
                            )
                        attempt_edit_id = str(teacher_action["edit_id"])
                        row.update(
                            {
                                "field_selected_edit_id": attempt_edit_id,
                                "teacher_field": teacher_begin,
                                "teacher_field_action_id": teacher_action["action_id"],
                                "teacher_field_candidate_id": teacher_action["candidate_id"],
                                "teacher_field_task_id": teacher_action["task_id"],
                                "teacher_field_thinking": teacher_action["thinking"],
                            }
                        )
                    control_frame = (
                        None
                        if teacher_action is None
                        else {
                            "action_id": teacher_action["action_id"],
                            "candidate_id": teacher_action["candidate_id"],
                            "edit_id": teacher_action["edit_id"],
                            "task_id": teacher_action["task_id"],
                            "thinking": teacher_action["thinking"],
                        }
                    )
                    prompt = cumulative_multi_prompt(
                        attempt,
                        previous_source,
                        selected_task_id,
                        len(experiences),
                        attempt_edit_id,
                        task_pool,
                        control_frame=control_frame,
                    )
                    row["prompt_sha256"] = _sha_text(prompt)
                    thinking = (
                        False
                        if teacher_action is None
                        else bool(teacher_action["thinking"]["enabled"])
                    )
                    request_max_tokens = (
                        max_tokens
                        if teacher_action is None
                        else (
                            max_tokens
                            if not thinking
                            else min(
                                max_tokens,
                                int(teacher_action["thinking"]["max_tokens"]),
                            )
                        )
                    )
                    result = client.complete(
                        prompt=prompt,
                        max_tokens=request_max_tokens,
                        thinking=thinking,
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
                            "teacher_field_thinking_effective": bool(
                                evidence["reasoning_content"]
                            ),
                        }
                    )
                    proposals = parse_proposals(evidence["response"])
                    proposal_outcomes, selected_proposal = rank_model_proposals(
                        previous_source,
                        selected_task_id,
                        proposals,
                        candidate_pool,
                        experiences,
                    )
                    row["proposal_outcomes"] = proposal_outcomes
                    if selected_proposal is None:
                        raise SelfImprovementError(
                            "field found no promotable model proposal"
                        )
                    task_id = str(selected_proposal["task_id"])
                    candidate_source = str(selected_proposal["candidate_source"])
                    optimization = evaluate_source_candidate(
                        previous_source, candidate_source, CASES
                    )
                    differential = verify_differential(candidate_source, CASES)
                    row.update(
                        {
                            "task_id": task_id,
                            "field_selected_edit_id": selected_proposal["edit_id"],
                            "selected_task_match": task_id == selected_task_id,
                            "selected_edit_match": (
                                selected_proposal["edit_id"] == attempt_edit_id
                            ),
                            "selected_proposal_id": selected_proposal["proposal_id"],
                            "candidate_origin": selected_proposal["candidate_origin"],
                            "novel_candidate": selected_proposal["novel_candidate"],
                            "candidate_source": candidate_source,
                            "candidate_sha256": _sha_text(candidate_source),
                            "status": (
                                "PASS"
                                if selected_proposal["status"] == "PASS"
                                else "REJECT"
                            ),
                            "original_steps": optimization.original_steps,
                            "candidate_steps": optimization.candidate_steps,
                            "equivalent": optimization.equivalent,
                            "improved": optimization.improved,
                            "cases": list(optimization.cases),
                            "oracle_differential": differential,
                        }
                    )
                    if teacher_field is not None and teacher_begin is not None:
                        row["teacher_field_outcome"] = teacher_field.observe_outcome(
                            teacher_begin,
                            status=str(row["status"]),
                            candidate_origin=str(row["candidate_origin"]),
                            candidate_sha256=str(row["candidate_sha256"]),
                            task_id=task_id,
                            candidate_steps=int(row["candidate_steps"]),
                            original_steps=int(row["original_steps"]),
                            reasoning_chars=int(row["reasoning_chars"]),
                            completion_tokens=int(
                                row.get("usage", {}).get("completion_tokens", 0)
                            ),
                            thinking_requested=thinking,
                            thinking_effective=bool(
                                row["teacher_field_thinking_effective"]
                            ),
                        )
                except Exception as exc:
                    row.update(
                        {
                            "task_id": selected_task_id,
                            "selected_task_match": False,
                            "status": "FAIL",
                            "failure": {"type": type(exc).__name__, "message": str(exc)},
                        }
                    )
                    if (
                        teacher_field is not None
                        and teacher_begin is not None
                        and "teacher_field_outcome" not in row
                    ):
                        action = teacher_begin.get("action", {})
                        descriptor = next(
                            (
                                candidate
                                for candidate in candidate_descriptors
                                if candidate.get("candidate_id") == action.get("candidate_id")
                            ),
                            None,
                        )
                        if isinstance(descriptor, Mapping):
                            try:
                                row["teacher_field_outcome"] = teacher_field.observe_outcome(
                                    teacher_begin,
                                    status="FAIL",
                                    candidate_origin=str(
                                        descriptor.get("candidate_origin", "verified_pool")
                                    ),
                                    candidate_sha256=str(descriptor["candidate_sha256"]),
                                    task_id=str(descriptor["task_id"]),
                                    candidate_steps=int(descriptor["candidate_steps"]),
                                    original_steps=int(descriptor["candidate_steps"]),
                                    reasoning_chars=len(
                                        str(evidence.get("reasoning_content", ""))
                                    ),
                                    completion_tokens=int(
                                        evidence.get("usage", {}).get("completion_tokens", 0)
                                    ),
                                    thinking_requested=bool(
                                        action.get("thinking", {}).get("enabled", False)
                                    ),
                                    thinking_effective=bool(
                                        evidence.get("reasoning_content")
                                    ),
                                )
                            except Exception as outcome_exc:
                                row["teacher_field_outcome_failure"] = {
                                    "type": type(outcome_exc).__name__,
                                    "message": str(outcome_exc),
                                }
                experience_receipt = _learn_experience(
                    memory,
                    index=experience_index,
                    generation=generation,
                    attempt=attempt,
                    task_id=str(row["task_id"]),
                    status=str(row["status"]),
                    row=row,
                )
                row["experience_source_revision_id"] = experience_receipt.get(
                    "source_revision_id"
                )
                experience_index += 1
                if row["status"] == "PASS":
                    state_receipt = _learn_state(
                        memory,
                        index=state_index,
                        generation=generation,
                        task_id=str(row["task_id"]),
                        previous_source=previous_source,
                        candidate_source=str(row["candidate_source"]),
                        optimization=optimization,
                        differential=differential,
                    )
                    row["state_index"] = state_index
                    row["state_source_revision_id"] = state_receipt.get(
                        "source_revision_id"
                    )
                    accepted_generation = {
                        "generation": generation,
                        "task_id": str(row["task_id"]),
                        "edit_id": row["field_selected_edit_id"],
                        "selected_proposal_id": row["selected_proposal_id"],
                        "candidate_origin": row["candidate_origin"],
                        "novel_candidate": row["novel_candidate"],
                        "previous_source_sha256": row["previous_source_sha256"],
                        "candidate_source": str(row["candidate_source"]),
                        "candidate_sha256": row["candidate_sha256"],
                        "state_index": state_index,
                        "state_source_revision_id": state_receipt.get(
                            "source_revision_id"
                        ),
                    }
                    current_source = str(row["candidate_source"])
                    state_index += 1
                    accepted.append(accepted_generation)
                    generation_attempts.append(row)
                    attempts.append(row)
                    break
                generation_attempts.append(row)
                attempts.append(row)
            generation_rows.append(
                {
                    "generation": generation,
                    "field_selected_task_id": (
                        selected_task_id
                        if accepted_generation is None
                        else accepted_generation["task_id"]
                    ),
                    "field_selected_edit_id": (
                        selected_edit_id
                        if accepted_generation is None
                        else accepted_generation["edit_id"]
                    ),
                    "field_planned_task_id": selected_task_id,
                    "field_planned_edit_id": selected_edit_id,
                    "candidate_pool": candidate_pool,
                    "experience_count_before": len(experiences),
                    "attempts": generation_attempts,
                    "accepted": accepted_generation,
                    "status": "PASS" if accepted_generation is not None else "FAIL",
                }
            )
        field = memory.regional_field_receipt()
    reopened_rows: list[dict[str, Any]] = []
    if accepted:
        with CassiFieldWorkMemory(
            Path(data_home), profile_overrides={"mode_count": 786_432}
        ) as reopened:
            for item in accepted:
                source = reopened._active_source_for_id(
                    f"{SOURCE_PREFIX}state:{int(item['state_index']):06d}"
                )
                payload = (
                    None
                    if source is None
                    else reopened._document_for_revision(source.revision_id)
                )
                payload = payload.get("payload") if isinstance(payload, Mapping) else None
                reopened_rows.append(
                    {
                        "generation": item["generation"],
                        "task_id": item["task_id"],
                        "candidate_sha256": None
                        if not isinstance(payload, Mapping)
                        else payload.get("candidate_sha256"),
                        "status": (
                            "PASS"
                            if isinstance(payload, Mapping)
                            and payload.get("candidate_sha256") == item["candidate_sha256"]
                            else "FAIL"
                        ),
                    }
                )
    novel_proposals_observed = sum(
        1
        for attempt in attempts
        for outcome in attempt.get("proposal_outcomes", ())
        if isinstance(outcome, Mapping) and outcome.get("novel_candidate") is True
    )
    novel_proposals_promoted = sum(
        1 for item in accepted if item.get("novel_candidate") is True
    )
    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "target": "cassi-python-program",
        "proposal_mode": "field-selected-cumulative-code-evolution",
        "teacher_control_mode": teacher_control,
        "teacher_thinking_policy_probe": teacher_policy_probe,
        "teacher_thinking_capability": thinking_capability,
        "novel_proposals_allowed": True,
        "novel_proposal_source_bound": 8_192,
        "novel_proposals_observed": novel_proposals_observed,
        "novel_proposals_promoted": novel_proposals_promoted,
        "model_path": str(Path(model_path).resolve()),
        "model_sha256": client.model_sha256,
        "generations_requested": generations,
        "baseline_source": BASELINE_SOURCE,
        "baseline_sha256": _sha_text(BASELINE_SOURCE),
        "case_ids": [case.case_id for case in CASES],
        "tasks": [_task_receipt(task) for task in TASKS],
        "tasks_sha256": digest_value([_task_receipt(task) for task in TASKS]),
        "generations": generation_rows,
        "attempts": attempts,
        "accepted": accepted,
        "final_source": current_source,
        "final_source_sha256": _sha_text(current_source),
        "mutation_controls": mutation_control_rows(),
        "reopened": {
            "status": "PASS"
            if reopened_rows and all(row["status"] == "PASS" for row in reopened_rows)
            else "FAIL",
            "rows": reopened_rows,
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


def verify_cumulative_receipt(
    receipt: Mapping[str, Any], data_home: Path | None = None
) -> dict[str, Any]:
    if not content_digest_matches(receipt):
        raise SelfImprovementError("cumulative receipt digest mismatch")
    teacher_control_mode = receipt.get("teacher_control_mode")
    if teacher_control_mode not in {"host", "field", "field-off"}:
        raise SelfImprovementError("cumulative teacher control mode is invalid")
    teacher_probe = receipt.get("teacher_thinking_policy_probe")
    teacher_capability = receipt.get("teacher_thinking_capability")
    if teacher_control_mode == "host":
        if teacher_probe is not None or teacher_capability is not None:
            raise SelfImprovementError("host receipt unexpectedly contains teacher calibration")
    else:
        if not isinstance(teacher_probe, Mapping) or not isinstance(
            teacher_capability, Mapping
        ):
            raise SelfImprovementError("teacher thinking calibration is missing")
        probe = teacher_probe.get("probe")
        quiet = probe.get("thinking_off") if isinstance(probe, Mapping) else None
        loud = probe.get("thinking_on") if isinstance(probe, Mapping) else None
        if not isinstance(quiet, Mapping) or not isinstance(loud, Mapping):
            raise SelfImprovementError("teacher thinking calibration readings are missing")
        if set(teacher_capability) != {
            "answer_channel_viable",
            "flag_effective",
            "probe_max_tokens",
        }:
            raise SelfImprovementError("teacher thinking capability schema changed")
        derived_capability = {
            "answer_channel_viable": bool(
                quiet.get("content_chars", 0) > 0
                and quiet.get("reasoning_chars", 0) == 0
                and loud.get("content_chars", 0) > 0
                and teacher_probe.get("flag_effective") is True
            ),
            "flag_effective": teacher_probe.get("flag_effective") is True,
            "probe_max_tokens": teacher_capability.get("probe_max_tokens"),
        }
        if dict(teacher_capability) != derived_capability:
            raise SelfImprovementError("teacher thinking capability was not derived from probe")
    generations = receipt.get("generations")
    accepted = receipt.get("accepted")
    if not isinstance(generations, list) or not isinstance(accepted, list):
        raise SelfImprovementError("cumulative generations are missing")
    if len(generations) != len(accepted) or not generations:
        raise SelfImprovementError("not every cumulative generation promoted a state")
    if receipt.get("novel_proposals_allowed") is not True:
        raise SelfImprovementError("cumulative receipt does not declare novel proposals")
    if receipt.get("novel_proposal_source_bound") != 8_192:
        raise SelfImprovementError("cumulative novel proposal bound changed")
    receipt_attempts = receipt.get("attempts")
    if not isinstance(receipt_attempts, list):
        raise SelfImprovementError("cumulative attempts are missing")
    observed_novel = sum(
        1
        for attempt in receipt_attempts
        if isinstance(attempt, Mapping)
        for outcome in attempt.get("proposal_outcomes", ())
        if isinstance(outcome, Mapping) and outcome.get("novel_candidate") is True
    )
    promoted_novel = sum(
        1 for item in accepted if item.get("novel_candidate") is True
    )
    if (
        receipt.get("novel_proposals_observed") != observed_novel
        or receipt.get("novel_proposals_promoted") != promoted_novel
        or promoted_novel > observed_novel
    ):
        raise SelfImprovementError("cumulative novel proposal counts are inconsistent")
    current_source = BASELINE_SOURCE
    for generation in generations:
        selected = generation.get("field_selected_task_id")
        selected_edit_id = generation.get("field_selected_edit_id")
        planned_task_id = generation.get("field_planned_task_id", selected)
        planned_edit_id = generation.get("field_planned_edit_id")
        promoted = generation.get("accepted")
        pool = generation.get("candidate_pool")
        if (
            not isinstance(selected, str)
            or not isinstance(selected_edit_id, str)
            or not isinstance(planned_task_id, str)
            or not isinstance(planned_edit_id, str)
            or not isinstance(promoted, Mapping)
            or not isinstance(pool, list)
        ):
            raise SelfImprovementError("cumulative selection or promotion is missing")
        if (
            promoted.get("task_id") != selected
            or promoted.get("edit_id") != selected_edit_id
            or promoted.get("candidate_origin")
            not in {"verified_pool", "model_novel"}
        ):
            raise SelfImprovementError("cumulative field selection was not honored")
        pool_row = next(
            (row for row in pool if row.get("edit_id") == planned_edit_id), None
        )
        if (
            not isinstance(pool_row, Mapping)
            or pool_row.get("status") != "PASS"
            or pool_row.get("task_invariant") is not True
        ):
            raise SelfImprovementError("planned cumulative edit lacks its task-local invariant")
        if planned_task_id != selected or not _eligible(current_source, selected):
            raise SelfImprovementError("cumulative task was not eligible for current source")
        generation_attempts = generation.get("attempts")
        accepted_attempt = (
            next(
                (attempt for attempt in generation_attempts if attempt.get("status") == "PASS"),
                None,
            )
            if isinstance(generation_attempts, list)
            else None
        )
        proposal_outcomes = (
            accepted_attempt.get("proposal_outcomes")
            if isinstance(accepted_attempt, Mapping)
            else None
        )
        selected_outcomes = [
            outcome
            for outcome in proposal_outcomes or ()
            if isinstance(outcome, Mapping) and outcome.get("field_rank_selected") is True
        ]
        if (
            not isinstance(accepted_attempt, Mapping)
            or not isinstance(proposal_outcomes, list)
            or len(proposal_outcomes) < 1
            or len(selected_outcomes) != 1
        ):
            raise SelfImprovementError("cumulative proposal ranking was not persisted")
        selected_outcome = selected_outcomes[0]
        if (
            selected_outcome.get("edit_id") != selected_edit_id
            or selected_outcome.get("candidate_sha256") != promoted.get("candidate_sha256")
            or selected_outcome.get("candidate_origin")
            != promoted.get("candidate_origin")
            or selected_outcome.get("novel_candidate")
            != promoted.get("novel_candidate")
            or selected_outcome.get("task_invariant") is not True
        ):
            raise SelfImprovementError("selected proposal task-local provenance was not persisted")
        if teacher_control_mode != "host":
            teacher_receipt = accepted_attempt.get("teacher_field")
            action = (
                teacher_receipt.get("action")
                if isinstance(teacher_receipt, Mapping)
                else None
            )
            if (
                not isinstance(teacher_receipt, Mapping)
                or teacher_receipt.get("mode") != teacher_control_mode
                or teacher_receipt.get("thinking_capability") != teacher_capability
                or not isinstance(action, Mapping)
                or accepted_attempt.get("teacher_field_action_id") != action.get("action_id")
                or accepted_attempt.get("teacher_field_task_id") != selected
                or accepted_attempt.get("teacher_field_thinking") != action.get("thinking")
            ):
                raise SelfImprovementError("teacher field action was not consumed by the attempt")
            if teacher_control_mode == "field":
                outcome = accepted_attempt.get("teacher_field_outcome")
                if (
                    not isinstance(outcome, Mapping)
                    or outcome.get("field_state_in_sha256")
                    != teacher_receipt.get("field_state_out_sha256")
                    or outcome.get("field_state_out_sha256") is None
                    or outcome.get("status") != "observed"
                ):
                    raise SelfImprovementError("teacher field outcome chain is incomplete")
            elif teacher_receipt.get("field_state_out_sha256") is not None:
                raise SelfImprovementError("field-off comparator mutated field state")
        candidate = promoted.get("candidate_source")
        if not isinstance(candidate, str):
            raise SelfImprovementError("cumulative candidate source is invalid")
        optimization = evaluate_source_candidate(current_source, candidate, CASES)
        if optimization.status != "PASS":
            raise SelfImprovementError("cumulative candidate does not replay")
        if not _task_local_invariant(current_source, candidate, selected):
            raise SelfImprovementError("cumulative candidate violates its task-local invariant")
        if not verify_differential(candidate, CASES)["passed"]:
            raise SelfImprovementError("cumulative candidate failed oracle differential")
        current_source = candidate
    if receipt.get("final_source") != current_source:
        raise SelfImprovementError("cumulative final source is not the promoted chain")
    reopened = receipt.get("reopened", {})
    if not isinstance(reopened, Mapping) or reopened.get("status") != "PASS":
        raise SelfImprovementError("cumulative state did not survive reopen")
    if receipt.get("field", {}).get("all_finite") is not True:
        raise SelfImprovementError("cumulative field is not finite")
    controls = receipt.get("mutation_controls")
    if (
        not isinstance(controls, list)
        or len(controls) != 3
        or any(row.get("status") != "REJECT" for row in controls)
    ):
        raise SelfImprovementError("mutation controls did not reject regressions")
    if data_home is not None:
        with CassiFieldWorkMemory(
            Path(data_home), profile_overrides={"mode_count": 786_432}
        ) as memory:
            epoch = memory.owner.state.generation
            experiences = _payloads(
                memory.recall(
                    EXPERIENCE_CONTEXT,
                    operation_label=f"cumulative-independent-experience:{epoch}",
                )
            )
            states = _payloads(
                memory.recall(
                    STATE_CONTEXT,
                    operation_label=f"cumulative-independent-state:{epoch}",
                )
            )
            if len(experiences) < len(receipt.get("attempts", ())):
                raise SelfImprovementError("cumulative experience history is incomplete")
            promoted_experiences = [
                payload
                for payload in experiences
                if payload.get("status") == "PASS"
            ]
            if (
                len(promoted_experiences) < len(generations)
                or any(
                    not isinstance(payload.get("proposal_outcomes"), list)
                    or len(payload["proposal_outcomes"]) < 1
                    for payload in promoted_experiences[-len(generations) :]
                )
            ):
                raise SelfImprovementError(
                    "proposal-level experience history is incomplete"
                )
            latest = _latest_state(states)
            if latest is None or latest.get("candidate_sha256") != receipt.get(
                "final_source_sha256"
            ):
                raise SelfImprovementError("persisted cumulative final state mismatch")
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
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument(
        "--teacher-control",
        choices=("host", "field", "field-off"),
        default="host",
        help="select host-only, field-owned, or field-off teacher control",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_cumulative_self_improvement(
        args.data_home,
        args.model,
        base_url=args.base_url,
        max_attempts=args.max_attempts,
        max_tokens=args.max_tokens,
        generations=args.generations,
        teacher_control=args.teacher_control,
    )
    _write_receipt(args.output, receipt)
    verify_cumulative_receipt(receipt, args.data_home)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
