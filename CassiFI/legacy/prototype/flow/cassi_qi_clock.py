"""Exact rational causal clock and source-frontier primitives for CassiFI."""

from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering
from math import gcd, isfinite, lcm
from typing import Any, Iterable, Mapping

from cassi_qi_bootstrap import canonical_hash


CLOCK_TIME_SCHEMA = "cassi.qi-flow-clock-time.v1"
CLOCK_SCHEMA = "cassi.qi-flow-clock.v1"
WATERMARK_SCHEMA = "cassi.qi-flow-watermark.v1"
ANTIALIAS_SCHEMA = "cassi.qi-flow-antialias.v1"


class QiClockError(ValueError):
    """Raised when exact causal-clock data is invalid or undecidable."""


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise QiClockError(f"{name} must be an integer >= {minimum}")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise QiClockError(f"{name} must be a nonempty string")
    return value


def _sha256(value: Any, name: str) -> str:
    value = _text(value, name)
    if len(value) != 64 or value.lower() != value or any(ch not in "0123456789abcdef" for ch in value):
        raise QiClockError(f"{name} must be a lowercase SHA-256 digest")
    return value


@total_ordering
@dataclass(frozen=True, slots=True)
class QiClockTime:
    """A nonnegative reduced rational multiple of the profile base unit."""

    n: int
    d: int

    def __post_init__(self) -> None:
        _integer(self.n, "n")
        _integer(self.d, "d", minimum=1)
        if gcd(self.n, self.d) != 1:
            raise QiClockError("clock time must be in lowest terms")

    @classmethod
    def make(cls, n: int, d: int = 1) -> "QiClockTime":
        _integer(n, "n")
        _integer(d, "d", minimum=1)
        divisor = gcd(n, d)
        return cls(n // divisor, d // divisor)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "QiClockTime":
        if not isinstance(payload, Mapping) or set(payload) != {"schema", "n", "d"}:
            raise QiClockError("clock-time payload fields do not match the schema")
        if payload["schema"] != CLOCK_TIME_SCHEMA:
            raise QiClockError("clock-time schema mismatch")
        return cls(payload["n"], payload["d"])

    @property
    def positive(self) -> bool:
        return self.n > 0

    def payload(self) -> dict[str, Any]:
        return {"schema": CLOCK_TIME_SCHEMA, "n": self.n, "d": self.d}

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, QiClockTime):
            return NotImplemented
        return self.n * other.d < other.n * self.d

    def __add__(self, other: "QiClockTime") -> "QiClockTime":
        if not isinstance(other, QiClockTime):
            return NotImplemented
        return QiClockTime.make(self.n * other.d + other.n * self.d, self.d * other.d)

    def __sub__(self, other: "QiClockTime") -> "QiClockTime":
        if not isinstance(other, QiClockTime):
            return NotImplemented
        numerator = self.n * other.d - other.n * self.d
        if numerator < 0:
            raise QiClockError("causal clock time cannot become negative")
        return QiClockTime.make(numerator, self.d * other.d)

    def scale(self, factor: int) -> "QiClockTime":
        return QiClockTime.make(self.n * _integer(factor, "factor"), self.d)


@dataclass(frozen=True, slots=True)
class QiSourceScope:
    source_epoch: str
    source_stream_id: str
    descriptor_sha256: str

    def __post_init__(self) -> None:
        _text(self.source_epoch, "source_epoch")
        _text(self.source_stream_id, "source_stream_id")
        _sha256(self.descriptor_sha256, "descriptor_sha256")
        if "\x1f" in self.source_epoch or "\x1f" in self.source_stream_id:
            raise QiClockError("source scope text contains the reserved separator")

    def key(self) -> str:
        return f"{self.source_epoch}\x1f{self.source_stream_id}\x1f{self.descriptor_sha256}"

    def payload(self) -> dict[str, str]:
        return {
            "source_epoch": self.source_epoch,
            "source_stream_id": self.source_stream_id,
            "descriptor_sha256": self.descriptor_sha256,
        }


@dataclass(frozen=True, slots=True)
class QiSourceCadence:
    scope: QiSourceScope
    interval: QiClockTime
    phase: QiClockTime
    descriptor_priority: int
    first_sequence: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.scope, QiSourceScope):
            raise QiClockError("source cadence requires a source scope")
        if not isinstance(self.interval, QiClockTime) or not self.interval.positive:
            raise QiClockError("source interval must be positive")
        if not isinstance(self.phase, QiClockTime) or self.phase >= self.interval:
            raise QiClockError("source phase must satisfy 0 <= phase < interval")
        _integer(self.descriptor_priority, "descriptor_priority")
        _integer(self.first_sequence, "first_sequence")

    def payload(self) -> dict[str, Any]:
        return {
            "scope": self.scope.payload(),
            "interval": self.interval.payload(),
            "phase": self.phase.payload(),
            "descriptor_priority": self.descriptor_priority,
            "first_sequence": self.first_sequence,
        }


@dataclass(frozen=True, slots=True)
class QiCausalClock:
    """One immutable LCM-bounded exact schedule."""

    tau_0: QiClockTime
    field_interval: QiClockTime
    field_steps_per_world_tick: int
    sources: tuple[QiSourceCadence, ...]
    max_clock_lcm: int
    lcm_denominator: int
    ticks_per_field_step: int
    ticks_per_world_tick: int
    ticks_per_source_interval: tuple[tuple[str, int], ...]
    schedule_sha256: str

    @classmethod
    def create(
        cls,
        *,
        tau_0: QiClockTime,
        field_interval: QiClockTime,
        field_steps_per_world_tick: int,
        sources: Iterable[QiSourceCadence],
        max_clock_lcm: int,
    ) -> "QiCausalClock":
        if not isinstance(tau_0, QiClockTime) or not tau_0.positive:
            raise QiClockError("tau_0 must be positive")
        if not isinstance(field_interval, QiClockTime) or not field_interval.positive:
            raise QiClockError("field interval must be positive")
        world_steps = _integer(field_steps_per_world_tick, "field_steps_per_world_tick", minimum=1)
        maximum = _integer(max_clock_lcm, "max_clock_lcm", minimum=1)
        try:
            candidates = tuple(sources)
        except TypeError as exc:
            raise QiClockError("sources must be iterable") from exc
        if not all(isinstance(item, QiSourceCadence) for item in candidates):
            raise QiClockError("sources must contain only QiSourceCadence values")
        ordered = tuple(sorted(candidates, key=lambda item: item.scope.key()))
        scope_keys = [item.scope.key() for item in ordered]
        if len(set(scope_keys)) != len(scope_keys):
            raise QiClockError("source scopes must be unique")
        denominator_lcm = field_interval.d
        for source in ordered:
            denominator_lcm = lcm(denominator_lcm, source.interval.d)
        if denominator_lcm > maximum:
            raise QiClockError("clock denominator LCM exceeds max_clock_lcm")
        field_ticks = field_interval.n * (denominator_lcm // field_interval.d)
        source_ticks: list[tuple[str, int]] = []
        for source in ordered:
            phase_ticks_numerator = source.phase.n * denominator_lcm
            if phase_ticks_numerator % source.phase.d:
                raise QiClockError("source phase is not aligned to the common exact tick")
            source_ticks.append(
                (source.scope.key(), source.interval.n * (denominator_lcm // source.interval.d))
            )
        provisional = {
            "schema": CLOCK_SCHEMA,
            "tau_0": tau_0.payload(),
            "epoch": QiClockTime(0, 1).payload(),
            "field_interval": field_interval.payload(),
            "field_steps_per_world_tick": world_steps,
            "sources": [item.payload() for item in ordered],
            "max_clock_lcm": maximum,
            "lcm_denominator": denominator_lcm,
            "delta_t": QiClockTime.make(1, denominator_lcm).payload(),
            "ticks_per_field_step": field_ticks,
            "ticks_per_world_tick": world_steps * field_ticks,
            "ticks_per_source_interval": dict(source_ticks),
        }
        schedule_sha256 = canonical_hash(provisional, CLOCK_SCHEMA)
        return cls(
            tau_0=tau_0,
            field_interval=field_interval,
            field_steps_per_world_tick=world_steps,
            sources=ordered,
            max_clock_lcm=maximum,
            lcm_denominator=denominator_lcm,
            ticks_per_field_step=field_ticks,
            ticks_per_world_tick=world_steps * field_ticks,
            ticks_per_source_interval=tuple(source_ticks),
            schedule_sha256=schedule_sha256,
        )

    @property
    def delta_t(self) -> QiClockTime:
        return QiClockTime.make(1, self.lcm_denominator)

    def tick_at(self, time: QiClockTime) -> int:
        if not isinstance(time, QiClockTime):
            raise QiClockError("logical time must be QiClockTime")
        numerator = time.n * self.lcm_denominator
        if numerator % time.d:
            raise QiClockError("logical time is not aligned to the common exact tick")
        return numerator // time.d

    def time_at_tick(self, tick: int) -> QiClockTime:
        return QiClockTime.make(_integer(tick, "tick"), self.lcm_denominator)

    def payload(self) -> dict[str, Any]:
        payload = {
            "schema": CLOCK_SCHEMA,
            "tau_0": self.tau_0.payload(),
            "epoch": QiClockTime(0, 1).payload(),
            "field_interval": self.field_interval.payload(),
            "field_steps_per_world_tick": self.field_steps_per_world_tick,
            "sources": [item.payload() for item in self.sources],
            "max_clock_lcm": self.max_clock_lcm,
            "lcm_denominator": self.lcm_denominator,
            "delta_t": self.delta_t.payload(),
            "ticks_per_field_step": self.ticks_per_field_step,
            "ticks_per_world_tick": self.ticks_per_world_tick,
            "ticks_per_source_interval": dict(self.ticks_per_source_interval),
        }
        if canonical_hash(payload, CLOCK_SCHEMA) != self.schedule_sha256:
            raise QiClockError("clock schedule identity mismatch")
        return {**payload, "schedule_sha256": self.schedule_sha256}
    def source_cadence(self, scope: QiSourceScope) -> QiSourceCadence:
        if not isinstance(scope, QiSourceScope):
            raise QiClockError("source scope is invalid")
        key = scope.key()
        for source in self.sources:
            if source.scope.key() == key:
                return source
        raise QiClockError("source scope is not registered with this clock")

    def expected_capture(
        self,
        scope: QiSourceScope,
        source_sequence: int,
    ) -> tuple[QiClockTime, QiClockTime]:
        source = self.source_cadence(scope)
        sequence = _integer(source_sequence, "source_sequence")
        offset = sequence - source.first_sequence
        if offset < 0:
            raise QiClockError("source sequence precedes the registered first sequence")
        start = source.phase + source.interval.scale(offset)
        return start, start + source.interval
    def validate_capture(
        self,
        *,
        scope: QiSourceScope,
        source_sequence: int,
        capture_start: QiClockTime,
        capture_end: QiClockTime,
        cycle_frontier: QiClockTime,
    ) -> None:
        if not isinstance(capture_start, QiClockTime) or not isinstance(capture_end, QiClockTime):
            raise QiClockError("capture bounds must be exact clock times")
        if not isinstance(cycle_frontier, QiClockTime):
            raise QiClockError("cycle frontier must be an exact clock time")
        if not capture_start < capture_end:
            raise QiClockError("capture interval must be nonempty and half-open")
        self.tick_at(cycle_frontier)
        expected_start, expected_end = self.expected_capture(scope, source_sequence)
        if capture_start != expected_start or capture_end != expected_end:
            raise QiClockError("capture interval does not match the registered source cadence")
        if capture_end > cycle_frontier:
            raise QiClockError("future capture interval is not admissible")


    @staticmethod
    def admission_key(
        *,
        capture_end: QiClockTime,
        capture_start: QiClockTime,
        descriptor_priority: int,
        scope: QiSourceScope,
        source_sequence: int,
        packet_sha256: str,
    ) -> tuple[Any, ...]:
        if not isinstance(capture_start, QiClockTime) or not isinstance(capture_end, QiClockTime):
            raise QiClockError("capture bounds must be exact clock times")
        if not isinstance(scope, QiSourceScope):
            raise QiClockError("admission scope is invalid")
        if not capture_start < capture_end:
            raise QiClockError("capture interval must be nonempty and half-open")
        return (
            capture_end,
            capture_start,
            _integer(descriptor_priority, "descriptor_priority"),
            scope.source_epoch,
            scope.source_stream_id,
            _integer(source_sequence, "source_sequence"),
            _sha256(packet_sha256, "packet_sha256"),
        )


@dataclass(frozen=True, slots=True)
class QiWatermarkFrontier:
    capture_end: QiClockTime
    source_sequence: int
    frame_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.capture_end, QiClockTime):
            raise QiClockError("watermark capture_end must be QiClockTime")
        _integer(self.source_sequence, "source_sequence")
        _sha256(self.frame_sha256, "frame_sha256")

    def payload(self) -> dict[str, Any]:
        return {
            "capture_end": self.capture_end.payload(),
            "source_sequence": self.source_sequence,
            "frame_sha256": self.frame_sha256,
        }


@dataclass(frozen=True, slots=True)
class QiWatermark:
    """Greatest contiguous committed frontier for every registered source scope."""

    frontiers: tuple[tuple[QiSourceScope, QiWatermarkFrontier], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.frontiers, tuple):
            raise QiClockError("watermark frontiers must be an immutable tuple")
        keys: list[str] = []
        for item in self.frontiers:
            if not isinstance(item, tuple) or len(item) != 2:
                raise QiClockError("watermark frontier rows must be scope/frontier pairs")
            scope, frontier = item
            if not isinstance(scope, QiSourceScope) or not isinstance(frontier, QiWatermarkFrontier):
                raise QiClockError("watermark frontier row has an invalid type")
            keys.append(scope.key())
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise QiClockError("watermark frontiers must be unique and canonically ordered")

    def frontier(self, scope: QiSourceScope) -> QiWatermarkFrontier | None:
        if not isinstance(scope, QiSourceScope):
            raise QiClockError("watermark scope is invalid")
        key = scope.key()
        return next((frontier for item, frontier in self.frontiers if item.key() == key), None)

    def advance(
        self,
        *,
        scope: QiSourceScope,
        capture_start: QiClockTime,
        capture_end: QiClockTime,
        source_sequence: int,
        frame_sha256: str,
        first_sequence: int,
        first_capture_start: QiClockTime,
        cycle_frontier: QiClockTime,
        indexed_in_commit_a: bool,
    ) -> "QiWatermark":
        if not indexed_in_commit_a:
            raise QiClockError("Commit A cannot advance an unindexed frame")
        if not isinstance(scope, QiSourceScope):
            raise QiClockError("watermark scope is invalid")
        if not isinstance(capture_start, QiClockTime) or not isinstance(capture_end, QiClockTime):
            raise QiClockError("capture bounds must be exact clock times")
        if not isinstance(first_capture_start, QiClockTime) or not isinstance(cycle_frontier, QiClockTime):
            raise QiClockError("watermark frontier bounds must be exact clock times")
        if not capture_start < capture_end:
            raise QiClockError("capture interval must be nonempty and half-open")
        if capture_end > cycle_frontier:
            raise QiClockError("future capture interval cannot advance the watermark")
        sequence = _integer(source_sequence, "source_sequence")
        first = _integer(first_sequence, "first_sequence")
        digest = _sha256(frame_sha256, "frame_sha256")
        previous = self.frontier(scope)
        if previous is None:
            if sequence != first or capture_start != first_capture_start:
                raise QiClockError("first source frame does not match the registered frontier")
        elif sequence == previous.source_sequence:
            if capture_end == previous.capture_end and digest == previous.frame_sha256:
                return self
            raise QiClockError("conflicting duplicate source frame")
        elif sequence != previous.source_sequence + 1 or capture_start != previous.capture_end:
            raise QiClockError("source sequence or interval gap")
        replacement = QiWatermarkFrontier(capture_end, sequence, digest)
        rows = [(item, frontier) for item, frontier in self.frontiers if item.key() != scope.key()]
        rows.append((scope, replacement))
        rows.sort(key=lambda item: item[0].key())
        return QiWatermark(tuple(rows))

    def payload(self) -> dict[str, Any]:
        core = {
            "schema": WATERMARK_SCHEMA,
            "frontiers": [
                {"scope": scope.payload(), "frontier": frontier.payload()}
                for scope, frontier in self.frontiers
            ],
        }
        return {**core, "self_sha256": canonical_hash(core, WATERMARK_SCHEMA)}


@dataclass(frozen=True, slots=True)
class QiAntialiasProfile:
    """Immutable declared resampling operator identity; application lives at the boundary."""

    profile_id: str
    coefficients: tuple[float, ...]
    phase: QiClockTime
    support_start: int
    support_end: int
    boundary_convention: str
    passband_tolerance: float
    stopband_tolerance: float

    def __post_init__(self) -> None:
        _text(self.profile_id, "profile_id")
        if not self.coefficients or not all(
            isinstance(value, float) and isfinite(value) for value in self.coefficients
        ):
            raise QiClockError("antialias coefficients must be nonempty finite float64 values")
        if not isinstance(self.phase, QiClockTime):
            raise QiClockError("antialias phase must be exact")
        start = _integer(self.support_start, "support_start")
        end = _integer(self.support_end, "support_end")
        if end < start or end - start + 1 != len(self.coefficients):
            raise QiClockError("antialias support and coefficient count disagree")
        if self.boundary_convention not in {"periodic", "finite-zero", "finite-reflect"}:
            raise QiClockError("unregistered antialias boundary convention")
        for name, value in (
            ("passband_tolerance", self.passband_tolerance),
            ("stopband_tolerance", self.stopband_tolerance),
        ):
            if not isinstance(value, float) or not isfinite(value) or value < 0.0:
                raise QiClockError(f"{name} must be finite and nonnegative")

    def payload(self) -> dict[str, Any]:
        operator = {
            "profile_id": self.profile_id,
            "coefficients": list(self.coefficients),
            "adjoint_coefficients": list(reversed(self.coefficients)),
            "phase": self.phase.payload(),
            "support": [self.support_start, self.support_end],
            "boundary_convention": self.boundary_convention,
            "passband_tolerance": self.passband_tolerance,
            "stopband_tolerance": self.stopband_tolerance,
        }
        response_sha256 = canonical_hash(operator, "cassi.qi-flow-antialias-response.v1")
        core = {"schema": ANTIALIAS_SCHEMA, **operator, "response_sha256": response_sha256}
        return {**core, "self_sha256": canonical_hash(core, ANTIALIAS_SCHEMA)}
