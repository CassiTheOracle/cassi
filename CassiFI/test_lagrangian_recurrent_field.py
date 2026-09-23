"""Behavioral regressions for the identity-bound recurrent trajectory field."""
from __future__ import annotations

import numpy as np
import torch

from cassi_lagrangian_recurrent_field import (
    LagrangianFieldConfig,
    LagrangianFrame,
    LagrangianRecurrentField,
)


def _world(seed: int, *, ticks: int = 96, identities: int = 8) -> list[LagrangianFrame]:
    rng = np.random.default_rng(seed)
    latent = rng.normal(size=(identities, 2))
    rows: list[LagrangianFrame] = []
    ids = np.arange(identities, dtype=np.int64)
    previous = latent[:, 0].copy()
    before_previous = latent[:, 1].copy()
    for tick in range(1, ticks + 1):
        innovation = rng.normal(scale=0.8, size=identities)
        current = 0.35 * previous + innovation
        present = rng.normal(size=(identities, 1))
        target = (
            1.6 * previous
            - 0.45 * before_previous
            + 0.2 * present[:, 0]
        )[:, None]
        rows.append(
            LagrangianFrame(
                tick=tick,
                identity_ids=ids,
                present=present,
                history=current[:, None],
                target=target,
            )
        )
        before_previous, previous = previous, current
    return rows


def _targets(frames: list[LagrangianFrame], ticks: np.ndarray, ids: np.ndarray) -> np.ndarray:
    lookup = {
        (frame.tick, int(identity)): float(frame.target[index, 0])
        for frame in frames
        for index, identity in enumerate(frame.identity_ids)
    }
    return np.asarray([lookup[(int(tick), int(identity))] for tick, identity in zip(ticks, ids)])[:, None]


def _trained_field():
    torch.set_num_threads(1)
    controller = LagrangianRecurrentField(
        LagrangianFieldConfig(
            present_width=1,
            history_width=1,
            target_width=1,
            lags=(1, 2),
            max_identities=8,
        )
    )
    training = _world(17)
    state = controller.fit_baseline(controller.initial_state(), training)
    state = controller.learn_world(state, training)
    return controller, state


def test_recurrent_field_transfers_delayed_identity_authority():
    controller, trained = _trained_field()
    holdout = _world(91, ticks=72)
    aligned = controller.forecast_world(trained, holdout)
    broken = controller.forecast_world(trained, holdout, break_identity=True)
    target = _targets(holdout, aligned.ticks, aligned.identity_ids)
    baseline_rmse = float(np.sqrt(np.mean((aligned.baseline - target) ** 2)))
    aligned_rmse = float(np.sqrt(np.mean((aligned.combined - target) ** 2)))
    broken_rmse = float(np.sqrt(np.mean((broken.combined - target) ** 2)))

    assert aligned.resolved_count == (len(holdout) - 2) * 8
    assert aligned_rmse < 0.20 * baseline_rmse
    assert broken_rmse > 3.0 * aligned_rmse
    assert aligned.identity_mismatch_fraction == 0.0
    assert broken.identity_mismatch_fraction == 1.0
    assert controller.inspect(trained)["adaptive_owner"] == "LagrangianRecurrentState.field"


def test_forecast_is_prewrite_restart_exact_and_target_blind():
    controller, trained = _trained_field()
    holdout = _world(29, ticks=48)
    changed_targets = [
        LagrangianFrame(
            tick=frame.tick,
            identity_ids=frame.identity_ids,
            present=frame.present,
            history=frame.history,
            target=frame.target + 10_000.0,
        )
        for frame in holdout
    ]
    original = controller.forecast_world(trained, holdout)
    blind = controller.forecast_world(trained, changed_targets)
    restarted = controller.import_state(controller.export_state(trained))
    replay = controller.forecast_world(restarted, holdout)

    assert np.array_equal(original.baseline, blind.baseline)
    assert np.array_equal(original.combined, blind.combined)
    assert np.array_equal(original.combined, replay.combined)
    assert controller.state_sha256(restarted) == controller.state_sha256(trained)

    first = holdout[0]
    altered_current = [
        LagrangianFrame(
            tick=first.tick,
            identity_ids=first.identity_ids,
            present=first.present,
            history=first.history * -123.0,
            target=None,
        ),
        *[
            LagrangianFrame(
                tick=frame.tick,
                identity_ids=frame.identity_ids,
                present=frame.present,
                history=frame.history,
                target=None,
            )
            for frame in holdout[1:]
        ],
    ]
    altered = controller.forecast_world(trained, altered_current)
    # The changed current write may affect later steps, but never its own prediction;
    # the first resolvable forecast is tick 3 and therefore reads ticks 1 and 2.
    assert np.array_equal(original.combined[:8], altered.combined[:8]) is False

    third = holdout[2]
    changed_third = [
        LagrangianFrame(
            tick=frame.tick,
            identity_ids=frame.identity_ids,
            present=frame.present,
            history=(frame.history * -123.0 if frame.tick == third.tick else frame.history),
            target=None,
        )
        for frame in holdout
    ]
    prewrite = controller.forecast_world(trained, changed_third)
    assert np.array_equal(original.combined[:8], prewrite.combined[:8])


def test_identity_row_order_is_canonical_field_input():
    controller = LagrangianRecurrentField(
        LagrangianFieldConfig(
            present_width=1,
            history_width=1,
            target_width=1,
            lags=(1, 2),
            max_identities=8,
        )
    )
    ordered = _world(42, ticks=48)
    shuffled = [
        LagrangianFrame(
            tick=frame.tick,
            identity_ids=frame.identity_ids[::-1],
            present=frame.present[::-1],
            history=frame.history[::-1],
            target=frame.target[::-1],
        )
        for frame in ordered
    ]
    left = controller.learn_world(
        controller.fit_baseline(controller.initial_state(), ordered), ordered
    )
    right = controller.learn_world(
        controller.fit_baseline(controller.initial_state(), shuffled), shuffled
    )
    assert controller.state_sha256(left) == controller.state_sha256(right)
