"""Loopback OpenAI-compatible provider for the trained Cassi world model.

The provider owns one frozen world model, feature-token decoder, candidate asset
set, and L18 native runtime for its entire process lifetime.  Requests are
serialized because the native runtime has one mutable context and is not
concurrent-safe.  This module is deliberately a closed-loop surface: callers
must opt in with ``cassi_world_mode: "closed_loop"`` and ordinary requests are
never routed to Qwen as a fallback.
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import ipaddress
import json
import math
import os
import sys
import tempfile
import threading
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import torch

try:  # Package imports and direct ``python CassiQwen/...`` use both work.
    from .cassi_feature_token_decoder import (
        CassiFeatureTokenDecoder,
        load_feature_token_decoder_checkpoint,
    )
    from .cassi_feature_token_pipeline import (
        CandidateAssets,
        Normalization,
        load_candidate_assets,
        sha256_array,
        sha256_file,
    )
    from .cassi_world_model import (
        CassiWorldModel,
        load_world_model_checkpoint,
        load_world_model_state,
        save_world_model_state,
    )
    from .l18_generated_token_trajectory import (
        EXPECTED_MODEL_SHA256,
        L18GeneratedTokenTrajectory,
        RuntimeConfig,
    )
    from .run_cassi_world_generation import (
        WorldGenerationError,
        _decode_generated_token,
        _decode_prompt_token,
        _decoder_metadata_compatible,
        _finite_array,
        _freeze_eval,
        _parameter_device,
        _parameter_dtype,
        _select_candidate,
        _standardized_tensors,
        _token_piece,
        _validate_dimensions,
    )
except ImportError:  # pragma: no cover - direct script execution fallback.
    from cassi_feature_token_decoder import (  # type: ignore[no-redef]
        CassiFeatureTokenDecoder,
        load_feature_token_decoder_checkpoint,
    )
    from cassi_feature_token_pipeline import (  # type: ignore[no-redef]
        CandidateAssets,
        Normalization,
        load_candidate_assets,
        sha256_array,
        sha256_file,
    )
    from cassi_world_model import (  # type: ignore[no-redef]
        CassiWorldModel,
        load_world_model_checkpoint,
        load_world_model_state,
        save_world_model_state,
    )
    from l18_generated_token_trajectory import (  # type: ignore[no-redef]
        EXPECTED_MODEL_SHA256,
        L18GeneratedTokenTrajectory,
        RuntimeConfig,
    )
    from run_cassi_world_generation import (  # type: ignore[no-redef]
        WorldGenerationError,
        _decode_generated_token,
        _decode_prompt_token,
        _decoder_metadata_compatible,
        _finite_array,
        _freeze_eval,
        _parameter_device,
        _parameter_dtype,
        _select_candidate,
        _standardized_tensors,
        _token_piece,
        _validate_dimensions,
    )


PROTOCOL = "cassi.world-provider"
VERSION = 1
WORLD_MODE = "closed_loop"
DEFAULT_PORT = 8082
DEFAULT_MAX_TOKENS = 32
DEFAULT_TOP_K = 8
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_CONTEXT_MESSAGES = 128
MAX_SESSION_ID = 256
MAX_TOKENS_LIMIT = 512


class ProviderError(RuntimeError):
    """A checked provider request, asset, or runtime failure."""

    def __init__(self, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.status = int(status)


@dataclass(frozen=True)
class ProviderConfig:
    """Immutable process configuration for one loaded provider."""

    world_checkpoint: Path
    decoder_checkpoint: Path
    normalization: Path
    candidate_npz: Path
    candidate_json: Path
    model: Path
    state_dir: Path
    host: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    context_size: int | None = None
    gpu_layers: int | None = None
    device: str = "cpu"
    max_tokens: int = DEFAULT_MAX_TOKENS
    seed: int = 0
    dll_dir: Path | None = None

    def __post_init__(self) -> None:
        for name in (
            "world_checkpoint",
            "decoder_checkpoint",
            "normalization",
            "candidate_npz",
            "candidate_json",
            "model",
            "state_dir",
        ):
            object.__setattr__(self, name, Path(getattr(self, name)))
        if self.dll_dir is not None:
            object.__setattr__(self, "dll_dir", Path(self.dll_dir))
        if self.host == "localhost":
            return_host = self.host
        else:
            try:
                parsed = ipaddress.ip_address(self.host)
            except ValueError as exc:
                raise ProviderError("host must be a loopback address", status=2) from exc
            if not parsed.is_loopback:
                raise ProviderError("host must be loopback-only", status=2)
            return_host = self.host
        object.__setattr__(self, "host", return_host)
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise ProviderError("port must be an integer in [1, 65535]", status=2)
        if self.context_size is not None and (
            isinstance(self.context_size, bool) or not isinstance(self.context_size, int) or self.context_size <= 0
        ):
            raise ProviderError("context_size must be a positive integer", status=2)
        if self.gpu_layers is not None and (
            isinstance(self.gpu_layers, bool) or not isinstance(self.gpu_layers, int) or self.gpu_layers < 0
        ):
            raise ProviderError("gpu_layers must be a non-negative integer", status=2)
        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or not 1 <= self.max_tokens <= MAX_TOKENS_LIMIT:
            raise ProviderError(f"max_tokens must be an integer in [1, {MAX_TOKENS_LIMIT}]", status=2)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ProviderError("seed must be a non-negative integer", status=2)
        try:
            torch.device(self.device)
        except (RuntimeError, TypeError) as exc:
            raise ProviderError(f"invalid torch device {self.device!r}", status=2) from exc


def _json_finite(value: Any, label: str = "JSON value") -> None:
    """Reject NaN, infinity, and values that cannot be represented in JSON."""

    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProviderError(f"{label} contains a non-finite number", status=500)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProviderError(f"{label} contains a non-string key", status=500)
            _json_finite(item, f"{label}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _json_finite(item, f"{label}[{index}]")
        return
    raise ProviderError(f"{label} contains unsupported value {type(value).__name__}", status=500)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    """Commit a small JSON checkpoint with replace-on-success semantics."""

    _json_finite(value, "session checkpoint")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")
    temporary: str | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise ProviderError(f"could not atomically save session metadata {path}: {exc}", status=500) from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ProviderError(f"session metadata is not valid JSON: {path}: {exc}", status=500) from exc
    if not isinstance(value, dict):
        raise ProviderError(f"session metadata must be an object: {path}", status=500)
    _json_finite(value, "session metadata")
    return value


def _render_messages(messages: Any) -> str:
    """Render messages using the existing local Qwen chat-template convention."""

    if not isinstance(messages, list) or not messages or len(messages) > MAX_CONTEXT_MESSAGES:
        raise ProviderError(f"messages must contain 1..{MAX_CONTEXT_MESSAGES} entries")
    parts: list[str] = []
    for index, message in enumerate(messages):
        if not isinstance(message, Mapping):
            raise ProviderError(f"message {index} is not an object")
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not role or not isinstance(content, str):
            raise ProviderError(f"message {index} requires string role/content")
        if role not in {"system", "user", "assistant", "tool"}:
            raise ProviderError(f"unsupported message role: {role!r}")
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
    parts.append("<|im_start|>assistant\n")
    return "".join(parts)


def _session_id(request: Mapping[str, Any]) -> str:
    value = request.get("user")
    if value is None and isinstance(request.get("metadata"), Mapping):
        value = request["metadata"].get("cassi_session_id")
    if value is None:
        return f"ephemeral-{uuid.uuid4().hex}"
    if not isinstance(value, str) or not value or len(value) > MAX_SESSION_ID:
        raise ProviderError("user/cassi_session_id must be non-empty bounded text")
    return value


def _finite_nonnegative(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProviderError(f"{label} must be a finite non-negative number")
    converted = float(value)
    if not math.isfinite(converted) or converted < 0.0:
        raise ProviderError(f"{label} must be a finite non-negative number")
    return converted


def _requested_max_tokens(value: Any, maximum: int) -> int:
    if value is None:
        return maximum
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ProviderError(f"max_tokens must be an integer in [1, {maximum}]")
    return int(value)


class SessionCheckpointStore:
    """Hash-addressed session metadata paired with an atomic torch state file."""

    def __init__(self, root: Path, *, checkpoint_hashes: Mapping[str, str]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.checkpoint_hashes = dict(checkpoint_hashes)

    def state_path(self, session_id: str) -> Path:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.state.pt"

    def metadata_path(self, session_id: str) -> Path:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    def load(self, session_id: str) -> dict[str, Any] | None:
        metadata_path = self.metadata_path(session_id)
        state_path = self.state_path(session_id)
        value = _load_json(metadata_path)
        if value is None:
            if state_path.is_file():
                raise ProviderError(f"session state exists without metadata: {state_path}", status=500)
            return None
        if value.get("protocol") != PROTOCOL or value.get("version") != VERSION:
            raise ProviderError("session metadata protocol/version mismatch", status=500)
        if value.get("session_id") != session_id:
            raise ProviderError("session metadata identity mismatch", status=500)
        if value.get("checkpoint_hashes") != self.checkpoint_hashes:
            raise ProviderError("session metadata checkpoint hashes do not match loaded assets", status=500)
        if value.get("state_path") != str(state_path):
            raise ProviderError("session metadata state path is not session-isolated", status=500)
        recorded_hash = value.get("state_sha256")
        if not isinstance(recorded_hash, str) or len(recorded_hash) != 64:
            raise ProviderError("session metadata state hash is malformed", status=500)
        try:
            actual_hash = sha256_file(state_path)
        except Exception as exc:
            raise ProviderError(f"session state hash cannot be read: {state_path}", status=500) from exc
        if actual_hash != recorded_hash:
            raise ProviderError("session state hash does not match metadata", status=500)
        return value

    def save(self, session_id: str, value: Mapping[str, Any]) -> None:
        if value.get("protocol") != PROTOCOL or value.get("version") != VERSION:
            raise ProviderError("cannot save session metadata with wrong protocol/version", status=500)
        if value.get("session_id") != session_id:
            raise ProviderError("cannot save session metadata for another session", status=500)
        _atomic_json(self.metadata_path(session_id), value)


class CassiWorldProvider:
    """One-time loaded world/decoder/native runtime with serialized requests."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.model_id = config.model.name
        self._lock = threading.RLock()
        self._started = False
        self._world: CassiWorldModel | None = None
        self._decoder: CassiFeatureTokenDecoder | None = None
        self._normalizer: Normalization | None = None
        self._assets: CandidateAssets | None = None
        self._candidate_rows: torch.Tensor | None = None
        self._runtime: L18GeneratedTokenTrajectory | None = None
        self._device = self._resolve_device(config.device)
        self._checkpoint_hashes: dict[str, str] = {}
        self._fingerprints: dict[str, str] = {}
        self._store: SessionCheckpointStore | None = None

    @staticmethod
    def _resolve_device(value: str) -> torch.device:
        device = torch.device(value)
        if device.type == "cuda" and device.index is None:
            return torch.device("cuda:0")
        return device

    @property
    def started(self) -> bool:
        return self._started

    @property
    def checkpoint_hashes(self) -> Mapping[str, str]:
        return dict(self._checkpoint_hashes)

    @property
    def fingerprints(self) -> Mapping[str, str]:
        return dict(self._fingerprints)

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            world: CassiWorldModel | None = None
            decoder: CassiFeatureTokenDecoder | None = None
            runtime: L18GeneratedTokenTrajectory | None = None
            try:
                world_hash = self._hash_path(self.config.world_checkpoint)
                decoder_hash = self._hash_path(self.config.decoder_checkpoint)
                normalization_hash = self._hash_path(self.config.normalization)
                candidate_npz_hash = self._hash_path(self.config.candidate_npz)
                candidate_json_hash = self._hash_path(self.config.candidate_json)
                model_hash = self._hash_path(self.config.model)
                world_receipt = load_world_model_checkpoint(self.config.world_checkpoint, device=self._device)
                world = world_receipt.model
                decoder_receipt = load_feature_token_decoder_checkpoint(
                    self.config.decoder_checkpoint, device=self._device
                )
                decoder = decoder_receipt.model
                normalizer = Normalization.load(self.config.normalization)
                assets = load_candidate_assets(
                    self.config.candidate_npz,
                    self.config.candidate_json,
                    expected_feature_dim=int(world.config.observation_dim),
                )
                _freeze_eval(world)
                _freeze_eval(decoder)
                _validate_dimensions(world, decoder, normalizer, assets)
                candidate_ids_hash = sha256_array(assets.token_ids)
                candidate_rows_hash = sha256_array(assets.rows)
                _decoder_metadata_compatible(
                    decoder_receipt.metadata,
                    world_checkpoint_sha256=world_hash,
                    normalization_sha256=normalization_hash,
                    candidate_npz_sha256=candidate_npz_hash,
                    candidate_json_sha256=candidate_json_hash,
                    candidate_token_ids_sha256=candidate_ids_hash,
                    candidate_rows_sha256=candidate_rows_hash,
                    world=world,
                    assets=assets,
                )
                if _parameter_device(world) != self._device or _parameter_device(decoder) != self._device:
                    raise ProviderError("loaded model device differs from requested device", status=500)
                model_dtype = _parameter_dtype(world)
                if model_dtype not in (torch.float32, torch.float64, torch.float16, torch.bfloat16):
                    raise ProviderError("world model uses an unsupported non-floating dtype", status=500)
                decoder_dtype = _parameter_dtype(decoder)
                runtime_config = RuntimeConfig(
                    model_path=self.config.model,
                    dll_dir=self.config.dll_dir or Path(__file__).resolve().parent,
                    context_size=self.config.context_size if self.config.context_size is not None else RuntimeConfig().context_size,
                    gpu_layers=self.config.gpu_layers if self.config.gpu_layers is not None else RuntimeConfig().gpu_layers,
                    expected_model_sha256=EXPECTED_MODEL_SHA256,
                )
                runtime = L18GeneratedTokenTrajectory(runtime_config)
                if runtime.hidden_dimension != int(world.config.observation_dim) or runtime.hidden_dimension != int(world.config.action_dim):
                    raise ProviderError("L18 hidden width does not match world observation/action dimensions", status=500)
                for candidate_index, candidate_id_value in enumerate(assets.token_ids.tolist()):
                    candidate_id = int(candidate_id_value)
                    if candidate_id < 0 or candidate_id >= runtime.vocabulary_size:
                        raise ProviderError(f"candidate token {candidate_id} is outside runtime vocabulary", status=500)
                    if _token_piece(runtime, candidate_id) != assets.pieces[candidate_index]:
                        raise ProviderError(f"candidate piece mismatch for token {candidate_id}", status=500)
                candidate_rows = torch.as_tensor(assets.rows, device=self._device, dtype=decoder_dtype)
                if candidate_rows.device != self._device:
                    raise ProviderError("decoder candidate rows are not on requested device", status=500)
                checkpoint_hashes = {
                    "world_checkpoint_sha256": world_hash,
                    "decoder_checkpoint_sha256": decoder_hash,
                    "normalization_sha256": normalization_hash,
                    "candidate_npz_sha256": candidate_npz_hash,
                    "candidate_json_sha256": candidate_json_hash,
                    "model_sha256": model_hash,
                }
                fingerprints = {
                    "world_config_fingerprint": world.config_fingerprint,
                    "decoder_config_fingerprint": decoder.config_fingerprint,
                    "candidate_token_ids_sha256": candidate_ids_hash,
                    "candidate_rows_sha256": candidate_rows_hash,
                }
                store = SessionCheckpointStore(self.config.state_dir, checkpoint_hashes=checkpoint_hashes)
            except ProviderError:
                if runtime is not None:
                    runtime.close(suppress=True)
                raise
            except (OSError, ValueError, RuntimeError, WorldGenerationError, TypeError) as exc:
                if runtime is not None:
                    runtime.close(suppress=True)
                raise ProviderError(f"provider asset/runtime startup failed: {type(exc).__name__}: {exc}", status=500) from exc
            self._world = world
            self._decoder = decoder
            self._normalizer = normalizer
            self._assets = assets
            self._candidate_rows = candidate_rows
            self._runtime = runtime
            self._checkpoint_hashes = checkpoint_hashes
            self._fingerprints = fingerprints
            self._store = store
            self._started = True

    @staticmethod
    def _hash_path(path: Path) -> str:
        try:
            return sha256_file(path)
        except Exception as exc:
            raise ProviderError(f"could not hash required asset {path}: {exc}", status=500) from exc

    def close(self) -> None:
        with self._lock:
            runtime = self._runtime
            self._runtime = None
            self._started = False
            self._world = None
            self._decoder = None
            self._normalizer = None
            self._assets = None
            self._candidate_rows = None
            self._store = None
            if runtime is not None:
                runtime.close(suppress=True)

    def _require(self) -> tuple[
        CassiWorldModel,
        CassiFeatureTokenDecoder,
        Normalization,
        CandidateAssets,
        torch.Tensor,
        L18GeneratedTokenTrajectory,
        SessionCheckpointStore,
    ]:
        if not self._started or any(
            value is None
            for value in (
                self._world,
                self._decoder,
                self._normalizer,
                self._assets,
                self._candidate_rows,
                self._runtime,
                self._store,
            )
        ):
            raise ProviderError("world provider is not started", status=500)
        return (
            self._world,
            self._decoder,
            self._normalizer,
            self._assets,
            self._candidate_rows,
            self._runtime,
            self._store,
        )  # type: ignore[return-value]

    def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Process one explicitly opted-in closed-loop request."""

        with self._lock:
            if not isinstance(request, Mapping):
                raise ProviderError("completion request must be an object")
            if request.get("cassi_world_mode") != WORLD_MODE:
                raise ProviderError('cassi_world_mode must be explicitly set to "closed_loop"')
            if bool(request.get("stream", False)):
                raise ProviderError("streaming is not supported by the closed-loop provider")
            world, decoder, normalizer, assets, candidate_rows, runtime, store = self._require()
            prompt = _render_messages(request.get("messages"))
            session_id = _session_id(request)
            request_id = f"cassi-world-{uuid.uuid4().hex}"
            temperature = _finite_nonnegative(request.get("temperature", 0.0), "temperature")
            max_tokens = _requested_max_tokens(request.get("max_tokens"), self.config.max_tokens)
            prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            checkpoint = store.load(session_id)
            state_path = store.state_path(session_id)
            same_prompt_replay = (
                checkpoint is not None and checkpoint.get("last_prompt_sha256") == prompt_sha256
            )
            model_dtype = _parameter_dtype(world)
            if same_prompt_replay:
                try:
                    state = load_world_model_state(state_path, world, device=self._device)
                except Exception as exc:
                    raise ProviderError(f"could not load session world state: {exc}", status=500) from exc
                if state.batch_size != 1:
                    raise ProviderError("session world state must have batch size one", status=500)
            else:
                checkpoint = None
                state = world.initial_state(1, device=self._device, dtype=model_dtype)
            try:
                runtime.reset_context()
                prompt_ids = tuple(int(token_id) for token_id in runtime.tokenize(prompt))
            except Exception as exc:
                raise ProviderError(f"prompt tokenization failed: {exc}", status=500) from exc
            if not prompt_ids:
                raise ProviderError("prompt tokenization produced no tokens")
            if len(prompt_ids) + max_tokens > runtime.config.context_size:
                raise ProviderError("rendered conversation plus max_tokens exceeds context_size")

            valid = torch.ones((1,), dtype=torch.bool, device=self._device)
            reset = torch.zeros((1,), dtype=torch.bool, device=self._device)
            last_action: torch.Tensor | None = None
            last_action_source: int | None = None
            prompt_pieces: list[str] = []
            for position, token_id in enumerate(prompt_ids):
                try:
                    _, piece, action_raw, observation_raw = _decode_prompt_token(runtime, token_id, position)
                    action, observation, _, _ = _standardized_tensors(
                        normalizer,
                        action_raw,
                        observation_raw,
                        device=self._device,
                        dtype=_parameter_dtype(world),
                    )
                except Exception as exc:
                    raise ProviderError(f"prompt decode failed at token {position}: {exc}", status=500) from exc
                if checkpoint is None:
                    try:
                        with torch.no_grad():
                            observed = world.observe_step(
                                observation,
                                action,
                                state,
                                valid=valid,
                                reset=(valid if position == 0 else reset),
                                sample=False,
                            )
                        state = observed.state
                    except Exception as exc:
                        raise ProviderError(f"world observation failed at prompt token {position}: {exc}", status=500) from exc
                last_action = action
                last_action_source = position
                prompt_pieces.append(piece)
            if last_action is None or last_action_source is None:
                raise ProviderError("no actual action is available for generated-step imagination", status=500)

            generated_ids: list[int] = []
            generated_pieces: list[str] = []
            selected_rows_by_step: list[list[dict[str, Any]]] = []
            selected_candidates: list[dict[str, Any]] = []
            model_dtype = _parameter_dtype(world)
            decoder_dtype = _parameter_dtype(decoder)
            for generated_index in range(max_tokens):
                pre_state = state
                imagine_action = last_action
                imagine_action_source = last_action_source
                try:
                    with torch.no_grad():
                        imagined = world.imagine_step(
                            imagine_action,
                            pre_state,
                            valid=valid,
                            reset=reset,
                            sample=False,
                        )
                    predicted_standardized = _finite_array(
                        imagined.observation_mean[0].detach().cpu().numpy(),
                        "predicted standardized feature",
                        (int(world.config.observation_dim),),
                    )
                    predicted_raw = _finite_array(
                        normalizer.observation_raw(predicted_standardized),
                        "predicted raw feature",
                        (int(world.config.observation_dim),),
                    )
                    decoder_input = torch.as_tensor(predicted_raw, device=self._device, dtype=decoder_dtype).reshape(1, -1)
                    if not bool(torch.isfinite(decoder_input).all().item()):
                        raise ProviderError("decoder feature input is non-finite", status=500)
                    with torch.no_grad():
                        scores = decoder.logits(decoder_input, candidate_rows)
                    top_rows, selected_id, selected_logit = _select_candidate(
                        scores,
                        assets,
                        top_k=min(DEFAULT_TOP_K, int(assets.token_ids.size)),
                        temperature=temperature,
                        seed=self.config.seed,
                        token_index=generated_index,
                    )
                    if selected_id < 0 or selected_id >= runtime.vocabulary_size:
                        raise ProviderError(f"decoder selected invalid runtime token {selected_id}", status=500)
                    if runtime.token_is_eog(selected_id):
                        raise ProviderError(f"decoder selected EOS/EOG token {selected_id}; refusing unsafe termination")
                    selected_piece = _token_piece(runtime, selected_id)
                    asset_index = int(np.searchsorted(assets.token_ids, selected_id))
                    if asset_index >= assets.token_ids.size or int(assets.token_ids[asset_index]) != selected_id:
                        raise ProviderError("selected token is absent from candidate assets", status=500)
                    if assets.pieces[asset_index] != selected_piece:
                        raise ProviderError("candidate asset piece disagrees with runtime piece", status=500)
                    _, actual_piece, actual_action_raw, actual_observation_raw = _decode_generated_token(
                        runtime,
                        selected_id,
                        len(prompt_ids) + generated_index,
                    )
                    if actual_piece != selected_piece:
                        raise ProviderError("decoded selected token piece changed inside runtime", status=500)
                    actual_action, actual_observation, actual_action_std, actual_observation_std = _standardized_tensors(
                        normalizer,
                        actual_action_raw,
                        actual_observation_raw,
                        device=self._device,
                        dtype=model_dtype,
                    )
                    with torch.no_grad():
                        observed = world.observe_step(
                            actual_observation,
                            actual_action,
                            pre_state,
                            valid=valid,
                            reset=reset,
                            sample=False,
                        )
                    state = observed.state
                except ProviderError:
                    raise
                except (WorldGenerationError, OSError, RuntimeError, ValueError, TypeError) as exc:
                    raise ProviderError(f"closed-loop generation failed at token {generated_index}: {exc}", status=500) from exc
                ranked_rows = [
                    {**dict(row), "rank": int(rank)} for rank, row in enumerate(top_rows)
                ]
                selected_row = next(row for row in ranked_rows if int(row["token_id"]) == int(selected_id))
                generated_ids.append(int(selected_id))
                generated_pieces.append(selected_piece)
                selected_rows_by_step.append(ranked_rows)
                selected_candidates.append(
                    {
                        "token_id": int(selected_id),
                        "piece": selected_piece,
                        "logit": float(selected_logit),
                        "rank": int(selected_row["rank"]),
                    }
                )
                last_action = actual_action
                last_action_source = len(prompt_ids) + generated_index

            try:
                state_sha256 = save_world_model_state(state_path, world, state)
            except Exception as exc:
                raise ProviderError(f"could not save final session world state: {exc}", status=500) from exc
            metadata_value = {
                "protocol": PROTOCOL,
                "version": VERSION,
                "session_id": session_id,
                "model": self.model_id,
                "checkpoint_hashes": dict(self._checkpoint_hashes),
                "state_path": str(state_path),
                "state_sha256": state_sha256,
                "field_step": int(state.step[0].item()),
                "updated_at": float(time.time()),
                "last_prompt_sha256": prompt_sha256,
                "last_generated_token_ids": list(generated_ids),
                "last_generated_pieces": list(generated_pieces),
            }
            store.save(session_id, metadata_value)
            output = "".join(generated_pieces)
            response = {
                "id": request_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": self.model_id,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": output},
                        "finish_reason": "length",
                    }
                ],
                "usage": {
                    "prompt_tokens": len(prompt_ids),
                    "completion_tokens": len(generated_ids),
                    "total_tokens": len(prompt_ids) + len(generated_ids),
                },
                "cassi": {
                    "protocol": PROTOCOL,
                    "version": VERSION,
                    "mode": WORLD_MODE,
                    "session_id": session_id,
                    "request_id": request_id,
                    "checkpoint_hashes": dict(self._checkpoint_hashes),
                    "fingerprints": dict(self._fingerprints),
                    "prompt_token_ids": list(prompt_ids),
                    "prompt_pieces": list(prompt_pieces),
                    "generated_token_ids": list(generated_ids),
                    "generated_pieces": list(generated_pieces),
                    "selected_candidate_rows": selected_rows_by_step,
                    "selected_candidates": selected_candidates,
                    "field_step": int(state.step[0].item()),
                    "state_boundary": "post_observe_current_state",
                    "state_path": str(state_path),
                    "state_sha256": state_sha256,
                    "finite": True,
                },
            }
            _json_finite(response, "completion response")
            return response

    def health(self) -> dict[str, Any]:
        with self._lock:
            return {
                "ok": bool(self._started),
                "protocol": PROTOCOL,
                "version": VERSION,
                "model": self.model_id,
                "mode": WORLD_MODE,
                "checkpoint_hashes": dict(self._checkpoint_hashes),
                "finite": True,
            }

    def models(self) -> dict[str, Any]:
        with self._lock:
            return {
                "object": "list",
                "data": [
                    {
                        "id": self.model_id,
                        "object": "model",
                        "owned_by": "cassi",
                        "cassi_world_mode": WORLD_MODE,
                    }
                ],
            }


class _ProviderHandler(http.server.BaseHTTPRequestHandler):
    provider: CassiWorldProvider

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[cassi-world-provider] {format % args}", flush=True)

    def _send_json(self, status: int, value: Mapping[str, Any]) -> None:
        _json_finite(value, "HTTP response")
        raw = (json.dumps(dict(value), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_error(self, status: int, message: str, error_type: str = "cassi_provider_error") -> None:
        self._send_json(
            status,
            {
                "error": {"message": str(message), "type": error_type},
                "cassi": {"protocol": PROTOCOL, "version": VERSION, "mode": WORLD_MODE, "finite": True},
            },
        )

    def do_GET(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        try:
            if path == "/health":
                self._send_json(200, self.provider.health())
                return
            if path == "/v1/models":
                self._send_json(200, self.provider.models())
                return
            self._send_error(404, "not found", "invalid_request_error")
        except Exception as exc:
            self._send_error(500, str(exc), "cassi_provider_error")

    def do_POST(self) -> None:
        path = urllib.parse.urlsplit(self.path).path
        if path != "/v1/chat/completions":
            self._send_error(404, "not found", "invalid_request_error")
            return
        try:
            length_text = self.headers.get("Content-Length")
            if length_text is None:
                raise ProviderError("request body requires Content-Length")
            try:
                length = int(length_text)
            except ValueError as exc:
                raise ProviderError("Content-Length is invalid") from exc
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ProviderError(f"request body must be 1..{MAX_REQUEST_BYTES} bytes")
            raw = self.rfile.read(length)
            try:
                request = json.loads(raw.decode("utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise ProviderError(f"request body is not valid JSON: {exc}") from exc
            if not isinstance(request, dict):
                raise ProviderError("request JSON must be an object")
            result = self.provider.complete(request)
            self._send_json(200, result)
        except ProviderError as exc:
            self._send_error(exc.status, str(exc))
        except (WorldGenerationError, OSError, RuntimeError, ValueError, TypeError, KeyError) as exc:
            self._send_error(500, str(exc))
        except Exception as exc:  # Keep every failure a finite JSON response.
            self._send_error(500, f"unexpected provider failure: {type(exc).__name__}: {exc}")


class _ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True


def build_parser() -> argparse.ArgumentParser:
    """Build the import-safe command-line parser."""

    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world-checkpoint", required=True, type=Path)
    parser.add_argument("--decoder-checkpoint", required=True, type=Path)
    parser.add_argument("--normalization", required=True, type=Path)
    parser.add_argument("--candidate-npz", required=True, type=Path)
    parser.add_argument("--candidate-json", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--state-dir", type=Path, default=here / "_diag" / "world-provider")
    parser.add_argument("--context-size", type=int, default=None)
    parser.add_argument("--gpu-layers", type=int, default=None)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--seed", type=int, default=0)
    return parser


def serve(args: argparse.Namespace) -> int:
    """Load assets once and serve the loopback provider until interrupted."""

    config = ProviderConfig(
        world_checkpoint=args.world_checkpoint,
        decoder_checkpoint=args.decoder_checkpoint,
        normalization=args.normalization,
        candidate_npz=args.candidate_npz,
        candidate_json=args.candidate_json,
        model=args.model,
        state_dir=args.state_dir,
        host=args.host,
        port=args.port,
        context_size=args.context_size,
        gpu_layers=args.gpu_layers,
        device=args.device,
        max_tokens=args.max_tokens,
        seed=args.seed,
        dll_dir=Path(__file__).resolve().parent,
    )
    provider = CassiWorldProvider(config)
    provider.start()
    handler = type("CassiWorldProviderHandler", (_ProviderHandler,), {"provider": provider})
    server = _ThreadingHTTPServer((config.host, config.port), handler)
    print(
        json.dumps(
            {
                "provider": "ready",
                "protocol": PROTOCOL,
                "version": VERSION,
                "host": config.host,
                "port": config.port,
                "model": provider.model_id,
                "mode": WORLD_MODE,
                "checkpoint_hashes": dict(provider.checkpoint_hashes),
                "finite": True,
            },
            ensure_ascii=False,
            allow_nan=False,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        provider.close()
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(list(argv) if argv is not None else None)
        return serve(args)
    except ProviderError as exc:
        print(
            json.dumps(
                {"error": {"message": str(exc), "type": "cassi_provider_error"}, "cassi": {"protocol": PROTOCOL, "version": VERSION, "finite": True}},
                ensure_ascii=False,
                allow_nan=False,
            ),
            file=sys.stderr,
        )
        return 2
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        print(
            json.dumps(
                {"error": {"message": str(exc), "type": "cassi_provider_error"}, "cassi": {"protocol": PROTOCOL, "version": VERSION, "finite": True}},
                ensure_ascii=False,
                allow_nan=False,
            ),
            file=sys.stderr,
        )
        return 2


__all__ = [
    "CassiWorldProvider",
    "ProviderConfig",
    "ProviderError",
    "PROTOCOL",
    "VERSION",
    "WORLD_MODE",
    "build_parser",
    "main",
    "serve",
]


if __name__ == "__main__":
    raise SystemExit(main())
