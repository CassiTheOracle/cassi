from __future__ import annotations

import numpy as np

from cassi_morphology_residual_authority import _conditional_spectrum, conditional_reading


def test_conditional_authority_recovers_real_added_channel() -> None:
    rng = np.random.default_rng(811)
    train_base = rng.normal(size=(400, 4))
    validation_base = rng.normal(size=(200, 4))
    train_morphology = rng.normal(size=(400, 3))
    validation_morphology = rng.normal(size=(200, 3))
    coefficient = np.array([0.4, -0.2, 0.1])
    train_target = train_base @ np.array([[0.1, 0.0, 0.2], [0.3, 0.1, 0.0], [0.0, -0.4, 0.1], [0.2, 0.3, -0.1]]) + train_morphology @ np.diag(coefficient)
    validation_target = validation_base @ np.array([[0.1, 0.0, 0.2], [0.3, 0.1, 0.0], [0.0, -0.4, 0.1], [0.2, 0.3, -0.1]]) + validation_morphology @ np.diag(coefficient)

    reading = conditional_reading(
        train_base, validation_base, train_morphology, validation_morphology, train_target, validation_target,
    )

    assert reading["fractional_rmse_reduction"] > 0.99


def test_conditional_spectrum_duplicate_control_loses_no_rank() -> None:
    rng = np.random.default_rng(812)
    base = rng.normal(size=(300, 5))
    morphology = rng.normal(size=(300, 4))

    original = _conditional_spectrum(base, morphology)
    duplicate = _conditional_spectrum(base, np.concatenate((morphology, morphology[:, :1]), axis=1))

    assert original["rank"] == 4
    assert duplicate["rank"] == original["rank"]
