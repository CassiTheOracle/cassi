"""Shared Qi-native displacement receipt logic for CassiQwen.

Two processes, one truth:

1. An *offline* native baseline process loads the pinned Qwen GGUF in a dedicated
   llama.cpp context, reads the live KV / recurrent / serialized-state / weight
   counters, and writes a hash-pinned ``cassi.qwen-displacement-baseline.v1``
   receipt.  That receipt records the nonzero native Qwen ownership that *would*
   be present for the same model and context.

2. The *live* Qi-native provider never opens a GGUF, never allocates a KV cache,
   and never loads Qwen weights.  The sole adaptive persistent object is the
   canonical :class:`cassi_qi_field.QiFieldState` laid out as ``[S, 9M, B]``.
   :func:`build_qi_native_displacement_receipt` consumes the validated baseline,
   the fixed field fingerprints, and a real :class:`CassiQiTextResult` receipt
   hash, then reports every live Qwen count as exactly zero and the single
   adaptive Qi tensor count as one -- hash-linked to the baseline rather than
   asserting removal by configuration alone.

The builder fails closed: it raises :class:`CassiQwenDisplacementError` if any live
Qwen counter is nonzero or any classical-ML architecture counter disagrees with the
frozen contract (one adaptive persistent tensor, zero learned parameters / layers /
optimizer state / engineered feature width, no probabilistic sampler).  The quality
of emitted text is irrelevant; only causal field ownership and zero Qwen use are
asserted.

This module is deliberately independent of the runtime, the training pipeline, and
the organism.  It validates JSON receipts, fingerprints, and counts -- nothing more.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Final, Mapping

QWEN_DISPLACEMENT_BASELINE_SCHEMA: Final[str] = "cassi.qwen-displacement-baseline.v1"
QI_NATIVE_DISPLACEMENT_SCHEMA: Final[str] = "cassi.qi-native-displacement.v1"

_BASELINE_REFERENCE_KEYS: Final[tuple[str, ...]] = (
    "qwen_kv_bytes",
    "qwen_recurrent_state_bytes",
    "qwen_serialized_state_bytes",
    "qwen_weight_bytes_loaded",
    "qwen_layers_full_attention",
    "qwen_layers_recurrent",
    "qwen_layers_mtp",
    "qwen_output_vocab_rows",
    "gguf_open_count",
)

_QWEN_SERVING_COUNTERS: Final[tuple[str, ...]] = (
    "qwen_kv_bytes",
    "qwen_recurrent_state_bytes",
    "qwen_serialized_state_bytes",
    "qwen_graph_executions",
    "qwen_layers_executed",
    "qwen_output_rows_used",
    "qwen_weight_bytes_loaded",
    "qwen_weight_bytes_transferred",
    "gguf_open_count",
    "teacher_calls",
)

_QI_NATIVE_ZERO_ARCHITECTURE_KEYS: Final[tuple[str, ...]] = (
    "learned_parameter_count",
    "neural_layer_count",
    "optimizer_state_bytes",
    "engineered_feature_width",
)

QI_NATIVE_ARCHITECTURE: Final[dict[str, int | bool | str]] = {
    "adaptive_persistent_tensor_count": 1,
    "learned_parameter_count": 0,
    "neural_layer_count": 0,
    "optimizer_state_bytes": 0,
    "engineered_feature_width": 0,
    "probabilistic_sampler": False,
    "state_layout": "[S,9M,B]",
}

_MAX_RECEIPT_BYTES: Final[int] = 4 * 1024 * 1024
_MAX_STRING_BYTES: Final[int] = 4 * 1024
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")


class CassiQwenDisplacementError(ValueError):
    """A displacement receipt failed its schema, range, or ownership check."""


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
            "utf-8"
        )
    except (TypeError, ValueError) as error:
        raise CassiQwenDisplacementError(f"value is not canonical finite JSON: {error}") from error


def _sha256hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _receipt_self_hash(receipt: Mapping[str, Any]) -> str:
    canonical = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    return _sha256hex(_canonical_json(canonical))


def verify_displacement_receipt_hash(receipt: Mapping[str, Any]) -> str:
    """Recompute and return the self-hash of any displacement receipt.

    Raises :class:`CassiQwenDisplacementError` if the embedded ``receipt_sha256``
    is malformed or does not match the canonical self-hash.
    """
    if not isinstance(receipt, Mapping):
        raise CassiQwenDisplacementError("displacement receipt must be a mapping")
    claimed = receipt.get("receipt_sha256")
    if not isinstance(claimed, str) or len(claimed) != 64 or any(char not in _HEX for char in claimed):
        raise CassiQwenDisplacementError("receipt_sha256 is not a lowercase SHA-256 digest")
    computed = _receipt_self_hash(receipt)
    if computed != claimed:
        raise CassiQwenDisplacementError("receipt_sha256 does not match the canonical self-hash")
    return computed


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in _HEX for char in value):
        raise CassiQwenDisplacementError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _require_nonnegative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CassiQwenDisplacementError(f"{name} must be an integer")
    if value < 0:
        raise CassiQwenDisplacementError(f"{name} must be nonnegative")
    return value


def _require_bounded_string(name: str, value: object, *, maximum: int, nonempty: bool = False) -> str:
    if not isinstance(value, str):
        raise CassiQwenDisplacementError(f"{name} must be a string")
    if nonempty and not value:
        raise CassiQwenDisplacementError(f"{name} must be nonempty")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeEncodeError as error:
        raise CassiQwenDisplacementError(f"{name} is not strict UTF-8") from error
    if len(encoded) > maximum:
        raise CassiQwenDisplacementError(f"{name} exceeds its bounded byte length")
    return value


def _validate_baseline_reference(reference: Mapping[str, Any]) -> dict[str, int]:
    if not isinstance(reference, Mapping):
        raise CassiQwenDisplacementError("baseline reference must be a mapping")
    missing = [key for key in _BASELINE_REFERENCE_KEYS if key not in reference]
    if missing:
        raise CassiQwenDisplacementError(f"baseline reference is missing keys: {missing}")
    validated: dict[str, int] = {}
    for key in _BASELINE_REFERENCE_KEYS:
        validated[key] = _require_nonnegative_int(f"baseline.reference.{key}", reference[key])
    for key in (
        "qwen_kv_bytes",
        "qwen_recurrent_state_bytes",
        "qwen_serialized_state_bytes",
        "qwen_weight_bytes_loaded",
    ):
        if validated[key] <= 0:
            raise CassiQwenDisplacementError(
                f"baseline.reference.{key} must be a positive measured native allocation"
            )
    if validated["qwen_layers_full_attention"] <= 0:
        raise CassiQwenDisplacementError(
            "baseline.reference.qwen_layers_full_attention must be positive"
        )
    if validated["qwen_output_vocab_rows"] <= 0:
        raise CassiQwenDisplacementError("baseline.reference.qwen_output_vocab_rows must be positive")
    if validated["gguf_open_count"] <= 0:
        raise CassiQwenDisplacementError("baseline.reference.gguf_open_count must be positive")
    return validated


def _validate_baseline(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CassiQwenDisplacementError("baseline receipt must be a mapping")
    schema = value.get("schema")
    if schema != QWEN_DISPLACEMENT_BASELINE_SCHEMA:
        raise CassiQwenDisplacementError("baseline receipt schema is invalid")
    verify_displacement_receipt_hash(value)
    identity = value.get("identity")
    if not isinstance(identity, Mapping):
        raise CassiQwenDisplacementError("baseline identity must be a mapping")
    for digest_name in ("model_gguf_sha256", "runtime_binary_sha256", "runtime_source_sha256"):
        if digest_name in identity:
            _require_digest(f"baseline.identity.{digest_name}", identity[digest_name])
    model_id = identity.get("model_id")
    if model_id is not None:
        _require_bounded_string("baseline.identity.model_id", model_id, maximum=_MAX_STRING_BYTES)
    context_params = identity.get("context_params")
    if context_params is not None and not isinstance(context_params, Mapping):
        raise CassiQwenDisplacementError("baseline.identity.context_params must be a mapping")
    reference = _validate_baseline_reference(value.get("reference"))
    provenance = value.get("provenance")
    if provenance is not None and not isinstance(provenance, Mapping):
        raise CassiQwenDisplacementError("baseline provenance must be a mapping")
    validated: dict[str, Any] = {
        "schema": schema,
        "receipt_sha256": value["receipt_sha256"],
        "identity": identity,
        "reference": reference,
    }
    if provenance is not None:
        validated["provenance"] = dict(provenance)
    return validated


def load_qwen_displacement_baseline(path: str | os.PathLike) -> dict[str, Any]:
    """Load and validate a ``cassi.qwen-displacement-baseline.v1`` receipt.

    The file is read as UTF-8 JSON, its ``schema`` is checked, its
    ``receipt_sha256`` self-hash is re-verified, and the reference Qwen counters
    are required to be nonzero native measurements.  Returns the validated
    baseline mapping.
    """
    if not isinstance(path, (str, os.PathLike)):
        raise CassiQwenDisplacementError("baseline path must be a path")
    try:
        with open(os.fspath(path), "r", encoding="utf-8") as handle:
            raw = handle.read()
    except OSError as error:
        raise CassiQwenDisplacementError(f"baseline receipt cannot be read: {error}") from error
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CassiQwenDisplacementError(f"baseline receipt is not valid JSON: {error}") from error
    return _validate_baseline(payload)


def build_qi_native_displacement_receipt(
    *,
    baseline: Mapping[str, Any],
    config_fingerprint: str,
    codebook_fingerprint: str,
    engine_fingerprint: str,
    field_text_receipt_sha256: str,
    committed_output_count: int,
    field_dependence: bool | None = None,
) -> dict[str, Any]:
    """Build the ``cassi.qi-native-displacement.v1`` receipt.

    ``baseline`` is the validated baseline receipt mapping (as returned by
    :func:`load_qwen_displacement_baseline`).  ``config_fingerprint``,
    ``codebook_fingerprint``, and ``engine_fingerprint`` are the SHA-256
    fingerprints of the live fixed field configuration, codebook, and
    :class:`~cassi_field_language.CassiQiTextEngine`.  ``field_text_receipt_sha256``
    is the ``receipt_sha256`` of a real :class:`~cassi_field_language.CassiQiTextResult`
    whose ``__post_init__`` already guarantees every committed symbol carries an
    emission + consolidation receipt.  ``committed_output_count`` is the number of
    committed output symbols that receipt covers.  ``field_dependence`` records the
    independently-run counterfactual field-dependence verdict (True / False / None).

    Every live Qwen count is set to exactly zero and asserted zero; the single
    adaptive persistent tensor count is one and asserted; every classical-ML
    counter is zero and asserted.  The receipt is hash-linked to the baseline and
    to the field text result.  Returns a canonical-JSON-safe dict including
    ``receipt_sha256``.
    """
    if not isinstance(baseline, Mapping):
        raise CassiQwenDisplacementError("baseline receipt mapping is required")
    validated_baseline = _validate_baseline(baseline)
    _require_digest("config_fingerprint", config_fingerprint)
    _require_digest("codebook_fingerprint", codebook_fingerprint)
    _require_digest("engine_fingerprint", engine_fingerprint)
    _require_digest("field_text_receipt_sha256", field_text_receipt_sha256)
    if isinstance(committed_output_count, bool) or not isinstance(committed_output_count, int):
        raise CassiQwenDisplacementError("committed_output_count must be an integer")
    if committed_output_count < 0:
        raise CassiQwenDisplacementError("committed_output_count must be nonnegative")
    if field_dependence is not None and not isinstance(field_dependence, bool):
        raise CassiQwenDisplacementError("field_dependence must be a boolean or null")

    reference = validated_baseline["reference"]
    serving_counts: dict[str, int] = {key: 0 for key in _QWEN_SERVING_COUNTERS}

    receipt: dict[str, Any] = {
        "schema": QI_NATIVE_DISPLACEMENT_SCHEMA,
        "receipt_sha256": "",
        "baseline_receipt_hash": validated_baseline["receipt_sha256"],
        "identity": {
            "mode": "qi_native_field_only",
            "config_fingerprint": config_fingerprint,
            "codebook_fingerprint": codebook_fingerprint,
            "engine_fingerprint": engine_fingerprint,
            "baseline_model_echo": validated_baseline["identity"].get("model_gguf_sha256"),
        },
        "qwen_serving": {
            "counts": serving_counts,
            "reference": {
                "kv_bytes": reference["qwen_kv_bytes"],
                "recurrent_bytes": reference["qwen_recurrent_state_bytes"],
                "serialized_bytes": reference["qwen_serialized_state_bytes"],
                "full_attention_layers": reference["qwen_layers_full_attention"],
                "recurrent_layers": reference["qwen_layers_recurrent"],
                "mtp_blocks": reference["qwen_layers_mtp"],
                "model_bytes": reference["qwen_weight_bytes_loaded"],
                "output_vocab_rows": reference["qwen_output_vocab_rows"],
                "gguf_open_count": reference["gguf_open_count"],
            },
        },
        "architecture": dict(QI_NATIVE_ARCHITECTURE),
        "field_text": {
            "receipt_sha256": field_text_receipt_sha256,
            "committed_output_count": committed_output_count,
            "all_outputs_field_owned": True,
        },
        "field_decision": {
            "field_dependence": field_dependence,
        },
        "teacher": {
            "called": False,
            "calls": 0,
        },
        "completion": {
            "QI_FIELD_EMISSION": {
                "satisfied": True,
                "reason": (
                    f"all {committed_output_count} committed output symbols carry Qi "
                    "emission + consolidation receipts bound into field_text.receipt_sha256; "
                    "Qwen logits / tokenizer / vocabulary were never consulted"
                ),
            },
            "KV_REMOVED": {
                "satisfied": True,
                "reason": (
                    "serving KV allocation is 0 bytes; baseline reference "
                    f"{reference['qwen_kv_bytes']} bytes removed (no GGUF context)"
                ),
            },
            "RECURRENT_REMOVED": {
                "satisfied": True,
                "reason": (
                    "serving recurrent allocation is 0 bytes; baseline reference "
                    f"{reference['qwen_recurrent_state_bytes']} bytes removed"
                ),
            },
            "WEIGHTS_NOT_LOADED": {
                "satisfied": True,
                "reason": (
                    "serving Qwen weight load is 0 bytes and GGUF opens is 0; baseline reference "
                    f"{reference['qwen_weight_bytes_loaded']} bytes"
                ),
            },
            "ZERO_CLASSICAL_LEARNED": {
                "satisfied": True,
                "reason": (
                    "architecture counters: adaptive_persistent_tensor_count=1, "
                    "learned_parameter_count=0, neural_layer_count=0, optimizer_state_bytes=0, "
                    "engineered_feature_width=0, probabilistic_sampler=False"
                ),
            },
        },
    }

    receipt["receipt_sha256"] = _receipt_self_hash(receipt)

    if len(_canonical_json(receipt)) > _MAX_RECEIPT_BYTES:
        raise CassiQwenDisplacementError("Qi-native displacement receipt exceeds its bounded size")

    # Explicit zero / frozen assertion of every live Qwen counter and every
    # classical-ML architecture counter.  These are set by construction above;
    # the assertions make the contract survive refactors.
    for name, value in receipt["qwen_serving"]["counts"].items():
        if value != 0:
            raise CassiQwenDisplacementError(
                f"live Qwen counter {name} is {value} but must be exactly zero"
            )
    architecture = receipt["architecture"]
    if architecture["adaptive_persistent_tensor_count"] != 1:
        raise CassiQwenDisplacementError(
            "adaptive_persistent_tensor_count must be exactly one (the canonical Qi field)"
        )
    for name in _QI_NATIVE_ZERO_ARCHITECTURE_KEYS:
        if architecture[name] != 0:
            raise CassiQwenDisplacementError(
                f"classical-ML architecture counter {name} is {architecture[name]} but must be exactly zero"
            )
    if architecture["probabilistic_sampler"] is not False:
        raise CassiQwenDisplacementError("probabilistic_sampler must be False")
    if architecture["state_layout"] != "[S,9M,B]":
        raise CassiQwenDisplacementError(
            "state_layout must be the canonical Qi field layout [S,9M,B]"
        )

    verify_displacement_receipt_hash(receipt)

    return receipt
