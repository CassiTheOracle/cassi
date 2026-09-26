"""Bounded, foreground-fenced XInput sampling for PCSX2 gameplay.

Injected APIs implement ``foreground_process()`` returning ``(basename, pid)``
(or ``None`` when it cannot be determined), ``read_xinput(slot)`` returning
``None`` for a disconnected controller or a mapping containing exactly the raw
XInput fields documented by :class:`XInputSource`, and
``tcp_listener_pids(port)`` returning the process owners of a local listener.
This tiny seam keeps tests independent of Windows and makes focus and endpoint
fencing observable.
"""

from __future__ import annotations

import ctypes
import ipaddress
import ntpath
import socket
import sys
from collections.abc import Mapping
from typing import Any


class GameplayInputError(RuntimeError):
    """Raised when the requested XInput state is unavailable or malformed."""


class GameplayFocusLost(GameplayInputError):
    """Raised when the exact bound PCSX2 process is not foreground-focused."""


# Stable XInput button order; masks follow XINPUT_GAMEPAD_* definitions.
_BUTTONS = (
    (0x0001, "dpad_up"),
    (0x0002, "dpad_down"),
    (0x0004, "dpad_left"),
    (0x0008, "dpad_right"),
    (0x0010, "start"),
    (0x0020, "back"),
    (0x0040, "left_thumb"),
    (0x0080, "right_thumb"),
    (0x0100, "left_shoulder"),
    (0x0200, "right_shoulder"),
    (0x1000, "a"),
    (0x2000, "b"),
    (0x4000, "x"),
    (0x8000, "y"),
)
_RAW_FIELDS = frozenset((
    "packet_number",
    "buttons",
    "left_trigger",
    "right_trigger",
    "left_stick_x",
    "left_stick_y",
    "right_stick_x",
    "right_stick_y",
))
_STATE_FIELDS = _RAW_FIELDS | {"pressed"}
_UINT32_MAX = 0xFFFFFFFF


def _integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise GameplayInputError(f"Malformed XInput field: {field}.")
    return value


def _basename(value: Any) -> str | None:
    if type(value) is not str or not value or len(value) > 255:
        return None
    if value in (".", "..") or any(
        char in value for char in ('<', '>', ':', '"', '/', "\\", '|', '?', '*', "\0")
    ):
        return None
    if any(ord(char) < 32 for char in value):
        return None
    return value


def _decode_raw(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != _RAW_FIELDS:
        raise GameplayInputError("Malformed XInput state.")
    packet = _integer(raw["packet_number"], "packet_number", 0, _UINT32_MAX)
    buttons = _integer(raw["buttons"], "buttons", 0, 0xFFFF)
    left_trigger = _integer(raw["left_trigger"], "left_trigger", 0, 0xFF)
    right_trigger = _integer(raw["right_trigger"], "right_trigger", 0, 0xFF)
    left_stick_x = _integer(raw["left_stick_x"], "left_stick_x", -0x8000, 0x7FFF)
    left_stick_y = _integer(raw["left_stick_y"], "left_stick_y", -0x8000, 0x7FFF)
    right_stick_x = _integer(raw["right_stick_x"], "right_stick_x", -0x8000, 0x7FFF)
    right_stick_y = _integer(raw["right_stick_y"], "right_stick_y", -0x8000, 0x7FFF)
    pressed = [name for mask, name in _BUTTONS if buttons & mask]
    return {
        "packet_number": packet,
        "buttons": buttons,
        "pressed": pressed,
        "left_trigger": left_trigger,
        "right_trigger": right_trigger,
        "left_stick_x": left_stick_x,
        "left_stick_y": left_stick_y,
        "right_stick_x": right_stick_x,
        "right_stick_y": right_stick_y,
    }


def _validated_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, Mapping) or set(state) != _STATE_FIELDS:
        raise GameplayInputError("Malformed gameplay input state.")
    raw = {field: state[field] for field in _RAW_FIELDS}
    decoded = _decode_raw(raw)
    pressed = state["pressed"]
    if not isinstance(pressed, list) or any(type(name) is not str for name in pressed):
        raise GameplayInputError("Malformed gameplay input field: pressed.")
    if pressed != decoded["pressed"]:
        raise GameplayInputError("Inconsistent gameplay input field: pressed.")
    return decoded


class _XInputState(ctypes.Structure):
    _fields_ = (
        ("packet_number", ctypes.c_uint32),
        ("buttons", ctypes.c_uint16),
        ("left_trigger", ctypes.c_uint8),
        ("right_trigger", ctypes.c_uint8),
        ("left_stick_x", ctypes.c_int16),
        ("left_stick_y", ctypes.c_int16),
        ("right_stick_x", ctypes.c_int16),
        ("right_stick_y", ctypes.c_int16),
    )


class _MibTcpRowOwnerPid(ctypes.Structure):
    _fields_ = [
        ("state", ctypes.c_uint32),
        ("local_address", ctypes.c_uint32),
        ("local_port", ctypes.c_uint32),
        ("remote_address", ctypes.c_uint32),
        ("remote_port", ctypes.c_uint32),
        ("owning_pid", ctypes.c_uint32),
    ]


class _Win32XInputAPI:
    """Private ctypes adapter; no Windows DLLs are loaded at module import."""

    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _ERROR_DEVICE_NOT_CONNECTED = 1167

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise GameplayInputError("XInput gameplay capture is available only on Windows.")

        try:
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            self._iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
        except (AttributeError, OSError):
            raise GameplayInputError("Windows process APIs are unavailable.") from None

        self._user32.GetForegroundWindow.argtypes = ()
        self._user32.GetForegroundWindow.restype = ctypes.c_void_p
        self._user32.GetWindowThreadProcessId.argtypes = (
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
        )
        self._user32.GetWindowThreadProcessId.restype = ctypes.c_uint32
        self._kernel32.OpenProcess.argtypes = (
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint32,
        )
        self._kernel32.OpenProcess.restype = ctypes.c_void_p
        self._kernel32.QueryFullProcessImageNameW.argtypes = (
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_wchar),
            ctypes.POINTER(ctypes.c_uint32),
        )
        self._kernel32.QueryFullProcessImageNameW.restype = ctypes.c_int
        self._kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        self._kernel32.CloseHandle.restype = ctypes.c_int

        self._xinput = self._load_xinput()
        self._xinput.XInputGetState.argtypes = (
            ctypes.c_uint32,
            ctypes.POINTER(_XInputState),
        )
        self._xinput.XInputGetState.restype = ctypes.c_uint32
        self._iphlpapi.GetExtendedTcpTable.argtypes = (
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_int,
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint32,
        )
        self._iphlpapi.GetExtendedTcpTable.restype = ctypes.c_uint32

    @staticmethod
    def _load_xinput() -> Any:
        for name in ("xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll"):
            try:
                library = ctypes.WinDLL(name, use_last_error=True)
                getattr(library, "XInputGetState")
                return library
            except (AttributeError, OSError):
                continue
        raise GameplayInputError("No supported XInput library is available.")

    def foreground_process(self) -> tuple[str, int] | None:
        window = self._user32.GetForegroundWindow()
        if not window:
            return None
        pid = ctypes.c_uint32()
        if not self._user32.GetWindowThreadProcessId(window, ctypes.byref(pid)) or not pid.value:
            return None
        process = self._kernel32.OpenProcess(
            self._PROCESS_QUERY_LIMITED_INFORMATION,
            0,
            pid.value,
        )
        if not process:
            return None
        try:
            image = ctypes.create_unicode_buffer(32768)
            length = ctypes.c_uint32(len(image))
            if not self._kernel32.QueryFullProcessImageNameW(
                process,
                0,
                image,
                ctypes.byref(length),
            ):
                return None
            process_name = ntpath.basename(image.value)
            if not process_name:
                return None
            return process_name, int(pid.value)
        finally:
            self._kernel32.CloseHandle(process)

    def read_xinput(self, slot: int) -> dict[str, int] | None:
        state = _XInputState()
        result = int(self._xinput.XInputGetState(slot, ctypes.byref(state)))
        if result == self._ERROR_DEVICE_NOT_CONNECTED:
            return None
        if result != 0:
            raise GameplayInputError("XInput state query failed.")
        return {
            "packet_number": int(state.packet_number),
            "buttons": int(state.buttons),
            "left_trigger": int(state.left_trigger),
            "right_trigger": int(state.right_trigger),
            "left_stick_x": int(state.left_stick_x),
            "left_stick_y": int(state.left_stick_y),
            "right_stick_x": int(state.right_stick_x),
            "right_stick_y": int(state.right_stick_y),
        }

    def tcp_listener_pids(self, port: int) -> tuple[int, ...]:
        """Return the process owners of IPv4 listeners on one local TCP port."""
        size = ctypes.c_uint32(0)
        result = int(self._iphlpapi.GetExtendedTcpTable(
            None, ctypes.byref(size), False, 2, 3, 0,
        ))
        if result not in (0, 122):
            raise GameplayInputError("Windows TCP listener ownership is unavailable.")
        if size.value == 0:
            return ()
        table = ctypes.create_string_buffer(size.value)
        result = int(self._iphlpapi.GetExtendedTcpTable(
            table, ctypes.byref(size), False, 2, 3, 0,
        ))
        if result != 0:
            raise GameplayInputError("Windows TCP listener ownership query failed.")
        count = ctypes.c_uint32.from_buffer_copy(table.raw).value
        row_size = ctypes.sizeof(_MibTcpRowOwnerPid)
        if ctypes.sizeof(ctypes.c_uint32) + count * row_size > len(table):
            raise GameplayInputError("Windows returned a malformed TCP listener table.")
        owners: set[int] = set()
        for index in range(count):
            offset = ctypes.sizeof(ctypes.c_uint32) + index * row_size
            row = _MibTcpRowOwnerPid.from_buffer_copy(table.raw, offset)
            if socket.ntohs(int(row.local_port) & 0xFFFF) == port:
                owners.add(int(row.owning_pid))
        return tuple(sorted(owners))


class XInputSource:
    """Sample one controller only while the bound PCSX2 PID is foreground.

    ``api`` is an optional test/integration seam with three methods:
    ``foreground_process() -> (basename, pid) | None``,
    ``read_xinput(slot) -> mapping | None``, and
    ``tcp_listener_pids(port) -> iterable[int]``. A non-``None`` raw mapping must
    contain exactly ``packet_number``, ``buttons``, ``left_trigger``,
    ``right_trigger``, ``left_stick_x``, ``left_stick_y``, ``right_stick_x``,
    and ``right_stick_y``. ``None`` means disconnected. Values are range
    checked before a JSON-safe state is returned.
    """

    def __init__(
        self,
        slot: int = 0,
        expected_process: str = "pcsx2-qt.exe",
        api: Any | None = None,
    ) -> None:
        if type(slot) is not int or not 0 <= slot <= 3:
            raise ValueError("XInput slot must be an integer from 0 through 3.")
        process_name = _basename(expected_process)
        if process_name is None:
            raise ValueError("expected_process must be a bounded process basename.")
        if api is None:
            api = _Win32XInputAPI()
        if (
            not callable(getattr(api, "foreground_process", None))
            or not callable(getattr(api, "read_xinput", None))
            or not callable(getattr(api, "tcp_listener_pids", None))
        ):
            raise TypeError(
                "api must provide foreground_process(), read_xinput(slot), "
                "and tcp_listener_pids(port)."
            )

        self.slot = slot
        self.expected_process = process_name
        self._api = api
        self._bound_pid: int | None = None

    def describe(self) -> dict[str, Any]:
        """Return fixed, path-free source identity and the current session PID."""
        return {
            "backend": "windows-xinput",
            "process": self.expected_process,
            "slot": self.slot,
            "pid": self._bound_pid,
        }

    def _foreground(self) -> tuple[str, int] | None:
        try:
            candidate = self._api.foreground_process()
        except Exception:
            return None
        if candidate is None or not isinstance(candidate, tuple) or len(candidate) != 2:
            return None
        name = _basename(candidate[0])
        pid = candidate[1]
        if name is None or type(pid) is not int or not 1 <= pid <= _UINT32_MAX:
            return None
        return name, pid

    def _is_expected_process(self, process: tuple[str, int] | None) -> bool:
        return (
            process is not None
            and self._bound_pid is not None
            and process[1] == self._bound_pid
            and process[0].casefold() == self.expected_process.casefold()
        )

    def begin_session(self) -> dict[str, Any]:
        """Bind this source to the currently foreground PCSX2 process PID."""
        if self._bound_pid is not None:
            raise GameplayInputError("An XInput session is already active.")
        process = self._foreground()
        if (
            process is None
            or process[0].casefold() != self.expected_process.casefold()
        ):
            raise GameplayFocusLost("The expected PCSX2 process is not foreground.")
        self._bound_pid = process[1]
        return self.describe()

    def assert_foreground(self) -> None:
        """Verify that the active session's exact PCSX2 PID still owns focus."""
        if self._bound_pid is None:
            raise GameplayInputError("No XInput session is active.")
        if not self._is_expected_process(self._foreground()):
            raise GameplayFocusLost("The bound PCSX2 process is no longer foreground.")


    def assert_pine_endpoint(self, host: str, port: int) -> None:
        """Verify that a local PINE listener belongs to the bound foreground PID."""
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise GameplayInputError(
                "Gameplay capture requires a literal IPv4 loopback PINE host."
            ) from exc
        if address.version != 4 or not address.is_loopback:
            raise GameplayInputError(
                "Gameplay capture requires a literal IPv4 loopback PINE host."
            )
        if type(port) is not int or not 1 <= port <= 65_535:
            raise GameplayInputError("The PINE listener port is invalid.")
        self.assert_foreground()
        try:
            owners = self._api.tcp_listener_pids(port)
        except GameplayInputError:
            raise
        except Exception as exc:
            raise GameplayInputError(
                "PINE listener ownership could not be inspected."
            ) from exc
        self.assert_foreground()
        if (
            not isinstance(owners, (list, tuple, set, frozenset))
            or any(type(pid) is not int or not 1 <= pid <= _UINT32_MAX for pid in owners)
            or set(owners) != {self._bound_pid}
        ):
            raise GameplayInputError(
                "The PINE listener is not owned by the bound PCSX2 process."
            )

    def sample(self) -> dict[str, Any]:
        """Read and validate one state, fenced by exact foreground PID checks."""
        self.assert_foreground()
        raw: Any = None
        read_error: Exception | None = None
        try:
            raw = self._api.read_xinput(self.slot)
        except Exception as error:
            read_error = error

        # This check is unconditional: even a failed or malformed poll is fenced.
        self.assert_foreground()
        if read_error is not None:
            raise GameplayInputError("XInput state query failed.") from None
        if raw is None:
            raise GameplayInputError("The XInput controller is disconnected.")
        return _decode_raw(raw)

    def end_session(self) -> None:
        """Clear the PID binding; safe to call more than once."""
        self._bound_pid = None


def meaningful_transitions(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return ordered digital edges and analog changes across quantized bins.

    Trigger bins are 16 raw units wide; stick bins are 4096 raw units wide.
    Transition ``previous``/``current`` values retain the original raw values.
    A missing baseline (or current state) intentionally emits no transitions.
    """
    if previous is None or current is None:
        return []
    before = _validated_state(previous)
    after = _validated_state(current)
    transitions: list[dict[str, Any]] = []

    for mask, name in _BUTTONS:
        old_value = 1 if before["buttons"] & mask else 0
        new_value = 1 if after["buttons"] & mask else 0
        if old_value != new_value:
            transitions.append({
                "control": name,
                "kind": "press" if new_value else "release",
                "previous": old_value,
                "current": new_value,
            })

    analog_fields = (
        "left_trigger",
        "right_trigger",
        "left_stick_x",
        "left_stick_y",
        "right_stick_x",
        "right_stick_y",
    )
    for field in analog_fields:
        old_value = before[field]
        new_value = after[field]
        bin_width = 16 if field.endswith("trigger") else 4096
        if old_value // bin_width != new_value // bin_width:
            transitions.append({
                "control": field,
                "kind": "change",
                "previous": old_value,
                "current": new_value,
            })
    return transitions
