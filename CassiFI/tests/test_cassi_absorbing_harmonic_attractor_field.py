"""Focused live-capacity check for the absorbing harmonic attractor."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_absorbing_harmonic_attractor_field import (
    ABSORBING_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID,
    AbsorbingHarmonicAttractorFieldConfig,
    AbsorbingHarmonicAttractorFieldController,
)
from cassi_qi_field import QiFieldState
from cassi_white_chromatic_field import WhiteChromaticFieldController

MODE_COUNT = 520
BASE = (0, 37, 74, 111, 148, 185, 222, 259)
STAGES = tuple(
    tuple((symbol + 37 * step) % 260 for symbol in BASE) for step in range(8)
)


def physical_harmonics(
    field: AbsorbingHarmonicAttractorFieldController,
    state,
) -> tuple[torch.Tensor, torch.Tensor]:
    _, differential, _, differential_velocity = field._active_coordinates(state)
    phase = field._constants(state)["channel_phase"]
    harmonics = torch.arange(7, dtype=torch.int64, device=phase.device)
    basis = phase.conj()[None, :].pow(harmonics[:, None]) / math.sqrt(7)
    return (
        torch.einsum("kc,cwb->kwb", basis, differential),
        torch.einsum("kc,cwb->kwb", basis, differential_velocity),
    )


def test_eighth_write_physically_retires_oldest_then_survives_evolution() -> None:
    torch.set_num_threads(1)
    field = AbsorbingHarmonicAttractorFieldController(
        AbsorbingHarmonicAttractorFieldConfig(mode_count=MODE_COUNT)
    )
    state = field.new_state(batch_size=8, dtype=torch.float64)
    clamp_count = 0
    for symbols in STAGES[:7]:
        tick = field.tick(state, symbols=symbols, steps=8)
        state = tick.state
        clamp_count += tick.clamp_count

    heartbeat_state, heartbeat = field._heartbeat_unchecked(state)
    before_d, before_vd = physical_harmonics(field, heartbeat_state)
    shifted = field.absorb_harmonics(heartbeat_state)
    after_d, after_vd = physical_harmonics(field, shifted)

    zero = torch.zeros_like(after_d[1])
    assert torch.allclose(after_d[1], zero, atol=2e-12, rtol=0)
    assert torch.allclose(after_vd[1], zero, atol=2e-12, rtol=0)
    assert torch.allclose(after_d[0], before_d[6], atol=2e-12, rtol=0)
    assert torch.allclose(after_vd[0], before_vd[6], atol=2e-12, rtol=0)
    assert torch.allclose(after_d[2:], before_d[1:6], atol=2e-12, rtol=0)
    assert torch.allclose(after_vd[2:], before_vd[1:6], atol=2e-12, rtol=0)
    before_energy = before_d.abs().square().sum() + before_vd.abs().square().sum()
    removed_energy = (
        before_d[0].abs().square().sum() + before_vd[0].abs().square().sum()
    )
    after_energy = after_d.abs().square().sum() + after_vd.abs().square().sum()
    assert torch.allclose(
        after_energy, before_energy - removed_energy, atol=2e-10, rtol=0
    )

    state, _, write_clamps = WhiteChromaticFieldController._modulate_unchecked(
        field, shifted, STAGES[7], 1.0
    )
    state, evolve_clamps = field._evolve_unchecked(state, 8)
    clamp_count += heartbeat.clamp_count + write_clamps + evolve_clamps
    expected = torch.tensor(tuple(reversed(STAGES[1:])), dtype=torch.int64).T

    def require_newest_seven() -> None:
        readout = field.white_readout(state)
        assert torch.equal(readout.age_symbols[:, :7], expected)
        assert readout.age_available[:, :7].all()

    require_newest_seven()
    for _ in range(16):
        tick = field.tick(state, steps=8)
        state = tick.state
        clamp_count += tick.clamp_count
    require_newest_seven()

    active = state.field.reshape(7, 9, MODE_COUNT, 8)[
        :, :8, : field.config.wave_mode_count
    ]
    assert clamp_count == 0
    assert torch.isfinite(state.field).all()
    assert active.abs().max().item() < field.config.max_mode_amplitude
    assert ABSORBING_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID == (
        "cassi.qi-absorbing-harmonic-attractor.v1"
    )


def test_reinstantiated_controller_continues_from_field_tensor_exactly() -> None:
    torch.set_num_threads(1)
    config = AbsorbingHarmonicAttractorFieldConfig(mode_count=MODE_COUNT)
    field = AbsorbingHarmonicAttractorFieldController(config)
    state = field.new_state(batch_size=8, dtype=torch.float64)
    stages = STAGES[:3] + (STAGES[1],) + STAGES[3:6]

    for symbols in stages:
        state = field.tick(state, symbols=symbols, steps=8).state
    for _ in range(16):
        state = field.tick(state, steps=8).state
    before = field.white_readout(state)
    expected = torch.tensor(tuple(reversed(stages)), dtype=torch.int64).T
    assert torch.all(before.age_available[:, :7])
    assert torch.equal(before.age_symbols[:, :7], expected)

    cloned_field = state.field.detach().cpu().clone()
    next_symbols = STAGES[6]
    uninterrupted_write = field.tick(state, symbols=next_symbols, steps=8)
    uninterrupted_blank = field.tick(uninterrupted_write.state, steps=8)
    uninterrupted_readouts = (
        field.white_readout(uninterrupted_write.state),
        field.white_readout(uninterrupted_blank.state),
    )
    del field

    fresh = AbsorbingHarmonicAttractorFieldController(config)
    reconstructed = QiFieldState(cloned_field)
    assert torch.equal(reconstructed.field, state.field)
    reconstructed_write = fresh.tick(
        reconstructed, symbols=next_symbols, steps=8
    )
    reconstructed_blank = fresh.tick(reconstructed_write.state, steps=8)
    reconstructed_readouts = (
        fresh.white_readout(reconstructed_write.state),
        fresh.white_readout(reconstructed_blank.state),
    )

    for uninterrupted, resumed in (
        (uninterrupted_write, reconstructed_write),
        (uninterrupted_blank, reconstructed_blank),
    ):
        assert torch.equal(uninterrupted.state.field, resumed.state.field)
        assert torch.equal(
            uninterrupted.input_energy_drift, resumed.input_energy_drift
        )
        assert uninterrupted.clamp_count == resumed.clamp_count
    for uninterrupted, resumed in zip(
        uninterrupted_readouts, reconstructed_readouts
    ):
        assert torch.equal(uninterrupted.age_scores, resumed.age_scores)
        assert torch.equal(uninterrupted.age_symbols, resumed.age_symbols)
        assert torch.equal(uninterrupted.age_available, resumed.age_available)
