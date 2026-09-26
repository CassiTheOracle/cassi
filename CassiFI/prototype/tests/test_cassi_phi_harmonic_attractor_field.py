"""Focused checks for the seven-pool phi-timescale successor field."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_absorbing_harmonic_attractor_field import (
    AbsorbingHarmonicAttractorFieldConfig,
)
from cassi_white_chromatic_field import WhiteChromaticFieldController
from cassi_phi_harmonic_attractor_field import (
    PHI_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID,
    PhiHarmonicAttractorFieldConfig,
    PhiHarmonicAttractorFieldController,
)
from cassi_prismatic_field import PHI
from cassi_qi_field import QiFieldError

MODE_COUNT = 520
SEQUENCE = (17, 83, 201, 83, 41, 59, 131, 223)
EXPECTED = tuple(reversed(SEQUENCE[-7:]))


def test_config_derives_exactly_seven_phi_pool_timescales() -> None:
    config = PhiHarmonicAttractorFieldConfig(mode_count=MODE_COUNT)
    expected = tuple(PHI**index for index in range(7))
    assert config.bank_timescales == pytest.approx(expected, rel=1.0e-15)

    field = PhiHarmonicAttractorFieldController(config)
    constants = field._constants(field.new_state(dtype=torch.float64))
    first_mode = torch.tensor(expected, dtype=torch.float64)
    torch.testing.assert_close(
        constants["timescale"][:, 0, 0], first_mode, rtol=1.0e-15, atol=0.0
    )
    torch.testing.assert_close(
        constants["timescale"][:, -1, 0], first_mode * PHI**6, rtol=1.0e-15, atol=0.0
    )
    timescale = constants["timescale"][:, :, 0]
    torch.testing.assert_close(
        timescale[1:] / timescale[:-1],
        torch.full_like(timescale[1:], PHI),
        rtol=1.0e-14,
        atol=0.0,
    )
    torch.testing.assert_close(
        timescale[:, 1:] / timescale[:, :-1],
        torch.full_like(
            timescale[:, 1:], PHI ** (6 / (config.wave_mode_count - 1))
        ),
        rtol=1.0e-14,
        atol=0.0,
    )
    assert field.config_fingerprint == config.fingerprint
    assert config.fingerprint != AbsorbingHarmonicAttractorFieldConfig(
        mode_count=MODE_COUNT
    ).fingerprint
    assert PHI_HARMONIC_ATTRACTOR_OPERATOR_PROFILE_ID == (
        "cassi.qi-phi-harmonic-attractor.v1"
    )


@pytest.mark.parametrize("root_timescale", (True, 0.0, -1.0, math.inf, math.nan))
def test_config_rejects_invalid_root_timescale(root_timescale: object) -> None:
    with pytest.raises(QiFieldError, match="root_timescale"):
        PhiHarmonicAttractorFieldConfig(
            mode_count=MODE_COUNT,
            root_timescale=root_timescale,  # type: ignore[arg-type]
        )


def test_coupling_is_symmetric_and_native_age_order_stays_bounded() -> None:
    torch.set_num_threads(1)
    field = PhiHarmonicAttractorFieldController(
        PhiHarmonicAttractorFieldConfig(mode_count=MODE_COUNT)
    )
    state = field.new_state(dtype=torch.float64)
    clamp_count = 0
    for symbol in SEQUENCE:
        tick = field.tick(state, symbols=(symbol,), steps=8)
        state = tick.state
        clamp_count += tick.clamp_count

    peak_energy = 0.0
    for _ in range(256):
        tick = field.tick(state, steps=8)
        state = tick.state
        clamp_count += tick.clamp_count
        peak_energy = max(
            peak_energy, float(field._dynamic_energy_unchecked(state).max().item())
        )

    readout = field.white_readout(state)
    assert tuple(int(value) for value in readout.age_symbols[0, :7]) == EXPECTED
    assert bool(readout.age_available[0, :7].all().item())
    assert clamp_count == 0
    assert torch.isfinite(state.field).all()
    assert state.field.abs().max().item() < field.config.max_mode_amplitude
    assert peak_energy < field.config.max_mean_energy

    constants = field._constants(state)
    generator = torch.Generator().manual_seed(7)
    position = torch.complex(
        torch.randn(7, field.config.wave_mode_count, 1, generator=generator),
        torch.randn(7, field.config.wave_mode_count, 1, generator=generator),
    ).to(dtype=torch.complex128)
    force = field._coupling_force(position, constants["edge_weight"])
    assert force.sum(dim=0).abs().max().item() <= 1.0e-12


def test_linear_operator_is_stable_and_phase_equivariant() -> None:
    field = PhiHarmonicAttractorFieldController(
        PhiHarmonicAttractorFieldConfig(mode_count=MODE_COUNT)
    )
    empty = field.new_state(dtype=torch.float64)
    constants = field._constants(empty)
    identity = torch.eye(7, dtype=torch.float64)
    max_radius = 0.0
    for mode in range(field.config.wave_mode_count):
        stiffness = torch.diag(constants["omega2"][:, mode, 0].clone())
        edge = constants["edge_weight"][:, mode, 0]
        index = torch.arange(6)
        stiffness[index, index] += edge
        stiffness[index + 1, index + 1] += edge
        stiffness[index, index + 1] -= edge
        stiffness[index + 1, index] -= edge
        damping = torch.diag(constants["damping_decay"][:, mode, 0])
        transition = torch.cat(
            (
                torch.cat(
                    (
                        identity - field.config.dt**2 * stiffness,
                        field.config.dt * damping,
                    ),
                    dim=1,
                ),
                torch.cat((-field.config.dt * stiffness, damping), dim=1),
            ),
            dim=0,
        )
        max_radius = max(
            max_radius,
            float(torch.linalg.eigvals(transition).abs().max().item()),
        )
    assert max_radius < 1.0

    generator = torch.Generator().manual_seed(11)
    width = field.config.wave_mode_count

    def random_coordinate() -> torch.Tensor:
        return torch.complex(
            torch.randn(7, width, 1, generator=generator, dtype=torch.float64),
            torch.randn(7, width, 1, generator=generator, dtype=torch.float64),
        ) * 0.01

    common = random_coordinate()
    differential = random_coordinate()
    common_velocity = random_coordinate()
    differential_velocity = random_coordinate()
    epsilon = torch.rand(
        7, width, 1, generator=generator, dtype=torch.float64
    ) * 0.01
    state = field._replace_coordinates(
        empty,
        common,
        differential,
        common_velocity,
        differential_velocity,
        epsilon=epsilon,
    )
    phase = torch.polar(
        torch.tensor(1.0, dtype=torch.float64),
        torch.tensor(0.731, dtype=torch.float64),
    )
    rotated = field._replace_coordinates(
        empty,
        common * phase,
        differential * phase,
        common_velocity * phase,
        differential_velocity * phase,
        epsilon=epsilon,
    )
    evolved, _ = WhiteChromaticFieldController._evolve_unchecked(field, state, 1)
    evolved_rotated, _ = WhiteChromaticFieldController._evolve_unchecked(
        field, rotated, 1
    )
    coordinates = field._active_coordinates(evolved)
    rotated_coordinates = field._active_coordinates(evolved_rotated)
    for expected, actual in zip(coordinates, rotated_coordinates):
        torch.testing.assert_close(actual, expected * phase, rtol=1.0e-12, atol=1.0e-12)
    assert field._hamiltonian_unchecked(state).item() == pytest.approx(
        field._hamiltonian_unchecked(rotated).item(), rel=1.0e-15
    )
