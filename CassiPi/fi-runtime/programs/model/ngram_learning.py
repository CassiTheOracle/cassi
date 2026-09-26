"""Compact field-owned readout learning for a pinned Qwen n-gram table.

The field stores one bounded low-rank coefficient matrix.  Inputs and model
weights remain read-only; learning consumes an observed next-token margin and
its output-head margin direction, then returns a new JSON-safe state for the
canonical Cassi field to persist.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
from numbers import Real
from typing import Any, Mapping

import numpy as np


STATE_SCHEMA = "cassifi.qwen-ngram-readout.v1"
FEEDBACK_SCHEMA = "cassifi.qwen-ngram-next-token-feedback.v1"
TABLE_VECTOR_SIZE = 2560
MAX_WIDTH = 8192
MAX_RANK = 32
MAX_COEFFICIENTS = 16_384
MAX_FEEDBACK_HISTORY = 64
MAX_FEEDBACK_ID_BYTES = 128
MAX_STATE_CAPACITY_WORDS = 32_768
_STATE_HISTORY_SLACK_BYTES = 12_288
_LEARNING_RATE = 0.02
_MAX_COEFFICIENT_NORM = 0.25
_MAX_RESIDUAL_NORM = 0.25
_MAX_MARGIN = 80.0
_MAX_TOKEN_ID = (1 << 31) - 1


class NgramLearningError(ValueError):
    """A readout state, input, or next-token feedback is not canonical."""


def _text(value: Any, label: str, *, maximum_bytes: int = 4096) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise NgramLearningError(f"{label} must be nonempty text")
    if len(value.encode("utf-8")) > maximum_bytes:
        raise NgramLearningError(f"{label} exceeds its bound")
    return value


def _integer(value: Any, label: str, *, minimum: int = 0, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise NgramLearningError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise NgramLearningError(f"{label} is outside its bound")
    return int(value)


def _digest(value: Any, label: str) -> str:
    text = _text(value, label, maximum_bytes=64)
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise NgramLearningError(f"{label} must be a lowercase SHA-256 digest")
    return text


def _real(value: Any, label: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise NgramLearningError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise NgramLearningError(f"{label} is outside its bound")
    return result


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise NgramLearningError("readout state is not canonical JSON") from exc


def _dimensions(width: Any, rank: Any) -> tuple[int, int]:
    width = _integer(width, "readout width", minimum=1, maximum=MAX_WIDTH)
    rank = _integer(rank, "readout rank", minimum=3, maximum=MAX_RANK)
    if rank > width or width * rank > MAX_COEFFICIENTS:
        raise NgramLearningError("readout dimensions exceed the field capacity bound")
    return width, rank


def _coefficients_record(values: np.ndarray) -> dict[str, Any]:
    encoded = np.asarray(values, dtype="<f4", order="C")
    raw = encoded.tobytes(order="C")
    return {
        "data_b64": base64.b64encode(raw).decode("ascii"),
        "dtype": "<f4",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "shape": [int(encoded.shape[0]), int(encoded.shape[1])],
    }


def _make_state(
    model_id: str,
    table_id: str,
    width: int,
    rank: int,
    coefficients: np.ndarray,
    revision: int,
    feedback_history: list[str],
    last_feedback: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema": STATE_SCHEMA,
        "model_id": model_id,
        "table_id": table_id,
        "width": width,
        "rank": rank,
        "revision": revision,
        "coefficients": _coefficients_record(coefficients),
        "feedback_history": list(feedback_history),
        "last_feedback": None if last_feedback is None else dict(last_feedback),
    }


def _decode_state(state: Mapping[str, Any]) -> tuple[dict[str, Any], np.ndarray]:
    required = {
        "schema",
        "model_id",
        "table_id",
        "width",
        "rank",
        "revision",
        "coefficients",
        "feedback_history",
        "last_feedback",
    }
    if not isinstance(state, Mapping) or set(state) != required:
        raise NgramLearningError("readout state keys are invalid")
    if state.get("schema") != STATE_SCHEMA:
        raise NgramLearningError("readout state schema is unsupported")
    model_id = _text(state.get("model_id"), "model_id")
    table_id = _text(state.get("table_id"), "table_id")
    width, rank = _dimensions(state.get("width"), state.get("rank"))
    revision = _integer(state.get("revision"), "readout revision", maximum=(1 << 31) - 1)
    raw_coefficients = state.get("coefficients")
    if not isinstance(raw_coefficients, Mapping) or set(raw_coefficients) != {
        "data_b64", "dtype", "sha256", "shape"
    }:
        raise NgramLearningError("readout coefficients record is invalid")
    if (
        raw_coefficients.get("dtype") != "<f4"
        or raw_coefficients.get("shape") != [width, rank]
        or not isinstance(raw_coefficients.get("data_b64"), str)
    ):
        raise NgramLearningError("readout coefficient layout is unsupported")
    try:
        raw = base64.b64decode(raw_coefficients["data_b64"], validate=True)
    except (TypeError, ValueError) as exc:
        raise NgramLearningError("readout coefficient encoding is invalid") from exc
    if (
        len(raw) != width * rank * 4
        or base64.b64encode(raw).decode("ascii") != raw_coefficients["data_b64"]
        or _digest(raw_coefficients.get("sha256"), "coefficient sha256")
        != hashlib.sha256(raw).hexdigest()
    ):
        raise NgramLearningError("readout coefficient digest or size mismatches")
    coefficients = np.frombuffer(raw, dtype="<f4").reshape(width, rank)
    if not np.isfinite(coefficients).all():
        raise NgramLearningError("readout coefficients contain nonfinite values")
    coefficient_norm = float(np.linalg.norm(coefficients.astype(np.float64)))
    if coefficient_norm > _MAX_COEFFICIENT_NORM + 1e-6:
        raise NgramLearningError("readout coefficients exceed their intervention bound")
    history = state.get("feedback_history")
    if (
        not isinstance(history, list)
        or len(history) > MAX_FEEDBACK_HISTORY
        or any(
            not isinstance(item, str)
            or len(item.encode("utf-8")) > MAX_FEEDBACK_ID_BYTES
            or not item
            for item in history
        )
        or len(history) != len(set(history))
    ):
        raise NgramLearningError("readout feedback history is invalid")
    last_feedback = state.get("last_feedback")
    if last_feedback is not None:
        expected_last = {
            "id",
            "context_sha256",
            "next_token_id",
            "competitor_token_id",
            "advantage",
            "gradient_scale",
        }
        if not isinstance(last_feedback, Mapping) or set(last_feedback) != expected_last:
            raise NgramLearningError("last next-token feedback record is invalid")
        _text(last_feedback.get("id"), "last feedback id", maximum_bytes=MAX_FEEDBACK_ID_BYTES)
        _digest(last_feedback.get("context_sha256"), "last context_sha256")
        _integer(last_feedback.get("next_token_id"), "last next_token_id", maximum=_MAX_TOKEN_ID)
        _integer(last_feedback.get("competitor_token_id"), "last competitor_token_id", maximum=_MAX_TOKEN_ID)
        _real(last_feedback.get("advantage"), "last advantage", minimum=-_MAX_MARGIN, maximum=_MAX_MARGIN)
        _real(last_feedback.get("gradient_scale"), "last gradient_scale", minimum=0.0, maximum=1.0)
        if last_feedback["id"] not in history:
            raise NgramLearningError("last feedback identity is absent from history")
    canonical = _make_state(
        model_id,
        table_id,
        width,
        rank,
        coefficients,
        revision,
        list(history),
        last_feedback,
    )
    return canonical, coefficients


def validate_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and detach a JSON-safe state before placing it in the field."""
    return _decode_state(state)[0]


def state_capacity_words(state: Mapping[str, Any]) -> int:
    """Return the bounded field allocation needed for all feedback history."""
    canonical = validate_state(state)
    required_bytes = len(_canonical_json(canonical)) + _STATE_HISTORY_SLACK_BYTES
    words = (required_bytes + 4 + 3) // 4
    if words > MAX_STATE_CAPACITY_WORDS:
        raise NgramLearningError("readout state exceeds the field allocation limit")
    return words


def initial_state(
    model_id: str,
    table_id: str,
    *,
    width: int = 2048,
    rank: int = 8,
) -> Mapping[str, Any]:
    """Create a zero-output, identity-bound low-rank field readout."""
    model_id = _text(model_id, "model_id")
    table_id = _text(table_id, "table_id")
    width, rank = _dimensions(width, rank)
    coefficients = np.zeros((width, rank), dtype="<f4")
    return _make_state(model_id, table_id, width, rank, coefficients, 0, [], None)


def _input_vector(value: Any, label: str, size: int) -> np.ndarray:
    try:
        raw = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise NgramLearningError(f"{label} must be a numeric vector") from exc
    if raw.ndim != 1 or raw.size != size or raw.dtype.kind not in "fiu":
        raise NgramLearningError(f"{label} must be a finite vector of length {size}")
    result = np.asarray(raw, dtype=np.float64)
    if not np.isfinite(result).all():
        raise NgramLearningError(f"{label} contains nonfinite values")
    return result


def _unit(values: np.ndarray) -> np.ndarray:
    maximum = float(np.max(np.abs(values), initial=0.0))
    if maximum == 0.0:
        return np.zeros(values.shape, dtype=np.float64)
    scaled = values / maximum
    norm = math.sqrt(float(np.dot(scaled, scaled)))
    if not math.isfinite(norm) or norm == 0.0:
        return np.zeros(values.shape, dtype=np.float64)
    return scaled / norm


def _features(table_vector: Any, hidden: Any, width: int, rank: int) -> np.ndarray:
    table = _input_vector(table_vector, "table_vector", TABLE_VECTOR_SIZE)
    hidden_values = _input_vector(hidden, "hidden", width)
    table_unit = _unit(table)
    hidden_unit = _unit(hidden_values)
    features = np.zeros(rank, dtype=np.float64)
    features[0] = 0.5
    context_slots = rank - 1
    table_slots = (context_slots + 1) // 2
    hidden_slots = context_slots - table_slots
    cursor = 1
    for values, slots, weight in ((table_unit, table_slots, 1.0), (hidden_unit, hidden_slots, 0.5)):
        if not slots:
            continue
        projections = np.empty(slots, dtype=np.float64)
        for index in range(slots):
            start = index * values.size // slots
            stop = (index + 1) * values.size // slots
            block = values[start:stop]
            projections[index] = float(np.sum(block, dtype=np.float64)) / math.sqrt(block.size)
        features[cursor:cursor + slots] = weight * _unit(projections)
        cursor += slots
    return _unit(features)


def readout(state: Mapping[str, Any], table_vector: np.ndarray, hidden: np.ndarray) -> np.ndarray:
    """Return a deterministic, bounded float32 residual for one head input."""
    canonical, coefficients = _decode_state(state)
    width, rank = int(canonical["width"]), int(canonical["rank"])
    features = _features(table_vector, hidden, width, rank)
    residual = coefficients.astype(np.float64) @ features
    norm = float(np.linalg.norm(residual))
    if norm > _MAX_RESIDUAL_NORM:
        residual *= _MAX_RESIDUAL_NORM / norm
    return np.asarray(residual, dtype=np.float32)


def _feedback_record(
    feedback: Mapping[str, Any],
    state: Mapping[str, Any],
) -> tuple[dict[str, Any], np.ndarray]:
    required = {
        "schema",
        "id",
        "model_id",
        "table_id",
        "context_sha256",
        "next_token_id",
        "probability_token_id",
        "competitor_token_id",
        "target_direction",
        "advantage",
    }
    if not isinstance(feedback, Mapping) or set(feedback) != required:
        raise NgramLearningError("next-token feedback keys are invalid")
    if feedback.get("schema") != FEEDBACK_SCHEMA:
        raise NgramLearningError("next-token feedback schema is unsupported")
    feedback_id = _text(feedback.get("id"), "feedback id", maximum_bytes=MAX_FEEDBACK_ID_BYTES)
    model_id = _text(feedback.get("model_id"), "feedback model_id")
    table_id = _text(feedback.get("table_id"), "feedback table_id")
    if model_id != state["model_id"] or table_id != state["table_id"]:
        raise NgramLearningError("next-token feedback identity does not match the readout")
    context_sha256 = _digest(feedback.get("context_sha256"), "context_sha256")
    next_token_id = _integer(feedback.get("next_token_id"), "next_token_id", maximum=_MAX_TOKEN_ID)
    probability_token_id = _integer(feedback.get("probability_token_id"), "probability_token_id", maximum=_MAX_TOKEN_ID)
    competitor_token_id = _integer(feedback.get("competitor_token_id"), "competitor_token_id", maximum=_MAX_TOKEN_ID)
    if probability_token_id != next_token_id:
        raise NgramLearningError("measured probability is not for the observed next token")
    if competitor_token_id == next_token_id:
        raise NgramLearningError("next-token competitor must differ from the observed token")
    width = int(state["width"])
    direction_values = _input_vector(feedback.get("target_direction"), "target_direction", width)
    direction = _unit(direction_values)
    if not np.any(direction):
        raise NgramLearningError("target_direction must be nonzero")
    advantage = _real(feedback.get("advantage"), "advantage", minimum=-_MAX_MARGIN, maximum=_MAX_MARGIN)
    # Pairwise logistic loss on the observed token versus its measured runner-up.
    gradient_scale = 1.0 / (1.0 + math.exp(max(-_MAX_MARGIN, min(_MAX_MARGIN, advantage))))
    return (
        {
            "id": feedback_id,
            "context_sha256": context_sha256,
            "next_token_id": next_token_id,
            "competitor_token_id": competitor_token_id,
            "advantage": advantage,
            "gradient_scale": gradient_scale,
        },
        direction,
    )


def learn(
    state: Mapping[str, Any],
    table_vector: np.ndarray,
    hidden: np.ndarray,
    feedback: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Apply one measured pairwise next-token update to field-owned coefficients."""
    canonical, coefficients = _decode_state(state)
    if canonical["revision"] >= (1 << 31) - 1:
        raise NgramLearningError("readout revision is exhausted")
    record, direction = _feedback_record(feedback, canonical)
    history = list(canonical["feedback_history"])
    if record["id"] in history:
        raise NgramLearningError("next-token feedback identity was already applied")
    features = _features(table_vector, hidden, int(canonical["width"]), int(canonical["rank"]))
    updated = coefficients.astype(np.float64, copy=True)
    updated += (
        _LEARNING_RATE
        * float(record["gradient_scale"])
        * np.outer(direction, features)
    )
    norm = float(np.linalg.norm(updated))
    if norm > _MAX_COEFFICIENT_NORM:
        updated *= _MAX_COEFFICIENT_NORM / norm
    updated_f32 = np.asarray(updated, dtype="<f4", order="C")
    # Leave a float32 rounding margin below the invariant enforced on reload.
    norm_f32 = float(np.linalg.norm(updated_f32.astype(np.float64)))
    if norm_f32 > _MAX_COEFFICIENT_NORM:
        updated_f32 *= np.float32(_MAX_COEFFICIENT_NORM / norm_f32)
    history.append(record["id"])
    history = history[-MAX_FEEDBACK_HISTORY:]
    return _make_state(
        str(canonical["model_id"]),
        str(canonical["table_id"]),
        int(canonical["width"]),
        int(canonical["rank"]),
        updated_f32,
        int(canonical["revision"]) + 1,
        history,
        record,
    )
