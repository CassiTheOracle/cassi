"""Deterministic Python 3.12 bootstrap compiler for the field interpreter.

``ast.parse`` supplies the pinned grammar only.  This module lowers the parsed
form to an immutable, JSON-serializable instruction graph.  It never executes
source and never emits host Python bytecode.
"""
from __future__ import annotations

import ast
import base64
import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .records import PythonProgram, canonical_json_bytes, digest_value


class CompilerError(ValueError):
    """Source cannot be represented by the bounded field instruction set."""


_BINARY = {
    ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.MatMult: "matmul",
    ast.Div: "truediv", ast.FloorDiv: "floordiv", ast.Mod: "mod",
    ast.Pow: "pow", ast.LShift: "lshift", ast.RShift: "rshift",
    ast.BitOr: "or", ast.BitXor: "xor", ast.BitAnd: "and",
}
_UNARY = {ast.Invert: "invert", ast.Not: "not", ast.UAdd: "pos", ast.USub: "neg"}
_COMPARE = {
    ast.Eq: "eq", ast.NotEq: "ne", ast.Lt: "lt", ast.LtE: "le",
    ast.Gt: "gt", ast.GtE: "ge", ast.Is: "is", ast.IsNot: "is-not",
    ast.In: "in", ast.NotIn: "not-in",
}


def _constant(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {"kind": "none"}
    if value is Ellipsis:
        return {"kind": "ellipsis"}
    if isinstance(value, bool):
        return {"kind": "bool", "value": value}
    if isinstance(value, int):
        return {"kind": "int", "value": str(value)}
    if isinstance(value, float):
        return {"kind": "float", "value": value.hex()}
    if isinstance(value, complex):
        return {"kind": "complex", "real": value.real.hex(), "imag": value.imag.hex()}
    if isinstance(value, str):
        return {"kind": "str", "value": value}
    if isinstance(value, bytes):
        return {"kind": "bytes", "value": base64.b64encode(value).decode("ascii")}
    if isinstance(value, tuple):
        return {"kind": "tuple", "items": [_constant(item) for item in value]}
    if isinstance(value, frozenset):
        return {"kind": "frozenset", "items": [_constant(item) for item in value]}
    raise CompilerError(f"unsupported literal constant: {type(value).__name__}")


def _span(node: ast.AST | None) -> Mapping[str, int] | None:
    if node is None or not hasattr(node, "lineno"):
        return None
    return {
        "line": int(node.lineno),
        "column": int(node.col_offset),
        "end_line": int(getattr(node, "end_lineno", node.lineno)),
        "end_column": int(getattr(node, "end_col_offset", node.col_offset)),
    }


def _dotted_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return None if prefix is None else f"{prefix}.{node.attr}"
    return None

def _pattern_key(node: ast.expr) -> Mapping[str, Any]:
    if isinstance(node, ast.Constant):
        return _constant(node.value)
    name = _dotted_name(node)
    if name is None:
        raise CompilerError("mapping pattern key must be a literal or dotted name")
    return {"name": name}



def _pattern(node: ast.pattern) -> Mapping[str, Any]:
    span = _span(node)
    if isinstance(node, ast.MatchValue):
        if isinstance(node.value, ast.Constant):
            return {
                "kind": "value",
                "value": _constant(node.value.value),
                "span": span,
            }
        name = _dotted_name(node.value)
        if name is None:
            raise CompilerError("match value must be a literal or dotted name")
        return {"kind": "value-name", "name": name, "span": span}
    if isinstance(node, ast.MatchSingleton):
        return {"kind": "singleton", "value": _constant(node.value), "span": span}
    if isinstance(node, ast.MatchSequence):
        return {"kind": "sequence", "patterns": [_pattern(item) for item in node.patterns], "span": span}
    if isinstance(node, ast.MatchMapping):
        return {
            "kind": "mapping",
            "keys": [_pattern_key(key) for key in node.keys],
            "patterns": [_pattern(item) for item in node.patterns],
            "rest": node.rest,
            "span": span,
        }
    if isinstance(node, ast.MatchClass):
        class_name = _dotted_name(node.cls)
        if class_name is None:
            raise CompilerError("match class must be a dotted name")
        return {
            "kind": "class",
            "class_name": class_name,
            "patterns": [_pattern(item) for item in node.patterns],
            "keyword_names": list(node.kwd_attrs),
            "keyword_patterns": [_pattern(item) for item in node.kwd_patterns],
            "span": span,
        }
    if isinstance(node, ast.MatchStar):
        return {"kind": "star", "name": node.name, "span": span}
    if isinstance(node, ast.MatchAs):
        return {"kind": "as", "pattern": None if node.pattern is None else _pattern(node.pattern), "name": node.name, "span": span}
    if isinstance(node, ast.MatchOr):
        return {"kind": "or", "patterns": [_pattern(item) for item in node.patterns], "span": span}
    raise CompilerError(f"unsupported pattern node: {type(node).__name__}")


@dataclass
class _CodeBuilder:
    compiler: "_Compiler"
    code_id: str
    name: str
    qualname: str
    kind: str
    arguments: Mapping[str, Any]
    first_line: int
    source_span: Mapping[str, int] | None = None
    instructions: list[dict[str, Any]] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)
    patches: list[tuple[int, str, str | None]] = field(default_factory=list)
    globals: set[str] = field(default_factory=set)
    nonlocals: set[str] = field(default_factory=set)
    flags: set[str] = field(default_factory=set)
    _label_counter: int = 0
    _temp_counter: int = 0

    def label(self, prefix: str = "L") -> str:
        self._label_counter += 1
        return f"{prefix}{self._label_counter}"

    def temp(self, prefix: str = "tmp") -> str:
        self._temp_counter += 1
        return f".<{prefix}-{self._temp_counter}>"

    def mark(self, label: str) -> None:
        if label in self.labels:
            raise CompilerError("duplicate compiler label")
        self.labels[label] = len(self.instructions)

    def emit(self, op: str, arg: Any = None, node: ast.AST | None = None) -> int:
        row: dict[str, Any] = {"op": op}
        if arg is not None:
            row["arg"] = arg
        span = _span(node)
        if span is not None:
            row["span"] = span
        self.instructions.append(row)
        return len(self.instructions) - 1

    def jump(self, op: str, label: str, node: ast.AST | None = None, *, field_name: str | None = None) -> None:
        index = self.emit(op, None if field_name is None else {}, node)
        self.patches.append((index, label, field_name))

    def finish(self) -> Mapping[str, Any]:
        for index, label, field_name in self.patches:
            if label not in self.labels:
                raise CompilerError(f"unresolved compiler label: {label}")
            target = self.labels[label]
            if field_name is None:
                self.instructions[index]["arg"] = target
            else:
                self.instructions[index]["arg"][field_name] = target
        return {
            "code_id": self.code_id,
            "name": self.name,
            "qualname": self.qualname,
            "kind": self.kind,
            "arguments": dict(self.arguments),
            "first_line": self.first_line,
            "source_span": None if self.source_span is None else dict(self.source_span),
            "source_sha256": self.compiler.source_sha256,
            "instructions": self.instructions,
            "globals": sorted(self.globals),
            "nonlocals": sorted(self.nonlocals),
            "flags": sorted(self.flags),
        }


class _Compiler:
    def __init__(self, *, source_name: str, module: str, source_sha256: str) -> None:
        self.source_name = source_name
        self.module = module
        self.source_sha256 = source_sha256
        self.codes: dict[str, Mapping[str, Any]] = {}
        self.future_flags: set[str] = set()
        self._code_counter = 0
        self._code_ids: set[str] = set()

    def _new_builder(
        self,
        name: str,
        qualname: str,
        kind: str,
        arguments: Mapping[str, Any] | None,
        first_line: int,
        source_span: Mapping[str, int] | None = None,
    ) -> _CodeBuilder:
        self._code_counter += 1
        identity = {
            "source_sha256": self.source_sha256,
            "qualname": qualname,
            "kind": kind,
            "source_span": None if source_span is None else dict(source_span),
            "ordinal": self._code_counter,
        }
        digest = hashlib.sha256(canonical_json_bytes(identity)).hexdigest()[:24]
        code_id = f"code-{digest}"
        # Synthetic AST nodes (notably nested comprehensions) can share all
        # user-visible coordinates.  Keep the identity deterministic while
        # making that rare collision explicit rather than silently replacing
        # an earlier callable.
        suffix = 1
        candidate = code_id
        while candidate in self._code_ids:
            suffix += 1
            candidate = f"{code_id}-{suffix}"
        self._code_ids.add(candidate)
        return _CodeBuilder(
            self,
            candidate,
            name,
            qualname,
            kind,
            arguments or {
                "posonly": [], "positional": [], "vararg": None,
                "kwonly": [], "kwarg": None, "defaults": 0,
                "kw_defaults": [],
            },
            first_line,
            None if source_span is None else dict(source_span),
        )

    @staticmethod
    def _arguments(args: ast.arguments) -> Mapping[str, Any]:
        positional = [item.arg for item in args.args]
        return {
            "posonly": [item.arg for item in args.posonlyargs],
            "positional": positional,
            "vararg": None if args.vararg is None else args.vararg.arg,
            "kwonly": [item.arg for item in args.kwonlyargs],
            "kwarg": None if args.kwarg is None else args.kwarg.arg,
            "defaults": len(args.defaults),
            "kw_defaults": [item is not None for item in args.kw_defaults],
        }

    def annotation(self, builder: _CodeBuilder, node: ast.expr) -> None:
        if "annotations" in self.future_flags:
            builder.emit("LOAD_CONST", _constant(ast.unparse(node)), node)
        else:
            self.expression(builder, node)

    @staticmethod
    def _contains_yield(node: ast.AST) -> bool:
        """Find yields belonging to this scope, excluding nested scopes."""
        for child in ast.iter_child_nodes(node):
            if isinstance(
                child,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Lambda,
                    ast.ClassDef,
                ),
            ):
                continue
            if isinstance(child, (ast.Yield, ast.YieldFrom)):
                return True
            if _Compiler._contains_yield(child):
                return True
        return False

    def compile_root(self, tree: ast.AST, mode: str) -> str:
        builder = self._new_builder("<module>", self.module, "module", None, 1)
        if mode == "eval":
            assert isinstance(tree, ast.Expression)
            self.expression(builder, tree.body)
            builder.emit("RETURN", node=tree.body)
        else:
            body = tree.body if isinstance(tree, (ast.Module, ast.Interactive)) else ()
            self.statements(builder, body)
            builder.emit("LOAD_CONST", _constant(None), tree)
            builder.emit("RETURN", node=tree)
        self.codes[builder.code_id] = builder.finish()
        return builder.code_id

    def compile_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda, qualname: str) -> str:
        name = node.name if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "<lambda>"
        args = self._arguments(node.args)
        builder = self._new_builder(
            name,
            qualname,
            "function",
            args,
            int(getattr(node, "lineno", 1)),
            _span(node),
        )
        has_yield = self._contains_yield(node)
        if has_yield:
            builder.flags.add("generator")
            if isinstance(node, ast.AsyncFunctionDef):
                builder.flags.add("async-generator")
        if isinstance(node, ast.AsyncFunctionDef):
            builder.flags.add("coroutine")
        if isinstance(node, ast.Lambda):
            self.expression(builder, node.body)
            builder.emit("RETURN", node=node.body)
        else:
            self.statements(builder, node.body)
            builder.emit("LOAD_CONST", _constant(None), node)
            builder.emit("RETURN", node=node)
        self.codes[builder.code_id] = builder.finish()
        return builder.code_id
    @staticmethod
    def _type_parameters(node: ast.AST) -> list[Mapping[str, Any]]:
        """Encode PEP 695 parameters as inert field metadata.

        Bounds, constraints, and defaults remain source expressions.  The
        compiler deliberately does not evaluate them; the runtime owns their
        typed representation.
        """
        parameters = getattr(node, "type_params", ())
        result: list[Mapping[str, Any]] = []
        for parameter in parameters:
            if isinstance(parameter, ast.TypeVar):
                bound = getattr(parameter, "bound", None)
                result.append({
                    "kind": "TypeVar",
                    "name": parameter.name,
                    "bound": None if bound is None else ast.unparse(bound),
                    "constraints": [],
                    "default": (
                        None
                        if getattr(parameter, "default_value", None) is None
                        else ast.unparse(parameter.default_value)
                    ),
                    "span": _span(parameter),
                })
            elif isinstance(parameter, ast.TypeVarTuple):
                result.append({
                    "kind": "TypeVarTuple",
                    "name": parameter.name,
                    "default": (
                        None
                        if getattr(parameter, "default_value", None) is None
                        else ast.unparse(parameter.default_value)
                    ),
                    "span": _span(parameter),
                })
            elif isinstance(parameter, ast.ParamSpec):
                result.append({
                    "kind": "ParamSpec",
                    "name": parameter.name,
                    "default": (
                        None
                        if getattr(parameter, "default_value", None) is None
                        else ast.unparse(parameter.default_value)
                    ),
                    "span": _span(parameter),
                })
            else:
                raise CompilerError(
                    f"unsupported type parameter: {type(parameter).__name__}"
                )
        return result


    def compile_class(self, node: ast.ClassDef, qualname: str) -> str:
        builder = self._new_builder(
            node.name,
            qualname,
            "class",
            None,
            node.lineno,
            _span(node),
        )
        builder.emit("LOAD_CONST", _constant(node.name), node)
        builder.emit("STORE_NAME", "__qualname__", node)
        builder.emit("LOAD_CONST", _constant(self.module), node)
        builder.emit("STORE_NAME", "__module__", node)
        self.statements(builder, node.body)
        builder.emit("LOAD_LOCALS", node=node)
        builder.emit("RETURN", node=node)
        self.codes[builder.code_id] = builder.finish()
        return builder.code_id


    def statements(self, builder: _CodeBuilder, nodes: Sequence[ast.stmt]) -> None:
        for node in nodes:
            self.statement(builder, node)


    def statement(self, builder: _CodeBuilder, node: ast.stmt) -> None:
        if isinstance(node, ast.Pass):
            builder.emit("NOP", node=node)
        elif isinstance(node, ast.Expr):
            self.expression(builder, node.value)
            builder.emit("POP_TOP", node=node)
        elif isinstance(node, ast.Assign):
            self.expression(builder, node.value)
            for index, target in enumerate(node.targets):
                if index < len(node.targets) - 1:
                    builder.emit("DUP_TOP", node=target)
                self.store(builder, target)
        elif isinstance(node, ast.AnnAssign):
            if node.value is not None:
                self.expression(builder, node.value)
                self.store(builder, node.target)
            if node.annotation is not None and isinstance(node.target, ast.Name):
                self.annotation(builder, node.annotation)
                builder.emit("LOAD_NAME", "__annotations__", node)
                builder.emit("LOAD_CONST", _constant(node.target.id), node)
                builder.emit("STORE_SUBSCR", node=node)
        elif isinstance(node, ast.AugAssign):
            self.augmented_assignment(builder, node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                self.expression(builder, decorator)
            type_parameters = self._type_parameters(node)
            if type_parameters:
                builder.emit("BIND_TYPE_PARAMS", type_parameters, node)
            annotation_nodes: list[tuple[str, ast.expr]] = []
            for argument in [
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            ]:
                if argument.annotation is not None:
                    annotation_nodes.append((argument.arg, argument.annotation))
            if node.args.vararg is not None and node.args.vararg.annotation is not None:
                annotation_nodes.append((node.args.vararg.arg, node.args.vararg.annotation))
            if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
                annotation_nodes.append((node.args.kwarg.arg, node.args.kwarg.annotation))
            if node.returns is not None:
                annotation_nodes.append(("return", node.returns))
            for _, annotation in annotation_nodes:
                self.annotation(builder, annotation)
            for default in node.args.defaults:
                self.expression(builder, default)
            for default in node.args.kw_defaults:
                if default is not None:
                    self.expression(builder, default)
            code_id = self.compile_function(node, f"{builder.qualname}.{node.name}")
            builder.emit(
                "MAKE_FUNCTION",
                {
                    "code_id": code_id,
                    "name": node.name,
                    "defaults": len(node.args.defaults),
                    "kw_default_names": [
                        arg.arg for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
                        if default is not None
                    ],
                    "annotation_names": [name for name, _ in annotation_nodes],
                    "type_params": self._type_parameters(node),
                },
                node,
            )
            if node.decorator_list:
                builder.emit("APPLY_DECORATORS", len(node.decorator_list), node)
            builder.emit("STORE_NAME", node.name, node)
            if type_parameters:
                builder.emit("UNBIND_TYPE_PARAMS", len(type_parameters), node)
        elif isinstance(node, ast.ClassDef):
            for decorator in node.decorator_list:
                self.expression(builder, decorator)
            type_parameters = self._type_parameters(node)
            if type_parameters:
                builder.emit("BIND_TYPE_PARAMS", type_parameters, node)
            for base in node.bases:
                self.expression(builder, base)
            keyword_names: list[str | None] = []
            for keyword in node.keywords:
                keyword_names.append(keyword.arg)
                self.expression(builder, keyword.value)
            code_id = self.compile_class(node, f"{builder.qualname}.{node.name}")
            builder.emit(
                "MAKE_CLASS",
                {
                    "code_id": code_id,
                    "name": node.name,
                    "bases": len(node.bases),
                    "keyword_names": keyword_names,
                    "type_params": self._type_parameters(node),
                },
                node,
            )
            if node.decorator_list:
                builder.emit("APPLY_DECORATORS", len(node.decorator_list), node)
            builder.emit("STORE_NAME", node.name, node)
            if type_parameters:
                builder.emit("UNBIND_TYPE_PARAMS", len(type_parameters), node)
        elif isinstance(node, ast.If):
            otherwise = builder.label("if_else")
            done = builder.label("if_done")
            self.expression(builder, node.test)
            builder.jump("JUMP_IF_FALSE", otherwise, node.test)
            self.statements(builder, node.body)
            builder.jump("JUMP", done, node)
            builder.mark(otherwise)
            self.statements(builder, node.orelse)
            builder.mark(done)
        elif isinstance(node, ast.While):
            start = builder.label("while_start")
            exhausted = builder.label("while_else")
            done = builder.label("while_done")
            builder.emit("SETUP_LOOP", {"break": None, "continue": None}, node)
            setup_index = len(builder.instructions) - 1
            builder.mark(start)
            self.expression(builder, node.test)
            builder.jump("JUMP_IF_FALSE", exhausted, node.test)
            self.statements(builder, node.body)
            builder.jump("JUMP", start, node)
            builder.mark(exhausted)
            builder.emit("POP_BLOCK", node=node)
            self.statements(builder, node.orelse)
            builder.mark(done)
            builder.instructions[setup_index]["arg"] = {"break": len(builder.instructions), "continue": builder.labels[start]}
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            self.expression(builder, node.iter)
            if isinstance(node, ast.AsyncFor):
                builder.emit("GET_AITER", node=node.iter)
            else:
                builder.emit("GET_ITER", node=node.iter)
            start = builder.label("for_start")
            exhausted = builder.label("for_else")
            done = builder.label("for_done")
            builder.emit("SETUP_LOOP", {"break": None, "continue": None}, node)
            setup_index = len(builder.instructions) - 1
            builder.mark(start)
            builder.jump("ASYNC_FOR_ITER" if isinstance(node, ast.AsyncFor) else "FOR_ITER", exhausted, node)
            self.store(builder, node.target)
            self.statements(builder, node.body)
            builder.jump("JUMP", start, node)
            builder.mark(exhausted)
            builder.emit("POP_BLOCK", node=node)
            self.statements(builder, node.orelse)
            builder.mark(done)
            builder.instructions[setup_index]["arg"] = {"break": len(builder.instructions), "continue": builder.labels[start]}
        elif isinstance(node, ast.Break):
            builder.emit("SIGNAL_BREAK", node=node)
        elif isinstance(node, ast.Continue):
            builder.emit("SIGNAL_CONTINUE", node=node)
        elif isinstance(node, ast.Return):
            if node.value is None:
                builder.emit("LOAD_CONST", _constant(None), node)
            else:
                self.expression(builder, node.value)
            builder.emit("RETURN", node=node)
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                self.delete(builder, target)
        elif isinstance(node, ast.Raise):
            if node.exc is None:
                builder.emit("RERAISE", node=node)
            else:
                self.expression(builder, node.exc)
                if node.cause is not None:
                    self.expression(builder, node.cause)
                    builder.emit("RAISE_FROM", node=node)
                else:
                    builder.emit("RAISE", node=node)
        elif isinstance(node, ast.Assert):
            passed = builder.label("assert_ok")
            self.expression(builder, node.test)
            builder.jump("JUMP_IF_TRUE", passed, node.test)
            if node.msg is None:
                builder.emit("LOAD_CONST", _constant(""), node)
            else:
                self.expression(builder, node.msg)
            builder.emit("RAISE_ASSERTION", node=node)
            builder.mark(passed)
        elif isinstance(node, ast.TryStar):
            self.try_star_statement(builder, node)
        elif isinstance(node, ast.Try):
            self.try_statement(builder, node)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            self.with_statement(builder, node, asynchronous=isinstance(node, ast.AsyncWith))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                builder.emit("IMPORT_NAME", {"module": alias.name, "from": [], "level": 0}, node)
                builder.emit("STORE_NAME", alias.asname or alias.name.split(".")[0], node)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            if module == "__future__":
                supported = {
                    "annotations",
                    "generator_stop",
                    "barry_as_FLUFL",
                    "division",
                    "absolute_import",
                    "with_statement",
                    "print_function",
                    "unicode_literals",
                }
                unknown = [name for name in names if name not in supported]
                if unknown:
                    raise CompilerError(
                        f"unsupported future feature: {unknown[0]}"
                    )
                self.future_flags.update(names)
            else:
                builder.emit("IMPORT_NAME", {"module": module, "from": names, "level": node.level}, node)
                for alias in reversed(node.names):
                    if alias.name == "*":
                        builder.emit("IMPORT_STAR", node=node)
                    else:
                        builder.emit("IMPORT_FROM", alias.name, node)
                        builder.emit("STORE_NAME", alias.asname or alias.name, node)
                builder.emit("POP_TOP", node=node)
        elif isinstance(node, ast.Global):
            builder.globals.update(node.names)
        elif isinstance(node, ast.Nonlocal):
            builder.nonlocals.update(node.names)
        elif isinstance(node, ast.Match):
            self.match_statement(builder, node)
        else:
            raise CompilerError(f"unsupported statement: {type(node).__name__}")

    def try_star_statement(self, builder: _CodeBuilder, node: ast.TryStar) -> None:
        if node.finalbody:
            final = builder.label("finally")
            done = builder.label("finally_done")
            builder.jump("SETUP_FINALLY", final, node)
            surrogate = ast.TryStar(
                body=node.body,
                handlers=node.handlers,
                orelse=node.orelse,
                finalbody=[],
            )
            ast.copy_location(surrogate, node)
            self.try_star_statement(builder, surrogate)
            builder.emit("POP_BLOCK", node=node)
            index = builder.emit("ENTER_FINALLY", {"target": None}, node)
            builder.patches.append((index, done, "target"))
            builder.jump("JUMP", final, node)
            builder.mark(final)
            self.statements(builder, node.finalbody)
            builder.emit("END_FINALLY", node=node)
            builder.mark(done)
            return
        if not node.handlers:
            self.statements(builder, node.body)
            self.statements(builder, node.orelse)
            return
        handler = builder.label("except_star")
        done = builder.label("try_star_done")
        builder.jump("SETUP_EXCEPT_STAR", handler, node)
        self.statements(builder, node.body)
        builder.emit("POP_BLOCK", node=node)
        self.statements(builder, node.orelse)
        builder.jump("JUMP", done, node)
        builder.mark(handler)
        builder.emit("EXCEPT_STAR_BEGIN", node=node)
        for item in node.handlers:
            if item.type is None:
                raise CompilerError("except* requires an exception type")
            next_handler = builder.label("except_star_next")
            self.expression(builder, item.type)
            builder.emit("EXCEPT_STAR_SPLIT", node=item)
            builder.jump("JUMP_IF_FALSE", next_handler, item)
            if item.name:
                builder.emit("LOAD_CURRENT_EXCEPTION", node=item)
                builder.emit("STORE_NAME", item.name, item)
            self.statements(builder, item.body)
            if item.name:
                builder.emit("DELETE_NAME_IF_PRESENT", item.name, item)
            builder.emit("POP_EXCEPT_STAR_CLAUSE", node=item)
            builder.mark(next_handler)
        end_index = builder.emit("EXCEPT_STAR_END", {"target": None}, node)
        builder.patches.append((end_index, done, "target"))
        builder.mark(done)

    def try_statement(self, builder: _CodeBuilder, node: ast.Try | ast.TryStar) -> None:
        if node.finalbody:
            final = builder.label("finally")
            done = builder.label("finally_done")
            builder.jump("SETUP_FINALLY", final, node)
            surrogate = ast.Try(body=node.body, handlers=node.handlers, orelse=node.orelse, finalbody=[])
            ast.copy_location(surrogate, node)
            self.try_statement(builder, surrogate)
            builder.emit("POP_BLOCK", node=node)
            index = builder.emit("ENTER_FINALLY", {"target": None}, node)
            builder.patches.append((index, done, "target"))
            builder.jump("JUMP", final, node)
            builder.mark(final)
            self.statements(builder, node.finalbody)
            builder.emit("END_FINALLY", node=node)
            builder.mark(done)
            return
        if not node.handlers:
            self.statements(builder, node.body)
            self.statements(builder, node.orelse)
            return
        handler = builder.label("except")
        done = builder.label("try_done")
        builder.jump("SETUP_EXCEPT", handler, node)
        self.statements(builder, node.body)
        builder.emit("POP_BLOCK", node=node)
        self.statements(builder, node.orelse)
        builder.jump("JUMP", done, node)
        builder.mark(handler)
        for item in node.handlers:
            next_handler = builder.label("except_next")
            if item.type is not None:
                builder.emit("LOAD_CURRENT_EXCEPTION", node=item)
                self.expression(builder, item.type)
                builder.emit("EXCEPTION_MATCH", node=item)
                builder.jump("JUMP_IF_FALSE", next_handler, item)
            if item.name:
                builder.emit("LOAD_CURRENT_EXCEPTION", node=item)
                builder.emit("STORE_NAME", item.name, item)
            self.statements(builder, item.body)
            if item.name:
                builder.emit("DELETE_NAME_IF_PRESENT", item.name, item)
            builder.emit("POP_EXCEPT", node=item)
            builder.jump("JUMP", done, item)
            builder.mark(next_handler)
        builder.emit("RERAISE", node=node)
        builder.mark(done)

    def with_statement(self, builder: _CodeBuilder, node: ast.With | ast.AsyncWith, *, asynchronous: bool) -> None:
        if len(node.items) > 1:
            nested: ast.With | ast.AsyncWith
            cls = ast.AsyncWith if asynchronous else ast.With
            nested = cls(items=node.items[1:], body=node.body, type_comment=getattr(node, "type_comment", None))
            ast.copy_location(nested, node)
            outer = cls(items=node.items[:1], body=[nested], type_comment=getattr(node, "type_comment", None))
            ast.copy_location(outer, node)
            self.with_statement(builder, outer, asynchronous=asynchronous)
            return
        item = node.items[0]
        done = builder.label("with_done")
        self.expression(builder, item.context_expr)
        enter_index = builder.emit(
            "WITH_ENTER_ASYNC" if asynchronous else "WITH_ENTER",
            {"target": None},
            item.context_expr,
        )
        builder.patches.append((enter_index, done, "target"))
        if item.optional_vars is None:
            builder.emit("POP_TOP", node=item.context_expr)
        else:
            self.store(builder, item.optional_vars)
        self.statements(builder, node.body)
        builder.emit("WITH_EXIT_NORMAL_ASYNC" if asynchronous else "WITH_EXIT_NORMAL", node=node)
        builder.mark(done)

    def match_statement(self, builder: _CodeBuilder, node: ast.Match) -> None:
        subject = builder.temp("match")
        self.expression(builder, node.subject)
        builder.emit("STORE_NAME", subject, node.subject)
        done = builder.label("match_done")
        for case in node.cases:
            next_case = builder.label("match_next")
            builder.emit("LOAD_NAME", subject, node)
            builder.emit("MATCH_PATTERN", _pattern(case.pattern), case.pattern)
            builder.jump("JUMP_IF_NONE", next_case, case.pattern)
            builder.emit("BIND_MATCH", node=case.pattern)
            if case.guard is not None:
                self.expression(builder, case.guard)
                builder.jump("JUMP_IF_FALSE", next_case, case.guard)
            self.statements(builder, case.body)
            builder.jump("JUMP", done, case.pattern)
            builder.mark(next_case)
        builder.mark(done)
        builder.emit("DELETE_NAME_IF_PRESENT", subject, node)

    def augmented_assignment(self, builder: _CodeBuilder, node: ast.AugAssign) -> None:
        op = _BINARY.get(type(node.op))
        if op is None:
            raise CompilerError("unsupported augmented assignment operator")
        target = node.target
        if isinstance(target, ast.Name):
            builder.emit("LOAD_NAME", target.id, target)
            self.expression(builder, node.value)
            builder.emit("INPLACE", op, node)
            builder.emit("STORE_NAME", target.id, target)
        elif isinstance(target, ast.Attribute):
            self.expression(builder, target.value)
            builder.emit("DUP_TOP", node=target)
            builder.emit("LOAD_ATTR", target.attr, target)
            self.expression(builder, node.value)
            builder.emit("INPLACE", op, node)
            builder.emit("STORE_ATTR_AUG", target.attr, target)
        elif isinstance(target, ast.Subscript):
            self.expression(builder, target.value)
            self.expression(builder, target.slice)
            builder.emit("DUP_PAIR", node=target)
            builder.emit("LOAD_SUBSCR", node=target)
            self.expression(builder, node.value)
            builder.emit("INPLACE", op, node)
            builder.emit("STORE_SUBSCR_AUG", node=target)
        else:
            raise CompilerError("unsupported augmented assignment target")

    def store(self, builder: _CodeBuilder, target: ast.expr) -> None:
        if isinstance(target, ast.Name):
            builder.emit("STORE_NAME", target.id, target)
        elif isinstance(target, ast.Attribute):
            self.expression(builder, target.value)
            builder.emit("STORE_ATTR", target.attr, target)
        elif isinstance(target, ast.Subscript):
            self.expression(builder, target.value)
            self.expression(builder, target.slice)
            builder.emit("STORE_SUBSCR", node=target)
        elif isinstance(target, (ast.Tuple, ast.List)):
            starred = [index for index, item in enumerate(target.elts) if isinstance(item, ast.Starred)]
            if len(starred) > 1:
                raise CompilerError("multiple starred assignment targets")
            builder.emit("UNPACK", {"count": len(target.elts), "star": None if not starred else starred[0]}, target)
            for item in reversed(target.elts):
                self.store(builder, item.value if isinstance(item, ast.Starred) else item)
        elif isinstance(target, ast.Starred):
            self.store(builder, target.value)
        else:
            raise CompilerError(f"unsupported assignment target: {type(target).__name__}")

    def delete(self, builder: _CodeBuilder, target: ast.expr) -> None:
        if isinstance(target, ast.Name):
            builder.emit("DELETE_NAME", target.id, target)
        elif isinstance(target, ast.Attribute):
            self.expression(builder, target.value)
            builder.emit("DELETE_ATTR", target.attr, target)
        elif isinstance(target, ast.Subscript):
            self.expression(builder, target.value)
            self.expression(builder, target.slice)
            builder.emit("DELETE_SUBSCR", node=target)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self.delete(builder, item)
        else:
            raise CompilerError(f"unsupported deletion target: {type(target).__name__}")

    def expression(self, builder: _CodeBuilder, node: ast.expr) -> None:
        if isinstance(node, ast.Constant):
            builder.emit("LOAD_CONST", _constant(node.value), node)
        elif isinstance(node, ast.Name):
            builder.emit("LOAD_NAME", node.id, node)
        elif isinstance(node, ast.Attribute):
            self.expression(builder, node.value)
            builder.emit("LOAD_ATTR", node.attr, node)
        elif isinstance(node, ast.Subscript):
            self.expression(builder, node.value)
            self.expression(builder, node.slice)
            builder.emit("LOAD_SUBSCR", node=node)
        elif isinstance(node, ast.Slice):
            for value in (node.lower, node.upper, node.step):
                if value is None:
                    builder.emit("LOAD_CONST", _constant(None), node)
                else:
                    self.expression(builder, value)
            builder.emit("BUILD_SLICE", 3, node)
        elif isinstance(node, ast.BinOp):
            self.expression(builder, node.left)
            self.expression(builder, node.right)
            op = _BINARY.get(type(node.op))
            if op is None:
                raise CompilerError("unsupported binary operator")
            builder.emit("BINARY", op, node)
        elif isinstance(node, ast.UnaryOp):
            self.expression(builder, node.operand)
            op = _UNARY.get(type(node.op))
            if op is None:
                raise CompilerError("unsupported unary operator")
            builder.emit("UNARY", op, node)
        elif isinstance(node, ast.BoolOp):
            done = builder.label("bool_done")
            for value in node.values[:-1]:
                self.expression(builder, value)
                builder.jump("JUMP_IF_TRUE_OR_POP" if isinstance(node.op, ast.Or) else "JUMP_IF_FALSE_OR_POP", done, value)
            self.expression(builder, node.values[-1])
            builder.mark(done)
        elif isinstance(node, ast.Compare):
            self.expression(builder, node.left)
            done = builder.label("compare_done")
            for index, (operator, comparator) in enumerate(zip(node.ops, node.comparators)):
                self.expression(builder, comparator)
                op = _COMPARE.get(type(operator))
                if op is None:
                    raise CompilerError("unsupported comparison operator")
                if index < len(node.ops) - 1:
                    builder.emit("COMPARE_CHAIN", op, node)
                    builder.jump("CHAIN_GUARD", done, node)
                else:
                    builder.emit("COMPARE", op, node)
            builder.mark(done)
        elif isinstance(node, ast.IfExp):
            otherwise = builder.label("ifexp_else")
            done = builder.label("ifexp_done")
            self.expression(builder, node.test)
            builder.jump("JUMP_IF_FALSE", otherwise, node.test)
            self.expression(builder, node.body)
            builder.jump("JUMP", done, node)
            builder.mark(otherwise)
            self.expression(builder, node.orelse)
            builder.mark(done)
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            descriptors: list[str] = []
            for item in node.elts:
                if isinstance(item, ast.Starred):
                    self.expression(builder, item.value)
                    descriptors.append("star")
                else:
                    self.expression(builder, item)
                    descriptors.append("item")
            kind = "list" if isinstance(node, ast.List) else "tuple" if isinstance(node, ast.Tuple) else "set"
            builder.emit("BUILD_COLLECTION", {"kind": kind, "items": descriptors}, node)
        elif isinstance(node, ast.Dict):
            descriptors: list[str] = []
            for key, value in zip(node.keys, node.values):
                if key is None:
                    self.expression(builder, value)
                    descriptors.append("mapping")
                else:
                    self.expression(builder, key)
                    self.expression(builder, value)
                    descriptors.append("pair")
            builder.emit("BUILD_MAP", descriptors, node)
        elif isinstance(node, ast.Call):
            self.expression(builder, node.func)
            descriptors: list[Mapping[str, Any]] = []
            for argument in node.args:
                if isinstance(argument, ast.Starred):
                    self.expression(builder, argument.value)
                    descriptors.append({"kind": "star"})
                else:
                    self.expression(builder, argument)
                    descriptors.append({"kind": "positional"})
            for keyword in node.keywords:
                self.expression(builder, keyword.value)
                descriptors.append({"kind": "mapping" if keyword.arg is None else "keyword", "name": keyword.arg})
            builder.emit("CALL", descriptors, node)
        elif isinstance(node, ast.Lambda):
            code_id = self.compile_function(node, f"{builder.qualname}.<lambda>")
            for default in node.args.defaults:
                self.expression(builder, default)
            for default in node.args.kw_defaults:
                if default is not None:
                    self.expression(builder, default)
            builder.emit(
                "MAKE_FUNCTION",
                {
                    "code_id": code_id,
                    "name": "<lambda>",
                    "defaults": len(node.args.defaults),
                    "kw_default_names": [arg.arg for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults) if default is not None],
                    "type_params": [],
                },
                node,
            )
        elif isinstance(node, ast.NamedExpr):
            self.expression(builder, node.value)
            builder.emit("DUP_TOP", node=node)
            self.store(builder, node.target)
        elif isinstance(node, ast.Yield):
            if node.value is None:
                builder.emit("LOAD_CONST", _constant(None), node)
            else:
                self.expression(builder, node.value)
            builder.emit("YIELD", node=node)
        elif isinstance(node, ast.YieldFrom):
            self.expression(builder, node.value)
            builder.emit("YIELD_FROM", node=node)
        elif isinstance(node, ast.Await):
            self.expression(builder, node.value)
            builder.emit("AWAIT", node=node)
        elif isinstance(node, ast.JoinedStr):
            for item in node.values:
                self.expression(builder, item)
            builder.emit("BUILD_STRING", len(node.values), node)
        elif isinstance(node, ast.FormattedValue):
            self.expression(builder, node.value)
            if node.format_spec is not None:
                self.expression(builder, node.format_spec)
            builder.emit("FORMAT_VALUE", {"conversion": node.conversion, "has_spec": node.format_spec is not None}, node)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            self.comprehension(builder, node)
        else:
            raise CompilerError(f"unsupported expression: {type(node).__name__}")

    def comprehension(self, builder: _CodeBuilder, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> None:
        name = "<genexpr>" if isinstance(node, ast.GeneratorExp) else "<comprehension>"
        child = self._new_builder(name, f"{builder.qualname}.{name}", "function", {
            "posonly": [], "positional": [], "vararg": None,
            "kwonly": [], "kwarg": None, "defaults": 0, "kw_defaults": [],
        }, int(getattr(node, "lineno", 1)), _span(node))
        if isinstance(node, ast.GeneratorExp):
            child.flags.add("generator")
            result_name = None
        else:
            result_name = child.temp("result")
            kind = "dict" if isinstance(node, ast.DictComp) else "set" if isinstance(node, ast.SetComp) else "list"
            child.emit("BUILD_COLLECTION", {"kind": kind, "items": []}, node)
            child.emit("STORE_NAME", result_name, node)

        def level(index: int) -> None:
            generator = node.generators[index]
            self.expression(child, generator.iter)
            child.emit("GET_AITER" if generator.is_async else "GET_ITER", node=generator.iter)
            start = child.label("comp_loop")
            end = child.label("comp_end")
            child.mark(start)
            child.jump("ASYNC_FOR_ITER" if generator.is_async else "FOR_ITER", end, generator.iter)
            self.store(child, generator.target)
            for condition in generator.ifs:
                self.expression(child, condition)
                child.jump("JUMP_IF_FALSE", start, condition)
            if index + 1 < len(node.generators):
                level(index + 1)
            else:
                if isinstance(node, ast.GeneratorExp):
                    self.expression(child, node.elt)
                    child.emit("YIELD", node=node.elt)
                    child.emit("POP_TOP", node=node.elt)
                elif isinstance(node, ast.DictComp):
                    child.emit("LOAD_NAME", result_name, node)
                    self.expression(child, node.key)
                    self.expression(child, node.value)
                    child.emit("MAP_SET", node=node)
                else:
                    child.emit("LOAD_NAME", result_name, node)
                    self.expression(child, node.elt)
                    child.emit("COLLECTION_ADD", node=node)
            child.jump("JUMP", start, generator.iter)
            child.mark(end)

        level(0)
        if result_name is None:
            child.emit("LOAD_CONST", _constant(None), node)
        else:
            child.emit("LOAD_NAME", result_name, node)
        child.emit("RETURN", node=node)
        self.codes[child.code_id] = child.finish()
        builder.emit("MAKE_FUNCTION", {"code_id": child.code_id, "name": name, "defaults": 0, "kw_default_names": []}, node)
        builder.emit("CALL", [], node)


def compile_python(
    source: str,
    *,
    source_name: str = "<field>",
    module: str = "__main__",
    package: str | None = None,
    mode: str = "exec",
    program_id: str | None = None,
    version: int = 1,
    dependencies: Sequence[str] = (),
    capability_requirements: Sequence[str] = (),
    max_source_bytes: int = 1_048_576,
    max_nodes: int = 100_000,
) -> PythonProgram:
    """Parse and lower source into immutable field instructions.

    Parsing and lowering are bounded bootstrap work.  The returned record is
    suitable for storing directly in a regional task state.
    """
    if not isinstance(source, str):
        raise CompilerError("source must be text")
    encoded = source.encode("utf-8")
    if len(encoded) > max_source_bytes:
        raise CompilerError("source exceeds the compiler byte bound")
    if mode not in {"exec", "eval", "single"}:
        raise CompilerError("compile mode is invalid")
    try:
        tree = ast.parse(source, filename=source_name, mode=mode, type_comments=True)
    except SyntaxError as exc:
        raise CompilerError(
            f"{exc.msg} at {source_name}:{exc.lineno}:{exc.offset}"
        ) from exc
    source_sha256 = hashlib.sha256(encoded).hexdigest()
    node_count = sum(1 for _ in ast.walk(tree))
    if node_count > max_nodes:
        raise CompilerError("source exceeds the compiler node bound")
    compiler = _Compiler(
        source_name=source_name,
        module=module,
        source_sha256=source_sha256,
    )
    entry = compiler.compile_root(tree, mode)
    code = {
        "schema": "cassifi.python-ir.v1",
        "entry": entry,
        "codes": compiler.codes,
        "source_name": source_name,
        "module": module,
        "node_count": node_count,
    }
    source_map = {
        code_id: {
            str(index): instruction.get("span")
            for index, instruction in enumerate(record["instructions"])
            if "span" in instruction
        }
        for code_id, record in compiler.codes.items()
    }
    resolved_id = program_id or f"python:{module}:{source_sha256[:16]}"
    return PythonProgram(
        program_id=resolved_id,
        version=version,
        source_sha256=source_sha256,
        source_name=source_name,
        module=module,
        package=package,
        mode=mode,
        future_flags=tuple(sorted(compiler.future_flags)),
        dependencies=tuple(dependencies),
        capability_requirements=tuple(capability_requirements),
        code=code,
        source_map=source_map,
    )


__all__ = ["CompilerError", "compile_python"]
