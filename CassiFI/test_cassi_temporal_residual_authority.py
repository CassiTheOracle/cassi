from __future__ import annotations

import numpy as np

from cassi_temporal_residual_authority import (
    _align_trajectory_rows,
    _base_context,
    _break_trajectory_identity,
    _reading_from_residual,
    _spectrum_from_gram,
)


def test_trajectory_alignment_preserves_identity_across_every_lag() -> None:
    middle = np.asarray([0, 0, 1, 1, 2, 2, 3, 3], dtype=np.int32)
    tracer = np.asarray([0, 16, 0, 16, 0, 32, 0, 16], dtype=np.int32)

    current, past = _align_trajectory_rows(middle, tracer, lags=(1, 2))

    assert current.tolist() == [4, 6]
    assert past[1].tolist() == [2, 4]
    assert past[2].tolist() == [0, 2]
    for current_row, lag_one, lag_two in zip(current, past[1], past[2]):
        assert tracer[current_row] == tracer[lag_one] == tracer[lag_two]
        assert middle[current_row] - middle[lag_one] == 1
        assert middle[current_row] - middle[lag_two] == 2


def test_identity_break_changes_tracers_without_changing_time_slots() -> None:
    middle = np.asarray([0, 0, 0, 1, 1, 1, 2, 2, 2], dtype=np.int32)
    current = np.asarray([6, 7, 8], dtype=np.int64)
    past = {
        1: np.asarray([3, 4, 5], dtype=np.int64),
        2: np.asarray([0, 1, 2], dtype=np.int64),
    }

    broken, mismatch = _break_trajectory_identity(current, past, middle)

    assert mismatch == 1.0
    for lag in (1, 2):
        assert set(broken[lag]) == set(past[lag])
        assert np.all(middle[broken[lag]] == middle[past[lag]])
        assert not np.array_equal(broken[lag], past[lag])


def test_conditional_reading_recovers_history_residual_not_identity_broken_history() -> None:
    rng = np.random.default_rng(20260919)
    train_base = rng.normal(size=(512, 8))
    validation_base = rng.normal(size=(256, 8))
    train_history = rng.normal(size=(512, 3))
    validation_history = rng.normal(size=(256, 3))
    base_coefficients = rng.normal(size=(8, 3))
    history_coefficients = rng.normal(size=(3, 3))
    train_target = (
        train_base @ base_coefficients
        + train_history @ history_coefficients
        + 0.005 * rng.normal(size=(512, 3))
    )
    validation_target = (
        validation_base @ base_coefficients
        + validation_history @ history_coefficients
        + 0.005 * rng.normal(size=(256, 3))
    )
    context = _base_context(
        train_base,
        validation_base,
        train_target,
        validation_target,
    )
    train_residual, validation_residual = context.project(
        train_history,
        validation_history,
    )

    aligned = _reading_from_residual(
        context,
        train_residual,
        validation_residual,
    )
    broken_train, broken_validation = context.project(
        np.roll(train_history, 1, axis=0),
        np.roll(validation_history, 1, axis=0),
    )
    broken = _reading_from_residual(
        context,
        broken_train,
        broken_validation,
    )

    assert aligned["fractional_rmse_reduction"] > 0.99
    assert (
        aligned["fractional_rmse_reduction"]
        - broken["fractional_rmse_reduction"]
        > 0.90
    )


def test_effective_rank_is_unchanged_by_an_exact_duplicate_history_block() -> None:
    rng = np.random.default_rng(20260920)
    history = rng.normal(size=(512, 24))
    gram = history.T @ history
    duplicate_gram = np.block([[gram, gram], [gram, gram]])

    reference = _spectrum_from_gram(gram, len(history))
    duplicate = _spectrum_from_gram(duplicate_gram, len(history))

    assert reference["rank"] == 24
    assert duplicate["rank"] == reference["rank"]
