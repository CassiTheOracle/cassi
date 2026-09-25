"""Bounded typed records for the host-owned Cassi Surface boundary.

These are operational views, not a second adaptive store.  In particular,
image/audio bytes are deliberately kept out of the JSON-safe record forms.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping


MAX_TEXT = 512
MAX_IDENTIFIER = 192
MAX_DIMENSION = 8192
MAX_FRAME_BYTES = 64 << 20
MAX_ACCESSIBILITY_BYTES = 1 << 20
MAX_METADATA_BYTES = 256 << 10
MAX_INTENT_BYTES = 64 << 10
MAX_DETAIL_BYTES = 64 << 10
MAX_JSON_DEPTH = 16
MAX_COLLECTION_ITEMS = 4096
PIXEL_CHANNELS = {"BGRA8": 4, "RGBA8": 4, "RGB8": 3, "GRAY8": 1}
MAX_AUDIO_BYTES = 4 << 20
AUDIO_SAMPLE_BYTES = {"pcm-f32le": 4, "pcm-f64le": 8, "pcm-i16le": 2, "pcm-i32le": 4, "pcm-u8": 1}
_OPERATION_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")


class SurfaceError(RuntimeError):
    """Base error for rejected Surface operations."""


class SurfaceValidationError(SurfaceError, ValueError):
    """A record violates its bounded wire schema."""


class SurfaceConflictError(SurfaceError):
    """An operation identity or compare-and-set value conflicts."""


class SurfaceAuthorizationError(SurfaceError):
    """No current host-issued authority permits the requested action."""


class SurfaceCapabilityError(SurfaceError):
    """The selected backend does not provide the requested capability."""


class SurfaceWaitError(SurfaceError):
    """A typed, inspectable resource or readiness wait (never a busy retry)."""

    def __init__(self, details: Mapping[str, Any]):
        self.details = json_value(details, max_bytes=MAX_DETAIL_BYTES, label="wait details")
        super().__init__(str(self.details.get("reason", "surface operation is waiting")))


def _uint(value: Any, label: str, maximum: int, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise SurfaceValidationError(f"{label} must be an integer in {minimum}..{maximum}")
    return value


def _text(value: Any, label: str, maximum: int = MAX_TEXT, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value) or len(value) > maximum or "\x00" in value:
        raise SurfaceValidationError(f"{label} must be bounded text")
    return value


def json_value(value: Any, *, max_bytes: int, label: str = "value", max_depth: int = MAX_JSON_DEPTH) -> Any:
    """Round-trip finite JSON data to detach caller-owned objects and bound it."""
    def walk(node: Any, depth: int) -> None:
        if depth > max_depth:
            raise SurfaceValidationError(f"{label} exceeds the JSON nesting limit")
        if node is None or isinstance(node, (str, bool, int)):
            if isinstance(node, str) and (len(node) > MAX_TEXT * 16 or "\x00" in node):
                raise SurfaceValidationError(f"{label} contains an invalid string")
            if isinstance(node, int) and not isinstance(node, bool) and abs(node) > (1 << 63) - 1:
                raise SurfaceValidationError(f"{label} contains an out-of-range integer")
            return
        if isinstance(node, float):
            if not math.isfinite(node):
                raise SurfaceValidationError(f"{label} contains a non-finite number")
            return
        if isinstance(node, Mapping):
            if len(node) > MAX_COLLECTION_ITEMS:
                raise SurfaceValidationError(f"{label} contains too many object members")
            for key, child in node.items():
                if not isinstance(key, str):
                    raise SurfaceValidationError(f"{label} object keys must be strings")
                _text(key, f"{label} key", maximum=MAX_TEXT)
                walk(child, depth + 1)
            return
        if isinstance(node, (list, tuple)):
            if len(node) > MAX_COLLECTION_ITEMS:
                raise SurfaceValidationError(f"{label} contains too many array items")
            for child in node:
                walk(child, depth + 1)
            return
        # bytes, native handles, custom objects and callbacks never cross JSON.
        raise SurfaceValidationError(f"{label} contains a non-JSON value")

    walk(value, 0)
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SurfaceValidationError(f"{label} is not valid JSON data") from exc
    if len(encoded) > max_bytes:
        raise SurfaceValidationError(f"{label} exceeds {max_bytes} bytes")
    try:
        return json.loads(encoded)
    except (ValueError, UnicodeError) as exc:
        raise SurfaceValidationError(f"{label} is not valid UTF-8 JSON data") from exc


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise SurfaceValidationError("record cannot be canonically encoded") from exc


def normalize_operations(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > 256:
        raise SurfaceValidationError("operations must be a bounded list")
    operations: list[str] = []
    seen: set[str] = set()
    for item in value:
        operation = _text(item, "operation", 128)
        if not _OPERATION_RE.fullmatch(operation):
            raise SurfaceValidationError("operation name has unsupported syntax")
        if operation not in seen:
            seen.add(operation)
            operations.append(operation)
    return tuple(sorted(operations))


@dataclass(frozen=True, slots=True)
class SurfaceSourceDescriptor:
    """A discoverable source whose binding epoch may not exist yet."""

    backend_id: str
    source_id: str
    source_instance: str
    environment_incarnation: str
    operations: tuple[str, ...]
    source_epoch: int | None = None
    geometry_revision: int | None = None
    width: int | None = None
    height: int | None = None
    capture_state: str | None = None
    input_state: str | None = None
    backend_version: str | None = None
    input_domain: str | None = None
    input_domain_epoch: int | None = None
    focus_epoch: int | None = None

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
        *,
        backend_id: str,
    ) -> "SurfaceSourceDescriptor":
        if not isinstance(value, Mapping):
            raise SurfaceValidationError("backend source descriptor must be an object")
        actual_backend = _text(value.get("backend_id", backend_id), "backend_id", 128)
        if actual_backend != backend_id:
            raise SurfaceValidationError("source descriptor backend_id does not match the registered backend")
        source_id = _text(value.get("source_id"), "source_id", 256)
        instance = _text(value.get("source_instance"), "source_instance", MAX_IDENTIFIER)
        environment = _text(value.get("environment_incarnation"), "environment_incarnation", MAX_IDENTIFIER)

        def optional_uint(key: str, maximum: int, *, minimum: int = 0) -> int | None:
            raw = value.get(key)
            return None if raw is None else _uint(
                raw, f"source descriptor {key}", maximum, minimum=minimum
            )

        def optional_text(key: str, maximum: int = MAX_TEXT) -> str | None:
            raw = value.get(key)
            return None if raw is None else _text(raw, f"source descriptor {key}", maximum)

        width_value = value.get("width")
        height_value = value.get("height")
        if (width_value is None) != (height_value is None):
            raise SurfaceValidationError("source descriptor dimensions must both be present or absent")
        width = None if width_value is None else _uint(width_value, "source descriptor width", MAX_DIMENSION)
        height = None if height_value is None else _uint(height_value, "source descriptor height", MAX_DIMENSION)
        if width is not None and bool(width) != bool(height):
            raise SurfaceValidationError("source descriptor dimensions must both be zero or both be positive")
        return cls(
            actual_backend,
            source_id,
            instance,
            environment,
            normalize_operations(value.get("operations", ())),
            optional_uint("source_epoch", (1 << 63) - 1, minimum=1),
            optional_uint("geometry_revision", (1 << 63) - 1),
            width,
            height,
            optional_text("capture_state", 64),
            optional_text("input_state", 64),
            optional_text("backend_version", 128),
            optional_text("input_domain", MAX_IDENTIFIER),
            optional_uint("input_domain_epoch", (1 << 63) - 1),
            optional_uint("focus_epoch", (1 << 63) - 1),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "backend_id": self.backend_id,
            "source_id": self.source_id,
            "source_instance": self.source_instance,
            "environment_incarnation": self.environment_incarnation,
            "operations": list(self.operations),
        }
        for key in (
            "source_epoch",
            "geometry_revision",
            "width",
            "height",
            "capture_state",
            "input_state",
            "backend_version",
            "input_domain",
            "input_domain_epoch",
            "focus_epoch",
        ):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        return result


@dataclass(frozen=True, slots=True)
class SurfaceBinding:
    backend_id: str
    source_id: str
    source_instance: str
    source_epoch: int
    environment_incarnation: str
    geometry_revision: int
    width: int
    height: int
    operations: tuple[str, ...]
    capture_state: str
    input_state: str
    backend_version: str | None = None
    input_domain: str | None = None
    input_domain_epoch: int | None = None
    focus_epoch: int | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, backend_id: str | None = None, source_id: str | None = None) -> "SurfaceBinding":
        if not isinstance(value, Mapping):
            raise SurfaceValidationError("backend binding must be an object")
        actual_backend = _text(value.get("backend_id", backend_id), "backend_id", 128)
        if backend_id is not None and actual_backend != backend_id:
            raise SurfaceValidationError("binding backend_id does not match the registered backend")
        actual_source = _text(value.get("source_id", source_id), "source_id", 256)
        if source_id is not None and actual_source != source_id:
            raise SurfaceValidationError("binding source_id does not match the requested source")
        instance = _text(value.get("source_instance"), "source_instance", MAX_IDENTIFIER)
        environment = _text(value.get("environment_incarnation"), "environment_incarnation", MAX_IDENTIFIER)
        epoch = _uint(value.get("source_epoch"), "source_epoch", (1 << 63) - 1, minimum=1)
        geometry = _uint(value.get("geometry_revision"), "geometry_revision", (1 << 63) - 1)
        width = _uint(value.get("width", 0), "width", MAX_DIMENSION)
        height = _uint(value.get("height", 0), "height", MAX_DIMENSION)
        if bool(width) != bool(height):
            raise SurfaceValidationError("binding dimensions must both be zero or both be positive")
        operations = normalize_operations(value.get("operations", ()))
        capture_state = _text(value.get("capture_state", "unavailable"), "capture_state", 64)
        input_state = _text(value.get("input_state", "unavailable"), "input_state", 64)
        backend_version = value.get("backend_version")
        if backend_version is not None:
            backend_version = _text(backend_version, "backend_version", 128)
        input_domain = value.get("input_domain")
        if input_domain is not None:
            input_domain = _text(input_domain, "input_domain", MAX_IDENTIFIER)
        input_domain_epoch = value.get("input_domain_epoch")
        if input_domain_epoch is not None:
            input_domain_epoch = _uint(input_domain_epoch, "input_domain_epoch", (1 << 63) - 1)
        focus_epoch = value.get("focus_epoch")
        if focus_epoch is not None:
            focus_epoch = _uint(focus_epoch, "focus_epoch", (1 << 63) - 1)
        return cls(actual_backend, actual_source, instance, epoch, environment, geometry, width, height,
                   operations, capture_state, input_state, backend_version, input_domain,
                   input_domain_epoch, focus_epoch)

    def to_dict(self, binding_id: str) -> dict[str, Any]:
        return {
            "binding_id": binding_id,
            "backend_id": self.backend_id,
            "source_id": self.source_id,
            "source_instance": self.source_instance,
            "source_epoch": self.source_epoch,
            "environment_incarnation": self.environment_incarnation,
            "geometry_revision": self.geometry_revision,
            "width": self.width,
            "height": self.height,
            "operations": list(self.operations),
            "capture_state": self.capture_state,
            "input_state": self.input_state,
            "backend_version": self.backend_version,
            "input_domain": self.input_domain,
            "input_domain_epoch": self.input_domain_epoch,
            "focus_epoch": self.focus_epoch,
        }


@dataclass(frozen=True, slots=True)
class ObservationPublication:
    binding_id: str
    source_id: str
    source_instance: str
    source_epoch: int
    environment_incarnation: str
    geometry_revision: int
    sequence: int
    width: int
    height: int
    pixel_format: str
    sample_time_ns: int | None
    receipt_time_ns: int
    coverage: dict[str, Any]
    accessibility: dict[str, Any] | list[Any] | None
    accessibility_sample_time_ns: int | None
    provenance: str | None
    screen_text: str | None
    pixel_bytes: bytes | None
    audio_bytes: bytes | None
    audio_sequence: int | None
    audio_metadata: dict[str, Any] | None
    delta: bool = False
    baseline_generation: int | None = None
    byte_ranges: tuple[dict[str, int], ...] = ()

    @classmethod
    def from_capture(cls, binding_id: str, binding: SurfaceBinding, value: Mapping[str, Any]) -> "ObservationPublication":
        if not isinstance(value, Mapping):
            raise SurfaceValidationError("capture result must be an object")
        source_id = _text(value.get("source_id", binding.source_id), "publication source_id", 256)
        instance = _text(value.get("source_instance"), "publication source_instance", MAX_IDENTIFIER)
        environment = _text(value.get("environment_incarnation"), "publication environment_incarnation", MAX_IDENTIFIER)
        source_epoch = _uint(value.get("source_epoch"), "publication source_epoch", (1 << 63) - 1, minimum=1)
        geometry = _uint(value.get("geometry_revision"), "publication geometry_revision", (1 << 63) - 1)
        audio = value.get("audio")
        audio_bytes: bytes | None = None
        audio_sequence: int | None = None
        audio_metadata: dict[str, Any] | None = None
        audio_sample_time: int | None = None
        audio_receipt_time: int | None = None
        if audio is not None:
            if not isinstance(audio, Mapping):
                raise SurfaceValidationError("audio capture must be an object")
            samples = audio.get("samples")
            if samples is not None:
                if not isinstance(samples, bytes) or len(samples) > MAX_AUDIO_BYTES:
                    raise SurfaceValidationError("audio samples must be immutable bounded bytes")
                audio_format = _text(audio.get("audio_format", audio.get("format")), "audio_format", 32)
                if audio_format == "pcm_s16le":
                    audio_format = "pcm-i16le"
                if audio_format not in AUDIO_SAMPLE_BYTES:
                    raise SurfaceCapabilityError(f"unsupported audio format: {audio_format}")
                sample_rate = _uint(audio.get("sample_rate_hz", audio.get("sample_rate")), "sample_rate_hz", 192000, minimum=8000)
                channels = _uint(audio.get("channel_count", audio.get("channels")), "channel_count", 8, minimum=1)
                sample_width = AUDIO_SAMPLE_BYTES[audio_format]
                frame_width = sample_width * channels
                if not samples or len(samples) % frame_width:
                    raise SurfaceValidationError("audio sample bytes must contain complete nonempty frames")
                derived_count = len(samples) // frame_width
                sample_count = _uint(audio.get("sample_count", audio.get("frames", derived_count)),
                                     "sample_count", MAX_AUDIO_BYTES, minimum=1)
                if sample_count != derived_count:
                    raise SurfaceValidationError("audio sample_count does not match sample bytes")
                audio_sequence = _uint(audio.get("sequence", value.get("sequence")),
                                       "audio sequence", (1 << 63) - 1, minimum=1)
                audio_sample_time = audio.get("sample_time_ns")
                if audio_sample_time is not None:
                    audio_sample_time = _uint(audio_sample_time, "audio sample_time_ns", (1 << 63) - 1)
                audio_receipt_time = _uint(audio.get("receipt_time_ns", value.get("receipt_time_ns")),
                                           "audio receipt_time_ns", (1 << 63) - 1, minimum=1)
                audio_sample_clock = audio.get("sample_clock_domain", audio.get("clock_domain"))
                if audio_sample_clock is not None:
                    audio_sample_clock = _text(audio_sample_clock, "audio sample_clock_domain", 128)
                audio_receipt_clock = audio.get("receipt_clock_domain", value.get("receipt_clock_domain"))
                if audio_receipt_clock is not None:
                    audio_receipt_clock = _text(audio_receipt_clock, "audio receipt_clock_domain", 128)
                uncertainty = audio.get("sample_time_uncertainty_ns")
                if uncertainty is not None:
                    uncertainty = _uint(uncertainty, "audio sample_time_uncertainty_ns", (1 << 63) - 1)
                audio_bytes = samples
                audio_coverage = json_value(audio.get("coverage", {}), max_bytes=MAX_METADATA_BYTES,
                                            label="audio coverage")
                if not isinstance(audio_coverage, dict):
                    raise SurfaceValidationError("audio coverage must be an object")
                audio_metadata = {
                    "audio_format": audio_format,
                    "sample_rate_hz": sample_rate,
                    "channel_count": channels,
                    "sample_count": sample_count,
                    "sequence": audio_sequence,
                    "sample_time_ns": audio_sample_time,
                    "sample_clock_domain": audio_sample_clock,
                    "sample_time_uncertainty_ns": uncertainty,
                    "receipt_time_ns": audio_receipt_time,
                    "receipt_clock_domain": audio_receipt_clock,
                    "byte_length": len(samples),
                    "coverage": audio_coverage,
                    "data_plane": "surface.read_audio_page",
                }
                audio_metadata = json_value(audio_metadata, max_bytes=4096, label="audio metadata")
        if audio_bytes is None and (audio is not None and audio.get("samples") is None):
            audio_metadata = None
        pixels = value.get("pixels")
        if pixels is not None and (not isinstance(pixels, bytes) or len(pixels) > MAX_FRAME_BYTES):
            raise SurfaceValidationError("capture pixels must be immutable bounded bytes")
        if pixels is None and audio_bytes is None and value.get("screen_text") is None and value.get("accessibility") is None:
            raise SurfaceValidationError("capture must contain pixels, audio samples, screen text, or accessibility")
        width = _uint(value.get("width", binding.width), "publication width", MAX_DIMENSION)
        height = _uint(value.get("height", binding.height), "publication height", MAX_DIMENSION)
        pixel_format_value = value.get("pixel_format", "none" if pixels is None else None)
        pixel_format = _text(pixel_format_value, "pixel_format", 16) if pixel_format_value is not None else "none"
        if pixels is None:
            if pixel_format != "none":
                raise SurfaceValidationError("non-pixel captures must use pixel_format='none'")
        else:
            if width < 1 or height < 1:
                raise SurfaceValidationError("pixel capture dimensions must be positive")
            if width * height * 4 > MAX_FRAME_BYTES:
                raise SurfaceValidationError("publication dimensions exceed the frame limit")
            if pixel_format not in PIXEL_CHANNELS:
                raise SurfaceCapabilityError(f"unsupported pixel format: {pixel_format}")
            if width != binding.width or height != binding.height:
                raise SurfaceConflictError("capture extents changed without a new geometry binding")
        sequence_value = value.get("sequence", audio_sequence)
        sequence = _uint(sequence_value, "publication sequence", (1 << 63) - 1, minimum=1)
        sample_time = value.get("sample_time_ns")
        if sample_time is not None:
            sample_time = _uint(sample_time, "sample_time_ns", (1 << 63) - 1)
        elif pixels is None:
            sample_time = audio_sample_time
        receipt_value = value.get("receipt_time_ns", audio_receipt_time)
        if receipt_value is None:
            raise SurfaceValidationError("capture requires a receipt_time_ns")
        receipt = _uint(receipt_value, "receipt_time_ns", (1 << 63) - 1, minimum=1)
        is_delta = value.get("delta", False)
        if not isinstance(is_delta, bool):
            raise SurfaceValidationError("delta must be a boolean")
        if pixels is None and is_delta:
            raise SurfaceValidationError("audio-only capture cannot use pixel delta ranges")
        baseline = value.get("baseline_generation")
        if baseline is not None:
            baseline = _uint(baseline, "baseline_generation", (1 << 63) - 1, minimum=1)
        ranges_value = value.get("byte_ranges", ())
        if not isinstance(ranges_value, (list, tuple)) or len(ranges_value) > MAX_COLLECTION_ITEMS:
            raise SurfaceValidationError("byte_ranges must be a bounded list")
        ranges: list[dict[str, int]] = []
        for index, item in enumerate(ranges_value):
            if not isinstance(item, Mapping) or set(item) != {"offset", "length", "source_offset"}:
                raise SurfaceValidationError(f"byte_ranges[{index}] has an invalid shape")
            offset = _uint(item["offset"], f"byte_ranges[{index}].offset", MAX_FRAME_BYTES)
            length = _uint(item["length"], f"byte_ranges[{index}].length", MAX_FRAME_BYTES, minimum=1)
            source_offset = _uint(item["source_offset"], f"byte_ranges[{index}].source_offset", MAX_FRAME_BYTES)
            ranges.append({"offset": offset, "length": length, "source_offset": source_offset})
        if is_delta != (baseline is not None and bool(ranges)):
            raise SurfaceValidationError("delta requires a baseline generation and at least one byte range")
        coverage = json_value(value.get("coverage", {}), max_bytes=MAX_METADATA_BYTES, label="coverage")
        if not isinstance(coverage, dict):
            raise SurfaceValidationError("coverage must be an object")
        accessibility_value = value.get("accessibility")
        if accessibility_value is not None:
            accessibility_value = json_value(accessibility_value, max_bytes=MAX_ACCESSIBILITY_BYTES, label="accessibility")
            if not isinstance(accessibility_value, (dict, list)):
                raise SurfaceValidationError("accessibility must be an object, array, or null")
        accessibility_time = value.get("accessibility_sample_time_ns")
        if accessibility_time is not None:
            accessibility_time = _uint(accessibility_time, "accessibility_sample_time_ns", (1 << 63) - 1)
        provenance = value.get("provenance")
        if provenance is not None:
            provenance = _text(provenance, "provenance", 256)
        screen_text = value.get("screen_text")
        if screen_text is not None:
            if not isinstance(screen_text, str):
                raise SurfaceValidationError("screen_text must be text")
            try:
                screen_text_bytes = screen_text.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise SurfaceValidationError("screen_text must be valid UTF-8") from exc
            if len(screen_text_bytes) > MAX_ACCESSIBILITY_BYTES:
                raise SurfaceValidationError("screen_text exceeds the structural publication limit")
        if source_id != binding.source_id or instance != binding.source_instance or environment != binding.environment_incarnation:
            raise SurfaceConflictError("capture source identity or environment changed")
        if source_epoch != binding.source_epoch:
            raise SurfaceConflictError("capture source epoch changed")
        if geometry != binding.geometry_revision:
            raise SurfaceConflictError("capture geometry changed")
        return cls(binding_id, source_id, instance, source_epoch, environment, geometry, sequence, width, height,
                   pixel_format, sample_time, receipt, coverage, accessibility_value, accessibility_time,
                   provenance, screen_text, pixels, audio_bytes, audio_sequence, audio_metadata, is_delta, baseline, tuple(ranges))

    @property
    def has_pixels(self) -> bool:
        return self.pixel_bytes is not None

    @property
    def expected_full_length(self) -> int:
        if self.pixel_bytes is None:
            return 0
        return self.width * self.height * PIXEL_CHANNELS[self.pixel_format]

    def metadata(self, generation: int, *, pixel_digest: str | None, byte_length: int,
                 field_metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if self.has_pixels and self.audio_bytes is not None:
            data_plane = "surface.read_page+surface.read_audio_page"
        elif self.has_pixels:
            data_plane = "surface.read_page"
        elif self.audio_bytes is not None:
            data_plane = "surface.read_audio_page"
        else:
            data_plane = "surface.read_text_page"
        result: dict[str, Any] = {
            "binding_id": self.binding_id,
            "source_id": self.source_id,
            "source_instance": self.source_instance,
            "source_epoch": self.source_epoch,
            "environment_incarnation": self.environment_incarnation,
            "geometry_revision": self.geometry_revision,
            "sequence": self.sequence,
            "generation": generation,
            "width": self.width,
            "height": self.height,
            "pixel_format": self.pixel_format,
            "sample_time_ns": self.sample_time_ns,
            "receipt_time_ns": self.receipt_time_ns,
            "coverage": self.coverage,
            "accessibility": self.accessibility,
            "accessibility_sample_time_ns": self.accessibility_sample_time_ns,
            "provenance": self.provenance,
            "audio": self.audio_metadata,
            "byte_length": byte_length,
            "sha256": pixel_digest,
            "data_plane": data_plane,
        }
        if field_metadata is not None:
            result["field"] = json_value(field_metadata, max_bytes=MAX_DETAIL_BYTES, label="field admission")
        return result


_INTENT_REQUIRED = frozenset({
    "operation_id", "mission_id", "binding_id", "grant_id", "operation", "payload",
    "expected_source_epoch", "expected_geometry_revision",
})
_INTENT_OPTIONAL = frozenset({
    "expected_focus_epoch", "expected_input_domain_epoch", "sequence", "created_ns", "deadline_ns",
    "semantic_target", "dependency_versions", "expected_effect", "resource_reservation",
    "max_duration_ns", "stop_conditions", "goal_revision",
})


@dataclass(frozen=True, slots=True)
class ControlIntent:
    operation_id: str
    mission_id: str
    binding_id: str
    grant_id: str
    operation: str
    payload: dict[str, Any]
    expected_source_epoch: int
    expected_geometry_revision: int
    expected_focus_epoch: int | None
    expected_input_domain_epoch: int | None
    sequence: int | None
    created_ns: int | None
    deadline_ns: int | None
    semantic_target: Any
    dependency_versions: Any
    expected_effect: Any
    resource_reservation: Any
    max_duration_ns: int | None
    stop_conditions: Any
    goal_revision: str | int | None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ControlIntent":
        if not isinstance(value, Mapping):
            raise SurfaceValidationError("intent must be an object")
        keys = set(value)
        missing = _INTENT_REQUIRED - keys
        unknown = keys - _INTENT_REQUIRED - _INTENT_OPTIONAL
        if missing:
            raise SurfaceValidationError(f"intent is missing required fields: {', '.join(sorted(missing))}")
        if unknown:
            raise SurfaceValidationError(f"intent has unsupported fields: {', '.join(sorted(map(str, unknown)))}")
        operation_id = _text(value["operation_id"], "operation_id", MAX_IDENTIFIER)
        mission_id = _text(value["mission_id"], "mission_id", MAX_IDENTIFIER)
        binding_id = _text(value["binding_id"], "binding_id", MAX_IDENTIFIER)
        grant_id = _text(value["grant_id"], "grant_id", MAX_IDENTIFIER)
        operation = _text(value["operation"], "operation", 128)
        if not _OPERATION_RE.fullmatch(operation):
            raise SurfaceValidationError("operation name has unsupported syntax")
        payload = json_value(value["payload"], max_bytes=MAX_INTENT_BYTES, label="intent payload")
        if not isinstance(payload, dict):
            raise SurfaceValidationError("intent payload must be a JSON object")
        expected_epoch = _uint(value["expected_source_epoch"], "expected_source_epoch", (1 << 63) - 1, minimum=1)
        expected_geometry = _uint(value["expected_geometry_revision"], "expected_geometry_revision", (1 << 63) - 1)
        optional_epochs: dict[str, int | None] = {}
        for key in ("expected_focus_epoch", "expected_input_domain_epoch", "sequence", "created_ns", "deadline_ns", "max_duration_ns"):
            item = value.get(key)
            if item is not None:
                maximum = 1 << 63 if key == "max_duration_ns" else (1 << 63) - 1
                minimum = 1 if key in {"sequence", "created_ns", "deadline_ns", "max_duration_ns"} else 0
                optional_epochs[key] = _uint(item, key, maximum, minimum=minimum)
            else:
                optional_epochs[key] = None
        if optional_epochs["max_duration_ns"] is not None and optional_epochs["max_duration_ns"] > 300_000_000_000:
            raise SurfaceValidationError("max_duration_ns exceeds the five-minute hard limit")
        if optional_epochs["deadline_ns"] is not None and optional_epochs["created_ns"] is not None and optional_epochs["deadline_ns"] <= optional_epochs["created_ns"]:
            raise SurfaceValidationError("deadline_ns must follow created_ns")
        extras: dict[str, Any] = {}
        for key in ("semantic_target", "dependency_versions", "expected_effect", "resource_reservation", "stop_conditions"):
            if key in value:
                extras[key] = json_value(value[key], max_bytes=MAX_DETAIL_BYTES, label=key)
        if "resource_reservation" in extras and not isinstance(extras["resource_reservation"], dict):
            raise SurfaceValidationError("resource_reservation must be an object")
        if "dependency_versions" in extras and not isinstance(extras["dependency_versions"], dict):
            raise SurfaceValidationError("dependency_versions must be an object")
        goal_revision = value.get("goal_revision")
        if goal_revision is not None and not isinstance(goal_revision, (str, int)):
            raise SurfaceValidationError("goal_revision must be bounded text or an integer")
        if isinstance(goal_revision, str):
            goal_revision = _text(goal_revision, "goal_revision", MAX_IDENTIFIER)
        if isinstance(goal_revision, int) and not isinstance(goal_revision, bool):
            goal_revision = _uint(goal_revision, "goal_revision", (1 << 63) - 1)
        return cls(
            operation_id, mission_id, binding_id, grant_id, operation, payload,
            expected_epoch, expected_geometry, optional_epochs["expected_focus_epoch"],
            optional_epochs["expected_input_domain_epoch"], optional_epochs["sequence"],
            optional_epochs["created_ns"], optional_epochs["deadline_ns"],
            extras.get("semantic_target"), extras.get("dependency_versions"), extras.get("expected_effect"),
            extras.get("resource_reservation"), optional_epochs["max_duration_ns"],
            extras.get("stop_conditions"), goal_revision,
        )

    def canonical(self, *, include_payload: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "operation_id": self.operation_id,
            "mission_id": self.mission_id,
            "binding_id": self.binding_id,
            "grant_id": self.grant_id,
            "operation": self.operation,
            "expected_source_epoch": self.expected_source_epoch,
            "expected_geometry_revision": self.expected_geometry_revision,
            "expected_focus_epoch": self.expected_focus_epoch,
            "expected_input_domain_epoch": self.expected_input_domain_epoch,
            "sequence": self.sequence,
            "created_ns": self.created_ns,
            "deadline_ns": self.deadline_ns,
            "semantic_target": self.semantic_target,
            "dependency_versions": self.dependency_versions,
            "expected_effect": self.expected_effect,
            "resource_reservation": self.resource_reservation,
            "max_duration_ns": self.max_duration_ns,
            "stop_conditions": self.stop_conditions,
            "goal_revision": self.goal_revision,
        }
        if include_payload:
            result["payload"] = self.payload
        return result


@dataclass(frozen=True, slots=True)
class EffectOutcome:
    disposition: str
    delivered_count: int
    ack_strength: str
    detail: Any

    @classmethod
    def from_backend(cls, value: Mapping[str, Any]) -> "EffectOutcome":
        if not isinstance(value, Mapping):
            raise SurfaceValidationError("backend dispatch result must be an object")
        disposition = _text(value.get("disposition"), "disposition", 32)
        if disposition not in {"rejected", "not-started", "partially-delivered", "delivered", "unknown"}:
            raise SurfaceValidationError("backend returned an unsupported disposition")
        delivered_count = _uint(value.get("delivered_count", 0), "delivered_count", MAX_COLLECTION_ITEMS)
        ack_strength = _text(value.get("ack_strength", "unknown"), "ack_strength", 128)
        detail_value = value.get("detail")
        if isinstance(detail_value, str):
            detail_value = _text(detail_value, "detail", MAX_DETAIL_BYTES)
        else:
            detail_value = json_value(detail_value if detail_value is not None else {}, max_bytes=MAX_DETAIL_BYTES, label="dispatch detail")
        return cls(disposition, delivered_count, ack_strength, detail_value)

    def to_dict(self) -> dict[str, Any]:
        return {"disposition": self.disposition, "delivered_count": self.delivered_count,
                "ack_strength": self.ack_strength, "detail": self.detail}
