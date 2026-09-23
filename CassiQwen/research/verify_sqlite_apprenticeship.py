#!/usr/bin/env python3
"""Independently verify a bounded SQLite capability-apprenticeship receipt.

This verifier intentionally does not import CassiFI or the runner.  It validates
canonical tables and sequence programs, parses the restricted SQL itself, and
executes that AST with SQLite's documented NULL/three-valued semantics.  The
SQLite receipts in the input are evidence from the external teacher; they are
never used as the source of truth for the verifier's prediction.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

RUN_SCHEMA = "cassi.sqlite-apprenticeship-run.v1"
TABLE_SCHEMA = "cassifi.nullable-table.v1"
PROGRAM_SCHEMA = "cassifi.semantic-program-payload.v1"
SEQUENCE_SCHEMA = "cassifi.semantic-sequence-program.v1"
ORACLE_SCHEMA = "cassi.sqlite-apprenticeship-receipt.v1"
MAX_ROWS = 8
MAX_COLUMNS = 8
MAX_INTEGER = 32

_LANGUAGE_STAGE_RECIPE_SCHEMA = "cassi.language-stage-recipe-catalog.v1"
_EXPECTED_STAGE_RECIPE_KEYS = (
    "filter",
    "limit",
    "limit-distinct",
    "distinct-filter",
    "nested-reapply",
    "recursive-3",
    "recursive-4",
    "weave",
)

_LANGUAGE_RECIPE_TEACHER_LINE = re.compile(r"^mode recursive depth ([23])$")
_LANGUAGE_PARAMETRIC_RECIPE_KEY = "recursive-parametric"
_LANGUAGE_PARAMETRIC_RECIPE_FAMILY = "recursive"
_LANGUAGE_PARAMETRIC_RECIPE_TEMPLATE = {
    "layers": [
        ["project_filled", "order", "limit"],
        {
            "repeat": {"$role": "repeat_count"},
            "stages": ["filter_on_column", "project_column", "order", "limit"],
        },
        ["project_column", "distinct"],
    ],
}


class VerificationError(ValueError):
    pass


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"not canonical JSON: {exc}") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


_LANGUAGE_TEACHER_LINE = re.compile(
    r"^N=([05]); keep above ([05]); unique; (ascending|descending); "
    r"first ([23]); mode filter$"
)


def _native_visible_text(output: str) -> str:
    if not isinstance(output, str) or not output.strip():
        raise VerificationError("native language teacher emitted no text")
    has_open = "<think>" in output
    has_close = "</think>" in output
    if has_open != has_close:
        raise VerificationError("native language teacher think segment is unbalanced")
    if has_open:
        match = re.fullmatch(r"(?s)\s*<think>.*?</think>\s*(.*)\s*", output)
        if match is None:
            raise VerificationError("native language teacher think segment is malformed")
        output = match.group(1)
    visible = output.strip()
    if not visible:
        raise VerificationError("native language teacher emitted no visible text")
    return visible


def _verify_native_language_teacher(
    *,
    language_raw: Mapping[str, Any],
    learning_examples: Any,
    native_observation: Any,
) -> None:
    teacher = language_raw.get("native_teacher")
    if not isinstance(teacher, Mapping):
        raise VerificationError("native language teacher evidence is missing")
    prompt = teacher.get("prompt")
    trial = teacher.get("trial")
    visible_output = teacher.get("visible_output")
    examples = teacher.get("examples")
    if (
        not isinstance(prompt, str)
        or teacher.get("prompt_sha256") != digest_text(prompt)
        or not isinstance(trial, Mapping)
        or trial.get("schema") != "cassi.qwen-native-instrument-result.v1"
        or trial.get("status") != "staged"
        or trial.get("mode") != "coupled"
        or not isinstance(trial.get("identity_sha256"), str)
        or not isinstance(trial.get("identity"), Mapping)
        or not isinstance(trial.get("output"), str)
        or teacher.get("output_sha256") != digest_text(trial["output"])
        or not isinstance(trial.get("receipt"), Mapping)
        or trial["receipt"].get("schema") != "cassi.qi.native-runtime.v1"
        or trial["receipt"].get("verdict") != "PASS"
        or trial["receipt"].get("output_bytes")
        != len(trial["output"].encode("utf-8"))
        or not isinstance(trial.get("ownership"), Mapping)
        or trial["ownership"].get("silent_native_fallback") is not False
        or not isinstance(trial["ownership"].get("qwen_forward_passes"), int)
        or trial["ownership"]["qwen_forward_passes"] < 1
    ):
        raise VerificationError("native language teacher runtime evidence is invalid")
    observation_trial = (
        native_observation.get("trial")
        if isinstance(native_observation, Mapping)
        else None
    )
    if (
        not isinstance(observation_trial, Mapping)
        or trial.get("identity_sha256") != observation_trial.get("identity_sha256")
    ):
        raise VerificationError("native language teacher identity is not bound to the run")
    expected_visible = _native_visible_text(trial["output"])
    if visible_output != expected_visible:
        raise VerificationError("native language teacher visible output was altered")
    lines = expected_visible.splitlines()
    if (
        not 4 <= len(lines) <= 8
        or (len(lines) - 2) % 2 != 0
        or any(not line.strip() for line in lines)
    ):
        raise VerificationError("native language teacher emitted an unbounded lesson")
    expected_examples: list[dict[str, Any]] = []
    expected = (
        ("0", "0", "ascending", "2"),
        ("5", "5", "descending", "3"),
    )
    for (
        expected_value,
        expected_threshold,
        expected_direction,
        expected_limit,
    ), line in zip(expected, lines[:2]):
        text = line.strip()
        match = _LANGUAGE_TEACHER_LINE.fullmatch(text)
        if (
            match is None
            or match.group(1) != expected_value
            or match.group(2) != expected_threshold
            or match.group(3) != expected_direction
            or match.group(4) != expected_limit
        ):
            raise VerificationError("native language teacher lesson is outside the grammar")
        expected_examples.append(
            {
                "text": text,
                "bindings": {
                    "fill_value": f"N={expected_value}",
                    "threshold": expected_threshold,
                    "order_direction": expected_direction,
                    "row_limit": expected_limit,
                    "stage_arrangement": "filter",
                },
            }
        )
    recorded_recipe_examples = teacher.get("recipe_examples")
    expected_recipe_examples: list[dict[str, Any]] = []
    for index, line in enumerate(lines[2:]):
        expected_depth = ("2", "3")[index % 2]
        text = line.strip()
        match = _LANGUAGE_RECIPE_TEACHER_LINE.fullmatch(text)
        if match is None or match.group(1) != expected_depth:
            raise VerificationError(
                "native language teacher recipe lesson is outside the grammar"
            )
        if len(expected_recipe_examples) < 2:
            expected_recipe_examples.append(
                {
                    "text": text,
                    "bindings": {
                        "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
                        "repeat_count": expected_depth,
                    },
                }
            )
    if (
        examples != expected_examples
        or learning_examples != expected_examples
        or recorded_recipe_examples != expected_recipe_examples
    ):
        raise VerificationError("native teacher examples were not admitted into learning")
def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise VerificationError(f"{label} is not a bounded identifier")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise VerificationError(f"{label} is not an identifier")
    return value


def _cell(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise VerificationError(f"{label} is not a typed cell")
    kind = value.get("kind")
    if kind == "null" and set(value) == {"kind"}:
        return {"kind": "null"}
    if kind == "integer" and set(value) == {"kind", "value"}:
        number = value["value"]
        if isinstance(number, bool) or not isinstance(number, int) or not -MAX_INTEGER <= number <= MAX_INTEGER:
            raise VerificationError(f"{label} integer is outside [-32,32]")
        return {"kind": "integer", "value": int(number)}
    raise VerificationError(f"{label} has invalid cell keys/kind")


def table(value: Any, label: str = "table") -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"schema", "columns", "rows"}:
        raise VerificationError(f"{label} has invalid keys")
    if value["schema"] != TABLE_SCHEMA:
        raise VerificationError(f"{label} has invalid schema")
    columns = value["columns"]
    if (not isinstance(columns, list) or not columns or len(columns) > MAX_COLUMNS
            or any(not isinstance(c, str) or not c or len(c.encode("utf-8")) > 128
                   or any(ord(ch) < 32 for ch in c) for c in columns)
            or columns != sorted(set(columns))):
        raise VerificationError(f"{label} columns are not canonical")
    rows = value["rows"]
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise VerificationError(f"{label} rows exceed bound")
    expected = set(columns)
    result_rows: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping) or set(raw) != expected:
            raise VerificationError(f"{label} row {index} has invalid columns")
        result_rows.append({column: _cell(raw[column], f"{label} row {index}.{column}") for column in columns})
    return {"schema": TABLE_SCHEMA, "columns": list(columns), "rows": result_rows}


def _value(cell: Mapping[str, Any]) -> int | None:
    return None if cell["kind"] == "null" else int(cell["value"])


# ---- Independent sequence-program canonicalization and evaluator ------------

def _seq_expr(raw: Any, depth: int, count: list[int]) -> dict[str, Any]:
    if depth > 16 or not isinstance(raw, Mapping) or not isinstance(raw.get("op"), str):
        raise VerificationError("invalid sequence expression")
    count[0] += 1
    if count[0] > 256:
        raise VerificationError("sequence AST exceeds bound")
    op = raw["op"]
    if op == "column":
        if set(raw) != {"op", "name"}:
            raise VerificationError("invalid sequence column")
        return {"op": "column", "name": _identifier(raw["name"], "sequence column")}
    if op == "literal":
        if set(raw) != {"op", "value"}:
            raise VerificationError("invalid sequence literal")
        value = raw["value"]
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not -32 <= value <= 32):
            raise VerificationError("invalid sequence literal value")
        return {"op": "literal", "value": value}
    if op == "coalesce":
        args = raw.get("args")
        if set(raw) != {"op", "args"} or not isinstance(args, list) or not args or len(args) > MAX_COLUMNS:
            raise VerificationError("invalid sequence coalesce")
        return {"op": "coalesce", "args": [_seq_expr(x, depth + 1, count) for x in args]}
    raise VerificationError(f"unsupported sequence expression {op!r}")


def _seq_pred(raw: Any, depth: int, count: list[int]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or not isinstance(raw.get("op"), str):
        raise VerificationError("invalid sequence predicate")
    op = raw["op"]
    if op in {"eq", "ne", "lt", "gt"}:
        if set(raw) != {"op", "left", "right"}:
            raise VerificationError("invalid comparison predicate")
        return {"op": op, "left": _seq_expr(raw["left"], depth + 1, count),
                "right": _seq_expr(raw["right"], depth + 1, count)}
    if op == "is_null":
        if set(raw) != {"op", "expr"}:
            raise VerificationError("invalid IS NULL predicate")
        return {"op": op, "expr": _seq_expr(raw["expr"], depth + 1, count)}
    raise VerificationError(f"unsupported sequence predicate {op!r}")


def _seq_stage(raw: Any, depth: int, count: list[int]) -> dict[str, Any]:
    if depth > 16 or not isinstance(raw, Mapping) or not isinstance(raw.get("op"), str):
        raise VerificationError("invalid sequence stage")
    count[0] += 1
    if count[0] > 256:
        raise VerificationError("sequence AST exceeds bound")
    op = raw["op"]
    if op == "project":
        if set(raw) != {"op", "columns"}:
            raise VerificationError("invalid project stage")
        source = raw["columns"]
        if isinstance(source, Mapping):
            entries = list(source.items())
        elif isinstance(source, list):
            if any(not isinstance(x, Mapping) or set(x) != {"name", "expr"} for x in source):
                raise VerificationError("invalid project column")
            entries = [(x["name"], x["expr"]) for x in source]
        else:
            raise VerificationError("invalid project columns")
        names = [_identifier(name, "projected column") for name, _ in entries]
        if not names or len(names) > MAX_COLUMNS or names != sorted(set(names)):
            raise VerificationError("project columns are not canonical")
        return {"op": op, "columns": {name: _seq_expr(expr, depth + 1, count)
                                           for name, (_, expr) in zip(names, entries)}}
    if op == "filter":
        if set(raw) != {"op", "predicate"}:
            raise VerificationError("invalid filter stage")
        return {"op": op, "predicate": _seq_pred(raw["predicate"], depth + 1, count)}
    if op == "distinct":
        if set(raw) != {"op"}:
            raise VerificationError("invalid distinct stage")
        return {"op": op}
    if op == "order":
        allowed = {"op", "expression", "direction", "nulls"}
        allowed_old = {"op", "by", "direction", "nulls"}
        keys = set(raw)
        if (
            keys not in (allowed, allowed_old)
            or raw["direction"] not in {"asc", "desc"}
            or raw["nulls"] not in {"first", "last"}
        ):
            raise VerificationError("invalid order stage")
        expr = raw.get("expression", raw.get("by"))
        return {"op": op, "expression": _seq_expr(expr, depth + 1, count),
                "direction": raw["direction"], "nulls": raw["nulls"]}
    if op == "limit":
        number = raw.get("count")
        if set(raw) != {"op", "count"} or isinstance(number, bool) or not isinstance(number, int) or not 0 <= number <= MAX_ROWS:
            raise VerificationError("invalid limit stage")
        return {"op": op, "count": int(number)}
    raise VerificationError(f"unsupported sequence stage {op!r}")


def sequence_ast(raw: Any, depth: int = 0, count: list[int] | None = None) -> dict[str, Any]:
    count = [0] if count is None else count
    if depth > 16 or not isinstance(raw, Mapping) or not isinstance(raw.get("op"), str):
        raise VerificationError("invalid sequence AST")
    count[0] += 1
    if count[0] > 256:
        raise VerificationError("sequence AST exceeds bound")
    if raw["op"] == "source":
        if set(raw) != {"op"}:
            raise VerificationError("invalid sequence source")
        return {"op": "source"}
    if raw["op"] != "pipeline" or set(raw) != {"op", "input", "stages"}:
        raise VerificationError("invalid sequence pipeline")
    stages = raw["stages"]
    if not isinstance(stages, list) or len(stages) > 8:
        raise VerificationError("sequence stages exceed bound")
    return {"op": "pipeline", "input": sequence_ast(raw["input"], depth + 1, count),
            "stages": [_seq_stage(x, depth + 1, count) for x in stages]}


def sequence_program(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise VerificationError("sequence program is not an object")
    required = {"applicability", "arguments", "body", "bounds", "effects", "guards", "program_kind", "schema"}
    if set(raw) != required or raw.get("schema") != PROGRAM_SCHEMA or raw.get("program_kind") != "sequence":
        raise VerificationError("semantic sequence payload has invalid keys/schema")
    arguments = raw["arguments"]
    applicability = raw["applicability"]
    if not isinstance(arguments, Mapping) or not isinstance(applicability, Mapping):
        raise VerificationError("sequence payload arguments/applicability invalid")
    for name, descriptor in arguments.items():
        _identifier(name, "sequence argument")
        if not isinstance(descriptor, Mapping) or set(descriptor) != {"required", "type", "units"}:
            raise VerificationError("sequence argument descriptor invalid")
        _identifier(descriptor["type"], "sequence argument type")
        if not isinstance(descriptor["required"], bool) or not isinstance(descriptor["units"], (Mapping, str, type(None))):
            raise VerificationError("sequence argument descriptor value invalid")
    guards = raw["guards"]
    if not isinstance(guards, list):
        raise VerificationError("sequence guards invalid")
    for guard in guards:
        if (not isinstance(guard, Mapping) or set(guard) != {"left", "op", "right"}
                or guard["op"] not in {"eq", "ge", "gt", "in", "le", "lt", "ne", "not-in"}):
            raise VerificationError("sequence guard invalid")
        _identifier(guard["left"], "sequence guard operand")
    bounds = raw["bounds"]
    if not isinstance(bounds, Mapping) or set(bounds) != {"max_branches", "max_horizon", "max_work"}:
        raise VerificationError("sequence bounds invalid")
    for key in bounds:
        if isinstance(bounds[key], bool) or not isinstance(bounds[key], int) or not 1 <= bounds[key] <= 1_000_000:
            raise VerificationError("sequence bound invalid")
    effects = raw["effects"]
    if not isinstance(effects, Mapping) or set(effects) != {"emits", "reads", "writes"}:
        raise VerificationError("sequence effects invalid")
    for key in effects:
        if not isinstance(effects[key], list) or effects[key] != sorted(set(effects[key])) or any(not isinstance(x, str) or not x for x in effects[key]):
            raise VerificationError("sequence effects are not canonical")
    body = raw["body"]
    if (
        not isinstance(body, Mapping)
        or body.get("schema") != SEQUENCE_SCHEMA
        or set(body) not in ({"schema", "ast"}, {"schema", "ast", "ast_parameter"})
    ):
        raise VerificationError("sequence body invalid")
    result = copy.deepcopy(dict(raw))
    result_body = {"schema": SEQUENCE_SCHEMA, "ast": sequence_ast(body["ast"])}
    if "ast_parameter" in body:
        result_body["ast_parameter"] = _identifier(
            body["ast_parameter"], "sequence AST parameter"
        )
    result["body"] = result_body
    return result


def _eval_expr(expr: Mapping[str, Any], columns: list[str], values: tuple[int | None, ...]) -> int | None:
    op = expr["op"]
    if op == "column":
        if expr["name"] not in columns:
            raise VerificationError(f"sequence references missing column {expr['name']}")
        return values[columns.index(expr["name"])]
    if op == "literal":
        return expr["value"]
    for child in expr["args"]:
        value = _eval_expr(child, columns, values)
        if value is not None:
            return value
    return None


def _eval_pred(
    pred: Mapping[str, Any],
    columns: list[str],
    values: tuple[int | None, ...],
) -> bool | None:
    if pred["op"] == "is_null":
        return _eval_expr(pred["expr"], columns, values) is None
    left = _eval_expr(pred["left"], columns, values)
    right = _eval_expr(pred["right"], columns, values)
    if left is None or right is None:
        return None
    return {
        "eq": left == right,
        "ne": left != right,
        "lt": left < right,
        "gt": left > right,
    }[pred["op"]]


def execute_sequence(
    program: Mapping[str, Any],
    input_table: Mapping[str, Any],
    query_ast: Any = None,
) -> dict[str, Any]:
    prog = sequence_program(program)
    source = table(input_table, "sequence input")
    body = prog["body"]
    if "ast_parameter" in body:
        if query_ast is None:
            raise VerificationError("sequence AST parameter is missing")
        try:
            selected_ast = sequence_ast(query_ast)
        except VerificationError as exc:
            raise VerificationError("sequence AST parameter is invalid") from exc
    else:
        selected_ast = body["ast"]
    columns = list(source["columns"])
    rows = [
        (tuple(_value(row[c]) for c in columns), index)
        for index, row in enumerate(source["rows"])
    ]

    def pipeline(
        node: Mapping[str, Any],
        cols: list[str],
        data: list[tuple[tuple[int | None, ...], int]],
    ) -> tuple[list[str], list[tuple[tuple[int | None, ...], int]]]:
        if node["op"] == "source":
            return list(cols), list(data)
        cols, data = pipeline(node["input"], cols, data)
        for stage in node["stages"]:
            op = stage["op"]
            if op == "project":
                names = list(stage["columns"])
                data = [
                    (
                        tuple(
                            _eval_expr(stage["columns"][n], cols, values)
                            for n in names
                        ),
                        ordinal,
                    )
                    for values, ordinal in data
                ]
                cols = names
            elif op == "filter":
                data = [
                    (values, ordinal)
                    for values, ordinal in data
                    if _eval_pred(stage["predicate"], cols, values) is True
                ]
            elif op == "distinct":
                seen: set[tuple[int | None, ...]] = set()
                data = [
                    (values, ordinal)
                    for values, ordinal in data
                    if not (values in seen or seen.add(values))
                ]
            elif op == "order":
                expr = stage["expression"]
                null_first = stage["nulls"] == "first"
                direction = stage["direction"]

                def key(
                    item: tuple[tuple[int | None, ...], int],
                ) -> tuple[Any, ...]:
                    value = _eval_expr(expr, cols, item[0])
                    null_rank = (
                        (0 if null_first else 1)
                        if value is None
                        else (1 if null_first else 0)
                    )
                    value_key = (
                        0
                        if value is None
                        else (value if direction == "asc" else -value)
                    )
                    return null_rank, value_key, item[1]

                data.sort(key=key)
            elif op == "limit":
                data = data[: stage["count"]]
            else:
                raise VerificationError("unrecognized canonical stage")
        return cols, data

    out_columns, out_rows = pipeline(selected_ast, columns, rows)
    if not out_columns or out_columns != sorted(set(out_columns)):
        raise VerificationError("sequence output columns are not canonical")
    return {
        "schema": TABLE_SCHEMA,
        "columns": out_columns,
        "rows": [
            {
                name: (
                    {"kind": "null"}
                    if value is None
                    else {"kind": "integer", "value": value}
                )
                for name, value in zip(out_columns, values)
            }
            for values, _ in out_rows
        ],
    }


# ---- Independent restricted-SQL parser/evaluator -----------------------------
_TOKEN = re.compile(r"\s+|(?P<punc>[(),.])|(?P<op><>|!=|<=|>=|=|<|>)|(?P<int>\d+)|(?P<id>[A-Za-z_][A-Za-z0-9_]*)|(?P<minus>-)")
_RESERVED = {"SELECT", "DISTINCT", "FROM", "WHERE", "ORDER", "BY", "ASC", "DESC", "NULLS", "FIRST", "LAST", "LIMIT", "AS", "IS", "NOT", "NULL"}


def _tokens(sql: str) -> list[tuple[str, str]]:
    if not isinstance(sql, str) or not sql.strip() or len(sql.encode("utf-8")) > 16 * 1024:
        raise VerificationError("SQL is empty or exceeds bound")
    result: list[tuple[str, str]] = []
    pos = 0
    while pos < len(sql):
        match = _TOKEN.match(sql, pos)
        if not match:
            raise VerificationError(f"unsupported SQL character at {pos}")
        pos = match.end()
        kind = match.lastgroup
        text = match.group(0)
        if kind == "punc" or kind == "op" or kind == "minus":
            result.append((kind or "", text))
        elif kind == "int" or kind == "id":
            result.append((kind or "", text))
        # whitespace is discarded
    return result


class _SQL:
    def __init__(self, sql: str):
        self.ts = _tokens(sql)
        self.i = 0
    def peek(self, text: str | None = None) -> tuple[str, str] | None:
        if self.i >= len(self.ts): return None
        token = self.ts[self.i]
        return token if text is None or token[1].upper() == text else None
    def take(self, text: str | None = None) -> tuple[str, str]:
        token = self.peek(text)
        if token is None: raise VerificationError(f"expected {text or 'token'}")
        self.i += 1; return token
    def optional(self, text: str) -> bool:
        if self.peek(text) is None: return False
        self.i += 1; return True
    def parse(self) -> Mapping[str, Any]:
        query = self.query()
        if self.peek() is not None: raise VerificationError("trailing SQL")
        return query
    def query(self) -> Mapping[str, Any]:
        self.take("SELECT"); distinct = self.optional("DISTINCT")
        select = []
        while True:
            expr = self.expr(); alias = None
            if self.optional("AS"): alias = _identifier(self.take()[1], "SQL alias")
            elif self.peek() and self.peek()[0] == "id" and self.peek()[1].upper() not in _RESERVED:
                alias = _identifier(self.take()[1], "SQL alias")
            select.append((expr, alias))
            if not self.optional(","): break
        self.take("FROM")
        if self.optional("("):
            source = {"kind": "query", "query": self.query()}
            self.take(")")
            if self.optional("AS"): self.take()
            elif self.peek() and self.peek()[0] == "id" and self.peek()[1].upper() not in _RESERVED: self.take()
        else:
            name = self.take()[1]
            if name.lower() != "readings": raise VerificationError("SQL source must be readings")
            source = {"kind": "readings"}
            if self.optional("AS"): self.take()
            elif self.peek() and self.peek()[0] == "id" and self.peek()[1].upper() not in _RESERVED: self.take()
        where = self.pred() if self.optional("WHERE") else None
        order = None
        if self.optional("ORDER"):
            self.take("BY"); expression = self.expr(); direction = "asc"
            if self.peek("ASC") or self.peek("DESC"): direction = self.take()[1].lower()
            nulls = "last" if direction == "asc" else "first"
            if self.optional("NULLS"): nulls = self.take()[1].lower()
            order = (expression, direction, nulls)
        limit = None
        if self.optional("LIMIT"):
            kind, value = self.take()
            if kind != "int" or int(value) > MAX_ROWS: raise VerificationError("SQL LIMIT exceeds bound")
            limit = int(value)
        return {"select": select, "distinct": distinct, "source": source, "where": where, "order": order, "limit": limit}
    def expr(self) -> Mapping[str, Any]:
        negative = self.optional("-"); kind, value = self.take()
        if kind == "int":
            number = int(value) * (-1 if negative else 1)
            if not -MAX_INTEGER <= number <= MAX_INTEGER: raise VerificationError("SQL integer exceeds bound")
            return {"op": "literal", "value": number}
        if negative: raise VerificationError("only integer literals may be negative")
        if kind != "id": raise VerificationError("expected SQL expression")
        if value.upper() == "NULL": return {"op": "literal", "value": None}
        if value.upper() == "COALESCE":
            self.take("("); first = self.expr(); self.take(","); second = self.expr(); self.take(")")
            return {"op": "coalesce", "args": [first, second]}
        if self.optional("."): value = self.take()[1]
        return {"op": "column", "name": _identifier(value, "SQL column")}
    def pred(self) -> Mapping[str, Any]:
        left = self.expr()
        if self.optional("IS"):
            negate = self.optional("NOT"); self.take("NULL")
            # SQL's IS NOT NULL is represented by a negated is_null predicate.
            return {"op": "is_not_null" if negate else "is_null", "expr": left}
        operator = self.take()[1]
        if operator not in {"=", "!=", "<>", "<", ">", "<=", ">="}: raise VerificationError("invalid SQL predicate")
        return {"op": "compare", "left": left, "operator": operator, "right": self.expr()}

def _sql_to_sequence_expr(expr: Mapping[str, Any]) -> dict[str, Any]:
    op = expr.get("op")
    if op == "column":
        return {"op": "column", "name": _identifier(expr["name"], "SQL column")}
    if op == "literal":
        value = expr.get("value")
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not -MAX_INTEGER <= value <= MAX_INTEGER
        ):
            raise VerificationError("SQL literal is outside the sequence bound")
        return {"op": "literal", "value": value}
    if op == "coalesce":
        args = expr.get("args")
        if not isinstance(args, list) or not args:
            raise VerificationError("SQL coalesce expression is invalid")
        return {
            "op": "coalesce",
            "args": [_sql_to_sequence_expr(item) for item in args],
        }
    raise VerificationError(f"unsupported SQL expression {op!r}")


def _sql_to_sequence_predicate(pred: Mapping[str, Any]) -> dict[str, Any]:
    op = pred.get("op")
    if op == "is_null":
        return {"op": "is_null", "expr": _sql_to_sequence_expr(pred["expr"])}
    if op == "compare":
        operators = {"=": "eq", "!=": "ne", "<>": "ne", "<": "lt", ">": "gt"}
        mapped = operators.get(str(pred.get("operator")))
        if mapped is None:
            raise VerificationError("SQL comparison is outside the sequence bound")
        return {
            "op": mapped,
            "left": _sql_to_sequence_expr(pred["left"]),
            "right": _sql_to_sequence_expr(pred["right"]),
        }
    raise VerificationError(f"unsupported SQL predicate {op!r}")


def _sql_to_sequence_ast(query: Mapping[str, Any]) -> dict[str, Any]:
    source = query.get("source")
    if not isinstance(source, Mapping):
        raise VerificationError("SQL source is invalid")
    if source.get("kind") == "readings":
        input_ast: dict[str, Any] = {"op": "source"}
    elif source.get("kind") == "query" and isinstance(source.get("query"), Mapping):
        input_ast = _sql_to_sequence_ast(source["query"])
    else:
        raise VerificationError("SQL source is outside the sequence bound")
    stages: list[dict[str, Any]] = []
    where = query.get("where")
    if where is not None:
        if not isinstance(where, Mapping):
            raise VerificationError("SQL WHERE clause is invalid")
        stages.append({"op": "filter", "predicate": _sql_to_sequence_predicate(where)})
    selected = query.get("select")
    if not isinstance(selected, list) or not selected:
        raise VerificationError("SQL SELECT list is invalid")
    columns: dict[str, Any] = {}
    for expression, alias in selected:
        if not isinstance(expression, Mapping):
            raise VerificationError("SQL SELECT expression is invalid")
        name = alias
        if name is None:
            if expression.get("op") != "column":
                raise VerificationError("SQL expression requires an alias")
            name = expression.get("name")
        name = _identifier(name, "SQL output column")
        columns[name] = _sql_to_sequence_expr(expression)
    if list(columns) != sorted(set(columns)):
        raise VerificationError("SQL output columns are not canonical")
    stages.append({"op": "project", "columns": columns})
    if query.get("distinct"):
        stages.append({"op": "distinct"})
    order = query.get("order")
    if order is not None:
        if not isinstance(order, tuple) or len(order) != 3:
            raise VerificationError("SQL ORDER BY clause is invalid")
        expression, direction, nulls = order
        stages.append(
            {
                "op": "order",
                "expression": _sql_to_sequence_expr(expression),
                "direction": str(direction),
                "nulls": str(nulls),
            }
        )
    limit = query.get("limit")
    if limit is not None:
        stages.append({"op": "limit", "count": int(limit)})
    return sequence_ast({"op": "pipeline", "input": input_ast, "stages": stages})


def _compile_language_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("program_kind") != "component-composition":
        raise VerificationError("language plan kind is invalid")
    expected_keys = (
        "fill_value",
        "threshold_filter",
        "distinct",
        "order_limit",
        "stage_order",
    )
    components = plan.get("components")
    if (
        not isinstance(components, list)
        or [item.get("key") for item in components if isinstance(item, Mapping)]
        != list(expected_keys)
        or any(
            not isinstance(item, Mapping)
            or not isinstance(item.get("construction"), Mapping)
            for item in components
        )
    ):
        raise VerificationError("language plan component list is invalid")
    bindings = plan.get("bindings")
    if not isinstance(bindings, Mapping):
        raise VerificationError("language plan bindings are missing")
    fill_raw = bindings.get("fill_value")
    threshold_raw = bindings.get("threshold")
    limit_raw = bindings.get("row_limit")
    if (
        not isinstance(fill_raw, str)
        or not isinstance(threshold_raw, str)
        or not isinstance(limit_raw, str)
    ):
        raise VerificationError("language plan numeric bindings are invalid")
    if not fill_raw.startswith("N="):
        raise VerificationError("language fill binding has no N= prefix")
    try:
        fill_value = int(fill_raw[2:], 10)
        threshold = int(threshold_raw, 10)
        row_limit = int(limit_raw, 10)
    except ValueError as exc:
        raise VerificationError("language plan numeric binding is invalid") from exc
    if not 0 <= row_limit <= MAX_ROWS:
        raise VerificationError("language plan limit is outside the bound")
    direction_map = {"ascending": "asc", "descending": "desc"}
    direction = direction_map.get(bindings.get("order_direction"))
    if direction is None:
        raise VerificationError("language plan direction is invalid")
    stage_recipes = plan.get("stage_recipes")
    if (
        not isinstance(stage_recipes, Mapping)
        or stage_recipes.get("schema") != _LANGUAGE_STAGE_RECIPE_SCHEMA
        or stage_recipes.get("component_key") != "stage_order"
    ):
        raise VerificationError("language plan has no field-owned stage recipes")
    stage_component = next(
        (
            item.get("construction")
            for item in components
            if isinstance(item, Mapping) and item.get("key") == "stage_order"
        ),
        None,
    )
    if (
        not isinstance(stage_component, Mapping)
        or stage_recipes.get("component") != stage_component
    ):
        raise VerificationError("language recipe component provenance is invalid")
    recipe_catalog = stage_recipes.get("catalog")
    recipe_entries = stage_recipes.get("entries")
    arrangement = plan.get("stage_arrangement")
    expected_entry_keys = set(_EXPECTED_STAGE_RECIPE_KEYS)
    if arrangement == "recursive-5":
        expected_entry_keys.add(arrangement)
    if (
        not isinstance(recipe_catalog, Mapping)
        or not isinstance(recipe_entries, Mapping)
        or set(recipe_catalog) != set(_EXPECTED_STAGE_RECIPE_KEYS)
        or set(recipe_entries) != expected_entry_keys
    ):
        raise VerificationError("language plan recipe entries are invalid")
    arrangement = plan.get("stage_arrangement")
    recipe_entry = recipe_entries.get(arrangement)
    if (
        not isinstance(recipe_entry, Mapping)
        or not isinstance(recipe_entry.get("construction"), Mapping)
    ):
        raise VerificationError("language plan recipe entry is not field-backed")
    recipe = recipe_entry.get("recipe")
    if not isinstance(recipe, Mapping):
        raise VerificationError("language plan recipe is invalid")
    layers = recipe.get("layers")
    if not isinstance(layers, list) or not layers:
        raise VerificationError("language plan recipe has no layers")
    filled = {
        "op": "coalesce",
        "args": [
            {"op": "column", "name": "x"},
            {"op": "literal", "value": fill_value},
        ],
    }
    filter_after_fill = {
        "op": "filter",
        "predicate": {
            "op": "gt",
            "left": filled,
            "right": {"op": "literal", "value": threshold},
        },
    }
    filter_on_column = {
        "op": "filter",
        "predicate": {
            "op": "gt",
            "left": {"op": "column", "name": "x"},
            "right": {"op": "literal", "value": threshold},
        },
    }
    stage_templates: dict[str, dict[str, Any]] = {
        "filter_after_fill": filter_after_fill,
        "filter_on_column": filter_on_column,
        "project_filled": {"op": "project", "columns": {"x": filled}},
        "project_column": {
            "op": "project",
            "columns": {"x": {"op": "column", "name": "x"}},
        },
        "distinct": {"op": "distinct"},
        "order": {
            "op": "order",
            "expression": {"op": "column", "name": "x"},
            "direction": direction,
            "nulls": "first",
        },
        "limit": {"op": "limit", "count": row_limit},
    }
    current: dict[str, Any] = {"op": "source"}
    layer_count = 0
    for layer in layers:
        repeat = 1
        stage_names: Any = layer
        if isinstance(layer, Mapping):
            repeat = layer.get("repeat")
            if isinstance(repeat, str):
                try:
                    repeat = int(repeat, 10)
                except ValueError as exc:
                    raise VerificationError(
                        "language recipe repeat is not an integer"
                    ) from exc
            stage_names = layer.get("stages")
            if isinstance(repeat, bool) or not isinstance(repeat, int) or not 1 <= repeat <= 8:
                raise VerificationError("language recipe repeat is outside the bound")
        if not isinstance(stage_names, list) or not stage_names:
            raise VerificationError("language recipe layer is invalid")
        if any(
            not isinstance(name, str) or name not in stage_templates
            for name in stage_names
        ):
            raise VerificationError("language recipe names an unsupported stage")
        for _ in range(repeat):
            layer_count += 1
            if layer_count > 16:
                raise VerificationError("language recipe exceeds the nesting bound")
            current = {
                "op": "pipeline",
                "input": current,
                "stages": [stage_templates[name] for name in stage_names],
            }
    return current

def _pipeline_stage_signature(ast: Mapping[str, Any]) -> list[list[str]]:
    signatures: list[list[str]] = []
    current: Any = ast
    while isinstance(current, Mapping) and current.get("op") == "pipeline":
        stages = current.get("stages")
        if not isinstance(stages, list):
            return []
        signatures.append(
            [
                str(stage.get("op"))
                for stage in stages
                if isinstance(stage, Mapping)
            ]
        )
        current = current.get("input")
    return signatures if current == {"op": "source"} else []


def _coerce_language_ast(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        if set(value) == {"$role"}:
            raise VerificationError("language AST contains an ungrounded role")
        result = {str(key): _coerce_language_ast(item) for key, item in value.items()}
        if result.get("op") == "literal" and isinstance(result.get("value"), str):
            raw = result["value"]
            if raw.startswith("N="):
                raw = raw[2:]
            try:
                result["value"] = int(raw, 10)
            except ValueError as exc:
                raise VerificationError("language literal is not an integer") from exc
        if result.get("op") == "limit" and isinstance(result.get("count"), str):
            try:
                result["count"] = int(result["count"], 10)
            except ValueError as exc:
                raise VerificationError("language limit is not an integer") from exc
        if result.get("op") == "limit" and (
            isinstance(result.get("count"), bool)
            or not isinstance(result.get("count"), int)
            or not 0 <= result["count"] <= MAX_ROWS
        ):
            raise VerificationError("language limit is outside the bound")
        if result.get("op") == "order":
            direction_map = {"ascending": "asc", "descending": "desc"}
            direction = result.get("direction")
            if direction in direction_map:
                result["direction"] = direction_map[direction]
            if result.get("direction") not in {"asc", "desc"}:
                raise VerificationError("language order direction is invalid")
        return result
    if isinstance(value, list):
        return [_coerce_language_ast(item) for item in value]  # type: ignore[return-value]
    return value

def _sql_expr(expr: Mapping[str, Any], cols: list[str], values: tuple[int | None, ...]) -> int | None:
    if expr["op"] == "literal": return expr["value"]
    if expr["op"] == "column":
        if expr["name"] not in cols: raise VerificationError(f"SQL column missing: {expr['name']}")
        return values[cols.index(expr["name"])]
    for child in expr["args"]:
        value = _sql_expr(child, cols, values)
        if value is not None: return value
    return None


def _sql_pred(pred: Mapping[str, Any], cols: list[str], values: tuple[int | None, ...]) -> bool | None:
    if pred["op"] == "is_null": return _sql_expr(pred["expr"], cols, values) is None
    if pred["op"] == "is_not_null": return _sql_expr(pred["expr"], cols, values) is not None
    left, right = _sql_expr(pred["left"], cols, values), _sql_expr(pred["right"], cols, values)
    if left is None or right is None: return None
    return {"=": left == right, "!=": left != right, "<>": left != right,
            "<": left < right, ">": left > right, "<=": left <= right, ">=": left >= right}[pred["operator"]]


def execute_sql(sql: str, source: Mapping[str, Any]) -> dict[str, Any]:
    query = _SQL(sql).parse()
    source_table = table(source, "SQL input")

    def run(q: Mapping[str, Any], input_t: Mapping[str, Any]) -> tuple[list[str], list[tuple[tuple[int | None, ...], int]]]:
        source_spec = q["source"]
        if source_spec["kind"] == "readings":
            cols = list(input_t["columns"])
            rows = [(tuple(_value(r[c]) for c in cols), n) for n, r in enumerate(input_t["rows"])]
        else:
            cols, rows = run(source_spec["query"], input_t)
        if q["where"] is not None:
            rows = [(v, n) for v, n in rows if _sql_pred(q["where"], cols, v) is True]
        out_names = []
        for expr, alias in q["select"]:
            name = alias or (expr.get("name") if expr["op"] == "column" else "value")
            out_names.append(_identifier(name, "SQL output column"))
        if len(set(out_names)) != len(out_names):
            raise VerificationError("SQL output columns are not unique")
        selected = [
            (tuple(_sql_expr(expr, cols, values) for expr, _ in q["select"]), ordinal, values)
            for values, ordinal in rows
        ]
        if q["distinct"]:
            seen: set[tuple[int | None, ...]] = set()
            selected = [item for item in selected if not (item[0] in seen or seen.add(item[0]))]
        if q["order"] is not None:
            expr, direction, nulls = q["order"]
            null_first = nulls == "first"
            def order_value(item: tuple[tuple[int | None, ...], int, tuple[int | None, ...]]) -> int | None:
                # SQLite resolves ORDER BY aliases before source columns when
                # a selected alias has the same name.
                if expr.get("op") == "column" and expr.get("name") in out_names:
                    return _sql_expr(expr, out_names, item[0])
                try:
                    return _sql_expr(expr, cols, item[2])
                except VerificationError:
                    return _sql_expr(expr, out_names, item[0])
            def order_key(item: tuple[tuple[int | None, ...], int, tuple[int | None, ...]]) -> tuple[Any, ...]:
                value = order_value(item)
                null_rank = (0 if null_first else 1) if value is None else (1 if null_first else 0)
                value_key = 0 if value is None else (value if direction == "asc" else -value)
                return null_rank, value_key, item[1]
            selected.sort(key=order_key)
        if q["limit"] is not None:
            selected = selected[:q["limit"]]
        return out_names, [(values, ordinal) for values, ordinal, _ in selected]

    cols, rows = run(query, source_table)
    if len(set(cols)) != len(cols):
        raise VerificationError("SQL output columns are not unique")
    canonical_cols = sorted(cols)
    positions = [cols.index(name) for name in canonical_cols]
    return {
        "schema": TABLE_SCHEMA,
        "columns": canonical_cols,
        "rows": [
            {name: ({"kind": "null"} if values[pos] is None else {"kind": "integer", "value": values[pos]})
             for name, pos in zip(canonical_cols, positions)}
            for values, _ in rows
        ],
    }


# ---- Receipt checks -----------------------------------------------------------

def _walk(value: Any):
    if isinstance(value, Mapping):
        yield value
        for child in value.values(): yield from _walk(child)
    elif isinstance(value, list):
        for child in value: yield from _walk(child)


def _find_table(value: Any) -> dict[str, Any] | None:
    for obj in _walk(value):
        if set(obj) == {"schema", "columns", "rows"} and obj.get("schema") == TABLE_SCHEMA:
            try: return table(obj)
            except VerificationError: return None
    return None


def _has_status(value: Any, statuses: set[str]) -> bool:
    return any(isinstance(obj.get("status"), str) and obj["status"] in statuses for obj in _walk(value))


def _verify_oracle(raw: Any, sql: str, inp: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or raw.get("schema") not in {None, ORACLE_SCHEMA}:
        raise VerificationError(f"{label} oracle receipt schema invalid")
    required = {"status", "canonical_output", "output_digest", "input_digest"}
    if not required.issubset(raw):
        raise VerificationError(f"{label} oracle receipt keys incomplete")
    expected_input = table(inp, f"{label} input")
    if raw["input_digest"] != digest(expected_input):
        raise VerificationError(f"{label} oracle input digest mismatch")
    if "canonical_input" in raw and raw["canonical_input"] != expected_input:
        raise VerificationError(f"{label} oracle canonical input mismatch")
    if "input" in raw and raw["input"] != expected_input:
        raise VerificationError(f"{label} oracle input mismatch")
    if "sql" in raw and (raw["sql"] != sql or raw.get("sql_digest") != digest_text(sql)):
        raise VerificationError(f"{label} oracle SQL/digest mismatch")
    if "operation_id" in raw:
        opid = raw["operation_id"]
        if not isinstance(opid, str) or not opid or raw.get("operation_id_digest") != digest_text(opid):
            raise VerificationError(f"{label} operation digest mismatch")
        operation = raw.get("operation")
        if operation is not None and (not isinstance(operation, Mapping) or operation.get("id") != opid):
            raise VerificationError(f"{label} operation identity mismatch")
    status = raw["status"]
    if status not in {"supported", "resource-exhausted", "rejected", "observation-unavailable"}:
        raise VerificationError(f"{label} oracle status invalid")
    output = raw["canonical_output"]
    if output is None:
        raise VerificationError(f"{label} oracle has no canonical output")
    output = table(output, f"{label} oracle output")
    if raw.get("output_digest") != digest(output):
        raise VerificationError(f"{label} output digest mismatch")
    expected = execute_sql(sql, expected_input)
    if status != "supported" or output != expected:
        raise VerificationError(f"{label} oracle disagrees with independent SQL semantics")
    return expected


def _verify_lifecycle(row: Mapping[str, Any], expected: Mapping[str, Any], label: str) -> None:
    for key in ("authorization", "dispatch", "acknowledgment"):
        if not isinstance(row.get(key), Mapping):
            raise VerificationError(f"{label} missing {key}")
    if not (_has_status(row["authorization"], {"authorized", "supported"}) or "grant_id" in row["authorization"]):
        raise VerificationError(f"{label} authorization did not authorize")
    dispatch_objs = list(_walk(row["dispatch"]))
    if (
        not any("dispatch_id" in obj for obj in dispatch_objs)
        or not _has_status(row["dispatch"], {"dispatched", "waiting"})
    ):
        raise VerificationError(f"{label} dispatch did not dispatch")
    ack_objs = list(_walk(row["acknowledgment"]))
    if not any(obj.get("status") in {"succeeded", "supported"} for obj in ack_objs):
        raise VerificationError(f"{label} acknowledgment did not succeed")
    verified = [obj for obj in ack_objs if obj.get("observation_verified") is True]
    if not verified:
        raise VerificationError(f"{label} observation was not verified")
    observed = next((_find_table(obj.get("observation")) for obj in verified if obj.get("observation") is not None), None)
    if observed != expected:
        raise VerificationError(f"{label} acknowledged observation differs from oracle")
    proposal_ids = []
    for phase in ("authorization", "dispatch", "acknowledgment"):
        proposal_ids.extend(str(obj["proposal_id"]) for obj in _walk(row[phase])
                            if isinstance(obj.get("proposal_id"), str) and obj.get("proposal_id"))
    if proposal_ids and len(set(proposal_ids)) != 1:
        raise VerificationError(f"{label} lifecycle proposal identities disagree")
def _verify_sequence_route(
    field_route: Any,
    training: Any,
    candidate_pool: Any,
    selected_candidate: Any,
) -> None:
    if (
        not isinstance(field_route, Mapping)
        or not isinstance(training, list)
        or not isinstance(candidate_pool, Mapping)
    ):
        raise VerificationError("field route evidence is incomplete")
    request = field_route.get("request")
    response = field_route.get("response")
    reference = field_route.get("reference")
    query_request = field_route.get("query_request")
    query_response = field_route.get("query_response")
    if not all(
        isinstance(value, Mapping)
        for value in (request, response, reference, query_request, query_response)
    ):
        raise VerificationError("field route request/response evidence is incomplete")
    if set(request) != {
        "frontier_refs",
        "operation",
        "operation_id",
        "route_id",
        "scope",
        "support_roots",
        "target",
    }:
        raise VerificationError("field route request carries unexpected data")
    if request.get("operation") != "sequence-route":
        raise VerificationError("field route operation is invalid")
    if any(
        key in obj
        for obj in _walk(request)
        for key in (
            "ast",
            "canonical_output",
            "oracle",
            "selected_candidate",
            "sql",
            "support_counts",
            "supported_candidates",
        )
    ):
        raise VerificationError("field route request contains host routing data")
    frontier_refs = request.get("frontier_refs")
    if not isinstance(frontier_refs, list) or len(frontier_refs) != len(training):
        raise VerificationError("field route frontier coverage is incomplete")
    expected_frontier_refs = []
    expected_counts = {
        str(candidate_id): 0 for candidate_id in candidate_pool
    }
    for index, row in enumerate(training):
        if not isinstance(row, Mapping):
            raise VerificationError(f"training[{index}] is invalid for field routing")
        observed_frontier = row.get("observed_frontier")
        if not isinstance(observed_frontier, Mapping):
            raise VerificationError(f"training[{index}] has no observed frontier reference")
        expected_frontier_refs.append(observed_frontier)
        supported = row.get("supported_candidates")
        if (
            not isinstance(supported, list)
            or len(supported) != len(set(supported))
            or not supported
        ):
            raise VerificationError(f"training[{index}] supported candidates are invalid")
        for candidate_id in supported:
            if not isinstance(candidate_id, str) or candidate_id not in expected_counts:
                raise VerificationError(f"training[{index}] names an unknown candidate")
            expected_counts[candidate_id] += 1
    if frontier_refs != expected_frontier_refs:
        raise VerificationError("field route did not consume observed frontier references")
    result = response.get("result")
    if not isinstance(result, Mapping) or result.get("status") != "supported":
        raise VerificationError("field route did not return a supported result")
    if result.get("route") != reference:
        raise VerificationError("field route result/reference mismatch")
    query_result = query_response.get("result")
    record = query_result.get("record") if isinstance(query_result, Mapping) else None
    if not isinstance(record, Mapping) or not isinstance(record.get("payload"), Mapping):
        raise VerificationError("field route persisted record is missing")
    if any(record.get(key) != reference.get(key) for key in ("id", "kind", "content_version")):
        raise VerificationError("field route persisted reference mismatch")
    payload = record["payload"]
    if payload.get("schema") != "cassifi.sequence-route.v1":
        raise VerificationError("field route persisted payload schema is invalid")
    if payload.get("frontier_refs") != frontier_refs:
        raise VerificationError("field route persisted frontier coverage differs")
    if payload.get("candidate_ids") != sorted(expected_counts):
        raise VerificationError("field route candidate coverage differs")
    reported_counts = payload.get("support_counts")
    if reported_counts != expected_counts:
        raise VerificationError("field route support aggregation differs")
    if result.get("support_counts") != reported_counts:
        raise VerificationError("field route result aggregation differs")
    if result.get("selected_candidate") != payload.get("selected_candidate"):
        raise VerificationError("field route result selection differs")
    expected_selected = min(
        expected_counts,
        key=lambda candidate_id: (-expected_counts[candidate_id], candidate_id),
    )
    if payload.get("selected_candidate") != expected_selected:
        raise VerificationError("field route selection policy was not applied")
    if selected_candidate != expected_selected:
        raise VerificationError("held-out routing did not use field selection")
    if payload.get("selection_policy") != "max-supported-frontiers-then-lexical-id":
        raise VerificationError("field route selection policy is undeclared")
    if query_request.get("operation") != "query" or query_request.get("query") != {
        "kind": "record",
        "reference": reference,
    }:
        raise VerificationError("field route persistence query is invalid")



def _verify_question_choice(receipt: Mapping[str, Any]) -> None:
    choice = receipt.get("field_question_choice")
    if not isinstance(choice, Mapping):
        raise VerificationError("field question-choice receipt is missing")
    candidates = choice.get("question_candidates")
    selected = choice.get("selected_question_id")
    if (
        choice.get("mode") != "field-directed-v1"
        or not isinstance(selected, str)
        or not isinstance(candidates, list)
        or len(candidates) != 2
        or any(not isinstance(item, str) or not item for item in candidates)
        or len(set(candidates)) != 2
        or selected not in candidates
    ):
        raise VerificationError("field question-choice receipt is invalid")
    native = receipt.get("native_observation")
    if not isinstance(native, Mapping):
        raise VerificationError("native observation receipt is missing")
    if (
        native.get("selected_question_id") != selected
        or native.get("question_candidates") != candidates
    ):
        raise VerificationError("native observation is not bound to field question choice")
    prompt = native.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        raise VerificationError("native observation prompt is missing")
    if native.get("prompt_sha256") != digest_text(prompt):
        raise VerificationError("native observation prompt digest mismatch")
    trial = native.get("trial")
    if not isinstance(trial, Mapping):
        raise VerificationError("native observation trial is missing")
    if (
        trial.get("schema") != "cassi.qwen-native-instrument-result.v1"
        or trial.get("status") != "staged"
        or trial.get("mode") != "coupled"
    ):
        raise VerificationError("native observation trial is not coupled")
    identity = trial.get("identity")
    identity_sha256 = trial.get("identity_sha256")
    if (
        not isinstance(identity, Mapping)
        or not isinstance(identity_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", identity_sha256)
        or identity_sha256 != digest(identity)
        or identity.get("backend") != "gpu"
    ):
        raise VerificationError("native observation model identity is invalid")
    native_runtime_receipt = trial.get("receipt")
    output = trial.get("output")
    ownership = trial.get("ownership")
    if (
        not isinstance(native_runtime_receipt, Mapping)
        or native_runtime_receipt.get("schema") != "cassi.qi.native-runtime.v1"
        or native_runtime_receipt.get("verdict") != "PASS"
        or not isinstance(output, str)
        or not output
        or not isinstance(ownership, Mapping)
        or ownership.get("silent_native_fallback") is not False
        or not isinstance(ownership.get("qwen_forward_passes"), int)
        or ownership.get("qwen_forward_passes", 0) < 1
        or native.get("output_sha256") != digest_text(output)
    ):
        raise VerificationError("native observation runtime receipt is invalid")
    request = native.get("observation_request")
    response = native.get("observation_response")
    event_query_request = native.get("event_query_request")
    event_query_response = native.get("event_query_response")
    binding_query_request = native.get("binding_query_request")
    binding_query_response = native.get("binding_query_response")
    if not all(
        isinstance(value, Mapping)
        for value in (
            request,
            response,
            event_query_request,
            event_query_response,
            binding_query_request,
            binding_query_response,
        )
    ):
        raise VerificationError("native observation field evidence is incomplete")
    source = request.get("source")
    observations = request.get("observations")
    if (
        request.get("operation") != "observe"
        or not isinstance(source, Mapping)
        or source.get("identity_sha256") != identity_sha256
        or source.get("prompt_sha256") != digest_text(prompt)
        or source.get("output_sha256") != digest_text(output)
        or not isinstance(observations, list)
        or len(observations) != 1
        or not isinstance(observations[0], Mapping)
        or observations[0].get("value") != output
    ):
        raise VerificationError("native output was not delivered to field observe")
    observe_result = response.get("result")
    if (
        not isinstance(observe_result, Mapping)
        or observe_result.get("status") != "supported"
        or not isinstance(observe_result.get("event"), Mapping)
        or not isinstance(observe_result.get("bindings"), list)
        or len(observe_result["bindings"]) != 1
        or not isinstance(observe_result["bindings"][0], Mapping)
    ):
        raise VerificationError("native field observe response is invalid")
    event_ref = observe_result["event"]
    binding_ref = observe_result["bindings"][0]
    if (
        event_query_request.get("query")
        != {"kind": "record", "reference": event_ref}
        or binding_query_request.get("query")
        != {"kind": "record", "reference": binding_ref}
    ):
        raise VerificationError("native field query references are invalid")
    event_record = event_query_response.get("result", {}).get("record")
    binding_record = binding_query_response.get("result", {}).get("record")
    if (
        not isinstance(event_record, Mapping)
        or not isinstance(event_record.get("payload"), Mapping)
        or not isinstance(binding_record, Mapping)
        or not isinstance(binding_record.get("payload"), Mapping)
    ):
        raise VerificationError("native field records are missing")
    event_payload = event_record["payload"]
    binding_payload = binding_record["payload"]
    event_source = event_payload.get("source")
    if (
        event_record.get("id") != event_ref.get("id")
        or event_payload.get("observation_count") != 1
        or not isinstance(event_source, Mapping)
        or event_source.get("identity_sha256") != identity_sha256
        or binding_record.get("id") != binding_ref.get("id")
        or binding_payload.get("subject") != "qwen-native-questioner"
        or binding_payload.get("attribute") != "response"
        or binding_payload.get("value") != output
    ):
        raise VerificationError("native output and field binding disagree")
    evidence = receipt.get("native_evidence_update")
    if evidence is None:
        raise VerificationError("native evidence update receipt is missing")
    if not isinstance(evidence, Mapping):
        raise VerificationError("native evidence update receipt is invalid")
    update_request = evidence.get("request")
    update_response = evidence.get("response")
    representation_reference = evidence.get("representation_reference")
    query_request = evidence.get("query_request")
    query_response = evidence.get("query_response")
    if not all(
        isinstance(value, Mapping)
        for value in (
            update_request,
            update_response,
            representation_reference,
            query_request,
            query_response,
        )
    ):
        raise VerificationError("native evidence update is incomplete")
    if (
        update_request.get("operation") != "learn-predictive-state"
        or update_request.get("representation_id")
        != "predictive:native-question-evidence"
        or update_request.get("support_roots") != [identity_sha256]
        or not isinstance(update_request.get("signature"), Mapping)
        or update_request["signature"].get("prediction_semantics")
        != "constraint-set"
    ):
        raise VerificationError("native evidence update request is invalid")
    examples = update_request.get("examples")
    if not isinstance(examples, list) or len(examples) != 1:
        raise VerificationError("native evidence update example coverage is invalid")
    example = examples[0]
    if not isinstance(example, Mapping):
        raise VerificationError("native evidence update example is invalid")
    future = example.get("future")
    history = example.get("history")
    if (
        not isinstance(future, Mapping)
        or future.get("response") != output
        or future.get("output_sha256") != digest_text(output)
        or not isinstance(history, list)
        or len(history) != 1
        or not isinstance(history[0], Mapping)
        or history[0].get("selected_question_id") != selected
        or history[0].get("question_candidates") != candidates
        or not isinstance(example.get("future_ref"), Mapping)
        or example["future_ref"].get("id") != binding_ref.get("id")
        or example["future_ref"].get("kind") != binding_ref.get("kind")
        or not isinstance(example.get("history_ref"), Mapping)
        or example["history_ref"].get("id") != event_ref.get("id")
        or example["history_ref"].get("kind") != event_ref.get("kind")
    ):
        raise VerificationError("native observation was not used as evidence input")
    update_result = update_response.get("result")
    if (
        not isinstance(update_result, Mapping)
        or update_result.get("status") != "supported"
        or update_result.get("representation") != representation_reference
    ):
        raise VerificationError("native evidence update result is invalid")
    if query_request.get("query") != {
        "kind": "record",
        "reference": representation_reference,
    }:
        raise VerificationError("native evidence query reference is invalid")
    representation_record = query_response.get("result", {}).get("record")
    if (
        not isinstance(representation_record, Mapping)
        or representation_record.get("id") != representation_reference.get("id")
        or representation_record.get("kind") != "Program"
        or not isinstance(representation_record.get("payload"), Mapping)
        or representation_record["payload"].get("program_role")
        != "predictive-state"
        or identity_sha256
        not in representation_record.get("support_roots", [])
    ):
        raise VerificationError("native evidence program was not persisted")
    dependencies = representation_record.get("dependencies")
    if (
        not isinstance(dependencies, list)
        or not any(
            isinstance(reference, Mapping)
            and reference.get("id") == event_ref.get("id")
            and reference.get("kind") == event_ref.get("kind")
            for reference in dependencies
        )
        or not any(
            isinstance(reference, Mapping)
            and reference.get("id") == binding_ref.get("id")
            and reference.get("kind") == binding_ref.get("kind")
            for reference in dependencies
        )
    ):
        raise VerificationError("native evidence program lost observation dependencies")


def verify(receipt: Mapping[str, Any], mutate: bool = False) -> dict[str, Any]:
    if not isinstance(receipt, Mapping) or receipt.get("schema") != RUN_SCHEMA:
        raise VerificationError("run receipt schema invalid")
    required = {"schema", "teacher_route", "teacher_fixture", "field_state_before", "field_state_after", "training", "held_out", "status"}
    if not required.issubset(receipt):
        raise VerificationError("run receipt keys incomplete")
    if receipt["teacher_route"] != "typed-development-proposal":
        raise VerificationError("teacher_route is not the declared typed proposal route")
    fixture = receipt["teacher_fixture"]
    if not isinstance(fixture, Mapping) or not isinstance(fixture.get("source"), str) or not re.fullmatch(r"[0-9a-f]{64}", str(fixture.get("sha256", ""))):
        raise VerificationError("teacher fixture identity is not explicit")
    if receipt["status"] not in {"completed", "verified"}:
        raise VerificationError("run receipt status is not successful")
    for state_key in ("field_state_before", "field_state_after"):
        if not isinstance(receipt[state_key], Mapping):
            raise VerificationError(f"{state_key} is not a state receipt object")

    reopen = receipt.get("persistence_reopen")
    reopened = receipt.get("field_state_after_reopen")
    persistence = receipt.get("persistence_equal")
    if isinstance(reopen, Mapping):
        if reopened is None:
            reopened = reopen.get("reopened")
        if persistence is None:
            persistence = reopen.get("equal")
    if persistence is not True or reopened is None or receipt["field_state_after"] != reopened:
        raise VerificationError("state receipt changed across reopen")

    def make_input(case: Mapping[str, Any], fallback: Any = None) -> dict[str, Any]:
        value = case.get("input_table", case.get("input", fallback))
        if value is not None:
            return table(value, "case input")
        rows = case.get("input_rows")
        if not isinstance(rows, list):
            raise VerificationError("case has no canonical input table")
        cells = []
        for raw in rows:
            if raw is None:
                cell = {"kind": "null"}
            elif isinstance(raw, bool) or not isinstance(raw, int) or not -MAX_INTEGER <= raw <= MAX_INTEGER:
                raise VerificationError("case input row is not integer/null")
            else:
                cell = {"kind": "integer", "value": int(raw)}
            cells.append({"x": cell})
        return table({"schema": TABLE_SCHEMA, "columns": ["x"], "rows": cells}, "case input")


    def verify_language_prediction(
        prediction: Any,
        case: Mapping[str, Any],
        *,
        label: str,
        construction_id: str,
        selected_candidate: str,
    ) -> None:
        if not isinstance(prediction, Mapping):
            raise VerificationError(f"{label} prediction is missing")
        text = case.get("text")
        sql = case.get("sql")
        if not isinstance(text, str) or not isinstance(sql, str):
            raise VerificationError(f"{label} case text or SQL is invalid")
        inp = make_input(case)
        expected = _verify_oracle(prediction.get("oracle"), sql, inp, label)
        interpret_request = prediction.get("interpret_request")
        interpret_result = prediction.get("interpret_result")
        interpretation = prediction.get("interpretation")
        mechanism_request = prediction.get("mechanism_request")
        mechanism_result = prediction.get("mechanism_result")
        recipe_interpret_request = prediction.get("recipe_interpret_request")
        recipe_interpret_result = prediction.get("recipe_interpret_result")
        recipe_interpretation = prediction.get("recipe_interpretation")
        if (
            not isinstance(interpret_request, Mapping)
            or interpret_request.get("operation") != "interpret"
            or interpret_request.get("text") != text
            or any(key in interpret_request for key in ("ast", "query_ast", "sql"))
            or not isinstance(interpret_result, Mapping)
            or not isinstance(interpretation, Mapping)
            or not isinstance(recipe_interpret_request, Mapping)
            or recipe_interpret_request.get("operation") != "interpret"
            or not isinstance(recipe_interpret_result, Mapping)
            or not isinstance(recipe_interpretation, Mapping)
            or not isinstance(mechanism_request, Mapping)
            or not isinstance(mechanism_result, Mapping)
        ):
            raise VerificationError(f"{label} interpretation route is invalid")
        content = interpretation.get("content")
        arrangement = (
            content.get("stage_arrangement")
            if isinstance(content, Mapping)
            else None
        )
        is_parametric = arrangement == "recursive-5"
        recipe_request_context = recipe_interpret_request.get("permitted_context")
        stage_recipes = content.get("stage_recipes") if isinstance(content, Mapping) else None
        entries = stage_recipes.get("entries") if isinstance(stage_recipes, Mapping) else None
        recipe_entry = entries.get(arrangement) if isinstance(entries, Mapping) else None
        if is_parametric:
            parametric = (
                stage_recipes.get("parametric")
                if isinstance(stage_recipes, Mapping)
                else None
            )
            recipe_entry = (
                {
                    "construction": parametric.get("construction"),
                    "recipe": None,
                }
                if isinstance(parametric, Mapping)
                else None
            )
            expected_recipe_text = "mode recursive depth 5"
            expected_recipe_context = {
                "component_scope": "recipe-only",
                "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
            }
            expected_recipe_key = _LANGUAGE_PARAMETRIC_RECIPE_KEY
        else:
            expected_recipe_text = f"mode {arrangement}"
            expected_recipe_context = {
                "component_scope": "recipe-only",
                "recipe_key": arrangement,
            }
            expected_recipe_key = arrangement
        recipe_construction = (
            recipe_entry.get("construction")
            if isinstance(recipe_entry, Mapping)
            else None
        )
        recipe_outcome = recipe_interpret_result.get("result", {})
        recipe_content = recipe_interpretation.get("content")
        recipe_bindings = recipe_interpretation.get("bindings")
        if is_parametric:
            parametric_reference = (
                stage_recipes.get("parametric", {}).get("construction")
                if isinstance(stage_recipes, Mapping)
                and isinstance(stage_recipes.get("parametric"), Mapping)
                else None
            )
            if (
                not isinstance(parametric_reference, Mapping)
                or not isinstance(recipe_interpretation.get("construction"), Mapping)
                or not str(recipe_interpretation["construction"].get("id", "")).startswith(
                    "construction:language:recipe:"
                )
            ):
                raise VerificationError(f"{label} parametric recipe reference is invalid")
            recipe_construction = recipe_interpretation["construction"]
            recipe_entry["construction"] = recipe_construction
        if not isinstance(recipe_bindings, Mapping):
            recipe_bindings = {}

        def materialize(value: Any) -> Any:
            if isinstance(value, Mapping):
                if set(value) == {"$role"}:
                    role = value.get("$role")
                    if not isinstance(role, str) or role not in recipe_bindings:
                        raise VerificationError(f"{label} recipe role is unbound")
                    return recipe_bindings[role]
                return {key: materialize(item) for key, item in value.items()}
            if isinstance(value, list):
                return [materialize(item) for item in value]
            return value

        if is_parametric and isinstance(recipe_entry, Mapping):
            recipe_entry["recipe"] = materialize(_LANGUAGE_PARAMETRIC_RECIPE_TEMPLATE)
        if (
            not isinstance(content, Mapping)
            or "query_ast" in content
            or "sql" in content
            or interpretation.get("construction_id") != construction_id
            or not isinstance(arrangement, str)
            or recipe_interpret_request.get("text") != expected_recipe_text
            or recipe_request_context != expected_recipe_context
            or any(
                key in recipe_interpret_request for key in ("ast", "query_ast", "sql")
            )
            or not isinstance(recipe_outcome, Mapping)
            or recipe_outcome.get("status") != "supported"
            or not isinstance(recipe_entry, Mapping)
            or not isinstance(recipe_content, Mapping)
            or recipe_content.get("component_kind") != "query-recipe"
            or recipe_content.get("recipe_key") != expected_recipe_key
            or recipe_content.get("recipe_schema") != _LANGUAGE_STAGE_RECIPE_SCHEMA
            or (
                is_parametric
                and recipe_content.get("recipe_family")
                != _LANGUAGE_PARAMETRIC_RECIPE_FAMILY
            )
            or recipe_content.get("recipe") != recipe_entry.get("recipe")
            or not isinstance(recipe_construction, Mapping)
            or recipe_interpretation.get("construction_id")
            != recipe_construction.get("id")
            or recipe_interpretation.get("construction") != recipe_construction
        ):
            raise VerificationError(f"{label} interpretation is not field-grounded")
        compile_content = content
        if is_parametric:
            compile_content = dict(content)
            compile_stage_recipes = dict(stage_recipes)
            compile_entries = dict(entries) if isinstance(entries, Mapping) else {}
            compile_entries[arrangement] = recipe_entry
            compile_stage_recipes["entries"] = compile_entries
            compile_content["stage_recipes"] = compile_stage_recipes
        expected_ast = _sql_to_sequence_ast(_SQL(sql).parse())
        compiled = sequence_ast(_compile_language_plan(compile_content))
        reported_ast = sequence_ast(prediction.get("query_ast"))
        if compiled != expected_ast or reported_ast != expected_ast:
            raise VerificationError(f"{label} compiled AST differs from SQL semantics")
        action = mechanism_request.get("action")
        if (
            mechanism_request.get("operation") != "mechanism-step"
            or mechanism_request.get("mechanism_id") != selected_candidate
            or not isinstance(action, Mapping)
            or table(action.get("table"), f"{label} field input") != inp
            or sequence_ast(action.get("query_ast")) != expected_ast
        ):
            raise VerificationError(f"{label} mechanism call is not bound to interpretation")
        outcome = mechanism_result.get("result", {}).get("outcome")
        if not isinstance(outcome, Mapping):
            raise VerificationError(f"{label} mechanism result has no outcome")
        prediction_table = table(prediction.get("prediction"), f"{label} prediction")
        if (
            prediction_table != expected
            or prediction.get("prediction_digest") != digest(prediction_table)
            or prediction.get("oracle_digest") != digest(expected)
            or prediction.get("matches_oracle") is not True
        ):
            raise VerificationError(f"{label} prediction does not match its oracle")
    training = receipt["training"]
    if not isinstance(training, list) or not training:
        raise VerificationError("training is empty or invalid")
    top_frontiers = receipt.get("frontier_receipts")
    top_acks = receipt.get("ack_receipts")
    if isinstance(top_frontiers, list) and len(top_frontiers) != len(training):
        raise VerificationError("frontier receipt count does not match training count")
    if isinstance(top_acks, list) and len(top_acks) != len(training):
        raise VerificationError("acknowledgment receipt count does not match training count")
    for index, raw in enumerate(training):
        if not isinstance(raw, Mapping):
            raise VerificationError(f"training[{index}] is not an object")
        case = raw.get("case") if isinstance(raw.get("case"), Mapping) else raw
        sql = case.get("sql")
        if not isinstance(sql, str):
            raise VerificationError(f"training[{index}] has no SQL")
        inp = make_input(raw, case.get("input_table"))
        oracle = _verify_oracle(raw.get("oracle"), sql, inp, f"training[{index}]")
        if all(key in raw for key in ("authorization", "dispatch", "acknowledgment")):
            lifecycle = dict(raw)
        elif isinstance(top_acks, list) and index < len(top_acks):
            ack = top_acks[index]
            if not isinstance(ack, Mapping):
                raise VerificationError(f"training[{index}] lifecycle is invalid")
            lifecycle = {**raw, **dict(ack)}
            if "authorization" not in lifecycle and isinstance(
                lifecycle.get("authorized"), Mapping
            ):
                lifecycle["authorization"] = lifecycle["authorized"]
        else:
            raise VerificationError(f"training[{index}] lifecycle is missing")
        ack_request = None
        for candidate in (raw, lifecycle):
            ack_request = next((candidate.get(key) for key in ("acknowledgment_request", "ack_request", "acknowledgment_call")
                                if isinstance(candidate.get(key), Mapping)), None)
            if ack_request is not None:
                break
        if ack_request is not None:
            lifecycle["acknowledgment"] = {
                "response": lifecycle["acknowledgment"],
                "request": ack_request,
            }
        _verify_lifecycle(lifecycle, oracle, f"training[{index}]")
        frontier = raw.get("field_frontier", raw.get("frontier_response"))
        if frontier is None and isinstance(top_frontiers, list) and index < len(top_frontiers):
            frontier = top_frontiers[index]
        if frontier is None:
            frontier = raw.get("observed_frontier")
        if not isinstance(frontier, Mapping):
            raise VerificationError(f"training[{index}] frontier is missing")
        if _find_table(frontier) is None:
            raise VerificationError(f"training[{index}] frontier has no canonical table")
        if isinstance(raw.get("supported_candidates"), list) and not raw["supported_candidates"]:
            raise VerificationError(f"training[{index}] has no supported candidate")
        programs = raw.get("candidate_programs")
        if isinstance(programs, Mapping):
            support_objects = list(_walk(raw.get("support_query", {})))
            candidate_rows = [
                obj
                for obj in support_objects
                if isinstance(obj.get("candidate_id"), str) and "prediction" in obj
            ]
            frontier_request = raw.get("frontier_request")
            frontier_query_ast = (
                frontier_request.get("query_ast")
                if isinstance(frontier_request, Mapping)
                else None
            )
            for candidate_id, program in programs.items():
                if not isinstance(candidate_id, str):
                    raise VerificationError(f"training[{index}] candidate identity is invalid")
                if not isinstance(program, Mapping) or program.get("program_kind") != "sequence":
                    raise VerificationError(f"training[{index}] candidate program is not sequence")
                predicted = execute_sequence(program, inp, frontier_query_ast)
                for candidate in candidate_rows:
                    if candidate["candidate_id"] == candidate_id and candidate.get("prediction") is not None:
                        candidate_prediction = table(candidate["prediction"], "candidate prediction")
                        if candidate_prediction != predicted:
                            raise VerificationError(f"training[{index}] candidate AST prediction mismatch")
        proposals = [
            obj for obj in _walk(frontier)
            if isinstance(obj.get("proposal_id"), str)
            and isinstance(obj.get("action"), Mapping)
            and isinstance(obj["action"].get("question"), Mapping)
            and obj["action"]["question"].get("kind") == "sequence-table"
        ]
        if not proposals:
            raise VerificationError(f"training[{index}] frontier has no sequence-table proposal")
        frontier_request = raw.get("frontier_request")
        if not isinstance(frontier_request, Mapping):
            raise VerificationError(f"training[{index}] frontier request is missing")
        if frontier_request.get("question_choice") == "field-directed-v1":
            frontier_result = frontier.get("result")
            question_choice = (
                frontier_result.get("question_choice")
                if isinstance(frontier_result, Mapping)
                else None
            )
            question_candidates = (
                frontier_result.get("question_candidates")
                if isinstance(frontier_result, Mapping)
                else None
            )
            if (
                not isinstance(frontier_result, Mapping)
                or not isinstance(question_choice, Mapping)
                or question_choice.get("mode") != "field-directed-v1"
                or not isinstance(question_candidates, list)
                or len(question_candidates) != 2
                or any(not isinstance(item, str) or not item for item in question_candidates)
                or len(set(question_candidates)) != 2
                or question_choice.get("selected_question_id")
                != frontier_result.get("selected_question_id")
            ):
                raise VerificationError(
                    f"training[{index}] field-directed question choice is malformed"
                )
            selected_question_id = question_choice.get("selected_question_id")
            selected_proposals = [
                proposal for proposal in proposals
                if proposal["action"].get("question_id") == selected_question_id
                and proposal["action"]["question"].get("question_role") == "separating"
            ]
            if (
                selected_question_id not in question_candidates
                or len(selected_proposals) != 1
            ):
                raise VerificationError(
                    f"training[{index}] field did not select the separating question"
                )
        frontier_ids = {obj["proposal_id"] for obj in proposals}
        lifecycle_ids = {
            obj["proposal_id"] for phase in ("authorization", "dispatch", "acknowledgment")
            for obj in _walk(lifecycle[phase])
            if isinstance(obj.get("proposal_id"), str)
        }
        if not frontier_ids.intersection(lifecycle_ids):
            raise VerificationError(f"training[{index}] lifecycle is not bound to frontier proposal")
    if "field_question_choice" in receipt or "native_observation" in receipt:
        _verify_question_choice(receipt)

    held_raw = receipt["held_out"]
    candidate_pool = receipt.get("candidate_programs")
    selected_candidate = (
        held_raw.get("selected_candidate")
        if isinstance(held_raw, Mapping)
        else None
    )
    _verify_sequence_route(
        receipt.get("field_route"),
        training,
        candidate_pool,
        selected_candidate,
    )
    if isinstance(held_raw, list):
        held_rows = held_raw
    elif isinstance(held_raw, Mapping):
        cases = held_raw.get("cases")
        predictions = held_raw.get("predictions")
        oracles = held_raw.get("oracle")
        if not isinstance(cases, list) or not isinstance(predictions, list) or not isinstance(oracles, list):
            raise VerificationError("held_out mapping is incomplete")
        pred_by_id = {row.get("case_id"): row for row in predictions if isinstance(row, Mapping)}
        oracle_by_id = {row.get("case_id"): row.get("oracle") for row in oracles if isinstance(row, Mapping)}
        if len(pred_by_id) != len(predictions) or len(oracle_by_id) != len(oracles):
            raise VerificationError("held_out identities are duplicated or invalid")
        held_rows = []
        for case in cases:
            if not isinstance(case, Mapping) or case.get("case_id") not in pred_by_id or case.get("case_id") not in oracle_by_id:
                raise VerificationError("held_out case/prediction/oracle identities do not align")
            pred = pred_by_id[case["case_id"]]
            held_rows.append({
                "name": case.get("case_id"), "sql": case.get("sql"),
                "input": make_input(case), "oracle": oracle_by_id[case["case_id"]],
                "field_prediction": pred.get("prediction"),
                "field_call": {"request": pred.get("field_request"), "result": pred.get("field_result")},
                "prediction_digest": pred.get("prediction_digest"),
                "oracle_digest": pred.get("oracle_digest"),
                "matches_oracle": pred.get("matches_oracle"),
            })
    else:
        raise VerificationError("held_out is invalid")
    if not held_rows:
        raise VerificationError("held_out is empty")
    for index, raw in enumerate(held_rows):
        if not isinstance(raw, Mapping):
            raise VerificationError(f"held_out[{index}] is not an object")
        for key in ("sql", "input", "oracle", "field_prediction", "field_call"):
            if key not in raw:
                raise VerificationError(f"held_out[{index}] missing {key}")
        sql = raw["sql"]
        if not isinstance(sql, str):
            raise VerificationError(f"held_out[{index}] SQL is invalid")
        inp = table(raw["input"], f"held_out[{index}] input")
        expected = _verify_oracle(raw["oracle"], sql, inp, f"held_out[{index}]")
        prediction = raw["field_prediction"]
        if isinstance(prediction, Mapping) and set(prediction) != {"schema", "columns", "rows"}:
            prediction = prediction.get("table", prediction)
        prediction_table = table(prediction, f"held_out[{index}] field prediction")
        if prediction_table != expected:
            raise VerificationError(f"held_out[{index}] field prediction mismatch")
        if raw.get("prediction_digest") is not None and raw["prediction_digest"] != digest(prediction_table):
            raise VerificationError(f"held_out[{index}] prediction digest mismatch")
        if raw.get("oracle_digest") is not None and raw["oracle_digest"] != digest(expected):
            raise VerificationError(f"held_out[{index}] oracle digest mismatch")
        if raw.get("matches_oracle") is not None and raw["matches_oracle"] is not True:
            raise VerificationError(f"held_out[{index}] declared mismatch")
        field_call = raw["field_call"]
        if not isinstance(field_call, Mapping):
            raise VerificationError(f"held_out[{index}] field call invalid")
        forbidden = [
            key
            for obj in _walk(field_call)
            for key in obj
            if key in {"sql", "oracle", "canonical_output", "output_digest"}
        ]
        if forbidden:
            raise VerificationError(f"held_out[{index}] field call contains teacher/oracle input")
        field_request = field_call.get("request")
        if isinstance(candidate_pool, Mapping) and isinstance(selected_candidate, str):
            if not isinstance(field_request, Mapping):
                raise VerificationError(f"held_out[{index}] field request is missing")
            if field_request.get("mechanism_id") != selected_candidate:
                raise VerificationError(f"held_out[{index}] field used an unselected candidate")
            action = field_request.get("action")
            if not isinstance(action, Mapping) or not isinstance(action.get("query_ast"), Mapping):
                raise VerificationError(f"held_out[{index}] typed query AST is missing")
            query_ast = action["query_ast"]
            selected_program = candidate_pool.get(selected_candidate)
            if not isinstance(selected_program, Mapping):
                raise VerificationError(f"held_out[{index}] selected program is missing")
            predicted_by_program = execute_sequence(selected_program, inp, query_ast)
            if predicted_by_program != prediction_table:
                raise VerificationError(f"held_out[{index}] selected program prediction mismatch")
            for candidate_id, candidate_program in candidate_pool.items():
                if not isinstance(candidate_id, str) or not isinstance(candidate_program, Mapping):
                    raise VerificationError("candidate pool identity or program is invalid")
                normalized_program = sequence_program(candidate_program)
                body = normalized_program["body"]
                if "ast_parameter" not in body and body["ast"] == query_ast:
                    raise VerificationError(f"held_out[{index}] candidate pool contains held-out AST")
    post_reopen_raw = receipt.get("post_reopen_behavior")
    if post_reopen_raw is not None:
        if not isinstance(post_reopen_raw, Mapping):
            raise VerificationError("post_reopen_behavior is invalid")
        post_case = post_reopen_raw.get("case")
        post_prediction = post_reopen_raw.get("prediction")
        if not isinstance(post_case, Mapping) or not isinstance(post_prediction, Mapping):
            raise VerificationError("post_reopen_behavior case/prediction is missing")
        case_id = post_case.get("case_id")
        held_ids = {
            str(case.get("case_id"))
            for case in (
                held_raw.get("cases", [])
                if isinstance(held_raw, Mapping)
                else held_rows
            )
            if isinstance(case, Mapping)
        }
        if not isinstance(case_id, str) or not case_id or case_id in held_ids:
            raise VerificationError("post-reopen case identity is invalid or duplicated")
        sql = post_case.get("sql")
        if not isinstance(sql, str):
            raise VerificationError("post-reopen case SQL is invalid")
        post_input = make_input(post_case)
        expected = _verify_oracle(
            post_prediction.get("oracle"),
            sql,
            post_input,
            "post_reopen_behavior",
        )
        prediction = post_prediction.get("prediction")
        if isinstance(prediction, Mapping) and set(prediction) != {"schema", "columns", "rows"}:
            prediction = prediction.get("table", prediction)
        prediction_table = table(prediction, "post-reopen field prediction")
        if prediction_table != expected:
            raise VerificationError("post-reopen field prediction mismatch")
        if (
            post_prediction.get("prediction_digest") is not None
            and post_prediction["prediction_digest"] != digest(prediction_table)
        ):
            raise VerificationError("post-reopen prediction digest mismatch")
        if (
            post_prediction.get("oracle_digest") is not None
            and post_prediction["oracle_digest"] != digest(expected)
        ):
            raise VerificationError("post-reopen oracle digest mismatch")
        if post_prediction.get("matches_oracle") is not True:
            raise VerificationError("post-reopen declared mismatch")
        post_field_call = {
            "request": post_prediction.get("field_request"),
            "result": post_prediction.get("field_result"),
        }
        forbidden = [
            key
            for obj in _walk(post_field_call)
            for key in obj
            if key in {"sql", "oracle", "canonical_output", "output_digest"}
        ]
        if forbidden:
            raise VerificationError("post-reopen field call contains teacher/oracle input")
        post_field_request = post_field_call["request"]
        if not isinstance(post_field_request, Mapping):
            raise VerificationError("post-reopen field request is missing")
        if (
            not isinstance(candidate_pool, Mapping)
            or not isinstance(selected_candidate, str)
            or post_field_request.get("mechanism_id") != selected_candidate
        ):
            raise VerificationError("post-reopen field used an unselected candidate")
        action = post_field_request.get("action")
        if not isinstance(action, Mapping) or not isinstance(action.get("query_ast"), Mapping):
            raise VerificationError("post-reopen typed query AST is missing")
        query_ast = action["query_ast"]
        selected_program = candidate_pool.get(selected_candidate)
        if not isinstance(selected_program, Mapping):
            raise VerificationError("post-reopen selected program is missing")
        predicted_by_program = execute_sequence(selected_program, post_input, query_ast)
        if predicted_by_program != prediction_table:
            raise VerificationError("post-reopen selected program prediction mismatch")
        for candidate_id, candidate_program in candidate_pool.items():
            if not isinstance(candidate_id, str) or not isinstance(candidate_program, Mapping):
                raise VerificationError("post-reopen candidate pool identity or program is invalid")
            normalized_program = sequence_program(candidate_program)
            body = normalized_program["body"]
            if "ast_parameter" not in body and body["ast"] == query_ast:
                raise VerificationError("post-reopen candidate pool contains its AST")
        state_before = post_reopen_raw.get("state_before")
        state_after = post_reopen_raw.get("state_after")
        if not isinstance(state_before, Mapping) or not isinstance(state_after, Mapping):
            raise VerificationError("post-reopen state receipts are missing")
        initial_reopen = receipt.get("persistence_reopen")
        if (
            not isinstance(initial_reopen, Mapping)
            or initial_reopen.get("equal") is not True
            or state_before != initial_reopen.get("reopened")
        ):
            raise VerificationError("post-reopen behavior did not start from persisted state")
        final_reopen = post_reopen_raw.get("persistence_reopen")
        if (
            not isinstance(final_reopen, Mapping)
            or final_reopen.get("equal") is not True
            or final_reopen.get("reopened") != state_after
        ):
            raise VerificationError("post-reopen behavior state did not persist")
        reported = receipt.get("invariants")
        if isinstance(reported, Mapping):
            for key in (
                "post_reopen_behavior_match",
                "post_reopen_persistence_equal",
                "post_reopen_field_call_contains_no_sql",
            ):
                if key in reported and reported[key] is not True:
                    raise VerificationError(f"receipt invariant {key} is false")
    language_raw = receipt.get("language_to_program")
    if not isinstance(language_raw, Mapping):
        raise VerificationError("language-to-program evidence is missing")
    language_fixture = language_raw.get("fixture")
    language_learning = language_raw.get("construction_learning")
    language_prediction = language_raw.get("prediction")
    if (
        not isinstance(language_fixture, Mapping)
        or not isinstance(language_learning, Mapping)
        or not isinstance(language_prediction, Mapping)
    ):
        raise VerificationError("language-to-program evidence is incomplete")
    language_case = language_fixture.get("case")
    if not isinstance(language_case, Mapping):
        raise VerificationError("language-to-program case is missing")
    language_text = language_case.get("text")
    language_sql = language_case.get("sql")
    if not isinstance(language_text, str) or not isinstance(language_sql, str):
        raise VerificationError("language-to-program case text or SQL is invalid")
    learning_request = language_learning.get("request")
    learning_result = language_learning.get("result")
    if (
        not isinstance(learning_request, Mapping)
        or learning_request.get("operation") != "learn-construction"
        or not isinstance(learning_result, Mapping)
    ):
        raise VerificationError("language construction learning route is invalid")
    learned_result = learning_result.get("result")
    if not isinstance(learned_result, Mapping) or learned_result.get("status") != "supported":
        raise VerificationError("language construction was not supported")
    examples = learning_request.get("examples")
    if not isinstance(examples, list) or not examples:
        raise VerificationError("language construction has no teaching examples")
    if language_fixture.get("examples") != examples:
        raise VerificationError("language fixture does not retain teacher examples")
    construction_reference = language_raw.get("construction_reference")
    if (
        not isinstance(construction_reference, Mapping)
        or learned_result.get("construction") != construction_reference
    ):
        raise VerificationError("language construction reference is not field-backed")
    component_acquisition = language_raw.get("component_acquisition")
    if not isinstance(component_acquisition, Mapping):
        raise VerificationError("language component acquisition is missing")
    component_rows = component_acquisition.get("components")
    component_references = component_acquisition.get("references")
    expected_component_ids = {
        "fill_value": "construction:language:component:fill-value",
        "threshold_filter": "construction:language:component:threshold-filter",
        "distinct": "construction:language:component:distinct",
        "order_limit": "construction:language:component:order-limit",
        "stage_order": "construction:language:component:stage-order",
    }
    if (
        not isinstance(component_rows, list)
        or len(component_rows) != len(expected_component_ids)
        or not isinstance(component_references, Mapping)
        or set(component_references) != set(expected_component_ids)
    ):
        raise VerificationError("language component acquisition shape is invalid")
    component_refs_in_order: list[Mapping[str, Any]] = []
    for row, (component_key, expected_id) in zip(
        component_rows, expected_component_ids.items()
    ):
        if not isinstance(row, Mapping):
            raise VerificationError("language component receipt row is invalid")
        request = row.get("request")
        result = row.get("result")
        payload = result.get("result") if isinstance(result, Mapping) else None
        if (
            not isinstance(request, Mapping)
            or request.get("operation") != "learn-construction"
            or request.get("construction_id") != expected_id
            or request.get("guards")
            != {
                "component_scope": "component-only",
                "component_key": component_key,
            }
            or not isinstance(result, Mapping)
            or not isinstance(payload, Mapping)
            or payload.get("status") != "supported"
            or not isinstance(payload.get("construction"), Mapping)
            or payload.get("construction") != component_references.get(component_key)
        ):
            raise VerificationError(f"language component {component_key} is invalid")
        component_refs_in_order.append(payload["construction"])
    recipe_acquisition = language_raw.get("recipe_acquisition")
    if not isinstance(recipe_acquisition, Mapping):
        raise VerificationError("language recipe acquisition is missing")
    recipe_rows = recipe_acquisition.get("recipes")
    recipe_references = recipe_acquisition.get("references")
    expected_recipe_ids = {
        key: f"construction:language:recipe:{key}"
        for key in _EXPECTED_STAGE_RECIPE_KEYS
    }
    if (
        not isinstance(recipe_rows, list)
        or len(recipe_rows) != len(expected_recipe_ids)
        or not isinstance(recipe_references, Mapping)
        or set(recipe_references) != set(expected_recipe_ids)
    ):
        raise VerificationError("language recipe acquisition shape is invalid")
    recipe_refs_in_order: list[Mapping[str, Any]] = []
    for row, (recipe_key, expected_id) in zip(
        recipe_rows, expected_recipe_ids.items()
    ):
        if not isinstance(row, Mapping):
            raise VerificationError("language recipe receipt row is invalid")
        request = row.get("request")
        result = row.get("result")
        payload = result.get("result") if isinstance(result, Mapping) else None
        meaning = request.get("meaning") if isinstance(request, Mapping) else None
        if (
            not isinstance(request, Mapping)
            or request.get("operation") != "learn-construction"
            or request.get("construction_id") != expected_id
            or request.get("examples")
            != [
                {
                    "text": f"mode {recipe_key}",
                    "bindings": {"stage_arrangement": recipe_key},
                },
                {
                    "text": f"mode {recipe_key}",
                    "bindings": {"stage_arrangement": recipe_key},
                },
            ]
            or request.get("guards")
            != {
                "component_scope": "recipe-only",
                "recipe_key": recipe_key,
            }
            or not isinstance(meaning, Mapping)
            or meaning.get("component_kind") != "query-recipe"
            or meaning.get("role") != "stage_recipe"
            or meaning.get("recipe_schema") != _LANGUAGE_STAGE_RECIPE_SCHEMA
            or meaning.get("recipe_key") != recipe_key
            or meaning.get("stage_component_key") != "stage_order"
            or not isinstance(meaning.get("recipe"), Mapping)
            or not isinstance(result, Mapping)
            or not isinstance(payload, Mapping)
            or payload.get("status") != "supported"
            or not isinstance(payload.get("construction"), Mapping)
            or payload.get("construction") != recipe_references.get(recipe_key)
        ):
            raise VerificationError(f"language recipe {recipe_key} is invalid")
        recipe_refs_in_order.append(payload["construction"])
    parametric_acquisition = language_raw.get("parametric_recipe_acquisition")
    if not isinstance(parametric_acquisition, Mapping):
        raise VerificationError("parametric recipe acquisition is missing")
    parametric_recipe = parametric_acquisition.get("recipe")
    parametric_examples = parametric_acquisition.get("examples")
    parametric_request = parametric_acquisition.get("request")
    parametric_result = parametric_acquisition.get("result")
    parametric_reference = parametric_acquisition.get("reference")
    expected_parametric_examples = [
        {
            "text": "mode recursive depth 2",
            "bindings": {
                "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
                "repeat_count": "2",
            },
        },
        {
            "text": "mode recursive depth 3",
            "bindings": {
                "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
                "repeat_count": "3",
            },
        },
    ]
    parametric_payload = (
        parametric_result.get("result")
        if isinstance(parametric_result, Mapping)
        else None
    )
    parametric_meaning = (
        parametric_request.get("meaning")
        if isinstance(parametric_request, Mapping)
        else None
    )
    if (
        parametric_recipe
        != {
            "key": _LANGUAGE_PARAMETRIC_RECIPE_KEY,
            "construction_id": (
                "construction:language:recipe:"
                f"{_LANGUAGE_PARAMETRIC_RECIPE_KEY}"
            ),
            "examples": expected_parametric_examples,
            "meaning": parametric_meaning,
        }
        or parametric_examples != expected_parametric_examples
        or not isinstance(parametric_request, Mapping)
        or parametric_request.get("operation") != "learn-construction"
        or parametric_request.get("construction_id")
        != (
            "construction:language:recipe:"
            f"{_LANGUAGE_PARAMETRIC_RECIPE_KEY}"
        )
        or parametric_request.get("examples") != expected_parametric_examples
        or parametric_request.get("guards")
        != {
            "component_scope": "recipe-only",
            "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
        }
        or not isinstance(parametric_meaning, Mapping)
        or parametric_meaning.get("component_kind") != "query-recipe"
        or parametric_meaning.get("role") != "stage_recipe"
        or parametric_meaning.get("recipe_schema") != _LANGUAGE_STAGE_RECIPE_SCHEMA
        or parametric_meaning.get("recipe_key") != _LANGUAGE_PARAMETRIC_RECIPE_KEY
        or parametric_meaning.get("recipe_family")
        != _LANGUAGE_PARAMETRIC_RECIPE_FAMILY
        or parametric_meaning.get("stage_component_key") != "stage_order"
        or parametric_meaning.get("recipe") != _LANGUAGE_PARAMETRIC_RECIPE_TEMPLATE
        or not isinstance(parametric_result, Mapping)
        or not isinstance(parametric_payload, Mapping)
        or parametric_payload.get("status") != "supported"
        or parametric_payload.get("construction") != parametric_reference
        or not isinstance(parametric_reference, Mapping)
    ):
        raise VerificationError("parametric recipe acquisition is invalid")
    stage_request = next(
        row["request"]
        for row in component_rows
        if row["request"].get("construction_id")
        == expected_component_ids["stage_order"]
    )
    stage_meaning = stage_request.get("meaning")
    if (
        not isinstance(stage_meaning, Mapping)
        or stage_meaning.get("component_kind") != "query-control"
        or stage_meaning.get("role") != "stage_arrangement"
        or stage_meaning.get("recipe_schema") != _LANGUAGE_STAGE_RECIPE_SCHEMA
        or not isinstance(stage_meaning.get("recipe_catalog"), Mapping)
        or set(stage_meaning["recipe_catalog"]) != set(_EXPECTED_STAGE_RECIPE_KEYS)
    ):
        raise VerificationError("stage component did not retain its recipe catalog")
    for row, recipe_key in zip(recipe_rows, _EXPECTED_STAGE_RECIPE_KEYS):
        recipe_meaning = row["request"].get("meaning")
        if (
            not isinstance(recipe_meaning, Mapping)
            or recipe_meaning.get("recipe")
            != stage_meaning["recipe_catalog"].get(recipe_key)
        ):
            raise VerificationError("recipe acquisition diverges from stage catalog")
    if recipe_refs_in_order != [
        recipe_references[key] for key in _EXPECTED_STAGE_RECIPE_KEYS
    ]:
        raise VerificationError("language recipe reference order is unstable")
    composed_meaning = learning_request.get("meaning")
    if (
        not isinstance(composed_meaning, Mapping)
        or "query_ast" in composed_meaning
        or composed_meaning.get("program_kind") != "component-composition"
        or [
            item.get("key")
            for item in composed_meaning.get("components", [])
            if isinstance(item, Mapping)
        ]
        != list(expected_component_ids)
    ):
        raise VerificationError("composed meaning did not retain component provenance")
    composed_recipe_components = composed_meaning.get("recipe_components")
    if (
        not isinstance(composed_recipe_components, list)
        or [
            item.get("key")
            for item in composed_recipe_components
            if isinstance(item, Mapping)
        ]
        != list(_EXPECTED_STAGE_RECIPE_KEYS)
        or any(
            not isinstance(item, Mapping)
            or item.get("construction") != recipe_references.get(item.get("key"))
            or item.get("recipe")
            != stage_meaning["recipe_catalog"].get(item.get("key"))
            for item in composed_recipe_components
        )
    ):
        raise VerificationError("composed meaning did not retain recipe provenance")
    composed_stage_recipes = composed_meaning.get("stage_recipes")
    composed_entries = (
        composed_stage_recipes.get("entries")
        if isinstance(composed_stage_recipes, Mapping)
        else None
    )
    composed_parametric = (
        composed_stage_recipes.get("parametric")
        if isinstance(composed_stage_recipes, Mapping)
        else None
    )
    if (
        not isinstance(composed_stage_recipes, Mapping)
        or composed_stage_recipes.get("schema") != _LANGUAGE_STAGE_RECIPE_SCHEMA
        or composed_stage_recipes.get("component_key") != "stage_order"
        or composed_stage_recipes.get("component")
        != component_references["stage_order"]
        or composed_stage_recipes.get("catalog")
        != stage_meaning["recipe_catalog"]
        or not isinstance(composed_entries, Mapping)
        or set(composed_entries) != set(_EXPECTED_STAGE_RECIPE_KEYS)
        or any(
            not isinstance(composed_entries[key], Mapping)
            or composed_entries[key].get("construction")
            != recipe_references[key]
            or composed_entries[key].get("recipe")
            != stage_meaning["recipe_catalog"][key]
            for key in _EXPECTED_STAGE_RECIPE_KEYS
        )
        or composed_parametric
        != {
            "family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
            "recipe_key": _LANGUAGE_PARAMETRIC_RECIPE_KEY,
            "construction": parametric_reference,
        }
    ):
        raise VerificationError("composed meaning did not retain field-owned recipes")
    if learning_request.get("components") != component_refs_in_order:
        raise VerificationError("composed construction dependencies are not ordered components")
    expected_pattern = [
        "{fill_value}",
        ";",
        "keep",
        "above",
        "{threshold}",
        ";",
        "unique",
        ";",
        "{order_direction}",
        ";",
        "first",
        "{row_limit}",
        ";",
        "mode",
        "{stage_arrangement}",
    ]
    if learned_result.get("pattern") != expected_pattern:
        raise VerificationError("language construction did not retain all five roles")
    pattern_variants = learned_result.get("pattern_variants")
    if pattern_variants is not None and pattern_variants != [expected_pattern]:
        raise VerificationError("language construction has an unexpected pattern variant")
    if language_text != "N=7; keep above 2; unique; ascending; first 4; mode limit":
        raise VerificationError("language held-out case is not the unseen arrangement binding")
    _verify_native_language_teacher(
        language_raw=language_raw,
        learning_examples=examples,
        native_observation=receipt.get("native_observation"),
    )
    teacher_evidence = language_raw.get("native_teacher")
    teacher_trial = (
        teacher_evidence.get("trial")
        if isinstance(teacher_evidence, Mapping)
        else None
    )
    teacher_identity_sha256 = (
        teacher_trial.get("identity_sha256")
        if isinstance(teacher_trial, Mapping)
        else None
    )
    if learning_request.get("support_roots") != [teacher_identity_sha256]:
        raise VerificationError("language construction is not rooted in the native teacher")
    for row in component_rows:
        component_request = row["request"]
        if component_request.get("support_roots") != [teacher_identity_sha256]:
            raise VerificationError("language component is not rooted in the native teacher")
    for row in recipe_rows:
        recipe_request = row["request"]
        if recipe_request.get("support_roots") != [teacher_identity_sha256]:
            raise VerificationError("language recipe is not rooted in the native teacher")
    if parametric_request.get("support_roots") != [teacher_identity_sha256]:
        raise VerificationError("parametric recipe is not rooted in the native teacher")
    teacher_recipe_examples = (
        teacher_evidence.get("recipe_examples")
        if isinstance(teacher_evidence, Mapping)
        else None
    )
    if teacher_recipe_examples != expected_parametric_examples:
        raise VerificationError("native teacher recipe examples were not retained")
    if any(
        isinstance(example, Mapping) and example.get("text") == language_text
        for example in examples
    ):
        raise VerificationError("language held-out text was exposed during teaching")
    meaning = learning_request.get("meaning")
    if (
        not isinstance(meaning, Mapping)
        or "query_ast" in meaning
        or meaning.get("program_kind") != "component-composition"
    ):
        raise VerificationError("language meaning was not a component plan")
    language_input = make_input(language_case)
    language_expected = _verify_oracle(
        language_prediction.get("oracle"),
        language_sql,
        language_input,
        "language_to_program",
    )
    interpret_request = language_prediction.get("interpret_request")
    interpret_result = language_prediction.get("interpret_result")
    interpretation = language_prediction.get("interpretation")
    mechanism_request = language_prediction.get("mechanism_request")
    mechanism_result = language_prediction.get("mechanism_result")
    for label, value in (
        ("interpret request", interpret_request),
        ("interpret result", interpret_result),
        ("interpretation", interpretation),
        ("mechanism request", mechanism_request),
        ("mechanism result", mechanism_result),
    ):
        if not isinstance(value, Mapping):
            raise VerificationError(f"language {label} is missing")
    if (
        interpret_request.get("operation") != "interpret"
        or interpret_request.get("text") != language_text
        or any(key in interpret_request for key in ("ast", "query_ast", "sql"))
    ):
        raise VerificationError("language interpretation request supplied a target AST")
    content = interpretation.get("content")
    if (
        not isinstance(content, Mapping)
        or "query_ast" in content
        or "sql" in content
    ):
        raise VerificationError("language interpretation emitted a target program")
    if interpretation.get("construction_id") != construction_reference.get("id"):
        raise VerificationError("language interpretation selected the wrong construction")
    expected_ast = _sql_to_sequence_ast(_SQL(language_sql).parse())
    compiled_from_plan = sequence_ast(_compile_language_plan(content))
    if compiled_from_plan != expected_ast:
        raise VerificationError("language component plan differs from SQL semantics")
    reported_ast = sequence_ast(language_prediction.get("query_ast"))
    if reported_ast != expected_ast:
        raise VerificationError("language-to-program AST differs from SQL semantics")
    if reported_ast != compiled_from_plan:
        raise VerificationError("language report changed the compiled component plan")
    action = mechanism_request.get("action")
    if (
        mechanism_request.get("operation") != "mechanism-step"
        or mechanism_request.get("mechanism_id") != selected_candidate
        or not isinstance(action, Mapping)
        or table(action.get("table"), "language field input") != language_input
        or sequence_ast(action.get("query_ast")) != expected_ast
    ):
        raise VerificationError("language mechanism call is not bound to interpretation")
    outcome = mechanism_result.get("result", {}).get("outcome")
    if not isinstance(outcome, Mapping):
        raise VerificationError("language mechanism result has no outcome")
    prediction = language_prediction.get("prediction")
    prediction_table = table(prediction, "language field prediction")
    if prediction_table != language_expected:
        raise VerificationError("language-to-program prediction mismatch")
    selected_program = candidate_pool.get(selected_candidate) if isinstance(candidate_pool, Mapping) else None
    if not isinstance(selected_program, Mapping):
        raise VerificationError("language selected program is missing")
    if execute_sequence(selected_program, language_input, expected_ast) != prediction_table:
        raise VerificationError("language selected program prediction mismatch")
    if language_prediction.get("prediction_digest") != digest(prediction_table):
        raise VerificationError("language prediction digest mismatch")
    if language_prediction.get("oracle_digest") != digest(language_expected):
        raise VerificationError("language oracle digest mismatch")
    if language_prediction.get("matches_oracle") is not True:
        raise VerificationError("language-to-program declared mismatch")
    language_state_before = language_raw.get("state_before")
    language_state_after = language_raw.get("state_after")
    language_reopen = language_raw.get("persistence_reopen")
    post_reopen = receipt.get("post_reopen_behavior")
    prior_reopen = (
        post_reopen.get("persistence_reopen")
        if isinstance(post_reopen, Mapping)
        else None
    )
    if not isinstance(language_state_before, Mapping) or not isinstance(language_state_after, Mapping):
        raise VerificationError("language state receipts are missing")
    if (
        not isinstance(prior_reopen, Mapping)
        or language_state_before != prior_reopen.get("reopened")
        or not isinstance(language_reopen, Mapping)
        or language_reopen.get("equal") is not True
        or language_reopen.get("reopened") != language_state_after
    ):
        raise VerificationError("language behavior did not persist across reopen")
    additional_cases = language_fixture.get("additional_cases")
    additional_predictions = language_raw.get("additional_predictions")
    if (
        not isinstance(additional_cases, list)
        or len(additional_cases) != 7
        or not isinstance(additional_predictions, list)
        or len(additional_predictions) != 7
    ):
        raise VerificationError("language additional arrangement evidence is incomplete")
    expected_arrangements = [
        "limit",
        "limit-distinct",
        "distinct-filter",
        "nested-reapply",
        "recursive-3",
        "recursive-4",
        "weave",
        "recursive-5",
    ]
    all_language_cases = [language_case, *additional_cases]
    if [
        case.get("binding", {}).get("stage_arrangement")
        for case in all_language_cases
        if isinstance(case, Mapping)
    ] != expected_arrangements:
        raise VerificationError("language arrangements are not the declared held-out routes")
    for index, (case, prediction_row) in enumerate(
        zip(additional_cases, additional_predictions), 1
    ):
        if not isinstance(case, Mapping):
            raise VerificationError(f"language additional case {index} is invalid")
        verify_language_prediction(
            prediction_row,
            case,
            label=f"language_to_program.additional[{index - 1}]",
            construction_id=str(construction_reference["id"]),
            selected_candidate=str(selected_candidate),
        )
    recursive_signatures = [
        _pipeline_stage_signature(
            additional_predictions[index]["query_ast"]
        )
        for index in (3, 4)
    ]
    if recursive_signatures != [
        [
            ["project", "distinct"],
            *[["filter", "project", "order", "limit"] for _ in range(3)],
            ["project", "order", "limit"],
        ],
        [
            ["project", "distinct"],
            *[["filter", "project", "order", "limit"] for _ in range(4)],
            ["project", "order", "limit"],
        ],
    ]:
        raise VerificationError("recursive language stage depth was not transferred")
    if _pipeline_stage_signature(additional_predictions[6]["query_ast"]) != [
        ["project", "distinct"],
        *[["filter", "project", "order", "limit"] for _ in range(5)],
        ["project", "order", "limit"],
    ]:
        raise VerificationError("parametric language recipe did not generalize")
    if _pipeline_stage_signature(additional_predictions[5]["query_ast"]) != [
        ["project", "limit"],
        ["project", "distinct"],
        ["filter", "project", "order"],
        ["project"],
    ]:
        raise VerificationError("declarative language recipe was not transferred")
    selective_recovery = language_raw.get("selective_component_recovery")
    if not isinstance(selective_recovery, Mapping):
        raise VerificationError("selective component recovery evidence is missing")
    component_key = selective_recovery.get("component_key")
    if component_key != "order_limit":
        raise VerificationError("selective loss targeted the wrong component")
    old_component_reference = component_references.get(component_key)
    revoke_request = selective_recovery.get("revoke_request")
    revoke_result = selective_recovery.get("revoke_result")
    revoked_reference = selective_recovery.get("revoked_reference")
    if (
        not isinstance(old_component_reference, Mapping)
        or not isinstance(revoke_request, Mapping)
        or revoke_request.get("operation") != "revoke"
        or revoke_request.get("target") != old_component_reference
        or not isinstance(revoke_result, Mapping)
        or revoke_result.get("result", {}).get("status") != "supported"
        or not isinstance(revoked_reference, Mapping)
        or revoked_reference.get("id") != old_component_reference.get("id")
    ):
        raise VerificationError("selective component revocation is not bound")
    lost_result = selective_recovery.get("lost_interpret_result")
    lost_request = selective_recovery.get("lost_interpret_request")
    if (
        not isinstance(lost_request, Mapping)
        or lost_request.get("operation") != "interpret"
        or lost_request.get("text") != language_text
        or any(key in lost_request for key in ("ast", "query_ast", "sql"))
        or not isinstance(lost_result, Mapping)
        or lost_result.get("result", {}).get("status") != "support-gap"
        or lost_result.get("result", {}).get("interpretation") is not None
    ):
        raise VerificationError("selective component loss did not remove composed support")
    unrelated_result = selective_recovery.get("unrelated_interpret_result")
    unrelated_request = selective_recovery.get("unrelated_interpret_request")
    unrelated_interpretation = (
        unrelated_result.get("result", {}).get("interpretation")
        if isinstance(unrelated_result, Mapping)
        else None
    )
    if (
        not isinstance(unrelated_request, Mapping)
        or unrelated_request.get("operation") != "interpret"
        or unrelated_request.get("text") != "unique"
        or unrelated_request.get("permitted_context")
        != {
            "component_scope": "component-only",
            "component_key": "distinct",
        }
        or not isinstance(unrelated_result, Mapping)
        or unrelated_result.get("result", {}).get("status") != "supported"
        or not isinstance(unrelated_interpretation, Mapping)
        or unrelated_interpretation.get("construction_id")
        != "construction:language:component:distinct"
    ):
        raise VerificationError("selective loss removed an unrelated component")
    reacquire_request = selective_recovery.get("reacquire_request")
    reacquire_result = selective_recovery.get("reacquire_result")
    reacquired_reference = selective_recovery.get("reacquired_reference")
    if (
        not isinstance(reacquire_request, Mapping)
        or reacquire_request.get("operation") != "learn-construction"
        or reacquire_request.get("construction_id") != expected_component_ids[component_key]
        or reacquire_request.get("guards")
        != {
            "component_scope": "component-only",
            "component_key": component_key,
        }
        or reacquire_request.get("support_roots") != [teacher_identity_sha256]
        or not isinstance(reacquire_result, Mapping)
        or reacquire_result.get("result", {}).get("status") != "supported"
        or not isinstance(reacquired_reference, Mapping)
        or reacquired_reference == old_component_reference
    ):
        raise VerificationError("selective component was not reacquired with provenance")
    recovered_learning = selective_recovery.get("recovered_learning")
    recovered_request = (
        recovered_learning.get("request") if isinstance(recovered_learning, Mapping) else None
    )
    recovered_result = (
        recovered_learning.get("result") if isinstance(recovered_learning, Mapping) else None
    )
    recovered_reference = (
        recovered_learning.get("reference") if isinstance(recovered_learning, Mapping) else None
    )
    expected_recovered_components = [
        reacquired_reference if key == component_key else component_references[key]
        for key in expected_component_ids
    ]
    if (
        not isinstance(recovered_request, Mapping)
        or recovered_request.get("operation") != "learn-construction"
        or recovered_request.get("components") != expected_recovered_components
        or not isinstance(recovered_result, Mapping)
        or recovered_result.get("result", {}).get("status") != "supported"
        or not isinstance(recovered_reference, Mapping)
        or recovered_result.get("result", {}).get("construction") != recovered_reference
    ):
        raise VerificationError("composed construction did not recover its component binding")
    recovery_case = selective_recovery.get("recovery_case")
    if not isinstance(recovery_case, Mapping) or recovery_case != additional_cases[2]:
        raise VerificationError("recovery case is not the nested unseen arrangement")
    recovery_prediction = selective_recovery.get("recovery_prediction")
    verify_language_prediction(
        recovery_prediction,
        recovery_case,
        label="language_to_program.recovery",
        construction_id=str(recovered_reference["id"]),
        selected_candidate=str(selected_candidate),
    )
    recovery_state_before = selective_recovery.get("state_before")
    recovery_state_after = selective_recovery.get("state_after")
    recovery_persistence = selective_recovery.get("persistence_reopen")
    if (
        not isinstance(recovery_state_before, Mapping)
        or not isinstance(recovery_state_after, Mapping)
        or not isinstance(recovery_persistence, Mapping)
        or recovery_persistence.get("equal") is not True
        or recovery_persistence.get("reopened") != recovery_state_after
    ):
        raise VerificationError("recovered component behavior did not persist")
    secondary_recovery = selective_recovery.get("secondary_component_recovery")
    if not isinstance(secondary_recovery, Mapping):
        raise VerificationError("sequential second component recovery is missing")
    secondary_key = secondary_recovery.get("component_key")
    if secondary_key != "stage_order":
        raise VerificationError("sequential second loss targeted the wrong component")
    secondary_old_reference = component_references.get(secondary_key)
    secondary_revoke_request = secondary_recovery.get("revoke_request")
    secondary_revoke_result = secondary_recovery.get("revoke_result")
    secondary_revoked_reference = secondary_recovery.get("revoked_reference")
    if (
        not isinstance(secondary_old_reference, Mapping)
        or not isinstance(secondary_revoke_request, Mapping)
        or secondary_revoke_request.get("operation") != "revoke"
        or secondary_revoke_request.get("target") != secondary_old_reference
        or not isinstance(secondary_revoke_result, Mapping)
        or secondary_revoke_result.get("result", {}).get("status") != "supported"
        or not isinstance(secondary_revoked_reference, Mapping)
        or secondary_revoked_reference.get("id") != secondary_old_reference.get("id")
    ):
        raise VerificationError("sequential second component revocation is not bound")
    secondary_lost_request = secondary_recovery.get("lost_interpret_request")
    secondary_lost_result = secondary_recovery.get("lost_interpret_result")
    if (
        not isinstance(secondary_lost_request, Mapping)
        or secondary_lost_request.get("operation") != "interpret"
        or secondary_lost_request.get("text") != recovery_case.get("text")
        or any(key in secondary_lost_request for key in ("ast", "query_ast", "sql"))
        or not isinstance(secondary_lost_result, Mapping)
        or secondary_lost_result.get("result", {}).get("status") != "support-gap"
        or secondary_lost_result.get("result", {}).get("interpretation") is not None
    ):
        raise VerificationError("sequential second loss did not remove nested support")
    secondary_unrelated_request = secondary_recovery.get("unrelated_interpret_request")
    secondary_unrelated_result = secondary_recovery.get("unrelated_interpret_result")
    secondary_unrelated_interpretation = (
        secondary_unrelated_result.get("result", {}).get("interpretation")
        if isinstance(secondary_unrelated_result, Mapping)
        else None
    )
    if (
        not isinstance(secondary_unrelated_request, Mapping)
        or secondary_unrelated_request.get("operation") != "interpret"
        or secondary_unrelated_request.get("text") != "ascending; first 2"
        or secondary_unrelated_request.get("permitted_context")
        != {
            "component_scope": "component-only",
            "component_key": "order_limit",
        }
        or not isinstance(secondary_unrelated_result, Mapping)
        or secondary_unrelated_result.get("result", {}).get("status") != "supported"
        or not isinstance(secondary_unrelated_interpretation, Mapping)
        or secondary_unrelated_interpretation.get("construction_id")
        != reacquired_reference.get("id")
    ):
        raise VerificationError("sequential second loss removed the first recovery")
    secondary_reacquire_request = secondary_recovery.get("reacquire_request")
    secondary_reacquire_result = secondary_recovery.get("reacquire_result")
    secondary_reacquired_reference = secondary_recovery.get("reacquired_reference")
    if (
        not isinstance(secondary_reacquire_request, Mapping)
        or secondary_reacquire_request.get("operation") != "learn-construction"
        or secondary_reacquire_request.get("construction_id")
        != expected_component_ids[secondary_key]
        or secondary_reacquire_request.get("guards")
        != {
            "component_scope": "component-only",
            "component_key": secondary_key,
        }
        or secondary_reacquire_request.get("support_roots") != [teacher_identity_sha256]
        or not isinstance(secondary_reacquire_result, Mapping)
        or secondary_reacquire_result.get("result", {}).get("status") != "supported"
        or not isinstance(secondary_reacquired_reference, Mapping)
        or secondary_reacquired_reference == secondary_old_reference
    ):
        raise VerificationError("sequential second component was not reacquired with provenance")
    secondary_learning = secondary_recovery.get("recovered_learning")
    secondary_request = (
        secondary_learning.get("request")
        if isinstance(secondary_learning, Mapping)
        else None
    )
    secondary_result = (
        secondary_learning.get("result")
        if isinstance(secondary_learning, Mapping)
        else None
    )
    secondary_reference = (
        secondary_learning.get("reference")
        if isinstance(secondary_learning, Mapping)
        else None
    )
    expected_secondary_components = [
        (
            reacquired_reference
            if key == component_key
            else secondary_reacquired_reference
            if key == secondary_key
            else component_references[key]
        )
        for key in expected_component_ids
    ]
    if (
        not isinstance(secondary_request, Mapping)
        or secondary_request.get("operation") != "learn-construction"
        or secondary_request.get("components") != expected_secondary_components
        or not isinstance(secondary_result, Mapping)
        or secondary_result.get("result", {}).get("status") != "supported"
        or not isinstance(secondary_reference, Mapping)
        or secondary_result.get("result", {}).get("construction") != secondary_reference
    ):
        raise VerificationError("nested construction did not recover after sequential reacquisition")
    secondary_prediction = secondary_recovery.get("recovery_prediction")
    verify_language_prediction(
        secondary_prediction,
        recovery_case,
        label="language_to_program.sequential-recovery",
        construction_id=str(secondary_reference["id"]),
        selected_candidate=str(selected_candidate),
    )
    recipe_recovery = selective_recovery.get("recipe_recovery")
    if not isinstance(recipe_recovery, Mapping):
        raise VerificationError("selective recipe recovery is missing")
    recipe_key = recipe_recovery.get("recipe_key")
    if recipe_key != "weave":
        raise VerificationError("selective recipe loss targeted the wrong recipe")
    old_recipe_reference = recipe_references.get(recipe_key)
    recipe_revoke_request = recipe_recovery.get("revoke_request")
    recipe_revoke_result = recipe_recovery.get("revoke_result")
    recipe_revoked_reference = recipe_recovery.get("revoked_reference")
    if (
        not isinstance(old_recipe_reference, Mapping)
        or not isinstance(recipe_revoke_request, Mapping)
        or recipe_revoke_request.get("operation") != "revoke"
        or recipe_revoke_request.get("target") != old_recipe_reference
        or not isinstance(recipe_revoke_result, Mapping)
        or recipe_revoke_result.get("result", {}).get("status") != "supported"
        or not isinstance(recipe_revoked_reference, Mapping)
        or recipe_revoked_reference.get("id") != old_recipe_reference.get("id")
    ):
        raise VerificationError("selective recipe revocation is not bound")
    recipe_lost_request = recipe_recovery.get("lost_interpret_request")
    recipe_lost_result = recipe_recovery.get("lost_interpret_result")
    if (
        not isinstance(recipe_lost_request, Mapping)
        or recipe_lost_request.get("operation") != "interpret"
        or recipe_lost_request.get("text") != "mode weave"
        or recipe_lost_request.get("permitted_context")
        != {"component_scope": "recipe-only", "recipe_key": "weave"}
        or any(key in recipe_lost_request for key in ("ast", "query_ast", "sql"))
        or not isinstance(recipe_lost_result, Mapping)
        or recipe_lost_result.get("result", {}).get("status") != "support-gap"
        or recipe_lost_result.get("result", {}).get("interpretation") is not None
    ):
        raise VerificationError("selective recipe loss did not remove weave support")
    unrelated_recipe_key = recipe_recovery.get("unrelated_recipe_key")
    unrelated_recipe_request = recipe_recovery.get("unrelated_interpret_request")
    unrelated_recipe_result = recipe_recovery.get("unrelated_interpret_result")
    unrelated_recipe_interpretation = (
        unrelated_recipe_result.get("result", {}).get("interpretation")
        if isinstance(unrelated_recipe_result, Mapping)
        else None
    )
    if (
        unrelated_recipe_key != "recursive-3"
        or not isinstance(unrelated_recipe_request, Mapping)
        or unrelated_recipe_request.get("operation") != "interpret"
        or unrelated_recipe_request.get("text") != "mode recursive-3"
        or unrelated_recipe_request.get("permitted_context")
        != {"component_scope": "recipe-only", "recipe_key": "recursive-3"}
        or not isinstance(unrelated_recipe_result, Mapping)
        or unrelated_recipe_result.get("result", {}).get("status") != "supported"
        or not isinstance(unrelated_recipe_interpretation, Mapping)
        or unrelated_recipe_interpretation.get("construction_id")
        != recipe_references["recursive-3"]["id"]
    ):
        raise VerificationError("selective recipe loss removed an unrelated recipe")
    survivor_case = recipe_recovery.get("survivor_case")
    if not isinstance(survivor_case, Mapping) or survivor_case != additional_cases[4]:
        raise VerificationError("recipe survivor case is not recursive-3")
    verify_language_prediction(
        recipe_recovery.get("survivor_prediction"),
        survivor_case,
        label="language_to_program.recipe-survivor",
        construction_id=str(secondary_reference["id"]),
        selected_candidate=str(selected_candidate),
    )
    recipe_reacquire_request = recipe_recovery.get("reacquire_request")
    recipe_reacquire_result = recipe_recovery.get("reacquire_result")
    recipe_reacquired_reference = recipe_recovery.get("reacquired_reference")
    if (
        not isinstance(recipe_reacquire_request, Mapping)
        or recipe_reacquire_request.get("operation") != "learn-construction"
        or recipe_reacquire_request.get("construction_id")
        != f"construction:language:recipe:{recipe_key}"
        or recipe_reacquire_request.get("guards")
        != {"component_scope": "recipe-only", "recipe_key": recipe_key}
        or recipe_reacquire_request.get("support_roots") != [teacher_identity_sha256]
        or not isinstance(recipe_reacquire_result, Mapping)
        or recipe_reacquire_result.get("result", {}).get("status") != "supported"
        or not isinstance(recipe_reacquired_reference, Mapping)
        or recipe_reacquired_reference == old_recipe_reference
    ):
        raise VerificationError("weave recipe was not reacquired with provenance")
    recovered_recipe_learning = recipe_recovery.get("recovered_learning")
    recovered_recipe_request = (
        recovered_recipe_learning.get("request")
        if isinstance(recovered_recipe_learning, Mapping)
        else None
    )
    recovered_recipe_result = (
        recovered_recipe_learning.get("result")
        if isinstance(recovered_recipe_learning, Mapping)
        else None
    )
    recovered_recipe_reference = (
        recovered_recipe_learning.get("reference")
        if isinstance(recovered_recipe_learning, Mapping)
        else None
    )
    if (
        not isinstance(recovered_recipe_request, Mapping)
        or recovered_recipe_request.get("operation") != "learn-construction"
        or recovered_recipe_request.get("components") != expected_secondary_components
        or not isinstance(recovered_recipe_result, Mapping)
        or recovered_recipe_result.get("result", {}).get("status") != "supported"
        or not isinstance(recovered_recipe_reference, Mapping)
        or recovered_recipe_result.get("result", {}).get("construction")
        != recovered_recipe_reference
    ):
        raise VerificationError("composition did not recover after recipe reacquisition")
    reported_recovered_recipe_references = recipe_recovery.get(
        "recovered_recipe_references"
    )
    expected_recovered_recipe_references = {
        key: (
            recipe_reacquired_reference
            if key == recipe_key
            else recipe_references[key]
        )
        for key in _EXPECTED_STAGE_RECIPE_KEYS
    }
    recovered_meaning = recovered_recipe_request.get("meaning")
    recovered_stage_recipes = (
        recovered_meaning.get("stage_recipes")
        if isinstance(recovered_meaning, Mapping)
        else None
    )
    recovered_entries = (
        recovered_stage_recipes.get("entries")
        if isinstance(recovered_stage_recipes, Mapping)
        else None
    )
    if (
        reported_recovered_recipe_references
        != expected_recovered_recipe_references
        or not isinstance(recovered_entries, Mapping)
        or set(recovered_entries) != set(_EXPECTED_STAGE_RECIPE_KEYS)
        or any(
            not isinstance(recovered_entries[key], Mapping)
            or recovered_entries[key].get("construction")
            != expected_recovered_recipe_references[key]
            for key in _EXPECTED_STAGE_RECIPE_KEYS
        )
    ):
        raise VerificationError("recovered composition lost recipe provenance")
    recipe_recovery_case = recipe_recovery.get("recovery_case")
    if (
        not isinstance(recipe_recovery_case, Mapping)
        or recipe_recovery_case != additional_cases[5]
    ):
        raise VerificationError("recipe recovery case is not recursive-4")
    verify_language_prediction(
        recipe_recovery.get("recovery_prediction"),
        recipe_recovery_case,
        label="language_to_program.recipe-recovery",
        construction_id=str(recovered_recipe_reference["id"]),
        selected_candidate=str(selected_candidate),
    )
    parametric_recovery = selective_recovery.get("parametric_recipe_recovery")
    if not isinstance(parametric_recovery, Mapping):
        raise VerificationError("parametric recipe recovery is missing")
    parametric_case = additional_cases[6]
    if (
        parametric_recovery.get("recipe_key") != _LANGUAGE_PARAMETRIC_RECIPE_KEY
        or parametric_recovery.get("recipe_family")
        != _LANGUAGE_PARAMETRIC_RECIPE_FAMILY
        or parametric_recovery.get("recovery_case") != parametric_case
    ):
        raise VerificationError("parametric recovery case is not recursive-5")
    parametric_old_reference = parametric_recovery.get("recipe_reference_before")
    parametric_revoke_request = parametric_recovery.get("revoke_request")
    parametric_revoke_result = parametric_recovery.get("revoke_result")
    parametric_revoked_reference = parametric_recovery.get("revoked_reference")
    if (
        parametric_old_reference != parametric_reference
        or not isinstance(parametric_revoke_request, Mapping)
        or parametric_revoke_request.get("operation") != "revoke"
        or parametric_revoke_request.get("target") != parametric_reference
        or not isinstance(parametric_revoke_result, Mapping)
        or parametric_revoke_result.get("result", {}).get("status") != "supported"
        or not isinstance(parametric_revoked_reference, Mapping)
        or parametric_revoked_reference.get("id") != parametric_reference.get("id")
    ):
        raise VerificationError("parametric recipe revocation is not bound")
    parametric_lost_request = parametric_recovery.get("lost_interpret_request")
    parametric_lost_result = parametric_recovery.get("lost_interpret_result")
    if (
        not isinstance(parametric_lost_request, Mapping)
        or parametric_lost_request.get("operation") != "interpret"
        or parametric_lost_request.get("text") != parametric_case.get("recipe_text")
        or parametric_lost_request.get("permitted_context")
        != {
            "component_scope": "recipe-only",
            "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
        }
        or any(key in parametric_lost_request for key in ("ast", "query_ast", "sql"))
        or not isinstance(parametric_lost_result, Mapping)
        or parametric_lost_result.get("result", {}).get("status") != "support-gap"
        or parametric_lost_result.get("result", {}).get("interpretation") is not None
    ):
        raise VerificationError("parametric recipe loss did not remove support")
    parametric_survivor_request = parametric_recovery.get("survivor_request")
    parametric_survivor_result = parametric_recovery.get("survivor_result")
    parametric_survivor_interpretation = (
        parametric_survivor_result.get("result", {}).get("interpretation")
        if isinstance(parametric_survivor_result, Mapping)
        else None
    )
    if (
        not isinstance(parametric_survivor_request, Mapping)
        or parametric_survivor_request.get("operation") != "interpret"
        or parametric_survivor_request.get("text") != "mode recursive-3"
        or parametric_survivor_request.get("permitted_context")
        != {"component_scope": "recipe-only", "recipe_key": "recursive-3"}
        or not isinstance(parametric_survivor_result, Mapping)
        or parametric_survivor_result.get("result", {}).get("status") != "supported"
        or not isinstance(parametric_survivor_interpretation, Mapping)
        or parametric_survivor_interpretation.get("construction_id")
        != recipe_references["recursive-3"]["id"]
    ):
        raise VerificationError("parametric recipe loss removed an unrelated recipe")
    parametric_reacquire_request = parametric_recovery.get("reacquire_request")
    parametric_reacquire_result = parametric_recovery.get("reacquire_result")
    parametric_reacquired_reference = parametric_recovery.get("reacquired_reference")
    if (
        not isinstance(parametric_reacquire_request, Mapping)
        or parametric_reacquire_request.get("operation") != "learn-construction"
        or parametric_reacquire_request.get("construction_id")
        != parametric_reference.get("id")
        or parametric_reacquire_request.get("guards")
        != {
            "component_scope": "recipe-only",
            "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
        }
        or parametric_reacquire_request.get("support_roots")
        != [teacher_identity_sha256]
        or not isinstance(parametric_reacquire_result, Mapping)
        or parametric_reacquire_result.get("result", {}).get("status")
        != "supported"
        or not isinstance(parametric_reacquired_reference, Mapping)
        or parametric_reacquired_reference == parametric_old_reference
        or parametric_reacquire_result.get("result", {}).get("construction")
        != parametric_reacquired_reference
    ):
        raise VerificationError("parametric recipe was not reacquired with provenance")
    parametric_recovery_prediction = parametric_recovery.get("recovery_prediction")
    verify_language_prediction(
        parametric_recovery_prediction,
        parametric_case,
        label="language_to_program.parametric-recovery",
        construction_id=str(recovered_recipe_reference["id"]),
        selected_candidate=str(selected_candidate),
    )
    parametric_recovery_recipe_interpretation = (
        parametric_recovery_prediction.get("recipe_interpretation")
        if isinstance(parametric_recovery_prediction, Mapping)
        else None
    )
    if (
        not isinstance(parametric_recovery_recipe_interpretation, Mapping)
        or parametric_recovery_recipe_interpretation.get("construction_id")
        != parametric_reacquired_reference.get("id")
    ):
        raise VerificationError("parametric recovery did not use the reacquired recipe")
    reported = receipt.get("invariants")
    if isinstance(reported, Mapping):
        for key in (
            "language_interpretation_call_contains_no_ast_or_sql",
            "field_question_choice_is_separating",
            "native_observation_is_coupled",
            "native_output_admitted_to_field",
            "native_observation_updates_field_evidence",
            "native_language_teacher_admitted",
            "language_components_acquired_separately",
            "language_recipes_acquired_separately",
            "language_stage_recipes_field_owned",
            "language_composed_components_bound",
            "language_recipe_entries_bound",
            "native_language_teacher_retained_five_roles",
            "native_language_parametric_recipe_admitted",
            "language_parametric_recipe_generalizes",
            "language_parametric_recipe_recovery",
            "language_selective_recipe_recovery",
            "language_selective_component_loss",
            "language_selective_component_recovery",
        ):
            if key in reported and reported[key] is not True:
                raise VerificationError(f"receipt invariant {key} is false")
    invariants = receipt.get("invariants")
    if isinstance(invariants, Mapping):
        for key in ("all_training_frontiers_proposed", "all_training_acknowledged",
                    "all_held_out_match", "oracle_is_external", "field_calls_contain_no_sql"):
            if key in invariants and invariants[key] is not True:
                raise VerificationError(f"receipt invariant {key} is false")
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path, help="runner canonical JSON receipt")
    mutation_group = parser.add_mutually_exclusive_group()
    mutation_group.add_argument(
        "--mutate",
        action="store_true",
        help="apply an in-memory field-binding mutation and require verification to fail",
    )
    mutation_group.add_argument(
        "--mutate-recipe",
        action="store_true",
        help="apply an in-memory stage-recipe mutation and require verification to fail",
    )
    args = parser.parse_args(argv)
    try:
        loaded = json.loads(args.receipt.read_text(encoding="utf-8"))
        if args.mutate or args.mutate_recipe:
            loaded = copy.deepcopy(loaded)
            if args.mutate_recipe:
                language = loaded.get("language_to_program")
                additional = (
                    language.get("additional_predictions")
                    if isinstance(language, Mapping)
                    else None
                )
                prediction = (
                    additional[-1]
                    if isinstance(additional, list) and additional
                    else language.get("prediction")
                    if isinstance(language, Mapping)
                    else None
                )
                recipe_interpretation = (
                    prediction.get("recipe_interpretation")
                    if isinstance(prediction, Mapping)
                    else None
                )
                recipe_content = (
                    recipe_interpretation.get("content")
                    if isinstance(recipe_interpretation, Mapping)
                    else None
                )
                recipe = (
                    recipe_content.get("recipe")
                    if isinstance(recipe_content, Mapping)
                    else None
                )
                layers = recipe.get("layers") if isinstance(recipe, Mapping) else None
                if not isinstance(layers, list) or not layers:
                    raise VerificationError("mutation control has no parametric recipe")
                layers[0] = ["distinct"]
            else:
                native = loaded.get("native_observation")
                if isinstance(native, Mapping):
                    binding_response = native.get("binding_query_response")
                    binding_record = (
                        binding_response.get("result", {}).get("record")
                        if isinstance(binding_response, Mapping)
                        else None
                    )
                    binding_payload = (
                        binding_record.get("payload")
                        if isinstance(binding_record, Mapping)
                        else None
                    )
                    if not isinstance(binding_payload, Mapping):
                        raise VerificationError("mutation control has no native binding")
                    binding_payload["value"] = (
                        f"{binding_payload.get('value', '')} [mutated]"
                    )
                else:
                    held = loaded.get("held_out", [])
                    if isinstance(held, list):
                        target = held[0] if held else None
                    elif isinstance(held, Mapping):
                        predictions = held.get("predictions")
                        target = (
                            predictions[0]
                            if isinstance(predictions, list) and predictions
                            else None
                        )
                    else:
                        target = None
                    if not isinstance(target, Mapping):
                        raise VerificationError("mutation control has no held-out case")
                    prediction = target.get("field_prediction", target.get("prediction"))
                    if (
                        isinstance(prediction, Mapping)
                        and isinstance(prediction.get("rows"), list)
                        and prediction["rows"]
                    ):
                        prediction["rows"] = copy.deepcopy(prediction["rows"])
                        first = prediction["rows"][0]
                        name = prediction.get("columns", [None])[0]
                        if name in first:
                            cell = first[name]
                            first[name] = {
                                "kind": "integer",
                                "value": (
                                    0
                                    if cell.get("kind") == "null"
                                    else (
                                        int(cell["value"]) + 1
                                        if int(cell["value"]) < 32
                                        else -32
                                    )
                                ),
                            }
                        else:
                            prediction["rows"] = []
                    else:
                        target["field_prediction"] = {
                            "schema": TABLE_SCHEMA,
                            "columns": ["x"],
                            "rows": [
                                {"x": {"kind": "integer", "value": 0}}
                            ],
                        }
            try:
                verify(loaded)
            except VerificationError as exc:
                print(
                    json.dumps(
                        {
                            "schema": RUN_SCHEMA,
                            "status": "mutation-rejected",
                            "error": str(exc),
                        },
                        sort_keys=True,
                    )
                )
                return 1
            raise VerificationError("mutation control unexpectedly passed")
        result = verify(loaded)
    except (OSError, json.JSONDecodeError, VerificationError, TypeError) as exc:
        print(
            json.dumps(
                {"schema": RUN_SCHEMA, "status": "failed", "error": str(exc)},
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
