"""Evaluate a Cassi world model on a held-out Qwen text trajectory archive.

The imagined suffix is prior-only: observations establish the state for the
observed prefix, then ``imagine`` receives only suffix actions and masks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import tempfile
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import torch

try:
    from .cassi_world_model import CassiTrajectoryBatch, CassiWorldModelError, load_world_model_checkpoint
    from .train_cassi_world_model import load_trajectory_npz
except ImportError:  # direct script execution
    from cassi_world_model import CassiTrajectoryBatch, CassiWorldModelError, load_world_model_checkpoint  # type: ignore[no-redef]
    from train_cassi_world_model import load_trajectory_npz  # type: ignore[no-redef]


OBSERVATION_DIM = 5120
ACTION_DIM = 5120
REWARD_DIM = 1
EVALUATION_SCHEMA = "cassi.world-model.text-evaluation.v1"
RETRIEVAL_SAMPLE_LIMIT = 8


class EvaluationError(CassiWorldModelError):
    """Raised when an evaluation input or sidecar is incompatible."""


def _fail(message: str) -> None:
    raise EvaluationError(message)


def _finite_array(name: str, value: np.ndarray) -> np.ndarray:
    result = np.asarray(value)
    if not np.issubdtype(result.dtype, np.number) or not np.isfinite(result).all():
        _fail(f"{name} contains non-finite or non-numeric values")
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        _fail(f"cannot hash {path}: {exc}")
    return digest.hexdigest()


def _trajectory_digest(batch: CassiTrajectoryBatch) -> str:
    """Match the trainer's content digest without importing its private helper."""
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


def _read_json(path: Path, description: str) -> Mapping[str, Any]:
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


def _normalization_vector(archive: Mapping[str, np.ndarray], names: Iterable[str], name: str, dimension: int) -> np.ndarray:
    selected = next((archive[key] for key in names if key in archive), None)
    if selected is None:
        _fail(f"normalization sidecar is missing {name}")
    value = _finite_array(name, np.asarray(selected))
    if value.size != dimension:
        _fail(f"{name} must contain exactly {dimension} values")
    return np.ascontiguousarray(value, dtype=np.float32).reshape(dimension)


def _load_normalization(path: Path, observation_dim: int, action_dim: int, reward_dim: int) -> dict[str, np.ndarray]:
    if not path.is_file():
        _fail(f"normalization sidecar does not exist: {path}")
    try:
        with np.load(path, allow_pickle=False) as archive:
            values = {str(key): np.asarray(archive[key]) for key in archive.files}
    except Exception as exc:
        _fail(f"normalization sidecar cannot be read: {type(exc).__name__}: {exc}")
    result = {
        "observation_mean": _normalization_vector(values, ("observation_mean", "obs_mean", "mean"), "observation_mean", observation_dim),
        "observation_std": _normalization_vector(values, ("observation_std", "obs_std", "std"), "observation_std", observation_dim),
    }
    for name, aliases, dimension in (
        ("action_mean", ("action_mean", "act_mean"), action_dim),
        ("action_std", ("action_std", "act_std"), action_dim),
        ("reward_mean", ("reward_mean", "rew_mean"), reward_dim),
        ("reward_std", ("reward_std", "rew_std"), reward_dim),
    ):
        present = next((values[key] for key in aliases if key in values), None)
        if present is not None:
            vector = _finite_array(name, present)
            if vector.size != dimension:
                _fail(f"{name} must contain exactly {dimension} values")
            result[name] = np.ascontiguousarray(vector, dtype=np.float32).reshape(dimension)
    if np.any(result["observation_std"] <= 0.0):
        _fail("observation_std must be strictly positive")
    for name in ("action_std", "reward_std"):
        if name in result and np.any(result[name] <= 0.0):
            _fail(f"{name} must be strictly positive")
    return result


def _walk_mappings(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            yield path, key_text, child
            yield from _walk_mappings(child, path + (key_text.lower(),))
    elif isinstance(value, list):
        for child in value:
            yield from _walk_mappings(child, path)


def _check_dimensions(metadata: Mapping[str, Any], observation_dim: int, action_dim: int, reward_dim: int) -> None:
    expected = {"observation_dim": observation_dim, "action_dim": action_dim, "reward_dim": reward_dim}
    for path, key, value in _walk_mappings(metadata):
        if key not in expected or isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            continue
        if int(value) != expected[key]:
            _fail(f"metadata dimension mismatch for {key}: {value} != {expected[key]}")


def _hash_values(metadata: Mapping[str, Any], *, data_sha: str, data_digest: str, normalization_sha: str) -> None:
    """Check explicit validation/normalization hashes, ignoring train-only digests."""
    for path, key, value in _walk_mappings(metadata):
        if not isinstance(value, str) or len(value) < 16:
            continue
        lowered = key.lower()
        scope = " ".join(path + (lowered,))
        if not any(marker in lowered for marker in ("sha256", "digest", "checksum", "hash")):
            continue
        # Source hashes and per-array hashes are not file-level sidecar hashes.
        if "source" in scope or lowered == "source_sha256" or "arrays" in path:
            continue
        expected: str | None = None
        if "normalization" in scope:
            expected = normalization_sha
        elif "validation" in scope:
            expected = data_sha if "sha" in lowered or "checksum" in lowered else data_digest
        if expected is not None and value.lower() not in {expected.lower(), data_sha.lower(), data_digest.lower()}:
            _fail(f"sidecar hash mismatch at {'/'.join(path + (key,))}")


def _scalar_sequence(record: Mapping[str, Any], names: Sequence[str]) -> list[Any] | None:
    for name in names:
        if name in record:
            value = record[name]
            if isinstance(value, np.ndarray):
                value = value.tolist()
            if isinstance(value, (list, tuple)):
                return list(value)
            return None
    return None


def _validation_records(metadata: Mapping[str, Any], episodes: int) -> list[Mapping[str, Any]]:
    candidates: list[Any] = []
    validation = metadata.get("validation")
    splits = metadata.get("splits")
    if isinstance(validation, Mapping):
        candidates.extend((validation.get("episodes"), validation.get("records")))
    split_validation = None
    if isinstance(splits, Mapping):
        split_validation = splits.get("validation")
        if isinstance(split_validation, Mapping):
            candidates.extend((split_validation.get("episodes"), split_validation.get("records")))
        elif isinstance(split_validation, list):
            candidates.append(split_validation)
            all_episode_rows = metadata.get("episodes")
            if all(isinstance(item, (int, np.integer)) and not isinstance(item, bool) for item in split_validation) and isinstance(all_episode_rows, list):
                selected_rows = [all_episode_rows[int(index)] for index in split_validation if 0 <= int(index) < len(all_episode_rows)]
                if len(selected_rows) == len(split_validation) and all(isinstance(row, Mapping) for row in selected_rows):
                    candidates.append(selected_rows)
    candidates.extend((metadata.get("validation_episodes"), metadata.get("validation_records")))
    all_episodes = metadata.get("episodes")
    if isinstance(all_episodes, Mapping):
        candidates.extend((all_episodes.get("validation"), all_episodes.get("valid"), all_episodes.get("val")))
    elif isinstance(all_episodes, list):
        validation_rows = [row for row in all_episodes if isinstance(row, Mapping) and str(row.get("split", "")).lower() in {"validation", "valid", "val"}]
        candidates.append(validation_rows if validation_rows else all_episodes)
    records: list[Mapping[str, Any]] | None = None
    for candidate in candidates:
        if isinstance(candidate, list) and candidate and all(isinstance(row, Mapping) for row in candidate):
            records = [row for row in candidate if isinstance(row, Mapping)]
            break
    if records is None:
        _fail("metadata contains no validation episode records")
    if len(records) != episodes:
        _fail(f"metadata validation episode count {len(records)} does not match archive count {episodes}")
    for key in ("validation_index", "archive_index", "episode_index"):
        if all(key in row for row in records):
            indices = [row[key] for row in records]
            if all(isinstance(value, (int, np.integer)) and not isinstance(value, bool) for value in indices) and sorted(int(value) for value in indices) == list(range(episodes)):
                records = [row for _, row in sorted(zip((int(value) for value in indices), records), key=lambda pair: pair[0])]
            break
    return records


def _aligned_sequence(values: list[Any], valid_row: np.ndarray, horizon: int, name: str) -> list[Any]:
    valid_positions = np.flatnonzero(valid_row)
    if len(values) == horizon:
        return list(values)
    if len(values) == len(valid_positions):
        result: list[Any] = [None] * horizon
        for position, value in zip(valid_positions.tolist(), values):
            result[position] = value
        return result
    _fail(f"metadata {name} length {len(values)} does not match horizon {horizon} or valid count {len(valid_positions)}")
    raise AssertionError("unreachable")


def _metadata_alignment(metadata: Mapping[str, Any], valid: np.ndarray, horizon: int) -> dict[str, Any]:
    records = _validation_records(metadata, int(valid.shape[0]))
    next_ids: list[list[int | None]] = []
    pieces: list[list[str | None]] = []
    for episode, record in enumerate(records):
        for key, expected in (("horizon", horizon), ("token_count", int(valid[episode].sum()))):
            value = record.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, np.integer)) or int(value) != expected):
                _fail(f"validation metadata episode {episode} {key} is incompatible with archive")
        ids = _scalar_sequence(record, ("target_next_token_ids", "next_token_ids", "target_token_ids"))
        if ids is None:
            _fail(f"validation metadata episode {episode} has no target-next-token IDs")
        aligned_ids = _aligned_sequence(ids, valid[episode], horizon, "target_next_token_ids")
        converted_ids: list[int | None] = []
        for value in aligned_ids:
            if value is None:
                converted_ids.append(None)
            elif isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
                _fail(f"validation metadata episode {episode} has a non-integer target token ID")
            else:
                converted_ids.append(int(value))
        next_ids.append(converted_ids)

        raw_pieces = _scalar_sequence(record, ("target_next_token_pieces", "next_token_pieces", "target_pieces"))
        if raw_pieces is None:
            raw_pieces = _scalar_sequence(record, ("pieces", "token_pieces"))
            if raw_pieces is not None and len(raw_pieces) == horizon + 1:
                raw_pieces = raw_pieces[1:]
        if raw_pieces is None:
            _fail(f"validation metadata episode {episode} has no token pieces")
        aligned_pieces = _aligned_sequence(raw_pieces, valid[episode], horizon, "target token pieces")
        pieces.append([None if value is None else str(value) for value in aligned_pieces])
    return {"next_token_ids": next_ids, "pieces": pieces}


class _MetricAccumulator:
    def __init__(self) -> None:
        self.count = 0
        self.standardized_sum = 0.0
        self.raw_sum = 0.0

    def add(self, prediction: torch.Tensor, target: torch.Tensor, mask: torch.Tensor, observation_std: torch.Tensor) -> None:
        if prediction.ndim != 2 or target.shape != prediction.shape or mask.shape != (prediction.shape[0],):
            _fail("metric tensors have incompatible shapes")
        if not bool(mask.any().item()):
            return
        selected_prediction = prediction[mask]
        selected_target = target[mask]
        difference = selected_prediction - selected_target
        raw_difference = difference * observation_std.reshape(1, -1)
        standardized_values = difference.square().mean(dim=-1)
        raw_values = raw_difference.square().mean(dim=-1)
        if not bool(torch.isfinite(standardized_values).all().item()) or not bool(torch.isfinite(raw_values).all().item()):
            _fail("evaluation produced non-finite squared errors")
        self.standardized_sum += float(standardized_values.sum().detach().cpu().item())
        self.raw_sum += float(raw_values.sum().detach().cpu().item())
        self.count += int(mask.sum().item())

    def result(self) -> dict[str, Any]:
        if self.count < 1:
            return {"available": False, "count": 0, "standardized_mse": 0.0, "raw_mse": 0.0}
        standardized = self.standardized_sum / self.count
        raw = self.raw_sum / self.count
        if not math.isfinite(standardized) or not math.isfinite(raw):
            _fail("evaluation metric became non-finite")
        return {"available": True, "count": self.count, "standardized_mse": standardized, "raw_mse": raw}


def _episode_batch(batch: CassiTrajectoryBatch, episode: int, start: int, end: int, device: torch.device) -> CassiTrajectoryBatch:
    return CassiTrajectoryBatch(
        observations=batch.observations[episode : episode + 1, start:end].to(device=device),
        actions=batch.actions[episode : episode + 1, start:end].to(device=device),
        rewards=batch.rewards[episode : episode + 1, start:end].to(device=device),
        continues=batch.continues[episode : episode + 1, start:end].to(device=device),
        valid=batch.valid[episode : episode + 1, start:end].to(device=device),
        resets=batch.resets[episode : episode + 1, start:end].to(device=device),
    )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        handle = tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, mode="w", encoding="utf-8", delete=False)
        temporary = Path(handle.name)
        with handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"), allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    except (OSError, TypeError, ValueError) as exc:
        if temporary is not None and temporary.exists():
            temporary.unlink()
        _fail(f"cannot atomically write evaluation output: {exc}")


def _seed_everything(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        _fail("seed must be a non-negative integer")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _metric_for_episode(prediction: torch.Tensor, target: torch.Tensor, valid: torch.Tensor, observation_std: torch.Tensor) -> dict[str, Any]:
    metric = _MetricAccumulator()
    metric.add(prediction, target, valid, observation_std)
    return metric.result()


def evaluate(
    checkpoint: Path | str,
    data: Path | str,
    normalization: Path | str,
    metadata: Path | str,
    output: Path | str,
    *,
    device: torch.device | str = "cpu",
    prefix_length: int = 1,
    max_episodes: int | None = None,
    seed: int = 0,
) -> dict[str, Any]:
    """Evaluate one strict validation archive and atomically write one JSON receipt."""
    if isinstance(prefix_length, bool) or not isinstance(prefix_length, int) or prefix_length < 1:
        _fail("prefix_length must be a positive integer")
    if max_episodes is not None and (isinstance(max_episodes, bool) or not isinstance(max_episodes, int) or max_episodes < 1):
        _fail("max_episodes must be a positive integer when provided")
    _seed_everything(seed)
    try:
        target_device = torch.device(device)
    except Exception as exc:
        _fail(f"invalid device: {exc}")

    data_path = Path(data)
    normalization_path = Path(normalization)
    metadata_path = Path(metadata)
    checkpoint_path = Path(checkpoint)
    trajectory = load_trajectory_npz(data_path, OBSERVATION_DIM, ACTION_DIM, REWARD_DIM)
    normalization_values = _load_normalization(normalization_path, OBSERVATION_DIM, ACTION_DIM, REWARD_DIM)
    metadata_value = _read_json(metadata_path, "metadata sidecar")
    _check_dimensions(metadata_value, OBSERVATION_DIM, ACTION_DIM, REWARD_DIM)
    data_sha = _sha256_file(data_path)
    data_digest = _trajectory_digest(trajectory)
    normalization_sha = _sha256_file(normalization_path)
    _hash_values(metadata_value, data_sha=data_sha, data_digest=data_digest, normalization_sha=normalization_sha)

    loaded = load_world_model_checkpoint(checkpoint_path, device=target_device)
    model = loaded.model.eval()
    if (model.config.observation_dim, model.config.action_dim, model.config.reward_dim) != (OBSERVATION_DIM, ACTION_DIM, REWARD_DIM):
        _fail("checkpoint dimensions are incompatible with the text trajectory contract")
    checkpoint_metadata_fingerprint = loaded.metadata.get("config_fingerprint")
    if checkpoint_metadata_fingerprint is not None and checkpoint_metadata_fingerprint != model.config_fingerprint:
        _fail("checkpoint metadata configuration fingerprint mismatch")
    for key in ("config_fingerprint", "model_config_fingerprint"):
        value = metadata_value.get(key)
        if isinstance(value, str) and value != model.config_fingerprint:
            _fail(f"metadata {key} is incompatible with the checkpoint")

    observations_np = np.asarray(trajectory.observations.numpy(), dtype=np.float32)
    valid_np = np.asarray(trajectory.valid.numpy(), dtype=np.bool_)
    episodes, horizon, _ = observations_np.shape
    selected_episodes = min(episodes, max_episodes) if max_episodes is not None else episodes
    observation_mean = torch.from_numpy(normalization_values["observation_mean"]).to(device=target_device, dtype=torch.float32)
    observation_std = torch.from_numpy(normalization_values["observation_std"]).to(device=target_device, dtype=torch.float32)
    if not bool(torch.isfinite(observation_mean).all().item()) or not bool(torch.isfinite(observation_std).all().item()):
        _fail("observation normalization is non-finite")

    valid_positions = np.argwhere(valid_np)
    permutation = np.random.default_rng(seed).permutation(len(valid_positions))
    shuffled_positions = valid_positions[permutation]
    rank_map = np.full((episodes, horizon), -1, dtype=np.int64)
    rank_map[valid_positions[:, 0], valid_positions[:, 1]] = np.arange(len(valid_positions), dtype=np.int64)

    retrieval: dict[str, Any]
    retrieval_target_unit: np.ndarray | None = None
    retrieval_next_ids: list[int | None] | None = None
    retrieval_pieces: list[str | None] | None = None
    retrieval_positions = valid_positions
    try:
        alignment = _metadata_alignment(metadata_value, valid_np, horizon)
        retrieval_target_raw = observations_np[valid_positions[:, 0], valid_positions[:, 1]] * normalization_values["observation_std"] + normalization_values["observation_mean"]
        if not np.isfinite(retrieval_target_raw).all():
            raise EvaluationError("raw retrieval targets are non-finite")
        target_norms = np.linalg.norm(retrieval_target_raw, axis=1, keepdims=True)
        retrieval_target_unit = retrieval_target_raw / np.maximum(target_norms, 1e-12)
        retrieval_next_ids = [alignment["next_token_ids"][int(e)][int(t)] for e, t in valid_positions.tolist()]
        retrieval_pieces = [alignment["pieces"][int(e)][int(t)] for e, t in valid_positions.tolist()]
        retrieval = {"available": True, "queries": 0, "next_token_id_queries": 0, "exact_episode_time_accuracy": 0.0, "exact_retrieval_accuracy": 0.0, "next_token_id_match_accuracy": 0.0, "mean_cosine": 0.0, "target_vs_retrieved_pieces": []}
    except (EvaluationError, KeyError, TypeError, ValueError) as exc:
        retrieval = {"available": False, "queries": 0, "reason": f"metadata alignment unavailable: {exc}", "target_vs_retrieved_pieces": []}

    posterior_acc = _MetricAccumulator()
    prior_acc = _MetricAccumulator()
    persistence_acc = _MetricAccumulator()
    shuffled_acc = _MetricAccumulator()
    shuffled_prior_acc = _MetricAccumulator()
    horizon_exact: dict[int, _MetricAccumulator] = {}
    episode_receipts: list[dict[str, Any]] = []
    total_suffix_steps = 0
    retrieval_exact = retrieval_next = retrieval_next_comparable = 0
    retrieval_cosine_sum = 0.0
    retrieval_samples: list[dict[str, Any]] = []
    model_dtype = next(model.parameters()).dtype

    with torch.no_grad():
        for episode in range(selected_episodes):
            full = _episode_batch(trajectory, episode, 0, horizon, target_device)
            observed = model.observe(full, sample=False)
            target = full.observations[0]
            valid = full.valid[0]
            posterior_prediction = observed.observation_mean[0]
            posterior_acc.add(posterior_prediction, target, valid, observation_std)

            valid_times = np.flatnonzero(valid_np[episode])
            shuffled_target_np = observations_np[shuffled_positions[rank_map[episode, valid_times], 0], shuffled_positions[rank_map[episode, valid_times], 1]]
            shuffled_target = torch.from_numpy(np.ascontiguousarray(shuffled_target_np)).to(device=target_device, dtype=model_dtype)
            shuffled_acc.add(posterior_prediction[valid], shuffled_target, torch.ones(len(valid_times), dtype=torch.bool, device=target_device), observation_std)

            prefix_end = min(prefix_length, horizon)
            suffix_steps = max(0, horizon - prefix_end)
            suffix_valid_count = int(valid_np[episode, prefix_end:].sum())
            episode_prior_acc = _MetricAccumulator()
            episode_persistence_acc = _MetricAccumulator()
            if prefix_end > 0:
                prefix_batch = _episode_batch(trajectory, episode, 0, prefix_end, target_device)
                prefix_output = model.observe(prefix_batch, sample=False)
                prior_state = prefix_output.final_state
                observed_prefix_positions = np.flatnonzero(valid_np[episode, :prefix_end])
            else:  # defensive; CLI currently requires a positive prefix
                prior_state = model.initial_state(1, device=target_device, dtype=model_dtype)
                observed_prefix_positions = np.empty((0,), dtype=np.int64)
            if suffix_steps > 0:
                suffix = _episode_batch(trajectory, episode, prefix_end, horizon, target_device)
                imagined = model.imagine(suffix.actions, prior_state, valid=suffix.valid, resets=suffix.resets, sample=False)
                suffix_target = suffix.observations[0]
                suffix_valid = suffix.valid[0]
                prior_prediction = imagined.observation_mean[0]
                prior_acc.add(prior_prediction, suffix_target, suffix_valid, observation_std)
                episode_prior_acc.add(prior_prediction, suffix_target, suffix_valid, observation_std)
                if observed_prefix_positions.size:
                    persistence_prediction = target[observed_prefix_positions[-1]].reshape(1, -1).expand(suffix_steps, -1)
                    persistence_acc.add(persistence_prediction, suffix_target, suffix_valid, observation_std)
                    episode_persistence_acc.add(persistence_prediction, suffix_target, suffix_valid, observation_std)
                suffix_valid_positions = np.flatnonzero(valid_np[episode, prefix_end:])
                if suffix_valid_positions.size:
                    shuffled_suffix_np = observations_np[shuffled_positions[rank_map[episode, prefix_end + suffix_valid_positions], 0], shuffled_positions[rank_map[episode, prefix_end + suffix_valid_positions], 1]]
                    shuffled_suffix_target = torch.from_numpy(np.ascontiguousarray(shuffled_suffix_np)).to(device=target_device, dtype=model_dtype)
                    suffix_mask_for_shuffle = torch.ones(len(suffix_valid_positions), dtype=torch.bool, device=target_device)
                    shuffled_prior_acc.add(prior_prediction[suffix_valid_positions], shuffled_suffix_target, suffix_mask_for_shuffle, observation_std)
                    for local_time in suffix_valid_positions.tolist():
                        horizon_number = int(local_time + 1)
                        metric = horizon_exact.setdefault(horizon_number, _MetricAccumulator())
                        metric.add(prior_prediction[local_time : local_time + 1], suffix_target[local_time : local_time + 1], torch.ones(1, dtype=torch.bool, device=target_device), observation_std)

                        if retrieval.get("available") and retrieval_target_unit is not None and retrieval_next_ids is not None and retrieval_pieces is not None:
                            prediction_raw = (prior_prediction[local_time] * observation_std + observation_mean).detach().cpu().numpy()
                            prediction_norm = float(np.linalg.norm(prediction_raw))
                            query = prediction_raw / max(prediction_norm, 1e-12)
                            scores = retrieval_target_unit @ query
                            nearest = int(np.argmax(scores))
                            current_rank = int(rank_map[episode, prefix_end + local_time])
                            current_id = retrieval_next_ids[current_rank]
                            retrieved_id = retrieval_next_ids[nearest]
                            retrieval["queries"] += 1
                            retrieval_exact += int(tuple(retrieval_positions[nearest].tolist()) == (episode, prefix_end + local_time))
                            if current_id is not None and retrieved_id is not None:
                                retrieval_next_comparable += 1
                                retrieval_next += int(current_id == retrieved_id)
                            retrieval_cosine_sum += float(scores[nearest])
                            if len(retrieval_samples) < RETRIEVAL_SAMPLE_LIMIT:
                                retrieval_samples.append({"episode": episode, "time": prefix_end + local_time, "target_next_token_id": current_id, "retrieved_episode": int(retrieval_positions[nearest, 0]), "retrieved_time": int(retrieval_positions[nearest, 1]), "retrieved_next_token_id": retrieved_id, "cosine": float(scores[nearest]), "target_piece": retrieval_pieces[current_rank], "retrieved_piece": retrieval_pieces[nearest]})
            total_suffix_steps += suffix_valid_count
            episode_receipts.append({"episode": episode, "valid_steps": int(valid_np[episode].sum()), "prefix_valid_steps": int(valid_np[episode, :prefix_end].sum()), "suffix_valid_steps": suffix_valid_count, "posterior_reconstruction": _metric_for_episode(posterior_prediction, target, valid, observation_std), "prior_open_loop": episode_prior_acc.result(), "persistence_baseline": episode_persistence_acc.result()})

    if retrieval.get("available"):
        query_count = int(retrieval["queries"])
        if query_count:
            retrieval.update({"exact_episode_time_accuracy": retrieval_exact / query_count, "exact_retrieval_accuracy": retrieval_exact / query_count, "next_token_id_queries": retrieval_next_comparable, "next_token_id_match_accuracy": (retrieval_next / retrieval_next_comparable) if retrieval_next_comparable else 0.0, "mean_cosine": retrieval_cosine_sum / query_count, "target_vs_retrieved_pieces": retrieval_samples})
        else:
            retrieval.update({"target_vs_retrieved_pieces": [], "reason": "no valid imagined suffix steps"})

    exact = {str(key): value.result() | {"horizon": key} for key, value in sorted(horizon_exact.items())}
    cumulative: dict[str, Any] = {}
    cumulative_acc = _MetricAccumulator()
    for key in sorted(horizon_exact):
        cumulative_acc.standardized_sum += horizon_exact[key].standardized_sum
        cumulative_acc.raw_sum += horizon_exact[key].raw_sum
        cumulative_acc.count += horizon_exact[key].count
        cumulative[str(key)] = cumulative_acc.result() | {"through_horizon": key}

    checkpoint_sha = _sha256_file(checkpoint_path)
    summary: dict[str, Any] = {
        "schema": EVALUATION_SCHEMA,
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": checkpoint_sha,
        "checkpoint_step": int(loaded.step),
        "config_fingerprint": model.config_fingerprint,
        "dataset": {"path": str(data_path), "sha256": data_sha, "digest": data_digest, "episodes": episodes, "evaluated_episodes": selected_episodes, "horizon": horizon, "observation_dim": OBSERVATION_DIM, "action_dim": ACTION_DIM, "reward_dim": REWARD_DIM},
        "normalization": {"path": str(normalization_path), "sha256": normalization_sha, "observation_dim": OBSERVATION_DIM},
        "metadata": {"path": str(metadata_path), "sha256": _sha256_file(metadata_path), "schema": metadata_value.get("schema")},
        "settings": {"device": str(target_device), "prefix_length": prefix_length, "max_episodes": max_episodes, "seed": seed},
        "counts": {"episodes": selected_episodes, "valid_steps": int(valid_np[:selected_episodes].sum()), "future_valid_steps": total_suffix_steps},
        "metrics": {"posterior_reconstruction": posterior_acc.result(), "prior_open_loop": prior_acc.result(), "persistence_baseline": persistence_acc.result(), "shuffled_target_control": shuffled_acc.result(), "shuffled_prior_control": shuffled_prior_acc.result(), "horizon_buckets": {"exact": exact, "cumulative": cumulative}, "retrieval": retrieval},
        "episodes": episode_receipts,
        "finite_checks": {"trajectory": True, "normalization": True, "checkpoint": True, "metrics": True, "json": True},
    }
    _atomic_json(Path(output), summary)
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path, help="strict validation.npz trajectory archive")
    parser.add_argument("--normalization", required=True, type=Path, help="normalization.npz sidecar")
    parser.add_argument("--metadata", required=True, type=Path, help="trajectory metadata.json sidecar")
    parser.add_argument("--output", required=True, type=Path, help="atomic JSON evaluation receipt")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--prefix-length", type=int, default=1)
    parser.add_argument("--max-episodes", type=int, default=None)
    parser.add_argument("--seed", type=int, default=0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        summary = evaluate(args.checkpoint, args.data, args.normalization, args.metadata, args.output, device=args.device, prefix_length=args.prefix_length, max_episodes=args.max_episodes, seed=args.seed)
    except (CassiWorldModelError, EvaluationError, OSError, RuntimeError, TypeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
