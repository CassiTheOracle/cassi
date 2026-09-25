"""Chronological, owner-held supervised training for resident Qwen n-gram readout.

Each training example is measured at the run's starting readout revision, then
contributes one idempotent owner operation. Post-update logits are projections
from frozen native head captures; heldout rows are finally re-run through the
resident model at the learned revision and reported as actual logits.
"""
from __future__ import annotations

import base64
import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent / "CassiFI"
if PROJECT_ROOT.is_dir() and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cassi_field_owner import FieldIntelligenceOwner
from cassi_programmable_swarm import ProgrammableSwarm
from programs.model.ngram_learning import MAX_COEFFICIENTS, validate_state
from programs.model.ngram_table import Qwen4NgramTable
from programs.model.ngram_training import margin_with_readout, make_next_token_feedback
from cassi_resident_qwen_client import ResidentQwenClient


RUN_SCHEMA = "cassifi.resident-qwen-ngram-training-run.v1"
MAX_DATASET_BYTES = 64 * 1024 * 1024
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_SAMPLES = 512
MAX_PREFIX_CHARS = 1_000_000
MAX_CONTEXT_TOKENS = 32_768
MAX_GROUPS_PER_BOUNDARY = 100_000


class TrainingError(RuntimeError):
    """A source, provenance, or owner-state check prevented safe training."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_bytes(value) + b"\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TrainingError("observations contain duplicate JSON object keys")
        result[key] = value
    return result


def _read_observations(path: Path, *, verify_source_hash: bool = True) -> tuple[list[dict[str, Any]], str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise TrainingError(f"cannot read observations file: {exc}") from exc
    if len(raw) > MAX_DATASET_BYTES:
        raise TrainingError("observations file exceeds the 64 MiB bound")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError, TrainingError) as exc:
        raise TrainingError(f"observations are not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_SAMPLES:
        raise TrainingError(f"observations must be an array of 1 to {MAX_SAMPLES} rows")
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    heldout_started = False
    train_count = 0
    source_mode: bool | None = None
    source_cache: dict[str, tuple[bytes, str]] = {}
    source_splits: dict[str, str] = {}
    for index, item in enumerate(value):
        keys = set(item) if isinstance(item, Mapping) else set()
        has_source = "source" in keys
        if keys != {"id", "prefix", "next_token", "split"} | ({"source"} if has_source else set()):
            raise TrainingError(f"observation row {index} must have exactly id, prefix, next_token, split, and optional source")
        if source_mode is not None and has_source != source_mode:
            raise TrainingError("observations cannot mix source-backed and unsourced rows")
        source_mode = has_source
        sample_id = item["id"]
        prefix = item["prefix"]
        next_token = item["next_token"]
        split = item["split"]
        if (
            not isinstance(sample_id, str)
            or not sample_id
            or len(sample_id.encode("utf-8")) > 128
            or "\x00" in sample_id
            or any(ord(character) < 32 for character in sample_id)
        ):
            raise TrainingError(f"observation row {index} has an invalid bounded id")
        if sample_id in seen_ids:
            raise TrainingError("observation ids must be unique")
        seen_ids.add(sample_id)
        if not isinstance(prefix, str) or not prefix or len(prefix) > MAX_PREFIX_CHARS:
            raise TrainingError(f"observation row {index} has an empty or oversized prefix")
        if not isinstance(next_token, str) or not next_token:
            raise TrainingError(f"observation row {index} has an empty next_token")
        if split not in {"train", "heldout"}:
            raise TrainingError(f"observation row {index} split must be train or heldout")
        if split == "heldout":
            heldout_started = True
        else:
            if heldout_started:
                raise TrainingError("all chronological train rows must precede reserved heldout rows")
            train_count += 1
        source: dict[str, Any] | None = None
        if has_source:
            provenance = item["source"]
            if not isinstance(provenance, Mapping) or set(provenance) != {"path", "sha256", "offset_bytes"}:
                raise TrainingError(f"observation row {index} source must have exactly path, sha256, offset_bytes")
            source_path = provenance["path"]
            if not isinstance(source_path, str) or not source_path or "\x00" in source_path:
                raise TrainingError(f"observation row {index} source path is invalid")
            candidate = Path(source_path)
            if not candidate.is_absolute():
                raise TrainingError(f"observation row {index} source path must be resolved and absolute")
            try:
                resolved = candidate.resolve(strict=True)
                if str(resolved) != source_path or not resolved.is_file():
                    raise TrainingError(f"observation row {index} source path must be a resolved absolute file")
            except (OSError, RuntimeError, ValueError, UnicodeError) as exc:
                raise TrainingError(f"observation row {index} source file cannot be resolved: {exc}") from exc
            source_sha256 = _valid_sha256(provenance["sha256"], f"observation row {index} source SHA-256")
            offset_bytes = provenance["offset_bytes"]
            if type(offset_bytes) is not int or offset_bytes < 0:
                raise TrainingError(f"observation row {index} source offset_bytes must be nonnegative integer")
            cached = source_cache.get(source_path)
            if cached is None:
                try:
                    with resolved.open("rb") as stream:
                        source_bytes = stream.read(MAX_SOURCE_BYTES + 1)
                except OSError as exc:
                    raise TrainingError(f"observation row {index} source file cannot be read: {exc}") from exc
                if len(source_bytes) > MAX_SOURCE_BYTES:
                    raise TrainingError(f"observation row {index} source file exceeds the 64 MiB bound")
                try:
                    source_bytes.decode("utf-8", errors="strict")
                except UnicodeError as exc:
                    raise TrainingError(f"observation row {index} source file is not strict UTF-8: {exc}") from exc
                cached = (source_bytes, _sha256_bytes(source_bytes))
                source_cache[source_path] = cached
            source_bytes, actual_sha256 = cached
            if verify_source_hash and source_sha256 != actual_sha256:
                raise TrainingError(f"observation row {index} source SHA-256 does not match its file")
            try:
                passage = (prefix + next_token).encode("utf-8", errors="strict")
            except UnicodeError as exc:
                raise TrainingError(f"observation row {index} passage is not valid UTF-8: {exc}") from exc
            if source_bytes[offset_bytes:offset_bytes + len(passage)] != passage:
                raise TrainingError(f"observation row {index} source passage does not match exact UTF-8 bytes at offset")
            earlier_split = source_splits.setdefault(source_path, split)
            if earlier_split != split:
                raise TrainingError(f"source file {source_path} cannot occur in both train and heldout")
            source = {"path": source_path, "sha256": source_sha256, "offset_bytes": offset_bytes}
        row = {
            "dataset_index": index,
            "id": sample_id,
            "prefix": prefix,
            "next_token": next_token,
            "split": split,
        }
        if source is not None:
            row["source"] = source
        rows.append(row)
    heldout_count = len(rows) - train_count
    if train_count < 1 or heldout_count < 1:
        raise TrainingError("observations require at least one train row followed by one heldout row")
    if train_count < 2 or heldout_count < 2:
        raise TrainingError("train and heldout splits each need two rows for table-swapped controls")
    return rows, _sha256_bytes(raw)


def _u32_sha256(tokens: Sequence[int]) -> str:
    array = np.asarray(tokens, dtype="<u4")
    return _sha256_bytes(array.tobytes(order="C"))


def _finite_array(value: Any, *, ndim: int, label: str) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim != ndim or array.dtype.kind not in "fiu" or not np.isfinite(array).all():
        raise TrainingError(f"{label} is not a finite numeric array with {ndim} dimensions")
    return np.ascontiguousarray(array, dtype=np.float32)


def _valid_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise TrainingError(f"{label} is not a lowercase SHA-256 identity")
    return value


def _snapshot_array_ref(store: Any, descriptor: Mapping[str, Any], name: str) -> dict[str, Any]:
    manifest, _ = store._read_manifest(descriptor)
    arrays = manifest.get("arrays") if isinstance(manifest, Mapping) else None
    record = arrays.get(name) if isinstance(arrays, Mapping) else None
    if not isinstance(record, Mapping):
        raise TrainingError(f"snapshot has no content-addressed {name} array")
    return {
        "snapshot_sha256": descriptor.get("snapshot_sha256"),
        "array": name,
        "sha256": record.get("sha256"),
        "dtype": record.get("dtype"),
        "shape": record.get("shape"),
        "nbytes": record.get("nbytes"),
    }


def _dataset_identity(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    identity = {
        "schema": "cassi.resident-qwen-next-token-observations.v1",
        "ordered_ids": [str(row["id"]) for row in rows],
        "splits": [str(row["split"]) for row in rows],
    }
    if rows and "source" in rows[0]:
        identity["sources"] = [row["source"] for row in rows]
    return identity


def _safe_row_lookup(table: Any, tokens: Sequence[int], *, sample_id: str) -> np.ndarray:
    result = table.lookup(tokens)
    if not isinstance(result, tuple) or len(result) != 2:
        raise TrainingError("ngram table lookup returned an unsupported record")
    vector = _finite_array(result[0], ndim=1, label=f"table vector for row {sample_id}")
    if vector.shape != (2560,):
        raise TrainingError("ngram table vector width is not 2560")
    return vector


def _same_plain_tokenizer(model: Any, table: Any) -> bool:
    """Plain text uses the token IDs and merge ranks, not chat or padding metadata."""
    return all(
        getattr(model, name, None) == getattr(table, name, None)
        for name in (
            "model", "tokens", "merges", "token_types", "_special_to_id",
            "bos_token_id", "eos_token_id", "unknown_token_id",
            "add_bos_token", "add_eos_token",
        )
    )


def _validate_dataset_tokens(
    rows: Sequence[Mapping[str, Any]], client: ResidentQwenClient, table: Any
) -> list[dict[str, Any]]:
    tokenizer = client._ensure_tokenizer()
    table_tokenizer = getattr(table, "tokenizer", None)
    if table_tokenizer is None:
        raise TrainingError("ngram table has no verified tokenizer")
    if not _same_plain_tokenizer(tokenizer, table_tokenizer):
        raise TrainingError("resident model and ngram table encode different plain-text token IDs")
    validated: list[dict[str, Any]] = []
    model_context = int(getattr(client, "_context_length", MAX_CONTEXT_TOKENS))
    if model_context <= 1:
        raise TrainingError("resident model context length is invalid")
    model_context = min(model_context, MAX_CONTEXT_TOKENS)
    for row in rows:
        prefix_ids = client.tokenize(str(row["prefix"]), add_special=False)
        extended_ids = client.tokenize(str(row["prefix"]) + str(row["next_token"]), add_special=False)
        if not prefix_ids or len(prefix_ids) > model_context - 1:
            raise TrainingError(f"row {row['id']} prefix is empty or exceeds resident model context")
        if len(extended_ids) != len(prefix_ids) + 1 or extended_ids[:-1] != prefix_ids:
            raise TrainingError(f"row {row['id']} prefix plus next_token is not exactly one token of extension")
        target_token_id = int(extended_ids[-1])
        if target_token_id < 0 or target_token_id > (1 << 31) - 1:
            raise TrainingError(f"row {row['id']} target token id is outside the feedback bound")
        if len(table_tokenizer.encode(str(row["prefix"]), add_special=False)) != len(prefix_ids):
            raise TrainingError(f"row {row['id']} table tokenizer does not preserve the prefix tokenization")
        if table_tokenizer.encode(str(row["prefix"]), add_special=False) != prefix_ids:
            raise TrainingError(f"row {row['id']} table tokenizer prefix IDs differ from the resident model")
        if table_tokenizer.encode(str(row["prefix"]) + str(row["next_token"]), add_special=False) != extended_ids:
            raise TrainingError(f"row {row['id']} table tokenizer extension IDs differ from the resident model")
        table_vector = _safe_row_lookup(table, prefix_ids, sample_id=str(row["id"]))
        validated.append({
            "dataset_index": int(row["dataset_index"]),
            "id": str(row["id"]),
            "split": str(row["split"]),
            "context_tokens": [int(token) for token in prefix_ids],
            "target_token_id": target_token_id,
            "context_tokens_sha256": _u32_sha256(prefix_ids),
            "extended_tokens_sha256": _u32_sha256(extended_ids),
            "table_vector_preflight_sha256": _sha256_bytes(table_vector.astype("<f4", copy=False).tobytes()),
        })
    return validated


def _time_task(
    *,
    swarm: ProgrammableSwarm,
    member_id: str,
    package: Any,
    model_id: str,
    client: ResidentQwenClient,
    task_id: str,
    operation_id: str,
    context_tokens: Sequence[int],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    try:
        swarm.bind_resident_model(model_id, client._ensure_executor())
        swarm.start_model(
            member_id,
            package,
            prompt_tokens=tuple(int(token) for token in context_tokens),
            max_new_tokens=1,
            placement="logical-cpu",
            sampler={"mode": "greedy", "temperature": 0.0, "top_k": 3},
            operation_id=operation_id,
            task_id=task_id,
            lineage_id=f"resident-ngram:{model_id}",
            steps=0,
        )
    except Exception as exc:
        try:
            existing = swarm.inspect(member_id, task_id=task_id)
        except Exception:
            raise TrainingError(f"resident task {task_id} could not be started: {exc}") from exc
        if not isinstance(existing, Mapping):
            raise TrainingError(f"resident task {task_id} could not be resumed") from exc
    for _ in range(128):
        boundary = swarm.run_to_boundary(
            member_id,
            task_id=task_id,
            quantum=64,
            max_groups=MAX_GROUPS_PER_BOUNDARY,
        )
        view = boundary.get("view") if isinstance(boundary, Mapping) else None
        if not isinstance(view, Mapping):
            raise TrainingError(f"resident task {task_id} returned no task view")
        status = view.get("status")
        if status == "completed":
            if not isinstance(view.get("result"), Mapping):
                raise TrainingError(f"resident task {task_id} completed without a result")
            return view, boundary
        if status in {"faulted", "cancelled", "paused", "resource-paused"}:
            raise TrainingError(f"resident task {task_id} stopped with status {status}")
        if status not in {"running", "waiting"}:
            raise TrainingError(f"resident task {task_id} returned unsupported status {status!r}")
    raise TrainingError(f"resident task {task_id} exceeded its bounded execution window")


def _capture_head(
    *,
    view: Mapping[str, Any],
    executor: Any,
    expected_source_sha256: str,
    expected_architecture: str,
    expected_backend: str,
    expected_context_tokens: Sequence[int],
) -> tuple[dict[str, Any], dict[str, np.ndarray], dict[str, Any]]:
    model_view = view.get("resident_model")
    descriptor = model_view.get("snapshot") if isinstance(model_view, Mapping) else None
    if not isinstance(descriptor, Mapping):
        raise TrainingError("completed resident task has no final head snapshot descriptor")
    descriptor = _plain(descriptor)
    arrays, metadata = executor._snapshots.load(descriptor)
    if not isinstance(metadata, Mapping) or not isinstance(arrays, Mapping):
        raise TrainingError("head snapshot store returned an invalid capture")
    expected_position = len(expected_context_tokens) - 1
    expected_token = int(expected_context_tokens[-1])
    if (
        metadata.get("source_sha256") != expected_source_sha256
        or metadata.get("architecture") != expected_architecture
        or metadata.get("stage") != "qwen-head"
        or metadata.get("position") != expected_position
        or metadata.get("token") != expected_token
        or metadata.get("backend") != expected_backend
    ):
        raise TrainingError("final head snapshot identity, stage, token, or position does not match the exact prefix")
    hidden = _finite_array(arrays.get("hidden"), ndim=1, label="captured final hidden vector")
    logits = _finite_array(arrays.get("logits"), ndim=1, label="captured native logits")
    if hidden.size == 0 or logits.size <= 1:
        raise TrainingError("captured head has an empty hidden vector or output vocabulary")
    task_tokens = view["result"].get("tokens")
    if not isinstance(task_tokens, list) or len(task_tokens) != 1:
        raise TrainingError("resident task did not produce exactly one next token")
    if int(task_tokens[0]) != int(np.argmax(logits)):
        raise TrainingError("resident task token disagrees with its captured native logits")
    # A resumed task may already be complete, in which case run_to_boundary
    # returns its durable view without a new transient stage receipt.
    return descriptor, {"hidden": hidden, "logits": logits}, dict(metadata)


def _logit_pair(logits: np.ndarray, target_token_id: int, competitor_token_id: int | None = None) -> dict[str, Any]:
    if target_token_id < 0 or target_token_id >= logits.size:
        raise TrainingError("observed next-token ID is outside the model output vocabulary")
    if competitor_token_id is None:
        candidate = np.asarray(logits, dtype=np.float32).copy()
        candidate[target_token_id] = -np.inf
        competitor_token_id = int(np.argmax(candidate))
    if competitor_token_id < 0 or competitor_token_id >= logits.size or competitor_token_id == target_token_id:
        raise TrainingError("selected competitor token is not a distinct output class")
    target_logit = float(logits[target_token_id])
    competitor_logit = float(logits[competitor_token_id])
    margin = target_logit - competitor_logit
    if not math.isfinite(target_logit) or not math.isfinite(competitor_logit) or not math.isfinite(margin):
        raise TrainingError("native logits or measured margin are nonfinite")
    return {
        "target_token_id": int(target_token_id),
        "competitor_token_id": int(competitor_token_id),
        "target_logit": target_logit,
        "competitor_logit": competitor_logit,
        "margin": margin,
    }


def _projection_arrays(
    *,
    executor: Any,
    target_token_id: int,
    competitor_token_id: int,
    hidden: np.ndarray,
    table_vector: np.ndarray,
) -> dict[str, np.ndarray]:
    norm_name = executor._weight("output_norm", None)
    output_name = executor._weight("output", None)
    if norm_name is None or output_name is None:
        raise TrainingError("resident output head lacks RMS norm or unembedding weights")
    output_norm = _finite_array(executor._bank.vector(norm_name), ndim=1, label="output norm")
    target_row = _finite_array(
        executor._bank.embedding(output_name, int(target_token_id)), ndim=1, label="target output row"
    )
    competitor_row = _finite_array(
        executor._bank.embedding(output_name, int(competitor_token_id)), ndim=1, label="competitor output row"
    )
    if output_norm.shape != hidden.shape or target_row.shape != hidden.shape or competitor_row.shape != hidden.shape:
        raise TrainingError("output head rows, normalization vector, and captured hidden width disagree")
    if table_vector.shape != (2560,):
        raise TrainingError("captured table vector has an unexpected width")
    return {
        "hidden": hidden,
        "table_vector": table_vector,
        "output_norm": output_norm,
        "target_row": target_row,
        "competitor_row": competitor_row,
    }


def _readout_state(swarm: ProgrammableSwarm, member_id: str) -> dict[str, Any]:
    member = swarm._member(member_id)
    row = swarm._computer(member)
    if row is None:
        raise TrainingError("owner-held resident computer is missing")
    try:
        return validate_state(row.ngram_readout_state())
    except Exception as exc:
        raise TrainingError(f"owner-held ngram readout state is invalid: {exc}") from exc


def _feedback_for_observation(
    *,
    feedback_id: str,
    token_row: Mapping[str, Any],
    baseline: Mapping[str, Any],
    advantage: float,
    frozen: Mapping[str, np.ndarray],
    model_id: str,
    table_id: str,
) -> dict[str, Any]:
    return make_next_token_feedback(
        feedback_id=feedback_id,
        model_id=model_id,
        table_id=table_id,
        context_tokens=token_row["context_tokens"],
        next_token_id=int(token_row["target_token_id"]),
        competitor_token_id=int(baseline["competitor_token_id"]),
        advantage=advantage,
        hidden=frozen["hidden"],
        output_norm=frozen["output_norm"],
        target_row=frozen["target_row"],
        competitor_row=frozen["competitor_row"],
    )


def _validate_learning_receipt(
    receipt: Mapping[str, Any],
    *,
    feedback: Mapping[str, Any],
    computer_id: str,
    revision_before: int,
    coefficient_sha256_before: str,
) -> str:
    expected = {
        "kind": "ngram-readout-learned",
        "computer_id": computer_id,
        "model_id": feedback["model_id"],
        "table_id": feedback["table_id"],
        "feedback_id": feedback["id"],
        "context_sha256": feedback["context_sha256"],
        "next_token_id": feedback["next_token_id"],
        "competitor_token_id": feedback["competitor_token_id"],
        "advantage": feedback["advantage"],
        "revision_before": revision_before,
        "revision_after": revision_before + 1,
        "coefficient_sha256_before": coefficient_sha256_before,
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise TrainingError("owner ngram learning receipt disagrees with its exact chronological feedback")
    coefficient_sha256_after = _valid_sha256(
        receipt.get("coefficient_sha256_after"), "updated ngram coefficient digest"
    )
    _valid_sha256(receipt.get("state_sha256"), "updated owner computer state digest")
    return coefficient_sha256_after


def _zero_coefficients(state: Mapping[str, Any]) -> bool:
    coefficients = state.get("coefficients")
    if not isinstance(coefficients, Mapping) or not isinstance(coefficients.get("data_b64"), str):
        return False
    try:
        raw = base64.b64decode(coefficients["data_b64"], validate=True)
    except (ValueError, TypeError):
        return False
    expected_bytes = int(state["width"]) * int(state["rank"]) * 4
    return len(raw) == expected_bytes and not any(raw)


def _projection_summary(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        raise TrainingError("cannot summarize an empty measurement split")
    data = np.asarray(values, dtype=np.float64)
    if not np.isfinite(data).all():
        raise TrainingError("projection measurements contain a nonfinite value")
    return {
        "count": int(data.size),
        "mean": float(np.mean(data)),
        "minimum": float(np.min(data)),
        "maximum": float(np.max(data)),
    }


def _projection_for_state(
    *,
    state: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    frozen_arrays: Mapping[str, Mapping[str, np.ndarray]],
    baseline_metrics: Mapping[str, Mapping[str, Any]],
    split_swaps: Mapping[str, Mapping[str, str]],
    initial_state: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    per_row: dict[str, dict[str, float]] = {}
    arrays_by_split: dict[str, dict[str, list[float]]] = {
        "train": {"measured_baseline_margin": [], "projected_margin": [], "zero_vector_margin": [], "table_swapped_margin": []},
        "heldout": {"measured_baseline_margin": [], "projected_margin": [], "zero_vector_margin": [], "table_swapped_margin": []},
    }
    for observation in observations:
        sample_id = str(observation["id"])
        split = str(observation["split"])
        captured = frozen_arrays[sample_id]
        baseline = baseline_metrics[sample_id]
        base_margin = float(baseline["margin"])
        hidden = captured["hidden"]
        common = {
            "output_norm": captured["output_norm"],
            "target_row": captured["target_row"],
            "competitor_row": captured["competitor_row"],
        }
        actual_vector = captured["table_vector"]
        zero_vector = np.zeros_like(actual_vector)
        swapped_id = split_swaps[split][sample_id]
        swapped_vector = frozen_arrays[swapped_id]["table_vector"]
        baseline_shift = (
            0.0 if initial_state is None else
            margin_with_readout(initial_state, actual_vector, hidden, 0.0, **common)
        )
        projected = margin_with_readout(state, actual_vector, hidden, base_margin, **common) - baseline_shift
        zero = margin_with_readout(state, zero_vector, hidden, base_margin, **common) - baseline_shift
        swapped = margin_with_readout(state, swapped_vector, hidden, base_margin, **common) - baseline_shift
        values = {
            "measured_baseline_margin": base_margin,
            "projected_margin": float(projected),
            "zero_vector_margin": float(zero),
            "table_swapped_margin": float(swapped),
        }
        per_row[sample_id] = values
        for name, value in values.items():
            arrays_by_split[split][name].append(float(value))
    summaries: dict[str, Any] = {"splits": {}, "per_sample": per_row}
    numeric_arrays: dict[str, np.ndarray] = {}
    for split, metrics in arrays_by_split.items():
        summaries["splits"][split] = {
            name: _projection_summary(values)
            for name, values in metrics.items()
        }
        for name, values in metrics.items():
            numeric_arrays[f"{split}_{name}"] = np.asarray(values, dtype=np.float64)
    return summaries, numeric_arrays


def _save_projection(
    executor: Any,
    run_id: str,
    revision: int,
    coefficient_sha256: str,
    observations: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    descriptor = executor._snapshots.save(
        dict(arrays),
        {
            "kind": "resident-ngram-chronological-margin-projection",
            "run_id": run_id,
            "revision": int(revision),
            "coefficient_sha256": coefficient_sha256,
            "ordered_ids": [str(row["id"]) for row in observations],
            "ordered_splits": [str(row["split"]) for row in observations],
            "measurement": "projected-from-run-baseline-native-head-captures",
        },
    )
    return {
        "revision": int(revision),
        "coefficient_sha256": coefficient_sha256,
        "snapshot_descriptor": _plain(descriptor),
        "summaries": _plain(metrics["splits"]),
        "measurement": "projected-from-run-baseline-native-head-captures",
    }


def _projected_advantage_before_update(
    executor: Any,
    training: Mapping[str, Any],
    index: int,
    initial_revision: int,
) -> float:
    """Read the current margin before consuming the next observation."""
    projection = (
        training["baseline_projection"]
        if index == 0
        else training["updates"][index - 1]["projection"]
    )
    if not isinstance(projection, Mapping) or projection.get("revision") != initial_revision + index:
        raise TrainingError("preceding readout projection is missing")
    arrays, metadata = executor._snapshots.load(projection["snapshot_descriptor"])
    if (
        metadata.get("kind") != "resident-ngram-chronological-margin-projection"
        or metadata.get("revision") != initial_revision + index
        or metadata.get("coefficient_sha256") != projection.get("coefficient_sha256")
    ):
        raise TrainingError("preceding projection snapshot has a different field revision")
    margins = arrays.get("train_projected_margin")
    if not isinstance(margins, np.ndarray) or margins.ndim != 1 or index >= margins.size:
        raise TrainingError("preceding projection lacks the next training margin")
    advantage = float(margins[index])
    if not math.isfinite(advantage):
        raise TrainingError("preceding projected margin is nonfinite")
    return advantage


def _verify_projection_snapshot(
    *,
    executor: Any,
    projection: Mapping[str, Any],
    run_id: str,
    revision: int,
    coefficient_sha256: str,
    observations: Sequence[Mapping[str, Any]],
    baseline_margins: Mapping[str, float],
) -> dict[str, np.ndarray]:
    descriptor = projection.get("snapshot_descriptor")
    if not isinstance(descriptor, Mapping) or projection.get("revision") != revision:
        raise TrainingError("chronological projection descriptor or revision is invalid")
    arrays, metadata = executor._snapshots.load(descriptor)
    ordered_ids = [str(row["id"]) for row in observations]
    ordered_splits = [str(row["split"]) for row in observations]
    if (
        metadata.get("kind") != "resident-ngram-chronological-margin-projection"
        or metadata.get("run_id") != run_id
        or metadata.get("revision") != revision
        or metadata.get("coefficient_sha256") != coefficient_sha256
        or metadata.get("ordered_ids") != ordered_ids
        or metadata.get("ordered_splits") != ordered_splits
        or projection.get("coefficient_sha256") != coefficient_sha256
        or projection.get("measurement_type") != "projected"
    ):
        raise TrainingError("chronological projection snapshot is not pinned to its owner readout revision")
    verified: dict[str, np.ndarray] = {}
    expected_summaries: dict[str, dict[str, Any]] = {"train": {}, "heldout": {}}
    for split in ("train", "heldout"):
        split_rows = [row for row in observations if row["split"] == split]
        for metric in ("measured_baseline_margin", "projected_margin", "zero_vector_margin", "table_swapped_margin"):
            name = f"{split}_{metric}"
            value = np.asarray(arrays.get(name))
            if value.ndim != 1 or value.size != len(split_rows) or value.dtype.kind not in "fiu" or not np.isfinite(value).all():
                raise TrainingError(f"chronological projection array {name} is missing or invalid")
            verified[name] = value
            expected_summaries[split][metric] = _projection_summary(value.tolist())
        expected_baseline = np.asarray([baseline_margins[str(row["id"])] for row in split_rows], dtype=np.float64)
        if not np.array_equal(np.asarray(verified[f"{split}_measured_baseline_margin"], dtype=np.float64), expected_baseline):
            raise TrainingError(f"chronological projection {split} baselines differ from measured native logits")
    if _canonical_bytes(expected_summaries) != _canonical_bytes(projection.get("summaries")):
        raise TrainingError("chronological projection summaries disagree with their content-addressed arrays")
    return verified


def _make_split_swaps(observations: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for split in ("train", "heldout"):
        group = [row for row in observations if row["split"] == split]
        if len(group) < 2:
            raise TrainingError(f"{split} split is too small for a table-swapped control")
        result[split] = {
            str(row["id"]): str(group[(index + 1) % len(group)]["id"])
            for index, row in enumerate(group)
        }
    return result


def _metric_from_observations(
    observations: Sequence[Mapping[str, Any]], values: Mapping[str, float]
) -> dict[str, Any]:
    return _projection_summary([float(values[str(row["id"])]) for row in observations])


def _persist(record_path: Path, record: dict[str, Any]) -> None:
    record["updated_at"] = _utc_now()
    _atomic_json(record_path, record)


def _read_record(record_path: Path, identity: Mapping[str, Any], run_id: str) -> dict[str, Any] | None:
    if not record_path.exists():
        return None
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TrainingError(f"existing run record cannot be read: {exc}") from exc
    if (
        not isinstance(record, dict)
        or record.get("schema") != RUN_SCHEMA
        or record.get("run_id") != run_id
        or record.get("identity") != _plain(identity)
    ):
        raise TrainingError("existing run record does not match this exact model, table, dataset, field, and output identity")
    if not isinstance(record.get("training"), dict) or not isinstance(record.get("observations"), dict):
        raise TrainingError("existing run record is structurally incomplete")
    return record

def _load_predecessor(path: Path, *, field_path: Path, resident_path: Path,
                      model_id: str, table_id: str, width: int, rank: int) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        prior = json.loads(raw)
        source = prior["identity"]
        field = prior["field"]
        final = prior["summary"]["field"]
        updates = prior["training"]["updates"]
        if (
            prior["schema"] != RUN_SCHEMA or prior["status"] != "completed"
            or prior["summary"]["status"] != "completed"
            or source["field_path"] != str(field_path)
            or source["resident_path"] != str(resident_path)
            or source["model"]["source_sha256"] != model_id
            or source["table"]["table_id"] != table_id
            or final["model_id"] != model_id or final["table_id"] != table_id
            or final["readout_width"] != width or final["readout_rank"] != rank
            or final["computer_id"] != field["computer_id"]
            or not isinstance(updates, list) or not updates
            or updates[-1]["receipt"]["revision_after"] != final["final_readout_revision"]
            or updates[-1]["receipt"]["coefficient_sha256_after"] != final["final_coefficient_sha256"]
        ):
            raise TrainingError("predecessor is not a completed compatible owner-held training run")
        revision = int(final["final_readout_revision"])
        if revision < 1:
            raise TrainingError("predecessor has no committed learning")
        return {
            "record_path": str(path),
            "record_sha256": _sha256_bytes(raw),
            "run_id": str(prior["run_id"]),
            "computer_id": str(field["computer_id"]),
            "member_id": str(field["member_id"]),
            "revision": revision,
            "coefficient_sha256": _valid_sha256(final["final_coefficient_sha256"], "predecessor coefficients"),
            "last_feedback_id": str(updates[-1]["feedback_id"]),
        }
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise TrainingError(f"predecessor training record cannot be verified: {exc}") from exc


def _capture_observation(
    *,
    row: Mapping[str, Any],
    token_row: Mapping[str, Any],
    task_id: str,
    operation_id: str,
    swarm: ProgrammableSwarm,
    member_id: str,
    package: Any,
    client: ResidentQwenClient,
    executor: Any,
    table: Any,
    run_id: str,
    expected_revision: int,
    model_id: str,
    model_architecture: str,
    backend: str,
) -> dict[str, Any]:
    view, _ = _time_task(
        swarm=swarm,
        member_id=member_id,
        package=package,
        model_id=model_id,
        client=client,
        task_id=task_id,
        operation_id=operation_id,
        context_tokens=token_row["context_tokens"],
    )
    descriptor, head_arrays, head_metadata = _capture_head(
        view=view,
        executor=executor,
        expected_source_sha256=model_id,
        expected_architecture=model_architecture,
        expected_backend=backend,
        expected_context_tokens=token_row["context_tokens"],
    )
    state = _readout_state(swarm, member_id)
    if state["revision"] != expected_revision or state["model_id"] != model_id or state["table_id"] != table.table_id:
        raise TrainingError("owner-held readout revision or binding changed during resident observation")
    if np.argmax(head_arrays["logits"]) != int(view["result"]["tokens"][0]):
        raise TrainingError("native head logits disagree with the resident task token")
    measurement = _logit_pair(head_arrays["logits"], int(token_row["target_token_id"]))
    if row["split"] == "train" and (measurement["margin"] < -80.0 or measurement["margin"] > 80.0):
        raise TrainingError(f"row {row['id']} measured next-token margin exceeds the learner's unmodified bound")
    table_vector, _ = table.lookup(token_row["context_tokens"])
    table_vector = _finite_array(table_vector, ndim=1, label="resident ngram context vector")
    if _sha256_bytes(table_vector.astype("<f4", copy=False).tobytes()) != token_row["table_vector_preflight_sha256"]:
        raise TrainingError(f"row {row['id']} table vector changed after tokenizer preflight")
    projection_arrays = _projection_arrays(
        executor=executor,
        target_token_id=int(token_row["target_token_id"]),
        competitor_token_id=int(measurement["competitor_token_id"]),
        hidden=head_arrays["hidden"],
        table_vector=table_vector,
    )
    prefix_position = len(token_row["context_tokens"]) - 1
    metadata_base = {
        "kind": "resident-ngram-baseline-head-capture",
        "run_id": run_id,
        "sample_id": str(row["id"]),
        "dataset_index": int(token_row["dataset_index"]),
        "split": str(row["split"]),
        "model_sha256": model_id,
        "table_id": str(table.table_id),
        "readout_revision": expected_revision,
        "prefix_position": prefix_position,
        "prefix_last_token_id": int(token_row["context_tokens"][-1]),
        "context_tokens_sha256": token_row["context_tokens_sha256"],
        "extended_tokens_sha256": token_row["extended_tokens_sha256"],
        "head_snapshot_sha256": descriptor.get("snapshot_sha256"),
    }
    head_vectors = executor._snapshots.save(
        {"hidden": head_arrays["hidden"], "logits": head_arrays["logits"]},
        {**metadata_base, "kind": "resident-ngram-native-head-arrays"},
    )
    projection_snapshot = executor._snapshots.save(
        projection_arrays,
        {**metadata_base, "kind": "resident-ngram-projection-inputs"},
    )
    head_ref = {
        "descriptor": _plain(descriptor),
        "metadata": _plain(head_metadata),
        "snapshot_sha256": descriptor.get("snapshot_sha256"),
        "arrays_snapshot_descriptor": _plain(head_vectors),
        "logits_ref": _snapshot_array_ref(executor._snapshots, head_vectors, "logits"),
        "hidden_ref": _snapshot_array_ref(executor._snapshots, head_vectors, "hidden"),
    }
    projection_refs = {
        name: _snapshot_array_ref(executor._snapshots, projection_snapshot, name)
        for name in projection_arrays
    }
    return {
        "sample_id": str(row["id"]),
        "dataset_index": int(token_row["dataset_index"]),
        "split": str(row["split"]),
        "model_sha256": model_id,
        "table_id": str(table.table_id),
        "context_tokens_sha256": token_row["context_tokens_sha256"],
        "extended_tokens_sha256": token_row["extended_tokens_sha256"],
        "context_token_count": len(token_row["context_tokens"]),
        "prefix_position": prefix_position,
        "prefix_last_token_id": int(token_row["context_tokens"][-1]),
        "target_token_id": int(token_row["target_token_id"]),
        "task_id": task_id,
        "operation_id": operation_id,
        "baseline_measurement": {
            **measurement,
            "revision": expected_revision,
            "kind": "measured-native-logits",
        },
        "head_snapshot": head_ref,
        "projection_input_snapshot_descriptor": _plain(projection_snapshot),
        "projection_input_refs": projection_refs,
    }


def _verify_observation_snapshots(
    *,
    record: Mapping[str, Any],
    executor: Any,
    row: Mapping[str, Any],
    token_row: Mapping[str, Any],
    model_id: str,
    table_id: str,
    model_architecture: str,
    backend: str,
    expected_revision: int,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    if (
        record.get("sample_id") != row["id"]
        or record.get("dataset_index") != token_row["dataset_index"]
        or record.get("split") != row["split"]
        or record.get("model_sha256") != model_id
        or record.get("table_id") != table_id
        or record.get("context_tokens_sha256") != token_row["context_tokens_sha256"]
        or record.get("extended_tokens_sha256") != token_row["extended_tokens_sha256"]
        or record.get("target_token_id") != token_row["target_token_id"]
        or record.get("context_token_count") != len(token_row["context_tokens"])
        or record.get("prefix_last_token_id") != token_row["context_tokens"][-1]
    ):
        raise TrainingError(f"stored observation {row['id']} does not match its exact source or tokenization")
    head_ref = record.get("head_snapshot")
    if not isinstance(head_ref, Mapping) or not isinstance(head_ref.get("descriptor"), Mapping):
        raise TrainingError(f"stored observation {row['id']} has no exact head snapshot descriptor")
    descriptor = head_ref["descriptor"]
    if descriptor.get("snapshot_sha256") != head_ref.get("snapshot_sha256"):
        raise TrainingError(f"stored observation {row['id']} head snapshot digest disagrees")
    head_arrays, metadata = executor._snapshots.load(descriptor)
    expected_metadata = head_ref.get("metadata")
    if (
        not isinstance(expected_metadata, Mapping)
        or _plain(metadata) != _plain(expected_metadata)
        or metadata.get("source_sha256") != model_id
        or metadata.get("architecture") != model_architecture
        or metadata.get("stage") != "qwen-head"
        or metadata.get("backend") != backend
        or metadata.get("position") != len(token_row["context_tokens"]) - 1
        or metadata.get("token") != token_row["context_tokens"][-1]
    ):
        raise TrainingError(f"stored observation {row['id']} head snapshot metadata no longer matches")
    hidden = _finite_array(head_arrays.get("hidden"), ndim=1, label="stored baseline hidden vector")
    logits = _finite_array(head_arrays.get("logits"), ndim=1, label="stored baseline logits")
    baseline = record.get("baseline_measurement")
    if not isinstance(baseline, Mapping):
        raise TrainingError(f"stored observation {row['id']} has no measured baseline")
    measured = _logit_pair(logits, int(token_row["target_token_id"]), int(baseline.get("competitor_token_id", -1)))
    if (
        measured["target_logit"] != baseline.get("target_logit")
        or measured["competitor_logit"] != baseline.get("competitor_logit")
        or measured["margin"] != baseline.get("margin")
        or baseline.get("revision") != expected_revision
        or baseline.get("kind") != "measured-native-logits"
    ):
        raise TrainingError(f"stored observation {row['id']} measured baseline does not match its logits")
    expected_logits_ref = _snapshot_array_ref(executor._snapshots, head_ref["arrays_snapshot_descriptor"], "logits")
    expected_hidden_ref = _snapshot_array_ref(executor._snapshots, head_ref["arrays_snapshot_descriptor"], "hidden")
    if head_ref.get("logits_ref") != expected_logits_ref or head_ref.get("hidden_ref") != expected_hidden_ref:
        raise TrainingError(f"stored observation {row['id']} content-addressed logits refs disagree")
    copied_arrays, copied_metadata = executor._snapshots.load(head_ref["arrays_snapshot_descriptor"])
    if (
        copied_metadata.get("head_snapshot_sha256") != descriptor.get("snapshot_sha256")
        or copied_metadata.get("context_tokens_sha256") != token_row["context_tokens_sha256"]
        or _sha256_bytes(np.asarray(copied_arrays["logits"], dtype="<f4").tobytes())
        != expected_logits_ref["sha256"]
        or not np.array_equal(np.asarray(copied_arrays["logits"]), logits)
        or not np.array_equal(np.asarray(copied_arrays["hidden"]), hidden)
    ):
        raise TrainingError(f"stored observation {row['id']} copied head arrays no longer match the exact snapshot")
    projection_descriptor = record.get("projection_input_snapshot_descriptor")
    if not isinstance(projection_descriptor, Mapping):
        raise TrainingError(f"stored observation {row['id']} has no projection input snapshot")
    projection_arrays, projection_metadata = executor._snapshots.load(projection_descriptor)
    if (
        projection_metadata.get("head_snapshot_sha256") != descriptor.get("snapshot_sha256")
        or projection_metadata.get("context_tokens_sha256") != token_row["context_tokens_sha256"]
        or projection_metadata.get("readout_revision") != expected_revision
        or projection_metadata.get("model_sha256") != model_id
        or projection_metadata.get("table_id") != table_id
        or projection_metadata.get("sample_id") != row["id"]
    ):
        raise TrainingError(f"stored observation {row['id']} projection input provenance disagrees")
    projection_vectors = {
        name: _finite_array(projection_arrays.get(name), ndim=1, label=f"stored {name}")
        for name in ("hidden", "table_vector", "output_norm", "target_row", "competitor_row")
    }
    if not np.array_equal(projection_vectors["hidden"], hidden):
        raise TrainingError(f"stored observation {row['id']} projection hidden vector differs from captured head")
    if (
        _sha256_bytes(projection_vectors["table_vector"].astype("<f4", copy=False).tobytes())
        != token_row["table_vector_preflight_sha256"]
    ):
        raise TrainingError(f"stored observation {row['id']} table vector no longer matches its exact ngram source")
    expected_projection_refs = record.get("projection_input_refs")
    if not isinstance(expected_projection_refs, Mapping):
        raise TrainingError(f"stored observation {row['id']} projection refs are missing")
    for name, vector in projection_vectors.items():
        if expected_projection_refs.get(name) != _snapshot_array_ref(executor._snapshots, projection_descriptor, name):
            raise TrainingError(f"stored observation {row['id']} {name} content reference disagrees")
        if vector.ndim != 1:
            raise TrainingError(f"stored observation {row['id']} {name} has an invalid shape")
    if (
        projection_vectors["output_norm"].shape != hidden.shape
        or projection_vectors["target_row"].shape != hidden.shape
        or projection_vectors["competitor_row"].shape != hidden.shape
        or projection_vectors["table_vector"].shape != (2560,)
    ):
        raise TrainingError(f"stored observation {row['id']} readout projection vector dimensions disagree")
    return {"hidden": hidden, "logits": logits}, projection_vectors


def _capture_final_heldout(
    *,
    row: Mapping[str, Any],
    token_row: Mapping[str, Any],
    baseline_observation: Mapping[str, Any],
    task_id: str,
    operation_id: str,
    swarm: ProgrammableSwarm,
    member_id: str,
    package: Any,
    client: ResidentQwenClient,
    executor: Any,
    run_id: str,
    expected_revision: int,
    expected_coefficient_sha256: str,
    model_id: str,
    model_architecture: str,
    table_id: str,
    backend: str,
) -> dict[str, Any]:
    before = _readout_state(swarm, member_id)
    if (
        before["revision"] != expected_revision
        or before["coefficients"]["sha256"] != expected_coefficient_sha256
        or before["model_id"] != model_id
        or before["table_id"] != table_id
    ):
        raise TrainingError("final heldout rerun did not begin at the exact final ngram readout revision")
    view, _ = _time_task(
        swarm=swarm,
        member_id=member_id,
        package=package,
        model_id=model_id,
        client=client,
        task_id=task_id,
        operation_id=operation_id,
        context_tokens=token_row["context_tokens"],
    )
    descriptor, head_arrays, head_metadata = _capture_head(
        view=view,
        executor=executor,
        expected_source_sha256=model_id,
        expected_architecture=model_architecture,
        expected_backend=backend,
        expected_context_tokens=token_row["context_tokens"],
    )
    after = _readout_state(swarm, member_id)
    if (
        after["revision"] != expected_revision
        or after["coefficients"]["sha256"] != expected_coefficient_sha256
    ):
        raise TrainingError("owner-held readout changed during final heldout evaluation")
    baseline = baseline_observation["baseline_measurement"]
    measured = _logit_pair(
        head_arrays["logits"],
        int(token_row["target_token_id"]),
        int(baseline["competitor_token_id"]),
    )
    logits_descriptor = executor._snapshots.save(
        {"logits": head_arrays["logits"]},
        {
            "kind": "resident-ngram-final-heldout-live-logits",
            "run_id": run_id,
            "sample_id": str(row["id"]),
            "dataset_index": int(row["dataset_index"]),
            "split": "heldout",
            "model_sha256": model_id,
            "table_id": table_id,
            "readout_revision": expected_revision,
            "coefficient_sha256": expected_coefficient_sha256,
            "head_snapshot_sha256": descriptor.get("snapshot_sha256"),
        },
    )
    return {
        "sample_id": str(row["id"]),
        "dataset_index": int(row["dataset_index"]),
        "split": "heldout",
        "task_id": task_id,
        "operation_id": operation_id,
        "readout_revision": expected_revision,
        "coefficient_sha256": expected_coefficient_sha256,
        "baseline_measured": _plain(baseline),
        "final_live_measured": {
            **measured,
            "revision": expected_revision,
            "kind": "measured-native-logits",
        },
        "head_snapshot": {
            "descriptor": _plain(descriptor),
            "metadata": _plain(head_metadata),
            "snapshot_sha256": descriptor.get("snapshot_sha256"),
        },
        "logits_snapshot_descriptor": _plain(logits_descriptor),
        "logits_ref": _snapshot_array_ref(executor._snapshots, logits_descriptor, "logits"),
        "delta_from_baseline": float(measured["margin"] - float(baseline["margin"])),
    }


def _verify_final_live_capture(
    *,
    live: Mapping[str, Any],
    row: Mapping[str, Any],
    token_row: Mapping[str, Any],
    baseline_observation: Mapping[str, Any],
    executor: Any,
    run_id: str,
    model_id: str,
    model_architecture: str,
    table_id: str,
    backend: str,
    revision: int,
    coefficient_sha256: str,
) -> None:
    if (
        live.get("sample_id") != row["id"]
        or live.get("dataset_index") != token_row["dataset_index"]
        or live.get("split") != "heldout"
        or live.get("readout_revision") != revision
        or live.get("coefficient_sha256") != coefficient_sha256
        or live.get("task_id") == baseline_observation.get("task_id")
    ):
        raise TrainingError(f"final live receipt for {row['id']} does not identify a fresh final-revision heldout task")
    head_ref = live.get("head_snapshot")
    if not isinstance(head_ref, Mapping) or not isinstance(head_ref.get("descriptor"), Mapping):
        raise TrainingError(f"final live receipt for {row['id']} has no exact head snapshot")
    descriptor = head_ref["descriptor"]
    if descriptor.get("snapshot_sha256") != head_ref.get("snapshot_sha256"):
        raise TrainingError(f"final live receipt for {row['id']} head snapshot digest disagrees")
    arrays, metadata = executor._snapshots.load(descriptor)
    if (
        _plain(metadata) != _plain(head_ref.get("metadata"))
        or metadata.get("source_sha256") != model_id
        or metadata.get("architecture") != model_architecture
        or metadata.get("stage") != "qwen-head"
        or metadata.get("backend") != backend
        or metadata.get("position") != len(token_row["context_tokens"]) - 1
        or metadata.get("token") != token_row["context_tokens"][-1]
    ):
        raise TrainingError(f"final live head snapshot for {row['id']} has mismatched source or prefix provenance")
    logits = _finite_array(arrays.get("logits"), ndim=1, label="stored final heldout native logits")
    baseline = baseline_observation["baseline_measurement"]
    measured = _logit_pair(
        logits,
        int(token_row["target_token_id"]),
        int(baseline["competitor_token_id"]),
    )
    stored_measurement = live.get("final_live_measured")
    if (
        not isinstance(stored_measurement, Mapping)
        or stored_measurement.get("kind") != "measured-native-logits"
        or stored_measurement.get("revision") != revision
        or any(measured[name] != stored_measurement.get(name) for name in measured)
        or live.get("delta_from_baseline") != measured["margin"] - float(baseline["margin"])
    ):
        raise TrainingError(f"final live logits for {row['id']} disagree with their stored measured pair")
    logits_descriptor = live.get("logits_snapshot_descriptor")
    if not isinstance(logits_descriptor, Mapping):
        raise TrainingError(f"final live receipt for {row['id']} has no logits content snapshot")
    if live.get("logits_ref") != _snapshot_array_ref(executor._snapshots, logits_descriptor, "logits"):
        raise TrainingError(f"final live logits reference for {row['id']} does not match its snapshot manifest")
    copied_arrays, copied_metadata = executor._snapshots.load(logits_descriptor)
    if (
        copied_metadata.get("kind") != "resident-ngram-final-heldout-live-logits"
        or copied_metadata.get("run_id") != run_id
        or copied_metadata.get("sample_id") != row["id"]
        or copied_metadata.get("model_sha256") != model_id
        or copied_metadata.get("table_id") != table_id
        or copied_metadata.get("readout_revision") != revision
        or copied_metadata.get("coefficient_sha256") != coefficient_sha256
        or copied_metadata.get("head_snapshot_sha256") != descriptor.get("snapshot_sha256")
        or not np.array_equal(np.asarray(copied_arrays.get("logits")), logits)
    ):
        raise TrainingError(f"final live logits snapshot for {row['id']} no longer matches its exact head capture")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train an owner-held resident Qwen ngram readout chronologically.")
    parser.add_argument("--model", required=True, type=Path, help="exact resident Qwen GGUF model")
    parser.add_argument("--table", required=True, type=Path, help="exact Qwen ngram table GGUF shard")
    parser.add_argument("--field", required=True, type=Path, help="owner-held field root; fresh unless --continue-from is supplied")
    parser.add_argument("--resident", required=True, type=Path, help="resident executor SnapshotStore directory")
    parser.add_argument("--observations", required=True, type=Path, help="ordered JSON array of train and heldout examples")
    parser.add_argument("--record-dir", "--results-dir", "--results", dest="record_dir", required=True, type=Path, help="new or resumable run-record directory")
    parser.add_argument("--continue-from", type=Path, default=None, help="completed prior run record whose readout and owner continue this run")
    parser.add_argument("--backend", choices=("vulkan", "cpu"), default="vulkan")
    parser.add_argument("--library", type=Path, default=None, help="optional Vulkan runtime library path")
    parser.add_argument("--threads", type=int, default=8)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, Any]:
    model_path = args.model.expanduser().resolve(strict=True)
    table_path = args.table.expanduser().resolve(strict=True)
    observations_path = args.observations.expanduser().resolve(strict=True)
    field_path = args.field.expanduser().resolve()
    resident_path = args.resident.expanduser().resolve()
    record_dir = args.record_dir.expanduser().resolve()
    library_path = None if args.library is None else args.library.expanduser().resolve(strict=True)
    if not model_path.is_file() or not table_path.is_file() or not observations_path.is_file():
        raise TrainingError("model, table, and observations must be regular files")
    if args.threads < 1:
        raise TrainingError("threads must be a positive integer")
    # A resumed record already pins the full source hashes from its first
    # strict preflight. Its exact saved passages remain usable if other parts
    # of a live source file changed after capture.
    rows, observations_sha256 = _read_observations(observations_path, verify_source_hash=False)

    client = ResidentQwenClient(
        model_path=model_path,
        state_directory=resident_path,
        backend=args.backend,
        library_path=library_path,
        ngram_table_path=table_path,
        threads=args.threads,
    )
    preflight_table: Any | None = None
    owner: FieldIntelligenceOwner | None = None
    swarm: ProgrammableSwarm | None = None
    try:
        if not isinstance(client.model_sha256, str):
            raise TrainingError("resident client could not establish an exact model source identity")
        model_id = _valid_sha256(client.model_sha256, "model source SHA-256")
        preflight_table = Qwen4NgramTable(table_path)
        table_id = _valid_sha256(preflight_table.table_id, "ngram table identity")
        token_rows = _validate_dataset_tokens(rows, client, preflight_table)
        dataset_identity = _dataset_identity(rows)
        dataset_identity["observations_sha256"] = observations_sha256
        dataset_identity["source_path"] = str(observations_path)
        executor = client._ensure_executor()
        table = getattr(executor, "ngram_table", None)
        if table is None or table.table_id != table_id:
            raise TrainingError("resident executor ngram table identity differs from the validated table")
        package = client._package()
        model_architecture = str(client.architecture)
        context_length = int(client._context_length)
        if not _same_plain_tokenizer(client._ensure_tokenizer(), table.tokenizer):
            raise TrainingError("resident executor tokenizer changed after plain-text preflight")
        output_norm_name = executor._weight("output_norm", None)
        output_name = executor._weight("output", None)
        if output_norm_name is None or output_name is None:
            raise TrainingError("resident model is missing output normalization or output projection weights")
        output_norm = _finite_array(executor._bank.vector(output_norm_name), ndim=1, label="resident output norm")
        width = int(output_norm.size)
        rank = min(8, MAX_COEFFICIENTS // width)
        if rank < 3:
            raise TrainingError("resident hidden width cannot fit the ngram readout's bounded coefficient matrix")
        predecessor = (
            None if args.continue_from is None else _load_predecessor(
                args.continue_from.expanduser().resolve(strict=True),
                field_path=field_path, resident_path=resident_path,
                model_id=model_id, table_id=table_id, width=width, rank=rank,
            )
        )
        identity = {
            "schema": RUN_SCHEMA,
            "model": {"path": str(model_path), "source_sha256": model_id, "architecture": model_architecture},
            "table": {"path": str(table_path), "table_id": table_id, "identity_sha256": _canonical_sha256(_plain(table.identity))},
            "field_path": str(field_path),
            "resident_path": str(resident_path),
            "record_dir": str(record_dir),
            "observations": dataset_identity,
            "backend": args.backend,
            "library_path": None if library_path is None else str(library_path),
            "threads": int(args.threads),
            "context_length": context_length,
            "readout_width": width,
            "readout_rank": rank,
            "predecessor": predecessor,
        }
        run_id = _canonical_sha256(identity)
        record_path = record_dir / f"resident-ngram-{run_id}.json"
        record_was_created = False
        record = _read_record(record_path, identity, run_id)
        if record is None:
            verified_rows, verified_sha256 = _read_observations(observations_path)
            if verified_rows != rows or verified_sha256 != observations_sha256:
                raise TrainingError("source observations changed between initial preflight and record creation")
            record_was_created = True
            record = {
                "schema": RUN_SCHEMA,
                "run_id": run_id,
                "identity": _plain(identity),
                "created_at": _utc_now(),
                "updated_at": _utc_now(),
                "status": "starting",
                "field": {
                    "computer_id": predecessor["computer_id"] if predecessor else f"resident-ngram-{run_id[:24]}",
                    "member_id": predecessor["member_id"] if predecessor else f"resident-ngram-member-{run_id[:16]}",
                    "readout_initial": None,
                    "enable_receipt": None,
                },
                "dataset": {
                    "ordered_ids": [str(row["id"]) for row in rows],
                    "train_ids": [str(row["id"]) for row in rows if row["split"] == "train"],
                    "heldout_ids": [str(row["id"]) for row in rows if row["split"] == "heldout"],
                    "source_sha256": observations_sha256,
                },
                "observations": {},
                "training": {
                    "status": "capturing-baseline",
                    "baseline_projection": None,
                    "updates": [],
                    "pending_update": None,
                    "final_live_heldout": [],
                },
                "summary": None,
            }
            _persist(record_path, record)

        if record.get("status") == "completed" and not isinstance(record.get("summary"), Mapping):
            raise TrainingError("completed run record has no final summary")
        computer_id = str(record["field"]["computer_id"])
        member_id = str(record["field"]["member_id"])
        if not record_path.exists():
            raise TrainingError("run record disappeared before owner initialization")
        owner = FieldIntelligenceOwner(field_path)
        if record.get("created_at") is None:
            raise TrainingError("run record creation time is missing")
        if record_was_created:
            computer_ids = [row.computer_id for row in getattr(owner.state, "computers", ())]
            if (computer_id in computer_ids) != (predecessor is not None):
                raise TrainingError("predecessor computer presence disagrees with the new run's ownership")
        swarm = ProgrammableSwarm()
        swarm.add_member(member_id, owner, computer_id=computer_id, placement="logical-cpu")
        swarm.ensure_computer(member_id)
        swarm.ensure_program_runtime(member_id)
        # Native captures are durable before their continuations are retired.
        # Reclaim recorded tasks on restart as well: the task region otherwise
        # grows with every observation even though the snapshots already hold
        # all data needed for projection and audit.
        for captured in record["observations"].values():
            swarm.release_task(member_id, str(captured["task_id"]))
        for captured in record["training"]["final_live_heldout"]:
            swarm.release_task(member_id, str(captured["task_id"]))
        client.bind_entity(SimpleNamespace(program_runtime=swarm, _program_member_id=member_id))
        # The preflight table is only a tokenizer check; all captures use the
        # exact table instance attached to the resident executor.
        if preflight_table is not None and callable(getattr(preflight_table, "close", None)):
            preflight_table.close()
        preflight_table = None

        if predecessor is None:
            enable = owner.operate_computer(
                f"ngram-enable:{run_id[:48]}",
                computer_id=computer_id,
                action="enable-ngram",
                arguments={"model_id": model_id, "table_id": table_id, "width": width, "rank": rank},
            )
            enable_receipt = enable.get("receipt") if isinstance(enable, Mapping) else None
            if not isinstance(enable_receipt, Mapping):
                raise TrainingError("owner did not return an ngram enable receipt")
        else:
            enable_receipt = None
        initial_state = _readout_state(swarm, member_id)
        if (
            initial_state["model_id"] != model_id
            or initial_state["table_id"] != table_id
            or initial_state["width"] != width
            or initial_state["rank"] != rank
        ):
            raise TrainingError("owner-held readout binding does not match this exact model and ngram table")
        field_record = record["field"]
        if field_record.get("readout_initial") is None:
            if predecessor is None:
                if (
                    initial_state["revision"] != 0
                    or initial_state["last_feedback"] is not None
                    or initial_state["feedback_history"]
                    or not _zero_coefficients(initial_state)
                    or not isinstance(enable_receipt, Mapping)
                    or enable_receipt.get("coefficient_sha256") != initial_state["coefficients"]["sha256"]
                ):
                    raise TrainingError("new owner readout is not a pristine revision-zero state")
            elif (
                initial_state["revision"] != predecessor["revision"]
                or initial_state["coefficients"]["sha256"] != predecessor["coefficient_sha256"]
                or not isinstance(initial_state["last_feedback"], Mapping)
                or initial_state["last_feedback"].get("id") != predecessor["last_feedback_id"]
            ):
                raise TrainingError("owner readout no longer equals the completed predecessor state")
            field_record["readout_initial"] = {
                "revision": initial_state["revision"],
                "coefficient_sha256": initial_state["coefficients"]["sha256"],
                "model_id": model_id,
                "table_id": table_id,
                "width": width,
                "rank": rank,
                "state": _plain(initial_state),
            }
            field_record["enable_receipt"] = _plain(enable_receipt) if predecessor is None else None
            _persist(record_path, record)
        else:
            pinned = field_record["readout_initial"]
            stored_enable = field_record.get("enable_receipt")
            if (
                not isinstance(pinned, Mapping)
                or pinned.get("revision") != (predecessor["revision"] if predecessor else 0)
                or pinned.get("model_id") != model_id
                or pinned.get("table_id") != table_id
                or pinned.get("width") != width
                or pinned.get("rank") != rank
                or (predecessor is None and (
                    not isinstance(stored_enable, Mapping)
                    or pinned.get("coefficient_sha256") != stored_enable.get("coefficient_sha256")
                ))
                or (predecessor is not None and pinned.get("coefficient_sha256") != predecessor["coefficient_sha256"])
            ):
                raise TrainingError("run record's initial readout binding is invalid")

        expected_train_ids = [str(row["id"]) for row in rows if row["split"] == "train"]
        observations_by_id = record["observations"]
        if set(observations_by_id) - {str(row["id"]) for row in rows}:
            raise TrainingError("run record contains observations outside the exact input dataset")
        initial_revision = int(field_record["readout_initial"]["revision"])
        stored_initial_state = field_record["readout_initial"].get("state")
        if stored_initial_state is None:
            if initial_revision != 0:
                raise TrainingError("continuation run has no pinned initial readout coefficients")
            initial_state_for_projection = None
        else:
            initial_state_for_projection = validate_state(stored_initial_state)
            if (
                initial_state_for_projection["revision"] != initial_revision
                or initial_state_for_projection["coefficients"]["sha256"]
                != field_record["readout_initial"]["coefficient_sha256"]
                or initial_state_for_projection["model_id"] != model_id
                or initial_state_for_projection["table_id"] != table_id
            ):
                raise TrainingError("pinned initial readout state differs from the run's predecessor")
        record["status"] = "capturing-baseline"
        for row, token_row in zip(rows, token_rows):
            sample_id = str(row["id"])
            prior = observations_by_id.get(sample_id)
            if prior is not None:
                continue
            if row["split"] == "heldout" and any(
                str(train_row["id"]) not in observations_by_id
                for train_row in rows
                if train_row["split"] == "train"
            ):
                raise TrainingError("heldout capture cannot precede complete chronological train baselines")
            baseline_state = _readout_state(swarm, member_id)
            if (
                baseline_state["revision"] != initial_revision
                or baseline_state["coefficients"]["sha256"] != field_record["readout_initial"]["coefficient_sha256"]
            ):
                raise TrainingError("baseline observation capture attempted after the readout changed")
            task_id = f"ngram-{run_id[:12]}-base-{int(token_row['dataset_index']):04d}"
            operation_id = f"{task_id}-start"
            observation = _capture_observation(
                row=row,
                token_row=token_row,
                task_id=task_id,
                operation_id=operation_id,
                swarm=swarm,
                member_id=member_id,
                package=package,
                client=client,
                executor=executor,
                table=table,
                run_id=run_id,
                expected_revision=initial_revision,
                model_id=model_id,
                model_architecture=model_architecture,
                backend=args.backend,
            )
            observations_by_id[sample_id] = observation
            _persist(record_path, record)
            swarm.release_task(member_id, task_id)

        if [str(row["id"]) for row in rows] != [str(record["observations"][str(row["id"])]["sample_id"]) for row in rows]:
            raise TrainingError("baseline observation records do not preserve exact dataset order")
        captured_observations = [record["observations"][str(row["id"])] for row in rows]
        frozen_arrays: dict[str, dict[str, np.ndarray]] = {}
        for row, token_row, observation in zip(rows, token_rows, captured_observations):
            _, projection_inputs = _verify_observation_snapshots(
                record=observation,
                executor=executor,
                row=row,
                token_row=token_row,
                model_id=model_id,
                table_id=table_id,
                model_architecture=model_architecture,
                backend=args.backend,
                expected_revision=initial_revision,
            )
            frozen_arrays[str(row["id"])] = projection_inputs
        baseline_metrics = {
            str(observation["sample_id"]): dict(observation["baseline_measurement"])
            for observation in captured_observations
        }
        observation_values = rows
        split_swaps = _make_split_swaps(observation_values)
        training = record["training"]
        updates = training["updates"]
        if not isinstance(updates, list) or len(updates) > len(expected_train_ids):
            raise TrainingError("training update history does not match the chronological train split")
        if [entry.get("sample_id") for entry in updates] != expected_train_ids[:len(updates)]:
            raise TrainingError("training updates are not a single chronological pass over train rows")
        initial = record["field"]["readout_initial"]
        coefficient_before = _valid_sha256(initial.get("coefficient_sha256"), "initial readout coefficient digest")
        row_by_id = {str(row["id"]): row for row in rows}
        token_row_by_id = {str(token_row["id"]): token_row for token_row in token_rows}
        for index, update in enumerate(updates):
            sample_id = expected_train_ids[index]
            row = row_by_id[sample_id]
            token_row = token_row_by_id[sample_id]
            baseline = baseline_metrics[sample_id]
            expected_feedback_id = f"train:{run_id[:24]}:{int(row['dataset_index']):04d}"
            expected_operation_id = f"ngram-learn:{run_id[:24]}:{int(row['dataset_index']):04d}"
            feedback = _feedback_for_observation(
                feedback_id=expected_feedback_id,
                token_row=token_row,
                baseline=baseline,
                advantage=_projected_advantage_before_update(executor, training, index, initial_revision),
                frozen=frozen_arrays[sample_id],
                model_id=model_id,
                table_id=table_id,
            )
            receipt = update.get("receipt")
            if (
                update.get("dataset_index") != row["dataset_index"]
                or update.get("feedback_id") != expected_feedback_id
                or update.get("operation_id") != expected_operation_id
                or not isinstance(receipt, Mapping)
            ):
                raise TrainingError("stored chronological update identity or receipt is invalid")
            coefficient_after = _validate_learning_receipt(
                receipt,
                feedback=feedback,
                computer_id=computer_id,
                revision_before=initial_revision + index,
                coefficient_sha256_before=coefficient_before,
            )
            projection = update.get("projection")
            if projection is None:
                if index != len(updates) - 1:
                    raise TrainingError("an earlier chronological update is missing its projected margin receipt")
            elif (
                not isinstance(projection, Mapping)
                or projection.get("revision") != initial_revision + index + 1
                or projection.get("coefficient_sha256") != coefficient_after
                or projection.get("measurement_type") != "projected"
            ):
                raise TrainingError("chronological update projection is not pinned to its learned readout revision")
            coefficient_before = coefficient_after
        pending = training.get("pending_update")
        current_state = _readout_state(swarm, member_id)
        expected_revision = initial_revision + len(updates)
        pending_feedback: dict[str, Any] | None = None
        if pending is None:
            if (
                current_state["revision"] != expected_revision
                or current_state["coefficients"]["sha256"] != coefficient_before
            ):
                raise TrainingError("owner readout revision or coefficients disagree with durable chronological update history")
            last = current_state.get("last_feedback")
            if len(updates) and (
                not isinstance(last, Mapping)
                or last.get("id") != updates[-1]["feedback_id"]
            ):
                raise TrainingError("owner readout last feedback disagrees with the durable update history")
            if not updates and predecessor is not None and (
                not isinstance(last, Mapping) or last.get("id") != predecessor["last_feedback_id"]
            ):
                raise TrainingError("owner readout no longer carries the predecessor's final feedback")
            if not updates and predecessor is None and last is not None:
                raise TrainingError("revision-zero owner readout unexpectedly has feedback history")
        else:
            if not isinstance(pending, Mapping) or pending.get("dataset_index") != len(updates):
                raise TrainingError("pending ngram update does not match the next chronological train row")
            pending_index = int(pending["dataset_index"])
            if pending_index >= len(expected_train_ids):
                raise TrainingError("pending ngram update lies outside the chronological train split")
            pending_id = expected_train_ids[pending_index]
            pending_row = row_by_id[pending_id]
            pending_token_row = token_row_by_id[pending_id]
            expected_feedback_id = f"train:{run_id[:24]}:{int(pending_row['dataset_index']):04d}"
            expected_operation_id = f"ngram-learn:{run_id[:24]}:{int(pending_row['dataset_index']):04d}"
            if (
                pending.get("sample_id") != pending_id
                or pending.get("feedback_id") != expected_feedback_id
                or pending.get("operation_id") != expected_operation_id
            ):
                raise TrainingError("pending ngram update identity is not the next chronological row")
            pending_feedback = _feedback_for_observation(
                feedback_id=expected_feedback_id,
                token_row=pending_token_row,
                baseline=baseline_metrics[pending_id],
                advantage=_projected_advantage_before_update(executor, training, pending_index, initial_revision),
                frozen=frozen_arrays[pending_id],
                model_id=model_id,
                table_id=table_id,
            )
            if (
                pending.get("feedback") != pending_feedback
                or pending.get("feedback_sha256") != _canonical_sha256(pending_feedback)
            ):
                raise TrainingError("pending feedback differs from the frozen measured observation")
            if current_state["revision"] == expected_revision + 1:
                last = current_state.get("last_feedback")
                if not isinstance(last, Mapping) or any(
                    last.get(key) != pending_feedback[value]
                    for key, value in (
                        ("id", "id"),
                        ("context_sha256", "context_sha256"),
                        ("next_token_id", "next_token_id"),
                        ("competitor_token_id", "competitor_token_id"),
                        ("advantage", "advantage"),
                    )
                ):
                    raise TrainingError("owner readout advanced with a different pending feedback record")
            elif current_state["revision"] == expected_revision:
                if current_state["coefficients"]["sha256"] != coefficient_before:
                    raise TrainingError("owner readout coefficients changed before the pending update")
            else:
                raise TrainingError("owner readout revision cannot be reconciled with the pending update")
        if training.get("baseline_projection") is None:
            if _readout_state(swarm, member_id)["revision"] != initial_revision:
                raise TrainingError("baseline projection is missing after the owner readout advanced")
            zero_state = _readout_state(swarm, member_id)
            zero_summary, zero_arrays = _projection_for_state(
                state=zero_state,
                observations=observation_values,
                frozen_arrays=frozen_arrays,
                baseline_metrics=baseline_metrics,
                split_swaps=split_swaps,
                initial_state=initial_state_for_projection,
            )
            training["baseline_projection"] = _save_projection(
                executor,
                run_id,
                initial_revision,
                str(zero_state["coefficients"]["sha256"]),
                observation_values,
                zero_summary,
                zero_arrays,
            )
            training["baseline_projection"]["measurement_type"] = "projected"
            _persist(record_path, record)
        elif training["baseline_projection"].get("revision") != initial_revision:
            raise TrainingError("stored baseline projection is not at the run's initial revision")

        # A crash after an owner commit but before the run-record append is
        # reconciled by replaying the deterministic operation ID.
        if pending is not None:
            pending_id = str(pending["sample_id"])
            pending_row = row_by_id[pending_id]
            pending_token_row = token_row_by_id[pending_id]
            pending_index = int(pending["dataset_index"])
            if pending_feedback is None:
                raise TrainingError("pending feedback was not reconstructed from its frozen observation")
            frozen = frozen_arrays[pending_id]
            applied = owner.operate_computer(
                str(pending["operation_id"]),
                computer_id=computer_id,
                action="learn-ngram",
                arguments={
                    "table_vector": frozen["table_vector"].tolist(),
                    "hidden": frozen["hidden"].tolist(),
                    "feedback": pending_feedback,
                },
            )
            applied_receipt = applied.get("receipt") if isinstance(applied, Mapping) else None
            if not isinstance(applied_receipt, Mapping):
                raise TrainingError("owner learning operation returned no matching feedback receipt")
            coefficient_after = _validate_learning_receipt(
                applied_receipt,
                feedback=pending_feedback,
                computer_id=computer_id,
                revision_before=expected_revision,
                coefficient_sha256_before=coefficient_before,
            )
            after_pending = _readout_state(swarm, member_id)
            if (
                after_pending["revision"] != expected_revision + 1
                or after_pending["coefficients"]["sha256"] != coefficient_after
                or after_pending["last_feedback"]["id"] != pending_feedback["id"]
            ):
                raise TrainingError("owner readout state does not confirm the pending chronological operation")
            updates.append({
                "dataset_index": int(pending_row["dataset_index"]),
                "sample_id": pending_id,
                "feedback_id": str(pending["feedback_id"]),
                "operation_id": str(pending["operation_id"]),
                "receipt": _plain(applied_receipt),
                "projection": None,
            })
            training["pending_update"] = None
            _persist(record_path, record)
            coefficient_before = coefficient_after

        # Every applied revision gets an immutable projection receipt before a
        # later row can advance the field state.
        for update in updates:
            if update.get("projection") is not None:
                continue
            state = _readout_state(swarm, member_id)
            revision = int(update["receipt"].get("revision_after", -1))
            if state["revision"] != revision or update is not updates[-1]:
                raise TrainingError("a historical projection receipt is missing after the field advanced")
            summary, arrays = _projection_for_state(
                state=state,
                observations=observation_values,
                frozen_arrays=frozen_arrays,
                baseline_metrics=baseline_metrics,
                split_swaps=split_swaps,
                initial_state=initial_state_for_projection,
            )
            update["projection"] = _save_projection(
                executor,
                run_id,
                revision,
                str(state["coefficients"]["sha256"]),
                observation_values,
                summary,
                arrays,
            )
            update["projection"]["measurement_type"] = "projected"
            _persist(record_path, record)

        train_rows = [row for row in observation_values if row["split"] == "train"]
        heldout_rows = [row for row in observation_values if row["split"] == "heldout"]
        while len(updates) < len(expected_train_ids):
            row = next(row for row in rows if row["id"] == expected_train_ids[len(updates)])
            token_row = token_rows[int(row["dataset_index"])]
            observation = record["observations"][str(row["id"])]
            baseline = observation["baseline_measurement"]
            captured = frozen_arrays[str(row["id"])]
            feedback_id = f"train:{run_id[:24]}:{int(row['dataset_index']):04d}"
            operation_id = f"ngram-learn:{run_id[:24]}:{int(row['dataset_index']):04d}"
            feedback = _feedback_for_observation(
                feedback_id=feedback_id,
                token_row=token_row,
                baseline=baseline,
                frozen=captured,
                advantage=_projected_advantage_before_update(executor, training, len(updates), initial_revision),
                model_id=model_id,
                table_id=table_id,
            )
            pending = {
                "dataset_index": int(row["dataset_index"]),
                "sample_id": str(row["id"]),
                "feedback_id": feedback_id,
                "feedback_sha256": _canonical_sha256(feedback),
                "operation_id": operation_id,
                "feedback": feedback,
            }
            training["pending_update"] = pending
            training["status"] = "training-chronologically"
            _persist(record_path, record)
            applied = owner.operate_computer(
                operation_id,
                computer_id=computer_id,
                action="learn-ngram",
                arguments={
                    "table_vector": captured["table_vector"].tolist(),
                    "hidden": captured["hidden"].tolist(),
                    "feedback": feedback,
                },
            )
            receipt = applied.get("receipt") if isinstance(applied, Mapping) else None
            if not isinstance(receipt, Mapping):
                raise TrainingError("owner learning operation returned no matching feedback receipt")
            coefficient_after = _validate_learning_receipt(
                receipt,
                feedback=feedback,
                computer_id=computer_id,
                revision_before=initial_revision + len(updates),
                coefficient_sha256_before=coefficient_before,
            )
            updated_state = _readout_state(swarm, member_id)
            if (
                updated_state["revision"] != initial_revision + len(updates) + 1
                or updated_state["coefficients"]["sha256"] != coefficient_after
                or not isinstance(updated_state.get("last_feedback"), Mapping)
                or updated_state["last_feedback"].get("id") != feedback_id
            ):
                raise TrainingError("owner readout state does not confirm the just-published chronological update")
            updates.append({
                "dataset_index": int(row["dataset_index"]),
                "sample_id": str(row["id"]),
                "feedback_id": feedback_id,
                "operation_id": operation_id,
                "receipt": _plain(receipt),
                "projection": None,
            })
            training["pending_update"] = None
            _persist(record_path, record)
            coefficient_before = coefficient_after
            projection_summary, projection_arrays = _projection_for_state(
                state=updated_state,
                observations=observation_values,
                frozen_arrays=frozen_arrays,
                baseline_metrics=baseline_metrics,
                split_swaps=split_swaps,
                initial_state=initial_state_for_projection,
            )
            updates[-1]["projection"] = _save_projection(
                executor,
                run_id,
                int(updated_state["revision"]),
                str(updated_state["coefficients"]["sha256"]),
                observation_values,
                projection_summary,
                projection_arrays,
            )
            updates[-1]["projection"]["measurement_type"] = "projected"
            _persist(record_path, record)

        final_state = _readout_state(swarm, member_id)
        if final_state["revision"] != initial_revision + len(expected_train_ids):
            raise TrainingError("final owner readout revision does not equal the starting revision plus train-row count")
        final_coefficient_sha256 = str(final_state["coefficients"]["sha256"])
        baseline_projection = training.get("baseline_projection")
        if not isinstance(baseline_projection, Mapping):
            raise TrainingError("baseline projected margin receipt is missing")
        initial_coefficient_sha256 = _valid_sha256(
            initial.get("coefficient_sha256"), "initial readout coefficient digest"
        )
        baseline_values_for_projection = {
            sample_id: float(value["margin"])
            for sample_id, value in baseline_metrics.items()
        }
        verified_projection_arrays: dict[int, dict[str, np.ndarray]] = {
            initial_revision: _verify_projection_snapshot(
                executor=executor,
                projection=baseline_projection,
                run_id=run_id,
                revision=initial_revision,
                coefficient_sha256=initial_coefficient_sha256,
                observations=observation_values,
                baseline_margins=baseline_values_for_projection,
            )
        }
        projection_coefficient = initial_coefficient_sha256
        for index, update in enumerate(updates):
            sample_id = expected_train_ids[index]
            feedback = _feedback_for_observation(
                feedback_id=str(update["feedback_id"]),
                token_row=token_row_by_id[sample_id],
                baseline=baseline_metrics[sample_id],
                advantage=float(verified_projection_arrays[initial_revision + index]["train_projected_margin"][index]),
                frozen=frozen_arrays[sample_id],
                model_id=model_id,
                table_id=table_id,
            )
            projection_coefficient = _validate_learning_receipt(
                update["receipt"],
                feedback=feedback,
                computer_id=computer_id,
                revision_before=initial_revision + index,
                coefficient_sha256_before=projection_coefficient,
            )
            verified_projection_arrays[initial_revision + index + 1] = _verify_projection_snapshot(
                executor=executor,
                projection=update["projection"],
                run_id=run_id,
                revision=initial_revision + index + 1,
                coefficient_sha256=projection_coefficient,
                observations=observation_values,
                baseline_margins=baseline_values_for_projection,
            )
        if projection_coefficient != final_coefficient_sha256:
            raise TrainingError("chronological receipts do not reach the exact final owner readout coefficient digest")
        final_projection_arrays = verified_projection_arrays[int(final_state["revision"])]
        training["status"] = "final-heldout-live-reruns"
        _persist(record_path, record)

        # Final live measurements use stable, never-baseline task IDs.  A crash
        # resumes each deterministic task rather than creating a duplicate.
        final_live_records = training.get("final_live_heldout")
        if not isinstance(final_live_records, list) or any(not isinstance(item, Mapping) for item in final_live_records):
            raise TrainingError("final live heldout run records are structurally invalid")
        expected_heldout_ids = [str(row["id"]) for row in rows if row["split"] == "heldout"]
        final_live_by_id = {str(item["sample_id"]): item for item in final_live_records}
        if len(final_live_by_id) != len(final_live_records) or not set(final_live_by_id).issubset(expected_heldout_ids):
            raise TrainingError("final live heldout records contain duplicate or unreserved sample identities")
        for row in rows:
            if row["split"] != "heldout":
                continue
            sample_id = str(row["id"])
            token_row = token_row_by_id[sample_id]
            baseline_observation = record["observations"][sample_id]
            task_id = f"ngram-{run_id[:12]}-live-{int(row['dataset_index']):04d}"
            operation_id = f"{task_id}-start"
            prior = final_live_by_id.get(sample_id)
            if prior is not None:
                if prior.get("task_id") != task_id or prior.get("operation_id") != operation_id:
                    raise TrainingError("stored final heldout measurement does not use its deterministic fresh task identity")
                _verify_final_live_capture(
                    live=prior,
                    row=row,
                    token_row=token_row,
                    baseline_observation=baseline_observation,
                    executor=executor,
                    run_id=run_id,
                    model_id=model_id,
                    model_architecture=model_architecture,
                    table_id=table_id,
                    backend=args.backend,
                    revision=int(final_state["revision"]),
                    coefficient_sha256=final_coefficient_sha256,
                )
                continue
            live = _capture_final_heldout(
                row=row,
                token_row=token_row,
                baseline_observation=baseline_observation,
                task_id=task_id,
                operation_id=operation_id,
                swarm=swarm,
                member_id=member_id,
                package=package,
                client=client,
                executor=executor,
                run_id=run_id,
                expected_revision=int(final_state["revision"]),
                expected_coefficient_sha256=final_coefficient_sha256,
                model_id=model_id,
                model_architecture=model_architecture,
                table_id=table_id,
                backend=args.backend,
            )
            _verify_final_live_capture(
                live=live,
                row=row,
                token_row=token_row,
                baseline_observation=baseline_observation,
                executor=executor,
                run_id=run_id,
                model_id=model_id,
                model_architecture=model_architecture,
                table_id=table_id,
                backend=args.backend,
                revision=int(final_state["revision"]),
                coefficient_sha256=final_coefficient_sha256,
            )
            training["final_live_heldout"].append(live)
            final_live_by_id[sample_id] = live
            _persist(record_path, record)
            swarm.release_task(member_id, task_id)

        if [str(item["sample_id"]) for item in final_live_records] != expected_heldout_ids:
            raise TrainingError("final live heldout records do not preserve exact reserved-split order")
        if len({str(item["task_id"]) for item in final_live_records}) != len(expected_heldout_ids):
            raise TrainingError("final heldout reruns did not use unique fresh task identities")
        if len(updates) != len(expected_train_ids) or training.get("pending_update") is not None:
            raise TrainingError("chronological training did not consume each train row exactly once")
        if [str(item["sample_id"]) for item in updates] != expected_train_ids:
            raise TrainingError("chronological update records do not match the ordered train split")

        final_projection = updates[-1]["projection"] if updates else baseline_projection
        if final_projection is None or final_projection.get("revision") != final_state["revision"]:
            raise TrainingError("final projected heldout record is missing or at the wrong readout revision")
        final_projection_values = {
            str(sample_id): float(final_projection_arrays[f"heldout_projected_margin"][index])
            for index, sample_id in enumerate([str(row["id"]) for row in rows if row["split"] == "heldout"])
        }
        live_by_id = {str(item["sample_id"]): item for item in training["final_live_heldout"]}
        final_live_values = {
            sample_id: float(live_by_id[sample_id]["final_live_measured"]["margin"])
            for sample_id in final_projection_values
        }
        baseline_values = {
            str(row["id"]): float(record["observations"][str(row["id"])]["baseline_measurement"]["margin"])
            for row in rows
        }
        projected_summaries = {
            "train": _metric_from_observations(train_rows, {
                str(row["id"]): float(final_projection_arrays[f"train_projected_margin"][index])
                for index, row in enumerate([row for row in rows if row["split"] == "train"])
            }),
            "heldout": _metric_from_observations(heldout_rows, final_projection_values),
        }
        live_summary = _projection_summary(list(final_live_values.values()))
        baseline_summary = {
            split: _metric_from_observations(
                [row for row in rows if row["split"] == split],
                baseline_values,
            )
            for split in ("train", "heldout")
        }
        delta_values = {
            sample_id: final_live_values[sample_id] - baseline_values[sample_id]
            for sample_id in final_live_values
        }
        chronological_projections = [
            {
                "revision": initial_revision,
                "readout_coefficient_sha256": baseline_projection["coefficient_sha256"],
                "measurement_type": "projected",
                "snapshot_descriptor": baseline_projection["snapshot_descriptor"],
                "summaries": baseline_projection["summaries"],
            }
        ] + [
            {
                "revision": int(update["projection"]["revision"]),
                "readout_coefficient_sha256": update["projection"]["coefficient_sha256"],
                "feedback_id": update["feedback_id"],
                "sample_id": update["sample_id"],
                "measurement_type": "projected",
                "snapshot_descriptor": update["projection"]["snapshot_descriptor"],
                "summaries": update["projection"]["summaries"],
            }
            for update in updates
        ]
        summary = {
            "schema": RUN_SCHEMA,
            "status": "completed",
            "run_id": run_id,
            "record_path": str(record_path),
            "source_identity": _plain(identity),
            "field": {
                "computer_id": computer_id,
                "model_id": model_id,
                "table_id": table_id,
                "initial_readout_revision": initial_revision,
                "final_readout_revision": int(final_state["revision"]),
                "readout_width": width,
                "readout_rank": int(final_state["rank"]),
                "final_coefficient_sha256": final_coefficient_sha256,
            },
            "dataset": {
                "ordered_ids": [str(row["id"]) for row in rows],
                "train_count": len(train_rows),
                "heldout_count": len(heldout_rows),
                "observations_sha256": observations_sha256,
            },
            "measured_run_baseline_margins": baseline_summary,
            "final_projected_margins_from_run_baseline_captures": projected_summaries,
            "final_live_heldout": {
                "measurement_type": "measured-native-logits",
                "readout_revision": int(final_state["revision"]),
                "margin": live_summary,
                "delta_from_baseline": _projection_summary(list(delta_values.values())),
                "rows": [
                    {
                        "sample_id": item["sample_id"],
                        "task_id": item["task_id"],
                        "readout_revision": item["readout_revision"],
                        "baseline_measured_logits_and_margin": item["baseline_measured"],
                        "final_live_measured_logits_and_margin": item["final_live_measured"],
                        "projected_final_margin": final_projection_values[str(item["sample_id"])],
                        "delta_from_baseline": item["delta_from_baseline"],
                        "head_snapshot_sha256": item["head_snapshot"]["snapshot_sha256"],
                        "logits_ref": item["logits_ref"],
                    }
                    for item in training["final_live_heldout"]
                ],
            },
            "chronological_projection_history": chronological_projections,
            "train_update_count": len(updates),
            "operation_receipts": [
                {
                    "sample_id": update["sample_id"],
                    "feedback_id": update["feedback_id"],
                    "operation_id": update["operation_id"],
                    "receipt": update["receipt"],
                }
                for update in updates
            ],
        }
        record["status"] = "completed"
        record["training"]["status"] = "completed"
        record["summary"] = summary
        _persist(record_path, record)
        return summary
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        if owner is not None:
            owner.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        summary = run(args)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(_plain(summary), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
