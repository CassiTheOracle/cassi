"""Optional frozen-teacher boundary for the isolated Cassi field.

The teacher is a read-only boundary sensor. It can copy one L18 trunk residual
from the pinned local runtime or accept a caller-supplied residual, normalize it
with an explicit receipt, and lift it into a fixed deterministic complex field
wave. It has no adaptive state and never returns Qwen KV, logits, or teacher
parameters.
"""

from __future__ import annotations

import base64
import hashlib
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

try:
    from .l18_generated_token_trajectory import L18GeneratedTokenTrajectory, RuntimeConfig
except ImportError:  # pragma: no cover - direct module execution
    from l18_generated_token_trajectory import L18GeneratedTokenTrajectory, RuntimeConfig


PROTOCOL = "CassiQwen F4 frozen-teacher boundary"
VERSION = 1
PROFILE_ID = "cassi.frozen-teacher.boundary.v1"
SENSE_PROTOCOL = "cassi.field.sense-event.v1"
SENSE_VERSION = 1
FIELD_CHECKPOINT_SCHEMA = "cassi.field-intelligence.field-only-checkpoint.v1"
NORM_METHOD = "float64-l2-unit"
DEFAULT_MODE_COUNT = 512
DEFAULT_PARITY_TOLERANCE = 1.0e-6
DEFAULT_NORM_EPSILON = 1.0e-12
TRUNK_LAYER_COUNT = 64

# These names are deliberately rejected from field-only checkpoint payloads.
FIELD_CHECKPOINT_EXCLUDED_KEYS = (
    "teacher",
    "teacher_state",
    "teacher_trace",
    "teacher_traces",
    "teacher_kv",
    "teacher_logits",
    "teacher_parameters",
    "kv",
    "logits",
)


class FrozenTeacherError(ValueError):
    """A checked frozen-teacher boundary or field checkpoint failure."""


def _finite_vector(values: Any, *, label: str) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=np.float32)
    except (TypeError, ValueError) as error:
        raise FrozenTeacherError(f"{label} is not numeric") from error
    if array.ndim != 1 or array.size == 0:
        raise FrozenTeacherError(f"{label} must be a nonempty one-dimensional vector")
    if not np.isfinite(array).all():
        raise FrozenTeacherError(f"{label} contains non-finite values")
    return np.ascontiguousarray(array)


def _finite_wave(values: Any, *, wave_modes: int) -> np.ndarray:
    try:
        wave = np.asarray(values, dtype=np.float32)
    except (TypeError, ValueError) as error:
        raise FrozenTeacherError("field wave is not numeric") from error
    if wave.shape != (wave_modes, 2):
        raise FrozenTeacherError(f"field wave must have shape ({wave_modes}, 2), got {wave.shape}")
    if not np.isfinite(wave).all():
        raise FrozenTeacherError("field wave contains non-finite values")
    return np.ascontiguousarray(wave)


def _float32_bytes(values: Any) -> bytes:
    array = np.ascontiguousarray(np.asarray(values, dtype=np.float32))
    little = array.astype("<f4", copy=False)
    return little.tobytes(order="C")


def _sha256(values: Any) -> str:
    return hashlib.sha256(_float32_bytes(values)).hexdigest()


@dataclass(frozen=True)
class NormReceipt:
    """Auditable normalization metadata without retaining the residual."""

    dimension: int
    input_l2_norm: float
    normalized_l2_norm: float
    epsilon: float
    method: str
    input_sha256: str
    normalized_sha256: str

    def __post_init__(self) -> None:
        if self.dimension <= 0:
            raise FrozenTeacherError("normalization dimension must be positive")
        for name in ("input_l2_norm", "normalized_l2_norm", "epsilon"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise FrozenTeacherError(f"normalization {name} must be finite")
        if self.input_l2_norm <= 0.0 or self.normalized_l2_norm <= 0.0:
            raise FrozenTeacherError("normalization norms must be positive")
        if self.epsilon <= 0.0:
            raise FrozenTeacherError("normalization epsilon must be positive")
        if self.method != NORM_METHOD:
            raise FrozenTeacherError(f"unknown normalization method {self.method!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "input_l2_norm": self.input_l2_norm,
            "normalized_l2_norm": self.normalized_l2_norm,
            "epsilon": self.epsilon,
            "method": self.method,
            "input_sha256": self.input_sha256,
            "normalized_sha256": self.normalized_sha256,
        }


@dataclass(frozen=True)
class CaptureParityReceipt:
    """Capture-off/on parity metrics; raw logits are intentionally absent."""

    capture_off: bool
    capture_on: bool
    parity_checked: bool
    parity_pass: bool | None
    max_abs_logit_difference: float | None
    argmax_off: int | None
    argmax_on: int | None
    top_ids_match: bool | None
    tolerance: float | None
    reason: str | None = None

    @classmethod
    def not_run(cls, reason: str = "parity was not supplied") -> "CaptureParityReceipt":
        return cls(False, False, False, None, None, None, None, None, None, reason)

    @classmethod
    def from_logits(
        cls,
        logits_off: Any,
        logits_on: Any,
        *,
        tolerance: float = DEFAULT_PARITY_TOLERANCE,
        top_ids_off: Sequence[int] | None = None,
        top_ids_on: Sequence[int] | None = None,
    ) -> "CaptureParityReceipt":
        off = _finite_vector(logits_off, label="capture-off logits")
        on = _finite_vector(logits_on, label="capture-on logits")
        if off.shape != on.shape:
            raise FrozenTeacherError("capture-off and capture-on logits have different shapes")
        tolerance_value = float(tolerance)
        if not math.isfinite(tolerance_value) or tolerance_value < 0.0:
            raise FrozenTeacherError("parity tolerance must be finite and non-negative")
        difference = float(np.max(np.abs(off.astype(np.float64) - on.astype(np.float64))))
        argmax_off = int(np.argmax(off))
        argmax_on = int(np.argmax(on))
        top_match: bool | None = None
        if (top_ids_off is None) != (top_ids_on is None):
            raise FrozenTeacherError("capture parity top-id lists must be supplied together")
        if top_ids_off is not None and top_ids_on is not None:
            top_match = tuple(int(value) for value in top_ids_off) == tuple(int(value) for value in top_ids_on)
        parity_pass = (
            argmax_off == argmax_on
            and difference <= tolerance_value
            and (top_match is None or top_match)
        )
        return cls(
            capture_off=True,
            capture_on=True,
            parity_checked=True,
            parity_pass=parity_pass,
            max_abs_logit_difference=difference,
            argmax_off=argmax_off,
            argmax_on=argmax_on,
            top_ids_match=top_match,
            tolerance=tolerance_value,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_off": self.capture_off,
            "capture_on": self.capture_on,
            "parity_checked": self.parity_checked,
            "parity_pass": self.parity_pass,
            "max_abs_logit_difference": self.max_abs_logit_difference,
            "argmax_off": self.argmax_off,
            "argmax_on": self.argmax_on,
            "top_ids_match": self.top_ids_match,
            "tolerance": self.tolerance,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TeacherSenseEvent:
    """One ephemeral teacher-derived sense wave for the F3 boundary."""

    sequence_id: int
    event_index: int
    source: str
    layer_index: int | None
    residual_dimension: int
    wave: np.ndarray
    norm: NormReceipt
    capture_parity: CaptureParityReceipt
    mode_count: int
    wave_modes: int

    def __post_init__(self) -> None:
        if isinstance(self.sequence_id, bool) or not isinstance(self.sequence_id, int) or self.sequence_id < 0:
            raise FrozenTeacherError("sequence_id must be a non-negative integer")
        if isinstance(self.event_index, bool) or not isinstance(self.event_index, int) or self.event_index < 0:
            raise FrozenTeacherError("event_index must be a non-negative integer")
        if self.layer_index is not None and (self.layer_index < 0 or self.layer_index >= TRUNK_LAYER_COUNT):
            raise FrozenTeacherError("layer_index must be in the L18 trunk range 0..63")
        if self.residual_dimension <= 0:
            raise FrozenTeacherError("residual_dimension must be positive")
        if self.mode_count <= 0 or self.mode_count % 2:
            raise FrozenTeacherError("mode_count must be positive and even")
        if self.wave_modes != self.mode_count // 2:
            raise FrozenTeacherError("wave_modes must equal mode_count // 2")
        wave = _finite_wave(self.wave, wave_modes=self.wave_modes)
        object.__setattr__(self, "wave", wave)
        if self.norm.dimension != self.residual_dimension:
            raise FrozenTeacherError("normalization dimension does not match residual dimension")

    @property
    def wave_sha256(self) -> str:
        return _sha256(self.wave)

    def to_f3_command(self, *, session: str | None = None) -> dict[str, Any]:
        """Return the strict minimal F3 daemon command (no teacher metadata)."""
        command: dict[str, Any] = {"cmd": "sense", "wave": [self.wave.tolist()]}
        if session is not None:
            command["session"] = str(session)
        return command

    def to_protocol_payload(self, *, include_base64: bool = False) -> dict[str, Any]:
        """Return a JSON-safe F3 sense event with audit metadata."""
        payload: dict[str, Any] = {
            "cmd": "sense",
            "protocol": SENSE_PROTOCOL,
            "version": SENSE_VERSION,
            "profile": PROFILE_ID,
            "sequence_id": self.sequence_id,
            "event_index": self.event_index,
            "source": self.source,
            "layer_index": self.layer_index,
            "residual_dimension": self.residual_dimension,
            "mode_count": self.mode_count,
            "wave_modes": self.wave_modes,
            "wave_shape": [self.wave_modes, 2],
            "wave_dtype": "float32",
            "wave_layout": "C",
            "wave_sha256": self.wave_sha256,
            "wave": self.wave.tolist(),
            "normalization": self.norm.to_dict(),
            "capture_parity": self.capture_parity.to_dict(),
            "checkpoint": field_checkpoint_exclusion_receipt(),
        }
        if include_base64:
            payload["wave_f32_b64"] = base64.b64encode(_float32_bytes(self.wave)).decode("ascii")
        return payload

    as_dict = to_protocol_payload
    as_f3_command = to_f3_command
    to_daemon_command = to_f3_command


class FrozenFieldTeacher:
    """Stateless optional teacher boundary around the pinned L18 runtime."""

    def __init__(
        self,
        runtime_config: RuntimeConfig | None = None,
        *,
        mode_count: int = DEFAULT_MODE_COUNT,
        wave_modes: int | None = None,
        layer_index: int = 0,
        norm_epsilon: float = DEFAULT_NORM_EPSILON,
        parity_tolerance: float = DEFAULT_PARITY_TOLERANCE,
    ) -> None:
        if isinstance(mode_count, bool) or not isinstance(mode_count, int) or mode_count <= 0 or mode_count % 2:
            raise FrozenTeacherError("mode_count must be a positive even integer")
        resolved_wave_modes = mode_count // 2 if wave_modes is None else wave_modes
        if (
            isinstance(resolved_wave_modes, bool)
            or not isinstance(resolved_wave_modes, int)
            or resolved_wave_modes != mode_count // 2
        ):
            raise FrozenTeacherError("wave_modes must equal mode_count // 2")
        if isinstance(layer_index, bool) or not isinstance(layer_index, int) or not 0 <= layer_index < TRUNK_LAYER_COUNT:
            raise FrozenTeacherError("layer_index must be in the L18 trunk range 0..63")
        for name, value in (("norm_epsilon", norm_epsilon), ("parity_tolerance", parity_tolerance)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise FrozenTeacherError(f"{name} must be finite")
            if float(value) <= 0.0:
                raise FrozenTeacherError(f"{name} must be positive")
        self.runtime_config = runtime_config or RuntimeConfig()
        self.mode_count = mode_count
        self.wave_modes = resolved_wave_modes
        self.layer_index = layer_index
        self.norm_epsilon = float(norm_epsilon)
        self.parity_tolerance = float(parity_tolerance)

    @staticmethod
    def normalize_residual(
        residual: Any,
        *,
        epsilon: float = DEFAULT_NORM_EPSILON,
    ) -> tuple[np.ndarray, NormReceipt]:
        vector = _finite_vector(residual, label="hidden residual")
        epsilon_value = float(epsilon)
        if not math.isfinite(epsilon_value) or epsilon_value <= 0.0:
            raise FrozenTeacherError("normalization epsilon must be finite and positive")
        input_norm = float(np.linalg.norm(vector.astype(np.float64, copy=False)))
        if not math.isfinite(input_norm) or input_norm <= epsilon_value:
            raise FrozenTeacherError("hidden residual L2 norm must be finite and greater than epsilon")
        normalized = np.ascontiguousarray(vector / np.float32(input_norm), dtype=np.float32)
        normalized_norm = float(np.linalg.norm(normalized.astype(np.float64, copy=False)))
        receipt = NormReceipt(
            dimension=int(vector.size),
            input_l2_norm=input_norm,
            normalized_l2_norm=normalized_norm,
            epsilon=epsilon_value,
            method=NORM_METHOD,
            input_sha256=_sha256(vector),
            normalized_sha256=_sha256(normalized),
        )
        return normalized, receipt

    def capture_parity_receipt(
        self,
        logits_off: Any,
        logits_on: Any,
        *,
        top_ids_off: Sequence[int] | None = None,
        top_ids_on: Sequence[int] | None = None,
    ) -> CaptureParityReceipt:
        """Summarize the L16 capture-off/on control without retaining logits."""
        return CaptureParityReceipt.from_logits(
            logits_off,
            logits_on,
            tolerance=self.parity_tolerance,
            top_ids_off=top_ids_off,
            top_ids_on=top_ids_on,
        )

    def _lift(self, normalized: np.ndarray) -> np.ndarray:
        # The lowest DFT bins are a fixed, parameter-free real/imag lift.
        if self.wave_modes > normalized.size // 2 + 1:
            raise FrozenTeacherError(
                f"wave_modes={self.wave_modes} exceeds the available DFT bins for residual dimension "
                f"{normalized.size}"
            )
        spectrum = np.fft.rfft(normalized.astype(np.float64, copy=False))
        selected = spectrum[: self.wave_modes] / math.sqrt(float(normalized.size))
        wave = np.column_stack((selected.real, selected.imag)).astype(np.float32)
        return _finite_wave(wave, wave_modes=self.wave_modes)


    def from_residual(
        self,
        residual: Any,
        *,
        sequence_id: int = 0,
        event_index: int = 0,
        source: str = "supplied_residual",
        capture_parity: CaptureParityReceipt | None = None,
    ) -> TeacherSenseEvent:
        normalized, receipt = self.normalize_residual(residual, epsilon=self.norm_epsilon)
        wave = self._lift(normalized)
        parity = capture_parity or CaptureParityReceipt.not_run("supplied residual has no runtime parity run")
        return TeacherSenseEvent(
            sequence_id=sequence_id,
            event_index=event_index,
            source=source,
            layer_index=None,
            residual_dimension=int(normalized.size),
            wave=wave,
            norm=receipt,
            capture_parity=parity,
            mode_count=self.mode_count,
            wave_modes=self.wave_modes,
        )

    sense_from_residual = from_residual

    def capture(
        self,
        token_ids: Sequence[int] | None = None,
        *,
        positions: Sequence[int] | None = None,
        runtime: Any | None = None,
        record: Any | None = None,
        sequence_id: int = 0,
        event_index: int = 0,
        capture_parity: CaptureParityReceipt | None = None,
    ) -> TeacherSenseEvent:
        """Copy one read-only L18 trunk residual and return its sense event.

        ``runtime`` may be an already-loaded ``L18GeneratedTokenTrajectory``.
        If it is omitted, one owner is constructed from ``runtime_config`` and
        closed before this method returns. A supplied ``record`` is accepted
        for callers that already performed the decode.
        """
        owner = runtime
        owns_runtime = owner is None
        if record is None:
            if token_ids is None:
                raise FrozenTeacherError("token_ids are required when record is not supplied")
            if owns_runtime:
                try:
                    owner = L18GeneratedTokenTrajectory(self.runtime_config)
                except Exception as error:
                    raise FrozenTeacherError(f"could not construct pinned L18 runtime: {error}") from error
            try:
                record = owner.decode_initial(token_ids, positions)
            except Exception as error:
                raise FrozenTeacherError(f"L18 hidden residual capture failed: {error}") from error
        try:
            trunk = getattr(record, "trunk", None)
            if trunk is None or len(trunk) <= self.layer_index:
                raise FrozenTeacherError("L18 record does not contain the requested trunk residual")
            capture = trunk[self.layer_index]
            residual = getattr(capture, "values", None)
            if residual is None:
                raise FrozenTeacherError("L18 trunk capture has no copied values")
            parity = capture_parity or CaptureParityReceipt.not_run(
                "capture parity must be supplied by the L16 off/on control"
            )
            event = self.from_residual(
                residual,
                sequence_id=sequence_id,
                event_index=event_index,
                source="l18_hidden_residual",
                capture_parity=parity,
            )
            return TeacherSenseEvent(
                sequence_id=event.sequence_id,
                event_index=event.event_index,
                source=event.source,
                layer_index=self.layer_index,
                residual_dimension=event.residual_dimension,
                wave=event.wave,
                norm=event.norm,
                capture_parity=event.capture_parity,
                mode_count=event.mode_count,
                wave_modes=event.wave_modes,
            )
        finally:
            if owns_runtime and owner is not None:
                try:
                    owner.close(suppress=True)
                except Exception:
                    pass

    capture_hidden_residual = capture

    def sense_payload(self, residual: Any, **kwargs: Any) -> dict[str, Any]:
        return self.from_residual(residual, **kwargs).to_protocol_payload()

    def capture_payload(self, token_ids: Sequence[int], **kwargs: Any) -> dict[str, Any]:
        return self.capture(token_ids, **kwargs).to_protocol_payload()

    def sense_command(self, residual: Any, **kwargs: Any) -> dict[str, Any]:
        return self.from_residual(residual, **kwargs).to_f3_command()

    def capture_command(self, token_ids: Sequence[int], **kwargs: Any) -> dict[str, Any]:
        return self.capture(token_ids, **kwargs).to_f3_command()


def field_checkpoint_exclusion_receipt() -> dict[str, Any]:
    """Return the fixed declaration carried by field-only checkpoint writers."""
    return {
        "field_only": True,
        "teacher_data_persisted": False,
        "excluded_keys": list(FIELD_CHECKPOINT_EXCLUDED_KEYS),
    }


def _find_forbidden_checkpoint_keys(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key).lower()
            if key_text in FIELD_CHECKPOINT_EXCLUDED_KEYS:
                found.append(f"{path}.{key_text}" if path else key_text)
            found.extend(_find_forbidden_checkpoint_keys(nested, f"{path}.{key_text}" if path else key_text))
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found.extend(_find_forbidden_checkpoint_keys(nested, f"{path}[{index}]"))
    return found


def validate_field_checkpoint_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Reject payloads that could persist teacher state, KV, logits, or traces."""
    if not isinstance(payload, Mapping):
        raise FrozenTeacherError("field checkpoint payload must be a mapping")
    if "field" not in payload:
        raise FrozenTeacherError("field checkpoint payload must contain field")
    forbidden = _find_forbidden_checkpoint_keys(payload)
    if forbidden:
        raise FrozenTeacherError(f"field checkpoint contains excluded teacher data: {forbidden}")
    return dict(payload)


def field_only_checkpoint_payload(field: Any, *, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build a field-only checkpoint envelope with no teacher persistence."""
    payload: dict[str, Any] = {
        "schema": FIELD_CHECKPOINT_SCHEMA,
        "profile": PROFILE_ID,
        "field": field,
        "checkpoint": field_checkpoint_exclusion_receipt(),
    }
    if metadata is not None:
        payload["metadata"] = dict(metadata)
    return validate_field_checkpoint_payload(payload)


__all__ = [
    "CaptureParityReceipt",
    "DEFAULT_MODE_COUNT",
    "FIELD_CHECKPOINT_EXCLUDED_KEYS",
    "FIELD_CHECKPOINT_SCHEMA",
    "FrozenFieldTeacher",
    "FrozenTeacherError",
    "NormReceipt",
    "NORM_METHOD",
    "PROFILE_ID",
    "PROTOCOL",
    "SENSE_PROTOCOL",
    "SENSE_VERSION",
    "TeacherSenseEvent",
    "TRUNK_LAYER_COUNT",
    "VERSION",
    "field_checkpoint_exclusion_receipt",
    "field_only_checkpoint_payload",
    "validate_field_checkpoint_payload",
]
