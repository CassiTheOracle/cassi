"""Executable contracts for the parameter-free Cassi field intelligence."""

from __future__ import annotations

import inspect
import tempfile
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training", _CASSI_FI_ROOT / "verification"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import torch

from cassi_field_intelligence import (
    BOUNDARY_PROFILE_ID,
    FIELD_LAYOUT_ID,
    CassiBoundaryAlphabet,
    CassiFieldIntelligence,
    CassiFieldIntelligenceConfig,
    CassiFieldIntelligenceError,
    CassiFieldState,
    load_field_state,
    save_field_state,
)


def _config() -> CassiFieldIntelligenceConfig:
    return CassiFieldIntelligenceConfig(
        mode_count=32,
        alphabet_size=16,
        grid_n=4,
        dt=0.002,
        fast_omega2=8.0,
        slow_omega2=0.02,
        fast_damping=0.8,
        slow_damping=0.02,
        nonlinear_gain=0.001,
        settle_steps=1,
        consolidation_steps=1,
        plasticity_gain=0.08,
        slow_retention=0.999,
        max_mode_amplitude=8.0,
        max_mean_energy=32.0,
    )


def _expect_error(fn) -> None:
    try:
        fn()
    except CassiFieldIntelligenceError:
        return
    raise AssertionError("expected CassiFieldIntelligenceError")


def _assert_state_close(left: CassiFieldState, right: CassiFieldState) -> None:
    torch.testing.assert_close(left.field, right.field, rtol=0.0, atol=0.0)


def test_single_field_contract_has_no_classical_head_or_parameter_surface() -> None:
    intelligence = CassiFieldIntelligence(_config())
    assert not hasattr(intelligence, "parameters")
    assert not any(isinstance(value, torch.Tensor) for value in vars(intelligence).values())
    source = inspect.getsource(CassiFieldIntelligence)
    for forbidden in ("torch.nn", "nn.Linear", "nn.Parameter", "LayerNorm", "Embedding"):
        assert forbidden not in source
    assert FIELD_LAYOUT_ID == "cassi.field-intelligence.native-linear-x-fast.v1"
    assert BOUNDARY_PROFILE_ID == "cassi.boundary.quadratic-chirp.v1"


def test_config_rejects_unstable_and_unknown_controls() -> None:
    _expect_error(lambda: CassiFieldIntelligenceConfig(mode_count=31))
    _expect_error(lambda: CassiFieldIntelligenceConfig(mode_count=64, grid_n=2))
    _expect_error(lambda: CassiFieldIntelligenceConfig.from_dict({"unknown": 1}))
    _expect_error(lambda: CassiFieldIntelligenceConfig(dt=1.0, fast_omega2=8.0))


def test_boundary_codes_are_fixed_finite_and_resonant() -> None:
    first = CassiBoundaryAlphabet(16, 64)
    second = CassiBoundaryAlphabet(16, 64)
    assert first.fingerprint == second.fingerprint
    codes = first.codes(device=torch.device("cpu"), dtype=torch.float32)
    scores = first.resonance_scores(codes)
    assert torch.isfinite(codes).all()
    torch.testing.assert_close(torch.diag(scores), torch.ones(16), atol=2.0e-6, rtol=0.0)
    off_diagonal = scores[~torch.eye(16, dtype=torch.bool)]
    assert float(off_diagonal.abs().max()) < 0.35
    assert torch.equal(
        first.bytes_to_symbols(b"Cassi", device="cpu"),
        torch.tensor([67, 97, 115, 115, 105], dtype=torch.int64),
    )
    assert first.symbols_to_bytes([67, 97, 115, 115, 105]) == b"Cassi"


def test_state_shape_batch_isolation_and_finite_evolution() -> None:
    intelligence = CassiFieldIntelligence(_config())
    state = intelligence.initial_state(2)
    symbols = torch.tensor([1, 2], dtype=torch.int64)
    batched = intelligence.evolve(intelligence.sense(state, symbols))
    one = intelligence.evolve(intelligence.sense(intelligence.initial_state(1), symbols[:1]))
    two = intelligence.evolve(intelligence.sense(intelligence.initial_state(1), symbols[1:]))
    torch.testing.assert_close(batched.field[:, :1], one.field, atol=0.0, rtol=0.0)
    torch.testing.assert_close(batched.field[:, 1:], two.field, atol=0.0, rtol=0.0)
    assert batched.field.shape == (8 * intelligence.config.mode_count, 2)
    assert torch.isfinite(batched.field).all()
    assert torch.isfinite(intelligence.component_energy(batched)).all()
    assert torch.isfinite(intelligence.free_energy(batched)).all()


def test_prediction_is_unavailable_without_field_signal_and_correction_writes_same_field() -> None:
    intelligence = CassiFieldIntelligence(_config())
    state = intelligence.initial_state(2)
    initial_emission = intelligence.emit(state)
    assert not bool(initial_emission.available.any())
    sensed = intelligence.evolve(
        intelligence.sense(state, torch.tensor([1, 2], dtype=torch.int64))
    )
    predicted = intelligence.emit(sensed)
    assert not bool(predicted.available.any())
    assert torch.isfinite(predicted.scores).all()
    corrected, correction_energy = intelligence.correct(
        sensed, torch.tensor([3, 4], dtype=torch.int64)
    )
    assert bool(torch.all(correction_energy > 0.0))
    slow = torch.tensor(intelligence.slow_indices, dtype=torch.int64)
    assert not torch.equal(
        sensed.field.index_select(0, 8 * slow), corrected.field.index_select(0, 8 * slow)
    )
    assert torch.isfinite(corrected.field).all()


def test_cycle_imagination_reset_and_persistence_round_trip() -> None:
    intelligence = CassiFieldIntelligence(_config())
    state = intelligence.initial_state(2)
    for current, target in ((1, 3), (2, 4), (1, 3), (2, 4)):
        cycle = intelligence.cycle(
            state,
            torch.tensor([current, current], dtype=torch.int64),
            target_symbols=torch.tensor([target, target], dtype=torch.int64),
            learn=True,
        )
        state = cycle.state
        assert torch.isfinite(cycle.emission.scores).all()
        assert torch.isfinite(state.field).all()
    imagined = intelligence.imagine(state, steps=3)
    assert len(imagined.emissions) <= 3
    assert torch.isfinite(imagined.state.field).all()
    preserved = intelligence.reset(state, preserve_memory=True)
    cleared = intelligence.reset(state, preserve_memory=False)
    assert torch.isfinite(preserved.field).all()
    assert torch.equal(cleared.field, torch.zeros_like(cleared.field))

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "field.pt"
        digest = save_field_state(path, intelligence, state)
        restored = load_field_state(path, intelligence)
        assert len(digest) == 64
        _assert_state_close(state, restored)
        incompatible = CassiFieldIntelligence(
            CassiFieldIntelligenceConfig(mode_count=32, alphabet_size=17, grid_n=4)
        )
        _expect_error(lambda: load_field_state(path, incompatible))


def test_invalid_symbols_and_state_are_rejected() -> None:
    intelligence = CassiFieldIntelligence(_config())
    state = intelligence.initial_state(1)
    _expect_error(lambda: intelligence.sense(state, torch.tensor([16], dtype=torch.int64)))
    _expect_error(lambda: intelligence.sense(state, torch.tensor([1.0])))
    bad = CassiFieldState(torch.full_like(state.field, float("nan")))
    _expect_error(lambda: intelligence.emit(bad))


if __name__ == "__main__":
    test_single_field_contract_has_no_classical_head_or_parameter_surface()
    test_config_rejects_unstable_and_unknown_controls()
    test_boundary_codes_are_fixed_finite_and_resonant()
    test_state_shape_batch_isolation_and_finite_evolution()
    test_prediction_is_unavailable_without_field_signal_and_correction_writes_same_field()
    test_cycle_imagination_reset_and_persistence_round_trip()
    test_invalid_symbols_and_state_are_rejected()
    print("Cassi field-intelligence tests passed")
