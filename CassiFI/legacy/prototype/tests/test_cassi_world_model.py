"""Focused executable tests for the field-native Cassi world model."""

from __future__ import annotations

import json
from io import BytesIO

import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Callable

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training", _CASSI_FI_ROOT / "verification"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import numpy as np
import torch

from cassi_modal_torch import CassiModalConfig
from cassi_world_model import (
    MAX_RUNTIME_STATE_BYTES,
    CassiTrajectoryBatch,
    CassiWorldModel,
    CassiWorldModelConfig,
    CassiWorldModelError,
    CassiWorldModelLossConfig,
    CassiWorldModelOutput,
    CassiWorldModelState,
    compute_world_model_loss,
    dump_world_model_state_bytes,
    load_world_model_checkpoint,
    load_world_model_state,
    load_world_model_state_bytes,
    save_world_model_checkpoint,
    save_world_model_state,
)


def _config() -> CassiWorldModelConfig:
    return CassiWorldModelConfig(
        observation_dim=3,
        action_dim=2,
        reward_dim=1,
        mode_count=2,
        latent_dim=3,
        model_dim=8,
        hidden_dim=8,
        mlp_layers=1,
        min_std=0.1,
        max_std=0.5,
        modal=CassiModalConfig(
            retained_weight=0.8,
            phi=1.61803398875,
            dt=0.002,
            omega2=8.0,
            coupling=0.5,
            steps_per_layer=1,
        ),
    )


def _batch(config: CassiWorldModelConfig, *, dtype: torch.dtype = torch.float32) -> CassiTrajectoryBatch:
    batch_size, horizon = 2, 3
    observations = torch.arange(batch_size * horizon * config.observation_dim, dtype=dtype).reshape(
        batch_size, horizon, config.observation_dim
    ) / 10.0
    actions = torch.arange(batch_size * horizon * config.action_dim, dtype=dtype).reshape(
        batch_size, horizon, config.action_dim
    ) / 7.0
    rewards = torch.arange(batch_size * horizon * config.reward_dim, dtype=dtype).reshape(
        batch_size, horizon, config.reward_dim
    ) / 11.0
    continues = torch.tensor([[1.0, 1.0, 0.0], [1.0, 0.0, 1.0]], dtype=dtype)
    valid = torch.tensor([[True, True, False], [True, True, True]])
    resets = torch.tensor([[True, False, False], [True, False, True]])
    return CassiTrajectoryBatch(observations, actions, rewards, continues, valid, resets)


def _expect_error(fn: Callable[[], object]) -> None:
    try:
        fn()
    except CassiWorldModelError:
        return
    raise AssertionError("expected CassiWorldModelError")


def _assert_state_close(left: CassiWorldModelState, right: CassiWorldModelState) -> None:
    torch.testing.assert_close(left.field, right.field)
    torch.testing.assert_close(left.stochastic, right.stochastic)
    torch.testing.assert_close(left.step, right.step)


def _assert_output_close(left: CassiWorldModelOutput, right: CassiWorldModelOutput) -> None:
    for name in (
        "observation_mean",
        "observation_log_std",
        "reward_mean",
        "reward_log_std",
        "continue_logits",
        "prior_mean",
        "prior_log_std",
        "field_correction",
        "features",
    ):
        torch.testing.assert_close(getattr(left, name), getattr(right, name))
    assert (left.posterior_mean is None) == (right.posterior_mean is None)
    assert (left.posterior_log_std is None) == (right.posterior_log_std is None)
    if left.posterior_mean is not None:
        torch.testing.assert_close(left.posterior_mean, right.posterior_mean)
    if left.posterior_log_std is not None:
        torch.testing.assert_close(left.posterior_log_std, right.posterior_log_std)
    _assert_state_close(left.final_state, right.final_state)


def test_config_round_trip_and_fingerprint() -> None:
    config = _config()
    restored = CassiWorldModelConfig.from_dict(config.to_dict())
    assert restored == config
    assert restored.fingerprint == config.fingerprint
    assert replace(config, latent_dim=config.latent_dim + 1).fingerprint != config.fingerprint


def test_trajectory_rejects_bad_shapes_and_nonfinite_values() -> None:
    config = _config()
    model = CassiWorldModel(config)
    batch = _batch(config)
    _expect_error(lambda: model.observe(replace(batch, actions=batch.actions[:, :, :1]), sample=False))
    nonfinite = batch.observations.clone()
    nonfinite[0, 0, 0] = float("nan")
    _expect_error(lambda: model.observe(replace(batch, observations=nonfinite), sample=False))
    bad_continue = batch.continues.clone()
    bad_continue[0, 0] = 2.0
    _expect_error(lambda: model.observe(replace(batch, continues=bad_continue), sample=False))


def test_observed_loss_has_finite_gradients() -> None:
    torch.manual_seed(101)
    model = CassiWorldModel(_config())
    batch = _batch(model.config)
    output = model.observe(batch, sample=False)
    loss = compute_world_model_loss(batch, output, CassiWorldModelLossConfig(free_nats=0.0))
    assert bool(torch.isfinite(loss.total))
    loss.total.backward()
    gradients = [parameter.grad for parameter in model.parameters() if parameter.requires_grad]
    assert gradients and all(gradient is not None for gradient in gradients)
    assert all(bool(torch.isfinite(gradient).all()) for gradient in gradients if gradient is not None)
    assert any(bool(gradient.abs().sum() > 0.0) for gradient in gradients if gradient is not None)


def test_observe_sample_false_is_deterministic() -> None:
    torch.manual_seed(103)
    model = CassiWorldModel(_config()).eval()
    batch = _batch(model.config)
    _assert_output_close(model.observe(batch, sample=False), model.observe(batch, sample=False))


def test_batch_observe_matches_repeated_observe_step() -> None:
    torch.manual_seed(107)
    model = CassiWorldModel(_config()).eval()
    batch = _batch(model.config)
    with torch.no_grad():
        observed = model.observe(batch, sample=False)
        state = model.initial_state(batch.batch_size)
        for time in range(batch.horizon):
            step = model.observe_step(
                batch.observations[:, time], batch.actions[:, time], state,
                valid=batch.valid[:, time], reset=batch.resets[:, time], sample=False,
            )
            for name in (
                "observation_mean", "observation_log_std", "reward_mean", "reward_log_std",
                "continue_logits", "prior_mean", "prior_log_std", "posterior_mean",
                "posterior_log_std", "field_correction", "features",
            ):
                torch.testing.assert_close(getattr(observed, name)[:, time], getattr(step, name))
            state = step.state
        _assert_state_close(observed.final_state, state)


def test_reset_clears_field_stochastic_and_step_state() -> None:
    torch.manual_seed(109)
    model = CassiWorldModel(_config()).eval()
    batch = _batch(model.config)
    initial = model.initial_state(batch.batch_size)
    dirty = CassiWorldModelState(
        field=torch.full_like(initial.field, 3.0),
        stochastic=torch.full_like(initial.stochastic, 4.0),
        step=torch.full_like(initial.step, 9),
    )
    with torch.no_grad():
        reset_step = model.observe_step(
            batch.observations[:, 0], batch.actions[:, 0], dirty,
            valid=torch.ones(batch.batch_size, dtype=torch.bool),
            reset=torch.ones(batch.batch_size, dtype=torch.bool), sample=False,
        )
        zero_step = model.observe_step(
            batch.observations[:, 0], batch.actions[:, 0], initial,
            valid=torch.ones(batch.batch_size, dtype=torch.bool),
            reset=torch.zeros(batch.batch_size, dtype=torch.bool), sample=False,
        )
    _assert_state_close(reset_step.state, zero_step.state)
    assert torch.equal(reset_step.state.step, torch.ones(batch.batch_size, dtype=torch.int64))


def test_invalid_padded_step_preserves_state_and_masks_outputs() -> None:
    torch.manual_seed(113)
    model = CassiWorldModel(_config()).eval()
    batch = _batch(model.config)
    initial = model.initial_state(batch.batch_size)
    state = CassiWorldModelState(
        field=torch.full_like(initial.field, 0.25),
        stochastic=torch.full_like(initial.stochastic, -0.5),
        step=torch.tensor([4, 7], dtype=torch.int64),
    )
    with torch.no_grad():
        step = model.observe_step(
            batch.observations[:, 2], batch.actions[:, 2], state,
            valid=torch.zeros(batch.batch_size, dtype=torch.bool),
            reset=torch.zeros(batch.batch_size, dtype=torch.bool), sample=False,
        )
    _assert_state_close(step.state, state)
    for name in (
        "observation_mean", "observation_log_std", "reward_mean", "reward_log_std",
        "continue_logits", "prior_mean", "prior_log_std", "posterior_mean", "posterior_log_std",
        "field_correction", "features",
    ):
        assert torch.equal(getattr(step, name), torch.zeros_like(getattr(step, name)))


def test_imagine_is_prior_only_and_has_expected_shapes() -> None:
    model = CassiWorldModel(_config()).eval()
    batch = _batch(model.config)
    with torch.no_grad():
        output = model.imagine(batch.actions, model.initial_state(batch.batch_size),
                               valid=batch.valid, resets=batch.resets, sample=False)
    assert output.posterior_mean is None and output.posterior_log_std is None
    assert output.observation_mean.shape == batch.observations.shape
    assert output.reward_mean.shape == batch.rewards.shape
    assert output.continue_logits.shape == batch.continues.shape
    assert output.prior_mean.shape == (batch.batch_size, batch.horizon, model.config.latent_dim)
    assert output.final_state.batch_size == batch.batch_size


def test_checkpoint_and_runtime_state_round_trip() -> None:
    torch.manual_seed(127)
    config = _config()
    model = CassiWorldModel(config)
    optimizer = torch.optim.Adam(model.parameters(), lr=1.0e-3)
    batch = _batch(config)
    output = model.observe(batch, sample=False)
    compute_world_model_loss(batch, output, CassiWorldModelLossConfig(free_nats=0.0)).total.backward()
    optimizer.step()
    state = model.observe(batch, sample=False).final_state.detach()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        checkpoint_path, runtime_path = root / "model.pt", root / "state.pt"
        checkpoint_digest = save_world_model_checkpoint(
            checkpoint_path, model, optimizer=optimizer, step=7,
            metadata={"test": "round-trip", "count": 1},
        )
        runtime_digest = save_world_model_state(runtime_path, model, state)
        assert len(checkpoint_digest) == 64 and len(runtime_digest) == 64
        loaded = load_world_model_checkpoint(checkpoint_path, expected_config=config)
        assert loaded.step == 7 and loaded.metadata == {"test": "round-trip", "count": 1}
        assert loaded.optimizer_state is not None
        for name, value in model.state_dict().items():
            torch.testing.assert_close(value, loaded.model.state_dict()[name])
        _assert_state_close(state, load_world_model_state(runtime_path, loaded.model))


def test_runtime_state_bytes_round_trip_returns_owned_detached_tensors() -> None:
    model = CassiWorldModel(_config()).eval()
    state = model.initial_state(2)
    encoded = dump_world_model_state_bytes(model, state)
    restored = load_world_model_state_bytes(encoded, model)
    _assert_state_close(state, restored)
    assert not restored.field.requires_grad
    assert not restored.stochastic.requires_grad
    assert not restored.step.requires_grad
    assert restored.field.data_ptr() != state.field.data_ptr()
    assert restored.stochastic.data_ptr() != state.stochastic.data_ptr()
    assert restored.step.data_ptr() != state.step.data_ptr()
    restored.field[0, 0] += 1.0
    assert torch.equal(state.field, model.initial_state(2).field)


def test_runtime_state_bytes_reject_malformed_oversize_and_wrong_types() -> None:
    model = CassiWorldModel(_config())
    for payload in (True, bytearray(b"payload"), memoryview(b"payload"), "payload", b""):
        _expect_error(lambda payload=payload: load_world_model_state_bytes(payload, model))
    _expect_error(lambda: load_world_model_state_bytes(b"not a torch archive", model))
    _expect_error(
        lambda: load_world_model_state_bytes(bytes(MAX_RUNTIME_STATE_BYTES + 1), model)
    )
    with BytesIO() as stream:
        torch.save({"schema": "wrong"}, stream)
        _expect_error(lambda: load_world_model_state_bytes(stream.getvalue(), model))


def test_runtime_state_byte_and_path_save_load_are_equivalent() -> None:
    model = CassiWorldModel(_config()).eval()
    state = model.initial_state(2)
    encoded = dump_world_model_state_bytes(model, state)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "state.pt"
        digest = save_world_model_state(path, model, state)
        assert path.read_bytes() == encoded
        assert digest == __import__("hashlib").sha256(encoded).hexdigest()
        _assert_state_close(state, load_world_model_state_bytes(encoded, model))
        _assert_state_close(state, load_world_model_state(path, model))


def test_runtime_state_bytes_reject_wrong_model_identity() -> None:
    config = _config()
    model = CassiWorldModel(config)
    encoded = dump_world_model_state_bytes(model, model.initial_state(2))
    wrong_model = CassiWorldModel(replace(config, latent_dim=config.latent_dim + 1))
    _expect_error(lambda: load_world_model_state_bytes(encoded, wrong_model))


def test_incompatible_checkpoint_and_runtime_config_are_rejected() -> None:
    config = _config()
    model = CassiWorldModel(config)
    state = model.initial_state(2)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        checkpoint_path, runtime_path = root / "model.pt", root / "state.pt"
        save_world_model_checkpoint(checkpoint_path, model)
        save_world_model_state(runtime_path, model, state)
        incompatible = replace(config, latent_dim=config.latent_dim + 1)
        _expect_error(lambda: load_world_model_checkpoint(checkpoint_path, expected_config=incompatible))
        _expect_error(lambda: load_world_model_state(runtime_path, CassiWorldModel(incompatible)))


def test_masked_loss_ignores_invalid_values() -> None:
    torch.manual_seed(131)
    config = _config()
    model = CassiWorldModel(config).eval()
    base = _batch(config)
    valid = torch.tensor([[True, False, True], [True, True, False]])
    base = replace(base, valid=valid, resets=torch.tensor([[True, False, False], [True, False, False]]))
    observations, actions = base.observations.clone(), base.actions.clone()
    rewards, continues = base.rewards.clone(), base.continues.clone()
    observations[~valid], actions[~valid], rewards[~valid], continues[~valid] = 10_000.0, -10_000.0, 10_000.0, 0.0
    changed = replace(base, observations=observations, actions=actions, rewards=rewards, continues=continues)
    with torch.no_grad():
        first_output, second_output = model.observe(base, sample=False), model.observe(changed, sample=False)
    first_loss = compute_world_model_loss(base, first_output, CassiWorldModelLossConfig(free_nats=0.0))
    second_loss = compute_world_model_loss(changed, second_output, CassiWorldModelLossConfig(free_nats=0.0))
    for left, right in zip(first_loss, second_loss):
        torch.testing.assert_close(left, right)


def test_tiny_cli_trainer_creates_loadable_checkpoint_and_summary() -> None:
    config = _config()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        data_path, checkpoint_path, config_path = (
            root / "tiny.npz",
            root / "tiny-checkpoint.pt",
            root / "config.json",
        )
        batch = _batch(config)
        np.savez(data_path, observations=batch.observations.numpy(), actions=batch.actions.numpy(),
                 rewards=batch.rewards.numpy(), continues=batch.continues.numpy(),
                 valid=batch.valid.numpy(), resets=batch.resets.numpy())
        config_path.write_text(json.dumps(config.to_dict()), encoding="utf-8")
        command = [sys.executable, str(_CASSI_FI_ROOT / "training" / "train_cassi_world_model.py"),
                   "--data", str(data_path), "--output", str(checkpoint_path),
                   "--observation-dim", str(config.observation_dim), "--action-dim", str(config.action_dim),
                   "--reward-dim", str(config.reward_dim), "--config-json", str(config_path),
                   "--epochs", "1", "--batch-size", "2", "--learning-rate", "0.001", "--seed", "137",
                   "--validation-fraction", "0"]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        assert checkpoint_path.is_file() and completed.stdout.strip()
        summary = json.loads(completed.stdout)
        assert isinstance(summary, dict) and summary.get("checkpoint") == str(checkpoint_path)
        assert summary.get("epochs") == 1
        assert load_world_model_checkpoint(checkpoint_path, expected_config=config).step == 1

        resume_command = list(command)
        resume_command[resume_command.index("--epochs") + 1] = "2"
        resume_command.extend(["--resume", str(checkpoint_path)])
        resumed = subprocess.run(resume_command, check=True, capture_output=True, text=True)
        resumed_summary = json.loads(resumed.stdout)
        assert resumed_summary.get("epochs") == 2
        assert load_world_model_checkpoint(checkpoint_path, expected_config=config).step == 2

if __name__ == "__main__":
    test_config_round_trip_and_fingerprint()
    test_trajectory_rejects_bad_shapes_and_nonfinite_values()
    test_observed_loss_has_finite_gradients()
    test_observe_sample_false_is_deterministic()
    test_batch_observe_matches_repeated_observe_step()
    test_reset_clears_field_stochastic_and_step_state()
    test_invalid_padded_step_preserves_state_and_masks_outputs()
    test_imagine_is_prior_only_and_has_expected_shapes()
    test_checkpoint_and_runtime_state_round_trip()
    test_runtime_state_bytes_round_trip_returns_owned_detached_tensors()
    test_runtime_state_bytes_reject_malformed_oversize_and_wrong_types()
    test_runtime_state_byte_and_path_save_load_are_equivalent()
    test_runtime_state_bytes_reject_wrong_model_identity()
    test_incompatible_checkpoint_and_runtime_config_are_rejected()
    test_masked_loss_ignores_invalid_values()
    test_tiny_cli_trainer_creates_loadable_checkpoint_and_summary()
    print("Cassi world-model tests passed")
