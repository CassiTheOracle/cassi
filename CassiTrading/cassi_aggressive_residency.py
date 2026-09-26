#!/usr/bin/env python3
"""Train one field-owned aggressive trader in a causal persistent market residency."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Mapping, Sequence

from cassi_trading_foundry import (
    MarketBar,
    CapacityError,
    RefinementField,
    ReplayConfig,
    StrategyProgram,
    _features,
    _max_drawdown,
    content_digest_matches,
    digest_value,
    load_bars_csv,
)


AGGRESSIVE_RESIDENCY_SCHEMA = "cassi.trading-aggressive-residency.v1"
RUNTIME_STATE_SCHEMA = "cassi.trading-aggressive-runtime-state.v1"
ACTION_LEVELS = (-1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0)


def _utc(value: str) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    result = datetime.fromisoformat(text)
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _temporal_epoch(timestamp: str, index: int, epoch_days: int) -> int:
    try:
        seconds = _utc(timestamp).timestamp()
    except ValueError:
        return index // (epoch_days * 24)
    return int(seconds // (epoch_days * 86_400))

def _atomic_write(path: Path, blob: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(blob)
    os.replace(temporary, path)


def _action_id(target: float) -> str:
    return f"target:{target:+.2f}"


def _program_from_document(document: Mapping[str, Any]) -> StrategyProgram:
    return StrategyProgram(
        strategy_id=str(document["strategy_id"]),
        source=str(document["source"]),
        parameters=dict(document["parameters"]),
        family=str(document["family"]),
        parent_id=document.get("parent_id"),
        mutation=str(document.get("mutation", "seed")),
    )


@dataclass(frozen=True, slots=True)
class AggressiveResidencyConfig:
    warmup_bars: int = 720
    decision_interval: int = 4
    lesson_interval: int = 24
    outcome_horizon: int = 12
    fee_bps: float = 10.0
    spread_bps: float = 5.0
    slippage_bps: float = 5.0
    short_funding_bps_daily: float = 1.0
    initial_equity: float = 1.0
    max_position: float = 1.0
    allow_short: bool = True
    stop_loss: float = 0.05
    max_hold_bars: int = 168
    soft_drawdown: float = 0.20
    hard_drawdown: float = 0.35
    cooldown_bars: int = 168
    risk_penalty: float = 0.75
    minimum_action_edge: float = 0.0025
    purposeful_replay_episodes: int = 384
    stress_episodes: int = 192
    stress_cost_multiplier: float = 3.0
    regime_epoch_days: int = 90
    regime_fresh_bars: int = 24
    regime_established_bars: int = 168
    confirmation_repeats: int = 4
    contradiction_repeats: int = 4
    downside_penalty: float = 0.35

    def __post_init__(self) -> None:
        integers = {
            "warmup_bars": self.warmup_bars,
            "decision_interval": self.decision_interval,
            "lesson_interval": self.lesson_interval,
            "outcome_horizon": self.outcome_horizon,
            "max_hold_bars": self.max_hold_bars,
            "cooldown_bars": self.cooldown_bars,
            "purposeful_replay_episodes": self.purposeful_replay_episodes,
            "stress_episodes": self.stress_episodes,
            "regime_epoch_days": self.regime_epoch_days,
            "regime_fresh_bars": self.regime_fresh_bars,
            "regime_established_bars": self.regime_established_bars,
            "confirmation_repeats": self.confirmation_repeats,
            "contradiction_repeats": self.contradiction_repeats,
        }
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in integers.values()):
            raise ValueError("aggressive residency integer bounds must be positive")
        if self.warmup_bars <= 32 or self.outcome_horizon >= self.warmup_bars:
            raise ValueError("warmup must exceed the outcome horizon and feature history")
        numbers = {
            "fee_bps": self.fee_bps,
            "spread_bps": self.spread_bps,
            "slippage_bps": self.slippage_bps,
            "short_funding_bps_daily": self.short_funding_bps_daily,
            "initial_equity": self.initial_equity,
            "max_position": self.max_position,
            "stop_loss": self.stop_loss,
            "soft_drawdown": self.soft_drawdown,
            "hard_drawdown": self.hard_drawdown,
            "risk_penalty": self.risk_penalty,
            "minimum_action_edge": self.minimum_action_edge,
            "stress_cost_multiplier": self.stress_cost_multiplier,
            "downside_penalty": self.downside_penalty,
        }
        if any(not math.isfinite(value) or value < 0.0 for value in numbers.values()):
            raise ValueError("aggressive residency numeric bounds must be finite and nonnegative")
        if self.initial_equity <= 0.0 or not 0.0 < self.max_position <= 1.0:
            raise ValueError("equity must be positive and max_position must be in (0, 1]")
        if not 0.0 < self.soft_drawdown < self.hard_drawdown < 1.0:
            raise ValueError("drawdown bounds must satisfy 0 < soft < hard < 1")
        if self.stop_loss <= 0.0 or self.stress_cost_multiplier < 1.0:
            raise ValueError("stop loss and stress multiplier are outside their bounds")
        if self.regime_fresh_bars >= self.regime_established_bars:
            raise ValueError("regime fresh bars must be below established bars")

    @property
    def replay(self) -> ReplayConfig:
        return ReplayConfig(
            fee_bps=self.fee_bps,
            slippage_bps=self.slippage_bps + self.spread_bps,
            initial_equity=self.initial_equity,
            max_position=self.max_position,
            timeframe_hours=1.0,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "warmup_bars": self.warmup_bars,
            "decision_interval": self.decision_interval,
            "lesson_interval": self.lesson_interval,
            "outcome_horizon": self.outcome_horizon,
            "fee_bps": self.fee_bps,
            "spread_bps": self.spread_bps,
            "slippage_bps": self.slippage_bps,
            "short_funding_bps_daily": self.short_funding_bps_daily,
            "initial_equity": self.initial_equity,
            "max_position": self.max_position,
            "allow_short": self.allow_short,
            "stop_loss": self.stop_loss,
            "max_hold_bars": self.max_hold_bars,
            "soft_drawdown": self.soft_drawdown,
            "hard_drawdown": self.hard_drawdown,
            "cooldown_bars": self.cooldown_bars,
            "risk_penalty": self.risk_penalty,
            "minimum_action_edge": self.minimum_action_edge,
            "purposeful_replay_episodes": self.purposeful_replay_episodes,
            "stress_episodes": self.stress_episodes,
            "stress_cost_multiplier": self.stress_cost_multiplier,
            "regime_epoch_days": self.regime_epoch_days,
            "regime_fresh_bars": self.regime_fresh_bars,
            "regime_established_bars": self.regime_established_bars,
            "confirmation_repeats": self.confirmation_repeats,
            "contradiction_repeats": self.contradiction_repeats,
            "downside_penalty": self.downside_penalty,
        }


@dataclass(slots=True)
class AccountState:
    equity: float
    peak_equity: float
    position: float = 0.0
    entry_price: float | None = None
    bars_in_position: int = 0
    cooldown_remaining: int = 0

    @property
    def drawdown(self) -> float:
        return 0.0 if self.peak_equity <= 0.0 else 1.0 - self.equity / self.peak_equity

    def document(self) -> dict[str, Any]:
        return {
            "equity": self.equity,
            "peak_equity": self.peak_equity,
            "position": self.position,
            "entry_price": self.entry_price,
            "bars_in_position": self.bars_in_position,
            "cooldown_remaining": self.cooldown_remaining,
            "drawdown": self.drawdown,
        }


def _clone_account(value: AccountState | Mapping[str, Any] | None, equity: float) -> AccountState:
    if value is None:
        return AccountState(equity, equity)
    document = value.document() if isinstance(value, AccountState) else value
    return AccountState(
        equity=float(document["equity"]),
        peak_equity=float(document["peak_equity"]),
        position=float(document.get("position", 0.0)),
        entry_price=(
            None
            if document.get("entry_price") is None
            else float(document["entry_price"])
        ),
        bars_in_position=int(document.get("bars_in_position", 0)),
        cooldown_remaining=int(document.get("cooldown_remaining", 0)),
    )

def load_fine_context(path: Path | None) -> dict[str, dict[str, float]]:
    """Aggregate genuine five-minute bars into completed-hour microstructure context."""

    if path is None:
        return {}
    rows = load_bars_csv(path, symbol="BTC-USD")
    grouped: dict[str, list[MarketBar]] = {}
    for bar in rows:
        start = _utc(bar.timestamp).replace(minute=0, second=0, microsecond=0)
        key = start.isoformat().replace("+00:00", "Z")
        grouped.setdefault(key, []).append(bar)
    result: dict[str, dict[str, float]] = {}
    for key, members in grouped.items():
        ordered = sorted(members, key=lambda bar: bar.timestamp)
        if len(ordered) != 12:
            continue
        changes = [
            ordered[index].close / ordered[index - 1].close - 1.0
            for index in range(1, len(ordered))
        ]
        result[key] = {
            "return": ordered[-1].close / ordered[0].open - 1.0,
            "volatility": sum(abs(value) for value in changes) / max(1, len(changes)),
            "volume": sum(bar.volume for bar in ordered),
            "bars": float(len(ordered)),
        }
    return result


def _direction(value: float, threshold: float) -> str:
    if value > threshold:
        return "up"
    if value < -threshold:
        return "down"
    return "flat"


def _volatility_bucket(value: float) -> str:
    if value < 0.0025:
        return "quiet"
    if value < 0.0075:
        return "normal"
    return "violent"

def _regime_descriptor(bars: Sequence[MarketBar], index: int) -> str:
    start = max(1, index - 23)
    changes = [
        bars[cursor].close / bars[cursor - 1].close - 1.0
        for cursor in range(start, index + 1)
    ]
    volatility = pstdev(changes) if len(changes) > 1 else 0.0
    return_24h = bars[index].close / bars[max(0, index - 24)].close - 1.0
    return (
        f"d1={_direction(return_24h, 0.0125)}:"
        f"vol={_volatility_bucket(volatility)}"
    )


def _regime_transition_descriptor(
    bars: Sequence[MarketBar],
    index: int,
    *,
    horizon_bars: int = 24,
) -> str:
    """Name the causal regime flow from one completed daily window to the next."""

    prior = _regime_descriptor(bars, max(0, index - horizon_bars))
    current = _regime_descriptor(bars, index)
    prior_parts = dict(part.split("=", 1) for part in prior.split(":"))
    current_parts = dict(part.split("=", 1) for part in current.split(":"))
    return (
        f"d1={prior_parts['d1']}>{current_parts['d1']}:"
        f"vol={prior_parts['vol']}>{current_parts['vol']}"
    )


def _coherence_acceleration_descriptor(
    bars: Sequence[MarketBar],
    index: int,
    *,
    horizon_bars: int = 24,
) -> str:
    """Classify whether a completed regime flow is building or resolving."""

    prior_index = max(0, index - horizon_bars)
    prior_return = (
        bars[prior_index].close
        / bars[max(0, prior_index - horizon_bars)].close
        - 1.0
    )
    current_return = bars[index].close / bars[prior_index].close - 1.0
    prior = dict(
        part.split("=", 1)
        for part in _regime_descriptor(bars, prior_index).split(":")
    )
    current = dict(
        part.split("=", 1)
        for part in _regime_descriptor(bars, index).split(":")
    )
    prior_direction = prior["d1"]
    current_direction = current["d1"]
    if prior_direction == "down" and current_direction == "up":
        coherence = "recovering"
    elif prior_direction == "up" and current_direction == "down":
        coherence = "breaking"
    elif prior_direction == current_direction and current_direction != "flat":
        magnitude_ratio = abs(current_return) / max(abs(prior_return), 1.0e-12)
        coherence = (
            "strengthening"
            if magnitude_ratio >= 1.25
            else "exhausting"
            if magnitude_ratio <= 0.75
            else "sustaining"
        )
    elif prior_direction == "flat" and current_direction != "flat":
        coherence = "emerging"
    elif prior_direction != "flat" and current_direction == "flat":
        coherence = "settling"
    else:
        coherence = "reorganizing"
    volatility_order = {"quiet": 0, "normal": 1, "violent": 2}
    volatility_delta = (
        volatility_order[current["vol"]] - volatility_order[prior["vol"]]
    )
    volatility_flow = (
        "expanding"
        if volatility_delta > 0
        else "contracting"
        if volatility_delta < 0
        else "steady"
    )
    return f"coherence={coherence}:vol={volatility_flow}"


def _positive_authority_descriptor(
    *,
    hourly_direction: str,
    four_hour_direction: str,
    daily_direction: str,
    trend_direction: str,
    volatility: str,
    acceleration: str,
) -> str:
    """Name a causal directional configuration eligible for constructive authority."""

    coherent_directions = (
        hourly_direction,
        four_hour_direction,
        daily_direction,
        trend_direction,
    )
    flow = acceleration.split(":", 1)[0].removeprefix("coherence=")
    direction = daily_direction
    if (
        direction in {"up", "down"}
        and all(value == direction for value in coherent_directions)
        and flow in {"strengthening", "recovering", "emerging", "sustaining"}
    ):
        return f"{direction}-coherent:{flow}:vol={volatility}"
    return f"unresolved:vol={volatility}"


def _mature_opportunity_descriptor(
    bars: Sequence[MarketBar],
    index: int,
    *,
    hourly_direction: str,
    four_hour_direction: str,
    daily_direction: str,
    trend_direction: str,
    acceleration: str,
) -> str:
    """Describe a persistent, pullback-contained directional opportunity."""

    direction = daily_direction
    if index < 72:
        return "unresolved"
    directions = (
        hourly_direction,
        four_hour_direction,
        daily_direction,
        trend_direction,
    )
    flow = acceleration.split(":", 1)[0].removeprefix("coherence=")
    returns = tuple(
        bars[index].close / bars[index - horizon].close - 1.0
        for horizon in (24, 48, 72)
    )
    persistence = all(
        _direction(value, 0.0125) == direction
        for value in returns
    )
    closes = tuple(bar.close for bar in bars[index - 72 : index + 1])
    adverse = (
        1.0 - bars[index].close / max(closes)
        if direction == "up"
        else bars[index].close / min(closes) - 1.0
    )
    excursion = (
        "contained"
        if adverse <= 0.015
        else "recoverable"
        if adverse <= 0.04
        else "deep"
    )
    if (
        direction in {"up", "down"}
        and all(value == direction for value in directions)
        and persistence
        and flow in {"strengthening", "recovering", "emerging", "sustaining"}
        and excursion in {"contained", "recoverable"}
    ):
        return f"{direction}:persistent:{excursion}"
    return "unresolved"


def _regime_timeline(
    bars: Sequence[MarketBar],
    *,
    epoch_days: int = 90,
) -> tuple[dict[str, Any], ...]:
    result: list[dict[str, Any]] = []
    previous = ""
    age = 0
    for index, bar in enumerate(bars):
        regime = _regime_descriptor(bars, index)
        age = age + 1 if regime == previous else 1
        epoch = _temporal_epoch(bar.timestamp, index, epoch_days)
        result.append({"regime": regime, "age_bars": age, "epoch_90d": epoch})
        previous = regime
    return tuple(result)


def _regime_age_bucket(age_bars: int, config: AggressiveResidencyConfig) -> str:
    if age_bars <= config.regime_fresh_bars:
        return "fresh"
    if age_bars <= config.regime_established_bars:
        return "established"
    return "mature"


def _market_context(
    bars: Sequence[MarketBar],
    index: int,
    *,
    program: StrategyProgram,
    account: AccountState,
    fine_context: Mapping[str, Mapping[str, float]],
    config: AggressiveResidencyConfig | None = None,
    regime_timeline: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    features = _features(
        bars,
        index,
        program,
        position=math.copysign(1.0, account.position) if account.position != 0.0 else 0.0,
        entry_price=account.entry_price,
        bars_in_position=account.bars_in_position,
    )
    close = bars[index].close
    return_4h = close / bars[index - 4].close - 1.0 if index >= 4 else 0.0
    return_24h = close / bars[index - 24].close - 1.0 if index >= 24 else 0.0
    volume_start = max(0, index - 23)
    average_volume = mean(bar.volume for bar in bars[volume_start : index + 1])
    volume_ratio = bars[index].volume / average_volume if average_volume > 0.0 else 1.0
    fine = fine_context.get(bars[index].timestamp)
    fine_direction = "missing" if fine is None else _direction(float(fine["return"]), 0.001)
    hourly_direction = _direction(float(features["momentum"]), 0.0025)
    trend_direction = _direction(float(features["trend"]), 0.0035)
    four_hour_direction = _direction(return_4h, 0.005)
    daily_direction = _direction(return_24h, 0.0125)
    volatility = _volatility_bucket(float(features["volatility"]))
    volume = "high" if volume_ratio >= 1.5 else "low" if volume_ratio <= 0.7 else "normal"
    position = "long" if account.position > 0.0 else "short" if account.position < 0.0 else "flat"
    drawdown = "pressed" if account.drawdown >= 0.10 else "calm"
    settings = config or AggressiveResidencyConfig()
    regime_row = (
        dict(regime_timeline[index])
        if regime_timeline is not None
        else dict(_regime_timeline(bars, epoch_days=settings.regime_epoch_days)[index])
    )
    regime = str(regime_row["regime"])
    regime_age_bars = int(regime_row["age_bars"])
    regime_age = _regime_age_bucket(regime_age_bars, settings)
    era = f"e{int(regime_row['epoch_90d'])}"
    acceleration = _coherence_acceleration_descriptor(bars, index)
    transition = _regime_transition_descriptor(bars, index)
    regime_parts = dict(part.split("=", 1) for part in regime.split(":"))
    current_epoch = int(regime_row["epoch_90d"])
    opportunity = _positive_authority_descriptor(
        hourly_direction=hourly_direction,
        four_hour_direction=four_hour_direction,
        daily_direction=daily_direction,
        trend_direction=trend_direction,
        volatility=volatility,
        acceleration=acceleration,
    )
    mature_opportunity = _mature_opportunity_descriptor(
        bars,
        index,
        hourly_direction=hourly_direction,
        four_hour_direction=four_hour_direction,
        daily_direction=daily_direction,
        trend_direction=trend_direction,
        acceleration=acceleration,
    )

    def relation_rows(epoch: int, temporal_offset: int) -> tuple[dict[str, Any], ...]:
        temporal_weight = 1.0 if temporal_offset == 0 else 0.55
        prefix = f"market:v3:era=e{epoch}:position={position}"
        rows = (
            {
                "context_id": f"{prefix}:relation=regime:{regime}",
                "relation": "regime",
                "temporal_offset": temporal_offset,
                "proximity": temporal_weight,
            },
            {
                "context_id": f"{prefix}:relation=direction:d1={regime_parts['d1']}",
                "relation": "direction",
                "temporal_offset": temporal_offset,
                "proximity": 0.70 * temporal_weight,
            },
            {
                "context_id": f"{prefix}:relation=transition:{transition}",
                "relation": "transition",
                "temporal_offset": temporal_offset,
                "proximity": 0.85 * temporal_weight,
            },
            {
                "context_id": f"{prefix}:relation=acceleration:{acceleration}",
                "relation": "acceleration",
                "temporal_offset": temporal_offset,
                "proximity": 0.75 * temporal_weight,
            },
            {
                "context_id": (
                    f"market:v4:era=e{epoch}:relation=opportunity:{opportunity}"
                ),
                "relation": "opportunity",
                "temporal_offset": temporal_offset,
                "proximity": 0.95 * temporal_weight,
            },
        )
        if temporal_offset == 0:
            rows += (
                {
                    "context_id": (
                        "market:v5:relation=mature-opportunity:"
                        f"{mature_opportunity}"
                    ),
                    "relation": "mature-opportunity",
                    "temporal_offset": temporal_offset,
                    "proximity": 0.90,
                },
            )
        return rows

    learning_contexts = relation_rows(current_epoch, 0)
    relational_contexts = learning_contexts + relation_rows(current_epoch - 1, 1)
    return {
        "context_ids": tuple(row["context_id"] for row in relational_contexts),
        "relational_contexts": relational_contexts,
        "learning_contexts": learning_contexts,
        "learning_context_ids": tuple(row["context_id"] for row in learning_contexts),
        "features": {
            "hourly_direction": hourly_direction,
            "trend_direction": trend_direction,
            "four_hour_direction": four_hour_direction,
            "daily_direction": daily_direction,
            "volatility_bucket": volatility,
            "volume_bucket": volume,
            "fine_direction": fine_direction,
            "position_bucket": position,
            "drawdown_bucket": drawdown,
            "regime": regime,
            "regime_age_bucket": regime_age,
            "regime_age_bars": regime_age_bars,
            "era": era,
            "trend": float(features["trend"]),
            "momentum": float(features["momentum"]),
            "transition": transition,
            "volatility": float(features["volatility"]),
            "mature_opportunity": mature_opportunity,
            "return_4h": return_4h,
            "return_24h": return_24h,
            "volume_ratio": volume_ratio,
            "acceleration": acceleration,
            "opportunity": opportunity,
        },
        "program_features": features,
    }


def _candidate_levels(config: AggressiveResidencyConfig) -> tuple[float, ...]:
    return tuple(
        level
        for level in ACTION_LEVELS
        if abs(level) <= config.max_position and (config.allow_short or level >= 0.0)
    )


def _choose_target(
    field: RefinementField,
    relational_contexts: Sequence[Mapping[str, Any]],
    *,
    requested: int,
    account: AccountState,
    config: AggressiveResidencyConfig,
    prediction_cache: dict[tuple[Any, ...], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    desired = 0.25 * requested if requested != 0 else account.position
    field_identity = field.fingerprint()
    context_key = tuple(
        (
            str(row["context_id"]),
            str(row["relation"]),
            int(row["temporal_offset"]),
            float(row["proximity"]),
        )
        for row in relational_contexts
    )
    rows = []
    for target in _candidate_levels(config):
        cache_key = (field_identity, context_key, _action_id(target))
        prediction = (
            prediction_cache[cache_key]
            if prediction_cache is not None and cache_key in prediction_cache
            else field.predict_market_action_relational(
                relational_contexts,
                _action_id(target),
            )
        )
        if prediction_cache is not None:
            prediction_cache[cache_key] = prediction
        rows.append({"target": target, "prediction": prediction})
    promoted = [row for row in rows if row["prediction"].get("outcome") == "promote"]
    rejected = [row for row in rows if row["prediction"].get("outcome") == "reject"]
    field_strength = 0.0
    if promoted:
        selected = max(
            promoted,
            key=lambda row: (
                float(row["prediction"]["strength"]),
                float(row["prediction"].get("score") or 0.0),
                float(row["prediction"].get("margin") or 0.0),
                float(row["target"]) * requested,
                -abs(float(row["target"]) - desired),
            ),
        )
        field_strength = float(selected["prediction"]["strength"])
        field_target = float(selected["target"])
        target = desired + field_strength * (field_target - desired)
        authority = "field-graded-promote"
    else:
        desired_level = min(
            _candidate_levels(config),
            key=lambda value: (abs(value - desired), abs(value)),
        )
        rejected_by_target = {float(row["target"]): row for row in rejected}
        rejected_row = rejected_by_target.get(desired_level)
        available = [
            target
            for target in _candidate_levels(config)
            if target not in rejected_by_target
        ]
        if rejected_row is not None:
            field_strength = float(rejected_row["prediction"]["strength"])
            alternative = (
                min(available, key=lambda value: (abs(value - desired), abs(value)))
                if available
                else 0.0
            )
            target = desired + field_strength * (alternative - desired)
            authority = "field-graded-avoidance"
        else:
            target = desired
            authority = "bounded-exploration"

    override: str | None = None
    if account.cooldown_remaining > 0:
        target, override = 0.0, "account-cooldown"
    elif account.drawdown >= config.hard_drawdown:
        target, override = 0.0, "hard-drawdown-stop"
    elif account.drawdown >= config.soft_drawdown and abs(target) > 0.5:
        target, override = math.copysign(0.5, target), "soft-drawdown-cap"
    elif account.bars_in_position >= config.max_hold_bars:
        target, override = 0.0, "maximum-hold-exit"
    target = max(-config.max_position, min(config.max_position, target))
    if not config.allow_short:
        target = max(0.0, target)
    return {
        "target": target,
        "authority": authority,
        "field_strength": field_strength,
        "safety_override": override,
        "field_rows": rows,
        "supported_promote_count": len(promoted),
        "supported_reject_count": len(rejected),
    }



def _execution_cost(
    change: float,
    *,
    volatility: float,
    config: AggressiveResidencyConfig,
    multiplier: float = 1.0,
) -> float:
    volatility_multiplier = min(4.0, 1.0 + volatility / 0.01)
    bps = config.fee_bps + config.spread_bps + config.slippage_bps * volatility_multiplier
    return change * bps * multiplier / 10_000.0


def _score_action(
    bars: Sequence[MarketBar],
    index: int,
    target: float,
    *,
    current_position: float,
    volatility: float,
    config: AggressiveResidencyConfig,
    cost_multiplier: float = 1.0,
) -> dict[str, float]:
    end = min(len(bars) - 1, index + config.outcome_horizon)
    fill = bars[index + 1].open
    changes = abs(target - current_position) + abs(target)
    cost = _execution_cost(
        changes,
        volatility=volatility,
        config=config,
        multiplier=cost_multiplier,
    )
    funding_per_bar = (
        abs(min(target, 0.0))
        * config.short_funding_bps_daily
        / 10_000.0
        / 24.0
    )
    path = [1.0]
    step_returns: list[float] = []
    previous_price = fill
    maximum_adverse = 0.0
    for offset, bar in enumerate(bars[index + 1 : end + 1], start=1):
        step_return = target * (bar.close / previous_price - 1.0) - funding_per_bar
        step_returns.append(step_return)
        marked = (
            1.0
            + target * (bar.close / fill - 1.0)
            - cost
            - funding_per_bar * offset
        )
        path.append(max(1.0e-12, marked))
        if target > 0.0:
            maximum_adverse = max(
                maximum_adverse,
                -(bar.low / fill - 1.0) * abs(target),
            )
        elif target < 0.0:
            maximum_adverse = max(
                maximum_adverse,
                (bar.high / fill - 1.0) * abs(target),
            )
        previous_price = bar.close
    funding = funding_per_bar * (end - index)
    net = path[-1] - 1.0
    compounded_log_growth = math.log(path[-1])
    path_drawdown = _max_drawdown(path)
    downside = [min(0.0, value) for value in step_returns]
    downside_deviation = (
        math.sqrt(mean(value * value for value in downside)) if downside else 0.0
    )
    objective = (
        compounded_log_growth
        - config.risk_penalty * path_drawdown
        - config.downside_penalty
        * downside_deviation
        * math.sqrt(max(1, len(step_returns)))
    )
    return {
        "target": target,
        "net_return": net,
        "compounded_log_growth": compounded_log_growth,
        "path_max_drawdown": path_drawdown,
        "downside_deviation": downside_deviation,
        "maximum_adverse_excursion": maximum_adverse,
        "cost": cost,
        "funding": funding,
        "objective": objective,
    }


def _lesson_outcome(score: Mapping[str, float], config: AggressiveResidencyConfig) -> str:
    objective = float(score["objective"])
    if float(score["maximum_adverse_excursion"]) >= config.stop_loss:
        return "reject"
    if objective >= config.minimum_action_edge:
        return "promote"
    if objective <= -config.minimum_action_edge:
        return "reject"
    return "uncertain"


def _learn_episode(
    field: RefinementField,
    episode: Mapping[str, Any],
    *,
    config: AggressiveResidencyConfig,
    cost_multiplier: float = 1.0,
) -> tuple[RefinementField, dict[str, Any]]:
    bars = episode["bars"]
    index = int(episode["index"])
    learning_contexts = tuple(dict(row) for row in episode["learning_contexts"])
    learning_context_ids = tuple(
        str(row["context_id"]) for row in learning_contexts
    )
    scores = [
        _score_action(
            bars,
            index,
            target,
            current_position=float(episode["position"]),
            volatility=float(episode["volatility"]),
            config=config,
            cost_multiplier=cost_multiplier,
        )
        for target in _candidate_levels(config)
    ]
    best = max(scores, key=lambda row: (row["objective"], abs(row["target"])))
    worst = min(scores, key=lambda row: (row["objective"], -abs(row["target"])))
    chosen = min(scores, key=lambda row: abs(row["target"] - float(episode["target"])))
    teaching = {float(row["target"]): row for row in (chosen, best)}
    admissions = []
    before = field.fingerprint()
    if not learning_context_ids:
        raise ValueError("field lesson requires relational learning contexts")
    for target, score in teaching.items():
        checkpoint = field.checkpoint_bytes()
        outcome = _lesson_outcome(score, config)
        selection_action = _action_id(target)
        prior_prediction = field.predict_market_action_relational(
            learning_contexts,
            selection_action,
        )
        memory_action = (
            f"consequence:uncertain:{selection_action}"
            if outcome == "uncertain"
            else selection_action
        )
        if outcome == "promote":
            repeats = config.confirmation_repeats
            memory_role = (
                "confirmation"
                if prior_prediction.get("outcome") == "promote"
                else "promotion"
            )
        elif outcome == "reject":
            repeats = config.contradiction_repeats
            memory_role = (
                "contradiction"
                if prior_prediction.get("outcome") == "promote"
                else "rejection"
            )
        else:
            repeats = 1
            memory_role = "uncertain-consequence"
        try:
            receipt = field.learn_market_action(
                learning_context_ids,
                memory_action,
                outcome,
                repeats=repeats,
            )
        except CapacityError as exc:
            field = RefinementField.restore(checkpoint)
            return field, {
                "status": "CAPACITY",
                "error": str(exc),
                "field_before_sha256": before,
                "field_after_sha256": field.fingerprint(),
                "scores": scores,
                "admissions": admissions,
            }
        admissions.append(
            {
                "target": target,
                "outcome": outcome,
                "memory_action": memory_action,
                "memory_role": memory_role,
                "repeats": repeats,
                "prior_prediction": prior_prediction,
                "selectable": outcome == "promote",
                "admission": receipt["admission"],
                "field_after_sha256": receipt["field_after_sha256"],
                "prediction_status": receipt["prediction_status"],
                "predicted_outcome": receipt["predicted_outcome"],
            }
        )
    return field, {
        "status": "PASS",
        "field_before_sha256": before,
        "field_after_sha256": field.fingerprint(),
        "scores": scores,
        "chosen_target": float(episode["target"]),
        "best_target": float(best["target"]),
        "worst_target": float(worst["target"]),
        "chosen_objective": float(chosen["objective"]),
        "best_objective": float(best["objective"]),
        "regret": float(best["objective"] - chosen["objective"]),
        "admissions": admissions,
    }


def _stream_metrics(
    account: AccountState,
    *,
    initial_equity: float,
    equity_curve: Sequence[float],
    realized_returns: Sequence[float],
    turnover: float,
    cost_paid: float,
    trade_count: int,
    active_steps: int,
    winning_steps: int,
) -> dict[str, float]:
    negative = [value for value in realized_returns if value < 0.0]
    positive = [value for value in realized_returns if value > 0.0]
    deviation = pstdev(realized_returns) if len(realized_returns) > 1 else 0.0
    return {
        "net_return": account.equity / initial_equity - 1.0,
        "final_equity": account.equity,
        "max_drawdown": _max_drawdown(equity_curve),
        "turnover": turnover,
        "cost_paid": cost_paid,
        "trade_count": float(trade_count),
        "active_steps": float(active_steps),
        "active_fraction": active_steps / max(1, len(realized_returns)),
        "winning_steps": float(winning_steps),
        "hit_rate": winning_steps / max(1, active_steps),
        "profit_factor": (
            sum(positive) / sum(-value for value in negative) if negative else 0.0
        ),
        "mean_step_return": mean(realized_returns) if realized_returns else 0.0,
        "sharpe": (
            0.0
            if deviation <= 1.0e-15
            else mean(realized_returns) / deviation * math.sqrt(365.0 * 24.0)
        ),
    }


def run_aggressive_stream(
    bars: Sequence[MarketBar],
    *,
    field: RefinementField,
    program: StrategyProgram,
    config: AggressiveResidencyConfig,
    fine_context: Mapping[str, Mapping[str, float]],
    learning_enabled: bool,
    record_decisions: bool = True,
    initial_account: AccountState | Mapping[str, Any] | None = None,
) -> tuple[RefinementField, dict[str, Any], list[dict[str, Any]]]:
    owned = tuple(bars)
    regimes = _regime_timeline(owned, epoch_days=config.regime_epoch_days)
    if len(owned) < config.warmup_bars + config.outcome_horizon + 2:
        raise ValueError("aggressive residency history is too short")
    account = _clone_account(initial_account, config.initial_equity)
    initial_account_document = account.document()
    initial_equity = account.equity
    initial_field_sha256 = field.fingerprint()
    initial_checkpoint_sha256 = _sha256(field.checkpoint_bytes())
    decisions: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    lesson_rows: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    equity_curve = [account.equity]
    realized_returns: list[float] = []
    turnover = 0.0
    cost_paid = 0.0
    trade_count = 0
    active_steps = 0
    winning_steps = 0
    field_authority_steps = 0
    field_promote_steps = 0
    prediction_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    field_avoidance_steps = 0
    capacity_event: dict[str, Any] | None = None
    learning_active = learning_enabled
    target = account.position

    for index in range(config.warmup_bars - 1, len(owned) - 1):
        current = owned[index]
        following = owned[index + 1]
        context = _market_context(
            owned,
            index,
            program=program,
            account=account,
            fine_context=fine_context,
            config=config,
            regime_timeline=regimes,
        )
        rebalance = (index - config.warmup_bars + 1) % config.decision_interval == 0
        if rebalance:
            requested = program.evaluate(context["program_features"])
            selection = _choose_target(
                field,
                context["relational_contexts"],
                requested=requested,
                account=account,
                config=config,
                prediction_cache=prediction_cache,
            )
            target = float(selection["target"])
            field_authority_steps += int(selection["authority"].startswith("field-graded-"))
            field_promote_steps += int(selection["authority"] == "field-graded-promote")
            field_avoidance_steps += int(selection["authority"] == "field-graded-avoidance")
        else:
            requested = int(math.copysign(1, target)) if target != 0.0 else 0
            selection = {
                "target": target,
                "authority": "held-between-decisions",
                "field_strength": 0.0,
                "safety_override": None,
                "supported_promote_count": 0,
                "supported_reject_count": 0,
                "field_rows": [],
            }

        position_before = account.position
        gap_return = position_before * (following.open / current.close - 1.0)
        change = abs(target - position_before)
        executed_turnover = change
        executed_orders = int(change > 0.0)
        execution_cost = _execution_cost(
            change,
            volatility=float(context["features"]["volatility"]),
            config=config,
        )
        funding = abs(min(target, 0.0)) * config.short_funding_bps_daily / 10_000.0 / 24.0
        intrabar = target * (following.close / following.open - 1.0)
        stopped = False
        if target > 0.0 and following.low / following.open - 1.0 <= -config.stop_loss:
            exit_size = abs(target)
            intrabar = -exit_size * config.stop_loss
            execution_cost += _execution_cost(
                exit_size,
                volatility=float(context["features"]["volatility"]),
                config=config,
            )
            executed_turnover += exit_size
            executed_orders += 1
            target, stopped = 0.0, True
        elif target < 0.0 and following.high / following.open - 1.0 >= config.stop_loss:
            exit_size = abs(target)
            intrabar = -exit_size * config.stop_loss
            execution_cost += _execution_cost(
                exit_size,
                volatility=float(context["features"]["volatility"]),
                config=config,
            )
            executed_turnover += exit_size
            executed_orders += 1
            target, stopped = 0.0, True
        net = gap_return + intrabar - execution_cost - funding
        provisional_equity = account.equity * (1.0 + net)
        provisional_peak = max(account.peak_equity, provisional_equity)
        provisional_drawdown = 1.0 - provisional_equity / provisional_peak
        if provisional_drawdown >= config.hard_drawdown and target != 0.0:
            liquidation_size = abs(target)
            liquidation_cost = _execution_cost(
                liquidation_size,
                volatility=float(context["features"]["volatility"]),
                config=config,
            )
            execution_cost += liquidation_cost
            executed_turnover += liquidation_size
            executed_orders += 1
            net -= liquidation_cost
            target = 0.0
            account.cooldown_remaining = max(account.cooldown_remaining, config.cooldown_bars)
        account.equity *= 1.0 + net
        if not math.isfinite(account.equity) or account.equity <= 0.0:
            raise RuntimeError("aggressive residency equity became nonpositive or nonfinite")
        account.peak_equity = max(account.peak_equity, account.equity)
        if account.cooldown_remaining > 0:
            account.cooldown_remaining -= 1
        if target == 0.0:
            account.entry_price = None
            account.bars_in_position = 0
        elif position_before == 0.0 or target != position_before:
            account.entry_price = following.open
            account.bars_in_position = 1
        else:
            account.bars_in_position += 1
        account.position = target
        equity_curve.append(account.equity)
        realized_returns.append(net)
        turnover += executed_turnover
        cost_paid += execution_cost + funding
        trade_count += executed_orders
        active_steps += int(target != 0.0)
        winning_steps += int(target != 0.0 and net > 0.0)

        decision = {
            "bar_index": index,
            "next_bar_index": index + 1,
            "available_prefix_count": index + 1,
            "available_until": current.timestamp,
            "execution_timestamp": following.timestamp,
            "future_bars_excluded": len(owned) - index - 2,
            "lookahead_guard": "closed-prefix-decision-next-open-fill",
            "requested_signal": requested,
            "position_before": position_before,
            "target_requested": float(selection["target"]),
            "position_after": target,
            "authority": selection["authority"],
            "field_strength": selection["field_strength"],
            "safety_override": selection["safety_override"],
            "supported_promote_count": selection["supported_promote_count"],
            "supported_reject_count": selection["supported_reject_count"],
            "context_sha256": digest_value(list(context["context_ids"])),
            "context_features": context["features"],
            "gap_return": gap_return,
            "intrabar_return": intrabar,
            "net_return": net,
            "execution_cost": execution_cost,
            "funding": funding,
            "stopped": stopped,
            "equity": account.equity,
            "drawdown": account.drawdown,
        }
        if record_decisions and rebalance:
            decisions.append(decision)

        if (
            learning_active
            and index + config.outcome_horizon < len(owned)
            and (index - config.warmup_bars + 1) % config.lesson_interval == 0
        ):
            pending.append(
                {
                    "maturity_index": index + config.outcome_horizon,
                    "index": index,
                    "bars": owned,
                    "context_ids": context["context_ids"],
                    "learning_contexts": context["learning_contexts"],
                    "position": position_before,
                    "target": float(selection["target"]),
                    "volatility": float(context["features"]["volatility"]),
                    "timestamp": current.timestamp,
                }
            )
        matured = [row for row in pending if int(row["maturity_index"]) <= index + 1]
        pending = [row for row in pending if int(row["maturity_index"]) > index + 1]
        for episode in matured:
            field, lesson = _learn_episode(field, episode, config=config)
            episode_summary = {
                "index": episode["index"],
                "timestamp": episode["timestamp"],
                "context_ids": list(episode["context_ids"]),
                "learning_contexts": [
                    dict(row) for row in episode["learning_contexts"]
                ],
                "position": episode["position"],
                "target": episode["target"],
                "volatility": episode["volatility"],
                "lesson": lesson,
            }
            episodes.append(episode_summary)
            lesson_rows.append(episode_summary)
            if lesson["status"] == "CAPACITY":
                capacity_event = {
                    "index": episode["index"],
                    "timestamp": episode["timestamp"],
                    "error": lesson["error"],
                }
                learning_active = False
                pending.clear()
                break

    body = {
        "learning_enabled": learning_enabled,
        "learning_completed": learning_active if learning_enabled else False,
        "capacity_event": capacity_event,
        "field": {
            "before_sha256": initial_field_sha256,
            "before_checkpoint_sha256": initial_checkpoint_sha256,
            "after_sha256": field.fingerprint(),
            "after_checkpoint_sha256": _sha256(field.checkpoint_bytes()),
            "changed": initial_field_sha256 != field.fingerprint(),
        },
        "account": {
            "initial": initial_account_document,
            "initial_equity": initial_equity,
            "final": account.document(),
            "metrics": _stream_metrics(
                account,
                initial_equity=initial_equity,
                equity_curve=equity_curve,
                realized_returns=realized_returns,
                turnover=turnover,
                cost_paid=cost_paid,
                trade_count=trade_count,
                active_steps=active_steps,
                winning_steps=winning_steps,
            ),
        },
        "authority": {
            "field_supported_steps": field_authority_steps,
            "field_promote_steps": field_promote_steps,
            "field_avoidance_steps": field_avoidance_steps,
            "decision_steps": sum(
                1
                for index in range(config.warmup_bars - 1, len(owned) - 1)
                if (index - config.warmup_bars + 1) % config.decision_interval == 0
            ),
        },
        "decisions": decisions,
        "lessons": lesson_rows,
    }
    return field, body, episodes


def _purposeful_replay(
    field: RefinementField,
    episodes: Sequence[Mapping[str, Any]],
    *,
    config: AggressiveResidencyConfig,
) -> tuple[RefinementField, dict[str, Any]]:
    eligible = [row for row in episodes if row["lesson"]["status"] == "PASS"]
    failure_rows = sorted(
        eligible,
        key=lambda row: (
            -float(row["lesson"]["regret"]),
            float(row["lesson"]["chosen_objective"]),
            int(row["index"]),
        ),
    )[: config.purposeful_replay_episodes]
    stress_rows = sorted(
        eligible,
        key=lambda row: (-float(row["volatility"]), int(row["index"])),
    )[: config.stress_episodes]
    before = field.fingerprint()
    rows = []
    capacity_event = None
    for curriculum, selected, multiplier in (
        ("failure-and-missed-opportunity", failure_rows, 1.0),
        ("historical-high-volatility-high-friction", stress_rows, config.stress_cost_multiplier),
    ):
        for row in sorted(selected, key=lambda item: int(item["index"])):
            episode = {
                "index": row["index"],
                "bars": row.get("bars"),
                "learning_contexts": row["learning_contexts"],
                "position": row["position"],
                "target": row["target"],
                "volatility": row["volatility"],
            }
            if episode["bars"] is None:
                continue
            field, lesson = _learn_episode(
                field,
                episode,
                config=config,
                cost_multiplier=multiplier,
            )
            rows.append(
                {
                    "curriculum": curriculum,
                    "index": row["index"],
                    "timestamp": row["timestamp"],
                    "cost_multiplier": multiplier,
                    "lesson": lesson,
                }
            )
            if lesson["status"] == "CAPACITY":
                capacity_event = rows[-1]
                break
        if capacity_event is not None:
            break
    return field, {
        "field_before_sha256": before,
        "field_after_sha256": field.fingerprint(),
        "field_changed": before != field.fingerprint(),
        "failure_episode_count": len(failure_rows),
        "stress_episode_count": len(stress_rows),
        "capacity_event": capacity_event,
        "lessons": rows,
    }


def _episode_runtime_rows(episodes: Sequence[Mapping[str, Any]], bars: Sequence[MarketBar]) -> list[dict[str, Any]]:
    result = []
    for row in episodes:
        result.append({**row, "bars": tuple(bars)})
    return result


def _decision_comparison(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_rows = left["decisions"]
    right_rows = right["decisions"]
    if len(left_rows) != len(right_rows):
        raise ValueError("matched residency streams have different decision counts")
    return {
        "decision_count": len(left_rows),
        "changed_targets": sum(
            float(a["target_requested"]) != float(b["target_requested"])
            for a, b in zip(left_rows, right_rows)
        ),
        "changed_positions": sum(
            float(a["position_after"]) != float(b["position_after"])
            for a, b in zip(left_rows, right_rows)
        ),
        "field_authority_delta": (
            int(right["authority"]["field_supported_steps"])
            - int(left["authority"]["field_supported_steps"])
        ),
        "net_return_delta": (
            float(right["account"]["metrics"]["net_return"])
            - float(left["account"]["metrics"]["net_return"])
        ),
        "max_drawdown_delta": (
            float(right["account"]["metrics"]["max_drawdown"])
            - float(left["account"]["metrics"]["max_drawdown"])
        ),
    }


def run_aggressive_curriculum(
    bars: Sequence[MarketBar],
    *,
    initial_checkpoint: bytes,
    program: StrategyProgram,
    config: AggressiveResidencyConfig | None = None,
    fine_context: Mapping[str, Mapping[str, float]] | None = None,
) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    residency = config or AggressiveResidencyConfig()
    owned = tuple(bars)
    fine = dict(fine_context or {})
    initial_field = RefinementField.restore(initial_checkpoint)
    initial_field_sha256 = initial_field.fingerprint()
    frozen_before = RefinementField.restore(initial_checkpoint)
    _, baseline, _ = run_aggressive_stream(
        owned,
        field=frozen_before,
        program=program,
        config=residency,
        fine_context=fine,
        learning_enabled=False,
    )
    training_field = RefinementField.restore(initial_checkpoint)
    training_field, online, episodes = run_aggressive_stream(
        owned,
        field=training_field,
        program=program,
        config=residency,
        fine_context=fine,
        learning_enabled=True,
    )
    runtime_episodes = _episode_runtime_rows(episodes, owned)
    if online["capacity_event"] is None:
        training_field, purposeful = _purposeful_replay(
            training_field,
            runtime_episodes,
            config=residency,
        )
    else:
        purposeful = {
            "field_before_sha256": training_field.fingerprint(),
            "field_after_sha256": training_field.fingerprint(),
            "field_changed": False,
            "failure_episode_count": 0,
            "stress_episode_count": 0,
            "capacity_event": {
                "status": "SKIPPED_AFTER_ONLINE_CAPACITY",
                "online_capacity_event": online["capacity_event"],
            },
            "lessons": [],
        }
    final_checkpoint = training_field.checkpoint_bytes()
    frozen_after = RefinementField.restore(final_checkpoint)
    frozen_after_before = frozen_after.fingerprint()
    _, after_diagnostic, _ = run_aggressive_stream(
        owned,
        field=frozen_after,
        program=program,
        config=residency,
        fine_context=fine,
        learning_enabled=False,
    )
    if frozen_after.fingerprint() != frozen_after_before:
        raise RuntimeError("inference mutated the trained field")
    body: dict[str, Any] = {
        "schema": AGGRESSIVE_RESIDENCY_SCHEMA,
        "status": "PASS_WITH_CAPACITY_LIMIT" if online["capacity_event"] or purposeful["capacity_event"] else "PASS",
        "protocol": {
            "one_field_lineage": True,
            "field_is_sole_adaptive_state": True,
            "causal_decisions": True,
            "decision_fill": "closed-hour decision; next-hour open fill; gap carried by prior position",
            "objective": "net compounded growth with fixed cost and adverse-excursion penalties",
            "history_is_training_not_unseen": True,
            "after_diagnostic_is_revisited_history": True,
            "config": residency.as_dict(),
        },
        "data": {
            "symbol": owned[0].symbol,
            "bars": len(owned),
            "first_timestamp": owned[0].timestamp,
            "last_timestamp": owned[-1].timestamp,
            "data_sha256": digest_value([bar.as_dict() for bar in owned]),
            "fine_context_hours": len(fine),
            "fine_context_sha256": digest_value(fine),
        },
        "program": program.document(),
        "initial_field": {
            "field_sha256": initial_field_sha256,
            "checkpoint_sha256": _sha256(initial_checkpoint),
        },
        "streams": {
            "frozen_before": baseline,
            "online_training": online,
            "frozen_after_diagnostic": after_diagnostic,
        },
        "purposeful_replay": purposeful,
        "comparisons": {
            "online_vs_frozen_before": _decision_comparison(baseline, online),
            "frozen_after_vs_frozen_before": _decision_comparison(baseline, after_diagnostic),
        },
        "final_field": {
            "field_sha256": training_field.fingerprint(),
            "checkpoint_sha256": _sha256(final_checkpoint),
            "checkpoint_bytes": len(final_checkpoint),
        },
    }
    body["content_sha256"] = digest_value(body)
    runtime_state = {
        "schema": RUNTIME_STATE_SCHEMA,
        "field_checkpoint_sha256": body["final_field"]["checkpoint_sha256"],
        "field_sha256": body["final_field"]["field_sha256"],
        "program": program.document(),
        "last_closed_bar": owned[-1].timestamp,
        "account": online["account"]["final"],
        "prospective_learning": False,
    }
    runtime_state["content_sha256"] = digest_value(runtime_state)
    return body, final_checkpoint, runtime_state


def verify_aggressive_curriculum(
    receipt: Mapping[str, Any],
    *,
    checkpoint: bytes,
    runtime_state: Mapping[str, Any],
) -> dict[str, Any]:
    if receipt.get("schema") != AGGRESSIVE_RESIDENCY_SCHEMA or not str(receipt.get("status", "")).startswith("PASS"):
        raise ValueError("aggressive residency receipt is invalid")
    if not content_digest_matches(receipt) or not content_digest_matches(runtime_state):
        raise ValueError("aggressive residency content digest mismatch")
    protocol = receipt["protocol"]
    if not protocol["one_field_lineage"] or not protocol["field_is_sole_adaptive_state"]:
        raise ValueError("aggressive residency ownership contract is invalid")
    final_field = RefinementField.restore(checkpoint)
    if _sha256(checkpoint) != receipt["final_field"]["checkpoint_sha256"]:
        raise ValueError("aggressive residency checkpoint digest mismatch")
    if final_field.fingerprint() != receipt["final_field"]["field_sha256"]:
        raise ValueError("aggressive residency field fingerprint mismatch")
    if runtime_state["field_checkpoint_sha256"] != receipt["final_field"]["checkpoint_sha256"]:
        raise ValueError("runtime state does not point to the final checkpoint")
    streams = receipt["streams"]
    stream_steps = receipt["data"]["bars"] - protocol["config"]["warmup_bars"]
    interval = protocol["config"]["decision_interval"]
    expected_decisions = (stream_steps + interval - 1) // interval
    for name in ("frozen_before", "online_training", "frozen_after_diagnostic"):
        stream = streams[name]
        if len(stream["decisions"]) != expected_decisions:
            raise ValueError(f"{name} decision count mismatch")
        for row in stream["decisions"]:
            if row["next_bar_index"] != row["bar_index"] + 1:
                raise ValueError(f"{name} contains a noncausal decision")
            if row["available_prefix_count"] != row["bar_index"] + 1:
                raise ValueError(f"{name} prefix count mismatch")
    if streams["frozen_before"]["field"]["changed"]:
        raise ValueError("frozen-before field mutated")
    if streams["frozen_after_diagnostic"]["field"]["changed"]:
        raise ValueError("frozen-after field mutated")
    comparison = receipt["comparisons"]["frozen_after_vs_frozen_before"]
    recomputed = _decision_comparison(streams["frozen_before"], streams["frozen_after_diagnostic"])
    if comparison != recomputed:
        raise ValueError("aggressive residency comparison is inconsistent")
    return {
        "status": "PASS",
        "content_sha256": receipt["content_sha256"],
        "final_field_sha256": final_field.fingerprint(),
        "changed_targets": comparison["changed_targets"],
        "field_authority_steps": streams["frozen_after_diagnostic"]["authority"]["field_supported_steps"],
        "online_net_return": streams["online_training"]["account"]["metrics"]["net_return"],
        "after_diagnostic_net_return": streams["frozen_after_diagnostic"]["account"]["metrics"]["net_return"],
        "after_diagnostic_max_drawdown": streams["frozen_after_diagnostic"]["account"]["metrics"]["max_drawdown"],
    }


def run_prospective(
    bars: Sequence[MarketBar],
    *,
    checkpoint: bytes,
    program: StrategyProgram,
    config: AggressiveResidencyConfig,
    fine_context: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, Any]:
    field = RefinementField.restore(checkpoint)
    before = field.fingerprint()
    before_checkpoint = _sha256(field.checkpoint_bytes())
    _, stream, _ = run_aggressive_stream(
        bars,
        field=field,
        program=program,
        config=config,
        fine_context=dict(fine_context or {}),
        learning_enabled=False,
    )
    if field.fingerprint() != before or _sha256(field.checkpoint_bytes()) != before_checkpoint:
        raise RuntimeError("prospective inference mutated the field")
    body = {
        "schema": "cassi.trading-aggressive-prospective.v1",
        "status": "PASS",
        "field_sha256": before,
        "checkpoint_sha256": before_checkpoint,
        "learning_enabled": False,
        "data_sha256": digest_value([bar.as_dict() for bar in bars]),
        "first_timestamp": bars[0].timestamp,
        "last_timestamp": bars[-1].timestamp,
        "stream": stream,
    }
    body["content_sha256"] = digest_value(body)
    return body


def _load_program_receipt(path: Path) -> StrategyProgram:
    body = json.loads(path.read_text(encoding="utf-8"))
    if not content_digest_matches(body):
        raise ValueError("program receipt content digest mismatch")
    document = body.get("final", {}).get("program")
    if not isinstance(document, Mapping):
        raise ValueError("program receipt does not contain a final program")
    return _program_from_document(document)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--fine-history", type=Path)
    parser.add_argument("--initial-checkpoint", type=Path, required=True)
    parser.add_argument("--program-receipt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("train", "prospective"), default="train")
    parser.add_argument("--warmup-bars", type=int, default=720)
    parser.add_argument("--decision-interval", type=int, default=4)
    parser.add_argument("--lesson-interval", type=int, default=24)
    parser.add_argument("--outcome-horizon", type=int, default=12)
    parser.add_argument("--purposeful-replay-episodes", type=int, default=384)
    parser.add_argument("--stress-episodes", type=int, default=192)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = AggressiveResidencyConfig(
        warmup_bars=args.warmup_bars,
        decision_interval=args.decision_interval,
        lesson_interval=args.lesson_interval,
        outcome_horizon=args.outcome_horizon,
        purposeful_replay_episodes=args.purposeful_replay_episodes,
        stress_episodes=args.stress_episodes,
    )
    bars = load_bars_csv(args.history, symbol="BTC-USD")
    fine = load_fine_context(args.fine_history)
    checkpoint = args.initial_checkpoint.read_bytes()
    program = _load_program_receipt(args.program_receipt)
    args.output_root.mkdir(parents=True, exist_ok=True)
    if args.mode == "prospective":
        receipt = run_prospective(
            bars,
            checkpoint=checkpoint,
            program=program,
            config=config,
            fine_context=fine,
        )
        receipt_path = args.output_root / "prospective_receipt.json"
        _atomic_write(receipt_path, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        print(json.dumps({
            "status": receipt["status"],
            "receipt": str(receipt_path),
            "content_sha256": receipt["content_sha256"],
            "field_sha256": receipt["field_sha256"],
        }, sort_keys=True))
        return 0
    receipt, final_checkpoint, runtime_state = run_aggressive_curriculum(
        bars,
        initial_checkpoint=checkpoint,
        program=program,
        config=config,
        fine_context=fine,
    )
    checkpoint_path = args.output_root / "final_refinement_field.chk"
    runtime_path = args.output_root / "runtime_state.json"
    receipt_path = args.output_root / "aggressive_residency_receipt.json"
    _atomic_write(checkpoint_path, final_checkpoint)
    _atomic_write(runtime_path, (json.dumps(runtime_state, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    _atomic_write(receipt_path, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    verification = verify_aggressive_curriculum(
        receipt,
        checkpoint=checkpoint_path.read_bytes(),
        runtime_state=json.loads(runtime_path.read_text(encoding="utf-8")),
    )
    print(json.dumps({
        **verification,
        "checkpoint": str(checkpoint_path),
        "runtime_state": str(runtime_path),
        "receipt": str(receipt_path),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
