"""Bounded RFB transport for a dedicated Linux Xvnc surface.

The backend is an actuator-side protocol client, not a viewer.  It accepts only
an owner-only Linux Unix socket or an explicitly configured mutually-authenticated
TLS TCP endpoint.  It never returns transport credentials or clipboard contents.
"""
from __future__ import annotations

import os
import socket
import ssl
import stat
import struct
import threading
import time
import uuid
import unicodedata
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_MAX_DIMENSION = 8192
_MAX_FRAMEBUFFER_BYTES = 64 * 1024 * 1024
_MAX_SERVER_NAME_BYTES = 8192
_MAX_REASON_BYTES = 4096
_MAX_RECTANGLES_PER_UPDATE = 4096
_MAX_CUT_TEXT_BYTES = 1024 * 1024
_PIXEL_FORMAT_BYTES = struct.pack(">BBBBHHHBBB3x", 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)
_RFB_ENCODINGS = (-223, 1, 0)  # DesktopSize, CopyRect, Raw; no compressed codecs.
_SEND_TIMEOUT_S = 3.0
_OPAQUE_ALPHA_ROW = memoryview(b"\xff" * _MAX_DIMENSION)
_MAX_TEXT_CODEPOINTS = 1024
_MAX_TEXT_UTF8_BYTES = 4096
_MAX_INPUT_EVENTS_PER_BATCH = 2048
_WHEEL_DELTA_PER_NOTCH = 120


class RfbError(RuntimeError):
    """The peer or transport violated the configured RFB contract."""


class RfbUnavailable(RfbError):
    """The requested secure transport cannot be provided on this host."""


def _text(value: Any, label: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value:
        raise ValueError(f"{label} must be a non-empty bounded string")
    return value


def _integer(value: Any, label: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < low or value > high:
        raise ValueError(f"{label} must be an integer in [{low}, {high}]")
    return value


def _new_epoch() -> int:
    return (uuid.uuid4().int & ((1 << 53) - 1)) or 1


def _framebuffer_size(width: int, height: int, max_bytes: int) -> int:
    if width < 1 or height < 1 or width > _MAX_DIMENSION or height > _MAX_DIMENSION:
        raise RfbError("RFB framebuffer dimensions are outside configured limits")
    size = width * height * 4
    if size > max_bytes:
        raise RfbError("RFB framebuffer exceeds the configured byte limit")
    return size


def _normalise_source(source: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        raise ValueError("each RFB source must be a mapping")
    source_id = _text(source.get("source_id"), "source_id", limit=256)
    source_instance = _text(source.get("source_instance"), "source_instance", limit=192)
    environment_incarnation = _text(source.get("environment_incarnation"), "environment_incarnation", limit=192)
    transport = source.get("transport")
    if not isinstance(transport, Mapping):
        raise ValueError("transport must be an explicit mapping")
    kind = transport.get("kind")
    if kind == "unix":
        path = _text(transport.get("socket_path"), "transport.socket_path", limit=4096)
        if not path.startswith("/"):
            raise ValueError("Unix socket path must be absolute")
        expected_uid = _integer(transport.get("owner_uid"), "transport.owner_uid", 0, 2**31 - 1)
        secured_transport = {"kind": "unix", "socket_path": path, "owner_uid": expected_uid}
    elif kind == "protected-tcp-tls":
        if transport.get("protected") is not True:
            raise ValueError("TCP transport requires an explicit protected=true declaration")
        host = _text(transport.get("host"), "transport.host", limit=253)
        port = _integer(transport.get("port"), "transport.port", 1, 65535)
        tls = transport.get("tls")
        if not isinstance(tls, Mapping):
            raise ValueError("protected TCP requires a TLS mapping; plaintext fallback is forbidden")
        server_hostname = _text(tls.get("server_hostname"), "transport.tls.server_hostname", limit=253)
        ca_file = _text(tls.get("ca_file"), "transport.tls.ca_file", limit=4096)
        client_cert = _text(tls.get("client_cert"), "transport.tls.client_cert", limit=4096)
        client_key = _text(tls.get("client_key"), "transport.tls.client_key", limit=4096)
        secured_transport = {
            "kind": "protected-tcp-tls",
            "protected": True,
            "host": host,
            "port": port,
            "tls": {
                "server_hostname": server_hostname,
                "ca_file": ca_file,
                "client_cert": client_cert,
                "client_key": client_key,
            },
        }
    else:
        raise ValueError("transport.kind must be 'unix' or 'protected-tcp-tls'")
    return {
        "source_id": source_id,
        "source_instance": source_instance,
        "environment_incarnation": environment_incarnation,
        "transport": secured_transport,
    }


def _recv_exact(sock: socket.socket, size: int, stop: threading.Event | None = None) -> bytes:
    if size < 0:
        raise RfbError("negative RFB field length")
    data = bytearray(size)
    view = memoryview(data)
    offset = 0
    while offset < size:
        if stop is not None and stop.is_set():
            raise RfbError("RFB connection is closing")
        try:
            count = sock.recv_into(view[offset:], size - offset)
        except socket.timeout:
            if stop is None:
                raise
            continue
        if count == 0:
            raise RfbError("RFB peer closed the connection")
        offset += count
    return bytes(data)


def _send(sock: socket.socket, payload: bytes | bytearray) -> None:
    try:
        sock.sendall(payload)
    except OSError as exc:
        raise RfbError(f"RFB write failed: {type(exc).__name__}") from exc


def _set_send_timeout(sock: socket.socket) -> None:
    option = getattr(socket, "SO_SNDTIMEO", None)
    if option is None:
        raise RfbUnavailable("bounded RFB input writes are unavailable on this host")
    if os.name == "nt":
        value = struct.pack("I", int(_SEND_TIMEOUT_S * 1000))
    else:
        value = struct.pack("@ll", int(_SEND_TIMEOUT_S), 0)
    try:
        sock.setsockopt(socket.SOL_SOCKET, option, value)
    except OSError as exc:
        raise RfbUnavailable(f"bounded RFB input writes are unavailable: {type(exc).__name__}") from exc


def _skip_reason(sock: socket.socket) -> str:
    length = struct.unpack(">I", _recv_exact(sock, 4))[0]
    if length > _MAX_REASON_BYTES:
        raise RfbError("RFB failure reason exceeds the configured limit")
    return _recv_exact(sock, length).decode("utf-8", "replace")


def _pixel_format_name() -> str:
    # The negotiated RFB BGRX data is normalized to the broker's opaque BGRA8 format.
    return "BGRA8"


def _key_code(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("keysyms must be an integer or a supported key name")
    if isinstance(value, int):
        return _integer(value, "keysym", 1, 0x0110FFFF)
    name = _text(value, "key", limit=32).lower()
    if len(name) == 1 and 0x20 <= ord(name) <= 0x7E:
        return ord(name)
    fixed = {
        "backspace": 0xFF08,
        "tab": 0xFF09,
        "enter": 0xFF0D,
        "return": 0xFF0D,
        "escape": 0xFF1B,
        "insert": 0xFF63,
        "delete": 0xFFFF,
        "home": 0xFF50,
        "end": 0xFF57,
        "page_up": 0xFF55,
        "page_down": 0xFF56,
        "left": 0xFF51,
        "up": 0xFF52,
        "right": 0xFF53,
        "down": 0xFF54,
        "space": 0x20,
        "shift_l": 0xFFE1,
        "shift_r": 0xFFE2,
        "control_l": 0xFFE3,
        "control_r": 0xFFE4,
        "alt_l": 0xFFE9,
        "alt_r": 0xFFEA,
        "meta_l": 0xFFE7,
        "meta_r": 0xFFE8,
    }
    if name in fixed:
        return fixed[name]
    if name.startswith("f") and name[1:].isdigit():
        number = int(name[1:])
        if 1 <= number <= 12:
            return 0xFFBD + number
    raise ValueError("key name is not in the bounded RFB keysym set")


def _text_keysyms(value: Any) -> list[int]:
    if not isinstance(value, str):
        raise ValueError("text must be a string")
    value = value.replace("\r\n", "\n")
    if not value or len(value) > _MAX_TEXT_CODEPOINTS:
        raise ValueError(f"text must contain 1..{_MAX_TEXT_CODEPOINTS} Unicode code points")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("text contains an unsupported Unicode surrogate") from exc
    if len(encoded) > _MAX_TEXT_UTF8_BYTES:
        raise ValueError(f"text exceeds the {_MAX_TEXT_UTF8_BYTES}-byte UTF-8 limit")

    keysyms: list[int] = []
    for character in value:
        codepoint = ord(character)
        category = unicodedata.category(character)
        if codepoint == 0x09:
            keysyms.append(0xFF09)  # XK_Tab
        elif codepoint in (0x0A, 0x0D):
            keysyms.append(0xFF0D)  # XK_Return
        elif category in ("Cc", "Cs", "Cn"):
            raise ValueError(f"text contains unsupported Unicode code point U+{codepoint:04X}")
        elif codepoint <= 0xFF:
            keysyms.append(codepoint)
        elif codepoint <= 0x10FFFF:
            keysyms.append(0x01000000 | codepoint)
        else:
            raise ValueError(f"text contains unsupported Unicode code point U+{codepoint:04X}")
    return keysyms


@dataclass
class _LiveBinding:
    source: dict[str, Any]
    binding_id: str
    source_epoch: int
    geometry_revision: int
    sock: socket.socket
    width: int
    height: int
    pixel_bytes: int
    max_framebuffer_bytes: int
    reconnect_min_delay_s: float
    reconnect_max_delay_s: float
    stop: threading.Event = field(default_factory=threading.Event)
    state_lock: threading.RLock = field(default_factory=threading.RLock)
    send_lock: threading.Lock = field(default_factory=threading.Lock)
    pixels: bytearray | None = None
    coverage: bytearray | None = None
    covered_pixels: int = 0
    baseline: bool = False
    status: str = "awaiting_full_baseline"
    last_error: str | None = None
    sequence: int = 0
    last_receipt_time_ns: int = 0
    last_rectangle_count: int = 0
    last_coverage_kind: str = "initial-full-request"
    owned_keys: set[int] = field(default_factory=set)
    owned_buttons: int = 0
    pointer_x: int = 0
    pointer_y: int = 0
    recent_inputs: deque[float] = field(default_factory=deque)
    worker: threading.Thread | None = None


class LinuxXvncBackend:
    """Dedicated RFB client for Xvnc; no viewer or clipboard client is spawned.

    Source records have ``source_id``, ``source_instance`` and
    ``environment_incarnation``.  ``transport`` is either:

    * ``{"kind":"unix", "socket_path":..., "owner_uid":...}``; the
      socket and its parent directory must be owned by this uid and owner-only,
      and Linux peer credentials must confirm the connected server uid; or
    * ``{"kind":"protected-tcp-tls", "protected":true, "host":..., "port":...,
      "tls":{"server_hostname":..., "ca_file":..., "client_cert":...,
      "client_key":...}}``.  TLS/mTLS is mandatory and there is no plaintext
      fallback.  RFB security type None is accepted only inside one of these
      independently authenticated transports.
    """

    backend_id = "linux-xvnc-rfb"

    def __init__(
        self,
        sources: Sequence[Mapping[str, Any]],
        *,
        connect_timeout_s: float = 5.0,
        max_framebuffer_bytes: int = _MAX_FRAMEBUFFER_BYTES,
        reconnect_min_delay_s: float = 0.25,
        reconnect_max_delay_s: float = 8.0,
    ) -> None:
        if isinstance(sources, (str, bytes)) or not isinstance(sources, Sequence):
            raise ValueError("sources must be a sequence of source records")
        self._sources: dict[str, dict[str, Any]] = {}
        for source in sources:
            normalized = _normalise_source(source)
            if normalized["source_id"] in self._sources:
                raise ValueError("source_id values must be unique")
            self._sources[normalized["source_id"]] = normalized
        if not 0.25 <= connect_timeout_s <= 30.0:
            raise ValueError("connect_timeout_s must be between 0.25 and 30 seconds")
        if not 1024 * 1024 <= max_framebuffer_bytes <= _MAX_FRAMEBUFFER_BYTES:
            raise ValueError("max_framebuffer_bytes must be between 1 MiB and 64 MiB")
        if not 0.05 <= reconnect_min_delay_s <= reconnect_max_delay_s <= 30.0:
            raise ValueError("reconnect delay bounds are invalid")
        self._connect_timeout_s = float(connect_timeout_s)
        self._max_framebuffer_bytes = int(max_framebuffer_bytes)
        self._reconnect_min_delay_s = float(reconnect_min_delay_s)
        self._reconnect_max_delay_s = float(reconnect_max_delay_s)
        self._bind_lock = threading.Lock()
        self._lock = threading.RLock()
        self._bindings: dict[str, _LiveBinding] = {}
        self._source_bindings: dict[str, str] = {}
        self._closed = False

    def describe(self) -> dict[str, Any]:
        linux_unix = os.name == "posix" and hasattr(socket, "AF_UNIX") and hasattr(socket, "SO_PEERCRED")
        has_supported_source = any(self._transport_supported(source, linux_unix) for source in self._sources.values())
        capabilities = {
            "visual": {
                "status": "supported" if has_supported_source else "unavailable",
                "reason": None if has_supported_source else "requires Linux peer-authenticated Unix sockets or verified TLS TCP",
                "formats": [_pixel_format_name()],
                "max_frame_bytes": self._max_framebuffer_bytes,
                "clock": "source sample time unavailable; host receipt uses monotonic clock",
                "encodings": ["raw", "copyrect", "desktop-size"],
                "full_baseline_required": True,
            },
            "keyboard.key": {
                "status": "supported" if has_supported_source else "unavailable",
                "reason": None if has_supported_source else "no configured source has a supported secure RFB transport",
                "ack_strength": "transport-only",
                "key_identity": "bounded X11 keysym",
                "max_events_per_second": 60,
            },
            "keyboard.text": {
                "status": "supported" if has_supported_source else "unavailable",
                "reason": None if has_supported_source else "no configured source has a supported secure RFB transport",
                "encoding": "X11 Unicode keysyms",
                "max_codepoints": _MAX_TEXT_CODEPOINTS,
                "max_utf8_bytes": _MAX_TEXT_UTF8_BYTES,
                "releases_held_keys_before_typing": True,
                "ack_strength": "transport-only",
                "max_input_events_per_batch": _MAX_INPUT_EVENTS_PER_BATCH,
                "max_events_per_second": 60,
            },
            "pointer.absolute": {
                "status": "supported" if has_supported_source else "unavailable",
                "reason": None if has_supported_source else "no configured source has a supported secure RFB transport",
                "coordinates": "absolute framebuffer pixels",
                "ack_strength": "transport-only",
            },
            "pointer.button": {
                "status": "supported" if has_supported_source else "unavailable",
                "reason": None if has_supported_source else "no configured source has a supported secure RFB transport",
                "buttons": ["left", "middle", "right"],
                "ack_strength": "transport-only",
            },
            "pointer.relative": {"status": "unavailable", "reason": "RFB relative pointer input is not implemented"},
            "pointer.wheel": {
                "status": "supported" if has_supported_source else "unavailable",
                "reason": None if has_supported_source else "no configured source has a supported secure RFB transport",
                "units": "signed 120-unit wheel steps",
                "buttons": {"up": 4, "down": 5, "left": 6, "right": 7},
                "max_notches_per_axis": 10,
                "ack_strength": "transport-only",
                "max_events_per_second": 60,
            },
            "accessibility": {"status": "unavailable", "reason": "RFB does not supply an accessibility tree"},
            "audio": {"status": "unavailable", "reason": "RFB does not transport audio"},
            "clipboard": {"status": "unavailable", "reason": "both RFB clipboard directions are disabled"},
            "touch": {"status": "unavailable", "reason": "RFB transport exposes no touch contacts"},
            "pen": {"status": "unavailable", "reason": "RFB transport exposes no pen state"},
            "controller": {"status": "unavailable", "reason": "RFB transport exposes no controller state"},
        }
        status = "available" if has_supported_source else "unavailable"
        reason = None if status == "available" else "no configured source has a supported secure RFB transport on this host"
        return {
            "backend_id": self.backend_id,
            "status": status,
            "reason": reason,
            "sources": self.sources(),
            "capabilities": capabilities,
            "limits": {
                "max_sources": len(self._sources),
                "max_input_events_per_batch": _MAX_INPUT_EVENTS_PER_BATCH,
                "max_rectangles_per_update": _MAX_RECTANGLES_PER_UPDATE,
                "clipboard": "disabled by default and unsupported by this backend",
                "reconnect": "forces new source epoch, geometry generation and full baseline before input",
            },
        }

    @staticmethod
    def _transport_supported(source: Mapping[str, Any], linux_unix: bool) -> bool:
        kind = source["transport"]["kind"]
        return kind == "protected-tcp-tls" or (kind == "unix" and linux_unix)

    def sources(self) -> list[dict[str, Any]]:
        with self._lock:
            active = {source_id: self._bindings.get(binding_id) for source_id, binding_id in self._source_bindings.items()}
        linux_unix = os.name == "posix" and hasattr(socket, "AF_UNIX") and hasattr(socket, "SO_PEERCRED")
        result = []
        for source in self._sources.values():
            supported = self._transport_supported(source, linux_unix)
            live = active.get(source["source_id"])
            modalities: list[str] = []
            if live is not None and not self._closed:
                with live.state_lock:
                    if live.status == "live" and live.baseline and not live.stop.is_set():
                        modalities = ["pixels"]
            result.append({
                "source_id": source["source_id"],
                "source_instance": source["source_instance"],
                "environment_incarnation": source["environment_incarnation"],
                "backend_id": self.backend_id,
                "transport": source["transport"]["kind"],
                "status": "bound" if source["source_id"] in active else "available" if supported else "unavailable",
                "modalities": modalities,
                "reason": None if supported else "secure transport is unsupported on this host",
                "operations": ["visual", "keyboard.key", "keyboard.text", "pointer.absolute", "pointer.button", "pointer.wheel"] if supported else [],
            })
        return result


    def bind(self, source_id: str) -> dict[str, Any]:
        if self._closed:
            raise RfbUnavailable("RFB backend is closed")
        source_id = _text(source_id, "source_id", limit=256)
        source = self._sources.get(source_id)
        if source is None:
            raise RfbUnavailable("source_id is not configured for this RFB backend")
        with self._bind_lock:
            with self._lock:
                if self._closed:
                    raise RfbUnavailable("RFB backend is closed")
                old_id = self._source_bindings.get(source_id)
                old = self._bindings.get(old_id) if old_id else None
                if old is not None and not old.stop.is_set():
                    return self._binding_view(old)
                if old is not None:
                    self._bindings.pop(old.binding_id, None)
                self._source_bindings.pop(source_id, None)
            if old is not None:
                self._stop_binding(old)
            sock, width, height = self._connect_and_negotiate(source)
            size = _framebuffer_size(width, height, self._max_framebuffer_bytes)
            live = _LiveBinding(
                source=source,
                binding_id=uuid.uuid4().hex,
                source_epoch=_new_epoch(),
                geometry_revision=1,
                sock=sock,
                width=width,
                height=height,
                pixel_bytes=size,
                max_framebuffer_bytes=self._max_framebuffer_bytes,
                reconnect_min_delay_s=self._reconnect_min_delay_s,
                reconnect_max_delay_s=self._reconnect_max_delay_s,
            )
            with self._lock:
                if self._closed:
                    sock.close()
                    raise RfbUnavailable("RFB backend closed during bind")
                self._bindings[live.binding_id] = live
                self._source_bindings[source_id] = live.binding_id
                live.worker = threading.Thread(target=self._pump, args=(live,), name=f"rfb-{source_id}", daemon=True)
                live.worker.start()
            return self._binding_view(live)

    def _binding_view(self, live: _LiveBinding) -> dict[str, Any]:
        with live.state_lock:
            live_ready = live.status == "live" and live.baseline and not live.stop.is_set()
            input_state = "available" if live_ready else "unavailable"
            capture_state = live.status if not live.stop.is_set() else "disconnected"
            return {
                "binding_id": live.binding_id,
                "backend_id": self.backend_id,
                "source_id": live.source["source_id"],
                "source_instance": live.source["source_instance"],
                "source_epoch": live.source_epoch,
                "environment_incarnation": live.source["environment_incarnation"],
                "geometry_revision": live.geometry_revision,
                "width": live.width,
                "height": live.height,
                "modalities": ["pixels"] if live_ready else [],
                "backend_version": "rfb-3.8",
                "input_domain": live.source["environment_incarnation"],
                "input_domain_epoch": None,
                "focus_epoch": None,
                "operations": ["visual", "keyboard.key", "keyboard.text", "pointer.absolute", "pointer.button", "pointer.wheel"],
                "capture_state": capture_state,
                "input_state": input_state,
                "owned_control_state": "held" if live.owned_keys or live.owned_buttons else "idle",
            }

    def revalidate(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        """Read current binding identity/state without reconnecting or replacing the transport."""
        try:
            live = self._lookup(binding)
        except RfbUnavailable as exc:
            return {"supported": True, "valid": False, "reason": str(exc)}
        with self._lock:
            if self._closed:
                return {"supported": True, "valid": False, "reason": "RFB backend is closed"}
        return {"supported": True, "valid": True, "reason": None, **self._binding_view(live)}

    def revalidate_target(self, binding: Mapping[str, Any], semantic_target: Any) -> dict[str, Any]:
        """RFB pixels cannot attest semantic targets or accessibility hit testing."""
        try:
            self._lookup(binding)
        except RfbUnavailable as exc:
            return {"supported": False, "valid": False, "detail": str(exc)}
        return {"supported": False, "valid": False, "detail": "RFB provides no semantic-target or accessibility attestation"}


    def capture(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        live = self._lookup(binding)
        with live.state_lock:
            now = time.monotonic_ns()
            pixels = bytes(live.pixels) if live.baseline and live.pixels is not None else None
            coverage = {
                "kind": live.last_coverage_kind,
                "complete": live.baseline,
                "full_baseline": live.baseline,
                "complete_current_frame": live.baseline,
                "missing_regions": [] if live.baseline else [{"kind": "unknown", "reason": "full-baseline-not-reconstructed"}],
                "redacted_regions": [],
                "last_update_rectangle_count": live.last_rectangle_count,
                "skipped_intervals": [{"reason": "RFB may coalesce transient intermediate states; complete render history is unavailable"}],
                "source_sample_time_known": False,
                "connection_state": live.status,
                "error": live.last_error,
            }
            return {
                "source_id": live.source["source_id"],
                "source_instance": live.source["source_instance"],
                "environment_incarnation": live.source["environment_incarnation"],
                "binding_id": live.binding_id,
                "pixels": pixels,
                "width": live.width,
                "height": live.height,
                "pixel_format": _pixel_format_name() if pixels is not None else "none",
                "source_epoch": live.source_epoch,
                "geometry_revision": live.geometry_revision,
                "sequence": live.sequence,
                "sample_time_ns": None,
                "sample_clock_domain": None,
                "sample_time_uncertainty_ns": None,
                "receipt_clock_domain": "host-monotonic",
                "receipt_time_ns": live.last_receipt_time_ns or now,
                "coverage": coverage,
                "accessibility": None,
                "accessibility_sample_time_ns": None,
                "provenance": "linux-xvnc-rfb-transport",
                "audio": None,
            }

    def dispatch(self, binding: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
        live = self._lookup(binding)
        if self._closed:
            return self._outcome("rejected", 0, "none", "RFB backend is closing")
        if not isinstance(action, Mapping) or set(action) != {"operation", "arguments"}:
            return self._outcome("rejected", 0, "none", "action must contain only operation and arguments")
        arguments = action.get("arguments")
        if not isinstance(arguments, Mapping):
            return self._outcome("rejected", 0, "none", "action arguments must be a mapping")
        with live.state_lock:
            stale = self._binding_mismatch(live, binding)
            if stale:
                return self._outcome("rejected", 0, "none", stale)
            if live.status != "live" or not live.baseline or live.sock.fileno() < 0:
                return self._outcome("not-started", 0, "none", "RFB source lacks a live full framebuffer baseline")
            operation = action.get("operation")
            text_keysyms: list[int] = []
            wheel_button_mask = 0
            wheel_base_buttons = live.owned_buttons
            try:
                if operation == "keyboard.key":
                    if set(arguments) != {"key", "state"} or not isinstance(arguments.get("key"), str):
                        raise ValueError("keyboard.key arguments must contain a string key and state")
                    keysym = _key_code(arguments["key"])
                    state = arguments.get("state")
                    if state not in ("down", "up"):
                        raise ValueError("keyboard key state must be 'down' or 'up'")
                    down = state == "down"
                    if down and keysym in live.owned_keys:
                        raise ValueError("duplicate key-down is rejected; repeats are not synthesized")
                    if not down and keysym not in live.owned_keys:
                        raise ValueError("key-up is allowed only for a broker-owned key-down")
                    payload = struct.pack(">BB2xI", 4, 1 if down else 0, keysym)
                elif operation == "keyboard.text":
                    if set(arguments) != {"text"}:
                        raise ValueError("keyboard.text arguments must contain exactly text")
                    text_keysyms = _text_keysyms(arguments["text"])
                    event_count = len(live.owned_keys) + 2 * len(text_keysyms)
                    if event_count > _MAX_INPUT_EVENTS_PER_BATCH:
                        raise ValueError("text and held-key releases exceed the bounded RFB input batch")
                    payload = bytearray(event_count * 8)
                    offset = 0
                    for held_keysym in sorted(live.owned_keys):
                        struct.pack_into(">BB2xI", payload, offset, 4, 0, held_keysym)
                        offset += 8
                    for keysym in text_keysyms:
                        struct.pack_into(">BB2xI", payload, offset, 4, 1, keysym)
                        offset += 8
                        struct.pack_into(">BB2xI", payload, offset, 4, 0, keysym)
                        offset += 8
                elif operation == "pointer.absolute":
                    if set(arguments) != {"x", "y"}:
                        raise ValueError("pointer.absolute arguments must contain exactly x and y")
                    x = _integer(arguments.get("x"), "pointer x", 0, live.width - 1)
                    y = _integer(arguments.get("y"), "pointer y", 0, live.height - 1)
                    buttons = live.owned_buttons
                    payload = struct.pack(">BBHH", 5, buttons, x, y)
                elif operation == "pointer.button":
                    if set(arguments) != {"button", "state"}:
                        raise ValueError("pointer.button arguments must contain exactly button and state")
                    button = arguments.get("button")
                    state = arguments.get("state")
                    masks = {"left": 1, "middle": 2, "right": 4}
                    if not isinstance(button, str) or button not in masks or state not in ("down", "up"):
                        raise ValueError("pointer.button requires left/middle/right and down/up")
                    button_mask = masks[button]
                    down = state == "down"
                    if down and live.owned_buttons & button_mask:
                        raise ValueError("duplicate pointer button-down is rejected")
                    if not down and not live.owned_buttons & button_mask:
                        raise ValueError("pointer button-up is allowed only for a broker-owned button-down")
                    buttons = live.owned_buttons | button_mask if down else live.owned_buttons & ~button_mask
                    x, y = live.pointer_x, live.pointer_y
                    payload = struct.pack(">BBHH", 5, buttons, x, y)
                elif operation == "pointer.wheel":
                    if set(arguments) != {"dx", "dy"}:
                        raise ValueError("pointer.wheel arguments must contain exactly dx and dy")
                    dx = _integer(arguments.get("dx"), "wheel dx", -1200, 1200)
                    dy = _integer(arguments.get("dy"), "wheel dy", -1200, 1200)
                    if dx % _WHEEL_DELTA_PER_NOTCH or dy % _WHEEL_DELTA_PER_NOTCH:
                        raise ValueError("RFB wheel deltas must be whole 120-unit notches")
                    if dx == 0 and dy == 0:
                        raise ValueError("pointer.wheel requires a non-zero delta")
                    wheel_events: list[tuple[int, int]] = []
                    if dy:
                        wheel_events.append((8 if dy > 0 else 16, abs(dy) // _WHEEL_DELTA_PER_NOTCH))
                    if dx:
                        wheel_events.append((64 if dx > 0 else 32, abs(dx) // _WHEEL_DELTA_PER_NOTCH))
                    notch_count = sum(count for _mask, count in wheel_events)
                    event_count = 2 * notch_count
                    if event_count > _MAX_INPUT_EVENTS_PER_BATCH:
                        raise ValueError("wheel input exceeds the bounded RFB event batch")
                    payload = bytearray(event_count * 6)
                    buttons = live.owned_buttons
                    x, y = live.pointer_x, live.pointer_y
                    offset = 0
                    for mask, count in wheel_events:
                        wheel_button_mask |= mask
                        for _ in range(count):
                            struct.pack_into(">BBHH", payload, offset, 5, buttons | mask, x, y)
                            offset += 6
                            struct.pack_into(">BBHH", payload, offset, 5, buttons, x, y)
                            offset += 6
                else:
                    return self._outcome(
                        "rejected", 0, "none",
                        "operation must be keyboard.key, keyboard.text, pointer.absolute, pointer.button, or pointer.wheel",
                    )
                if not self._within_rate_limit(live):
                    return self._outcome("rejected", 0, "none", "bounded RFB input rate exceeded")
                if operation == "keyboard.key" and down:
                    live.owned_keys.add(keysym)
                elif operation == "keyboard.text":
                    live.owned_keys.update(text_keysyms)
                if operation == "pointer.absolute":
                    live.pointer_x, live.pointer_y = x, y
                    live.owned_buttons |= buttons
                elif operation == "pointer.button":
                    live.owned_buttons |= buttons
                elif operation == "pointer.wheel":
                    live.owned_buttons |= wheel_button_mask
                self._write_input(live, payload)
                if operation == "keyboard.key" and not down:
                    live.owned_keys.discard(keysym)
                elif operation == "keyboard.text":
                    live.owned_keys.clear()
                if operation in ("pointer.absolute", "pointer.button"):
                    live.owned_buttons = buttons
                elif operation == "pointer.wheel":
                    live.owned_buttons = wheel_base_buttons
                return self._outcome(
                    "delivered", 1, "transport-only",
                    "RFB event bytes were fully written to the transport; server/application handling is unacknowledged",
                )
            except (ValueError, struct.error) as exc:
                return self._outcome("rejected", 0, "none", str(exc))
            except RfbError as exc:
                self._invalidate_connection(live, live.sock, exc)
                return self._outcome("unknown", 0, "none", f"RFB write outcome is uncertain: {exc}")

    def _write_input(self, live: _LiveBinding, payload: bytes | bytearray) -> None:
        sock = live.sock
        with live.send_lock:
            if live.stop.is_set() or sock.fileno() < 0:
                raise RfbError("RFB source disconnected before input dispatch")
            _send(sock, payload)

    def neutralize(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        live = self._lookup(binding)
        with live.state_lock:
            if not live.owned_keys and not live.owned_buttons:
                return {"confirmed": True, "detail": "no broker-owned RFB key or pointer controls are held"}
            if live.status not in ("live", "awaiting_full_baseline") or live.stop.is_set() or live.sock.fileno() < 0:
                return {"confirmed": False, "detail": "source lost with broker-owned controls potentially held; release is uncertain"}
            pending = list(sorted(live.owned_keys))
            if live.owned_buttons:
                pending.append(None)
            try:
                for keysym in pending:
                    if keysym is None:
                        payload = struct.pack(">BBHH", 5, 0, live.pointer_x, live.pointer_y)
                        self._write_input(live, payload)
                        live.owned_buttons = 0
                    else:
                        payload = struct.pack(">BB2xI", 4, 0, keysym)
                        self._write_input(live, payload)
                        live.owned_keys.discard(keysym)
            except RfbError as exc:
                return {"confirmed": False, "detail": f"release delivery is uncertain: {exc}"}
            return {
                "confirmed": False,
                "detail": "broker-owned key/button release events were written, but RFB has no server or application acknowledgement",
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            bindings = list(self._bindings.values())
        for live in bindings:
            try:
                self.neutralize(self._binding_view(live))
            except RfbUnavailable:
                pass
            self._stop_binding(live)
        with self._lock:
            self._bindings.clear()
            self._source_bindings.clear()

    def _lookup(self, binding: Mapping[str, Any]) -> _LiveBinding:
        if not isinstance(binding, Mapping):
            raise RfbUnavailable("binding must be a mapping")
        binding_id = binding.get("binding_id")
        if not isinstance(binding_id, str):
            raise RfbUnavailable("binding_id is missing")
        with self._lock:
            live = self._bindings.get(binding_id)
        if live is None:
            raise RfbUnavailable("binding is no longer active")
        return live

    @staticmethod
    def _binding_mismatch(live: _LiveBinding, binding: Mapping[str, Any]) -> str | None:
        if binding.get("source_epoch") != live.source_epoch:
            return "stale source_epoch; rebind and reconstruct a full baseline before input"
        if binding.get("geometry_revision") != live.geometry_revision:
            return "stale geometry_revision; rebind before input"
        if binding.get("environment_incarnation") != live.source["environment_incarnation"]:
            return "stale environment_incarnation; explicit rebind is required"
        if binding.get("source_instance") != live.source["source_instance"]:
            return "stale source_instance; explicit rebind is required"
        return None

    @staticmethod
    def _outcome(disposition: str, delivered_count: int, ack_strength: str, detail: str) -> dict[str, Any]:
        return {
            "disposition": disposition,
            "delivered_count": delivered_count,
            "ack_strength": ack_strength,
            "detail": detail,
        }

    @staticmethod
    def _within_rate_limit(live: _LiveBinding) -> bool:
        now = time.monotonic()
        while live.recent_inputs and now - live.recent_inputs[0] >= 1.0:
            live.recent_inputs.popleft()
        if len(live.recent_inputs) >= 60:
            return False
        live.recent_inputs.append(now)
        return True

    def _open_transport(self, source: Mapping[str, Any]) -> socket.socket:
        transport = source["transport"]
        timeout = self._connect_timeout_s
        if transport["kind"] == "unix":
            if os.name != "posix" or not hasattr(socket, "SO_PEERCRED") or not hasattr(socket, "AF_UNIX"):
                raise RfbUnavailable("owner-authenticated Linux Unix sockets are unavailable on this host")
            path = Path(transport["socket_path"])
            try:
                parent = path.parent.lstat()
                endpoint = path.lstat()
            except OSError as exc:
                raise RfbUnavailable(f"configured RFB Unix socket is missing: {type(exc).__name__}") from exc
            expected_uid = transport["owner_uid"]
            if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != expected_uid or stat.S_IMODE(parent.st_mode) & 0o077:
                raise RfbUnavailable("RFB socket directory must be a non-symlink owner-only directory")
            if not stat.S_ISSOCK(endpoint.st_mode) or endpoint.st_uid != expected_uid or stat.S_IMODE(endpoint.st_mode) & 0o077:
                raise RfbUnavailable("RFB endpoint must be an owner-only Unix socket owned by the declared uid")
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                sock.connect(str(path))
                current = path.lstat()
                if (current.st_dev, current.st_ino) != (endpoint.st_dev, endpoint.st_ino):
                    raise RfbUnavailable("RFB Unix socket changed during connection")
                peer_pid, peer_uid, _peer_gid = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
                if peer_pid <= 0 or peer_uid != expected_uid:
                    raise RfbUnavailable("RFB Unix socket peer uid does not match the declared owner")
                return sock
            except Exception:
                sock.close()
                raise

        if transport["kind"] != "protected-tcp-tls":
            raise RfbUnavailable("unsupported RFB transport")
        tls = transport["tls"]
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=tls["ca_file"])
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        try:
            context.load_cert_chain(certfile=tls["client_cert"], keyfile=tls["client_key"])
        except (OSError, ssl.SSLError) as exc:
            raise RfbUnavailable(f"configured TLS client identity is unavailable: {type(exc).__name__}") from exc
        raw = socket.create_connection((transport["host"], transport["port"]), timeout=timeout)
        raw.settimeout(timeout)
        try:
            secured = context.wrap_socket(raw, server_hostname=tls["server_hostname"])
        except (OSError, ssl.SSLError) as exc:
            raw.close()
            raise RfbUnavailable(f"protected RFB TLS handshake failed without fallback: {type(exc).__name__}") from exc
        return secured

    def _connect_and_negotiate(self, source: Mapping[str, Any]) -> tuple[socket.socket, int, int]:
        sock = self._open_transport(source)
        try:
            version = _recv_exact(sock, 12)
            if version != b"RFB 003.008\n":
                raise RfbError("only RFB 3.8 is accepted; protocol downgrade is forbidden")
            _send(sock, b"RFB 003.008\n")
            security_count = _recv_exact(sock, 1)[0]
            if security_count == 0:
                raise RfbError(f"RFB server rejected connection: {_skip_reason(sock)}")
            if security_count > 64:
                raise RfbError("RFB security type list exceeds the configured limit")
            security_types = _recv_exact(sock, security_count)
            if 1 not in security_types:
                raise RfbError("RFB None security is unavailable inside the authenticated transport")
            _send(sock, b"\x01")
            result = struct.unpack(">I", _recv_exact(sock, 4))[0]
            if result != 0:
                raise RfbError(f"RFB authentication failed: {_skip_reason(sock)}")
            _send(sock, b"\x01")  # ClientInit(shared=1), never exclusive by default.
            dimensions = _recv_exact(sock, 4)
            width, height = struct.unpack(">HH", dimensions)
            _framebuffer_size(width, height, self._max_framebuffer_bytes)
            server_format = _recv_exact(sock, 16)
            self._validate_server_pixel_format(server_format)
            name_length = struct.unpack(">I", _recv_exact(sock, 4))[0]
            if name_length > _MAX_SERVER_NAME_BYTES:
                raise RfbError("RFB server name exceeds the configured limit")
            _recv_exact(sock, name_length)  # Untrusted label; never used for identity or authority.
            _send(sock, b"\x00\x00\x00\x00" + _PIXEL_FORMAT_BYTES)
            encodings = struct.pack(">BBH", 2, 0, len(_RFB_ENCODINGS)) + b"".join(struct.pack(">i", item) for item in _RFB_ENCODINGS)
            _send(sock, encodings)
            sock.settimeout(None)
            _set_send_timeout(sock)
            return sock, width, height
        except Exception:
            sock.close()
            raise

    @staticmethod
    def _validate_server_pixel_format(pixel_format: bytes) -> None:
        bpp, depth, big_endian, true_colour = struct.unpack_from(">BBBB", pixel_format)
        if bpp not in (8, 16, 32) or depth < 1 or depth > bpp or big_endian not in (0, 1) or true_colour != 1:
            raise RfbError("RFB server advertised an unsupported pixel format")
        red_max, green_max, blue_max = struct.unpack_from(">HHH", pixel_format, 4)
        red_shift, green_shift, blue_shift = struct.unpack_from(">BBB", pixel_format, 10)
        if not red_max or not green_max or not blue_max or max(red_shift, green_shift, blue_shift) >= bpp:
            raise RfbError("RFB server pixel format has invalid colour fields")

    def _pump(self, live: _LiveBinding) -> None:
        sock = live.sock
        delay = live.reconnect_min_delay_s
        while not live.stop.is_set():
            try:
                with live.send_lock:
                    self._request_update(live, incremental=False, sock=sock)
                self._read_server_messages(live, sock)
                delay = live.reconnect_min_delay_s
            except (OSError, RfbError, struct.error, ValueError) as exc:
                if live.stop.is_set():
                    break
                self._invalidate_connection(live, sock, exc)
                if live.stop.wait(delay):
                    break
                delay = min(live.reconnect_max_delay_s, max(live.reconnect_min_delay_s, delay * 2.0))
                try:
                    sock, width, height = self._connect_and_negotiate(live.source)
                    with live.state_lock:
                        if live.stop.is_set():
                            sock.close()
                            break
                        live.sock = sock
                        live.width = width
                        live.height = height
                        live.pixel_bytes = _framebuffer_size(width, height, live.max_framebuffer_bytes)
                        live.pixels = None
                        live.coverage = None
                        live.covered_pixels = 0
                        live.baseline = False
                        live.status = "awaiting_full_baseline"
                        live.last_error = None
                        live.source_epoch = _new_epoch()
                        live.geometry_revision += 1
                        live.last_coverage_kind = "reconnect-full-request"
                    delay = live.reconnect_min_delay_s
                except (OSError, RfbError, RfbUnavailable, ValueError, struct.error) as reconnect_error:
                    with live.state_lock:
                        live.status = "disconnected"
                        live.last_error = f"reconnect failed: {type(reconnect_error).__name__}"
                    continue
        try:
            sock.close()
        except OSError:
            pass

    def _invalidate_connection(self, live: _LiveBinding, sock: socket.socket, exc: BaseException) -> None:
        try:
            sock.close()
        except OSError:
            pass
        with live.state_lock:
            if live.sock is sock and live.status != "disconnected":
                live.status = "disconnected"
                live.last_error = f"RFB connection lost: {type(exc).__name__}: {exc}"
                live.pixels = None
                live.coverage = None
                live.covered_pixels = 0
                live.baseline = False
                live.source_epoch = _new_epoch()
                live.geometry_revision += 1
                live.last_coverage_kind = "disconnected-no-baseline"

    def _read_server_messages(self, live: _LiveBinding, sock: socket.socket) -> None:
        while not live.stop.is_set():
            message_type = _recv_exact(sock, 1, live.stop)[0]
            if message_type == 0:
                self._read_framebuffer_update(live, sock)
                with live.state_lock:
                    live.status = "live" if live.baseline else "awaiting_full_baseline"
                    if live.baseline:
                        live.last_receipt_time_ns = time.monotonic_ns()
                    incremental = live.baseline
                with live.send_lock:
                    self._request_update(live, incremental=incremental, sock=sock)
                continue
            if message_type == 2:  # Bell: not a visual or accessibility observation.
                continue
            if message_type == 3:  # ServerCutText is deliberately discarded, never published.
                header = _recv_exact(sock, 7, live.stop)
                length = struct.unpack_from(">I", header, 3)[0]
                if length > _MAX_CUT_TEXT_BYTES:
                    raise RfbError("RFB clipboard payload exceeds the discard limit")
                _recv_exact(sock, length, live.stop)
                continue
            raise RfbError(f"unsupported RFB server message type {message_type}")

    def _read_framebuffer_update(self, live: _LiveBinding, sock: socket.socket) -> None:
        _recv_exact(sock, 1, live.stop)  # padding
        rectangle_count = struct.unpack(">H", _recv_exact(sock, 2, live.stop))[0]
        if rectangle_count > _MAX_RECTANGLES_PER_UPDATE:
            raise RfbError("RFB update rectangle count exceeds the configured limit")
        with live.state_lock:
            if live.pixels is None:
                live.pixels = bytearray(_framebuffer_size(live.width, live.height, live.max_framebuffer_bytes))
                live.coverage = bytearray(live.width * live.height)
                live.covered_pixels = 0
            rects_processed = 0
            resized = False
        for _ in range(rectangle_count):
            x, y, width, height, encoding = struct.unpack(">HHHHi", _recv_exact(sock, 12, live.stop))
            if encoding == -223:  # DesktopSize pseudo-encoding.
                if x != 0 or y != 0:
                    raise RfbError("DesktopSize rectangle has a non-zero origin")
                size = _framebuffer_size(width, height, live.max_framebuffer_bytes)
                with live.state_lock:
                    if (width, height) != (live.width, live.height):
                        live.width, live.height = width, height
                        live.pointer_x = min(live.pointer_x, width - 1)
                        live.pointer_y = min(live.pointer_y, height - 1)
                        live.pixel_bytes = size
                        live.geometry_revision += 1
                        live.pixels = bytearray(size)
                        live.coverage = bytearray(width * height)
                        live.covered_pixels = 0
                        live.baseline = False
                        live.status = "awaiting_full_baseline"
                        live.last_coverage_kind = "resized-full-request"
                        resized = True
                continue
            if width < 1 or height < 1:
                raise RfbError("RFB update rectangle is empty")
            if encoding == 0:
                if width * height * 4 > live.max_framebuffer_bytes:
                    raise RfbError("RFB raw rectangle exceeds the configured byte limit")
                with live.state_lock:
                    if x + width > live.width or y + height > live.height or live.pixels is None:
                        raise RfbError("RFB raw rectangle is outside the current framebuffer")
                self._read_raw_rect(live, sock, x, y, width, height)
            elif encoding == 1:
                src_x, src_y = struct.unpack(">HH", _recv_exact(sock, 4, live.stop))
                with live.state_lock:
                    if (
                        x + width > live.width
                        or y + height > live.height
                        or src_x + width > live.width
                        or src_y + height > live.height
                        or live.pixels is None
                    ):
                        raise RfbError("RFB CopyRect source or destination is outside the framebuffer")
                    self._copy_rect(live, x, y, src_x, src_y, width, height)
            else:
                raise RfbError(f"unsupported RFB framebuffer encoding {encoding}")
            rects_processed += 1
        with live.state_lock:
            live.sequence += 1
            live.last_rectangle_count = rects_processed
            if not live.baseline and live.coverage is not None and live.covered_pixels == live.width * live.height:
                live.baseline = True
                live.coverage = None
                live.status = "live"
                live.last_coverage_kind = "full-reconstructed-frame"
            elif not live.baseline:
                live.status = "awaiting_full_baseline"
                live.last_coverage_kind = "partial-baseline-pending" if not resized else "resized-partial-baseline-pending"
            else:
                live.status = "live"
                live.last_coverage_kind = "incremental-changed-regions"
            live.last_receipt_time_ns = time.monotonic_ns()

    def _read_raw_rect(self, live: _LiveBinding, sock: socket.socket, x: int, y: int, width: int, height: int) -> None:
        data_length = width * height * 4
        if data_length > live.max_framebuffer_bytes:
            raise RfbError("RFB raw rectangle exceeds the configured byte limit")
        data = _recv_exact(sock, data_length, live.stop)
        with live.state_lock:
            if x + width > live.width or y + height > live.height or live.pixels is None:
                raise RfbError("RFB raw rectangle became invalid before application")
            coverage = live.coverage if not live.baseline else None
            if not live.baseline and coverage is None:
                raise RfbError("RFB baseline coverage is unavailable")
            for row in range(height):
                source_start = row * width * 4
                target_start = ((y + row) * live.width + x) * 4
                target_end = target_start + width * 4
                live.pixels[target_start:target_end] = data[source_start:source_start + width * 4]
                alpha_start = target_start + 3
                memoryview(live.pixels)[alpha_start:target_end:4] = _OPAQUE_ALPHA_ROW[:width]
                if coverage is not None:
                    coverage_start = (y + row) * live.width + x
                    coverage_end = coverage_start + width
                    existing = coverage[coverage_start:coverage_end]
                    live.covered_pixels += width - existing.count(1)
                    coverage[coverage_start:coverage_end] = b"\x01" * width

    def _copy_rect(self, live: _LiveBinding, x: int, y: int, src_x: int, src_y: int, width: int, height: int) -> None:
        assert live.pixels is not None
        coverage = live.coverage if not live.baseline else None
        if not live.baseline and coverage is None:
            raise RfbError("CopyRect baseline coverage is unavailable")
        if coverage is not None:
            for row in range(height):
                start = (src_y + row) * live.width + src_x
                if coverage[start:start + width].count(1) != width:
                    raise RfbError("CopyRect source contains pixels outside the reconstructed baseline")
        row_order = range(height - 1, -1, -1) if y > src_y else range(height)
        for row in row_order:
            src_start = ((src_y + row) * live.width + src_x) * 4
            dst_start = ((y + row) * live.width + x) * 4
            row_bytes = width * 4
            live.pixels[dst_start:dst_start + row_bytes] = live.pixels[src_start:src_start + row_bytes]
        if coverage is not None:
            for row in range(height):
                start = (y + row) * live.width + x
                existing = coverage[start:start + width]
                live.covered_pixels += width - existing.count(1)
                coverage[start:start + width] = b"\x01" * width

    @staticmethod
    def _request_update(live: _LiveBinding, *, incremental: bool, sock: socket.socket) -> None:
        width, height = live.width, live.height
        if width < 1 or height < 1:
            raise RfbError("cannot request an RFB update without valid geometry")
        request = struct.pack(">BBHHHH", 3, 1 if incremental else 0, 0, 0, width, height)
        _send(sock, request)

    def _stop_binding(self, live: _LiveBinding) -> None:
        live.stop.set()
        try:
            live.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            live.sock.close()
        except OSError:
            pass
        worker = live.worker
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=2.0)
