"""Focused CPU contracts for the frozen L42 harmonic age ladder."""

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
from cassi_harmonic_age_field import (
    HARMONIC_AGE_INDICES,
    HARMONIC_AGE_LAYOUT_PROFILE_ID,
    HARMONIC_AGE_OPERATOR_PROFILE_ID,
    HARMONIC_AGE_PROJECTION_PROFILE_ID,
    HarmonicAgeFieldConfig,
    HarmonicAgeFieldController,
)
from cassi_qi_field import QiFieldState

CHANNELS = 7
MODE_COUNT = 520
SYMBOLS = (37, 134, 74, 171)


def controllers() -> tuple[
    CyclicChromaticFieldController, HarmonicAgeFieldController
]:
    return (
        CyclicChromaticFieldController(
            CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
        HarmonicAgeFieldController(HarmonicAgeFieldConfig(mode_count=MODE_COUNT)),
    )


def complex_random(shape: tuple[int, ...], scale: float = 1.0e-3) -> torch.Tensor:
    generator = torch.Generator().manual_seed(sum(shape))
    return scale * torch.complex(
        torch.randn(shape, dtype=torch.float64, generator=generator),
        torch.randn(shape, dtype=torch.float64, generator=generator),
    )


def direct_age_readout(
    field: HarmonicAgeFieldController,
    state: QiFieldState,
    allowed: tuple[int, ...] | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    cyclic = CyclicChromaticFieldController(
        CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
    )
    current = cyclic.white_readout(
        QiFieldState(state.field.clone()), allowed_symbols=allowed
    )
    _, differential, _, _ = field._active_coordinates(state)
    phase = field._constants(state)["channel_phase"]
    harmonics = torch.tensor(HARMONIC_AGE_INDICES, dtype=torch.int64)
    basis = phase.conj()[None, :].pow(harmonics[:, None]) / math.sqrt(CHANNELS)
    collapsed = torch.einsum("hc,cwb->hwb", basis, differential)
    phase_parts = field.codebook(0, dtype=torch.float64)
    codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
    coefficients = torch.einsum(
        "aw,hwb->hba", codebook.conj(), collapsed
    ) / float(field.config.wave_mode_count)
    age_scores = coefficients.abs().square().permute(1, 0, 2)
    if allowed is None:
        age_symbols = torch.argmax(age_scores, dim=2)
    else:
        allowed_tensor = torch.tensor(allowed)
        local = torch.argmax(age_scores.index_select(2, allowed_tensor), dim=2)
        age_symbols = allowed_tensor.index_select(0, local.reshape(-1)).reshape_as(
            local
        )
    floor = field.config.readout_energy_floor
    age_max = age_scores.amax(dim=2)
    age_available = current.available[:, None] & (age_max >= floor)
    scores = (age_scores / age_max.clamp_min(floor)[:, :, None]).amax(dim=1)
    candidates = torch.arange(field.config.alphabet_size)[None, :]
    for age in range(CHANNELS - 1, -1, -1):
        slot = age_available[:, age, None] & (
            candidates == age_symbols[:, age, None]
        )
        scores = torch.where(slot, torch.full_like(scores, 8.0 - age), scores)
    scores = torch.where(current.available[:, None], scores, current.scores)
    return age_scores, age_symbols, age_available, scores


def test_one_lift_is_unitary_and_touches_only_chromatic_planes() -> None:
    _, field = controllers()
    state = field.new_state(batch_size=2, dtype=torch.float64)
    common = complex_random((CHANNELS, field.config.wave_mode_count, 2))
    differential = complex_random((CHANNELS, field.config.wave_mode_count, 2))
    common_velocity = complex_random((CHANNELS, field.config.wave_mode_count, 2))
    differential_velocity = complex_random(
        (CHANNELS, field.config.wave_mode_count, 2)
    )
    state = field._replace_coordinates(
        state, common, differential, common_velocity, differential_velocity
    )

    lifted = field.lift_harmonics(state)
    got_common, got_differential, got_common_velocity, got_differential_velocity = (
        field._active_coordinates(lifted)
    )
    phase = field._constants(state)["channel_phase"][:, None, None]

    assert lifted.field.shape == state.field.shape
    assert torch.isfinite(lifted.field).all()
    assert torch.equal(got_common, common)
    assert torch.equal(got_common_velocity, common_velocity)
    assert torch.equal(got_differential, phase * differential)
    assert torch.equal(got_differential_velocity, phase * differential_velocity)


def test_seven_lifts_are_identity_and_preserve_dynamic_energy() -> None:
    _, field = controllers()
    state = field.new_state(batch_size=2, dtype=torch.float64)
    parts = tuple(
        complex_random((CHANNELS, field.config.wave_mode_count, 2), 1.0e-4)
        for _ in range(4)
    )
    state = field._replace_coordinates(state, *parts)
    before_energy = field.dynamic_energy(state)
    lifted = state
    for _ in range(CHANNELS):
        lifted = field.lift_harmonics(lifted)
    before = field._active_coordinates(state)
    after = field._active_coordinates(lifted)

    assert torch.equal(before[0], after[0])
    assert torch.equal(before[2], after[2])
    assert torch.allclose(before[1], after[1], rtol=0.0, atol=2.0e-12)
    assert torch.allclose(before[3], after[3], rtol=0.0, atol=2.0e-12)
    assert torch.allclose(
        field.dynamic_energy(lifted), before_energy, rtol=0.0, atol=2.0e-12
    )


def test_lift_advances_one_pure_channel_harmonic() -> None:
    _, field = controllers()
    state = field.new_state(dtype=torch.float64)
    phase = field._constants(state)["channel_phase"]
    trace = complex_random((field.config.wave_mode_count, 1), 1.0e-4)
    harmonic = 4
    differential = (
        phase[:, None, None].pow(harmonic) * trace[None] / math.sqrt(CHANNELS)
    )
    zero = torch.zeros_like(differential)
    state = field._replace_coordinates(state, zero, differential, zero, zero)
    lifted = field.lift_harmonics(state)
    _, got, _, _ = field._active_coordinates(lifted)
    basis = phase.conj()[None, :].pow(
        torch.arange(CHANNELS)[:, None]
    ) / math.sqrt(CHANNELS)
    collapsed = torch.einsum("hc,cwb->hwb", basis, got)
    magnitudes = collapsed.abs().amax(dim=(1, 2))

    assert int(torch.argmax(magnitudes).item()) == (harmonic + 1) % CHANNELS
    off_slot = torch.cat((magnitudes[:5], magnitudes[6:]))
    assert off_slot.max().item() < 2.0e-12
    assert torch.allclose(collapsed[5], trace, rtol=0.0, atol=2.0e-12)


def test_no_symbol_path_is_bit_identical_to_l31() -> None:
    cyclic, field = controllers()
    cyclic_state = cyclic.new_state(batch_size=2, dtype=torch.float64)
    harmonic_state = field.new_state(batch_size=2, dtype=torch.float64)

    for _ in range(4):
        cyclic_tick = cyclic.tick(cyclic_state, symbols=None, steps=8)
        harmonic_tick = field.tick(harmonic_state, symbols=None, steps=8)
        cyclic_state = cyclic_tick.state
        harmonic_state = harmonic_tick.state
        assert torch.equal(cyclic_state.field, harmonic_state.field)
        assert torch.equal(cyclic_tick.hamiltonian, harmonic_tick.hamiltonian)
        assert cyclic_tick.clamp_count == harmonic_tick.clamp_count


def test_readout_equals_direct_seven_harmonic_recomputation() -> None:
    _, field = controllers()
    state = field.new_state(batch_size=2, dtype=torch.float64)
    for symbols in ((37, 74), (134, 171), (74, 208)):
        state = field.tick(state, symbols=symbols, steps=8).state
    before = state.field.clone()

    readout = field.white_readout(state)
    age_scores, age_symbols, age_available, scores = direct_age_readout(field, state)

    assert torch.equal(state.field, before)
    assert torch.equal(readout.age_scores, age_scores)
    assert torch.equal(readout.age_symbols, age_symbols)
    assert torch.equal(readout.age_available, age_available)
    assert torch.equal(readout.scores, scores)
    assert readout.age_harmonics == HARMONIC_AGE_INDICES
    assert torch.equal(readout.symbols, readout.age_symbols[:, 0])


@pytest.mark.xfail(
    strict=True,
    reason="L42 frozen fourth-deposit functional failure retained for canonical classification",
)
def test_one_through_four_deposits_fill_ordered_age_slots() -> None:
    _, field = controllers()
    state = field.new_state(dtype=torch.float64)

    for count, symbol in enumerate(SYMBOLS, start=1):
        state = field.tick(state, symbols=(symbol,), steps=8).state
        readout = field.white_readout(state)
        expected = list(reversed(SYMBOLS[:count]))
        assert readout.symbols.item() == symbol
        assert readout.age_symbols[0, :count].tolist() == expected
        assert readout.age_available[0, :count].all()
        assert torch.topk(readout.scores[0], count).indices.tolist() == expected


def test_allowed_symbols_govern_every_age_winner() -> None:
    _, field = controllers()
    state = field.new_state(dtype=torch.float64)
    for symbol in SYMBOLS:
        state = field.tick(state, symbols=(symbol,), steps=8).state

    allowed = (19, 56, 93)
    readout = field.white_readout(state, allowed_symbols=allowed)
    assert all(int(symbol) in allowed for symbol in readout.age_symbols[0])
    assert int(readout.symbols.item()) in allowed


def test_blank_is_exact_zero_without_auxiliary_state() -> None:
    cyclic, field = controllers()
    blank = field.white_readout(field.new_state(dtype=torch.float64))

    assert not blank.available.item()
    assert not blank.age_available.any()
    assert torch.count_nonzero(blank.age_scores) == 0
    assert torch.count_nonzero(blank.scores) == 0
    assert HARMONIC_AGE_LAYOUT_PROFILE_ID == (
        "cassi.qi-cyclic-chromatic-coordinate-native.v1"
    )
    assert HARMONIC_AGE_OPERATOR_PROFILE_ID == "cassi.qi-harmonic-age-ladder.v1"
    assert HARMONIC_AGE_PROJECTION_PROFILE_ID == (
        "cassi.qi-cyclic-chromatic-projection.v1"
    )
    assert field.config_fingerprint != cyclic.config_fingerprint
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
