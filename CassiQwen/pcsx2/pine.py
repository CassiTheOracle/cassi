"""PCSX2 PINE protocol client: strict framing over TCP on Windows.

Framing matches upstream PCSX2 PINE.cpp:
- requests are uint32 little-endian total length (including the four length
  bytes) followed by a payload of [opcode][arguments] commands;
- replies are uint32 little-endian total size, one status byte (0x00 ok,
  0xFF failed), then the sequential results of every command;
- string results are a uint32 length followed by that many bytes, the last
  one being the NUL terminator;
- maximum request size is 650000 bytes, maximum reply size 450000 bytes.
"""

from __future__ import annotations

import socket
import struct
from typing import Any

PINE_DEFAULT_SLOT = 28011
MAX_REQUEST = 650_000
MAX_REPLY = 450_000
IPC_OK = 0x00
IPC_FAIL = 0xFF

MSG_READ8 = 0x00
MSG_READ16 = 0x01
MSG_READ32 = 0x02
MSG_READ64 = 0x03
MSG_WRITE8 = 0x04
MSG_WRITE16 = 0x05
MSG_WRITE32 = 0x06
MSG_WRITE64 = 0x07
MSG_VERSION = 0x08
MSG_SAVE_STATE = 0x09
MSG_LOAD_STATE = 0x0A
MSG_TITLE = 0x0B
MSG_ID = 0x0C
MSG_UUID = 0x0D
MSG_GAME_VERSION = 0x0E
MSG_STATUS = 0x0F

STATUS_RUNNING = 0
STATUS_PAUSED = 1
STATUS_SHUTDOWN = 2
STATUS_NAMES = {STATUS_RUNNING: "running", STATUS_PAUSED: "paused",
                STATUS_SHUTDOWN: "shutdown"}

_ADDRESS_SPACE = 1 << 32
READ_RESULT_BYTES = {MSG_READ8: 1, MSG_READ16: 2, MSG_READ32: 4, MSG_READ64: 8}
MAX_READ_BYTES = 1 << 20


class PineError(RuntimeError):
    """A PINE operation failed: framing, bounds, denial, or emulator reply."""


class PineClient:
    """A read-only-by-default PINE connection to exactly one emulator slot."""

    def __init__(self, host: str = "127.0.0.1", slot: int = PINE_DEFAULT_SLOT,
                 timeout: float = 2.0, allow_effects: bool = False) -> None:
        self.host = host
        self.slot = int(slot)
        self.timeout = float(timeout)
        self.allow_effects = bool(allow_effects)
        self._socket: socket.socket | None = None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "PineClient":
        self._connect()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def _connect(self) -> None:
        if self._socket is not None:
            return
        try:
            socket_ = socket.create_connection((self.host, self.slot), timeout=self.timeout)
            socket_.settimeout(self.timeout)
        except OSError as exc:
            raise PineError(f"cannot connect to PINE slot {self.slot} on {self.host}") from exc
        self._socket = socket_

    # -- framing -----------------------------------------------------------
    def _send_frame(self, payload: bytes) -> None:
        self._connect()
        total = len(payload) + 4
        if total > MAX_REQUEST:
            raise PineError(
                f"batched request of {total} bytes exceeds the PINE limit of {MAX_REQUEST}")
        try:
            assert self._socket is not None
            self._socket.sendall(struct.pack("<I", total) + payload)
        except OSError as exc:
            raise PineError("PINE request could not be sent") from exc

    def _recv_exact(self, count: int) -> bytes:
        assert self._socket is not None
        chunks = bytearray()
        while len(chunks) < count:
            try:
                block = self._socket.recv(count - len(chunks))
            except (OSError, TimeoutError) as exc:
                raise PineError("PINE reply was interrupted") from exc
            if not block:
                raise PineError("PINE reply was truncated by the connection")
            chunks += block
        return bytes(chunks)

    def _exchange(self, ops: list[tuple[int, bytes, int | None]]) -> list[bytes]:
        """Send a batch of [opcode, argument, expected_result] and split the reply.

        An expected result of `None` denotes a length-prefixed string result.
        """
        payload = b"".join(bytes([opcode]) + argument for opcode, argument, _ in ops)
        self._send_frame(payload)
        header = self._recv_exact(4)
        total = int.from_bytes(header, "little")
        if total < 5 or total > MAX_REPLY:
            raise PineError(f"PINE reply length {total} is outside the protocol limits")
        body = self._recv_exact(total - 4)
        if body[0] != IPC_OK:
            raise PineError("PINE emulator answered with a failure status")
        results: list[bytes] = []
        cursor = 1
        for _opcode, _argument, expected in ops:
            if expected is None:
                if cursor + 4 > len(body):
                    raise PineError("PINE string result is truncated")
                length = int.from_bytes(body[cursor:cursor + 4], "little")
                cursor += 4
                if length <= 0 or cursor + length > len(body):
                    raise PineError("PINE string result carries an invalid length")
                raw = body[cursor:cursor + length]
                if len(raw) != length or raw[-1:] != b"\x00":
                    raise PineError("PINE string result is not NUL-terminated")
                cursor += length
                results.append(raw)
            else:
                if cursor + expected > len(body):
                    raise PineError("PINE reply is shorter than the batch requires")
                results.append(body[cursor:cursor + expected])
                cursor += expected
        if cursor != len(body):
            raise PineError("PINE reply carries unexpected trailing results")
        return results

    @staticmethod
    def _address_bytes(address: int) -> bytes:
        if isinstance(address, bool) or not isinstance(address, int):
            raise PineError("PINE address must be an integer")
        if not 0 <= address < _ADDRESS_SPACE:
            raise PineError(f"PINE address 0x{address:08x} is outside the 32-bit space")
        return struct.pack("<I", address)

    # -- reads -------------------------------------------------------------
    def read(self, address: int, size: int) -> bytes:
        """Bounded chunked read; big reads become batches of 8/4/2/1-byte ops."""
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise PineError("PINE read size must be a non-negative integer")
        if size == 0:
            return b""
        self._address_bytes(address)
        if size > MAX_READ_BYTES:
            raise PineError(
                f"PINE read of {size} bytes exceeds the bounded read limit of {MAX_READ_BYTES}")
        if address + size > _ADDRESS_SPACE:
            raise PineError("PINE read crosses the end of the 32-bit address space")
        collected = bytearray()
        offset = address
        remaining = size
        while remaining > 0:
            chunk = self._exchange_chunk(offset, remaining)
            if not chunk:
                raise PineError("PINE read made no progress")
            collected += chunk
            remaining -= len(chunk)
            offset += len(chunk)
        return bytes(collected)

    @staticmethod
    def _read_ops(address: int, size: int, *, ops_per_batch: int) -> list[tuple[int, bytes, int | None]]:
        ops: list[tuple[int, bytes, int | None]] = []
        offset = address
        remaining = size
        while remaining > 0:
            if len(ops) >= ops_per_batch:
                break
            if remaining >= 8:
                opcode, chunk = MSG_READ64, 8
            elif remaining >= 4:
                opcode, chunk = MSG_READ32, 4
            elif remaining >= 2:
                opcode, chunk = MSG_READ16, 2
            else:
                opcode, chunk = MSG_READ8, 1
            ops.append((opcode, struct.pack("<I", offset), READ_RESULT_BYTES[opcode]))
            offset += chunk
            remaining -= chunk
        return ops

    def _exchange_chunk(self, address: int, size: int) -> bytes:
        results = self._exchange(self._read_ops(address, size, ops_per_batch=self._ops_per_batch()))
        return b"".join(results)

    def _ops_per_batch(self) -> int:
        # request cost per op is 5 bytes, reply cost 8 bytes; stay far below
        # both PINE limits in one frame.
        return min((MAX_REQUEST - 4) // 5, (MAX_REPLY - 5) // 8, 4096)

    def read8(self, address: int) -> int:
        return self._exchange(self._read_ops_single(MSG_READ8, address))[0][0]

    def read16(self, address: int) -> int:
        return int.from_bytes(self._exchange(self._read_ops_single(MSG_READ16, address))[0], "little")

    def read32(self, address: int) -> int:
        return int.from_bytes(self._exchange(self._read_ops_single(MSG_READ32, address))[0], "little")

    def read64(self, address: int) -> int:
        return int.from_bytes(self._exchange(self._read_ops_single(MSG_READ64, address))[0], "little")

    @classmethod
    def _read_ops_single(cls, opcode: int, address: int) -> list[tuple[int, bytes, int | None]]:
        encoded = cls._address_bytes(address)
        width = READ_RESULT_BYTES[opcode]
        if width is None or address + width > _ADDRESS_SPACE:
            raise PineError("PINE read crosses the end of the 32-bit address space")
        return [(opcode, encoded, width)]

    # -- effects (explicit permission required) -----------------------------
    def _require_effects(self, action: str) -> None:
        if not self.allow_effects:
            raise PineError(
                f"PINE {action} is denied: this client is read-only by default")

    def write(self, address: int, data: bytes) -> None:
        self._require_effects("memory write")
        length = len(data)
        if length == 0 or length > 8:
            raise PineError("PINE write must carry 1 to 8 bytes")
        opcode = {1: MSG_WRITE8, 2: MSG_WRITE16, 4: MSG_WRITE32, 8: MSG_WRITE64}.get(length)
        if opcode is None:
            raise PineError("PINE write must carry 1, 2, 4, or 8 bytes")
        self._exchange([(opcode, self._address_bytes(address) + data, 0)])

    def save_state(self, slot: int = 0) -> None:
        self._require_effects("save state")
        self._exchange([(MSG_SAVE_STATE, bytes([int(slot)]), 0)])

    def load_state(self, slot: int = 0) -> None:
        self._require_effects("load state")
        self._exchange([(MSG_LOAD_STATE, bytes([int(slot)]), 0)])

    # -- identity ------------------------------------------------------------
    def version(self) -> str:
        return self._string_op(MSG_VERSION)

    def title(self) -> str:
        return self._string_op(MSG_TITLE)

    def game_id(self) -> str:
        return self._string_op(MSG_ID)

    def game_uuid(self) -> str:
        return self._string_op(MSG_UUID)

    def game_version(self) -> str:
        return self._string_op(MSG_GAME_VERSION)

    def status(self) -> int:
        result = self._exchange([(MSG_STATUS, b"", 4)])[0]
        return int.from_bytes(result, "little")

    def status_name(self) -> str:
        return STATUS_NAMES.get(self.status(), f"unknown:{self.status()}")

    def identity(self) -> dict[str, Any]:
        """JSON-safe emulator/game identity; missing fields are None."""
        def attempt(call: Any) -> str | None:
            try:
                return call()
            except PineError:
                return None

        status_value = self.status()
        return {
            "emulator": "pcsx2",
            "version": attempt(self.version),
            "title": attempt(self.title),
            "game_id": attempt(self.game_id),
            "game_uuid": attempt(self.game_uuid),
            "game_version": attempt(self.game_version),
            "status": status_value,
            "status_name": STATUS_NAMES.get(status_value, f"unknown:{status_value}"),
        }

    def _string_op(self, opcode: int) -> str:
        raw = self._exchange([(opcode, b"", None)])[0]
        try:
            return raw[:-1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PineError("PINE string result is not valid UTF-8") from exc
