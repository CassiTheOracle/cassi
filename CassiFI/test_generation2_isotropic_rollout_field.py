"""Focused tests for generation-two regime identity gating."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cassi_generation2_isotropic_rollout_field import (
    Generation2GuardedFieldConfig,
    Generation2IsotropicRegimeGuardedField,
)
from cassi_hierarchical_covariant_recurrent_field import (
    HierarchicalCovariantFieldConfig,
    HierarchicalCovariantRecurrentField,
)
from run_generation2_two_regime_holdout import (
    _controller,
    _holdout_metrics,
    _split,
    _synthetic_world,
)


def _config() -> HierarchicalCovariantFieldConfig:
    return HierarchicalCovariantFieldConfig(
        present_width=3,
        max_identities=8,
        lags=(1, 2, 4, 8),
        correction_ridge=0.1,
        anisotropy_ridge=8.0,
        anisotropy_support_threshold=0.2,
        min_anisotropic_worlds=2,
    )


def test_same_regime_chunks_cannot_release_anisotropy() -> None:
    world = _synthetic_world(22103).frames
    controller = Generation2IsotropicRegimeGuardedField(
        Generation2GuardedFieldConfig(_config())
    )
    state = controller.fit_snapshot_baseline(controller.initial_state(), world)
    state = controller.begin_isotropic_rollout(state)
    state = controller.learn_world(state, world, regime_id="chronological-regime")
    state = controller.learn_world(state, world, regime_id="chronological-regime")

    inspection = controller.inspect(state)
    assert inspection["guard_regime_token_count"] == 1
    assert inspection["guard_unique_regime_support"] == 1
    assert inspection["anisotropic_world_support"] == 1
    aligned = controller.forecast_world(state, world)
    isotropic = controller.forecast_isotropic(state, world)
    assert np.array_equal(aligned.combined, isotropic.combined)


def test_unguarded_control_reenters_after_two_calls_and_checkpoint_preserves_guard() -> None:
    world = _synthetic_world(22103).frames
    unguarded = HierarchicalCovariantRecurrentField(_config())
    unguarded_state = unguarded.fit_snapshot_baseline(unguarded.initial_state(), world)
    unguarded_state = unguarded.learn_world(unguarded_state, world)
    unguarded_state = unguarded.learn_world(unguarded_state, world)
    assert unguarded.inspect(unguarded_state)["anisotropic_world_support"] == 2
    assert abs(float(unguarded.inspect(unguarded_state)["basis_coefficients"][1])) > 1e-6

    guarded = Generation2IsotropicRegimeGuardedField(
        Generation2GuardedFieldConfig(_config())
    )
    state = guarded.fit_snapshot_baseline(guarded.initial_state(), world)
    state = guarded.begin_isotropic_rollout(state)
    state = guarded.learn_world(state, world, regime_id="same-regime")
    state = guarded.learn_world(state, world, regime_id="same-regime")
    restored = guarded.import_state(guarded.export_state(state))
    assert guarded.state_sha256(restored) == guarded.state_sha256(state)
    assert guarded.inspect(restored)["guard_unique_regime_support"] == 1
    assert guarded.inspect(restored)["anisotropic_world_support"] == 1


def test_distinct_regimes_release_once_and_repeated_chunks_stay_bounded() -> None:
    first_world = _synthetic_world(22103).frames
    second_world = _synthetic_world(22111).frames
    controller = Generation2IsotropicRegimeGuardedField(
        Generation2GuardedFieldConfig(_config())
    )
    state = controller.fit_snapshot_baseline(
        controller.initial_state(), first_world
    )
    state = controller.begin_isotropic_rollout(state)

    state = controller.learn_world(state, first_world, regime_id="regime-A")
    first = controller.inspect(state)
    assert first["guard_regime_token_count"] == 1
    assert first["guard_unique_regime_support"] == 1
    assert first["anisotropic_world_support"] == 1

    state = controller.learn_world(state, first_world, regime_id="regime-A")
    repeated_first = controller.inspect(state)
    assert repeated_first["guard_regime_token_count"] == 1
    assert repeated_first["guard_unique_regime_support"] == 1
    assert repeated_first["anisotropic_world_support"] == 1
    assert np.array_equal(
        controller.forecast_world(state, first_world).combined,
        controller.forecast_isotropic(state, first_world).combined,
    )

    state = controller.learn_world(state, second_world, regime_id="regime-B")
    second = controller.inspect(state)
    assert second["guard_regime_token_count"] == 2
    assert second["guard_unique_regime_support"] == 2
    assert second["anisotropic_world_support"] == 2
    assert abs(float(second["basis_coefficients"][1])) > 1e-6
    released = controller.forecast_world(state, second_world)
    isotropic = controller.forecast_isotropic(state, second_world)
    assert not np.array_equal(released.combined, isotropic.combined)

    state = controller.learn_world(state, second_world, regime_id="regime-B")
    repeated_second = controller.inspect(state)
    assert repeated_second["guard_regime_token_count"] == 2
    assert repeated_second["guard_unique_regime_support"] == 2
    assert repeated_second["anisotropic_world_support"] == 2
    restored = controller.import_state(controller.export_state(state))
    assert controller.state_sha256(restored) == controller.state_sha256(state)
    assert controller.inspect(restored)["guard_unique_regime_support"] == 2


def test_distinct_release_is_nonworse_on_chronological_holdout() -> None:
    development = _synthetic_world(22001)
    regime_a = _synthetic_world(22103)
    regime_b = _synthetic_world(22111)
    controller = _controller((development, regime_a, regime_b))
    state = controller.fit_snapshot_baseline(
        controller.initial_state(), development.frames
    )
    state = controller.begin_isotropic_rollout(state)

    a_first, a_second, _ = _split(regime_a)
    state = controller.learn_world(
        state, a_first, regime_id=f"{regime_a.relative_root}:A"
    )
    state = controller.learn_world(
        state, a_second, regime_id=f"{regime_a.relative_root}:A"
    )
    after_a = controller.inspect(state)
    assert after_a["guard_unique_regime_support"] == 1
    assert after_a["anisotropic_world_support"] == 1

    b_first, b_second, b_holdout = _split(regime_b)
    state = controller.learn_world(
        state, b_first, regime_id=f"{regime_b.relative_root}:B"
    )
    state = controller.learn_world(
        state, b_second, regime_id=f"{regime_b.relative_root}:B"
    )
    after_b = controller.inspect(state)
    assert after_b["guard_unique_regime_support"] == 2
    assert after_b["anisotropic_world_support"] == 2
    metrics = _holdout_metrics(controller, state, regime_b, b_holdout)
    assert metrics["guarded_nrmse"] <= metrics["isotropic_nrmse"] + 1e-12
