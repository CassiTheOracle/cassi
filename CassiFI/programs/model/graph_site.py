"""Owner-held acquisition and admission for typed resident graph sites."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import numbers as numeric_types
import struct
from typing import Any, Mapping

SCHEMA = "cassifi.graph-site-policy.v1"
INVOCATION_SCHEMA = "cassifi.graph-site-invocation.v1"
CANDIDATE_SCHEMA = "cassifi.graph-site-candidate.v1"
NATIVE_PROGRAM_SCHEMA = "cassifi.graph-site-native-program.v1"
TRAINING_SCHEMA = "cassifi.graph-site-training.v1"
ABSTENTION_SCHEMA = "cassifi.graph-site-abstention.v1"
OBSERVATION_SCHEMA = "cassifi.graph-site-observation.v1"
METHOD_SCHEMA = "cassifi.graph-site-low-rank-affine.v1"
NEUTRAL_MEMBRANE_PROFILE = {"mode": "none", "state_effects": "none"}
NEUTRAL_FIELD_EPOCH_SHA256 = hashlib.sha256(b"").hexdigest()
SPECIALISTS = ("expert-synthesis", "recurrent-dynamics", "attention-memory", "execution-choice")
VERBS = ("observe", "assist", "replace", "propose")
# Specialists that deploy an admitted method unless the task configures a verb.
# Attention memory and execution choice deploy only when a task asks for them.
DEFAULT_AUTO_SPECIALISTS = ("expert-synthesis", "recurrent-dynamics")
# Executor stage hosting each specialist's native subgraph. Dense Qwen3.5 runs
# attention and FFN as one layer stage whose first subgraph is the recurrent
# branch; MoE Qwen3.5 splits attention/route from the expert stage.
SITE_STAGES = {
    ("qwen35moe", "expert-synthesis"): "qwen-experts",
    ("qwen35moe", "recurrent-dynamics"): "qwen-attention-route",
    ("qwen35moe", "attention-memory"): "qwen-attention-route",
    ("qwen35moe", "execution-choice"): "qwen-head",
    ("qwen35", "recurrent-dynamics"): "qwen-layer",
}
MAX_EVIDENCE = 128
MAX_F32 = 3.4028234663852886e38
MIN_ADMISSION_SUPPORT = 8
MAX_ERROR = 0.02
MAX_TRAINING_INPUT_VALUES = 8192
MAX_TRAINING_OUTPUT_VALUES = 524288
MAX_NATIVE_PROGRAM_VALUES = 1 << 20
MAX_LOCAL_RECURRENT_METHODS = 8
LOCAL_RECURRENT_RADIUS_FRACTION = 0.5
LOCAL_RECURRENT_DIRECTION_EPSILON = 1e-6
MAX_LOCAL_TRAJECTORY_SAMPLES = 8

 

class GraphSiteError(ValueError):
    """A graph-site invocation, candidate, or policy is not canonical."""


def configured_mode(modes: Any, specialist: str) -> str:
    """Return a task's verb for one specialist, with the shared default."""
    if isinstance(modes, Mapping) and specialist in modes:
        return str(modes[specialist])
    return "auto" if specialist in DEFAULT_AUTO_SPECIALISTS else "off"


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise GraphSiteError("graph-site values must be finite")
        return value
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    raise GraphSiteError("graph-site state must be JSON-canonical")


def _digest(value: Any) -> str:
    try:
        raw = json.dumps(_plain(value), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GraphSiteError("graph-site value is not canonical JSON") from exc
    return hashlib.sha256(raw).hexdigest()


def _shape_width(shape: Any) -> int:
    if not isinstance(shape, (list, tuple)) or not shape:
        raise GraphSiteError("graph-site tensor shape is required")
    width = 1
    for dimension in shape:
        if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
            raise GraphSiteError("graph-site tensor dimensions must be positive integers")
        width *= dimension
    return width


def _policy_layout(layout: Any, specialist: str, layer: int | None) -> Any:
    """Keep the recurrent convolution channel contract across token positions."""
    result = _plain(layout)
    if specialist == "recurrent-dynamics" and isinstance(result, dict):
        history = result.get(f"conv_history.{layer}")
        if isinstance(history, dict) and isinstance(history.get("shape"), list):
            history["shape"] = [None, history["shape"][-1]]
    return result

def _matrix(value: Any, rows: int, columns: int, name: str) -> None:
    if not isinstance(value, (list, tuple)) or len(value) != rows:
        raise GraphSiteError(f"graph-site {name} row dimension is invalid")
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != columns:
            raise GraphSiteError(f"graph-site {name} column dimension is invalid")
        if any(isinstance(item, bool) or not isinstance(item, (int, float))
               or not math.isfinite(item) or abs(item) > MAX_F32 for item in row):
            raise GraphSiteError(f"graph-site {name} values must be finite f32 numbers")


def _validate_affine_fields(method: Mapping[str, Any], in_width: int, out_width: int,
                            label: str) -> int:
    rank = method.get("rank")
    if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 16:
        raise GraphSiteError(f"graph-site {label} rank must be between one and sixteen")
    _matrix(method.get("A"), in_width, rank, label)
    _matrix(method.get("B"), rank, out_width, label)
    bias = method.get("bias")
    if (not isinstance(bias, (list, tuple)) or len(bias) != out_width
            or any(isinstance(item, bool) or not isinstance(item, (int, float))
                   or not math.isfinite(item) or abs(item) > MAX_F32 for item in bias)):
        raise GraphSiteError(f"graph-site {label} bias dimension or values are invalid")
    return rank


def _validate_input_support(support: Any, in_width: int, rank: int, label: str) -> None:
    if not isinstance(support, Mapping):
        raise GraphSiteError(f"graph-site {label} input support is required")
    anchor = support.get("anchor")
    if anchor is None:
        if rank != 1:
            raise GraphSiteError(
                f"graph-site {label} input support needs an anchor for rank above one")
    elif (not isinstance(anchor, (list, tuple)) or len(anchor) != in_width
          or any(isinstance(value, bool) or not isinstance(value, (int, float))
                 or not math.isfinite(value) or abs(value) > MAX_F32 for value in anchor)):
        raise GraphSiteError(f"graph-site {label} input support anchor is invalid")
    for name in ("radius", "anchor_norm"):
        value = support.get(name)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise GraphSiteError(f"graph-site {label} input support {name} is invalid")


def _validate_recurrent_successor(method: Mapping[str, Any], in_width: int,
                                  out_width: int) -> None:
    layout = method.get("successor_shapes")
    if not isinstance(layout, Mapping) or len(layout) != 3 or "hidden" not in layout:
        raise GraphSiteError("recurrent method must describe its complete successor state")
    conv = [name for name in layout if name.startswith("conv_history.")]
    state = [name for name in layout if name.startswith("recurrent_state.")]
    suffix = conv[0].partition(".")[2] if len(conv) == 1 else ""
    if (len(conv) != 1 or len(state) != 1 or not suffix
            or any(character not in "0123456789" for character in suffix)
            or state[0].partition(".")[2] != suffix):
        raise GraphSiteError(
            "recurrent method must name one conv history and one recurrent state layer")
    hidden_desc, conv_desc, state_desc = layout["hidden"], layout[conv[0]], layout[state[0]]
    for desc in (hidden_desc, conv_desc, state_desc):
        if (not isinstance(desc, Mapping) or desc.get("dtype") != "<f4"
                or desc.get("order") != "C"):
            raise GraphSiteError("recurrent successor must be contiguous f32")
    hidden_shape = hidden_desc.get("shape")
    conv_shape, state_shape = conv_desc.get("shape"), state_desc.get("shape")
    if (not isinstance(hidden_shape, (list, tuple)) or len(hidden_shape) != 1
            or not isinstance(conv_shape, (list, tuple)) or len(conv_shape) != 2
            or not isinstance(state_shape, (list, tuple)) or len(state_shape) != 3):
        raise GraphSiteError(
            "recurrent successor must retain vector hidden, convolution rows, and head/value/key dimensions")
    hidden_width = _shape_width(hidden_shape)
    conv_width = _shape_width(conv_shape)
    state_width = _shape_width(state_shape)
    if in_width != hidden_width + conv_width + state_width:
        raise GraphSiteError("recurrent feature width differs from hidden and prior state")
    if out_width != hidden_width + conv_width + state_width:
        raise GraphSiteError("recurrent successor width differs from complete native state")


def _validate_method(method: Mapping[str, Any]) -> None:
    if method.get("schema") != METHOD_SCHEMA:
        raise GraphSiteError("graph-site method must use the fixed low-rank affine schema")
    input_desc, output_desc = method.get("input"), method.get("output")
    if not isinstance(input_desc, Mapping) or not isinstance(output_desc, Mapping):
        raise GraphSiteError("graph-site method input/output tensor descriptors are required")
    for desc in (input_desc, output_desc):
        if (not isinstance(desc.get("name"), str) or not desc["name"]
                or desc.get("dtype") != "f32"):
            raise GraphSiteError("graph-site method tensor name and f32 dtype are required")
    in_width, out_width = _shape_width(input_desc.get("shape")), _shape_width(output_desc.get("shape"))
    successor_kind = output_desc["name"]
    if successor_kind == "recurrent_successor":
        if input_desc["name"] != "recurrent_features":
            raise GraphSiteError("recurrent method requires complete native input features")
        for desc in (input_desc, output_desc):
            shape = desc.get("shape")
            if not isinstance(shape, (list, tuple)) or len(shape) != 1:
                raise GraphSiteError("recurrent feature and successor descriptors must be vectors")
        _validate_recurrent_successor(method, in_width, out_width)
    elif successor_kind == "attention_projection":
        if input_desc["name"] != "attn_input":
            raise GraphSiteError("attention projection method requires normalized native input")
        layout = method.get("successor_shapes")
        required = {"attn_q", "attn_k", "attn_v"}
        if not isinstance(layout, Mapping) or set(layout) != required:
            raise GraphSiteError("attention projection method must describe every native projection")
        total = 0
        for desc in layout.values():
            if not isinstance(desc, Mapping) or desc.get("dtype") != "<f4" or desc.get("order") != "C":
                raise GraphSiteError("attention projection layout must be contiguous f32")
            total += _shape_width(desc.get("shape"))
        if total != out_width:
            raise GraphSiteError("attention projection method output width differs from native projections")
    elif successor_kind == "attention_successor":
        if input_desc["name"] != "attention_features":
            raise GraphSiteError("attention method must use complete native input features")
        layout = method.get("successor_shapes")
        if not isinstance(layout, Mapping):
            raise GraphSiteError("attention method must describe its complete successor")
        first = [name for name in layout if name.startswith("kv_k.")]
        second = [name for name in layout if name.startswith("kv_v.")]
        if (len(layout) != 3 or len(first) != 1 or len(second) != 1
                or "hidden" not in layout or first[0].split(".", 1)[1] != second[0].split(".", 1)[1]):
            raise GraphSiteError("attention method must describe its complete successor")
        total = 0
        for desc in layout.values():
            if not isinstance(desc, Mapping) or desc.get("dtype") != "<f4" or desc.get("order") != "C":
                raise GraphSiteError("attention method successor must be contiguous f32")
            total += _shape_width(desc.get("shape"))
        if total != out_width:
            raise GraphSiteError("attention method successor dimensions are invalid")
    elif successor_kind == "ffn_delta":
        if input_desc["name"] == "attn_post_norm":
            for desc in (input_desc, output_desc):
                shape = desc.get("shape")
                if not isinstance(shape, (list, tuple)) or len(shape) != 1:
                    raise GraphSiteError("expert method input and output must be vectors")
            if in_width != out_width:
                raise GraphSiteError("expert method dimensions differ from the native site")
        elif input_desc["name"] != "ffn_input" or method.get("successor_shapes") is not None:
            raise GraphSiteError("expert method input/output role is invalid")
    elif successor_kind != "logits" or input_desc["name"] != "head_input" or method.get(
        "successor_shapes"
    ) is not None:
        raise GraphSiteError("graph-site method input/output role is invalid")
    rank = method.get("rank")
    if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 16:
        raise GraphSiteError("graph-site affine rank must be between one and sixteen")
    _matrix(method.get("A"), in_width, rank, "A")
    _matrix(method.get("B"), rank, out_width, "B")
    bias = method.get("bias")
    if (not isinstance(bias, (list, tuple)) or len(bias) != out_width
            or any(isinstance(item, bool) or not isinstance(item, (int, float))
                   or not math.isfinite(item) or abs(item) > MAX_F32 for item in bias)):
        raise GraphSiteError("graph-site affine bias dimension or values are invalid")
    guard = method.get("native_state_applicability")
    if not isinstance(guard, Mapping) or not guard:
        raise GraphSiteError("graph-site native-state applicability is required")
    if successor_kind == "ffn_delta":
        route = guard.get("expert_route")
        ids = route.get("expert_ids") if isinstance(route, Mapping) else None
        if (not isinstance(ids, (list, tuple)) or not ids
                or isinstance(route.get("top_k"), bool) or route.get("top_k") != len(ids)
                or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in ids)
                or len(set(ids)) != len(ids)
                or (input_desc["name"] == "ffn_input"
                    and in_width != out_width + len(ids))
                or (input_desc["name"] == "attn_post_norm" and in_width != out_width)):
            raise GraphSiteError("expert method input or route applicability is invalid")
    support = method.get("input_support")
    if not isinstance(support, Mapping):
        raise GraphSiteError("graph-site input support is required")
    anchor = support.get("anchor")
    if anchor is None:
        if rank != 1:
            raise GraphSiteError("graph-site input support needs an anchor for rank above one")
    elif (not isinstance(anchor, (list, tuple)) or len(anchor) != in_width
          or any(isinstance(value, bool) or not isinstance(value, (int, float))
                 or not math.isfinite(value) or abs(value) > MAX_F32 for value in anchor)):
        raise GraphSiteError("graph-site input support anchor is invalid")
    for name in ("radius", "anchor_norm"):
        value = support.get(name)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise GraphSiteError(f"graph-site input support {name} is invalid")


def initial_state(source_sha256: str, backend: str) -> dict[str, Any]:
    if (not isinstance(source_sha256, str) or len(source_sha256) != 64
            or any(character not in "0123456789abcdef" for character in source_sha256)):
        raise GraphSiteError("graph-site source identity must be a SHA-256 digest")
    if not isinstance(backend, str) or not backend:
        raise GraphSiteError("graph-site backend is required")
    return {"schema": SCHEMA, "source_sha256": source_sha256, "backend": backend,
            "generation": 0, "methods": {},
            "telemetry": {"observed_error": 0, "task_outcome": 0, "native_ops_omitted": 0,
                          "native_ops_executed": 0, "added_flops": 0, "assisted": 0,
                          "proposed": 0, "proposals_accepted": 0, "proposals_rejected": 0},
            "evidence": []}


def invocation(*, source_sha256: str, architecture: str, backend: str, sequence_id: str,
               position: int, stage: str, layer: int | None, site: str, specialist: str,
               predecessor_generation: int, predecessor_sha256: str, intervention_order: int,
               dependencies: Mapping[str, Any], request_sha256: str,
               request_sha256_pending: bool = False, verb: str = "observe") -> dict[str, Any]:
    if specialist not in SPECIALISTS or verb not in VERBS:
        raise GraphSiteError("unsupported graph-site specialist or verb")
    if (isinstance(position, bool) or not isinstance(position, int) or position < 0
            or isinstance(intervention_order, bool) or not isinstance(intervention_order, int)
            or intervention_order < 0):
        raise GraphSiteError("graph-site position and intervention order must be nonnegative")
    if (isinstance(predecessor_generation, bool) or not isinstance(predecessor_generation, int)
            or predecessor_generation < 0):
        raise GraphSiteError("graph-site predecessor generation is invalid")
    if (not isinstance(request_sha256_pending, bool)
            or (request_sha256_pending and request_sha256 != "")):
        raise GraphSiteError("pending graph-site request must not carry a request digest")
    if not isinstance(dependencies, Mapping) or not dependencies:
        raise GraphSiteError("graph-site exact dependencies are required")
    bound = {"schema": INVOCATION_SCHEMA, "source_sha256": source_sha256,
             "architecture": architecture, "backend": backend, "sequence_id": sequence_id,
             "position": position, "stage": stage, "layer": layer, "site": site,
             "specialist": specialist, "predecessor_generation": predecessor_generation,
             "predecessor_sha256": predecessor_sha256, "intervention_order": intervention_order,
             "dependencies": _plain(dependencies), "request_sha256": request_sha256, "verb": verb}
    if request_sha256_pending:
        bound["request_sha256_pending"] = True
    bound["invocation_sha256"] = _digest(bound)
    return bound


def _required_successor_keys(specialist: str, layer: int | None) -> set[str]:
    if specialist == "expert-synthesis":
        return {"hidden", "snapshot", "expert_route"}
    if specialist == "recurrent-dynamics":
        return {"hidden", f"conv_history.{layer}", f"recurrent_state.{layer}",
                "attention_residual", "expert_route", "snapshot"}
    if specialist == "attention-memory":
        return {"hidden", f"kv_k.{layer}", f"kv_v.{layer}",
                "attention_residual", "expert_route", "snapshot"}
    if specialist == "execution-choice":
        return {"logits", "token", "snapshot"}
    raise GraphSiteError("graph-site specialist is unsupported")


def candidate(invocation_value: Mapping[str, Any], *, method_generation: int,
              applicability: Mapping[str, Any], method: Mapping[str, Any], output: Any,
              successor: Mapping[str, Any], omitted_ops: tuple[str, ...] = (),
              observed_error: float | None = None, task_outcome: str = "unknown",
              native_ops_omitted: int = 0, method_key: str | None = None) -> dict[str, Any]:
    if invocation_value.get("schema") != INVOCATION_SCHEMA:
        raise GraphSiteError("candidate is not bound to a typed invocation")
    if isinstance(method_generation, bool) or not isinstance(method_generation, int) or method_generation < 1:
        raise GraphSiteError("candidate method generation must be positive")
    if not isinstance(applicability, Mapping) or not applicability or not isinstance(method, Mapping):
        raise GraphSiteError("candidate applicability and fixed method are required")
    _validate_method(method)
    if not isinstance(successor, Mapping):
        raise GraphSiteError("candidate must carry its complete successor state")
    required = _required_successor_keys(
        str(invocation_value.get("specialist")), invocation_value.get("layer")
    )
    if not required.issubset(successor):
        raise GraphSiteError("candidate successor is incomplete for its graph specialist")
    if method_key is not None and (not isinstance(method_key, str) or not method_key):
        raise GraphSiteError("candidate local method key is invalid")
    item = {"schema": CANDIDATE_SCHEMA, "invocation": _plain(invocation_value),
            "method_generation": method_generation, "applicability": _plain(applicability),
            "method": _plain(method), "output": _plain(output), "successor": _plain(successor),
            "omitted_ops": list(omitted_ops), "observed_error": observed_error,
            "task_outcome": task_outcome, "native_ops_omitted": native_ops_omitted}
    if method_key is not None:
        item["method_key"] = method_key
    item["candidate_sha256"] = _digest(item)
    return item


def _policy_key(invocation_value: Mapping[str, Any], applicability: Mapping[str, Any],
                native_guard: Mapping[str, Any]) -> str:
    return _digest({"applicability": _plain(applicability),
                    "dependencies": _plain(invocation_value["dependencies"]),
                    "native_state_applicability": _plain(native_guard)})


def _append_evidence(state: dict[str, Any], evidence: Mapping[str, Any]) -> None:
    evidence_rows = state.setdefault("evidence", [])
    if len(evidence_rows) >= MAX_EVIDENCE:
        evidence_rows.pop(0)
    evidence_rows.append(_plain(evidence))


def _remember_owner_invocation(row: dict[str, Any], binding: Mapping[str, Any]) -> None:
    invocations = row.setdefault("owner_invocations", [])
    invocation_hash = binding.get("invocation_sha256")
    if any(item.get("invocation_sha256") == invocation_hash
           for item in invocations if isinstance(item, Mapping)):
        return
    if len(invocations) >= MAX_EVIDENCE:
        invocations.pop(0)
    invocations.append(_plain(binding))


def _native_successor_digest(value: Any, layer: int, specialist: str) -> str:
    state_names = (
        {"hidden", f"conv_history.{layer}", f"recurrent_state.{layer}"}
        if specialist == "recurrent-dynamics"
        else {"hidden", f"kv_k.{layer}", f"kv_v.{layer}"}
    )
    if not isinstance(value, Mapping) or set(value) != state_names:
        raise GraphSiteError("native observation must name its complete successor state")
    for name in state_names:
        desc = value[name]
        if (not isinstance(desc, Mapping) or set(desc) != {"dtype", "order", "shape", "sha256"}
                or desc["dtype"] != "<f4" or desc["order"] != "C"
                or not isinstance(desc["sha256"], str) or len(desc["sha256"]) != 64
                or any(char not in "0123456789abcdef" for char in desc["sha256"])):
            raise GraphSiteError("native successor evidence is invalid")
        _shape_width(desc["shape"])
    return _digest(value)


def _vector_norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _encoded_f32(values: list[float]) -> str:
    raw = struct.pack("<" + "f" * len(values), *values)
    return base64.b64encode(raw).decode("ascii")




def _support_distance(values: Any, support: Mapping[str, Any],
                      method: Mapping[str, Any] | None = None) -> float | None:
    """Return distance to an acquired support anchor, or None for a bad width."""
    anchor = support.get("anchor")
    if anchor is None:
        if method is None or method.get("rank") != 1:
            return None
        matrix = method.get("A")
        anchor_norm = support.get("anchor_norm")
        if (not isinstance(matrix, (list, tuple))
                or isinstance(anchor_norm, bool)
                or not isinstance(anchor_norm, (int, float))):
            return None
        anchor = [column[0] * anchor_norm for column in matrix]
    if isinstance(values, (str, bytes, bytearray)) or not hasattr(values, "__iter__"):
        return None
    if hasattr(values, "reshape"):
        values = values.reshape(-1)
    if len(anchor) != len(values):
        return None
    distance_squared = 0.0
    for index, value in enumerate(values):
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
            reference = float(anchor[index])
        except (TypeError, ValueError, OverflowError):
            return None
        if (not math.isfinite(number) or abs(number) > MAX_F32
                or not math.isfinite(reference) or abs(reference) > MAX_F32):
            return None
        delta = number - reference
        distance_squared += delta * delta
    distance = math.sqrt(distance_squared)
    return distance if math.isfinite(distance) else None


def _local_training_distance(values: list[float], support: Mapping[str, Any],
                             method: Mapping[str, Any]) -> tuple[float, float] | None:
    distance = _support_distance(values, support, method)
    anchor_norm = support.get("anchor_norm")
    radius = support.get("radius")
    if (distance is None or isinstance(anchor_norm, bool)
            or not isinstance(anchor_norm, (int, float))
            or isinstance(radius, bool) or not isinstance(radius, (int, float))):
        return None
    limit = max(float(radius), LOCAL_RECURRENT_RADIUS_FRACTION * max(1.0, float(anchor_norm)))
    if distance > limit:
        return None
    return distance, limit


def _append_local_support(support: dict[str, Any], distance: float) -> None:
    support["radius"] = max(float(support["radius"]), distance)


def _affine_prediction(method: Mapping[str, Any], values: list[float]) -> list[float]:
    rank = method["rank"]
    features = [
        sum(value * float(column[index]) for value, column in zip(values, method["A"]))
        for index in range(rank)
    ]
    return [
        float(method["bias"][output]) + sum(
            features[index] * float(method["B"][index][output]) for index in range(rank)
        )
        for output in range(len(method["bias"]))
    ]


def _relative_error(prediction: list[float], target: list[float]) -> float:
    if len(prediction) != len(target):
        raise GraphSiteError("recurrent training target width changed within a local method")
    delta = [actual - predicted for actual, predicted in zip(target, prediction)]
    error = math.sqrt(sum(value * value for value in delta)
                      / max(sum(value * value for value in target), 1e-12))
    if not math.isfinite(error):
        raise GraphSiteError("recurrent training holdout error is not finite")
    return error


def _fit_recurrent_affine(method: dict[str, Any], values: list[float],
                          target: list[float]) -> None:
    """Update a compact affine basis with this actual chronological native sample."""
    if len(values) != len(method["A"]) or len(target) != len(method["bias"]):
        raise GraphSiteError("recurrent training dimensions changed within a local method")
    prediction = _affine_prediction(method, values)
    residual = [actual - predicted for actual, predicted in zip(target, prediction)]
    rank = method["rank"]
    features = [
        sum(value * float(column[index]) for value, column in zip(values, method["A"]))
        for index in range(rank)
    ]

    # A new orthogonal input direction adds one affine degree of freedom without
    # changing predictions for any earlier sample in this local chronological
    # span. Its coefficient is fitted from the actual native output residual.
    projected = [0.0] * len(values)
    for component, feature in enumerate(features):
        for index, column in enumerate(method["A"]):
            projected[index] += float(column[component]) * feature
    direction = [value - component for value, component in zip(values, projected)]
    direction_norm = _vector_norm(direction)
    value_norm = _vector_norm(values)
    if (rank < 16 and direction_norm
            > LOCAL_RECURRENT_DIRECTION_EPSILON * max(1.0, value_norm)):
        inverse_norm = 1.0 / direction_norm
        for index, column in enumerate(method["A"]):
            column.append(direction[index] * inverse_norm)
        method["B"].append([value / direction_norm for value in residual])
        method["rank"] = rank + 1
    else:
        denominator = sum(feature * feature for feature in features)
        if denominator > 1e-12:
            scale = 1.0 / denominator
            for component, feature in enumerate(features):
                weight = feature * scale
                for output, delta in enumerate(residual):
                    method["B"][component][output] += weight * delta
        else:
            for output, delta in enumerate(residual):
                method["bias"][output] += delta


def _append_error(errors: list[float], error: float) -> None:
    errors.append(error)
    if len(errors) > MIN_ADMISSION_SUPPORT:
        errors.pop(0)


def _initialize_recurrent_method(input_name: str, target_name: str,
                                 values: list[float], target: list[float],
                                 successor_shapes: Mapping[str, Any],
                                 native_guard: Mapping[str, Any],
                                 row_cost: Mapping[str, Any]) -> dict[str, Any] | None:
    input_norm, target_norm = _vector_norm(values), _vector_norm(target)
    if input_norm <= 1e-10 or target_norm <= 1e-10:
        return None
    return {
        "schema": METHOD_SCHEMA,
        "input": {"name": input_name, "shape": [len(values)], "dtype": "f32"},
        "output": {"name": target_name, "shape": [len(target)], "dtype": "f32"},
        "rank": 1, "A": [[value / input_norm] for value in values],
        "B": [[value / input_norm for value in target]], "bias": [0.0] * len(target),
        "native_state_applicability": _plain(native_guard),
        "native_cost": _plain(row_cost),
        "input_support": {"radius": 0.0, "anchor_norm": input_norm,
                          "anchor": list(values)},
        "successor_shapes": _plain(successor_shapes),
    }


def _acquire_recurrent_training(working: dict[str, Any], binding: Mapping[str, Any],
                                training: Mapping[str, Any], *, x: list[float],
                                y: list[float], applicability: Mapping[str, Any],
                                state_guard: Mapping[str, Any], successor_shapes: Mapping[str, Any],
                                row_cost: Mapping[str, Any], site: str, layer: int) -> dict[str, Any]:
    methods = working.setdefault("methods", {})
    base_key = _policy_key(binding, applicability, state_guard)
    invocation_hash = binding["invocation_sha256"]
    all_local_rows = [
        (key, row) for key, row in methods.items()
        if isinstance(row, dict) and row.get("local_recurrent") is True
        and row.get("policy_key") == base_key
    ]
    if any(invocation_hash in row.get("evidence_ids", ()) for _, row in all_local_rows):
        raise GraphSiteError("graph-site training observation was replayed")
    local_rows = [
        (key, row) for key, row in all_local_rows
        if row.get("local_contract") == "recurrent_successor.v1"
    ]

    anchor_digest = _digest({"input": x})
    choices: list[tuple[float, str, dict[str, Any], float]] = []
    for key, row in local_rows:
        method = row.get("method")
        if isinstance(method, Mapping):
            support = _local_training_distance(x, method.get("input_support", {}), method)
            if support is not None:
                choices.append((support[0] / max(support[1], 1e-12), key, row, support[0]))
        elif method is None and row.get("local_anchor_sha256") == anchor_digest:
            choices.append((0.0, key, row, 0.0))

    if choices:
        _, key, row, input_distance = min(choices, key=lambda item: (item[0], item[1]))
    else:
        if len(local_rows) >= MAX_LOCAL_RECURRENT_METHODS:
            _append_evidence(working, {
                "kind": "training-local-cap", "key": base_key,
                "invocation_sha256": invocation_hash,
                "maximum_local_methods": MAX_LOCAL_RECURRENT_METHODS,
            })
            if working.get("backend") == "unknown":
                working["backend"] = binding["backend"]
            working["generation"] += 1
            return working
        key = _digest({"policy_key": base_key, "local_anchor": invocation_hash})
        if key in methods:
            raise GraphSiteError("graph-site recurrent local method key collides with legacy state")
        row = {
            "key": key, "policy_key": base_key, "local_recurrent": True,
            "local_contract": "recurrent_successor.v1",
            "local_anchor_sha256": anchor_digest,
            "site": site, "specialist": "recurrent-dynamics", "generation": 0,
            "support": 0, "candidate_support": 0, "bad": 0, "observed_error": 0.0,
            "error_samples": 0, "task_success": 0, "task_failure": 0,
            "native_ops_omitted": 0, "admitted": False, "backed_off": False,
            "applicability": _plain(applicability), "dependencies": _plain(binding["dependencies"]),
            "successor_shapes": _policy_layout(successor_shapes, "recurrent-dynamics", layer),
            "native_state_applicability": _plain(state_guard), "method_cost": _plain(row_cost),
            "method": None, "evidence_ids": [], "heldout_errors": [], "trajectory": [],
        }
        methods[key] = row
        input_distance = 0.0

    successor_evidence = _plain(training["successor_state"])
    successor_digest = _native_successor_digest(
        training["successor_state"], layer, "recurrent-dynamics")
    trajectory = row.setdefault("trajectory", [])
    trajectory.append({
        "invocation_sha256": invocation_hash,
        "sequence_id": binding["sequence_id"], "position": binding["position"],
        "input": {"width": len(x), "data_b64": _encoded_f32(x)},
        "successor_state": successor_evidence,
        "native_successor_sha256": successor_digest,
    })
    if len(trajectory) > MAX_LOCAL_TRAJECTORY_SAMPLES:
        trajectory.pop(0)

    if (row.get("applicability") != _plain(applicability)
            or row.get("dependencies") != _plain(binding["dependencies"])
            or row.get("successor_shapes") != _policy_layout(
                successor_shapes, "recurrent-dynamics", layer)
            or row.get("native_state_applicability") != _plain(state_guard)
            or row.get("method_cost") != _plain(row_cost)):
        raise GraphSiteError("graph-site recurrent local applicability changed within one method")

    count = min(MAX_EVIDENCE, row["support"] + 1)
    row["support"] = count
    row["generation"] += 1
    method = row.get("method")
    if method is None:
        method = _initialize_recurrent_method(
            "recurrent_features", "recurrent_successor", x, y,
            successor_shapes, state_guard, row_cost)
        if method is not None:
            row["method"] = method
            _validate_method(method)
    else:
        error = _relative_error(_affine_prediction(method, x), y)
        _append_error(row["heldout_errors"], error)
        row["observed_error"] += (error - row["observed_error"]) / (row["error_samples"] + 1)
        row["error_samples"] += 1
        _fit_recurrent_affine(method, x, y)
        _validate_method(method)

    if method is not None:
        _append_local_support(method["input_support"], input_distance)
    row["admitted"] = (
        count >= MIN_ADMISSION_SUPPORT and method is not None
        and len(row.get("heldout_errors", ())) >= MIN_ADMISSION_SUPPORT - 1
        and max(row["heldout_errors"][-(MIN_ADMISSION_SUPPORT - 1):]) <= MAX_ERROR
        and not row["backed_off"]
    )
    if len(row["evidence_ids"]) >= MAX_EVIDENCE:
        row["evidence_ids"].pop(0)
    row["evidence_ids"].append(invocation_hash)
    _remember_owner_invocation(row, binding)
    _append_evidence(working, {
        "kind": "training", "key": key, "invocation_sha256": invocation_hash,
        "method_generation": row["generation"], "support": count,
        "native_successor_sha256": successor_digest,
    })
    if working.get("backend") == "unknown":
        working["backend"] = binding["backend"]
    working["generation"] += 1
    return working




def acquire_training(state: Mapping[str, Any], training: Mapping[str, Any]) -> dict[str, Any]:
    """Learn and retain a low-rank affine approximation from native execution."""
    working = _plain(state)
    binding = training.get("invocation")
    if (working.get("schema") != SCHEMA or training.get("schema") != TRAINING_SCHEMA
            or not isinstance(binding, Mapping)):
        raise GraphSiteError("graph-site training sample is invalid")
    body = {key: value for key, value in binding.items() if key != "invocation_sha256"}
    specialist = binding.get("specialist")
    stage = binding.get("stage")
    if (binding.get("schema") != INVOCATION_SCHEMA or binding.get("invocation_sha256") != _digest(body)
            or binding.get("source_sha256") != working.get("source_sha256")
            or SITE_STAGES.get((binding.get("architecture"), specialist)) != stage
            or binding.get("verb") not in {"observe", "replace", "propose"}
            or working.get("backend") not in {"unknown", binding.get("backend")}):
        raise GraphSiteError("graph-site training binding is stale or unsupported")
    if binding["verb"] == "replace" and training.get("native_ops_omitted") != 0:
        raise GraphSiteError("replacement fallback training requires native graph execution")
    if training.get("task_outcome") != "unknown":
        raise GraphSiteError("training observations cannot claim downstream task outcomes")
    dependencies = binding.get("dependencies")
    if not isinstance(dependencies, Mapping):
        raise GraphSiteError("graph-site training dependencies are invalid")
    membrane_profile = dependencies.get("membrane_profile")
    field_epoch = dependencies.get("field_epoch_sha256")
    native_guard = training.get("native_state_applicability")
    if (not isinstance(membrane_profile, Mapping)
            or not isinstance(field_epoch, str) or len(field_epoch) != 64
            or any(char not in "0123456789abcdef" for char in field_epoch)):
        raise GraphSiteError("graph-site training requires an exact field-state identity")
    state_guard = {"membrane_profile": _plain(membrane_profile),
                   "field_epoch_sha256": field_epoch}
    if specialist == "expert-synthesis":
        route = native_guard.get("expert_route") if isinstance(native_guard, Mapping) else None
        ids = route.get("expert_ids") if isinstance(route, Mapping) else None
        top_k = route.get("top_k") if isinstance(route, Mapping) else None
        if (not isinstance(ids, (list, tuple)) or not ids
                or isinstance(top_k, bool) or not isinstance(top_k, int)
                or top_k != len(ids)
                or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in ids)
                or len(set(ids)) != len(ids)):
            raise GraphSiteError("expert graph method requires an exact routed expert choice")
        state_guard["expert_route"] = {"expert_ids": list(ids), "top_k": top_k}
    if native_guard != state_guard:
        raise GraphSiteError("graph-site training native state differs from its field dependencies")
    cost = training.get("cost")
    minimum_omitted = 5 if specialist == "recurrent-dynamics" else 1
    if (not isinstance(cost, Mapping) or isinstance(cost.get("native_ops_omitted"), bool)
            or not isinstance(cost.get("native_ops_omitted"), int)
            or cost["native_ops_omitted"] < minimum_omitted
            or isinstance(cost.get("flops"), bool) or not isinstance(cost.get("flops"), int)
            or cost["flops"] < 1):
        raise GraphSiteError("graph-site training must declare positive prospective native cost")
    if specialist == "recurrent-dynamics" and cost["native_ops_omitted"] != 5:
        raise GraphSiteError("recurrent training must account for all five native projections")

    def vector(name: str) -> list[float]:
        tensor = training.get(name)
        if not isinstance(tensor, Mapping) or tensor.get("dtype") != "<f4":
            raise GraphSiteError(f"graph-site {name} must be an f32 tensor")
        shape = tensor.get("shape")
        if not isinstance(shape, (list, tuple)) or len(shape) != 1:
            raise GraphSiteError(f"graph-site {name} must be a vector")
        width, encoded, digest = _shape_width(shape), tensor.get("data_b64"), tensor.get("sha256")
        capacity = (
            MAX_TRAINING_INPUT_VALUES if name == "input"
            else MAX_TRAINING_OUTPUT_VALUES
        )
        if width > capacity:
            raise GraphSiteError(f"graph-site {name} exceeds the bounded tensor limit")
        if not isinstance(encoded, str) or not isinstance(digest, str):
            raise GraphSiteError(f"graph-site {name} bytes and digest are required")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise GraphSiteError(f"graph-site {name} encoding is invalid") from exc
        if len(raw) != width * 4 or hashlib.sha256(raw).hexdigest() != digest:
            raise GraphSiteError(f"graph-site {name} byte count or digest is invalid")
        values = list(struct.unpack("<" + "f" * width, raw))
        if any(not math.isfinite(value) for value in values):
            raise GraphSiteError(f"graph-site {name} contains non-finite values")
        return values
    x, y = vector("input"), vector("target")
    site, layer = binding.get("site"), binding.get("layer")
    sequence = binding.get("sequence_id")
    if (not isinstance(site, str) or not site
            or (specialist != "execution-choice"
                and (isinstance(layer, bool) or not isinstance(layer, int)))
            or (specialist == "execution-choice" and layer is not None)
            or not isinstance(sequence, str) or not sequence):
        raise GraphSiteError("graph-site training applicability is incomplete")
    successor_shapes = None
    if specialist == "expert-synthesis":
        top_k = state_guard["expert_route"]["top_k"]
        if len(x) == len(y):
            input_name, target_name = "attn_post_norm", "ffn_delta"
        elif len(x) == len(y) + top_k:
            input_name, target_name = "ffn_input", "ffn_delta"
        else:
            raise GraphSiteError("expert input must bind the activation and exact native route")
        if training.get("successor_shapes") is not None:
            raise GraphSiteError("expert training cannot declare attention state")
    elif specialist == "execution-choice":
        if training.get("successor_shapes") is not None:
            raise GraphSiteError("head training cannot declare attention state")
        input_name, target_name = "head_input", "logits"
    elif specialist == "recurrent-dynamics":
        successor_shapes = training.get("successor_shapes")
        layout_order = ["hidden", f"conv_history.{layer}", f"recurrent_state.{layer}"]
        if (not isinstance(successor_shapes, Mapping)
                or list(successor_shapes) != layout_order):
            raise GraphSiteError("recurrent method must describe its complete successor state")
        for name in layout_order:
            desc = successor_shapes[name]
            if not isinstance(desc, Mapping) or desc.get("dtype") != "<f4" or desc.get("order") != "C":
                raise GraphSiteError("recurrent successor layout must be contiguous f32")
            _shape_width(desc.get("shape"))
        hidden_width = _shape_width(successor_shapes["hidden"].get("shape"))
        conv_shape = successor_shapes[f"conv_history.{layer}"].get("shape")
        state_shape = successor_shapes[f"recurrent_state.{layer}"].get("shape")
        if (not isinstance(conv_shape, (list, tuple)) or len(conv_shape) != 2
                or not isinstance(state_shape, (list, tuple)) or len(state_shape) != 3):
            raise GraphSiteError(
                "recurrent successor must retain convolution rows and head/value/key dimensions")
        conv_width, state_width = _shape_width(conv_shape), _shape_width(state_shape)
        feature_width = hidden_width + conv_width + state_width
        if len(x) != feature_width:
            raise GraphSiteError(
                "recurrent feature input must include hidden, prior convolution history, and prior state")
        if len(y) != feature_width:
            raise GraphSiteError("recurrent target must contain the complete native successor")
        successor_state = training.get("successor_state")
        _native_successor_digest(successor_state, layer, specialist)
        offset = 0
        for name in layout_order:
            desc = successor_state[name]
            shape = successor_shapes[name]["shape"]
            if desc["shape"] != shape:
                raise GraphSiteError("recurrent successor evidence shape differs from its descriptor")
            width = _shape_width(shape)
            actual_digest = hashlib.sha256(
                struct.pack("<" + "f" * width, *y[offset:offset + width])).hexdigest()
            if actual_digest != desc["sha256"]:
                raise GraphSiteError("recurrent training target differs from the native successor receipt")
            offset += width
        input_name, target_name = "recurrent_features", "recurrent_successor"
    else:
        successor_shapes = training.get("successor_shapes")
        names = ("attn_q", "attn_k", "attn_v")
        if not isinstance(successor_shapes, Mapping) or set(successor_shapes) != set(names):
            raise GraphSiteError("attention projection layout is incomplete")
        total = 0
        for name in names:
            desc = successor_shapes[name]
            if not isinstance(desc, Mapping) or desc.get("dtype") != "<f4" or desc.get("order") != "C":
                raise GraphSiteError("attention projection layout must be contiguous f32")
            total += _shape_width(desc.get("shape"))
        if total != len(y):
            raise GraphSiteError("attention projection layout differs from native target")
        _native_successor_digest(training.get("successor_state"), layer, specialist)
        input_name, target_name = "attn_input", "attention_projection"
    applicability = {"source_sha256": binding["source_sha256"], "architecture": binding["architecture"],
                     "backend": binding["backend"], "stage": binding["stage"],
                     "layer": layer, "site": site, "specialist": specialist}
    if specialist == "expert-synthesis" and input_name == "attn_post_norm":
        applicability["tensor_layout"] = {
            "input_tensor": "attn_post_norm", "output_tensor": "ffn_delta",
        }
    if specialist == "attention-memory":
        applicability["position"] = binding["position"]
    if successor_shapes is not None:
        applicability["successor_shapes"] = _policy_layout(successor_shapes, specialist, layer)
    row_cost = _plain(cost)
    if specialist == "recurrent-dynamics":
        # Retain the measured native projection work for exact portability evidence.
        return _acquire_recurrent_training(
            working, binding, training, x=x, y=y, applicability=applicability,
            state_guard=state_guard, successor_shapes=successor_shapes,
            row_cost=row_cost, site=site, layer=layer)

    key = _policy_key(binding, applicability, state_guard)
    methods = working.setdefault("methods", {})
    row = methods.get(key)
    if row is None:
        row = {"key": key, "site": site, "specialist": specialist,
               "generation": 0, "support": 0, "candidate_support": 0, "bad": 0,
               "observed_error": 0.0, "error_samples": 0, "task_success": 0, "task_failure": 0,
               "native_ops_omitted": 0, "admitted": False, "backed_off": False,
               "applicability": _plain(applicability), "dependencies": _plain(dependencies),
               "successor_shapes": _policy_layout(successor_shapes, specialist, layer),
               "native_state_applicability": _plain(state_guard), "method_cost": row_cost,
               "method": None, "evidence_ids": []}
        methods[key] = row
    invocation_hash = binding["invocation_sha256"]
    if invocation_hash in row["evidence_ids"]:
        raise GraphSiteError("graph-site training observation was replayed")
    if len(row["evidence_ids"]) >= MAX_EVIDENCE:
        row["evidence_ids"].pop(0)
    if (row["applicability"] != _plain(applicability)
            or row["dependencies"] != _plain(dependencies)
            or row.get("successor_shapes") != _policy_layout(successor_shapes, specialist, layer)
            or row["native_state_applicability"] != _plain(state_guard)
            or row["method_cost"] != row_cost):
        raise GraphSiteError("graph-site training layout or applicability changed within one method")
    count = min(MAX_EVIDENCE, row["support"] + 1)
    row.pop("training_input_mean", None)
    row.pop("training_target_mean", None)
    row["support"] = count
    row["generation"] += 1
    method = row["method"]
    if method is None:
        norm = math.sqrt(sum(value * value for value in x))
        y_norm = math.sqrt(sum(value * value for value in y))
        if norm > 1e-10 and y_norm > 1e-10:
            method = {
                "schema": METHOD_SCHEMA,
                "input": {"name": input_name, "shape": [len(x)], "dtype": "f32"},
                "output": {"name": target_name, "shape": [len(y)], "dtype": "f32"},
                "rank": 1, "A": [[value / norm] for value in x],
                "B": [[value / norm for value in y]], "bias": [0.0] * len(y),
                "native_state_applicability": _plain(state_guard),
                "native_cost": row_cost,
                "input_support": {"radius": 0.0, "anchor_norm": norm},
                **({"successor_shapes": _plain(successor_shapes)}
                   if successor_shapes is not None else {}),
            }
            row["method"] = method
            row["heldout_errors"] = []
            _validate_method(method)
    else:
        feature = sum(value * column[0] for value, column in zip(x, method["A"]))
        estimate = [method["bias"][j] + feature * method["B"][0][j]
                    for j in range(len(y))]
        delta = [target - predicted for target, predicted in zip(y, estimate)]
        error = math.sqrt(sum(value * value for value in delta)
                          / max(sum(value * value for value in y), 1e-12))
        heldout = row.setdefault("heldout_errors", [])
        heldout.append(error)
        if len(heldout) > MIN_ADMISSION_SUPPORT:
            heldout.pop(0)
        row["observed_error"] += (error - row["observed_error"]) / (row["error_samples"] + 1)
        row["error_samples"] += 1
        support = method["input_support"]
        if method["rank"] == 1:
            support.pop("anchor", None)
        anchor = support.get("anchor")
        support["radius"] = max(
            support["radius"],
            math.sqrt(sum((value - (anchor[index] if anchor is not None
                                     else method["A"][index][0] * support["anchor_norm"])) ** 2
                          for index, value in enumerate(x))),
        )
        denominator = feature * feature + 1e-8
        for j, value in enumerate(delta):
            method["B"][0][j] += 0.4 * feature * value / denominator
            method["bias"][j] += 0.1 * value
        _validate_method(method)
    row["admitted"] = (
        count >= MIN_ADMISSION_SUPPORT and method is not None
        and len(row.get("heldout_errors", ())) >= MIN_ADMISSION_SUPPORT - 1
        and max(row["heldout_errors"][-(MIN_ADMISSION_SUPPORT - 1):]) <= MAX_ERROR
        and not row["backed_off"]
    )
    row["evidence_ids"].append(invocation_hash)
    _remember_owner_invocation(row, binding)
    _append_evidence(working, {
        "kind": "training", "key": key, "invocation_sha256": invocation_hash,
        "method_generation": row["generation"], "support": count,
        **({"native_successor_sha256": _native_successor_digest(
            training["successor_state"], layer, specialist)}
           if specialist == "attention-memory" else {}),
    })
    if working.get("backend") == "unknown":
        working["backend"] = binding["backend"]
    working["generation"] += 1
    return working


def admit(state: Mapping[str, Any], candidate_value: Mapping[str, Any]) -> dict[str, Any]:
    """Record a bound proposal against its acquired, owner-held method."""
    working = _plain(state)
    candidate_body = {key: value for key, value in candidate_value.items() if key != "candidate_sha256"}
    invocation_value = candidate_value.get("invocation")
    if candidate_value.get("candidate_sha256") != _digest(candidate_body):
        raise GraphSiteError("graph-site candidate digest is invalid")
    if candidate_value.get("schema") != CANDIDATE_SCHEMA or not isinstance(invocation_value, Mapping):
        raise GraphSiteError("graph-site policy or candidate schema is invalid")
    invocation_body = {key: value for key, value in invocation_value.items() if key != "invocation_sha256"}
    if invocation_value.get("invocation_sha256") != _digest(invocation_body):
        raise GraphSiteError("graph-site invocation digest is invalid")
    if (working.get("schema") != SCHEMA or invocation_value.get("schema") != INVOCATION_SCHEMA
            or invocation_value.get("source_sha256") != working.get("source_sha256")
            or invocation_value.get("specialist") not in SPECIALISTS
            or invocation_value.get("verb") not in {"replace", "propose"}):
        raise GraphSiteError("graph-site candidate binding is unsupported")
    successor = candidate_value.get("successor")
    required = _required_successor_keys(
        str(invocation_value.get("specialist")), invocation_value.get("layer")
    )
    if not isinstance(successor, Mapping) or not required.issubset(successor):
        raise GraphSiteError("graph-site candidate successor is incomplete")
    method = candidate_value.get("method")
    applicability = candidate_value.get("applicability")
    if not isinstance(method, Mapping) or not isinstance(applicability, Mapping) or not applicability:
        raise GraphSiteError("graph-site candidate method and applicability are invalid")
    _validate_method(method)
    if invocation_value.get("specialist") == "recurrent-dynamics":
        key = candidate_value.get("method_key")
        if key is None:
            matching = [
                candidate_key for candidate_key, candidate_row in working.get("methods", {}).items()
                if isinstance(candidate_row, dict)
                and candidate_row.get("local_recurrent") is True
                and candidate_row.get("policy_key") == _policy_key(
                    invocation_value, applicability, method["native_state_applicability"])
                and candidate_row.get("method") == _plain(method)
                and candidate_row.get("site") == invocation_value.get("site")
                and candidate_row.get("dependencies") == invocation_value.get("dependencies")
            ]
            if len(matching) != 1:
                raise GraphSiteError("candidate recurrent local method key is missing or ambiguous")
            key = matching[0]
        if not isinstance(key, str) or not key:
            raise GraphSiteError("candidate recurrent local method key is invalid")
        row = working.get("methods", {}).get(key)
        if (not isinstance(row, dict) or row.get("local_recurrent") is not True
                or row.get("policy_key") != _policy_key(
                    invocation_value, applicability, method["native_state_applicability"])):
            raise GraphSiteError("candidate recurrent method does not bind an owner local row")
    else:
        key = _policy_key(invocation_value, applicability, method["native_state_applicability"])
        row = working.get("methods", {}).get(key)
    if not isinstance(row, dict) or row.get("method") != _plain(method):
        raise GraphSiteError("candidate does not use the current owner-trained method")
    generation = candidate_value.get("method_generation")
    if isinstance(generation, bool) or generation != row.get("generation"):
        raise GraphSiteError("candidate method generation is stale")
    if row.get("site") != invocation_value.get("site") or row.get("dependencies") != invocation_value.get("dependencies"):
        raise GraphSiteError("candidate method applicability is stale")
    error, outcome = candidate_value.get("observed_error"), candidate_value.get("task_outcome", "unknown")
    if (error is None or isinstance(error, bool) or not isinstance(error, (int, float)) or not 0 <= error <= 1
            or outcome not in {"success", "failure", "unknown"}):
        raise GraphSiteError("candidate must provide measured error and scoped task outcome")
    omitted = candidate_value.get("native_ops_omitted")
    if isinstance(omitted, bool) or not isinstance(omitted, int) or omitted < 0:
        raise GraphSiteError("native omitted-op telemetry must be nonnegative")
    if (not isinstance(candidate_value.get("omitted_ops"), (list, tuple))
            or (omitted > 0 and not candidate_value["omitted_ops"])):
        raise GraphSiteError("candidate omitted-op accounting is invalid")
    row["candidate_support"] += 1
    row["observed_error"] += (float(error) - row["observed_error"]) / (row["error_samples"] + 1)
    row["error_samples"] += 1
    row["task_success"] += outcome == "success"
    row["task_failure"] += outcome == "failure"
    row["native_ops_omitted"] += omitted
    if error > MAX_ERROR or outcome == "failure":
        row["bad"] += 1
        row["backed_off"] = True
    row["admitted"] = (row["support"] >= MIN_ADMISSION_SUPPORT
                       and len(row.get("heldout_errors", ())) >= MIN_ADMISSION_SUPPORT - 1
                       and max(row["heldout_errors"][-(MIN_ADMISSION_SUPPORT - 1):]) <= MAX_ERROR
                       and not row["backed_off"])
    working["telemetry"]["observed_error"] += 1
    working["telemetry"]["task_outcome"] += outcome != "unknown"
    working["telemetry"]["native_ops_omitted"] += omitted
    working["generation"] += 1
    _append_evidence(working, {"kind": "candidate", "key": key,
                               "candidate_sha256": candidate_value["candidate_sha256"],
                               "invocation_sha256": invocation_value["invocation_sha256"],
                               "observed_error": float(error), "task_outcome": outcome,
                               "native_ops_omitted": omitted})
    return working

def _intervention_receipt(value: Any, verb: str, specialist: str,
                          native_cost: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("mode") != verb:
        raise GraphSiteError("assistance or proposal lacks its native verifier receipt")
    expected = (
        {"mode", "native_output_sha256", "candidate_output_sha256", "committed_output_sha256",
         "correction_scale", "native_ops_executed", "added_flops"}
        if verb == "assist" else
        {"mode", "native_output_sha256", "candidate_output_sha256", "accepted",
         "native_ops_executed", "added_flops"} |
        ({"candidate_token", "native_token"} if specialist == "execution-choice" else set())
    )
    if set(value) != expected:
        raise GraphSiteError("graph-site intervention receipt fields are incomplete")
    digest_names = ("native_output_sha256", "candidate_output_sha256")
    if verb == "assist":
        digest_names += ("committed_output_sha256",)
    for name in digest_names:
        digest = value[name]
        if (not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)):
            raise GraphSiteError("graph-site intervention tensor digest is invalid")
    for name in ("native_ops_executed", "added_flops"):
        amount = value[name]
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
            raise GraphSiteError("graph-site intervention cost must include native and field work")
    if value["native_ops_executed"] < native_cost["native_ops_omitted"]:
        raise GraphSiteError("graph-site intervention concealed native work")
    if verb == "assist":
        scale = value["correction_scale"]
        if isinstance(scale, bool) or not isinstance(scale, (float, int)) or not 0 < scale <= 1:
            raise GraphSiteError("graph-site assistance correction scale is invalid")
    else:
        if not isinstance(value["accepted"], bool):
            raise GraphSiteError("graph-site proposal disposition is invalid")
        if specialist == "execution-choice":
            tokens = (value["candidate_token"], value["native_token"])
            if any(isinstance(token, bool) or not isinstance(token, int) or token < 0 for token in tokens):
                raise GraphSiteError("graph-site proposed token is invalid")
            if value["accepted"] != (tokens[0] == tokens[1]):
                raise GraphSiteError("graph-site proposed token disposition disagrees with native verifier")
        elif value["accepted"] != (value["candidate_output_sha256"] == value["native_output_sha256"]):
            raise GraphSiteError("graph-site proposed tensor disposition disagrees with native verifier")
    return _plain(value)



def record_execution(state: Mapping[str, Any], observation: Mapping[str, Any]) -> dict[str, Any]:
    """Fold downstream outcome/error and actual native displacement separately."""
    working = _plain(state)
    invocation_value = observation.get("invocation")
    if (working.get("schema") != SCHEMA or observation.get("schema") != OBSERVATION_SCHEMA
            or not isinstance(invocation_value, Mapping)):
        raise GraphSiteError("graph-site execution observation is invalid")
    invocation_body = {key: value for key, value in invocation_value.items() if key != "invocation_sha256"}
    if (invocation_value.get("schema") != INVOCATION_SCHEMA
            or invocation_value.get("invocation_sha256") != _digest(invocation_body)
            or invocation_value.get("source_sha256") != working.get("source_sha256")
            or invocation_value.get("verb") not in {"assist", "replace", "propose"}
            or working.get("backend") not in {"unknown", invocation_value.get("backend")}):
        raise GraphSiteError("graph-site execution observation binding is stale")
    outcome = observation.get("task_outcome", "unknown")
    audit_rejected = observation.get("audit_rejected", False)
    audit_performed = observation.get("audit_performed", False)
    if not isinstance(audit_rejected, bool) or not isinstance(audit_performed, bool):
        raise GraphSiteError("recurrent audit markers must be boolean")
    if audit_rejected and audit_performed:
        raise GraphSiteError("recurrent audit cannot be both accepted and rejected")
    error, omitted = observation.get("observed_error"), observation.get("native_ops_omitted")
    if outcome not in {"success", "failure", "unknown"}:
        raise GraphSiteError("graph-site task outcome is invalid")
    if error is not None and (isinstance(error, bool) or not isinstance(error, (int, float)) or not 0 <= error <= 1):
        raise GraphSiteError("observed graph-site error must be normalized or unavailable")
    if isinstance(omitted, bool) or not isinstance(omitted, int) or omitted < 0:
        raise GraphSiteError("native omitted-op telemetry must be nonnegative")
    if invocation_value["verb"] in {"assist", "propose"} and omitted:
        raise GraphSiteError("assisted or proposed method cannot claim native work omitted")
    key = observation.get("method_key")
    row = working.get("methods", {}).get(key) if isinstance(key, str) else None
    generation = observation.get("method_generation")
    if key is None:
        if (generation is not None or error is not None or outcome != "unknown" or omitted != 0
                or observation.get("intervention") is not None or audit_rejected or audit_performed):
            raise GraphSiteError("refused graph-site execution claimed a method or displacement")
        working["generation"] += 1
        _append_evidence(working, {
            "kind": "refusal", "invocation_sha256": invocation_value["invocation_sha256"],
            "native_ops_omitted": 0,
        })
        return working
    if (not isinstance(row, dict) or not row.get("admitted") or row.get("backed_off")
            or row.get("generation") != generation or row.get("site") != invocation_value.get("site")
            or row.get("specialist") != invocation_value.get("specialist")
            or row.get("dependencies") != invocation_value.get("dependencies")):
        raise GraphSiteError("graph-site telemetry method binding is stale or not admitted")
    if audit_rejected:
        if (invocation_value["verb"] != "replace"
                or row.get("specialist") != "recurrent-dynamics"
                or error is None or float(error) <= MAX_ERROR or omitted != 0
                or outcome != "unknown" or observation.get("intervention") is not None):
            raise GraphSiteError("audited rejection must be an exact recurrent replace failure")
    elif audit_performed:
        if (invocation_value["verb"] != "replace"
                or row.get("specialist") != "recurrent-dynamics"
                or error is None or float(error) > MAX_ERROR or omitted != 0
                or observation.get("intervention") is not None
                or not isinstance(observation.get("successor_state"), Mapping)):
            raise GraphSiteError("audited replacement must prove a supported recurrent successor")
    elif (invocation_value["verb"] == "replace"
          and omitted != row["method"]["native_cost"]["native_ops_omitted"]):
        raise GraphSiteError("replacement receipt disagrees with the declared native subgraph")
    intervention = None
    if invocation_value["verb"] in {"assist", "propose"}:
        intervention = _intervention_receipt(
            observation.get("intervention"), invocation_value["verb"],
            row["specialist"], row["method"]["native_cost"],
        )
    elif observation.get("intervention") is not None:
        raise GraphSiteError("replacement cannot report unperformed assistance or verification")
    successor_digest = None
    if row["specialist"] in {"recurrent-dynamics", "attention-memory"} and (
            omitted or intervention or audit_performed):
        successor_digest = _native_successor_digest(
            observation.get("successor_state"), invocation_value["layer"], row["specialist"]
        )
    if error is not None:
        row["observed_error"] += (float(error) - row["observed_error"]) / (row["error_samples"] + 1)
        row["error_samples"] += 1
    row["task_success"] += outcome == "success"
    row["task_failure"] += outcome == "failure"
    row["native_ops_omitted"] += omitted
    if (error is not None and error > MAX_ERROR) or outcome == "failure":
        row["bad"] += 1
        row["backed_off"] = True
        row["admitted"] = False
    if working.get("backend") == "unknown":
        working["backend"] = invocation_value.get("backend")
    working["telemetry"]["observed_error"] += error is not None
    working["telemetry"]["task_outcome"] += outcome != "unknown"
    working["telemetry"]["native_ops_omitted"] += omitted
    if intervention is not None:
        telemetry = working["telemetry"]
        telemetry["native_ops_executed"] = telemetry.get("native_ops_executed", 0) + intervention["native_ops_executed"]
        telemetry["added_flops"] = telemetry.get("added_flops", 0) + intervention["added_flops"]
        if intervention["mode"] == "assist":
            telemetry["assisted"] = telemetry.get("assisted", 0) + 1
        else:
            telemetry["proposed"] = telemetry.get("proposed", 0) + 1
            name = "proposals_accepted" if intervention["accepted"] else "proposals_rejected"
            telemetry[name] = telemetry.get(name, 0) + 1
    working["generation"] += 1
    _append_evidence(working, {"kind": "execution", "invocation_sha256": invocation_value["invocation_sha256"],
                               "method_key": key, "observed_error": error, "task_outcome": outcome,
                               "native_ops_omitted": omitted,
                               **({"native_successor_sha256": successor_digest}
                                  if successor_digest is not None else {}),
                               **({"audit_performed": True} if audit_performed else {}),
                               **({"audit_rejected": True} if audit_rejected else {}),
                               **({"intervention": intervention} if intervention is not None else {})})
    return working


def record_abstention(state: Mapping[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Retain the exact reason ordinary Qwen ran instead of an eligible field site."""
    binding = receipt.get("invocation")
    if (state.get("schema") != SCHEMA or receipt.get("schema") != ABSTENTION_SCHEMA
            or not isinstance(binding, Mapping)):
        raise GraphSiteError("graph-site abstention receipt is invalid")
    body = {key: value for key, value in binding.items() if key != "invocation_sha256"}
    if (binding.get("schema") != INVOCATION_SCHEMA
            or binding.get("invocation_sha256") != _digest(body)
            or binding.get("source_sha256") != state.get("source_sha256")
            or binding.get("verb") not in VERBS
            or state.get("backend") not in {"unknown", binding.get("backend")}):
        raise GraphSiteError("graph-site abstention binding is stale")
    input_values = receipt.get("input_values")
    output_values = receipt.get("output_values")
    reason = receipt.get("reason")
    if (reason not in {"input-capacity", "output-capacity", "coefficient-capacity",
                       "variable-layout", "unsupported-state"}
            or any(isinstance(value, bool) or not isinstance(value, int) or value < 0
                   for value in (input_values, output_values))
            or receipt.get("maximum_input_values") != MAX_TRAINING_INPUT_VALUES
            or receipt.get("maximum_output_values") != MAX_TRAINING_OUTPUT_VALUES
            or (reason == "input-capacity" and input_values <= MAX_TRAINING_INPUT_VALUES)
            or (reason == "output-capacity" and output_values <= MAX_TRAINING_OUTPUT_VALUES)
            or (reason == "coefficient-capacity"
                and input_values + output_values <= MAX_NATIVE_PROGRAM_VALUES // 4)):
        raise GraphSiteError("graph-site abstention evidence is invalid")
    working = _plain(state)
    if working.get("backend") == "unknown":
        working["backend"] = binding["backend"]
    working["generation"] += 1
    _append_evidence(working, {
        "kind": "abstention", "invocation_sha256": binding["invocation_sha256"],
        "specialist": binding["specialist"], "reason": reason,
        "input_values": input_values, "output_values": output_values,
        "native_ops_omitted": 0,
    })
    return working


def _within_support(values: Any, support: Mapping[str, Any],
                    method: Mapping[str, Any]) -> float | None:
    radius, anchor_norm = support.get("radius"), support.get("anchor_norm")
    if (isinstance(radius, bool) or not isinstance(radius, numeric_types.Real)
            or not math.isfinite(float(radius)) or float(radius) < 0
            or isinstance(anchor_norm, bool) or not isinstance(anchor_norm, numeric_types.Real)
            or not math.isfinite(float(anchor_norm)) or float(anchor_norm) < 0):
        return None
    distance = _support_distance(values, support, method)
    if distance is None:
        return None
    allowance = float(radius) + 1e-5 * max(1.0, float(anchor_norm))
    return distance if distance <= allowance else None


def is_local_recurrent_row(row: Mapping[str, Any]) -> bool:
    """Whether an owner row carries the live local recurrent successor contract."""
    method = row.get("method")
    if not isinstance(method, Mapping):
        return False
    output_desc, input_desc = method.get("output"), method.get("input")
    return (row.get("local_recurrent") is True
            and row.get("local_contract") == "recurrent_successor.v1"
            and isinstance(output_desc, Mapping)
            and output_desc.get("name") == "recurrent_successor"
            and isinstance(input_desc, Mapping)
            and input_desc.get("name") == "recurrent_features"
            and "readout" not in method)


def _eligible_rows(state: Mapping[str, Any], invocation_value: Mapping[str, Any],
                   successor_shapes: Mapping[str, Any] | None,
                   native_state_applicability: Mapping[str, Any] | None
                   ) -> list[dict[str, Any]]:
    if state.get("schema") != SCHEMA or invocation_value.get("schema") != INVOCATION_SCHEMA:
        raise GraphSiteError("graph-site selection inputs are invalid")
    methods = state.get("methods", {})
    if not isinstance(methods, Mapping):
        return []
    specialist = invocation_value.get("specialist")
    result = []
    for key, row in methods.items():
        if not isinstance(row, Mapping):
            continue
        applicability = row.get("applicability", {})
        if (not row.get("admitted") or row.get("backed_off")
                or row.get("site") != invocation_value.get("site")
                or row.get("specialist") != specialist
                or row.get("dependencies") != invocation_value.get("dependencies")
                or not isinstance(applicability, Mapping)
                or row.get("native_state_applicability") != native_state_applicability
                or row.get("successor_shapes") != _policy_layout(
                    successor_shapes, specialist, invocation_value.get("layer"))
                or not all(invocation_value.get(name) == expected
                           for name, expected in applicability.items()
                           if name not in {"successor_shapes", "tensor_layout"})):
            continue
        method = row.get("method")
        if not isinstance(method, Mapping):
            raise GraphSiteError("admitted graph-site method descriptor is invalid")
        output_desc, input_desc = method.get("output"), method.get("input")
        if (isinstance(output_desc, Mapping)
                and output_desc.get("name") == "recurrent_projection"):
            # Historical projection-only evidence is retained but never a full transition.
            continue
        if specialist == "recurrent-dynamics" and not is_local_recurrent_row(row):
            continue
        _validate_method(method)
        selected = _plain(row)
        selected["key"] = key
        result.append(selected)
    return result


def select(state: Mapping[str, Any], invocation_value: Mapping[str, Any],
           *, successor_shapes: Mapping[str, Any] | None = None,
           native_state_applicability: Mapping[str, Any] | None = None,
           input_values: Any = None) -> dict[str, Any] | None:
    """Return the nearest admitted exact-dependency method supported by this input."""
    rows = _eligible_rows(
        state, invocation_value, successor_shapes, native_state_applicability)
    if invocation_value.get("specialist") != "recurrent-dynamics":
        return rows[0] if rows else None
    choices = []
    for row in rows:
        method = row["method"]
        support = method.get("input_support")
        if not isinstance(support, Mapping):
            continue
        distance = _within_support(input_values, support, method)
        if distance is not None:
            choices.append((distance, row["key"], row))
    return min(choices, key=lambda item: (item[0], item[1]))[2] if choices else None


def _value_shape(value: Any) -> tuple[int, ...] | None:
    shape = getattr(value, "shape", None)
    if shape is not None:
        try:
            return tuple(int(dimension) for dimension in shape)
        except (TypeError, ValueError):
            return None
    if not isinstance(value, (list, tuple)):
        return ()
    dimensions, current = [], value
    while isinstance(current, (list, tuple)):
        dimensions.append(len(current))
        current = current[0] if current else None
    return tuple(dimensions)


def _value_dtype(value: Any, metadata: Mapping[str, Any], name: str) -> str | None:
    dtypes = metadata.get("tensor_dtypes")
    dtype = dtypes.get(name) if isinstance(dtypes, Mapping) else getattr(value, "dtype", None)
    if dtype is None:
        return None
    label = str(dtype).lower().replace("torch.", "").replace("numpy.", "")
    return {"float32": "f32", "f32": "f32"}.get(label)


def candidates_for_site(resident_model_or_program_state: Mapping[str, Any],
                        request: Mapping[str, Any], arrays: Mapping[str, Any],
                        metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return bounded recurrent local candidates nearest-first for nested preflight."""
    if not isinstance(resident_model_or_program_state, Mapping):
        return []
    resident = resident_model_or_program_state.get("resident_model", resident_model_or_program_state)
    if not isinstance(resident, Mapping):
        return []
    site, policies = request.get("graph_site"), resident.get("policies")
    graph_state = resident.get("graph_sites")
    if graph_state is None and isinstance(policies, Mapping):
        graph_state = policies.get("graph_sites")
    if (not isinstance(graph_state, Mapping) or not isinstance(site, Mapping)
            or site.get("schema") != "cassifi.graph-site-request.v1"
            or not isinstance(arrays, Mapping) or not isinstance(metadata, Mapping)):
        return []
    source = request.get("source_sha256")
    if source != resident.get("source_sha256") or source != site.get("source_sha256"):
        return []
    backend = str(metadata.get("backend", site.get("backend", "")))
    if not backend or site.get("backend") not in {"unknown", backend}:
        return []
    specialist, stage, layer = site.get("specialist"), request.get("stage"), request.get("layer")
    if (SITE_STAGES.get((site.get("architecture"), specialist)) != stage
            or specialist == "expert-synthesis" and "router_ids" not in arrays
            or specialist in {"recurrent-dynamics", "attention-memory"}
            and (isinstance(layer, bool) or not isinstance(layer, int))
            or specialist == "execution-choice" and layer is not None
            or specialist not in SPECIALISTS):
        return []
    invocation_value = invocation(
        source_sha256=str(source), architecture=str(site.get("architecture", "")), backend=backend,
        sequence_id=str(site.get("sequence_id", "")), position=int(site.get("position", -1)),
        stage=str(site.get("stage", "")), layer=site.get("layer"), site=str(site.get("site", "")),
        specialist=str(site.get("specialist", "")),
        predecessor_generation=int(site.get("predecessor_generation", -1)),
        predecessor_sha256=str(site.get("predecessor_snapshot_sha256", "")),
        intervention_order=int(site.get("intervention_order", -1)),
        dependencies=site.get("dependencies", {}), request_sha256=str(request.get("request_sha256", "")),
        verb=str(site.get("verb", "observe")))
    shapes = metadata.get("successor_shapes") \
        if specialist in {"recurrent-dynamics", "attention-memory"} else None
    state_applicability = metadata.get("native_state_applicability")
    if specialist == "recurrent-dynamics":
        selected_rows = _eligible_rows(graph_state, invocation_value, shapes, state_applicability)
    else:
        selected = select(
            graph_state, invocation_value, successor_shapes=shapes,
            native_state_applicability=state_applicability)
        selected_rows = [selected] if selected is not None else []

    supported: list[tuple[float, str, dict[str, Any]]] = []
    for selected in selected_rows:
        method = selected["method"]
        input_name = method["input"]["name"]
        if input_name not in arrays:
            continue
        input_value = arrays[input_name]
        if (_value_shape(input_value) != tuple(method["input"]["shape"])
                or _value_dtype(input_value, metadata, input_name) != method["input"]["dtype"]
                or metadata.get("native_state_applicability") != method["native_state_applicability"]
                or not hasattr(input_value, "reshape")):
            continue
        flattened = input_value.reshape(-1)
        support = method.get("input_support")
        if not isinstance(support, Mapping):
            continue
        numel = (
            input_value.numel()
            if callable(getattr(input_value, "numel", None))
            else getattr(input_value, "size", None)
        )
        anchor = support.get("anchor")
        if (anchor is not None and (not isinstance(anchor, (list, tuple)) or len(anchor) != numel)
                or anchor is None and (method.get("rank") != 1 or len(method["A"]) != numel)):
            continue
        distance = _within_support(flattened, support, method)
        if distance is None:
            continue
        candidate_value = {
            "schema": "cassifi.graph-site-selection.v1", "invocation": invocation_value,
            "method_key": selected["key"], "method_generation": selected["generation"],
            "applicability": _plain(selected["applicability"]), "method": _plain(method),
            "predecessor_snapshot_sha256": site.get("predecessor_snapshot_sha256"),
        }
        supported.append((distance, selected["key"], candidate_value))
    supported.sort(key=lambda item: (item[0], item[1]))
    limit = MAX_LOCAL_RECURRENT_METHODS if specialist == "recurrent-dynamics" else 1
    return [item[2] for item in supported[:limit]]


def candidate_for_site(resident_model_or_program_state: Mapping[str, Any], request: Mapping[str, Any],
                       arrays: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    """Select the nearest owner-trained method for this exact resident executor input."""
    candidates = candidates_for_site(resident_model_or_program_state, request, arrays, metadata)
    return candidates[0] if candidates else None


def _native_digest(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


def _native_integer(value: Any, *, minimum: int = 0) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= minimum


def native_program_for_site(resident_model_or_program_state: Mapping[str, Any],
                            request: Mapping[str, Any],
                            metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    """Build the exact CAPI candidate and guard from an owner-held admitted method."""
    resident = resident_model_or_program_state.get(
        "resident_model", resident_model_or_program_state)
    if not isinstance(resident, Mapping):
        return None
    site, preflight, native_site = (
        request.get("graph_site"), request.get("native_preflight"), request.get("native_site")
    )
    graph_state = resident.get("graph_sites")
    if graph_state is None and isinstance(resident.get("policies"), Mapping):
        graph_state = resident["policies"].get("graph_sites")
    if (not isinstance(graph_state, Mapping)
            or not isinstance(site, Mapping) or site.get("schema") != "cassifi.graph-site-request.v1"
            or not isinstance(preflight, Mapping) or not isinstance(native_site, Mapping)
            or not isinstance(metadata.get("native_state_applicability"), Mapping)
            or request.get("request_sha256_pending") is not True
            or request.get("request_sha256") != ""):
        return None
    preflight_seq = preflight.get("seq_id", preflight.get("native_seq_id"))
    preflight_position = preflight.get("position", preflight.get("next_position"))
    preflight_predecessor = preflight.get("native_predecessor_sha256")
    preflight_field_epoch = preflight.get(
        "native_field_epoch_sha256", preflight.get("field_epoch_sha256"))
    preflight_digest = preflight.get(
        "native_preflight_sha256", preflight.get("preflight_sha256"))
    preflight_sampler = preflight.get("sampler")
    preflight_sites = preflight.get("sites")
    if (preflight.get("schema") != "cassifi.native-graph-site-preflight.v1"
            or preflight.get("task_id") != request.get("task_id")
            or request.get("model_sha256") != preflight.get("model_sha256")
            or request.get("tokenizer_sha256") != preflight.get("tokenizer_sha256")
            or request.get("source_sha256") != preflight.get("source_sha256")
            or request.get("sequence_id") != preflight.get("sequence_id")
            or request.get("seq_id") != preflight_seq
            or request.get("position") != preflight_position
            or request.get("native_preflight_sha256") != preflight_digest
            or request.get("native_predecessor_sha256") != preflight_predecessor
            or request.get("native_field_epoch_sha256") != preflight_field_epoch
            or request.get("native_operation_id") != preflight.get("native_operation_id")
            or not _native_integer(preflight_seq)
            or not _native_integer(preflight_position)
            or not _native_digest(preflight_digest)
            or not _native_digest(preflight_predecessor)
            or not _native_digest(preflight_field_epoch)
            or not _native_digest(preflight.get("model_sha256"))
            or not _native_digest(preflight.get("source_sha256"))
            or not _native_digest(preflight.get("tokenizer_sha256"))
            or not isinstance(preflight_sites, list) or not preflight_sites
            or len(preflight_sites) > 4096):
        return None

    sampler = request.get("sampler")
    sampler_sha256 = preflight.get("sampler_sha256")
    if (not isinstance(sampler, Mapping) or not isinstance(preflight_sampler, Mapping)
            or set(preflight_sampler) != {"mode", "temperature", "top_k", "draw"}
            or sampler != preflight_sampler
            or not isinstance(preflight_sampler.get("mode"), str)
            or preflight_sampler.get("mode") not in {"greedy", "categorical"}
            or isinstance(preflight_sampler.get("temperature"), bool)
            or not isinstance(preflight_sampler.get("temperature"), (int, float))
            or not math.isfinite(preflight_sampler["temperature"])
            or preflight_sampler["temperature"] <= 0
            or not _native_integer(preflight_sampler.get("top_k"))
            or isinstance(preflight_sampler.get("draw"), bool)
            or not isinstance(preflight_sampler.get("draw"), (int, float))
            or not math.isfinite(preflight_sampler["draw"])
            or not 0 <= preflight_sampler["draw"] < 1
            or not _native_digest(sampler_sha256)
            or _digest(preflight_sampler) != sampler_sha256):
        return None
    source, backend = request.get("source_sha256"), metadata.get("backend")
    if (source != resident.get("source_sha256") or source != graph_state.get("source_sha256")
            or source != site.get("source_sha256") or source != preflight.get("source_sha256")
            or request.get("model_sha256") != preflight.get("model_sha256")
            or request.get("tokenizer_sha256") != preflight.get("tokenizer_sha256")
            or site.get("model_sha256") != request.get("model_sha256")
            or site.get("tokenizer_sha256") != request.get("tokenizer_sha256")
            or graph_state.get("backend") not in {"unknown", backend}
            or site.get("backend") != backend or request.get("backend") != backend
            or not isinstance(backend, str) or not backend
            or site.get("architecture") != request.get("architecture")
            or site.get("architecture") != "qwen35moe"
            or site.get("sequence_id") != preflight.get("sequence_id")
            or site.get("sequence_id") != request.get("sequence_id")
            or site.get("seq_id") != preflight_seq
            or site.get("seq_id") != request.get("seq_id")
            or site.get("position") != preflight_position
            or site.get("position") != request.get("position")
            or request.get("native_operation_id") != preflight.get("native_operation_id")
            or request.get("native_operation_id") != site.get("native_operation_id")
            or site.get("native_preflight_sha256") != preflight_digest
            or site.get("native_predecessor_sha256") != preflight_predecessor
            or site.get("native_field_epoch_sha256") != preflight_field_epoch
            or site.get("sampler") != preflight_sampler
            or site.get("sampler_sha256") != sampler_sha256
            or request.get("sampler_sha256") != sampler_sha256
            or site.get("verb") != "replace"):
        return None

    specialist, stage = site.get("specialist"), site.get("stage")
    kind = native_site.get("kind")
    if (specialist == "expert-synthesis" and (stage != "qwen-experts" or kind != 1
                                               or request.get("stage") != "qwen-experts")
            or specialist == "recurrent-dynamics" and (
                stage != "qwen-attention-route" or kind != 2
                or request.get("stage") != "qwen-attention-route")
            or specialist == "attention-memory" and (
                stage != "qwen-attention-route" or kind != 3
                or request.get("stage") != "qwen-attention-route")
            or specialist == "execution-choice" and (
                stage != "qwen-head" or kind != 6
                or request.get("stage") != "qwen-head")
            or specialist not in {"expert-synthesis", "recurrent-dynamics",
                                   "attention-memory", "execution-choice"}
            or (specialist == "execution-choice"
                and (isinstance(site.get("layer"), bool) or site.get("layer") != -1))
            or (specialist != "execution-choice" and not _native_integer(site.get("layer")))
            or request.get("layer") != site.get("layer")
            or not _native_integer(site.get("position"))
            or not _native_integer(site.get("predecessor_generation"))
            or not _native_integer(site.get("intervention_order"))
            or not _native_digest(site.get("predecessor_snapshot_sha256"))):
        return None

    descriptor_keys = (
        "kind", "layer", "input_width", "output_width", "stage", "site", "specialist",
        "input_tensor", "output_tensor", "dependencies_json",
    )
    if (native_site.get("supported") is not True
            or native_site.get("refusal") != ""
            or any(key not in native_site for key in descriptor_keys)
            or any(not _native_integer(native_site.get(key), minimum=1 if key in {
                "input_width", "output_width"
            } else 0) for key in ("kind", "layer", "input_width", "output_width"))
            or any(not isinstance(native_site.get(key), str) or not native_site[key]
                   for key in ("stage", "site", "specialist", "input_tensor", "output_tensor",
                               "dependencies_json"))):
        return None
    descriptor_matches = [
        descriptor for descriptor in preflight_sites
        if isinstance(descriptor, Mapping)
        and all(descriptor.get(key) == native_site.get(key) for key in descriptor_keys)
        and descriptor.get("supported") is True
        and descriptor.get("refusal") == ""
    ]
    if (len(descriptor_matches) != 1 or native_site != descriptor_matches[0]
            or any(native_site.get(key) != site.get(key)
                   for key in ("stage", "site", "specialist", "layer"))):
        return None
    try:
        native_dependencies = json.loads(native_site["dependencies_json"])
    except (TypeError, ValueError):
        return None
    if (not isinstance(native_dependencies, Mapping)
            or native_site.get("dependencies") != native_dependencies
            or native_dependencies.get("architecture") != "qwen35moe"
            or native_dependencies.get("layer") != site.get("layer")):
        return None

    dependencies = site.get("dependencies")
    if not isinstance(dependencies, Mapping):
        return None
    owner_state = {
        "membrane_profile": dependencies.get("membrane_profile"),
        "field_epoch_sha256": dependencies.get("field_epoch_sha256"),
    }
    field_epoch = owner_state["field_epoch_sha256"]
    supplied_state = metadata.get("native_state_applicability")
    if (not isinstance(owner_state["membrane_profile"], Mapping)
            or not _native_digest(field_epoch)
            or not isinstance(supplied_state, Mapping)
            or any(supplied_state.get(key) != value for key, value in owner_state.items())):
        return None
    if preflight.get("native_preflight_sha256") != request.get("native_preflight_sha256"):
        return None

    invocation_value = invocation(
        source_sha256=source, architecture="qwen35moe", backend=backend,
        sequence_id=site["sequence_id"], position=site["position"],
        stage=site["stage"], layer=(None if specialist == "execution-choice" else site["layer"]),
        site=site["site"],
        specialist=specialist, predecessor_generation=site["predecessor_generation"],
        predecessor_sha256=site["predecessor_snapshot_sha256"],
        intervention_order=site["intervention_order"], dependencies=dependencies,
        request_sha256="", request_sha256_pending=True, verb="replace")

    shapes = (metadata.get("successor_shapes")
              if specialist in {"recurrent-dynamics", "attention-memory"} else None)
    if (specialist in {"recurrent-dynamics", "attention-memory"}
            and not isinstance(shapes, Mapping)):
        return None
    # Never broaden expert selection beyond the caller's exact route guard.
    route_guards: list[Mapping[str, Any]] = []
    if specialist == "expert-synthesis":
        expert_count = native_dependencies.get("expert_count")
        experts_per_token = native_dependencies.get("experts_per_token")
        if (not _native_integer(expert_count, minimum=1)
                or not _native_integer(experts_per_token, minimum=1)
                or experts_per_token > expert_count):
            return None
        route = supplied_state.get("expert_route")
        expert_ids = route.get("expert_ids") if isinstance(route, Mapping) else None
        top_k = route.get("top_k") if isinstance(route, Mapping) else None
        if (not isinstance(route, Mapping)
                or not isinstance(expert_ids, (list, tuple))
                or len(expert_ids) != experts_per_token
                or any(not _native_integer(value) or value >= expert_count
                       for value in expert_ids)
                or len(set(expert_ids)) != experts_per_token
                or not _native_integer(top_k, minimum=1)
                or top_k != experts_per_token):
            return None
        route_guards = [supplied_state]
    elif specialist == "recurrent-dynamics":
        if supplied_state != owner_state:
            return None
        route_guards = [owner_state]
        expected_shapes = {
            f"conv_history.{site['layer']}": [
                native_dependencies.get("conv_history_rows"),
                native_dependencies.get("conv_history_channels"),
            ],
            f"recurrent_state.{site['layer']}": [
                native_dependencies.get("recurrent_state_heads"),
                native_dependencies.get("recurrent_state_value_width"),
                native_dependencies.get("recurrent_state_key_width"),
            ],
        }
        for name, expected_shape in expected_shapes.items():
            desc = shapes.get(name)
            if (not isinstance(desc, Mapping) or desc.get("shape") != expected_shape
                    or desc.get("dtype") != "<f4" or desc.get("order") != "C"):
                return None
        hidden_desc = shapes.get("hidden")
        if (not isinstance(hidden_desc, Mapping) or hidden_desc.get("dtype") != "<f4"
                or hidden_desc.get("order") != "C"
                or hidden_desc.get("shape") != [native_site["input_width"]
                    - _shape_width(expected_shapes[f"conv_history.{site['layer']}"])
                    - _shape_width(expected_shapes[f"recurrent_state.{site['layer']}"]) ]):
            return None
    elif specialist == "attention-memory":
        if supplied_state != owner_state:
            return None
        route_guards = [owner_state]
        kv_heads = native_dependencies.get("kv_heads")
        kv_head_width = native_dependencies.get("kv_head_width")
        if (not _native_integer(kv_heads, minimum=1)
                or not _native_integer(kv_head_width, minimum=1)
                or native_site.get("input_tensor") != "attention_features"
                or native_site.get("output_tensor") != "attention_successor"):
            return None
        expected_shapes = {
            f"kv_k.{site['layer']}": [kv_heads, kv_head_width],
            f"kv_v.{site['layer']}": [kv_heads, kv_head_width],
        }
        for name, expected_shape in expected_shapes.items():
            desc = shapes.get(name)
            if (not isinstance(desc, Mapping) or desc.get("shape") != expected_shape
                    or desc.get("dtype") != "<f4" or desc.get("order") != "C"):
                return None
        hidden_desc = shapes.get("hidden")
        if (not isinstance(hidden_desc, Mapping) or hidden_desc.get("dtype") != "<f4"
                or hidden_desc.get("order") != "C"
                or hidden_desc.get("shape") != [native_site["input_width"]]):
            return None
    else:
        if supplied_state != owner_state:
            return None
        route_guards = [owner_state]
        if (native_site.get("input_tensor") != "head_input"
                or native_site.get("output_tensor") != "logits"):
            return None

    selected_rows: list[dict[str, Any]] = []
    for state_guard in route_guards:
        selected_rows.extend(_eligible_rows(
            graph_state, invocation_value, shapes, state_guard))
    if not selected_rows:
        return None
    selected = min(selected_rows, key=lambda row: row["key"])
    method = selected.get("method")
    if not isinstance(method, Mapping):
        return None
    input_desc, output_desc = method.get("input"), method.get("output")
    if (not isinstance(input_desc, Mapping) or not isinstance(output_desc, Mapping)
            or input_desc.get("dtype") != "f32" or output_desc.get("dtype") != "f32"
            or input_desc.get("name") != native_site.get("input_tensor")
            or output_desc.get("name") != native_site.get("output_tensor")
            or _shape_width(input_desc.get("shape")) != native_site.get("input_width")
            or _shape_width(output_desc.get("shape")) != native_site.get("output_width")):
        return None
    _validate_method(method)
    support = method.get("input_support")
    if not isinstance(support, Mapping):
        return None
    rank = method["rank"]
    anchor = support.get("anchor")
    if (anchor is None and (specialist in {"recurrent-dynamics", "attention-memory"} or rank != 1)
            or anchor is not None and len(anchor) != native_site["input_width"]):
        return None
    coefficients = (native_site["input_width"] * rank + rank * native_site["output_width"]
                    + native_site["output_width"])
    if coefficients > MAX_NATIVE_PROGRAM_VALUES:
        return None
    route = supplied_state.get("expert_route", {})
    route_ids = route.get("expert_ids", []) if specialist == "expert-synthesis" else []
    if (specialist == "expert-synthesis"
            and len(route_ids) != native_dependencies["experts_per_token"]):
        return None

    program = {
        "schema": NATIVE_PROGRAM_SCHEMA,
        "invocation": invocation_value,
        "method_key": selected["key"],
        "method_generation": selected["generation"],
        "applicability": _plain(selected["applicability"]),
        "method": _plain(method),
        "predecessor_snapshot_sha256": site["predecessor_snapshot_sha256"],
    }
    program["candidate_sha256"] = _digest(program)
    native_candidate = {
        "kind": kind, "seq_id": preflight["native_seq_id"],
        "position": preflight["next_position"], "layer": site["layer"],
        "owner_generation": request["owner_generation"],
        "predecessor_generation": site["predecessor_generation"],
        "sequence_id": preflight["sequence_id"], "source_sha256": preflight["source_sha256"],
        "architecture": "qwen35moe", "backend": backend,
        "input_tensor": input_desc["name"], "output_tensor": output_desc["name"],
        "tensor_dtype": "f32", "stage": native_site["stage"], "site": native_site["site"],
        "specialist": native_site["specialist"],
        "predecessor_sha256": site["predecessor_snapshot_sha256"],
        "request_sha256": "", "request_sha256_pending": True,
        "invocation_sha256": invocation_value["invocation_sha256"],
        "candidate_sha256": program["candidate_sha256"],
        "intervention_order": str(site["intervention_order"]),
        "dependencies_json": native_site["dependencies_json"],
        "method_key": METHOD_SCHEMA, "method_generation": selected["generation"],
        "input_width": native_site["input_width"], "rank": rank,
        "output_width": native_site["output_width"],
        "a": [value for row in method["A"] for value in row],
        "b": [value for row in method["B"] for value in row],
        "bias": list(method["bias"]),
        "conv_history_rows": native_dependencies.get("conv_history_rows", 0),
        "conv_history_channels": native_dependencies.get("conv_history_channels", 0),
        "recurrent_state_heads": native_dependencies.get("recurrent_state_heads", 0),
        "recurrent_state_value_width": native_dependencies.get("recurrent_state_value_width", 0),
        "recurrent_state_key_width": native_dependencies.get("recurrent_state_key_width", 0),
        "attn_kv_heads": native_dependencies.get("kv_heads", 0),
        "attn_kv_head_width": native_dependencies.get("kv_head_width", 0),
    }
    native_guard = {
        "candidate_id": program["candidate_sha256"],
        "verb": 1,
        "native_preflight_sha256": preflight["native_preflight_sha256"],
        "native_predecessor_sha256": preflight["predecessor_sha256"],
        "owner_snapshot_sha256": site["predecessor_snapshot_sha256"],
        "field_epoch_sha256": preflight["native_field_epoch_sha256"],
        "input_support_anchor": list(anchor) if anchor is not None else [],
        "input_support_radius": float(support["radius"]),
        "input_support_anchor_norm": float(support["anchor_norm"]),
        "expected_expert_ids": list(route_ids),
    }
    program["native_candidate"] = native_candidate
    program["native_guard"] = native_guard
    return program
