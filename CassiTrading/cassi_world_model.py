"""Chronological market regime and hypothesis world model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from cassi_market_contracts import Event, Hypothesis, Regime, canonical_bytes, digest_value
from cassi_market_coordinates import CoordinateConfig, CoordinateError, derive_market_coordinates


WORLD_MODEL_SCHEMA = "cassi.market-world-model.v1"


class WorldModelError(ValueError):
    """The world model received invalid or non-chronological evidence."""


def _finite(name: str, value: Any, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WorldModelError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise WorldModelError(f"{name} must be finite and in [{minimum}, {maximum}]")
    return result


@dataclass(frozen=True, slots=True)
class WorldModelConfig:
    coordinates: CoordinateConfig = CoordinateConfig()
    trend_threshold: float = 0.004
    momentum_threshold: float = 0.004

    def __post_init__(self) -> None:
        _finite("trend_threshold", self.trend_threshold)
        _finite("momentum_threshold", self.momentum_threshold)

    def as_dict(self) -> dict[str, Any]:
        return {
            "coordinates": self.coordinates.as_dict(),
            "trend_threshold": self.trend_threshold,
            "momentum_threshold": self.momentum_threshold,
        }

    @property
    def content_sha256(self) -> str:
        return digest_value({"schema": WORLD_MODEL_SCHEMA, "config": self.as_dict()})

def classify_coordinate_values(values: Mapping[str, Any], config: WorldModelConfig) -> str:
    if values.get("ready") != 1:
        return "warming"
    trend = float(values["trend"])
    momentum = float(values["momentum"])
    if trend >= config.trend_threshold and momentum >= config.momentum_threshold:
        return "trend-up"
    if trend <= -config.trend_threshold and momentum <= -config.momentum_threshold:
        return "trend-down"
    if abs(trend) < config.trend_threshold and abs(momentum) < config.momentum_threshold:
        return "range"
    return "transition"


class MarketWorldModel:
    """Fixed-coordinate world model with strict chronological admission.

    The model creates explicit regime and hypothesis objects, but does not claim
    that a deterministic regime label is learned truth.  Support remains tied
    to the admitted observations and can later be revised by field-owned
    prediction/outcome updates.
    """

    _REGIME_LABELS = ("warming", "trend-up", "trend-down", "range", "transition")

    def __init__(self, config: WorldModelConfig | None = None) -> None:
        self.config = config or WorldModelConfig()
        self._events: tuple[Event, ...] = ()
        self._observations: tuple[Any, ...] = ()
        self._regimes: dict[str, Regime] = {}
        self._hypotheses: dict[str, Hypothesis] = {}
        self._revision = 0
        self._last_available_at: str | None = None
        self._active_regime_id: str | None = None

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def active_regime(self) -> Regime | None:
        if self._active_regime_id is None:
            return None
        return self._regimes[self._active_regime_id]

    @property
    def events(self) -> tuple[Event, ...]:
        return self._events

    @property
    def observations(self) -> tuple[Any, ...]:
        return self._observations

    @property
    def hypotheses(self) -> tuple[Hypothesis, ...]:
        return tuple(self._hypotheses.values())

    @staticmethod
    def _label(values: Mapping[str, Any], config: WorldModelConfig) -> str:
        return classify_coordinate_values(values, config)

    def _update_regime(self, label: str, observation: Any) -> None:
        regime_id = f"regime:{label}"
        prior = self._regimes.get(regime_id)
        support = tuple(prior.supporting_observations) if prior is not None else ()
        if observation.observation_id not in support:
            support += (observation.observation_id,)
        state = dict(observation.value)
        state["observation_id"] = observation.observation_id
        competing = tuple(f"regime:{name}" for name in self._REGIME_LABELS if name != label)
        self._regimes[regime_id] = Regime(
            regime_id=regime_id,
            state_variables=state,
            applicability_guards=(f"label == {label}", "coordinate-availability-boundary"),
            supporting_observations=support,
            competing_regimes=competing,
            transition_programs=(),
            uncertainty={
                "method": "fixed-coordinate-threshold-v1",
                "trend_margin": abs(float(state["trend"])) - self.config.trend_threshold,
                "momentum_margin": abs(float(state["momentum"])) - self.config.momentum_threshold,
            },
            revision_id=f"world-revision-{self._revision}",
        )
        hypothesis_id = f"hypothesis:{regime_id}"
        prior_hypothesis = self._hypotheses.get(hypothesis_id)
        evidence = tuple(prior_hypothesis.evidence_roots) if prior_hypothesis is not None else ()
        if observation.observation_id not in evidence:
            evidence += (observation.observation_id,)
        self._hypotheses[hypothesis_id] = Hypothesis(
            hypothesis_id=hypothesis_id,
            claim=f"current coordinate state is {label}",
            target_schema={"schema": "cassi.market-regime.v1", "type": "regime"},
            expected_direction_or_outcome={"regime_id": regime_id},
            applicable_context={"subject_ids": list(self._events[-1].subject_ids)},
            assumptions=("events are ordered by available_at", "coordinates use no future events"),
            candidate_program_ids=(),
            evidence_roots=evidence,
            disconfirming_observations=(),
            status="proposed",
        )
        self._active_regime_id = regime_id

    def update(self, events: Sequence[Event]) -> dict[str, Any]:
        """Admit a strictly future batch and return a content-addressed receipt."""
        incoming = tuple(events)
        if not incoming:
            raise WorldModelError("world-model update requires at least one event")
        if self._last_available_at is not None and incoming[0].available_at <= self._last_available_at:
            raise WorldModelError("world-model update must advance available_at")
        prior_ids = {event.event_id for event in self._events}
        if any(event.event_id in prior_ids for event in incoming):
            raise WorldModelError("world-model update contains an already admitted event")
        before = self.snapshot()
        try:
            all_events = self._events + incoming
            all_observations = derive_market_coordinates(all_events, self.config.coordinates)
        except CoordinateError as exc:
            raise WorldModelError(str(exc)) from exc
        new_observations = all_observations[len(self._observations) :]
        self._events = all_events
        self._observations = all_observations
        self._revision += len(incoming)
        self._last_available_at = incoming[-1].available_at
        self._update_regime(self._label(new_observations[-1].value, self.config), new_observations[-1])
        after = self.snapshot()
        return {
            "schema": "cassi.market-world-update.v1",
            "before_revision": before["revision"],
            "after_revision": after["revision"],
            "event_ids": [event.event_id for event in incoming],
            "observation_ids": [observation.observation_id for observation in new_observations],
            "active_regime_id": self._active_regime_id,
            "before_sha256": before["content_sha256"],
            "after_sha256": after["content_sha256"],
        }

    def snapshot(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": WORLD_MODEL_SCHEMA,
            "revision": self._revision,
            "config": self.config.as_dict(),
            "last_available_at": self._last_available_at,
            "event_ids": [event.event_id for event in self._events],
            "observation_ids": [observation.observation_id for observation in self._observations],
            "active_regime_id": self._active_regime_id,
            "regimes": [regime.as_dict() for regime in self._regimes.values()],
            "hypotheses": [hypothesis.as_dict() for hypothesis in self._hypotheses.values()],
        }
        body["content_sha256"] = digest_value(body)
        return body

    def checkpoint_bytes(self) -> bytes:
        return canonical_bytes(self.snapshot())


__all__ = [
    "MarketWorldModel",
    "WORLD_MODEL_SCHEMA",
    "WorldModelConfig",
    "WorldModelError",
    "classify_coordinate_values",
]
