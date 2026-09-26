"""Executable typed-teacher apprenticeship over the CassiFI sequence field.

The runner is deliberately bounded: SQLite is an external teacher/verification
oracle and the field only receives typed nullable tables and typed sequence
programs.  No SQL text or oracle receipt is sent to a field operation; the
native model appears only as an identified, coupled observation after the field
chooses its separating study question.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_ROOT = Path(__file__).resolve().parents[2]
_CASSIFI = _ROOT / "CassiFI"
_CASSIQWEN = _ROOT / "CassiQwen"
for _path in (_CASSIFI, _CASSIQWEN):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from cassi_field_program import semantic_program_payload  # noqa: E402
from cassi_field_qwen_workbench import (  # noqa: E402
    COMPUTER_ID,
    CassiFieldWorkMemory,
)
from cassi_field_owner import AuthorityGrant  # noqa: E402
from cassi_model_instrument import QwenNativeInstrument  # noqa: E402
from cassi_sqlite_apprenticeship import (  # noqa: E402
    canonical_table,
    digest_json,
    execute_sqlite_oracle,
    table_from_rows,
)

RECEIPT_SCHEMA = "cassi.sqlite-apprenticeship-run.v1"
TEACHER_ROUTE = "typed-development-proposal"
TABLE_SCHEMA = "cassifi.nullable-table.v1"
SEQUENCE_SCHEMA = "cassifi.semantic-sequence-program.v1"
NATIVE_EXECUTABLE = _CASSIQWEN / "native" / "llama.cpp" / "b8" / "bin" / "Release" / "cassi-qwen.exe"
NATIVE_MODEL = _CASSIQWEN / "Qwen3.5-0.8B-Q4_0.gguf"
NATIVE_STATE = _CASSIQWEN / "_diag" / "latent-reasoning" / "zero-state-4scale.f32"


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

_LANGUAGE_TEACHER_LINE = re.compile(
    r"^N=([05]); keep above ([05]); unique; (ascending|descending); "
    r"first ([23]); mode filter$"
)
_LANGUAGE_RECIPE_TEACHER_LINE = re.compile(
    r"^mode recursive depth ([23])$"
)
_LANGUAGE_PARAMETRIC_RECIPE_KEY = "recursive-parametric"
_LANGUAGE_PARAMETRIC_RECIPE_FAMILY = "recursive"
_LANGUAGE_PARAMETRIC_RECIPE_TEXT = "mode recursive depth"
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


def _language_parametric_recipe_meaning() -> dict[str, Any]:
    return {
        "component_kind": "query-recipe",
        "role": "stage_recipe",
        "recipe_schema": _LANGUAGE_STAGE_RECIPE_SCHEMA,
        "recipe_key": _LANGUAGE_PARAMETRIC_RECIPE_KEY,
        "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
        "stage_component_key": "stage_order",
        "recipe": _LANGUAGE_PARAMETRIC_RECIPE_TEMPLATE,
    }


def _native_visible_text(output: str) -> str:
    """Remove the native chat template's private think segment."""
    if not isinstance(output, str) or not output.strip():
        raise RuntimeError("native language teacher emitted no text")
    has_open = "<think>" in output
    has_close = "</think>" in output
    if has_open != has_close:
        raise RuntimeError("native language teacher emitted an unclosed think segment")
    if has_open:
        match = re.fullmatch(r"(?s)\s*<think>.*?</think>\s*(.*)\s*", output)
        if match is None:
            raise RuntimeError("native language teacher think segment is malformed")
        output = match.group(1)
    visible = output.strip()
    if not visible:
        raise RuntimeError("native language teacher emitted no visible text")
    return visible


def _parse_language_teacher_output(
    output: str,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Admit the bounded component and parametric-recipe lesson."""
    visible = _native_visible_text(output)
    lines = visible.splitlines()
    if (
        not 4 <= len(lines) <= 8
        or (len(lines) - 2) % 2 != 0
        or any(not line.strip() for line in lines)
    ):
        raise RuntimeError("native language teacher emitted an unbounded lesson")
    examples: list[dict[str, Any]] = []
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
            raise RuntimeError("native language teacher emitted an unsupported lesson")
        examples.append(
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
    recipe_examples: list[dict[str, Any]] = []
    for index, line in enumerate(lines[2:]):
        expected_depth = ("2", "3")[index % 2]
        text = line.strip()
        match = _LANGUAGE_RECIPE_TEACHER_LINE.fullmatch(text)
        if match is None or match.group(1) != expected_depth:
            raise RuntimeError(
                "native language teacher emitted an unsupported recipe lesson"
            )
        if len(recipe_examples) < 2:
            recipe_examples.append(
                {
                    "text": text,
                    "bindings": {
                        "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
                        "repeat_count": expected_depth,
                    },
                }
            )
    return visible, examples, recipe_examples



def _literal(value: int | None) -> dict[str, Any]:
    return {"op": "literal", "value": value}


def _expression(ast: Mapping[str, Any]) -> dict[str, Any]:
    kind = ast.get("kind")
    if kind == "column":
        return {"op": "column", "name": str(ast["name"])}
    if kind == "literal":
        return _literal(ast.get("value"))
    if kind == "coalesce":
        return {
            "op": "coalesce",
            "args": [_expression(ast["first"]), _expression(ast["second"])],
        }
    raise ValueError(f"unsupported SQL AST expression kind: {kind!r}")


def _predicate(ast: Mapping[str, Any]) -> dict[str, Any]:
    kind = ast.get("kind")
    if kind == "is_null":
        if bool(ast.get("negate")):
            raise ValueError("IS NOT NULL is outside this bounded sequence route")
        return {"op": "is_null", "expr": _expression(ast["expression"])}
    if kind == "compare":
        operators = {"=": "eq", "!=": "ne", "<>": "ne", "<": "lt", ">": "gt"}
        operator = operators.get(str(ast.get("operator")))
        if operator is None:
            raise ValueError("SQL comparison is outside this bounded sequence route")
        return {
            "op": operator,
            "left": _expression(ast["left"]),
            "right": _expression(ast["right"]),
        }
    raise ValueError(f"unsupported SQL AST predicate kind: {kind!r}")


def sql_ast_to_sequence_ast(ast: Mapping[str, Any]) -> dict[str, Any]:
    """Lower a bounded teacher SQL AST into the field sequence grammar."""
    if not isinstance(ast, Mapping):
        raise ValueError("SQL AST must be a mapping")
    source = ast.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("SQL AST source is invalid")
    source_kind = source.get("kind")
    if source_kind == "readings":
        input_ast: dict[str, Any] = {"op": "source"}
    elif source_kind == "query":
        nested = source.get("query")
        if not isinstance(nested, Mapping):
            raise ValueError("nested SQL AST source is invalid")
        input_ast = sql_ast_to_sequence_ast(nested)
    else:
        raise ValueError("SQL AST source must be readings or a nested query")
    stages: list[dict[str, Any]] = []
    where = ast.get("where")
    if where is not None:
        stages.append({"op": "filter", "predicate": _predicate(where)})
    selected = ast.get("select")
    if not isinstance(selected, list) or not selected:
        raise ValueError("SQL AST must select at least one expression")
    columns: dict[str, Any] = {}
    for item in selected:
        if not isinstance(item, Mapping):
            raise ValueError("SQL AST select item is invalid")
        expression = item["expression"]
        name = item.get("alias")
        if not name:
            if not isinstance(expression, Mapping) or expression.get("kind") != "column":
                raise ValueError("non-column select expressions require an alias")
            name = expression["name"]
        columns[str(name)] = _expression(expression)
    if list(columns) != sorted(set(columns)):
        raise ValueError("SQL AST output columns must be sorted and unique")
    stages.append({"op": "project", "columns": columns})
    if ast.get("distinct"):
        stages.append({"op": "distinct"})
    order = ast.get("order")
    if order is not None:
        nulls = order.get("nulls") or (
            "first" if order.get("direction", "ASC") == "ASC" else "last"
        )
        stages.append(
            {
                "op": "order",
                "expression": _expression(order["expression"]),
                "direction": str(order.get("direction", "ASC")).lower(),
                "nulls": str(nulls).lower(),
            }
        )
    if ast.get("limit") is not None:
        stages.append({"op": "limit", "count": int(ast["limit"])})
    return {"op": "pipeline", "input": input_ast, "stages": stages}


def sequence_composer_program() -> dict[str, Any]:
    """Build the reusable field-owned interpreter for typed sequence plans."""
    return semantic_program_payload(
        program_kind="sequence",
        body={
            "schema": SEQUENCE_SCHEMA,
            "ast": {"op": "source"},
            "ast_parameter": "query_ast",
        },
        arguments={
            "query_ast": {"required": True, "type": "mapping", "units": None},
            "table": {"required": True, "type": "mapping", "units": None},
        },
        reads=["action.query_ast", "action.table"],
        emits=["table"],
        max_work=4096,
        max_horizon=1,
        max_branches=4,
    )


def sequence_program_from_ast(ast: Mapping[str, Any]) -> dict[str, Any]:
    return semantic_program_payload(
        program_kind="sequence",
        body={"schema": SEQUENCE_SCHEMA, "ast": sql_ast_to_sequence_ast(ast)},
        arguments={"table": {"required": True, "type": "mapping", "units": None}},
        reads=["action.table"],
        emits=["table"],
        max_work=4096,
        max_horizon=1,
        max_branches=4,
    )


def _ast(*, expression: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "select": [{"expression": dict(expression), "alias": "x"}],
        "distinct": False,
        "source": {"kind": "readings", "alias": None},
        "where": None,
        "order": None,
        "limit": None,
    }


_IDENTITY_AST = _ast(expression={"kind": "column", "name": "x"})
_COALESCE_AST = _ast(
    expression={
        "kind": "coalesce",
        "first": {"kind": "column", "name": "x"},
        "second": {"kind": "literal", "value": 0},
    }
)
_COALESCE_ORDER_AST = {
    **_COALESCE_AST,
    "order": {
        "expression": {"kind": "column", "name": "x"},
        "direction": "ASC",
        "nulls": "FIRST",
    },
}
_COALESCE_DISTINCT_ORDER_AST = {
    **_COALESCE_ORDER_AST,
    "distinct": True,
}
_NESTED_LIMIT_DESC_AST = {
    "select": [{"expression": {"kind": "column", "name": "x"}, "alias": None}],
    "distinct": False,
    "source": {
        "kind": "query",
        "query": {**_COALESCE_AST, "limit": 3},
        "alias": "inner_readings",
    },
    "where": None,
    "order": {
        "expression": {"kind": "column", "name": "x"},
        "direction": "DESC",
        "nulls": "FIRST",
    },
    "limit": None,
}
_NESTED_DISTINCT_FILTER_AST = {
    "select": [{"expression": {"kind": "column", "name": "x"}, "alias": None}],
    "distinct": False,
    "source": {
        "kind": "query",
        "query": {
            **_IDENTITY_AST,
            "distinct": True,
            "order": {
                "expression": {"kind": "column", "name": "x"},
                "direction": "ASC",
                "nulls": "FIRST",
            },
            "limit": 3,
        },
        "alias": "inner_readings",
    },
    "where": {
        "kind": "compare",
        "left": {"kind": "column", "name": "x"},
        "operator": ">",
        "right": {"kind": "literal", "value": 0},
    },
    "order": None,
    "limit": None,
}
_LANGUAGE_LIMIT_DISTINCT_AST = {
    "select": [{"expression": {"kind": "column", "name": "x"}, "alias": None}],
    "distinct": True,
    "source": {
        "kind": "query",
        "query": {**_COALESCE_ORDER_AST, "limit": 5},
        "alias": "inner_readings",
    },
    "where": {
        "kind": "compare",
        "left": {"kind": "column", "name": "x"},
        "operator": ">",
        "right": {"kind": "literal", "value": 2},
    },
    "order": None,
    "limit": None,
}
_LANGUAGE_DISTINCT_FILTER_AST = {
    "select": [{"expression": {"kind": "column", "name": "x"}, "alias": None}],
    "distinct": False,
    "source": {
        "kind": "query",
        "query": {**_COALESCE_AST, "distinct": True},
        "alias": "inner_readings",
    },
    "where": {
        "kind": "compare",
        "left": {"kind": "column", "name": "x"},
        "operator": ">",
        "right": {"kind": "literal", "value": 2},
    },
    "order": {
        "expression": {"kind": "column", "name": "x"},
        "direction": "ASC",
        "nulls": "FIRST",
    },
    "limit": 4,
}



_POST_REOPEN_AST = {
    **_COALESCE_AST,
    "limit": 2,
}


def post_reopen_case() -> dict[str, Any]:
    """Return a fresh-value case executed only after the field is reopened."""
    return {
        "case_id": "post-reopen-coalesce-limit",
        "sql": "SELECT COALESCE(x, 0) AS x FROM readings LIMIT 2",
        "ast": _POST_REOPEN_AST,
        "input_rows": [None, 5, -3],
    }
_LANGUAGE_CONSTRUCTION_ID = "construction:fill-filter-distinct-order-limit"
_LANGUAGE_COMPONENT_KEYS = (
    "fill_value",
    "threshold_filter",
    "distinct",
    "order_limit",
    "stage_order",
)

_LANGUAGE_STAGE_RECIPE_SCHEMA = "cassi.language-stage-recipe-catalog.v1"
_LANGUAGE_STAGE_RECIPES: dict[str, dict[str, Any]] = {
    "filter": {
        "layers": [
            ["filter_after_fill", "project_filled", "distinct", "order", "limit"],
        ],
    },
    "limit": {
        "layers": [
            ["project_filled", "distinct", "order", "limit"],
            ["filter_on_column", "project_column"],
        ],
    },
    "limit-distinct": {
        "layers": [
            ["project_filled", "order", "limit"],
            ["filter_on_column", "project_column", "distinct"],
        ],
    },
    "distinct-filter": {
        "layers": [
            ["project_filled", "distinct"],
            ["filter_on_column", "project_column", "order", "limit"],
        ],
    },
    "nested-reapply": {
        "layers": [
            ["project_filled", "order", "limit"],
            ["filter_on_column", "project_column", "order", "limit"],
            ["project_column", "distinct"],
        ],
    },
    "recursive-3": {
        "layers": [
            ["project_filled", "order", "limit"],
            {
                "repeat": 3,
                "stages": ["filter_on_column", "project_column", "order", "limit"],
            },
            ["project_column", "distinct"],
        ],
    },
    "recursive-4": {
        "layers": [
            ["project_filled", "order", "limit"],
            {
                "repeat": 4,
                "stages": ["filter_on_column", "project_column", "order", "limit"],
            },
            ["project_column", "distinct"],
        ],
    },
    "weave": {
        "layers": [
            ["project_filled"],
            ["filter_on_column", "project_column", "order"],
            ["project_column", "distinct"],
            ["project_column", "limit"],
        ],
    },
}

_LANGUAGE_RECIPE_KEYS = tuple(_LANGUAGE_STAGE_RECIPES)


def _language_component_specs(
    teaching_examples: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Split the native lesson into separately acquired reusable components."""
    if len(teaching_examples) != 2:
        raise ValueError("component acquisition requires exactly two examples")
    first, second = teaching_examples
    first_bindings = first["bindings"]
    second_bindings = second["bindings"]
    return [
        {
            "key": "fill_value",
            "construction_id": "construction:language:component:fill-value",
            "examples": [
                {
                    "text": first_bindings["fill_value"],
                    "bindings": {"fill_value": first_bindings["fill_value"]},
                },
                {
                    "text": second_bindings["fill_value"],
                    "bindings": {"fill_value": second_bindings["fill_value"]},
                },
            ],
            "meaning": {
                "component_kind": "query-role",
                "role": "fill_value",
            },
        },
        {
            "key": "threshold_filter",
            "construction_id": "construction:language:component:threshold-filter",
            "examples": [
                {
                    "text": f"keep above {first_bindings['threshold']}",
                    "bindings": {"threshold": first_bindings["threshold"]},
                },
                {
                    "text": f"keep above {second_bindings['threshold']}",
                    "bindings": {"threshold": second_bindings["threshold"]},
                },
            ],
            "meaning": {
                "component_kind": "query-role",
                "role": "threshold",
            },
        },
        {
            "key": "distinct",
            "construction_id": "construction:language:component:distinct",
            "examples": [
                {"text": "unique", "bindings": {}},
                {"text": "unique", "bindings": {}},
            ],
            "meaning": {
                "component_kind": "query-stage",
                "stage": "distinct",
            },
        },
        {
            "key": "order_limit",
            "construction_id": "construction:language:component:order-limit",
            "examples": [
                {
                    "text": (
                        f"{first_bindings['order_direction']}; first "
                        f"{first_bindings['row_limit']}"
                    ),
                    "bindings": {
                        "order_direction": first_bindings["order_direction"],
                        "row_limit": first_bindings["row_limit"],
                    },
                },
                {
                    "text": (
                        f"{second_bindings['order_direction']}; first "
                        f"{second_bindings['row_limit']}"
                    ),
                    "bindings": {
                        "order_direction": second_bindings["order_direction"],
                        "row_limit": second_bindings["row_limit"],
                    },
                },
            ],
            "meaning": {
                "component_kind": "query-roles",
                "roles": ["order_direction", "row_limit"],
            },
        },
        {
            "key": "stage_order",
            "construction_id": "construction:language:component:stage-order",
            "examples": [
                {
                    "text": f"mode {first_bindings['stage_arrangement']}",
                    "bindings": {
                        "stage_arrangement": first_bindings["stage_arrangement"]
                    },
                },
                {
                    "text": f"mode {second_bindings['stage_arrangement']}",
                    "bindings": {
                        "stage_arrangement": second_bindings["stage_arrangement"]
                    },
                },
            ],
            "meaning": {
                "component_kind": "query-control",
                "role": "stage_arrangement",
                "recipe_schema": _LANGUAGE_STAGE_RECIPE_SCHEMA,
                "recipe_catalog": _LANGUAGE_STAGE_RECIPES,
            },
        },
    ]

def _language_component_request(
    component: Mapping[str, Any],
    *,
    native_identity_sha256: str,
    operation_id: str,
) -> dict[str, Any]:
    return {
        "operation": "learn-construction",
        "operation_id": operation_id,
        "construction_id": component["construction_id"],
        "examples": component["examples"],
        "meaning": component["meaning"],
        "guards": {
            "component_scope": "component-only",
            "component_key": component["key"],
        },
        "support_roots": [native_identity_sha256],
    }


def _language_recipe_specs() -> list[dict[str, Any]]:
    """Return independently acquirable field-owned recipe entries."""
    return [
        {
            "key": recipe_key,
            "construction_id": f"construction:language:recipe:{recipe_key}",
            "examples": [
                {
                    "text": f"mode {recipe_key}",
                    "bindings": {"stage_arrangement": recipe_key},
                },
                {
                    "text": f"mode {recipe_key}",
                    "bindings": {"stage_arrangement": recipe_key},
                },
            ],
            "meaning": {
                "component_kind": "query-recipe",
                "role": "stage_recipe",
                "recipe_schema": _LANGUAGE_STAGE_RECIPE_SCHEMA,
                "recipe_key": recipe_key,
                "stage_component_key": "stage_order",
                "recipe": _LANGUAGE_STAGE_RECIPES[recipe_key],
            },
        }
        for recipe_key in _LANGUAGE_RECIPE_KEYS
    ]
def _language_parametric_recipe_spec(
    teaching_examples: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if len(teaching_examples) != 2:
        raise ValueError("parametric recipe acquisition requires two examples")
    expected = (
        {"recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY, "repeat_count": "2"},
        {"recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY, "repeat_count": "3"},
    )
    examples = [dict(example) for example in teaching_examples]
    if [example.get("bindings") for example in examples] != list(expected):
        raise ValueError("native recipe lesson has unexpected bindings")
    return {
        "key": _LANGUAGE_PARAMETRIC_RECIPE_KEY,
        "construction_id": (
            "construction:language:recipe:"
            f"{_LANGUAGE_PARAMETRIC_RECIPE_KEY}"
        ),
        "examples": examples,
        "meaning": _language_parametric_recipe_meaning(),
    }


def _language_parametric_recipe_request(
    recipe: Mapping[str, Any],
    *,
    native_identity_sha256: str,
    operation_id: str,
) -> dict[str, Any]:
    return {
        "operation": "learn-construction",
        "operation_id": operation_id,
        "construction_id": recipe["construction_id"],
        "examples": recipe["examples"],
        "meaning": recipe["meaning"],
        "guards": {
            "component_scope": "recipe-only",
            "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
        },
        "support_roots": [native_identity_sha256],
    }



def _language_recipe_request(
    recipe: Mapping[str, Any],
    *,
    native_identity_sha256: str,
    operation_id: str,
) -> dict[str, Any]:
    return {
        "operation": "learn-construction",
        "operation_id": operation_id,
        "construction_id": recipe["construction_id"],
        "examples": recipe["examples"],
        "meaning": recipe["meaning"],
        "guards": {
            "component_scope": "recipe-only",
            "recipe_key": recipe["key"],
        },
        "support_roots": [native_identity_sha256],
    }


def _language_construction_dependencies(
    component_references: Mapping[str, Mapping[str, Any]],
    recipe_references: Mapping[str, Mapping[str, Any]],
    parametric_recipe_reference: Mapping[str, Any] | None = None,
) -> list[Mapping[str, Any]]:
    if (
        set(component_references) != set(_LANGUAGE_COMPONENT_KEYS)
        or set(recipe_references) != set(_LANGUAGE_RECIPE_KEYS)
        or (
            parametric_recipe_reference is not None
            and not isinstance(parametric_recipe_reference, Mapping)
        )
    ):
        raise ValueError("language construction dependencies are incomplete")
    return [component_references[key] for key in _LANGUAGE_COMPONENT_KEYS]


def _language_composed_meaning(
    component_references: Mapping[str, Mapping[str, Any]],
    recipe_references: Mapping[str, Mapping[str, Any]],
    parametric_recipe_reference: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if (
        set(component_references) != set(_LANGUAGE_COMPONENT_KEYS)
        or set(recipe_references) != set(_LANGUAGE_RECIPE_KEYS)
        or (
            parametric_recipe_reference is not None
            and not isinstance(parametric_recipe_reference, Mapping)
        )
    ):
        raise ValueError("composed meaning is missing a component reference")
    stage_recipes: dict[str, Any] = {
        "schema": _LANGUAGE_STAGE_RECIPE_SCHEMA,
        "component_key": "stage_order",
        "component": dict(component_references["stage_order"]),
        "catalog": _LANGUAGE_STAGE_RECIPES,
        "entries": {
            key: {
                "construction": dict(recipe_references[key]),
                "recipe": _LANGUAGE_STAGE_RECIPES[key],
            }
            for key in _LANGUAGE_RECIPE_KEYS
        },
    }
    if parametric_recipe_reference is not None:
        stage_recipes["parametric"] = {
            "family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
            "recipe_key": _LANGUAGE_PARAMETRIC_RECIPE_KEY,
            "construction": dict(parametric_recipe_reference),
        }
    return {
        "program_kind": "component-composition",
        "components": [
            {
                "key": key,
                "construction": dict(component_references[key]),
            }
            for key in _LANGUAGE_COMPONENT_KEYS
        ],
        "recipe_components": [
            {
                "key": key,
                "construction": dict(recipe_references[key]),
                "recipe": _LANGUAGE_STAGE_RECIPES[key],
            }
            for key in _LANGUAGE_RECIPE_KEYS
        ],
        "bindings": {
            "fill_value": {"$role": "fill_value"},
            "threshold": {"$role": "threshold"},
            "order_direction": {"$role": "order_direction"},
            "row_limit": {"$role": "row_limit"},
        },
        "stage_arrangement": {"$role": "stage_arrangement"},
        "stage_recipes": stage_recipes,
    }




def language_to_program_fixture(
    *,
    teaching_examples: Sequence[Mapping[str, Any]],
    component_references: Mapping[str, Mapping[str, Any]],
    recipe_references: Mapping[str, Mapping[str, Any]],
    parametric_recipe_reference: Mapping[str, Any],
) -> dict[str, Any]:
    """Build component-composed routes with recursive held-out arrangements."""
    if len(teaching_examples) != 2:
        raise ValueError("language construction requires exactly two teacher examples")
    if not isinstance(parametric_recipe_reference, Mapping):
        raise ValueError("language construction requires a parametric recipe")
    examples = [dict(example) for example in teaching_examples]
    expected_examples = [
        {
            "text": (
                "N=0; keep above 0; unique; ascending; first 2; mode filter"
            ),
            "bindings": {
                "fill_value": "N=0",
                "threshold": "0",
                "order_direction": "ascending",
                "row_limit": "2",
                "stage_arrangement": "filter",
            },
        },
        {
            "text": (
                "N=5; keep above 5; unique; descending; first 3; mode filter"
            ),
            "bindings": {
                "fill_value": "N=5",
                "threshold": "5",
                "order_direction": "descending",
                "row_limit": "3",
                "stage_arrangement": "filter",
            },
        },
    ]
    if examples != expected_examples:
        raise ValueError("language teacher did not supply the component lesson")
    cases = [
        {
            "case_id": "language-heldout-limit-arrangement-7",
            "text": (
                "N=7; keep above 2; unique; ascending; first 4; mode limit"
            ),
            "sql": (
                "SELECT x FROM ("
                "SELECT DISTINCT COALESCE(x, 7) AS x FROM readings "
                "ORDER BY x ASC NULLS FIRST LIMIT 4"
                ") AS inner_readings WHERE x > 2"
            ),
            "input_rows": [None, 2, 7, -1, 3, 4, 5],
            "binding": {
                "fill_value": "7",
                "threshold": "2",
                "order_direction": "ascending",
                "row_limit": "4",
                "stage_arrangement": "limit",
            },
        },
        {
            "case_id": "language-heldout-limit-distinct-7",
            "text": (
                "N=7; keep above 2; unique; ascending; first 5; "
                "mode limit-distinct"
            ),
            "sql": (
                "SELECT DISTINCT x FROM ("
                "SELECT COALESCE(x, 7) AS x FROM readings "
                "ORDER BY x ASC NULLS FIRST LIMIT 5"
                ") AS inner_readings WHERE x > 2"
            ),
            "input_rows": [None, 6, 6, 3, 2, 1, 8],
            "binding": {
                "fill_value": "7",
                "threshold": "2",
                "order_direction": "ascending",
                "row_limit": "5",
                "stage_arrangement": "limit-distinct",
            },
        },
        {
            "case_id": "language-heldout-distinct-filter-7",
            "text": (
                "N=7; keep above 2; unique; ascending; first 4; "
                "mode distinct-filter"
            ),
            "sql": (
                "SELECT x FROM ("
                "SELECT DISTINCT COALESCE(x, 7) AS x FROM readings"
                ") AS inner_readings WHERE x > 2 "
                "ORDER BY x ASC NULLS FIRST LIMIT 4"
            ),
            "input_rows": [None, 2, 7, -1, 3, 4, 5],
            "binding": {
                "fill_value": "7",
                "threshold": "2",
                "order_direction": "ascending",
                "row_limit": "4",
                "stage_arrangement": "distinct-filter",
            },
        },
        {
            "case_id": "language-heldout-nested-reapply-7",
            "text": (
                "N=7; keep above 2; unique; descending; first 5; "
                "mode nested-reapply"
            ),
            "sql": (
                "SELECT DISTINCT x FROM ("
                "SELECT x FROM ("
                "SELECT COALESCE(x, 7) AS x FROM readings "
                "ORDER BY x DESC NULLS FIRST LIMIT 5"
                ") AS inner_readings WHERE x > 2 "
                "ORDER BY x DESC NULLS FIRST LIMIT 5"
                ") AS outer_readings"
            ),
            "input_rows": [None, 6, 6, 3, 2, 1, 8],
            "binding": {
                "fill_value": "7",
                "threshold": "2",
                "order_direction": "descending",
                "row_limit": "5",
                "stage_arrangement": "nested-reapply",
            },
        },
        {
            "case_id": "language-heldout-recursive-3",
            "text": (
                "N=7; keep above 2; unique; descending; first 5; "
                "mode recursive-3"
            ),
            "sql": (
                "SELECT DISTINCT x FROM ("
                "SELECT x FROM ("
                "SELECT x FROM ("
                "SELECT x FROM ("
                "SELECT COALESCE(x, 7) AS x FROM readings "
                "ORDER BY x DESC NULLS FIRST LIMIT 5"
                ") AS inner_readings WHERE x > 2 "
                "ORDER BY x DESC NULLS FIRST LIMIT 5"
                ") AS level_1 WHERE x > 2 "
                "ORDER BY x DESC NULLS FIRST LIMIT 5"
                ") AS level_2 WHERE x > 2 "
                "ORDER BY x DESC NULLS FIRST LIMIT 5"
                ") AS level_3"
            ),
            "input_rows": [None, 9, 9, 7, 5, 3, 1, 8],
            "binding": {
                "fill_value": "7",
                "threshold": "2",
                "order_direction": "descending",
                "row_limit": "5",
                "stage_arrangement": "recursive-3",
            },
        },
        {
            "case_id": "language-heldout-recursive-4",
            "text": (
                "N=9; keep above 4; unique; descending; first 6; "
                "mode recursive-4"
            ),
            "sql": (
                "SELECT DISTINCT x FROM ("
                "SELECT x FROM ("
                "SELECT x FROM ("
                "SELECT x FROM ("
                "SELECT x FROM ("
                "SELECT COALESCE(x, 9) AS x FROM readings "
                "ORDER BY x DESC NULLS FIRST LIMIT 6"
                ") AS inner_readings WHERE x > 4 "
                "ORDER BY x DESC NULLS FIRST LIMIT 6"
                ") AS level_1 WHERE x > 4 "
                "ORDER BY x DESC NULLS FIRST LIMIT 6"
                ") AS level_2 WHERE x > 4 "
                "ORDER BY x DESC NULLS FIRST LIMIT 6"
                ") AS level_3 WHERE x > 4 "
                "ORDER BY x DESC NULLS FIRST LIMIT 6"
                ") AS level_4"
            ),
            "input_rows": [None, 10, 10, 8, 6, 4, 2, 1],
            "binding": {
                "fill_value": "9",
                "threshold": "4",
                "order_direction": "descending",
                "row_limit": "6",
                "stage_arrangement": "recursive-4",
            },
        },
        {
            "case_id": "language-heldout-weave-7",
            "text": (
                "N=7; keep above 2; unique; ascending; first 3; "
                "mode weave"
            ),
            "sql": (
                "SELECT x FROM ("
                "SELECT DISTINCT x FROM ("
                "SELECT x FROM ("
                "SELECT COALESCE(x, 7) AS x FROM readings"
                ") AS inner_readings WHERE x > 2 "
                "ORDER BY x ASC NULLS FIRST"
                ") AS ordered_readings"
                ") AS distinct_readings LIMIT 3"
            ),
            "input_rows": [None, 6, 6, 3, 2, 1, 8],
            "binding": {
                "fill_value": "7",
                "threshold": "2",
                "order_direction": "ascending",
                "row_limit": "3",
                "stage_arrangement": "weave",
            },
        },
        {
            "case_id": "language-heldout-recursive-5",
            "text": (
                "N=11; keep above 5; unique; descending; first 7; "
                "mode recursive-5"
            ),
            "recipe_text": "mode recursive depth 5",
            "sql": (
                "SELECT DISTINCT x FROM ("
                "SELECT x FROM ("
                "SELECT x FROM ("
                "SELECT x FROM ("
                "SELECT x FROM ("
                "SELECT x FROM ("
                "SELECT COALESCE(x, 11) AS x FROM readings "
                "ORDER BY x DESC NULLS FIRST LIMIT 7"
                ") AS inner_readings WHERE x > 5 "
                "ORDER BY x DESC NULLS FIRST LIMIT 7"
                ") AS level_1 WHERE x > 5 "
                "ORDER BY x DESC NULLS FIRST LIMIT 7"
                ") AS level_2 WHERE x > 5 "
                "ORDER BY x DESC NULLS FIRST LIMIT 7"
                ") AS level_3 WHERE x > 5 "
                "ORDER BY x DESC NULLS FIRST LIMIT 7"
                ") AS level_4 WHERE x > 5 "
                "ORDER BY x DESC NULLS FIRST LIMIT 7"
                ") AS level_5"
            ),
            "input_rows": [None, 12, 12, 10, 8, 6, 4, 2],
            "binding": {
                "fill_value": "11",
                "threshold": "5",
                "order_direction": "descending",
                "row_limit": "7",
                "stage_arrangement": "recursive-5",
            },
        },
    ]
    return {
        "construction_id": _LANGUAGE_CONSTRUCTION_ID,
        "meaning": _language_composed_meaning(
            component_references,
            recipe_references,
            parametric_recipe_reference,
        ),
        "examples": examples,
        "case": cases[0],
        "additional_cases": cases[1:],
    }


def _language_integer(value: Any, *, prefix: str = "") -> int:
    if not isinstance(value, str):
        raise ValueError("language role is not text")
    raw = value[len(prefix) :] if prefix and value.startswith(prefix) else value
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise ValueError("language role is not an integer") from exc



def _resolve_language_recipe_roles(
    value: Any,
    bindings: Mapping[str, Any],
) -> Any:
    """Materialize field-interpreted recipe role tokens before compilation."""
    if isinstance(value, Mapping):
        if set(value) == {"$role"}:
            role = value.get("$role")
            if not isinstance(role, str) or role not in bindings:
                raise ValueError("language recipe role is not field-bound")
            bound = bindings[role]
            if not isinstance(bound, str):
                raise ValueError("language recipe role binding is not text")
            return bound
        return {
            key: _resolve_language_recipe_roles(item, bindings)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_resolve_language_recipe_roles(item, bindings) for item in value]
    return value

def _language_filled_expression(fill_value: int) -> dict[str, Any]:
    return {
        "op": "coalesce",
        "args": [
            {"op": "column", "name": "x"},
            {"op": "literal", "value": fill_value},
        ],
    }


def _compile_language_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Compile grounded field component roles into a bounded sequence AST."""
    if plan.get("program_kind") != "component-composition":
        raise ValueError("language interpretation is not a component composition")
    components = plan.get("components")
    if (
        not isinstance(components, list)
        or [item.get("key") for item in components if isinstance(item, Mapping)]
        != list(_LANGUAGE_COMPONENT_KEYS)
        or any(
            not isinstance(item, Mapping)
            or not isinstance(item.get("construction"), Mapping)
            for item in components
        )
    ):
        raise ValueError("language interpretation lost its component references")
    bindings = plan.get("bindings")
    if not isinstance(bindings, Mapping):
        raise ValueError("language interpretation has no grounded bindings")
    fill_value = _language_integer(bindings.get("fill_value"), prefix="N=")
    threshold = _language_integer(bindings.get("threshold"))
    row_limit = _language_integer(bindings.get("row_limit"))
    if not 0 <= row_limit <= 32:
        raise ValueError("language limit is outside the bound")
    direction = bindings.get("order_direction")
    direction_map = {"ascending": "asc", "descending": "desc"}
    if direction not in direction_map:
        raise ValueError("language order direction is invalid")
    stage_recipes = plan.get("stage_recipes")
    if (
        not isinstance(stage_recipes, Mapping)
        or stage_recipes.get("schema") != _LANGUAGE_STAGE_RECIPE_SCHEMA
        or stage_recipes.get("component_key") != "stage_order"
    ):
        raise ValueError("language interpretation has no field-owned stage recipes")
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
        raise ValueError("language stage recipes lost component provenance")
    recipe_catalog = stage_recipes.get("catalog")
    recipe_entries = stage_recipes.get("entries")
    if (
        not isinstance(recipe_catalog, Mapping)
        or not isinstance(recipe_entries, Mapping)
        or not set(recipe_catalog).issubset(set(recipe_entries))
    ):
        raise ValueError("language stage recipe entries are missing")
    arrangement = plan.get("stage_arrangement")
    recipe_entry = recipe_entries.get(arrangement)
    if (
        not isinstance(recipe_entry, Mapping)
        or not isinstance(recipe_entry.get("construction"), Mapping)
    ):
        raise ValueError("language stage recipe entry is not field-backed")
    recipe = recipe_entry.get("recipe")
    if not isinstance(recipe, Mapping):
        raise ValueError(f"language stage recipe is unsupported: {arrangement!r}")
    layers = recipe.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError("language stage recipe has no layers")
    filled = _language_filled_expression(fill_value)
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
        "project_filled": {
            "op": "project",
            "columns": {"x": filled},
        },
        "project_column": {
            "op": "project",
            "columns": {"x": {"op": "column", "name": "x"}},
        },
        "distinct": {"op": "distinct"},
        "order": {
            "op": "order",
            "expression": {"op": "column", "name": "x"},
            "direction": direction_map[direction],
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
                repeat = _language_integer(repeat)
            stage_names = layer.get("stages")
            if isinstance(repeat, bool) or not isinstance(repeat, int) or not 1 <= repeat <= 8:
                raise ValueError("language stage recipe repeat is outside the bound")
        if not isinstance(stage_names, list) or not stage_names:
            raise ValueError("language stage recipe layer is invalid")
        if any(name not in stage_templates for name in stage_names):
            raise ValueError("language stage recipe names an unsupported stage")
        for _ in range(repeat):
            layer_count += 1
            if layer_count > 16:
                raise ValueError("language stage recipe exceeds the nesting bound")
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


def _field_mechanism_request(
    *,
    operation_id: str,
    mechanism_id: str,
    table: Mapping[str, Any],
    query_ast: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "operation": "mechanism-step",
        "operation_id": operation_id,
        "mechanism_id": mechanism_id,
        "state": {},
        "action": {"query_ast": dict(query_ast), "table": dict(table)},
        "context": {},
        "interval": {},
    }

def _language_live_recipe_binding(
    memory: CassiFieldWorkMemory,
    *,
    content: Mapping[str, Any],
    operation_prefix: str,
    case_id: str,
    recipe_text: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Mapping[str, Any], dict[str, Any]]:
    arrangement = content.get("stage_arrangement")
    if not isinstance(arrangement, str):
        raise RuntimeError(f"language case {case_id} has no valid recipe arrangement")
    is_parametric = arrangement not in _LANGUAGE_RECIPE_KEYS
    if is_parametric:
        if not isinstance(recipe_text, str):
            raise RuntimeError(f"language case {case_id} has no parametric recipe text")
        request_text = recipe_text
        permitted_context = {
            "component_scope": "recipe-only",
            "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
        }
        expected_recipe_key = _LANGUAGE_PARAMETRIC_RECIPE_KEY
    else:
        request_text = f"mode {arrangement}"
        permitted_context = {
            "component_scope": "recipe-only",
            "recipe_key": arrangement,
        }
        expected_recipe_key = arrangement
    request = {
        "operation": "interpret",
        "operation_id": f"{operation_prefix}:recipe-interpret:{case_id}",
        "text": request_text,
        "permitted_context": permitted_context,
    }
    result = memory.semantic(request)
    outcome = result.get("result", {})
    interpretation = (
        outcome.get("interpretation") if isinstance(outcome, Mapping) else None
    )
    if not isinstance(interpretation, Mapping):
        raise RuntimeError(f"field recipe support is missing for {arrangement}")
    recipe_content = interpretation.get("content")
    if not isinstance(recipe_content, Mapping):
        raise RuntimeError(f"field recipe {arrangement} has no grounded content")
    if (
        recipe_content.get("component_kind") != "query-recipe"
        or recipe_content.get("recipe_key") != expected_recipe_key
        or recipe_content.get("recipe_schema") != _LANGUAGE_STAGE_RECIPE_SCHEMA
        or (
            is_parametric
            and recipe_content.get("recipe_family")
            != _LANGUAGE_PARAMETRIC_RECIPE_FAMILY
        )
        or not isinstance(recipe_content.get("recipe"), Mapping)
    ):
        raise RuntimeError(f"field recipe {arrangement} has invalid content")
    recipe_bindings = interpretation.get("bindings")
    if not isinstance(recipe_bindings, Mapping):
        recipe_bindings = {}
    materialized_recipe = _resolve_language_recipe_roles(
        recipe_content["recipe"],
        recipe_bindings,
    )
    if not isinstance(materialized_recipe, Mapping):
        raise RuntimeError(f"field recipe {arrangement} did not materialize")
    stage_recipes = content.get("stage_recipes")
    entries = stage_recipes.get("entries") if isinstance(stage_recipes, Mapping) else None
    if not isinstance(entries, Mapping):
        raise RuntimeError(f"language case {case_id} has no recipe entries")
    bound_entries = dict(entries)
    if is_parametric:
        parametric = (
            stage_recipes.get("parametric")
            if isinstance(stage_recipes, Mapping)
            else None
        )
        if (
            not isinstance(parametric, Mapping)
            or parametric.get("family") != _LANGUAGE_PARAMETRIC_RECIPE_FAMILY
            or not isinstance(parametric.get("construction"), Mapping)
        ):
            raise RuntimeError(f"language case {case_id} has no parametric recipe root")
        bound_entry = {
            "construction": interpretation.get("construction"),
            "recipe": materialized_recipe,
            "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
            "bindings": dict(recipe_bindings),
        }
    else:
        if arrangement not in bound_entries:
            raise RuntimeError(f"language case {case_id} has no recipe entry")
        bound_entry = dict(bound_entries[arrangement])
        bound_entry["construction"] = interpretation.get("construction")
        bound_entry["recipe"] = materialized_recipe
    bound_entries[arrangement] = bound_entry
    bound_content = dict(content)
    bound_stage_recipes = dict(stage_recipes)
    bound_stage_recipes["entries"] = bound_entries
    bound_content["stage_recipes"] = bound_stage_recipes
    return request, result, interpretation, bound_content


def _execute_language_case(
    memory: CassiFieldWorkMemory,
    *,
    case: Mapping[str, Any],
    mechanism_id: str,
    operation_prefix: str,
    construction_id: str | None = None,
) -> dict[str, Any]:
    """Interpret and execute one field-owned composed-language case."""
    case_id = str(case["case_id"])
    interpret_request = {
        "operation": "interpret",
        "operation_id": f"{operation_prefix}:interpret:{case_id}",
        "text": case["text"],
    }
    interpret_result = memory.semantic(interpret_request)
    outcome = interpret_result.get("result", {})
    interpretation = (
        outcome.get("interpretation") if isinstance(outcome, Mapping) else None
    )
    if not isinstance(interpretation, Mapping):
        raise RuntimeError(f"field did not interpret language case {case_id}")
    content = interpretation.get("content")
    if not isinstance(content, Mapping):
        raise RuntimeError(f"language case {case_id} has no grounded content")
    (
        recipe_interpret_request,
        recipe_interpret_result,
        recipe_interpretation,
        bound_content,
    ) = _language_live_recipe_binding(
        memory,
        content=content,
        operation_prefix=operation_prefix,
        case_id=case_id,
        recipe_text=(
            str(case["recipe_text"])
            if isinstance(case.get("recipe_text"), str)
            else None
        ),
    )
    program_ast = _compile_language_plan(bound_content)
    if construction_id is not None and interpretation.get("construction_id") != construction_id:
        raise RuntimeError(f"language case {case_id} selected the wrong construction")
    mechanism_request = _field_mechanism_request(
        operation_id=f"{operation_prefix}:mechanism:{case_id}",
        mechanism_id=mechanism_id,
        table=table_from_rows(case["input_rows"]),
        query_ast=program_ast,
    )
    mechanism_result = memory.semantic(mechanism_request)
    mechanism_outcome = mechanism_result.get("result", {}).get("outcome", {})
    output = (
        mechanism_outcome.get("output")
        if isinstance(mechanism_outcome, Mapping)
        else None
    )
    if not isinstance(output, Mapping):
        raise RuntimeError(f"field produced no language prediction for {case_id}")
    output = canonical_table(output)
    oracle = execute_sqlite_oracle(
        table_from_rows(case["input_rows"]),
        case["sql"],
        operation_id=f"{operation_prefix}:oracle:{case_id}",
        max_rows=8,
        timeout_ms=1000,
    )
    if oracle["status"] != "supported" or not isinstance(
        oracle.get("canonical_output"), Mapping
    ):
        raise RuntimeError(f"language oracle did not support {case_id}")
    return {
        "case_id": case_id,
        "interpret_request": interpret_request,
        "interpret_result": interpret_result,
        "interpretation": interpretation,
        "recipe_interpret_request": recipe_interpret_request,
        "recipe_interpret_result": recipe_interpret_result,
        "recipe_interpretation": recipe_interpretation,
        "mechanism_request": mechanism_request,
        "mechanism_result": mechanism_result,
        "query_ast": program_ast,
        "prediction": output,
        "oracle": _canonical_oracle(oracle),
        "prediction_digest": digest_json(output),
        "oracle_digest": oracle["output_digest"],
        "matches_oracle": output == oracle["canonical_output"],
    }


def builtin_tape() -> dict[str, list[dict[str, Any]]]:
    """Return a fresh nullable tape with unseen operation compositions."""
    rows_a = [None, -2, 3]
    rows_b = [None, 1, 4]
    rows_c = [-1, None, 2]
    return {
        "training": [
            {
                "case_id": "train-1",
                "sql": "SELECT COALESCE(x, 0) AS x FROM readings ORDER BY x ASC",
                "ast": _COALESCE_ORDER_AST,
                "input_rows": rows_a,
            },
            {
                "case_id": "train-2",
                "sql": "SELECT COALESCE(x, 0) AS x FROM readings ORDER BY x ASC",
                "ast": _COALESCE_ORDER_AST,
                "input_rows": rows_b,
            },
            {
                "case_id": "train-3",
                "sql": "SELECT COALESCE(x, 0) AS x FROM readings ORDER BY x ASC",
                "ast": _COALESCE_ORDER_AST,
                "input_rows": rows_c,
            },
            {
                "case_id": "train-4",
                "sql": "SELECT DISTINCT COALESCE(x, 0) AS x FROM readings ORDER BY x ASC",
                "ast": _COALESCE_DISTINCT_ORDER_AST,
                "input_rows": [None, None, 3, -1],
            },
        ],
        "held_out": [
            {
                "case_id": "heldout-order-distinct-limit",
                "sql": "SELECT DISTINCT COALESCE(x, 0) AS x FROM readings ORDER BY x ASC LIMIT 2",
                "ast": {**_COALESCE_DISTINCT_ORDER_AST, "limit": 2},
                "input_rows": [None, None, 2, -1],
            },
            {
                "case_id": "heldout-nested-limit-order",
                "sql": "SELECT x FROM (SELECT COALESCE(x, 0) AS x FROM readings LIMIT 3) AS inner_readings ORDER BY x DESC",
                "ast": _NESTED_LIMIT_DESC_AST,
                "input_rows": [None, 4, 1, -2],
            },
            {
                "case_id": "heldout-nested-distinct-filter",
                "sql": "SELECT x FROM (SELECT DISTINCT x AS x FROM readings ORDER BY x ASC NULLS FIRST LIMIT 3) AS inner_readings WHERE x > 0",
                "ast": _NESTED_DISTINCT_FILTER_AST,
                "input_rows": [None, 3, 3, -1],
            },
        ],
    }


def _load_tape(path: Path | None) -> tuple[dict[str, list[dict[str, Any]]], Mapping[str, Any]]:
    if path is None:
        tape = builtin_tape()
        return tape, {"source": "builtin-development-fixture", "sha256": _sha(tape)}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping) or not isinstance(raw.get("training"), list) or not isinstance(raw.get("held_out", raw.get("held-out")), list):
        raise ValueError("teacher JSON must contain training and held_out arrays")
    tape: dict[str, list[dict[str, Any]]] = {}
    for name in ("training", "held_out"):
        source = raw.get(name, raw.get("held-out"))
        assert isinstance(source, list)
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(source):
            if not isinstance(item, Mapping) or not isinstance(item.get("sql"), str) or not isinstance(item.get("ast"), Mapping) or not isinstance(item.get("input_rows"), list):
                raise ValueError(f"teacher JSON {name}[{index}] is invalid")
            normalized.append({"case_id": str(item.get("case_id", f"{name}-{index + 1}")), "sql": item["sql"], "ast": dict(item["ast"]), "input_rows": list(item["input_rows"])})
        tape[name] = normalized
    if not tape["training"] or not tape["held_out"]:
        raise ValueError("teacher JSON training and held_out arrays must be nonempty")
    return tape, {"source": str(path.resolve()), "sha256": _sha(tape)}


def _affordance_payload(program: Mapping[str, Any]) -> dict[str, Any]:
    roles = [
        {"name": "kind", "required": True, "value_type": "string", "units": None, "bounds": None, "binding_constraints": {}},
        {"name": "question", "required": True, "value_type": "object", "units": None, "bounds": None, "binding_constraints": {}},
        {"name": "question_id", "required": True, "value_type": "string", "units": None, "bounds": None, "binding_constraints": {}},
    ]
    return {
        "program_role": "affordance", "program": dict(program), "argument_roles": roles,
        "preconditions": {"observable": [], "latent": [], "semantics": "set", "probability_model": None},
        "execution": {"duration": {"lower": 0, "upper": 1, "units": "step"}, "concurrency": {}, "resource_occupancy": [], "termination_conditions": []},
        "effects": {"intended": {}, "expected_observations": [], "failure_modes": [], "possible_side_effects": []},
        "action_context_support": [], "reversibility": {"mode": "reversible", "compensation": None},
        "risk": {"minimum": 0, "possible_harms": [], "units": "unit"},
        "obligations": {"authority": [], "disclosure": [], "source_access": []},
    }


def _register(memory: CassiFieldWorkMemory, record_id: str, payload: Mapping[str, Any], role: str, index: int) -> Mapping[str, Any]:
    return memory.semantic({
        "operation": "register", "operation_id": f"sqlite-apprenticeship:register:{index}:{record_id}",
        "record_id": record_id, "kind": "Program", "payload": {**dict(payload), "program_role": role},
        "epistemic_kind": "derived", "scope": "sqlite-apprenticeship", "support_roots": [],
    })


def _authorized_semantic(
    memory: CassiFieldWorkMemory,
    request: Mapping[str, Any],
    proposal: Mapping[str, Any],
    *,
    label: str,
    grant: AuthorityGrant,
) -> Mapping[str, Any]:
    """Run an action lifecycle operation through the owner's authorized seam.

    The owner injects the validated authority into the semantic request.  This
    is still the cognition.field ``authorize-action``/``dispatch-action``
    operation, but avoids treating an external effect as an ordinary invoke.
    """
    owner_result = memory.owner.operate_computer(
        str(request["operation_id"]),
        computer_id=COMPUTER_ID,
        action="authorized-invoke",
        arguments={
            "arguments": dict(request),
            "grant": grant.as_dict(),
            "scope": str(proposal["scope"]),
            "target": str(proposal["target"]),
            "steps": 1,
        },
        expected_state_sha256=memory.owner.state.state_sha256,
    )
    inspected = memory._settle_semantic(
        label=label,
        inspected=memory._computer_inspect(),
    )
    task = inspected.get("task")
    if not isinstance(task, Mapping) or not isinstance(task.get("last_result"), Mapping):
        raise RuntimeError(f"authorized semantic operation produced no result: {label}")
    return {
        "schema": "cassi.field-qwen.semantic-operation.v1",
        "operation": request["operation"],
        "operation_id": request["operation_id"],
        "result": task["last_result"],
        "field_state_sha256": inspected.get("state_sha256"),
        "checkpoint_receipt": inspected.get("checkpoint_receipt"),
        "authorized_owner_receipt": owner_result,
        "authority_grant": grant.as_dict(),
    }


def _canonical_oracle(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {key: receipt.get(key) for key in ("status", "canonical_output", "output_digest", "input_digest", "operation_id_digest", "runtime", "sqlite_version", "sqlite_source_id")}


def run_apprenticeship(*, out: Path, teacher_json: Path | None = None) -> dict[str, Any]:
    tape, teacher = _load_tape(teacher_json)
    language_fixture: Mapping[str, Any]
    language_learning_request: Mapping[str, Any]
    language_learning: Mapping[str, Any]
    language_reference: Mapping[str, Any]
    language_reopen: Mapping[str, Any]
    language_state_before: Mapping[str, Any]
    language_state_after: Mapping[str, Any]
    language_persistence_equal: bool
    language_program_ast: dict[str, Any]
    language_prediction: Mapping[str, Any]
    language_interpretation: Mapping[str, Any]
    language_interpret_request: Mapping[str, Any]
    language_mechanism_request: Mapping[str, Any]
    language_mechanism_result: Mapping[str, Any]
    language_oracle: Mapping[str, Any]
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=True)
    memory_home = out / "field-memory"
    programs = {
        "mechanism-identity": sequence_program_from_ast(_IDENTITY_AST),
        "mechanism-coalesce-zero": sequence_program_from_ast(_COALESCE_AST),
        "mechanism-coalesce-order": sequence_program_from_ast(_COALESCE_ORDER_AST),
        "mechanism-sequence-composer": sequence_composer_program(),
    }
    if len(programs) > 4:
        raise ValueError("bounded sequence apprenticeship accepts at most four candidates")
    heldout_query_asts = {
        str(case["case_id"]): sql_ast_to_sequence_ast(case["ast"])
        for case in tape["held_out"]
    }
    static_candidate_asts = {
        _sha(program["body"]["ast"])
        for program in programs.values()
        if "ast_parameter" not in program["body"]
    }
    if any(
        _sha(query_ast) in static_candidate_asts
        for query_ast in heldout_query_asts.values()
    ):
        raise ValueError("candidate pool contains a held-out sequence AST")
    before: Mapping[str, Any]
    after: Mapping[str, Any]
    frontier_receipts: list[Mapping[str, Any]] = []
    ack_receipts: list[Mapping[str, Any]] = []
    native_prompt: str
    native_trial: Mapping[str, Any]
    native_observation_request: Mapping[str, Any]
    native_observation_receipt: Mapping[str, Any]
    native_observation_query_request: Mapping[str, Any]
    native_observation_query_receipt: Mapping[str, Any]
    native_binding_query_request: Mapping[str, Any]
    native_binding_query_receipt: Mapping[str, Any]
    native_evidence_update_request: Mapping[str, Any]
    native_evidence_update_receipt: Mapping[str, Any]
    native_evidence_query_request: Mapping[str, Any]
    native_evidence_query_receipt: Mapping[str, Any]
    native_language_teacher_prompt: str
    native_language_teacher_trial: Mapping[str, Any]
    native_language_teacher_visible_output: str
    native_language_teacher_examples: list[dict[str, Any]]
    training_rows: list[dict[str, Any]] = []
    route_receipt: Mapping[str, Any]
    route_reference: Mapping[str, Any]
    route_query_request: Mapping[str, Any]
    route_query_receipt: Mapping[str, Any]
    with CassiFieldWorkMemory(memory_home) as memory:
        before = memory.state_receipt()
        affordance_program = semantic_program_payload(program_kind="sequence", body={"schema": SEQUENCE_SCHEMA, "ast": {"op": "pipeline", "input": {"op": "source"}, "stages": []}}, arguments={"kind": {"required": True, "type": "string", "units": None}}, reads=[], emits=["table"], max_work=64, max_horizon=1, max_branches=4)
        _register(memory, "affordance-sequence-table", _affordance_payload(affordance_program), "affordance", 0)
        for index, identity in enumerate(programs, 1):
            _register(memory, identity, {"program_role": "mechanism", "program": programs[identity], "causal_authority": True}, "mechanism", index)
        for index, case in enumerate(tape["training"], 1):
            table = table_from_rows(case["input_rows"])
            oracle = execute_sqlite_oracle(
                table, case["sql"],
                operation_id=f"sqlite-apprenticeship:teacher:{case['case_id']}",
                max_rows=8, timeout_ms=1000,
            )
            if oracle["status"] != "supported" or not isinstance(oracle.get("canonical_output"), Mapping):
                raise RuntimeError(f"teacher oracle did not support {case['case_id']}")
            query_ast = sql_ast_to_sequence_ast(case["ast"])
            request = {
                "operation": "sequence-frontier",
                "operation_id": f"sqlite-apprenticeship:frontier:{case['case_id']}",
                "frontier_id": f"frontier:{case['case_id']}",
                "affordance_id": "affordance-sequence-table",
                "candidates": [
                    {"candidate_id": ident, "program": program, "structural_cost": cost}
                    for cost, (ident, program) in enumerate(programs.items(), 1)
                ],
                "input_table": table,
                "query_ast": query_ast,
                "scope": "sqlite-apprenticeship",
                "target": "sqlite-readings",
                "context": {"teacher_route": TEACHER_ROUTE},
                "question_choice": "field-directed-v1",
                "support_roots": [],
            }
            frontier = memory.semantic(request)
            proposal = frontier.get("result", {}).get("inquiry", {}).get("proposal")
            if not isinstance(proposal, Mapping):
                raise RuntimeError(f"sequence-frontier returned no sequence-table proposal for {case['case_id']}")
            action = proposal.get("action")
            question = action.get("question") if isinstance(action, Mapping) else None
            frontier_result = frontier.get("result", {})
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
                not isinstance(question, Mapping)
                or not isinstance(action, Mapping)
                or question.get("kind") != "sequence-table"
                or question.get("question_role") != "separating"
                or question.get("frontier_id") != request["frontier_id"]
                or question.get("input_table") != table
                or not isinstance(question_choice, Mapping)
                or question_choice.get("mode") != "field-directed-v1"
                or question_choice.get("selected_question_id")
                != action.get("question_id")
                or not isinstance(question_candidates, list)
                or len(question_candidates) != 2
                or action.get("question_id") not in question_candidates
            ):
                raise RuntimeError(f"field did not choose the separating sequence question for {case['case_id']}")
            frontier_receipts.append({"request": request, "response": frontier})
            proposal_id = str(proposal["proposal_id"])
            grant = AuthorityGrant(
                grant_id=f"grant:{proposal_id[:32]}",
                issuer="typed-development-fixture",
                generation=memory.owner.authority_generation,
                operation="computer-effect",
                target=str(proposal["target"]),
                scope=str(proposal["scope"]),
                one_use=False,
            )
            authorized_request = {
                "operation": "authorize-action",
                "operation_id": f"sqlite-apprenticeship:authorize:{case['case_id']}",
                "proposal_id": proposal_id,
            }
            authorized = _authorized_semantic(
                memory, authorized_request, proposal,
                label=f"authorize:{case['case_id']}", grant=grant,
            )
            dispatch_request = {
                "operation": "dispatch-action",
                "operation_id": f"sqlite-apprenticeship:dispatch:{case['case_id']}",
                "proposal_id": proposal_id,
                "adapter_id": "sqlite-typed-development-teacher",
                "dispatch_id": f"dispatch:{case['case_id']}",
                "idempotency": "guaranteed",
                "idempotency_key": proposal_id,
            }
            dispatch = _authorized_semantic(
                memory, dispatch_request, proposal,
                label=f"dispatch:{case['case_id']}", grant=grant,
            )
            acknowledgment_request = {
                "operation": "acknowledgment",
                "operation_id": f"sqlite-apprenticeship:ack:{case['case_id']}",
                "event_id": f"event:{_sha(case['case_id'])}",
                "proposal_id": proposal_id,
                "status": "succeeded",
                "observation_verified": True,
                "observation": {"table": oracle["canonical_output"]},
                "support_roots": [str(oracle["output_digest"])],
            }
            acknowledgment = memory.semantic(acknowledgment_request)
            ack_receipts.append({
                "authorized_request": authorized_request, "authorized": authorized,
                "dispatch_request": dispatch_request, "dispatch": dispatch,
                "acknowledgment_request": acknowledgment_request,
                "acknowledgment": acknowledgment,
            })
            observed_ref = acknowledgment.get("result", {}).get("sequence_frontier")
            if not isinstance(observed_ref, Mapping):
                raise RuntimeError(f"acknowledgment did not update frontier for {case['case_id']}")
            query_request = {
                "operation": "query",
                "operation_id": f"sqlite-apprenticeship:query:{case['case_id']}",
                "query": {"kind": "record", "reference": observed_ref},
            }
            queried = memory.semantic(query_request)
            candidates = queried.get("result", {}).get("record", {}).get("payload", {}).get("candidates", [])
            supported = [
                str(row["candidate_id"]) for row in candidates
                if isinstance(row, Mapping) and row.get("support_status") == "supported"
            ]
            if not supported:
                raise RuntimeError(f"teacher observation supported no candidate for {case['case_id']}")
            training_rows.append({
                "case": case, "input_table": table, "candidate_programs": programs,
                "oracle": _canonical_oracle(oracle), "frontier_request": request,
                "frontier_response": frontier, "observed_frontier": observed_ref,
                "support_query_request": query_request, "support_query": queried,
                "supported_candidates": sorted(supported),
            })
        route_request = {
            "operation": "sequence-route",
            "operation_id": "sqlite-apprenticeship:sequence-route",
            "route_id": "route:sqlite-apprenticeship:training",
            "frontier_refs": [
                row["observed_frontier"] for row in training_rows
            ],
            "scope": "sqlite-apprenticeship",
            "target": "sqlite-readings",
            "support_roots": [],
        }
        route_receipt = memory.semantic(route_request)
        route_result = route_receipt.get("result", {})
        route_reference = (
            route_result.get("route") if isinstance(route_result, Mapping) else None
        )
        if (
            not isinstance(route_result, Mapping)
            or route_result.get("status") != "supported"
            or not isinstance(route_reference, Mapping)
        ):
            raise RuntimeError("field route did not support a candidate")
        route_query_request = {
            "operation": "query",
            "operation_id": "sqlite-apprenticeship:sequence-route-query",
            "query": {"kind": "record", "reference": route_reference},
        }
        route_query_receipt = memory.semantic(route_query_request)
        route_record = route_query_receipt.get("result", {}).get("record", {})
        route_payload = route_record.get("payload", {}) if isinstance(
            route_record, Mapping
        ) else {}
        selected_identity = (
            route_payload.get("selected_candidate")
            if isinstance(route_payload, Mapping)
            else None
        )
        support_counts_raw = (
            route_payload.get("support_counts")
            if isinstance(route_payload, Mapping)
            else None
        )
        if (
            not isinstance(selected_identity, str)
            or selected_identity not in programs
            or not isinstance(support_counts_raw, Mapping)
            or set(support_counts_raw) != set(programs)
            or route_result.get("selected_candidate") != selected_identity
            or route_result.get("support_counts") != dict(support_counts_raw)
        ):
            raise RuntimeError("field route returned an invalid candidate selection")
        if not frontier_receipts:
            raise RuntimeError("field-directed question choice produced no frontier receipt")
        first_frontier_response = frontier_receipts[0]["response"]
        first_frontier_result = first_frontier_response.get("result", {})
        first_question_choice = (
            first_frontier_result.get("question_choice")
            if isinstance(first_frontier_result, Mapping)
            else None
        )
        if not isinstance(first_question_choice, Mapping):
            raise RuntimeError("field-directed question choice was not persisted")
        selected_question_id = first_question_choice.get("selected_question_id")
        question_candidates = first_frontier_result.get("question_candidates")
        if (
            not isinstance(selected_question_id, str)
            or not isinstance(question_candidates, list)
            or len(question_candidates) != 2
            or selected_question_id not in question_candidates
        ):
            raise RuntimeError("field-directed question choice has invalid candidates")
        native_prompt = (
            "Bounded native observation for the Cassi apprenticeship. "
            "The field selected question "
            f"{selected_question_id} from candidates {question_candidates}. "
            "Return one concise sentence describing why a separating question "
            "is useful when selecting a sequence program. Do not emit SQL."
        )
        native_instrument = QwenNativeInstrument(
            executable=NATIVE_EXECUTABLE,
            model=NATIVE_MODEL,
            state=NATIVE_STATE,
            backend="gpu",
        )
        native_trial = native_instrument.execute(
            mode="coupled",
            prompt=native_prompt,
            tokens=8,
            trial_dir=out / "native-question-observation",
        )
        native_identity = native_trial.get("identity")
        native_identity_sha256 = native_trial.get("identity_sha256")
        native_receipt = native_trial.get("receipt")
        native_output = native_trial.get("output")
        native_ownership = native_trial.get("ownership")
        if (
            native_trial.get("schema") != "cassi.qwen-native-instrument-result.v1"
            or native_trial.get("status") != "staged"
            or native_trial.get("mode") != "coupled"
            or not isinstance(native_identity, Mapping)
            or not isinstance(native_identity_sha256, str)
            or not isinstance(native_receipt, Mapping)
            or not isinstance(native_output, str)
            or not native_output
            or not isinstance(native_ownership, Mapping)
            or native_ownership.get("silent_native_fallback") is not False
            or int(native_ownership.get("qwen_forward_passes", 0)) < 1
        ):
            raise RuntimeError("native Qwen observation did not produce a coupled receipt")
        native_operation_id = "sqlite-apprenticeship:native-observation"
        native_event_id = "event:native-question-observation"
        native_observation_request = {
            "operation": "observe",
            "operation_id": native_operation_id,
            "delivery_id": "delivery:native-question-observation",
            "event_id": native_event_id,
            "observations": [
                {
                    "subject": "qwen-native-questioner",
                    "attribute": "response",
                    "value": native_output,
                    "confidence": 1.0,
                    "epistemic_kind": "observed",
                    "frame": "native-text",
                }
            ],
            "source": {
                "kind": "qwen-native-model",
                "adapter_id": native_identity.get("adapter_id"),
                "identity_sha256": native_identity_sha256,
                "model_sha256": native_identity.get("model_sha256"),
                "runtime_sha256": native_identity.get("runtime_sha256"),
                "prompt_sha256": _sha_text(native_prompt),
                "output_sha256": _sha_text(native_output),
            },
            "scope": "sqlite-apprenticeship",
            "support_roots": [native_identity_sha256],
        }
        native_observation_receipt = memory.semantic(native_observation_request)
        native_observation_result = native_observation_receipt.get("result", {})
        native_event_ref = (
            native_observation_result.get("event")
            if isinstance(native_observation_result, Mapping)
            else None
        )
        native_bindings = (
            native_observation_result.get("bindings")
            if isinstance(native_observation_result, Mapping)
            else None
        )
        if (
            not isinstance(native_event_ref, Mapping)
            or not isinstance(native_bindings, list)
            or len(native_bindings) != 1
            or not isinstance(native_bindings[0], Mapping)
        ):
            raise RuntimeError("native Qwen observation was not admitted as one field binding")
        native_observation_query_request = {
            "operation": "query",
            "operation_id": "sqlite-apprenticeship:native-observation-event-query",
            "query": {"kind": "record", "reference": native_event_ref},
        }
        native_observation_query_receipt = memory.semantic(
            native_observation_query_request
        )
        native_binding_query_request = {
            "operation": "query",
            "operation_id": "sqlite-apprenticeship:native-observation-binding-query",
            "query": {"kind": "record", "reference": native_bindings[0]},
        }
        native_binding_query_receipt = memory.semantic(
            native_binding_query_request
        )
        native_binding_record = native_binding_query_receipt.get("result", {}).get(
            "record", {}
        )
        native_binding_payload = (
            native_binding_record.get("payload", {})
            if isinstance(native_binding_record, Mapping)
            else {}
        )
        if (
            not isinstance(native_binding_payload, Mapping)
            or native_binding_payload.get("value") != native_output
            or native_binding_payload.get("subject") != "qwen-native-questioner"
            or native_binding_payload.get("attribute") != "response"
        ):
            raise RuntimeError("field binding did not preserve native Qwen output")
        native_binding_reference = native_bindings[0]
        native_evidence_update_request = {
            "operation": "learn-predictive-state",
            "operation_id": "sqlite-apprenticeship:native-evidence-update",
            "representation_id": "predictive:native-question-evidence",
            "signature": {
                "clock_boundary": {
                    "domain": "sqlite-apprenticeship",
                    "start": 0,
                    "end": 0,
                },
                "collection_boundary": {
                    "kind": "one-coupled-native-observation",
                    "question_id": selected_question_id,
                },
                "comparison_metric": "native-question-response-exact",
                "horizon": 1,
                "interval": {"start": 0, "end": 0, "units": "observation"},
                "output_measure": {
                    "kind": "native-text",
                    "source": "qwen-native-model",
                },
                "prediction_semantics": "constraint-set",
                "probability_model": None,
                "tolerance": 0,
                "units": "utf8-text",
            },
            "examples": [
                {
                    "action": {
                        "operation": "field-question-selection",
                        "question_id": selected_question_id,
                    },
                    "context": {
                        "question_candidates": list(question_candidates),
                        "source": "qwen-native-model",
                    },
                    "future": {
                        "response": native_output,
                        "output_sha256": _sha_text(native_output),
                    },
                    "future_ref": native_binding_reference,
                    "history": [
                        {
                            "question_candidates": list(question_candidates),
                            "selected_question_id": selected_question_id,
                        }
                    ],
                    "history_ref": native_event_ref,
                    "question": {
                        "question_id": selected_question_id,
                        "question_role": "separating",
                    },
                }
            ],
            "holdout": [],
            "window": 1,
            "support_roots": [native_identity_sha256],
        }
        native_evidence_update_receipt = memory.semantic(
            native_evidence_update_request
        )
        native_evidence_result = native_evidence_update_receipt.get("result", {})
        native_evidence_reference = (
            native_evidence_result.get("representation")
            if isinstance(native_evidence_result, Mapping)
            else None
        )
        if (
            not isinstance(native_evidence_result, Mapping)
            or native_evidence_result.get("status") != "supported"
            or not isinstance(native_evidence_reference, Mapping)
        ):
            raise RuntimeError("native observation did not update field predictive evidence")
        native_evidence_query_request = {
            "operation": "query",
            "operation_id": "sqlite-apprenticeship:native-evidence-query",
            "query": {"kind": "record", "reference": native_evidence_reference},
        }
        native_evidence_query_receipt = memory.semantic(
            native_evidence_query_request
        )
        native_evidence_record = native_evidence_query_receipt.get("result", {}).get(
            "record", {}
        )
        native_evidence_payload = (
            native_evidence_record.get("payload", {})
            if isinstance(native_evidence_record, Mapping)
            else {}
        )
        native_evidence_dependencies = (
            native_evidence_record.get("dependencies", [])
            if isinstance(native_evidence_record, Mapping)
            else []
        )
        if (
            not isinstance(native_evidence_record, Mapping)
            or native_evidence_record.get("kind") != "Program"
            or native_evidence_record.get("id")
            != native_evidence_reference.get("id")
            or not isinstance(native_evidence_payload, Mapping)
            or native_evidence_payload.get("program_role") != "predictive-state"
            or native_identity_sha256
            not in native_evidence_record.get("support_roots", [])
            or not isinstance(native_evidence_dependencies, list)
            or not any(
                isinstance(reference, Mapping)
                and reference.get("id") == native_event_ref.get("id")
                and reference.get("kind") == native_event_ref.get("kind")
                for reference in native_evidence_dependencies
            )
            or not any(
                isinstance(reference, Mapping)
                and reference.get("id") == native_binding_reference.get("id")
                and reference.get("kind") == native_binding_reference.get("kind")
                for reference in native_evidence_dependencies
            )
        ):
            raise RuntimeError("native observation evidence update lost field provenance")
        native_language_teacher_prompt = (
            "Teach four bounded field examples. Emit exactly four lines and no "
            "other text. First use N=0, keep above 0, unique, ascending, first 2, "
            "mode filter; then N=5, keep above 5, unique, descending, first 3, "
            "mode filter. Then emit mode recursive depth 2 and mode recursive "
            "depth 3. Format the first two as N=<number>; keep above <threshold>; "
            "unique; <direction>; first <count>; mode <arrangement>. Format the "
            "last two exactly as mode recursive depth <count>."
        )
        native_language_teacher_trial = native_instrument.execute(
            mode="coupled",
            prompt=native_language_teacher_prompt,
            tokens=80,
            trial_dir=out / "native-language-teacher",
        )
        teacher_identity = native_language_teacher_trial.get("identity")
        teacher_runtime_receipt = native_language_teacher_trial.get("receipt")
        teacher_output = native_language_teacher_trial.get("output")
        teacher_ownership = native_language_teacher_trial.get("ownership")
        if (
            native_language_teacher_trial.get("schema")
            != "cassi.qwen-native-instrument-result.v1"
            or native_language_teacher_trial.get("status") != "staged"
            or native_language_teacher_trial.get("mode") != "coupled"
            or not isinstance(teacher_identity, Mapping)
            or native_language_teacher_trial.get("identity_sha256") != native_identity_sha256
            or not isinstance(teacher_runtime_receipt, Mapping)
            or teacher_runtime_receipt.get("schema")
            != "cassi.qi.native-runtime.v1"
            or teacher_runtime_receipt.get("verdict") != "PASS"
            or not isinstance(teacher_output, str)
            or not isinstance(teacher_ownership, Mapping)
            or teacher_ownership.get("silent_native_fallback") is not False
            or int(teacher_ownership.get("qwen_forward_passes", 0)) < 1
        ):
            raise RuntimeError("native language teacher did not produce a coupled receipt")
        (
            native_language_teacher_visible_output,
            native_language_teacher_examples,
            native_language_recipe_examples,
        ) = _parse_language_teacher_output(teacher_output)
        parametric_recipe_examples = native_language_recipe_examples
        component_specs = _language_component_specs(native_language_teacher_examples)
        component_learning: list[dict[str, Any]] = []
        component_references: dict[str, Mapping[str, Any]] = {}
        for component in component_specs:
            component_request = _language_component_request(
                component,
                native_identity_sha256=native_identity_sha256,
                operation_id=(
                    "sqlite-apprenticeship:language:component:"
                    f"{component['key']}"
                ),
            )
            component_result = memory.semantic(component_request)
            result_payload = component_result.get("result", {})
            component_reference = (
                result_payload.get("construction")
                if isinstance(result_payload, Mapping)
                else None
            )
            if (
                not isinstance(result_payload, Mapping)
                or result_payload.get("status") != "supported"
                or not isinstance(component_reference, Mapping)
            ):
                raise RuntimeError(
                    f"language component was not supported: {component['key']}"
                )
            component_learning.append(
                {"request": component_request, "result": component_result}
            )
            component_references[component["key"]] = component_reference
        recipe_specs = _language_recipe_specs()
        recipe_learning: list[dict[str, Any]] = []
        recipe_references: dict[str, Mapping[str, Any]] = {}
        for recipe in recipe_specs:
            recipe_request = _language_recipe_request(
                recipe,
                native_identity_sha256=native_identity_sha256,
                operation_id=(
                    "sqlite-apprenticeship:language:recipe:"
                    f"{recipe['key']}"
                ),
            )
            recipe_result = memory.semantic(recipe_request)
            result_payload = recipe_result.get("result", {})
            recipe_reference = (
                result_payload.get("construction")
                if isinstance(result_payload, Mapping)
                else None
            )
            if (
                not isinstance(result_payload, Mapping)
                or result_payload.get("status") != "supported"
                or not isinstance(recipe_reference, Mapping)
            ):
                raise RuntimeError(
                    f"language recipe was not supported: {recipe['key']}"
                )
            recipe_learning.append(
                {"request": recipe_request, "result": recipe_result}
            )
            recipe_references[recipe["key"]] = recipe_reference
        parametric_recipe = _language_parametric_recipe_spec(
            parametric_recipe_examples
        )
        parametric_recipe_request = _language_parametric_recipe_request(
            parametric_recipe,
            native_identity_sha256=native_identity_sha256,
            operation_id=(
                "sqlite-apprenticeship:language:recipe:"
                f"{_LANGUAGE_PARAMETRIC_RECIPE_KEY}"
            ),
        )
        parametric_recipe_result = memory.semantic(parametric_recipe_request)
        parametric_result_payload = parametric_recipe_result.get("result", {})
        parametric_recipe_reference = (
            parametric_result_payload.get("construction")
            if isinstance(parametric_result_payload, Mapping)
            else None
        )
        if (
            not isinstance(parametric_result_payload, Mapping)
            or parametric_result_payload.get("status") != "supported"
            or not isinstance(parametric_recipe_reference, Mapping)
        ):
            raise RuntimeError("parametric recipe was not supported")
        parametric_recipe_learning = {
            "request": parametric_recipe_request,
            "result": parametric_recipe_result,
        }
        language_fixture = language_to_program_fixture(
            teaching_examples=native_language_teacher_examples,
            component_references=component_references,
            recipe_references=recipe_references,
            parametric_recipe_reference=parametric_recipe_reference,
        )
        language_learning_request = {
            "operation": "learn-construction",
            "operation_id": "sqlite-apprenticeship:language:learn-composed",
            "construction_id": language_fixture["construction_id"],
            "components": _language_construction_dependencies(
                component_references,
                recipe_references,
                parametric_recipe_reference,
            ),
            "examples": language_fixture["examples"],
            "meaning": language_fixture["meaning"],
            "support_roots": [native_identity_sha256],
        }
        language_learning = memory.semantic(language_learning_request)
        language_result = language_learning.get("result", {})
        if not isinstance(language_result, Mapping) or language_result.get(
            "status"
        ) != "supported":
            raise RuntimeError("language construction was not supported")
        language_reference = language_result.get("construction")
        if not isinstance(language_reference, Mapping):
            raise RuntimeError("language construction produced no field reference")
        support_counts = {
            str(candidate_id): int(count)
            for candidate_id, count in support_counts_raw.items()
        }
        predictions: list[dict[str, Any]] = []
        oracle_rows: list[dict[str, Any]] = []
        for case in tape["held_out"]:
            table = table_from_rows(case["input_rows"])
            query_ast = heldout_query_asts[str(case["case_id"])]
            # The held-out field call receives only the typed table and the
            # typed sequence plan; SQL, oracle receipts, and expected output
            # remain outside the field boundary.
            field_request = {
                "operation": "mechanism-step",
                "operation_id": f"sqlite-apprenticeship:heldout:{case['case_id']}",
                "mechanism_id": selected_identity,
                "state": {},
                "action": {"query_ast": query_ast, "table": table},
                "context": {},
                "interval": {},
            }
            field_result = memory.semantic(field_request)
            outcome = field_result.get("result", {}).get("outcome", {})
            predicted = outcome.get("output") if isinstance(outcome, Mapping) else None
            if not isinstance(predicted, Mapping):
                raise RuntimeError(f"field produced no held-out prediction for {case['case_id']}")
            predicted = canonical_table(predicted)
            oracle = execute_sqlite_oracle(table, case["sql"], operation_id=f"sqlite-apprenticeship:heldout-oracle:{case['case_id']}", max_rows=8, timeout_ms=1000)
            if oracle["status"] != "supported" or not isinstance(oracle.get("canonical_output"), Mapping):
                raise RuntimeError(f"held-out oracle did not support {case['case_id']}")
            predictions.append({"case_id": case["case_id"], "field_request": field_request, "field_result": field_result, "prediction": predicted, "prediction_digest": digest_json(predicted), "oracle_digest": oracle["output_digest"], "matches_oracle": predicted == oracle["canonical_output"]})
            oracle_rows.append({"case_id": case["case_id"], "oracle": _canonical_oracle(oracle)})
        after = memory.state_receipt()
    post_case = post_reopen_case()
    with CassiFieldWorkMemory(memory_home) as reopened:
        reopened_state = reopened.state_receipt()
        post_table = table_from_rows(post_case["input_rows"])
        post_query_ast = sql_ast_to_sequence_ast(post_case["ast"])
        post_field_request = _field_mechanism_request(
            operation_id=f"sqlite-apprenticeship:post-reopen:{post_case['case_id']}",
            mechanism_id=selected_identity,
            table=post_table,
            query_ast=post_query_ast,
        )
        post_field_result = reopened.semantic(post_field_request)
        post_outcome = post_field_result.get("result", {}).get("outcome", {})
        post_predicted = post_outcome.get("output") if isinstance(post_outcome, Mapping) else None
        if not isinstance(post_predicted, Mapping):
            raise RuntimeError("field produced no post-reopen prediction")
        post_predicted = canonical_table(post_predicted)
        post_oracle = execute_sqlite_oracle(
            post_table,
            post_case["sql"],
            operation_id=f"sqlite-apprenticeship:post-reopen-oracle:{post_case['case_id']}",
            max_rows=8,
            timeout_ms=1000,
        )
        if post_oracle["status"] != "supported" or not isinstance(post_oracle.get("canonical_output"), Mapping):
            raise RuntimeError("post-reopen oracle did not support the case")
        post_reopen_prediction = {
            "case_id": post_case["case_id"],
            "field_request": post_field_request,
            "field_result": post_field_result,
            "prediction": post_predicted,
            "oracle": _canonical_oracle(post_oracle),
            "prediction_digest": digest_json(post_predicted),
            "oracle_digest": post_oracle["output_digest"],
            "matches_oracle": post_predicted == post_oracle["canonical_output"],
        }
        post_behavior_after = reopened.state_receipt()
    with CassiFieldWorkMemory(memory_home) as post_behavior_reopened:
        post_behavior_reopened_state = post_behavior_reopened.state_receipt()
    language_case = language_fixture["case"]
    language_additional_cases = language_fixture.get("additional_cases", [])
    if not isinstance(language_additional_cases, list) or len(language_additional_cases) != 7:
        raise RuntimeError("language fixture did not provide seven additional arrangements")
    language_additional_predictions: list[Mapping[str, Any]] = []
    with CassiFieldWorkMemory(memory_home) as language_reopened:
        language_state_before = language_reopened.state_receipt()
        language_prediction = _execute_language_case(
            language_reopened,
            case=language_case,
            mechanism_id=selected_identity,
            operation_prefix="sqlite-apprenticeship:language",
            construction_id=str(language_reference["id"]),
        )
        for additional_case in language_additional_cases:
            language_additional_predictions.append(
                _execute_language_case(
                    language_reopened,
                    case=additional_case,
                    mechanism_id=selected_identity,
                    operation_prefix="sqlite-apprenticeship:language",
                    construction_id=str(language_reference["id"]),
                )
            )
        language_state_after = language_reopened.state_receipt()
    language_program_ast = dict(language_prediction["query_ast"])
    language_interpretation = dict(language_prediction["interpretation"])
    language_interpret_request = dict(language_prediction["interpret_request"])
    language_mechanism_request = dict(language_prediction["mechanism_request"])
    language_mechanism_result = dict(language_prediction["mechanism_result"])
    language_oracle = dict(language_prediction["oracle"])
    with CassiFieldWorkMemory(memory_home) as language_final_reopened:
        language_final_reopen_state = language_final_reopened.state_receipt()
    language_persistence_equal = (
        dict(language_state_after) == dict(language_final_reopen_state)
    )
    language_reopen = {
        "equal": language_persistence_equal,
        "reopened": dict(language_final_reopen_state),
    }
    recovery_case = language_additional_cases[2]
    selective_component_key = "order_limit"
    selective_component_reference = component_references[selective_component_key]
    selective_component = next(
        item for item in component_specs if item["key"] == selective_component_key
    )
    with CassiFieldWorkMemory(memory_home) as selective_memory:
        selective_state_before = selective_memory.state_receipt()
        revoke_request = {
            "operation": "revoke",
            "operation_id": "sqlite-apprenticeship:language:revoke-order-limit",
            "reason": "selective-component-loss",
            "target": dict(selective_component_reference),
        }
        revoke_result = selective_memory.semantic(revoke_request)
        revoke_payload = revoke_result.get("result", {})
        revoked_reference = (
            revoke_payload.get("revoked")
            if isinstance(revoke_payload, Mapping)
            else None
        )
        if (
            not isinstance(revoke_payload, Mapping)
            or revoke_payload.get("status") != "supported"
            or not isinstance(revoked_reference, Mapping)
        ):
            raise RuntimeError("selective component revocation was not supported")
        lost_interpret_request = {
            "operation": "interpret",
            "operation_id": "sqlite-apprenticeship:language:after-order-limit-loss",
            "text": language_case["text"],
        }
        lost_interpret_result = selective_memory.semantic(lost_interpret_request)
        lost_outcome = lost_interpret_result.get("result", {})
        if (
            not isinstance(lost_outcome, Mapping)
            or lost_outcome.get("status") != "support-gap"
            or lost_outcome.get("interpretation") is not None
        ):
            raise RuntimeError("selective component loss did not remove composed support")
        unrelated_interpret_request = {
            "operation": "interpret",
            "permitted_context": {
                "component_scope": "component-only",
                "component_key": "distinct",
            },
            "operation_id": "sqlite-apprenticeship:language:unrelated-distinct",
            "text": "unique",
        }
        unrelated_interpret_result = selective_memory.semantic(
            unrelated_interpret_request
        )
        unrelated_outcome = unrelated_interpret_result.get("result", {})
        unrelated_interpretation = (
            unrelated_outcome.get("interpretation")
            if isinstance(unrelated_outcome, Mapping)
            else None
        )
        if (
            not isinstance(unrelated_outcome, Mapping)
            or unrelated_outcome.get("status") != "supported"
            or not isinstance(unrelated_interpretation, Mapping)
            or unrelated_interpretation.get("construction_id")
            != "construction:language:component:distinct"
        ):
            raise RuntimeError("selective component loss removed an unrelated component")
        reacquire_request = _language_component_request(
            selective_component,
            native_identity_sha256=native_identity_sha256,
            operation_id="sqlite-apprenticeship:language:reacquire-order-limit",
        )
        reacquire_result = selective_memory.semantic(reacquire_request)
        reacquire_payload = reacquire_result.get("result", {})
        reacquired_reference = (
            reacquire_payload.get("construction")
            if isinstance(reacquire_payload, Mapping)
            else None
        )
        if (
            not isinstance(reacquire_payload, Mapping)
            or reacquire_payload.get("status") != "supported"
            or not isinstance(reacquired_reference, Mapping)
            or reacquired_reference == selective_component_reference
        ):
            raise RuntimeError("selective component was not reacquired as a new version")
        recovered_component_references = {
            **component_references,
            selective_component_key: reacquired_reference,
        }
        recovered_learning_request = {
            "operation": "learn-construction",
            "operation_id": "sqlite-apprenticeship:language:recover-composed",
            "construction_id": language_fixture["construction_id"],
            "components": _language_construction_dependencies(
                recovered_component_references,
                recipe_references,
                parametric_recipe_reference,
            ),
            "examples": language_fixture["examples"],
            "meaning": _language_composed_meaning(
                recovered_component_references,
                recipe_references,
                parametric_recipe_reference,
            ),
            "support_roots": [native_identity_sha256],
        }
        recovered_learning = selective_memory.semantic(recovered_learning_request)
        recovered_learning_payload = recovered_learning.get("result", {})
        recovered_reference = (
            recovered_learning_payload.get("construction")
            if isinstance(recovered_learning_payload, Mapping)
            else None
        )
        if (
            not isinstance(recovered_learning_payload, Mapping)
            or recovered_learning_payload.get("status") != "supported"
            or not isinstance(recovered_reference, Mapping)
        ):
            raise RuntimeError("composed construction did not recover after reacquisition")
        recovery_prediction = _execute_language_case(
            selective_memory,
            case=recovery_case,
            mechanism_id=selected_identity,
            operation_prefix="sqlite-apprenticeship:language:recovered",
            construction_id=str(recovered_reference["id"]),
        )
        secondary_component_key = "stage_order"
        secondary_component_reference = component_references[secondary_component_key]
        secondary_component = next(
            item for item in component_specs if item["key"] == secondary_component_key
        )
        secondary_revoke_request = {
            "operation": "revoke",
            "operation_id": "sqlite-apprenticeship:language:revoke-stage-order",
            "reason": "sequential-selective-component-loss",
            "target": dict(secondary_component_reference),
        }
        secondary_revoke_result = selective_memory.semantic(
            secondary_revoke_request
        )
        secondary_revoke_payload = secondary_revoke_result.get("result", {})
        secondary_revoked_reference = (
            secondary_revoke_payload.get("revoked")
            if isinstance(secondary_revoke_payload, Mapping)
            else None
        )
        if (
            not isinstance(secondary_revoke_payload, Mapping)
            or secondary_revoke_payload.get("status") != "supported"
            or not isinstance(secondary_revoked_reference, Mapping)
        ):
            raise RuntimeError("second selective component revocation was not supported")
        secondary_lost_interpret_request = {
            "operation": "interpret",
            "operation_id": "sqlite-apprenticeship:language:after-stage-order-loss",
            "text": recovery_case["text"],
        }
        secondary_lost_interpret_result = selective_memory.semantic(
            secondary_lost_interpret_request
        )
        secondary_lost_outcome = secondary_lost_interpret_result.get("result", {})
        if (
            not isinstance(secondary_lost_outcome, Mapping)
            or secondary_lost_outcome.get("status") != "support-gap"
            or secondary_lost_outcome.get("interpretation") is not None
        ):
            raise RuntimeError("second selective component loss did not remove recovery support")
        secondary_unrelated_text = str(selective_component["examples"][0]["text"])
        secondary_unrelated_interpret_request = {
            "operation": "interpret",
            "permitted_context": {
                "component_scope": "component-only",
                "component_key": selective_component_key,
            },
            "operation_id": "sqlite-apprenticeship:language:unrelated-order-limit",
            "text": secondary_unrelated_text,
        }
        secondary_unrelated_interpret_result = selective_memory.semantic(
            secondary_unrelated_interpret_request
        )
        secondary_unrelated_outcome = secondary_unrelated_interpret_result.get(
            "result", {}
        )
        secondary_unrelated_interpretation = (
            secondary_unrelated_outcome.get("interpretation")
            if isinstance(secondary_unrelated_outcome, Mapping)
            else None
        )
        if (
            not isinstance(secondary_unrelated_outcome, Mapping)
            or secondary_unrelated_outcome.get("status") != "supported"
            or not isinstance(secondary_unrelated_interpretation, Mapping)
            or secondary_unrelated_interpretation.get("construction_id")
            != str(reacquired_reference["id"])
        ):
            raise RuntimeError("second selective loss removed reacquired order-limit support")
        secondary_reacquire_request = _language_component_request(
            secondary_component,
            native_identity_sha256=native_identity_sha256,
            operation_id="sqlite-apprenticeship:language:reacquire-stage-order",
        )
        secondary_reacquire_result = selective_memory.semantic(
            secondary_reacquire_request
        )
        secondary_reacquire_payload = secondary_reacquire_result.get("result", {})
        secondary_reacquired_reference = (
            secondary_reacquire_payload.get("construction")
            if isinstance(secondary_reacquire_payload, Mapping)
            else None
        )
        if (
            not isinstance(secondary_reacquire_payload, Mapping)
            or secondary_reacquire_payload.get("status") != "supported"
            or not isinstance(secondary_reacquired_reference, Mapping)
            or secondary_reacquired_reference == secondary_component_reference
        ):
            raise RuntimeError("second selective component was not reacquired as a new version")
        secondary_component_references = {
            **recovered_component_references,
            secondary_component_key: secondary_reacquired_reference,
        }
        secondary_learning_request = {
            "operation": "learn-construction",
            "operation_id": "sqlite-apprenticeship:language:recover-composed-final",
            "construction_id": language_fixture["construction_id"],
            "components": _language_construction_dependencies(
                secondary_component_references,
                recipe_references,
                parametric_recipe_reference,
            ),
            "examples": language_fixture["examples"],
            "meaning": _language_composed_meaning(
                secondary_component_references,
                recipe_references,
                parametric_recipe_reference,
            ),
            "support_roots": [native_identity_sha256],
        }
        secondary_learning = selective_memory.semantic(secondary_learning_request)
        secondary_learning_payload = secondary_learning.get("result", {})
        secondary_reference = (
            secondary_learning_payload.get("construction")
            if isinstance(secondary_learning_payload, Mapping)
            else None
        )
        if (
            not isinstance(secondary_learning_payload, Mapping)
            or secondary_learning_payload.get("status") != "supported"
            or not isinstance(secondary_reference, Mapping)
        ):
            raise RuntimeError("composed construction did not recover after second reacquisition")
        secondary_recovery_prediction = _execute_language_case(
            selective_memory,
            case=recovery_case,
            mechanism_id=selected_identity,
            operation_prefix="sqlite-apprenticeship:language:recovered-final",
            construction_id=str(secondary_reference["id"]),
        )
        if not secondary_recovery_prediction["matches_oracle"]:
            raise RuntimeError("final sequential recovery prediction did not match the oracle")
        recipe_selective_key = "weave"
        recipe_selective_reference = recipe_references[recipe_selective_key]
        recipe_selective_spec = next(
            item for item in recipe_specs if item["key"] == recipe_selective_key
        )
        recipe_revoke_request = {
            "operation": "revoke",
            "operation_id": "sqlite-apprenticeship:language:revoke-recipe-weave",
            "reason": "selective-recipe-loss",
            "target": dict(recipe_selective_reference),
        }
        recipe_revoke_result = selective_memory.semantic(recipe_revoke_request)
        recipe_revoke_payload = recipe_revoke_result.get("result", {})
        recipe_revoked_reference = (
            recipe_revoke_payload.get("revoked")
            if isinstance(recipe_revoke_payload, Mapping)
            else None
        )
        if (
            not isinstance(recipe_revoke_payload, Mapping)
            or recipe_revoke_payload.get("status") != "supported"
            or not isinstance(recipe_revoked_reference, Mapping)
        ):
            raise RuntimeError("selective recipe revocation was not supported")
        recipe_lost_interpret_request = {
            "operation": "interpret",
            "operation_id": "sqlite-apprenticeship:language:after-weave-recipe-loss",
            "text": "mode weave",
            "permitted_context": {
                "component_scope": "recipe-only",
                "recipe_key": recipe_selective_key,
            },
        }
        recipe_lost_interpret_result = selective_memory.semantic(
            recipe_lost_interpret_request
        )
        recipe_lost_outcome = recipe_lost_interpret_result.get("result", {})
        if (
            not isinstance(recipe_lost_outcome, Mapping)
            or recipe_lost_outcome.get("status") != "support-gap"
            or recipe_lost_outcome.get("interpretation") is not None
        ):
            raise RuntimeError("recipe loss did not remove weave recipe support")
        recipe_unrelated_key = "recursive-3"
        recipe_unrelated_interpret_request = {
            "operation": "interpret",
            "operation_id": (
                "sqlite-apprenticeship:language:unrelated-recipe:"
                f"{recipe_unrelated_key}"
            ),
            "text": f"mode {recipe_unrelated_key}",
            "permitted_context": {
                "component_scope": "recipe-only",
                "recipe_key": recipe_unrelated_key,
            },
        }
        recipe_unrelated_interpret_result = selective_memory.semantic(
            recipe_unrelated_interpret_request
        )
        recipe_unrelated_outcome = recipe_unrelated_interpret_result.get(
            "result", {}
        )
        recipe_unrelated_interpretation = (
            recipe_unrelated_outcome.get("interpretation")
            if isinstance(recipe_unrelated_outcome, Mapping)
            else None
        )
        if (
            not isinstance(recipe_unrelated_outcome, Mapping)
            or recipe_unrelated_outcome.get("status") != "supported"
            or not isinstance(recipe_unrelated_interpretation, Mapping)
            or recipe_unrelated_interpretation.get("construction_id")
            != str(recipe_references[recipe_unrelated_key]["id"])
        ):
            raise RuntimeError("recipe loss removed an unrelated recipe")
        recipe_survivor_case = language_additional_cases[4]
        recipe_survivor_prediction = _execute_language_case(
            selective_memory,
            case=recipe_survivor_case,
            mechanism_id=selected_identity,
            operation_prefix="sqlite-apprenticeship:language:recipe-survivor",
            construction_id=str(secondary_reference["id"]),
        )
        if not recipe_survivor_prediction["matches_oracle"]:
            raise RuntimeError("unrelated recipe failed after weave recipe loss")
        recipe_reacquire_request = _language_recipe_request(
            recipe_selective_spec,
            native_identity_sha256=native_identity_sha256,
            operation_id="sqlite-apprenticeship:language:reacquire-recipe-weave",
        )
        recipe_reacquire_result = selective_memory.semantic(recipe_reacquire_request)
        recipe_reacquire_payload = recipe_reacquire_result.get("result", {})
        recipe_reacquired_reference = (
            recipe_reacquire_payload.get("construction")
            if isinstance(recipe_reacquire_payload, Mapping)
            else None
        )
        if (
            not isinstance(recipe_reacquire_payload, Mapping)
            or recipe_reacquire_payload.get("status") != "supported"
            or not isinstance(recipe_reacquired_reference, Mapping)
            or recipe_reacquired_reference == recipe_selective_reference
        ):
            raise RuntimeError("weave recipe was not reacquired as a new version")
        recovered_recipe_references = {
            **recipe_references,
            recipe_selective_key: recipe_reacquired_reference,
        }
        recipe_recovered_learning_request = {
            "operation": "learn-construction",
            "operation_id": "sqlite-apprenticeship:language:recover-recipe-composed",
            "construction_id": language_fixture["construction_id"],
            "components": _language_construction_dependencies(
                secondary_component_references,
                recovered_recipe_references,
                parametric_recipe_reference,
            ),
            "examples": language_fixture["examples"],
            "meaning": _language_composed_meaning(
                secondary_component_references,
                recovered_recipe_references,
                parametric_recipe_reference,
            ),
            "support_roots": [native_identity_sha256],
        }
        recipe_recovered_learning = selective_memory.semantic(
            recipe_recovered_learning_request
        )
        recipe_recovered_learning_payload = recipe_recovered_learning.get("result", {})
        recipe_recovered_reference = (
            recipe_recovered_learning_payload.get("construction")
            if isinstance(recipe_recovered_learning_payload, Mapping)
            else None
        )
        if (
            not isinstance(recipe_recovered_learning_payload, Mapping)
            or recipe_recovered_learning_payload.get("status") != "supported"
            or not isinstance(recipe_recovered_reference, Mapping)
        ):
            raise RuntimeError("composition did not recover after recipe reacquisition")
        recipe_recovery_case = language_additional_cases[5]
        recipe_recovery_prediction = _execute_language_case(
            selective_memory,
            case=recipe_recovery_case,
            mechanism_id=selected_identity,
            operation_prefix="sqlite-apprenticeship:language:recipe-recovered",
            construction_id=str(recipe_recovered_reference["id"]),
        )
        if not recipe_recovery_prediction["matches_oracle"]:
            raise RuntimeError("recovered weave recipe did not match the oracle")
        parametric_recipe_case = language_additional_cases[6]
        parametric_recipe_reference_before = parametric_recipe_reference
        parametric_recipe_revoke_request = {
            "operation": "revoke",
            "operation_id": (
                "sqlite-apprenticeship:language:revoke-parametric-recipe"
            ),
            "reason": "selective-parametric-recipe-loss",
            "target": dict(parametric_recipe_reference_before),
        }
        parametric_recipe_revoke_result = selective_memory.semantic(
            parametric_recipe_revoke_request
        )
        parametric_recipe_revoked_payload = parametric_recipe_revoke_result.get(
            "result", {}
        )
        parametric_recipe_revoked_reference = (
            parametric_recipe_revoked_payload.get("revoked")
            if isinstance(parametric_recipe_revoked_payload, Mapping)
            else None
        )
        if (
            not isinstance(parametric_recipe_revoked_payload, Mapping)
            or parametric_recipe_revoked_payload.get("status") != "supported"
            or not isinstance(parametric_recipe_revoked_reference, Mapping)
        ):
            raise RuntimeError("parametric recipe revocation was not supported")
        parametric_recipe_lost_interpret_request = {
            "operation": "interpret",
            "operation_id": (
                "sqlite-apprenticeship:language:after-parametric-recipe-loss"
            ),
            "text": str(parametric_recipe_case["recipe_text"]),
            "permitted_context": {
                "component_scope": "recipe-only",
                "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
            },
        }
        parametric_recipe_lost_interpret_result = selective_memory.semantic(
            parametric_recipe_lost_interpret_request
        )
        parametric_recipe_lost_payload = parametric_recipe_lost_interpret_result.get(
            "result", {}
        )
        if (
            not isinstance(parametric_recipe_lost_payload, Mapping)
            or parametric_recipe_lost_payload.get("status") != "support-gap"
            or parametric_recipe_lost_payload.get("interpretation") is not None
        ):
            raise RuntimeError("parametric recipe loss did not create a support gap")
        parametric_recipe_survivor_request = {
            "operation": "interpret",
            "operation_id": (
                "sqlite-apprenticeship:language:parametric-survivor-recipe"
            ),
            "text": "mode recursive-3",
            "permitted_context": {
                "component_scope": "recipe-only",
                "recipe_key": "recursive-3",
            },
        }
        parametric_recipe_survivor_result = selective_memory.semantic(
            parametric_recipe_survivor_request
        )
        parametric_recipe_survivor_payload = (
            parametric_recipe_survivor_result.get("result", {})
        )
        if (
            not isinstance(parametric_recipe_survivor_payload, Mapping)
            or parametric_recipe_survivor_payload.get("status") != "supported"
            or not isinstance(
                parametric_recipe_survivor_payload.get("interpretation"), Mapping
            )
        ):
            raise RuntimeError("parametric recipe loss removed recursive-3")
        parametric_recipe_reacquire_request = _language_parametric_recipe_request(
            parametric_recipe,
            native_identity_sha256=native_identity_sha256,
            operation_id=(
                "sqlite-apprenticeship:language:reacquire-parametric-recipe"
            ),
        )
        parametric_recipe_reacquire_result = selective_memory.semantic(
            parametric_recipe_reacquire_request
        )
        parametric_recipe_reacquire_payload = parametric_recipe_reacquire_result.get(
            "result", {}
        )
        parametric_recipe_reacquired_reference = (
            parametric_recipe_reacquire_payload.get("construction")
            if isinstance(parametric_recipe_reacquire_payload, Mapping)
            else None
        )
        if (
            not isinstance(parametric_recipe_reacquire_payload, Mapping)
            or parametric_recipe_reacquire_payload.get("status") != "supported"
            or not isinstance(parametric_recipe_reacquired_reference, Mapping)
            or parametric_recipe_reacquired_reference
            == parametric_recipe_reference_before
        ):
            raise RuntimeError("parametric recipe was not reacquired as a new version")
        parametric_recipe_recovery_prediction = _execute_language_case(
            selective_memory,
            case=parametric_recipe_case,
            mechanism_id=selected_identity,
            operation_prefix="sqlite-apprenticeship:language:parametric-recovered",
            construction_id=str(recipe_recovered_reference["id"]),
        )
        if not parametric_recipe_recovery_prediction["matches_oracle"]:
            raise RuntimeError("recovered parametric recipe did not match the oracle")
        selective_state_after = selective_memory.state_receipt()
    with CassiFieldWorkMemory(memory_home) as recovery_reopened:
        recovery_reopen_state = recovery_reopened.state_receipt()
    recovery_persistence_equal = (
        dict(selective_state_after) == dict(recovery_reopen_state)
    )
    language_selective_recovery = {
        "component_key": selective_component_key,
        "component_reference_before": dict(selective_component_reference),
        "revoke_request": revoke_request,
        "revoke_result": revoke_result,
        "revoked_reference": dict(revoked_reference),
        "lost_interpret_request": lost_interpret_request,
        "lost_interpret_result": lost_interpret_result,
        "unrelated_interpret_request": unrelated_interpret_request,
        "unrelated_interpret_result": unrelated_interpret_result,
        "reacquire_request": reacquire_request,
        "reacquire_result": reacquire_result,
        "reacquired_reference": dict(reacquired_reference),
        "recovered_learning": {
            "request": recovered_learning_request,
            "result": recovered_learning,
            "reference": dict(recovered_reference),
        },
        "recovery_case": recovery_case,
        "recovery_prediction": recovery_prediction,
        "secondary_component_recovery": {
            "component_key": secondary_component_key,
            "component_reference_before": dict(secondary_component_reference),
            "revoke_request": secondary_revoke_request,
            "revoke_result": secondary_revoke_result,
            "revoked_reference": dict(secondary_revoked_reference),
            "lost_interpret_request": secondary_lost_interpret_request,
            "lost_interpret_result": secondary_lost_interpret_result,
            "unrelated_interpret_request": secondary_unrelated_interpret_request,
            "unrelated_interpret_result": secondary_unrelated_interpret_result,
            "reacquire_request": secondary_reacquire_request,
            "reacquire_result": secondary_reacquire_result,
            "reacquired_reference": dict(secondary_reacquired_reference),
            "recovered_learning": {
                "request": secondary_learning_request,
                "result": secondary_learning,
                "reference": dict(secondary_reference),
            },
            "recovery_prediction": secondary_recovery_prediction,
        },
        "recipe_recovery": {
            "recipe_key": recipe_selective_key,
            "recipe_reference_before": dict(recipe_selective_reference),
            "revoke_request": recipe_revoke_request,
            "revoke_result": recipe_revoke_result,
            "revoked_reference": dict(recipe_revoked_reference),
            "lost_interpret_request": recipe_lost_interpret_request,
            "lost_interpret_result": recipe_lost_interpret_result,
            "unrelated_recipe_key": recipe_unrelated_key,
            "unrelated_interpret_request": recipe_unrelated_interpret_request,
            "unrelated_interpret_result": recipe_unrelated_interpret_result,
            "survivor_case": recipe_survivor_case,
            "survivor_prediction": recipe_survivor_prediction,
            "reacquire_request": recipe_reacquire_request,
            "reacquire_result": recipe_reacquire_result,
            "reacquired_reference": dict(recipe_reacquired_reference),
            "recovered_recipe_references": {
                key: dict(reference)
                for key, reference in recovered_recipe_references.items()
            },
            "recovered_learning": {
                "request": recipe_recovered_learning_request,
                "result": recipe_recovered_learning,
                "reference": dict(recipe_recovered_reference),
            },
            "recovery_case": recipe_recovery_case,
            "recovery_prediction": recipe_recovery_prediction,
        },
        "parametric_recipe_recovery": {
            "recipe_key": _LANGUAGE_PARAMETRIC_RECIPE_KEY,
            "recipe_family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
            "recipe_reference_before": dict(parametric_recipe_reference_before),
            "revoke_request": parametric_recipe_revoke_request,
            "revoke_result": parametric_recipe_revoke_result,
            "revoked_reference": dict(parametric_recipe_revoked_reference),
            "lost_interpret_request": parametric_recipe_lost_interpret_request,
            "lost_interpret_result": parametric_recipe_lost_interpret_result,
            "survivor_request": parametric_recipe_survivor_request,
            "survivor_result": parametric_recipe_survivor_result,
            "reacquire_request": parametric_recipe_reacquire_request,
            "reacquire_result": parametric_recipe_reacquire_result,
            "reacquired_reference": dict(parametric_recipe_reacquired_reference),
            "recovery_case": parametric_recipe_case,
            "recovery_prediction": parametric_recipe_recovery_prediction,
        },
        "state_before": dict(selective_state_before),
        "state_after": dict(selective_state_after),
        "persistence_reopen": {
            "equal": recovery_persistence_equal,
            "reopened": dict(recovery_reopen_state),
        },
    }
    persistence_equal = dict(after) == dict(reopened_state)
    post_reopen_persistence_equal = dict(post_behavior_after) == dict(post_behavior_reopened_state)
    if (
        not persistence_equal
        or not post_reopen_persistence_equal
        or not language_persistence_equal
        or not recovery_persistence_equal
        or dict(language_state_before) != dict(post_behavior_reopened_state)
        or not predictions
        or not all(row["matches_oracle"] for row in predictions)
        or not post_reopen_prediction["matches_oracle"]
        or not language_prediction["matches_oracle"]
        or not language_additional_predictions
        or not all(
            row["matches_oracle"] for row in language_additional_predictions
        )
        or not recovery_prediction["matches_oracle"]
        or not secondary_recovery_prediction["matches_oracle"]
        or not recipe_survivor_prediction["matches_oracle"]
        or not recipe_recovery_prediction["matches_oracle"]
        or not parametric_recipe_recovery_prediction["matches_oracle"]
    ):
        raise RuntimeError(
            "apprenticeship invariant failed: prediction mismatch or persistence drift"
        )
    composition_holdout = {
        "schema": "cassi.sqlite-apprenticeship-composition-holdout.v1",
        "candidate_pool_source": "built-in-primitives-plus-parameterized-sequence-composer",
        "candidate_pool_ids": sorted(programs),
        "held_out_case_ids": [str(case["case_id"]) for case in tape["held_out"]],
        "held_out_sequence_ast_digests": {
            case_id: _sha(query_ast)
            for case_id, query_ast in sorted(heldout_query_asts.items())
        },
        "static_candidate_ast_digests": sorted(static_candidate_asts),
        "parameterized_candidate": "mechanism-sequence-composer",
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": "verified",
        "teacher_route": TEACHER_ROUTE,
        "teacher_fixture": teacher,
        "composition_holdout": composition_holdout,
        "candidate_programs": programs,
        "training": training_rows,
        "held_out": {
            "cases": tape["held_out"],
            "oracle": oracle_rows,
            "predictions": predictions,
            "selected_candidate": selected_identity,
            "support_counts": support_counts,
        },
        "frontier_receipts": frontier_receipts,
        "ack_receipts": ack_receipts,
        "field_route": {
            "request": dict(route_request),
            "response": dict(route_receipt),
            "reference": dict(route_reference),
            "query_request": dict(route_query_request),
            "query_response": dict(route_query_receipt),
        },
        "field_question_choice": {
            "mode": first_question_choice.get("mode"),
            "selected_question_id": selected_question_id,
            "question_candidates": list(question_candidates),
        },
        "native_observation": {
            "selected_question_id": selected_question_id,
            "question_candidates": list(question_candidates),
            "prompt": native_prompt,
            "prompt_sha256": _sha_text(native_prompt),
            "trial": dict(native_trial),
            "observation_request": dict(native_observation_request),
            "observation_response": dict(native_observation_receipt),
            "event_query_request": dict(native_observation_query_request),
            "event_query_response": dict(native_observation_query_receipt),
            "binding_query_request": dict(native_binding_query_request),
            "binding_query_response": dict(native_binding_query_receipt),
            "output_sha256": _sha_text(str(native_trial["output"])),
        },
        "native_evidence_update": {
            "request": dict(native_evidence_update_request),
            "response": dict(native_evidence_update_receipt),
            "representation_reference": dict(native_evidence_reference),
            "query_request": dict(native_evidence_query_request),
            "query_response": dict(native_evidence_query_receipt),
        },
        "native_language_teacher": {
            "prompt": native_language_teacher_prompt,
            "prompt_sha256": _sha_text(native_language_teacher_prompt),
            "trial": dict(native_language_teacher_trial),
            "visible_output": native_language_teacher_visible_output,
            "examples": list(native_language_teacher_examples),
            "output_sha256": _sha_text(str(native_language_teacher_trial["output"])),
        },
        "prediction_oracle_digests": [
            {
                "case_id": row["case_id"],
                "prediction_digest": row["prediction_digest"],
                "oracle_digest": row["oracle_digest"],
                "matches": row["matches_oracle"],
            }
            for row in predictions
        ],
        "field_state_before": dict(before),
        "field_state_after": dict(after),
        "persistence_reopen": {
            "equal": persistence_equal,
            "reopened": dict(reopened_state),
        },
        "post_reopen_behavior": {
            "case": post_case,
            "prediction": post_reopen_prediction,
            "state_before": dict(reopened_state),
            "state_after": dict(post_behavior_after),
            "persistence_reopen": {
                "equal": post_reopen_persistence_equal,
                "reopened": dict(post_behavior_reopened_state),
            },
        },
        "language_to_program": {
            "native_teacher": {
                "prompt": native_language_teacher_prompt,
                "prompt_sha256": _sha_text(native_language_teacher_prompt),
                "trial": dict(native_language_teacher_trial),
                "visible_output": native_language_teacher_visible_output,
                "examples": list(native_language_teacher_examples),
                "recipe_examples": list(native_language_recipe_examples),
                "output_sha256": _sha_text(str(native_language_teacher_trial["output"])),
            },
            "component_acquisition": {
                "components": component_learning,
                "references": {
                    key: dict(reference)
                    for key, reference in component_references.items()
                },
            },
            "recipe_acquisition": {
                "recipes": recipe_learning,
                "references": {
                    key: dict(reference)
                    for key, reference in recipe_references.items()
                },
            },
            "parametric_recipe_acquisition": {
                "recipe": dict(parametric_recipe),
                "examples": list(parametric_recipe_examples),
                "request": dict(parametric_recipe_request),
                "result": dict(parametric_recipe_result),
                "reference": dict(parametric_recipe_reference),
            },
            "construction_learning": {
                "request": language_learning_request,
                "result": language_learning,
            },
            "construction_reference": language_reference,
            "fixture": language_fixture,
            "prediction": language_prediction,
            "additional_predictions": language_additional_predictions,
            "state_before": dict(language_state_before),
            "state_after": dict(language_state_after),
            "persistence_reopen": language_reopen,
            "selective_component_recovery": language_selective_recovery,
        },
        "invariants": {
            "all_training_frontiers_proposed": len(frontier_receipts)
            == len(tape["training"]),
            "all_training_acknowledged": len(ack_receipts)
            == len(tape["training"]),
            "all_held_out_match": all(
                row["matches_oracle"] for row in predictions
            ),
            "post_reopen_behavior_match": bool(
                post_reopen_prediction["matches_oracle"]
            ),
            "field_question_choice_is_separating": (
                first_question_choice.get("mode") == "field-directed-v1"
                and selected_question_id in question_candidates
            ),
            "native_observation_is_coupled": (
                native_trial.get("schema")
                == "cassi.qwen-native-instrument-result.v1"
                and native_trial.get("mode") == "coupled"
                and native_trial.get("ownership", {}).get(
                    "silent_native_fallback"
                )
                is False
            ),
            "native_output_admitted_to_field": (
                native_binding_payload.get("value") == native_trial.get("output")
            ),
            "native_observation_updates_field_evidence": (
                native_evidence_update_receipt.get("result", {}).get("status")
                == "supported"
                and native_evidence_payload.get("program_role")
                == "predictive-state"
                and native_identity_sha256
                in native_evidence_record.get("support_roots", [])
            ),
            "native_language_teacher_admitted": (
                native_language_teacher_trial.get("schema")
                == "cassi.qwen-native-instrument-result.v1"
                and native_language_teacher_trial.get("mode") == "coupled"
                and native_language_teacher_trial.get("ownership", {}).get(
                    "silent_native_fallback"
                )
                is False
                and language_fixture.get("examples")
                == native_language_teacher_examples
            ),
            "language_components_acquired_separately": (
                len(component_learning) == len(_LANGUAGE_COMPONENT_KEYS)
                and all(
                    item.get("result", {}).get("result", {}).get("status")
                    == "supported"
                    for item in component_learning
                )
                and list(component_references)
                == list(_LANGUAGE_COMPONENT_KEYS)
            ),
            "language_recipes_acquired_separately": (
                len(recipe_learning) == len(_LANGUAGE_RECIPE_KEYS)
                and all(
                    item.get("result", {}).get("result", {}).get("status")
                    == "supported"
                    for item in recipe_learning
                )
                and list(recipe_references) == list(_LANGUAGE_RECIPE_KEYS)
            ),
            "language_stage_recipes_field_owned": (
                language_fixture["meaning"].get("stage_recipes")
                == {
                    "schema": _LANGUAGE_STAGE_RECIPE_SCHEMA,
                    "component_key": "stage_order",
                    "component": component_references["stage_order"],
                    "catalog": _LANGUAGE_STAGE_RECIPES,
                    "entries": {
                        key: {
                            "construction": recipe_references[key],
                            "recipe": _LANGUAGE_STAGE_RECIPES[key],
                        }
                        for key in _LANGUAGE_RECIPE_KEYS
                    },
                    "parametric": {
                        "family": _LANGUAGE_PARAMETRIC_RECIPE_FAMILY,
                        "recipe_key": _LANGUAGE_PARAMETRIC_RECIPE_KEY,
                        "construction": parametric_recipe_reference,
                    },
                }
                and language_prediction["interpretation"]
                .get("content", {})
                .get("stage_recipes")
                == language_fixture["meaning"]["stage_recipes"]
            ),
            "native_language_parametric_recipe_admitted": (
                native_language_recipe_examples == parametric_recipe_examples
                and len(parametric_recipe_examples) == 2
                and parametric_recipe_learning.get("result", {})
                .get("result", {})
                .get("status")
                == "supported"
                and parametric_recipe_reference.get("id")
                == (
                    "construction:language:recipe:"
                    f"{_LANGUAGE_PARAMETRIC_RECIPE_KEY}"
                )
            ),
            "language_parametric_recipe_generalizes": (
                language_additional_predictions[6]["recipe_interpretation"]
                .get("bindings", {})
                .get("recipe_family")
                == _LANGUAGE_PARAMETRIC_RECIPE_FAMILY
                and language_additional_predictions[6]["recipe_interpretation"]
                .get("bindings", {})
                .get("repeat_count")
                == "5"
                and language_additional_predictions[6]["recipe_interpretation"]
                .get("content", {})
                .get("recipe")
                == _resolve_language_recipe_roles(
                    _LANGUAGE_PARAMETRIC_RECIPE_TEMPLATE,
                    language_additional_predictions[6]["recipe_interpretation"].get(
                        "bindings", {}
                    ),
                )
                and _pipeline_stage_signature(
                    language_additional_predictions[6]["query_ast"]
                )
                == [
                    ["project", "distinct"],
                    *[
                        ["filter", "project", "order", "limit"]
                        for _ in range(5)
                    ],
                    ["project", "order", "limit"],
                ]
            ),
            "language_parametric_recipe_recovery": (
                parametric_recipe_lost_payload.get("status") == "support-gap"
                and parametric_recipe_survivor_payload.get("status") == "supported"
                and parametric_recipe_reacquire_payload.get("status") == "supported"
                and parametric_recipe_recovery_prediction["matches_oracle"] is True
            ),
            "language_composed_components_bound": (
                language_learning_request.get("components")
                == [
                    component_references[key]
                    for key in _LANGUAGE_COMPONENT_KEYS
                ]
                and [
                    item.get("key")
                    for item in language_fixture["meaning"].get("components", [])
                    if isinstance(item, Mapping)
                ]
                == list(_LANGUAGE_COMPONENT_KEYS)
            ),
            "language_recipe_entries_bound": (
                [
                    item.get("key")
                    for item in language_fixture["meaning"].get(
                        "recipe_components", []
                    )
                    if isinstance(item, Mapping)
                ]
                == list(_LANGUAGE_RECIPE_KEYS)
                and all(
                    language_fixture["meaning"]["stage_recipes"]["entries"][key][
                        "construction"
                    ]
                    == recipe_references[key]
                    for key in _LANGUAGE_RECIPE_KEYS
                )
            ),
            "native_language_teacher_retained_five_roles": (
                isinstance(language_learning.get("result"), Mapping)
                and language_learning["result"].get("pattern")
                == [
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
            ),
            "language_to_program_new_stage_arrangements": (
                language_fixture["case"]["binding"]["stage_arrangement"] == "limit"
                and language_additional_cases[0]["binding"]["stage_arrangement"]
                == "limit-distinct"
                and language_additional_cases[1]["binding"]["stage_arrangement"]
                == "distinct-filter"
                and language_additional_cases[2]["binding"]["stage_arrangement"]
                == "nested-reapply"
                and [
                    stage.get("op")
                    for stage in language_prediction["query_ast"]
                    .get("input", {})
                    .get("stages", [])
                ]
                == ["project", "distinct", "order", "limit"]
                and [
                    stage.get("op")
                    for stage in language_additional_predictions[0]["query_ast"]
                    .get("stages", [])
                ]
                == ["filter", "project", "distinct"]
                and [
                    stage.get("op")
                    for stage in language_additional_predictions[0]["query_ast"]
                    .get("input", {})
                    .get("stages", [])
                ]
                == ["project", "order", "limit"]
                and [
                    stage.get("op")
                    for stage in language_additional_predictions[1]["query_ast"]
                    .get("stages", [])
                ]
                == ["filter", "project", "order", "limit"]
                and [
                    stage.get("op")
                    for stage in language_additional_predictions[1]["query_ast"]
                    .get("input", {})
                    .get("stages", [])
                ]
                == ["project", "distinct"]
                and [
                    stage.get("op")
                    for stage in language_additional_predictions[2]["query_ast"]
                    .get("stages", [])
                ]
                == ["project", "distinct"]
                and [
                    stage.get("op")
                    for stage in language_additional_predictions[2]["query_ast"]
                    .get("input", {})
                    .get("stages", [])
                ]
                == ["filter", "project", "order", "limit"]
                and [
                    stage.get("op")
                    for stage in language_additional_predictions[2]["query_ast"]
                    .get("input", {})
                    .get("input", {})
                    .get("stages", [])
                ]
                == ["project", "order", "limit"]
                and _pipeline_stage_signature(
                    language_additional_predictions[3]["query_ast"]
                )
                == [
                    ["project", "distinct"],
                    *[["filter", "project", "order", "limit"] for _ in range(3)],
                    ["project", "order", "limit"],
                ]
                and _pipeline_stage_signature(
                    language_additional_predictions[4]["query_ast"]
                )
                == [
                    ["project", "distinct"],
                    *[["filter", "project", "order", "limit"] for _ in range(4)],
                    ["project", "order", "limit"],
                ]
                and _pipeline_stage_signature(
                    language_additional_predictions[5]["query_ast"]
                )
                == [
                    ["project", "limit"],
                    ["project", "distinct"],
                    ["filter", "project", "order"],
                    ["project"],
                ]
            ),
            "language_selective_component_loss": (
                language_selective_recovery["revoke_result"]
                .get("result", {})
                .get("status")
                == "supported"
                and language_selective_recovery["lost_interpret_result"]
                .get("result", {})
                .get("status")
                == "support-gap"
                and language_selective_recovery["unrelated_interpret_result"]
                .get("result", {})
                .get("status")
                == "supported"
                and language_selective_recovery["secondary_component_recovery"]
                ["revoke_result"]
                .get("result", {})
                .get("status")
                == "supported"
                and language_selective_recovery["secondary_component_recovery"]
                ["lost_interpret_result"]
                .get("result", {})
                .get("status")
                == "support-gap"
                and language_selective_recovery["secondary_component_recovery"]
                ["unrelated_interpret_result"]
                .get("result", {})
                .get("status")
                == "supported"
            ),
            "language_selective_component_recovery": (
                language_selective_recovery["reacquire_result"]
                .get("result", {})
                .get("status")
                == "supported"
                and language_selective_recovery["recovered_learning"]
                .get("result", {})
                .get("result", {})
                .get("status")
                == "supported"
                and language_selective_recovery["recovery_prediction"]
                .get("matches_oracle")
                is True
                and language_selective_recovery["secondary_component_recovery"]
                ["reacquire_result"]
                .get("result", {})
                .get("status")
                == "supported"
                and language_selective_recovery["secondary_component_recovery"]
                ["recovered_learning"]
                .get("result", {})
                .get("result", {})
                .get("status")
                == "supported"
                and language_selective_recovery["secondary_component_recovery"]
                ["recovery_prediction"]
                .get("matches_oracle")
                is True
                and language_selective_recovery["persistence_reopen"]
                .get("equal")
                is True
            ),
            "language_selective_recipe_recovery": (
                language_selective_recovery["recipe_recovery"]
                ["revoke_result"]
                .get("result", {})
                .get("status")
                == "supported"
                and language_selective_recovery["recipe_recovery"]
                ["lost_interpret_result"]
                .get("result", {})
                .get("status")
                == "support-gap"
                and language_selective_recovery["recipe_recovery"]
                ["unrelated_interpret_result"]
                .get("result", {})
                .get("status")
                == "supported"
                and language_selective_recovery["recipe_recovery"]
                ["survivor_prediction"]
                .get("matches_oracle")
                is True
                and language_selective_recovery["recipe_recovery"]
                ["reacquire_result"]
                .get("result", {})
                .get("status")
                == "supported"
                and language_selective_recovery["recipe_recovery"]
                ["recovery_prediction"]
                .get("matches_oracle")
                is True
            ),
            "post_reopen_persistence_equal": post_reopen_persistence_equal,
            "language_to_program_match": bool(
                language_prediction["matches_oracle"]
            ),
            "language_to_program_persistence_equal": language_persistence_equal,
            "language_interpretation_call_contains_no_ast_or_sql": not any(
                key in language_interpret_request
                for key in ("ast", "query_ast", "sql")
            ),
            "oracle_is_external": True,
            "field_calls_contain_no_sql": all(
                "sql" not in row["field_request"] for row in predictions
            ),
            "post_reopen_field_call_contains_no_sql": "sql"
            not in post_reopen_prediction["field_request"],
        },
    }
    receipt_path = out / "sqlite-apprenticeship.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=_CASSIQWEN / "_diag" / "sqlite-apprenticeship")
    parser.add_argument("--teacher-json", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        receipt = run_apprenticeship(out=args.out, teacher_json=args.teacher_json)
    except Exception as exc:
        print(json.dumps({"schema": RECEIPT_SCHEMA, "status": "failed", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps({"schema": receipt["schema"], "status": "verified", "receipt": str((Path(args.out).resolve() / 'sqlite-apprenticeship.json'))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
