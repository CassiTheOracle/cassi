"""Focused CPU contracts for the frozen L34 exact cyclic dynamics."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_cyclic_chromatic_field import (
    CyclicChromaticFieldConfig,
    CyclicChromaticFieldController,
)
from cassi_exact_cyclic_field import (
    EXACT_CYCLIC_LAYOUT_PROFILE_ID,
    EXACT_CYCLIC_OPERATOR_PROFILE_ID,
    EXACT_CYCLIC_PROJECTION_PROFILE_ID,
    ExactCyclicFieldConfig,
    ExactCyclicFieldController,
)

CHANNELS = 7
MODE_COUNT = 520
WIDTH = MODE_COUNT // 2


def controllers() -> tuple[
    CyclicChromaticFieldController, ExactCyclicFieldController
]:
    return (
        CyclicChromaticFieldController(
            CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
        ExactCyclicFieldController(ExactCyclicFieldConfig(mode_count=MODE_COUNT)),
    )


def packed(state: object) -> torch.Tensor:
    field = getattr(state, "field")
    return field.reshape(CHANNELS, 9, MODE_COUNT, field.shape[2])


def test_exact_linear_step_matches_closed_form_for_one_channel_harmonic() -> None:
    field = controllers()[1]
    state = field.new_state(dtype=torch.float64)
    exact = field._exact_constants(state)
    harmonic = 2
    channel = torch.arange(CHANNELS, dtype=torch.float64).reshape(CHANNELS, 1, 1)
    channel_phase = torch.exp(2j * math.pi * harmonic * channel / CHANNELS)
    mode = torch.linspace(0.1, 0.9, WIDTH, dtype=torch.float64).reshape(1, WIDTH, 1)
    position = channel_phase * torch.complex(mode, -0.3 * mode)
    velocity = channel_phase * torch.complex(-0.2 * mode, 0.4 * mode)

    actual_position, actual_velocity = field._linear_exact_step(
        position, velocity, exact
    )
    omega2, alpha, cosine, sine_over_nu, decay = exact
    expected_position = decay * (
        (cosine[harmonic] + alpha * sine_over_nu[harmonic]) * position
        + sine_over_nu[harmonic] * velocity
    )
    expected_velocity = decay * (
        -omega2[harmonic] * sine_over_nu[harmonic] * position
        + (cosine[harmonic] - alpha * sine_over_nu[harmonic]) * velocity
    )

    assert actual_position.dtype == torch.complex128
    assert actual_position.shape == (CHANNELS, WIDTH, 1)
    assert actual_velocity.shape == actual_position.shape
    assert torch.isfinite(actual_position).all()
    assert torch.isfinite(actual_velocity).all()
    assert torch.allclose(actual_position, expected_position, atol=2e-13, rtol=2e-13)
    assert torch.allclose(actual_velocity, expected_velocity, atol=2e-13, rtol=2e-13)


def test_l34_changes_only_evolution_before_the_first_step() -> None:
    cyclic, exact = controllers()
    cyclic_state, cyclic_receipt = cyclic.heartbeat(
        cyclic.new_state(dtype=torch.float64)
    )
    exact_state, exact_receipt = exact.heartbeat(exact.new_state(dtype=torch.float64))

    assert torch.equal(cyclic_state.field, exact_state.field)
    assert cyclic_receipt.clamp_count == exact_receipt.clamp_count
    cyclic_state, cyclic_drift = cyclic.modulate_symbols(
        cyclic_state, (148,), source_trust=1.0
    )
    exact_state, exact_drift = exact.modulate_symbols(
        exact_state, (148,), source_trust=1.0
    )
    cyclic_readout = cyclic.white_readout(cyclic_state)
    exact_readout = exact.white_readout(exact_state)

    assert torch.equal(cyclic_state.field, exact_state.field)
    assert torch.equal(cyclic_drift, exact_drift)
    assert torch.equal(cyclic_readout.scores, exact_readout.scores)
    assert torch.equal(cyclic_readout.symbols, exact_readout.symbols)
    assert torch.equal(
        cyclic.psychedelic_projection(cyclic_state, max_side=16).rgb,
        exact.psychedelic_projection(exact_state, max_side=16).rgb,
    )


def test_blank_float32_differential_stays_exact_for_128_ticks() -> None:
    field = controllers()[1]
    state = field.new_state(dtype=torch.float32)

    for _ in range(128):
        tick = field.tick(state, steps=8)
        state = tick.state
        values = packed(state)
        assert torch.count_nonzero(values[:, 2:4, :WIDTH]) == 0
        assert torch.count_nonzero(values[:, :, WIDTH:]) == 0
        assert tick.clamp_count == 0
        assert torch.isfinite(state.field).all()

    assert field.dynamic_energy(state).item() <= 1.05


def test_driven_float32_state_remains_finite_and_bounded() -> None:
    field = controllers()[1]
    state, receipt = field.heartbeat(field.new_state(dtype=torch.float32))
    assert receipt.clamp_count == 0

    max_energy = field.dynamic_energy(state).item()
    clamp_count = 0
    for tick_index in range(64):
        symbols = (37 + tick_index % 17,) if tick_index % 8 == 0 else None
        tick = field.tick(state, symbols=symbols, steps=8)
        state = tick.state
        max_energy = max(max_energy, field.dynamic_energy(state).item())
        clamp_count += tick.clamp_count

    assert torch.isfinite(state.field).all()
    assert clamp_count == 0
    assert max_energy <= 1.05


def test_l34_profile_is_distinct_without_parallel_adaptive_state() -> None:
    cyclic, field = controllers()

    assert (
        EXACT_CYCLIC_LAYOUT_PROFILE_ID
        == "cassi.qi-cyclic-chromatic-coordinate-native.v1"
    )
    assert EXACT_CYCLIC_OPERATOR_PROFILE_ID == "cassi.qi-exact-cyclic-strang.v1"
    assert (
        EXACT_CYCLIC_PROJECTION_PROFILE_ID
        == "cassi.qi-cyclic-chromatic-projection.v1"
    )
    assert field.config_fingerprint != cyclic.config_fingerprint
    assert field.new_state(batch_size=3).field.shape == (CHANNELS, 9 * MODE_COUNT, 3)
    for name in (
        "model",
        "optimizer",
        "memory_table",
        "history",
        "time_counter",
        "learned_embedding",
    ):
        assert not hasattr(field, name)
