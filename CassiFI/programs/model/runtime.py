"""Bounded field-owned model graph execution.

The runtime keeps graph control, activations, attention/recurrent memory,
sampling, branches, and external-lane waits in a canonical JSON continuation.
Fixed tensor primitives implement mechanics only; the admitted graph determines
composition and no opaque host model call is labelled resident execution.
"""
from __future__ import annotations

import copy
import json
import math
import struct
from typing import Any, Mapping, MutableMapping, Sequence

from programs.python.records import ModelContinuation, TensorView, canonical_json_bytes, digest_value

from .records import MODEL_PACKAGE_SCHEMA, ModelPackage, ModelRecordError


RUNTIME_SCHEMA = "cassifi.field-model-runtime.v1"
RESULT_SCHEMA = "cassifi.field-model-result.v1"
RESIDENT_STAGE_REQUEST_SCHEMA = "cassifi.resident-model-stage-request.v1"
RESIDENT_STAGE_RESULT_SCHEMA = "cassifi.resident-model-stage-result.v1"
RESIDENT_STAGE_WAIT_REASON = "resident-model-stage"
RESIDENT_PREFIX_REUSE_SCHEMA = "cassifi.resident-qwen-prefix-reuse.v1"
# Largest number of consecutive native tokens one owner round may admit.
NATIVE_TOKEN_RUN_MAX = 8
# Largest number of consecutive resident prompt positions one owner round may
# admit. A block ends early at any head that sampled, so a generated token
# still takes its own round.
RESIDENT_PROMPT_BLOCK_MAX = 8
RESIDENT_PREFIX_SNAPSHOT_WINDOW = 64
DEFAULT_LIMITS = {
    "max_tensor_elements": 1_048_576,
    "max_attention_positions": 32_768,
    "max_new_tokens": 4_096,
    "max_branches": 128,
    "max_events": 4_096,
    "max_pending_operations": 8,
    "panel_rows": 8,
}


class ModelRuntimeError(ValueError):
    """Invalid model state, control request, or graph operation."""


def _plain(value: Any) -> Any:
    try:
        return json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ModelRuntimeError("model runtime value is not canonical JSON") from exc


def _positive(value: Any, label: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModelRuntimeError(f"{label} must be an integer")
    if value < (0 if allow_zero else 1):
        raise ModelRuntimeError(f"{label} is outside its bound")
    return value


def _limit(state: Mapping[str, Any], name: str) -> int:
    limits = state.get("limits")
    if not isinstance(limits, Mapping) or name not in limits:
        raise ModelRuntimeError(f"model limit {name!r} is unavailable")
    return _positive(limits[name], f"model limit {name}")



_EVENT_WINDOW = 256
"""Events retained in state after an advance; the advance returns its own.

The host records each advance's events in its own ledger, so holding a whole
generation's worth inside the state only made every later dispatch copy and
encode them again.  Retention is applied after the advance has taken its own
events, so trimming can never hide events from the caller.
"""


def _retain_events(state: Mapping[str, Any]) -> None:
    retention = min(_limit(state, "max_events"), _EVENT_WINDOW)
    events = state["events"]
    if len(events) > retention:
        del events[: len(events) - retention]


def _event(state: MutableMapping[str, Any], kind: str, payload: Mapping[str, Any]) -> None:
    if len(state["events"]) >= _limit(state, "max_events"):
        del state["events"][0]
    sequence = int(state["counters"]["event"])
    state["counters"]["event"] = sequence + 1
    state["events"].append(
        {
            "schema": "cassifi.model-event.v1",
            "sequence": sequence,
            "kind": kind,
            "payload": _plain(payload),
            "revision": int(state["ledger"]["transitions"]),
        }
    )


def _shape(payload: Mapping[str, Any]) -> tuple[int, ...]:
    return tuple(int(item) for item in payload["view"]["shape"])


def _dequantized(payload: Mapping[str, Any]) -> list[float]:
    values = payload.get("values")
    if values is None:
        raise ModelRuntimeError("tensor backing is not resident in this placement")
    dtype = str(payload["view"]["dtype"])
    if dtype == "q8_0":
        layout = payload["view"].get("quantization_layout") or {}
        scale = float(layout["scale"])
        zero = int(layout.get("zero_point", 0))
        return [(int(value) - zero) * scale for value in values]
    return [float(value) for value in values]


def _tensor(state: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if name == "$token":
        return {
            "view": {"shape": [1], "dtype": "i64"},
            "values": [int(state["current_token"])],
        }
    if name == "$position":
        return {
            "view": {"shape": [1], "dtype": "i64"},
            "values": [int(state["continuation"]["token_position"])],
        }
    payload = state["tensors"].get(name)
    if not isinstance(payload, Mapping):
        raise ModelRuntimeError(f"model tensor {name!r} is unavailable")
    return payload


def _activation_payload(
    state: Mapping[str, Any],
    name: str,
    values: Sequence[int | float],
    shape: Sequence[int],
    *,
    dtype: str = "f64",
) -> Mapping[str, Any]:
    shape_tuple = tuple(int(item) for item in shape)
    if not shape_tuple or math.prod(shape_tuple) != len(values):
        raise ModelRuntimeError("activation shape does not match its values")
    if len(values) > _limit(state, "max_tensor_elements"):
        raise ModelRuntimeError("activation exceeds tensor element limit")
    old = state["tensors"].get(name)
    version = 1
    if isinstance(old, Mapping):
        version = int(old["view"].get("mutable_version") or 0) + 1
    strides: list[int] = []
    stride = 1
    for extent in reversed(shape_tuple):
        strides.append(stride)
        stride *= extent
    view = TensorView(
        tensor_id=f"{state['identity']['operation_id']}:{name}",
        owner_id=str(state["identity"]["owner_id"]),
        scope_id=str(state["identity"]["scope_id"]),
        shape=shape_tuple,
        dtype=dtype,
        strides=tuple(reversed(strides)),
        quantization_layout=None,
        backing_sha256=None,
        mutable_version=version,
        rights=("read", "write"),
        dependencies=(str(state["package_sha256"]),),
    )
    normalized: list[int | float] = []
    for value in values:
        number: int | float = int(value) if dtype.startswith(("i", "u")) else float(value)
        if isinstance(number, float) and not math.isfinite(number):
            raise ModelRuntimeError("model operation produced a non-finite value")
        normalized.append(number)
    return {
        "schema": "cassifi.model-tensor-payload.v1",
        "view": view.as_dict(),
        "values": normalized,
        "values_sha256": digest_value(normalized),
        "placement": state["placement"]["actual"],
    }


def _store(
    state: MutableMapping[str, Any],
    name: str | None,
    values: Sequence[int | float],
    shape: Sequence[int],
    *,
    dtype: str = "f64",
) -> None:
    if name is None:
        raise ModelRuntimeError("model operation requires an output")
    state["tensors"][name] = _activation_payload(state, name, values, shape, dtype=dtype)
    state["continuation"]["live_activation_refs"] = sorted(
        key for key in state["tensors"] if key not in state["immutable_tensors"]
    )


def _vector(payload: Mapping[str, Any]) -> list[float]:
    shape = _shape(payload)
    if len(shape) != 1:
        raise ModelRuntimeError("operation requires a vector")
    return _dequantized(payload)


def _binary_values(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> tuple[list[float], list[float], tuple[int, ...]]:
    a, b = _dequantized(left), _dequantized(right)
    shape_a, shape_b = _shape(left), _shape(right)
    if shape_a == shape_b:
        return a, b, shape_a
    if len(a) == 1:
        return a * len(b), b, shape_b
    if len(b) == 1:
        return a, b * len(a), shape_a
    raise ModelRuntimeError("tensor operands have incompatible shapes")


def _softmax(values: Sequence[float], temperature: float = 1.0) -> list[float]:
    if not values:
        raise ModelRuntimeError("softmax input is empty")
    if not math.isfinite(temperature) or temperature <= 0.0:
        raise ModelRuntimeError("sampling temperature must be positive")
    maximum = max(values)
    weights = [math.exp((value - maximum) / temperature) for value in values]
    total = sum(weights)
    if not math.isfinite(total) or total <= 0.0:
        raise ModelRuntimeError("softmax normalization failed")
    return [value / total for value in weights]


def _rng_uniform(state: MutableMapping[str, Any]) -> float:
    mask = (1 << 64) - 1
    x = int(state["continuation"]["rng_state"]["state"])
    x ^= (x >> 12) & mask
    x ^= (x << 25) & mask
    x ^= (x >> 27) & mask
    x &= mask
    state["continuation"]["rng_state"]["state"] = str(x)
    value = (x * 2685821657736338717) & mask
    return value / float(1 << 64)


def _sample_token(
    state: MutableMapping[str, Any], logits: Sequence[float]
) -> tuple[int, Mapping[str, Any]]:
    sampler = state["continuation"]["sampler_state"]
    mode = str(sampler.get("mode", "greedy"))
    if mode == "greedy":
        token = max(range(len(logits)), key=lambda index: (logits[index], -index))
        return token, {"mode": mode, "probability": None}
    if mode != "categorical":
        raise ModelRuntimeError("sampler mode is unsupported")
    probabilities = _softmax(logits, float(sampler.get("temperature", 1.0)))
    top_k = int(sampler.get("top_k", 0))
    if top_k > 0 and top_k < len(probabilities):
        selected = sorted(range(len(probabilities)), key=lambda index: probabilities[index], reverse=True)[:top_k]
        allowed = set(selected)
        probabilities = [value if index in allowed else 0.0 for index, value in enumerate(probabilities)]
        total = sum(probabilities)
        probabilities = [value / total for value in probabilities]
    draw = _rng_uniform(state)
    cumulative = 0.0
    token = len(probabilities) - 1
    for index, probability in enumerate(probabilities):
        cumulative += probability
        if draw < cumulative:
            token = index
            break
    return token, {"mode": mode, "probability": probabilities[token], "draw": draw}


def _apply_pending_deltas(state: MutableMapping[str, Any]) -> None:
    for delta in state["continuation"]["pending_deltas"]:
        kind = delta["kind"]
        name = str(delta["name"])
        if kind == "attention-append":
            memory = state["memory"]["attention"].setdefault(name, [])
            memory.append({"key": list(delta["key"]), "value": list(delta["value"]), "position": int(delta["position"])})
            limit = _limit(state, "max_attention_positions")
            if len(memory) > limit:
                del memory[: len(memory) - limit]
        elif kind == "recurrent-write":
            state["memory"]["recurrent"][name] = list(delta["value"])
        elif kind == "convolution-write":
            state["memory"]["convolution"][name] = [list(row) for row in delta["value"]]
        else:
            raise ModelRuntimeError("pending model delta is invalid")
    state["continuation"]["pending_deltas"] = []
    state["continuation"]["attention_roots"] = [
        f"{name}:{digest_value(value)}"
        for name, value in sorted(state["memory"]["attention"].items())
    ]
    state["continuation"]["recurrent_roots"] = [
        f"{name}:{digest_value(value)}"
        for name, value in sorted(state["memory"]["recurrent"].items())
    ]


def _complete_token(
    state: MutableMapping[str, Any],
    token: int,
    sample: Mapping[str, Any],
    *,
    force_stop: bool = False,
) -> None:
    speculation = state.get("speculation")
    disposition: Mapping[str, Any] | None = None
    if isinstance(speculation, MutableMapping) and speculation.get("status") == "active":
        draft = speculation["draft_tokens"]
        index = int(speculation["cursor"])
        proposed = int(draft[index]) if index < len(draft) else None
        accepted = proposed == token
        if accepted:
            speculation["accepted_tokens"].append(token)
            speculation["cursor"] = index + 1
            if index + 1 >= len(draft):
                speculation["status"] = "accepted"
        else:
            speculation["rejected_tokens"] = list(draft[index:])
            speculation["status"] = "rejected"
        disposition = {
            "proposed": proposed,
            "target": token,
            "accepted": accepted,
            "prefix_position": int(state["continuation"]["token_position"]),
            "mode": str(sample.get("mode", "")),
            "draw": sample.get("draw"),
            "source": speculation.get("source"),
            "verification_lane": speculation.get("verification_lane"),
            "request_sha256": speculation.get("verified_head_sha256"),
        }
    _apply_pending_deltas(state)
    state["generated_tokens"].append(token)
    state["current_token"] = token
    state["continuation"]["token_position"] = int(state["continuation"]["token_position"]) + 1
    state["continuation"]["block_cursor"] = 0
    state["continuation"]["operation_cursor"] = 0
    state["graph_cursor"] = 0
    state["active_operation"] = None
    state["ledger"]["tokens"] += 1
    _event(
        state,
        "token-committed",
        {"token": token, "sample": sample, "speculation": disposition},
    )
    stop_tokens = set(int(item) for item in state["request"]["stop_tokens"])
    if force_stop or token in stop_tokens or len(state["generated_tokens"]) >= int(state["request"]["max_new_tokens"]):
        state["phase"] = "completed"
        state["result"] = {
            "schema": RESULT_SCHEMA,
            "status": "completed",
            "program_id": state["package"]["program"]["program_id"],
            "tokens": list(state["generated_tokens"]),
            "placement": _plain(state["placement"]),
            "logical_work": int(state["ledger"]["transitions"]) + 1,
            "speculation": _plain(state.get("speculation")),
            "field_policies": _policy_summary(state),
        }


def _start_external(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    if state["branch_stack"]:
        raise ModelRuntimeError("hypothetical model branches cannot dispatch external work")
    operation_id = f"model-external-{state['counters']['operation']}"
    state["counters"]["operation"] += 1
    request = {
        "schema": "cassifi.external-model-request.v1",
        "operation_id": operation_id,
        "adapter": operation["parameters"].get("adapter", "field-brain"),
        "model_program_id": state["package"]["program"]["program_id"],
        "prompt_tokens": list(state["request"]["prompt_tokens"]),
        "max_new_tokens": int(state["request"]["max_new_tokens"]),
        "sampler": _plain(state["continuation"]["sampler_state"]),
        "attribution": "external-model-lane",
    }
    state["operations"][operation_id] = {
        "phase": "proposed",
        "request": request,
        "result": None,
    }
    state["phase"] = "waiting"
    state["wait_reason"] = "external-model-result"
    state["await_target"] = operation_id
    _event(state, "external-model-proposed", request)

def _resident_qwen_graph(state: Mapping[str, Any]) -> bool:
    graph = state["package"]["graph"]
    return bool(graph) and all(
        operation.get("op") in {
            "qwen-embedding", "qwen-attention", "qwen-attention-route",
            "qwen-route", "qwen-experts", "qwen-ffn", "qwen-layer",
            "qwen-head",
        }
        for operation in graph
    )


def _resident_snapshot(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ModelRuntimeError("resident stage snapshot must be a mapping")
    # Descriptors identify immutable backing; payload arrays belong to the
    # executor/state store and must never be copied into canonical JSON state.
    if any(key in value for key in ("values", "array", "data", "bytes")):
        raise ModelRuntimeError("resident stage snapshot contains mutable payload")
    try:
        descriptor = _plain(value)
    except ModelRuntimeError:
        raise
    if not isinstance(descriptor, dict):
        raise ModelRuntimeError("resident stage snapshot is not canonical")
    return descriptor


def _record_resident_prefix_snapshot(
    state: MutableMapping[str, Any],
    *,
    position: int,
    token: int,
    snapshot: Any,
    head_executed: bool,
) -> None:
    resident = state.get("resident_model")
    prompt_tokens = state.get("request", {}).get("prompt_tokens", ())
    if (
        not isinstance(resident, MutableMapping)
        or not isinstance(prompt_tokens, list)
        or position < 0
        or position >= len(prompt_tokens)
        or prompt_tokens[position] != token
    ):
        return
    descriptor = _resident_snapshot(snapshot)
    if not descriptor:
        return
    rows = resident.setdefault("prefix_snapshots", [])
    if not isinstance(rows, list):
        raise ModelRuntimeError("resident prompt-prefix snapshot index is invalid")
    row = {
        "position": position,
        "token": token,
        "snapshot": descriptor,
        "head_executed": bool(head_executed),
    }
    if rows and rows[-1].get("position") == position:
        rows[-1] = row
    else:
        rows.append(row)
    if len(rows) > RESIDENT_PREFIX_SNAPSHOT_WINDOW:
        del rows[: len(rows) - RESIDENT_PREFIX_SNAPSHOT_WINDOW]


def seed_resident_prefix(
    state: MutableMapping[str, Any],
    resident_prefix: Mapping[str, Any],
) -> bool:
    """Start a cold resident task at an exact, field-bound prompt boundary."""
    if (
        not isinstance(state, MutableMapping)
        or state.get("schema") != RUNTIME_SCHEMA
        or not isinstance(resident_prefix, Mapping)
        or not _resident_qwen_graph(state)
        or state.get("phase") != "running"
        or int(state.get("graph_cursor", -1)) != 0
    ):
        return False
    request = state.get("request")
    resident = state.get("resident_model")
    continuation = state.get("continuation")
    if (
        not isinstance(request, MutableMapping)
        or not isinstance(resident, MutableMapping)
        or not isinstance(continuation, MutableMapping)
        or int(resident.get("token_index", -1)) != 0
        or int(continuation.get("token_position", -1)) != 0
        or state.get("generated_tokens")
    ):
        return False
    try:
        tokens = [
            _positive(value, "prompt token", allow_zero=True)
            for value in request.get("prompt_tokens", ())
        ]
        count = _positive(resident_prefix.get("prefix_token_count"), "prefix token count")
        position = _positive(resident_prefix.get("position"), "prefix position", allow_zero=True)
        token = _positive(resident_prefix.get("token"), "prefix token", allow_zero=True)
        source_sha256 = str(resident_prefix.get("source_sha256", ""))
        backend = resident_prefix.get("backend")
        conversation_id = resident_prefix.get("conversation_id")
        field_epoch_sha256 = str(resident_prefix.get("field_epoch_sha256", ""))
        prefix_sha256 = str(resident_prefix.get("prefix_sha256", ""))
        descriptor = _resident_snapshot(resident_prefix.get("snapshot"))
    except (ModelRuntimeError, TypeError, ValueError):
        return False
    if (
        not descriptor
        or resident_prefix.get("schema") != RESIDENT_PREFIX_REUSE_SCHEMA
        or count >= len(tokens)
        or position != count - 1
        or token != tokens[position]
        or source_sha256 != resident.get("source_sha256")
        or not isinstance(backend, str)
        or not backend
        or not isinstance(conversation_id, str)
        or not conversation_id
        or len(conversation_id.encode("utf-8")) > 512
        or resident_prefix.get("head_executed") is not False
        or not isinstance(field_epoch_sha256, str)
        or len(field_epoch_sha256) != 64
        or any(character not in "0123456789abcdef" for character in field_epoch_sha256)
        or not isinstance(prefix_sha256, str)
        or prefix_sha256 != digest_value(tokens[:count])
    ):
        return False
    graph = state["package"]["graph"]
    numerical_stages_per_token = len(graph) - sum(
        1 for operation in graph if operation.get("op") == "qwen-head"
    )
    if numerical_stages_per_token < 1:
        return False
    metadata = {
        "schema": RESIDENT_PREFIX_REUSE_SCHEMA,
        "conversation_id": conversation_id,
        "source_sha256": source_sha256,
        "backend": backend,
        "prefix_token_count": count,
        "prefix_sha256": prefix_sha256,
        "position": position,
        "token": token,
        "head_executed": False,
        "field_epoch_sha256": field_epoch_sha256,
        "reused_stage_count": count * numerical_stages_per_token,
    }
    request["prefix_reuse"] = {**metadata, "snapshot": descriptor}
    resident["snapshot"] = descriptor
    resident["prefix_reuse"] = metadata
    resident["token_index"] = count
    resident["position"] = count
    resident["stage_cursor"] = 0
    continuation["token_position"] = count
    state["current_token"] = tokens[count]
    state["graph_cursor"] = 0
    _record_resident_prefix_snapshot(
        state,
        position=position,
        token=token,
        snapshot=descriptor,
        head_executed=False,
    )
    _event(
        state,
        "resident-model-prefix-reused",
        {
            "prefix_token_count": count,
            "reused_stage_count": metadata["reused_stage_count"],
            "source_sha256": source_sha256,
            "backend": backend,
            "conversation_identity_sha256": digest_value(conversation_id),
            "field_epoch_sha256": field_epoch_sha256,
        },
    )
    continuation["checkpoint_sha256"] = digest_value(_snapshot(state))
    canonical_json_bytes(state)
    return True


def _elide_prompt_head(
    state: MutableMapping[str, Any],
    operation: Mapping[str, Any],
) -> bool:
    """Advance a non-sampling prompt head whose numerical action is identity."""

    resident = state.get("resident_model")
    if not isinstance(resident, MutableMapping):
        return False
    prompt_tokens = state["request"]["prompt_tokens"]
    token_index = int(resident["token_index"])
    if token_index < 0 or token_index >= len(prompt_tokens) - 1:
        return False
    _record_resident_prefix_snapshot(
        state,
        position=token_index,
        token=int(prompt_tokens[token_index]),
        snapshot=resident.get("snapshot"),
        head_executed=False,
    )
    resident["token_index"] = token_index + 1
    state["continuation"]["token_position"] = (
        int(state["continuation"]["token_position"]) + 1
    )
    resident["position"] = int(state["continuation"]["token_position"])
    state["current_token"] = prompt_tokens[token_index + 1]
    state["graph_cursor"] = 0
    resident["stage_cursor"] = 0
    _event(
        state,
        "resident-model-prompt-head-elided",
        {
            "operation_id": operation["operation_id"],
            "position": resident["position"],
            "snapshot_sha256": resident.get("snapshot", {}).get("manifest_sha256"),
        },
    )
    return True


def _draft_propose(state: MutableMapping[str, Any]) -> None:
    resident = state["resident_model"]
    policies = resident.get("policies")
    if not isinstance(policies, Mapping) or not isinstance(policies.get("drafting"), Mapping):
        return
    try:
        from .draft_learning import propose_draft
        context = list(state["request"]["prompt_tokens"]) + list(state["generated_tokens"])
        config = policies["drafting"].get("config", {})
        horizon = int(config.get("max_horizon", 1))
        resident["draft_proposal"] = propose_draft(
            policies["drafting"], context, max_tokens=max(1, min(horizon, 8))
        )
        resident["draft_target_cost_units"] = 0
    except (TypeError, ValueError, KeyError) as exc:
        raise ModelRuntimeError("resident draft policy proposal failed") from exc


_DRAFT_ATTEMPT_WINDOW = 16
"""Closed draft attempts retained as isolated receipts beside the live one."""


def _draft_begin_speculation(
    state: MutableMapping[str, Any], proposal: Mapping[str, Any]
) -> None:
    """Verify a field-owned draft proposal against the real native target.

    The proposal never controls Qwen state by itself: the runtime activates a
    bounded speculation frame (explicit CPU/cache-lane proposed tokens, no
    model execution of its own) and every proposed token is compared against
    the exact native head sample -- same sampler mode, same draw, same head
    stage request -- before its value may appear in the committed stream.
    """
    speculation = state.get("speculation")
    if isinstance(speculation, MutableMapping) and speculation.get("status") == "active":
        return
    draft = list(proposal.get("draft_tokens") or ())
    if not draft:
        return
    sampler = state["continuation"]["sampler_state"]
    state["speculation"] = {
        "schema": "cassifi.model-speculation.v1",
        "source": "resident-draft-policy",
        "draft_program_id": f"resident-draft:{proposal.get('method_id')}",
        "method_id": proposal.get("method_id"),
        "proposal_sha256": proposal.get("proposal_sha256"),
        "fork_checkpoint_sha256": digest_value(_snapshot(state)),
        "prefix_position": int(state["continuation"]["token_position"]),
        "sampler_mode": str(sampler.get("mode", "greedy")),
        "draft_tokens": draft,
        "cursor": 0,
        "accepted_tokens": [],
        "rejected_tokens": [],
        "mode": "target-sample-and-compare",
        "verification_lane": "sequential-native-head",
        "native_tokens_saved": 0,
        "status": "active",
    }
    _event(
        state,
        "draft-speculation-begun",
        {
            "proposal_sha256": proposal.get("proposal_sha256"),
            "method_id": proposal.get("method_id"),
            "horizon": len(draft),
            "prefix_position": int(state["continuation"]["token_position"]),
            "draft_tokens": draft,
        },
    )


def _policy_summary(state: Mapping[str, Any]) -> Mapping[str, Any]:
    """Summarize the learned field policies that shaped one model task.

    The summary is evidence, not control: an ordinary completion reports what
    the field learned and decided, so expert residency and draft acceptance are
    visible on the same surface that produced the tokens.
    """
    resident = state.get("resident_model")
    resident = resident if isinstance(resident, Mapping) else {}
    policies = resident.get("policies")
    policies = policies if isinstance(policies, Mapping) else {}
    experts_raw = policies.get("experts")
    summary: dict[str, Any] = {"experts": None, "drafting": None}
    if isinstance(experts_raw, Mapping):
        layers = experts_raw.get("layers")
        layers = layers if isinstance(layers, list) else []
        observations = 0
        rows = 0
        uses = 0
        for layer in layers:
            if not isinstance(layer, Mapping):
                continue
            observations += int(layer.get("observations", 0) or 0)
            expert_rows = layer.get("experts")
            if isinstance(expert_rows, Mapping):
                rows += len(expert_rows)
                uses += sum(
                    int(row.get("uses", 0) or 0)
                    for row in expert_rows.values()
                    if isinstance(row, Mapping)
                )
        methods_raw = experts_raw.get("methods")
        methods = {}
        if isinstance(methods_raw, Mapping):
            for name in sorted(methods_raw):
                row = methods_raw[name]
                if isinstance(row, Mapping) and int(row.get("attempts", 0) or 0):
                    methods[str(name)] = {
                        key: int(row.get(key, 0) or 0)
                        for key in ("attempts", "hits", "misses", "load_cost_ns")
                    }
        summary["experts"] = {
            "schema": experts_raw.get("schema"),
            "layout": experts_raw.get("layout"),
            "model_id": experts_raw.get("model_id"),
            "layer_count": experts_raw.get("layer_count"),
            "expert_count": experts_raw.get("expert_count"),
            "capacity_bytes": experts_raw.get("capacity_bytes"),
            "epoch": experts_raw.get("epoch"),
            "observations": observations,
            "materialized_rows": rows,
            "expert_uses": uses,
            "contexts": len(experts_raw.get("contexts") or ()),
            "evidence_rows": len(experts_raw.get("evidence") or ()),
            "transitions": len(experts_raw.get("transitions") or ()),
            "methods": methods,
        }
    drafting_raw = policies.get("drafting")
    if isinstance(drafting_raw, Mapping):
        draft_methods = []
        for item in drafting_raw.get("methods") or ():
            if not isinstance(item, Mapping):
                continue
            draft_methods.append(
                {
                    "method_id": item.get("method_id"),
                    "context_width": item.get("context_width"),
                    "horizon": item.get("horizon"),
                    "rows": len(item.get("rows") or ()),
                    "attempts": int(item.get("attempts", 0) or 0),
                    "accepted_tokens": int(item.get("accepted_tokens", 0) or 0),
                    "rejected_tokens": int(item.get("rejected_tokens", 0) or 0),
                    "full_accepts": int(item.get("full_accepts", 0) or 0),
                    "draft_cost_units": int(item.get("draft_cost_units", 0) or 0),
                    "target_cost_units": int(item.get("target_cost_units", 0) or 0),
                }
            )
        summary["drafting"] = {
            "schema": drafting_raw.get("schema"),
            "version": drafting_raw.get("version"),
            "owner_id": drafting_raw.get("owner_id"),
            "active_method_id": drafting_raw.get("active_method_id"),
            "attempts": int(drafting_raw.get("attempts", 0) or 0),
            "accepted_tokens": int(drafting_raw.get("accepted_tokens", 0) or 0),
            "rejected_tokens": int(drafting_raw.get("rejected_tokens", 0) or 0),
            "target_tokens": int(drafting_raw.get("target_tokens", 0) or 0),
            "draft_cost_units": int(drafting_raw.get("draft_cost_units", 0) or 0),
            "target_cost_units": int(drafting_raw.get("target_cost_units", 0) or 0),
            "pretrained_mtp": _plain(drafting_raw.get("pretrained_mtp")),
            "methods": draft_methods,
            "recent_attempts": _plain(resident.get("draft_attempts")),
        }
    graph_sites_raw = resident.get("graph_sites")
    if isinstance(graph_sites_raw, Mapping):
        telemetry = graph_sites_raw.get("telemetry")
        telemetry = telemetry if isinstance(telemetry, Mapping) else {}
        methods_raw = graph_sites_raw.get("methods")
        methods = []
        if isinstance(methods_raw, Mapping):
            for key in sorted(methods_raw):
                row = methods_raw[key]
                if isinstance(row, Mapping):
                    methods.append({
                        "site": row.get("site"),
                        "specialist": row.get("specialist"),
                        "generation": row.get("generation"),
                        "support": row.get("support"),
                        "observed_error_mean": row.get("observed_error"),
                        "task_success": row.get("task_success"),
                        "task_failure": row.get("task_failure"),
                        "native_ops_omitted": row.get("native_ops_omitted"),
                        "admitted": row.get("admitted"),
                        "backed_off": row.get("backed_off"),
                    })
        summary["graph_sites"] = {
            "schema": graph_sites_raw.get("schema"),
            "generation": graph_sites_raw.get("generation"),
            "observed_error_samples": telemetry.get("observed_error", 0),
            "task_outcome_samples": telemetry.get("task_outcome", 0),
            "native_ops_omitted": telemetry.get("native_ops_omitted", 0),
            "native_ops_executed": telemetry.get("native_ops_executed", 0),
            "added_flops": telemetry.get("added_flops", 0),
            "assisted": telemetry.get("assisted", 0),
            "proposed": telemetry.get("proposed", 0),
            "proposals_accepted": telemetry.get("proposals_accepted", 0),
            "proposals_rejected": telemetry.get("proposals_rejected", 0),
            "methods": methods,
        }
    else:
        summary["graph_sites"] = None

    summary["expert_selection"] = _plain(resident.get("expert_selection"))
    summary["draft_comparison"] = _plain(resident.get("draft_comparison"))
    return _plain(summary)


def _draft_observe_target(
    state: MutableMapping[str, Any], token: int, cost_units: int
) -> None:
    resident = state["resident_model"]
    policies = resident.get("policies")
    proposal = resident.get("draft_proposal")
    if not isinstance(policies, MutableMapping) or not isinstance(policies.get("drafting"), Mapping):
        return
    if not isinstance(proposal, Mapping):
        return
    resident["draft_target_cost_units"] = int(resident.get("draft_target_cost_units", 0)) + max(0, int(cost_units))
    targets = list(resident.get("draft_target_tokens", ()))
    draft = list(proposal.get("draft_tokens", ()))
    targets.append(int(token))
    index = len(targets) - 1
    finalize = not draft or index >= len(draft) - 1 or int(token) != int(draft[index])
    if not finalize:
        resident["draft_target_tokens"] = targets
        return
    try:
        from .draft_learning import record_target_outcome, target_sample_and_compare
        comparison = target_sample_and_compare(proposal, targets)
        updated, comparison = record_target_outcome(
            policies["drafting"], proposal, targets,
            target_cost_units=int(resident["draft_target_cost_units"]), draft_cost_units=0,
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise ModelRuntimeError("resident draft target observation failed") from exc
    policies["drafting"] = updated
    resident["draft_comparison"] = comparison
    attempts = resident.get("draft_attempts")
    if not isinstance(attempts, list):
        attempts = []
    attempts.append(
        {
            "schema": "cassifi.draft-attempt-receipt.v1",
            "method_id": proposal.get("method_id"),
            "proposal_sha256": proposal.get("proposal_sha256"),
            "status": comparison["status"],
            "accepted_tokens": list(comparison["accepted_prefix"]),
            "rejected_tokens": list(comparison["rejected_suffix"]),
            "rejection_target": comparison["rejection_target"],
            "target_tokens_committed": len(comparison["committed_tokens"]),
            "target_cost_units": int(resident["draft_target_cost_units"]),
            "draft_lane": "cpu-cache",
            "native_tokens_saved": 0,
            "revision": int(state["ledger"]["transitions"]),
        }
    )
    if len(attempts) > _DRAFT_ATTEMPT_WINDOW:
        del attempts[: len(attempts) - _DRAFT_ATTEMPT_WINDOW]
    resident["draft_attempts"] = attempts
    resident["draft_proposal"] = None
    resident["draft_target_cost_units"] = 0
    resident["draft_target_tokens"] = []


def _start_resident_stage(state: MutableMapping[str, Any], operation: Mapping[str, Any]) -> None:
    pending_count = sum(
        1 for item in state["operations"].values()
        if isinstance(item, Mapping) and item.get("phase") == "proposed"
    )
    if pending_count >= _limit(state, "max_pending_operations"):
        raise ModelRuntimeError("resident stage operation limit exhausted")
    parameters = operation["parameters"]
    source_sha256 = parameters.get("source_sha256")
    if (
        not isinstance(source_sha256, str)
        or len(source_sha256) != 64
        or any(character not in "0123456789abcdef" for character in source_sha256)
    ):
        raise ModelRuntimeError("resident stage lacks an exact GGUF source identity")
    resident = state.get("resident_model")
    if not isinstance(resident, MutableMapping):
        raise ModelRuntimeError("resident model cursor is unavailable")
    graph = state["package"]["graph"]
    graph_cursor = int(state["graph_cursor"])
    expected = graph[graph_cursor]
    if expected.get("operation_id") != operation.get("operation_id"):
        raise ModelRuntimeError("resident stage cursor does not match graph")
    stage = str(operation["stage"])
    if stage in {"qwen-route", "qwen-attention-route"}:
        resident["expert_selection"] = None
        resident["expert_route"] = None
    prompt_tokens = state["request"]["prompt_tokens"]
    token_index = int(resident["token_index"])
    if token_index < 0 or token_index >= len(state["generated_tokens"]) + len(prompt_tokens):
        raise ModelRuntimeError("resident token cursor is outside its bound")
    is_prompt = token_index < len(prompt_tokens)
    position = int(state["continuation"]["token_position"])
    should_sample = stage == "qwen-head" and (not is_prompt or token_index == len(prompt_tokens) - 1)
    if should_sample:
        if resident.get("draft_proposal") is None:
            _draft_propose(state)
        proposal = resident.get("draft_proposal")
        if isinstance(proposal, Mapping):
            _draft_begin_speculation(state, proposal)
    sampler = dict(state["continuation"]["sampler_state"])
    mode = str(sampler.get("mode", "greedy"))
    if mode not in {"greedy", "categorical"}:
        raise ModelRuntimeError("resident sampler mode is unsupported")
    draw = _rng_uniform(state) if should_sample and mode == "categorical" else 0.0
    operation_id = f"resident-stage-{state['counters']['operation']}"
    state["counters"]["operation"] += 1
    stage_parameters = {
        key: _plain(value) for key, value in parameters.items()
        if key not in {"source_sha256", "source_id", "manifest_sha256"}
    }
    request_metadata = state["request"]
    visual_reference = request_metadata.get("visual_embedding_id")
    visual_positions = request_metadata.get("visual_embedding_positions")
    visual_rope_positions = request_metadata.get("visual_rope_positions")
    visual_image_grid = request_metadata.get("visual_image_grid")
    visual_image_start = request_metadata.get("visual_image_start")
    visual_rope_delta = request_metadata.get("visual_rope_delta")
    placeholder_token = request_metadata.get("visual_placeholder_token_id")
    if visual_reference is not None:
        if (
            not isinstance(visual_reference, str)
            or not visual_reference
            or not isinstance(visual_positions, Mapping)
            or not isinstance(visual_rope_positions, Mapping)
            or set(visual_positions) != set(visual_rope_positions)
            or not isinstance(visual_image_grid, (list, tuple))
            or len(visual_image_grid) != 2
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 1
                for value in visual_image_grid
            )
            or isinstance(visual_image_start, bool)
            or not isinstance(visual_image_start, int)
            or visual_image_start < 0
            or visual_image_start + len(visual_positions) > len(prompt_tokens)
            or isinstance(visual_rope_delta, bool)
            or not isinstance(visual_rope_delta, int)
            or visual_rope_delta != (
                len(visual_positions) - max(visual_image_grid)
            )
            or isinstance(placeholder_token, bool)
            or not isinstance(placeholder_token, int)
            or placeholder_token < 0
        ):
            raise ModelRuntimeError("resident visual embedding metadata is invalid")
        raw_index = visual_positions.get(str(position))
        raw_axes = visual_rope_positions.get(str(position))
        image_marker = (
            is_prompt and int(state["current_token"]) == placeholder_token
        )
        if raw_index is not None and (
            isinstance(raw_index, bool)
            or not isinstance(raw_index, int)
            or raw_index < 0
            or not image_marker
        ):
            raise ModelRuntimeError(
                "visual embedding position does not match its image marker"
            )
        if (
            stage == "qwen-embedding"
            and image_marker
            and raw_index is None
        ):
            raise ModelRuntimeError("visual image marker has no embedding row")
        if raw_index is not None:
            expected_axes = [
                visual_image_start,
                visual_image_start + raw_index // visual_image_grid[1],
                visual_image_start + raw_index % visual_image_grid[1],
                0,
            ]
            if (
                not isinstance(raw_axes, (list, tuple))
                or len(raw_axes) != 4
                or any(
                    isinstance(value, bool) or not isinstance(value, int)
                    or value < 0
                    for value in raw_axes
                )
                or list(raw_axes) != expected_axes
                or position != visual_image_start + raw_index
                or visual_image_grid[0] * visual_image_grid[1]
                != len(visual_positions)
            ):
                raise ModelRuntimeError(
                    "visual image M-RoPE coordinates differ from the merger grid"
                )
        stage_parameters["visual_embedding_id"] = visual_reference
        if raw_index is not None:
            stage_parameters["visual_embedding_index"] = raw_index
            stage_parameters["rope_position_ids"] = list(raw_axes)
        elif position >= visual_image_start + len(visual_positions):
            corrected = position - visual_rope_delta
            stage_parameters["rope_position_ids"] = [corrected] * 4
    elif any(
        value is not None
        for value in (
            visual_positions,
            visual_rope_positions,
            visual_image_grid,
            placeholder_token,
            visual_image_start,
            visual_rope_delta,
        )
    ):
        raise ModelRuntimeError(
            "resident visual marker metadata has no embedding reference"
        )
    model_metadata = state["package"].get("numerical_profile", {}).get("model_metadata", {})
    stage_parameters.update(
        {
            "source_id": parameters.get("source_id"),
            "manifest_sha256": parameters.get("manifest_sha256"),
            "sample": should_sample,
            "prompt": is_prompt,
            "model_metadata": {
                key: value for key, value in model_metadata.items()
                if not isinstance(value, (list, dict))
            },
        }
    )
    if resident.get("draft_proposal") is not None:
        stage_parameters["draft_proposal"] = _plain(resident["draft_proposal"])
    route = resident.get("expert_route")
    if isinstance(route, Mapping):
        route_experts = route.get("expert_ids", route.get("mandatory_experts"))
        if route_experts is not None:
            stage_parameters["expert_ids"] = _plain(route_experts)
        stage_parameters["expert_route"] = _plain(route)
    selection = resident.get("expert_selection")
    if isinstance(selection, Mapping):
        prefetch = selection.get("prefetch_experts", selection.get("resident_experts"))
        evict = selection.get("evict_experts")
        if prefetch is not None:
            stage_parameters["prefetch_experts"] = _plain(prefetch)
        if evict is not None:
            stage_parameters["evict_experts"] = _plain(evict)
    specialist = (
        "recurrent-dynamics" if stage in {"qwen-attention-route", "qwen-layer"} and bool(parameters.get("recurrent", False))
        else "expert-synthesis" if stage == "qwen-experts"
        else "execution-choice" if stage == "qwen-head"
        else "attention-memory"
    )
    graph_state = resident.get("graph_sites", {})
    methods = graph_state.get("methods", {}) if isinstance(graph_state, Mapping) else {}
    sequence_id = f"{state['identity']['owner_id']}:{state['identity']['member_id']}:{state['identity']['operation_id']}"
    resident_metadata = resident.get("snapshot", {}).get("metadata", {})
    resident_metadata = resident_metadata if isinstance(resident_metadata, Mapping) else {}
    from .graph_site import (
        NEUTRAL_FIELD_EPOCH_SHA256,
        NEUTRAL_MEMBRANE_PROFILE,
        configured_mode as graph_site_mode,
        is_local_recurrent_row,
    )
    dependencies = {
        "tensor_names": _plain(parameters.get("tensor_names", {})),
        "state_effects": _plain(operation.get("state_effects", ())),
        "architecture": str(model_metadata.get("general.architecture", "")),
        "membrane_profile": _plain(
            resident_metadata.get(
                "membrane_profile",
                parameters.get("membrane_profile", model_metadata.get("cassifi.membrane_profile", NEUTRAL_MEMBRANE_PROFILE)),
            )
        ),
        "field_epoch_sha256": str(
            resident_metadata.get(
                "field_epoch_sha256",
                parameters.get(
                    "field_epoch_sha256",
                    state.get("request", {}).get("prefix_reuse", {}).get("field_epoch_sha256", "")
                    if isinstance(state.get("request", {}).get("prefix_reuse"), Mapping) else NEUTRAL_FIELD_EPOCH_SHA256,
                ),
            )
        ),
    }
    field_epoch = dependencies["field_epoch_sha256"]
    membrane_profile = dependencies["membrane_profile"]
    expected_native_state = {
        "membrane_profile": membrane_profile,
        "field_epoch_sha256": field_epoch,
    }
    eligible = specialist in {"expert-synthesis", "recurrent-dynamics", "attention-memory", "execution-choice"} and isinstance(methods, Mapping) and any(
        isinstance(method, Mapping) and method.get("admitted") is True
        and not method.get("backed_off") and method.get("site") == str(parameters.get("op", stage))
        and method.get("specialist") == specialist and method.get("dependencies") == dependencies
        and isinstance(method.get("applicability"), Mapping)
        and isinstance(method.get("method"), Mapping)
        and (specialist != "recurrent-dynamics" or is_local_recurrent_row(method))
        and isinstance(method["method"].get("native_state_applicability"), Mapping)
        and all(method["method"]["native_state_applicability"].get(key) == value
                for key, value in expected_native_state.items())
        and method["applicability"].get("source_sha256") == source_sha256
        and method["applicability"].get("stage") == stage
        and method["applicability"].get("layer") == parameters.get("layer")
        and (specialist != "attention-memory"
             or method["applicability"].get("position") == position)
        for method in methods.values()
    )
    configured_mode = graph_site_mode(state["request"].get("graph_site_modes"), specialist)
    graph_verb = (
        ("replace" if eligible else "observe") if configured_mode == "auto"
        else configured_mode if configured_mode == "observe" or eligible else "observe"
    )
    graph_site = {
        "schema": "cassifi.graph-site-request.v1",
        "verb": graph_verb,
        "operation_id": operation_id,
        "source_sha256": source_sha256,
        "architecture": str(model_metadata.get("general.architecture", "")),
        "backend": str(resident.get("snapshot", {}).get("metadata", {}).get("backend", "unknown")),
        "site": str(parameters.get("op", stage)),
        "stage": stage,
        "layer": parameters.get("layer"),
        "position": position,
        "sequence_id": sequence_id,
        "intervention_order": graph_cursor,
        "predecessor_generation": int(resident.get("graph_site_generation", 0)),
        "predecessor_snapshot_sha256": str(resident.get("snapshot", {}).get("snapshot_sha256", "")),
        "dependencies": dependencies,
        "specialist": specialist,
    }
    request = {
        "schema": RESIDENT_STAGE_REQUEST_SCHEMA,
        "operation_id": operation_id,
        "model_program_id": state["package"]["program"]["program_id"],
        "source_sha256": source_sha256,
        "stage": stage,
        "layer": parameters.get("layer"),
        "token": int(state["current_token"]),
        "position": position,
        "snapshot": _resident_snapshot(resident.get("snapshot")),
        "sampler": {
            "mode": mode,
            "temperature": float(sampler.get("temperature", 1.0)),
            "top_k": int(sampler.get("top_k", 0)),
            "draw": draw,
        },
        "parameters": stage_parameters,
        "policies": _plain({
            key: value for key, value in resident.get("policies", {}).items()
            if key != "graph_sites"
        }),
        **({"graph_site": graph_site} if configured_mode != "off" else {}),
    }
    request["request_sha256"] = digest_value(request)
    state["operations"][operation_id] = {
        "phase": "proposed",
        "request": request,
        "graph_site": graph_site if configured_mode != "off" else None,
        "request_sha256": request["request_sha256"],
    }
    state["phase"] = "waiting"
    state["wait_reason"] = RESIDENT_STAGE_WAIT_REASON
    state["await_target"] = operation_id
    # The full request stays on the pending operation row; the event only
    # carries its identity so that accumulated events do not duplicate the
    # whole snapshot descriptor and policy block on every single stage.
    _event(
        state,
        "resident-model-stage-proposed",
        {
            "operation_id": operation_id,
            "request_sha256": request["request_sha256"],
            "stage": stage,
            "layer": parameters.get("layer"),
            "token": int(state["current_token"]),
            "position": position,
        },
    )
    


def _start_native_transformer(
    state: MutableMapping[str, Any], operation: Mapping[str, Any]
) -> None:
    parameters = operation["parameters"]
    source_sha256 = parameters.get("source_sha256")
    if (
        not isinstance(source_sha256, str)
        or len(source_sha256) != 64
        or any(character not in "0123456789abcdef" for character in source_sha256)
    ):
        raise ModelRuntimeError("native transformer lacks an exact GGUF source identity")
    branch_key = state["branch_stack"][-1] if state["branch_stack"] else "main"
    native_task_id = f"{state['identity']['owner_id']}:{state['identity']['operation_id']}:{branch_key}"
    # The owner publishes each resume as ``resident-model-resume:<id>`` in one
    # owner-wide operation namespace, so the id carries its task identity.
    operation_id = (
        f"model-native-{digest_value(native_task_id)[:24]}-{state['counters']['operation']}"
    )
    state["counters"]["operation"] += 1
    sampler = state["continuation"]["sampler_state"]
    mode = str(sampler.get("mode", "greedy"))
    if mode not in {"greedy", "categorical"}:
        raise ModelRuntimeError("native transformer sampler mode is unsupported")
    # The request records the sampler the native C API executes, so owner
    # replay compares every step exactly: greedy decoding runs in its canonical
    # form, and categorical temperature is a float32.
    if mode == "greedy":
        temperature, top_k = 1.0, 0
    else:
        try:
            temperature = struct.unpack(
                "<f", struct.pack("<f", float(sampler.get("temperature", 1.0)))
            )[0]
        except (OverflowError, struct.error) as exc:
            raise ModelRuntimeError(
                "native transformer sampler temperature exceeds float32"
            ) from exc
        if not math.isfinite(temperature) or temperature <= 0.0:
            raise ModelRuntimeError("native transformer sampler temperature is invalid")
        top_k = int(sampler.get("top_k", 0))
    draw = _rng_uniform(state) if mode == "categorical" else 0.0
    request = {
        "schema": "cassifi.native-model-token-request.v1",
        "operation_id": operation_id,
        "native_task_id": native_task_id,
        "model_program_id": state["package"]["program"]["program_id"],
        "source_id": parameters.get("source_id"),
        "source_sha256": source_sha256,
        "tokens": list(state["request"]["prompt_tokens"]) + list(state["generated_tokens"]),
        "sampler": {
            "mode": mode,
            "temperature": temperature,
            "top_k": top_k,
            "draw": draw,
        },
        "attribution": "resident-native-transformer",
    }
    # A token run lets one owner round admit up to NATIVE_TOKEN_RUN_MAX
    # consecutive native tokens.  Every position keeps its own operation id
    # and exact pre-drawn sampler value, so each admitted token replays as the
    # same row the one-token path would produce.
    speculation = state.get("speculation")
    speculating = (
        isinstance(speculation, Mapping) and speculation.get("status") == "active"
    )
    draft_tokens: list[int] = []
    draft_remaining = 0
    if speculating:
        draft_all = speculation.get("draft_tokens") or ()
        cursor = int(speculation.get("cursor", 0))
        draft_tokens = [int(item) for item in draft_all[cursor:]]
        draft_remaining = len(draft_tokens)
    bound = min(
        NATIVE_TOKEN_RUN_MAX,
        int(state["request"]["max_new_tokens"]) - len(state["generated_tokens"]),
        (draft_remaining + 1) if speculating else NATIVE_TOKEN_RUN_MAX,
    )
    if (
        bound > 1
        and not state["branch_stack"]
        and (not speculating or draft_remaining > 0)
    ):
        prefix = operation_id.rsplit("-", 1)[0]
        counter = int(state["counters"]["operation"])
        state["counters"]["operation"] = counter + bound - 1
        scratch = {
            "continuation": {
                "rng_state": {"state": state["continuation"]["rng_state"]["state"]}
            }
        }
        request["run"] = {
            "bound": bound,
            "operation_ids": [operation_id]
            + [f"{prefix}-{counter + index}" for index in range(bound - 1)],
            "draws": [draw]
            + [
                _rng_uniform(scratch) if mode == "categorical" else 0.0
                for _ in range(bound - 1)
            ],
        }
        if speculating:
            # The draft's own proposed tokens for this round; the native
            # side verifies them in one pass and falls back to ordinary
            # per-token steps whenever it cannot (see the swarm dispatch).
            # Position ``bound - 1`` has no draft entry: it is always the
            # target's own sample, either the first divergence or a bonus
            # token once the whole draft matches.
            request["run"]["draft_tokens"] = draft_tokens[: bound - 1]
    state["operations"][operation_id] = {
        "phase": "proposed",
        "request": request,
        "result": None,
    }
    state["phase"] = "waiting"
    state["wait_reason"] = "native-model-token"
    state["await_target"] = operation_id
    _event(state, "native-model-token-proposed", request)


def _execute_matmul(
    state: MutableMapping[str, Any], operation: Mapping[str, Any]
) -> bool:
    left = _tensor(state, operation["inputs"][0])
    right = _tensor(state, operation["inputs"][1])
    vector = _vector(left)
    matrix_shape = _shape(right)
    matrix = _dequantized(right)
    if len(matrix_shape) != 2:
        raise ModelRuntimeError("matmul weight must be rank two")
    rows, columns = matrix_shape
    if len(vector) != columns:
        raise ModelRuntimeError("matmul dimensions do not align")
    active = state.get("active_operation")
    if not isinstance(active, MutableMapping) or active.get("operation_id") != operation["operation_id"]:
        active = {
            "operation_id": operation["operation_id"],
            "cursor": 0,
            "partial": [0.0] * rows,
            "input_versions": {
                name: _tensor(state, name)["view"].get("mutable_version")
                for name in operation["inputs"]
                if not name.startswith("$")
            },
        }
        state["active_operation"] = active
    start = int(active["cursor"])
    stop = min(rows, start + _limit(state, "panel_rows"))
    for row in range(start, stop):
        offset = row * columns
        active["partial"][row] = math.fsum(vector[column] * matrix[offset + column] for column in range(columns))
    active["cursor"] = stop
    state["ledger"]["scalar_operations"] += (stop - start) * columns * 2
    if stop < rows:
        return False
    _store(state, operation["output"], active["partial"], (rows,))
    state["active_operation"] = None
    return True


def _execute_operation(
    state: MutableMapping[str, Any], operation: Mapping[str, Any]
) -> bool:
    op = operation["op"]
    inputs = [_tensor(state, name) for name in operation["inputs"]]
    output = operation["output"]
    parameters = operation["parameters"]
    if op == "external-model":
        _start_external(state, operation)
        return False
    if op == "native-transformer":
        _start_native_transformer(state, operation)
        return False
    if op in {
        "qwen-embedding", "qwen-attention", "qwen-attention-route",
        "qwen-route", "qwen-experts", "qwen-ffn", "qwen-layer", "qwen-head",
    }:
        if op == "qwen-head" and _elide_prompt_head(state, operation):
            return False
        _start_resident_stage(state, operation)
        return False
    if op == "matmul":
        return _execute_matmul(state, operation)
    if op == "copy":
        payload = inputs[0]
        _store(state, output, _dequantized(payload), _shape(payload), dtype=str(payload["view"]["dtype"]))
    elif op == "embedding":
        table = inputs[0]
        token = int(_dequantized(inputs[1])[0])
        shape = _shape(table)
        if len(shape) != 2 or token < 0 or token >= shape[0]:
            raise ModelRuntimeError("embedding index is outside table")
        values = _dequantized(table)
        width = shape[1]
        _store(state, output, values[token * width : (token + 1) * width], (width,))
    elif op in {"add", "mul"}:
        left, right, shape = _binary_values(inputs[0], inputs[1])
        values = [a + b for a, b in zip(left, right)] if op == "add" else [a * b for a, b in zip(left, right)]
        _store(state, output, values, shape)
    elif op in {"silu", "gelu"}:
        values = _dequantized(inputs[0])
        if op == "silu":
            result = [value / (1.0 + math.exp(-value)) for value in values]
        else:
            result = [0.5 * value * (1.0 + math.erf(value / math.sqrt(2.0))) for value in values]
        _store(state, output, result, _shape(inputs[0]))
    elif op == "softmax":
        _store(state, output, _softmax(_vector(inputs[0]), float(parameters.get("temperature", 1.0))), _shape(inputs[0]))
    elif op == "rms-norm":
        values = _vector(inputs[0])
        epsilon = float(parameters.get("epsilon", 1e-6))
        if epsilon <= 0.0 or not math.isfinite(epsilon):
            raise ModelRuntimeError("rms normalization epsilon is invalid")
        scale = 1.0 / math.sqrt(math.fsum(value * value for value in values) / len(values) + epsilon)
        if len(inputs) > 1:
            weights = _vector(inputs[1])
            if len(weights) != len(values):
                raise ModelRuntimeError("rms normalization weight shape mismatch")
        else:
            weights = [1.0] * len(values)
        _store(state, output, [value * scale * weight for value, weight in zip(values, weights)], (len(values),))
    elif op == "rope":
        values = _vector(inputs[0])
        if len(values) % 2:
            raise ModelRuntimeError("rope vector width must be even")
        position = int(_dequantized(inputs[1])[0]) if len(inputs) > 1 else int(state["continuation"]["token_position"])
        theta = float(parameters.get("theta", 10_000.0))
        result = list(values)
        for index in range(0, len(values), 2):
            frequency = theta ** (-index / len(values))
            angle = position * frequency
            cosine, sine = math.cos(angle), math.sin(angle)
            result[index] = values[index] * cosine - values[index + 1] * sine
            result[index + 1] = values[index] * sine + values[index + 1] * cosine
        _store(state, output, result, (len(result),))
    elif op == "attention":
        query, key, value = (_vector(item) for item in inputs[:3])
        if not (len(query) == len(key) == len(value)):
            raise ModelRuntimeError("attention vectors must have equal width")
        name = str(parameters.get("memory", operation["operation_id"]))
        history = list(state["memory"]["attention"].get(name, []))
        history.append({"key": key, "value": value, "position": int(state["continuation"]["token_position"])})
        scale = 1.0 / math.sqrt(len(query))
        probabilities = _softmax([math.fsum(a * b for a, b in zip(query, row["key"])) * scale for row in history])
        attended = [math.fsum(probability * row["value"][column] for probability, row in zip(probabilities, history)) for column in range(len(value))]
        state["continuation"]["pending_deltas"].append({"kind": "attention-append", "name": name, "key": key, "value": value, "position": int(state["continuation"]["token_position"])})
        _store(state, output, attended, (len(attended),))
    elif op == "conv1d":
        vector = _vector(inputs[0])
        kernel = _vector(inputs[1])
        name = str(parameters.get("memory", operation["operation_id"]))
        width = int(parameters.get("history", len(kernel)))
        history = list(state["memory"]["convolution"].get(name, []))
        history.append(vector)
        history = history[-width:]
        result = []
        for column in range(len(vector)):
            values = [row[column] for row in history]
            weights = kernel[-len(values):]
            result.append(math.fsum(a * b for a, b in zip(values, weights)))
        state["continuation"]["pending_deltas"].append({"kind": "convolution-write", "name": name, "value": history})
        _store(state, output, result, (len(result),))
    elif op == "recurrent":
        vector = _vector(inputs[0])
        input_weights, recurrent_weights = inputs[1], inputs[2]
        name = str(parameters.get("memory", operation["operation_id"]))
        hidden_size = _shape(input_weights)[0]
        hidden = list(state["memory"]["recurrent"].get(name, [0.0] * hidden_size))
        wx = _matrix_vector(input_weights, vector)
        uh = _matrix_vector(recurrent_weights, hidden)
        result = [math.tanh(a + b) for a, b in zip(wx, uh)]
        state["continuation"]["pending_deltas"].append({"kind": "recurrent-write", "name": name, "value": result})
        _store(state, output, result, (len(result),))
    elif op == "sample":
        logits = _vector(inputs[0])
        token, sample = _sample_token(state, logits)
        if output is not None:
            _store(state, output, [token], (1,), dtype="i64")
        _complete_token(state, token, sample)
    else:
        raise ModelRuntimeError(f"model operation {op!r} is not implemented")
    state["ledger"]["scalar_operations"] += sum(len(_dequantized(item)) for item in inputs if item.get("values") is not None)
    return True


def _matrix_vector(matrix_payload: Mapping[str, Any], vector: Sequence[float]) -> list[float]:
    shape = _shape(matrix_payload)
    if len(shape) != 2 or shape[1] != len(vector):
        raise ModelRuntimeError("matrix-vector dimensions do not align")
    matrix = _dequantized(matrix_payload)
    return [math.fsum(matrix[row * shape[1] + column] * vector[column] for column in range(shape[1])) for row in range(shape[0])]


def _snapshot(state: Mapping[str, Any], *, detach: bool = True) -> Mapping[str, Any]:
    keys = (
        "tensors",
        "memory",
        "resident_model",
        "continuation",
        "graph_cursor",
        "current_token",
        "generated_tokens",
        "active_operation",
        "operations",
        "phase",
        "wait_reason",
        "await_target",
        "result",
        "speculation",
        "paused_from",
    )
    fields = {key: state.get(key) for key in keys}
    # A checkpoint hashes these fields immediately; only retained branch
    # snapshots need a detached copy of the already-owned model state.
    return _plain(fields) if detach else fields


def _begin_branch(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if len(state["branches"]) >= _limit(state, "max_branches"):
        raise ModelRuntimeError("model branch limit exhausted")
    branch_id = str(arguments.get("branch_id") or f"model-branch-{state['counters']['branch']}")
    if branch_id in state["branches"]:
        raise ModelRuntimeError("model branch identity already exists")
    state["counters"]["branch"] += 1
    snapshot = _snapshot(state)
    branch = {
        "branch_id": branch_id,
        "parent": state["branch_stack"][-1] if state["branch_stack"] else None,
        "base_sha256": digest_value(snapshot),
        "snapshot": snapshot,
        "assumptions": _plain(arguments.get("assumptions", [])),
        "effect_policy": "forbid",
        "work_start": int(state["ledger"]["transitions"]),
        "status": "active",
    }
    state["branches"][branch_id] = branch
    state["branch_stack"].append(branch_id)
    return {key: branch[key] for key in ("branch_id", "parent", "base_sha256", "effect_policy")}


def _rollback_branch(state: MutableMapping[str, Any], branch_id: str) -> Mapping[str, Any]:
    if not state["branch_stack"] or state["branch_stack"][-1] != branch_id:
        raise ModelRuntimeError("only the active innermost model branch may roll back")
    branch = state["branches"][branch_id]
    spent = int(state["ledger"]["transitions"]) - int(branch["work_start"])
    for key, value in copy.deepcopy(branch["snapshot"]).items():
        state[key] = value
    state["branch_stack"].pop()
    state["branches"][branch_id] = {
        **{key: value for key, value in branch.items() if key != "snapshot"},
        "status": "rolled-back",
        "spent_work": spent,
    }
    state["ledger"]["discarded_work"] += spent
    return {"branch_id": branch_id, "status": "rolled-back", "spent_work": spent}


def _commit_branch(
    state: MutableMapping[str, Any],
    branch_id: str,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    if not state["branch_stack"] or state["branch_stack"][-1] != branch_id:
        raise ModelRuntimeError("only the active innermost model branch may commit")
    branch = state["branches"][branch_id]
    expected = arguments.get("expected_base_sha256")
    if expected is not None and expected != branch["base_sha256"]:
        raise ModelRuntimeError("model branch base revision is stale")
    new_operation_ids = set(state["operations"]) - set(branch["snapshot"]["operations"])
    unsafe_operations = []
    for operation_id in sorted(new_operation_ids):
        operation = state["operations"][operation_id]
        request = operation.get("request")
        if (
            not isinstance(request, Mapping)
            or request.get("schema") not in {
                "cassifi.native-model-token-request.v1",
                RESIDENT_STAGE_REQUEST_SCHEMA,
            }
            or operation.get("phase") not in {"proposed", "settled"}
        ):
            unsafe_operations.append(operation_id)
    if unsafe_operations:
        raise ModelRuntimeError("model branch contains an external operation")
    spent = int(state["ledger"]["transitions"]) - int(branch["work_start"])
    successor = digest_value(_snapshot(state))
    state["branch_stack"].pop()
    state["branches"][branch_id] = {
        **{key: value for key, value in branch.items() if key != "snapshot"},
        "status": "committed",
        "spent_work": spent,
        "successor_sha256": successor,
    }
    return {
        "branch_id": branch_id,
        "status": "committed",
        "spent_work": spent,
        "successor_sha256": successor,
    }


def _begin_speculation(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if state.get("speculation") is not None and state["speculation"].get("status") == "active":
        raise ModelRuntimeError("a speculative model fork is already active")
    draft = arguments.get("draft_tokens")
    if isinstance(draft, (str, bytes)) or not isinstance(draft, Sequence) or not draft:
        raise ModelRuntimeError("draft_tokens must be a nonempty sequence")
    tokens = [_positive(item, "draft token", allow_zero=True) for item in draft]
    checkpoint = digest_value(_snapshot(state))
    state["speculation"] = {
        "schema": "cassifi.model-speculation.v1",
        "fork_checkpoint_sha256": checkpoint,
        "prefix_tokens": list(state["request"]["prompt_tokens"]) + list(state["generated_tokens"]),
        "draft_tokens": tokens,
        "cursor": 0,
        "accepted_tokens": [],
        "rejected_tokens": [],
        "draft_program_id": str(arguments.get("draft_program_id", "attributed-draft")),
        "mode": "target-sample-and-compare",
        "status": "active",
    }
    return _plain(state["speculation"])


def _apply_expert_learning(
    state: MutableMapping[str, Any], route: Mapping[str, Any]
) -> None:
    resident = state["resident_model"]
    policies = resident.get("policies")
    if not isinstance(policies, MutableMapping) or not isinstance(policies.get("experts"), Mapping):
        return
    experts = policies["experts"]
    ledger = resident.get("expert_context")
    if not isinstance(ledger, MutableMapping):
        ledger = {}
        resident["expert_context"] = ledger
    try:
        from .expert_learning import select
        layer = int(route.get("layer"))
        mandatory = route.get("mandatory_experts", route.get("expert_ids", ()))
        expert_count = int(experts["expert_count"])
        expert_bytes = route.get("expert_bytes", [1] * expert_count)
        context_key = str(route.get("context_key", ""))
        previous_context_key = route.get("previous_context_key", ledger.get(str(layer)))
        updated, decision = select(
            experts,
            layer,
            context_key,
            mandatory,

            expert_bytes,
            route.get("resident_experts", ()),
            previous_context_key,
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise ModelRuntimeError("resident expert policy selection failed") from exc
    ledger[str(layer)] = context_key
    policies["experts"] = updated
    resident["expert_selection"] = decision


def _observe_expert_learning(
    state: MutableMapping[str, Any], observation: Mapping[str, Any]
) -> None:
    resident = state["resident_model"]
    policies = resident.get("policies")
    if not isinstance(policies, MutableMapping) or not isinstance(policies.get("experts"), Mapping):
        return
    try:
        from .expert_learning import observe
        policies["experts"] = observe(policies["experts"], observation)
    except (TypeError, ValueError, KeyError) as exc:
        raise ModelRuntimeError("resident expert policy observation failed") from exc





def _record_graph_site_execution(
    state: MutableMapping[str, Any],
    request: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    site = request.get("graph_site")
    if site is None and not any(result.get(name) is not None for name in (
        "graph_site_training", "graph_site_observation", "graph_site_abstention",
    )):
        return
    if not isinstance(site, Mapping):
        raise ModelRuntimeError("resident graph-site request binding is invalid")
    received = {
        name: result[name] for name in (
            "graph_site_training", "graph_site_observation", "graph_site_abstention"
        ) if result.get(name) is not None
    }
    if len(received) > 1:
        raise ModelRuntimeError("resident graph-site result has conflicting evidence")
    if not received:
        if site.get("verb") in {"assist", "replace", "propose"}:
            raise ModelRuntimeError("resident graph-site intervention lacks executor telemetry")
        return
    name, evidence = next(iter(received.items()))
    if not isinstance(evidence, Mapping):
        raise ModelRuntimeError("resident graph-site evidence is invalid")
    binding = evidence.get("invocation")
    if not isinstance(binding, Mapping):
        raise ModelRuntimeError("resident graph-site evidence lacks its invocation")
    invocation_body = {key: value for key, value in binding.items() if key != "invocation_sha256"}
    if binding.get("invocation_sha256") != digest_value(invocation_body):
        raise ModelRuntimeError("resident graph-site invocation digest is invalid")
    expected = {
        "source_sha256": request.get("source_sha256"),
        "architecture": site.get("architecture"),
        "backend": result.get("backend", site.get("backend")),
        "sequence_id": site.get("sequence_id"),
        "stage": request.get("stage"),
        "layer": request.get("layer"),
        "position": request.get("position"),
        "request_sha256": request.get("request_sha256"),
        "site": site.get("site"),
        "specialist": site.get("specialist"),
        "intervention_order": site.get("intervention_order"),
        "predecessor_generation": site.get("predecessor_generation"),
        "predecessor_sha256": site.get("predecessor_snapshot_sha256"),
        "dependencies": site.get("dependencies"),
        "verb": site.get("verb"),
    }
    if any(binding.get(key) != value for key, value in expected.items()):
        raise ModelRuntimeError("resident graph-site evidence binding is stale")
    if name == "graph_site_training" and (
        site.get("verb") not in {"observe", "propose", "replace"}
        or result.get("native_ops_omitted", 0) != 0
    ):
        raise ModelRuntimeError("training requires ordinary native graph execution")
    if name == "graph_site_observation" and (
        site.get("verb") not in {"assist", "replace", "propose"}
        or evidence.get("native_ops_omitted") != result.get("native_ops_omitted", 0)
    ):
        raise ModelRuntimeError("graph-site intervention telemetry is invalid")
    try:
        from .graph_site import acquire_training, record_abstention, record_execution
        resident = state["resident_model"]
        graph_state = resident["graph_sites"]
        if name == "graph_site_training":
            updated = acquire_training(graph_state, evidence)
        elif name == "graph_site_observation":
            updated = record_execution(graph_state, evidence)
        else:
            updated = record_abstention(graph_state, evidence)
        resident["graph_sites"] = updated
        resident["graph_site_generation"] = int(updated["generation"])
    except (TypeError, ValueError, KeyError) as exc:
        raise ModelRuntimeError("resident graph-site evidence admission failed") from exc


def _resume_resident_stage(
    state: MutableMapping[str, Any], arguments: Mapping[str, Any]
) -> Mapping[str, Any]:
    operation_id = str(arguments.get("operation_id", ""))
    pending = state["operations"].get(operation_id)
    if not isinstance(pending, MutableMapping):
        raise ModelRuntimeError("resident stage operation is unavailable")
    result_value = arguments.get("result")
    if not isinstance(result_value, Mapping):
        raise ModelRuntimeError("resident stage result must be a mapping")
    result = _plain(result_value)
    if result.get("schema") != RESIDENT_STAGE_RESULT_SCHEMA:
        raise ModelRuntimeError("resident stage result schema is invalid")
    supplied_request_sha = result.get("request_sha256")
    request_sha = pending.get("request_sha256") or pending.get("request", {}).get("request_sha256")
    if supplied_request_sha != request_sha:
        raise ModelRuntimeError("resident stage result is not bound to its request")
    supplied_digest = digest_value(result)
    if pending.get("phase") == "settled":
        if pending.get("result_sha256") != supplied_digest:
            raise ModelRuntimeError("conflicting duplicate resident stage result")
        return _plain(pending["result"])
    if state["phase"] != "waiting" or state.get("wait_reason") != RESIDENT_STAGE_WAIT_REASON:
        raise ModelRuntimeError("resident stage result does not match a stage wait")
    if operation_id != state.get("await_target"):
        raise ModelRuntimeError("resident stage result does not match the wait target")
    request = pending.get("request")
    if not isinstance(request, Mapping):
        raise ModelRuntimeError("resident stage request is unavailable")
    for key in ("operation_id", "source_sha256", "stage", "layer", "position"):
        if result.get(key) != request.get(key):
            raise ModelRuntimeError(f"resident stage result field {key!r} does not match request")
    snapshot = _resident_snapshot(result.get("snapshot"))
    stage = str(request["stage"])
    if stage != "qwen-head" and any(key in result for key in ("token", "eog", "end_of_generation")):
        raise ModelRuntimeError("only qwen-head may return a token")
    if stage == "qwen-head":
        token = result.get("token")
        should_sample = bool(request.get("parameters", {}).get("sample", False))
        if should_sample:
            if isinstance(token, bool) or not isinstance(token, int) or token < 0:
                raise ModelRuntimeError("sampled resident head result lacks a valid token")
            eog = result.get("eog", result.get("end_of_generation", False))
            if not isinstance(eog, bool):
                raise ModelRuntimeError("resident head end-of-generation flag is invalid")
        elif token is not None:
            raise ModelRuntimeError("non-sampling prompt head returned a token")
    _record_graph_site_execution(state, request, result)
    pending["phase"] = "settled"
    pending["result"] = result
    pending["result_sha256"] = supplied_digest
    resident = state["resident_model"]
    if isinstance(result.get("expert_route"), Mapping):
        resident["expert_route"] = _plain(result["expert_route"])
        if stage in {"qwen-route", "qwen-attention-route"}:
            _apply_expert_learning(state, resident["expert_route"])
    if isinstance(result.get("expert_observation"), Mapping):
        _observe_expert_learning(state, result["expert_observation"])
    if isinstance(result.get("expert_selection"), Mapping):
        resident["expert_selection"] = _plain(result["expert_selection"])
    resident["snapshot"] = snapshot
    if stage == "qwen-head" and bool(request.get("parameters", {}).get("prompt", False)):
        _record_resident_prefix_snapshot(
            state,
            position=int(request["position"]),
            token=int(request["token"]),
            snapshot=snapshot,
            head_executed=True,
        )
    if isinstance(result.get("policies"), Mapping):
        resident["policies"] = _plain(result["policies"])
    graph_cursor = int(state["graph_cursor"])
    state["graph_cursor"] = graph_cursor + 1
    state["ledger"]["transitions"] += 1
    state["phase"] = "running"
    state["wait_reason"] = None
    state["await_target"] = None
    if stage == "qwen-head" and bool(request.get("parameters", {}).get("sample", False)):
        sample = {
            **_plain(request["sampler"]),
            "executor": result.get("executor", "cassi-resident-qwen"),
            "backend": result.get("backend"),
        }
        _draft_observe_target(state, int(result["token"]), int(result.get("logical_weight_bytes", 0)))
        speculation = state.get("speculation")
        if isinstance(speculation, MutableMapping) and speculation.get("status") == "active":
            speculation["verified_head_sha256"] = str(request.get("request_sha256", ""))
            speculation["verified_position"] = int(request["position"])
        _complete_token(
            state,
            int(result["token"]),
            sample,
            force_stop=bool(result.get("eog", result.get("end_of_generation", False))),
        )
        resident["token_index"] = len(state["request"]["prompt_tokens"]) + len(state["generated_tokens"]) - 1
        resident["position"] = int(state["continuation"]["token_position"])
    elif stage == "qwen-head":
        resident["token_index"] = int(resident["token_index"]) + 1
        state["continuation"]["token_position"] = (
            int(state["continuation"]["token_position"]) + 1
        )
        resident["position"] = int(state["continuation"]["token_position"])
        if resident["token_index"] < len(state["request"]["prompt_tokens"]):
            state["current_token"] = state["request"]["prompt_tokens"][resident["token_index"]]
        state["graph_cursor"] = 0
    if len(state["operations"]) > _limit(state, "max_pending_operations") * 4:
        settled = [
            key for key, value in state["operations"].items()
            if isinstance(value, Mapping) and value.get("phase") == "settled" and key != operation_id
        ]
        for key in sorted(settled)[: max(0, len(state["operations"]) - _limit(state, "max_pending_operations") * 4)]:
            del state["operations"][key]
    _event(state, "resident-model-stage-admitted", {"operation_id": operation_id, "result_sha256": supplied_digest})
    resident["stage_cursor"] = int(state["graph_cursor"])
    _strip_settled_stage(pending)
    return _plain(result)


_STAGE_IDENTITY_KEYS = (
    "schema",
    "operation_id",
    "model_program_id",
    "source_sha256",
    "stage",
    "layer",
    "token",
    "position",
    "request_sha256",
)


def _strip_settled_stage(pending: MutableMapping[str, Any]) -> None:
    """Release a settled resident stage's request body down to its identity.

    The full request carries the resident snapshot descriptor, the policy block
    and the per-stage parameters, and a generation proposes one stage per graph
    row -- so keeping every settled request made each later dispatch (state
    deepcopy, canonical encode and digest) grow with generation length.  A
    settled row is read only for its schema (branch commit safety), its binding
    digests (duplicate results) and its identity, so the rest is dropped here.
    """

    request = pending.get("request")
    if not isinstance(request, Mapping):
        return
    pending["request"] = {
        key: request[key] for key in _STAGE_IDENTITY_KEYS if key in request
    }


def _resume_native_run(
    state: MutableMapping[str, Any], arguments: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    """Admit a token run as consecutive one-token resumes in position order."""

    operation_id = str(arguments.get("operation_id", ""))
    result = arguments["result"]
    steps = result.get("steps")
    pending = state["operations"].get(operation_id)
    request = pending.get("request") if isinstance(pending, Mapping) else None
    run = request.get("run") if isinstance(request, Mapping) else None
    bound = run.get("bound") if isinstance(run, Mapping) else None
    if (
        not isinstance(run, Mapping)
        or set(result) != {"steps"}
        or not isinstance(steps, list)
        or isinstance(bound, bool)
        or not isinstance(bound, int)
        or not 1 <= len(steps) <= bound
        or not isinstance(run.get("operation_ids"), list)
        or not isinstance(run.get("draws"), list)
        or len(run["operation_ids"]) != bound
        or len(run["draws"]) != bound
        or run["operation_ids"][0] != operation_id
        or run["draws"][0] != request["sampler"]["draw"]
    ):
        raise ModelRuntimeError("native model token run does not match its request")
    continuation_request = {
        key: value for key, value in request.items() if key != "run"
    }
    categorical = request["sampler"]["mode"] == "categorical"
    admitted: Mapping[str, Any] | None = None
    for index, step in enumerate(steps):
        step_operation_id = run["operation_ids"][index]
        if index and step_operation_id not in state["operations"]:
            if state["phase"] != "running":
                raise ModelRuntimeError(
                    "native model token run continues past its admitted end"
                )
            draw = run["draws"][index]
            # Advance the continuation RNG exactly as the one-token proposal
            # of this position would; the pre-drawn value must agree.
            if categorical and _rng_uniform(state) != draw:
                raise ModelRuntimeError("native model token run draw is not the continuation draw")
            step_request = {
                **_plain(continuation_request),
                "operation_id": step_operation_id,
                "tokens": list(state["request"]["prompt_tokens"])
                + list(state["generated_tokens"]),
                "sampler": {**_plain(request["sampler"]), "draw": draw},
            }
            state["operations"][step_operation_id] = {
                "phase": "proposed",
                "request": step_request,
                "result": None,
            }
            state["phase"] = "waiting"
            state["wait_reason"] = "native-model-token"
            state["await_target"] = step_operation_id
            _event(state, "native-model-token-proposed", step_request)
        admitted = _handle_control(
            state,
            {
                "operation": "resume-native-model",
                "operation_id": step_operation_id,
                "result": step,
            },
        )
    return admitted


def _handle_control(state: MutableMapping[str, Any], arguments: Mapping[str, Any]) -> Mapping[str, Any] | None:
    operation = arguments.get("operation")
    if operation is None:
        return None
    if operation == "inspect":
        return computation_view(state, offset=int(arguments.get("offset", 0)), limit=int(arguments.get("limit", 64)))
    if operation == "pause":
        if state["phase"] in {"running", "waiting"}:
            state["paused_from"] = {
                "phase": state["phase"],
                "wait_reason": state.get("wait_reason"),
                "await_target": state.get("await_target"),
            }
            state["phase"] = "paused"
            state["wait_reason"] = str(arguments.get("reason", "requested"))
        return {"status": state["phase"]}
    if operation == "continue":
        if state["phase"] != "paused":
            raise ModelRuntimeError("only a paused model computation can continue")
        paused_from = state.get("paused_from")
        if isinstance(paused_from, Mapping):
            state["phase"] = str(paused_from.get("phase", "running"))
            state["wait_reason"] = paused_from.get("wait_reason")
            state["await_target"] = paused_from.get("await_target")
        else:
            state["phase"] = "running"
            state["wait_reason"] = None
        state["paused_from"] = None
        return {"status": state["phase"]}
    if operation == "cancel":
        if state["phase"] not in {"completed", "faulted", "cancelled"}:
            state["phase"] = "cancelled"
            state["continuation"]["pending_deltas"] = []
            state["active_operation"] = None
            state["result"] = {"schema": RESULT_SCHEMA, "status": "cancelled", "reason": str(arguments.get("reason", "cancelled"))}
            _event(state, "model-cancelled", {"reason": state["result"]["reason"]})
        return _plain(state["result"])
    if operation == "resume-external":
        operation_id = str(arguments.get("operation_id", ""))
        pending = state["operations"].get(operation_id)
        if not isinstance(pending, MutableMapping):
            raise ModelRuntimeError("external model operation is unavailable")
        supplied_digest = digest_value(arguments.get("result"))
        if pending["phase"] == "settled":
            if pending.get("result_sha256") != supplied_digest:
                raise ModelRuntimeError("conflicting duplicate external model result")
            return _plain(pending["result"])
        if state["phase"] != "waiting" or operation_id != state.get("await_target"):
            raise ModelRuntimeError("external model result does not match the wait target")
        result = _plain(arguments.get("result"))
        if not isinstance(result, Mapping):
            raise ModelRuntimeError("external model result must be a mapping")
        pending["phase"] = "settled"
        pending["result"] = result
        pending["result_sha256"] = supplied_digest
        state["phase"] = "completed"
        state["wait_reason"] = None
        state["await_target"] = None
        state["result"] = {
            "schema": RESULT_SCHEMA,
            "status": "completed",
            "program_id": state["package"]["program"]["program_id"],
            "external_result": result,
            "placement": {"requested": state["placement"]["requested"], "actual": "external-model", "resident": False},
            "logical_work": int(state["ledger"]["transitions"]),
        }
        _event(state, "external-model-admitted", {"operation_id": operation_id, "result_sha256": supplied_digest})
        return _plain(state["result"])
    if operation in {"resume-resident-model", "resume-resident-model-and-advance"}:
        return _resume_resident_stage(state, arguments)
    if operation == "resume-native-model":
        operation_id = str(arguments.get("operation_id", ""))
        pending = state["operations"].get(operation_id)
        if not isinstance(pending, MutableMapping):
            raise ModelRuntimeError("native model token operation is unavailable")
        result = arguments.get("result")
        if not isinstance(result, Mapping):
            raise ModelRuntimeError("native model token result must be a mapping")
        if "steps" in result:
            return _resume_native_run(state, arguments)
        if result.get("status") == "graph-site-rejected":
            raise ModelRuntimeError(
                "refused native graph-site candidate cannot admit a model token"
            )
        request = pending.get("request")
        if not isinstance(request, Mapping):
            raise ModelRuntimeError("native model token request is unavailable")
        request_tokens = request.get("tokens")
        request_sampler = request.get("sampler")
        if not isinstance(request_tokens, list) or not isinstance(request_sampler, Mapping):
            raise ModelRuntimeError("native model token request is invalid")
        identity = state.get("identity")
        if not isinstance(identity, Mapping) or any(
            not isinstance(identity.get(name), str) or not identity.get(name)
            for name in ("owner_id", "member_id", "operation_id")
        ):
            raise ModelRuntimeError("native model identity is unavailable")
        expected_sequence_id = ":".join(
            str(identity[name]) for name in ("owner_id", "member_id", "operation_id")
        )
        graph_provisional = result.get("status") == "model-provisional"
        token = (
            result.get("selected_token_id")
            if graph_provisional
            else result.get("token")
        )
        graph_rejection = result.get("graph_site_rejection")
        token_count = result.get("token_count")
        end_of_generation = result.get("end_of_generation")
        replay_sha256 = result.get("replay_sha256")
        stage_trace_sha256 = result.get("stage_trace_sha256")
        exact_stages = result.get("exact_stages")
        embedding_stages = result.get("embedding_stages")
        attention_stages = result.get("attention_stages")
        ffn_stages = result.get("ffn_stages")
        head_stages = result.get("head_stages")
        ggml_nodes = result.get("ggml_nodes")
        logical_weight_bytes = result.get("logical_weight_bytes")
        expected_count = (
            len(request_tokens) + 1
            if isinstance(request_tokens, list)
            else -1
        )
        tokenizer = state["package"]["tokenizer"]
        vocab_size = int(tokenizer.get("vocab_size", tokenizer.get("token_count", 0)))
        if graph_provisional:
            ticket = result.get("graph_site_ticket")
            receipt = result.get("graph_site_receipt")
            receipt_sha256 = result.get("graph_site_receipt_sha256")
            native_receipt_sha256 = result.get(
                "native_graph_site_receipt_sha256"
            )
            wire_sha256 = result.get("graph_receipt_wire_sha256")
            native_wire_sha256 = result.get(
                "native_graph_site_receipt_wire_sha256"
            )
            if (
                result.get("accepted") is not False
                or result.get("provisional") is not True
                or "token" in result
                or "accepted_token_id" in result
                or graph_rejection is not None
                or not isinstance(ticket, Mapping)
                or not isinstance(receipt, Mapping)
                or ticket.get("task_id") != request.get("native_task_id")
                or ticket.get("operation_id") != operation_id
                or ticket.get("source_sha256") != request.get("source_sha256")
                or ticket.get("sampler") != dict(request_sampler)
                or result.get("task_id") != request.get("native_task_id")
                or result.get("native_operation_id") != operation_id
                or result.get("source_sha256") != request.get("source_sha256")
                or result.get("input_tokens") != request_tokens
                or result.get("sampler") != dict(request_sampler)
                or result.get("sequence_id") != ticket.get("sequence_id")
                or result.get("sequence_id") != expected_sequence_id
                or result.get("sequence_id") != receipt.get("sequence_id")
                or result.get("field_candidate_id") != result.get("candidate_id")
                or result.get("field_candidate_id")
                != receipt.get("field_candidate_id")
                or result.get("ticket_id") != ticket.get("ticket_id")
                or ticket.get("sampler_sha256") != digest_value(dict(request_sampler))
                or result.get("position") != len(request_tokens)
                or result.get("input_tokens_sha256")
                != receipt.get("input_tokens_sha256")
                or receipt.get("schema")
                != "cassifi.native-graph-site-receipt.v1"
                or receipt.get("position") != len(request_tokens)
                or receipt.get("ticket_sha256") != ticket.get("ticket_sha256")
                or receipt.get("sampler_sha256")
                != digest_value(dict(request_sampler))
                or receipt.get("sampler") != dict(request_sampler)
                or receipt.get("input_token_count") != len(request_tokens)
                or receipt.get("admitted") is not True
                or receipt.get("selected_token_id") != token
                or receipt.get("task_id") != request.get("native_task_id")
                or receipt.get("native_operation_id") != operation_id
                or receipt.get("source_sha256") != request.get("source_sha256")
                or receipt.get("ticket_id") != ticket.get("ticket_id")
                or receipt_sha256 != native_receipt_sha256
                or digest_value(dict(receipt)) != receipt_sha256
                or not isinstance(wire_sha256, str)
                or wire_sha256 != native_wire_sha256
            ):
                raise ModelRuntimeError(
                    "provisional native graph-site result disagrees with its request or receipt"
                )
        elif graph_rejection is not None:
            if (
                not isinstance(graph_rejection, Mapping)
                or set(graph_rejection)
                != {"receipt", "receipt_sha256", "wire_sha256"}
            ):
                raise ModelRuntimeError("native graph-site rejection evidence is invalid")
            receipt = graph_rejection.get("receipt")
            receipt_sha256 = graph_rejection.get("receipt_sha256")
            wire_sha256 = graph_rejection.get("wire_sha256")
            if (
                not isinstance(receipt, Mapping)
                or receipt.get("schema")
                != "cassifi.native-graph-site-receipt.v1"
                or receipt.get("sequence_id") != expected_sequence_id
                or receipt.get("admitted") is not False
                or receipt.get("selected_token_id") != -1
                or receipt.get("task_id") != request.get("native_task_id")
                or receipt.get("native_operation_id") != operation_id
                or receipt.get("source_sha256") != request.get("source_sha256")
                or receipt.get("sampler") != dict(request_sampler)
                or receipt.get("sampler_sha256") != digest_value(dict(request_sampler))
                or receipt.get("input_token_count") != len(request_tokens)
                or not isinstance(receipt.get("sequence_id"), str)
                or not receipt.get("sequence_id")
                or not isinstance(receipt.get("refusal"), str)
                or not receipt.get("refusal")
                or not isinstance(receipt_sha256, str)
                or digest_value(dict(receipt)) != receipt_sha256
                or not isinstance(wire_sha256, str)
                or len(wire_sha256) != 64
                or any(character not in "0123456789abcdef" for character in wire_sha256)
            ):
                raise ModelRuntimeError(
                    "native graph-site rejection receipt does not match its request"
                )
            graph_rejection = {
                "receipt": _plain(receipt),
                "receipt_sha256": receipt_sha256,
                "wire_sha256": wire_sha256,
            }
        stage_counts = (
            exact_stages,
            embedding_stages,
            attention_stages,
            ffn_stages,
            head_stages,
            ggml_nodes,
            logical_weight_bytes,
        )
        if (
            isinstance(token, bool)
            or not isinstance(token, int)
            or not 0 <= token < vocab_size
            or isinstance(token_count, bool)
            or token_count != expected_count
            or not isinstance(end_of_generation, bool)
            or not isinstance(replay_sha256, str)
            or len(replay_sha256) != 64
            or any(character not in "0123456789abcdef" for character in replay_sha256)
            or not isinstance(stage_trace_sha256, str)
            or len(stage_trace_sha256) != 64
            or any(character not in "0123456789abcdef" for character in stage_trace_sha256)
            or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in stage_counts)
            or embedding_stages < 1
            or head_stages != 1
            or attention_stages != ffn_stages
            or exact_stages != embedding_stages + attention_stages + ffn_stages + head_stages
            or ggml_nodes < exact_stages
            or logical_weight_bytes < 1
        ):
            raise ModelRuntimeError("native model token result is invalid")
        stage_trace = {
            "schema": "cassi.exact-model-stage-trace.v1",
            "sha256": stage_trace_sha256,
            "exact_stages": exact_stages,
            "embedding_stages": embedding_stages,
            "attention_stages": attention_stages,
            "ffn_stages": ffn_stages,
            "head_stages": head_stages,
            "ggml_nodes": ggml_nodes,
            "logical_weight_bytes": logical_weight_bytes,
        }
        admitted = {
            "token": token,
            "token_count": token_count,
            "end_of_generation": end_of_generation,
            "replay_sha256": replay_sha256,
            "stage_trace": stage_trace,
        }
        if graph_rejection is not None:
            admitted["graph_site_rejection"] = graph_rejection
        supplied_digest = digest_value(admitted)
        if pending.get("phase") == "settled":
            if pending.get("result_sha256") != supplied_digest:
                raise ModelRuntimeError("conflicting duplicate native model result")
            return _plain(pending["result"])
        if (
            pending.get("phase") != "proposed"
            or state["phase"] != "waiting"
            or state.get("wait_reason") != "native-model-token"
            or operation_id != state.get("await_target")
        ):
            raise ModelRuntimeError("native model token does not match the wait target")
        pending["phase"] = "settled"
        pending["result"] = admitted
        pending["result_sha256"] = supplied_digest
        state["phase"] = "running"
        state["wait_reason"] = None
        state["await_target"] = None
        sample = {
            **_plain(pending["request"]["sampler"]),
            "replay_sha256": replay_sha256,
            "stage_trace": _plain(stage_trace),
        }
        _complete_token(
            state,
            token,
            sample,
            force_stop=end_of_generation,
        )
        _event(
            state,
            "native-model-token-admitted",
            {
                "operation_id": operation_id,
                "token": token,
                "replay_sha256": replay_sha256,
                "stage_trace_sha256": stage_trace_sha256,
                "exact_stages": exact_stages,
            },
        )
        return _plain(state.get("result") or admitted)
    if operation == "begin-branch":
        return _begin_branch(state, arguments)
    if operation == "rollback":
        return _rollback_branch(state, str(arguments["branch_id"]))
    if operation == "commit":
        return _commit_branch(state, str(arguments["branch_id"]), arguments)
    if operation == "begin-speculation":
        return _begin_speculation(state, arguments)
    raise ModelRuntimeError("model runtime operation is unsupported")


def _step(state: MutableMapping[str, Any]) -> str:
    if state["phase"] in {"waiting", "paused", "resource-paused"}:
        return "blocked"
    if state["phase"] in {"completed", "faulted", "cancelled"}:
        return "done" if state["phase"] == "completed" else "fault"
    graph = state["package"]["graph"]
    cursor = int(state["graph_cursor"])
    if cursor >= len(graph):
        _apply_pending_deltas(state)
        state["phase"] = "completed"
        state["result"] = {
            "schema": RESULT_SCHEMA,
            "status": "completed",
            "program_id": state["package"]["program"]["program_id"],
            "outputs": {
                name: _plain(state["tensors"][name])
                for name in state["request"]["output_tensors"]
                if name in state["tensors"]
            },
            "placement": _plain(state["placement"]),
            "logical_work": int(state["ledger"]["transitions"]),
        }
        return "done"
    operation = graph[cursor]
    state["continuation"]["block_cursor"] = cursor
    state["continuation"]["operation_cursor"] = int(state.get("active_operation", {}).get("cursor", 0)) if isinstance(state.get("active_operation"), Mapping) else 0
    completed = _execute_operation(state, operation)
    if completed and state["phase"] == "running" and operation["op"] != "sample":
        state["graph_cursor"] = cursor + 1
    state["ledger"]["transitions"] += 1
    return "blocked" if state["phase"] in {"waiting", "paused", "resource-paused"} else "done" if state["phase"] == "completed" else "fault" if state["phase"] in {"faulted", "cancelled"} else "running"


def _initial_resident_policies(model: ModelPackage, owner_id: str) -> Mapping[str, Any]:
    """Create canonical field policies bound to the imported model identity."""
    graph = model.graph
    source_sha256 = str(graph[0]["parameters"].get("source_sha256", ""))
    if not (len(source_sha256) == 64 and all(char in "0123456789abcdef" for char in source_sha256)):
        return {"experts": {}, "drafting": {}}
    try:
        from .draft_learning import initial_policy as initial_draft_policy
        from .graph_site import initial_state as initial_graph_site_state
        from .expert_learning import initial_state as initial_expert_state
        metadata = model.numerical_profile.get("model_metadata", {})
        layer_ids = [
            int(operation["parameters"]["layer"])
            for operation in graph
            if operation["parameters"].get("layer") is not None
        ]
        layer_count = max(layer_ids, default=0) + 1
        expert_count = next(
            (
                int(metadata[key]) for key in (
                    "qwen35moe.expert_count", "qwen35.expert_count",
                    "general.expert_count",
                ) if isinstance(metadata.get(key), int) and not isinstance(metadata.get(key), bool)
            ),
            1,
        )
        experts = initial_expert_state(
            source_sha256,
            max(1, layer_count),
            max(1, expert_count),
            max(1, int(metadata.get("general.expert_capacity_bytes", 1 << 30))),
        ) if any(
            operation["op"] in {"qwen-route", "qwen-attention-route"}
            for operation in graph
        ) else {}
        drafting = initial_draft_policy(
            model_program_id=model.program.program_id,
            source_sha256=source_sha256,
            owner_id=owner_id,
        )
        return {
            "experts": experts,
            "drafting": drafting,
            "graph_sites": initial_graph_site_state(source_sha256, "unknown"),
        }
    except (TypeError, ValueError, KeyError) as exc:
        raise ModelRuntimeError("resident model policy initialization failed") from exc


def _backend_selection(
    requested: str,
    *,
    has_native: bool,
    resident_graph: bool,
    has_resident_qwen: bool,
    bounded_work: int | None,
) -> dict[str, Any]:
    """Resolve one whole-request backend through the measured-cost policy.

    Explicit policies pass through untouched.  ``auto`` consults the shared
    measured cost ledger and probed capability; without complete measured
    evidence it keeps the historical default for the graph's lane.  The
    native Vulkan lane runs only when the native runtime probe reports the
    model runtime ready; a resident Qwen graph has no measured Vulkan lane
    at this runtime seam, so it stays on its existing CPU choice unless
    measured evidence says otherwise.
    """

    import backend_policy

    capability = backend_policy.observed_capability() or {}
    if not resident_graph:
        return {
            "requested": requested,
            "selected": "external-model",
            "reason": "explicit-policy" if requested != backend_policy.AUTO_POLICY
            else "external-lane-existing-choice",
            "evidence": None,
            "candidates": [],
            "capability": capability,
        }
    if has_native:
        supported = [
            name for name in ("native-cpu", "vulkan")
            if name != "vulkan" or capability.get("available")
        ]
        default = "vulkan" if "vulkan" in supported else "native-cpu"
    else:
        supported = ["logical-cpu"]
        default = "logical-cpu"
    return backend_policy.select_backend(
        requested,
        supported=supported,
        default=default,
        scope="model-transformer",
        bounded_work=bounded_work,
        capability=capability,
    )


def initial_state(
    package: ModelPackage | Mapping[str, Any],
    *,
    prompt_tokens: Sequence[int],
    owner_id: str,
    member_id: str,
    lineage_id: str,
    operation_id: str,
    scope_id: str = "model",
    max_new_tokens: int = 1,
    stop_tokens: Sequence[int] = (),
    sampler: Mapping[str, Any] | None = None,
    output_tensors: Sequence[str] = (),
    limits: Mapping[str, int] | None = None,
    backend_policy: str = "auto",
    rng_seed: int = 1,
    graph_site_modes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    model = package if isinstance(package, ModelPackage) else ModelPackage.from_dict(package)
    resident_policies = dict(_initial_resident_policies(model, owner_id))
    graph_sites = resident_policies.pop("graph_sites", {})
    tokens = [_positive(item, "prompt token", allow_zero=True) for item in prompt_tokens]
    if not tokens:
        raise ModelRuntimeError("prompt_tokens cannot be empty")
    resolved_limits = dict(DEFAULT_LIMITS)
    for name, value in dict(limits or {}).items():
        if name not in resolved_limits:
            raise ModelRuntimeError(f"unknown model limit {name!r}")
        resolved_limits[name] = _positive(value, name)
    requested_tokens = _positive(max_new_tokens, "max_new_tokens")
    if requested_tokens > resolved_limits["max_new_tokens"]:
        raise ModelRuntimeError("max_new_tokens exceeds model limit")
    if backend_policy not in {"auto", "logical-cpu", "native-cpu", "vulkan", "external-model"}:
        raise ModelRuntimeError("model backend policy is invalid")
    from .graph_site import SPECIALISTS
    if not isinstance(graph_site_modes, (Mapping, type(None))):
        raise ModelRuntimeError("graph-site modes must be a mapping")
    configured_modes = dict(graph_site_modes or {})
    if any(name not in SPECIALISTS or mode not in {"auto", "observe", "assist", "replace", "propose", "off"}
           for name, mode in configured_modes.items()):
        raise ModelRuntimeError("graph-site modes must name supported specialists and verbs")
    has_external = any(operation["op"] == "external-model" for operation in model.graph)
    has_native = any(operation["op"] == "native-transformer" for operation in model.graph)
    has_resident_qwen = _resident_qwen_graph({"package": {"graph": model.graph}})
    if has_external and (has_native or has_resident_qwen):
        raise ModelRuntimeError("a model graph cannot mix resident and external transformer lanes")
    if has_native and backend_policy in {"logical-cpu", "external-model"}:
        raise ModelRuntimeError("native transformer requires native-cpu, vulkan, or auto placement")
    if has_resident_qwen and backend_policy == "external-model":
        raise ModelRuntimeError("resident Qwen graph cannot use external-model placement")
    if len(tokens) > resolved_limits["max_attention_positions"]:
        raise ModelRuntimeError("prompt token history exceeds the model context limit")
    resident_graph = not has_external
    phase = "running"
    wait_reason = None
    selection = _backend_selection(
        backend_policy,
        has_native=has_native,
        resident_graph=resident_graph,
        has_resident_qwen=has_resident_qwen,
        bounded_work=requested_tokens,
    )
    actual = selection["selected"]
    if actual not in {
        "native-cpu", "native-cpu-continuation", "vulkan", "logical-cpu", "external-model",
    }:
        raise ModelRuntimeError("resolved model backend placement is invalid")
    if has_native and actual in {"logical-cpu", "external-model"}:
        raise ModelRuntimeError("native transformer requires native-cpu, vulkan, or auto placement")
    if has_resident_qwen and actual == "external-model":
        raise ModelRuntimeError("resident Qwen graph cannot use external-model placement")
    runtime_package = model.as_dict()
    runtime_tensors = _plain(model.tensors)
    immutable_tensors = sorted(model.tensors)
    tensor_catalog = {
        "manifest_sha256": model.program.tensor_manifest_sha256,
        "tensor_count": len(model.tensors),
        "detached": False,
    }
    if has_native or has_resident_qwen or has_external:
        tokenizer = dict(model.tokenizer)
        raw_vocab_size = tokenizer.get(
            "vocab_size", tokenizer.get("token_count")
        )
        if (
            isinstance(raw_vocab_size, bool)
            or not isinstance(raw_vocab_size, int)
            or raw_vocab_size < 1
        ):
            raw_tokens = tokenizer.get("tokens")
            if not isinstance(raw_tokens, (list, tuple, dict)):
                raise ModelRuntimeError(
                    "detached model tokenizer has no vocabulary size"
                )
            raw_vocab_size = len(raw_tokens)
        runtime_package = {
            **runtime_package,
            "tensors": {},
            "tokenizer": {
                "schema": "cassifi.detached-model-tokenizer.v1",
                "vocab_size": int(raw_vocab_size),
                "token_count": int(raw_vocab_size),
                "tokenizer_sha256": model.program.tokenizer_sha256,
                "detached": True,
            },
        }
        runtime_tensors = {}
        immutable_tensors = []
        tensor_catalog["detached"] = True
    state: dict[str, Any] = {
        "schema": RUNTIME_SCHEMA,
        "identity": {
            "owner_id": str(owner_id),
            "member_id": str(member_id),
            "operation_id": str(operation_id),
            "scope_id": str(scope_id),
        },
        "package": runtime_package,
        "package_sha256": model.sha256,
        "tensor_catalog": tensor_catalog,
        "tensors": runtime_tensors,
        "immutable_tensors": immutable_tensors,
        "memory": {"attention": {}, "recurrent": {}, "convolution": {}},
        "request": {
            "prompt_tokens": tokens,
            "max_new_tokens": requested_tokens,
            "stop_tokens": [_positive(item, "stop token", allow_zero=True) for item in stop_tokens],
            "output_tensors": [str(item) for item in output_tensors],
            "graph_site_modes": configured_modes,
        },
        "current_token": tokens[0] if has_resident_qwen else tokens[-1],
        "generated_tokens": [],
        "resident_model": {
            "schema": "cassifi.resident-model-state.v1",
            "model_program_id": model.program.program_id,
            "source_sha256": str(model.graph[0]["parameters"].get("source_sha256", "")),
            "stage_cursor": 0,
            "token_index": 0 if has_resident_qwen else len(tokens) - 1,
            "position": 0 if has_resident_qwen else len(tokens) - 1,
            "snapshot": {},
            "expert_route": None,
            "expert_selection": None,
            "expert_context": {},
            "graph_sites": graph_sites,
            "graph_site_generation": 0,
            "draft_target_cost_units": 0,
            "draft_proposal": None,
            "draft_target_tokens": [],
            "draft_comparison": None,
            "draft_attempts": [],
            "policies": resident_policies,
            "prefix_snapshots": [],
        },
        "graph_cursor": 0,
        "active_operation": None,
        "continuation": {
            "schema": ModelContinuation.SCHEMA,
            "continuation_id": f"{operation_id}:continuation",
            "block_cursor": 0,
            "operation_cursor": 0,
            "token_position": 0 if has_resident_qwen else len(tokens) - 1,
            "live_activation_refs": [],
            "attention_roots": [],
            "recurrent_roots": [],
            "sampler_state": _plain(dict(sampler or {"mode": "greedy"})),
            "rng_state": {"algorithm": "xorshift64star", "state": str(_positive(rng_seed, "rng_seed"))},
            "pending_deltas": [],
            "checkpoint_sha256": "0" * 64,
        },
        "placement": {
            "requested": backend_policy,
            "actual": actual,
            "resident": resident_graph and actual != "external-model",
            "selection": selection,
        },
        "operations": {},
        "paused_from": None,
        "await_target": None,
        "branches": {},
        "branch_stack": [],
        "speculation": None,
        "phase": phase,
        "wait_reason": wait_reason,
        "result": None,
        "events": [],
        "counters": {"event": 1, "operation": 1, "branch": 1},
        "limits": resolved_limits,
        "ledger": {"transitions": 0, "scalar_operations": 0, "tokens": 0, "discarded_work": 0},
    }
    if has_resident_qwen:
        source_sha256 = state["resident_model"]["source_sha256"]
        if (
            not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in source_sha256)
        ):
            raise ModelRuntimeError("resident Qwen graph lacks an exact GGUF source identity")
    state["continuation"]["checkpoint_sha256"] = digest_value(_snapshot(state))
    canonical_json_bytes(state)
    return state


def advance(
    state: Mapping[str, Any],
    arguments: Mapping[str, Any] | None,
    quantum: int,
    *,
    _owned_state: bool = False,
) -> tuple[dict[str, Any], str, int, Mapping[str, Any] | None, tuple[Mapping[str, Any], ...]]:
    if not isinstance(state, Mapping) or state.get("schema") != RUNTIME_SCHEMA:
        raise ModelRuntimeError("field model runtime state is invalid")
    quantum = _positive(quantum, "model quantum")
    if _owned_state:
        if not isinstance(state, dict):
            raise ModelRuntimeError("owned model state must be a mutable object")
        current = state
    else:
        current = copy.deepcopy(dict(state))
    event_sequence = int(current["counters"]["event"])
    control = _handle_control(current, dict(arguments or {}))
    control_operation = (arguments or {}).get("operation")
    combined_resume = control_operation == "resume-resident-model-and-advance"
    if combined_resume and quantum < 2:
        raise ModelRuntimeError("combined resident model resume requires two work units")
    control_only = {
        "inspect",
        "pause",
        "continue",
        "cancel",
        "resume-resident-model",
        "begin-branch",
        "rollback",
        "commit",
        "begin-speculation",
    }
    work = 1 if combined_resume else 0
    status = "running"
    if control is not None and (
        control_operation in control_only
        or (combined_resume and current["phase"] != "running")
    ):
        if current["phase"] == "completed":
            status = "done"
        elif current["phase"] in {"faulted", "cancelled"}:
            status = "fault"
        elif current["phase"] in {"waiting", "paused", "resource-paused"}:
            status = "blocked"
    else:
        stepped = False
        while work < quantum:
            try:
                status = _step(current)
                stepped = True
            except (ModelRuntimeError, ModelRecordError, ArithmeticError, KeyError, IndexError, TypeError, ValueError) as exc:
                current["continuation"]["pending_deltas"] = []
                current["active_operation"] = None
                current["phase"] = "faulted"
                current["result"] = {
                    "schema": RESULT_SCHEMA,
                    "status": "faulted",
                    "program_id": current["package"]["program"]["program_id"],
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "graph_cursor": int(current["graph_cursor"]),
                    "operation_id": current["package"]["graph"][int(current["graph_cursor"])]["operation_id"] if int(current["graph_cursor"]) < len(current["package"]["graph"]) else None,
                    "placement": _plain(current["placement"]),
                }
                _event(current, "model-faulted", current["result"])
                status = "fault"
            work += 1
            if status != "running":
                break
        if stepped:
            # Only the quantum boundary is persisted or resumed, so one
            # checkpoint identity per advance names the retained state.
            current["continuation"]["checkpoint_sha256"] = digest_value(
                _snapshot(current, detach=False)
            )
    if status == "running":
        status = "yield"
    elif status == "blocked":
        status = "blocked"
    elif status == "done":
        status = "done"
    elif status == "fault":
        status = "fault"
    output = current.get("result") or control
    events = tuple(
        copy.deepcopy(
            [
                event
                for event in current["events"]
                if int(event["sequence"]) >= event_sequence
            ]
        )
    )
    # The owner-held regional KernelResult canonicalizes this same state.
    # Standalone model advances keep their direct boundary check.
    if not _owned_state:
        canonical_json_bytes(current)
    return current, status, max(work, 1 if control is not None else 0), output, events


def computation_view(state: Mapping[str, Any], *, offset: int = 0, limit: int = 64) -> Mapping[str, Any]:
    offset = _positive(offset, "offset", allow_zero=True)
    limit = _positive(limit, "limit")
    tensor_names = sorted(state["tensors"])
    selected = tensor_names[offset : offset + limit]
    continuation = ModelContinuation(
        continuation_id=str(state["continuation"]["continuation_id"]),
        token_position=int(state["continuation"]["token_position"]),
        block_cursor=int(state["continuation"]["block_cursor"]),
        operation_cursor=int(state["continuation"]["operation_cursor"]),
        live_activation_refs=tuple(str(item) for item in state["continuation"]["live_activation_refs"]),
        attention_roots=tuple(str(item) for item in state["continuation"]["attention_roots"]),
        recurrent_roots=tuple(str(item) for item in state["continuation"]["recurrent_roots"]),
        sampler_state=state["continuation"]["sampler_state"],
        rng_state=state["continuation"]["rng_state"],
        pending_deltas=tuple(state["continuation"]["pending_deltas"]),
        checkpoint_sha256=str(state["continuation"]["checkpoint_sha256"]),
    )
    return {
        "schema": "cassifi.model-computation-view.v1",
        "computation_id": state["identity"]["operation_id"],
        "version": int(state["ledger"]["transitions"]) + 1,
        "owner_id": state["identity"]["owner_id"],
        "program_id": state["package"]["program"]["program_id"],
        "program_identity": {
            "package_sha256": state["package_sha256"],
            "graph_sha256": state["package"]["program"]["graph_sha256"],
            "tensor_manifest_sha256": state["package"]["program"]["tensor_manifest_sha256"],
            "tokenizer_sha256": state["package"]["program"]["tokenizer_sha256"],
        },
        "status": state["phase"],
        "stage": state["package"]["graph"][int(state["graph_cursor"])]["stage"] if int(state["graph_cursor"]) < len(state["package"]["graph"]) else "return",
        "placement": _plain(state["placement"]),
        "continuation": continuation.as_dict(),
        "resident_model": _plain(state.get("resident_model")),
        "tensor_views": {name: _plain(state["tensors"][name]["view"]) for name in selected},
        "branches": [{key: _plain(value) for key, value in branch.items() if key != "snapshot"} for _, branch in sorted(state["branches"].items())],
        "speculation": _plain(state.get("speculation")),
        "effects": [_plain(value) for _, value in sorted(state["operations"].items())],
        "result": _plain(state.get("result")),
        "unfinished_reason": state.get("wait_reason") if state["phase"] != "running" else "finite-quantum",
        "page": {"offset": offset, "limit": limit, "returned": len(selected), "total": len(tensor_names)},
    }


__all__ = [
    "DEFAULT_LIMITS",
    "ModelRuntimeError",
    "RESIDENT_STAGE_REQUEST_SCHEMA",
    "RESIDENT_STAGE_RESULT_SCHEMA",
    "RESIDENT_STAGE_WAIT_REASON",
    "RESIDENT_PREFIX_REUSE_SCHEMA",
    "seed_resident_prefix",
    "RESULT_SCHEMA",
    "RUNTIME_SCHEMA",
    "advance",
    "computation_view",
    "initial_state",
]
