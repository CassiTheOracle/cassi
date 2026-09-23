#!/usr/bin/env python3
"""Independently verify a continuing-apprenticeship campaign receipt.

This verifier deliberately does not import the campaign runner.  It rebuilds
its curriculum, candidate randomization, SQL semantics, model-answer parsing,
learning chronology, checkpoint metrics, and state-chain obligations.  It then
hard-links the persisted final field into a disposable E-drive snapshot and
runs a third, previously unused set of role bindings after a process reopen.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import random
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
_CASSIFI = _ROOT / "CassiFI"
_CASSIQWEN = _ROOT / "CassiQwen"
for _path in (_CASSIFI, _CASSIQWEN):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from cassi_field_qwen_workbench import CassiFieldWorkMemory, cassifi_source_identity  # noqa: E402
from cassi_sqlite_apprenticeship import (  # noqa: E402
    canonical_json,
    canonical_table,
    execute_sqlite_oracle,
    table_from_rows,
)

SOURCE_SCHEMA = "cassi.continuing-apprenticeship.v1"
VERIFY_SCHEMA = "cassi.continuing-apprenticeship-verification.v1"
MODEL_SHA256 = "3895b6eaa91e705c06ad1938d16c22e86f073c6a67df86260a1da79be3d1f887"
MECHANISM_ID = "mechanism:continuing-apprenticeship:sequence-composer"
CAMPAIGN_PROFILE_OVERRIDES: Mapping[str, int] = {"mode_count": 262_144}
DEFAULT_RECEIPT = Path(
    "E:/CassiLearning/continuing-apprenticeship-27b-iq1s-20260917-r2/continuing-apprenticeship.json"
)

_EXPECTED_TEMPLATES: tuple[dict[str, str], ...] = (
    {"id": "fol-01", "family": "fill-order-limit", "text": "For {subject}, replace missing values with {fill}, sort {direction}, and keep {limit}."},
    {"id": "fol-02", "family": "fill-order-limit", "text": "Process {subject}: use {fill} for blanks, arrange {direction}, return {limit}."},
    {"id": "fol-03", "family": "fill-order-limit", "text": "In {subject}, fill absent entries as {fill}; order {direction}; take {limit}."},
    {"id": "fol-04", "family": "fill-order-limit", "text": "Transform {subject} by substituting {fill} for missing entries, listing {direction}, capped at {limit}."},
    {"id": "fol-05", "family": "fill-order-limit", "text": "From {subject}, set every blank to {fill}, rank {direction}, retain {limit}."},
    {"id": "fol-06", "family": "fill-order-limit", "text": "{subject} needs blanks changed to {fill}, values placed {direction}, with {limit} results."},
    {"id": "fol-07", "family": "fill-order-limit", "text": "Prepare {subject}: missing becomes {fill}; sequence is {direction}; output count is {limit}."},
    {"id": "fol-08", "family": "fill-order-limit", "text": "For the {subject} series, impute {fill}, sort {direction}, select {limit}."},
    {"id": "fdo-01", "family": "filter-distinct-order", "text": "For {subject}, keep values {relation} {threshold}, remove duplicates, sort {direction}."},
    {"id": "fdo-02", "family": "filter-distinct-order", "text": "Process {subject}: retain entries {relation} {threshold}; deduplicate; arrange {direction}."},
    {"id": "fdo-03", "family": "filter-distinct-order", "text": "In {subject}, select numbers {relation} {threshold}, keep unique values, order {direction}."},
    {"id": "fdo-04", "family": "filter-distinct-order", "text": "Transform {subject} by filtering {relation} {threshold}, removing repeats, listing {direction}."},
    {"id": "fdo-05", "family": "filter-distinct-order", "text": "From {subject}, accept only values {relation} {threshold}, collapse duplicates, rank {direction}."},
    {"id": "fdo-06", "family": "filter-distinct-order", "text": "{subject} needs entries {relation} {threshold}, one of each value, placed {direction}."},
    {"id": "fdo-07", "family": "filter-distinct-order", "text": "Prepare {subject}: values must be {relation} {threshold}; repeats vanish; sequence is {direction}."},
    {"id": "fdo-08", "family": "filter-distinct-order", "text": "For the {subject} series, retain {relation} {threshold}, uniquify, sort {direction}."},
    {"id": "full-01", "family": "full-pipeline", "text": "Run the complete chain for {subject}: impute blanks as {fill}; gate {relation} {threshold}; collapse repeats; rank {direction}; truncate to {limit}."},
    {"id": "full-02", "family": "full-pipeline", "text": "Apply every stage to {subject}: encode absent items as {fill}; screen {relation} {threshold}; merge repeats; traverse {direction}; stop after {limit}."},
    {"id": "full-03", "family": "full-pipeline", "text": "Build the full sequence from {subject}: seed gaps with {fill}; admit {relation} {threshold}; make values singular; walk {direction}; emit {limit}."},
    {"id": "full-04", "family": "full-pipeline", "text": "Complete-transform {subject}: patch voids using {fill}; test {relation} {threshold}; fuse repeats; traverse {direction}; cut at {limit}."},
    {"id": "full-05", "family": "full-pipeline", "text": "Use the five-stage chain on {subject}: map gaps to {fill}; pass {relation} {threshold}; coalesce repeats; walk {direction}; yield {limit}."},
    {"id": "full-06", "family": "full-pipeline", "text": "Resolve {subject} end to end: encode voids as {fill}; gate {relation} {threshold}; reduce repetition; traverse {direction}; stop at {limit}."},
    {"id": "full-07", "family": "full-pipeline", "text": "Pipeline all operations for {subject}: patch absence with {fill}; screen {relation} {threshold}; unify repeated values; walk {direction}; emit {limit}."},
    {"id": "full-08", "family": "full-pipeline", "text": "Perform the complete sequence on {subject}: map missing entries to {fill}; admit {relation} {threshold}; merge equal values; traverse {direction}; return {limit}."},
)
_TRAIN_SUBJECTS = (
    "sensor readings",
    "lab counts",
    "queue scores",
    "ledger values",
    "survey totals",
    "signal levels",
)
_EVAL_SUBJECTS = (
    "stellar measurements",
    "warehouse tallies",
    "river gauges",
    "archive indices",
)
_VERIFY_SUBJECTS = (
    "seismic samples",
    "orchard yields",
    "tidal observations",
    "crystal counts",
)


class VerificationError(RuntimeError):
    pass


class Audit:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def require(self, name: str, condition: bool, evidence: Any = None) -> None:
        row: dict[str, Any] = {"name": name, "passed": bool(condition)}
        if evidence is not None:
            row["evidence"] = evidence
        self.checks.append(row)
        if not condition:
            raise VerificationError(name)


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(8 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()

def _current_implementation_identity() -> dict[str, Any]:
    paths = {
        "runner": _CASSIQWEN / "run_continuing_apprenticeship.py",
        "field_workbench": _CASSIQWEN / "cassi_field_qwen_workbench.py",
        "model_instrument": _CASSIQWEN / "cassi_model_instrument.py",
        "sqlite_oracle": _CASSIQWEN / "cassi_sqlite_apprenticeship.py",
        "apprenticeship_helpers": _CASSIQWEN / "run_sqlite_apprenticeship.py",
    }
    files = {
        name: {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": _file_sha(path),
        }
        for name, path in paths.items()
    }
    closure = dict(cassifi_source_identity())
    return {
        "files": files,
        "files_sha256": _sha(files),
        "cassifi_closure": closure,
        "aggregate_sha256": _sha(
            {
                "files_sha256": _sha(files),
                "cassifi_aggregate_sha256": closure["aggregate_sha256"],
            }
        ),
    }

def _campaign_memory(data_home: Path) -> CassiFieldWorkMemory:
    return CassiFieldWorkMemory(
        data_home,
        profile_overrides=CAMPAIGN_PROFILE_OVERRIDES,
    )

def _timing_summary_ns(values: Sequence[int]) -> dict[str, int]:
    if not values:
        return {
            "count": 0,
            "total_ns": 0,
            "mean_ns": 0,
            "median_ns": 0,
            "p95_ns": 0,
            "min_ns": 0,
            "max_ns": 0,
            "first_ns": 0,
            "last_ns": 0,
        }
    ordered = sorted(int(value) for value in values)
    count = len(ordered)
    return {
        "count": count,
        "total_ns": sum(ordered),
        "mean_ns": sum(ordered) // count,
        "median_ns": ordered[(count - 1) // 2],
        "p95_ns": ordered[min(count - 1, (95 * count + 99) // 100 - 1)],
        "min_ns": ordered[0],
        "max_ns": ordered[-1],
        "first_ns": int(values[0]),
        "last_ns": int(values[-1]),
    }


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    staging = path.with_suffix(path.suffix + ".staging")
    staging.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    staging.replace(path)


def _plan(
    *,
    fill: int | None,
    filter_op: str | None,
    threshold: int | None,
    distinct: bool,
    order: str | None,
    limit: int | None,
) -> dict[str, Any]:
    return {
        "fill": fill,
        "filter_op": filter_op,
        "threshold": threshold,
        "distinct": bool(distinct),
        "order": order,
        "limit": limit,
    }


def _plan_code(plan: Mapping[str, Any]) -> str:
    filter_code = "_" if plan["filter_op"] is None else f"{plan['filter_op']}{int(plan['threshold'])}"
    return ",".join(
        (
            "f_" if plan["fill"] is None else f"f{int(plan['fill'])}",
            filter_code,
            "u1" if plan["distinct"] else "u0",
            "o_" if plan["order"] is None else f"o{plan['order'][0]}",
            "l_" if plan["limit"] is None else f"l{int(plan['limit'])}",
        )
    )


def _task_plan(family: str, index: int, *, split: str) -> dict[str, Any]:
    order = "desc" if index % 2 == 0 else "asc"
    if family == "fill-order-limit":
        magnitude = 10 if split == "verification" else (9 if split == "evaluation" else 8)
        fill = magnitude if order == "desc" else -magnitude
        return _plan(
            fill=fill,
            filter_op=None,
            threshold=None,
            distinct=False,
            order=order,
            limit=(1 + index % 4) if split == "verification" else (2 + index % 3),
        )
    filter_op = "gt" if index % 2 == 0 else "lt"
    if split == "verification":
        values = (5, -5, 6, -6)
    elif split == "evaluation":
        values = (3, -3, 4, -4)
    else:
        values = (-1, 0, 1, 2)
    threshold = values[index % len(values)]
    if family == "filter-distinct-order":
        return _plan(
            fill=None,
            filter_op=filter_op,
            threshold=threshold,
            distinct=True,
            order=order,
            limit=None,
        )
    distance = 7 if split == "verification" else 6
    fill = threshold + distance if filter_op == "gt" else threshold - distance
    return _plan(
        fill=fill,
        filter_op=filter_op,
        threshold=threshold,
        distinct=True,
        order=order,
        limit=3 if split == "verification" else 4,
    )


def _task_rows(plan: Mapping[str, Any]) -> list[int | None]:
    if plan["filter_op"] is None:
        return [None, None, -6, -2, 0, 3, 3, 7]
    threshold = int(plan["threshold"])
    return [
        None,
        threshold - 3,
        threshold - 3,
        threshold - 1,
        threshold,
        threshold + 1,
        threshold + 3,
        threshold + 3,
    ]


def _candidate_plans(truth: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(truth)]
    if truth["filter_op"] is None:
        rows.extend(
            (
                {**truth, "fill": int(truth["fill"]) + (1 if truth["fill"] >= 0 else -1)},
                {**truth, "order": "asc" if truth["order"] == "desc" else "desc"},
                {**truth, "limit": 1 if int(truth["limit"]) != 1 else 5},
            )
        )
    elif truth["fill"] is None:
        rows.extend(
            (
                {**truth, "filter_op": "lt" if truth["filter_op"] == "gt" else "gt"},
                {**truth, "threshold": int(truth["threshold"]) + 1},
                {**truth, "distinct": False},
            )
        )
    else:
        rows.extend(
            (
                {**truth, "fill": int(truth["fill"]) + (1 if truth["fill"] >= 0 else -1)},
                {**truth, "filter_op": "lt" if truth["filter_op"] == "gt" else "gt"},
                {**truth, "order": "asc" if truth["order"] == "desc" else "desc"},
            )
        )
    return [_plan(**row) for row in rows]


def _render_task(
    template: Mapping[str, str],
    index: int,
    *,
    split: str,
    seed: int,
) -> dict[str, Any]:
    truth = _task_plan(template["family"], index, split=split)
    if split == "training":
        subject_pool = _TRAIN_SUBJECTS
    elif split == "evaluation":
        subject_pool = _EVAL_SUBJECTS
    else:
        subject_pool = _VERIFY_SUBJECTS
    subject = subject_pool[index % len(subject_pool)]
    bindings: dict[str, str] = {
        "subject": subject,
        "order_direction": "ascending" if truth["order"] == "asc" else "descending",
    }
    format_values: dict[str, Any] = {
        "subject": subject,
        "direction": bindings["order_direction"],
    }
    if truth["fill"] is not None:
        bindings["fill_value"] = str(truth["fill"])
        bindings["row_limit"] = str(truth["limit"])
        format_values.update(fill=truth["fill"], limit=truth["limit"])
    if truth["filter_op"] is not None:
        relation = "above" if truth["filter_op"] == "gt" else "below"
        bindings["filter_relation"] = relation
        bindings["threshold"] = str(truth["threshold"])
        format_values.update(relation=relation, threshold=truth["threshold"])
    instruction = template["text"].format(**format_values)
    candidates = _candidate_plans(truth)
    rng = random.Random(seed * 1_000_003 + index * 97 + (31 if split == "evaluation" else 0))
    rng.shuffle(candidates)
    labelled = [
        {"letter": chr(ord("A") + offset), "plan": plan, "code": _plan_code(plan)}
        for offset, plan in enumerate(candidates)
    ]
    truth_letter = next(row["letter"] for row in labelled if row["plan"] == truth)
    if split == "training":
        split_name = "consequence-grounded-training"
    elif split == "evaluation":
        split_name = "teacher-disconnected-evaluation"
    else:
        split_name = "independent-restart-verification"
    return {
        "case_id": f"{split_name}:{template['id']}:{index:03d}",
        "split": split_name,
        "template_id": template["id"],
        "family": template["family"],
        "instruction": instruction,
        "instruction_sha256": _sha_text(instruction),
        "bindings": bindings,
        "input_rows": _task_rows(truth),
        "input_table": table_from_rows(_task_rows(truth)),
        "candidates": labelled,
        "truth_plan": truth,
        "truth_plan_sha256": _sha(truth),
        "truth_letter": truth_letter,
        "sql": _plan_sql(truth),
    }


def _plan_sql(plan: Mapping[str, Any]) -> str:
    query = "SELECT x FROM readings"
    alias = 0

    def nest(select_expression: str, suffix: str = "") -> None:
        nonlocal query, alias
        alias += 1
        query = f"SELECT {select_expression} FROM ({query}) AS s{alias}{suffix}"

    if plan["fill"] is not None:
        nest(f"COALESCE(x, {int(plan['fill'])}) AS x")
    if plan["filter_op"] is not None:
        operator = ">" if plan["filter_op"] == "gt" else "<"
        nest("x", f" WHERE x {operator} {int(plan['threshold'])}")
    if plan["distinct"]:
        nest("DISTINCT x")
    if plan["order"] is not None:
        direction = "ASC" if plan["order"] == "asc" else "DESC"
        nulls = "FIRST" if direction == "ASC" else "LAST"
        nest("x", f" ORDER BY x {direction} NULLS {nulls}")
    if plan["limit"] is not None:
        nest("x", f" LIMIT {int(plan['limit'])}")
    return query


def _model_prompt(task: Mapping[str, Any]) -> str:
    candidates = "\n".join(f"{row['letter']} {row['code']}" for row in task["candidates"])
    return (
        f"Instruction: {task['instruction']}\n"
        f"Candidates:\n{candidates}\n"
        "The correct candidate letter is"
    )


def _model_choice(output: str) -> str | None:
    match = re.match(r"\s*([A-D])(?:\b|[.)])", output)
    return None if match is None else match.group(1)


def _task_core(task: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "case_id",
        "split",
        "template_id",
        "family",
        "instruction",
        "instruction_sha256",
        "bindings",
        "input_rows",
        "input_table",
        "candidates",
        "truth_plan",
        "truth_plan_sha256",
        "truth_letter",
        "sql",
    )
    return {key: task[key] for key in keys}


def _verify_oracle(task: Mapping[str, Any], oracle: Mapping[str, Any], label: str) -> None:
    truth = execute_sqlite_oracle(
        canonical_table(task["input_table"]),
        str(task["sql"]),
        operation_id=f"independent-verifier:{label}:truth",
        max_rows=8,
        timeout_ms=1000,
    )
    stored_truth = oracle["truth"]
    if truth.get("status") != "supported":
        raise VerificationError(f"{label}: independent truth SQL failed")
    for key in ("canonical_output", "output_digest", "input_digest", "sqlite_source_id"):
        if truth.get(key) != stored_truth.get(key):
            raise VerificationError(f"{label}: stored truth {key} differs from independent SQLite")
    candidate_rows = oracle["candidates"]
    if len(candidate_rows) != 4:
        raise VerificationError(f"{label}: candidate receipt count is not four")
    matching: list[str] = []
    digests: set[str] = set()
    for candidate in task["candidates"]:
        stored = next(
            (row for row in candidate_rows if row.get("letter") == candidate["letter"]),
            None,
        )
        if stored is None:
            raise VerificationError(f"{label}: candidate receipt is missing {candidate['letter']}")
        sql = _plan_sql(candidate["plan"])
        if stored.get("sql") != sql or stored.get("plan_sha256") != _sha(candidate["plan"]):
            raise VerificationError(f"{label}: candidate plan or SQL drifted")
        result = execute_sqlite_oracle(
            canonical_table(task["input_table"]),
            sql,
            operation_id=f"independent-verifier:{label}:{candidate['letter']}",
            max_rows=8,
            timeout_ms=1000,
        )
        if result.get("canonical_output") != stored.get("output") or result.get("output_digest") != stored.get("output_digest"):
            raise VerificationError(f"{label}: candidate output differs from independent SQLite")
        matches = result.get("canonical_output") == truth.get("canonical_output")
        if bool(stored.get("matches_truth")) != matches:
            raise VerificationError(f"{label}: candidate truth comparison drifted")
        if matches:
            matching.append(str(candidate["letter"]))
        digests.add(str(result["output_digest"]))
    if matching != [task["truth_letter"]] or list(oracle.get("supported_letters", [])) != matching:
        raise VerificationError(f"{label}: oracle does not uniquely select the frozen truth letter")
    if len(digests) != 4:
        raise VerificationError(f"{label}: candidate outputs are not pairwise distinct")


def _verify_model(
    task: Mapping[str, Any],
    model: Mapping[str, Any],
    *,
    identity_sha256: str,
    state_seed_sha256: str,
    label: str,
) -> bool:
    prompt = _model_prompt(task)
    if model.get("prompt") != prompt or model.get("prompt_sha256") != _sha_text(prompt):
        raise VerificationError(f"{label}: model prompt drifted")
    output = str(model.get("output", ""))
    if model.get("output_sha256") != _sha_text(output):
        raise VerificationError(f"{label}: model output digest drifted")
    choice = _model_choice(output)
    if model.get("choice") != choice:
        raise VerificationError(f"{label}: parsed model choice drifted")
    selected = next((row for row in task["candidates"] if row["letter"] == choice), None)
    expected_plan = None if selected is None else selected["plan"]
    if model.get("selected_plan") != expected_plan:
        raise VerificationError(f"{label}: selected model plan drifted")
    if model.get("identity_sha256") != identity_sha256:
        raise VerificationError(f"{label}: native model identity drifted")
    predecessor = model.get("state_predecessor", {})
    if predecessor.get("sha256") != state_seed_sha256:
        raise VerificationError(f"{label}: native trial did not start from the frozen zero state")
    successor = model.get("state_successor", {})
    successor_path = Path(str(successor.get("path", "")))
    if not successor_path.is_file():
        raise VerificationError(f"{label}: persisted native state successor is absent")
    if successor_path.drive.upper() != "E:":
        raise VerificationError(f"{label}: native state successor is not stored on E drive")
    if successor_path.stat().st_size != int(successor.get("bytes", -1)):
        raise VerificationError(f"{label}: native state successor byte count drifted")
    if _file_sha(successor_path) != successor.get("sha256"):
        raise VerificationError(f"{label}: native state successor digest drifted")
    return choice == task["truth_letter"]


def _prediction_matches(attempt: Mapping[str, Any], truth: Mapping[str, Any]) -> bool:
    prediction = attempt.get("prediction")
    return isinstance(prediction, Mapping) and canonical_table(prediction) == canonical_table(truth)

def _verify_attempt_timing(attempt: Mapping[str, Any], *, label: str) -> None:
    timing = attempt.get("timing")
    if not isinstance(timing, Mapping) or set(timing) != {
        "interpret_ns",
        "execution_ns",
        "total_ns",
    }:
        raise VerificationError(f"{label}: field timing receipt is incomplete")
    values = [timing["interpret_ns"], timing["execution_ns"], timing["total_ns"]]
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise VerificationError(f"{label}: field timing receipt is invalid")
    if int(timing["interpret_ns"]) <= 0 or int(timing["total_ns"]) < (
        int(timing["interpret_ns"]) + int(timing["execution_ns"])
    ):
        raise VerificationError(f"{label}: field timing accounting is inconsistent")

def _verify_fixed_plan_attempt(
    attempt: Mapping[str, Any],
    task: Mapping[str, Any],
    *,
    label: str,
) -> None:
    _verify_attempt_timing(attempt, label=label)
    if attempt.get("status") != "answered":
        if attempt.get("execution_surface") is not None:
            raise VerificationError(f"{label}: unsupported field attempt names an execution surface")
        return
    if (
        attempt.get("execution_surface") != "fixed-plan-codec"
        or attempt.get("mechanism_request") is not None
        or attempt.get("mechanism_result") is not None
    ):
        raise VerificationError(f"{label}: training prediction did not use the declared fixed codec")
    plan = attempt.get("plan")
    if not isinstance(plan, Mapping) or attempt.get("plan_sha256") != _sha(plan):
        raise VerificationError(f"{label}: field plan digest drifted")
    executed = execute_sqlite_oracle(
        canonical_table(task["input_table"]),
        _plan_sql(plan),
        operation_id=f"independent-verifier:{label}:field-plan",
        max_rows=8,
        timeout_ms=1000,
    )
    if (
        executed.get("status") != "supported"
        or executed.get("canonical_output") != attempt.get("prediction")
        or executed.get("output_digest") != attempt.get("prediction_digest")
    ):
        raise VerificationError(f"{label}: fixed codec prediction differs from independent SQLite")


def _summarize_field(rows: Sequence[Mapping[str, Any]], oracle_by_case: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    families = sorted({str(row["family"]) for row in rows})
    by_family: dict[str, Any] = {}
    for family in families:
        selected = [row for row in rows if row["family"] == family]
        by_family[family] = {
            "total": len(selected),
            "answered": sum(row["attempt"]["status"] == "answered" for row in selected),
            "correct": sum(
                _prediction_matches(
                    row["attempt"],
                    oracle_by_case[row["case_id"]]["truth"]["canonical_output"],
                )
                for row in selected
            ),
        }
    return {
        "total": len(rows),
        "answered": sum(row["attempt"]["status"] == "answered" for row in rows),
        "correct": sum(
            _prediction_matches(
                row["attempt"],
                oracle_by_case[row["case_id"]]["truth"]["canonical_output"],
            )
            for row in rows
        ),
        "by_family": by_family,
    }


def _as_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise VerificationError(f"{label} is boolean")
    try:
        result = int(str(value))
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"{label} is not an integer") from exc
    if not -32 <= result <= 32:
        raise VerificationError(f"{label} is outside the bounded domain")
    return result


def _ast_to_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("op") != "pipeline":
        raise VerificationError("field interpretation is not a pipeline")
    if value.get("input") != {"op": "source"} or not isinstance(value.get("stages"), list):
        raise VerificationError("field interpretation source or stages are invalid")
    fill = None
    filter_op = None
    threshold = None
    distinct = False
    order = None
    limit = None
    seen: list[str] = []
    for stage in value["stages"]:
        if not isinstance(stage, Mapping):
            raise VerificationError("field interpretation stage is invalid")
        op = str(stage.get("op"))
        seen.append(op)
        if op == "project":
            columns = stage.get("columns")
            expression = columns.get("x") if isinstance(columns, Mapping) else None
            args = expression.get("args") if isinstance(expression, Mapping) else None
            if (
                not isinstance(expression, Mapping)
                or expression.get("op") != "coalesce"
                or not isinstance(args, list)
                or len(args) != 2
                or args[0] != {"op": "column", "name": "x"}
                or not isinstance(args[1], Mapping)
                or args[1].get("op") != "literal"
            ):
                raise VerificationError("field interpretation project is invalid")
            fill = _as_int(args[1].get("value"), "field fill")
        elif op == "filter":
            predicate = stage.get("predicate")
            if not isinstance(predicate, Mapping):
                raise VerificationError("field interpretation filter is invalid")
            filter_op = {"above": "gt", "below": "lt", "gt": "gt", "lt": "lt"}.get(
                str(predicate.get("op"))
            )
            right = predicate.get("right")
            if (
                filter_op is None
                or predicate.get("left") != {"op": "column", "name": "x"}
                or not isinstance(right, Mapping)
                or right.get("op") != "literal"
            ):
                raise VerificationError("field interpretation predicate is invalid")
            threshold = _as_int(right.get("value"), "field threshold")
        elif op == "distinct":
            distinct = True
        elif op == "order":
            order = {"ascending": "asc", "descending": "desc", "asc": "asc", "desc": "desc"}.get(
                str(stage.get("direction"))
            )
            if order is None or stage.get("expression") != {"op": "column", "name": "x"}:
                raise VerificationError("field interpretation order is invalid")
        elif op == "limit":
            limit = _as_int(stage.get("count"), "field limit")
        else:
            raise VerificationError(f"field interpretation has unsupported stage {op}")
    expected = [name for name in ("project", "filter", "distinct", "order", "limit") if name in seen]
    if seen != expected or order is None:
        raise VerificationError("field interpretation stages are absent, duplicated, or out of order")
    return _plan(
        fill=fill,
        filter_op=filter_op,
        threshold=threshold,
        distinct=distinct,
        order=order,
        limit=limit,
    )


def _plan_to_ast(plan: Mapping[str, Any]) -> dict[str, Any]:
    stages: list[dict[str, Any]] = []
    if plan["fill"] is not None:
        stages.append(
            {
                "op": "project",
                "columns": {
                    "x": {
                        "op": "coalesce",
                        "args": [
                            {"op": "column", "name": "x"},
                            {"op": "literal", "value": int(plan["fill"])},
                        ],
                    }
                },
            }
        )
    if plan["filter_op"] is not None:
        stages.append(
            {
                "op": "filter",
                "predicate": {
                    "op": str(plan["filter_op"]),
                    "left": {"op": "column", "name": "x"},
                    "right": {"op": "literal", "value": int(plan["threshold"])},
                },
            }
        )
    if plan["distinct"]:
        stages.append({"op": "distinct"})
    stages.append(
        {
            "op": "order",
            "expression": {"op": "column", "name": "x"},
            "direction": str(plan["order"]),
            "nulls": "first" if plan["order"] == "asc" else "last",
        }
    )
    if plan["limit"] is not None:
        stages.append({"op": "limit", "count": int(plan["limit"])})
    return {"op": "pipeline", "input": {"op": "source"}, "stages": stages}


def _live_field_attempt(
    memory: CassiFieldWorkMemory,
    task: Mapping[str, Any],
    *,
    operation_prefix: str,
) -> dict[str, Any]:
    interpreted = memory.semantic(
        {
            "operation": "interpret",
            "operation_id": f"{operation_prefix}:interpret",
            "text": task["instruction"],
        }
    )
    result = interpreted.get("result", {})
    interpretation = result.get("interpretation") if isinstance(result, Mapping) else None
    if not isinstance(interpretation, Mapping) or not isinstance(interpretation.get("content"), Mapping):
        return {"status": "unsupported", "interpret_result": interpreted, "prediction": None}
    plan = _ast_to_plan(interpretation["content"].get("query_ast"))
    mechanism = memory.semantic(
        {
            "operation": "mechanism-step",
            "operation_id": f"{operation_prefix}:mechanism",
            "mechanism_id": MECHANISM_ID,
            "state": {},
            "action": {"query_ast": _plan_to_ast(plan), "table": task["input_table"]},
            "context": {},
            "interval": {},
        }
    )
    outcome = mechanism.get("result", {}).get("outcome", {})
    prediction = outcome.get("output") if isinstance(outcome, Mapping) else None
    if not isinstance(prediction, Mapping):
        raise VerificationError("live final field mechanism emitted no table")
    return {
        "status": "answered",
        "interpret_result": interpreted,
        "plan": plan,
        "prediction": canonical_table(prediction),
        "mechanism_result": mechanism,
    }


def _hardlink_clone(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, copy_function=os.link)


def _contains_forbidden_truth(value: Any) -> bool:
    forbidden = {
        "truth_plan",
        "truth_letter",
        "oracle",
        "supported_letters",
        "matches_truth",
        "canonical_output",
    }
    if isinstance(value, Mapping):
        if any(str(key) in forbidden for key in value):
            return True
        return any(_contains_forbidden_truth(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_truth(item) for item in value)
    return False


def verify(receipt_path: Path, output_path: Path) -> tuple[dict[str, Any], int]:
    audit = Audit()
    holdout_rows: list[dict[str, Any]] = []
    source_state_before: Mapping[str, Any] | None = None
    source_state_after: Mapping[str, Any] | None = None
    try:
        receipt_path = receipt_path.resolve()
        audit.require("source receipt is stored on E drive", receipt_path.drive.upper() == "E:", str(receipt_path))
        source = json.loads(receipt_path.read_text(encoding="utf-8"))
        audit.require("source schema is recognized", source.get("schema") == SOURCE_SCHEMA)
        audit.require("source campaign completed", source.get("status") == "completed")
        stored_content = source.get("content_sha256")
        digest_body = copy.deepcopy(source)
        digest_body.pop("content_sha256", None)
        audit.require("source content digest reproduces", stored_content == _sha(digest_body), stored_content)

        config = source["configuration"]
        template_count = int(config["template_count"])
        repetitions = int(config["repetitions"])
        total_episodes = int(config["total_episodes"])
        seed = int(config["seed"])
        expected_templates = list(_EXPECTED_TEMPLATES[:template_count])
        audit.require("template count is bounded", 1 <= template_count <= len(_EXPECTED_TEMPLATES))
        audit.require("template manifest matches independent copy", source["templates"] == expected_templates)
        audit.require("episode count is complete", total_episodes == template_count * repetitions)
        expected_milestones = sorted(
            {0, total_episodes, *(value for value in (8, 16, 32, 64) if 0 < value < total_episodes)}
        )
        audit.require("checkpoint schedule is complete", config["milestones"] == expected_milestones)
        audit.require(
            "adaptive-state policy names only the regional field",
            config["adaptive_state_policy"]
            == "one CassiFI regional field; transformer frozen; no optimizer or learned side state",
        )
        audit.require(
            "campaign field capacity profile is exact",
            config["field_profile_overrides"] == dict(CAMPAIGN_PROFILE_OVERRIDES),
        )
        current_implementation = _current_implementation_identity()
        audit.require(
            "campaign implementation closure remains byte-exact",
            source["implementation_identity"] == current_implementation,
            current_implementation["aggregate_sha256"],
        )

        model_meta = source["model"]
        before = model_meta["artifact_before"]
        after = model_meta["artifact_after"]
        audit.require("pinned model digest is declared", before["sha256"] == MODEL_SHA256)
        audit.require("model artifact metadata is unchanged", before == after and model_meta["unchanged"] is True)
        model_path = Path(before["path"])
        audit.require("pinned model remains present", model_path.is_file(), str(model_path))
        audit.require("pinned model byte count remains exact", model_path.stat().st_size == int(before["bytes"]))
        audit.require("pinned model bytes remain exact", _file_sha(model_path) == MODEL_SHA256)
        identity_sha256 = str(model_meta["identity_sha256"])
        audit.require("model identity fingerprint reproduces", _sha(model_meta["identity"]) == identity_sha256)
        state_seed_sha256 = str(model_meta["state_seed"]["sha256"])
        state_seed_path = Path(model_meta["state_seed"]["path"])
        audit.require("zero-state seed remains present", state_seed_path.is_file(), str(state_seed_path))
        audit.require("zero-state seed digest remains exact", _file_sha(state_seed_path) == state_seed_sha256)
        audit.require("native context was reset for every attempt", model_meta["native_context_persisted_between_attempts"] is False)

        evaluation_tasks = source["evaluation_tasks"]
        audit.require("evaluation bank has one case per template", len(evaluation_tasks) == template_count)
        expected_evaluation = [
            _render_task(template, index + 1000, split="evaluation", seed=seed)
            for index, template in enumerate(expected_templates)
        ]
        for index, (stored, expected) in enumerate(zip(evaluation_tasks, expected_evaluation, strict=True)):
            if _task_core(stored) != _task_core(expected):
                raise VerificationError(f"evaluation task {index} differs from independent reconstruction")
            _verify_oracle(stored, stored["oracle"], f"evaluation:{index:03d}")
        audit.require("evaluation tasks and SQL consequences reconstruct", True, template_count)
        oracle_by_case = {task["case_id"]: task["oracle"] for task in evaluation_tasks}

        baseline_rows = source["baseline"]["frozen_model"]
        audit.require("frozen-model baseline covers evaluation bank", len(baseline_rows) == template_count)
        baseline_correct_by_case: dict[str, bool] = {}
        baseline_correct = 0
        baseline_answered = 0
        for index, (row, task) in enumerate(zip(baseline_rows, evaluation_tasks, strict=True)):
            if row["case_id"] != task["case_id"] or row["candidates"] != task["candidates"]:
                raise VerificationError(f"baseline row {index} does not bind to its evaluation task")
            correct = _verify_model(
                task,
                row["model"],
                identity_sha256=identity_sha256,
                state_seed_sha256=state_seed_sha256,
                label=f"baseline:{index:03d}",
            )
            if bool(row["matches_oracle"]) != correct:
                raise VerificationError(f"baseline row {index} correctness drifted")
            if row["event_order"] != {"model_commit": 1, "oracle_consequence": 2}:
                raise VerificationError(f"baseline row {index} chronology drifted")
            baseline_correct_by_case[task["case_id"]] = correct
            baseline_correct += int(correct)
            baseline_answered += int(row["model"]["choice"] is not None)
        expected_model_summary = {
            "total": template_count,
            "answered": baseline_answered,
            "correct": baseline_correct,
        }
        audit.require(
            "frozen-model baseline summary recomputes",
            source["baseline"]["frozen_model_summary"] == expected_model_summary,
            expected_model_summary,
        )

        cold_rows = source["baseline"]["cold_field"]
        audit.require("cold-field baseline covers evaluation bank", len(cold_rows) == template_count)
        for row in cold_rows:
            _verify_attempt_timing(row["attempt"], label="cold-field baseline")
            if _contains_forbidden_truth(row["attempt"].get("interpret_request", {})):
                raise VerificationError("cold field received a hidden truth field")
            expected_match = _prediction_matches(
                row["attempt"], oracle_by_case[row["case_id"]]["truth"]["canonical_output"]
            )
            if bool(row["matches_oracle"]) != expected_match:
                raise VerificationError("cold-field correctness drifted")
        cold_summary = _summarize_field(cold_rows, oracle_by_case)
        audit.require("cold-field summary recomputes", source["baseline"]["cold_field_summary"] == cold_summary)
        audit.require("cold-field process restart is exact", source["baseline"]["cold_field_restart_equal"] is True)

        episodes = source["episodes"]
        audit.require("all planned episodes were persisted", len(episodes) == total_episodes)
        expected_training = [
            _render_task(
                expected_templates[episode // repetitions],
                episode,
                split="training",
                seed=seed,
            )
            for episode in range(total_episodes)
        ]
        previous_state: Mapping[str, Any] | None = None
        acquisition_count = 0
        training_model_correct = 0
        training_field_correct = 0
        for episode, (row, expected_task) in enumerate(zip(episodes, expected_training, strict=True)):
            if row["episode"] != episode or row["template_index"] != episode // repetitions or row["repetition"] != episode % repetitions:
                raise VerificationError(f"episode {episode} schedule drifted")
            if _task_core(row["task"]) != _task_core(expected_task):
                raise VerificationError(f"episode {episode} task differs from independent reconstruction")
            _verify_oracle(row["task"], row["oracle"], f"training:{episode:03d}")
            model_correct = _verify_model(
                row["task"],
                row["model"],
                identity_sha256=identity_sha256,
                state_seed_sha256=state_seed_sha256,
                label=f"training:{episode:03d}",
            )
            truth_output = row["oracle"]["truth"]["canonical_output"]
            field_correct = _prediction_matches(row["field_pre"], truth_output)
            _verify_fixed_plan_attempt(
                row["field_pre"],
                row["task"],
                label=f"training:{episode:03d}:field-pre",
            )
            if bool(row["model_matches_oracle"]) != model_correct or bool(row["field_pre_matches_oracle"]) != field_correct:
                raise VerificationError(f"episode {episode} stored correctness drifted")
            if _contains_forbidden_truth(row["field_pre"].get("interpret_request", {})):
                raise VerificationError(f"episode {episode} field prediction received hidden truth")
            if previous_state is not None and row["state_before"] != previous_state:
                raise VerificationError(f"episode {episode} breaks the persistent field state chain")
            previous_state = row["state_after"]
            first_exposure = episode % repetitions == 0
            episode_timing = row.get("timing")
            if not isinstance(episode_timing, Mapping) or set(episode_timing) != {
                "oracle_ns",
                "consequence_admission_ns",
                "construction_learning_ns",
                "total_ns",
            }:
                raise VerificationError(f"episode {episode} timing receipt is incomplete")
            for name, value in episode_timing.items():
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise VerificationError(f"episode {episode} timing {name} is invalid")
            if (
                int(episode_timing["oracle_ns"]) <= 0
                or int(episode_timing["consequence_admission_ns"]) <= 0
                or int(episode_timing["total_ns"]) <= int(row["model"]["elapsed_ns"])
                or (int(episode_timing["construction_learning_ns"]) > 0) != first_exposure
            ):
                raise VerificationError(f"episode {episode} timing accounting is inconsistent")
            if first_exposure:
                if row["learning"] is None or row["field_post"] is None or row["field_post_matches_oracle"] is not True:
                    raise VerificationError(f"episode {episode} did not acquire its new construction")
                if not _prediction_matches(row["field_post"], truth_output):
                    raise VerificationError(f"episode {episode} post-learning output differs from SQLite")
                _verify_fixed_plan_attempt(
                    row["field_post"],
                    row["task"],
                    label=f"training:{episode:03d}:field-post",
                )
                acquisition_count += 1
            elif row["learning"] is not None or row["field_post"] is not None or row["field_post_matches_oracle"] is not None:
                raise VerificationError(f"episode {episode} relearned an existing construction")
            expected_order = {
                "field_commit": 1,
                "model_commit": 2,
                "oracle_consequence": 3,
                "field_observation": 4,
                "construction_learning": 5 if first_exposure else None,
            }
            if row["event_order"] != expected_order:
                raise VerificationError(f"episode {episode} chronology drifted")
            training_model_correct += int(model_correct)
            training_field_correct += int(field_correct)
        audit.require("training state is one unbroken persistent chain", True, total_episodes)
        audit.require("each surface construction was acquired once", acquisition_count == template_count, acquisition_count)

        checkpoints = source["checkpoints"]
        audit.require("all scheduled checkpoints exist", [row["milestone"] for row in checkpoints] == expected_milestones)
        for checkpoint in checkpoints:
            milestone = int(checkpoint["milestone"])
            rows = checkpoint["evaluation"]
            if len(rows) != template_count:
                raise VerificationError(f"checkpoint {milestone} evaluation coverage drifted")
            for row in rows:
                _verify_attempt_timing(
                    row["attempt"],
                    label=f"checkpoint {milestone} field evaluation",
                )
                if _contains_forbidden_truth(row["attempt"].get("interpret_request", {})):
                    raise VerificationError(f"checkpoint {milestone} field received hidden truth")
                if (
                    row["attempt"].get("status") == "answered"
                    and row["attempt"].get("execution_surface")
                    != "field-owned-sequence-composer"
                ):
                    raise VerificationError(
                        f"checkpoint {milestone} bypassed the field-owned mechanism"
                    )
                expected_match = _prediction_matches(
                    row["attempt"], oracle_by_case[row["case_id"]]["truth"]["canonical_output"]
                )
                if bool(row["matches_oracle"]) != expected_match:
                    raise VerificationError(f"checkpoint {milestone} correctness drifted")
            summary = _summarize_field(rows, oracle_by_case)
            if checkpoint["summary"] != summary:
                raise VerificationError(f"checkpoint {milestone} summary drifted")
            learned_count = min(template_count, (milestone + repetitions - 1) // repetitions)
            learned_ids = [template["id"] for template in expected_templates[:learned_count]]
            if checkpoint["learned_template_ids"] != learned_ids:
                raise VerificationError(f"checkpoint {milestone} learned-template set drifted")
            retained = [row for row in rows if row["template_id"] in set(learned_ids)]
            early_ids = set(learned_ids[: min(8, len(learned_ids))])
            early = [row for row in rows if row["template_id"] in early_ids]
            expected_retention = {
                "total": len(retained),
                "correct": sum(bool(row["matches_oracle"]) for row in retained),
                "early_total": len(early),
                "early_correct": sum(bool(row["matches_oracle"]) for row in early),
            }
            if checkpoint["retention"] != expected_retention:
                raise VerificationError(f"checkpoint {milestone} retention summary drifted")
            combined = 0
            for row in rows:
                if row["attempt"]["status"] == "answered":
                    combined += int(bool(row["matches_oracle"]))
                else:
                    combined += int(baseline_correct_by_case[row["case_id"]])
            if checkpoint["combined_with_frozen_model"] != {"total": template_count, "correct": combined}:
                raise VerificationError(f"checkpoint {milestone} combined policy summary drifted")
            if not (
                checkpoint["active_restart_equal"]
                and checkpoint["evaluation_snapshot_initial_equal"]
                and checkpoint["evaluation_restart_equal"]
            ):
                raise VerificationError(f"checkpoint {milestone} lacks exact restart/snapshot equality")
            if milestone > 0 and checkpoint["training_state"] != episodes[milestone - 1]["state_after"]:
                raise VerificationError(f"checkpoint {milestone} is not anchored to its training state")
        audit.require("checkpoint transfer, retention, and restart metrics recompute", True, len(checkpoints))
        performance = source.get("performance")
        if not isinstance(performance, Mapping):
            raise VerificationError("performance receipt is missing")
        campaign_elapsed = performance.get("campaign_elapsed_ns_before_receipt_write")
        if isinstance(campaign_elapsed, bool) or not isinstance(campaign_elapsed, int) or campaign_elapsed <= 0:
            raise VerificationError("campaign elapsed time is invalid")
        model_attempt_rows = [
            *(row["model"] for row in baseline_rows),
            *(row["model"] for row in episodes),
        ]
        model_elapsed_values = [int(row["elapsed_ns"]) for row in model_attempt_rows]
        model_elapsed_ns = sum(model_elapsed_values)
        generated_tokens = sum(
            int(row["runtime_receipt"]["generated_tokens"])
            for row in model_attempt_rows
        )
        decoded_tokens = sum(
            int(row["runtime_receipt"]["decoded_tokens"])
            for row in model_attempt_rows
        )
        expected_model_performance = {
            "attempts": len(model_attempt_rows),
            "generated_tokens": generated_tokens,
            "decoded_tokens_including_prompt": decoded_tokens,
            "elapsed": _timing_summary_ns(model_elapsed_values),
            "generated_tokens_per_second": (
                0.0
                if model_elapsed_ns == 0
                else generated_tokens * 1_000_000_000.0 / model_elapsed_ns
            ),
            "decoded_tokens_per_second_including_prompt": (
                0.0
                if model_elapsed_ns == 0
                else decoded_tokens * 1_000_000_000.0 / model_elapsed_ns
            ),
            "field_state_persisted_between_attempts": False,
        }
        if performance.get("frozen_model") != expected_model_performance:
            raise VerificationError("frozen-model performance summary drifted from raw attempts")
        field_pre_values = [
            int(row["field_pre"]["timing"]["total_ns"]) for row in episodes
        ]
        if performance.get("training_field_pre") != _timing_summary_ns(field_pre_values):
            raise VerificationError("training field performance summary drifted")
        field_window_size = max(1, len(field_pre_values) // 4)
        expected_growth_windows = []
        for start in range(0, len(field_pre_values), field_window_size):
            stop = min(len(field_pre_values), start + field_window_size)
            expected_growth_windows.append(
                {
                    "first_episode": start,
                    "last_episode": stop - 1,
                    "learned_templates_at_start": start // repetitions,
                    "timing": _timing_summary_ns(field_pre_values[start:stop]),
                }
            )
        if performance.get("training_field_pre_growth_windows") != expected_growth_windows:
            raise VerificationError("field growth-window timings drifted")
        if performance.get("consequence_admission") != _timing_summary_ns(
            [int(row["timing"]["consequence_admission_ns"]) for row in episodes]
        ):
            raise VerificationError("consequence-admission timing summary drifted")
        if performance.get("construction_learning") != _timing_summary_ns(
            [
                int(row["timing"]["construction_learning_ns"])
                for row in episodes
                if int(row["timing"]["construction_learning_ns"]) > 0
            ]
        ):
            raise VerificationError("construction-learning timing summary drifted")
        if performance.get("training_episode_total") != _timing_summary_ns(
            [int(row["timing"]["total_ns"]) for row in episodes]
        ):
            raise VerificationError("episode timing summary drifted")
        expected_checkpoint_performance = [
            {
                "milestone": checkpoint["milestone"],
                "attempt_total": _timing_summary_ns(
                    [
                        int(row["attempt"]["timing"]["total_ns"])
                        for row in checkpoint["evaluation"]
                    ]
                ),
                "interpret": _timing_summary_ns(
                    [
                        int(row["attempt"]["timing"]["interpret_ns"])
                        for row in checkpoint["evaluation"]
                    ]
                ),
                "execution": _timing_summary_ns(
                    [
                        int(row["attempt"]["timing"]["execution_ns"])
                        for row in checkpoint["evaluation"]
                    ]
                ),
            }
            for checkpoint in checkpoints
        ]
        if performance.get("checkpoints") != expected_checkpoint_performance:
            raise VerificationError("checkpoint performance summaries drifted")
        audit.require("all performance summaries recompute from raw timings", True)

        final_state = source["field"]["final_state"]
        audit.require("final field receipt equals last training state", final_state == episodes[-1]["state_after"])
        audit.require("runner final process restart was exact", source["field"]["final_restart_equal"] is True)
        audit.require("runner final reopened state is exact", source["field"]["final_reopen_state"] == final_state)
        audit.require("all declared campaign invariants fired", all(source["invariants"].values()), source["invariants"])

        final_checkpoint = checkpoints[-1]
        final_summary = final_checkpoint["summary"]
        analysis = source["analysis"]
        audit.require("analysis training-model count recomputes", analysis["training_model_correct"] == training_model_correct)
        audit.require("analysis field-pre count recomputes", analysis["training_field_pre_correct"] == training_field_correct)
        audit.require("analysis acquisition count recomputes", analysis["new_construction_acquisitions"] == acquisition_count)
        audit.require("analysis transfer count recomputes", analysis["final_transfer_correct"] == final_summary["correct"])
        audit.require("analysis restart claim is exact", analysis["all_checkpoint_restarts_exact"] and analysis["final_restart_exact"])

        memory_home = Path(source["field"]["memory_home"]).resolve()
        audit.require("adaptive field storage is on E drive", memory_home.drive.upper() == "E:", str(memory_home))
        audit.require("persisted final field exists", memory_home.is_dir())
        scratch = output_path.parent / "independent-verifier-field-snapshot"
        with _campaign_memory(memory_home) as source_memory:
            source_state_before = source_memory.state_receipt()
        assert source_state_before is not None
        audit.require("live persisted field matches final receipt", dict(source_state_before) == dict(final_state))
        _hardlink_clone(memory_home, scratch)
        try:
            with _campaign_memory(scratch) as clone:
                clone_initial = clone.state_receipt()
                if dict(clone_initial) != dict(final_state):
                    raise VerificationError("independent clone initial state differs from final field")
                for index, template in enumerate(expected_templates):
                    task = _render_task(
                        template,
                        index + 2001,
                        split="verification",
                        seed=seed,
                    )
                    oracle = execute_sqlite_oracle(
                        task["input_table"],
                        task["sql"],
                        operation_id=f"independent-restart-holdout:{index:03d}",
                        max_rows=8,
                        timeout_ms=1000,
                    )
                    if oracle.get("status") != "supported":
                        raise VerificationError(f"independent holdout oracle failed at {index}")
                    attempt = _live_field_attempt(
                        clone,
                        task,
                        operation_prefix=f"independent-restart-holdout:{index:03d}",
                    )
                    matches = _prediction_matches(attempt, oracle["canonical_output"])
                    holdout_rows.append(
                        {
                            "case_id": task["case_id"],
                            "template_id": task["template_id"],
                            "family": task["family"],
                            "instruction": task["instruction"],
                            "bindings": task["bindings"],
                            "input_table": task["input_table"],
                            "truth_plan": task["truth_plan"],
                            "sql": task["sql"],
                            "oracle_output": oracle["canonical_output"],
                            "oracle_output_digest": oracle["output_digest"],
                            "attempt": attempt,
                            "matches_oracle": matches,
                        }
                    )
                clone_after = clone.state_receipt()
            with _campaign_memory(scratch) as reopened_clone:
                clone_reopen = reopened_clone.state_receipt()
            audit.require("independent evaluation clone restarts exactly", dict(clone_after) == dict(clone_reopen))
        finally:
            if scratch.exists():
                shutil.rmtree(scratch)
        with _campaign_memory(memory_home) as source_reopened:
            source_state_after = source_reopened.state_receipt()
        assert source_state_before is not None and source_state_after is not None
        audit.require("independent evaluation did not mutate training field", dict(source_state_before) == dict(source_state_after))
        audit.require(
            "independent unseen-binding restart holdout is fully correct",
            all(row["matches_oracle"] for row in holdout_rows) and len(holdout_rows) == template_count,
            {"correct": sum(row["matches_oracle"] for row in holdout_rows), "total": len(holdout_rows)},
        )

        report: dict[str, Any] = {
            "schema": VERIFY_SCHEMA,
            "status": "PASS",
            "source_receipt": str(receipt_path),
            "source_content_sha256": stored_content,
            "checks": audit.checks,
            "recomputed": {
                "frozen_model_baseline": expected_model_summary,
                "cold_field_baseline": cold_summary,
                "training_model_correct": training_model_correct,
                "training_model_total": total_episodes,
                "training_field_pre_correct": training_field_correct,
                "training_field_pre_total": total_episodes,
                "construction_acquisitions": acquisition_count,
                "construction_total": template_count,
                "final_transfer": final_summary,
                "independent_restart_holdout_correct": sum(row["matches_oracle"] for row in holdout_rows),
                "independent_restart_holdout_total": len(holdout_rows),
            },
            "independent_restart_holdout": holdout_rows,
            "source_state_before": source_state_before,
            "source_state_after": source_state_after,
        }
        report["content_sha256"] = _sha(report)
        _atomic_json(output_path, report)
        return report, 0
    except Exception as exc:
        report = {
            "schema": VERIFY_SCHEMA,
            "status": "FAIL",
            "source_receipt": str(receipt_path.resolve()),
            "checks": audit.checks,
            "failure_type": type(exc).__name__,
            "failure": str(exc),
            "independent_restart_holdout": holdout_rows,
            "source_state_before": source_state_before,
            "source_state_after": source_state_after,
        }
        report["content_sha256"] = _sha(report)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_json(output_path, report)
        return report, 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    receipt_path = args.receipt.resolve()
    output_path = (
        args.out.resolve()
        if args.out is not None
        else receipt_path.with_name("continuing-apprenticeship-verification.json")
    )
    report, code = verify(receipt_path, output_path)
    print(
        json.dumps(
            {
                "schema": VERIFY_SCHEMA,
                "status": report["status"],
                "verification": str(output_path),
                "content_sha256": report["content_sha256"],
                "checks_passed": sum(row["passed"] for row in report["checks"]),
                "checks_total": len(report["checks"]),
                "failure": report.get("failure"),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
