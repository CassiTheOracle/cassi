from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import struct
from typing import Literal

import torch

from cassi_bilateral_counterflow import (
    BilateralCounterflowController,
    CounterflowTelemetry,
)
from cassi_qi_field import QiFieldError, QiFieldState


_ADDRESS = struct.Struct(">8H")
_ADDRESS_SCALE = 1 << 15


def _exact_address(address: bytes) -> bytes:
    if not isinstance(address, bytes) or len(address) != _ADDRESS.size:
        raise QiFieldError("Mnemic address must be exactly 16 bytes")
    return address


def encode_mnemic_address(
    address: bytes,
    *,
    device: str | torch.device = "cpu",
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """Encode one exact 128-bit address into four complex field components."""
    if dtype not in (torch.float32, torch.float64):
        raise QiFieldError("Mnemic address lanes require float32 or float64")
    words = _ADDRESS.unpack(_exact_address(address))
    lanes = torch.tensor(
        [(word - _ADDRESS_SCALE) / _ADDRESS_SCALE for word in words],
        device=device,
        dtype=dtype,
    )
    return torch.complex(lanes[0::2], lanes[1::2])


def decode_mnemic_address(value: torch.Tensor | Sequence[complex]) -> bytes:
    """Decode four exact complex field components, rejecting malformed lanes."""
    tensor = torch.as_tensor(value)
    if tensor.shape != (4,) or not tensor.is_complex():
        raise QiFieldError("encoded Mnemic address must have four complex components")
    lanes = torch.stack((tensor.real, tensor.imag), dim=-1).reshape(-1)
    if not torch.isfinite(lanes).all().item():
        raise QiFieldError("encoded Mnemic address must be finite")
    if (torch.signbit(lanes) & (lanes == 0)).any().item():
        raise QiFieldError("encoded Mnemic address may not contain negative zero")
    scaled = lanes * _ADDRESS_SCALE + _ADDRESS_SCALE
    rounded = scaled.round()
    if not torch.equal(scaled, rounded):
        raise QiFieldError("encoded Mnemic address is off the exact uint16 grid")
    if ((rounded < 0) | (rounded > 0xFFFF)).any().item():
        raise QiFieldError("encoded Mnemic address contains an out-of-range word")
    return _ADDRESS.pack(*(int(word) for word in rounded.to(device="cpu").tolist()))


@dataclass(frozen=True, slots=True)
class MnemicThalamusConstraint:
    record_id: str
    address: bytes
    revision: str
    byte_start: int
    byte_end: int
    slot: int
    value: tuple[complex, ...]
    mask: tuple[float, ...]
    authority: float
    required: bool
    semantic_kind: str


@dataclass(frozen=True, slots=True)
class ThalamusPolicy:
    eligible_basins: tuple[int, ...]
    permitted_action_kinds: tuple[str, ...] = ()
    authority: float = 1.0
    authorization_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SymbolicTrajectory:
    basin_path: tuple[int, ...]
    symbols: tuple[str, ...]
    text: str
    source_addresses: tuple[bytes, ...]
    field_sha256: str


@dataclass(frozen=True, slots=True)
class OutcomeEquivalenceReceipt:
    surface_address: bytes
    basin_id: int | None
    decision: Literal["create", "reinforce", "separate", "abstain", "capacity"]
    field_sha256: str


@dataclass(frozen=True, slots=True)
class TypedActionDescriptor:
    basin_id: int
    action_id: str
    kind: str
    required_authority: float
    reversible: bool
    precondition_address: bytes
    effect_address: bytes


@dataclass(frozen=True, slots=True)
class TypedActionProposal:
    basin_path: tuple[int, ...]
    actions: tuple[TypedActionDescriptor, ...]
    authorization_path: tuple[str, ...]
    field_sha256: str
    inert: bool = True


def _validate_policy(policy: ThalamusPolicy) -> None:
    if not policy.eligible_basins:
        raise QiFieldError("Thalamus must authorize at least one eligible basin")
    if len(set(policy.eligible_basins)) != len(policy.eligible_basins) or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in policy.eligible_basins
    ):
        raise QiFieldError("Thalamus eligible basins must be distinct non-negative IDs")
    if not math.isfinite(policy.authority) or not 0.0 <= policy.authority <= 1.0:
        raise QiFieldError("Thalamus authority must be finite and in [0, 1]")
    if any(not isinstance(kind, str) or not kind for kind in policy.permitted_action_kinds):
        raise QiFieldError("permitted action kinds must be non-empty strings")
    if any(not isinstance(step, str) or not step for step in policy.authorization_path):
        raise QiFieldError("authorization path entries must be non-empty strings")


def _validate_constraint_identity(item: MnemicThalamusConstraint) -> None:
    _exact_address(item.address)
    if not isinstance(item.record_id, str) or not item.record_id:
        raise QiFieldError("record_id must be a non-empty string")
    if not isinstance(item.revision, str) or len(item.revision) != 64:
        raise QiFieldError("revision must be a SHA-256 digest")
    try:
        bytes.fromhex(item.revision)
    except ValueError as error:
        raise QiFieldError("revision must be a SHA-256 digest") from error
    for name, value in (
        ("byte_start", item.byte_start),
        ("byte_end", item.byte_end),
        ("slot", item.slot),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise QiFieldError(f"{name} must be a non-negative integer")
    if item.byte_end < item.byte_start:
        raise QiFieldError("Mnemic byte span is reversed")
    if not isinstance(item.semantic_kind, str) or not item.semantic_kind:
        raise QiFieldError("semantic_kind must be a non-empty string")
    if not math.isfinite(item.authority) or not 0.0 < item.authority <= 1.0:
        raise QiFieldError("candidate authority must be finite and in (0, 1]")
    if item.required and item.authority != 1.0:
        raise QiFieldError("required candidates must carry full deterministic authority")


def start_mnemic_thalamus_thought(
    controller: BilateralCounterflowController,
    state: QiFieldState,
    candidates: Sequence[MnemicThalamusConstraint],
    *,
    active_slots: int,
    policy: ThalamusPolicy,
) -> QiFieldState:
    """Translate exact records and deterministic authority into one field thought."""
    _validate_policy(policy)
    if not candidates:
        raise QiFieldError("at least one Mnemic candidate is required")
    latent_dim = controller.config.latent_dim
    complex_dtype = torch.complex64 if state.field.dtype == torch.float32 else torch.complex128
    values = torch.zeros(
        (active_slots, latent_dim),
        device=state.field.device,
        dtype=complex_dtype,
    )
    weights = torch.zeros(
        (active_slots, latent_dim),
        device=state.field.device,
        dtype=state.field.dtype,
    )
    hard = torch.zeros_like(weights, dtype=torch.bool)
    identities: dict[bytes, tuple[str, str, int, int, str]] = {}

    for item in candidates:
        if not isinstance(item, MnemicThalamusConstraint):
            raise QiFieldError("candidates must be MnemicThalamusConstraint values")
        _validate_constraint_identity(item)
        if item.slot >= active_slots:
            raise QiFieldError("candidate slot is outside the active trajectory")
        identity = (
            item.record_id,
            item.revision,
            item.byte_start,
            item.byte_end,
            item.semantic_kind,
        )
        previous_identity = identities.setdefault(item.address, identity)
        if previous_identity != identity:
            raise QiFieldError("Mnemic address collision across record identities")
        value = controller._coerce_latent(item.value, state)
        mask = controller._coerce_mask(item.mask, state, allow_empty=True)
        if item.required and torch.count_nonzero(mask).item() == 0:
            raise QiFieldError("required candidates must constrain at least one latent component")
        effective = mask if item.required else mask * item.authority
        for component in torch.nonzero(effective > 0.0, as_tuple=False).flatten().tolist():
            occupied = weights[item.slot, component] > 0.0
            if occupied and values[item.slot, component] != value[component]:
                if hard[item.slot, component] and item.required:
                    raise QiFieldError("contradictory required Mnemic constraints")
                if effective[component] == weights[item.slot, component]:
                    raise QiFieldError("equally authoritative Mnemic constraints conflict")
                if effective[component] < weights[item.slot, component]:
                    continue
            values[item.slot, component] = value[component]
            weights[item.slot, component] = effective[component]
            hard[item.slot, component] = item.required

    if not hard[0].all().item() or not torch.equal(weights[0], torch.ones_like(weights[0])):
        raise QiFieldError("slot zero requires one complete authoritative observation")
    goal_slot = active_slots - 1
    if torch.count_nonzero(weights[goal_slot]).item() == 0:
        raise QiFieldError("the terminal slot requires an authorized constraint")
    intermediate = {
        slot: (values[slot], weights[slot])
        for slot in range(1, goal_slot)
        if torch.count_nonzero(weights[slot]).item()
    }
    return controller.start_thought(
        state,
        values[0],
        values[goal_slot],
        active_slots=active_slots,
        goal_mask=weights[goal_slot],
        constraints=intermediate,
        eligible_basins=policy.eligible_basins,
    )


def render_symbolic_trajectory(
    controller: BilateralCounterflowController,
    state: QiFieldState,
    catalog: Mapping[int, str],
    *,
    source_addresses: Sequence[bytes] = (),
    separator: str = " ",
) -> SymbolicTrajectory:
    """Render only a settled whole trajectory through a fixed symbol catalog."""
    controller.validate_state(state)
    packed = controller._packed(state)
    _, status, _, encoded_plan, active_slots = controller._metadata(packed)
    if status != controller._SETTLED:
        raise QiFieldError("symbols may render only after unique field settlement")
    basin_path = tuple(value - 1 for value in encoded_plan[: active_slots - 1])
    symbols: list[str] = []
    for basin_id in basin_path:
        symbol = catalog.get(basin_id)
        if not isinstance(symbol, str) or not symbol:
            raise QiFieldError(f"symbol catalog has no rendering for basin {basin_id}")
        symbols.append(symbol)
    addresses = tuple(_exact_address(address) for address in source_addresses)
    return SymbolicTrajectory(
        basin_path=basin_path,
        symbols=tuple(symbols),
        text=separator.join(symbols),
        source_addresses=addresses,
        field_sha256=controller._tensor_sha256(state.field),
    )


def settle_symbolic_trajectory(
    controller: BilateralCounterflowController,
    state: QiFieldState,
    candidates: Sequence[MnemicThalamusConstraint],
    *,
    active_slots: int,
    policy: ThalamusPolicy,
    catalog: Mapping[int, str],
    separator: str = " ",
) -> tuple[QiFieldState, SymbolicTrajectory, tuple[CounterflowTelemetry, ...]]:
    active = start_mnemic_thalamus_thought(
        controller,
        state,
        candidates,
        active_slots=active_slots,
        policy=policy,
    )
    closed, trace = controller.run_until_closed(active)
    rendered = render_symbolic_trajectory(
        controller,
        closed,
        catalog,
        source_addresses=tuple(item.address for item in candidates),
        separator=separator,
    )
    return closed, rendered, trace


def consolidate_equivalent_outcome(
    controller: BilateralCounterflowController,
    state: QiFieldState,
    surface_address: bytes,
    before: torch.Tensor | Sequence[Sequence[complex | float]],
    after: torch.Tensor | Sequence[Sequence[complex | float]],
    *,
    successful: bool,
) -> tuple[QiFieldState, OutcomeEquivalenceReceipt]:
    """Route successful surface-distinct outcomes through the shared basin law."""
    address = _exact_address(surface_address)
    if not successful:
        raise QiFieldError("failed outcomes may not induce semantic equivalence")
    controller.validate_state(state)
    _, status, _, _, _ = controller._metadata(controller._packed(state))
    if status == controller._IDLE:
        result, receipt = controller.observe_transitions(state, before, after)
    else:
        result, receipt = controller.consolidate_outcome(state, before, after)
    return result, OutcomeEquivalenceReceipt(
        surface_address=address,
        basin_id=receipt.basin_id,
        decision=receipt.decision,
        field_sha256=receipt.field_sha256,
    )


def propose_typed_actions(
    controller: BilateralCounterflowController,
    state: QiFieldState,
    catalog: Mapping[int, TypedActionDescriptor],
    *,
    policy: ThalamusPolicy,
    start_address: bytes,
    goal_address: bytes,
) -> TypedActionProposal:
    """Validate and return an inert action chain; this function never executes it."""
    _validate_policy(policy)
    start = _exact_address(start_address)
    goal = _exact_address(goal_address)
    controller.validate_state(state)
    packed = controller._packed(state)
    _, status, _, encoded_plan, active_slots = controller._metadata(packed)
    if status != controller._SETTLED:
        raise QiFieldError("actions may be proposed only after unique field settlement")
    basin_path = tuple(value - 1 for value in encoded_plan[: active_slots - 1])
    actions: list[TypedActionDescriptor] = []
    expected_precondition = start
    for basin_id in basin_path:
        descriptor = catalog.get(basin_id)
        if not isinstance(descriptor, TypedActionDescriptor) or descriptor.basin_id != basin_id:
            raise QiFieldError(f"action catalog has no exact descriptor for basin {basin_id}")
        _exact_address(descriptor.precondition_address)
        _exact_address(descriptor.effect_address)
        if basin_id not in policy.eligible_basins:
            raise QiFieldError("settled action is outside Thalamus eligibility")
        if descriptor.kind not in policy.permitted_action_kinds:
            raise QiFieldError("settled action kind is not permitted by Thalamus")
        if (
            not math.isfinite(descriptor.required_authority)
            or not 0.0 <= descriptor.required_authority <= 1.0
            or policy.authority < descriptor.required_authority
        ):
            raise QiFieldError("Thalamus authority is insufficient for settled action")
        if descriptor.precondition_address != expected_precondition:
            raise QiFieldError("typed action precondition/effect chain is discontinuous")
        expected_precondition = descriptor.effect_address
        actions.append(descriptor)
    if expected_precondition != goal:
        raise QiFieldError("typed action chain does not reach the declared goal")
    if actions and not policy.authorization_path:
        raise QiFieldError("typed action proposal requires an explicit authorization path")
    return TypedActionProposal(
        basin_path=basin_path,
        actions=tuple(actions),
        authorization_path=policy.authorization_path,
        field_sha256=controller._tensor_sha256(state.field),
    )


def propose_predicted_action(
    controller: BilateralCounterflowController,
    state: QiFieldState,
    descriptor: TypedActionDescriptor,
    *,
    policy: ThalamusPolicy,
    start_address: bytes,
    effect_address: bytes,
) -> TypedActionProposal:
    """Authorize one inert action selected by a frozen transition prediction."""
    _validate_policy(policy)
    controller.validate_state(state)
    start = _exact_address(start_address)
    effect = _exact_address(effect_address)
    if descriptor.basin_id not in policy.eligible_basins:
        raise QiFieldError("predicted action is outside Thalamus eligibility")
    if descriptor.kind not in policy.permitted_action_kinds:
        raise QiFieldError("predicted action kind is not permitted by Thalamus")
    if (
        not math.isfinite(descriptor.required_authority)
        or not 0.0 <= descriptor.required_authority <= 1.0
        or policy.authority < descriptor.required_authority
    ):
        raise QiFieldError("Thalamus authority is insufficient for predicted action")
    if descriptor.precondition_address != start or descriptor.effect_address != effect:
        raise QiFieldError("predicted action does not match its exact transition")
    if not policy.authorization_path:
        raise QiFieldError("typed action proposal requires an explicit authorization path")
    return TypedActionProposal(
        basin_path=(descriptor.basin_id,),
        actions=(descriptor,),
        authorization_path=policy.authorization_path,
        field_sha256=controller._tensor_sha256(state.field),
    )
