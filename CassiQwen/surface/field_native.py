"""A general visual/input boundary for applications hosted by Cassi's own runtime.

The application publishes pixels and consumes standard input events; this module
has no application rules, learned state, or authority to grant control. The host
Surface broker remains the only route from an intention to ``dispatch``.
"""

from __future__ import annotations
import json

from collections import deque
from collections.abc import Mapping
from copy import deepcopy
from secrets import token_hex
from threading import Condition, RLock
from time import monotonic_ns
from typing import Any


_MAX_SIDE = 8192
_MAX_FRAME_BYTES = 64 << 20
_MAX_INPUT_EVENTS = 256
_FORMAT_CHANNELS = {"BGRA8": 4, "RGBA8": 4, "RGB8": 3, "GRAY8": 1}
_INPUT_OPERATIONS = frozenset({
    "keyboard.key", "keyboard.text", "pointer.absolute", "pointer.relative",
    "pointer.button", "pointer.wheel",
})


class FieldNativeError(ValueError):
    """A publication or control event is invalid for this source generation."""


def _uint(value: Any, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise FieldNativeError(f"{label} must be an integer in 0..{maximum}")
    return value


class FieldNativeBackend:
    """An identified field-native canvas with bounded, acknowledged input.

    ``publish`` is called by a real application. ``next_input`` returns the
    events that application must apply; a queue acknowledgment is never called
    evidence that the application's task succeeded. A generation changes on
    application restart, and geometry changes invalidate old coordinates.
    """

    backend_id = "field-native"

    def __init__(self, source_id: str, *, max_input_events: int = _MAX_INPUT_EVENTS) -> None:
        if not isinstance(source_id, str) or not source_id or len(source_id) > 128:
            raise FieldNativeError("source_id must be bounded nonempty text")
        if not 1 <= max_input_events <= 4096:
            raise FieldNativeError("max_input_events must be in 1..4096")
        self.source_id = source_id
        self._limit = max_input_events
        self._lock = RLock()
        self._ready = Condition(self._lock)
        self._incarnation = token_hex(16)
        self._instance = token_hex(16)
        self._epoch = 1
        self._geometry = 0
        self._width = 0
        self._height = 0
        self._format = "BGRA8"
        self._sequence = 0
        self._pixels: bytes | None = None
        self._sample_ns: int | None = None
        self._sample_clock: str | None = None
        self._sample_uncertainty_ns: int | None = None
        self._accessibility: dict[str, Any] | None = None
        self._privacy: tuple[dict[str, int], ...] = ()
        self._audio: bytes | None = None
        self._audio_sequence = 0
        self._audio_info: dict[str, Any] | None = None
        self._events: deque[dict[str, Any]] = deque()
        self._event_sequence = 0
        self._owned_keys: set[str] = set()
        self._owned_buttons: set[str] = set()
        self._neutralization_pending: int | None = None
        self._closed = False

    def _binding(self) -> dict[str, Any]:
        live = self._pixels is not None and not self._closed
        return {
            "backend_id": self.backend_id,
            "source_id": self.source_id,
            "source_instance": self._instance,
            "source_epoch": self._epoch,
            "environment_incarnation": self._incarnation,
            "geometry_revision": self._geometry,
            "width": self._width,
            "height": self._height,
            "operations": sorted(_INPUT_OPERATIONS | ({"audio.capture"} if self._audio_info is not None else set())),
            "modalities": (
                (["pixels"] if live else [])
                + (["accessibility"] if live and self._accessibility is not None else [])
                + (["audio"] if live and self._audio_info is not None else [])
            ),
            "capture_state": "live" if live else "unavailable",
            "input_state": (
                "unavailable" if not live else
                "suspended" if self._neutralization_pending is not None else "available"
            ),
        }

    def describe(self) -> dict[str, Any]:
        with self._lock:
            binding = self._binding()
            return {
                "backend_id": self.backend_id,
                "environment_incarnation": self._incarnation,
                "source": binding,
                "capabilities": {
                    "visual": {"status": binding["capture_state"], "formats": sorted(_FORMAT_CHANNELS),
                               "max_frame_bytes": _MAX_FRAME_BYTES, "clock": "application-monotonic-or-unknown"},
                    "keyboard.key": {"status": binding["input_state"], "ack_strength": "queued-only", "key_identity": "application-declared"},
                    "keyboard.text": {"status": binding["input_state"], "ack_strength": "queued-only", "encoding": "Unicode"},
                    "pointer.absolute": {"status": binding["input_state"], "coordinates": "source-local-physical-pixels"},
                    "pointer.relative": {"status": binding["input_state"], "coordinates": "signed-pixel-deltas"},
                    "pointer.button": {"status": binding["input_state"], "ack_strength": "queued-only"},
                    "pointer.wheel": {"status": binding["input_state"], "ack_strength": "queued-only", "units": "application-declared"},
                    "accessibility": {"status": "supported" if self._accessibility is not None else "unavailable",
                                      "reason": None if self._accessibility is not None else "application has not published an accessibility tree"},
                    "audio": {"status": "supported" if self._audio_info is not None else "unavailable",
                              "reason": None if self._audio_info is not None else "application has not provisioned an audio channel",
                              "format": None if self._audio_info is None else self._audio_info["audio_format"]},
                    "touch": {"status": "unavailable", "reason": "no touch endpoint"},
                    "controller": {"status": "unavailable", "reason": "no controller endpoint"},
                },
            }

    def sources(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._binding()]

    def bind(self, source_id: str) -> dict[str, Any]:
        with self._lock:
            if source_id != self.source_id or self._closed:
                raise FieldNativeError("source is unavailable")
            return self._binding()

    def revalidate(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        """Inspect the live source without rebinding or changing application state."""
        with self._lock:
            current = self._binding()
            valid = (
                isinstance(binding, Mapping)
                and current["capture_state"] == "live"
                and all(
                    binding.get(key) == current[key]
                    for key in (
                        "source_id", "source_instance", "source_epoch",
                        "environment_incarnation", "geometry_revision",
                    )
                )
            )
            return {
                "supported": True,
                "valid": valid,
                "reason": None if valid else "application instance or geometry is no longer live",
                **current,
            }

    def revalidate_target(
        self, binding: Mapping[str, Any], semantic_target: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate the live canvas itself, never an inferred child object."""
        current = self.revalidate(binding)
        if not current["valid"]:
            return {
                "supported": True,
                "valid": False,
                "detail": current["reason"],
            }
        if not isinstance(semantic_target, Mapping):
            return {
                "supported": False,
                "valid": False,
                "detail": "semantic target must name the exact source",
            }
        if dict(semantic_target) in (
            {"source_instance": current["source_instance"]},
            {"kind": "field-native", "identity": current["source_id"]},
        ):
            return {
                "supported": True,
                "valid": True,
                "detail": "target identifies the bound application canvas",
            }
        return {
            "supported": False,
            "valid": False,
            "detail": "field-native adapter cannot validate child objects",
        }

    def _assert_current(self, binding: Mapping[str, Any], *, geometry: bool) -> None:
        if self._closed or self._pixels is None:
            raise FieldNativeError("source is not live")
        if (
            binding.get("source_id") != self.source_id
            or binding.get("source_instance") != self._instance
            or binding.get("source_epoch") != self._epoch
            or binding.get("environment_incarnation") != self._incarnation
        ):
            raise FieldNativeError("source instance or epoch changed")
        if geometry and binding.get("geometry_revision") != self._geometry:
            raise FieldNativeError("source geometry changed")

    def publish(
        self,
        pixels: bytes,
        *,
        width: int,
        height: int,
        pixel_format: str = "BGRA8",
        sample_time_ns: int | None = None,
        sample_clock_domain: str | None = None,
        sample_time_uncertainty_ns: int | None = None,
        accessibility: Mapping[str, Any] | None = None,
        redacted_regions: tuple[Mapping[str, int], ...] = (),
    ) -> dict[str, Any]:
        """Publish a complete, immutable frame; partial updates need a baseline upstream."""
        width = _uint(width, "width", _MAX_SIDE)
        height = _uint(height, "height", _MAX_SIDE)
        if not width or not height or pixel_format not in _FORMAT_CHANNELS:
            raise FieldNativeError("visual dimensions or pixel format are unsupported")
        length = width * height * _FORMAT_CHANNELS[pixel_format]
        if length > _MAX_FRAME_BYTES or not isinstance(pixels, bytes) or len(pixels) != length:
            raise FieldNativeError("visual bytes do not match bounded dimensions")
        if sample_time_ns is not None:
            _uint(sample_time_ns, "sample_time_ns", (1 << 63) - 1)
        if sample_time_ns is None:
            if sample_clock_domain is not None or sample_time_uncertainty_ns is not None:
                raise FieldNativeError("a sample clock requires a sample time")
        elif not isinstance(sample_clock_domain, str) or not sample_clock_domain or len(sample_clock_domain) > 128:
            raise FieldNativeError("sample_clock_domain must identify the producer's clock")
        if sample_time_uncertainty_ns is not None:
            _uint(sample_time_uncertainty_ns, "sample_time_uncertainty_ns", (1 << 63) - 1)
        if accessibility is not None:
            if not isinstance(accessibility, Mapping):
                raise FieldNativeError("accessibility publication must be a mapping")
            try:
                encoded_accessibility = json.dumps(accessibility, allow_nan=False).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise FieldNativeError("accessibility tree must contain only finite JSON data") from exc
            if len(encoded_accessibility) > 1_048_576:
                raise FieldNativeError("accessibility tree exceeds one MiB")
            safe_accessibility = json.loads(encoded_accessibility)
        else:
            safe_accessibility = None
        regions: list[dict[str, int]] = []
        for rect in redacted_regions:
            if not isinstance(rect, Mapping) or set(rect) != {"x", "y", "width", "height"}:
                raise FieldNativeError("redaction region is invalid")
            x, y = _uint(rect["x"], "x", width), _uint(rect["y"], "y", height)
            w, h = _uint(rect["width"], "width", width), _uint(rect["height"], "height", height)
            if x + w > width or y + h > height:
                raise FieldNativeError("redaction escapes the source")
            regions.append({"x": x, "y": y, "width": w, "height": h})
        if len(regions) > 1024:
            raise FieldNativeError("too many redaction regions")
        with self._lock:
            if self._closed:
                raise FieldNativeError("source is closed")
            if (width, height, pixel_format) != (self._width, self._height, self._format):
                self._geometry += 1
            self._width, self._height, self._format = width, height, pixel_format
            if regions:
                masked = bytearray(pixels)
                stride = width * _FORMAT_CHANNELS[pixel_format]
                channels = _FORMAT_CHANNELS[pixel_format]
                for rect in regions:
                    row_bytes = rect["width"] * channels
                    blank = bytes(row_bytes)
                    for y in range(rect["y"], rect["y"] + rect["height"]):
                        start = y * stride + rect["x"] * channels
                        masked[start : start + row_bytes] = blank
                pixels = bytes(masked)
            self._pixels = pixels  # immutable masked bytes: readers retain their own generation
            self._sample_ns = sample_time_ns
            self._sample_clock = sample_clock_domain
            self._sample_uncertainty_ns = sample_time_uncertainty_ns
            # A pixel mask cannot prove which structural nodes disclose the
            # same secret; with any protected region, omit the whole tree.
            self._accessibility = None if regions else safe_accessibility
            self._privacy = tuple(regions)
            self._sequence += 1
            return self._binding()

    def publish_audio(
        self,
        samples: bytes,
        *,
        sample_rate: int,
        channels: int,
        sample_time_ns: int | None = None,
        sample_clock_domain: str | None = None,
        sample_time_uncertainty_ns: int | None = None,
    ) -> None:
        """Publish a bounded PCM interval, separately timed from the image."""
        sample_rate = _uint(sample_rate, "sample_rate", 192_000)
        channels = _uint(channels, "channels", 8)
        if sample_rate < 8_000 or not channels or not isinstance(samples, bytes) or len(samples) > 4 << 20:
            raise FieldNativeError("audio interval is invalid or exceeds four MiB")
        if len(samples) % (channels * 2):
            raise FieldNativeError("PCM s16le samples must contain whole frames")
        if sample_time_ns is not None:
            _uint(sample_time_ns, "sample_time_ns", (1 << 63) - 1)
        if sample_time_ns is None:
            if sample_clock_domain is not None or sample_time_uncertainty_ns is not None:
                raise FieldNativeError("an audio sample clock requires a sample time")
        elif not isinstance(sample_clock_domain, str) or not sample_clock_domain or len(sample_clock_domain) > 128:
            raise FieldNativeError("audio sample_clock_domain must identify the producer's clock")
        if sample_time_uncertainty_ns is not None:
            _uint(sample_time_uncertainty_ns, "sample_time_uncertainty_ns", (1 << 63) - 1)
        with self._lock:
            if self._closed:
                raise FieldNativeError("source is closed")
            self._audio = samples
            self._audio_sequence += 1
            self._audio_info = {
                "sequence": self._audio_sequence,
                "audio_format": "pcm-i16le",
                "sample_rate_hz": sample_rate,
                "channel_count": channels,
                "sample_count": len(samples) // (channels * 2),
                "sample_time_ns": sample_time_ns,
                "sample_clock_domain": sample_clock_domain,
                "sample_time_uncertainty_ns": sample_time_uncertainty_ns,
                "receipt_clock_domain": "host-monotonic",
                "receipt_time_ns": monotonic_ns(),
                "coverage": {
                    "complete": True, "missing_regions": [], "redacted_regions": [],
                    "unknown_regions": [],
                    "skipped_intervals": [{"reason": "intermediate-audio-intervals-not-retained"}],
                },
            }

    def capture(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._assert_current(binding, geometry=False)
            return {
                **self._binding(),
                "pixels": self._pixels,
                "pixel_format": self._format,
                "sequence": self._sequence,
                "sample_time_ns": self._sample_ns,
                "sample_clock_domain": self._sample_clock,
                "sample_time_uncertainty_ns": self._sample_uncertainty_ns,
                "receipt_clock_domain": "host-monotonic",
                "receipt_time_ns": monotonic_ns(),
                "coverage": {"complete": True, "missing_regions": [],
                             "redacted_regions": [dict(rect) for rect in self._privacy],
                             "unknown_regions": [],
                             "skipped_intervals": [{"reason": "intermediate-frames-not-retained"}]},
                "accessibility": deepcopy(self._accessibility),
                "accessibility_sample_time_ns": self._sample_ns if self._accessibility is not None else None,
                "provenance": "field-native-application",
                "audio": None if self._audio_info is None else {
                    **self._audio_info, "samples": self._audio,
                },
            }

    def _event(self, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        self._event_sequence += 1
        return {
            "sequence": self._event_sequence,
            "source_id": self.source_id,
            "source_epoch": self._epoch,
            "geometry_revision": self._geometry,
            "operation": operation,
            "arguments": dict(arguments),
            "queued_time_ns": monotonic_ns(),
        }

    def dispatch(self, binding: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
        with self._ready:
            try:
                if not isinstance(binding, Mapping) or not isinstance(action, Mapping):
                    raise FieldNativeError("binding and control action must be objects")
                self._assert_current(binding, geometry=True)
                if self._neutralization_pending is not None:
                    raise FieldNativeError("input neutralization has not been acknowledged")
                operation = action.get("operation")
                if not isinstance(operation, str) or operation not in _INPUT_OPERATIONS:
                    raise FieldNativeError("control operation is unsupported")
                arguments = action.get("arguments")
                if not isinstance(arguments, Mapping):
                    raise FieldNativeError("control arguments must be an object")
                if operation == "keyboard.key":
                    if (set(arguments) != {"key", "state"}
                        or not isinstance(arguments["key"], str)
                        or not 0 < len(arguments["key"]) <= 128
                        or not isinstance(arguments["state"], str)
                        or arguments["state"] not in {"down", "up"}):
                        raise FieldNativeError("key event is invalid")
                elif operation == "keyboard.text":
                    if set(arguments) != {"text"} or not isinstance(arguments["text"], str) or len(arguments["text"].encode("utf-8")) > 4096:
                        raise FieldNativeError("text event is invalid")
                elif operation == "pointer.absolute":
                    if set(arguments) != {"x", "y"} or _uint(arguments["x"], "x", self._width - 1) >= self._width or _uint(arguments["y"], "y", self._height - 1) >= self._height:
                        raise FieldNativeError("pointer coordinates are invalid")
                elif operation == "pointer.relative":
                    if set(arguments) != {"dx", "dy"} or any(isinstance(arguments[n], bool) or not isinstance(arguments[n], int) or abs(arguments[n]) > 8192 for n in ("dx", "dy")):
                        raise FieldNativeError("relative pointer movement is invalid")
                elif operation == "pointer.button":
                    if (set(arguments) != {"button", "state"}
                        or not isinstance(arguments["button"], str)
                        or arguments["button"] not in {"left", "middle", "right"}
                        or not isinstance(arguments["state"], str)
                        or arguments["state"] not in {"down", "up"}):
                        raise FieldNativeError("pointer button event is invalid")
                elif operation == "pointer.wheel":
                    if set(arguments) != {"dx", "dy"} or any(isinstance(arguments[n], bool) or not isinstance(arguments[n], int) or abs(arguments[n]) > 1200 for n in ("dx", "dy")):
                        raise FieldNativeError("wheel event is invalid")
                if len(self._events) >= self._limit:
                    raise FieldNativeError("input queue is full")
                event = self._event(operation, arguments)
                self._events.append(event)
                if operation == "keyboard.key":
                    (self._owned_keys.add if arguments["state"] == "down" else self._owned_keys.discard)(arguments["key"])
                elif operation == "pointer.button":
                    (self._owned_buttons.add if arguments["state"] == "down" else self._owned_buttons.discard)(arguments["button"])
                self._ready.notify()
                return {"disposition": "delivered", "delivered_count": 1,
                        "ack_strength": "queued-only", "detail": {"event_sequence": event["sequence"]}}
            except FieldNativeError as exc:
                return {"disposition": "rejected", "delivered_count": 0,
                        "ack_strength": "none", "detail": str(exc)}

    def next_input(self, *, timeout_seconds: float = 0.0) -> dict[str, Any] | None:
        """Application-side dequeue; the host cannot use this to grant input."""
        if not 0 <= timeout_seconds <= 60:
            raise FieldNativeError("timeout_seconds must be in 0..60")
        with self._ready:
            if not self._events and not self._closed:
                self._ready.wait(timeout_seconds)
            if self._events:
                return self._events.popleft()
            return None

    def neutralize(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        with self._ready:
            if binding.get("source_instance") != self._instance or binding.get("source_epoch") != self._epoch:
                return {"confirmed": True, "detail": "application restart cleared the previous instance's queued and held controls; the new instance was not touched"}
            self._events.clear()  # queued conflicting events must not run after takeover
            for key in sorted(self._owned_keys):
                self._events.append(self._event("keyboard.key", {"key": key, "state": "up"}))
            for button in sorted(self._owned_buttons):
                self._events.append(self._event("pointer.button", {"button": button, "state": "up"}))
            self._owned_keys.clear()
            self._owned_buttons.clear()
            self._neutralization_pending = self._events[-1]["sequence"] if self._events else None
            self._ready.notify_all()
            return {"confirmed": self._neutralization_pending is None,
                    "detail": "no owned controls held" if self._neutralization_pending is None else
                              f"release events queued through {self._neutralization_pending}; application acknowledgment required"}

    def acknowledge_input(self, event_sequence: int) -> None:
        """Application confirms processing an input event, not its semantic result."""
        with self._ready:
            if self._neutralization_pending is not None and event_sequence >= self._neutralization_pending:
                self._neutralization_pending = None
                self._ready.notify_all()

    def restart(self) -> None:
        """Replace this application's instance; the old binding is never reused."""
        with self._ready:
            self._epoch += 1
            self._instance = token_hex(16)
            self._geometry += 1
            self._pixels = None
            self._sample_ns = None
            self._sample_clock = None
            self._sample_uncertainty_ns = None
            self._audio = None
            self._audio_sequence = 0
            self._audio_info = None
            self._sequence = 0
            self._events.clear()
            self._owned_keys.clear()
            self._owned_buttons.clear()
            self._neutralization_pending = None
            self._ready.notify_all()

    def close(self) -> None:
        with self._ready:
            self._closed = True
            self._events.clear()
            self._ready.notify_all()
