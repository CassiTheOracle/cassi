"""Surface broker adapter for a visible ConPTY text screen.

This backend publishes only the terminal viewport produced by the VT screen
model.  It has no native-pixel claim and never consults game state outside that
visible viewport.  Input is a bounded keyboard.text effect dispatched through
the owning SurfaceBroker.
"""
from __future__ import annotations

import math
import threading
import time
from typing import Any, Mapping
from uuid import uuid4

from games.terminal import ScreenFrame, TerminalError, TerminalSession
from games.world import WorldError

MAX_TERMINAL_TEXT_BYTES = 1 << 20
MAX_KEYBOARD_TEXT_BYTES = 128
MAX_SEND_QUIET_SECONDS = 5.0
MAX_SEND_IDLE_SECONDS = 30.0
MAX_SEND_TIMEOUT_SECONDS = 30.0


class SurfaceTerminalError(WorldError):
    """A Surface-mediated terminal action failed or has an unknown outcome."""


class SurfaceTerminalBackend:
    """A source-bound structural capture and keyboard backend for one game."""

    def __init__(self, world_name: str, *, cols: int, rows: int) -> None:
        nonce = uuid4().hex
        self.backend_id = f"conpty-game-{nonce}"
        self.source_id = f"games.{world_name}.terminal.{nonce[:12]}"
        self.input_domain = f"{self.backend_id}.keyboard"
        self._environment_incarnation = f"conpty-env-{nonce}"
        self._source_instance = ""
        self._source_epoch = 0
        self._geometry_revision = 0
        self._cols = int(cols)
        self._rows = int(rows)
        self._sequence = 0
        self._session: TerminalSession | None = None
        self._send_token: object | None = None
        self._last_frame: ScreenFrame | None = None
        self._binding: dict[str, Any] | None = None
        self._lock = threading.RLock()
        self._closed = False

    def describe(self) -> dict[str, Any]:
        return {
            "name": "ConPTY visible terminal",
            "capture": "structural-text",
            "modalities": ["accessibility"],
            "native_pixels": False,
            "input": "brokered-keyboard-text",
            "version": "1",
        }

    def sources(self) -> list[dict[str, Any]]:
        with self._lock:
            if self._session is None or self._closed:
                return []
            return [self._source_descriptor()]

    def attach(self, session: TerminalSession, send_token: object) -> None:
        with self._lock:
            if self._closed:
                raise SurfaceTerminalError("ConPTY backend is closed")
            if self._session is not None:
                raise SurfaceTerminalError("ConPTY backend already owns a session")
            self._session = session
            self._send_token = send_token
            self._source_instance = f"conpty-{uuid4().hex}"
            self._source_epoch += 1
            self._sequence = 0
            self._last_frame = None
            self._binding = None

    def detach(self, session: TerminalSession) -> None:
        with self._lock:
            if self._session is session:
                self._session = None
                self._send_token = None
                self._binding = None
                self._last_frame = None

    def bind(self, source_id: str) -> dict[str, Any]:
        with self._lock:
            if self._closed or self._session is None:
                raise SurfaceTerminalError("ConPTY session is unavailable")
            if source_id != self.source_id:
                raise SurfaceTerminalError("unknown ConPTY source")
            descriptor = self._source_descriptor()
            self._binding = descriptor
            return dict(descriptor)

    def revalidate(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        """Report the current source identity/capability without rebinding it."""
        with self._lock:
            current = self._binding
            descriptor = self._source_descriptor() if self._session is not None else {
                "backend_id": self.backend_id,
                "source_id": self.source_id,
                "source_instance": self._source_instance,
                "source_epoch": self._source_epoch,
                "environment_incarnation": self._environment_incarnation,
                "geometry_revision": self._geometry_revision,
                "width": 0,
                "height": 0,
                "operations": ["keyboard.text"],
                "modalities": ["accessibility"],
                "capture_state": "unavailable",
                "input_state": "unavailable",
                "backend_version": "1",
                "input_domain": self.input_domain,
                "input_domain_epoch": max(0, self._source_epoch - 1),
                "focus_epoch": 0,
            }
            valid = (
                not self._closed
                and current is not None
                and all(
                    binding.get(key) == current.get(key)
                    for key in (
                        "source_id",
                        "source_instance",
                        "source_epoch",
                        "environment_incarnation",
                        "geometry_revision",
                    )
                )
            )
            result = dict(descriptor)
            result["supported"] = True
            result["valid"] = valid
            if not valid:
                result["reason"] = "ConPTY binding no longer identifies the active terminal session"
            return result

    def capture(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            session = self._session
            current = self._binding
            if self._closed or session is None or current is None:
                raise SurfaceTerminalError("ConPTY source is detached")
            self._require_current_binding(binding, current)
            frame = session.frame()
            self._sequence += 1
            sequence = self._sequence
            self._last_frame = frame
            sample_time_ns = time.monotonic_ns()
            receipt_time_ns = time.monotonic_ns()
            text = frame.text
            if len(text.encode("utf-8")) > MAX_TERMINAL_TEXT_BYTES:
                raise SurfaceTerminalError("visible terminal text exceeds the structural capture limit")
            return {
                "source_id": self.source_id,
                "source_instance": self._source_instance,
                "source_epoch": self._source_epoch,
                "environment_incarnation": self._environment_incarnation,
                "geometry_revision": self._geometry_revision,
                "sequence": sequence,
                "width": 0,
                "height": 0,
                "pixel_format": "none",
                "screen_text": text,
                "accessibility": {
                    "role": "terminal",
                    "rows": self._rows,
                    "columns": self._cols,
                    "cursor": {"row": frame.cursor[1], "column": frame.cursor[0]},
                    "screen_revision": frame.revision,
                },
                "accessibility_sample_time_ns": sample_time_ns,
                "sample_time_ns": sample_time_ns,
                "sample_clock_domain": "python-monotonic-ns",
                "receipt_time_ns": receipt_time_ns,
                "receipt_clock_domain": "python-monotonic-ns",
                "coverage": {
                    "complete": True,
                    "missing_regions": [],
                    "unknown_regions": [],
                    "redacted_regions": [],
                    "kind": "complete-terminal-viewport",
                    "rows": self._rows,
                    "columns": self._cols,
                    "truncated": False,
                },
                "provenance": "ConPTY VT screen model; visible terminal text only; native pixels unavailable",
            }

    def last_frame(self) -> ScreenFrame:
        with self._lock:
            if self._last_frame is None:
                raise SurfaceTerminalError("no terminal frame has been captured")
            return self._last_frame

    def dispatch(self, binding: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            session = self._session
            current = self._binding
            token = self._send_token
            if self._closed or session is None or current is None or token is None:
                return self._outcome("not-started", 0, "none", "ConPTY source is detached")
            try:
                self._require_current_binding(binding, current)
            except SurfaceTerminalError as exc:
                return self._outcome("not-started", 0, "none", str(exc))
            if action.get("operation") != "keyboard.text":
                return self._outcome("rejected", 0, "none", "only keyboard.text is supported")
            arguments = action.get("arguments")
            if not isinstance(arguments, Mapping) or set(arguments) != {"text", "quiet", "idle", "timeout"}:
                return self._outcome("rejected", 0, "none", "keyboard.text arguments are invalid")
            text = arguments.get("text")
            if not isinstance(text, str) or not text or "\x00" in text:
                return self._outcome("rejected", 0, "none", "keyboard text must be nonempty and contain no NUL")
            try:
                byte_count = len(text.encode("utf-8"))
            except UnicodeEncodeError:
                return self._outcome("rejected", 0, "none", "keyboard text must be valid UTF-8")
            if byte_count > MAX_KEYBOARD_TEXT_BYTES:
                return self._outcome("rejected", 0, "none", "keyboard text exceeds the per-action byte limit")
            quiet = self._seconds(arguments.get("quiet"), "quiet", MAX_SEND_QUIET_SECONDS)
            idle = self._seconds(arguments.get("idle"), "idle", MAX_SEND_IDLE_SECONDS)
            timeout = self._seconds(arguments.get("timeout"), "timeout", MAX_SEND_TIMEOUT_SECONDS)
            if quiet is None or idle is None or timeout is None:
                return self._outcome("rejected", 0, "none", "keyboard timing bounds are invalid")
            if not session.accepting_input:
                return self._outcome("not-started", 0, "none", "ConPTY session is no longer accepting input")
            try:
                session._send_from_surface(
                    token,
                    text,
                    quiet=quiet,
                    idle=idle,
                    timeout=timeout,
                )
            except TerminalError:
                # Dispatch has begun.  The broker must retain this as unknown
                # rather than replaying a text stream whose delivery is unclear.
                raise
            return self._outcome(
                "delivered",
                byte_count,
                "conpty-write-returned",
                {"status": "acknowledged", "actual_count": byte_count, "source_epoch": self._source_epoch},
            )

    def neutralize(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self._binding
            if current is None:
                return {"confirmed": True, "detail": "detached ConPTY has no held key state"}
            try:
                self._require_current_binding(binding, current)
            except SurfaceTerminalError as exc:
                return {"confirmed": False, "detail": str(exc)}
            # keyboard.text is a one-shot ConPTY byte write, not a held key-down
            # state. The broker serializes this method against dispatch.
            return {"confirmed": True, "detail": "no persistent ConPTY key state"}

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._session = None
            self._send_token = None
            self._binding = None
            self._last_frame = None

    def _source_descriptor(self) -> dict[str, Any]:
        session = self._session
        live = session is not None and session.accepting_input
        return {
            "backend_id": self.backend_id,
            "source_id": self.source_id,
            "source_instance": self._source_instance,
            "source_epoch": self._source_epoch,
            "environment_incarnation": self._environment_incarnation,
            "geometry_revision": self._geometry_revision,
            "width": 0,
            "height": 0,
            "operations": ["keyboard.text"],
            "modalities": ["accessibility"],
            "capture_state": "live" if session is not None else "unavailable",
            "input_state": "supported" if live else "unavailable",
            "backend_version": "1",
            "input_domain": self.input_domain,
            "input_domain_epoch": max(0, self._source_epoch - 1),
            "focus_epoch": 0,
        }

    @staticmethod
    def _require_current_binding(binding: Mapping[str, Any], current: Mapping[str, Any]) -> None:
        for key in (
            "source_id",
            "source_instance",
            "source_epoch",
            "environment_incarnation",
            "geometry_revision",
        ):
            if binding.get(key) != current.get(key):
                raise SurfaceTerminalError(f"ConPTY {key} no longer matches the active epoch")

    @staticmethod
    def _seconds(value: Any, label: str, maximum: float) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        if not math.isfinite(number) or number < 0 or number > maximum:
            return None
        return number

    @staticmethod
    def _outcome(disposition: str, delivered_count: int, ack_strength: str, detail: Any) -> dict[str, Any]:
        return {
            "disposition": disposition,
            "delivered_count": delivered_count,
            "ack_strength": ack_strength,
            "detail": detail,
        }
