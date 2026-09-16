"""Field-native raw-event acquisition over the Cassi Qi field.

This module is an isolated experiment.  It uses the fixed Qi codebook and
bounded Yang/Yin controller from ``CassiFI/prototype`` as its only adaptive
substrate: the learner's persistent value is one ``QiFieldState.field``
tensor.  Event journals, provenance, and the temporary event trace belong to
the surrounding protocol, not to the learned representation.

The experiment deliberately starts with a small, inspectable primitive. Raw
events are bounded unordered opaque byte spans. A transition is stored as a
superposition of fixed phase-conjugate waves. Emission decodes the complete
bounded packet through fixed byte-position slots and remains ``unresolved``
when field support is insufficient or ambiguous.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import struct
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, cast

import torch


# The CassiFI prototype is the fixed Qi implementation that this isolated
# experiment reuses.  Importing it by source path keeps this repo independent
# of package installation and makes the source identity checkpoint-visible.
_CASSIFI_ROOT = Path(__file__).resolve().parent.parent / "CassiFI"
if not (_CASSIFI_ROOT / "prototype" / "cassi_qi_field.py").is_file():
    raise RuntimeError(f"CassiFI prototype is unavailable at {_CASSIFI_ROOT}")
if str(_CASSIFI_ROOT / "prototype") not in sys.path:
    sys.path.insert(0, str(_CASSIFI_ROOT / "prototype"))

import cassi_qi_field as _qi_field_module  # pyright: ignore[reportMissingImports]  # noqa: E402
from cassi_qi_field import (  # pyright: ignore[reportMissingImports]  # noqa: E402
    QiFieldConfig,
    QiFieldController,
    QiFieldPhysicsConfig,
    QiFieldState,
)


_PACKET_VERSION = 1
_PACKET_MAX_SPANS = 3
_PACKET_MAX_SPAN_BYTES = 8
_PACKET_MAX_BYTES = 16
_ATOM_ALPHABET = 256
_CHECKPOINT_MAGIC = b"CASSI-RAW-EVENT-FIELD\x02"
_CHECKPOINT_SCHEMA = "cassi.raw-event-field-checkpoint.v2"
_PROFILE_SCHEMA = "cassi.raw-event-acquisition-profile.v2"
_OPERATOR_ID = "cassi.raw-event-holographic-transition.v2"
_TRACE_NONE = object()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@lru_cache(maxsize=1)
def _operator_source_sha256() -> str:
    """Bind checkpoints to the exact learner implementation bytes."""

    return _sha256(Path(__file__).read_bytes())

def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _finite_float(name: str, value: Any, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return result


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _sha_tensor(field: torch.Tensor) -> str:
    owned = field.detach().to(device="cpu", dtype=torch.float64).contiguous()
    return _sha256(owned.numpy().tobytes(order="C"))


def encode_packet(spans: Sequence[bytes]) -> bytes:
    """Encode bounded opaque spans with deterministic length framing.

    The order supplied by the caller is retained in the wire payload.  The
    learner's semantic wave canonicalizes spans before sensing, so argument
    presentation order is deliberately not a semantic signal.
    """

    if isinstance(spans, (bytes, bytearray, memoryview)) or not isinstance(spans, Sequence):
        raise ValueError("spans must be a sequence of byte spans")
    if not 1 <= len(spans) <= _PACKET_MAX_SPANS:
        raise ValueError(f"a packet requires 1..{_PACKET_MAX_SPANS} spans")
    output = bytearray((_PACKET_VERSION, len(spans)))
    for index, span in enumerate(spans):
        if not isinstance(span, (bytes, bytearray, memoryview)):
            raise ValueError(f"span {index} must be bytes-like")
        owned = bytes(span)
        if not 1 <= len(owned) <= _PACKET_MAX_SPAN_BYTES:
            raise ValueError(
                f"span {index} must contain 1..{_PACKET_MAX_SPAN_BYTES} bytes"
            )
        output.extend(struct.pack(">H", len(owned)))
        output.extend(owned)
    if len(output) > _PACKET_MAX_BYTES:
        raise ValueError(
            f"encoded packet is {len(output)} bytes; limit is {_PACKET_MAX_BYTES}"
        )
    return bytes(output)


def decode_packet(payload: bytes | bytearray | memoryview) -> tuple[bytes, ...]:
    """Validate and decode one bounded packet."""

    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise ValueError("packet payload must be bytes-like")
    owned = bytes(payload)
    if not 3 <= len(owned) <= _PACKET_MAX_BYTES:
        raise ValueError("packet payload has an invalid bounded length")
    if owned[0] != _PACKET_VERSION:
        raise ValueError("packet version mismatch")
    count = owned[1]
    if not 1 <= count <= _PACKET_MAX_SPANS:
        raise ValueError("packet span count is outside the fixed bound")
    offset = 2
    spans: list[bytes] = []
    for index in range(count):
        if offset + 2 > len(owned):
            raise ValueError(f"packet ends before span {index} length")
        span_size = struct.unpack(">H", owned[offset : offset + 2])[0]
        offset += 2
        if not 1 <= span_size <= _PACKET_MAX_SPAN_BYTES:
            raise ValueError(f"span {index} length is outside the fixed bound")
        if offset + span_size > len(owned):
            raise ValueError(f"packet ends before span {index} data")
        spans.append(owned[offset : offset + span_size])
        offset += span_size
    if offset != len(owned):
        raise ValueError("packet contains trailing bytes")
    return tuple(spans)


def canonical_packet(payload: bytes | bytearray | memoryview) -> bytes:
    """Return the semantic packet identity with unordered spans canonicalized."""

    spans = decode_packet(payload)
    return encode_packet(tuple(sorted(spans)))


def atom_packet(value: int | bytes | bytearray | memoryview) -> bytes:
    """Encode one byte as the fixed atomic emission packet."""

    if isinstance(value, int):
        if not 0 <= value < _ATOM_ALPHABET:
            raise ValueError("atom integer must be in [0, 255]")
        owned = bytes((value,))
    elif isinstance(value, (bytes, bytearray, memoryview)):
        owned = bytes(value)
        if len(owned) != 1:
            raise ValueError("atom bytes must contain exactly one byte")
    else:
        raise ValueError("atom must be an integer or one byte")
    return encode_packet((owned,))




def _payload_digest(payload: bytes) -> str:
    return _sha256(canonical_packet(payload))


@dataclass(frozen=True, slots=True)
class AcquisitionProfile:
    """Fixed acquisition law and bounded field capacity.

    ``wave_width`` is the number of complex phase modes.  The underlying Qi
    tensor therefore has ``2 * wave_width`` modes per component.  The default
    512-mode wave gives ample fixed-codebook separation without introducing a
    learned projection.
    """

    wave_width: int = 512
    payload_limit: int = _PACKET_MAX_BYTES
    trace_horizon: int = 2
    energy_limit: float = 32.0
    provisional_gain: float = 0.08
    consolidation_gain: float = 0.08
    minimum_memory_norm: float = 0.025
    minimum_score: float = 0.58
    minimum_margin: float = 0.08
    dynamic_steps: int = 1

    def __post_init__(self) -> None:
        width = _positive_int("wave_width", self.wave_width)
        if width < 16 or width > 4096 or width % 2:
            raise ValueError("wave_width must be an even value in [16, 4096]")
        payload_limit = _positive_int("payload_limit", self.payload_limit)
        if payload_limit > _PACKET_MAX_BYTES:
            raise ValueError(f"payload_limit cannot exceed {_PACKET_MAX_BYTES}")
        horizon = _positive_int("trace_horizon", self.trace_horizon)
        if horizon > 16:
            raise ValueError("trace_horizon exceeds the fixed protocol bound")
        energy_limit = _finite_float("energy_limit", self.energy_limit, minimum=1.0e-9)
        for name in ("provisional_gain", "consolidation_gain"):
            gain = _finite_float(name, getattr(self, name), minimum=0.0)
            if gain > 0.25:
                raise ValueError(f"{name} exceeds the bounded admission gain")
        for name in ("minimum_memory_norm", "minimum_score", "minimum_margin"):
            value = _finite_float(name, getattr(self, name), minimum=0.0)
            if value > 1.0:
                raise ValueError(f"{name} must be <= 1")
        dynamic_steps = _positive_int("dynamic_steps", self.dynamic_steps)
        if dynamic_steps > 8:
            raise ValueError("dynamic_steps exceeds the fixed work bound")
        object.__setattr__(self, "wave_width", width)
        object.__setattr__(self, "payload_limit", payload_limit)
        object.__setattr__(self, "trace_horizon", horizon)
        object.__setattr__(self, "energy_limit", energy_limit)
        object.__setattr__(self, "provisional_gain", float(self.provisional_gain))
        object.__setattr__(self, "consolidation_gain", float(self.consolidation_gain))
        object.__setattr__(self, "minimum_memory_norm", float(self.minimum_memory_norm))
        object.__setattr__(self, "minimum_score", float(self.minimum_score))
        object.__setattr__(self, "minimum_margin", float(self.minimum_margin))
        object.__setattr__(self, "dynamic_steps", dynamic_steps)

    @property
    def mode_count(self) -> int:
        return self.wave_width * 2

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": _PROFILE_SCHEMA,
            "operator_id": _OPERATOR_ID,
            "wave_width": self.wave_width,
            "mode_count": self.mode_count,
            "payload_limit": self.payload_limit,
            "trace_horizon": self.trace_horizon,
            "energy_limit": self.energy_limit,
            "provisional_gain": self.provisional_gain,
            "consolidation_gain": self.consolidation_gain,
            "minimum_memory_norm": self.minimum_memory_norm,
            "minimum_score": self.minimum_score,
            "minimum_margin": self.minimum_margin,
            "dynamic_steps": self.dynamic_steps,
            "packet": {
                "version": _PACKET_VERSION,
                "max_spans": _PACKET_MAX_SPANS,
                "max_span_bytes": _PACKET_MAX_SPAN_BYTES,
                "max_bytes": _PACKET_MAX_BYTES,
                "semantic_order": "unordered-spans-event-order",
            },
        }

    @property
    def fingerprint(self) -> str:
        return _sha256(_canonical_json(self.as_dict()))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AcquisitionProfile":
        if not isinstance(value, Mapping):
            raise ValueError("acquisition profile must be a mapping")
        payload = dict(value)
        if payload.get("schema") != _PROFILE_SCHEMA:
            raise ValueError("acquisition profile schema mismatch")
        if payload.get("operator_id") != _OPERATOR_ID:
            raise ValueError("acquisition operator identity mismatch")
        packet = payload.pop("packet", None)
        if packet != {
            "version": _PACKET_VERSION,
            "max_spans": _PACKET_MAX_SPANS,
            "max_span_bytes": _PACKET_MAX_SPAN_BYTES,
            "max_bytes": _PACKET_MAX_BYTES,
            "semantic_order": "unordered-spans-event-order",
        }:
            raise ValueError("packet contract mismatch")
        payload.pop("schema", None)
        payload.pop("operator_id", None)
        expected = {
            "wave_width",
            "mode_count",
            "payload_limit",
            "trace_horizon",
            "energy_limit",
            "provisional_gain",
            "consolidation_gain",
            "minimum_memory_norm",
            "minimum_score",
            "minimum_margin",
            "dynamic_steps",
        }
        if set(payload) != expected:
            raise ValueError("acquisition profile fields do not match the fixed schema")
        mode_count = payload.pop("mode_count")
        profile = cls(**payload)
        if profile.mode_count != mode_count or profile.as_dict() != dict(value):
            raise ValueError("acquisition profile materialization mismatch")
        return profile


@dataclass(frozen=True, slots=True)
class RawEvent:
    """One framed world event; provenance is never used as a field coordinate."""

    seq: int
    kind: str
    payload: bytes = b""
    ref: int | None = None
    channel: str = "world"

    def __post_init__(self) -> None:
        seq = _positive_int("event seq", self.seq)
        if self.kind not in {"reset", "observation", "action", "goal"}:
            raise ValueError("event kind must be reset, observation, action, or goal")
        if not isinstance(self.payload, (bytes, bytearray, memoryview)):
            raise ValueError("event payload must be bytes-like")
        payload = bytes(self.payload)
        if self.kind == "reset":
            if payload:
                raise ValueError("reset events do not carry a payload")
        else:
            decode_packet(payload)
        if self.ref is not None:
            _positive_int("event ref", self.ref)
        if not isinstance(self.channel, str) or not self.channel:
            raise ValueError("event channel must be a nonempty string")
        object.__setattr__(self, "seq", seq)
        object.__setattr__(self, "payload", payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "payload_hex": self.payload.hex(),
            "ref": self.ref,
            "channel": self.channel,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RawEvent":
        if not isinstance(value, Mapping):
            raise ValueError("raw event must be a mapping")
        expected = {"seq", "kind", "payload_hex", "ref", "channel"}
        if set(value) != expected:
            raise ValueError("raw event fields do not match the fixed schema")
        payload_hex = value["payload_hex"]
        if not isinstance(payload_hex, str):
            raise ValueError("payload_hex must be a string")
        try:
            payload = bytes.fromhex(payload_hex)
        except ValueError as exc:
            raise ValueError("payload_hex is not hexadecimal") from exc
        return cls(
            seq=value["seq"],
            kind=value["kind"],
            payload=payload,
            ref=value["ref"],
            channel=value["channel"],
        )


class CapacityError(ValueError):
    """The fixed field bound rejected a candidate update."""


class EventError(ValueError):
    """A raw event or field query violates the acquisition contract."""


class CheckpointError(ValueError):
    """A checkpoint is malformed or belongs to another fixed profile."""


@lru_cache(maxsize=8)
def _qi_profile_source_sha256() -> str:
    module_path = cast(str | None, _qi_field_module.__file__)
    if module_path is None:
        raise RuntimeError("CassiFI Qi source has no file identity")
    return _sha256(Path(module_path).resolve().read_bytes())


@lru_cache(maxsize=8)
def _controller_for(profile: AcquisitionProfile) -> QiFieldController:
    physics = QiFieldPhysicsConfig(
        dt=0.005,
        fast_omega2=0.08,
        slow_omega2=0.02,
        fast_damping=0.20,
        slow_damping=0.075,
        nonlinear_gain=0.002,
        max_mode_amplitude=0.5,
        max_mean_energy=profile.energy_limit,
        correction_epsilon=1.0e-6,
        velocity_weight=0.05,
    )
    config = QiFieldConfig(
        scale_count=4,
        mode_count=profile.mode_count,
        alphabet_size=260,
        phi=float(getattr(_qi_field_module, "_DEFAULT_PHI", (1.0 + math.sqrt(5.0)) / 2.0)),
        energy_floor=1.0e-9,
        read_floor=0.05,
        emission_floor=1.0e-9,
        epsilon_clip=0.5,
        sense_gain=1.0,
        correction_gain=0.5,
        consolidation_gain=0.25,
        write_trust_floor=0.05,
        settle_steps=1,
        consolidation_steps=1,
        physics=physics,
    )
    return QiFieldController(config)


@dataclass(slots=True)
class _PendingAction:
    observation: bytes
    action: bytes
    history: bytes | None
    prediction: dict[str, Any]
    event_seq: int


class RawEventLearner:
    """A bounded field-native raw-event learner.

    Only ``state.field`` is adaptive and checkpointed.  ``_current_observation``,
    ``_last_action``, ``_trace_age``, and ``_pending`` are ephemeral protocol
    context needed to associate the next observation with an action.  They are
    reconstructed by the persistence layer from the raw journal and are never
    serialized into the learned field checkpoint.
    """

    def __init__(
        self,
        profile: AcquisitionProfile | None = None,
        *,
        state: QiFieldState | None = None,
    ) -> None:
        self.profile = profile or AcquisitionProfile()
        self._controller = _controller_for(self.profile)
        self._qi_config = self._controller.config
        owned_state = (
            self._controller.initial_state(1, device="cpu", dtype=torch.float64)
            if state is None
            else state
        )
        if not isinstance(owned_state, QiFieldState):
            raise EventError("state must be a QiFieldState")
        self._validate_field(owned_state.field)
        self.state = QiFieldState(
            owned_state.field.detach().to(device="cpu", dtype=torch.float64).clone()
        )
        self._current_observation: bytes | None = None
        self._last_action: bytes | None = None
        self._trace_age: int | None = None
        self._pending: _PendingAction | None = None

    @property
    def controller(self) -> QiFieldController:
        return self._controller

    @property
    def field(self) -> torch.Tensor:
        return self.state.field

    @property
    def current_observation(self) -> bytes | None:
        return self._current_observation

    def _validate_payload(self, payload: bytes | bytearray | memoryview) -> bytes:
        try:
            owned = bytes(payload)
            if len(owned) > self.profile.payload_limit:
                raise ValueError("payload exceeds the acquisition profile limit")
            decode_packet(owned)
            return owned
        except Exception as exc:
            raise EventError(f"invalid event payload: {exc}") from exc

    def _validate_field(self, field: torch.Tensor) -> None:
        if not torch.is_tensor(field):
            raise CapacityError("field candidate must be a tensor")
        try:
            state = QiFieldState(field)
            state.validate(
                self._qi_config,
                device=torch.device("cpu"),
                dtype=torch.float64,
            )
        except Exception as exc:
            raise CapacityError(f"field candidate failed fixed Qi validation: {exc}") from exc
        if not bool(torch.isfinite(field).all().item()):
            raise CapacityError("field candidate contains non-finite values")
        max_abs = float(field.abs().max().item()) if field.numel() else 0.0
        if max_abs > 0.5000000001:
            raise CapacityError("field candidate exceeds the 0.5 component bound")
        mean_energy = float(field.square().mean().item())
        if mean_energy > self.profile.energy_limit + 1.0e-10:
            raise CapacityError("field candidate exceeds the declared energy bound")

    def _parts(self, field: torch.Tensor) -> torch.Tensor:
        return field.reshape(4, 9, self.profile.mode_count, 1)

    def _differential(self, field: torch.Tensor, scale: int) -> tuple[torch.Tensor, torch.Tensor]:
        parts = self._parts(field)
        phi = float(self._qi_config.phi)
        return (
            parts[scale, 0, : self.profile.wave_width, 0]
            - phi * parts[scale, 2, : self.profile.wave_width, 0],
            parts[scale, 1, : self.profile.wave_width, 0]
            - phi * parts[scale, 3, : self.profile.wave_width, 0],
        )

    def _set_differential(
        self,
        field: torch.Tensor,
        scale: int,
        delta_re: torch.Tensor,
        delta_im: torch.Tensor,
    ) -> None:
        parts = self._parts(field)
        phi = float(self._qi_config.phi)
        denominator = 1.0 + phi * phi
        parts[scale, 0, : self.profile.wave_width, 0].add_(delta_re / denominator)
        parts[scale, 1, : self.profile.wave_width, 0].add_(delta_im / denominator)
        parts[scale, 2, : self.profile.wave_width, 0].add_(-phi * delta_re / denominator)
        parts[scale, 3, : self.profile.wave_width, 0].add_(-phi * delta_im / denominator)

    @staticmethod
    def _complex_mul(
        left_re: torch.Tensor,
        left_im: torch.Tensor,
        right_re: torch.Tensor,
        right_im: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        return (
            left_re * right_re - left_im * right_im,
            left_re * right_im + left_im * right_re,
        )

    @staticmethod
    def _complex_conj_mul(
        left_re: torch.Tensor,
        left_im: torch.Tensor,
        right_re: torch.Tensor,
        right_im: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        return (
            left_re * right_re + left_im * right_im,
            left_re * right_im - left_im * right_re,
        )

    def _packet_wave(
        self, payload: bytes, *, role: int
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Map a packet to a fixed pseudo-orthogonal Qi-codebook wave."""

        if role == 3:
            return self._output_packet_wave(payload)
        if role not in (0, 1, 2):
            raise EventError("packet wave role is outside the fixed codec")
        owned = canonical_packet(payload)
        domain = b"cassi.raw-event.packet-wave.v1\\x00" + bytes((role,)) + owned
        digest = hashlib.shake_256(domain).digest(self.profile.wave_width * 2)
        indices = torch.tensor(
            [
                int.from_bytes(digest[offset : offset + 2], "little") % 260
                for offset in range(0, len(digest), 2)
            ],
            dtype=torch.int64,
        )
        positions = torch.arange(self.profile.wave_width, dtype=torch.int64)
        codebook = self._controller.codebook(
            0, device="cpu", dtype=torch.float64
        )
        selected = codebook[indices, positions]
        return selected[:, 0], selected[:, 1]

    def _output_packet_wave(
        self, payload: bytes
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode every canonical packet byte in a fixed disjoint mode slot."""
        owned = canonical_packet(payload)
        if len(owned) > self.profile.payload_limit:
            raise EventError("output packet exceeds the fixed payload limit")
        terminator = 259
        symbols = list(owned) + [terminator] * (
            self.profile.payload_limit - len(owned)
        )
        codebook = self._controller.codebook(
            0, device="cpu", dtype=torch.float64
        )
        slot_width = self.profile.wave_width // self.profile.payload_limit
        real = torch.empty(self.profile.wave_width, dtype=torch.float64)
        imag = torch.empty(self.profile.wave_width, dtype=torch.float64)
        for slot, symbol in enumerate(symbols):
            start = slot * slot_width
            end = (
                self.profile.wave_width
                if slot + 1 == self.profile.payload_limit
                else start + slot_width
            )
            real[start:end] = codebook[symbol, start:end, 0]
            imag[start:end] = codebook[symbol, start:end, 1]
        return real, imag
    def _decode_output_wave(
        self, real: torch.Tensor, imag: torch.Tensor
    ) -> tuple[bytes | None, float, float, str]:
        """Decode a bounded packet without an outcome candidate list."""
        codebook = self._controller.codebook(
            0, device="cpu", dtype=torch.float64
        )
        candidate_ids = torch.tensor(
            list(range(_ATOM_ALPHABET)) + [259], dtype=torch.int64
        )
        candidates = codebook.index_select(0, candidate_ids)
        slot_width = self.profile.wave_width // self.profile.payload_limit
        decoded = bytearray()
        scores: list[float] = []
        margins: list[float] = []
        terminated = False
        for slot in range(self.profile.payload_limit):
            start = slot * slot_width
            end = (
                self.profile.wave_width
                if slot + 1 == self.profile.payload_limit
                else start + slot_width
            )
            slot_re = real[start:end]
            slot_im = imag[start:end]
            norm = math.sqrt(
                float((slot_re.square() + slot_im.square()).mean().item())
            )
            if norm <= 1.0e-12:
                return None, 0.0, 0.0, "field-output-slot-has-zero-norm"
            slot_scores = (
                slot_re.reshape(1, -1) * candidates[:, start:end, 0]
                + slot_im.reshape(1, -1) * candidates[:, start:end, 1]
            ).mean(dim=1) / norm
            top_values, top_indices = torch.topk(slot_scores, k=2)
            score = float(top_values[0].item())
            margin = score - float(top_values[1].item())
            scores.append(score)
            margins.append(margin)
            symbol = int(candidate_ids[int(top_indices[0].item())].item())
            if symbol == 259:
                terminated = True
                break
            decoded.append(symbol)
        if not terminated and len(decoded) != self.profile.payload_limit:
            return (
                None,
                sum(scores) / len(scores),
                min(margins),
                "field-output-has-no-terminator",
            )
        try:
            payload = canonical_packet(bytes(decoded))
        except Exception:
            return (
                None,
                sum(scores) / len(scores),
                min(margins),
                "field-output-packet-is-invalid",
            )
        return (
            payload,
            sum(scores) / len(scores),
            min(margins),
            "field-supported-packet",
        )
    def _key_wave(
        self,
        observation: bytes,
        action: bytes,
        history: bytes | None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        obs_re, obs_im = self._packet_wave(observation, role=0)
        action_re, action_im = self._packet_wave(action, role=1)
        key_re, key_im = self._complex_mul(obs_re, obs_im, action_re, action_im)
        if history is not None:
            history_re, history_im = self._packet_wave(history, role=2)
            key_re, key_im = self._complex_mul(key_re, key_im, history_re, history_im)
        magnitude = torch.sqrt(key_re.square() + key_im.square()).clamp_min(1.0e-12)
        return key_re / magnitude, key_im / magnitude

    def _read_memory(
        self,
        field: torch.Tensor,
        *,
        history: bytes | None,
    ) -> tuple[torch.Tensor, torch.Tensor, float, tuple[int, int]]:
        scales = (3, 2) if history is not None else (1, 0)
        first_re, first_im = self._differential(field, scales[0])
        second_re, second_im = self._differential(field, scales[1])
        memory_re = first_re + second_re
        memory_im = first_im + second_im
        norm = math.sqrt(float((memory_re.square() + memory_im.square()).mean().item()))
        return memory_re, memory_im, norm, scales

    def _read_query_field(self, *, dynamic: bool) -> torch.Tensor:
        if not dynamic:
            return self.state.field
        try:
            evolved = self._controller.evolve(
                QiFieldState(self.state.field.clone()),
                steps=self.profile.dynamic_steps,
            )
        except Exception as exc:
            raise EventError(f"dynamic field read failed: {type(exc).__name__}: {exc}") from exc
        self._validate_field(evolved.field)
        return evolved.field

    @staticmethod
    def _abstract_transition_packets(
        observation: bytes, outcome: bytes
    ) -> tuple[bytes, bytes] | None:
        """Extract one changed span while preserving shared entity spans."""

        before = list(sorted(decode_packet(observation)))
        after = list(sorted(decode_packet(outcome)))
        remaining_after = list(after)
        removed: list[bytes] = []
        shared = 0
        for span in before:
            if span in remaining_after:
                remaining_after.remove(span)
                shared += 1
            else:
                removed.append(span)
        if shared < 1 or len(removed) != 1 or len(remaining_after) != 1:
            return None
        return encode_packet((removed[0],)), encode_packet((remaining_after[0],))

    def _predict_internal(
        self,
        observation: bytes,
        action: bytes,
        history: bytes | None,
        *,
        dynamic: bool,
        relational: bool = True,
    ) -> dict[str, Any]:
        observation = self._validate_payload(observation)
        action = self._validate_payload(action)
        if history is not None:
            history = self._validate_payload(history)
        if relational:
            spans = list(sorted(decode_packet(observation)))
            if len(spans) > 1:
                supported: list[tuple[int, bytes, dict[str, Any]]] = []
                for index, span in enumerate(spans):
                    singleton = encode_packet((span,))
                    candidate = self._predict_internal(
                        singleton,
                        action,
                        history,
                        dynamic=dynamic,
                        relational=False,
                    )
                    if (
                        candidate["status"] == "supported"
                        and candidate["payload_hex"] is not None
                    ):
                        supported.append(
                            (
                                index,
                                bytes.fromhex(str(candidate["payload_hex"])),
                                candidate,
                            )
                        )
                if len(supported) == 1:
                    index, replacement, candidate = supported[0]
                    output_spans = list(spans)
                    output_spans.pop(index)
                    output_spans.extend(decode_packet(replacement))
                    payload = encode_packet(tuple(sorted(output_spans)))
                    return {
                        **candidate,
                        "payload_hex": payload.hex(),
                        "reason": "field-supported-copy-binding",
                        "copy_binding": {
                            "preserved_spans": len(spans) - 1,
                            "changed_span_index": index,
                            "fixed_operator": True,
                        },
                    }
                if len(supported) > 1:
                    return {
                        "status": "unresolved",
                        "payload_hex": None,
                        "reason": "copy-binding-is-ambiguous",
                        "score": min(
                            float(row[2]["score"]) for row in supported
                        ),
                        "margin": 0.0,
                        "memory_norm": max(
                            float(row[2]["memory_norm"]) for row in supported
                        ),
                        "bank": (
                            "temporal" if history is not None else "ordinary"
                        ),
                        "scales": [3, 2] if history is not None else [1, 0],
                        "dynamic": bool(dynamic),
                        "observation_sha256": _payload_digest(observation),
                        "action_sha256": _payload_digest(action),
                        "history_sha256": (
                            None
                            if history is None
                            else _payload_digest(history)
                        ),
                        "depth": None,
                    }
        field = self._read_query_field(dynamic=dynamic)
        key_re, key_im = self._key_wave(observation, action, history)
        memory_re, memory_im, norm, scales = self._read_memory(field, history=history)
        base: dict[str, Any] = {
            "status": "unresolved",
            "payload_hex": None,
            "reason": "",
            "score": None,
            "margin": None,
            "memory_norm": norm,
            "bank": "temporal" if history is not None else "ordinary",
            "scales": list(scales),
            "dynamic": bool(dynamic),
            "observation_sha256": _payload_digest(observation),
            "action_sha256": _payload_digest(action),
            "history_sha256": None if history is None else _payload_digest(history),
            "depth": None,
        }
        if norm < self.profile.minimum_memory_norm:
            base["reason"] = "field-memory-below-support-floor"
            return base
        query_re, query_im = self._complex_mul(key_re, key_im, memory_re, memory_im)
        query_norm = math.sqrt(float((query_re.square() + query_im.square()).mean().item()))
        if query_norm <= 1.0e-12:
            base["reason"] = "field-query-has-zero-norm"
            return base
        payload, top_score, margin, decode_reason = self._decode_output_wave(
            query_re, query_im
        )
        base["score"] = top_score
        base["margin"] = margin
        if top_score < self.profile.minimum_score:
            base["reason"] = "field-emission-score-below-floor"
            return base
        if margin < self.profile.minimum_margin:
            base["reason"] = "field-emission-is-ambiguous"
            return base
        if payload is None:
            base["reason"] = decode_reason
            return base
        base.update(
            {
                "status": "supported",
                "payload_hex": payload.hex(),
                "reason": decode_reason,
                "depth": 1,
            }
        )
        return base

    def _history_for_next_action(self) -> bytes | None:
        if self._last_action is None or self._trace_age is None:
            return None
        if self._trace_age >= self.profile.trace_horizon:
            return None
        return self._last_action

    def predict(
        self,
        action: bytes,
        *,
        observation: bytes | None = None,
        history: bytes | None | object = _TRACE_NONE,
        dynamic: bool = True,
    ) -> dict[str, Any]:
        """Read one field-predicted outcome without mutating the field."""

        if observation is None:
            observation = self._current_observation
        if observation is None:
            return {
                "status": "unresolved",
                "payload_hex": None,
                "reason": "no-current-observation",
                "score": None,
                "margin": None,
                "memory_norm": 0.0,
                "bank": "ordinary",
                "scales": [1, 0],
                "dynamic": bool(dynamic),
                "depth": None,
            }
        if history is _TRACE_NONE:
            history = self._history_for_next_action()
        if history is not None and not isinstance(history, (bytes, bytearray, memoryview)):
            raise EventError("history must be bytes-like or None")
        return self._predict_internal(
            observation,
            action,
            None if history is None else bytes(history),
            dynamic=dynamic,
        )

    def _write_relation(
        self,
        state: QiFieldState,
        *,
        observation: bytes,
        action: bytes,
        history: bytes | None,
        outcome: bytes,
        scale: int,
        gain: float,
    ) -> QiFieldState:
        candidate = state.field.detach().clone()
        abstract = self._abstract_transition_packets(observation, outcome)
        if abstract is not None:
            observation, outcome = abstract
        key_re, key_im = self._key_wave(observation, action, history)
        out_re, out_im = self._packet_wave(outcome, role=3)
        relation_re, relation_im = self._complex_conj_mul(key_re, key_im, out_re, out_im)
        self._set_differential(candidate, scale, gain * relation_re, gain * relation_im)
        self._validate_field(candidate)
        return QiFieldState(candidate)

    def _advance_candidate(self, state: QiFieldState) -> QiFieldState:
        try:
            advanced = self._controller.evolve(state, steps=self.profile.dynamic_steps)
        except Exception as exc:
            raise CapacityError(f"fixed Qi evolution rejected the candidate: {exc}") from exc
        self._validate_field(advanced.field)
        return advanced

    def _same_payload(self, left: bytes, right: bytes) -> bool:
        return canonical_packet(left) == canonical_packet(right)

    def _context_copy(self) -> tuple[bytes | None, bytes | None, int | None, _PendingAction | None]:
        pending = self._pending
        pending_copy = None
        if pending is not None:
            pending_copy = _PendingAction(
                observation=pending.observation,
                action=pending.action,
                history=pending.history,
                prediction=copy.deepcopy(pending.prediction),
                event_seq=pending.event_seq,
            )
        return self._current_observation, self._last_action, self._trace_age, pending_copy

    def _restore_context(
        self,
        value: tuple[bytes | None, bytes | None, int | None, _PendingAction | None],
    ) -> None:
        self._current_observation, self._last_action, self._trace_age, self._pending = value

    def apply(
        self,
        event: RawEvent,
        *,
        learn: bool = True,
        promote: bool = True,
    ) -> dict[str, Any]:
        """Consume one event exactly once and return a measured receipt.

        The method is transactional at the learner boundary: if admission,
        field mutation, evolution, or validation fails, both the tensor and the
        ephemeral event context are restored to their predecessors.
        """

        if not isinstance(event, RawEvent):
            raise EventError("apply requires a RawEvent")
        if not isinstance(learn, bool) or not isinstance(promote, bool):
            raise EventError("learn and promote must be booleans")
        if event.kind != "reset":
            self._validate_payload(event.payload)
        predecessor = self.fingerprint()
        old_field = self.state.field.clone()
        old_context = self._context_copy()
        receipt: dict[str, Any] = {
            "schema": "cassi.raw-event-transition-receipt.v1",
            "event": event.to_dict(),
            "learn_requested": learn,
            "promote_requested": promote,
            "predecessor_state_sha256": predecessor,
            "successor_state_sha256": predecessor,
            "learned": False,
            "promoted": False,
            "prediction_before_outcome": None,
            "reason": "",
        }
        try:
            if event.kind == "reset":
                discarded = self._pending is not None
                self._current_observation = None
                self._last_action = None
                self._trace_age = None
                self._pending = None
                receipt.update(
                    {
                        "reason": "trace-reset",
                        "discarded_incomplete_action": discarded,
                    }
                )

            elif event.kind == "observation":
                observation = event.payload
                if self._pending is None:
                    self._current_observation = observation
                    self._last_action = None
                    self._trace_age = None
                    receipt["reason"] = "observation-established"
                else:
                    pending = self._pending
                    receipt["prediction_before_outcome"] = copy.deepcopy(pending.prediction)
                    if learn:
                        provisional_scale = 2 if pending.history is not None else 0
                        consolidated_scale = 3 if pending.history is not None else 1
                        candidate = self._write_relation(
                            self.state,
                            observation=pending.observation,
                            action=pending.action,
                            history=pending.history,
                            outcome=observation,
                            scale=provisional_scale,
                            gain=self.profile.provisional_gain,
                        )
                        # The witnessed outcome itself is the evidence for
                        # promotion.  ``promote=False`` keeps the same event
                        # provisional for the explicit control arm.
                        promoted = promote
                        if promoted:
                            candidate = self._write_relation(
                                candidate,
                                observation=pending.observation,
                                action=pending.action,
                                history=pending.history,
                                outcome=observation,
                                scale=consolidated_scale,
                                gain=self.profile.consolidation_gain,
                            )
                        candidate = self._advance_candidate(candidate)
                        self.state = candidate
                        receipt["learned"] = True
                        receipt["promoted"] = promoted
                        receipt["reason"] = "transition-admitted"
                    else:
                        receipt["reason"] = "inference-only-outcome-not-admitted"
                    self._current_observation = observation
                    self._last_action = pending.action
                    self._trace_age = 0
                    self._pending = None
                    receipt["outcome_payload_hex"] = observation.hex()

            elif event.kind == "action":
                if self._current_observation is None:
                    raise EventError("action requires a current observation")
                if self._pending is not None:
                    raise EventError("an action is pending its outcome")
                history = self._history_for_next_action()
                prediction = self._predict_internal(
                    self._current_observation,
                    event.payload,
                    history,
                    dynamic=True,
                )
                self._pending = _PendingAction(
                    observation=self._current_observation,
                    action=event.payload,
                    history=history,
                    prediction=prediction,
                    event_seq=event.seq,
                )
                receipt.update(
                    {
                        "prediction_before_outcome": copy.deepcopy(prediction),
                        "reason": "action-bound-to-next-observation",
                    }
                )

            elif event.kind == "goal":
                receipt.update(
                    {
                        "goal_payload_hex": event.payload.hex(),
                        "reason": "goal-is-an-external-query",
                    }
                )
                if self._trace_age is not None:
                    self._trace_age += 1
                    if self._trace_age >= self.profile.trace_horizon:
                        self._last_action = None
                        self._trace_age = None

            receipt["successor_state_sha256"] = self.fingerprint()
            receipt["field_snapshot"] = self.snapshot()
            return receipt
        except Exception:
            self.state = QiFieldState(old_field)
            self._restore_context(old_context)
            raise

    def choose(
        self,
        actions: Sequence[bytes],
        goal: bytes,
        *,
        observation: bytes | None = None,
        history: bytes | None | object = _TRACE_NONE,
        max_depth: int = 3,
        max_expansions: int = 32,
        dynamic: bool = True,
    ) -> dict[str, Any]:
        """Compose field-predicted transitions through authorized actions."""

        if isinstance(actions, (bytes, bytearray, memoryview)) or not isinstance(actions, Sequence):
            raise EventError("actions must be a sequence of packets")
        max_depth = _positive_int("max_depth", max_depth)
        max_expansions = _positive_int("max_expansions", max_expansions)
        if max_depth > 8 or max_expansions > 256:
            raise EventError("planner bounds exceed the fixed work limit")
        if observation is None:
            observation = self._current_observation
        if observation is None:
            return {
                "status": "unresolved",
                "action_hex": None,
                "plan_hex": [],
                "expanded": 0,
                "reason": "no-current-observation",
                "goal_hex": None,
            }
        observation = self._validate_payload(observation)
        goal = self._validate_payload(goal)
        if history is _TRACE_NONE:
            resolved_history: bytes | None = None
        elif history is None:
            resolved_history = None
        else:
            resolved_history = self._validate_payload(cast(bytes, history))
        action_packets = tuple(self._validate_payload(action) for action in actions)
        if not action_packets:
            return {
                "status": "unresolved",
                "action_hex": None,
                "plan_hex": [],
                "expanded": 0,
                "reason": "no-authorized-actions",
                "goal_hex": goal.hex(),
            }
        expanded = 0
        capacity_hit = False

        def search(
            current: bytes,
            trace: bytes | None,
            depth: int,
            plan: tuple[bytes, ...],
        ) -> tuple[bytes, ...] | None:
            nonlocal expanded, capacity_hit
            if self._same_payload(current, goal):
                return plan
            if depth >= max_depth:
                return None
            for action in action_packets:
                if expanded >= max_expansions:
                    capacity_hit = True
                    return None
                expanded += 1
                prediction = self._predict_internal(
                    current,
                    action,
                    trace,
                    dynamic=dynamic,
                )
                if prediction["status"] != "supported" or prediction["payload_hex"] is None:
                    continue
                next_payload = bytes.fromhex(str(prediction["payload_hex"]))
                next_trace = action if trace is not None else None
                found = search(next_payload, next_trace, depth + 1, plan + (action,))
                if found is not None:
                    return found
            return None

        result_plan = search(observation, resolved_history, 0, ())
        if result_plan is not None and result_plan:
            return {
                "status": "supported",
                "action_hex": result_plan[0].hex(),
                "plan_hex": [item.hex() for item in result_plan],
                "expanded": expanded,
                "reason": "field-composed-authorized-route",
                "goal_hex": goal.hex(),
                "dynamic": bool(dynamic),
            }
        return {
            "status": "capacity" if capacity_hit else "unresolved",
            "action_hex": None,
            "plan_hex": [],
            "expanded": expanded,
            "reason": "planner-expansion-bound" if capacity_hit else "no-field-supported-route",
            "goal_hex": goal.hex(),
            "dynamic": bool(dynamic),
        }

    def fingerprint(self) -> str:
        return _sha_tensor(self.state.field)

    def snapshot(self) -> dict[str, Any]:
        field = self.state.field
        return {
            "schema": "cassi.raw-event-field-snapshot.v1",
            "operator_id": _OPERATOR_ID,
            "profile_sha256": self.profile.fingerprint,
            "qi_config_sha256": self._controller.config_fingerprint,
            "qi_codebook_sha256": self._controller.codebook_fingerprint,
            "qi_source_sha256": _qi_profile_source_sha256(),
            "operator_source_sha256": _operator_source_sha256(),
            "state_sha256": self.fingerprint(),
            "field_bytes": int(field.numel() * field.element_size()),
            "shape": [int(item) for item in field.shape],
            "dtype": str(field.dtype),
            "all_finite": bool(torch.isfinite(field).all().item()),
            "max_abs": float(field.abs().max().item()) if field.numel() else 0.0,
            "mean_square": float(field.square().mean().item()) if field.numel() else 0.0,
            "current_observation_sha256": (
                None
                if self._current_observation is None
                else _payload_digest(self._current_observation)
            ),
            "pending_action": self._pending is not None,
            "trace_age": self._trace_age,
        }

    def checkpoint_bytes(self) -> bytes:
        """Serialize profile identity plus the sole adaptive Qi tensor."""

        try:
            raw_state = self._controller.dump_state_bytes(self.state)
        except Exception as exc:
            raise CheckpointError(f"Qi state serialization failed: {exc}") from exc
        header = {
            "schema": _CHECKPOINT_SCHEMA,
            "operator_id": _OPERATOR_ID,
            "profile": self.profile.as_dict(),
            "profile_sha256": self.profile.fingerprint,
            "qi_config_sha256": self._controller.config_fingerprint,
            "qi_codebook_sha256": self._controller.codebook_fingerprint,
            "qi_source_sha256": _qi_profile_source_sha256(),
            "operator_source_sha256": _operator_source_sha256(),
            "state_sha256": self.fingerprint(),
            "raw_state_sha256": _sha256(raw_state),
            "raw_state_bytes": len(raw_state),
            "adaptive_payload": "one-qi-field-state",
            "excluded": ["event-journal", "trace", "pending-action", "python-memory"],
        }
        encoded_header = _canonical_json(header)
        return _CHECKPOINT_MAGIC + struct.pack(">Q", len(encoded_header)) + encoded_header + raw_state

    @classmethod
    def restore(cls, blob: bytes | bytearray | memoryview) -> "RawEventLearner":
        if not isinstance(blob, (bytes, bytearray, memoryview)):
            raise CheckpointError("checkpoint must be bytes-like")
        owned = bytes(blob)
        prefix = len(_CHECKPOINT_MAGIC)
        if len(owned) < prefix + 8 or owned[:prefix] != _CHECKPOINT_MAGIC:
            raise CheckpointError("checkpoint magic mismatch")
        header_size = struct.unpack(">Q", owned[prefix : prefix + 8])[0]
        header_start = prefix + 8
        header_end = header_start + header_size
        if header_size <= 0 or header_end > len(owned):
            raise CheckpointError("checkpoint header length is invalid")
        try:
            header = json.loads(owned[header_start:header_end].decode("utf-8"))
        except Exception as exc:
            raise CheckpointError(f"checkpoint header is not canonical JSON: {exc}") from exc
        if not isinstance(header, Mapping) or header.get("schema") != _CHECKPOINT_SCHEMA:
            raise CheckpointError("checkpoint schema mismatch")
        if header.get("operator_id") != _OPERATOR_ID:
            raise CheckpointError("checkpoint operator identity mismatch")
        try:
            profile = AcquisitionProfile.from_dict(header["profile"])
        except Exception as exc:
            raise CheckpointError(f"checkpoint profile is invalid: {exc}") from exc
        controller = _controller_for(profile)
        if header.get("profile_sha256") != profile.fingerprint:
            raise CheckpointError("checkpoint profile digest mismatch")
        if header.get("operator_source_sha256") != _operator_source_sha256():
            raise CheckpointError("checkpoint operator source identity mismatch")
        if header.get("qi_config_sha256") != controller.config_fingerprint:
            raise CheckpointError("checkpoint Qi configuration mismatch")
        if header.get("qi_codebook_sha256") != controller.codebook_fingerprint:
            raise CheckpointError("checkpoint Qi codebook mismatch")
        if header.get("qi_source_sha256") != _qi_profile_source_sha256():
            raise CheckpointError("checkpoint Qi source identity mismatch")
        raw_state = owned[header_end:]
        if header.get("raw_state_bytes") != len(raw_state):
            raise CheckpointError("checkpoint raw state byte count mismatch")
        if header.get("raw_state_sha256") != _sha256(raw_state):
            raise CheckpointError("checkpoint raw state digest mismatch")
        try:
            state = controller.load_state_bytes(raw_state, device="cpu", dtype=torch.float64)
        except Exception as exc:
            raise CheckpointError(f"checkpoint Qi state is invalid: {exc}") from exc
        learner = cls(profile, state=state)
        if header.get("state_sha256") != learner.fingerprint():
            raise CheckpointError("checkpoint field identity mismatch")
        return learner

    def clone(self) -> "RawEventLearner":
        cloned = RawEventLearner(self.profile, state=QiFieldState(self.state.field.clone()))
        cloned._restore_context(self._context_copy())
        return cloned

    def _zero_scales(self, learner: "RawEventLearner", scales: Iterable[int]) -> None:
        candidate = learner.state.field.clone()
        parts = learner._parts(candidate)
        for scale in scales:
            parts[scale].zero_()
        learner._validate_field(candidate)
        learner.state = QiFieldState(candidate)

    def intervene(
        self,
        region: str,
        *,
        action: bytes | None = None,
        observation: bytes | None = None,
        history: bytes | None | object = _TRACE_NONE,
    ) -> tuple["RawEventLearner", dict[str, Any]]:
        """Create a field-only counterfactual intervention."""

        if region not in {"all_memory", "consolidated", "provisional", "history", "relation"}:
            raise EventError("unknown intervention region")
        counterfactual = self.clone()
        before = self.fingerprint()
        if region == "all_memory":
            counterfactual.state = QiFieldState(torch.zeros_like(self.state.field))
            reason = "all-adaptive-field-memory-cleared"
        elif region == "consolidated":
            self._zero_scales(counterfactual, (1, 3))
            reason = "consolidated-banks-cleared"
        elif region == "provisional":
            self._zero_scales(counterfactual, (0, 2))
            reason = "provisional-banks-cleared"
        elif region == "history":
            self._zero_scales(counterfactual, (2, 3))
            reason = "history-banks-cleared"
        else:
            if action is None:
                raise EventError("relation intervention requires an action")
            if observation is None:
                observation = self._current_observation
            if observation is None:
                raise EventError("relation intervention requires an observation")
            if history is _TRACE_NONE:
                resolved_history = self._history_for_next_action()
            elif history is None:
                resolved_history = None
            else:
                resolved_history = self._validate_payload(cast(bytes, history))
            prediction = self._predict_internal(
                observation,
                action,
                resolved_history,
                dynamic=False,
            )
            if prediction.get("status") != "supported" or prediction.get("payload_hex") is None:
                return counterfactual, {
                    "schema": "cassi.raw-event-intervention-receipt.v1",
                    "region": region,
                    "status": "unresolved",
                    "reason": "target-relation-not-supported",
                    "before_state_sha256": before,
                    "after_state_sha256": counterfactual.fingerprint(),
                    "changed": False,
                    "prediction": prediction,
                }
            target = bytes.fromhex(str(prediction["payload_hex"]))
            abstract = self._abstract_transition_packets(observation, target)
            if abstract is not None:
                observation, target = abstract
            key_re, key_im = self._key_wave(
                observation, action, resolved_history
            )
            out_re, out_im = self._packet_wave(target, role=3)
            relation_re, relation_im = self._complex_conj_mul(key_re, key_im, out_re, out_im)
            candidate = counterfactual.state.field.clone()
            scales = (
                (3, 2) if resolved_history is not None else (1, 0)
            )
            coefficients: list[float] = []
            for scale in scales:
                memory_re, memory_im = counterfactual._differential(candidate, scale)
                coefficient = float(
                    (memory_re * relation_re + memory_im * relation_im).mean().item()
                )
                coefficient = max(0.0, coefficient)
                coefficients.append(coefficient)
                counterfactual._set_differential(
                    candidate,
                    scale,
                    -coefficient * relation_re,
                    -coefficient * relation_im,
                )
            counterfactual._validate_field(candidate)
            counterfactual.state = QiFieldState(candidate)
            reason = "targeted-relation-projection-removed"
            return counterfactual, {
                "schema": "cassi.raw-event-intervention-receipt.v1",
                "region": region,
                "status": "supported",
                "reason": reason,
                "before_state_sha256": before,
                "after_state_sha256": counterfactual.fingerprint(),
                "changed": before != counterfactual.fingerprint(),
                "prediction": prediction,
                "projection_coefficients": coefficients,
            }
        return counterfactual, {
            "schema": "cassi.raw-event-intervention-receipt.v1",
            "region": region,
            "status": "supported",
            "reason": reason,
            "before_state_sha256": before,
            "after_state_sha256": counterfactual.fingerprint(),
            "changed": before != counterfactual.fingerprint(),
        }

    def restore_context_from_events(self, events: Iterable[RawEvent]) -> None:
        """Reconstruct ephemeral trace without replaying or mutating field memory."""

        self._current_observation = None
        self._last_action = None
        self._trace_age = None
        self._pending = None
        for event in events:
            if event.kind == "reset":
                self._current_observation = None
                self._last_action = None
                self._trace_age = None
                self._pending = None
            elif event.kind == "observation":
                if self._pending is not None:
                    self._last_action = self._pending.action
                    self._trace_age = 0
                    self._pending = None
                else:
                    self._last_action = None
                    self._trace_age = None
                self._current_observation = event.payload
            elif event.kind == "action":
                if self._current_observation is not None and self._pending is None:
                    history = self._history_for_next_action()
                    prediction = self._predict_internal(
                        self._current_observation,
                        event.payload,
                        history,
                        dynamic=False,
                    )
                    self._pending = _PendingAction(
                        observation=self._current_observation,
                        action=event.payload,
                        history=history,
                        prediction=prediction,
                        event_seq=event.seq,
                    )
            elif event.kind == "goal":
                if self._trace_age is not None:
                    self._trace_age += 1
                    if self._trace_age >= self.profile.trace_horizon:
                        self._last_action = None
                        self._trace_age = None


__all__ = [
    "AcquisitionProfile",
    "CapacityError",
    "CheckpointError",
    "EventError",
    "RawEvent",
    "RawEventLearner",
    "atom_packet",
    "canonical_packet",
    "decode_packet",
    "encode_packet",
]
