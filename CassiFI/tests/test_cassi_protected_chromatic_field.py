"""Focused CPU contracts for the frozen L33 protected chromatic memory."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_cyclic_chromatic_field import CyclicChromaticFieldConfig
from cassi_protected_chromatic_field import (
    PROTECTED_CHROMATIC_LAYOUT_PROFILE_ID,
    PROTECTED_CHROMATIC_OPERATOR_PROFILE_ID,
    PROTECTED_CHROMATIC_PROJECTION_PROFILE_ID,
    ProtectedChromaticFieldConfig,
    ProtectedChromaticFieldController,
)
from cassi_qi_field import QiFieldState

CHANNELS = 7
MODE_COUNT = 520


def controller() -> ProtectedChromaticFieldController:
    return ProtectedChromaticFieldController(
        ProtectedChromaticFieldConfig(mode_count=MODE_COUNT)
    )


def two_symbol_state(
    field: ProtectedChromaticFieldController,
) -> tuple[torch.Tensor, torch.Tensor, QiFieldState]:
    carrier, _ = field.heartbeat(field.new_state(dtype=torch.float64))
    target_state, target_drift = field.modulate_symbols(carrier, (37,), trust=1.0)
    target_lane = field._active_coordinates(target_state)[1].clone()
    carrier, _ = field.heartbeat(target_state)
    state, distractor_drift = field.modulate_symbols(carrier, (134,), trust=1.0)
    assert abs(target_drift.item()) <= 1e-12
    assert abs(distractor_drift.item()) <= 1e-12
    return target_lane, field.effective_differential(state), state



def rank(scores: torch.Tensor, symbol: int) -> int:
    candidate = scores[0, symbol]
    ids = torch.arange(scores.shape[1], device=scores.device)
    return int(
        1
        + (scores[0] > candidate).sum().item()
        + ((scores[0] == candidate) & (ids < symbol)).sum().item()
    )



def test_zero_trust_is_identity_for_protected_lane_rotation() -> None:
    field = controller()
    carrier, _ = field.heartbeat(field.new_state(dtype=torch.float64))
    state, _ = field.modulate_symbols(carrier, (37,), trust=1.0)
    before = state.field.clone()

    result, drift = field.modulate_symbols(state, (134,), trust=0.0)

    assert torch.equal(result.field, before)
    assert drift.item() == 0.0


@pytest.mark.xfail(
    strict=True,
    reason="L33 mechanical FAIL: paired velocity deposit erases the retained lane",
)
def test_full_trust_retains_first_symbol_through_second_deposit() -> None:
    field = controller()
    target_lane, effective, state = two_symbol_state(field)
    _, current_lane, _, memory_lane = field._active_coordinates(state)
    readout = field.white_readout(state)

    assert torch.allclose(memory_lane, -target_lane, atol=1e-12, rtol=1e-12)
    assert torch.allclose(effective, current_lane - 0.5 * memory_lane, atol=1e-12)
    assert readout.symbols.item() == 134
    assert rank(readout.scores, 37) <= 2


def test_low_energy_protected_lanes_survive_blank_evolution() -> None:
    field = controller()
    state = field.new_state(dtype=torch.float64)
    common, current_lane, common_velocity, memory_lane = (
        field._active_coordinates(state)
    )
    current_lane = torch.full_like(current_lane, 0.01 + 0.02j)
    memory_lane = torch.full_like(memory_lane, -0.02 + 0.01j)
    state = field._replace_coordinates(
        state, common, current_lane, common_velocity, memory_lane
    )

    evolved = field.evolve(state, steps=512)
    _, current_after, _, memory_after = field._active_coordinates(evolved)

    assert torch.equal(current_after, current_lane)
    assert torch.equal(memory_after, memory_lane)
    assert field.dynamic_energy(evolved).item() <= 1.05
    assert torch.isfinite(evolved.field).all()


def test_l33_profile_is_incompatible_without_parallel_state() -> None:
    config = ProtectedChromaticFieldConfig(mode_count=MODE_COUNT)
    field = ProtectedChromaticFieldController(config)

    assert (
        PROTECTED_CHROMATIC_LAYOUT_PROFILE_ID
        == "cassi.qi-protected-chromatic-memory-lane.v1"
    )
    assert (
        PROTECTED_CHROMATIC_OPERATOR_PROFILE_ID
        == "cassi.qi-protected-chromatic-heartbeat.v1"
    )
    assert (
        PROTECTED_CHROMATIC_PROJECTION_PROFILE_ID
        == "cassi.qi-cyclic-chromatic-projection.v1"
    )
    assert config.fingerprint != CyclicChromaticFieldConfig(
        mode_count=MODE_COUNT
    ).fingerprint
    assert field.new_state(batch_size=3).field.shape == (CHANNELS, 9 * MODE_COUNT, 3)
    for name in ("model", "optimizer", "memory_table", "history", "cache"):
        assert not hasattr(field, name)
