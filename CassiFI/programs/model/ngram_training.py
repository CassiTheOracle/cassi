"""Measured next-token feedback for the owner-held Qwen n-gram readout.

The ordinary margin comes from an actual resident head snapshot.  Later
margins on that frozen hidden state are projections through the same output
normalization and two unembedding rows; only another resident pass measures
what the evolving owner and model actually produce.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping, Sequence

import numpy as np

from .ngram_learning import FEEDBACK_SCHEMA, readout


def _vector(value: Any, size: int, name: str) -> np.ndarray:
    values = np.asarray(value)
    if values.ndim != 1 or values.size != size or values.dtype.kind not in "fiu":
        raise ValueError(f"{name} must be a numeric vector of length {size}")
    result = np.asarray(values, dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} contains nonfinite values")
    return result


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _head_margin(
    hidden: np.ndarray,
    output_norm: np.ndarray,
    row_difference: np.ndarray,
) -> float:
    scale = math.sqrt(float(np.mean(hidden * hidden)) + 1e-6)
    return float(np.dot(row_difference * output_norm, hidden / scale))


def margin_with_readout(
    state: Mapping[str, Any],
    table_vector: np.ndarray,
    hidden: np.ndarray,
    baseline_margin: float,
    *,
    output_norm: np.ndarray,
    target_row: np.ndarray,
    competitor_row: np.ndarray,
) -> float:
    """Project a fixed-context target margin using the live head's two rows.

    The baseline is the measured logit difference.  Computing only the change
    through the readout preserves that baseline, including native quantization
    and rounding differences between a CPU row reconstruction and Vulkan.
    """
    width = int(state["width"])
    source = _vector(hidden, width, "hidden")
    norm = _vector(output_norm, width, "output_norm")
    difference = _vector(target_row, width, "target_row") - _vector(
        competitor_row, width, "competitor_row"
    )
    measured = _finite(baseline_margin, "baseline_margin")
    residual = _vector(readout(state, table_vector, hidden), width, "readout")
    projected = measured + _head_margin(source + residual, norm, difference) - _head_margin(
        source, norm, difference
    )
    if not math.isfinite(projected):
        raise ValueError("projected margin is nonfinite")
    return projected


def make_next_token_feedback(
    *,
    feedback_id: str,
    model_id: str,
    table_id: str,
    context_tokens: Sequence[int],
    next_token_id: int,
    competitor_token_id: int,
    advantage: float,
    hidden: np.ndarray,
    output_norm: np.ndarray,
    target_row: np.ndarray,
    competitor_row: np.ndarray,
) -> dict[str, Any]:
    """Construct the canonical pairwise observation for field-owned learning."""
    if not isinstance(feedback_id, str) or not feedback_id or len(feedback_id.encode("utf-8")) > 128:
        raise ValueError("feedback_id must be bounded nonempty text")
    if not isinstance(model_id, str) or not model_id or not isinstance(table_id, str) or not table_id:
        raise ValueError("model and table identity must be nonempty")
    if isinstance(context_tokens, (str, bytes)) or not context_tokens:
        raise ValueError("context_tokens must be nonempty")
    if any(isinstance(token, bool) or not isinstance(token, (int, np.integer)) or token < 0 or token > 0xffffffff for token in context_tokens):
        raise ValueError("context_tokens must be uint32 IDs")
    for token_id in (next_token_id, competitor_token_id):
        if isinstance(token_id, bool) or not isinstance(token_id, (int, np.integer)) or token_id < 0 or token_id > (1 << 31) - 1:
            raise ValueError("next-token IDs must be nonnegative signed integers")
    if next_token_id == competitor_token_id:
        raise ValueError("target and competitor must differ")
    margin = _finite(advantage, "advantage")
    if abs(margin) > 80.0:
        raise ValueError("advantage exceeds the feedback margin bound")
    source = np.asarray(hidden)
    if source.ndim != 1:
        raise ValueError("hidden must be a vector")
    width = int(source.size)
    x = _vector(source, width, "hidden")
    norm = _vector(output_norm, width, "output_norm")
    difference = _vector(target_row, width, "target_row") - _vector(
        competitor_row, width, "competitor_row"
    )
    weighted = difference * norm
    scale = math.sqrt(float(np.mean(x * x)) + 1e-6)
    derivative = weighted / scale - x * (float(np.dot(weighted, x)) / (width * scale**3))
    if not np.isfinite(derivative).all() or not np.any(derivative):
        raise ValueError("head margin has no finite update direction")
    tokens = np.asarray(context_tokens, dtype="<u4")
    return {
        "schema": FEEDBACK_SCHEMA,
        "id": feedback_id,
        "model_id": model_id,
        "table_id": table_id,
        "context_sha256": hashlib.sha256(tokens.tobytes()).hexdigest(),
        "next_token_id": int(next_token_id),
        "probability_token_id": int(next_token_id),
        "competitor_token_id": int(competitor_token_id),
        "target_direction": np.asarray(derivative, dtype=np.float32).tolist(),
        "advantage": margin,
    }
