from dataclasses import asdict, replace
from itertools import product
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest
import torch

from cassi_bilateral_counterflow import (
    BilateralCounterflowConfig,
    BilateralCounterflowController,
    TransitionPrediction,
)
from cassi_qi_field import QiFieldError, QiFieldState


def test_counterflow_profile_roundtrips_exactly_and_rejects_corruption(tmp_path) -> None:
    controller = BilateralCounterflowController()
    with pytest.raises(QiFieldError, match="plan_beam_width"):
        BilateralCounterflowConfig(plan_beam_width=0)
    with pytest.raises(QiFieldError, match="breath_steps"):
        BilateralCounterflowConfig(breath_steps=2)
    with pytest.raises(QiFieldError, match="stable_plan_steps"):
        BilateralCounterflowConfig(breath_steps=4)
    shortest_breath = BilateralCounterflowController(
        BilateralCounterflowConfig(breath_steps=6)
    )
    assert [shortest_breath._breath_gains(step).phase for step in range(6)] == [
        "expansion",
        "expansion",
        "expansion",
        "contraction",
        "contraction",
        "contraction",
    ]
    state = controller.initial_state(dtype=torch.float64)
    packed = state.field.reshape(7, 9, controller.config.mode_count, 1)
    packed[:, 0, controller.config.up_modes, 0] = 0.25
    packed[:, 2, controller.config.down_modes, 0] = -0.125
    controller.validate_state(state)

    encoded = controller.dump_state_bytes(state)
    restored = controller.load_state_bytes(encoded)
    assert torch.equal(restored.field, state.field)
    assert controller.dump_state_bytes(restored) == encoded
    checkpoint = tmp_path / "counterflow.pt"
    controller.save_state(checkpoint, state)
    assert torch.equal(controller.load_state(checkpoint).field, state.field)
    incompatible = BilateralCounterflowController(BilateralCounterflowConfig(max_basins=4))
    with pytest.raises(QiFieldError, match="configuration"):
        incompatible.load_state_bytes(encoded)


    corrupted = bytearray(encoded)
    corrupted[-1] ^= 1
    with pytest.raises(QiFieldError, match="digest"):
        controller.load_state_bytes(corrupted)


def test_counterflow_profile_has_four_views_and_protects_reserved_cells() -> None:
    config = BilateralCounterflowConfig()
    controller = BilateralCounterflowController(config)
    assert config.metadata_start + controller._active_slots_offset < config.mode_count
    state = controller.initial_state()
    packed = state.field.reshape(7, 9, config.mode_count, 1)

    assert config.up_modes == slice(0, 8)
    assert config.down_modes == slice(8, 16)
    assert packed[:, 0:2, config.up_modes, :].numel() > 0  # Yang-up
    assert packed[:, 2:4, config.up_modes, :].numel() > 0  # Yin-up
    assert packed[:, 0:2, config.down_modes, :].numel() > 0  # Yang-down
    assert packed[:, 2:4, config.down_modes, :].numel() > 0  # Yin-down

    step_mode = config.metadata_start
    packed[0, 8, step_mode, 0] = 0.5
    with pytest.raises(QiFieldError, match="exact integer"):
        controller.validate_state(state)

    packed[0, 8, step_mode, 0] = 0.0
    packed[1, 8, step_mode, 0] = 1.0
    with pytest.raises(QiFieldError, match="non-root metadata"):
        controller.validate_state(state)


def _noncommuting_operators(dtype: torch.dtype = torch.complex128) -> tuple[torch.Tensor, torch.Tensor]:
    a = torch.tensor(
        [
            [0, 0, 0, 1],
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
        ],
        dtype=dtype,
    )
    b = torch.diag(torch.tensor([1, -1, 1j, -1j], dtype=dtype))
    return a, b

def _four_operators(dtype: torch.dtype = torch.complex128) -> tuple[torch.Tensor, ...]:
    a, b = _noncommuting_operators(dtype)
    c = torch.fft.fft(torch.eye(4, dtype=dtype), dim=0, norm="ortho")
    d = 0.5 * torch.tensor(
        [
            [1, 1, 1, 1],
            [1, -1, 1, -1],
            [1, 1, -1, -1],
            [1, -1, -1, 1],
        ],
        dtype=dtype,
    )
    return a, b, c, d


def _train_two_basins(
    controller: BilateralCounterflowController,
    *,
    dtype: torch.dtype = torch.float64,
) -> tuple[QiFieldState, int, int]:
    state = controller.initial_state(dtype=dtype)
    complex_dtype = torch.complex64 if dtype == torch.float32 else torch.complex128
    a, b = _noncommuting_operators(complex_dtype)
    basis = torch.eye(4, dtype=complex_dtype)
    state, first = controller.observe_transitions(
        state, basis, torch.einsum("ij,nj->ni", a, basis)
    )
    state, second = controller.observe_transitions(
        state, basis, torch.einsum("ij,nj->ni", b, basis)
    )
    assert first.decision == "create"
    assert second.decision == "separate"
    assert first.basin_id is not None and second.basin_id is not None
    return state, first.basin_id, second.basin_id

def _train_four_basins(
    controller: BilateralCounterflowController,
    *,
    dtype: torch.dtype = torch.float64,
) -> tuple[QiFieldState, tuple[int, ...]]:
    state = controller.initial_state(dtype=dtype)
    complex_dtype = torch.complex64 if dtype == torch.float32 else torch.complex128
    basis = torch.eye(4, dtype=complex_dtype)
    receipts = []
    for operator in _four_operators(complex_dtype):
        state, receipt = controller.observe_transitions(
            state,
            basis,
            torch.einsum("ij,nj->ni", operator, basis),
        )
        receipts.append(receipt)
    assert [receipt.decision for receipt in receipts] == [
        "create",
        "separate",
        "separate",
        "separate",
    ]
    assert all(receipt.basin_id is not None for receipt in receipts)
    return state, tuple(int(receipt.basin_id) for receipt in receipts)


def test_transition_prediction_receipt_is_public_and_read_only() -> None:
    controller = BilateralCounterflowController()
    current = torch.tensor([1, 0, 0, 0], dtype=torch.complex128)
    empty = controller.initial_state(dtype=torch.float64)
    empty_bytes = controller.dump_state_bytes(empty)

    no_data = controller.predict_transition(empty, current)

    assert isinstance(no_data, TransitionPrediction)
    assert no_data.status == "no_transition_data"
    assert no_data.basin_id is None
    assert no_data.value is None
    assert no_data.score is None
    assert no_data.support == 0
    assert len(no_data.field_sha256) == 64
    assert controller.dump_state_bytes(empty) == empty_bytes

    state, first_basin, _ = _train_two_basins(controller)
    trained_bytes = controller.dump_state_bytes(state)
    predicted = controller.predict_transition(
        state,
        current,
        eligible_basins=[first_basin],
    )

    assert isinstance(predicted, TransitionPrediction)
    assert predicted.status == "predicted"
    assert predicted.basin_id == first_basin
    assert predicted.value is not None and len(predicted.value) == 4
    assert predicted.score is not None
    assert predicted.cycle_residual is not None
    assert predicted.score == pytest.approx(
        predicted.cycle_residual
        + predicted.dispersion / max(1, predicted.support)
    )
    assert predicted.margin is None
    assert len(predicted.field_sha256) == 64
    assert controller.dump_state_bytes(state) == trained_bytes


_VARIABLE_SEQUENCE = (1, 2, 0, 3, 1)
_VARIABLE_START = (0.23 + 0.61j, -0.71 + 0.17j, 0.42 - 0.38j, 0.55 + 0.09j)


def _variable_thought(
    controller: BilateralCounterflowController,
    state: QiFieldState,
) -> tuple[QiFieldState, tuple[torch.Tensor, ...]]:
    complex_dtype = torch.complex64 if state.field.dtype == torch.float32 else torch.complex128
    operators = tuple(operator.to(device=state.field.device) for operator in _four_operators(complex_dtype))
    values = [torch.tensor(_VARIABLE_START, device=state.field.device, dtype=complex_dtype)]
    for index in _VARIABLE_SEQUENCE:
        values.append(operators[index] @ values[-1])
    active = controller.start_thought(
        state,
        values[0],
        values[-1],
        active_slots=6,
        goal_mask=(1.0, 1.0, 1.0, 0.0),
        constraints={
            2: (values[2], (1.0, 0.0, 1.0, 0.0)),
            4: (values[4], (0.0, 1.0, 0.0, 1.0)),
        },
    )
    return active, tuple(values)


def test_directed_matrices_have_opposite_nonwrapping_boundaries() -> None:
    controller = BilateralCounterflowController()
    up, down = controller.directional_matrices()
    assert torch.equal(down, up.T)
    assert torch.equal(
        controller.directional_impulse_trace("up")[-1],
        torch.tensor([0, 0, 0, 0, 0, 0, 1], dtype=torch.float64),
    )
    assert torch.equal(
        controller.directional_impulse_trace("down")[-1],
        torch.tensor([1, 0, 0, 0, 0, 0, 0], dtype=torch.float64),
    )
    assert not torch.count_nonzero(up[0])
    assert not torch.count_nonzero(down[-1])

    ascending = torch.tensor([1, 0, 0, 0, 0, 0, 0], dtype=torch.float64)
    descending = torch.tensor([0, 0, 0, 0, 0, 0, 1], dtype=torch.float64)
    expansion = controller._breath_gains(0)
    assert expansion.phase == "expansion"
    assert expansion.ascending > expansion.descending
    for _ in range(6):
        ascending = expansion.ascending * (up @ ascending)
        descending = expansion.descending * (down @ descending)
    assert ascending[-1] > 100.0 * descending[0]

    ascending = torch.tensor([1, 0, 0, 0, 0, 0, 0], dtype=torch.float64)
    descending = torch.tensor([0, 0, 0, 0, 0, 0, 1], dtype=torch.float64)
    contraction = controller._breath_gains(controller.config.breath_steps // 2)
    assert contraction.phase == "contraction"
    assert contraction.descending > contraction.ascending
    for _ in range(6):
        ascending = contraction.ascending * (up @ ascending)
        descending = contraction.descending * (down @ descending)
    assert descending[0] > 100.0 * ascending[-1]


def test_field_owned_basins_create_reinforce_and_separate_noncommuting_operators() -> None:
    controller = BilateralCounterflowController()
    state, first_id, _ = _train_two_basins(controller)
    a, b = _noncommuting_operators()
    assert not torch.allclose(a @ b, b @ a)
    basis = torch.eye(4, dtype=torch.complex128) * torch.tensor(
        [1, 1j, -1, -1j]
    )
    state, reinforced = controller.observe_transitions(
        state,
        basis,
        torch.einsum("ij,nj->ni", a, basis),
    )
    assert reinforced.decision == "reinforce"
    assert reinforced.basin_id == first_id
    assert reinforced.occupied_before == reinforced.occupied_after == 2
    assert reinforced.support_before == 4
    assert reinforced.support_after == 8
    assert reinforced.dispersion_after >= 0.0
    assert reinforced.field_sha256 == controller._tensor_sha256(state.field)
    restored = controller.load_state_bytes(controller.dump_state_bytes(state))
    assert torch.equal(restored.field, state.field)


def test_breath_relaxes_a_never_stored_ordered_composition() -> None:
    controller = BilateralCounterflowController()
    state, basin_ids = _train_four_basins(controller)
    operators = _four_operators()
    start = torch.tensor(
        [0.23 + 0.61j, -0.71 + 0.17j, 0.42 - 0.38j, 0.55 + 0.09j],
        dtype=torch.complex128,
    )
    sequence = (1, 2, 0)
    goal = start
    for index in sequence:
        goal = operators[index] @ goal
    state = controller.start_thought(state, start, goal)
    packed = controller._packed(state)
    eligible_mode = controller.config.metadata_start + controller._eligible_mask_offset
    assert packed[0, 8, eligible_mode, 0].item() == sum(1 << value for value in basin_ids)

    tampered = QiFieldState(field=state.field.clone())
    first_modes = controller._basin_slice(basin_ids[0])
    controller._packed(tampered)[0, :, first_modes, :] = 0.0
    with pytest.raises(QiFieldError, match="eligible basin set changed"):
        controller.validate_state(tampered)

    state, trace = controller.run_until_closed(state)
    final = trace[-1]
    expected = tuple(basin_ids[index] for index in sequence)

    assert final.status == "settled"
    assert final.winning_basins == expected
    assert final.action_valid
    assert final.constraint_residual <= controller.config.constraint_tolerance
    assert final.trajectory_delta <= controller.config.trajectory_tolerance
    assert final.stable_plan_steps >= controller.config.stable_plan_steps
    assert len(trace) == final.refinement_step == controller.config.breath_steps
    assert tuple(item.phase_step for item in trace) == tuple(range(controller.config.breath_steps))
    assert {item.cycle_index for item in trace} == {0}
    assert all(item.phase == "expansion" for item in trace[: controller.config.breath_steps // 2])
    assert all(item.phase == "contraction" for item in trace[controller.config.breath_steps // 2 :])
    assert all(item.occupied_basin_count == 4 for item in trace)
    assert len({item.basin_region_sha256 for item in trace}) == 1
    assert not any(item.clamp_count for item in trace)
    assert all(item.eligible_basin_count_at_breath_start == 4 for item in trace)
    assert all(item.currently_above_support_floor == 4 for item in trace)
    assert not any(item.support_threshold_crossing_count for item in trace)
    assert all(item.max_amplitude <= controller.config.max_amplitude for item in trace)
    assert all(item.relative_mode_ratio >= 0.0 for item in trace)
    directed = torch.tensor(
        [
            value
            for item in trace
            for value in (
                item.ascending_directed_response,
                item.descending_directed_response,
            )
        ]
    )
    assert torch.isfinite(directed).all().item()
    assert trace[0].trajectory_delta <= 1.0
    assert all(item.winning_basins == expected for item in trace)

    expansion_entropy = [
        item.normalized_candidate_entropy for item in trace if item.phase == "expansion"
    ]
    contraction_entropy = [
        item.normalized_candidate_entropy for item in trace if item.phase == "contraction"
    ]
    assert max(expansion_entropy) > min(contraction_entropy)
    assert final.normalized_candidate_entropy < max(expansion_entropy)


def test_variable_length_partial_constraints_select_a_unique_bounded_plan() -> None:
    controller = BilateralCounterflowController(
        BilateralCounterflowConfig(slot_count=6, plan_beam_width=16)
    )
    idle, basin_ids = _train_four_basins(controller)
    active, values = _variable_thought(controller, idle)
    with pytest.raises(QiFieldError, match="active_slots"):
        controller.start_thought(idle, values[0], values[-1], active_slots=1)
    with pytest.raises(QiFieldError, match="select at least one"):
        controller.start_thought(
            idle,
            values[0],
            values[-1],
            active_slots=6,
            goal_mask=(0.0, 0.0, 0.0, 0.0),
        )
    with pytest.raises(QiFieldError, match="intermediate active-slot"):
        controller.start_thought(
            idle,
            values[0],
            values[-1],
            active_slots=6,
            constraints={5: (values[5], (1.0, 1.0, 1.0, 1.0))},
        )
    expected = tuple(basin_ids[index] for index in _VARIABLE_SEQUENCE)

    altered_goal = values[-1].clone()
    altered_goal[3] += 7.0 + 3.0j
    leakage_control = controller.start_thought(
        idle,
        values[0],
        altered_goal,
        active_slots=6,
        goal_mask=(1.0, 1.0, 1.0, 0.0),
        constraints={
            2: (values[2], (1.0, 0.0, 1.0, 0.0)),
            4: (values[4], (0.0, 1.0, 0.0, 1.0)),
        },
    )
    assert torch.equal(leakage_control.field, active.field)
    stored_constraint, stored_mask = controller._constraint(controller._packed(active))
    assert stored_constraint[-1, 3].item() == 0.0j
    assert torch.equal(
        stored_mask[-1],
        torch.tensor([1.0, 1.0, 1.0, 0.0], dtype=torch.float64),
    )

    closed, trace = controller.run_until_closed(active)
    final = trace[-1]
    assert final.status == "settled"
    assert final.winning_basins == expected
    assert all(item.active_slot_count == 6 for item in trace)
    assert all(
        1 <= item.beam_survivor_count <= controller.config.exact_segment_limit
        for item in trace
    )
    assert all(item.evaluated_plan_extensions < 4**5 for item in trace)
    assert final.evaluated_plan_extensions < 4**5
    assert all(0.0 <= item.beam_plan_entropy <= math.log(16) for item in trace)
    assert all(item.beam_effective_plan_count == pytest.approx(math.exp(item.beam_plan_entropy)) for item in trace)
    assert len({item.basin_region_sha256 for item in trace}) == 1
    assert all(item.eligible_basin_count_at_breath_start == 4 for item in trace)
    assert not any(item.support_threshold_crossing_count for item in trace)
    assert not any(item.clamp_count for item in trace)

    operators = _four_operators()
    masks = {
        2: torch.tensor([True, False, True, False]),
        4: torch.tensor([False, True, False, True]),
        5: torch.tensor([True, True, True, False]),
    }
    matching: list[tuple[int, ...]] = []
    for candidate in product(range(4), repeat=5):
        value = values[0]
        viable = True
        for slot, operator_index in enumerate(candidate, start=1):
            value = operators[operator_index] @ value
            if slot in masks and not torch.allclose(
                value[masks[slot]],
                values[slot][masks[slot]],
                rtol=1.0e-10,
                atol=1.0e-10,
            ):
                viable = False
                break
        if viable:
            matching.append(candidate)
    assert matching == [_VARIABLE_SEQUENCE]

    short = controller.start_thought(
        controller.reset_thought(closed),
        values[0],
        values[3],
        active_slots=4,
    )
    short_closed, short_trace = controller.run_until_closed(short)
    assert short_trace[-1].status == "settled"
    assert short_trace[-1].winning_basins == expected[:3]
    assert short_trace[-1].active_slot_count == 4
    assert short_trace[-1].evaluated_plan_extensions == 84
    packed = controller._packed(short_closed)
    _, _, _, encoded_plan, active_slots = controller._metadata(packed)
    assert active_slots == 4
    assert encoded_plan[3:] == (0, 0)
    inactive_offset = active_slots * controller.config.features_per_species
    for modes in (
        controller.config.up_modes,
        controller.config.down_modes,
        controller.config.constraint_modes,
    ):
        inactive_modes = slice(modes.start + inactive_offset, modes.stop)
        assert torch.count_nonzero(packed[:, :, inactive_modes, :]).item() == 0

    tampered = QiFieldState(field=short_closed.field.clone())
    tampered_packed = controller._packed(tampered)
    inactive_up = slice(
        controller.config.up_modes.start + inactive_offset,
        controller.config.up_modes.stop,
    )
    tampered_packed[0, 0, inactive_up.start, 0] = 1.0
    with pytest.raises(QiFieldError, match="inactive ascending trajectory"):
        controller.validate_state(tampered)


def test_state_owns_learning_and_outcome_consolidates_only_after_closure() -> None:
    controller = BilateralCounterflowController()
    state, _, _ = _train_two_basins(controller)
    assert set(controller.__dict__) == {"config"}

    a, b = _noncommuting_operators()
    basis = torch.eye(4, dtype=torch.complex128)
    oversized = 17.0 * basis
    with pytest.raises(QiFieldError, match="max_amplitude"):
        controller.observe_transitions(state, oversized, oversized)

    start = torch.tensor(
        [0.7 + 0.1j, -0.2 + 0.4j, 0.3 - 0.5j, 0.6 + 0.2j],
        dtype=torch.complex128,
    )
    active = controller.start_thought(state, start, a @ (b @ (a @ start)))
    with pytest.raises(QiFieldError, match="no thought is active"):
        controller.observe_transitions(active, basis, basis)
    with pytest.raises(QiFieldError, match="only after a thought closes"):
        controller.consolidate_outcome(active, basis, basis)

    closed, trace = controller.run_until_closed(active)
    memory_before = trace[-1].basin_region_sha256
    third = torch.fft.fft(torch.eye(4, dtype=torch.complex128), dim=0, norm="ortho")
    consolidated, receipt = controller.consolidate_outcome(
        closed,
        basis,
        torch.einsum("ij,nj->ni", third, basis),
    )
    packed = controller._packed(consolidated)
    _, status, _, _, _ = controller._metadata(packed)
    assert receipt.decision == "separate"
    assert receipt.occupied_before == 2
    assert receipt.occupied_after == 3
    assert status == controller._IDLE
    assert controller._basin_region_sha256(packed) != memory_before
    assert set(controller.__dict__) == {"config"}


def test_noncommuting_order_is_distinguished_by_global_completion() -> None:
    controller = BilateralCounterflowController()
    state, first_id, second_id = _train_two_basins(controller)
    a, b = _noncommuting_operators()
    start = torch.tensor(
        [
            0.11234131329155948 + 0.12566674214019047j,
            -0.9723807125794848 - 0.2334004066050727j,
            -0.23286109843543615 - 0.37480824580844596j,
            0.48637222340392855 + 0.18060123598308872j,
        ],
        dtype=torch.complex128,
    )
    assert not torch.allclose(a @ b, b @ a)

    goal_aab = b @ (a @ (a @ start))
    _, trace_aab = controller.run_until_closed(
        controller.start_thought(state, start, goal_aab)
    )
    expected_aab = (first_id, first_id, second_id)
    assert trace_aab[-1].status == "settled"
    assert trace_aab[-1].winning_basins == expected_aab
    assert all(item.winning_basins == expected_aab for item in trace_aab)

    goal_baa = a @ (a @ (b @ start))
    _, trace_baa = controller.run_until_closed(
        controller.start_thought(state, start, goal_baa)
    )
    expected_baa = (second_id, first_id, first_id)
    assert not torch.allclose(goal_aab, goal_baa)
    assert trace_baa[-1].status == "settled"
    assert trace_baa[-1].winning_basins == expected_baa
    assert expected_aab != expected_baa


@pytest.mark.parametrize("completed_steps", (3, 10))
def test_cpu_variable_thought_restart_replays_the_next_step_exactly(
    completed_steps: int,
    tmp_path,
) -> None:
    config = BilateralCounterflowConfig(slot_count=6, plan_beam_width=16)
    controller = BilateralCounterflowController(config)
    idle, _ = _train_four_basins(controller)
    state, _ = _variable_thought(controller, idle)
    for _ in range(completed_steps):
        state = controller.refine_once(state).state
    before_refinement = controller._packed(state).clone()
    step_before = controller._metadata(before_refinement)[0]

    encoded = controller.dump_state_bytes(state)
    uninterrupted = controller.refine_once(state)
    after_refinement = controller._packed(uninterrupted.state)
    assert controller._metadata(after_refinement)[0] == step_before + 1
    assert uninterrupted.telemetry.active_slot_count == 6
    assert 0 < uninterrupted.telemetry.evaluated_plan_extensions < 4**5
    assert torch.equal(
        after_refinement[:, :, controller.config.constraint_modes, :],
        before_refinement[:, :, controller.config.constraint_modes, :],
    )
    assert torch.equal(
        after_refinement[:, :, controller.config.basin_start : controller.config.basin_end, :],
        before_refinement[:, :, controller.config.basin_start : controller.config.basin_end, :],
    )
    resumed_controller = BilateralCounterflowController(config)
    resumed = resumed_controller.refine_once(
        resumed_controller.load_state_bytes(encoded)
    )
    assert torch.equal(resumed.state.field, uninterrupted.state.field)
    assert resumed.telemetry == uninterrupted.telemetry
    assert resumed_controller.dump_state_bytes(resumed.state) == controller.dump_state_bytes(
        uninterrupted.state
    )

    input_path = tmp_path / f"counterflow-variable-step-{completed_steps}.pt"
    output_path = tmp_path / f"counterflow-variable-next-{completed_steps}.pt"
    controller.save_state(input_path, state)
    worker = """
from dataclasses import asdict
import json
import sys
from cassi_bilateral_counterflow import (
    BilateralCounterflowConfig,
    BilateralCounterflowController,
)

controller = BilateralCounterflowController(
    BilateralCounterflowConfig(slot_count=6, plan_beam_width=16)
)
step = controller.refine_once(controller.load_state(sys.argv[1]))
controller.save_state(sys.argv[2], step.state)
print(json.dumps(asdict(step.telemetry), sort_keys=True, separators=(",", ":")))
"""
    completed = subprocess.run(
        [sys.executable, "-c", worker, str(input_path), str(output_path)],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    process_state = controller.load_state(output_path)
    expected_telemetry = json.dumps(
        asdict(uninterrupted.telemetry),
        sort_keys=True,
        separators=(",", ":"),
    )
    assert torch.equal(process_state.field, uninterrupted.state.field)
    assert completed.stdout.strip() == expected_telemetry


def test_clearing_a_required_basin_selectively_breaks_its_composition() -> None:
    controller = BilateralCounterflowController()
    state, first_id, second_id = _train_two_basins(controller)
    a, b = _noncommuting_operators()
    start = torch.tensor(
        [0.7 + 0.1j, -0.2 + 0.4j, 0.3 - 0.5j, 0.6 + 0.2j],
        dtype=torch.complex128,
    )
    goal = a @ (b @ (a @ start))
    expected = (first_id, second_id, first_id)
    _, intact_trace = controller.run_until_closed(
        controller.start_thought(state, start, goal)
    )
    assert intact_trace[-1].status == "settled"
    assert intact_trace[-1].winning_basins == expected

    active = controller.start_thought(state, start, goal)
    with pytest.raises(QiFieldError, match="no thought is active"):
        controller.clear_basin(active, first_id)
    reduced = controller.clear_basin(state, first_id)
    with pytest.raises(QiFieldError, match="unoccupied"):
        controller.clear_basin(reduced, first_id)
    _, ablated_trace = controller.run_until_closed(
        controller.start_thought(reduced, start, goal)
    )
    final = ablated_trace[-1]
    assert final.status == "exhausted"
    assert final.occupied_basin_count == 1
    assert final.winning_basins == (second_id, second_id, second_id)
    assert final.winning_basins != expected


def test_grounded_relational_composition_transfers_to_renamed_holdout() -> None:
    from run_bilateral_counterflow_scenario import (
        run_grounded_relational_transfer,
    )

    result = run_grounded_relational_transfer()

    assert result["result"] == "GROUNDED_RELATIONAL_COMPOSITION_OK"
    assert result["status"] == "settled"
    assert result["settled_actions"] == [
        "action.gaze-right",
        "action.gaze-up",
        "action.gaze-right",
    ]
    assert result["holdout_pose_seen_in_training"] is False
    assert set(result["source_execution_action_counts"]) == {1}
    assert result["complete_trajectory_observed"] is False
    assert result["action_labels_in_field_features"] is False
    assert result["exact_goal_reached"] is True
    assert result["field_memory_frozen"] is True
    assert result["checkpoint_restart_exact"] is True
    assert result["ablation_status"] == "exhausted"
    assert result["live_provider_descriptor_law"] == "unchanged_exact_address_only"


def test_beam_bound_and_matched_capacity_controls_isolate_counterflow_advantage() -> None:
    modes = (
        "counterflow",
        "uncoupled",
        "swapped",
        "same_up",
        "same_down",
        "single_stream",
        "constant",
        "reversed",
        "fixed_phase",
    )
    results = {}
    shapes = set()

    for mode in modes:
        controller = BilateralCounterflowController(
            BilateralCounterflowConfig(
                slot_count=6,
                plan_beam_width=16,
                ablation=mode,
            )
        )
        state, basin_ids = _train_four_basins(controller)
        shapes.add(tuple(state.field.shape))
        active, _ = _variable_thought(controller, state)
        _, trace = controller.run_until_closed(active)
        assert all(item.occupied_basin_count == 4 for item in trace)
        assert not any(item.clamp_count for item in trace)
        expected = tuple(basin_ids[index] for index in _VARIABLE_SEQUENCE)
        results[mode] = (trace[-1], expected)

    narrow = BilateralCounterflowController(
        BilateralCounterflowConfig(slot_count=6, plan_beam_width=1)
    )
    narrow_state, narrow_ids = _train_four_basins(narrow)
    shapes.add(tuple(narrow_state.field.shape))
    narrow_active, _ = _variable_thought(narrow, narrow_state)
    _, narrow_trace = narrow.run_until_closed(narrow_active)
    narrow_final = narrow_trace[-1]
    narrow_expected = tuple(narrow_ids[index] for index in _VARIABLE_SEQUENCE)

    assert len(shapes) == 1
    counterflow, expected = results["counterflow"]
    assert counterflow.status == "settled"
    assert counterflow.winning_basins == expected == narrow_expected
    assert counterflow.beam_survivor_count == 8
    assert counterflow.evaluated_plan_extensions == 348 < 4**5
    assert narrow_final.status == "settled"
    assert narrow_final.winning_basins == narrow_expected
    assert narrow_final.beam_survivor_count == 1
    assert narrow_final.evaluated_plan_extensions == 44
    assert results["uncoupled"][0].status == "settled"
    assert results["same_down"][0].status == "settled"
    assert counterflow.energy < results["uncoupled"][0].energy
    assert counterflow.energy < results["same_down"][0].energy
    for mode in (
        "swapped",
        "same_up",
        "single_stream",
        "constant",
        "reversed",
        "fixed_phase",
    ):
        assert results[mode][0].status == "exhausted"
    assert results["fixed_phase"][0].winning_basins != expected


@pytest.mark.skipif(not torch.cuda.is_available(), reason="requires the ROCm CUDA surface")
def test_gpu_variable_refinement_matches_cpu_discrete_state_with_numeric_tolerance() -> None:
    controller = BilateralCounterflowController(
        BilateralCounterflowConfig(slot_count=6, plan_beam_width=16)
    )
    state, basin_ids = _train_four_basins(controller, dtype=torch.float32)
    active, _ = _variable_thought(controller, state)
    expected = tuple(basin_ids[index] for index in _VARIABLE_SEQUENCE)
    encoded = controller.dump_state_bytes(active)
    cpu_state = active
    gpu_state = controller.load_state_bytes(encoded, device="cuda")
    gpu_replay = controller.load_state_bytes(encoded, device="cuda")

    for _ in range(controller.config.breath_steps):
        cpu_step = controller.refine_once(cpu_state)
        gpu_step = controller.refine_once(gpu_state)
        replay_step = controller.refine_once(gpu_replay)
        assert gpu_step.telemetry.refinement_step == cpu_step.telemetry.refinement_step
        assert gpu_step.telemetry.status == cpu_step.telemetry.status
        assert gpu_step.telemetry.winning_basins == cpu_step.telemetry.winning_basins
        assert gpu_step.telemetry.phase == cpu_step.telemetry.phase
        assert gpu_step.telemetry.phase_step == cpu_step.telemetry.phase_step
        assert gpu_step.telemetry.cycle_index == cpu_step.telemetry.cycle_index
        assert gpu_step.telemetry.active_slot_count == cpu_step.telemetry.active_slot_count == 6
        assert (
            gpu_step.telemetry.eligible_basin_count_at_breath_start
            == cpu_step.telemetry.eligible_basin_count_at_breath_start
        )
        assert (
            gpu_step.telemetry.beam_survivor_count
            == cpu_step.telemetry.beam_survivor_count
        )
        assert (
            gpu_step.telemetry.evaluated_plan_extensions
            == cpu_step.telemetry.evaluated_plan_extensions
            < 4**5
        )
        assert gpu_step.telemetry.action_valid == cpu_step.telemetry.action_valid
        assert gpu_step.telemetry.energy == pytest.approx(
            cpu_step.telemetry.energy,
            rel=3.0e-3,
            abs=3.0e-5,
        )
        assert gpu_step.telemetry.constraint_residual == pytest.approx(
            cpu_step.telemetry.constraint_residual,
            rel=3.0e-3,
            abs=3.0e-5,
        )
        assert gpu_step.telemetry.candidate_entropy == pytest.approx(
            cpu_step.telemetry.candidate_entropy,
            rel=3.0e-3,
            abs=3.0e-5,
        )
        assert gpu_step.telemetry.beam_plan_entropy == pytest.approx(
            cpu_step.telemetry.beam_plan_entropy,
            rel=3.0e-3,
            abs=3.0e-5,
        )
        assert gpu_step.telemetry.basin_margins == pytest.approx(
            cpu_step.telemetry.basin_margins,
            rel=3.0e-3,
            abs=3.0e-5,
        )
        assert replay_step.telemetry.winning_basins == gpu_step.telemetry.winning_basins
        cpu_state = cpu_step.state
        gpu_state = gpu_step.state
        gpu_replay = replay_step.state

    torch.cuda.synchronize()
    _, cpu_status, _, cpu_plan, _ = controller._metadata(controller._packed(cpu_state))
    _, gpu_status, _, gpu_plan, _ = controller._metadata(controller._packed(gpu_state))
    assert cpu_status == gpu_status == controller._SETTLED
    assert tuple(value - 1 for value in cpu_plan[:5]) == expected
    assert tuple(value - 1 for value in gpu_plan[:5]) == expected
    assert gpu_state.field.device.type == "cuda"
    assert torch.isfinite(gpu_state.field).all().item()
    torch.testing.assert_close(
        gpu_state.field.cpu(),
        cpu_state.field,
        rtol=3.0e-4,
        atol=3.0e-5,
    )
    torch.testing.assert_close(
        gpu_replay.field,
        gpu_state.field,
        rtol=3.0e-4,
        atol=3.0e-5,
    )


def _train_operator_family(
    controller: BilateralCounterflowController,
    operators: tuple[torch.Tensor, ...],
) -> tuple[QiFieldState, tuple[int, ...]]:
    state = controller.initial_state(dtype=torch.float64)
    basis = torch.eye(4, dtype=torch.complex128)
    basin_ids: list[int] = []
    for operator in operators:
        state, receipt = controller.observe_transitions(
            state,
            basis,
            torch.einsum("ij,nj->ni", operator, basis),
        )
        assert receipt.basin_id is not None
        basin_ids.append(receipt.basin_id)
    return state, tuple(basin_ids)


@pytest.mark.parametrize("active_slots", range(2, 9))
def test_endpoint_only_completion_covers_active_lengths_two_through_eight(
    active_slots: int,
) -> None:
    base = _four_operators()
    operators = tuple(
        scale * operator
        for scale, operator in zip((0.91, 0.97, 0.89, 1.03), base, strict=True)
    )
    controller = BilateralCounterflowController(
        BilateralCounterflowConfig(
            slot_count=8,
            plan_beam_width=16,
            breath_steps={6: 24, 7: 24, 8: 40}.get(active_slots, 16),
        )
    )
    state, basin_ids = _train_operator_family(controller, operators)
    phase = active_slots - 1
    start = torch.tensor(
        [
            0.19 + (0.31 + 0.01 * phase) * 1j,
            -0.47 + (0.11 - 0.01 * phase) * 1j,
            0.36 - (0.29 + 0.005 * phase) * 1j,
            0.58 + (0.07 + 0.003 * phase) * 1j,
        ],
        dtype=torch.complex128,
    )
    sequence = (1, 2, 0, 3, 1, 0, 2)[: active_slots - 1]
    goal = start
    for operator_id in sequence:
        goal = operators[operator_id] @ goal
    _, trace = controller.run_until_closed(
        controller.start_thought(state, start, goal, active_slots=active_slots)
    )
    final = trace[-1]
    assert final.status == "settled"
    assert final.winning_basins == tuple(basin_ids[index] for index in sequence)
    assert final.action_valid
    assert final.constraint_residual <= controller.config.constraint_tolerance
    assert final.evaluated_plan_extensions <= sum(
        len(operators) ** edge for edge in range(1, active_slots)
    )


def test_held_out_starts_and_distinct_operator_families_preserve_order() -> None:
    a, b, c, conjugator = _four_operators()
    conjugated = tuple(
        conjugator @ operator @ conjugator.conj().T
        for operator in (a, b, c)
    )
    families = (
        (a, b, c),
        (0.92 * a, 1.01 * b, 0.88 * c),
        conjugated,
    )
    starts = (
        torch.tensor([0.31 + 0.12j, -0.28 + 0.44j, 0.57 - 0.08j, -0.19 - 0.33j]),
        torch.tensor([-0.17 + 0.51j, 0.62 - 0.13j, -0.39 + 0.27j, 0.22 + 0.18j]),
        torch.tensor([0.46 - 0.09j, 0.14 + 0.37j, -0.53 + 0.21j, 0.29 - 0.41j]),
    )
    sequence = (2, 0, 1)
    for operators, start in zip(families, starts, strict=True):
        controller = BilateralCounterflowController(
            BilateralCounterflowConfig(slot_count=4, max_basins=5)
        )
        state, basin_ids = _train_operator_family(controller, operators)
        value = start.to(dtype=torch.complex128)
        for operator_id in sequence:
            value = operators[operator_id] @ value
        _, trace = controller.run_until_closed(
            controller.start_thought(state, start, value, active_slots=4)
        )
        assert trace[-1].status == "settled"
        assert trace[-1].winning_basins == tuple(basin_ids[index] for index in sequence)


def test_noisy_partial_constraints_retain_the_unique_plan() -> None:
    controller = BilateralCounterflowController(
        BilateralCounterflowConfig(slot_count=6, plan_beam_width=16)
    )
    state, basin_ids = _train_four_basins(controller)
    _, values = _variable_thought(controller, state)
    noise = torch.tensor(
        [0.008 + 0.004j, -0.006 + 0.003j, 0.007 - 0.005j, -0.004 - 0.006j],
        dtype=torch.complex128,
    )
    active = controller.start_thought(
        state,
        values[0],
        values[-1] + noise,
        active_slots=6,
        goal_mask=(1.0, 1.0, 1.0, 0.0),
        constraints={
            2: (values[2] + noise, (1.0, 0.0, 1.0, 0.0)),
            4: (values[4] - noise, (0.0, 1.0, 0.0, 1.0)),
        },
    )
    _, trace = controller.run_until_closed(active)
    final = trace[-1]
    assert final.status == "settled"
    assert final.winning_basins == tuple(
        basin_ids[index] for index in _VARIABLE_SEQUENCE
    )
    assert final.best_plan_residual <= controller.config.constraint_tolerance * 3


def test_ambiguous_valid_plans_abstain_while_null_goal_exhausts() -> None:
    controller = BilateralCounterflowController(
        BilateralCounterflowConfig(slot_count=2, max_basins=2)
    )
    identity = torch.eye(4, dtype=torch.complex128)
    flip = torch.diag(torch.tensor([1, -1, 1, -1], dtype=torch.complex128))
    state, _ = _train_operator_family(controller, (identity, flip))
    start = torch.tensor([0.4 + 0.2j, 0.0j, 0.6 - 0.1j, 0.0j], dtype=torch.complex128)
    ambiguous_state, ambiguous_trace = controller.run_until_closed(
        controller.start_thought(
            state,
            start,
            start,
            active_slots=2,
            goal_mask=(1.0, 0.0, 1.0, 0.0),
        )
    )
    ambiguous = ambiguous_trace[-1]
    assert ambiguous.status == "ambiguous"
    assert ambiguous.valid_plan_count == 2
    assert ambiguous.terminal_plan_margin <= controller.config.score_tie_tolerance
    assert not ambiguous.action_valid

    impossible = torch.tensor(
        [3.0 + 2.0j, -2.0 + 1.0j, 1.0 - 4.0j, 2.0 + 3.0j],
        dtype=torch.complex128,
    )
    _, null_trace = controller.run_until_closed(
        controller.start_thought(
            controller.reset_thought(ambiguous_state),
            start,
            impossible,
            active_slots=2,
        )
    )
    null = null_trace[-1]
    assert null.status == "exhausted"
    assert null.valid_plan_count == 0
    assert not null.action_valid


def test_rank_deficient_noninvertible_basin_keeps_forward_plan_and_cycle_uncertainty() -> None:
    controller = BilateralCounterflowController(
        BilateralCounterflowConfig(slot_count=2, max_basins=3)
    )
    identity = torch.eye(4, dtype=torch.complex128)
    projection = torch.diag(torch.tensor([1, 1, 0, 0], dtype=torch.complex128))
    flip = torch.diag(torch.tensor([1, -1, 1, -1], dtype=torch.complex128))
    state, basin_ids = _train_operator_family(controller, (projection, flip))
    state, reinforcement = controller.observe_transitions(
        state,
        identity[:2],
        torch.einsum("ij,nj->ni", projection, identity[:2]),
    )
    assert reinforcement.decision == "reinforce"
    start = torch.tensor(
        [0.2 + 0.1j, -0.3 + 0.2j, 0.8 - 0.2j, -0.4 + 0.5j],
        dtype=torch.complex128,
    )
    _, trace = controller.run_until_closed(
        controller.start_thought(state, start, projection @ start, active_slots=2)
    )
    final = trace[-1]
    assert final.status == "settled"
    assert final.winning_basins == (basin_ids[0],)
    assert final.action_residuals[0] <= controller.config.action_residual_tolerance
    assert final.cycle_residuals[0] > 0.5
    forward, backward, occupied = controller._operators(controller._packed(state))
    flip_position = occupied.index(basin_ids[1])
    flip_cycle = backward[flip_position] @ (forward[flip_position] @ start)
    flip_cycle_residual = controller._masked_residual(
        flip_cycle,
        start,
        torch.ones_like(start.real),
    )
    assert flip_cycle_residual.item() < 0.01


def test_backward_suffix_truncation_bounds_candidate_set_deterministically() -> None:
    base_config = BilateralCounterflowConfig(
        slot_count=6,
        plan_beam_width=1,
        initial_plan_beam_width=1,
        exact_segment_limit=1,
        bidirectional_lookahead_limit=4096,
    )
    full_lookahead = BilateralCounterflowController(base_config)
    truncated_lookahead = BilateralCounterflowController(
        replace(base_config, bidirectional_lookahead_limit=1)
    )
    full_state, full_ids = _train_four_basins(full_lookahead)
    truncated_state, truncated_ids = _train_four_basins(truncated_lookahead)
    _, full_values = _variable_thought(full_lookahead, full_state)
    _, truncated_values = _variable_thought(truncated_lookahead, truncated_state)
    _, full_backward, full_occupied = full_lookahead._operators(
        full_lookahead._packed(full_state)
    )
    _, truncated_backward, truncated_occupied = truncated_lookahead._operators(
        truncated_lookahead._packed(truncated_state)
    )
    suffix_count = len(full_ids) ** 4
    full_suffixes = full_lookahead._backward_anchor_states(
        full_values[-1], full_backward, 4
    )
    truncated_suffixes = truncated_lookahead._backward_anchor_states(
        truncated_values[-1], truncated_backward, 4
    )
    assert full_occupied == truncated_occupied
    assert torch.equal(full_backward, truncated_backward)
    assert full_suffixes.shape == (suffix_count, base_config.latent_dim)
    assert truncated_suffixes.shape == (1, base_config.latent_dim)
    assert torch.equal(truncated_suffixes, full_suffixes[:1])
    full_active = full_lookahead.start_thought(
        full_state,
        full_values[0],
        full_values[-1],
        active_slots=6,
        constraints={
            2: (full_values[2], (1.0, 0.0, 1.0, 0.0)),
            4: (full_values[4], (0.0, 1.0, 0.0, 1.0)),
        },
    )
    truncated_active = truncated_lookahead.start_thought(
        truncated_state,
        truncated_values[0],
        truncated_values[-1],
        active_slots=6,
        constraints={
            2: (truncated_values[2], (1.0, 0.0, 1.0, 0.0)),
            4: (truncated_values[4], (0.0, 1.0, 0.0, 1.0)),
        },
    )
    _, full_trace = full_lookahead.run_until_closed(full_active)
    _, truncated_trace = truncated_lookahead.run_until_closed(truncated_active)
    expected = tuple(full_ids[index] for index in _VARIABLE_SEQUENCE)
    assert expected == tuple(truncated_ids[index] for index in _VARIABLE_SEQUENCE)
    assert full_lookahead.config.bidirectional_lookahead_limit >= suffix_count
    assert truncated_lookahead.config.bidirectional_lookahead_limit < suffix_count
    assert full_trace[-1].status == "settled"
    assert full_trace[-1].winning_basins == expected
    assert full_trace[-1].search_mode == "bidirectional"
    assert truncated_trace[-1].search_mode == "bidirectional"


def test_adaptive_beam_matches_fixed_max_plan_with_fewer_terminal_extensions() -> None:
    adaptive = BilateralCounterflowController(
        BilateralCounterflowConfig(slot_count=6, plan_beam_width=16)
    )
    fixed_max = BilateralCounterflowController(
        BilateralCounterflowConfig(
            slot_count=6,
            plan_beam_width=16,
            initial_plan_beam_width=16,
        )
    )
    adaptive_state, adaptive_ids = _train_four_basins(adaptive)
    fixed_state, fixed_ids = _train_four_basins(fixed_max)
    adaptive_active, _ = _variable_thought(adaptive, adaptive_state)
    fixed_active, _ = _variable_thought(fixed_max, fixed_state)
    _, adaptive_trace = adaptive.run_until_closed(adaptive_active)
    _, fixed_trace = fixed_max.run_until_closed(fixed_active)
    adaptive_final = adaptive_trace[-1]
    fixed_final = fixed_trace[-1]
    expected = tuple(adaptive_ids[index] for index in _VARIABLE_SEQUENCE)
    assert expected == tuple(fixed_ids[index] for index in _VARIABLE_SEQUENCE)
    assert adaptive_final.status == fixed_final.status == "settled"
    assert adaptive_final.winning_basins == fixed_final.winning_basins == expected
    assert adaptive_final.evaluated_plan_extensions < fixed_final.evaluated_plan_extensions
    assert adaptive_final.constraint_residual == pytest.approx(
        fixed_final.constraint_residual,
        abs=0.01,
    )


def test_settled_plan_consolidates_as_restart_stable_macro_and_invalidates_transitively() -> None:
    controller = BilateralCounterflowController(
        BilateralCounterflowConfig(slot_count=6, plan_beam_width=16)
    )
    state, basin_ids = _train_four_basins(controller)
    active, values = _variable_thought(controller, state)
    closed, trace = controller.run_until_closed(active)
    assert trace[-1].status == "settled"
    macro_state, created = controller.consolidate_plan(closed)
    assert created.decision == "create"
    assert created.basin_id is not None
    assert created.constituents == tuple(
        basin_ids[index] for index in _VARIABLE_SEQUENCE
    )

    restricted, _ = controller.run_until_closed(
        controller.start_thought(
            macro_state,
            values[0],
            values[-1],
            active_slots=6,
            goal_mask=(1.0, 1.0, 1.0, 0.0),
            constraints={
                2: (values[2], (1.0, 0.0, 1.0, 0.0)),
                4: (values[4], (0.0, 1.0, 0.0, 1.0)),
            },
            eligible_basins=basin_ids,
        )
    )
    reinforced_state, reinforced = controller.consolidate_plan(restricted)
    assert reinforced.decision == "reinforce"
    assert reinforced.basin_id == created.basin_id
    assert reinforced.support_after == created.support_after + 1

    restored = controller.load_state_bytes(controller.dump_state_bytes(reinforced_state))
    assert torch.equal(restored.field, reinforced_state.field)
    direct_closed, direct_trace = controller.run_until_closed(
        controller.start_thought(
            restored,
            values[0],
            values[-1],
            active_slots=2,
            goal_mask=(1.0, 1.0, 1.0, 0.0),
            eligible_basins=(created.basin_id,),
        )
    )
    assert direct_trace[-1].status == "settled"
    assert direct_trace[-1].winning_basins == (created.basin_id,)

    invalidated = controller.clear_basin(
        controller.reset_thought(direct_closed),
        basin_ids[1],
    )
    support = controller._basin_support(controller._packed(invalidated))
    assert support[basin_ids[1]].item() == 0.0
    assert support[created.basin_id].item() == 0.0
