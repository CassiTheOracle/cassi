"""Compact residual adapter for reading world features as token candidates.

The decoder deliberately has no vocabulary-sized parameter.  Candidate output
rows are supplied by the caller and are used only for the requested readout.
"""

from __future__ import annotations

import hashlib
import json
import math
import numbers
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor, nn
from torch.nn import functional as F


FEATURE_TOKEN_DECODER_CONFIG_SCHEMA = "cassi.feature-token-decoder.config.v1"
FEATURE_TOKEN_DECODER_CHECKPOINT_SCHEMA = "cassi.feature-token-decoder.checkpoint.v1"
_MAX_TOKEN_ID = (1 << 63) - 1


class CassiFeatureTokenDecoderError(ValueError):
    """Raised when decoder inputs, configuration, or checkpoints are invalid."""


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral) or int(value) < 1:
        raise CassiFeatureTokenDecoderError(f"{name} must be a positive integer")
    return int(value)


def _finite_float(name: str, value: Any, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise CassiFeatureTokenDecoderError(f"{name} must be a finite real number")
    converted = float(value)
    if not math.isfinite(converted) or (positive and converted <= 0.0):
        qualifier = "positive and finite" if positive else "finite"
        raise CassiFeatureTokenDecoderError(f"{name} must be {qualifier}")
    return converted


@dataclass(frozen=True)
class CassiFeatureTokenDecoderConfig:
    """Architecture and temperature bounds for one feature-token decoder."""

    feature_dim: int = 5120
    adapter_rank: int = 64
    adapter_scale: float = 0.1
    min_temperature: float = 0.05
    max_temperature: float = 5.0

    def __post_init__(self) -> None:
        feature_dim = _positive_int("feature_dim", self.feature_dim)
        adapter_rank = _positive_int("adapter_rank", self.adapter_rank)
        adapter_scale = _finite_float("adapter_scale", self.adapter_scale, positive=True)
        min_temperature = _finite_float("min_temperature", self.min_temperature, positive=True)
        max_temperature = _finite_float("max_temperature", self.max_temperature, positive=True)
        if max_temperature <= min_temperature:
            raise CassiFeatureTokenDecoderError(
                "max_temperature must be greater than min_temperature"
            )
        object.__setattr__(self, "feature_dim", feature_dim)
        object.__setattr__(self, "adapter_rank", adapter_rank)
        object.__setattr__(self, "adapter_scale", adapter_scale)
        object.__setattr__(self, "min_temperature", min_temperature)
        object.__setattr__(self, "max_temperature", max_temperature)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_dim": self.feature_dim,
            "adapter_rank": self.adapter_rank,
            "adapter_scale": self.adapter_scale,
            "min_temperature": self.min_temperature,
            "max_temperature": self.max_temperature,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CassiFeatureTokenDecoderConfig":
        if not isinstance(value, Mapping):
            raise CassiFeatureTokenDecoderError("decoder configuration must be a mapping")
        expected = {
            "feature_dim",
            "adapter_rank",
            "adapter_scale",
            "min_temperature",
            "max_temperature",
        }
        payload = dict(value)
        unknown = set(payload) - expected
        if unknown:
            raise CassiFeatureTokenDecoderError(
                f"decoder configuration has unknown fields: {sorted(unknown)!r}"
            )
        try:
            return cls(**payload)
        except CassiFeatureTokenDecoderError:
            raise
        except (TypeError, ValueError) as exc:
            raise CassiFeatureTokenDecoderError(f"invalid decoder configuration: {exc}") from exc

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _validate_features(features: Tensor, config: CassiFeatureTokenDecoderConfig, label: str) -> None:
    if not torch.is_tensor(features):
        raise CassiFeatureTokenDecoderError(f"{label} must be a torch.Tensor")
    if not features.dtype.is_floating_point:
        raise CassiFeatureTokenDecoderError(f"{label} must have a floating-point dtype")
    if features.ndim != 2 or features.shape[1] != config.feature_dim or features.shape[0] < 1:
        raise CassiFeatureTokenDecoderError(
            f"{label} must have shape [B, {config.feature_dim}] with B >= 1"
        )
    if not bool(torch.isfinite(features).all().item()):
        raise CassiFeatureTokenDecoderError(f"{label} must contain only finite values")


def _validate_candidate_rows(
    candidate_rows: Tensor,
    config: CassiFeatureTokenDecoderConfig,
    batch_size: int,
) -> int:
    if not torch.is_tensor(candidate_rows):
        raise CassiFeatureTokenDecoderError("candidate_rows must be a torch.Tensor")
    if not candidate_rows.dtype.is_floating_point:
        raise CassiFeatureTokenDecoderError("candidate_rows must have a floating-point dtype")
    if candidate_rows.ndim == 2:
        if candidate_rows.shape[1] != config.feature_dim or candidate_rows.shape[0] < 1:
            raise CassiFeatureTokenDecoderError(
                f"candidate_rows must have shape [K, {config.feature_dim}] with K >= 1"
            )
        candidate_count = int(candidate_rows.shape[0])
    elif candidate_rows.ndim == 3:
        if (
            candidate_rows.shape[0] != batch_size
            or candidate_rows.shape[2] != config.feature_dim
            or candidate_rows.shape[1] < 1
        ):
            raise CassiFeatureTokenDecoderError(
                f"candidate_rows must have shape [B, K, {config.feature_dim}] with matching B and K >= 1"
            )
        candidate_count = int(candidate_rows.shape[1])
    else:
        raise CassiFeatureTokenDecoderError(
            "candidate_rows must have shape [K, D] or [B, K, D]"
        )
    if not bool(torch.isfinite(candidate_rows).all().item()):
        raise CassiFeatureTokenDecoderError("candidate_rows must contain only finite values")
    return candidate_count


def _validate_token_id(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise CassiFeatureTokenDecoderError("candidate_ids must contain non-bool integers")
    token_id = int(value)
    if token_id < 0 or token_id > _MAX_TOKEN_ID:
        raise CassiFeatureTokenDecoderError(
            f"candidate token IDs must be in [0, {_MAX_TOKEN_ID}]"
        )
    return token_id


def _token_id_rows(candidate_ids: Any) -> list[list[int]]:
    if torch.is_tensor(candidate_ids):
        if candidate_ids.dtype == torch.bool or candidate_ids.dtype.is_floating_point or candidate_ids.dtype.is_complex:
            raise CassiFeatureTokenDecoderError("candidate_ids must have a non-bool integer dtype")
        if candidate_ids.ndim not in (1, 2):
            raise CassiFeatureTokenDecoderError("candidate_ids must have shape [K] or [B, K]")
        raw = candidate_ids.detach().cpu().tolist()
    elif isinstance(candidate_ids, (str, bytes, bytearray)):
        raise CassiFeatureTokenDecoderError("candidate_ids must be an integer sequence or tensor")
    else:
        try:
            raw = list(candidate_ids)
        except (TypeError, ValueError) as exc:
            raise CassiFeatureTokenDecoderError(
                "candidate_ids must be an integer sequence or tensor"
            ) from exc
    if not raw:
        raise CassiFeatureTokenDecoderError("candidate_ids cannot be empty")
    if isinstance(raw[0], (list, tuple)):
        rows: list[list[int]] = []
        for row in raw:
            if not isinstance(row, (list, tuple)) or not row:
                raise CassiFeatureTokenDecoderError("candidate_ids rows must be non-empty integer sequences")
            rows.append([_validate_token_id(item) for item in row])
        return rows
    return [[_validate_token_id(item) for item in raw]]


@dataclass(frozen=True)
class CassiFeatureTokenDecoderCheckpoint:
    """Frozen result returned by :func:`load_feature_token_decoder_checkpoint`."""

    model: "CassiFeatureTokenDecoder"
    step: int
    metadata: dict[str, Any]
    config: CassiFeatureTokenDecoderConfig
    sha256: str

    @property
    def checkpoint_sha256(self) -> str:
        """Compatibility alias making the digest name explicit at call sites."""
        return self.sha256


class CassiFeatureTokenDecoder(nn.Module):
    """A compact residual low-rank adapter and externally supplied candidate readout."""

    def __init__(self, config: CassiFeatureTokenDecoderConfig):
        if not isinstance(config, CassiFeatureTokenDecoderConfig):
            raise CassiFeatureTokenDecoderError("config must be a CassiFeatureTokenDecoderConfig")
        super().__init__()
        self.config = config
        self.down = nn.Linear(config.feature_dim, config.adapter_rank, bias=False)
        self.up = nn.Linear(config.adapter_rank, config.feature_dim, bias=False)
        self.temperature_logit = nn.Parameter(torch.zeros(()))
        with torch.no_grad():
            nn.init.normal_(self.down.weight, mean=0.0, std=1.0 / math.sqrt(config.feature_dim))
            nn.init.normal_(self.up.weight, mean=0.0, std=1.0 / math.sqrt(config.adapter_rank))
        self.register_buffer("_initial_down_weight", self.down.weight.detach().clone())
        self.register_buffer("_initial_up_weight", self.up.weight.detach().clone())

    @property
    def temperature(self) -> Tensor:
        span = self.config.max_temperature - self.config.min_temperature
        return self.config.min_temperature + span * torch.sigmoid(self.temperature_logit)

    @property
    def config_fingerprint(self) -> str:
        return self.config.fingerprint

    def _rms_normalize(self, values: Tensor) -> Tensor:
        variance = values.square().mean(dim=-1, keepdim=True)
        return values * torch.rsqrt(variance + 1.0e-6)

    def adapt(self, features: Tensor) -> Tensor:
        """Apply the identity-initialized residual adapter to ``[B, D]`` features."""
        _validate_features(features, self.config, "features")
        if features.device != self.down.weight.device:
            raise CassiFeatureTokenDecoderError("features and decoder parameters must share a device")
        parameter_dtype = self.down.weight.dtype
        branch_input = self._rms_normalize(features.to(dtype=parameter_dtype))
        current = F.linear(F.linear(branch_input, self.down.weight), self.up.weight)
        initial = F.linear(
            F.linear(branch_input, self._initial_down_weight), self._initial_up_weight
        )
        adapted = features + (current - initial).to(dtype=features.dtype) * self.config.adapter_scale
        if not bool(torch.isfinite(adapted).all().item()):
            raise CassiFeatureTokenDecoderError("adapted features are non-finite")
        return adapted

    def logits(self, features: Tensor, candidate_rows: Tensor) -> Tensor:
        """Score externally supplied candidate rows without registering them as parameters."""
        _validate_features(features, self.config, "features")
        candidate_count = _validate_candidate_rows(candidate_rows, self.config, int(features.shape[0]))
        if candidate_rows.device != features.device:
            raise CassiFeatureTokenDecoderError("features and candidate_rows must share a device")
        adapted = self.adapt(features)
        compute_dtype = torch.promote_types(adapted.dtype, candidate_rows.dtype)
        if compute_dtype in (torch.float16, torch.bfloat16):
            compute_dtype = torch.float32
        adapted_compute = adapted.to(dtype=compute_dtype)
        rows_compute = candidate_rows.to(dtype=compute_dtype)
        temperature = self.temperature.to(device=features.device, dtype=compute_dtype)
        if candidate_rows.ndim == 2:
            result = adapted_compute.matmul(rows_compute.transpose(0, 1)) / temperature
        else:
            result = torch.einsum("bd,bkd->bk", adapted_compute, rows_compute) / temperature
        if result.shape != (features.shape[0], candidate_count):
            raise CassiFeatureTokenDecoderError("decoder logits have an invalid shape")
        if not bool(torch.isfinite(result).all().item()):
            raise CassiFeatureTokenDecoderError("decoder logits are non-finite")
        return result

    def top_k(
        self,
        features: Tensor,
        candidate_rows: Tensor,
        candidate_ids: Any,
        k: int,
    ) -> list[list[dict[str, float | int]]]:
        """Return per-batch deterministic ``token_id``/``logit`` rows."""
        if isinstance(k, bool) or not isinstance(k, numbers.Integral) or int(k) < 1:
            raise CassiFeatureTokenDecoderError("k must be a positive integer")
        k = int(k)
        _validate_features(features, self.config, "features")
        candidate_count = _validate_candidate_rows(candidate_rows, self.config, int(features.shape[0]))
        if k > candidate_count:
            raise CassiFeatureTokenDecoderError("k cannot exceed the candidate count")
        id_rows = _token_id_rows(candidate_ids)
        if len(id_rows) == 1:
            shared_ids = id_rows[0]
            if len(shared_ids) != candidate_count:
                raise CassiFeatureTokenDecoderError("candidate_ids length must equal candidate count")
            ids_for_batch = [shared_ids] * int(features.shape[0])
        else:
            if candidate_rows.ndim != 3 or len(id_rows) != int(features.shape[0]):
                raise CassiFeatureTokenDecoderError("batched candidate_ids must match batch candidate rows")
            if any(len(row) != candidate_count for row in id_rows):
                raise CassiFeatureTokenDecoderError("candidate_ids rows must match candidate count")
            ids_for_batch = id_rows
        scores = self.logits(features, candidate_rows).detach().to(device="cpu", dtype=torch.float64)
        ranked: list[list[dict[str, float | int]]] = []
        for batch_index, id_row in enumerate(ids_for_batch):
            rows = [
                {"token_id": token_id, "logit": float(scores[batch_index, index].item())}
                for index, token_id in enumerate(id_row)
            ]
            rows.sort(key=lambda row: (-float(row["logit"]), int(row["token_id"])))
            ranked.append(rows[:k])
        return ranked


def _json_safe_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        value: dict[str, Any] = {}
    elif not isinstance(metadata, Mapping):
        raise CassiFeatureTokenDecoderError("checkpoint metadata must be a mapping")
    else:
        value = dict(metadata)
    if any(not isinstance(key, str) for key in value):
        raise CassiFeatureTokenDecoderError("checkpoint metadata keys must be strings")
    try:
        encoded = json.dumps(value, allow_nan=False, sort_keys=True)
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise CassiFeatureTokenDecoderError(
            f"checkpoint metadata must be finite JSON data: {exc}"
        ) from exc
    if not isinstance(decoded, dict):
        raise CassiFeatureTokenDecoderError("checkpoint metadata must encode a JSON object")
    return decoded


def _finite_state_dict(state_dict: Mapping[str, Any]) -> bool:
    if not isinstance(state_dict, Mapping) or not state_dict:
        return False
    for value in state_dict.values():
        if not torch.is_tensor(value) or not value.dtype.is_floating_point:
            return False
        if not bool(torch.isfinite(value).all().item()):
            return False
    return True


def _atomic_torch_save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    )
    temporary = Path(handle.name)
    handle.close()
    try:
        torch.save(payload, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def save_feature_token_decoder_checkpoint(
    path: Path | str,
    model: CassiFeatureTokenDecoder,
    *,
    step: int = 0,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    """Atomically save a CPU-portable decoder checkpoint and return its SHA256."""
    if not isinstance(model, CassiFeatureTokenDecoder):
        raise CassiFeatureTokenDecoderError("model must be a CassiFeatureTokenDecoder")
    if isinstance(step, bool) or not isinstance(step, numbers.Integral) or int(step) < 0:
        raise CassiFeatureTokenDecoderError("checkpoint step must be a non-negative integer")
    state = {
        key: value.detach().cpu().clone() if torch.is_tensor(value) else value
        for key, value in model.state_dict().items()
    }
    if not _finite_state_dict(state):
        raise CassiFeatureTokenDecoderError("model contains a non-finite or invalid state tensor")
    payload = {
        "schema": FEATURE_TOKEN_DECODER_CHECKPOINT_SCHEMA,
        "config_schema": FEATURE_TOKEN_DECODER_CONFIG_SCHEMA,
        "config": model.config.to_dict(),
        "config_fingerprint": model.config_fingerprint,
        "model_state": state,
        "step": int(step),
        "metadata": _json_safe_metadata(metadata),
    }
    target = Path(path)
    try:
        _atomic_torch_save(payload, target)
    except CassiFeatureTokenDecoderError:
        raise
    except Exception as exc:
        raise CassiFeatureTokenDecoderError(
            f"decoder checkpoint cannot be saved: {type(exc).__name__}: {exc}"
        ) from exc
    return hashlib.sha256(target.read_bytes()).hexdigest()


def load_feature_token_decoder_checkpoint(
    path: Path | str,
    *,
    device: torch.device | str | None = None,
) -> CassiFeatureTokenDecoderCheckpoint:
    """Load a decoder checkpoint with safe, CPU-default deserialization."""
    target = Path(path)
    if not target.is_file():
        raise CassiFeatureTokenDecoderError(f"decoder checkpoint does not exist: {target}")
    try:
        target_device = torch.device("cpu" if device is None else device)
        payload = torch.load(target, map_location=target_device, weights_only=True)
    except Exception as exc:
        raise CassiFeatureTokenDecoderError(
            f"decoder checkpoint cannot be loaded: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema") != FEATURE_TOKEN_DECODER_CHECKPOINT_SCHEMA:
        raise CassiFeatureTokenDecoderError("decoder checkpoint schema mismatch")
    if payload.get("config_schema") != FEATURE_TOKEN_DECODER_CONFIG_SCHEMA:
        raise CassiFeatureTokenDecoderError("decoder checkpoint configuration schema mismatch")
    config = CassiFeatureTokenDecoderConfig.from_dict(payload.get("config", {}))
    if payload.get("config_fingerprint") != config.fingerprint:
        raise CassiFeatureTokenDecoderError("decoder checkpoint configuration fingerprint mismatch")
    state = payload.get("model_state")
    if not isinstance(state, dict) or not _finite_state_dict(state):
        raise CassiFeatureTokenDecoderError("decoder checkpoint contains invalid model state")
    model = CassiFeatureTokenDecoder(config)
    try:
        model.to(device=target_device)
        model.load_state_dict(state, strict=True)
    except (RuntimeError, ValueError) as exc:
        raise CassiFeatureTokenDecoderError(
            f"decoder checkpoint state mismatch: {exc}"
        ) from exc
    step = payload.get("step")
    if isinstance(step, bool) or not isinstance(step, numbers.Integral) or int(step) < 0:
        raise CassiFeatureTokenDecoderError("decoder checkpoint step is invalid")
    if "metadata" not in payload:
        raise CassiFeatureTokenDecoderError("decoder checkpoint metadata is missing")
    metadata = _json_safe_metadata(payload["metadata"])
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return CassiFeatureTokenDecoderCheckpoint(
        model=model,
        step=int(step),
        metadata=metadata,
        config=config,
        sha256=digest,
    )


__all__ = [
    "FEATURE_TOKEN_DECODER_CONFIG_SCHEMA",
    "FEATURE_TOKEN_DECODER_CHECKPOINT_SCHEMA",
    "CassiFeatureTokenDecoderError",
    "CassiFeatureTokenDecoderConfig",
    "CassiFeatureTokenDecoderCheckpoint",
    "CassiFeatureTokenDecoder",
    "save_feature_token_decoder_checkpoint",
    "load_feature_token_decoder_checkpoint",
]
