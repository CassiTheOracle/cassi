#!/usr/bin/env python3
"""Run a sustained, consequence-grounded Cassi field apprenticeship.

The Qwen transformer is a frozen proposal instrument.  One persistent CassiFI
regional field is the only adaptive owner.  Every training episode commits the
field and model predictions before a bounded SQLite oracle is executed; only
then is the verified consequence admitted and, on a new surface form, learned
as a field-owned language-to-program construction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
_CASSIFI = _ROOT / "CassiFI"
_CASSIQWEN = _ROOT / "CassiQwen"
for _path in (_CASSIFI, _CASSIQWEN):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from cassi_field_qwen_workbench import CassiFieldWorkMemory, cassifi_source_identity  # noqa: E402
from cassi_model_instrument import QwenNativeInstrument, sha256_path  # noqa: E402
from cassi_sqlite_apprenticeship import (  # noqa: E402
    canonical_json,
    canonical_table,
    digest_json,
    execute_sqlite_oracle,
    table_from_rows,
)
from run_sqlite_apprenticeship import sequence_composer_program  # noqa: E402

SCHEMA = "cassi.continuing-apprenticeship.v1"
SEQUENCE_SCHEMA = "cassifi.semantic-sequence-program.v1"
MODEL_SHA256 = "3895b6eaa91e705c06ad1938d16c22e86f073c6a67df86260a1da79be3d1f887"
NATIVE_EXECUTABLE = (
    _CASSIQWEN / "native" / "llama.cpp" / "b8" / "bin" / "Release" / "cassi-qwen.exe"
)
NATIVE_MODEL = _CASSIQWEN / "Qwen3.8-27B-UD-IQ1_S.gguf"
NATIVE_STATE = _CASSIQWEN / "_diag" / "latent-reasoning" / "zero-state-4scale.f32"
DEFAULT_OUT = Path("E:/CassiLearning/continuing-apprenticeship-27b-iq1s-20260917-r2")
MECHANISM_ID = "mechanism:continuing-apprenticeship:sequence-composer"
MODEL_TOKENS = 8
CAMPAIGN_PROFILE_OVERRIDES: Mapping[str, int] = {"mode_count": 262_144}


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    staging = path.with_suffix(path.suffix + ".staging")
    staging.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    staging.replace(path)

def campaign_implementation_identity() -> dict[str, Any]:
    paths = {
        "runner": Path(__file__).resolve(),
        "field_workbench": _CASSIQWEN / "cassi_field_qwen_workbench.py",
        "model_instrument": _CASSIQWEN / "cassi_model_instrument.py",
        "sqlite_oracle": _CASSIQWEN / "cassi_sqlite_apprenticeship.py",
        "apprenticeship_helpers": _CASSIQWEN / "run_sqlite_apprenticeship.py",
    }
    files = {
        name: {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": sha256_path(path),
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


def campaign_memory(data_home: Path) -> CassiFieldWorkMemory:
    return CassiFieldWorkMemory(
        data_home,
        profile_overrides=CAMPAIGN_PROFILE_OVERRIDES,
    )

def timing_summary_ns(values: Sequence[int]) -> dict[str, int]:
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

def _plan(
    *,
    fill: int | None,
    filter_op: str | None,
    threshold: int | None,
    distinct: bool,
    order: str | None,
    limit: int | None,
) -> dict[str, Any]:
    if fill is not None and (isinstance(fill, bool) or not -32 <= fill <= 32):
        raise ValueError("fill is outside the bounded integer domain")
    if filter_op not in {None, "gt", "lt"}:
        raise ValueError("filter operation must be gt, lt, or absent")
    if (filter_op is None) != (threshold is None):
        raise ValueError("filter operation and threshold must be present together")
    if threshold is not None and (isinstance(threshold, bool) or not -32 <= threshold <= 32):
        raise ValueError("threshold is outside the bounded integer domain")
    if order not in {None, "asc", "desc"}:
        raise ValueError("order must be asc, desc, or absent")
    if limit is not None and (isinstance(limit, bool) or not 1 <= limit <= 8):
        raise ValueError("limit is outside [1,8]")
    return {
        "fill": fill,
        "filter_op": filter_op,
        "threshold": threshold,
        "distinct": bool(distinct),
        "order": order,
        "limit": limit,
    }


def plan_code(plan: Mapping[str, Any]) -> str:
    filter_code = (
        "_" if plan["filter_op"] is None else f"{plan['filter_op']}{int(plan['threshold'])}"
    )
    return ",".join(
        (
            "f_" if plan["fill"] is None else f"f{int(plan['fill'])}",
            filter_code,
            "u1" if plan["distinct"] else "u0",
            "o_" if plan["order"] is None else f"o{plan['order'][0]}",
            "l_" if plan["limit"] is None else f"l{int(plan['limit'])}",
        )
    )


def plan_to_ast(plan: Mapping[str, Any]) -> dict[str, Any]:
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
    if plan["order"] is not None:
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


def role_ast(family: str) -> dict[str, Any]:
    stages: list[dict[str, Any]] = []
    if family in {"fill-order-limit", "full-pipeline"}:
        stages.append(
            {
                "op": "project",
                "columns": {
                    "x": {
                        "op": "coalesce",
                        "args": [
                            {"op": "column", "name": "x"},
                            {"op": "literal", "value": {"$role": "fill_value"}},
                        ],
                    }
                },
            }
        )
    if family in {"filter-distinct-order", "full-pipeline"}:
        stages.append(
            {
                "op": "filter",
                "predicate": {
                    "op": {"$role": "filter_relation"},
                    "left": {"op": "column", "name": "x"},
                    "right": {
                        "op": "literal",
                        "value": {"$role": "threshold"},
                    },
                },
            }
        )
        stages.append({"op": "distinct"})
    stages.append(
        {
            "op": "order",
            "expression": {"op": "column", "name": "x"},
            "direction": {"$role": "order_direction"},
            "nulls": "last",
        }
    )
    if family in {"fill-order-limit", "full-pipeline"}:
        stages.append({"op": "limit", "count": {"$role": "row_limit"}})
    return {"op": "pipeline", "input": {"op": "source"}, "stages": stages}


def _as_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} is boolean")
    try:
        result = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not an integer") from exc
    if not -32 <= result <= 32:
        raise ValueError(f"{label} is outside the bounded integer domain")
    return result


def ast_to_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("op") != "pipeline":
        raise ValueError("interpretation did not emit a sequence pipeline")
    if value.get("input") != {"op": "source"} or not isinstance(value.get("stages"), list):
        raise ValueError("interpretation sequence source or stages are invalid")
    fill: int | None = None
    filter_op: str | None = None
    threshold: int | None = None
    distinct = False
    order: str | None = None
    limit: int | None = None
    seen: list[str] = []
    for stage in value["stages"]:
        if not isinstance(stage, Mapping) or not isinstance(stage.get("op"), str):
            raise ValueError("interpretation stage is invalid")
        op = str(stage["op"])
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
                raise ValueError("interpretation project stage is invalid")
            fill = _as_int(args[1].get("value"), "fill value")
        elif op == "filter":
            predicate = stage.get("predicate")
            if not isinstance(predicate, Mapping):
                raise ValueError("interpretation filter stage is invalid")
            relation = str(predicate.get("op"))
            relation = {"above": "gt", "below": "lt", "gt": "gt", "lt": "lt"}.get(
                relation, ""
            )
            if (
                not relation
                or predicate.get("left") != {"op": "column", "name": "x"}
                or not isinstance(predicate.get("right"), Mapping)
                or predicate["right"].get("op") != "literal"
            ):
                raise ValueError("interpretation filter predicate is invalid")
            filter_op = relation
            threshold = _as_int(predicate["right"].get("value"), "threshold")
        elif op == "distinct":
            distinct = True
        elif op == "order":
            direction = {"ascending": "asc", "descending": "desc", "asc": "asc", "desc": "desc"}.get(
                str(stage.get("direction")), ""
            )
            if not direction or stage.get("expression") != {"op": "column", "name": "x"}:
                raise ValueError("interpretation order stage is invalid")
            order = direction
        elif op == "limit":
            limit = _as_int(stage.get("count"), "row limit")
        else:
            raise ValueError(f"interpretation emitted unsupported stage {op!r}")
    expected = [name for name in ("project", "filter", "distinct", "order", "limit") if name in seen]
    if seen != expected or order is None:
        raise ValueError("interpretation stages are absent, duplicated, or out of order")
    return _plan(
        fill=fill,
        filter_op=filter_op,
        threshold=threshold,
        distinct=distinct,
        order=order,
        limit=limit,
    )


def execute_plan(rows: Sequence[int | None], plan: Mapping[str, Any]) -> dict[str, Any]:
    values: list[int | None] = list(rows)
    if plan["fill"] is not None:
        values = [int(plan["fill"]) if value is None else value for value in values]
    if plan["filter_op"] == "gt":
        values = [value for value in values if value is not None and value > int(plan["threshold"])]
    elif plan["filter_op"] == "lt":
        values = [value for value in values if value is not None and value < int(plan["threshold"])]
    if plan["distinct"]:
        unique: list[int | None] = []
        for value in values:
            if value not in unique:
                unique.append(value)
        values = unique
    if plan["order"] is not None:
        reverse = plan["order"] == "desc"
        nonnull = sorted((value for value in values if value is not None), reverse=reverse)
        nulls = [None] * sum(value is None for value in values)
        values = (nonnull + nulls) if reverse else (nulls + nonnull)
    if plan["limit"] is not None:
        values = values[: int(plan["limit"])]
    return table_from_rows(values)


def plan_sql(plan: Mapping[str, Any]) -> str:
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


_TEMPLATES: tuple[dict[str, str], ...] = (
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


def task_plan(family: str, index: int, *, evaluation: bool) -> dict[str, Any]:
    order = "desc" if index % 2 == 0 else "asc"
    if family == "fill-order-limit":
        fill = (9 if order == "desc" else -9) if evaluation else (8 if order == "desc" else -8)
        return _plan(
            fill=fill,
            filter_op=None,
            threshold=None,
            distinct=False,
            order=order,
            limit=2 + (index % 3),
        )
    filter_op = "gt" if index % 2 == 0 else "lt"
    threshold_values = (3, -3, 4, -4) if evaluation else (-1, 0, 1, 2)
    threshold = threshold_values[index % len(threshold_values)]
    if family == "filter-distinct-order":
        return _plan(
            fill=None,
            filter_op=filter_op,
            threshold=threshold,
            distinct=True,
            order=order,
            limit=None,
        )
    fill = threshold + 6 if filter_op == "gt" else threshold - 6
    return _plan(
        fill=fill,
        filter_op=filter_op,
        threshold=threshold,
        distinct=True,
        order=order,
        limit=4,
    )


def task_rows(plan: Mapping[str, Any]) -> list[int | None]:
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


def candidate_plans(truth: Mapping[str, Any]) -> list[dict[str, Any]]:
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
    normalized = [_plan(**row) for row in rows]
    if len({_sha(row) for row in normalized}) != 4:
        raise RuntimeError("candidate plans are not distinct")
    return normalized


def make_task(template: Mapping[str, str], index: int, *, evaluation: bool, seed: int) -> dict[str, Any]:
    truth = task_plan(template["family"], index, evaluation=evaluation)
    subject_pool = _EVAL_SUBJECTS if evaluation else _TRAIN_SUBJECTS
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
    candidates = candidate_plans(truth)
    rng = random.Random(seed * 1_000_003 + index * 97 + (31 if evaluation else 0))
    rng.shuffle(candidates)
    labelled = [
        {"letter": chr(ord("A") + offset), "plan": plan, "code": plan_code(plan)}
        for offset, plan in enumerate(candidates)
    ]
    truth_letter = next(row["letter"] for row in labelled if row["plan"] == truth)
    input_rows = task_rows(truth)
    outputs = [digest_json(execute_plan(input_rows, row["plan"])) for row in labelled]
    if len(set(outputs)) != 4:
        raise RuntimeError(f"task {template['id']} does not distinguish all candidates")
    split = "teacher-disconnected-evaluation" if evaluation else "consequence-grounded-training"
    return {
        "case_id": f"{split}:{template['id']}:{index:03d}",
        "split": split,
        "template_id": template["id"],
        "family": template["family"],
        "instruction": instruction,
        "instruction_sha256": _sha_text(instruction),
        "bindings": bindings,
        "input_rows": input_rows,
        "input_table": table_from_rows(input_rows),
        "candidates": labelled,
        "truth_plan": truth,
        "truth_plan_sha256": _sha(truth),
        "truth_letter": truth_letter,
        "sql": plan_sql(truth),
    }


def model_prompt(task: Mapping[str, Any]) -> str:
    candidate_lines = "\n".join(f"{row['letter']} {row['code']}" for row in task["candidates"])
    prompt = (
        f"Instruction: {task['instruction']}\n"
        f"Candidates:\n{candidate_lines}\n"
        "The correct candidate letter is"
    )
    if len(prompt.encode("utf-8")) > 1200:
        raise RuntimeError("model proposal prompt exceeded its byte bound")
    return prompt


def _model_choice(output: str) -> str | None:
    match = re.match(r"\s*([A-D])(?:\b|[.)])", output)
    return None if match is None else match.group(1)


def run_model_attempt(
    instrument: QwenNativeInstrument,
    task: Mapping[str, Any],
    trial_dir: Path,
) -> dict[str, Any]:
    prompt = model_prompt(task)
    trial = instrument.execute(
        mode="coupled",
        prompt=prompt,
        tokens=MODEL_TOKENS,
        trial_dir=trial_dir,
    )
    output = str(trial["output"])
    choice = _model_choice(output)
    selected = next(
        (row for row in task["candidates"] if row["letter"] == choice), None
    )
    return {
        "prompt": prompt,
        "prompt_sha256": _sha_text(prompt),
        "output": output,
        "output_sha256": _sha_text(output),
        "choice": choice,
        "selected_plan": None if selected is None else selected["plan"],
        "identity_sha256": trial["identity_sha256"],
        "runtime_receipt": trial["receipt"],
        "ownership": trial["ownership"],
        "state_predecessor": trial["state_predecessor"],
        "state_successor": trial["state_successor"],
        "continuation_class": trial["continuation_class"],
        "elapsed_ns": trial["elapsed_ns"],
    }


def oracle_after_commit(task: Mapping[str, Any], *, operation_prefix: str) -> dict[str, Any]:
    table = canonical_table(task["input_table"])
    truth = execute_sqlite_oracle(
        table,
        str(task["sql"]),
        operation_id=f"{operation_prefix}:truth",
        max_rows=8,
        timeout_ms=1000,
    )
    if truth.get("status") != "supported" or not isinstance(truth.get("canonical_output"), Mapping):
        raise RuntimeError(f"SQLite truth oracle failed for {task['case_id']}")
    candidate_rows: list[dict[str, Any]] = []
    for row in task["candidates"]:
        candidate_sql = plan_sql(row["plan"])
        result = execute_sqlite_oracle(
            table,
            candidate_sql,
            operation_id=f"{operation_prefix}:candidate:{row['letter']}",
            max_rows=8,
            timeout_ms=1000,
        )
        if result.get("status") != "supported" or not isinstance(result.get("canonical_output"), Mapping):
            raise RuntimeError(f"SQLite candidate oracle failed for {task['case_id']}:{row['letter']}")
        candidate_rows.append(
            {
                "letter": row["letter"],
                "plan_sha256": _sha(row["plan"]),
                "sql": candidate_sql,
                "output": result["canonical_output"],
                "output_digest": result["output_digest"],
                "matches_truth": result["canonical_output"] == truth["canonical_output"],
            }
        )
    supported = [row["letter"] for row in candidate_rows if row["matches_truth"]]
    if supported != [task["truth_letter"]] or len({row["output_digest"] for row in candidate_rows}) != 4:
        raise RuntimeError(f"SQLite consequence did not uniquely identify {task['case_id']}")
    return {
        "truth": {
            key: truth.get(key)
            for key in (
                "schema",
                "status",
                "canonical_output",
                "output_digest",
                "input_digest",
                "operation_id_digest",
                "runtime",
                "sqlite_version",
                "sqlite_source_id",
            )
        },
        "candidates": candidate_rows,
        "supported_letters": supported,
    }


def register_mechanism(memory: CassiFieldWorkMemory, *, label: str) -> Mapping[str, Any]:
    return memory.semantic(
        {
            "operation": "register",
            "operation_id": f"continuing-apprenticeship:{label}:register-composer",
            "record_id": MECHANISM_ID,
            "kind": "Program",
            "payload": {
                "program_role": "mechanism",
                "program": sequence_composer_program(),
                "causal_authority": True,
            },
            "epistemic_kind": "derived",
            "scope": "continuing-apprenticeship",
            "support_roots": [],
        }
    )


def field_attempt(
    memory: CassiFieldWorkMemory,
    task: Mapping[str, Any],
    *,
    operation_prefix: str,
    execute_in_field: bool = True,
) -> dict[str, Any]:
    started_ns = time.perf_counter_ns()
    interpret_started_ns = time.perf_counter_ns()
    interpret_elapsed_ns = 0
    interpret_request = {
        "operation": "interpret",
        "operation_id": f"{operation_prefix}:interpret",
        "text": task["instruction"],
    }
    try:
        interpreted = memory.semantic(interpret_request)
        interpret_elapsed_ns = time.perf_counter_ns() - interpret_started_ns
        result = interpreted.get("result", {})
        interpretation = result.get("interpretation") if isinstance(result, Mapping) else None
        if not isinstance(interpretation, Mapping):
            return {
                "status": "unsupported",
                "interpret_request": interpret_request,
                "interpret_result": interpreted,
                "plan": None,
                "prediction": None,
                "execution_surface": None,
                "timing": {
                    "interpret_ns": interpret_elapsed_ns,
                    "execution_ns": 0,
                    "total_ns": time.perf_counter_ns() - started_ns,
                },
                "error": None,
            }
        content = interpretation.get("content")
        if not isinstance(content, Mapping):
            raise ValueError("interpretation contains no grounded content")
        plan = ast_to_plan(content.get("query_ast"))
        mechanism_request: Mapping[str, Any] | None = None
        mechanism: Mapping[str, Any] | None = None
        execution_started_ns = time.perf_counter_ns()
        if execute_in_field:
            mechanism_request = {
                "operation": "mechanism-step",
                "operation_id": f"{operation_prefix}:mechanism",
                "mechanism_id": MECHANISM_ID,
                "state": {},
                "action": {"query_ast": plan_to_ast(plan), "table": task["input_table"]},
                "context": {},
                "interval": {},
            }
            mechanism = memory.semantic(mechanism_request)
            if not isinstance(mechanism, Mapping):
                raise ValueError("field mechanism receipt is invalid")
            outcome = mechanism.get("result", {}).get("outcome", {})
            prediction = outcome.get("output") if isinstance(outcome, Mapping) else None
            if not isinstance(prediction, Mapping):
                raise ValueError("field mechanism emitted no table")
            execution_surface = "field-owned-sequence-composer"
        else:
            prediction = execute_plan(task["input_rows"], plan)
            execution_surface = "fixed-plan-codec"
        execution_elapsed_ns = time.perf_counter_ns() - execution_started_ns
        canonical_prediction = canonical_table(prediction)
        return {
            "status": "answered",
            "interpret_request": interpret_request,
            "interpret_result": interpreted,
            "plan": plan,
            "plan_sha256": _sha(plan),
            "mechanism_request": mechanism_request,
            "mechanism_result": mechanism,
            "prediction": canonical_prediction,
            "prediction_digest": digest_json(canonical_prediction),
            "execution_surface": execution_surface,
            "timing": {
                "interpret_ns": interpret_elapsed_ns,
                "execution_ns": execution_elapsed_ns,
                "total_ns": time.perf_counter_ns() - started_ns,
            },
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "error",
            "interpret_request": interpret_request,
            "plan": None,
            "prediction": None,
            "execution_surface": None,
            "timing": {
                "interpret_ns": (
                    interpret_elapsed_ns
                    if interpret_elapsed_ns
                    else time.perf_counter_ns() - interpret_started_ns
                ),
                "execution_ns": 0,
                "total_ns": time.perf_counter_ns() - started_ns,
            },
            "error": f"{type(exc).__name__}: {exc}",
        }


def admit_consequence(
    memory: CassiFieldWorkMemory,
    task: Mapping[str, Any],
    model: Mapping[str, Any],
    field: Mapping[str, Any],
    oracle: Mapping[str, Any],
    *,
    episode: int,
) -> Mapping[str, Any]:
    truth_output = oracle["truth"]["canonical_output"]
    model_selected = next(
        (row for row in oracle["candidates"] if row["letter"] == model.get("choice")),
        None,
    )
    value = {
        "instruction_sha256": task["instruction_sha256"],
        "model_choice": model.get("choice"),
        "model_output_sha256": model["output_sha256"],
        "model_prediction_digest": (
            None if model_selected is None else model_selected["output_digest"]
        ),
        "model_matches_oracle": bool(model_selected and model_selected["matches_truth"]),
        "field_status": field["status"],
        "field_prediction_digest": field.get("prediction_digest"),
        "field_matches_oracle": field.get("prediction") == truth_output,
        "oracle_output_digest": oracle["truth"]["output_digest"],
        "supported_candidate": task["truth_letter"],
        "supported_plan": task["truth_plan"],
    }
    return memory.semantic(
        {
            "operation": "observe",
            "operation_id": f"continuing-apprenticeship:episode:{episode:03d}:consequence",
            "delivery_id": f"delivery:continuing-apprenticeship:{episode:03d}",
            "event_id": f"event:continuing-apprenticeship:{episode:03d}",
            "episode_id": f"episode:{episode:03d}",
            "observations": [
                {
                    "binding_id": f"binding:continuing-apprenticeship:{episode:03d}:outcome",
                    "subject": f"episode:{episode:03d}",
                    "attribute": "verified-consequence",
                    "value": value,
                    "confidence": 1.0,
                    "epistemic_kind": "observed",
                    "frame": "verified-task-outcome",
                }
            ],
            "source": {
                "kind": "bounded-sqlite-oracle",
                "schema": oracle["truth"].get("schema"),
                "sqlite_source_id": oracle["truth"].get("sqlite_source_id"),
            },
            "scope": "continuing-apprenticeship",
            "support_roots": [str(oracle["truth"]["output_digest"])],
        }
    )


def learn_template(
    memory: CassiFieldWorkMemory,
    template: Mapping[str, str],
    task: Mapping[str, Any],
    oracle: Mapping[str, Any],
    *,
    episode: int,
) -> Mapping[str, Any]:
    return memory.semantic(
        {
            "operation": "learn-construction",
            "operation_id": f"continuing-apprenticeship:episode:{episode:03d}:learn-construction",
            "construction_id": f"construction:continuing-apprenticeship:{template['id']}",
            "examples": [
                {"text": task["instruction"], "bindings": dict(task["bindings"])}
            ],
            "meaning": {"query_ast": role_ast(template["family"])},
            "speech_act": "request",
            "support_roots": [str(oracle["truth"]["output_digest"])],
        }
    )


def evaluate_field(
    memory: CassiFieldWorkMemory,
    tasks: Sequence[Mapping[str, Any]],
    *,
    label: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, task in enumerate(tasks):
        attempt = field_attempt(
            memory,
            task,
            operation_prefix=f"continuing-apprenticeship:{label}:{index:03d}",
        )
        oracle_output = task["oracle"]["truth"]["canonical_output"]
        rows.append(
            {
                "case_id": task["case_id"],
                "template_id": task["template_id"],
                "family": task["family"],
                "instruction": task["instruction"],
                "instruction_sha256": task["instruction_sha256"],
                "input_table": task["input_table"],
                "attempt": attempt,
                "matches_oracle": attempt.get("prediction") == oracle_output,
                "oracle_output_digest": task["oracle"]["truth"]["output_digest"],
            }
        )
    return rows


def summarize_field(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    families = sorted({str(row["family"]) for row in rows})
    by_family = {}
    for family in families:
        selected = [row for row in rows if row["family"] == family]
        by_family[family] = {
            "total": len(selected),
            "answered": sum(row["attempt"]["status"] == "answered" for row in selected),
            "correct": sum(bool(row["matches_oracle"]) for row in selected),
        }
    return {
        "total": len(rows),
        "answered": sum(row["attempt"]["status"] == "answered" for row in rows),
        "correct": sum(bool(row["matches_oracle"]) for row in rows),
        "by_family": by_family,
    }


def summarize_model(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(rows),
        "answered": sum(row["model"]["choice"] is not None for row in rows),
        "correct": sum(bool(row["matches_oracle"]) for row in rows),
    }


def hardlink_clone(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copytree(source, destination, copy_function=os.link)


def checkpoint_evaluation(
    memory: CassiFieldWorkMemory,
    memory_home: Path,
    tasks: Sequence[Mapping[str, Any]],
    baseline_by_case: Mapping[str, bool],
    *,
    milestone: int,
    learned_template_ids: Sequence[str],
    scratch_root: Path,
) -> tuple[CassiFieldWorkMemory, dict[str, Any]]:
    state_before = memory.state_receipt()
    memory.close()
    clone_home = scratch_root / f"eval-snapshot-{milestone:03d}"
    hardlink_clone(memory_home, clone_home)
    with campaign_memory(clone_home) as clone:
        clone_initial = clone.state_receipt()
        if dict(clone_initial) != dict(state_before):
            raise RuntimeError("hard-linked evaluation snapshot differs from training state")
        rows = evaluate_field(clone, tasks, label=f"milestone:{milestone:03d}")
        clone_after = clone.state_receipt()
    with campaign_memory(clone_home) as clone_reopened:
        clone_reopened_state = clone_reopened.state_receipt()
    clone_restart_equal = dict(clone_after) == dict(clone_reopened_state)
    shutil.rmtree(clone_home)
    reopened = campaign_memory(memory_home)
    active_reopen = reopened.state_receipt()
    active_restart_equal = dict(state_before) == dict(active_reopen)
    if not active_restart_equal or not clone_restart_equal:
        reopened.close()
        raise RuntimeError("checkpoint restart equality failed")
    summary = summarize_field(rows)
    combined_correct = 0
    for row in rows:
        if row["attempt"]["status"] == "answered":
            combined_correct += int(bool(row["matches_oracle"]))
        else:
            combined_correct += int(bool(baseline_by_case[row["case_id"]]))
    learned = set(learned_template_ids)
    retained = [row for row in rows if row["template_id"] in learned]
    early_ids = set(list(learned_template_ids)[: min(8, len(learned_template_ids))])
    early = [row for row in rows if row["template_id"] in early_ids]
    return reopened, {
        "milestone": milestone,
        "training_state": state_before,
        "active_restart_equal": active_restart_equal,
        "evaluation_snapshot_initial_equal": dict(clone_initial) == dict(state_before),
        "evaluation_restart_equal": clone_restart_equal,
        "learned_template_ids": list(learned_template_ids),
        "evaluation": rows,
        "summary": summary,
        "combined_with_frozen_model": {
            "total": len(rows),
            "correct": combined_correct,
        },
        "retention": {
            "total": len(retained),
            "correct": sum(bool(row["matches_oracle"]) for row in retained),
            "early_total": len(early),
            "early_correct": sum(bool(row["matches_oracle"]) for row in early),
        },
    }


def _progress(path: Path, row: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def run_campaign(
    *,
    out: Path,
    template_count: int,
    repetitions: int,
    seed: int,
    model: Path,
) -> dict[str, Any]:
    campaign_started_ns = time.perf_counter_ns()
    if not 1 <= template_count <= len(_TEMPLATES):
        raise ValueError(f"template_count must be in [1,{len(_TEMPLATES)}]")
    if not 1 <= repetitions <= 8:
        raise ValueError("repetitions must be in [1,8]")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    progress_path = out / "progress.jsonl"
    scratch_root = out / "scratch"
    scratch_root.mkdir()
    memory_home = out / "field-memory"
    cold_home = out / "cold-field"
    model_root = out / "model-trials"
    model_root.mkdir()
    implementation_identity = campaign_implementation_identity()
    selected_templates = list(_TEMPLATES[:template_count])
    total_episodes = template_count * repetitions
    milestones = sorted(
        {
            0,
            total_episodes,
            *(
                value
                for value in (8, 16, 32, 64)
                if 0 < value < total_episodes
            ),
        }
    )
    model = Path(model).resolve()
    model_before = {"path": str(model), "bytes": model.stat().st_size, "sha256": sha256_path(model)}
    if model_before["sha256"] != MODEL_SHA256:
        raise RuntimeError("the sustained campaign model digest is not the pinned IQ1_S target")
    instrument = QwenNativeInstrument(
        executable=NATIVE_EXECUTABLE,
        model=model,
        state=NATIVE_STATE,
        backend="gpu",
        architecture="qwen3.5",
        quantization="IQ1_S",
        native_context=False,
    )
    identity = instrument.identity.as_dict()
    identity_sha256 = instrument.identity.fingerprint
    state_seed = {
        "path": str(NATIVE_STATE.resolve()),
        "bytes": NATIVE_STATE.stat().st_size,
        "sha256": sha256_path(NATIVE_STATE),
    }
    _progress(
        progress_path,
        {
            "status": "started",
            "episodes": total_episodes,
            "templates": template_count,
            "model_identity_sha256": identity_sha256,
        },
    )
    print(json.dumps({"status": "started", "episodes": total_episodes, "out": str(out)}), flush=True)

    evaluation_tasks: list[dict[str, Any]] = []
    model_baseline_rows: list[dict[str, Any]] = []
    for index, template in enumerate(selected_templates):
        task = make_task(template, index + 1000, evaluation=True, seed=seed)
        model_attempt = run_model_attempt(
            instrument,
            task,
            model_root / "baseline" / f"{index:03d}-{template['id']}",
        )
        oracle = oracle_after_commit(task, operation_prefix=f"continuing-apprenticeship:baseline:{index:03d}")
        model_selected = next(
            (row for row in oracle["candidates"] if row["letter"] == model_attempt["choice"]),
            None,
        )
        task = {**task, "oracle": oracle}
        evaluation_tasks.append(task)
        model_baseline_rows.append(
            {
                "case_id": task["case_id"],
                "template_id": task["template_id"],
                "family": task["family"],
                "instruction": task["instruction"],
                "input_table": task["input_table"],
                "candidates": task["candidates"],
                "truth_letter": task["truth_letter"],
                "model": model_attempt,
                "oracle": oracle,
                "matches_oracle": bool(model_selected and model_selected["matches_truth"]),
                "event_order": {"model_commit": 1, "oracle_consequence": 2},
            }
        )
        print(
            json.dumps(
                {
                    "status": "baseline",
                    "case": index + 1,
                    "total": template_count,
                    "model_correct": bool(model_selected and model_selected["matches_truth"]),
                }
            ),
            flush=True,
        )

    baseline_by_case = {
        row["case_id"]: bool(row["matches_oracle"]) for row in model_baseline_rows
    }
    with campaign_memory(cold_home) as cold:
        cold_register = register_mechanism(cold, label="cold")
        cold_state_before = cold.state_receipt()
        cold_rows = evaluate_field(cold, evaluation_tasks, label="cold")
        cold_state_after = cold.state_receipt()
    with campaign_memory(cold_home) as cold_reopened:
        cold_reopen = cold_reopened.state_receipt()
    cold_restart_equal = dict(cold_state_after) == dict(cold_reopen)
    if not cold_restart_equal:
        raise RuntimeError("cold-field restart equality failed")
    cold_summary = summarize_field(cold_rows)
    shutil.rmtree(cold_home)

    model_baseline_summary = summarize_model(model_baseline_rows)
    checkpoints: list[dict[str, Any]] = [
        {
            "milestone": 0,
            "training_state": cold_state_before,
            "active_restart_equal": cold_restart_equal,
            "evaluation_snapshot_initial_equal": True,
            "evaluation_restart_equal": cold_restart_equal,
            "learned_template_ids": [],
            "evaluation": cold_rows,
            "summary": cold_summary,
            "combined_with_frozen_model": {
                "total": len(cold_rows),
                "correct": model_baseline_summary["correct"],
            },
            "retention": {"total": 0, "correct": 0, "early_total": 0, "early_correct": 0},
        }
    ]

    memory = campaign_memory(memory_home)
    register_receipt = register_mechanism(memory, label="warm")
    episodes: list[dict[str, Any]] = []
    learned_template_ids: list[str] = []
    next_milestones = set(milestones[1:])
    try:
        for episode in range(total_episodes):
            episode_started_ns = time.perf_counter_ns()
            template_index = episode // repetitions
            repetition = episode % repetitions
            template = selected_templates[template_index]
            task = make_task(
                template,
                episode,
                evaluation=False,
                seed=seed,
            )
            state_before = memory.state_receipt()
            field_pre = field_attempt(
                memory,
                task,
                operation_prefix=f"continuing-apprenticeship:episode:{episode:03d}:pre",
                execute_in_field=False,
            )
            model_attempt = run_model_attempt(
                instrument,
                task,
                model_root / "training" / f"{episode:03d}-{template['id']}",
            )
            oracle_started_ns = time.perf_counter_ns()
            oracle = oracle_after_commit(
                task,
                operation_prefix=f"continuing-apprenticeship:episode:{episode:03d}",
            )
            oracle_elapsed_ns = time.perf_counter_ns() - oracle_started_ns
            truth_output = oracle["truth"]["canonical_output"]
            model_selected = next(
                (row for row in oracle["candidates"] if row["letter"] == model_attempt["choice"]),
                None,
            )
            consequence_started_ns = time.perf_counter_ns()
            consequence = admit_consequence(
                memory,
                task,
                model_attempt,
                field_pre,
                oracle,
                episode=episode,
            )
            consequence_elapsed_ns = time.perf_counter_ns() - consequence_started_ns
            learning: Mapping[str, Any] | None = None
            field_post: Mapping[str, Any] | None = None
            learning_elapsed_ns = 0
            if repetition == 0:
                learning_started_ns = time.perf_counter_ns()
                learning = learn_template(
                    memory,
                    template,
                    task,
                    oracle,
                    episode=episode,
                )
                learning_elapsed_ns = time.perf_counter_ns() - learning_started_ns
                learned_template_ids.append(template["id"])
                field_post = field_attempt(
                    memory,
                    task,
                    operation_prefix=f"continuing-apprenticeship:episode:{episode:03d}:post",
                    execute_in_field=False,
                )
                if field_post.get("prediction") != truth_output:
                    raise RuntimeError(f"new construction did not acquire {template['id']}")
            state_after = memory.state_receipt()
            row = {
                "episode": episode,
                "template_index": template_index,
                "repetition": repetition,
                "template_id": template["id"],
                "family": template["family"],
                "task": task,
                "state_before": state_before,
                "field_pre": field_pre,
                "model": model_attempt,
                "oracle": oracle,
                "consequence": consequence,
                "learning": learning,
                "field_post": field_post,
                "state_after": state_after,
                "timing": {
                    "oracle_ns": oracle_elapsed_ns,
                    "consequence_admission_ns": consequence_elapsed_ns,
                    "construction_learning_ns": learning_elapsed_ns,
                    "total_ns": time.perf_counter_ns() - episode_started_ns,
                },
                "field_pre_matches_oracle": field_pre.get("prediction") == truth_output,
                "model_matches_oracle": bool(model_selected and model_selected["matches_truth"]),
                "field_post_matches_oracle": (
                    None if field_post is None else field_post.get("prediction") == truth_output
                ),
                "event_order": {
                    "field_commit": 1,
                    "model_commit": 2,
                    "oracle_consequence": 3,
                    "field_observation": 4,
                    "construction_learning": 5 if learning is not None else None,
                },
            }
            episodes.append(row)
            _progress(
                progress_path,
                {
                    "status": "episode",
                    "episode": episode + 1,
                    "total": total_episodes,
                    "template_id": template["id"],
                    "field_pre_correct": row["field_pre_matches_oracle"],
                    "model_correct": row["model_matches_oracle"],
                    "learned": learning is not None,
                },
            )
            print(
                json.dumps(
                    {
                        "status": "episode",
                        "episode": episode + 1,
                        "total": total_episodes,
                        "template": template["id"],
                        "field_pre_correct": row["field_pre_matches_oracle"],
                        "model_correct": row["model_matches_oracle"],
                    }
                ),
                flush=True,
            )
            completed = episode + 1
            if completed in next_milestones:
                memory, checkpoint = checkpoint_evaluation(
                    memory,
                    memory_home,
                    evaluation_tasks,
                    baseline_by_case,
                    milestone=completed,
                    learned_template_ids=learned_template_ids,
                    scratch_root=scratch_root,
                )
                checkpoints.append(checkpoint)
                _progress(
                    progress_path,
                    {
                        "status": "checkpoint",
                        "milestone": completed,
                        "field_correct": checkpoint["summary"]["correct"],
                        "total": checkpoint["summary"]["total"],
                        "retained": checkpoint["retention"]["correct"],
                    },
                )
                print(
                    json.dumps(
                        {
                            "status": "checkpoint",
                            "milestone": completed,
                            "field_correct": checkpoint["summary"]["correct"],
                            "total": checkpoint["summary"]["total"],
                        }
                    ),
                    flush=True,
                )
        final_state = memory.state_receipt()
    finally:
        memory.close()

    with campaign_memory(memory_home) as final_reopened:
        final_reopen_state = final_reopened.state_receipt()
    final_restart_equal = dict(final_state) == dict(final_reopen_state)
    if not final_restart_equal:
        raise RuntimeError("final field state changed across process reopen")
    model_after = {"path": str(model), "bytes": model.stat().st_size, "sha256": sha256_path(model)}
    if model_after != model_before:
        raise RuntimeError("frozen model artifact changed during the campaign")

    final_checkpoint = checkpoints[-1]
    early_retention = final_checkpoint["retention"]
    learning_curve = [
        {
            "milestone": row["milestone"],
            "field_correct": row["summary"]["correct"],
            "field_answered": row["summary"]["answered"],
            "combined_correct": row["combined_with_frozen_model"]["correct"],
            "retention_correct": row["retention"]["correct"],
            "retention_total": row["retention"]["total"],
        }
        for row in checkpoints
    ]
    training_model_correct = sum(row["model_matches_oracle"] for row in episodes)
    training_field_pre_correct = sum(row["field_pre_matches_oracle"] for row in episodes)
    acquisition_correct = sum(row["field_post_matches_oracle"] is True for row in episodes)
    final_full_family = final_checkpoint["summary"]["by_family"].get(
        "full-pipeline", {"total": 0, "correct": 0}
    )
    model_attempt_rows = [
        *(row["model"] for row in model_baseline_rows),
        *(row["model"] for row in episodes),
    ]
    model_elapsed_values = [int(row["elapsed_ns"]) for row in model_attempt_rows]
    generated_tokens = sum(
        int(row["runtime_receipt"]["generated_tokens"])
        for row in model_attempt_rows
    )
    decoded_tokens = sum(
        int(row["runtime_receipt"]["decoded_tokens"])
        for row in model_attempt_rows
    )
    model_elapsed_ns = sum(model_elapsed_values)
    field_pre_values = [
        int(row["field_pre"]["timing"]["total_ns"]) for row in episodes
    ]
    field_window_size = max(1, len(field_pre_values) // 4)
    field_growth_windows = []
    for start in range(0, len(field_pre_values), field_window_size):
        stop = min(len(field_pre_values), start + field_window_size)
        field_growth_windows.append(
            {
                "first_episode": start,
                "last_episode": stop - 1,
                "learned_templates_at_start": start // repetitions,
                "timing": timing_summary_ns(field_pre_values[start:stop]),
            }
        )
    checkpoint_performance = [
        {
            "milestone": checkpoint["milestone"],
            "attempt_total": timing_summary_ns(
                [
                    int(row["attempt"]["timing"]["total_ns"])
                    for row in checkpoint["evaluation"]
                ]
            ),
            "interpret": timing_summary_ns(
                [
                    int(row["attempt"]["timing"]["interpret_ns"])
                    for row in checkpoint["evaluation"]
                ]
            ),
            "execution": timing_summary_ns(
                [
                    int(row["attempt"]["timing"]["execution_ns"])
                    for row in checkpoint["evaluation"]
                ]
            ),
        }
        for checkpoint in checkpoints
    ]
    performance = {
        "campaign_elapsed_ns_before_receipt_write": (
            time.perf_counter_ns() - campaign_started_ns
        ),
        "frozen_model": {
            "attempts": len(model_attempt_rows),
            "generated_tokens": generated_tokens,
            "decoded_tokens_including_prompt": decoded_tokens,
            "elapsed": timing_summary_ns(model_elapsed_values),
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
        },
        "training_field_pre": timing_summary_ns(field_pre_values),
        "training_field_pre_growth_windows": field_growth_windows,
        "consequence_admission": timing_summary_ns(
            [int(row["timing"]["consequence_admission_ns"]) for row in episodes]
        ),
        "construction_learning": timing_summary_ns(
            [
                int(row["timing"]["construction_learning_ns"])
                for row in episodes
                if int(row["timing"]["construction_learning_ns"]) > 0
            ]
        ),
        "training_episode_total": timing_summary_ns(
            [int(row["timing"]["total_ns"]) for row in episodes]
        ),
        "checkpoints": checkpoint_performance,
    }
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "completed",
        "configuration": {
            "seed": seed,
            "template_count": template_count,
            "repetitions": repetitions,
            "total_episodes": total_episodes,
            "milestones": milestones,
            "model_tokens_per_attempt": MODEL_TOKENS,
            "field_profile_overrides": dict(CAMPAIGN_PROFILE_OVERRIDES),
            "adaptive_state_policy": "one CassiFI regional field; transformer frozen; no optimizer or learned side state",
            "evaluation_policy": "teacher-disconnected hard-linked snapshot; outcomes never returned to training field",
        },
        "implementation_identity": implementation_identity,
        "templates": selected_templates,
        "model": {
            "identity": identity,
            "identity_sha256": identity_sha256,
            "artifact_before": model_before,
            "artifact_after": model_after,
            "unchanged": model_before == model_after,
            "state_seed": state_seed,
            "native_context_persisted_between_attempts": False,
        },
        "field": {
            "memory_home": str(memory_home),
            "registration": register_receipt,
            "final_state": final_state,
            "final_reopen_state": final_reopen_state,
            "final_restart_equal": final_restart_equal,
        },
        "evaluation_tasks": evaluation_tasks,
        "baseline": {
            "frozen_model": model_baseline_rows,
            "frozen_model_summary": model_baseline_summary,
            "cold_field_registration": cold_register,
            "cold_field_state_before": cold_state_before,
            "cold_field_state_after": cold_state_after,
            "cold_field_restart_equal": cold_restart_equal,
            "cold_field": cold_rows,
            "cold_field_summary": cold_summary,
        },
        "episodes": episodes,
        "checkpoints": checkpoints,
        "performance": performance,
        "analysis": {
            "learning_curve": learning_curve,
            "training_model_correct": training_model_correct,
            "training_model_total": len(episodes),
            "training_field_pre_correct": training_field_pre_correct,
            "training_field_pre_total": len(episodes),
            "new_construction_acquisitions": acquisition_correct,
            "new_construction_total": template_count,
            "final_transfer_correct": final_checkpoint["summary"]["correct"],
            "final_transfer_total": final_checkpoint["summary"]["total"],
            "final_retention_correct": early_retention["correct"],
            "final_retention_total": early_retention["total"],
            "final_early_retention_correct": early_retention["early_correct"],
            "final_early_retention_total": early_retention["early_total"],
            "final_full_pipeline_correct": final_full_family["correct"],
            "final_full_pipeline_total": final_full_family["total"],
            "all_checkpoint_restarts_exact": all(
                row["active_restart_equal"] and row["evaluation_restart_equal"]
                for row in checkpoints
            ),
            "final_restart_exact": final_restart_equal,
            "frozen_model_unchanged": model_before == model_after,
        },
        "invariants": {
            "all_model_attempts_use_pinned_identity": all(
                row["model"]["identity_sha256"] == identity_sha256
                for row in [*model_baseline_rows, *episodes]
            ),
            "all_model_attempts_restart_from_same_state": all(
                row["model"]["state_predecessor"]["sha256"] == state_seed["sha256"]
                for row in [*model_baseline_rows, *episodes]
            ),
            "all_training_predictions_precede_oracle": all(
                row["event_order"]["model_commit"] < row["event_order"]["oracle_consequence"]
                and row["event_order"]["field_commit"] < row["event_order"]["oracle_consequence"]
                for row in episodes
            ),
            "all_learning_follows_consequence": all(
                row["event_order"]["construction_learning"] is None
                or row["event_order"]["oracle_consequence"]
                < row["event_order"]["construction_learning"]
                for row in episodes
            ),
            "all_oracles_uniquely_discriminate": all(
                row["oracle"]["supported_letters"] == [row["task"]["truth_letter"]]
                for row in episodes
            ),
            "all_new_constructions_acquired": acquisition_correct == template_count,
            "all_final_transfer_cases_correct": final_checkpoint["summary"]["correct"]
            == final_checkpoint["summary"]["total"],
            "all_learned_templates_retained": early_retention["correct"]
            == early_retention["total"],
            "all_restarts_exact": all(
                row["active_restart_equal"] and row["evaluation_restart_equal"]
                for row in checkpoints
            )
            and final_restart_equal,
            "model_artifact_unchanged": model_before == model_after,
            "evaluation_did_not_mutate_training_field": all(
                row["active_restart_equal"] for row in checkpoints
            ),
        },
    }
    receipt["content_sha256"] = _sha(receipt)
    _atomic_json(out / "continuing-apprenticeship.json", receipt)
    shutil.rmtree(scratch_root)
    _progress(
        progress_path,
        {
            "status": "completed",
            "receipt": str(out / "continuing-apprenticeship.json"),
            "content_sha256": receipt["content_sha256"],
        },
    )
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--template-count", type=int, default=len(_TEMPLATES))
    parser.add_argument("--repetitions", type=int, default=4)
    parser.add_argument("--seed", type=int, default=38027)
    parser.add_argument("--model", type=Path, default=NATIVE_MODEL)
    args = parser.parse_args(argv)
    try:
        receipt = run_campaign(
            out=args.out,
            template_count=args.template_count,
            repetitions=args.repetitions,
            seed=args.seed,
            model=args.model,
        )
    except Exception as exc:
        failure = {
            "schema": SCHEMA,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        try:
            Path(args.out).mkdir(parents=True, exist_ok=True)
            _atomic_json(Path(args.out) / "failure.json", failure)
        except Exception:
            pass
        print(json.dumps(failure, sort_keys=True), file=sys.stderr, flush=True)
        return 1
    print(
        json.dumps(
            {
                "schema": SCHEMA,
                "status": "completed",
                "receipt": str((Path(args.out).resolve() / "continuing-apprenticeship.json")),
                "content_sha256": receipt["content_sha256"],
                "final_transfer": receipt["analysis"]["final_transfer_correct"],
                "final_transfer_total": receipt["analysis"]["final_transfer_total"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
