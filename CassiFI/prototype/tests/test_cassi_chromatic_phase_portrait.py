"""Focused CPU contracts for the frozen L36 chromatic phase portrait."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_chromatic_phase_portrait import (
    CHROMATIC_PHASE_PORTRAIT_PANEL_NAMES,
    CHROMATIC_PHASE_PORTRAIT_PROFILE_ID,
    chromatic_phase_portrait,
)
from cassi_cyclic_chromatic_field import (
    CyclicChromaticFieldConfig,
    CyclicChromaticFieldController,
)

MODE_COUNT = 520
CHANNELS = 7


def controller() -> CyclicChromaticFieldController:
    return CyclicChromaticFieldController(
        CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
    )


def test_portrait_is_read_only_deterministic_and_bounded() -> None:
    field = controller()
    state = field.new_state(batch_size=2, dtype=torch.float64)
    tick = field.tick(state, symbols=(252, 132), steps=8)
    state = tick.state
    before = state.field.clone()

    first = chromatic_phase_portrait(field, state, panel_side=8)
    second = chromatic_phase_portrait(field, state, panel_side=8)

    assert torch.equal(state.field, before)
    assert torch.equal(first.rgb, second.rgb)
    assert torch.equal(first.panel_amplitude, second.panel_amplitude)
    assert torch.equal(first.panel_phase, second.panel_phase)
    assert first.rgb.shape == (2, 3, 17, 17)
    assert first.panel_amplitude.shape == (2, 4, 8, 8)
    assert first.panel_phase.shape == first.panel_amplitude.shape
    assert first.panel_peak_amplitude.shape == (2, 4)
    assert first.panel_side == 8
    assert first.side == 17
    assert torch.isfinite(first.rgb).all()
    assert torch.isfinite(first.panel_amplitude).all()
    assert torch.isfinite(first.panel_phase).all()
    assert 0.0 <= first.rgb.min().item() <= first.rgb.max().item() <= 1.0
    assert -math.pi <= first.panel_phase.min().item()
    assert first.panel_phase.max().item() <= math.pi
    assert torch.count_nonzero(first.rgb[:, :, 8, :]) == 0
    assert torch.count_nonzero(first.rgb[:, :, :, 8]) == 0


def test_each_native_coordinate_activates_only_its_own_panel() -> None:
    field = controller()
    state = field.new_state(dtype=torch.float64)
    width = field.config.wave_mode_count
    carrier = torch.complex(
        torch.linspace(0.1, 1.0, width, dtype=torch.float64),
        torch.linspace(-0.3, 0.4, width, dtype=torch.float64),
    ).reshape(1, width, 1)
    constants = field._constants(state)
    common_fixture = constants["white"][:, None, None] * carrier
    differential_fixture = (
        constants["channel_phase"][:, None, None]
        * carrier
        / math.sqrt(CHANNELS)
    )
    zero = torch.zeros_like(common_fixture)
    fixtures = (common_fixture, differential_fixture, common_fixture, differential_fixture)

    for active_index in range(4):
        coordinates = [zero, zero, zero, zero]
        coordinates[active_index] = fixtures[active_index]
        candidate = field._replace_coordinates(state, *coordinates)
        portrait = chromatic_phase_portrait(field, candidate, panel_side=8)
        peak = portrait.panel_peak_amplitude[0]
        assert peak[active_index].item() > 0.0
        assert torch.count_nonzero(
            torch.cat((peak[:active_index], peak[active_index + 1 :]))
        ) == 0


def test_quadrature_rotation_preserves_amplitude_and_rotates_color() -> None:
    field = controller()
    state = field.new_state(dtype=torch.float64)
    width = field.config.wave_mode_count
    carrier = torch.complex(
        torch.linspace(0.2, 0.9, width, dtype=torch.float64),
        torch.linspace(0.1, 0.5, width, dtype=torch.float64),
    ).reshape(1, width, 1)
    direction = (
        field._constants(state)["channel_phase"][:, None, None]
        / math.sqrt(CHANNELS)
    )
    zero = torch.zeros_like(direction * carrier)
    original = field._replace_coordinates(
        state, zero, direction * carrier, zero, zero
    )
    rotated = field._replace_coordinates(
        state, zero, 1j * direction * carrier, zero, zero
    )

    first = chromatic_phase_portrait(field, original, panel_side=8)
    second = chromatic_phase_portrait(field, rotated, panel_side=8)
    active = first.panel_amplitude[:, 1] > 1.0e-12
    phase_delta = torch.angle(
        torch.exp(1j * (second.panel_phase[:, 1] - first.panel_phase[:, 1]))
    )

    assert torch.allclose(
        first.panel_amplitude[:, 1], second.panel_amplitude[:, 1], atol=1e-12
    )
    assert torch.allclose(
        phase_delta[active],
        torch.full_like(phase_delta[active], 0.5 * math.pi),
        atol=1e-12,
    )
    assert not torch.equal(first.rgb, second.rgb)


def test_projection_identity_has_no_adaptive_object() -> None:
    assert (
        CHROMATIC_PHASE_PORTRAIT_PROFILE_ID
        == "cassi.qi-chromatic-phase-portrait.v1"
    )
    assert CHROMATIC_PHASE_PORTRAIT_PANEL_NAMES == ("C", "D", "VC", "VD")
