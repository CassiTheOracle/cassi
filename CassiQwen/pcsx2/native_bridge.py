"""Bounded PCSX2 v2.8.2 Cassi field-bridge v1 transport.

The native process owns two current-user named pipes. This module only frames
and validates the fixed binary ABI; field/session policy lives in ``field.py``.
"""

from __future__ import annotations

import ctypes
import struct
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping


MAGIC = b"CASSIIPC"
VERSION = 1
MAX_PAYLOAD = 8 * 1024 * 1024
MAX_RAM_BYTES = 128 * 1024 * 1024
PAGE_BYTES = 4096
STREAM_PIPE = r"\\.\pipe\CassiPCSX2-v1-stream"
CONTROL_PIPE = r"\\.\pipe\CassiPCSX2-v1-control"
_HEADER = struct.Struct("<8sHHIQ")
_SESSION = struct.Struct("<16s16sQQIIIIIHH")
_BASELINE = struct.Struct("<QQIIHHI")
_DELTA = struct.Struct("<QQII")
_GAP = struct.Struct("<QQII")
_VM_RESET = struct.Struct("<16s16sQQII")
_INPUT = struct.Struct("<QQBBHIII4BI")
_ACTION_RECEIPT = struct.Struct("<16sHHIIHHQQIIB3s")
_CONTROL_HELLO = struct.Struct("<16s16sIQ")

SESSION = 1
BASELINE_CHUNK = 2
DELTA = 3
GAP = 4
VM_RESET = 5
INPUT_EVENT = 6
ACTION_RECEIPT = 7
GAP_SNAPSHOT_QUEUE_FULL = 1
GAP_TOO_MANY_CHANGED_PAGES = 2
GAP_OUTPUT_QUEUE_FULL = 3
GAP_VM_STOPPED = 4
GAP_CAPTURE_UNAVAILABLE = 5
CONTROL_HELLO = 0x100
ENABLE_ACTIONS = 0x101
ACTION = 0x102
CANCEL_ACTION = 0x103

# Session, baseline, delta, gap, reset, input and receipt wire structures are
# deliberately decoded by explicit field order. The compact numeric type table
# is the versioned ABI; no user-controlled type or size reaches a pipe read.


class NativeBridgeError(RuntimeError):
    """The native bridge is absent, malformed, discontinuous, or incompatible."""


class NativeBridgeTimeout(NativeBridgeError):
    """No complete pipe data arrived before the bounded read timeout."""


@dataclass(frozen=True, slots=True)
class NativeMessage:
    type: int
    sequence: int
    payload: Mapping[str, Any]
    raw: bytes
    sequence_gap: bool = False


class _Overlapped(ctypes.Structure):
    _fields_ = (
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", ctypes.c_uint32),
        ("OffsetHigh", ctypes.c_uint32),
        ("hEvent", ctypes.c_void_p),
    )


class _WindowsPipe:
    """Timeout-capable byte-pipe handle using overlapped Win32 I/O."""

    _GENERIC_READ = 0x80000000
    _GENERIC_WRITE = 0x40000000
    _OPEN_EXISTING = 3
    _FILE_FLAG_OVERLAPPED = 0x40000000
    _ERROR_IO_PENDING = 997
    _WAIT_OBJECT_0 = 0
    _WAIT_TIMEOUT = 258
    _INFINITE = 0xFFFFFFFF

    def __init__(self, path: str, handle: int, kernel32: Any) -> None:
        self.path = path
        self._handle = handle
        self._kernel32 = kernel32
        self._closed = False

    @classmethod
    def connect(cls, path: str, timeout: float) -> "_WindowsPipe":
        if sys.platform != "win32":
            raise NativeBridgeError("PCSX2 native bridge pipes are available only on Windows")
        if not 0 < timeout <= 60:
            raise ValueError("pipe connection timeout must be within 0..60 seconds")
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        except (AttributeError, OSError) as exc:
            raise NativeBridgeError("Windows named-pipe APIs are unavailable") from exc
        access = cls._GENERIC_READ if path == STREAM_PIPE else cls._GENERIC_WRITE
        kernel32.CreateEventW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p)
        kernel32.CreateEventW.restype = ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel32.CloseHandle.restype = ctypes.c_int
        kernel32.CancelIoEx.argtypes = (ctypes.c_void_p, ctypes.POINTER(_Overlapped))
        kernel32.CancelIoEx.restype = ctypes.c_int
        kernel32.GetOverlappedResult.argtypes = (
            ctypes.c_void_p, ctypes.POINTER(_Overlapped),
            ctypes.POINTER(ctypes.c_uint32), ctypes.c_int,
        )
        kernel32.GetOverlappedResult.restype = ctypes.c_int
        kernel32.ReadFile.argtypes = (
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(_Overlapped),
        )
        kernel32.ReadFile.restype = ctypes.c_int
        kernel32.WriteFile.argtypes = (
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(_Overlapped),
        )
        kernel32.WriteFile.restype = ctypes.c_int
        kernel32.CreateFileW.argtypes = (
            ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        )
        kernel32.CreateFileW.restype = ctypes.c_void_p
        kernel32.WaitNamedPipeW.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32)
        kernel32.WaitNamedPipeW.restype = ctypes.c_int
        kernel32.GetNamedPipeServerProcessId.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))
        kernel32.GetNamedPipeServerProcessId.restype = ctypes.c_int
        deadline = time.monotonic() + timeout
        invalid = ctypes.c_void_p(-1).value
        while True:
            handle = kernel32.CreateFileW(
                path,
                access,
                0,
                None,
                cls._OPEN_EXISTING,
                cls._FILE_FLAG_OVERLAPPED,
                None,
            )
            if handle not in (None, invalid):
                return cls(path, int(handle), kernel32)
            error = ctypes.get_last_error()
            if time.monotonic() >= deadline:
                raise NativeBridgeTimeout(f"timed out connecting to {path} (Win32 {error})")
            # WaitNamedPipe also handles ERROR_PIPE_BUSY. For ERROR_FILE_NOT_FOUND,
            # its short timeout is a bounded discovery poll while PCSX2 starts.
            kernel32.WaitNamedPipeW(path, 100)

    def _transfer(self, *, write: bool, buffer: Any, size: int, timeout: float) -> int:
        if self._closed:
            raise NativeBridgeError("native bridge pipe is closed")
        if not 0 < timeout <= 60:
            raise ValueError("pipe I/O timeout must be within 0..60 seconds")
        event = self._kernel32.CreateEventW(None, True, False, None)
        if not event:
            raise NativeBridgeError("could not allocate a Windows pipe event")
        overlapped = _Overlapped()
        overlapped.hEvent = event
        transferred = ctypes.c_uint32()
        api = self._kernel32.WriteFile if write else self._kernel32.ReadFile
        api.argtypes = (
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(_Overlapped),
        )
        api.restype = ctypes.c_int
        try:
            completed = bool(api(self._handle, buffer, size, ctypes.byref(transferred), ctypes.byref(overlapped)))
            if not completed:
                error = ctypes.get_last_error()
                if error != self._ERROR_IO_PENDING:
                    raise NativeBridgeError(f"PCSX2 named-pipe I/O failed (Win32 {error})")
                wait = self._kernel32.WaitForSingleObject(event, max(1, int(timeout * 1000)))
                if wait == self._WAIT_TIMEOUT:
                    self._kernel32.CancelIoEx(self._handle, ctypes.byref(overlapped))
                    self._kernel32.WaitForSingleObject(event, self._INFINITE)
                    raise NativeBridgeTimeout(f"timed out reading from {self.path}" if not write else f"timed out writing to {self.path}")
                if wait != self._WAIT_OBJECT_0:
                    raise NativeBridgeError("PCSX2 named-pipe wait failed")
                if not self._kernel32.GetOverlappedResult(
                    self._handle, ctypes.byref(overlapped), ctypes.byref(transferred), False,
                ):
                    error = ctypes.get_last_error()
                    raise NativeBridgeError(f"PCSX2 named-pipe transfer failed (Win32 {error})")
            count = int(transferred.value)
            if count <= 0:
                raise NativeBridgeError("PCSX2 named-pipe peer closed the connection")
            return count
        finally:
            self._kernel32.CloseHandle(event)
    def server_pid(self) -> int:
        pid = ctypes.c_uint32()
        if not self._kernel32.GetNamedPipeServerProcessId(self._handle, ctypes.byref(pid)) or pid.value == 0:
            error = ctypes.get_last_error()
            raise NativeBridgeError(f"could not verify named-pipe server PID (Win32 {error})")
        return int(pid.value)

    def read_exact(self, size: int, timeout: float) -> bytes:
        if not 1 <= size <= MAX_PAYLOAD + _HEADER.size:
            raise NativeBridgeError("invalid bounded native bridge read size")
        output = bytearray(size)
        view = memoryview(output)
        offset = 0
        while offset < size:
            target = (ctypes.c_ubyte * (size - offset)).from_buffer(output, offset)
            count = self._transfer(write=False, buffer=target, size=size - offset, timeout=timeout)
            offset += count
        return bytes(view)

    def write_all(self, data: bytes, timeout: float) -> None:
        if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_PAYLOAD + _HEADER.size:
            raise NativeBridgeError("invalid bounded native bridge write")
        offset = 0
        while offset < len(data):
            chunk = data[offset:offset + 1024 * 1024]
            source = ctypes.create_string_buffer(chunk)
            count = self._transfer(write=True, buffer=source, size=len(chunk), timeout=timeout)
            offset += count

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._kernel32.CancelIoEx(self._handle, None)
            self._kernel32.CloseHandle(self._handle)


class NativeBridgeClient:
    """Read validated producer messages and send bounded, typed control frames.

    Optional pipe objects provide ``read_exact(size, timeout)``, ``write_all``
    and ``close`` for deterministic integration tests. Production uses the
    native current-user named pipes and never PINE/PINE writes.
    """

    def __init__(
        self,
        *,
        stream_pipe: Any | None = None,
        control_pipe: Any | None = None,
        pipe_connector: Callable[[str, float], Any] | None = None,
        expected_server_pid: int | None = None,
        connect_timeout: float = 10.0,
        io_timeout: float = 10.0,
    ) -> None:
        if expected_server_pid is not None and (
            type(expected_server_pid) is not int
            or not 1 <= expected_server_pid <= 0xFFFF_FFFF
        ):
            raise ValueError("expected_server_pid must be a nonzero Windows process ID")
        self._stream = stream_pipe
        self._control = control_pipe
        self._pipe_connector = pipe_connector or _WindowsPipe.connect
        self._expected_server_pid = expected_server_pid
        self._connect_timeout = connect_timeout
        self._io_timeout = io_timeout
        self._stream_sequence = 0
        self._control_sequence = 0
        self._stream_server_pid: int | None = None
        self._last_session: Mapping[str, Any] | None = None

    @property
    def stream_server_pid(self) -> int | None:
        return self._stream_server_pid

    @property
    def session(self) -> Mapping[str, Any] | None:
        return self._last_session

    def connect_stream(self) -> None:
        if self._expected_server_pid is None:
            raise NativeBridgeError("bind the foreground PCSX2 PID before connecting")
        if self._stream is None:
            self._stream = self._pipe_connector(STREAM_PIPE, self._connect_timeout)
        server_pid = getattr(self._stream, "server_pid", None)
        self._stream_server_pid = int(server_pid()) if callable(server_pid) else None
        if self._stream_server_pid is None or self._stream_server_pid != self._expected_server_pid:
            self.close_stream()
            raise NativeBridgeError("stream pipe is not owned by the bound foreground PCSX2 PID")
        self._stream_sequence = 0

    def connect_control(self, session: Mapping[str, Any]) -> None:
        self.close_control()
        if self._expected_server_pid is None or session["producer_pid"] != self._expected_server_pid:
            raise NativeBridgeError("SESSION producer PID is not the bound foreground PCSX2 PID")
        self._control = self._pipe_connector(CONTROL_PIPE, self._connect_timeout)
        server_pid = getattr(self._control, "server_pid", None)
        if not callable(server_pid) or int(server_pid()) != self._expected_server_pid:
            self.close_control()
            raise NativeBridgeError("control pipe is not owned by the bound foreground PCSX2 PID")
        if self._stream_server_pid != self._expected_server_pid:
            self.close_control()
            raise NativeBridgeError("stream pipe is not owned by the bound foreground PCSX2 PID")
        self._control_sequence = 0
        hello = _CONTROL_HELLO.pack(
            session["session_id"], session["stream_id"],
            session["producer_pid"], session["vm_generation"],
        )
        self.send_control(CONTROL_HELLO, hello)

    def receive(self, *, timeout: float | None = None) -> NativeMessage:
        if self._stream is None or self._stream_server_pid is None:
            self.connect_stream()
        wait = self._io_timeout if timeout is None else timeout
        try:
            header = self._stream.read_exact(_HEADER.size, wait)
            magic, version, message_type, payload_bytes, sequence = _HEADER.unpack(header)
            if magic != MAGIC or version != VERSION:
                raise NativeBridgeError("native bridge framing magic or version is invalid")
            if payload_bytes > MAX_PAYLOAD:
                raise NativeBridgeError("native bridge message exceeds the 8 MiB frame bound")
            if sequence == 0 or sequence <= self._stream_sequence:
                raise NativeBridgeError("native producer sequence is not strictly increasing")
            sequence_gap = self._stream_sequence != 0 and sequence != self._stream_sequence + 1
            payload_raw = self._stream.read_exact(payload_bytes, wait) if payload_bytes else b""
            payload = _decode_payload(message_type, payload_raw)
            if message_type == SESSION:
                if (
                    self._expected_server_pid is None
                    or self._stream_server_pid != self._expected_server_pid
                    or payload["producer_pid"] != self._expected_server_pid
                ):
                    raise NativeBridgeError("SESSION PID does not match the bound foreground PCSX2 process")
                self._last_session = payload
            elif message_type == VM_RESET:
                if self._last_session is not None and payload["old_stream_id"] != self._last_session["stream_id"]:
                    raise NativeBridgeError("VM_RESET does not name the current stream")
            self._stream_sequence = sequence
            return NativeMessage(message_type, sequence, payload, header + payload_raw, sequence_gap)
        except NativeBridgeError:
            # A failed transfer or decode leaves the byte-stream cursor untrusted.
            # Reconnect to a new server pipe instead of resuming a partial frame.
            self.close_stream()
            raise

    def encode_control(self, message_type: int, payload: bytes) -> bytes:
        if message_type not in (CONTROL_HELLO, ENABLE_ACTIONS, ACTION, CANCEL_ACTION):
            raise NativeBridgeError("unsupported consumer control type")
        if not isinstance(payload, bytes) or len(payload) > MAX_PAYLOAD:
            raise NativeBridgeError("native control payload exceeds its bound")
        sequence = self._control_sequence + 1
        return _HEADER.pack(MAGIC, VERSION, message_type, len(payload), sequence) + payload

    def send_control(self, message_type: int, payload: bytes, *, before_send: Callable[[bytes], None] | None = None) -> bytes:
        if self._control is None:
            raise NativeBridgeError("native control pipe is not connected")
        raw = self.encode_control(message_type, payload)
        if before_send is not None:
            before_send(raw)
        self._control.write_all(raw, self._io_timeout)
        self._control_sequence += 1
        return raw

    def send_enable_actions(
        self, session_id: bytes, stream_id: bytes, request_id: bytes, *,
        expected_serial: str, expected_current_crc: int,
        before_send: Callable[[bytes], None] | None = None,
    ) -> bytes:
        """Enable actions only for the expected SESSION serial and current_crc."""
        _validate_uuid_bytes(session_id, "session_id")
        _validate_uuid_bytes(stream_id, "stream_id")
        _validate_uuid_bytes(request_id, "request_id")
        if not isinstance(expected_serial, str) or not expected_serial:
            raise NativeBridgeError("expected game serial must be non-empty UTF-8 text")
        try:
            serial_bytes = expected_serial.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise NativeBridgeError("expected game serial is not valid UTF-8") from exc
        if len(serial_bytes) > 256 or b"\x00" in serial_bytes:
            raise NativeBridgeError("expected game serial must be 1..256 non-NUL UTF-8 bytes")
        if (
            type(expected_current_crc) is not int
            or not 0 <= expected_current_crc <= 0xFFFF_FFFF
        ):
            raise NativeBridgeError("expected current CRC must be a 32-bit unsigned integer")
        # The CRC at payload offset 48 matches SESSION.current_crc, not disc_crc.
        payload = (
            session_id + stream_id + request_id
            + struct.pack("<IHH", expected_current_crc, len(serial_bytes), 0)
            + serial_bytes
        )
        return self.send_control(ENABLE_ACTIONS, payload, before_send=before_send)

    def send_action(self, session_id: bytes, stream_id: bytes, request_id: bytes, mask: int, duration_frames: int, *, before_send: Callable[[bytes], None] | None = None) -> bytes:
        _validate_uuid_bytes(session_id, "session_id")
        _validate_uuid_bytes(stream_id, "stream_id")
        _validate_uuid_bytes(request_id, "request_id")
        if type(mask) is not int or not 1 <= mask <= 0xFFFF:
            raise NativeBridgeError("virtual pad action must carry a nonzero 16-bit PS2 button mask")
        if type(duration_frames) is not int or not 1 <= duration_frames <= 120:
            raise NativeBridgeError("virtual pad duration must be within 1..120 frames")
        payload = session_id + stream_id + request_id + struct.pack("<IHH", mask, duration_frames, 0)
        return self.send_control(ACTION, payload, before_send=before_send)

    def send_cancel(self, session_id: bytes, stream_id: bytes, request_id: bytes, *, before_send: Callable[[bytes], None] | None = None) -> bytes:
        _validate_uuid_bytes(session_id, "session_id")
        _validate_uuid_bytes(stream_id, "stream_id")
        _validate_uuid_bytes(request_id, "request_id")
        return self.send_control(CANCEL_ACTION, session_id + stream_id + request_id, before_send=before_send)

    def close_control(self) -> None:
        if self._control is not None:
            try:
                self._control.close()
            finally:
                self._control = None
        self._control_sequence = 0

    def close_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.close()
            finally:
                self._stream = None
        self._stream_sequence = 0
        self._stream_server_pid = None
        self._last_session = None

    def close(self) -> None:
        self.close_control()
        self.close_stream()

    def __enter__(self) -> "NativeBridgeClient":
        self.connect_stream()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def _validate_uuid_bytes(value: bytes, name: str) -> None:
    if not isinstance(value, bytes) or len(value) != 16 or value == bytes(16):
        raise NativeBridgeError(f"{name} must be a nonzero 16-byte identity")


def _decode_payload(message_type: int, raw: bytes) -> Mapping[str, Any]:
    if message_type == SESSION:
        if len(raw) < 72:
            raise NativeBridgeError("SESSION payload is shorter than its 72-byte fixed header")
        (session_id, stream_id, generation, frame, pid, ram_size, page_size,
         disc_crc, current_crc, serial_length, title_length) = _SESSION.unpack_from(raw)
        if len(raw) != 72 + serial_length + title_length:
            raise NativeBridgeError("SESSION string lengths do not match its payload")
        _validate_uuid_bytes(session_id, "session_id")
        _validate_uuid_bytes(stream_id, "stream_id")
        if generation == 0 or pid == 0 or not 1 <= ram_size <= MAX_RAM_BYTES:
            raise NativeBridgeError("SESSION identity or RAM size is outside its bounds")
        if page_size != PAGE_BYTES or ram_size % page_size:
            raise NativeBridgeError("SESSION EE RAM page geometry is unsupported")
        if not 1 <= serial_length <= 256 or title_length > 1024:
            raise NativeBridgeError("SESSION game identity text exceeds its bounds")
        try:
            serial = raw[72:72 + serial_length].decode("utf-8", errors="strict")
            title = raw[72 + serial_length:].decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise NativeBridgeError("SESSION game identity is not valid UTF-8") from exc
        if not serial or any(ord(character) < 32 for character in serial + title):
            raise NativeBridgeError("SESSION game identity contains invalid text")
        return {
            "session_id": session_id, "stream_id": stream_id,
            "vm_generation": generation, "frame_no": frame, "producer_pid": pid,
            "ram_size": ram_size, "page_size": page_size,
            "disc_crc": disc_crc, "current_crc": current_crc,
            "serial": serial, "title": title,
        }
    if message_type == BASELINE_CHUNK:
        if len(raw) < _BASELINE.size:
            raise NativeBridgeError("BASELINE_CHUNK payload is shorter than its fixed header")
        snapshot, frame, total, offset, index, count, data_length = _BASELINE.unpack_from(raw)
        if len(raw) != _BASELINE.size + data_length or not data_length:
            raise NativeBridgeError("BASELINE_CHUNK data length does not match its payload")
        if (
            count == 0 or index >= count or count > MAX_RAM_BYTES // (1024 * 1024)
            or total > MAX_RAM_BYTES or offset > total or data_length > total - offset
        ):
            raise NativeBridgeError("BASELINE_CHUNK offset, count, or total is invalid")
        if data_length > 1024 * 1024:
            raise NativeBridgeError("BASELINE_CHUNK exceeds the 1 MiB chunk bound")
        return {
            "snapshot_id": snapshot, "frame_no": frame, "total_ram_size": total,
            "offset": offset, "chunk_index": index, "chunk_count": count,
            "data": memoryview(raw)[_BASELINE.size:],
        }
    if message_type == DELTA:
        if len(raw) < _DELTA.size:
            raise NativeBridgeError("DELTA payload is shorter than its fixed header")
        snapshot, frame, page_count, record_size = _DELTA.unpack_from(raw)
        if page_count > 1024 or record_size != 4100:
            raise NativeBridgeError("DELTA page count or record size is outside its contract")
        if len(raw) != _DELTA.size + page_count * record_size:
            raise NativeBridgeError("DELTA records do not match page_count")
        records = []
        offset = _DELTA.size
        for _ in range(page_count):
            page_index = struct.unpack_from("<I", raw, offset)[0]
            records.append((page_index, memoryview(raw)[offset + 4:offset + record_size]))
            offset += record_size
        if len({page for page, _ in records}) != len(records):
            raise NativeBridgeError("DELTA contains a duplicate page index")
        return {"snapshot_id": snapshot, "frame_no": frame, "pages": tuple(records)}
    if message_type == GAP:
        if len(raw) != _GAP.size:
            raise NativeBridgeError("GAP payload must be exactly 24 bytes")
        first, last, reason, reserved = _GAP.unpack(raw)
        if first > last or reserved:
            raise NativeBridgeError("GAP frame range or reserved field is invalid")
        return {"first_frame": first, "last_frame": last, "reason": reason}
    if message_type == VM_RESET:
        if len(raw) != _VM_RESET.size:
            raise NativeBridgeError("VM_RESET payload must be exactly 56 bytes")
        old_stream, new_stream, generation, frame, reason, reserved = _VM_RESET.unpack(raw)
        _validate_uuid_bytes(old_stream, "old_stream_id")
        _validate_uuid_bytes(new_stream, "new_stream_id")
        if old_stream == new_stream or generation == 0 or reserved:
            raise NativeBridgeError("VM_RESET stream generation or reserved field is invalid")
        return {
            "old_stream_id": old_stream, "new_stream_id": new_stream,
            "vm_generation": generation, "frame_no": frame, "reason": reason,
        }
    if message_type == INPUT_EVENT:
        if len(raw) != 40:
            raise NativeBridgeError("INPUT_EVENT payload must be exactly 40 bytes")
        (frame, sample, slot, source_bits, reserved, active_low,
         physical_active_low, virtual_active, lx, ly, rx, ry, reserved2) = _INPUT.unpack(raw)
        if reserved or reserved2 or source_bits & ~0x03:
            raise NativeBridgeError("INPUT_EVENT source or reserved fields are invalid")
        if active_low & ~0xFFFF or physical_active_low & ~0xFFFF or virtual_active & ~0xFFFF:
            raise NativeBridgeError("INPUT_EVENT contains unsupported PS2 pad bits")
        return {
            "frame_no": frame, "sample_no": sample, "slot": slot,
            "source_bits": source_bits, "active_low_buttons": active_low,
            "physical_active_low_buttons": physical_active_low,
            "virtual_active_high_mask": virtual_active,
            "lx": lx, "ly": ly, "rx": rx, "ry": ry,
        }
    if message_type == ACTION_RECEIPT:
        if len(raw) != 60:
            raise NativeBridgeError("ACTION_RECEIPT payload must be exactly 60 bytes")
        (request_id, result, reason, requested_mask, applied_mask,
         requested_frames, consumed_frames, first_frame, last_frame,
         first_active_low, last_active_low, source_bits, reserved) = _ACTION_RECEIPT.unpack(raw)
        _validate_uuid_bytes(request_id, "request_id")
        if (
            reserved != bytes(3) or applied_mask & ~0xFFFF
            or result not in (0, 1, 2, 3, 4) or reason not in range(17)
            or consumed_frames > requested_frames or source_bits & ~0x03
        ):
            raise NativeBridgeError("ACTION_RECEIPT status, mask, source, or reserved fields are invalid")
        # These native enums keep explicit cancellation (None=0) distinct from a
        # rejected unknown request (UnknownRequest=9).
        if result == 3:
            if (
                reason != 0 or requested_mask or applied_mask or requested_frames
                or consumed_frames or first_frame or last_frame or source_bits
            ):
                raise NativeBridgeError("ENABLE_ACTIONS success receipt contains invalid fields")
        elif result == 2:
            if (
                reason not in (1, 2, 3, 5, 6, 7, 8, 9, 11, 12, 13)
                or applied_mask or consumed_frames or first_frame or last_frame
                or source_bits
            ):
                raise NativeBridgeError("rejected ACTION_RECEIPT contains invalid status fields")
        elif result == 0:
            if (
                reason != 0 or not 1 <= requested_frames <= 120
                or consumed_frames != requested_frames or not 1 <= requested_mask <= 0xFFFF
                or applied_mask != requested_mask or first_frame > last_frame
                or source_bits != 0x02
            ):
                raise NativeBridgeError("completed ACTION_RECEIPT does not match its request")
        elif result == 1:
            if (
                reason not in (0, 2, 3, 4, 10, 11, 16)
                or not 1 <= requested_frames <= 120
                or not 1 <= requested_mask <= 0xFFFF
                or applied_mask & ~requested_mask
                or first_frame > last_frame
                or (reason == 4 and not (source_bits & 0x01))
                or (reason != 4 and source_bits & 0x01)
                or (
                    not consumed_frames and (first_frame or last_frame)
                    and reason not in (3, 4)
                )
            ):
                raise NativeBridgeError("cancelled ACTION_RECEIPT does not match its cancellation reason")
        elif result == 4:
            if (
                reason not in (14, 15) or not 1 <= requested_frames <= 120
                or not 1 <= requested_mask <= 0xFFFF
                or applied_mask & ~requested_mask
                or (
                    reason == 14 and (
                        consumed_frames or applied_mask or source_bits
                        or first_frame or last_frame
                    )
                )
                or (
                    reason == 15 and (
                        not 1 <= consumed_frames < requested_frames
                        or applied_mask != requested_mask
                        or source_bits != 0x02
                        or first_frame > last_frame
                    )
                )
            ):
                raise NativeBridgeError("expired ACTION_RECEIPT does not match its expiry reason")
        return {
            "request_id": request_id, "result": result, "reason": reason,
            "requested_mask": requested_mask, "applied_mask": applied_mask,
            "requested_frames": requested_frames, "consumed_frames": consumed_frames,
            "first_frame": first_frame, "last_frame": last_frame,
            "first_active_low_buttons": first_active_low,
            "last_active_low_buttons": last_active_low, "source_bits": source_bits,
        }
    raise NativeBridgeError(f"unknown native bridge message type {message_type}")


__all__ = [
    "ACTION", "ACTION_RECEIPT", "BASELINE_CHUNK", "CANCEL_ACTION",
    "CONTROL_HELLO", "DELTA", "ENABLE_ACTIONS", "GAP", "INPUT_EVENT",
    "MAX_PAYLOAD", "MAX_RAM_BYTES", "NativeBridgeClient", "NativeBridgeError",
    "NativeBridgeTimeout", "NativeMessage", "PAGE_BYTES", "SESSION", "VM_RESET",
]
