"""Strict shared assets and causal feature pipeline for text-world token decoding.

This module intentionally contains no model-loading work at import time.  The
frozen Qwen output head is imported and constructed only by
:func:`extract_candidate_rows`.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from numbers import Integral
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch


FEATURE_TOKEN_ASSET_SCHEMA = "cassi.feature-token-decoder.assets.v1"
TEXT_WORLD_DATA_SCHEMA = "cassi.text-world-data.v1"
DEFAULT_VOCABULARY_SIZE = 248320
EXPECTED_FEATURE_DIMENSION = 5120
_MAX_TEACHER_CANDIDATES = 16


class FeatureTokenPipelineError(ValueError):
    """Raised when a trajectory, metadata row, or persisted asset is invalid."""


def _error(message: str) -> None:
    raise FeatureTokenPipelineError(message)


def _path(value: str | os.PathLike[str], label: str) -> Path:
    try:
        return Path(value)
    except (TypeError, ValueError) as exc:
        raise FeatureTokenPipelineError(f"{label} must be a filesystem path") from exc


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or int(value) < 1:
        _error(f"{label} must be a positive integer")
    return int(value)


def _vocabulary_size(value: Any) -> int:
    return _positive_int(value, "vocabulary_size")


def _finite_float32(value: Any, label: str, *, ndim: int | None = None) -> np.ndarray:
    try:
        array = np.asarray(value, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise FeatureTokenPipelineError(f"{label} must be numeric float32-compatible data") from exc
    if ndim is not None and array.ndim != ndim:
        _error(f"{label} must have {ndim} dimensions, got {array.ndim}")
    if not np.isfinite(array).all():
        _error(f"{label} contains non-finite values")
    return np.ascontiguousarray(array, dtype=np.float32)


def _integer_vector(value: Any, label: str, *, allow_empty: bool = False) -> np.ndarray:
    try:
        array = np.asarray(value)
    except Exception as exc:  # numpy can raise several conversion errors
        raise FeatureTokenPipelineError(f"{label} must be a one-dimensional integer sequence") from exc
    if array.ndim != 1 or (not allow_empty and array.size == 0):
        _error(f"{label} must be a nonempty one-dimensional integer sequence")
    if array.dtype.kind == "b":
        _error(f"{label} must contain integer IDs, not booleans")
    values = array.tolist()
    if any(isinstance(item, bool) or not isinstance(item, Integral) for item in values):
        _error(f"{label} must contain only integer IDs")
    return np.ascontiguousarray(np.asarray([int(item) for item in values], dtype=np.int64))


def _token_id(value: Any, label: str, vocabulary_size: int) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        _error(f"{label} must be an integer token ID")
    token_id = int(value)
    if token_id < 0 or token_id >= vocabulary_size:
        _error(f"{label} {token_id} is outside vocabulary size {vocabulary_size}")
    return token_id


def _sequence(value: Any, label: str) -> list[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _error(f"{label} must be a sequence")
    return list(value)


def _bool_mask(value: Any, shape: tuple[int, int], label: str) -> np.ndarray:
    try:
        array = np.asarray(value)
    except Exception as exc:
        raise FeatureTokenPipelineError(f"{label} must be a boolean array") from exc
    if array.shape != shape or array.dtype.kind != "b":
        _error(f"{label} must have boolean shape {shape}")
    return np.ascontiguousarray(array, dtype=np.bool_)


def _json_finite(value: Any, label: str = "JSON value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _error(f"{label} contains a non-finite number")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _error(f"{label} contains a non-string object key")
            _json_finite(item, f"{label}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _json_finite(item, f"{label}[{index}]")
        return
    _error(f"{label} contains a non-JSON value ({type(value).__name__})")


def sha256_file(path: str | os.PathLike[str]) -> str:
    """Return the SHA-256 digest of a file's raw bytes."""

    file_path = _path(path, "path")
    digest = hashlib.sha256()
    try:
        with file_path.open("rb") as handle:
            while True:
                block = handle.read(1 << 20)
                if not block:
                    break
                digest.update(block)
    except OSError as exc:
        raise FeatureTokenPipelineError(f"could not hash file {file_path}: {exc}") from exc
    return digest.hexdigest()


def sha256_array(array: Any) -> str:
    """Return a stable SHA-256 digest of an array's C-order raw bytes."""

    try:
        value = np.asarray(array)
    except Exception as exc:
        raise FeatureTokenPipelineError("array cannot be converted for hashing") from exc
    if value.dtype.kind == "O" or value.dtype.kind in {"U", "S", "V"}:
        _error("array hashing requires a numeric or boolean dtype")
    if value.dtype.kind == "f" and not np.isfinite(value).all():
        _error("array to hash contains non-finite values")
    # Assets are written in little-endian NumPy dtypes.  Canonicalising byte
    # order makes the receipt independent of the host's native endian setting.
    canonical_dtype = value.dtype.newbyteorder("<")
    canonical = np.asarray(value, dtype=canonical_dtype)
    canonical = np.ascontiguousarray(canonical)
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


@dataclass(frozen=True)
class Normalization:
    """Train-split observation/action standardisation statistics."""

    observation_mean: np.ndarray
    observation_std: np.ndarray
    action_mean: np.ndarray
    action_std: np.ndarray

    def __post_init__(self) -> None:
        converted: dict[str, np.ndarray] = {}
        for name in ("observation_mean", "observation_std", "action_mean", "action_std"):
            value = _finite_float32(getattr(self, name), name, ndim=1)
            if value.size == 0:
                _error(f"{name} must not be empty")
            converted[name] = value
        if converted["observation_mean"].shape != converted["observation_std"].shape:
            _error("observation mean and standard deviation shapes do not match")
        if converted["action_mean"].shape != converted["action_std"].shape:
            _error("action mean and standard deviation shapes do not match")
        for name in ("observation_std", "action_std"):
            if np.any(converted[name] <= 0.0):
                _error(f"{name} must be strictly positive")
        for name, value in converted.items():
            object.__setattr__(self, name, value)

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "Normalization":
        """Load the strict ``normalization.npz`` archive without pickle."""

        archive_path = _path(path, "normalization path")
        try:
            with np.load(archive_path, allow_pickle=False) as archive:
                keys = set(archive.files)
                required = {"observation_mean", "observation_std", "action_mean", "action_std"}
                allowed = required | {"reward_mean", "reward_std"}
                if not required.issubset(keys) or not keys.issubset(allowed):
                    _error("normalization archive keys do not match the strict schema")
                values = {name: np.array(archive[name], copy=True) for name in required}
                for name in sorted(keys - required):
                    _finite_float32(archive[name], name)
        except FeatureTokenPipelineError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise FeatureTokenPipelineError(f"could not load normalization archive: {exc}") from exc
        return cls(**values)

    def observation_raw(self, standardized: Any) -> np.ndarray:
        value = _finite_float32(standardized, "standardized observations")
        if value.ndim < 1 or value.shape[-1] != self.observation_mean.size:
            _error("standardized observations have the wrong final dimension")
        result = value * self.observation_std + self.observation_mean
        if not np.isfinite(result).all():
            _error("raw observations contain non-finite values")
        return np.ascontiguousarray(result, dtype=np.float32)

    def observation_standardized(self, raw: Any) -> np.ndarray:
        value = _finite_float32(raw, "raw observations")
        if value.ndim < 1 or value.shape[-1] != self.observation_mean.size:
            _error("raw observations have the wrong final dimension")
        result = (value - self.observation_mean) / self.observation_std
        if not np.isfinite(result).all():
            _error("standardized observations contain non-finite values")
        return np.ascontiguousarray(result, dtype=np.float32)

    def action_standardized(self, raw: Any) -> np.ndarray:
        value = _finite_float32(raw, "raw actions")
        if value.ndim < 1 or value.shape[-1] != self.action_mean.size:
            _error("raw actions have the wrong final dimension")
        result = (value - self.action_mean) / self.action_std
        if not np.isfinite(result).all():
            _error("standardized actions contain non-finite values")
        return np.ascontiguousarray(result, dtype=np.float32)


def load_text_metadata(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load and validate a ``cassi.text-world-data.v1`` metadata JSON file."""

    metadata_path = _path(path, "metadata path")
    try:
        with metadata_path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise FeatureTokenPipelineError(f"could not load text metadata: {exc}") from exc
    if not isinstance(metadata, dict):
        _error("text metadata must be a JSON object")
    if metadata.get("schema") != TEXT_WORLD_DATA_SCHEMA:
        _error(f"text metadata schema must be {TEXT_WORLD_DATA_SCHEMA!r}")
    _json_finite(metadata, "text metadata")
    episodes = metadata.get("episodes")
    if not isinstance(episodes, Mapping):
        _error("text metadata must contain an episodes object")
    return metadata


def episode_records(
    metadata: Mapping[str, Any], split: str, episodes: int, horizon: int
) -> list[Mapping[str, Any]]:
    """Select row-aligned episode metadata for one archive split."""

    if not isinstance(metadata, Mapping) or metadata.get("schema") != TEXT_WORLD_DATA_SCHEMA:
        _error(f"metadata schema must be {TEXT_WORLD_DATA_SCHEMA!r}")
    if not isinstance(split, str) or not split:
        _error("split must be a nonempty string")
    count = _positive_int(episodes, "episodes")
    length = _positive_int(horizon, "horizon")
    all_episodes = metadata.get("episodes")
    if not isinstance(all_episodes, Mapping):
        _error("metadata episodes must be an object keyed by split")
    rows_value = all_episodes.get(split)
    if not isinstance(rows_value, list):
        _error(f"metadata episodes has no row list for split {split!r}")
    if len(rows_value) != count:
        _error(f"metadata split {split!r} contains {len(rows_value)} rows, expected {count}")
    rows: list[Mapping[str, Any]] = []
    for index, row in enumerate(rows_value):
        if not isinstance(row, Mapping):
            _error(f"metadata split {split!r} row {index} is not an object")
        if "horizon" in row:
            value = row["horizon"]
            if isinstance(value, bool) or not isinstance(value, Integral) or int(value) != length:
                _error(f"metadata split {split!r} row {index} horizon does not match archive")
        rows.append(row)
    return rows


def target_ids(
    records: Sequence[Mapping[str, Any]], valid: Any, vocabulary_size: int = DEFAULT_VOCABULARY_SIZE
) -> np.ndarray:
    """Align metadata next-token targets to a padded ``[episodes, horizon]`` mask."""

    vocab = _vocabulary_size(vocabulary_size)
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(records, Sequence):
        _error("records must be a sequence of episode objects")
    count = len(records)
    try:
        valid_array = np.asarray(valid)
    except Exception as exc:
        raise FeatureTokenPipelineError("valid must be a boolean [episodes, horizon] array") from exc
    if valid_array.ndim != 2 or valid_array.shape[0] != count or valid_array.dtype.kind != "b":
        _error("valid must be a boolean [episodes, horizon] array aligned with records")
    mask = np.ascontiguousarray(valid_array, dtype=np.bool_)
    result = np.full(mask.shape, -1, dtype=np.int64)
    for episode_index, row in enumerate(records):
        if not isinstance(row, Mapping):
            _error(f"record {episode_index} is not a mapping")
        if "target_next_token_ids" not in row:
            _error(f"record {episode_index} lacks target_next_token_ids")
        targets = _sequence(row["target_next_token_ids"], f"record {episode_index} target_next_token_ids")
        if len(targets) > mask.shape[1]:
            _error(f"record {episode_index} has more target rows than the trajectory horizon")
        saw_terminal = False
        for time_index in range(mask.shape[1]):
            present = time_index < len(targets)
            value = targets[time_index] if present else None
            is_valid = bool(mask[episode_index, time_index])
            if not is_valid:
                if present and value is not None:
                    _error(f"record {episode_index} has a nonterminal target on padded time {time_index}")
                continue
            if not present:
                _error(f"record {episode_index} is missing target for valid time {time_index}")
            if value is None:
                saw_terminal = True
                continue
            if saw_terminal:
                _error(f"record {episode_index} has a valid target after its terminal target")
            result[episode_index, time_index] = _token_id(
                value, f"record {episode_index} target at time {time_index}", vocab
            )
    return result


def candidate_lexicon(
    records: Sequence[Mapping[str, Any]], vocabulary_size: int = DEFAULT_VOCABULARY_SIZE
) -> tuple[np.ndarray, tuple[str, ...]]:
    """Build a sorted lexicon from exactly the supplied records."""

    vocab = _vocabulary_size(vocabulary_size)
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(records, Sequence) or not records:
        _error("records must be a nonempty sequence of episode objects")
    pieces_by_id: dict[int, str] = {}
    for episode_index, row in enumerate(records):
        if not isinstance(row, Mapping):
            _error(f"record {episode_index} is not a mapping")
        if "target_next_token_ids" not in row or "target_next_token_pieces" not in row:
            _error(f"record {episode_index} lacks aligned target IDs/pieces")
        targets = _sequence(row["target_next_token_ids"], f"record {episode_index} target IDs")
        target_pieces = _sequence(row["target_next_token_pieces"], f"record {episode_index} target pieces")
        if len(targets) != len(target_pieces):
            _error(f"record {episode_index} target IDs and pieces are not row-aligned")
        if "teacher_top_candidates" not in row:
            _error(f"record {episode_index} lacks teacher_top_candidates")
        teachers = _sequence(row["teacher_top_candidates"], f"record {episode_index} teacher candidates")
        if len(teachers) != len(targets):
            _error(f"record {episode_index} teacher candidates are not row-aligned")

        def register(token_id: int, piece: str, label: str) -> None:
            previous = pieces_by_id.get(token_id)
            if previous is not None and previous != piece:
                _error(f"{label} gives token {token_id} conflicting display pieces")
            pieces_by_id[token_id] = piece

        for time_index, (target, target_piece, candidates) in enumerate(zip(targets, target_pieces, teachers)):
            if target is not None:
                token = _token_id(target, f"record {episode_index} target at time {time_index}", vocab)
                if not isinstance(target_piece, str):
                    _error(f"record {episode_index} target piece at time {time_index} is not a string")
                register(token, target_piece, f"record {episode_index} target")
            elif target_piece is not None:
                _error(f"record {episode_index} terminal target has a non-null display piece")
            candidate_rows = _sequence(candidates, f"record {episode_index} teacher row {time_index}")
            if not candidate_rows or len(candidate_rows) > _MAX_TEACHER_CANDIDATES:
                _error(
                    f"record {episode_index} teacher row {time_index} must contain 1..{_MAX_TEACHER_CANDIDATES} candidates"
                )
            for candidate_index, candidate in enumerate(candidate_rows):
                if not isinstance(candidate, Mapping) or "token_id" not in candidate or "piece" not in candidate:
                    _error(f"record {episode_index} teacher candidate {time_index}:{candidate_index} is malformed")
                token = _token_id(
                    candidate["token_id"],
                    f"record {episode_index} teacher candidate {time_index}:{candidate_index}",
                    vocab,
                )
                piece = candidate["piece"]
                if not isinstance(piece, str):
                    _error(f"record {episode_index} teacher candidate {time_index}:{candidate_index} piece is not a string")
                if "logit" in candidate:
                    logit = candidate["logit"]
                    if isinstance(logit, bool) or not isinstance(logit, (int, float)) or not math.isfinite(float(logit)):
                        _error(f"record {episode_index} teacher candidate {time_index}:{candidate_index} logit is non-finite")
                register(token, piece, f"record {episode_index} teacher candidate")
    ids = np.ascontiguousarray(np.asarray(sorted(pieces_by_id), dtype=np.int64))
    return ids, tuple(pieces_by_id[int(token_id)] for token_id in ids)


def _asset_descriptor(array: np.ndarray) -> dict[str, Any]:
    return {
        "dtype": str(array.dtype.newbyteorder("<")),
        "shape": list(array.shape),
        "sha256": sha256_array(array),
    }
def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise FeatureTokenPipelineError(f"JSON manifest is not serializable: {exc}") from exc


def _json_digest_without_receipt(value: Mapping[str, Any]) -> str:
    body = dict(value)
    body.pop("json_sha256", None)
    return hashlib.sha256(_canonical_json_bytes(body)).hexdigest()




@dataclass(frozen=True)
class CandidateAssets:
    """Frozen output-head rows and their bounded token display lexicon."""

    token_ids: np.ndarray
    rows: np.ndarray
    pieces: tuple[str, ...]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        ids = _integer_vector(self.token_ids, "candidate token_ids")
        if np.any(ids < 0) or np.any(ids >= DEFAULT_VOCABULARY_SIZE):
            _error(f"candidate token_ids must be in [0, {DEFAULT_VOCABULARY_SIZE})")
        if ids.size == 0:
            _error("candidate token_ids must not be empty")
        if np.any(ids[1:] <= ids[:-1]):
            _error("candidate token_ids must be strictly increasing and unique")
        values = _finite_float32(self.rows, "candidate rows", ndim=2)
        if values.shape[0] != ids.size:
            _error("candidate rows and token_ids have different counts")
        if values.shape[1] < 1:
            _error("candidate rows must have a nonzero feature dimension")
        if isinstance(self.pieces, (str, bytes, bytearray)):
            _error("candidate pieces must be a sequence of strings")
        pieces = tuple(self.pieces)
        if len(pieces) != ids.size or not all(isinstance(piece, str) for piece in pieces):
            _error("candidate pieces must align with token_ids")
        if not isinstance(self.metadata, Mapping):
            _error("candidate metadata must be an object")
        metadata = dict(self.metadata)
        _json_finite(metadata, "candidate metadata")
        object.__setattr__(self, "token_ids", ids)
        object.__setattr__(self, "rows", values)
        object.__setattr__(self, "pieces", pieces)
        object.__setattr__(self, "metadata", metadata)

    @property
    def ids(self) -> np.ndarray:
        """Alias useful to callers that refer to the lexicon as IDs."""

        return self.token_ids


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise FeatureTokenPipelineError(f"could not create output directory for {path}: {exc}") from exc
    temporary: str | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise FeatureTokenPipelineError(f"could not atomically write {path}: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def save_candidate_assets(
    npz_path: str | os.PathLike[str],
    json_path: str | os.PathLike[str],
    token_ids: Any,
    rows: Any,
    pieces: Sequence[str],
    metadata: Mapping[str, Any] | None = None,
) -> CandidateAssets:
    """Atomically write bounded candidate rows and a hash-checked JSON manifest."""

    npz = _path(npz_path, "candidate NPZ path")
    manifest_path = _path(json_path, "candidate JSON path")
    if npz.resolve() == manifest_path.resolve():
        _error("candidate NPZ and JSON paths must differ")
    ids = _integer_vector(token_ids, "candidate token_ids")
    values = _finite_float32(rows, "candidate rows", ndim=2)
    asset_metadata = {} if metadata is None else metadata
    assets = CandidateAssets(ids, values, tuple(pieces), asset_metadata)
    envelope = {
        "schema": FEATURE_TOKEN_ASSET_SCHEMA,
        "token_ids": _asset_descriptor(assets.token_ids),
        "rows": _asset_descriptor(assets.rows),
        "pieces": list(assets.pieces),
        "metadata": dict(assets.metadata),
    }
    envelope["json_sha256"] = _json_digest_without_receipt(envelope)
    npz_temporary: str | None = None
    try:
        npz.parent.mkdir(parents=True, exist_ok=True)
        encoded_manifest = _canonical_json_bytes(envelope)
        with tempfile.NamedTemporaryFile(
            mode="w+b", prefix=f".{npz.name}.", suffix=".tmp", dir=str(npz.parent), delete=False
        ) as handle:
            np.savez(handle, token_ids=assets.token_ids, rows=assets.rows)
            handle.flush()
            os.fsync(handle.fileno())
            npz_temporary = handle.name
    except (OSError, ValueError, TypeError) as exc:
        if npz_temporary is not None:
            try:
                os.unlink(npz_temporary)
            except OSError:
                pass
        raise FeatureTokenPipelineError(f"could not stage candidate NPZ: {exc}") from exc
    assert npz_temporary is not None
    try:
        _atomic_write_bytes(manifest_path, encoded_manifest)
        os.replace(npz_temporary, npz)
        npz_temporary = None
    except OSError as exc:
        if npz_temporary is not None:
            try:
                os.unlink(npz_temporary)
            except OSError:
                pass
        raise FeatureTokenPipelineError(f"could not atomically commit candidate assets: {exc}") from exc
    return assets


def load_candidate_assets(
    npz_path: str | os.PathLike[str],
    json_path: str | os.PathLike[str],
    expected_feature_dim: int = EXPECTED_FEATURE_DIMENSION,
) -> CandidateAssets:
    """Load candidate assets and verify manifest shape, dtype, and SHA-256 receipts."""

    npz = _path(npz_path, "candidate NPZ path")
    manifest_path = _path(json_path, "candidate JSON path")
    dimension = _positive_int(expected_feature_dim, "expected_feature_dim")
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            envelope = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise FeatureTokenPipelineError(f"could not load candidate manifest: {exc}") from exc
    if not isinstance(envelope, Mapping) or envelope.get("schema") != FEATURE_TOKEN_ASSET_SCHEMA:
        _error(f"candidate manifest schema must be {FEATURE_TOKEN_ASSET_SCHEMA!r}")
    _json_finite(envelope, "candidate manifest")
    recorded_json_digest = envelope.get("json_sha256")
    if not isinstance(recorded_json_digest, str) or len(recorded_json_digest) != 64:
        _error("candidate manifest lacks a valid json_sha256 receipt")
    if recorded_json_digest != _json_digest_without_receipt(envelope):
        _error("candidate manifest JSON SHA-256 verification failed")
    for key in ("token_ids", "rows", "pieces", "metadata"):
        if key not in envelope:
            _error(f"candidate manifest lacks {key}")
    try:
        with np.load(npz, allow_pickle=False) as archive:
            if set(archive.files) != {"token_ids", "rows"}:
                _error("candidate NPZ keys do not match the strict schema")
            ids = np.array(archive["token_ids"], copy=True)
            values = np.array(archive["rows"], copy=True)
    except FeatureTokenPipelineError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise FeatureTokenPipelineError(f"could not load candidate NPZ: {exc}") from exc
    if ids.dtype.kind != "i" or ids.dtype.itemsize != 8:
        _error("candidate token_ids must be int64")
    if values.dtype.kind != "f" or values.dtype.itemsize != 4:
        _error("candidate rows must be float32")
    if values.ndim != 2 or values.shape[1] != dimension:
        _error(f"candidate rows must have shape [V, {dimension}]")
    for name, array in (("token_ids", ids), ("rows", values)):
        descriptor = envelope[name]
        if not isinstance(descriptor, Mapping):
            _error(f"candidate manifest {name} descriptor is malformed")
        if descriptor.get("shape") != list(array.shape) or descriptor.get("dtype") != str(array.dtype.newbyteorder("<")):
            _error(f"candidate manifest {name} shape or dtype does not match NPZ")
        if descriptor.get("sha256") != sha256_array(array):
            _error(f"candidate {name} SHA-256 verification failed")
    pieces_value = envelope["pieces"]
    if not isinstance(pieces_value, list) or len(pieces_value) != ids.size or not all(isinstance(piece, str) for piece in pieces_value):
        _error("candidate manifest pieces do not align with NPZ IDs")
    metadata = envelope["metadata"]
    if not isinstance(metadata, Mapping):
        _error("candidate manifest metadata must be an object")
    return CandidateAssets(ids, values, tuple(pieces_value), metadata)


def extract_candidate_rows(
    model_path: str | os.PathLike[str],
    dll_path: str | os.PathLike[str] | None,
    token_ids: Sequence[int],
) -> np.ndarray:
    """Extract only the requested frozen Qwen output rows and close the head."""

    ids = _integer_vector(token_ids, "candidate token_ids")
    if np.any(ids < 0) or np.any(ids >= DEFAULT_VOCABULARY_SIZE):
        _error(f"candidate token_ids must be in [0, {DEFAULT_VOCABULARY_SIZE})")
    try:
        global FieldLanguageHead  # type: ignore[global-variable-not-assigned]
        head_cls = globals().get("FieldLanguageHead")
        if head_cls is None:
            try:
                from .l18_field_language_head import FieldLanguageHead as head_cls  # type: ignore[no-redef]
            except ImportError:
                from l18_field_language_head import FieldLanguageHead as head_cls  # type: ignore[no-redef]
            globals()["FieldLanguageHead"] = head_cls
        head = head_cls(model_path, dll_path, enabled=True)
    except Exception as exc:
        raise FeatureTokenPipelineError(f"could not open FieldLanguageHead: {exc}") from exc
    try:
        result = np.asarray(head.candidate_rows(ids), dtype=np.float32)
        if result.shape != (ids.size, EXPECTED_FEATURE_DIMENSION):
            _error(
                f"candidate rows must have shape [{ids.size}, {EXPECTED_FEATURE_DIMENSION}], got {result.shape}"
            )
        if not np.isfinite(result).all():
            _error("candidate rows contain non-finite values")
        return np.ascontiguousarray(result, dtype=np.float32)
    except FeatureTokenPipelineError:
        raise
    except Exception as exc:
        raise FeatureTokenPipelineError(f"could not extract candidate rows: {exc}") from exc
    finally:
        try:
            head.close()
        except Exception as exc:
            raise FeatureTokenPipelineError(f"could not close FieldLanguageHead: {exc}") from exc


def _trajectory_tensor(trajectory: Any, name: str) -> torch.Tensor:
    value = getattr(trajectory, name, None)
    if not isinstance(value, torch.Tensor):
        _error(f"trajectory.{name} must be a torch tensor")
    return value


def causal_prior_features(model: Any, trajectory: Any, *, device: torch.device | str) -> np.ndarray:
    """Run the chronological prior/correction split without observation leakage."""

    observations = _trajectory_tensor(trajectory, "observations")
    actions = _trajectory_tensor(trajectory, "actions")
    valid = _trajectory_tensor(trajectory, "valid")
    resets = _trajectory_tensor(trajectory, "resets")
    if observations.ndim != 3 or actions.ndim != 3:
        _error("trajectory observations/actions must have shape [B, T, D]")
    batch_size, horizon, observation_dim = observations.shape
    if actions.shape[:2] != (batch_size, horizon):
        _error("trajectory observations/actions have mismatched batch or horizon")
    if valid.shape != (batch_size, horizon) or resets.shape != (batch_size, horizon):
        _error("trajectory valid/resets have mismatched batch or horizon")
    if not valid.dtype == torch.bool or not resets.dtype == torch.bool:
        _error("trajectory valid/resets must be boolean tensors")
    if not observations.dtype.is_floating_point or not actions.dtype.is_floating_point or actions.dtype != observations.dtype:
        _error("trajectory observations/actions must share a floating dtype")
    if not all(bool(torch.isfinite(value).all().item()) for value in (observations, actions)):
        _error("trajectory observations/actions must be finite")
    if bool(torch.any(resets & ~valid).item()):
        _error("trajectory resets cannot occur on invalid steps")
    target_device = torch.device(device)
    obs = observations.to(device=target_device)
    act = actions.to(device=target_device)
    mask = valid.to(device=target_device)
    reset_mask = resets.to(device=target_device)
    was_training = getattr(model, "training", None)
    try:
        model.eval()
        with torch.no_grad():
            state = model.initial_state(batch_size, device=target_device, dtype=obs.dtype)
            saved = torch.zeros((batch_size, horizon, observation_dim), device=target_device, dtype=torch.float32)
            for time_index in range(horizon):
                action_t = act[:, time_index]
                observation_t = obs[:, time_index]
                valid_t = mask[:, time_index]
                reset_t = reset_mask[:, time_index]
                imagined = model.imagine_step(
                    action_t,
                    state,
                    valid=valid_t,
                    reset=reset_t,
                    sample=False,
                )
                prior = getattr(imagined, "observation_mean", None)
                if not isinstance(prior, torch.Tensor) or prior.shape != (batch_size, observation_dim):
                    _error(f"imagine_step observation_mean has the wrong shape at time {time_index}")
                if not bool(torch.isfinite(prior).all().item()):
                    _error(f"imagine_step observation_mean is non-finite at time {time_index}")
                saved[:, time_index] = prior.to(dtype=torch.float32)
                corrected = model.observe_step(
                    observation_t,
                    action_t,
                    state,
                    valid=valid_t,
                    reset=reset_t,
                    sample=False,
                )
                next_state = getattr(corrected, "state", None)
                if next_state is None:
                    _error(f"observe_step returned no state at time {time_index}")
                state = next_state
            result = saved.detach().cpu().numpy()
    except FeatureTokenPipelineError:
        raise
    except Exception as exc:
        raise FeatureTokenPipelineError(f"causal prior feature extraction failed: {exc}") from exc
    finally:
        if was_training is not None:
            try:
                model.train(bool(was_training))
            except Exception:
                pass
    if result.shape != (batch_size, horizon, observation_dim) or not np.isfinite(result).all():
        _error("causal prior features have invalid shape or non-finite values")
    return np.ascontiguousarray(result, dtype=np.float32)


def supervision_rows(
    prior_standardized: Any,
    target_ids_array: Any,
    valid: Any,
    normalizer: Normalization,
    token_ids: Any,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """De-standardise and retain valid prior rows whose target is in the lexicon."""

    prior = _finite_float32(prior_standardized, "prior_standardized", ndim=3)
    if not isinstance(normalizer, Normalization):
        _error("normalizer must be a Normalization instance")
    if prior.shape[2] != normalizer.observation_mean.size:
        _error("prior_standardized dimension does not match the normalizer")
    ids = _integer_vector(token_ids, "candidate token_ids")
    if np.any(ids < 0) or np.any(ids >= DEFAULT_VOCABULARY_SIZE):
        _error(f"candidate token_ids must be in [0, {DEFAULT_VOCABULARY_SIZE})")
    if np.any(ids[1:] <= ids[:-1]):
        _error("candidate token_ids must be strictly increasing and unique")
    try:
        targets = np.asarray(target_ids_array)
    except Exception as exc:
        raise FeatureTokenPipelineError("target_ids must be an int64 [B, T] array") from exc
    if targets.shape != prior.shape[:2] or targets.dtype.kind not in {"i", "u"} or targets.dtype.itemsize > 8:
        _error("target_ids must be an integer array aligned with prior_standardized")
    targets = np.asarray(targets, dtype=np.int64)
    mask = _bool_mask(valid, prior.shape[:2], "valid")
    if np.any(targets < -1):
        _error("target_ids may only contain -1 or vocabulary IDs")
    rank = {int(token_id): index for index, token_id in enumerate(ids.tolist())}
    selected: list[tuple[int, int, int]] = []
    for episode_index in range(prior.shape[0]):
        for time_index in range(prior.shape[1]):
            token_id = int(targets[episode_index, time_index])
            if not bool(mask[episode_index, time_index]):
                if token_id != -1:
                    _error(f"nonterminal target on invalid trajectory step {episode_index}:{time_index}")
                continue
            if token_id == -1:
                continue
            if token_id not in rank:
                _error(f"target token {token_id} is absent from the supplied candidate lexicon")
            selected.append((episode_index, time_index, rank[token_id]))
    raw_all = normalizer.observation_raw(prior)
    if selected:
        episode_indices = np.asarray([item[0] for item in selected], dtype=np.int64)
        time_indices = np.asarray([item[1] for item in selected], dtype=np.int64)
        lexicon_indices = np.asarray([item[2] for item in selected], dtype=np.int64)
        features_raw = np.ascontiguousarray(raw_all[episode_indices, time_indices], dtype=np.float32)
    else:
        episode_indices = np.empty((0,), dtype=np.int64)
        time_indices = np.empty((0,), dtype=np.int64)
        lexicon_indices = np.empty((0,), dtype=np.int64)
        features_raw = np.empty((0, prior.shape[2]), dtype=np.float32)
    if not np.isfinite(features_raw).all():
        _error("supervision features contain non-finite values")
    return features_raw, lexicon_indices, episode_indices, time_indices


__all__ = [
    "CandidateAssets",
    "DEFAULT_VOCABULARY_SIZE",
    "EXPECTED_FEATURE_DIMENSION",
    "FEATURE_TOKEN_ASSET_SCHEMA",
    "FeatureTokenPipelineError",
    "Normalization",
    "causal_prior_features",
    "candidate_lexicon",
    "episode_records",
    "extract_candidate_rows",
    "load_candidate_assets",
    "load_text_metadata",
    "save_candidate_assets",
    "sha256_array",
    "sha256_file",
    "supervision_rows",
    "target_ids",
]
