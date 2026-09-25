"""Fixed regional-kernel seam for the field-owned Python continuation machine."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from cassi_field_regions import KernelResult

from .compiler import compile_python
from .records import PythonProgram, decode_record
from .runtime import (
    DEFAULT_LIMITS,
    RUNTIME_SCHEMA,
    RuntimeError as PythonRuntimeError,
    advance as advance_python,
    initial_state as initial_python_state,
)


REGIONAL_KERNEL_NAME = "field-python-interpreter"
REGIONAL_STATE_SCHEMA = RUNTIME_SCHEMA
REGIONAL_KERNEL_MAX_WORK = 64


class PythonKernelError(ValueError):
    """Invalid admission or bounded Python-kernel operation."""


def _text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 512
        or any(ord(character) < 32 for character in value)
    ):
        raise PythonKernelError(f"{label} must be bounded nonempty text")
    return value


def regional_state(
    source: str | PythonProgram | Mapping[str, Any],
    *,
    mode: str = "exec",
    module: str = "__main__",
    package: str | None = None,
    filename: str = "<field>",
    inputs: Mapping[str, Any] | None = None,
    owner_id: str = "owner",
    member_id: str = "member",
    lineage_id: str = "lineage",
    operation_id: str = "python-main",
    capabilities: Sequence[str] = (),
    limits: Mapping[str, int] | None = None,
    module_sources: Mapping[str, Mapping[str, Any]] | None = None,
    backend_policy: str = "logical-cpu",
    regional_catalog_sha256: str | None = None,
) -> dict[str, Any]:
    """Compile guest source and create its complete resumable regional state."""
    max_source_bytes = DEFAULT_LIMITS["max_source_bytes"]
    if limits is not None:
        if not isinstance(limits, Mapping):
            raise PythonKernelError("runtime limits must be a mapping")
        max_source_bytes = limits.get("max_source_bytes", max_source_bytes)
        if (
            isinstance(max_source_bytes, bool)
            or not isinstance(max_source_bytes, int)
            or max_source_bytes < 1
        ):
            raise PythonKernelError("runtime limit max_source_bytes is invalid")


    if isinstance(source, str):
        program = compile_python(
            source,
            mode=mode,
            module=module,
            package=package,
            source_name=filename,
            max_source_bytes=max_source_bytes,
        )
    elif isinstance(source, PythonProgram):
        program = source
    elif isinstance(source, Mapping):
        decoded = decode_record(source)
        if not isinstance(decoded, PythonProgram):
            raise PythonKernelError(
                "source mapping must describe a PythonProgram"
            )
        program = decoded
    else:
        raise PythonKernelError("source must be text or a PythonProgram")
    return initial_python_state(
        program,
        inputs=inputs,
        owner_id=_text(owner_id, "owner_id"),
        member_id=_text(member_id, "member_id"),
        lineage_id=_text(lineage_id, "lineage_id"),
        operation_id=_text(operation_id, "operation_id"),
        capabilities=capabilities,
        limits=limits,
        module_sources=module_sources,
        backend_policy=backend_policy,
        regional_catalog_sha256=regional_catalog_sha256,
    )


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance one bounded quantum of the field-owned Python continuation."""

    if not isinstance(state, Mapping) or state.get("schema") != RUNTIME_SCHEMA:
        raise PythonKernelError("field Python regional state is invalid")
    if not isinstance(arguments, Mapping):
        raise PythonKernelError("field Python arguments must be a mapping")
    if (
        isinstance(quantum, bool)
        or not isinstance(quantum, int)
        or not 1 <= quantum <= REGIONAL_KERNEL_MAX_WORK
    ):
        raise PythonKernelError("field Python quantum is outside its bound")
    try:
        successor, status, work, output, events = advance_python(
            state, arguments, quantum
        )
    except PythonRuntimeError as exc:
        raise PythonKernelError(str(exc)) from exc
    return KernelResult(
        state=successor,
        status=status,
        work=work,
        output=output,
        events=(),
    )


__all__ = [
    "PythonKernelError",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_STATE_SCHEMA",
    "regional_kernel",
    "regional_state",
]
