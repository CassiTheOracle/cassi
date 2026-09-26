"""Train the compact feature-token decoder on causal world-model priors.

The world model and candidate output rows are frozen.  The only trainable
parameters are the compact residual adapter and temperature in
``cassi_feature_token_decoder``; candidate classification never constructs a
vocabulary-sized trainable head.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch.nn import functional as F

try:
    from .cassi_feature_token_decoder import (
        CassiFeatureTokenDecoder,
        CassiFeatureTokenDecoderConfig,
        CassiFeatureTokenDecoderError,
        load_feature_token_decoder_checkpoint,
        save_feature_token_decoder_checkpoint,
    )
    from .cassi_feature_token_pipeline import (
        CandidateAssets,
        FeatureTokenPipelineError,
        Normalization,
        causal_prior_features,
        episode_records,
        load_candidate_assets,
        load_text_metadata,
        sha256_array,
        sha256_file,
        supervision_rows,
        target_ids,
    )
    from .cassi_world_model import (
        CassiTrajectoryBatch,
        CassiWorldModelError,
        load_world_model_checkpoint,
    )
    from .train_cassi_world_model import load_trajectory_npz
except ImportError:  # direct script execution
    from cassi_feature_token_decoder import (  # type: ignore[no-redef]
        CassiFeatureTokenDecoder,
        CassiFeatureTokenDecoderConfig,
        CassiFeatureTokenDecoderError,
        load_feature_token_decoder_checkpoint,
        save_feature_token_decoder_checkpoint,
    )
    from cassi_feature_token_pipeline import (  # type: ignore[no-redef]
        CandidateAssets,
        FeatureTokenPipelineError,
        Normalization,
        causal_prior_features,
        episode_records,
        load_candidate_assets,
        load_text_metadata,
        sha256_array,
        sha256_file,
        supervision_rows,
        target_ids,
    )
    from cassi_world_model import CassiTrajectoryBatch, CassiWorldModelError  # type: ignore[no-redef]
    from cassi_world_model import load_world_model_checkpoint  # type: ignore[no-redef]
    from train_cassi_world_model import load_trajectory_npz  # type: ignore[no-redef]


TRAINING_RECEIPT_SCHEMA = "cassi.feature-token-decoder.training-receipt.v1"
OPTIMIZER_SCHEMA = "cassi.feature-token-decoder.optimizer-state.v1"
REQUIRED_FINGERPRINTS = (
    "world_checkpoint_sha256",
    "normalization_sha256",
    "metadata_sha256",
    "data_sha256",
    "candidate_npz_sha256",
    "candidate_json_sha256",
)


def _fail(message: str) -> None:
    raise CassiFeatureTokenDecoderError(message)


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(f"{name} must be a positive integer")
    return int(value)


def _nonnegative_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{name} must be a non-negative integer")
    return int(value)


def _finite_positive(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{name} must be positive and finite")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        _fail(f"{name} must be positive and finite")
    return result


def _finite_nonnegative(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{name} must be non-negative and finite")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        _fail(f"{name} must be non-negative and finite")
    return result


def _seed_everything(seed: int) -> None:
    _nonnegative_int("seed", seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _json_finite(value: Any, label: str = "value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail(f"{label} contains a non-finite number")
        return
    if torch.is_tensor(value):
        if value.dtype.is_floating_point and not bool(torch.isfinite(value).all().item()):
            _fail(f"{label} contains a non-finite tensor")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) and not isinstance(key, (int, float)):
                _fail(f"{label} contains a non-JSON key")
            _json_finite(item, f"{label}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _json_finite(item, f"{label}[{index}]")
        return
    _fail(f"{label} contains unsupported value {type(value).__name__}")


def _cpu_tree(value: Any) -> Any:
    if torch.is_tensor(value):
        return value.detach().cpu().clone()
    if isinstance(value, Mapping):
        return {key: _cpu_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_cpu_tree(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_cpu_tree(item) for item in value)
    return value


def _state_is_finite(value: Any) -> bool:
    if torch.is_tensor(value):
        return (not value.dtype.is_floating_point) or bool(torch.isfinite(value).all().item())
    if isinstance(value, Mapping):
        return all(_state_is_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_state_is_finite(item) for item in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return True


def _asset_fingerprints(
    *,
    world_checkpoint: Path,
    data: Path,
    normalization: Path,
    metadata: Path,
    candidate_npz: Path,
    candidate_json: Path,
    assets: CandidateAssets,
) -> dict[str, Any]:
    return {
        "world_checkpoint_sha256": sha256_file(world_checkpoint),
        "data_sha256": sha256_file(data),
        "normalization_sha256": sha256_file(normalization),
        "metadata_sha256": sha256_file(metadata),
        "candidate_npz_sha256": sha256_file(candidate_npz),
        "candidate_json_sha256": sha256_file(candidate_json),
        "candidate_token_ids_sha256": sha256_array(assets.token_ids),
        "candidate_rows_sha256": sha256_array(assets.rows),
    }


def _load_training_context(
    *,
    world_checkpoint: Path,
    data: Path,
    normalization: Path,
    metadata: Path,
    candidate_npz: Path,
    candidate_json: Path,
    device: torch.device,
) -> tuple[Any, CassiTrajectoryBatch, Normalization, dict[str, Any], CandidateAssets, dict[str, Any]]:
    world_receipt = load_world_model_checkpoint(world_checkpoint, device=device)
    world = world_receipt.model.to(device=device)
    world.eval()
    for parameter in world.parameters():
        parameter.requires_grad_(False)
    config = world.config
    trajectory = load_trajectory_npz(
        data,
        config.observation_dim,
        config.action_dim,
        config.reward_dim,
    )
    trajectory = trajectory.to(device)
    normalizer = Normalization.load(normalization)
    if normalizer.observation_mean.size != config.observation_dim:
        _fail("normalization observation dimension does not match the world model")
    if normalizer.action_mean.size != config.action_dim:
        _fail("normalization action dimension does not match the world model")
    metadata_value = load_text_metadata(metadata)
    assets = load_candidate_assets(candidate_npz, candidate_json)
    if assets.rows.shape[1] != config.observation_dim:
        _fail("candidate rows feature dimension does not match the world model observation dimension")
    fingerprints = _asset_fingerprints(
        world_checkpoint=world_checkpoint,
        data=data,
        normalization=normalization,
        metadata=metadata,
        candidate_npz=candidate_npz,
        candidate_json=candidate_json,
        assets=assets,
    )
    return world, trajectory, normalizer, metadata_value, assets, fingerprints


def _checkpoint_metadata_compatible(
    previous: Mapping[str, Any], expected: Mapping[str, Any], config: CassiFeatureTokenDecoderConfig
) -> None:
    if previous.get("schema") != TRAINING_RECEIPT_SCHEMA:
        _fail("resume checkpoint training metadata schema mismatch")
    if previous.get("decoder_config_fingerprint") != config.fingerprint:
        _fail("resume checkpoint decoder configuration is incompatible")
    old_fingerprints = previous.get("fingerprints")
    new_fingerprints = expected.get("fingerprints")
    if not isinstance(old_fingerprints, Mapping) or not isinstance(new_fingerprints, Mapping):
        _fail("resume checkpoint lacks compatibility fingerprints")
    for name in REQUIRED_FINGERPRINTS:
        if old_fingerprints.get(name) != new_fingerprints.get(name):
            _fail(f"resume checkpoint {name} does not match the supplied assets")
    for name in ("candidate_token_ids_sha256", "candidate_rows_sha256"):
        if old_fingerprints.get(name) != new_fingerprints.get(name):
            _fail(f"resume checkpoint {name} does not match the supplied candidate assets")
    old_training = previous.get("training")
    new_training = expected.get("training")
    if not isinstance(old_training, Mapping) or not isinstance(new_training, Mapping):
        _fail("resume checkpoint lacks training compatibility metadata")
    for name in ("batch_size", "learning_rate", "weight_decay", "seed"):
        if old_training.get(name) != new_training.get(name):
            _fail(f"resume checkpoint training setting {name} is incompatible")


def _atomic_training_checkpoint(
    path: Path,
    model: CassiFeatureTokenDecoder,
    optimizer: torch.optim.Optimizer,
    *,
    step: int,
    metadata: Mapping[str, Any],
) -> str:
    """Use the canonical decoder serializer, then atomically add optimizer state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, staging_name = tempfile.mkstemp(prefix=f".{path.name}.model.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    staging = Path(staging_name)
    final_tmp: Path | None = None
    try:
        save_feature_token_decoder_checkpoint(staging, model, step=step, metadata=metadata)
        payload = torch.load(staging, map_location="cpu", weights_only=True)
        if not isinstance(payload, dict):
            _fail("canonical decoder serializer returned an invalid payload")
        optimizer_state = _cpu_tree(optimizer.state_dict())
        if not _state_is_finite(optimizer_state):
            _fail("optimizer state contains non-finite values")
        payload["optimizer_schema"] = OPTIMIZER_SCHEMA
        payload["optimizer_state"] = optimizer_state
        fd, final_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        os.close(fd)
        final_tmp = Path(final_name)
        with final_tmp.open("wb") as handle:
            torch.save(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(final_tmp, path)
        final_tmp = None
        return sha256_file(path)
    except CassiFeatureTokenDecoderError:
        raise
    except Exception as exc:
        raise CassiFeatureTokenDecoderError(f"could not save decoder training checkpoint: {exc}") from exc
    finally:
        for temporary in (staging, final_tmp):
            if temporary is not None and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass


def _load_optimizer_state(path: Path, device: torch.device) -> tuple[Any, dict[str, Any]]:
    checkpoint = load_feature_token_decoder_checkpoint(path, device=device)
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as exc:
        _fail(f"resume decoder checkpoint cannot be read: {exc}")
    if not isinstance(payload, dict) or payload.get("optimizer_schema") != OPTIMIZER_SCHEMA:
        _fail("resume decoder checkpoint lacks optimizer state")
    optimizer_state = payload.get("optimizer_state")
    if not isinstance(optimizer_state, dict) or not _state_is_finite(optimizer_state):
        _fail("resume decoder checkpoint optimizer state is invalid")
    return checkpoint, optimizer_state


def _build_metadata(
    *,
    fingerprints: Mapping[str, Any],
    world: Any,
    assets: CandidateAssets,
    decoder: CassiFeatureTokenDecoder,
    data: Path,
    normalization: Path,
    metadata: Path,
    candidate_npz: Path,
    candidate_json: Path,
    training: Mapping[str, Any],
    metrics: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    completed_epochs: int,
    step: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": TRAINING_RECEIPT_SCHEMA,
        "data": str(data),
        "normalization": str(normalization),
        "metadata": str(metadata),
        "candidate_npz": str(candidate_npz),
        "candidate_json": str(candidate_json),
        "fingerprints": dict(fingerprints),
        "world_config_fingerprint": world.config_fingerprint,
        "world_observation_dim": int(world.config.observation_dim),
        "world_action_dim": int(world.config.action_dim),
        "world_reward_dim": int(world.config.reward_dim),
        "candidate_count": int(assets.token_ids.size),
        "candidate_feature_dim": int(assets.rows.shape[1]),
        "decoder_config": decoder.config.to_dict(),
        "decoder_config_fingerprint": decoder.config.fingerprint,
        "training": dict(training),
        "completed_epochs": int(completed_epochs),
        "step": int(step),
        "metrics": dict(metrics),
        "history": [dict(item) for item in history],
    }
    _json_finite(result, "checkpoint metadata")
    return result


def train(
    world_checkpoint: Path | str,
    data: Path | str,
    normalization: Path | str,
    metadata: Path | str,
    candidate_npz: Path | str,
    candidate_json: Path | str,
    output: Path | str,
    *,
    epochs: int = 1,
    batch_size: int = 8,
    learning_rate: float = 1.0e-3,
    weight_decay: float = 0.0,
    seed: int = 0,
    device: torch.device | str = "cpu",
    split: str = "train",
    resume: Path | str | None = None,
) -> dict[str, Any]:
    """Train and atomically save a candidate-classification decoder checkpoint."""
    epochs = _positive_int("epochs", epochs)
    batch_size = _positive_int("batch_size", batch_size)
    learning_rate = _finite_positive("learning_rate", learning_rate)
    weight_decay = _finite_nonnegative("weight_decay", weight_decay)
    seed = _nonnegative_int("seed", seed)
    if split not in {"train", "tiny"}:
        _fail(f"unsupported training metadata split {split!r}")
    try:
        target_device = torch.device(device)
    except Exception as exc:
        _fail(f"invalid device: {exc}")
    world_path = Path(world_checkpoint)
    data_path = Path(data)
    normalization_path = Path(normalization)
    metadata_path = Path(metadata)
    candidate_npz_path = Path(candidate_npz)
    candidate_json_path = Path(candidate_json)
    output_path = Path(output)
    _seed_everything(seed)
    world, trajectory, normalizer, metadata_value, assets, fingerprints = _load_training_context(
        world_checkpoint=world_path,
        data=data_path,
        normalization=normalization_path,
        metadata=metadata_path,
        candidate_npz=candidate_npz_path,
        candidate_json=candidate_json_path,
        device=target_device,
    )
    records = episode_records(metadata_value, split, trajectory.batch_size, trajectory.horizon)
    valid_numpy = trajectory.valid.detach().cpu().numpy().astype(np.bool_, copy=False)
    targets = target_ids(records, valid_numpy)
    prior = causal_prior_features(world, trajectory, device=target_device)
    features_raw, labels_numpy, episode_indices, time_indices = supervision_rows(
        prior,
        targets,
        valid_numpy,
        normalizer,
        assets.token_ids,
    )
    if features_raw.shape[0] < 1:
        _fail("training data contains no valid candidate-covered target rows")
    config = CassiFeatureTokenDecoderConfig(feature_dim=int(assets.rows.shape[1]))
    candidate_rows = torch.from_numpy(np.ascontiguousarray(assets.rows, dtype=np.float32)).to(device=target_device)
    features = torch.from_numpy(features_raw).to(device=target_device)
    labels = torch.from_numpy(labels_numpy.astype(np.int64, copy=False)).to(device=target_device)
    decoder: CassiFeatureTokenDecoder
    optimizer: torch.optim.Optimizer
    start_epoch = 0
    step = 0
    history: list[dict[str, Any]] = []
    resume_path = Path(resume) if resume is not None else None
    if resume_path is not None:
        resumed, optimizer_state = _load_optimizer_state(resume_path, target_device)
        decoder = resumed.model
        if decoder.config != config:
            _fail("resume decoder configuration does not match candidate feature dimension")
        expected_metadata = {
            "fingerprints": fingerprints,
            "training": {
                "batch_size": batch_size,
                "learning_rate": learning_rate,
                "weight_decay": weight_decay,
                "seed": seed,
                "split": split,
            },
        }
        _checkpoint_metadata_compatible(resumed.metadata, expected_metadata, config)
        previous_completed = resumed.metadata.get("completed_epochs")
        if isinstance(previous_completed, bool) or not isinstance(previous_completed, int) or previous_completed < 0:
            _fail("resume checkpoint completed_epochs is invalid")
        start_epoch = int(previous_completed)
        if start_epoch > epochs:
            _fail("resume checkpoint completed more epochs than requested")
        if isinstance(resumed.metadata.get("history"), list):
            history = [dict(item) for item in resumed.metadata["history"] if isinstance(item, Mapping)]
        step = int(resumed.step)
    else:
        decoder = CassiFeatureTokenDecoder(config).to(device=target_device)
    decoder = decoder.to(device=target_device)
    optimizer = torch.optim.AdamW(decoder.parameters(), lr=learning_rate, weight_decay=weight_decay)
    if resume_path is not None:
        try:
            optimizer.load_state_dict(optimizer_state)
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            _fail(f"resume optimizer state is incompatible: {exc}")
        if not _state_is_finite(optimizer.state_dict()):
            _fail("resume optimizer state became non-finite")
    training_config = {
        "epochs_requested": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "weight_decay": weight_decay,
        "seed": seed,
        "split": split,
        "device": str(target_device),
    }
    last_metrics: dict[str, Any] = {}
    for epoch_index in range(start_epoch, epochs):
        decoder.train(True)
        order = np.arange(features.shape[0], dtype=np.int64)
        np.random.default_rng(seed + 1_000_003 * (epoch_index + 1)).shuffle(order)
        total_loss = 0.0
        seen = 0
        batches = 0
        for offset in range(0, order.size, batch_size):
            selected = torch.from_numpy(order[offset : offset + batch_size].astype(np.int64, copy=False)).to(device=target_device)
            batch_features = features.index_select(0, selected)
            batch_labels = labels.index_select(0, selected)
            optimizer.zero_grad(set_to_none=True)
            logits = decoder.logits(batch_features, candidate_rows)
            loss = F.cross_entropy(logits, batch_labels)
            if not bool(torch.isfinite(loss).item()):
                _fail("decoder training loss became non-finite")
            loss.backward()
            for parameter in decoder.parameters():
                if parameter.grad is not None and not bool(torch.isfinite(parameter.grad).all().item()):
                    _fail("decoder training gradient became non-finite")
            optimizer.step()
            if not _state_is_finite(optimizer.state_dict()):
                _fail("decoder optimizer state became non-finite")
            count = int(batch_labels.numel())
            total_loss += float(loss.detach().cpu().item()) * count
            seen += count
            batches += 1
            step += 1
        if seen < 1:
            _fail("decoder epoch contains no training rows")
        last_metrics = {
            "loss": total_loss / seen,
            "rows": seen,
            "batches": batches,
            "candidate_count": int(assets.token_ids.size),
        }
        history.append({"epoch": epoch_index + 1, "step": step, "metrics": dict(last_metrics)})
        checkpoint_metadata = _build_metadata(
            fingerprints=fingerprints,
            world=world,
            assets=assets,
            decoder=decoder,
            data=data_path,
            normalization=normalization_path,
            metadata=metadata_path,
            candidate_npz=candidate_npz_path,
            candidate_json=candidate_json_path,
            training=training_config,
            metrics=last_metrics,
            history=history,
            completed_epochs=epoch_index + 1,
            step=step,
        )
        _atomic_training_checkpoint(output_path, decoder, optimizer, step=step, metadata=checkpoint_metadata)
    if start_epoch == epochs:
        previous_metrics = None
        if resume_path is not None:
            previous_metrics = resumed.metadata.get("metrics")  # type: ignore[union-attr]
        last_metrics = dict(previous_metrics) if isinstance(previous_metrics, Mapping) else {}
        checkpoint_metadata = _build_metadata(
            fingerprints=fingerprints,
            world=world,
            assets=assets,
            decoder=decoder,
            data=data_path,
            normalization=normalization_path,
            metadata=metadata_path,
            candidate_npz=candidate_npz_path,
            candidate_json=candidate_json_path,
            training=training_config,
            metrics=last_metrics,
            history=history,
            completed_epochs=start_epoch,
            step=step,
        )
        _atomic_training_checkpoint(output_path, decoder, optimizer, step=step, metadata=checkpoint_metadata)
    checkpoint_sha256 = sha256_file(output_path)
    summary = {
        "status": "ok",
        "checkpoint": str(output_path),
        "checkpoint_sha256": checkpoint_sha256,
        "step": step,
        "epochs": epochs,
        "completed_epochs": epochs,
        "rows": int(features.shape[0]),
        "episodes": int(trajectory.batch_size),
        "horizon": int(trajectory.horizon),
        "candidate_count": int(assets.token_ids.size),
        "decoder_config_fingerprint": decoder.config.fingerprint,
        "world_config_fingerprint": world.config_fingerprint,
        "fingerprints": fingerprints,
        "metrics": last_metrics,
    }
    _json_finite(summary, "training summary")
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world-checkpoint", type=Path, required=True, help="frozen world-model checkpoint")
    parser.add_argument("--data", type=Path, required=True, help="strict training trajectory .npz")
    parser.add_argument("--normalization", type=Path, required=True, help="strict normalization.npz")
    parser.add_argument("--metadata", type=Path, required=True, help="strict text-world metadata JSON")
    parser.add_argument("--candidate-npz", type=Path, required=True, help="frozen candidate rows .npz")
    parser.add_argument("--candidate-json", type=Path, required=True, help="candidate manifest JSON")
    parser.add_argument("--output", type=Path, required=True, help="decoder checkpoint output path")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1.0e-3)
    parser.add_argument("--split", choices=("train", "tiny"), default="train", help="metadata split matching the trajectory archive")
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--resume", type=Path, default=None, help="decoder checkpoint with optimizer state")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        summary = train(
            args.world_checkpoint,
            args.data,
            args.normalization,
            args.metadata,
            args.candidate_npz,
            args.candidate_json,
            args.output,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            weight_decay=args.weight_decay,
            seed=args.seed,
            device=args.device,
            split=args.split,
            resume=args.resume,
        )
    except (CassiFeatureTokenDecoderError, FeatureTokenPipelineError, CassiWorldModelError, OSError, RuntimeError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


__all__ = ["train", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
