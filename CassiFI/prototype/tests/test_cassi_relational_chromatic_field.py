"""Focused CPU contracts for the frozen L38 relational recall."""

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
from cassi_qi_field import QiFieldState
from cassi_relational_chromatic_field import (
    RELATIONAL_CHROMATIC_LAYOUT_PROFILE_ID,
    RELATIONAL_CHROMATIC_OPERATOR_PROFILE_ID,
    RELATIONAL_CHROMATIC_PROJECTION_PROFILE_ID,
    RelationalChromaticFieldConfig,
    RelationalChromaticFieldController,
)

CHANNELS = 7
MODE_COUNT = 520


def controllers() -> tuple[
    CyclicChromaticFieldController, RelationalChromaticFieldController
]:
    return (
        CyclicChromaticFieldController(
            CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
        RelationalChromaticFieldController(
            RelationalChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
    )


def test_l38_changes_readout_but_not_l31_state_dynamics() -> None:
    cyclic, relational = controllers()
    cyclic_state = cyclic.new_state(batch_size=2, dtype=torch.float64)
    relational_state = relational.new_state(batch_size=2, dtype=torch.float64)

    for symbols in ((37, 74), None, (134, 171), None, None):
        cyclic_tick = cyclic.tick(cyclic_state, symbols=symbols, steps=8)
        relational_tick = relational.tick(
            relational_state, symbols=symbols, steps=8
        )
        cyclic_state = cyclic_tick.state
        relational_state = relational_tick.state
        assert torch.equal(cyclic_state.field, relational_state.field)
        assert torch.equal(cyclic_tick.hamiltonian, relational_tick.hamiltonian)
        assert torch.equal(
            cyclic_tick.input_energy_drift, relational_tick.input_energy_drift
        )
        assert cyclic_tick.clamp_count == relational_tick.clamp_count

    assert torch.equal(
        cyclic.psychedelic_projection(cyclic_state, max_side=16).rgb,
        relational.psychedelic_projection(relational_state, max_side=16).rgb,
    )


def test_scores_equal_direct_common_differential_recomputation() -> None:
    cyclic, field = controllers()
    state, _ = field.heartbeat(field.new_state(batch_size=2, dtype=torch.float64))
    state, _ = field.modulate_symbols(state, (37, 148), trust=1.0)
    state = field.evolve(state, steps=7)
    state, _ = field.modulate_symbols(state, (134, 245), trust=1.0)
    before = state.field.clone()

    readout = field.white_readout(state)
    base = cyclic.white_readout(QiFieldState(state.field.clone()))
    phase_parts = field.codebook(0, dtype=torch.float64)
    codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
    coefficient = torch.einsum(
        "aw,wb->ab", codebook.conj(), field.relational_trace(state)
    ) / float(field.config.wave_mode_count)
    expected = base.scores + coefficient.abs().square().transpose(0, 1)

    assert torch.equal(state.field, before)
    assert torch.equal(readout.scores, expected)


def test_exact_rotated_pair_exposes_old_and_new_symbols() -> None:
    cyclic, field = controllers()
    state = field.new_state(dtype=torch.float64)
    phase_parts = field.codebook(0, dtype=torch.float64)
    codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
    old_symbol = 37
    new_symbol = 134
    old_phase = codebook[old_symbol]
    new_phase = codebook[new_symbol]
    constants = field._constants(state)
    common_trace = -new_phase.conj() * old_phase
    common = constants["white"][:, None, None] * common_trace[None, :, None]
    differential = (
        constants["channel_phase"][:, None, None]
        * new_phase[None, :, None]
        / math.sqrt(CHANNELS)
    )
    zero = torch.zeros_like(common)
    candidate = field._replace_coordinates(
        state, common, differential, zero, zero
    )

    relational = field.white_readout(candidate)
    coherent = cyclic.white_readout(QiFieldState(candidate.field.clone()))
    top_two = set(torch.topk(relational.scores[0], 2).indices.tolist())

    assert top_two == {old_symbol, new_symbol}
    assert relational.scores[0, old_symbol].item() > 0.9
    assert relational.scores[0, new_symbol].item() > 0.9
    assert coherent.symbols.item() == new_symbol
    assert coherent.scores[0, old_symbol].item() < 0.05


def test_first_deposit_and_blank_preserve_l31_scores() -> None:
    cyclic, field = controllers()
    cyclic_state, _ = cyclic.heartbeat(cyclic.new_state(dtype=torch.float64))
    relational_state, _ = field.heartbeat(field.new_state(dtype=torch.float64))
    cyclic_state, _ = cyclic.modulate_symbols(cyclic_state, (148,), trust=1.0)
    relational_state, _ = field.modulate_symbols(
        relational_state, (148,), trust=1.0
    )

    assert field.relational_trace(relational_state).abs().max().item() < 3.0e-15
    assert torch.equal(
        cyclic.white_readout(cyclic_state).scores,
        field.white_readout(relational_state).scores,
    )
    blank = field.white_readout(field.new_state(dtype=torch.float32))
    assert not blank.available.item()
    assert torch.count_nonzero(blank.scores) == 0


def test_l38_profile_is_distinct_without_adaptive_state() -> None:
    cyclic, field = controllers()

    assert (
        RELATIONAL_CHROMATIC_LAYOUT_PROFILE_ID
        == "cassi.qi-cyclic-chromatic-coordinate-native.v1"
    )
    assert (
        RELATIONAL_CHROMATIC_OPERATOR_PROFILE_ID
        == "cassi.qi-relational-chromatic-recall.v1"
    )
    assert (
        RELATIONAL_CHROMATIC_PROJECTION_PROFILE_ID
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
