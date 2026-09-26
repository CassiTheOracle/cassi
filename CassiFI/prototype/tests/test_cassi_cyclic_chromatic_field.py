"""Focused CPU contracts for the frozen L31 cyclic-chromatic field."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_cyclic_chromatic_field import (
    CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID,
    CYCLIC_CHROMATIC_OPERATOR_PROFILE_ID,
    CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID,
    CyclicChromaticFieldConfig,
    CyclicChromaticFieldController,
)
from cassi_white_chromatic_field import (
    WhiteChromaticFieldConfig,
    WhiteChromaticFieldController,
)

CHANNELS = 7
MODE_COUNT = 520
WIDTH = MODE_COUNT // 2
DENOMINATOR = 1.0 + ((1.0 + math.sqrt(5.0)) / 2.0) ** 2


def controller() -> CyclicChromaticFieldController:
    return CyclicChromaticFieldController(
        CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
    )


def packed(state: object) -> torch.Tensor:
    field = getattr(state, "field")
    return field.reshape(CHANNELS, 9, MODE_COUNT, field.shape[2])


def test_native_coordinates_keep_blank_differential_exact_in_float32() -> None:
    field = controller()
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


def test_periodic_laplacian_preserves_white_and_first_chromatic_modes() -> None:
    field = controller()
    width = 11
    weight = torch.linspace(0.01, 0.03, width, dtype=torch.float64).reshape(
        1, width, 1
    ).expand(CHANNELS - 1, -1, -1)
    base = torch.complex(
        torch.linspace(0.2, 0.8, width, dtype=torch.float64),
        torch.linspace(-0.4, 0.3, width, dtype=torch.float64),
    ).reshape(1, width, 1)

    white = base.expand(CHANNELS, -1, -1)
    assert torch.count_nonzero(field._coupling_force(white, weight)) == 0

    angles = 2.0 * math.pi * torch.arange(CHANNELS, dtype=torch.float64) / CHANNELS
    phase = torch.complex(torch.cos(angles), torch.sin(angles)).reshape(
        CHANNELS, 1, 1
    )
    chromatic = phase * base
    force = field._coupling_force(chromatic, weight)
    eigenvalue = 2.0 * math.cos(2.0 * math.pi / CHANNELS) - 2.0

    assert torch.allclose(force, eigenvalue * weight[0] * chromatic, atol=1e-14)
    assert torch.allclose(force.sum(dim=0), torch.zeros_like(base), atol=1e-14)


def test_cyclic_hamiltonian_accounts_for_closing_edge() -> None:
    field = controller()
    state = field.new_state(dtype=torch.float64)
    values = packed(state)
    values[0, 0, :WIDTH] = 0.25

    path_energy = WhiteChromaticFieldController._hamiltonian_unchecked(field, state)
    cyclic_energy = field._hamiltonian_unchecked(state)
    weight = field._constants(state)["edge_weight"][0]
    closing = (0.5 * weight * torch.full_like(weight, 0.25**2)).mean(dim=0) / DENOMINATOR

    assert torch.allclose(cyclic_energy - path_energy, closing, atol=1e-14)


def test_modulation_readout_and_projection_remain_field_owned_and_read_only() -> None:
    field = controller()
    carrier, receipt = field.heartbeat(field.new_state(dtype=torch.float64))
    before_energy = field.dynamic_energy(carrier).clone()
    before = carrier.field.clone()

    state, drift = field.modulate_symbols(carrier, (148,), source_trust=1.0)
    state_before_projection = state.field.clone()
    readout = field.white_readout(state)
    projection = field.psychedelic_projection(state, max_side=16)

    assert torch.equal(carrier.field, before)
    assert receipt.clamp_count == 0
    assert abs(drift.item()) <= 1e-11
    assert field.dynamic_energy(state).item() == pytest.approx(
        before_energy.item(), abs=1e-12
    )
    assert readout.symbols.item() == 148
    assert readout.white_coherence.item() == pytest.approx(1.0, abs=1e-10)
    assert projection.rgb.shape == (1, 3, 16, 16)
    assert torch.isfinite(projection.rgb).all()
    assert 0.0 <= projection.rgb.min().item() <= projection.rgb.max().item() <= 1.0
    assert torch.equal(state.field, state_before_projection)


def test_l31_profile_is_distinct_without_parallel_adaptive_state() -> None:
    config = CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
    field = CyclicChromaticFieldController(config)

    assert CYCLIC_CHROMATIC_LAYOUT_PROFILE_ID == (
        "cassi.qi-cyclic-chromatic-coordinate-native.v1"
    )
    assert CYCLIC_CHROMATIC_OPERATOR_PROFILE_ID == (
        "cassi.qi-cyclic-chromatic-heartbeat.v1"
    )
    assert CYCLIC_CHROMATIC_PROJECTION_PROFILE_ID == (
        "cassi.qi-cyclic-chromatic-projection.v1"
    )
    assert config.fingerprint != WhiteChromaticFieldConfig(
        mode_count=MODE_COUNT
    ).fingerprint
    assert field.new_state(batch_size=3).field.shape == (CHANNELS, 9 * MODE_COUNT, 3)
    for name in (
        "model",
        "optimizer",
        "checkpoint",
        "save",
        "load",
        "learned_embedding",
        "parallel_policy",
    ):
        assert not hasattr(field, name)
