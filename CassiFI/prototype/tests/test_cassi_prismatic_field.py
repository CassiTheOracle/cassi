"""Focused CPU contracts for the side-by-side prismatic heartbeat field."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_prismatic_field import (
    PHI,
    PRISMATIC_LAYOUT_PROFILE_ID,
    PRISMATIC_OPERATOR_PROFILE_ID,
    PrismaticFieldConfig,
    PrismaticFieldController,
)
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldError
from verification.verify_l29_phi_prismatic_heartbeat import verify


def controller(bank_count: int = 7, mode_count: int = 520) -> PrismaticFieldController:
    return PrismaticFieldController(
        PrismaticFieldConfig(
            tuple(PHI**index for index in range(bank_count)), mode_count
        )
    )


def coordinates(field: PrismaticFieldController, state):
    return field._active_coordinates(state)


def differential_symbol_state(
    field: PrismaticFieldController, symbol: int, *, phase: complex = 1.0 + 0.0j
):
    state = field.new_state(dtype=torch.float64)
    packed = state.field.reshape(
        field.config.bank_count, 9, field.config.mode_count, 1
    )
    width = field.config.wave_mode_count
    code = field._codebook_source.codebook(0, dtype=torch.float64)[symbol]
    differential = phase * torch.complex(code[:, 0], code[:, 1])
    denominator = 1.0 + PHI * PHI
    packed[:, 0, :width, 0] = differential.real / denominator
    packed[:, 1, :width, 0] = differential.imag / denominator
    packed[:, 2, :width, 0] = -PHI * differential.real / denominator
    packed[:, 3, :width, 0] = -PHI * differential.imag / denominator
    return state


def test_heartbeat_seeds_only_central_common_energy() -> None:
    field = controller()
    state, receipt = field.heartbeat(field.new_state(dtype=torch.float64))
    common, differential, common_velocity, differential_velocity = coordinates(
        field, state
    )
    energy = field.dynamic_energy(state)[:, 0]

    assert receipt.source_weights.tolist() == [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    assert receipt.source_energy_before.item() == 0.0
    assert receipt.source_energy_after.item() == pytest.approx(1.0, abs=1.0e-12)
    assert receipt.injected_energy.item() == pytest.approx(1.0, abs=1.0e-12)
    assert energy[3].item() == pytest.approx(1.0, abs=1.0e-12)
    assert torch.count_nonzero(torch.cat((energy[:3], energy[4:]))) == 0
    assert torch.max(torch.abs(differential)).item() <= 1.0e-15
    assert torch.count_nonzero(common_velocity) == 0
    assert torch.count_nonzero(differential_velocity) == 0
    assert torch.count_nonzero(common[[0, 1, 2, 4, 5, 6]]) == 0
    assert receipt.clamp_count == 0

    even = controller(bank_count=4)
    _, even_receipt = even.heartbeat(even.new_state(dtype=torch.float64))
    assert even_receipt.source_weights.tolist() == [0.0, 0.5, 0.5, 0.0]
    assert even_receipt.source_energy_after.item() == pytest.approx(1.0, abs=1.0e-12)


def test_unitary_symbol_modulation_preserves_energy_and_sets_phase() -> None:
    field = controller()
    state = field.new_state(dtype=torch.float64)
    packed = state.field.reshape(7, 9, 520, 1)
    width = field.config.wave_mode_count
    denominator = 1.0 + PHI * PHI
    packed[0, 0, :width, 0] = PHI / denominator
    packed[0, 2, :width, 0] = 1.0 / denominator
    before = field.dynamic_energy(state)[0, 0]

    result, drift = field.modulate_symbols(state, (37,))
    common, differential, _, _ = coordinates(field, result)
    code = field._codebook_source.codebook(0, dtype=torch.float64)[37]
    expected = torch.complex(code[:, 0], code[:, 1])

    assert abs(drift.item()) <= 1.0e-10
    assert field.dynamic_energy(result)[0, 0].item() == pytest.approx(
        before.item(), rel=1.0e-12, abs=1.0e-12
    )
    assert torch.max(torch.abs(differential[0, :, 0] - expected)).item() <= 1.0e-12
    assert torch.max(torch.abs(common[0, :, 0])).item() <= 1.0e-12


def test_input_without_heartbeat_cannot_supply_energy() -> None:
    field = controller()
    state = field.new_state(batch_size=2, dtype=torch.float64)
    result, drift = field.modulate_symbols(state, (0, 259))

    assert torch.equal(result.field, state.field)
    assert torch.equal(drift, torch.zeros_like(drift))
    assert torch.count_nonzero(field.dynamic_energy(result)) == 0


def test_heartbeat_evolution_stays_differentially_blank_and_propagates() -> None:
    field = controller()
    tick = field.tick(field.new_state(dtype=torch.float64), steps=32)
    _, differential, _, differential_velocity = coordinates(field, tick.state)

    assert torch.max(torch.abs(differential)).item() <= 1.0e-12
    assert torch.max(torch.abs(differential_velocity)).item() <= 1.0e-12
    assert tick.bank_energy[0, 0].item() > 0.0
    assert tick.bank_energy[-1, 0].item() > 0.0
    assert tick.clamp_count == 0


def test_resource_matched_four_and_seven_bank_counts_are_equal() -> None:
    seven_banks, seven_modes = 7, 3512
    four_banks, four_modes = 4, 6146
    seven_state = seven_banks * 9 * seven_modes
    four_state = four_banks * 9 * four_modes
    seven_active = seven_banks * 8 * (seven_modes // 2)
    four_active = four_banks * 8 * (four_modes // 2)
    batch_weighted_ticks = 128 + 128 + 65 * 8

    assert seven_state == four_state == 221256
    assert seven_active == four_active == 98336
    assert (
        seven_active * 16 * batch_weighted_ticks
        == four_active * 16 * batch_weighted_ticks
    )


def test_white_readout_rewards_coherence_without_changing_energy() -> None:
    field = controller()
    state = differential_symbol_state(field, 37)
    energy_before = field.dynamic_energy(state).clone()
    coherent = field.white_readout(state)

    assert coherent.available.item()
    assert coherent.symbols.item() == 37
    assert coherent.white_coherence.item() == pytest.approx(1.0, abs=1.0e-12)

    packed = state.field.reshape(7, 9, 520, 1)
    denominator = 1.0 + PHI * PHI
    code = field._codebook_source.codebook(0, dtype=torch.float64)[37]
    scrambled = 1j * torch.complex(code[:, 0], code[:, 1])
    packed[0, 0, :260, 0] = scrambled.real / denominator
    packed[0, 1, :260, 0] = scrambled.imag / denominator
    packed[0, 2, :260, 0] = -PHI * scrambled.real / denominator
    packed[0, 3, :260, 0] = -PHI * scrambled.imag / denominator
    incoherent = field.white_readout(state)

    assert incoherent.symbols.item() == 37
    assert incoherent.white_coherence.item() < coherent.white_coherence.item()
    assert incoherent.white_coherence.item() == pytest.approx(37.0 / 49.0, abs=1.0e-12)
    assert torch.equal(field.dynamic_energy(state), energy_before)


@pytest.mark.parametrize(
    "arguments",
    [
        {"bank_timescales": (1.0,), "mode_count": 520},
        {"bank_timescales": (1.0, math.inf), "mode_count": 520},
        {"bank_timescales": (1.0, 2.0), "mode_count": 519},
        {"bank_timescales": (1.0, 2.0), "mode_count": 518},
        {"bank_timescales": (1.0, 2.0), "mode_count": 520, "dt": 0.11},
        {
            "bank_timescales": (1.0, 2.0),
            "mode_count": 520,
            "epsilon_tau": 1.01,
        },
    ],
)
def test_malformed_configs_are_rejected(arguments: dict) -> None:
    with pytest.raises(QiFieldError):
        PrismaticFieldConfig(**arguments)


def test_nonfinite_inputs_and_checkpoint_surfaces_are_rejected() -> None:
    field = controller()
    state = field.new_state(dtype=torch.float64)
    state.field[0, 0, 0] = math.nan
    with pytest.raises(QiFieldError, match="non-finite"):
        field.dynamic_energy(state)

    clean = field.new_state(dtype=torch.float64)
    with pytest.raises(QiFieldError, match="source_trust"):
        field.modulate_symbols(clean, (0,), source_trust=float("nan"))
    with pytest.raises(QiFieldError, match="source_trust"):
        field.modulate_symbols(clean, (0,), source_trust=1.01)
    with pytest.raises(QiFieldError, match="integer dtype"):
        field.modulate_symbols(clean, torch.tensor([0.0]))
    with pytest.raises(QiFieldError):
        field.heartbeat(b"not a QiFieldState")  # type: ignore[arg-type]

    canonical = QiFieldController(QiFieldConfig(mode_count=520))
    checkpoint = canonical.dump_state_bytes(canonical.initial_state(1))
    assert isinstance(checkpoint, bytes)
    for name in (
        "dump_state_bytes",
        "load_state_bytes",
        "save",
        "load",
    ):
        assert not hasattr(field, name)


def test_identity_binds_profiles_and_shared_codebook() -> None:
    field = controller()

    assert len(field.config_fingerprint) == 64
    assert field.config_fingerprint == field.config.fingerprint
    assert PRISMATIC_LAYOUT_PROFILE_ID == "cassi.qi-prismatic-shared-coordinate.v1"
    assert PRISMATIC_OPERATOR_PROFILE_ID == "cassi.qi-prismatic-heartbeat.v1"


def test_hardware_aborted_board_remains_incomplete(tmp_path: Path) -> None:
    source_paths = (
        "designs/L29-PHI-PRISMATIC-HEARTBEAT-PREREG.md",
        "cassi_prismatic_field.py",
        "verification/run_l29_phi_prismatic_heartbeat.py",
        "verification/verify_l29_phi_prismatic_heartbeat.py",
    )
    source_hashes = {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in source_paths
    }
    reason = "AcceleratorError: device kernel image is invalid"
    board = {
        "schema_id": "cassi.l29.phi-prismatic-heartbeat-board.v1",
        "status": "INCOMPLETE",
        "layout_profile_id": PRISMATIC_LAYOUT_PROFILE_ID,
        "operator_profile_id": PRISMATIC_OPERATOR_PROFILE_ID,
        "trace_schema_id": "cassi.l29.phi-prismatic-heartbeat-traces.v1",
        "preregistration_sha256": source_hashes[
            "designs/L29-PHI-PRISMATIC-HEARTBEAT-PREREG.md"
        ],
        "source_sha256": source_hashes,
        "device": {
            "requested": "cuda",
            "type": "cuda",
            "name": "AMD Radeon RX 7900 XTX",
            "torch_version": "test",
            "hip_version": "test",
            "dtype": "torch.float32",
        },
        "constants": {
            "phi": PHI,
            "targets": [0, 37, 74, 111, 148, 185, 222, 259],
            "distractors": [97, 134, 171, 208, 245, 22, 59, 96],
            "read_ticks": [0, 1, 2, 4, 8, 16, 32, 64],
            "long_horizon_ticks": [16, 32, 64],
            "warm_ticks": 128,
            "beating_ticks": 128,
            "task_ticks": 65,
            "evolution_steps": 16,
        },
        "trace": {"path": "l29-traces.npz", "sha256": None},
        "arms": {},
        "error": reason,
    }
    board_path = tmp_path / "l29-board.json"
    board_path.write_text(
        json.dumps(
            board,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "report.md"
    verdict, payload = verify(
        board_path, report_path, tmp_path / "verification.json"
    )

    assert verdict == "INCOMPLETE"
    assert payload["failures"] == []
    assert payload["incomplete_reason"] == reason
    report = report_path.read_text(encoding="utf-8")
    assert "## Verdict: INCOMPLETE" in report
    assert "## Verdict: FAIL" not in report
