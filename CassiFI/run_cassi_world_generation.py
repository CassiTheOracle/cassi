"""Causal hybrid Cassi world-model and bounded-token text generation.

The runner owns no model-loading side effects at import time.  Its executable
path loads one frozen L18 Qwen trajectory, one frozen Cassi world model, and a
feature-token decoder whose readout is restricted to the supplied candidate
rows.  Prompt observations are always incorporated with ``observe_step``
first.  A generated step is ordered as:

``imagine_step(pre_state, last_actual_action)`` -> bounded decoder selection ->
``decode_token`` -> ``observe_step(actual_observation, actual_action,
pre_state)``.

The final ``observe_step`` intentionally receives the pre-imagination state:
``imagine_step`` is a prior readout, not an additional state transition.  This
keeps the actual Qwen observation causal and prevents the selected token from
being selected using its own future observation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import torch

try:  # Package imports are useful to OMP and direct script imports both.
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
        CassiWorldModelState,
        load_world_model_checkpoint,
        load_world_model_state,
        save_world_model_state,
    )
    from .l18_generated_token_trajectory import (
        L18GeneratedTokenTrajectory,
        RuntimeConfig,
    )
except ImportError:  # pragma: no cover - direct ``python CassiFI/...`` use.
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
        CassiWorldModelState,
        load_world_model_checkpoint,
        load_world_model_state,
        save_world_model_state,
    )
    from l18_generated_token_trajectory import (  # type: ignore[no-redef]
        L18GeneratedTokenTrajectory,
        RuntimeConfig,
    )


GENERATION_SCHEMA = "cassi.world-generation.receipt.v1"
STATE_BOUNDARY = "post_observe_current_state"


class WorldGenerationError(RuntimeError):
    """Raised when a generation contract, asset, or causal step is invalid."""


def _fail(message: str) -> None:
    raise WorldGenerationError(message)


def _finite_float(value: Any, label: str) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise WorldGenerationError(f"{label} is not numeric") from exc
    if not math.isfinite(converted):
        _fail(f"{label} is non-finite")
    return converted


def _finite_array(value: Any, label: str, shape: tuple[int, ...] | None = None) -> np.ndarray:
    try:
        array = np.asarray(value, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise WorldGenerationError(f"{label} is not float32-compatible") from exc
    if shape is not None and array.shape != shape:
        _fail(f"{label} must have shape {shape}, got {array.shape}")
    if not np.isfinite(array).all():
        _fail(f"{label} is non-finite")
    return np.ascontiguousarray(array, dtype=np.float32)


def _norm(value: Any, label: str) -> float:
    array = _finite_array(value, label)
    result = float(np.linalg.norm(array.astype(np.float64, copy=False).reshape(-1)))
    return _finite_float(result, f"{label} norm")


def _json_finite(value: Any, label: str = "JSON value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail(f"{label} contains a non-finite number")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _fail(f"{label} contains a non-string key")
            _json_finite(item, f"{label}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _json_finite(item, f"{label}[{index}]")
        return
    _fail(f"{label} contains unsupported value {type(value).__name__}")


def _path_sha256(path: Path) -> str:
    try:
        return sha256_file(path)
    except Exception as exc:
        raise WorldGenerationError(f"could not hash {path}: {exc}") from exc


def _parameter_dtype(model: torch.nn.Module) -> torch.dtype:
    try:
        return next(model.parameters()).dtype
    except StopIteration as exc:
        raise WorldGenerationError("model has no parameters") from exc


def _parameter_device(model: torch.nn.Module) -> torch.device:
    try:
        return next(model.parameters()).device
    except StopIteration as exc:
        raise WorldGenerationError("model has no parameters") from exc


def _freeze_eval(model: torch.nn.Module) -> None:
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)


def _decoder_metadata_compatible(
    metadata: Mapping[str, Any],
    *,
    world_checkpoint_sha256: str,
    normalization_sha256: str,
    candidate_npz_sha256: str,
    candidate_json_sha256: str,
    candidate_token_ids_sha256: str,
    candidate_rows_sha256: str,
    world: CassiWorldModel,
    assets: CandidateAssets,
) -> None:
    """Validate every decoder fingerprint that the checkpoint supplies.

    Older decoder checkpoints may omit some fields, so absence is tolerated;
    supplied fields are never silently ignored.
    """

    fingerprints = metadata.get("fingerprints")
    if fingerprints is not None and not isinstance(fingerprints, Mapping):
        _fail("decoder metadata fingerprints must be an object")
    expected_fingerprints = {
        "world_checkpoint_sha256": world_checkpoint_sha256,
        "normalization_sha256": normalization_sha256,
        "candidate_npz_sha256": candidate_npz_sha256,
        "candidate_json_sha256": candidate_json_sha256,
        "candidate_token_ids_sha256": candidate_token_ids_sha256,
        "candidate_rows_sha256": candidate_rows_sha256,
    }
    for name, expected in expected_fingerprints.items():
        if isinstance(fingerprints, Mapping) and name in fingerprints:
            if fingerprints[name] != expected:
                _fail(f"decoder metadata {name} does not match supplied assets")

    direct_fingerprints = {
        "world_config_fingerprint": world.config_fingerprint,
    }
    for name, expected in direct_fingerprints.items():
        if name in metadata and metadata[name] != expected:
            _fail(f"decoder metadata {name} does not match the world checkpoint")

    dimensions = {
        "world_observation_dim": int(world.config.observation_dim),
        "world_action_dim": int(world.config.action_dim),
        "candidate_count": int(assets.token_ids.size),
        "candidate_feature_dim": int(assets.rows.shape[1]),
    }
    for name, expected in dimensions.items():
        if name in metadata:
            try:
                actual = int(metadata[name])
            except (TypeError, ValueError) as exc:
                raise WorldGenerationError(f"decoder metadata {name} is invalid") from exc
            if actual != expected:
                _fail(f"decoder metadata {name} does not match supplied assets")


def _validate_dimensions(
    world: CassiWorldModel,
    decoder: CassiFeatureTokenDecoder,
    normalizer: Normalization,
    assets: CandidateAssets,
) -> None:
    observation_dim = int(world.config.observation_dim)
    action_dim = int(world.config.action_dim)
    if normalizer.observation_mean.size != observation_dim:
        _fail("normalization observation dimension does not match world model")
    if normalizer.action_mean.size != action_dim:
        _fail("normalization action dimension does not match world model")
    if assets.rows.shape[1] != observation_dim:
        _fail("candidate row dimension does not match world observation dimension")
    if decoder.config.feature_dim != observation_dim:
        _fail("decoder feature dimension does not match world observation dimension")
    if assets.token_ids.size < 1:
        _fail("candidate assets contain no token IDs")


def _token_piece(runtime: L18GeneratedTokenTrajectory, token_id: int) -> str:
    try:
        piece = runtime.token_piece(token_id)
    except Exception as exc:
        raise WorldGenerationError(f"could not obtain token piece for {token_id}: {exc}") from exc
    if not isinstance(piece, str):
        _fail(f"token piece for {token_id} is invalid")
    return piece


def _capture_record(
    runtime: L18GeneratedTokenTrajectory,
    record: Any,
    token_id: int,
    position: int,
    label: str,
) -> tuple[str, np.ndarray, np.ndarray]:
    if record.final_token_id != token_id:
        _fail(f"{label} token mismatch: runtime returned {record.final_token_id}, expected {token_id}")
    if int(record.final_position) != int(position):
        _fail(f"{label} position mismatch: runtime returned {record.final_position}, expected {position}")
    trunk = getattr(record, "trunk", None)
    if not isinstance(trunk, tuple) or len(trunk) != 64:
        _fail(f"{label} did not return all 64 trunk captures")
    layer_zero = trunk[0]
    if int(layer_zero.layer_index) != 0 or layer_zero.role != "field_trunk":
        _fail(f"{label} layer-0 capture has the wrong role")
    action_raw = _finite_array(layer_zero.values, f"{label} layer-0 action", (runtime.hidden_dimension,))
    observation_raw = _finite_array(
        record.head_output_vector,
        f"{label} head output",
        (runtime.hidden_dimension,),
    )
    piece = _token_piece(runtime, token_id)
    return piece, action_raw, observation_raw


def _decode_prompt_token(
    runtime: L18GeneratedTokenTrajectory,
    token_id: int,
    position: int,
) -> tuple[Any, str, np.ndarray, np.ndarray]:
    if position == 0:
        record = runtime.decode_initial((token_id,), positions=(0,))
    else:
        record = runtime.decode_token(token_id, position)
    piece, action_raw, observation_raw = _capture_record(
        runtime, record, token_id, position, f"prompt token {position}"
    )
    return record, piece, action_raw, observation_raw


def _decode_generated_token(
    runtime: L18GeneratedTokenTrajectory,
    token_id: int,
    position: int,
) -> tuple[Any, str, np.ndarray, np.ndarray]:
    record = runtime.decode_token(token_id, position)
    piece, action_raw, observation_raw = _capture_record(
        runtime, record, token_id, position, f"generated token {position}"
    )
    return record, piece, action_raw, observation_raw


def _standardized_tensors(
    normalizer: Normalization,
    action_raw: np.ndarray,
    observation_raw: np.ndarray,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[torch.Tensor, torch.Tensor, np.ndarray, np.ndarray]:
    action_standardized = _finite_array(
        normalizer.action_standardized(action_raw), "standardized action", action_raw.shape
    )
    observation_standardized = _finite_array(
        normalizer.observation_standardized(observation_raw),
        "standardized observation",
        observation_raw.shape,
    )
    action = torch.as_tensor(action_standardized, device=device, dtype=dtype).reshape(1, -1)
    observation = torch.as_tensor(observation_standardized, device=device, dtype=dtype).reshape(1, -1)
    if not bool(torch.isfinite(action).all().item()) or not bool(torch.isfinite(observation).all().item()):
        _fail("standardized Qwen action or observation is non-finite")
    return action, observation, action_standardized, observation_standardized


def _rank_candidate_rows(
    scores: torch.Tensor,
    assets: CandidateAssets,
    count: int,
) -> tuple[list[dict[str, Any]], torch.Tensor]:
    if scores.shape != (1, int(assets.token_ids.size)):
        _fail("decoder logits have the wrong bounded-candidate shape")
    values = scores[0].detach().to(device="cpu", dtype=torch.float64)
    if not bool(torch.isfinite(values).all().item()):
        _fail("decoder candidate logits are non-finite")
    rows = [
        {
            "token_id": int(token_id),
            "piece": str(assets.pieces[index]),
            "logit": _finite_float(values[index].item(), "decoder candidate logit"),
        }
        for index, token_id in enumerate(assets.token_ids.tolist())
    ]
    rows.sort(key=lambda row: (-float(row["logit"]), int(row["token_id"])))
    selected_rows = rows[:count]
    if not selected_rows:
        _fail("decoder returned no candidate rows")
    selected_indices = torch.tensor(
        [int(np.searchsorted(assets.token_ids, int(row["token_id"]))) for row in selected_rows],
        device=scores.device,
        dtype=torch.int64,
    )
    return selected_rows, selected_indices


def _select_candidate(
    scores: torch.Tensor,
    assets: CandidateAssets,
    *,
    top_k: int,
    temperature: float,
    seed: int,
    token_index: int,
) -> tuple[list[dict[str, Any]], int, float]:
    count = min(int(top_k), int(assets.token_ids.size))
    rows, indices = _rank_candidate_rows(scores, assets, count)
    if temperature == 0.0:
        selected = rows[0]
        return rows, int(selected["token_id"]), float(selected["logit"])

    selected_logits = scores[0].index_select(0, indices)
    scaled = selected_logits / float(temperature)
    if not bool(torch.isfinite(scaled).all().item()):
        _fail("temperature-scaled candidate logits are non-finite")
    probabilities = torch.softmax(scaled, dim=0)
    if not bool(torch.isfinite(probabilities).all().item()) or float(probabilities.sum().item()) <= 0.0:
        _fail("candidate sampling probabilities are non-finite or empty")
    try:
        generator = torch.Generator(device=scores.device)
        generator.manual_seed((int(seed) + int(token_index)) % ((1 << 63) - 1))
        sampled_index = int(torch.multinomial(probabilities, 1, generator=generator).item())
    except Exception as exc:
        raise WorldGenerationError(f"seeded candidate sampling failed: {exc}") from exc
    selected = rows[sampled_index]
    return rows, int(selected["token_id"]), float(selected["logit"])


def _common_receipt(
    *,
    prompt: str,
    prompt_ids: Sequence[int],
    checkpoint_hashes: Mapping[str, str],
    fingerprints: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "schema": GENERATION_SCHEMA,
        "prompt": prompt,
        "prompt_token_ids": [int(token_id) for token_id in prompt_ids],
        "checkpoint_hashes": dict(checkpoint_hashes),
        "fingerprints": dict(fingerprints),
        "state_boundary": {
            "name": STATE_BOUNDARY,
            "semantics": "state is the latest actual post-observe_step state",
            "resume_runtime": "replay prompt and prior selected tokens from this JSONL",
        },
    }


def _read_existing_receipt(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not path.is_file():
        _fail(f"resume output receipt does not exist: {path}")
    header: dict[str, Any] | None = None
    generated: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise WorldGenerationError(f"resume receipt line {line_number} is invalid JSON") from exc
                if not isinstance(value, dict):
                    _fail(f"resume receipt line {line_number} is not an object")
                event = value.get("event")
                if event == "header":
                    if header is not None:
                        _fail("resume receipt contains multiple headers")
                    header = value
                elif event == "generated":
                    generated.append(value)
    except OSError as exc:
        raise WorldGenerationError(f"could not read resume receipt {path}: {exc}") from exc
    if header is None:
        _fail("resume receipt lacks a header")
    for index, row in enumerate(generated):
        if row.get("token_index") != index:
            _fail("resume generated receipt token indices are not contiguous")
        selected = row.get("selected_token_id")
        if isinstance(selected, bool) or not isinstance(selected, int) or selected < 0:
            _fail("resume generated receipt has an invalid selected token")
    return header, generated


class _ReceiptWriter:
    def __init__(self, path: Path, *, append: bool) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = path.open("a" if append else "w", encoding="utf-8")
        except OSError as exc:
            raise WorldGenerationError(f"could not open receipt {path}: {exc}") from exc
        self.path = path

    def write(self, value: Mapping[str, Any]) -> None:
        payload = dict(value)
        _json_finite(payload, "receipt")
        try:
            self._handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
            self._handle.flush()
        except (OSError, TypeError, ValueError) as exc:
            raise WorldGenerationError(f"could not write receipt {self.path}: {exc}") from exc

    def close(self) -> None:
        try:
            self._handle.close()
        except OSError as exc:
            raise WorldGenerationError(f"could not close receipt {self.path}: {exc}") from exc

    def __enter__(self) -> "_ReceiptWriter":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()


def _build_runtime_config(args: argparse.Namespace) -> RuntimeConfig:
    values: dict[str, Any] = {}
    if args.model is not None:
        values["model_path"] = Path(args.model)
    if args.dll_dir is not None:
        values["dll_dir"] = Path(args.dll_dir)
    if args.context_size is not None:
        values["context_size"] = int(args.context_size)
    if args.gpu_layers is not None:
        values["gpu_layers"] = int(args.gpu_layers)
    try:
        return RuntimeConfig(**values)
    except Exception as exc:
        raise WorldGenerationError(f"invalid L18 runtime configuration: {exc}") from exc


def _validate_args(args: argparse.Namespace) -> None:
    if args.max_new_tokens < 0:
        _fail("max-new-tokens must be non-negative")
    if args.top_k < 1:
        _fail("top-k must be positive")
    if not math.isfinite(float(args.temperature)) or args.temperature < 0.0:
        _fail("temperature must be finite and non-negative")
    if args.seed < 0:
        _fail("seed must be non-negative")
    try:
        torch.device(args.device)
    except (RuntimeError, TypeError) as exc:
        raise WorldGenerationError(f"invalid torch device {args.device!r}") from exc


def generate(args: argparse.Namespace) -> dict[str, Any]:
    """Run one causal generation and return the structured final summary."""

    device = torch.device(args.device)
    if device.type == "cuda" and device.index is None:
        device = torch.device("cuda:0")
    world_path = Path(args.world_checkpoint)
    decoder_path = Path(args.decoder_checkpoint)
    normalization_path = Path(args.normalization)
    candidate_npz_path = Path(args.candidate_npz)
    candidate_json_path = Path(args.candidate_json)
    output_path = Path(args.output)

    world_hash = _path_sha256(world_path)
    decoder_hash = _path_sha256(decoder_path)
    normalization_hash = _path_sha256(normalization_path)
    candidate_npz_hash = _path_sha256(candidate_npz_path)
    candidate_json_hash = _path_sha256(candidate_json_path)

    try:
        world_receipt = load_world_model_checkpoint(world_path, device=device)
        world = world_receipt.model
        decoder_receipt = load_feature_token_decoder_checkpoint(decoder_path, device=device)
        decoder = decoder_receipt.model
        normalizer = Normalization.load(normalization_path)
        assets = load_candidate_assets(
            candidate_npz_path,
            candidate_json_path,
            expected_feature_dim=int(world.config.observation_dim),
        )
    except Exception as exc:
        raise WorldGenerationError(f"asset loading failed: {exc}") from exc

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

    checkpoint_hashes = {
        "world_checkpoint_sha256": world_hash,
        "decoder_checkpoint_sha256": decoder_hash,
        "normalization_sha256": normalization_hash,
        "candidate_npz_sha256": candidate_npz_hash,
        "candidate_json_sha256": candidate_json_hash,
    }
    fingerprints = {
        "world_config_fingerprint": world.config_fingerprint,
        "decoder_config_fingerprint": decoder.config_fingerprint,
        "candidate_token_ids_sha256": candidate_ids_hash,
        "candidate_rows_sha256": candidate_rows_hash,
    }
    common = _common_receipt(
        prompt=str(args.prompt),
        prompt_ids=(),
        checkpoint_hashes=checkpoint_hashes,
        fingerprints=fingerprints,
    )

    runtime_config = _build_runtime_config(args)
    prior_header: dict[str, Any] | None = None
    prior_generated: list[dict[str, Any]] = []
    if args.resume_state is not None:
        prior_header, prior_generated = _read_existing_receipt(output_path)
        if prior_header.get("schema") != GENERATION_SCHEMA:
            _fail("resume receipt schema mismatch")
        for field in ("prompt", "checkpoint_hashes", "fingerprints"):
            if prior_header.get(field) != common.get(field) and field != "prompt":
                _fail(f"resume receipt {field} does not match supplied assets")
        if prior_header.get("prompt") != str(args.prompt):
            _fail("resume receipt prompt does not match supplied prompt")

    state: CassiWorldModelState | None = None
    runtime: L18GeneratedTokenTrajectory | None = None
    writer: _ReceiptWriter | None = None
    prompt_ids: tuple[int, ...] = ()
    generated_pieces: list[str] = []
    last_action: torch.Tensor | None = None
    last_action_source: int | None = None
    try:
        runtime = L18GeneratedTokenTrajectory(runtime_config)
        prompt_ids = tuple(int(token_id) for token_id in runtime.tokenize(str(args.prompt)))
        if not prompt_ids:
            _fail("prompt tokenization produced no tokens")
        for token_id in prompt_ids:
            if token_id < 0 or token_id >= runtime.vocabulary_size:
                _fail(f"prompt token {token_id} is outside the runtime vocabulary")
            if runtime.token_is_eog(token_id):
                _fail(f"prompt contains EOS/EOG token {token_id}")
        if runtime.hidden_dimension != int(world.config.observation_dim) or runtime.hidden_dimension != int(
            world.config.action_dim
        ):
            _fail("L18 hidden width does not match world observation/action dimensions")
        for candidate_index, candidate_id_value in enumerate(assets.token_ids.tolist()):
            candidate_id = int(candidate_id_value)
            if candidate_id < 0 or candidate_id >= runtime.vocabulary_size:
                _fail(f"candidate token {candidate_id} is outside the runtime vocabulary")
            runtime_piece = _token_piece(runtime, candidate_id)
            if runtime_piece != assets.pieces[candidate_index]:
                _fail(f"candidate piece mismatch for token {candidate_id}")


        common = _common_receipt(
            prompt=str(args.prompt),
            prompt_ids=prompt_ids,
            checkpoint_hashes=checkpoint_hashes,
            fingerprints=fingerprints,
        )
        if prior_header is not None:
            if prior_header.get("prompt_token_ids") != list(prompt_ids):
                _fail("resume receipt tokenization does not match current runtime")

        model_dtype = _parameter_dtype(world)
        model_device = _parameter_device(world)
        if model_device != device:
            _fail("world model device differs from requested device")
        if model_dtype not in (torch.float32, torch.float64, torch.float16, torch.bfloat16):
            _fail("world model uses an unsupported non-floating dtype")
        valid = torch.ones((1,), dtype=torch.bool, device=device)
        reset = torch.zeros((1,), dtype=torch.bool, device=device)

        if args.resume_state is not None:
            state = load_world_model_state(args.resume_state, world, device=device)
            if state.batch_size != 1:
                _fail("resume runtime state must have batch size one")
        else:
            state = world.initial_state(1, device=device, dtype=model_dtype)

        candidate_rows = torch.as_tensor(assets.rows, device=_parameter_device(decoder), dtype=_parameter_dtype(decoder))
        if candidate_rows.device != device:
            _fail("decoder candidate rows are not on requested device")

        append_receipt = args.resume_state is not None
        writer = _ReceiptWriter(output_path, append=append_receipt)
        if not append_receipt:
            header = dict(common)
            header.update(
                {
                    "event": "header",
                    "temperature": float(args.temperature),
                    "top_k": int(args.top_k),
                    "seed": int(args.seed),
                    "max_new_tokens": int(args.max_new_tokens),
                    "runtime": {
                        "model_path": str(runtime_config.model_path),
                        "dll_dir": str(runtime_config.dll_dir),
                        "context_size": int(runtime_config.context_size),
                        "gpu_layers": int(runtime_config.gpu_layers),
                    },
                }
            )
            writer.write(header)

        # Rebuild the Qwen context chronologically even when a world state is
        # resumed.  On a fresh state, each prompt record is also observed.
        for position, token_id in enumerate(prompt_ids):
            _, piece, action_raw, observation_raw = _decode_prompt_token(runtime, token_id, position)
            action, observation, action_std, observation_std = _standardized_tensors(
                normalizer,
                action_raw,
                observation_raw,
                device=device,
                dtype=model_dtype,
            )
            if args.resume_state is None:
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
            last_action = action
            last_action_source = position
            if args.resume_state is None:
                prompt_event = dict(common)
                prompt_event.update(
                    {
                        "event": "prompt",
                        "token_index": position,
                        "input_token_id": int(token_id),
                        "input_piece": piece,
                        "actual_qwen": {
                            "action_norm": _norm(action_raw, "prompt action"),
                            "observation_norm": _norm(observation_raw, "prompt observation"),
                            "action_standardized_norm": _norm(action_std, "prompt standardized action"),
                            "observation_standardized_norm": _norm(
                                observation_std, "prompt standardized observation"
                            ),
                        },
                        "field_step": int(state.step[0].item()),
                        "finite": True,
                    }
                )
                writer.write(prompt_event)

        if args.resume_state is not None:
            expected_step = len(prompt_ids) + len(prior_generated)
            loaded_step = int(state.step[0].item())
            if loaded_step != expected_step:
                _fail(
                    f"resume state step {loaded_step} does not match prompt plus receipt history {expected_step}"
                )
            # Replay previously selected tokens only to reconstruct the native
            # L18 context and the last actual action.  The loaded world state is
            # already the post-observe state for that history.
            for generated_index, previous in enumerate(prior_generated):
                selected_id = int(previous["selected_token_id"])
                if selected_id >= runtime.vocabulary_size or runtime.token_is_eog(selected_id):
                    _fail("resume receipt contains an invalid or EOS selected token")
                _, selected_piece, action_raw, _ = _decode_generated_token(
                    runtime, selected_id, len(prompt_ids) + generated_index
                )
                recorded_piece = previous.get("selected_piece")
                if recorded_piece != selected_piece:
                    _fail("resume selected token piece does not match the pinned runtime")
                action_standardized = normalizer.action_standardized(action_raw)
                last_action = torch.as_tensor(
                    _finite_array(action_standardized, "resumed standardized action"),
                    device=device,
                    dtype=model_dtype,
                ).reshape(1, -1)
                last_action_source = len(prompt_ids) + generated_index
                generated_pieces.append(selected_piece)

        if last_action is None or last_action_source is None:
            _fail("no actual action is available for generated-step imagination")
        if state is None:
            _fail("world state was not initialized")

        decoder_features_dtype = _parameter_dtype(decoder)
        for generated_index in range(len(prior_generated), len(prior_generated) + int(args.max_new_tokens)):
            pre_state = state
            imagine_action = last_action
            imagine_action_source = last_action_source
            if imagine_action is None or imagine_action_source is None:
                _fail("generated-step imagination lost its actual action source")
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
            decoder_input = torch.as_tensor(
                predicted_raw,
                device=device,
                dtype=decoder_features_dtype,
            ).reshape(1, -1)
            if not bool(torch.isfinite(decoder_input).all().item()):
                _fail("decoder feature input is non-finite")
            with torch.no_grad():
                scores = decoder.logits(decoder_input, candidate_rows)
            top_rows, selected_id, selected_logit = _select_candidate(
                scores,
                assets,
                top_k=int(args.top_k),
                temperature=float(args.temperature),
                seed=int(args.seed),
                token_index=generated_index,
            )
            if selected_id < 0 or selected_id >= runtime.vocabulary_size:
                _fail(f"decoder selected invalid runtime token {selected_id}")
            if runtime.token_is_eog(selected_id):
                _fail(f"decoder selected EOS/EOG token {selected_id}; refusing unsafe termination")
            selected_piece = _token_piece(runtime, selected_id)
            asset_index = int(np.searchsorted(assets.token_ids, selected_id))
            if asset_index >= assets.token_ids.size or int(assets.token_ids[asset_index]) != selected_id:
                _fail("selected token is absent from candidate assets")
            if assets.pieces[asset_index] != selected_piece:
                _fail("candidate asset piece disagrees with the pinned runtime piece")

            _, actual_piece, actual_action_raw, actual_observation_raw = _decode_generated_token(
                runtime,
                selected_id,
                len(prompt_ids) + generated_index,
            )
            if actual_piece != selected_piece:
                _fail("decoded selected token piece changed inside the pinned runtime")
            actual_action, actual_observation, actual_action_std, actual_observation_std = _standardized_tensors(
                normalizer,
                actual_action_raw,
                actual_observation_raw,
                device=device,
                dtype=model_dtype,
            )
            # The actual observation is incorporated only after selection.  It
            # uses pre_state so the prior readout does not double-advance state.
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
            last_action = actual_action
            last_action_source = len(prompt_ids) + generated_index
            generated_pieces.append(selected_piece)

            event = dict(common)
            event.update(
                {
                    "event": "generated",
                    "token_index": generated_index,
                    "input_token_id": int(selected_id),
                    "input_piece": selected_piece,
                    "action_contract": {
                        "kind": "last_actual_action",
                        "source_token_index": int(imagine_action_source),
                        "imagine_action_standardized_norm": _norm(
                            imagine_action.detach().cpu().numpy(), "imagine action"
                        ),
                    },
                    "predicted_feature": {
                        "finite": True,
                        "standardized_norm": _norm(predicted_standardized, "predicted standardized feature"),
                        "raw_norm": _norm(predicted_raw, "predicted raw feature"),
                    },
                    "decoder_top_k": top_rows,
                    "selected_token_id": int(selected_id),
                    "selected_piece": selected_piece,
                    "selected_logit": _finite_float(selected_logit, "selected logit"),
                    "actual_qwen": {
                        "action_norm": _norm(actual_action_raw, "actual action"),
                        "observation_norm": _norm(actual_observation_raw, "actual observation"),
                        "action_standardized_norm": _norm(actual_action_std, "actual standardized action"),
                        "observation_standardized_norm": _norm(
                            actual_observation_std, "actual standardized observation"
                        ),
                    },
                    "field_step": int(state.step[0].item()),
                    "finite": True,
                }
            )
            writer.write(event)

        state_hash: str | None = None
        if args.save_state is not None:
            try:
                state_hash = save_world_model_state(args.save_state, world, state)
            except Exception as exc:
                raise WorldGenerationError(f"could not save world runtime state: {exc}") from exc
            saved_event = dict(common)
            saved_event.update(
                {
                    "event": "state_saved",
                    "state_path": str(args.save_state),
                    "state_sha256": state_hash,
                    "field_step": int(state.step[0].item()),
                    "finite": True,
                }
            )
            writer.write(saved_event)

        generated_text = "".join(generated_pieces)
        summary = {
            "schema": GENERATION_SCHEMA,
            "generated_text": generated_text,
            "prompt": str(args.prompt),
            "receipt_path": str(output_path),
            "generated_token_count": len(generated_pieces),
            "field_step": int(state.step[0].item()),
            "checkpoint_hashes": checkpoint_hashes,
            "fingerprints": fingerprints,
            "state_boundary": STATE_BOUNDARY,
        }
        if args.save_state is not None:
            summary["state_path"] = str(args.save_state)
            summary["state_sha256"] = state_hash
        complete_event = dict(common)
        complete_event.update(
            {
                "event": "complete",
                "generated_text": generated_text,
                "generated_token_count": len(generated_pieces),
                "field_step": int(state.step[0].item()),
                "finite": True,
            }
        )
        writer.write(complete_event)
        return summary
    except WorldGenerationError:
        raise
    except Exception as exc:
        raise WorldGenerationError(f"world generation failed: {type(exc).__name__}: {exc}") from exc
    finally:
        if writer is not None:
            writer.close()
        if runtime is not None:
            runtime.close(suppress=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world-checkpoint", required=True, type=Path)
    parser.add_argument("--decoder-checkpoint", required=True, type=Path)
    parser.add_argument("--normalization", required=True, type=Path)
    parser.add_argument("--candidate-npz", required=True, type=Path)
    parser.add_argument("--candidate-json", required=True, type=Path)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max-new-tokens", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", "--model-path", dest="model", type=Path, default=None)
    parser.add_argument("--dll-dir", type=Path, default=None)
    parser.add_argument("--context-size", type=int, default=None)
    parser.add_argument("--gpu-layers", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--resume-state", type=Path, default=None)
    parser.add_argument("--save-state", type=Path, default=None)
    parser.add_argument("--device", default="cpu")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(list(argv) if argv is not None else None)
        summary = generate(args)
    except (WorldGenerationError, OSError, ValueError) as exc:
        print(json.dumps({"schema": GENERATION_SCHEMA, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


__all__ = [
    "GENERATION_SCHEMA",
    "STATE_BOUNDARY",
    "WorldGenerationError",
    "build_parser",
    "generate",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
