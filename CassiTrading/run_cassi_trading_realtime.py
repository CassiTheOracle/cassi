#!/usr/bin/env python3
"""Run the deterministic causal realtime Cassi Trading benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Mapping, Sequence

from cassi_trading_foundry import (
    FINANCIAL_COMPOSITIONS,
    FINANCIAL_SKILL_IDS,
    MarketBar,
    ReplayConfig,
    RefinementField,
    StrategyProgram,
    _FIELD_MUTATION_CODES,
    _child_program,
    _failure_signature,
    _features,
    _max_drawdown,
    _objective,
    _validate_bars,
    digest_value,
    learn_financial_composition,
    load_bars_csv,
    run_backtest,
    score_financial_composition,
    select_financial_composition,
    teach_financial_math,
)
from cassi_raw_event_field import CapacityError
from run_cassi_trading_benchmark import _bar_series


REALTIME_SCHEMA = "cassi.trading-realtime-benchmark.v1"
STANDARD_SCENARIO_ID = "RT-1-mixed-hourly"
STANDARD_SCENARIO_DESCRIPTION = (
    "384 hourly bars across four repeating regimes; the field receives one bar "
    "at a time, trades causally, and adapts every 24 live bars"
)


@dataclass(frozen=True, slots=True)
class RealtimeConfig:
    scenario_id: str = STANDARD_SCENARIO_ID
    bars: int = 384
    warmup_bars: int = 48
    adaptation_interval: int = 24
    max_candidates: int = 4
    minimum_improvement: float = 0.0005
    minimum_trades: int = 3
    maximum_drawdown: float = 0.35
    replay: ReplayConfig = field(default_factory=ReplayConfig)

    def __post_init__(self) -> None:
        if self.scenario_id != STANDARD_SCENARIO_ID:
            raise ValueError("realtime benchmark uses the standard scenario identifier")
        if self.bars < 96:
            raise ValueError("realtime benchmark requires at least 96 bars")
        if self.warmup_bars < 8 or self.warmup_bars >= self.bars - 2:
            raise ValueError("warmup_bars must leave a live trading interval")
        if self.adaptation_interval < 4:
            raise ValueError("adaptation_interval must be at least four bars")
        if self.max_candidates < 1 or self.max_candidates > len(_FIELD_MUTATION_CODES):
            raise ValueError("max_candidates exceeds the fixed mutation catalog")
        if self.minimum_trades < 1:
            raise ValueError("minimum_trades must be positive")
        if not math.isfinite(self.minimum_improvement) or self.minimum_improvement < 0.0:
            raise ValueError("minimum_improvement must be finite and nonnegative")
        if not math.isfinite(self.maximum_drawdown) or self.maximum_drawdown < 0.0:
            raise ValueError("maximum_drawdown must be finite and nonnegative")

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "bars": self.bars,
            "warmup_bars": self.warmup_bars,
            "adaptation_interval": self.adaptation_interval,
            "max_candidates": self.max_candidates,
            "minimum_improvement": self.minimum_improvement,
            "minimum_trades": self.minimum_trades,
            "maximum_drawdown": self.maximum_drawdown,
            "replay": self.replay.as_dict(),
        }


def _bounded_field_write(field: RefinementField, writer: Any) -> dict[str, Any]:
    if getattr(field, "_realtime_learning_saturated", False):
        return {
            "admission": "capacity-saturated",
            "promoted": False,
            "reason": "field-component-bound",
        }
    try:
        return dict(writer())
    except CapacityError:
        setattr(field, "_realtime_learning_saturated", True)
        return {
            "admission": "capacity-saturated",
            "promoted": False,
            "reason": "field-component-bound",
        }


def standard_scenario_bars(*, count: int = 384) -> tuple[MarketBar, ...]:
    """Return the pinned causal stream used by the standard benchmark."""

    return _bar_series("mixed", count=count, symbol="REALTIME")


def _target_position(
    requested: int,
    *,
    program: StrategyProgram,
    replay: ReplayConfig,
) -> float:
    target = float(requested)
    if program.parameters["allow_short"] == 0.0 and target < 0.0:
        target = 0.0
    return max(-replay.max_position, min(replay.max_position, target))


def _adapt_field(
    bars: Sequence[MarketBar],
    *,
    cutoff_index: int,
    program: StrategyProgram,
    field: RefinementField,
    config: RealtimeConfig,
    position: float,
) -> tuple[StrategyProgram, dict[str, Any]]:
    """Evaluate only bars known at the adaptation cutoff and update the field."""

    prefix = tuple(bars[: cutoff_index + 1])
    parent = run_backtest(
        prefix,
        program,
        config.replay,
        start_index=0,
        end_index=cutoff_index,
    )
    signature = _failure_signature(parent.metrics)
    financial_selection = select_financial_composition(field, signature)
    composition_id = str(financial_selection["selected"]["composition_id"])
    composition = FINANCIAL_COMPOSITIONS[composition_id]
    parent_financial = score_financial_composition(composition, parent.metrics, config.replay)
    predictions = {
        mutation: field.predict(signature, mutation)
        for mutation in _FIELD_MUTATION_CODES
    }
    ordered_mutations = sorted(
        _FIELD_MUTATION_CODES,
        key=lambda mutation: (
            {"promote": 0, None: 1, "uncertain": 1, "reject": 2}.get(
                predictions[mutation].get("outcome"),
                1,
            ),
            -float(predictions[mutation].get("score") or 0.0),
        ),
    )[: config.max_candidates]

    field_before = field.fingerprint()
    candidate_rows: list[dict[str, Any]] = []
    candidate_programs: dict[str, StrategyProgram] = {}
    for mutation in ordered_mutations:
        candidate = _child_program(program, mutation)
        candidate_programs[mutation] = candidate
        candidate_result = run_backtest(
            prefix,
            candidate,
            config.replay,
            start_index=0,
            end_index=cutoff_index,
        )
        candidate_financial = score_financial_composition(
            composition,
            candidate_result.metrics,
            config.replay,
        )
        enough_trades = candidate_result.metrics["trade_count"] >= config.minimum_trades
        safe_drawdown = candidate_result.metrics["max_drawdown"] <= config.maximum_drawdown
        improved = (
            candidate_financial["objective"]
            >= parent_financial["objective"] + config.minimum_improvement
        )
        outcome = "promote" if enough_trades and safe_drawdown and improved else "reject"
        if not enough_trades:
            outcome = "uncertain"
        admission = {
            "admission": "deferred-until-selection",
            "promoted": False,
            "outcome": outcome,
        }
        candidate_rows.append(
            {
                "mutation": mutation,
                "field_prediction": predictions[mutation],
                "candidate": candidate.document(),
                "metrics": dict(candidate_result.metrics),
                "financial_score": candidate_financial,
                "enough_trades": enough_trades,
                "safe_drawdown": safe_drawdown,
                "improved": improved,
                "outcome": outcome,
                "field_admission": admission,
            }
        )

    composition_outcome = (
        "promote"
        if any(row["outcome"] == "promote" for row in candidate_rows)
        else "uncertain"
        if any(row["outcome"] == "uncertain" for row in candidate_rows)
        else "reject"
    )
    composition_admission = _bounded_field_write(
        field,
        lambda: learn_financial_composition(
            field,
            signature,
            composition_id,
            composition_outcome,
        ),
    )
    promoted = [row for row in candidate_rows if row["outcome"] == "promote"]
    selected_row = (
        max(
            promoted,
            key=lambda row: (
                row["financial_score"]["objective"],
                row["metrics"]["objective"],
            ),
        )
        if promoted
        else None
    )
    selected_program = (
        candidate_programs[str(selected_row["mutation"])]
        if selected_row is not None
        else program
    )
    teaching_row = selected_row or max(
        candidate_rows,
        key=lambda row: (
            row["financial_score"]["objective"],
            row["metrics"]["objective"],
        ),
    )
    selected_admission = _bounded_field_write(
        field,
        lambda: field.learn_transfer_gated(
            signature,
            str(teaching_row["mutation"]),
            str(teaching_row["outcome"]),
            repeats=1,
        ),
    )
    for row in candidate_rows:
        if row["mutation"] == teaching_row["mutation"]:
            row["field_admission"] = selected_admission
        else:
            row["field_admission"] = {
                "admission": "not-selected",
                "promoted": False,
                "outcome": row["outcome"],
            }
    field_after = field.fingerprint()
    event = {
        "available_through_index": cutoff_index,
        "available_until": bars[cutoff_index].timestamp,
        "next_decision_index": cutoff_index,
        "candidate_replay_end_index": cutoff_index,
        "future_bars_excluded": len(bars) - cutoff_index - 1,
        "lookahead_guard": "prefix-only-causal",
        "position_before_adaptation": position,
        "parent_strategy": program.document(),
        "failure_signature": signature,
        "financial_selection": financial_selection,
        "financial_composition": composition.as_dict(),
        "parent_financial_score": parent_financial,
        "financial_composition_outcome": composition_outcome,
        "financial_composition_admission": composition_admission,
        "candidates": candidate_rows,
        "selected_mutation": None if selected_row is None else selected_row["mutation"],
        "selected_strategy": selected_program.document(),
        "field_before_sha256": field_before,
        "field_after_sha256": field_after,
    }
    return selected_program, event


def _stream_metrics(
    *,
    initial_equity: float,
    equity: float,
    equity_curve: Sequence[float],
    realized_returns: Sequence[float],
    buy_hold_equity: float,
    turnover: float,
    cost_paid: float,
    trade_count: int,
    active_steps: int,
    winning_steps: int,
) -> dict[str, float]:
    mean_return = mean(realized_returns) if realized_returns else 0.0
    deviation = pstdev(realized_returns) if len(realized_returns) > 1 else 0.0
    arithmetic_return = sum(realized_returns)
    mean_absolute_return = (
        sum(abs(value) for value in realized_returns) / len(realized_returns)
        if realized_returns
        else 0.0
    )
    negative_returns = [value for value in realized_returns if value < 0.0]
    downside_deviation = (
        math.sqrt(sum(value * value for value in negative_returns) / len(negative_returns))
        if negative_returns
        else 0.0
    )
    ordered_returns = sorted(realized_returns)
    if ordered_returns:
        tail_size = max(1, int(len(ordered_returns) * 0.20))
        tail_threshold = ordered_returns[tail_size - 1]
        tail_returns = [value for value in ordered_returns if value <= tail_threshold]
        expected_shortfall = sum(tail_returns) / len(tail_returns)
    else:
        expected_shortfall = 0.0
    positive_returns = [value for value in realized_returns if value > 0.0]
    gross_profit = sum(positive_returns)
    gross_loss = sum(-value for value in negative_returns)
    profit_factor = gross_profit / gross_loss if gross_loss > 0.0 else 0.0
    metrics: dict[str, float] = {
        "net_return": equity / initial_equity - 1.0,
        "arithmetic_return": arithmetic_return,
        "mean_absolute_return": mean_absolute_return,
        "downside_deviation": downside_deviation,
        "expected_shortfall": expected_shortfall,
        "profit_factor": profit_factor,
        "average_win": gross_profit / len(positive_returns) if positive_returns else 0.0,
        "average_loss": gross_loss / len(negative_returns) if negative_returns else 0.0,
        "buy_hold_return": buy_hold_equity - 1.0,
        "max_drawdown": _max_drawdown(equity_curve),
        "trade_count": float(trade_count),
        "turnover": turnover,
        "cost_paid": cost_paid,
        "active_steps": float(active_steps),
        "winning_steps": float(winning_steps),
        "active_fraction": active_steps / max(1, len(realized_returns)),
        "hit_rate": winning_steps / max(1, active_steps),
        "sharpe": 0.0 if deviation <= 1.0e-15 else mean_return / deviation * math.sqrt(365.0 * 24.0),
        "final_equity": equity,
        "objective": 0.0,
    }
    metrics["objective"] = _objective(metrics)
    return metrics


def run_realtime_benchmark(
    bars: Sequence[MarketBar] | None = None,
    *,
    config: RealtimeConfig | None = None,
    field_memory: RefinementField | None = None,
    seed_program: StrategyProgram | None = None,
) -> dict[str, Any]:
    """Run the standard scenario as a causal one-bar-at-a-time market stream."""

    benchmark = config or RealtimeConfig()
    owned = _validate_bars(
        tuple(bars) if bars is not None else standard_scenario_bars(count=benchmark.bars)
    )
    if len(owned) != benchmark.bars:
        raise ValueError("bars length must equal RealtimeConfig.bars")
    field = field_memory or RefinementField()
    initial_field_sha256 = field.fingerprint()
    financial_teaching = teach_financial_math(field)
    program = seed_program or StrategyProgram.seed()
    initial_program = program.document()
    position = 0.0
    entry_price: float | None = None
    bars_in_position = 0
    equity = benchmark.replay.initial_equity
    equity_curve = [equity]
    realized_returns: list[float] = []
    turnover = 0.0
    cost_paid = 0.0
    trade_count = 0
    active_steps = 0
    winning_steps = 0
    buy_hold_equity = 1.0
    decisions: list[dict[str, Any]] = []
    adaptations: list[dict[str, Any]] = []
    live_start_index = benchmark.warmup_bars - 1

    for index in range(len(owned) - 1):
        current_bar = owned[index]
        following_bar = owned[index + 1]
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
            else _target_position(requested, program=program, replay=benchmark.replay)
        )
        change = abs(target - position)
        cost = change * benchmark.replay.transaction_cost
        realized = following_bar.close / current_bar.close - 1.0
        net = target * realized - cost
        equity *= 1.0 + net
        if not math.isfinite(equity) or equity <= 0.0:
            raise RuntimeError("realtime equity became nonpositive or nonfinite")
        if index >= live_start_index:
            trade_count += int(change > 0.0)
            turnover += change
            cost_paid += cost
            realized_returns.append(net)
            buy_hold_equity *= 1.0 + realized
            if target != 0.0:
                active_steps += 1
                if target * realized > 0.0:
                    winning_steps += 1
        if target == 0.0:
            entry_price = None
            bars_in_position = 0
        elif position == 0.0 or target != position:
            entry_price = following_bar.open
            bars_in_position = 1
        else:
            bars_in_position += 1
        position = target
        equity_curve.append(equity)
        decisions.append(
            {
                "bar_index": index,
                "next_bar_index": index + 1,
                "available_until": current_bar.timestamp,
                "execution_timestamp": following_bar.timestamp,
                "available_prefix_count": index + 1,
                "future_bars_excluded": len(owned) - index - 2,
                "lookahead_guard": "prefix-only-causal",
                "phase": "warmup" if index < live_start_index else "live",
                "strategy_sha256": program.program_sha256,
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
        should_adapt = (
            available_index > benchmark.warmup_bars
            and (available_index - benchmark.warmup_bars) % benchmark.adaptation_interval == 0
            and available_index < len(owned) - 1
        )
        if should_adapt:
            program, event = _adapt_field(
                owned,
                cutoff_index=available_index,
                program=program,
                field=field,
                config=benchmark,
                position=position,
            )
            adaptations.append(event)

    metrics = _stream_metrics(
        initial_equity=benchmark.replay.initial_equity,
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
    final_financial_selection = select_financial_composition(field, final_signature)
    final_composition = FINANCIAL_COMPOSITIONS[
        final_financial_selection["selected"]["composition_id"]
    ]
    final_financial_score = score_financial_composition(
        final_composition,
        metrics,
        benchmark.replay,
    )
    source_id = f"cassi-realtime:{owned[0].symbol}"
    events = tuple(
        bar.as_event(source_id=source_id, source_revision="standard-realtime.v1")
        for bar in owned
    )
    data_sha256 = digest_value([bar.as_dict() for bar in owned])
    event_root_sha256 = digest_value([event.as_dict() for event in events])
    final_field_sha256 = field.fingerprint()
    final_checkpoint = field.checkpoint_bytes()
    final_checkpoint_sha256 = hashlib.sha256(final_checkpoint).hexdigest()
    body: dict[str, Any] = {
        "schema": REALTIME_SCHEMA,
        "status": "PASS",
        "protocol": {
            "scenario_id": benchmark.scenario_id,
            "description": STANDARD_SCENARIO_DESCRIPTION,
            "causal_stream": "one bar arrives before each next-bar decision",
            "source_id": source_id,
            "source_revision": "standard-realtime.v1",
            "initial_field_mode": "inherited" if field_memory is not None else "fresh",
            "initial_strategy_sha256": initial_program["program_sha256"],
            "config": benchmark.as_dict(),
            "data_bars": len(owned),
            "live_start_index": live_start_index,
        },
        "data": {
            "symbol": owned[0].symbol,
            "bars": len(owned),
            "data_sha256": data_sha256,
            "event_schema": "cassi.market-event.v1",
            "event_root_sha256": event_root_sha256,
        },
        "financial_teaching": financial_teaching,
        "field": {
            "before_sha256": initial_field_sha256,
            "after_sha256": final_field_sha256,
            "checkpoint_sha256": final_checkpoint_sha256,
            "checkpoint_bytes": len(final_checkpoint),
            "checkpoint_hex": final_checkpoint.hex(),
            "adaptations": len(adaptations),
        },
        "initial_strategy": initial_program,
        "adaptations": adaptations,
        "stream": {
            "decisions": decisions,
            "metrics": metrics,
            "final_strategy": program.document(),
            "final_financial_selection": final_financial_selection,
            "final_financial_composition": final_composition.as_dict(),
            "final_financial_score": final_financial_score,
        },
    }
    body["content_sha256"] = digest_value(body)
    return body

def verify_realtime_benchmark(
    receipt: Mapping[str, Any],
    *,
    require_field_change: bool = True,
) -> dict[str, Any]:
    if receipt.get("schema") != REALTIME_SCHEMA:
        raise ValueError("realtime benchmark schema mismatch")
    if receipt.get("status") != "PASS":
        raise ValueError("realtime benchmark did not pass")
    protocol = receipt.get("protocol")
    data = receipt.get("data")
    stream = receipt.get("stream")
    adaptations = receipt.get("adaptations")
    if not isinstance(protocol, Mapping) or not isinstance(data, Mapping):
        raise ValueError("realtime protocol or data is missing")
    if not isinstance(stream, Mapping) or not isinstance(adaptations, list):
        raise ValueError("realtime stream or adaptations are missing")
    bars = int(protocol["config"]["bars"])
    decisions = stream.get("decisions")
    if not isinstance(decisions, list) or len(decisions) != bars - 1:
        raise ValueError("realtime decision count does not match the stream")
    for index, decision in enumerate(decisions):
        if decision.get("bar_index") != index or decision.get("next_bar_index") != index + 1:
            raise ValueError("realtime decision index is not causal")
        if decision.get("available_prefix_count") != index + 1:
            raise ValueError("realtime decision did not use the available prefix")
        if decision.get("future_bars_excluded") != bars - index - 2:
            raise ValueError("realtime future exclusion count is invalid")
        if decision.get("lookahead_guard") != "prefix-only-causal":
            raise ValueError("realtime lookahead guard is missing")
    for event in adaptations:
        cutoff = int(event["available_through_index"])
        if event["candidate_replay_end_index"] != cutoff:
            raise ValueError("adaptation replay consumed bars beyond its cutoff")
        if event["future_bars_excluded"] != bars - cutoff - 1:
            raise ValueError("adaptation future exclusion count is invalid")
        if event["lookahead_guard"] != "prefix-only-causal":
            raise ValueError("adaptation lookahead guard is missing")
    teaching = receipt.get("financial_teaching")
    if not isinstance(teaching, Mapping) or teaching.get("algorithm_count") != len(FINANCIAL_SKILL_IDS):
        raise ValueError("financial curriculum was not taught into the field")
    field = receipt.get("field")
    if (
        not isinstance(field, Mapping)
        or require_field_change
        and field.get("before_sha256") == field.get("after_sha256")
    ):
        raise ValueError("realtime field never changed")
    checkpoint_hex = field.get("checkpoint_hex")
    if not isinstance(checkpoint_hex, str):
        raise ValueError("realtime field checkpoint is missing")
    try:
        checkpoint = bytes.fromhex(checkpoint_hex)
    except ValueError as exc:
        raise ValueError("realtime field checkpoint is not hex") from exc
    if (
        len(checkpoint) != field.get("checkpoint_bytes")
        or hashlib.sha256(checkpoint).hexdigest() != field.get("checkpoint_sha256")
    ):
        raise ValueError("realtime field checkpoint digest mismatch")
    body = dict(receipt)
    stated = body.pop("content_sha256", None)
    if not isinstance(stated, str) or digest_value(body) != stated:
        raise ValueError("realtime content digest mismatch")
    return {
        "status": "PASS",
        "content_sha256": stated,
        "decisions": len(decisions),
        "adaptations": len(adaptations),
        "final_equity": stream["metrics"]["final_equity"],
    }
def _strategy_from_document(document: Mapping[str, Any]) -> StrategyProgram:
    return StrategyProgram(
        strategy_id=str(document["strategy_id"]),
        source=str(document["source"]),
        parameters=dict(document["parameters"]),
        family=str(document["family"]),
        parent_id=document.get("parent_id"),
        mutation=str(document.get("mutation", "seed")),
    )


def run_historical_external_validation(
    bars: Sequence[MarketBar],
    *,
    config: RealtimeConfig | None = None,
    max_windows: int = 5,
) -> dict[str, Any]:
    """Calibrate on RT-1, then run independent historical realtime windows."""

    benchmark = config or RealtimeConfig()
    owned = _validate_bars(tuple(bars))
    if max_windows < 1:
        raise ValueError("max_windows must be positive")
    required = benchmark.bars * max_windows
    if len(owned) < required:
        raise ValueError(f"historical validation requires at least {required} bars")
    calibration = run_realtime_benchmark(config=benchmark)
    calibration_checkpoint = bytes.fromhex(calibration["field"]["checkpoint_hex"])
    calibration_program = _strategy_from_document(calibration["stream"]["final_strategy"])
    windows: list[dict[str, Any]] = []
    for window_index in range(max_windows):
        start = window_index * benchmark.bars
        segment = owned[start : start + benchmark.bars]
        field = RefinementField.restore(calibration_checkpoint)
        window_receipt = run_realtime_benchmark(
            segment,
            config=benchmark,
            field_memory=field,
            seed_program=calibration_program,
        )
        windows.append(
            {
                "window_index": window_index,
                "start_index": start,
                "end_index": start + benchmark.bars - 1,
                "timestamp_start": segment[0].timestamp,
                "timestamp_end": segment[-1].timestamp,
                "receipt": window_receipt,
            }
        )
    body: dict[str, Any] = {
        "schema": "cassi.trading-realtime-external-validation.v1",
        "status": "PASS",
        "protocol": {
            "calibration_scenario": STANDARD_SCENARIO_ID,
            "calibration_stream": "synthetic RT-1-mixed-hourly",
            "external_stream": "closed historical OHLCV windows",
            "source_id": f"cassi-realtime-external:{owned[0].symbol}",
            "source_revision": "standard-realtime.v1",
            "source_bars": len(owned),
            "window_bars": benchmark.bars,
            "window_count": max_windows,
            "config": benchmark.as_dict(),
            "calibration_content_sha256": calibration["content_sha256"],
            "calibration_field_sha256": calibration["field"]["after_sha256"],
            "calibration_program_sha256": calibration["stream"]["final_strategy"][
                "program_sha256"
            ],
        },
        "data": {
            "symbol": owned[0].symbol,
            "data_sha256": digest_value([bar.as_dict() for bar in owned]),
        },
        "calibration": calibration,
        "windows": windows,
    }
    body["content_sha256"] = digest_value(body)
    return body


def verify_historical_external_validation(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != "cassi.trading-realtime-external-validation.v1":
        raise ValueError("external validation schema mismatch")
    if receipt.get("status") != "PASS":
        raise ValueError("external validation did not pass")
    protocol = receipt.get("protocol")
    windows = receipt.get("windows")
    calibration = receipt.get("calibration")
    if (
        not isinstance(protocol, Mapping)
        or not isinstance(windows, list)
        or not isinstance(calibration, Mapping)
    ):
        raise ValueError("external validation receipt is incomplete")
    calibration_verification = verify_realtime_benchmark(calibration)
    if calibration_verification["content_sha256"] != protocol["calibration_content_sha256"]:
        raise ValueError("calibration receipt digest mismatch")
    if len(windows) != protocol["window_count"]:
        raise ValueError("external validation window count mismatch")
    window_verifications = []
    for index, row in enumerate(windows):
        if row.get("window_index") != index:
            raise ValueError("external validation windows are not ordered")
        window = row.get("receipt")
        if not isinstance(window, Mapping):
            raise ValueError("external validation window receipt is missing")
        verification = verify_realtime_benchmark(window, require_field_change=False)
        if window["protocol"].get("initial_field_mode") != "inherited":
            raise ValueError("external window did not inherit the calibration field")
        if window["initial_strategy"]["program_sha256"] != protocol["calibration_program_sha256"]:
            raise ValueError("external window did not inherit the calibration strategy")
        window_verifications.append(verification)
    body = dict(receipt)
    stated = body.pop("content_sha256", None)
    if not isinstance(stated, str) or digest_value(body) != stated:
        raise ValueError("external validation content digest mismatch")
    return {
        "status": "PASS",
        "content_sha256": stated,
        "calibration": calibration_verification,
        "windows": window_verifications,
    }




def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, help="closed historical OHLCV CSV for external validation")
    parser.add_argument("--symbol", default=None, help="symbol to select from a multi-symbol CSV")
    parser.add_argument("--external-windows", type=int, default=5)
    parser.add_argument("--bars", type=int, default=384)
    parser.add_argument("--warmup-bars", type=int, default=48)
    parser.add_argument("--adaptation-interval", type=int, default=24)
    parser.add_argument("--max-candidates", type=int, default=4)
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--out-dir", type=Path, default=Path("_diag/trading-realtime-benchmark"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = RealtimeConfig(
        bars=args.bars,
        warmup_bars=args.warmup_bars,
        adaptation_interval=args.adaptation_interval,
        max_candidates=args.max_candidates,
        replay=ReplayConfig(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps),
    )
    if args.csv is None:
        receipt = run_realtime_benchmark(config=config)
        verification = verify_realtime_benchmark(receipt)
        filename = "realtime_benchmark.json"
    else:
        bars = load_bars_csv(args.csv, symbol=args.symbol)
        receipt = run_historical_external_validation(
            bars,
            config=config,
            max_windows=args.external_windows,
        )
        verification = verify_historical_external_validation(receipt)
        filename = "external_realtime_validation.json"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / filename
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "status": verification["status"],
        "receipt": str(path),
        "content_sha256": verification["content_sha256"],
    }
    if args.csv is None:
        summary.update(
            {
                "decisions": verification["decisions"],
                "adaptations": verification["adaptations"],
                "final_equity": verification["final_equity"],
            }
        )
    else:
        summary["windows"] = len(verification["windows"])
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
