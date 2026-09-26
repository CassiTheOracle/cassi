"""Regional-kernel seam for field-owned model graph continuations."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Sequence

if TYPE_CHECKING:  # pragma: no cover - typing only
    from cassi_field_regions import KernelResult

from .records import ModelPackage
from .runtime import RUNTIME_SCHEMA, advance, initial_state


REGIONAL_KERNEL_NAME = "field-model-program"
REGIONAL_STATE_SCHEMA = RUNTIME_SCHEMA
REGIONAL_KERNEL_MAX_WORK = 64


class ModelKernelError(ValueError):
    """Invalid model admission or bounded kernel operation."""


def regional_state(
    package: ModelPackage | Mapping[str, Any],
    *,
    prompt_tokens: Sequence[int],
    owner_id: str = "owner",
    member_id: str = "member",
    lineage_id: str = "lineage",
    operation_id: str = "model-main",
    scope_id: str = "model",
    max_new_tokens: int = 1,
    stop_tokens: Sequence[int] = (),
    sampler: Mapping[str, Any] | None = None,
    output_tensors: Sequence[str] = (),
    limits: Mapping[str, int] | None = None,
    backend_policy: str = "auto",
    rng_seed: int = 1,
    graph_site_modes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return initial_state(
        package,
        prompt_tokens=prompt_tokens,
        owner_id=owner_id,
        member_id=member_id,
        lineage_id=lineage_id,
        operation_id=operation_id,
        scope_id=scope_id,
        max_new_tokens=max_new_tokens,
        stop_tokens=stop_tokens,
        sampler=sampler,
        output_tensors=output_tensors,
        limits=limits,
        backend_policy=backend_policy,
        rng_seed=rng_seed,
        graph_site_modes=graph_site_modes,
    )


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
    *,
    _owned_state: bool = False,
) -> KernelResult:
    if not isinstance(state, Mapping) or state.get("schema") != RUNTIME_SCHEMA:
        raise ModelKernelError("field model state is invalid")
    if not isinstance(arguments, Mapping):
        raise ModelKernelError("field model arguments must be a mapping")
    if isinstance(quantum, bool) or not isinstance(quantum, int) or not 1 <= quantum <= REGIONAL_KERNEL_MAX_WORK:
        raise ModelKernelError("field model quantum is outside its bound")
    try:
        successor, status, work, output, events = advance(
            state, arguments, quantum, _owned_state=_owned_state
        )
    except ValueError as exc:
        raise ModelKernelError(str(exc)) from exc
    from cassi_field_regions import KernelResult

    return KernelResult(
        state=successor,
        status=status,
        work=work,
        output=output,
        events=events,
    )


__all__ = [
    "ModelKernelError",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_STATE_SCHEMA",
    "regional_kernel",
    "regional_state",
]
