"""Focused CPU contracts for the L47 absorbing harmonic age write."""

from __future__ import annotations

import math
from pathlib import Path
import sys

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_absorbing_harmonic_age_field import (
    ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID,
    ABSORBING_HARMONIC_AGE_OPERATOR_PROFILE_ID,
    ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID,
    AbsorbingHarmonicAgeFieldConfig,
    AbsorbingHarmonicAgeFieldController,
)
from cassi_absorbing_harmonic_attractor_field import (
    ABSORBING_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID,
    AbsorbingHarmonicAttractorFieldConfig,
    AbsorbingHarmonicAttractorFieldController,
)
from cassi_harmonic_age_field import (
    HarmonicAgeFieldConfig,
    HarmonicAgeFieldController,
)
from cassi_ordered_relational_field import (
    OrderedRelationalChromaticFieldConfig,
    OrderedRelationalChromaticFieldController,
)
from cassi_qi_field import QiFieldState
from cassi_white_chromatic_field import WhiteChromaticFieldController


CHANNELS = 7
MODE_COUNT = 520


def controller() -> AbsorbingHarmonicAgeFieldController:
    return AbsorbingHarmonicAgeFieldController(
        AbsorbingHarmonicAgeFieldConfig(mode_count=MODE_COUNT)
    )


def complex_random(shape: tuple[int, ...], seed: int, scale: float = 1.0e-3) -> torch.Tensor:
    generator = torch.Generator().manual_seed(seed)
    return scale * torch.complex(
        torch.randn(shape, dtype=torch.float64, generator=generator),
        torch.randn(shape, dtype=torch.float64, generator=generator),
    )


def populated_state(field: AbsorbingHarmonicAgeFieldController) -> QiFieldState:
    state = field.new_state(batch_size=2, dtype=torch.float64)
    shape = (CHANNELS, field.config.wave_mode_count, state.batch_size)
    common, differential = complex_random(shape, 11), complex_random(shape, 13)
    common_velocity, differential_velocity = complex_random(shape, 17), complex_random(shape, 19)
    epsilon = torch.arange(
        1, CHANNELS + 1, dtype=torch.float64
    )[:, None, None].expand(CHANNELS, field.config.wave_mode_count, state.batch_size) * 1.0e-4
    return field._replace_coordinates(
        state, common, differential, common_velocity, differential_velocity, epsilon=epsilon
    )


def dft(field: AbsorbingHarmonicAgeFieldController, values: torch.Tensor) -> torch.Tensor:
    phase = field._constants(field.new_state(dtype=torch.float64))["channel_phase"]
    basis = phase.conj()[None, :].pow(torch.arange(CHANNELS)[:, None]) / math.sqrt(CHANNELS)
    return torch.einsum("hc,cwb->hwb", basis, values)


def test_identity_off_and_exact_profile_constants() -> None:
    field = controller()
    state = populated_state(field)
    clone = QiFieldState(state.field.clone())

    assert torch.equal(state.field, clone.field)
    assert ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID == "cassi.qi-cyclic-chromatic-coordinate-native.v1"
    assert ABSORBING_HARMONIC_AGE_OPERATOR_PROFILE_ID == "cassi.qi-absorbing-harmonic-age-write.v2"
    assert ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID == "cassi.qi-cyclic-chromatic-projection.v1"
    assert field.config_fingerprint != HarmonicAgeFieldController(
        HarmonicAgeFieldConfig(mode_count=MODE_COUNT)
    ).config_fingerprint


def test_native_equation_and_dft_shift() -> None:
    field = controller()
    state = populated_state(field)
    common, differential, common_velocity, differential_velocity = field._active_coordinates(state)
    phase = field._constants(state)["channel_phase"][:, None, None]
    expected = phase * (differential - differential.mean(dim=0, keepdim=True))
    expected_velocity = phase * (
        differential_velocity - differential_velocity.mean(dim=0, keepdim=True)
    )

    shifted = field.absorb_harmonics(state)
    got_common, got_differential, got_common_velocity, got_differential_velocity = field._active_coordinates(shifted)
    assert torch.equal(got_common, common)
    assert torch.equal(got_common_velocity, common_velocity)
    assert torch.allclose(got_differential, expected, rtol=0.0, atol=2.0e-12)
    assert torch.allclose(got_differential_velocity, expected_velocity, rtol=0.0, atol=2.0e-12)

    before = dft(field, differential)
    after = dft(field, got_differential)
    expected_dft = torch.zeros_like(before)
    expected_dft[2:] = before[1:-1]
    expected_dft[0] = before[6]
    expected_dft[1] = 0.0
    assert torch.allclose(after, expected_dft, rtol=0.0, atol=2.0e-12)


def test_seven_absorbing_shifts_annihilate_d_and_vd() -> None:
    field = controller()
    state = populated_state(field)
    shifted = state
    for _ in range(CHANNELS):
        shifted = field.absorb_harmonics(shifted)
    _, differential, _, differential_velocity = field._active_coordinates(shifted)
    assert torch.allclose(differential, torch.zeros_like(differential), rtol=0.0, atol=2.0e-12)
    assert torch.allclose(
        differential_velocity, torch.zeros_like(differential_velocity), rtol=0.0, atol=2.0e-12
    )


def test_projection_loses_exact_discarded_harmonic_energy() -> None:
    field = controller()
    state = populated_state(field)
    _, differential, _, differential_velocity = field._active_coordinates(state)
    zero_d = dft(field, differential)[0]
    zero_v = dft(field, differential_velocity)[0]
    before = field.dynamic_energy(state)
    after = field.dynamic_energy(field.absorb_harmonics(state))
    denominator = 1.0 + ((1.0 + math.sqrt(5.0)) / 2.0) ** 2
    removed = (
        zero_d.abs().square() + zero_v.abs().square()
    ).mean(dim=0) / (CHANNELS * denominator)
    assert torch.allclose(before - after, removed, rtol=0.0, atol=2.0e-12)
    assert torch.all(after <= before + 2.0e-12)


def test_common_velocity_epsilon_and_inactive_tails_are_untouched() -> None:
    field = controller()
    state = populated_state(field)
    shifted = field.absorb_harmonics(state)
    before_parts = field._parts(state)
    after_parts = field._parts(shifted)
    width = field.config.wave_mode_count
    for index in (0, 1, 4, 5, 8):
        assert torch.equal(before_parts[index], after_parts[index])
    for index in (2, 3, 6, 7):
        assert torch.equal(before_parts[index][:, width:], after_parts[index][:, width:])


def test_no_symbol_path_is_bit_identical_to_l42() -> None:
    baseline = HarmonicAgeFieldController(HarmonicAgeFieldConfig(mode_count=MODE_COUNT))
    field = controller()
    baseline_state = baseline.new_state(batch_size=2, dtype=torch.float64)
    absorbing_state = field.new_state(batch_size=2, dtype=torch.float64)
    for _ in range(4):
        baseline_tick = baseline.tick(baseline_state, symbols=None, steps=8)
        absorbing_tick = field.tick(absorbing_state, symbols=None, steps=8)
        baseline_state, absorbing_state = baseline_tick.state, absorbing_tick.state
        assert torch.equal(baseline_state.field, absorbing_state.field)
        assert torch.equal(baseline_tick.hamiltonian, absorbing_tick.hamiltonian)
        assert baseline_tick.clamp_count == absorbing_tick.clamp_count


def test_one_write_places_new_symbol_at_age_zero_without_old_age_six_wrap() -> None:
    field = controller()
    state = field.new_state(dtype=torch.float64)
    width = field.config.wave_mode_count
    phase = field._constants(state)["channel_phase"]
    white = field._constants(state)["white"]
    codebook_parts = field.codebook(0, dtype=torch.float64)
    codebook = torch.complex(
        codebook_parts[..., 0], codebook_parts[..., 1]
    )
    old_zero = codebook[37]
    old_six = codebook[74]
    differential = torch.zeros(
        (CHANNELS, width, 1), dtype=torch.complex128
    )
    differential += (
        phase[:, None, None]
        * old_zero[None, :, None]
        * 0.07
        / math.sqrt(CHANNELS)
    )
    differential += (
        old_six[None, :, None] * 0.09 / math.sqrt(CHANNELS)
    )
    common = white[:, None, None] * (0.02 + 0.0j)
    zero = torch.zeros_like(differential)
    state = field._replace_coordinates(
        state, common, differential, zero, zero
    )
    written, _, _ = field._modulate_unchecked(state, (181,), 1.0)
    coefficients = dft(field, field._active_coordinates(written)[1])
    scores = (
        torch.einsum(
            "aw,hwb->hba", codebook.conj(), coefficients
        )
        / width
    ).abs().square()
    assert int(torch.argmax(scores[1, 0]).item()) == 181
    assert int(torch.argmax(scores[2, 0]).item()) == 37
    assert torch.allclose(
        coefficients[0],
        torch.zeros_like(coefficients[0]),
        rtol=0.0,
        atol=2.0e-12,
    )


def test_save_reload_profile_rejects_harmonic_age_controller(tmp_path: Path) -> None:
    field = controller()
    state = populated_state(field)
    payload = {
        "field": state.field.detach().clone(),
        "layout_profile_id": ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID,
        "operator_profile_id": ABSORBING_HARMONIC_AGE_OPERATOR_PROFILE_ID,
        "projection_profile_id": ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID,
        "config_fingerprint": field.config_fingerprint,
    }
    path = tmp_path / "l47.pt"
    torch.save(payload, path)
    loaded = torch.load(path, weights_only=True)
    assert torch.equal(loaded["field"], payload["field"])

    baseline = HarmonicAgeFieldController(HarmonicAgeFieldConfig(mode_count=MODE_COUNT))
    assert loaded["layout_profile_id"] == ABSORBING_HARMONIC_AGE_LAYOUT_PROFILE_ID
    assert loaded["operator_profile_id"] == ABSORBING_HARMONIC_AGE_OPERATOR_PROFILE_ID
    assert loaded["projection_profile_id"] == ABSORBING_HARMONIC_AGE_PROJECTION_PROFILE_ID
    assert loaded["config_fingerprint"] != baseline.config_fingerprint


def test_write_calls_unchanged_givens_once_after_absorbing_shift() -> None:
    field = controller()
    state = populated_state(field)
    expected = WhiteChromaticFieldController._modulate_unchecked(
        field, field.absorb_harmonics(state), (37, 134), 1.0
    )
    actual = field._modulate_unchecked(state, (37, 134), 1.0)
    assert torch.equal(actual[0].field, expected[0].field)
    assert torch.equal(actual[1], expected[1])
    assert actual[2] == expected[2]


def test_absorbing_attractor_repairs_rolling_ordered_trajectory() -> None:
    ordered = OrderedRelationalChromaticFieldController(
        OrderedRelationalChromaticFieldConfig(mode_count=MODE_COUNT)
    )
    field = AbsorbingHarmonicAttractorFieldController(
        AbsorbingHarmonicAttractorFieldConfig(mode_count=MODE_COUNT)
    )
    assert (
        ABSORBING_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID
        == "cassi.qi-absorbing-harmonic-attractor.v1"
    )
    assert field.config_fingerprint != controller().config_fingerprint
    s0 = torch.tensor((0, 37, 74, 111, 148, 185, 222, 259))
    stages = (s0, (s0 + 97) % 260, (s0 + 181) % 260, (s0 + 97) % 260)
    state, _ = ordered.heartbeat(
        ordered.new_state(batch_size=8, dtype=torch.float64)
    )
    state = ordered.tick(state, symbols=stages[0], steps=8, trust=1.0).state
    for _ in range(16):
        state = ordered.tick(state, steps=8).state
    for current, predecessor in zip(stages[1:], stages[:-1]):
        state, drift, clamp_count = field._modulate_unchecked(
            state, current, 1.0
        )
        immediate = field.white_readout(state)
        assert torch.all(immediate.age_available[:, :2])
        assert torch.equal(immediate.age_symbols[:, 0], current)
        assert torch.equal(immediate.age_symbols[:, 1], predecessor)
        assert clamp_count == 0
        assert torch.all(drift.abs() <= 2.0e-12)
        for _ in range(16):
            state = field.tick(state, steps=8).state
        readout = field.white_readout(state)
        assert torch.all(readout.age_available[:, :2])
        assert torch.equal(readout.age_symbols[:, 0], current)
        assert torch.equal(readout.age_symbols[:, 1], predecessor)


def test_absorbing_attractor_retires_eighth_write_through_128_blanks() -> None:
    field = AbsorbingHarmonicAttractorFieldController(
        AbsorbingHarmonicAttractorFieldConfig(mode_count=MODE_COUNT)
    )
    state = field.new_state(batch_size=8, dtype=torch.float64)
    base = torch.tensor((0, 37, 74, 111, 148, 185, 222, 259))
    stages = tuple((base + 29 * step) % 260 for step in range(8))
    history: list[torch.Tensor] = []
    clamp_count = 0

    def require_history() -> None:
        readout = field.white_readout(state)
        depth = min(len(history), CHANNELS)
        expected = torch.stack(tuple(reversed(history[-depth:])), dim=1)
        assert torch.all(readout.age_available[:, :depth])
        assert torch.equal(readout.age_symbols[:, :depth], expected)

    for symbols in stages:
        tick = field.tick(state, symbols=symbols, steps=8)
        state = tick.state
        clamp_count += tick.clamp_count
        history.append(symbols)
        require_history()
        for _ in range(16):
            tick = field.tick(state, steps=8)
            state = tick.state
            clamp_count += tick.clamp_count
        require_history()

    readout = field.white_readout(state)
    assert not torch.any(
        readout.age_available
        & (readout.age_symbols == stages[0][:, None])
    )
    for _ in range(112):
        tick = field.tick(state, steps=8)
        state = tick.state
        clamp_count += tick.clamp_count
    require_history()
    assert clamp_count == 0
