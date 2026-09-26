"""Authenticated Windows client for the native CassiFI field-runtime service."""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import hashlib
import json
import math
from pathlib import Path
import secrets
import struct
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping
from typing import Any, Iterable, Sequence
import uuid

import numpy as np


FRAME_MAGIC = 0x31524643
PROTOCOL_VERSION = 2
FRAME_HEADER = struct.Struct("<IHHII16s32s")
MAX_FRAME_BODY = 8 << 20
MAX_FIELD_BYTES = 64 << 20
MAX_LOGICAL_IMAGE_BYTES = 1 << 30
MAX_WORD_OPERATIONS_PER_FRAME = 32_000

HELLO = 1
STATUS = 2
IMPORT_IMAGE = 3
BEGIN_CANDIDATE = 4
APPLY_WORD_OPS = 5
EXPORT_CANDIDATE = 6
CONFIRM_CACHE = 7
DISCARD_CANDIDATE = 8
PROBE_VULKAN = 9
SHUTDOWN = 10
DETACH_OWNER = 11
REGISTER_MODEL = 12
STEP_MODEL = 13
DROP_MODEL_TASK = 14
IMPORT_IMAGE_INFO = 15
IMPORT_IMAGE_CHUNK = 16
FINISH_IMAGE_IMPORT = 17
CANCEL_IMAGE_IMPORT = 18
EXPORT_CANDIDATE_INFO = 19
EXPORT_CANDIDATE_CHUNK = 20
APPLY_CANDIDATE_PAGE = 21
REDUCE_CANDIDATE = 22
CREATE_GROUP = 23
STEP_GROUP = 24
DROP_GROUP = 25
GRAPH_SITE_PREFLIGHT = 26
LEAVE_GROUP = 27
JOIN_GROUP = 28
GRAPH_SITE_WIRE_VERSION = 3
GRAPH_SITE_RECEIPT_WIRE_VERSION = 3
MAX_GRAPH_SITE_TEXT = 4096
MAX_GRAPH_SITE_VECTOR = MAX_FRAME_BODY // 4
RESPONSE_BIT = 0x8000
ERROR = 0xFFFF

WIRE_BYTES = 1
WIRE_UTF8 = 2
WIRE_U64 = 3

# Names for the calls ordinary work makes, so a trace row reads as the field
# operation rather than as a number.  Other kinds keep their numeric identity.
_REQUEST_KIND_NAMES = {
    STATUS: "status",
    PROBE_VULKAN: "probe-vulkan",
    REGISTER_MODEL: "register-model",
    STEP_MODEL: "step-model",
    DROP_MODEL_TASK: "drop-model-task",
    CONFIRM_CACHE: "confirm-cache",
    CREATE_GROUP: "create-group",
    STEP_GROUP: "step-group",
    DROP_GROUP: "drop-group",
    GRAPH_SITE_PREFLIGHT: "graph-site-preflight",
}


def _active_work_trace() -> Any | None:
    """The active CassiFI work trace, or None when ordinary work is untraced.

    The trace is optional observability: a client without the CassiFI root
    importable, or without a caller that asked for a trace, records nothing and
    changes no wire behavior.
    """
    try:
        from cassi_work_trace import active_trace
    except ImportError:  # pragma: no cover - trace is optional for this client
        return None
    try:
        return active_trace()
    except Exception:  # pragma: no cover - a broken trace must not fail work
        return None


def _trace_record(
    trace: Any | None,
    kind: str,
    name: str,
    duration_ns: int = 0,
    **fields: Any,
) -> None:
    if trace is None:
        return
    try:
        trace.record(kind, name, duration_ns, **fields)
    except Exception:
        pass


class NativeFieldRuntimeError(ValueError):
    """The native service rejected a frame, identity, or candidate operation."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 512:
        raise NativeFieldRuntimeError(f"{label} must be bounded nonempty text")
    return value


def _digest(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise NativeFieldRuntimeError(f"{label} must be a lowercase sha256 digest")
    return value


def _body(fields: Sequence[tuple[int, int, bytes]]) -> bytes:
    result = bytearray()
    prior = 0
    for tag, wire, value in fields:
        if not 0 < tag <= 0xFFFF or tag <= prior:
            raise NativeFieldRuntimeError("body tags must be unique and ascending")
        if wire not in {WIRE_BYTES, WIRE_UTF8, WIRE_U64}:
            raise NativeFieldRuntimeError("body wire type is unsupported")
        if len(value) > MAX_FIELD_BYTES:
            raise NativeFieldRuntimeError("body field exceeds its bound")
        result.extend(struct.pack("<HHI", tag, wire, len(value)))
        result.extend(value)
        prior = tag
    if len(result) > MAX_FRAME_BODY:
        raise NativeFieldRuntimeError("frame body exceeds its bound")
    return bytes(result)


def _bytes(tag: int, value: bytes) -> tuple[int, int, bytes]:
    return tag, WIRE_BYTES, bytes(value)


def _utf8(tag: int, value: str) -> tuple[int, int, bytes]:
    return tag, WIRE_UTF8, _text(value, f"field {tag}").encode("utf-8")


def _u64(tag: int, value: int) -> tuple[int, int, bytes]:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise NativeFieldRuntimeError(f"field {tag} must be an unsigned 64-bit integer")
    return tag, WIRE_U64, struct.pack("<Q", value)


def _decode_body(data: bytes) -> dict[int, tuple[int, bytes]]:
    cursor = 0
    prior = 0
    result: dict[int, tuple[int, bytes]] = {}
    while cursor < len(data):
        if len(data) - cursor < 8:
            raise NativeFieldRuntimeError("native response contains a truncated field")
        tag, wire, size = struct.unpack_from("<HHI", data, cursor)
        cursor += 8
        if tag <= prior or wire not in {WIRE_BYTES, WIRE_UTF8, WIRE_U64} or size > len(data) - cursor:
            raise NativeFieldRuntimeError("native response field is invalid")
        result[tag] = (wire, data[cursor : cursor + size])
        cursor += size
        prior = tag
    return result


def _field_text(fields: dict[int, tuple[int, bytes]], tag: int) -> str:
    try:
        wire, value = fields[tag]
    except KeyError as exc:
        raise NativeFieldRuntimeError(f"native response is missing field {tag}") from exc
    if wire != WIRE_UTF8:
        raise NativeFieldRuntimeError(f"native response field {tag} has the wrong type")
    return value.decode("utf-8")


def _field_u64(fields: dict[int, tuple[int, bytes]], tag: int) -> int:
    try:
        wire, value = fields[tag]
    except KeyError as exc:
        raise NativeFieldRuntimeError(f"native response is missing field {tag}") from exc
    if wire != WIRE_U64 or len(value) != 8:
        raise NativeFieldRuntimeError(f"native response field {tag} has the wrong type")
    return struct.unpack("<Q", value)[0]


def _field_bytes(fields: dict[int, tuple[int, bytes]], tag: int) -> bytes:
    try:
        wire, value = fields[tag]
    except KeyError as exc:
        raise NativeFieldRuntimeError(f"native response is missing field {tag}") from exc
    if wire != WIRE_BYTES:
        raise NativeFieldRuntimeError(f"native response field {tag} has the wrong type")
    return value
def _canonical_json_sha256(value: Any, label: str) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise NativeFieldRuntimeError(f"{label} is not canonical JSON") from exc
    return hashlib.sha256(payload).hexdigest()


def _graph_site_text(value: Any, label: str) -> bytes:
    if not isinstance(value, str):
        raise NativeFieldRuntimeError(f"{label} must be text")
    encoded = value.encode("utf-8")
    if len(encoded) > MAX_GRAPH_SITE_TEXT:
        raise NativeFieldRuntimeError(f"{label} exceeds its graph-site bound")
    return struct.pack("<I", len(encoded)) + encoded


def _graph_site_u32(value: Any, label: str) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFF:
        raise NativeFieldRuntimeError(f"{label} is outside uint32 range")
    return struct.pack("<I", value)


def _graph_site_i32(value: Any, label: str) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int) or not -(1 << 31) <= value < (1 << 31):
        raise NativeFieldRuntimeError(f"{label} is outside int32 range")
    return struct.pack("<i", value)
def _graph_site_u32_value(value: Any, label: str) -> int:
    return struct.unpack("<I", _graph_site_u32(value, label))[0]


def _graph_site_i32_value(value: Any, label: str) -> int:
    return struct.unpack("<i", _graph_site_i32(value, label))[0]


def _graph_site_u64(value: Any, label: str) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise NativeFieldRuntimeError(f"{label} is outside uint64 range")
    return struct.pack("<Q", value)


def _graph_site_float(value: Any, label: str) -> bytes:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise NativeFieldRuntimeError(f"{label} must be finite")
    return struct.pack("<f", float(value))


def _graph_site_double(value: Any, label: str) -> bytes:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise NativeFieldRuntimeError(f"{label} must be finite")
    return struct.pack("<d", float(value))


def _graph_site_float_vector(value: Any, label: str) -> bytes:
    array = np.asarray(value, dtype="<f4")
    if array.ndim != 1 or array.size > MAX_GRAPH_SITE_VECTOR or not np.isfinite(array).all():
        raise NativeFieldRuntimeError(f"{label} must be a bounded finite float vector")
    return struct.pack("<I", int(array.size)) + array.tobytes(order="C")


def _graph_site_i32_vector(value: Any, label: str) -> bytes:
    array = np.asarray(value)
    if (
        array.ndim != 1
        or array.dtype.kind not in {"i", "u"}
        or array.size > MAX_GRAPH_SITE_VECTOR
        or (array.size and (int(array.min()) < -(1 << 31) or int(array.max()) >= (1 << 31)))
    ):
        raise NativeFieldRuntimeError(f"{label} must be a bounded int32 vector")
    return struct.pack("<I", int(array.size)) + array.astype("<i4", copy=False).tobytes(order="C")


class _GraphSiteReader:
    def __init__(self, payload: bytes):
        if not payload or len(payload) > MAX_FRAME_BODY:
            raise NativeFieldRuntimeError("graph-site payload size is invalid")
        self.payload = payload
        self.cursor = 0

    def _take(self, size: int) -> bytes:
        if size < 0 or size > len(self.payload) - self.cursor:
            raise NativeFieldRuntimeError("graph-site payload is truncated")
        result = self.payload[self.cursor : self.cursor + size]
        self.cursor += size
        return result

    def u8(self) -> int:
        return self._take(1)[0]

    def u32(self) -> int:
        return struct.unpack("<I", self._take(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self._take(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self._take(8))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self._take(4))[0]

    def f64(self) -> float:
        return struct.unpack("<d", self._take(8))[0]

    def text(self) -> str:
        size = self.u32()
        if size > MAX_GRAPH_SITE_TEXT:
            raise NativeFieldRuntimeError("graph-site text exceeds its bound")
        try:
            return self._take(size).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NativeFieldRuntimeError("graph-site text is not UTF-8") from exc

    def float_vector(self) -> list[float]:
        count = self.u32()
        if count > MAX_GRAPH_SITE_VECTOR:
            raise NativeFieldRuntimeError("graph-site float vector exceeds its bound")
        values = np.frombuffer(self._take(count * 4), dtype="<f4")
        if not np.isfinite(values).all():
            raise NativeFieldRuntimeError("graph-site float vector is non-finite")
        return values.astype(float, copy=True).tolist()

    def i32_vector(self) -> list[int]:
        count = self.u32()
        if count > MAX_GRAPH_SITE_VECTOR:
            raise NativeFieldRuntimeError("graph-site integer vector exceeds its bound")
        return np.frombuffer(self._take(count * 4), dtype="<i4").astype(int, copy=True).tolist()

    def text_vector(self) -> list[str]:
        count = self.u32()
        if count > MAX_GRAPH_SITE_VECTOR:
            raise NativeFieldRuntimeError("graph-site text vector exceeds its bound")
        return [self.text() for _ in range(count)]

    def finish(self) -> None:
        if self.cursor != len(self.payload):
            raise NativeFieldRuntimeError("graph-site payload has trailing bytes")

def _normalized_graph_site_sampler(value: Any) -> tuple[dict[str, Any], str]:
    if not isinstance(value, Mapping) or set(value) != {"mode", "temperature", "top_k", "draw"}:
        raise NativeFieldRuntimeError("native graph-site sampler has unsupported or missing fields")
    mode = value["mode"]
    temperature = value["temperature"]
    top_k = value["top_k"]
    draw = value["draw"]
    if not isinstance(mode, str) or mode not in {"greedy", "categorical"}:
        raise NativeFieldRuntimeError("native graph-site sampler mode is unsupported")
    if mode == "greedy":
        normalized = {
            "mode": "greedy",
            "temperature": 1.0,
            "top_k": 0,
            "draw": 0.0,
        }
        return normalized, _canonical_json_sha256(normalized, "native graph-site sampler")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
        raise NativeFieldRuntimeError("native graph-site sampler temperature is invalid")
    try:
        temperature = struct.unpack("<f", struct.pack("<f", float(temperature)))[0]
    except (OverflowError, ValueError, struct.error) as exc:
        raise NativeFieldRuntimeError(
            "native graph-site sampler temperature overflows the C API float32"
        ) from exc
    if not math.isfinite(temperature) or temperature <= 0.0:
        raise NativeFieldRuntimeError(
            "native graph-site sampler temperature is invalid after C API float32 conversion"
        )
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 0 <= top_k <= 0xFFFFFFFF:
        raise NativeFieldRuntimeError("native graph-site sampler top_k is invalid")
    if isinstance(draw, bool) or not isinstance(draw, (int, float)):
        raise NativeFieldRuntimeError("native graph-site sampler draw is invalid")
    try:
        draw = struct.unpack("<d", struct.pack("<d", float(draw)))[0]
    except (OverflowError, ValueError, struct.error) as exc:
        raise NativeFieldRuntimeError(
            "native graph-site sampler draw is not representable as a C API double"
        ) from exc
    if not math.isfinite(draw) or not 0.0 <= draw < 1.0:
        raise NativeFieldRuntimeError("native graph-site sampler draw is invalid")
    normalized = {
        "mode": "categorical",
        "temperature": temperature,
        "top_k": int(top_k),
        "draw": draw,
    }
    return normalized, _canonical_json_sha256(normalized, "native graph-site sampler")


def _graph_ticket_value(mapping: Mapping[str, Any], key: str) -> Any:
    try:
        return mapping[key]
    except KeyError as exc:
        raise NativeFieldRuntimeError(f"native graph-site ticket is missing {key}") from exc


def _encode_graph_site_candidate(ticket: Mapping[str, Any]) -> bytes:
    if not isinstance(ticket, Mapping):
        raise NativeFieldRuntimeError("native graph-site ticket must be a mapping")
    candidate = _graph_ticket_value(ticket, "native_candidate")
    guard = _graph_ticket_value(ticket, "native_guard")
    sampler, sampler_sha256 = _normalized_graph_site_sampler(_graph_ticket_value(ticket, "sampler"))
    if not isinstance(candidate, Mapping) or not isinstance(guard, Mapping):
        raise NativeFieldRuntimeError("native graph-site program and guard must be mappings")
    if ticket.get("request_sha256_pending") is not True:
        raise NativeFieldRuntimeError("native graph-site ticket must defer request hashing until stage evaluation")
    if _digest(_graph_ticket_value(ticket, "sampler_sha256"), "sampler_sha256") != sampler_sha256:
        raise NativeFieldRuntimeError("native graph-site sampler hash disagrees with its exact tuple")
    if _graph_ticket_value(candidate, "request_sha256") != "":
        raise NativeFieldRuntimeError("native graph-site program must have an empty deferred request hash")

    payload = bytearray()

    def text(mapping: Mapping[str, Any], key: str) -> None:
        payload.extend(_graph_site_text(_graph_ticket_value(mapping, key), key))

    def u32(mapping: Mapping[str, Any], key: str) -> None:
        payload.extend(_graph_site_u32(_graph_ticket_value(mapping, key), key))

    def i32(mapping: Mapping[str, Any], key: str) -> None:
        payload.extend(_graph_site_i32(_graph_ticket_value(mapping, key), key))

    def u64(mapping: Mapping[str, Any], key: str) -> None:
        payload.extend(_graph_site_u64(_graph_ticket_value(mapping, key), key))

    payload.extend(struct.pack("<I", GRAPH_SITE_WIRE_VERSION))
    for key in (
        "ticket_id",
        "ticket_sha256",
        "preflight_sha256",
        "native_preflight_sha256",
        "source_sha256",
        "model_sha256",
        "tokenizer_sha256",
        "task_id",
        "sequence_id",
        "native_operation_id",
        "native_predecessor_sha256",
    ):
        value = _graph_ticket_value(ticket, key)
        payload.extend(_graph_site_text(value, key))
    payload.extend(_graph_site_text(_graph_ticket_value(ticket, "field_state_sha256"), "field_state_sha256"))
    payload.extend(_graph_site_text(_graph_ticket_value(ticket, "native_field_epoch_sha256"), "native_field_epoch_sha256"))
    payload.extend(_graph_site_text(_graph_ticket_value(ticket, "field_epoch_sha256"), "field_epoch_sha256"))
    payload.extend(b"\x01")
    payload.extend(_graph_site_text(sampler_sha256, "sampler_sha256"))
    payload.extend(_graph_site_text(sampler["mode"], "sampler.mode"))
    payload.extend(_graph_site_double(sampler["temperature"], "sampler.temperature"))
    payload.extend(_graph_site_u32(sampler["top_k"], "sampler.top_k"))
    payload.extend(_graph_site_double(sampler["draw"], "sampler.draw"))
    for key in ("kind",):
        u32(candidate, key)
    for key in ("seq_id", "position", "layer"):
        i32(candidate, key)
    u64(candidate, "owner_generation")
    u64(candidate, "predecessor_generation")
    for key in (
        "sequence_id",
        "source_sha256",
        "architecture",
        "backend",
        "input_tensor",
        "output_tensor",
        "tensor_dtype",
        "stage",
        "site",
        "specialist",
        "predecessor_sha256",
        "request_sha256",
        "invocation_sha256",
        "candidate_sha256",
        "intervention_order",
        "dependencies_json",
        "method_key",
    ):
        text(candidate, key)
    u64(candidate, "method_generation")
    for key in ("input_width", "rank", "output_width"):
        u32(candidate, key)
    for key in ("a", "b", "bias"):
        payload.extend(_graph_site_float_vector(_graph_ticket_value(candidate, key), key))
    for key in (
        "conv_history_rows",
        "conv_history_channels",
        "recurrent_state_heads",
        "recurrent_state_value_width",
        "recurrent_state_key_width",
        "attn_kv_heads",
        "attn_kv_head_width",
    ):
        u32(candidate, key)
    u32(guard, "verb")
    for key in (
        "candidate_id",
        "owner_snapshot_sha256",
        "field_epoch_sha256",
        "native_predecessor_sha256",
        "native_preflight_sha256",
    ):
        text(guard, key)
    payload.extend(_graph_site_float_vector(_graph_ticket_value(guard, "input_support_anchor"), "input_support_anchor"))
    payload.extend(_graph_site_float(_graph_ticket_value(guard, "input_support_radius"), "input_support_radius"))
    payload.extend(_graph_site_float(_graph_ticket_value(guard, "input_support_anchor_norm"), "input_support_anchor_norm"))
    payload.extend(_graph_site_i32_vector(_graph_ticket_value(guard, "expected_expert_ids"), "expected_expert_ids"))
    if len(payload) > MAX_FRAME_BODY:
        raise NativeFieldRuntimeError("native graph-site ticket exceeds its frame bound")
    return bytes(payload)
def _decode_graph_site_preflight(payload: bytes) -> dict[str, Any]:
    reader = _GraphSiteReader(payload)
    version = reader.u32()
    ready_byte = reader.u8()
    if ready_byte not in {0, 1}:
        raise NativeFieldRuntimeError("native graph-site readiness marker is invalid")
    result: dict[str, Any] = {
        "version": version,
        "ready": bool(ready_byte),
        "native_seq_id": reader.i32(),
        "next_position": reader.i32(),
        "context_limit": reader.u32(),
        "remaining_tokens": reader.u32(),
        "model_embedding_width": reader.u32(),
        "model_layer_count": reader.u32(),
        "task_id": reader.text(),
        "sequence_id": reader.text(),
        "native_operation_id": reader.text(),
        "source_sha256": reader.text(),
        "model_sha256": reader.text(),
        "tokenizer_sha256": reader.text(),
        "native_predecessor_sha256": reader.text(),
        "native_field_epoch_sha256": reader.text(),
        "native_preflight_sha256": reader.text(),
        "sampler_sha256": reader.text(),
        "sampler_mode": reader.text(),
        "sampler_temperature": reader.f64(),
        "sampler_top_k": reader.u32(),
        "sampler_draw": reader.f64(),
        "refusal": reader.text(),
    }
    count = reader.u32()
    if result["version"] != GRAPH_SITE_WIRE_VERSION or count > 4096:
        raise NativeFieldRuntimeError("native graph-site preflight metadata is invalid")
    sites: list[dict[str, Any]] = []
    seen_sites: set[tuple[int, int, str, str]] = set()
    for _ in range(count):
        kind = reader.u32()
        supported_byte = reader.u8()
        if supported_byte not in {0, 1}:
            raise NativeFieldRuntimeError("native graph-site support marker is invalid")
        descriptor = {
            "kind": kind,
            "supported": bool(supported_byte),
            "layer": reader.i32(),
            "input_width": reader.u32(),
            "output_width": reader.u32(),
            "stage": reader.text(),
            "site": reader.text(),
            "specialist": reader.text(),
            "input_tensor": reader.text(),
            "output_tensor": reader.text(),
            "dependencies_json": reader.text(),
            "refusal": reader.text(),
        }
        identity = (
            descriptor["kind"],
            descriptor["layer"],
            descriptor["stage"],
            descriptor["site"],
        )
        if identity in seen_sites:
            raise NativeFieldRuntimeError("native graph-site preflight repeats a site")
        seen_sites.add(identity)
        sites.append(descriptor)
    reader.finish()
    result["sites"] = sites
    sampler, sampler_sha = _normalized_graph_site_sampler(
        {
            "mode": result["sampler_mode"],
            "temperature": result["sampler_temperature"],
            "top_k": result["sampler_top_k"],
            "draw": result["sampler_draw"],
        }
    )
    result["sampler"] = sampler
    if result["ready"]:
        if sampler_sha != _digest(result["sampler_sha256"], "sampler_sha256"):
            raise NativeFieldRuntimeError("native graph-site preflight sampler hash disagrees")
        for name in (
            "source_sha256",
            "model_sha256",
            "tokenizer_sha256",
            "native_predecessor_sha256",
            "native_field_epoch_sha256",
            "native_preflight_sha256",
        ):
            result[name] = _digest(result[name], name)
        if (
            not result["task_id"]
            or not result["sequence_id"]
            or not result["native_operation_id"]
            or result["native_seq_id"] < 0
            or result["model_embedding_width"] == 0
            or result["model_layer_count"] == 0
            or result["next_position"] < 0
            or result["context_limit"] == 0
            or result["next_position"] > result["context_limit"]
            or result["remaining_tokens"] != result["context_limit"] - result["next_position"]
        ):
            raise NativeFieldRuntimeError("native graph-site preflight identity or context is invalid")
    return result


def _decode_graph_site_receipt(payload: bytes) -> dict[str, Any]:
    reader = _GraphSiteReader(payload)
    result: dict[str, Any] = {
        "schema": "cassifi.native-graph-site-receipt.v1",
        "version": reader.u32(),
        "ticket_id": reader.text(),
        "field_candidate_id": reader.text(),
        "ticket_sha256": reader.text(),
        "preflight_sha256": reader.text(),
        "native_preflight_sha256": reader.text(),
        "source_sha256": reader.text(),
        "model_sha256": reader.text(),
        "tokenizer_sha256": reader.text(),
        "task_id": reader.text(),
        "sequence_id": reader.text(),
        "native_operation_id": reader.text(),
        "seq_id": reader.i32(),
        "position": reader.i32(),
        "selected_token_id": reader.i32(),
        "input_token_count": reader.u64(),
        "input_tokens_sha256": reader.text(),
        "replay_sha256": reader.text(),
        "token_count": reader.u64(),
        "stage": reader.text(),
        "layer": reader.i32(),
        "site": reader.text(),
        "specialist": reader.text(),
        "invocation_sha256": reader.text(),
        "request_sha256": reader.text(),
        "candidate_sha256": reader.text(),
        "dependencies_json": reader.text(),
        "method_key": reader.text(),
        "method_generation": reader.u64(),
        "intervention_order": reader.text(),
        "graph_predecessor_sha256": reader.text(),
        "owner_snapshot_sha256": reader.text(),
        "owner_field_epoch_sha256": reader.text(),
        "native_field_epoch_sha256": reader.text(),
        "native_predecessor_sha256": reader.text(),
        "sampler_sha256": reader.text(),
        "sampler_mode": reader.text(),
        "sampler_temperature": reader.f64(),
        "sampler_top_k": reader.u32(),
        "sampler_draw": reader.f64(),
        "input_sha256": reader.text(),
        "output_sha256": reader.text(),
        "expected_expert_ids": reader.i32_vector(),
        "actual_expert_ids": reader.i32_vector(),
        "stage_trace": reader.text_vector(),
        "stage_trace_sha256": reader.text(),
        "candidate_successor_sha256": reader.text(),
        "native_successor_sha256": reader.text(),
        "successor_state_json": reader.text(),
        "refusal": reader.text(),
        "attempted": reader.u8(),
        "admitted": reader.u8(),
        "owner_generation": reader.u64(),
        "operators_omitted": reader.u64(),
        "weights_omitted": reader.u64(),
        "weight_bytes_omitted": reader.u64(),
        "transfer_bytes_omitted": reader.u64(),
        "added_flops": reader.f64(),
    }
    reader.finish()
    admitted = result["admitted"]
    if (
        result["version"] != GRAPH_SITE_RECEIPT_WIRE_VERSION
        or result["attempted"] != 1
        or admitted not in {0, 1}
        or (admitted == 1 and result["refusal"])
        or (admitted == 0 and not result["refusal"])
        or any(expert_id < 0 for expert_id in result["actual_expert_ids"])
    ):
        raise NativeFieldRuntimeError("native graph-site receipt decision or route evidence is invalid")
    result["attempted"] = True
    result["admitted"] = bool(admitted)
    required_hashes = [
        "ticket_sha256",
        "preflight_sha256",
        "native_preflight_sha256",
        "source_sha256",
        "model_sha256",
        "tokenizer_sha256",
        "input_tokens_sha256",
        "invocation_sha256",
        "candidate_sha256",
        "graph_predecessor_sha256",
        "owner_snapshot_sha256",
        "owner_field_epoch_sha256",
        "native_field_epoch_sha256",
        "native_predecessor_sha256",
        "sampler_sha256",
    ]
    if admitted:
        required_hashes.extend(
            (
                "replay_sha256",
                "request_sha256",
                "input_sha256",
                "output_sha256",
                "candidate_successor_sha256",
                "native_successor_sha256",
            )
        )
    for name in required_hashes:
        result[name] = _digest(result[name], name)
    if admitted:
        if (
            result["successor_state_json"] == ""
            or not result["stage_trace"]
            or any(not entry for entry in result["stage_trace"])
            or _canonical_json_sha256(result["stage_trace"], "native graph-site stage trace")
            != _digest(result["stage_trace_sha256"], "stage_trace_sha256")
        ):
            raise NativeFieldRuntimeError("admitted native graph-site receipt lacks measured successor or stage trace")
    else:
        for name in ("request_sha256", "input_sha256", "output_sha256"):
            if result[name]:
                result[name] = _digest(result[name], name)
        if (
            result["selected_token_id"] != -1
            or result["token_count"] != 0
            or result["replay_sha256"]
            or result["candidate_successor_sha256"]
            or result["native_successor_sha256"]
            or result["successor_state_json"]
        ):
            raise NativeFieldRuntimeError("rejected native graph-site receipt carries admitted successor state")
        if result["stage_trace"]:
            if (
                any(not entry for entry in result["stage_trace"])
                or _canonical_json_sha256(result["stage_trace"], "rejected graph-site partial trace")
                != _digest(result["stage_trace_sha256"], "stage_trace_sha256")
            ):
                raise NativeFieldRuntimeError("rejected native graph-site partial trace digest disagrees")
        elif result["stage_trace_sha256"]:
            raise NativeFieldRuntimeError("rejected native graph-site empty trace carries a digest")
    sampler, sampler_sha = _normalized_graph_site_sampler(
        {
            "mode": result["sampler_mode"],
            "temperature": result["sampler_temperature"],
            "top_k": result["sampler_top_k"],
            "draw": result["sampler_draw"],
        }
    )
    if sampler_sha != result["sampler_sha256"]:
        raise NativeFieldRuntimeError("native graph-site receipt sampler hash disagrees")
    result["sampler"] = sampler
    if (
        not math.isfinite(result["added_flops"])
        or result["seq_id"] < 0
        or result["position"] < 0
        or result["input_token_count"] == 0
        or (result["admitted"] and (result["selected_token_id"] < 0 or result["token_count"] == 0))
        or (not result["admitted"] and result["token_count"] != 0)
    ):
        raise NativeFieldRuntimeError("native graph-site receipt counters are invalid")
    if not all(
        result[name]
        for name in (
            "ticket_id",
            "field_candidate_id",
            "task_id",
            "sequence_id",
            "stage",
            "site",
            "specialist",
            "method_key",
        )
    ):
        raise NativeFieldRuntimeError("native graph-site receipt identity is incomplete")
    return result


def _validate_graph_site_route_evidence(
    receipt: Mapping[str, Any],
    ticket: Mapping[str, Any],
) -> None:
    candidate = _graph_ticket_value(ticket, "native_candidate")
    guard = _graph_ticket_value(ticket, "native_guard")
    if not isinstance(candidate, Mapping) or not isinstance(guard, Mapping):
        raise NativeFieldRuntimeError("native graph-site ticket lacks its route program or guard")
    kind = _graph_site_u32_value(candidate.get("kind"), "candidate.kind")
    actual_ids = receipt.get("actual_expert_ids")
    expected_route = _graph_site_i32_vector(
        _graph_ticket_value(guard, "expected_expert_ids"),
        "expected_expert_ids",
    )
    expected_ids = np.frombuffer(expected_route, dtype="<i4", offset=4).astype(int, copy=True).tolist()
    if (
        not isinstance(actual_ids, list)
        or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in actual_ids)
        or any(value < 0 for value in expected_ids)
    ):
        raise NativeFieldRuntimeError("native graph-site expert route evidence is invalid")
    if kind == 1:
        if not expected_ids:
            raise NativeFieldRuntimeError("expert graph-site guard has no expected route ids")
        if receipt.get("admitted") and (not actual_ids or actual_ids != list(expected_ids)):
            raise NativeFieldRuntimeError("admitted expert route differs from its ordered guard ids")
    elif kind in (2, 3, 6):
        if expected_ids or actual_ids:
            raise NativeFieldRuntimeError("native graph-site receipt unexpectedly carries expert route ids")
    else:
        raise NativeFieldRuntimeError("native graph-site ticket has an unsupported candidate kind")


def _graph_successor_state_sha256(
    receipt: Mapping[str, Any],
    *,
    candidate: Mapping[str, Any],
    preflight: Mapping[str, Any],
) -> str:
    raw_state = receipt.get("successor_state_json")
    if not isinstance(raw_state, str) or not raw_state:
        raise NativeFieldRuntimeError("native graph-site receipt lacks its measured successor state")
    try:
        state = json.loads(raw_state)
    except (TypeError, ValueError) as exc:
        raise NativeFieldRuntimeError("native graph-site successor state is invalid JSON") from exc
    if not isinstance(state, Mapping):
        raise NativeFieldRuntimeError("native graph-site successor state must be a mapping")
    layer = _graph_site_i32_value(candidate.get("layer"), "candidate.layer")
    layer_count = _graph_site_u32_value(preflight.get("model_layer_count"), "model_layer_count")
    embedding_width = _graph_site_u32_value(
        preflight.get("model_embedding_width"), "model_embedding_width"
    )
    kind = _graph_site_u32_value(candidate.get("kind"), "candidate.kind")
    if (
        embedding_width == 0
        or (kind == 6 and layer != -1)
        or (kind != 6 and (layer < 0 or layer >= layer_count))
    ):
        raise NativeFieldRuntimeError("native graph-site successor model geometry is invalid")
    if kind == 1:
        expected_shapes = {"expert_output": [embedding_width]}
    elif kind == 2:
        expected_shapes = {
            "hidden": [embedding_width],
            f"conv_history.{layer}": [
                _graph_site_u32_value(candidate.get("conv_history_rows"), "conv_history_rows"),
                _graph_site_u32_value(candidate.get("conv_history_channels"), "conv_history_channels"),
            ],
            f"recurrent_state.{layer}": [
                _graph_site_u32_value(candidate.get("recurrent_state_heads"), "recurrent_state_heads"),
                _graph_site_u32_value(
                    candidate.get("recurrent_state_value_width"),
                    "recurrent_state_value_width",
                ),
                _graph_site_u32_value(
                    candidate.get("recurrent_state_key_width"),
                    "recurrent_state_key_width",
                ),
            ],
        }
    elif kind == 3:
        kv_heads = _graph_site_u32_value(candidate.get("attn_kv_heads"), "attn_kv_heads")
        kv_head_width = _graph_site_u32_value(candidate.get("attn_kv_head_width"), "attn_kv_head_width")
        expected_shapes = {
            "hidden": [embedding_width],
            f"kv_k.{layer}": [kv_heads, kv_head_width],
            f"kv_v.{layer}": [kv_heads, kv_head_width],
        }
    elif kind == 6:
        vocab_size = _graph_site_u32_value(candidate.get("output_width"), "candidate.output_width")
        expected_shapes = {"logits": [vocab_size]}
    else:
        raise NativeFieldRuntimeError("native graph-site successor candidate kind is unsupported")
    if any(any(dimension == 0 for dimension in shape) for shape in expected_shapes.values()):
        raise NativeFieldRuntimeError("native graph-site successor tensor dimensions are invalid")
    if set(state) != set(expected_shapes):
        raise NativeFieldRuntimeError("native graph-site successor tensor names disagree with the candidate")
    for name, expected_shape in expected_shapes.items():
        descriptor = state[name]
        if not isinstance(descriptor, Mapping) or set(descriptor) != {
            "dtype",
            "order",
            "shape",
            "sha256",
        }:
            raise NativeFieldRuntimeError("native graph-site successor tensor descriptor is incomplete")
        shape = descriptor.get("shape")
        if (
            descriptor.get("dtype") != "<f4"
            or descriptor.get("order") != "C"
            or not isinstance(shape, list)
            or any(isinstance(size, bool) or not isinstance(size, int) for size in shape)
            or shape != expected_shape
        ):
            raise NativeFieldRuntimeError("native graph-site successor tensor layout disagrees with the model")
        _digest(descriptor.get("sha256"), f"{name}.sha256")
    if kind == 1:
        if _digest(state["expert_output"]["sha256"], "expert_output.sha256") != _digest(
            receipt.get("output_sha256"), "output_sha256"
        ):
            raise NativeFieldRuntimeError("native graph-site expert successor digest disagrees with its receipt")
    elif kind == 6:
        if _digest(state["logits"]["sha256"], "logits.sha256") != _digest(
            receipt.get("output_sha256"), "output_sha256"
        ):
            raise NativeFieldRuntimeError("native graph-site execution-choice successor digest disagrees with its receipt")
    successor_sha256 = _canonical_json_sha256(state, "native graph-site successor map")
    if successor_sha256 != receipt.get("candidate_successor_sha256"):
        raise NativeFieldRuntimeError("native graph-site successor map digest disagrees with its receipt")
    return successor_sha256


def _model_token_history(
    value: Sequence[int],
    *,
    allow_empty: bool = False,
) -> tuple[tuple[int, ...], bytes, str]:
    if isinstance(value, (str, bytes, bytearray, Mapping)) or not isinstance(value, Sequence):
        raise NativeFieldRuntimeError("model token history must be a sequence of integer tokens")
    if len(value) > MAX_GRAPH_SITE_VECTOR - 32 or (not value and not allow_empty):
        raise NativeFieldRuntimeError("model token history is empty or exceeds its frame bound")
    tokens: list[int] = []
    packed = bytearray()
    for token in value:
        if isinstance(token, bool) or not isinstance(token, int) or not 0 <= token <= 0x7FFFFFFF:
            raise NativeFieldRuntimeError("model token is outside int32 range")
        tokens.append(token)
        packed.extend(struct.pack("<i", token))
    token_bytes = bytes(packed)
    return tuple(tokens), token_bytes, hashlib.sha256(token_bytes).hexdigest()


def _model_sampler(
    sampler_mode: str,
    temperature: float,
    top_k: int,
    draw: float,
) -> tuple[dict[str, Any], str]:
    return _normalized_graph_site_sampler(
        {
            "mode": sampler_mode,
            "temperature": temperature,
            "top_k": top_k,
            "draw": draw,
        }
    )


def _graph_ticket_for_step(
    ticket: Mapping[str, Any],
    *,
    candidate_id: str | None,
    task_id: str,
    sequence_id: str,
    native_operation_id: str,
    source_sha256: str,
    preflight: Mapping[str, Any],
    sampler: Mapping[str, Any],
    sampler_sha256: str,
) -> bytes:
    packed = _encode_graph_site_candidate(ticket)
    _text(_graph_ticket_value(ticket, "model_task_id"), "model_task_id")
    candidate = _graph_ticket_value(ticket, "native_candidate")
    guard = _graph_ticket_value(ticket, "native_guard")
    expected = {
        "task_id": task_id,
        "sequence_id": sequence_id,
        "native_operation_id": native_operation_id,
        "source_sha256": source_sha256,
        "model_sha256": preflight["model_sha256"],
        "tokenizer_sha256": preflight["tokenizer_sha256"],
        "native_predecessor_sha256": preflight["native_predecessor_sha256"],
        "native_preflight_sha256": preflight["native_preflight_sha256"],
        "sampler_sha256": sampler_sha256,
    }
    for key, value in expected.items():
        if ticket.get(key) != value:
            raise NativeFieldRuntimeError(f"native graph-site ticket {key} disagrees with preflight")
    ticket_sampler, ticket_sampler_sha = _normalized_graph_site_sampler(
        _graph_ticket_value(ticket, "sampler")
    )
    if ticket_sampler != dict(sampler) or ticket_sampler_sha != sampler_sha256:
        raise NativeFieldRuntimeError("native graph-site ticket sampler disagrees with the exact step")
    candidate_kind = _graph_site_u32_value(candidate.get("kind"), "candidate.kind")
    candidate_layer = candidate.get("layer")
    layer_ok = (
        candidate_layer == -1
        if candidate_kind == 6
        else candidate_layer is not None and 0 <= candidate_layer < preflight["model_layer_count"]
    )
    if (
        candidate.get("sequence_id") != sequence_id
        or candidate.get("source_sha256") != source_sha256
        or candidate.get("seq_id") != preflight["native_seq_id"]
        or candidate.get("position") != preflight["next_position"]
        or not layer_ok
        or not candidate.get("predecessor_sha256")
    ):
        raise NativeFieldRuntimeError("native graph-site candidate identity or position is stale")
    if (
        guard.get("native_predecessor_sha256") != preflight["native_predecessor_sha256"]
        or guard.get("native_preflight_sha256") != preflight["native_preflight_sha256"]
    ):
        raise NativeFieldRuntimeError("native graph-site guard predecessor or preflight is stale")
    guard_candidate_id = _text(guard.get("candidate_id"), "ticket_id")
    ticket_id = _text(ticket.get("ticket_id"), "ticket_id")
    if guard_candidate_id != ticket_id:
        raise NativeFieldRuntimeError("native graph-site guard candidate id must identify its graph ticket")
    if candidate_id is not None:
        _text(candidate_id, "field_candidate_id")
    return packed


def _graph_replay_step_wire(
    step: Mapping[str, Any],
    *,
    sequence_index: int,
    native_operation_id: str,
    input_tokens: tuple[int, ...],
    input_tokens_sha256: str,
    sampler: Mapping[str, Any],
    sampler_sha256: str,
    accepted_token_id: int,
    replay_sha256: str,
    stage_trace_sha256: str,
    token_count: int,
) -> bytes:
    if not isinstance(step, Mapping):
        raise NativeFieldRuntimeError("owner replay step must be a mapping")
    ticket = step.get("graph_site_ticket")
    if ticket is None:
        raise NativeFieldRuntimeError("native replay wire carries graph-site rows only")
    if not isinstance(ticket, Mapping) or not isinstance(step.get("graph_site_receipt"), Mapping):
        raise NativeFieldRuntimeError("owner graph replay row lacks its immutable ticket or receipt")
    receipt = step["graph_site_receipt"]
    candidate = _graph_ticket_value(ticket, "native_candidate")
    preflight = _graph_ticket_value(ticket, "preflight")
    if not isinstance(preflight, Mapping):
        raise NativeFieldRuntimeError("owner replay graph ticket preflight is invalid")
    if (
        ticket.get("task_id") != step.get("task_id")
        or ticket.get("sequence_id") != step.get("sequence_id")
        or ticket.get("native_operation_id") != native_operation_id
        or ticket.get("source_sha256") != step.get("source_sha256")
        or candidate.get("sequence_id") != step.get("sequence_id")
        or candidate.get("source_sha256") != step.get("source_sha256")
        or candidate.get("seq_id") != step.get("seq_id")
        or candidate.get("position") != step.get("position")
        or preflight.get("task_id") != step.get("task_id")
        or preflight.get("sequence_id") != step.get("sequence_id")
        or preflight.get("native_operation_id") != native_operation_id
        or preflight.get("source_sha256") != step.get("source_sha256")
        or preflight.get("sampler") != sampler
        or preflight.get("sampler_sha256") != sampler_sha256
        or receipt.get("task_id") != step.get("task_id")
        or receipt.get("sequence_id") != step.get("sequence_id")
        or receipt.get("native_operation_id") != native_operation_id
        or receipt.get("seq_id") != step.get("seq_id")
        or receipt.get("position") != step.get("position")
        or receipt.get("source_sha256") != step.get("source_sha256")
        or receipt.get("sampler") != sampler
        or receipt.get("sampler_sha256") != sampler_sha256
        or receipt.get("preflight_sha256") != ticket.get("preflight_sha256")
    ):
        raise NativeFieldRuntimeError("owner replay graph source, sequence, or ticket identity disagrees")
    ticket_sha256 = _digest(_graph_ticket_value(ticket, "ticket_sha256"), "ticket_sha256")
    receipt_sha256 = _digest(
        step.get("native_graph_site_receipt_sha256"),
        "native_graph_site_receipt_sha256",
    )
    receipt_wire_sha256 = _digest(
        step.get("native_graph_site_receipt_wire_sha256"),
        "native_graph_site_receipt_wire_sha256",
    )
    if _canonical_json_sha256(receipt, "graph-site replay receipt") != receipt_sha256:
        raise NativeFieldRuntimeError("owner graph replay canonical receipt digest disagrees")
    field_candidate_id = _text(step.get("field_candidate_id"), "field_candidate_id")
    if receipt.get("field_candidate_id") != field_candidate_id:
        raise NativeFieldRuntimeError("owner graph replay physical candidate id disagrees with receipt")
    field_predecessor = _digest(
        step.get("field_predecessor_sha256"),
        "field_predecessor_sha256",
    )
    _digest(step.get("field_successor_sha256"), "field_successor_sha256")
    if (
        field_predecessor != _digest(
            _graph_ticket_value(ticket, "field_state_sha256"),
            "field_state_sha256",
        )
        or field_predecessor != _digest(
            _graph_ticket_value(ticket, "graph_predecessor_sha256"),
            "graph_predecessor_sha256",
        )
        or receipt.get("ticket_id") != _graph_ticket_value(ticket, "ticket_id")
        or receipt.get("ticket_sha256") != ticket_sha256
    ):
        raise NativeFieldRuntimeError("owner graph replay field or ticket anchor disagrees")
    owner_predecessor = _digest(
        _graph_ticket_value(candidate, "predecessor_sha256"),
        "owner_predecessor_sha256",
    )
    owner_successor = _digest(
        _graph_ticket_value(receipt, "candidate_successor_sha256"),
        "owner_successor_sha256",
    )
    if (
        _digest(step.get("graph_successor_sha256"), "graph_successor_sha256")
        != owner_successor
    ):
        raise NativeFieldRuntimeError("owner graph replay successor digest disagrees with receipt")
    _graph_successor_state_sha256(
        receipt,
        candidate=candidate,
        preflight={
            "model_embedding_width": step.get("model_embedding_width"),
            "model_layer_count": step.get("model_layer_count"),
        },
    )
    native_predecessor = _digest(
        step.get("native_predecessor_sha256"),
        "native_predecessor_sha256",
    )
    native_successor = _digest(
        step.get("native_successor_sha256"),
        "native_successor_sha256",
    )
    native_preflight = _digest(
        step.get("native_preflight_sha256"),
        "native_preflight_sha256",
    )
    if (
        native_predecessor != _digest(
            _graph_ticket_value(ticket, "native_predecessor_sha256"),
            "native_predecessor_sha256",
        )
        or native_preflight != _digest(
            _graph_ticket_value(ticket, "native_preflight_sha256"),
            "native_preflight_sha256",
        )
        or receipt.get("native_predecessor_sha256") != native_predecessor
        or receipt.get("native_preflight_sha256") != native_preflight
        or receipt.get("native_successor_sha256") != native_successor
    ):
        raise NativeFieldRuntimeError("owner graph replay native checkpoint anchors disagree")
    ticket_payload = _encode_graph_site_candidate(ticket)
    history_complete = step.get("history_complete")
    if not isinstance(history_complete, bool):
        raise NativeFieldRuntimeError("owner replay history_complete must be a boolean")
    payload = bytearray(struct.pack("<I", GRAPH_SITE_WIRE_VERSION))
    payload.extend(_graph_site_u64(sequence_index, "sequence_index"))
    payload.extend(_graph_site_text(_text(native_operation_id, "native_operation_id"), "native_operation_id"))
    payload.extend(_graph_site_text(field_candidate_id, "field_candidate_id"))
    for value, label in (
        (owner_predecessor, "owner_predecessor_sha256"),
        (owner_successor, "owner_successor_sha256"),
        (native_predecessor, "native_predecessor_sha256"),
        (native_successor, "native_successor_sha256"),
        (native_preflight, "native_preflight_sha256"),
    ):
        payload.extend(_graph_site_text(value, label))
    payload.extend(_graph_site_u64(len(input_tokens), "input_token_count"))
    payload.extend(_graph_site_text(input_tokens_sha256, "input_tokens_sha256"))
    payload.extend(_graph_site_i32(accepted_token_id, "accepted_token_id"))
    payload.extend(_graph_site_text(sampler_sha256, "sampler_sha256"))
    payload.extend(_graph_site_text(sampler["mode"], "sampler.mode"))
    payload.extend(_graph_site_double(sampler["temperature"], "sampler.temperature"))
    payload.extend(_graph_site_u32(sampler["top_k"], "sampler.top_k"))
    payload.extend(_graph_site_double(sampler["draw"], "sampler.draw"))
    payload.extend(_graph_site_text(replay_sha256, "replay_sha256"))
    payload.extend(_graph_site_text(stage_trace_sha256, "stage_trace_sha256"))
    payload.extend(_graph_site_u64(token_count, "token_count"))
    payload.append(1 if history_complete else 0)
    payload.extend(_graph_site_text(ticket_sha256, "expected_ticket_sha256"))
    payload.extend(_graph_site_text(receipt_wire_sha256, "expected_graph_receipt_sha256"))
    payload.extend(
        _graph_site_text(
            receipt_sha256,
            "expected_native_graph_site_receipt_sha256",
        )
    )
    payload.extend(_graph_site_u32(len(ticket_payload), "ticket_payload_bytes"))
    payload.extend(ticket_payload)
    if len(payload) > MAX_FRAME_BODY:
        raise NativeFieldRuntimeError("owner replay step exceeds its frame bound")
    return bytes(payload)





def _optional_field_text(fields: dict[int, tuple[int, bytes]], tag: int) -> str | None:
    """Read an optional UTF-8 field; ``None`` when the native build omits it."""

    if tag not in fields:
        return None
    return _field_text(fields, tag)


def _optional_field_u64(fields: dict[int, tuple[int, bytes]], tag: int) -> int | None:
    """Read an optional u64 field; ``None`` when the native build omits it."""

    if tag not in fields:
        return None
    return _field_u64(fields, tag)


def _optional_field_identity(
    fields: dict[int, tuple[int, bytes]], tag: int
) -> str | None:
    """Read an optional identity field where the native sentinel means unknown."""

    value = _optional_field_text(fields, tag)
    if value == "unavailable":
        return None
    return value


def _device_report(
    *,
    device_index: int | None,
    device_identity: str | None,
    device_identity_kind: str | None,
    heap_total: int | None,
    heap_budget: int | None,
    heap_usage: int | None,
    memory_state: str | None,
    note: str | None,
) -> dict[str, Any]:
    """Structure one native per-device report with explicit unknowns.

    ``memory_state`` is the native truth marker: ``measured`` (heap and
    budget data available), ``heap-total-only`` (heap total present, no
    budget), ``unavailable``, or ``None`` when the native build reports
    no device memory state.  Budget and usage are only claimed under
    ``measured``; a heap total is only claimed when heaps are known to
    exist.  Nothing here is guessed from another API.
    """

    heaps_known = memory_state in {"measured", "heap-total-only"}
    budget_known = memory_state == "measured"
    return {
        "device_index": device_index,
        "device_identity": device_identity,
        "device_identity_kind": device_identity_kind,
        "heap_total_bytes": heap_total if heaps_known else None,
        "heap_budget_bytes": heap_budget if budget_known else None,
        "heap_usage_bytes": heap_usage if budget_known else None,
        "memory_state": memory_state,
        "note": note,
    }


def _optional_field_bool(
    fields: dict[int, tuple[int, bytes]], tag: int, name: str
) -> bool | None:
    value = _optional_field_u64(fields, tag)
    if value is None:
        return None
    if value not in {0, 1}:
        raise NativeFieldRuntimeError(f"native report {name} is not a boolean")
    return bool(value)


def _memory_report(
    fields: dict[int, tuple[int, bytes]],
    *,
    memory_state: str | None,
    heap_total: int | None,
    heap_budget: int | None,
    heap_usage: int | None,
    note: str | None,
    first_tag: int,
) -> dict[str, Any]:
    heaps_available = (
        None if memory_state is None else memory_state in {"measured", "heap-total-only"}
    )
    budget_available = None if memory_state is None else memory_state == "measured"
    memory_type_available = _optional_field_bool(
        fields, first_tag + 6, "gpu_field_memory_type_available"
    )
    memory_type_index: int | None = None
    heap_index: int | None = None
    memory_property_flags: int | None = None
    memory_heap_flags: int | None = None
    device_local = _optional_field_bool(fields, first_tag + 4, "gpu_field_device_local")
    if memory_type_available:
        memory_type_index = _optional_field_u64(fields, first_tag)
        heap_index = _optional_field_u64(fields, first_tag + 1)
        memory_property_flags = _optional_field_u64(fields, first_tag + 2)
        memory_heap_flags = _optional_field_u64(fields, first_tag + 3)
        if (
            memory_type_index is None
            or heap_index is None
            or memory_type_index >= 0xFFFFFFFF
            or heap_index >= 0xFFFFFFFF
            or memory_property_flags is None
            or memory_property_flags > 0xFFFFFFFF
            or memory_heap_flags is None
            or memory_heap_flags > 0xFFFFFFFF
            or device_local is None
        ):
            raise NativeFieldRuntimeError("native Vulkan memory selection report is incomplete")
    else:
        device_local = None
    return {
        "heaps_available": heaps_available,
        "budget_available": budget_available,
        "heap_total_bytes": heap_total if heaps_available else None,
        "heap_budget_bytes": heap_budget if budget_available else None,
        "heap_usage_bytes": heap_usage if budget_available else None,
        "gpu_field_memory_type_index": memory_type_index,
        "gpu_field_heap_index": heap_index,
        "gpu_field_memory_property_flags": memory_property_flags,
        "gpu_field_memory_heap_flags": memory_heap_flags,
        "gpu_field_device_local": device_local,
        "gpu_field_words_available": _optional_field_bool(
            fields, first_tag + 5, "gpu_field_words_available"
        ),
        "gpu_field_memory_type_available": memory_type_available,
        "gpu_field_batches": _optional_field_u64(fields, first_tag + 7),
        "gpu_field_host_upload_bytes": _optional_field_u64(fields, first_tag + 8),
        "gpu_field_changed_page_export_bytes": _optional_field_u64(fields, first_tag + 9),
        "gpu_field_retained_bytes": _optional_field_u64(fields, first_tag + 10),
        "note": note,
    }


def _field_decimal_u64(fields: dict[int, tuple[int, bytes]], tag: int) -> int:
    """Parse an exact u64 carried as decimal text with no sign or separators."""

    text = _field_text(fields, tag)
    if not text or any(character not in "0123456789" for character in text):
        raise NativeFieldRuntimeError(
            f"native response field {tag} is not exact decimal text"
        )
    value = int(text)
    if value > 0xFFFFFFFFFFFFFFFF:
        raise NativeFieldRuntimeError(f"native response field {tag} exceeds an exact u64")
    return value


if sys.platform == "win32":
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _GENERIC_READ = 0x80000000
    _GENERIC_WRITE = 0x40000000
    _OPEN_EXISTING = 3
    _PAGE_READWRITE = 0x04
    _FILE_MAP_WRITE = 0x0002
    _FILE_MAP_READ = 0x0004

    _kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _kernel32.CreateFileW.restype = wintypes.HANDLE
    _kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    _kernel32.WaitNamedPipeW.restype = wintypes.BOOL
    _kernel32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _kernel32.ReadFile.restype = wintypes.BOOL
    _kernel32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    _kernel32.WriteFile.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.CreateFileMappingW.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR]
    _kernel32.CreateFileMappingW.restype = wintypes.HANDLE
    _kernel32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
    _kernel32.MapViewOfFile.restype = ctypes.c_void_p
    _kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    _kernel32.UnmapViewOfFile.restype = wintypes.BOOL
else:
    _kernel32 = None


def _win_error(message: str) -> NativeFieldRuntimeError:
    return NativeFieldRuntimeError(f"{message}: Windows error {ctypes.get_last_error()}")


class _Handle:
    def __init__(self, value: int) -> None:
        if sys.platform != "win32" or value in {0, _INVALID_HANDLE_VALUE}:
            raise _win_error("native handle is invalid")
        self.value = int(value)

    def close(self) -> None:
        if self.value:
            _kernel32.CloseHandle(wintypes.HANDLE(self.value))
            self.value = 0

    def __enter__(self) -> "_Handle":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        self.close()


class _StagingMapping(_Handle):
    @classmethod
    def from_bytes(cls, data: bytes) -> "_StagingMapping":
        if not data or len(data) > MAX_FIELD_BYTES:
            raise NativeFieldRuntimeError("staging payload size is outside its bound")
        handle = _kernel32.CreateFileMappingW(wintypes.HANDLE(_INVALID_HANDLE_VALUE), None, _PAGE_READWRITE, len(data) >> 32, len(data) & 0xFFFFFFFF, None)
        mapping = cls(int(handle))
        address = _kernel32.MapViewOfFile(wintypes.HANDLE(mapping.value), _FILE_MAP_WRITE, 0, 0, len(data))
        if not address:
            mapping.close()
            raise _win_error("cannot map staging payload")
        try:
            ctypes.memmove(address, data, len(data))
        finally:
            _kernel32.UnmapViewOfFile(address)
        return mapping

    def read(self, size: int) -> bytes:
        if not 0 < size <= MAX_FIELD_BYTES:
            raise NativeFieldRuntimeError("exported payload size is outside its bound")
        address = _kernel32.MapViewOfFile(wintypes.HANDLE(self.value), _FILE_MAP_READ, 0, 0, size)
        if not address:
            raise _win_error("cannot map exported payload")
        try:
            return ctypes.string_at(address, size)
        finally:
            _kernel32.UnmapViewOfFile(address)


@dataclass(frozen=True, slots=True)
class NativeWordOperation:
    opcode: str
    destination: int
    source_or_expected: int = 0
    count_or_value: int = 0
    value: int = 0

    def encode(self) -> bytes:
        opcodes = {"set": 1, "copy": 2, "fill": 3, "compare-set": 4, "add-constant": 5}
        try:
            opcode = opcodes[self.opcode]
        except KeyError as exc:
            raise NativeFieldRuntimeError("native word opcode is unsupported") from exc
        values = (self.destination, self.source_or_expected, self.count_or_value, self.value)
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in values):
            raise NativeFieldRuntimeError("native word operation values must be nonnegative integers")
        if self.destination > 0xFFFFFFFFFFFFFFFF or self.source_or_expected > 0xFFFFFFFFFFFFFFFF or self.count_or_value > 0xFFFFFFFF or self.value > 0xFFFFFFFF:
            raise NativeFieldRuntimeError("native word operation value exceeds its encoding")
        return struct.pack("<B7xQQII", opcode, *values)


@dataclass(frozen=True, slots=True)
class NativeGroupRow:
    """One group row request record: exact committed history plus sampler.

    The token history is this row's exact committed generation history; the
    backend rejects stale, duplicate, or divergent histories and never
    answers optimistically.  ``accept_sampled`` selects the fused head
    sample instead of the verified next token.
    """

    tokens: tuple[int, ...]
    next_token: int
    accept_sampled: bool
    sampler_mode: str
    temperature: float
    top_k: int
    draw: float

    def encode(self) -> bytes:
        tokens = self.tokens
        if isinstance(tokens, (str, bytes, dict)) or not isinstance(tokens, (tuple, list)):
            raise NativeFieldRuntimeError("group row token history must be a sequence")
        if len(tokens) > 1_048_576:
            raise NativeFieldRuntimeError("group row token history is outside its bound")
        parts = [struct.pack("<I", len(tokens))]
        for token in tokens:
            if isinstance(token, bool) or not isinstance(token, int) or not 0 <= token <= 0x7FFFFFFF:
                raise NativeFieldRuntimeError("group row token is outside int32 range")
            parts.append(struct.pack("<i", token))
        if isinstance(self.next_token, bool) or not isinstance(self.next_token, int) or not 0 <= self.next_token <= 0x7FFFFFFF:
            raise NativeFieldRuntimeError("group row next token is outside int32 range")
        parts.append(struct.pack("<i", self.next_token))
        if not isinstance(self.accept_sampled, bool):
            raise NativeFieldRuntimeError("group row accept_sampled must be a boolean")
        parts.append(struct.pack("<B", 1 if self.accept_sampled else 0))
        sampler = _text(self.sampler_mode, "group row sampler_mode").encode("utf-8")
        if len(sampler) > 32:
            raise NativeFieldRuntimeError("group row sampler mode is outside its bound")
        parts.append(struct.pack("<I", len(sampler)))
        parts.append(sampler)
        if not math.isfinite(self.temperature) or self.temperature <= 0.0:
            raise NativeFieldRuntimeError("group row temperature is invalid")
        parts.append(struct.pack("<d", self.temperature))
        if isinstance(self.top_k, bool) or not isinstance(self.top_k, int) or not 0 <= self.top_k <= 0xFFFFFFFF:
            raise NativeFieldRuntimeError("group row top_k is outside its bound")
        parts.append(struct.pack("<I", self.top_k))
        if not math.isfinite(self.draw) or not 0.0 <= self.draw < 1.0:
            raise NativeFieldRuntimeError("group row draw is invalid")
        parts.append(struct.pack("<d", self.draw))
        return b"".join(parts)


def _group_digest(value: bytes, label: str) -> str:
    try:
        text = value.decode("ascii")
    except UnicodeDecodeError as exc:
        raise NativeFieldRuntimeError(f"native group result {label} is not hex text") from exc
    return _digest(text, f"native group result {label}")


def _decode_group_results(blob: bytes, expected_rows: int) -> list[dict[str, Any]]:
    """Decode the packed group result rows; the blob must be consumed exactly."""

    rows: list[dict[str, Any]] = []
    cursor = 0

    def take(size: int) -> bytes:
        nonlocal cursor
        if size < 0 or cursor + size > len(blob):
            raise NativeFieldRuntimeError("native group result row is truncated")
        value = blob[cursor : cursor + size]
        cursor += size
        return value

    for _ in range(expected_rows):
        token, end_of_generation, sampled_token = struct.unpack("<iBi", take(9))
        if end_of_generation not in {0, 1}:
            raise NativeFieldRuntimeError("native group result end_of_generation is invalid")
        replay_len = struct.unpack("<I", take(4))[0]
        if replay_len != 64:
            raise NativeFieldRuntimeError("native group result replay digest length is invalid")
        replay_sha256 = _group_digest(take(replay_len), "replay_sha256")
        token_count = struct.unpack("<Q", take(8))[0]
        trace_len = struct.unpack("<I", take(4))[0]
        if trace_len != 64:
            raise NativeFieldRuntimeError("native group result stage trace length is invalid")
        stage_trace_sha256 = _group_digest(take(trace_len), "stage_trace_sha256")
        stages = struct.unpack("<7Q", take(56))
        rows.append(
            {
                "token": token,
                "end_of_generation": bool(end_of_generation),
                "sampled_token": sampled_token,
                "replay_sha256": replay_sha256,
                "token_count": token_count,
                "stage_trace_sha256": stage_trace_sha256,
                "exact_stages": stages[0],
                "embedding_stages": stages[1],
                "attention_stages": stages[2],
                "ffn_stages": stages[3],
                "head_stages": stages[4],
                "ggml_nodes": stages[5],
                "logical_weight_bytes": stages[6],
            }
        )
    if cursor != len(blob):
        raise NativeFieldRuntimeError("native group result blob has trailing bytes")
    return rows


class NativeFieldRuntimeClient:
    """One authenticated connection; the owner remains the only publisher."""

    def __init__(
        self,
        instance_id: str,
        launch_nonce: str,
        *,
        process: subprocess.Popen[bytes] | None = None,
        process_logs: tuple[Any, Any] | None = None,
        connect_timeout_s: float = 10.0,
        device_index: int | None = None,
    ) -> None:
        if sys.platform != "win32":
            raise NativeFieldRuntimeError("native field-runtime transport requires Windows")
        self.instance_id = _text(instance_id, "instance_id")
        self.launch_nonce = _text(launch_nonce, "launch_nonce")
        if device_index is not None and (
            isinstance(device_index, bool)
            or not isinstance(device_index, int)
            or device_index < 0
        ):
            raise NativeFieldRuntimeError("device_index must be a nonnegative integer")
        self.device_index = device_index
        self._device_report: dict[str, Any] | None = None
        self._process = process
        self._process_logs = process_logs
        self._request_lock = threading.Lock()
        self._pipe = self._connect(connect_timeout_s)
        response = self._request(HELLO, (_utf8(1, self.instance_id), _utf8(2, self.launch_nonce)))
        if _field_text(response, 1) != "authenticated":
            self.close()
            raise NativeFieldRuntimeError("native runtime authentication failed")
        self.service_generation = _field_u64(response, 2)
        self._candidate_placements: dict[str, str] = {}
        self._verified_model_sources: dict[str, Path] = {}
        self._graph_site_preflights: dict[str, dict[str, Any]] = {}
        self._pending_graph_site_candidates: dict[str, dict[str, Any]] = {}
        self._model_task_states: dict[str, dict[str, Any]] = {}

    @classmethod
    def launch(
        cls,
        executable: str | Path,
        *,
        instance_id: str | None = None,
        launch_nonce: str | None = None,
        device_index: int = 0,
        cpu_only: bool = False,
        connect_timeout_s: float = 10.0,
    ) -> "NativeFieldRuntimeClient":
        if isinstance(device_index, bool) or not isinstance(device_index, int) or device_index < 0:
            raise NativeFieldRuntimeError("device_index must be a nonnegative integer")
        instance = instance_id or secrets.token_hex(16)
        nonce = launch_nonce or secrets.token_hex(32)
        stdout_log = tempfile.TemporaryFile()
        stderr_log = tempfile.TemporaryFile()
        arguments = [
            str(Path(executable)),
            "--instance",
            instance,
            "--nonce",
            nonce,
            "--device",
            str(device_index),
        ]
        if cpu_only:
            arguments.append("--cpu-only")
        process = subprocess.Popen(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=stdout_log,
            stderr=stderr_log,
        )
        try:
            return cls(
                instance,
                nonce,
                process=process,
                process_logs=(stdout_log, stderr_log),
                connect_timeout_s=connect_timeout_s,
                device_index=device_index,
            )
        except Exception:
            process.terminate()
            process.wait(timeout=5)
            stdout_log.close()
            stderr_log.close()
            raise

    @property
    def pipe_name(self) -> str:
        return rf"\\.\pipe\cassi-field-runtime-{self.instance_id}"

    def _connect(self, timeout_s: float) -> _Handle:
        deadline = time.monotonic() + timeout_s
        while True:
            if self._process is not None and self._process.poll() is not None:
                stderr = self._process_log(1)
                raise NativeFieldRuntimeError(f"native field-runtime exited before connection: {stderr.strip()}")
            handle = _kernel32.CreateFileW(self.pipe_name, _GENERIC_READ | _GENERIC_WRITE, 0, None, _OPEN_EXISTING, 0, None)
            if int(handle) not in {0, _INVALID_HANDLE_VALUE}:
                return _Handle(int(handle))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NativeFieldRuntimeError("timed out connecting to native field-runtime")
            _kernel32.WaitNamedPipeW(self.pipe_name, min(int(remaining * 1000), 100))

    def _process_log(self, index: int) -> str:
        if self._process_logs is None:
            return ""
        stream = self._process_logs[index]
        stream.flush()
        stream.seek(0)
        return stream.read().decode("utf-8", "replace")

    def _write_all(self, data: bytes) -> None:
        cursor = 0
        while cursor < len(data):
            chunk = data[cursor : cursor + (1 << 20)]
            buffer = ctypes.create_string_buffer(chunk)
            written = wintypes.DWORD()
            if not _kernel32.WriteFile(wintypes.HANDLE(self._pipe.value), buffer, len(chunk), ctypes.byref(written), None) or not written.value:
                raise _win_error("cannot write native runtime frame")
            cursor += written.value

    def _read_exact(self, size: int) -> bytes:
        result = bytearray(size)
        cursor = 0
        while cursor < size:
            count = min(size - cursor, 1 << 20)
            buffer = (ctypes.c_ubyte * count)()
            received = wintypes.DWORD()
            if not _kernel32.ReadFile(wintypes.HANDLE(self._pipe.value), buffer, count, ctypes.byref(received), None) or not received.value:
                raise _win_error("native runtime response is truncated")
            result[cursor : cursor + received.value] = bytes(buffer[: received.value])
            cursor += received.value
        return bytes(result)

    def _request(self, kind: int, fields: Sequence[tuple[int, int, bytes]]) -> dict[int, tuple[int, bytes]]:
        body = _body(fields)
        request_id = uuid.uuid4().bytes
        header = FRAME_HEADER.pack(FRAME_MAGIC, PROTOCOL_VERSION, kind, 0, len(body), request_id, hashlib.sha256(body).digest())
        trace = _active_work_trace()
        started_ns = trace.now() if trace is not None else 0
        wire_bytes = len(header) + len(body)
        with self._request_lock:
            self._write_all(header + body)
            raw_header = self._read_exact(FRAME_HEADER.size)
            magic, version, response_kind, _flags, size, response_id, digest = FRAME_HEADER.unpack(raw_header)
            if magic != FRAME_MAGIC or version != PROTOCOL_VERSION or size > MAX_FRAME_BODY:
                raise NativeFieldRuntimeError("native runtime response header is invalid")
            response_body = self._read_exact(size)
            wire_bytes += len(raw_header) + len(response_body)
            if hashlib.sha256(response_body).digest() != digest:
                raise NativeFieldRuntimeError("native runtime response digest mismatch")
            decoded = _decode_body(response_body)
            if response_id != request_id:
                raise NativeFieldRuntimeError("native runtime response identity is invalid")
            if response_kind == ERROR:
                raise NativeFieldRuntimeError(_field_text(decoded, 2))
            if response_kind != (kind | RESPONSE_BIT):
                raise NativeFieldRuntimeError("native runtime response identity is invalid")
        if trace is not None:
            duration_ns = max(0, trace.now() - started_ns)
            _trace_record(
                trace,
                "native",
                _REQUEST_KIND_NAMES.get(kind, f"kind-{kind}"),
                duration_ns,
                wait_ns=duration_ns,
                bytes_moved=wire_bytes,
                items=1,
                meta={"kind": kind},
            )
        return decoded

    def device_report(self, *, refresh: bool = False) -> dict[str, Any] | None:
        """Structured per-device report from the latest status/probe evidence.

        ``None`` means no device evidence has been observed (no native
        report yet or a native build without the device fields); every
        unknown budget or identity inside a report stays explicit ``None``.
        """

        if refresh or self._device_report is None:
            self.status()
        return self._device_report

    def verify_device(self, operation: str) -> dict[str, Any] | None:
        """Refuse the operation when the native reports a different device.

        The requested ``--device`` index is compared against the
        native-reported device index from status evidence; a mismatch is a
        hard error.  A native build that reports no device index cannot be
        verified and is reported as unknown, never guessed.
        """

        report = self.device_report(refresh=self._device_report is None)
        index = report.get("device_index") if report else None
        if (
            self.device_index is not None
            and isinstance(index, int)
            and index != self.device_index
        ):
            raise NativeFieldRuntimeError(
                f"native field-runtime reported device index {index} for "
                f"{operation} but launch requested device {self.device_index}"
            )
        return report

    def status(self) -> dict[str, Any]:
        response = self._request(STATUS, ())
        report = {
            "status": _field_text(response, 1),
            "service_generation": _field_u64(response, 2),
            "attachments": _field_u64(response, 3),
            "candidates": _field_u64(response, 4),
            "vulkan": _field_text(response, 5),
            "vulkan_device": _field_text(response, 6),
            "vulkan_reason": _field_text(response, 7),
            "model_runtime": _field_text(response, 8),
            "loaded_models": _field_u64(response, 9),
            "model_tasks": _field_u64(response, 10),
            "model_runtime_reason": _field_text(response, 11),
            "execution_profile": _field_text(response, 12),
            "group_hosts": _optional_field_u64(response, 21),
            "device": _device_report(
                device_index=_optional_field_u64(response, 13),
                device_identity=_optional_field_identity(response, 14),
                device_identity_kind=_optional_field_identity(response, 15),
                heap_total=_optional_field_u64(response, 16),
                heap_budget=_optional_field_u64(response, 17),
                heap_usage=_optional_field_u64(response, 18),
                memory_state=_optional_field_text(response, 19),
                note=_optional_field_text(response, 20),
            ),
        }
        self._device_report = report["device"]
        return report

    def attach(
        self,
        owner_id: str,
        field_image: np.ndarray,
        *,
        profile_sha256: str,
        state_sha256: str,
        catalog_sha256: str,
        fence: int = 0,
    ) -> dict[str, Any]:
        self.verify_device("attach")
        if (
            not isinstance(field_image, np.ndarray)
            or field_image.dtype != np.float64
            or not field_image.flags.c_contiguous
        ):
            raise NativeFieldRuntimeError(
                "native attachment requires a C-contiguous float64 field image"
            )
        if not 1 <= field_image.ndim <= 8 or any(
            not 0 < int(extent) <= 0xFFFFFFFF for extent in field_image.shape
        ):
            raise NativeFieldRuntimeError("native attachment shape is outside its bound")
        payload = memoryview(field_image).cast("B")
        size = payload.nbytes
        if not size or size > MAX_LOGICAL_IMAGE_BYTES:
            raise NativeFieldRuntimeError("native logical image size is outside its bound")
        shape = b"".join(struct.pack("<I", int(extent)) for extent in field_image.shape)
        profile = _digest(profile_sha256, "profile_sha256")
        state = _digest(state_sha256, "state_sha256")
        catalog = _digest(catalog_sha256, "catalog_sha256")
        digest = hashlib.sha256(payload).digest()
        if size <= MAX_FIELD_BYTES:
            chunk = payload.tobytes()
            with _StagingMapping.from_bytes(chunk) as mapping:
                response = self._request(
                    IMPORT_IMAGE,
                    (
                        _utf8(1, owner_id),
                        _u64(2, self.service_generation),
                        _u64(3, fence),
                        _utf8(4, profile),
                        _utf8(5, state),
                        _utf8(6, catalog),
                        _bytes(7, shape),
                        _u64(8, mapping.value),
                        _u64(9, size),
                        _bytes(10, digest),
                    ),
                )
        else:
            response = self._request(
                IMPORT_IMAGE_INFO,
                (
                    _utf8(1, owner_id),
                    _u64(2, self.service_generation),
                    _u64(3, fence),
                    _utf8(4, profile),
                    _utf8(5, state),
                    _utf8(6, catalog),
                    _bytes(7, shape),
                    _u64(8, size),
                    _bytes(9, digest),
                ),
            )
            transfer_id = _field_text(response, 2)
            try:
                if _field_text(response, 1) != "import-open":
                    raise NativeFieldRuntimeError(
                        "native runtime did not open image import"
                    )
                chunk_bytes = _field_u64(response, 3)
                if not 0 < chunk_bytes <= MAX_FIELD_BYTES or chunk_bytes % 8:
                    raise NativeFieldRuntimeError("native import chunk bound is invalid")
                for offset in range(0, size, chunk_bytes):
                    chunk = payload[offset : min(size, offset + chunk_bytes)].tobytes()
                    with _StagingMapping.from_bytes(chunk) as mapping:
                        chunk_response = self._request(
                            IMPORT_IMAGE_CHUNK,
                            (
                                _utf8(1, transfer_id),
                                _u64(2, offset),
                                _u64(3, mapping.value),
                                _u64(4, len(chunk)),
                                _bytes(5, hashlib.sha256(chunk).digest()),
                            ),
                        )
                    if (
                        _field_text(chunk_response, 1) != "import-chunk-accepted"
                        or _field_text(chunk_response, 2) != transfer_id
                        or _field_u64(chunk_response, 3) != offset + len(chunk)
                    ):
                        raise NativeFieldRuntimeError(
                            "native image import chunk acknowledgment disagrees"
                        )
                response = self._request(
                    FINISH_IMAGE_IMPORT, (_utf8(1, transfer_id),)
                )
            except BaseException:
                try:
                    self._request(
                        CANCEL_IMAGE_IMPORT, (_utf8(1, transfer_id),)
                    )
                except Exception:
                    pass
                raise
        if (
            _field_text(response, 1) != "attached"
            or _field_text(response, 2) != owner_id
        ):
            raise NativeFieldRuntimeError("native runtime did not attach imported image")
        return {
            "status": _field_text(response, 1),
            "owner_id": _field_text(response, 2),
            "word_count": _field_u64(response, 3),
            "packed_sha256": _field_text(response, 4),
        }


    def attach_packed(
        self,
        owner_id: str,
        shape: Sequence[int],
        packed_words: bytes,
        *,
        profile_sha256: str,
        state_sha256: str,
        catalog_sha256: str,
        fence: int = 0,
    ) -> dict[str, Any]:
        """Attach packed u32 words without constructing a full float64 image."""

        self.verify_device("attach")
        extents = tuple(shape)
        if not 1 <= len(extents) <= 8 or any(
            isinstance(extent, bool)
            or not isinstance(extent, int)
            or not 0 < extent <= 0xFFFFFFFF
            for extent in extents
        ):
            raise NativeFieldRuntimeError("native attachment shape is outside its bound")
        total_words = math.prod(extents)
        if not isinstance(packed_words, bytes) or len(packed_words) != total_words * 4:
            raise NativeFieldRuntimeError("native packed attachment size disagrees with shape")
        canonical_size = len(packed_words) * 2
        if not canonical_size or canonical_size > MAX_LOGICAL_IMAGE_BYTES:
            raise NativeFieldRuntimeError("native logical image size is outside its bound")
        shape_bytes = b"".join(struct.pack("<I", extent) for extent in extents)
        profile = _digest(profile_sha256, "profile_sha256")
        state = _digest(state_sha256, "state_sha256")
        catalog = _digest(catalog_sha256, "catalog_sha256")

        def canonical_chunk(start_word: int, stop_word: int) -> bytes:
            packed = packed_words[start_word * 4 : stop_word * 4]
            return np.frombuffer(packed, dtype="<u4").astype(np.float64).tobytes(order="C")

        digest_builder = hashlib.sha256()
        for start in range(0, total_words, 4096):
            digest_builder.update(canonical_chunk(start, min(total_words, start + 4096)))
        digest = digest_builder.digest()
        response = self._request(
            IMPORT_IMAGE_INFO,
            (
                _utf8(1, owner_id),
                _u64(2, self.service_generation),
                _u64(3, fence),
                _utf8(4, profile),
                _utf8(5, state),
                _utf8(6, catalog),
                _bytes(7, shape_bytes),
                _u64(8, canonical_size),
                _bytes(9, digest),
            ),
        )
        transfer_id = _field_text(response, 2)
        try:
            if _field_text(response, 1) != "import-open":
                raise NativeFieldRuntimeError("native runtime did not open image import")
            chunk_bytes = _field_u64(response, 3)
            if not 0 < chunk_bytes <= MAX_FIELD_BYTES or chunk_bytes % 8:
                raise NativeFieldRuntimeError("native import chunk bound is invalid")
            words_per_chunk = max(1, chunk_bytes // 8)
            total_words = math.prod(extents)
            for start in range(0, total_words, words_per_chunk):
                stop = min(total_words, start + words_per_chunk)
                chunk = canonical_chunk(start, stop)
                with _StagingMapping.from_bytes(chunk) as mapping:
                    chunk_response = self._request(
                        IMPORT_IMAGE_CHUNK,
                        (
                            _utf8(1, transfer_id),
                            _u64(2, start * 8),
                            _u64(3, mapping.value),
                            _u64(4, len(chunk)),
                            _bytes(5, hashlib.sha256(chunk).digest()),
                        ),
                    )
                next_offset = stop * 8
                if (
                    _field_text(chunk_response, 1) != "import-chunk-accepted"
                    or _field_text(chunk_response, 2) != transfer_id
                    or _field_u64(chunk_response, 3) != next_offset
                ):
                    raise NativeFieldRuntimeError("native image import chunk acknowledgment disagrees")
            response = self._request(FINISH_IMAGE_IMPORT, (_utf8(1, transfer_id),))
        except BaseException:
            try:
                self._request(CANCEL_IMAGE_IMPORT, (_utf8(1, transfer_id),))
            except Exception:
                pass
            raise
        if _field_text(response, 1) != "attached" or _field_text(response, 2) != owner_id:
            raise NativeFieldRuntimeError("native runtime did not attach imported image")
        return {
            "status": _field_text(response, 1),
            "owner_id": _field_text(response, 2),
            "word_count": _field_u64(response, 3),
            "packed_sha256": _field_text(response, 4),
        }

    def begin_candidate(
        self,
        owner_id: str,
        predecessor_state_sha256: str,
        *,
        fence: int,
        lease_id: str,
        placement: str = "native-cpu",
    ) -> str:
        self.verify_device("begin_candidate")
        response = self._request(
            BEGIN_CANDIDATE,
            (
                _utf8(1, owner_id),
                _utf8(2, _digest(predecessor_state_sha256, "predecessor_state_sha256")),
                _u64(3, fence),
                _utf8(4, lease_id),
                _utf8(5, placement),
            ),
        )
        if _field_text(response, 1) != "candidate-open":
            raise NativeFieldRuntimeError("native runtime did not open a candidate")
        candidate_id = _field_text(response, 2)
        self._candidate_placements[candidate_id] = _field_text(response, 3)
        return candidate_id

    def candidate_placement(self, candidate_id: str) -> str:
        try:
            return self._candidate_placements[candidate_id]
        except KeyError as exc:
            raise NativeFieldRuntimeError("native candidate placement is unknown") from exc

    def apply_word_operations(
        self,
        candidate_id: str,
        operations: Iterable[NativeWordOperation],
    ) -> dict[str, Any]:
        iterator = iter(operations)
        sent = False
        response: dict[int, tuple[int, bytes]] | None = None
        while True:
            batch: list[NativeWordOperation] = []
            for _ in range(MAX_WORD_OPERATIONS_PER_FRAME):
                try:
                    batch.append(next(iterator))
                except StopIteration:
                    break
            if not batch and sent:
                break
            encoded = b"".join(operation.encode() for operation in batch)
            response = self._request(
                APPLY_WORD_OPS,
                (_utf8(1, candidate_id), _bytes(2, encoded)),
            )
            sent = True
            if len(batch) < MAX_WORD_OPERATIONS_PER_FRAME:
                break
        if response is None:
            raise NativeFieldRuntimeError("native operation batch was not sent")
        if _field_text(response, 1) != "candidate-advanced":
            raise NativeFieldRuntimeError("native runtime did not advance candidate")
        operations_count = _field_u64(response, 2)
        digest = _field_text(response, 3)
        if not digest:
            finalized = self.candidate_digest(candidate_id)
            if finalized["logical_operations"] != operations_count:
                raise NativeFieldRuntimeError("native candidate changed during digest finalization")
            digest = finalized["canonical_bytes_sha256"]
        digest = _digest(digest, "canonical_bytes_sha256")
        if 4 in response:
            placement = _field_text(response, 4)
        else:
            placement = self._candidate_placements.get(candidate_id, "native-cpu")
        self._candidate_placements[candidate_id] = placement
        return {
            "status": "candidate-advanced",
            "logical_operations": operations_count,
            "canonical_bytes_sha256": digest,
            "placement": placement,
        }

    def candidate_digest(self, candidate_id: str) -> dict[str, Any]:
        """Finalize a candidate and return its canonical identity without moving the image."""

        response = self._request(EXPORT_CANDIDATE_INFO, (_utf8(1, candidate_id),))
        if (
            _field_text(response, 1) != "candidate-export-info"
            or _field_text(response, 2) != candidate_id
        ):
            raise NativeFieldRuntimeError("native runtime returned another candidate export")
        return {
            "canonical_bytes": _field_u64(response, 3),
            "canonical_bytes_sha256": _field_bytes(response, 4).hex(),
            "predecessor_state_sha256": _field_text(response, 5),
            "logical_operations": _field_u64(response, 6),
        }

    def export_candidate(
        self, candidate_id: str, shape: Sequence[int]
    ) -> tuple[np.ndarray, dict[str, Any]]:
        expected_size = math.prod(shape) * 8
        if expected_size <= MAX_FIELD_BYTES:
            response = self._request(EXPORT_CANDIDATE, (_utf8(1, candidate_id),))
            if _field_text(response, 1) != "candidate-exported":
                raise NativeFieldRuntimeError("native runtime did not export candidate")
            handle = _field_u64(response, 2)
            size = _field_u64(response, 3)
            expected = _field_bytes(response, 4)
            with _StagingMapping(handle) as mapping:
                payload = mapping.read(size)
            if hashlib.sha256(payload).digest() != expected:
                raise NativeFieldRuntimeError("exported candidate digest mismatch")
            if expected_size != size:
                raise NativeFieldRuntimeError("exported candidate size does not match shape")
            array = np.frombuffer(payload, dtype=np.float64).reshape(
                tuple(int(item) for item in shape)
            ).copy()
            metadata = {
                "status": _field_text(response, 1),
                "predecessor_state_sha256": _field_text(response, 5),
                "logical_operations": _field_u64(response, 6),
                "payload_sha256": expected.hex(),
            }
            return array, metadata

        if expected_size > MAX_LOGICAL_IMAGE_BYTES:
            raise NativeFieldRuntimeError("exported candidate exceeds logical image bound")
        response = self._request(
            EXPORT_CANDIDATE_INFO, (_utf8(1, candidate_id),)
        )
        if (
            _field_text(response, 1) != "candidate-export-info"
            or _field_text(response, 2) != candidate_id
        ):
            raise NativeFieldRuntimeError("native runtime returned another candidate export")
        size = _field_u64(response, 3)
        expected = _field_bytes(response, 4)
        expected_operations = _field_u64(response, 6)
        if size != expected_size:
            raise NativeFieldRuntimeError("exported candidate size does not match shape")
        chunk_bytes = _field_u64(response, 7)
        if not 0 < chunk_bytes <= MAX_FIELD_BYTES or chunk_bytes % 8:
            raise NativeFieldRuntimeError("native export chunk bound is invalid")
        payload = bytearray(size)
        for offset in range(0, size, chunk_bytes):
            requested = min(chunk_bytes, size - offset)
            chunk_response = self._request(
                EXPORT_CANDIDATE_CHUNK,
                (
                    _utf8(1, candidate_id),
                    _u64(2, offset),
                    _u64(3, requested),
                    _u64(4, expected_operations),
                    _bytes(5, expected),
                ),
            )
            if _field_text(chunk_response, 1) != "candidate-export-chunk":
                raise NativeFieldRuntimeError("native runtime returned an invalid export chunk")
            if (
                _field_u64(chunk_response, 5) != expected_operations
                or _field_bytes(chunk_response, 6) != expected
            ):
                raise NativeFieldRuntimeError(
                    "native candidate changed during chunked export"
                )
            handle = _field_u64(chunk_response, 2)
            chunk_size = _field_u64(chunk_response, 3)
            chunk_digest = _field_bytes(chunk_response, 4)
            if chunk_size != requested:
                raise NativeFieldRuntimeError("native export chunk size disagrees")
            with _StagingMapping(handle) as mapping:
                chunk = mapping.read(chunk_size)
            if hashlib.sha256(chunk).digest() != chunk_digest:
                raise NativeFieldRuntimeError("native export chunk digest mismatch")
            payload[offset : offset + chunk_size] = chunk
        if hashlib.sha256(payload).digest() != expected:
            raise NativeFieldRuntimeError("exported candidate digest mismatch")
        array = np.frombuffer(payload, dtype=np.float64).reshape(
            tuple(int(item) for item in shape)
        ).copy()
        metadata = {
            "status": _field_text(response, 1),
            "predecessor_state_sha256": _field_text(response, 5),
            "logical_operations": _field_u64(response, 6),
            "payload_sha256": expected.hex(),
        }
        return array, metadata
 
    def apply_candidate_page(
        self,
        candidate_id: str,
        page_index: int,
        predecessor_page_sha256: str,
        packed_words: bytes,
    ) -> dict[str, Any]:
        """Replace one 4096-word private candidate page after an exact CAS."""

        if isinstance(page_index, bool) or not isinstance(page_index, int) or page_index < 0:
            raise NativeFieldRuntimeError("candidate page index is invalid")
        if not isinstance(packed_words, bytes) or not 0 < len(packed_words) <= 4096 * 4 or len(packed_words) % 4:
            raise NativeFieldRuntimeError("candidate packed page size is invalid")
        expected = bytes.fromhex(_digest(predecessor_page_sha256, "predecessor_page_sha256"))
        response = self._request(
            APPLY_CANDIDATE_PAGE,
            (
                _utf8(1, candidate_id),
                _u64(2, page_index),
                _bytes(3, expected),
                _bytes(4, packed_words),
            ),
        )
        if _field_text(response, 1) != "candidate-page-accepted":
            raise NativeFieldRuntimeError("native runtime did not accept candidate page")
        placement = _field_text(response, 3)
        self._candidate_placements[candidate_id] = placement
        return {
            "status": "candidate-page-accepted",
            "logical_operations": _field_u64(response, 2),
            "placement": placement,
        }

 




    def reduce_candidate(
        self,
        candidate_id: str,
        first_word: int,
        count: int,
    ) -> dict[str, Any]:
        """Sum a read-only contiguous canonical-u32 word range on the resident candidate.

        The reduction runs in the native service against the private candidate
        image; the exact sum never mutates the candidate and is returned as an
        exact u64.  The scalar stays uncommitted: nothing here publishes it.
        """

        _text(candidate_id, "candidate_id")
        if isinstance(first_word, bool) or not isinstance(first_word, int) or first_word < 0:
            raise NativeFieldRuntimeError("first_word must be a nonnegative word index")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise NativeFieldRuntimeError("count must be a positive word count")
        if count > 0xFFFFFFFFFFFFFFFF // 0xFFFFFFFF:
            raise NativeFieldRuntimeError(
                "reduction count cannot produce an exact u64 sum"
            )
        response = self._request(
            REDUCE_CANDIDATE,
            (
                _utf8(1, candidate_id),
                _u64(2, first_word),
                _u64(3, count),
            ),
        )
        if _field_text(response, 1) != "reduced":
            raise NativeFieldRuntimeError("native runtime did not reduce the candidate")
        sum_value = _field_decimal_u64(response, 2)
        if _field_u64(response, 3) != count:
            raise NativeFieldRuntimeError("native reduction count disagrees")
        placement = _field_text(response, 4)
        fence = _field_u64(response, 5)
        predecessor_state_sha256 = _digest(
            _field_text(response, 6), "predecessor_state_sha256"
        )
        self._candidate_placements[candidate_id] = placement
        return {
            "status": "reduced",
            "sum": sum_value,
            "count": count,
            "first_word": first_word,
            "placement": placement,
            "fence": fence,
            "predecessor_state_sha256": predecessor_state_sha256,
        }

    def confirm_cache(
        self,
        candidate_id: str,
        predecessor_state_sha256: str,
        successor_state_sha256: str,
        *,
        fence: int,
        lease_id: str,
        graph_site_receipt_sha256: str | None = None,
        owner_ack: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        candidate_id = _text(candidate_id, "candidate_id")
        predecessor = _digest(predecessor_state_sha256, "predecessor_state_sha256")
        successor = _digest(successor_state_sha256, "successor_state_sha256")
        lease_id = _text(lease_id, "lease_id")
        pending = self._pending_graph_site_candidates.get(candidate_id)
        fields: list[tuple[int, int, bytes]] = [
            _utf8(1, candidate_id),
            _utf8(2, predecessor),
            _u64(3, fence),
            _utf8(4, lease_id),
            _utf8(5, successor),
        ]
        if pending is not None:
            if not isinstance(owner_ack, Mapping):
                raise NativeFieldRuntimeError("native graph-site confirmation requires the flat owner acknowledgment")
            if set(owner_ack) != {
                "accepted_model_step",
                "accepted_token_id",
                "native_operation_id",
                "field_successor_sha256",
                "native_successor_sha256",
                "native_graph_site_receipt_sha256",
                "graph_receipt_wire_sha256",
                "ticket_id",
                "field_candidate_id",
            }:
                raise NativeFieldRuntimeError("native graph-site owner acknowledgment has an unsupported shape")
            accepted_token_id = owner_ack["accepted_token_id"]
            if (
                owner_ack["accepted_model_step"] is not True
                or isinstance(accepted_token_id, bool)
                or not isinstance(accepted_token_id, int)
                or accepted_token_id != pending["selected_token_id"]
            ):
                raise NativeFieldRuntimeError("native graph-site owner acknowledgment token disagrees")
            if owner_ack["native_operation_id"] != pending["native_operation_id"]:
                raise NativeFieldRuntimeError("native graph-site owner acknowledgment operation id disagrees")
            field_successor_sha256 = _digest(
                owner_ack["field_successor_sha256"],
                "field_successor_sha256",
            )
            native_successor_sha256 = _digest(
                owner_ack["native_successor_sha256"],
                "native_successor_sha256",
            )
            receipt_sha256 = _digest(
                graph_site_receipt_sha256,
                "graph_site_receipt_sha256",
            )
            if (
                field_successor_sha256 != successor
                or native_successor_sha256 != pending["receipt"]["native_successor_sha256"]
                or receipt_sha256 != pending["receipt_sha256"]
                or _digest(
                    owner_ack["native_graph_site_receipt_sha256"],
                    "native_graph_site_receipt_sha256",
                )
                != receipt_sha256
                or _digest(owner_ack["graph_receipt_wire_sha256"], "graph_receipt_wire_sha256")
                != pending["receipt_wire_sha256"]
                or _text(owner_ack["ticket_id"], "ticket_id") != pending["ticket_id"]
                or _text(owner_ack["field_candidate_id"], "field_candidate_id")
                != pending["candidate_id"]
            ):
                raise NativeFieldRuntimeError("native graph-site owner acknowledgment receipt/state bindings disagree")
            fields.extend(
                (
                    _utf8(6, pending["task_id"]),
                    _utf8(7, receipt_sha256),
                    _utf8(8, pending["receipt_wire_sha256"]),
                    _utf8(9, pending["ticket_id"]),
                    _utf8(10, pending["native_operation_id"]),
                )
            )
        elif graph_site_receipt_sha256 is not None or owner_ack is not None:
            raise NativeFieldRuntimeError("owner acknowledgment supplied for a non-graph native candidate")

        response = self._request(CONFIRM_CACHE, fields)
        report = {
            "status": _field_text(response, 1),
            "owner_id": _field_text(response, 2),
            "state_sha256": _field_text(response, 3),
            "fence": _field_u64(response, 4),
        }
        if pending is not None:
            accepted_token = _field_u64(response, 5)
            accepted_model_step = _field_u64(response, 6)
            if (
                accepted_token != pending["selected_token_id"]
                or accepted_model_step != 1
                or _field_text(response, 7) != pending["native_operation_id"]
                or _digest(_field_text(response, 8), "native_successor_sha256")
                != pending["receipt"]["native_successor_sha256"]
                or _digest(_field_text(response, 9), "native_graph_site_receipt_sha256")
                != pending["receipt_sha256"]
                or _digest(_field_text(response, 10), "native_graph_site_receipt_wire_sha256")
                != pending["receipt_wire_sha256"]
                or _field_text(response, 11) != candidate_id
                or _field_text(response, 12) != pending["ticket_id"]
            ):
                raise NativeFieldRuntimeError("native graph-site confirmation acknowledgment disagrees")
            report.update(
                {
                    "accepted_token_id": accepted_token,
                    "accepted_model_step": accepted_model_step,
                    "native_operation_id": pending["native_operation_id"],
                    "native_successor_sha256": pending["receipt"]["native_successor_sha256"],
                    "native_graph_site_receipt_sha256": pending["receipt_sha256"],
                    "native_graph_site_receipt_wire_sha256": pending["receipt_wire_sha256"],
                    "graph_receipt_wire_sha256": pending["receipt_wire_sha256"],
                    "field_candidate_id": candidate_id,
                    "ticket_id": pending["ticket_id"],
                }
            )
            state = self._model_task_states.setdefault(
                pending["task_id"],
                {
                    "service_generation": self.service_generation,
                    "source_sha256": pending["source_sha256"],
                    "accepted_steps": [],
                    "initialized": True,
                },
            )
            state["source_sha256"] = pending["source_sha256"]
            state["input_tokens"] = pending["input_tokens"]
            state["accepted_token_id"] = accepted_token
            state["accepted_steps"].append(pending["signature"])
            state["initialized"] = True
            if pending["preflight"] is not None:
                state["model_sha256"] = pending["preflight"]["model_sha256"]
                state["tokenizer_sha256"] = pending["preflight"]["tokenizer_sha256"]
            self._pending_graph_site_candidates.pop(candidate_id, None)
            self._graph_site_preflights.pop(pending["task_id"], None)
        self._candidate_placements.pop(candidate_id, None)
        return report

    def discard_candidate(self, candidate_id: str) -> dict[str, str]:
        candidate_id = _text(candidate_id, "candidate_id")
        pending = self._pending_graph_site_candidates.get(candidate_id)
        response = self._request(DISCARD_CANDIDATE, (_utf8(1, candidate_id),))
        if _field_text(response, 2) != candidate_id:
            raise NativeFieldRuntimeError("native discarded candidate identity disagrees")
        self._candidate_placements.pop(candidate_id, None)
        if pending is not None:
            self._pending_graph_site_candidates.pop(candidate_id, None)
            self._graph_site_preflights.pop(pending["task_id"], None)
        return {
            "status": _field_text(response, 1),
            "candidate_id": candidate_id,
        }
    def detach(self, owner_id: str) -> dict[str, str]:
        owner_id = _text(owner_id, "owner_id")
        response = self._request(DETACH_OWNER, (_utf8(1, owner_id),))
        return {
            "status": _field_text(response, 1),
            "owner_id": _field_text(response, 2),
        }


    def probe_vulkan(self) -> dict[str, Any]:
        response = self._request(PROBE_VULKAN, ())
        report = {
            "status": _field_text(response, 1),
            "device": _field_text(response, 2),
            "reason": _field_text(response, 3),
            "operation_groups": _field_text(response, 4),
            "device_report": _device_report(
                device_index=_optional_field_u64(response, 5),
                device_identity=_optional_field_identity(response, 6),
                device_identity_kind=_optional_field_identity(response, 7),
                heap_total=_optional_field_u64(response, 8),
                heap_budget=_optional_field_u64(response, 9),
                heap_usage=_optional_field_u64(response, 10),
                memory_state=_optional_field_text(response, 11),
                note=_optional_field_text(response, 12),
            ),
            # Resident GPU field traffic; older native builds omit these tags.
            "gpu_field": {
                "device_local": _optional_field_u64(response, 17),
                "batches": _optional_field_u64(response, 20),
                "host_upload_bytes": _optional_field_u64(response, 21),
                "changed_page_export_bytes": _optional_field_u64(response, 22),
                "retained_bytes": _optional_field_u64(response, 23),
            },
        }
        self._device_report = report["device_report"]
        return report

    @staticmethod
    def _source_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(8 << 20):
                digest.update(chunk)
        return digest.hexdigest()

    def register_model(
        self,
        source_sha256: str,
        path: str | Path,
        *,
        context_size: int = 32_768,
        gpu_layers: int = -1,
    ) -> dict[str, Any]:
        source_sha256 = _digest(source_sha256, "source_sha256")
        source = Path(path).resolve(strict=True)
        if not source.is_file():
            raise NativeFieldRuntimeError("registered model source is not a regular file")
        prior = self._verified_model_sources.get(source_sha256)
        if prior is not None and prior != source:
            raise NativeFieldRuntimeError("model digest is already bound to another source")
        if prior is None:
            actual = self._source_sha256(source)
            if actual != source_sha256:
                raise NativeFieldRuntimeError("registered model source digest mismatch")
            self._verified_model_sources[source_sha256] = source
        if isinstance(context_size, bool) or not isinstance(context_size, int) or not 2 <= context_size <= 1_048_576:
            raise NativeFieldRuntimeError("model context_size is outside its bound")
        if isinstance(gpu_layers, bool) or not isinstance(gpu_layers, int) or not -1 <= gpu_layers <= 0x7FFFFFFF:
            raise NativeFieldRuntimeError("model gpu_layers is outside its bound")
        response = self._request(
            REGISTER_MODEL,
            (
                _utf8(1, source_sha256),
                _utf8(2, str(source)),
                _u64(3, context_size),
                _u64(4, gpu_layers & 0xFFFFFFFF),
            ),
        )
        return {
            "status": _field_text(response, 1),
            "source_sha256": _field_text(response, 2),
            "description": _field_text(response, 3),
            "vocabulary_size": _field_u64(response, 4),
            "context_size": _field_u64(response, 5),
            "model_bytes": _field_u64(response, 6),
        }

    def candidate_preflight(
        self,
        task_id: str,
        source_sha256: str,
        tokens: Sequence[int],
        *,
        sequence_id: str,
        sampler: Mapping[str, Any],
        native_operation_id: str,
    ) -> dict[str, Any]:
        """Bind the next native graph-site intervention to the exact decode step."""

        task_id = _text(task_id, "task_id")
        if len(task_id.encode("utf-8")) > 127:
            raise NativeFieldRuntimeError("native model task id exceeds the C API bound")
        sequence_id = _text(sequence_id, "sequence_id")
        if len(sequence_id.encode("utf-8")) > 127:
            raise NativeFieldRuntimeError("native graph-site sequence id exceeds the C API bound")
        if sequence_id == task_id:
            raise NativeFieldRuntimeError("native graph-site logical sequence id must differ from task id")
        source_sha256 = _digest(source_sha256, "source_sha256")
        native_operation_id = _text(native_operation_id, "native_operation_id")
        if len(native_operation_id.encode("utf-8")) > 127:
            raise NativeFieldRuntimeError("native operation id exceeds the C API bound")
        if self._pending_graph_site_candidates:
            raise NativeFieldRuntimeError("a native graph-site candidate is awaiting owner acknowledgment")
        input_tokens, packed_tokens, input_tokens_sha256 = _model_token_history(tokens)
        normalized_sampler, sampler_sha256 = _normalized_graph_site_sampler(sampler)
        prior = self._model_task_states.get(task_id)
        if prior is not None:
            if prior.get("source_sha256") != source_sha256:
                raise NativeFieldRuntimeError("native model task source identity changed")
            last_input = prior.get("input_tokens")
            last_token = prior.get("accepted_token_id")
            if last_input is not None and last_token is not None:
                expected_tokens = tuple(last_input) + (last_token,)
                if input_tokens != expected_tokens:
                    # The caller may already have advanced past the accepted
                    # token (the ordinary step that follows the same boundary),
                    # so the accepted history is also the same decode boundary.
                    if (
                        len(input_tokens) <= len(expected_tokens)
                        or input_tokens[: len(expected_tokens)] != expected_tokens
                    ):
                        raise NativeFieldRuntimeError(
                            "graph-site preflight token history is not the next accepted step"
                        )
                # One boundary, one accepted token: re-anchoring here keeps the
                # following step checked against the history just verified.
                prior["input_tokens"] = input_tokens
                prior["accepted_token_id"] = None
        try:
            response = self._request(
                GRAPH_SITE_PREFLIGHT,
                (
                    _utf8(1, task_id),
                    _utf8(2, source_sha256),
                    _bytes(3, packed_tokens),
                    _utf8(4, normalized_sampler["mode"]),
                    _bytes(5, struct.pack("<d", normalized_sampler["temperature"])),
                    _u64(6, normalized_sampler["top_k"]),
                    _bytes(7, struct.pack("<d", normalized_sampler["draw"])),
                    _utf8(8, sequence_id),
                    _utf8(9, sampler_sha256),
                    _utf8(10, native_operation_id),
                ),
            )
        except NativeFieldRuntimeError as exc:
            raise NativeFieldRuntimeError(
                f"native graph-site preflight API is unavailable or incompatible: {exc}"
            ) from exc
        if _field_text(response, 1) != "graph-site-preflight":
            raise NativeFieldRuntimeError("native runtime returned an incompatible graph-site preflight status")
        preflight = _decode_graph_site_preflight(_field_bytes(response, 2))
        if (
            not preflight["ready"]
            or preflight["task_id"] != task_id
            or preflight["sequence_id"] != sequence_id
            or preflight["native_operation_id"] != native_operation_id
            or preflight["source_sha256"] != source_sha256
            or preflight["sampler"] != normalized_sampler
            or preflight["sampler_sha256"] != sampler_sha256
            or preflight["next_position"] != len(input_tokens) - 1
        ):
            refusal = preflight.get("refusal") or "preflight identity or token position disagrees"
            raise NativeFieldRuntimeError(f"native graph-site preflight refused: {refusal}")
        if preflight["remaining_tokens"] <= 0:
            raise NativeFieldRuntimeError("native graph-site preflight has no remaining model context")
        if not any(site["supported"] for site in preflight["sites"]):
            raise NativeFieldRuntimeError(
                "native graph-site preflight reports no supported sites: "
                + (preflight["refusal"] or "no compatible native operators")
            )
        preflight["input_tokens"] = list(input_tokens)
        preflight["input_tokens_sha256"] = input_tokens_sha256
        preflight["native_operation_id"] = native_operation_id
        self._graph_site_preflights[task_id] = {
            "preflight": preflight,
            "source_sha256": source_sha256,
            "input_tokens": input_tokens,
            "sequence_id": sequence_id,
            "input_tokens_sha256": input_tokens_sha256,
            "sampler": normalized_sampler,
            "sampler_sha256": sampler_sha256,
            "native_operation_id": native_operation_id,
        }
        if prior is not None and (
            prior.get("model_sha256") not in {None, preflight["model_sha256"]}
            or prior.get("tokenizer_sha256") not in {None, preflight["tokenizer_sha256"]}
        ):
            self._graph_site_preflights.pop(task_id, None)
            raise NativeFieldRuntimeError("native model task model/tokenizer identity changed")

        if prior is None:
            self._model_task_states[task_id] = {
                "service_generation": self.service_generation,
                "source_sha256": source_sha256,
                "model_sha256": preflight["model_sha256"],
                "tokenizer_sha256": preflight["tokenizer_sha256"],
                "input_tokens": input_tokens,
                "accepted_token_id": None,
                "accepted_steps": [],
                "initialized": True,
            }
        else:
            prior["model_sha256"] = preflight["model_sha256"]
            prior["tokenizer_sha256"] = preflight["tokenizer_sha256"]
            # A ready preflight reads the decode boundary just verified above,
            # and that boundary is the history the following step repeats.
            prior["initialized"] = True
        return preflight

    def step_model(
        self,
        task_id: str,
        source_sha256: str,
        tokens: Sequence[int],
        *,
        sampler_mode: str = "greedy",
        temperature: float = 1.0,
        top_k: int = 0,
        draw: float = 0.0,
        sequence_id: str | None = None,
        native_operation_id: str | None = None,
        candidate_id: str | None = None,
        graph_site_ticket: Mapping[str, Any] | None = None,
        replay_step: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        task_id = _text(task_id, "task_id")
        if len(task_id.encode("utf-8")) > 127:
            raise NativeFieldRuntimeError("native model task id exceeds the C API bound")
        logical_sequence_id = (
            _text(sequence_id, "sequence_id") if sequence_id is not None else None
        )
        if logical_sequence_id is not None and len(logical_sequence_id.encode("utf-8")) > 127:
            raise NativeFieldRuntimeError("native graph-site sequence id exceeds the C API bound")
        source_sha256 = _digest(source_sha256, "source_sha256")
        operation_id = (
            _text(native_operation_id, "native_operation_id")
            if native_operation_id is not None
            else None
        )
        if operation_id is not None and len(operation_id.encode("utf-8")) > 127:
            raise NativeFieldRuntimeError("native operation id exceeds the C API bound")
        input_tokens, packed_tokens, input_tokens_sha256 = _model_token_history(tokens)
        sampler, sampler_sha256 = _model_sampler(sampler_mode, temperature, top_k, draw)
        replaying = replay_step is not None
        live_graph = candidate_id is not None or graph_site_ticket is not None
        if replaying and candidate_id is not None:
            raise NativeFieldRuntimeError("native owner-history replay cannot use a live field candidate")
        if live_graph and (candidate_id is None or graph_site_ticket is None or replaying):
            raise NativeFieldRuntimeError(
                "live native graph-site step requires physical candidate id and immutable ticket"
            )
        if (live_graph or replaying) and (
            operation_id is None
            or logical_sequence_id is None
            or logical_sequence_id == task_id
        ):
            raise NativeFieldRuntimeError(
                "graph-site and replay steps require a distinct logical sequence id and native_operation_id"
            )
        if self._pending_graph_site_candidates and not live_graph:
            raise NativeFieldRuntimeError("a native graph-site candidate is awaiting owner acknowledgment")
        if candidate_id is not None:
            candidate_id = _text(candidate_id, "candidate_id")
            if candidate_id in self._pending_graph_site_candidates:
                raise NativeFieldRuntimeError("physical candidate already has a pending model step")
        prior = self._model_task_states.get(task_id)
        if prior is not None and prior.get("source_sha256") != source_sha256:
            raise NativeFieldRuntimeError("native model task source identity changed")
        if prior is not None and prior.get("accepted_token_id") is not None:
            expected_tokens = tuple(prior["input_tokens"]) + (prior["accepted_token_id"],)
            if input_tokens != expected_tokens:
                raise NativeFieldRuntimeError("native model step is not the next accepted token history")

        replay_ticket: Mapping[str, Any] | None = None
        replay_payload: bytes | None = None
        if replaying:
            if not isinstance(replay_step, Mapping):
                raise NativeFieldRuntimeError("owner replay step must be a mapping")
            if replay_step.get("native_operation_id") != operation_id:
                raise NativeFieldRuntimeError("owner replay operation id disagrees with STEP_MODEL")
            if (
                replay_step.get("task_id") != task_id
                or replay_step.get("source_sha256") != source_sha256
            ):
                raise NativeFieldRuntimeError("owner replay task or source identity disagrees with STEP_MODEL")
            if replay_step.get("sequence_id") != logical_sequence_id:
                raise NativeFieldRuntimeError("owner replay sequence id disagrees with STEP_MODEL")
            if tuple(replay_step.get("input_tokens", ())) != input_tokens:
                raise NativeFieldRuntimeError("owner replay input tokens disagree with STEP_MODEL")
            replay_sampler, replay_sampler_sha = _normalized_graph_site_sampler(
                replay_step.get("sampler")
            )
            if (
                replay_sampler != sampler
                or replay_sampler_sha != sampler_sha256
                or _digest(replay_step.get("sampler_sha256"), "sampler_sha256") != sampler_sha256
            ):
                raise NativeFieldRuntimeError("owner replay sampler disagrees with STEP_MODEL")
            replay_ticket = replay_step.get("graph_site_ticket")
            if replay_ticket is not None:
                if not isinstance(replay_ticket, Mapping):
                    raise NativeFieldRuntimeError("owner replay graph ticket is invalid")
                replay_preflight = {
                    "model_sha256": _graph_ticket_value(replay_ticket, "model_sha256"),
                    "tokenizer_sha256": _graph_ticket_value(replay_ticket, "tokenizer_sha256"),
                    "model_embedding_width": _graph_site_u32_value(
                        replay_step.get("model_embedding_width"),
                        "model_embedding_width",
                    ),
                    "model_layer_count": _graph_site_u32_value(
                        replay_step.get("model_layer_count"),
                        "model_layer_count",
                    ),
                    "native_predecessor_sha256": _digest(
                        replay_step.get("native_predecessor_sha256"),
                        "native_predecessor_sha256",
                    ),
                    "native_preflight_sha256": _digest(
                        replay_step.get("native_preflight_sha256"),
                        "native_preflight_sha256",
                    ),
                    "native_seq_id": replay_step.get("seq_id"),
                    "next_position": replay_step.get("position"),
                }
                _graph_ticket_for_step(
                    replay_ticket,
                    candidate_id=None,
                    task_id=task_id,
                    sequence_id=logical_sequence_id,
                    native_operation_id=operation_id,
                    source_sha256=source_sha256,
                    preflight=replay_preflight,
                    sampler=sampler,
                    sampler_sha256=sampler_sha256,
                )
                replay_payload = _graph_replay_step_wire(
                    replay_step,
                    sequence_index=replay_step.get("graph_sequence_index"),
                    native_operation_id=operation_id,
                    input_tokens=input_tokens,
                    input_tokens_sha256=input_tokens_sha256,
                    sampler=sampler,
                    sampler_sha256=sampler_sha256,
                    accepted_token_id=replay_step.get("selected_token"),
                    replay_sha256=_digest(replay_step.get("replay_sha256"), "replay_sha256"),
                    stage_trace_sha256=_digest(
                        replay_step.get("stage_trace_sha256"),
                        "stage_trace_sha256",
                    ),
                    token_count=replay_step.get("token_count"),
                )

        ticket_payload: bytes | None = None
        preflight_entry: dict[str, Any] | None = None
        if live_graph:
            if not isinstance(graph_site_ticket, Mapping):
                raise NativeFieldRuntimeError("native graph-site ticket must be a mapping")
            preflight_entry = self._graph_site_preflights.get(task_id)
            if preflight_entry is None:
                raise NativeFieldRuntimeError("native graph-site step lacks a current native preflight")
            if (
                preflight_entry["source_sha256"] != source_sha256
                or preflight_entry["sequence_id"] != logical_sequence_id
                or preflight_entry["input_tokens"] != input_tokens
                or preflight_entry["sampler"] != sampler
                or preflight_entry["sampler_sha256"] != sampler_sha256
                or preflight_entry["native_operation_id"] != operation_id
            ):
                raise NativeFieldRuntimeError("native graph-site step differs from its exact preflight tuple")
            ticket_payload = _graph_ticket_for_step(
                graph_site_ticket,
                candidate_id=candidate_id,
                task_id=task_id,
                sequence_id=logical_sequence_id,
                native_operation_id=operation_id,
                source_sha256=source_sha256,
                preflight=preflight_entry["preflight"],
                sampler=sampler,
                sampler_sha256=sampler_sha256,
            )

        fields: list[tuple[int, int, bytes]] = [
            _utf8(1, task_id),
            _utf8(2, source_sha256),
            _bytes(3, packed_tokens),
            _utf8(4, sampler["mode"]),
            _bytes(5, struct.pack("<d", sampler["temperature"])),
            _u64(6, sampler["top_k"]),
            _bytes(7, struct.pack("<d", sampler["draw"])),
        ]
        if operation_id is not None:
            fields.append(_utf8(8, operation_id))
        if logical_sequence_id is not None:
            fields.append(_utf8(9, logical_sequence_id))
        fields.append(_utf8(10, sampler_sha256))
        if live_graph:
            fields.extend(
                (
                    _utf8(14, candidate_id),
                    _utf8(15, _text(graph_site_ticket["ticket_id"], "ticket_id")),
                    _bytes(17, ticket_payload),
                )
            )
        if replay_payload is not None:
            fields.append(_bytes(16, replay_payload))
        try:
            try:
                response = self._request(STEP_MODEL, fields)
            except NativeFieldRuntimeError as exc:
                if live_graph:
                    raise NativeFieldRuntimeError(
                        f"native graph-site STEP_MODEL API is unavailable or rejected: {exc}"
                    ) from exc
                raise
            status = _field_text(response, 1)
            if status == "graph-site-rejected":
                if not (live_graph or (replaying and replay_ticket is not None)):
                    raise NativeFieldRuntimeError("native graph-site rejection lacks its immutable ticket")
                if any(tag in response for tag in (*range(2, 14), 17, 28)):
                    raise NativeFieldRuntimeError("rejected native graph-site response carries admitted-step fields")
                required_tags = (14, 15, 16, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27)
                if any(tag not in response for tag in required_tags):
                    raise NativeFieldRuntimeError("rejected native graph-site response omits route evidence")
                ticket = graph_site_ticket if live_graph else replay_ticket
                assert isinstance(ticket, Mapping)
                candidate = _graph_ticket_value(ticket, "native_candidate")
                guard = _graph_ticket_value(ticket, "native_guard")
                expected_field_candidate_id = (
                    candidate_id
                    if live_graph
                    else _text(replay_step.get("field_candidate_id"), "field_candidate_id")
                )
                expected_ticket_id = _text(_graph_ticket_value(ticket, "ticket_id"), "ticket_id")
                native_predecessor_sha256 = _digest(
                    _field_text(response, 16),
                    "native_predecessor_sha256",
                )
                response_input_count = _field_u64(response, 21)
                response_sampler_sha256 = _digest(_field_text(response, 15), "sampler_sha256")
                response_input_sha256 = _digest(_field_text(response, 18), "input_tokens_sha256")
                if (
                    _field_u64(response, 20) != 0
                    or response_input_count != len(input_tokens)
                    or response_sampler_sha256 != sampler_sha256
                    or response_input_sha256 != input_tokens_sha256
                    or _field_text(response, 19) != operation_id
                    or _field_u64(response, 22) != candidate["seq_id"]
                    or _field_u64(response, 23) != candidate["position"]
                    or _field_text(response, 25) != expected_field_candidate_id
                    or _field_text(response, 26) != logical_sequence_id
                    or _field_text(response, 27) != expected_ticket_id
                    or native_predecessor_sha256 != _graph_ticket_value(ticket, "native_predecessor_sha256")
                ):
                    raise NativeFieldRuntimeError("rejected native graph-site response identity disagrees")
                receipt_wire = _field_bytes(response, 14)
                receipt_wire_sha256 = hashlib.sha256(receipt_wire).hexdigest()
                if (
                    _digest(_field_text(response, 24), "native_graph_site_receipt_wire_sha256")
                    != receipt_wire_sha256
                ):
                    raise NativeFieldRuntimeError("rejected native graph-site packed receipt digest disagrees")
                receipt = _decode_graph_site_receipt(receipt_wire)
                if receipt["admitted"] or receipt["field_candidate_id"] != expected_field_candidate_id:
                    raise NativeFieldRuntimeError("rejected native graph-site receipt admission or candidate disagrees")
                _validate_graph_site_route_evidence(receipt, ticket)
                native_preflight_sha256 = _graph_ticket_value(ticket, "native_preflight_sha256")
                expected_receipt_identity = {
                    "ticket_id": expected_ticket_id,
                    "ticket_sha256": _graph_ticket_value(ticket, "ticket_sha256"),
                    "preflight_sha256": _graph_ticket_value(ticket, "preflight_sha256"),
                    "native_preflight_sha256": native_preflight_sha256,
                    "source_sha256": source_sha256,
                    "model_sha256": _graph_ticket_value(ticket, "model_sha256"),
                    "tokenizer_sha256": _graph_ticket_value(ticket, "tokenizer_sha256"),
                    "task_id": task_id,
                    "sequence_id": logical_sequence_id,
                    "native_operation_id": operation_id,
                    "seq_id": candidate["seq_id"],
                    "position": candidate["position"],
                    "selected_token_id": -1,
                    "input_token_count": len(input_tokens),
                    "input_tokens_sha256": input_tokens_sha256,
                    "stage": candidate["stage"],
                    "layer": candidate["layer"],
                    "site": candidate["site"],
                    "specialist": candidate["specialist"],
                    "invocation_sha256": candidate["invocation_sha256"],
                    "candidate_sha256": candidate["candidate_sha256"],
                    "dependencies_json": candidate["dependencies_json"],
                    "method_key": candidate["method_key"],
                    "method_generation": candidate["method_generation"],
                    "intervention_order": candidate["intervention_order"],
                    "graph_predecessor_sha256": candidate["predecessor_sha256"],
                    "owner_snapshot_sha256": guard["owner_snapshot_sha256"],
                    "owner_field_epoch_sha256": _graph_ticket_value(ticket, "field_epoch_sha256"),
                    "native_field_epoch_sha256": _graph_ticket_value(ticket, "native_field_epoch_sha256"),
                    "native_predecessor_sha256": native_predecessor_sha256,
                    "sampler_sha256": sampler_sha256,
                    "sampler": sampler,
                }
                for key, expected_value in expected_receipt_identity.items():
                    if receipt.get(key) != expected_value:
                        raise NativeFieldRuntimeError(
                            f"rejected native graph-site receipt {key} disagrees with its ticket or request"
                        )
                receipt_sha256 = _canonical_json_sha256(receipt, "rejected native graph-site receipt")
                self._graph_site_preflights.pop(task_id, None)
                rejected_result: dict[str, Any] = {
                    "status": status,
                    "rejected": True,
                    "accepted": False,
                    "attempted": True,
                    "admitted": False,
                    "provisional": False,
                    "confirmable": False,
                    "task_id": task_id,
                    "sequence_id": logical_sequence_id,
                    "seq_id": candidate["seq_id"],
                    "position": candidate["position"],
                    "source_sha256": source_sha256,
                    "native_operation_id": operation_id,
                    "input_tokens": list(input_tokens),
                    "input_tokens_sha256": input_tokens_sha256,
                    "sampler": sampler,
                    "sampler_sha256": sampler_sha256,
                    "graph_site_ticket": ticket,
                    "graph_site_receipt": receipt,
                    "graph_site_receipt_sha256": receipt_sha256,
                    "native_graph_site_receipt_sha256": receipt_sha256,
                    "graph_receipt_wire_sha256": receipt_wire_sha256,
                    "native_graph_site_receipt_wire_sha256": receipt_wire_sha256,
                    "native_preflight_sha256": native_preflight_sha256,
                    "native_predecessor_sha256": native_predecessor_sha256,
                    "field_candidate_id": expected_field_candidate_id,
                    "candidate_id": expected_field_candidate_id,
                    "ticket_id": expected_ticket_id,
                    "ticket_sha256": _graph_ticket_value(ticket, "ticket_sha256"),
                    "actual_expert_ids": receipt["actual_expert_ids"],
                    "refusal": receipt["refusal"],
                    "request_sha256": receipt["request_sha256"],
                    "input_sha256": receipt["input_sha256"],
                    "output_sha256": receipt["output_sha256"],
                }
                return rejected_result
            selected_token_id = _field_u64(response, 2)
            end_of_generation = _field_u64(response, 3)
            replay_sha256 = _digest(_field_text(response, 4), "replay_sha256")
            token_count = _field_u64(response, 5)
            stage_trace_sha256 = _digest(_field_text(response, 6), "stage_trace_sha256")
            response_stage_trace: list[str] | None = None
            if live_graph:
                if 28 not in response:
                    raise NativeFieldRuntimeError("native graph-site response omits its measured stage trace")
                stage_trace_json = _field_text(response, 28)
                try:
                    response_stage_trace = json.loads(stage_trace_json)
                    canonical_stage_trace_json = json.dumps(
                        response_stage_trace,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    stage_trace_digest = _canonical_json_sha256(
                        response_stage_trace,
                        "native STEP_MODEL stage trace",
                    )
                    encoded_trace = [entry.encode("utf-8") for entry in response_stage_trace]
                except (TypeError, ValueError, UnicodeEncodeError) as exc:
                    raise NativeFieldRuntimeError("native STEP_MODEL stage trace is invalid JSON") from exc
                if (
                    not isinstance(response_stage_trace, list)
                    or not response_stage_trace
                    or len(response_stage_trace) > MAX_GRAPH_SITE_VECTOR
                    or any(not entry or len(entry_bytes) > MAX_GRAPH_SITE_TEXT for entry, entry_bytes in zip(response_stage_trace, encoded_trace))
                    or canonical_stage_trace_json != stage_trace_json
                    or stage_trace_digest != stage_trace_sha256
                ):
                    raise NativeFieldRuntimeError("native STEP_MODEL stage trace list or digest disagrees")
            elif 28 in response:
                raise NativeFieldRuntimeError("native runtime returned an unrequested graph stage trace list")
            if (
                not status
                or status != ("model-provisional" if live_graph else "model-advanced")
                or selected_token_id > 0x7FFFFFFF
                or end_of_generation not in {0, 1}
                or token_count != len(input_tokens) + 1
            ):
                raise NativeFieldRuntimeError("native model-step counters or status are invalid")
            accepted_flag = _field_u64(response, 20)
            response_input_count = _field_u64(response, 21)
            response_sampler_sha256 = _digest(_field_text(response, 15), "sampler_sha256")
            response_input_sha256 = _digest(_field_text(response, 18), "input_tokens_sha256")
            accepted = not live_graph
            if (
                response_input_count != len(input_tokens)
                or response_input_sha256 != input_tokens_sha256
                or response_sampler_sha256 != sampler_sha256
                or accepted_flag not in {0, 1}
                or bool(accepted_flag) != accepted
            ):
                raise NativeFieldRuntimeError("native model-step input digest, sampler digest, or acceptance state disagrees")
            response_operation_id = _field_text(response, 19) if 19 in response else ""
            if response_operation_id != (operation_id or ""):
                raise NativeFieldRuntimeError("native model-step operation id echo disagrees")
            response_sequence_id = _field_text(response, 26) if 26 in response else ""
            if response_sequence_id != (logical_sequence_id or ""):
                raise NativeFieldRuntimeError("native model-step logical sequence id echo disagrees")

            sequence_id = logical_sequence_id or ""
            seq_id: int | None = None
            position: int | None = None
            receipt: dict[str, Any] | None = None
            receipt_sha256: str | None = None
            receipt_wire_sha256: str | None = None
            native_predecessor_sha256: str | None = None
            native_successor_sha256: str | None = None
            native_preflight_sha256: str | None = None
            field_candidate_id: str | None = None
            candidate_successor_sha256: str | None = None
            graph_successor_sha256: str | None = None

            graph_result = live_graph or (replaying and replay_ticket is not None)
            if graph_result:
                receipt_wire = _field_bytes(response, 14)
                receipt_wire_sha256 = hashlib.sha256(receipt_wire).hexdigest()
                if (
                    _digest(_field_text(response, 24), "native_graph_site_receipt_wire_sha256")
                    != receipt_wire_sha256
                ):
                    raise NativeFieldRuntimeError("native graph-site packed receipt digest disagrees")
                receipt = _decode_graph_site_receipt(receipt_wire)
                field_candidate_id = receipt["field_candidate_id"]
                expected_field_candidate_id = (
                    candidate_id
                    if live_graph
                    else _text(replay_step.get("field_candidate_id"), "field_candidate_id")
                )
                if (
                    field_candidate_id != expected_field_candidate_id
                    or _field_text(response, 25) != expected_field_candidate_id
                ):
                    raise NativeFieldRuntimeError("native graph-site physical candidate id echo disagrees")
                expected_ticket_id = (
                    graph_site_ticket["ticket_id"] if live_graph else replay_ticket["ticket_id"]
                )
                if _field_text(response, 27) != expected_ticket_id:
                    raise NativeFieldRuntimeError("native graph-site ticket id echo disagrees")
                sequence_id = receipt["sequence_id"]
                seq_id = receipt["seq_id"]
                position = receipt["position"]
                native_preflight_sha256 = receipt["native_preflight_sha256"]
                native_predecessor_sha256 = _digest(
                    _field_text(response, 16),
                    "native_predecessor_sha256",
                )
                native_successor_sha256 = _digest(
                    _field_text(response, 17),
                    "native_successor_sha256",
                )
                ticket = graph_site_ticket if live_graph else replay_ticket
                assert isinstance(ticket, Mapping) and receipt is not None
                candidate = _graph_ticket_value(ticket, "native_candidate")
                guard = _graph_ticket_value(ticket, "native_guard")
                if live_graph:
                    assert preflight_entry is not None
                    graph_preflight = preflight_entry["preflight"]
                else:
                    graph_preflight = replay_preflight
                _validate_graph_site_route_evidence(receipt, ticket)
                if receipt["stage_trace_sha256"] != stage_trace_sha256:
                    raise NativeFieldRuntimeError("native STEP_MODEL stage trace digest disagrees with its receipt")
                if live_graph and response_stage_trace != receipt["stage_trace"]:
                    raise NativeFieldRuntimeError("native STEP_MODEL trace list disagrees with its measured receipt")
                if receipt["request_sha256"] != receipt["input_sha256"]:
                    raise NativeFieldRuntimeError("native graph-site request and synchronized input hashes disagree")
                candidate_successor_sha256 = _graph_successor_state_sha256(
                    receipt,
                    candidate=candidate,
                    preflight=graph_preflight,
                )
                graph_successor_sha256 = candidate_successor_sha256
                expected_receipt_identity = {
                    "ticket_id": ticket["ticket_id"],
                    "ticket_sha256": ticket["ticket_sha256"],
                    "preflight_sha256": ticket["preflight_sha256"],
                    "native_preflight_sha256": ticket["native_preflight_sha256"],
                    "source_sha256": source_sha256,
                    "model_sha256": ticket["model_sha256"],
                    "tokenizer_sha256": ticket["tokenizer_sha256"],
                    "task_id": task_id,
                    "field_candidate_id": expected_field_candidate_id,
                    "sequence_id": logical_sequence_id,
                    "native_operation_id": operation_id,
                    "seq_id": candidate["seq_id"],
                    "position": candidate["position"],
                    "selected_token_id": selected_token_id,
                    "stage": candidate["stage"],
                    "layer": candidate["layer"],
                    "site": candidate["site"],
                    "specialist": candidate["specialist"],
                    "invocation_sha256": candidate["invocation_sha256"],
                    "candidate_sha256": candidate["candidate_sha256"],
                    "dependencies_json": candidate["dependencies_json"],
                    "method_key": candidate["method_key"],
                    "method_generation": candidate["method_generation"],
                    "intervention_order": candidate["intervention_order"],
                    "graph_predecessor_sha256": candidate["predecessor_sha256"],
                    "owner_snapshot_sha256": guard["owner_snapshot_sha256"],
                    "owner_field_epoch_sha256": ticket["field_epoch_sha256"],
                    "native_field_epoch_sha256": ticket["native_field_epoch_sha256"],
                    "native_predecessor_sha256": ticket["native_predecessor_sha256"],
                    "sampler_sha256": sampler_sha256,
                    "stage_trace_sha256": stage_trace_sha256,
                    "input_token_count": len(input_tokens),
                    "input_tokens_sha256": input_tokens_sha256,
                    "replay_sha256": replay_sha256,
                    "token_count": token_count,
                    "native_successor_sha256": native_successor_sha256,
                }
                for key, expected_value in expected_receipt_identity.items():
                    if receipt.get(key) != expected_value:
                        raise NativeFieldRuntimeError(
                            f"native graph-site measured receipt {key} disagrees with ticket or step"
                        )
                if receipt["native_predecessor_sha256"] != native_predecessor_sha256:
                    raise NativeFieldRuntimeError("native graph-site receipt predecessor echo disagrees")
                if live_graph:
                    assert preflight_entry is not None
                    if native_predecessor_sha256 != preflight_entry["preflight"]["native_predecessor_sha256"]:
                        raise NativeFieldRuntimeError("native graph-site predecessor changed after preflight")
                receipt_sha256 = _canonical_json_sha256(receipt, "native graph-site receipt")
                if replaying:
                    if (
                        receipt_sha256
                        != _digest(
                            replay_step.get("native_graph_site_receipt_sha256"),
                            "native_graph_site_receipt_sha256",
                        )
                        or receipt_wire_sha256
                        != _digest(
                            replay_step.get("native_graph_site_receipt_wire_sha256"),
                            "native_graph_site_receipt_wire_sha256",
                        )
                    ):
                        raise NativeFieldRuntimeError("native graph-site replay receipt digest disagrees")
            else:
                # Native always echoes state roots (16/17) and empty proof
                # slots; only a receipt or a nonempty proof identity is graph work.
                if 14 in response or any(
                    tag in response and _field_text(response, tag) for tag in (24, 25, 27)
                ):
                    raise NativeFieldRuntimeError(
                        "ordinary native model step unexpectedly returned graph-site proof"
                    )
                seq_id = _field_u64(response, 22)
                position = _field_u64(response, 23)
                if replaying and (
                    seq_id != replay_step["seq_id"]
                    or position != replay_step["position"]
                ):
                    raise NativeFieldRuntimeError("native owner-history replay sequence position disagrees")

            # A fused group row measured its stage trace over the whole batch;
            # its singleton replay must reproduce the token and replay digest.
            grouped_row = replaying and replay_step.get("execution") == "native-group"
            if replaying and (
                selected_token_id != replay_step["selected_token"]
                or replay_sha256 != replay_step["replay_sha256"]
                or token_count != replay_step["token_count"]
                or (not grouped_row and stage_trace_sha256 != replay_step["stage_trace_sha256"])
                or (
                    receipt is not None
                    and "stage_trace" in replay_step
                    and receipt["stage_trace"] != replay_step["stage_trace"]
                )
            ):
                raise NativeFieldRuntimeError("native owner-history replay output differs from its accepted step")
            if replaying and replay_ticket is not None and (
                native_predecessor_sha256 != replay_step["native_predecessor_sha256"]
                or native_successor_sha256 != replay_step["native_successor_sha256"]
                or native_preflight_sha256 != replay_step["native_preflight_sha256"]
            ):
                raise NativeFieldRuntimeError("native graph-site replay state digest disagrees")

            result = {
                "status": status,
                "token": selected_token_id,
                "selected_token_id": selected_token_id,
                "accepted": accepted,
                "provisional": live_graph,
                "end_of_generation": bool(end_of_generation),
                "replay_sha256": replay_sha256,
                "token_count": token_count,
                "stage_trace_sha256": stage_trace_sha256,
                "exact_stages": _field_u64(response, 7),
                "embedding_stages": _field_u64(response, 8),
                "attention_stages": _field_u64(response, 9),
                "ffn_stages": _field_u64(response, 10),
                "head_stages": _field_u64(response, 11),
                "ggml_nodes": _field_u64(response, 12),
                "logical_weight_bytes": _field_u64(response, 13),
                "task_id": task_id,
                "sequence_id": sequence_id,
                "seq_id": seq_id,
                "position": position,
                "source_sha256": source_sha256,
                "native_operation_id": operation_id,
                "input_tokens": list(input_tokens),
                "input_tokens_sha256": input_tokens_sha256,
                "sampler": sampler,
                "sampler_sha256": sampler_sha256,
            }
            if accepted:
                result["accepted_token_id"] = selected_token_id
            if operation_id is not None:
                result["native_operation_id"] = _field_text(response, 19)
            if receipt is not None:
                ticket = graph_site_ticket if live_graph else replay_ticket
                assert isinstance(ticket, Mapping)
                result.update(
                    {
                        "graph_site_ticket": ticket,
                        "stage_trace": receipt["stage_trace"],
                        "actual_expert_ids": receipt["actual_expert_ids"],
                        "graph_site_receipt": receipt,
                        "graph_site_receipt_sha256": receipt_sha256,
                        "native_graph_site_receipt_sha256": receipt_sha256,
                        "graph_receipt_wire_sha256": receipt_wire_sha256,
                        "native_graph_site_receipt_wire_sha256": receipt_wire_sha256,
                        "native_preflight_sha256": native_preflight_sha256,
                        "native_predecessor_sha256": native_predecessor_sha256,
                        "native_successor_sha256": native_successor_sha256,
                        "field_candidate_id": field_candidate_id,
                        "ticket_id": ticket["ticket_id"],
                        "ticket_sha256": ticket["ticket_sha256"],
                        "request_sha256": receipt["request_sha256"],
                        "input_sha256": receipt["input_sha256"],
                        "output_sha256": receipt["output_sha256"],
                        "candidate_successor_sha256": candidate_successor_sha256,
                        "graph_successor_sha256": graph_successor_sha256,
                        "model_embedding_width": graph_preflight["model_embedding_width"],
                        "model_layer_count": graph_preflight["model_layer_count"],
                    }
                )
                if live_graph:
                    result["candidate_id"] = candidate_id

            signature = {
                "native_operation_id": operation_id,
                "sequence_id": logical_sequence_id,
                "seq_id": seq_id,
                "position": position,
                "input_tokens": list(input_tokens),
                "sampler": sampler,
                "sampler_sha256": sampler_sha256,
                "accepted_token_id": selected_token_id,
                "replay_sha256": replay_sha256,
                "token_count": token_count,
                "stage_trace_sha256": stage_trace_sha256,
            }
            if receipt is not None:
                signature.update(
                    {
                        "ticket_sha256": receipt["ticket_sha256"],
                        "stage_trace": receipt["stage_trace"],
                        "native_graph_site_receipt_sha256": receipt_sha256,
                        "native_graph_site_receipt_wire_sha256": receipt_wire_sha256,
                        "native_predecessor_sha256": native_predecessor_sha256,
                        "native_successor_sha256": native_successor_sha256,
                        "native_preflight_sha256": native_preflight_sha256,
                        "graph_successor_sha256": graph_successor_sha256,
                        "model_embedding_width": graph_preflight["model_embedding_width"],
                        "model_layer_count": graph_preflight["model_layer_count"],
                    }
                )
            if live_graph:
                self._pending_graph_site_candidates[candidate_id] = {
                    "candidate_id": candidate_id,
                    "task_id": task_id,
                    "source_sha256": source_sha256,
                    "native_operation_id": operation_id,
                    "input_tokens": input_tokens,
                    "sampler": sampler,
                    "sampler_sha256": sampler_sha256,
                    "selected_token_id": selected_token_id,
                    "receipt": receipt,
                    "receipt_sha256": receipt_sha256,
                    "receipt_wire_sha256": receipt_wire_sha256,
                    "ticket_id": graph_site_ticket["ticket_id"],
                    "ticket_sha256": graph_site_ticket["ticket_sha256"],
                    "signature": signature,
                    "preflight": preflight_entry["preflight"] if preflight_entry else None,
                }
                self._graph_site_preflights.pop(task_id, None)
            else:
                state = self._model_task_states.setdefault(
                    task_id,
                    {
                        "service_generation": self.service_generation,
                        "source_sha256": source_sha256,
                        "accepted_steps": [],
                        "initialized": True,
                    },
                )
                state["source_sha256"] = source_sha256
                if receipt is not None:
                    state["model_sha256"] = receipt["model_sha256"]
                    state["tokenizer_sha256"] = receipt["tokenizer_sha256"]
                state["input_tokens"] = input_tokens
                state["accepted_token_id"] = selected_token_id
                state["accepted_steps"].append(signature)
                state["initialized"] = True
            return result
        except BaseException:
            if live_graph and candidate_id is not None:
                try:
                    self.discard_candidate(candidate_id)
                except Exception:
                    pass
                self._graph_site_preflights.pop(task_id, None)
            raise

    def drop_model_task(self, task_id: str) -> dict[str, str]:
        task_id = _text(task_id, "task_id")
        if any(
            pending["task_id"] == task_id
            for pending in self._pending_graph_site_candidates.values()
        ):
            raise NativeFieldRuntimeError("cannot drop a native model task with an unacknowledged graph candidate")
        response = self._request(DROP_MODEL_TASK, (_utf8(1, task_id),))
        status = _field_text(response, 1)
        if status not in {"model-task-dropped", "model-task-absent"}:
            raise NativeFieldRuntimeError("native model-task drop returned an invalid status")
        if _field_text(response, 2) != task_id:
            raise NativeFieldRuntimeError("native model-task drop identity disagrees")
        self._graph_site_preflights.pop(task_id, None)
        self._model_task_states.pop(task_id, None)
        return {"status": status, "task_id": task_id}
    def rebuild_task_from_owner_history(
        self,
        task_id: str,
        source_sha256: str,
        model_id: str,
        tokenizer_id: str,
        owner_history: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Recreate disposable model state from the owner's accepted history."""

        task_id = _text(task_id, "task_id")
        if len(task_id.encode("utf-8")) > 127:
            raise NativeFieldRuntimeError("native model task id exceeds the C API bound")
        source_sha256 = _digest(source_sha256, "source_sha256")
        model_id = _digest(model_id, "model_id")
        tokenizer_id = _digest(tokenizer_id, "tokenizer_id")
        if source_sha256 not in self._verified_model_sources:
            raise NativeFieldRuntimeError("owner replay source is not registered with the native runtime")
        if not isinstance(owner_history, Mapping):
            raise NativeFieldRuntimeError("owner replay history must be a mapping")
        if owner_history.get("schema") != "cassifi.native-graph-site-replay-history.v1":
            raise NativeFieldRuntimeError("owner replay history schema is unsupported")
        if owner_history.get("history_complete") is not True:
            raise NativeFieldRuntimeError("owner replay history is incomplete")
        if (
            owner_history.get("task_id") != task_id
            or owner_history.get("source_sha256") != source_sha256
            or owner_history.get("model_id") != model_id
            or owner_history.get("tokenizer_id") != tokenizer_id
        ):
            raise NativeFieldRuntimeError("owner replay task, source, model, or tokenizer identity disagrees")
        model_task_id = _text(owner_history.get("model_task_id"), "model_task_id")
        prompt_value = owner_history.get("prompt_tokens")
        if not isinstance(prompt_value, list):
            raise NativeFieldRuntimeError("owner replay prompt tokens must be a list")
        prompt_tokens, _, _ = _model_token_history(prompt_value)
        raw_steps = owner_history.get("accepted_steps")
        if (
            not isinstance(raw_steps, list)
            or len(raw_steps) > MAX_GRAPH_SITE_VECTOR
        ):
            raise NativeFieldRuntimeError("owner replay accepted steps are invalid or exceed their bound")

        prepared_steps: list[dict[str, Any]] = []
        owner_operation_ids: set[str] = set()
        native_operation_ids: set[str] = set()
        sequence_positions: set[tuple[str, int]] = set()
        previous_input: tuple[int, ...] | None = None
        previous_token: int | None = None
        previous_position: int | None = None
        previous_generation: int | None = None
        previous_owner_operation_id: str | None = None
        graph_sequence_index = 0
        for index, raw_step in enumerate(raw_steps):
            if not isinstance(raw_step, Mapping):
                raise NativeFieldRuntimeError("owner replay step must be a mapping")
            if raw_step.get("history_complete") is not True:
                raise NativeFieldRuntimeError("owner replay step history is incomplete")
            sequence_index = raw_step.get("sequence_index")
            generation = raw_step.get("generation")
            owner_operation_id = _text(raw_step.get("owner_operation_id"), "owner_operation_id")
            native_operation_id = _text(raw_step.get("native_operation_id"), "native_operation_id")
            # Later steps of one token run share its owner transition.
            run_continuation = (
                previous_owner_operation_id is not None
                and owner_operation_id == previous_owner_operation_id
                and generation == previous_generation
            )
            if (
                isinstance(sequence_index, bool)
                or not isinstance(sequence_index, int)
                or sequence_index != index
                or isinstance(generation, bool)
                or not isinstance(generation, int)
                or generation < 0
                or (
                    previous_generation is not None
                    and generation <= previous_generation
                    and not run_continuation
                )
            ):
                raise NativeFieldRuntimeError("owner replay step ordering is invalid")
            previous_generation = generation
            previous_owner_operation_id = owner_operation_id
            if (
                not run_continuation
                and owner_operation_id != f"resident-model-resume:{native_operation_id}"
            ):
                raise NativeFieldRuntimeError("owner replay operation id lacks its resident-model prefix")
            if (
                len(native_operation_id.encode("utf-8")) > 127
                or (not run_continuation and owner_operation_id in owner_operation_ids)
                or native_operation_id in native_operation_ids
            ):
                raise NativeFieldRuntimeError("owner replay operation identity is invalid or duplicated")
            owner_operation_ids.add(owner_operation_id)
            native_operation_ids.add(native_operation_id)
            if (
                raw_step.get("task_id") != task_id
                or raw_step.get("source_sha256") != source_sha256
                or (
                    raw_step.get("model_id") is not None
                    and raw_step.get("model_id") != model_id
                )
                or (
                    raw_step.get("tokenizer_id") is not None
                    and raw_step.get("tokenizer_id") != tokenizer_id
                )
            ):
                raise NativeFieldRuntimeError("owner replay step task/model identity disagrees")
            sequence_id = _text(raw_step.get("sequence_id"), "sequence_id")
            if sequence_id == task_id:
                raise NativeFieldRuntimeError("owner replay logical sequence identity is invalid")
            raw_inputs = raw_step.get("input_tokens")
            if not isinstance(raw_inputs, list):
                raise NativeFieldRuntimeError("owner replay input tokens must be a list")
            input_tokens, _, input_tokens_sha256 = _model_token_history(raw_inputs)
            position = raw_step.get("position")
            seq_id = raw_step.get("seq_id")
            if (
                isinstance(position, bool)
                or not isinstance(position, int)
                or position < 0
                or position != len(input_tokens)
                or isinstance(seq_id, bool)
                or not isinstance(seq_id, int)
                or not 0 <= seq_id <= 0x7FFFFFFF
            ):
                raise NativeFieldRuntimeError("owner replay native sequence position is invalid")
            identity = (sequence_id, position)
            if identity in sequence_positions:
                raise NativeFieldRuntimeError("owner replay repeats a logical sequence position")
            sequence_positions.add(identity)
            if previous_input is None:
                if input_tokens != prompt_tokens:
                    raise NativeFieldRuntimeError("owner replay history does not begin at the retained prompt")
            elif (
                input_tokens != previous_input + (previous_token,)
                or position != previous_position + 1
            ):
                raise NativeFieldRuntimeError("owner replay history has a token or position gap")
            selected_token = raw_step.get("selected_token")
            accepted_token_id = raw_step.get("accepted_token_id")
            if (
                isinstance(selected_token, bool)
                or not isinstance(selected_token, int)
                or not 0 <= selected_token <= 0x7FFFFFFF
                or isinstance(accepted_token_id, bool)
                or not isinstance(accepted_token_id, int)
                or accepted_token_id != selected_token
            ):
                raise NativeFieldRuntimeError("owner replay accepted token identity is invalid")
            token_count = raw_step.get("token_count")
            if (
                isinstance(token_count, bool)
                or not isinstance(token_count, int)
                or token_count != len(input_tokens) + 1
            ):
                raise NativeFieldRuntimeError("owner replay token count is inconsistent")
            sampler, sampler_sha256 = _normalized_graph_site_sampler(raw_step.get("sampler"))
            if _digest(raw_step.get("sampler_sha256"), "sampler_sha256") != sampler_sha256:
                raise NativeFieldRuntimeError("owner replay sampler digest disagrees")
            replay_sha256 = _digest(raw_step.get("replay_sha256"), "replay_sha256")
            stage_trace_sha256 = _digest(raw_step.get("stage_trace_sha256"), "stage_trace_sha256")
            graph_ticket = raw_step.get("graph_site_ticket")
            if raw_step.get("execution") not in {None, "native-group"} or (
                graph_ticket is not None and raw_step.get("execution") is not None
            ):
                raise NativeFieldRuntimeError("owner replay row execution provenance is invalid")
            if graph_ticket is None:
                if any(
                    raw_step.get(key) is not None
                    for key in (
                        "graph_site_receipt",
                        "graph_site_receipt_sha256",
                        "native_graph_site_receipt_sha256",
                        "graph_receipt_wire_sha256",
                        "native_graph_site_receipt_wire_sha256",
                        "field_candidate_id",
                        "ticket_id",
                        "ticket_sha256",
                        "native_predecessor_sha256",
                        "native_successor_sha256",
                        "native_preflight_sha256",
                        "candidate_successor_sha256",
                        "graph_successor_sha256",
                        "field_predecessor_sha256",
                        "field_successor_sha256",
                        "model_embedding_width",
                        "model_layer_count",
                    )
                ):
                    raise NativeFieldRuntimeError("ordinary owner replay row unexpectedly carries graph proof")
                row_graph_index = graph_sequence_index
            else:
                if not isinstance(graph_ticket, Mapping):
                    raise NativeFieldRuntimeError("owner replay graph ticket is invalid")
                receipt = raw_step.get("graph_site_receipt")
                if not isinstance(receipt, Mapping):
                    raise NativeFieldRuntimeError("owner graph replay row lacks its measured receipt")
                ticket_candidate = _graph_ticket_value(graph_ticket, "native_candidate")
                ticket_preflight = _graph_ticket_value(graph_ticket, "preflight")
                if not isinstance(ticket_preflight, Mapping):
                    raise NativeFieldRuntimeError("owner graph ticket preflight is invalid")
                ticket_sampler, ticket_sampler_sha256 = _normalized_graph_site_sampler(
                    _graph_ticket_value(graph_ticket, "sampler")
                )
                ticket_native_predecessor = _digest(
                    _graph_ticket_value(graph_ticket, "native_predecessor_sha256"),
                    "native_predecessor_sha256",
                )
                ticket_native_preflight = _digest(
                    _graph_ticket_value(graph_ticket, "native_preflight_sha256"),
                    "native_preflight_sha256",
                )
                ticket_field_predecessor = _digest(
                    _graph_ticket_value(graph_ticket, "field_state_sha256"),
                    "field_state_sha256",
                )
                ticket_graph_predecessor = _digest(
                    _graph_ticket_value(graph_ticket, "graph_predecessor_sha256"),
                    "graph_predecessor_sha256",
                )
                row_field_predecessor = _digest(
                    raw_step.get("field_predecessor_sha256"),
                    "field_predecessor_sha256",
                )
                row_field_successor = _digest(
                    raw_step.get("field_successor_sha256"),
                    "field_successor_sha256",
                )
                if (
                    _graph_ticket_value(graph_ticket, "task_id") != task_id
                    or _graph_ticket_value(graph_ticket, "model_task_id") != model_task_id
                    or _graph_ticket_value(graph_ticket, "operation_id") != native_operation_id
                    or _graph_ticket_value(graph_ticket, "sequence_id") != sequence_id
                    or _graph_ticket_value(graph_ticket, "native_operation_id") != native_operation_id
                    or _graph_ticket_value(graph_ticket, "seq_id") != raw_step.get("seq_id")
                    or _graph_ticket_value(graph_ticket, "position") != raw_step.get("position")
                    or _graph_ticket_value(ticket_candidate, "sequence_id") != sequence_id
                    or _graph_ticket_value(ticket_candidate, "source_sha256") != source_sha256
                    or _graph_ticket_value(ticket_candidate, "seq_id") != raw_step.get("seq_id")
                    or _graph_ticket_value(ticket_candidate, "position") != raw_step.get("position")
                    or _graph_ticket_value(graph_ticket, "source_sha256") != source_sha256
                    or _graph_ticket_value(graph_ticket, "model_sha256") != model_id
                    or _graph_ticket_value(graph_ticket, "tokenizer_sha256") != tokenizer_id
                    or ticket_sampler != sampler
                    or ticket_sampler_sha256 != sampler_sha256
                    or raw_step.get("ticket_id") != _graph_ticket_value(graph_ticket, "ticket_id")
                    or raw_step.get("ticket_sha256") != _graph_ticket_value(graph_ticket, "ticket_sha256")
                ):
                    raise NativeFieldRuntimeError("owner replay graph ticket identity disagrees with the history")
                if (
                    ticket_preflight.get("task_id") != task_id
                    or ticket_preflight.get("sequence_id") != sequence_id
                    or ticket_preflight.get("native_operation_id") != native_operation_id
                    or ticket_preflight.get("source_sha256") != source_sha256
                    or ticket_preflight.get("model_sha256") != model_id
                    or ticket_preflight.get("tokenizer_sha256") != tokenizer_id
                    or ticket_preflight.get("native_predecessor_sha256") != ticket_native_predecessor
                    or ticket_preflight.get("native_preflight_sha256") != ticket_native_preflight
                    or ticket_preflight.get("sampler") != ticket_sampler
                    or ticket_preflight.get("sampler_sha256") != ticket_sampler_sha256
                    or ticket_preflight.get("native_seq_id", ticket_preflight.get("seq_id"))
                    != raw_step.get("seq_id")
                    or ticket_preflight.get("next_position", ticket_preflight.get("position"))
                    != raw_step.get("position")
                ):
                    raise NativeFieldRuntimeError("owner replay graph ticket preflight disagrees with the history")
                model_embedding_width = _graph_site_u32_value(
                    raw_step.get("model_embedding_width"),
                    "model_embedding_width",
                )
                model_layer_count = _graph_site_u32_value(
                    raw_step.get("model_layer_count"),
                    "model_layer_count",
                )
                if model_embedding_width == 0 or model_layer_count == 0:
                    raise NativeFieldRuntimeError("owner replay model geometry is invalid")
                if (
                    ticket_preflight.get("model_embedding_width") != model_embedding_width
                    or ticket_preflight.get("model_layer_count") != model_layer_count
                ):
                    raise NativeFieldRuntimeError("owner replay graph ticket geometry disagrees with the history")
                if (
                    ticket_field_predecessor != row_field_predecessor
                    or ticket_graph_predecessor != row_field_predecessor
                ):
                    raise NativeFieldRuntimeError("owner replay graph field predecessor disagrees with the ticket")
                row_native_predecessor = _digest(
                    raw_step.get("native_predecessor_sha256"),
                    "native_predecessor_sha256",
                )
                row_native_successor = _digest(
                    raw_step.get("native_successor_sha256"),
                    "native_successor_sha256",
                )
                row_native_preflight = _digest(
                    raw_step.get("native_preflight_sha256"),
                    "native_preflight_sha256",
                )
                field_candidate_id = _text(raw_step.get("field_candidate_id"), "field_candidate_id")
                if (
                    row_native_predecessor != ticket_native_predecessor
                    or row_native_preflight != ticket_native_preflight
                    or receipt.get("field_candidate_id") != field_candidate_id
                    or receipt.get("ticket_id") != _graph_ticket_value(graph_ticket, "ticket_id")
                    or receipt.get("ticket_sha256") != _graph_ticket_value(graph_ticket, "ticket_sha256")
                    or receipt.get("native_predecessor_sha256") != ticket_native_predecessor
                    or receipt.get("native_preflight_sha256") != ticket_native_preflight
                    or receipt.get("native_successor_sha256") != row_native_successor
                    or receipt.get("task_id") != task_id
                    or receipt.get("sequence_id") != sequence_id
                    or receipt.get("native_operation_id") != native_operation_id
                    or receipt.get("seq_id") != raw_step.get("seq_id")
                    or receipt.get("position") != raw_step.get("position")
                    or receipt.get("source_sha256") != source_sha256
                    or receipt.get("model_sha256") != model_id
                    or receipt.get("tokenizer_sha256") != tokenizer_id
                    or receipt.get("preflight_sha256")
                    != _graph_ticket_value(graph_ticket, "preflight_sha256")
                    or receipt.get("sampler") != sampler
                    or receipt.get("sampler_sha256") != sampler_sha256
                ):
                    raise NativeFieldRuntimeError("owner replay graph receipt checkpoint anchors disagree")
                _validate_graph_site_route_evidence(receipt, graph_ticket)
                receipt_stage_trace = receipt.get("stage_trace")
                receipt_stage_trace_sha256 = _digest(
                    receipt.get("stage_trace_sha256"),
                    "stage_trace_sha256",
                )
                if (
                    receipt.get("attempted") is not True
                    or receipt.get("admitted") is not True
                    or receipt.get("refusal")
                    or receipt.get("selected_token_id") != selected_token
                    or receipt.get("input_token_count") != len(input_tokens)
                    or receipt.get("input_tokens_sha256") != input_tokens_sha256
                    or receipt.get("replay_sha256") != replay_sha256
                    or receipt.get("token_count") != token_count
                    or receipt.get("sampler") != sampler
                    or receipt.get("sampler_sha256") != sampler_sha256
                    or receipt.get("request_sha256") != receipt.get("input_sha256")
                    or not isinstance(receipt_stage_trace, list)
                    or not receipt_stage_trace
                    or any(not isinstance(event, str) or not event for event in receipt_stage_trace)
                    or raw_step.get("stage_trace") != receipt_stage_trace
                    or receipt_stage_trace_sha256 != stage_trace_sha256
                    or _canonical_json_sha256(receipt_stage_trace, "owner replay stage trace")
                    != receipt_stage_trace_sha256
                ):
                    raise NativeFieldRuntimeError("owner replay graph receipt step or trace binding disagrees")
                expected_successor = _graph_successor_state_sha256(
                    receipt,
                    candidate=ticket_candidate,
                    preflight={
                        "model_embedding_width": model_embedding_width,
                        "model_layer_count": model_layer_count,
                    },
                )
                if (
                    _digest(raw_step.get("graph_successor_sha256"), "graph_successor_sha256")
                    != expected_successor
                    or _canonical_json_sha256(receipt, "owner replay graph receipt")
                    != _digest(
                        raw_step.get("native_graph_site_receipt_sha256"),
                        "native_graph_site_receipt_sha256",
                    )
                    or _digest(
                        raw_step.get("graph_receipt_wire_sha256"),
                        "graph_receipt_wire_sha256",
                    )
                    != _digest(
                        raw_step.get("native_graph_site_receipt_wire_sha256"),
                        "native_graph_site_receipt_wire_sha256",
                    )
                ):
                    raise NativeFieldRuntimeError("owner replay graph receipt or successor binding disagrees")
                row_graph_index = graph_sequence_index
                graph_sequence_index += 1

            prepared = dict(raw_step)
            prepared["sampler"] = sampler
            prepared["sampler_sha256"] = sampler_sha256
            prepared["graph_sequence_index"] = row_graph_index
            prepared["input_tokens_sha256"] = input_tokens_sha256
            prepared["replay_sha256"] = replay_sha256
            prepared["stage_trace_sha256"] = stage_trace_sha256
            prepared_steps.append(prepared)
            previous_input = input_tokens
            previous_token = selected_token
            previous_position = position

        self.drop_model_task(task_id)
        if not prepared_steps:
            return {
                "status": "history-empty",
                "task_id": task_id,
                "source_sha256": source_sha256,
                "model_sha256": model_id,
                "tokenizer_sha256": tokenizer_id,
                "replayed_steps": 0,
                "token_count": 0,
                "final_replay_sha256": None,
                "final_stage_trace_sha256": None,
            }

        last_result: dict[str, Any] | None = None
        try:
            for step in prepared_steps:
                sampler = step["sampler"]
                last_result = self.step_model(
                    task_id,
                    source_sha256,
                    step["input_tokens"],
                    sampler_mode=sampler["mode"],
                    temperature=sampler["temperature"],
                    top_k=sampler["top_k"],
                    draw=sampler["draw"],
                    sequence_id=step["sequence_id"],
                    native_operation_id=step["native_operation_id"],
                    replay_step=step,
                )
                if (
                    last_result.get("accepted") is not True
                    or last_result.get("selected_token_id") != step["selected_token"]
                ):
                    raise NativeFieldRuntimeError("native owner-history replay did not accept its exact row")
        except BaseException:
            try:
                self.drop_model_task(task_id)
            except Exception:
                self._graph_site_preflights.pop(task_id, None)
                self._model_task_states.pop(task_id, None)
            raise

        assert last_result is not None
        result: dict[str, Any] = {
            "status": "history-replayed",
            "task_id": task_id,
            "source_sha256": source_sha256,
            "model_sha256": model_id,
            "tokenizer_sha256": tokenizer_id,
            "replayed_steps": len(prepared_steps),
            "token_count": last_result["token_count"],
            "final_replay_sha256": last_result["replay_sha256"],
            "final_stage_trace_sha256": last_result["stage_trace_sha256"],
        }
        if last_result.get("graph_site_receipt") is not None:
            for name in (
                "graph_site_ticket",
                "graph_site_receipt",
                "graph_site_receipt_sha256",
                "native_graph_site_receipt_sha256",
                "graph_receipt_wire_sha256",
                "native_graph_site_receipt_wire_sha256",
                "request_sha256",
                "input_sha256",
                "output_sha256",
                "candidate_successor_sha256",
                "graph_successor_sha256",
                "field_candidate_id",
                "candidate_id",
                "ticket_id",
                "ticket_sha256",
                "native_preflight_sha256",
                "native_predecessor_sha256",
                "native_successor_sha256",
                "model_embedding_width",
                "model_layer_count",
                "stage_trace",
                "stage_trace_sha256",
                "actual_expert_ids",
            ):
                if name in last_result:
                    result[name] = last_result[name]
        return result


    def create_group(
        self, source_sha256: str, capacity: int
    ) -> dict[str, Any]:
        """Create one llama.cpp group host bound to a registered model source."""

        if isinstance(capacity, bool) or not isinstance(capacity, int) or not 2 <= capacity <= 8:
            raise NativeFieldRuntimeError("group capacity is outside its bound")
        response = self._request(
            CREATE_GROUP,
            (_utf8(21, _digest(source_sha256, "source_sha256")), _u64(22, capacity)),
        )
        if _field_text(response, 1) != "group-created":
            raise NativeFieldRuntimeError("native runtime did not create a group")
        if _field_u64(response, 21) != capacity:
            raise NativeFieldRuntimeError("native group capacity echo disagrees")
        return {
            "status": "group-created",
            "group_id": _field_u64(response, 2),
            "capacity": capacity,
            "group_count": _field_u64(response, 22),
        }

    def step_group(
        self, group_id: int, rows: Sequence[NativeGroupRow]
    ) -> dict[str, Any]:
        """Advance every row of one group with its exact committed history."""

        if isinstance(group_id, bool) or not isinstance(group_id, int) or group_id < 1:
            raise NativeFieldRuntimeError("group id must be a positive integer")
        if isinstance(rows, (str, bytes, dict)) or not isinstance(rows, (tuple, list)) or not 2 <= len(rows) <= 8:
            raise NativeFieldRuntimeError("group row count is outside its bound")
        blob = b"".join(row.encode() for row in rows)
        response = self._request(STEP_GROUP, (_u64(21, group_id), _bytes(22, blob)))
        if _field_text(response, 1) != "group-advanced":
            raise NativeFieldRuntimeError("native runtime did not advance the group")
        if _field_u64(response, 2) != group_id:
            raise NativeFieldRuntimeError("native group response identity disagrees")
        row_count = _field_u64(response, 22)
        if row_count != len(rows):
            raise NativeFieldRuntimeError("native group row count disagrees")
        parsed = _decode_group_results(_field_bytes(response, 21), row_count)
        candidate_status = _field_text(response, 23)
        if candidate_status != "unavailable_native_group_candidate":
            raise NativeFieldRuntimeError("native group graph-candidate capability is unknown")
        return {
            "status": "group-advanced",
            "group_id": group_id,
            "rows": parsed,
            "row_count": row_count,
            "native_graph_candidate": candidate_status,
        }

    def drop_group(self, group_id: int) -> dict[str, Any]:
        """Release one group host; identifiers are never reused."""

        if isinstance(group_id, bool) or not isinstance(group_id, int) or group_id < 1:
            raise NativeFieldRuntimeError("group id must be a positive integer")
        response = self._request(DROP_GROUP, (_u64(21, group_id),))
        status_value = _field_text(response, 1)
        if status_value not in {"group-dropped", "group-absent"}:
            raise NativeFieldRuntimeError("native runtime returned an unknown group drop status")
        if _field_u64(response, 2) != group_id:
            raise NativeFieldRuntimeError("native group response identity disagrees")
        return {
            "status": status_value,
            "group_id": group_id,
            "group_count": _field_u64(response, 21),
        }

    def leave_group(self, group_id: int, row: int) -> dict[str, Any]:
        """Free one seat; the group and its other seats' sequences stay resident."""

        if isinstance(group_id, bool) or not isinstance(group_id, int) or group_id < 1:
            raise NativeFieldRuntimeError("group id must be a positive integer")
        if isinstance(row, bool) or not isinstance(row, int) or not 0 <= row < 8:
            raise NativeFieldRuntimeError("group row index is outside its bound")
        response = self._request(LEAVE_GROUP, (_u64(21, group_id), _u64(22, row)))
        status_value = _field_text(response, 1)
        if status_value not in {"group-row-left", "group-row-idle"}:
            raise NativeFieldRuntimeError("native runtime returned an unknown group leave status")
        if _field_u64(response, 2) != group_id or _field_u64(response, 21) != row:
            raise NativeFieldRuntimeError("native group leave identity disagrees")
        return {"status": status_value, "group_id": group_id, "row": row}

    def join_group(self, group_id: int) -> dict[str, Any]:
        """Seat a newcomer in the first free seat with a wiped native sequence."""

        if isinstance(group_id, bool) or not isinstance(group_id, int) or group_id < 1:
            raise NativeFieldRuntimeError("group id must be a positive integer")
        response = self._request(JOIN_GROUP, (_u64(21, group_id),))
        status_value = _field_text(response, 1)
        if _field_u64(response, 2) != group_id:
            raise NativeFieldRuntimeError("native group join identity disagrees")
        if status_value == "group-full":
            return {"status": status_value, "group_id": group_id}
        if status_value != "group-row-joined":
            raise NativeFieldRuntimeError("native runtime returned an unknown group join status")
        row = _field_u64(response, 21)
        if not 0 <= row < 8:
            raise NativeFieldRuntimeError("native group join returned an invalid seat")
        return {
            "status": status_value,
            "group_id": group_id,
            "row": row,
            "member_generation": _field_u64(response, 22),
        }

    def shutdown(self) -> None:
        if self._pipe.value:
            self._request(SHUTDOWN, ())
        self.close()
        if self._process is not None:
            self._process.wait(timeout=5)
        if self._process_logs is not None:
            for stream in self._process_logs:
                stream.close()
            self._process_logs = None

    def close(self) -> None:
        self._pipe.close()

    def __enter__(self) -> "NativeFieldRuntimeClient":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _traceback: Any) -> None:
        if self._process is None:
            self.close()
        else:
            self.shutdown()


__all__ = [
    "NativeFieldRuntimeClient",
    "NativeFieldRuntimeError",
    "NativeGroupRow",
    "NativeWordOperation",
    "PROTOCOL_VERSION",
]
