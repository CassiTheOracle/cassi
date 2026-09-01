"""Focused checks for field-local harmonic phase locking."""

from __future__ import annotations

import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_harmonic_attractor_field import (
    HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID,
    HarmonicAttractorFieldConfig,
    HarmonicAttractorFieldController,
)

MODE_COUNT = 520
S0 = (0, 37, 74, 111, 148, 185, 222, 259)
S1 = tuple((symbol + 97) % 260 for symbol in S0)
STAGES = tuple(
    tuple((symbol + 37 * step) % 260 for symbol in S0) for step in range(7)
) + (S1,)


def test_lock_preserves_energy_and_noncarrier_coordinates() -> None:
    field = HarmonicAttractorFieldController(
        HarmonicAttractorFieldConfig(mode_count=MODE_COUNT)
    )
    state = field.new_state(batch_size=2, dtype=torch.float64)
    generator = torch.Generator().manual_seed(47)
    shape = (7, field.config.wave_mode_count, 2)
    values = [
        0.02
        * torch.complex(
            torch.randn(shape, generator=generator, dtype=torch.float64),
            torch.randn(shape, generator=generator, dtype=torch.float64),
        )
        for _ in range(4)
    ]
    state = field._replace_coordinates(state, *values)
    before = field._active_coordinates(state)
    before_energy = field.dynamic_energy(state)
    before_epsilon = field._parts(state)[8].clone()
    white = field._constants(state)["white"]
    before_carrier = (white[:, None, None] * before[0]).sum(dim=0)
    before_velocity_carrier = (white[:, None, None] * before[2]).sum(dim=0)
    before_complement = before[0] - white[:, None, None] * before_carrier[None]
    before_velocity_complement = (
        before[2] - white[:, None, None] * before_velocity_carrier[None]
    )

    locked = field.lock_field(state)
    after = field._active_coordinates(locked)
    after_carrier = (white[:, None, None] * after[0]).sum(dim=0)
    after_velocity_carrier = (white[:, None, None] * after[2]).sum(dim=0)

    assert torch.allclose(
        after[0] - white[:, None, None] * after_carrier[None],
        before_complement,
        atol=2e-12,
        rtol=0,
    )
    assert torch.allclose(
        after[2] - white[:, None, None] * after_velocity_carrier[None],
        before_velocity_complement,
        atol=2e-12,
        rtol=0,
    )
    assert after_carrier.abs().std(dim=0).max().item() < 2e-12
    assert after_velocity_carrier.abs().std(dim=0).max().item() < 2e-12
    assert torch.equal(field._parts(locked)[8], before_epsilon)
    assert torch.allclose(field.dynamic_energy(locked), before_energy, atol=2e-12, rtol=0)
    assert locked.field.abs().max().item() < field.config.max_mode_amplitude
    assert HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID == "cassi.qi-harmonic-attractor.v1"


def test_seven_slot_reversal_survives_128_blank_ticks() -> None:
    torch.set_num_threads(1)
    field = HarmonicAttractorFieldController(
        HarmonicAttractorFieldConfig(mode_count=MODE_COUNT)
    )
    state = field.new_state(batch_size=8, dtype=torch.float64)
    history: list[tuple[int, ...]] = []
    clamp_count = 0

    def require_order() -> None:
        readout = field.white_readout(state)
        depth = min(len(history), 7)
        expected = torch.tensor(
            tuple(reversed(history[-depth:])), dtype=torch.int64
        ).T
        assert torch.equal(readout.age_symbols[:, :depth], expected)
        assert readout.age_available[:, :depth].all()

    for symbols in STAGES:
        tick = field.tick(state, symbols=symbols, steps=8)
        state = tick.state
        clamp_count += tick.clamp_count
        history.append(symbols)
        require_order()
        for _ in range(16):
            tick = field.tick(state, steps=8)
            state = tick.state
            clamp_count += tick.clamp_count
        require_order()

    for _ in range(112):
        tick = field.tick(state, steps=8)
        state = tick.state
        clamp_count += tick.clamp_count
    require_order()

    active = state.field.reshape(7, 9, MODE_COUNT, 8)[
        :, :8, : field.config.wave_mode_count
    ]
    assert clamp_count == 0
    assert torch.isfinite(state.field).all()
    assert active.abs().max().item() < field.config.max_mode_amplitude
