"""Focused CPU contracts for the frozen L30 white-chromatic field."""

from __future__ import annotations

import math
from pathlib import Path
import sys

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_qi_field import QiFieldError, QiFieldState
from cassi_white_chromatic_field import (
    WHITE_CHROMATIC_CHANNEL_NAMES,
    WHITE_CHROMATIC_LAYOUT_PROFILE_ID,
    WHITE_CHROMATIC_OPERATOR_PROFILE_ID,
    WHITE_CHROMATIC_PROJECTION_PROFILE_ID,
    PsychedelicProjection,
    WhiteChromaticFieldConfig,
    WhiteChromaticFieldController,
)

PHI = (1.0 + math.sqrt(5.0)) / 2.0
CHANNELS = 7
MODE_COUNT = 520
WIDTH = MODE_COUNT // 2
DENOMINATOR = 1.0 + PHI * PHI


def controller() -> WhiteChromaticFieldController:
    return WhiteChromaticFieldController(WhiteChromaticFieldConfig(mode_count=MODE_COUNT))


def packed(state: QiFieldState, mode_count: int = MODE_COUNT) -> torch.Tensor:
    return state.field.reshape(CHANNELS, 9, mode_count, state.field.shape[2])


def differential(state: QiFieldState) -> torch.Tensor:
    values = packed(state)
    y = torch.complex(values[:, 0, :WIDTH], values[:, 1, :WIDTH])
    i = torch.complex(values[:, 2, :WIDTH], values[:, 3, :WIDTH])
    return y - PHI * i




def write_coordinates(
    state: QiFieldState,
    *,
    differential_value: torch.Tensor,
    common_value: torch.Tensor | None = None,
) -> None:
    """Write frozen C/D coordinates into the public nine-plane state layout."""
    if not differential_value.is_complex():
        differential_value = torch.complex(
            differential_value, torch.zeros_like(differential_value)
        )
    if common_value is not None and not common_value.is_complex():
        common_value = torch.complex(common_value, torch.zeros_like(common_value))
    if common_value is None:
        common_value = torch.zeros_like(differential_value)
    values = packed(state)
    y = (differential_value + PHI * common_value) / DENOMINATOR
    i = (common_value - PHI * differential_value) / DENOMINATOR
    values[:, 0, :WIDTH] = y.real
    values[:, 1, :WIDTH] = y.imag
    values[:, 2, :WIDTH] = i.real
    values[:, 3, :WIDTH] = i.imag


def channel_dynamic_energy(state: QiFieldState) -> torch.Tensor:
    values = packed(state)
    y = torch.complex(values[:, 0, :WIDTH], values[:, 1, :WIDTH])
    i = torch.complex(values[:, 2, :WIDTH], values[:, 3, :WIDTH])
    vy = torch.complex(values[:, 4, :WIDTH], values[:, 5, :WIDTH])
    vi = torch.complex(values[:, 6, :WIDTH], values[:, 7, :WIDTH])
    c, d = PHI * y + i, y - PHI * i
    vc, vd = PHI * vy + vi, vy - PHI * vi
    return (c.abs().square() + d.abs().square() + vc.abs().square() + vd.abs().square()).mean(dim=1) / DENOMINATOR


def test_first_heartbeat_is_equal_white_carrier_and_zero_differential() -> None:
    field = controller()
    source = field.new_state(dtype=torch.float64)
    result, receipt = field.heartbeat(source)

    assert torch.equal(source.field, torch.zeros_like(source.field))
    assert field.carrier_energy(result).reshape(-1).item() == pytest.approx(0.5, abs=1e-12)
    assert field.dynamic_energy(result).reshape(-1).item() == pytest.approx(0.5, abs=1e-12)
    energies = channel_dynamic_energy(result)
    assert torch.max(torch.abs(energies - energies.mean())).item() <= 1e-12
    assert torch.max(torch.abs(differential(result))).item() <= 1e-12
    assert receipt.clamp_count == 0


def test_heartbeat_caps_overfull_complement_without_exceeding_budget() -> None:
    field = controller()
    source = field.new_state(dtype=torch.float64)
    values = torch.linspace(1.0, 2.0, WIDTH, dtype=torch.float64).reshape(1, WIDTH, 1)
    write_coordinates(source, differential_value=values.expand(CHANNELS, -1, -1).clone())
    before = source.field.clone()

    result, receipt = field.heartbeat(source)

    assert torch.equal(source.field, before)
    assert field.carrier_energy(result).reshape(-1).item() == pytest.approx(0.5, abs=1e-12)
    assert field.dynamic_energy(result).reshape(-1).item() <= 1.0 + 1e-12
    assert receipt.clamp_count == 0


def test_all_zero_input_modulation_is_an_exact_identity() -> None:
    field = controller()
    source = field.new_state(dtype=torch.float64)
    result, drift = field.modulate_symbols(source, (37,), source_trust=1.0)

    assert torch.equal(result.field, source.field)
    assert torch.equal(drift, torch.zeros_like(drift))


def test_whole_prism_modulation_is_unitary_and_immediately_readable() -> None:
    field = controller()
    source = field.new_state(dtype=torch.float64)
    carrier, _ = field.heartbeat(source)
    before = field.dynamic_energy(carrier).clone()
    carrier_bytes = carrier.field.clone()

    result, drift = field.modulate_symbols(carrier, (37,), source_trust=1.0)
    readout = field.white_readout(result)

    assert torch.equal(carrier.field, carrier_bytes)
    assert field.dynamic_energy(result).reshape(-1).item() == pytest.approx(
        before.reshape(-1).item(), rel=1e-11, abs=1e-12
    )
    assert torch.max(torch.abs(drift)).item() <= 1e-11
    assert field.carrier_energy(result).reshape(-1).item() <= 1e-11
    assert bool(readout.available.reshape(-1)[0].item())
    assert readout.symbols.reshape(-1).item() == 37


def test_shared_per_mode_timescales_are_shared_across_channels() -> None:
    field = controller()
    state = field.new_state(dtype=torch.float64)
    values = torch.zeros(CHANNELS, WIDTH, 1, dtype=torch.complex128)
    values[:, 0, 0] = 0.2 + 0.1j
    values[:, -1, 0] = 0.2 + 0.1j
    write_coordinates(state, differential_value=values)

    evolved = field.evolve(state, steps=1)
    result = differential(evolved)

    assert torch.allclose(result, result[0:1], rtol=1e-11, atol=1e-12)
    assert not torch.allclose(result[:, 0], result[:, -1], rtol=1e-8, atol=1e-10)


def test_readout_has_no_crown_or_violet_availability_gate() -> None:
    field = controller()
    carrier, _ = field.heartbeat(field.new_state(dtype=torch.float64))
    modulated, _ = field.modulate_symbols(carrier, (74,), source_trust=1.0)
    two_channels = QiFieldState(modulated.field.clone())
    packed(two_channels)[2:] = 0.0

    readout = field.white_readout(two_channels)

    assert bool(readout.available.reshape(-1)[0].item())
    assert readout.active_channel_count.reshape(-1).item() >= 2


def test_fixed_channel_phase_compensation_recovers_coherent_symbol() -> None:
    field = controller()
    carrier, _ = field.heartbeat(field.new_state(dtype=torch.float64))
    state, _ = field.modulate_symbols(carrier, (148,), source_trust=1.0)
    readout = field.white_readout(state)

    assert readout.symbols.reshape(-1).item() == 148
    assert readout.white_coherence.reshape(-1).item() == pytest.approx(1.0, abs=1e-10)


def test_projection_is_bounded_deterministic_input_dependent_and_read_only() -> None:
    field = controller()

    def projected(symbol: int) -> PsychedelicProjection:
        carrier, _ = field.heartbeat(field.new_state(dtype=torch.float64))
        state, _ = field.modulate_symbols(carrier, (symbol,), source_trust=1.0)
        before = state.field.clone()
        image = field.psychedelic_projection(state, max_side=16)
        assert torch.equal(state.field, before)
        return image

    first = projected(0)
    repeated = projected(0)
    counterfactual = projected(37)

    assert first.side == repeated.side == counterfactual.side == 16
    assert torch.equal(first.rgb, repeated.rgb)
    assert torch.equal(first.common_intensity, repeated.common_intensity)
    assert torch.equal(first.channel_intensity, repeated.channel_intensity)
    assert torch.isfinite(first.rgb).all()
    assert float(first.rgb.min().item()) >= 0.0
    assert float(first.rgb.max().item()) <= 1.0
    assert first.rgb.numel() > 0
    assert first.channel_intensity.numel() > 0
    assert torch.mean((first.rgb - counterfactual.rgb).square()).sqrt().item() > 1e-4


def test_public_operations_leave_input_state_byte_identical() -> None:
    field = controller()
    operations = (
        lambda state: field.heartbeat(state),
        lambda state: field.modulate_symbols(state, (0,)),
        lambda state: field.evolve(state, steps=1),
        lambda state: field.white_readout(state),
        lambda state: field.psychedelic_projection(state, max_side=16),
        lambda state: field.tick(state, steps=1),
    )
    for operation in operations:
        state = field.new_state(dtype=torch.float64)
        before = state.field.clone()
        operation(state)
        assert torch.equal(state.field, before)


def test_repeated_ticks_remain_finite_bounded_and_differentially_blank() -> None:
    field = controller()
    state = field.new_state(dtype=torch.float64)

    for _ in range(24):
        tick = field.tick(state, steps=2)
        state = tick.state
        assert torch.isfinite(state.field).all()
        assert tick.clamp_count == 0
        assert tick.injected_energy.reshape(-1).numel() == 1
        assert field.dynamic_energy(state).reshape(-1).item() <= 1.05 + 1e-10
        assert torch.max(torch.abs(differential(state))).item() <= 1e-10
        assert torch.count_nonzero(packed(state)[:, :, WIDTH:]) == 0


@pytest.mark.parametrize("mode_count", [0, -2, 519, 2, 520.0, True])
def test_malformed_configs_are_rejected(mode_count: object) -> None:
    with pytest.raises((QiFieldError, TypeError, ValueError)):
        WhiteChromaticFieldConfig(mode_count=mode_count)  # type: ignore[arg-type]


def test_malformed_states_inputs_and_projection_requests_are_rejected() -> None:
    field = controller()
    clean = field.new_state(dtype=torch.float64)

    with pytest.raises(QiFieldError):
        field.dynamic_energy(QiFieldState(torch.zeros(7, 9 * MODE_COUNT - 1, 1)))
    nonfinite = field.new_state(dtype=torch.float64)
    nonfinite.field[0, 0, 0] = math.nan
    with pytest.raises(QiFieldError, match="non-finite"):
        field.dynamic_energy(nonfinite)
    with pytest.raises(QiFieldError):
        field.heartbeat(object())  # type: ignore[arg-type]
    with pytest.raises(QiFieldError):
        field.modulate_symbols(clean, torch.tensor([37.0]))
    with pytest.raises(QiFieldError):
        field.modulate_symbols(clean, (MODE_COUNT,))
    with pytest.raises(QiFieldError, match="source_trust"):
        field.modulate_symbols(clean, (0,), source_trust=float("nan"))
    with pytest.raises(QiFieldError, match="source_trust"):
        field.modulate_symbols(clean, (0,), source_trust=1.01)
    with pytest.raises(QiFieldError):
        field.psychedelic_projection(clean, max_side=0)
    with pytest.raises(QiFieldError):
        field.psychedelic_projection(clean, max_side=1.5)  # type: ignore[arg-type]


def test_profile_identities_fingerprint_and_field_only_surface() -> None:
    field = controller()
    other = WhiteChromaticFieldController(WhiteChromaticFieldConfig(mode_count=522))

    assert WHITE_CHROMATIC_LAYOUT_PROFILE_ID == "cassi.qi-white-chromatic-shared-coordinate.v1"
    assert WHITE_CHROMATIC_OPERATOR_PROFILE_ID == "cassi.qi-white-chromatic-heartbeat.v1"
    assert WHITE_CHROMATIC_PROJECTION_PROFILE_ID == "cassi.qi-white-chromatic-projection.v1"
    assert WHITE_CHROMATIC_CHANNEL_NAMES == (
        "red", "orange", "yellow", "green", "blue", "indigo", "violet"
    )
    assert len(field.config_fingerprint) == 64
    assert field.config_fingerprint == field.config.fingerprint
    assert field.config_fingerprint != other.config_fingerprint
    assert len({
        WHITE_CHROMATIC_LAYOUT_PROFILE_ID,
        WHITE_CHROMATIC_OPERATOR_PROFILE_ID,
        WHITE_CHROMATIC_PROJECTION_PROFILE_ID,
    }) == 3
    for name in (
        "model",
        "optimizer",
        "checkpoint",
        "save",
        "load",
        "dump_state_bytes",
        "load_state_bytes",
    ):
        assert not hasattr(field, name)
    assert not hasattr(field, "learned_embedding")
    assert not hasattr(field, "parallel_policy")
