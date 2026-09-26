"""Resumable field-owned Python execution.

This is a continuation machine over JSON-canonical records.  It deliberately
uses neither ``exec`` nor ``eval`` nor host Python code objects.  The host runs
only fixed bounded primitives; guest source, heap objects, frames, generators,
imports, branches, and pending effects are explicit values in the regional
state returned after every quantum.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import operator
from typing import Any, Mapping, MutableMapping, Sequence

from programs.optimizer.compiler import (
    OptimizationCompilerError,
    compile_constant_fold_at,
    compile_guarded_load_name,
    validate_portable_artifact,
)
from programs.optimizer.records import CompiledArtifact

from .compiler import CompilerError, compile_python
from .records import (
    ComputationView,
    PythonProgram,
    canonical_json_bytes,
    default_python_semantics,
    digest_value,
)


RUNTIME_SCHEMA = "cassifi.field-python-runtime.v1"
RUNTIME_RESULT_SCHEMA = "cassifi.field-python-result.v1"
DEFAULT_LIMITS = {
    "max_heap_objects": 16_384,
    "max_frames": 1_024,
    "max_tasks": 1_024,
    "max_operations": 1_024,
    "max_collection_items": 65_536,
    "max_optimizations": 1_024,
    "max_string_bytes": 1_048_576,
    "max_integer_bits": 1_048_576,
    "max_call_depth": 512,
    "max_source_bytes": 1_048_576,
    "max_programs": 512,
    "max_branches": 128,
    "max_events": 4_096,
}


class RuntimeError(ValueError):
    """Invalid field runtime state or operation."""


class _GuestSignal(Exception):
    def __init__(self, exception: Mapping[str, Any]) -> None:
        super().__init__("guest exception")
        self.exception = exception



class _ResourceLimitPause(BaseException):
    """Internal quota wait; deliberately not a guest-catchable exception."""

    def __init__(self, limit: str, required: int, message: str) -> None:
        super().__init__(message)
        self.limit = limit
        self.required = required
        self.message = message

def _plain(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value).decode("utf-8"))


def _v_none() -> dict[str, Any]:
    return {"t": "none"}


def _v_bool(value: bool) -> dict[str, Any]:
    return {"t": "bool", "v": bool(value)}


def _v_int(value: int) -> dict[str, Any]:
    return {"t": "int", "v": str(int(value))}


def _v_float(value: float) -> dict[str, Any]:
    return {"t": "float", "v": float(value).hex()}


def _v_complex(value: complex) -> dict[str, Any]:
    return {"t": "complex", "r": value.real.hex(), "i": value.imag.hex()}


def _v_str(value: str) -> dict[str, Any]:
    return {"t": "str", "v": value}


def _v_bytes(value: bytes) -> dict[str, Any]:
    return {"t": "bytes", "v": base64.b64encode(value).decode("ascii")}


def _v_ref(object_id: str, generation: int = 1) -> dict[str, Any]:
    return {"t": "ref", "id": object_id, "g": generation}


def _v_builtin(name: str) -> dict[str, Any]:
    return {"t": "builtin", "v": name}


def _v_type(name: str) -> dict[str, Any]:
    return {"t": "type", "v": name}


def _v_exception_type(name: str) -> dict[str, Any]:
    return {"t": "exception-type", "v": name}


def _v_method(name: str, target: Mapping[str, Any]) -> dict[str, Any]:
    return {"t": "method", "name": name, "self": _plain(target)}


def _is_value(value: Any) -> bool:
    return isinstance(value, Mapping) and isinstance(value.get("t"), str)


def _as_int(value: Mapping[str, Any]) -> int:
    if value.get("t") == "bool":
        return int(bool(value["v"]))
    if value.get("t") != "int":
        raise TypeError("expected integer")
    return int(value["v"])


def _as_float(value: Mapping[str, Any]) -> float:
    if value.get("t") == "float":
        return float.fromhex(str(value["v"]))
    if value.get("t") in {"int", "bool"}:
        return float(_as_int(value))
    raise TypeError("expected real number")


def _as_complex(value: Mapping[str, Any]) -> complex:
    if value.get("t") == "complex":
        return complex(float.fromhex(str(value["r"])), float.fromhex(str(value["i"])))
    return complex(_as_float(value))


def _as_str(value: Mapping[str, Any]) -> str:
    if value.get("t") != "str":
        raise TypeError("expected string")
    return str(value["v"])


def _as_bytes(value: Mapping[str, Any]) -> bytes:
    if value.get("t") != "bytes":
        raise TypeError("expected bytes")
    return base64.b64decode(str(value["v"]).encode("ascii"), validate=True)


def _ref_id(value: Mapping[str, Any]) -> str:
    if value.get("t") != "ref" or not isinstance(value.get("id"), str):
        raise TypeError("expected object reference")
    return str(value["id"])


def _check_value(value: Any) -> Mapping[str, Any]:
    if not _is_value(value):
        raise RuntimeError("runtime value is invalid")
    return value


def _limit(state: Mapping[str, Any], name: str) -> int:
    value = state["limits"].get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RuntimeError(f"runtime limit {name} is invalid")
    return value


def _next_id(state: MutableMapping[str, Any], kind: str) -> str:
    counters = state["counters"]
    value = int(counters[kind])
    counters[kind] = value + 1
    return f"{kind[0]}{value}"


def _heap_object(state: Mapping[str, Any], value: Mapping[str, Any]) -> MutableMapping[str, Any]:
    object_id = _ref_id(value)
    item = state["heap"].get(object_id)
    if not isinstance(item, MutableMapping) or int(item.get("generation", 0)) != int(value.get("g", -1)):
        raise RuntimeError("object reference is stale")
    return item


def _alloc(
    state: MutableMapping[str, Any],
    kind: str,
    payload: Mapping[str, Any],
    *,
    type_name: str | None = None,
    scope: str = "root",
    finalizer: bool = False,
) -> dict[str, Any]:
    if len(state["heap"]) >= _limit(state, "max_heap_objects"):
        if state.get("_instruction_active") is True:
            raise _ResourceLimitPause(
                "max_heap_objects",
                len(state["heap"]) + 1,
                "field heap object limit exhausted",
            )
        raise _GuestSignal(
            _emergency_exception(
                state,
                "MemoryError",
                "field heap object limit exhausted",
            )
        )
    object_id = _next_id(state, "object")
    state["heap"][object_id] = {
        "schema": "cassifi.py-object-state.v1",
        "id": object_id,
        "generation": 1,
        "kind": kind,
        "type_name": type_name or kind,
        "version": 0,
        "payload": _plain(dict(payload)),
        "scope": scope,
        "gc": {
            "finalizer": bool(finalizer),
            "finalized": False,
            "resurrected": False,
            "weakrefs": [],
        },
    }
    state["ledger"]["allocations"] += 1
    return _v_ref(object_id)


def _emergency_exception(
    state: MutableMapping[str, Any],
    type_name: str,
    message: str,
) -> Mapping[str, Any]:
    roots = state.setdefault("runtime_roots", {})
    existing = roots.get("emergency_exception")
    if isinstance(existing, Mapping) and existing.get("t") == "ref":
        item = state["heap"].get(str(existing.get("id")))
        if isinstance(item, MutableMapping):
            item["type_name"] = type_name
            item["payload"] = {
                "exception_type": type_name,
                "message": str(message),
                "args": [_v_str(str(message))],
                "cause": None,
                "context": None,
                "traceback": [],
            }
            _mutated(item)
            return _plain(existing)
    object_id = _next_id(state, "object")
    state["heap"][object_id] = {
        "schema": "cassifi.py-object-state.v1",
        "id": object_id,
        "generation": 1,
        "kind": "exception",
        "type_name": type_name,
        "version": 0,
        "payload": {
            "exception_type": type_name,
            "message": str(message),
            "args": [_v_str(str(message))],
            "cause": None,
            "context": None,
            "traceback": [],
        },
        "scope": "runtime-reserve",
        "gc": {
            "finalizer": False,
            "finalized": False,
            "resurrected": False,
            "weakrefs": [],
        },
    }
    roots["emergency_exception"] = _v_ref(object_id)
    state["ledger"]["allocations"] += 1
    return _v_ref(object_id)


def _mutated(item: MutableMapping[str, Any]) -> None:
    item["version"] = int(item["version"]) + 1


def _env(state: MutableMapping[str, Any], parent: Mapping[str, Any] | None, kind: str) -> dict[str, Any]:
    return _alloc(
        state,
        "env",
        {"values": {}, "parent": None if parent is None else _plain(parent), "kind": kind},
        type_name="namespace",
    )


def _env_values(state: Mapping[str, Any], env_ref: Mapping[str, Any]) -> MutableMapping[str, Any]:
    item = _heap_object(state, env_ref)
    if item["kind"] != "env" or not isinstance(item["payload"].get("values"), MutableMapping):
        raise RuntimeError("environment object is invalid")
    return item["payload"]["values"]


def _env_parent(state: Mapping[str, Any], env_ref: Mapping[str, Any]) -> Mapping[str, Any] | None:
    item = _heap_object(state, env_ref)
    parent = item["payload"].get("parent")
    return _check_value(parent) if parent is not None else None


def _env_get(state: Mapping[str, Any], env_ref: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    current: Mapping[str, Any] | None = env_ref
    seen: set[str] = set()
    while current is not None:
        object_id = _ref_id(current)
        if object_id in seen:
            raise RuntimeError("environment parent cycle")
        seen.add(object_id)
        values = _env_values(state, current)
        if name in values:
            return _check_value(values[name])
        current = _env_parent(state, current)
    return None


def _env_find(state: Mapping[str, Any], env_ref: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    current = _env_parent(state, env_ref)
    while current is not None:
        if name in _env_values(state, current):
            return current
        current = _env_parent(state, current)
    return None


def _env_set(state: MutableMapping[str, Any], env_ref: Mapping[str, Any], name: str, value: Mapping[str, Any]) -> None:
    values = _env_values(state, env_ref)
    values[name] = _plain(_check_value(value))
    _mutated(_heap_object(state, env_ref))


def _env_delete(state: MutableMapping[str, Any], env_ref: Mapping[str, Any], name: str, *, missing_ok: bool = False) -> None:
    values = _env_values(state, env_ref)
    if name not in values:
        if missing_ok:
            return
        raise _GuestSignal(_exception(state, "NameError", f"name '{name}' is not defined"))
    del values[name]
    _mutated(_heap_object(state, env_ref))
def _bind_type_params(
    state: MutableMapping[str, Any],
    frame: MutableMapping[str, Any],
    descriptors: Sequence[Mapping[str, Any]],
) -> None:
    values = _env_values(state, _check_value(frame["locals"]))
    saved = frame.setdefault("type_param_bindings", [])
    refs = frame.setdefault("type_param_refs", {})
    for descriptor in descriptors:
        name = str(descriptor.get("name", ""))
        if not name:
            raise TypeError("type parameter requires a name")
        saved.append(
            {
                "name": name,
                "present": name in values,
                "value": None if name not in values else _plain(values[name]),
                "ref_present": name in refs,
                "ref": None if name not in refs else _plain(refs[name]),
            }
        )
        ref = _alloc(
            state,
            "type-param",
            {
                "name": name,
                "descriptor": copy.deepcopy(dict(descriptor)),
            },
            type_name="type parameter",
        )
        refs[name] = _plain(ref)
        _env_set(state, _check_value(frame["locals"]), name, ref)


def _unbind_type_params(
    state: MutableMapping[str, Any],
    frame: MutableMapping[str, Any],
    count: int,
) -> None:
    values = _env_values(state, _check_value(frame["locals"]))
    saved = frame.setdefault("type_param_bindings", [])
    refs = frame.setdefault("type_param_refs", {})
    if count < 0 or count > len(saved):
        raise RuntimeError("type parameter binding stack is invalid")
    for entry in reversed(saved[-count:] if count else []):
        name = str(entry["name"])
        if entry["present"]:
            _env_set(state, _check_value(frame["locals"]), name, _check_value(entry["value"]))
        else:
            values.pop(name, None)
            _mutated(_heap_object(state, _check_value(frame["locals"])))
        if entry.get("ref_present"):
            refs[name] = _plain(entry["ref"])
        else:
            refs.pop(name, None)
    if count:
        del saved[-count:]



def _exception(
    state: MutableMapping[str, Any],
    type_name: str,
    message: str,
    *,
    cause: Mapping[str, Any] | None = None,
    value: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    if value is not None and value.get("t") == "ref":
        item = _heap_object(state, value)
        if item["kind"] == "exception":
            return value
    return _alloc(
        state,
        "exception",
        {
            "exception_type": type_name,
            "message": str(message),
            "args": [_v_str(str(message))],
            "cause": None if cause is None else _plain(cause),
            "context": None,
            "traceback": [],
        },
        type_name=type_name,
    )


def _quota_exhausted(
    state: MutableMapping[str, Any],
    limit: str,
    required: int,
    message: str,
    *,
    guest_type: str = "MemoryError",
) -> None:
    if state.get("_instruction_active") is True:
        raise _ResourceLimitPause(limit, required, message)
    raise _GuestSignal(_exception(state, guest_type, message))


def _check_source_limit(state: MutableMapping[str, Any], source: str) -> None:
    source_bytes = len(source.encode("utf-8"))
    if source_bytes > _limit(state, "max_source_bytes"):
        _quota_exhausted(
            state,
            "max_source_bytes",
            source_bytes,
            "source exceeds the compiler byte bound",
        )
def _exception_leaves(state: Mapping[str, Any], exception: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    item = _heap_object(state, exception)
    children = item["payload"].get("exceptions") if item["kind"] == "exception" else None
    if not isinstance(children, list):
        return [exception]
    leaves: list[Mapping[str, Any]] = []
    for child in children:
        leaves.extend(_exception_leaves(state, _check_value(child)))
    return leaves


def _exception_group(
    state: MutableMapping[str, Any],
    exceptions: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    values = [_plain(value) for value in exceptions]
    if not values:
        return None
    if len(values) == 1:
        return _check_value(values[0])
    group = _exception(state, "ExceptionGroup", "field exception group")
    item = _heap_object(state, group)
    item["payload"]["exceptions"] = values
    _mutated(item)
    return group


def _split_exception_group(
    state: MutableMapping[str, Any],
    exception: Mapping[str, Any],
    target: Mapping[str, Any],
) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    target_name = str(target.get("v", ""))
    if target.get("t") == "exception-type" and target_name in {"ExceptionGroup", "BaseExceptionGroup"}:
        raise TypeError("cannot catch ExceptionGroup with except*")
    if target.get("t") == "ref" and _heap_object(state, target)["kind"] == "class":
        target_name = str(_heap_object(state, target)["payload"]["name"])
        if target_name in {"ExceptionGroup", "BaseExceptionGroup"}:
            raise TypeError("cannot catch ExceptionGroup with except*")
    matched: list[Mapping[str, Any]] = []
    remainder: list[Mapping[str, Any]] = []
    for leaf in _exception_leaves(state, exception):
        (matched if _exception_matches(state, leaf, target) else remainder).append(leaf)
    return _exception_group(state, matched), _exception_group(state, remainder)




def _raise_host(state: MutableMapping[str, Any], exc: BaseException) -> _GuestSignal:
    table = {
        ZeroDivisionError: "ZeroDivisionError",
        IndexError: "IndexError",
        KeyError: "KeyError",
        AttributeError: "AttributeError",
        NameError: "NameError",
        UnboundLocalError: "UnboundLocalError",
        TypeError: "TypeError",
        RuntimeError: "RuntimeError",
        ValueError: "ValueError",
        OverflowError: "OverflowError",
        ImportError: "ImportError",
        StopIteration: "StopIteration",
    }
    name = next((guest for host, guest in table.items() if isinstance(exc, host)), type(exc).__name__)
    return _GuestSignal(_exception(state, name, str(exc)))


def _constant_value(state: MutableMapping[str, Any], record: Mapping[str, Any]) -> Mapping[str, Any]:
    kind = record.get("kind")
    if kind == "none":
        return _v_none()
    if kind == "ellipsis":
        return {"t": "ellipsis"}
    if kind == "bool":
        return _v_bool(bool(record["value"]))
    if kind == "int":
        return _v_int(int(record["value"]))
    if kind == "float":
        return _v_float(float.fromhex(str(record["value"])))
    if kind == "complex":
        return _v_complex(complex(float.fromhex(str(record["real"])), float.fromhex(str(record["imag"]))))
    if kind == "str":
        return _v_str(str(record["value"]))
    if kind == "bytes":
        return _v_bytes(base64.b64decode(str(record["value"]).encode("ascii"), validate=True))
    if kind in {"tuple", "frozenset"}:
        values = [_constant_value(state, item) for item in record.get("items", [])]
        return _alloc(state, kind, {"items": values}, type_name=kind)
    raise RuntimeError("constant record is invalid")


def _from_host(state: MutableMapping[str, Any], value: Any, memo: dict[int, Mapping[str, Any]] | None = None) -> Mapping[str, Any]:
    if _is_value(value):
        return _plain(value)
    if value is None:
        return _v_none()
    if isinstance(value, bool):
        return _v_bool(value)
    if isinstance(value, int):
        if value.bit_length() > _limit(state, "max_integer_bits"):
            _quota_exhausted(
                state,
                "max_integer_bits",
                value.bit_length(),
                "integer exceeds field limit",
                guest_type="OverflowError",
            )
        return _v_int(value)
    if isinstance(value, float):
        return _v_float(value)
    if isinstance(value, complex):
        return _v_complex(value)
    if isinstance(value, str):
        encoded_bytes = len(value.encode("utf-8", "surrogatepass"))
        if encoded_bytes > _limit(state, "max_string_bytes"):
            _quota_exhausted(
                state,
                "max_string_bytes",
                encoded_bytes,
                "string exceeds field limit",
            )
        return _v_str(value)
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        if len(raw) > _limit(state, "max_string_bytes"):
            _quota_exhausted(
                state,
                "max_string_bytes",
                len(raw),
                "byte string exceeds field limit",
            )
        if isinstance(value, bytes):
            return _v_bytes(raw)
        return _alloc(state, "bytearray", {"bytes": base64.b64encode(raw).decode("ascii")})
    if memo is None:
        memo = {}
    identity = id(value)
    if identity in memo:
        return memo[identity]
    if isinstance(value, (list, tuple, set, frozenset)):
        if len(value) > _limit(state, "max_collection_items"):
            _quota_exhausted(
                state,
                "max_collection_items",
                len(value),
                "collection exceeds field limit",
            )
        kind = "list" if isinstance(value, list) else "tuple" if isinstance(value, tuple) else "set" if isinstance(value, set) else "frozenset"
        ref = _alloc(state, kind, {"items": []})
        memo[identity] = ref
        item = _heap_object(state, ref)
        item["payload"]["items"] = [_from_host(state, member, memo) for member in value]
        return ref
    if isinstance(value, Mapping):
        if len(value) > _limit(state, "max_collection_items"):
            _quota_exhausted(
                state,
                "max_collection_items",
                len(value),
                "mapping exceeds field limit",
            )
        ref = _alloc(state, "dict", {"entries": []})
        memo[identity] = ref
        item = _heap_object(state, ref)
        item["payload"]["entries"] = [
            [_from_host(state, key, memo), _from_host(state, member, memo)]
            for key, member in value.items()
        ]
        return ref
    raise _GuestSignal(_exception(state, "TypeError", f"cannot admit host value of type {type(value).__name__}"))


def _to_host(state: Mapping[str, Any], value: Mapping[str, Any], memo: dict[str, Any] | None = None) -> Any:
    kind = value.get("t")
    if kind == "none":
        return None
    if kind == "bool":
        return bool(value["v"])
    if kind == "int":
        return int(value["v"])
    if kind == "float":
        return float.fromhex(str(value["v"]))
    if kind == "complex":
        return complex(float.fromhex(str(value["r"])), float.fromhex(str(value["i"])))
    if kind == "str":
        return str(value["v"])
    if kind == "bytes":
        return _as_bytes(value)
    if kind == "ellipsis":
        return Ellipsis
    if kind != "ref":
        raise TypeError(f"{kind} is not a data value")
    if memo is None:
        memo = {}
    object_id = _ref_id(value)
    if object_id in memo:
        return memo[object_id]
    item = _heap_object(state, value)
    object_kind = item["kind"]
    payload = item["payload"]
    if object_kind in {"list", "tuple", "set", "frozenset"}:
        placeholder: list[Any] = []
        memo[object_id] = placeholder
        placeholder.extend(_to_host(state, member, memo) for member in payload["items"])
        if object_kind == "list":
            return placeholder
        if object_kind == "tuple":
            result = tuple(placeholder)
        elif object_kind == "set":
            result = set(placeholder)
        else:
            result = frozenset(placeholder)
        memo[object_id] = result
        return result
    if object_kind == "dict":
        result: dict[Any, Any] = {}
        memo[object_id] = result
        for key, member in payload["entries"]:
            result[_to_host(state, key, memo)] = _to_host(state, member, memo)
        return result
    if object_kind == "range":
        return range(int(payload["start"]), int(payload["stop"]), int(payload["step"]))
    if object_kind == "slice":
        return slice(*(_to_host(state, part, memo) for part in payload["parts"]))
    if object_kind == "bytearray":
        result = bytearray(base64.b64decode(payload["bytes"]))
        memo[object_id] = result
        return result
    raise TypeError(f"{object_kind} cannot cross the field data boundary")


def _project(state: Mapping[str, Any], value: Mapping[str, Any], seen: set[str] | None = None) -> Any:
    kind = value.get("t")
    if kind == "float":
        raw = _as_float(value)
        if math.isfinite(raw):
            return raw
        return {"float": value["v"]}
    if kind == "complex":
        return {"complex": [value["r"], value["i"]]}
    if kind == "bytes":
        return {"bytes_b64": value["v"]}
    if kind in {"none", "bool", "int", "str"}:
        return _to_host(state, value)
    if kind != "ref":
        return _plain(value)
    object_id = _ref_id(value)
    if seen is None:
        seen = set()
    if object_id in seen:
        return {"$ref": object_id}
    seen.add(object_id)
    item = _heap_object(state, value)
    payload = item["payload"]
    if item["kind"] in {"list", "tuple", "set", "frozenset"}:
        return {
            "$id": object_id,
            "type": item["kind"],
            "items": [_project(state, member, seen) for member in payload["items"]],
        }
    if item["kind"] == "dict":
        return {
            "$id": object_id,
            "type": "dict",
            "entries": [[_project(state, key, seen), _project(state, member, seen)] for key, member in payload["entries"]],
        }
    if item["kind"] == "exception":
        return {
            "$id": object_id,
            "type": payload["exception_type"],
            "message": payload["message"],
            "traceback": list(payload["traceback"]),
        }
    return {
        "$id": object_id,
        "type": item["type_name"],
        "kind": item["kind"],
        "version": item["version"],
    }


def _repr_value(state: Mapping[str, Any], value: Mapping[str, Any], seen: set[str] | None = None) -> str:
    kind = value.get("t")
    if kind == "none": return "None"
    if kind == "bool": return "True" if value["v"] else "False"
    if kind == "int": return str(value["v"])
    if kind == "float": return repr(_as_float(value))
    if kind == "complex": return repr(_as_complex(value))
    if kind == "str": return repr(value["v"])
    if kind == "bytes": return repr(_as_bytes(value))
    if kind == "ellipsis": return "Ellipsis"
    if kind == "builtin": return f"<built-in function {value['v']}>"
    if kind == "type": return f"<class '{value['v']}'>"
    if kind == "exception-type": return f"<class '{value['v']}'>"
    if kind == "method": return f"<built-in method {value['name']}>"
    if kind != "ref": return f"<{kind}>"
    object_id = _ref_id(value)
    if seen is None: seen = set()
    if object_id in seen: return "..."
    seen.add(object_id)
    item = _heap_object(state, value)
    payload = item["payload"]
    if item["kind"] in {"list", "tuple", "set", "frozenset"}:
        parts = [_repr_value(state, member, seen.copy()) for member in payload["items"]]
        if item["kind"] == "list": return "[" + ", ".join(parts) + "]"
        if item["kind"] == "tuple": return "(" + ", ".join(parts) + ("," if len(parts) == 1 else "") + ")"
        if item["kind"] == "set": return "{" + ", ".join(parts) + "}" if parts else "set()"
        return "frozenset({" + ", ".join(parts) + "})"
    if item["kind"] == "dict":
        return "{" + ", ".join(f"{_repr_value(state, key, seen.copy())}: {_repr_value(state, member, seen.copy())}" for key, member in payload["entries"]) + "}"
    if item["kind"] == "function": return f"<function {payload['qualname']}>"
    if item["kind"] == "class": return f"<class '{payload['qualname']}'>"
    if item["kind"] == "instance": return f"<{item['type_name']} object {object_id}>"
    if item["kind"] == "exception": return f"{payload['exception_type']}({payload['message']!r})"
    if item["kind"] in {"generator", "coroutine"}: return f"<{item['kind']} {object_id} {payload['status']}>"
    return f"<{item['type_name']} {object_id}>"


def _str_value(state: Mapping[str, Any], value: Mapping[str, Any]) -> str:
    if value.get("t") == "str":
        return _as_str(value)
    if value.get("t") == "ref":
        item = _heap_object(state, value)
        if item["kind"] == "exception":
            return str(item["payload"]["message"])
    return _repr_value(state, value)


def _truth(state: Mapping[str, Any], value: Mapping[str, Any]) -> bool:
    kind = value.get("t")
    if kind == "none": return False
    if kind == "bool": return bool(value["v"])
    if kind == "int": return int(value["v"]) != 0
    if kind == "float": return _as_float(value) != 0.0
    if kind == "complex": return _as_complex(value) != 0j
    if kind == "str": return bool(value["v"])
    if kind == "bytes": return bool(_as_bytes(value))
    if kind == "ref":
        item = _heap_object(state, value)
        if item["kind"] in {"list", "tuple", "set", "frozenset"}: return bool(item["payload"]["items"])
        if item["kind"] == "dict": return bool(item["payload"]["entries"])
        if item["kind"] == "range": return len(range(int(item["payload"]["start"]), int(item["payload"]["stop"]), int(item["payload"]["step"]))) != 0
        if item["kind"] == "bytearray": return bool(base64.b64decode(item["payload"]["bytes"]))
        return True
    return True


def _value_equal(state: Mapping[str, Any], left: Mapping[str, Any], right: Mapping[str, Any], seen: set[tuple[str, str]] | None = None) -> bool:
    if left.get("t") != right.get("t"):
        numeric = {left.get("t"), right.get("t")} <= {"bool", "int", "float", "complex"}
        if numeric:
            return _as_complex(left) == _as_complex(right)
        return False
    kind = left.get("t")
    if kind == "ref":
        left_id, right_id = _ref_id(left), _ref_id(right)
        if left_id == right_id: return True
        if seen is None: seen = set()
        if (left_id, right_id) in seen: return True
        seen.add((left_id, right_id))
        a, b = _heap_object(state, left), _heap_object(state, right)
        if a["kind"] != b["kind"]: return False
        if a["kind"] in {"list", "tuple"}:
            return len(a["payload"]["items"]) == len(b["payload"]["items"]) and all(_value_equal(state, x, y, seen) for x, y in zip(a["payload"]["items"], b["payload"]["items"]))
        if a["kind"] == "dict":
            if len(a["payload"]["entries"]) != len(b["payload"]["entries"]): return False
            return all(any(_value_equal(state, ka, kb, seen) and _value_equal(state, va, vb, seen) for kb, vb in b["payload"]["entries"]) for ka, va in a["payload"]["entries"])
        return False
    return dict(left) == dict(right)


def _stable_hash(state: Mapping[str, Any], value: Mapping[str, Any]) -> int:
    """Return the pinned process-independent Python hash for a field value."""

    kind = str(value.get("t"))
    if kind == "none":
        payload: Any = ["none"]
    elif kind == "not-implemented":
        payload = ["not-implemented"]
    elif kind in {"bool", "int"}:
        payload = ["number", str(_as_int(value))]
    elif kind == "float":
        numeric = _as_float(value)
        payload = (
            ["number", str(int(numeric))]
            if math.isfinite(numeric) and numeric.is_integer()
            else ["float", numeric.hex()]
        )
    elif kind == "complex":
        numeric = _as_complex(value)
        if numeric.imag == 0.0:
            return _stable_hash(state, _v_float(numeric.real))
        payload = ["complex", numeric.real.hex(), numeric.imag.hex()]
    elif kind == "str":
        payload = ["str", _as_str(value)]
    elif kind == "bytes":
        payload = ["bytes", base64.b64encode(_as_bytes(value)).decode("ascii")]
    elif kind == "ref":
        item = _heap_object(state, value)
        if item["kind"] == "tuple":
            payload = [
                "tuple",
                *[_stable_hash(state, _check_value(member)) for member in item["payload"]["items"]],
            ]
        elif item["kind"] == "frozenset":
            payload = [
                "frozenset",
                *sorted(
                    _stable_hash(state, _check_value(member))
                    for member in item["payload"]["items"]
                ),
            ]
        elif item["kind"] in {
            "list",
            "dict",
            "set",
            "bytearray",
            "memoryview",
        }:
            raise TypeError(f"unhashable type: '{item['type_name']}'")
        else:
            payload = ["identity", _ref_id(value), int(value["generation"])]
    else:
        payload = [kind, _plain(value)]
    digest = hashlib.sha256(canonical_json_bytes(payload)).digest()
    result = int.from_bytes(digest[:8], "little", signed=True)
    return -2 if result == -1 else result


def _super_attr(
    state: MutableMapping[str, Any],
    super_ref: Mapping[str, Any],
    name: str,
) -> tuple[str, Any]:
    payload = _heap_object(state, super_ref)["payload"]
    start_class = _check_value(payload["start_class"])
    receiver = _check_value(payload["receiver"])
    receiver_class = _instance_class(state, receiver)
    if receiver_class is None:
        raise TypeError("super receiver must be an instance or class")
    mro = _class_mro(state, receiver_class)
    start_index = next(
        (
            index
            for index, candidate in enumerate(mro)
            if dict(candidate) == dict(start_class)
        ),
        None,
    )
    if start_index is None:
        raise TypeError("super(type, obj): obj is not an instance or subtype of type")
    for candidate in mro[start_index + 1 :]:
        namespace = _check_value(_heap_object(state, candidate)["payload"]["namespace"])
        found = _env_get(state, namespace, name)
        if found is None:
            continue
        if found.get("t") == "ref":
            found_item = _heap_object(state, found)
            if found_item["kind"] == "function":
                return "value", {
                    "t": "bound",
                    "func": _plain(found),
                    "self": _plain(receiver),
                }
            if found_item["kind"] == "staticmethod":
                return "value", _check_value(found_item["payload"]["function"])
            if found_item["kind"] == "classmethod":
                return "value", {
                    "t": "bound",
                    "func": _plain(_check_value(found_item["payload"]["function"])),
                    "self": _plain(receiver_class),
                }
            descriptor_class = _instance_class(state, found)
            if descriptor_class is not None:
                getter = _lookup_class_attr(state, descriptor_class, "__get__")
                if getter is not None:
                    return "call", (
                        {
                            "t": "bound",
                            "func": _plain(getter),
                            "self": _plain(found),
                        },
                        [receiver, receiver_class],
                        {},
                    )
        return "value", found
    raise AttributeError(f"super object has no attribute {name!r}")


def _contains(state: Mapping[str, Any], container: Mapping[str, Any], needle: Mapping[str, Any]) -> bool:
    kind = container.get("t")
    if kind == "str": return _as_str(needle) in _as_str(container)
    if kind == "bytes": return _to_host(state, needle) in _as_bytes(container)
    if kind == "ref":
        item = _heap_object(state, container)
        if item["kind"] in {"list", "tuple", "set", "frozenset"}:
            return any(_value_equal(state, needle, member) for member in item["payload"]["items"])
        if item["kind"] == "dict":
            return any(_value_equal(state, needle, key) for key, _ in item["payload"]["entries"])
        if item["kind"] == "range": return _as_int(needle) in _to_host(state, container)
    raise TypeError("object is not a container")


def _binary(state: MutableMapping[str, Any], op: str, left: Mapping[str, Any], right: Mapping[str, Any], *, inplace: bool = False) -> Mapping[str, Any]:
    try:
        if inplace and left.get("t") == "ref":
            item = _heap_object(state, left)
            if op == "add" and item["kind"] == "list":
                other = _heap_object(state, right)
                if other["kind"] not in {"list", "tuple"}: raise TypeError("can only extend list with iterable")
                item["payload"]["items"].extend(copy.deepcopy(other["payload"]["items"]))
                _mutated(item)
                return left
            if op == "or" and item["kind"] == "dict":
                other = _heap_object(state, right)
                if other["kind"] != "dict": raise TypeError("dict update requires mapping")
                for key, member in other["payload"]["entries"]:
                    _dict_set(state, left, key, member)
                return left
        if left.get("t") == "str" and right.get("t") == "str" and op in {"add", "mod"}:
            if op == "add": return _from_host(state, _as_str(left) + _as_str(right))
            return _from_host(state, _as_str(left) % _to_host(state, right))
        if left.get("t") == "bytes" and right.get("t") == "bytes" and op == "add":
            return _v_bytes(_as_bytes(left) + _as_bytes(right))
        if op == "mul" and left.get("t") in {"str", "bytes"} and right.get("t") in {"int", "bool"}:
            return _from_host(state, _to_host(state, left) * _as_int(right))
        if op == "mul" and right.get("t") in {"str", "bytes"} and left.get("t") in {"int", "bool"}:
            return _from_host(state, _as_int(left) * _to_host(state, right))
        if left.get("t") == "ref":
            a = _heap_object(state, left)
            if op == "add" and a["kind"] in {"list", "tuple"}:
                b = _heap_object(state, right)
                if b["kind"] != a["kind"]: raise TypeError("sequence types differ")
                return _alloc(state, a["kind"], {"items": copy.deepcopy(a["payload"]["items"] + b["payload"]["items"])})
            if op == "mul" and a["kind"] in {"list", "tuple"}:
                count = _as_int(right)
                return _alloc(state, a["kind"], {"items": copy.deepcopy(a["payload"]["items"] * max(0, count))})
        types = {left.get("t"), right.get("t")}
        if "complex" in types:
            a, b = _as_complex(left), _as_complex(right)
        elif "float" in types or op == "truediv":
            a, b = _as_float(left), _as_float(right)
        else:
            a, b = _as_int(left), _as_int(right)
        operations = {
            "add": operator.add, "sub": operator.sub, "mul": operator.mul,
            "matmul": operator.matmul, "truediv": operator.truediv,
            "floordiv": operator.floordiv, "mod": operator.mod,
            "pow": operator.pow, "lshift": operator.lshift,
            "rshift": operator.rshift, "or": operator.or_,
            "xor": operator.xor, "and": operator.and_,
        }
        result = operations[op](a, b)
        return _from_host(state, result)
    except _ResourceLimitPause:
        raise
    except _GuestSignal:
        raise
    except BaseException as exc:
        raise _raise_host(state, exc) from exc



_BINARY_METHODS = {
    "add": ("__add__", "__radd__"),
    "sub": ("__sub__", "__rsub__"),
    "mul": ("__mul__", "__rmul__"),
    "matmul": ("__matmul__", "__rmatmul__"),
    "truediv": ("__truediv__", "__rtruediv__"),
    "floordiv": ("__floordiv__", "__rfloordiv__"),
    "mod": ("__mod__", "__rmod__"),
    "pow": ("__pow__", "__rpow__"),
    "lshift": ("__lshift__", "__rlshift__"),
    "rshift": ("__rshift__", "__rrshift__"),
    "or": ("__or__", "__ror__"),
    "xor": ("__xor__", "__rxor__"),
    "and": ("__and__", "__rand__"),
}
_INPLACE_METHODS = {
    name: f"__i{name}__"
    for name in _BINARY_METHODS
}
_COMPARE_METHODS = {
    "eq": ("__eq__", "__eq__"),
    "ne": ("__ne__", "__ne__"),
    "lt": ("__lt__", "__gt__"),
    "le": ("__le__", "__ge__"),
    "gt": ("__gt__", "__lt__"),
    "ge": ("__ge__", "__le__"),
}
_UNARY_METHODS = {
    "pos": "__pos__",
    "neg": "__neg__",
    "invert": "__invert__",
}


def _bound_special(
    state: Mapping[str, Any],
    target: Mapping[str, Any],
    name: str,
) -> Mapping[str, Any] | None:
    class_ref = _instance_class(state, target)
    if class_ref is None:
        return None
    function = _lookup_class_attr(state, class_ref, name)
    if function is None:
        return None
    return {
        "t": "bound",
        "func": _plain(function),
        "self": _plain(target),
    }


def _operator_candidates(
    state: Mapping[str, Any],
    op: str,
    left: Mapping[str, Any],
    right: Mapping[str, Any] | None = None,
    *,
    inplace: bool = False,
    comparison: bool = False,
) -> list[Mapping[str, Any]]:
    candidates: list[Mapping[str, Any]] = []
    if right is None:
        method_name = _UNARY_METHODS.get(op)
        method = None if method_name is None else _bound_special(state, left, method_name)
        if method is not None:
            candidates.append({"callable": method, "arguments": []})
        return candidates
    names = _COMPARE_METHODS.get(op) if comparison else _BINARY_METHODS.get(op)
    if names is None:
        return candidates
    if inplace and not comparison:
        inplace_method = _bound_special(state, left, _INPLACE_METHODS[op])
        if inplace_method is not None:
            candidates.append(
                {"callable": inplace_method, "arguments": [_plain(right)]}
            )
    left_method = _bound_special(state, left, names[0])
    if left_method is not None:
        candidates.append({"callable": left_method, "arguments": [_plain(right)]})
    right_method = _bound_special(state, right, names[1])
    if right_method is not None:
        candidates.append({"callable": right_method, "arguments": [_plain(left)]})
    return candidates


def _operator_fallback(
    state: MutableMapping[str, Any],
    fallback: Mapping[str, Any],
) -> Mapping[str, Any]:
    kind = str(fallback["kind"])
    op = str(fallback["operation"])
    left = _check_value(fallback["left"])
    if kind == "unary":
        return _unary(state, op, left)
    right = _check_value(fallback["right"])
    if kind == "compare":
        return _compare(state, op, left, right)
    return _binary(
        state,
        op,
        left,
        right,
        inplace=bool(fallback.get("inplace", False)),
    )


def _invoke_operator(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    fallback: Mapping[str, Any],
) -> tuple[bool, Mapping[str, Any] | None]:
    remaining = list(candidates)
    while remaining:
        candidate = remaining.pop(0)
        immediate, result = _invoke(
            state,
            task,
            _check_value(candidate["callable"]),
            [_check_value(value) for value in candidate["arguments"]],
            {},
            return_context={
                "kind": "operator",
                "remaining": _plain(remaining),
                "fallback": _plain(fallback),
            },
        )
        if not immediate:
            return False, None
        if result is not None and result.get("t") != "not-implemented":
            return True, result
    return True, _operator_fallback(state, fallback)

def _unary(state: MutableMapping[str, Any], op: str, value: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        if op == "not": return _v_bool(not _truth(state, value))
        if op == "invert": return _v_int(~_as_int(value))
        if op == "pos": return _from_host(state, +_to_host(state, value))
        if op == "neg": return _from_host(state, -_to_host(state, value))
        raise RuntimeError("unary operation is invalid")
    except _ResourceLimitPause:
        raise
    except _GuestSignal:
        raise
    except BaseException as exc:
        raise _raise_host(state, exc) from exc


def _compare(state: MutableMapping[str, Any], op: str, left: Mapping[str, Any], right: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        if op == "is": return _v_bool(dict(left) == dict(right))
        if op == "is-not": return _v_bool(dict(left) != dict(right))
        if op == "in": return _v_bool(_contains(state, right, left))
        if op == "not-in": return _v_bool(not _contains(state, right, left))
        if op == "eq": return _v_bool(_value_equal(state, left, right))
        if op == "ne": return _v_bool(not _value_equal(state, left, right))
        a, b = _to_host(state, left), _to_host(state, right)
        return _v_bool({"lt": operator.lt, "le": operator.le, "gt": operator.gt, "ge": operator.ge}[op](a, b))
    except _ResourceLimitPause:
        raise
    except _GuestSignal:
        raise
    except BaseException as exc:
        raise _raise_host(state, exc) from exc


def _dict_find(state: Mapping[str, Any], item: Mapping[str, Any], key: Mapping[str, Any]) -> int | None:
    for index, (candidate, _) in enumerate(item["payload"]["entries"]):
        if _value_equal(state, candidate, key): return index
    return None


def _dict_set(state: MutableMapping[str, Any], ref: Mapping[str, Any], key: Mapping[str, Any], value: Mapping[str, Any]) -> None:
    item = _heap_object(state, ref)
    if item["kind"] != "dict": raise TypeError("object is not a mapping")
    index = _dict_find(state, item, key)
    if index is None:
        if len(item["payload"]["entries"]) >= _limit(state, "max_collection_items"):
            _quota_exhausted(
                state,
                "max_collection_items",
                len(item["payload"]["entries"]) + 1,
                "mapping exceeds field limit",
            )
        item["payload"]["entries"].append([_plain(key), _plain(value)])
    else:
        item["payload"]["entries"][index][1] = _plain(value)
    _mutated(item)


def _index_value(state: Mapping[str, Any], value: Mapping[str, Any]) -> int | slice:
    if value.get("t") in {"int", "bool"}: return _as_int(value)
    if value.get("t") == "ref" and _heap_object(state, value)["kind"] == "slice": return _to_host(state, value)
    raise TypeError("indices must be integers or slices")


def _get_item(state: MutableMapping[str, Any], container: Mapping[str, Any], key: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        kind = container.get("t")
        if kind == "str": return _v_str(_as_str(container)[_index_value(state, key)])
        if kind == "bytes": return _from_host(state, _as_bytes(container)[_index_value(state, key)])
        item = _heap_object(state, container)
        if item["kind"] in {"list", "tuple"}:
            index = _index_value(state, key)
            if isinstance(index, slice):
                return _alloc(state, item["kind"], {"items": copy.deepcopy(item["payload"]["items"][index])})
            return _check_value(item["payload"]["items"][index])
        if item["kind"] == "dict":
            index = _dict_find(state, item, key)
            if index is None: raise KeyError(_repr_value(state, key))
            return _check_value(item["payload"]["entries"][index][1])
        if item["kind"] == "range": return _from_host(state, _to_host(state, container)[_index_value(state, key)])
        if item["kind"] == "bytearray": return _from_host(state, _to_host(state, container)[_index_value(state, key)])
        if item["kind"] == "memoryview":
            target = _check_value(item["payload"]["target"])
            base = _heap_object(state, target)
            data = bytearray(base64.b64decode(base["payload"]["bytes"]))
            start, stop = int(item["payload"]["start"]), int(item["payload"]["stop"])
            return _from_host(state, data[start:stop][_index_value(state, key)])
        raise TypeError("object is not subscriptable")
    except _ResourceLimitPause:
        raise
    except _GuestSignal:
        raise
    except BaseException as exc:
        raise _raise_host(state, exc) from exc


def _store_item(state: MutableMapping[str, Any], container: Mapping[str, Any], key: Mapping[str, Any], value: Mapping[str, Any]) -> None:
    try:
        item = _heap_object(state, container)
        if item["kind"] == "dict":
            _dict_set(state, container, key, value); return
        if item["kind"] == "list":
            index = _index_value(state, key)
            if isinstance(index, slice):
                replacement = _iter_values(state, value)
                item["payload"]["items"][index] = copy.deepcopy(replacement)
            else:
                item["payload"]["items"][index] = _plain(value)
            _mutated(item); return
        if item["kind"] == "bytearray":
            data = bytearray(base64.b64decode(item["payload"]["bytes"]))
            index = _index_value(state, key)
            if isinstance(index, slice): data[index] = bytes(_to_host(state, value))
            else: data[index] = _as_int(value)
            item["payload"]["bytes"] = base64.b64encode(bytes(data)).decode("ascii")
            _mutated(item); return
        if item["kind"] == "memoryview":
            target = _check_value(item["payload"]["target"])
            base = _heap_object(state, target)
            data = bytearray(base64.b64decode(base["payload"]["bytes"]))
            offset = int(item["payload"]["start"])
            index = _index_value(state, key)
            if isinstance(index, slice):
                start, stop, step = index.indices(int(item["payload"]["stop"]) - offset)
                if step != 1: raise ValueError("extended memoryview assignment is unsupported")
                data[offset + start:offset + stop] = bytes(_to_host(state, value))
            else: data[offset + index] = _as_int(value)
            base["payload"]["bytes"] = base64.b64encode(bytes(data)).decode("ascii")
            _mutated(base); return
        raise TypeError("object does not support item assignment")
    except _ResourceLimitPause:
        raise
    except _GuestSignal:
        raise
    except BaseException as exc:
        raise _raise_host(state, exc) from exc


def _delete_item(state: MutableMapping[str, Any], container: Mapping[str, Any], key: Mapping[str, Any]) -> None:
    try:
        item = _heap_object(state, container)
        if item["kind"] == "dict":
            index = _dict_find(state, item, key)
            if index is None: raise KeyError(_repr_value(state, key))
            del item["payload"]["entries"][index]
        elif item["kind"] == "list":
            del item["payload"]["items"][_index_value(state, key)]
        else: raise TypeError("object does not support item deletion")
        _mutated(item)
    except _ResourceLimitPause:
        raise
    except _GuestSignal:
        raise
    except BaseException as exc:
        raise _raise_host(state, exc) from exc


def _iter_values(state: Mapping[str, Any], value: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    kind = value.get("t")
    if kind == "str": return [_v_str(char) for char in str(value["v"])]
    if kind == "bytes": return [_v_int(byte) for byte in _as_bytes(value)]
    if kind == "ref":
        item = _heap_object(state, value)
        if item["kind"] in {"list", "tuple", "set", "frozenset"}: return list(item["payload"]["items"])
        if item["kind"] == "dict": return [key for key, _ in item["payload"]["entries"]]
        if item["kind"] == "range": return [_v_int(number) for number in _to_host(state, value)]
    raise TypeError("object is not iterable")


def _make_iterator(
    state: MutableMapping[str, Any],
    value: Mapping[str, Any],
) -> Mapping[str, Any]:
    if value.get("t") == "ref":
        item = _heap_object(state, value)
        if item["kind"] == "iterator":
            return value
        if item["kind"] in {"generator", "coroutine", "map", "filter"}:
            return value
        if item["kind"] in {"list", "tuple", "dict", "set", "frozenset"}:
            size = (
                len(item["payload"]["entries"])
                if item["kind"] == "dict"
                else len(item["payload"]["items"])
            )
            return _alloc(
                state,
                "iterator",
                {
                    "items": [],
                    "index": 0,
                    "source": _plain(value),
                    "source_kind": item["kind"],
                    "expected_size": size,
                },
            )
    values = _iter_values(state, value)
    return _alloc(
        state,
        "iterator",
        {
            "items": copy.deepcopy(values),
            "index": 0,
            "source": _plain(value),
            "source_kind": "snapshot",
            "expected_size": len(values),
        },
    )
def _callable_iterator_done(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
    iterator_ref: Mapping[str, Any],
    consumer: Mapping[str, Any],
) -> None:
    if not task["stack"]:
        raise RuntimeError("callable iterator has no consumer")
    caller = state["frames"][task["stack"][-1]]
    mode = str(consumer["mode"])
    if mode == "for":
        if caller["stack"] and dict(_check_value(caller["stack"][-1])) == dict(iterator_ref):
            caller["stack"].pop()
        caller["pc"] = int(consumer["target"])
    elif mode == "next":
        if consumer.get("default") is not None:
            caller["stack"].append(_plain(consumer["default"]))
        else:
            _propagate(
                state,
                task,
                {"kind": "exception", "value": _exception(state, "StopIteration", "")},
            )
    elif mode == "collect":
        caller["stack"].append(_plain(consumer["accumulator"]))
    else:
        raise RuntimeError("callable iterator consumer is invalid")


def _callable_iterator_result(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
    iterator_ref: Mapping[str, Any],
    consumer: Mapping[str, Any],
    source_value: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    iterator = _heap_object(state, iterator_ref)
    kind = str(iterator["kind"])
    if kind == "filter" and not _truth(state, result):
        _resume_callable_iterator(state, task, iterator_ref, consumer)
        return
    if str(consumer["mode"]) == "collect":
        accumulator = _check_value(consumer["accumulator"])
        collection_kind = str(consumer.get("collection_kind", "list"))
        _append_collected_value(state, accumulator, collection_kind, result)
        next_consumer = {**dict(consumer), "accumulator": _plain(accumulator)}
        _resume_callable_iterator(state, task, iterator_ref, next_consumer)
        return
    caller = state["frames"][task["stack"][-1]]
    caller["stack"].append(_plain(source_value if kind == "filter" else result))


def _resume_callable_iterator(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
    iterator_ref: Mapping[str, Any],
    consumer: Mapping[str, Any],
) -> None:
    iterator = _heap_object(state, iterator_ref)
    if iterator["kind"] not in {"map", "filter"}:
        raise TypeError("object is not a callable iterator")
    sources = iterator["payload"]["iterators"]
    source_values: list[Mapping[str, Any]] = []
    for source in sources:
        value = _iterator_next(state, _check_value(source))
        if value is None:
            _callable_iterator_done(state, task, iterator_ref, consumer)
            return
        source_values.append(value)
    callback = _check_value(iterator["payload"]["callback"])
    positional = source_values if iterator["kind"] == "map" else [source_values[0]]
    immediate, result = _invoke(
        state,
        task,
        callback,
        positional,
        {},
        return_context={
            "kind": "callable-iterator",
            "iterator_ref": _plain(iterator_ref),
            "consumer": _plain(consumer),
            "source_value": _plain(source_values[0]),
        },
    )
    if immediate:
        _callable_iterator_result(
            state,
            task,
            iterator_ref,
            consumer,
            source_values[0],
            _check_value(result),
        )



def _iterator_next(
    state: MutableMapping[str, Any],
    iterator: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    item = _heap_object(state, iterator)
    if item["kind"] != "iterator":
        raise TypeError("object is not a field iterator")
    index = int(item["payload"]["index"])
    source_kind = str(item["payload"].get("source_kind", "snapshot"))
    if source_kind == "snapshot":
        values = item["payload"]["items"]
    else:
        source = _check_value(item["payload"]["source"])
        source_item = _heap_object(state, source)
        if source_item["kind"] != source_kind:
            raise RuntimeError("iterator source changed type")
        if source_kind == "dict":
            current_size = len(source_item["payload"]["entries"])
            values = [key for key, _ in source_item["payload"]["entries"]]
        else:
            current_size = len(source_item["payload"]["items"])
            values = source_item["payload"]["items"]
        if (
            source_kind in {"dict", "set"}
            and current_size != int(item["payload"]["expected_size"])
        ):
            raise RuntimeError(f"{source_kind} changed size during iteration")
    if index >= len(values):
        return None
    item["payload"]["index"] = index + 1
    _mutated(item)
    return _check_value(values[index])


_EXCEPTION_BASES = {
    "BaseException": None,
    "BaseExceptionGroup": "BaseException",
    "ExceptionGroup": "BaseExceptionGroup",
    "Exception": "BaseException",
    "ArithmeticError": "Exception",
    "ZeroDivisionError": "ArithmeticError",
    "OverflowError": "ArithmeticError",
    "LookupError": "Exception",
    "IndexError": "LookupError",
    "KeyError": "LookupError",
    "RuntimeError": "Exception",
    "NotImplementedError": "RuntimeError",
    "TypeError": "Exception",
    "ValueError": "Exception",
    "NameError": "Exception",
    "UnboundLocalError": "NameError",
    "AttributeError": "Exception",
    "ImportError": "Exception",
    "MemoryError": "Exception",
    "RecursionError": "RuntimeError",
    "AssertionError": "Exception",
    "StopIteration": "Exception",
    "StopAsyncIteration": "Exception",
    "CancelledError": "BaseException",
    "PermissionError": "Exception",
}


def _exception_name(state: Mapping[str, Any], exception: Mapping[str, Any]) -> str:
    item = _heap_object(state, exception)
    if item["kind"] != "exception": return item["type_name"]
    return str(item["payload"]["exception_type"])


def _exception_matches(state: Mapping[str, Any], exception: Mapping[str, Any], target: Mapping[str, Any]) -> bool:
    item = _heap_object(state, exception)
    children = item["payload"].get("exceptions") if item["kind"] == "exception" else None
    if isinstance(children, list):
        names = (
            [str(target["v"])]
            if target.get("t") == "exception-type"
            else [
                str(_heap_object(state, target)["payload"]["name"])
            ]
            if target.get("t") == "ref"
            and _heap_object(state, target)["kind"] == "class"
            else []
        )
        if names:
            current: str | None = _exception_name(state, exception)
            while current is not None:
                if current in names: return True
                current = _EXCEPTION_BASES.get(current)
        return False
    names: list[str]
    if target.get("t") == "exception-type": names = [str(target["v"])]
    elif target.get("t") == "ref" and _heap_object(state, target)["kind"] == "tuple":
        return any(_exception_matches(state, exception, item) for item in _heap_object(state, target)["payload"]["items"])
    elif target.get("t") == "ref" and _heap_object(state, target)["kind"] == "class":
        names = [str(_heap_object(state, target)["payload"]["name"])]
    else: raise TypeError("catching classes must derive from BaseException")
    current: str | None = _exception_name(state, exception)
    while current is not None:
        if current in names: return True
        current = _EXCEPTION_BASES.get(current)
    return False


def _type_name(state: Mapping[str, Any], value: Mapping[str, Any]) -> str:
    kind = value.get("t")
    table = {"none": "NoneType", "bool": "bool", "int": "int", "float": "float", "complex": "complex", "str": "str", "bytes": "bytes", "builtin": "builtin_function_or_method", "type": "type", "exception-type": "type", "method": "builtin_function_or_method"}
    if kind == "ref": return str(_heap_object(state, value)["type_name"])
    return table.get(str(kind), str(kind))


def _class_mro(state: Mapping[str, Any], class_ref: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    item = _heap_object(state, class_ref)
    if item["kind"] != "class": raise TypeError("expected class")
    return [class_ref, *[_check_value(value) for value in item["payload"].get("mro_tail", [])]]


def _lookup_class_attr(state: Mapping[str, Any], class_ref: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    for candidate in _class_mro(state, class_ref):
        item = _heap_object(state, candidate)
        namespace = _check_value(item["payload"]["namespace"])
        value = _env_get(state, namespace, name)
        if value is not None: return value
    return None


def _instance_class(state: Mapping[str, Any], value: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if value.get("t") != "ref": return None
    item = _heap_object(state, value)
    if item["kind"] == "instance": return _check_value(item["payload"]["class"])
    if item["kind"] == "class": return value
    return None


def _get_attr(state: MutableMapping[str, Any], value: Mapping[str, Any], name: str) -> tuple[str, Any]:
    if value.get("t") in {"type", "exception-type"} and name == "__name__":
        return "value", _v_str(str(value["v"]))
    if value.get("t") == "ref" and _heap_object(state, value)["kind"] == "super":
        return _super_attr(state, value, name)
    if value.get("t") == "ref":
        item = _heap_object(state, value)
        if item["kind"] == "module":
            found = _env_get(state, _check_value(item["payload"]["namespace"]), name)
            if found is None: raise AttributeError(f"module has no attribute {name!r}")
            return "value", found
        if item["kind"] == "instance":
            attrs = _check_value(item["payload"]["attrs"])
            found = _env_get(state, attrs, name)
            class_ref = _check_value(item["payload"]["class"])
            descriptor = _lookup_class_attr(state, class_ref, name)
            if descriptor is not None and descriptor.get("t") == "ref":
                descriptor_item = _heap_object(state, descriptor)
                if descriptor_item["kind"] == "property":
                    getter = descriptor_item["payload"].get("getter")
                    if getter is None: raise AttributeError(f"unreadable attribute {name!r}")
                    return "call", (_check_value(getter), [value], {})
                descriptor_class = _instance_class(state, descriptor)
                if descriptor_class is not None:
                    get_method = _lookup_class_attr(state, descriptor_class, "__get__")
                    if get_method is not None:
                        return "call", ({"t": "bound", "func": _plain(get_method), "self": _plain(descriptor)}, [value, class_ref], {})
            if found is not None: return "value", found
            if descriptor is not None:
                if descriptor.get("t") == "ref" and _heap_object(state, descriptor)["kind"] == "function":
                    return "value", {"t": "bound", "func": _plain(descriptor), "self": _plain(value)}
                if descriptor.get("t") == "ref" and _heap_object(state, descriptor)["kind"] == "staticmethod":
                    return "value", _check_value(_heap_object(state, descriptor)["payload"]["function"])
                if descriptor.get("t") == "ref" and _heap_object(state, descriptor)["kind"] == "classmethod":
                    function = _check_value(_heap_object(state, descriptor)["payload"]["function"])
                    return "value", {"t": "bound", "func": _plain(function), "self": _plain(class_ref)}
                return "value", descriptor
            fallback = _lookup_class_attr(state, class_ref, "__getattr__")
            if fallback is not None:
                return "call", ({"t": "bound", "func": _plain(fallback), "self": _plain(value)}, [_v_str(name)], {})
            raise AttributeError(f"{item['type_name']} has no attribute {name!r}")
        if item["kind"] == "class":
            if name == "__name__":
                return "value", _v_str(str(item["payload"]["name"]))
            if name == "__qualname__":
                return "value", _v_str(str(item["payload"]["qualname"]))
            if name == "__bases__":
                return "value", _alloc(
                    state,
                    "tuple",
                    {"items": copy.deepcopy(item["payload"]["bases"])},
                )
            if name == "__type_params__":
                return "value", _from_host(state, item["payload"].get("type_params", []))
            found = _lookup_class_attr(state, value, name)
            if found is None: raise AttributeError(f"class has no attribute {name!r}")
            if found.get("t") == "ref" and _heap_object(state, found)["kind"] == "classmethod":
                function = _check_value(_heap_object(state, found)["payload"]["function"])
                return "value", {"t": "bound", "func": _plain(function), "self": _plain(value)}
            if found.get("t") == "ref" and _heap_object(state, found)["kind"] == "staticmethod":
                return "value", _check_value(_heap_object(state, found)["payload"]["function"])
            return "value", found
        if item["kind"] == "function":
            if name == "__annotations__":
                return "value", _check_value(item["payload"]["annotations"])
            if name == "__type_params__":
                return "value", _from_host(state, item["payload"].get("type_params", []))
            if name == "__annotations__":
                return "value", _check_value(item["payload"]["annotations"])
            if name == "__name__":
                return "value", _v_str(str(item["payload"]["name"]))
            if name == "__qualname__":
                return "value", _v_str(str(item["payload"]["qualname"]))
        if item["kind"] == "property" and name in {"getter", "setter", "deleter"}:
            return "value", _v_method(name, value)
        method_sets = {
            "list": {"append", "extend", "insert", "pop", "clear", "copy", "count", "index", "remove", "reverse", "sort"},
            "tuple": {"count", "index"},
            "dict": {"get", "items", "keys", "values", "update", "setdefault", "pop", "clear", "copy"},
            "set": {"add", "discard", "remove", "pop", "clear", "update", "union", "intersection"},
            "bytearray": {"append", "extend", "decode"},
            "generator": {"send", "throw", "close"},
            "coroutine": {"send", "throw", "close", "__await__"},
        }
        if name in method_sets.get(item["kind"], set()): return "value", _v_method(name, value)
        if name == "__class__": return "value", _v_type(item["type_name"])
    if value.get("t") in {"str", "bytes"}:
        methods = {"upper", "lower", "split", "join", "strip", "replace", "find", "startswith", "endswith", "encode", "decode", "format"}
        if name in methods: return "value", _v_method(name, value)
    if name == "__class__": return "value", _v_type(_type_name(state, value))
    raise AttributeError(f"{_type_name(state, value)} has no attribute {name!r}")


def _store_attr(state: MutableMapping[str, Any], target: Mapping[str, Any], name: str, value: Mapping[str, Any]) -> tuple[str, Any] | None:
    item = _heap_object(state, target)
    if item["kind"] != "instance": raise TypeError("attribute assignment requires an instance")
    class_ref = _check_value(item["payload"]["class"])
    descriptor = _lookup_class_attr(state, class_ref, name)
    if descriptor is not None and descriptor.get("t") == "ref":
        desc = _heap_object(state, descriptor)
        if desc["kind"] == "property" and desc["payload"].get("setter") is not None:
            return "call", (_check_value(desc["payload"]["setter"]), [target, value], {})
        desc_class = _instance_class(state, descriptor)
        if desc_class is not None:
            setter = _lookup_class_attr(state, desc_class, "__set__")
            if setter is not None:
                return "call", ({"t": "bound", "func": _plain(setter), "self": _plain(descriptor)}, [target, value], {})
    _env_set(state, _check_value(item["payload"]["attrs"]), name, value)
    _mutated(item)
    return None


def _delete_attr(
    state: MutableMapping[str, Any],
    target: Mapping[str, Any],
    name: str,
) -> tuple[str, Any] | None:
    item = _heap_object(state, target)
    if item["kind"] != "instance":
        raise TypeError("attribute deletion requires an instance")
    class_ref = _check_value(item["payload"]["class"])
    descriptor = _lookup_class_attr(state, class_ref, name)
    if descriptor is not None and descriptor.get("t") == "ref":
        desc = _heap_object(state, descriptor)
        if desc["kind"] == "property" and desc["payload"].get("deleter") is not None:
            return "call", (_check_value(desc["payload"]["deleter"]), [target], {})
        desc_class = _instance_class(state, descriptor)
        if desc_class is not None:
            deleter = _lookup_class_attr(state, desc_class, "__delete__")
            if deleter is not None:
                return "call", (
                    {"t": "bound", "func": _plain(deleter), "self": _plain(descriptor)},
                    [target],
                    {},
                )
    _env_delete(state, _check_value(item["payload"]["attrs"]), name)
    _mutated(item)
    return None


def _c3_mro(state: Mapping[str, Any], bases: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    sequences = [_class_mro(state, base)[:] for base in bases] + [list(bases)]
    result: list[Mapping[str, Any]] = []
    while any(sequences):
        sequences = [seq for seq in sequences if seq]
        candidate = None
        for seq in sequences:
            head = seq[0]
            if not any(any(dict(head) == dict(item) for item in other[1:]) for other in sequences):
                candidate = head; break
        if candidate is None: raise TypeError("cannot create a consistent method resolution order")
        result.append(candidate)
        for seq in sequences:
            if seq and dict(seq[0]) == dict(candidate): seq.pop(0)
    return result


def _make_class(
    state: MutableMapping[str, Any],
    name: str,
    bases: Sequence[Mapping[str, Any]],
    namespace: Mapping[str, Any],
    keywords: Mapping[str, Mapping[str, Any]],
    *,
    type_params: Sequence[Mapping[str, Any]] = (),
) -> Mapping[str, Any]:
    if not bases:
        object_type = state["runtime_roots"].get("object_type")
        bases = [] if object_type is None else [_check_value(object_type)]
    for base in bases:
        if _heap_object(state, base)["kind"] != "class": raise TypeError("bases must be classes")
    tail = _c3_mro(state, bases)
    class_ref = _alloc(
        state,
        "class",
        {
            "name": name,
            "qualname": name,
            "bases": list(bases),
            "mro_tail": tail,
            "namespace": _plain(namespace),
            "metaclass": keywords.get("metaclass"),
            "type_params": copy.deepcopy(list(type_params)),
        },
        type_name="type",
    )
    return class_ref


def _frame_code(state: Mapping[str, Any], frame: Mapping[str, Any]) -> Mapping[str, Any]:
    program = state["programs"].get(frame["program_id"])
    if not isinstance(program, Mapping): raise RuntimeError("frame program is unavailable")
    code = program["code"]["codes"].get(frame["code_id"])
    if not isinstance(code, Mapping): raise RuntimeError("frame code is unavailable")
    return code


def _new_frame(
    state: MutableMapping[str, Any],
    *,
    program_id: str,
    code_id: str,
    locals_ref: Mapping[str, Any],
    globals_ref: Mapping[str, Any],
    builtins_ref: Mapping[str, Any],
    return_context: Mapping[str, Any] | None = None,
) -> str:
    if len(state["frames"]) >= _limit(state, "max_frames"):
        _quota_exhausted(
            state,
            "max_frames",
            len(state["frames"]) + 1,
            "field frame limit exhausted",
            guest_type="RecursionError",
        )
    frame_id = _next_id(state, "frame")
    state["frames"][frame_id] = {
        "schema": "cassifi.py-frame-state.v1",
        "frame_id": frame_id,
        "program_id": program_id,
        "code_id": code_id,
        "pc": 0,
        "locals": _plain(locals_ref),
        "globals": _plain(globals_ref),
        "builtins": _plain(builtins_ref),
        "stack": [],
        "blocks": [],
        "current_exception": None,
        "pending_signal": None,
        "return_context": None if return_context is None else _plain(return_context),
        "last_span": None,
    }
    state["ledger"]["frames_created"] += 1
    return frame_id


def _bind_arguments(
    state: MutableMapping[str, Any],
    function_item: Mapping[str, Any],
    positional: Sequence[Mapping[str, Any]],
    keywords: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    payload = function_item["payload"]
    program = state["programs"][payload["program_id"]]
    code = program["code"]["codes"][payload["code_id"]]
    spec = code["arguments"]
    posonly = list(spec["posonly"])
    normal = list(spec["positional"])
    all_pos = posonly + normal
    defaults = list(payload.get("defaults", []))
    kw_defaults = dict(payload.get("kw_defaults", {}))
    bound: dict[str, Mapping[str, Any]] = {}
    if len(positional) > len(all_pos) and spec["vararg"] is None:
        raise TypeError(f"{payload['name']}() takes {len(all_pos)} positional arguments but {len(positional)} were given")
    for name, value in zip(all_pos, positional): bound[name] = value
    extras = list(positional[len(all_pos):])
    for name, value in keywords.items():
        if name in posonly: raise TypeError(f"{payload['name']}() got positional-only argument passed as keyword: {name}")
        if name in bound: raise TypeError(f"{payload['name']}() got multiple values for argument {name!r}")
        if name in all_pos or name in spec["kwonly"]: bound[name] = value
        elif spec["kwarg"] is None: raise TypeError(f"{payload['name']}() got an unexpected keyword argument {name!r}")
    required_count = len(all_pos) - len(defaults)
    for index, name in enumerate(all_pos):
        if name not in bound:
            if index < required_count: raise TypeError(f"{payload['name']}() missing required argument: {name!r}")
            bound[name] = _check_value(defaults[index - required_count])
    for name in spec["kwonly"]:
        if name not in bound:
            if name not in kw_defaults: raise TypeError(f"{payload['name']}() missing required keyword-only argument: {name!r}")
            bound[name] = _check_value(kw_defaults[name])
    if spec["vararg"] is not None: bound[spec["vararg"]] = _alloc(state, "tuple", {"items": extras})
    if spec["kwarg"] is not None:
        extra_pairs = [[_v_str(name), value] for name, value in keywords.items() if name not in all_pos and name not in spec["kwonly"]]
        bound[spec["kwarg"]] = _alloc(state, "dict", {"entries": extra_pairs})
    env_ref = _env(state, _check_value(payload["closure"]), "function")
    for name, value in bound.items(): _env_set(state, env_ref, name, value)
    return env_ref


def _push_frame_call(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
    function_ref: Mapping[str, Any],
    positional: Sequence[Mapping[str, Any]],
    keywords: Mapping[str, Mapping[str, Any]],
    *,
    return_context: Mapping[str, Any] | None = None,
) -> Mapping[str, Any] | None:
    function_item = _heap_object(state, function_ref)
    if function_item["kind"] != "function": raise TypeError("object is not a field function")
    locals_ref = _bind_arguments(state, function_item, positional, keywords)
    payload = function_item["payload"]
    frame_id = _new_frame(
        state,
        program_id=payload["program_id"],
        code_id=payload["code_id"],
        locals_ref=locals_ref,
        globals_ref=_check_value(payload["globals"]),
        builtins_ref=_check_value(payload["builtins"]),
        return_context=return_context,
    )
    code = _frame_code(state, state["frames"][frame_id])
    flags = set(code.get("flags", []))
    if "generator" in flags or "coroutine" in flags:
        if "async-generator" in flags:
            kind = "async-generator"
        else:
            kind = "coroutine" if "coroutine" in flags else "generator"
        return _alloc(
            state,
            kind,
            {
                "frame_id": frame_id,
                "status": "created",
                "yield_count": 0,
                "return": None,
            },
            type_name=kind,
        )
    if len(task["stack"]) >= _limit(state, "max_call_depth"):
        del state["frames"][frame_id]
        _quota_exhausted(
            state,
            "max_call_depth",
            len(task["stack"]) + 1,
            "maximum field call depth exceeded",
            guest_type="RecursionError",
        )
    task["stack"].append(frame_id)
    return None


def _invoke(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
    callable_value: Mapping[str, Any],
    positional: Sequence[Mapping[str, Any]],
    keywords: Mapping[str, Mapping[str, Any]],
    *,
    return_context: Mapping[str, Any] | None = None,
) -> tuple[bool, Mapping[str, Any] | None]:
    kind = callable_value.get("t")
    if kind == "bound":
        return _invoke(state, task, _check_value(callable_value["func"]), [_check_value(callable_value["self"]), *positional], keywords, return_context=return_context)
    if kind == "builtin":
        return True, _call_builtin(state, task, str(callable_value["v"]), positional, keywords)
    if kind == "method":
        result = _call_method(
            state,
            task,
            str(callable_value["name"]),
            _check_value(callable_value["self"]),
            positional,
            keywords,
            return_context=return_context,
        )
        return result.get("t") != "deferred", result
    if kind == "exception-type":
        type_name = str(callable_value["v"])
        message = (
            ""
            if not positional
            else _repr_value(state, positional[0])
            if positional[0].get("t") != "str"
            else _as_str(positional[0])
        )
        exception = _exception(state, type_name, message)
        if type_name in {"ExceptionGroup", "BaseExceptionGroup"}:
            if keywords or len(positional) != 2:
                raise TypeError(
                    f"{type_name} requires a message and an exception sequence"
                )
            collection = _check_value(positional[1])
            if collection.get("t") != "ref":
                raise TypeError("exceptions must be a sequence")
            collection_item = _heap_object(state, collection)
            if collection_item["kind"] not in {"list", "tuple"}:
                raise TypeError("exceptions must be a sequence")
            children = [
                _check_value(value)
                for value in collection_item["payload"]["items"]
            ]
            if not children:
                raise ValueError("second argument (exceptions) must be non-empty")
            for child in children:
                if (
                    child.get("t") != "ref"
                    or _heap_object(state, child)["kind"] != "exception"
                ):
                    raise ValueError(
                        "second argument (exceptions) must contain exceptions"
                    )
            exception_item = _heap_object(state, exception)
            exception_item["payload"]["exceptions"] = [
                _plain(child) for child in children
            ]
            _mutated(exception_item)
        return True, exception
    if kind == "type":
        type_name = str(callable_value["v"])
        if (
            type_name in {"list", "tuple", "set", "frozenset", "dict"}
            and len(positional) == 1
            and not keywords
            and positional[0].get("t") == "ref"
            and _heap_object(state, positional[0])["kind"] in {"generator", "coroutine", "map", "filter"}
        ):
            accumulator = _alloc(
                state,
                type_name,
                {"entries": []} if type_name == "dict" else {"items": []},
            )
            if _heap_object(state, positional[0])["kind"] in {"map", "filter"}:
                _resume_callable_iterator(
                    state,
                    task,
                    positional[0],
                    {
                        "mode": "collect",
                        "collection_kind": type_name,
                        "accumulator": _plain(accumulator),
                    },
                )
            else:
                _resume_generator(
                    state,
                    task,
                    positional[0],
                    mode="next",
                    value=None,
                caller_context={
                    "kind": "builtin-collect",
                    "collection_kind": type_name,
                    "accumulator": _plain(accumulator),
                },
            )
            return False, None
        return True, _call_type(state, type_name, positional, keywords)
    if kind == "ref":
        item = _heap_object(state, callable_value)
        if item["kind"] == "function":
            immediate = _push_frame_call(state, task, callable_value, positional, keywords, return_context=return_context)
            return immediate is not None, immediate
        if item["kind"] == "weakref":
            target = item["payload"].get("target")
            return True, _v_none() if target is None else _check_value(target)
        if item["kind"] == "class":
            attrs = _env(state, None, "instance")
            instance = _alloc(state, "instance", {"class": _plain(callable_value), "attrs": attrs}, type_name=str(item["payload"]["name"]), finalizer=_lookup_class_attr(state, callable_value, "__del__") is not None)
            initializer = _lookup_class_attr(state, callable_value, "__init__")
            if initializer is None:
                if positional or keywords: raise TypeError(f"{item['payload']['name']}() takes no arguments")
                return True, instance
            bound = {"t": "bound", "func": _plain(initializer), "self": _plain(instance)}
            return _invoke(state, task, bound, positional, keywords, return_context={"kind": "return-override", "value": instance})
        class_ref = _instance_class(state, callable_value)
        if class_ref is not None:
            call = _lookup_class_attr(state, class_ref, "__call__")
            if call is not None:
                return _invoke(state, task, {"t": "bound", "func": _plain(call), "self": _plain(callable_value)}, positional, keywords, return_context=return_context)
    raise TypeError(f"{_type_name(state, callable_value)} object is not callable")


def _call_type(state: MutableMapping[str, Any], name: str, positional: Sequence[Mapping[str, Any]], keywords: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    if keywords: raise TypeError(f"{name}() does not accept keyword arguments here")
    value = positional[0] if positional else _v_none()
    if name == "int": return _v_int(0 if not positional else int(_to_host(state, value)))
    if name == "float": return _v_float(0.0 if not positional else float(_to_host(state, value)))
    if name == "complex": return _v_complex(0j if not positional else complex(_to_host(state, value)))
    if name == "str": return _v_str("" if not positional else _str_value(state, value))
    if name == "bool": return _v_bool(False if not positional else _truth(state, value))
    if name == "bytes": return _v_bytes(b"" if not positional else bytes(_to_host(state, value)))
    if name == "bytearray": return _from_host(state, bytearray() if not positional else bytearray(_to_host(state, value)))
    if name in {"list", "tuple", "set", "frozenset"}:
        items = [] if not positional else _iter_values(state, value)
        return _alloc(state, name, {"items": copy.deepcopy(items)})
    if name == "dict":
        ref = _alloc(state, "dict", {"entries": []})
        if positional:
            source = _heap_object(state, value)
            if source["kind"] == "dict":
                _heap_object(state, ref)["payload"]["entries"] = copy.deepcopy(source["payload"]["entries"])
            else:
                for pair in _iter_values(state, value):
                    members = _iter_values(state, pair)
                    if len(members) != 2: raise ValueError("dictionary update sequence element has length not equal to 2")
                    _dict_set(state, ref, members[0], members[1])
        return ref
    if name == "object": return _alloc(state, "instance", {"class": state["runtime_roots"]["object_type"], "attrs": _env(state, None, "instance")}, type_name="object")
    raise TypeError(f"unsupported field type constructor {name}")


def _call_method(state: MutableMapping[str, Any], task: MutableMapping[str, Any], name: str, target: Mapping[str, Any], positional: Sequence[Mapping[str, Any]], keywords: Mapping[str, Mapping[str, Any]], *, return_context: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    if keywords and name not in {"sort", "format"}: raise TypeError(f"{name}() does not accept keyword arguments")
    if target.get("t") in {"str", "bytes"}:
        host = _to_host(state, target)
        args = [_to_host(state, value) for value in positional]
        if name == "format": return _from_host(state, host.format(*args, **{key: _to_host(state, value) for key, value in keywords.items()}))
        return _from_host(state, getattr(host, name)(*args))
    item = _heap_object(state, target)
    if item["kind"] == "list":
        values = item["payload"]["items"]
        if name == "append": values.append(_plain(positional[0])); result = _v_none()
        elif name == "extend": values.extend(copy.deepcopy(_iter_values(state, positional[0]))); result = _v_none()
        elif name == "insert": values.insert(_as_int(positional[0]), _plain(positional[1])); result = _v_none()
        elif name == "pop": result = _check_value(values.pop(-1 if not positional else _as_int(positional[0])))
        elif name == "clear": values.clear(); result = _v_none()
        elif name == "copy": return _alloc(state, "list", {"items": copy.deepcopy(values)})
        elif name == "count": return _v_int(sum(_value_equal(state, positional[0], value) for value in values))
        elif name == "index":
            result = _v_int(next(index for index, value in enumerate(values) if _value_equal(state, positional[0], value)))
        elif name == "remove":
            index = next(index for index, value in enumerate(values) if _value_equal(state, positional[0], value)); del values[index]; result = _v_none()
        elif name == "reverse": values.reverse(); result = _v_none()
        elif name == "sort":
            reverse = _truth(state, keywords.get("reverse", _v_bool(False)))
            key = keywords.get("key")
            if key is not None and key.get("t") != "none":
                immediate, result = _start_sort_operation(
                    state,
                    task,
                    values=list(values),
                    callback=key,
                    reverse=reverse,
                    target=target,
                )
                if immediate:
                    return result
                return {"t": "deferred"}
            values.sort(key=lambda value: _to_host(state, value), reverse=reverse)
            result = _v_none()
        else:
            raise AttributeError(name)
        _mutated(item)
        return result
    if item["kind"] == "tuple":
        values = item["payload"]["items"]
        if name == "count":
            if len(positional) != 1: raise TypeError("tuple.count() takes exactly one argument")
            return _v_int(sum(_value_equal(state, positional[0], value) for value in values))
        if name == "index":
            if not positional: raise TypeError("tuple.index() takes at least one argument")
            start = _as_int(positional[1]) if len(positional) > 1 else 0
            stop = _as_int(positional[2]) if len(positional) > 2 else len(values)
            for index in range(*slice(start, stop).indices(len(values))):
                if _value_equal(state, positional[0], values[index]): return _v_int(index)
            raise ValueError("tuple.index(x): x not in tuple")
        raise AttributeError(name)
    if item["kind"] == "property":
        if name not in {"getter", "setter", "deleter"} or len(positional) != 1:
            raise AttributeError(name)
        payload = copy.deepcopy(item["payload"])
        payload[name] = _plain(positional[0])
        return _alloc(state, "property", payload)
    if item["kind"] == "dict":
        if name == "get":
            index = _dict_find(state, item, positional[0]); return positional[1] if index is None and len(positional) > 1 else _v_none() if index is None else _check_value(item["payload"]["entries"][index][1])
        if name in {"keys", "values", "items"}:
            if name == "keys": values = [key for key, _ in item["payload"]["entries"]]
            elif name == "values": values = [value for _, value in item["payload"]["entries"]]
            else: values = [_alloc(state, "tuple", {"items": [key, value]}) for key, value in item["payload"]["entries"]]
            return _alloc(state, "list", {"items": copy.deepcopy(values)}, type_name=f"dict_{name}")
        if name == "update":
            other = _heap_object(state, positional[0])
            if other["kind"] != "dict": raise TypeError("dict.update requires mapping")
            for key, value in other["payload"]["entries"]: _dict_set(state, target, key, value)
            return _v_none()
        if name == "setdefault":
            index = _dict_find(state, item, positional[0])
            if index is not None: return _check_value(item["payload"]["entries"][index][1])
            value = positional[1] if len(positional) > 1 else _v_none(); _dict_set(state, target, positional[0], value); return value
        if name == "pop":
            index = _dict_find(state, item, positional[0])
            if index is None:
                if len(positional) > 1: return positional[1]
                raise KeyError(_repr_value(state, positional[0]))
            _, result = item["payload"]["entries"].pop(index); _mutated(item); return _check_value(result)
        if name == "clear": item["payload"]["entries"].clear(); _mutated(item); return _v_none()
        if name == "copy": return _alloc(state, "dict", {"entries": copy.deepcopy(item["payload"]["entries"])})
    if item["kind"] == "set":
        values = item["payload"]["items"]
        if name == "add":
            if not any(_value_equal(state, positional[0], value) for value in values): values.append(_plain(positional[0]))
            _mutated(item); return _v_none()
        if name in {"discard", "remove"}:
            index = next((i for i, value in enumerate(values) if _value_equal(state, positional[0], value)), None)
            if index is None and name == "remove": raise KeyError(_repr_value(state, positional[0]))
            if index is not None: del values[index]; _mutated(item)
            return _v_none()
        if name == "clear": values.clear(); _mutated(item); return _v_none()
        if name == "pop":
            if not values: raise KeyError("pop from an empty set")
            result = values.pop(); _mutated(item); return _check_value(result)
        if name == "update":
            for value in _iter_values(state, positional[0]):
                if not any(_value_equal(state, value, old) for old in values): values.append(_plain(value))
            _mutated(item); return _v_none()
        if name in {"union", "intersection"}:
            other = _iter_values(state, positional[0])
            selected = values + [value for value in other if not any(_value_equal(state, value, old) for old in values)] if name == "union" else [value for value in values if any(_value_equal(state, value, old) for old in other)]
            return _alloc(state, "set", {"items": copy.deepcopy(selected)})
    if item["kind"] == "bytearray":
        data = bytearray(base64.b64decode(item["payload"]["bytes"]))
        if name == "append": data.append(_as_int(positional[0])); result = _v_none()
        elif name == "extend": data.extend(bytes(_to_host(state, positional[0]))); result = _v_none()
        elif name == "decode": return _v_str(bytes(data).decode("utf-8" if not positional else _as_str(positional[0])))
        else: raise AttributeError(name)
        item["payload"]["bytes"] = base64.b64encode(bytes(data)).decode("ascii"); _mutated(item); return result
    if item["kind"] in {"generator", "coroutine"}:
        if name in {"send", "throw", "close", "__await__"}:
            if name == "__await__": return target
            mode = "next" if name == "send" and positional and positional[0].get("t") == "none" else name
            _resume_generator(state, task, target, mode=mode, value=None if not positional else positional[0], caller_context={"kind": "builtin-next"})
            return {"t": "deferred"}
    raise AttributeError(name)


def _append_collected_value(
    state: MutableMapping[str, Any],
    accumulator: Mapping[str, Any],
    collection_kind: str,
    value: Mapping[str, Any],
) -> None:
    item = _heap_object(state, accumulator)
    if item["kind"] != collection_kind:
        raise RuntimeError("generator collection accumulator is invalid")
    if collection_kind == "dict":
        pair = _iter_values(state, value)
        if len(pair) != 2:
            raise ValueError(
                f"dictionary update sequence element has length {len(pair)}; 2 is required"
            )
        _dict_set(state, accumulator, pair[0], pair[1])
        return
    items = item["payload"]["items"]
    if collection_kind in {"set", "frozenset"} and any(
        _value_equal(state, value, member) for member in items
    ):
        return
    if len(items) >= _limit(state, "max_collection_items"):
        _quota_exhausted(
            state,
            "max_collection_items",
            len(items) + 1,
            "collection exceeds field limit",
        )
    items.append(_plain(value))
    _mutated(item)


def _call_builtin(state: MutableMapping[str, Any], task: MutableMapping[str, Any], name: str, positional: Sequence[Mapping[str, Any]], keywords: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    if name == "len":
        value = positional[0]
        if value.get("t") in {"str", "bytes"}: return _v_int(len(_to_host(state, value)))
        item = _heap_object(state, value)
        if item["kind"] in {"list", "tuple", "set", "frozenset"}: return _v_int(len(item["payload"]["items"]))
        if item["kind"] == "dict": return _v_int(len(item["payload"]["entries"]))
        if item["kind"] == "range": return _v_int(len(_to_host(state, value)))
        if item["kind"] == "bytearray": return _v_int(len(base64.b64decode(item["payload"]["bytes"])))
        raise TypeError("object has no len()")
    if name == "range":
        values = [_as_int(value) for value in positional]
        host = range(*values)
        return _alloc(state, "range", {"start": host.start, "stop": host.stop, "step": host.step})
    if name == "enumerate":
        start = 0 if len(positional) < 2 else _as_int(positional[1])
        items = [_alloc(state, "tuple", {"items": [_v_int(index), value]}) for index, value in enumerate(_iter_values(state, positional[0]), start)]
        return _alloc(state, "list", {"items": items})
    if name == "zip":
        rows = zip(*[_iter_values(state, value) for value in positional])
        return _alloc(state, "list", {"items": [_alloc(state, "tuple", {"items": list(row)}) for row in rows]})
    if name in {"map", "filter"}:
        required = 2 if name == "map" else 2
        if len(positional) < required or keywords:
            raise TypeError(f"{name}() requires a callable and iterable")
        callback = positional[0]
        sources = positional[1:]
        if name == "filter" and len(sources) != 1:
            raise TypeError("filter() takes exactly two arguments")
        return _alloc(
            state,
            name,
            {
                "callback": _plain(callback),
                "iterators": [_plain(_make_iterator(state, source)) for source in sources],
            },
            type_name=name,
        )
    if name == "iter": return _make_iterator(state, positional[0])
    if name == "next":
        iterator = positional[0]
        if iterator.get("t") == "ref" and _heap_object(state, iterator)["kind"] in {"generator", "coroutine"}:
            _resume_generator(state, task, iterator, mode="next", value=None, caller_context={"kind": "builtin-next", "default": None if len(positional) < 2 else positional[1]})
            return {"t": "deferred"}
        if iterator.get("t") == "ref" and _heap_object(state, iterator)["kind"] in {"map", "filter"}:
            _resume_callable_iterator(
                state,
                task,
                iterator,
                {"mode": "next", "default": None if len(positional) < 2 else _plain(positional[1])},
            )
            return {"t": "deferred"}
        result = _iterator_next(state, iterator)
        if result is None:
            if len(positional) > 1: return positional[1]
            raise _GuestSignal(_exception(state, "StopIteration", ""))
        return result
    if name in {"list", "tuple", "set", "frozenset", "dict", "int", "float", "complex", "str", "bool", "bytes", "bytearray", "object"}:
        return _call_type(state, name, positional, keywords)
    if name == "abs": return _from_host(state, abs(_to_host(state, positional[0])))
    if name == "round": return _from_host(state, round(_to_host(state, positional[0]), *[_as_int(value) for value in positional[1:]]))
    if name == "divmod": return _from_host(state, divmod(_to_host(state, positional[0]), _to_host(state, positional[1])))
    if name == "pow": return _from_host(state, pow(*[_to_host(state, value) for value in positional]))
    if name == "sum":
        result = positional[1] if len(positional) > 1 else _v_int(0)
        iterable = positional[0]
        if iterable.get("t") == "ref" and _heap_object(state, iterable)["kind"] in {"generator", "coroutine"}:
            _resume_generator(
                state,
                task,
                iterable,
                mode="next",
                value=None,
                caller_context={
                    "kind": "builtin-reduce",
                    "operation": "sum",
                    "accumulator": _plain(result),
                    "seen": False,
                },
            )
            return {"t": "deferred"}
        for value in _iter_values(state, iterable):
            result = _binary(state, "add", result, value)
        return result
    if name in {"min", "max"}:
        iterable = positional[0] if len(positional) == 1 else None
        if iterable is not None and iterable.get("t") == "ref" and _heap_object(state, iterable)["kind"] in {"generator", "coroutine"}:
            _resume_generator(
                state,
                task,
                iterable,
                mode="next",
                value=None,
                caller_context={
                    "kind": "builtin-reduce",
                    "operation": name,
                    "accumulator": _v_none(),
                    "seen": False,
                },
            )
            return {"t": "deferred"}
        values = list(positional) if len(positional) > 1 else _iter_values(state, positional[0])
        if not values:
            raise ValueError(f"{name}() arg is an empty sequence")
    if name in {"all", "any"}:
        iterable = positional[0]
        if iterable.get("t") == "ref" and _heap_object(state, iterable)["kind"] in {"generator", "coroutine"}:
            _resume_generator(
                state,
                task,
                iterable,
                mode="next",
                value=None,
                caller_context={
                    "kind": "builtin-reduce",
                    "operation": name,
                    "accumulator": _v_bool(name == "all"),
                    "seen": False,
                },
            )
            return {"t": "deferred"}
        return _v_bool((all if name == "all" else any)(_truth(state, value) for value in _iter_values(state, iterable)))
    if name == "sorted":
        values = _iter_values(state, positional[0])
        reverse = _truth(state, keywords.get("reverse", _v_bool(False)))
        key = keywords.get("key")
        if key is None or key.get("t") == "none":
            values.sort(key=lambda value: _to_host(state, value), reverse=reverse)
            return _alloc(state, "list", {"items": copy.deepcopy(values)})
        immediate, result = _start_sort_operation(
            state,
            task,
            values=values,
            callback=key,
            reverse=reverse,
            target=None,
        )
        if immediate:
            return _check_value(result)
        return {"t": "deferred"}
    if name == "reversed": return _alloc(state, "list", {"items": list(reversed(copy.deepcopy(_iter_values(state, positional[0]))))})
    if name == "repr": return _v_str(_repr_value(state, positional[0]))
    if name == "print":
        sep = _as_str(keywords.get("sep", _v_str(" "))); end = _as_str(keywords.get("end", _v_str("\n")))
        text = sep.join(_as_str(value) if value.get("t") == "str" else _repr_value(state, value) for value in positional) + end
        next_stdout = state["stdout"] + text
        stdout_bytes = len(next_stdout.encode("utf-8"))
        if stdout_bytes > _limit(state, "max_string_bytes"):
            _quota_exhausted(
                state,
                "max_string_bytes",
                stdout_bytes,
                "stdout exceeds field limit",
            )
        state["stdout"] = next_stdout
        return _v_none()
    if name == "hash":
        if len(positional) != 1 or keywords:
            raise TypeError("hash() requires one positional argument")
        return _v_int(_stable_hash(state, positional[0]))
    if name == "id":
        if len(positional) != 1 or keywords:
            raise TypeError("id() requires one positional argument")
        value = positional[0]
        return _v_int(
            int(hashlib.sha256(canonical_json_bytes(value)).hexdigest()[:16], 16)
            if value.get("t") != "ref"
            else int(hashlib.sha256(_ref_id(value).encode()).hexdigest()[:16], 16)
        )
    if name == "type":
        if len(positional) == 1:
            class_ref = _instance_class(state, positional[0])
            return class_ref or _v_type(_type_name(state, positional[0]))
        if len(positional) == 3:
            class_name = _as_str(positional[0]); bases = _iter_values(state, positional[1]); namespace_dict = _heap_object(state, positional[2])
            if namespace_dict["kind"] != "dict": raise TypeError("type namespace must be dict")
            namespace = _env(state, None, "class")
            for key, value in namespace_dict["payload"]["entries"]: _env_set(state, namespace, _as_str(key), value)
            return _make_class(state, class_name, bases, namespace, {})
        raise TypeError("type() takes 1 or 3 arguments")
    if name in {"isinstance", "issubclass"}:
        subject, target = positional
        if name == "isinstance": subject = _instance_class(state, subject) or _v_type(_type_name(state, subject))
        if subject.get("t") == "type" and target.get("t") == "type": return _v_bool(subject["v"] == target["v"] or target["v"] == "object")
        if subject.get("t") == "ref" and _heap_object(state, subject)["kind"] == "class":
            candidates = _class_mro(state, subject)
            targets = _iter_values(state, target) if target.get("t") == "ref" and _heap_object(state, target)["kind"] == "tuple" else [target]
            return _v_bool(any(any(dict(candidate) == dict(wanted) for candidate in candidates) for wanted in targets))
        return _v_bool(False)
    if name == "getattr":
        if keywords or len(positional) not in {2, 3}:
            raise TypeError("getattr() requires two or three positional arguments")
        try:
            result_kind, result = _get_attr(
                state, positional[0], _as_str(positional[1])
            )
        except AttributeError:
            if len(positional) == 3:
                return positional[2]
            raise
        if result_kind == "call":
            callable_value, args, kwargs = result
            immediate, value = _invoke(state, task, callable_value, args, kwargs)
            return value if immediate else {"t": "deferred"}
        return result
    if name == "setattr":
        pending = _store_attr(state, positional[0], _as_str(positional[1]), positional[2])
        if pending is not None:
            _, (callable_value, args, kwargs) = pending
            immediate, _ = _invoke(state, task, callable_value, args, kwargs, return_context={"kind": "discard-return"})
            if not immediate: return {"t": "deferred"}
        return _v_none()
    if name == "hasattr":
        try: _get_attr(state, positional[0], _as_str(positional[1])); return _v_bool(True)
        except AttributeError: return _v_bool(False)
    if name == "delattr":
        pending = _delete_attr(state, positional[0], _as_str(positional[1]))
        if pending is not None:
            _, (callable_value, args, kwargs) = pending
            immediate, _ = _invoke(
                state,
                task,
                callable_value,
                args,
                kwargs,
                return_context={"kind": "discard-return"},
            )
            if not immediate:
                return {"t": "deferred"}
        return _v_none()
    if name in {"property", "staticmethod", "classmethod"}:
        if name == "property":
            return _alloc(state, "property", {"getter": positional[0] if positional else None, "setter": positional[1] if len(positional) > 1 and positional[1].get("t") != "none" else None, "deleter": positional[2] if len(positional) > 2 and positional[2].get("t") != "none" else None})
        return _alloc(state, name, {"function": positional[0]})
    if name == "super":
        if keywords or len(positional) > 2:
            raise TypeError("super() accepts zero, one, or two positional arguments")
        current_frame = state["frames"][task["stack"][-1]]
        if len(positional) == 2:
            start_class, receiver = positional
        elif len(positional) == 1:
            start_class = positional[0]
            receiver = _v_none()
        else:
            code = _frame_code(state, current_frame)
            local_class = _env_get(
                state,
                _check_value(current_frame["locals"]),
                "__class__",
            )
            if local_class is None:
                parts = str(code["qualname"]).split(".")
                class_name = parts[-2] if len(parts) >= 2 else ""
                local_class = _env_get(
                    state,
                    _check_value(current_frame["globals"]),
                    class_name,
                )
            arguments = code.get("arguments", {})
            first_names = [
                *arguments.get("posonly", []),
                *arguments.get("positional", []),
            ]
            receiver = (
                _env_get(
                    state,
                    _check_value(current_frame["locals"]),
                    str(first_names[0]),
                )
                if first_names
                else None
            )
            if local_class is None or receiver is None:
                raise RuntimeError("super(): no arguments and no enclosing class")
            start_class = local_class
        if start_class.get("t") != "ref" or _heap_object(state, start_class)["kind"] != "class":
            raise TypeError("super() argument 1 must be a class")
        return _alloc(
            state,
            "super",
            {
                "start_class": _plain(start_class),
                "receiver": _plain(receiver),
            },
            type_name="super",
        )
    if name == "memoryview":
        target = positional[0]; item = _heap_object(state, target)
        if item["kind"] != "bytearray": raise TypeError("field memoryview currently requires bytearray")
        length = len(base64.b64decode(item["payload"]["bytes"]))
        return _alloc(state, "memoryview", {"target": target, "start": 0, "stop": length})
    if name == "weakref":
        target = positional[0]; item = _heap_object(state, target)
        ref = _alloc(state, "weakref", {"target": target, "callback": positional[1] if len(positional) > 1 else None, "cleared": False})
        item["gc"]["weakrefs"].append(_ref_id(ref)); return ref
    if name in {"compile", "eval", "exec"}:
        return _dynamic_code(state, task, name, positional, keywords)
    if name == "globals": return _frame_env_dict(state, state["frames"][task["stack"][-1]]["globals"])
    if name == "locals": return _frame_env_dict(state, state["frames"][task["stack"][-1]]["locals"])
    if name == "request_model":
        return _request_external(state, task, "model", positional, keywords)
    if name == "request_effect":
        return _request_external(state, task, "effect", positional, keywords)
    if name == "field_checkpoint": return _v_str(digest_value(_checkpoint_payload(state)))
    if name == "collect": return _v_int(_collect(state)["reclaimed"])
    raise TypeError(f"unknown field builtin {name}")


def _dynamic_namespace(
    state: MutableMapping[str, Any],
    value: Mapping[str, Any],
    *,
    kind: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    item = _heap_object(state, value)
    if item["kind"] != "dict":
        raise TypeError(f"{kind} must be a dict")
    env_ref = _env(state, None, kind)
    for key, member in item["payload"]["entries"]:
        _env_set(state, env_ref, _as_str(_check_value(key)), _check_value(member))
    return env_ref, {"dict_ref": _plain(value), "env_ref": _plain(env_ref)}


def _sync_dynamic_namespace(
    state: MutableMapping[str, Any],
    pair: Mapping[str, Any],
) -> None:
    dict_ref = _check_value(pair["dict_ref"])
    env_ref = _check_value(pair["env_ref"])
    item = _heap_object(state, dict_ref)
    if item["kind"] != "dict":
        raise RuntimeError("dynamic namespace mapping changed type")
    live_names = set(_env_values(state, env_ref))
    item["payload"]["entries"] = [
        entry
        for entry in item["payload"]["entries"]
        if _check_value(entry[0]).get("t") != "str"
        or _as_str(_check_value(entry[0])) in live_names
    ]
    for key, member in _env_values(state, env_ref).items():
        _dict_set(state, dict_ref, _v_str(key), _check_value(member))
    _mutated(item)


def _sync_dynamic_context(
    state: MutableMapping[str, Any],
    context: Mapping[str, Any] | None,
) -> None:
    if not context or context.get("kind") != "dynamic":
        return
    seen: set[tuple[str, str]] = set()
    for raw_pair in context.get("sync_namespaces", []):
        pair = dict(raw_pair)
        identity = (
            _ref_id(_check_value(pair["dict_ref"])),
            _ref_id(_check_value(pair["env_ref"])),
        )
        if identity in seen:
            continue
        seen.add(identity)
        _sync_dynamic_namespace(state, pair)


def _dynamic_call_arguments(
    name: str,
    positional: Sequence[Mapping[str, Any]],
    keywords: Mapping[str, Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    parameter_names = (
        ["source", "filename", "mode", "flags", "dont_inherit", "optimize"]
        if name == "compile"
        else ["source", "globals", "locals"]
    )
    if len(positional) > len(parameter_names):
        raise TypeError(
            f"{name}() takes at most {len(parameter_names)} arguments "
            f"({len(positional)} given)"
        )
    bound = {
        parameter_names[index]: _check_value(value)
        for index, value in enumerate(positional)
    }
    for key, value in keywords.items():
        if key not in parameter_names:
            raise TypeError(f"{name}() got an unexpected keyword argument {key!r}")
        if key in bound:
            raise TypeError(f"{name}() got multiple values for argument {key!r}")
        bound[key] = _check_value(value)
    if "source" not in bound:
        raise TypeError(f"{name}() missing required argument 'source'")
    return bound


def _dynamic_code(state: MutableMapping[str, Any], task: MutableMapping[str, Any], name: str, positional: Sequence[Mapping[str, Any]], keywords: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    bound = _dynamic_call_arguments(name, positional, keywords)
    source_value = bound["source"]
    if name == "compile":
        if "filename" not in bound or "mode" not in bound:
            missing = "filename" if "filename" not in bound else "mode"
            raise TypeError(f"compile() missing required argument {missing!r}")
        if _as_int(bound.get("flags", _v_int(0))) != 0:
            raise NotImplementedError("compile() flags are unsupported")
        if _truth(state, bound.get("dont_inherit", _v_bool(False))):
            raise NotImplementedError("compile() dont_inherit is unsupported")
        if _as_int(bound.get("optimize", _v_int(-1))) not in {-1, 0}:
            raise NotImplementedError("compile() optimize levels are unsupported")
        source = _as_str(source_value)
        filename = _as_str(bound["filename"])
        mode = _as_str(bound["mode"])
        _check_source_limit(state, source)
        program = compile_python(source, source_name=filename, module=state["programs"][state["frames"][task["stack"][-1]]["program_id"]]["module"], mode=mode, program_id=f"dynamic:{hashlib.sha256(source.encode()).hexdigest()[:16]}", max_source_bytes=_limit(state, "max_source_bytes"))
        if (
            program.program_id not in state["programs"]
            and len(state["programs"]) >= _limit(state, "max_programs")
        ):
            _quota_exhausted(
                state,
                "max_programs",
                len(state["programs"]) + 1,
                "program limit exhausted",
            )
        state["programs"][program.program_id] = program.as_dict()
        return _alloc(state, "code", {"program_id": program.program_id, "entry": program.code["entry"], "mode": mode, "source_sha256": program.source_sha256})
    if source_value.get("t") == "ref" and _heap_object(state, source_value)["kind"] == "code":
        code_ref = source_value
    else:
        source = _as_str(source_value)
        mode = "eval" if name == "eval" else "exec"
        parent = state["programs"][state["frames"][task["stack"][-1]]["program_id"]]
        _check_source_limit(state, source)
        program = compile_python(source, source_name="<dynamic>", module=parent["module"], mode=mode, program_id=f"dynamic:{hashlib.sha256((mode + chr(0) + source).encode()).hexdigest()[:16]}", max_source_bytes=_limit(state, "max_source_bytes"))
        if (
            program.program_id not in state["programs"]
            and len(state["programs"]) >= _limit(state, "max_programs")
        ):
            _quota_exhausted(
                state,
                "max_programs",
                len(state["programs"]) + 1,
                "program limit exhausted",
            )
        state["programs"][program.program_id] = program.as_dict()
        code_ref = _alloc(state, "code", {"program_id": program.program_id, "entry": program.code["entry"], "mode": mode, "source_sha256": program.source_sha256})
    item = _heap_object(state, code_ref)
    current = state["frames"][task["stack"][-1]]
    globals_ref = _check_value(current["globals"])
    locals_ref = _check_value(current["locals"])
    sync_namespaces: list[Mapping[str, Any]] = []
    globals_value = bound.get("globals")
    custom_globals = globals_value is not None and globals_value.get("t") != "none"
    if custom_globals:
        globals_ref, sync_pair = _dynamic_namespace(state, globals_value, kind="dynamic-globals")
        sync_namespaces.append(sync_pair)
    locals_value = bound.get("locals")
    if locals_value is not None and locals_value.get("t") != "none":
        locals_ref, sync_pair = _dynamic_namespace(state, locals_value, kind="dynamic-locals")
        sync_namespaces.append(sync_pair)
    elif custom_globals:
        locals_ref = globals_ref
    context = {
        "kind": "dynamic",
        "mode": item["payload"]["mode"],
        "sync_namespaces": sync_namespaces,
    }
    frame_id = _new_frame(state, program_id=item["payload"]["program_id"], code_id=item["payload"]["entry"], locals_ref=locals_ref, globals_ref=globals_ref, builtins_ref=_check_value(current["builtins"]), return_context=context)
    task["stack"].append(frame_id)
    return {"t": "deferred"}


def _request_external(state: MutableMapping[str, Any], task: MutableMapping[str, Any], kind: str, positional: Sequence[Mapping[str, Any]], keywords: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    required_capability = {
        "model": "model-request",
        "effect": "effect-proposal",
    }.get(kind)
    if (
        required_capability is None
        or required_capability not in state["capabilities"]
    ):
        raise _GuestSignal(
            _exception(
                state,
                "PermissionError",
                f"{kind} request lacks capability {required_capability!r}",
            )
        )
    if state["branch_stack"]:
        raise _GuestSignal(_exception(state, "PermissionError", "speculative branches cannot dispatch external work"))
    if len(state["operations"]) >= _limit(state, "max_operations"):
        _quota_exhausted(
            state,
            "max_operations",
            len(state["operations"]) + 1,
            "operation limit exhausted",
        )
    if len(state["events"]) >= _limit(state, "max_events"):
        _quota_exhausted(
            state,
            "max_events",
            len(state["events"]) + 1,
            "event limit exhausted",
        )
    operation_id = _next_id(state, "operation")
    operation = {
        "schema": "cassifi.py-operation-state.v1",
        "operation_id": operation_id,
        "kind": kind,
        "phase": "proposed",
        "cursor": 0,
        "inputs": [_project(state, value) for value in positional],
        "keywords": {name: _project(state, value) for name, value in keywords.items()},
        "callback_tokens": [],
        "effect_tokens": [],
        "charged_work": 1,
        "result": None,
    }
    state["operations"][operation_id] = operation
    task["status"] = "waiting"
    task["await_target"] = operation_id
    task["pending_call"] = {"kind": kind, "operation_id": operation_id}
    event = {"schema": "cassifi.program-event.v1", "event_id": _next_id(state, "event"), "kind": f"{kind}-request", "operation_id": operation_id, "payload": {"inputs": operation["inputs"], "keywords": operation["keywords"]}}
    state["events"].append(event)
    return {"t": "deferred"}


def _dynamic_import(state: MutableMapping[str, Any], task: MutableMapping[str, Any], frame: MutableMapping[str, Any], spec: Mapping[str, Any]) -> tuple[bool, Mapping[str, Any] | None]:
    module_name = str(spec["module"])
    level = int(spec.get("level", 0))
    if level:
        current_program = state["programs"][frame["program_id"]]
        package = current_program.get("package") or current_program.get("module", "")
        parts = package.split(".") if package else []
        if level > len(parts) + 1: raise ImportError("attempted relative import beyond top-level package")
        prefix = ".".join(parts[: len(parts) - level + 1])
        module_name = f"{prefix}.{module_name}".strip(".")
    existing = state["modules"].get(module_name)
    if existing is not None: return True, _check_value(existing)
    if module_name in {"math", "json", "collections", "asyncio"}:
        namespace = _env(state, _check_value(state["runtime_roots"]["builtins"]), "module")
        exports = {
            "math": ["sqrt", "sin", "cos", "tan", "exp", "log", "floor", "ceil", "pi", "e"],
            "json": ["dumps", "loads"],
            "collections": ["deque"],
            "asyncio": ["sleep", "run"],
        }[module_name]
        for exported in exports:
            if exported == "pi": value = _v_float(math.pi)
            elif exported == "e": value = _v_float(math.e)
            else: value = _v_builtin(f"{module_name}.{exported}")
            _env_set(state, namespace, exported, value)
        module_ref = _alloc(state, "module", {"name": module_name, "namespace": namespace, "status": "ready"}, type_name="module")
        state["modules"][module_name] = module_ref
        return True, module_ref
    manifest = state["module_sources"].get(module_name)
    if not isinstance(manifest, Mapping):
        raise ImportError(f"field module {module_name!r} is unavailable (unsupported-native-abi or absent manifest)")
    if manifest.get("kind") == "native-extension":
        raise ImportError(f"field module {module_name!r} requires unsupported native ABI {manifest.get('abi', 'unspecified')}")
    if manifest.get("kind") != "field-python" or not isinstance(manifest.get("source"), str):
        raise ImportError(f"field module {module_name!r} manifest is unsupported")
    source = str(manifest["source"])
    _check_source_limit(state, source)
    program = compile_python(source, source_name=str(manifest.get("source_name", module_name)), module=module_name, package=str(manifest.get("package", module_name.rpartition(".")[0])) or None, mode="exec", program_id=f"module:{module_name}:{hashlib.sha256(source.encode()).hexdigest()[:16]}", max_source_bytes=_limit(state, "max_source_bytes"))
    if (
        program.program_id not in state["programs"]
        and len(state["programs"]) >= _limit(state, "max_programs")
    ):
        _quota_exhausted(
            state,
            "max_programs",
            len(state["programs"]) + 1,
            "program limit exhausted",
        )
    state["programs"][program.program_id] = program.as_dict()
    namespace = _env(state, _check_value(state["runtime_roots"]["builtins"]), "module")
    _env_set(state, namespace, "__name__", _v_str(module_name))
    module_ref = _alloc(state, "module", {"name": module_name, "namespace": namespace, "status": "initializing"}, type_name="module")
    state["modules"][module_name] = module_ref
    child_id = _new_frame(state, program_id=program.program_id, code_id=program.code["entry"], locals_ref=namespace, globals_ref=namespace, builtins_ref=_check_value(state["runtime_roots"]["builtins"]), return_context={"kind": "import", "module": module_name, "module_ref": module_ref})
    task["stack"].append(child_id)
    return False, None


def _call_library_builtin(state: MutableMapping[str, Any], name: str, positional: Sequence[Mapping[str, Any]], keywords: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    if name.startswith("math."):
        function = getattr(math, name.split(".", 1)[1]); return _from_host(state, function(*[_to_host(state, value) for value in positional]))
    if name == "json.dumps": return _v_str(json.dumps(_to_host(state, positional[0]), ensure_ascii=False, sort_keys=bool(_to_host(state, keywords.get("sort_keys", _v_bool(False))))))
    if name == "json.loads": return _from_host(state, json.loads(_as_str(positional[0])))
    if name == "collections.deque": return _alloc(state, "list", {"items": [] if not positional else _iter_values(state, positional[0])}, type_name="deque")
    if name == "asyncio.sleep":
        return _alloc(state, "coroutine", {"frame_id": None, "status": "completed", "yield_count": 0, "return": _v_none()}, type_name="coroutine")
    raise TypeError(f"unknown library primitive {name}")


def _builtins(state: MutableMapping[str, Any]) -> Mapping[str, Any]:
    env_ref = _env(state, None, "builtins")
    names = {
        "abs", "all", "any", "bool", "bytearray", "bytes", "classmethod",
        "collect", "compile", "complex", "delattr", "dict", "divmod", "enumerate",
        "eval", "exec", "field_checkpoint", "filter", "float", "frozenset", "getattr", "globals",
        "hasattr", "hash", "id", "int", "isinstance", "issubclass", "iter", "len",
        "list", "locals", "map", "max", "memoryview", "min", "next", "object", "pow",
        "print", "property", "range", "repr", "request_effect", "request_model",
        "reversed", "round", "set", "setattr", "sorted", "staticmethod", "str", "sum",
        "super", "tuple", "type", "weakref", "zip",
    }
    type_names = {"bool", "bytearray", "bytes", "complex", "dict", "float", "frozenset", "int", "list", "object", "set", "str", "tuple"}
    for name in sorted(names): _env_set(state, env_ref, name, _v_type(name) if name in type_names else _v_builtin(name))
    for name in _EXCEPTION_BASES: _env_set(state, env_ref, name, _v_exception_type(name))
    _env_set(state, env_ref, "None", _v_none())
    _env_set(state, env_ref, "True", _v_bool(True))
    _env_set(state, env_ref, "False", _v_bool(False))
    _env_set(state, env_ref, "NotImplemented", {"t": "not-implemented"})
    return env_ref


def _name_load(state: MutableMapping[str, Any], frame: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    code = _frame_code(state, frame)
    if name in code.get("globals", []): value = _env_get(state, _check_value(frame["globals"]), name)
    else: value = _env_get(state, _check_value(frame["locals"]), name)
    if value is None: value = _env_get(state, _check_value(frame["globals"]), name)
    if value is None: value = _env_get(state, _check_value(frame["builtins"]), name)
    if value is None: raise _GuestSignal(_exception(state, "NameError", f"name '{name}' is not defined"))
    return value


def _name_store(state: MutableMapping[str, Any], frame: Mapping[str, Any], name: str, value: Mapping[str, Any]) -> None:
    code = _frame_code(state, frame)
    target = _check_value(frame["globals"]) if name in code.get("globals", []) else _check_value(frame["locals"])
    if name in code.get("nonlocals", []):
        found = _env_find(state, target, name)
        if found is None: raise _GuestSignal(_exception(state, "NameError", f"no binding for nonlocal '{name}' found"))
        target = found
    _env_set(state, target, name, value)


def _name_delete(state: MutableMapping[str, Any], frame: Mapping[str, Any], name: str, *, missing_ok: bool = False) -> None:
    code = _frame_code(state, frame)
    target = _check_value(frame["globals"]) if name in code.get("globals", []) else _check_value(frame["locals"])
    if name in code.get("nonlocals", []): target = _env_find(state, target, name) or target
    _env_delete(state, target, name, missing_ok=missing_ok)


def _resume_generator(state: MutableMapping[str, Any], task: MutableMapping[str, Any], generator_ref: Mapping[str, Any], *, mode: str, value: Mapping[str, Any] | None, caller_context: Mapping[str, Any]) -> None:
    item = _heap_object(state, generator_ref)
    if item["kind"] not in {"generator", "coroutine", "async-generator"}:
        raise TypeError("object is not resumable")
    payload = item["payload"]
    if payload["status"] == "completed":
        raise _GuestSignal(_exception(state, "StopIteration", "", value=_check_value(payload.get("return", _v_none()))))
    frame_id = payload.get("frame_id")
    if not isinstance(frame_id, str) or frame_id not in state["frames"]:
        raise RuntimeError("generator frame is unavailable")
    frame = state["frames"][frame_id]
    if payload["status"] == "created" and mode == "send" and value is not None and value.get("t") != "none":
        raise TypeError("can't send non-None value to a just-started generator")
    if payload["status"] == "suspended":
        frame["stack"].append(_v_none() if value is None else _plain(value))
    if mode == "throw":
        frame["resume_signal"] = {"kind": "exception", "value": _plain(value or _exception(state, "RuntimeError", "generator throw"))}
    if mode == "close":
        frame["resume_signal"] = {"kind": "exception", "value": _exception(state, "GeneratorExit", "")}
    frame["return_context"] = {**dict(caller_context), "generator_ref": _plain(generator_ref)}
    payload["status"] = "running"
    _mutated(item)
    task["stack"].append(frame_id)


def _await_coroutine(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
    coroutine_ref: Mapping[str, Any],
    *,
    caller_context: Mapping[str, Any],
) -> tuple[bool, Mapping[str, Any] | None]:
    item = _heap_object(state, coroutine_ref)
    if item["kind"] != "coroutine":
        raise TypeError("object cannot be used in an await expression")
    payload = item["payload"]
    if payload["status"] == "completed":
        return True, _check_value(payload.get("return") or _v_none())
    _resume_generator(
        state,
        task,
        coroutine_ref,
        mode="next",
        value=None,
        caller_context=caller_context,
    )
    return False, None

def _start_sort_operation(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
    *,
    values: Sequence[Mapping[str, Any]],
    callback: Mapping[str, Any],
    reverse: bool,
    target: Mapping[str, Any] | None,
) -> tuple[bool, Mapping[str, Any] | None]:
    context: MutableMapping[str, Any] = {
        "kind": "sort-key",
        "values": [_plain(value) for value in values],
        "pairs": [],
        "callback": _plain(callback),
        "index": 0,
        "reverse": bool(reverse),
        "target": None if target is None else _plain(target),
    }
    return _resume_sort_operation(state, task, context, None)


def _resume_sort_operation(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
    context: MutableMapping[str, Any],
    result: Mapping[str, Any] | None,
) -> tuple[bool, Mapping[str, Any] | None]:
    if result is not None:
        context["pairs"].append([_plain(result), context["values"][int(context["index"]) - 1]])
    values = context["values"]
    index = int(context["index"])
    if index < len(values):
        context["index"] = index + 1
        immediate, callback_result = _invoke(
            state,
            task,
            _check_value(context["callback"]),
            [_check_value(values[index])],
            {},
            return_context=context,
        )
        if not immediate:
            return False, None
        return _resume_sort_operation(state, task, context, _check_value(callback_result))
    ordered = sorted(
        context["pairs"],
        key=lambda pair: _to_host(state, _check_value(pair[0])),
        reverse=bool(context["reverse"]),
    )
    target = context.get("target")
    if target is not None:
        item = _heap_object(state, _check_value(target))
        if item["kind"] != "list":
            raise RuntimeError("sort target is not a list")
        item["payload"]["items"] = [_plain(pair[1]) for pair in ordered]
        _mutated(item)
        return True, _v_none()
    return True, _alloc(state, "list", {"items": [_plain(pair[1]) for pair in ordered]})


def _start_decorators(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
    function: Mapping[str, Any],
    decorators: Sequence[Mapping[str, Any]],
) -> tuple[bool, Mapping[str, Any] | None]:
    context: MutableMapping[str, Any] = {
        "kind": "decorator",
        "decorators": [_plain(value) for value in reversed(decorators)],
        "index": 0,
        "function": _plain(function),
    }
    return _resume_decorators(state, task, context, None)


def _resume_decorators(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
    context: MutableMapping[str, Any],
    result: Mapping[str, Any] | None,
) -> tuple[bool, Mapping[str, Any] | None]:
    if result is not None:
        context["function"] = _plain(result)
    index = int(context["index"])
    decorators = context["decorators"]
    if index >= len(decorators):
        return True, _check_value(context["function"])
    context["index"] = index + 1
    immediate, callback_result = _invoke(
        state,
        task,
        _check_value(decorators[index]),
        [_check_value(context["function"])],
        {},
        return_context=context,
    )
    if not immediate:
        return False, None
    return _resume_decorators(state, task, context, _check_value(callback_result))


def _trace_exception(state: MutableMapping[str, Any], frame: Mapping[str, Any], exception: Mapping[str, Any]) -> None:
    item = _heap_object(state, exception)
    if item["kind"] != "exception": return
    code = _frame_code(state, frame)
    item["payload"]["traceback"].append({"program_id": frame["program_id"], "code": code["qualname"], "pc": max(0, int(frame["pc"]) - 1), "span": frame.get("last_span")})
    _mutated(item)


def _finish_frame(state: MutableMapping[str, Any], task: MutableMapping[str, Any], frame: MutableMapping[str, Any], value: Mapping[str, Any]) -> None:
    frame_id = frame["frame_id"]
    if task["stack"] and task["stack"][-1] == frame_id: task["stack"].pop()
    context = frame.get("return_context")
    if context and context.get("kind") == "dynamic":
        _sync_dynamic_context(state, context)
    if context and context.get("kind") in {"decorator", "sort-key"}:
        caller = state["frames"][task["stack"][-1]] if task["stack"] else None
        if caller is not None:
            if context["kind"] == "decorator":
                immediate, result = _resume_decorators(state, task, context, _check_value(value))
            else:
                immediate, result = _resume_sort_operation(state, task, context, _check_value(value))
            if immediate and result is not None:
                caller["stack"].append(_plain(result))
        del state["frames"][frame_id]
        return
    if context and context.get("kind") == "async-for-anext":
        if not task["stack"]:
            del state["frames"][frame_id]
            raise RuntimeError("asynchronous iterator completion has no caller")
        caller = state["frames"][task["stack"][-1]]
        awaited, awaited_result = _await_coroutine(
            state,
            task,
            _check_value(value),
            caller_context={
                "kind": "async-for-await",
                "target": int(context["target"]),
                "iterator": _plain(context["iterator"]),
            },
        )
        if awaited:
            caller["stack"].append(_plain(awaited_result))
        del state["frames"][frame_id]
        return
    if context and context.get("kind") == "callable-iterator":
        _callable_iterator_result(
            state,
            task,
            _check_value(context["iterator_ref"]),
            context["consumer"],
            _check_value(context["source_value"]),
            _check_value(value),
        )
        del state["frames"][frame_id]
        return
    if context and context.get("kind") == "attribute-call":
        if task["stack"]:
            state["frames"][task["stack"][-1]]["stack"].append(_plain(value))
        else:
            task["status"] = "completed"
            task["result"] = _plain(value)
            state["phase"] = "completed"
        del state["frames"][frame_id]
        return
    resumable_contexts = {
        "generator",
        "builtin-next",
        "for-iter",
        "builtin-reduce",
        "builtin-collect",
        "async-for",
        "async-for-await",
        "await",
        "asyncio-run",
        "async-with-enter",
        "async-with-exit-normal",
        "async-with-exit-signal",
    }
    if context and context.get("kind") in resumable_contexts:
        generator_ref = _check_value(context["generator_ref"])
        generator_item = _heap_object(state, generator_ref)
        generator_item["payload"]["status"] = "completed"
        generator_item["payload"]["return"] = _plain(value)
        _mutated(generator_item)
        if task["stack"]:
            caller = state["frames"][task["stack"][-1]]
            context_kind = str(context["kind"])
            if context_kind in {"for-iter", "async-for"}:
                if (
                    caller["stack"]
                    and dict(_check_value(caller["stack"][-1])) == dict(generator_ref)
                ):
                    caller["stack"].pop()
                caller["pc"] = int(context["target"])
            elif context_kind == "async-for-await":
                caller["stack"].append(_plain(value))
            elif context_kind == "builtin-reduce":
                operation = str(context["operation"])
                if operation in {"min", "max"} and not bool(context["seen"]):
                    _propagate(
                        state,
                        task,
                        {
                            "kind": "exception",
                            "value": _exception(
                                state,
                                "ValueError",
                                f"{operation}() arg is an empty sequence",
                            ),
                        },
                    )
                else:
                    caller["stack"].append(_plain(context["accumulator"]))
            elif context_kind == "builtin-collect":
                caller["stack"].append(_plain(context["accumulator"]))
            elif context_kind in {"await", "asyncio-run"}:
                caller["stack"].append(_plain(value))
            elif context_kind == "async-with-enter":
                caller["blocks"].append(
                    {
                        "kind": "with",
                        "manager": _plain(context["manager"]),
                        "depth": len(caller["stack"]),
                        "target": int(context["target"]),
                        "asynchronous": True,
                    }
                )
                caller["stack"].append(_plain(value))
            elif context_kind == "async-with-exit-signal":
                if _truth(state, value):
                    caller["pc"] = int(context["target"])
                else:
                    _propagate(state, task, context["signal"])
            elif context_kind == "async-with-exit-normal":
                pass
            elif context.get("default") is not None:
                caller["stack"].append(_plain(context["default"]))
            else:
                _propagate(
                    state,
                    task,
                    {
                        "kind": "exception",
                        "value": _exception(state, "StopIteration", ""),
                    },
                )
        return
    del state["frames"][frame_id]
    if context and context.get("kind") == "yield-from":
        if task["stack"]:
            caller = state["frames"][task["stack"][-1]]
            caller["yield_from"] = None
            caller["pc"] = int(caller["pc"]) + 1
            caller["stack"].append(_plain(value))
        return
    if context and context.get("kind") == "with-enter":
        if task["stack"]:
            caller = state["frames"][task["stack"][-1]]
            caller["blocks"].append(
                {
                    "kind": "with",
                    "manager": _plain(context["manager"]),
                    "depth": len(caller["stack"]),
                    "target": int(context["target"]),
                }
            )
            caller["stack"].append(_plain(value))
            caller["blocks"][-1]["asynchronous"] = False
        return
    if context and context.get("kind") == "with-exit":
        if task["stack"]:
            caller = state["frames"][task["stack"][-1]]
            if _truth(state, value):
                caller["pc"] = int(context["target"])
            else:
                _propagate(state, task, context["signal"])
        return
    if context and context.get("kind") == "gc-callback":
        entry = state["finalizer_queue"][int(context["queue_index"])]
        entry["phase"] = "settled"
        if entry.get("kind") == "finalizer":
            _collect(state)
        if not task["stack"]:
            task["status"] = str(context["restore_status"])
            state["phase"] = str(context["restore_phase"])
        return
    if context and context.get("kind") == "operator":
        if value.get("t") != "not-implemented":
            if task["stack"]:
                state["frames"][task["stack"][-1]]["stack"].append(_plain(value))
            return
        immediate, result = _invoke_operator(
            state,
            task,
            context.get("remaining", []),
            context["fallback"],
        )
        if immediate and task["stack"]:
            state["frames"][task["stack"][-1]]["stack"].append(
                _check_value(result)
            )
        return
    if context and context.get("kind") == "return-override":
        value = _check_value(context["value"])
    elif context and context.get("kind") == "discard-return":
        value = _v_none()
    elif context and context.get("kind") == "import":
        module_ref = _check_value(context["module_ref"]); module_item = _heap_object(state, module_ref); module_item["payload"]["status"] = "ready"; _mutated(module_item); value = module_ref
    elif context and context.get("kind") == "class":
        value = _make_class(
            state,
            str(context["name"]),
            [_check_value(item) for item in context["bases"]],
            _check_value(value),
            {name: _check_value(item) for name, item in context["keywords"].items()},
            type_params=context.get("type_params", []),
        )
    if task["stack"]:
        state["frames"][task["stack"][-1]]["stack"].append(_plain(value))
    else:
        task["status"] = "completed"; task["result"] = _plain(value); task["frame_ref"] = None
        state["phase"] = "completed"; state["result"] = {"schema": RUNTIME_RESULT_SCHEMA, "status": "completed", "task_id": task["task_id"], "value": _project(state, value), "value_ref": _plain(value), "stdout": state["stdout"], "logical_work": state["ledger"]["instructions"]}


def _yield_frame(state: MutableMapping[str, Any], task: MutableMapping[str, Any], frame: MutableMapping[str, Any], value: Mapping[str, Any]) -> None:
    context = frame.get("return_context")
    if not context or "generator_ref" not in context: raise _GuestSignal(_exception(state, "RuntimeError", "yield outside a resumed generator"))
    if task["stack"] and task["stack"][-1] == frame["frame_id"]: task["stack"].pop()
    generator_ref = _check_value(context["generator_ref"])
    item = _heap_object(state, generator_ref)
    item["payload"]["status"] = "suspended"
    item["payload"]["yield_count"] = int(item["payload"]["yield_count"]) + 1
    _mutated(item)
    frame["return_context"] = None
    if not task["stack"]:
        task["status"] = "yielded"
        task["result"] = _plain(value)
        return
    caller = state["frames"][task["stack"][-1]]
    if context.get("kind") == "builtin-reduce":
        operation = str(context["operation"])
        accumulator = _check_value(context["accumulator"])
        seen = bool(context["seen"])
        if operation == "sum":
            accumulator = _binary(state, "add", accumulator, value)
        elif operation in {"min", "max"}:
            if not seen:
                accumulator = value
            else:
                comparison = "lt" if operation == "min" else "gt"
                if _truth(state, _compare(state, comparison, value, accumulator)):
                    accumulator = value
        elif operation == "all":
            accumulator = _v_bool(_truth(state, value))
        elif operation == "any":
            accumulator = _v_bool(_truth(state, value))
        else:
            raise RuntimeError("generator reduction operation is invalid")
        next_context = {
            "kind": "builtin-reduce",
            "operation": operation,
            "accumulator": _plain(accumulator),
            "seen": True,
        }
        if (operation == "all" and not _truth(state, accumulator)) or (
            operation == "any" and _truth(state, accumulator)
        ):
            caller["stack"].append(_plain(accumulator))
            return
        _resume_generator(
            state,
            task,
            generator_ref,
            mode="next",
            value=None,
            caller_context=next_context,
        )
        return
    if context.get("kind") == "builtin-collect":
        accumulator = _check_value(context["accumulator"])
        collection_kind = str(context["collection_kind"])
        _append_collected_value(state, accumulator, collection_kind, value)
        _resume_generator(
            state,
            task,
            generator_ref,
            mode="next",
            value=None,
            caller_context={
                "kind": "builtin-collect",
                "collection_kind": collection_kind,
                "accumulator": _plain(accumulator),
            },
        )
        return
    if context.get("kind") == "yield-from":
        _propagate(
            state,
            task,
            {"kind": "yield", "value": _plain(value)},
        )
        return
    caller["stack"].append(_plain(value))


def _propagate(state: MutableMapping[str, Any], task: MutableMapping[str, Any], signal: Mapping[str, Any]) -> None:
    while task["stack"]:
        frame = state["frames"][task["stack"][-1]]
        blocks = frame["blocks"]
        while blocks:
            block = blocks.pop()
            frame["stack"] = frame["stack"][: int(block["depth"])]
            if block["kind"] == "finally":
                frame["pending_signal"] = _plain(signal); frame["pc"] = int(block["handler"]); return
            if block["kind"] == "with":
                manager = _check_value(block["manager"])
                if signal["kind"] == "exception":
                    exception = _check_value(signal["value"])
                    arguments = [
                        _v_exception_type(_exception_name(state, exception)),
                        exception,
                        _v_none(),
                    ]
                else:
                    arguments = [_v_none(), _v_none(), _v_none()]
                try:
                    asynchronous = bool(block.get("asynchronous", False))
                    exit_kind, exit_value = _get_attr(
                        state,
                        manager,
                        "__aexit__" if asynchronous else "__exit__",
                    )
                    if exit_kind != "value":
                        raise TypeError("context exit descriptor is unsupported")
                    immediate, exit_result = _invoke(
                        state,
                        task,
                        exit_value,
                        arguments,
                        {},
                        return_context={
                            "kind": "with-exit",
                            "signal": _plain(signal),
                            "target": int(block["target"]),
                        },
                    )
                    if not immediate:
                        return
                    checked_result = _check_value(exit_result)
                    if asynchronous:
                        awaited, awaited_result = _await_coroutine(
                            state,
                            task,
                            checked_result,
                            caller_context={
                                "kind": "async-with-exit-signal",
                                "signal": _plain(signal),
                                "target": int(block["target"]),
                            },
                        )
                        if not awaited:
                            return
                        checked_result = _check_value(awaited_result)
                    if _truth(state, checked_result):
                        frame["pc"] = int(block["target"])
                        return
                except _GuestSignal as exc:
                    signal = {"kind": "exception", "value": _plain(exc.exception)}
                continue
            if signal["kind"] == "exception" and block["kind"] == "except-star":
                exception = _check_value(signal["value"])
                frame["exception_star"] = {
                    "remainder": _plain(exception),
                    "raised": [],
                    "end": None,
                }
                frame["pc"] = int(block["handler"])
                return
            if signal["kind"] == "exception" and block["kind"] == "except-star-active":
                context = frame.setdefault(
                    "exception_star",
                    {"remainder": None, "raised": [], "end": int(block["target"])},
                )
                context["raised"].append(_plain(signal["value"]))
                frame["pc"] = int(block["target"])
                return
            if signal["kind"] == "exception" and block["kind"] == "except":
                frame["current_exception"] = _plain(signal["value"]); frame["pc"] = int(block["handler"]); frame["stack"].append(_plain(signal["value"])); return
            if signal["kind"] == "break" and block["kind"] == "loop": frame["pc"] = int(block["break"]); return
            if signal["kind"] == "continue" and block["kind"] == "loop":
                frame["blocks"].append(block); frame["pc"] = int(block["continue"]); return
        if signal["kind"] == "return": _finish_frame(state, task, frame, _check_value(signal["value"])); return
        if signal["kind"] == "yield": _yield_frame(state, task, frame, _check_value(signal["value"])); return
        if signal["kind"] == "exception":
            _trace_exception(state, frame, _check_value(signal["value"]))
            context = frame.get("return_context")
            _sync_dynamic_context(state, context)
            if context and context.get("kind") == "gc-callback":
                entry = state["finalizer_queue"][int(context["queue_index"])]
                entry["phase"] = "failed"
                entry["exception"] = _project(state, _check_value(signal["value"]))
                task["stack"].pop()
                if frame["frame_id"] in state["frames"]:
                    del state["frames"][frame["frame_id"]]
                if not task["stack"]:
                    task["status"] = str(context["restore_status"])
                    state["phase"] = str(context["restore_phase"])
                return
            iterator_stop = (
                context
                and context.get("kind") == "for-iter"
                and _exception_matches(
                    state,
                    _check_value(signal["value"]),
                    _v_exception_type("StopIteration"),
                )
            )
            async_iterator_stop = (
                context
                and context.get("kind") == "async-for-await"
                and _exception_matches(
                    state,
                    _check_value(signal["value"]),
                    _v_exception_type("StopAsyncIteration"),
                )
            )
            if iterator_stop or async_iterator_stop:
                generator_ref = _check_value(context["generator_ref"])
                gen = _heap_object(state, generator_ref)
                gen["payload"]["status"] = "completed"
                _mutated(gen)
                task["stack"].pop()
                caller = state["frames"][task["stack"][-1]]
                iterator_ref = (
                    _check_value(context["iterator"])
                    if async_iterator_stop
                    else generator_ref
                )
                if (
                    caller["stack"]
                    and dict(_check_value(caller["stack"][-1])) == dict(iterator_ref)
                ):
                    caller["stack"].pop()
                caller["pc"] = int(context["target"])
                return
            task["stack"].pop()
            if frame["frame_id"] in state["frames"]:
                del state["frames"][frame["frame_id"]]
            continue
        if signal["kind"] in {"break", "continue"}: signal = {"kind": "exception", "value": _exception(state, "SyntaxError", f"'{signal['kind']}' outside loop")}; continue
    if signal["kind"] == "exception":
        task["status"] = "faulted"; task["exception"] = _plain(signal["value"]); state["phase"] = "faulted"; state["result"] = {"schema": RUNTIME_RESULT_SCHEMA, "status": "faulted", "task_id": task["task_id"], "exception": _project(state, _check_value(signal["value"])), "stdout": state["stdout"], "logical_work": state["ledger"]["instructions"]}


def _resume_pending_signal(state: MutableMapping[str, Any], task: MutableMapping[str, Any], frame: MutableMapping[str, Any]) -> bool:
    # ``pending_signal`` belongs to an active finally suite and is consumed by
    # END_FINALLY.  Only an explicitly injected generator signal fires before
    # the next opcode.
    signal = frame.pop("resume_signal", None)
    if signal is None:
        return False
    _propagate(state, task, signal)
    return True


def _resolve_pattern_name(
    state: MutableMapping[str, Any],
    frame: Mapping[str, Any],
    dotted_name: str,
) -> Mapping[str, Any]:
    parts = dotted_name.split(".")
    value = _name_load(state, frame, parts[0])
    for part in parts[1:]:
        kind, found = _get_attr(state, value, part)
        if kind != "value":
            raise TypeError("suspending descriptors are unavailable in patterns")
        value = _check_value(found)
    return value


def _match_pattern(
    state: MutableMapping[str, Any],
    frame: Mapping[str, Any],
    subject: Mapping[str, Any],
    pattern: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    kind = pattern.get("kind")
    bindings: dict[str, Mapping[str, Any]] = {}
    if kind in {"singleton", "value"}:
        expected = _constant_value(state, pattern["value"])
        return (
            _alloc(state, "dict", {"entries": []})
            if _value_equal(state, subject, expected)
            else None
        )
    if kind == "value-name":
        expected = _resolve_pattern_name(state, frame, str(pattern["name"]))
        return (
            _alloc(state, "dict", {"entries": []})
            if _value_equal(state, subject, expected)
            else None
        )
    if kind == "as":
        if pattern.get("pattern") is not None:
            nested = _match_pattern(state, frame, subject, pattern["pattern"])
            if nested is None:
                return None
            bindings.update(
                {
                    _as_str(key): value
                    for key, value in _heap_object(state, nested)["payload"]["entries"]
                }
            )
        if pattern.get("name"):
            bindings[str(pattern["name"])] = subject
    elif kind == "or":
        for candidate in pattern["patterns"]:
            result = _match_pattern(state, frame, subject, candidate)
            if result is not None:
                return result
        return None
    elif kind == "sequence":
        try:
            values = _iter_values(state, subject)
        except TypeError:
            return None
        patterns = pattern["patterns"]
        stars = [
            index
            for index, item in enumerate(patterns)
            if item.get("kind") == "star"
        ]
        if not stars and len(values) != len(patterns):
            return None
        if stars and len(values) < len(patterns) - 1:
            return None
        expanded: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
        if stars:
            star = stars[0]
            tail = len(patterns) - star - 1
            for index, child in enumerate(patterns):
                if index < star:
                    expanded.append((child, values[index]))
                elif index == star:
                    if child.get("name"):
                        bindings[str(child["name"])] = _alloc(
                            state,
                            "list",
                            {"items": values[star : len(values) - tail]},
                        )
                else:
                    expanded.append(
                        (child, values[len(values) - tail + (index - star - 1)])
                    )
        else:
            expanded = list(zip(patterns, values))
        for child, value in expanded:
            result = _match_pattern(state, frame, value, child)
            if result is None:
                return None
            bindings.update(
                {
                    _as_str(key): member
                    for key, member in _heap_object(state, result)["payload"]["entries"]
                }
            )
    elif kind == "mapping":
        if (
            subject.get("t") != "ref"
            or _heap_object(state, subject)["kind"] != "dict"
        ):
            return None
        item = _heap_object(state, subject)
        used: set[int] = set()
        for key_record, child in zip(pattern["keys"], pattern["patterns"]):
            if "kind" in key_record:
                key = _constant_value(state, key_record)
            elif "name" in key_record:
                key = _resolve_pattern_name(state, frame, str(key_record["name"]))
            else:
                return None
            index = _dict_find(state, item, key)
            if index is None:
                return None
            used.add(index)
            result = _match_pattern(
                state,
                frame,
                _check_value(item["payload"]["entries"][index][1]),
                child,
            )
            if result is None:
                return None
            bindings.update(
                {
                    _as_str(key): value
                    for key, value in _heap_object(state, result)["payload"]["entries"]
                }
            )
        if pattern.get("rest"):
            bindings[str(pattern["rest"])] = _alloc(
                state,
                "dict",
                {
                    "entries": [
                        copy.deepcopy(pair)
                        for index, pair in enumerate(item["payload"]["entries"])
                        if index not in used
                    ]
                },
            )
    elif kind == "class":
        target_class = _resolve_pattern_name(
            state,
            frame,
            str(pattern["class_name"]),
        )
        subject_class = _instance_class(state, subject)
        if (
            target_class.get("t") != "ref"
            or _heap_object(state, target_class)["kind"] != "class"
            or subject_class is None
            or not any(
                dict(candidate) == dict(target_class)
                for candidate in _class_mro(state, subject_class)
            )
        ):
            return None
        positional_names: list[str] = []
        if pattern["patterns"]:
            match_args = _lookup_class_attr(state, target_class, "__match_args__")
            if match_args is None:
                raise TypeError(
                    f"{_heap_object(state, target_class)['payload']['name']} accepts 0 positional sub-patterns"
                )
            match_values = _iter_values(state, match_args)
            positional_names = [_as_str(value) for value in match_values]
            if len(pattern["patterns"]) > len(positional_names):
                raise TypeError("too many positional sub-patterns")
        names = [
            *positional_names[: len(pattern["patterns"])],
            *[str(name) for name in pattern["keyword_names"]],
        ]
        children = [
            *pattern["patterns"],
            *pattern["keyword_patterns"],
        ]
        if len(set(names)) != len(names):
            raise TypeError("class pattern repeats an attribute")
        for name, child in zip(names, children):
            try:
                attr_kind, attr = _get_attr(state, subject, name)
            except AttributeError:
                return None
            if attr_kind != "value":
                raise TypeError("suspending descriptors are unavailable in patterns")
            result = _match_pattern(state, frame, _check_value(attr), child)
            if result is None:
                return None
            bindings.update(
                {
                    _as_str(key): value
                    for key, value in _heap_object(state, result)["payload"]["entries"]
                }
            )
    else:
        return None
    return _alloc(
        state,
        "dict",
        {
            "entries": [
                [_v_str(name), value]
                for name, value in bindings.items()
            ]
        },
    )


def _execute_instruction(state: MutableMapping[str, Any], task: MutableMapping[str, Any], frame: MutableMapping[str, Any], instruction: Mapping[str, Any]) -> None:
    op = instruction["op"]; arg = instruction.get("arg"); stack = frame["stack"]
    frame["last_span"] = instruction.get("span")
    if op == "NOP": return
    if op == "LOAD_CONST": stack.append(_constant_value(state, arg))
    elif op == "LOAD_NAME": stack.append(_name_load(state, frame, str(arg)))
    elif op == "STORE_NAME": _name_store(state, frame, str(arg), _check_value(stack.pop()))
    elif op == "DELETE_NAME": _name_delete(state, frame, str(arg))
    elif op == "DELETE_NAME_IF_PRESENT": _name_delete(state, frame, str(arg), missing_ok=True)
    elif op == "LOAD_LOCALS": stack.append(_check_value(frame["locals"]))
    elif op == "POP_TOP": stack.pop()
    elif op == "DUP_TOP": stack.append(copy.deepcopy(stack[-1]))
    elif op == "DUP_PAIR": stack.extend(copy.deepcopy(stack[-2:]))
    elif op in {"BINARY", "INPLACE"}:
        right = _check_value(stack.pop())
        left = _check_value(stack.pop())
        inplace = op == "INPLACE"
        candidates = _operator_candidates(
            state,
            str(arg),
            left,
            right,
            inplace=inplace,
        )
        if candidates:
            immediate, result = _invoke_operator(
                state,
                task,
                candidates,
                {
                    "kind": "binary",
                    "operation": str(arg),
                    "left": _plain(left),
                    "right": _plain(right),
                    "inplace": inplace,
                },
            )
            if immediate:
                stack.append(_check_value(result))
        else:
            stack.append(_binary(state, str(arg), left, right, inplace=inplace))
    elif op == "UNARY":
        value = _check_value(stack.pop())
        candidates = _operator_candidates(state, str(arg), value)
        if candidates:
            immediate, result = _invoke_operator(
                state,
                task,
                candidates,
                {
                    "kind": "unary",
                    "operation": str(arg),
                    "left": _plain(value),
                },
            )
            if immediate:
                stack.append(_check_value(result))
        else:
            stack.append(_unary(state, str(arg), value))
    elif op == "COMPARE":
        right = _check_value(stack.pop())
        left = _check_value(stack.pop())
        candidates = _operator_candidates(
            state,
            str(arg),
            left,
            right,
            comparison=True,
        )
        if candidates:
            immediate, result = _invoke_operator(
                state,
                task,
                candidates,
                {
                    "kind": "compare",
                    "operation": str(arg),
                    "left": _plain(left),
                    "right": _plain(right),
                },
            )
            if immediate:
                stack.append(_check_value(result))
        else:
            stack.append(_compare(state, str(arg), left, right))
    elif op == "COMPARE_CHAIN":
        right = _check_value(stack.pop())
        left = _check_value(stack.pop())
        stack.extend([right, _compare(state, str(arg), left, right)])
    elif op == "CHAIN_GUARD":
        result = _check_value(stack.pop())
        if not _truth(state, result):
            stack.pop()
            stack.append(result)
            frame["pc"] = int(arg)
    elif op == "JUMP": frame["pc"] = int(arg)
    elif op == "JUMP_IF_FALSE":
        if not _truth(state, _check_value(stack.pop())): frame["pc"] = int(arg)
    elif op == "JUMP_IF_TRUE":
        if _truth(state, _check_value(stack.pop())): frame["pc"] = int(arg)
    elif op == "JUMP_IF_NONE":
        if _check_value(stack[-1]).get("t") == "none":
            stack.pop()
            frame["pc"] = int(arg)
    elif op == "JUMP_IF_FALSE_OR_POP":
        if not _truth(state, _check_value(stack[-1])): frame["pc"] = int(arg)
        else: stack.pop()
    elif op == "JUMP_IF_TRUE_OR_POP":
        if _truth(state, _check_value(stack[-1])): frame["pc"] = int(arg)
        else: stack.pop()
    elif op == "BUILD_COLLECTION":
        descriptors = arg["items"]
        values = [_check_value(stack.pop()) for _ in descriptors][::-1]
        items: list[Mapping[str, Any]] = []
        for descriptor, value in zip(descriptors, values):
            items.extend(
                _iter_values(state, value) if descriptor == "star" else [value]
            )
        kind = arg["kind"]
        if kind == "dict":
            stack.append(_alloc(state, "dict", {"entries": []}))
        elif kind in {"set", "frozenset"}:
            unique: list[Mapping[str, Any]] = []
            for value in items:
                if not any(_value_equal(state, value, old) for old in unique):
                    unique.append(value)
            stack.append(_alloc(state, kind, {"items": unique}))
        else:
            stack.append(_alloc(state, kind, {"items": items}))
    elif op == "BUILD_MAP":
        descriptors = list(arg); count = sum(1 if kind == "mapping" else 2 for kind in descriptors); values = [_check_value(stack.pop()) for _ in range(count)][::-1]; cursor = 0; result = _alloc(state, "dict", {"entries": []})
        for descriptor in descriptors:
            if descriptor == "mapping":
                source = _heap_object(state, values[cursor]); cursor += 1
                if source["kind"] != "dict": raise TypeError("dictionary unpacking requires mapping")
                for key, value in source["payload"]["entries"]: _dict_set(state, result, key, value)
            else:
                _dict_set(state, result, values[cursor], values[cursor + 1]); cursor += 2
        stack.append(result)
    elif op == "MAP_SET": value, key, mapping = _check_value(stack.pop()), _check_value(stack.pop()), _check_value(stack.pop()); _dict_set(state, mapping, key, value)
    elif op == "COLLECTION_ADD":
        value, collection = _check_value(stack.pop()), _check_value(stack.pop())
        item = _heap_object(state, collection)
        if item["kind"] not in {"list", "set"}:
            raise TypeError("invalid comprehension collection")
        _append_collected_value(state, collection, item["kind"], value)
    elif op == "BUILD_SLICE": parts = [_check_value(stack.pop()) for _ in range(int(arg))][::-1]; stack.append(_alloc(state, "slice", {"parts": parts}))
    elif op == "LOAD_SUBSCR": key, container = _check_value(stack.pop()), _check_value(stack.pop()); stack.append(_get_item(state, container, key))
    elif op == "STORE_SUBSCR": key, container, value = _check_value(stack.pop()), _check_value(stack.pop()), _check_value(stack.pop()); _store_item(state, container, key, value)
    elif op == "STORE_SUBSCR_AUG":
        value = _check_value(stack.pop())
        key = _check_value(stack.pop())
        container = _check_value(stack.pop())
        _store_item(state, container, key, value)
    elif op == "DELETE_SUBSCR": key, container = _check_value(stack.pop()), _check_value(stack.pop()); _delete_item(state, container, key)
    elif op == "LOAD_ATTR":
        target = _check_value(stack.pop()); result_kind, result = _get_attr(state, target, str(arg))
        if result_kind == "value": stack.append(result)
        else:
            callable_value, positional, keywords = result
            immediate, value = _invoke(
                state,
                task,
                callable_value,
                positional,
                keywords,
                return_context={"kind": "attribute-call"},
            )
            if immediate: stack.append(_check_value(value))
    elif op == "STORE_ATTR":
        target, value = _check_value(stack.pop()), _check_value(stack.pop()); pending = _store_attr(state, target, str(arg), value)
        if pending is not None:
            _, (callable_value, positional, keywords) = pending; immediate, _ = _invoke(state, task, callable_value, positional, keywords, return_context={"kind": "discard-return"})
            if immediate: pass
    elif op == "STORE_ATTR_AUG":
        value = _check_value(stack.pop())
        target = _check_value(stack.pop())
        pending = _store_attr(state, target, str(arg), value)
        if pending is not None:
            _, (callable_value, positional, keywords) = pending
            _invoke(
                state,
                task,
                callable_value,
                positional,
                keywords,
                return_context={"kind": "discard-return"},
            )
    elif op == "DELETE_ATTR":
        pending = _delete_attr(state, _check_value(stack.pop()), str(arg))
        if pending is not None:
            _, (callable_value, positional, keywords) = pending
            _invoke(
                state,
                task,
                callable_value,
                positional,
                keywords,
                return_context={"kind": "discard-return"},
            )
    elif op == "UNPACK":
        values = _iter_values(state, _check_value(stack.pop())); count = int(arg["count"]); star = arg["star"]
        if star is None:
            if len(values) != count: raise ValueError(f"not enough values to unpack (expected {count}, got {len(values)})")
            unpacked = values
        else:
            minimum = count - 1
            if len(values) < minimum: raise ValueError(f"not enough values to unpack (expected at least {minimum}, got {len(values)})")
            tail = count - int(star) - 1; unpacked = values[: int(star)] + [_alloc(state, "list", {"items": values[int(star): len(values)-tail]})] + (values[len(values)-tail:] if tail else [])
        stack.extend(copy.deepcopy(unpacked))
    elif op == "GET_ITER":
        stack[-1] = _make_iterator(state, _check_value(stack[-1]))
    elif op == "GET_AITER":
        target = _check_value(stack.pop())
        if (
            target.get("t") == "ref"
            and _heap_object(state, target)["kind"] == "async-generator"
        ):
            stack.append(target)
        else:
            kind, aiter = _get_attr(state, target, "__aiter__")
            if kind != "value":
                raise TypeError("asynchronous iterator descriptor is unsupported")
            immediate, result = _invoke(state, task, aiter, [], {})
            if not immediate:
                return
            iterator = _check_value(result)
            if (
                iterator.get("t") != "ref"
                or _heap_object(state, iterator)["kind"]
                not in {"instance", "async-generator"}
            ):
                raise TypeError("__aiter__ returned a non-asynchronous iterator")
            stack.append(iterator)
    elif op == "FOR_ITER":
        iterator = _check_value(stack[-1])
        if (
            iterator.get("t") == "ref"
            and _heap_object(state, iterator)["kind"] in {"generator", "map", "filter"}
        ):
            if _heap_object(state, iterator)["kind"] in {"map", "filter"}:
                _resume_callable_iterator(
                    state,
                    task,
                    iterator,
                    {"mode": "for", "target": int(arg)},
                )
            else:
                _resume_generator(
                    state,
                    task,
                    iterator,
                    mode="next",
                    value=None,
                    caller_context={"kind": "for-iter", "target": int(arg)},
                )
        else:
            value = _iterator_next(state, iterator)
            if value is None:
                stack.pop()
                frame["pc"] = int(arg)
            else:
                stack.append(value)
    elif op == "ASYNC_FOR_ITER":
        iterator = _check_value(stack[-1])
        if (
            iterator.get("t") == "ref"
            and _heap_object(state, iterator)["kind"] == "async-generator"
        ):
            _resume_generator(
                state,
                task,
                iterator,
                mode="next",
                value=None,
                caller_context={"kind": "async-for", "target": int(arg)},
            )
        else:
            kind, anext = _get_attr(state, iterator, "__anext__")
            if kind != "value":
                raise TypeError("asynchronous next descriptor is unsupported")
            immediate, result = _invoke(
                state,
                task,
                anext,
                [],
                {},
                return_context={
                    "kind": "async-for-anext",
                    "target": int(arg),
                    "iterator": _plain(iterator),
                },
            )
            if not immediate:
                return
            awaited, awaited_result = _await_coroutine(
                state,
                task,
                _check_value(result),
                caller_context={
                    "kind": "async-for-await",
                    "target": int(arg),
                    "iterator": _plain(iterator),
                },
            )
            if awaited:
                stack.append(_check_value(awaited_result))
    elif op == "SETUP_LOOP": frame["blocks"].append({"kind": "loop", "break": int(arg["break"]), "continue": int(arg["continue"]), "depth": len(stack)})
    elif op == "SETUP_EXCEPT": frame["blocks"].append({"kind": "except", "handler": int(arg), "depth": len(stack)})
    elif op == "SETUP_EXCEPT_STAR":
        frame["blocks"].append({"kind": "except-star", "handler": int(arg), "depth": len(stack)})
    elif op == "EXCEPT_STAR_BEGIN":
        context = frame.get("exception_star")
        if not isinstance(context, MutableMapping):
            raise RuntimeError("except* handler has no exception group")
        if context.get("end") is None:
            code = _frame_code(state, frame)
            for index in range(int(frame["pc"]), len(code["instructions"])):
                instruction = code["instructions"][index]
                if instruction.get("op") == "EXCEPT_STAR_END":
                    context["end"] = index
                    break
        if context.get("end") is None:
            raise RuntimeError("except* handler has no end")
        frame["blocks"].append(
            {
                "kind": "except-star-active",
                "depth": len(stack),
                "target": int(context["end"]),
            }
        )
    elif op == "EXCEPT_STAR_SPLIT":
        context = frame.get("exception_star")
        if not isinstance(context, MutableMapping):
            raise RuntimeError("except* split has no active group")
        target = _check_value(stack.pop())
        remainder = context.get("remainder")
        matched, residual = (
            (None, None)
            if remainder is None
            else _split_exception_group(state, _check_value(remainder), target)
        )
        context["remainder"] = None if residual is None else _plain(residual)
        frame["current_exception"] = None if matched is None else _plain(matched)
        stack.append(_v_bool(matched is not None))
    elif op == "POP_EXCEPT_STAR_CLAUSE":
        frame["current_exception"] = None
    elif op == "EXCEPT_STAR_END":
        context = frame.pop("exception_star", None)
        if frame["blocks"] and frame["blocks"][-1]["kind"] == "except-star-active":
            frame["blocks"].pop()
        if isinstance(context, Mapping):
            pending = []
            if context.get("remainder") is not None:
                pending.append(_check_value(context["remainder"]))
            pending.extend(_check_value(value) for value in context.get("raised", []))
            merged = _exception_group(state, pending)
            if merged is not None:
                _propagate(state, task, {"kind": "exception", "value": merged})
            else:
                frame["pc"] = int(arg["target"])
    elif op == "SETUP_FINALLY": frame["blocks"].append({"kind": "finally", "handler": int(arg), "depth": len(stack)})
    elif op == "POP_BLOCK": frame["blocks"].pop()
    elif op == "ENTER_FINALLY": frame["pending_signal"] = {"kind": "normal", "target": int(arg["target"])}
    elif op == "END_FINALLY":
        signal = frame.get("pending_signal"); frame["pending_signal"] = None
        if signal and signal["kind"] == "normal": frame["pc"] = int(signal["target"])
        elif signal: _propagate(state, task, signal)
    elif op == "LOAD_CURRENT_EXCEPTION": stack.append(_check_value(frame["current_exception"]))
    elif op == "EXCEPTION_MATCH": target, exception = _check_value(stack.pop()), _check_value(stack.pop()); stack.append(_v_bool(_exception_matches(state, exception, target)))
    elif op == "POP_EXCEPT": frame["current_exception"] = None
    elif op == "RAISE":
        value = _check_value(stack.pop())
        if value.get("t") == "exception-type": value = _exception(state, str(value["v"]), "")
        elif value.get("t") != "ref" or _heap_object(state, value)["kind"] != "exception": raise TypeError("exceptions must derive from BaseException")
        _propagate(state, task, {"kind": "exception", "value": value})
    elif op == "RAISE_FROM": cause, value = _check_value(stack.pop()), _check_value(stack.pop()); exception = _exception(state, _exception_name(state, value), _heap_object(state, value)["payload"].get("message", ""), cause=cause, value=value); _propagate(state, task, {"kind": "exception", "value": exception})
    elif op == "RERAISE":
        if frame["current_exception"] is None: raise RuntimeError("No active exception to reraise")
        _propagate(state, task, {"kind": "exception", "value": _check_value(frame["current_exception"])})
    elif op == "RAISE_ASSERTION": value = _check_value(stack.pop()); _propagate(state, task, {"kind": "exception", "value": _exception(state, "AssertionError", _as_str(value) if value.get("t") == "str" else _repr_value(state, value))})
    elif op == "SIGNAL_BREAK": _propagate(state, task, {"kind": "break"})
    elif op == "SIGNAL_CONTINUE": _propagate(state, task, {"kind": "continue"})
    elif op == "RETURN": _propagate(state, task, {"kind": "return", "value": _check_value(stack.pop())})
    elif op == "YIELD": _propagate(state, task, {"kind": "yield", "value": _check_value(stack.pop())})
    elif op == "YIELD_FROM":
        iterator_value = frame.get("yield_from")
        sent = None
        if iterator_value is None:
            iterator = _make_iterator(state, _check_value(stack.pop()))
            frame["yield_from"] = _plain(iterator)
        else:
            iterator = _check_value(iterator_value)
            if stack:
                sent = _check_value(stack.pop())
        if (
            iterator.get("t") == "ref"
            and _heap_object(state, iterator)["kind"] in {"generator", "coroutine"}
        ):
            frame["pc"] -= 1
            _resume_generator(
                state,
                task,
                iterator,
                mode="next" if sent is None or sent.get("t") == "none" else "send",
                value=sent,
                caller_context={"kind": "yield-from"},
            )
        else:
            if sent is not None and sent.get("t") != "none":
                raise AttributeError("iterator has no attribute 'send'")
            value = _iterator_next(state, iterator)
            if value is None:
                frame["yield_from"] = None
                stack.append(_v_none())
            else:
                frame["pc"] -= 1
                _propagate(state, task, {"kind": "yield", "value": value})
    elif op == "AWAIT":
        awaitable = _check_value(stack.pop())
        awaited, result = _await_coroutine(
            state,
            task,
            awaitable,
            caller_context={"kind": "await"},
        )
        if awaited:
            stack.append(_check_value(result))
    elif op == "BIND_TYPE_PARAMS":
        _bind_type_params(state, frame, list(arg))
    elif op == "UNBIND_TYPE_PARAMS":
        _unbind_type_params(state, frame, int(arg))
    elif op == "MAKE_FUNCTION":
        kw_names = list(arg["kw_default_names"])
        kw_values = [_check_value(stack.pop()) for _ in kw_names][::-1]
        defaults = [
            _check_value(stack.pop())
            for _ in range(int(arg["defaults"]))
        ][::-1]
        annotation_names = list(arg.get("annotation_names", []))
        annotation_values = [
            _check_value(stack.pop())
            for _ in annotation_names
        ][::-1]
        annotations = _alloc(
            state,
            "dict",
            {
                "entries": [
                    [_v_str(str(name)), value]
                    for name, value in zip(annotation_names, annotation_values)
                ]
            },
        )
        type_params = copy.deepcopy(list(arg.get("type_params", [])))
        closure = _check_value(frame["locals"])
        if type_params:
            closure = _env(state, closure, "function")
            for descriptor in type_params:
                name = str(descriptor.get("name", ""))
                ref = frame.get("type_param_refs", {}).get(name)
                if ref is not None:
                    _env_set(state, closure, name, _check_value(ref))
        function = _alloc(
            state,
            "function",
            {
                "program_id": frame["program_id"],
                "code_id": arg["code_id"],
                "name": arg["name"],
                "qualname": _frame_code(
                    state,
                    {**frame, "code_id": arg["code_id"]},
                )["qualname"],
                "defaults": defaults,
                "kw_defaults": dict(zip(kw_names, kw_values)),
                "annotations": annotations,
                "type_params": type_params,
                "closure": closure,
                "globals": frame["globals"],
                "builtins": frame["builtins"],
            },
            type_name="function",
        )
        stack.append(function)
    elif op == "APPLY_DECORATORS":
        function = _check_value(stack.pop())
        decorators = [_check_value(stack.pop()) for _ in range(int(arg))][::-1]
        immediate, result = _start_decorators(state, task, function, decorators)
        if immediate:
            stack.append(_check_value(result))
    elif op == "MAKE_CLASS":
        keyword_names = list(arg["keyword_names"]); keyword_values = [_check_value(stack.pop()) for _ in keyword_names][::-1]; bases = [_check_value(stack.pop()) for _ in range(int(arg["bases"]))][::-1]
        namespace = _env(state, _check_value(frame["globals"]), "class")
        _env_set(state, namespace, "__annotations__", _alloc(state, "dict", {"entries": []}))
        for descriptor in arg.get("type_params", []):
            name = str(descriptor.get("name", ""))
            ref = frame.get("type_param_refs", {}).get(name)
            if ref is not None:
                _env_set(state, namespace, name, _check_value(ref))
        child = _new_frame(
            state,
            program_id=frame["program_id"],
            code_id=arg["code_id"],
            locals_ref=namespace,
            globals_ref=_check_value(frame["globals"]),
            builtins_ref=_check_value(frame["builtins"]),
            return_context={
                "kind": "class",
                "name": arg["name"],
                "bases": bases,
                "keywords": {
                    str(name): value
                    for name, value in zip(keyword_names, keyword_values)
                    if name is not None
                },
                "type_params": copy.deepcopy(list(arg.get("type_params", []))),
            },
        )
        task["stack"].append(child)
    elif op == "CALL":
        descriptors = list(arg); values = [_check_value(stack.pop()) for _ in descriptors][::-1]; callable_value = _check_value(stack.pop()); positional: list[Mapping[str, Any]] = []; keywords: dict[str, Mapping[str, Any]] = {}
        for descriptor, value in zip(descriptors, values):
            if descriptor["kind"] == "positional": positional.append(value)
            elif descriptor["kind"] == "star": positional.extend(_iter_values(state, value))
            elif descriptor["kind"] == "keyword":
                name = str(descriptor["name"])
                if name in keywords: raise TypeError(f"got multiple values for keyword argument {name!r}")
                keywords[name] = value
            else:
                mapping = _heap_object(state, value)
                if mapping["kind"] != "dict": raise TypeError("keyword unpacking requires mapping")
                for key, member in mapping["payload"]["entries"]:
                    name = _as_str(key)
                    if name in keywords: raise TypeError(f"got multiple values for keyword argument {name!r}")
                    keywords[name] = member
        if callable_value.get("t") == "builtin" and str(callable_value["v"]) == "asyncio.run":
            if len(positional) != 1 or keywords:
                raise TypeError("asyncio.run() requires one coroutine")
            immediate, result = _await_coroutine(
                state,
                task,
                positional[0],
                caller_context={"kind": "asyncio-run"},
            )
        elif callable_value.get("t") == "builtin" and "." in str(callable_value["v"]):
            immediate, result = True, _call_library_builtin(
                state,
                str(callable_value["v"]),
                positional,
                keywords,
            )
        else:
            immediate, result = _invoke(
                state,
                task,
                callable_value,
                positional,
                keywords,
            )
        if immediate and result is not None and result.get("t") != "deferred":
            stack.append(_check_value(result))
    elif op == "IMPORT_NAME":
        immediate, module = _dynamic_import(state, task, frame, arg)
        if immediate: stack.append(_check_value(module))
    elif op == "IMPORT_FROM":
        module = _check_value(stack[-1]); kind, result = _get_attr(state, module, str(arg))
        if kind != "value": raise ImportError("suspending import descriptors are unsupported")
        stack.append(result)
    elif op == "IMPORT_STAR":
        module = _heap_object(state, _check_value(stack[-1])); namespace = _env_values(state, _check_value(module["payload"]["namespace"]))
        for name, value in namespace.items():
            if not name.startswith("_"): _name_store(state, frame, name, value)
    elif op == "FORMAT_VALUE":
        spec = _as_str(_check_value(stack.pop())) if arg["has_spec"] else ""; value = _check_value(stack.pop()); conversion = int(arg["conversion"])
        host = _repr_value(state, value) if conversion == 114 else _as_str(value) if conversion == 115 and value.get("t") == "str" else _repr_value(state, value) if conversion == 97 else _to_host(state, value)
        stack.append(_v_str(format(host, spec)))
    elif op == "BUILD_STRING": parts = [_check_value(stack.pop()) for _ in range(int(arg))][::-1]; stack.append(_v_str("".join(_as_str(value) for value in parts)))
    elif op == "MATCH_PATTERN":
        result = _match_pattern(
            state,
            frame,
            _check_value(stack.pop()),
            arg,
        )
        stack.append(_v_none() if result is None else result)
    elif op == "BIND_MATCH":
        mapping = _heap_object(state, _check_value(stack.pop()))
        for key, value in mapping["payload"]["entries"]: _name_store(state, frame, _as_str(key), value)
    elif op in {"WITH_ENTER", "WITH_ENTER_ASYNC"}:
        asynchronous = op.endswith("ASYNC")
        manager = _check_value(stack.pop())
        kind, enter = _get_attr(
            state,
            manager,
            "__aenter__" if asynchronous else "__enter__",
        )
        if kind != "value":
            raise TypeError("context entry descriptor is unsupported")
        immediate, result = _invoke(
            state,
            task,
            enter,
            [],
            {},
            return_context={
                "kind": "with-enter",
                "manager": _plain(manager),
                "target": int(arg["target"]),
            },
        )
        if immediate:
            entered = _check_value(result)
            if asynchronous:
                awaited, awaited_result = _await_coroutine(
                    state,
                    task,
                    entered,
                    caller_context={
                        "kind": "async-with-enter",
                        "manager": _plain(manager),
                        "target": int(arg["target"]),
                    },
                )
                if not awaited:
                    return
                entered = _check_value(awaited_result)
            frame["blocks"].append(
                {
                    "kind": "with",
                    "manager": _plain(manager),
                    "depth": len(stack),
                    "target": int(arg["target"]),
                    "asynchronous": asynchronous,
                }
            )
            stack.append(entered)
    elif op in {"WITH_EXIT_NORMAL", "WITH_EXIT_NORMAL_ASYNC"}:
        asynchronous = op.endswith("ASYNC")
        block = frame["blocks"].pop()
        manager = _check_value(block["manager"])
        kind, exit_value = _get_attr(
            state,
            manager,
            "__aexit__" if asynchronous else "__exit__",
        )
        if kind != "value":
            raise TypeError("context exit descriptor is unsupported")
        immediate, result = _invoke(
            state,
            task,
            exit_value,
            [_v_none(), _v_none(), _v_none()],
            {},
            return_context={"kind": "discard-return"},
        )
        if immediate and asynchronous:
            awaited, _ = _await_coroutine(
                state,
                task,
                _check_value(result),
                caller_context={"kind": "async-with-exit-normal"},
            )
            if not awaited:
                return
    else: raise RuntimeError(f"unknown field instruction {op}")


def _advance_finalizer_queue(
    state: MutableMapping[str, Any],
    task: MutableMapping[str, Any],
) -> bool:
    if any(
        isinstance(entry, Mapping) and entry.get("phase") == "running"
        for entry in state["finalizer_queue"]
    ):
        return False
    for index, raw_entry in enumerate(state["finalizer_queue"]):
        if isinstance(raw_entry, str):
            entry: MutableMapping[str, Any] = {
                "kind": "finalizer",
                "object_id": raw_entry,
                "phase": "queued",
            }
            state["finalizer_queue"][index] = entry
        elif isinstance(raw_entry, MutableMapping):
            entry = raw_entry
        else:
            raise RuntimeError("finalizer queue entry is invalid")
        if entry.get("phase") != "queued":
            continue
        callable_value: Mapping[str, Any] | None = None
        positional: list[Mapping[str, Any]] = []
        if entry.get("kind") == "finalizer":
            object_id = str(entry.get("object_id"))
            item = state["heap"].get(object_id)
            if item is None:
                entry["phase"] = "settled"
                continue
            target = _v_ref(object_id, int(item["generation"]))
            class_ref = _instance_class(state, target)
            finalizer = None if class_ref is None else _lookup_class_attr(state, class_ref, "__del__")
            if finalizer is None:
                entry["phase"] = "settled"
                continue
            callable_value = {"t": "bound", "func": _plain(finalizer), "self": target}
        elif entry.get("kind") == "weakref-callback":
            callback = entry.get("callback")
            weakref_id = str(entry.get("weakref_id"))
            weakref_item = state["heap"].get(weakref_id)
            if callback is None or weakref_item is None:
                entry["phase"] = "settled"
                continue
            callable_value = _check_value(callback)
            positional = [_v_ref(weakref_id, int(weakref_item["generation"]))]
        else:
            raise RuntimeError("finalizer queue kind is invalid")
        restore_status = str(task["status"])
        restore_phase = str(state["phase"])
        task["status"] = "running"
        state["phase"] = "running"
        entry["phase"] = "running"
        immediate, _ = _invoke(
            state,
            task,
            callable_value,
            positional,
            {},
            return_context={
                "kind": "gc-callback",
                "queue_index": index,
                "restore_status": restore_status,
                "restore_phase": restore_phase,
            },
        )
        if immediate:
            entry["phase"] = "settled"
            if entry.get("kind") == "finalizer":
                _collect(state)
            if not task["stack"]:
                task["status"] = restore_status
                state["phase"] = restore_phase
        return True
    return False


def _optimizer_history(
    state: MutableMapping[str, Any],
    kind: str,
    payload: Mapping[str, Any],
) -> None:
    optimizer = state["optimizer"]
    history = optimizer["history"]
    if len(history) >= _limit(state, "max_events"):
        del history[0]
    history.append(
        {
            "sequence": int(optimizer["ledger"]["events"]),
            "kind": kind,
            "logical_instruction": int(state["ledger"]["instructions"]),
            "payload": _plain(payload),
        }
    )
    optimizer["ledger"]["events"] = int(optimizer["ledger"]["events"]) + 1


def _optimization_metadata(state: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "semantics_sha256": digest_value(state["semantics"]),
        "regional_catalog_sha256": state["optimizer"]["regional_catalog_sha256"],
        "arithmetic_profile_sha256": digest_value(
            state["semantics"]["arithmetic_profile"]
        ),
        "target_profile": {
            "backend": state["backend"]["actual"],
            "policy": state["backend"]["policy"],
            "runtime_schema": RUNTIME_SCHEMA,
            "effective_capabilities": list(state["capabilities"]),
        },
    }


def _adopt_optimization(
    state: MutableMapping[str, Any],
    artifact: CompiledArtifact,
) -> Mapping[str, Any]:
    optimizer = state["optimizer"]
    artifact_record = artifact.as_dict()
    existing = optimizer["artifacts"].get(artifact.artifact_id)
    if existing is not None:
        if existing["artifact"] != artifact_record:
            raise RuntimeError("compiled artifact identity conflict")
        return existing
    if len(optimizer["artifacts"]) >= _limit(state, "max_optimizations"):
        raise RuntimeError("compiled artifact limit exhausted")
    key = f"{artifact.program_id}:{artifact.code_id}:{artifact.start_pc}"
    row = {
        "artifact": artifact_record,
        "status": "adopted",
        "adopted_at": int(state["ledger"]["instructions"]),
        "last_guard": "not-evaluated" if artifact.guards else "proved",
        "hits": 0,
        "deoptimizations": 0,
        "physical_work": 0,
        "logical_work": 0,
    }
    optimizer["artifacts"][artifact.artifact_id] = row
    optimizer["active"][key] = artifact.artifact_id
    optimizer["ledger"]["artifacts_adopted"] += 1
    _optimizer_history(
        state,
        "compiled-artifact-adopted",
        {
            "artifact_id": artifact.artifact_id,
            "kind": artifact.kind,
            "program_id": artifact.program_id,
            "code_id": artifact.code_id,
            "start_pc": artifact.start_pc,
        },
    )
    return row


def _environment_guards(
    state: MutableMapping[str, Any],
    frame: Mapping[str, Any],
    name: str,
) -> tuple[list[Mapping[str, Any]], Mapping[str, Any]]:
    starts = (
        ("locals", _check_value(frame["locals"])),
        ("globals", _check_value(frame["globals"])),
        ("builtins", _check_value(frame["builtins"])),
    )
    guards: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for role, start in starts:
        current: Mapping[str, Any] | None = start
        while current is not None:
            object_id = _ref_id(current)
            if object_id in seen:
                break
            seen.add(object_id)
            item = _heap_object(state, current)
            guards.append(
                {
                    "kind": "heap-version",
                    "role": role,
                    "object_id": object_id,
                    "generation": int(item["generation"]),
                    "version": int(item["version"]),
                }
            )
            current = _env_parent(state, current)
    try:
        value = _name_load(state, frame, name)
    except _GuestSignal as exc:
        raise RuntimeError("guarded name is not currently bound") from exc
    return guards, _plain(value)


def _compile_optimization(
    state: MutableMapping[str, Any],
    arguments: Mapping[str, Any],
    budget: int,
) -> Mapping[str, Any]:
    optimizer = state["optimizer"]
    kind = str(arguments.get("kind", "constant-fold"))
    frame_id = arguments.get("frame_id")
    if frame_id is None:
        task = state["tasks"].get(state.get("active_task"))
        if isinstance(task, Mapping) and task.get("stack"):
            frame_id = task["stack"][-1]
    frame = state["frames"].get(frame_id) if isinstance(frame_id, str) else None
    program_id = str(
        arguments.get(
            "program_id",
            frame["program_id"] if isinstance(frame, Mapping) else state["identity"]["program_id"],
        )
    )
    program = state["programs"].get(program_id)
    if not isinstance(program, Mapping):
        raise RuntimeError("optimizer program is unavailable")
    metadata = _optimization_metadata(state)
    adopted: list[str] = []
    charged_work = 1
    if kind == "constant-fold":
        code_ids = sorted(program["code"]["codes"])
        program_sha256 = digest_value(program)
        cursor = optimizer.get("scan")
        if (
            bool(arguments.get("reset", False))
            or not isinstance(cursor, Mapping)
            or cursor.get("program_sha256") != program_sha256
            or cursor.get("kind") != kind
        ):
            cursor = {
                "kind": kind,
                "program_id": program_id,
                "program_sha256": program_sha256,
                "code_index": 0,
                "pc": 0,
                "done": False,
            }
        cursor = dict(cursor)
        charged_work = 0
        while charged_work < budget and int(cursor["code_index"]) < len(code_ids):
            code_id = code_ids[int(cursor["code_index"])]
            instructions = program["code"]["codes"][code_id]["instructions"]
            pc = int(cursor["pc"])
            if pc >= len(instructions):
                cursor["code_index"] = int(cursor["code_index"]) + 1
                cursor["pc"] = 0
                continue
            artifact = compile_constant_fold_at(
                program,
                code_id=code_id,
                pc=pc,
                **metadata,
            )
            charged_work += 1
            optimizer["ledger"]["compile_work"] += 1
            if artifact is None:
                cursor["pc"] = pc + 1
            else:
                _adopt_optimization(state, artifact)
                adopted.append(artifact.artifact_id)
                cursor["pc"] = artifact.next_pc
        if int(cursor["code_index"]) >= len(code_ids):
            cursor["done"] = True
        optimizer["scan"] = cursor
        status = "completed" if cursor["done"] else "yielded"
    elif kind == "guarded-load-name":
        if not isinstance(frame, Mapping):
            raise RuntimeError("guarded specialization frame is unavailable")
        code_id = str(arguments.get("code_id", frame["code_id"]))
        pc = int(arguments.get("pc", frame["pc"]))
        code = program["code"]["codes"].get(code_id)
        if not isinstance(code, Mapping) or not 0 <= pc < len(code["instructions"]):
            raise RuntimeError("guarded specialization program counter is unavailable")
        instruction = code["instructions"][pc]
        if instruction.get("op") != "LOAD_NAME":
            raise RuntimeError("guarded specialization requires a LOAD_NAME safe point")
        guards, cached_value = _environment_guards(
            state,
            frame,
            str(instruction["arg"]),
        )
        artifact = compile_guarded_load_name(
            program,
            code_id=code_id,
            pc=pc,
            guards=guards,
            cached_value=cached_value,
            **metadata,
        )
        _adopt_optimization(state, artifact)
        adopted.append(artifact.artifact_id)
        optimizer["ledger"]["compile_work"] += 1
        status = "completed"
    else:
        raise RuntimeError("optimization kind is unsupported")
    return {
        "schema": "cassifi.optimization-control.v1",
        "status": status,
        "kind": kind,
        "adopted_artifact_ids": adopted,
        "continuation": _plain(optimizer.get("scan")),
        "charged_work": max(charged_work, 1),
        "ledger": _plain(optimizer["ledger"]),
    }
def optimizer_status(state: Mapping[str, Any]) -> Mapping[str, Any]:
    if (
        not isinstance(state, Mapping)
        or state.get("schema") != RUNTIME_SCHEMA
        or not isinstance(state.get("optimizer"), Mapping)
    ):
        raise RuntimeError("optimizer status requires a Python runtime state")
    return {
        "schema": "cassifi.optimization-status.v1",
        "artifacts": _plain(state["optimizer"]["artifacts"]),
        "active": _plain(state["optimizer"]["active"]),
        "continuation": _plain(state["optimizer"].get("scan")),
        "history": _plain(state["optimizer"]["history"]),
        "ledger": _plain(state["optimizer"]["ledger"]),
        "charged_work": 0,
    }
def _admit_portable_optimization(
    state: MutableMapping[str, Any],
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    raw = arguments.get("artifact")
    if not isinstance(raw, Mapping):
        raise RuntimeError("portable optimization requires an artifact")
    try:
        parsed = CompiledArtifact.from_dict(raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("portable compiled artifact is invalid") from exc
    program = state["programs"].get(parsed.program_id)
    if not isinstance(program, Mapping):
        raise RuntimeError("compiled artifact program is not resident")
    try:
        artifact = validate_portable_artifact(
            parsed,
            program,
            **_optimization_metadata(state),
        )
    except OptimizationCompilerError as exc:
        raise RuntimeError(str(exc)) from exc
    existed = artifact.artifact_id in state["optimizer"]["artifacts"]
    _adopt_optimization(state, artifact)
    contribution_sha256 = str(arguments.get("contribution_sha256", ""))
    if contribution_sha256 and (
        len(contribution_sha256) != 64
        or any(character not in "0123456789abcdef" for character in contribution_sha256)
    ):
        raise RuntimeError("optimization contribution digest is invalid")
    if not existed:
        _optimizer_history(
            state,
            "compiled-artifact-incorporated",
            {
                "artifact_id": artifact.artifact_id,
                "contribution_sha256": contribution_sha256 or None,
                "provider_member_id": str(
                    arguments.get("provider_member_id", "unknown")
                ),
            },
        )
    return {
        "schema": "cassifi.optimization-admission.v1",
        "status": "already-resident" if existed else "incorporated",
        "artifact_id": artifact.artifact_id,
        "artifact_sha256": artifact.sha256,
        "charged_work": 1,
    }






def _guard_outcome(
    state: Mapping[str, Any],
    artifact: CompiledArtifact,
) -> str:
    try:
        for guard in artifact.guards:
            object_id = str(guard["object_id"])
            item = state["heap"].get(object_id)
            if not isinstance(item, Mapping):
                return "stale"
            if int(item.get("generation", -1)) != int(guard["generation"]):
                return "stale"
            if int(item.get("version", -1)) != int(guard["version"]):
                return "false"
        return "true"
    except (KeyError, TypeError, ValueError):
        return "error"


def _execute_optimized(
    state: MutableMapping[str, Any],
    frame: MutableMapping[str, Any],
    instruction_pc: int,
) -> int | None:
    optimizer = state["optimizer"]
    key = f"{frame['program_id']}:{frame['code_id']}:{instruction_pc}"
    artifact_id = optimizer["active"].get(key)
    if not isinstance(artifact_id, str):
        return None
    row = optimizer["artifacts"].get(artifact_id)
    if not isinstance(row, MutableMapping) or row.get("status") != "adopted":
        return None
    try:
        artifact = CompiledArtifact.from_dict(row["artifact"])
        program = state["programs"].get(frame["program_id"])
        if (
            not isinstance(program, Mapping)
            or digest_value(program) != artifact.program_sha256
            or digest_value(state["semantics"]) != artifact.semantics_sha256
            or state["optimizer"]["regional_catalog_sha256"]
            != artifact.regional_catalog_sha256
        ):
            outcome = "stale"
        else:
            outcome = _guard_outcome(state, artifact)
        row["last_guard"] = outcome
        if outcome != "true":
            row["status"] = outcome
            row["deoptimizations"] = int(row["deoptimizations"]) + 1
            optimizer["ledger"]["deoptimizations"] += 1
            optimizer["ledger"][f"guard_{outcome}"] += 1
            _optimizer_history(
                state,
                "compiled-artifact-deoptimized",
                {
                    "artifact_id": artifact_id,
                    "guard_outcome": outcome,
                    "interpreter_pc": instruction_pc,
                    "settled_operation_ids": sorted(
                        operation_id
                        for operation_id, operation in state["operations"].items()
                        if operation.get("phase") == "settled"
                    ),
                },
            )
            return None
        replacement = artifact.replacement
        if artifact.kind == "constant-fold":
            if replacement.get("op") != "LOAD_CONST":
                raise RuntimeError("constant-fold replacement is invalid")
            frame["stack"].append(_constant_value(state, replacement["arg"]))
            frame["pc"] = artifact.next_pc
        elif artifact.kind == "guarded-load-name":
            if replacement.get("op") != "LOAD_CACHED_NAME":
                raise RuntimeError("guarded-load replacement is invalid")
            frame["stack"].append(
                _plain(_check_value(replacement["value"]))
            )
            frame["pc"] = artifact.next_pc
        else:
            raise RuntimeError("compiled artifact kind is unsupported")
        if artifact.guards:
            optimizer["ledger"]["guard_true"] += 1
        row["hits"] = int(row["hits"]) + 1
        row["physical_work"] = int(row["physical_work"]) + 1
        row["logical_work"] = (
            int(row["logical_work"]) + artifact.logical_instructions
        )
        optimizer["ledger"]["hits"] += 1
        optimizer["ledger"]["physical_work"] += 1
        optimizer["ledger"]["logical_work"] += artifact.logical_instructions
        optimizer["ledger"]["logical_instructions_saved"] += (
            artifact.logical_instructions - 1
        )
        return artifact.logical_instructions
    except (KeyError, TypeError, ValueError, OptimizationCompilerError) as exc:
        row["status"] = "error"
        row["last_guard"] = "error"
        row["deoptimizations"] = int(row["deoptimizations"]) + 1
        optimizer["ledger"]["deoptimizations"] += 1
        optimizer["ledger"]["guard_error"] += 1
        _optimizer_history(
            state,
            "compiled-artifact-error",
            {"artifact_id": artifact_id, "error": str(exc)},
        )
        return None


def _step(state: MutableMapping[str, Any]) -> str:
    task_id = state.get("active_task")
    task = state["tasks"].get(task_id)
    if not isinstance(task, MutableMapping): raise RuntimeError("active task is unavailable")
    if task["status"] in {"waiting", "paused", "resource-paused"} or state["phase"] in {"paused", "resource-paused"}:
        return "blocked"
    if _advance_finalizer_queue(state, task):
        return "running"
    if task["status"] in {"completed", "faulted", "cancelled"}: return "done" if task["status"] == "completed" else "fault"
    if not task["stack"]:
        task["status"] = "completed"; state["phase"] = "completed"; return "done"
    frame = state["frames"][task["stack"][-1]]
    if frame.get("resume_signal") is not None and _resume_pending_signal(state, task, frame): return "running"
    code = _frame_code(state, frame); instructions = code["instructions"]
    if int(frame["pc"]) >= len(instructions):
        _finish_frame(state, task, frame, _v_none()); return "running"
    instruction_pc = int(frame["pc"])
    state["fault_checkpoint"] = {
        "snapshot": _snapshot(state),
        "ledger": copy.deepcopy(state["ledger"]),
        "event_count": len(state["events"]),
        "frame_id": frame["frame_id"],
        "pc": instruction_pc,
        "program_id": frame["program_id"],
        "source_span": _plain(instructions[instruction_pc].get("span")),
    }
    instruction = instructions[instruction_pc]
    frame["pc"] = instruction_pc + 1
    logical_charge = 1
    state["_instruction_active"] = True
    try:
        optimized_charge = _execute_optimized(state, frame, instruction_pc)
        if optimized_charge is None:
            _execute_instruction(state, task, frame, instruction)
        else:
            logical_charge = optimized_charge
    except _ResourceLimitPause as pause:
        checkpoint = state["fault_checkpoint"]
        for key, value in checkpoint["snapshot"].items():
            state[key] = value
        state["ledger"] = copy.deepcopy(checkpoint["ledger"])
        del state["events"][int(checkpoint["event_count"]):]
        task = state["tasks"][task_id]
        state["phase"] = "resource-paused"
        task["status"] = "resource-paused"
        state["resource_wait"] = {
            "schema": "cassifi.python-runtime-resource-wait.v1",
            "limit": pause.limit,
            "required": pause.required,
            "current": _limit(state, pause.limit),
            "message": pause.message,
            "task_id": task_id,
            "operation_id": state["identity"]["operation_id"],
            "frame_id": checkpoint["frame_id"],
            "pc": checkpoint["pc"],
            "source_span": copy.deepcopy(checkpoint["source_span"]),
        }
        return "blocked"
    except _GuestSignal as signal:
        _propagate(state, task, {"kind": "exception", "value": signal.exception})
    except (TypeError, ValueError, KeyError, IndexError, AttributeError, ImportError, ZeroDivisionError, OverflowError) as exc:
        _propagate(state, task, {"kind": "exception", "value": _raise_host(state, exc).exception})
    finally:
        state.pop("_instruction_active", None)
    state["ledger"]["instructions"] += logical_charge
    state["ledger"]["peak_heap_objects"] = max(state["ledger"]["peak_heap_objects"], len(state["heap"]))
    state["ledger"]["peak_frames"] = max(state["ledger"]["peak_frames"], len(state["frames"]))
    return "blocked" if task["status"] in {"waiting", "paused", "resource-paused"} else "fault" if task["status"] == "faulted" else "done" if task["status"] == "completed" else "running"


def _checkpoint_payload(state: Mapping[str, Any]) -> Mapping[str, Any]:
    return {key: value for key, value in state.items() if key not in {"branches"}}


def _collect_refs(value: Any, refs: set[str]) -> None:
    if isinstance(value, Mapping):
        if value.get("t") == "ref" and isinstance(value.get("id"), str): refs.add(str(value["id"])); return
        for member in value.values(): _collect_refs(member, refs)
    elif isinstance(value, list):
        for member in value: _collect_refs(member, refs)


def _collect(state: MutableMapping[str, Any]) -> Mapping[str, Any]:
    roots: set[str] = set()
    for key in ("frames", "tasks", "modules", "operations", "runtime_roots", "result"):
        _collect_refs(state.get(key), roots)
    for branch in state["branches"].values(): _collect_refs(branch.get("snapshot"), roots)
    reachable: set[str] = set(); frontier = list(roots)
    while frontier:
        object_id = frontier.pop()
        if object_id in reachable or object_id not in state["heap"]: continue
        reachable.add(object_id)
        item = state["heap"][object_id]
        payload = item["payload"]
        if item["kind"] == "weakref":
            payload = {key: value for key, value in payload.items() if key != "target"}
        discovered: set[str] = set(); _collect_refs(payload, discovered); frontier.extend(discovered)
    unreachable = [object_id for object_id in state["heap"] if object_id not in reachable]
    finalizers: list[Mapping[str, Any]] = []
    for object_id in unreachable:
        item = state["heap"][object_id]
        if item["gc"]["finalizer"] and not item["gc"]["finalized"]:
            item["gc"]["finalized"] = True
            finalizers.append(
                {"kind": "finalizer", "object_id": object_id, "phase": "queued"}
            )
            reachable.add(object_id)
    reclaimed = 0
    for object_id in unreachable:
        if object_id in reachable: continue
        item = state["heap"][object_id]
        for weak_id in item["gc"].get("weakrefs", []):
            weak = state["heap"].get(weak_id)
            if weak is not None:
                weak["payload"]["target"] = None
                weak["payload"]["cleared"] = True
                _mutated(weak)
                callback = weak["payload"].get("callback")
                if callback is not None and weak_id in reachable:
                    finalizers.append(
                        {
                            "kind": "weakref-callback",
                            "weakref_id": weak_id,
                            "callback": _plain(callback),
                            "phase": "queued",
                        }
                    )
        del state["heap"][object_id]; reclaimed += 1
    state["finalizer_queue"].extend(finalizers); state["ledger"]["collections"] += 1; state["ledger"]["reclaimed_objects"] += reclaimed
    return {"reachable": len(reachable), "reclaimed": reclaimed, "finalizers_queued": len(finalizers)}


def _snapshot(state: Mapping[str, Any]) -> Mapping[str, Any]:
    keys = ("programs", "heap", "frames", "tasks", "operations", "modules", "scheduler", "active_task", "counters", "phase", "result", "stdout", "finalizer_queue", "runtime_roots", "optimizer")
    snapshot = {key: state[key] for key in keys}
    snapshot["resource_wait"] = state.get("resource_wait")
    return _plain(snapshot)


def _begin_branch(
    state: MutableMapping[str, Any],
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    if len(state["branches"]) >= _limit(state, "max_branches"):
        raise RuntimeError("branch limit exhausted")
    branch_id = str(arguments.get("branch_id") or _next_id(state, "branch"))
    if branch_id in state["branches"]:
        raise RuntimeError("branch identity already exists")
    effect_policy = str(arguments.get("effect_policy", "forbid"))
    if effect_policy != "forbid":
        raise RuntimeError("hypothetical branches require the forbid effect policy")
    snapshot = _snapshot(state)
    base = digest_value(snapshot)
    state["branches"][branch_id] = {
        "schema": "cassifi.python-branch.v1",
        "branch_id": branch_id,
        "parent": state["branch_stack"][-1] if state["branch_stack"] else None,
        "base_sha256": base,
        "snapshot": snapshot,
        "base_object_versions": {
            object_id: int(item["version"])
            for object_id, item in snapshot["heap"].items()
        },
        "assumptions": _plain(arguments.get("assumptions", [])),
        "effect_policy": effect_policy,
        "status": "active",
        "work_start": state["ledger"]["instructions"],
        "spent_work": None,
    }
    state["branch_stack"].append(branch_id)
    return {
        "branch_id": branch_id,
        "parent": state["branches"][branch_id]["parent"],
        "base_sha256": base,
        "effect_policy": effect_policy,
    }


def _rollback_branch(
    state: MutableMapping[str, Any],
    branch_id: str,
) -> Mapping[str, Any]:
    if not state["branch_stack"] or state["branch_stack"][-1] != branch_id:
        raise RuntimeError("only the active innermost branch may roll back")
    branch = state["branches"][branch_id]
    spent = state["ledger"]["instructions"] - int(branch["work_start"])
    ledger = copy.deepcopy(state["ledger"])
    snapshot = copy.deepcopy(branch["snapshot"])
    discarded_objects = sorted(set(state["heap"]) - set(snapshot["heap"]))
    for key, value in snapshot.items():
        state[key] = value
    ledger["branch_work"] += spent
    state["ledger"] = ledger
    state["branches"][branch_id] = {
        **{
            key: value
            for key, value in branch.items()
            if key not in {"snapshot", "base_object_versions"}
        },
        "status": "rolled-back",
        "spent_work": spent,
        "discarded_object_ids": discarded_objects,
    }
    state["branch_stack"].pop()
    return {
        "branch_id": branch_id,
        "status": "rolled-back",
        "spent_work": spent,
        "discarded_object_ids": discarded_objects,
    }


def _branch_escape_map(
    state: Mapping[str, Any],
    branch: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    snapshot = branch["snapshot"]
    base_ids = set(snapshot["heap"])
    new_ids = set(state["heap"]) - base_ids
    escapes: list[Mapping[str, Any]] = []
    for object_id in sorted(base_ids & set(state["heap"])):
        refs: set[str] = set()
        _collect_refs(state["heap"][object_id].get("payload"), refs)
        escaped = sorted(refs & new_ids)
        if escaped:
            escapes.append(
                {
                    "holder_object_id": object_id,
                    "promoted_object_ids": escaped,
                }
            )
    return escapes


def _commit_branch(
    state: MutableMapping[str, Any],
    branch_id: str,
    arguments: Mapping[str, Any],
) -> Mapping[str, Any]:
    if not state["branch_stack"] or state["branch_stack"][-1] != branch_id:
        raise RuntimeError("only the active innermost branch may commit")
    branch = state["branches"][branch_id]
    expected_base = arguments.get("expected_base_sha256")
    if expected_base is not None and str(expected_base) != branch["base_sha256"]:
        raise RuntimeError("branch base revision is stale")
    if branch.get("effect_policy") != "forbid":
        raise RuntimeError("branch effect policy is not publishable")
    snapshot_operations = set(branch["snapshot"]["operations"])
    new_operations = set(state["operations"]) - snapshot_operations
    if new_operations:
        raise RuntimeError("branch contains queued external operations")
    escape_map = _branch_escape_map(state, branch)
    if bool(arguments.get("require_no_reference_escape", False)) and escape_map:
        raise RuntimeError("branch contains escaping references")
    spent = state["ledger"]["instructions"] - int(branch["work_start"])
    successor_sha256 = digest_value(_snapshot(state))
    state["branches"][branch_id] = {
        **{
            key: value
            for key, value in branch.items()
            if key not in {"snapshot", "base_object_versions"}
        },
        "status": "committed",
        "spent_work": spent,
        "successor_sha256": successor_sha256,
        "reference_escape_map": escape_map,
    }
    state["branch_stack"].pop()
    return {
        "branch_id": branch_id,
        "status": "committed",
        "spent_work": spent,
        "successor_sha256": successor_sha256,
        "reference_escape_map": escape_map,
    }


def _handle_arguments(
    state: MutableMapping[str, Any],
    arguments: Mapping[str, Any],
    budget: int,
) -> Mapping[str, Any] | None:
    if not arguments: return None
    operation = arguments.get("operation")
    task = state["tasks"].get(state["active_task"])
    if operation == "increase-limits":
        if state["phase"] in {"completed", "faulted", "cancelled"}:
            raise RuntimeError(
                f"runtime limits cannot be increased for {state['phase']} computation"
            )
        requested = arguments.get("limits")
        if not isinstance(requested, Mapping) or not requested:
            raise RuntimeError("limit increase requires a nonempty limits mapping")
        unknown = [
            name
            for name in requested
            if not isinstance(name, str) or name not in state["limits"]
        ]
        if unknown:
            raise RuntimeError(
                f"unknown runtime limits: {sorted(unknown, key=str)}"
            )
        changed: dict[str, int] = {}
        for name, value in requested.items():
            current_limit = _limit(state, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise RuntimeError(f"runtime limit {name} is invalid")
            if value < current_limit:
                raise RuntimeError(f"runtime limit {name} cannot be reduced")
            if value > current_limit:
                changed[name] = value
        if not changed:
            raise RuntimeError("limit increase must raise at least one runtime limit")
        state["limits"].update(changed)
        resource_wait = state.get("resource_wait")
        if (
            isinstance(resource_wait, Mapping)
            and state["limits"].get(resource_wait.get("limit"), 0)
            >= resource_wait.get("required", 1)
        ):
            state["resource_wait"] = None
            if state["phase"] == "resource-paused":
                state["phase"] = "running"
                task["status"] = "running"
            elif state["phase"] == "paused":
                paused_from = state.get("paused_from")
                if (
                    isinstance(paused_from, MutableMapping)
                    and paused_from.get("phase") == "resource-paused"
                ):
                    paused_from["phase"] = "running"
                    paused_from["task_status"] = "running"
        return {
            "status": state["phase"],
            "changed_limits": changed,
            "resource_wait": copy.deepcopy(state.get("resource_wait")),
            "charged_work": 1,
        }
    if operation == "resume":
        operation_id = str(arguments.get("operation_id"))
        pending = state["operations"].get(operation_id)
        if not isinstance(pending, MutableMapping):
            raise RuntimeError("resume operation is unknown")
        settlement = (
            {
                "kind": "exception",
                "exception_type": str(
                    arguments.get("exception_type", "RuntimeError")
                ),
                "message": str(arguments["exception"]),
            }
            if "exception" in arguments
            else {"kind": "value", "value": _plain(arguments.get("value"))}
        )
        settlement_sha256 = digest_value(settlement)
        if pending["phase"] == "settled":
            if pending.get("settlement_sha256") != settlement_sha256:
                raise RuntimeError("external result conflicts with settled operation")
            return {
                "status": "already-settled",
                "operation_id": operation_id,
                "settlement_sha256": settlement_sha256,
            }
        if pending["phase"] == "revoked":
            raise RuntimeError("external operation was revoked")
        if pending["phase"] != "proposed":
            raise RuntimeError("external operation is not resumable")
        if (
            task["status"] != "waiting"
            or operation_id != task["await_target"]
        ):
            raise RuntimeError("resume operation does not match wait target")
        if settlement["kind"] == "exception":
            pending["result"] = _exception(
                state,
                str(settlement["exception_type"]),
                str(settlement["message"]),
            )
        else:
            pending["result"] = _from_host(state, settlement["value"])
        pending["phase"] = "settled"
        pending["settlement"] = settlement
        pending["settlement_sha256"] = settlement_sha256
        task["status"] = "running"
        task["await_target"] = None
        task["pending_call"] = None
        if settlement["kind"] == "exception":
            _propagate(
                state,
                task,
                {"kind": "exception", "value": pending["result"]},
            )
        elif task["stack"]:
            state["frames"][task["stack"][-1]]["stack"].append(
                _plain(pending["result"])
            )
        return {
            "status": "resumed",
            "operation_id": operation_id,
            "settlement_sha256": settlement_sha256,
        }
    if operation == "pause":
        if state["phase"] in {"completed", "faulted", "cancelled"}:
            return {"status": state["phase"]}
        if state["phase"] != "paused":
            state["paused_from"] = {
                "phase": state["phase"],
                "task_status": task["status"],
            }
            state["phase"] = "paused"
            task["status"] = "paused"
        return {
            "status": "paused",
            "reason": str(arguments.get("reason", "requested")),
        }
    if operation == "continue":
        if state["phase"] != "paused":
            raise RuntimeError("only a paused Python computation can continue")
        paused_from = state.pop("paused_from", None)
        if not isinstance(paused_from, Mapping):
            raise RuntimeError("paused Python continuation is unavailable")
        state["phase"] = str(paused_from["phase"])
        task["status"] = str(paused_from["task_status"])
        return {"status": state["phase"]}
    if operation == "cancel":
        if task["status"] in {"completed", "faulted", "cancelled"}: return {"status": task["status"]}
        task["status"] = "cancelled"; task["exception"] = _exception(state, "CancelledError", str(arguments.get("reason", "cancelled"))); state["phase"] = "cancelled"; state["result"] = {"schema": RUNTIME_RESULT_SCHEMA, "status": "cancelled", "task_id": task["task_id"], "exception": _project(state, task["exception"]), "logical_work": state["ledger"]["instructions"]}; return {"status": "cancelled"}
    if operation == "begin-branch": return _begin_branch(state, arguments)
    if operation == "rollback": return _rollback_branch(state, str(arguments["branch_id"]))
    if operation == "commit":
        return _commit_branch(state, str(arguments["branch_id"]), arguments)
    if operation == "collect": return _collect(state)
    if operation == "inspect": return computation_view(state, offset=int(arguments.get("offset", 0)), limit=int(arguments.get("limit", 64))).as_dict()
    if operation == "optimize":
        return _compile_optimization(state, arguments, budget)
    if operation == "optimizer-status":
        return optimizer_status(state)
    if operation == "admit-optimization":
        return _admit_portable_optimization(state, arguments)
    if operation == "invalidate-optimization":
        artifact_id = str(arguments.get("artifact_id"))
        row = state["optimizer"]["artifacts"].get(artifact_id)
        if not isinstance(row, MutableMapping):
            raise RuntimeError("compiled artifact is unknown")
        row["status"] = "invalidated"
        state["optimizer"]["ledger"]["invalidations"] += 1
        _optimizer_history(
            state,
            "compiled-artifact-invalidated",
            {
                "artifact_id": artifact_id,
                "reason": str(arguments.get("reason", "dependency-correction")),
            },
        )
        return {
            "status": "invalidated",
            "artifact_id": artifact_id,
            "charged_work": 1,
        }
    if operation == "repair":
        if state["phase"] != "faulted": raise RuntimeError("repair requires a faulted computation")
        replacement = arguments.get("program")
        if not isinstance(replacement, Mapping) or replacement.get("schema") != PythonProgram.SCHEMA: raise RuntimeError("repair requires a compiled PythonProgram")
        checkpoint = state.get("fault_checkpoint")
        if not isinstance(checkpoint, Mapping) or not isinstance(checkpoint.get("snapshot"), Mapping):
            raise RuntimeError("fault predecessor checkpoint is unavailable")
        preserved_ledger = copy.deepcopy(state["ledger"])
        preserved_branches = copy.deepcopy(state["branches"])
        preserved_branch_stack = copy.deepcopy(state["branch_stack"])
        for key, value in copy.deepcopy(checkpoint["snapshot"]).items():
            state[key] = value
        state["ledger"] = preserved_ledger
        state["branches"] = preserved_branches
        state["branch_stack"] = preserved_branch_stack
        state["programs"][str(replacement["program_id"])] = _plain(replacement)
        frame_id = arguments.get("frame_id", checkpoint.get("frame_id"))
        if not isinstance(frame_id, str) or frame_id not in state["frames"]:
            raise RuntimeError("repair frame is unavailable")
        frame = state["frames"][frame_id]
        frame["program_id"] = replacement["program_id"]
        frame["code_id"] = str(arguments.get("code_id", replacement["code"]["entry"]))
        frame["pc"] = int(arguments.get("pc", 0))
        frame["current_exception"] = None
        task = state["tasks"][state["active_task"]]
        task["status"] = "running"
        task["exception"] = None
        state["phase"] = "running"
        state["result"] = None
        state["fault_checkpoint"] = None
        repair_event = {
            "schema": "cassifi.program-event.v1",
            "event_id": _next_id(state, "event"),
            "kind": "computation-repaired",
            "payload": {
                "frame_id": frame_id,
                "program_id": replacement["program_id"],
                "predecessor_program_id": checkpoint.get("program_id"),
                "predecessor_pc": checkpoint.get("pc"),
                "predecessor_source_span": _plain(checkpoint.get("source_span")),
            },
        }
        state["events"].append(repair_event)
        if len(state["events"]) > _limit(state, "max_events"):
            raise RuntimeError("event limit exhausted")
        return {
            "status": "repaired",
            "frame_id": frame_id,
            "program_id": replacement["program_id"],
            "predecessor_program_id": checkpoint.get("program_id"),
            "predecessor_pc": checkpoint.get("pc"),
        }
    if operation == "revocation":
        capability = str(arguments.get("capability"))
        state["capabilities"] = [
            item for item in state["capabilities"] if item != capability
        ]
        operation_kind = {
            "model-request": "model",
            "effect-proposal": "effect",
        }.get(capability)
        revoked_operation_ids: list[str] = []
        for operation_id, candidate in state["operations"].items():
            if (
                candidate["phase"] == "proposed"
                and operation_kind is not None
                and candidate["kind"] == operation_kind
            ):
                candidate["phase"] = "revoked"
                candidate["revocation"] = {
                    "capability": capability,
                    "reason": str(
                        arguments.get("reason", "capability revoked")
                    ),
                }
                revoked_operation_ids.append(operation_id)
        if (
            task["status"] == "waiting"
            and task["await_target"] in revoked_operation_ids
        ):
            operation_id = str(task["await_target"])
            exception = _exception(
                state,
                "PermissionError",
                f"capability {capability!r} was revoked",
            )
            state["operations"][operation_id]["result"] = exception
            task["status"] = "running"
            task["await_target"] = None
            task["pending_call"] = None
            _propagate(
                state,
                task,
                {"kind": "exception", "value": exception},
            )
        invalidated: list[str] = []
        for artifact_id, row in state["optimizer"]["artifacts"].items():
            effective = row["artifact"]["target_profile"].get(
                "effective_capabilities", []
            )
            if capability in effective and row["status"] == "adopted":
                row["status"] = "invalidated"
                invalidated.append(artifact_id)
        state["optimizer"]["ledger"]["invalidations"] += len(invalidated)
        return {
            "status": "revoked",
            "capability": capability,
            "revoked_operation_ids": revoked_operation_ids,
            "invalidated_artifact_ids": invalidated,
        }
    raise RuntimeError("runtime operation is unsupported")


def initial_state(
    program: PythonProgram | Mapping[str, Any],
    *,
    inputs: Mapping[str, Any] | None = None,
    owner_id: str = "owner",
    member_id: str = "member",
    lineage_id: str = "lineage",
    operation_id: str = "python-main",
    capabilities: Sequence[str] = (),
    limits: Mapping[str, int] | None = None,
    module_sources: Mapping[str, Mapping[str, Any]] | None = None,
    backend_policy: str = "logical-cpu",
    regional_catalog_sha256: str | None = None,
) -> dict[str, Any]:
    record = program.as_dict() if isinstance(program, PythonProgram) else _plain(program)
    if record.get("schema") != PythonProgram.SCHEMA: raise RuntimeError("program record is invalid")
    selected_limits = dict(DEFAULT_LIMITS)
    if limits:
        unknown = set(limits) - set(selected_limits)
        if unknown: raise RuntimeError(f"unknown runtime limits: {sorted(unknown)}")
        for name, value in limits.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 1: raise RuntimeError(f"runtime limit {name} is invalid")
            selected_limits[name] = value
    state: dict[str, Any] = {
        "schema": RUNTIME_SCHEMA,
        "semantics": default_python_semantics().as_dict(),
        "interpreter": {"schema": "cassifi.interpreter-program.v1", "program_id": "cassifi.bootstrap-python", "version": 1, "source_sha256": hashlib.sha256(b"cassifi-field-python-runtime-v1").hexdigest(), "ir_sha256": digest_value(record["code"]), "semantics_sha256": default_python_semantics().sha256, "dependencies": [], "entry": "runtime.step", "source_map": {}, "assessment": {"status": "runtime-bootstrap"}, "adoption_state": "adopted"},
        "identity": {"owner_id": owner_id, "member_id": member_id, "lineage_id": lineage_id, "program_id": record["program_id"], "operation_id": operation_id},
        "backend": {"policy": backend_policy, "actual": "logical-cpu", "placement_reason": "canonical-bootstrap"},
        "limits": selected_limits,
        "capabilities": sorted(set(str(item) for item in capabilities)),
        "optimizer": {
            "schema": "cassifi.field-optimizer-state.v1",
            "regional_catalog_sha256": (
                regional_catalog_sha256
                or hashlib.sha256(b"unbound-regional-catalog").hexdigest()
            ),
            "artifacts": {},
            "active": {},
            "scan": None,
            "history": [],
            "ledger": {
                "compile_work": 0,
                "artifacts_adopted": 0,
                "hits": 0,
                "deoptimizations": 0,
                "invalidations": 0,
                "guard_true": 0,
                "guard_false": 0,
                "guard_stale": 0,
                "guard_error": 0,
                "physical_work": 0,
                "logical_work": 0,
                "logical_instructions_saved": 0,
                "events": 0,
            },
        },
        "programs": {record["program_id"]: record},
        "heap": {}, "frames": {}, "tasks": {}, "operations": {}, "modules": {},
        "module_sources": _plain(dict(module_sources or {})),
        "scheduler": [], "active_task": None,
        "counters": {"object": 1, "frame": 1, "task": 1, "operation": 1, "event": 1, "branch": 1},
        "phase": "running", "result": None, "stdout": "", "events": [],
        "resource_wait": None,
        "branches": {}, "branch_stack": [], "finalizer_queue": [],
        "runtime_roots": {},
        "ledger": {"instructions": 0, "allocations": 0, "frames_created": 0, "collections": 0, "reclaimed_objects": 0, "branch_work": 0, "peak_heap_objects": 0, "peak_frames": 0},
    }
    builtins_ref = _builtins(state)
    object_namespace = _env(state, builtins_ref, "class")
    object_ref = _alloc(state, "class", {"name": "object", "qualname": "object", "bases": [], "mro_tail": [], "namespace": object_namespace, "metaclass": None}, type_name="type")
    state["runtime_roots"] = {"builtins": builtins_ref, "object_type": object_ref}
    globals_ref = _env(state, builtins_ref, "module")
    _env_set(state, globals_ref, "__name__", _v_str(record["module"]))
    _env_set(state, globals_ref, "__package__", _v_none() if record.get("package") is None else _v_str(str(record["package"])))
    _env_set(state, globals_ref, "__annotations__", _alloc(state, "dict", {"entries": []}))
    for name, value in (inputs or {}).items(): _env_set(state, globals_ref, str(name), _from_host(state, value))
    module_ref = _alloc(state, "module", {"name": record["module"], "namespace": globals_ref, "status": "ready"}, type_name="module")
    state["modules"][record["module"]] = module_ref
    frame_id = _new_frame(state, program_id=record["program_id"], code_id=record["code"]["entry"], locals_ref=globals_ref, globals_ref=globals_ref, builtins_ref=builtins_ref)
    task_id = _next_id(state, "task")
    state["tasks"][task_id] = {"schema": "cassifi.py-task-state.v1", "task_id": task_id, "role": "main", "frame_ref": frame_id, "stack": [frame_id], "status": "running", "suspension": "none", "await_target": None, "pending_send": None, "pending_throw": None, "pending_call": None, "schedule_binding": "regional-automaton", "result": None, "exception": None}
    state["scheduler"] = [task_id]; state["active_task"] = task_id
    canonical_json_bytes(state)
    return state


def advance(state: Mapping[str, Any], arguments: Mapping[str, Any] | None, quantum: int) -> tuple[dict[str, Any], str, int, Mapping[str, Any] | None, tuple[Mapping[str, Any], ...]]:
    if not isinstance(state, Mapping) or state.get("schema") != RUNTIME_SCHEMA: raise RuntimeError("field Python runtime state is invalid")
    if isinstance(quantum, bool) or not isinstance(quantum, int) or quantum < 1: raise RuntimeError("runtime quantum must be positive")
    current = copy.deepcopy(dict(state)); event_start = len(current["events"])
    control = _handle_arguments(current, dict(arguments or {}), quantum)
    control_operation = (arguments or {}).get("operation")
    control_only = {
        "inspect", "begin-branch", "rollback", "commit", "collect",
        "revocation", "optimize", "optimizer-status",
        "invalidate-optimization", "pause", "continue", "cancel",
        "increase-limits",
    }
    if control is not None and control_operation in control_only:
        current["control_result"] = control
    work = 0
    status = "running"
    if control is not None and control_operation in control_only:
        work = min(quantum, max(1, int(control.get("charged_work", 1))))
        if current["phase"] == "completed":
            status = "done"
        elif current["phase"] in {"faulted", "cancelled"}:
            status = "fault"
        elif current["phase"] in {"waiting", "paused", "resource-paused"}:
            status = "blocked"
    else:
        while work < quantum:
            status = _step(current)
            if status != "running":
                break
            work += 1
    if status == "running": status = "yield"
    elif status == "done": status = "done"
    elif status == "fault": status = "fault"
    elif status == "blocked": status = "blocked"
    output = current.get("result") or control
    if output is None and current["phase"] == "resource-paused":
        output = copy.deepcopy(current.get("resource_wait"))
    events = tuple(copy.deepcopy(current["events"][event_start:]))
    canonical_json_bytes(current)
    return current, status, max(work, 1 if control is not None else 0), output, events


def computation_view(state: Mapping[str, Any], *, offset: int = 0, limit: int = 64) -> ComputationView:
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0: raise RuntimeError("view offset is invalid")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1_024: raise RuntimeError("view limit is invalid")
    frame_ids = sorted(state["frames"]); object_ids = sorted(state["heap"]); selected_frames = frame_ids[offset: offset + limit]; selected_objects = object_ids[offset: offset + limit]
    dependencies = sorted({dependency for program in state["programs"].values() for dependency in program.get("dependencies", [])})
    effects = [copy.deepcopy(value) for value in state["operations"].values()]
    return ComputationView(
        computation_id=str(state["identity"]["operation_id"]),
        version=int(state["ledger"]["instructions"]) + 1,
        owner_id=str(state["identity"]["owner_id"]),
        program_id=str(state["identity"]["program_id"]),
        status=str(state["phase"]),
        frame_refs=tuple(selected_frames), object_refs=tuple(selected_objects),
        assumptions=tuple(
            copy.deepcopy(assumption)
            for branch in state["branch_stack"]
            for assumption in state["branches"][branch].get("assumptions", [])
        ),
        dependencies=tuple(dependencies),
        effects=tuple(effects),
        costs={
            **copy.deepcopy(state["ledger"]),
            "optimizer": copy.deepcopy(state["optimizer"]["ledger"]),
            "compiled_artifacts": [
                {
                    "artifact_id": artifact_id,
                    "kind": row["artifact"]["kind"],
                    "status": row["status"],
                    "hits": row["hits"],
                    "deoptimizations": row["deoptimizations"],
                }
                for artifact_id, row in sorted(
                    state["optimizer"]["artifacts"].items()
                )
            ],
        },
        result=copy.deepcopy(state.get("result")),
        unfinished_reason=("runtime-limit-exhausted" if state["phase"] == "resource-paused" else "paused" if state["phase"] == "paused" else "awaiting-external-result" if any(task["status"] == "waiting" for task in state["tasks"].values()) else "finite-quantum" if state["phase"] == "running" else None),
        page={"offset": offset, "limit": limit, "frame_total": len(frame_ids), "object_total": len(object_ids), "has_more": offset + limit < max(len(frame_ids), len(object_ids))},
    )


def _json_guest_value(value: Any, active: set[int]) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, (list, dict)):
        identity = id(value)
        if identity in active:
            raise ValueError("cyclic guest result")
        active.add(identity)
        try:
            if isinstance(value, list):
                for item in value:
                    _json_guest_value(item, active)
            else:
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise TypeError("guest JSON object key must be a string")
                    _json_guest_value(item, active)
        finally:
            active.remove(identity)
        return
    raise TypeError("guest value is not JSON")


def read_global(state: Mapping[str, Any], name: str) -> Any:
    """Read a completed guest module global as a canonical JSON value."""
    if not isinstance(state, Mapping) or state.get("schema") != RUNTIME_SCHEMA:
        raise RuntimeError("field Python runtime state is invalid")
    if state.get("phase") != "completed" or not isinstance(name, str) or not name:
        raise RuntimeError("guest global is unavailable before completion")
    program = state["programs"][state["identity"]["program_id"]]
    module = state["modules"].get(program["module"])
    if not isinstance(module, Mapping):
        raise RuntimeError("guest module is unavailable")
    namespace = _heap_object(state, module)["payload"]["namespace"]
    values = _env_values(state, _check_value(namespace))
    if name not in values:
        raise RuntimeError(f"guest global {name!r} was not assigned")
    try:
        value = _to_host(state, _check_value(values[name]))
        _json_guest_value(value, set())
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)
        return json.loads(encoded)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise RuntimeError(f"guest global {name!r} is not a JSON value") from exc


__all__ = [
    "DEFAULT_LIMITS",
    "RUNTIME_SCHEMA",
    "RuntimeError",
    "advance",
    "computation_view",
    "initial_state",
    "read_global",
    "optimizer_status",
]
