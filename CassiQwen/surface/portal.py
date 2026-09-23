"""Consent-gated Linux Wayland capture and remote input via xdg-desktop-portal.

The module deliberately imports no platform-specific package at import time.
On Windows and on Linux installations without its optional runtime pieces,
``describe`` reports exact unavailable reasons; it never substitutes a host
input API.  Portal consent and the compositor remain the only source of
screen access and remote-input authority.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import math
import os
import re
import secrets
import select
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

try:  # Optional: the adapter remains importable on non-Linux hosts.
    from dbus_next import BusType, Message, MessageType, Variant
    from dbus_next.aio import MessageBus
except Exception as _dbus_import_error:  # pragma: no cover - host dependent
    BusType = Message = MessageType = Variant = MessageBus = None  # type: ignore[assignment,misc]
    _DBUS_IMPORT_ERROR: str | None = f"{type(_dbus_import_error).__name__}: {_dbus_import_error}"
else:  # pragma: no cover - availability depends on host
    _DBUS_IMPORT_ERROR = None


BACKEND_ID = "linux-xdg-portal"
_PORTAL_NAME = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"
_SCREENCAST = "org.freedesktop.portal.ScreenCast"
_REMOTE_DESKTOP = "org.freedesktop.portal.RemoteDesktop"
_SESSION = "org.freedesktop.portal.Session"
_REQUEST = "org.freedesktop.portal.Request"
_DBUS = "org.freedesktop.DBus"
_PROPERTIES = "org.freedesktop.DBus.Properties"

SOURCE_TYPES: dict[str, int] = {"portal:monitor": 1, "portal:window": 2, "portal:virtual": 4}
_SOURCE_NAMES = {value: key.removeprefix("portal:") for key, value in SOURCE_TYPES.items()}
CURSOR_MODES: dict[str, int] = {"hidden": 1, "embedded": 2, "metadata": 4}
_DEVICE_NAMES: dict[int, str] = {1: "keyboard", 2: "pointer", 4: "touchscreen"}

_MAX_FRAME_BYTES = 16 * 1024 * 1024
_MAX_FRAME_EDGE = 8192
_MAX_CAPTURE_SECONDS = 8.0
_MAX_STDERR_BYTES = 64 * 1024
_MAX_INPUT_DELTA = 10_000.0
_MAX_HELD_KEYS = 16
_MAX_HELD_BUTTONS = 16
_MAX_HELD_TOUCHES = 16
_DEFAULT_REQUEST_TIMEOUT = 120.0
_DEFAULT_METHOD_TIMEOUT = 5.0


class PortalUnavailableError(RuntimeError):
    """A required portal capability or optional dependency is unavailable."""


class PortalConsentError(RuntimeError):
    """A portal request was cancelled or rejected by the user/compositor."""


class _PortalDBusError(RuntimeError):
    def __init__(self, name: str, detail: str) -> None:
        super().__init__(detail)
        self.name = name
        self.detail = detail


@dataclass
class _PortalSession:
    handle: str
    source_id: str
    source_mask: int
    session_epoch: int
    pipewire_fd: int
    stream: dict[str, Any]
    binding: dict[str, Any]
    granted_devices: int
    input_method: str = "notify"
    closed: bool = False
    close_reason: str | None = None
    sequence: int = 0
    geometry_revision: int = 1
    physical_size: tuple[int, int] | None = None
    held_keycodes: set[int] = field(default_factory=set)
    held_keysyms: set[int] = field(default_factory=set)
    held_buttons: set[int] = field(default_factory=set)
    held_touches: set[int] = field(default_factory=set)
    lock: threading.RLock = field(default_factory=threading.RLock)


class _PortalLoop:
    """Serialize D-Bus portal traffic on a private asyncio loop."""

    def __init__(self, request_timeout: float, method_timeout: float) -> None:
        if MessageBus is None:
            raise PortalUnavailableError(f"python package dbus-next is unavailable: {_DBUS_IMPORT_ERROR}")
        self.request_timeout = request_timeout
        self.method_timeout = method_timeout
        self.loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="cassi-xdg-portal-dbus", daemon=True)
        self._bus: Any = None
        self._owner: str | None = None
        self._pending: dict[str, tuple[asyncio.Future[tuple[int, dict[str, Any]]], str | None]] = {}
        self._closed_sessions: dict[str, str] = {}
        self._portal_lost = False
        self._closed = False
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            self._closed = True
            raise PortalUnavailableError("could not start the portal D-Bus event loop")
        try:
            self._call(self._connect(), timeout=method_timeout)
        except Exception:
            self.close()
            raise

    @property
    def owner(self) -> str | None:
        return self._owner

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        self.loop.run_forever()
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self.loop.close()

    def _call(self, awaitable: Any, *, timeout: float | None = None) -> Any:
        if self._closed or not self.loop.is_running():
            if hasattr(awaitable, "close"):
                awaitable.close()
            raise PortalUnavailableError("portal D-Bus connection is closed")
        future = asyncio.run_coroutine_threadsafe(awaitable, self.loop)
        try:
            return future.result(timeout=timeout or self.method_timeout)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise TimeoutError("portal D-Bus operation timed out") from exc

    async def _connect(self) -> None:
        assert MessageBus is not None and BusType is not None
        self._bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self._bus.add_message_handler(self._on_message)
        owner_reply = await self._bus.call(
            Message(
                destination=_DBUS,
                path="/org/freedesktop/DBus",
                interface=_DBUS,
                member="GetNameOwner",
                signature="s",
                body=[_PORTAL_NAME],
            )
        )
        if owner_reply.message_type == MessageType.ERROR:
            raise _message_error(owner_reply)
        self._owner = str(owner_reply.body[0])
        for rule in (
            "type='signal',interface='org.freedesktop.portal.Request',member='Response',sender='org.freedesktop.portal.Desktop'",
            "type='signal',interface='org.freedesktop.portal.Session',member='Closed',sender='org.freedesktop.portal.Desktop'",
            "type='signal',interface='org.freedesktop.DBus',member='NameOwnerChanged'",
        ):
            match_reply = await self._bus.call(
                Message(
                    destination=_DBUS,
                    path="/org/freedesktop/DBus",
                    interface=_DBUS,
                    member="AddMatch",
                    signature="s",
                    body=[rule],
                )
            )
            if match_reply.message_type == MessageType.ERROR:
                raise _message_error(match_reply)
        node = await self._bus.introspect(_PORTAL_NAME, _PORTAL_PATH)
        interfaces = {interface.name for interface in node.interfaces}
        missing = [name for name in (_SCREENCAST, _REMOTE_DESKTOP) if name not in interfaces]
        if missing:
            raise PortalUnavailableError("portal service does not implement " + ", ".join(missing))

    def _on_message(self, message: Any) -> bool:
        if message.message_type != MessageType.SIGNAL:
            return False
        sender = getattr(message, "sender", None)
        if message.interface in (_REQUEST, _SESSION) and sender and self._owner and sender != self._owner:
            return False
        if message.interface == _REQUEST and message.member == "Response" and message.body:
            path = str(getattr(message, "path", ""))
            token = path.rsplit("/", 1)[-1]
            pending = self._pending.get(token)
            if pending is not None:
                future, _ = pending
                if not future.done():
                    response = int(message.body[0])
                    results = _plain(message.body[1]) if len(message.body) > 1 else {}
                    future.set_result((response, results if isinstance(results, dict) else {}))
            return False
        if message.interface == _SESSION and message.member == "Closed":
            path = str(getattr(message, "path", ""))
            reason_code = int(message.body[0]) if message.body else 0
            self._closed_sessions[path] = f"portal session closed (reason {reason_code})"
            return False
        if message.interface == _DBUS and message.member == "NameOwnerChanged" and len(message.body) >= 3:
            name, old_owner, new_owner = map(str, message.body[:3])
            if name == _PORTAL_NAME and old_owner != new_owner:
                self._portal_lost = True
                for path in tuple(self._closed_sessions):
                    self._closed_sessions[path] = "portal service owner changed"
            return False
        return False

    async def _call_message(self, message: Any, *, timeout: float | None = None) -> Any:
        if self._portal_lost or self._bus is None:
            raise PortalUnavailableError("the xdg-desktop-portal service was lost")
        reply = await asyncio.wait_for(self._bus.call(message), timeout=timeout or self.method_timeout)
        if reply.message_type == MessageType.ERROR:
            raise _message_error(reply)
        return reply

    async def _request(
        self,
        interface: str,
        method: str,
        signature: str,
        body: list[Any],
        options: Mapping[str, Any],
    ) -> dict[str, Any]:
        if self._portal_lost or self._bus is None:
            raise PortalUnavailableError("the xdg-desktop-portal service was lost")
        token = secrets.token_hex(12)
        request_future: asyncio.Future[tuple[int, dict[str, Any]]] = self.loop.create_future()
        self._pending[token] = (request_future, self._owner)
        vardict = dict(options)
        vardict["handle_token"] = Variant("s", token)
        request_path: str | None = None
        try:
            reply = await self._call_message(
                Message(
                    destination=_PORTAL_NAME,
                    path=_PORTAL_PATH,
                    interface=interface,
                    member=method,
                    signature=signature,
                    body=[*body, vardict],
                )
            )
            if reply.body:
                request_path = str(reply.body[0])
            response, results = await asyncio.wait_for(request_future, timeout=self.request_timeout)
            if response != 0:
                label = "cancelled" if response == 1 else "failed"
                raise PortalConsentError(f"portal {method} request {label} (response {response})")
            return results
        except asyncio.TimeoutError as exc:
            if request_path:
                await self._close_request(request_path)
            raise TimeoutError(f"portal {method} request did not complete before its deadline") from exc
        finally:
            self._pending.pop(token, None)
            if not request_future.done():
                request_future.cancel()

    async def _close_request(self, path: str) -> None:
        try:
            await self._call_message(
                Message(destination=_PORTAL_NAME, path=path, interface=_REQUEST, member="Close")
            )
        except Exception:
            pass

    async def _get_property(self, interface: str, name: str) -> Any:
        reply = await self._call_message(
            Message(
                destination=_PORTAL_NAME,
                path=_PORTAL_PATH,
                interface=_PROPERTIES,
                member="Get",
                signature="ss",
                body=[interface, name],
            )
        )
        return _plain(reply.body[0])

    async def capabilities(self) -> dict[str, Any]:
        screen_version = await self._get_property(_SCREENCAST, "version")
        remote_version = await self._get_property(_REMOTE_DESKTOP, "version")
        source_types = await self._get_property(_SCREENCAST, "AvailableSourceTypes")
        try:
            cursor_modes = await self._get_property(_SCREENCAST, "AvailableCursorModes")
        except _PortalDBusError:
            if int(screen_version) < 2:
                cursor_modes = 1
            else:
                raise
        device_types = await self._get_property(_REMOTE_DESKTOP, "AvailableDeviceTypes")
        return {
            "screen_cast_version": int(screen_version),
            "remote_desktop_version": int(remote_version),
            "available_source_types": int(source_types),
            "available_cursor_modes": int(cursor_modes),
            "available_device_types": int(device_types),
            "portal_owner": self._owner,
        }

    def request(self, interface: str, method: str, signature: str, body: list[Any], options: Mapping[str, Any]) -> dict[str, Any]:
        return self._call(self._request(interface, method, signature, body, options), timeout=self.request_timeout + self.method_timeout)

    def method(self, interface: str, method: str, signature: str, body: list[Any]) -> Any:
        message = Message(
            destination=_PORTAL_NAME,
            path=_PORTAL_PATH,
            interface=interface,
            member=method,
            signature=signature,
            body=body,
        )
        return self._call(self._call_message(message), timeout=self.method_timeout)

    def open_pipewire_remote(self, session_handle: str) -> int:
        reply = self._call(
            self._call_message(
                Message(
                    destination=_PORTAL_NAME,
                    path=_PORTAL_PATH,
                    interface=_SCREENCAST,
                    member="OpenPipeWireRemote",
                    signature="oa{sv}",
                    body=[session_handle, {}],
                )
            ),
            timeout=self.method_timeout,
        )
        if not reply.body:
            raise PortalUnavailableError("portal returned no PipeWire remote file descriptor")
        return _take_fd(reply.body[0])

    def close_session(self, session_handle: str) -> None:
        if self._portal_lost:
            return
        self._call(
            self._call_message(
                Message(
                    destination=_PORTAL_NAME,
                    path=session_handle,
                    interface=_SESSION,
                    member="Close",
                )
            ),
            timeout=self.method_timeout,
        )

    def session_status(self, session_handle: str) -> tuple[bool, str | None]:
        return self._call(self._session_status(session_handle), timeout=self.method_timeout)

    async def _session_status(self, session_handle: str) -> tuple[bool, str | None]:
        if self._portal_lost or self._bus is None:
            return False, "the xdg-desktop-portal service was lost"
        reason = self._closed_sessions.get(session_handle)
        return reason is None, reason

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self.loop.is_running():
                self._call(self._disconnect(), timeout=2.0)
        except Exception:
            pass
        self._closed = True
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if threading.current_thread() is not self._thread:
            self._thread.join(timeout=2.0)

    async def _disconnect(self) -> None:
        bus = self._bus
        self._bus = None
        if bus is not None:
            try:
                bus.disconnect()
            except Exception:
                pass


def _message_error(message: Any) -> _PortalDBusError:
    name = str(getattr(message, "error_name", None) or "org.freedesktop.DBus.Error.Failed")
    body = getattr(message, "body", None) or []
    detail = str(body[0]) if body else name
    return _PortalDBusError(name, detail)


def _plain(value: Any) -> Any:
    if hasattr(value, "value") and type(value).__name__ == "Variant":
        return _plain(value.value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return tuple(_plain(item) for item in value)
    return value


def _take_fd(value: Any) -> int:
    take = getattr(value, "take", None)
    if callable(take):
        fd = int(take())
    elif hasattr(value, "fileno"):
        fd = os.dup(int(value.fileno()))
    elif isinstance(value, int):
        fd = os.dup(value)
    else:
        raise PortalUnavailableError("dbus-next did not expose the portal file descriptor")
    os.set_inheritable(fd, False)
    return fd


def _variant_map(values: Mapping[str, tuple[str, Any]]) -> dict[str, Any]:
    assert Variant is not None
    return {name: Variant(signature, value) for name, (signature, value) in values.items()}


def _positive_size(value: Any) -> tuple[int, int] | None:
    value = _plain(value)
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return None
    width, height = value
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        return None
    if width > _MAX_FRAME_EDGE or height > _MAX_FRAME_EDGE:
        return None
    return width, height


class LinuxPortalBackend:
    """ScreenCast and RemoteDesktop adapter with consent-bound session state.

    ``source_id`` is a source *kind* (``portal:monitor``, ``portal:window``,
    ``portal:virtual`` or ``portal:any``).  The compositor's interactive
    portal dialog performs the actual source choice; source titles and real
    stream identities are returned only after consent.

    Input is intentionally the portal's Notify method family only.  This
    adapter never calls ``ConnectToEIS`` and never mixes EIS and Notify input.
    EIS is reported as unavailable until a real libei sender implementation
    is supplied by this adapter.  No restore token leaves this object or is
    written to disk.
    """

    def __init__(
        self,
        *,
        backend_id: str = BACKEND_ID,
        cursor_mode: str = "embedded",
        requested_devices: int = 3,
        persist_mode: int = 0,
        host_restore_token: str | None = None,
        request_timeout: float = _DEFAULT_REQUEST_TIMEOUT,
        method_timeout: float = _DEFAULT_METHOD_TIMEOUT,
    ) -> None:
        if cursor_mode not in CURSOR_MODES:
            raise ValueError(f"unsupported cursor mode {cursor_mode!r}")
        if type(requested_devices) is not int or requested_devices < 0 or requested_devices & ~7:
            raise ValueError("requested_devices must be a RemoteDesktop device-type bitmask")
        if type(persist_mode) is not int or persist_mode not in (0, 1, 2):
            raise ValueError("persist_mode must be 0 (none), 1 (application), or 2 (explicit revoke)")
        if request_timeout <= 0 or method_timeout <= 0:
            raise ValueError("portal timeouts must be positive")
        self.backend_id = backend_id
        self.cursor_mode = cursor_mode
        self.requested_devices = requested_devices
        self.persist_mode = persist_mode
        self._restore_token = host_restore_token or None
        self._request_timeout = float(request_timeout)
        self._method_timeout = float(method_timeout)
        self._runtime: _PortalLoop | None = None
        self._runtime_error: str | None = None
        self._bind_lock = threading.Lock()
        self._runtime_lock = threading.RLock()
        self._state_lock = threading.RLock()
        self._sessions: dict[str, _PortalSession] = {}
        self._bindings: dict[str, _PortalSession] = {}
        self._epoch = 0
        self._environment_incarnation = secrets.token_urlsafe(18)
        self._gstreamer: dict[str, Any] | None = None
        self._gstreamer_checked = False
        self._closed = False

    def describe(self) -> dict[str, Any]:
        """Return live per-operation portal capability and dependency status."""
        dependencies = self._dependency_status()
        gst_ready = self._probe_gstreamer()
        portal: dict[str, Any] = {
            "status": "unavailable",
            "reason": dependencies["portal_reason"],
            "screen_cast_version": None,
            "remote_desktop_version": None,
            "available_source_types": 0,
            "available_cursor_modes": 0,
            "available_device_types": 0,
            "environment_incarnation": self._environment_incarnation,
            "input_method": "notify-only",
            "portal_owner": None,
        }
        if dependencies["portal_ready"]:
            try:
                runtime = self._get_runtime()
                capabilities = runtime._call(runtime.capabilities(), timeout=self._method_timeout)
                portal.update(capabilities)
                portal["status"] = "supported"
                portal["reason"] = None
            except Exception as exc:
                self._runtime_error = _reason(exc)
                portal["reason"] = self._runtime_error
        screen_ok = portal["status"] == "supported" and int(portal["screen_cast_version"] or 0) >= 1
        remote_ok = portal["status"] == "supported" and int(portal["remote_desktop_version"] or 0) >= 1
        capture_problems = [
            dependencies["platform_reason"],
            dependencies["wayland_reason"] if not dependencies["wayland"] else None,
            dependencies["dbus_reason"] if not dependencies["dbus_module"] else None,
            dependencies["dbus_bus_reason"] if not dependencies["dbus_session_bus"] else None,
            gst_ready["reason"] if not gst_ready["ready"] else None,
        ]
        if portal["status"] != "supported":
            capture_problems.append(portal["reason"] or "desktop portal is unavailable")
        elif not screen_ok:
            capture_problems.append("ScreenCast interface version 1 or later is unavailable")
        if portal["status"] == "supported" and not remote_ok:
            capture_problems.append("RemoteDesktop interface version 1 or later is unavailable for the combined consent-bound session")
        capture_reason = "; ".join(dict.fromkeys(problem for problem in capture_problems if problem)) or None
        input_surface_ready = remote_ok and capture_reason is None
        input_devices = int(portal.get("available_device_types", 0))
        operations = {
            "source.list": _capability(screen_ok and dependencies["wayland"] and dependencies["dbus_module"], None if screen_ok else (portal["reason"] or "ScreenCast interface version 1 or later is unavailable"),
                                       interactive_selection=True, source_enumeration="not exposed before compositor consent"),
            "source.bind": _capability(capture_reason is None, capture_reason, max_active_sessions=1),
            "surface.capture": _capability(capture_reason is None, capture_reason, pixel_format="BGRA8", max_page_bytes=_MAX_FRAME_BYTES,
                                           max_edge=_MAX_FRAME_EDGE, sample_policy="one bounded PipeWire frame"),
            "pointer.absolute": _capability(input_surface_ready and bool(input_devices & 2), capture_reason if not input_surface_ready else "compositor does not advertise pointer input",
                                            method="NotifyPointerMotionAbsolute"),
            "pointer.relative": _capability(input_surface_ready and bool(input_devices & 2), capture_reason if not input_surface_ready else "compositor does not advertise pointer input",
                                            method="NotifyPointerMotion"),
            "pointer.button": _capability(input_surface_ready and bool(input_devices & 2), capture_reason if not input_surface_ready else "compositor does not advertise pointer input",
                                          method="NotifyPointerButton"),
            "pointer.axis": _capability(input_surface_ready and bool(input_devices & 2), capture_reason if not input_surface_ready else "compositor does not advertise pointer input",
                                        method="NotifyPointerAxis"),
            "keyboard.key": _capability(input_surface_ready and bool(input_devices & 1), capture_reason if not input_surface_ready else "compositor does not advertise keyboard input",
                                        method="NotifyKeyboardKeycode/NotifyKeyboardKeysym"),
            "touch.down": _capability(input_surface_ready and bool(input_devices & 4), capture_reason if not input_surface_ready else "compositor does not advertise touchscreen input",
                                      method="NotifyTouchDown"),
            "touch.move": _capability(input_surface_ready and bool(input_devices & 4), capture_reason if not input_surface_ready else "compositor does not advertise touchscreen input",
                                      method="NotifyTouchMotion"),
            "touch.up": _capability(input_surface_ready and bool(input_devices & 4), capture_reason if not input_surface_ready else "compositor does not advertise touchscreen input",
                                    method="NotifyTouchUp"),
            "audio.capture": _capability(False, "ScreenCast streams are visual; this portal adapter has no separately granted audio stream"),
            "accessibility.read": _capability(False, "AT-SPI accessibility is not implemented by this portal adapter"),
            "eis.input": _capability(False, "No libei sender implementation is available; this adapter selects Notify and does not call ConnectToEIS"),
        }
        binding_ready = operations["source.bind"]["status"] == "supported"
        if portal["status"] == "supported":
            if not (int(portal["available_source_types"]) & 7):
                operations["source.list"] = _capability(False, "portal reports no supported monitor, window, or virtual source types")
                operations["source.bind"] = _capability(False, "portal reports no supported ScreenCast source types")
                operations["surface.capture"] = _capability(False, "portal reports no supported ScreenCast source types")
            if not (int(portal["available_cursor_modes"]) & CURSOR_MODES[self.cursor_mode]):
                operations["source.bind"] = _capability(False, f"requested cursor mode {self.cursor_mode!r} is not advertised by this compositor")
                operations["surface.capture"] = _capability(False, f"requested cursor mode {self.cursor_mode!r} is not advertised by this compositor")
            if operations["source.bind"]["status"] != "supported":
                reason = operations["source.bind"]["reason"] or "no bindable ScreenCast session is available"
                for operation in (
                    "pointer.absolute",
                    "pointer.relative",
                    "pointer.button",
                    "pointer.axis",
                    "keyboard.key",
                    "touch.down",
                    "touch.move",
                    "touch.up",
                ):
                    operations[operation] = _capability(False, reason)
            binding_ready = operations["source.bind"]["status"] == "supported"
        binding_ready = binding_ready and capture_reason is None
        return {
            "backend_id": self.backend_id,
            "platform": sys.platform,
            "status": "supported" if binding_ready else "unavailable",
            "reason": None if binding_ready else operations["source.bind"]["reason"],
            "portal": portal,
            "dependencies": dependencies,
            "pipewire_capture": gst_ready,
            "operations": operations,
            "limits": {
                "max_active_sessions": 1,
                "max_frame_bytes": _MAX_FRAME_BYTES,
                "max_frame_edge": _MAX_FRAME_EDGE,
                "capture_timeout_seconds": _MAX_CAPTURE_SECONDS,
                "max_calls_per_dispatch": 1,
                "max_held_keys": _MAX_HELD_KEYS,
                "max_held_buttons": _MAX_HELD_BUTTONS,
                "max_held_touches": _MAX_HELD_TOUCHES,
            },
            "input_method_policy": "Notify methods only; EIS is never mixed with Notify",
            "restore_token_policy": "host-memory only; single-use on restore; never emitted or checkpointed",
        }

    def sources(self) -> list[dict[str, Any]]:
        """List selectable source kinds without guessing compositor surfaces."""
        capabilities = self.describe()
        if capabilities["operations"]["source.list"]["status"] != "supported":
            return []
        available_types = int(capabilities["portal"].get("available_source_types", 0))
        pixel_modality_supported = capabilities["operations"]["surface.capture"]["status"] == "supported"
        choices = [
            {
                "source_id": source_id,
                "source_kind": name,
                "selection": "interactive compositor portal",
                "selectable": True,
                "availability": "not-enumerated-before-consent",
                "identity_status": "not enumerated before consent",
                "cursor_mode": self.cursor_mode,
                "modalities": ["pixels"] if pixel_modality_supported else [],
            }
            for source_id, bit in SOURCE_TYPES.items()
            for name in (_SOURCE_NAMES[bit],)
            if available_types & bit
        ]
        if available_types & 7:
            choices.append({
                "source_id": "portal:any",
                "source_kind": "any advertised monitor/window/virtual type",
                "selection": "interactive compositor portal",
                "selectable": True,
                "availability": "not-enumerated-before-consent",
                "identity_status": "not enumerated before consent",
                "cursor_mode": self.cursor_mode,
                "modalities": ["pixels"] if pixel_modality_supported else [],
            })
        with self._state_lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            alive, reason = self._session_alive(session)
            if not alive:
                session.closed = True
                session.close_reason = reason
                self._close_pipewire_fd(session)
                continue
            stream = session.stream
            choices.append({
                "source_id": session.binding["source_instance"],
                "source_kind": stream.get("source_type_name"),
                "source_instance": session.binding["source_instance"],
                "portal_session_handle": session.handle,
                "portal_stream_id": stream.get("id"),
                "pipewire_node_id": stream.get("node_id"),
                "pipewire_serial": stream.get("pipewire_serial"),
                "selected": True,
                "consent_required": False,
                "availability": "granted-and-live",
                "available": True,
                "modalities": ["pixels"] if pixel_modality_supported and session.pipewire_fd >= 0 else [],
            })
        return choices

    def bind(self, source_id: str) -> dict[str, Any]:
        """Serialize interactive binds so two concurrent dialogs cannot leak sessions."""
        if not self._bind_lock.acquire(blocking=False):
            raise PortalUnavailableError("another portal source bind is already in progress")
        try:
            return self._bind_session(source_id)
        finally:
            self._bind_lock.release()

    def _bind_session(self, source_id: str) -> dict[str, Any]:
        """Ask the compositor to consent, select and bind a real source."""
        if not isinstance(source_id, str):
            raise TypeError("source_id must be a string")
        with self._state_lock:
            if self._closed:
                raise PortalUnavailableError("portal backend is closed")
        capabilities = self.describe()
        if capabilities["operations"]["source.bind"]["status"] != "supported":
            raise PortalUnavailableError(str(capabilities["operations"]["source.bind"]["reason"]))
        source_mask = self._source_mask(source_id, int(capabilities["portal"]["available_source_types"]))
        if not source_mask:
            raise PortalUnavailableError(f"source kind {source_id!r} is not advertised by the compositor")
        with self._state_lock:
            existing_sessions = list(self._sessions.values())
        for existing in existing_sessions:
            with existing.lock:
                alive, reason = self._session_alive(existing)
                if not alive:
                    existing.closed = True
                    existing.close_reason = reason
                    self._close_pipewire_fd(existing)
        with self._state_lock:
            if self._closed:
                raise PortalUnavailableError("portal backend is closed")
            for handle, existing in list(self._sessions.items()):
                if existing.closed:
                    self._sessions.pop(handle, None)
                    self._bindings.pop(str(existing.binding.get("binding_id")), None)
            if self._sessions:
                raise PortalUnavailableError("this backend allows one active portal session; close or revoke it before binding another")
        runtime = self._get_runtime()
        version = int(capabilities["portal"]["remote_desktop_version"])
        if self.persist_mode and version < 2:
            raise PortalUnavailableError("RemoteDesktop persistence requires interface version 2 or later")
        devices = self.requested_devices & int(capabilities["portal"]["available_device_types"])
        if devices != self.requested_devices:
            missing = self.requested_devices & ~int(capabilities["portal"]["available_device_types"])
            raise PortalUnavailableError(f"compositor does not advertise requested RemoteDesktop device mask bits {missing}")
        session_handle: str | None = None
        pipewire_fd: int | None = None
        restore_candidate = self._restore_token
        # A restore token is single-use.  Remove it before sending so failures
        # and retries cannot silently reuse it.
        if restore_candidate:
            self._restore_token = None
        try:
            created = runtime.request(
                _REMOTE_DESKTOP,
                "CreateSession",
                "a{sv}",
                [],
                _variant_map({"session_handle_token": ("s", secrets.token_hex(12))}),
            )
            session_handle = _object_path(created.get("session_handle"), "CreateSession session_handle")
            select_options: dict[str, tuple[str, Any]] = {"types": ("u", devices)}
            if version >= 2:
                select_options["persist_mode"] = ("u", self.persist_mode)
            if restore_candidate:
                if version < 2:
                    raise PortalUnavailableError("RemoteDesktop restore tokens require interface version 2 or later")
                select_options["restore_token"] = ("s", restore_candidate)
            runtime.request(
                _REMOTE_DESKTOP,
                "SelectDevices",
                "oa{sv}",
                [session_handle],
                _variant_map(select_options),
            )
            source_options: dict[str, tuple[str, Any]] = {
                "types": ("u", source_mask),
                "multiple": ("b", False),
            }
            screen_version = int(capabilities["portal"]["screen_cast_version"])
            if screen_version >= 2:
                source_options["cursor_mode"] = ("u", CURSOR_MODES[self.cursor_mode])
            elif self.cursor_mode != "hidden":
                raise PortalUnavailableError("ScreenCast cursor selection requires interface version 2 or later")
            runtime.request(_SCREENCAST, "SelectSources", "oa{sv}", [session_handle], _variant_map(source_options))
            remote_result = runtime.request(_REMOTE_DESKTOP, "Start", "osa{sv}", [session_handle, ""], {})
            granted_devices = int(remote_result.get("devices", 0)) & devices
            streams = _stream_records(remote_result.get("streams"))
            if not streams:
                raise PortalUnavailableError("RemoteDesktop.Start succeeded but returned no PipeWire streams from the selected ScreenCast source")
            stream = streams[0]
            node_id = stream.get("node_id")
            if type(node_id) is not int or node_id < 0:
                raise PortalUnavailableError("portal stream omitted its PipeWire node ID")
            logical_size = stream.get("logical_size") or stream.get("size")
            if logical_size is None:
                raise PortalUnavailableError("portal stream omitted a valid compositor-logical size")
            if logical_size[0] > _MAX_FRAME_EDGE or logical_size[1] > _MAX_FRAME_EDGE:
                raise PortalUnavailableError("portal logical size exceeds the configured coordinate/frame edge limit")
            pipewire_fd = runtime.open_pipewire_remote(session_handle)
            with self._state_lock:
                self._epoch += 1
                epoch = self._epoch
            stream_id = stream.get("id")
            pipewire_serial = stream.get("pipewire_serial")
            stream_identity = (
                f"portal-stream:{stream_id}" if isinstance(stream_id, str) and stream_id else
                f"pipewire-serial:{pipewire_serial}" if type(pipewire_serial) is int else
                f"portal-session:{epoch}:node:{node_id}"
            )
            selected_type = stream.get("source_type")
            selected_name = _SOURCE_NAMES.get(selected_type) if type(selected_type) is int else None
            if selected_name is None:
                selected_name = _single_source_name(source_mask)
            position = stream.get("position")
            if not isinstance(position, (tuple, list)) or len(position) != 2:
                position = None
            else:
                position = [int(position[0]), int(position[1])]
            mapping_id = stream.get("mapping_id") if isinstance(stream.get("mapping_id"), str) else None
            geometry_revision = 1
            binding_id = uuid.uuid4().hex
            frame_size = stream.get("size") or logical_size
            operation_states = {
                "surface.capture": True,
                "pointer.absolute": bool(granted_devices & 2),
                "pointer.relative": bool(granted_devices & 2),
                "pointer.button": bool(granted_devices & 2),
                "pointer.axis": bool(granted_devices & 2),
                "keyboard.key": bool(granted_devices & 1),
                "touch.down": bool(granted_devices & 4),
                "touch.move": bool(granted_devices & 4),
                "touch.up": bool(granted_devices & 4),
                "audio.capture": False,
                "accessibility.read": False,
            }
            binding: dict[str, Any] = {
                "backend_id": self.backend_id,
                "binding_id": binding_id,
                "source_id": source_id,
                "source_instance": stream_identity,
                "source_epoch": epoch,
                "environment_incarnation": self._environment_incarnation,
                "geometry_revision": geometry_revision,
                "width": frame_size[0],
                "height": frame_size[1],
                "logical_size": [logical_size[0], logical_size[1]],
                "coordinate_space": "compositor-logical",
                "backend_version": f"ScreenCast {capabilities['portal']['screen_cast_version']}; RemoteDesktop {version}",
                "operations": [operation for operation, supported in operation_states.items() if supported],
                "operation_states": operation_states,
                "capture_state": "available",
                "modalities": ["pixels"],
                "input_state": "available" if granted_devices else "unavailable",
                "portal_session_handle": session_handle,
                "portal_stream_id": stream_id,
                "pipewire_node_id": node_id,
                "pipewire_serial": pipewire_serial,
                "source_type": selected_type,
                "source_type_name": selected_name,
                "cursor_mode": self.cursor_mode,
                "cursor_mode_value": CURSOR_MODES[self.cursor_mode],
                "position": position,
                "mapping_id": mapping_id,
                "granted_devices": granted_devices,
                "granted_device_names": [name for bit, name in _DEVICE_NAMES.items() if granted_devices & bit],
                "requested_devices": devices,
                "input_method": "notify",
                "portal_versions": {
                    "screen_cast": int(capabilities["portal"]["screen_cast_version"]),
                    "remote_desktop": version,
                },
                "persist_mode": self.persist_mode,
                "bound_at_ns": time.time_ns(),
            }
            session = _PortalSession(
                handle=session_handle,
                source_id=source_id,
                source_mask=source_mask,
                session_epoch=epoch,
                pipewire_fd=pipewire_fd,
                stream=stream,
                binding=binding,
                granted_devices=granted_devices,
                physical_size=frame_size,
            )
            with self._state_lock:
                if self._closed:
                    raise PortalUnavailableError("portal backend closed while the source bind was in progress")
                self._sessions[session_handle] = session
                self._bindings[binding_id] = session
            token = remote_result.get("restore_token")
            if self.persist_mode and isinstance(token, str) and token:
                self._restore_token = token
            return dict(binding)
        except Exception:
            if pipewire_fd is not None:
                try:
                    os.close(pipewire_fd)
                except OSError:
                    pass
            if session_handle is not None:
                try:
                    runtime.close_session(session_handle)
                except Exception:
                    pass
            raise

    def revalidate(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        """Recheck the already-consented session without creating another portal session."""
        try:
            session = self._resolve_binding(binding)
        except PortalUnavailableError as exc:
            return {"supported": True, "valid": False, "detail": str(exc)}
        with session.lock:
            alive, reason = self._session_alive(session)
            if not alive:
                session.closed = True
                session.close_reason = reason
                self._close_pipewire_fd(session)
                return {"supported": True, "valid": False, "detail": reason or "portal session is lost"}
            for key in ("backend_id", "source_id", "source_instance"):
                if binding.get(key) != session.binding.get(key):
                    return {"supported": True, "valid": False, "detail": f"binding {key} does not match the active portal session"}
            current = dict(session.binding)
            current["geometry_revision"] = session.geometry_revision
            if session.physical_size is not None:
                current["width"], current["height"] = session.physical_size
            current["capture_state"] = "available" if session.pipewire_fd >= 0 else "unavailable"
            current["input_state"] = "available" if session.granted_devices else "unavailable"
            current["operations"] = [
                operation for operation, supported in session.binding.get("operation_states", {}).items() if supported
            ]
            current["modalities"] = ["pixels"] if session.pipewire_fd >= 0 else []
            current.update({"supported": True, "valid": True, "detail": "active consent-bound portal session"})
            return current

    def revalidate_target(self, binding: Mapping[str, Any], semantic_target: Any) -> dict[str, Any]:
        """Validate only an explicit exact source-instance target; never infer child objects."""
        current = self.revalidate(binding)
        if not current.get("valid"):
            return {"supported": bool(current.get("supported")), "valid": False, "detail": current.get("detail")}
        source_instance = current["source_instance"]
        if semantic_target is None:
            return {"supported": True, "valid": True, "detail": "intent declares no semantic target"}
        if isinstance(semantic_target, str) and semantic_target == source_instance:
            return {"supported": True, "valid": True, "detail": "semantic target matches the active portal source instance"}
        if isinstance(semantic_target, Mapping) and set(semantic_target) == {"source_instance"}:
            return {
                "supported": True,
                "valid": semantic_target.get("source_instance") == source_instance,
                "detail": "semantic target source_instance matches" if semantic_target.get("source_instance") == source_instance else "semantic target names a different source instance",
            }
        return {
            "supported": False,
            "valid": False,
            "detail": "portal adapter can validate only an exact source_instance; it cannot identify child UI or visual targets",
        }

    def capture(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        """Read exactly one bounded BGRA frame through portal-opened PipeWire."""
        session = self._resolve_binding(binding)
        with session.lock:
            alive, reason = self._session_alive(session)
            if not alive:
                session.closed = True
                session.close_reason = reason
                raise PortalUnavailableError(reason or "portal session is lost")
            session.sequence += 1
            sequence = session.sequence
            try:
                width, height, pixels = self._capture_pipewire_frame(session)
            except Exception as exc:
                raise PortalUnavailableError(f"PipeWire frame capture failed: {_reason(exc)}") from exc
            if session.physical_size is not None and session.physical_size != (width, height):
                session.geometry_revision += 1
            session.physical_size = (width, height)
            session.binding["geometry_revision"] = session.geometry_revision
            session.binding["width"] = width
            session.binding["height"] = height
            return {
                "source_id": session.source_id,
                "source_instance": session.binding["source_instance"],
                "environment_incarnation": self._environment_incarnation,
                "pixels": pixels,
                "modalities": ["pixels"],
                "width": width,
                "height": height,
                "pixel_format": "BGRA8",
                "source_epoch": session.session_epoch,
                "geometry_revision": session.geometry_revision,
                "sequence": sequence,
                "sample_time_ns": None,
                "sample_clock_domain": None,
                "receipt_time_ns": time.monotonic_ns(),
                "receipt_clock_domain": "host-monotonic",
                "coverage": {
                    "complete": True,
                    "missing_regions": [],
                    "unknown_regions": [],
                    "redacted_regions": [],
                    "skipped_intervals": [{"reason": "intermediate-pipewire-frames-not-retained"}],
                    "source": "xdg-desktop-portal ScreenCast",
                    "transport": "portal-opened PipeWire remote",
                    "cursor_mode": session.binding["cursor_mode"],
                    "cursor_in_pixels": session.binding["cursor_mode"] == "embedded",
                    "cursor_metadata": "not decoded" if session.binding["cursor_mode"] == "metadata" else None,
                    "frame_timestamp": "unavailable from gst-launch transport",
                },
            }

    def dispatch(self, binding: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
        """Dispatch exactly one approved common operation via portal Notify."""
        try:
            session = self._resolve_binding(binding)
        except PortalUnavailableError as exc:
            return _dispatch_result("rejected", 0, "none", str(exc))
        if not isinstance(action, Mapping):
            return _dispatch_result("rejected", 0, "none", "action must be a mapping")
        operation = action.get("operation")
        arguments = action.get("arguments")
        if not isinstance(operation, str) or not isinstance(arguments, Mapping):
            return _dispatch_result("rejected", 0, "none", "dispatch requires an operation token and an arguments mapping")
        operation_kinds = {
            "pointer.absolute": "pointer_move_absolute",
            "pointer.relative": "pointer_motion",
            "pointer.button": "pointer_button",
            "pointer.axis": "pointer_axis",
            "touch.down": "touch_down",
            "touch.move": "touch_motion",
            "touch.up": "touch_up",
        }
        kind = operation_kinds.get(operation)
        if operation == "keyboard.key":
            kind = "keyboard_keycode" if "keycode" in arguments else "keyboard_keysym" if "keysym" in arguments else None
        if kind is None:
            return _dispatch_result("rejected", 0, "none", f"unsupported portal operation {operation!r}")
        if session.binding.get("operation_states", {}).get(operation) is not True:
            return _dispatch_result("rejected", 0, "none", f"operation {operation!r} was not granted in this binding")
        normalized = dict(arguments)
        normalized["kind"] = kind
        with session.lock:
            alive, reason = self._session_alive(session)
            if not alive:
                session.closed = True
                session.close_reason = reason
                self._close_pipewire_fd(session)
                return _dispatch_result("rejected", 0, "none", reason or "portal session is lost")
            if binding.get("geometry_revision") != session.geometry_revision:
                return _dispatch_result("rejected", 0, "none", "binding geometry revision is stale; capture again before input")
            if session.input_method != "notify" or binding.get("input_method") != "notify":
                return _dispatch_result("rejected", 0, "none", "input method mismatch; Notify cannot be used in an EIS session")
            try:
                method, signature, options, args, required_device, tracked = self._input_call(session, normalized)
            except (TypeError, ValueError, PortalUnavailableError) as exc:
                return _dispatch_result("rejected", 0, "none", str(exc))
            if not session.granted_devices & required_device:
                return _dispatch_result("rejected", 0, "none", f"portal did not grant required device {_DEVICE_NAMES.get(required_device, required_device)}")
            try:
                self._get_runtime().method(_REMOTE_DESKTOP, method, signature, [session.handle, options, *args])
            except _PortalDBusError as exc:
                return _dispatch_result("rejected", 0, "portal-method-error", f"{exc.name}: {exc.detail}")
            except Exception as exc:
                if tracked is not None:
                    self._track_uncertain(session, tracked)
                return _dispatch_result("unknown", 0, "no-acknowledgment", f"input call outcome is uncertain: {_reason(exc)}")
            if tracked is not None:
                self._track_confirmed(session, tracked)
            return _dispatch_result("delivered", 1, "portal-method-accepted", f"{method} returned successfully; compositor delivery beyond the portal method is not observable")

    def neutralize(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        """Release only controls this backend attempted to hold, without retry loops."""
        try:
            session = self._resolve_binding(binding)
        except PortalUnavailableError as exc:
            return {"confirmed": False, "detail": str(exc)}
        with session.lock:
            alive, reason = self._session_alive(session)
            held = self._held_control_count(session)
            if not alive:
                session.closed = True
                session.close_reason = reason
                self._close_pipewire_fd(session)
                return {
                    "confirmed": held == 0,
                    "detail": (reason or "portal session is lost") if held else "no locally tracked held controls",
                }
            events: list[dict[str, Any]] = []
            events.extend({"operation": "keyboard.key", "arguments": {"keycode": key, "pressed": False}} for key in sorted(session.held_keycodes))
            events.extend({"operation": "keyboard.key", "arguments": {"keysym": key, "pressed": False}} for key in sorted(session.held_keysyms))
            events.extend({"operation": "pointer.button", "arguments": {"button": button, "pressed": False}} for button in sorted(session.held_buttons))
            events.extend({"operation": "touch.up", "arguments": {"slot": slot}} for slot in sorted(session.held_touches))
            failed: list[str] = []
            for event in events:
                operation = event["operation"]
                arguments = event["arguments"]
                kind = "keyboard_keycode" if operation == "keyboard.key" and "keycode" in arguments else (
                    "keyboard_keysym" if operation == "keyboard.key" else
                    "pointer_button" if operation == "pointer.button" else "touch_up"
                )
                try:
                    method, signature, options, args, device, tracked = self._input_call(session, {**arguments, "kind": kind})
                    if not session.granted_devices & device:
                        failed.append(f"{method}: corresponding portal device was not granted")
                        continue
                    self._get_runtime(allow_closed=True).method(_REMOTE_DESKTOP, method, signature, [session.handle, options, *args])
                    if tracked is not None:
                        self._track_confirmed(session, tracked)
                except Exception as exc:
                    failed.append(f"{operation}: {_reason(exc)}")
            remaining = self._held_control_count(session)
            if remaining or failed:
                return {"confirmed": False, "detail": f"released controls where acknowledged; {remaining} may remain held; " + "; ".join(failed)}
            return {"confirmed": True, "detail": f"released {len(events)} backend-tracked controls" if events else "no locally tracked held controls"}

    def revoke(self, binding: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Close one or all portal sessions, invalidating stream and input state."""
        with self._state_lock:
            if binding is None:
                sessions = list(self._sessions.values())
            else:
                try:
                    sessions = [self._resolve_binding(binding)]
                except PortalUnavailableError as exc:
                    return {"revoked": False, "detail": str(exc)}
        results: list[str] = []
        confirmed = True
        for session in sessions:
            with session.lock:
                if session.closed:
                    continue
                try:
                    self._get_runtime(allow_closed=True).close_session(session.handle)
                    results.append(f"closed {session.handle}")
                except Exception as exc:
                    results.append(f"could not close {session.handle}: {_reason(exc)}")
                    confirmed = False
                finally:
                    session.closed = True
                    self._close_pipewire_fd(session)
        return {"revoked": confirmed and all(session.closed for session in sessions), "detail": "; ".join(results) or "no active portal sessions"}

    def close(self) -> None:
        """Release tracked controls, close sessions and discard host-held tokens."""
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            sessions = list(self._sessions.values())
        for session in sessions:
            if not session.closed:
                try:
                    self.neutralize(session.binding)
                except Exception:
                    pass
        for session in sessions:
            with session.lock:
                if not session.closed:
                    try:
                        self._get_runtime(allow_closed=True).close_session(session.handle)
                    except Exception:
                        pass
                    session.closed = True
                self._close_pipewire_fd(session)
        with self._state_lock:
            self._restore_token = None
        with self._runtime_lock:
            if self._runtime is not None:
                self._runtime.close()
                self._runtime = None

    def _dependency_status(self) -> dict[str, Any]:
        linux = sys.platform.startswith("linux")
        wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        dbus_address = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
        platform_reason = None if linux else f"xdg-desktop-portal requires a Linux host; current platform is {sys.platform}"
        wayland_reason = None if wayland and runtime_dir else "a Wayland user session with WAYLAND_DISPLAY and XDG_RUNTIME_DIR is required"
        dbus_module = _DBUS_IMPORT_ERROR is None
        dbus_reason = None if dbus_module else f"optional python package dbus-next is unavailable: {_DBUS_IMPORT_ERROR}"
        bus_ready = bool(dbus_address or (runtime_dir and os.path.exists(os.path.join(runtime_dir, "bus"))))
        bus_reason = None if bus_ready else "the user D-Bus session bus is unavailable (DBUS_SESSION_BUS_ADDRESS or XDG_RUNTIME_DIR/bus is required)"
        portal_ready = linux and wayland and bool(runtime_dir) and dbus_module and bus_ready
        missing_requirements = [reason for reason in (platform_reason, wayland_reason, dbus_reason, bus_reason) if reason]
        portal_reason = "; ".join(missing_requirements) or None
        return {
            "linux": linux,
            "platform_reason": platform_reason,
            "wayland": wayland and bool(runtime_dir),
            "wayland_reason": wayland_reason,
            "dbus_module": dbus_module,
            "dbus_reason": dbus_reason,
            "dbus_session_bus": bus_ready,
            "dbus_bus_reason": bus_reason,
            "portal_ready": portal_ready,
            "missing_requirements": missing_requirements,
            "portal_reason": portal_reason,
        }

    def _probe_gstreamer(self) -> dict[str, Any]:
        with self._runtime_lock:
            if self._gstreamer_checked:
                assert self._gstreamer is not None
                return dict(self._gstreamer)
            self._gstreamer_checked = True
            if not sys.platform.startswith("linux"):
                self._gstreamer = {"ready": False, "reason": "PipeWire capture requires Linux"}
                return dict(self._gstreamer)
            launch = shutil.which("gst-launch-1.0")
            inspect = shutil.which("gst-inspect-1.0")
            if not launch:
                self._gstreamer = {"ready": False, "reason": "GStreamer gst-launch-1.0 is missing; bounded PipeWire capture is unavailable"}
                return dict(self._gstreamer)
            if not inspect:
                self._gstreamer = {"ready": False, "reason": "GStreamer gst-inspect-1.0 is missing; the PipeWire source plugin cannot be verified"}
                return dict(self._gstreamer)
            properties = ""
            for plugin in ("pipewiresrc", "videoconvert", "queue", "fdsink"):
                try:
                    result = subprocess.run([inspect, plugin], capture_output=True, text=True, timeout=3.0, check=False)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    self._gstreamer = {"ready": False, "reason": f"cannot inspect the GStreamer {plugin} plugin: {_reason(exc)}"}
                    return dict(self._gstreamer)
                if result.returncode != 0:
                    detail = (result.stderr or result.stdout or "plugin not found").strip()[:1000]
                    self._gstreamer = {"ready": False, "reason": f"GStreamer {plugin} plugin is unavailable: {detail}"}
                    return dict(self._gstreamer)
                if plugin == "pipewiresrc":
                    properties = result.stdout + "\n" + result.stderr
            has_fd = bool(re.search(r"(?m)^\s*fd\s*:", properties))
            has_path = bool(re.search(r"(?m)^\s*path\s*:", properties))
            target_object = bool(re.search(r"(?m)^\s*target-object\s*:", properties))
            if not has_fd or not has_path:
                missing = ", ".join(name for name, present in (("fd", has_fd), ("path", has_path)) if not present)
                self._gstreamer = {"ready": False, "reason": f"GStreamer pipewiresrc lacks required properties: {missing}"}
            else:
                self._gstreamer = {
                    "ready": True,
                    "reason": None,
                    "gst_launch": launch,
                    "gst_inspect": inspect,
                    "supports_target_object": target_object,
                }
            return dict(self._gstreamer)

    def _get_runtime(self, *, allow_closed: bool = False) -> _PortalLoop:
        with self._runtime_lock:
            if self._closed and not allow_closed:
                raise PortalUnavailableError("portal backend is closed")
            if self._runtime is not None:
                return self._runtime
            dependencies = self._dependency_status()
            if not dependencies["portal_ready"]:
                raise PortalUnavailableError(dependencies["portal_reason"] or "portal runtime is unavailable")
            if _DBUS_IMPORT_ERROR is not None:
                raise PortalUnavailableError(f"python package dbus-next is unavailable: {_DBUS_IMPORT_ERROR}")
            try:
                self._runtime = _PortalLoop(self._request_timeout, self._method_timeout)
            except Exception as exc:
                self._runtime_error = _reason(exc)
                raise PortalUnavailableError(self._runtime_error) from exc
            return self._runtime

    @staticmethod
    def _source_mask(source_id: str, available: int) -> int:
        if source_id == "portal:any":
            return available & 7
        return SOURCE_TYPES.get(source_id, 0) & available

    def _session_alive(self, session: _PortalSession) -> tuple[bool, str | None]:
        if session.closed:
            return False, session.close_reason or "portal session was closed"
        if self._runtime is None:
            return False, "portal D-Bus connection is unavailable"
        try:
            return self._runtime.session_status(session.handle)
        except Exception as exc:
            return False, _reason(exc)

    def _resolve_binding(self, binding: Mapping[str, Any]) -> _PortalSession:
        if not isinstance(binding, Mapping):
            raise PortalUnavailableError("binding must be a mapping returned by this backend")
        binding_id = binding.get("binding_id")
        if not isinstance(binding_id, str):
            raise PortalUnavailableError("binding is missing its opaque backend binding_id")
        with self._state_lock:
            session = self._bindings.get(binding_id)
        if session is None or binding.get("portal_session_handle") != session.handle:
            raise PortalUnavailableError("binding is unknown to this backend or belongs to a different portal session")
        if binding.get("source_epoch") != session.session_epoch or binding.get("environment_incarnation") != self._environment_incarnation:
            raise PortalUnavailableError("binding belongs to an obsolete environment or source epoch")
        return session

    def _capture_pipewire_frame(self, session: _PortalSession) -> tuple[int, int, bytes]:
        gst = self._probe_gstreamer()
        if not gst.get("ready"):
            raise PortalUnavailableError(str(gst.get("reason")))
        stream = session.stream
        target = stream.get("pipewire_serial")
        target_arg = f"target-object={target}" if type(target) is int and gst.get("supports_target_object") else f"path={stream['node_id']}"
        child_fd = os.dup(session.pipewire_fd)
        command = [
            str(gst["gst_launch"]), "-v",
            "pipewiresrc", f"fd={child_fd}", target_arg, "num-buffers=1", "do-timestamp=true",
            "!", "queue", f"max-size-bytes={_MAX_FRAME_BYTES}", "max-size-buffers=1", "max-size-time=0",
            "!", "videoconvert", "!", "video/x-raw,format=BGRA", "!", "fdsink", "fd=1", "sync=false",
        ]
        os.set_inheritable(child_fd, True)
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                pass_fds=(child_fd,),
            )
        except OSError as exc:
            os.close(child_fd)
            raise PortalUnavailableError(f"cannot start bounded PipeWire capture: {_reason(exc)}") from exc
        os.close(child_fd)
        assert process.stdout is not None and process.stderr is not None
        stderr = bytearray()
        stderr_lock = threading.Lock()

        def drain_stderr() -> None:
            while True:
                try:
                    chunk = os.read(process.stderr.fileno(), 8192)
                except OSError:
                    return
                if not chunk:
                    return
                with stderr_lock:
                    remaining = _MAX_STDERR_BYTES - len(stderr)
                    if remaining > 0:
                        stderr.extend(chunk[:remaining])

        stderr_thread = threading.Thread(target=drain_stderr, name="cassi-gst-diagnostics", daemon=True)
        stderr_thread.start()
        output = bytearray()
        deadline = time.monotonic() + _MAX_CAPTURE_SECONDS
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("PipeWire frame did not arrive before the capture deadline")
                ready, _, _ = select.select([process.stdout], [], [], min(remaining, 0.2))
                if not ready:
                    if process.poll() is not None:
                        break
                    continue
                chunk = os.read(process.stdout.fileno(), min(65_536, _MAX_FRAME_BYTES + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > _MAX_FRAME_BYTES:
                    raise PortalUnavailableError(f"PipeWire frame exceeds the {_MAX_FRAME_BYTES}-byte capture page limit")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("PipeWire capture deadline expired while stopping gst-launch")
            process.wait(timeout=remaining)
        except Exception:
            process.kill()
            try:
                process.wait(timeout=1.0)
            except Exception:
                pass
            raise
        finally:
            try:
                process.stdout.close()
            except Exception:
                pass
        stderr_thread.join(timeout=1.0)
        try:
            process.stderr.close()
        except Exception:
            pass
        if process.returncode != 0:
            detail = bytes(stderr).decode("utf-8", "replace").strip()[-2000:]
            raise PortalUnavailableError(f"PipeWire capture pipeline failed with exit status {process.returncode}: {detail or 'no GStreamer diagnostic'}")
        caps = bytes(stderr).decode("utf-8", "replace")
        width, height = _bgra_caps_size(caps)
        if width is None or height is None:
            raise PortalUnavailableError("GStreamer did not report negotiated BGRA frame dimensions")
        if width > _MAX_FRAME_EDGE or height > _MAX_FRAME_EDGE or width * height * 4 > _MAX_FRAME_BYTES:
            raise PortalUnavailableError(f"negotiated frame {width}x{height} exceeds bounded PipeWire page limits")
        expected = width * height * 4
        if len(output) != expected:
            raise PortalUnavailableError(f"PipeWire frame byte count {len(output)} does not match negotiated BGRA size {expected}")
        return width, height, bytes(output)


    def _input_call(
        self, session: _PortalSession, action: Mapping[str, Any]
    ) -> tuple[str, str, dict[str, Any], list[Any], int, tuple[str, int, bool] | None]:
        kind = action.get("kind")
        if not isinstance(kind, str):
            raise TypeError("action.kind must name one portal input event")
        empty_options: dict[str, Any] = {}
        if kind == "pointer_motion":
            dx = _bounded_number(action.get("dx"), "dx", _MAX_INPUT_DELTA)
            dy = _bounded_number(action.get("dy"), "dy", _MAX_INPUT_DELTA)
            return "NotifyPointerMotion", "oa{sv}dd", empty_options, [dx, dy], 2, None
        if kind == "pointer_move_absolute":
            x = _bounded_number(action.get("x"), "x", float(session.binding["logical_size"][0]))
            y = _bounded_number(action.get("y"), "y", float(session.binding["logical_size"][1]))
            if x < 0 or y < 0:
                raise ValueError("absolute pointer coordinates must be inside the selected stream")
            stream = action.get("stream", session.binding["pipewire_node_id"])
            if type(stream) is not int or stream != session.binding["pipewire_node_id"]:
                raise ValueError("absolute pointer event must identify this bound PipeWire stream")
            return "NotifyPointerMotionAbsolute", "oa{sv}udd", empty_options, [stream, x, y], 2, None
        if kind == "pointer_button":
            button = _integer(action.get("button"), "button", 1, 767)
            pressed = _boolean(action.get("pressed"), "pressed")
            if pressed and button not in session.held_buttons and len(session.held_buttons) >= _MAX_HELD_BUTTONS:
                raise ValueError("backend held-pointer-button limit reached")
            return "NotifyPointerButton", "oa{sv}iu", empty_options, [button, 1 if pressed else 0], 2, ("button", button, pressed)
        if kind == "pointer_axis":
            dx = _bounded_number(action.get("dx", 0), "dx", _MAX_INPUT_DELTA)
            dy = _bounded_number(action.get("dy", 0), "dy", _MAX_INPUT_DELTA)
            finish = _boolean(action.get("finish", False), "finish")
            options = _variant_map({"finish": ("b", finish)}) if finish else empty_options
            return "NotifyPointerAxis", "oa{sv}dd", options, [dx, dy], 2, None
        if kind == "keyboard_keycode":
            keycode = _integer(action.get("keycode"), "keycode", 0, 767)
            pressed = _boolean(action.get("pressed"), "pressed")
            if pressed and keycode not in session.held_keycodes and len(session.held_keycodes) >= _MAX_HELD_KEYS:
                raise ValueError("backend held-keycode limit reached")
            return "NotifyKeyboardKeycode", "oa{sv}iu", empty_options, [keycode, 1 if pressed else 0], 1, ("keycode", keycode, pressed)
        if kind == "keyboard_keysym":
            keysym = _integer(action.get("keysym"), "keysym", 0, 0x1FFFFFFF)
            pressed = _boolean(action.get("pressed"), "pressed")
            if pressed and keysym not in session.held_keysyms and len(session.held_keysyms) >= _MAX_HELD_KEYS:
                raise ValueError("backend held-keysym limit reached")
            return "NotifyKeyboardKeysym", "oa{sv}iu", empty_options, [keysym, 1 if pressed else 0], 1, ("keysym", keysym, pressed)
        if kind in ("touch_down", "touch_motion"):
            slot = _integer(action.get("slot"), "slot", 0, 31)
            x = _bounded_number(action.get("x"), "x", float(session.binding["logical_size"][0]))
            y = _bounded_number(action.get("y"), "y", float(session.binding["logical_size"][1]))
            if x < 0 or y < 0:
                raise ValueError("touch coordinates must be inside the selected stream")
            if kind == "touch_down" and slot not in session.held_touches and len(session.held_touches) >= _MAX_HELD_TOUCHES:
                raise ValueError("backend held-touch limit reached")
            method = "NotifyTouchDown" if kind == "touch_down" else "NotifyTouchMotion"
            tracked = ("touch", slot, True) if kind == "touch_down" else None
            return method, "oa{sv}uudd", empty_options, [session.binding["pipewire_node_id"], slot, x, y], 4, tracked
        if kind == "touch_up":
            slot = _integer(action.get("slot"), "slot", 0, 31)
            return "NotifyTouchUp", "oa{sv}u", empty_options, [slot], 4, ("touch", slot, False)
        raise ValueError(f"unsupported portal input action kind {kind!r}")

    @staticmethod
    def _track_confirmed(session: _PortalSession, tracked: tuple[str, int, bool]) -> None:
        kind, value, pressed = tracked
        if kind == "keycode":
            target = session.held_keycodes
        elif kind == "keysym":
            target = session.held_keysyms
        elif kind == "button":
            target = session.held_buttons
        elif kind == "touch":
            target = session.held_touches
        else:
            return
        if pressed:
            target.add(value)
        else:
            target.discard(value)

    @staticmethod
    def _track_uncertain(session: _PortalSession, tracked: tuple[str, int, bool]) -> None:
        kind, value, pressed = tracked
        if not pressed:
            return
        if kind == "keycode":
            session.held_keycodes.add(value)
        elif kind == "keysym":
            session.held_keysyms.add(value)
        elif kind == "button":
            session.held_buttons.add(value)
        elif kind == "touch":
            session.held_touches.add(value)


    @staticmethod
    def _held_control_count(session: _PortalSession) -> int:
        return len(session.held_keycodes) + len(session.held_keysyms) + len(session.held_buttons) + len(session.held_touches)

    @staticmethod
    def _close_pipewire_fd(session: _PortalSession) -> None:
        if session.pipewire_fd >= 0:
            try:
                os.close(session.pipewire_fd)
            except OSError:
                pass
            session.pipewire_fd = -1




def _stream_records(value: Any) -> list[dict[str, Any]]:
    value = _plain(value)
    if not isinstance(value, (tuple, list)):
        return []
    records: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            continue
        node_id, properties = item
        if not isinstance(properties, dict):
            continue
        raw_size = properties.get("size")
        size = _positive_size(raw_size)
        logical_size = _positive_size(properties.get("logical_size")) or size
        source_type = properties.get("source_type")
        serial = properties.get("pipewire-serial")
        type_value = int(source_type) if type(source_type) is int else None
        records.append({
            "node_id": int(node_id) if type(node_id) is int else None,
            "properties": properties,
            "id": properties.get("id") if isinstance(properties.get("id"), str) else None,
            "size": size,
            "logical_size": logical_size,
            "position": properties.get("logical_position", properties.get("position")),
            "source_type": type_value,
            "source_type_name": _SOURCE_NAMES.get(type_value),
            "pipewire_serial": int(serial) if type(serial) is int else None,
            "mapping_id": properties.get("mapping_id"),
        })
    return records


def _single_source_name(mask: int) -> str | None:
    if mask in _SOURCE_NAMES:
        return _SOURCE_NAMES[mask]
    return None


def _object_path(value: Any, name: str) -> str:
    value = _plain(value)
    if not isinstance(value, str) or not value.startswith("/"):
        raise PortalUnavailableError(f"portal response omitted a valid {name}")
    return value


def _bgra_caps_size(caps_log: str) -> tuple[int | None, int | None]:
    for line in caps_log.splitlines():
        if "video/x-raw" not in line or "BGRA" not in line:
            continue
        width = re.search(r"\bwidth=\(int\)(\d+)", line) or re.search(r"\bwidth=(\d+)", line)
        height = re.search(r"\bheight=\(int\)(\d+)", line) or re.search(r"\bheight=(\d+)", line)
        if width and height:
            return int(width.group(1)), int(height.group(1))
    return None, None


def _bounded_number(value: Any, name: str, limit: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number) or abs(number) > limit:
        raise ValueError(f"{name} must be finite and within +/-{limit:g}")
    return number


def _integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        raise ValueError(f"{name} must be an integer from {minimum} through {maximum}")
    return value


def _boolean(value: Any, name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{name} must be a boolean")
    return value


def _capability(supported: bool, reason: str | None, **details: Any) -> dict[str, Any]:
    result = {"status": "supported" if supported else "unavailable", "reason": None if supported else reason}
    result.update(details)
    return result


def _dispatch_result(disposition: str, delivered_count: int, ack_strength: str, detail: str) -> dict[str, Any]:
    return {
        "disposition": disposition,
        "delivered_count": delivered_count,
        "ack_strength": ack_strength,
        "detail": detail,
    }


def _reason(exc: BaseException) -> str:
    text = str(exc).strip()
    return text if text else type(exc).__name__


# A short spelling eases registry integrations without hiding the platform.
PortalBackend = LinuxPortalBackend
