"""Chronological adaptive-vs-frozen campaign runner."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from cassi_field_learning import NativeProgramOutcomeLearner
from cassi_learning_loop import ChronologicalLearningLoop, make_outcome
from cassi_market_contracts import Event, Prediction, digest_value
from cassi_trading_foundry import MarketBar, RefinementField
from cassi_world_model import MarketWorldModel


CAMPAIGN_SCHEMA = "cassi.market-rolling-campaign.v1"


class CampaignError(ValueError):
    """A rolling campaign cannot satisfy its chronological contract."""


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CampaignError(f"{name} must be nonempty text")
    return value


def _finite(name: str, value: Any, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CampaignError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise CampaignError(f"{name} must be finite and >= {minimum}")
    return result


@dataclass(frozen=True, slots=True)
class RollingCampaignConfig:
    train_bars: int = 32
    horizon_bars: int = 1
    step_bars: int = 4
    max_windows: int = 8
    cost_bps: float = 15.0
    program_id: str = "synthesized-native-program"
    field_signature: str = "edge"

    def __post_init__(self) -> None:
        for name in ("train_bars", "horizon_bars", "step_bars", "max_windows"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise CampaignError(f"{name} must be a positive integer")
        _finite("cost_bps", self.cost_bps)
        _text("program_id", self.program_id)
        _text("field_signature", self.field_signature)

    def as_dict(self) -> dict[str, Any]:
        return {
            "train_bars": self.train_bars,
            "horizon_bars": self.horizon_bars,
            "step_bars": self.step_bars,
            "max_windows": self.max_windows,
            "cost_bps": self.cost_bps,
            "program_id": self.program_id,
            "field_signature": self.field_signature,
        }


class RollingCampaign:
    """Run identical chronological windows with adaptive and frozen field arms."""

    def __init__(self, config: RollingCampaignConfig | None = None) -> None:
        self.config = config or RollingCampaignConfig()

    @staticmethod
    def _events(bars: Sequence[MarketBar]) -> tuple[Event, ...]:
        if not bars:
            raise CampaignError("campaign requires market bars")
        symbol = bars[0].symbol
        if any(bar.symbol != symbol for bar in bars):
            raise CampaignError("campaign requires one instrument")
        return tuple(
            bar.as_event(source_id=f"campaign:{symbol}", source_revision="bars.v1")
            for bar in bars
        )

    def _window_starts(self, count: int) -> tuple[int, ...]:
        last_start = count - self.config.train_bars - self.config.horizon_bars
        if last_start < 0:
            raise CampaignError("campaign does not contain a complete train/outcome window")
        return tuple(range(0, last_start + 1, self.config.step_bars))[: self.config.max_windows]

    def _run_arm(self, bars: Sequence[MarketBar], events: Sequence[Event], *, arm: str, field: RefinementField) -> dict[str, Any]:
        adaptive = arm == "adaptive"
        windows: list[dict[str, Any]] = []
        initial_field_sha256 = field.fingerprint()
        starts = self._window_starts(len(bars))
        for window_index, start in enumerate(starts):
            decision_index = start + self.config.train_bars - 1
            outcome_index = decision_index + self.config.horizon_bars
            history_events = events[: decision_index + 1]
            world = MarketWorldModel()
            world.update(history_events)
            context = world.observations[-1]
            field_before = field.fingerprint()
            field_prediction = field.predict_program(self.config.field_signature, self.config.program_id)
            values = context.value
            trend = float(values["trend"])
            accepted = field_prediction.get("outcome") != "reject"
            direction = 0.0 if not accepted else (1.0 if trend >= 0.0 else -1.0)
            current_close = float(bars[decision_index].close)
            future_close = float(bars[outcome_index].close)
            gross_return = future_close / current_close - 1.0
            realized_return = direction * gross_return - abs(direction) * self.config.cost_bps / 10_000.0
            predicted_return = direction * max(abs(trend), 1.0e-6)
            prediction = Prediction(
                prediction_id=f"{arm}-prediction-{window_index}",
                predecessor_field_sha256=field_before,
                policy_id=f"{arm}-rolling-policy",
                program_id=self.config.program_id,
                input_event_ids=tuple(context.input_event_ids),
                available_at=events[decision_index].available_at,
                predicted_outcome={
                    "return": predicted_return,
                    "field_signature": self.config.field_signature,
                    "direction": direction,
                    "regime_id": f"regime:{world.active_regime.regime_id.split(':', 1)[-1] if world.active_regime else 'warming'}",
                },
                alternatives=({"return": 0.0},),
                cost_expectation={"bps": self.config.cost_bps},
                risk_expectation={"drawdown": max(float(values["volatility"]), 1.0e-4)},
            )
            learner = NativeProgramOutcomeLearner(field, repeats=1) if adaptive else None
            loop = ChronologicalLearningLoop(field_sha256=field_before, learner=learner)
            loop.issue_prediction(prediction)
            outcome = make_outcome(
                prediction,
                outcome_id=f"{arm}-outcome-{window_index}",
                observed_at=events[outcome_index].available_at,
                realized_outcome={"return": realized_return, "drawdown": max(0.0, -realized_return)},
                execution_trace={"arm": arm, "direction": direction, "external_effect": "none"},
                cost_vector={"bps": abs(direction) * self.config.cost_bps},
                source_event_ids=(events[outcome_index].event_id,),
            )
            admitted = loop.settle_outcome(outcome)
            field_after = field.fingerprint()
            windows.append(
                {
                    "window_index": window_index,
                    "start_index": start,
                    "decision_index": decision_index,
                    "outcome_index": outcome_index,
                    "decision_available_at": prediction.available_at,
                    "outcome_observed_at": outcome.observed_at,
                    "input_event_ids": list(context.input_event_ids),
                    "decision_event_id": events[decision_index].event_id,
                    "outcome_event_id": events[outcome_index].event_id,
                    "prediction_input_event_ids": list(prediction.input_event_ids),
                    "field_prediction": field_prediction,
                    "regime_id": prediction.predicted_outcome["regime_id"],
                    "direction": direction,
                    "predicted_return": predicted_return,
                    "realized_return": realized_return,
                    "admitted": admitted,
                    "field_before_sha256": field_before,
                    "field_after_sha256": field_after,
                }
            )
        return {
            "arm": arm,
            "adaptive": adaptive,
            "initial_field_sha256": initial_field_sha256,
            "final_field_sha256": field.fingerprint(),
            "field_changed": initial_field_sha256 != field.fingerprint(),
            "windows": windows,
            "window_count": len(windows),
        }

    def run(self, bars: Sequence[MarketBar]) -> dict[str, Any]:
        events = self._events(bars)
        seed_field = RefinementField()
        seed_checkpoint = seed_field.checkpoint_bytes()
        adaptive_field = RefinementField.restore(seed_checkpoint)
        frozen_field = RefinementField.restore(seed_checkpoint)
        adaptive = self._run_arm(bars, events, arm="adaptive", field=adaptive_field)
        frozen = self._run_arm(bars, events, arm="frozen", field=frozen_field)
        body: dict[str, Any] = {
            "schema": CAMPAIGN_SCHEMA,
            "config": self.config.as_dict(),
            "event_count": len(events),
            "event_root_sha256": digest_value([event.as_dict() for event in events]),
            "seed_field_sha256": seed_field.fingerprint(),
            "adaptive": adaptive,
            "frozen": frozen,
            "matched_window_starts": [row["start_index"] for row in adaptive["windows"]],
        }
        body["content_sha256"] = digest_value(body)
        return body


__all__ = ["CAMPAIGN_SCHEMA", "CampaignError", "RollingCampaign", "RollingCampaignConfig"]
