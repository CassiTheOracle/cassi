"""Focused CPU contracts for the frozen L49 causal crossover."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import cast

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cassi_harmonic_age_field import HarmonicAgeFieldController
from cassi_ordered_relational_field import (
    OrderedRelationalChromaticFieldController,
)
from cassi_qi_field import QiFieldState
from cassi_white_chromatic_field import WhiteChromaticFieldController
from verification.run_l49_harmonic_write_causal_crossover import (
    bare_write,
    frozen_style_state,
    lift_then_bare_write,
)
import verification.verify_l49_harmonic_write_causal_crossover as l49v
from verification.verify_l49_harmonic_write_causal_crossover import (
    L49VerificationError,
    semantic_compare,
)

CHANNELS = 7
MODE_COUNT = 520
S0 = (0, 37, 74, 111, 148, 185, 222, 259)
S1 = tuple((symbol + 97) % 260 for symbol in S0)


def _clone(state: QiFieldState) -> QiFieldState:
    return QiFieldState(state.field.clone())


@pytest.fixture(scope="module")
def frozen_state() -> tuple[
    OrderedRelationalChromaticFieldController,
    HarmonicAgeFieldController,
    QiFieldState,
]:
    return frozen_style_state(
        torch.device("cpu"), torch.float64, mode_count=MODE_COUNT
    )


def _physical_harmonics(
    controller: HarmonicAgeFieldController,
    state: QiFieldState,
    differential: torch.Tensor,
) -> torch.Tensor:
    phase = controller._constants(state)["channel_phase"]
    harmonics = torch.arange(CHANNELS, device=phase.device, dtype=torch.int64)
    basis = phase.conj()[None, :].pow(harmonics[:, None]) / math.sqrt(CHANNELS)
    return torch.einsum("hc,cwb->hwb", basis, differential)


def test_bare_write_is_direct_qualified_white_write(
    frozen_state: tuple[
        OrderedRelationalChromaticFieldController,
        HarmonicAgeFieldController,
        QiFieldState,
    ],
) -> None:
    ordered, _, state = frozen_state

    got_state, got_drift, got_clamps = bare_write(ordered, _clone(state), S1)
    expected_state, expected_drift, expected_clamps = (
        WhiteChromaticFieldController._modulate_unchecked(
            ordered, _clone(state), S1, 1.0
        )
    )

    assert torch.equal(got_state.field, expected_state.field)
    assert torch.equal(got_drift, expected_drift)
    assert got_clamps == expected_clamps


def test_lift_then_bare_write_is_bare_write_of_one_lift_and_differs_from_w(
    frozen_state: tuple[
        OrderedRelationalChromaticFieldController,
        HarmonicAgeFieldController,
        QiFieldState,
    ],
) -> None:
    ordered, harmonic, state = frozen_state

    got_state, got_drift, got_clamps = lift_then_bare_write(
        ordered, harmonic, _clone(state), S1
    )
    lifted = harmonic.lift_harmonics(_clone(state))
    expected_state, expected_drift, expected_clamps = (
        WhiteChromaticFieldController._modulate_unchecked(
            ordered, lifted, S1, 1.0
        )
    )
    bare_state, _, _ = bare_write(ordered, _clone(state), S1)

    assert torch.equal(got_state.field, expected_state.field)
    assert torch.equal(got_drift, expected_drift)
    assert got_clamps == expected_clamps
    assert not torch.equal(bare_state.field, got_state.field)

def test_independent_numpy_bare_write_matches_direct_white_write(
    frozen_state: tuple[
        OrderedRelationalChromaticFieldController,
        HarmonicAgeFieldController,
        QiFieldState,
    ],
) -> None:
    ordered, _, state = frozen_state
    expected_state, expected_drift, expected_clamps = (
        WhiteChromaticFieldController._modulate_unchecked(
            ordered, _clone(state), S1, 1.0
        )
    )
    codebook = ordered.codebook(
        device=state.field.device, dtype=state.field.dtype
    ).detach().cpu().numpy()
    got_field, got_drift, got_clamps = l49v.bare_write_field(
        state.field.detach().cpu().numpy(),
        codebook,
        np.asarray(S1, dtype=np.int64),
    )

    np.testing.assert_allclose(
        got_field,
        expected_state.field.detach().cpu().numpy(),
        rtol=0.0,
        atol=2.0e-12,
    )
    np.testing.assert_allclose(
        got_drift,
        expected_drift.detach().cpu().numpy(),
        rtol=0.0,
        atol=2.0e-12,
    )
    assert got_clamps == expected_clamps



def test_write_helpers_never_invoke_harmonic_modulation_override(
    monkeypatch: pytest.MonkeyPatch,
    frozen_state: tuple[
        OrderedRelationalChromaticFieldController,
        HarmonicAgeFieldController,
        QiFieldState,
    ],
) -> None:
    ordered, harmonic, state = frozen_state

    def fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("harmonic modulation override was invoked")

    monkeypatch.setattr(HarmonicAgeFieldController, "_modulate_unchecked", fail)

    bare_write(ordered, _clone(state), S1)
    lift_then_bare_write(ordered, harmonic, _clone(state), S1)


def test_lift_changes_only_differential_planes_and_rotates_physical_harmonics(
    frozen_state: tuple[
        OrderedRelationalChromaticFieldController,
        HarmonicAgeFieldController,
        QiFieldState,
    ],
) -> None:
    _, harmonic, state = frozen_state
    before_parts = harmonic._parts(state)
    before_common, before_differential, before_common_velocity, before_differential_velocity = (
        harmonic._active_coordinates(state)
    )
    lifted = harmonic.lift_harmonics(_clone(state))
    after_parts = harmonic._parts(lifted)
    after_common, after_differential, after_common_velocity, after_differential_velocity = (
        harmonic._active_coordinates(lifted)
    )

    assert torch.equal(after_common, before_common)
    assert torch.equal(after_common_velocity, before_common_velocity)
    assert torch.allclose(
        after_differential,
        harmonic._constants(state)["channel_phase"][:, None, None]
        * before_differential,
        rtol=0.0,
        atol=2.0e-12,
    )
    assert torch.allclose(
        after_differential_velocity,
        harmonic._constants(state)["channel_phase"][:, None, None]
        * before_differential_velocity,
        rtol=0.0,
        atol=2.0e-12,
    )
    for index in (0, 1, 4, 5, 8):
        assert torch.equal(after_parts[index], before_parts[index])

    packed_before = state.field.reshape(
        harmonic.config.bank_count,
        9,
        harmonic.config.mode_count,
        state.batch_size,
    )
    packed_after = lifted.field.reshape(
        harmonic.config.bank_count,
        9,
        harmonic.config.mode_count,
        state.batch_size,
    )
    width = harmonic.config.wave_mode_count
    assert torch.equal(packed_after[:, :, width:, :], packed_before[:, :, width:, :])

    before_d = _physical_harmonics(harmonic, state, before_differential)
    after_d = _physical_harmonics(harmonic, state, after_differential)
    before_vd = _physical_harmonics(harmonic, state, before_differential_velocity)
    after_vd = _physical_harmonics(harmonic, state, after_differential_velocity)
    for old_harmonic in range(CHANNELS):
        new_harmonic = (old_harmonic + 1) % CHANNELS
        assert torch.allclose(
            after_d[new_harmonic], before_d[old_harmonic], rtol=0.0, atol=2.0e-12
        )
        assert torch.allclose(
            after_vd[new_harmonic], before_vd[old_harmonic], rtol=0.0, atol=2.0e-12
        )
    assert torch.allclose(
        after_d.abs().square().sum(),
        before_d.abs().square().sum(),
        rtol=0.0,
        atol=2.0e-12,
    )
    assert torch.allclose(
        after_vd.abs().square().sum(),
        before_vd.abs().square().sum(),
        rtol=0.0,
        atol=2.0e-12,
    )


def _semantic_inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    scores = np.array([[[1.0, 0.5, 0.0], [0.0, 0.25, 0.0]]])
    symbols = np.array([[0, 1]])
    available = np.array([[True, False]])
    return scores, symbols, available


def test_semantic_compare_accepts_equal_available_winners() -> None:
    scores, symbols, available = _semantic_inputs()
    counts = semantic_compare(
        scores,
        symbols,
        available,
        scores.copy(),
        symbols.copy(),
        available.copy(),
        "equal",
    )

    assert counts["available_winner_mismatches"] == 0
    assert counts["ignored_unavailable_winner_mismatches"] == 0


def test_semantic_compare_counts_but_accepts_unavailable_winner_disagreement() -> None:
    scores, symbols, available = _semantic_inputs()
    recorded_symbols = symbols.copy()
    recorded_symbols[0, 1] = 2
    counts = semantic_compare(
        scores,
        recorded_symbols,
        available,
        scores.copy(),
        symbols,
        available.copy(),
        "unavailable-winner",
    )

    assert counts["available_winner_mismatches"] == 0
    assert counts["ignored_unavailable_winner_mismatches"] == 1


@pytest.mark.parametrize("mutation", ("winner", "availability", "score"))
def test_semantic_compare_rejects_available_winner_availability_or_score_mismatch(
    mutation: str,
) -> None:
    scores, symbols, available = _semantic_inputs()
    recorded_scores = scores.copy()
    recorded_symbols = symbols.copy()
    recorded_available = available.copy()
    if mutation == "winner":
        recorded_symbols[0, 0] = 2
    elif mutation == "availability":
        recorded_available[0, 1] = True
    else:
        recorded_scores[0, 0, 0] += 1.0e-2

    with pytest.raises(L49VerificationError):
        semantic_compare(
            recorded_scores,
            recorded_symbols,
            recorded_available,
            scores,
            symbols,
            available,
            mutation,
        )


@pytest.fixture(scope="module")
def identity_receipts() -> dict[str, np.ndarray]:
    trace_path = (
        ROOT
        / "_diag"
        / "l40-rolling-ordered-relational-recall"
        / "l40-rolling-traces.npz"
    )
    with np.load(trace_path, allow_pickle=False) as archive:
        prefix = np.asarray(archive["checkpoint_fields"][:2]).copy()
    branch_pre = np.stack((prefix[1],) * 4)
    fork_hash = l49v._sha_array(prefix[1])
    resume = np.asarray(("a" * 64, "b" * 64), dtype="<U64")
    return {
        "prefix_checkpoint_fields": prefix,
        "prefix_field_sha256": l49v.PREFIX_FIELD_HASHES.copy(),
        "branch_pre_fields": branch_pre,
        "fork_field_sha256": np.asarray(
            (fork_hash,) * 4, dtype="<U64"
        ),
        "s1_symbol_sha256": np.asarray(
            l49v._sha_array(l49v.S1.astype(np.int64)), dtype="<U64"
        ),
        "resume_uninterrupted_sha256": resume,
        "resume_reloaded_sha256": resume.copy(),
    }


def test_identity_receipt_gate_accepts_frozen_values(
    identity_receipts: dict[str, np.ndarray],
) -> None:
    l49v.check_identity_receipts(identity_receipts)


@pytest.mark.parametrize(
    "mutation", ("prefix_hash", "clone", "s1_symbol", "resume")
)
def test_identity_receipt_gate_rejects_mutations(
    identity_receipts: dict[str, np.ndarray],
    mutation: str,
) -> None:
    changed = {
        name: value.copy() for name, value in identity_receipts.items()
    }
    if mutation == "prefix_hash":
        changed["prefix_field_sha256"][0] = "0" * 64
    elif mutation == "clone":
        changed["branch_pre_fields"][1, 0, 0, 0] += 1.0
    elif mutation == "s1_symbol":
        changed["s1_symbol_sha256"][...] = "0" * 64
    else:
        changed["resume_reloaded_sha256"][0] = "0" * 64

    with pytest.raises(L49VerificationError):
        l49v.check_identity_receipts(changed)


@pytest.fixture(scope="module")
def source_board() -> dict[str, object]:
    source = {
        relative: l49v.sha256_file(ROOT / relative)
        for relative in l49v.EXPECTED_SOURCES
    }
    return {
        "source_sha256": source,
        "preregistration_sha256": l49v.EXPECTED_SOURCES[
            "designs/L49-HARMONIC-WRITE-CAUSAL-CROSSOVER-PREREG.md"
        ],
    }


def test_source_gate_accepts_exact_closure(
    source_board: dict[str, object],
) -> None:
    l49v._source_gate(source_board)


@pytest.mark.parametrize("mutation", ("key", "hash"))
def test_source_gate_rejects_key_or_hash_mutation(
    source_board: dict[str, object],
    mutation: str,
) -> None:
    changed = dict(source_board)
    source = dict(
        cast(dict[str, str], source_board["source_sha256"])
    )
    changed["source_sha256"] = source
    if mutation == "key":
        source.pop("cassi_qi_profile.py")
    else:
        source["cassi_qi_profile.py"] = "0" * 64

    with pytest.raises(L49VerificationError):
        l49v._source_gate(changed)


def test_native_harmonic_comparator_rejects_mutation() -> None:
    trace_path = (
        ROOT
        / "_diag"
        / "l40-rolling-ordered-relational-recall"
        / "l40-rolling-traces.npz"
    )
    with np.load(trace_path, allow_pickle=False) as archive:
        field = np.asarray(archive["checkpoint_fields"][1])
        codebook = np.asarray(archive["codebook"])
    expected = l49v.reconstruct_readouts(field, codebook)["physical_d"]
    changed = expected.copy()
    changed[0, 0, 0] += 1.0e-2

    with pytest.raises(L49VerificationError):
        l49v._close(changed, expected, "mutated native harmonic")


def test_clamp_gate_rejects_mutation() -> None:
    with pytest.raises(L49VerificationError):
        l49v._check_zero_clamps(np.asarray((0, 1)), "mutated")


def test_inactive_tail_gate_rejects_mutation() -> None:
    trace_path = (
        ROOT
        / "_diag"
        / "l40-rolling-ordered-relational-recall"
        / "l40-rolling-traces.npz"
    )
    with np.load(trace_path, allow_pickle=False) as archive:
        field = np.asarray(archive["checkpoint_fields"][1]).copy()
    packed = field.reshape(7, 9, 2048, 8)
    packed[0, 0, 1024, 0] = 1.0

    with pytest.raises(L49VerificationError):
        l49v._check_field_bounds(field, "mutated")
