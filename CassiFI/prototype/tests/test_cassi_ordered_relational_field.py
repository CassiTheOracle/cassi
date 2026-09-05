"""Focused CPU contracts for the frozen L39 ordered relational recall."""

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
from cassi_ordered_relational_field import (
    ORDERED_RELATIONAL_LAYOUT_PROFILE_ID,
    ORDERED_RELATIONAL_OPERATOR_PROFILE_ID,
    ORDERED_RELATIONAL_PROJECTION_PROFILE_ID,
    OrderedRelationalChromaticFieldConfig,
    OrderedRelationalChromaticFieldController,
)
from cassi_qi_field import QiFieldState

CHANNELS = 7
MODE_COUNT = 520


def controllers() -> tuple[
    CyclicChromaticFieldController, OrderedRelationalChromaticFieldController
]:
    return (
        CyclicChromaticFieldController(
            CyclicChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
        OrderedRelationalChromaticFieldController(
            OrderedRelationalChromaticFieldConfig(mode_count=MODE_COUNT)
        ),
    )


def rotated_pair(
    field: OrderedRelationalChromaticFieldController,
    old_symbol: int = 37,
    new_symbol: int = 134,
) -> QiFieldState:
    state = field.new_state(dtype=torch.float64)
    phase_parts = field.codebook(0, dtype=torch.float64)
    codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
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
    return field._replace_coordinates(state, common, differential, zero, zero)


def test_l39_changes_readout_but_not_l31_state_dynamics() -> None:
    cyclic, ordered = controllers()
    cyclic_state = cyclic.new_state(batch_size=2, dtype=torch.float64)
    ordered_state = ordered.new_state(batch_size=2, dtype=torch.float64)

    for symbols in ((37, 74), None, (134, 171), None, None):
        cyclic_tick = cyclic.tick(cyclic_state, symbols=symbols, steps=8)
        ordered_tick = ordered.tick(ordered_state, symbols=symbols, steps=8)
        cyclic_state = cyclic_tick.state
        ordered_state = ordered_tick.state
        assert torch.equal(cyclic_state.field, ordered_state.field)
        assert torch.equal(cyclic_tick.hamiltonian, ordered_tick.hamiltonian)
        assert torch.equal(
            cyclic_tick.input_energy_drift, ordered_tick.input_energy_drift
        )
        assert cyclic_tick.clamp_count == ordered_tick.clamp_count

    assert torch.equal(
        cyclic.psychedelic_projection(cyclic_state, max_side=16).rgb,
        ordered.psychedelic_projection(ordered_state, max_side=16).rgb,
    )


def test_scores_equal_direct_ordered_recomputation() -> None:
    cyclic, field = controllers()
    state, _ = field.heartbeat(field.new_state(batch_size=2, dtype=torch.float64))
    state, _ = field.modulate_symbols(state, (37, 148), trust=1.0)
    state = field.evolve(state, steps=7)
    state, _ = field.modulate_symbols(state, (134, 245), trust=1.0)
    before = state.field.clone()

    readout = field.white_readout(state)
    current = cyclic.white_readout(QiFieldState(state.field.clone()))
    phase_parts = field.codebook(0, dtype=torch.float64)
    codebook = torch.complex(phase_parts[..., 0], phase_parts[..., 1])
    coefficient = torch.einsum(
        "aw,wb->ab", codebook.conj(), field.relational_trace(state)
    ) / float(field.config.wave_mode_count)
    relational_scores = coefficient.abs().square().transpose(0, 1)
    relational_symbols = torch.argmax(relational_scores, dim=1)
    floor = field.config.readout_energy_floor
    expected = torch.maximum(
        current.scores / current.scores.amax(dim=1, keepdim=True).clamp_min(floor),
        relational_scores
        / relational_scores.amax(dim=1, keepdim=True).clamp_min(floor),
    )
    relational_available = current.available & (
        relational_scores.amax(dim=1) >= floor
    )
    candidates = torch.arange(field.config.alphabet_size)[None, :]
    expected = torch.where(
        relational_available[:, None]
        & (relational_symbols != current.symbols)[:, None]
        & (candidates == relational_symbols[:, None]),
        torch.full_like(expected, 2.0),
        expected,
    )
    expected = torch.where(
        current.available[:, None] & (candidates == current.symbols[:, None]),
        torch.full_like(expected, 3.0),
        expected,
    )
    expected = torch.where(current.available[:, None], expected, current.scores)

    assert torch.equal(state.field, before)
    assert torch.equal(readout.current_scores, current.scores)
    assert torch.equal(readout.relational_scores, relational_scores)
    assert torch.equal(readout.relational_symbols, relational_symbols)
    assert torch.equal(readout.relational_available, relational_available)
    assert torch.equal(readout.scores, expected)
    assert torch.equal(readout.symbols, current.symbols)


def test_exact_rotated_pair_orders_new_then_old() -> None:
    cyclic, field = controllers()
    old_symbol = 37
    new_symbol = 134
    candidate = rotated_pair(field, old_symbol, new_symbol)

    ordered = field.white_readout(candidate)
    coherent = cyclic.white_readout(QiFieldState(candidate.field.clone()))
    top_two = torch.topk(ordered.scores[0], 2).indices.tolist()

    assert ordered.symbols.item() == new_symbol
    assert top_two == [new_symbol, old_symbol]
    assert ordered.scores[0, new_symbol].item() == 3.0
    assert ordered.scores[0, old_symbol].item() == 2.0
    assert ordered.relational_symbols.item() == old_symbol
    assert ordered.relational_available.item()
    assert coherent.symbols.item() == new_symbol
    assert coherent.scores[0, old_symbol].item() < 0.05


def test_first_deposit_introduces_no_predecessor_slot() -> None:
    cyclic, field = controllers()
    cyclic_state, _ = cyclic.heartbeat(cyclic.new_state(dtype=torch.float64))
    ordered_state, _ = field.heartbeat(field.new_state(dtype=torch.float64))
    cyclic_state, _ = cyclic.modulate_symbols(cyclic_state, (148,), trust=1.0)
    ordered_state, _ = field.modulate_symbols(ordered_state, (148,), trust=1.0)

    current = cyclic.white_readout(cyclic_state)
    ordered = field.white_readout(ordered_state)
    assert field.relational_trace(ordered_state).abs().max().item() < 3.0e-15
    assert torch.equal(ordered.symbols, current.symbols)
    assert torch.equal(ordered.current_scores, current.scores)
    assert not ordered.relational_available.item()
    assert torch.count_nonzero(ordered.scores == 2.0) == 0
    assert ordered.scores[0, 148].item() == 3.0


def test_allowed_symbols_govern_both_slots() -> None:
    _, field = controllers()
    candidate = rotated_pair(field)
    allowed = (74, 171)
    readout = field.white_readout(candidate, allowed_symbols=allowed)

    current_symbol = int(readout.current_symbols.item())
    relational_symbol = int(readout.relational_symbols.item())
    assert current_symbol in allowed
    assert relational_symbol in allowed
    assert readout.scores[0, current_symbol].item() == 3.0
    if relational_symbol != current_symbol:
        assert readout.scores[0, relational_symbol].item() == 2.0
    disallowed = torch.ones(field.config.alphabet_size, dtype=torch.bool)
    disallowed[list(allowed)] = False
    assert readout.scores[0, disallowed].max().item() <= 1.0


def test_blank_is_exactly_zero_and_unavailable() -> None:
    _, field = controllers()
    blank = field.white_readout(field.new_state(dtype=torch.float32))

    assert not blank.available.item()
    assert not blank.relational_available.item()
    assert torch.count_nonzero(blank.current_scores) == 0
    assert torch.count_nonzero(blank.relational_scores) == 0
    assert torch.count_nonzero(blank.scores) == 0


def test_l39_profile_is_distinct_without_adaptive_state() -> None:
    cyclic, field = controllers()

    assert (
        ORDERED_RELATIONAL_LAYOUT_PROFILE_ID
        == "cassi.qi-cyclic-chromatic-coordinate-native.v1"
    )
    assert (
        ORDERED_RELATIONAL_OPERATOR_PROFILE_ID
        == "cassi.qi-ordered-relational-chromatic-recall.v1"
    )
    assert (
        ORDERED_RELATIONAL_PROJECTION_PROFILE_ID
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
