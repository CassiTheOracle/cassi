from __future__ import annotations

import random

import pytest
import torch

from cassi_bilateral_counterflow import (
    BilateralCounterflowConfig,
    BilateralCounterflowController,
)
from cassi_counterflow_reasoner import (
    MnemicThalamusConstraint,
    ThalamusPolicy,
    TypedActionDescriptor,
    consolidate_equivalent_outcome,
    decode_mnemic_address,
    encode_mnemic_address,
    propose_typed_actions,
    render_symbolic_trajectory,
    settle_symbolic_trajectory,
    start_mnemic_thalamus_thought,
)
from cassi_qi_field import QiFieldError, QiFieldState


def _operators() -> tuple[torch.Tensor, ...]:
    a = torch.tensor(
        [[0, 0, 0, 1], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]],
        dtype=torch.complex128,
    )
    b = torch.diag(torch.tensor([1, -1, 1j, -1j], dtype=torch.complex128))
    c = torch.fft.fft(torch.eye(4, dtype=torch.complex128), dim=0, norm="ortho")
    return a, b, c


def _trained() -> tuple[BilateralCounterflowController, QiFieldState, tuple[int, ...]]:
    controller = BilateralCounterflowController(
        BilateralCounterflowConfig(slot_count=4, max_basins=6)
    )
    state = controller.initial_state(dtype=torch.float64)
    basis = torch.eye(4, dtype=torch.complex128)
    basin_ids: list[int] = []
    for operator in _operators():
        state, receipt = controller.observe_transitions(
            state,
            basis,
            torch.einsum("ij,nj->ni", operator, basis),
        )
        assert receipt.basin_id is not None
        basin_ids.append(receipt.basin_id)
    return controller, state, tuple(basin_ids)


def _trajectory() -> tuple[torch.Tensor, ...]:
    a, b, c = _operators()
    start = torch.tensor(
        [0.23 + 0.61j, -0.71 + 0.17j, 0.42 - 0.38j, 0.55 + 0.09j],
        dtype=torch.complex128,
    )
    first = b @ start
    second = c @ first
    return start, first, second, a @ second


def _candidate(
    address_byte: int,
    slot: int,
    value: torch.Tensor,
    *,
    mask: tuple[float, ...] = (1.0, 1.0, 1.0, 1.0),
    authority: float = 1.0,
    required: bool = True,
    revision: int = 1,
) -> MnemicThalamusConstraint:
    return MnemicThalamusConstraint(
        record_id=f"record-{address_byte:02x}",
        address=bytes([address_byte]) * 16,
        revision=f"{revision:064x}",
        byte_start=slot * 8,
        byte_end=(slot + 1) * 8,
        slot=slot,
        value=tuple(complex(item) for item in value.tolist()),
        mask=mask,
        authority=authority,
        required=required,
        semantic_kind="trajectory-anchor",
    )


def _settled_symbolic():
    controller, state, basin_ids = _trained()
    values = _trajectory()
    candidates = (
        _candidate(0x10, 0, values[0]),
        _candidate(
            0x12,
            2,
            values[2],
            mask=(1.0, 0.0, 1.0, 0.0),
            authority=0.75,
            required=False,
        ),
        _candidate(0x13, 3, values[3]),
    )
    policy = ThalamusPolicy(eligible_basins=basin_ids)
    expected = (basin_ids[1], basin_ids[2], basin_ids[0])
    closed, rendered, trace = settle_symbolic_trajectory(
        controller,
        state,
        candidates,
        active_slots=4,
        policy=policy,
        catalog={expected[0]: "phase", expected[1]: "gather", expected[2]: "turn"},
    )
    return controller, state, closed, values, basin_ids, expected, rendered, trace


def test_exact_128_bit_address_codec_roundtrips_every_word_and_dtype(tmp_path) -> None:
    rng = random.Random(20260831)
    addresses = (
        bytes(16),
        bytes([0xFF]) * 16,
        bytes.fromhex("0001ffff7fff80001234abcd55aaaa55"),
        *(rng.randbytes(16) for _ in range(32)),
    )
    for dtype in (torch.float32, torch.float64):
        for address in addresses:
            encoded = encode_mnemic_address(address, dtype=dtype)
            assert encoded.shape == (4,)
            assert decode_mnemic_address(encoded) == address
            checkpoint = tmp_path / f"{dtype}-{address.hex()}.pt"
            torch.save(encoded, checkpoint)
            restored = torch.load(checkpoint, weights_only=True)
            assert torch.equal(restored, encoded)
            assert decode_mnemic_address(restored) == address

    malformed = encode_mnemic_address(bytes(16), dtype=torch.float64)
    malformed[0] += 1.0 / 65536.0
    with pytest.raises(QiFieldError, match="uint16 grid"):
        decode_mnemic_address(malformed)
    with pytest.raises(QiFieldError, match="out-of-range"):
        decode_mnemic_address(torch.ones(4, dtype=torch.complex128))
    with pytest.raises(QiFieldError, match="finite"):
        decode_mnemic_address(
            torch.tensor([complex(float("nan"), 0), 0j, 0j, 0j], dtype=torch.complex128)
        )
    negative_zero = torch.complex(
        torch.tensor([-0.0, 0.0, 0.0, 0.0]),
        torch.zeros(4),
    )
    with pytest.raises(QiFieldError, match="negative zero"):
        decode_mnemic_address(negative_zero)
    with pytest.raises(QiFieldError, match="exactly 16 bytes"):
        encode_mnemic_address(bytes(15))


def test_mnemic_thalamus_constraints_settle_and_render_whole_trajectory() -> None:
    _, _, _, _, _, expected, rendered, trace = _settled_symbolic()
    assert trace[-1].status == "settled"
    assert rendered.basin_path == expected
    assert rendered.symbols == ("phase", "gather", "turn")
    assert rendered.text == "phase gather turn"
    assert len(rendered.source_addresses) == 3
    assert len(rendered.field_sha256) == 64


def test_required_conflict_and_address_collision_fail_before_field_mutation() -> None:
    controller, state, basin_ids = _trained()
    values = _trajectory()
    conflict = list(values[0].clone())
    conflict[0] += 1.0
    candidates = (
        _candidate(0x20, 0, values[0]),
        _candidate(0x21, 0, torch.as_tensor(conflict, dtype=torch.complex128)),
        _candidate(0x23, 3, values[3]),
    )
    before = state.field.clone()
    with pytest.raises(QiFieldError, match="contradictory required"):
        start_mnemic_thalamus_thought(
            controller,
            state,
            candidates,
            active_slots=4,
            policy=ThalamusPolicy(eligible_basins=basin_ids),
        )
    assert torch.equal(state.field, before)

    collision = (
        _candidate(0x20, 0, values[0], revision=1),
        _candidate(0x20, 3, values[3], revision=2),
    )
    with pytest.raises(QiFieldError, match="address collision"):
        start_mnemic_thalamus_thought(
            controller,
            state,
            collision,
            active_slots=4,
            policy=ThalamusPolicy(eligible_basins=basin_ids),
        )


def test_thalamus_eligibility_remains_frozen_and_excludes_forbidden_basin() -> None:
    controller, state, basin_ids = _trained()
    values = _trajectory()
    candidates = (_candidate(0x30, 0, values[0]), _candidate(0x33, 3, values[3]))
    active = start_mnemic_thalamus_thought(
        controller,
        state,
        candidates,
        active_slots=4,
        policy=ThalamusPolicy(eligible_basins=(basin_ids[0], basin_ids[2])),
    )
    _, trace = controller.run_until_closed(active)
    assert trace[-1].status == "exhausted"
    assert basin_ids[1] not in trace[-1].winning_basins
    assert all(item.eligible_basin_count_at_breath_start == 2 for item in trace)
    assert all(item.occupied_basin_count == 3 for item in trace)


def test_surface_distinct_successes_share_one_field_basin() -> None:
    controller = BilateralCounterflowController(
        BilateralCounterflowConfig(slot_count=2, max_basins=3)
    )
    state = controller.initial_state(dtype=torch.float64)
    basis = torch.eye(4, dtype=torch.complex128)
    operator = _operators()[0]
    after = torch.einsum("ij,nj->ni", operator, basis)
    receipts = []
    for address in (bytes([0x40]) * 16, bytes([0x41]) * 16, bytes([0x42]) * 16):
        state, receipt = consolidate_equivalent_outcome(
            controller,
            state,
            address,
            basis,
            after,
            successful=True,
        )
        receipts.append(receipt)
    assert [item.decision for item in receipts] == ["create", "reinforce", "reinforce"]
    assert len({item.basin_id for item in receipts}) == 1
    assert torch.count_nonzero(controller._basin_support(controller._packed(state))).item() == 1
    with pytest.raises(QiFieldError, match="failed outcomes"):
        consolidate_equivalent_outcome(
            controller,
            state,
            bytes([0x43]) * 16,
            basis,
            after,
            successful=False,
        )


def test_typed_action_plan_is_inert_authorized_and_contiguous() -> None:
    controller, _, closed, _, basin_ids, expected, _, _ = _settled_symbolic()
    addresses = tuple(bytes([0x50 + index]) * 16 for index in range(4))
    catalog = {
        basin_id: TypedActionDescriptor(
            basin_id=basin_id,
            action_id=f"transform-{edge}",
            kind="field-transform",
            required_authority=0.8,
            reversible=True,
            precondition_address=addresses[edge],
            effect_address=addresses[edge + 1],
        )
        for edge, basin_id in enumerate(expected)
    }
    policy = ThalamusPolicy(
        eligible_basins=basin_ids,
        permitted_action_kinds=("field-transform",),
        authority=1.0,
        authorization_path=("thalamus:reasoning", "owner:execute-separately"),
    )
    proposal = propose_typed_actions(
        controller,
        closed,
        catalog,
        policy=policy,
        start_address=addresses[0],
        goal_address=addresses[-1],
    )
    assert proposal.inert
    assert proposal.basin_path == expected
    assert tuple(item.action_id for item in proposal.actions) == (
        "transform-0",
        "transform-1",
        "transform-2",
    )
    assert proposal.authorization_path == policy.authorization_path

    with pytest.raises(QiFieldError, match="authority is insufficient"):
        propose_typed_actions(
            controller,
            closed,
            catalog,
            policy=ThalamusPolicy(
                eligible_basins=basin_ids,
                permitted_action_kinds=("field-transform",),
                authority=0.5,
                authorization_path=("thalamus:reasoning",),
            ),
            start_address=addresses[0],
            goal_address=addresses[-1],
        )


def test_symbol_rendering_rejects_nonsettled_field() -> None:
    controller, state, _ = _trained()
    with pytest.raises(QiFieldError, match="unique field settlement"):
        render_symbolic_trajectory(controller, state, {0: "unused"})
