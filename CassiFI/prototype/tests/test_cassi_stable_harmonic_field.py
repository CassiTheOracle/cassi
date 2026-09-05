"""Focused contracts for the frozen L43 stable harmonic readout."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_harmonic_age_field import (
    HARMONIC_AGE_INDICES,
    HarmonicAgeFieldConfig,
    HarmonicAgeFieldController,
)
from cassi_qi_field import QiFieldState
from cassi_stable_harmonic_field import (
    ROUND_OFF_MULTIPLIER,
    STABLE_HARMONIC_LAYOUT_PROFILE_ID,
    STABLE_HARMONIC_OPERATOR_PROFILE_ID,
    STABLE_HARMONIC_PROJECTION_PROFILE_ID,
    StableHarmonicFieldConfig,
    StableHarmonicFieldController,
)

SYMBOLS = (37, 134, 74, 171)


def controllers(
    mode_count: int = 520,
) -> tuple[HarmonicAgeFieldController, StableHarmonicFieldController]:
    return (
        HarmonicAgeFieldController(HarmonicAgeFieldConfig(mode_count=mode_count)),
        StableHarmonicFieldController(
            StableHarmonicFieldConfig(mode_count=mode_count)
        ),
    )


def synthetic_state(
    field: StableHarmonicFieldController,
    amplitudes: tuple[float, ...],
    *,
    dtype: torch.dtype,
) -> QiFieldState:
    state = field.new_state(dtype=dtype)
    phase_parts = field.codebook(0, dtype=dtype)
    codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
    phase = field._constants(state)["channel_phase"]
    differential = torch.zeros(
        (7, field.config.wave_mode_count, 1), dtype=codebook.dtype
    )
    for age, amplitude in enumerate(amplitudes):
        harmonic = HARMONIC_AGE_INDICES[age]
        trace = codebook[SYMBOLS[age]][:, None]
        differential += (
            amplitude
            * phase[:, None, None].pow(harmonic)
            * trace[None]
            / math.sqrt(7)
        )
    zero = torch.zeros_like(differential)
    return field._replace_coordinates(state, zero, differential, zero, zero)


def direct_stable_readout(
    field: StableHarmonicFieldController, state: QiFieldState
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    base = HarmonicAgeFieldController(
        HarmonicAgeFieldConfig(mode_count=field.config.mode_count)
    ).white_readout(QiFieldState(state.field.clone()))
    age_max = base.age_scores.amax(dim=2)
    row_peak = age_max.amax(dim=1)
    floor = torch.maximum(
        torch.full_like(row_peak, field.config.readout_energy_floor),
        row_peak
        * (ROUND_OFF_MULTIPLIER * torch.finfo(state.field.real.dtype).eps),
    )
    available = base.available[:, None] & (age_max >= floor[:, None])
    normalized = torch.where(
        available[:, :, None],
        base.age_scores / age_max.clamp_min(floor[:, None])[:, :, None],
        torch.zeros_like(base.age_scores),
    )
    scores = normalized.amax(dim=1)
    candidates = torch.arange(field.config.alphabet_size)[None, :]
    for age in range(6, -1, -1):
        slot = available[:, age, None] & (
            candidates == base.age_symbols[:, age, None]
        )
        scores = torch.where(slot, torch.full_like(scores, 8.0 - age), scores)
    scores = torch.where(base.available[:, None], scores, base.scores)
    return floor, available, normalized, scores


def test_modulation_and_no_symbol_evolution_are_bit_identical_to_l42() -> None:
    harmonic, stable = controllers()
    harmonic_state = harmonic.new_state(batch_size=2, dtype=torch.float64)
    stable_state = stable.new_state(batch_size=2, dtype=torch.float64)
    schedule = ((37, 74), None, (134, 171), None)

    for symbols in schedule:
        harmonic_tick = harmonic.tick(harmonic_state, symbols=symbols, steps=8)
        stable_tick = stable.tick(stable_state, symbols=symbols, steps=8)
        harmonic_state = harmonic_tick.state
        stable_state = stable_tick.state
        assert torch.equal(harmonic_state.field, stable_state.field)
        assert torch.equal(harmonic_tick.hamiltonian, stable_tick.hamiltonian)
        assert harmonic_tick.clamp_count == stable_tick.clamp_count


@pytest.mark.parametrize("dtype", (torch.float32, torch.float64))
def test_dtype_floor_keeps_strong_harmonics_and_masks_weak_residue(
    dtype: torch.dtype,
) -> None:
    _, field = controllers()
    epsilon = torch.finfo(dtype).eps
    expected_floor = max(1.0e-8, ROUND_OFF_MULTIPLIER * epsilon)
    weak_amplitude = math.sqrt(expected_floor / 4.0)
    state = synthetic_state(field, (1.0, 0.1, weak_amplitude), dtype=dtype)

    readout = field.white_readout(state)
    floor, available, normalized, scores = direct_stable_readout(field, state)

    assert readout.age_available[0, :2].all()
    assert not readout.age_available[0, 2]
    assert torch.count_nonzero(normalized[0, 2]) == 0
    assert torch.equal(readout.age_numerical_floor, floor)
    assert torch.equal(readout.age_available, available)
    assert torch.equal(readout.scores, scores)


def test_every_readout_field_matches_direct_reconstruction() -> None:
    _, field = controllers()
    state = field.new_state(batch_size=2, dtype=torch.float64)
    for symbols in ((37, 74), (134, 171), (74, 208)):
        state = field.tick(state, symbols=symbols, steps=8).state
    before = state.field.clone()

    readout = field.white_readout(state)
    floor, available, _, scores = direct_stable_readout(field, state)

    assert torch.equal(state.field, before)
    assert torch.equal(readout.age_numerical_floor, floor)
    assert torch.equal(readout.age_available, available)
    assert torch.equal(readout.scores, scores)
    assert torch.equal(readout.symbols, readout.age_symbols[:, 0])


def test_four_mode_2048_deposits_fill_exact_reverse_age_order() -> None:
    _, field = controllers(mode_count=2048)
    state = field.new_state(dtype=torch.float32)

    for count, symbol in enumerate(SYMBOLS, start=1):
        state = field.tick(state, symbols=(symbol,), steps=8).state
        readout = field.white_readout(state)
        expected = list(reversed(SYMBOLS[:count]))
        assert readout.symbols.item() == symbol
        assert readout.age_symbols[0, :count].tolist() == expected
        assert readout.age_available[0, :count].all()
        assert not readout.age_available[0, count:].any()
        assert torch.topk(readout.scores[0], count).indices.tolist() == expected


def test_allowed_symbols_govern_every_available_age_winner() -> None:
    _, field = controllers(mode_count=2048)
    state = field.new_state(dtype=torch.float32)
    for symbol in SYMBOLS:
        state = field.tick(state, symbols=(symbol,), steps=8).state

    allowed = (19, 56, 93)
    readout = field.white_readout(state, allowed_symbols=allowed)
    winners = readout.age_symbols[0][readout.age_available[0]].tolist()
    assert winners
    assert all(int(symbol) in allowed for symbol in winners)
    assert int(readout.symbols.item()) in allowed


def test_blank_is_exact_zero_without_auxiliary_state() -> None:
    harmonic, field = controllers()
    blank = field.white_readout(field.new_state(dtype=torch.float64))

    assert not blank.available.item()
    assert not blank.age_available.any()
    assert torch.count_nonzero(blank.age_scores) == 0
    assert torch.count_nonzero(blank.scores) == 0
    assert blank.age_numerical_floor.item() == field.config.readout_energy_floor
    assert STABLE_HARMONIC_LAYOUT_PROFILE_ID == (
        "cassi.qi-cyclic-chromatic-coordinate-native.v1"
    )
    assert STABLE_HARMONIC_OPERATOR_PROFILE_ID == (
        "cassi.qi-stable-harmonic-age-ladder.v1"
    )
    assert STABLE_HARMONIC_PROJECTION_PROFILE_ID == (
        "cassi.qi-cyclic-chromatic-projection.v1"
    )
    assert field.config_fingerprint != harmonic.config_fingerprint
    for name in (
        "model",
        "optimizer",
        "memory_table",
        "history",
        "time_counter",
        "shift_counter",
        "learned_embedding",
    ):
        assert not hasattr(field, name)
