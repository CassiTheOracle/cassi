#!/usr/bin/env python3
"""Run bounded English/LaTeX lessons and proof traces against the Cassi field."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
_CASSIQWEN_ROOT = Path(__file__).resolve().parent.parent
if str(_CASSIQWEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN_ROOT))
from typing import Any, Mapping, Sequence

from cassi_math_latex import (
    EXPR_SCHEMA,
    EQUATION_SCHEMA,
    WORD_PROBLEM_SCHEMA,
    WORD_PROBLEM_SYSTEM_SCHEMA,
    WORD_PROBLEM_CHAIN_SCHEMA,
    WORD_PROBLEM_STORY_SCHEMA,
    MathLatexError,
    digest_value,
    evaluate_equation,
    evaluate_expression,
    parse_english_equation,
    parse_english_expression,
    parse_english_word_problem,
    parse_english_word_problem_system,
    parse_english_word_problem_story,
    parse_english_word_problem_chain,
    parse_latex_equation,
    parse_latex_expression,
    render_english,
    render_latex,
    solve_linear_equation,
    solve_english_word_problem_story,
    solve_linear_system,
    solve_linear_equations,
    verify_linear_system_trace,
    verify_linear_trace,
)
from cassi_field_qwen_workbench import CassiFieldWorkMemory, WorkMemoryRecord


RECEIPT_SCHEMA = "cassi.math-latex.apprenticeship-receipt.v1"
LESSON_SCHEMA = "cassi.math-latex.lesson.v1"
TRACE_SCHEMA = "cassi.math-latex.trace.v1"
SYSTEM_TRACE_SCHEMA = "cassi.math-latex.system-trace.v1"
SYSTEM_CLASSIFICATION_SCHEMA = "cassi.math-latex.system-classification.v1"
LANGUAGE_SCHEMA = "cassi.math-language.lesson.v1"
OBSERVED_TIMESTAMP = "2000-01-01T00:00:00Z"
DEFAULT_ROOT = Path("E:/CassiLearning/cassi-math-latex-20260918")
DEFAULT_DATA_HOME = DEFAULT_ROOT / "field"
DEFAULT_OUTPUT = DEFAULT_ROOT / "receipt.json"


@dataclass(frozen=True, slots=True)
class LatexLesson:
    lesson_id: str
    title: str
    source: str
    kind: str
    cases: tuple[Mapping[str, Any], ...]


LESSONS: tuple[LatexLesson, ...] = (
    LatexLesson(
        "L0",
        "Exact fractions",
        r"\frac{14}{6}+\frac{1}{3}",
        "expression",
        ({"values": {}, "expected": {"numerator": 8, "denominator": 3}},),
    ),
    LatexLesson(
        "L1",
        "Implicit multiplication",
        "2x+3",
        "expression",
        (
            {"values": {"x": 4}, "expected": 11},
            {"values": {"x": -2}, "expected": -1},
        ),
    ),
    LatexLesson(
        "L2",
        "Nested powers and fractions",
        r"\frac{(x+1)^2}{2}",
        "expression",
        (
            {"values": {"x": 3}, "expected": 8},
            {"values": {"x": 5}, "expected": 18},
        ),
    ),
    LatexLesson(
        "L3",
        "Linear equation",
        "2x+3=11",
        "equation",
        ({"variable": "x", "expected": 4},),
    ),
    LatexLesson(
        "L4",
        "Named Greek symbol",
        r"\alpha^2+2\alpha+1",
        "expression",
        ({"values": {"alpha": 3}, "expected": 16},),
    ),
)


LINEAR_TRACES: tuple[Mapping[str, Any], ...] = (
    {
        "trace_id": "T0",
        "title": "Verified linear isolation",
        "variable": "x",
        "sources": ("2x+3=11", "2x=8", "x=4"),
        "operations": (
            {"kind": "subtract_both_sides", "value": 3},
            {"kind": "divide_both_sides", "value": 2},
        ),
        "expected_solution": {"status": "unique", "variable": "x", "value": 4},
    },
    {
        "trace_id": "T1",
        "title": "Collect and move a variable term",
        "variable": "x",
        "sources": ("2x+x=x+6", "3x=x+6", "2x=6", "x=3"),
        "operations": (
            {"kind": "collect_like_terms", "side": "left"},
            {"kind": "move_variable_term_to_left", "variable": "x", "coefficient": 1},
            {"kind": "divide_both_sides", "value": 2},
        ),
        "expected_solution": {"status": "unique", "variable": "x", "value": 3},
    },
    {
        "trace_id": "T2",
        "title": "Normalize a fractional coefficient",
        "variable": "x",
        "sources": (
            r"\frac{6}{4}x-4=5",
            r"\frac{3}{2}x-4=5",
            r"\frac{3}{2}x=9",
            "x=6",
        ),
        "operations": (
            {"kind": "normalize_variable_coefficient", "variable": "x", "side": "left"},
            {"kind": "subtract_both_sides", "value": 4},
            {"kind": "divide_both_sides", "value": {"numerator": 3, "denominator": 2}},
        ),
        "expected_solution": {"status": "unique", "variable": "x", "value": 6},
    },
    {
        "trace_id": "T3",
        "title": "Distribute a signed fractional factor",
        "variable": "x",
        "sources": (
            r"-\frac{3}{2}(x-2)=6",
            r"-\frac{3}{2}x+3=6",
            r"-\frac{3}{2}x=3",
            "x=-2",
        ),
        "operations": (
            {
                "kind": "distribute_factor",
                "factor": {"numerator": -3, "denominator": 2},
                "side": "left",
            },
            {"kind": "subtract_both_sides", "value": 3},
            {
                "kind": "divide_both_sides",
                "value": {"numerator": -3, "denominator": 2},
            },
        ),
        "expected_solution": {"status": "unique", "variable": "x", "value": -2},
    },
    {
        "trace_id": "T4",
        "title": "Distribute across both sides",
        "variable": "x",
        "sources": (
            r"-\frac{3}{2}(x-2)=\frac{1}{2}(x+6)",
            r"-\frac{3}{2}x+3=\frac{1}{2}(x+6)",
            r"-\frac{3}{2}x+3=\frac{1}{2}x+3",
            "-2x+3=3",
            "-2x=0",
            "x=0",
        ),
        "operations": (
            {
                "kind": "distribute_factor",
                "factor": {"numerator": -3, "denominator": 2},
                "side": "left",
            },
            {
                "kind": "distribute_factor",
                "factor": {"numerator": 1, "denominator": 2},
                "side": "right",
            },
            {
                "kind": "move_variable_term_to_left",
                "variable": "x",
                "coefficient": {"numerator": 1, "denominator": 2},
            },
            {"kind": "subtract_both_sides", "value": 3},
            {"kind": "divide_both_sides", "value": -2},
        ),
        "expected_solution": {"status": "unique", "variable": "x", "value": 0},
    },
)


ENGLISH_TRACES: tuple[Mapping[str, Any], ...] = (
    {
        "trace_id": "E-T0",
        "title": "Spoken linear isolation",
        "variable": "x",
        "sources": (
            "twice x plus 3 equals 11",
            "twice x equals 8",
            "x equals 4",
        ),
        "operations": (
            {"kind": "subtract_both_sides", "value": 3},
            {"kind": "divide_both_sides", "value": 2},
        ),
        "expected_solution": {"status": "unique", "variable": "x", "value": 4},
    },
)

SYSTEM_TRACES: tuple[Mapping[str, Any], ...] = (
    {
        "trace_id": "S0",
        "title": "Eliminate and substitute a coupled system",
        "variables": ("x", "y"),
        "states": (
            ("x+y=10", "2x-y=5"),
            ("3x=15", "2x-y=5"),
            ("x=5", "2x-y=5"),
            ("x=5", "10-y=5"),
            ("x=5", "-y=-5"),
            ("x=5", "y=5"),
        ),
        "operations": (
            {
                "kind": "add_equation_multiple",
                "target_row": 0,
                "source_row": 1,
                "multiple": 1,
            },
            {"kind": "scale_equation", "row": 0, "factor": {"numerator": 1, "denominator": 3}},
            {
                "kind": "substitute_solution",
                "source_row": 0,
                "target_row": 1,
                "variable": "x",
                "value": 5,
            },
            {"kind": "add_constant_both_sides", "row": 1, "delta": -10},
            {"kind": "scale_equation", "row": 1, "factor": -1},
        ),
        "expected_solution": {"status": "unique", "variables": {"x": 5, "y": 5}},
    },
)


SYSTEM_CLASSIFICATION_CASES: tuple[Mapping[str, Any], ...] = (
    {
        "case_id": "C0",
        "title": "Dependent system",
        "variables": ("x", "y"),
        "sources": ("x+y=2", "2x+2y=4"),
        "expected": {"status": "dependent", "variables": ["x", "y"]},
    },
    {
        "case_id": "C1",
        "title": "Inconsistent system",
        "variables": ("x", "y"),
        "sources": ("x+y=2", "2x+2y=5"),
        "expected": {"status": "no-solution", "variables": ["x", "y"]},
    },
)


REFUSAL_CONTROLS: tuple[Mapping[str, str], ...] = (
    {"control_id": "non-square-root", "source": r"\sqrt{2}", "expected_error": "MathLatexEvaluationError"},
    {"control_id": "quadratic-equation", "source": "x^2=4", "expected_error": "MathLatexEvaluationError"},
)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".staging")
    staging.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(staging, path)


LANGUAGE_LESSONS: tuple[Mapping[str, Any], ...] = (
    {
        "lesson_id": "E0",
        "title": "Spoken sum",
        "kind": "expression",
        "english": "x plus 2",
        "latex": "x+2",
        "cases": ({"values": {"x": 4}, "expected": 6}, {"values": {"x": -2}, "expected": 0}),
    },
    {
        "lesson_id": "E1",
        "title": "Spoken product and difference",
        "kind": "expression",
        "english": "the difference between the product of 2 and x and 1",
        "latex": "2x-1",
        "cases": ({"values": {"x": 3}, "expected": 5},),
    },
    {
        "lesson_id": "E2",
        "title": "Nested spoken quotient",
        "kind": "expression",
        "english": "the quotient of the sum of x and 1 and 2",
        "latex": r"\frac{x+1}{2}",
        "cases": ({"values": {"x": 5}, "expected": 3},),
    },
    {
        "lesson_id": "E3",
        "title": "Spoken equation",
        "kind": "equation",
        "english": "twice x plus 3 equals 11",
        "latex": "2x+3=11",
        "variable": "x",
        "expected": {"status": "unique", "variable": "x", "value": 4},
    },
)


WORD_PROBLEM_LESSONS: tuple[Mapping[str, Any], ...] = (
    {
        "lesson_id": "W0",
        "title": "Increased unknown",
        "source": "a number increased by 2 is 5",
        "variable": "x",
        "expected": {"status": "unique", "variable": "x", "value": 3},
    },
    {
        "lesson_id": "W1",
        "title": "Twice an unknown",
        "source": "twice a number minus 3 equals 11",
        "variable": "x",
        "expected": {"status": "unique", "variable": "x", "value": 7},
    },
    {
        "lesson_id": "W2",
        "title": "Sum of an unknown",
        "source": "the sum of a number and 4 is 9",
        "variable": "x",
        "expected": {"status": "unique", "variable": "x", "value": 5},
    },
    {
        "lesson_id": "W3",
        "title": "Divided unknown",
        "source": "a number divided by 2 is 3",
        "variable": "x",
        "expected": {"status": "unique", "variable": "x", "value": 6},
    },
)


WORD_PROBLEM_SYSTEM_LESSONS: tuple[Mapping[str, Any], ...] = (
    {
        "lesson_id": "S0",
        "title": "Sum and difference of two numbers",
        "source": "the sum of two numbers is 10 and their difference is 2",
        "variables": ("x", "y"),
        "expected": {"status": "unique", "variables": {"x": 6, "y": 4}},
    },
    {
        "lesson_id": "S1",
        "title": "First and second number",
        "source": "the first number plus the second number equals 13 and the first number minus the second number equals 5",
        "variables": ("x", "y"),
        "expected": {"status": "unique", "variables": {"x": 9, "y": 4}},
    },
    {
        "lesson_id": "S2",
        "title": "Dependent verbal system",
        "source": "the sum of two numbers is 10 and their sum is 10",
        "variables": ("x", "y"),
        "expected": {"status": "dependent", "variables": ["x", "y"]},
    },
    {
        "lesson_id": "S3",
        "title": "Inconsistent verbal system",
        "source": "the sum of two numbers is 10 and their sum is 11",
        "variables": ("x", "y"),
        "expected": {"status": "no-solution", "variables": ["x", "y"]},
    },
    {
        "lesson_id": "S4",
        "title": "Derived greater-number relation",
        "source": "one number is 2 more than another and their sum is 10",
        "variables": ("x", "y"),
        "expected": {"status": "unique", "variables": {"x": 6, "y": 4}},
    },
    {
        "lesson_id": "S5",
        "title": "Derived lesser-number relation",
        "source": "the first number is 3 less than the second and their sum is 15",
        "variables": ("x", "y"),
        "expected": {"status": "unique", "variables": {"x": 6, "y": 9}},
    },
    {
        "lesson_id": "S6",
        "title": "Derived ratio relation",
        "source": "one number is twice the other and their sum is 18",
        "variables": ("x", "y"),
        "expected": {"status": "unique", "variables": {"x": 12, "y": 6}},
    },
)


STORY_LESSONS: tuple[Mapping[str, Any], ...] = (
    {
        "lesson_id": "P0",
        "title": "Named ages",
        "source": "alice is 4 years older than bob and their ages sum to 30",
        "variables": ("x", "y"),
        "aliases": {"alice": "x", "bob": "y"},
        "expected": {"status": "unique", "variables": {"x": 17, "y": 13}},
    },
    {
        "lesson_id": "P1",
        "title": "Ticket prices",
        "source": "3 tickets cost x dollars each and 2 tickets cost y dollars each for 23 dollars total and x is 1 dollar more than y",
        "variables": ("x", "y"),
        "aliases": {},
        "expected": {"status": "unique", "variables": {"x": 5, "y": 4}},
    },
    {
        "lesson_id": "P2",
        "title": "Percentage increase",
        "source": "one quantity is 20 percent more than another and their sum is 33",
        "variables": ("x", "y"),
        "aliases": {},
        "expected": {"status": "unique", "variables": {"x": 18, "y": 15}},
    },
    {
        "lesson_id": "P3",
        "title": "Half-ratio quantity",
        "source": "one quantity is half as much as another and their sum is 18",
        "variables": ("x", "y"),
        "aliases": {},
        "expected": {"status": "unique", "variables": {"x": 6, "y": 12}},
    },
    {
        "lesson_id": "P4",
        "title": "Discounted price",
        "source": "a 20 percent discount on y gives x and x plus y equals 90",
        "variables": ("x", "y"),
        "aliases": {},
        "expected": {"status": "unique", "variables": {"x": 40, "y": 50}},
    },
    {
        "lesson_id": "P5",
        "title": "Marked-up price",
        "source": "a 10 percent markup on y gives x and x plus y equals 231",
        "variables": ("x", "y"),
        "aliases": {},
        "expected": {"status": "unique", "variables": {"x": 121, "y": 110}},
    },
    {
        "lesson_id": "P6",
        "title": "Unit quantity total",
        "source": "3 items cost x dollars each and 2 items cost y dollars each for 36 dollars total and x is 2 dollars more than y",
        "variables": ("x", "y"),
        "aliases": {},
        "expected": {"status": "unique", "variables": {"x": 8, "y": 6}},
    },
    {
        "lesson_id": "P7",
        "title": "Discount followed by tax",
        "source": "a 25 percent discount followed by 20 percent tax on y gives x and x plus y equals 38",
        "variables": ("x", "y"),
        "aliases": {},
        "expected": {"status": "unique", "variables": {"x": 18, "y": 20}},
    },
    {
        "lesson_id": "P8",
        "title": "Markup followed by tax",
        "source": "a 10 percent markup followed by 10 percent tax on y gives x and x plus y equals 221",
        "variables": ("x", "y"),
        "aliases": {},
        "expected": {"status": "unique", "variables": {"x": 121, "y": 100}},
    },
    {
        "lesson_id": "P9",
        "title": "Compound investment growth",
        "source": "an investment y grows by 10 percent for 2 years to x and x plus y equals 221",
        "variables": ("x", "y"),
        "aliases": {},
        "expected": {"status": "unique", "variables": {"x": 121, "y": 100}},
    },
    {
        "lesson_id": "P10",
        "title": "Simple interest growth",
        "source": "a principal y earns 5 percent simple interest for 2 years to x and x plus y equals 210",
        "variables": ("x", "y"),
        "aliases": {},
        "expected": {"status": "unique", "variables": {"x": 110, "y": 100}},
    },
)


STORY_CHAIN_LESSONS: tuple[Mapping[str, Any], ...] = (
    {
        "lesson_id": "P11",
        "title": "Named discount and tax states",
        "source": (
            "a 20 percent discount on original_price gives discounted_price and "
            "a 10 percent tax on discounted_price gives final_price and "
            "final_price plus original_price equals 188"
        ),
        "variables": ("x", "y", "z"),
        "aliases": {
            "final_price": "x",
            "original_price": "y",
            "discounted_price": "z",
        },
        "expected": {
            "status": "unique",
            "variables": {"x": 88, "y": 100, "z": 80},
        },
    },
    {
        "lesson_id": "P12",
        "title": "Named markup and tax states",
        "source": (
            "a 10 percent markup on wholesale_cost gives marked_price and "
            "a 10 percent tax on marked_price gives customer_price and "
            "customer_price plus wholesale_cost equals 221"
        ),
        "variables": ("x", "y", "z"),
        "aliases": {
            "customer_price": "x",
            "wholesale_cost": "y",
            "marked_price": "z",
        },
        "expected": {
            "status": "unique",
            "variables": {"x": 121, "y": 100, "z": 110},
        },
    },
)


def _validate_lesson(lesson: LatexLesson) -> dict[str, Any]:
    parsed = parse_latex_expression(lesson.source) if lesson.kind == "expression" else parse_latex_equation(lesson.source)
    rendered = render_latex(parsed)
    reparsed = parse_latex_expression(rendered) if lesson.kind == "expression" else parse_latex_equation(rendered)
    if digest_value(parsed) != digest_value(reparsed):
        raise MathLatexError(f"{lesson.lesson_id} LaTeX render did not round-trip")
    rows: list[dict[str, Any]] = []
    if lesson.kind == "expression":
        for index, case in enumerate(lesson.cases):
            actual = evaluate_expression(parsed, case["values"])
            rows.append({"case_id": f"{lesson.lesson_id}-{index}", "values": dict(case["values"]), "expected": case["expected"], "actual": actual, "same": actual == case["expected"]})
    else:
        case = lesson.cases[0]
        solution = solve_linear_equation(parsed, str(case["variable"]))
        actual = solution.get("value")
        rows.append({"case_id": f"{lesson.lesson_id}-0", "variable": case["variable"], "expected": case["expected"], "actual": actual, "equation_holds": evaluate_equation(parsed, {str(case["variable"]): case["expected"]}), "solution": solution, "same": actual == case["expected"]})
    if not all(row["same"] for row in rows):
        raise MathLatexError(f"{lesson.lesson_id} exact case mismatch")
    return {
        "schema": LESSON_SCHEMA,
        "lesson_id": lesson.lesson_id,
        "title": lesson.title,
        "kind": lesson.kind,
        "source": lesson.source,
        "source_sha256": digest_value(lesson.source),
        "canonical": parsed,
        "canonical_sha256": digest_value(parsed),
        "rendered": rendered,
        "round_trip": True,
        "cases": rows,
        "status": "PASS",
    }


def _validate_language_lesson(lesson: Mapping[str, Any]) -> dict[str, Any]:
    lesson_id = str(lesson["lesson_id"])
    kind = str(lesson["kind"])
    if kind not in {"expression", "equation"}:
        raise MathLatexError(f"{lesson_id} language lesson kind is invalid")
    english_parser = parse_english_expression if kind == "expression" else parse_english_equation
    latex_parser = parse_latex_expression if kind == "expression" else parse_latex_equation
    english = english_parser(str(lesson["english"]))
    latex = latex_parser(str(lesson["latex"]))
    if digest_value(english) != digest_value(latex):
        raise MathLatexError(f"{lesson_id} English and LaTeX meanings differ")
    rendered_english = render_english(latex)
    if digest_value(english_parser(rendered_english)) != digest_value(latex):
        raise MathLatexError(f"{lesson_id} English rendering did not round-trip")
    rendered_latex = render_latex(english)
    if digest_value(latex_parser(rendered_latex)) != digest_value(latex):
        raise MathLatexError(f"{lesson_id} LaTeX rendering did not round-trip")
    rows: list[dict[str, Any]] = []
    if kind == "expression":
        for index, case in enumerate(lesson["cases"]):
            actual = evaluate_expression(english, case["values"])
            rows.append(
                {
                    "case_id": f"{lesson_id}-{index}",
                    "values": dict(case["values"]),
                    "expected": case["expected"],
                    "actual": actual,
                    "same": actual == case["expected"],
                }
            )
    else:
        case = lesson
        solution = solve_linear_equation(english, str(case["variable"]))
        rows.append(
            {
                "case_id": f"{lesson_id}-0",
                "variable": case["variable"],
                "expected": case["expected"],
                "actual": solution,
                "equation_holds": evaluate_equation(
                    english, {str(case["variable"]): case["expected"]["value"]}
                ),
                "same": solution == case["expected"],
            }
        )
    if not all(row["same"] for row in rows):
        raise MathLatexError(f"{lesson_id} language case mismatch")
    return {
        "schema": LANGUAGE_SCHEMA,
        "lesson_id": lesson_id,
        "title": lesson["title"],
        "kind": kind,
        "english": lesson["english"],
        "latex": lesson["latex"],
        "english_sha256": digest_value(english),
        "latex_sha256": digest_value(latex),
        "rendered_english": rendered_english,
        "rendered_latex": rendered_latex,
        "cases": rows,
        "status": "PASS",
    }


def _validate_word_problem(lesson: Mapping[str, Any]) -> dict[str, Any]:
    lesson_id = str(lesson["lesson_id"])
    variable = str(lesson["variable"])
    problem = parse_english_word_problem(str(lesson["source"]), variable)
    solution = solve_linear_equation(problem["equation"], variable)
    expected = lesson["expected"]
    if solution != expected:
        raise MathLatexError(f"{lesson_id} word-problem solution mismatch")
    if not evaluate_equation(problem["equation"], {variable: expected["value"]}):
        raise MathLatexError(f"{lesson_id} word-problem solution does not satisfy equation")
    return {
        "schema": WORD_PROBLEM_SCHEMA,
        "lesson_id": lesson_id,
        "title": lesson["title"],
        "source": lesson["source"],
        "normalized": problem["normalized"],
        "variable": variable,
        "rendered_latex": problem["rendered_latex"],
        "rendered_english": problem["rendered_english"],
        "solution": solution,
        "status": "PASS",
    }


def _validate_word_problem_system(lesson: Mapping[str, Any]) -> dict[str, Any]:
    lesson_id = str(lesson["lesson_id"])
    variables = tuple(str(variable) for variable in lesson["variables"])
    problem = parse_english_word_problem_system(str(lesson["source"]), variables)
    solution = solve_linear_system(problem["equations"], variables)
    expected = lesson["expected"]
    if solution != expected:
        raise MathLatexError(f"{lesson_id} word-problem system solution mismatch")
    if solution["status"] == "unique":
        values = solution["variables"]
        if not all(evaluate_equation(equation, values) for equation in problem["equations"]):
            raise MathLatexError(f"{lesson_id} word-problem system solution does not satisfy equations")
    return {
        "schema": WORD_PROBLEM_SYSTEM_SCHEMA,
        "lesson_id": lesson_id,
        "title": lesson["title"],
        "source": lesson["source"],
        "normalized": problem["normalized"],
        "variables": list(variables),
        "rendered_latex": problem["rendered_latex"],
        "rendered_english": problem["rendered_english"],
        "solution": solution,
        "status": "PASS",
    }


def _validate_story_chain_lesson(lesson: Mapping[str, Any]) -> dict[str, Any]:
    lesson_id = str(lesson["lesson_id"])
    variables = tuple(str(variable) for variable in lesson["variables"])
    aliases = dict(lesson.get("aliases", {}))
    problem = parse_english_word_problem_chain(str(lesson["source"]), variables, aliases)
    solution = solve_linear_equations(problem["equations"], variables)
    expected = lesson["expected"]
    if solution != expected:
        raise MathLatexError(f"{lesson_id} story-chain solution mismatch")
    if solution["status"] == "unique":
        values = solution["variables"]
        if not all(
            evaluate_equation(equation, values) for equation in problem["equations"]
        ):
            raise MathLatexError(f"{lesson_id} story-chain solution does not satisfy equations")
    return {
        "schema": WORD_PROBLEM_CHAIN_SCHEMA,
        "lesson_id": lesson_id,
        "title": lesson["title"],
        "source": lesson["source"],
        "aliases": aliases,
        "normalized": problem["normalized"],
        "variables": list(variables),
        "rendered_latex": problem["rendered_latex"],
        "rendered_english": problem["rendered_english"],
        "solution": solution,
        "status": "PASS",
    }


def _validate_story_lesson(lesson: Mapping[str, Any]) -> dict[str, Any]:
    lesson_id = str(lesson["lesson_id"])
    variables = tuple(str(variable) for variable in lesson["variables"])
    aliases = dict(lesson.get("aliases", {}))
    problem = parse_english_word_problem_story(str(lesson["source"]), variables, aliases)
    solution = solve_linear_system(problem["system"]["equations"], variables)
    expected = lesson["expected"]
    if solution != expected:
        raise MathLatexError(f"{lesson_id} story solution mismatch")
    if solution["status"] == "unique":
        values = solution["variables"]
        if not all(
            evaluate_equation(equation, values)
            for equation in problem["system"]["equations"]
        ):
            raise MathLatexError(f"{lesson_id} story solution does not satisfy equations")
    return {
        "schema": WORD_PROBLEM_STORY_SCHEMA,
        "lesson_id": lesson_id,
        "title": lesson["title"],
        "source": lesson["source"],
        "aliases": aliases,
        "normalized": problem["normalized"],
        "variables": list(variables),
        "rendered_latex": problem["rendered_latex"],
        "rendered_english": problem["rendered_english"],
        "solution": solution,
        "status": "PASS",
    }
def _validate_trace(trace: Mapping[str, Any]) -> dict[str, Any]:
    trace_id = str(trace["trace_id"])
    variable = str(trace["variable"])
    sources = tuple(str(source) for source in trace["sources"])
    operations = tuple(trace["operations"])
    proof = verify_linear_trace(sources, variable, operations)
    if proof["status"] != "PASS":
        raise MathLatexError(f"{trace_id} contains an invalid algebraic transition")
    if proof["steps"][-1]["solution"] != trace["expected_solution"]:
        raise MathLatexError(f"{trace_id} final solution mismatch")
    return {
        "schema": TRACE_SCHEMA,
        "trace_id": trace_id,
        "title": trace["title"],
        "variable": variable,
        "sources": list(sources),
        "operations": [transition["operation"] for transition in proof["transitions"]],
        "source_sha256": digest_value(list(sources)),
        "proof": proof,
        "proof_sha256": digest_value(proof),
        "status": "PASS",
    }


def _validate_language_trace(trace: Mapping[str, Any]) -> dict[str, Any]:
    trace_id = str(trace["trace_id"])
    variable = str(trace["variable"])
    sources = tuple(str(source) for source in trace["sources"])
    operations = tuple(trace["operations"])
    proof = verify_linear_trace(sources, variable, operations, surface="english")
    if proof["status"] != "PASS":
        raise MathLatexError(f"{trace_id} contains an invalid English algebraic transition")
    if proof["steps"][-1]["solution"] != trace["expected_solution"]:
        raise MathLatexError(f"{trace_id} final English solution mismatch")
    return {
        "schema": "cassi.math-language.linear-trace.v1",
        "trace_id": trace_id,
        "title": trace["title"],
        "variable": variable,
        "sources": list(sources),
        "operations": [transition["operation"] for transition in proof["transitions"]],
        "source_sha256": digest_value(list(sources)),
        "proof": proof,
        "proof_sha256": digest_value(proof),
        "status": "PASS",
    }


def _validate_system_trace(trace: Mapping[str, Any]) -> dict[str, Any]:
    trace_id = str(trace["trace_id"])
    variables = tuple(str(variable) for variable in trace["variables"])
    states = tuple(tuple(str(source) for source in state) for state in trace["states"])
    operations = tuple(trace["operations"])
    proof = verify_linear_system_trace(states, variables, operations)
    if proof["status"] != "PASS":
        raise MathLatexError(f"{trace_id} contains an invalid system transition")
    if proof["steps"][-1]["solution"] != trace["expected_solution"]:
        raise MathLatexError(f"{trace_id} final system solution mismatch")
    return {
        "schema": SYSTEM_TRACE_SCHEMA,
        "trace_id": trace_id,
        "title": trace["title"],
        "variables": list(variables),
        "states": [list(state) for state in states],
        "operations": [transition["operation"] for transition in proof["transitions"]],
        "proof": proof,
        "proof_sha256": digest_value(proof),
        "status": "PASS",
    }


def _validate_system_classification(case: Mapping[str, Any]) -> dict[str, Any]:
    case_id = str(case["case_id"])
    variables = tuple(str(variable) for variable in case["variables"])
    sources = tuple(str(source) for source in case["sources"])
    equations = [parse_latex_equation(source) for source in sources]
    solution = solve_linear_system(equations, variables)
    if solution != case["expected"]:
        raise MathLatexError(f"{case_id} system classification mismatch")
    return {
        "schema": SYSTEM_CLASSIFICATION_SCHEMA,
        "case_id": case_id,
        "title": case["title"],
        "variables": list(variables),
        "sources": list(sources),
        "solution": solution,
        "status": "PASS",
    }


def _learn_lesson(memory: CassiFieldWorkMemory, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    record = WorkMemoryRecord(
        source_id=f"cassi-math-latex:lesson:{payload['lesson_id']}",
        context={"domain": "mathematics", "kind": "latex-lesson", "lesson": payload["lesson_id"]},
        payload=payload,
        observed_timestamp=OBSERVED_TIMESTAMP,
        labels=("cassi-math", "latex", payload["lesson_id"]),
    )
    return memory.learn(record)


def _learn_trace(memory: CassiFieldWorkMemory, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    record = WorkMemoryRecord(
        source_id=f"cassi-math-latex:trace:{payload['trace_id']}",
        context={"domain": "mathematics", "kind": "linear-proof-trace", "trace": payload["trace_id"]},
        payload=payload,
        observed_timestamp=OBSERVED_TIMESTAMP,
        labels=("cassi-math", "latex", "proof-trace", payload["trace_id"]),
    )
    return memory.learn(record)


def _learn_system_trace(
    memory: CassiFieldWorkMemory, payload: Mapping[str, Any]
) -> Mapping[str, Any]:
    record = WorkMemoryRecord(
        source_id=f"cassi-math-latex:system-trace:{payload['trace_id']}",
        context={
            "domain": "mathematics",
            "kind": "linear-system-proof-trace",
            "trace": payload["trace_id"],
        },
        payload=payload,
        observed_timestamp=OBSERVED_TIMESTAMP,
        labels=("cassi-math", "latex", "system-proof-trace", payload["trace_id"]),
    )
    return memory.learn(record)


def _learn_system_classification(
    memory: CassiFieldWorkMemory, payload: Mapping[str, Any]
) -> Mapping[str, Any]:
    record = WorkMemoryRecord(
        source_id=f"cassi-math-latex:system-classification:{payload['case_id']}",
        context={
            "domain": "mathematics",
            "kind": "linear-system-classification",
            "case": payload["case_id"],
        },
        payload=payload,
        observed_timestamp=OBSERVED_TIMESTAMP,
        labels=("cassi-math", "latex", "system-classification", payload["case_id"]),
    )
    return memory.learn(record)


def _learn_language_lesson(
    memory: CassiFieldWorkMemory, payload: Mapping[str, Any]
) -> Mapping[str, Any]:
    record = WorkMemoryRecord(
        source_id=f"cassi-math-language:lesson:{payload['lesson_id']}",
        context={
            "domain": "mathematics",
            "kind": "english-latex-meaning",
            "lesson": payload["lesson_id"],
        },
        payload=payload,
        observed_timestamp=OBSERVED_TIMESTAMP,
        labels=("cassi-math", "english", "latex", payload["lesson_id"]),
    )
    return memory.learn(record)


def _learn_language_trace(
    memory: CassiFieldWorkMemory, payload: Mapping[str, Any]
) -> Mapping[str, Any]:
    record = WorkMemoryRecord(
        source_id=f"cassi-math-language:trace:{payload['trace_id']}",
        context={
            "domain": "mathematics",
            "kind": "english-linear-proof-trace",
            "trace": payload["trace_id"],
        },
        payload=payload,
        observed_timestamp=OBSERVED_TIMESTAMP,
        labels=("cassi-math", "english", "proof-trace", payload["trace_id"]),
    )
    return memory.learn(record)


def _learn_word_problem(
    memory: CassiFieldWorkMemory, payload: Mapping[str, Any]
) -> Mapping[str, Any]:
    record = WorkMemoryRecord(
        source_id=f"cassi-math-language:word-problem:{payload['lesson_id']}",
        context={
            "domain": "mathematics",
            "kind": "english-word-problem",
            "lesson": payload["lesson_id"],
        },
        payload=payload,
        observed_timestamp=OBSERVED_TIMESTAMP,
        labels=("cassi-math", "english", "word-problem", payload["lesson_id"]),
    )
    return memory.learn(record)


def _learn_word_problem_system(
    memory: CassiFieldWorkMemory, payload: Mapping[str, Any]
) -> Mapping[str, Any]:
    record = WorkMemoryRecord(
        source_id=f"cassi-math-language:word-problem-system:{payload['lesson_id']}",
        context={
            "domain": "mathematics",
            "kind": "english-word-problem-system",
            "lesson": payload["lesson_id"],
        },
        payload=payload,
        observed_timestamp=OBSERVED_TIMESTAMP,
        labels=("cassi-math", "english", "word-problem-system", payload["lesson_id"]),
    )
    return memory.learn(record)


def _learn_story_lesson(
    memory: CassiFieldWorkMemory, payload: Mapping[str, Any]
) -> Mapping[str, Any]:
    record = WorkMemoryRecord(
        source_id=f"cassi-math-language:story:{payload['lesson_id']}",
        context={
            "domain": "mathematics",
            "kind": "english-word-problem-story",
            "lesson": payload["lesson_id"],
        },
        payload=payload,
        observed_timestamp=OBSERVED_TIMESTAMP,
        labels=("cassi-math", "english", "story", payload["lesson_id"]),
    )
    return memory.learn(record)


def _learn_story_chain_lesson(
    memory: CassiFieldWorkMemory, payload: Mapping[str, Any]
) -> Mapping[str, Any]:
    record = WorkMemoryRecord(
        source_id=f"cassi-math-language:story-chain:{payload['lesson_id']}",
        context={
            "domain": "mathematics",
            "kind": "english-word-problem-intermediate-chain",
            "lesson": payload["lesson_id"],
        },
        payload=payload,
        observed_timestamp=OBSERVED_TIMESTAMP,
        labels=("cassi-math", "english", "story-chain", payload["lesson_id"]),
    )
    return memory.learn(record)


def _run_refusal_controls() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for control in REFUSAL_CONTROLS:
        try:
            parsed = parse_latex_equation(control["source"]) if "=" in control["source"] else parse_latex_expression(control["source"])
            if parsed.get("schema") == EQUATION_SCHEMA:
                solve_linear_equation(parsed, "x")
            else:
                evaluate_expression(parsed)
        except MathLatexError as exc:
            rows.append({**control, "status": "REFUSED", "error_type": type(exc).__name__})
        else:
            rows.append({**control, "status": "UNEXPECTED_ACCEPT"})
    return rows

def run_apprenticeship(data_home: Path = DEFAULT_DATA_HOME) -> dict[str, Any]:
    lesson_rows: list[dict[str, Any]] = []
    language_rows: list[dict[str, Any]] = []
    word_problem_rows: list[dict[str, Any]] = []
    word_problem_system_rows: list[dict[str, Any]] = []
    story_rows: list[dict[str, Any]] = []
    story_chain_rows: list[dict[str, Any]] = []
    language_trace_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    system_trace_rows: list[dict[str, Any]] = []
    classification_rows: list[dict[str, Any]] = []
    field_receipts: list[Mapping[str, Any]] = []
    with CassiFieldWorkMemory(data_home, profile_overrides={"mode_count": 786_432}) as memory:
        for lesson in LESSONS:
            payload = _validate_lesson(lesson)
            field_receipts.append(_learn_lesson(memory, payload))
            lesson_rows.append(
                {
                    "lesson_id": lesson.lesson_id,
                    "status": payload["status"],
                    "canonical_sha256": payload["canonical_sha256"],
                    "rendered": payload["rendered"],
                    "cases": payload["cases"],
                    "field_source_revision_id": field_receipts[-1].get("source_revision_id"),
                }
            )
        for lesson in LANGUAGE_LESSONS:
            payload = _validate_language_lesson(lesson)
            field_receipts.append(_learn_language_lesson(memory, payload))
            language_rows.append(
                {
                    "lesson_id": payload["lesson_id"],
                    "title": payload["title"],
                    "status": payload["status"],
                    "english": payload["english"],
                    "latex": payload["latex"],
                    "english_sha256": payload["english_sha256"],
                    "latex_sha256": payload["latex_sha256"],
                    "rendered_english": payload["rendered_english"],
                    "rendered_latex": payload["rendered_latex"],
                    "cases": payload["cases"],
                    "field_source_revision_id": field_receipts[-1].get("source_revision_id"),
                }
            )
        for lesson in WORD_PROBLEM_LESSONS:
            payload = _validate_word_problem(lesson)
            field_receipts.append(_learn_word_problem(memory, payload))
            word_problem_rows.append(
                {
                    "lesson_id": payload["lesson_id"],
                    "title": payload["title"],
                    "status": payload["status"],
                    "source": payload["source"],
                    "normalized": payload["normalized"],
                    "variable": payload["variable"],
                    "rendered_latex": payload["rendered_latex"],
                    "rendered_english": payload["rendered_english"],
                    "solution": payload["solution"],
                    "field_source_revision_id": field_receipts[-1].get("source_revision_id"),
                }
            )
        for lesson in WORD_PROBLEM_SYSTEM_LESSONS:
            payload = _validate_word_problem_system(lesson)
            field_receipts.append(_learn_word_problem_system(memory, payload))
            word_problem_system_rows.append(
                {
                    "lesson_id": payload["lesson_id"],
                    "title": payload["title"],
                    "status": payload["status"],
                    "source": payload["source"],
                    "normalized": payload["normalized"],
                    "variables": payload["variables"],
                    "rendered_latex": payload["rendered_latex"],
                    "rendered_english": payload["rendered_english"],
                    "solution": payload["solution"],
                    "field_source_revision_id": field_receipts[-1].get("source_revision_id"),
                }
            )
        for lesson in STORY_LESSONS:
            payload = _validate_story_lesson(lesson)
            field_receipts.append(_learn_story_lesson(memory, payload))
            story_rows.append(
                {
                    "lesson_id": payload["lesson_id"],
                    "title": payload["title"],
                    "status": payload["status"],
                    "source": payload["source"],
                    "aliases": payload["aliases"],
                    "normalized": payload["normalized"],
                    "variables": payload["variables"],
                    "rendered_latex": payload["rendered_latex"],
                    "rendered_english": payload["rendered_english"],
                    "solution": payload["solution"],
                    "field_source_revision_id": field_receipts[-1].get("source_revision_id"),
                }
            )
        for lesson in STORY_CHAIN_LESSONS:
            payload = _validate_story_chain_lesson(lesson)
            field_receipts.append(_learn_story_chain_lesson(memory, payload))
            story_chain_rows.append(
                {
                    "lesson_id": payload["lesson_id"],
                    "title": payload["title"],
                    "status": payload["status"],
                    "source": payload["source"],
                    "aliases": payload["aliases"],
                    "normalized": payload["normalized"],
                    "variables": payload["variables"],
                    "rendered_latex": payload["rendered_latex"],
                    "rendered_english": payload["rendered_english"],
                    "solution": payload["solution"],
                    "field_source_revision_id": field_receipts[-1].get("source_revision_id"),
                }
            )
        for trace in ENGLISH_TRACES:
            payload = _validate_language_trace(trace)
            field_receipts.append(_learn_language_trace(memory, payload))
            language_trace_rows.append(
                {
                    "trace_id": payload["trace_id"],
                    "title": payload["title"],
                    "status": payload["status"],
                    "sources": payload["sources"],
                    "operations": payload["operations"],
                    "proof_sha256": payload["proof_sha256"],
                    "proof": payload["proof"],
                    "field_source_revision_id": field_receipts[-1].get("source_revision_id"),
                }
            )
        for trace in LINEAR_TRACES:
            payload = _validate_trace(trace)
            field_receipts.append(_learn_trace(memory, payload))
            trace_rows.append(
                {
                    "trace_id": payload["trace_id"],
                    "title": payload["title"],
                    "status": payload["status"],
                    "sources": payload["sources"],
                    "operations": payload["operations"],
                    "proof_sha256": payload["proof_sha256"],
                    "proof": payload["proof"],
                    "field_source_revision_id": field_receipts[-1].get("source_revision_id"),
                }
            )
        for trace in SYSTEM_TRACES:
            payload = _validate_system_trace(trace)
            field_receipts.append(_learn_system_trace(memory, payload))
            system_trace_rows.append(
                {
                    "trace_id": payload["trace_id"],
                    "title": payload["title"],
                    "status": payload["status"],
                    "variables": payload["variables"],
                    "states": payload["states"],
                    "operations": payload["operations"],
                    "proof_sha256": payload["proof_sha256"],
                    "proof": payload["proof"],
                    "field_source_revision_id": field_receipts[-1].get("source_revision_id"),
                }
            )
        for case in SYSTEM_CLASSIFICATION_CASES:
            payload = _validate_system_classification(case)
            field_receipts.append(_learn_system_classification(memory, payload))
            classification_rows.append(
                {
                    "case_id": payload["case_id"],
                    "title": payload["title"],
                    "variables": payload["variables"],
                    "sources": payload["sources"],
                    "solution": payload["solution"],
                    "status": payload["status"],
                    "field_source_revision_id": field_receipts[-1].get("source_revision_id"),
                }
            )
        refusal_rows = _run_refusal_controls()
        field = memory.regional_field_receipt()
    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "notation": {
            "expression_schema": EXPR_SCHEMA,
            "equation_schema": EQUATION_SCHEMA,
            "word_problem_schema": WORD_PROBLEM_SCHEMA,
            "word_problem_system_schema": WORD_PROBLEM_SYSTEM_SCHEMA,
            "word_problem_story_schema": WORD_PROBLEM_STORY_SCHEMA,
            "word_problem_chain_schema": WORD_PROBLEM_CHAIN_SCHEMA,
        },
        "lessons": lesson_rows,
        "language_lessons": language_rows,
        "word_problem_lessons": word_problem_rows,
        "word_problem_system_lessons": word_problem_system_rows,
        "story_lessons": story_rows,
        "story_chain_lessons": story_chain_rows,
        "language_proof_traces": language_trace_rows,
        "proof_traces": trace_rows,
        "system_traces": system_trace_rows,
        "system_classifications": classification_rows,
        "refusal_controls": refusal_rows,
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
        if all(row["status"] == "PASS" for row in lesson_rows)
        and all(row["status"] == "PASS" for row in language_rows)
        and all(row["status"] == "PASS" for row in word_problem_rows)
        and all(row["status"] == "PASS" for row in word_problem_system_rows)
        and all(row["status"] == "PASS" for row in story_rows)
        and all(row["status"] == "PASS" for row in story_chain_rows)
        and all(row["status"] == "PASS" for row in language_trace_rows)
        and all(row["status"] == "PASS" for row in trace_rows)
        and all(row["status"] == "PASS" for row in system_trace_rows)
        and all(row["status"] == "PASS" for row in classification_rows)
        and all(row["status"] == "REFUSED" for row in refusal_rows)
        and body["field"]["all_finite"]
        else "FAIL"
    )
    body["content_sha256"] = digest_value(body)
    return body

def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(receipt)
    stated = body.pop("content_sha256", None)
    if not isinstance(stated, str) or digest_value(body) != stated:
        raise MathLatexError("LaTeX receipt digest mismatch")
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("status") != "PASS":
        raise MathLatexError("LaTeX receipt is not a pass")
    if len(receipt.get("lessons", ())) != len(LESSONS):
        raise MathLatexError("LaTeX lesson count mismatch")
    if not all(row.get("status") == "PASS" for row in receipt["lessons"]):
        raise MathLatexError("LaTeX lesson failure")
    if len(receipt.get("language_lessons", ())) != len(LANGUAGE_LESSONS):
        raise MathLatexError("English language lesson count mismatch")
    for expected, row in zip(LANGUAGE_LESSONS, receipt["language_lessons"], strict=True):
        payload = _validate_language_lesson(expected)
        if (
            row.get("status") != "PASS"
            or row.get("lesson_id") != payload["lesson_id"]
            or row.get("english_sha256") != payload["english_sha256"]
            or row.get("latex_sha256") != payload["latex_sha256"]
            or row.get("cases") != payload["cases"]
        ):
            raise MathLatexError("English language lesson failure")
    if len(receipt.get("language_proof_traces", ())) != len(ENGLISH_TRACES):
        raise MathLatexError("English proof trace count mismatch")
    for expected, row in zip(ENGLISH_TRACES, receipt["language_proof_traces"], strict=True):
        payload = _validate_language_trace(expected)
        if (
            row.get("status") != "PASS"
            or row.get("trace_id") != payload["trace_id"]
            or row.get("proof_sha256") != payload["proof_sha256"]
            or row.get("proof") != payload["proof"]
        ):
            raise MathLatexError("English proof trace failure")
    if len(receipt.get("word_problem_lessons", ())) != len(WORD_PROBLEM_LESSONS):
        raise MathLatexError("English word-problem lesson count mismatch")
    for expected, row in zip(WORD_PROBLEM_LESSONS, receipt["word_problem_lessons"], strict=True):
        payload = _validate_word_problem(expected)
        if (
            row.get("status") != "PASS"
            or row.get("lesson_id") != payload["lesson_id"]
            or row.get("normalized") != payload["normalized"]
            or row.get("solution") != payload["solution"]
        ):
            raise MathLatexError("English word-problem lesson failure")
    if len(receipt.get("word_problem_system_lessons", ())) != len(WORD_PROBLEM_SYSTEM_LESSONS):
        raise MathLatexError("English word-problem system lesson count mismatch")
    for expected, row in zip(
        WORD_PROBLEM_SYSTEM_LESSONS, receipt["word_problem_system_lessons"], strict=True
    ):
        payload = _validate_word_problem_system(expected)
        if (
            row.get("status") != "PASS"
            or row.get("lesson_id") != payload["lesson_id"]
            or row.get("normalized") != payload["normalized"]
            or row.get("solution") != payload["solution"]
        ):
            raise MathLatexError("English word-problem system lesson failure")
    if len(receipt.get("story_lessons", ())) != len(STORY_LESSONS):
        raise MathLatexError("English story lesson count mismatch")
    for expected, row in zip(STORY_LESSONS, receipt["story_lessons"], strict=True):
        payload = _validate_story_lesson(expected)
        if (
            row.get("status") != "PASS"
            or row.get("lesson_id") != payload["lesson_id"]
            or row.get("aliases") != payload["aliases"]
            or row.get("normalized") != payload["normalized"]
            or row.get("solution") != payload["solution"]
        ):
            raise MathLatexError("English story lesson failure")
    if len(receipt.get("story_chain_lessons", ())) != len(STORY_CHAIN_LESSONS):
        raise MathLatexError("English story-chain lesson count mismatch")
    for expected, row in zip(
        STORY_CHAIN_LESSONS, receipt["story_chain_lessons"], strict=True
    ):
        payload = _validate_story_chain_lesson(expected)
        if (
            row.get("status") != "PASS"
            or row.get("lesson_id") != payload["lesson_id"]
            or row.get("aliases") != payload["aliases"]
            or row.get("normalized") != payload["normalized"]
            or row.get("solution") != payload["solution"]
        ):
            raise MathLatexError("English story-chain lesson failure")
    if len(receipt.get("proof_traces", ())) != len(LINEAR_TRACES):
        raise MathLatexError("LaTeX proof trace count mismatch")
    if not all(
        row.get("status") == "PASS"
        and row.get("proof", {}).get("status") == "PASS"
        and all(
            transition.get("equivalent") is True
            and transition.get("operation_applied") is True
            for transition in row["proof"]["transitions"]
        )
        for row in receipt["proof_traces"]
    ):
        raise MathLatexError("LaTeX proof trace failure")
    if len(receipt.get("system_traces", ())) != len(SYSTEM_TRACES):
        raise MathLatexError("LaTeX system trace count mismatch")
    if not all(
        row.get("status") == "PASS"
        and row.get("proof", {}).get("status") == "PASS"
        and all(
            transition.get("operation_applied") is True
            for transition in row["proof"]["transitions"]
        )
        for row in receipt["system_traces"]
    ):
        raise MathLatexError("LaTeX system trace failure")
    if len(receipt.get("system_classifications", ())) != len(SYSTEM_CLASSIFICATION_CASES):
        raise MathLatexError("LaTeX system classification count mismatch")
    if not all(
        row.get("status") == "PASS"
        and row.get("solution", {}).get("status") in {"dependent", "no-solution"}
        for row in receipt["system_classifications"]
    ):
        raise MathLatexError("LaTeX system classification failure")
    if not all(row.get("status") == "REFUSED" for row in receipt["refusal_controls"]):
        raise MathLatexError("refusal control unexpectedly accepted")
    if receipt.get("field", {}).get("all_finite") is not True:
        raise MathLatexError("persisted LaTeX field is not finite")
    return {"status": "PASS", "content_sha256": stated}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded exact LaTeX lessons and algebra traces through the Cassi field"
    )
    parser.add_argument("--data-home", type=Path, default=DEFAULT_DATA_HOME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    receipt = run_apprenticeship(args.data_home)
    _atomic_json(args.output, receipt)
    verify_receipt(receipt)
    print(
        json.dumps(
            {
                "receipt": str(args.output),
                "status": receipt["status"],
                "content_sha256": receipt["content_sha256"],
                "lessons": len(receipt["lessons"]),
                "linear_traces": len(receipt["proof_traces"]),
                "language_lessons": len(receipt["language_lessons"]),
                "word_problem_lessons": len(receipt["word_problem_lessons"]),
                "word_problem_system_lessons": len(receipt["word_problem_system_lessons"]),
                "story_lessons": len(receipt["story_lessons"]),
                "story_chain_lessons": len(receipt["story_chain_lessons"]),
                "language_proof_traces": len(receipt["language_proof_traces"]),
                "system_traces": len(receipt["system_traces"]),
                "system_classifications": len(receipt["system_classifications"]),
                "field": receipt["field"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
