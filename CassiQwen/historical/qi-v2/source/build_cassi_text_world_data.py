"""Build strict Cassi world-model trajectories from local Qwen teacher forcing.

The builder keeps the pinned :class:`L18GeneratedTokenTrajectory` runtime as the
single source of tokenization, ordinary logits, and hidden-state captures. It
loads one model for the complete run, resets only its context between episodes,
and writes fixed-horizon, strictly keyed archives:

``train.npz``, ``validation.npz``, ``tiny.npz``, ``normalization.npz``, and
``metadata.json``.

No model or native runtime work happens at import time.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

try:
    from .l18_generated_token_trajectory import (
        DEFAULT_CONTEXT_SIZE,
        DEFAULT_GPU_LAYERS,
        DEFAULT_TOP_K,
        EXPECTED_LLAMA_VERSION,
        EXPECTED_MODEL_SHA256,
        HIDDEN_DIMENSION,
        PROTOCOL,
        VERSION,
        L18GeneratedTokenTrajectory,
        RuntimeConfig,
        TrajectoryError,
        array_metadata,
        float32_bytes,
        sha256_bytes,
    )
except ImportError:  # direct ``python CassiQwen/...`` execution
    from l18_generated_token_trajectory import (  # type: ignore[no-redef]
        DEFAULT_CONTEXT_SIZE,
        DEFAULT_GPU_LAYERS,
        DEFAULT_TOP_K,
        EXPECTED_LLAMA_VERSION,
        EXPECTED_MODEL_SHA256,
        HIDDEN_DIMENSION,
        PROTOCOL,
        VERSION,
        L18GeneratedTokenTrajectory,
        RuntimeConfig,
        TrajectoryError,
        array_metadata,
        float32_bytes,
        sha256_bytes,
    )


DATA_SCHEMA = "cassi.text-world-data.v1"
TRAJECTORY_KEYS = frozenset(("observations", "actions", "rewards", "continues", "valid", "resets"))
NORMALIZATION_KEYS = frozenset(
    (
        "observation_mean",
        "observation_std",
        "action_mean",
        "action_std",
        "reward_mean",
        "reward_std",
    )
)
NORMALIZATION_STD_FLOOR = 1.0e-6
DEFAULT_EPISODE_TOKENS = 16
DEFAULT_MINIMUM_EPISODE_TOKENS = 1
DEFAULT_TINY_EPISODES = 1
TEACHER_TOP_K = min(DEFAULT_TOP_K, 16)


class TextWorldDataError(RuntimeError):
    """Raised for malformed sources, captures, arrays, or output artifacts."""


@dataclass(frozen=True)
class SourceInput:
    path: Path
    raw_bytes: bytes
    text: str
    sha256: str


@dataclass(frozen=True)
class SourceData:
    source: SourceInput
    token_ids: tuple[int, ...]
    pieces: tuple[str, ...]
    windows: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class SelectedWindow:
    source_index: int
    token_start: int
    token_end: int


@dataclass
class CapturedSplit:
    arrays: dict[str, np.ndarray]
    episode_metadata: list[dict[str, Any]]
    selected_windows: list[SelectedWindow]


def _fail(message: str) -> None:
    raise TextWorldDataError(message)


def _positive_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(f"{name} must be a positive integer")
    return value


def _optional_positive_int(name: str, value: int | None) -> int | None:
    if value is None:
        return None
    return _positive_int(name, value)


def _nonnegative_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{name} must be a non-negative integer")
    return value


def _finite_float32(values: Any, *, label: str, shape: tuple[int, ...] | None = None) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=np.float32)
    except (TypeError, ValueError) as error:
        _fail(f"{label} is not a float32 array: {error}")
    if shape is not None and array.shape != shape:
        _fail(f"{label} shape must be {shape}, got {array.shape}")
    if not np.isfinite(array).all():
        _fail(f"{label} contains non-finite values")
    return np.ascontiguousarray(array, dtype=np.float32)


def _canonical_sources(paths: Sequence[Path | str], *, split: str) -> list[SourceInput]:
    if not paths:
        _fail(f"{split} requires at least one --{split}-source")
    result: list[SourceInput] = []
    for supplied in paths:
        path = Path(supplied).expanduser().resolve()
        if not path.is_file():
            _fail(f"{split} source does not exist or is not a file: {path}")
        try:
            raw = path.read_bytes()
        except OSError as error:
            _fail(f"could not read {split} source {path}: {error}")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            _fail(f"{split} source is not valid UTF-8: {path}: {error}")
        result.append(SourceInput(path, raw, text, sha256_bytes(raw)))
    return result


def _check_non_overlapping_sources(train: Sequence[SourceInput], validation: Sequence[SourceInput]) -> None:
    all_sources = [("train", source) for source in train] + [("validation", source) for source in validation]
    for index, (split, left) in enumerate(all_sources):
        left_key = os.path.normcase(str(left.path))
        for other_split, right in all_sources[index + 1 :]:
            right_key = os.path.normcase(str(right.path))
            if left_key == right_key:
                _fail(
                    "source paths overlap/equal across requested splits or within a split: "
                    f"{split}:{left.path} and {other_split}:{right.path}"
                )


def _source_windows(
    token_count: int,
    *,
    episode_tokens: int,
    minimum_episode_tokens: int,
    source: Path,
) -> tuple[tuple[int, int], ...]:
    if token_count < minimum_episode_tokens:
        _fail(
            f"source is too short after tokenization: {source} has {token_count} tokens, "
            f"requires at least {minimum_episode_tokens}"
        )
    windows: list[tuple[int, int]] = []
    for start in range(0, token_count, episode_tokens):
        end = min(start + episode_tokens, token_count)
        if end - start >= minimum_episode_tokens:
            windows.append((start, end))
    if not windows:
        _fail(f"source produced no usable windows: {source}")
    return tuple(windows)


def _round_robin_windows(sources: Sequence[SourceData], limit: int | None) -> list[SelectedWindow]:
    maximum = sum(len(source.windows) for source in sources) if limit is None else min(
        limit, sum(len(source.windows) for source in sources)
    )
    selected: list[SelectedWindow] = []
    round_index = 0
    while len(selected) < maximum:
        added = False
        for source_index, source in enumerate(sources):
            if round_index >= len(source.windows):
                continue
            start, end = source.windows[round_index]
            selected.append(SelectedWindow(source_index, start, end))
            added = True
            if len(selected) >= maximum:
                break
        if not added:
            break
        round_index += 1
    if not selected:
        _fail("episode cap produced an empty split")
    return selected


def _stable_log_probability(logits: Any, token_id: int) -> float:
    values = _finite_float32(logits, label="ordinary logits")
    if values.ndim != 1:
        _fail(f"ordinary logits must be one-dimensional, got {values.shape}")
    if token_id < 0 or token_id >= values.size:
        _fail(f"next-token ID {token_id} is outside ordinary-logit vocabulary {values.size}")
    values64 = values.astype(np.float64, copy=False)
    maximum = float(np.max(values64))
    shifted = values64 - maximum
    log_partition = maximum + math.log(float(np.exp(shifted).sum(dtype=np.float64)))
    result = float(values64[token_id] - log_partition)
    if not math.isfinite(result):
        _fail("teacher next-token log-probability is non-finite")
    return result


def _teacher_candidates(runtime: L18GeneratedTokenTrajectory, record: Any) -> list[dict[str, Any]]:
    rows = list(record.ordinary_top_k[:TEACHER_TOP_K])
    if not rows:
        _fail("ordinary teacher top candidates are empty")
    candidates: list[dict[str, Any]] = []
    for rank, row in enumerate(rows):
        try:
            token_id = int(row["token_id"])
            logit = float(row["logit"])
            piece = str(row.get("piece", runtime.token_piece(token_id)))
            is_eog = bool(row.get("is_eog", runtime.token_is_eog(token_id)))
        except (KeyError, TypeError, ValueError) as error:
            _fail(f"ordinary teacher candidate is malformed: {error}")
        if not math.isfinite(logit):
            _fail("ordinary teacher candidate logit is non-finite")
        candidates.append({"rank": rank, "token_id": token_id, "piece": piece, "logit": logit, "is_eog": is_eog})
    return candidates


def _capture_episode(
    runtime: L18GeneratedTokenTrajectory,
    source: SourceData,
    selected: SelectedWindow,
    *,
    episode_tokens: int,
    split: str,
    episode_index: int,
    reset_context: bool,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if reset_context:
        runtime.reset_context()
    token_ids = source.token_ids[selected.token_start : selected.token_end]
    token_pieces = source.pieces[selected.token_start : selected.token_end]
    token_count = len(token_ids)
    if token_count < 1 or token_count > episode_tokens:
        _fail("selected window has an invalid token count")

    observations = np.zeros((episode_tokens, HIDDEN_DIMENSION), dtype=np.float32)
    actions = np.zeros((episode_tokens, HIDDEN_DIMENSION), dtype=np.float32)
    rewards = np.zeros((episode_tokens, 1), dtype=np.float32)
    continues = np.zeros((episode_tokens,), dtype=np.float32)
    valid = np.zeros((episode_tokens,), dtype=np.bool_)
    resets = np.zeros((episode_tokens,), dtype=np.bool_)
    valid[:token_count] = True
    continues[:token_count] = 1.0
    continues[token_count - 1] = 0.0
    resets[0] = True

    target_next_token_ids: list[int | None] = []
    teacher_top_candidates: list[list[dict[str, Any]]] = []
    for local_index, token_id in enumerate(token_ids):
        if local_index == 0:
            record = runtime.decode_initial((token_id,), positions=(0,))
        else:
            record = runtime.decode_token(token_id, local_index)
        if record.final_position != local_index:
            _fail(
                f"capture position mismatch for {split} episode {episode_index}: "
                f"{record.final_position} != {local_index}"
            )
        if record.final_token_id != token_id:
            _fail(f"capture token mismatch for {split} episode {episode_index} at {local_index}")
        if len(record.trunk) != 64 or record.trunk[0].layer_index != 0 or record.trunk[0].role != "field_trunk":
            _fail("Qwen capture did not provide the expected layer-0 trunk residual")
        action = _finite_float32(record.trunk[0].values, label="layer-0 trunk residual", shape=(HIDDEN_DIMENSION,))
        observation = _finite_float32(
            record.head_output_vector,
            label="head-output reference",
            shape=(HIDDEN_DIMENSION,),
        )
        actions[local_index] = action
        observations[local_index] = observation
        target_id = int(token_ids[local_index + 1]) if local_index + 1 < token_count else None
        target_next_token_ids.append(target_id)
        if target_id is not None:
            rewards[local_index, 0] = np.float32(_stable_log_probability(record.ordinary_logits, target_id))
        teacher_top_candidates.append(_teacher_candidates(runtime, record))

    for label, array in (
        ("observations", observations),
        ("actions", actions),
        ("rewards", rewards),
        ("continues", continues),
    ):
        _finite_float32(array, label=label)
    metadata = {
        "episode_index": episode_index,
        "source_index": selected.source_index,
        "source_path": str(source.source.path),
        "source_sha256": source.source.sha256,
        "token_start": selected.token_start,
        "token_end": selected.token_end,
        "token_count": token_count,
        "horizon": episode_tokens,
        "token_ids": [int(token_id) for token_id in token_ids],
        "pieces": list(token_pieces),
        "target_next_token_ids": target_next_token_ids,
        "target_next_token_pieces": [*token_pieces[1:], None],
        "teacher_top_candidates": teacher_top_candidates,
    }
    arrays = {
        "observations": observations,
        "actions": actions,
        "rewards": rewards,
        "continues": continues,
        "valid": valid,
        "resets": resets,
    }
    return arrays, metadata


def _capture_split(
    runtime: L18GeneratedTokenTrajectory,
    sources: Sequence[SourceData],
    selected_windows: Sequence[SelectedWindow],
    *,
    split: str,
    episode_tokens: int,
) -> CapturedSplit:
    if not selected_windows:
        _fail(f"{split} split is empty")
    per_array: dict[str, list[np.ndarray]] = {key: [] for key in TRAJECTORY_KEYS}
    metadata: list[dict[str, Any]] = []
    for episode_index, selected in enumerate(selected_windows):
        arrays, episode_metadata = _capture_episode(
            runtime,
            sources[selected.source_index],
            selected,
            episode_tokens=episode_tokens,
            split=split,
            episode_index=episode_index,
            reset_context=True,
        )
        for key in TRAJECTORY_KEYS:
            per_array[key].append(arrays[key])
        metadata.append(episode_metadata)
    stacked: dict[str, np.ndarray] = {}
    for key in TRAJECTORY_KEYS:
        if key in ("valid", "resets"):
            stacked[key] = np.ascontiguousarray(np.stack(per_array[key], axis=0), dtype=np.bool_)
        else:
            stacked[key] = np.ascontiguousarray(np.stack(per_array[key], axis=0), dtype=np.float32)
    return CapturedSplit(stacked, metadata, list(selected_windows))


def _fit_normalization(train: CapturedSplit) -> dict[str, np.ndarray]:
    valid = train.arrays["valid"]
    if valid.ndim != 2 or not bool(valid.any()):
        _fail("training split has no valid steps for normalization")

    def stats(name: str, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        selected = np.asarray(values[valid], dtype=np.float64)
        if selected.size == 0:
            _fail(f"training split has no valid {name} values")
        mean = selected.mean(axis=0, dtype=np.float64)
        centered = selected - mean
        std = np.sqrt(np.mean(centered * centered, axis=0, dtype=np.float64))
        std = np.maximum(std, NORMALIZATION_STD_FLOOR)
        if not np.isfinite(mean).all() or not np.isfinite(std).all() or np.any(std < NORMALIZATION_STD_FLOOR):
            _fail(f"training normalization for {name} is non-finite")
        return np.ascontiguousarray(mean, dtype=np.float32), np.ascontiguousarray(std, dtype=np.float32)

    observation_mean, observation_std = stats("observations", train.arrays["observations"])
    action_mean, action_std = stats("actions", train.arrays["actions"])
    reward_mean, reward_std = stats("rewards", train.arrays["rewards"])
    return {
        "observation_mean": observation_mean,
        "observation_std": observation_std,
        "action_mean": action_mean,
        "action_std": action_std,
        "reward_mean": reward_mean,
        "reward_std": reward_std,
    }


def _apply_normalization(split: CapturedSplit, normalization: Mapping[str, np.ndarray]) -> None:
    valid = split.arrays["valid"]
    for value_name, mean_name, std_name in (
        ("observations", "observation_mean", "observation_std"),
        ("actions", "action_mean", "action_std"),
        ("rewards", "reward_mean", "reward_std"),
    ):
        values = split.arrays[value_name]
        transformed = np.zeros_like(values, dtype=np.float32)
        transformed[valid] = (
            (values[valid].astype(np.float64) - normalization[mean_name].astype(np.float64))
            / normalization[std_name].astype(np.float64)
        ).astype(np.float32)
        _finite_float32(transformed, label=f"standardized {value_name}")
        split.arrays[value_name] = np.ascontiguousarray(transformed, dtype=np.float32)


def _subset_split(source: CapturedSplit, indices: Sequence[int]) -> CapturedSplit:
    if not indices:
        _fail("tiny subset is empty")
    selector = np.asarray(indices, dtype=np.int64)
    arrays = {
        key: np.ascontiguousarray(value[selector], dtype=np.bool_ if key in ("valid", "resets") else np.float32)
        for key, value in source.arrays.items()
    }
    metadata = []
    selected_windows = []
    for tiny_index, train_index in enumerate(indices):
        row = dict(source.episode_metadata[train_index])
        row["episode_index"] = tiny_index
        row["train_episode_index"] = int(train_index)
        metadata.append(row)
        selected_windows.append(source.selected_windows[train_index])
    return CapturedSplit(arrays, metadata, selected_windows)


def _strict_archive_payload(split: CapturedSplit) -> dict[str, np.ndarray]:
    if set(split.arrays) != set(TRAJECTORY_KEYS):
        _fail("strict trajectory archive keys do not match the required six-array schema")
    payload = {
        "observations": np.ascontiguousarray(split.arrays["observations"], dtype=np.float32),
        "actions": np.ascontiguousarray(split.arrays["actions"], dtype=np.float32),
        "rewards": np.ascontiguousarray(split.arrays["rewards"], dtype=np.float32),
        "continues": np.ascontiguousarray(split.arrays["continues"], dtype=np.float32),
        "valid": np.ascontiguousarray(split.arrays["valid"], dtype=np.bool_),
        "resets": np.ascontiguousarray(split.arrays["resets"], dtype=np.bool_),
    }
    if set(payload) != set(TRAJECTORY_KEYS):
        _fail("strict trajectory archive accidentally gained an extra key")
    for key, value in payload.items():
        if value.dtype.kind == "f" and not np.isfinite(value).all():
            _fail(f"strict archive array {key} contains non-finite values")
    return payload


def _npz_bytes(payload: Mapping[str, np.ndarray], *, expected_keys: frozenset[str]) -> bytes:
    if set(payload) != set(expected_keys):
        _fail("NPZ payload keys do not match its declared schema")
    stream = io.BytesIO()
    try:
        np.savez_compressed(stream, **{key: payload[key] for key in sorted(payload)})
    except (OSError, TypeError, ValueError) as error:
        _fail(f"could not encode NPZ payload: {error}")
    return stream.getvalue()


def _array_descriptor(name: str, values: np.ndarray) -> dict[str, Any]:
    array = np.ascontiguousarray(values)
    if array.dtype.kind == "f":
        receipt = array_metadata(array, label=name)
        receipt.pop("l2_norm", None)
        receipt.pop("max_abs", None)
        return receipt
    raw = array.tobytes(order="C")
    return {
        "dtype": str(array.dtype),
        "shape": list(array.shape),
        "layout": "C",
        "nbytes": len(raw),
        "sha256": sha256_bytes(raw),
    }


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _archive_receipt(path: Path, payload: Mapping[str, np.ndarray], raw_bytes: bytes) -> dict[str, Any]:
    return {
        "path": path.name,
        "sha256": sha256_bytes(raw_bytes),
        "nbytes": len(raw_bytes),
        "keys": sorted(payload),
        "arrays": {name: _array_descriptor(name, payload[name]) for name in sorted(payload)},
    }


def _source_metadata(split: str, sources: Sequence[SourceData], selected: Sequence[SelectedWindow]) -> list[dict[str, Any]]:
    selected_counts = {index: 0 for index in range(len(sources))}
    for item in selected:
        selected_counts[item.source_index] += 1
    result: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        result.append(
            {
                "split": split,
                "source_index": index,
                "path": str(source.source.path),
                "sha256": source.source.sha256,
                "utf8_bytes": len(source.source.raw_bytes),
                "token_count": len(source.token_ids),
                "available_windows": len(source.windows),
                "selected_windows": selected_counts[index],
            }
        )
    return result


def build_dataset(
    output_dir: Path | str,
    train_sources: Sequence[Path | str],
    validation_sources: Sequence[Path | str],
    *,
    episode_tokens: int = DEFAULT_EPISODE_TOKENS,
    minimum_episode_tokens: int = DEFAULT_MINIMUM_EPISODE_TOKENS,
    max_train_episodes: int | None = None,
    max_validation_episodes: int | None = None,
    tiny_episodes: int = DEFAULT_TINY_EPISODES,
    context_size: int = DEFAULT_CONTEXT_SIZE,
    gpu_layers: int = DEFAULT_GPU_LAYERS,
    seed: int = 0,
    model_path: Path | str | None = None,
    dll_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Build all five artifacts and return the JSON-safe receipt summary."""
    _positive_int("episode_tokens", episode_tokens)
    _positive_int("minimum_episode_tokens", minimum_episode_tokens)
    if minimum_episode_tokens > episode_tokens:
        _fail("minimum_episode_tokens cannot exceed episode_tokens")
    _optional_positive_int("max_train_episodes", max_train_episodes)
    _optional_positive_int("max_validation_episodes", max_validation_episodes)
    _positive_int("tiny_episodes", tiny_episodes)
    _positive_int("context_size", context_size)
    if episode_tokens > context_size:
        _fail("episode_tokens cannot exceed context_size")
    if isinstance(gpu_layers, bool) or not isinstance(gpu_layers, int) or gpu_layers < 0:
        _fail("gpu_layers must be a non-negative integer")
    _nonnegative_int("seed", seed)

    train_inputs = _canonical_sources(train_sources, split="train")
    validation_inputs = _canonical_sources(validation_sources, split="validation")
    _check_non_overlapping_sources(train_inputs, validation_inputs)
    default_runtime = RuntimeConfig()
    runtime_batch = min(64, context_size)
    runtime_config = RuntimeConfig(
        model_path=Path(model_path) if model_path is not None else default_runtime.model_path,
        dll_dir=Path(dll_dir) if dll_dir is not None else default_runtime.dll_dir,
        context_size=context_size,
        n_batch=runtime_batch,
        n_ubatch=runtime_batch,
        gpu_layers=gpu_layers,
        expected_model_sha256=EXPECTED_MODEL_SHA256,
    )

    output_root = Path(output_dir).expanduser().resolve()
    train_data: list[SourceData] = []
    validation_data: list[SourceData] = []
    train_selected: list[SelectedWindow] = []
    validation_selected: list[SelectedWindow] = []
    runtime: L18GeneratedTokenTrajectory | None = None
    try:
        # One runtime owns the model and is reused for tokenization and every capture.
        runtime = L18GeneratedTokenTrajectory(runtime_config)
        for source in train_inputs:
            ids = tuple(int(token_id) for token_id in runtime.tokenize(source.text))
            if not ids:
                _fail(f"train source tokenized to zero tokens: {source.path}")
            pieces = tuple(runtime.token_piece(token_id) for token_id in ids)
            train_data.append(
                SourceData(
                    source,
                    ids,
                    pieces,
                    _source_windows(
                        len(ids),
                        episode_tokens=episode_tokens,
                        minimum_episode_tokens=minimum_episode_tokens,
                        source=source.path,
                    ),
                )
            )
        for source in validation_inputs:
            ids = tuple(int(token_id) for token_id in runtime.tokenize(source.text))
            if not ids:
                _fail(f"validation source tokenized to zero tokens: {source.path}")
            pieces = tuple(runtime.token_piece(token_id) for token_id in ids)
            validation_data.append(
                SourceData(
                    source,
                    ids,
                    pieces,
                    _source_windows(
                        len(ids),
                        episode_tokens=episode_tokens,
                        minimum_episode_tokens=minimum_episode_tokens,
                        source=source.path,
                    ),
                )
            )
        train_selected = _round_robin_windows(train_data, max_train_episodes)
        validation_selected = _round_robin_windows(validation_data, max_validation_episodes)
        train = _capture_split(runtime, train_data, train_selected, split="train", episode_tokens=episode_tokens)
        validation = _capture_split(
            runtime,
            validation_data,
            validation_selected,
            split="validation",
            episode_tokens=episode_tokens,
        )
    except (TrajectoryError, OSError, ValueError, TypeError) as error:
        if isinstance(error, TextWorldDataError):
            raise
        _fail(str(error))
    finally:
        if runtime is not None:
            runtime.close(suppress=True)

    if not train_selected or not validation_selected:
        _fail("train and validation splits must both be non-empty")
    normalization = _fit_normalization(train)
    tiny_count = min(tiny_episodes, len(train.episode_metadata))
    if tiny_count < 1:
        _fail("tiny subset is empty")
    permutation = np.random.default_rng(seed).permutation(len(train.episode_metadata))
    tiny_indices = sorted(int(index) for index in permutation[:tiny_count])
    tiny = _subset_split(train, tiny_indices)
    _apply_normalization(train, normalization)
    _apply_normalization(validation, normalization)
    _apply_normalization(tiny, normalization)

    train_payload = _strict_archive_payload(train)
    validation_payload = _strict_archive_payload(validation)
    tiny_payload = _strict_archive_payload(tiny)
    normalization_payload = {key: np.ascontiguousarray(value, dtype=np.float32) for key, value in normalization.items()}
    if set(normalization_payload) != set(NORMALIZATION_KEYS):
        _fail("normalization archive keys do not match the declared schema")
    for key, value in normalization_payload.items():
        _finite_float32(value, label=key)

    output_root.mkdir(parents=True, exist_ok=True)
    archive_bytes = {
        "train.npz": _npz_bytes(train_payload, expected_keys=TRAJECTORY_KEYS),
        "validation.npz": _npz_bytes(validation_payload, expected_keys=TRAJECTORY_KEYS),
        "tiny.npz": _npz_bytes(tiny_payload, expected_keys=TRAJECTORY_KEYS),
        "normalization.npz": _npz_bytes(normalization_payload, expected_keys=NORMALIZATION_KEYS),
    }
    payloads: dict[str, Mapping[str, np.ndarray]] = {
        "train.npz": train_payload,
        "validation.npz": validation_payload,
        "tiny.npz": tiny_payload,
        "normalization.npz": normalization_payload,
    }
    receipts: dict[str, Any] = {}
    for filename, raw_bytes in archive_bytes.items():
        path = output_root / filename
        _atomic_write_bytes(path, raw_bytes)
        receipts[filename] = _archive_receipt(path, payloads[filename], raw_bytes)

    metadata: dict[str, Any] = {
        "schema": DATA_SCHEMA,
        "protocol": PROTOCOL,
        "trajectory_version": VERSION,
        "model": {
            "path": str(runtime_config.model_path.resolve()),
            "sha256": EXPECTED_MODEL_SHA256,
            "runtime_version": EXPECTED_LLAMA_VERSION,
            "context_size": context_size,
            "n_batch": runtime_batch,
            "n_ubatch": runtime_batch,
            "gpu_layers": gpu_layers,
            "hidden_dimension": HIDDEN_DIMENSION,
            "layer_count": 64,
        },
        "dimensions": {"observation_dim": HIDDEN_DIMENSION, "action_dim": HIDDEN_DIMENSION, "reward_dim": 1},
        "settings": {
            "episode_tokens": episode_tokens,
            "minimum_episode_tokens": minimum_episode_tokens,
            "max_train_episodes": max_train_episodes,
            "max_validation_episodes": max_validation_episodes,
            "tiny_episodes_requested": tiny_episodes,
            "seed": seed,
        },
        "sources": {
            "train": _source_metadata("train", train_data, train_selected),
            "validation": _source_metadata("validation", validation_data, validation_selected),
        },
        "splits": {
            "train": {"episodes": len(train.episode_metadata), "valid_steps": int(train.arrays["valid"].sum()), "horizon": episode_tokens},
            "validation": {
                "episodes": len(validation.episode_metadata),
                "valid_steps": int(validation.arrays["valid"].sum()),
                "horizon": episode_tokens,
            },
            "tiny": {"episodes": len(tiny.episode_metadata), "valid_steps": int(tiny.arrays["valid"].sum()), "horizon": episode_tokens},
        },
        "episodes": {
            "train": train.episode_metadata,
            "validation": validation.episode_metadata,
            "tiny": tiny.episode_metadata,
        },
        "normalization": {
            "fit_split": "train",
            "valid_steps": int(train.arrays["valid"].sum()),
            "std_floor": NORMALIZATION_STD_FLOOR,
            "variance": "population variance over train valid steps; every std is max(raw_std, std_floor)",
            "archive_keys": sorted(NORMALIZATION_KEYS),
        },
        "archives": receipts,
    }
    metadata_bytes = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    _atomic_write_bytes(output_root / "metadata.json", metadata_bytes)
    return {
        "status": "ok",
        "schema": DATA_SCHEMA,
        "output_dir": str(output_root),
        "metadata": "metadata.json",
        "train_episodes": len(train.episode_metadata),
        "validation_episodes": len(validation.episode_metadata),
        "tiny_episodes": len(tiny.episode_metadata),
        "horizon": episode_tokens,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build strict CassiWorldModel text trajectories from pinned local Qwen teacher-forced captures."
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="gitignored directory for the five output artifacts")
    parser.add_argument("--train-source", action="append", required=True, metavar="PATH", help="UTF-8 training text file; repeatable")
    parser.add_argument("--validation-source", action="append", required=True, metavar="PATH", help="UTF-8 held-out text file; repeatable")
    parser.add_argument("--episode-tokens", type=int, default=DEFAULT_EPISODE_TOKENS, help="fixed archive horizon and maximum window tokens")
    parser.add_argument(
        "--minimum-episode-tokens", "--min-episode-tokens", dest="minimum_episode_tokens", type=int,
        default=DEFAULT_MINIMUM_EPISODE_TOKENS, help="discard final source tails shorter than this threshold",
    )
    parser.add_argument("--max-train-episodes", type=int, default=None, help="optional independent cap, selected round-robin across train sources")
    parser.add_argument("--max-validation-episodes", type=int, default=None, help="optional independent cap, selected round-robin across validation sources")
    parser.add_argument("--tiny-episodes", type=int, default=DEFAULT_TINY_EPISODES, help="bounded deterministic subset size from train")
    parser.add_argument("--context-size", type=int, default=DEFAULT_CONTEXT_SIZE, help="pinned Qwen context length")
    parser.add_argument("--gpu-layers", type=int, default=DEFAULT_GPU_LAYERS, help="Qwen GPU layer request")
    parser.add_argument("--seed", type=int, default=0, help="deterministic tiny-subset seed")
    parser.add_argument("--model-path", type=Path, default=None, help="local pinned Qwen GGUF path")
    parser.add_argument("--dll-dir", type=Path, default=None, help="directory containing the pinned llama/ggml DLLs")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        summary = build_dataset(
            args.output_dir,
            args.train_source,
            args.validation_source,
            episode_tokens=args.episode_tokens,
            minimum_episode_tokens=args.minimum_episode_tokens,
            max_train_episodes=args.max_train_episodes,
            max_validation_episodes=args.max_validation_episodes,
            tiny_episodes=args.tiny_episodes,
            context_size=args.context_size,
            gpu_layers=args.gpu_layers,
            seed=args.seed,
            model_path=args.model_path,
            dll_dir=args.dll_dir,
        )
    except (TextWorldDataError, TrajectoryError, OSError, RuntimeError, TypeError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(summary, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
