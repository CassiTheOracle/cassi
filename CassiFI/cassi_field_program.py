"""Compile a small deterministic structured language to the field computer.

The frontend is a fixed codec, not an adaptive executor. Runtime state remains
inside :mod:`cassi_field_computer`. Functions and bounded ``repeat`` forms are
expanded at compile time; ``while_acc`` loops are bounded by the machine's
explicit ``max_steps`` profile. Byte arithmetic is exact modulo 256 and lowers
to the existing six-instruction vocabulary rather than extending the machine.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence, cast

from cassi_field_computer import (
    BRANCH,
    EMPTY,
    HALT,
    JUMP,
    POP,
    PROPAGATE,
    PUSH,
    PUSH_ACC,
    ComputerProfile,
    _advance_propagation_frame,
)
from cassi_field_regions import KernelResult, canonical_program

SCHEMA = "cassifi.structured-field-program.v1"
COMPILED_SCHEMA = "cassifi.compiled-structured-field-program.v1"
_MAX_SOURCE_NODES = 4096
REGIONAL_SOURCE_SCHEMA = "cassifi.regional-program-source.v1"
COMPILED_REGIONAL_SCHEMA = "cassifi.compiled-regional-program.v1"
SCALAR_REGIONAL_KERNEL = "scalar-computer"
SCALAR_REGIONAL_MAX_WORK = 4_096
SCALAR_REGIONAL_STATE_SCHEMA = "cassifi.regional-scalar-state.v1"
SCALAR_PROCEDURE_SCHEMA = "cassifi.regional-scalar-procedures.v1"
SCALAR_PROCEDURE_KERNEL = "learning.scalar-procedure"
SCALAR_SPECIALIZATION_MAX_BLOCK = 32

SEMANTIC_PROGRAM_SCHEMA = "cassifi.semantic-program-payload.v1"
SEMANTIC_REPRESENTATION_SCHEMA = "cassifi.semantic-representation.v1"
SEMANTIC_SEQUENCE_SCHEMA = "cassifi.semantic-sequence-program.v1"
NULLABLE_TABLE_SCHEMA = "cassifi.nullable-table.v1"
SURFACE_PROCEDURE_SCHEMA = "cassifi.surface-procedure.v1"
_SURFACE_VALUE_TYPES = frozenset(
    {"boolean", "integer", "json", "list", "mapping", "number", "string"}
)
_SURFACE_CONDITION_OPS = frozenset(
    {"eq", "ge", "gt", "in", "le", "lt", "missing", "ne", "not-in", "exists"}
)


def _canonical_surface_conditions(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > _CONDITIONAL_MAX_BRANCHES:
        raise FieldProgramError(f"{label} must be a bounded list")
    result: list[dict[str, Any]] = []
    for condition in value:
        if not isinstance(condition, Mapping):
            raise FieldProgramError(f"{label} contains an invalid condition")
        operation = condition.get("op", "eq")
        if not isinstance(operation, str):
            raise FieldProgramError(f"{label} contains an invalid condition")
        required = {"op", "path"} if operation in {"exists", "missing"} else {
            "op",
            "path",
            "value",
        }
        if set(condition) != required or operation not in _SURFACE_CONDITION_OPS:
            raise FieldProgramError(f"{label} contains an invalid condition")
        path = condition.get("path")
        if (
            not isinstance(path, str)
            or not path
            or len(path.encode("utf-8")) > 1024
        ):
            raise FieldProgramError(f"{label} condition path is invalid")
        row: dict[str, Any] = {"op": operation, "path": path}
        if operation not in {"exists", "missing"}:
            row["value"] = _semantic_program_plain(
                condition["value"], f"{label} condition value"
            )
        result.append(row)
    return result


def _canonical_surface_control(
    value: Any,
    *,
    depth: int,
    counter: list[int],
    bounds: Mapping[str, Any],
) -> dict[str, Any]:
    counter[0] += 1
    if depth > _SEQUENCE_MAX_AST_DEPTH or counter[0] > min(
        int(bounds["max_work"]), _MAX_SOURCE_NODES
    ):
        raise FieldProgramError("surface procedure control exceeds its bound")
    if not isinstance(value, Mapping) or not isinstance(value.get("op"), str):
        raise FieldProgramError("surface procedure control node is invalid")
    op = value["op"]
    if op == "sequence":
        if set(value) != {"op", "steps"} or not isinstance(value["steps"], list):
            raise FieldProgramError("surface procedure sequence is invalid")
        if not value["steps"] or len(value["steps"]) > int(bounds["max_horizon"]):
            raise FieldProgramError("surface procedure sequence exceeds its bound")
        return {
            "op": op,
            "steps": [
                _canonical_surface_control(
                    step, depth=depth + 1, counter=counter, bounds=bounds
                )
                for step in value["steps"]
            ],
        }
    if op == "choice":
        if set(value) - {"branches", "default", "op"} or not isinstance(
            value.get("branches"), list
        ):
            raise FieldProgramError("surface procedure choice is invalid")
        branches = value["branches"]
        if not branches or len(branches) > int(bounds["max_branches"]):
            raise FieldProgramError("surface procedure choice exceeds its bound")
        canonical_branches = []
        for branch in branches:
            if (
                not isinstance(branch, Mapping)
                or set(branch) != {"then", "when"}
            ):
                raise FieldProgramError("surface procedure choice branch is invalid")
            conditions = _canonical_surface_conditions(
                branch["when"], "surface procedure choice conditions"
            )
            if not conditions:
                raise FieldProgramError("surface procedure choice guard is empty")
            canonical_branches.append(
                {
                    "then": _canonical_surface_control(
                        branch["then"],
                        depth=depth + 1,
                        counter=counter,
                        bounds=bounds,
                    ),
                    "when": conditions,
                }
            )
        result = {"branches": canonical_branches, "op": op}
        if "default" in value:
            result["default"] = _canonical_surface_control(
                value["default"],
                depth=depth + 1,
                counter=counter,
                bounds=bounds,
            )
        return result
    if op == "loop":
        if set(value) != {"body", "max_iterations", "op", "while"}:
            raise FieldProgramError("surface procedure loop is invalid")
        conditions = _canonical_surface_conditions(
            value["while"], "surface procedure loop condition"
        )
        if not conditions:
            raise FieldProgramError("surface procedure loop condition is empty")
        return {
            "body": _canonical_surface_control(
                value["body"], depth=depth + 1, counter=counter, bounds=bounds
            ),
            "max_iterations": _integer(
                value["max_iterations"],
                "surface procedure loop maximum",
                minimum=1,
                maximum=int(bounds["max_horizon"]),
            ),
            "op": op,
            "while": conditions,
        }
    if op == "wait":
        if set(value) - {"op", "timeout_ns", "until"} or "until" not in value:
            raise FieldProgramError("surface procedure wait is invalid")
        conditions = _canonical_surface_conditions(
            value["until"], "surface procedure wait condition"
        )
        if not conditions:
            raise FieldProgramError("surface procedure wait condition is empty")
        result = {"op": op, "until": conditions}
        if "timeout_ns" in value:
            result["timeout_ns"] = _integer(
                value["timeout_ns"],
                "surface procedure wait timeout",
                minimum=1,
                maximum=9_007_199_254_740_991,
            )
        return result
    if op == "parallel":
        if set(value) != {"branches", "join", "op"} or value["join"] != "all":
            raise FieldProgramError("surface procedure parallel join is invalid")
        branches = value["branches"]
        if (
            not isinstance(branches, list)
            or not 2 <= len(branches) <= int(bounds["max_branches"])
        ):
            raise FieldProgramError("surface procedure parallel branches are invalid")
        return {
            "branches": [
                _canonical_surface_control(
                    branch, depth=depth + 1, counter=counter, bounds=bounds
                )
                for branch in branches
            ],
            "join": "all",
            "op": op,
        }
    if op == "intent":
        if set(value) != {"expected_effect", "op", "operation", "payload"}:
            raise FieldProgramError("surface procedure intent is invalid")
        operation = value["operation"]
        if not isinstance(operation, str) or not operation:
            raise FieldProgramError("surface procedure operation is invalid")
        payload = _semantic_program_plain(
            value["payload"], "surface procedure intent payload"
        )
        expected_effect = value["expected_effect"]
        if (
            not isinstance(payload, Mapping)
            or not isinstance(expected_effect, Mapping)
            or not expected_effect
            or any(not isinstance(path, str) or not path for path in expected_effect)
        ):
            raise FieldProgramError(
                "surface procedure intent payload or effect is invalid"
            )
        return {
            "expected_effect": _semantic_program_plain(
                dict(expected_effect), "surface procedure expected effect"
            ),
            "op": op,
            "operation": _semantic_program_identifier(
                operation, "surface procedure operation"
            ),
            "payload": dict(payload),
        }
    if op == "stop":
        if set(value) - {"op", "reason", "when"} or "reason" not in value:
            raise FieldProgramError("surface procedure stop is invalid")
        reason = _semantic_program_identifier(value["reason"], "stop reason")
        result = {"op": op, "reason": reason}
        if "when" in value:
            conditions = _canonical_surface_conditions(
                value["when"], "surface procedure stop condition"
            )
            if not conditions:
                raise FieldProgramError("surface procedure stop condition is empty")
            result["when"] = conditions
        return result
    if op in {"cancel", "checkpoint", "complete"}:
        if set(value) != {"op"}:
            raise FieldProgramError(f"surface procedure {op} node is invalid")
        return {"op": op}
    raise FieldProgramError("surface procedure control operation is unsupported")


def _canonical_surface_contract(
    value: Any,
    *,
    bounds: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "applicability",
        "capability_requirements",
        "control_flow",
        "dependencies",
        "expected_effect",
        "experience",
        "known_exceptions",
        "max_duration_ns",
        "max_intentions",
        "maximum_observation_age_ns",
        "purpose",
        "recovery_choices",
        "schema",
        "stop_conditions",
        "target",
    }
    optional = {"resource_reservation"}
    if (
        not isinstance(value, Mapping)
        or not required <= set(value)
        or set(value) - required - optional
        or value.get("schema") != SURFACE_PROCEDURE_SCHEMA
    ):
        raise FieldProgramError("surface procedure contract has invalid keys")
    purpose = _semantic_program_identifier(value["purpose"], "procedure purpose")
    target = _semantic_program_plain(value["target"], "procedure target")
    if (
        not isinstance(target, Mapping)
        or set(target) != {"identity", "kind"}
        or not isinstance(target["kind"], str)
        or not target["kind"]
    ):
        raise FieldProgramError("surface procedure target is invalid")
    raw_dependencies = value["dependencies"]
    if not isinstance(raw_dependencies, list) or not raw_dependencies:
        raise FieldProgramError("surface procedure dependencies are invalid")
    dependencies: list[dict[str, str]] = []
    dependency_paths: set[str] = set()
    roles: set[str] = set()
    for dependency in raw_dependencies:
        if (
            not isinstance(dependency, Mapping)
            or set(dependency) != {"path", "role", "type"}
        ):
            raise FieldProgramError("surface procedure dependency is invalid")
        path = dependency["path"]
        role = dependency["role"]
        value_type = dependency["type"]
        if (
            not isinstance(path, str)
            or not path
            or len(path.encode("utf-8")) > 1024
            or path in dependency_paths
            or not isinstance(role, str)
            or role not in {"field", "observed-version", "source", "target"}
            or not isinstance(value_type, str)
            or value_type not in _SURFACE_VALUE_TYPES
        ):
            raise FieldProgramError("surface procedure dependency is invalid")
        dependency_paths.add(path)
        roles.add(role)
        dependencies.append({"path": path, "role": role, "type": value_type})
    if not {"observed-version", "target"} <= roles:
        raise FieldProgramError(
            "surface procedure needs typed target and observed-version dependencies"
        )
    dependencies.sort(key=lambda item: (item["path"], item["role"]))
    capabilities = value["capability_requirements"]
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or any(not isinstance(item, str) or not item for item in capabilities)
        or len(set(capabilities)) != len(capabilities)
    ):
        raise FieldProgramError("surface procedure capabilities are invalid")
    capabilities = sorted(capabilities)
    expected_effect = _semantic_program_plain(
        value["expected_effect"], "surface procedure expected effect"
    )
    if (
        not isinstance(expected_effect, Mapping)
        or not expected_effect
        or any(not isinstance(path, str) or not path for path in expected_effect)
    ):
        raise FieldProgramError("surface procedure expected effect is invalid")
    applicability = _canonical_surface_conditions(
        value["applicability"], "surface procedure applicability"
    )
    stop_conditions = _canonical_surface_conditions(
        value["stop_conditions"], "surface procedure stop conditions"
    )
    exceptions = value["known_exceptions"]
    if not isinstance(exceptions, list) or len(exceptions) > int(
        bounds["max_branches"]
    ):
        raise FieldProgramError("surface procedure exceptions are invalid")
    known_exceptions: list[dict[str, Any]] = []
    for exception in exceptions:
        if (
            not isinstance(exception, Mapping)
            or set(exception) != {"description", "name", "when"}
            or not isinstance(exception["description"], str)
            or not exception["description"]
        ):
            raise FieldProgramError("surface procedure exception is invalid")
        known_exceptions.append(
            {
                "description": _semantic_program_identifier(
                    exception["description"], "exception description"
                ),
                "name": _semantic_program_identifier(
                    exception["name"], "exception name"
                ),
                "when": _canonical_surface_conditions(
                    exception["when"], "surface procedure exception condition"
                ),
            }
        )
    experience = _semantic_program_plain(
        value["experience"], "surface procedure experience"
    )
    if not isinstance(experience, list):
        raise FieldProgramError("surface procedure experience must be a list")
    max_age = _integer(
        value["maximum_observation_age_ns"],
        "surface procedure observation age",
        minimum=1,
        maximum=9_007_199_254_740_991,
    )
    max_duration = _integer(
        value["max_duration_ns"],
        "surface procedure maximum duration",
        minimum=1,
        maximum=9_007_199_254_740_991,
    )
    max_intentions = _integer(
        value["max_intentions"],
        "surface procedure intention maximum",
        minimum=1,
        maximum=int(bounds["max_horizon"]),
    )
    flow = _canonical_surface_control(
        value["control_flow"],
        depth=0,
        counter=[0],
        bounds=bounds,
    )
    recovery_choices = value["recovery_choices"]
    if not isinstance(recovery_choices, list) or len(recovery_choices) > int(
        bounds["max_branches"]
    ):
        raise FieldProgramError("surface procedure recovery choices are invalid")
    canonical_recovery = []
    for recovery in recovery_choices:
        if (
            not isinstance(recovery, Mapping)
            or set(recovery) != {"control", "name", "when"}
        ):
            raise FieldProgramError("surface procedure recovery choice is invalid")
        conditions = _canonical_surface_conditions(
            recovery["when"], "surface procedure recovery condition"
        )
        if not conditions:
            raise FieldProgramError("surface procedure recovery condition is empty")
        canonical_recovery.append(
            {
                "control": _canonical_surface_control(
                    recovery["control"],
                    depth=0,
                    counter=[0],
                    bounds=bounds,
                ),
                "name": _semantic_program_identifier(
                    recovery["name"], "surface procedure recovery name"
                ),
                "when": conditions,
            }
        )
    result = {
        "applicability": applicability,
        "capability_requirements": capabilities,
        "control_flow": flow,
        "dependencies": dependencies,
        "expected_effect": dict(expected_effect),
        "experience": experience,
        "known_exceptions": known_exceptions,
        "max_duration_ns": max_duration,
        "max_intentions": max_intentions,
        "maximum_observation_age_ns": max_age,
        "purpose": purpose,
        "recovery_choices": canonical_recovery,
        "schema": SURFACE_PROCEDURE_SCHEMA,
        "stop_conditions": stop_conditions,
        "target": dict(target),
    }
    if "resource_reservation" in value:
        reservation = _semantic_program_plain(
            value["resource_reservation"], "surface procedure reservation"
        )
        if not isinstance(reservation, Mapping):
            raise FieldProgramError("surface procedure reservation is invalid")
        result["resource_reservation"] = dict(reservation)
    return result
SEMANTIC_PROGRAM_KINDS = (
    "affine",
    "construction",
    "consolidation",
    "context-tree",
    "factor",
    "hybrid",
    "identity",
    "migration",
    "measurement",
    "procedure",
    "sequence",
    "table",
    "timer",
    "conditional",
)
SEMANTIC_MECHANISM_KINDS = (
    "affine",
    "context-tree",
    "factor",
    "hybrid",
    "identity",
    "sequence",
    "table",
    "timer",
    "conditional",
)
MECHANISM_STEP_KERNEL = "learning.mechanism-step"
MECHANISM_STEP_MAX_WORK = 32
_SEQUENCE_MAX_ROWS = 8
_SEQUENCE_MAX_COLUMNS = 8
_SEQUENCE_MAX_AST_NODES = 256
_SEQUENCE_MAX_AST_DEPTH = 16
_SEQUENCE_MAX_STAGES = 8
_CONDITIONAL_MAX_BRANCHES = 64
_CONTEXT_TREE_MAX_DEPTH = 8
_CONTEXT_TREE_MAX_FEATURES = 64
_SEMANTIC_MECHANISM_MAX_NESTING = 8


class FieldProgramError(ValueError):
    """A structured source is malformed or exceeds its compile bound."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FieldProgramError("structured program is not JSON-canonical") from exc


def _integer(value: Any, name: str, *, minimum: int = 0, maximum: int = 255) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise FieldProgramError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return int(value)


def _stack(value: Any) -> int:
    if value == "left":
        return 0
    if value == "right":
        return 1
    raise FieldProgramError("stack must be 'left' or 'right'")


@dataclass(frozen=True, slots=True)
class CompiledFieldProgram:
    program: tuple[tuple[int, int, int, int, int], ...]
    entry: int
    left: tuple[int, ...]
    right: tuple[int, ...]
    source_sha256: str
    source_nodes: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": COMPILED_SCHEMA,
            "program": [list(row) for row in self.program],
            "entry": self.entry,
            "left": list(self.left),
            "right": list(self.right),
            "source_sha256": self.source_sha256,
            "source_nodes": self.source_nodes,
        }


@dataclass(frozen=True, slots=True)
class CompiledRegionalProgram:
    """Immutable lowering result for the v3 regional instruction catalog."""

    program: tuple[Mapping[str, Any], ...]
    entry: int
    values: Mapping[str, Any]
    value_capacities: Mapping[str, int]
    source_sha256: str
    source_nodes: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": COMPILED_REGIONAL_SCHEMA,
            "program": [dict(row) for row in self.program],
            "entry": self.entry,
            "values": dict(self.values),
            "value_capacities": dict(self.value_capacities),
            "source_sha256": self.source_sha256,
            "source_nodes": self.source_nodes,
        }


class _Assembler:
    def __init__(self, max_instructions: int):
        self.rows: list[list[int | str]] = []
        self.labels: dict[str, int] = {}
        self.serial = 0
        self.max_instructions = max_instructions

    def name(self, prefix: str) -> str:
        self.serial += 1
        return f"@{prefix}-{self.serial}"

    def mark(self, label: str) -> None:
        if label in self.labels:
            raise FieldProgramError("internal duplicate label")
        self.labels[label] = len(self.rows)

    def emit(self, opcode: int, a: int | str = 0, b: int | str = 0,
             c: int | str = 0, d: int | str = 0) -> None:
        if len(self.rows) >= self.max_instructions:
            raise FieldProgramError("compiled program exceeds max_instructions")
        self.rows.append([opcode, a, b, c, d])

    def resolve(self) -> tuple[tuple[int, int, int, int, int], ...]:
        resolved: list[tuple[int, int, int, int, int]] = []
        for row in self.rows:
            words: list[int] = []
            for word in row:
                if isinstance(word, str):
                    if word not in self.labels:
                        raise FieldProgramError("internal unresolved label")
                    words.append(self.labels[word])
                else:
                    words.append(int(word))
            resolved.append((words[0], words[1], words[2], words[3], words[4]))
        return tuple(resolved)


class _Compiler:
    def __init__(self, source: Mapping[str, Any], max_instructions: int):
        self.source = source
        self.asm = _Assembler(max_instructions)
        raw_constants = source.get("constants", {})
        raw_functions = source.get("functions", {})
        if not isinstance(raw_constants, Mapping) or not all(isinstance(key, str) and key for key in raw_constants):
            raise FieldProgramError("constants must be a string-keyed mapping")
        if not isinstance(raw_functions, Mapping) or not all(isinstance(key, str) and key for key in raw_functions):
            raise FieldProgramError("functions must be a string-keyed mapping")
        self.constants = {
            str(key): _integer(value, f"constant {key!r}")
            for key, value in raw_constants.items()
        }
        self.functions: dict[str, Sequence[Any]] = {}
        for name, body in raw_functions.items():
            if not isinstance(body, list):
                raise FieldProgramError(f"function {name!r} must be a statement list")
            self.functions[str(name)] = body
        self.nodes = 0
        self.scratch = _stack(source.get("scratch_stack", "left"))

    def value(self, raw: Any, name: str = "value") -> int:
        if isinstance(raw, str):
            if raw not in self.constants:
                raise FieldProgramError(f"unknown constant {raw!r}")
            return self.constants[raw]
        return _integer(raw, name)

    @staticmethod
    def _keys(statement: Mapping[str, Any], allowed: set[str]) -> None:
        if set(statement) != allowed:
            raise FieldProgramError(
                f"{statement.get('op', 'statement')!r} has invalid keys"
            )
    @staticmethod
    def _right_push(frames: tuple[int, ...]) -> tuple[int, ...]:
        return tuple(depth + 1 for depth in frames)

    @staticmethod
    def _right_pop(frames: tuple[int, ...]) -> tuple[int, ...]:
        if frames and frames[-1] == 0:
            raise FieldProgramError("right-stack pop would consume a live lexical binding")
        return tuple(depth - 1 for depth in frames)

    def validate_scope_sequence(
        self,
        statements: Sequence[Any],
        frames: tuple[int, ...] = (),
        variables: tuple[str, ...] = (),
        active_calls: tuple[str, ...] = (),
    ) -> tuple[int, ...] | None:
        """Prove every continuing path preserves live right-stack bindings."""

        if not isinstance(statements, (list, tuple)):
            raise FieldProgramError("statement body must be a finite sequence")
        current: tuple[int, ...] | None = frames
        for raw in statements:
            if current is None:
                break
            current = self.validate_scope_statement(
                raw, current, variables, active_calls
            )
        return current

    def validate_scope_statement(
        self,
        raw: Any,
        frames: tuple[int, ...],
        variables: tuple[str, ...],
        active_calls: tuple[str, ...],
    ) -> tuple[int, ...] | None:
        if not isinstance(raw, Mapping) or not isinstance(raw.get("op"), str):
            raise FieldProgramError("every statement must have a string op")
        op = raw["op"]
        if op == "push":
            self._keys(raw, {"op", "stack", "value"})
            stack = _stack(raw["stack"])
            self.value(raw["value"])
            return self._right_push(frames) if stack == 1 and frames else frames
        if op == "pop":
            self._keys(raw, {"op", "stack"})
            stack = _stack(raw["stack"])
            return self._right_pop(frames) if stack == 1 and frames else frames
        if op == "push_acc":
            self._keys(raw, {"op", "stack"})
            stack = _stack(raw["stack"])
            return self._right_push(frames) if stack == 1 and frames else frames
        if op == "set_acc":
            self._keys(raw, {"op", "value"})
            self.value(raw["value"])
            return frames
        if op in {"add_acc", "sub_acc"}:
            self._keys(raw, {"op", "value"})
            self.value(raw["value"])
            return frames
        if op == "if_acc":
            self._keys(raw, {"op", "condition", "then", "else"})
            if not isinstance(raw["then"], list) or not isinstance(raw["else"], list):
                raise FieldProgramError("if_acc branches must be statement lists")
            self._condition(raw["condition"])
            branch_states = [
                state
                for state in (
                    self.validate_scope_sequence(
                        raw["then"], frames, variables, active_calls
                    ),
                    self.validate_scope_sequence(
                        raw["else"], frames, variables, active_calls
                    ),
                )
                if state is not None
            ]
            if not branch_states:
                return None
            if any(state != branch_states[0] for state in branch_states[1:]):
                raise FieldProgramError(
                    "if_acc branches leave incompatible live lexical stack effects"
                )
            return branch_states[0]
        if op == "while_acc":
            self._keys(raw, {"op", "condition", "body"})
            if not isinstance(raw["body"], list):
                raise FieldProgramError("while_acc body must be a statement list")
            self._condition(raw["condition"])
            body_state = self.validate_scope_sequence(
                raw["body"], frames, variables, active_calls
            )
            if body_state is not None and body_state != frames:
                raise FieldProgramError(
                    "while_acc body must preserve live lexical stack depth"
                )
            return frames
        if op == "repeat":
            self._keys(raw, {"op", "count", "body"})
            count = _integer(raw["count"], "repeat count", maximum=1024)
            body = raw["body"]
            if not isinstance(body, list):
                raise FieldProgramError("repeat body must be a list")
            current: tuple[int, ...] | None = frames
            for _ in range(count):
                if current is None:
                    break
                current = self.validate_scope_sequence(
                    body, current, variables, active_calls
                )
            return current
        if op == "call":
            self._keys(raw, {"op", "function"})
            name = raw["function"]
            if not isinstance(name, str) or name not in self.functions:
                raise FieldProgramError("call names a missing function")
            if name in active_calls:
                raise FieldProgramError(
                    "recursive structured functions are not allowed"
                )
            return self.validate_scope_sequence(
                self.functions[name],
                frames,
                variables,
                (*active_calls, name),
            )
        if op == "with_var":
            self._keys(raw, {"op", "name", "value", "body"})
            name = raw["name"]
            body = raw["body"]
            if not isinstance(name, str) or not name or name in variables:
                raise FieldProgramError("with_var requires a unique nonempty name")
            if not isinstance(body, list):
                raise FieldProgramError("with_var body must be a statement list")
            if raw["value"] != "acc":
                self.value(raw["value"], "variable value")
            entered = (*self._right_push(frames), 0)
            body_state = self.validate_scope_sequence(
                body, entered, (*variables, name), active_calls
            )
            if body_state is None:
                return None
            if body_state[-1] != 0:
                raise FieldProgramError(
                    "with_var body buries its live lexical binding on the right stack"
                )
            restored = tuple(depth - 1 for depth in body_state[:-1])
            if restored != frames:
                raise FieldProgramError(
                    "with_var body does not restore outer lexical stack depth"
                )
            return restored
        if op == "load_var":
            self._keys(raw, {"op", "name"})
            if not variables or raw["name"] != variables[-1]:
                raise FieldProgramError(
                    "only the innermost live variable can be loaded"
                )
            if frames[-1] != 0:
                raise FieldProgramError(
                    "load_var requires its lexical binding at the right-stack top"
                )
            return frames
        if op == "halt":
            self._keys(raw, {"op"})
            return None
        raise FieldProgramError(f"unknown structured operation {op!r}")

    def fold_sequence(
        self,
        statements: Sequence[Any],
        accumulator: int | None,
        variables: tuple[tuple[str, int | None], ...] = (),
        active_calls: tuple[str, ...] = (),
    ) -> tuple[list[Mapping[str, Any]], int | None, bool]:
        """Fold only values proved at the current instruction boundary."""

        folded: list[Mapping[str, Any]] = []
        current = accumulator
        continuing = True
        for raw in statements:
            rows, after, statement_continues = self.fold_statement(
                raw,
                current if continuing else None,
                variables,
                active_calls,
            )
            if continuing:
                folded.extend(rows)
                current = after
                continuing = statement_continues
        return folded, current, continuing

    def fold_statement(
        self,
        raw: Any,
        accumulator: int | None,
        variables: tuple[tuple[str, int | None], ...],
        active_calls: tuple[str, ...],
    ) -> tuple[list[Mapping[str, Any]], int | None, bool]:
        self.nodes += 1
        if self.nodes > _MAX_SOURCE_NODES:
            raise FieldProgramError(
                "structured source exceeds its node bound"
            )
        if not isinstance(raw, Mapping) or not isinstance(
            raw.get("op"), str
        ):
            raise FieldProgramError(
                "every statement must have a string op"
            )
        op = raw["op"]
        if op == "push":
            self._keys(raw, {"op", "stack", "value"})
            _stack(raw["stack"])
            self.value(raw["value"])
            return [dict(raw)], accumulator, True
        if op == "pop":
            self._keys(raw, {"op", "stack"})
            _stack(raw["stack"])
            return [dict(raw)], None, True
        if op == "push_acc":
            self._keys(raw, {"op", "stack"})
            _stack(raw["stack"])
            return [dict(raw)], accumulator, True
        if op == "set_acc":
            self._keys(raw, {"op", "value"})
            value = self.value(raw["value"])
            return [{"op": "set_acc", "value": value}], value, True
        if op in {"add_acc", "sub_acc"}:
            self._keys(raw, {"op", "value"})
            value = self.value(raw["value"])
            if accumulator is not None and accumulator < 256:
                delta = value if op == "add_acc" else -value
                result = (accumulator + delta) % 256
                return [
                    {"op": "set_acc", "value": result}
                ], result, True
            return [dict(raw)], None, True
        if op == "if_acc":
            self._keys(
                raw,
                {"op", "condition", "then", "else"},
            )
            then_body = raw["then"]
            else_body = raw["else"]
            if not isinstance(then_body, list) or not isinstance(
                else_body, list
            ):
                raise FieldProgramError(
                    "if_acc branches must be statement lists"
                )
            mode, value = self._condition(raw["condition"])
            then_rows, then_acc, then_continues = self.fold_sequence(
                then_body,
                accumulator,
                variables,
                active_calls,
            )
            else_rows, else_acc, else_continues = self.fold_sequence(
                else_body,
                accumulator,
                variables,
                active_calls,
            )
            if accumulator is not None:
                matches = accumulator == value
                choose_then = (
                    matches if mode == "equals" else not matches
                )
                return (
                    (then_rows, then_acc, then_continues)
                    if choose_then
                    else (else_rows, else_acc, else_continues)
                )
            continuing_states = [
                state
                for state, continues in (
                    (then_acc, then_continues),
                    (else_acc, else_continues),
                )
                if continues
            ]
            merged = (
                continuing_states[0]
                if continuing_states
                and all(
                    state == continuing_states[0]
                    for state in continuing_states[1:]
                )
                else None
            )
            return [
                {
                    "op": "if_acc",
                    "condition": dict(raw["condition"]),
                    "then": then_rows,
                    "else": else_rows,
                }
            ], merged, bool(continuing_states)
        if op == "while_acc":
            self._keys(raw, {"op", "condition", "body"})
            body = raw["body"]
            if not isinstance(body, list):
                raise FieldProgramError(
                    "while_acc body must be a statement list"
                )
            mode, value = self._condition(raw["condition"])
            entry_accumulator = (
                value if mode == "equals" else None
            )
            body_rows, _, _ = self.fold_sequence(
                body,
                entry_accumulator,
                variables,
                active_calls,
            )
            if accumulator is not None:
                matches = accumulator == value
                enters = (
                    matches if mode == "equals" else not matches
                )
                if not enters:
                    return [], accumulator, True
            exit_accumulator = (
                value if mode == "not_equals" else None
            )
            return [
                {
                    "op": "while_acc",
                    "condition": dict(raw["condition"]),
                    "body": body_rows,
                }
            ], exit_accumulator, True
        if op == "repeat":
            self._keys(raw, {"op", "count", "body"})
            count = _integer(
                raw["count"], "repeat count", maximum=1024
            )
            body = raw["body"]
            if not isinstance(body, list):
                raise FieldProgramError(
                    "repeat body must be a list"
                )
            rows: list[Mapping[str, Any]] = []
            current = accumulator
            continuing = True
            for _ in range(count):
                iteration, after, iteration_continues = (
                    self.fold_sequence(
                        body,
                        current if continuing else None,
                        variables,
                        active_calls,
                    )
                )
                if continuing:
                    rows.extend(iteration)
                    current = after
                    continuing = iteration_continues
            return rows, current, continuing
        if op == "call":
            self._keys(raw, {"op", "function"})
            name = raw["function"]
            if not isinstance(name, str) or name not in self.functions:
                raise FieldProgramError(
                    "call names a missing function"
                )
            if name in active_calls:
                raise FieldProgramError(
                    "recursive structured functions are not allowed"
                )
            return self.fold_sequence(
                self.functions[name],
                accumulator,
                variables,
                (*active_calls, name),
            )
        if op == "with_var":
            self._keys(
                raw,
                {"op", "name", "value", "body"},
            )
            name = raw["name"]
            body = raw["body"]
            if (
                not isinstance(name, str)
                or not name
                or any(existing == name for existing, _ in variables)
            ):
                raise FieldProgramError(
                    "with_var requires a unique nonempty name"
                )
            if not isinstance(body, list):
                raise FieldProgramError(
                    "with_var body must be a statement list"
                )
            binding = (
                accumulator
                if raw["value"] == "acc"
                else self.value(raw["value"], "variable value")
            )
            body_rows, _, body_continues = self.fold_sequence(
                body,
                accumulator,
                (*variables, (name, binding)),
                active_calls,
            )
            return [
                {
                    "op": "with_var",
                    "name": name,
                    "value": (
                        "acc"
                        if raw["value"] == "acc"
                        else self.value(
                            raw["value"], "variable value"
                        )
                    ),
                    "body": body_rows,
                }
            ], binding, body_continues
        if op == "load_var":
            self._keys(raw, {"op", "name"})
            if not variables or raw["name"] != variables[-1][0]:
                raise FieldProgramError(
                    "only the innermost live variable can be loaded"
                )
            return [dict(raw)], variables[-1][1], True
        if op == "halt":
            self._keys(raw, {"op"})
            return [dict(raw)], accumulator, False
        raise FieldProgramError(
            f"unknown structured operation {op!r}"
        )


    def sequence(self, statements: Sequence[Any], continuation: str,
                 variables: tuple[str, ...] = (), active_calls: tuple[str, ...] = ()) -> str:
        if not isinstance(statements, (list, tuple)):
            raise FieldProgramError("statement body must be a finite sequence")
        if not statements:
            return continuation
        labels = [self.asm.name("stmt") for _ in statements]
        for index, raw in enumerate(statements):
            self.asm.mark(labels[index])
            next_label = labels[index + 1] if index + 1 < len(labels) else continuation
            self.statement(raw, next_label, variables, active_calls)
        return labels[0]

    def _set_acc(self, value: int, continuation: str) -> None:
        popped = self.asm.name("set-pop")
        self.asm.emit(PUSH, self.scratch, value, popped, 0)
        self.asm.mark(popped)
        self.asm.emit(POP, self.scratch, continuation, 0, 0)

    def _arithmetic(self, delta: int, continuation: str) -> None:
        checks = [self.asm.name("arith-check") for _ in range(256)]
        handlers = [self.asm.name("arith-value") for _ in range(256)]
        missing = self.asm.name("arith-empty")
        for value in range(256):
            if value:
                self.asm.mark(checks[value])
            next_check = checks[value + 1] if value < 255 else missing
            self.asm.emit(BRANCH, value, handlers[value], next_check, 0)
        self.asm.mark(missing)
        # PUSH_ACC faults exactly when arithmetic sees the EMPTY accumulator.
        self.asm.emit(PUSH_ACC, self.scratch, continuation, 0, 0)
        for value in range(256):
            self.asm.mark(handlers[value])
            self._set_acc((value + delta) % 256, continuation)

    def _condition(self, raw: Any) -> tuple[str, int]:
        if not isinstance(raw, Mapping) or len(raw) != 1:
            raise FieldProgramError("condition must contain exactly equals or not_equals")
        if "equals" in raw:
            return "equals", self.value(raw["equals"], "condition value")
        if "not_equals" in raw:
            return "not_equals", self.value(raw["not_equals"], "condition value")
        raise FieldProgramError("condition must contain equals or not_equals")

    def statement(self, raw: Any, continuation: str, variables: tuple[str, ...],
                  active_calls: tuple[str, ...]) -> None:
        if not isinstance(raw, Mapping) or not isinstance(raw.get("op"), str):
            raise FieldProgramError("every statement must have a string op")
        op = raw["op"]
        if op == "push":
            self._keys(raw, {"op", "stack", "value"})
            self.asm.emit(PUSH, _stack(raw["stack"]), self.value(raw["value"]), continuation, 0)
        elif op == "pop":
            self._keys(raw, {"op", "stack"})
            self.asm.emit(POP, _stack(raw["stack"]), continuation, 0, 0)
        elif op == "push_acc":
            self._keys(raw, {"op", "stack"})
            self.asm.emit(PUSH_ACC, _stack(raw["stack"]), continuation, 0, 0)
        elif op == "set_acc":
            self._keys(raw, {"op", "value"})
            self._set_acc(self.value(raw["value"]), continuation)
        elif op in {"add_acc", "sub_acc"}:
            self._keys(raw, {"op", "value"})
            delta = self.value(raw["value"])
            self._arithmetic(delta if op == "add_acc" else -delta, continuation)
        elif op == "if_acc":
            self._keys(raw, {"op", "condition", "then", "else"})
            if not isinstance(raw["then"], list) or not isinstance(raw["else"], list):
                raise FieldProgramError("if_acc branches must be statement lists")
            mode, value = self._condition(raw["condition"])
            then_label = self.asm.name("if-then")
            else_label = self.asm.name("if-else")
            yes, no = (then_label, else_label) if mode == "equals" else (else_label, then_label)
            self.asm.emit(BRANCH, value, yes, no, 0)
            self.asm.mark(then_label)
            if raw["then"]:
                self.sequence(raw["then"], continuation, variables, active_calls)
            else:
                self.asm.emit(JUMP, continuation, 0, 0, 0)
            self.asm.mark(else_label)
            if raw["else"]:
                self.sequence(raw["else"], continuation, variables, active_calls)
            else:
                self.asm.emit(JUMP, continuation, 0, 0, 0)
        elif op == "while_acc":
            self._keys(raw, {"op", "condition", "body"})
            if not isinstance(raw["body"], list):
                raise FieldProgramError("while_acc body must be a statement list")
            condition_label = self.asm.name("while-condition")
            body_label = self.asm.name("while-body")
            self.asm.mark(condition_label)
            mode, value = self._condition(raw["condition"])
            yes, no = (body_label, continuation) if mode == "equals" else (continuation, body_label)
            self.asm.emit(BRANCH, value, yes, no, 0)
            self.asm.mark(body_label)
            if raw["body"]:
                self.sequence(raw["body"], condition_label, variables, active_calls)
            else:
                self.asm.emit(JUMP, condition_label, 0, 0, 0)
        elif op == "repeat":
            self._keys(raw, {"op", "count", "body"})
            count = _integer(raw["count"], "repeat count", maximum=1024)
            body = raw["body"]
            if not isinstance(body, list):
                raise FieldProgramError("repeat body must be a list")
            if not count or not body:
                self.asm.emit(JUMP, continuation, 0, 0, 0)
            else:
                start = self.asm.name("repeat-body")
                self.asm.emit(JUMP, start, 0, 0, 0)
                self.asm.mark(start)
                self.sequence(body * count, continuation, variables, active_calls)
        elif op == "call":
            self._keys(raw, {"op", "function"})
            name = raw["function"]
            if not isinstance(name, str) or name not in self.functions:
                raise FieldProgramError("call names a missing function")
            if name in active_calls:
                raise FieldProgramError("recursive structured functions are not allowed")
            start = self.asm.name("call-body")
            self.asm.emit(JUMP, start, 0, 0, 0)
            self.asm.mark(start)
            body = self.functions[name]
            if body:
                self.sequence(body, continuation, variables, (*active_calls, name))
            else:
                self.asm.emit(JUMP, continuation, 0, 0, 0)
        elif op == "with_var":
            self._keys(raw, {"op", "name", "value", "body"})
            name = raw["name"]
            body = raw["body"]
            if not isinstance(name, str) or not name or name in variables:
                raise FieldProgramError("with_var requires a unique nonempty name")
            if not isinstance(body, list):
                raise FieldProgramError("with_var body must be a statement list")
            body_label = self.asm.name("var-body")
            cleanup = self.asm.name("var-cleanup")
            if raw["value"] == "acc":
                self.asm.emit(PUSH_ACC, 1, body_label, 0, 0)
            else:
                self.asm.emit(PUSH, 1, self.value(raw["value"], "variable value"), body_label, 0)
            self.asm.mark(body_label)
            if body:
                self.sequence(body, cleanup, (*variables, name), active_calls)
            else:
                self.asm.emit(JUMP, cleanup, 0, 0, 0)
            self.asm.mark(cleanup)
            self.asm.emit(POP, 1, continuation, 0, 0)
        elif op == "load_var":
            self._keys(raw, {"op", "name"})
            if not variables or raw["name"] != variables[-1]:
                raise FieldProgramError("only the innermost live variable can be loaded")
            restore = self.asm.name("var-restore")
            self.asm.emit(POP, 1, restore, 0, 0)
            self.asm.mark(restore)
            self.asm.emit(PUSH_ACC, 1, continuation, 0, 0)
        elif op == "halt":
            self._keys(raw, {"op"})
            self.asm.emit(HALT, 0, 0, 0, 0)
        else:
            raise FieldProgramError(f"unknown structured operation {op!r}")


def compile_structured_program(
    source: Mapping[str, Any],
    *,
    max_instructions: int = 16384,
    optimize_known_values: bool = True,
) -> CompiledFieldProgram:
    """Compile one canonical structured program into ordinary machine rows."""

    if not isinstance(source, Mapping):
        raise FieldProgramError("structured source must be a mapping")
    allowed = {"schema", "constants", "functions", "main", "left", "right", "scratch_stack"}
    if set(source) - allowed or source.get("schema") != SCHEMA or "main" not in source:
        raise FieldProgramError("structured source has invalid keys or schema")
    max_instructions = _integer(max_instructions, "max_instructions", minimum=1, maximum=1_000_000)
    if not isinstance(optimize_known_values, bool):
        raise FieldProgramError(
            "optimize_known_values must be boolean"
        )
    main = source["main"]
    if not isinstance(main, list):
        raise FieldProgramError("main must be a statement list")
    left = tuple(_integer(value, "left input") for value in source.get("left", ()))
    right = tuple(_integer(value, "right input") for value in source.get("right", ()))
    compiler = _Compiler(source, max_instructions)
    compiler.validate_scope_sequence(main)
    optimized_main, _, _ = compiler.fold_sequence(main, 256)
    halt = compiler.asm.name("program-halt")
    entry_label = compiler.sequence(
        optimized_main if optimize_known_values else main,
        halt,
    )
    compiler.asm.mark(halt)
    compiler.asm.emit(HALT, 0, 0, 0, 0)
    program = compiler.asm.resolve()
    entry = compiler.asm.labels[entry_label]
    return CompiledFieldProgram(
        program=program,
        entry=entry,
        left=left,
        right=right,
        source_sha256=hashlib.sha256(_canonical(source)).hexdigest(),
        source_nodes=compiler.nodes,
    )


def _bounded_source_nodes(value: Any) -> int:
    pending = [value]
    count = 0
    while pending:
        current = pending.pop()
        count += 1
        if count > _MAX_SOURCE_NODES:
            raise FieldProgramError("regional source exceeds its node bound")
        if isinstance(current, Mapping):
            pending.extend(current.values())
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
    return count


def compile_regional_program(
    source: Mapping[str, Any],
    *,
    max_instructions: int = 16_384,
) -> CompiledRegionalProgram:
    """Lower labels in one bounded declarative v3 program.

    The compiler is a pure codec: it admits no callbacks and owns no runtime
    state. Native-kernel names are bound later by ``FieldComputer.initial``
    against that machine's frozen catalog.
    """

    if not isinstance(source, Mapping):
        raise FieldProgramError("regional source must be a mapping")
    allowed = {
        "schema",
        "instructions",
        "entry",
        "values",
        "value_capacities",
    }
    if set(source) - allowed or source.get("schema") != REGIONAL_SOURCE_SCHEMA:
        raise FieldProgramError("regional source has invalid keys or schema")
    raw_rows = source.get("instructions")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise FieldProgramError("regional instructions must be a nonempty list")
    max_instructions = _integer(
        max_instructions,
        "max_instructions",
        minimum=1,
        maximum=1_000_000,
    )
    if len(raw_rows) > max_instructions:
        raise FieldProgramError("compiled regional program exceeds max_instructions")
    source_nodes = _bounded_source_nodes(source)
    values = source.get("values", {})
    capacities = source.get("value_capacities", {})
    if not isinstance(values, Mapping) or not all(
        isinstance(name, str) and name for name in values
    ):
        raise FieldProgramError("regional values must be a string-keyed mapping")
    if not isinstance(capacities, Mapping) or not all(
        isinstance(name, str) and name for name in capacities
    ):
        raise FieldProgramError(
            "regional value capacities must be a string-keyed mapping"
        )
    if set(capacities) - set(values):
        raise FieldProgramError("regional capacities name undeclared values")
    canonical_values = json.loads(_canonical(dict(values)).decode("utf-8"))
    canonical_capacities = {
        str(name): _integer(
            capacity,
            f"value capacity {name!r}",
            minimum=1,
            maximum=2**32 - 1,
        )
        for name, capacity in capacities.items()
    }

    labels: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, Mapping):
            raise FieldProgramError(
                f"regional instruction {index} must be a mapping"
            )
        row = dict(raw)
        label = row.pop("label", None)
        if label is not None:
            if not isinstance(label, str) or not label or label in labels:
                raise FieldProgramError("regional labels must be unique strings")
            labels[label] = index
        rows.append(row)

    def resolve_target(value: Any, name: str) -> int:
        if isinstance(value, str):
            if value not in labels:
                raise FieldProgramError(f"{name} names an unknown label")
            return labels[value]
        return _integer(
            value,
            name,
            minimum=0,
            maximum=len(rows) - 1,
        )

    resolved: list[dict[str, Any]] = []
    for index, source_row in enumerate(rows):
        row = dict(source_row)
        for key in ("next", "target_pc"):
            if key in row:
                row[key] = resolve_target(
                    row[key], f"regional instruction {index}.{key}"
                )
        if isinstance(row.get("event"), Mapping):
            event = dict(row["event"])
            if "pc" in event:
                event["pc"] = resolve_target(
                    event["pc"], f"regional instruction {index}.event.pc"
                )
            row["event"] = event
        resolved.append(row)
    try:
        program = canonical_program(resolved)
    except ValueError as exc:
        raise FieldProgramError(str(exc)) from exc
    entry = resolve_target(source.get("entry", 0), "regional entry")
    frozen_program = tuple(MappingProxyType(dict(row)) for row in program)
    return CompiledRegionalProgram(
        program=frozen_program,
        entry=entry,
        values=MappingProxyType(canonical_values),
        value_capacities=MappingProxyType(canonical_capacities),
        source_sha256=hashlib.sha256(_canonical(source)).hexdigest(),
        source_nodes=source_nodes,
    )


def _semantic_program_plain(value: Any, label: str) -> Any:
    try:
        detached = json.loads(_canonical(value).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise FieldProgramError(f"{label} is not canonical JSON") from exc
    pending = [detached]
    nodes = 0
    while pending:
        current = pending.pop()
        nodes += 1
        if nodes > _MAX_SOURCE_NODES:
            raise FieldProgramError(f"{label} exceeds the semantic node bound")
        if isinstance(current, float) and not math.isfinite(current):
            raise FieldProgramError(f"{label} contains a nonfinite number")
        if isinstance(current, dict):
            if any(not isinstance(key, str) for key in current):
                raise FieldProgramError(f"{label} contains a non-string key")
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
        elif current is not None and not isinstance(
            current, (bool, int, float, str)
        ):
            raise FieldProgramError(f"{label} contains an unsupported value")
    return detached


def _semantic_program_identifier(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 512
        or any(ord(character) < 32 for character in value)
    ):
        raise FieldProgramError(f"{label} must be a bounded nonempty string")
    return value


def _canonical_table_cell(value: Any, label: str) -> dict[str, Any]:
    """Validate one canonical nullable-table cell and return a detached cell."""

    if not isinstance(value, Mapping):
        raise FieldProgramError(f"{label} must be a typed cell")
    if value.get("kind") == "null":
        if set(value) != {"kind"}:
            raise FieldProgramError(f"{label} null cell has invalid keys")
        return {"kind": "null"}
    if value.get("kind") == "integer":
        if set(value) != {"kind", "value"}:
            raise FieldProgramError(f"{label} integer cell has invalid keys")
        integer = value["value"]
        if (
            isinstance(integer, bool)
            or not isinstance(integer, int)
            or not -32 <= integer <= 32
        ):
            raise FieldProgramError(f"{label} integer is outside [-32, 32]")
        return {"kind": "integer", "value": int(integer)}
    raise FieldProgramError(f"{label} has an unsupported cell kind")


def canonical_table(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and canonicalize a bounded ``cassifi.nullable-table.v1`` value."""

    if not isinstance(value, Mapping) or set(value) != {"schema", "columns", "rows"}:
        raise FieldProgramError("nullable table has invalid keys")
    detached = _semantic_program_plain(dict(value), "nullable table")
    if detached["schema"] != NULLABLE_TABLE_SCHEMA:
        raise FieldProgramError("nullable table schema is unsupported")
    columns = detached["columns"]
    if (
        not isinstance(columns, list)
        or not columns
        or len(columns) > _SEQUENCE_MAX_COLUMNS
        or any(
            not isinstance(column, str) or not column
            or len(column.encode("utf-8")) > 128
            or any(ord(character) < 32 for character in column)
            for column in columns
        )
        or columns != sorted(set(columns))
    ):
        raise FieldProgramError("nullable table columns are not canonical")
    rows = detached["rows"]
    if not isinstance(rows, list) or len(rows) > _SEQUENCE_MAX_ROWS:
        raise FieldProgramError("nullable table rows exceed their bound")
    canonical_rows: list[dict[str, Any]] = []
    expected = set(columns)
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or set(row) != expected:
            raise FieldProgramError(f"nullable table row {index} has invalid columns")
        canonical_rows.append(
            {
                column: _canonical_table_cell(
                    row[column], f"nullable table row {index} column {column!r}"
                )
                for column in columns
            }
        )
    return {
        "schema": NULLABLE_TABLE_SCHEMA,
        "columns": list(columns),
        "rows": canonical_rows,
    }


def table_from_rows(
    rows: Sequence[Any], columns: Sequence[str] = ("x",)
) -> dict[str, Any]:
    """Build a canonical nullable table from plain integer/``None`` rows.

    A one-column table accepts scalar rows; multi-column tables accept either
    aligned sequences or mappings.  Typed cells are accepted as a convenience
    but are still validated at this boundary.
    """

    if not isinstance(rows, (list, tuple)):
        raise FieldProgramError("table rows must be a finite sequence")
    if len(rows) > _SEQUENCE_MAX_ROWS:
        raise FieldProgramError("table rows exceed their bound")
    if not isinstance(columns, (list, tuple)) or not columns:
        raise FieldProgramError("table columns must be a nonempty sequence")
    names = list(columns)
    if any(not isinstance(name, str) for name in names):
        raise FieldProgramError("table columns must be strings")
    if names != sorted(set(names)):
        raise FieldProgramError("table columns must be sorted and unique")
    if len(names) > _SEQUENCE_MAX_COLUMNS:
        raise FieldProgramError("table columns exceed their bound")

    def cell(value: Any, label: str) -> dict[str, Any]:
        if value is None:
            return {"kind": "null"}
        if isinstance(value, Mapping):
            return _canonical_table_cell(value, label)
        if isinstance(value, bool) or not isinstance(value, int) or not -32 <= value <= 32:
            raise FieldProgramError(f"{label} must be an integer in [-32, 32] or null")
        return {"kind": "integer", "value": int(value)}

    canonical_rows: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        if isinstance(raw, Mapping):
            if set(raw) != set(names):
                raise FieldProgramError(f"table row {index} has invalid columns")
            values = [raw[name] for name in names]
        elif len(names) == 1:
            values = [raw]
        elif isinstance(raw, (list, tuple)) and len(raw) == len(names):
            values = list(raw)
        else:
            raise FieldProgramError(f"table row {index} has invalid shape")
        canonical_rows.append(
            {
                name: cell(values[column_index], f"table row {index} column {name!r}")
                for column_index, name in enumerate(names)
            }
        )
    return canonical_table(
        {"schema": NULLABLE_TABLE_SCHEMA, "columns": names, "rows": canonical_rows}
    )


def _sequence_literal_value(value: Any, label: str) -> int | None:
    if isinstance(value, Mapping):
        value = _canonical_table_cell(value, label)
        if value["kind"] == "null":
            return None
        return int(value["value"])
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not -32 <= value <= 32:
        raise FieldProgramError(f"{label} must be an integer in [-32, 32] or null")
    return int(value)


def _canonical_sequence_expr(raw: Any, depth: int, nodes: list[int]) -> dict[str, Any]:
    if depth > _SEQUENCE_MAX_AST_DEPTH:
        raise FieldProgramError("sequence AST depth exceeds its bound")
    if not isinstance(raw, Mapping) or not isinstance(raw.get("op"), str):
        raise FieldProgramError("sequence expression must have an op")
    nodes[0] += 1
    if nodes[0] > _SEQUENCE_MAX_AST_NODES:
        raise FieldProgramError("sequence AST exceeds its node bound")
    op = raw["op"]
    if op == "column":
        if set(raw) != {"op", "name"}:
            raise FieldProgramError("sequence column expression is invalid")
        return {
            "op": "column",
            "name": _semantic_program_identifier(raw["name"], "sequence column"),
        }
    if op == "literal":
        if set(raw) != {"op", "value"}:
            raise FieldProgramError("sequence literal expression is invalid")
        return {"op": "literal", "value": _sequence_literal_value(raw["value"], "sequence literal")}
    if op == "coalesce":
        if set(raw) != {"op", "args"} or not isinstance(raw["args"], list):
            raise FieldProgramError("sequence coalesce expression is invalid")
        if not raw["args"] or len(raw["args"]) > _SEQUENCE_MAX_COLUMNS:
            raise FieldProgramError("sequence coalesce arguments exceed their bound")
        return {
            "op": "coalesce",
            "args": [
                _canonical_sequence_expr(item, depth + 1, nodes)
                for item in raw["args"]
            ],
        }
    raise FieldProgramError(f"sequence expression operation {op!r} is unsupported")


def _canonical_sequence_predicate(raw: Any, depth: int, nodes: list[int]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or not isinstance(raw.get("op"), str):
        raise FieldProgramError("sequence predicate must have an op")
    op = raw["op"]
    if op in {"eq", "ne", "lt", "gt"}:
        if set(raw) != {"op", "left", "right"}:
            raise FieldProgramError("sequence comparison predicate is invalid")
        return {
            "op": op,
            "left": _canonical_sequence_expr(raw["left"], depth + 1, nodes),
            "right": _canonical_sequence_expr(raw["right"], depth + 1, nodes),
        }
    if op == "is_null":
        if set(raw) != {"op", "expr"}:
            raise FieldProgramError("sequence is_null predicate is invalid")
        return {
            "op": "is_null",
            "expr": _canonical_sequence_expr(raw["expr"], depth + 1, nodes),
        }
    raise FieldProgramError(f"sequence predicate operation {op!r} is unsupported")


def _canonical_sequence_stage(raw: Any, depth: int, nodes: list[int]) -> dict[str, Any]:
    if depth > _SEQUENCE_MAX_AST_DEPTH:
        raise FieldProgramError("sequence AST depth exceeds its bound")
    if not isinstance(raw, Mapping) or not isinstance(raw.get("op"), str):
        raise FieldProgramError("sequence stage must have an op")
    nodes[0] += 1
    if nodes[0] > _SEQUENCE_MAX_AST_NODES:
        raise FieldProgramError("sequence AST exceeds its node bound")
    op = raw["op"]
    if op == "project":
        if set(raw) != {"op", "columns"}:
            raise FieldProgramError("sequence project stage is invalid")
        columns = raw["columns"]
        if isinstance(columns, Mapping):
            entries = list(columns.items())
        elif isinstance(columns, list):
            entries = []
            for item in columns:
                if not isinstance(item, Mapping) or set(item) != {"name", "expr"}:
                    raise FieldProgramError("sequence project column is invalid")
                entries.append((item["name"], item["expr"]))
        else:
            raise FieldProgramError("sequence project columns are invalid")
        if not entries or len(entries) > _SEQUENCE_MAX_COLUMNS:
            raise FieldProgramError("sequence project columns exceed their bound")
        names = [
            _semantic_program_identifier(name, "sequence projected column")
            for name, _expr in entries
        ]
        if names != sorted(set(names)):
            raise FieldProgramError("sequence projected columns are not canonical")
        return {
            "op": "project",
            "columns": {
                name: _canonical_sequence_expr(expr, depth + 1, nodes)
                for name, (_original, expr) in zip(names, entries)
            },
        }
    if op == "filter":
        if set(raw) != {"op", "predicate"}:
            raise FieldProgramError("sequence filter stage is invalid")
        return {
            "op": "filter",
            "predicate": _canonical_sequence_predicate(raw["predicate"], depth + 1, nodes),
        }
    if op == "distinct":
        if set(raw) != {"op"}:
            raise FieldProgramError("sequence distinct stage is invalid")
        return {"op": "distinct"}
    if op == "order":
        if set(raw) not in ({"op", "expression", "direction", "nulls"}, {"op", "by", "direction", "nulls"}):
            raise FieldProgramError("sequence order stage is invalid")
        expression = raw.get("expression", raw.get("by"))
        direction = raw["direction"]
        nulls = raw["nulls"]
        if direction not in {"asc", "desc"} or nulls not in {"first", "last"}:
            raise FieldProgramError("sequence order direction or null placement is invalid")
        return {
            "op": "order",
            "expression": _canonical_sequence_expr(expression, depth + 1, nodes),
            "direction": direction,
            "nulls": nulls,
        }
    if op == "limit":
        if set(raw) != {"op", "count"}:
            raise FieldProgramError("sequence limit stage is invalid")
        count = _integer(raw["count"], "sequence limit", minimum=0, maximum=_SEQUENCE_MAX_ROWS)
        return {"op": "limit", "count": count}
    raise FieldProgramError(f"sequence stage operation {op!r} is unsupported")


def _canonical_sequence_ast(raw: Any, depth: int = 0, nodes: list[int] | None = None) -> dict[str, Any]:
    nodes = [0] if nodes is None else nodes
    if depth > _SEQUENCE_MAX_AST_DEPTH:
        raise FieldProgramError("sequence AST depth exceeds its bound")
    if not isinstance(raw, Mapping) or not isinstance(raw.get("op"), str):
        raise FieldProgramError("sequence AST node must have an op")
    nodes[0] += 1
    if nodes[0] > _SEQUENCE_MAX_AST_NODES:
        raise FieldProgramError("sequence AST exceeds its node bound")
    op = raw["op"]
    if op == "source":
        if set(raw) != {"op"}:
            raise FieldProgramError("sequence source node is invalid")
        return {"op": "source"}
    if op != "pipeline" or set(raw) != {"op", "input", "stages"}:
        raise FieldProgramError("sequence AST pipeline node is invalid")
    stages = raw["stages"]
    if not isinstance(stages, list) or len(stages) > _SEQUENCE_MAX_STAGES:
        raise FieldProgramError("sequence stages exceed their bound")
    return {
        "op": "pipeline",
        "input": _canonical_sequence_ast(raw["input"], depth + 1, nodes),
        "stages": [
            _canonical_sequence_stage(stage, depth + 1, nodes)
            for stage in stages
        ],
    }


def _canonical_sequence_body(value: Mapping[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or value.get("schema") != SEMANTIC_SEQUENCE_SCHEMA
        or set(value) not in ({"schema", "ast"}, {"schema", "ast", "ast_parameter"})
    ):
        raise FieldProgramError("sequence program body has invalid schema or keys")
    detached = _semantic_program_plain(dict(value), "sequence program body")
    result = {
        "schema": SEMANTIC_SEQUENCE_SCHEMA,
        "ast": _canonical_sequence_ast(detached["ast"]),
    }
    if "ast_parameter" in detached:
        parameter = detached["ast_parameter"]
        result["ast_parameter"] = _semantic_program_identifier(
            parameter, "sequence AST parameter"
        )
    return result



class _SequenceExhausted(Exception):
    pass


class _SequenceSupportGap(Exception):
    def __init__(self, limitation: str):
        super().__init__(limitation)
        self.limitation = limitation


class _SequenceBudget:
    def __init__(self, maximum: int):
        self.maximum = int(maximum)
        self.used = 0

    def charge(self, amount: int = 1) -> None:
        amount = max(1, int(amount))
        self.used += amount
        if self.used > self.maximum:
            raise _SequenceExhausted


def _sequence_cell_value(cell: Mapping[str, Any]) -> int | None:
    return None if cell["kind"] == "null" else int(cell["value"])


def _execute_sequence_program(
    program: Mapping[str, Any],
    action_values: Mapping[str, Any],
) -> dict[str, Any]:
    if "table" not in action_values:
        return {
            "status": "support-gap",
            "values": {},
            "alternatives": [],
            "limitations": ["sequence-table-input-missing"],
            "work": 1,
        }
    table = canonical_table(action_values["table"])
    sequence_ast = program["body"]["ast"]
    ast_parameter = program["body"].get("ast_parameter")
    if ast_parameter is not None:
        if ast_parameter not in action_values:
            return {
                "status": "support-gap",
                "values": {},
                "alternatives": [],
                "limitations": [f"sequence-ast-parameter-missing:{ast_parameter}"],
                "work": 1,
            }
        try:
            sequence_ast = _canonical_sequence_ast(action_values[ast_parameter])
        except (FieldProgramError, TypeError, ValueError):
            return {
                "status": "support-gap",
                "values": {},
                "alternatives": [],
                "limitations": [f"sequence-ast-parameter-invalid:{ast_parameter}"],
                "work": 1,
            }
    budget = _SequenceBudget(int(program["bounds"]["max_work"]))
    initial_rows = [
        (
            tuple(_sequence_cell_value(row[column]) for column in table["columns"]),
            ordinal,
        )
        for ordinal, row in enumerate(table["rows"])
    ]

    def expression(
        raw: Mapping[str, Any],
        columns: Sequence[str],
        values: Sequence[int | None],
    ) -> int | None:
        budget.charge()
        op = raw["op"]
        if op == "column":
            name = raw["name"]
            if name not in columns:
                raise _SequenceSupportGap(f"sequence-column-missing:{name}")
            return values[columns.index(name)]
        if op == "literal":
            return raw["value"]
        for item in raw["args"]:
            result = expression(item, columns, values)
            if result is not None:
                return result
        return None

    def predicate(
        raw: Mapping[str, Any],
        columns: Sequence[str],
        values: Sequence[int | None],
    ) -> bool | None:
        budget.charge()
        if raw["op"] == "is_null":
            return expression(raw["expr"], columns, values) is None
        left = expression(raw["left"], columns, values)
        right = expression(raw["right"], columns, values)
        if left is None or right is None:
            return None
        if raw["op"] == "eq":
            return left == right
        if raw["op"] == "ne":
            return left != right
        if raw["op"] == "lt":
            return left < right
        return left > right

    def pipeline(raw: Mapping[str, Any], depth: int) -> tuple[list[str], list[tuple[tuple[int | None, ...], int]]]:
        if depth > _SEQUENCE_MAX_AST_DEPTH:
            raise FieldProgramError("sequence AST depth exceeds its bound")
        if raw["op"] == "source":
            budget.charge()
            return list(table["columns"]), initial_rows
        columns, rows = pipeline(raw["input"], depth + 1)
        for stage in raw["stages"]:
            op = stage["op"]
            if op == "project":
                next_columns = list(stage["columns"])
                next_rows: list[tuple[tuple[int | None, ...], int]] = []
                for values, ordinal in rows:
                    projected = tuple(
                        expression(stage["columns"][name], columns, values)
                        for name in next_columns
                    )
                    next_rows.append((projected, ordinal))
                budget.charge(len(rows))
                columns, rows = next_columns, next_rows
            elif op == "filter":
                next_rows = []
                for values, ordinal in rows:
                    accepted = predicate(stage["predicate"], columns, values)
                    if accepted is True:
                        next_rows.append((values, ordinal))
                budget.charge(len(rows))
                rows = next_rows
            elif op == "distinct":
                seen: set[tuple[int | None, ...]] = set()
                next_rows = []
                for values, ordinal in rows:
                    if values not in seen:
                        seen.add(values)
                        next_rows.append((values, ordinal))
                budget.charge(len(rows))
                rows = next_rows
            elif op == "order":
                decorated = [
                    (
                        expression(stage["expression"], columns, values),
                        ordinal,
                        values,
                    )
                    for values, ordinal in rows
                ]
                nulls_first = stage["nulls"] == "first"
                direction = stage["direction"]
                decorated.sort(
                    key=lambda item: (
                        (0 if nulls_first else 1) if item[0] is None else (1 if nulls_first else 0),
                        0 if item[0] is None else (item[0] if direction == "asc" else -item[0]),
                        item[1],
                    )
                )
                budget.charge(len(rows))
                rows = [(values, ordinal) for _key, ordinal, values in decorated]
            else:
                count = stage["count"]
                budget.charge(1)
                rows = rows[:count]
        return columns, rows

    try:
        columns, rows = pipeline(sequence_ast, 0)
        output = table_from_rows(
            [dict(zip(columns, values)) for values, _ordinal in rows],
            columns=columns,
        )
    except _SequenceExhausted:
        return {
            "status": "resource-exhausted",
            "values": {},
            "alternatives": [],
            "limitations": ["program-work-bound"],
            "work": budget.maximum,
        }
    except _SequenceSupportGap as exc:
        return {
            "status": "support-gap",
            "values": {},
            "alternatives": [],
            "limitations": [exc.limitation],
            "work": max(1, budget.used),
        }
    return {
        "status": "supported",
        "values": {},
        "alternatives": [],
        "limitations": [],
        "output": output,
        "work": max(1, budget.used),
    }

def _semantic_program_number(
    value: Any, label: str, *, nonnegative: bool = False
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FieldProgramError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (nonnegative and result < 0.0):
        raise FieldProgramError(f"{label} is outside its numeric domain")
    return result
def _semantic_conditional_scalar(value: Any, label: str) -> Any:
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise FieldProgramError(f"{label} must be a finite scalar")


def _canonical_conditional_body(
    body: Mapping[str, Any],
    *,
    nesting_depth: int,
) -> dict[str, Any]:
    if set(body) != {"context_keys", "branches"}:
        raise FieldProgramError("conditional mechanism body has invalid keys")
    context_keys = body["context_keys"]
    branches = body["branches"]
    if (
        not isinstance(context_keys, list)
        or not context_keys
        or len(context_keys) > 8
        or any(
            not isinstance(key, str)
            or not key
            or key.split(".", 1)[0] not in {"state", "action", "context"}
            for key in context_keys
        )
        or context_keys != sorted(set(context_keys))
    ):
        raise FieldProgramError("conditional context keys are invalid")
    if (
        not isinstance(branches, list)
        or not branches
        or len(branches) > _CONDITIONAL_MAX_BRANCHES
    ):
        raise FieldProgramError("conditional mechanism branches are invalid")
    normalized: list[dict[str, Any]] = []
    seen: set[bytes] = set()
    for branch in branches:
        if not isinstance(branch, Mapping) or set(branch) != {"when", "program"}:
            raise FieldProgramError("conditional mechanism branch is invalid")
        when = branch["when"]
        if (
            not isinstance(when, list)
            or len(when) != len(context_keys)
            or any(
                not isinstance(item, Mapping)
                or set(item) != {"key", "value"}
                or item["key"] not in context_keys
                for item in when
            )
            or [item["key"] for item in when] != context_keys
        ):
            raise FieldProgramError("conditional branch context is invalid")
        normalized_when = [
            {
                "key": key,
                "value": _semantic_conditional_scalar(
                    item["value"], "conditional context value"
                ),
            }
            for key, item in zip(context_keys, when)
        ]
        nested = _canonical_semantic_program_payload(
            cast(Mapping[str, Any], branch["program"]),
            nesting_depth=nesting_depth + 1,
        )
        if nested["program_kind"] not in set(SEMANTIC_MECHANISM_KINDS) - {"conditional"}:
            raise FieldProgramError(
                "conditional branch must contain a non-conditional mechanism"
            )
        normalized_branch = {"when": normalized_when, "program": nested}
        marker = _canonical(normalized_when)
        if marker in seen:
            raise FieldProgramError("conditional branch contexts must be unique")
        seen.add(marker)
        normalized.append(normalized_branch)
    normalized.sort(key=lambda item: _canonical(item["when"]))
    return {"context_keys": list(context_keys), "branches": normalized}


def _canonical_context_tree_body(
    body: Mapping[str, Any],
    *,
    nesting_depth: int,
) -> dict[str, Any]:
    if set(body) != {"features", "tree"}:
        raise FieldProgramError("context tree body has invalid keys")
    raw_features = body["features"]
    if (
        not isinstance(raw_features, list)
        or len(raw_features) > _CONTEXT_TREE_MAX_FEATURES
    ):
        raise FieldProgramError("context tree features are invalid")
    features: list[dict[str, Any]] = []
    for raw in raw_features:
        if not isinstance(raw, Mapping):
            raise FieldProgramError("context tree feature is invalid")
        key = raw.get("key")
        kind = raw.get("kind")
        if (
            not isinstance(key, str)
            or len(key.split(".")) < 2
            or key.split(".", 1)[0] not in {"state", "action", "context"}
            or any(not part for part in key.split("."))
            or kind not in {"categorical", "numeric"}
        ):
            raise FieldProgramError("context tree feature identity is invalid")
        if kind == "numeric":
            if set(raw) != {"key", "kind", "maximum", "minimum"}:
                raise FieldProgramError(
                    "numeric context tree feature is invalid"
                )
            minimum = _semantic_program_number(
                raw["minimum"], "context tree numeric minimum"
            )
            maximum = _semantic_program_number(
                raw["maximum"], "context tree numeric maximum"
            )
            if not minimum < maximum:
                raise FieldProgramError(
                    "context tree numeric support must have width"
                )
            features.append(
                {
                    "key": key,
                    "kind": "numeric",
                    "maximum": maximum,
                    "minimum": minimum,
                }
            )
            continue
        if set(raw) != {"key", "kind", "values"}:
            raise FieldProgramError(
                "categorical context tree feature is invalid"
            )
        raw_values = raw["values"]
        if (
            not isinstance(raw_values, list)
            or len(raw_values) < 2
            or len(raw_values) > _CONDITIONAL_MAX_BRANCHES
        ):
            raise FieldProgramError(
                "categorical context tree support is invalid"
            )
        values = [
            _semantic_conditional_scalar(
                value, "context tree categorical value"
            )
            for value in raw_values
        ]
        values.sort(key=_canonical)
        if len({_canonical(value) for value in values}) != len(values):
            raise FieldProgramError(
                "context tree categorical values must be unique"
            )
        features.append(
            {
                "key": key,
                "kind": "categorical",
                "values": values,
            }
        )
    features.sort(key=lambda item: item["key"])
    if len({item["key"] for item in features}) != len(features):
        raise FieldProgramError("context tree feature keys must be unique")
    feature_by_key = {item["key"]: item for item in features}
    leaf_ids: set[str] = set()
    used_keys: set[str] = set()

    def normalize_node(raw: Any, depth: int) -> dict[str, Any]:
        if depth > _CONTEXT_TREE_MAX_DEPTH or not isinstance(raw, Mapping):
            raise FieldProgramError("context tree depth is exhausted")
        kind = raw.get("kind")
        if kind == "leaf":
            if set(raw) != {"kind", "leaf_id", "program"}:
                raise FieldProgramError("context tree leaf is invalid")
            leaf_id = _semantic_program_identifier(
                raw["leaf_id"], "context tree leaf identity"
            )
            if leaf_id in leaf_ids:
                raise FieldProgramError(
                    "context tree leaf identities must be unique"
                )
            leaf_ids.add(leaf_id)
            nested = _canonical_semantic_program_payload(
                cast(Mapping[str, Any], raw["program"]),
                nesting_depth=nesting_depth + 1,
            )
            if nested["program_kind"] not in SEMANTIC_MECHANISM_KINDS:
                raise FieldProgramError(
                    "context tree leaf must contain a bounded mechanism"
                )
            return {
                "kind": "leaf",
                "leaf_id": leaf_id,
                "program": nested,
            }
        if kind != "split" or set(raw) != {
            "kind",
            "match",
            "otherwise",
            "test",
        }:
            raise FieldProgramError("context tree node is invalid")
        test = raw["test"]
        if not isinstance(test, Mapping) or set(test) != {
            "key",
            "operator",
            "value",
        }:
            raise FieldProgramError("context tree split test is invalid")
        key = test["key"]
        operator = test["operator"]
        feature = feature_by_key.get(key)
        if feature is None:
            raise FieldProgramError(
                "context tree split has no feature support"
            )
        used_keys.add(key)
        if feature["kind"] == "numeric":
            if operator != "le":
                raise FieldProgramError(
                    "numeric context tree split must use le"
                )
            value = _semantic_program_number(
                test["value"], "context tree threshold"
            )
            if not feature["minimum"] < value < feature["maximum"]:
                raise FieldProgramError(
                    "context tree threshold is outside feature support"
                )
        else:
            if operator != "eq":
                raise FieldProgramError(
                    "categorical context tree split must use eq"
                )
            value = _semantic_conditional_scalar(
                test["value"], "context tree category"
            )
            if _canonical(value) not in {
                _canonical(item) for item in feature["values"]
            }:
                raise FieldProgramError(
                    "context tree category is outside feature support"
                )
        return {
            "kind": "split",
            "test": {
                "key": key,
                "operator": operator,
                "value": value,
            },
            "match": normalize_node(raw["match"], depth + 1),
            "otherwise": normalize_node(raw["otherwise"], depth + 1),
        }

    tree = normalize_node(body["tree"], 0)
    if len(leaf_ids) > _CONDITIONAL_MAX_BRANCHES:
        raise FieldProgramError("context tree has too many leaves")
    if used_keys != set(feature_by_key):
        raise FieldProgramError(
            "context tree feature support must exactly match its splits"
        )
    return {"features": features, "tree": tree}


def _context_tree_shape(tree: Mapping[str, Any]) -> tuple[int, int]:
    if tree["kind"] == "leaf":
        return 1, 0
    match_leaves, match_depth = _context_tree_shape(tree["match"])
    other_leaves, other_depth = _context_tree_shape(tree["otherwise"])
    return (
        match_leaves + other_leaves,
        1 + max(match_depth, other_depth),
    )



def _canonical_semantic_program_payload(
    value: Mapping[str, Any],
    *,
    nesting_depth: int,
) -> dict[str, Any]:
    """Validate a bounded field-owned representation or mechanism program."""
    if nesting_depth > _SEMANTIC_MECHANISM_MAX_NESTING:
        raise FieldProgramError(
            "semantic mechanism nesting depth is exhausted"
        )

    required = {
        "applicability",
        "arguments",
        "body",
        "bounds",
        "effects",
        "guards",
        "program_kind",
        "schema",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise FieldProgramError("semantic program payload has invalid keys")
    result = _semantic_program_plain(dict(value), "semantic program payload")
    if result["schema"] != SEMANTIC_PROGRAM_SCHEMA:
        raise FieldProgramError("semantic program payload schema is unsupported")
    if result["program_kind"] not in SEMANTIC_PROGRAM_KINDS:
        raise FieldProgramError("semantic program kind is unsupported")
    if not isinstance(result["arguments"], dict):
        raise FieldProgramError("semantic program arguments must be a mapping")
    for name, descriptor in result["arguments"].items():
        _semantic_program_identifier(name, "semantic argument name")
        if not isinstance(descriptor, dict) or set(descriptor) != {
            "required",
            "type",
            "units",
        }:
            raise FieldProgramError(
                "semantic argument descriptor has invalid keys"
            )
        _semantic_program_identifier(
            descriptor["type"], "semantic argument type"
        )
        if not isinstance(descriptor["required"], bool):
            raise FieldProgramError(
                "semantic argument required flag must be boolean"
            )
        if not isinstance(
            descriptor["units"], (dict, str, type(None))
        ):
            raise FieldProgramError("semantic argument units are invalid")
    effects = result["effects"]
    if not isinstance(effects, dict) or set(effects) != {
        "emits",
        "reads",
        "writes",
    }:
        raise FieldProgramError("semantic program effects are invalid")
    for name in ("emits", "reads", "writes"):
        rows = effects[name]
        if (
            not isinstance(rows, list)
            or any(not isinstance(item, str) or not item for item in rows)
            or rows != sorted(set(rows))
        ):
            raise FieldProgramError(
                f"semantic program {name} footprint is not canonical"
            )
    guards = result["guards"]
    if not isinstance(guards, list):
        raise FieldProgramError("semantic program guards must be a list")
    for guard in guards:
        if (
            not isinstance(guard, dict)
            or set(guard) != {"left", "op", "right"}
            or guard["op"] not in {
                "eq",
                "ge",
                "gt",
                "in",
                "le",
                "lt",
                "ne",
                "not-in",
            }
        ):
            raise FieldProgramError("semantic program guard is invalid")
        _semantic_program_identifier(
            guard["left"], "semantic guard operand"
        )
    bounds = result["bounds"]
    if not isinstance(bounds, dict) or set(bounds) != {
        "max_branches",
        "max_horizon",
        "max_work",
    }:
        raise FieldProgramError("semantic program bounds are invalid")
    for name in ("max_branches", "max_horizon", "max_work"):
        _integer(
            bounds[name],
            f"semantic program {name}",
            minimum=1,
            maximum=1_000_000,
        )
    if not isinstance(result["body"], dict):
        raise FieldProgramError("semantic program body must be a mapping")
    if result["program_kind"] == "sequence":
        result["body"] = _canonical_sequence_body(result["body"])
    if result["program_kind"] == "conditional":
        result["body"] = _canonical_conditional_body(
            result["body"], nesting_depth=nesting_depth
        )
    if result["program_kind"] == "context-tree":
        result["body"] = _canonical_context_tree_body(
            result["body"], nesting_depth=nesting_depth
        )
    if (
        result["program_kind"] == "procedure"
        and "surface_contract" in result["body"]
    ):
        body = result["body"]
        body["surface_contract"] = _canonical_surface_contract(
            body["surface_contract"], bounds=result["bounds"]
        )
    if not isinstance(result["applicability"], dict):
        raise FieldProgramError(
            "semantic program applicability must be a mapping"
        )
    return result


def canonical_semantic_program_payload(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a bounded field-owned representation or mechanism program."""

    return _canonical_semantic_program_payload(value, nesting_depth=0)


def semantic_program_payload(
    *,
    program_kind: str,
    body: Mapping[str, Any],
    arguments: Mapping[str, Mapping[str, Any]] | None = None,
    guards: Sequence[Mapping[str, Any]] = (),
    reads: Sequence[str] = (),
    writes: Sequence[str] = (),
    emits: Sequence[str] = (),
    max_work: int = MECHANISM_STEP_MAX_WORK,
    max_horizon: int = 1,
    max_branches: int = 64,
    applicability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a canonical typed program payload for a semantic record."""

    return canonical_semantic_program_payload(
        {
            "schema": SEMANTIC_PROGRAM_SCHEMA,
            "program_kind": program_kind,
            "arguments": {
                str(name): {
                    "required": bool(descriptor.get("required", True)),
                    "type": str(descriptor.get("type", "json")),
                    "units": descriptor.get("units"),
                }
                for name, descriptor in dict(arguments or {}).items()
            },
            "effects": {
                "reads": sorted(set(reads)),
                "writes": sorted(set(writes)),
                "emits": sorted(set(emits)),
            },
            "guards": [dict(guard) for guard in guards],
            "bounds": {
                "max_work": max_work,
                "max_horizon": max_horizon,
                "max_branches": max_branches,
            },
            "body": dict(body),
            "applicability": dict(applicability or {}),
        }
    )


def _semantic_lookup(
    name: str,
    state: Mapping[str, Any],
    action: Mapping[str, Any],
    context: Mapping[str, Any],
) -> tuple[bool, Any]:
    roots = {"state": state, "action": action, "context": context}
    parts = name.split(".")
    if parts[0] in roots:
        current: Any = roots[parts.pop(0)]
    else:
        current = state
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _semantic_guard(
    guard: Mapping[str, Any],
    state: Mapping[str, Any],
    action: Mapping[str, Any],
    context: Mapping[str, Any],
) -> tuple[bool, bool]:
    available, left = _semantic_lookup(
        str(guard["left"]), state, action, context
    )
    if not available:
        return False, False
    right = guard["right"]
    operation = guard["op"]
    try:
        if operation == "eq":
            return True, left == right
        if operation == "ne":
            return True, left != right
        if operation == "in":
            return True, left in right
        if operation == "not-in":
            return True, left not in right
        left_number = _semantic_program_number(left, "guard left operand")
        right_number = _semantic_program_number(
            right, "guard right operand"
        )
        if operation == "lt":
            return True, left_number < right_number
        if operation == "le":
            return True, left_number <= right_number
        if operation == "gt":
            return True, left_number > right_number
        if operation == "ge":
            return True, left_number >= right_number
    except (TypeError, ValueError):
        return False, False
    raise FieldProgramError("semantic guard operation is unsupported")


def canonical_semantic_representation_edits(
    value: Any,
) -> list[dict[str, Any]]:
    """Validate the closed typed edit grammar used by learned representations."""

    if not isinstance(value, list) or len(value) > 128:
        raise FieldProgramError("representation edits must be a bounded list")
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise FieldProgramError(f"representation edit {index} must be a mapping")
        edit = _semantic_program_plain(
            dict(raw), f"representation edit {index}"
        )
        family = edit.get("family")
        if family == "observed-role":
            if (
                set(edit) != {"family", "mode", "roles"}
                or edit["mode"] not in {"include", "exclude"}
                or not isinstance(edit["roles"], list)
                or not edit["roles"]
            ):
                raise FieldProgramError("observed-role edit is invalid")
            roles = [
                _semantic_program_identifier(role, "observed role")
                for role in edit["roles"]
            ]
            if roles != sorted(set(roles)):
                raise FieldProgramError(
                    "observed roles must be sorted and unique"
                )
            edit["roles"] = roles
        elif family == "relational-variable":
            if set(edit) != {
                "family",
                "guard",
                "relation",
                "sources",
                "target",
                "tolerance",
                "units",
            }:
                raise FieldProgramError("relational-variable edit is invalid")
            relation = edit["relation"]
            arity = {
                "contact": 2,
                "difference": 2,
                "distance": 2,
                "equal": 2,
                "order": 2,
                "product": None,
                "rate": 2,
                "ratio": 2,
                "sum": None,
            }.get(relation)
            if relation not in {
                "contact",
                "difference",
                "distance",
                "equal",
                "order",
                "product",
                "rate",
                "ratio",
                "sum",
            }:
                raise FieldProgramError("relational-variable relation is invalid")
            sources = edit["sources"]
            if (
                not isinstance(sources, list)
                or not sources
                or (arity is not None and len(sources) != arity)
            ):
                raise FieldProgramError(
                    "relational-variable source arity is invalid"
                )
            edit["sources"] = [
                _semantic_program_identifier(source, "relation source")
                for source in sources
            ]
            edit["target"] = _semantic_program_identifier(
                edit["target"], "relation target"
            )
            edit["tolerance"] = _semantic_program_number(
                edit["tolerance"], "relation tolerance", nonnegative=True
            )
            if edit["units"] is not None and not isinstance(
                edit["units"], (str, dict)
            ):
                raise FieldProgramError("relation units are invalid")
            guard = edit["guard"]
            if guard is not None and (
                not isinstance(guard, dict)
                or set(guard) != {"left", "op", "right"}
                or guard["op"]
                not in {"eq", "ge", "gt", "in", "le", "lt", "ne", "not-in"}
            ):
                raise FieldProgramError("relation guard is invalid")
        elif family == "context":
            if set(edit) != {
                "cases",
                "default",
                "family",
                "source",
                "target",
            }:
                raise FieldProgramError("context edit is invalid")
            if (
                not isinstance(edit["cases"], list)
                or not edit["cases"]
                or any(
                    not isinstance(row, dict)
                    or set(row) != {"equals", "label"}
                    for row in edit["cases"]
                )
            ):
                raise FieldProgramError("context cases are invalid")
            edit["source"] = _semantic_program_identifier(
                edit["source"], "context source"
            )
            edit["target"] = _semantic_program_identifier(
                edit["target"], "context target"
            )
        elif family == "factor-scope":
            if (
                set(edit) != {"family", "relation", "sources", "target"}
                or edit["relation"]
                not in {"all-equal", "exactly-one", "exclusion", "xor"}
                or not isinstance(edit["sources"], list)
                or len(edit["sources"]) < 2
            ):
                raise FieldProgramError("factor-scope edit is invalid")
            edit["sources"] = [
                _semantic_program_identifier(source, "factor source")
                for source in edit["sources"]
            ]
            edit["target"] = _semantic_program_identifier(
                edit["target"], "factor target"
            )
        elif family == "latent-alternative":
            if (
                set(edit)
                != {
                    "alternatives",
                    "family",
                    "observation_consequences",
                    "target",
                }
                or not isinstance(edit["alternatives"], list)
                or len(edit["alternatives"]) < 2
                or not isinstance(edit["observation_consequences"], dict)
            ):
                raise FieldProgramError("latent-alternative edit is invalid")
            edit["target"] = _semantic_program_identifier(
                edit["target"], "latent alternative target"
            )
            alternative_keys = {_canonical(row) for row in edit["alternatives"]}
            if len(alternative_keys) != len(edit["alternatives"]):
                raise FieldProgramError("latent alternatives must be unique")
        elif family == "compose-mechanisms":
            if (
                set(edit)
                != {
                    "family",
                    "output",
                    "programs",
                    "target",
                    "time_rule",
                    "units_rule",
                }
                or not isinstance(edit["programs"], list)
                or not edit["programs"]
                or len(edit["programs"]) > 8
            ):
                raise FieldProgramError("mechanism composition edit is invalid")
            edit["programs"] = [
                canonical_semantic_program_payload(program)
                for program in edit["programs"]
            ]
            edit["output"] = _semantic_program_identifier(
                edit["output"], "mechanism composition output"
            )
            edit["target"] = _semantic_program_identifier(
                edit["target"], "mechanism composition target"
            )
            for name in ("time_rule", "units_rule"):
                edit[name] = _semantic_program_identifier(
                    edit[name], f"mechanism composition {name}"
                )
        elif family == "scale":
            if (
                set(edit)
                != {
                    "boundary",
                    "factor",
                    "family",
                    "reducer",
                    "sources",
                    "target",
                }
                or edit["boundary"] not in {"preserve", "refuse"}
                or edit["reducer"]
                not in {"first", "last", "max", "mean", "min", "sum"}
                or not isinstance(edit["sources"], list)
                or not edit["sources"]
            ):
                raise FieldProgramError("scale edit is invalid")
            edit["sources"] = [
                _semantic_program_identifier(source, "scale source")
                for source in edit["sources"]
            ]
            edit["target"] = _semantic_program_identifier(
                edit["target"], "scale target"
            )
            edit["factor"] = _semantic_program_number(
                edit["factor"], "scale factor"
            )
        elif family == "symmetry":
            if (
                set(edit)
                != {"claim", "family", "operator", "sources", "target"}
                or edit["claim"] not in {"empirical", "exact"}
                or edit["operator"]
                not in {"absolute-difference", "cyclic-min", "sorted-tuple"}
                or not isinstance(edit["sources"], list)
                or not edit["sources"]
            ):
                raise FieldProgramError("symmetry edit is invalid")
            edit["sources"] = [
                _semantic_program_identifier(source, "symmetry source")
                for source in edit["sources"]
            ]
            edit["target"] = _semantic_program_identifier(
                edit["target"], "symmetry target"
            )
        else:
            raise FieldProgramError("representation edit family is unsupported")
        result.append(edit)
    return result


def apply_semantic_representation_edits(
    features: Mapping[str, Any],
    edits: Sequence[Mapping[str, Any]],
    *,
    action: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a bounded representation program without inventing observations."""

    normalized = canonical_semantic_representation_edits(list(edits))
    values = _semantic_program_plain(dict(features), "representation features")
    action_values = _semantic_program_plain(
        dict(action or {}), "representation action"
    )
    context_values = _semantic_program_plain(
        dict(context or {}), "representation context"
    )
    if not all(
        isinstance(item, dict)
        for item in (values, action_values, context_values)
    ):
        raise FieldProgramError("representation operands must be mappings")
    limitations: list[str] = []
    work = 0

    def source_values(edit: Mapping[str, Any]) -> list[Any] | None:
        result: list[Any] = []
        for source in edit["sources"]:
            present, value = _semantic_lookup(
                source, values, action_values, context_values
            )
            if not present:
                limitations.append(f"representation-source-missing:{source}")
                return None
            result.append(value)
        return result

    for edit in normalized:
        family = edit["family"]
        work += 1
        if family == "observed-role":
            if edit["mode"] == "include":
                for role in edit["roles"]:
                    present, _ = _semantic_lookup(
                        role, values, action_values, context_values
                    )
                    if not present:
                        limitations.append(
                            f"representation-role-missing:{role}"
                        )
            else:
                for role in edit["roles"]:
                    values.pop(role, None)
            continue
        if family == "relational-variable":
            guard = edit["guard"]
            if guard is not None:
                known, accepted = _semantic_guard(
                    guard, values, action_values, context_values
                )
                if not known:
                    limitations.append("representation-guard-unknown")
                    continue
                if not accepted:
                    limitations.append("representation-guard-false")
                    continue
            operands = source_values(edit)
            if operands is None:
                continue
            relation = edit["relation"]
            tolerance = float(edit["tolerance"])
            try:
                if relation == "equal":
                    result: Any = operands[0] == operands[1]
                elif relation == "order":
                    result = (
                        -1
                        if operands[0] < operands[1]
                        else (1 if operands[0] > operands[1] else 0)
                    )
                elif relation in {"distance", "contact"}:
                    if all(
                        isinstance(item, Sequence)
                        and not isinstance(item, (str, bytes))
                        for item in operands
                    ):
                        left = list(operands[0])
                        right = list(operands[1])
                        if len(left) != len(right):
                            raise ValueError
                        distance = math.sqrt(
                            sum(
                                (
                                    _semantic_program_number(
                                        first, "relation coordinate"
                                    )
                                    - _semantic_program_number(
                                        second, "relation coordinate"
                                    )
                                )
                                ** 2
                                for first, second in zip(
                                    left, right, strict=True
                                )
                            )
                        )
                    else:
                        distance = abs(
                            _semantic_program_number(
                                operands[0], "relation source"
                            )
                            - _semantic_program_number(
                                operands[1], "relation source"
                            )
                        )
                    result = (
                        distance <= tolerance
                        if relation == "contact"
                        else distance
                    )
                else:
                    numbers = [
                        _semantic_program_number(item, "relation source")
                        for item in operands
                    ]
                    if relation == "difference":
                        result = numbers[0] - numbers[1]
                    elif relation == "sum":
                        result = sum(numbers)
                    elif relation == "product":
                        result = math.prod(numbers)
                    else:
                        if abs(numbers[1]) <= tolerance:
                            limitations.append(
                                "representation-nonzero-guard-failed"
                            )
                            continue
                        result = numbers[0] / numbers[1]
            except (TypeError, ValueError):
                limitations.append("representation-relation-type")
                continue
            values[edit["target"]] = result
            continue
        if family == "context":
            present, source = _semantic_lookup(
                edit["source"], values, action_values, context_values
            )
            if not present:
                limitations.append(
                    f"representation-source-missing:{edit['source']}"
                )
                continue
            selected = next(
                (
                    row["label"]
                    for row in edit["cases"]
                    if source == row["equals"]
                ),
                edit["default"],
            )
            values[edit["target"]] = selected
            continue
        if family == "factor-scope":
            operands = source_values(edit)
            if operands is None:
                continue
            bits = []
            for operand in operands:
                if isinstance(operand, bool):
                    bits.append(operand)
                elif (
                    isinstance(operand, int)
                    and not isinstance(operand, bool)
                    and operand in (0, 1)
                ):
                    bits.append(bool(operand))
                else:
                    limitations.append("representation-factor-domain")
                    break
            else:
                relation = edit["relation"]
                values[edit["target"]] = (
                    sum(bits) % 2 == 1
                    if relation == "xor"
                    else (
                        sum(bits) == 1
                        if relation == "exactly-one"
                        else (
                            sum(bits) <= 1
                            if relation == "exclusion"
                            else len(set(bits)) == 1
                        )
                    )
                )
            continue
        if family == "latent-alternative":
            values[edit["target"]] = {
                "alternatives": edit["alternatives"],
                "epistemic_kind": "hypothesized",
                "observation_consequences": edit[
                    "observation_consequences"
                ],
            }
            continue
        if family == "compose-mechanisms":
            composed = dict(values)
            for program in edit["programs"]:
                outcome = execute_semantic_program(
                    program,
                    composed,
                    action=action_values,
                    context=context_values,
                )
                work += int(outcome["work"])
                if (
                    outcome["status"] != "supported"
                    or outcome.get("proposed_actions")
                ):
                    limitations.append(
                        "representation-mechanism-composition-unsupported"
                    )
                    break
                composed = dict(outcome["values"])
            else:
                present, output = _semantic_lookup(
                    edit["output"], composed, action_values, context_values
                )
                if present:
                    values[edit["target"]] = output
                else:
                    limitations.append(
                        "representation-composition-output-missing"
                    )
            continue
        if family == "scale":
            operands = source_values(edit)
            if operands is None:
                continue
            try:
                numbers = [
                    _semantic_program_number(item, "scale source")
                    for item in operands
                ]
            except (TypeError, ValueError):
                limitations.append("representation-scale-type")
                continue
            reducer = edit["reducer"]
            reduced = (
                numbers[0]
                if reducer == "first"
                else (
                    numbers[-1]
                    if reducer == "last"
                    else (
                        max(numbers)
                        if reducer == "max"
                        else (
                            min(numbers)
                            if reducer == "min"
                            else (
                                sum(numbers) / len(numbers)
                                if reducer == "mean"
                                else sum(numbers)
                            )
                        )
                    )
                )
            )
            values[edit["target"]] = reduced * float(edit["factor"])
            continue
        operands = source_values(edit)
        if operands is None:
            continue
        operator = edit["operator"]
        if operator == "absolute-difference":
            if len(operands) != 2:
                limitations.append("representation-symmetry-arity")
                continue
            try:
                symmetric: Any = abs(
                    _semantic_program_number(
                        operands[0], "symmetry source"
                    )
                    - _semantic_program_number(
                        operands[1], "symmetry source"
                    )
                )
            except (TypeError, ValueError):
                limitations.append("representation-symmetry-type")
                continue
        elif operator == "sorted-tuple":
            symmetric = sorted(operands, key=_canonical)
        else:
            rotations = [
                operands[index:] + operands[:index]
                for index in range(len(operands))
            ]
            symmetric = min(rotations, key=_canonical)
        values[edit["target"]] = symmetric
    return {
        "status": "supported" if not limitations else "support-gap",
        "values": values,
        "limitations": sorted(set(limitations)),
        "work": max(1, work),
    }


def _semantic_procedure_substitute(
    value: Any, bindings: Mapping[str, Any]
) -> tuple[bool, Any]:
    if isinstance(value, Mapping):
        if set(value) == {"$role"}:
            role = value["$role"]
            if not isinstance(role, str) or role not in bindings:
                return False, None
            return True, _semantic_program_plain(
                bindings[role], "procedure role binding"
            )
        result: dict[str, Any] = {}
        for key, item in value.items():
            available, substituted = _semantic_procedure_substitute(
                item, bindings
            )
            if not available:
                return False, None
            result[str(key)] = substituted
        return True, result
    if isinstance(value, list):
        result_list: list[Any] = []
        for item in value:
            available, substituted = _semantic_procedure_substitute(
                item, bindings
            )
            if not available:
                return False, None
            result_list.append(substituted)
        return True, result_list
    return True, value


def _semantic_select_procedure_branch(
    value: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    maximum: int,
) -> Mapping[str, Any] | None:
    """Select one bounded contingent procedure step from current context."""

    if "branches" not in value:
        return value
    if set(value) - {"branches", "default"}:
        raise FieldProgramError("procedure branch wrapper has invalid keys")
    branches = value["branches"]
    if (
        not isinstance(branches, list)
        or not branches
        or len(branches) > maximum
    ):
        raise FieldProgramError("procedure branches are invalid")
    matches: list[tuple[int, Mapping[str, Any]]] = []
    for index, branch in enumerate(branches):
        if (
            not isinstance(branch, Mapping)
            or set(branch) != {"step", "when"}
            or not isinstance(branch["when"], Mapping)
            or not isinstance(branch["step"], Mapping)
        ):
            raise FieldProgramError("procedure branch is invalid")
        accepted = True
        for path, expected in branch["when"].items():
            if not isinstance(path, str) or not path:
                raise FieldProgramError("procedure branch condition is invalid")
            available, actual = _semantic_lookup(
                path, state, action, context
            )
            if not available or actual != expected:
                accepted = False
                break
        if accepted:
            matches.append((index, branch["step"]))
    if len(matches) > 1:
        raise FieldProgramError("procedure branches are ambiguous")
    if matches:
        branch_index, selected = matches[0]
        return {
            **dict(selected),
            "branch_index": branch_index,
        }
    default = value.get("default")
    if default is None:
        return None
    if not isinstance(default, Mapping):
        raise FieldProgramError("procedure default branch is invalid")
    return {
        **dict(default),
        "branch_index": None,
    }


def _surface_condition(
    condition: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
    action: Mapping[str, Any],
    context: Mapping[str, Any],
) -> bool | None:
    available, actual = _semantic_lookup(
        condition["path"], state, action, context
    )
    operation = condition["op"]
    if operation == "exists":
        return available
    if operation == "missing":
        return not available
    if not available:
        return None
    expected = condition["value"]
    if operation == "eq":
        return _canonical(actual) == _canonical(expected)
    if operation == "ne":
        return _canonical(actual) != _canonical(expected)
    if operation in {"in", "not-in"}:
        if not isinstance(expected, list):
            raise FieldProgramError("surface membership condition is invalid")
        matched = _canonical(actual) in {_canonical(item) for item in expected}
        return matched if operation == "in" else not matched
    if isinstance(actual, bool) or isinstance(expected, bool):
        return None
    if not isinstance(actual, (int, float)) or not isinstance(
        expected, (int, float)
    ):
        return None
    if operation == "lt":
        return actual < expected
    if operation == "le":
        return actual <= expected
    if operation == "gt":
        return actual > expected
    if operation == "ge":
        return actual >= expected
    raise FieldProgramError("surface condition operation is invalid")


def _surface_conditions(
    conditions: Sequence[Mapping[str, Any]],
    *,
    state: Mapping[str, Any],
    action: Mapping[str, Any],
    context: Mapping[str, Any],
) -> bool | None:
    unknown = False
    for condition in conditions:
        result = _surface_condition(
            condition, state=state, action=action, context=context
        )
        if result is False:
            return False
        if result is None:
            unknown = True
    return None if unknown else True


def advance_surface_procedure(
    payload: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
    bindings: Mapping[str, Any],
    context: Mapping[str, Any],
    cursor: Mapping[str, Any] | None = None,
    maximum_work: int = 32,
    complete_pending: bool = False,
) -> dict[str, Any]:
    """Advance one bounded field-owned surface procedure control slice.

    This function only returns an intention description. It never calls a
    surface backend or treats its own proposed action as an external effect.
    """

    program = canonical_semantic_program_payload(payload)
    if program["program_kind"] != "procedure":
        raise FieldProgramError("surface execution requires a procedure program")
    body = program["body"]
    contract = body.get("surface_contract")
    if not isinstance(contract, Mapping):
        raise FieldProgramError("procedure has no surface contract")
    if (
        isinstance(maximum_work, bool)
        or not isinstance(maximum_work, int)
        or not 1 <= maximum_work <= int(program["bounds"]["max_work"])
    ):
        raise FieldProgramError("surface procedure work quantum is invalid")
    state_values = _semantic_program_plain(dict(state), "surface procedure state")
    action_values = _semantic_program_plain(
        dict(bindings), "surface procedure bindings"
    )
    context_values = _semantic_program_plain(
        dict(context), "surface procedure context"
    )
    if not all(
        isinstance(item, dict)
        for item in (state_values, action_values, context_values)
    ):
        raise FieldProgramError("surface procedure operands must be mappings")
    for name, descriptor in program["arguments"].items():
        if descriptor["required"] and name not in action_values:
            return {
                "cursor": None,
                "intent": None,
                "limitations": [f"missing-argument:{name}"],
                "status": "support-gap",
                "work": 1,
            }
        if name not in action_values:
            continue
        value = action_values[name]
        expected = descriptor["type"]
        matches = (
            expected == "json"
            or (expected == "boolean" and isinstance(value, bool))
            or (
                expected == "integer"
                and isinstance(value, int)
                and not isinstance(value, bool)
            )
            or (
                expected == "number"
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            )
            or (expected == "string" and isinstance(value, str))
            or (expected == "mapping" and isinstance(value, Mapping))
            or (expected == "list" and isinstance(value, list))
        )
        if not matches:
            return {
                "cursor": None,
                "intent": None,
                "limitations": [f"argument-type:{name}:{expected}"],
                "status": "support-gap",
                "work": 1,
            }
    for guard in program["guards"]:
        known, accepted = _semantic_guard(
            guard, state_values, action_values, context_values
        )
        if not known or not accepted:
            return {
                "cursor": None,
                "intent": None,
                "limitations": ["guard-unknown" if not known else "guard-false"],
                "status": "support-gap",
                "work": 1,
            }
    available, substituted_contract = _semantic_procedure_substitute(
        contract, action_values
    )
    if not available or not isinstance(substituted_contract, Mapping):
        return {
            "cursor": None,
            "intent": None,
            "limitations": ["procedure-role-binding-missing"],
            "status": "support-gap",
            "work": 1,
        }
    conditions = cast(
        Sequence[Mapping[str, Any]], substituted_contract["applicability"]
    )
    applicability = _surface_conditions(
        conditions,
        state=state_values,
        action=action_values,
        context=context_values,
    )
    if applicability is not True:
        return {
            "cursor": None,
            "intent": None,
            "limitations": [
                "procedure-applicability-unknown"
                if applicability is None
                else "procedure-not-applicable"
            ],
            "status": "support-gap",
            "work": 1,
        }
    def normalize_frame(raw_frame: Any, depth: int = 0) -> dict[str, Any]:
        if (
            depth > _SEQUENCE_MAX_AST_DEPTH
            or not isinstance(raw_frame, Mapping)
            or set(raw_frame)
            - {
                "active_branch",
                "branch_states",
                "index",
                "iteration",
                "next_branch",
                "node",
                "started_ns",
            }
        ):
            raise FieldProgramError(
                "surface procedure checkpoint frame is invalid"
            )
        node = _canonical_surface_control(
            raw_frame.get("node"),
            depth=0,
            counter=[0],
            bounds=program["bounds"],
        )
        normalized = {
            "index": _integer(
                raw_frame.get("index", 0),
                "surface procedure frame index",
                minimum=0,
                maximum=int(program["bounds"]["max_horizon"]),
            ),
            "iteration": _integer(
                raw_frame.get("iteration", 0),
                "surface procedure loop cursor",
                minimum=0,
                maximum=int(program["bounds"]["max_horizon"]),
            ),
            "node": node,
        }
        if "started_ns" in raw_frame:
            normalized["started_ns"] = _integer(
                raw_frame["started_ns"],
                "surface procedure wait start",
                minimum=0,
                maximum=9_007_199_254_740_991,
            )
        parallel_keys = {"active_branch", "branch_states", "next_branch"}
        if "branch_states" in raw_frame:
            if node["op"] != "parallel" or not parallel_keys <= set(raw_frame):
                raise FieldProgramError(
                    "surface parallel checkpoint frame is invalid"
                )
            raw_branches = raw_frame["branch_states"]
            branch_nodes = node["branches"]
            if not isinstance(raw_branches, list) or len(raw_branches) != len(
                branch_nodes
            ):
                raise FieldProgramError(
                    "surface parallel checkpoint branches are invalid"
                )
            active = raw_frame["active_branch"]
            if active is not None:
                active = _integer(
                    active,
                    "surface parallel active branch",
                    minimum=0,
                    maximum=len(branch_nodes) - 1,
                )
            next_branch = _integer(
                raw_frame["next_branch"],
                "surface parallel next branch",
                minimum=0,
                maximum=len(branch_nodes) - 1,
            )
            branch_states = []
            for index, raw_branch in enumerate(raw_branches):
                if (
                    not isinstance(raw_branch, Mapping)
                    or set(raw_branch)
                    != {"branch_digest", "stack", "status", "wait_status"}
                    or raw_branch["branch_digest"]
                    != sha256_value(branch_nodes[index])
                    or not isinstance(raw_branch["stack"], list)
                    or len(raw_branch["stack"])
                    > int(program["bounds"]["max_horizon"])
                ):
                    raise FieldProgramError(
                        "surface parallel branch checkpoint is invalid"
                    )
                status = raw_branch["status"]
                wait_status = raw_branch["wait_status"]
                if not isinstance(status, str) or status not in {
                    "complete",
                    "ready",
                    "running",
                    "waiting",
                }:
                    raise FieldProgramError(
                        "surface parallel branch status is invalid"
                    )
                if (
                    wait_status is not None
                    and (
                        not isinstance(wait_status, str)
                        or wait_status
                        not in {"awaiting-observation", "waiting"}
                    )
                ):
                    raise FieldProgramError(
                        "surface parallel branch wait status is invalid"
                    )
                if (status == "waiting") != (wait_status is not None):
                    raise FieldProgramError(
                        "surface parallel branch wait status is invalid"
                    )
                if status == "running" and (
                    active != index or raw_branch["stack"]
                ):
                    raise FieldProgramError(
                        "surface parallel active branch is invalid"
                    )
                if status != "running" and active == index:
                    raise FieldProgramError(
                        "surface parallel active branch state is invalid"
                    )
                if status in {"complete", "running"} and raw_branch["stack"]:
                    raise FieldProgramError(
                        "surface parallel branch stack is invalid"
                    )
                if status in {"ready", "waiting"} and not raw_branch["stack"]:
                    raise FieldProgramError(
                        "surface parallel runnable branch has no cursor"
                    )
                branch_states.append(
                    {
                        "branch_digest": raw_branch["branch_digest"],
                        "stack": [
                            normalize_frame(frame, depth + 1)
                            for frame in raw_branch["stack"]
                        ],
                        "status": status,
                        "wait_status": wait_status,
                    }
                )
            if (active is None) != all(
                branch["status"] != "running" for branch in branch_states
            ):
                raise FieldProgramError(
                    "surface parallel active branch identity is invalid"
                )
            normalized.update(
                {
                    "active_branch": active,
                    "branch_states": branch_states,
                    "next_branch": next_branch,
                }
            )
        elif parallel_keys & set(raw_frame):
            raise FieldProgramError(
                "surface parallel checkpoint frame is incomplete"
            )
        return normalized

    if cursor is None:
        control = substituted_contract["control_flow"]
        current: dict[str, Any] = {
            "completed_intentions": 0,
            "stack": [{"index": 0, "iteration": 0, "node": control}],
        }
    else:
        if not isinstance(cursor, Mapping):
            raise FieldProgramError(
                "surface procedure checkpoint cursor is invalid"
            )
        raw_stack = cursor.get("stack")
        completed = cursor.get("completed_intentions", 0)
        if (
            set(cursor) != {"completed_intentions", "stack"}
            or not isinstance(raw_stack, list)
            or isinstance(completed, bool)
            or not isinstance(completed, int)
            or completed < 0
        ):
            raise FieldProgramError("surface procedure checkpoint cursor is invalid")
        current = {
            "completed_intentions": completed,
            "stack": [normalize_frame(frame) for frame in raw_stack],
        }
    if complete_pending:
        if not current["stack"] or current["stack"][-1]["node"]["op"] != "intent":
            raise FieldProgramError(
                "surface procedure has no pending intention to complete"
            )
        current["stack"].pop()
        current["completed_intentions"] += 1
    if current["completed_intentions"] > int(
        substituted_contract["max_intentions"]
    ):
        return {
            "cursor": current,
            "intent": None,
            "limitations": ["procedure-intention-bound"],
            "status": "resource-exhausted",
            "work": 1,
        }
    work = 0
    attempted_parallel: dict[int, set[int]] = {}

    def ensure_parallel_state(
        frame: dict[str, Any],
        active_stack: list[dict[str, Any]] | None = None,
    ) -> None:
        if "branch_states" in frame:
            return
        branches = frame["node"]["branches"]
        previous_index = frame["index"]
        active_index = previous_index - 1 if active_stack else None
        if (
            active_stack
            and (
                active_index is None
                or active_index < 0
                or active_index >= len(branches)
            )
        ):
            raise FieldProgramError(
                "surface parallel active branch cursor is invalid"
            )
        branch_states = []
        for index, branch in enumerate(branches):
            is_active = index == active_index
            complete = index < previous_index and not is_active
            branch_states.append(
                {
                    "branch_digest": sha256_value(branch),
                    "stack": [] if complete or is_active else [
                        {"index": 0, "iteration": 0, "node": branch}
                    ],
                    "status": "complete"
                    if complete
                    else "running"
                    if is_active
                    else "ready",
                    "wait_status": None,
                }
            )
        frame["active_branch"] = active_index
        frame["branch_states"] = branch_states
        frame["next_branch"] = (
            (active_index + 1) % len(branches)
            if active_index is not None
            else previous_index % len(branches)
        )

    def pause_active_parallel_branch(status: str) -> bool:
        stack = current["stack"]
        for position in range(len(stack) - 1, -1, -1):
            frame = stack[position]
            if frame["node"]["op"] != "parallel":
                continue
            if "branch_states" not in frame:
                suffix = stack[position + 1 :]
                if not suffix:
                    continue
                ensure_parallel_state(frame, suffix)
            branch_index = frame["active_branch"]
            if branch_index is None:
                continue
            branch = frame["branch_states"][branch_index]
            suffix = stack[position + 1 :]
            if not suffix:
                branch["status"] = "complete"
                branch["stack"] = []
                branch["wait_status"] = None
            elif status in {"awaiting-observation", "uncertain", "waiting"}:
                branch["status"] = "waiting"
                branch["stack"] = suffix
                branch["wait_status"] = (
                    "waiting" if status == "waiting" else "awaiting-observation"
                )
            else:
                branch["status"] = "ready"
                branch["stack"] = suffix
                branch["wait_status"] = None
            frame["active_branch"] = None
            frame["next_branch"] = (branch_index + 1) % len(
                frame["branch_states"]
            )
            del stack[position + 1 :]
            return True
        return False

    while work < maximum_work:
        work += 1
        if not current["stack"]:
            expected_effect = cast(
                Mapping[str, Any], substituted_contract["expected_effect"]
            )
            observed = _surface_conditions(
                [
                    {"op": "eq", "path": path, "value": value}
                    for path, value in expected_effect.items()
                ],
                state=state_values,
                action=action_values,
                context=context_values,
            )
            status = (
                "complete"
                if observed is True
                else "effect-mismatch"
                if observed is False
                else "awaiting-observation"
            )
            return {
                "cursor": current,
                "intent": None,
                "limitations": [],
                "status": status,
                "work": work,
            }
        frame = current["stack"][-1]
        node = frame["node"]
        op = node["op"]
        if op == "sequence":
            if frame["index"] >= len(node["steps"]):
                current["stack"].pop()
                continue
            selected = node["steps"][frame["index"]]
            frame["index"] += 1
            current["stack"].append(
                {"index": 0, "iteration": 0, "node": selected}
            )
            continue
        if op == "choice":
            matches: list[Mapping[str, Any]] = []
            unresolved = False
            for branch in node["branches"]:
                accepted = _surface_conditions(
                    branch["when"],
                    state=state_values,
                    action=action_values,
                    context=context_values,
                )
                if accepted is None:
                    unresolved = True
                elif accepted:
                    matches.append(branch["then"])
            if unresolved:
                if pause_active_parallel_branch("awaiting-observation"):
                    continue
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": ["procedure-choice-condition-unknown"],
                    "status": "awaiting-observation",
                    "work": work,
                }
            if len(matches) > 1:
                if pause_active_parallel_branch("uncertain"):
                    continue
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": ["procedure-choice-ambiguous"],
                    "status": "uncertain",
                    "work": work,
                }
            selected = matches[0] if matches else node.get("default")
            if not isinstance(selected, Mapping):
                if pause_active_parallel_branch("awaiting-observation"):
                    continue
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": ["procedure-choice-unmatched"],
                    "status": "awaiting-observation",
                    "work": work,
                }
            current["stack"].pop()
            current["stack"].append(
                {"index": 0, "iteration": 0, "node": selected}
            )
            continue
        if op == "loop":
            accepted = _surface_conditions(
                node["while"],
                state=state_values,
                action=action_values,
                context=context_values,
            )
            if accepted is None:
                if pause_active_parallel_branch("awaiting-observation"):
                    continue
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": ["procedure-loop-condition-unknown"],
                    "status": "awaiting-observation",
                    "work": work,
                }
            if not accepted:
                current["stack"].pop()
                continue
            if frame["iteration"] >= node["max_iterations"]:
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": ["procedure-loop-bound"],
                    "status": "resource-exhausted",
                    "work": work,
                }
            frame["iteration"] += 1
            current["stack"].append(
                {"index": 0, "iteration": 0, "node": node["body"]}
            )
            continue
        if op == "wait":
            accepted = _surface_conditions(
                node["until"],
                state=state_values,
                action=action_values,
                context=context_values,
            )
            if accepted is True:
                current["stack"].pop()
                continue
            if accepted is None:
                if pause_active_parallel_branch("awaiting-observation"):
                    continue
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": ["wait-condition-unknown"],
                    "status": "awaiting-observation",
                    "work": work,
                }
            now_ns = context_values.get("now_ns")
            started_ns = frame.get("started_ns")
            if started_ns is None and isinstance(now_ns, int) and not isinstance(
                now_ns, bool
            ):
                frame["started_ns"] = now_ns
                started_ns = now_ns
            timeout_ns = node.get("timeout_ns")
            if (
                timeout_ns is not None
                and isinstance(now_ns, int)
                and not isinstance(now_ns, bool)
                and isinstance(started_ns, int)
                and now_ns - started_ns >= timeout_ns
            ):
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": ["procedure-wait-timeout"],
                    "status": "timed-out",
                    "work": work,
                }
            if pause_active_parallel_branch("waiting"):
                continue
            return {
                "cursor": current,
                "intent": None,
                "limitations": ["procedure-waiting"],
                "status": "waiting",
                "work": work,
            }
        if op == "parallel":
            ensure_parallel_state(frame)
            active = frame["active_branch"]
            if active is not None:
                branch = frame["branch_states"][active]
                if branch["status"] != "running":
                    raise FieldProgramError(
                        "surface parallel active branch state is invalid"
                    )
                branch["status"] = "complete"
                branch["stack"] = []
                branch["wait_status"] = None
                frame["active_branch"] = None
            branch_states = frame["branch_states"]
            if all(branch["status"] == "complete" for branch in branch_states):
                current["stack"].pop()
                continue
            attempted = attempted_parallel.setdefault(id(frame), set())
            selected_index = None
            for offset in range(len(branch_states)):
                candidate_index = (
                    frame["next_branch"] + offset
                ) % len(branch_states)
                if (
                    candidate_index not in attempted
                    and branch_states[candidate_index]["status"]
                    in {"ready", "waiting"}
                ):
                    selected_index = candidate_index
                    break
            if selected_index is not None:
                attempted.add(selected_index)
                branch = branch_states[selected_index]
                branch["status"] = "running"
                branch["wait_status"] = None
                child_stack = branch["stack"]
                branch["stack"] = []
                frame["active_branch"] = selected_index
                frame["next_branch"] = (selected_index + 1) % len(
                    branch_states
                )
                current["stack"].extend(child_stack)
                continue
            wait_statuses = [
                branch["wait_status"]
                for branch in branch_states
                if branch["status"] == "waiting"
            ]
            parallel_status = (
                "awaiting-observation"
                if "awaiting-observation" in wait_statuses
                else "waiting"
                if wait_statuses
                else "yielded"
            )
            if pause_active_parallel_branch(parallel_status):
                continue
            return {
                "cursor": current,
                "intent": None,
                "limitations": [
                    "procedure-parallel-waiting"
                    if wait_statuses
                    else "procedure-work-quantum"
                ],
                "status": parallel_status,
                "work": work,
            }
        if op == "intent":
            if current["completed_intentions"] >= int(
                substituted_contract["max_intentions"]
            ):
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": ["procedure-intention-bound"],
                    "status": "resource-exhausted",
                    "work": work,
                }
            available, intent = _semantic_procedure_substitute(
                node, action_values
            )
            if not available or not isinstance(intent, Mapping):
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": ["procedure-role-binding-missing"],
                    "status": "support-gap",
                    "work": work,
                }
            return {
                "cursor": current,
                "intent": dict(intent),
                "limitations": [],
                "status": "intent",
                "work": work,
            }
        if op == "checkpoint":
            current["stack"].pop()
            pause_active_parallel_branch("checkpoint")
            return {
                "cursor": current,
                "intent": None,
                "limitations": [],
                "status": "checkpoint",
                "work": work,
            }
        if op == "stop":
            conditions = node.get("when")
            accepted = (
                True
                if conditions is None
                else _surface_conditions(
                    conditions,
                    state=state_values,
                    action=action_values,
                    context=context_values,
                )
            )
            if accepted is None:
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": ["procedure-stop-condition-unknown"],
                    "status": "uncertain",
                    "work": work,
                }
            if accepted:
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": [node["reason"]],
                    "status": "stopped",
                    "work": work,
                }
            current["stack"].pop()
            continue
        if op == "cancel":
            return {
                "cursor": current,
                "intent": None,
                "limitations": ["procedure-cancel-node"],
                "status": "cancelled",
                "work": work,
            }
        if op == "complete":
            expected_effect = cast(
                Mapping[str, Any], substituted_contract["expected_effect"]
            )
            observed = _surface_conditions(
                [
                    {"op": "eq", "path": path, "value": value}
                    for path, value in expected_effect.items()
                ],
                state=state_values,
                action=action_values,
                context=context_values,
            )
            if observed is not True:
                return {
                    "cursor": current,
                    "intent": None,
                    "limitations": [
                        "expected-effect-not-observed"
                        if observed is None
                        else "expected-effect-mismatch"
                    ],
                    "status": (
                        "awaiting-observation" if observed is None else "effect-mismatch"
                    ),
                    "work": work,
                }
            current["stack"].pop()
            continue
        return {
            "cursor": current,
            "intent": None,
            "limitations": ["procedure-control-invalid"],
            "status": "support-gap",
            "work": work,
        }
    while pause_active_parallel_branch("yielded"):
        pass
    return {
        "cursor": current,
        "intent": None,
        "limitations": ["procedure-work-quantum"],
        "status": "yielded",
        "work": work,
    }


def _semantic_tokens(text: Any) -> tuple[str, ...]:
    if not isinstance(text, str) or len(text.encode("utf-8")) > 64 * 1024:
        raise FieldProgramError("construction text must be bounded text")
    result: list[str] = []
    current: list[str] = []
    for character in text.strip():
        if character.isspace():
            if current:
                result.append("".join(current))
                current.clear()
        elif character in ".,?!:;":
            if current:
                result.append("".join(current))
                current.clear()
            result.append(character)
        else:
            current.append(character)
    if current:
        result.append("".join(current))
    return tuple(result)


def _semantic_pattern_matches(
    pattern: Sequence[Any],
    tokens: Sequence[str],
    maximum: int,
) -> list[dict[str, str]]:
    frontier: list[tuple[int, int, dict[str, str]]] = [(0, 0, {})]
    completed: dict[bytes, dict[str, str]] = {}
    work = 0
    while frontier:
        pattern_cursor, token_cursor, bindings = frontier.pop()
        work += 1
        if work > maximum:
            raise FieldProgramError("construction match exceeds its work bound")
        if pattern_cursor == len(pattern):
            if token_cursor == len(tokens):
                completed[_canonical(bindings)] = bindings
            continue
        expected = pattern[pattern_cursor]
        if not (
            isinstance(expected, str)
            and expected.startswith("{")
            and expected.endswith("}")
            and len(expected) > 2
        ):
            if token_cursor < len(tokens) and expected == tokens[token_cursor]:
                frontier.append(
                    (pattern_cursor + 1, token_cursor + 1, bindings)
                )
            continue
        role = expected[1:-1]
        remaining_pattern = len(pattern) - pattern_cursor - 1
        maximum_end = len(tokens) - remaining_pattern
        for end in range(token_cursor + 1, maximum_end + 1):
            surface = " ".join(tokens[token_cursor:end])
            previous = bindings.get(role)
            if previous is not None and previous != surface:
                continue
            successor = dict(bindings)
            successor[role] = surface
            frontier.append((pattern_cursor + 1, end, successor))
    return [completed[key] for key in sorted(completed)]


def _semantic_interval_duration(interval: Mapping[str, Any]) -> float:
    if "duration" in interval:
        return _semantic_program_number(
            interval["duration"], "mechanism duration", nonnegative=True
        )
    if "start" in interval and "end" in interval:
        start = _semantic_program_number(
            interval["start"], "mechanism interval start"
        )
        end = _semantic_program_number(
            interval["end"], "mechanism interval end"
        )
        if end < start:
            raise FieldProgramError("mechanism interval is reversed")
        return end - start
    return 0.0


def execute_semantic_program(
    payload: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    action: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    interval: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one bounded, goal-independent mechanism program."""

    return execute_canonical_semantic_program(
        canonical_semantic_program_payload(payload),
        state,
        action=action,
        context=context,
        interval=interval,
    )


def execute_canonical_semantic_program(
    program: Mapping[str, Any],
    state: Mapping[str, Any],
    *,
    action: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    interval: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a mechanism program already in canonical payload form.

    Canonicalizing a program validates and rebuilds the whole representation,
    which dominates repeated evaluation of one retained mechanism. A caller
    that evaluates the same program many times canonicalizes once with
    ``canonical_semantic_program_payload`` and reuses the result here; the
    canonical form is read-only for the life of that program revision.
    """

    current = _semantic_program_plain(dict(state), "mechanism state")
    action_values = _semantic_program_plain(
        dict(action or {}), "mechanism action"
    )
    context_values = _semantic_program_plain(
        dict(context or {}), "mechanism context"
    )
    interval_values = _semantic_program_plain(
        dict(interval or {}), "mechanism interval"
    )
    if not all(
        isinstance(item, dict)
        for item in (
            current,
            action_values,
            context_values,
            interval_values,
        )
    ):
        raise FieldProgramError("mechanism operands must be mappings")
    for name, descriptor in program["arguments"].items():
        if descriptor["required"] and name not in action_values:
            return {
                "status": "support-gap",
                "values": current,
                "alternatives": [],
                "limitations": [f"missing-argument:{name}"],
                "work": 1,
            }
        if name not in action_values:
            continue
        expected_type = descriptor["type"]
        supplied_value = action_values[name]
        type_matches = (
            expected_type == "json"
            or (
                expected_type == "boolean"
                and isinstance(supplied_value, bool)
            )
            or (
                expected_type == "integer"
                and isinstance(supplied_value, int)
                and not isinstance(supplied_value, bool)
            )
            or (
                expected_type == "number"
                and isinstance(supplied_value, (int, float))
                and not isinstance(supplied_value, bool)
            )
            or (
                expected_type == "string"
                and isinstance(supplied_value, str)
            )
            or (
                expected_type == "mapping"
                and isinstance(supplied_value, Mapping)
            )
            or (
                expected_type == "list"
                and isinstance(supplied_value, list)
            )
        )
        if not type_matches:
            return {
                "status": "support-gap",
                "values": current,
                "alternatives": [],
                "limitations": [
                    f"argument-type:{name}:{expected_type}"
                ],
                "work": 1,
            }
    for guard in program["guards"]:
        known, accepted = _semantic_guard(
            guard, current, action_values, context_values
        )
        if not known:
            return {
                "status": "support-gap",
                "values": current,
                "alternatives": [],
                "limitations": ["guard-unknown"],
                "work": 1,
            }
        if not accepted:
            return {
                "status": "support-gap",
                "values": current,
                "alternatives": [],
                "limitations": ["guard-false"],
                "work": 1,
            }

    def execute(
        nested: Mapping[str, Any],
        values: Mapping[str, Any],
        depth: int,
    ) -> dict[str, Any]:
        if depth > 8:
            raise FieldProgramError("semantic mechanism nesting is exhausted")
        kind = nested["program_kind"]
        body = nested["body"]
        successor = dict(values)
        for name, descriptor in nested["arguments"].items():
            if descriptor["required"] and name not in action_values:
                return {
                    "status": "support-gap",
                    "values": values,
                    "alternatives": [],
                    "limitations": [f"missing-argument:{name}"],
                    "work": 1,
                }
            if name not in action_values:
                continue
            supplied_value = action_values[name]
            expected_type = descriptor["type"]
            type_matches = (
                expected_type == "json"
                or (
                    expected_type == "boolean"
                    and isinstance(supplied_value, bool)
                )
                or (
                    expected_type == "integer"
                    and isinstance(supplied_value, int)
                    and not isinstance(supplied_value, bool)
                )
                or (
                    expected_type == "number"
                    and isinstance(supplied_value, (int, float))
                    and not isinstance(supplied_value, bool)
                )
                or (
                    expected_type == "string"
                    and isinstance(supplied_value, str)
                )
                or (
                    expected_type == "mapping"
                    and isinstance(supplied_value, Mapping)
                )
                or (
                    expected_type == "list"
                    and isinstance(supplied_value, list)
                )
            )
            if not type_matches:
                return {
                    "status": "support-gap",
                    "values": values,
                    "alternatives": [],
                    "limitations": [f"argument-type:{name}:{expected_type}"],
                    "work": 1,
                }
        for guard in nested["guards"]:
            known, accepted = _semantic_guard(
                guard, values, action_values, context_values
            )
            if not known:
                return {
                    "status": "support-gap",
                    "values": values,
                    "alternatives": [],
                    "limitations": ["guard-unknown"],
                    "work": 1,
                }
            if not accepted:
                return {
                    "status": "support-gap",
                    "values": values,
                    "alternatives": [],
                    "limitations": ["guard-false"],
                    "work": 1,
                }
        if kind == "context-tree":
            features = body["features"]
            tree = body["tree"]
            leaf_count, tree_depth = _context_tree_shape(tree)
            if leaf_count > nested["bounds"]["max_branches"]:
                return {
                    "status": "resource-exhausted",
                    "values": successor,
                    "alternatives": [],
                    "limitations": ["program-branch-bound"],
                    "required_work": leaf_count,
                    "available_work": nested["bounds"]["max_branches"],
                    "work": 1,
                }
            feature_values: dict[str, Any] = {}
            for feature in features:
                present, actual = _semantic_lookup(
                    feature["key"], values, action_values, context_values
                )
                if not present:
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": [
                            f"missing-context:{feature['key']}"
                        ],
                        "work": max(1, len(feature_values) + 1),
                    }
                if feature["kind"] == "numeric":
                    if (
                        isinstance(actual, bool)
                        or not isinstance(actual, (int, float))
                        or not math.isfinite(float(actual))
                    ):
                        return {
                            "status": "support-gap",
                            "values": successor,
                            "alternatives": [],
                            "limitations": [
                                f"context-type:{feature['key']}:numeric"
                            ],
                            "work": max(1, len(feature_values) + 1),
                        }
                    numeric = float(actual)
                    if not (
                        feature["minimum"]
                        <= numeric
                        <= feature["maximum"]
                    ):
                        return {
                            "status": "support-gap",
                            "values": successor,
                            "alternatives": [],
                            "limitations": [
                                f"outside-context-support:{feature['key']}"
                            ],
                            "work": max(1, len(feature_values) + 1),
                        }
                    feature_values[feature["key"]] = numeric
                    continue
                if _canonical(actual) not in {
                    _canonical(item) for item in feature["values"]
                }:
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": [
                            f"unseen-context:{feature['key']}"
                        ],
                        "work": max(1, len(feature_values) + 1),
                    }
                feature_values[feature["key"]] = actual
            node = tree
            traversed = 0
            while node["kind"] == "split":
                traversed += 1
                test = node["test"]
                actual = feature_values[test["key"]]
                accepted = (
                    float(actual) <= float(test["value"])
                    if test["operator"] == "le"
                    else _canonical(actual) == _canonical(test["value"])
                )
                node = node["match"] if accepted else node["otherwise"]
            nested_outcome = execute(
                node["program"], successor, depth + 1
            )
            total_work = max(
                1,
                len(features)
                + traversed
                + int(nested_outcome.get("work", 1)),
            )
            if (
                tree_depth > _CONTEXT_TREE_MAX_DEPTH
                or total_work > nested["bounds"]["max_work"]
            ):
                return {
                    "status": "resource-exhausted",
                    "values": successor,
                    "alternatives": [],
                    "limitations": ["program-work-bound"],
                    "required_work": total_work,
                    "available_work": nested["bounds"]["max_work"],
                    "work": nested["bounds"]["max_work"],
                }
            nested_outcome["work"] = total_work
            return nested_outcome
        if kind == "conditional":
            branches = body["branches"]
            if len(branches) > nested["bounds"]["max_branches"]:
                return {
                    "status": "resource-exhausted",
                    "values": successor,
                    "alternatives": [],
                    "limitations": ["program-branch-bound"],
                    "required_work": len(branches),
                    "available_work": nested["bounds"]["max_branches"],
                    "work": 1,
                }
            matches: list[Mapping[str, Any]] = []
            for branch in branches:
                accepted = True
                for item in branch["when"]:
                    present, actual = _semantic_lookup(
                        item["key"], values, action_values, context_values
                    )
                    if not present or _canonical(actual) != _canonical(
                        item["value"]
                    ):
                        accepted = False
                        break
                if accepted:
                    matches.append(branch)
            if not matches:
                return {
                    "status": "support-gap",
                    "values": successor,
                    "alternatives": [],
                    "limitations": ["uncovered-context"],
                    "work": max(1, len(branches)),
                }
            nested_outcome = execute(
                matches[0]["program"], successor, depth + 1
            )
            nested_outcome["work"] = max(
                1, len(branches) + int(nested_outcome.get("work", 1))
            )
            return nested_outcome
        if kind == "sequence":
            sequence_outcome = _execute_sequence_program(nested, action_values)
            sequence_outcome["values"] = successor
            return sequence_outcome
        if kind == "identity":
            return {
                "status": "supported",
                "values": successor,
                "alternatives": [],
                "limitations": [],
                "work": 1,
            }
        if kind in {"consolidation", "migration"}:
            expected_schema = (
                "cassifi.semantic-consolidation-program.v1"
                if kind == "consolidation"
                else "cassifi.semantic-migration-program.v1"
            )
            if body.get("schema") != expected_schema:
                raise FieldProgramError(
                    f"{kind} program body schema is invalid"
                )
            return {
                "status": "support-gap",
                "values": successor,
                "alternatives": [],
                "limitations": [
                    f"{kind}-requires-semantic-lifecycle-handler"
                ],
                "work": 1,
            }
        if kind == "table":
            rows = body.get("rows", [])
            if not isinstance(rows, list) or len(rows) > nested["bounds"]["max_branches"]:
                raise FieldProgramError("table mechanism rows are invalid")
            matched: list[dict[str, Any]] = []
            for row in rows:
                if (
                    not isinstance(row, dict)
                    or set(row) - {"set", "status", "when"}
                    or not isinstance(row.get("when"), dict)
                    or not isinstance(row.get("set"), dict)
                ):
                    raise FieldProgramError("table mechanism row is invalid")
                accepted = True
                for key, expected in row["when"].items():
                    present, actual = _semantic_lookup(
                        key, successor, action_values, context_values
                    )
                    if not present or actual != expected:
                        accepted = False
                        break
                if accepted:
                    matched.append({**successor, **dict(row["set"])})
            if not matched and isinstance(body.get("default"), dict):
                matched.append({**successor, **dict(body["default"])})
            unique = {
                _canonical(item): item for item in matched
            }
            ordered = [unique[key] for key in sorted(unique)]
            if not ordered:
                return {
                    "status": "support-gap",
                    "values": successor,
                    "alternatives": [],
                    "limitations": ["uncovered-transition"],
                    "work": max(1, len(rows)),
                }
            return {
                "status": (
                    "supported" if len(ordered) == 1 else "alternatives"
                ),
                "values": ordered[0] if len(ordered) == 1 else successor,
                "alternatives": ordered if len(ordered) > 1 else [],
                "limitations": [],
                "work": max(1, len(rows)),
            }
        if kind == "construction":
            if body.get("schema") == SEMANTIC_REPRESENTATION_SCHEMA:
                if set(body) != {
                    "edits",
                    "information_boundary",
                    "output_roles",
                    "question",
                    "schema",
                    "table",
                }:
                    raise FieldProgramError(
                        "typed representation body has invalid keys"
                    )
                output_roles = body["output_roles"]
                table = body["table"]
                features = successor.get("features", successor)
                if (
                    not isinstance(output_roles, list)
                    or not output_roles
                    or output_roles != sorted(set(output_roles))
                    or not isinstance(table, dict)
                    or not isinstance(body["question"], Mapping)
                    or not isinstance(body["information_boundary"], Mapping)
                    or not isinstance(features, Mapping)
                ):
                    raise FieldProgramError(
                        "typed representation body is invalid"
                    )
                transformed = apply_semantic_representation_edits(
                    features,
                    body["edits"],
                    action=action_values,
                    context=context_values,
                )
                if transformed["status"] != "supported":
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": transformed["limitations"],
                        "work": transformed["work"],
                    }
                encoded: dict[str, Any] = {}
                for role in output_roles:
                    present, value = _semantic_lookup(
                        role,
                        transformed["values"],
                        action_values,
                        context_values,
                    )
                    if not present:
                        return {
                            "status": "support-gap",
                            "values": successor,
                            "alternatives": [],
                            "limitations": [
                                f"representation-output-missing:{role}"
                            ],
                            "work": transformed["work"],
                        }
                    encoded[role] = value
                row = table.get(_canonical(encoded).hex())
                if (
                    not isinstance(row, dict)
                    or set(row) != {"encoded", "outcome", "support"}
                    or row["encoded"] != encoded
                ):
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": ["representation-state-unseen"],
                        "work": max(
                            int(transformed["work"]),
                            min(len(table), len(output_roles)),
                        ),
                    }
                return {
                    "status": "supported",
                    "values": successor,
                    "alternatives": [],
                    "limitations": [],
                    "output": {
                        "encoded": encoded,
                        "information_boundary": body[
                            "information_boundary"
                        ],
                        "outcome": row["outcome"],
                        "question": body["question"],
                        "support": row["support"],
                        "transformed": transformed["values"],
                    },
                    "work": max(
                        1,
                        int(transformed["work"]) + len(output_roles),
                    ),
                }
            if set(body).issuperset({"keys", "table"}):
                keys = body["keys"]
                table = body["table"]
                features = successor.get("features", successor)
                if (
                    not isinstance(keys, list)
                    or keys != sorted(set(keys))
                    or not all(isinstance(key, str) and key for key in keys)
                    or not isinstance(table, dict)
                    or not isinstance(features, Mapping)
                ):
                    raise FieldProgramError(
                        "predictive construction table is invalid"
                    )
                if any(key not in features for key in keys):
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": ["representation-feature-missing"],
                        "work": max(1, len(keys)),
                    }
                encoded = {key: features[key] for key in keys}
                row = table.get(_canonical(encoded).hex())
                if (
                    not isinstance(row, dict)
                    or set(row) != {"encoded", "outcome", "support"}
                    or row["encoded"] != encoded
                ):
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": ["representation-state-unseen"],
                        "work": max(1, min(len(table), len(keys))),
                    }
                return {
                    "status": "supported",
                    "values": successor,
                    "alternatives": [],
                    "limitations": [],
                    "output": {
                        "encoded": encoded,
                        "outcome": row["outcome"],
                        "support": row["support"],
                    },
                    "work": max(1, len(keys)),
                }
            if set(body).issuperset(
                {"belief_semantics", "classes", "signature", "window"}
            ):
                classes = body["classes"]
                signature = body["signature"]
                semantics = body["belief_semantics"]
                window = _integer(
                    body["window"],
                    "predictive construction window",
                    minimum=1,
                    maximum=1_000_000,
                )
                history = successor.get("history")
                if (
                    not isinstance(classes, list)
                    or not isinstance(signature, Mapping)
                    or semantics not in {"constraint-set", "probability"}
                    or not isinstance(history, list)
                ):
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": ["predictive-history-missing"],
                        "work": 1,
                    }
                if successor.get("signature") != signature:
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": ["predictive-signature-mismatch"],
                        "work": 1,
                    }
                selected: Mapping[str, Any] | None = None
                history_window = history[-window:]
                for row in classes:
                    if (
                        not isinstance(row, Mapping)
                        or set(row)
                        != {
                            "class_id",
                            "histories",
                            "history_refs",
                            "tests",
                        }
                        or not isinstance(row["histories"], list)
                        or not isinstance(row["history_refs"], list)
                        or not isinstance(row["tests"], list)
                    ):
                        raise FieldProgramError(
                            "predictive construction class is invalid"
                        )
                    if history_window in row["histories"]:
                        selected = row
                        break
                if selected is None:
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": ["predictive-history-unseen"],
                        "work": max(1, len(classes)),
                    }
                condition = {
                    "action": action_values,
                    "context": context_values,
                    "question": successor.get("question"),
                }
                selected_test = next(
                    (
                        test
                        for test in selected["tests"]
                        if isinstance(test, Mapping)
                        and set(test)
                        == {
                            "condition",
                            "consequences",
                            "prediction_semantics",
                        }
                        and test["condition"] == condition
                        and test["prediction_semantics"] == semantics
                    ),
                    None,
                )
                if selected_test is None:
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": ["predictive-condition-unseen"],
                        "work": max(1, len(selected["tests"])),
                    }
                consequences = selected_test["consequences"]
                if not isinstance(consequences, list):
                    raise FieldProgramError(
                        "predictive construction consequences are invalid"
                    )
                predictive_alternatives: list[dict[str, Any]] = []
                weights: list[float] = []
                for raw in consequences:
                    expected = (
                        {"future", "support_count", "weight"}
                        if semantics == "probability"
                        else {"future", "support_count"}
                    )
                    if not isinstance(raw, Mapping) or set(raw) != expected:
                        raise FieldProgramError(
                            "predictive construction consequence is invalid"
                        )
                    _integer(
                        raw["support_count"],
                        "predictive consequence support count",
                        minimum=1,
                        maximum=2**53,
                    )
                    future = raw["future"]
                    predictive_alternatives.append(
                        dict(future)
                        if isinstance(future, Mapping)
                        else {"future": future}
                    )
                    if semantics == "probability":
                        weights.append(
                            _semantic_program_number(
                                raw["weight"],
                                "predictive probability",
                                nonnegative=True,
                            )
                        )
                if not predictive_alternatives or (
                    semantics == "probability"
                    and abs(sum(weights) - 1.0) > 1.0e-9
                ):
                    raise FieldProgramError(
                        "predictive construction consequences are empty or invalid"
                    )
                return {
                    "status": (
                        "supported"
                        if len(predictive_alternatives) == 1
                        else "alternatives"
                    ),
                    "values": (
                        predictive_alternatives[0]
                        if len(predictive_alternatives) == 1
                        else successor
                    ),
                    "alternatives": (
                        predictive_alternatives
                        if len(predictive_alternatives) > 1
                        else []
                    ),
                    **(
                        {"alternative_weights": weights}
                        if semantics == "probability"
                        and len(predictive_alternatives) > 1
                        else {}
                    ),
                    "uncertainty_semantics": semantics,
                    "limitations": [],
                    "output": {
                        "class_id": selected["class_id"],
                        "condition": condition,
                        "consequences": consequences,
                        "prediction_semantics": semantics,
                        "signature": signature,
                    },
                    "work": max(1, len(classes) + len(selected["tests"])),
                }
            if set(body).issuperset({"meaning", "pattern", "roles"}):
                pattern = body["pattern"]
                roles = body["roles"]
                if (
                    not isinstance(pattern, list)
                    or not isinstance(roles, list)
                    or roles != sorted(set(roles))
                    or any(not isinstance(role, str) for role in roles)
                ):
                    raise FieldProgramError(
                        "language construction body is invalid"
                    )
                operation = action_values.get("operation")
                if operation == "interpret":
                    tokens = _semantic_tokens(action_values.get("text"))
                    matches = _semantic_pattern_matches(
                        pattern,
                        tokens,
                        int(nested["bounds"]["max_work"]),
                    )
                    outputs = [
                        {
                            "bindings": bindings,
                            "meaning": body["meaning"],
                        }
                        for bindings in matches
                    ]
                    if not outputs:
                        return {
                            "status": "support-gap",
                            "values": successor,
                            "alternatives": [],
                            "limitations": ["construction-does-not-match"],
                            "work": max(1, len(pattern)),
                        }
                    return {
                        "status": (
                            "supported"
                            if len(outputs) == 1
                            else "alternatives"
                        ),
                        "values": (
                            outputs[0] if len(outputs) == 1 else successor
                        ),
                        "alternatives": (
                            outputs if len(outputs) > 1 else []
                        ),
                        "limitations": [],
                        "work": max(1, len(pattern)),
                    }
                if operation == "express":
                    bindings = action_values.get("bindings")
                    if not isinstance(bindings, Mapping) or any(
                        role not in bindings for role in roles
                    ):
                        return {
                            "status": "support-gap",
                            "values": successor,
                            "alternatives": [],
                            "limitations": [
                                "construction-binding-missing"
                            ],
                            "work": max(1, len(pattern)),
                        }
                    words = [
                        str(bindings[token[1:-1]])
                        if (
                            isinstance(token, str)
                            and token.startswith("{")
                            and token.endswith("}")
                        )
                        else str(token)
                        for token in pattern
                    ]
                    return {
                        "status": "supported",
                        "values": {
                            "meaning": body["meaning"],
                            "text": " ".join(words),
                        },
                        "alternatives": [],
                        "limitations": [],
                        "work": max(1, len(pattern)),
                    }
                return {
                    "status": "support-gap",
                    "values": successor,
                    "alternatives": [],
                    "limitations": [
                        "construction-operation-required"
                    ],
                    "work": 1,
                }
            raise FieldProgramError("construction body is unsupported")
        if kind == "procedure":
            steps = body.get("steps")
            if not isinstance(steps, list) or len(steps) > int(
                nested["bounds"]["max_horizon"]
            ):
                raise FieldProgramError("procedure steps are invalid")
            proposed_actions: list[Any] = []
            nested_work = 0
            raw_roles = body.get("roles", [])
            if not isinstance(raw_roles, list):
                raise FieldProgramError("procedure roles are invalid")
            procedure_roles: list[dict[str, str]] = []
            role_names: set[str] = set()
            for role in raw_roles:
                if not isinstance(role, dict) or set(role) != {"name", "type"}:
                    raise FieldProgramError("procedure role is invalid")
                name = _semantic_program_identifier(
                    role["name"], "procedure role name"
                )
                value_type = _semantic_program_identifier(
                    role["type"], "procedure role type"
                )
                if (
                    name in role_names
                    or name not in nested["arguments"]
                    or value_type != nested["arguments"][name]["type"]
                ):
                    raise FieldProgramError("procedure role is invalid")
                role_names.add(name)
                procedure_roles.append({"name": name, "type": value_type})
            if any(name not in action_values for name in role_names):
                return {
                    "status": "support-gap",
                    "values": successor,
                    "alternatives": [],
                    "limitations": ["procedure-role-binding-missing"],
                    "work": 1,
                }
            role_bindings = {
                name: action_values[name] for name in sorted(role_names)
            }
            available, expected_effects = _semantic_procedure_substitute(
                body.get("effects", {}), action_values
            )
            if not available:
                return {
                    "status": "support-gap",
                    "values": successor,
                    "alternatives": [],
                    "limitations": ["procedure-role-binding-missing"],
                    "work": 1,
                }
            available, expected_postconditions = (
                _semantic_procedure_substitute(
                    body.get("postconditions", {}), action_values
                )
            )
            if not available:
                return {
                    "status": "support-gap",
                    "values": successor,
                    "alternatives": [],
                    "limitations": ["procedure-role-binding-missing"],
                    "work": 1,
                }
            failure_behavior = _semantic_program_plain(
                body.get("failure_behavior", []),
                "procedure failure behavior",
            )
            if not isinstance(failure_behavior, list):
                raise FieldProgramError(
                    "procedure failure behavior must be a list"
                )
            substituted_steps: list[Mapping[str, Any]] = []
            for raw_step in steps:
                available, substituted = _semantic_procedure_substitute(
                    raw_step, action_values
                )
                if not available or not isinstance(substituted, Mapping):
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": ["procedure-role-binding-missing"],
                        "work": max(1, len(substituted_steps)),
                    }
                selected_step = _semantic_select_procedure_branch(
                    substituted,
                    state=successor,
                    action=action_values,
                    context=context_values,
                    maximum=int(nested["bounds"]["max_branches"]),
                )
                if selected_step is None:
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": ["procedure-branch-unmatched"],
                        "work": max(1, len(substituted_steps)),
                    }
                substituted_steps.append(selected_step)
            steps = substituted_steps
            for raw_step in steps:
                if not isinstance(raw_step, Mapping):
                    raise FieldProgramError(
                        "procedure step must be a mapping"
                    )
                execution_step = (
                    {
                        key: value
                        for key, value in raw_step.items()
                        if key != "branch_index"
                    }
                    if "branch_index" in raw_step
                    else raw_step
                )
                if set(execution_step) == {"set"} and isinstance(
                    execution_step["set"], Mapping
                ):
                    successor.update(dict(execution_step["set"]))
                    nested_work += 1
                    continue
                if set(execution_step) == {"program"}:
                    nested_program = canonical_semantic_program_payload(
                        execution_step["program"]
                    )
                    nested_outcome = execute(
                        nested_program, successor, depth + 1
                    )
                    nested_work += int(nested_outcome["work"])
                    if nested_outcome["status"] != "supported":
                        return nested_outcome
                    successor = dict(nested_outcome["values"])
                    continue
                proposed_actions.append(
                    _semantic_program_plain(
                        dict(raw_step), "procedure proposed action"
                    )
                )
                nested_work += 1
            return {
                "status": "supported",
                "values": successor,
                "alternatives": [],
                "limitations": [],
                "procedure_effects": expected_effects,
                "procedure_postconditions": expected_postconditions,
                "failure_behavior": failure_behavior,
                "role_bindings": role_bindings,
                "proposed_actions": proposed_actions,
                "work": max(1, nested_work),
            }
        if kind == "affine":
            outputs = body.get("outputs")
            if not isinstance(outputs, dict):
                raise FieldProgramError("affine mechanism outputs are invalid")
            source_values = dict(successor)
            uncertainty: dict[str, list[float]] = {}
            for target, expression in sorted(outputs.items()):
                _semantic_program_identifier(target, "affine output")
                if (
                    not isinstance(expression, dict)
                    or set(expression)
                    != {"action_terms", "bias", "error", "terms"}
                    or not isinstance(expression["terms"], dict)
                    or not isinstance(expression["action_terms"], dict)
                ):
                    raise FieldProgramError(
                        "affine mechanism expression is invalid"
                    )
                result = _semantic_program_number(
                    expression["bias"], "affine bias"
                )
                for source, coefficient in expression["terms"].items():
                    present, raw = _semantic_lookup(
                        source, source_values, action_values, context_values
                    )
                    if not present:
                        return {
                            "status": "support-gap",
                            "values": successor,
                            "alternatives": [],
                            "limitations": [f"missing-state:{source}"],
                            "work": 1,
                        }
                    result += _semantic_program_number(
                        coefficient, "affine coefficient"
                    ) * _semantic_program_number(raw, "affine source")
                for source, coefficient in expression[
                    "action_terms"
                ].items():
                    present, raw = _semantic_lookup(
                        f"action.{source}",
                        successor,
                        action_values,
                        context_values,
                    )
                    if not present:
                        return {
                            "status": "support-gap",
                            "values": successor,
                            "alternatives": [],
                            "limitations": [f"missing-action:{source}"],
                            "work": 1,
                        }
                    result += _semantic_program_number(
                        coefficient, "affine action coefficient"
                    ) * _semantic_program_number(
                        raw, "affine action source"
                    )
                error = _semantic_program_number(
                    expression["error"],
                    "affine error",
                    nonnegative=True,
                )
                clamp = body.get("clamp", {}).get(target)
                if clamp is not None:
                    if not isinstance(clamp, list) or len(clamp) != 2:
                        raise FieldProgramError(
                            "affine clamp must contain two bounds"
                        )
                    lower = _semantic_program_number(
                        clamp[0], "affine lower clamp"
                    )
                    upper = _semantic_program_number(
                        clamp[1], "affine upper clamp"
                    )
                    if upper < lower:
                        raise FieldProgramError(
                            "affine clamp bounds are reversed"
                        )
                    result = min(upper, max(lower, result))
                successor[target] = result
                uncertainty[target] = [result - error, result + error]
            return {
                "status": "supported",
                "values": successor,
                "alternatives": [],
                "limitations": [],
                "uncertainty": uncertainty,
                "work": max(1, len(outputs)),
            }
        if kind == "timer":
            elapsed_key = _semantic_program_identifier(
                body.get("elapsed_key", "elapsed"), "timer elapsed key"
            )
            output_key = _semantic_program_identifier(
                body.get("output_key", "observation"), "timer output key"
            )
            threshold = _semantic_program_number(
                body.get("threshold"), "timer threshold", nonnegative=True
            )
            elapsed = _semantic_program_number(
                successor.get(elapsed_key, 0.0),
                "timer elapsed state",
                nonnegative=True,
            )
            reset_on = body.get("reset_on", [])
            if not isinstance(reset_on, list):
                raise FieldProgramError("timer reset actions are invalid")
            if action_values.get("action") in reset_on:
                elapsed = 0.0
            elapsed += _semantic_interval_duration(interval_values)
            successor[elapsed_key] = elapsed
            successor[output_key] = (
                body.get("fired") if elapsed >= threshold else body.get("quiet")
            )
            return {
                "status": "supported",
                "values": successor,
                "alternatives": [],
                "limitations": [],
                "work": 1,
            }
        if kind == "hybrid":
            mode_key = _semantic_program_identifier(
                body.get("mode_key", "mode"), "hybrid mode key"
            )
            modes = body.get("modes")
            transitions = body.get("transitions", [])
            if (
                not isinstance(modes, dict)
                or not modes
                or len(modes) > nested["bounds"]["max_branches"]
                or not isinstance(transitions, list)
            ):
                raise FieldProgramError("hybrid mechanism body is invalid")
            mode_programs: dict[str, dict[str, Any]] = {}
            for raw_mode, raw_program in modes.items():
                mode_name = _semantic_program_identifier(
                    raw_mode, "hybrid mode identity"
                )
                mode_programs[mode_name] = canonical_semantic_program_payload(
                    raw_program
                )
            raw_mode_weights = body.get("mode_weights")
            mode_weights: dict[str, float] | None = None
            if raw_mode_weights is not None:
                if (
                    not isinstance(raw_mode_weights, dict)
                    or set(raw_mode_weights) != set(mode_programs)
                ):
                    raise FieldProgramError(
                        "hybrid mode weights do not cover the mode family"
                    )
                mode_weights = {
                    name: _semantic_program_number(
                        raw_mode_weights[name],
                        "hybrid mode weight",
                        nonnegative=True,
                    )
                    for name in mode_programs
                }
                if abs(sum(mode_weights.values()) - 1.0) > 1.0e-9:
                    raise FieldProgramError(
                        "hybrid mode weights are not normalized"
                    )
            for transition in transitions:
                if (
                    not isinstance(transition, dict)
                    or set(transition) != {"from", "guard", "to"}
                    or transition["from"] not in mode_programs
                    or transition["to"] not in mode_programs
                    or not isinstance(transition["guard"], dict)
                ):
                    raise FieldProgramError(
                        "hybrid mechanism transition is invalid"
                    )

            def advance_mode(
                selected_mode: str,
            ) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
                branch = {**successor, mode_key: selected_mode}
                nested_outcome = execute(
                    mode_programs[selected_mode], branch, depth + 1
                )
                nested_work = int(nested_outcome["work"])
                if nested_outcome["status"] == "supported":
                    branch_values = [dict(nested_outcome["values"])]
                elif nested_outcome["status"] == "alternatives":
                    branch_values = [
                        dict(item)
                        for item in nested_outcome["alternatives"]
                        if isinstance(item, Mapping)
                    ]
                else:
                    return [], nested_outcome, nested_work
                applicable = [
                    transition
                    for transition in transitions
                    if transition["from"] == selected_mode
                ]
                advanced: list[dict[str, Any]] = []
                for values in branch_values:
                    values[mode_key] = selected_mode
                    for transition in applicable:
                        known, accepted = _semantic_guard(
                            transition["guard"],
                            values,
                            action_values,
                            context_values,
                        )
                        if known and accepted:
                            values[mode_key] = transition["to"]
                            break
                    advanced.append(values)
                return (
                    advanced,
                    nested_outcome,
                    nested_work + max(1, len(applicable)),
                )

            mode = successor.get(mode_key)
            if mode is not None and mode not in mode_programs:
                return {
                    "status": "representation-insufficient",
                    "values": successor,
                    "alternatives": [],
                    "limitations": ["mode-outside-family"],
                    "work": 1,
                }
            if mode is not None:
                branch_values, nested_outcome, branch_work = advance_mode(mode)
                if not branch_values:
                    return nested_outcome
                if len(branch_values) == 1:
                    nested_outcome["status"] = "supported"
                    nested_outcome["values"] = branch_values[0]
                    nested_outcome["alternatives"] = []
                else:
                    nested_outcome["status"] = "alternatives"
                    nested_outcome["values"] = successor
                    nested_outcome["alternatives"] = branch_values
                nested_outcome["work"] = branch_work
                return nested_outcome

            alternatives: dict[bytes, dict[str, Any]] = {}
            alternative_details: dict[bytes, dict[str, Any]] = {}
            alternative_masses: dict[bytes, float] = {}
            alternative_uncertainties: dict[bytes, dict[str, Any]] = {}
            total_work = 0
            for mode_name in sorted(mode_programs):
                branch_values, nested_outcome, branch_work = advance_mode(
                    mode_name
                )
                total_work += branch_work
                branch_weights: list[float] | None = None
                if mode_weights is not None:
                    nested_weights = nested_outcome.get(
                        "alternative_weights"
                    )
                    if len(branch_values) == 1:
                        branch_weights = [1.0]
                    elif (
                        isinstance(nested_weights, list)
                        and len(nested_weights) == len(branch_values)
                        and all(
                            isinstance(item, (int, float))
                            and not isinstance(item, bool)
                            and float(item) >= 0.0
                            for item in nested_weights
                        )
                        and abs(
                            sum(float(item) for item in nested_weights) - 1.0
                        )
                        <= 1.0e-9
                    ):
                        branch_weights = [
                            float(item) for item in nested_weights
                        ]
                    else:
                        raise FieldProgramError(
                            "probabilistic hybrid branch lacks normalized weights"
                        )
                raw_branch_uncertainties = nested_outcome.get(
                    "alternative_uncertainties"
                )
                for branch_index, values in enumerate(branch_values):
                    branch_key = _canonical(values)
                    alternatives[branch_key] = values
                    branch_uncertainty = (
                        raw_branch_uncertainties[branch_index]
                        if isinstance(raw_branch_uncertainties, list)
                        and len(raw_branch_uncertainties)
                        == len(branch_values)
                        and isinstance(
                            raw_branch_uncertainties[branch_index],
                            Mapping,
                        )
                        else nested_outcome.get("uncertainty", {})
                    )
                    merged_uncertainty = alternative_uncertainties.setdefault(
                        branch_key, {}
                    )
                    for name, raw_bounds in branch_uncertainty.items():
                        bounds = list(raw_bounds)
                        prior_bounds = merged_uncertainty.get(name)
                        merged_uncertainty[name] = (
                            [
                                min(float(prior_bounds[0]), float(bounds[0])),
                                max(float(prior_bounds[1]), float(bounds[1])),
                            ]
                            if isinstance(prior_bounds, list)
                            and len(prior_bounds) == 2
                            and len(bounds) == 2
                            else bounds
                        )
                    if mode_weights is not None and branch_weights is not None:
                        alternative_masses[branch_key] = (
                            alternative_masses.get(branch_key, 0.0)
                            + mode_weights[mode_name]
                            * branch_weights[branch_index]
                        )
                    detail = alternative_details.setdefault(
                        branch_key,
                        {"modes": [], "uncertainty_by_mode": {}},
                    )
                    detail["modes"].append(mode_name)
                    detail["uncertainty_by_mode"][mode_name] = (
                        branch_uncertainty
                    )
            if not alternatives:
                return {
                    "status": "support-gap",
                    "values": successor,
                    "alternatives": [],
                    "limitations": ["all-latent-modes-unsupported"],
                    "work": max(1, total_work),
                }
            ordered_keys = sorted(alternatives)
            probabilistic = (
                {}
                if mode_weights is None
                else {
                    "alternative_weights": [
                        alternative_masses[key] for key in ordered_keys
                    ]
                }
            )
            return {
                "status": "alternatives",
                "values": successor,
                "alternatives": [
                    alternatives[key] for key in ordered_keys
                ],
                **probabilistic,
                "alternative_details": [
                    alternative_details[key] for key in ordered_keys
                ],
                "alternative_uncertainties": [
                    alternative_uncertainties[key] for key in ordered_keys
                ],
                "limitations": ["mode-unresolved"],
                "work": max(1, total_work),
            }
        if kind == "factor":
            constraints = body.get("constraints", [])
            if not isinstance(constraints, list):
                raise FieldProgramError("factor constraints are invalid")
            for constraint in constraints:
                if not isinstance(constraint, dict):
                    raise FieldProgramError("factor constraint is invalid")
                names = constraint.get("variables", [])
                if not isinstance(names, list) or not names:
                    raise FieldProgramError("factor variables are invalid")
                if any(name not in successor for name in names):
                    return {
                        "status": "support-gap",
                        "values": successor,
                        "alternatives": [],
                        "limitations": ["factor-variable-missing"],
                        "work": 1,
                    }
                values_row = [successor[name] for name in names]
                relation = constraint.get("relation")
                accepted = (
                    len(set(values_row)) == 1
                    if relation == "equality"
                    else (
                        sum(int(bool(item)) for item in values_row) % 2
                        == int(constraint.get("parity", 1))
                        if relation == "xor"
                        else (
                            sum(int(bool(item)) for item in values_row)
                            <= int(constraint.get("at_most", 1))
                            if relation == "exclusion"
                            else False
                        )
                    )
                )
                if not accepted:
                    return {
                        "status": "representation-insufficient",
                        "values": successor,
                        "alternatives": [],
                        "limitations": ["factor-contradiction"],
                        "work": max(1, len(constraints)),
                    }
            return {
                "status": "supported",
                "values": successor,
                "alternatives": [],
                "limitations": [],
                "work": max(1, len(constraints)),
            }
        return {
            "status": "representation-insufficient",
            "values": successor,
            "alternatives": [],
            "limitations": [f"not-a-transition:{kind}"],
            "work": 1,
        }

    outcome = execute(program, current, 0)
    if int(outcome["work"]) > int(program["bounds"]["max_work"]):
        return {
            "status": "resource-exhausted",
            "values": current,
            "alternatives": [],
            "limitations": ["program-work-bound"],
            "work": int(program["bounds"]["max_work"]),
        }
    return _semantic_program_plain(outcome, "mechanism result")


def _scalar_outcome(state: Mapping[str, Any]) -> dict[str, Any]:
    profile = ComputerProfile(**dict(state["profile"]))
    observations = [int(value) for value in state["pc_observations"]]
    learning = state["procedure_learning"]
    promoted = list(learning["promoted"])
    return {
        "schema": (
            "cassifi.field-computer.v2"
            if any(int(row[0]) == PROPAGATE for row in state["program"])
            else "cassifi.field-computer.v1"
        ),
        "status": state["status"],
        "pc": int(state["pc"]),
        "accumulator": int(state["accumulator"]),
        "left": [int(value) for value in state["left"]],
        "right": [int(value) for value in state["right"]],
        "reason": state["reason"],
        "program_length": len(state["program"]),
        "max_steps": profile.max_steps,
        "profile_sha256": profile.fingerprint,
        "resource_ledger": {
            "transitions": int(state["transitions"]),
            "stack_reads": int(state["stack_reads"]),
            "stack_writes": int(state["stack_writes"]),
            "field_cells_copied": int(state["field_cells_copied"]),
            "procedure_derivation_work": int(learning["derivation_work"]),
        },
        "execution_learning": {
            "hot_threshold": 8,
            "observation_limit": 65_535,
            "pc_observations": observations,
            "hot_pcs": [
                index for index, count in enumerate(observations)
                if count >= 8
            ],
        },
        "specialization": {
            "enabled": True,
            "hot_threshold": 8,
            "block_invocations": int(learning["block_invocations"]),
            "block_transitions": int(learning["block_transitions"]),
            "derived_blocks": len(promoted),
            "transferable_procedures": len(learning.get("transferable", [])),
            "scheduler_dispatches_saved": max(
                0,
                int(learning["block_transitions"])
                - int(learning["block_invocations"]),
            ),
            "derivation_deferred": bool(
                any(count >= 8 for count in observations) and not promoted
            ),
            "reason": (
                "field-procedure-promoted"
                if promoted else "awaiting-hot-block"
            ),
        },
        "field_bytes": profile.field_cells * 8,
    }


def _scalar_targets(row: Sequence[int]) -> tuple[int, ...]:
    opcode, a, b, c, _reserved = (int(value) for value in row)
    if opcode == PUSH:
        return (c,)
    if opcode in (POP, PUSH_ACC, PROPAGATE):
        return (b,)
    if opcode == BRANCH:
        return (b, c)
    if opcode == JUMP:
        return (a,)
    return ()


def _scalar_transfer_shape(
    program: Sequence[Sequence[int]], entry: int, length: int
) -> list[dict[str, int | str]]:
    if length < 2 or entry < 0 or entry + length > len(program):
        raise FieldProgramError("transferable scalar procedure range is invalid")
    shape: list[dict[str, int | str]] = []
    for offset in range(length):
        pc = entry + offset
        opcode, a, _b, c, _reserved = (int(value) for value in program[pc])
        if opcode == PUSH:
            successor = c
            row = {"opcode": opcode, "stack": a, "operand": "parameter"}
        elif opcode in (POP, PUSH_ACC):
            successor = int(program[pc][2])
            row = {"opcode": opcode, "stack": a, "operand": "none"}
        else:
            raise FieldProgramError(
                "transferable scalar procedures require straight-line stack operations"
            )
        if offset + 1 < length and successor != pc + 1:
            raise FieldProgramError(
                "transferable scalar procedure has noncontiguous interior control flow"
            )
        row["flow"] = "next" if offset + 1 < length else "exit"
        shape.append(row)
    return shape


def _canonical_transferable_procedure(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != {
        "procedure_id",
        "shape",
        "shape_sha256",
        "length",
        "parameter_roles",
        "evidence_program_sha256",
        "correctness",
        "status",
    }:
        raise FieldProgramError("transferable scalar procedure schema is invalid")
    shape = json.loads(_canonical(raw["shape"]).decode("utf-8"))
    length = _integer(
        raw["length"],
        "transferable scalar procedure length",
        minimum=2,
        maximum=SCALAR_SPECIALIZATION_MAX_BLOCK,
    )
    if not isinstance(shape, list) or len(shape) != length:
        raise FieldProgramError("transferable scalar procedure shape is invalid")
    for offset, row in enumerate(shape):
        if not isinstance(row, dict) or set(row) != {
            "opcode",
            "stack",
            "operand",
            "flow",
        }:
            raise FieldProgramError("transferable scalar procedure row is invalid")
        opcode = _integer(row["opcode"], "transferable opcode")
        stack = _integer(row["stack"], "transferable stack", maximum=1)
        operand = row["operand"]
        flow = row["flow"]
        if (
            opcode not in (PUSH, POP, PUSH_ACC)
            or stack not in (0, 1)
            or operand != ("parameter" if opcode == PUSH else "none")
            or flow != ("exit" if offset + 1 == length else "next")
        ):
            raise FieldProgramError("transferable scalar procedure guard is invalid")
    shape_sha256 = hashlib.sha256(_canonical(shape)).hexdigest()
    correctness = "parameterized-straight-line-batching.v1"
    procedure_id = hashlib.sha256(
        _canonical({"correctness": correctness, "shape": shape})
    ).hexdigest()
    if (
        raw["shape_sha256"] != shape_sha256
        or raw["procedure_id"] != procedure_id
        or raw["correctness"] != correctness
        or raw["status"] != "promoted"
    ):
        raise FieldProgramError("transferable scalar procedure identity is invalid")
    parameter_roles = [
        {
            "instruction": offset,
            "role": "literal",
            "type": "integer",
        }
        for offset, row in enumerate(shape)
        if row["operand"] == "parameter"
    ]
    if raw["parameter_roles"] != parameter_roles:
        raise FieldProgramError("transferable scalar parameter roles are invalid")
    evidence = raw["evidence_program_sha256"]
    if (
        not isinstance(evidence, list)
        or not evidence
        or len(set(evidence)) != len(evidence)
        or any(
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            for value in evidence
        )
    ):
        raise FieldProgramError("transferable scalar evidence is invalid")
    return {
        "procedure_id": procedure_id,
        "shape": shape,
        "shape_sha256": shape_sha256,
        "length": length,
        "parameter_roles": parameter_roles,
        "evidence_program_sha256": sorted(evidence),
        "correctness": correctness,
        "status": "promoted",
    }


def _advance_scalar_procedures(
    state: dict[str, Any], quantum: int
) -> tuple[int, bool]:
    """Advance bounded structural proof construction from field-owned cursors."""

    learning = dict(state["procedure_learning"])
    if learning.get("schema") != SCALAR_PROCEDURE_SCHEMA:
        raise FieldProgramError("regional scalar procedure state is invalid")
    program = state["program"]
    program_sha256 = hashlib.sha256(_canonical(program)).hexdigest()
    if learning.get("program_sha256") != program_sha256:
        raise FieldProgramError("regional scalar procedure guard is stale")
    hot_entries = [int(value) for value in learning["hot_entries"]]
    hot_cursor = int(learning["hot_cursor"])
    if hot_cursor >= len(hot_entries):
        return 1, True
    work = 0
    if not bool(learning["scan_complete"]):
        incoming = [int(value) for value in learning["incoming"]]
        cursor = int(learning["scan_cursor"])
        while cursor < len(program) and work < quantum:
            for target in _scalar_targets(program[cursor]):
                incoming[target] += 1
            cursor += 1
            work += 1
        learning["incoming"] = incoming
        learning["scan_cursor"] = cursor
        learning["scan_complete"] = cursor == len(program)
        learning["derivation_work"] = (
            int(learning["derivation_work"]) + work
        )
        state["procedure_learning"] = learning
        if work >= quantum or not learning["scan_complete"]:
            return max(1, work), False
    incoming = [int(value) for value in learning["incoming"]]
    promoted = list(learning["promoted"])
    transferable = list(learning.get("transferable", []))
    known = {int(row["entry"]) for row in promoted}
    candidate = [int(value) for value in learning["candidate_pcs"]]
    while hot_cursor < len(hot_entries) and work < quantum:
        entry = hot_entries[hot_cursor]
        if entry in known:
            hot_cursor += 1
            work += 1
            continue
        if not candidate:
            candidate = [entry]
            work += 1
        current = candidate[-1]
        opcode, next_a, next_b, next_c, _reserved = (
            int(value) for value in program[current]
        )
        if opcode == PUSH:
            successor = next_c
        elif opcode in (POP, PUSH_ACC):
            successor = next_b
        # Branch traces use the contiguous fall-through only as a candidate;
        # reuse remains exact because the execution loop below rechecks the
        # expected PC before every scalar transition.
        elif opcode == BRANCH:
            successor = (
                current + 1
                if current + 1 in (next_b, next_c)
                else -1
            )
        elif opcode == JUMP:
            successor = next_a
        else:
            successor = -1
        extend = (
            len(candidate) < SCALAR_SPECIALIZATION_MAX_BLOCK
            and successor == current + 1
            and successor < len(program)
            and incoming[successor] == 1
        )
        if extend and work < quantum:
            candidate.append(successor)
            work += 1
            continue
        if len(candidate) >= 2:
            identity = hashlib.sha256(
                _canonical(
                    {
                        "program_sha256": program_sha256,
                        "entry": entry,
                        "pcs": candidate,
                    }
                )
            ).hexdigest()
            try:
                shape = _scalar_transfer_shape(program, entry, len(candidate))
            except FieldProgramError:
                shape = None
            promoted.append(
                {
                    "procedure_id": identity,
                    "entry": entry,
                    "pcs": candidate,
                    "guard": {
                        "kind": "exact-program-version",
                        "program_sha256": program_sha256,
                    },
                    "correctness": "restricted-straight-line-proof.v1",
                    "status": "promoted",
                }
            )
            if shape is not None:
                shape_sha256 = hashlib.sha256(_canonical(shape)).hexdigest()
                matching = next(
                    (
                        row
                        for row in transferable
                        if row.get("shape_sha256") == shape_sha256
                    ),
                    None,
                )
                if matching is None:
                    transferable.append(
                        _canonical_transferable_procedure(
                            {
                                "procedure_id": hashlib.sha256(
                                    _canonical(
                                        {
                                            "correctness": (
                                                "parameterized-straight-line-batching.v1"
                                            ),
                                            "shape": shape,
                                        }
                                    )
                                ).hexdigest(),
                                "shape": shape,
                                "shape_sha256": shape_sha256,
                                "length": len(candidate),
                                "parameter_roles": [
                                    {
                                        "instruction": offset,
                                        "role": "literal",
                                        "type": "integer",
                                    }
                                    for offset, row in enumerate(shape)
                                    if row["operand"] == "parameter"
                                ],
                                "evidence_program_sha256": [program_sha256],
                                "correctness": (
                                    "parameterized-straight-line-batching.v1"
                                ),
                                "status": "promoted",
                            }
                        )
                    )
                else:
                    evidence = sorted(
                        set(matching["evidence_program_sha256"])
                        | {program_sha256}
                    )
                    matching["evidence_program_sha256"] = evidence
            known.add(entry)
        hot_cursor += 1
        candidate = []
    learning["hot_cursor"] = hot_cursor
    learning["candidate_pcs"] = candidate
    learning["promoted"] = promoted
    learning["transferable"] = [
        _canonical_transferable_procedure(row) for row in transferable
    ]
    learning["derivation_work"] = (
        int(learning["derivation_work"]) + work
    )
    state["procedure_learning"] = learning
    return max(1, work), hot_cursor >= len(hot_entries) and not candidate


def _scalar_step(state: Mapping[str, Any]) -> dict[str, Any]:
    """Execute one scalar primitive directly over typed regional data."""

    mutable = json.loads(_canonical(dict(state)).decode("utf-8"))
    profile = ComputerProfile(**dict(mutable["profile"]))
    program = mutable["program"]
    pc = _integer(
        mutable["pc"], "regional scalar pc",
        maximum=len(program) - 1,
    )
    row = program[pc]
    if (
        not isinstance(row, list)
        or len(row) != 5
        or any(isinstance(value, bool) or not isinstance(value, int) for value in row)
    ):
        raise FieldProgramError("regional scalar instruction is invalid")
    opcode, a, b, c, _reserved = (int(value) for value in row)
    left = [int(value) for value in mutable["left"]]
    right = [int(value) for value in mutable["right"]]
    accumulator = _integer(
        mutable["accumulator"], "regional scalar accumulator",
        maximum=EMPTY,
    )
    transitions = _integer(
        mutable["transitions"], "regional scalar transitions",
        maximum=profile.max_steps,
    )
    stack_reads = _integer(
        mutable["stack_reads"], "regional scalar stack reads",
        maximum=2**53,
    )
    stack_writes = _integer(
        mutable["stack_writes"], "regional scalar stack writes",
        maximum=2**53,
    )
    copied = _integer(
        mutable["field_cells_copied"], "regional scalar copied cells",
        maximum=2**53,
    ) + 2 * profile.field_cells
    if copied > 2**53:
        raise FieldProgramError("regional scalar copy ledger overflow")
    hot = [int(value) for value in mutable["pc_observations"]]
    if len(hot) != len(program):
        raise FieldProgramError("regional scalar observations are invalid")

    status = "running"
    reason = "none"
    next_pc = pc
    attempted = True
    if opcode == HALT:
        status = "halted"
        reason = "halt"
    elif opcode == PUSH:
        stack = left if a == 0 else right
        if a not in (0, 1):
            status, reason = "faulted", "invalid_instruction"
        elif len(stack) >= profile.stack_capacity:
            status, reason, attempted = "exhausted", "stack_capacity", False
        else:
            stack.append(b)
            stack_writes += 1
            next_pc = c
    elif opcode == POP:
        if a not in (0, 1):
            status, reason = "faulted", "invalid_instruction"
        else:
            stack = left if a == 0 else right
            accumulator = EMPTY if not stack else stack.pop()
            stack_reads += 1
            next_pc = b
    elif opcode == BRANCH:
        next_pc = b if accumulator == a else c
    elif opcode == PUSH_ACC:
        if a not in (0, 1):
            status, reason = "faulted", "invalid_instruction"
        elif accumulator == EMPTY:
            status, reason = "faulted", "push_acc_empty"
        else:
            stack = left if a == 0 else right
            if len(stack) >= profile.stack_capacity:
                status, reason, attempted = "exhausted", "stack_capacity", False
            else:
                stack.append(accumulator)
                stack_writes += 1
                next_pc = b
    elif opcode == PROPAGATE:
        if a not in (0, 1):
            status, reason = "faulted", "invalid_instruction"
        else:
            stack = left if a == 0 else right
            try:
                if len(stack) < 4:
                    raise FieldProgramError("propagation frame is missing")
                length = int.from_bytes(bytes(stack[-4:]), "little")
                if not 4 <= length <= len(stack):
                    raise FieldProgramError("propagation frame length is invalid")
                start = len(stack) - length
                raw = bytearray(stack[start:])
                result, prefix_end, lanes_start, _detail = _advance_propagation_frame(
                    raw, include_detail=False,
                )
                stack[start:start + prefix_end] = raw[:prefix_end]
                stack[start + lanes_start:-4] = raw[lanes_start:-4]
                accumulator = result
                stack_reads += length + 4
                stack_writes += prefix_end + length - 4 - lanes_start
                next_pc = b
            except (ValueError, OverflowError, TypeError):
                status, reason = "faulted", "invalid_state"
    elif opcode == JUMP:
        next_pc = a
    else:
        status, reason = "faulted", "invalid_instruction"

    mutable.update({
        "left": left,
        "right": right,
        "accumulator": accumulator,
        "stack_reads": stack_reads,
        "stack_writes": stack_writes,
        "field_cells_copied": copied,
    })
    if attempted:
        transitions += 1
        mutable["transitions"] = transitions
        mutable["pc"] = next_pc
        hot[pc] = hot[pc] // 2 if hot[pc] >= 65_535 else hot[pc]
        hot[pc] += 1
        if hot[pc] == 8:
            learning = dict(mutable["procedure_learning"])
            entries = [int(value) for value in learning["hot_entries"]]
            if pc not in entries:
                entries.append(pc)
                learning["hot_entries"] = entries
                mutable["procedure_learning"] = learning
        if status == "running" and transitions >= profile.max_steps:
            status, reason = "exhausted", "step_budget"
    mutable["pc_observations"] = hot
    mutable["status"] = status
    mutable["reason"] = reason
    return mutable


def scalar_regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance scalar state, applying only field-promoted exact blocks."""

    required = {
        "schema", "profile", "program", "pc", "left", "right",
        "accumulator", "status", "reason", "transitions", "stack_reads",
        "stack_writes", "field_cells_copied", "pc_observations",
        "procedure_learning", "outcome",
    }
    if (
        not isinstance(state, Mapping)
        or state.get("schema") != SCALAR_REGIONAL_STATE_SCHEMA
        or set(state) != required
    ):
        raise FieldProgramError("regional scalar state is invalid")
    if arguments:
        raise FieldProgramError("regional scalar kernel takes no arguments")
    _integer(
        quantum, "regional scalar quantum",
        minimum=1, maximum=SCALAR_REGIONAL_MAX_WORK,
    )
    current = json.loads(_canonical(dict(state)).decode("utf-8"))
    learning = current["procedure_learning"]
    if (
        not isinstance(learning, Mapping)
        or learning.get("schema") != SCALAR_PROCEDURE_SCHEMA
    ):
        raise FieldProgramError("regional scalar procedure state is invalid")
    program_sha256 = hashlib.sha256(
        _canonical(current["program"])
    ).hexdigest()
    planned: list[int] = [int(current["pc"])]
    for candidate in learning["promoted"]:
        guard = candidate.get("guard", {})
        pcs = [int(value) for value in candidate.get("pcs", ())]
        if (
            int(candidate.get("entry", -1)) == int(current["pc"])
            and candidate.get("status") == "promoted"
            and candidate.get("correctness")
            == "restricted-straight-line-proof.v1"
            and guard.get("kind") == "exact-program-version"
            and guard.get("program_sha256") == program_sha256
            and 2 <= len(pcs) <= SCALAR_SPECIALIZATION_MAX_BLOCK
        ):
            planned = pcs
            break
    if len(planned) == 1:
        for raw_candidate in learning.get("transferable", []):
            candidate = _canonical_transferable_procedure(raw_candidate)
            length = candidate["length"]
            try:
                expected_shape = _scalar_transfer_shape(
                    current["program"], int(current["pc"]), length
                )
            except FieldProgramError:
                continue
            expected_sha256 = hashlib.sha256(
                _canonical(expected_shape)
            ).hexdigest()
            if (
                candidate.get("shape") != expected_shape
                or candidate.get("shape_sha256") != expected_sha256
            ):
                continue
            planned = list(
                range(int(current["pc"]), int(current["pc"]) + length)
            )
            break
    applied = 0
    for expected_pc in planned:
        if applied >= quantum:
            break
        if (
            current["status"] != "running"
            or int(current["pc"]) != expected_pc
        ):
            break
        current = _scalar_step(current)
        applied += 1
    learning_work = 0
    if current["status"] == "running" and applied < quantum:
        learning = current["procedure_learning"]
        if learning.get("hot_entries"):
            learning_work, _ = _advance_scalar_procedures(
                current, quantum - applied
            )
    if (
        len(planned) >= 2
        and applied == len(planned)
    ):
        updated = dict(current["procedure_learning"])
        updated["block_invocations"] = (
            int(updated["block_invocations"]) + 1
        )
        updated["block_transitions"] = (
            int(updated["block_transitions"]) + applied
        )
        current["procedure_learning"] = updated
    charged_work = max(1, applied + learning_work)
    if current["status"] == "running":
        return KernelResult(
            state=current, status="yield", work=charged_work
        )
    outcome = _scalar_outcome(current)
    current["outcome"] = outcome
    return KernelResult(
        state=current,
        status="fault" if current["status"] == "faulted" else "done",
        work=charged_work,
        output=outcome,
    )


def scalar_procedure_regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Derive and promote bounded exact blocks as a charged transition."""

    if arguments:
        raise FieldProgramError("scalar procedure kernel takes no arguments")
    _integer(
        quantum, "scalar procedure quantum",
        minimum=1, maximum=SCALAR_REGIONAL_MAX_WORK,
    )
    current = json.loads(_canonical(dict(state)).decode("utf-8"))
    work, done = _advance_scalar_procedures(current, quantum)
    outcome = _scalar_outcome(current)
    current["outcome"] = outcome
    return KernelResult(
        state=current,
        status="done" if done else "yield",
        work=work,
        output=outcome,
    )


def regional_scalar_state(
    compiled: CompiledFieldProgram,
    profile: ComputerProfile,
    *,
    transferable_procedures: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Lower scalar execution into typed regional machine data."""

    if not isinstance(compiled, CompiledFieldProgram):
        raise FieldProgramError("CompiledFieldProgram required")
    if not isinstance(profile, ComputerProfile):
        raise FieldProgramError("ComputerProfile required")
    if len(compiled.left) > profile.stack_capacity or len(compiled.right) > profile.stack_capacity:
        raise FieldProgramError("compiled scalar stack exceeds profile capacity")
    if len(compiled.program) > profile.program_capacity:
        raise FieldProgramError("compiled scalar program exceeds profile capacity")
    transferable = [
        _canonical_transferable_procedure(row) for row in transferable_procedures
    ]
    return {
        "schema": SCALAR_REGIONAL_STATE_SCHEMA,
        "profile": profile.as_dict(),
        "program": [list(row) for row in compiled.program],
        "pc": compiled.entry,
        "left": list(compiled.left),
        "right": list(compiled.right),
        "accumulator": EMPTY,
        "status": "running",
        "reason": "none",
        "transitions": 0,
        "stack_reads": 0,
        "stack_writes": 0,
        "field_cells_copied": profile.field_cells,
        "pc_observations": [0] * len(compiled.program),
        "procedure_learning": {
            "schema": SCALAR_PROCEDURE_SCHEMA,
            "program_sha256": hashlib.sha256(
                _canonical([list(row) for row in compiled.program])
            ).hexdigest(),
            "promoted": [],
            "transferable": transferable,
            "hot_entries": [],
            "hot_cursor": 0,
            "scan_complete": False,
            "scan_cursor": 0,
            "incoming": [0] * len(compiled.program),
            "candidate_pcs": [],
            "derivation_work": 0,
            "block_invocations": 0,
            "block_transitions": 0,
        },
        "outcome": None,
    }


__all__ = [
    "COMPILED_REGIONAL_SCHEMA",
    "COMPILED_SCHEMA",
    "REGIONAL_SOURCE_SCHEMA",
    "MECHANISM_STEP_KERNEL",
    "MECHANISM_STEP_MAX_WORK",
    "SCALAR_REGIONAL_KERNEL",
    "SCALAR_REGIONAL_MAX_WORK",
    "SCALAR_PROCEDURE_KERNEL",
    "SCALAR_PROCEDURE_SCHEMA",
    "SCALAR_SPECIALIZATION_MAX_BLOCK",
    "SCALAR_REGIONAL_STATE_SCHEMA",
    "SCHEMA",
    "SEMANTIC_MECHANISM_KINDS",
    "SEMANTIC_PROGRAM_KINDS",
    "SEMANTIC_PROGRAM_SCHEMA",
    "SEMANTIC_REPRESENTATION_SCHEMA",
    "NULLABLE_TABLE_SCHEMA",
    "SURFACE_PROCEDURE_SCHEMA",
    "SEMANTIC_SEQUENCE_SCHEMA",
    "CompiledFieldProgram",
    "CompiledRegionalProgram",
    "FieldProgramError",
    "apply_semantic_representation_edits",
    "canonical_table",
    "canonical_semantic_representation_edits",
    "compile_regional_program",
    "compile_structured_program",
    "regional_scalar_state",
    "canonical_semantic_program_payload",
    "scalar_regional_kernel",
    "advance_surface_procedure",
    "execute_semantic_program",
    "scalar_procedure_regional_kernel",
    "semantic_program_payload",
    "table_from_rows",
]
