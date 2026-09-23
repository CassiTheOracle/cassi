"""Bounded Python-subset interpreter and self-optimization laboratory.

CassiPy deliberately treats Python as an object language.  Source is parsed into
an immutable, JSON-shaped AST, executed by a small bounded interpreter, and
optimized only after an independent behavior comparison.  The accepted subset
contains no imports, attributes, I/O, subprocesses, reflection, or arbitrary
``eval``/``exec`` paths.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


PROGRAM_SCHEMA = "cassi.python.program.v1"
RECEIPT_SCHEMA = "cassi.python.apprenticeship-receipt.v1"
MAX_NODES = 512
MAX_DEPTH = 32
MAX_STEPS = 50_000
MAX_CALL_DEPTH = 32
MAX_SEQUENCE = 2_048
MAX_STRING = 8_192
MAX_INTEGER_ABS = 10**18


class CassiPyError(RuntimeError):
    """Base class for parse, execution, budget, and verification failures."""


class CassiPySyntaxError(CassiPyError):
    """The source uses syntax outside the bounded CassiPy subset."""


class CassiPyRuntimeError(CassiPyError):
    """The program requests an unsupported or invalid runtime operation."""


class CassiPyBudgetError(CassiPyRuntimeError):
    """The program exceeded an explicit execution or value budget."""


_MISSING = object()
_BINOPS = {
    ast.Add: "add",
    ast.Sub: "sub",
    ast.Mult: "mul",
    ast.Div: "div",
    ast.FloorDiv: "floordiv",
    ast.Mod: "mod",
    ast.Pow: "pow",
}
_UNARYOPS = {ast.UAdd: "pos", ast.USub: "neg", ast.Not: "not"}
_CMPOPS = {
    ast.Eq: "eq",
    ast.NotEq: "ne",
    ast.Lt: "lt",
    ast.LtE: "le",
    ast.Gt: "gt",
    ast.GtE: "ge",
}
_SAFE_BUILTINS = frozenset({"range", "len", "sum", "min", "max", "abs", "int", "bool"})


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def content_digest_matches(value: Mapping[str, Any]) -> bool:
    body = dict(value)
    stated = body.pop("content_sha256", None)
    return isinstance(stated, str) and digest_value(body) == stated


def _check_identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.isidentifier() or value.startswith("__"):
        raise CassiPySyntaxError(f"{label} must be a public Python identifier")
    return value


def _bounded(value: Any, *, depth: int = 0) -> Any:
    if depth > MAX_DEPTH:
        raise CassiPyBudgetError("value nesting exceeds CassiPy depth budget")
    if value is None or isinstance(value, (bool, str, int, float)):
        if isinstance(value, str) and len(value) > MAX_STRING:
            raise CassiPyBudgetError("string exceeds CassiPy budget")
        if isinstance(value, int) and abs(value) > MAX_INTEGER_ABS:
            raise CassiPyBudgetError("integer exceeds CassiPy budget")
        if isinstance(value, float) and (not math.isfinite(value) or abs(value) > MAX_INTEGER_ABS):
            raise CassiPyBudgetError("float exceeds CassiPy budget")
        return value
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_SEQUENCE:
            raise CassiPyBudgetError("sequence exceeds CassiPy budget")
        bounded = [_bounded(item, depth=depth + 1) for item in value]
        return type(value)(bounded)
    if isinstance(value, dict):
        if len(value) > MAX_SEQUENCE:
            raise CassiPyBudgetError("mapping exceeds CassiPy budget")
        return {
            _bounded(key, depth=depth + 1): _bounded(item, depth=depth + 1)
            for key, item in value.items()
        }
    raise CassiPyRuntimeError(f"value type is outside CassiPy: {type(value).__name__}")


class _Canonicalizer:
    def __init__(self, *, params: Sequence[str]) -> None:
        self.params = tuple(_check_identifier(name, "parameter") for name in params)
        if len(set(self.params)) != len(self.params):
            raise CassiPySyntaxError("parameters must be unique")
        self.nodes = 0

    def _enter(self, node: ast.AST, depth: int) -> None:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise CassiPyBudgetError("program exceeds CassiPy node budget")
        if depth > MAX_DEPTH:
            raise CassiPyBudgetError("program exceeds CassiPy depth budget")

    def convert(self, node: ast.AST, depth: int = 0) -> dict[str, Any] | list[Any]:
        self._enter(node, depth)
        if isinstance(node, ast.Module):
            return {"type": "module", "body": self._statements(node.body, depth + 1)}
        if isinstance(node, ast.Expr):
            return {"type": "expr", "value": self.convert(node.value, depth + 1)}
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                raise CassiPySyntaxError("multiple assignment targets are not supported")
            return {
                "type": "assign",
                "target": self.convert(node.targets[0], depth + 1),
                "value": self.convert(node.value, depth + 1),
            }
        if isinstance(node, ast.AugAssign):
            op = _BINOPS.get(type(node.op))
            if op is None:
                raise CassiPySyntaxError("augmented operator is not supported")
            return {
                "type": "augassign",
                "target": self.convert(node.target, depth + 1),
                "op": op,
                "value": self.convert(node.value, depth + 1),
            }
        if isinstance(node, ast.Return):
            return {
                "type": "return",
                "value": None if node.value is None else self.convert(node.value, depth + 1),
            }
        if isinstance(node, ast.If):
            return {
                "type": "if",
                "test": self.convert(node.test, depth + 1),
                "body": self._statements(node.body, depth + 1),
                "orelse": self._statements(node.orelse, depth + 1),
            }
        if isinstance(node, ast.For):
            return {
                "type": "for",
                "target": self.convert(node.target, depth + 1),
                "iter": self.convert(node.iter, depth + 1),
                "body": self._statements(node.body, depth + 1),
                "orelse": self._statements(node.orelse, depth + 1),
            }
        if isinstance(node, ast.While):
            raise CassiPySyntaxError("while is intentionally excluded; use bounded for")
        if isinstance(node, ast.FunctionDef):
            if node.decorator_list or node.returns is not None or node.type_comment:
                raise CassiPySyntaxError("decorators and annotations are not supported")
            if node.args.vararg or node.args.kwarg or node.args.kwonlyargs or node.args.defaults:
                raise CassiPySyntaxError("variadic and default function arguments are not supported")
            if node.args.posonlyargs:
                raise CassiPySyntaxError("positional-only function arguments are not supported")
            args = [_check_identifier(arg.arg, "function argument") for arg in node.args.args]
            if len(set(args)) != len(args):
                raise CassiPySyntaxError("function arguments must be unique")
            return {
                "type": "function",
                "name": _check_identifier(node.name, "function name"),
                "args": args,
                "body": self._statements(node.body, depth + 1),
            }
        if isinstance(node, (ast.Break, ast.Continue)):
            return {"type": "break" if isinstance(node, ast.Break) else "continue"}
        if isinstance(node, ast.Constant):
            if not (node.value is None or isinstance(node.value, (bool, int, float, str))):
                raise CassiPySyntaxError("constant type is not supported")
            return {"type": "constant", "value": _bounded(node.value)}
        if isinstance(node, ast.Name):
            return {"type": "name", "id": _check_identifier(node.id, "name")}
        if isinstance(node, ast.BinOp):
            op = _BINOPS.get(type(node.op))
            if op is None:
                raise CassiPySyntaxError("binary operator is not supported")
            return {
                "type": "binop",
                "op": op,
                "left": self.convert(node.left, depth + 1),
                "right": self.convert(node.right, depth + 1),
            }
        if isinstance(node, ast.UnaryOp):
            op = _UNARYOPS.get(type(node.op))
            if op is None:
                raise CassiPySyntaxError("unary operator is not supported")
            return {"type": "unary", "op": op, "value": self.convert(node.operand, depth + 1)}
        if isinstance(node, ast.BoolOp):
            op = "and" if isinstance(node.op, ast.And) else "or" if isinstance(node.op, ast.Or) else None
            if op is None or len(node.values) < 2:
                raise CassiPySyntaxError("Boolean operator is not supported")
            return {"type": "boolop", "op": op, "values": [self.convert(v, depth + 1) for v in node.values]}
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise CassiPySyntaxError("chained comparisons are not supported")
            op = _CMPOPS.get(type(node.ops[0]))
            if op is None:
                raise CassiPySyntaxError("comparison operator is not supported")
            return {
                "type": "compare",
                "op": op,
                "left": self.convert(node.left, depth + 1),
                "right": self.convert(node.comparators[0], depth + 1),
            }
        if isinstance(node, ast.IfExp):
            return {
                "type": "ifexp",
                "test": self.convert(node.test, depth + 1),
                "then": self.convert(node.body, depth + 1),
                "else": self.convert(node.orelse, depth + 1),
            }
        if isinstance(node, ast.Call):
            if node.keywords:
                raise CassiPySyntaxError("keyword arguments are not supported")
            return {
                "type": "call",
                "func": self.convert(node.func, depth + 1),
                "args": [self.convert(arg, depth + 1) for arg in node.args],
            }
        if isinstance(node, ast.ListComp):
            if len(node.generators) != 1 or node.generators[0].ifs or node.generators[0].is_async:
                raise CassiPySyntaxError("only one-generator list comprehensions are supported")
            generator = node.generators[0]
            return {
                "type": "listcomp",
                "elt": self.convert(node.elt, depth + 1),
                "target": self.convert(generator.target, depth + 1),
                "iter": self.convert(generator.iter, depth + 1),
            }
        if isinstance(node, ast.List):
            return {"type": "list", "items": [self.convert(v, depth + 1) for v in node.elts]}
        if isinstance(node, ast.Tuple):
            return {"type": "tuple", "items": [self.convert(v, depth + 1) for v in node.elts]}
        if isinstance(node, ast.Dict):
            if any(key is None for key in node.keys):
                raise CassiPySyntaxError("dictionary unpacking is not supported")
            return {
                "type": "dict",
                "items": [
                    {"key": self.convert(key, depth + 1), "value": self.convert(value, depth + 1)}
                    for key, value in zip(node.keys, node.values)
                ],
            }
        if isinstance(node, ast.Subscript):
            return {
                "type": "subscript",
                "value": self.convert(node.value, depth + 1),
                "index": self.convert(node.slice, depth + 1),
            }
        raise CassiPySyntaxError(f"Python node is outside CassiPy: {type(node).__name__}")

    def _statements(self, nodes: Sequence[ast.stmt], depth: int) -> list[dict[str, Any]]:
        return [self.convert(node, depth) for node in nodes]


def parse_source(source: str, *, params: Sequence[str] = ()) -> dict[str, Any]:
    if not isinstance(source, str) or not source.strip():
        raise CassiPySyntaxError("source must be nonempty text")
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise CassiPySyntaxError(str(exc)) from exc
    canonicalizer = _Canonicalizer(params=params)
    body = canonicalizer.convert(tree)
    return {
        "schema": PROGRAM_SCHEMA,
        "params": list(canonicalizer.params),
        "body": body,
    }


def canonical_program(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"schema", "params", "body"}:
        raise CassiPySyntaxError("program must contain exactly schema, params, and body")
    if value["schema"] != PROGRAM_SCHEMA or not isinstance(value["params"], list):
        raise CassiPySyntaxError("program schema or parameters are invalid")
    params = [_check_identifier(name, "parameter") for name in value["params"]]
    if len(set(params)) != len(params) or not isinstance(value["body"], Mapping):
        raise CassiPySyntaxError("program parameters or body are invalid")
    return {"schema": PROGRAM_SCHEMA, "params": params, "body": copy.deepcopy(value["body"])}


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    value: Any
    steps: int


@dataclass(frozen=True, slots=True)
class PythonCase:
    case_id: str
    inputs: Mapping[str, Any]
    expected: Any = _MISSING


@dataclass(frozen=True, slots=True)
class _Function:
    name: str
    args: tuple[str, ...]
    body: tuple[Mapping[str, Any], ...]
    closure: dict[str, Any]


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _Interpreter:
    def __init__(self, inputs: Mapping[str, Any], *, max_steps: int, max_call_depth: int) -> None:
        self.frames: list[dict[str, Any]] = [dict(inputs)]
        self.steps = 0
        self.max_steps = max_steps
        self.max_call_depth = max_call_depth

    def tick(self) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise CassiPyBudgetError("program exceeded execution-step budget")

    def lookup(self, name: str) -> Any:
        for frame in reversed(self.frames):
            if name in frame:
                return frame[name]
        raise CassiPyRuntimeError(f"name is not defined: {name}")

    def assign(self, target: Mapping[str, Any], value: Any) -> None:
        if target["type"] == "name":
            self.frames[-1][target["id"]] = _bounded(value)
            return
        if target["type"] == "subscript":
            container = self.eval(target["value"])
            index = self.eval(target["index"])
            try:
                container[index] = _bounded(value)
            except (IndexError, KeyError, TypeError) as exc:
                raise CassiPyRuntimeError("invalid subscript assignment") from exc
            return
        raise CassiPyRuntimeError("assignment target is not writable")

    def eval(self, node: Mapping[str, Any]) -> Any:
        self.tick()
        kind = node["type"]
        if kind == "constant":
            return node["value"]
        if kind == "name":
            name = node["id"]
            if name in _SAFE_BUILTINS:
                return name
            return self.lookup(name)
        if kind == "binop":
            return _bounded(_apply_binary(node["op"], self.eval(node["left"]), self.eval(node["right"])))
        if kind == "unary":
            value = self.eval(node["value"])
            if node["op"] == "pos":
                return +value
            if node["op"] == "neg":
                return _bounded(-value)
            if node["op"] == "not":
                return not value
        if kind == "boolop":
            if node["op"] == "and":
                result: Any = None
                for child in node["values"]:
                    result = self.eval(child)
                    if not result:
                        return result
                return result
            result = None
            for child in node["values"]:
                result = self.eval(child)
                if result:
                    return result
            return result
        if kind == "compare":
            left = self.eval(node["left"])
            right = self.eval(node["right"])
            return _apply_compare(node["op"], left, right)
        if kind == "ifexp":
            branch = node["then"] if self.eval(node["test"]) else node["else"]
            return self.eval(branch)
        if kind == "call":
            function = self.eval(node["func"])
            return self.call(function, [self.eval(arg) for arg in node["args"]])
        if kind == "list":
            return _bounded([self.eval(item) for item in node["items"]])
        if kind == "listcomp":
            iterable = self.eval(node["iter"])
            if not isinstance(iterable, (list, tuple, str, dict)):
                raise CassiPyRuntimeError("list comprehension requires a bounded iterable")
            frame: dict[str, Any] = {}
            self.frames.append(frame)
            try:
                values = []
                for item in iterable:
                    self.assign(node["target"], item)
                    values.append(self.eval(node["elt"]))
                return _bounded(values)
            finally:
                self.frames.pop()
        if kind == "tuple":
            return _bounded(tuple(self.eval(item) for item in node["items"]))
        if kind == "dict":
            return _bounded({self.eval(item["key"]): self.eval(item["value"]) for item in node["items"]})
        if kind == "subscript":
            try:
                return _bounded(self.eval(node["value"])[self.eval(node["index"])])
            except (IndexError, KeyError, TypeError) as exc:
                raise CassiPyRuntimeError("invalid subscript read") from exc
        raise CassiPyRuntimeError(f"expression is not implemented: {kind}")

    def call(self, function: Any, args: list[Any]) -> Any:
        if isinstance(function, str) and function in _SAFE_BUILTINS:
            return _bounded(_call_builtin(function, args))
        if not isinstance(function, _Function):
            raise CassiPyRuntimeError("only bounded built-ins and CassiPy functions are callable")
        if len(self.frames) >= self.max_call_depth:
            raise CassiPyBudgetError("function call depth exceeded")
        if len(args) != len(function.args):
            raise CassiPyRuntimeError(f"function {function.name} received the wrong arity")
        frame = dict(function.closure)
        frame.update(zip(function.args, args))
        self.frames.append(frame)
        try:
            self.exec_block(function.body)
        except _ReturnSignal as signal:
            return _bounded(signal.value)
        finally:
            self.frames.pop()
        return None

    def assign_function(self, node: Mapping[str, Any]) -> None:
        function = _Function(
            name=node["name"],
            args=tuple(node["args"]),
            body=tuple(node["body"]),
            closure=self.frames[-1],
        )
        self.frames[-1][node["name"]] = function

    def exec_stmt(self, node: Mapping[str, Any]) -> Any:
        self.tick()
        kind = node["type"]
        if kind == "assign":
            value = self.eval(node["value"])
            self.assign(node["target"], value)
            return value
        if kind == "augassign":
            current = self.eval(node["target"])
            value = _apply_binary(node["op"], current, self.eval(node["value"]))
            self.assign(node["target"], _bounded(value))
            return value
        if kind == "expr":
            return self.eval(node["value"])
        if kind == "function":
            self.assign_function(node)
            return None
        if kind == "return":
            raise _ReturnSignal(None if node["value"] is None else self.eval(node["value"]))
        if kind == "if":
            chosen = node["body"] if self.eval(node["test"]) else node["orelse"]
            return self.exec_block(chosen)
        if kind == "for":
            iterable = self.eval(node["iter"])
            if not isinstance(iterable, (list, tuple, str, dict)):
                raise CassiPyRuntimeError("for requires a bounded iterable")
            completed = True
            last = None
            for item in iterable:
                self.assign(node["target"], item)
                try:
                    last = self.exec_block(node["body"])
                except _ContinueSignal:
                    continue
                except _BreakSignal:
                    completed = False
                    break
            if completed and node["orelse"]:
                last = self.exec_block(node["orelse"])
            return last
        if kind == "break":
            raise _BreakSignal()
        if kind == "continue":
            raise _ContinueSignal()
        raise CassiPyRuntimeError(f"statement is not implemented: {kind}")

    def exec_block(self, body: Sequence[Mapping[str, Any]]) -> Any:
        result = None
        for statement in body:
            result = self.exec_stmt(statement)
        return result


def _call_builtin(name: str, args: Sequence[Any]) -> Any:
    if name == "range":
        if not 1 <= len(args) <= 3 or any(isinstance(arg, bool) or not isinstance(arg, int) for arg in args):
            raise CassiPyRuntimeError("range requires one to three integer arguments")
        values = list(range(*args))
        if len(values) > MAX_SEQUENCE:
            raise CassiPyBudgetError("range exceeds sequence budget")
        return values
    if name == "len":
        if len(args) != 1:
            raise CassiPyRuntimeError("len requires one argument")
        return len(args[0])
    if name == "sum":
        if len(args) != 1:
            raise CassiPyRuntimeError("sum requires one argument")
        return sum(args[0])
    if name in {"min", "max"}:
        if len(args) != 1 or not args[0]:
            raise CassiPyRuntimeError(f"{name} requires one nonempty iterable")
        return min(args[0]) if name == "min" else max(args[0])
    if name == "abs":
        if len(args) != 1:
            raise CassiPyRuntimeError("abs requires one argument")
        return abs(args[0])
    if name == "int":
        if len(args) != 1:
            raise CassiPyRuntimeError("int requires one argument")
        return int(args[0])
    if name == "bool":
        if len(args) != 1:
            raise CassiPyRuntimeError("bool requires one argument")
        return bool(args[0])
    raise CassiPyRuntimeError(f"unknown built-in: {name}")


def _apply_binary(op: str, left: Any, right: Any) -> Any:
    try:
        if op == "add":
            return left + right
        if op == "sub":
            return left - right
        if op == "mul":
            return left * right
        if op == "div":
            return left / right
        if op == "floordiv":
            return left // right
        if op == "mod":
            return left % right
        if op == "pow":
            if isinstance(right, int) and abs(right) > 1_000_000:
                raise CassiPyBudgetError("power exponent exceeds budget")
            return left**right
    except (ArithmeticError, TypeError) as exc:
        raise CassiPyRuntimeError(f"binary operation {op} failed") from exc
    raise CassiPyRuntimeError(f"binary operation is not implemented: {op}")


def _apply_compare(op: str, left: Any, right: Any) -> bool:
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    if op == "gt":
        return left > right
    if op == "ge":
        return left >= right
    raise CassiPyRuntimeError(f"comparison is not implemented: {op}")


def execute_program(
    program: Mapping[str, Any], inputs: Mapping[str, Any] | None = None, *,
    max_steps: int = MAX_STEPS, max_call_depth: int = MAX_CALL_DEPTH,
) -> ExecutionResult:
    canonical = canonical_program(program)
    actual_inputs = dict(inputs or {})
    if set(actual_inputs) != set(canonical["params"]):
        raise CassiPyRuntimeError("inputs do not match the program parameter contract")
    interpreter = _Interpreter(_bounded(actual_inputs), max_steps=max_steps, max_call_depth=max_call_depth)
    try:
        value = interpreter.exec_block(canonical["body"]["body"])
    except (_BreakSignal, _ContinueSignal) as exc:
        raise CassiPyRuntimeError("break or continue escaped its loop") from exc
    if value is None and "result" in interpreter.frames[0]:
        value = interpreter.frames[0]["result"]
    return ExecutionResult(value=_bounded(value), steps=interpreter.steps)


def run_source(
    source: str, inputs: Mapping[str, Any] | None = None, *,
    max_steps: int = MAX_STEPS, max_call_depth: int = MAX_CALL_DEPTH,
) -> ExecutionResult:
    actual_inputs = dict(inputs or {})
    program = parse_source(source, params=tuple(actual_inputs))
    return execute_program(program, actual_inputs, max_steps=max_steps, max_call_depth=max_call_depth)


def _cpython_result(source: str, inputs: Mapping[str, Any]) -> Any:
    """Run an already-canonicalized fixture against restricted CPython built-ins."""
    import builtins

    namespace: dict[str, Any] = {
        "__builtins__": {name: getattr(builtins, name) for name in _SAFE_BUILTINS}
    }
    namespace.update(_bounded(dict(inputs)))
    exec(compile(source, "<cassi-python-oracle>", "exec"), namespace, namespace)
    return namespace.get("result")


def differential_case(source: str, case: PythonCase) -> dict[str, Any]:
    cassi = run_source(source, case.inputs)
    reference = _cpython_result(source, case.inputs)
    expected_ok = case.expected is _MISSING or cassi.value == case.expected
    return {
        "case_id": case.case_id,
        "cassi_value": cassi.value,
        "cpython_value": reference,
        "steps": cassi.steps,
        "equivalent": cassi.value == reference,
        "expected": None if case.expected is _MISSING else case.expected,
        "expected_ok": expected_ok,
        "passed": cassi.value == reference and expected_ok,
    }


def verify_differential(source: str, cases: Sequence[PythonCase]) -> dict[str, Any]:
    rows = [differential_case(source, case) for case in cases]
    return {"passed": all(row["passed"] for row in rows), "cases": rows}


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    status: str
    original_steps: int
    candidate_steps: int
    equivalent: bool
    improved: bool
    changes: int
    original: Mapping[str, Any]
    candidate: Mapping[str, Any]
    cases: tuple[Mapping[str, Any], ...]


def _constant(node: Mapping[str, Any]) -> tuple[bool, Any]:
    if node.get("type") == "constant":
        return True, node.get("value")
    return False, None


def _fold_expr(node: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
    kind = node["type"]
    changes = 0
    result = copy.deepcopy(dict(node))
    for key in ("left", "right", "value", "test", "then", "else", "func", "index", "elt", "iter"):
        child = result.get(key)
        if isinstance(child, Mapping):
            folded, delta = _fold_expr(child)
            result[key] = folded
            changes += delta
    for key in ("args", "items", "values"):
        if isinstance(result.get(key), list):
            folded_items = []
            for item in result[key]:
                if isinstance(item, Mapping):
                    folded, delta = _fold_expr(item)
                    folded_items.append(folded)
                    changes += delta
                else:
                    folded_items.append(item)
            result[key] = folded_items
    if kind == "binop":
        left_ok, left = _constant(result["left"])
        right_ok, right = _constant(result["right"])
        if left_ok and right_ok:
            value = _bounded(_apply_binary(result["op"], left, right))
            return {"type": "constant", "value": value}, changes + 1
    if kind == "ifexp":
        test_ok, test = _constant(result["test"])
        if test_ok:
            return copy.deepcopy(result["then"] if test else result["else"]), changes + 1
    return result, changes


def _optimize_block(body: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    output: list[dict[str, Any]] = []
    changes = 0
    for statement in body:
        kind = statement["type"]
        if kind == "if":
            test, delta = _fold_expr(statement["test"])
            changes += delta
            test_ok, value = _constant(test)
            if test_ok:
                chosen = statement["body"] if value else statement["orelse"]
                branch, branch_delta = _optimize_block(chosen)
                output.extend(branch)
                changes += branch_delta + 1
                continue
            body_out, body_delta = _optimize_block(statement["body"])
            else_out, else_delta = _optimize_block(statement["orelse"])
            output.append({"type": "if", "test": test, "body": body_out, "orelse": else_out})
            changes += body_delta + else_delta
            continue
        if kind == "for":
            body_out, body_delta = _optimize_block(statement["body"])
            else_out, else_delta = _optimize_block(statement["orelse"])
            iterable, iterable_delta = _fold_expr(statement["iter"])
            output.append({**statement, "iter": iterable, "body": body_out, "orelse": else_out})
            changes += body_delta + else_delta + iterable_delta
            continue
        if kind == "function":
            body_out, body_delta = _optimize_block(statement["body"])
            output.append({**statement, "body": body_out})
            changes += body_delta
            continue
        changed = copy.deepcopy(dict(statement))
        for key in ("value", "target"):
            if isinstance(changed.get(key), Mapping) and key == "value":
                changed[key], delta = _fold_expr(changed[key])
                changes += delta
        output.append(changed)
    return output, changes


def optimize_program(program: Mapping[str, Any]) -> tuple[dict[str, Any], int]:
    original = canonical_program(program)
    body, changes = _optimize_block(original["body"]["body"])
    return {**original, "body": {"type": "module", "body": body}}, changes


def evaluate_optimization(
    original: Mapping[str, Any], cases: Sequence[PythonCase], candidate: Mapping[str, Any] | None = None,
) -> OptimizationResult:
    original_program = canonical_program(original)
    candidate_program = canonical_program(candidate) if candidate is not None else optimize_program(original_program)[0]
    rows: list[Mapping[str, Any]] = []
    original_steps = 0
    candidate_steps = 0
    equivalent = True
    for case in cases:
        before = execute_program(original_program, case.inputs)
        after = execute_program(candidate_program, case.inputs)
        original_steps += before.steps
        candidate_steps += after.steps
        same = before.value == after.value
        equivalent = equivalent and same
        rows.append({"case_id": case.case_id, "before": before.value, "after": after.value, "same": same})
    changes = 0 if digest_value(original_program) == digest_value(candidate_program) else 1
    improved = equivalent and candidate_steps < original_steps
    return OptimizationResult(
        status="PASS" if improved else "REJECT",
        original_steps=original_steps,
        candidate_steps=candidate_steps,
        equivalent=equivalent,
        improved=improved,
        changes=changes,
        original=original_program,
        candidate=candidate_program,
        cases=tuple(rows),
    )

def evaluate_source_candidate(
    original_source: str,
    candidate_source: str,
    cases: Sequence[PythonCase],
) -> OptimizationResult:
    if not cases:
        raise CassiPyRuntimeError("source optimization requires at least one case")
    params = tuple(cases[0].inputs)
    if any(tuple(case.inputs) != params for case in cases):
        raise CassiPyRuntimeError("source optimization cases must share parameters")
    original = parse_source(original_source, params=params)
    candidate = parse_source(candidate_source, params=params)
    return evaluate_optimization(original, cases, candidate)


@dataclass(frozen=True, slots=True)
class PythonLesson:
    lesson_id: str
    title: str
    source: str
    cases: tuple[PythonCase, ...]
    domains: tuple[str, ...] = ("algorithmic-math", "cassi-python")


CURRICULUM: tuple[PythonLesson, ...] = (
    PythonLesson("P0", "Expressions and values", "result = 2 + 3 * 4", (PythonCase("p0", {}, 14),)),
    PythonLesson("P1", "Names and assignment", "result = value * value", (PythonCase("p1", {"value": 7}, 49),)),
    PythonLesson(
        "P2", "Conditionals", "if value < 0:\n    result = -value\nelse:\n    result = value",
        (PythonCase("p2-negative", {"value": -8}, 8), PythonCase("p2-positive", {"value": 8}, 8)),
    ),
    PythonLesson(
        "P3", "Bounded iteration", "total = 0\nfor value in values:\n    total = total + value\nresult = total",
        (PythonCase("p3", {"values": [1, 2, 3, 4]}, 10),),
    ),
    PythonLesson(
        "P4", "Lists and comprehensions", "result = [value * 2 for value in values]",
        (PythonCase("p4", {"values": [2, 5, 9]}, [4, 10, 18]),),
    ),
    PythonLesson(
        "P5", "Functions and scope", "def square(value):\n    return value * value\nresult = square(value)",
        (PythonCase("p5", {"value": 11}, 121),),
    ),
    PythonLesson(
        "P6", "Recursion", "def factorial(value):\n    return 1 if value <= 1 else value * factorial(value - 1)\nresult = factorial(value)",
        (PythonCase("p6", {"value": 6}, 720),),
    ),
    PythonLesson(
        "P7", "Collections and built-ins", "result = {\"length\": len(text), \"first\": text[0]}",
        (PythonCase("p7", {"text": "cassi"}, {"length": 5, "first": "c"}),),
    ),
)


FINANCIAL_CURRICULUM: tuple[PythonLesson, ...] = (
    PythonLesson(
        "FM0",
        "Simple return",
        "result = current / previous - 1",
        (
            PythonCase("fm0-up", {"previous": 100.0, "current": 110.0}, 0.10000000000000009),
            PythonCase("fm0-down", {"previous": 100.0, "current": 95.0}, -0.050000000000000044),
        ),
        ("financial-math", "returns", "cassi-python"),
    ),
    PythonLesson(
        "FM1",
        "Compounded return",
        "wealth = 1\nfor value in returns:\n    wealth = wealth * (1 + value)\nresult = wealth - 1",
        (
            PythonCase("fm1-two-periods", {"returns": [0.1, -0.1]}, -0.009999999999999898),
            PythonCase("fm1-positive", {"returns": [0.05, 0.02]}, 0.07100000000000017),
        ),
        ("financial-math", "returns", "cassi-python"),
    ),
    PythonLesson(
        "FM2",
        "Maximum drawdown",
        "peak = values[0]\nresult = 0\nfor value in values:\n    if value > peak:\n        peak = value\n    drawdown = 1 - value / peak\n    if drawdown > result:\n        result = drawdown",
        (
            PythonCase("fm2-drawdown", {"values": [1.0, 1.2, 1.1, 0.96, 1.05]}, 0.19999999999999996),
            PythonCase("fm2-flat", {"values": [1.0, 1.0, 1.0]}, 0.0),
        ),
        ("financial-math", "risk", "cassi-python"),
    ),
    PythonLesson(
        "FM3",
        "Transaction cost",
        "result = turnover * (fee_bps + slippage_bps) / 10000",
        (
            PythonCase("fm3-standard", {"turnover": 2.0, "fee_bps": 10.0, "slippage_bps": 5.0}, 0.003),
            PythonCase("fm3-zero", {"turnover": 0.0, "fee_bps": 25.0, "slippage_bps": 10.0}, 0.0),
        ),
        ("financial-math", "execution", "cassi-python"),
    ),
    PythonLesson(
        "FM4",
        "Risk-sized position",
        "risk_capital = equity * risk_fraction\nresult = risk_capital / stop_distance\nif result > max_position:\n    result = max_position",
        (
            PythonCase(
                "fm4-capped",
                {"equity": 10000.0, "risk_fraction": 0.01, "stop_distance": 100.0, "max_position": 0.5},
                0.5,
            ),
            PythonCase(
                "fm4-uncapped",
                {"equity": 10000.0, "risk_fraction": 0.01, "stop_distance": 500.0, "max_position": 1.0},
                0.2,
            ),
        ),
        ("financial-math", "risk", "position-sizing", "cassi-python"),
    ),
    PythonLesson(
        "FM5",
        "Multi-dimensional risk-adjusted objective",
        "result = net_return - drawdown_penalty * max_drawdown - turnover_penalty * turnover + performance_weight * performance_value - sizing_penalty * abs(position_size - target_position)",
        (
            PythonCase(
                "fm5-balanced",
                {
                    "net_return": 0.12,
                    "drawdown_penalty": 1.5,
                    "max_drawdown": 0.08,
                    "turnover_penalty": 0.0005,
                    "turnover": 10.0,
                    "performance_value": 1.5,
                    "performance_weight": 0.01,
                    "position_size": 0.25,
                    "target_position": 0.25,
                    "sizing_penalty": 0.02,
                },
                0.009999999999999998,
            ),
            PythonCase(
                "fm5-clean",
                {
                    "net_return": 0.05,
                    "drawdown_penalty": 1.5,
                    "max_drawdown": 0.0,
                    "turnover_penalty": 0.0005,
                    "turnover": 2.0,
                    "performance_value": 0.8,
                    "performance_weight": 0.01,
                    "position_size": 0.4,
                    "target_position": 0.25,
                    "sizing_penalty": 0.02,
                },
                0.054,
            ),
        ),
        ("financial-math", "risk", "portfolio-objective", "cassi-python"),
    ),
    PythonLesson(
        "FM6",
        "Active hit rate",
        "wins = 0\nactive = 0\nfor value in returns:\n    if value != 0:\n        active = active + 1\n        if value > 0:\n            wins = wins + 1\nresult = wins / active",
        (
            PythonCase("fm6-mixed", {"returns": [0.1, -0.02, 0.0, 0.03]}, 2 / 3),
            PythonCase("fm6-all-wins", {"returns": [0.01, 0.02]}, 1.0),
        ),
        ("financial-math", "performance", "cassi-python"),
    ),
    PythonLesson(
        "FM7",
        "Mean absolute volatility",
        "total = 0\nfor value in returns:\n    total = total + abs(value)\nresult = total / len(returns)",
        (
            PythonCase("fm7-mixed", {"returns": [0.1, -0.05, 0.02]}, 0.05666666666666667),
            PythonCase("fm7-flat", {"returns": [0.0, 0.0]}, 0.0),
        ),
        ("financial-math", "risk", "volatility", "cassi-python"),
    ),
    PythonLesson(
        "FM8",
        "Downside deviation",
        "total = 0\ncount = 0\nfor value in returns:\n    if value < target:\n        difference = value - target\n        total = total + difference * difference\n        count = count + 1\nif count == 0:\n    result = 0\nelse:\n    result = (total / count) ** 0.5",
        (
            PythonCase(
                "fm8-mixed",
                {"returns": [0.1, -0.1, 0.0], "target": 0.0},
                0.1,
            ),
            PythonCase(
                "fm8-clean",
                {"returns": [0.02, 0.03], "target": 0.0},
                0.0,
            ),
        ),
        ("financial-math", "risk", "downside-risk", "cassi-python"),
    ),
    PythonLesson(
        "FM9",
        "Expected shortfall below a threshold",
        "total = 0\ncount = 0\nfor value in returns:\n    if value <= threshold:\n        total = total + value\n        count = count + 1\nif count == 0:\n    result = threshold\nelse:\n    result = total / count",
        (
            PythonCase(
                "fm9-tail",
                {"returns": [0.1, -0.1, -0.2, 0.05], "threshold": -0.1},
                -0.15000000000000002,
            ),
            PythonCase(
                "fm9-no-tail",
                {"returns": [0.02, 0.03], "threshold": -0.1},
                -0.1,
            ),
        ),
        ("financial-math", "risk", "tail-risk", "cassi-python"),
    ),
    PythonLesson(
        "FM10",
        "Profit factor",
        "wins = 0\nlosses = 0\nfor value in returns:\n    if value > 0:\n        wins = wins + value\n    elif value < 0:\n        losses = losses - value\nif losses == 0:\n    result = 0\nelse:\n    result = wins / losses",
        (
            PythonCase(
                "fm10-mixed",
                {"returns": [0.1, -0.05, 0.0]},
                2.0,
            ),
            PythonCase(
                "fm10-no-loss",
                {"returns": [0.01, 0.02]},
                0.0,
            ),
        ),
        ("financial-math", "performance", "profit-factor", "cassi-python"),
    ),
    PythonLesson(
        "FM11",
        "Kelly fraction capped",
        "if average_win <= 0:\n    result = 0\nelif average_loss <= 0:\n    result = max_fraction\nelse:\n    odds = average_win / average_loss\n    result = win_rate - (1 - win_rate) / odds\n    if result < 0:\n        result = 0\n    if result > max_fraction:\n        result = max_fraction",
        (
            PythonCase(
                "fm11-capped",
                {
                    "win_rate": 0.55,
                    "average_win": 0.02,
                    "average_loss": 0.01,
                    "max_fraction": 0.25,
                },
                0.25,
            ),
            PythonCase(
                "fm11-negative-edge",
                {
                    "win_rate": 0.4,
                    "average_win": 0.01,
                    "average_loss": 0.02,
                    "max_fraction": 0.25,
                },
                0.0,
            ),
        ),
        ("financial-math", "risk", "position-sizing", "cassi-python"),
    ),
    PythonLesson(
        "FM12",
        "Approximate risk of ruin",
        "if win_rate <= 0.5:\n    result = 1\nelse:\n    odds = (1 - win_rate) / win_rate\n    exponent = loss_limit / risk_fraction\n    result = odds ** exponent",
        (
            PythonCase(
                "fm12-positive-edge",
                {
                    "win_rate": 0.6,
                    "risk_fraction": 0.01,
                    "loss_limit": 0.2,
                },
                0.00030072865982171815,
            ),
            PythonCase(
                "fm12-no-edge",
                {
                    "win_rate": 0.5,
                    "risk_fraction": 0.01,
                    "loss_limit": 0.2,
                },
                1.0,
            ),
        ),
        ("financial-math", "risk", "ruin", "cassi-python"),
    ),
)


FULL_CURRICULUM: tuple[PythonLesson, ...] = CURRICULUM + FINANCIAL_CURRICULUM


def run_apprenticeship() -> dict[str, Any]:
    lesson_rows: list[dict[str, Any]] = []
    for lesson in FULL_CURRICULUM:
        differential = verify_differential(lesson.source, lesson.cases)
        lesson_rows.append(
            {
                "lesson_id": lesson.lesson_id,
                "title": lesson.title,
                "domains": list(lesson.domains),
                "differential": differential,
            }
        )
    optimization_source = "result = (2 + 3) * value"
    optimization_cases = (PythonCase("optimizer", {"value": 9}, 45),)
    optimization_program = parse_source(optimization_source, params=("value",))
    optimization = evaluate_optimization(optimization_program, optimization_cases)
    candidate_source = "result = 5 * value"
    self_optimization = evaluate_source_candidate(optimization_source, candidate_source, optimization_cases)
    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "program_schema": PROGRAM_SCHEMA,
        "curriculum": [
            {"lesson_id": row["lesson_id"], "title": row["title"], "domains": row["domains"]}
            for row in lesson_rows
        ],
        "lessons": lesson_rows,
        "optimization": {
            "status": optimization.status,
            "equivalent": optimization.equivalent,
            "improved": optimization.improved,
            "changes": optimization.changes,
            "original_steps": optimization.original_steps,
            "candidate_steps": optimization.candidate_steps,
            "cases": list(optimization.cases),
        },
        "self_optimization": {
            "target": "cassi-python-program",
            "baseline_source": optimization_source,
            "candidate_source": candidate_source,
            "status": self_optimization.status,
            "equivalent": self_optimization.equivalent,
            "improved": self_optimization.improved,
            "original_steps": self_optimization.original_steps,
            "candidate_steps": self_optimization.candidate_steps,
            "cases": list(self_optimization.cases),
        },
    }
    body["status"] = (
        "PASS"
        if all(row["differential"]["passed"] for row in lesson_rows)
        and optimization.status == "PASS"
        and self_optimization.status == "PASS"
        else "FAIL"
    )
    body["content_sha256"] = digest_value(body)
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not content_digest_matches(receipt):
        raise CassiPyError("receipt content digest mismatch")
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("status") != "PASS":
        raise CassiPyError("receipt is not a passing CassiPy apprenticeship")
    if not all(lesson["differential"]["passed"] for lesson in receipt.get("lessons", [])):
        raise CassiPyError("lesson differential verification failed")
    if receipt.get("optimization", {}).get("status") != "PASS":
        raise CassiPyError("optimization promotion failed")
    if receipt.get("self_optimization", {}).get("status") != "PASS":
        raise CassiPyError("self-optimization candidate was not promoted")
    return {"status": "PASS", "content_sha256": receipt["content_sha256"]}


__all__ = [
    "CassiPyBudgetError",
    "CassiPyError",
    "CassiPyRuntimeError",
    "CassiPySyntaxError",
    "CURRICULUM",
    "FINANCIAL_CURRICULUM",
    "FULL_CURRICULUM",
    "ExecutionResult",
    "MAX_STEPS",
    "OptimizationResult",
    "PROGRAM_SCHEMA",
    "PythonCase",
    "PythonLesson",
    "RECEIPT_SCHEMA",
    "canonical_program",
    "content_digest_matches",
    "digest_value",
    "evaluate_optimization",
    "evaluate_source_candidate",
    "execute_program",
    "optimize_program",
    "parse_source",
    "run_apprenticeship",
    "run_source",
    "verify_differential",
    "verify_receipt",
]
