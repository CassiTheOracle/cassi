"""Focused CPU contracts for the frozen L32 quadrature readout."""

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
    CyclicChromaticFieldConfig,
    CyclicChromaticFieldController,
)
from cassi_quadrature_chromatic_field import (
    QUADRATURE_CHROMATIC_LAYOUT_PROFILE_ID,
    QUADRATURE_CHROMATIC_OPERATOR_PROFILE_ID,
    QUADRATURE_CHROMATIC_PROJECTION_PROFILE_ID,
    QuadratureChromaticFieldConfig,
    QuadratureChromaticFieldController,
)
from cassi_qi_field import QiFieldState

CHANNELS = 7
MODE_COUNT = 520
WIDTH = MODE_COUNT // 2


def controllers() -> tuple[
    CyclicChromaticFieldController, QuadratureChromaticFieldController
]:
    return (
        CyclicChromaticFieldController(
            CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
        QuadratureChromaticFieldController(
            QuadratureChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
    )


def test_l32_changes_readout_but_not_l31_state_dynamics() -> None:
    cyclic, quadrature = controllers()
    cyclic_state = cyclic.new_state(batch_size=2, dtype=torch.float64)
    quadrature_state = quadrature.new_state(batch_size=2, dtype=torch.float64)
    schedule: tuple[tuple[int, int] | None, ...] = (
        (37, 74),
        None,
        None,
        (134, 171),
        None,
    )

    for symbols in schedule:
        cyclic_tick = cyclic.tick(cyclic_state, symbols=symbols, steps=8)
        quadrature_tick = quadrature.tick(
            quadrature_state, symbols=symbols, steps=8
        )
        cyclic_state = cyclic_tick.state
        quadrature_state = quadrature_tick.state
        assert torch.equal(cyclic_state.field, quadrature_state.field)
        assert torch.equal(cyclic_tick.hamiltonian, quadrature_tick.hamiltonian)
        assert torch.equal(
            cyclic_tick.input_energy_drift, quadrature_tick.input_energy_drift
        )
        assert cyclic_tick.clamp_count == quadrature_tick.clamp_count

    cyclic_projection = cyclic.psychedelic_projection(cyclic_state, max_side=16)
    quadrature_projection = quadrature.psychedelic_projection(
        quadrature_state, max_side=16
    )
    assert torch.equal(cyclic_projection.rgb, quadrature_projection.rgb)


def test_velocity_only_symbol_is_recalled_from_normalized_quadrature() -> None:
    cyclic, field = controllers()
    state = field.new_state(dtype=torch.float64)
    phase_parts = field.codebook(0, dtype=torch.float64)[37]
    phase = torch.complex(phase_parts[:, 0], phase_parts[:, 1])
    angles = 2.0 * math.pi * torch.arange(CHANNELS, dtype=torch.float64) / CHANNELS
    channel_phase = torch.complex(torch.cos(angles), torch.sin(angles))
    normalized_velocity = (
        channel_phase[:, None, None]
        * phase[None, :, None]
        / math.sqrt(CHANNELS)
    )
    constants = field._constants(state)
    omega = torch.sqrt(
        constants["omega2"]
        + 4.0
        * constants["edge_weight"][0:1]
        * math.sin(math.pi / CHANNELS) ** 2
    )
    zeros = torch.zeros_like(normalized_velocity)
    velocity_state = field._replace_coordinates(
        state,
        zeros,
        zeros,
        zeros,
        normalized_velocity * omega,
    )
    before = velocity_state.field.clone()

    readout = field.white_readout(velocity_state)
    position_only = cyclic.white_readout(QiFieldState(velocity_state.field.clone()))

    assert torch.equal(velocity_state.field, before)
    assert torch.allclose(
        readout.normalized_differential_velocity,
        normalized_velocity,
        atol=1e-12,
    )
    assert readout.available.item()
    assert readout.symbols.item() == 37
    assert readout.white_coherence.item() == pytest.approx(1.0, abs=1e-10)
    assert not position_only.available.item()


def test_quadrature_scores_match_direct_phase_space_recomputation() -> None:
    _, field = controllers()
    carrier, _ = field.heartbeat(field.new_state(dtype=torch.float64))
    state, _ = field.modulate_symbols(carrier, (148,), trust=1.0)
    state = field.evolve(state, steps=11)
    before = state.field.clone()
    readout = field.white_readout(state)
    _, differential, _, _ = field._active_coordinates(state)
    normalized_velocity = field.normalized_differential_velocity(state)
    phase_parts = field.codebook(0, dtype=torch.float64)
    codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
    compensation = field._constants(state)["channel_phase"].conj()[:, None, None]
    coefficient_d = torch.einsum(
        "aw,swb->sab", codebook.conj(), differential
    ) / WIDTH
    coefficient_v = torch.einsum(
        "aw,swb->sab", codebook.conj(), normalized_velocity
    ) / WIDTH
    global_d = (compensation * coefficient_d).sum(dim=0) / math.sqrt(CHANNELS)
    global_v = (compensation * coefficient_v).sum(dim=0) / math.sqrt(CHANNELS)
    expected = (global_d.abs().square() + global_v.abs().square()).transpose(0, 1)

    assert torch.equal(state.field, before)
    assert torch.allclose(readout.scores, expected, atol=1e-12, rtol=1e-11)
    assert readout.symbols.item() == 148


def test_l32_profile_is_distinct_without_new_adaptive_state() -> None:
    cyclic, field = controllers()

    assert (
        QUADRATURE_CHROMATIC_LAYOUT_PROFILE_ID
        == "cassi.qi-cyclic-chromatic-coordinate-native.v1"
    )
    assert (
        QUADRATURE_CHROMATIC_OPERATOR_PROFILE_ID
        == "cassi.qi-quadrature-chromatic-recall.v1"
    )
    assert (
        QUADRATURE_CHROMATIC_PROJECTION_PROFILE_ID
        == "cassi.qi-cyclic-chromatic-projection.v1"
    )
    assert field.config_fingerprint != cyclic.config_fingerprint
    assert field.new_state(batch_size=3).field.shape == (CHANNELS, 9 * MODE_COUNT, 3)
    for name in ("model", "optimizer", "memory_table", "history", "time_counter"):
        assert not hasattr(field, name)
