"""Tests for the native modal Cassi reference recurrence."""

from __future__ import annotations

import numpy as np

from cassi_modal_reference import (
    DIMENSION,
    LAYER_COUNT,
    MODE_COUNT,
    ModalFieldState,
    ModalFieldError,
    direction_modes,
    laplacian_symbol,
    transition_matrices,
)


def test_shader_symbol_and_transition_identity() -> None:
    assert laplacian_symbol(0, 0, 0) == 0.0
    matrices = transition_matrices(steps=0)
    assert matrices.shape == (MODE_COUNT, 4, 4)
    np.testing.assert_allclose(matrices, np.broadcast_to(np.eye(4, dtype=np.float32), matrices.shape), rtol=0.0, atol=0.0)


def test_signed_direction_round_trips_through_modal_epsilon() -> None:
    direction = np.linspace(-1.0, 1.0, DIMENSION, dtype=np.float32)
    direction /= np.linalg.norm(direction.astype(np.float64))
    modes = direction_modes(direction)
    state = ModalFieldState.zeros()
    state.values[:, 0] = 0.5 * modes
    state.values[:, 1] = -0.5 / 1.618033988749895 * modes
    np.testing.assert_allclose(state.decode(), direction, rtol=0.0, atol=2e-7)


def test_one_token_evolves_all_layers_and_stays_finite() -> None:
    transitions = transition_matrices()
    direction = np.ones(DIMENSION, dtype=np.float32)
    state = ModalFieldState.zeros()
    state.update_token((direction for _ in range(LAYER_COUNT)), transitions)
    assert state.layer_updates == LAYER_COUNT
    assert state.byte_size == MODE_COUNT * 4 * np.dtype(np.complex64).itemsize
    assert np.isfinite(state.decode()).all()


def test_invalid_layer_count_fails_closed() -> None:
    state = ModalFieldState.zeros()
    try:
        state.update_token((np.ones(DIMENSION, dtype=np.float32) for _ in range(LAYER_COUNT - 1)), transition_matrices())
    except ModalFieldError:
        pass
    else:
        raise AssertionError("short layer sequence was accepted")


if __name__ == "__main__":
    test_shader_symbol_and_transition_identity()
    test_signed_direction_round_trips_through_modal_epsilon()
    test_one_token_evolves_all_layers_and_stays_finite()
    test_invalid_layer_count_fails_closed()
    print("modal reference PASS")
