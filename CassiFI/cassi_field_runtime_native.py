"""Authenticated Windows client for the native CassiFI field-runtime service."""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import hashlib
import math
from pathlib import Path
import secrets
import struct
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable, Sequence
import uuid

import numpy as np


FRAME_MAGIC = 0x31524643
PROTOCOL_VERSION = 1
FRAME_HEADER = struct.Struct("<IHHII16s32s")
MAX_FRAME_BODY = 1 << 20
MAX_FIELD_BYTES = 64 << 20

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
RESPONSE_BIT = 0x8000
ERROR = 0xFFFF

WIRE_BYTES = 1
WIRE_UTF8 = 2
WIRE_U64 = 3


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
        opcodes = {"set": 1, "copy": 2, "fill": 3, "compare-set": 4}
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
    ) -> None:
        if sys.platform != "win32":
            raise NativeFieldRuntimeError("native field-runtime transport requires Windows")
        self.instance_id = _text(instance_id, "instance_id")
        self.launch_nonce = _text(launch_nonce, "launch_nonce")
        self._process = process
        self._process_logs = process_logs
        self._pipe = self._connect(connect_timeout_s)
        response = self._request(HELLO, (_utf8(1, self.instance_id), _utf8(2, self.launch_nonce)))
        if _field_text(response, 1) != "authenticated":
            self.close()
            raise NativeFieldRuntimeError("native runtime authentication failed")
        self.service_generation = _field_u64(response, 2)
        self._verified_model_sources: dict[str, Path] = {}

    @classmethod
    def launch(
        cls,
        executable: str | Path,
        *,
        instance_id: str | None = None,
        launch_nonce: str | None = None,
        device_index: int = 0,
        connect_timeout_s: float = 10.0,
    ) -> "NativeFieldRuntimeClient":
        instance = instance_id or secrets.token_hex(16)
        nonce = launch_nonce or secrets.token_hex(32)
        stdout_log = tempfile.TemporaryFile()
        stderr_log = tempfile.TemporaryFile()
        process = subprocess.Popen(
            [str(Path(executable)), "--instance", instance, "--nonce", nonce, "--device", str(device_index)],
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
        self._write_all(header + body)
        raw_header = self._read_exact(FRAME_HEADER.size)
        magic, version, response_kind, _flags, size, response_id, digest = FRAME_HEADER.unpack(raw_header)
        if magic != FRAME_MAGIC or version != PROTOCOL_VERSION or size > MAX_FRAME_BODY:
            raise NativeFieldRuntimeError("native runtime response header is invalid")
        response_body = self._read_exact(size)
        if hashlib.sha256(response_body).digest() != digest:
            raise NativeFieldRuntimeError("native runtime response digest mismatch")
        decoded = _decode_body(response_body)
        if response_id != request_id:
            raise NativeFieldRuntimeError("native runtime response identity is invalid")
        if response_kind == ERROR:
            raise NativeFieldRuntimeError(_field_text(decoded, 2))
        if response_kind != (kind | RESPONSE_BIT):
            raise NativeFieldRuntimeError("native runtime response identity is invalid")
        return decoded

    def status(self) -> dict[str, Any]:
        response = self._request(STATUS, ())
        return {
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
        }

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
        if not isinstance(field_image, np.ndarray) or field_image.dtype != np.float64 or not field_image.flags.c_contiguous:
            raise NativeFieldRuntimeError("native attachment requires a C-contiguous float64 field image")
        payload = field_image.tobytes(order="C")
        shape = b"".join(struct.pack("<I", int(extent)) for extent in field_image.shape)
        with _StagingMapping.from_bytes(payload) as mapping:
            response = self._request(
                IMPORT_IMAGE,
                (
                    _utf8(1, owner_id),
                    _u64(2, self.service_generation),
                    _u64(3, fence),
                    _utf8(4, _digest(profile_sha256, "profile_sha256")),
                    _utf8(5, _digest(state_sha256, "state_sha256")),
                    _utf8(6, _digest(catalog_sha256, "catalog_sha256")),
                    _bytes(7, shape),
                    _u64(8, mapping.value),
                    _u64(9, len(payload)),
                    _bytes(10, hashlib.sha256(payload).digest()),
                ),
            )
        return {"status": _field_text(response, 1), "owner_id": _field_text(response, 2), "word_count": _field_u64(response, 3), "packed_sha256": _field_text(response, 4)}

    def begin_candidate(self, owner_id: str, predecessor_state_sha256: str, *, fence: int, lease_id: str, placement: str = "native-cpu") -> str:
        response = self._request(BEGIN_CANDIDATE, (_utf8(1, owner_id), _utf8(2, _digest(predecessor_state_sha256, "predecessor_state_sha256")), _u64(3, fence), _utf8(4, lease_id), _utf8(5, placement)))
        if _field_text(response, 1) != "candidate-open":
            raise NativeFieldRuntimeError("native runtime did not open a candidate")
        return _field_text(response, 2)

    def apply_word_operations(self, candidate_id: str, operations: Iterable[NativeWordOperation]) -> dict[str, Any]:
        encoded = b"".join(operation.encode() for operation in operations)
        response = self._request(APPLY_WORD_OPS, (_utf8(1, candidate_id), _bytes(2, encoded)))
        return {"status": _field_text(response, 1), "logical_operations": _field_u64(response, 2), "canonical_bytes_sha256": _field_text(response, 3)}

    def export_candidate(self, candidate_id: str, shape: Sequence[int]) -> tuple[np.ndarray, dict[str, Any]]:
        response = self._request(EXPORT_CANDIDATE, (_utf8(1, candidate_id),))
        handle = _field_u64(response, 2)
        size = _field_u64(response, 3)
        expected = _field_bytes(response, 4)
        with _StagingMapping(handle) as mapping:
            payload = mapping.read(size)
        if hashlib.sha256(payload).digest() != expected:
            raise NativeFieldRuntimeError("exported candidate digest mismatch")
        expected_size = math.prod(shape) * 8
        if expected_size != size:
            raise NativeFieldRuntimeError("exported candidate size does not match shape")
        array = np.frombuffer(payload, dtype=np.float64).reshape(tuple(int(item) for item in shape)).copy()
        return array, {"status": _field_text(response, 1), "predecessor_state_sha256": _field_text(response, 5), "logical_operations": _field_u64(response, 6), "payload_sha256": expected.hex()}

    def confirm_cache(self, candidate_id: str, predecessor_state_sha256: str, successor_state_sha256: str, *, fence: int, lease_id: str) -> dict[str, Any]:
        response = self._request(CONFIRM_CACHE, (_utf8(1, candidate_id), _utf8(2, _digest(predecessor_state_sha256, "predecessor_state_sha256")), _u64(3, fence), _utf8(4, lease_id), _utf8(5, _digest(successor_state_sha256, "successor_state_sha256"))))
        return {"status": _field_text(response, 1), "owner_id": _field_text(response, 2), "state_sha256": _field_text(response, 3), "fence": _field_u64(response, 4)}

    def discard_candidate(self, candidate_id: str) -> dict[str, str]:
        response = self._request(DISCARD_CANDIDATE, (_utf8(1, candidate_id),))
        return {"status": _field_text(response, 1), "candidate_id": _field_text(response, 2)}
    def detach(self, owner_id: str) -> dict[str, str]:
        response = self._request(DETACH_OWNER, (_utf8(1, owner_id),))
        return {
            "status": _field_text(response, 1),
            "owner_id": _field_text(response, 2),
        }


    def probe_vulkan(self) -> dict[str, str]:
        response = self._request(PROBE_VULKAN, ())
        return {"status": _field_text(response, 1), "device": _field_text(response, 2), "reason": _field_text(response, 3), "operation_groups": _field_text(response, 4)}

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
    ) -> dict[str, Any]:
        if not tokens:
            raise NativeFieldRuntimeError("model token history cannot be empty")
        packed = bytearray()
        for token in tokens:
            if isinstance(token, bool) or not isinstance(token, int) or not 0 <= token <= 0x7FFFFFFF:
                raise NativeFieldRuntimeError("model token is outside int32 range")
            packed.extend(struct.pack("<i", token))
        if sampler_mode not in {"greedy", "categorical"}:
            raise NativeFieldRuntimeError("model sampler mode is unsupported")
        if not math.isfinite(temperature) or temperature <= 0.0:
            raise NativeFieldRuntimeError("model temperature is invalid")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 0 <= top_k <= 0xFFFFFFFF:
            raise NativeFieldRuntimeError("model top_k is outside its bound")
        if not math.isfinite(draw) or not 0.0 <= draw < 1.0:
            raise NativeFieldRuntimeError("model draw is outside its bound")
        response = self._request(
            STEP_MODEL,
            (
                _utf8(1, task_id),
                _utf8(2, _digest(source_sha256, "source_sha256")),
                _bytes(3, bytes(packed)),
                _utf8(4, sampler_mode),
                _bytes(5, struct.pack("<d", temperature)),
                _u64(6, top_k),
                _bytes(7, struct.pack("<d", draw)),
            ),
        )
        return {
            "status": _field_text(response, 1),
            "token": _field_u64(response, 2),
            "end_of_generation": bool(_field_u64(response, 3)),
            "replay_sha256": _field_text(response, 4),
            "token_count": _field_u64(response, 5),
            "stage_trace_sha256": _field_text(response, 6),
            "exact_stages": _field_u64(response, 7),
            "embedding_stages": _field_u64(response, 8),
            "attention_stages": _field_u64(response, 9),
            "ffn_stages": _field_u64(response, 10),
            "head_stages": _field_u64(response, 11),
            "ggml_nodes": _field_u64(response, 12),
            "logical_weight_bytes": _field_u64(response, 13),
        }

    def drop_model_task(self, task_id: str) -> dict[str, str]:
        response = self._request(DROP_MODEL_TASK, (_utf8(1, task_id),))
        return {
            "status": _field_text(response, 1),
            "task_id": _field_text(response, 2),
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
    "NativeWordOperation",
    "PROTOCOL_VERSION",
]
