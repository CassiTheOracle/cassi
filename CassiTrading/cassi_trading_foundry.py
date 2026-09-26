"""Cassi Trading Foundry: bounded strategy programs and field-guided refinement.

This workspace is deliberately separate from the live CassiQwen runtime.  It
uses the existing bounded CassiPy interpreter to execute strategy decisions and
the field-native raw-event learner to retain reusable refinement outcomes.
The foundry only replays historical data; it has no exchange or order API.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping, Sequence


_CASSIQWEN_ROOT = Path(__file__).resolve().parents[1] / "CassiQwen" / "research"
if str(_CASSIQWEN_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSIQWEN_ROOT))

from cassi_python import (  # type: ignore  # noqa: E402
    FINANCIAL_CURRICULUM,
    execute_program,
    parse_source,
    verify_differential,
)
from cassi_market_contracts import Event, SplitManifest  # noqa: E402
from cassi_skill_bundle import build_skill_bundle, skill_contracts_from_bundle  # noqa: E402
from cassi_raw_event_field import (  # type: ignore  # noqa: E402
    CapacityError,
    AcquisitionProfile,
    RawEvent,
    RawEventLearner,
    decode_packet,
    encode_packet,
)


FOUNDRY_SCHEMA = "cassi.trading-foundry.v2"
STRATEGY_SCHEMA = "cassi.trading-strategy.v1"
MARKET_ACTION_MINIMUM_SCORE = 0.30
MARKET_ACTION_MINIMUM_MARGIN = 0.04

REFINEMENT_SCHEMA = "cassi.trading-refinement.v1"

PROGRAM_INPUTS = (
    "ready",
    "trend",
    "momentum",
    "volatility",
    "trade_return",
    "position",
    "bars_in_position",
    "fast_window",
    "slow_window",
    "momentum_window",
    "volatility_window",
    "entry_threshold",
    "exit_threshold",
    "stop_loss",
    "take_profit",
    "max_hold",
    "allow_short",
)

DEFAULT_PARAMETERS: Mapping[str, float] = {
    "fast_window": 8,
    "slow_window": 32,
    "momentum_window": 4,
    "volatility_window": 16,
    "entry_threshold": 0.004,
    "exit_threshold": 0.002,
    "stop_loss": 0.025,
    "take_profit": 0.040,
    "max_hold": 72,
    "allow_short": 0,
}

STRATEGY_SOURCES: Mapping[str, str] = {
    "trend_pullback": """if ready == 0:\n    result = 0\nelif position != 0 and trade_return <= -stop_loss:\n    result = 0\nelif position != 0 and bars_in_position >= max_hold:\n    result = 0\nelif position != 0 and position * momentum < -exit_threshold:\n    result = 0\nelif trend > entry_threshold and momentum > entry_threshold:\n    result = 1\nelif allow_short > 0 and trend < -entry_threshold and momentum < -entry_threshold:\n    result = -1\nelse:\n    result = position""",
    "breakout": """if ready == 0:\n    result = 0\nelif position != 0 and trade_return <= -stop_loss:\n    result = 0\nelif position != 0 and bars_in_position >= max_hold:\n    result = 0\nelif position != 0 and position * momentum < -exit_threshold:\n    result = 0\nelif trend > entry_threshold and momentum > entry_threshold and volatility >= entry_threshold:\n    result = 1\nelif allow_short > 0 and trend < -entry_threshold and momentum < -entry_threshold and volatility >= entry_threshold:\n    result = -1\nelse:\n    result = position""",
    "mean_reversion": """if ready == 0:\n    result = 0\nelif position != 0 and trade_return <= -stop_loss:\n    result = 0\nelif position != 0 and bars_in_position >= max_hold:\n    result = 0\nelif position != 0 and position * momentum > exit_threshold:\n    result = 0\nelif momentum < -entry_threshold and volatility <= take_profit:\n    result = 1\nelif allow_short > 0 and momentum > entry_threshold and volatility <= take_profit:\n    result = -1\nelse:\n    result = position""",
    "trend_following": """if ready == 0:\n    result = 0\nelif position != 0 and trade_return <= -stop_loss:\n    result = 0\nelif position != 0 and bars_in_position >= max_hold:\n    result = 0\nelif position != 0 and position * trend < -exit_threshold:\n    result = 0\nelif trend > entry_threshold and momentum > 0:\n    result = 1\nelif allow_short > 0 and trend < -entry_threshold and momentum < 0:\n    result = -1\nelse:\n    result = position""",
    "momentum_continuation": """if ready == 0:\n    result = 0\nelif position != 0 and trade_return <= -stop_loss:\n    result = 0\nelif position != 0 and bars_in_position >= max_hold:\n    result = 0\nelif position != 0 and position * momentum < -exit_threshold:\n    result = 0\nelif momentum > entry_threshold and trend > 0:\n    result = 1\nelif allow_short > 0 and momentum < -entry_threshold and trend < 0:\n    result = -1\nelse:\n    result = position""",
    "volatility_expansion": """if ready == 0:\n    result = 0\nelif position != 0 and trade_return <= -stop_loss:\n    result = 0\nelif position != 0 and bars_in_position >= max_hold:\n    result = 0\nelif position != 0 and position * momentum < -exit_threshold:\n    result = 0\nelif trend > entry_threshold and momentum > entry_threshold and volatility >= take_profit:\n    result = 1\nelif allow_short > 0 and trend < -entry_threshold and momentum < -entry_threshold and volatility >= take_profit:\n    result = -1\nelse:\n    result = position""",
    "range_reversion": """if ready == 0:\n    result = 0\nelif position != 0 and trade_return <= -stop_loss:\n    result = 0\nelif position != 0 and bars_in_position >= max_hold:\n    result = 0\nelif position != 0 and position * momentum > exit_threshold:\n    result = 0\nelif momentum < -entry_threshold and volatility <= entry_threshold:\n    result = 1\nelif allow_short > 0 and momentum > entry_threshold and volatility <= entry_threshold:\n    result = -1\nelse:\n    result = position""",
}


class TradingFoundryError(RuntimeError):
    """Base error for malformed strategies, data, or refinement runs."""


class MarketDataError(TradingFoundryError):
    """Historical market data violates the replay contract."""


class StrategyContractError(TradingFoundryError):
    """A candidate strategy is outside the bounded program contract."""


class RefinementError(TradingFoundryError):
    """A field-guided refinement operation failed closed."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def content_digest_matches(value: Mapping[str, Any]) -> bool:
    body = dict(value)
    stated = body.pop("content_sha256", None)
    return isinstance(stated, str) and digest_value(body) == stated


def _finite_number(name: str, value: Any, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return result


def _integer_parameter(name: str, value: float, *, minimum: int, maximum: int) -> int:
    if not math.isfinite(value) or value != int(value):
        raise StrategyContractError(f"{name} must be an integer")
    result = int(value)
    if not minimum <= result <= maximum:
        raise StrategyContractError(f"{name} must be in [{minimum}, {maximum}]")
    return result


@dataclass(frozen=True, slots=True)
class MarketBar:
    timestamp: str
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, str) or not self.timestamp:
            raise MarketDataError("bar timestamp must be nonempty text")
        if not isinstance(self.symbol, str) or not self.symbol:
            raise MarketDataError("bar symbol must be nonempty text")
        values = {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }
        for name, value in values.items():
            _finite_number(name, value, minimum=0.0)
        if min(self.open, self.close) > self.high:
            raise MarketDataError("bar high is below open or close")
        if max(self.open, self.close) < self.low:
            raise MarketDataError("bar low is above open or close")
        if self.high <= 0 or self.low <= 0:
            raise MarketDataError("bar prices must be positive")

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }

    def as_event(
        self,
        *,
        source_id: str,
        source_revision: str,
        available_at: str | None = None,
    ) -> Event:
        """Expose this replay bar through the canonical evidence contract."""
        payload = self.as_dict()
        event_id = f"{source_id}:{digest_value(payload)}"
        return Event(
            event_id=event_id,
            source_id=source_id,
            source_revision=source_revision,
            observed_at=self.timestamp,
            available_at=available_at or self.timestamp,
            event_type="market-bar",
            subject_ids=(self.symbol,),
            payload=payload,
            units={
                "open": "price",
                "high": "price",
                "low": "price",
                "close": "price",
                "volume": "asset-units",
            },
            coordinate_frame="venue-native",
        )


def _validate_bars(bars: Sequence[MarketBar]) -> tuple[MarketBar, ...]:
    if len(bars) < 12:
        raise MarketDataError("at least twelve bars are required")
    owned = tuple(bars)
    symbol = owned[0].symbol
    previous_timestamp: str | None = None
    for bar in owned:
        if bar.symbol != symbol:
            raise MarketDataError("one replay must contain exactly one symbol")
        if previous_timestamp is not None and bar.timestamp <= previous_timestamp:
            raise MarketDataError("bar timestamps must be strictly increasing")
        previous_timestamp = bar.timestamp
    return owned


def load_bars_csv(path: Path, *, symbol: str | None = None) -> tuple[MarketBar, ...]:
    """Load a strict timestamp,OHLCV CSV without reordering or filling data."""

    path = Path(path)
    if not path.is_file():
        raise MarketDataError(f"market data file does not exist: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise MarketDataError("market data CSV has no header")
        names = {name.strip().lower(): name for name in reader.fieldnames}
        timestamp_name = names.get("timestamp") or names.get("time") or names.get("date")
        required = ("open", "high", "low", "close", "volume")
        if timestamp_name is None or any(name not in names for name in required):
            raise MarketDataError(
                "CSV must contain timestamp (or time/date), open, high, low, close, volume"
            )
        symbol_name = names.get("symbol")
        rows: list[MarketBar] = []
        for line_number, row in enumerate(reader, start=2):
            try:
                row_symbol = str(row[symbol_name]).strip() if symbol_name else (symbol or "MARKET")
                if symbol is not None and row_symbol != symbol:
                    continue
                rows.append(
                    MarketBar(
                        timestamp=str(row[timestamp_name]).strip(),
                        symbol=row_symbol,
                        open=float(row[names["open"]]),
                        high=float(row[names["high"]]),
                        low=float(row[names["low"]]),
                        close=float(row[names["close"]]),
                        volume=float(row[names["volume"]]),
                    )
                )
            except (KeyError, TypeError, ValueError, MarketDataError) as exc:
                raise MarketDataError(f"invalid market row at CSV line {line_number}: {exc}") from exc
    return _validate_bars(rows)


def _sample_inputs(parameters: Mapping[str, float]) -> dict[str, Any]:
    values: dict[str, Any] = {
        "ready": 1,
        "trend": 0.01,
        "momentum": 0.01,
        "volatility": 0.01,
        "trade_return": 0.0,
        "position": 0,
        "bars_in_position": 0,
    }
    values.update(parameters)
    return values


@lru_cache(maxsize=128)
def _compile_strategy_source(source: str) -> Mapping[str, Any]:
    try:
        return parse_source(source, params=PROGRAM_INPUTS)
    except Exception as exc:
        raise StrategyContractError(f"strategy source is outside CassiPy: {exc}") from exc


@dataclass(frozen=True, slots=True)
class StrategyProgram:
    """One bounded executable strategy candidate."""

    strategy_id: str
    source: str
    parameters: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_PARAMETERS))
    family: str = "trend_pullback"
    parent_id: str | None = None
    mutation: str = "seed"

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_id, str) or not self.strategy_id:
            raise StrategyContractError("strategy_id must be nonempty")
        if not isinstance(self.source, str) or not self.source.strip() or len(self.source) > 8192:
            raise StrategyContractError("strategy source must be nonempty and <= 8192 characters")
        if self.family not in STRATEGY_SOURCES:
            raise StrategyContractError(f"unknown strategy family: {self.family}")
        raw = dict(self.parameters)
        if set(raw) != set(DEFAULT_PARAMETERS):
            raise StrategyContractError("strategy parameters do not match the fixed contract")
        normalized: dict[str, float] = {}
        for name in DEFAULT_PARAMETERS:
            normalized[name] = _finite_number(name, raw[name], minimum=0.0)
        _integer_parameter("fast_window", normalized["fast_window"], minimum=2, maximum=256)
        _integer_parameter("slow_window", normalized["slow_window"], minimum=4, maximum=512)
        _integer_parameter("momentum_window", normalized["momentum_window"], minimum=1, maximum=128)
        _integer_parameter("volatility_window", normalized["volatility_window"], minimum=2, maximum=256)
        _integer_parameter("max_hold", normalized["max_hold"], minimum=1, maximum=2048)
        if normalized["fast_window"] >= normalized["slow_window"]:
            raise StrategyContractError("fast_window must be smaller than slow_window")
        if normalized["entry_threshold"] > 0.25 or normalized["exit_threshold"] > 0.25:
            raise StrategyContractError("signal thresholds exceed the fixed bound")
        if normalized["stop_loss"] > 0.90 or normalized["take_profit"] > 0.90:
            raise StrategyContractError("risk thresholds exceed the fixed bound")
        if normalized["allow_short"] not in (0.0, 1.0):
            raise StrategyContractError("allow_short must be 0 or 1")
        compiled = _compile_strategy_source(self.source)
        try:
            result = execute_program(compiled, _sample_inputs(normalized)).value
        except Exception as exc:
            raise StrategyContractError(f"strategy source failed its contract probe: {exc}") from exc
        if isinstance(result, bool) or not isinstance(result, int) or result not in {-1, 0, 1}:
            raise StrategyContractError("strategy must emit exactly -1, 0, or 1")
        object.__setattr__(self, "parameters", normalized)

    @classmethod
    def seed(cls) -> "StrategyProgram":
        return cls(
            strategy_id="seed-trend-pullback",
            source=STRATEGY_SOURCES["trend_pullback"],
            parameters=dict(DEFAULT_PARAMETERS),
            family="trend_pullback",
        )

    @property
    def program_sha256(self) -> str:
        return digest_value(
            {
                "schema": STRATEGY_SCHEMA,
                "family": self.family,
                "source": self.source,
                "parameters": dict(self.parameters),
            }
        )

    def evaluate(self, features: Mapping[str, Any]) -> int:
        actual = {name: features[name] for name in PROGRAM_INPUTS if name in features}
        actual.update(self.parameters)
        if set(actual) != set(PROGRAM_INPUTS):
            missing = sorted(set(PROGRAM_INPUTS) - set(actual))
            raise StrategyContractError(f"strategy features missing {missing}")
        try:
            value = execute_program(_compile_strategy_source(self.source), actual).value
        except Exception as exc:
            raise StrategyContractError(f"strategy execution failed: {exc}") from exc
        if isinstance(value, bool) or not isinstance(value, int) or value not in {-1, 0, 1}:
            raise StrategyContractError("strategy emitted a value outside {-1, 0, 1}")
        return int(value)

    def document(self) -> dict[str, Any]:
        return {
            "schema": STRATEGY_SCHEMA,
            "strategy_id": self.strategy_id,
            "family": self.family,
            "source": self.source,
            "parameters": dict(self.parameters),
            "program_sha256": self.program_sha256,
            "parent_id": self.parent_id,
            "mutation": self.mutation,
        }


@dataclass(frozen=True, slots=True)
class ReplayConfig:
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    initial_equity: float = 1.0
    max_position: float = 1.0
    timeframe_hours: float = 1.0

    def __post_init__(self) -> None:
        _finite_number("fee_bps", self.fee_bps, minimum=0.0)
        _finite_number("slippage_bps", self.slippage_bps, minimum=0.0)
        _finite_number("initial_equity", self.initial_equity, minimum=1.0e-12)
        position = _finite_number("max_position", self.max_position, minimum=0.0)
        if position > 1.0:
            raise ValueError("max_position cannot exceed one without explicit leverage support")
        _finite_number("timeframe_hours", self.timeframe_hours, minimum=1.0e-9)

    @property
    def transaction_cost(self) -> float:
        return (self.fee_bps + self.slippage_bps) / 10_000.0

    def as_dict(self) -> dict[str, float]:
        return {
            "fee_bps": float(self.fee_bps),
            "slippage_bps": float(self.slippage_bps),
            "initial_equity": float(self.initial_equity),
            "max_position": float(self.max_position),
            "timeframe_hours": float(self.timeframe_hours),
        }


def _rolling_mean(values: Sequence[float], end: int, window: int) -> float:
    start = end - window + 1
    return sum(values[start : end + 1]) / window


def _features(
    bars: Sequence[MarketBar],
    index: int,
    program: StrategyProgram,
    *,
    position: float,
    entry_price: float | None,
    bars_in_position: int,
) -> dict[str, Any]:
    closes = [bar.close for bar in bars]
    parameters = program.parameters
    fast = _integer_parameter("fast_window", parameters["fast_window"], minimum=2, maximum=256)
    slow = _integer_parameter("slow_window", parameters["slow_window"], minimum=4, maximum=512)
    momentum_window = _integer_parameter(
        "momentum_window", parameters["momentum_window"], minimum=1, maximum=128
    )
    volatility_window = _integer_parameter(
        "volatility_window", parameters["volatility_window"], minimum=2, maximum=256
    )
    ready = int(index >= max(slow - 1, momentum_window, volatility_window))
    trend = 0.0
    momentum = 0.0
    volatility = 0.0
    if ready:
        fast_mean = _rolling_mean(closes, index, fast)
        slow_mean = _rolling_mean(closes, index, slow)
        trend = fast_mean / slow_mean - 1.0
        momentum = closes[index] / closes[index - momentum_window] - 1.0
        changes = [
            closes[offset] / closes[offset - 1] - 1.0
            for offset in range(index - volatility_window + 1, index + 1)
        ]
        volatility = sum(abs(value) for value in changes) / len(changes)
    trade_return = 0.0 if entry_price is None else (bars[index].close / entry_price - 1.0) * position
    result: dict[str, Any] = {
        "ready": ready,
        "trend": trend,
        "momentum": momentum,
        "volatility": volatility,
        "trade_return": trade_return,
        "position": int(position),
        "bars_in_position": int(bars_in_position),
    }
    result.update(parameters)
    return result


@dataclass(frozen=True, slots=True)
class BacktestResult:
    strategy: Mapping[str, Any]
    start_index: int
    end_index: int
    metrics: Mapping[str, float]
    decisions: tuple[Mapping[str, Any], ...]

    def as_dict(self, *, include_decisions: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema": "cassi.trading-backtest-result.v1",
            "strategy": dict(self.strategy),
            "start_index": self.start_index,
            "end_index": self.end_index,
            "metrics": dict(self.metrics),
        }
        if include_decisions:
            result["decisions"] = [dict(row) for row in self.decisions]
        return result


_FINANCIAL_LESSONS: Mapping[str, Any] = {
    lesson.lesson_id: lesson for lesson in FINANCIAL_CURRICULUM
}
FINANCIAL_SKILL_IDS = tuple(_FINANCIAL_LESSONS)


@dataclass(frozen=True, slots=True)
class FinancialRoleContract:
    """Typed slot contract for one financial composition role."""

    role: str
    input_kind: str
    output_kind: str
    skill_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.role or not self.input_kind or not self.output_kind:
            raise TradingFoundryError("financial role contracts require nonempty names")
        if not self.skill_ids:
            raise TradingFoundryError(f"financial role {self.role} has no skills")
        unknown = set(self.skill_ids) - set(_FINANCIAL_LESSONS)
        if unknown:
            raise TradingFoundryError(
                f"financial role {self.role} contains unknown skills: {sorted(unknown)}"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "input_kind": self.input_kind,
            "output_kind": self.output_kind,
            "skill_ids": list(self.skill_ids),
        }


FINANCIAL_ROLE_CONTRACTS: Mapping[str, FinancialRoleContract] = {
    "return": FinancialRoleContract(
        "return", "price-or-return-series", "scalar-return", ("FM0", "FM1")
    ),
    "risk": FinancialRoleContract(
        "risk",
        "equity-or-return-series",
        "scalar-risk",
        ("FM2", "FM7", "FM8", "FM9", "FM12"),
    ),
    "cost": FinancialRoleContract(
        "cost", "turnover-and-cost-rates", "scalar-cost", ("FM3",)
    ),
    "objective": FinancialRoleContract(
        "objective", "return-risk-turnover", "scalar-objective", ("FM5",)
    ),
    "sizing": FinancialRoleContract(
        "sizing", "equity-risk-distance", "scalar-position-size", ("FM4", "FM11")
    ),
    "performance": FinancialRoleContract(
        "performance", "return-series", "scalar-performance", ("FM6", "FM10")
    ),
}


@dataclass(frozen=True, slots=True)
class FinancialComposition:
    """A bounded, typed composition of verified financial algorithms."""

    composition_id: str
    title: str
    anchor_skill_id: str
    return_skill_id: str
    risk_skill_id: str
    cost_skill_id: str
    objective_skill_id: str
    sizing_skill_id: str
    performance_skill_id: str
    drawdown_penalty: float
    turnover_penalty: float

    def __post_init__(self) -> None:
        if not self.composition_id or not self.title:
            raise TradingFoundryError("financial compositions require an id and title")
        if self.anchor_skill_id not in _FINANCIAL_LESSONS:
            raise TradingFoundryError(f"unknown financial skill: {self.anchor_skill_id}")
        role_skills = {
            "return": self.return_skill_id,
            "risk": self.risk_skill_id,
            "cost": self.cost_skill_id,
            "objective": self.objective_skill_id,
            "sizing": self.sizing_skill_id,
            "performance": self.performance_skill_id,
        }
        for role, skill_id in role_skills.items():
            contract = FINANCIAL_ROLE_CONTRACTS[role]
            if skill_id not in contract.skill_ids:
                raise TradingFoundryError(
                    f"skill {skill_id} is not valid for financial role {role}"
                )
        _finite_number("drawdown_penalty", self.drawdown_penalty, minimum=0.0)
        _finite_number("turnover_penalty", self.turnover_penalty, minimum=0.0)

    def as_dict(self) -> dict[str, Any]:
        return {
            "grammar_version": "cassi.financial-composition.v1",
            "composition_id": self.composition_id,
            "title": self.title,
            "anchor_skill_id": self.anchor_skill_id,
            "roles": {
                "return": self.return_skill_id,
                "risk": self.risk_skill_id,
                "cost": self.cost_skill_id,
                "objective": self.objective_skill_id,
                "sizing": self.sizing_skill_id,
                "performance": self.performance_skill_id,
            },
            "return_skill_id": self.return_skill_id,
            "risk_skill_id": self.risk_skill_id,
            "cost_skill_id": self.cost_skill_id,
            "objective_skill_id": self.objective_skill_id,
            "sizing_skill_id": self.sizing_skill_id,
            "performance_skill_id": self.performance_skill_id,
            "drawdown_penalty": self.drawdown_penalty,
            "turnover_penalty": self.turnover_penalty,
        }


_NAMED_FINANCIAL_COMPOSITIONS: Mapping[str, FinancialComposition] = {
    "risk_first": FinancialComposition(
        "risk_first",
        "Drawdown-first composition",
        "FM2",
        "FM1",
        "FM2",
        "FM3",
        "FM5",
        "FM4",
        "FM6",
        2.0,
        0.001,
    ),
    "cost_aware": FinancialComposition(
        "cost_aware",
        "Execution-cost-aware composition",
        "FM3",
        "FM0",
        "FM7",
        "FM3",
        "FM5",
        "FM4",
        "FM6",
        1.5,
        0.001,
    ),
    "growth": FinancialComposition(
        "growth",
        "Compounded-growth composition",
        "FM1",
        "FM1",
        "FM7",
        "FM3",
        "FM5",
        "FM4",
        "FM6",
        1.0,
        0.00025,
    ),
    "balanced": FinancialComposition(
        "balanced",
        "Balanced risk-return composition",
        "FM5",
        "FM1",
        "FM2",
        "FM3",
        "FM5",
        "FM4",
        "FM6",
        1.5,
        0.0005,
    ),
}


def _composition_key(composition: FinancialComposition) -> tuple[Any, ...]:
    return (
        composition.return_skill_id,
        composition.risk_skill_id,
        composition.cost_skill_id,
        composition.objective_skill_id,
        composition.sizing_skill_id,
        composition.performance_skill_id,
        composition.drawdown_penalty,
        composition.turnover_penalty,
    )

def _generate_typed_financial_compositions() -> dict[str, FinancialComposition]:
    """Enumerate bounded single-slot mutations from the skill grammar."""

    generated: dict[str, FinancialComposition] = {}
    seen = {_composition_key(composition) for composition in _NAMED_FINANCIAL_COMPOSITIONS.values()}
    role_attributes = {
        "return": "return_skill_id",
        "risk": "risk_skill_id",
        "sizing": "sizing_skill_id",
        "performance": "performance_skill_id",
    }
    for preset_id, preset in _NAMED_FINANCIAL_COMPOSITIONS.items():
        for role, attribute in role_attributes.items():
            current_skill_id = str(getattr(preset, attribute))
            for skill_id in FINANCIAL_ROLE_CONTRACTS[role].skill_ids:
                if skill_id == current_skill_id:
                    continue
                values = {
                    "return_skill_id": preset.return_skill_id,
                    "risk_skill_id": preset.risk_skill_id,
                    "sizing_skill_id": preset.sizing_skill_id,
                    "performance_skill_id": preset.performance_skill_id,
                }
                values[attribute] = skill_id
                composition = FinancialComposition(
                    f"typed_{preset_id}_{role}_{skill_id}",
                    f"Typed {preset.title}: {role}/{skill_id}",
                    skill_id,
                    values["return_skill_id"],
                    values["risk_skill_id"],
                    preset.cost_skill_id,
                    preset.objective_skill_id,
                    values["sizing_skill_id"],
                    values["performance_skill_id"],
                    preset.drawdown_penalty,
                    preset.turnover_penalty,
                )
                if _composition_key(composition) in seen:
                    continue
                seen.add(_composition_key(composition))
                generated[composition.composition_id] = composition
    return generated


FINANCIAL_COMPOSITIONS: Mapping[str, FinancialComposition] = {
    **_NAMED_FINANCIAL_COMPOSITIONS,
    **_generate_typed_financial_compositions(),
}


_FINANCIAL_COMPOSITION_BY_SIGNATURE: Mapping[str, tuple[str, ...]] = {
    "drawdown": ("risk_first", "cost_aware", "balanced"),
    "cost": ("cost_aware", "risk_first", "balanced"),
    "edge": ("growth", "balanced", "risk_first"),
    "flat": ("growth", "cost_aware", "balanced"),
    "stable": ("balanced", "growth", "risk_first"),
}
_TYPED_FINANCIAL_COMPOSITION_IDS = tuple(
    composition_id
    for composition_id in sorted(FINANCIAL_COMPOSITIONS)
    if composition_id.startswith("typed_")
)
_FINANCIAL_COMPOSITION_BY_SIGNATURE = {
    signature: preferred
    + tuple(
        composition_id
        for composition_id in _TYPED_FINANCIAL_COMPOSITION_IDS
        if composition_id not in preferred
    )
    for signature, preferred in _FINANCIAL_COMPOSITION_BY_SIGNATURE.items()
}


def financial_composition_candidates(signature: str) -> tuple[FinancialComposition, ...]:
    """Return every typed composition allowed in a failure regime."""

    choices = _FINANCIAL_COMPOSITION_BY_SIGNATURE.get(signature)
    if choices is None:
        raise RefinementError(f"unknown financial composition context: {signature}")
    return tuple(FINANCIAL_COMPOSITIONS[composition_id] for composition_id in choices)


@lru_cache(maxsize=32)
def _financial_program(skill_id: str) -> Mapping[str, Any]:
    lesson = _FINANCIAL_LESSONS.get(skill_id)
    if lesson is None:
        raise TradingFoundryError(f"unknown financial skill: {skill_id}")
    return parse_source(lesson.source, params=tuple(lesson.cases[0].inputs))


def execute_financial_skill(skill_id: str, inputs: Mapping[str, Any]) -> Any:
    """Execute one verified financial algorithm through CassiPy."""

    lesson = _FINANCIAL_LESSONS.get(skill_id)
    if lesson is None:
        raise TradingFoundryError(f"unknown financial skill: {skill_id}")
    expected_inputs = set(lesson.cases[0].inputs)
    if set(inputs) != expected_inputs:
        raise TradingFoundryError(
            f"financial skill {skill_id} expects {sorted(expected_inputs)}, got {sorted(inputs)}"
        )
    return execute_program(_financial_program(skill_id), inputs).value


FINANCIAL_COMPOSITION_PROGRAM_PREFIX = "composition:"
FINANCIAL_OBJECTIVE_PERFORMANCE_WEIGHT = 0.01
FINANCIAL_OBJECTIVE_SIZING_PENALTY = 0.02
FINANCIAL_OBJECTIVE_TARGET_POSITION = 0.25



def _financial_field_predictor(field: Any) -> Any:
    predictor = getattr(field, "predict_program", None)
    if callable(predictor):
        return predictor
    inner = getattr(field, "_field", None)
    predictor = getattr(inner, "predict_program", None)
    return predictor if callable(predictor) else None


def _financial_control_prediction() -> dict[str, Any]:
    return {
        "status": "control",
        "outcome": None,
        "reason": "field-control-suppressed",
    }


def _composition_field_prediction(
    predictor: Any,
    signature: str,
    composition: FinancialComposition,
) -> dict[str, Any]:
    if not callable(predictor):
        return _financial_control_prediction()
    composition_prediction = predictor(
        "financial_math",
        FINANCIAL_COMPOSITION_PROGRAM_PREFIX + composition.composition_id,
    )
    if composition_prediction.get("outcome") is not None:
        return {
            **composition_prediction,
            "selection_scope": "composition",
        }
    anchor_prediction = predictor("financial_math", composition.anchor_skill_id)
    if anchor_prediction.get("outcome") is not None:
        return {
            **anchor_prediction,
            "selection_scope": "anchor",
            "composition_prediction": dict(composition_prediction),
        }
    return {
        **composition_prediction,
        "selection_scope": "composition",
        "composition_prediction": dict(composition_prediction),
        "anchor_prediction": dict(anchor_prediction),
    }


def select_financial_composition(
    field: Any,
    signature: str,
) -> dict[str, Any]:
    """Let field support order every typed composition for the regime."""

    choices = tuple(composition.composition_id for composition in financial_composition_candidates(signature))
    predictor = _financial_field_predictor(field)
    predictions: dict[str, Mapping[str, Any]] = {}
    for composition in financial_composition_candidates(signature):
        predictions[composition.composition_id] = _composition_field_prediction(
            predictor,
            signature,
            composition,
        )
    supported = [
        composition_id
        for composition_id in choices
        if predictions[composition_id].get("outcome") == "promote"
    ]
    supported.sort(
        key=lambda composition_id: (
            0 if predictions[composition_id].get("selection_scope") == "composition" else 1,
            choices.index(composition_id),
        )
    )
    selected_id = supported[0] if supported else choices[0]
    selected_prediction = predictions[selected_id]
    return {
        "signature": signature,
        "selected": FINANCIAL_COMPOSITIONS[selected_id].as_dict(),
        "candidates": [
            {
                "composition": FINANCIAL_COMPOSITIONS[composition_id].as_dict(),
                "field_prediction": dict(predictions[composition_id]),
            }
            for composition_id in choices
        ],
        "selection_reason": (
            "field-supported-composition"
            if supported and selected_prediction.get("selection_scope") == "composition"
            else "field-supported-anchor"
            if supported
            else "bounded-default"
        ),
    }


def fixed_financial_composition_selection(
    signature: str,
    composition_id: str,
) -> dict[str, Any]:
    """Build a receipt-visible fixed-objective selection for a control arm."""

    composition = FINANCIAL_COMPOSITIONS.get(composition_id)
    if composition is None:
        raise RefinementError(f"unknown fixed financial composition: {composition_id}")
    return {
        "signature": signature,
        "selected": composition.as_dict(),
        "candidates": [
            {
                "composition": composition.as_dict(),
                "field_prediction": {
                    "status": "fixed",
                    "outcome": "promote",
                    "reason": "fixed-objective-control",
                    "selection_scope": "fixed",
                },
            }
        ],
        "selection_reason": "fixed-objective-control",
        "fixed": True,
    }


def learn_financial_composition(
    field: Any,
    signature: str,
    composition_id: str,
    outcome: str,
) -> dict[str, Any]:
    """Write the observed composition outcome back into the owned field."""

    if composition_id not in FINANCIAL_COMPOSITIONS:
        raise RefinementError(f"unknown financial composition: {composition_id}")
    learner = getattr(field, "learn_program", None)
    if not callable(learner):
        inner = getattr(field, "_field", None)
        learner = getattr(inner, "learn_program", None)
    if not callable(learner):
        return {
            "admission": "control-suppressed",
            "repeats": 0,
            "promoted": True,
            "outcome": outcome,
        }
    return {
        **learner(
            "financial_math",
            FINANCIAL_COMPOSITION_PROGRAM_PREFIX + composition_id,
            outcome,
            repeats=2,
        ),
        "composition_id": composition_id,
        "signature": signature,
    }


def score_financial_composition(
    composition: FinancialComposition,
    metrics: Mapping[str, float],
    replay: ReplayConfig,
) -> dict[str, float]:
    """Compose the verified financial algorithms into a comparable score."""

    return_value = (
        float(metrics["arithmetic_return"])
        if composition.return_skill_id == "FM0"
        else float(metrics["net_return"])
    )
    if composition.risk_skill_id == "FM2":
        risk_value = float(metrics["max_drawdown"])
    elif composition.risk_skill_id == "FM7":
        risk_value = float(metrics["mean_absolute_return"])
    elif composition.risk_skill_id == "FM8":
        risk_value = float(metrics["downside_deviation"])
    elif composition.risk_skill_id == "FM9":
        risk_value = -float(metrics["expected_shortfall"])
    elif composition.risk_skill_id == "FM12":
        risk_value = float(
            execute_financial_skill(
                "FM12",
                {
                    "win_rate": float(metrics["hit_rate"]),
                    "risk_fraction": 0.01,
                    "loss_limit": max(float(metrics["max_drawdown"]), 0.01),
                },
            )
        )
    else:
        raise TradingFoundryError(f"unsupported financial risk skill: {composition.risk_skill_id}")
    execution_cost = float(
        execute_financial_skill(
            composition.cost_skill_id,
            {
                "turnover": float(metrics["turnover"]),
                "fee_bps": replay.fee_bps,
                "slippage_bps": replay.slippage_bps,
            },
        )
    )
    if composition.sizing_skill_id == "FM4":
        position_size = float(
            execute_financial_skill(
                "FM4",
                {
                    "equity": float(metrics["final_equity"]),
                    "risk_fraction": 0.01,
                    "stop_distance": max(risk_value, 1.0e-6),
                    "max_position": replay.max_position,
                },
            )
        )
    elif composition.sizing_skill_id == "FM11":
        position_size = float(
            execute_financial_skill(
                "FM11",
                {
                    "win_rate": float(metrics["hit_rate"]),
                    "average_win": float(metrics["average_win"]),
                    "average_loss": float(metrics["average_loss"]),
                    "max_fraction": replay.max_position,
                },
            )
        )
    else:
        raise TradingFoundryError(
            f"unsupported financial sizing skill: {composition.sizing_skill_id}"
        )
    active_steps = int(metrics.get("active_steps", 0.0))
    winning_steps = int(metrics.get("winning_steps", 0.0))
    if active_steps < 0 or winning_steps < 0 or winning_steps > active_steps:
        raise TradingFoundryError("replay performance counts are invalid")
    performance_value = 0.0
    if composition.performance_skill_id == "FM6":
        if active_steps:
            performance_value = float(
                execute_financial_skill(
                    "FM6",
                    {
                        "returns": [1.0] * winning_steps + [-1.0] * (active_steps - winning_steps),
                    },
                )
            )
    elif composition.performance_skill_id == "FM10":
        performance_value = float(metrics["profit_factor"])
    else:
        raise TradingFoundryError(
            f"unsupported financial performance skill: {composition.performance_skill_id}"
        )
    objective = float(
        execute_financial_skill(
            composition.objective_skill_id,
            {
                "net_return": return_value,
                "drawdown_penalty": composition.drawdown_penalty,
                "max_drawdown": risk_value,
                "turnover_penalty": composition.turnover_penalty,
                "turnover": float(metrics["turnover"]),
                "performance_value": performance_value,
                "performance_weight": FINANCIAL_OBJECTIVE_PERFORMANCE_WEIGHT,
                "position_size": position_size,
                "target_position": min(FINANCIAL_OBJECTIVE_TARGET_POSITION, replay.max_position),
                "sizing_penalty": FINANCIAL_OBJECTIVE_SIZING_PENALTY,
            },
        )
    )
    return {
        "return_value": return_value,
        "risk_value": risk_value,
        "execution_cost": execution_cost,
        "position_size_reference": position_size,
        "performance_value": performance_value,
        "hit_rate": float(metrics["hit_rate"]),
        "objective": objective,
        "objective_delta_vs_default": objective - float(metrics["objective"]),
    }


def _max_drawdown(equity_curve: Sequence[float]) -> float:
    peak = equity_curve[0] if equity_curve else 1.0
    maximum = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        maximum = max(maximum, 1.0 - equity / peak)
    return maximum


def _objective(metrics: Mapping[str, float]) -> float:
    return (
        float(metrics["net_return"])
        - 1.5 * float(metrics["max_drawdown"])
        - 0.0005 * float(metrics["turnover"])
    )


def run_backtest(
    bars: Sequence[MarketBar],
    program: StrategyProgram,
    config: ReplayConfig | None = None,
    *,
    start_index: int = 0,
    end_index: int | None = None,
) -> BacktestResult:
    """Replay one candidate without allowing it to see the next bar."""

    owned = _validate_bars(bars)
    replay = config or ReplayConfig()
    if end_index is None:
        end_index = len(owned) - 1
    if not 0 <= start_index < end_index <= len(owned) - 1:
        raise MarketDataError("replay interval must leave one future bar for every decision")

    position = 0.0
    entry_price: float | None = None
    bars_in_position = 0
    equity = replay.initial_equity
    equity_curve = [equity]
    decisions: list[Mapping[str, Any]] = []
    turnover = 0.0
    cost_paid = 0.0
    trade_count = 0
    active_steps = 0
    winning_steps = 0
    realized_returns: list[float] = []
    buy_hold_equity = 1.0

    for index in range(start_index, end_index):
        current = owned[index]
        following = owned[index + 1]
        position_before = position
        features = _features(
            owned,
            index,
            program,
            position=position,
            entry_price=entry_price,
            bars_in_position=bars_in_position,
        )
        requested = program.evaluate(features)
        target = float(requested)
        if program.parameters["allow_short"] == 0.0 and target < 0.0:
            target = 0.0
        target = max(-replay.max_position, min(replay.max_position, target))
        change = abs(target - position)
        if change > 0:
            trade_count += 1
        turnover += change
        cost = change * replay.transaction_cost
        cost_paid += cost
        realized = following.close / current.close - 1.0
        net = target * realized - cost
        equity *= 1.0 + net
        if not math.isfinite(equity) or equity <= 0.0:
            raise TradingFoundryError("replay equity became nonpositive or nonfinite")
        buy_hold_equity *= 1.0 + realized
        realized_returns.append(net)
        if target != 0.0:
            active_steps += 1
            if target * realized > 0.0:
                winning_steps += 1

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
                "timestamp": current.timestamp,
                "next_timestamp": following.timestamp,
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

    mean_return = mean(realized_returns) if realized_returns else 0.0
    deviation = pstdev(realized_returns) if len(realized_returns) > 1 else 0.0
    periods_per_year = 365.0 * 24.0 / replay.timeframe_hours
    sharpe = 0.0 if deviation <= 1.0e-15 else mean_return / deviation * math.sqrt(periods_per_year)
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
    if realized_returns:
        ordered_returns = sorted(realized_returns)
        tail_size = max(1, int(len(ordered_returns) * 0.20))
        tail_threshold = ordered_returns[tail_size - 1]
        tail_returns = [value for value in realized_returns if value <= tail_threshold]
        expected_shortfall = sum(tail_returns) / len(tail_returns)
    else:
        expected_shortfall = 0.0
    positive_returns = [value for value in realized_returns if value > 0.0]
    gross_profit = sum(positive_returns)
    gross_loss = sum(-value for value in negative_returns)
    profit_factor = gross_profit / gross_loss if gross_loss > 0.0 else 0.0
    average_win = gross_profit / len(positive_returns) if positive_returns else 0.0
    average_loss = gross_loss / len(negative_returns) if negative_returns else 0.0
    metrics: dict[str, float] = {
        "net_return": equity / replay.initial_equity - 1.0,
        "arithmetic_return": arithmetic_return,
        "mean_absolute_return": mean_absolute_return,
        "downside_deviation": downside_deviation,
        "expected_shortfall": expected_shortfall,
        "profit_factor": profit_factor,
        "average_win": average_win,
        "average_loss": average_loss,
        "buy_hold_return": buy_hold_equity - 1.0,
        "max_drawdown": _max_drawdown(equity_curve),
        "trade_count": float(trade_count),
        "turnover": turnover,
        "cost_paid": cost_paid,
        "active_steps": float(active_steps),
        "winning_steps": float(winning_steps),
        "active_fraction": active_steps / max(1, len(realized_returns)),
        "hit_rate": winning_steps / max(1, active_steps),
        "sharpe": sharpe,
        "final_equity": equity,
        "objective": 0.0,
    }
    metrics["objective"] = _objective(metrics)
    return BacktestResult(
        strategy=program.document(),
        start_index=start_index,
        end_index=end_index,
        metrics=metrics,
        decisions=tuple(decisions),
    )


_TRANSFER_FAMILY_CONTEXTS: Mapping[str, str] = {
    "risk": "__transfer_risk__",
    "opportunity": "__transfer_opportunity__",
    "baseline": "__transfer_baseline__",
}
_TRANSFER_FAMILY_BY_CONTEXT: Mapping[str, str] = {
    "drawdown": "risk",
    "cost": "risk",
    "edge": "opportunity",
    "flat": "opportunity",
    "stable": "baseline",
}
_TRANSFER_FAMILY_BY_CONTEXT_KEY: Mapping[str, str] = {
    context_key: family
    for family, context_key in _TRANSFER_FAMILY_CONTEXTS.items()
}
_FIELD_CONTEXT_CODES: Mapping[str, bytes] = {
    "drawdown": b"DD",
    "cost": b"CO",
    "edge": b"ED",
    "flat": b"FL",
    "stable": b"ST",
    "financial_math": b"FM",
    "__transfer_risk__": b"TR",
    "__transfer_opportunity__": b"TO",
    "__transfer_baseline__": b"TB",
}
_FIELD_MUTATION_CODES: Mapping[str, bytes] = {
    "entry_up": b"e+",
    "entry_down": b"e-",
    "exit_up": b"x+",
    "exit_down": b"x-",
    "fast_up": b"f+",
    "fast_down": b"f-",
    "slow_up": b"s+",
    "slow_down": b"s-",
    "hold_up": b"h+",
    "hold_down": b"h-",
    "mean_reversion": b"mr",
    "breakout": b"br",
    "trend_following": b"tf",
    "momentum_continuation": b"mc",
    "volatility_expansion": b"ve",
    "range_reversion": b"rr",
}

_FIELD_OUTCOME_CODES: Mapping[str, bytes] = {
    "promote": b"+",
    "reject": b"-",
    "uncertain": b"?",
}


class RefinementField:
    """Field-owned memory of which bounded refinements worked in context."""

    def __init__(
        self,
        learner: RawEventLearner | None = None,
        *,
        profile: AcquisitionProfile | None = None,
    ) -> None:
        if learner is not None and profile is not None:
            raise ValueError("RefinementField accepts either learner or profile, not both")
        self.learner = learner or RawEventLearner(profile or AcquisitionProfile())
        self._sequence = 1

    @staticmethod
    def _packet(prefix: bytes, value: bytes) -> bytes:
        return encode_packet((prefix + value,))

    def _context(self, signature: str) -> bytes:
        code = _FIELD_CONTEXT_CODES.get(signature)
        if code is None:
            raise RefinementError(f"unknown refinement context: {signature}")
        return self._packet(b"F", code)

    @staticmethod
    def _transfer_context(signature: str) -> str:
        if signature in _TRANSFER_FAMILY_CONTEXTS.values():
            return signature
        family = _TRANSFER_FAMILY_BY_CONTEXT.get(signature)
        if family is None:
            raise RefinementError(f"unknown refinement context: {signature}")
        return _TRANSFER_FAMILY_CONTEXTS[family]

    @staticmethod
    def transfer_family(signature: str) -> str:
        if signature in _TRANSFER_FAMILY_BY_CONTEXT:
            return _TRANSFER_FAMILY_BY_CONTEXT[signature]
        family = _TRANSFER_FAMILY_BY_CONTEXT_KEY.get(signature)
        if family is None:
            raise RefinementError(f"unknown refinement context: {signature}")
        return family

    def _mutation(self, mutation: str) -> bytes:
        code = _FIELD_MUTATION_CODES.get(mutation)
        if code is None:
            raise RefinementError(f"unknown refinement mutation: {mutation}")
        return self._packet(b"M", code)

    def _outcome(self, outcome: str) -> bytes:
        code = _FIELD_OUTCOME_CODES.get(outcome)
        if code is None:
            raise RefinementError(f"unknown refinement outcome: {outcome}")
        return self._packet(b"O", code)

    def _apply(
        self,
        kind: str,
        payload: bytes = b"",
        *,
        learn: bool,
        promote: bool,
    ) -> dict[str, Any]:
        event = RawEvent(self._sequence, kind, payload)
        self._sequence += 1
        return self.learner.apply(event, learn=learn, promote=promote)

    def _predict_exact(self, signature: str, mutation: str) -> dict[str, Any]:
        observation = self._context(signature)
        action = self._mutation(mutation)
        prediction = self.learner.predict(
            action,
            observation=observation,
            history=None,
            dynamic=False,
        )
        outcome: str | None = None
        payload_hex = prediction.get("payload_hex")
        if prediction.get("status") == "supported" and isinstance(payload_hex, str):
            spans = decode_packet(bytes.fromhex(payload_hex))
            for name, code in _FIELD_OUTCOME_CODES.items():
                if b"O" + code in spans:
                    outcome = name
                    break
        transfer_family = _TRANSFER_FAMILY_BY_CONTEXT_KEY.get(signature)
        return {
            "status": prediction.get("status"),
            "outcome": outcome,
            "score": prediction.get("score"),
            "margin": prediction.get("margin"),
            "reason": prediction.get("reason"),
            "context_scope": "family" if transfer_family is not None else "specific",
            "transfer_family": transfer_family,
        }

    def predict(self, signature: str, mutation: str) -> dict[str, Any]:
        specific = self._predict_exact(signature, mutation)
        if specific["outcome"] is not None:
            return specific
        family_context = self._transfer_context(signature)
        if family_context == signature:
            return specific
        family_prediction = self._predict_exact(family_context, mutation)
        if family_prediction["outcome"] is None:
            return specific
        return {
            **family_prediction,
            "reason": "field-supported-family-context",
            "specific_reason": specific["reason"],
        }

    def _lesson_plan(
        self,
        signature: str,
        action_name: str,
        outcome: str,
        *,
        repeats: int,
        program: bool = False,
        transfer_gate: bool = False,
    ) -> tuple[dict[str, Any], int, bool, str]:
        """Use the field's current readout to grade the next write.

        The optional transfer gate writes novel evidence provisionally until
        the field can reproduce it. Contradictory evidence receives a bounded
        corrective write. Repeatedly confirmed evidence receives one write,
        while uncertain evidence remains provisional. The plan is derived
        from the live field readout; no outcome table or sidecar is retained.
        """

        prediction = (
            self.predict_program(signature, action_name)
            if program
            else self.predict(signature, action_name)
        )
        predicted = prediction.get("outcome")
        if outcome == "uncertain":
            return prediction, 1, False, "uncertain-provisional"
        if predicted == outcome:
            return prediction, 1, True, "confirmed-reinforcement"
        if predicted is None and transfer_gate:
            return prediction, repeats, False, "novel-provisional"
        if predicted is None:
            return prediction, repeats, True, "novel-evidence"
        return prediction, repeats, True, "contradictory-correction"

    def _lesson_receipt(
        self,
        *,
        before: str,
        after: str,
        prediction: Mapping[str, Any],
        outcome: str,
        repeats: int,
        promoted: bool,
        admission: str,
        write_summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "prediction_status": prediction.get("status"),
            "predicted_outcome": prediction.get("outcome"),
            "prediction_context_scope": prediction.get("context_scope"),
            "prediction_transfer_family": prediction.get("transfer_family"),
            "prediction_score": prediction.get("score"),
            "prediction_margin": prediction.get("margin"),
            "specific_reason": prediction.get("specific_reason"),
            "observed_outcome": outcome,
            "admission": admission,
            "repeats": repeats,
            "promoted": promoted,
            "field_before_sha256": before,
            "field_after_sha256": after,
            "write_summary": dict(write_summary),
        }

    def _lesson_observations(
        self,
        signature: str,
        outcome: str,
        *,
        transfer_gate: bool,
    ) -> tuple[bytes, ...]:
        if transfer_gate and outcome != "uncertain":
            return (self._context(self._transfer_context(signature)),)
        return (self._context(signature),)

    def _write_lesson(
        self,
        observations: tuple[bytes, ...],
        action: bytes,
        result: bytes,
        *,
        repeats: int,
        promoted: bool,
    ) -> dict[str, Any]:
        consolidations: list[dict[str, Any]] = []
        for _ in range(repeats):
            for observation in observations:
                self._apply("reset", learn=False, promote=False)
                self._apply("observation", observation, learn=False, promote=False)
                self._apply("action", action, learn=False, promote=False)
                transition = self._apply(
                    "observation",
                    result,
                    learn=True,
                    promote=promoted,
                )
                if transition.get("consolidation_attempted"):
                    consolidations.extend(
                        dict(item)
                        for item in transition.get("consolidations", [])
                        if isinstance(item, Mapping)
                    )
        return {
            "consolidation_attempted": bool(consolidations),
            "consolidation_steps": sum(int(item["steps"]) for item in consolidations),
            "consolidations": consolidations,
        }

    def learn(
        self,
        signature: str,
        mutation: str,
        outcome: str,
        *,
        repeats: int = 2,
        transfer_gate: bool = False,
    ) -> dict[str, Any]:
        if repeats < 1 or repeats > 4:
            raise RefinementError("field lesson repeats must be in [1, 4]")
        observations = self._lesson_observations(
            signature,
            outcome,
            transfer_gate=transfer_gate,
        )
        action = self._mutation(mutation)
        result = self._outcome(outcome)
        prediction, effective_repeats, promoted, admission = self._lesson_plan(
            signature,
            mutation,
            outcome,
            repeats=repeats,
            transfer_gate=transfer_gate,
        )
        before = self.fingerprint()
        write_summary = self._write_lesson(
            observations,
            action,
            result,
            repeats=effective_repeats,
            promoted=promoted,
        )
        after = self.fingerprint()
        return self._lesson_receipt(
            before=before,
            after=after,
            prediction=prediction,
            outcome=outcome,
            repeats=effective_repeats,
            promoted=promoted,
            admission=admission,
            write_summary=write_summary,
        )

    def learn_transfer_gated(
        self,
        signature: str,
        mutation: str,
        outcome: str,
        *,
        repeats: int = 2,
    ) -> dict[str, Any]:
        return self.learn(
            signature,
            mutation,
            outcome,
            repeats=repeats,
            transfer_gate=True,
        )

    @staticmethod
    def _program_action(program_id: str) -> bytes:
        if not isinstance(program_id, str) or not program_id.strip():
            raise RefinementError("program_id must be nonempty")
        return RefinementField._packet(b"P", hashlib.sha256(program_id.encode("utf-8")).digest()[:7])

    def _predict_program_exact(self, signature: str, program_id: str) -> dict[str, Any]:
        observation = self._context(signature)
        prediction = self.learner.predict(
            self._program_action(program_id),
            observation=observation,
            history=None,
            dynamic=False,
        )
        outcome: str | None = None
        payload_hex = prediction.get("payload_hex")
        if prediction.get("status") == "supported" and isinstance(payload_hex, str):
            spans = decode_packet(bytes.fromhex(payload_hex))
            for name, code in _FIELD_OUTCOME_CODES.items():
                if b"O" + code in spans:
                    outcome = name
                    break
        transfer_family = _TRANSFER_FAMILY_BY_CONTEXT_KEY.get(signature)
        return {
            "status": prediction.get("status"),
            "outcome": outcome,
            "score": prediction.get("score"),
            "margin": prediction.get("margin"),
            "reason": prediction.get("reason"),
            "context_scope": "family" if transfer_family is not None else "specific",
            "transfer_family": transfer_family,
        }

    def predict_program(self, signature: str, program_id: str) -> dict[str, Any]:
        specific = self._predict_program_exact(signature, program_id)
        if signature not in _TRANSFER_FAMILY_BY_CONTEXT and signature not in _TRANSFER_FAMILY_BY_CONTEXT_KEY:
            return specific
        if specific["outcome"] is not None:
            return specific
        family_context = self._transfer_context(signature)
        if family_context == signature:
            return specific
        family_prediction = self._predict_program_exact(family_context, program_id)
        if family_prediction["outcome"] is None:
            return specific
        return {
            **family_prediction,
            "reason": "field-supported-family-context",
            "specific_reason": specific["reason"],
        }

    def learn_program(
        self,
        signature: str,
        program_id: str,
        outcome: str,
        *,
        repeats: int = 2,
        transfer_gate: bool = False,
    ) -> dict[str, Any]:
        if repeats < 1 or repeats > 4:
            raise RefinementError("field lesson repeats must be in [1, 4]")
        observations = self._lesson_observations(
            signature,
            outcome,
            transfer_gate=transfer_gate,
        )
        action = self._program_action(program_id)
        result = self._outcome(outcome)
        prediction, effective_repeats, promoted, admission = self._lesson_plan(
            signature,
            program_id,
            outcome,
            repeats=repeats,
            program=True,
            transfer_gate=transfer_gate,
        )
        before = self.fingerprint()
        write_summary = self._write_lesson(
            observations,
            action,
            result,
            repeats=effective_repeats,
            promoted=promoted,
        )
        after = self.fingerprint()
        return self._lesson_receipt(
            before=before,
            after=after,
            prediction=prediction,
            outcome=outcome,
            repeats=effective_repeats,
            promoted=promoted,
            admission=admission,
            write_summary=write_summary,
        )

    @staticmethod
    def _market_memory_packet(prefix: bytes, value: str) -> bytes:
        if not isinstance(value, str) or not value.strip():
            raise RefinementError("market-memory identity must be nonempty")
        return RefinementField._packet(
            prefix,
            hashlib.sha256(value.encode("utf-8")).digest()[:7],
        )

    @staticmethod
    def _market_history_packet() -> bytes:
        return RefinementField._market_memory_packet(b"H", "market-v1")

    @staticmethod
    def _market_start_packet(context_id: str) -> bytes:
        return RefinementField._market_memory_packet(b"S", context_id)

    def _predict_market_action_exact(
        self,
        context_id: str,
        action_id: str,
    ) -> dict[str, Any]:
        profile = self.learner.profile
        self.learner.profile = replace(
            profile,
            minimum_score=MARKET_ACTION_MINIMUM_SCORE,
            minimum_margin=MARKET_ACTION_MINIMUM_MARGIN,
        )
        try:
            prediction = self.learner.predict(
                self._market_memory_packet(b"A", action_id),
                observation=self._market_memory_packet(b"C", context_id),
                history=self._market_history_packet(),
                dynamic=False,
            )
        finally:
            self.learner.profile = profile
        outcome: str | None = None
        payload_hex = prediction.get("payload_hex")
        if prediction.get("status") == "supported" and isinstance(payload_hex, str):
            spans = decode_packet(bytes.fromhex(payload_hex))
            for name, code in _FIELD_OUTCOME_CODES.items():
                if b"O" + code in spans:
                    outcome = name
                    break
        return {
            "status": prediction.get("status"),
            "outcome": outcome,
            "score": prediction.get("score"),
            "margin": prediction.get("margin"),
            "reason": prediction.get("reason"),
            "context_id": context_id,
        }

    def predict_market_action(
        self,
        context_ids: Sequence[str],
        action_id: str,
    ) -> dict[str, Any]:
        """Read one market action through exact-to-broad field contexts."""

        contexts = tuple(context_ids)
        if not contexts:
            raise RefinementError("market action prediction requires context")
        predictions = [
            self._predict_market_action_exact(context_id, action_id)
            for context_id in contexts
        ]
        supported = [
            prediction
            for prediction in predictions
            if prediction.get("outcome") is not None
        ]
        selected = (
            max(
                supported,
                key=lambda prediction: (
                    float(prediction.get("score") or 0.0),
                    float(prediction.get("margin") or 0.0),
                    -contexts.index(str(prediction["context_id"])),
                ),
            )
            if supported
            else max(
                predictions,
                key=lambda prediction: (
                    float(prediction.get("score") or 0.0),
                    float(prediction.get("margin") or 0.0),
                    -contexts.index(str(prediction["context_id"])),
                ),
            )
        )
        return {
            **selected,
            "context_scope": contexts.index(str(selected["context_id"])),
            "context_count": len(contexts),
        }

    def predict_market_action_relational(
        self,
        contexts: Sequence[Mapping[str, Any]],
        action_id: str,
    ) -> dict[str, Any]:
        """Combine field-supported relations into one graded action pressure."""

        owned = tuple(dict(context) for context in contexts)
        if not owned:
            raise RefinementError("relational market prediction requires context")
        seen: set[str] = set()
        predictions: list[dict[str, Any]] = []
        for relation in owned:
            context_id = str(relation["context_id"])
            proximity = float(relation["proximity"])
            if context_id in seen:
                raise RefinementError("relational market contexts must be unique")
            if not math.isfinite(proximity) or proximity <= 0.0 or proximity > 1.0:
                raise RefinementError("market context proximity must be in (0, 1]")
            seen.add(context_id)
            prediction = self._predict_market_action_exact(context_id, action_id)
            score = float(prediction.get("score") or 0.0)
            predictions.append(
                {
                    **prediction,
                    "relation": str(relation["relation"]),
                    "temporal_offset": int(relation["temporal_offset"]),
                    "proximity": proximity,
                    "pressure": proximity * score
                    if prediction.get("outcome") in {"promote", "reject"}
                    else 0.0,
                }
            )
        promote = max(
            (
                float(prediction["pressure"])
                for prediction in predictions
                if prediction.get("outcome") == "promote"
            ),
            default=0.0,
        )
        reject = max(
            (
                float(prediction["pressure"])
                for prediction in predictions
                if prediction.get("outcome") == "reject"
            ),
            default=0.0,
        )
        net = promote - reject
        selected = max(
            predictions,
            key=lambda prediction: (
                float(prediction["pressure"]),
                float(prediction.get("margin") or 0.0),
                float(prediction["proximity"]),
            ),
        )
        outcome = "promote" if net > 0.0 else "reject" if net < 0.0 else None
        return {
            **selected,
            "status": "supported" if outcome is not None else "unresolved",
            "outcome": outcome,
            "strength": min(1.0, abs(net)),
            "promote_pressure": promote,
            "reject_pressure": reject,
            "net_pressure": net,
            "supported_context_count": sum(
                prediction.get("outcome") in {"promote", "reject"}
                for prediction in predictions
            ),
            "context_count": len(predictions),
            "relations": predictions,
        }

    def learn_market_action(
        self,
        context_ids: Sequence[str],
        action_id: str,
        outcome: str,
        *,
        repeats: int = 2,
    ) -> dict[str, Any]:
        """Write a causal market-action outcome into the owned field."""

        contexts = tuple(dict.fromkeys(context_ids))
        if not contexts:
            raise RefinementError("market action lesson requires context")
        if repeats < 1 or repeats > 4:
            raise RefinementError("field lesson repeats must be in [1, 4]")
        prediction = self.predict_market_action(contexts, action_id)
        predicted = prediction.get("outcome")
        if outcome == "uncertain":
            effective_repeats, promoted, admission = 1, False, "uncertain-provisional"
        elif predicted == outcome:
            effective_repeats, promoted, admission = 1, True, "confirmed-reinforcement"
        elif predicted is None:
            effective_repeats, promoted, admission = repeats, True, "novel-evidence"
        else:
            effective_repeats, promoted, admission = repeats, True, "contradictory-correction"
        before = self.fingerprint()
        summaries = []
        for context_id in contexts:
            consolidations: list[dict[str, Any]] = []
            for _ in range(effective_repeats):
                self._apply("reset", learn=False, promote=False)
                self._apply(
                    "observation",
                    self._market_start_packet(context_id),
                    learn=False,
                    promote=False,
                )
                self._apply(
                    "action",
                    self._market_history_packet(),
                    learn=False,
                    promote=False,
                )
                self._apply(
                    "observation",
                    self._market_memory_packet(b"C", context_id),
                    learn=False,
                    promote=False,
                )
                self._apply(
                    "action",
                    self._market_memory_packet(b"A", action_id),
                    learn=False,
                    promote=False,
                )
                transition = self._apply(
                    "observation",
                    self._outcome(outcome),
                    learn=True,
                    promote=promoted,
                )
                if transition.get("consolidation_attempted"):
                    consolidations.extend(
                        dict(item)
                        for item in transition.get("consolidations", [])
                        if isinstance(item, Mapping)
                    )
            summaries.append(
                {
                    "consolidation_attempted": bool(consolidations),
                    "consolidation_steps": sum(
                        int(item["steps"]) for item in consolidations
                    ),
                    "consolidations": consolidations,
                }
            )
        write_summary = {
            "consolidation_attempted": any(
                summary["consolidation_attempted"] for summary in summaries
            ),
            "consolidation_steps": sum(
                int(summary["consolidation_steps"]) for summary in summaries
            ),
            "consolidations": [
                row
                for summary in summaries
                for row in summary["consolidations"]
            ],
            "context_writes": len(summaries),
        }
        after = self.fingerprint()
        receipt = self._lesson_receipt(
            before=before,
            after=after,
            prediction=prediction,
            outcome=outcome,
            repeats=effective_repeats,
            promoted=promoted,
            admission=admission,
            write_summary=write_summary,
        )
        receipt["context_ids"] = list(contexts)
        receipt["action_id"] = action_id
        return receipt




    def fingerprint(self) -> str:
        return self.learner.fingerprint()
    def state_vector(self) -> tuple[float, ...]:
        """Return the owned field in deterministic row-major order."""
        return tuple(float(value) for value in self.learner.field.detach().cpu().reshape(-1).tolist())

    def checkpoint_bytes(self) -> bytes:
        return self.learner.checkpoint_bytes()

    @classmethod
    def restore(cls, blob: bytes) -> "RefinementField":
        return cls(RawEventLearner.restore(blob))

def teach_financial_math(
    field: Any,
    *,
    lessons: Sequence[Any] = FINANCIAL_CURRICULUM,
) -> dict[str, Any]:
    """Write verified financial algorithms once into an owned field or control."""

    if not lessons:
        raise RefinementError("financial math curriculum cannot be empty")
    target = field if isinstance(field, RefinementField) else getattr(field, "_field", None)
    if not isinstance(target, RefinementField):
        target = None
    field_has_memory = target is not None and any(
        abs(value) > 1.0e-12 for value in target.state_vector()
    )
    already_taught = (
        target is not None
        and (
            target.predict_program("financial_math", lessons[0].lesson_id).get("outcome") == "promote"
            or field_has_memory
        )
    )
    rows: list[dict[str, Any]] = []
    for lesson in lessons:
        differential = verify_differential(lesson.source, lesson.cases)
        if not differential["passed"]:
            raise RefinementError(f"financial lesson {lesson.lesson_id} failed differential verification")
        program_sha256 = digest_value(
            parse_source(lesson.source, params=tuple(lesson.cases[0].inputs))
        )
        if target is None:
            teaching = {
                "admission": "control-suppressed",
                "repeats": 0,
                "promoted": True,
            }
            prediction = {
                "status": "control",
                "outcome": None,
                "reason": "field-control-suppressed",
            }
        elif already_taught:
            teaching = {
                "admission": "already-present",
                "repeats": 0,
                "promoted": True,
            }
            prediction = target.predict_program("financial_math", lesson.lesson_id)
        else:
            teaching = target.learn_program(
                "financial_math",
                lesson.lesson_id,
                "promote",
                repeats=1,
            )
            prediction = target.predict_program("financial_math", lesson.lesson_id)
        rows.append(
            {
                "lesson_id": lesson.lesson_id,
                "title": lesson.title,
                "domains": list(lesson.domains),
                "program_sha256": program_sha256,
                "differential": differential,
                "teaching": teaching,
                "prediction": prediction,
            }
        )
    body = {
        "status": "PASS" if all(row["teaching"]["promoted"] for row in rows) else "FAIL",
        "context": "financial_math",
        "algorithm_count": len(rows),
        "mode": "field" if target is not None else "control-suppressed",
        "algorithms": rows,
    }
    body["content_sha256"] = digest_value(body)
    return body


def _failure_signature(metrics: Mapping[str, float]) -> str:
    if metrics["max_drawdown"] >= 0.20:
        return "drawdown"
    if metrics["turnover"] >= 12.0:
        return "cost"
    if metrics["trade_count"] < 3.0:
        return "flat"
    if metrics["net_return"] <= 0.0:
        return "edge"
    return "stable"


def _child_program(parent: StrategyProgram, mutation: str) -> StrategyProgram:
    params = dict(parent.parameters)
    family = parent.family
    source = parent.source
    if mutation == "entry_up":
        params["entry_threshold"] += 0.0005
    elif mutation == "entry_down":
        params["entry_threshold"] = max(0.0005, params["entry_threshold"] - 0.0005)
    elif mutation == "exit_up":
        params["exit_threshold"] = min(0.25, params["exit_threshold"] + 0.0005)
    elif mutation == "exit_down":
        params["exit_threshold"] = max(0.0005, params["exit_threshold"] - 0.0005)
    elif mutation == "fast_up":
        params["fast_window"] += 2
    elif mutation == "fast_down":
        params["fast_window"] = max(2, params["fast_window"] - 2)
    elif mutation == "slow_up":
        params["slow_window"] += 4
    elif mutation == "slow_down":
        params["slow_window"] = max(params["fast_window"] + 2, params["slow_window"] - 4)
    elif mutation == "hold_up":
        params["max_hold"] += 12
    elif mutation == "hold_down":
        params["max_hold"] = max(12, params["max_hold"] - 12)
    elif mutation == "mean_reversion":
        family = "mean_reversion"
        source = STRATEGY_SOURCES[family]
    elif mutation == "breakout":
        family = "breakout"
        source = STRATEGY_SOURCES[family]
    elif mutation in {
        "trend_following",
        "momentum_continuation",
        "volatility_expansion",
        "range_reversion",
    }:
        family = mutation
        source = STRATEGY_SOURCES[family]
    else:
        raise RefinementError(f"unknown mutation: {mutation}")
    return StrategyProgram(
        strategy_id=f"{parent.strategy_id}-{mutation}",
        source=source,
        parameters=params,
        family=family,
        parent_id=parent.program_sha256,
        mutation=mutation,
    )


@dataclass(frozen=True, slots=True)
class FoundryConfig:
    train_fraction: float = 0.60
    validation_fraction: float = 0.20
    validation_slices: int = 2
    max_rounds: int = 4
    max_candidates_per_round: int = 12
    minimum_improvement: float = 0.0005
    minimum_trades: int = 3
    maximum_drawdown: float = 0.35
    learn_field: bool = True
    replay: ReplayConfig = field(default_factory=ReplayConfig)

    def __post_init__(self) -> None:
        train = _finite_number("train_fraction", self.train_fraction, minimum=0.1)
        validation = _finite_number("validation_fraction", self.validation_fraction, minimum=0.1)
        if train + validation >= 0.95:
            raise ValueError("train plus validation fractions must leave a holdout")
        if self.validation_slices < 1 or self.validation_slices > 8:
            raise ValueError("validation_slices must be in [1, 8]")
        if self.max_rounds < 1 or self.max_rounds > 32:
            raise ValueError("max_rounds must be in [1, 32]")
        if self.max_candidates_per_round < 1 or self.max_candidates_per_round > len(_FIELD_MUTATION_CODES):
            raise ValueError("max_candidates_per_round exceeds the fixed mutation catalog")
        if self.minimum_trades < 1:
            raise ValueError("minimum_trades must be positive")
        _finite_number("minimum_improvement", self.minimum_improvement, minimum=0.0)
        _finite_number("maximum_drawdown", self.maximum_drawdown, minimum=0.0)
        if not isinstance(self.learn_field, bool):
            raise ValueError("learn_field must be bool")
        if train + validation <= 0.0:
            raise ValueError("development fractions must be positive")

    def as_dict(self) -> dict[str, Any]:
        return {
            "train_fraction": self.train_fraction,
            "validation_fraction": self.validation_fraction,
            "validation_slices": self.validation_slices,
            "max_rounds": self.max_rounds,
            "max_candidates_per_round": self.max_candidates_per_round,
            "minimum_improvement": self.minimum_improvement,
            "minimum_trades": self.minimum_trades,
            "maximum_drawdown": self.maximum_drawdown,
            "learn_field": self.learn_field,
            "replay": self.replay.as_dict(),
        }


def _split_indices(length: int, config: FoundryConfig) -> tuple[int, int]:
    train_end = max(4, int(length * config.train_fraction))
    validation_end = max(
        train_end + 2,
        int(length * (config.train_fraction + config.validation_fraction)),
    )
    if validation_end >= length - 2:
        raise MarketDataError("market history is too short for a frozen holdout")
    return train_end, validation_end

def _validation_ranges(
    train_end: int,
    validation_end: int,
    config: FoundryConfig,
) -> tuple[tuple[int, int], ...]:
    width = validation_end - train_end
    if width < config.validation_slices * 2:
        raise MarketDataError("validation history is too short for configured slices")
    boundaries = [
        train_end + (width * index) // config.validation_slices
        for index in range(config.validation_slices + 1)
    ]
    return tuple(
        (boundaries[index] - 1, boundaries[index + 1] - 1)
        for index in range(config.validation_slices)
    )


class StrategyRefiner:
    """Use field-recalled refinement outcomes to order bounded candidates."""

    MUTATIONS = tuple(_FIELD_MUTATION_CODES)

    def __init__(self, field_memory: RefinementField | None = None) -> None:
        self.field = field_memory or RefinementField()

    @staticmethod
    def _rank_key(prediction: Mapping[str, Any]) -> tuple[int, float]:
        outcome = prediction.get("outcome")
        priority = {"promote": 0, None: 1, "uncertain": 1, "reject": 2}.get(outcome, 1)
        score = prediction.get("score")
        return priority, -(float(score) if isinstance(score, (int, float)) else 0.0)

    def refine(
        self,
        bars: Sequence[MarketBar],
        seed: StrategyProgram,
        config: FoundryConfig,
        *,
        train_end: int,
        validation_end: int,
        financial_composition_id: str | None = None,
    ) -> tuple[StrategyProgram, list[dict[str, Any]]]:
        if (
            financial_composition_id is not None
            and financial_composition_id not in FINANCIAL_COMPOSITIONS
        ):
            raise RefinementError(
                f"unknown fixed financial composition: {financial_composition_id}"
            )
        current = seed
        rounds: list[dict[str, Any]] = []
        current_train = run_backtest(bars, current, config.replay, start_index=0, end_index=train_end - 1)
        current_validation = run_backtest(
            bars,
            current,
            config.replay,
            start_index=train_end - 1,
            end_index=validation_end - 1,
        )
        validation_ranges = _validation_ranges(train_end, validation_end, config)

        def evaluate_validation_slices(strategy: StrategyProgram) -> tuple[BacktestResult, ...]:
            return tuple(
                run_backtest(
                    bars,
                    strategy,
                    config.replay,
                    start_index=start_index,
                    end_index=end_index,
                )
                for start_index, end_index in validation_ranges
            )

        current_validation_slices = evaluate_validation_slices(current)

        for round_index in range(config.max_rounds):
            signature = _failure_signature(current_validation.metrics)
            financial_selection = (
                fixed_financial_composition_selection(signature, financial_composition_id)
                if financial_composition_id is not None
                else select_financial_composition(self.field, signature)
            )
            financial_composition = FINANCIAL_COMPOSITIONS[
                financial_selection["selected"]["composition_id"]
            ]
            predictions = {
                mutation: self.field.predict(signature, mutation) for mutation in self.MUTATIONS
            }
            ordered = sorted(self.MUTATIONS, key=lambda mutation: self._rank_key(predictions[mutation]))
            ordered = ordered[: config.max_candidates_per_round]
            candidates: list[dict[str, Any]] = []
            for mutation in ordered:
                candidate = _child_program(current, mutation)
                train_result = run_backtest(
                    bars,
                    candidate,
                    config.replay,
                    start_index=0,
                    end_index=train_end - 1,
                )
                validation_result = run_backtest(
                    bars,
                    candidate,
                    config.replay,
                    start_index=train_end - 1,
                    end_index=validation_end - 1,
                )
                parent_objective = current_validation.metrics["objective"]
                candidate_objective = validation_result.metrics["objective"]
                parent_financial = score_financial_composition(
                    financial_composition,
                    current_validation.metrics,
                    config.replay,
                )
                candidate_financial = score_financial_composition(
                    financial_composition,
                    validation_result.metrics,
                    config.replay,
                )
                candidate_validation_slices = evaluate_validation_slices(candidate)
                slice_evidence = []
                for slice_index, (parent_slice, candidate_slice) in enumerate(
                    zip(current_validation_slices, candidate_validation_slices)
                ):
                    slice_parent_objective = parent_slice.metrics["objective"]
                    slice_candidate_objective = candidate_slice.metrics["objective"]
                    slice_parent_financial = score_financial_composition(
                        financial_composition,
                        parent_slice.metrics,
                        config.replay,
                    )["objective"]
                    slice_candidate_financial = score_financial_composition(
                        financial_composition,
                        candidate_slice.metrics,
                        config.replay,
                    )["objective"]
                    slice_enough_trades = (
                        candidate_slice.metrics["trade_count"] >= config.minimum_trades
                    )
                    slice_safe_drawdown = (
                        candidate_slice.metrics["max_drawdown"] <= config.maximum_drawdown
                    )
                    slice_improved_default = (
                        slice_candidate_objective
                        >= slice_parent_objective + config.minimum_improvement
                    )
                    slice_improved = (
                        slice_candidate_financial
                        >= slice_parent_financial + config.minimum_improvement
                    )
                    slice_evidence.append(
                        {
                            "slice": slice_index,
                            "parent_objective": slice_parent_objective,
                            "candidate_objective": slice_candidate_objective,
                            "parent_financial_objective": slice_parent_financial,
                            "candidate_financial_objective": slice_candidate_financial,
                            "enough_trades": slice_enough_trades,
                            "safe_drawdown": slice_safe_drawdown,
                            "improved_default": slice_improved_default,
                            "improved": slice_improved,
                        }
                    )
                enough_trades = all(row["enough_trades"] for row in slice_evidence)
                safe_drawdown = all(row["safe_drawdown"] for row in slice_evidence)
                improved = all(row["improved"] for row in slice_evidence)
                outcome = "promote" if enough_trades and safe_drawdown and improved else "reject"
                if not enough_trades:
                    outcome = "uncertain"
                validation_worst_objective = min(
                    row["candidate_financial_objective"] for row in slice_evidence
                )
                validation_financial_objective = candidate_financial["objective"]
                field_admission: dict[str, Any] | None = None
                if config.learn_field:
                    gated_learn = getattr(self.field, "learn_transfer_gated", None)
                    if callable(gated_learn):
                        field_admission = gated_learn(signature, mutation, outcome)
                    else:
                        field_admission = self.field.learn(signature, mutation, outcome)
                field_family = None
                family_for = getattr(self.field, "transfer_family", None)
                if callable(family_for):
                    field_family = family_for(signature)
                candidates.append(
                    {
                        "mutation": mutation,
                        "field_signature": signature,
                        "field_transfer_family": field_family,
                        "financial_composition": financial_composition.as_dict(),
                        "financial_selection": financial_selection,
                        "candidate": candidate.document(),
                        "field_prediction": predictions[mutation],
                        "field_admission": field_admission,
                        "outcome": outcome,
                        "validation_worst_objective": validation_worst_objective,
                        "validation_financial_objective": validation_financial_objective,
                        "validation_default_objective": candidate_objective,
                        "financial_score": candidate_financial,
                        "validation_slice_evidence": slice_evidence,
                        "validation_slices": [
                            result.as_dict(include_decisions=False)
                            for result in candidate_validation_slices
                        ],
                        "train": train_result.as_dict(include_decisions=False),
                        "validation": validation_result.as_dict(include_decisions=False),
                    }
                )

            composition_outcome = (
                "promote"
                if any(row["outcome"] == "promote" for row in candidates)
                else "uncertain"
                if any(row["outcome"] == "uncertain" for row in candidates)
                else "reject"
            )
            if financial_composition_id is not None:
                composition_admission = {
                    "admission": "fixed-control-suppressed",
                    "composition_id": financial_composition.composition_id,
                    "signature": signature,
                    "observed_outcome": composition_outcome,
                    "promoted": True,
                }
            elif config.learn_field:
                composition_admission = learn_financial_composition(
                    self.field,
                    signature,
                    financial_composition.composition_id,
                    composition_outcome,
                )
            else:
                composition_admission = {
                    "admission": "learning-disabled",
                    "composition_id": financial_composition.composition_id,
                    "signature": signature,
                    "observed_outcome": composition_outcome,
                    "promoted": True,
                }
            promoted = [row for row in candidates if row["outcome"] == "promote"]
            selected: Mapping[str, Any] | None = None
            if promoted:
                selected = max(
                    promoted,
                    key=lambda row: (
                        row["validation_worst_objective"],
                        row["validation_financial_objective"],
                        row["validation_default_objective"],
                    ),
                )
                current = _child_program(current, str(selected["mutation"]))
                current_train = run_backtest(
                    bars,
                    current,
                    config.replay,
                    start_index=0,
                    end_index=train_end - 1,
                )
                current_validation = run_backtest(
                    bars,
                    current,
                    config.replay,
                    start_index=train_end - 1,
                    end_index=validation_end - 1,
                )
                current_validation_slices = evaluate_validation_slices(current)
            rounds.append(
                {
                    "round": round_index,
                    "parent": current.parent_id if selected is not None else current.document(),
                    "failure_signature": signature,
                    "financial_composition": financial_selection,
                    "financial_composition_override": financial_composition_id,
                    "financial_composition_outcome": composition_outcome,
                    "financial_composition_admission": composition_admission,
                    "candidates": candidates,
                    "selected_mutation": None if selected is None else selected["mutation"],
                    "selected_strategy": current.document(),
                }
            )
            if selected is None:
                break
        return current, rounds


def run_foundry(
    bars: Sequence[MarketBar],
    *,
    seed: StrategyProgram | None = None,
    config: FoundryConfig | None = None,
    field_memory: RefinementField | None = None,
    financial_composition_id: str | None = None,
) -> dict[str, Any]:
    """Develop a candidate on train/validation and evaluate it once on holdout."""
    owned = _validate_bars(bars)
    foundry = config or FoundryConfig()
    train_end, validation_end = _split_indices(len(owned), foundry)
    initial_field = field_memory or RefinementField()
    field_before_sha256 = initial_field.fingerprint()
    financial_teaching = teach_financial_math(initial_field)
    seed_program = seed or StrategyProgram.seed()
    refiner = StrategyRefiner(initial_field)
    selected, rounds = refiner.refine(
        owned,
        seed_program,
        foundry,
        train_end=train_end,
        validation_end=validation_end,
        financial_composition_id=financial_composition_id,
    )
    holdout = run_backtest(
        owned,
        selected,
        foundry.replay,
        start_index=validation_end - 1,
        end_index=len(owned) - 1,
    )
    train = run_backtest(owned, selected, foundry.replay, start_index=0, end_index=train_end - 1)
    validation = run_backtest(
        owned,
        selected,
        foundry.replay,
        start_index=train_end - 1,
        end_index=validation_end - 1,
    )
    final_financial_signature = _failure_signature(validation.metrics)
    final_financial_selection = (
        fixed_financial_composition_selection(
            final_financial_signature,
            financial_composition_id,
        )
        if financial_composition_id is not None
        else select_financial_composition(
            refiner.field,
            final_financial_signature,
        )
    )
    final_financial_composition = FINANCIAL_COMPOSITIONS[
        final_financial_selection["selected"]["composition_id"]
    ]
    validation_financial_score = score_financial_composition(
        final_financial_composition,
        validation.metrics,
        foundry.replay,
    )
    holdout_financial_score = score_financial_composition(
        final_financial_composition,
        holdout.metrics,
        foundry.replay,
    )
    field_checkpoint = refiner.field.checkpoint_bytes()
    source_id = f"trading-foundry:{owned[0].symbol}"
    source_revision = "market-bars.v1"
    events = tuple(
        bar.as_event(source_id=source_id, source_revision=source_revision)
        for bar in owned
    )
    data_sha256 = digest_value([bar.as_dict() for bar in owned])
    event_root_sha256 = digest_value([event.as_dict() for event in events])
    split_manifest = SplitManifest(
        manifest_id=f"foundry-split:{data_sha256}",
        availability_cutoff=owned[-1].timestamp,
        partitions={
            "train": tuple(event.event_id for event in events[:train_end]),
            "validation": tuple(event.event_id for event in events[train_end:validation_end]),
            "holdout": tuple(event.event_id for event in events[validation_end:]),
        },
        source_digests={source_id: data_sha256},
    )
    skill_bundle = build_skill_bundle()
    skill_contracts = skill_contracts_from_bundle(skill_bundle)
    skill_contract_sha256 = digest_value([contract.as_dict() for contract in skill_contracts])
    financial_skill_ids = [
        row["skill_id"] for row in skill_bundle["skills"] if "financial-math" in row["domains"]
    ]
    field_checkpoint_sha256 = hashlib.sha256(field_checkpoint).hexdigest()
    field_closure_sha256 = digest_value(
        {
            "field_checkpoint_sha256": field_checkpoint_sha256,
            "capability_bundle_sha256": skill_bundle["content_sha256"],
            "skill_contract_sha256": skill_contract_sha256,
            "financial_teaching_sha256": financial_teaching["content_sha256"],
        }
    )
    body: dict[str, Any] = {
        "schema": FOUNDRY_SCHEMA,
        "status": "PASS",
        "data": {
            "symbol": owned[0].symbol,
            "bars": len(owned),
            "data_sha256": data_sha256,
            "event_schema": "cassi.market-event.v1",
            "event_root_sha256": event_root_sha256,
            "source_id": source_id,
            "source_revision": source_revision,
            "train_end": train_end,
            "validation_end": validation_end,
            "holdout_start": validation_end - 1,
            "split_manifest": split_manifest.as_dict(),
            "split_manifest_sha256": split_manifest.content_sha256,
            "capability_bundle_schema": skill_bundle["schema"],
            "capability_bundle_sha256": skill_bundle["content_sha256"],
            "skill_contract_sha256": skill_contract_sha256,
            "skill_ids": [contract.skill_id for contract in skill_contracts],
            "financial_skill_ids": financial_skill_ids,
        },
        "seed": seed_program.document(),
        "selected": selected.document(),
        "development": {
            "train": train.as_dict(include_decisions=False),
            "validation": validation.as_dict(include_decisions=False),
            "rounds": rounds,
        },
        "holdout": holdout.as_dict(include_decisions=True),
        "financial": {
            "selection_signature": final_financial_signature,
            "selection": final_financial_selection,
            "composition": final_financial_composition.as_dict(),
            "override": financial_composition_id,
            "validation": validation_financial_score,
            "holdout": holdout_financial_score,
            "holdout_minus_validation": (
                holdout_financial_score["objective"] - validation_financial_score["objective"]
            ),
        },
        "field": {
            "adaptive_object": "RawEventLearner.state.field / QiFieldState.field",
            "before_sha256": field_before_sha256,
            "after_sha256": refiner.field.fingerprint(),
            "checkpoint_sha256": field_checkpoint_sha256,
            "checkpoint_bytes": len(field_checkpoint),
            "closure_sha256": field_closure_sha256,
            "capability_bundle_sha256": skill_bundle["content_sha256"],
            "skill_contract_sha256": skill_contract_sha256,
            "financial_teaching": financial_teaching,
            "qwen_calls": 0,
            "teacher_calls": 0,
        },
        "ownership": {
            "strategy_program_executor": "CassiPy bounded interpreter",
            "financial_math_executor": "CassiPy bounded interpreter",
            "strategy_selection": "field-guided bounded refinement",
            "live_exchange_calls": 0,
            "adaptive_sidecars": 0,
            "deployment_mode": "historical-replay-only",
        },
        "config": foundry.as_dict(),
    }
    body["content_sha256"] = digest_value(body)
    return body


def write_foundry_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_foundry_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != FOUNDRY_SCHEMA:
        raise TradingFoundryError("foundry receipt schema mismatch")
    if receipt.get("status") != "PASS":
        raise TradingFoundryError("foundry receipt is not a pass")
    if not content_digest_matches(receipt):
        raise TradingFoundryError("foundry receipt content digest mismatch")
    field_info = receipt.get("field")
    if not isinstance(field_info, Mapping) or field_info.get("qwen_calls") != 0:
        raise TradingFoundryError("foundry receipt reports an unexpected Qwen call")
    data_info = receipt.get("data")
    if not isinstance(data_info, Mapping):
        raise TradingFoundryError("foundry receipt has no canonical data metadata")
    capability_bundle = build_skill_bundle()
    capability_contracts = skill_contracts_from_bundle(capability_bundle)
    capability_bundle_sha256 = capability_bundle["content_sha256"]
    skill_contract_sha256 = digest_value([contract.as_dict() for contract in capability_contracts])
    financial_skill_ids = [
        row["skill_id"] for row in capability_bundle["skills"] if "financial-math" in row["domains"]
    ]
    if data_info.get("capability_bundle_sha256") != capability_bundle_sha256:
        raise TradingFoundryError("foundry receipt capability bundle is stale")
    if data_info.get("skill_contract_sha256") != skill_contract_sha256:
        raise TradingFoundryError("foundry receipt skill contract closure is stale")
    if data_info.get("financial_skill_ids") != financial_skill_ids:
        raise TradingFoundryError("foundry receipt financial skill closure is stale")
    if field_info.get("capability_bundle_sha256") != capability_bundle_sha256:
        raise TradingFoundryError("field closure has no capability bundle identity")
    if field_info.get("skill_contract_sha256") != skill_contract_sha256:
        raise TradingFoundryError("field closure has no skill contract identity")
    financial_teaching = field_info.get("financial_teaching")
    if not isinstance(financial_teaching, Mapping) or financial_teaching.get("status") != "PASS":
        raise TradingFoundryError("foundry field did not pass financial math teaching")
    if not content_digest_matches(financial_teaching):
        raise TradingFoundryError("foundry financial teaching digest mismatch")
    taught_ids = [row.get("lesson_id") for row in financial_teaching.get("algorithms", [])]
    if taught_ids != financial_skill_ids:
        raise TradingFoundryError("foundry financial teaching does not cover the skill bundle")
    checkpoint_sha256 = field_info.get("checkpoint_sha256")
    closure_sha256 = field_info.get("closure_sha256")
    expected_closure_sha256 = digest_value(
        {
            "field_checkpoint_sha256": checkpoint_sha256,
            "capability_bundle_sha256": capability_bundle_sha256,
            "skill_contract_sha256": skill_contract_sha256,
            "financial_teaching_sha256": financial_teaching["content_sha256"],
        }
    )
    if not isinstance(checkpoint_sha256, str) or closure_sha256 != expected_closure_sha256:
        raise TradingFoundryError("foundry field closure digest mismatch")
    selected = receipt.get("selected")
    if not isinstance(selected, Mapping) or not selected.get("program_sha256"):
        raise TradingFoundryError("foundry receipt has no selected strategy identity")
    financial_info = receipt.get("financial")
    if not isinstance(financial_info, Mapping):
        raise TradingFoundryError("foundry receipt has no financial composition")
    composition = financial_info.get("composition")
    if not isinstance(composition, Mapping) or composition.get("composition_id") not in FINANCIAL_COMPOSITIONS:
        raise TradingFoundryError("foundry receipt has an unknown financial composition")
    for key in (
        "anchor_skill_id",
        "return_skill_id",
        "risk_skill_id",
        "cost_skill_id",
        "objective_skill_id",
        "sizing_skill_id",
        "performance_skill_id",
    ):
        if composition.get(key) not in financial_skill_ids:
            raise TradingFoundryError(f"financial composition references an unbound skill: {key}")
    for split in ("validation", "holdout"):
        score = financial_info.get(split)
        if not isinstance(score, Mapping) or not isinstance(score.get("objective"), (int, float)):
            raise TradingFoundryError(f"financial {split} score is missing")
    return {
        "status": "PASS",
        "content_sha256": receipt["content_sha256"],
        "selected_program_sha256": selected["program_sha256"],
    }


def generate_demo_bars(count: int = 240, *, symbol: str = "BTCUSDT") -> tuple[MarketBar, ...]:
    """Generate a deterministic multi-regime market for local development smokes."""

    if count < 32:
        raise ValueError("demo market requires at least 32 bars")
    price = 100.0
    bars: list[MarketBar] = []
    for index in range(count):
        block = (index // 32) % 4
        if block == 0:
            drift = 0.006
        elif block == 1:
            drift = -0.004
        elif block == 2:
            drift = 0.003
        else:
            drift = -0.002
        oscillation = 0.0012 * math.sin(index * 1.7)
        change = drift + oscillation
        opening = price
        closing = opening * (1.0 + change)
        high = max(opening, closing) * 1.001
        low = min(opening, closing) * 0.999
        bars.append(
            MarketBar(
                timestamp=f"2025-01-01T{index:04d}Z",
                symbol=symbol,
                open=opening,
                high=high,
                low=low,
                close=closing,
                volume=1000.0 + 25.0 * (index % 11),
            )
        )
        price = closing
    return tuple(bars)


__all__ = [
    "BacktestResult",
    "FINANCIAL_COMPOSITIONS",
    "FINANCIAL_ROLE_CONTRACTS",
    "FINANCIAL_SKILL_IDS",
    "FOUNDRY_SCHEMA",
    "FinancialComposition",
    "FinancialRoleContract",
    "FoundryConfig",
    "MarketBar",
    "MarketDataError",
    "RefinementField",
    "ReplayConfig",
    "STRATEGY_SCHEMA",
    "StrategyContractError",
    "StrategyProgram",
    "StrategyRefiner",
    "TradingFoundryError",
    "teach_financial_math",
    "execute_financial_skill",
    "financial_composition_candidates",
    "fixed_financial_composition_selection",
    "learn_financial_composition",
    "score_financial_composition",
    "select_financial_composition",
    "content_digest_matches",
    "digest_value",
    "generate_demo_bars",
    "load_bars_csv",
    "run_backtest",
    "run_foundry",
    "verify_foundry_receipt",
    "write_foundry_receipt",
]
