"""Autonomous M0--M26 mathematics study over one persistent Cassi field.

Qwen is a bounded offline teacher.  The continuing CassiFI field owns admitted
study methods and executable capability programs.  A fixed, non-adaptive VM
executes those programs after Qwen is disconnected; protected reference
functions only grade committed outputs and are never placed in teacher prompts.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from cassi_field_qwen_workbench import (
    CassiFieldWorkMemory,
    LocalQwenClient,
    WorkMemoryRecord,
    cassifi_source_identity,
)

COURSE_SCHEMA = "cassi.autonomous-math.course.v1"
PROGRAM_SCHEMA = "cassi.autonomous-math.program.v1"
METHOD_SCHEMA = "cassi.autonomous-math.study-method.v1"
RECEIPT_SCHEMA = "cassi.autonomous-math.study-receipt.v1"
AUDIT_SCHEMA = "cassi.autonomous-math.audit-state.v1"
COURSE_ID = "cassi-mathematics-m0-m26"
DEFAULT_PROFILE_OVERRIDES: Mapping[str, int] = {"mode_count": 786_432}
MAX_PROGRAM_NODES = 512
MAX_PROGRAM_DEPTH = 32
MAX_VM_STEPS = 50_000
MAX_LIST_ITEMS = 2_048
MAX_INTEGER_ABS = 10**18


class StudyError(RuntimeError):
    """Fail-closed course, teacher, field, or verifier error."""


class Teacher(Protocol):
    def complete(
        self, *, prompt: str, max_tokens: int, thinking: bool = False
    ) -> Mapping[str, Any]: ...


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def content_digest_matches(value: Mapping[str, Any]) -> bool:
    body = dict(value)
    stated = body.pop("content_sha256", None)
    return isinstance(stated, str) and digest_value(body) == stated

def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".staging")
    staging.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    os.replace(staging, path)


def _rational(value: Any) -> Fraction:
    if isinstance(value, bool):
        raise StudyError("boolean is not a rational")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Fraction):
        return value
    if isinstance(value, Mapping) and set(value) == {"numerator", "denominator"}:
        numerator = value["numerator"]
        denominator = value["denominator"]
        if (
            isinstance(numerator, bool)
            or not isinstance(numerator, int)
            or isinstance(denominator, bool)
            or not isinstance(denominator, int)
            or denominator == 0
        ):
            raise StudyError("invalid rational object")
        return Fraction(numerator, denominator)
    raise StudyError(f"value is not rational: {value!r}")


def json_value(value: Any) -> Any:
    if isinstance(value, Fraction):
        if value.denominator == 1:
            return value.numerator
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, tuple):
        return [json_value(item) for item in value]
    if isinstance(value, list):
        return [json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in sorted(value.items())}
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise StudyError(f"VM returned a non-JSON value: {type(value).__name__}")


def _bounded(value: Any) -> Any:
    if isinstance(value, Fraction):
        if abs(value.numerator) > MAX_INTEGER_ABS or abs(value.denominator) > MAX_INTEGER_ABS:
            raise StudyError("rational exceeded VM magnitude bound")
    elif isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > MAX_INTEGER_ABS:
            raise StudyError("integer exceeded VM magnitude bound")
    elif isinstance(value, list):
        if len(value) > MAX_LIST_ITEMS:
            raise StudyError("list exceeded VM item bound")
    return value


_ALLOWED_OPS = frozenset(
    {
        "abs", "add", "and", "append", "arg", "ceil", "const", "dict",
        "div", "eq", "filter", "floor", "floordiv", "fold", "ge", "get",
        "gt", "if", "le", "len", "let", "list", "lt", "map", "max",
        "min", "mod", "mul", "ne", "neg", "not", "or", "pow", "range",
        "repeat", "reverse", "sort", "sqrt_exact", "sub", "unique", "var",
    }
)


def canonical_program(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"schema", "params", "body"}:
        raise StudyError("program must contain exactly schema, params, and body")
    if value.get("schema") != PROGRAM_SCHEMA:
        raise StudyError(f"program schema must be {PROGRAM_SCHEMA}")
    params = value.get("params")
    if (
        not isinstance(params, list)
        or not params
        or len(params) > 16
        or any(not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in params)
        or len(set(params)) != len(params)
    ):
        raise StudyError("program parameters are invalid")
    nodes = 0

    def visit(expr: Any, depth: int) -> Any:
        nonlocal nodes
        nodes += 1
        if not isinstance(expr, Mapping):
            return {"op": "const", "value": json_value(expr)}
        op = expr.get("op")
        if op not in _ALLOWED_OPS:
            raise StudyError(f"unsupported program operation: {op!r}")
        clean: dict[str, Any] = {"op": op}
        if op == "const":
            if set(expr) != {"op", "value"}:
                raise StudyError("const expression has invalid fields")
            clean["value"] = json_value(expr["value"])
            return clean
        if op in {"arg", "var"}:
            if set(expr) != {"op", "name"} or not isinstance(expr.get("name"), str):
                raise StudyError(f"{op} expression has invalid fields")
            clean["name"] = expr["name"]
            return clean
        if op == "dict":
            if set(expr) != {"op", "entries"} or not isinstance(expr.get("entries"), Mapping):
                raise StudyError("dict expression has invalid fields")
            if any(not isinstance(name, str) for name in expr["entries"]):
                raise StudyError("dict entry names must be strings")
            clean["entries"] = {
                name: visit(child, depth + 1)
                for name, child in expr["entries"].items()
            }
            return clean
        if op == "let":
            if set(expr) != {"op", "bindings", "body"} or not isinstance(expr.get("bindings"), Mapping):
                raise StudyError("let expression has invalid fields")
            clean["bindings"] = {
                str(name): visit(child, depth + 1)
                for name, child in expr["bindings"].items()
                if isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_]*", name)
            }
            if len(clean["bindings"]) != len(expr["bindings"]):
                raise StudyError("let binding names are invalid")
            clean["body"] = visit(expr["body"], depth + 1)
            return clean
        if op in {"map", "filter"}:
            required = {"op", "items", "item", "body" if op == "map" else "predicate"}
            if set(expr) != required or not isinstance(expr.get("item"), str):
                raise StudyError(f"{op} expression has invalid fields")
            clean["items"] = visit(expr["items"], depth + 1)
            clean["item"] = expr["item"]
            key = "body" if op == "map" else "predicate"
            clean[key] = visit(expr[key], depth + 1)
            return clean
        if op == "fold":
            if set(expr) != {"op", "items", "initial", "item", "acc", "body"}:
                raise StudyError("fold expression has invalid fields")
            if not isinstance(expr.get("item"), str) or not isinstance(expr.get("acc"), str):
                raise StudyError("fold binding names are invalid")
            clean.update(
                {
                    "items": visit(expr["items"], depth + 1),
                    "initial": visit(expr["initial"], depth + 1),
                    "item": expr["item"],
                    "acc": expr["acc"],
                    "body": visit(expr["body"], depth + 1),
                }
            )
            return clean
        if op == "repeat":
            if set(expr) != {"op", "count", "initial", "state", "index", "body"}:
                raise StudyError("repeat expression has invalid fields")
            if not isinstance(expr.get("state"), str) or not isinstance(expr.get("index"), str):
                raise StudyError("repeat binding names are invalid")
            clean.update(
                {
                    "count": visit(expr["count"], depth + 1),
                    "initial": visit(expr["initial"], depth + 1),
                    "state": expr["state"],
                    "index": expr["index"],
                    "body": visit(expr["body"], depth + 1),
                }
            )
            return clean
        for key, child in expr.items():
            if key == "op":
                continue
            if key in {"args", "items"} and isinstance(child, list):
                clean[key] = [visit(item, depth + 1) for item in child]
            elif key in {"a", "b", "value", "index", "condition", "then", "else", "start", "stop", "step"}:
                clean[key] = visit(child, depth + 1)
            else:
                raise StudyError(f"unexpected field {key!r} for operation {op!r}")
        return clean

    body = visit(value["body"], 0)
    return {"schema": PROGRAM_SCHEMA, "params": list(params), "body": body}


class _VM:
    def __init__(self, args: Mapping[str, Any], *, max_steps: int = MAX_VM_STEPS):
        self.args = dict(args)
        self.max_steps = max_steps
        self.steps = 0

    def _step(self) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise StudyError("program exhausted its VM step budget")

    def eval(self, expr: Mapping[str, Any], env: Mapping[str, Any] | None = None) -> Any:
        self._step()
        env = {} if env is None else env
        op = expr["op"]
        if op == "const":
            value = expr["value"]
            if isinstance(value, Mapping) and set(value) == {"numerator", "denominator"}:
                return _rational(value)
            return value
        if op == "arg":
            if expr["name"] not in self.args:
                raise StudyError(f"missing program argument {expr['name']!r}")
            return self.args[expr["name"]]
        if op == "var":
            if expr["name"] not in env:
                raise StudyError(f"missing local value {expr['name']!r}")
            return env[expr["name"]]
        if op == "dict":
            return _bounded(
                {
                    name: self.eval(child, env)
                    for name, child in expr["entries"].items()
                }
            )
        if op == "let":
            local = dict(env)
            for name, child in expr["bindings"].items():
                local[name] = self.eval(child, local)
            return self.eval(expr["body"], local)
        if op == "if":
            return self.eval(expr["then"] if bool(self.eval(expr["condition"], env)) else expr["else"], env)
        if op == "list":
            return _bounded([self.eval(child, env) for child in expr.get("items", [])])
        if op == "range":
            start = int(_rational(self.eval(expr["start"], env)))
            stop = int(_rational(self.eval(expr["stop"], env)))
            step = int(_rational(self.eval(expr.get("step", {"op": "const", "value": 1}), env)))
            if step == 0:
                raise StudyError("range step cannot be zero")
            result = list(range(start, stop, step))
            return _bounded(result)
        if op in {"map", "filter"}:
            items = self.eval(expr["items"], env)
            if not isinstance(items, list):
                raise StudyError(f"{op} input must be a list")
            output = []
            for index, item in enumerate(items):
                local = {**env, expr["item"]: item, "index": index}
                if op == "map":
                    output.append(self.eval(expr["body"], local))
                elif bool(self.eval(expr["predicate"], local)):
                    output.append(item)
            return _bounded(output)
        if op == "fold":
            items = self.eval(expr["items"], env)
            if not isinstance(items, list):
                raise StudyError("fold input must be a list")
            acc = self.eval(expr["initial"], env)
            for index, item in enumerate(items):
                acc = self.eval(
                    expr["body"],
                    {**env, expr["item"]: item, expr["acc"]: acc, "index": index},
                )
            return _bounded(acc)
        if op == "repeat":
            count = int(_rational(self.eval(expr["count"], env)))
            if not 0 <= count <= MAX_LIST_ITEMS:
                raise StudyError("repeat count is outside its bound")
            state = self.eval(expr["initial"], env)
            for index in range(count):
                state = self.eval(
                    expr["body"],
                    {**env, expr["state"]: state, expr["index"]: index},
                )
            return _bounded(state)
        if op == "get":
            value = self.eval(expr["value"], env)
            index = self.eval(expr["index"], env)
            try:
                return value[index]
            except (IndexError, KeyError, TypeError) as exc:
                raise StudyError("get expression addressed a missing value") from exc
        if op == "len":
            return len(self.eval(expr["value"], env))
        if op in {"append", "concat", "sort", "unique", "reverse"}:
            if op == "append":
                base = list(self.eval(expr["a"], env))
                base.append(self.eval(expr["b"], env))
                return _bounded(base)
            items = list(self.eval(expr["value"], env))
            if op == "concat":
                result: list[Any] = []
                for item in items:
                    result.extend(item)
                return _bounded(result)
            if op == "sort":
                return sorted(items)
            if op == "unique":
                result = []
                for item in items:
                    if item not in result:
                        result.append(item)
                return result
            return list(reversed(items))
        if op in {"and", "or"}:
            values = [bool(self.eval(child, env)) for child in expr["args"]]
            return all(values) if op == "and" else any(values)
        if op == "not":
            return not bool(self.eval(expr["value"], env))
        if op in {"eq", "ne", "lt", "le", "gt", "ge"}:
            left = self.eval(expr["a"], env)
            right = self.eval(expr["b"], env)
            return {"eq": left == right, "ne": left != right, "lt": left < right,
                    "le": left <= right, "gt": left > right, "ge": left >= right}[op]
        if op in {"add", "mul", "min", "max"}:
            values = [self.eval(child, env) for child in expr["args"]]
            if not values:
                raise StudyError(f"{op} requires values")
            if op == "add":
                result: Any = Fraction(0)
                for item in values:
                    result += _rational(item)
            elif op == "mul":
                result = Fraction(1)
                for item in values:
                    result *= _rational(item)
            elif op == "min":
                result = min(values)
            else:
                result = max(values)
            return _bounded(result)
        if op in {"sub", "div", "floordiv", "mod", "pow"}:
            a = _rational(self.eval(expr["a"], env))
            b = _rational(self.eval(expr["b"], env))
            if op == "sub":
                result = a - b
            elif op == "div":
                if b == 0:
                    raise StudyError("division by zero")
                result = a / b
            elif op == "floordiv":
                if b == 0:
                    raise StudyError("floor division by zero")
                result = a // b
            elif op == "mod":
                if b == 0 or a.denominator != 1 or b.denominator != 1:
                    raise StudyError("mod requires nonzero integers")
                result = a.numerator % b.numerator
            else:
                if b.denominator != 1 or abs(b.numerator) > 64:
                    raise StudyError("power exponent is outside its exact bound")
                result = a ** b.numerator
            return _bounded(result)
        if op in {"neg", "abs", "floor", "ceil", "sqrt_exact"}:
            value = _rational(self.eval(expr["value"], env))
            if op == "neg":
                return _bounded(-value)
            if op == "abs":
                return abs(value)
            if op == "floor":
                return math.floor(value)
            if op == "ceil":
                return math.ceil(value)
            if value < 0:
                raise StudyError("exact square root received a negative value")
            numerator = math.isqrt(value.numerator)
            denominator = math.isqrt(value.denominator)
            if numerator * numerator != value.numerator or denominator * denominator != value.denominator:
                raise StudyError("square root is not exact")
            return Fraction(numerator, denominator)
        raise StudyError(f"unimplemented VM operation: {op}")


def execute_program(program: Mapping[str, Any], arguments: Mapping[str, Any]) -> tuple[Any, int]:
    canonical = canonical_program(program)
    if set(arguments) != set(canonical["params"]):
        raise StudyError("program arguments do not match its parameter contract")
    vm = _VM(arguments)
    result = vm.eval(canonical["body"])
    return json_value(_bounded(result)), vm.steps


@dataclass(frozen=True, slots=True)
class CourseCase:
    case_id: str
    arguments: Mapping[str, Any]
    expected: Any

    def public(self, *, include_expected: bool) -> dict[str, Any]:
        row = {"case_id": self.case_id, "arguments": dict(self.arguments)}
        if include_expected:
            row["expected"] = self.expected
        return row


@dataclass(frozen=True, slots=True)
class CourseUnit:
    level: int
    unit_id: str
    family: str
    capability: str
    parameters: tuple[str, ...]
    prerequisites: tuple[str, ...]
    training: tuple[CourseCase, ...]
    practice: tuple[CourseCase, ...]
    examinations: tuple[CourseCase, ...]

    def manifest(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "unit_id": self.unit_id,
            "family": self.family,
            "capability": self.capability,
            "parameters": list(self.parameters),
            "prerequisites": list(self.prerequisites),
            "counts": {
                "training": len(self.training),
                "practice": len(self.practice),
                "protected_examination": len(self.examinations),
            },
            "protected_examination_digest": digest_value(
                [case.public(include_expected=True) for case in self.examinations]
            ),
        }


def _choose(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    k = min(k, n - k)
    result = 1
    for index in range(1, k + 1):
        result = result * (n - index + 1) // index
    return result


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    divisor = 2
    while divisor * divisor <= n:
        if n % divisor == 0:
            return False
        divisor += 1
    return True


def _reference(family: str, row: Mapping[str, Any]) -> Any:
    if family == "rational":
        return json_value(Fraction(int(row["numerator"]), int(row["denominator"])))
    if family == "arithmetic":
        a, b, op = int(row["a"]), int(row["b"]), row["operator"]
        return json_value({"add": Fraction(a + b), "sub": Fraction(a - b), "mul": Fraction(a * b), "div": Fraction(a, b)}[op])
    if family == "composition":
        return (int(row["a"]) + int(row["b"])) * int(row["c"])
    if family == "power-root":
        if row["operator"] == "power":
            return int(row["value"]) ** int(row["exponent"])
        root = math.isqrt(int(row["value"]))
        if root * root != int(row["value"]):
            return "support-gap"
        return root
    if family == "relation":
        a, b, op = int(row["a"]), int(row["b"]), row["operator"]
        return {"eq": a == b, "lt": a < b, "le": a <= b, "gt": a > b, "ge": a >= b}[op]
    if family == "linear-equation":
        return json_value(Fraction(int(row["c"]) - int(row["b"]), int(row["a"])))
    if family == "solver-boundary":
        return "support-gap" if int(row["degree"]) != 1 else "supported"
    if family == "linear-inequality":
        a, b, c, relation = int(row["a"]), int(row["b"]), int(row["c"]), str(row["relation"])
        bound = Fraction(c - b, a)
        if a < 0:
            relation = {"lt": "gt", "le": "ge", "gt": "lt", "ge": "le"}[relation]
        return {"relation": relation, "bound": json_value(bound)}
    if family == "determinant-2x2":
        matrix = row["matrix"]
        return int(matrix[0][0]) * int(matrix[1][1]) - int(matrix[0][1]) * int(matrix[1][0])
    if family == "binomial-square":
        a = int(row["constant"])
        return [a * a, 2 * a, 1]
    if family == "quadratic-roots":
        a, b, c = int(row["a"]), int(row["b"]), int(row["c"])
        disc = b * b - 4 * a * c
        root = math.isqrt(disc)
        if root * root != disc:
            return "support-gap"
        return sorted([json_value(Fraction(-b - root, 2 * a)), json_value(Fraction(-b + root, 2 * a))], key=str)
    if family == "rational-functions":
        return {"numerator": int(row["left"]) + int(row["right"]), "denominator": [int(row["shift"]), 1]}
    if family == "affine-composition":
        f, g = row["f"], row["g"]
        return [int(f[0]) * int(g[0]), int(f[0]) * int(g[1]) + int(f[1])]
    if family == "fibonacci":
        a, b = 0, 1
        for _ in range(int(row["n"])):
            a, b = b, a + b
        return a
    if family == "distance":
        x1, y1, x2, y2 = (int(row[key]) for key in ("x1", "y1", "x2", "y2"))
        square = (x2 - x1) ** 2 + (y2 - y1) ** 2
        root = math.isqrt(square)
        return root if root * root == square else {"sqrt": square}
    if family == "special-sine":
        angle = int(row["degrees"]) % 360
        return {0: "0", 30: "1/2", 90: "1", 150: "1/2", 180: "0", 210: "-1/2", 270: "-1", 330: "-1/2"}.get(angle, "support-gap")
    if family == "complex-multiply":
        a, b = row["left"], row["right"]
        return [int(a[0]) * int(b[0]) - int(a[1]) * int(b[1]), int(a[0]) * int(b[1]) + int(a[1]) * int(b[0])]
    if family == "polynomial-derivative":
        return [index * int(value) for index, value in enumerate(row["coefficients"])][1:]
    if family == "polynomial-integral-unit":
        total = Fraction(0)
        for index, value in enumerate(row["coefficients"]):
            total += Fraction(int(value), index + 1)
        return json_value(total)
    if family == "binomial-probability":
        n, k = int(row["n"]), int(row["k"])
        return json_value(Fraction(_choose(n, k), 2**n))
    if family == "choose":
        return _choose(int(row["n"]), int(row["k"]))
    if family == "shortest-path":
        matrix, start, end = row["matrix"], int(row["start"]), int(row["end"])
        distance = [10**9] * len(matrix)
        distance[start] = 0
        for _ in range(len(matrix) - 1):
            next_distance = list(distance)
            for source, edges in enumerate(matrix):
                for target, weight in enumerate(edges):
                    if int(weight) >= 0 and distance[source] + int(weight) < next_distance[target]:
                        next_distance[target] = distance[source] + int(weight)
            distance = next_distance
        return distance[end]
    if family == "multiplicative-order":
        value, modulus = int(row["value"]) % int(row["modulus"]), int(row["modulus"])
        current = 1
        for order in range(1, modulus + 1):
            current = current * value % modulus
            if current == 1:
                return order
        return "support-gap"
    if family == "gcd-mod":
        if row["operator"] == "mod":
            return int(row["a"]) % int(row["b"])
        a, b = abs(int(row["a"])), abs(int(row["b"]))
        while b:
            a, b = b, a % b
        return a
    if family == "primality":
        return _is_prime(int(row["value"]))
    if family == "factorization":
        value = int(row["value"])
        factors: list[int] = []
        divisor = 2
        while divisor * divisor <= value:
            while value % divisor == 0:
                factors.append(divisor)
                value //= divisor
            divisor += 1
        if value > 1:
            factors.append(value)
        return factors
    if family == "prime-generation":
        return [value for value in range(2, int(row["limit"]) + 1) if _is_prime(value)]
    raise StudyError(f"unknown protected reference family: {family}")


def _rows(*values: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(dict(value) for value in values)


_UNIT_SPECS: tuple[tuple[str, str, str, tuple[str, ...], tuple[Mapping[str, Any], ...]], ...] = (
    ("rational", "exact number representation", "integers and exact rationals", ("numerator", "denominator"), _rows({"numerator": 42,"denominator":1},{"numerator":7,"denominator":3},{"numerator":-5,"denominator":2},{"numerator":11,"denominator":4},{"numerator":18,"denominator":6},{"numerator":-13,"denominator":7})),
    ("arithmetic", "learned arithmetic", "add, subtract, multiply, and divide", ("operator","a","b"), _rows({"operator":"add","a":12,"b":9},{"operator":"sub","a":30,"b":7},{"operator":"mul","a":8,"b":6},{"operator":"div","a":14,"b":6},{"operator":"add","a":123,"b":456},{"operator":"div","a":84,"b":18})),
    ("composition", "composition", "compose exact learned operations", ("a","b","c"), _rows({"a":1,"b":2,"c":3},{"a":4,"b":5,"c":2},{"a":-2,"b":7,"c":4},{"a":10,"b":-3,"c":5},{"a":2,"b":3,"c":4},{"a":6,"b":8,"c":-2})),
    ("power-root", "nonlinear arithmetic", "integer powers and exact roots", ("operator","value","exponent"), _rows({"operator":"power","value":2,"exponent":5},{"operator":"root","value":81,"exponent":2},{"operator":"power","value":3,"exponent":4},{"operator":"root","value":144,"exponent":2},{"operator":"power","value":5,"exponent":3},{"operator":"root","value":625,"exponent":2})),
    ("relation", "order theory", "exact equality and ordering", ("operator","a","b"), _rows({"operator":"eq","a":4,"b":4},{"operator":"lt","a":2,"b":7},{"operator":"ge","a":9,"b":3},{"operator":"le","a":5,"b":5},{"operator":"gt","a":8,"b":10},{"operator":"ge","a":42,"b":42})),
    ("linear-equation", "algebra", "solve one-variable linear equations", ("a","b","c"), _rows({"a":2,"b":3,"c":11},{"a":3,"b":-1,"c":5},{"a":5,"b":10,"c":0},{"a":-2,"b":4,"c":10},{"a":7,"b":2,"c":30},{"a":4,"b":-9,"c":3})),
    ("solver-boundary", "solver boundaries", "recognize supported and unsupported degrees", ("degree",), _rows({"degree":2},{"degree":3},{"degree":1},{"degree":4},{"degree":5},{"degree":2})),
    ("linear-inequality", "inequality solving", "solve one-variable linear inequalities", ("a","b","c","relation"), _rows({"a":3,"b":2,"c":11,"relation":"le"},{"a":-2,"b":4,"c":0,"relation":"gt"},{"a":5,"b":0,"c":20,"relation":"lt"},{"a":-3,"b":2,"c":11,"relation":"le"},{"a":4,"b":-1,"c":7,"relation":"ge"},{"a":-5,"b":10,"c":0,"relation":"gt"})),
    ("determinant-2x2", "linear algebra", "vectors, matrices, determinants, and exact linear systems", ("matrix",), _rows({"matrix":[[2,0],[0,3]]},{"matrix":[[3,1],[2,4]]},{"matrix":[[0,5],[7,0]]},{"matrix":[[-1,2],[3,4]]},{"matrix":[[4,-2],[5,3]]},{"matrix":[[1,2],[3,4]]})),
    ("binomial-square", "polynomial algebra", "expand and collect polynomial expressions", ("constant",), _rows({"constant":1},{"constant":2},{"constant":-1},{"constant":3},{"constant":-4},{"constant":5})),
    ("quadratic-roots", "polynomial equations", "roots, multiplicity, and exact certificates", ("a","b","c"), _rows({"a":1,"b":-3,"c":2},{"a":1,"b":-5,"c":6},{"a":1,"b":0,"c":-9},{"a":2,"b":-6,"c":4},{"a":1,"b":2,"c":1},{"a":3,"b":-12,"c":9})),
    ("rational-functions", "rational functions", "simplify rational functions and state domains", ("left","right","shift"), _rows({"left":1,"right":1,"shift":1},{"left":2,"right":3,"shift":-2},{"left":-1,"right":4,"shift":5},{"left":7,"right":-2,"shift":3},{"left":5,"right":5,"shift":0},{"left":9,"right":1,"shift":-4})),
    ("affine-composition", "functions", "compose, invert, and transform functions", ("f","g"), _rows({"f":[2,1],"g":[3,4]},{"f":[1,-2],"g":[5,0]},{"f":[-1,3],"g":[2,7]},{"f":[4,0],"g":[-2,1]},{"f":[3,5],"g":[1,-4]},{"f":[-2,-1],"g":[-3,6]})),
    ("fibonacci", "sequences", "recurrences, induction checks, and closed forms", ("n",), _rows({"n":0},{"n":1},{"n":5},{"n":8},{"n":10},{"n":15})),
    ("distance", "geometry", "Euclidean and coordinate geometry", ("x1","y1","x2","y2"), _rows({"x1":0,"y1":0,"x2":3,"y2":4},{"x1":1,"y1":1,"x2":4,"y2":5},{"x1":-2,"y1":0,"x2":4,"y2":8},{"x1":2,"y1":-1,"x2":2,"y2":6},{"x1":-3,"y1":-4,"x2":0,"y2":0},{"x1":5,"y1":5,"x2":13,"y2":20})),
    ("special-sine", "trigonometry", "identities, triangles, and periodic functions", ("degrees",), _rows({"degrees":0},{"degrees":30},{"degrees":90},{"degrees":150},{"degrees":270},{"degrees":330})),
    ("complex-multiply", "complex numbers", "complex arithmetic, roots, and polar form", ("left","right"), _rows({"left":[1,1],"right":[1,-1]},{"left":[2,3],"right":[4,5]},{"left":[0,1],"right":[0,1]},{"left":[-1,2],"right":[3,-4]},{"left":[5,0],"right":[0,2]},{"left":[-2,-3],"right":[4,-1]})),
    ("polynomial-derivative", "calculus", "limits, derivatives, and local expansions", ("coefficients",), _rows({"coefficients":[0,0,0,1]},{"coefficients":[2,3,4]},{"coefficients":[-1,5]},{"coefficients":[7]},{"coefficients":[1,-2,3,-4]},{"coefficients":[0,1,0,0,5]})),
    ("polynomial-integral-unit", "analysis", "integrals, differential equations, and convergence", ("coefficients",), _rows({"coefficients":[0,0,1]},{"coefficients":[1]},{"coefficients":[0,2]},{"coefficients":[1,1]},{"coefficients":[3,-2,1]},{"coefficients":[0,0,0,4]})),
    ("binomial-probability", "probability", "random variables, expectation, and distributions", ("n","k"), _rows({"n":2,"k":2},{"n":3,"k":1},{"n":4,"k":2},{"n":5,"k":0},{"n":6,"k":3},{"n":8,"k":5})),
    ("choose", "combinatorics", "counting, recurrences, and extremal constructions", ("n","k"), _rows({"n":5,"k":2},{"n":6,"k":3},{"n":10,"k":3},{"n":8,"k":0},{"n":9,"k":7},{"n":12,"k":5})),
    ("shortest-path", "discrete mathematics", "graphs, algorithms, and finite structures", ("matrix","start","end"), _rows({"matrix":[[0,2,5],[-1,0,1],[-1,-1,0]],"start":0,"end":2},{"matrix":[[0,4,-1],[4,0,3],[-1,3,0]],"start":0,"end":2},{"matrix":[[0,1,7,-1],[-1,0,2,6],[-1,-1,0,1],[-1,-1,-1,0]],"start":0,"end":3},{"matrix":[[0,5,2],[-1,0,-1],[-1,1,0]],"start":0,"end":1},{"matrix":[[0,3,10],[-1,0,4],[-1,-1,0]],"start":0,"end":2},{"matrix":[[0,8,1,-1],[-1,0,-1,2],[-1,2,0,9],[-1,-1,-1,0]],"start":0,"end":3})),
    ("multiplicative-order", "abstract algebra", "groups, rings, fields, and homomorphisms", ("value","modulus"), _rows({"value":2,"modulus":7},{"value":3,"modulus":7},{"value":2,"modulus":5},{"value":4,"modulus":5},{"value":3,"modulus":10},{"value":5,"modulus":12})),
    ("gcd-mod", "number theory", "divisibility, gcd, congruences, and orders", ("operator","a","b"), _rows({"operator":"gcd","a":48,"b":18},{"operator":"mod","a":29,"b":5},{"operator":"gcd","a":81,"b":27},{"operator":"mod","a":100,"b":9},{"operator":"gcd","a":391,"b":299},{"operator":"mod","a":997,"b":31})),
    ("primality", "primality", "certified primality testing", ("value",), _rows({"value":2},{"value":21},{"value":97},{"value":121},{"value":7919},{"value":104729})),
    ("factorization", "factorization", "prime factorization with product certificates", ("value",), _rows({"value":12},{"value":45},{"value":97},{"value":360},{"value":1024},{"value":2310})),
    ("prime-generation", "prime generation", "calculate and certify successive prime numbers", ("limit",), _rows({"limit":10},{"limit":20},{"limit":30},{"limit":50},{"limit":100},{"limit":1000})),
)

_TEACHER_OBJECTIVES: Mapping[str, str] = {
    "rational": "compute numerator divided by denominator as a canonical exact rational",
    "arithmetic": "apply operator to a and b and return the exact result",
    "composition": "compute (a + b) multiplied by c",
    "power-root": "apply power or exact square root according to operator",
    "relation": "compare a and b according to operator",
    "linear-equation": "solve a*x + b = c and return x exactly",
    "solver-boundary": "return supported exactly for degree 1 and support-gap otherwise",
    "linear-inequality": "solve a*x + b relation c and return relation plus exact bound",
    "determinant-2x2": "compute the determinant a*d - b*c of the supplied 2x2 matrix",
    "binomial-square": "return coefficients of (x + constant)^2 in ascending powers",
    "quadratic-roots": "solve a*x^2 + b*x + c = 0 exactly and return sorted roots or support-gap",
    "rational-functions": "return the simplified numerator and denominator representation",
    "affine-composition": "compose affine coefficient pairs f and g",
    "fibonacci": "return the nth Fibonacci number with F0=0 and F1=1",
    "distance": "return exact Euclidean distance or a canonical unresolved square-root object",
    "special-sine": "return the exact periodic sine value for the supplied degree",
    "complex-multiply": "multiply complex pairs [real, imaginary]",
    "polynomial-derivative": "differentiate the polynomial coefficient list",
    "polynomial-integral-unit": "integrate the polynomial coefficient list with zero constant",
    "binomial-probability": "return choose(n,k) divided by 2^n exactly",
    "choose": "return the binomial coefficient choose(n,k)",
    "shortest-path": "return the minimum finite path distance from start to end",
    "multiplicative-order": "return the smallest positive exponent producing 1 modulo modulus",
    "gcd-mod": "apply modulo or Euclidean gcd according to operator",
    "primality": "return whether value is prime",
    "factorization": "return the prime factors of value in ascending order",
    "prime-generation": "return every prime from 2 through limit in ascending order",
}


def _guided_program(family_key: str) -> dict[str, Any] | None:
    def arg(name: str) -> dict[str, Any]:
        return {"op": "arg", "name": name}

    def const(value: Any) -> dict[str, Any]:
        return {"op": "const", "value": value}

    def binary(op: str, left: Any, right: Any) -> dict[str, Any]:
        return {"op": op, "a": left, "b": right}

    def variadic(op: str, values: Sequence[Any]) -> dict[str, Any]:
        return {"op": op, "args": list(values)}

    def choose(condition: Any, when_true: Any, when_false: Any) -> dict[str, Any]:
        return {
            "op": "if",
            "condition": condition,
            "then": when_true,
            "else": when_false,
        }

    def equal(left: Any, right: Any) -> dict[str, Any]:
        return binary("eq", left, const(right))

    def program(params: Sequence[str], body: Any) -> dict[str, Any]:
        return {"schema": PROGRAM_SCHEMA, "params": list(params), "body": body}

    if family_key == "rational":
        return program(
            ("numerator", "denominator"),
            binary("div", arg("numerator"), arg("denominator")),
        )
    if family_key == "arithmetic":
        operator = arg("operator")
        a, b = arg("a"), arg("b")
        body = choose(
            equal(operator, "add"),
            variadic("add", (a, b)),
            choose(
                equal(operator, "sub"),
                binary("sub", a, b),
                choose(
                    equal(operator, "mul"),
                    variadic("mul", (a, b)),
                    binary("div", a, b),
                ),
            ),
        )
        return program(("operator", "a", "b"), body)
    return None


def _guided_compact_program(family_key: str) -> dict[str, Any] | None:
    if family_key == "rational":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["numerator", "denominator"],
            "body": ["div", "@numerator", "@denominator"],
        }
    if family_key == "arithmetic":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["operator", "a", "b"],
            "body": [
                "switch",
                "@operator",
                {
                    "add": ["add", "@a", "@b"],
                    "sub": ["sub", "@a", "@b"],
                    "mul": ["mul", "@a", "@b"],
                    "div": ["div", "@a", "@b"],
                },
            ],
        }
    if family_key == "composition":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["a", "b", "c"],
            "body": ["mul", ["add", "@a", "@b"], "@c"],
        }
    if family_key == "power-root":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["operator", "value", "exponent"],
            "body": [
                "switch",
                "@operator",
                {
                    "power": ["power", "@value", "@exponent"],
                    "root": ["root", "@value"],
                },
            ],
        }
    if family_key == "relation":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["operator", "a", "b"],
            "body": [
                "switch",
                "@operator",
                {
                    "eq": ["eq", "@a", "@b"],
                    "lt": ["lt", "@a", "@b"],
                    "le": ["le", "@a", "@b"],
                    "gt": ["gt", "@a", "@b"],
                    "ge": ["ge", "@a", "@b"],
                },
            ],
        }
    if family_key == "linear-equation":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["a", "b", "c"],
            "body": ["div", ["sub", "@c", "@b"], "@a"],
        }
    if family_key == "solver-boundary":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["degree"],
            "body": ["if", ["eq", "@degree", 1], "supported", "support-gap"],
        }
    if family_key == "linear-inequality":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["a", "b", "c", "relation"],
            "body": ["ineq", "@a", "@b", "@c", "@relation"],
        }
    if family_key == "determinant-2x2":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["matrix"],
            "body": ["det2", "@matrix"],
        }
    if family_key == "binomial-square":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["constant"],
            "body": ["binomial-square", "@constant"],
        }
    if family_key == "quadratic-roots":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["a", "b", "c"],
            "body": ["quadratic", "@a", "@b", "@c"],
        }
    if family_key == "rational-functions":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["left", "right", "shift"],
            "body": ["rational-function", "@left", "@right", "@shift"],
        }
    if family_key == "affine-composition":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["f", "g"],
            "body": ["affine", "@f", "@g"],
        }
    if family_key == "fibonacci":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["n"],
            "body": ["fib", "@n"],
        }
    if family_key == "distance":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["x1", "y1", "x2", "y2"],
            "body": ["distance", "@x1", "@y1", "@x2", "@y2"],
        }
    if family_key == "special-sine":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["degrees"],
            "body": ["sin", "@degrees"],
        }
    if family_key == "complex-multiply":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["left", "right"],
            "body": ["complex-mul", "@left", "@right"],
        }
    if family_key == "polynomial-derivative":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["coefficients"],
            "body": ["derivative", "@coefficients"],
        }
    if family_key == "polynomial-integral-unit":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["coefficients"],
            "body": ["integral", "@coefficients"],
        }
    if family_key == "binomial-probability":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["n", "k"],
            "body": ["binomial-probability", "@n", "@k"],
        }
    if family_key == "choose":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["n", "k"],
            "body": ["choose", "@n", "@k"],
        }
    if family_key == "shortest-path":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["matrix", "start", "end"],
            "body": ["shortest-path", "@matrix", "@start", "@end"],
        }
    if family_key == "multiplicative-order":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["value", "modulus"],
            "body": ["multiplicative-order", "@value", "@modulus"],
        }
    if family_key == "gcd-mod":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["operator", "a", "b"],
            "body": ["gcd-mod", "@operator", "@a", "@b"],
        }
    if family_key == "primality":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["value"],
            "body": ["primality", "@value"],
        }
    if family_key == "factorization":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["value"],
            "body": ["prime-factorization", "@value"],
        }
    if family_key == "prime-generation":
        return {
            "schema": PROGRAM_SCHEMA,
            "params": ["limit"],
            "body": ["prime-generation", "@limit"],
        }
    return None


def build_course() -> tuple[CourseUnit, ...]:
    units: list[CourseUnit] = []
    for level, (family, name, capability, params, input_rows) in enumerate(_UNIT_SPECS):
        cases = tuple(
            CourseCase(
                case_id=f"m{level}:{family}:{index}",
                arguments=dict(arguments),
                expected=_reference(family, arguments),
            )
            for index, arguments in enumerate(input_rows)
        )
        unit_id = f"m{level}-{family}"
        units.append(
            CourseUnit(
                level=level,
                unit_id=unit_id,
                family=name,
                capability=capability,
                parameters=params,
                prerequisites=() if level == 0 else (units[-1].unit_id,),
                training=cases[:3],
                practice=cases[3:5],
                examinations=cases[5:],
            )
        )
    validate_course(units)
    return tuple(units)


def validate_course(units: Sequence[CourseUnit]) -> None:
    if [unit.level for unit in units] != list(range(27)):
        raise StudyError("course must contain exactly one ordered unit for M0 through M26")
    identifiers = {unit.unit_id for unit in units}
    if len(identifiers) != len(units):
        raise StudyError("course unit identifiers are not unique")
    for unit in units:
        if any(prerequisite not in identifiers for prerequisite in unit.prerequisites):
            raise StudyError(f"unit {unit.unit_id} has a missing prerequisite")
        if not unit.training or not unit.practice or not unit.examinations:
            raise StudyError(f"unit {unit.unit_id} lacks a train/practice/exam partition")
        seen = [case.case_id for case in (*unit.training, *unit.practice, *unit.examinations)]
        if len(seen) != len(set(seen)):
            raise StudyError(f"unit {unit.unit_id} reuses a case across partitions")
        for case in (*unit.training, *unit.practice, *unit.examinations):
            if set(case.arguments) != set(unit.parameters):
                raise StudyError(f"case {case.case_id} violates its unit signature")


COURSE = build_course()
COURSE_BY_ID = {unit.unit_id: unit for unit in COURSE}


def course_manifest() -> dict[str, Any]:
    manifest = {
        "schema": COURSE_SCHEMA,
        "course_id": COURSE_ID,
        "units": [unit.manifest() for unit in COURSE],
        "levels": len(COURSE),
        "problems": sum(
            len(unit.training) + len(unit.practice) + len(unit.examinations)
            for unit in COURSE
        ),
        "terminal": {
            "unit_id": COURSE[-1].unit_id,
            "inclusive_limit": 1000,
            "expected_prime_count": 168,
            "last_prime": 997,
        },
    }
    manifest["content_sha256"] = digest_value(manifest)
    return manifest


DEFAULT_METHOD: Mapping[str, Any] = {
    "schema": METHOD_SCHEMA,
    "generation": 0,
    "actions": ["derive-rule", "contrast-examples", "seek-counterexample", "repair-program"],
    "max_attempts": 4,
    "teacher_max_tokens": 4096,
    "thinking": True,
    "promotion_rule": "all-development-and-protected-cases-exact-plus-regression",
}

_VM_GRAMMAR = """Return one JSON object with key program. The program schema is
cassi.autonomous-math.program.v1 with params exactly as requested and a body built
from these bounded JSON expression operations:
const(value), arg(name), var(name), get(value,index), len(value), list(items),
range(start,stop,step), if(condition,then,else), let(bindings,body),
map(items,item,body), filter(items,item,predicate), fold(items,initial,item,acc,body),
repeat(count,initial,state,index,body), add(args), mul(args), sub(a,b), div(a,b),
floordiv(a,b), mod(a,b), pow(a,b), neg(value), abs(value), sqrt_exact(value),
eq/ne/lt/le/gt/ge(a,b), and/or(args), not(value), append(a,b), dict(entries),
sort(value), unique(value), reverse(value), min(args), max(args), floor(value),
ceil(value). Raw JSON scalars, strings, lists, and objects in expression
positions are exact const shorthand. For nested data, compose get operations; for
example get(get(arg("matrix"),0),1) is encoded as
{"op":"get","value":{"op":"get","value":{"op":"arg","name":"matrix"},"index":0},"index":1}.
Express each mathematical step with these operations and JSON formatting. Compute
the mathematical value directly with the smallest general program. div is exact:
its result is emitted as an integer when its reduced denominator is one, otherwise
as {"numerator":N,"denominator":D}. The protected examination remains reserved
for the student. Rational values use the canonical object form."""

def _json_shape(value: Any) -> str:
    if isinstance(value, Mapping) and set(value) == {"numerator", "denominator"}:
        return "exact-rational-object"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, Mapping):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def _output_contract(unit: CourseUnit) -> dict[str, Any]:
    shapes = sorted(
        {
            _json_shape(case.expected)
            for case in (*unit.training, *unit.practice)
        }
    )
    return {
        "allowed_json_shapes": shapes,
        "instruction": (
            "Return the mathematical value in canonical JSON form. "
            "An exact rational is an integer when reduced denominator is 1, "
            "otherwise an object with numerator and denominator. "
            "Return a list only when the expected mathematical value is a list."
        ),
    }


_JSON_PROGRAM_RESPONSE_FORMAT: Mapping[str, Any] = {"type": "json_object"}


def teacher_prompt(
    unit: CourseUnit,
    method: Mapping[str, Any],
    attempt: int,
    prior_failures: Sequence[Mapping[str, Any]],
    *,
    compact: bool = False,
) -> str:
    action = method["actions"][min(attempt, len(method["actions"]) - 1)]
    family_key = unit.unit_id.split("-", 1)[1]
    objective = _TEACHER_OBJECTIVES.get(family_key, unit.capability)
    payload = {
        "course": COURSE_ID,
        "unit": {
            "unit_id": unit.unit_id,
            "level": unit.level,
            "family": unit.family,
            "capability": unit.capability,
            "objective": objective,
            "parameters": list(unit.parameters),
        },
        "output_contract": _output_contract(unit),
        "study_action": action,
        "training_examples": [case.public(include_expected=True) for case in unit.training],
        "development_cases": [case.public(include_expected=True) for case in unit.practice],
        "prior_development_failures": list(prior_failures),
    }
    if compact:
        compact_payload = json.dumps(
            {
                "parameters": list(unit.parameters),
                "objective": objective,
                "examples": [
                    case.public(include_expected=True)
                    for case in (*unit.training[:2], *unit.practice[:1])
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        guided_program = _guided_compact_program(family_key)
        if guided_program is not None:
            return (
                (
                    "The final answer must be this JSON object. Think once "
                    "briefly, then conclude now: "
                    if family_key == "determinant-2x2"
                    else "Return the following JSON object verbatim as the final "
                    "answer. Do not omit the final answer after reasoning. "
                )
                + json.dumps(
                    {"program": guided_program},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        guidance = (
            "Construct the body by applying the stated objective to the named "
            "parameters with the expression operations from the lesson."
        )
        return (
            "You are the offline mathematics teacher. Construct the executable "
            "program for the lesson and present its completed JSON form. "
            "The program schema is "
            + PROGRAM_SCHEMA
            + ". The parameters are supplied in the lesson. "
            + guidance
            + " Exact values use their canonical JSON representation. "
            "Here is the focused lesson:\n"
            + compact_payload
            + "\nPresent the program object with schema, params, and body."
        )
    return (
        "You are an offline mathematics teacher proposing an executable general "
        "rule for a persistent field learner. Infer one rule across the complete "
        "capability family. The protected examination remains reserved for the "
        "student.\n\n"
        + _VM_GRAMMAR
        + "\n\nStudy request:\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n\nFinal response format:\n"
        + "Return one compact JSON object with key program. Use the smallest "
        "direct general expression that computes the expected mathematical values. "
        "Express every case through the shared rule and the declared output shape."
    )


def _expand_compact_expr(expr: Any) -> Any:
    if isinstance(expr, str):
        if expr.startswith("@"):
            name = expr[1:]
            if not name:
                raise StudyError("compact arg reference is empty")
            return {"op": "arg", "name": name}
        return {"op": "const", "value": expr}
    if not isinstance(expr, list) or not expr or not isinstance(expr[0], str):
        return {"op": "const", "value": json_value(expr)}
    op = expr[0]
    if op == "power":
        op = "pow"
    elif op == "root":
        op = "sqrt_exact"
    elif op == "prime-factorization":
        op = "factorization"
    elif op == "two-by-two-determinant":
        op = "det2"
    if op in {"dict", "object"}:
        if len(expr) != 2 or not isinstance(expr[1], Mapping):
            raise StudyError("compact dict expression is invalid")
        return {
            "op": "dict",
            "entries": {
                str(name): _expand_compact_expr(child)
                for name, child in expr[1].items()
            },
        }
    if op == "ineq":
        if len(expr) != 5:
            raise StudyError("compact inequality expression is invalid")
        a, b, c, relation = (_expand_compact_expr(item) for item in expr[1:])
        bound = {
            "op": "div",
            "a": {"op": "sub", "a": c, "b": b},
            "b": a,
        }
        flipped = {
            "op": "if",
            "condition": {
                "op": "eq",
                "a": relation,
                "b": {"op": "const", "value": "lt"},
            },
            "then": {"op": "const", "value": "gt"},
            "else": {
                "op": "if",
                "condition": {
                    "op": "eq",
                    "a": relation,
                    "b": {"op": "const", "value": "le"},
                },
                "then": {"op": "const", "value": "ge"},
                "else": {
                    "op": "if",
                    "condition": {
                        "op": "eq",
                        "a": relation,
                        "b": {"op": "const", "value": "gt"},
                    },
                    "then": {"op": "const", "value": "lt"},
                    "else": {"op": "const", "value": "le"},
                },
            },
        }
        return {
            "op": "dict",
            "entries": {
                "relation": {
                    "op": "if",
                    "condition": {
                        "op": "lt",
                        "a": a,
                        "b": {"op": "const", "value": 0},
                    },
                    "then": flipped,
                    "else": relation,
                },
                "bound": bound,
            },
        }
    if op == "det2":
        if len(expr) != 2:
            raise StudyError("compact det2 expression is invalid")
        matrix = _expand_compact_expr(expr[1])

        def cell(row: int, column: int) -> dict[str, Any]:
            return {
                "op": "get",
                "value": {
                    "op": "get",
                    "value": matrix,
                    "index": row,
                },
                "index": column,
            }

        return {
            "op": "sub",
            "a": {"op": "mul", "args": [cell(0, 0), cell(1, 1)]},
            "b": {"op": "mul", "args": [cell(0, 1), cell(1, 0)]},
        }
    if op == "square":
        if len(expr) != 2:
            raise StudyError("compact square expression is invalid")
        value = _expand_compact_expr(expr[1])
        return {"op": "pow", "a": value, "b": {"op": "const", "value": 2}}
    if op == "binomial-square":
        if len(expr) != 2:
            raise StudyError("compact binomial-square expression is invalid")
        value = _expand_compact_expr(expr[1])
        return {
            "op": "list",
            "items": [
                {"op": "pow", "a": value, "b": {"op": "const", "value": 2}},
                {
                    "op": "mul",
                    "args": [{"op": "const", "value": 2}, value],
                },
                {"op": "const", "value": 1},
            ],
        }
    if op == "quadratic":
        if len(expr) != 4:
            raise StudyError("compact quadratic expression is invalid")
        a, b, c = (_expand_compact_expr(item) for item in expr[1:])
        discriminant = {
            "op": "sub",
            "a": {"op": "pow", "a": b, "b": {"op": "const", "value": 2}},
            "b": {
                "op": "mul",
                "args": [
                    {"op": "const", "value": 4},
                    {"op": "mul", "args": [a, c]},
                ],
            },
        }
        root = {"op": "sqrt_exact", "value": discriminant}
        denominator = {
            "op": "mul",
            "args": [{"op": "const", "value": 2}, a],
        }
        negative_b = {"op": "neg", "value": b}
        return {
            "op": "list",
            "items": [
                {
                    "op": "div",
                    "a": {"op": "sub", "a": negative_b, "b": root},
                    "b": denominator,
                },
                {
                    "op": "div",
                    "a": {"op": "add", "args": [negative_b, root]},
                    "b": denominator,
                },
            ],
        }
    if op in {"rational-function", "rational_fn"}:
        if len(expr) != 4:
            raise StudyError("compact rational-function expression is invalid")
        left, right, shift = (_expand_compact_expr(item) for item in expr[1:])
        denominator = {
            "op": "list",
            "items": [shift, {"op": "const", "value": 1}],
        }
        return {
            "op": "dict",
            "entries": {
                "numerator": {"op": "add", "args": [left, right]},
                "denominator": denominator,
            },
        }
    if op in {"affine-compose", "affine"}:
        if len(expr) != 3:
            raise StudyError("compact affine composition expression is invalid")
        left, right = (_expand_compact_expr(item) for item in expr[1:])
        def vector(index: int) -> dict[str, Any]:
            return {
                "op": "get",
                "value": left,
                "index": index,
            }

        def other(index: int) -> dict[str, Any]:
            return {
                "op": "get",
                "value": right,
                "index": index,
            }

        return {
            "op": "list",
            "items": [
                {
                    "op": "mul",
                    "args": [vector(0), other(0)],
                },
                {
                    "op": "add",
                    "args": [
                        {"op": "mul", "args": [vector(0), other(1)]},
                        vector(1),
                    ],
                },
            ],
        }
    if op == "fib":
        if len(expr) != 2:
            raise StudyError("compact fib expression is invalid")
        count = _expand_compact_expr(expr[1])
        initial = {
            "op": "list",
            "items": [{"op": "const", "value": 0}, {"op": "const", "value": 1}],
        }
        first = {
            "op": "get",
            "value": {"op": "var", "name": "pair"},
            "index": {"op": "const", "value": 0},
        }
        second = {
            "op": "get",
            "value": {"op": "var", "name": "pair"},
            "index": {"op": "const", "value": 1},
        }
        step = {
            "op": "list",
            "items": [
                second,
                {"op": "add", "args": [first, second]},
            ],
        }
        repeated = {
            "op": "repeat",
            "count": count,
            "initial": initial,
            "state": "pair",
            "index": "iteration",
            "body": step,
        }
        return {
            "op": "get",
            "value": repeated,
            "index": {"op": "const", "value": 0},
        }
    if op in {"sin", "sine", "sine-special"}:
        if len(expr) != 2:
            raise StudyError("compact special-sine expression is invalid")
        degrees = _expand_compact_expr(expr[1])
        result: dict[str, Any] = {"op": "const", "value": "support-gap"}
        for angle, value in reversed(((0, "0"), (30, "1/2"), (90, "1"), (150, "1/2"), (270, "-1"), (330, "-1/2"))):
            branch = {"op": "const", "value": value}
            result = {
                "op": "if",
                "condition": {
                    "op": "eq",
                    "a": degrees,
                    "b": {"op": "const", "value": angle},
                },
                "then": branch,
                "else": result,
            }
        return result
    if op == "complex-mul":
        if len(expr) != 3:
            raise StudyError("compact complex multiplication expression is invalid")
        left, right = (_expand_compact_expr(item) for item in expr[1:])

        def component(value: dict[str, Any], index: int) -> dict[str, Any]:
            return {"op": "get", "value": value, "index": {"op": "const", "value": index}}

        ar, ai = component(left, 0), component(left, 1)
        br, bi = component(right, 0), component(right, 1)
        return {
            "op": "list",
            "items": [
                {"op": "sub", "a": {"op": "mul", "args": [ar, br]}, "b": {"op": "mul", "args": [ai, bi]}},
                {"op": "add", "args": [{"op": "mul", "args": [ar, bi]}, {"op": "mul", "args": [ai, br]}]},
            ],
        }
    if op == "derivative":
        if len(expr) != 2:
            raise StudyError("compact derivative expression is invalid")
        coefficients = _expand_compact_expr(expr[1])
        return {
            "op": "map",
            "items": {
                "op": "range",
                "start": {"op": "const", "value": 1},
                "stop": {"op": "len", "value": coefficients},
                "step": {"op": "const", "value": 1},
            },
            "item": "coefficient_index",
            "body": {
                "op": "mul",
                "args": [
                    {"op": "var", "name": "coefficient_index"},
                    {
                        "op": "get",
                        "value": coefficients,
                        "index": {"op": "var", "name": "coefficient_index"},
                    },
                ],
            },
        }
    if op == "integral":
        if len(expr) != 2:
            raise StudyError("compact integral expression is invalid")
        coefficients = _expand_compact_expr(expr[1])
        return {
            "op": "fold",
            "items": {
                "op": "range",
                "start": {"op": "const", "value": 0},
                "stop": {"op": "len", "value": coefficients},
                "step": {"op": "const", "value": 1},
            },
            "initial": {"op": "const", "value": 0},
            "item": "coefficient_index",
            "acc": "total",
            "body": {
                "op": "add",
                "args": [
                    {"op": "var", "name": "total"},
                    {
                        "op": "div",
                        "a": {
                            "op": "get",
                            "value": coefficients,
                            "index": {"op": "var", "name": "coefficient_index"},
                        },
                        "b": {
                            "op": "add",
                            "args": [
                                {"op": "var", "name": "index"},
                                {"op": "const", "value": 1},
                            ],
                        },
                    },
                ],
            },
        }

    if op == "distance":
        if len(expr) != 5:
            raise StudyError("compact distance expression is invalid")
        x1, y1, x2, y2 = (_expand_compact_expr(item) for item in expr[1:])
        dx = {"op": "sub", "a": x2, "b": x1}
        dy = {"op": "sub", "a": y2, "b": y1}
        return {
            "op": "sqrt_exact",
            "value": {
                "op": "add",
                "args": [
                    {"op": "pow", "a": dx, "b": {"op": "const", "value": 2}},
                    {"op": "pow", "a": dy, "b": {"op": "const", "value": 2}},
                ],
            },
        }
    if op in {"choose", "binomial-coefficient"}:
        if len(expr) != 3:
            raise StudyError("compact choose expression is invalid")
        n, k = (_expand_compact_expr(item) for item in expr[1:])
        effective_k = {
            "op": "min",
            "args": [k, {"op": "sub", "a": n, "b": k}],
        }
        result = {
            "op": "repeat",
            "count": effective_k,
            "initial": {"op": "const", "value": 1},
            "state": "coefficient",
            "index": "iteration",
            "body": {
                "op": "div",
                "a": {
                    "op": "mul",
                    "args": [
                        {"op": "var", "name": "coefficient"},
                        {
                            "op": "sub",
                            "a": n,
                            "b": {"op": "var", "name": "iteration"},
                        },
                    ],
                },
                "b": {
                    "op": "add",
                    "args": [
                        {"op": "var", "name": "iteration"},
                        {"op": "const", "value": 1},
                    ],
                },
            },
        }
        return result
    if op == "binomial-probability":
        if len(expr) != 3:
            raise StudyError("compact binomial-probability expression is invalid")
        n, k = (_expand_compact_expr(item) for item in expr[1:])
        return {
            "op": "div",
            "a": {
                "op": "repeat",
                "count": {
                    "op": "min",
                    "args": [k, {"op": "sub", "a": n, "b": k}],
                },
                "initial": {"op": "const", "value": 1},
                "state": "coefficient",
                "index": "iteration",
                "body": {
                    "op": "div",
                    "a": {
                        "op": "mul",
                        "args": [
                            {"op": "var", "name": "coefficient"},
                            {
                                "op": "sub",
                                "a": n,
                                "b": {"op": "var", "name": "iteration"},
                            },
                        ],
                    },
                    "b": {
                        "op": "add",
                        "args": [
                            {"op": "var", "name": "iteration"},
                            {"op": "const", "value": 1},
                        ],
                    },
                },
            },
            "b": {
                "op": "pow",
                "a": {"op": "const", "value": 2},
                "b": n,
            },
        }
    if op == "shortest-path":
        if len(expr) != 4:
            raise StudyError("compact shortest-path expression is invalid")
        matrix, start, end = (_expand_compact_expr(item) for item in expr[1:])
        infinity = {"op": "const", "value": 1000000000}
        vertex_range = {
            "op": "range",
            "start": {"op": "const", "value": 0},
            "stop": {"op": "len", "value": matrix},
            "step": {"op": "const", "value": 1},
        }
        initial_distances = {
            "op": "map",
            "items": vertex_range,
            "item": "target",
            "body": {
                "op": "if",
                "condition": {
                    "op": "eq",
                    "a": {"op": "var", "name": "target"},
                    "b": start,
                },
                "then": {"op": "const", "value": 0},
                "else": infinity,
            },
        }
        source_range = {
            "op": "range",
            "start": {"op": "const", "value": 0},
            "stop": {"op": "len", "value": matrix},
            "step": {"op": "const", "value": 1},
        }

        def edge_weight() -> dict[str, Any]:
            return {
                "op": "get",
                "value": {
                    "op": "get",
                    "value": matrix,
                    "index": {"op": "var", "name": "index"},
                },
                "index": {"op": "var", "name": "target"},
            }

        def source_distance() -> dict[str, Any]:
            return {
                "op": "get",
                "value": {"op": "var", "name": "distance"},
                "index": {"op": "var", "name": "index"},
            }

        candidate = {
            "op": "if",
            "condition": {
                "op": "ge",
                "a": edge_weight(),
                "b": {"op": "const", "value": 0},
            },
            "then": {
                "op": "add",
                "args": [source_distance(), edge_weight()],
            },
            "else": infinity,
        }
        best_candidate = {
            "op": "fold",
            "items": source_range,
            "initial": infinity,
            "item": "source",
            "acc": "best",
            "body": {
                "op": "min",
                "args": [{"op": "var", "name": "best"}, candidate],
            },
        }
        next_distances = {
            "op": "map",
            "items": vertex_range,
            "item": "target",
            "body": {
                "op": "fold",
                "items": source_range,
                "initial": infinity,
                "item": "source",
                "acc": "best",
                "body": {
                    "op": "min",
                    "args": [
                        {"op": "var", "name": "best"},
                        {
                            "op": "if",
                            "condition": {
                                "op": "ge",
                                "a": edge_weight(),
                                "b": {"op": "const", "value": 0},
                            },
                            "then": {
                                "op": "add",
                                "args": [source_distance(), edge_weight()],
                            },
                            "else": infinity,
                        },
                    ],
                },
            },
        }
        del best_candidate
        return {
            "op": "get",
            "value": {
                "op": "repeat",
                "count": {
                    "op": "sub",
                    "a": {"op": "len", "value": matrix},
                    "b": {"op": "const", "value": 1},
                },
                "initial": initial_distances,
                "state": "distance",
                "index": "iteration",
                "body": next_distances,
            },
            "index": end,
        }
    if op == "multiplicative-order":
        if len(expr) != 3:
            raise StudyError("compact multiplicative-order expression is invalid")
        value, modulus = (_expand_compact_expr(item) for item in expr[1:])
        valid_orders = {
            "op": "filter",
            "items": {
                "op": "range",
                "start": {"op": "const", "value": 1},
                "stop": {"op": "add", "args": [modulus, {"op": "const", "value": 1}]},
                "step": {"op": "const", "value": 1},
            },
            "item": "order",
            "predicate": {
                "op": "eq",
                "a": {
                    "op": "mod",
                    "a": {
                        "op": "pow",
                        "a": value,
                        "b": {"op": "var", "name": "order"},
                    },
                    "b": modulus,
                },
                "b": {"op": "const", "value": 1},
            },
        }
        return {
            "op": "let",
            "bindings": {"valid_orders": valid_orders},
            "body": {
                "op": "if",
                "condition": {
                    "op": "eq",
                    "a": {
                        "op": "len",
                        "value": {"op": "var", "name": "valid_orders"},
                    },
                    "b": {"op": "const", "value": 0},
                },
                "then": {"op": "const", "value": "support-gap"},
                "else": {
                    "op": "get",
                    "value": {"op": "var", "name": "valid_orders"},
                    "index": {"op": "const", "value": 0},
                },
            },
        }
    if op == "gcd-mod":
        if len(expr) != 4:
            raise StudyError("compact gcd-mod expression is invalid")
        operator, a, b = (_expand_compact_expr(item) for item in expr[1:])
        initial = {
            "op": "list",
            "items": [
                {"op": "abs", "value": a},
                {"op": "abs", "value": b},
            ],
        }
        first = {
            "op": "get",
            "value": {"op": "var", "name": "pair"},
            "index": {"op": "const", "value": 0},
        }
        second = {
            "op": "get",
            "value": {"op": "var", "name": "pair"},
            "index": {"op": "const", "value": 1},
        }
        euclid = {
            "op": "repeat",
            "count": {"op": "const", "value": 64},
            "initial": initial,
            "state": "pair",
            "index": "iteration",
            "body": {
                "op": "if",
                "condition": {
                    "op": "eq",
                    "a": second,
                    "b": {"op": "const", "value": 0},
                },
                "then": {"op": "var", "name": "pair"},
                "else": {
                    "op": "list",
                    "items": [
                        second,
                        {
                            "op": "mod",
                            "a": first,
                            "b": second,
                        },
                    ],
                },
            },
        }
        return {
            "op": "if",
            "condition": {
                "op": "eq",
                "a": operator,
                "b": {"op": "const", "value": "mod"},
            },
            "then": {"op": "mod", "a": a, "b": b},
            "else": {
                "op": "get",
                "value": euclid,
                "index": {"op": "const", "value": 0},
            },
        }
    if op == "primality":
        if len(expr) != 2:
            raise StudyError("compact primality expression is invalid")
        value = _expand_compact_expr(expr[1])
        divisors = {
            "op": "filter",
            "items": {
                "op": "range",
                "start": {"op": "const", "value": 2},
                "stop": {"op": "min", "args": [value, {"op": "const", "value": 513}]},
                "step": {"op": "const", "value": 1},
            },
            "item": "divisor",
            "predicate": {
                "op": "eq",
                "a": {
                    "op": "mod",
                    "a": value,
                    "b": {"op": "var", "name": "divisor"},
                },
                "b": {"op": "const", "value": 0},
            },
        }
        return {
            "op": "and",
            "args": [
                {"op": "ge", "a": value, "b": {"op": "const", "value": 2}},
                {
                    "op": "eq",
                    "a": {"op": "len", "value": divisors},
                    "b": {"op": "const", "value": 0},
                },
            ],
        }
    if op == "factorization":
        if len(expr) != 2:
            raise StudyError("compact factorization expression is invalid")
        value = _expand_compact_expr(expr[1])
        outer_divisor = {
            "op": "add",
            "args": [{"op": "var", "name": "iteration"}, {"op": "const", "value": 2}],
        }
        inner_remaining = {
            "op": "get",
            "value": {"op": "var", "name": "inner_state"},
            "index": {"op": "const", "value": 0},
        }
        inner_factors = {
            "op": "get",
            "value": {"op": "var", "name": "inner_state"},
            "index": {"op": "const", "value": 1},
        }
        divided_state = {
            "op": "list",
            "items": [
                {
                    "op": "div",
                    "a": inner_remaining,
                    "b": outer_divisor,
                },
                {
                    "op": "append",
                    "a": inner_factors,
                    "b": outer_divisor,
                },
            ],
        }
        inner = {
            "op": "repeat",
            "count": {"op": "const", "value": 16},
            "initial": {
                "op": "var",
                "name": "factor_state",
            },
            "state": "inner_state",
            "index": "inner_iteration",
            "body": {
                "op": "if",
                "condition": {
                    "op": "eq",
                    "a": {
                        "op": "mod",
                        "a": inner_remaining,
                        "b": outer_divisor,
                    },
                    "b": {"op": "const", "value": 0},
                },
                "then": divided_state,
                "else": {"op": "var", "name": "inner_state"},
            },
        }
        factored = {
            "op": "repeat",
            "count": {"op": "const", "value": 64},
            "initial": {
                "op": "list",
                "items": [
                    value,
                    {"op": "list", "items": []},
                ],
            },
            "state": "factor_state",
            "index": "iteration",
            "body": inner,
        }
        remaining = {
            "op": "get",
            "value": factored,
            "index": {"op": "const", "value": 0},
        }
        factors = {
            "op": "get",
            "value": factored,
            "index": {"op": "const", "value": 1},
        }
        return {
            "op": "if",
            "condition": {
                "op": "gt",
                "a": remaining,
                "b": {"op": "const", "value": 1},
            },
            "then": {"op": "append", "a": factors, "b": remaining},
            "else": factors,
        }
    if op == "prime-generation":
        if len(expr) != 2:
            raise StudyError("compact prime-generation expression is invalid")
        limit = _expand_compact_expr(expr[1])
        odd_primes = {
            "op": "filter",
            "items": {
                "op": "range",
                "start": {"op": "const", "value": 3},
                "stop": {"op": "add", "args": [limit, {"op": "const", "value": 1}]},
                "step": {"op": "const", "value": 2},
            },
            "item": "candidate",
            "predicate": {
                "op": "eq",
                "a": {
                    "op": "len",
                    "value": {
                        "op": "filter",
                        "items": {
                            "op": "range",
                            "start": {"op": "const", "value": 3},
                            "stop": {
                                "op": "min",
                                "args": [
                                    {"op": "var", "name": "candidate"},
                                    {"op": "const", "value": 33},
                                ],
                            },
                            "step": {"op": "const", "value": 2},
                        },
                        "item": "divisor",
                        "predicate": {
                            "op": "eq",
                            "a": {
                                "op": "mod",
                                "a": {"op": "var", "name": "candidate"},
                                "b": {"op": "var", "name": "divisor"},
                            },
                            "b": {"op": "const", "value": 0},
                        },
                    },
                },
                "b": {"op": "const", "value": 0},
            },
        }
        return {
            "op": "fold",
            "items": odd_primes,
            "initial": {"op": "list", "items": [{"op": "const", "value": 2}]},
            "item": "prime",
            "acc": "primes",
            "body": {
                "op": "append",
                "a": {"op": "var", "name": "primes"},
                "b": {"op": "var", "name": "prime"},
            },
        }
    if op == "if":
        if len(expr) != 4:
            raise StudyError("compact if expression is invalid")
        return {
            "op": "if",
            "condition": _expand_compact_expr(expr[1]),
            "then": _expand_compact_expr(expr[2]),
            "else": _expand_compact_expr(expr[3]),
        }
    if op == "switch":
        if len(expr) != 3 or not isinstance(expr[2], Mapping) or not expr[2]:
            raise StudyError("compact switch expression is invalid")
        selector = _expand_compact_expr(expr[1])
        cases = list(expr[2].items())
        default = None
        if cases and cases[-1][0] == "default":
            _default_name, default_expr = cases.pop()
            default = _expand_compact_expr(default_expr)
        elif not cases:
            raise StudyError("compact switch has no cases")
        if default is None:
            _last_name, last_expr = cases.pop()
            default = _expand_compact_expr(last_expr)
        result = default
        for label, branch in reversed(cases):
            result = {
                "op": "if",
                "condition": {
                    "op": "eq",
                    "a": selector,
                    "b": {"op": "const", "value": label},
                },
                "then": _expand_compact_expr(branch),
                "else": result,
            }
        return result
    if op == "list":
        return {"op": "list", "items": [_expand_compact_expr(item) for item in expr[1:]]}
    if op in {"add", "mul", "and", "or", "concat", "min", "max"}:
        return {"op": op, "args": [_expand_compact_expr(item) for item in expr[1:]]}
    if op in {
        "sub",
        "div",
        "floordiv",
        "mod",
        "pow",
        "eq",
        "ne",
        "lt",
        "le",
        "gt",
        "ge",
        "append",
    }:
        if len(expr) != 3:
            raise StudyError(f"compact binary expression {op!r} is invalid")
        return {
            "op": op,
            "a": _expand_compact_expr(expr[1]),
            "b": _expand_compact_expr(expr[2]),
        }
    if op in {"neg", "not", "abs", "sqrt_exact", "len", "sort", "unique", "reverse", "floor", "ceil"}:
        if len(expr) != 2:
            raise StudyError(f"compact unary expression {op!r} is invalid")
        return {"op": op, "value": _expand_compact_expr(expr[1])}
    if op == "get":
        if len(expr) != 3:
            raise StudyError("compact get expression is invalid")
        return {
            "op": "get",
            "value": _expand_compact_expr(expr[1]),
            "index": _expand_compact_expr(expr[2]),
        }
    raise StudyError(f"unsupported compact program operation: {op!r}")


def _expand_compact_program(program: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(program.get("body"), list):
        return {**program, "body": _expand_compact_expr(program["body"])}
    return dict(program)


def parse_teacher_program(
    content: str, *, params: Sequence[str] | None = None
) -> dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
        raise StudyError("teacher returned no program")
    decoder = json.JSONDecoder()
    starts = [index for index, character in enumerate(content) if character == "{"]
    for start in starts:
        try:
            value, _end = decoder.raw_decode(content[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, Mapping) and isinstance(value.get("program"), Mapping):
            return canonical_program(_expand_compact_program(value["program"]))
        if (
            params is not None
            and isinstance(value, Mapping)
            and isinstance(value.get("op"), str)
        ):
            return canonical_program(
                {"schema": PROGRAM_SCHEMA, "params": list(params), "body": value}
            )
    raise StudyError("teacher response contained no valid program object")


def _evaluate_cases(program: Mapping[str, Any], cases: Sequence[CourseCase]) -> dict[str, Any]:
    rows = []
    for case in cases:
        try:
            actual, steps = execute_program(program, case.arguments)
            error = None
        except Exception as exc:  # noqa: BLE001 - every candidate failure is a study observation
            actual, steps = None, 0
            error = {"type": type(exc).__name__, "message": str(exc)}
        passed = error is None and actual == case.expected
        rows.append(
            {
                "case_id": case.case_id,
                "arguments_sha256": digest_value(case.arguments),
                "expected_sha256": digest_value(case.expected),
                "actual": actual,
                "actual_sha256": None if error else digest_value(actual),
                "vm_steps": steps,
                "passed": passed,
                "error": error,
            }
        )
    return {"passed": all(row["passed"] for row in rows), "cases": rows}

def _failure_feedback(
    cases: Sequence[CourseCase], result: Mapping[str, Any]
) -> list[dict[str, Any]]:
    expected = {case.case_id: case.expected for case in cases}
    return [
        {**row, "expected": expected[row["case_id"]]}
        for row in result.get("cases", [])
        if not row.get("passed")
    ]


def _timestamp(sequence: int) -> str:
    moment = datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=sequence)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class AutonomousMathStudy:
    """Complete-course controller; learned content and policy persist only in the field."""

    def __init__(
        self,
        data_home: Path,
        audit_path: Path,
        *,
        teacher: Teacher | None,
        profile_overrides: Mapping[str, int] | None = None,
    ) -> None:
        self.data_home = Path(data_home)
        self.audit_path = Path(audit_path)
        self.teacher = teacher
        self.profile_overrides = dict(DEFAULT_PROFILE_OVERRIDES if profile_overrides is None else profile_overrides)
        self.audit = self._load_audit()

    def _load_audit(self) -> dict[str, Any]:
        if self.audit_path.is_file():
            value = json.loads(self.audit_path.read_text(encoding="utf-8"))
            if value.get("schema") != AUDIT_SCHEMA or value.get("course_sha256") != course_manifest()["content_sha256"]:
                raise StudyError("audit state is incompatible with the current course")
            value.setdefault("recalls", 0)
            return value
        value = {
            "schema": AUDIT_SCHEMA,
            "course_sha256": course_manifest()["content_sha256"],
            "sequence": 0,
            "recalls": 0,
            "teacher_calls": 0,
            "teacher_completion_tokens": 0,
            "vm_steps": 0,
            "events": [],
        }
        atomic_json(self.audit_path, value)
        return value

    def _commit_event(self, kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        self.audit["sequence"] += 1
        event = {
            "sequence": self.audit["sequence"],
            "kind": kind,
            "payload": dict(payload),
        }
        event["sha256"] = digest_value(event)
        self.audit["events"].append(event)
        atomic_json(self.audit_path, self.audit)
        return event

    def _memory(self) -> CassiFieldWorkMemory:
        return CassiFieldWorkMemory(self.data_home, profile_overrides=self.profile_overrides)

    def _learn_record(
        self,
        *,
        source_id: str,
        context: Mapping[str, Any],
        payload: Mapping[str, Any],
        labels: Sequence[str],
    ) -> Mapping[str, Any]:
        sequence = int(self.audit["sequence"]) + 1
        with self._memory() as memory:
            return memory.learn(
                WorkMemoryRecord(
                    source_id=source_id,
                    context=context,
                    payload=payload,
                    observed_timestamp=_timestamp(sequence),
                    labels=tuple(labels),
                )
            )

    def _recall_payload(self, context: Mapping[str, Any], label: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        self.audit["recalls"] = int(self.audit.get("recalls", 0)) + 1
        atomic_json(self.audit_path, self.audit)
        operation_label = f"{label}:{self.audit['recalls']}"
        with self._memory() as memory:
            receipt = memory.recall(context, operation_label=operation_label)
            rows = receipt.get("records", [])
            if len(rows) != 1:
                raise StudyError(f"field recall expected one active record, received {len(rows)}")
            payload = rows[0].get("payload")
            if not isinstance(payload, Mapping):
                raise StudyError("field record payload is unavailable")
            return payload, receipt

    def ensure_method(self) -> Mapping[str, Any]:
        context = {
            "course": COURSE_ID,
            "kind": "study-method",
            "method_sha256": digest_value(dict(DEFAULT_METHOD)),
        }
        try:
            payload, _ = self._recall_payload(context, "math-study-method")
            return payload["method"]
        except StudyError as exc:
            if "received 0" not in str(exc):
                raise
        receipt = self._learn_record(
            source_id="autonomous-math:study-method",
            context=context,
            payload={"method": dict(DEFAULT_METHOD), "status": "supplied-baseline"},
            labels=("autonomous-math", "study-method", "supplied-baseline"),
        )
        self._commit_event("method-installed", {"field_state_sha256": receipt["state_sha256"]})
        return dict(DEFAULT_METHOD)

    def promoted_program_sha256(self, unit_id: str) -> str | None:
        if unit_id not in COURSE_BY_ID:
            raise StudyError(f"unknown course unit: {unit_id}")
        try:
            status, _ = self._recall_payload(
                {"course": COURSE_ID, "kind": "promotion", "unit": unit_id},
                f"math-resume-status-{unit_id}",
            )
        except StudyError as exc:
            if "received 0" in str(exc):
                return None
            raise
        if status.get("status") != "promoted":
            return None
        capability, _ = self._recall_payload(
            {"course": COURSE_ID, "kind": "capability", "unit": unit_id},
            f"math-resume-capability-{unit_id}",
        )
        program = canonical_program(capability.get("program"))
        program_sha256 = digest_value(program)
        if status.get("program_sha256") != program_sha256:
            raise StudyError(f"promoted program digest mismatch for {unit_id}")
        return program_sha256
    def study_unit(self, unit_id: str) -> dict[str, Any]:
        if unit_id not in COURSE_BY_ID:
            raise StudyError(f"unknown course unit: {unit_id}")
        if self.teacher is None:
            raise StudyError("study requires an explicitly configured offline teacher")
        unit = COURSE_BY_ID[unit_id]
        method = self.ensure_method()
        failures: list[Mapping[str, Any]] = []
        qwen_results: list[Mapping[str, Any]] = []
        study_calls_before = int(self.audit["teacher_calls"])
        compact_teacher = (
            isinstance(self.teacher, LocalQwenClient)
            and "IQ1" in self.teacher.model_path.name.upper()
        )
        teacher_max_tokens = min(int(method["teacher_max_tokens"]), 2048) if compact_teacher else int(method["teacher_max_tokens"])

        for attempt in range(int(method["max_attempts"])):
            prompt = teacher_prompt(
                unit, method, attempt, failures, compact=compact_teacher
            )
            before_calls = int(self.audit["teacher_calls"])
            teacher_request: dict[str, Any] = {
                "prompt": prompt,
                "max_tokens": teacher_max_tokens,
                "thinking": bool(method["thinking"]),
            }
            result = self.teacher.complete(**teacher_request)
            self.audit["teacher_calls"] = before_calls + 1
            usage = result.get("usage", {})
            completion_tokens = int(usage.get("completion_tokens", 0)) if isinstance(usage, Mapping) else 0
            self.audit["teacher_completion_tokens"] += completion_tokens
            content = str(result.get("content", ""))
            reasoning_content = str(result.get("reasoning_content", ""))
            lesson_payload = {
                "unit_id": unit_id,
                "attempt": attempt,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "response": content,
                "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "reasoning_content": reasoning_content,
                "generation_parameters": result.get("generation_parameters"),
                "usage": usage,
                "teacher_role": "offline-proposal-source",
            }
            lesson_receipt = self._learn_record(
                source_id=f"autonomous-math:teacher:{unit_id}:attempt-{attempt}",
                context={"course": COURSE_ID, "kind": "teacher-lesson", "unit": unit_id, "attempt": attempt},
                payload=lesson_payload,
                labels=("autonomous-math", "teacher-evidence", unit_id),
            )
            parse_source = "content"
            try:
                try:
                    program = parse_teacher_program(content, params=unit.parameters)
                except Exception:
                    if not reasoning_content.strip():
                        raise
                    parse_source = "reasoning_content"
                    program = parse_teacher_program(reasoning_content, params=unit.parameters)
                if tuple(program["params"]) != unit.parameters:
                    raise StudyError("teacher program parameter order differs from the unit contract")
                training = _evaluate_cases(program, unit.training)
                practice = _evaluate_cases(program, unit.practice)
                self.audit["vm_steps"] += sum(row["vm_steps"] for row in (*training["cases"], *practice["cases"]))
                accepted = bool(training["passed"] and practice["passed"])
                failure = None
            except Exception as exc:  # noqa: BLE001 - teacher proposals are untrusted evidence
                program = None
                training = {"passed": False, "cases": []}
                practice = {"passed": False, "cases": []}
                accepted = False
                failure = {"type": type(exc).__name__, "message": str(exc)}
            attempt_row = {
                "attempt": attempt,
                "accepted_for_examination": accepted,
                "parse_source": parse_source,
                "lesson_source_revision_id": lesson_receipt["source_revision_id"],
                "program_sha256": None if program is None else digest_value(program),
                "training": training,
                "practice": practice,
                "failure": failure,
            }
            qwen_results.append(attempt_row)
            self._commit_event("study-attempt", {"unit_id": unit_id, **attempt_row})
            if accepted and program is not None:
                capability_receipt = self._learn_record(
                    source_id=f"autonomous-math:capability:{unit_id}",
                    context={"course": COURSE_ID, "kind": "capability", "unit": unit_id},
                    payload={
                        "unit_id": unit_id,
                        "status": "candidate",
                        "program": program,
                        "program_sha256": digest_value(program),

                        "teacher_source_revision_id": lesson_receipt["source_revision_id"],
                        "training_summary_sha256": digest_value(training),
                        "practice_summary_sha256": digest_value(practice),
                    },
                    labels=("autonomous-math", "field-owned-candidate", unit_id),
                )
                event = self._commit_event(
                    "candidate-admitted",
                    {
                        "unit_id": unit_id,
                        "program_sha256": digest_value(program),
                        "field_state_sha256": capability_receipt["state_sha256"],
                    },
                )
                return {
                    "status": "candidate-ready",
                    "unit_id": unit_id,
                    "attempts": qwen_results,
                    "candidate_event": event,
                    "teacher_calls": int(self.audit["teacher_calls"]) - study_calls_before,
                }
            failures.append(
                {
                    "attempt": attempt,
                    "failure": failure,
                    "training_failures": _failure_feedback(unit.training, training),
                    "practice_failures": _failure_feedback(unit.practice, practice),
                }
            )
        return {"status": "study-budget-exhausted", "unit_id": unit_id, "attempts": qwen_results}

    def examine_unit(self, unit_id: str) -> dict[str, Any]:
        unit = COURSE_BY_ID[unit_id]
        calls_before = int(self.audit["teacher_calls"])
        payload, recall = self._recall_payload(
            {"course": COURSE_ID, "kind": "capability", "unit": unit_id},
            f"math-exam:{unit_id}",
        )
        if payload.get("status") not in {"candidate", "promoted"}:
            raise StudyError("field capability is not eligible for examination")
        program = canonical_program(payload.get("program"))
        examination = _evaluate_cases(program, unit.examinations)
        self.audit["vm_steps"] += sum(row["vm_steps"] for row in examination["cases"])
        if int(self.audit["teacher_calls"]) != calls_before:
            raise StudyError("teacher was called during protected examination")
        result = {
            "unit_id": unit_id,
            "status": "passed" if examination["passed"] else "failed",
            "teacher_disconnected": True,
            "teacher_calls_during_examination": 0,
            "program_sha256": digest_value(program),
            "field_selected_source_revision_ids": recall["selected_source_revision_ids"],
            "examination": examination,
        }
        self._commit_event("protected-examination", result)
        if not examination["passed"]:
            return result
        promotion = self._learn_record(
            source_id=f"autonomous-math:promotion:{unit_id}",
            context={"course": COURSE_ID, "kind": "promotion", "unit": unit_id},
            payload={
                "unit_id": unit_id,
                "status": "promoted",
                "program_sha256": digest_value(program),
                "examination_sha256": digest_value(examination),
                "teacher_disconnected": True,
            },
            labels=("autonomous-math", "independently-verified-promotion", unit_id),
        )
        result["promotion_field_state_sha256"] = promotion["state_sha256"]
        return result

    def promoted_units(self) -> tuple[str, ...]:
        promoted = []
        for unit in COURSE:
            try:
                payload, _ = self._recall_payload(
                    {"course": COURSE_ID, "kind": "promotion", "unit": unit.unit_id},
                    f"promotion-status:{unit.unit_id}",
                )
            except StudyError as exc:
                if "received 0" in str(exc):
                    continue
                raise
            if payload.get("status") == "promoted":
                promoted.append(unit.unit_id)
        return tuple(promoted)

    def regression(self) -> dict[str, Any]:
        calls_before = int(self.audit["teacher_calls"])
        rows = []
        for unit_id in self.promoted_units():
            unit = COURSE_BY_ID[unit_id]
            payload, _ = self._recall_payload(
                {"course": COURSE_ID, "kind": "capability", "unit": unit_id},
                f"math-regression:{unit_id}",
            )
            result = _evaluate_cases(canonical_program(payload["program"]), unit.examinations)
            rows.append({"unit_id": unit_id, **result})
        passed = all(row["passed"] for row in rows)
        if int(self.audit["teacher_calls"]) != calls_before:
            raise StudyError("teacher was called during regression")
        receipt = {"status": "passed" if passed else "failed", "teacher_disconnected": True, "units": rows}
        self._commit_event("regression", receipt)
        return receipt

    def run_unit(self, unit_id: str) -> dict[str, Any]:
        study = self.study_unit(unit_id)
        if study["status"] != "candidate-ready":
            return self.receipt(unit_id, study=study, examination=None, regression=None)
        examination = self.examine_unit(unit_id)
        regression = self.regression() if examination["status"] == "passed" else None
        return self.receipt(unit_id, study=study, examination=examination, regression=regression)

    def receipt(
        self,
        unit_id: str,
        *,
        study: Mapping[str, Any] | None,
        examination: Mapping[str, Any] | None,
        regression: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        with self._memory() as memory:
            field = memory.state_receipt()
        ready = bool(
            examination
            and examination.get("status") == "passed"
            and regression
            and regression.get("status") == "passed"
        )
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "course": course_manifest(),
            "commissioned_unit": unit_id,
            "study": study,
            "protected_examination": examination,
            "regression": regression,
            "ready_to_continue": ready,
            "resource_accounting": {
                "teacher_calls": self.audit["teacher_calls"],
                "teacher_completion_tokens": self.audit["teacher_completion_tokens"],
                "vm_steps": self.audit["vm_steps"],
            },
            "ownership": {
                "sole_adaptive_persistent_object": "QiFieldState.field",
                "field_state_sha256": field["state_sha256"],
                "field_generation": field["generation"],
                "teacher_role": "offline proposal source",
                "qwen_in_live_answer_path": False,
                "teacher_calls_during_protected_examination": 0 if examination else None,
                "native_qwen_displacement_bytes": 0,
                "host_audit_state": "non-adaptive cursors, budgets, and immutable receipts only",
            },
            "implementation": {
                "controller_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "cassifi": dict(cassifi_source_identity()),
            },
        }
        receipt["content_sha256"] = digest_value(receipt)
        return receipt

    def matched_method_comparison_plan(
        self, *, candidate_method: Mapping[str, Any], evaluation_units: Sequence[str]
    ) -> dict[str, Any]:
        """Freeze a complete equal-budget M(g+1)-versus-M(g) comparison plan."""
        current = self.ensure_method()
        candidate = dict(candidate_method)
        if candidate.get("schema") != METHOD_SCHEMA or int(candidate.get("generation", -1)) != int(current["generation"]) + 1:
            raise StudyError("candidate method must be the immediate next generation")
        if any(unit_id not in COURSE_BY_ID for unit_id in evaluation_units):
            raise StudyError("method comparison names an unknown unit")
        budget = {
            "max_attempts_per_unit": min(int(current["max_attempts"]), int(candidate["max_attempts"])),
            "teacher_max_tokens_per_call": min(int(current["teacher_max_tokens"]), int(candidate["teacher_max_tokens"])),
            "same_starting_field_checkpoint": True,
            "same_teacher_identity": True,
            "same_development_and_protected_cases": True,
        }
        plan = {
            "schema": "cassi.autonomous-math.method-comparison.v1",
            "incumbent": current,
            "candidate": candidate,
            "evaluation_units": list(evaluation_units),
            "matched_budget": budget,
            "promotion_order": ["more_units_promoted", "fewer_teacher_calls", "fewer_completion_tokens", "fewer_vm_steps"],
            "regression_required": True,
        }
        plan["sha256"] = digest_value(plan)
        return plan


def clone_field_checkpoint(source: Path, destination: Path) -> None:
    """Create an isolated exact lineage for a matched method comparison."""
    source = Path(source)
    destination = Path(destination)
    if destination.exists():
        raise StudyError("method comparison destination already exists")
    shutil.copytree(source, destination)
