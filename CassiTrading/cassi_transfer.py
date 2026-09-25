"""Matched cross-instrument transfer campaign with frozen target arms."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean
from typing import Any, Mapping, Sequence

from cassi_field_learning import NativeProgramOutcomeLearner
from cassi_learning_loop import ChronologicalLearningLoop, make_outcome
from cassi_market_contracts import Event, Prediction, digest_value
from cassi_trading_foundry import MarketBar, RefinementField
from cassi_world_model import MarketWorldModel


TRANSFER_SCHEMA = "cassi.market-transfer-matrix.v1"


class TransferError(ValueError):
    """A transfer campaign cannot satisfy its matched chronology contract."""


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TransferError(f"{name} must be nonempty text")
    return value


def _finite(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TransferError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise TransferError(f"{name} must be finite and nonnegative")
    return result


@dataclass(frozen=True, slots=True)
class TransferConfig:
    train_bars: int = 32
    horizon_bars: int = 1
    step_bars: int = 8
    source_windows: int = 4
    target_start: int = 64
    target_windows: int = 4
    target_starts: tuple[int, ...] = ()
    cost_bps: float = 15.0
    program_id: str = "synthesized-transfer-program"
    field_signature: str = "edge"
    def __post_init__(self) -> None:
        for name in (
            "train_bars",
            "horizon_bars",
            "step_bars",
            "source_windows",
            "target_start",
            "target_windows",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise TransferError(f"{name} must be a positive integer")
        if not isinstance(self.target_starts, tuple) or any(
            isinstance(start, bool) or not isinstance(start, int) or start < 1 for start in self.target_starts
        ):
            raise TransferError("target_starts must be a tuple of positive integers")
        if tuple(sorted(set(self.target_starts))) != self.target_starts:
            raise TransferError("target_starts must be strictly increasing")
        _finite("cost_bps", self.cost_bps)
        _text("program_id", self.program_id)
        _text("field_signature", self.field_signature)

    def resolved_target_starts(self) -> tuple[int, ...]:
        if self.target_starts:
            return self.target_starts
        return tuple(self.target_start + index * self.step_bars for index in range(self.target_windows))

    def required_bars(self) -> int:
        target_last = max(self.resolved_target_starts())
        return max(
            self.train_bars + (self.source_windows - 1) * self.step_bars + self.horizon_bars,
            target_last + self.train_bars + self.horizon_bars,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "train_bars": self.train_bars,
            "horizon_bars": self.horizon_bars,
            "step_bars": self.step_bars,
            "source_windows": self.source_windows,
            "target_start": self.target_start,
            "target_windows": self.target_windows,
            "target_starts": list(self.target_starts),
            "cost_bps": self.cost_bps,
            "program_id": self.program_id,
            "field_signature": self.field_signature,
        }


class CrossInstrumentTransferCampaign:
    """Train a native program identity on each source and test on frozen targets."""

    def __init__(self, config: TransferConfig | None = None) -> None:
        self.config = config or TransferConfig()

    def _events(self, bars_by_instrument: Mapping[str, Sequence[MarketBar]]) -> dict[str, tuple[Event, ...]]:
        if not bars_by_instrument:
            raise TransferError("transfer campaign requires instruments")
        events: dict[str, tuple[Event, ...]] = {}
        expected_count: int | None = None
        for instrument, bars in sorted(bars_by_instrument.items()):
            _text("instrument", instrument)
            owned = tuple(bars)
            if not owned or any(bar.symbol != instrument for bar in owned):
                raise TransferError(f"bars do not match instrument {instrument}")
            if expected_count is None:
                expected_count = len(owned)
            elif len(owned) != expected_count:
                raise TransferError("transfer instruments must have matched bar counts")
            events[instrument] = tuple(
                bar.as_event(source_id=f"transfer:{instrument}", source_revision="bars.v1")
                for bar in owned
            )
        assert expected_count is not None
        required = self.config.required_bars()
        if expected_count < required:
            raise TransferError(f"transfer needs at least {required} bars per instrument")
        return events

    def _row(
        self,
        bars: Sequence[MarketBar],
        events: Sequence[Event],
        *,
        instrument: str,
        start: int,
        arm: str,
        field: RefinementField,
        adaptive: bool,
        repeats: int = 1,
    ) -> dict[str, Any]:
        decision_index = start + self.config.train_bars - 1
        outcome_index = decision_index + self.config.horizon_bars
        history_events = events[: decision_index + 1]
        world = MarketWorldModel()
        world.update(history_events)
        context = world.observations[-1]
        field_before = field.fingerprint()
        field_prediction = field.predict_program(self.config.field_signature, self.config.program_id)
        trend = float(context.value["trend"])
        accepted = field_prediction.get("outcome") != "reject"
        direction = 0.0 if not accepted else (1.0 if trend >= 0.0 else -1.0)
        gross_return = bars[outcome_index].close / bars[decision_index].close - 1.0
        realized_return = direction * gross_return - abs(direction) * self.config.cost_bps / 10_000.0
        predicted_return = direction * max(abs(trend), 1.0e-6)
        prediction = Prediction(
            prediction_id=f"{arm}:{instrument}:{start}:prediction",
            predecessor_field_sha256=field_before,
            policy_id=f"{arm}:{instrument}:transfer-policy",
            program_id=self.config.program_id,
            input_event_ids=tuple(context.input_event_ids),
            available_at=events[decision_index].available_at,
            predicted_outcome={
                "return": predicted_return,
                "field_signature": self.config.field_signature,
                "direction": direction,
                "regime_id": world.active_regime.regime_id if world.active_regime else "regime:warming",
            },
            alternatives=({"return": 0.0},),
            cost_expectation={"bps": self.config.cost_bps},
            risk_expectation={"drawdown": max(float(context.value["volatility"]), 1.0e-4)},
        )
        learner = NativeProgramOutcomeLearner(field, repeats=repeats) if adaptive else None
        loop = ChronologicalLearningLoop(field_sha256=field_before, learner=learner)
        loop.issue_prediction(prediction)
        outcome = make_outcome(
            prediction,
            outcome_id=f"{arm}:{instrument}:{start}:outcome",
            observed_at=events[outcome_index].available_at,
            realized_outcome={"return": realized_return, "drawdown": max(0.0, -realized_return)},
            execution_trace={"arm": arm, "instrument": instrument, "direction": direction, "external_effect": "none"},
            cost_vector={"bps": abs(direction) * self.config.cost_bps},
            source_event_ids=(events[outcome_index].event_id,),
        )
        admitted = loop.settle_outcome(outcome)
        return {
            "instrument": instrument,
            "start_index": start,
            "decision_index": decision_index,
            "outcome_index": outcome_index,
            "decision_available_at": prediction.available_at,
            "outcome_observed_at": outcome.observed_at,
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
            "field_after_sha256": field.fingerprint(),
        }

    def run(
        self,
        bars_by_instrument: Mapping[str, Sequence[MarketBar]],
        *,
        events_by_instrument: Mapping[str, Sequence[Event]] | None = None,
        source_manifest: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if events_by_instrument is None:
            events_by_instrument = self._events(bars_by_instrument)
        else:
            if set(events_by_instrument) != set(bars_by_instrument):
                raise TransferError("provided events and bars cover different instruments")
            events_by_instrument = {
                instrument: tuple(events)
                for instrument, events in events_by_instrument.items()
            }
            for instrument, events in events_by_instrument.items():
                if len(events) != len(bars_by_instrument[instrument]):
                    raise TransferError(f"provided event/bar count differs for {instrument}")
            required = self.config.required_bars()
            if any(len(events) < required for events in events_by_instrument.values()):
                raise TransferError(f"transfer needs at least {required} bars per instrument")
        seed_field = RefinementField()
        seed_checkpoint = seed_field.checkpoint_bytes()
        cells: list[dict[str, Any]] = []
        train_starts = tuple(index * self.config.step_bars for index in range(self.config.source_windows))
        target_starts = self.config.resolved_target_starts()
        for source in sorted(events_by_instrument):
            source_field = RefinementField.restore(seed_checkpoint)
            source_rows = [
                self._row(
                    bars_by_instrument[source],
                    events_by_instrument[source],
                    instrument=source,
                    start=start,
                    arm=f"source:{source}",
                    field=source_field,
                    adaptive=True,
                )
                for start in train_starts
            ]
            trained_field_sha256 = source_field.fingerprint()
            for target in sorted(events_by_instrument):
                trained_rows = [
                    self._row(
                        bars_by_instrument[target],
                        events_by_instrument[target],
                        instrument=target,
                        start=start,
                        arm=f"trained:{source}->{target}",
                        field=source_field,
                        adaptive=False,
                    )
                    for start in target_starts
                ]
                baseline_field = RefinementField.restore(seed_checkpoint)
                baseline_rows = [
                    self._row(
                        bars_by_instrument[target],
                        events_by_instrument[target],
                        instrument=target,
                        start=start,
                        arm=f"baseline:{source}->{target}",
                        field=baseline_field,
                        adaptive=False,
                    )
                    for start in target_starts
                ]
                cells.append(
                    {
                        "source_instrument": source,
                        "target_instrument": target,
                        "source_training": source_rows,
                        "source_field_sha256": trained_field_sha256,
                        "trained_target": trained_rows,
                        "baseline_target": baseline_rows,
                        "trained_target_field_stable": all(
                            row["field_before_sha256"] == row["field_after_sha256"] for row in trained_rows
                        ),
                        "baseline_target_field_stable": all(
                            row["field_before_sha256"] == row["field_after_sha256"] for row in baseline_rows
                        ),
                        "trained_mean_return": mean(row["realized_return"] for row in trained_rows),
                        "baseline_mean_return": mean(row["realized_return"] for row in baseline_rows),
                    }
                )
        body: dict[str, Any] = {
            "schema": TRANSFER_SCHEMA,
            "config": self.config.as_dict(),
            "instruments": sorted(events_by_instrument),
            "event_roots": {
                instrument: digest_value([event.as_dict() for event in events])
                for instrument, events in events_by_instrument.items()
            },
            "matched_source_starts": list(train_starts),
            "matched_target_starts": list(target_starts),
            "cells": cells,
        }
        if source_manifest is not None:
            body["source_manifest"] = dict(source_manifest)
        body["content_sha256"] = digest_value(body)
        return body

    def run_dataset(self, dataset: Any) -> dict[str, Any]:
        """Run against a HistoricalDataset while preserving its source manifest."""
        return self.run(
            dataset.bars_by_instrument,
            events_by_instrument=dataset.events_by_instrument,
            source_manifest=dataset.manifest,
        )


__all__ = ["CrossInstrumentTransferCampaign", "TRANSFER_SCHEMA", "TransferConfig", "TransferError"]
