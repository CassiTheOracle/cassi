"""Focused CPU contracts for the frozen L37 incoherent recall."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_cyclic_chromatic_field import (
    CyclicChromaticFieldConfig,
    CyclicChromaticFieldController,
)
from cassi_incoherent_chromatic_field import (
    INCOHERENT_CHROMATIC_LAYOUT_PROFILE_ID,
    INCOHERENT_CHROMATIC_OPERATOR_PROFILE_ID,
    INCOHERENT_CHROMATIC_PROJECTION_PROFILE_ID,
    IncoherentChromaticFieldConfig,
    IncoherentChromaticFieldController,
)
from cassi_qi_field import QiFieldState

CHANNELS = 7
MODE_COUNT = 520


def controllers() -> tuple[
    CyclicChromaticFieldController, IncoherentChromaticFieldController
]:
    return (
        CyclicChromaticFieldController(
            CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
        IncoherentChromaticFieldController(
            IncoherentChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
    )


def test_l37_changes_readout_but_not_l31_state_dynamics() -> None:
    cyclic, incoherent = controllers()
    cyclic_state = cyclic.new_state(batch_size=2, dtype=torch.float64)
    incoherent_state = incoherent.new_state(batch_size=2, dtype=torch.float64)
    schedule: tuple[tuple[int, int] | None, ...] = (
        (37, 74),
        None,
        (134, 171),
        None,
        None,
    )

    for symbols in schedule:
        cyclic_tick = cyclic.tick(cyclic_state, symbols=symbols, steps=8)
        incoherent_tick = incoherent.tick(
            incoherent_state, symbols=symbols, steps=8
        )
        cyclic_state = cyclic_tick.state
        incoherent_state = incoherent_tick.state
        assert torch.equal(cyclic_state.field, incoherent_state.field)
        assert torch.equal(cyclic_tick.hamiltonian, incoherent_tick.hamiltonian)
        assert torch.equal(
            cyclic_tick.input_energy_drift, incoherent_tick.input_energy_drift
        )
        assert cyclic_tick.clamp_count == incoherent_tick.clamp_count

    assert torch.equal(
        cyclic.psychedelic_projection(cyclic_state, max_side=16).rgb,
        incoherent.psychedelic_projection(incoherent_state, max_side=16).rgb,
    )


def test_scores_are_exact_mean_channel_codebook_energy() -> None:
    _, field = controllers()
    state, _ = field.heartbeat(field.new_state(batch_size=2, dtype=torch.float64))
    state, _ = field.modulate_symbols(state, (37, 148), trust=1.0)
    state = field.evolve(state, steps=11)
    before = state.field.clone()

    readout = field.white_readout(state)

    assert torch.equal(state.field, before)
    assert torch.equal(readout.scores, readout.bank_scores.mean(dim=0))


def test_channel_dephasing_preserves_incoherent_symbol_rank() -> None:
    cyclic, field = controllers()
    state = field.new_state(dtype=torch.float64)
    width = field.config.wave_mode_count
    phase_parts = field.codebook(0, dtype=torch.float64)[37]
    symbol_phase = torch.complex(phase_parts[:, 0], phase_parts[:, 1])
    channel = field._constants(state)["channel_phase"]
    angle = 2.0 * math.pi * torch.arange(CHANNELS, dtype=torch.float64) / CHANNELS
    dephasing = torch.complex(torch.cos(angle), torch.sin(angle))
    differential = (
        channel[:, None, None]
        * dephasing[:, None, None]
        * symbol_phase[None, :, None]
        / math.sqrt(CHANNELS)
    )
    zero = torch.zeros((CHANNELS, width, 1), dtype=torch.complex128)
    candidate = field._replace_coordinates(
        state, zero, differential, zero, zero
    )

    incoherent = field.white_readout(candidate)
    coherent = cyclic.white_readout(QiFieldState(candidate.field.clone()))

    assert incoherent.available.item()
    assert incoherent.symbols.item() == 37
    assert incoherent.scores[0, 37].item() > 0.1
    assert coherent.scores[0, 37].item() < 1.0e-24
    assert incoherent.white_coherence.item() < 1.0e-24


def test_blank_is_unavailable_with_exactly_zero_scores() -> None:
    field = controllers()[1]
    readout = field.white_readout(field.new_state(dtype=torch.float32))

    assert not readout.available.item()
    assert torch.count_nonzero(readout.scores) == 0
    assert torch.count_nonzero(readout.bank_scores) == 0
    assert readout.white_coherence.item() == 0.0


def test_l37_profile_is_distinct_without_adaptive_state() -> None:
    cyclic, field = controllers()

    assert (
        INCOHERENT_CHROMATIC_LAYOUT_PROFILE_ID
        == "cassi.qi-cyclic-chromatic-coordinate-native.v1"
    )
    assert (
        INCOHERENT_CHROMATIC_OPERATOR_PROFILE_ID
        == "cassi.qi-incoherent-chromatic-recall.v1"
    )
    assert (
        INCOHERENT_CHROMATIC_PROJECTION_PROFILE_ID
        == "cassi.qi-cyclic-chromatic-projection.v1"
    )
    assert field.config_fingerprint != cyclic.config_fingerprint
    for name in (
        "model",
        "optimizer",
        "memory_table",
        "history",
        "time_counter",
        "learned_embedding",
    ):
        assert not hasattr(field, name)
