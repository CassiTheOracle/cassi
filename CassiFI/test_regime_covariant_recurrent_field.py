from __future__ import annotations

from dataclasses import replace

import numpy as np
import torch

from cassi_regime_covariant_recurrent_field import (
    CovariantFieldConfig,
    CovariantFrame,
    RegimeCovariantRecurrentField,
)


def _world(seed: int, *, frames: int = 72, identities: int = 8) -> list[CovariantFrame]:
    rng = np.random.default_rng(seed)
    ids = np.arange(identities, dtype=np.int64)
    phase = rng.uniform(-np.pi, np.pi, size=(identities, 3))
    direction = rng.normal(size=(identities, 3))
    direction /= np.linalg.norm(direction, axis=1, keepdims=True)
    offset = 2.0 * direction
    delta_time = 0.4
    position_rows: list[np.ndarray] = []
    velocity_rows: list[np.ndarray] = []
    for tick in range(1, frames + 1):
        time = tick * delta_time
        velocity = (
            0.7 * np.sin(0.31 * time + phase)
            + 0.25 * np.cos(0.11 * time - 0.5 * phase)
            + 0.002 * tick * direction
        )
        position = offset + 0.18 * time * direction + 0.12 * np.sin(
            0.17 * time + phase
        )
        position_rows.append(position)
        velocity_rows.append(velocity)

    result: list[CovariantFrame] = []
    for index, (position, velocity) in enumerate(
        zip(position_rows, velocity_rows, strict=True)
    ):
        target = np.zeros((identities, 3), dtype=np.float64)
        if index >= 2:
            d1 = (velocity - velocity_rows[index - 1]) / delta_time
            d2 = (velocity - velocity_rows[index - 2]) / (2.0 * delta_time)
            jerk = d1 - d2
            midpoint = position + position_rows[index - 1]
            radial = midpoint / np.linalg.norm(midpoint, axis=1, keepdims=True)
            radial_jerk = radial * np.einsum("ni,ni->n", jerk, radial)[:, None]
            transverse_jerk = jerk - radial_jerk
            target = d1 + 0.45 * radial_jerk - 0.30 * transverse_jerk
        present = np.column_stack(
            (
                np.linalg.norm(position, axis=1),
                np.linalg.norm(velocity, axis=1),
                np.einsum("ni,ni->n", position, velocity),
            )
        )
        result.append(
            CovariantFrame(
                tick=index + 1,
                identity_ids=ids.copy(),
                present=present,
                position=position,
                velocity=velocity,
                delta_time=delta_time,
                target=target,
            )
        )
    return result


def _controller() -> RegimeCovariantRecurrentField:
    torch.set_num_threads(1)
    return RegimeCovariantRecurrentField(
        CovariantFieldConfig(
            present_width=3,
            max_identities=8,
            correction_ridge=0.1,
        )
    )


def _trained() -> tuple[RegimeCovariantRecurrentField, object]:
    controller = _controller()
    training = _world(1701)
    state = controller.fit_snapshot_baseline(controller.initial_state(), training)
    state = controller.learn_world(state, training)
    return controller, state


def _target(forecast, frames: list[CovariantFrame]) -> np.ndarray:
    lookup = {
        (frame.tick, int(identity)): frame.target[index]
        for frame in frames
        for index, identity in enumerate(frame.identity_ids)
    }
    return np.stack(
        [
            lookup[(int(tick), int(identity))]
            for tick, identity in zip(
                forecast.ticks.tolist(), forecast.identity_ids.tolist(), strict=True
            )
        ]
    )


def _rmse(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((prediction - target) ** 2)))


def test_field_learns_identity_bound_covariant_correction():
    controller, state = _trained()
    holdout = _world(1723)
    aligned = controller.forecast_world(state, holdout)
    broken = controller.forecast_world(state, holdout, break_identity=True)
    target = _target(aligned, holdout)

    causal_error = _rmse(aligned.causal, target)
    combined_error = _rmse(aligned.combined, target)
    broken_error = _rmse(broken.combined, target)
    assert combined_error < 0.45 * causal_error
    assert broken_error > 5.0 * combined_error
    assert broken.identity_mismatch_fraction == 1.0
    inspection = controller.inspect(state)
    assert inspection["adaptive_owner"] == "RegimeCovariantState.field"
    assert inspection["correction_rank"] == 2
    assert inspection["memory_samples"] > 0


def test_same_field_commutes_with_units_and_rigid_rotation():
    controller, state = _trained()
    holdout = _world(1741)
    reference = controller.forecast_world(state, holdout)
    length_scale = 7.5
    velocity_scale = 2.25
    acceleration_scale = velocity_scale**2 / length_scale
    angle = 0.73
    cosine = float(np.cos(angle))
    sine = float(np.sin(angle))
    rotation = np.array(
        (
            (cosine, -sine, 0.0),
            (sine, cosine, 0.0),
            (0.0, 0.0, 1.0),
        ),
        dtype=np.float64,
    )
    assert np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-15)
    transformed = [
        CovariantFrame(
            tick=frame.tick,
            identity_ids=frame.identity_ids.copy(),
            present=frame.present.copy(),
            position=length_scale * (frame.position @ rotation.T),
            velocity=velocity_scale * (frame.velocity @ rotation.T),
            delta_time=frame.delta_time * length_scale / velocity_scale,
            target=None
            if frame.target is None
            else acceleration_scale * (frame.target @ rotation.T),
        )
        for frame in holdout
    ]
    changed = controller.forecast_world(state, transformed)
    expected = acceleration_scale * (reference.combined @ rotation.T)
    assert np.allclose(changed.combined, expected, rtol=2e-12, atol=2e-12)
    assert np.allclose(
        changed.causal,
        acceleration_scale * (reference.causal @ rotation.T),
        rtol=2e-12,
        atol=2e-12,
    )


def test_checkpoint_target_blindness_and_row_order_are_exact():
    controller, state = _trained()
    holdout = _world(1753)
    before = controller.state_sha256(state)
    canonical = controller.forecast_world(state, holdout)
    restarted_state = controller.import_state(controller.export_state(state))
    restarted = controller.forecast_world(restarted_state, holdout)
    target_changed = controller.forecast_world(
        state,
        [replace(frame, target=frame.target + 1000.0) for frame in holdout],
    )
    reversed_rows = controller.forecast_world(
        state,
        [
            CovariantFrame(
                tick=frame.tick,
                identity_ids=frame.identity_ids[::-1],
                present=frame.present[::-1],
                position=frame.position[::-1],
                velocity=frame.velocity[::-1],
                delta_time=frame.delta_time,
                target=frame.target[::-1],
            )
            for frame in holdout
        ],
    )

    assert controller.state_sha256(state) == before
    assert controller.state_sha256(restarted_state) == before
    assert np.array_equal(canonical.combined, restarted.combined)
    assert np.array_equal(canonical.combined, target_changed.combined)
    assert np.array_equal(canonical.combined, reversed_rows.combined)
    assert np.array_equal(canonical.identity_ids, reversed_rows.identity_ids)
