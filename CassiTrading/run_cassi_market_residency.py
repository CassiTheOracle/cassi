#!/usr/bin/env python3
"""Run Cassi's long-horizon field-owned market residency benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_trading_foundry import (
    FINANCIAL_COMPOSITIONS,
    MarketBar,
    ReplayConfig,
    RefinementField,
    StrategyProgram,
    _FIELD_MUTATION_CODES,
    _failure_signature,
    _features,
    _child_program,
    _max_drawdown,
    _objective,
    _validate_bars,
    digest_value,
    learn_financial_composition,
    load_bars_csv,
    select_financial_composition,
    teach_financial_math,
)
from cassi_raw_event_field import AcquisitionProfile, CapacityError
from run_cassi_trading_benchmark import _bar_series
from run_cassi_trading_realtime import _stream_metrics, _target_position


RESIDENCY_SCHEMA = "cassi.trading-market-residency.v1"
ARM_SCHEMA = "cassi.trading-residency-arm.v1"
RESIDENCY_SCENARIO_ID = "MR-1-field-residency"
RESIDENCY_DESCRIPTION = (
    "long-horizon causal market residency with an online field, account, "
    "financial program, and frozen-transfer control"
)
MUTATIONS = tuple(_FIELD_MUTATION_CODES)
CAMPAIGN_SCHEMA = "cassi.trading-market-residency-campaign.v1"
CAMPAIGN_SCENARIO_ID = "MR-2-chronological-residency"
CAMPAIGN_DESCRIPTION = (
    "chronological closed-bar residency comparing carried-field learning, "
    "frozen transfer, fresh-field learning, and a static control"
)


@dataclass(frozen=True, slots=True)
class ResidencyConfig:
    calibration_bars: int = 768
    external_bars: int = 1536
    warmup_bars: int = 48
    review_interval: int = 24
    minimum_live_steps: int = 8
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    initial_equity: float = 1.0
    max_position: float = 1.0
    timeframe_hours: float = 1.0
    field_component_limit: float = 4.0
    field_wave_width: int = 512

    def __post_init__(self) -> None:
        if self.calibration_bars < 96 or self.external_bars < 96:
            raise ValueError("residency streams require at least 96 bars")
        if self.warmup_bars < 8 or self.warmup_bars >= min(self.calibration_bars, self.external_bars) - 2:
            raise ValueError("warmup_bars leaves no live residency interval")
        if self.review_interval < 4:
            raise ValueError("review_interval must be at least four bars")
        if self.minimum_live_steps < 1:
            raise ValueError("minimum_live_steps must be positive")
        for name, value in (
            ("fee_bps", self.fee_bps),
            ("slippage_bps", self.slippage_bps),
            ("initial_equity", self.initial_equity),
            ("max_position", self.max_position),
            ("timeframe_hours", self.timeframe_hours),
            ("field_component_limit", self.field_component_limit),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.initial_equity <= 0.0 or self.timeframe_hours <= 0.0:
            raise ValueError("initial_equity and timeframe_hours must be positive")
        if self.field_component_limit <= 0.0:
            raise ValueError("field_component_limit must be positive")
        if self.field_component_limit > 4.0:
            raise ValueError("field_component_limit cannot exceed four")
        if (
            isinstance(self.field_wave_width, bool)
            or not isinstance(self.field_wave_width, int)
            or self.field_wave_width < 16
            or self.field_wave_width > 4096
            or self.field_wave_width % 2
        ):
            raise ValueError("field_wave_width must be an even integer in [16, 4096]")
        if self.max_position > 1.0:
            raise ValueError("max_position cannot exceed one")

    @property
    def replay(self) -> ReplayConfig:
        return ReplayConfig(
            fee_bps=self.fee_bps,
            slippage_bps=self.slippage_bps,
            initial_equity=self.initial_equity,
            max_position=self.max_position,
            timeframe_hours=self.timeframe_hours,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "calibration_bars": self.calibration_bars,
            "external_bars": self.external_bars,
            "warmup_bars": self.warmup_bars,
            "review_interval": self.review_interval,
            "minimum_live_steps": self.minimum_live_steps,
            "fee_bps": self.fee_bps,
            "slippage_bps": self.slippage_bps,
            "initial_equity": self.initial_equity,
            "max_position": self.max_position,
            "timeframe_hours": self.timeframe_hours,
            "field_component_limit": self.field_component_limit,
            "field_wave_width": self.field_wave_width,
        }


def _bounded_write(field: RefinementField, writer: Any) -> dict[str, Any]:
    try:
        result = dict(writer())
        summary = result.get("write_summary")
        if isinstance(summary, Mapping):
            field._residency_consolidation_steps = (
                int(getattr(field, "_residency_consolidation_steps", 0))
                + int(summary.get("consolidation_steps", 0))
            )
            field._residency_consolidation_events = (
                int(getattr(field, "_residency_consolidation_events", 0))
                + len(summary.get("consolidations", ()))
            )
        return result
    except CapacityError as exc:
        events = int(getattr(field, "_residency_capacity_events", 0)) + 1
        setattr(field, "_residency_capacity_events", events)
        return {
            "admission": "capacity-saturated",
            "promoted": False,
            "reason": "field-component-bound",
            "capacity_event_index": events,
            "recoverable": True,
            "error": str(exc),
        }


def _events(bars: Sequence[MarketBar], source_id: str) -> tuple[dict[str, Any], ...]:
    return tuple(
        bar.as_event(source_id=source_id, source_revision="market-residency.v1").as_dict()
        for bar in bars
    )


def _field_info(
    field: RefinementField | None,
    *,
    before: str | None = None,
    before_checkpoint_sha256: str | None = None,
) -> dict[str, Any]:
    if field is None:
        return {"mode": "none", "before_sha256": None, "after_sha256": None}
    checkpoint = field.checkpoint_bytes()
    profile = field.learner.profile
    return {
        "mode": "field-owned",
        "before_sha256": before,
        "before_checkpoint_sha256": before_checkpoint_sha256,
        "after_sha256": field.fingerprint(),
        "wave_width": profile.wave_width,
        "component_limit": profile.component_limit,
        "energy_limit": profile.energy_limit,
        "checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
        "checkpoint_bytes": len(checkpoint),
        "checkpoint_hex": checkpoint.hex(),
        "learning_saturated": bool(getattr(field, "_residency_learning_saturated", False)),
        "capacity_events": int(getattr(field, "_residency_capacity_events", 0)),
        "consolidation_events": int(getattr(field, "_residency_consolidation_events", 0)),
        "consolidation_steps": int(getattr(field, "_residency_consolidation_steps", 0)),
    }


def _review_outcome(metrics: Mapping[str, float], minimum_live_steps: int) -> str:
    if metrics["active_steps"] < minimum_live_steps:
        return "uncertain"
    return "promote" if metrics["objective"] > 0.0 else "reject"


def run_online_arm(
    bars: Sequence[MarketBar],
    *,
    config: ResidencyConfig,
    arm_name: str,
    seed_program: StrategyProgram | None = None,
    field_memory: RefinementField | None = None,
    learning_enabled: bool,
    teach_field: bool,
    initial_composition_id: str = "balanced",
) -> dict[str, Any]:
    """Trade one stream causally and learn only from realized decisions."""

    owned = _validate_bars(tuple(bars))
    if len(owned) < config.warmup_bars + 2:
        raise ValueError("residency arm is shorter than its warmup interval")
    replay = config.replay
    field = field_memory or (
        RefinementField(
            profile=AcquisitionProfile(
                component_limit=config.field_component_limit,
                wave_width=config.field_wave_width,
            )
        )
        if learning_enabled or teach_field
        else None
    )
    field_before = field.fingerprint() if field is not None else None
    field_before_checkpoint_sha256 = (
        hashlib.sha256(field.checkpoint_bytes()).hexdigest() if field is not None else None
    )
    if field is not None and teach_field:
        financial_teaching = teach_financial_math(field)
    elif field is not None:
        financial_teaching = {
            "admission": "inherited",
            "algorithm_count": 13,
            "content_sha256": None,
        }
    else:
        financial_teaching = {"admission": "not-applicable", "algorithm_count": 0}

    program = seed_program or StrategyProgram.seed()
    initial_strategy = program.document()
    composition_id = initial_composition_id
    position = 0.0
    entry_price: float | None = None
    bars_in_position = 0
    equity = replay.initial_equity
    equity_curve = [equity]
    realized_returns: list[float] = []
    turnover = 0.0
    cost_paid = 0.0
    trade_count = 0
    active_steps = 0
    winning_steps = 0
    buy_hold_equity = 1.0
    decisions: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    live_start_index = config.warmup_bars - 1
    review_return_start = 0
    review_equity_start = live_start_index
    review_index = 0
    active_mutation: str | None = None

    def perform_review(cutoff_index: int, *, terminal: bool) -> None:
        nonlocal program, composition_id, review_return_start, review_equity_start, review_index, active_mutation
        interval_returns = realized_returns[review_return_start:]
        interval_curve = equity_curve[review_equity_start:]
        interval_initial = interval_curve[0] if interval_curve else equity
        interval_metrics = _stream_metrics(
            initial_equity=interval_initial,
            equity=equity,
            equity_curve=interval_curve or [equity],
            realized_returns=interval_returns,
            buy_hold_equity=buy_hold_equity,
            turnover=sum(abs(row["position_after"] - row["position_before"]) for row in decisions[-len(interval_returns):])
            if interval_returns
            else 0.0,
            cost_paid=sum(row["cost"] for row in decisions[-len(interval_returns):])
            if interval_returns
            else 0.0,
            trade_count=sum(
                int(row["position_after"] != row["position_before"])
                for row in decisions[-len(interval_returns):]
            )
            if interval_returns
            else 0,
            active_steps=sum(
                int(row["position_after"] != 0)
                for row in decisions[-len(interval_returns):]
            )
            if interval_returns
            else 0,
            winning_steps=sum(
                int(row["position_after"] != 0 and row["position_after"] * row["realized_return"] > 0.0)
                for row in decisions[-len(interval_returns):]
            )
            if interval_returns
            else 0,
        )
        outcome = _review_outcome(interval_metrics, config.minimum_live_steps)
        signature = _failure_signature(interval_metrics)
        field_before_review = field.fingerprint() if field is not None else None
        strategy_admission: dict[str, Any] = {"admission": "not-applicable"}
        mutation_admission: dict[str, Any] = {"admission": "not-applicable"}
        composition_admission: dict[str, Any] = {"admission": "not-applicable"}
        prediction: dict[str, Any] | None = None
        next_mutation: str | None = None
        observed_mutation = active_mutation
        composition_before = composition_id
        if field is not None and learning_enabled:
            strategy_action = f"residency_strategy:{program.program_sha256}"
            strategy_admission = _bounded_write(
                field,
                lambda: field.learn_program(
                    signature,
                    strategy_action,
                    outcome,
                    repeats=1,
                ),
            )
            if active_mutation is not None:
                mutation_admission = _bounded_write(
                    field,
                    lambda: field.learn_transfer_gated(
                        signature,
                        active_mutation,
                        outcome,
                        repeats=1,
                    ),
                )
            composition_admission = _bounded_write(
                field,
                lambda: learn_financial_composition(
                    field,
                    signature,
                    composition_id,
                    outcome,
                ),
            )
            financial_selection = select_financial_composition(field, signature)
            next_composition = str(financial_selection["selected"]["composition_id"])
            predictions = {
                mutation: field.predict(signature, mutation) for mutation in MUTATIONS
            }
            promoted = [
                mutation
                for mutation in MUTATIONS
                if predictions[mutation].get("outcome") == "promote"
            ]
            next_mutation = promoted[0] if promoted else MUTATIONS[review_index % len(MUTATIONS)]
            prediction = {
                "financial_selection": financial_selection,
                "mutation_predictions": predictions,
            }
            composition_id = next_composition
            program = _child_program(program, next_mutation)
            active_mutation = next_mutation
        field_after_review = field.fingerprint() if field is not None else None
        reviews.append(
            {
                "review_index": review_index,
                "cutoff_index": cutoff_index,
                "available_until": owned[cutoff_index].timestamp,
                "future_bars_excluded": len(owned) - cutoff_index - 1,
                "lookahead_guard": "realized-prefix-only",
                "terminal": terminal,
                "observed_mutation": observed_mutation,
                "next_mutation": next_mutation,
                "financial_composition_before": composition_before,
                "financial_composition_after": composition_id,
                "failure_signature": signature,
                "outcome": outcome,
                "interval_metrics": interval_metrics,
                "field_prediction": prediction,
                "strategy_admission": strategy_admission,
                "mutation_admission": mutation_admission,
                "composition_admission": composition_admission,
                "field_before_sha256": field_before_review,
                "field_after_sha256": field_after_review,
                "counterfactual_backtests": 0,
            }
        )
        review_index += 1
        review_return_start = len(realized_returns)
        review_equity_start = len(equity_curve) - 1

    for index in range(len(owned) - 1):
        current = owned[index]
        following = owned[index + 1]
        history = owned[: index + 1]
        position_before = position
        features = _features(
            history,
            index,
            program,
            position=position,
            entry_price=entry_price,
            bars_in_position=bars_in_position,
        )
        requested = program.evaluate(features)
        target = (
            0.0
            if index < live_start_index
            else _target_position(requested, program=program, replay=replay)
        )
        change = abs(target - position)
        cost = change * replay.transaction_cost
        realized = following.close / current.close - 1.0
        net = target * realized - cost
        equity *= 1.0 + net
        if not math.isfinite(equity) or equity <= 0.0:
            raise RuntimeError("residency equity became nonpositive or nonfinite")
        if index >= live_start_index:
            trade_count += int(change > 0.0)
            turnover += change
            cost_paid += cost
            realized_returns.append(net)
            buy_hold_equity *= 1.0 + realized
            if target != 0.0:
                active_steps += 1
                winning_steps += int(target * realized > 0.0)
        if target == 0.0:
            entry_price = None
            bars_in_position = 0
        elif position == 0.0 or target != position:
            entry_price = following.open
            bars_in_position = 1
        else:
            bars_in_position += 1
        position = target
        equity_curve.append(equity)
        decisions.append(
            {
                "bar_index": index,
                "next_bar_index": index + 1,
                "available_prefix_count": index + 1,
                "available_until": current.timestamp,
                "execution_timestamp": following.timestamp,
                "future_bars_excluded": len(owned) - index - 2,
                "lookahead_guard": "realized-prefix-only",
                "phase": "warmup" if index < live_start_index else "live",
                "strategy_sha256": program.program_sha256,
                "financial_composition_id": composition_id,
                "signal": requested,
                "position_before": int(round(position_before)),
                "position_after": int(round(target)),
                "realized_return": realized,
                "net_return": net,
                "cost": cost,
                "equity": equity,
                "ready": features["ready"],
                "trend": features["trend"],
                "momentum": features["momentum"],
                "volatility": features["volatility"],
            }
        )
        available_index = index + 1
        live_steps = available_index - live_start_index
        if live_steps > 0 and live_steps % config.review_interval == 0:
            perform_review(available_index, terminal=False)

    if len(realized_returns) > review_return_start:
        perform_review(len(owned) - 1, terminal=True)

    metrics = _stream_metrics(
        initial_equity=replay.initial_equity,
        equity=equity,
        equity_curve=equity_curve,
        realized_returns=realized_returns,
        buy_hold_equity=buy_hold_equity,
        turnover=turnover,
        cost_paid=cost_paid,
        trade_count=trade_count,
        active_steps=active_steps,
        winning_steps=winning_steps,
    )
    final_signature = _failure_signature(metrics)
    if field is not None:
        final_selection = select_financial_composition(field, final_signature)
        final_composition = FINANCIAL_COMPOSITIONS[final_selection["selected"]["composition_id"]]
    else:
        final_selection = {
            "selection_reason": "static-control",
            "selected": FINANCIAL_COMPOSITIONS[composition_id].as_dict(),
        }
        final_composition = FINANCIAL_COMPOSITIONS[composition_id]
    source_id = f"cassi-residency:{owned[0].symbol}"
    event_rows = _events(owned, source_id)
    body: dict[str, Any] = {
        "schema": ARM_SCHEMA,
        "status": "PASS",
        "protocol": {
            "arm_name": arm_name,
            "learning_enabled": learning_enabled,
            "online_learning_only": True,
            "counterfactual_backtests": 0,
            "source_id": source_id,
            "source_revision": "market-residency.v1",
            "config": config.as_dict(),
            "initial_composition_id": initial_composition_id,
        },
        "data": {
            "symbol": owned[0].symbol,
            "bars": len(owned),
            "data_sha256": digest_value([bar.as_dict() for bar in owned]),
            "event_root_sha256": digest_value(event_rows),
            "event_schema": "cassi.market-event.v1",
        },
        "financial_teaching": financial_teaching,
        "field": _field_info(
            field,
            before=field_before,
            before_checkpoint_sha256=field_before_checkpoint_sha256,
        ),
        "initial_strategy": initial_strategy,
        "stream": {
            "decisions": decisions,
            "reviews": reviews,
            "metrics": metrics,
            "final_strategy": program.document(),
            "final_financial_selection": final_selection,
            "final_financial_composition": final_composition.as_dict(),
        },
    }
    body["content_sha256"] = digest_value(body)
    return body


def _strategy_from_document(document: Mapping[str, Any]) -> StrategyProgram:
    return StrategyProgram(
        strategy_id=str(document["strategy_id"]),
        source=str(document["source"]),
        parameters=dict(document["parameters"]),
        family=str(document["family"]),
        parent_id=document.get("parent_id"),
        mutation=str(document.get("mutation", "seed")),
    )


def _calibration_bundle(
    config: ResidencyConfig,
) -> tuple[dict[str, Any], bytes, StrategyProgram, str]:
    calibration_bars = _bar_series(
        "mixed",
        count=config.calibration_bars,
        symbol="RESIDENCY-CAL",
        phase_offset=0.37,
    )
    calibration = run_online_arm(
        calibration_bars,
        config=config,
        arm_name="synthetic-calibration",
        learning_enabled=True,
        teach_field=True,
        initial_composition_id="balanced",
    )
    checkpoint = bytes.fromhex(calibration["field"]["checkpoint_hex"])
    calibrated_program = _strategy_from_document(calibration["stream"]["final_strategy"])
    calibrated_composition = calibration["stream"]["final_financial_composition"]["composition_id"]
    return calibration, checkpoint, calibrated_program, str(calibrated_composition)


def run_market_residency(
    *,
    config: ResidencyConfig | None = None,
    external_bars: Sequence[MarketBar] | None = None,
    external_source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run calibration, online residency, static baseline, and frozen transfer."""

    residency = config or ResidencyConfig()
    external = tuple(
        external_bars
        if external_bars is not None
        else _bar_series(
            "mixed",
            count=residency.external_bars,
            symbol="RESIDENCY-EXTERNAL",
            phase_offset=1.73,
        )
    )
    if len(external) != residency.external_bars:
        raise ValueError("external stream length must equal ResidencyConfig.external_bars")
    calibration, checkpoint, calibrated_program, calibrated_composition = _calibration_bundle(residency)
    static = run_online_arm(
        external,
        config=residency,
        arm_name="static-baseline",
        learning_enabled=False,
        teach_field=False,
        initial_composition_id="balanced",
    )
    guided = run_online_arm(
        external,
        config=residency,
        arm_name="field-residency",
        seed_program=calibrated_program,
        field_memory=RefinementField.restore(checkpoint),
        learning_enabled=True,
        teach_field=False,
        initial_composition_id=calibrated_composition,
    )
    frozen = run_online_arm(
        external,
        config=residency,
        arm_name="frozen-transfer",
        seed_program=calibrated_program,
        field_memory=RefinementField.restore(checkpoint),
        learning_enabled=False,
        teach_field=False,
        initial_composition_id=calibrated_composition,
    )
    external_data_sha256 = digest_value([bar.as_dict() for bar in external])
    pairs = {
        "guided_vs_static": {
            "data_match": guided["data"]["data_sha256"] == static["data"]["data_sha256"],
            "net_return_delta": guided["stream"]["metrics"]["net_return"] - static["stream"]["metrics"]["net_return"],
            "objective_delta": guided["stream"]["metrics"]["objective"] - static["stream"]["metrics"]["objective"],
            "drawdown_delta": guided["stream"]["metrics"]["max_drawdown"] - static["stream"]["metrics"]["max_drawdown"],
        },
        "frozen_vs_static": {
            "data_match": frozen["data"]["data_sha256"] == static["data"]["data_sha256"],
            "net_return_delta": frozen["stream"]["metrics"]["net_return"] - static["stream"]["metrics"]["net_return"],
            "objective_delta": frozen["stream"]["metrics"]["objective"] - static["stream"]["metrics"]["objective"],
            "drawdown_delta": frozen["stream"]["metrics"]["max_drawdown"] - static["stream"]["metrics"]["max_drawdown"],
        },
        "guided_vs_frozen": {
            "data_match": guided["data"]["data_sha256"] == frozen["data"]["data_sha256"],
            "net_return_delta": guided["stream"]["metrics"]["net_return"] - frozen["stream"]["metrics"]["net_return"],
            "objective_delta": guided["stream"]["metrics"]["objective"] - frozen["stream"]["metrics"]["objective"],
        },
    }
    body: dict[str, Any] = {
        "schema": RESIDENCY_SCHEMA,
        "status": "PASS",
        "protocol": {
            "scenario_id": RESIDENCY_SCENARIO_ID,
            "description": RESIDENCY_DESCRIPTION,
            "calibration_stream": "synthetic mixed regime",
            "external_stream": "matched external closed-bar stream",
            "online_learning_only": True,
            "counterfactual_backtests": 0,
            "config": residency.as_dict(),
            "external_source": dict(external_source or {"kind": "synthetic", "source_bars": len(external)}),
            "external_data_sha256": external_data_sha256,
        },
        "calibration": calibration,
        "external": {
            "data_sha256": external_data_sha256,
            "static": static,
            "field_residency": guided,
            "frozen_transfer": frozen,
        },
        "pairs": pairs,
    }
    body["content_sha256"] = digest_value(body)
    return body


def _verify_arm(receipt: Mapping[str, Any], *, require_field_change: bool) -> None:
    if receipt.get("schema") != ARM_SCHEMA or receipt.get("status") != "PASS":
        raise ValueError("residency arm receipt is invalid")
    protocol = receipt.get("protocol")
    data = receipt.get("data")
    stream = receipt.get("stream")
    config = protocol.get("config") if isinstance(protocol, Mapping) else None
    if (
        not isinstance(protocol, Mapping)
        or not isinstance(data, Mapping)
        or not isinstance(stream, Mapping)
        or not isinstance(config, Mapping)
    ):
        raise ValueError("residency arm is incomplete")
    arm_name = str(protocol.get("arm_name"))
    bars_key = "external_bars" if arm_name != "synthetic-calibration" else "calibration_bars"
    bars = int(config[bars_key])
    if int(data.get("bars", -1)) != bars:
        raise ValueError("residency arm data length is invalid")
    decisions = stream.get("decisions")
    reviews = stream.get("reviews")
    if not isinstance(decisions, list) or len(decisions) != bars - 1:
        raise ValueError("residency arm decision count mismatch")
    if not isinstance(reviews, list) or not reviews:
        raise ValueError("residency arm has no realized reviews")
    if protocol.get("counterfactual_backtests") != 0 or not protocol.get("online_learning_only"):
        raise ValueError("residency arm is not online-only")
    for index, decision in enumerate(decisions):
        if decision.get("bar_index") != index or decision.get("next_bar_index") != index + 1:
            raise ValueError("residency arm decision is not causal")
        if decision.get("available_prefix_count") != index + 1:
            raise ValueError("residency arm prefix count is invalid")
        if decision.get("future_bars_excluded") != bars - index - 2:
            raise ValueError("residency arm future exclusion is invalid")
    previous_cutoff = -1
    for index, review in enumerate(reviews):
        if review.get("review_index") != index:
            raise ValueError("residency review index is not ordered")
        cutoff = int(review["cutoff_index"])
        if cutoff <= previous_cutoff or cutoff >= bars:
            raise ValueError("residency review cutoff is not ordered")
        previous_cutoff = cutoff
        if review.get("future_bars_excluded") != bars - cutoff - 1:
            raise ValueError("residency review future exclusion is invalid")
        if review.get("counterfactual_backtests") != 0:
            raise ValueError("residency review used a counterfactual backtest")
    field = receipt.get("field")
    if not isinstance(field, Mapping):
        raise ValueError("residency arm field receipt is missing")
    if field.get("mode") == "field-owned":
        checkpoint_hex = field.get("checkpoint_hex")
        if not isinstance(checkpoint_hex, str):
            raise ValueError("field-owned arm has no checkpoint")
        try:
            checkpoint = bytes.fromhex(checkpoint_hex)
        except ValueError as exc:
            raise ValueError("field checkpoint is not hexadecimal") from exc
        if field.get("checkpoint_bytes") != len(checkpoint):
            raise ValueError("field checkpoint length is invalid")
        if field.get("checkpoint_sha256") != hashlib.sha256(checkpoint).hexdigest():
            raise ValueError("field checkpoint digest mismatch")
        if field.get("component_limit") != config.get("field_component_limit"):
            raise ValueError("field profile does not match residency config")
        if field.get("wave_width") != config.get("field_wave_width"):
            raise ValueError("field wave width does not match residency config")
        for key in ("capacity_events", "consolidation_events", "consolidation_steps"):
            if (
                isinstance(field.get(key), bool)
                or not isinstance(field.get(key), int)
                or field.get(key) < 0
            ):
                raise ValueError(f"field {key} is invalid")
        if not isinstance(field.get("before_sha256"), str) or not isinstance(field.get("after_sha256"), str):
            raise ValueError("field identity is incomplete")
        if not isinstance(field.get("before_checkpoint_sha256"), str):
            raise ValueError("field checkpoint start identity is incomplete")
    elif field.get("mode") != "none":
        raise ValueError("unknown residency field mode")
    if require_field_change:
        if field.get("mode") != "field-owned" or field.get("before_sha256") == field.get("after_sha256"):
            raise ValueError("calibration field did not change")
    body = dict(receipt)
    stated = body.pop("content_sha256", None)
    if not isinstance(stated, str) or digest_value(body) != stated:
        raise ValueError("residency arm digest mismatch")


def verify_market_residency(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != RESIDENCY_SCHEMA or receipt.get("status") != "PASS":
        raise ValueError("market residency receipt is invalid")
    calibration = receipt.get("calibration")
    external = receipt.get("external")
    pairs = receipt.get("pairs")
    protocol = receipt.get("protocol")
    if (
        not isinstance(calibration, Mapping)
        or not isinstance(external, Mapping)
        or not isinstance(pairs, Mapping)
        or not isinstance(protocol, Mapping)
    ):
        raise ValueError("market residency receipt is incomplete")
    _verify_arm(calibration, require_field_change=True)
    static = external.get("static")
    guided = external.get("field_residency")
    frozen = external.get("frozen_transfer")
    arms = (static, guided, frozen)
    if not all(isinstance(arm, Mapping) for arm in arms):
        raise ValueError("matched residency arms are missing")
    assert isinstance(static, Mapping)
    assert isinstance(guided, Mapping)
    assert isinstance(frozen, Mapping)
    _verify_arm(static, require_field_change=False)
    _verify_arm(guided, require_field_change=False)
    _verify_arm(frozen, require_field_change=False)
    expected_config = protocol.get("config")
    if not isinstance(expected_config, Mapping):
        raise ValueError("residency protocol config is missing")
    if any(arm["protocol"].get("config") != expected_config for arm in arms):
        raise ValueError("residency arms do not share config")
    data_hashes = {arm["data"]["data_sha256"] for arm in arms}
    external_hash = protocol.get("external_data_sha256")
    if len(data_hashes) != 1 or next(iter(data_hashes)) != external_hash:
        raise ValueError("matched residency arms do not share external data")
    calibration_strategy = calibration["stream"]["final_strategy"]
    calibration_field = calibration["field"]
    for arm in (guided, frozen):
        if arm["initial_strategy"]["program_sha256"] != calibration_strategy["program_sha256"]:
            raise ValueError("transfer arm did not inherit calibration strategy")
        if arm["field"].get("before_checkpoint_sha256") != calibration_field.get("checkpoint_sha256"):
            raise ValueError("transfer arm did not inherit calibration field")
        if arm["field"].get("before_sha256") != calibration_field.get("after_sha256"):
            raise ValueError("transfer arm field start does not match calibration")
    if frozen["protocol"]["learning_enabled"] or frozen["stream"]["final_strategy"]["program_sha256"] != frozen["initial_strategy"]["program_sha256"]:
        raise ValueError("frozen transfer arm changed its policy")
    if guided["protocol"]["learning_enabled"] is not True:
        raise ValueError("field residency arm is not learning-enabled")
    if static["protocol"]["learning_enabled"] is not False or static["field"].get("mode") != "none":
        raise ValueError("static baseline is not a static field-free arm")
    expected_pairs = {
        "guided_vs_static": {
            "data_match": guided["data"]["data_sha256"] == static["data"]["data_sha256"],
            "net_return_delta": guided["stream"]["metrics"]["net_return"] - static["stream"]["metrics"]["net_return"],
            "objective_delta": guided["stream"]["metrics"]["objective"] - static["stream"]["metrics"]["objective"],
            "drawdown_delta": guided["stream"]["metrics"]["max_drawdown"] - static["stream"]["metrics"]["max_drawdown"],
        },
        "frozen_vs_static": {
            "data_match": frozen["data"]["data_sha256"] == static["data"]["data_sha256"],
            "net_return_delta": frozen["stream"]["metrics"]["net_return"] - static["stream"]["metrics"]["net_return"],
            "objective_delta": frozen["stream"]["metrics"]["objective"] - static["stream"]["metrics"]["objective"],
            "drawdown_delta": frozen["stream"]["metrics"]["max_drawdown"] - static["stream"]["metrics"]["max_drawdown"],
        },
        "guided_vs_frozen": {
            "data_match": guided["data"]["data_sha256"] == frozen["data"]["data_sha256"],
            "net_return_delta": guided["stream"]["metrics"]["net_return"] - frozen["stream"]["metrics"]["net_return"],
            "objective_delta": guided["stream"]["metrics"]["objective"] - frozen["stream"]["metrics"]["objective"],
        },
    }
    if dict(pairs) != expected_pairs:
        raise ValueError("residency pair summary is inconsistent")
    body = dict(receipt)
    stated = body.pop("content_sha256", None)
    if not isinstance(stated, str) or digest_value(body) != stated:
        raise ValueError("market residency digest mismatch")
    return {
        "status": "PASS",
        "content_sha256": stated,
        "calibration_final_equity": calibration["stream"]["metrics"]["final_equity"],
        "guided_final_equity": guided["stream"]["metrics"]["final_equity"],
        "frozen_final_equity": frozen["stream"]["metrics"]["final_equity"],
        "static_final_equity": static["stream"]["metrics"]["final_equity"],
        "guided_reviews": len(guided["stream"]["reviews"]),
    }


def _campaign_aggregate(
    windows: Sequence[Mapping[str, Any]],
    *,
    initial_equity: float,
) -> dict[str, Any]:
    if not windows:
        raise ValueError("campaign arm requires at least one window")
    ratios = [
        float(row["receipt"]["stream"]["metrics"]["final_equity"]) / initial_equity
        for row in windows
    ]
    compound_ratio = math.prod(ratios)
    return {
        "window_count": len(windows),
        "window_final_equities": [
            row["receipt"]["stream"]["metrics"]["final_equity"] for row in windows
        ],
        "window_net_returns": [
            row["receipt"]["stream"]["metrics"]["net_return"] for row in windows
        ],
        "compound_final_equity": initial_equity * compound_ratio,
        "compound_net_return": compound_ratio - 1.0,
        "mean_objective": sum(
            row["receipt"]["stream"]["metrics"]["objective"] for row in windows
        )
        / len(windows),
    }


def _run_campaign_arm(
    segments: Sequence[Sequence[MarketBar]],
    *,
    config: ResidencyConfig,
    arm_name: str,
    mode: str,
    calibration_checkpoint: bytes,
    calibrated_program: StrategyProgram,
    calibrated_composition: str,
) -> dict[str, Any]:
    if mode not in {"carried-field", "frozen-transfer", "fresh-field", "static-baseline"}:
        raise ValueError(f"unknown campaign arm mode: {mode}")
    field_memory = (
        RefinementField.restore(calibration_checkpoint)
        if mode == "carried-field"
        else None
    )
    program = calibrated_program
    composition_id = calibrated_composition
    rows: list[dict[str, Any]] = []
    for window_index, segment in enumerate(segments):
        if mode == "carried-field":
            receipt = run_online_arm(
                segment,
                config=config,
                arm_name=f"campaign-{arm_name}-window-{window_index}",
                seed_program=program,
                field_memory=field_memory,
                learning_enabled=True,
                teach_field=False,
                initial_composition_id=composition_id,
            )
            program = _strategy_from_document(receipt["stream"]["final_strategy"])
            composition_id = str(
                receipt["stream"]["final_financial_composition"]["composition_id"]
            )
        elif mode == "frozen-transfer":
            receipt = run_online_arm(
                segment,
                config=config,
                arm_name=f"campaign-{arm_name}-window-{window_index}",
                seed_program=calibrated_program,
                field_memory=RefinementField.restore(calibration_checkpoint),
                learning_enabled=False,
                teach_field=False,
                initial_composition_id=calibrated_composition,
            )
        elif mode == "fresh-field":
            receipt = run_online_arm(
                segment,
                config=config,
                arm_name=f"campaign-{arm_name}-window-{window_index}",
                learning_enabled=True,
                teach_field=True,
                initial_composition_id="balanced",
            )
        else:
            receipt = run_online_arm(
                segment,
                config=config,
                arm_name=f"campaign-{arm_name}-window-{window_index}",
                learning_enabled=False,
                teach_field=False,
                initial_composition_id="balanced",
            )
        start_index = window_index * config.external_bars
        rows.append(
            {
                "window_index": window_index,
                "start_index": start_index,
                "end_index": start_index + len(segment) - 1,
                "timestamp_start": segment[0].timestamp,
                "timestamp_end": segment[-1].timestamp,
                "window_data_sha256": digest_value(
                    [bar.as_dict() for bar in segment]
                ),
                "receipt": receipt,
            }
        )
    return {
        "mode": mode,
        "windows": rows,
        "aggregate": _campaign_aggregate(
            rows,
            initial_equity=config.initial_equity,
        ),
    }


def run_market_residency_campaign(
    *,
    config: ResidencyConfig | None = None,
    external_bars: Sequence[MarketBar] | None = None,
    window_count: int = 5,
    external_source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run calibration once, then compare chronological residency arms."""

    residency = config or ResidencyConfig()
    if window_count < 2:
        raise ValueError("window_count must be at least two")
    total_bars = residency.external_bars * window_count
    external = tuple(
        external_bars
        if external_bars is not None
        else _bar_series(
            "mixed",
            count=total_bars,
            symbol="RESIDENCY-CAMPAIGN",
            phase_offset=1.73,
        )
    )
    if len(external) != total_bars:
        raise ValueError("campaign external stream length does not match its windows")
    segments = tuple(
        external[start : start + residency.external_bars]
        for start in range(0, total_bars, residency.external_bars)
    )
    calibration, checkpoint, calibrated_program, calibrated_composition = _calibration_bundle(
        residency
    )
    arm_specs = (
        ("carried_field", "carried-field"),
        ("frozen_transfer", "frozen-transfer"),
        ("fresh_field", "fresh-field"),
        ("static_baseline", "static-baseline"),
    )
    arms = {
        name: _run_campaign_arm(
            segments,
            config=residency,
            arm_name=name,
            mode=mode,
            calibration_checkpoint=checkpoint,
            calibrated_program=calibrated_program,
            calibrated_composition=calibrated_composition,
        )
        for name, mode in arm_specs
    }
    aggregate_pairs = {
        "carried_vs_frozen": {
            "compound_net_return_delta": (
                arms["carried_field"]["aggregate"]["compound_net_return"]
                - arms["frozen_transfer"]["aggregate"]["compound_net_return"]
            ),
            "mean_objective_delta": (
                arms["carried_field"]["aggregate"]["mean_objective"]
                - arms["frozen_transfer"]["aggregate"]["mean_objective"]
            ),
        },
        "carried_vs_fresh": {
            "compound_net_return_delta": (
                arms["carried_field"]["aggregate"]["compound_net_return"]
                - arms["fresh_field"]["aggregate"]["compound_net_return"]
            ),
            "mean_objective_delta": (
                arms["carried_field"]["aggregate"]["mean_objective"]
                - arms["fresh_field"]["aggregate"]["mean_objective"]
            ),
        },
        "carried_vs_static": {
            "compound_net_return_delta": (
                arms["carried_field"]["aggregate"]["compound_net_return"]
                - arms["static_baseline"]["aggregate"]["compound_net_return"]
            ),
            "mean_objective_delta": (
                arms["carried_field"]["aggregate"]["mean_objective"]
                - arms["static_baseline"]["aggregate"]["mean_objective"]
            ),
        },
    }
    window_data_sha256 = [
        digest_value([bar.as_dict() for bar in segment]) for segment in segments
    ]
    body: dict[str, Any] = {
        "schema": CAMPAIGN_SCHEMA,
        "status": "PASS",
        "protocol": {
            "scenario_id": CAMPAIGN_SCENARIO_ID,
            "description": CAMPAIGN_DESCRIPTION,
            "calibration_stream": "synthetic mixed regime",
            "external_stream": "chronological disjoint closed-bar windows",
            "online_learning_only": True,
            "counterfactual_backtests": 0,
            "window_count": window_count,
            "window_bars": residency.external_bars,
            "config": residency.as_dict(),
            "external_source": dict(
                external_source
                or {"kind": "synthetic", "source_bars": len(external)}
            ),
        },
        "data": {
            "symbol": external[0].symbol,
            "bars": len(external),
            "data_sha256": digest_value([bar.as_dict() for bar in external]),
            "window_data_sha256": window_data_sha256,
            "event_schema": "cassi.market-event.v1",
        },
        "calibration": calibration,
        "arms": arms,
        "aggregate_pairs": aggregate_pairs,
    }
    body["content_sha256"] = digest_value(body)
    return body


def _verify_campaign_arm(
    arm: Mapping[str, Any],
    *,
    name: str,
    mode: str,
    expected_config: Mapping[str, Any],
    expected_window_hashes: Sequence[str],
    initial_equity: float,
) -> dict[str, Any]:
    if arm.get("mode") != mode:
        raise ValueError(f"{name} arm mode is invalid")
    rows = arm.get("windows")
    if not isinstance(rows, list) or len(rows) != len(expected_window_hashes):
        raise ValueError(f"{name} arm window count is invalid")
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"{name} window row is incomplete")
        if row.get("window_index") != index:
            raise ValueError(f"{name} windows are not ordered")
        if row.get("start_index") != index * int(expected_config["external_bars"]):
            raise ValueError(f"{name} window start is invalid")
        if row.get("end_index") != (index + 1) * int(expected_config["external_bars"]) - 1:
            raise ValueError(f"{name} window end is invalid")
        if row.get("window_data_sha256") != expected_window_hashes[index]:
            raise ValueError(f"{name} window data digest is invalid")
        receipt = row.get("receipt")
        if not isinstance(receipt, Mapping):
            raise ValueError(f"{name} window receipt is missing")
        _verify_arm(receipt, require_field_change=False)
        if receipt["protocol"].get("config") != expected_config:
            raise ValueError(f"{name} window config does not match campaign")
        if receipt["data"].get("data_sha256") != expected_window_hashes[index]:
            raise ValueError(f"{name} window receipt data does not match campaign")
        if receipt["protocol"].get("arm_name") != f"campaign-{name}-window-{index}":
            raise ValueError(f"{name} window arm identity is invalid")
    expected_aggregate = _campaign_aggregate(
        rows,
        initial_equity=initial_equity,
    )
    if dict(arm.get("aggregate", {})) != expected_aggregate:
        raise ValueError(f"{name} aggregate is inconsistent")
    return expected_aggregate


def verify_market_residency_campaign(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    if receipt.get("schema") != CAMPAIGN_SCHEMA or receipt.get("status") != "PASS":
        raise ValueError("market residency campaign receipt is invalid")
    protocol = receipt.get("protocol")
    data = receipt.get("data")
    calibration = receipt.get("calibration")
    arms = receipt.get("arms")
    aggregate_pairs = receipt.get("aggregate_pairs")
    if (
        not isinstance(protocol, Mapping)
        or not isinstance(data, Mapping)
        or not isinstance(calibration, Mapping)
        or not isinstance(arms, Mapping)
        or not isinstance(aggregate_pairs, Mapping)
    ):
        raise ValueError("market residency campaign receipt is incomplete")
    config = protocol.get("config")
    if not isinstance(config, Mapping):
        raise ValueError("campaign config is missing")
    window_count = int(protocol["window_count"])
    window_bars = int(protocol["window_bars"])
    if window_count < 2 or int(data.get("bars", -1)) != window_count * window_bars:
        raise ValueError("campaign data dimensions are invalid")
    if not isinstance(data.get("data_sha256"), str):
        raise ValueError("campaign data digest is missing")
    window_hashes = data.get("window_data_sha256")
    if (
        not isinstance(window_hashes, list)
        or len(window_hashes) != window_count
        or any(not isinstance(value, str) for value in window_hashes)
    ):
        raise ValueError("campaign window digests are incomplete")
    _verify_arm(calibration, require_field_change=True)
    if calibration["protocol"].get("config") != config:
        raise ValueError("campaign calibration config does not match")
    arm_modes = {
        "carried_field": "carried-field",
        "frozen_transfer": "frozen-transfer",
        "fresh_field": "fresh-field",
        "static_baseline": "static-baseline",
    }
    aggregates = {
        name: _verify_campaign_arm(
            arms[name],
            name=name,
            mode=mode,
            expected_config=config,
            expected_window_hashes=window_hashes,
            initial_equity=float(config["initial_equity"]),
        )
        for name, mode in arm_modes.items()
        if name in arms and isinstance(arms[name], Mapping)
    }
    if set(aggregates) != set(arm_modes):
        raise ValueError("campaign arms are incomplete")
    calibration_strategy = calibration["stream"]["final_strategy"]
    calibration_field = calibration["field"]
    seed_program_sha256 = StrategyProgram.seed().program_sha256
    carried_rows = arms["carried_field"]["windows"]
    frozen_rows = arms["frozen_transfer"]["windows"]
    fresh_rows = arms["fresh_field"]["windows"]
    static_rows = arms["static_baseline"]["windows"]
    for index in range(window_count):
        carried_receipt = carried_rows[index]["receipt"]
        carried_expected_strategy = (
            calibration_strategy
            if index == 0
            else carried_rows[index - 1]["receipt"]["stream"]["final_strategy"]
        )
        carried_expected_field = (
            calibration_field
            if index == 0
            else carried_rows[index - 1]["receipt"]["field"]
        )
        if (
            carried_receipt["initial_strategy"]["program_sha256"]
            != carried_expected_strategy["program_sha256"]
            or carried_receipt["field"]["before_checkpoint_sha256"]
            != carried_expected_field["checkpoint_sha256"]
            or carried_receipt["field"]["before_sha256"]
            != carried_expected_field["after_sha256"]
            or carried_receipt["protocol"]["learning_enabled"] is not True
        ):
            raise ValueError("carried field arm did not continue chronologically")
        frozen_receipt = frozen_rows[index]["receipt"]
        if (
            frozen_receipt["initial_strategy"]["program_sha256"]
            != calibration_strategy["program_sha256"]
            or frozen_receipt["field"]["before_checkpoint_sha256"]
            != calibration_field["checkpoint_sha256"]
            or frozen_receipt["field"]["before_sha256"]
            != calibration_field["after_sha256"]
            or frozen_receipt["protocol"]["learning_enabled"]
            or frozen_receipt["stream"]["final_strategy"]["program_sha256"]
            != frozen_receipt["initial_strategy"]["program_sha256"]
        ):
            raise ValueError("frozen transfer arm was not frozen")
        fresh_receipt = fresh_rows[index]["receipt"]
        if (
            fresh_receipt["initial_strategy"]["program_sha256"] != seed_program_sha256
            or fresh_receipt["protocol"]["learning_enabled"] is not True
            or fresh_receipt["field"]["before_sha256"]
            == fresh_receipt["field"]["after_sha256"]
        ):
            raise ValueError("fresh field control was not fresh and adaptive")
        static_receipt = static_rows[index]["receipt"]
        if (
            static_receipt["initial_strategy"]["program_sha256"] != seed_program_sha256
            or static_receipt["protocol"]["learning_enabled"]
            or static_receipt["field"].get("mode") != "none"
        ):
            raise ValueError("static baseline is not field-free")
    expected_pairs = {
        "carried_vs_frozen": {
            "compound_net_return_delta": (
                aggregates["carried_field"]["compound_net_return"]
                - aggregates["frozen_transfer"]["compound_net_return"]
            ),
            "mean_objective_delta": (
                aggregates["carried_field"]["mean_objective"]
                - aggregates["frozen_transfer"]["mean_objective"]
            ),
        },
        "carried_vs_fresh": {
            "compound_net_return_delta": (
                aggregates["carried_field"]["compound_net_return"]
                - aggregates["fresh_field"]["compound_net_return"]
            ),
            "mean_objective_delta": (
                aggregates["carried_field"]["mean_objective"]
                - aggregates["fresh_field"]["mean_objective"]
            ),
        },
        "carried_vs_static": {
            "compound_net_return_delta": (
                aggregates["carried_field"]["compound_net_return"]
                - aggregates["static_baseline"]["compound_net_return"]
            ),
            "mean_objective_delta": (
                aggregates["carried_field"]["mean_objective"]
                - aggregates["static_baseline"]["mean_objective"]
            ),
        },
    }
    if dict(aggregate_pairs) != expected_pairs:
        raise ValueError("campaign aggregate comparisons are inconsistent")
    body = dict(receipt)
    stated = body.pop("content_sha256", None)
    if not isinstance(stated, str) or digest_value(body) != stated:
        raise ValueError("market residency campaign digest mismatch")
    return {
        "status": "PASS",
        "content_sha256": stated,
        "windows": window_count,
        "calibration": calibration["stream"]["metrics"],
        "arms": aggregates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="closed historical OHLCV CSV for external residency")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--calibration-bars", type=int, default=768)
    parser.add_argument("--external-bars", type=int, default=1536)
    parser.add_argument("--warmup-bars", type=int, default=48)
    parser.add_argument("--review-interval", type=int, default=24)
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--field-component-limit", type=float, default=4.0)
    parser.add_argument("--field-wave-width", type=int, default=512)
    parser.add_argument("--out", type=Path, default=Path("_diag/market-residency.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = ResidencyConfig(
        calibration_bars=args.calibration_bars,
        external_bars=args.external_bars,
        warmup_bars=args.warmup_bars,
        review_interval=args.review_interval,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        field_component_limit=args.field_component_limit,
        field_wave_width=args.field_wave_width,
    )
    external_source: dict[str, Any]
    external_bars: tuple[MarketBar, ...] | None
    if args.csv is None:
        external_bars = None
        external_source = {"kind": "synthetic", "source_bars": config.external_bars}
    else:
        source = load_bars_csv(args.csv, symbol=args.symbol)
        if len(source) < config.external_bars:
            raise SystemExit("historical CSV is shorter than --external-bars")
        external_bars = tuple(source[: config.external_bars])
        external_source = {
            "kind": "historical_csv",
            "path": str(args.csv),
            "symbol": args.symbol or source[0].symbol,
            "source_bars": len(source),
            "source_data_sha256": digest_value([bar.as_dict() for bar in source]),
        }
    receipt = run_market_residency(
        config=config,
        external_bars=external_bars,
        external_source=external_source,
    )
    verification = verify_market_residency(receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": verification["status"],
                "out": str(args.out),
                "content_sha256": verification["content_sha256"],
                "calibration_final_equity": verification["calibration_final_equity"],
                "static_final_equity": verification["static_final_equity"],
                "guided_final_equity": verification["guided_final_equity"],
                "frozen_final_equity": verification["frozen_final_equity"],
                "guided_reviews": verification["guided_reviews"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
