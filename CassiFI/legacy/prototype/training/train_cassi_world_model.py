"""Train the Cassi field-native world model from strict ``.npz`` trajectories.

The input archive contains six arrays, one row per episode:
``observations [N,T,O]``, ``actions [N,T,A]``, ``rewards [N,T,R]``,
``continues [N,T]``, ``valid [N,T]``, and ``resets [N,T]``. Invalid padded
steps are carried through the recurrent model but are excluded from every
loss term. The command-line surface deliberately fails closed for malformed
arrays and incompatible resume checkpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any, Mapping, Sequence
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

import numpy as np
import torch

try:
    from .cassi_world_model import (
        CassiTrajectoryBatch,
        CassiWorldModel,
        CassiWorldModelCheckpoint,
        CassiWorldModelConfig,
        CassiWorldModelError,
        CassiWorldModelLossConfig,
        compute_world_model_loss,
        load_world_model_checkpoint,
        save_world_model_checkpoint,
    )
except ImportError:  # direct script execution
    from cassi_world_model import (  # type: ignore[no-redef]
        CassiTrajectoryBatch,
        CassiWorldModel,
        CassiWorldModelCheckpoint,
        CassiWorldModelConfig,
        CassiWorldModelError,
        CassiWorldModelLossConfig,
        compute_world_model_loss,
        load_world_model_checkpoint,
        save_world_model_checkpoint,
    )


TRAJECTORY_KEYS = frozenset(("observations", "actions", "rewards", "continues", "valid", "resets"))
TRAINING_RECEIPT_SCHEMA = "cassi.world-model.training-receipt.v1"
DEFAULT_GRADIENT_CLIP_NORM = 100.0


def _fail(message: str) -> None:
    raise CassiWorldModelError(message)


def _positive_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(f"{name} must be a positive integer")
    return value


def _nonnegative_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{name} must be a non-negative integer")
    return value


def _finite_positive(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{name} must be positive and finite")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        _fail(f"{name} must be positive and finite")
    return result


def _finite_nonnegative(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{name} must be non-negative and finite")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        _fail(f"{name} must be non-negative and finite")
    return result


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    if not path.is_file():
        _fail(f"trajectory archive does not exist: {path}")
    try:
        with np.load(path, allow_pickle=False) as archive:
            names = set(archive.files)
            missing = sorted(TRAJECTORY_KEYS - names)
            extra = sorted(names - TRAJECTORY_KEYS)
            if missing:
                _fail(f"trajectory archive is missing arrays: {', '.join(missing)}")
            if extra:
                _fail(f"trajectory archive contains unexpected arrays: {', '.join(extra)}")
            return {name: np.asarray(archive[name]) for name in TRAJECTORY_KEYS}
    except CassiWorldModelError:
        raise
    except Exception as exc:
        _fail(f"trajectory archive cannot be read: {type(exc).__name__}: {exc}")
    raise AssertionError("unreachable")


def _require_value_array(name: str, value: np.ndarray) -> None:
    if not np.issubdtype(value.dtype, np.floating):
        _fail(f"{name} must use a floating dtype")
    if not np.isfinite(value).all():
        _fail(f"{name} contains non-finite values")


def _require_mask_array(name: str, value: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if value.ndim != 2 or value.shape != shape:
        _fail(f"{name} must have exact shape [N, T] = {shape}")
    if value.dtype == np.bool_:
        return value.astype(np.bool_, copy=False)
    if not np.issubdtype(value.dtype, np.integer):
        _fail(f"{name} must be boolean or a 0/1 integer mask")
    if np.any((value != 0) & (value != 1)):
        _fail(f"{name} must contain only 0/1 integer values")
    return value.astype(np.bool_, copy=False)


def load_trajectory_npz(
    path: Path | str,
    observation_dim: int,
    action_dim: int,
    reward_dim: int = 1,
) -> CassiTrajectoryBatch:
    """Load and strictly validate one padded episode archive."""
    _positive_int("observation_dim", observation_dim)
    _positive_int("action_dim", action_dim)
    _positive_int("reward_dim", reward_dim)
    arrays = _load_npz(Path(path))
    observations, actions, rewards, continues = (
        arrays["observations"], arrays["actions"], arrays["rewards"], arrays["continues"]
    )
    if observations.ndim != 3 or observations.shape[2] != observation_dim:
        _fail(f"observations must have exact shape [N, T, {observation_dim}]")
    episodes, horizon, _ = observations.shape
    if episodes < 1 or horizon < 1:
        _fail("observations require N >= 1 and T >= 1")
    if actions.ndim != 3 or actions.shape != (episodes, horizon, action_dim):
        _fail(f"actions must have exact shape [N, T, {action_dim}]")
    if rewards.ndim != 3 or rewards.shape != (episodes, horizon, reward_dim):
        _fail(f"rewards must have exact shape [N, T, {reward_dim}]")
    if continues.ndim != 2 or continues.shape != (episodes, horizon):
        _fail("continues must have exact shape [N, T]")
    for name, value in (
        ("observations", observations),
        ("actions", actions),
        ("rewards", rewards),
        ("continues", continues),
    ):
        _require_value_array(name, value)
    if np.any((continues < 0.0) | (continues > 1.0)):
        _fail("continues must be in [0, 1]")
    expected_mask_shape = (episodes, horizon)
    valid = _require_mask_array("valid", arrays["valid"], expected_mask_shape)
    resets = _require_mask_array("resets", arrays["resets"], expected_mask_shape)
    if not np.all(valid.any(axis=1)):
        _fail("each trajectory row must contain at least one valid step")
    if np.any(resets & ~valid):
        _fail("resets cannot occur on invalid steps")
    values = tuple(
        torch.from_numpy(np.ascontiguousarray(value, dtype=np.float32))
        for value in (observations, actions, rewards, continues)
    )
    valid_tensor = torch.from_numpy(np.ascontiguousarray(valid, dtype=np.bool_))
    resets_tensor = torch.from_numpy(np.ascontiguousarray(resets, dtype=np.bool_))
    batch = CassiTrajectoryBatch(*values, valid_tensor, resets_tensor)
    batch.validate(CassiWorldModelConfig(observation_dim, action_dim, reward_dim))
    return batch


def _batch_digest(batch: CassiTrajectoryBatch) -> str:
    digest = hashlib.sha256()
    for name, tensor in (
        ("observations", batch.observations),
        ("actions", batch.actions),
        ("rewards", batch.rewards),
        ("continues", batch.continues),
        ("valid", batch.valid),
        ("resets", batch.resets),
    ):
        array = np.ascontiguousarray(tensor.detach().cpu().numpy())
        digest.update(name.encode("utf-8"))
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(repr(tuple(array.shape)).encode("ascii"))
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _parse_json_file(path: Path, description: str) -> Mapping[str, Any]:
    if not path.is_file():
        _fail(f"{description} does not exist: {path}")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"invalid JSON constant {token}")),
        )
    except Exception as exc:
        _fail(f"{description} is not valid JSON: {type(exc).__name__}: {exc}")
    if not isinstance(value, Mapping):
        _fail(f"{description} must contain a JSON object")
    return value


def _coerce_model_config(
    value: CassiWorldModelConfig | Mapping[str, Any] | None,
    observation_dim: int,
    action_dim: int,
    reward_dim: int,
) -> CassiWorldModelConfig:
    _positive_int("observation_dim", observation_dim)
    _positive_int("action_dim", action_dim)
    _positive_int("reward_dim", reward_dim)
    if value is None:
        return CassiWorldModelConfig(observation_dim, action_dim, reward_dim)
    if isinstance(value, CassiWorldModelConfig):
        config = value
    elif isinstance(value, Mapping):
        payload = dict(value)
        for name, expected in (
            ("observation_dim", observation_dim),
            ("action_dim", action_dim),
            ("reward_dim", reward_dim),
        ):
            supplied = payload.get(name, expected)
            if supplied != expected:
                _fail(f"model config {name} does not match the CLI dimension")
            payload[name] = expected
        try:
            config = CassiWorldModelConfig.from_dict(payload)
        except (TypeError, ValueError) as exc:
            _fail(f"invalid model configuration: {exc}")
    else:
        _fail("model configuration must be a CassiWorldModelConfig or mapping")
    if (config.observation_dim, config.action_dim, config.reward_dim) != (observation_dim, action_dim, reward_dim):
        _fail("model configuration dimensions do not match the requested dimensions")
    return config


def _coerce_loss_config(value: CassiWorldModelLossConfig | Mapping[str, Any] | None) -> CassiWorldModelLossConfig:
    if value is None:
        return CassiWorldModelLossConfig()
    if isinstance(value, CassiWorldModelLossConfig):
        return value
    if not isinstance(value, Mapping):
        _fail("loss configuration must be a CassiWorldModelLossConfig or mapping")
    try:
        return CassiWorldModelLossConfig.from_dict(value)
    except (TypeError, ValueError) as exc:
        _fail(f"invalid loss configuration: {exc}")
    raise AssertionError("unreachable")


def _seed_everything(seed: int) -> None:
    _nonnegative_int("seed", seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)


def _split_episodes(episode_count: int, validation_fraction: float, seed: int) -> tuple[list[int], list[int]]:
    if not math.isfinite(validation_fraction) or not 0.0 <= validation_fraction < 1.0:
        _fail("validation_fraction must be finite and in [0, 1)")
    order = np.arange(episode_count, dtype=np.int64)
    np.random.default_rng(seed).shuffle(order)
    if validation_fraction <= 0.0 or episode_count < 2:
        validation_count = 0
    else:
        validation_count = min(episode_count - 1, max(1, int(math.ceil(episode_count * validation_fraction))))
    validation = sorted(int(index) for index in order[:validation_count])
    train = sorted(int(index) for index in order[validation_count:])
    if not train:
        _fail("episode split produced an empty training set")
    return train, validation


def _epoch_order(indices: Sequence[int], seed: int, epoch: int) -> list[int]:
    order = np.asarray(indices, dtype=np.int64).copy()
    np.random.default_rng(seed + 1_000_003 * epoch).shuffle(order)
    return [int(index) for index in order]


def _state_is_finite(value: Any) -> bool:
    if torch.is_tensor(value):
        return not value.dtype.is_floating_point or bool(torch.isfinite(value).all().item())
    if isinstance(value, Mapping):
        return all(_state_is_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_state_is_finite(item) for item in value)
    return True


def _run_epoch(
    model: CassiWorldModel,
    batch: CassiTrajectoryBatch,
    indices: Sequence[int],
    *,
    batch_size: int,
    loss_config: CassiWorldModelLossConfig,
    optimizer: torch.optim.Optimizer | None,
    device: torch.device,
    train: bool,
    gradient_clip_norm: float,
) -> dict[str, float | int | bool]:
    if not indices:
        return {"available": False, "episodes": 0, "batches": 0, "valid_steps": 0}
    model.train(mode=train)
    totals: dict[str, float] = {}
    valid_steps = 0
    batches = 0
    for start in range(0, len(indices), batch_size):
        selected = indices[start : start + batch_size]
        selector = torch.tensor(selected, dtype=torch.int64)
        current = batch.index_select(selector).to(device=device, dtype=torch.float32)
        if train:
            if optimizer is None:
                _fail("training epoch requires an optimizer")
            optimizer.zero_grad(set_to_none=True)
            output = model.observe(current, sample=True)
            losses = compute_world_model_loss(current, output, loss_config)
            if not bool(torch.isfinite(losses.total).item()):
                _fail("training loss became non-finite")
            losses.total.backward()
            for parameter in model.parameters():
                if parameter.grad is not None and not bool(torch.isfinite(parameter.grad).all().item()):
                    _fail("training gradient became non-finite")
            gradient_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip_norm)
            if not bool(torch.isfinite(torch.as_tensor(gradient_norm)).item()):
                _fail("gradient norm became non-finite")
            optimizer.step()
        else:
            with torch.no_grad():
                output = model.observe(current, sample=False)
                losses = compute_world_model_loss(current, output, loss_config)
        metrics = losses.detached_metrics()
        step_count = int(current.valid.sum().item())
        valid_steps += step_count
        batches += 1
        for name, value in metrics.items():
            totals[name] = totals.get(name, 0.0) + value * step_count
    if valid_steps < 1:
        _fail("epoch has no valid time steps")
    result: dict[str, float | int | bool] = {"available": True, "episodes": len(indices), "batches": batches, "valid_steps": valid_steps}
    result.update({name: value / valid_steps for name, value in totals.items()})
    return result


def _metadata(
    *,
    data: Path | str,
    trajectory: CassiTrajectoryBatch,
    observation_dim: int,
    action_dim: int,
    reward_dim: int,
    config: CassiWorldModelConfig,
    loss: CassiWorldModelLossConfig,
    dataset_digest: str,
    seed: int,
    validation_fraction: float,
    train_indices: list[int],
    validation_indices: list[int],
    epochs: int,
    completed_epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
    gradient_clip_norm: float,
    device: torch.device,
    history: list[dict[str, Any]],
    metrics: Mapping[str, Any],
    resume: Path | str | None,
    start_epoch: int,
) -> dict[str, Any]:
    return {
        "schema": TRAINING_RECEIPT_SCHEMA,
        "data": str(Path(data)),
        "dataset_digest": dataset_digest,
        "dataset": {
            "episodes": trajectory.batch_size,
            "horizon": trajectory.horizon,
            "observation_dim": observation_dim,
            "action_dim": action_dim,
            "reward_dim": reward_dim,
        },
        "model_config": config.to_dict(),
        "loss_config": loss.to_dict(),
        "config_fingerprint": config.fingerprint,
        "fingerprint": config.fingerprint,
        "splits": {
            "seed": seed,
            "validation_fraction": float(validation_fraction),
            "train_episodes": train_indices,
            "validation_episodes": validation_indices,
        },
        "training": {
            "epochs_requested": epochs,
            "completed_epochs": completed_epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "weight_decay": weight_decay,
            "gradient_clip_norm": gradient_clip_norm,
            "device": str(device),
            "seed": seed,
        },
        "epoch_receipts": history,
        "metrics": dict(metrics),
        "resume": {"checkpoint": str(resume) if resume is not None else None, "start_epoch": start_epoch},
    }


def train(
    data: Path | str,
    output: Path | str,
    observation_dim: int,
    action_dim: int,
    reward_dim: int = 1,
    *,
    model_config: CassiWorldModelConfig | Mapping[str, Any] | None = None,
    loss_config: CassiWorldModelLossConfig | Mapping[str, Any] | None = None,
    config: CassiWorldModelConfig | Mapping[str, Any] | None = None,
    loss: CassiWorldModelLossConfig | Mapping[str, Any] | None = None,
    epochs: int = 1,
    batch_size: int = 8,
    learning_rate: float = 1e-3,
    weight_decay: float = 0.0,
    seed: int = 0,
    device: torch.device | str = "cpu",
    validation_fraction: float = 0.2,
    resume: Path | str | None = None,
    gradient_clip_norm: float = DEFAULT_GRADIENT_CLIP_NORM,
) -> dict[str, Any]:
    """Train a model and atomically persist a checkpoint plus receipt metadata."""
    if model_config is not None and config is not None:
        _fail("use only one of model_config and config")
    if loss_config is not None and loss is not None:
        _fail("use only one of loss_config and loss")
    model_config = model_config if model_config is not None else config
    loss_config = loss_config if loss_config is not None else loss
    _positive_int("epochs", epochs)
    _positive_int("batch_size", batch_size)
    learning_rate = _finite_positive("learning_rate", learning_rate)
    weight_decay = _finite_nonnegative("weight_decay", weight_decay)
    gradient_clip_norm = _finite_positive("gradient_clip_norm", gradient_clip_norm)
    _nonnegative_int("seed", seed)
    if not math.isfinite(validation_fraction) or not 0.0 <= validation_fraction < 1.0:
        _fail("validation_fraction must be finite and in [0, 1)")
    try:
        target_device = torch.device(device)
    except Exception as exc:
        _fail(f"invalid device: {exc}")

    trajectory = load_trajectory_npz(data, observation_dim, action_dim, reward_dim)
    dataset_digest = _batch_digest(trajectory)
    config_value = _coerce_model_config(model_config, observation_dim, action_dim, reward_dim)
    loss_value = _coerce_loss_config(loss_config)
    _seed_everything(seed)

    resumed: CassiWorldModelCheckpoint | None = None
    if resume is not None:
        resumed = load_world_model_checkpoint(resume, device=target_device, expected_config=config_value if model_config is not None else None)
        if model_config is None:
            config_value = resumed.model.config
            if (config_value.observation_dim, config_value.action_dim, config_value.reward_dim) != (observation_dim, action_dim, reward_dim):
                _fail("resume checkpoint dimensions do not match the requested dimensions")
        if resumed.optimizer_state is None:
            _fail("resume checkpoint does not contain optimizer state")
        previous_digest = resumed.metadata.get("dataset_digest")
        if previous_digest is not None and previous_digest != dataset_digest:
            _fail("resume checkpoint belongs to a different dataset")
        previous_loss = resumed.metadata.get("loss_config")
        if previous_loss is not None and previous_loss != loss_value.to_dict():
            _fail("resume checkpoint loss configuration is incompatible")
        model = resumed.model
        start_epoch = resumed.step
        if start_epoch > epochs:
            _fail("resume checkpoint has completed more epochs than requested")
    else:
        model = CassiWorldModel(config_value).to(device=target_device)
        start_epoch = 0
    if model.config != config_value:
        _fail("model configuration is incompatible with the requested configuration")
    model = model.to(device=target_device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    if resumed is not None:
        try:
            optimizer.load_state_dict(resumed.optimizer_state)
        except (KeyError, RuntimeError, ValueError, TypeError) as exc:
            _fail(f"resume optimizer state is incompatible: {exc}")
        if not _state_is_finite(optimizer.state_dict()):
            _fail("resume optimizer state contains non-finite values")

    train_indices, validation_indices = _split_episodes(trajectory.batch_size, float(validation_fraction), seed)
    previous_metadata = resumed.metadata if resumed is not None else {}
    history_value = previous_metadata.get("epoch_receipts", [])
    history: list[dict[str, Any]] = [dict(item) for item in history_value] if isinstance(history_value, list) and all(isinstance(item, Mapping) for item in history_value) else []
    last_train: dict[str, Any] | None = None
    last_validation: dict[str, Any] | None = None
    checkpoint_hash: str | None = None
    for completed_epoch in range(start_epoch, epochs):
        epoch_number = completed_epoch + 1
        order = _epoch_order(train_indices, seed, epoch_number)
        train_metrics = _run_epoch(
            model, trajectory, order, batch_size=batch_size, loss_config=loss_value, optimizer=optimizer,
            device=target_device, train=True, gradient_clip_norm=gradient_clip_norm,
        )
        validation_metrics = _run_epoch(
            model, trajectory, validation_indices, batch_size=batch_size, loss_config=loss_value, optimizer=None,
            device=target_device, train=False, gradient_clip_norm=gradient_clip_norm,
        )
        last_train = dict(train_metrics)
        last_validation = dict(validation_metrics)
        history.append({"epoch": epoch_number, "train": train_metrics, "validation": validation_metrics})
        metadata = _metadata(
            data=data, trajectory=trajectory, observation_dim=observation_dim, action_dim=action_dim, reward_dim=reward_dim,
            config=config_value, loss=loss_value, dataset_digest=dataset_digest, seed=seed,
            validation_fraction=float(validation_fraction), train_indices=train_indices, validation_indices=validation_indices,
            epochs=epochs, completed_epochs=epoch_number, batch_size=batch_size, learning_rate=learning_rate,
            weight_decay=weight_decay, gradient_clip_norm=gradient_clip_norm, device=target_device, history=history,
            metrics={"train": train_metrics, "validation": validation_metrics}, resume=resume, start_epoch=start_epoch,
        )
        checkpoint_hash = save_world_model_checkpoint(output, model, optimizer=optimizer, step=epoch_number, metadata=metadata)

    if checkpoint_hash is None:
        metadata = _metadata(
            data=data, trajectory=trajectory, observation_dim=observation_dim, action_dim=action_dim, reward_dim=reward_dim,
            config=config_value, loss=loss_value, dataset_digest=dataset_digest, seed=seed,
            validation_fraction=float(validation_fraction), train_indices=train_indices, validation_indices=validation_indices,
            epochs=epochs, completed_epochs=start_epoch, batch_size=batch_size, learning_rate=learning_rate,
            weight_decay=weight_decay, gradient_clip_norm=gradient_clip_norm, device=target_device, history=history,
            metrics=previous_metadata.get("metrics", {"train": last_train, "validation": last_validation}), resume=resume,
            start_epoch=start_epoch,
        )
        checkpoint_hash = save_world_model_checkpoint(output, model, optimizer=optimizer, step=start_epoch, metadata=metadata)

    summary = {
        "status": "ok", "checkpoint": str(output), "checkpoint_sha256": checkpoint_hash,
        "config_fingerprint": config_value.fingerprint, "dataset_digest": dataset_digest,
        "episodes": trajectory.batch_size, "horizon": trajectory.horizon,
        "train_episodes": len(train_indices), "validation_episodes": len(validation_indices),
        "epochs": epochs, "completed_epochs": epochs,
        "metrics": {"train": last_train, "validation": last_validation},
    }
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="strict .npz trajectory archive")
    parser.add_argument("--output", type=Path, required=True, help="checkpoint output path")
    parser.add_argument("--observation-dim", type=int, required=True)
    parser.add_argument("--action-dim", type=int, required=True)
    parser.add_argument("--reward-dim", type=int, default=1)
    parser.add_argument("--config-json", "--config", dest="config_json", type=Path, default=None)
    parser.add_argument("--loss-json", "--loss-config", dest="loss_json", type=Path, default=None)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--resume", "--resume-checkpoint", dest="resume", type=Path, default=None)
    parser.add_argument("--gradient-clip-norm", type=float, default=DEFAULT_GRADIENT_CLIP_NORM)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        model_config = _parse_json_file(args.config_json, "model config JSON") if args.config_json is not None else None
        loss_config = _parse_json_file(args.loss_json, "loss config JSON") if args.loss_json is not None else None
        summary = train(
            args.data, args.output, args.observation_dim, args.action_dim, args.reward_dim,
            model_config=model_config, loss_config=loss_config, epochs=args.epochs,
            batch_size=args.batch_size, learning_rate=args.learning_rate, weight_decay=args.weight_decay,
            seed=args.seed, device=args.device, validation_fraction=args.validation_fraction,
            resume=args.resume, gradient_clip_norm=args.gradient_clip_norm,
        )
    except (CassiWorldModelError, OSError, RuntimeError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
