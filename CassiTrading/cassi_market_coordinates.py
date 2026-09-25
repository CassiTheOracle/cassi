"""Deterministic, provenance-preserving market coordinate transforms."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from cassi_market_contracts import DerivedObservation, Event, canonical_bytes, digest_value


COORDINATE_SCHEMA = "cassi.market-coordinates.v1"


class CoordinateError(ValueError):
    """Market events cannot be transformed under the coordinate contract."""


def _finite(name: str, value: Any, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CoordinateError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise CoordinateError(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise CoordinateError(f"{name} must be >= {minimum}")
    return result


def _integer(name: str, value: Any, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise CoordinateError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


@dataclass(frozen=True, slots=True)
class CoordinateConfig:
    fast_window: int = 8
    slow_window: int = 32
    momentum_window: int = 4
    volatility_window: int = 16

    def __post_init__(self) -> None:
        fast = _integer("fast_window", self.fast_window, minimum=2, maximum=512)
        slow = _integer("slow_window", self.slow_window, minimum=4, maximum=1024)
        _integer("momentum_window", self.momentum_window, minimum=1, maximum=512)
        _integer("volatility_window", self.volatility_window, minimum=2, maximum=512)
        if fast >= slow:
            raise CoordinateError("fast_window must be smaller than slow_window")

    @property
    def readiness_window(self) -> int:
        return max(self.slow_window, self.momentum_window + 1, self.volatility_window)

    def as_dict(self) -> dict[str, int]:
        return {
            "fast_window": self.fast_window,
            "slow_window": self.slow_window,
            "momentum_window": self.momentum_window,
            "volatility_window": self.volatility_window,
        }

    @property
    def content_sha256(self) -> str:
        return digest_value({"schema": COORDINATE_SCHEMA, "config": self.as_dict()})


def _close(event: Event) -> float:
    payload = event.payload
    return _finite(f"{event.event_id}.payload.close", payload.get("close"), minimum=0.0)


def _validate_events(events: Sequence[Event]) -> tuple[Event, ...]:
    if not events:
        raise CoordinateError("at least one market event is required")
    owned = tuple(events)
    seen: set[str] = set()
    subject: tuple[str, ...] | None = None
    previous_available: str | None = None
    for event in owned:
        if not isinstance(event, Event):
            raise CoordinateError("coordinate input must contain Event contracts")
        if event.event_type != "market-bar":
            raise CoordinateError("coordinate input contains a non-bar event")
        if event.event_id in seen:
            raise CoordinateError(f"duplicate event ID: {event.event_id}")
        seen.add(event.event_id)
        if subject is None:
            subject = event.subject_ids
        elif event.subject_ids != subject:
            raise CoordinateError("one coordinate sequence must contain one subject")
        if previous_available is not None and event.available_at < previous_available:
            raise CoordinateError("market events must be ordered by available_at")
        previous_available = event.available_at
        _close(event)
    return owned


def derive_market_coordinates(
    events: Sequence[Event],
    config: CoordinateConfig | None = None,
) -> tuple[DerivedObservation, ...]:
    """Derive fixed relative coordinates without reading future events."""
    owned = _validate_events(events)
    coordinate_config = config or CoordinateConfig()
    closes = [_close(event) for event in owned]
    config_digest = coordinate_config.content_sha256
    observations: list[DerivedObservation] = []
    for index, event in enumerate(owned):
        ready = int(index >= coordinate_config.readiness_window - 1)
        trend = 0.0
        momentum = 0.0
        volatility = 0.0
        if ready:
            fast_start = index - coordinate_config.fast_window + 1
            slow_start = index - coordinate_config.slow_window + 1
            fast_mean = sum(closes[fast_start : index + 1]) / coordinate_config.fast_window
            slow_mean = sum(closes[slow_start : index + 1]) / coordinate_config.slow_window
            trend = fast_mean / slow_mean - 1.0
            momentum = closes[index] / closes[index - coordinate_config.momentum_window] - 1.0
            changes = [
                closes[offset] / closes[offset - 1] - 1.0
                for offset in range(index - coordinate_config.volatility_window + 1, index + 1)
            ]
            volatility = sum(abs(value) for value in changes) / len(changes)
        return_1 = 0.0 if index == 0 else closes[index] / closes[index - 1] - 1.0
        values: dict[str, Any] = {
            "ready": ready,
            "trend": trend,
            "momentum": momentum,
            "volatility": volatility,
            "return_1": return_1,
        }
        input_start = max(
            0,
            index
            - max(
                coordinate_config.slow_window,
                coordinate_config.momentum_window + 1,
                coordinate_config.volatility_window,
            )
            + 1,
        )
        input_events = owned[input_start : index + 1]
        observation_id = f"coordinates:{event.event_id}:{config_digest}"
        observations.append(
            DerivedObservation(
                observation_id=observation_id,
                operator_id=COORDINATE_SCHEMA,
                operator_version=config_digest,
                input_event_ids=tuple(row.event_id for row in input_events),
                input_digests=tuple(row.content_sha256 for row in input_events),
                parameters=coordinate_config.as_dict(),
                output_schema={
                    "schema": "cassi.market-coordinate-values.v1",
                    "fields": {
                        "ready": "integer",
                        "trend": "relative-number",
                        "momentum": "relative-number",
                        "volatility": "relative-number",
                        "return_1": "relative-number",
                    },
                },
                value=values,
                units={
                    "ready": "boolean-integer",
                    "trend": "fraction",
                    "momentum": "fraction",
                    "volatility": "fraction",
                    "return_1": "fraction",
                },
                valid_from=event.observed_at,
            )
        )
    canonical_bytes([observation.as_dict() for observation in observations])
    return tuple(observations)


__all__ = [
    "COORDINATE_SCHEMA",
    "CoordinateConfig",
    "CoordinateError",
    "derive_market_coordinates",
]
