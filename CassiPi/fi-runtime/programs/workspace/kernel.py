"""Regional-kernel seam for the shared field-owned research workspace."""
from __future__ import annotations

from typing import Any, Mapping

from cassi_field_regions import KernelResult

from .runtime import RUNTIME_SCHEMA, advance, initial_state


REGIONAL_KERNEL_NAME = "field-research-workspace"
REGIONAL_STATE_SCHEMA = RUNTIME_SCHEMA
REGIONAL_KERNEL_MAX_WORK = 1


class WorkspaceKernelError(ValueError):
    """Invalid workspace admission or operation."""


def regional_state(
    *,
    owner_id: str = "owner",
    member_id: str = "member",
    workspace_id: str = "research",
    principal: str = "owner",
    limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    return initial_state(
        owner_id=owner_id,
        member_id=member_id,
        workspace_id=workspace_id,
        principal=principal,
        limits=limits,
    )


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    if not isinstance(state, Mapping) or state.get("schema") != RUNTIME_SCHEMA:
        raise WorkspaceKernelError("field workspace state is invalid")
    if not isinstance(arguments, Mapping):
        raise WorkspaceKernelError("field workspace arguments must be a mapping")
    if quantum != 1:
        raise WorkspaceKernelError("workspace operations consume one logical work unit")
    try:
        successor, status, work, output, events = advance(state, arguments, quantum)
    except ValueError as exc:
        raise WorkspaceKernelError(str(exc)) from exc
    return KernelResult(
        state=successor,
        status=status,
        work=work,
        output=output,
        events=events,
    )


__all__ = [
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_STATE_SCHEMA",
    "WorkspaceKernelError",
    "regional_kernel",
    "regional_state",
]
