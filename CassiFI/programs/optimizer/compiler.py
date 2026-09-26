"""Fixed, bounded lowering for exact field-program specializations.

The compiler performs only transformations whose local primitive contract is
known.  It does not execute guest callables or choose whether an artifact should
be adopted; that choice belongs to the owner continuation.
"""
from __future__ import annotations

import base64
import math
import operator
from typing import Any, Mapping, Sequence
from programs.python.records import PythonProgram, decode_record, digest_value

from .records import CompiledArtifact


class OptimizationCompilerError(ValueError):
    """A proposed specialization cannot be lowered exactly."""


_BINARY = {
    "add": operator.add,
    "sub": operator.sub,
    "mul": operator.mul,
    "truediv": operator.truediv,
    "floordiv": operator.floordiv,
    "mod": operator.mod,
    "pow": operator.pow,
    "lshift": operator.lshift,
    "rshift": operator.rshift,
    "or": operator.or_,
    "xor": operator.xor,
    "and": operator.and_,
}
_CONTROL_TARGET_OPS = {
    "ASYNC_FOR_ITER",
    "CHAIN_GUARD",
    "FOR_ITER",
    "JUMP",
    "JUMP_IF_FALSE",
    "JUMP_IF_FALSE_OR_POP",
    "JUMP_IF_NONE",
    "JUMP_IF_TRUE",
    "JUMP_IF_TRUE_OR_POP",
    "SETUP_EXCEPT",
    "SETUP_FINALLY",
    "SETUP_LOOP",
    "WITH_ENTER",
    "WITH_ENTER_ASYNC",
}


def _program(value: PythonProgram | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(value, PythonProgram):
        return value.as_dict()
    try:
        decoded = decode_record(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise OptimizationCompilerError("optimizer requires a PythonProgram") from exc
    if not isinstance(decoded, PythonProgram):
        raise OptimizationCompilerError("optimizer requires a PythonProgram")
    return decoded.as_dict()

def _host_literal(record: Mapping[str, Any]) -> Any:
    kind = record.get("kind")
    if kind == "none":
        return None
    if kind == "bool":
        return bool(record["value"])
    if kind == "int":
        return int(record["value"])
    if kind == "float":
        return float.fromhex(str(record["value"]))
    if kind == "complex":
        return complex(
            float.fromhex(str(record["real"])),
            float.fromhex(str(record["imag"])),
        )
    if kind == "str":
        return str(record["value"])
    if kind == "bytes":
        return base64.b64decode(str(record["value"]).encode("ascii"), validate=True)
    raise OptimizationCompilerError("literal is not a foldable scalar")


def _literal(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {"kind": "none"}
    if isinstance(value, bool):
        return {"kind": "bool", "value": value}
    if isinstance(value, int):
        if value.bit_length() > 1_048_576:
            raise OptimizationCompilerError("folded integer exceeds the runtime bound")
        return {"kind": "int", "value": str(value)}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise OptimizationCompilerError("folded float is non-finite")
        return {"kind": "float", "value": value.hex()}
    if isinstance(value, complex):
        if not math.isfinite(value.real) or not math.isfinite(value.imag):
            raise OptimizationCompilerError("folded complex value is non-finite")
        return {"kind": "complex", "real": value.real.hex(), "imag": value.imag.hex()}
    if isinstance(value, str):
        if len(value.encode("utf-8", "surrogatepass")) > 1_048_576:
            raise OptimizationCompilerError("folded string exceeds the runtime bound")
        return {"kind": "str", "value": value}
    if isinstance(value, bytes):
        if len(value) > 1_048_576:
            raise OptimizationCompilerError("folded bytes exceed the runtime bound")
        return {"kind": "bytes", "value": base64.b64encode(value).decode("ascii")}
    raise OptimizationCompilerError("folded result type is unsupported")


def _fold(left: Mapping[str, Any], right: Mapping[str, Any], operation: str) -> Mapping[str, Any]:
    function = _BINARY.get(operation)
    if function is None or operation == "matmul":
        raise OptimizationCompilerError("operation has no exact scalar fold")
    a = _host_literal(left)
    b = _host_literal(right)
    allowed = (type(None), bool, int, float, complex, str, bytes)
    if type(a) not in allowed or type(b) not in allowed:
        raise OptimizationCompilerError("operands are not exact scalar literals")
    if operation in {"lshift", "rshift"} and (not isinstance(b, int) or b < 0 or b > 1_048_576):
        raise OptimizationCompilerError("literal shift is outside the runtime bound")
    if operation == "pow" and isinstance(b, int) and abs(b) > 4_096:
        raise OptimizationCompilerError("literal exponent is outside the compiler bound")
    try:
        result = function(a, b)
    except (ArithmeticError, TypeError, ValueError, OverflowError) as exc:
        raise OptimizationCompilerError("literal operation is not safely foldable") from exc
    return _literal(result)


def _targets(value: Any) -> set[int]:
    result: set[int] = set()
    if isinstance(value, bool):
        return result
    if isinstance(value, int):
        result.add(value)
    elif isinstance(value, Mapping):
        for member in value.values():
            result.update(_targets(member))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for member in value:
            result.update(_targets(member))
    return result


def _control_targets(instructions: Sequence[Mapping[str, Any]]) -> set[int]:
    result: set[int] = set()
    for instruction in instructions:
        if instruction.get("op") in _CONTROL_TARGET_OPS:
            result.update(_targets(instruction.get("arg")))
    return result


def _artifact(
    *,
    kind: str,
    program: Mapping[str, Any],
    code_id: str,
    start_pc: int,
    next_pc: int,
    instructions: Sequence[Mapping[str, Any]],
    replacement: Mapping[str, Any],
    guards: Sequence[Mapping[str, Any]],
    semantics_sha256: str,
    regional_catalog_sha256: str,
    arithmetic_profile_sha256: str,
    target_profile: Mapping[str, Any],
    dependencies: Sequence[str],
    proof: Mapping[str, Any],
) -> CompiledArtifact:
    identity = {
        "kind": kind,
        "program_sha256": digest_value(program),
        "code_id": code_id,
        "start_pc": start_pc,
        "next_pc": next_pc,
        "original_sha256": digest_value(list(instructions)),
        "replacement": replacement,
        "guards": list(guards),
        "semantics_sha256": semantics_sha256,
        "regional_catalog_sha256": regional_catalog_sha256,
        "arithmetic_profile_sha256": arithmetic_profile_sha256,
        "target_profile": dict(target_profile),
        "dependencies": list(dependencies),
    }
    artifact_id = f"compiled:{digest_value(identity)[:32]}"
    safe_points = (
        {
            "optimized_offset": 0,
            "interpreter_pc": start_pc,
            "stack": "unchanged-before-replacement",
            "operations": "preserve-settled-callback-and-effect-tokens",
        },
        {
            "optimized_offset": 1,
            "interpreter_pc": next_pc,
            "stack": "replacement-complete",
            "operations": "preserve-settled-callback-and-effect-tokens",
        },
    )
    return CompiledArtifact(
        artifact_id=artifact_id,
        kind=kind,
        program_id=str(program["program_id"]),
        program_version=int(program["version"]),
        program_sha256=digest_value(program),
        source_sha256=str(program["source_sha256"]),
        code_id=code_id,
        start_pc=start_pc,
        next_pc=next_pc,
        original_sha256=digest_value(list(instructions)),
        replacement=replacement,
        guards=tuple(guards),
        semantics_sha256=semantics_sha256,
        regional_catalog_sha256=regional_catalog_sha256,
        arithmetic_profile_sha256=arithmetic_profile_sha256,
        target_profile=target_profile,
        dependencies=tuple(dependencies),
        logical_instructions=next_pc - start_pc,
        safe_points=safe_points,
        deoptimization={
            "before": {"interpreter_pc": start_pc, "stack": "identity"},
            "after": {"interpreter_pc": next_pc, "stack": "replacement-complete"},
            "preserve": [
                "heap-references",
                "frame-stack",
                "exception-state",
                "logical-charges",
                "settled-callback-tokens",
                "settled-effect-tokens",
            ],
            "restart_completed_effects": False,
        },
        proof=proof,
    )


def compile_constant_fold_at(
    value: PythonProgram | Mapping[str, Any],
    *,
    code_id: str,
    pc: int,
    semantics_sha256: str,
    regional_catalog_sha256: str,
    arithmetic_profile_sha256: str,
    target_profile: Mapping[str, Any],
) -> CompiledArtifact | None:
    """Try one bounded, locally proved scalar-literal replacement."""

    program = _program(value)
    try:
        instructions = program["code"]["codes"][code_id]["instructions"]
    except (KeyError, TypeError) as exc:
        raise OptimizationCompilerError("optimizer code identity is unavailable") from exc
    if isinstance(pc, bool) or not isinstance(pc, int) or pc < 0:
        raise OptimizationCompilerError("optimizer program counter is invalid")
    if pc + 2 >= len(instructions):
        return None
    targets = _control_targets(instructions)
    window = instructions[pc : pc + 3]
    if not (
        window[0].get("op") == "LOAD_CONST"
        and window[1].get("op") == "LOAD_CONST"
        and window[2].get("op") == "BINARY"
        and pc + 1 not in targets
        and pc + 2 not in targets
    ):
        return None
    try:
        literal = _fold(
            window[0]["arg"],
            window[1]["arg"],
            str(window[2]["arg"]),
        )
    except (KeyError, OptimizationCompilerError):
        return None
    return _artifact(
        kind="constant-fold",
        program=program,
        code_id=code_id,
        start_pc=pc,
        next_pc=pc + 3,
        instructions=window,
        replacement={"op": "LOAD_CONST", "arg": literal},
        guards=(),
        semantics_sha256=semantics_sha256,
        regional_catalog_sha256=regional_catalog_sha256,
        arithmetic_profile_sha256=arithmetic_profile_sha256,
        target_profile=target_profile,
        dependencies=tuple(program.get("dependencies", ())),
        proof={
            "status": "proved-local",
            "method": "closed primitive-contract evaluation",
            "domain": [
                window[0]["arg"].get("kind"),
                window[1]["arg"].get("kind"),
            ],
            "operation": window[2]["arg"],
            "control_entry_check": "no-target-enters-replacement",
            "observable_effects": [],
        },
    )


def compile_constant_folds(
    value: PythonProgram | Mapping[str, Any],
    *,
    semantics_sha256: str,
    regional_catalog_sha256: str,
    arithmetic_profile_sha256: str,
    target_profile: Mapping[str, Any],
    max_artifacts: int = 256,
) -> tuple[CompiledArtifact, ...]:
    """Lower a bounded complete set of locally proved literal expressions."""

    if isinstance(max_artifacts, bool) or not 1 <= max_artifacts <= 4_096:
        raise OptimizationCompilerError("max_artifacts is outside its bound")
    program = _program(value)
    artifacts: list[CompiledArtifact] = []
    for code_id in sorted(program["code"]["codes"]):
        instructions = program["code"]["codes"][code_id]["instructions"]
        pc = 0
        while pc < len(instructions) and len(artifacts) < max_artifacts:
            artifact = compile_constant_fold_at(
                program,
                code_id=code_id,
                pc=pc,
                semantics_sha256=semantics_sha256,
                regional_catalog_sha256=regional_catalog_sha256,
                arithmetic_profile_sha256=arithmetic_profile_sha256,
                target_profile=target_profile,
            )
            if artifact is None:
                pc += 1
            else:
                artifacts.append(artifact)
                pc = artifact.next_pc
        if len(artifacts) >= max_artifacts:
            break
    return tuple(artifacts)


def compile_guarded_load_name(
    value: PythonProgram | Mapping[str, Any],
    *,
    code_id: str,
    pc: int,
    guards: Sequence[Mapping[str, Any]],
    cached_value: Mapping[str, Any],
    semantics_sha256: str,
    regional_catalog_sha256: str,
    arithmetic_profile_sha256: str,
    target_profile: Mapping[str, Any],
) -> CompiledArtifact:
    """Lower one observed name lookup behind exact environment-version guards."""

    program = _program(value)
    try:
        instruction = program["code"]["codes"][code_id]["instructions"][pc]
    except (KeyError, IndexError, TypeError) as exc:
        raise OptimizationCompilerError("specialization program counter is unavailable") from exc
    if instruction.get("op") != "LOAD_NAME":
        raise OptimizationCompilerError("guarded name specialization requires LOAD_NAME")
    if not guards:
        raise OptimizationCompilerError("guarded name specialization requires environment guards")
    for guard in guards:
        if guard.get("kind") != "heap-version" or not isinstance(guard.get("object_id"), str):
            raise OptimizationCompilerError("name specialization guard is invalid")
    return _artifact(
        kind="guarded-load-name",
        program=program,
        code_id=code_id,
        start_pc=pc,
        next_pc=pc + 1,
        instructions=(instruction,),
        replacement={
            "op": "LOAD_CACHED_NAME",
            "name": instruction["arg"],
            "value": dict(cached_value),
        },
        guards=guards,
        semantics_sha256=semantics_sha256,
        regional_catalog_sha256=regional_catalog_sha256,
        arithmetic_profile_sha256=arithmetic_profile_sha256,
        target_profile=target_profile,
        dependencies=tuple(program.get("dependencies", ())),
        proof={
            "status": "guarded-exact",
            "method": "environment identity-generation-version guard",
            "fallback": "original LOAD_NAME at same interpreter safe point",
            "observable_effects": [],
        },
    )


def validate_portable_artifact(
    artifact_value: CompiledArtifact | Mapping[str, Any],
    program_value: PythonProgram | Mapping[str, Any],
    *,
    semantics_sha256: str,
    regional_catalog_sha256: str,
    arithmetic_profile_sha256: str,
    target_profile: Mapping[str, Any],
) -> CompiledArtifact:
    """Re-derive a portable artifact before admitting it to another owner."""

    try:
        artifact = (
            artifact_value
            if isinstance(artifact_value, CompiledArtifact)
            else CompiledArtifact.from_dict(artifact_value)
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OptimizationCompilerError(
            "portable compiled artifact is invalid"
        ) from exc
    if artifact.kind != "constant-fold" or artifact.guards:
        raise OptimizationCompilerError(
            "only guard-free proved constant folds are portable"
        )
    expected_profile = dict(target_profile)
    for actual, expected, label in (
        (artifact.semantics_sha256, semantics_sha256, "semantics"),
        (
            artifact.regional_catalog_sha256,
            regional_catalog_sha256,
            "regional catalog",
        ),
        (
            artifact.arithmetic_profile_sha256,
            arithmetic_profile_sha256,
            "arithmetic profile",
        ),
        (artifact.target_profile, expected_profile, "target profile"),
    ):
        if actual != expected:
            raise OptimizationCompilerError(
                f"compiled artifact {label} does not match this owner"
            )
    rebuilt = compile_constant_fold_at(
        program_value,
        code_id=artifact.code_id,
        pc=artifact.start_pc,
        semantics_sha256=semantics_sha256,
        regional_catalog_sha256=regional_catalog_sha256,
        arithmetic_profile_sha256=arithmetic_profile_sha256,
        target_profile=expected_profile,
    )
    if rebuilt is None or rebuilt.as_dict() != artifact.as_dict():
        raise OptimizationCompilerError(
            "compiled artifact cannot be re-derived from the resident program"
        )
    return artifact


__all__ = [
    "OptimizationCompilerError",
    "compile_constant_fold_at",
    "compile_constant_folds",
    "compile_guarded_load_name",
    "validate_portable_artifact",
]