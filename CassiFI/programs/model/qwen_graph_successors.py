"""Exact tensor layout helpers for Qwen recurrent and attention graph sites."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


def successor_names(kind: str, layer: int) -> tuple[str, str, str]:
    """Return the graph-site successor tensor names in canonical flat order."""
    if isinstance(layer, bool) or not isinstance(layer, int) or layer < 0:
        raise ValueError("Qwen graph layer must be a nonnegative integer")
    if kind == "recurrent":
        return "hidden", f"conv_history.{layer}", f"recurrent_state.{layer}"
    if kind == "attention":
        return "hidden", f"kv_k.{layer}", f"kv_v.{layer}"
    raise ValueError("Qwen graph successor kind must be recurrent or attention")


def _f32_c_array(value: Any, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype != np.dtype("<f4"):
        raise ValueError(f"Qwen graph tensor {name} must have dtype <f4")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"Qwen graph tensor {name} contains non-finite values")
    return array


def _flatten(array: np.ndarray) -> np.ndarray:
    # ravel is a view for contiguous inputs and makes only the required C-order
    # copy for strided inputs.
    return array.ravel(order="C")


def _state_arrays(state: Mapping[str, Any], state_names: Sequence[str]) -> list[np.ndarray]:
    if not isinstance(state, Mapping):
        raise ValueError("Qwen graph state must be a named tensor mapping")
    if (not state_names or len(set(state_names)) != len(state_names)
            or any(not isinstance(name, str) or not name or name == "hidden" for name in state_names)):
        raise ValueError("Qwen graph state names must be nonempty and unique")
    if set(state) != set(state_names):
        raise ValueError("Qwen graph state tensors do not match the required named state")
    return [_f32_c_array(state[name], name) for name in state_names]


def build_pre_state_features(hidden: Any, state: Mapping[str, Any],
                             state_names: Sequence[str]) -> np.ndarray:
    """Flatten hidden then each required named pre-attention state tensor."""
    arrays = [_f32_c_array(hidden, "hidden"), *_state_arrays(state, state_names)]
    flat = [_flatten(array) for array in arrays]
    return np.concatenate(flat) if len(flat) > 1 else flat[0]


def derive_successor_shapes(expected_shapes: Mapping[str, Any],
                            state_names: Sequence[str]) -> dict[str, dict[str, Any]]:
    """Describe exact next-state dimensions supplied by the executor."""
    names = ("hidden", *state_names)
    if (not isinstance(expected_shapes, Mapping) or len(set(names)) != len(names)
            or not state_names or set(expected_shapes) != set(names)):
        raise ValueError("Qwen graph expected successor tensors are incomplete or unexpected")
    result: dict[str, dict[str, Any]] = {}
    for name in names:
        value = expected_shapes[name]
        if isinstance(value, Mapping) and "shape" in value:
            shape = value["shape"]
        elif hasattr(value, "shape"):
            array = _f32_c_array(value, name)
            shape = array.shape
        else:
            shape = value
        if (not isinstance(shape, (list, tuple)) or not shape
                or any(isinstance(dim, bool) or not isinstance(dim, (int, np.integer)) or dim < 1
                       for dim in shape)):
            raise ValueError(f"Qwen graph expected shape for {name} is invalid")
        result[name] = {"shape": [int(dim) for dim in shape], "dtype": "<f4", "order": "C"}
    return result


def _validated_layout(successor_shapes: Mapping[str, Any]) -> tuple[tuple[str, tuple[int, ...]], ...]:
    if not isinstance(successor_shapes, Mapping) or not successor_shapes:
        raise ValueError("Qwen graph successor shapes must be a nonempty mapping")
    layout: list[tuple[str, tuple[int, ...]]] = []
    for name, descriptor in successor_shapes.items():
        if not isinstance(name, str) or not name or not isinstance(descriptor, Mapping):
            raise ValueError("Qwen graph successor descriptor is invalid")
        shape = descriptor.get("shape")
        if (descriptor.get("dtype") != "<f4" or descriptor.get("order") != "C"
                or not isinstance(shape, (list, tuple)) or not shape
                or any(isinstance(dim, bool) or not isinstance(dim, (int, np.integer)) or dim < 1 for dim in shape)):
            raise ValueError(f"Qwen graph successor descriptor for {name} is invalid")
        layout.append((name, tuple(int(dim) for dim in shape)))
    if layout[0][0] != "hidden":
        raise ValueError("Qwen graph successor layout must start with hidden")
    return tuple(layout)


def serialize_successor_state(hidden: Any, state: Mapping[str, Any],
                              state_names: Sequence[str],
                              successor_shapes: Mapping[str, Any]) -> np.ndarray:
    """Serialize hidden and the full native next-state mapping to the graph target."""
    layout = _validated_layout(successor_shapes)
    names = ("hidden", *state_names)
    if tuple(name for name, _ in layout) != names:
        raise ValueError("Qwen graph successor layout does not match canonical tensor order")
    arrays = [_f32_c_array(hidden, "hidden"), *_state_arrays(state, state_names)]
    pieces = []
    for (name, shape), array in zip(layout, arrays):
        if array.shape != shape:
            raise ValueError(f"Qwen graph successor shape mismatch for {name}")
        pieces.append(_flatten(array))
    return np.concatenate(pieces) if len(pieces) > 1 else pieces[0]


def split_successor_state(flat: Any, successor_shapes: Mapping[str, Any]) -> dict[str, np.ndarray]:
    """Split a learned flat successor into exact named C-order tensor views."""
    layout = _validated_layout(successor_shapes)
    vector = _f32_c_array(flat, "flat successor")
    if vector.ndim != 1:
        raise ValueError("Qwen graph learned successor must be one-dimensional")
    if not vector.flags.c_contiguous:
        vector = np.ascontiguousarray(vector)
    sizes = [math.prod(shape) for _, shape in layout]
    if vector.size != sum(sizes):
        raise ValueError("Qwen graph learned successor width does not match declared shapes")
    output: dict[str, np.ndarray] = {}
    offset = 0
    for (name, shape), size in zip(layout, sizes):
        output[name] = vector[offset:offset + size].reshape(shape, order="C")
        offset += size
    return output
