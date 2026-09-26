from __future__ import annotations

"""Audit and canonicalize compact GSM8K-style arithmetic records.

The adapter deliberately does not treat a benchmark explanation as trusted
training truth. It admits a case only when an extracted numeric expression
replays to the declared ``####`` answer under CassiFI's exact math kernel.
Natural-language construction learning remains a separate, explicit lesson
operation.
"""

import ast
import hashlib
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from cassi_math_language import (
    MathLanguageError,
    canonical_math_template,
    evaluate,
    integer_term,
    parse_latex,
    render_latex,
    validate_math_lessons,
)


MATH_DATASET_AUDIT_SCHEMA = "cassifi.math-dataset-audit.v1"
MATH_DATASET_LESSON_SCHEMA = "cassifi.math-dataset-lesson.v1"

_NUMBER_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?")
_EXPRESSION_RE = re.compile(r"\d[\d\s./*+xX()%\-]*")


class MathDatasetError(ValueError):
    """Raised when a dataset record violates the bounded audit contract."""


def _collapse_repeated_number(value: str) -> str:
    compact = value.strip().replace("$", "").replace(",", "")
    if len(compact) >= 2 and len(compact) % 2 == 0:
        midpoint = len(compact) // 2
        if compact[:midpoint] == compact[midpoint:]:
            return compact[:midpoint]
    return compact


def _fraction_text(value: str) -> Fraction:
    normalized = _collapse_repeated_number(value)
    try:
        return Fraction(normalized)
    except (ValueError, ZeroDivisionError) as exc:
        raise MathDatasetError(f"invalid numeric answer: {value!r}") from exc


def parse_gsm8k_records(text: str) -> list[dict[str, Any]]:
    """Parse the Q/A/#### block format used by the inactive GSM8K copy."""

    if not isinstance(text, str):
        raise MathDatasetError("dataset content must be text")
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    reasoning: list[str] = []
    for line in text.splitlines():
        if line.startswith("Q: "):
            if current is not None:
                raise MathDatasetError("encountered a question before closing a record")
            current = {"question": line[3:].strip()}
            reasoning = []
            continue
        if current is None:
            if line.strip():
                raise MathDatasetError("dataset has content outside a Q/A record")
            continue
        if line.startswith("A: "):
            reasoning.append(line[3:].strip())
            continue
        if line.startswith("#### "):
            answer_text = line[5:].strip()
            if not answer_text:
                raise MathDatasetError("record answer is empty")
            records.append(
                {
                    "index": len(records),
                    "question": current["question"],
                    "reasoning": "\n".join(reasoning),
                    "answer_text": answer_text,
                }
            )
            current = None
            reasoning = []
            continue
        if line.strip():
            reasoning.append(line.strip())
    if current is not None:
        raise MathDatasetError("dataset ended with an incomplete record")
    return records


def _numeric_equation_candidates(reasoning: str) -> Iterable[dict[str, Any]]:
    for line in reasoning.splitlines():
        parts = line.split("=")
        if len(parts) < 2:
            continue
        left_segment = parts[-2].replace("$", "")
        right_segment = parts[-1].strip()
        right_match = _NUMBER_RE.match(right_segment)
        if right_match is None:
            continue
        right_text = _collapse_repeated_number(right_match.group(0))
        for raw_left in reversed(_EXPRESSION_RE.findall(left_segment)):
            expression = re.sub(r"\s+", "", raw_left).replace("x", "*").replace("X", "*")
            if not expression or "%" in expression:
                continue
            try:
                term = parse_latex(expression)
                value = evaluate(term)
            except MathLanguageError:
                continue
            if isinstance(value, bool):
                continue
            try:
                declared_value = _fraction_text(right_text)
            except MathDatasetError:
                continue
            yield {
                "expression": expression,
                "term": term,
                "value": Fraction(value),
                "declared_value": declared_value,
                "source_line": line,
            }
            break


def audit_gsm8k_text(
    text: str,
    *,
    max_cases: int | None = None,
) -> dict[str, Any]:
    """Audit records and return only exact, independently replayable cases."""

    records = parse_gsm8k_records(text)
    if max_cases is not None and (
        isinstance(max_cases, bool) or not isinstance(max_cases, int) or max_cases < 1
    ):
        raise MathDatasetError("max_cases must be a positive integer or None")
    cases: list[dict[str, Any]] = []
    counts = {
        "records": len(records),
        "numeric_answers": 0,
        "equation_candidates": 0,
        "verified_cases": 0,
        "answer_parse_failures": 0,
        "equation_mismatches": 0,
        "no_numeric_equation": 0,
    }
    for record in records:
        try:
            answer = _fraction_text(record["answer_text"])
        except MathDatasetError:
            counts["answer_parse_failures"] += 1
            continue
        counts["numeric_answers"] += 1
        candidates = list(_numeric_equation_candidates(record["reasoning"]))
        counts["equation_candidates"] += len(candidates)
        matching = [candidate for candidate in candidates if candidate["value"] == answer]
        if not matching:
            counts["no_numeric_equation"] += int(not candidates)
            counts["equation_mismatches"] += int(bool(candidates))
            continue
        candidate = matching[-1]
        counts["verified_cases"] += 1
        if max_cases is not None and len(cases) >= max_cases:
            continue
        cases.append(
            {
                "answer": str(answer),
                "equation_latex": render_latex(candidate["term"]),
                "equation_surface": candidate["expression"],
                "index": record["index"],
                "question": record["question"],
                "source_line": candidate["source_line"],
            }
        )
    return {
        "schema": MATH_DATASET_AUDIT_SCHEMA,
        "source_format": "gsm8k-q-a-hash",
        "counts": counts,
        "cases": cases,
    }


def _integer_role(name: str) -> dict[str, Any]:
    return {
        "kind": "variable",
        "name": name,
        "scope": "role",
        "type": {"kind": "atom", "name": "integer"},
    }


def _lesson_tree(
    node: ast.AST,
    bindings: dict[str, str],
) -> tuple[dict[str, Any], tuple[Any, ...]]:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(
        node.value, bool
    ):
        name = f"operand_{len(bindings)}"
        bindings[name] = str(node.value)
        return _integer_role(name), ("operand",)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, int)
        and not isinstance(node.operand.value, bool)
    ):
        name = f"operand_{len(bindings)}"
        bindings[name] = str(-node.operand.value)
        return _integer_role(name), ("operand",)
    if not isinstance(node, ast.BinOp):
        raise MathDatasetError("lesson expression contains an unsupported AST node")
    left, left_signature = _lesson_tree(node.left, bindings)
    right, right_signature = _lesson_tree(node.right, bindings)
    if isinstance(node.op, ast.Add):
        name = "add"
        template = {"kind": "constructor", "name": name, "args": [left, right]}
    elif isinstance(node.op, ast.Sub):
        name = "sub"
        template = {
            "kind": "constructor",
            "name": "add",
            "args": [
                left,
                {
                    "kind": "constructor",
                    "name": "mul",
                    "args": [integer_term(-1), right],
                },
            ],
        }
    elif isinstance(node.op, ast.Mult):
        name = "mul"
        template = {"kind": "constructor", "name": name, "args": [left, right]}
    elif isinstance(node.op, ast.Div):
        name = "div"
        template = {"kind": "constructor", "name": name, "args": [left, right]}
    else:
        raise MathDatasetError("lesson expression uses an unsupported arithmetic operator")
    return template, (name, left_signature, right_signature)


def _lesson_english(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(
        node.value, bool
    ):
        return str(node.value)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
    ):
        return str(-int(node.operand.value))
    if not isinstance(node, ast.BinOp):
        raise MathDatasetError("lesson expression contains an unsupported AST node")
    left = _lesson_english(node.left)
    right = _lesson_english(node.right)
    words = {
        ast.Add: "plus",
        ast.Sub: "minus",
        ast.Mult: "times",
        ast.Div: "divided by",
    }
    for operator, word in words.items():
        if isinstance(node.op, operator):
            return f"( {left} {word} {right} )"
    raise MathDatasetError("lesson expression uses an unsupported arithmetic operator")


def _role_spans_are_unambiguous(example: Mapping[str, Any]) -> bool:
    text = str(example["english"])
    bindings = example["bindings"]
    spans: list[tuple[int, int]] = []
    values = [str(value) for value in bindings.values()]
    if len(set(values)) != len(values):
        return False
    for value in values:
        if text.count(value) != 1:
            return False
        start = text.index(value)
        spans.append((start, start + len(value)))
    ordered = sorted(spans)
    for index, (start, _) in enumerate(ordered[1:], start=1):
        if start < ordered[index - 1][1]:
            return False
    return True


def _lesson_case(case: Mapping[str, Any]) -> tuple[str, dict[str, Any], tuple[Any, ...]]:
    expression = str(case.get("equation_surface", "")).strip()
    if not expression:
        raise MathDatasetError("verified case has no source expression")
    try:
        tree = ast.parse(expression, mode="eval").body
    except SyntaxError as exc:
        raise MathDatasetError("verified case expression is not a safe arithmetic AST") from exc
    bindings: dict[str, str] = {}
    template, signature = _lesson_tree(tree, bindings)
    example = {
        "bindings": bindings,
        "english": _lesson_english(tree),
        "latex": expression,
    }
    if not _role_spans_are_unambiguous(example):
        raise MathDatasetError("lesson role spans are ambiguous")
    return expression, {"template": template, "example": example}, signature

def _is_flat_binary_signature(signature: tuple[Any, ...]) -> bool:
    return (
        len(signature) == 3
        and signature[0] in {"add", "sub", "mul", "div"}
        and signature[1] == ("operand",)
        and signature[2] == ("operand",)
    )


def mine_gsm8k_lessons(
    cases: Sequence[Mapping[str, Any]],
    *,
    max_lessons: int = 8,
    max_examples: int = 8,
    holdout_count: int = 2,
) -> list[dict[str, Any]]:
    """Mine bounded, exact arithmetic lessons from audited GSM8K cases.

    Only source expressions with an integer-only flat binary ``+``, ``-``,
    ``*``, or ``/`` AST are admitted. Each lesson is grouped by one operator,
    uses independently generated English/LaTeX surfaces, and is revalidated
    by the field's typed math lesson contract before admission.
    """

    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in (max_lessons, max_examples)
    ) or isinstance(holdout_count, bool) or not isinstance(holdout_count, int) or holdout_count < 0:
        raise MathDatasetError("lesson bounds must be positive integers")
    groups: dict[str, dict[str, Any]] = {}
    for case in cases:
        try:
            expression, lesson_case, signature = _lesson_case(case)
            template = canonical_math_template(lesson_case["template"])
        except (MathDatasetError, MathLanguageError, TypeError, ValueError):
            continue
        key = repr(signature)
        group = groups.setdefault(
            key,
            {
                "key": key,
                "signature": signature,
                "template": template,
                "rows": [],
            },
        )
        if group["template"] != template:
            continue
        group["rows"].append(
            {
                "case_index": case.get("index"),
                "expression": expression,
                "example": lesson_case["example"],
            }
        )
    eligible = [
        group
        for group in groups.values()
        if _is_flat_binary_signature(group["signature"])
        and len(group["rows"]) >= holdout_count + 1
    ]
    eligible.sort(key=lambda group: (-len(group["rows"]), group["key"]))
    lessons: list[dict[str, Any]] = []
    for group in eligible[:max_lessons]:
        rows = group["rows"]
        training_rows = rows[:max_examples]
        holdout_rows = rows[max_examples : max_examples + holdout_count]
        if not training_rows or len(holdout_rows) != holdout_count:
            continue
        examples = [row["example"] for row in training_rows]
        holdout = [row["example"] for row in holdout_rows]
        try:
            validated = validate_math_lessons(
                template=group["template"],
                examples=examples,
                holdout=holdout,
            )
        except MathLanguageError:
            continue
        digest = hashlib.sha256(group["key"].encode("utf-8")).hexdigest()[:12]
        lessons.append(
            {
                "schema": MATH_DATASET_LESSON_SCHEMA,
                "construction_id": f"gsm8k_arithmetic_{digest}",
                "operator_signature": group["signature"],
                "term_template": validated["term_template"],
                "examples": validated["examples"],
                "holdout": validated["holdout"],
                "source_indexes": [
                    row["case_index"] for row in [*training_rows, *holdout_rows]
                ],
            }
        )
    return lessons


def audit_gsm8k_file(
    path: str | Path,
    *,
    max_cases: int | None = None,
) -> dict[str, Any]:
    source = Path(path)
    return audit_gsm8k_text(
        source.read_text(encoding="utf-8"), max_cases=max_cases
    )


__all__ = [
    "MATH_DATASET_AUDIT_SCHEMA",
    "MATH_DATASET_LESSON_SCHEMA",
    "MathDatasetError",
    "audit_gsm8k_file",
    "audit_gsm8k_text",
    "mine_gsm8k_lessons",
    "parse_gsm8k_records",
]
