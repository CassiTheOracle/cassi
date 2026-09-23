# cassi_python_universal.py
# Universal Python Interpreter (Static AST Analysis)

import ast
import dataclasses
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class RuntimeBoundaryKind(Enum):
    OPEN = "open"
    EVAL = "eval"
    EXEC = "exec"
    GETATTR = "getattr"


@dataclass
class Binding:
    name: str
    scope_id: str
    kind: str  # 'local', 'global', 'builtin', 'import', 'param', 'closure'
    line: int


@dataclass
class CallSite:
    name: str
    args: List[str]
    kwargs: Dict[str, str]
    line: int


@dataclass
class Effect:
    kind: str  # 'assign', 'delete', 'import', 'print', 'raise', 'return', 'yield'
    target: Optional[str]
    line: int


@dataclass
class RuntimeBoundary:
    kind: RuntimeBoundaryKind
    name: str
    line: int


@dataclass
class InterpretResult:
    syntax_error: Optional[str]
    bindings: List[Binding]
    call_sites: List[CallSite]
    effects: List[Effect]
    runtime_boundaries: List[RuntimeBoundary]
    unknowns: List[str]
    cfg_nodes: List[str]
    cfg_edges: List[tuple]

    def to_json(self) -> str:
        def _encode(obj):
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, (list, tuple)):
                return [_encode(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _encode(v) for k, v in obj.items()}
            if isinstance(obj, (str, int, float, bool)) or obj is None:
                return obj
            if dataclasses.is_dataclass(obj):
                return asdict(obj)
            return str(obj)

        return json.dumps(_encode(self), indent=2)


class OwnerCognitionInterface:
    def __init__(self, store, reopen):
        self._store = store
        self._reopen = reopen

    def persist(self, key: str, value: str):
        self._store(key, value)

    def reopen(self, key: str) -> Optional[str]:
        return self._reopen(key)


class UniversalInterpreter:
    def __init__(self, cognition: Optional[OwnerCognitionInterface] = None):
        self.cognition = cognition
        self.bindings: List[Binding] = []
        self.call_sites: List[CallSite] = []
        self.effects: List[Effect] = []
        self.runtime_boundaries: List[RuntimeBoundary] = []
        self.unknowns: List[str] = []
        self.cfg_nodes: List[str] = []
        self.cfg_edges: List[tuple] = []
        self.scope_stack: List[str] = []
        self.current_scope = "global"

    def interpret(self, source: str) -> InterpretResult:
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return InterpretResult(
                syntax_error=str(e),
                bindings=[],
                call_sites=[],
                effects=[],
                runtime_boundaries=[],
                unknowns=[],
                cfg_nodes=[],
                cfg_edges=[]
            )

        self._reset()
        self._visit(tree, "global")

        result = InterpretResult(
            syntax_error=None,
            bindings=self.bindings,
            call_sites=self.call_sites,
            effects=self.effects,
            runtime_boundaries=self.runtime_boundaries,
            unknowns=self.unknowns,
            cfg_nodes=self.cfg_nodes,
            cfg_edges=self.cfg_edges
        )

        if self.cognition:
            self.cognition.persist("last_result", result.to_json())

        return result

    def reopen(self) -> Optional[InterpretResult]:
        """Reconstruct the last InterpretResult from the injected cognition callback.

        Reads the stored JSON under the key 'last_result' through the
        OwnerCognitionInterface.reopen callback. Returns a fully reconstructed
        InterpretResult (with real dataclass records, Enum values, and CFG
        tuples) when a stored value is present, or None when the callback
        returns no stored value.
        """
        if self.cognition is None:
            return None

        stored = self.cognition.reopen("last_result")
        if stored is None:
            return None

        try:
            raw = json.loads(stored)
        except (json.JSONDecodeError, TypeError):
            return None

        if not isinstance(raw, dict):
            return None

        syntax_error = raw.get("syntax_error")

        bindings = []
        for item in raw.get("bindings", []):
            if isinstance(item, dict):
                bindings.append(Binding(
                    name=item.get("name", ""),
                    scope_id=item.get("scope_id", ""),
                    kind=item.get("kind", ""),
                    line=item.get("line", 0)
                ))

        call_sites = []
        for item in raw.get("call_sites", []):
            if isinstance(item, dict):
                call_sites.append(CallSite(
                    name=item.get("name", ""),
                    args=list(item.get("args", [])),
                    kwargs=dict(item.get("kwargs", {})),
                    line=item.get("line", 0)
                ))

        effects = []
        for item in raw.get("effects", []):
            if isinstance(item, dict):
                effects.append(Effect(
                    kind=item.get("kind", ""),
                    target=item.get("target"),
                    line=item.get("line", 0)
                ))

        runtime_boundaries = []
        for item in raw.get("runtime_boundaries", []):
            if isinstance(item, dict):
                kind_value = item.get("kind", "")
                # Map the stored string back to the RuntimeBoundaryKind enum
                try:
                    kind_enum = RuntimeBoundaryKind(kind_value)
                except ValueError:
                    kind_enum = RuntimeBoundaryKind.OPEN
                runtime_boundaries.append(RuntimeBoundary(
                    kind=kind_enum,
                    name=item.get("name", ""),
                    line=item.get("line", 0)
                ))

        unknowns = list(raw.get("unknowns", []))

        cfg_nodes = list(raw.get("cfg_nodes", []))

        cfg_edges = []
        for edge in raw.get("cfg_edges", []):
            if isinstance(edge, list):
                cfg_edges.append(tuple(edge))
            elif isinstance(edge, tuple):
                cfg_edges.append(edge)

        return InterpretResult(
            syntax_error=syntax_error,
            bindings=bindings,
            call_sites=call_sites,
            effects=effects,
            runtime_boundaries=runtime_boundaries,
            unknowns=unknowns,
            cfg_nodes=cfg_nodes,
            cfg_edges=cfg_edges
        )

    def _reset(self):
        self.bindings = []
        self.call_sites = []
        self.effects = []
        self.runtime_boundaries = []
        self.unknowns = []
        self.cfg_nodes = []
        self.cfg_edges = []
        self.scope_stack = []
        self.current_scope = "global"

    def _visit(self, node: ast.AST, scope: str):
        if isinstance(node, ast.Module):
            self.cfg_nodes.append("entry")
            for stmt in node.body:
                self._visit(stmt, scope)
            self.cfg_nodes.append("exit")
            return

        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
            new_scope = f"{scope}.{node.name}"
            self.scope_stack.append(scope)
            self.current_scope = new_scope
            self.bindings.append(Binding(name=node.name, scope_id=scope, kind="function" if isinstance(node, ast.FunctionDef) else "class", line=node.lineno))
            for stmt in node.body:
                self._visit(stmt, new_scope)
            self.scope_stack.pop()
            self.current_scope = scope
            return

        if isinstance(node, ast.Lambda):
            new_scope = f"{scope}.lambda"
            self.scope_stack.append(scope)
            self.current_scope = new_scope
            self._visit(node.body, new_scope)
            self.scope_stack.pop()
            self.current_scope = scope
            return

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.bindings.append(Binding(name=target.id, scope_id=self.current_scope, kind="local", line=node.lineno))
                    self.effects.append(Effect(kind="assign", target=target.id, line=node.lineno))
            self._visit(node.value, self.current_scope)
            return

        if isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.effects.append(Effect(kind="delete", target=target.id, line=node.lineno))
            return

        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            else:
                name = "<unknown>"

            args = [self._expr_to_str(a) for a in node.args]
            kwargs = {kw.arg: self._expr_to_str(kw.value) for kw in node.keywords if kw.arg}

            self.call_sites.append(CallSite(name=name, args=args, kwargs=kwargs, line=node.lineno))

            if name in ("open", "eval", "exec", "getattr"):
                kind_map = {"open": RuntimeBoundaryKind.OPEN, "eval": RuntimeBoundaryKind.EVAL, "exec": RuntimeBoundaryKind.EXEC, "getattr": RuntimeBoundaryKind.GETATTR}
                self.runtime_boundaries.append(RuntimeBoundary(kind=kind_map[name], name=name, line=node.lineno))

            for arg in node.args:
                self._visit(arg, self.current_scope)
            for kw in node.keywords:
                self._visit(kw.value, self.current_scope)
            return

        if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            self.effects.append(Effect(kind="import", target=None, line=node.lineno))
            return

        if isinstance(node, ast.If):
            self.cfg_nodes.append(f"if_{node.lineno}")
            self._visit(node.test, self.current_scope)
            for stmt in node.body:
                self._visit(stmt, self.current_scope)
            for stmt in node.orelse:
                self._visit(stmt, self.current_scope)
            return

        if isinstance(node, ast.For) or isinstance(node, ast.While):
            self.cfg_nodes.append(f"loop_{node.lineno}")
            self._visit(node.test if hasattr(node, 'test') else node.iter, self.current_scope)
            for stmt in node.body:
                self._visit(stmt, self.current_scope)
            return

        if isinstance(node, ast.Try):
            self.cfg_nodes.append(f"try_{node.lineno}")
            for stmt in node.body:
                self._visit(stmt, self.current_scope)
            for handler in node.handlers:
                for stmt in handler.body:
                    self._visit(stmt, self.current_scope)
            return

        if isinstance(node, ast.Expr):
            self._visit(node.value, self.current_scope)
            return

        if isinstance(node, ast.Name):
            return

        # Generic traversal for unknown nodes
        for child in ast.iter_child_nodes(node):
            self._visit(child, self.current_scope)

    def _expr_to_str(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Constant):
            return str(node.value)
        return "<expr>"
