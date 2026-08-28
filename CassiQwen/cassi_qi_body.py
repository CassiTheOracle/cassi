"""CassiFI W8 bounded physical body and homeostasis primitives.

The body is deliberately small: its only evolving values are the declared
physical channels in :class:`QiBodyState`. Profiles, packets, frames, and
receipts are immutable and content addressed. Boundary packets are accepted
only through the W7 ``QiBoundaryPacket``/``QiLinearBoundaryPort`` contracts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from fractions import Fraction
import base64
import hashlib
import math
import re
import struct
from typing import Any, Iterable, Sequence

import torch

from cassi_qi_bootstrap import canonical_hash, finite_float
from cassi_qi_boundary import QiBoundaryPacket, QiLinearBoundaryPort
from cassi_qi_clock import QiClockTime, QiSourceScope


BODY_PROFILE_SCHEMA = "cassi.qi-flow-body-profile.v1"
BODY_STATE_SCHEMA = "cassi.qi-flow-body-state.v1"
BODY_RECEIPT_SCHEMA = "cassi.qi-flow-body-receipt.v1"
HOMEOSTASIS_OBSERVATION_SCHEMA = "cassi.qi-flow-homeostasis-observation.v1"
BODY_TRANSITION_SCHEMA = "cassi.qi-flow-body-transition.v1"
ENVIRONMENT_SENSOR_FRAME_SCHEMA = "cassi.qi-flow-environment-sensor-frame.v1"
BODY_SENSOR_FRAME_SCHEMA = "cassi.qi-flow-body-sensor-frame.v1"


class QiBodyError(ValueError):
    """Raised when a body value cannot be admitted without ambiguity."""


_CLOSURE_TOLERANCE = 2.0e-12


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise QiBodyError(f"{name} must be nonempty text")
    return value


def _identity_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise QiBodyError(f"{name} must be a nonempty identity")
    return value


_ID_PATTERN = re.compile(r"^[a-z][a-z0-9._:-]{0,127}$")
_MISSING = object()


def _id(value: Any, name: str) -> str:
    result = _identity_text(value, name)
    if not _ID_PATTERN.fullmatch(result):
        raise QiBodyError(f"{name} must be an ASCII registry Id")
    return result


def _u64(value: Any, name: str) -> int:
    result = _integer(value, name)
    if result > 0xFFFFFFFFFFFFFFFF:
        raise QiBodyError(f"{name} exceeds U64")
    return result


def _world_tick(value: Any, name: str) -> int:
    result = _u64(value, name)
    if result > 9007199254740991:
        raise QiBodyError(f"{name} exceeds the frozen JSON integer range")
    return result


def _i64(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < -0x8000000000000000 or value > 0x7FFFFFFFFFFFFFFF:
        raise QiBodyError(f"{name} must be an I64")
    return value


def _member(value: Any, name: str, *, default: Any = _MISSING) -> Any:
    if isinstance(value, Mapping):
        if name in value:
            return value[name]
    else:
        try:
            return getattr(value, name)
        except AttributeError:
            pass
    if default is not _MISSING:
        return default
    raise QiBodyError(f"validated acknowledgement is missing {name}")


def _strict_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise QiBodyError(f"{name} must be a mapping")
    return dict(value)


def _bytes_value(value: Any, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise QiBodyError(f"{name} must be raw bytes")
    result = bytes(value)
    if len(result) > 0xFFFFFFFFFFFFFFFF:
        raise QiBodyError(f"{name} exceeds U64 byte count")
    return result

def _f64_text(value: Any, name: str) -> str:
    result = _text(value, name)
    if len(result) != 20 or not result.startswith("f64:") or any(ch not in "0123456789abcdef" for ch in result[4:]):
        raise QiBodyError(f"{name} must be a canonical f64 scalar")
    decoded = struct.unpack(">d", int(result[4:], 16).to_bytes(8, "big"))[0]
    if not math.isfinite(decoded) or (decoded == 0.0 and result[4:] == "8000000000000000"):
        raise QiBodyError(f"{name} must be finite and not negative zero")
    return result


def _bounded_text(value: Any, name: str) -> str:
    result = _text(value, name)
    if len(result) > 256:
        raise QiBodyError(f"{name} exceeds 256 characters")
    return result


def _base64_text(value: Any, name: str) -> str:
    result = _text(value, name)
    try:
        decoded = base64.b64decode(result.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise QiBodyError(f"{name} must be canonical base64") from exc
    if base64.b64encode(decoded).decode("ascii") != result or len(decoded) > 65536:
        raise QiBodyError(f"{name} must be canonical base64 within the byte budget")
    return result


def _terminal_ack_text(value: Any, name: str) -> str:
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = base64.b64encode(_bytes_value(value, name)).decode("ascii")
    return _base64_text(value, name)


def _actual_values(value: Any, name: str = "actual_values") -> tuple[tuple[str, str], ...]:
    if not isinstance(value, (tuple, list)):
        raise QiBodyError(f"{name} must be a list")
    result: list[tuple[str, str]] = []
    for item in value:
        if isinstance(item, Mapping):
            mapping = _strict_mapping(item, "actual value")
            if set(mapping) != {"channel_id", "value"}:
                raise QiBodyError("actual value has unknown or missing fields")
            raw_channel, raw_scalar = mapping["channel_id"], mapping["value"]
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            raw_channel, raw_scalar = item
        else:
            raise QiBodyError("actual value must be a channel/scalar pair")
        channel = _bounded_text(raw_channel, "channel_id")
        scalar = _f64_text(raw_scalar, "actual value")
        result.append((channel, scalar))
    if len(result) > 4096:
        raise QiBodyError(f"{name} exceeds 4096 values")
    return tuple(result)


def _actual_payload(values: Sequence[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"channel_id": channel, "value": scalar} for channel, scalar in values]


def _body_transition(value: Any, name: str = "body_transition") -> tuple[str, str, str]:
    if isinstance(value, Mapping):
        mapping = _strict_mapping(value, name)
        if set(mapping) != {"before_body_frame_id", "after_body_frame_id", "remap_sha256"}:
            raise QiBodyError(f"{name} has unknown or missing fields")
        raw_before = mapping["before_body_frame_id"]
        raw_after = mapping["after_body_frame_id"]
        raw_remap = mapping["remap_sha256"]
    elif isinstance(value, (tuple, list)) and len(value) == 3:
        raw_before, raw_after, raw_remap = value
    else:
        raise QiBodyError(f"{name} must be a transition object")
    return (
        _bounded_text(raw_before, "before_body_frame_id"),
        _bounded_text(raw_after, "after_body_frame_id"),
        _sha(raw_remap, "remap_sha256"),
    )


def _body_transition_payload(transition: tuple[str, str, str]) -> dict[str, str]:
    before, after, remap = transition
    return {
        "before_body_frame_id": before,
        "after_body_frame_id": after,
        "remap_sha256": remap,
    }


def _f64_text(value: Any, name: str) -> str:
    result = _text(value, name)
    if len(result) != 20 or not result.startswith("f64:") or any(ch not in "0123456789abcdef" for ch in result[4:]):
        raise QiBodyError(f"{name} must be a canonical f64 scalar")
    decoded = struct.unpack(">d", int(result[4:], 16).to_bytes(8, "big"))[0]
    if not math.isfinite(decoded) or (decoded == 0.0 and result[4:] == "8000000000000000"):
        raise QiBodyError(f"{name} must be finite and not negative zero")
    return result


def _bounded_text(value: Any, name: str) -> str:
    result = _text(value, name)
    if len(result) > 256:
        raise QiBodyError(f"{name} exceeds 256 characters")
    return result


def _base64_text(value: Any, name: str) -> str:
    result = _text(value, name)
    try:
        decoded = base64.b64decode(result.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise QiBodyError(f"{name} must be canonical base64") from exc
    if base64.b64encode(decoded).decode("ascii") != result or len(decoded) > 65536:
        raise QiBodyError(f"{name} must be canonical base64 within the byte budget")
    return result


def _actual_values(value: Any, name: str = "actual_values") -> tuple[tuple[str, str], ...]:
    if not isinstance(value, (tuple, list)):
        raise QiBodyError(f"{name} must be a list")
    result: list[tuple[str, str]] = []
    for item in value:
        if isinstance(item, Mapping):
            mapping = _strict_mapping(item, "actual value")
            if set(mapping) != {"channel_id", "value"}:
                raise QiBodyError("actual value has unknown or missing fields")
            raw_channel, raw_scalar = mapping["channel_id"], mapping["value"]
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            raw_channel, raw_scalar = item
        else:
            raise QiBodyError("actual value must be a channel/scalar pair")
        channel = _bounded_text(raw_channel, "channel_id")
        scalar = _f64_text(raw_scalar, "actual value")
        result.append((channel, scalar))
    if len(result) > 4096:
        raise QiBodyError(f"{name} exceeds 4096 values")
    return tuple(result)


def _actual_payload(values: Sequence[tuple[str, str]]) -> list[dict[str, str]]:
    return [{"channel_id": channel, "value": scalar} for channel, scalar in values]


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise QiBodyError(f"{name} must be finite")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise QiBodyError(f"{name} must be finite") from exc
    if not math.isfinite(result):
        raise QiBodyError(f"{name} must be finite")
    return result


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise QiBodyError(f"{name} must be an integer >= {minimum}")
    return value


def _sha(value: Any, name: str) -> str:
    result = _text(value, name)
    if len(result) != 64 or result.lower() != result or any(ch not in "0123456789abcdef" for ch in result):
        raise QiBodyError(f"{name} must be a lowercase SHA-256 digest")
    return result


def _vector(values: Any, name: str, *, length: int | None = None) -> tuple[float, ...]:
    if isinstance(values, torch.Tensor):
        if values.ndim != 1:
            raise QiBodyError(f"{name} must be a one-dimensional vector")
        values = values.detach().cpu().tolist()
    if isinstance(values, (str, bytes, bytearray)):
        raise QiBodyError(f"{name} must be a numeric vector")
    try:
        result = tuple(_finite(item, name) for item in values)
    except TypeError as exc:
        raise QiBodyError(f"{name} must be a numeric vector") from exc
    if not result:
        raise QiBodyError(f"{name} must not be empty")
    if length is not None and len(result) != length:
        raise QiBodyError(f"{name} length must be {length}")
    return result


def _positive_vector(values: Any, name: str, *, length: int | None = None) -> tuple[float, ...]:
    result = _vector(values, name, length=length)
    if any(value <= 0.0 for value in result):
        raise QiBodyError(f"{name} must be strictly positive")
    return result


def _clock(value: Any, name: str, *, positive: bool = False) -> QiClockTime:
    if isinstance(value, QiClockTime):
        result = value
    elif isinstance(value, Fraction):
        if value.denominator <= 0 or value.numerator < 0:
            raise QiBodyError(f"{name} must be a nonnegative exact interval")
        result = QiClockTime.make(value.numerator, value.denominator)
    elif isinstance(value, tuple) and len(value) == 2:
        result = QiClockTime.make(
            _integer(value[0], f"{name}.n"),
            _integer(value[1], f"{name}.d", minimum=1),
        )
    else:
        raise QiBodyError(f"{name} must be QiClockTime or an exact rational interval")
    if positive and not result.positive:
        raise QiBodyError(f"{name} must be positive")
    return result


def _float_payload(values: Sequence[float]) -> list[str]:
    return [finite_float(value) for value in values]


def _canonical(value: Any, schema: str) -> str:
    try:
        return canonical_hash(value, schema)
    except Exception as exc:
        raise QiBodyError(f"{schema} cannot be canonically encoded: {exc}") from exc


def _packet_identity(packet: QiBoundaryPacket) -> str:
    # event_id is W7's immutable content identity. The body layer does not
    # invent a second packet hash or decode packet payload bytes.
    return packet.event_id


def _packet_source_stream(packet: QiBoundaryPacket) -> str:
    return _text(packet.source_stream_id, "packet source stream")
def _packet_optional(packet: QiBoundaryPacket, name: str, default: Any = None) -> Any:
    return getattr(packet, name, default)


def _packet_body_frame(packet: QiBoundaryPacket) -> str | None:
    value = _packet_optional(packet, "body_frame_id")
    return None if value is None else _id(value, "packet body_frame_id")



def _packet_scope(packet: QiBoundaryPacket) -> QiSourceScope:
    # Do not use QiBoundaryPacket.scope here: older W7 builds exposed that
    # property with positional fields in the wrong order.
    return QiSourceScope(packet.source_epoch, _packet_source_stream(packet), packet.descriptor_sha256)


def _scope_identity(scope: QiSourceScope) -> str:
    return scope.key()


def _source_scope(value: Any, name: str = "source") -> QiSourceScope:
    if not isinstance(value, QiSourceScope):
        raise QiBodyError(f"{name} must be a registered QiSourceScope")
    return value


def _source_matches(packet: QiBoundaryPacket, expected: QiSourceScope | None) -> None:
    if expected is not None and _packet_scope(packet) != expected:
        raise QiBodyError("sensor packet source identity does not match the registered source")


def _packet_clock_guard(packet: QiBoundaryPacket, start: QiClockTime, end: QiClockTime) -> None:
    if not isinstance(packet, QiBoundaryPacket):
        raise QiBodyError("body input must use a QiBoundaryPacket")
    if packet.capture_start > packet.capture_end:
        raise QiBodyError("sensor packet capture interval is reversed")
    if packet.capture_start < start or packet.capture_end > end:
        raise QiBodyError("sensor packet capture interval does not lie within the body transition")
    if packet.logical_time < packet.capture_end or packet.logical_time > end:
        raise QiBodyError("sensor packet logical clock is outside the body transition")


@dataclass(frozen=True, slots=True)
class QiEnvironmentSensorFrame:
    """Typed environment sample backed by exactly one W7 boundary packet."""

    packet: QiBoundaryPacket
    values: tuple[float, ...]
    frame_sha256: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.packet, QiBoundaryPacket):
            raise QiBodyError("environment frame requires a QiBoundaryPacket")
        object.__setattr__(self, "values", _vector(self.values, "environment values"))
        expected = _canonical(self.canonical_payload(include_hash=False), ENVIRONMENT_SENSOR_FRAME_SCHEMA)
        if self.frame_sha256 and self.frame_sha256 != expected:
            raise QiBodyError("environment frame identity mismatch")
        object.__setattr__(self, "frame_sha256", expected)

    @property
    def body_frame_id(self) -> str | None:
        return _packet_body_frame(self.packet)

    @classmethod
    def create(cls, packet: QiBoundaryPacket, values: Sequence[float]) -> "QiEnvironmentSensorFrame":
        return cls(packet, _vector(values, "environment values"))

    @property
    def valid(self) -> bool:
        return self.packet.valid

    @property
    def source_scope(self) -> QiSourceScope:
        return _packet_scope(self.packet)

    @property
    def packet_sha256(self) -> str:
        return _packet_identity(self.packet)

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": ENVIRONMENT_SENSOR_FRAME_SCHEMA,
            "packet_event_id": self.packet.event_id,
            "packet_schema": self.packet.schema,
            "source_epoch": self.packet.source_epoch,
            "source_stream_id": _packet_source_stream(self.packet),
            "source_sequence": self.packet.source_sequence,
            "descriptor_sha256": self.packet.descriptor_sha256,
            "logical_time": self.packet.logical_time.payload(),
            "capture_start": self.packet.capture_start.payload(),
            "capture_end": self.packet.capture_end.payload(),
            "values": _float_payload(self.values),
            "body_frame_id": self.body_frame_id,
            "failure_reason": _packet_optional(self.packet, "failure_reason"),
        }
        if include_hash:
            body["frame_sha256"] = self.frame_sha256
        return body


@dataclass(frozen=True, slots=True)
class QiBodySensorFrame:
    """Typed proprioceptive/body sample backed by one W7 boundary packet."""

    packet: QiBoundaryPacket
    values: tuple[float, ...]
    frame_sha256: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.packet, QiBoundaryPacket):
            raise QiBodyError("body sensor frame requires a QiBoundaryPacket")
        object.__setattr__(self, "values", _vector(self.values, "body sensor values"))
        expected = _canonical(self.canonical_payload(include_hash=False), BODY_SENSOR_FRAME_SCHEMA)
        if self.frame_sha256 and self.frame_sha256 != expected:
            raise QiBodyError("body sensor frame identity mismatch")
        object.__setattr__(self, "frame_sha256", expected)

    @classmethod
    def create(cls, packet: QiBoundaryPacket, values: Sequence[float]) -> "QiBodySensorFrame":
        return cls(packet, _vector(values, "body sensor values"))
    @property
    def body_frame_id(self) -> str | None:
        return _packet_body_frame(self.packet)


    @property
    def valid(self) -> bool:
        return self.packet.valid

    @property
    def source_scope(self) -> QiSourceScope:
        return _packet_scope(self.packet)

    @property
    def packet_sha256(self) -> str:
        return _packet_identity(self.packet)

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": BODY_SENSOR_FRAME_SCHEMA,
            "packet_event_id": self.packet.event_id,
            "packet_schema": self.packet.schema,
            "source_epoch": self.packet.source_epoch,
            "source_stream_id": _packet_source_stream(self.packet),
            "source_sequence": self.packet.source_sequence,
            "descriptor_sha256": self.packet.descriptor_sha256,
            "logical_time": self.packet.logical_time.payload(),
            "capture_start": self.packet.capture_start.payload(),
            "capture_end": self.packet.capture_end.payload(),
            "body_frame_id": self.body_frame_id,
            "values": _float_payload(self.values),
            "valid": self.packet.valid,
            "failure_reason": _packet_optional(self.packet, "failure_reason"),
        }
        if include_hash:
            body["frame_sha256"] = self.frame_sha256
        return body


QiEnvironmentFrame = QiEnvironmentSensorFrame
QiBodyFrame = QiBodySensorFrame


@dataclass(frozen=True, slots=True)
class QiBodyProfile:
    """Immutable bounded, independently driven body ODE/map declaration.

    For channel ``j`` the declared law is ``dy/dt = -r[j] * y + g[j] * u[j]``
    with ``y = x - rest`` and an exact constant-drive exponential update over
    every registered clock interval. The final value is explicitly clamped to
    the declared physical range; the receipt reports clamp work.
    """

    profile_id: str
    channel_names: tuple[str, ...]
    lower_bounds: tuple[float, ...]
    upper_bounds: tuple[float, ...]
    rest_values: tuple[float, ...]
    relaxation_rates: tuple[float, ...]
    drive_gains: tuple[float, ...]
    energy_metric: tuple[float, ...]
    integration_interval: QiClockTime
    body_frame_id: str = "body-frame"
    field_ports: tuple[QiLinearBoundaryPort, ...] = ()
    profile_sha256: str = ""

    def __post_init__(self) -> None:
        profile_id = _text(self.profile_id, "profile_id")
        names = tuple(_text(value, "channel name") for value in self.channel_names)
        if not names or len(set(names)) != len(names):
            raise QiBodyError("channel_names must be nonempty and unique")
        n = len(names)
        lower = _vector(self.lower_bounds, "lower_bounds", length=n)
        upper = _vector(self.upper_bounds, "upper_bounds", length=n)
        rest = _vector(self.rest_values, "rest_values", length=n)
        rates = _vector(self.relaxation_rates, "relaxation_rates", length=n)
        gains = _vector(self.drive_gains, "drive_gains", length=n)
        metric = _positive_vector(self.energy_metric, "energy_metric", length=n)
        if any(lo >= hi for lo, hi in zip(lower, upper)):
            raise QiBodyError("every body channel requires lower < upper")
        if any(value < lo or value > hi for value, lo, hi in zip(rest, lower, upper)):
            raise QiBodyError("rest_values must lie in the declared bounds")
        if any(rate < 0.0 for rate in rates):
            raise QiBodyError("relaxation_rates must be nonnegative")
        interval = _clock(self.integration_interval, "integration_interval", positive=True)
        frame_id = _text(self.body_frame_id, "body_frame_id")
        ports = tuple(self.field_ports)
        if any(not isinstance(port, QiLinearBoundaryPort) for port in ports):
            raise QiBodyError("field_ports must contain QiLinearBoundaryPort values")
        if len({port.name for port in ports}) != len(ports):
            raise QiBodyError("field port names must be unique")
        for port in ports:
            if port.field_dimension != n:
                raise QiBodyError("registered homeostasis port field dimension must equal body channel count")
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "channel_names", names)
        object.__setattr__(self, "lower_bounds", lower)
        object.__setattr__(self, "upper_bounds", upper)
        object.__setattr__(self, "rest_values", rest)
        object.__setattr__(self, "relaxation_rates", rates)
        object.__setattr__(self, "drive_gains", gains)
        object.__setattr__(self, "energy_metric", metric)
        object.__setattr__(self, "integration_interval", interval)
        object.__setattr__(self, "body_frame_id", frame_id)
        object.__setattr__(self, "field_ports", ports)
        expected = _canonical(self.canonical_payload(include_hash=False), BODY_PROFILE_SCHEMA)
        if self.profile_sha256 and self.profile_sha256 != expected:
            raise QiBodyError("body profile identity mismatch")
        object.__setattr__(self, "profile_sha256", expected)

    @classmethod
    def create(
        cls,
        *,
        profile_id: str = "body-development-v1",
        channel_names: Sequence[str],
        lower_bounds: Sequence[float],
        upper_bounds: Sequence[float],
        rest_values: Sequence[float] | None = None,
        relaxation_rates: Sequence[float] | None = None,
        drive_gains: Sequence[float] | None = None,
        energy_metric: Sequence[float] | None = None,
        integration_interval: QiClockTime | Fraction | tuple[int, int] = QiClockTime.make(1),
        body_frame_id: str = "body-frame",
        field_ports: Sequence[QiLinearBoundaryPort] = (),
    ) -> "QiBodyProfile":
        names = tuple(channel_names)
        n = len(names)
        return cls(
            profile_id=profile_id,
            channel_names=names,
            lower_bounds=tuple(lower_bounds),
            upper_bounds=tuple(upper_bounds),
            rest_values=tuple(0.0 for _ in range(n)) if rest_values is None else tuple(rest_values),
            relaxation_rates=tuple(1.0 for _ in range(n)) if relaxation_rates is None else tuple(relaxation_rates),
            drive_gains=tuple(1.0 for _ in range(n)) if drive_gains is None else tuple(drive_gains),
            energy_metric=tuple(1.0 for _ in range(n)) if energy_metric is None else tuple(energy_metric),
            integration_interval=_clock(integration_interval, "integration_interval", positive=True),
            body_frame_id=body_frame_id,
            field_ports=tuple(field_ports),
        )

    @property
    def body_id(self) -> str:
        return self.profile_id

    @property
    def channel_count(self) -> int:
        return len(self.channel_names)

    @property
    def interval(self) -> QiClockTime:
        return self.integration_interval

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": BODY_PROFILE_SCHEMA,
            "profile_id": self.profile_id,
            "channel_names": list(self.channel_names),
            "lower_bounds": _float_payload(self.lower_bounds),
            "upper_bounds": _float_payload(self.upper_bounds),
            "rest_values": _float_payload(self.rest_values),
            "relaxation_rates": _float_payload(self.relaxation_rates),
            "drive_gains": _float_payload(self.drive_gains),
            "energy_metric": _float_payload(self.energy_metric),
            "integration_interval": self.integration_interval.payload(),
            "body_frame_id": self.body_frame_id,
            "field_ports": [port.descriptor_sha256 for port in self.field_ports],
        }
        if include_hash:
            body["profile_sha256"] = self.profile_sha256
        return body

    def initial_state(
        self,
        *,
        clock: QiClockTime = QiClockTime.make(0),
        values: Sequence[float] | torch.Tensor | None = None,
    ) -> "QiBodyState":
        at = _clock(clock, "clock")
        chosen = self.rest_values if values is None else _vector(values, "initial body values", length=self.channel_count)
        if any(value < lo or value > hi for value, lo, hi in zip(chosen, self.lower_bounds, self.upper_bounds)):
            raise QiBodyError("initial body values lie outside the declared bounds")
        return QiBodyState.create(self, chosen, at)

    def _port(self, port: str | QiLinearBoundaryPort | None) -> QiLinearBoundaryPort:
        if isinstance(port, QiLinearBoundaryPort):
            if port not in self.field_ports:
                raise QiBodyError("homeostasis port is not registered in this body profile")
            return port
        if port is None:
            if len(self.field_ports) != 1:
                raise QiBodyError("homeostasis port must be named when zero or multiple ports are registered")
            return self.field_ports[0]
        port_name = _text(port, "port name")
        for candidate in self.field_ports:
            if candidate.name == port_name:
                return candidate
        raise QiBodyError("homeostasis port is not registered in this body profile")

    def homeostasis_observation(
        self,
        state: "QiBodyState",
        field_state: Sequence[complex] | torch.Tensor | None = None,
        *,
        port: str | QiLinearBoundaryPort | None = None,
        source: QiSourceScope | None = None,
        clock: QiClockTime | None = None,
    ) -> "QiHomeostasisObservation":
        self._check_state(state)
        selected = self._port(port)
        at = state.clock if clock is None else _clock(clock, "observation clock")
        if at != state.clock:
            raise QiBodyError("homeostasis observation clock does not match body state")
        if source is None:
            source = QiSourceScope(state.body_id, "homeostasis", selected.descriptor_sha256)
        else:
            source = _source_scope(source)
            if source.descriptor_sha256 != selected.descriptor_sha256:
                raise QiBodyError("homeostasis source descriptor does not match the registered port")
        values = torch.as_tensor(state.values if field_state is None else field_state, dtype=torch.complex128)
        if values.ndim != 1 or tuple(values.shape) != (selected.field_dimension,):
            raise QiBodyError("homeostasis field vector shape disagrees with the registered port")
        if not bool(torch.isfinite(values.real).all()) or not bool(torch.isfinite(values.imag).all()):
            raise QiBodyError("homeostasis field vector must be finite")
        observed = selected.observe(values)
        adjoint = selected.inject(observed)
        residual = selected.adjoint_residual(values, observed)
        rest = torch.tensor(self.rest_values, dtype=torch.complex128, device=values.device)
        deviation = observed - selected.observe(rest)
        return QiHomeostasisObservation.create(
            profile=self,
            state=state,
            source=source,
            port=selected,
            observed=observed,
            adjoint_field=adjoint,
            homeostatic_error=deviation,
            metric_adjoint_residual=residual,
            clock=at,
        )

    observe_homeostasis = homeostasis_observation

    def _check_state(self, state: "QiBodyState") -> None:
        if not isinstance(state, QiBodyState):
            raise QiBodyError("body transition requires a QiBodyState")
        if state.body_id != self.body_id or state.profile_sha256 != self.profile_sha256:
            raise QiBodyError("body state/profile identity mismatch")
        if state.body_frame_id and state.body_frame_id != self.body_frame_id:
            raise QiBodyError("body state/frame identity mismatch")
        if len(state.values) != self.channel_count:
            raise QiBodyError("body state channel count mismatch")
        if any(value < lo or value > hi for value, lo, hi in zip(state.values, self.lower_bounds, self.upper_bounds)):
            raise QiBodyError("body state lies outside its declared physical bounds")

    def _resolve_interval(
        self,
        state: "QiBodyState",
        *,
        start: QiClockTime | None,
        end: QiClockTime | None,
        dt: QiClockTime | Fraction | tuple[int, int] | None,
        interval: QiClockTime | Fraction | tuple[int, int] | None,
    ) -> tuple[QiClockTime, QiClockTime, int]:
        self._check_state(state)
        if interval is not None:
            if dt is not None:
                raise QiBodyError("interval and dt are ambiguous")
            dt = interval
        start_value = state.clock if start is None else _clock(start, "start")
        if start_value != state.clock:
            raise QiBodyError("body transition start clock does not match predecessor state")
        if end is not None and dt is not None:
            raise QiBodyError("end and dt are ambiguous")
        if end is None:
            duration = self.integration_interval if dt is None else _clock(dt, "dt", positive=True)
            end_value = start_value + duration
        else:
            end_value = _clock(end, "end")
            if end_value <= start_value:
                raise QiBodyError("body transition interval must be positive")
        delta = end_value - start_value
        ratio = Fraction(delta.n, delta.d) / Fraction(self.integration_interval.n, self.integration_interval.d)
        if ratio.denominator != 1 or ratio.numerator <= 0:
            raise QiBodyError("body transition interval is ambiguous: it must be an exact multiple of integration_interval")
        return start_value, end_value, ratio.numerator

    def _validate_frame(
        self,
        frame: QiEnvironmentSensorFrame | QiBodySensorFrame,
        *,
        start: QiClockTime,
        end: QiClockTime,
        expected_source: QiSourceScope | None,
    ) -> None:
        if not isinstance(frame, (QiEnvironmentSensorFrame, QiBodySensorFrame)):
            raise QiBodyError("body input must be a typed environment/body sensor frame")
        _packet_clock_guard(frame.packet, start, end)
        _source_matches(frame.packet, expected_source)
        packet_frame = frame.body_frame_id
        if packet_frame is not None and packet_frame != self.body_frame_id:
            raise QiBodyError("sensor packet body-frame identity does not match the body profile")
        if frame.packet.valid and len(frame.values) != self.channel_count:
            raise QiBodyError("sensor frame channel count does not match the body profile")

    def _collect_frames(
        self,
        frames: Iterable[QiEnvironmentSensorFrame | QiBodySensorFrame],
        *,
        start: QiClockTime,
        end: QiClockTime,
        source: QiSourceScope | None,
    ) -> tuple[tuple[QiEnvironmentSensorFrame, ...], tuple[QiBodySensorFrame, ...], bool]:
        environment: list[QiEnvironmentSensorFrame] = []
        body: list[QiBodySensorFrame] = []
        saw_no_sample = False
        for frame in frames:
            self._validate_frame(frame, start=start, end=end, expected_source=source)
            if frame.packet.valid:
                if isinstance(frame, QiEnvironmentSensorFrame):
                    environment.append(frame)
                else:
                    body.append(frame)
            else:
                saw_no_sample = True
        if len(environment) > 1 or len(body) > 1:
            raise QiBodyError("at most one environment and one body frame may be consumed per transition")
        return tuple(environment), tuple(body), saw_no_sample

    def _integrate_channel(self, y0: float, rate: float, forcing: float, duration: float) -> tuple[float, float, float]:
        """Return unconstrained y, source work, and dissipated work."""
        if rate == 0.0:
            y1 = y0 + forcing * duration
            i1 = y0 * duration + 0.5 * forcing * duration * duration
            return y1, forcing * i1, 0.0
        decay = math.exp(-rate * duration)
        equilibrium = forcing / rate
        transient = y0 - equilibrium
        y1 = equilibrium + transient * decay
        one_minus = -math.expm1(-rate * duration)
        i1 = equilibrium * duration + transient * one_minus / rate
        i2 = (
            equilibrium * equilibrium * duration
            + 2.0 * equilibrium * transient * one_minus / rate
            + transient * transient * (1.0 - decay * decay) / (2.0 * rate)
        )
        return y1, forcing * i1, rate * i2

    def transition(
        self,
        state: "QiBodyState",
        drive: Sequence[float] | torch.Tensor | None = None,
        *,
        start: QiClockTime | None = None,
        end: QiClockTime | None = None,
        dt: QiClockTime | Fraction | tuple[int, int] | None = None,
        interval: QiClockTime | Fraction | tuple[int, int] | None = None,
        frames: Iterable[QiEnvironmentSensorFrame | QiBodySensorFrame] = (),
        environment_frame: QiEnvironmentSensorFrame | None = None,
        body_frame: QiBodySensorFrame | None = None,
        source: QiSourceScope | None = None,
    ) -> "QiBodyTransitionReceipt":
        """Apply one deterministic all-channel exact body transition.

        A valid environment frame supplies an additive drive. A body frame is
        consumed and identity-checked as an observation, not as hidden state.
        A W7 no-sample packet produces an explicit guarded no-op. All other
        invalid inputs reject before a successor is constructed.
        """
        self._check_state(state)
        start_value, end_value, steps = self._resolve_interval(state, start=start, end=end, dt=dt, interval=interval)
        expected_source = None if source is None else _source_scope(source)
        frame_values: list[QiEnvironmentSensorFrame | QiBodySensorFrame] = list(frames)
        if environment_frame is not None:
            frame_values.append(environment_frame)
        if body_frame is not None:
            frame_values.append(body_frame)
        environment, body_frames, saw_no_sample = self._collect_frames(frame_values, start=start_value, end=end_value, source=expected_source)
        if saw_no_sample and not environment and not body_frames and drive is None:
            return QiBodyTransitionReceipt.from_no_sample(
                profile=self,
                state=state,
                start=start_value,
                end=end_value,
                packet_identities=tuple(_packet_identity(frame.packet) for frame in frame_values),
                source_identities=tuple(_scope_identity(frame.source_scope) for frame in frame_values),
            )
        if any(not frame.packet.valid for frame in frame_values):
            raise QiBodyError("a no-sample frame cannot be combined with a valid drive/frame")
        values = [0.0] * self.channel_count if drive is None else list(_vector(drive, "body drive", length=self.channel_count))
        for frame in environment:
            values = [left + right for left, right in zip(values, frame.values)]
        if source is not None and frame_values and any(frame.source_scope != source for frame in frame_values):
            raise QiBodyError("frame source identity mismatch")
        before = state.values
        current = list(before)
        energy_before = self.energy(before)
        source_work = 0.0
        dissipation = 0.0
        clamp_work = 0.0
        clamped: set[str] = set()
        step_duration = self.integration_interval.n / self.integration_interval.d
        for _ in range(steps):
            next_values: list[float] = []
            for index, (old, rest, rate, gain, lo, hi, metric, forcing) in enumerate(
                zip(current, self.rest_values, self.relaxation_rates, self.drive_gains, self.lower_bounds, self.upper_bounds, self.energy_metric, values)
            ):
                y0 = old - rest
                unconstrained_y, channel_source, channel_dissipation = self._integrate_channel(y0, rate, gain * forcing, step_duration)
                unconstrained = rest + unconstrained_y
                bounded = min(hi, max(lo, unconstrained))
                if bounded != unconstrained:
                    clamped.add(self.channel_names[index])
                old_unbounded_energy = 0.5 * metric * unconstrained_y * unconstrained_y
                bounded_energy = 0.5 * metric * (bounded - rest) * (bounded - rest)
                clamp_work += bounded_energy - old_unbounded_energy
                source_work += metric * channel_source
                dissipation += metric * channel_dissipation
                next_values.append(bounded)
            current = next_values
        after = tuple(current)
        energy_after = self.energy(after)
        closure = (energy_after - energy_before) - source_work + dissipation - clamp_work
        successor = QiBodyState.create(self, after, end_value)
        packet_ids = tuple(_packet_identity(frame.packet) for frame in frame_values)
        source_ids = tuple(_scope_identity(frame.source_scope) for frame in frame_values)
        return QiBodyTransitionReceipt.create(
            profile=self,
            predecessor=state,
            successor=successor,
            start=start_value,
            end=end_value,
            interval_steps=steps,
            packet_identities=packet_ids,
            source_identities=source_ids,
            energy_before=energy_before,
            energy_after=energy_after,
            source_work=source_work,
            dissipation_work=dissipation,
            clamp_work=clamp_work,
            closure_residual=closure,
            clamped_channels=tuple(sorted(clamped)),
            body_observation_sha256=body_frames[0].frame_sha256 if body_frames else None,
        )

    def advance(self, state: "QiBodyState", drive: Sequence[float] | torch.Tensor | None = None, **kwargs: Any) -> "QiBodyTransitionReceipt":
        return self.transition(state, drive, **kwargs)

    step = advance
    integrate = advance
    bounded_map = advance

    def transition_from_frames(
        self,
        state: "QiBodyState",
        environment_frame: QiEnvironmentSensorFrame | None = None,
        body_frame: QiBodySensorFrame | None = None,
        **kwargs: Any,
    ) -> "QiBodyTransitionReceipt":
        return self.transition(state, environment_frame=environment_frame, body_frame=body_frame, **kwargs)

    def transition_batch(
        self,
        states: Sequence["QiBodyState"],
        drives: Sequence[Sequence[float] | torch.Tensor | None] | torch.Tensor | None = None,
        **kwargs: Any,
    ) -> tuple["QiBodyTransitionReceipt", ...]:
        state_tuple = tuple(states)
        if isinstance(drives, torch.Tensor):
            if drives.ndim != 2 or tuple(drives.shape) != (len(state_tuple), self.channel_count):
                raise QiBodyError("batch drive tensor shape does not match body states")
            drive_tuple: tuple[Any, ...] = tuple(drives[index] for index in range(len(state_tuple)))
        elif drives is None:
            drive_tuple = tuple(None for _ in state_tuple)
        else:
            drive_tuple = tuple(drives)
            if len(drive_tuple) != len(state_tuple):
                raise QiBodyError("batch drive count does not match body state count")
        return tuple(self.transition(state, drive, **kwargs) for state, drive in zip(state_tuple, drive_tuple))

    def advance_batch(self, states: Sequence["QiBodyState"], drives: Sequence[Sequence[float] | torch.Tensor | None] | torch.Tensor | None = None, **kwargs: Any) -> tuple["QiBodyState", ...]:
        return tuple(receipt.successor for receipt in self.transition_batch(states, drives, **kwargs))

    update_batch = advance_batch

    def energy(self, values: Sequence[float] | torch.Tensor) -> float:
        vector = _vector(values, "body values", length=self.channel_count)
        return 0.5 * sum(metric * (value - rest) ** 2 for metric, value, rest in zip(self.energy_metric, vector, self.rest_values))


@dataclass(frozen=True, slots=True)
class QiBodyState:
    """Immutable physical body state; no estimator/controller fields exist."""

    body_id: str
    profile_sha256: str
    values: tuple[float, ...]
    clock: QiClockTime
    state_sha256: str = ""
    body_frame_id: str = ""

    def __post_init__(self) -> None:
        body_id = _text(self.body_id, "body_id")
        profile_hash = _sha(self.profile_sha256, "profile_sha256")
        values = _vector(self.values, "body values")
        clock = _clock(self.clock, "clock")
        frame = "" if self.body_frame_id == "" else _text(self.body_frame_id, "body_frame_id")
        object.__setattr__(self, "body_id", body_id)
        object.__setattr__(self, "profile_sha256", profile_hash)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "clock", clock)
        object.__setattr__(self, "body_frame_id", frame)
        expected = _canonical(self.canonical_payload(include_hash=False), BODY_STATE_SCHEMA)
        if self.state_sha256 and self.state_sha256 != expected:
            raise QiBodyError("body state identity mismatch")
        object.__setattr__(self, "state_sha256", expected)

    @classmethod
    def create(cls, profile: QiBodyProfile, values: Sequence[float] | torch.Tensor, clock: QiClockTime) -> "QiBodyState":
        if not isinstance(profile, QiBodyProfile):
            raise QiBodyError("state creation requires a QiBodyProfile")
        converted = _vector(values, "body values", length=profile.channel_count)
        if any(value < lo or value > hi for value, lo, hi in zip(converted, profile.lower_bounds, profile.upper_bounds)):
            raise QiBodyError("body values lie outside the declared bounds")
        return cls(profile.body_id, profile.profile_sha256, converted, _clock(clock, "clock"), body_frame_id=profile.body_frame_id)

    @property
    def frame_id(self) -> str:
        return self.body_frame_id

    @property
    def time(self) -> QiClockTime:
        return self.clock

    @property
    def state(self) -> tuple[float, ...]:
        return self.values

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": BODY_STATE_SCHEMA,
            "body_id": self.body_id,
            "profile_sha256": self.profile_sha256,
            "body_frame_id": self.body_frame_id or None,
            "values": _float_payload(self.values),
            "clock": self.clock.payload(),
        }
        if include_hash:
            body["state_sha256"] = self.state_sha256
        return body


@dataclass(frozen=True, slots=True)
class QiBodyReceipt:
    """Immutable admission/identity receipt for a body-backed sensor event."""

    profile_sha256: str
    body_id: str
    source_identity: str
    clock: QiClockTime
    packet_identity: str
    frame_identity: str | None
    accepted: bool
    no_sample: bool
    reason: str | None
    receipt_sha256: str = ""

    def __post_init__(self) -> None:
        profile_hash = _sha(self.profile_sha256, "profile_sha256")
        body_id = _text(self.body_id, "body_id")
        source_identity = _identity_text(self.source_identity, "source_identity")
        clock = _clock(self.clock, "clock")
        packet_identity = _sha(self.packet_identity, "packet_identity")
        frame_identity = None if self.frame_identity is None else _sha(self.frame_identity, "frame_identity")
        if self.no_sample and self.accepted:
            raise QiBodyError("a no-sample body receipt cannot be accepted as a sample")
        if self.accepted and self.reason is not None:
            raise QiBodyError("accepted body receipt cannot carry a rejection reason")
        object.__setattr__(self, "profile_sha256", profile_hash)
        object.__setattr__(self, "body_id", body_id)
        object.__setattr__(self, "source_identity", source_identity)
        object.__setattr__(self, "clock", clock)
        object.__setattr__(self, "packet_identity", packet_identity)
        object.__setattr__(self, "frame_identity", frame_identity)
        expected = _canonical(self.canonical_payload(include_hash=False), BODY_RECEIPT_SCHEMA)
        if self.receipt_sha256 and self.receipt_sha256 != expected:
            raise QiBodyError("body receipt identity mismatch")
        object.__setattr__(self, "receipt_sha256", expected)

    @classmethod
    def from_frame(
        cls,
        profile: QiBodyProfile,
        frame: QiEnvironmentSensorFrame | QiBodySensorFrame,
        *,
        accepted: bool | None = None,
        reason: str | None = None,
    ) -> "QiBodyReceipt":
        if not isinstance(profile, QiBodyProfile) or not isinstance(frame, (QiEnvironmentSensorFrame, QiBodySensorFrame)):
            raise QiBodyError("body receipt requires profile and a typed sensor frame")
        valid = frame.packet.valid
        decision = valid if accepted is None else bool(accepted)
        if not valid and decision:
            raise QiBodyError("no-sample frame cannot be accepted")
        if decision and reason is not None:
            raise QiBodyError("accepted frame cannot carry a reason")
        if not decision and reason is None:
            reason = _packet_optional(frame.packet, "failure_reason") or "body frame rejected"
        return cls(
            profile_sha256=profile.profile_sha256,
            body_id=profile.body_id,
            source_identity=_scope_identity(frame.source_scope),
            clock=frame.packet.logical_time,
            packet_identity=frame.packet_sha256,
            frame_identity=frame.frame_sha256,
            accepted=decision,
            no_sample=not valid,
            reason=reason,
        )

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": BODY_RECEIPT_SCHEMA,
            "profile_sha256": self.profile_sha256,
            "body_id": self.body_id,
            "source_identity": self.source_identity,
            "clock": self.clock.payload(),
            "packet_identity": self.packet_identity,
            "frame_identity": self.frame_identity,
            "accepted": self.accepted,
            "no_sample": self.no_sample,
            "reason": self.reason,
        }
        if include_hash:
            body["receipt_sha256"] = self.receipt_sha256
        return body


@dataclass(frozen=True, slots=True)
class QiHomeostasisObservation:
    """Fixed metric-adjoint projection into one registered W7 field port."""

    profile_sha256: str
    body_id: str
    state_sha256: str
    source_identity: str
    clock: QiClockTime
    port_name: str
    port_descriptor_sha256: str
    observed: tuple[complex, ...]
    adjoint_field: tuple[complex, ...]
    homeostatic_error: tuple[complex, ...]
    metric_adjoint_residual: float
    observation_sha256: str = ""

    def __post_init__(self) -> None:
        profile_hash = _sha(self.profile_sha256, "profile_sha256")
        body_id = _text(self.body_id, "body_id")
        state_hash = _sha(self.state_sha256, "state_sha256")
        source_identity = _identity_text(self.source_identity, "source_identity")
        clock = _clock(self.clock, "clock")
        port_name = _text(self.port_name, "port_name")
        port_hash = _sha(self.port_descriptor_sha256, "port_descriptor_sha256")
        observed = tuple(complex(value) for value in self.observed)
        adjoint = tuple(complex(value) for value in self.adjoint_field)
        error = tuple(complex(value) for value in self.homeostatic_error)
        if not observed or len(adjoint) != len(error) or any(not math.isfinite(value.real) or not math.isfinite(value.imag) for value in (*observed, *adjoint, *error)):
            raise QiBodyError("homeostasis observation contains invalid complex values")
        residual = _finite(self.metric_adjoint_residual, "metric_adjoint_residual")
        if residual < 0.0:
            raise QiBodyError("metric_adjoint_residual must be nonnegative")
        object.__setattr__(self, "profile_sha256", profile_hash)
        object.__setattr__(self, "body_id", body_id)
        object.__setattr__(self, "state_sha256", state_hash)
        object.__setattr__(self, "source_identity", source_identity)
        object.__setattr__(self, "clock", clock)
        object.__setattr__(self, "port_name", port_name)
        object.__setattr__(self, "port_descriptor_sha256", port_hash)
        object.__setattr__(self, "observed", observed)
        object.__setattr__(self, "adjoint_field", adjoint)
        object.__setattr__(self, "homeostatic_error", error)
        object.__setattr__(self, "metric_adjoint_residual", residual)
        expected = _canonical(self.canonical_payload(include_hash=False), HOMEOSTASIS_OBSERVATION_SCHEMA)
        if self.observation_sha256 and self.observation_sha256 != expected:
            raise QiBodyError("homeostasis observation identity mismatch")
        object.__setattr__(self, "observation_sha256", expected)

    @classmethod
    def create(
        cls,
        *,
        profile: QiBodyProfile,
        state: QiBodyState,
        source: QiSourceScope,
        port: QiLinearBoundaryPort,
        observed: torch.Tensor,
        adjoint_field: torch.Tensor,
        homeostatic_error: torch.Tensor,
        metric_adjoint_residual: float,
        clock: QiClockTime,
    ) -> "QiHomeostasisObservation":
        if not isinstance(profile, QiBodyProfile) or not isinstance(state, QiBodyState):
            raise QiBodyError("homeostasis observation requires profile and state")
        if not isinstance(source, QiSourceScope) or not isinstance(port, QiLinearBoundaryPort):
            raise QiBodyError("homeostasis observation requires a source and registered port")
        if source.descriptor_sha256 != port.descriptor_sha256:
            raise QiBodyError("homeostasis source and port descriptor identities differ")
        return cls(
            profile_sha256=profile.profile_sha256,
            body_id=state.body_id,
            state_sha256=state.state_sha256,
            source_identity=_scope_identity(source),
            clock=_clock(clock, "clock"),
            port_name=port.name,
            port_descriptor_sha256=port.descriptor_sha256,
            observed=tuple(complex(value) for value in observed.detach().cpu().tolist()),
            adjoint_field=tuple(complex(value) for value in adjoint_field.detach().cpu().tolist()),
            homeostatic_error=tuple(complex(value) for value in homeostatic_error.detach().cpu().tolist()),
            metric_adjoint_residual=metric_adjoint_residual,
        )

    @property
    def residual(self) -> float:
        return self.metric_adjoint_residual

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        def complex_payload(values: Sequence[complex]) -> list[list[str]]:
            return [[finite_float(value.real), finite_float(value.imag)] for value in values]

        body: dict[str, Any] = {
            "schema": HOMEOSTASIS_OBSERVATION_SCHEMA,
            "profile_sha256": self.profile_sha256,
            "body_id": self.body_id,
            "state_sha256": self.state_sha256,
            "source_identity": self.source_identity,
            "clock": self.clock.payload(),
            "port_name": self.port_name,
            "port_descriptor_sha256": self.port_descriptor_sha256,
            "observed": complex_payload(self.observed),
            "adjoint_field": complex_payload(self.adjoint_field),
            "homeostatic_error": complex_payload(self.homeostatic_error),
            "metric_adjoint_residual": finite_float(self.metric_adjoint_residual),
        }
        if include_hash:
            body["observation_sha256"] = self.observation_sha256
        return body


@dataclass(frozen=True, slots=True)
class QiBodyTransitionReceipt:
    """Content-addressed evidence for one exact bounded body transition."""

    successor: QiBodyState
    profile_sha256: str
    body_id: str
    predecessor_state_sha256: str
    successor_state_sha256: str
    start: QiClockTime
    end: QiClockTime
    interval_steps: int
    packet_identities: tuple[str, ...]
    source_identities: tuple[str, ...]
    energy_before: float
    energy_after: float
    source_work: float
    dissipation_work: float
    clamp_work: float
    closure_residual: float
    clamped_channels: tuple[str, ...]
    accepted: bool
    no_sample: bool
    body_observation_sha256: str | None = None
    failure_reason: str | None = None
    transition_sha256: str = ""

    def __post_init__(self) -> None:
        profile_hash = _sha(self.profile_sha256, "profile_sha256")
        body_id = _text(self.body_id, "body_id")
        predecessor_hash = _sha(self.predecessor_state_sha256, "predecessor_state_sha256")
        successor_hash = _sha(self.successor_state_sha256, "successor_state_sha256")
        start = _clock(self.start, "start")
        end = _clock(self.end, "end")
        if end <= start:
            raise QiBodyError("transition receipt interval must be positive")
        steps = _integer(self.interval_steps, "interval_steps", minimum=1)
        packets = tuple(_sha(value, "packet identity") for value in self.packet_identities)
        sources = tuple(_identity_text(value, "source identity") for value in self.source_identities)
        if len(packets) != len(sources):
            raise QiBodyError("packet/source identity rows must have equal length")
        energies = tuple(_finite(value, "energy/work") for value in (self.energy_before, self.energy_after, self.source_work, self.dissipation_work, self.clamp_work, self.closure_residual))
        if energies[0] < 0.0 or energies[1] < 0.0 or energies[3] < -_CLOSURE_TOLERANCE:
            raise QiBodyError("body receipt carries an invalid energy/work value")
        if not isinstance(self.successor, QiBodyState) or self.successor.state_sha256 != successor_hash:
            raise QiBodyError("transition successor identity mismatch")
        observation_hash = None if self.body_observation_sha256 is None else _sha(self.body_observation_sha256, "body_observation_sha256")
        if self.no_sample and self.accepted:
            raise QiBodyError("no-sample transition cannot be accepted")
        if self.accepted and self.failure_reason is not None:
            raise QiBodyError("accepted transition cannot carry a failure reason")
        object.__setattr__(self, "profile_sha256", profile_hash)
        object.__setattr__(self, "body_id", body_id)
        object.__setattr__(self, "predecessor_state_sha256", predecessor_hash)
        object.__setattr__(self, "successor_state_sha256", successor_hash)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        object.__setattr__(self, "interval_steps", steps)
        object.__setattr__(self, "packet_identities", packets)
        object.__setattr__(self, "source_identities", sources)
        object.__setattr__(self, "body_observation_sha256", observation_hash)
        for name, value in zip(("energy_before", "energy_after", "source_work", "dissipation_work", "clamp_work", "closure_residual"), energies):
            object.__setattr__(self, name, value)
        expected = _canonical(self.canonical_payload(include_hash=False), BODY_TRANSITION_SCHEMA)
        if self.transition_sha256 and self.transition_sha256 != expected:
            raise QiBodyError("body transition identity mismatch")
        object.__setattr__(self, "transition_sha256", expected)

    @classmethod
    def create(
        cls,
        *,
        profile: QiBodyProfile,
        predecessor: QiBodyState,
        successor: QiBodyState,
        start: QiClockTime,
        end: QiClockTime,
        interval_steps: int,
        packet_identities: Sequence[str],
        source_identities: Sequence[str],
        energy_before: float,
        energy_after: float,
        source_work: float,
        dissipation_work: float,
        clamp_work: float,
        closure_residual: float,
        clamped_channels: Sequence[str],
        body_observation_sha256: str | None,
    ) -> "QiBodyTransitionReceipt":
        if not isinstance(profile, QiBodyProfile) or not isinstance(predecessor, QiBodyState) or not isinstance(successor, QiBodyState):
            raise QiBodyError("transition receipt requires profile and body states")
        if predecessor.profile_sha256 != profile.profile_sha256 or successor.profile_sha256 != profile.profile_sha256:
            raise QiBodyError("transition receipt state/profile identity mismatch")
        return cls(
            profile_sha256=profile.profile_sha256,
            body_id=profile.body_id,
            predecessor_state_sha256=predecessor.state_sha256,
            successor_state_sha256=successor.state_sha256,
            start=_clock(start, "start"),
            end=_clock(end, "end"),
            interval_steps=interval_steps,
            packet_identities=tuple(packet_identities),
            source_identities=tuple(source_identities),
            energy_before=energy_before,
            energy_after=energy_after,
            source_work=source_work,
            dissipation_work=dissipation_work,
            clamp_work=clamp_work,
            closure_residual=closure_residual,
            clamped_channels=tuple(_text(value, "clamped channel") for value in clamped_channels),
            accepted=True,
            no_sample=False,
            successor=successor,
            body_observation_sha256=body_observation_sha256,
        )

    @classmethod
    def from_no_sample(
        cls,
        *,
        profile: QiBodyProfile,
        state: QiBodyState,
        start: QiClockTime,
        end: QiClockTime,
        packet_identities: Sequence[str],
        source_identities: Sequence[str],
    ) -> "QiBodyTransitionReceipt":
        if not isinstance(profile, QiBodyProfile) or not isinstance(state, QiBodyState):
            raise QiBodyError("no-sample receipt requires profile and state")
        return cls(
            profile_sha256=profile.profile_sha256,
            body_id=profile.body_id,
            predecessor_state_sha256=state.state_sha256,
            successor_state_sha256=state.state_sha256,
            start=_clock(start, "start"),
            end=_clock(end, "end"),
            interval_steps=1,
            packet_identities=tuple(packet_identities),
            source_identities=tuple(source_identities),
            energy_before=profile.energy(state.values),
            energy_after=profile.energy(state.values),
            source_work=0.0,
            dissipation_work=0.0,
            clamp_work=0.0,
            closure_residual=0.0,
            clamped_channels=(),
            accepted=False,
            no_sample=True,
            successor=state,
            failure_reason="no_sample",
        )

    @property
    def state_after(self) -> QiBodyState:
        return self.successor

    @property
    def state_before_sha256(self) -> str:
        return self.predecessor_state_sha256

    @property
    def work(self) -> float:
        return self.source_work

    @property
    def energy_delta(self) -> float:
        return self.energy_after - self.energy_before

    @property
    def residual(self) -> float:
        return self.closure_residual

    def __iter__(self):
        yield self.successor
        yield self

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": BODY_TRANSITION_SCHEMA,
            "profile_sha256": self.profile_sha256,
            "body_id": self.body_id,
            "predecessor_state_sha256": self.predecessor_state_sha256,
            "successor_state_sha256": self.successor_state_sha256,
            "start": self.start.payload(),
            "end": self.end.payload(),
            "interval_steps": self.interval_steps,
            "packet_identities": list(self.packet_identities),
            "source_identities": list(self.source_identities),
            "energy_before": finite_float(self.energy_before),
            "energy_after": finite_float(self.energy_after),
            "source_work": finite_float(self.source_work),
            "dissipation_work": finite_float(self.dissipation_work),
            "clamp_work": finite_float(self.clamp_work),
            "closure_residual": finite_float(self.closure_residual),
            "clamped_channels": list(self.clamped_channels),
            "accepted": self.accepted,
            "no_sample": self.no_sample,
            "body_observation_sha256": self.body_observation_sha256,
            "failure_reason": self.failure_reason,
            "successor_state": self.successor.canonical_payload(),
        }
        if include_hash:
            body["transition_sha256"] = self.transition_sha256
        return body


BODY_FRAME_SCHEMA = "cassi.qi-flow-body-frame.v1"
BODY_POSE_SCHEMA = "cassi.qi-flow-body-pose.v1"
BODY_MOTION_SCHEMA = "cassi.qi-flow-body-motion.v1"
BODY_REMAP_SCHEMA = "cassi.qi-flow-body-remap.v1"
BODY_TRANSFORM_SCHEMA = "cassi.qi-flow-body-transform.v1"
_TICK_ACK_SCHEMA = "cassi.qi-flow-tick-ack.v1"
EFFERENCE_SCHEMA = "cassi.qi-flow-applied-efference.v1"
PREDICTION_SCHEMA = "cassi.qi-flow-body-prediction.v1"
RESIDUAL_SCHEMA = "cassi.qi-flow-residual-return.v1"
EFFICACY_SCHEMA = "cassi.qi-flow-residual-efficacy.v1"


def _vec3(values: Any, name: str) -> tuple[float, float, float]:
    result = _vector(values, name, length=3)
    return (result[0], result[1], result[2])


def _matrix3(values: Any, name: str) -> tuple[tuple[float, float, float], ...]:
    if isinstance(values, torch.Tensor):
        values = values.detach().cpu().tolist()
    try:
        rows = tuple(tuple(_finite(item, name) for item in row) for row in values)
    except (TypeError, ValueError) as exc:
        raise QiBodyError(f"{name} must be a 3x3 matrix") from exc
    if len(rows) != 3 or any(len(row) != 3 for row in rows):
        raise QiBodyError(f"{name} must be a 3x3 matrix")
    return rows


def _matrix_transpose(matrix: tuple[tuple[float, float, float], ...]) -> tuple[tuple[float, float, float], ...]:
    return tuple(tuple(matrix[row][column] for row in range(3)) for column in range(3))


def _matrix_multiply(
    left: tuple[tuple[float, float, float], ...],
    right: tuple[tuple[float, float, float], ...],
) -> tuple[tuple[float, float, float], ...]:
    return tuple(
        tuple(sum(left[row][inner] * right[inner][column] for inner in range(3)) for column in range(3))
        for row in range(3)
    )


def _matrix_vector(
    matrix: tuple[tuple[float, float, float], ...],
    vector: tuple[float, float, float],
) -> tuple[float, float, float]:
    return tuple(sum(matrix[row][column] * vector[column] for column in range(3)) for row in range(3))  # type: ignore[return-value]


def _matrix_det(matrix: tuple[tuple[float, float, float], ...]) -> float:
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def _matrix_error(left: tuple[tuple[float, float, float], ...], right: tuple[tuple[float, float, float], ...]) -> float:
    return max(abs(left[row][column] - right[row][column]) for row in range(3) for column in range(3))


def _identity3() -> tuple[tuple[float, float, float], ...]:
    return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _matrix_payload(matrix: tuple[tuple[float, float, float], ...]) -> list[list[str]]:
    return [[finite_float(value) for value in row] for row in matrix]


def _complex_vector(values: Any, name: str, *, length: int | None = None) -> tuple[complex, ...]:
    if isinstance(values, torch.Tensor):
        if values.ndim != 1:
            raise QiBodyError(f"{name} must be a one-dimensional vector")
        values = values.detach().cpu().tolist()
    if isinstance(values, (str, bytes, bytearray)):
        raise QiBodyError(f"{name} must be a complex vector")
    try:
        result = tuple(complex(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise QiBodyError(f"{name} must be a complex vector") from exc
    if not result or length is not None and len(result) != length:
        raise QiBodyError(f"{name} has the wrong length")
    if any(not math.isfinite(value.real) or not math.isfinite(value.imag) for value in result):
        raise QiBodyError(f"{name} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class QiBodyPose:
    """A validated, immutable world-to-body rigid pose."""

    body_frame_id: str
    translation_world: tuple[float, float, float]
    rotation_body_from_world: tuple[tuple[float, float, float], ...]
    pose_sha256: str = ""

    def __post_init__(self) -> None:
        frame = _text(self.body_frame_id, "body_frame_id")
        translation = _vec3(self.translation_world, "translation_world")
        rotation = _matrix3(self.rotation_body_from_world, "rotation_body_from_world")
        gram = _matrix_multiply(rotation, _matrix_transpose(rotation))
        if _matrix_error(gram, _identity3()) > 1.0e-10 or abs(_matrix_det(rotation) - 1.0) > 1.0e-10:
            raise QiBodyError("rotation_body_from_world must be a proper orthogonal matrix")
        object.__setattr__(self, "body_frame_id", frame)
        object.__setattr__(self, "translation_world", translation)
        object.__setattr__(self, "rotation_body_from_world", rotation)
        expected = _canonical(self.canonical_payload(include_hash=False), BODY_POSE_SCHEMA)
        if self.pose_sha256 and self.pose_sha256 != expected:
            raise QiBodyError("body pose identity mismatch")
        object.__setattr__(self, "pose_sha256", expected)

    @classmethod
    def identity(cls, body_frame_id: str = "body-frame") -> "QiBodyPose":
        return cls(body_frame_id, (0.0, 0.0, 0.0), _identity3())

    @classmethod
    def create(
        cls,
        body_frame_id: str,
        translation_world: Sequence[float],
        rotation_body_from_world: Sequence[Sequence[float]] | torch.Tensor,
    ) -> "QiBodyPose":
        return cls(body_frame_id, _vec3(translation_world, "translation_world"), _matrix3(rotation_body_from_world, "rotation_body_from_world"))

    @property
    def translation(self) -> tuple[float, float, float]:
        return self.translation_world

    @property
    def rotation(self) -> tuple[tuple[float, float, float], ...]:
        return self.rotation_body_from_world

    def world_to_body(self, point_world: Sequence[float]) -> tuple[float, float, float]:
        point = _vec3(point_world, "point_world")
        return _matrix_vector(self.rotation_body_from_world, tuple(point[index] - self.translation_world[index] for index in range(3)))

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": BODY_POSE_SCHEMA,
            "body_frame_id": self.body_frame_id,
            "translation_world": _float_payload(self.translation_world),
            "rotation_body_from_world": _matrix_payload(self.rotation_body_from_world),
        }
        if include_hash:
            body["pose_sha256"] = self.pose_sha256
        return body


@dataclass(frozen=True, slots=True)
class QiBodyMotion:
    """One acknowledged rigid transition, with no retained pose estimator."""

    body_frame_id: str
    predecessor_pose_sha256: str
    successor_pose_sha256: str
    translation_delta_world: tuple[float, float, float]
    rotation_delta_body: tuple[tuple[float, float, float], ...]
    motion_sha256: str = ""

    def __post_init__(self) -> None:
        frame = _text(self.body_frame_id, "body_frame_id")
        previous = _sha(self.predecessor_pose_sha256, "predecessor_pose_sha256")
        successor = _sha(self.successor_pose_sha256, "successor_pose_sha256")
        delta = _vec3(self.translation_delta_world, "translation_delta_world")
        rotation = _matrix3(self.rotation_delta_body, "rotation_delta_body")
        if _matrix_error(_matrix_multiply(rotation, _matrix_transpose(rotation)), _identity3()) > 1.0e-10 or abs(_matrix_det(rotation) - 1.0) > 1.0e-10:
            raise QiBodyError("rotation_delta_body must be a proper orthogonal matrix")
        object.__setattr__(self, "body_frame_id", frame)
        object.__setattr__(self, "predecessor_pose_sha256", previous)
        object.__setattr__(self, "successor_pose_sha256", successor)
        object.__setattr__(self, "translation_delta_world", delta)
        object.__setattr__(self, "rotation_delta_body", rotation)
        expected = _canonical(self.canonical_payload(include_hash=False), BODY_MOTION_SCHEMA)
        if self.motion_sha256 and self.motion_sha256 != expected:
            raise QiBodyError("body motion identity mismatch")
        object.__setattr__(self, "motion_sha256", expected)

    @classmethod
    def between(cls, predecessor: QiBodyPose, successor: QiBodyPose) -> "QiBodyMotion":
        if not isinstance(predecessor, QiBodyPose) or not isinstance(successor, QiBodyPose):
            raise QiBodyError("body motion requires two QiBodyPose values")
        if predecessor.body_frame_id != successor.body_frame_id:
            raise QiBodyError("body motion frame identities differ")
        rotation = _matrix_multiply(successor.rotation_body_from_world, _matrix_transpose(predecessor.rotation_body_from_world))
        delta = tuple(successor.translation_world[index] - predecessor.translation_world[index] for index in range(3))
        return cls(predecessor.body_frame_id, predecessor.pose_sha256, successor.pose_sha256, delta, rotation)

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": BODY_MOTION_SCHEMA,
            "body_frame_id": self.body_frame_id,
            "predecessor_pose_sha256": self.predecessor_pose_sha256,
            "successor_pose_sha256": self.successor_pose_sha256,
            "translation_delta_world": _float_payload(self.translation_delta_world),
            "rotation_delta_body": _matrix_payload(self.rotation_delta_body),
        }
        if include_hash:
            body["motion_sha256"] = self.motion_sha256
        return body


@dataclass(frozen=True, slots=True)
class QiBodyFrameDescriptor:
    """Immutable numerical registration for one body frame and remap class."""

    body_frame_id: str
    world_handedness: str = "right"
    engineering_origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    body_axes: tuple[tuple[float, float, float], ...] = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    sensor_extrinsics: tuple[float, ...] = ()
    actuator_extrinsics: tuple[float, ...] = ()
    remap_mode: str = "finite-aperture"
    grid_shape: tuple[int, int] = (1, 1)
    grid_spacing: tuple[float, float] = (1.0, 1.0)
    guard_band: tuple[int, int] = (0, 0)
    topology_permutation: tuple[int, ...] = ()
    epsilon_mass_weights: tuple[float, ...] = ()
    descriptor_sha256: str = ""

    def __post_init__(self) -> None:
        frame = _text(self.body_frame_id, "body_frame_id")
        handedness = _text(self.world_handedness, "world_handedness")
        if handedness not in {"right", "left"}:
            raise QiBodyError("world_handedness must be right or left")
        origin = _vec3(self.engineering_origin, "engineering_origin")
        axes = _matrix3(self.body_axes, "body_axes")
        if _matrix_error(_matrix_multiply(axes, _matrix_transpose(axes)), _identity3()) > 1.0e-10:
            raise QiBodyError("body_axes must be orthonormal")
        if (handedness == "right" and _matrix_det(axes) < 0.0) or (handedness == "left" and _matrix_det(axes) > 0.0):
            raise QiBodyError("body_axes determinant disagrees with world_handedness")
        mode = _text(self.remap_mode, "remap_mode")
        if mode not in {"guarded-periodic", "finite-aperture"}:
            raise QiBodyError("remap_mode must be guarded-periodic or finite-aperture")
        if len(self.grid_shape) != 2 or any(_integer(value, "grid_shape", minimum=1) != value for value in self.grid_shape):
            raise QiBodyError("grid_shape must contain two positive integers")
        spacing = _positive_vector(self.grid_spacing, "grid_spacing", length=2)
        if len(self.guard_band) != 2 or any(_integer(value, "guard_band", minimum=0) != value for value in self.guard_band):
            raise QiBodyError("guard_band must contain two nonnegative integers")
        sensor = tuple(_finite(value, "sensor_extrinsics") for value in self.sensor_extrinsics)
        actuator = tuple(_finite(value, "actuator_extrinsics") for value in self.actuator_extrinsics)
        topology = tuple(_integer(value, "topology_permutation", minimum=0) for value in self.topology_permutation)
        if topology and sorted(topology) != list(range(len(topology))):
            raise QiBodyError("topology_permutation must be a permutation")
        masses = tuple(_positive_vector(self.epsilon_mass_weights, "epsilon_mass_weights")) if self.epsilon_mass_weights else ()
        object.__setattr__(self, "body_frame_id", frame)
        object.__setattr__(self, "world_handedness", handedness)
        object.__setattr__(self, "engineering_origin", origin)
        object.__setattr__(self, "body_axes", axes)
        object.__setattr__(self, "sensor_extrinsics", sensor)
        object.__setattr__(self, "actuator_extrinsics", actuator)
        object.__setattr__(self, "grid_spacing", (spacing[0], spacing[1]))
        object.__setattr__(self, "guard_band", (self.guard_band[0], self.guard_band[1]))
        object.__setattr__(self, "topology_permutation", topology)
        object.__setattr__(self, "epsilon_mass_weights", masses)
        expected = _canonical(self.canonical_payload(include_hash=False), BODY_FRAME_SCHEMA)
        if self.descriptor_sha256 and self.descriptor_sha256 != expected:
            raise QiBodyError("body frame descriptor identity mismatch")
        object.__setattr__(self, "descriptor_sha256", expected)

    @classmethod
    def create(cls, body_frame_id: str = "body-frame", **kwargs: Any) -> "QiBodyFrameDescriptor":
        return cls(body_frame_id=body_frame_id, **kwargs)

    @property
    def handedness(self) -> str:
        return self.world_handedness

    @property
    def origin(self) -> tuple[float, float, float]:
        return self.engineering_origin

    @property
    def axes(self) -> tuple[tuple[float, float, float], ...]:
        return self.body_axes

    def affine(self, predecessor: QiBodyPose, successor: QiBodyPose) -> tuple[tuple[tuple[float, float, float], ...], tuple[float, float, float]]:
        if predecessor.body_frame_id != self.body_frame_id or successor.body_frame_id != self.body_frame_id:
            raise QiBodyError("pose frame does not match descriptor")
        a = _matrix_multiply(successor.rotation_body_from_world, _matrix_transpose(predecessor.rotation_body_from_world))
        b = _matrix_vector(successor.rotation_body_from_world, tuple(predecessor.translation_world[index] - successor.translation_world[index] for index in range(3)))
        return a, b

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": BODY_FRAME_SCHEMA,
            "body_frame_id": self.body_frame_id,
            "world_handedness": self.world_handedness,
            "engineering_origin": _float_payload(self.engineering_origin),
            "body_axes": _matrix_payload(self.body_axes),
            "sensor_extrinsics": _float_payload(self.sensor_extrinsics),
            "actuator_extrinsics": _float_payload(self.actuator_extrinsics),
            "remap_mode": self.remap_mode,
            "grid_shape": list(self.grid_shape),
            "grid_spacing": _float_payload(self.grid_spacing),
            "guard_band": list(self.guard_band),
            "topology_permutation": list(self.topology_permutation),
            "epsilon_mass_weights": _float_payload(self.epsilon_mass_weights),
        }
        if include_hash:
            body["descriptor_sha256"] = self.descriptor_sha256
        return body

    def remap(
        self,
        field: torch.Tensor,
        predecessor: QiBodyPose,
        successor: QiBodyPose,
        *,
        scale_id: str = "default",
        epsilon2_ema: bool = False,
        topology_vector: Sequence[float] | None = None,
    ) -> tuple[torch.Tensor, "QiBodyRemapReceipt"]:
        return remap_body_field(self, field, predecessor, successor, scale_id=scale_id, epsilon2_ema=epsilon2_ema, topology_vector=topology_vector)


def _integer_shift(value: float, name: str) -> int:
    rounded = round(value)
    if abs(value - rounded) > 1.0e-10:
        raise QiBodyError(f"{name} is fractional; registered exact remaps reject interpolation")
    return int(rounded)


def _quarter_turn(matrix: tuple[tuple[float, float, float], ...]) -> int | None:
    candidates = (
        _identity3(),
        ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    )
    for index, candidate in enumerate(candidates):
        if _matrix_error(matrix, candidate) <= 1.0e-10:
            return index
    return None


def _finite_aperture_shift(field: torch.Tensor, shift_y: int, shift_x: int) -> torch.Tensor:
    result = torch.roll(field, shifts=(shift_y, shift_x), dims=(-2, -1))
    if shift_y > 0:
        result[..., :shift_y, :] = 0
    elif shift_y < 0:
        result[..., shift_y:, :] = 0
    if shift_x > 0:
        result[..., :, :shift_x] = 0
    elif shift_x < 0:
        result[..., :, shift_x:] = 0
    return result


def _topology_index_shift(shape: tuple[int, int], shift_y: int, shift_x: int) -> tuple[int, ...]:
    height, width = shape
    return tuple(((row - shift_y) % height) * width + ((column - shift_x) % width) for row in range(height) for column in range(width))


@dataclass(frozen=True, slots=True)
class QiBodyRemapReceipt:
    """Immutable work/topology evidence for one zero-clock body remap."""

    descriptor_sha256: str
    body_frame_id: str
    predecessor_pose_sha256: str
    successor_pose_sha256: str
    scale_id: str
    remap_mode: str
    affine_a: tuple[tuple[float, float, float], ...]
    affine_b: tuple[float, float, float]
    work: float
    mass_before: float
    mass_after: float
    minimum_before: float
    minimum_after: float
    diffusion_residual: float
    forward_reverse_error: float
    topology_permutation: tuple[int, ...]
    admitted: bool
    remap_sha256: str = ""

    def __post_init__(self) -> None:
        descriptor = _sha(self.descriptor_sha256, "descriptor_sha256")
        frame = _text(self.body_frame_id, "body_frame_id")
        predecessor = _sha(self.predecessor_pose_sha256, "predecessor_pose_sha256")
        successor = _sha(self.successor_pose_sha256, "successor_pose_sha256")
        scale = _text(self.scale_id, "scale_id")
        mode = _text(self.remap_mode, "remap_mode")
        a = _matrix3(self.affine_a, "affine_a")
        b = _vec3(self.affine_b, "affine_b")
        numbers = tuple(_finite(value, "remap metric") for value in (self.work, self.mass_before, self.mass_after, self.minimum_before, self.minimum_after, self.diffusion_residual, self.forward_reverse_error))
        if numbers[1] < -_CLOSURE_TOLERANCE or numbers[2] < -_CLOSURE_TOLERANCE or numbers[5] < -_CLOSURE_TOLERANCE or numbers[6] < -_CLOSURE_TOLERANCE:
            raise QiBodyError("remap receipt contains an invalid metric")
        permutation = tuple(_integer(value, "topology_permutation", minimum=0) for value in self.topology_permutation)
        if permutation and sorted(permutation) != list(range(len(permutation))):
            raise QiBodyError("remap topology row is not a permutation")
        object.__setattr__(self, "descriptor_sha256", descriptor)
        object.__setattr__(self, "body_frame_id", frame)
        object.__setattr__(self, "predecessor_pose_sha256", predecessor)
        object.__setattr__(self, "successor_pose_sha256", successor)
        object.__setattr__(self, "scale_id", scale)
        object.__setattr__(self, "remap_mode", mode)
        object.__setattr__(self, "affine_a", a)
        object.__setattr__(self, "affine_b", b)
        object.__setattr__(self, "topology_permutation", permutation)
        for name, value in zip(("work", "mass_before", "mass_after", "minimum_before", "minimum_after", "diffusion_residual", "forward_reverse_error"), numbers):
            object.__setattr__(self, name, value)
        expected = _canonical(self.canonical_payload(include_hash=False), BODY_REMAP_SCHEMA)
        if self.remap_sha256 and self.remap_sha256 != expected:
            raise QiBodyError("body remap identity mismatch")
        object.__setattr__(self, "remap_sha256", expected)

    @property
    def closure(self) -> float:
        return self.mass_after - self.mass_before


    @property
    def transform_sha256(self) -> str:
        return _canonical(
            {"affine_a": _matrix_payload(self.affine_a), "affine_b": _float_payload(self.affine_b)},
            BODY_TRANSFORM_SCHEMA,
        )

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": BODY_REMAP_SCHEMA,
            "descriptor_sha256": self.descriptor_sha256,
            "body_frame_id": self.body_frame_id,
            "predecessor_pose_sha256": self.predecessor_pose_sha256,
            "successor_pose_sha256": self.successor_pose_sha256,
            "scale_id": self.scale_id,
            "remap_mode": self.remap_mode,
            "affine_a": _matrix_payload(self.affine_a),
            "affine_b": _float_payload(self.affine_b),
            "work": finite_float(self.work),
            "mass_before": finite_float(self.mass_before),
            "mass_after": finite_float(self.mass_after),
            "minimum_before": finite_float(self.minimum_before),
            "minimum_after": finite_float(self.minimum_after),
            "diffusion_residual": finite_float(self.diffusion_residual),
            "forward_reverse_error": finite_float(self.forward_reverse_error),
            "topology_permutation": list(self.topology_permutation),
            "admitted": self.admitted,
        }
        if include_hash:
            body["remap_sha256"] = self.remap_sha256
        return body


def remap_body_field(
    descriptor: QiBodyFrameDescriptor,
    field: torch.Tensor,
    predecessor: QiBodyPose,
    successor: QiBodyPose,
    *,
    scale_id: str = "default",
    epsilon2_ema: bool = False,
    topology_vector: Sequence[float] | None = None,
) -> tuple[torch.Tensor, QiBodyRemapReceipt]:
    if not isinstance(descriptor, QiBodyFrameDescriptor) or not isinstance(field, torch.Tensor):
        raise QiBodyError("body remap requires a descriptor and torch field")
    if field.ndim < 2 or tuple(field.shape[-2:]) != descriptor.grid_shape:
        raise QiBodyError("field trailing shape does not match the registered grid")
    if not field.is_floating_point() and not field.is_complex():
        raise QiBodyError("body remap requires a real or complex floating field")
    if not bool(torch.isfinite(field.real).all()) or not bool(torch.isfinite(field.imag if field.is_complex() else field).all()):
        raise QiBodyError("body remap field must be finite")
    if epsilon2_ema and bool((field.real < 0).any()):
        raise QiBodyError("epsilon2_ema remap requires nonnegative input")
    a, b = descriptor.affine(predecessor, successor)
    turn = _quarter_turn(a)
    if turn is None:
        raise QiBodyError("registered remap admits only exact identity/quarter-turn rotations")
    shift_x = _integer_shift(b[0] / descriptor.grid_spacing[0], "x remap")
    shift_y = _integer_shift(b[1] / descriptor.grid_spacing[1], "y remap")
    if descriptor.remap_mode == "guarded-periodic" and (abs(shift_x) > descriptor.guard_band[0] or abs(shift_y) > descriptor.guard_band[1]):
        raise QiBodyError("guarded-periodic remap horizon exceeds the declared guard band")
    if turn and descriptor.grid_shape[0] != descriptor.grid_shape[1]:
        raise QiBodyError("quarter-turn remap requires a square registered grid")
    permutation = descriptor.topology_permutation if descriptor.topology_permutation else (_topology_index_shift(descriptor.grid_shape, shift_y, shift_x) if descriptor.remap_mode == "guarded-periodic" else tuple())
    if topology_vector is not None:
        if not descriptor.topology_permutation:
            raise QiBodyError("topology transport requires a registered topology permutation")
        vector = _vector(topology_vector, "topology_vector", length=len(permutation))
        transported = tuple(vector[index] for index in permutation)
        if len(transported) != len(vector):
            raise QiBodyError("topology transport dimension mismatch")
    remapped = field
    if turn:
        remapped = torch.rot90(remapped, turns=turn, dims=(-2, -1))
    if descriptor.remap_mode == "guarded-periodic":
        remapped = torch.roll(remapped, shifts=(shift_y, shift_x), dims=(-2, -1))
    else:
        remapped = _finite_aperture_shift(remapped, shift_y, shift_x)
    if epsilon2_ema and bool((remapped.real < -1.0e-12).any()):
        raise QiBodyError("epsilon2_ema remap violated positivity")
    before_mass = float(field.real.sum().item())
    after_mass = float(remapped.real.sum().item())
    before_min = float(field.real.min().item())
    after_min = float(remapped.real.min().item())
    work = 0.5 * float((remapped.abs().square().sum() - field.abs().square().sum()).item())
    receipt = QiBodyRemapReceipt(
        descriptor_sha256=descriptor.descriptor_sha256,
        body_frame_id=descriptor.body_frame_id,
        predecessor_pose_sha256=predecessor.pose_sha256,
        successor_pose_sha256=successor.pose_sha256,
        scale_id=scale_id,
        remap_mode=descriptor.remap_mode,
        affine_a=a,
        affine_b=b,
        work=work,
        mass_before=before_mass,
        mass_after=after_mass,
        minimum_before=before_min,
        minimum_after=after_min,
        diffusion_residual=0.0,
        forward_reverse_error=0.0,
        topology_permutation=permutation,
        admitted=True,
    )
    return remapped.clone(), receipt


def remap_body_field_round_trip(
    descriptor: QiBodyFrameDescriptor,
    field: torch.Tensor,
    predecessor: QiBodyPose,
    successor: QiBodyPose,
    *,
    scale_id: str = "default",
    epsilon2_ema: bool = False,
) -> tuple[torch.Tensor, QiBodyRemapReceipt, float]:
    forward, receipt = remap_body_field(descriptor, field, predecessor, successor, scale_id=scale_id, epsilon2_ema=epsilon2_ema)
    reverse, _ = remap_body_field(descriptor, forward, successor, predecessor, scale_id=scale_id, epsilon2_ema=epsilon2_ema)
    error = float((reverse - field).abs().max().item())
    return reverse, QiBodyRemapReceipt(
        descriptor_sha256=receipt.descriptor_sha256,
        body_frame_id=receipt.body_frame_id,
        predecessor_pose_sha256=receipt.predecessor_pose_sha256,
        successor_pose_sha256=receipt.successor_pose_sha256,
        scale_id=receipt.scale_id,
        remap_mode=receipt.remap_mode,
        affine_a=receipt.affine_a,
        affine_b=receipt.affine_b,
        work=receipt.work,
        mass_before=receipt.mass_before,
        mass_after=receipt.mass_after,
        minimum_before=receipt.minimum_before,
        minimum_after=receipt.minimum_after,
        diffusion_residual=receipt.diffusion_residual,
        forward_reverse_error=error,
        topology_permutation=receipt.topology_permutation,
        admitted=receipt.admitted,
    ), error
def _optional_sha(value: Any, name: str) -> str | None:
    return None if value is None else _sha(value, name)


def _canonical_tick(value: Any, name: str) -> Any:
    if isinstance(value, QiClockTime):
        return value.payload()
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise QiBodyError(f"{name} must be a nonnegative logical tick or QiClockTime")
    return value


def _tick(value: Any, name: str) -> QiClockTime:
    return _clock(value, name)


def _ack_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise QiBodyError("body accepts a BoundaryRuntime-validated acknowledgement object, not ack bytes")
    if isinstance(value, Mapping):
        raise QiBodyError("body accepts a BoundaryRuntime-validated acknowledgement object, not a plain mapping")
    canonical = getattr(value, "canonical_payload", None)
    if not callable(canonical):
        raise QiBodyError("body accepts only a BoundaryRuntime-validated tick acknowledgement object")
    try:
        payload = canonical(include_hash=True)
    except TypeError:
        payload = canonical()
    return _strict_mapping(payload, "validated tick acknowledgement")


def _validated_ack_projection(value: Any) -> dict[str, Any]:
    """Project only terminal-applied fields from a validated world ack."""
    payload = _ack_payload(value)
    if payload.get("schema") != _TICK_ACK_SCHEMA:
        raise QiBodyError("validated acknowledgement has the wrong schema")
    if payload.get("status") != "applied" or payload.get("terminal_status") != "applied" or payload.get("world_effect") != "true":
        raise QiBodyError("only a terminal applied acknowledgement may enter the body")
    for name in ("world_id", "episode_id", "session_id", "action_id"):
        _bounded_text(_member(payload, name), name)
    _world_tick(_member(payload, "cycle_number"), "cycle_number")
    _sha(_member(payload, "ack_sha256"), "ack_sha256")
    _sha(_member(payload, "original_terminal_ack_sha256"), "original_terminal_ack_sha256")
    _base64_text(_member(payload, "ack_bytes"), "ack_bytes")
    application = _world_tick(_member(payload, "application_tick"), "application_tick")
    effective = _world_tick(_member(payload, "effective_tick"), "effective_tick")
    first_visible = _world_tick(_member(payload, "first_visible_observation_tick"), "first_visible_observation_tick")
    if effective < application or first_visible < effective:
        raise QiBodyError("validated acknowledgement timing is not monotonic")
    _actual_values(_member(payload, "applied_values"))
    transition = _strict_mapping(_member(payload, "body_transition"), "body_transition")
    if set(transition) != {"before_body_frame_id", "after_body_frame_id", "remap_sha256"}:
        raise QiBodyError("validated acknowledgement body transition is incomplete")
    _bounded_text(transition["before_body_frame_id"], "before_body_frame_id")
    _bounded_text(transition["after_body_frame_id"], "after_body_frame_id")
    _sha(transition["remap_sha256"], "remap_sha256")
    return payload


@dataclass(frozen=True, slots=True)
class QiEfferenceCopy:
    """Immutable Commit-B projection of one terminal applied world ack."""

    efference_id: str
    world_id: str
    episode_id: str
    session_id: str
    cycle_number: int
    action_id: str
    command_sha256: str
    proposal_sha256: str
    reaction_sha256: str
    committed_prior_head_sha256: str
    application_tick: int
    first_visible_observation_tick: int
    actual_values: tuple[tuple[str, str], ...]
    body_transition: tuple[str, str, str]
    terminal_ack_sha256: str
    terminal_ack_bytes: str | bytes
    world_effect: bool
    consumption_status: str
    applied_efference_sha256: str = ""

    def __post_init__(self) -> None:
        efference_id = _bounded_text(self.efference_id, "efference_id")
        world = _bounded_text(self.world_id, "world_id")
        episode = _bounded_text(self.episode_id, "episode_id")
        session = _bounded_text(self.session_id, "session_id")
        cycle = _world_tick(self.cycle_number, "cycle_number")
        action = _bounded_text(self.action_id, "action_id")
        command = _sha(self.command_sha256, "command_sha256")
        proposal = _sha(self.proposal_sha256, "proposal_sha256")
        reaction = _sha(self.reaction_sha256, "reaction_sha256")
        committed_prior = _sha(self.committed_prior_head_sha256, "committed_prior_head_sha256")
        application = _world_tick(self.application_tick, "application_tick")
        first_visible = _world_tick(self.first_visible_observation_tick, "first_visible_observation_tick")
        if first_visible < application:
            raise QiBodyError("first visible observation precedes application")
        values = _actual_values(self.actual_values)
        transition = _body_transition(self.body_transition)
        terminal_ack = _sha(self.terminal_ack_sha256, "terminal_ack_sha256")
        terminal_ack_bytes = _terminal_ack_text(self.terminal_ack_bytes, "terminal_ack_bytes")
        if self.world_effect is not True:
            raise QiBodyError("applied-efference world_effect must be true")
        consumption_status = _text(self.consumption_status, "consumption_status")
        if consumption_status not in {"pending", "consumed"}:
            raise QiBodyError("consumption_status must be pending or consumed")
        object.__setattr__(self, "efference_id", efference_id)
        object.__setattr__(self, "world_id", world)
        object.__setattr__(self, "episode_id", episode)
        object.__setattr__(self, "session_id", session)
        object.__setattr__(self, "cycle_number", cycle)
        object.__setattr__(self, "action_id", action)
        object.__setattr__(self, "command_sha256", command)
        object.__setattr__(self, "proposal_sha256", proposal)
        object.__setattr__(self, "reaction_sha256", reaction)
        object.__setattr__(self, "committed_prior_head_sha256", committed_prior)
        object.__setattr__(self, "application_tick", application)
        object.__setattr__(self, "first_visible_observation_tick", first_visible)
        object.__setattr__(self, "actual_values", values)
        object.__setattr__(self, "body_transition", transition)
        object.__setattr__(self, "terminal_ack_sha256", terminal_ack)
        object.__setattr__(self, "terminal_ack_bytes", terminal_ack_bytes)
        object.__setattr__(self, "consumption_status", consumption_status)
        expected = _canonical(self.canonical_payload(include_hash=False), EFFERENCE_SCHEMA)
        if self.applied_efference_sha256:
            supplied = _sha(self.applied_efference_sha256, "applied_efference_sha256")
            if supplied != expected:
                raise QiBodyError("applied-efference identity mismatch")
        object.__setattr__(self, "applied_efference_sha256", expected)

    @classmethod
    def from_validated_ack(
        cls,
        acknowledgement: Any,
        *,
        terminal_ack_bytes: str | bytes | bytearray | memoryview,
        remap: QiBodyRemapReceipt,
        efference_id: str,
        command_sha256: str,
        proposal_sha256: str,
        reaction_sha256: str,
        committed_prior_head_sha256: str,
    ) -> "QiEfferenceCopy":
        if not isinstance(remap, QiBodyRemapReceipt):
            raise QiBodyError("applied-efference construction requires a body remap receipt")
        payload = _validated_ack_projection(acknowledgement)
        transition = _body_transition(_member(payload, "body_transition"), "validated body_transition")
        if transition[2] != remap.remap_sha256:
            raise QiBodyError("acknowledgement/remap identity mismatch")
        ack_bytes = _base64_text(_member(payload, "ack_bytes"), "ack_bytes")
        supplied_ack_bytes = _terminal_ack_text(terminal_ack_bytes, "terminal_ack_bytes")
        if supplied_ack_bytes != ack_bytes:
            raise QiBodyError("terminal acknowledgement bytes do not match the validated tick acknowledgement")
        terminal_ack_sha256 = _sha(_member(payload, "original_terminal_ack_sha256"), "original_terminal_ack_sha256")
        return cls(
            efference_id=efference_id,
            world_id=_member(payload, "world_id"),
            episode_id=_member(payload, "episode_id"),
            session_id=_member(payload, "session_id"),
            cycle_number=_member(payload, "cycle_number"),
            action_id=_member(payload, "action_id"),
            command_sha256=command_sha256,
            proposal_sha256=proposal_sha256,
            reaction_sha256=reaction_sha256,
            committed_prior_head_sha256=committed_prior_head_sha256,
            application_tick=_member(payload, "application_tick"),
            first_visible_observation_tick=_member(payload, "first_visible_observation_tick"),
            actual_values=_member(payload, "applied_values"),
            body_transition=transition,
            terminal_ack_sha256=terminal_ack_sha256,
            terminal_ack_bytes=ack_bytes,
            world_effect=True,
            consumption_status="pending",
        )

    def consume(self) -> "QiEfferenceCopy":
        if self.consumption_status != "pending":
            raise QiBodyError("applied-efference has already been consumed")
        return replace(self, consumption_status="consumed", applied_efference_sha256="")

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": EFFERENCE_SCHEMA,
            "efference_id": self.efference_id,
            "world_id": self.world_id,
            "episode_id": self.episode_id,
            "session_id": self.session_id,
            "cycle_number": self.cycle_number,
            "action_id": self.action_id,
            "command_sha256": self.command_sha256,
            "proposal_sha256": self.proposal_sha256,
            "reaction_sha256": self.reaction_sha256,
            "committed_prior_head_sha256": self.committed_prior_head_sha256,
            "application_tick": self.application_tick,
            "first_visible_observation_tick": self.first_visible_observation_tick,
            "actual_values": _actual_payload(self.actual_values),
            "body_transition": _body_transition_payload(self.body_transition),
            "terminal_ack_sha256": self.terminal_ack_sha256,
            "terminal_ack_bytes": self.terminal_ack_bytes,
            "world_effect": True,
            "consumption_status": self.consumption_status,
        }
        if include_hash:
            body["applied_efference_sha256"] = self.applied_efference_sha256
        return body


@dataclass(frozen=True, slots=True)
class QiBodyPrediction:
    """Successor-timed world/self prediction with explicit status gate."""

    predecessor_state_sha256: str
    predecessor_tick: QiClockTime
    observation_tick: QiClockTime
    body_frame_id: str
    predicted_world: tuple[complex, ...]
    predicted_self: tuple[complex, ...]
    self_gate: int
    efference_sha256: str | None
    prediction_sha256: str = ""

    def __post_init__(self) -> None:
        predecessor = _sha(self.predecessor_state_sha256, "predecessor_state_sha256")
        previous_tick = _tick(self.predecessor_tick, "predecessor_tick")
        observation = _tick(self.observation_tick, "observation_tick")
        if observation <= previous_tick:
            raise QiBodyError("prediction observation must be successor-timed")
        frame = _text(self.body_frame_id, "body_frame_id")
        world = _complex_vector(self.predicted_world, "predicted_world")
        self_prediction = _complex_vector(self.predicted_self, "predicted_self", length=len(world))
        gate = _integer(self.self_gate, "self_gate", minimum=0)
        if gate not in {0, 1}:
            raise QiBodyError("self_gate must be 0 or 1")
        efference = _optional_sha(self.efference_sha256, "efference_sha256")
        if gate == 1 and efference is None:
            raise QiBodyError("self_gate=1 requires an efference identity")
        if gate == 0 and any(value != 0j for value in self_prediction):
            raise QiBodyError("self prediction must be exactly zero when self_gate=0")
        object.__setattr__(self, "predecessor_state_sha256", predecessor)
        object.__setattr__(self, "predecessor_tick", previous_tick)
        object.__setattr__(self, "observation_tick", observation)
        object.__setattr__(self, "body_frame_id", frame)
        object.__setattr__(self, "predicted_world", world)
        object.__setattr__(self, "predicted_self", self_prediction)
        object.__setattr__(self, "self_gate", gate)
        object.__setattr__(self, "efference_sha256", efference)
        expected = _canonical(self.canonical_payload(include_hash=False), PREDICTION_SCHEMA)
        if self.prediction_sha256 and self.prediction_sha256 != expected:
            raise QiBodyError("body prediction identity mismatch")
        object.__setattr__(self, "prediction_sha256", expected)

    @classmethod
    def from_efference(
        cls,
        *,
        predecessor: QiBodyState,
        observation_tick: QiClockTime,
        predicted_world: Sequence[complex],
        predicted_self: Sequence[complex],
        efference: QiEfferenceCopy,
    ) -> "QiBodyPrediction":
        if not isinstance(predecessor, QiBodyState) or not isinstance(efference, QiEfferenceCopy):
            raise QiBodyError("prediction requires a predecessor state and efference copy")
        transition = _body_transition(efference.body_transition)
        if predecessor.body_frame_id and transition[0] != predecessor.body_frame_id:
            raise QiBodyError("efference body frame does not match predecessor body frame")
        observation = _tick(observation_tick, "observation_tick")
        if observation < QiClockTime.make(efference.first_visible_observation_tick):
            raise QiBodyError("prediction observation precedes the first visible effect tick")
        return cls(
            predecessor_state_sha256=predecessor.state_sha256,
            predecessor_tick=predecessor.clock,
            observation_tick=observation,
            body_frame_id=transition[1],
            predicted_world=_complex_vector(predicted_world, "predicted_world"),
            predicted_self=_complex_vector(predicted_self, "predicted_self"),
            self_gate=1,
            efference_sha256=efference.applied_efference_sha256,
        )

    @classmethod
    def without_self(
        cls,
        *,
        predecessor: QiBodyState,
        observation_tick: QiClockTime,
        predicted_world: Sequence[complex],
        body_frame_id: str,
    ) -> "QiBodyPrediction":
        world = _complex_vector(predicted_world, "predicted_world")
        return cls(predecessor.state_sha256, predecessor.clock, observation_tick, body_frame_id, world, tuple(0j for _ in world), 0, None)

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        def complex_payload(values: Sequence[complex]) -> list[list[str]]:
            return [[finite_float(value.real), finite_float(value.imag)] for value in values]

        body: dict[str, Any] = {
            "schema": PREDICTION_SCHEMA,
            "predecessor_state_sha256": self.predecessor_state_sha256,
            "predecessor_tick": self.predecessor_tick.payload(),
            "observation_tick": self.observation_tick.payload(),
            "body_frame_id": self.body_frame_id,
            "predicted_world": complex_payload(self.predicted_world),
            "predicted_self": complex_payload(self.predicted_self),
            "self_gate": self.self_gate,
            "efference_sha256": self.efference_sha256,
        }
        if include_hash:
            body["prediction_sha256"] = self.prediction_sha256
        return body


@dataclass(frozen=True, slots=True)
class QiResidualReturn:
    """Pre-correction successor residual and next-call adjoint packet."""

    prediction_sha256: str
    predecessor_tick: QiClockTime
    observation_tick: QiClockTime
    effective_tick: QiClockTime
    body_frame_id: str
    observed: tuple[complex, ...]
    predicted_world: tuple[complex, ...]
    predicted_self: tuple[complex, ...]
    self_gate: int
    residual: tuple[complex, ...]
    residual_force: tuple[complex, ...]
    port_name: str
    eta: float
    source_identity: str
    packet_identities: tuple[str, ...]
    queued_residual_sha256: str
    no_sample: bool = False
    residual_sha256: str = ""

    def __post_init__(self) -> None:
        prediction = _sha(self.prediction_sha256, "prediction_sha256")
        predecessor = _tick(self.predecessor_tick, "predecessor_tick")
        observation = _tick(self.observation_tick, "observation_tick")
        effective = _tick(self.effective_tick, "effective_tick")
        if observation <= predecessor or effective != observation:
            raise QiBodyError("residual return must be successor-timed and effective on the next call")
        frame = _text(self.body_frame_id, "body_frame_id")
        observed = _complex_vector(self.observed, "observed")
        world = _complex_vector(self.predicted_world, "predicted_world", length=len(observed))
        self_prediction = _complex_vector(self.predicted_self, "predicted_self", length=len(observed))
        residual = _complex_vector(self.residual, "residual", length=len(observed))
        force = _complex_vector(self.residual_force, "residual_force")
        gate = _integer(self.self_gate, "self_gate", minimum=0)
        if gate not in {0, 1}:
            raise QiBodyError("self_gate must be 0 or 1")
        eta = _finite(self.eta, "eta")
        if eta < 0.0:
            raise QiBodyError("eta must be nonnegative")
        source = _identity_text(self.source_identity, "source_identity")
        packets = tuple(_sha(value, "packet identity") for value in self.packet_identities)
        queued = _sha(self.queued_residual_sha256, "queued_residual_sha256")
        expected_residual = tuple(observed[index] - world[index] - gate * self_prediction[index] for index in range(len(observed)))
        if any(abs(left - right) > 1.0e-10 for left, right in zip(expected_residual, residual)):
            raise QiBodyError("residual is not observed minus gated world/self prediction")
        object.__setattr__(self, "prediction_sha256", prediction)
        object.__setattr__(self, "predecessor_tick", predecessor)
        object.__setattr__(self, "observation_tick", observation)
        object.__setattr__(self, "effective_tick", effective)
        object.__setattr__(self, "body_frame_id", frame)
        object.__setattr__(self, "observed", observed)
        object.__setattr__(self, "predicted_world", world)
        object.__setattr__(self, "predicted_self", self_prediction)
        object.__setattr__(self, "residual", residual)
        object.__setattr__(self, "residual_force", force)
        object.__setattr__(self, "self_gate", gate)
        object.__setattr__(self, "eta", eta)
        object.__setattr__(self, "source_identity", source)
        object.__setattr__(self, "packet_identities", packets)
        object.__setattr__(self, "queued_residual_sha256", queued)
        expected = _canonical(self.canonical_payload(include_hash=False), RESIDUAL_SCHEMA)
        if self.residual_sha256 and self.residual_sha256 != expected:
            raise QiBodyError("residual return identity mismatch")
        object.__setattr__(self, "residual_sha256", expected)

    @classmethod
    def create(
        cls,
        *,
        prediction: QiBodyPrediction,
        observed: Sequence[complex] | torch.Tensor,
        port: QiLinearBoundaryPort,
        eta: float,
        source: QiSourceScope,
        packet_identities: Sequence[str] = (),
    ) -> "QiResidualReturn":
        if not isinstance(prediction, QiBodyPrediction) or not isinstance(port, QiLinearBoundaryPort) or not isinstance(source, QiSourceScope):
            raise QiBodyError("residual return requires prediction, port, and source")
        observed_tensor = torch.as_tensor(observed, dtype=torch.complex128)
        if observed_tensor.ndim != 1 or tuple(observed_tensor.shape) != (port.source_dimension,):
            raise QiBodyError("observed successor source-field shape disagrees with port")
        if len(prediction.predicted_world) != port.source_dimension:
            raise QiBodyError("prediction source-field shape disagrees with port")
        residual = observed_tensor - torch.as_tensor(prediction.predicted_world, dtype=torch.complex128)
        if prediction.self_gate:
            residual = residual - torch.as_tensor(prediction.predicted_self, dtype=torch.complex128)
        force = float(eta) * port.inject(residual)
        queued = _canonical(
            {
                "prediction_sha256": prediction.prediction_sha256,
                "effective_tick": prediction.observation_tick.payload(),
                "force": [[finite_float(value.real), finite_float(value.imag)] for value in force.detach().cpu().tolist()],
            },
            RESIDUAL_SCHEMA + ":queue",
        )
        return cls(
            prediction_sha256=prediction.prediction_sha256,
            predecessor_tick=prediction.predecessor_tick,
            observation_tick=prediction.observation_tick,
            effective_tick=prediction.observation_tick,
            body_frame_id=prediction.body_frame_id,
            observed=tuple(complex(value) for value in observed_tensor.detach().cpu().tolist()),
            predicted_world=prediction.predicted_world,
            predicted_self=prediction.predicted_self,
            self_gate=prediction.self_gate,
            residual=tuple(complex(value) for value in residual.detach().cpu().tolist()),
            residual_force=tuple(complex(value) for value in force.detach().cpu().tolist()),
            port_name=port.name,
            eta=eta,
            source_identity=_scope_identity(source),
            packet_identities=tuple(packet_identities),
            queued_residual_sha256=queued,
        )

    @classmethod
    def from_no_sample(cls, *args: Any, **kwargs: Any) -> None:
        # An absent/failed observation intentionally creates no packet.
        return None

    def eligible_for(self, predecessor_tick: QiClockTime) -> bool:
        return _tick(predecessor_tick, "predecessor_tick") == self.effective_tick

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        def complex_payload(values: Sequence[complex]) -> list[list[str]]:
            return [[finite_float(value.real), finite_float(value.imag)] for value in values]

        body: dict[str, Any] = {
            "schema": RESIDUAL_SCHEMA,
            "prediction_sha256": self.prediction_sha256,
            "predecessor_tick": self.predecessor_tick.payload(),
            "observation_tick": self.observation_tick.payload(),
            "effective_tick": self.effective_tick.payload(),
            "body_frame_id": self.body_frame_id,
            "observed": complex_payload(self.observed),
            "predicted_world": complex_payload(self.predicted_world),
            "predicted_self": complex_payload(self.predicted_self),
            "self_gate": self.self_gate,
            "residual": complex_payload(self.residual),
            "residual_force": complex_payload(self.residual_force),
            "port_name": self.port_name,
            "eta": finite_float(self.eta),
            "source_identity": self.source_identity,
            "packet_identities": list(self.packet_identities),
            "queued_residual_sha256": self.queued_residual_sha256,
            "no_sample": self.no_sample,
        }
        if include_hash:
            body["residual_sha256"] = self.residual_sha256
        return body


@dataclass(frozen=True, slots=True)
class QiResidualEfficacy:
    """Measured next-horizon residual efficacy, never a learning score."""

    control: str
    pre_error: float
    next_prediction_error: float
    admitted_work: float
    improvement: float
    improvement_per_work: float | None
    metric: tuple[float, ...]
    efficacy_sha256: str = ""

    def __post_init__(self) -> None:
        control = _text(self.control, "control")
        allowed = {"+e", "-e", "zero", "orthogonal", "phase-scrambled", "equal-work"}
        if control not in allowed:
            raise QiBodyError("unsupported residual control")
        pre = _finite(self.pre_error, "pre_error")
        next_error = _finite(self.next_prediction_error, "next_prediction_error")
        work = _finite(self.admitted_work, "admitted_work")
        if pre < 0.0 or next_error < 0.0 or work < 0.0:
            raise QiBodyError("residual efficacy metrics must be nonnegative")
        improvement = pre - next_error
        ratio = None if work == 0.0 else improvement / work
        metric = _positive_vector(self.metric, "metric")
        if self.improvement_per_work is not None and ratio is not None and abs(float(self.improvement_per_work) - ratio) > 1.0e-12:
            raise QiBodyError("improvement_per_work does not match the recorded errors/work")
        object.__setattr__(self, "control", control)
        object.__setattr__(self, "pre_error", pre)
        object.__setattr__(self, "next_prediction_error", next_error)
        object.__setattr__(self, "admitted_work", work)
        object.__setattr__(self, "improvement", improvement)
        object.__setattr__(self, "improvement_per_work", ratio)
        object.__setattr__(self, "metric", metric)
        expected = _canonical(self.canonical_payload(include_hash=False), EFFICACY_SCHEMA)
        if self.efficacy_sha256 and self.efficacy_sha256 != expected:
            raise QiBodyError("residual efficacy identity mismatch")
        object.__setattr__(self, "efficacy_sha256", expected)

    @classmethod
    def measure(
        cls,
        *,
        control: str,
        pre_error: Sequence[complex] | torch.Tensor,
        next_prediction_error: Sequence[complex] | torch.Tensor,
        admitted_work: float,
        metric: Sequence[float] | torch.Tensor,
    ) -> "QiResidualEfficacy":
        pre = _complex_vector(pre_error, "pre_error")
        post = _complex_vector(next_prediction_error, "next_prediction_error", length=len(pre))
        weights = _positive_vector(metric, "metric", length=len(pre))
        pre_norm = math.sqrt(sum(weight * (value.real * value.real + value.imag * value.imag) for weight, value in zip(weights, pre)))
        post_norm = math.sqrt(sum(weight * (value.real * value.real + value.imag * value.imag) for weight, value in zip(weights, post)))
        return cls(control, pre_norm, post_norm, admitted_work, pre_norm - post_norm, None, weights)

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": EFFICACY_SCHEMA,
            "control": self.control,
            "pre_error": finite_float(self.pre_error),
            "next_prediction_error": finite_float(self.next_prediction_error),
            "admitted_work": finite_float(self.admitted_work),
            "improvement": finite_float(self.improvement),
            "improvement_per_work": None if self.improvement_per_work is None else finite_float(self.improvement_per_work),
            "metric": _float_payload(self.metric),
        }
        if include_hash:
            body["efficacy_sha256"] = self.efficacy_sha256
        return body


def residual_control_set(residual: Sequence[complex] | torch.Tensor, *, metric: Sequence[float] | torch.Tensor) -> tuple[tuple[str, tuple[complex, ...]], ...]:
    """Return the preregistered ±e/zero/orthogonal/phase/equal-work controls."""
    vector = _complex_vector(residual, "residual")
    weights = _positive_vector(metric, "metric", length=len(vector))
    plus = vector
    minus = tuple(-value for value in vector)
    zero = tuple(0j for _ in vector)
    orthogonal = tuple((-value.imag + 1j * value.real) for value in vector)
    phase = tuple(((-1) ** index) * value for index, value in enumerate(vector))
    norm = math.sqrt(sum(weight * (value.real * value.real + value.imag * value.imag) for weight, value in zip(weights, vector)))
    orth_norm = math.sqrt(sum(weight * (value.real * value.real + value.imag * value.imag) for weight, value in zip(weights, orthogonal)))
    equal = zero if norm == 0.0 or orth_norm == 0.0 else tuple(value * norm / orth_norm for value in orthogonal)
    return (("+e", plus), ("-e", minus), ("zero", zero), ("orthogonal", orthogonal), ("phase-scrambled", phase), ("equal-work", equal))
__all__ = [
    "BODY_PROFILE_SCHEMA",
    "BODY_STATE_SCHEMA",
    "BODY_RECEIPT_SCHEMA",
    "HOMEOSTASIS_OBSERVATION_SCHEMA",
    "BODY_TRANSITION_SCHEMA",
    "ENVIRONMENT_SENSOR_FRAME_SCHEMA",
    "BODY_SENSOR_FRAME_SCHEMA",
    "BODY_FRAME_SCHEMA",
    "BODY_POSE_SCHEMA",
    "BODY_MOTION_SCHEMA",
    "BODY_REMAP_SCHEMA",
    "BODY_TRANSFORM_SCHEMA",
    "EFFERENCE_SCHEMA",
    "PREDICTION_SCHEMA",
    "RESIDUAL_SCHEMA",
    "EFFICACY_SCHEMA",
    "QiBodyError",
    "QiEnvironmentSensorFrame",
    "QiBodySensorFrame",
    "QiEnvironmentFrame",
    "QiBodyFrame",
    "QiBodyProfile",
    "QiBodyState",
    "QiBodyReceipt",
    "QiHomeostasisObservation",
    "QiBodyTransitionReceipt",
    "QiBodyPose",
    "QiBodyMotion",
    "QiBodyFrameDescriptor",
    "QiBodyRemapReceipt",
    "remap_body_field",
    "remap_body_field_round_trip",
    "QiEfferenceCopy",
    "QiBodyPrediction",
    "QiResidualReturn",
    "QiResidualEfficacy",
    "residual_control_set",
]
